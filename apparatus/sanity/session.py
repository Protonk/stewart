"""Run one retained sanity session inside Linux; all raw records stay private.

The host sends the credential only after READY.json confirms local intake.
Rehearsal mode uses a loopback fake. Live mode requires a reviewed host packet.
"""
import argparse
import errno
import fcntl
import json
import os
from pathlib import Path
import resource
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exercise import Fake, verify_package
from session_support import credential_bytes, digest, scan_tree, strict_json, write_json

SCENARIOS = ['submitted', 'unsubmitted', 'provider-rejected', 'interrupted',
             'reflected-body', 'export-contamination', 'export-failure']


def safe_choice(value, allowed):
    return value if value is None or isinstance(value, str) and value in allowed else 'unknown'


def safe_usage(value):
    if not isinstance(value, dict):
        return None
    result = {}
    for category in ['turns', 'input_tokens', 'output_tokens']:
        counts = value.get(category)
        if not isinstance(counts, dict):
            return None
        result[category] = {k: counts[k] if type(counts.get(k)) is int and counts[k] >= 0 else None for k in ['reported', 'estimated']}
    return result


def failure_details(error, phase, scenario=None):
    """Report controlled context and exception category, never exception text."""
    category = type(error).__name__
    if category not in ['PermissionError', 'FileNotFoundError', 'FileExistsError',
                        'TimeoutExpired', 'RuntimeError', 'ValueError', 'KeyError',
                        'TypeError', 'AttributeError', 'OSError', 'JSONDecodeError',
                        'UnicodeDecodeError', 'BrokenPipeError', 'ProcessLookupError']:
        category = 'OtherError'
    result = {'phase': phase, 'error_type': category, 'scenario': scenario,
              'private_originals_retained': True}
    number = getattr(error, 'errno', None)
    if type(number) is int:
        result['errno'] = number
    return result


def safe_observation(value):
    """Expose only numeric identity/access facts from the independent observer."""
    result = {'access': {}}
    for key in ['observer_uid', 'observer_pid', 'target_pid', 'status_errno', 'limits_errno']:
        if type(value.get(key)) is int:
            result[key] = value[key]
    if isinstance(value.get('target_uids'), list) and all(type(item) is int for item in value['target_uids']):
        result['target_uids'] = value['target_uids']
    if isinstance(value.get('core_limits'), list):
        result['core_limits'] = [item if isinstance(item, str) and re.fullmatch(r'[0-9]{1,20}|unlimited', item) else 'unknown' for item in value['core_limits']]
    for name in ['cmdline', 'environ', 'maps', 'mem', 'fd']:
        access = value.get('access', {}).get(name, {})
        result['access'][name] = {key: access[key] for key in ['allowed', 'errno', 'read_bytes'] if key in access and (type(access[key]) in [bool, int] or access[key] is None)}
    return result


class RequestSeen:
    """The sanity interruption: its fake reports the request that is in flight.

    Twenty seconds without that report is a failed rehearsal, never a point.
    """
    def __init__(self, event):
        self.event = event

    def await_point(self, proc, limit):
        if not self.event.wait(20):
            raise RuntimeError('interruption witness did not observe the request')
        return True

    def sent(self, proc):
        pass

    def missed(self, proc):
        raise

    def remaining(self, limit):
        return limit

    def ended(self, proc, rc, timed_out):
        pass


