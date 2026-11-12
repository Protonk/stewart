"""Durable invocation budgets and supervised processes; no live command-line entry.

This library is apparatus, not a grant of spending authority. A future live
controller must validate its full commission and pass the principal's exact
approved budget digest. Tests use only synthetic processes. Groups are cooperative
process control, not confinement of an executable that escapes its group.
"""

import base64
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import select
import selectors
import signal
import sys
import time

_spec = importlib.util.spec_from_file_location('bounded_profile', Path(__file__).with_name('profile.py'))
data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(data)
CLOCK_NAME = 'CLOCK_UPTIME_RAW' if sys.platform == 'darwin' else 'CLOCK_MONOTONIC'
CLOCK = getattr(time, CLOCK_NAME)
AUTH_LIMIT = 65536
MODEL_LIMIT = 32 * 1024 * 1024
STOP_GRACE = 0.3


def now():
    return time.clock_gettime(CLOCK)


def record(path, value):
    data.publish(path, data.compact(value) + b'\n')


def validate(value):
    data.exact(value, ('schema', 'mode', 'purpose', 'overall_timeout_seconds', 'bindings', 'invocations'), 'budget')
    if value['schema'] != 'stewart.claude-code.invocation-budget/1' or value['mode'] not in ('synthetic-rehearsal', 'real-harness'):
        raise ValueError('unsupported invocation budget')
    data.text(value['purpose'], 'purpose')
    bound = value['overall_timeout_seconds']
    if type(bound) is not int or not 1 <= bound <= 21600:
        raise ValueError('overall timeout must be 1..21600 seconds')
    if not isinstance(value['bindings'], list) or not value['bindings']:
        raise ValueError('budget must bind its executable and source inputs')
    paths = set()
    for item in value['bindings']:
        data.exact(item, ('path', 'sha256'), 'file binding')
        path = str(data.absolute(data.text(item['path'], 'bound path')))
        data.checksum(item['sha256'], 'file digest')
        if path in paths:
            raise ValueError('repeated bound path')
        paths.add(path)
    slots = value['invocations']
    if not isinstance(slots, list) or not 1 <= len(slots) <= 32:
        raise ValueError('budget requires 1..32 named invocations')
    identities = set()
    for index, item in enumerate(slots):
        data.exact(item, ('id', 'role', 'argv', 'environment', 'working_directory',
                          'stdin_base64', 'timeout_seconds'), 'invocation')
        identity = data.text(item['id'], 'invocation id')
        if not identity.isascii() or not all(c.isalnum() or c in '-_' for c in identity) or identity in identities:
            raise ValueError('invocation ids must be unique ASCII names')
        identities.add(identity)
        if item['role'] not in ('auth', 'model'):
            raise ValueError('invocation role must be auth or model')
        argv = item['argv']
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and '\0' not in arg for arg in argv):
            raise ValueError('invalid argument vector')
        if str(data.absolute(argv[0])) not in paths:
            raise ValueError('executable is not bound')
        environment = item['environment']
        if (not isinstance(environment, dict) or not environment
                or any(not isinstance(k, str) or not k or '=' in k or '\0' in k
                       or not isinstance(v, str) or '\0' in v for k, v in environment.items())):
            raise ValueError('invalid explicit environment')
        data.absolute(data.text(item['working_directory'], 'working directory'))
        if type(item['timeout_seconds']) is not int or not 1 <= item['timeout_seconds'] <= bound:
            raise ValueError('invocation timeout exceeds its budget')
        if not isinstance(item['stdin_base64'], str):
            raise ValueError('input must be base64 text')
        payload = base64.b64decode(item['stdin_base64'], validate=True)
        if len(payload) > 1024 * 1024 or (item['role'] == 'auth' and payload):
            raise ValueError('input exceeds apparatus bound or auth input is not empty')
        if item['role'] == 'model' and (index == 0 or slots[index - 1]['role'] != 'auth'):
            raise ValueError('each model invocation requires its own preceding authentication slot')
        if value['mode'] == 'real-harness':
            if item['role'] == 'auth' and argv[1:] != ['auth', 'status']:
                raise ValueError('live authentication may only invoke auth status')
            if item['role'] == 'model':
                previous = slots[index - 1]
                if any(previous[key] != item[key] for key in ('environment', 'working_directory')) or previous['argv'][0] != argv[0]:
                    raise ValueError('model and fresh authentication must share executable, environment and directory')
    return value


