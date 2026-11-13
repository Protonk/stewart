"""Offline invocation controls. Every executable is the selected Python interpreter."""

import base64
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('bounded', Path(__file__).with_name('bounded.py'))
bounded = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bounded)
RUN = Path(tempfile.mkdtemp(prefix='stewart-bounded-controls-')).resolve()
PYTHON = str(Path(sys.executable).resolve())
SECRET = 'discarded-private-auth-canary-3a4f'
FAKE = '''import json,os,signal,sys,time
from pathlib import Path
mode, witness = sys.argv[1:]
with Path(witness).open('ab',buffering=0) as out:
    out.write((mode+'\\n').encode())
if mode.startswith('auth'):
    value={'loggedIn':True,'authMethod':'claude.ai','configDirectory':os.environ['CLAUDE_CONFIG_DIR'],'secret':'discarded-private-auth-canary-3a4f'}
    if mode=='auth-wrong': value['authMethod']='api-key'
    if mode=='auth-number': value['loggedIn']=1
    if mode=='auth-malformed':
        print('discarded-private-auth-canary-3a4f {')
    elif mode=='auth-overflow':
        value['padding']='x'*70000
        print(json.dumps(value))
    else: print(json.dumps(value))
    print('discarded-private-auth-canary-3a4f',file=sys.stderr)
elif mode=='model':
    raw=sys.stdin.buffer.read()
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    print('diagnostic',file=sys.stderr)
elif mode=='reject':
    print('reject this event',flush=True)
    time.sleep(30)
elif mode=='nonzero': raise SystemExit(7)
elif mode in ('stall','descendant'):
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    if mode=='descendant':
        child=os.fork()
        if child==0:
            Path(witness+'.child').write_text(str(os.getpid()))
            while True: time.sleep(1)
    print('ready',flush=True)
    while True: time.sleep(1)
'''


def observe_group(group, seconds, probe=None):
    """Bounded read-only observations: EPERM stays unknown, never absent."""
    probe = os.killpg if probe is None else probe
    started = bounded.now()
    result = {'group': group, 'clock': bounded.CLOCK_NAME, 'observer_pid': os.getpid(),
              'started': started, 'observations': [], 'state': 'unknown'}
    while True:
        error = None
        try:
            probe(group, 0)
            state = 'present'
        except ProcessLookupError as exc:
            state, error = 'absent', exc.errno
        except PermissionError as exc:
            state, error = 'unknown', exc.errno
        observed = bounded.now()
        result['observations'].append({'at': observed, 'state': state, 'errno': error})
        result['state'] = state
        result['elapsed_seconds'] = observed - started
        if state == 'absent' or observed >= started + seconds:
            return result
        time.sleep(min(0.02, max(0, started + seconds - bounded.now())))