def process_identity(pid):
    """What an outside observer can read about a process; None where unavailable.

    `start_ticks` is field 22 of /proc/<pid>/stat, the value INTERFACE 4.4 says a
    placement records about itself, so the two can be compared.
    """
    result = {'pid': pid, 'start_ticks': None, 'uid': None, 'boot_id': None}
    try:
        stat = Path(f'/proc/{pid}/stat').read_bytes()
        result['start_ticks'] = int(stat[stat.rindex(b')') + 2:].split()[19])
        for line in Path(f'/proc/{pid}/status').read_bytes().splitlines():
            if line.startswith(b'Uid:'):
                result['uid'] = int(line.split()[1])
        result['boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except (OSError, ValueError, IndexError):
        pass
    return result


def signal_timing(captured, attempts):
    """Where a stop found one request, in the terms INTERFACE 6.4 charges and reports it."""
    if not captured:
        return 'not_captured'
    if any(row['outcome'] == 'response' for row in attempts):
        return 'answered'
    if any(row['request_written'] != 'none' for row in attempts):
        return 'written_unanswered'
    return 'captured_not_written'


LOG_POINTS = {'reminder_notice': lambda record: record.get('kind') == 'notice'
                  and record['body'].get('type') == 'reminder',
              'entry_record': lambda record: record.get('kind') == 'entry'}


class LogPoint:
    """Signal one placement after it publishes a named record in its audit log.

    The log is read from outside the service process. Only a record numbered
    after those present before the placement started can be the point, so an
    earlier placement's record never selects it; neither does elapsed time. The
    pause between looks only spaces the observations. When the placement ends
    first, or its watchdog expires, nothing is signalled and the interruption is
    recorded as unexercised. Each witness file is written once, exclusively, in
    a folder outside Stewart's archive.

    `in_flight` is a rehearsal aid: the fake provider's report that it holds the
    request following the point. Waiting for it makes the estimated charge of
    INTERFACE 6.4 deterministic. Without it, as in a live placement, the signal
    goes as soon as the record is seen, whatever the next request has reached:
    not yet captured, captured, on the wire or already answered. Which of those
    it was is read from the placement's own run directory, once when the record
    is seen and again after the process has stopped, and kept with the witness.
    """
    def __init__(self, log, point, folder, *, in_flight=None):
        if point not in LOG_POINTS:
            raise ValueError('unknown interruption point')
        self.log, self.point, self.folder, self.in_flight = Path(log), point, Path(folder), in_flight
        self.before = self.numbers()
        self.next = max(self.before, default=0) + 1
        self.started = self.waited = None
        self.state = 'unexercised'
        self.folder.mkdir(mode=0o700)
        write_json(self.folder / 'selected.json', {'point': point, 'signal': 'SIGTERM',
            'log_records_before_placement': len(self.before), 'at': time.time(),
            'observer': {'pid': os.getpid(), 'uid': os.getuid()}})

    def numbers(self):
        return sorted(int(path.stem) for path in self.log.iterdir()
                      if re.fullmatch(r'[1-9][0-9]*\.json', path.name))

    def look(self):
        """The first new record that is the point, or None. Records are linked whole."""
        while True:
            path = self.log / f'{self.next}.json'
            try:
                raw = path.read_bytes()
            except FileNotFoundError:
                return None
            record = strict_json(raw)
            if LOG_POINTS[self.point](record):
                body = record['body']
                # The placement, and for a notice the request planned to carry it (INTERFACE 4.4).
                self.run = body['run'] if record['kind'] == 'notice' else body['invocation']['run']
                self.carrying = body['request'] if record['kind'] == 'notice' else None
                return {'record': f'log/{self.next}.json', 'sha256': digest(raw), 'kind': record['kind']}
            self.next += 1

    def captures(self):
        """Request captures and attempt records of the placement, by number."""
        run = self.log.parent / 'runs' / str(self.run)
        requests, attempts = [], {}
        for path in run.iterdir() if run.is_dir() else []:
            request = re.fullmatch(r'request-([1-9][0-9]*)\.json', path.name)
            attempt = re.fullmatch(r'attempt-([1-9][0-9]*)-([1-9][0-9]*)\.json', path.name)
            if request:
                requests.append(int(request[1]))
            if attempt:
                attempts.setdefault(int(attempt[1]), []).append(int(attempt[2]))
        return run, sorted(requests), attempts

    def timing(self):
        """What the signal found, from the stopped placement's captures and attempt records."""
        run, requests, attempts = self.captures()
        request = self.carrying if self.carrying is not None else max(requests, default=None)
        rows = []
        for number in sorted(attempts.get(request, [])):
            body = strict_json((run / f'attempt-{request}-{number}.json').read_bytes())['body']
            rows.append({'attempt': number, 'outcome': body['outcome'], 'request_written': body['request_written'],
                         'charge_basis': body['charged']['basis']})
        return {'placement': self.run, 'request': request, 'named_by_the_notice': self.carrying is not None,
                'request_captured': request in requests, 'attempts': rows, 'requests_captured': len(requests),
                'timing': signal_timing(request in requests, rows),
                'source': "the placement's own captures and attempt records, read after it stopped"}

    def await_point(self, proc, limit):
        self.started = time.monotonic()
        while True:
            found = self.look()
            if found is not None:
                break
            ended = proc.poll() is not None
            if ended or time.monotonic() - self.started >= limit:
                # The process may have published the record as it ended; nothing
                # can be signalled then, and the result must not claim otherwise.
                self.waited = time.monotonic() - self.started
                write_json(self.folder / 'unexercised.json', {
                    'reason': 'placement_ended_first' if ended else 'watchdog_expired_first',
                    'new_log_records_seen': self.next - 1 - max(self.before, default=0),
                    'signal_sent': False, 'at': time.time()})
                return False
            time.sleep(0.01)
        held = None
        if self.in_flight is not None:
            held = self.in_flight.wait(20)
            if not held:
                raise RuntimeError('rehearsal provider did not report the request in flight after the point')
        self.waited = time.monotonic() - self.started
        _, requests, attempts = self.captures()
        write_json(self.folder / 'point.json', {'point': self.point, **found, 'observed_at': time.time(),
            'process': process_identity(proc.pid), 'process_running': proc.poll() is None,
            'rehearsal_request_in_flight': held,
            # Seen from outside just before the signal; the placement keeps running meanwhile.
            'run_directory_when_seen': {'request_captures': len(requests),
                'attempt_records': sum(len(numbers) for numbers in attempts.values()),
                'carrying_request_captured': None if self.carrying is None else self.carrying in requests}})
        return True

    def sent(self, proc):
        write_json(self.folder / 'signal.json', {'signal': 'SIGTERM', 'number': int(signal.SIGTERM),
            'process_group': proc.pid, 'sent_at': time.time()})
        self.state = 'signalled'

    def missed(self, proc):
        # The record was seen, but the process had gone before a signal could reach it.
        write_json(self.folder / 'unexercised.json', {'reason': 'placement_ended_at_the_point',
            'new_log_records_seen': self.next - max(self.before, default=0),
            'signal_sent': False, 'at': time.time()})

    def remaining(self, limit):
        # One watchdog covers reaching the point and stopping after it; a
        # signalled service still gets ten seconds to record its ending.
        left = max(0, limit - self.waited)
        return max(left, 10) if self.state == 'signalled' else left

    def ended(self, proc, rc, timed_out):
        if self.state != 'signalled':
            return
        try:
            os.killpg(proc.pid, 0)
            group_gone = False
        except ProcessLookupError:
            group_gone = True
        except PermissionError:
            group_gone = None
        write_json(self.folder / 'termination.json', {'exit': rc, 'timed_out': timed_out,
            'process_group_gone': group_gone, 'observed_at': time.time()})
        if rc is not None:
            write_json(self.folder / 'timing.json', self.timing())

    def summary(self):
        """Controlled facts only; the witness files hold the full observation."""
        result = {'after': self.point, 'state': self.state, 'witness': self.folder.name}
        for name in ['point', 'signal', 'termination', 'timing', 'unexercised']:
            path = self.folder / (name + '.json')
            result[name] = strict_json(path.read_bytes()) if path.exists() else None
        return result


class Session:
    def spawn(self, argv, **options):
        """Run the production Linux path as the unprivileged audit owner."""
        return subprocess.Popen(argv, user=1000, group=1000, extra_groups=[],
                                umask=0o077, **options)

    def __init__(self, binary, root, commission, template, mode, witness=None):
        self.binary, self.root, self.commission, self.mode = binary, root, commission, mode
        self.phase = 'session-setup'
        self.observer_state = None
        self.witness = witness
        root.mkdir(mode=0o700)
        os.chown(root, 1000, 1000)
        self.folder, self.archive, self.destination, self.evidence = [root / n for n in ['submission', 'archive', 'returns', 'evidence']]
        shutil.copytree(template, self.folder)
        self.destination.mkdir(mode=0o700)
        self.evidence.mkdir(mode=0o700)
        (root / 'home').mkdir(mode=0o700)
        text = (self.folder / 'question.md').read_text()
        body = text.split('---\n', 2)[2]
        settings = ['---', 'stewart: question/1', 'family: open-inquiry',
                    'model: ' + commission['model'], 'destination: ' + str(self.destination)]
        if commission['effort'] is not None:
            settings.append('effort: ' + commission['effort'])
        for key in ['turns', 'input_tokens', 'output_tokens']:
            settings.append('limit-' + key.replace('_', '-') + ': ' + str(commission['limits'][key]))
        (self.folder / 'question.md').write_text('\n'.join(settings) + '\n---\n' + body)
        for p in [root, *root.rglob('*')]:
            os.chown(p, 1000, 1000)
        self.question = body
        self.materials = {'materials/' + p.name: p.read_bytes() for p in sorted((self.folder / 'materials').iterdir(), reverse=True)}
        shutil.copytree(self.folder, self.evidence / 'input-witness')
        self.env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(root / 'home'), 'LANG': 'C.UTF-8'}
        self.index = 0
        self.ref = None
        self.process = None

    def command(self, label, *args, raw=False, key=None, endpoint=None, interrupt=None, observe=None):
        self.phase = 'command.' + safe_choice(args[0], ['new', 'prepare', 'commission', 'receipt', 'status', 'run', 'close'])
        self.index += 1
        stem = self.evidence / f'{self.index:02}-{label}'
        argv = [str(self.binary), *args] + ([] if raw else ['--json'])
        env = dict(self.env)
        if endpoint is not None:
            env['STEWART_PROVIDER_URL'] = endpoint
        read_fd = write_fd = None
        if key is not None:
            read_fd, write_fd = os.pipe()
            argv += ['--key-fd', str(read_fd)]
        started = time.time()
        timed_out = False
        proc, primary_error, cleanup_error = None, None, None
        with stem.with_suffix('.stdout').open('xb') as stdout, stem.with_suffix('.stderr').open('xb') as stderr:
            try:
                proc = self.spawn(argv, cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                    stdout=stdout, stderr=stderr, pass_fds=(() if read_fd is None else (read_fd,)),
                    start_new_session=True)
                self.process = proc
                if read_fd is not None:
                    os.close(read_fd)
                    read_fd = None
                    view = memoryview(key)
                    while view:
                        view = view[os.write(write_fd, view):]
                    os.close(write_fd)
                    write_fd = None
                if observe is not None:
                    self.phase = 'process-observation'
                    event, release = observe
                    if not event.wait(20):
                        raise RuntimeError('process observation witness did not observe the request')
                    self.observe_process(proc.pid)
                    release.set()
                limit = self.commission['stop_after_seconds'] if key is not None else 40
                if interrupt is not None:
                    self.phase = 'interruption-witness'
                    if interrupt.await_point(proc, limit):
                        try:
                            os.killpg(proc.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            interrupt.missed(proc)
                        else:
                            interrupt.sent(proc)
                    limit = interrupt.remaining(limit)
                try:
                    rc = proc.wait(timeout=limit)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        rc = proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        rc = proc.wait(timeout=10)
            except BaseException as error:
                primary_error = error
            finally:
                try:
                    for fd in [read_fd, write_fd]:
                        if fd is not None:
                            os.close(fd)
                    if proc is not None and proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGTERM)
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(proc.pid, signal.SIGKILL)
                            proc.wait(timeout=10)
                except BaseException as error:
                    cleanup_error = error
                rc = proc.poll() if proc is not None else None
                if interrupt is not None and proc is not None and cleanup_error is None:
                    try:
                        interrupt.ended(proc, rc, timed_out)
                    except BaseException as error:
                        primary_error = primary_error or error
                metadata = {'argv': argv, 'exit': rc, 'pid': proc.pid if proc is not None else None,
                    'process_state': 'not_started' if proc is None else 'exited' if rc is not None else 'unknown',
                    'timed_out': timed_out, 'started_at': started, 'ended_at': time.time(),
                    'environment_names': sorted(env), 'credential_channel': 'owned pipe fd' if key is not None else None}
                if primary_error is not None:
                    metadata['failure'] = failure_details(primary_error, self.phase, self.mode)
                if cleanup_error is not None:
                    metadata['cleanup_failure'] = failure_details(cleanup_error, 'process-cleanup', self.mode)
                # An observer/callback failure must not erase the attempted
                # command's identity, observed exit, timing or retained streams.
                write_json(stem.with_suffix('.json'), metadata)
        if primary_error is not None:
            raise primary_error
        if cleanup_error is not None:
            raise cleanup_error
        content = stem.with_suffix('.stdout').read_bytes()
        if raw:
            if rc != 0:
                raise RuntimeError(label + ' failed; raw records retained privately')
            return content
        try:
            reply = json.loads(content)
            if reply.get("schema") != "stewart.reply/2":
                raise ValueError("unsupported Stewart reply schema")
        except (UnicodeError, json.JSONDecodeError):
            raise RuntimeError(label + ' did not return JSON; raw records retained privately') from None
        if key is None and (rc != 0 or reply.get('outcome') != 'completed'):
            raise RuntimeError(label + ' failed; raw records retained privately')
        return reply, rc, timed_out

    def observe_process(self, pid):
        helper = Path(__file__).parents[1] / 'driver' / 'credential_observer.py'
        observations = []
        initializations = []
        for uid in [1000, 1001]:
            self.observer_state = {'code': 'control_ready', 'uid': uid, 'role': 'readable-control'}
            # Request sibling inspection where Yama supports it. Some kernels
            # reject this optional prctl yet permit all the actual reads below;
            # retain that result and require the reads themselves to fire.
            control_code = '''import ctypes,json,os,time
c=ctypes.CDLL(None,use_errno=True)
ctypes.set_errno(0)
rc=c.prctl(0x59616d61,ctypes.c_ulong(-1),0,0,0)
err=ctypes.get_errno()
print(json.dumps({'uid':os.getuid(),'euid':os.geteuid(),'gid':os.getgid(),
    'pr_set_ptracer_return':rc,'errno':err,'dumpable':c.prctl(3,0,0,0,0)}),flush=True)
time.sleep(60)
'''
            control = subprocess.Popen(['python3', '-I', '-B', '-c', control_code],
                env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'STEWART_OBSERVER_CONTROL': 'readable-control'},
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                user=uid, group=uid, extra_groups=[], start_new_session=True)
            try:
                initialized = strict_json(control.stdout.readline())
                fields = ['uid', 'euid', 'gid', 'pr_set_ptracer_return', 'errno', 'dumpable']
                if not isinstance(initialized, dict) or set(initialized) != set(fields) or not all(type(initialized[name]) is int for name in fields):
                    raise RuntimeError('readable process control did not initialize')
                initialization = {'pid': control.pid, 'at': time.time(), **initialized}
                self.observer_state['initialization'] = initialization
                write_json(self.evidence / f'observer-{uid}-control-init.json', initialization)
                initializations.append(initialization)
                if any(initialized[name] != uid for name in ['uid', 'euid', 'gid']):
                    raise RuntimeError('readable process control identity differs')
                for role, target in [('readable-control', control.pid), ('hardened', pid)]:
                    self.observer_state = {'code': 'observer_exit', 'uid': uid, 'role': role,
                                           'initialization': initialization}
                    result = subprocess.run(['python3', '-I', '-B', str(helper), str(target)],
                        env={'PATH': '/usr/local/bin:/usr/bin:/bin'}, cwd='/work',
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        user=uid, group=uid, extra_groups=[], timeout=10)
                    self.observer_state['exit'] = result.returncode
                    if result.returncode:
                        raise RuntimeError('process observer failed')
                    observation = json.loads(result.stdout)
                    self.observer_state['observation'] = safe_observation(observation)
                    write_json(self.evidence / f'observer-{uid}-{role}.json', observation)
                    observations.append({'uid': uid, 'role': role, 'observation': observation})
                    access = observation.get('access', {})
                    if role == 'readable-control':
                        self.observer_state['code'] = 'control_firing'
                        if not all(access.get(name, {}).get('allowed') is True for name in ['cmdline', 'environ', 'maps', 'mem', 'fd']) or access['mem'].get('read_bytes') != 1:
                            raise RuntimeError('readable process control did not fire')
                    else:
                        self.observer_state['code'] = 'protection'
                        if not all(access.get(name, {}).get('allowed') is False and access[name].get('errno') in [errno.EACCES, errno.EPERM] for name in ['environ', 'maps', 'mem', 'fd']):
                            raise RuntimeError('hardened process inspection was not denied')
                        self.observer_state['code'] = 'identity'
                        if observation.get('core_limits') != ['0', '0'] or observation.get('target_uids') != [1000, 1000, 1000, 1000]:
                            raise RuntimeError('hardened process identity or core limits differ')
            finally:
                if control.poll() is None:
                    os.killpg(control.pid, signal.SIGTERM)
                control.wait(timeout=10)
        write_json(self.evidence / 'process-observation-index.json', {'target_pid': pid,
            'observers': [1000, 1001], 'count': len(observations), 'controls_fired': 2,
            'control_initializations': initializations, 'inspection_denied': True, 'at': time.time()})
        self.observer_state = {'code': 'complete', 'observers': [1000, 1001], 'controls_fired': 2,
                               'control_initializations': initializations, 'inspection_denied': True}

    def intake(self):
        new, _, _ = self.command('new', 'new', str(self.folder), '--archive', str(self.archive))
        self.phase = 'new-reply'
        self.ref = new['data']['reference']
        prepared, _, _ = self.command('prepare', 'prepare', self.ref)
        self.phase = 'prepare-reply'
        self.command('commission', 'commission', self.ref, prepared['data']['prepared'], '--i-am-finished')
        receipt, _, _ = self.command('receipt-verify', 'receipt', self.ref, '--verify')
        for item, content in {'question-file': (self.folder / 'question.md').read_bytes(), 'question-body': self.question.encode(), **self.materials}.items():
            if self.command('readback-' + item.replace('/', '-'), 'receipt', self.ref, '--read', item, raw=True) != content:
                raise RuntimeError('receipt readback differs from input witness')
        self.command('status-before', 'status', self.ref)
        write_json(self.root / 'operator.json', {'binary': str(self.binary), 'reference': self.ref, 'home': self.env['HOME']})

    def verify_delivery(self, data):
        manifests = list(self.archive.glob('audits/*/seal/manifest-*.json'))
        if len(manifests) != 1:
            raise RuntimeError('one sealed manifest was expected')
        raw = manifests[0].read_bytes()
        if digest(raw) != data['seal']['manifest_sha256']:
            raise RuntimeError('seal digest differs from retained manifest')
        package = Path(data['delivery']['location'])
        verify_package(package, raw)
        return package, raw

    def run(self, key):
        interrupt = None
        observe = None
        fake = None
        if self.mode == 'live':
            endpoint = self.commission['endpoint']
        else:
            evidence = self.evidence / 'fake-provider'
            evidence.mkdir()
            observed_auth = []
            witness = self.witness / self.mode
            witness.mkdir(mode=0o700)
            def auth_observer(number, received):
                path = witness / f'received-{number}.bin'
                with path.open('xb') as stream:
                    stream.write(received)
                observation = {'request': number, 'bytes': len(received), 'sha256': digest(received),
                    'matches_canary': received == key, 'observed_at': time.time()}
                write_json(witness / f'received-{number}.json', observation)
                observed_auth.append(observation)
            fake = Fake(self.mode if self.mode in ['submitted', 'unsubmitted', 'provider-rejected'] else 'submitted', evidence, self.materials, self.question, auth_observer=auth_observer)
            fake.key = key.decode('ascii')
            if self.mode == 'reflected-body':
                fake.respond = lambda body: fake.message([{'type': 'text', 'text': key.decode('ascii')}], 'end_turn')
            if self.mode == 'interrupted':
                interrupt = threading.Event()
                release = threading.Event()
                original = fake.respond
                def delayed(body):
                    if fake.requests == 4:
                        interrupt.set()
                        release.wait(15)
                    return original(body)
                fake.respond = delayed
            if self.mode == 'submitted':
                observed = threading.Event()
                released = threading.Event()
                original = fake.respond
                def held(body):
                    if fake.requests == 1:
                        observed.set()
                        released.wait(20)
                    return original(body)
                fake.respond = held
                observe = (observed, released)
            endpoint = f'http://127.0.0.1:{fake.server.server_port}'
            fake.__enter__()
        try:
            reply, rc, timed_out = self.command('run', 'run', self.ref, key=key, endpoint=endpoint,
                interrupt=None if interrupt is None else RequestSeen(interrupt), observe=observe)
        finally:
            if interrupt is not None:
                release.set()
            if observe is not None:
                observe[1].set()
            if fake is not None:
                fake.__exit__(None, None, None)
        status, _, _ = self.command('status-after-run', 'status', self.ref)
        data = reply.get('data', {})
        submitted = bool(data.get('seal', {}).get('state') == 'present' and data['seal'].get('actor') == 'auditor')
        verified = False
        closed = False
        if submitted and data.get('delivery', {}).get('outcome') == 'verified':
            package, manifest = self.verify_delivery(data)
            verified = True
            # Only the successful submitted-and-verified path closes automatically.
            close, _, _ = self.command('close', 'close', self.ref)
            closed = close['data'].get('closure') == 'complete'
            if not closed:
                raise RuntimeError('ordinary close did not complete')
            if self.mode == 'submitted':
                control = self.root / 'altered-return-control'
                shutil.copytree(package, control)
                with (control / 'answer.md').open('ab') as stream:
                    stream.write(b'\nDeliberate verifier control.\n')
                try:
                    verify_package(control, manifest)
                except ValueError:
                    pass
                else:
                    raise RuntimeError('altered-return control did not fire')
                verify_package(package, manifest)
                write_json(self.evidence / 'verifier-control.json', {'fired': True, 'original_still_verifies': True})
        if self.mode == 'export-contamination':
            (self.root / 'deliberately-contaminated-export-control').write_bytes(key)
        summary = {'scenario': self.mode, 'exit': rc, 'timed_out': timed_out,
            'ending': safe_choice(data.get('ending'), ['sealed', 'ended_unsubmitted', 'limit_reached', 'stopped_by_close', 'damaged', 'interrupted']),
            'cause': safe_choice(data.get('cause'), ['signal', 'provider_unavailable', 'provider_rejected', 'context_exhausted', 'provider_refusal', 'max_tokens', 'protocol_anomaly', 'archive_write_failed', 'process_gone', 'credential_reflected']),
            'auditor_submitted': submitted, 'delivery_verified': verified, 'closed': closed,
            'usage': safe_usage(data.get('usage')), 'status_condition': safe_choice(status['data'].get('condition'), ['preparing', 'intake_in_progress', 'intake_failed', 'acceptance_uncertain', 'log_damaged', 'not_started', 'run_active', 'interrupted', 'ended_unsubmitted', 'limit_reached', 'damaged', 'sealed_undelivered', 'delivered_open', 'awaiting_confirmation', 'close_unfinished', 'closed_before_launch', 'closed']),
            'automatic_continuation': False, 'fake_requests': fake.requests if fake else None,
            'failure': False}
        if fake is not None and fake.failures:
            summary['failure'] = True
        if fake is not None:
            summary['authentication_observation'] = {'requests_observed': len(observed_auth),
                'exact_matches': sum(item['matches_canary'] for item in observed_auth),
                'independent_witness': str(witness), 'canary_sha256': digest(key)}
            if len(observed_auth) != fake.requests or not observed_auth or not all(item['matches_canary'] for item in observed_auth):
                summary['failure'] = True
        expected = {'unsubmitted': 'ended_unsubmitted', 'provider-rejected': 'interrupted',
            'interrupted': 'interrupted', 'reflected-body': 'interrupted'}.get(self.mode, 'sealed')
        if self.mode != 'live' and (data.get('ending') != expected or timed_out):
            summary['failure'] = True
        if self.mode == 'reflected-body' and (data.get('cause') != 'credential_reflected' or fake.requests != 1):
            summary['failure'] = True
        write_json(self.evidence / 'RESULT.json', summary)
        return summary