def verify_bindings(value):
    for item in value['bindings']:
        if data.read_file(Path(item['path']), limit=None, hash_only=True)[0] != item['sha256']:
            raise ValueError('bound file changed: ' + item['path'])
    for slot in value['invocations']:
        os.close(data.directory(Path(slot['working_directory'])))


def prepare(root, value):
    """Freeze a new budget without executing anything or recording approval."""
    root = data.absolute(root)
    validate(value)
    verify_bindings(value)
    os.close(data.directory(root.parent))
    root.mkdir(mode=0o700)
    record(root / 'BUDGET.json', value)
    return data.sha(data.read_file(root / 'BUDGET.json'))


def _guard(control, status, child_input, child_output, child_error, slot, deadline, close_fds):
    """Separate session; no exec until owner has durably recorded its group."""
    try:
        for fd in close_fds:
            os.close(fd)
        os.setsid()
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        os.write(status, b'R\n')
        remaining = max(0, deadline - now())
        if not select.select([control], [], [], remaining)[0] or os.read(control, 1) != b'G':
            os._exit(125)
        if now() >= deadline:
            os._exit(125)
        worker = os.fork()
        if worker == 0:
            try:
                signal.signal(signal.SIGTERM, signal.SIG_DFL)
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                for source, target in ((child_input, 0), (child_output, 1), (child_error, 2)):
                    os.dup2(source, target)
                for fd in (control, status, child_input, child_output, child_error):
                    if fd > 2:
                        os.close(fd)
                os.chdir(slot['working_directory'])
                if now() >= deadline:
                    os._exit(124)
                os.execve(slot['argv'][0], slot['argv'], slot['environment'])
            except BaseException:
                # No exception text: it might expose authentication diagnostics.
                os._exit(127)
        for fd in (child_input, child_output, child_error):
            os.close(fd)
        reason = b'deadline'
        while now() < deadline:
            got, status_code = os.waitpid(worker, os.WNOHANG)
            if got:
                os.write(status, b'E' + str(os.waitstatus_to_exitcode(status_code)).encode() + b'\n')
                reason = b'worker-exit'
                break
            if select.select([control], [], [], min(0.02, max(0, deadline - now())))[0]:
                # Owner closure or any further byte revokes this invocation.
                os.read(control, 1)
                reason = b'owner-stop'
                break
        try:
            os.write(status, b'S' + reason + b'\n')
        except OSError:
            pass
        os.killpg(os.getpid(), signal.SIGTERM)
        until = now() + STOP_GRACE
        while now() < until:
            try:
                os.waitpid(worker, os.WNOHANG)
            except ChildProcessError:
                pass
            time.sleep(0.01)
        os.killpg(os.getpid(), signal.SIGKILL)
    except BaseException:
        # An internal guard failure must not strand a child it may have started.
        try:
            if os.getpgrp() == os.getpid():
                os.killpg(os.getpid(), signal.SIGKILL)
        finally:
            os._exit(125)


