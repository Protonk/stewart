"""Offline controller controls; real-mode documents here are labelled parser fixtures."""

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('controller_test_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = load('surface_check')
profile_tests = load('test_profile')
RUN = Path(tempfile.mkdtemp(prefix='stewart-controller-controls-')).resolve()


class ControllerControls(unittest.TestCase):
    def setUp(self):
        self.root = RUN / self._testMethodName
        self.root.mkdir()
        self.writer = self.root / 'writer-canary'
        self.marker = self.root / 'writer-started'
        self.writer.write_text('#!/bin/sh\n# Stewart development build: claude-code __stewart-cc-relay __stewart-cc-hook\n'
                               'printf unexpected > ' + c.shlex.quote(str(self.marker)) + '\nexit 97\n')
        self.writer.chmod(0o700)
        self.packet = self.root / 'packet'

    def synthetic(self, family='open-inquiry', scenario='normal'):
        return c.prepare_packet(self.packet, self.writer, 'synthetic-control-model', family, scenario=scenario)

    def real_fixture(self):
        fixture = profile_tests.ProfileControls('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        commission = c.prepare_packet(self.packet, self.writer, 'synthetic-control-model', installation=fixture.install)
        self.assertFalse(fixture.marker.exists())
        return commission, fixture

    def rewrite_budget(self, change):
        path = self.packet / 'invocations/BUDGET.json'
        value = c.p.decode(path.read_bytes())
        change(value)
        path.write_bytes(c.p.compact(value) + b'\n')
        path = self.packet / 'COMMISSION.json'
        commission = c.p.decode(path.read_bytes())
        commission['budget_sha256'] = c.digest_file(self.packet / 'invocations/BUDGET.json')
        path.write_bytes(c.p.compact(commission) + b'\n')

    def test_preparation_freezes_three_pairs_and_all_family_inputs_without_launch(self):
        for family in c.surface.FAMILIES:
            self.packet = self.root / family
            commission = self.synthetic(family)
            verified, _ = c.verify_packet(self.packet)
            self.assertEqual(verified, commission)
            budget = c.p.decode((self.packet / 'invocations/BUDGET.json').read_bytes())
            self.assertEqual([slot['id'] for slot in budget['invocations']],
                             [kind + '-' + role for kind in c.KINDS for role in ('auth', 'model')])
            self.assertEqual(len({case['workspace'] for case in commission['cases']}), 3)
            self.assertFalse((self.packet / 'invocations/START.json').exists())
            self.assertFalse((self.packet / 'observation').exists())
            self.assertFalse(self.marker.exists())
        with self.assertRaises(FileExistsError):
            self.synthetic()

    def test_changed_executable_source_or_supplied_file_refuses(self):
        commission = self.synthetic()
        paths = [self.writer, self.packet / 'synthetic-harness', self.packet / c.CONTROLLER,
                 Path(commission['cases'][0]['workspace']) / 'settings.json',
                 self.packet / 'prepared/positive/inputs/input.jsonl']
        for path in paths:
            raw = path.read_bytes()
            path.write_bytes(raw + b'\nchanged')
            with self.assertRaisesRegex(ValueError, 'bound file changed'):
                c.verify_packet(self.packet)
            path.write_bytes(raw)
        c.verify_packet(self.packet)
        self.assertFalse(self.marker.exists())

    def test_missing_binding_is_not_excused_by_rehashed_budget(self):
        self.synthetic()
        self.rewrite_budget(lambda value: value['bindings'].remove(next(
            item for item in value['bindings'] if item['path'].endswith('/surface_check.py'))))
        with self.assertRaisesRegex(ValueError, 'inventory'):
            c.verify_packet(self.packet)

    def test_changed_surface_timeout_or_allowance_refuses(self):
        for name in ('argv', 'input', 'timeout', 'allowance'):
            self.packet = self.root / name
            self.synthetic()
            if name == 'allowance':
                path = self.packet / 'COMMISSION.json'
                value = c.p.decode(path.read_bytes())
                value['allowance']['model_invocations'] = 1
                path.write_bytes(c.p.compact(value))
            else:
                def change(value):
                    slot = value['invocations'][1]
                    if name == 'argv': slot['argv'].append('--unexpected')
                    elif name == 'input': slot['stdin_base64'] = 'Y2hhbmdlZA=='
                    else: slot['timeout_seconds'] += 1
                self.rewrite_budget(change)
            with self.assertRaisesRegex(ValueError, 'invocation|allowance'):
                c.verify_packet(self.packet)

    def test_unlisted_and_special_immutable_files_refuse(self):
        self.synthetic()
        extra = self.packet / 'unexpected'
        extra.write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            c.verify_packet(self.packet)
        extra.unlink()
        extra.symlink_to(self.writer)
        with self.assertRaisesRegex(ValueError, 'link or special'):
            c.verify_packet(self.packet)

    def test_live_authority_gate_precedes_budget_and_process_start(self):
        commission, fixture = self.real_fixture()
        raw = (self.packet / 'COMMISSION.json').read_bytes()
        digest = c.p.sha(raw)
        with patch.object(c, '__file__', str(self.packet / c.CONTROLLER)):
            for approved, disabled in ((None, False), (digest, False), ('0' * 64, True)):
                with patch.object(c.bounded, 'Budget') as budget:
                    with self.assertRaisesRegex(ValueError, 'principal-approved'):
                        c.run_packet(self.packet, approved, disabled)
                    budget.assert_not_called()
            # Firing control: the exact approval/condition reaches the budget,
            # replaced here before it can create state or invoke any process.
            with patch.object(c.bounded, 'Budget', side_effect=RuntimeError('authorized control reached budget')) as budget:
                with self.assertRaisesRegex(RuntimeError, 'authorized control'):
                    c.run_packet(self.packet, digest, True)
                budget.assert_called_once_with(self.packet / 'invocations', commission['budget_sha256'], True)
        self.assertFalse(fixture.marker.exists())
        self.assertFalse((self.packet / 'invocations/START.json').exists())

    def test_rehearsal_cannot_select_real_installation_or_receive_live_review(self):
        self.real_fixture()
        with patch.object(c, '__file__', str(self.packet / c.CONTROLLER)):
            with self.assertRaisesRegex(ValueError, 'synthetic packet'):
                c.run_packet(self.packet, rehearsal=True)
        self.packet = self.root / 'synthetic'
        self.synthetic()
        with patch.object(c, '__file__', str(self.packet / c.CONTROLLER)):
            with self.assertRaisesRegex(ValueError, 'principal-approved'):
                c.run_packet(self.packet, c.digest_file(self.packet / 'COMMISSION.json'), True)
        with self.assertRaisesRegex(ValueError, 'rehearsals cannot'):
            c.attest(self.packet, '0' * 64, 'synthetic reviewer', self.root / 'CHECK.json')
        self.assertFalse((self.root / 'CHECK.json').exists())

    def test_run_requires_frozen_controller(self):
        self.synthetic()
        with self.assertRaisesRegex(ValueError, 'frozen controller'):
            c.run_packet(self.packet, rehearsal=True)

    def test_duplicate_session_stops_before_third_pair(self):
        commission = self.synthetic()
        calls = []
        controller = self

        class FakeBudget:
            def __init__(self, root, *args):
                self.root, self.index, self.failed = root, 0, False
                self.value = c.p.decode((root / 'BUDGET.json').read_bytes())
            def __enter__(self):
                (self.root / 'uses').mkdir()
                c.save(self.root / 'START.json', {'scope': 'synthetic no-process controller control'})
                return self
            def execute(self, identity, **kwargs):
                slot = self.value['invocations'][self.index]
                self.index += 1
                calls.append(identity)
                out = self.root / 'uses' / identity
                out.mkdir()
                if slot['role'] == 'auth':
                    c.save(out / 'auth-status.json', {'loggedIn': True, 'authMethod': 'claude.ai',
                        'configDirectory': slot['environment']['CLAUDE_CONFIG_DIR']})
                return {'stop': None, 'group_gone': True, 'stream_eof': {'stdout': True, 'stderr': True},
                        'input_bytes_sent': len(c.base64.b64decode(slot['stdin_base64']))}
            def halt(self, reason):
                self.failed = True
                c.save(self.root / 'HALT.json', {'reason': reason, 'scope': 'synthetic no-process control'})
            def __exit__(self, *args):
                c.save(self.root / 'FINISH.json', {'invocations_reserved': self.index,
                    'invocations_unstarted': 6 - self.index, 'failed': self.failed, 'resume_allowed': False})

        class FakeCase:
            def __init__(self, inputs, identity, kind, workspace, evidence):
                self.case_id, self.root, self.workspace = identity, evidence, workspace
                evidence.mkdir()
            def start_listeners(self): pass
            def record_launch(self, value): pass
            def feed(self, raw): pass
            def feed_stderr(self, raw): pass
            def check_stop(self): pass
            def finish_stream(self, channel): pass
            def record_input(self, attempted, prefix): pass
            def close(self): pass
            def finish(self, process, auth):
                value = {'errors': [], 'checks': {name: 'observed' for name in c.surface.REQUIRED_CHECKS},
                    'stopping': 'observed', 'bindings': commission['bindings'],
                    'workspace': str(self.workspace), 'session_id': 'deliberately-reused-synthetic-session'}
                c.save(self.root / 'CASE.json', value)
                return value

        with patch.object(c, '__file__', str(self.packet / c.CONTROLLER)), \
                patch.object(c.bounded, 'Budget', FakeBudget), patch.object(c.observer, 'CaseObserver', FakeCase):
            self.assertEqual(c.run_packet(self.packet, rehearsal=True), 1)
        self.assertEqual(calls, ['positive-auth', 'positive-model', 'closed-gate-auth', 'closed-gate-model'])
        result = c.p.decode((self.packet / 'observation/RESULT.json').read_bytes())
        self.assertEqual(result['outcome'], 'failed')
        self.assertIn('fresh session', result['failures'][0]['error'])
        self.assertTrue(c.p.decode((self.packet / 'invocations/FINISH.json').read_bytes())['failed'])
        self.assertFalse((self.packet / 'observation/OBSERVATION.json').exists())
        self.assertFalse(self.marker.exists())

    def test_synthetic_ack_is_complete_at_publication_and_does_not_overwrite(self):
        marker = self.root / 'peer/startup-observed.json'
        link = c.os.link
        def observed_link(source, destination, **kwargs):
            self.assertFalse(marker.exists())
            self.assertEqual(c.p.decode((marker.parent / source).read_bytes()), {'session_id': 'synthetic-session'})
            return link(source, destination, **kwargs)
        with patch.object(c.os, 'link', side_effect=observed_link):
            c.publish_ack(marker, 'synthetic-session')
        self.assertEqual(c.p.decode(marker.read_bytes()), {'session_id': 'synthetic-session'})
        self.assertFalse((marker.parent / 'startup-observed.pending').exists())
        with self.assertRaises(FileExistsError):
            c.publish_ack(marker, 'different')
        self.assertEqual(c.p.decode(marker.read_bytes()), {'session_id': 'synthetic-session'})

    def review_fixture(self):
        commission, _ = self.real_fixture()
        out = self.packet / 'observation'
        (out / 'inputs').mkdir(parents=True)
        (out / 'execution').mkdir()
        for name in ('launch.json', 'surface.json', 'tools.json'):
            (out / 'inputs' / name).write_bytes((self.packet / 'prepared/positive/inputs' / name).read_bytes())
        (out / 'execution/BUDGET.json').write_bytes((self.packet / 'invocations/BUDGET.json').read_bytes())
        c.save(out / 'execution/START.json', {'mode': 'real-harness', 'budget_sha256': commission['budget_sha256'],
            'approved_digest': commission['budget_sha256'], 'extra_usage_disabled': True})
        c.save(out / 'execution/FINISH.json', {'invocations_reserved': 6, 'invocations_unstarted': 0, 'failed': False, 'resume_allowed': False})
        c.save(out / 'RESULT.json', {'schema': 'stewart.claude-code.surface-run/1', 'mode': 'real-harness', 'outcome': 'observed', 'failures': [],
            'commission_sha256': c.digest_file(self.packet / 'COMMISSION.json'),
            'attempted_cases': list(c.KINDS), 'completed_cases': list(c.KINDS)})
        (out / 'parser-fixture.txt').write_text('Synthetic review parser fixture; no real harness or authentication was invoked.\n')
        c.save(out / 'EVIDENCE.json', c.surface.manifest(out))
        observation = {'schema': 'stewart.claude-code.surface-observation/1', 'mode': 'real-harness',
            'scope': 'supplied-surface', 'started_at': '2026-11-12T00:00:00Z', 'finished_at': '2026-11-12T00:01:00Z',
            **commission['bindings'], 'evidence_manifest_sha256': c.digest_file(out / 'EVIDENCE.json'),
            'checks': [{'id': name, 'outcome': 'observed', 'evidence': ['parser-fixture.txt']} for name in c.surface.REQUIRED_CHECKS],
            'stopping': 'observed'}
        c.save(out / 'OBSERVATION.json', observation)
        return out, observation

    def test_review_requires_explicit_exact_observation_and_preserves_digest(self):
        out, _ = self.review_fixture()
        digest = c.digest_file(out / 'OBSERVATION.json')
        with self.assertRaisesRegex(ValueError, 'digest differs'):
            c.attest(self.packet, '0' * 64, 'synthetic parser reviewer', out / 'CHECK.json')
        self.assertFalse((out / 'CHECK.json').exists())
        c.attest(self.packet, digest, 'synthetic parser reviewer; no real check occurred', out / 'CHECK.json')
        review = c.p.decode((out / 'CHECK.json').read_bytes())
        self.assertEqual(review['observation_sha256'], digest)
        self.assertEqual(review['outcome'], 'observed')
        c.p.evidence(out, (out / 'EVIDENCE.json').read_bytes())
        with self.assertRaises(FileExistsError):
            c.attest(self.packet, digest, 'synthetic parser reviewer', out / 'CHECK.json')

    def test_review_refuses_failed_or_unexercised_observation(self):
        for state in ('failed', 'unexercised'):
            self.packet = self.root / state
            out, value = self.review_fixture()
            value['checks'][0]['outcome'] = state
            (out / 'OBSERVATION.json').write_bytes(c.p.compact(value))
            with self.assertRaisesRegex(ValueError, 'complete, stopped and observed'):
                c.attest(self.packet, c.digest_file(out / 'OBSERVATION.json'), 'synthetic parser reviewer', out / 'CHECK.json')
            self.assertFalse((out / 'CHECK.json').exists())

    def test_review_refuses_missing_witness_and_input_directory_output(self):
        out, _ = self.review_fixture()
        digest = c.digest_file(out / 'OBSERVATION.json')
        with self.assertRaisesRegex(ValueError, 'outside the frozen packet'):
            c.attest(self.packet, digest, 'synthetic parser reviewer', self.packet / 'invalid-review.json')
        (out / 'parser-fixture.txt').unlink()
        with self.assertRaises((ValueError, OSError)):
            c.attest(self.packet, digest, 'synthetic parser reviewer', out / 'CHECK.json')


if __name__ == '__main__':
    print('Retained offline controller controls: ' + str(RUN), flush=True)
    unittest.main(verbosity=2)