def placement_folder(evidence, placement):
    """Where one placement's launcher records live, outside Stewart's archive.

    The first placement keeps its names directly in `evidence/`. Each later one
    has `evidence/placement-NNNN/`, so no earlier record is ever rewritten.
    """
    return evidence if placement == 1 else evidence / f'placement-{placement:04d}'


def numbered_records(evidence, pattern):
    found = []
    for path in evidence.iterdir():
        match = re.fullmatch(pattern, path.name)
        if match is not None:
            found.append((int(match[1]), path))
    return [path for _, path in sorted(found)], [number for number, _ in sorted(found)]


# Attempt outcomes whose response capture may be cut off (INTERFACE 6.6): every
# outcome with a status line except `response`, a complete decodable message.
CUT_OFF_OUTCOMES = ['response_undecodable', 'http_error', 'timeout', 'connection_lost',
                    'aborted_by_close', 'aborted_by_signal']


def run_capture_state(run, ended):
    """Account every capture of one placement against its recorded ending."""
    attempts = list(run.glob('attempt-*.json'))
    requests = list(run.glob('request-*.json'))
    if not attempts or not requests:
        return 'missing_attempt_evidence'
    if ended.get('requests') != len(requests) or ended.get('attempts') != len(attempts) or str(ended.get('run')) != run.name:
        return 'capture_counts_disagree'
    witnessed_responses = set()
    witnessed_requests = set()
    attempt_numbers = {}
    for path in attempts:
        value = strict_json(path.read_bytes())
        if value.get('kind') != 'provider_attempt':
            return 'invalid_attempt_evidence'
        body = value['body']
        if any(type(body.get(field)) is not int or body[field] <= 0 for field in ['request', 'attempt']):
            return 'invalid_attempt_identity'
        match = re.fullmatch(r'attempt-([1-9][0-9]*)-([1-9][0-9]*)\.json', path.name)
        if match is None or (int(match[1]), int(match[2])) != (body.get('request'), body.get('attempt')):
            return 'attempt_identity_disagrees'
        attempt_numbers.setdefault(body['request'], []).append(body['attempt'])
        marker = body['credential_reflection']
        if not isinstance(marker, dict) or set(marker) != {'body', 'headers'} or type(marker['body']) is not bool or not isinstance(marker['headers'], list) or any(h not in ['content-type', 'request-id', 'retry-after'] for h in marker['headers']):
            return 'invalid_reflection_marker'
        if marker['body'] or marker['headers']:
            return 'credential_reflection_recorded'
        witnessed_requests.add('request-' + str(body['request']) + '.json')
        response = body['response']
        if response is not None:
            name = response['file']
            if name != f"response-{body['request']}-{body['attempt']}.bin":
                return 'invalid_response_membership'
            raw = (run / name).read_bytes()
            # INTERFACE 4.5: a response capture is written "once its body ended or
            # was cut off", the attempt record "binds its size and SHA-256", and
            # `complete` "is false when the body was cut off or exceeded 32 MiB".
            # A cut-off body bound exactly by its record is therefore a complete
            # observation of an incomplete response. It is accepted only for an
            # outcome that INTERFACE 6.6 does not define as a complete decodable
            # body, and only with the clean reflection marker required above.
            # Anything used as a response must be whole, and any size or digest
            # difference withholds as before.
            whole = response['complete'] is True or (response['complete'] is False
                and body.get('outcome') in CUT_OFF_OUTCOMES)
            if not whole or type(response.get('bytes')) is not int or response['bytes'] < 0 or len(raw) != response['bytes'] or digest(raw) != response['sha256']:
                return 'incomplete_response_evidence'
            witnessed_responses.add(name)
    if witnessed_responses != {path.name for path in run.glob('response-*.bin')} or witnessed_requests != {path.name for path in requests}:
        return 'unaccounted_capture'
    if witnessed_requests != {f'request-{n}.json' for n in range(1, len(requests) + 1)} or any(sorted(numbers) != list(range(1, len(numbers) + 1)) for numbers in attempt_numbers.values()):
        return 'noncontiguous_attempt_evidence'
    for path in requests:
        raw = path.read_bytes()
        request = strict_json(raw)
        if not raw.endswith(b'\n') or not isinstance(request, dict) or type(request.get('request')) is not int or request['request'] <= 0 or path.name != f"request-{request.get('request')}.json":
            return 'incomplete_request_evidence'
    # A staged provider attempt must have an identical published record.
    published = {path.read_bytes() for path in attempts}
    for path in (run / 'stage').glob('*'):
        if path.is_file():
            raw = path.read_bytes()
            value = strict_json(raw)
            if value.get('kind') == 'provider_attempt' and raw not in published:
                return 'unpublished_attempt_evidence'
    return None