def supervise(slot, root, deadline, on_stdout=None, on_stderr=None, check_stop=None):
    """Capture before observer callbacks; authentication stays private in memory.

    The separate guard stops its group on owner EOF or its kernel-clock deadline,
    including when the observer stalls. The owner must still complete evidence
    writes. Neither this mechanism nor its deadline confines escaped descendants.
    """
    started = now()
    deadline = min(deadline, started + slot['timeout_seconds'])
    private = slot['role'] == 'auth'
    captured = {'stdout': bytearray(), 'stderr': bytearray()} if private else None
    outputs, pairs, selector = {}, [], selectors.DefaultSelector()
    pid = None
    reaped, group_gone, permission_sent = False, False, False
    exit_code, stopped, guard_reason = None, None, None
    control_write = None
    seen = 0
    sent = 0
    capture_bytes = {'stdout': 0, 'stderr': 0}
    capture_hashes = {name: hashlib.sha256() for name in capture_bytes}
    stream_eof = {'stdout': False, 'stderr': False}
    status_pending = b''
    payload = base64.b64decode(slot['stdin_base64'], validate=True)
    try:
        if not private:
            for channel in ('stdout', 'stderr'):
                outputs[channel] = (root / (channel + '.bin')).open('xb', buffering=0)
        # All pipes are non-inheritable across exec except the explicitly duped
        # standard streams. The guard also closes owner-only ends before waiting.
        pairs = [os.pipe() for _ in range(5)]
        (stdin_r, stdin_w), (stdout_r, stdout_w), (stderr_r, stderr_w), (control_r, control_write), (status_r, status_w) = pairs
        pid = os.fork()
        if pid == 0:
            _guard(control_r, status_w, stdin_r, stdout_w, stderr_w, slot, deadline,
                   (stdin_w, stdout_r, stderr_r, control_write, status_r))
            os._exit(125)
        for fd in (stdin_r, stdout_w, stderr_w, control_r, status_w):
            os.close(fd)
        pairs = [(stdin_w, stdout_r, stderr_r, control_write, status_r)]
        for fd, channel in ((stdout_r, 'stdout'), (stderr_r, 'stderr'), (status_r, 'guard')):
            os.set_blocking(fd, False)
            selector.register(fd, selectors.EVENT_READ, channel)
        os.set_blocking(stdin_w, False)
        while selector.get_map() or not reaped:
            if not private and check_stop is not None:
                check_stop()
            if now() >= deadline + STOP_GRACE + 1:
                stopped = stopped or 'process observation deadline reached'
                break
            if not reaped:
                got, _ = os.waitpid(pid, os.WNOHANG)
                reaped = bool(got)
            for key, mask in selector.select(0.02):
                channel = key.data
                if channel == 'stdin':
                    broken = False
                    try:
                        count = os.write(key.fd, payload[sent:sent + 65536])
                        sent += count
                    except BrokenPipeError:
                        stopped = stopped or 'input pipe closed before all input was sent'
                        broken = True
                    if sent == len(payload) or broken:
                        selector.unregister(key.fd)
                        os.close(key.fd)
                        pairs[0] = tuple(fd for fd in pairs[0] if fd != key.fd)
                    if broken:
                        raise ValueError('input pipe closed before all input was sent')
                    continue
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    if channel in stream_eof:
                        stream_eof[channel] = True
                    selector.unregister(key.fd)
                    continue
                if channel == 'guard':
                    status_pending += chunk
                    while b'\n' in status_pending:
                        line, status_pending = status_pending.split(b'\n', 1)
                        if line == b'R' and not permission_sent:
                            record(root / 'group.json', {'group': pid, 'clock': CLOCK_NAME,
                                   'observer_pid': os.getpid(), 'deadline': deadline})
                            os.write(control_write, b'G')
                            permission_sent = True
                            if payload:
                                selector.register(stdin_w, selectors.EVENT_WRITE, 'stdin')
                            else:
                                os.close(stdin_w)
                                pairs[0] = tuple(fd for fd in pairs[0] if fd != stdin_w)
                        elif line.startswith(b'E'):
                            exit_code = int(line[1:])
                        elif line.startswith(b'S'):
                            guard_reason = line[1:].decode('ascii')
                    continue
                seen += len(chunk)
                if seen > (AUTH_LIMIT if private else MODEL_LIMIT):
                    stopped = 'authentication output exceeded private bound' if private else 'process capture bound exceeded'
                    raise ValueError(stopped)
                if private:
                    captured[channel].extend(chunk)
                else:
                    if outputs[channel].write(chunk) != len(chunk):
                        raise OSError('incomplete process capture')
                    os.fsync(outputs[channel].fileno())
                    capture_bytes[channel] += len(chunk)
                    capture_hashes[channel].update(chunk)
                    if channel == 'stdout' and on_stdout is not None:
                        on_stdout(chunk)
                    elif channel == 'stderr' and on_stderr is not None:
                        on_stderr(chunk)
    except (Exception, KeyboardInterrupt) as error:
        # Authentication failures never interpolate child output or parser errors.
        stopped = 'private authentication failed' if private else type(error).__name__ + ': ' + str(error)
    finally:
        if control_write is not None:
            try:
                os.close(control_write)
            except OSError:
                pass
        if pid is not None and pid > 0:
            until = now() + STOP_GRACE + 1
            while now() < until:
                if not reaped:
                    got, _ = os.waitpid(pid, os.WNOHANG)
                    reaped = bool(got)
                try:
                    os.killpg(pid, 0)
                    group_gone = False
                except ProcessLookupError:
                    group_gone = True
                except PermissionError:
                    group_gone = False
                if reaped and group_gone:
                    break
                time.sleep(0.01)
            if not reaped or not group_gone:
                # Only our newly forked child/group, never a historical PID.
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    if not reaped:
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                except PermissionError:
                    pass
                stopped = stopped or 'process stopping not observed'
            # Drain already available bytes after a stop without parsing them into
            # a success. Bounded by nonblocking reads and the capture ceiling.
            if not private:
                for fd, channel in ((stdout_r, 'stdout'), (stderr_r, 'stderr')):
                    while seen < MODEL_LIMIT:
                        try:
                            tail = os.read(fd, min(65536, MODEL_LIMIT - seen))
                        except (BlockingIOError, OSError):
                            break
                        if not tail:
                            stream_eof[channel] = True
                            break
                        seen += len(tail)
                        try:
                            if outputs[channel].write(tail) != len(tail):
                                raise OSError('incomplete stopping capture')
                            capture_bytes[channel] += len(tail)
                            capture_hashes[channel].update(tail)
                        except OSError:
                            stopped = stopped or 'capture failed during stopping'
                            break
        selector.close()
        for pair in pairs:
            for fd in pair:
                if fd == control_write:
                    continue
                try:
                    os.close(fd)
                except OSError:
                    pass
        for output in outputs.values():
            try:
                os.fsync(output.fileno())
            except OSError:
                stopped = stopped or 'capture flush failed during stopping'
            finally:
                output.close()
    if guard_reason != 'worker-exit':
        stopped = stopped or 'guard stopped invocation: ' + str(guard_reason)
    if exit_code != 0:
        stopped = stopped or 'invoked process did not exit successfully'
    if not reaped or not group_gone:
        stopped = stopped or 'process stopping not observed'
    result = {'exit': exit_code, 'stop': stopped, 'group_gone': group_gone, 'guard_reaped': reaped,
              'elapsed_seconds': now() - started, 'input_bytes_sent': sent, 'guard_reason': guard_reason}
    if not private:
        result.update(capture_bytes=capture_bytes,
                      capture_sha256={name: item.hexdigest() for name, item in capture_hashes.items()},
                      input_prefix_sha256=data.sha(payload[:sent]), stream_eof=stream_eof)
    if private:
        status = {}
        try:
            raw_status = data.decode(bytes(captured['stdout']))
            if (isinstance(raw_status, dict) and type(raw_status.get('loggedIn')) is bool
                    and isinstance(raw_status.get('authMethod'), str)
                    and isinstance(raw_status.get('configDirectory'), str)):
                status = {key: raw_status[key] for key in ('loggedIn', 'authMethod', 'configDirectory')}
            if status != {'loggedIn': True, 'authMethod': 'claude.ai',
                          'configDirectory': slot['environment'].get('CLAUDE_CONFIG_DIR')}:
                result['stop'] = result['stop'] or 'authentication route differs from the bound subscription login'
        except (ValueError, UnicodeError):
            result['stop'] = result['stop'] or 'authentication output is invalid'
        finally:
            for buffer in captured.values():
                buffer.clear()
        record(root / 'auth-status.json', status)
    record(root / 'result.json', result)
    return result