class BoundedControls(unittest.TestCase):
    def setUp(self):
        self.root = RUN / self._testMethodName
        self.root.mkdir()
        self.fake = self.root / 'fake.py'
        self.fake.write_text(FAKE)
        self.witness = self.root / 'independent-launches.txt'
        self.budget_root = self.root / 'budget'

    def value(self, auth='auth', model='model', mode='synthetic-rehearsal', timeout=2):
        environment = {'PATH': '/usr/bin:/bin', 'CLAUDE_CONFIG_DIR': str(self.root / 'config')}
        slots = []
        for identity, role, behavior in [('fresh-auth', 'auth', auth), ('case', 'model', model)]:
            slots.append({'id': identity, 'role': role,
                'argv': [PYTHON, '-I', '-B', str(self.fake), behavior, str(self.witness)],
                'environment': environment.copy(), 'working_directory': str(self.root),
                'stdin_base64': base64.b64encode(b'' if role == 'auth' else b'first input\n').decode(),
                'timeout_seconds': timeout})
        value = {'schema': 'stewart.claude-code.invocation-budget/1', 'mode': mode,
                 'purpose': 'offline process and reservation controls', 'overall_timeout_seconds': 10,
                 'bindings': [{'path': str(path), 'sha256': bounded.data.read_file(Path(path), limit=None, hash_only=True)[0]}
                              for path in (PYTHON, self.fake)], 'invocations': slots}
        return value

    def run_pair(self, value=None, **callbacks):
        bounded.prepare(self.budget_root, value or self.value())
        with bounded.Budget(self.budget_root) as book:
            auth = book.execute('fresh-auth')
            self.assertIsNone(auth['stop'], auth)
            result = book.execute('case', **callbacks)
        return result

    def test_prepare_and_approval_gate_never_execute(self):
        value = self.value(mode='real-harness')
        for slot in value['invocations']:
            slot['argv'] = [PYTHON, 'auth', 'status'] if slot['role'] == 'auth' else [PYTHON, '-c', 'raise SystemExit(99)']
        digest = bounded.prepare(self.budget_root, value)
        self.assertFalse((self.budget_root / 'START.json').exists())
        for approved, disabled in [(None, False), (digest, False), ('0' * 64, True)]:
            with self.assertRaisesRegex(ValueError, 'principal-approved'):
                with bounded.Budget(self.budget_root, approved, disabled):
                    self.fail('unauthorized budget opened')
        self.assertFalse(self.witness.exists())
        self.assertFalse((self.budget_root / 'START.json').exists())
        # The differing control must admit the exact digest/condition without
        # starting any invocation merely by opening the budget.
        with bounded.Budget(self.budget_root, digest, True):
            self.assertTrue((self.budget_root / 'START.json').exists())
            self.assertFalse(self.witness.exists())

    def test_positive_and_invariance_capture_and_private_auth(self):
        for name in ('positive', 'invariance'):
            self.budget_root = self.root / name
            stdout, stderr = bytearray(), bytearray()
            result = self.run_pair(on_stdout=stdout.extend, on_stderr=stderr.extend)
            self.assertIsNone(result['stop'], result)
            self.assertEqual(bytes(stdout), b'first input\n')
            self.assertEqual(bytes(stderr), b'diagnostic\n')
            self.assertEqual(result['stream_eof'], {'stdout': True, 'stderr': True})
            self.assertTrue(result['group_gone'] and result['guard_reaped'])
            for channel, content in [('stdout', stdout), ('stderr', stderr)]:
                self.assertEqual(result['capture_sha256'][channel], bounded.data.sha(content))
                self.assertEqual(result['capture_bytes'][channel], len(content))
                self.assertEqual((self.budget_root / 'uses/case' / (channel + '.bin')).read_bytes(), content)
            self.assertEqual(result['input_prefix_sha256'], bounded.data.sha(b'first input\n'))
            auth = self.budget_root / 'uses/fresh-auth'
            self.assertEqual(set(json.loads((auth / 'auth-status.json').read_bytes())),
                             {'loggedIn', 'authMethod', 'configDirectory'})
            for path in self.budget_root.rglob('*'):
                if path.is_file():
                    self.assertNotIn(SECRET.encode(), path.read_bytes(), str(path))
            self.assertFalse((auth / 'stdout.bin').exists())
            self.assertFalse((auth / 'stderr.bin').exists())
        self.assertEqual(self.witness.read_text().splitlines(), ['auth', 'model', 'auth', 'model'])

    def test_failed_authentication_stops_before_model_and_discards_raw(self):
        for behavior in ('auth-wrong', 'auth-number', 'auth-malformed', 'auth-overflow'):
            self.budget_root = self.root / behavior
            bounded.prepare(self.budget_root, self.value(auth=behavior))
            with bounded.Budget(self.budget_root) as book:
                result = book.execute('fresh-auth')
                self.assertIsNotNone(result['stop'])
                if behavior == 'auth-overflow':
                    self.assertEqual(result['stop'], 'private authentication failed')
                self.assertTrue(result['group_gone'], result)
                with self.assertRaisesRegex(ValueError, 'no further start'):
                    book.execute('case')
            for path in self.budget_root.rglob('*'):
                if path.is_file():
                    self.assertNotIn(SECRET.encode(), path.read_bytes(), str(path))
        self.assertNotIn('model', self.witness.read_text().splitlines())
        # The same oversized JSON authenticates when only the output bound is
        # raised. This distinguishes the bound from JSON or route validation.
        self.budget_root = self.root / 'auth-overflow-nonbinding-control'
        bounded.prepare(self.budget_root, self.value(auth='auth-overflow'))
        with patch.object(bounded, 'AUTH_LIMIT', 100000), bounded.Budget(self.budget_root) as book:
            result = book.execute('fresh-auth')
            self.assertIsNone(result['stop'], result)
            self.assertTrue(result['group_gone'], result)

    def test_authentication_never_calls_model_observers(self):
        bounded.prepare(self.budget_root, self.value())
        def forbidden(*args):
            self.fail('private authentication reached a model observer')
        with bounded.Budget(self.budget_root) as book:
            result = book.execute('fresh-auth', on_stdout=forbidden, on_stderr=forbidden, check_stop=forbidden)
            self.assertIsNone(result['stop'], result)

    def test_unknown_group_observation_blocks_another_start(self):
        bounded.prepare(self.budget_root, self.value())
        killpg = os.killpg
        def unavailable(group, sig):
            if sig == 0:
                raise PermissionError('process observation denied by control')
            return killpg(group, sig)
        with bounded.Budget(self.budget_root) as book:
            with patch.object(bounded.os, 'killpg', unavailable):
                result = book.execute('fresh-auth')
            self.assertFalse(result['group_gone'])
            self.assertIsNotNone(result['stop'])
            with self.assertRaisesRegex(ValueError, 'no further start'):
                book.execute('case')
        group = json.loads((self.budget_root / 'uses/fresh-auth/group.json').read_bytes())['group']
        with self.assertRaises(ProcessLookupError):
            killpg(group, 0)  # Independent observation after the refusal control.
        self.assertEqual(self.witness.read_text().splitlines(), ['auth'])

    def test_observer_failure_retains_bytes_and_stops_group(self):
        def reject(raw):
            path = self.budget_root / 'uses/case/stdout.bin'
            self.assertIn(raw, path.read_bytes())  # Witness exists before interpretation.
            raise ValueError('independent observer refused event')
        result = self.run_pair(self.value(model='reject'), on_stdout=reject)
        self.assertIn('observer refused', result['stop'])
        self.assertTrue(result['group_gone'], result)
        self.assertIn(b'reject this event', (self.budget_root / 'uses/case/stdout.bin').read_bytes())

    def test_timeout_stops_uncooperative_worker_and_descendant(self):
        result = self.run_pair(self.value(model='descendant', timeout=1))
        self.assertIsNotNone(result['stop'])
        self.assertTrue(result['group_gone'] and result['guard_reaped'], result)
        self.assertLess(result['elapsed_seconds'], 4)
        self.assertIn(b'ready', (self.budget_root / 'uses/case/stdout.bin').read_bytes())
        child = int(Path(str(self.witness) + '.child').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)

    def test_silent_fixture_failure_revokes_running_process(self):
        def stopped():
            output = self.budget_root / 'uses/case/stdout.bin'
            if output.exists() and b'ready' in output.read_bytes():
                raise ValueError('independent fixture failed while stdout was silent')
        result = self.run_pair(self.value(model='stall'), check_stop=stopped)
        self.assertIn('fixture failed', result['stop'])
        self.assertTrue(result['group_gone'], result)
        self.assertLess(result['elapsed_seconds'], 1.5)

    def test_stalled_observer_cannot_extend_process_deadline(self):
        def stalled(raw):
            if b'ready' in raw:
                time.sleep(1.8)
        result = self.run_pair(self.value(model='stall', timeout=1), on_stdout=stalled)
        self.assertIsNotNone(result['stop'])
        self.assertTrue(result['group_gone'] and result['guard_reaped'], result)
        self.assertEqual(result['guard_reason'], 'deadline')

    def test_whole_batch_deadline_cannot_reset_between_slots(self):
        value = self.value(model='stall', timeout=2)
        def delayed_pair():
            bounded.prepare(self.budget_root, value)
            with bounded.Budget(self.budget_root) as book:
                self.assertIsNone(book.execute('fresh-auth')['stop'])
                time.sleep(0.75)
                return book.execute('case')
        value['overall_timeout_seconds'] = 2
        result = delayed_pair()
        self.assertEqual(result['guard_reason'], 'deadline')
        self.assertTrue(result['group_gone'], result)
        self.assertLess(result['elapsed_seconds'], 1.5)
        self.budget_root = self.root / 'nonbinding-batch'
        value['overall_timeout_seconds'] = 10
        comparison = delayed_pair()
        self.assertEqual(comparison['guard_reason'], 'deadline')
        self.assertTrue(comparison['group_gone'], comparison)
        self.assertGreater(comparison['elapsed_seconds'], 1.8)

    def test_nonzero_exit_is_failure(self):
        result = self.run_pair(self.value(model='nonzero'))
        self.assertEqual(result['exit'], 7)
        self.assertIsNotNone(result['stop'])
        self.assertTrue(result['group_gone'])

    def test_reservation_failure_prevents_fork(self):
        bounded.prepare(self.budget_root, self.value())
        original = bounded.record
        def fail(path, value):
            if path.name == 'RESERVATION.json':
                raise OSError('reservation storage unavailable')
            return original(path, value)
        with bounded.Budget(self.budget_root) as book, patch.object(bounded, 'record', side_effect=fail):
            with patch.object(bounded, 'supervise') as launch:
                with self.assertRaisesRegex(OSError, 'reservation storage'):
                    book.execute('fresh-auth')
                launch.assert_not_called()
        self.assertFalse(self.witness.exists())
        with self.assertRaises(FileExistsError):
            with bounded.Budget(self.budget_root):
                self.fail('uncertain batch reused')

    def test_group_record_failure_prevents_exec(self):
        bounded.prepare(self.budget_root, self.value())
        original = bounded.record
        def fail(path, value):
            if path.name == 'group.json':
                raise OSError('group witness unavailable')
            return original(path, value)
        with bounded.Budget(self.budget_root) as book, patch.object(bounded, 'record', side_effect=fail):
            result = book.execute('fresh-auth')
            self.assertIsNotNone(result['stop'])
            self.assertTrue(result['group_gone'], result)
        self.assertFalse(self.witness.exists())
        self.assertTrue((self.budget_root / 'uses/fresh-auth/RESERVATION.json').exists())

    def test_changed_binding_after_auth_refuses_model(self):
        bounded.prepare(self.budget_root, self.value())
        with bounded.Budget(self.budget_root) as book:
            self.assertIsNone(book.execute('fresh-auth')['stop'])
            self.fake.write_text(FAKE + '\n# changed\n')
            with self.assertRaisesRegex(ValueError, 'bound file changed'):
                book.execute('case')
        self.assertEqual(self.witness.read_text().splitlines(), ['auth'])

    def test_changed_budget_after_auth_refuses_model(self):
        bounded.prepare(self.budget_root, self.value())
        with bounded.Budget(self.budget_root) as book:
            self.assertIsNone(book.execute('fresh-auth')['stop'])
            with (self.budget_root / 'BUDGET.json').open('ab') as output:
                output.write(b'\n')
            with self.assertRaisesRegex(ValueError, 'budget changed'):
                book.execute('case')
        self.assertEqual(self.witness.read_text().splitlines(), ['auth'])

    def test_failed_independent_assessment_closes_batch(self):
        bounded.prepare(self.budget_root, self.value())
        with bounded.Budget(self.budget_root) as book:
            self.assertIsNone(book.execute('fresh-auth')['stop'])
            book.halt('independent comparison failed')
            with self.assertRaisesRegex(ValueError, 'no further start'):
                book.execute('case')
        self.assertEqual(self.witness.read_text().splitlines(), ['auth'])
        self.assertTrue(json.loads((self.budget_root / 'FINISH.json').read_bytes())['failed'])

    def test_changed_in_memory_slot_does_not_bypass_frozen_budget(self):
        bounded.prepare(self.budget_root, self.value())
        with bounded.Budget(self.budget_root) as book:
            book.value['invocations'][0]['environment']['INJECTED'] = 'changed'
            with self.assertRaisesRegex(ValueError, 'in-memory invocation budget changed'):
                book.execute('fresh-auth')
        self.assertFalse(self.witness.exists())

    def test_order_and_repetition_and_concurrent_open_refuse(self):
        bounded.prepare(self.budget_root, self.value())
        with bounded.Budget(self.budget_root) as book:
            with self.assertRaisesRegex(ValueError, 'frozen order'):
                book.execute('case')
            with self.assertRaises(BlockingIOError):
                with bounded.Budget(self.budget_root):
                    self.fail('concurrent batch opened')
            self.assertIsNone(book.execute('fresh-auth')['stop'])
            with self.assertRaisesRegex(ValueError, 'repeated'):
                book.execute('fresh-auth')
            self.assertIsNone(book.execute('case')['stop'])
        with self.assertRaises(FileExistsError):
            with bounded.Budget(self.budget_root):
                self.fail('completed batch reused')

    def test_missing_and_special_bound_files_refuse(self):
        value = self.value()
        self.fake.unlink()
        with self.assertRaises(FileNotFoundError):
            bounded.prepare(self.budget_root, value)
        os.mkfifo(self.fake)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            bounded.prepare(self.budget_root, value)
        self.fake.unlink()
        self.fake.symlink_to(Path(PYTHON))
        with self.assertRaises(OSError):
            bounded.prepare(self.budget_root, value)
        self.assertFalse(self.budget_root.exists())

    def test_invalid_budget_requires_each_model_auth_and_bound_executable(self):
        for mutation in ('missing-auth', 'duplicate-id', 'unbound-executable', 'invalid-timeout', 'extra-key'):
            value = self.value()
            if mutation == 'missing-auth': value['invocations'].pop(0)
            elif mutation == 'duplicate-id': value['invocations'][1]['id'] = 'fresh-auth'
            elif mutation == 'unbound-executable': value['bindings'].pop(0)
            elif mutation == 'invalid-timeout': value['invocations'][1]['timeout_seconds'] = True
            else: value['permission'] = 'invented'
            with self.assertRaises(ValueError, msg=mutation):
                bounded.prepare(self.budget_root, value)
        self.assertFalse(self.witness.exists())

    def test_owner_loss_stops_guard_and_worker(self):
        # A separate owner is deliberately killed; its guard must act without it.
        value = self.value(model='stall', timeout=8)
        case = self.root / 'owner-loss'
        case.mkdir()
        slot_path = self.root / 'slot.json'
        slot_path.write_text(json.dumps(value['invocations'][1]))
        owner_code = '''import importlib.util,json,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('b',sys.argv[1]); b=importlib.util.module_from_spec(s); s.loader.exec_module(b)
b.supervise(json.loads(Path(sys.argv[2]).read_bytes()),Path(sys.argv[3]),b.now()+8)
'''
        with (self.root / 'owner.stdout').open('xb') as stdout, (self.root / 'owner.stderr').open('xb') as stderr:
            owner = subprocess.Popen([PYTHON, '-I', '-B', '-c', owner_code, str(Path(bounded.__file__).resolve()),
                                      str(slot_path), str(case)], stdout=stdout, stderr=stderr)
        group = None
        observation = None
        cleanup = {'group_signal': 'not needed'}
        try:
            until = time.monotonic() + 5
            while time.monotonic() < until:
                output = case / 'stdout.bin'
                if output.exists() and b'ready' in output.read_bytes(): break
                time.sleep(0.02)
            else: self.fail('owner-loss firing control never reached running worker')
            group = json.loads((case / 'group.json').read_bytes())['group']
            firing = observe_group(group, 0)
            bounded.record(self.root / 'group-before-owner-loss.json', firing)
            self.assertEqual(firing['state'], 'present', firing)
            owner.kill()
            owner.wait(timeout=2)
            observation = observe_group(group, 3)
            bounded.record(self.root / 'group-after-owner-loss.json', observation)
            self.assertEqual(observation['state'], 'absent',
                             'guard group absence not observed after owner EOF: ' + repr(observation))
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=2)
            # Only this fresh control's group, and never after observed absence.
            # A cleanup denial is retained without masking the primary failure.
            if group and (observation is None or observation['state'] != 'absent'):
                try:
                    os.killpg(group, signal.SIGKILL)
                    cleanup['group_signal'] = 'SIGKILL sent'
                except ProcessLookupError:
                    cleanup['group_signal'] = 'already absent; no signal sent'
                except PermissionError:
                    cleanup['group_signal'] = 'denied; stopping remains unknown'
                cleanup['observation'] = observe_group(group, 1)
            bounded.record(self.root / 'owner-loss-cleanup.json', cleanup)

    def test_group_observation_distinguishes_denial_from_absence(self):
        outcomes = iter(('present', 'denied', 'denied', 'absent'))
        def transition(group, sig):
            self.assertEqual(sig, 0)
            state = next(outcomes)
            if state == 'denied':
                raise PermissionError(1, 'controlled observation denial')
            if state == 'absent':
                raise ProcessLookupError(3, 'controlled absence')
        result = observe_group(123, 1, transition)
        bounded.record(self.root / 'transition.json', result)
        self.assertEqual(result['state'], 'absent')
        self.assertEqual([item['state'] for item in result['observations']],
                         ['present', 'unknown', 'unknown', 'absent'])
        def denied(group, sig):
            raise PermissionError(1, 'persistent controlled denial')
        result = observe_group(123, 0.04, denied)
        bounded.record(self.root / 'persistent-denial.json', result)
        self.assertEqual(result['state'], 'unknown')
        self.assertTrue(all(item['state'] == 'unknown' for item in result['observations']))
        result = observe_group(123, 0, lambda group, sig: None)
        bounded.record(self.root / 'present.json', result)
        self.assertEqual(result['state'], 'present')
        def absent(group, sig):
            raise ProcessLookupError(3, 'controlled absence')
        for identity in (123, 456):
            result = observe_group(identity, 0, absent)
            bounded.record(self.root / ('absent-%d.json' % identity), result)
            self.assertEqual(result['state'], 'absent')


if __name__ == '__main__':
    print('Retained offline controls: ' + str(RUN), flush=True)
    unittest.main(verbosity=2)