def export_evidence_state(root):
    """Require complete stopped-run observations and independently check markers.

    Every placement needs its own launcher result, run command, status
    observation, log boundary and run directory, in the same order, and every
    capture of every placement is accounted. An audit continued after an
    interruption therefore exports only when each placement would have exported
    alone. A crash between raw capture and marker publication cannot authorize
    export. Raw bodies, orphaned captures and staged records remain private on
    failure.
    """
    try:
        evidence = root / 'evidence'
        commands, command_numbers = numbered_records(evidence, r'([0-9]{2,})-run\.json')
        statuses, status_numbers = numbered_records(evidence, r'([0-9]{2,})-status-after-run\.stdout')
        later = sorted(path.name for path in evidence.iterdir() if path.name.startswith('placement-'))
        placements = max(len(commands), 1)
        for number in range(1, placements + 1):
            result = strict_json((placement_folder(evidence, number) / 'RESULT.json').read_bytes())
            if result.get('failure') is not False:
                return 'procedure_not_complete'
        # A placement folder without its run command is an intended start whose
        # effects were never observed.
        if (not commands or len(commands) != len(statuses)
                or later != [f'placement-{number:04d}' for number in range(2, placements + 1)]):
            return 'missing_run_observation'
        order = sorted([(number, 'run') for number in command_numbers] + [(number, 'status') for number in status_numbers])
        if [kind for _, kind in order] != ['run', 'status'] * placements:
            return 'missing_run_observation'
        observed = []
        first_argv = None
        for number, (command_path, status_path) in enumerate(zip(commands, statuses), 1):
            command = strict_json(command_path.read_bytes())
            status_command = strict_json(status_path.with_suffix('.json').read_bytes())
            run_argv, status_argv = command.get('argv'), status_command.get('argv')
            if not isinstance(run_argv, list) or not isinstance(status_argv, list) or len(run_argv) < 3 or len(status_argv) < 3 or run_argv[1] != 'run' or status_argv[1] != 'status' or run_argv[0] != status_argv[0] or run_argv[2] != status_argv[2]:
                return 'mismatched_run_observation'
            first_argv = first_argv or run_argv
            if run_argv[0] != first_argv[0] or run_argv[2] != first_argv[2]:
                return 'mismatched_run_observation'
            if type(status_command.get('exit')) is not int or status_command['exit'] != 0 or status_command.get('timed_out') is not False:
                return 'uncertain_writer_state'
            status = strict_json(status_path.read_bytes())['data']['runs']
            if type(command.get('exit')) is not int or command['exit'] < 0 or command.get('timed_out') is not False:
                return 'uncertain_process_exit'
            if status.get('held') is not False or type(status.get('count')) is not int or status['count'] != number or not status.get('last', {}).get('ending'):
                return 'uncertain_writer_state'
            observed.append(status)
        audits = list((root / 'archive/audits').iterdir())
        if len(audits) != 1:
            return 'unknown_audit_membership'
        logs = sorted((audits[0] / 'log').glob('*.json'), key=lambda path: (len(path.stem), path.stem))
        logs = [strict_json(path.read_bytes()) for path in logs]
        starts = [record['body'] for record in logs if record.get('kind') == 'run_started']
        ends = [record['body'] for record in logs if record.get('kind') == 'run_ended']
        if len(starts) != placements or len(ends) != placements:
            return 'missing_run_boundary'
        for number, (started, ended, status) in enumerate(zip(starts, ends, observed), 1):
            if any(type(ended.get(field)) is not int or ended[field] <= 0 for field in ['run', 'requests', 'attempts']):
                return 'invalid_run_counts'
            if type(started.get('run')) is not int or started['run'] <= 0 or started['run'] != ended['run'] or started['run'] != number:
                return 'invalid_run_identity'
            last = status['last']
            if type(last.get('number')) is not int or last['number'] <= 0 or last['number'] != ended['run']:
                return 'uncertain_writer_state'
        run_dirs = sorted((path for path in (audits[0] / 'runs').iterdir() if path.is_dir()),
                          key=lambda path: (len(path.name), path.name))
        if len(run_dirs) != placements:
            return 'unknown_run_membership'
        for run, ended in zip(run_dirs, ends):
            state = run_capture_state(run, ended)
            if state is not None:
                return state
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return 'missing_or_malformed_evidence'
    return 'complete'