class Budget:
    """One non-resumable batch. A lost reply consumes reservations, never retries."""
    def __init__(self, root, approved_digest=None, extra_usage_disabled=False):
        self.root = data.absolute(root)
        self.approved_digest = approved_digest
        self.extra_usage_disabled = extra_usage_disabled
        self.lock = None
        self.index = 0
        self.failed = False

    def __enter__(self):
        parent = data.directory(self.root)
        try:
            self.lock = os.open('run.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
        finally:
            os.close(parent)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            raw = data.read_file(self.root / 'BUDGET.json')
            self.raw = raw
            self.value = validate(data.decode(raw))
            if self.value['mode'] == 'real-harness':
                if self.approved_digest != data.sha(raw) or self.extra_usage_disabled is not True:
                    raise ValueError('live use needs the principal-approved exact budget digest and paid extra usage disabled')
            elif self.approved_digest is not None:
                raise ValueError('synthetic rehearsal does not accept live approval')
            verify_bindings(self.value)
            self.deadline = now() + self.value['overall_timeout_seconds']
            record(self.root / 'START.json', {'budget_sha256': data.sha(raw), 'mode': self.value['mode'],
                   'clock': CLOCK_NAME, 'observer_pid': os.getpid(), 'deadline': self.deadline,
                   'approved_digest': self.approved_digest, 'extra_usage_disabled': self.extra_usage_disabled})
            (self.root / 'uses').mkdir(mode=0o700)
            return self
        except BaseException:
            os.close(self.lock)
            self.lock = None
            raise

    def execute(self, identity, on_stdout=None, on_stderr=None, check_stop=None):
        if self.lock is None or self.failed or now() >= self.deadline:
            raise ValueError('invocation batch is closed, failed or expired; no further start allowed')
        slots = self.value['invocations']
        if self.index >= len(slots) or slots[self.index]['id'] != identity:
            raise ValueError('invocation is repeated or outside the frozen order')
        slot = slots[self.index]
        try:
            if data.read_file(self.root / 'BUDGET.json') != self.raw:
                raise ValueError('frozen invocation budget changed')
            if self.value != data.decode(self.raw):
                raise ValueError('in-memory invocation budget changed')
            verify_bindings(self.value)
            out = self.root / 'uses' / identity
            out.mkdir(mode=0o700)
            record(out / 'RESERVATION.json', {'id': identity, 'slot': self.index,
                   'status': 'reserved; execution uncertain until observed completion'})
            self.index += 1
            result = supervise(slot, out, self.deadline, on_stdout, on_stderr, check_stop)
            self.failed = result['stop'] is not None or not result['group_gone']
            return result
        except BaseException:
            self.failed = True
            raise

    def __exit__(self, kind, value, traceback):
        try:
            record(self.root / 'FINISH.json', {'invocations_reserved': self.index,
                   'invocations_unstarted': len(self.value['invocations']) - self.index,
                   'failed': self.failed or kind is not None, 'resume_allowed': False})
        finally:
            os.close(self.lock)
            self.lock = None

    def halt(self, reason):
        """An independent final assessment can close the batch between slots."""
        self.failed = True
        record(self.root / 'HALT.json', {'reason': data.text(reason, 'halt reason'),
               'invocations_reserved': self.index, 'resume_allowed': False})