def export_work(root, out, key, *, force_failure=False):
    # Serialize the apparatus's operator commands and export. The owner can
    # still bypass this lock with ordinary tools; this is not a hostile-owner
    # or atomic filesystem snapshot claim.
    with (root.parent / (root.name + '.operator.lock')).open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return export_locked(root, out, key, force_failure=force_failure)


def export_locked(root, out, key, *, force_failure=False):
    state = export_evidence_state(root)
    scan = scan_tree(root, key)
    report = {'scan': scan, 'evidence_state': state, 'outcome': 'withheld', 'archive': None}
    if state != 'complete' or scan['files_with_matches'] or scan['errors']:
        report['reason'] = 'incomplete observation, reflection marker or credential scan; originals remain private'
        return report
    target = out / 'work.tar'
    try:
        if force_failure:
            # A real exclusive-open failure, with the obstruction retained.
            target.mkdir()
        with target.open('xb') as stream:
            with tarfile.open(fileobj=stream, mode='w') as archive:
                archive.add(root, arcname='private', recursive=True)
        report.update(outcome='exported', archive={'name': 'work.tar', 'bytes': target.stat().st_size,
            'sha256': digest(target.read_bytes())}, finished_at=time.time())
    except OSError:
        report['reason'] = 'export failed; originals and any partial copy retained'
        report['outcome'] = 'failed'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['rehearse', 'live'])
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--private', type=Path, default=Path('/work/private'))
    parser.add_argument('--out', type=Path, default=Path('/out'))
    args = parser.parse_args()
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # Stewart opens each ancestor for reading during path validation. This
    # root-owned parent contains only generic scenario/lock names; payloads
    # remain behind each uid1000-owned mode-0700 scenario directory.
    args.private.mkdir(mode=0o755)
    args.private.chmod(0o755)
    commission = strict_json(args.packet.read_bytes())
    modes = SCENARIOS if args.mode == 'rehearse' else ['live']
    sessions = []
    report = {'schema': 'stewart.sanity-session/1', 'mode': args.mode, 'started_at': time.time(),
              'scenarios': [], 'failures': [], 'model_calls': 0 if args.mode == 'rehearse' else None}
    key = None
    phase, active_mode, active_session = 'credential-witness-setup', None, None
    try:
        witness = Path('/work/credential-witness') if args.mode == 'rehearse' else None
        if witness is not None:
            witness.mkdir(mode=0o700)
        for mode in modes:
            phase, active_mode, active_session = 'session-setup', mode, None
            session = Session(args.binary, args.private / mode, commission, Path(__file__).parent / 'submission', mode, witness=witness)
            active_session = session
            session.intake()
            sessions.append(session)
        phase, active_mode, active_session = 'publish-readiness', None, None
        write_json(args.out / 'READY.json', {'credential_free_intake_verified': True,
            'scenarios': modes, 'operator_roots': [str(s.root) for s in sessions], 'at': time.time()})
        phase = 'credential-entry'
        key = credential_bytes(sys.stdin.buffer.read(4098))
        if witness is not None:
            with (witness / 'canary.bin').open('xb') as stream:
                stream.write(key)
            report['independent_credential_witness'] = {'location': str(witness),
                'canary_sha256': digest(key), 'retention': 'private retained container; outside archives and exports under test'}
        for session in sessions:
            try:
                summary = session.run(key)
                if summary['failure']:
                    report['failures'].append(session.mode)
                report['scenarios'].append(summary)
            except Exception as error:
                # Exceptions may contain provider text; never forward them outside.
                report['failures'].append(session.mode)
                detail = failure_details(error, session.phase, session.mode)
                if session.observer_state is not None:
                    detail['observer'] = session.observer_state
                report.setdefault('failure_details', []).append(detail)
                write_json(session.evidence / 'procedure-failure.json', {**detail, 'at': time.time()})
        # Export each scenario independently; a reflected specimen must not prevent
        # the clean scenarios from furnishing their independent witnesses.
        report['exports'] = []
        phase = 'evidence-export'
        for session in sessions:
            destination = args.out / session.mode
            destination.mkdir(mode=0o700)
            result = export_work(session.root, destination, key, force_failure=session.mode == 'export-failure')
            write_json(destination / 'EXPORT.json', result)
            report['exports'].append({'scenario': session.mode, **result})
            expected = 'withheld' if session.mode in ['reflected-body', 'export-contamination'] else 'failed' if session.mode == 'export-failure' else 'exported'
            if args.mode == 'rehearse' and result['outcome'] != expected:
                report['failures'].append(session.mode + ':export')
        if args.mode == 'rehearse':
            report['outcome'] = 'passed' if not report['failures'] else 'failed'
        else:
            export = report['exports'][0]['outcome'] if report['exports'] else 'withheld'
            if export == 'failed':
                report['failures'].append('live:export_failed')
            report['outcome'] = 'failed' if report['failures'] else 'observed_review_required'
    except Exception as error:
        report['outcome'] = 'failed'
        report['failures'].append('setup-or-credential; private originals retained')
        report.setdefault('failure_details', []).append(failure_details(error,
            active_session.phase if active_session is not None else phase, active_mode))
    report['ended_at'] = time.time()
    write_json(args.out / 'RESULT.json', report)
    print('Sanity session finished; inspect RESULT.json. Originals remain in the container.', flush=True)
    return report['outcome'] not in ['passed', 'observed_review_required']


if __name__ == '__main__':
    raise SystemExit(main())
