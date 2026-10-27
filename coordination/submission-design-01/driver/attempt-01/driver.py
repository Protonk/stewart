#!/usr/bin/env python3
"""Independent retained process comparisons for the disposable submission prototype."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import traceback

COMMISSION = hashlib.sha256(b'independent prototype commission witness').hexdigest()
MIB = 1024 * 1024
CASES = {}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + '\n').encode()


def exclusive(path, data):
    with path.open('xb') as stream:
        stream.write(data)


def record(path, value):
    exclusive(path, encoded(value))


def case(name):
    def decorate(fn):
        CASES[name] = fn
        return fn
    return decorate


def snapshot(root):
    """Observe only regular files/directories; never follow a planted symlink."""
    entries = {}
    def visit(directory):
        for path in sorted(directory.iterdir()):
            info = path.lstat()
            rel = str(path.relative_to(root))
            row = {'mode': stat.S_IMODE(info.st_mode), 'device': info.st_dev,
                   'inode': info.st_ino, 'size': info.st_size}
            if stat.S_ISDIR(info.st_mode):
                row['kind'] = 'directory'
                entries[rel] = row
                visit(path)
            elif stat.S_ISREG(info.st_mode):
                row['kind'] = 'file'
                row['sha256'] = digest(path.read_bytes())
                entries[rel] = row
            elif stat.S_ISLNK(info.st_mode):
                row['kind'] = 'symlink'
                row['target'] = os.readlink(path)
                entries[rel] = row
            else:
                row['kind'] = 'special'
                entries[rel] = row
    visit(root)
    return entries


def byte_population(observation):
    return {name: {key: value for key, value in row.items()
                   if key not in ('inode', 'device', 'size') or row['kind'] == 'file'}
            for name, row in observation.items()}


class Trial:
    def __init__(self, harness, name):
        self.h = harness
        self.name = name
        self.dir = harness.evidence / 'cases' / name
        self.dir.mkdir(parents=True)
        self.home = harness.work / 'specimens' / name
        self.home.mkdir(parents=True)
        self.cwd = harness.work / 'unrelated-cwd' / name / 'deep' / 'nested'
        self.cwd.mkdir(parents=True)
        self.store = self.home / 'stores' / 'nested' / 'selection'
        self.store.mkdir(parents=True)
        self.sources = self.home / 'sources'
        self.sources.mkdir()
        self.witnesses = self.dir / 'witnesses'
        self.witnesses.mkdir()
        self.n = 0
        self.assertions = 0
        self.children = []
        self.stores = [self.store]
        record(self.dir / 'START.json', {'at': now(), 'cwd': str(self.cwd),
               'store': str(self.store), 'home': str(self.home), 'driver_pid': os.getpid()})
        self.snap('before')

    def check(self, condition, description, actual=None, expected=None):
        self.assertions += 1
        self.h.assertions += 1
        item = {'number': self.assertions, 'at': now(), 'description': description,
                'pass': bool(condition)}
        if actual is not None:
            item['actual'] = actual
        if expected is not None:
            item['expected'] = expected
        with (self.dir / 'assertions.jsonl').open('ab') as stream:
            stream.write(encoded(item))
        if not condition:
            raise AssertionError(f'{description}: actual={actual!r}, expected={expected!r}')

    def snap(self, label, store=None):
        value = snapshot(store or self.store)
        record(self.dir / (label + '.snapshot.json'), value)
        return value

    def source(self, label, data):
        witness = self.witnesses / label
        source = self.sources / label
        exclusive(witness, data)
        exclusive(source, data)
        record(self.witnesses / (label + '.identity.json'),
               {'size': len(data), 'sha256': digest(data), 'source': str(source),
                'witness': str(witness), 'at': now()})
        return source

    def request(self, op, key, source=None, data=None, **kwargs):
        result = {'op': op, 'request_id': key, **kwargs}
        if source is not None:
            result.update(source=str(source), size=len(data), sha256=digest(data))
        return result

    def start(self, request=None, raw=None, hook=None, store=None, argv=None, binary=None):
        self.n += 1
        self.h.invocations += 1
        label = f'{self.n:04d}'
        folder = self.dir / 'commands' / label
        folder.mkdir(parents=True)
        data = raw if raw is not None else encoded(request)
        exclusive(folder / 'stdin.bin', data)
        command = argv or [str(binary or self.h.binary), '--store', str(store or self.store)]
        env = os.environ.copy()
        env.pop('STEWART_PROTO_PAUSE', None)
        if hook:
            env['STEWART_PROTO_PAUSE'] = hook
        before_hook = self.snap('before-hook-' + label, store or self.store) if hook else None
        out = (folder / 'stdout.bin').open('xb')
        err = (folder / 'stderr.bin').open('xb')
        proc = subprocess.Popen(command, cwd=self.cwd, env=env, stdin=subprocess.PIPE,
                                stdout=out, stderr=err)
        item = {'process': proc, 'dir': folder, 'stdout_file': out, 'stderr_file': err,
                'request': request, 'hook': hook, 'store': store or self.store,
                'finished': False, 'before_hook': before_hook}
        self.children.append(item)
        record(folder / 'START.json', {'at': now(), 'argv': command, 'cwd': str(self.cwd),
               'pid': proc.pid, 'driver_pid': os.getpid(), 'hook': hook,
               'stdin_size': len(data), 'stdin_sha256': digest(data)})
        proc.stdin.write(data)
        proc.stdin.close()
        return item

    def finish(self, item, timeout=12, parse=True):
        proc = item['process']
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.send(item, signal.SIGKILL, 'bounded process timeout')
            code = proc.wait(timeout=5)
            record(item['dir'] / 'TIMEOUT.json', {'at': now(), 'seconds': timeout})
        item['stdout_file'].close()
        item['stderr_file'].close()
        item['finished'] = True
        raw = (item['dir'] / 'stdout.bin').read_bytes()
        record(item['dir'] / 'EXIT.json', {'at': now(), 'pid': proc.pid, 'exit_code': code,
               'stdout_size': len(raw), 'stdout_sha256': digest(raw),
               'stderr_sha256': digest((item['dir'] / 'stderr.bin').read_bytes())})
        if not parse:
            return code, raw
        try:
            value = json.loads(raw)
        except Exception as exc:
            raise AssertionError(f'command {item["dir"].name}: non-JSON stdout, exit {code}: {raw!r}') from exc
        self.check(isinstance(value, dict), 'outcome is one JSON object')
        return code, value

    def call(self, request=None, raw=None, store=None, ok=True, reason=None, binary=None):
        code, value = self.finish(self.start(request=request, raw=raw, store=store, binary=binary))
        if ok:
            self.check(code == 0 and value.get('ok') is True,
                       'successful process outcome', {'exit': code, 'outcome': value}, 0)
        else:
            self.check(code == 2 and value.get('ok') is False,
                       'refusal process outcome', {'exit': code, 'outcome': value}, 2)
            for field in ('reason', 'message', 'paths', 'next_step', 'effect'):
                self.check(field in value, 'refusal has ' + field)
            self.check(isinstance(value['paths'], list), 'refusal paths is an array')
            self.check(value['effect'] in ('unchanged', 'partial', 'uncertain'),
                       'refusal qualifies effects', value['effect'])
            if reason:
                self.check(value['reason'] == reason, 'stable refusal reason', value['reason'], reason)
        return value

    def init(self, audit='audit-a', store=None):
        return self.call({'op': 'init', 'audit': audit, 'commission_sha256': COMMISSION,
                          'request_id': 'init'}, store=store)['state']

    def add(self, key, data=b'ordinary answer', name='answer', store=None):
        source = self.source(key, data)
        req = self.request('add', key, source, data, name=name)
        result = self.call(req, store=store)
        return result, req, source

    def inspect(self, store=None):
        return self.call({'op': 'inspect'}, store=store)['state']

    def prepare(self, key='prepare', store=None):
        return self.call({'op': 'prepare', 'request_id': key}, store=store)

    def verify_read(self, element, data, store=None):
        got = self.call({'op': 'read', 'handle': element['handle']}, store=store)
        self.check(got['element'] == element, 'read preserves exact element descriptor')
        self.check(got['bytes_hex'] == data.hex(), 'read matches independent exact bytes')
        self.check(element['sha256'] == digest(data) and element['size'] == len(data),
                   'element identity matches independent byte witness')

    def send(self, item, sig, why):
        path = item['dir'] / f'SIGNAL-{time.monotonic_ns()}.json'
        record(path, {'at': now(), 'pid': item['process'].pid, 'signal': sig.name, 'why': why})
        os.kill(item['process'].pid, sig)

    def stopped(self, item):
        deadline = time.monotonic() + 12
        marker = None
        stopped = None
        while time.monotonic() < deadline:
            raw = (item['dir'] / 'stderr.bin').read_bytes()
            for line in raw.splitlines():
                try:
                    value = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                if isinstance(value, dict) and value.get('hook') == item['hook']:
                    marker = value
            pid, status = os.waitpid(item['process'].pid, os.WNOHANG | os.WUNTRACED)
            if pid:
                if os.WIFSTOPPED(status):
                    stopped = {'pid': pid, 'wait_status': status,
                               'stop_signal': os.WSTOPSIG(status), 'at': now()}
                elif os.WIFEXITED(status) or os.WIFSIGNALED(status):
                    item['process'].returncode = os.waitstatus_to_exitcode(status)
                    break
            if marker and stopped:
                break
            time.sleep(0.01)  # bounded poll for explicit marker and kernel stop, not a race timer
        record(item['dir'] / 'BARRIER.json', {'at': now(), 'marker': marker,
               'kernel_stop': stopped, 'observer': 'parent waitpid WUNTRACED plus raw stderr'})
        self.check(marker is not None, 'requested barrier emitted independently captured marker')
        self.check(stopped is not None and stopped['stop_signal'] == signal.SIGSTOP,
                   'kernel observed actual SIGSTOP', stopped)
        self.check(isinstance(marker.get('request_id'), str), 'barrier identifies request')
        self.check(isinstance(marker.get('commit'), str), 'barrier identifies planned commit')
        expected_key = item['request'].get('request_id', item['request'].get('handle'))
        self.check(marker['request_id'] == expected_key, 'barrier binds caller-known request identity')
        observed = self.snap('stopped-' + item['dir'].name, item['store'])
        published = item['hook'] in ('after_publish', 'after_sync')
        self.check((marker['commit'] in observed) is published,
                   'independent snapshot proves commit publication side of fired barrier')
        request_name = 'request-' + digest(expected_key.encode()) + '.json'
        request_raw = (item['store'] / request_name).read_bytes()
        binding = json.loads(request_raw)
        request_ref = {'name': request_name, 'sha256': digest(request_raw)}
        prefix = 'attempt-' + digest(expected_key.encode()) + '-'
        attempts = [name for name in observed if name not in item['before_hook']
                    and name.startswith(prefix) and name.endswith('.json')]
        self.check(bool(attempts), 'fired request has independently observed scoped attempt plan')
        staged = []
        for name in attempts:
            attempt = json.loads((item['store'] / name).read_bytes())
            self.check(attempt.get('request') == request_ref, 'attempt binds exact fired request bytes')
            coordinate = attempt['record_stage']
            self.check(isinstance(coordinate, str) and Path(coordinate).name == coordinate,
                       'documented record_stage is one planned store coordinate')
            if coordinate in observed:
                stage_raw = (item['store'] / coordinate).read_bytes()
                stage = json.loads(stage_raw)
                self.check(stage.get('schema') == 'prototype-commit-v1' and
                           stage.get('request') == request_ref and stage.get('state') == binding['candidate'],
                           'planned record_stage contains complete bound commit candidate')
                staged.append({'attempt': name, 'record_stage': coordinate, 'sha256': digest(stage_raw)})
        record(item['dir'] / 'COMMIT-STAGE.json', {'request': request_ref,
               'attempts': attempts, 'complete_commit_stages': staged, 'at': now()})
        self.check(bool(staged) is (item['hook'] != 'after_stage'),
                   'independent snapshot distinguishes payload-only from complete staged-commit barrier',
                   staged)
        return marker

    def close(self):
        for item in self.children:
            if not item['finished']:
                if item['process'].poll() is None:
                    self.send(item, signal.SIGKILL, 'retain incomplete failed-case child evidence')
                self.finish(item, parse=False)
        for index, store in enumerate(self.stores):
            self.snap(f'after-{index}', store)


@case('ordinary_bytes_names_source_loss')
def ordinary(t):
    state = t.init()
    t.check(state['revision'] == 0 and state['elements'] == [], 'empty initial collection')
    fixtures = [b'\0\xff\x80\r\n', 'Partial answer: café, 雪; a reframed question.\n'.encode(), b'', b'\0\xff\x80\r\n']
    elements = []
    for index, data in enumerate(fixtures):
        result, request, source = t.add('add-' + str(index), data, name='same 雪 name')
        elements.append(result['element'])
        t.verify_read(result['element'], data)
        source.rename(source.with_name(source.name + '.source-lost'))
        t.verify_read(result['element'], data)
        repeat = t.call(request)
        t.check(repeat == result, 'matching key recovers exact original outcome after source loss')
    final = t.inspect()
    t.check(final['elements'] == elements, 'ordered exact population survives fresh helper processes')
    t.check(len({element['id'] for element in elements}) == len(fixtures), 'same descriptive name retains distinct IDs')
    t.check(elements[0]['sha256'] == elements[-1]['sha256'] and elements[0]['id'] != elements[-1]['id'],
            'equal bytes and equal names do not merge independent selection identities')
    t.check(final['revision'] == len(fixtures), 'each acknowledged addition increments revision')


@case('equal_bytes_replace_delete_stale')
def replace_delete(t):
    t.init()
    first, _, source = t.add('a', b'unchanged bytes')
    other, _, _ = t.add('b', b'invariant independent element')
    before = t.inspect()
    req = t.request('replace', 'r', source, b'unchanged bytes', name='renamed', handle=first['element']['handle'])
    replaced = t.call(req)
    t.check(replaced['element']['handle'] != first['element']['handle'], 'equal-byte replacement changes handle')
    t.check(replaced['element']['version'] != first['element']['version'], 'equal-byte replacement changes version')
    t.check(replaced['state']['revision'] == before['revision'] + 1, 'equal-byte replacement increments collection revision')
    t.check(replaced['state']['elements'][1] == other['element'], 'unaffected identity stays invariant')
    t.verify_read(other['element'], b'invariant independent element')
    for op in ('replace', 'delete'):
        stale = {'op': op, 'request_id': 'stale-' + op, 'handle': first['element']['handle']}
        if op == 'replace':
            stale.update(name='new', source=str(source), size=len(b'unchanged bytes'), sha256=digest(b'unchanged bytes'))
        t.call(stale, ok=False, reason='stale_handle')
    t.check(t.inspect() == replaced['state'], 'obsolete-handle refusals leave current collection invariant')
    deleted = t.call({'op': 'delete', 'request_id': 'delete-current', 'handle': replaced['element']['handle']})
    t.check(deleted['state']['elements'] == [other['element']], 'delete removes only current membership')
    t.verify_read(other['element'], b'invariant independent element')


@case('changed_key_source_identity')
def changed_key(t):
    t.init()
    added, req, source = t.add('fixed', b'witness A')
    changed = dict(req, name='different intent')
    t.call(changed, ok=False, reason='request_conflict')
    t.check(t.inspect() == added['state'], 'changed key cannot make another edit')
    source.write_bytes(b'witness B')
    t.call(t.request('add', 'mismatch', source, b'witness A', name='mismatch'), ok=False, reason='source_mismatch')
    t.check(t.inspect() == added['state'], 'source identity refusal preserves collection')
    t.verify_read(added['element'], b'witness A')


@case('bounds_element_exact')
def element_bound(t):
    t.init()
    result, _, _ = t.add('at-limit', b'X' * MIB)
    t.verify_read(result['element'], b'X' * MIB)
    data = b'Y' * (MIB + 1)
    source = t.source('over-limit', data)
    t.call(t.request('add', 'over', source, data, name='over'), ok=False, reason='limit_exceeded')
    t.check(t.inspect() == result['state'], 'per-element overflow cannot publish')


@case('bounds_count_exact')
def count_bound(t):
    t.init()
    for index in range(32):
        result, _, _ = t.add('count-' + str(index), b'', name='empty')
    t.check(len(result['state']['elements']) == 32, 'exact 32-element bound admitted')
    source = t.source('overflow', b'')
    t.call(t.request('add', 'count-over', source, b'', name='empty'), ok=False, reason='limit_exceeded')
    t.check(t.inspect() == result['state'], 'active-count overflow leaves exact population invariant')


@case('bounds_active_bytes_exact')
def active_bound(t):
    t.init()
    for index in range(8):
        result, _, _ = t.add('bytes-' + str(index), bytes([65 + index]) * MIB)
    t.check(sum(e['size'] for e in result['state']['elements']) == 8 * MIB, 'exact active-byte bound admitted')
    source = t.source('one-over', b'!')
    t.call(t.request('add', 'bytes-over', source, b'!', name='one over'), ok=False, reason='limit_exceeded')
    t.check(t.inspect() == result['state'], 'active-byte overflow cannot publish')


@case('bounds_control_bytes_exact')
def control_bound(t):
    initial = t.init()
    minimal = b'{"op":"inspect"}'
    exact = minimal + b' ' * (64 * 1024 - len(minimal))
    result = t.call(raw=exact)
    t.check(result['state'] == initial, 'exact documented control-input bound admitted')
    t.call(raw=exact + b' ', ok=False)
    t.check(t.inspect() == initial, 'control-input one-byte overflow changes no current state')


@case('help_side_effect_free')
def help_check(t):
    before = snapshot(t.cwd)
    code, raw = t.finish(t.start(raw=b'', argv=[str(t.h.binary), '--help']), parse=False)
    t.check(code == 0, 'help succeeds without selecting a store')
    help_text = raw.decode('utf-8').lower()
    t.check(all(word in help_text for word in ('--store', 'prepare', 'submit', 'delete', 'resume')),
            'help describes store and supported operation surface')
    t.check(snapshot(t.cwd) == before and snapshot(t.store) == {}, 'help creates no cwd or store state')


BAD_INPUTS = {
    'duplicate_top': b'{"op":"inspect","op":"inspect"}',
    'duplicate_escaped': b'{"op":"inspect","\\u006fp":"inspect"}',
    'duplicate_nested': b'{"op":"inspect","x":{"a":1,"a":1}}',
    'duplicate_nested_escaped': b'{"op":"inspect","x":{"a":1,"\\u0061":1}}',
    'malformed': b'{"op":',
    'trailing_json': b'{"op":"inspect"} {}',
    'non_utf8': b'{"op":"\xff"}',
    'non_object': b'[]',
    'unknown_field': b'{"op":"inspect","surprise":true}',
    'unknown_operation': b'{"op":"manager-release"}',
    'missing_handle': b'{"op":"submit","submit":true}',
    'non_boolean_submit': b'{"op":"submit","handle":"made-up","submit":1}',
    'caller_manifest': b'{"op":"submit","handle":"made-up","manifest":{},"submit":true}',
    'unkeyed_mutation': b'{"op":"delete","handle":"made-up"}',
    'oversize_control': b'{"op":"inspect","padding":"' + b'x' * (64 * 1024) + b'"}',
}
for label, data in BAD_INPUTS.items():
    def bad(t, data=data, label=label):
        t.init()
        before = t.inspect()
        t.call(raw=data, ok=False, reason='duplicate_key' if label.startswith('duplicate_') else None)
        t.check(t.inspect() == before, 'rejected direct control leaves collection invariant')
    case('control_' + label)(bad)


@case('prepare_dry_submit_finality')
def submission(t):
    t.init()
    added, _, source = t.add('answer', b'Qualified, partial, non-answer: evidence does not decide this.')
    first = t.prepare('prepare-one')
    second = t.prepare('prepare-two')
    t.check(first['state'] == added['state'], 'preparation does not edit state')
    t.check(first['manifest']['elements'] == added['state']['elements'], 'manifest exact ordered element population')
    for field in ('audit', 'instance', 'revision'):
        t.check(first['manifest'][field] == added['state'][field], 'manifest binds ' + field)
    t.check(first['manifest']['commission_sha256'] == COMMISSION, 'manifest binds independent commission identity')
    t.check(first['handle'] != second['handle'], 'distinct preparations retain distinct issued identity')
    prior = t.snap('before-dry')
    for fields in ({}, {'submit': False}):
        dry = t.call({'op': 'submit', 'handle': first['handle'], **fields})
        t.check(dry.get('dry_run') is True and dry.get('would_submit') is True, 'dry submit reports validated would-submit')
        t.check(dry['state'] == added['state'], 'dry submit leaves exact state invariant')
    t.check(t.snap('after-dry') == prior, 'dry submissions change no store entries or file bytes')
    result = t.call({'op': 'submit', 'handle': first['handle'], 'submit': True})
    t.check(result['dry_run'] is False and result['state']['submitted'] is True, 'explicit true seals answer')
    t.check(result['state']['submission_handle'] == first['handle'], 'fixed result identifies original preparation')
    t.check(t.call({'op': 'submit', 'handle': first['handle'], 'submit': True}) == result,
            'identical confirmed repeat returns same outcome')
    t.call({'op': 'submit', 'handle': second['handle'], 'submit': True}, ok=False, reason='already_submitted')
    requests = [t.request('add', 'late-add', source, source.read_bytes(), name='late'),
                t.request('replace', 'late-replace', source, source.read_bytes(), name='late', handle=added['element']['handle']),
                {'op': 'delete', 'request_id': 'late-delete', 'handle': added['element']['handle']}]
    for req in requests:
        t.call(req, ok=False, reason='already_submitted')
    t.check(t.inspect() == result['state'], 'all post-submit edits leave fixed selection invariant')


@case('prepare_stale_equal_restore')
def stale_equal(t):
    t.init()
    original, _, source = t.add('a', b'equal')
    prepared = t.prepare()
    replacement = t.source('changed', b'different')
    changed = t.call(t.request('replace', 'changed', replacement, b'different', name='answer', handle=original['element']['handle']))
    restored = t.call(t.request('replace', 'restored', source, b'equal', name='answer', handle=changed['element']['handle']))
    t.check(restored['element']['sha256'] == original['element']['sha256'], 'restored bytes equal original witness')
    t.check(restored['state']['revision'] != prepared['state']['revision'], 'equal bytes do not restore revision identity')
    for confirm in (False, True):
        t.call({'op': 'submit', 'handle': prepared['handle'], 'submit': confirm}, ok=False, reason='stale_preparation')
    t.check(t.inspect() == restored['state'], 'stale submission leaves restored current answer invariant')


@case('prepare_cross_audit_forged')
def cross_audit(t):
    t.init()
    t.add('same', b'same bytes')
    prepared = t.prepare()
    other = t.home / 'other-store'
    other.mkdir()
    t.stores.append(other)
    other_state = t.init('audit-b', other)
    other_added, _, _ = t.add('same-other', b'same bytes', store=other)
    t.call({'op': 'submit', 'handle': prepared['handle'], 'submit': True}, store=other, ok=False, reason='invalid_handle')
    t.check(t.inspect(other) == other_added['state'], 'cross-audit handle cannot change equal-byte other audit')
    t.check(other_state['instance'] != prepared['state']['instance'], 'store instances differ')
    t.call({'op': 'submit', 'handle': 'forged-' + digest(encoded(prepared['manifest'])), 'submit': True}, ok=False, reason='invalid_handle')
    t.call({'op': 'read', 'handle': other_added['element']['handle']}, ok=False, reason='invalid_handle')


@case('prepare_empty_selection')
def empty_submission(t):
    initial = t.init()
    prepared = t.prepare()
    t.check(prepared['manifest']['elements'] == [], 'empty exact selection can be prepared')
    dry = t.call({'op': 'submit', 'handle': prepared['handle']})
    t.check(dry['state'] == initial, 'empty dry submit preserves selection')
    sealed = t.call({'op': 'submit', 'handle': prepared['handle'], 'submit': True})
    t.check(sealed['state']['submitted'] and sealed['state']['elements'] == [], 'empty selection explicitly submitted')


for hook in ('after_stage', 'before_publish', 'after_publish', 'after_sync'):
    for action in ('continue', 'kill'):
        def interrupted_edit(t, hook=hook, action=action):
            t.init()
            base, _, _ = t.add('base', b'invariant base')
            data = b'complete new payload\0\xff'
            source = t.source('new', data)
            req = t.request('add', 'interrupted-add', source, data, name='new')
            child = t.start(req, hook=hook)
            t.stopped(child)
            t.send(child, signal.SIGCONT if action == 'continue' else signal.SIGKILL, 'measured barrier ' + action)
            if action == 'continue':
                code, outcome = t.finish(child)
                t.check(code == 0 and outcome.get('ok'), 'SIGCONT firing control completes acknowledged edit')
                committed = True
            else:
                code, _ = t.finish(child, parse=False)
                t.check(code == -signal.SIGKILL, 'actual killed process exit is SIGKILL', code)
                committed = hook in ('after_publish', 'after_sync')
            current = t.inspect()
            t.check(current['revision'] == base['state']['revision'] + int(committed),
                    'complete old-or-new state at observed publication window', current['revision'])
            t.check(len(current['elements']) == (2 if committed else 1), 'no partial membership exposed')
            t.verify_read(current['elements'][0], b'invariant base')
            if committed:
                t.verify_read(current['elements'][1], data)
                source.rename(source.with_name('new.lost'))
                recovered = t.call(req)
                t.check(recovered['state'] == current, 'same request recovers committed lost reply after source loss')
                resolution = t.call({'op': 'resolve', 'request_id': req['request_id']})
                t.check(resolution['status'] == 'committed' and resolution['outcome'] == recovered,
                        'resolution attributes exact original committed outcome')
                t.check(t.inspect() == current, 'resolution creates no duplicate effects')
            else:
                resolution = t.call({'op': 'resolve', 'request_id': req['request_id']})
                t.check(resolution['status'] == 'pending' and resolution['outcome'] is None,
                        'resolution distinguishes pending from committed')
                t.check(t.inspect() == current, 'pending resolve does not publish')
                source.rename(source.with_name('new.lost'))
                t.call({'op': 'resume', 'request_id': req['request_id']})
                resumed = t.inspect()
                t.check(resumed['revision'] == base['state']['revision'] + 1 and len(resumed['elements']) == 2,
                        'explicit same-operation resume completes one planned edit without source')
                t.verify_read(resumed['elements'][1], data)
        case('edit_' + hook + '_' + action)(interrupted_edit)

        def interrupted_submit(t, hook=hook, action=action):
            t.init()
            added, _, source = t.add('answer', b'fixed submission witness')
            prep = t.prepare()
            req = {'op': 'submit', 'handle': prep['handle'], 'submit': True}
            child = t.start(req, hook=hook)
            t.stopped(child)
            t.send(child, signal.SIGCONT if action == 'continue' else signal.SIGKILL, 'measured submission barrier ' + action)
            if action == 'continue':
                code, outcome = t.finish(child)
                t.check(code == 0 and outcome.get('ok'), 'SIGCONT firing control submits successfully')
                committed = True
            else:
                code, _ = t.finish(child, parse=False)
                t.check(code == -signal.SIGKILL, 'submission process actually SIGKILLed')
                committed = hook in ('after_publish', 'after_sync')
            observed = t.inspect()
            t.check(observed['submitted'] is committed, 'submission finality matches observed commit window')
            t.check(observed['elements'] == added['state']['elements'], 'submission preserves exact selected identities')
            source.rename(source.with_name('answer.lost'))
            result = t.call(req)
            t.check(result['state']['submitted'] and result['state']['submission_handle'] == prep['handle'],
                    'same handle completes or recovers one submission after source loss')
            t.check(t.call(req) == result, 'repeated confirmed handle has one stable outcome')
            t.call({'op': 'delete', 'request_id': 'late', 'handle': added['element']['handle']}, ok=False, reason='already_submitted')
        case('submit_' + hook + '_' + action)(interrupted_submit)


@case('pending_cancel_and_changed_key')
def pending_cancel(t):
    t.init()
    base, _, _ = t.add('base', b'base')
    source = t.source('pending', b'pending bytes')
    req = t.request('add', 'pending', source, b'pending bytes', name='pending')
    child = t.start(req, hook='before_publish')
    t.stopped(child)
    t.send(child, signal.SIGKILL, 'pending cancellation specimen')
    t.finish(child, parse=False)
    t.call(dict(req, name='changed'), ok=False, reason='request_conflict')
    cancellation = t.call({'op': 'cancel', 'request_id': 'pending', 'reason': 'independent caller elects to retain uncommitted partials'})
    t.check(cancellation['status'] == 'cancelled' and cancellation['cancellation']['attribution'] == 'caller',
            'cancellation preserves caller attribution')
    t.check(t.inspect() == base['state'], 'cancellation leaves prior answer current')
    t.call({'op': 'resume', 'request_id': 'pending'}, ok=False, reason='request_cancelled')
    t.call(req, ok=False, reason='request_cancelled')
    t.check(t.inspect() == base['state'], 'cancelled operation cannot silently publish later')


@case('committed_cannot_cancel')
def committed_cancel(t):
    t.init()
    result, _, _ = t.add('done', b'committed')
    t.call({'op': 'cancel', 'request_id': 'done', 'reason': 'cannot revoke committed observation'}, ok=False, reason='already_committed')
    t.check(t.inspect() == result['state'], 'cancel cannot reverse a committed edit')


@case('pending_does_not_block_independent_edit')
def pending_independent_edit(t):
    t.init()
    t.add('base', b'base')
    source = t.source('pending', b'pending bytes')
    req = t.request('add', 'pending', source, b'pending bytes', name='pending')
    child = t.start(req, hook='before_publish')
    t.stopped(child)
    t.send(child, signal.SIGKILL, 'independent-edit exception-burden specimen')
    t.finish(child, parse=False)
    partial_before = t.snap('pending-before-independent-edit')
    later, _, _ = t.add('independent', b'unrelated next edit')
    t.check(len(later['state']['elements']) == 2, 'unrelated edit succeeds without resolving pending request')
    t.call({'op': 'resume', 'request_id': 'pending'}, ok=False, reason='stale_request')
    cancellation = t.call({'op': 'cancel', 'request_id': 'pending', 'reason': 'old base superseded by independent edit'})
    t.check(cancellation['status'] == 'cancelled', 'explicit cancel dispositions only superseded pending operation')
    t.check(t.inspect() == later['state'], 'stale resume and cancel preserve independent current selection')
    partial_after = t.snap('pending-after-cancel')
    retained = {name: row for name, row in partial_before.items() if row['kind'] == 'file'}
    t.check(all(partial_after.get(name) == row for name, row in retained.items()),
            'original pending partials and records remain byte-for-byte retained')


def finish_competitor(t, child):
    code, value = t.finish(child)
    t.check((code == 0 and value.get('ok') is True) or
            (code == 2 and value.get('ok') is False), 'contender has structured success or refusal')
    return code, value


@case('race_edit_first_submission_stale')
def race_edit_first(t):
    t.init()
    t.add('base', b'base')
    prep = t.prepare()
    source = t.source('edit', b'edit wins')
    req = t.request('add', 'edit', source, b'edit wins', name='edit')
    first = t.start(req, hook='before_publish')
    t.stopped(first)
    contender = t.start({'op': 'submit', 'handle': prep['handle'], 'submit': True})
    t.send(first, signal.SIGCONT, 'release known edit-first linearization')
    code, value = t.finish(first)
    t.check(code == 0 and value.get('ok'), 'first edit completes')
    _, response = finish_competitor(t, contender)
    t.check(response.get('reason') in ('busy', 'stale_preparation'), 'racing submission cannot seal incompatible selection', response)
    t.call({'op': 'submit', 'handle': prep['handle'], 'submit': True}, ok=False, reason='stale_preparation')
    t.check(not t.inspect()['submitted'], 'edit-first race leaves answer editable')


@case('race_submit_first_edit_refused')
def race_submit_first(t):
    t.init()
    base, _, _ = t.add('base', b'base')
    prep = t.prepare()
    first = t.start({'op': 'submit', 'handle': prep['handle'], 'submit': True}, hook='before_publish')
    t.stopped(first)
    source = t.source('late', b'late edit')
    req = t.request('add', 'late', source, b'late edit', name='late')
    contender = t.start(req)
    t.send(first, signal.SIGCONT, 'release known submit-first linearization')
    code, value = t.finish(first)
    t.check(code == 0 and value.get('ok'), 'first submission completes')
    _, response = finish_competitor(t, contender)
    t.check(response.get('reason') in ('busy', 'already_submitted'), 'racing edit cannot change fixed answer', response)
    t.call(req, ok=False, reason='already_submitted')
    state = t.inspect()
    t.check(state['submitted'] and state['elements'] == base['state']['elements'], 'submit-first exact selection stays fixed')


@case('race_prepare_with_edit')
def race_prepare(t):
    t.init()
    t.add('base', b'base')
    source = t.source('edit', b'coherent second element')
    first = t.start(t.request('add', 'edit', source, b'coherent second element', name='second'), hook='before_publish')
    t.stopped(first)
    contender = t.start({'op': 'prepare', 'request_id': 'racing-prepare'})
    t.send(first, signal.SIGCONT, 'release edit while prepare contends')
    t.finish(first)
    code, response = finish_competitor(t, contender)
    if code == 2:
        t.check(response.get('reason') == 'busy', 'overlapping prepare refusal is busy')
        response = t.prepare('racing-prepare')
    current = t.inspect()
    t.check(response['manifest']['elements'] == current['elements'], 'prepare sees one coherent exact collection')
    t.check(response['manifest']['revision'] == current['revision'], 'prepare revision matches coherent population')


@case('race_competing_replacements')
def race_replacements(t):
    t.init()
    base, _, _ = t.add('base', b'original')
    a = t.source('first', b'first replacement')
    b = t.source('second', b'second replacement')
    req_a = t.request('replace', 'first', a, b'first replacement', name='first', handle=base['element']['handle'])
    req_b = t.request('replace', 'second', b, b'second replacement', name='second', handle=base['element']['handle'])
    first = t.start(req_a, hook='before_publish')
    t.stopped(first)
    contender = t.start(req_b)
    t.send(first, signal.SIGCONT, 'release first replacement')
    code, result = t.finish(first)
    t.check(code == 0 and result.get('ok'), 'first version-bound replacement wins')
    _, response = finish_competitor(t, contender)
    t.check(response.get('reason') in ('busy', 'stale_handle'), 'second incompatible replacement cannot also succeed')
    t.call(req_b, ok=False, reason='stale_handle')
    t.check(t.inspect() == result['state'], 'replacement contention exposes one complete winner')
    t.verify_read(result['element'], b'first replacement')


@case('contention_observed_while_holder_stopped')
def observed_contention(t):
    t.init()
    source = t.source('held', b'held edit')
    req = t.request('add', 'held', source, b'held edit', name='held')
    holder = t.start(req, hook='before_publish')
    t.stopped(holder)
    other = t.source('other', b'other edit')
    contender = t.request('add', 'other', other, b'other edit', name='other')
    for request in ({'op': 'inspect'}, {'op': 'prepare', 'request_id': 'contending-preparation'}, contender):
        t.call(request, ok=False, reason='busy')
    t.check(holder['process'].poll() is None, 'holder remains stopped/alive through completed busy outcomes')
    t.send(holder, signal.SIGCONT, 'release only after competing requests returned busy')
    code, result = t.finish(holder)
    t.check(code == 0 and result.get('ok'), 'held operation completes after contention evidence')
    later = t.call(contender)
    t.check(len(later['state']['elements']) == 2, 'busy request can independently succeed after holder releases lock')


@case('writer_identity_read_refusal_invariance')
def writer_identity(t):
    t.init()
    added, original, source = t.add('original', b'exact original writer payload')
    prepared = t.prepare()
    other = t.h.other_binary
    t.check(other is not None and digest(other.read_bytes()) != digest(t.h.binary.read_bytes()),
            'other writer is a distinct valid recorded binary')
    current = t.call({'op': 'inspect'}, binary=other)['state']
    t.check(current == added['state'], 'distinct writer may inspect verified state')
    read = t.call({'op': 'read', 'handle': added['element']['handle']}, binary=other)
    t.check(read['bytes_hex'] == b'exact original writer payload'.hex(), 'distinct writer read preserves verified exact bytes')
    resolved = t.call({'op': 'resolve', 'request_id': 'original'}, binary=other)
    t.check(resolved['status'] == 'committed' and resolved['outcome'] == added, 'distinct writer resolves existing verified outcome')
    before = t.snap('before-other-writer')
    for req in (original, t.request('add', 'changed-writer-add', source, source.read_bytes(), name='other'),
                {'op': 'prepare', 'request_id': 'changed-writer-prepare'},
                {'op': 'resume', 'request_id': 'original'},
                {'op': 'cancel', 'request_id': 'original', 'reason': 'different implementation'},
                {'op': 'submit', 'handle': prepared['handle'], 'submit': True}):
        t.call(req, binary=other, ok=False, reason='writer_mismatch')
    t.check(t.snap('after-other-writer') == before, 'changed-writer refusals mutate no store bytes')
    accepted, _, _ = t.add('same-writer-control', b'original writer remains functional')
    t.check(len(accepted['state']['elements']) == 2, 'byte-identical copied original writer still mutates')


@case('control_unknown_fields_all_operations')
def unknown_all(t):
    t.init()
    added, original, source = t.add('base', b'base')
    prepared = t.prepare()
    inputs = [
        {'op': 'init', 'audit': 'audit-a', 'commission_sha256': COMMISSION, 'request_id': 'another-init'},
        t.request('add', 'unknown-add', source, b'base', name='base'),
        t.request('replace', 'unknown-replace', source, b'base', name='base', handle=added['element']['handle']),
        {'op': 'delete', 'request_id': 'unknown-delete', 'handle': added['element']['handle']},
        {'op': 'inspect'}, {'op': 'read', 'handle': added['element']['handle']},
        {'op': 'prepare', 'request_id': 'unknown-prepare'},
        {'op': 'submit', 'handle': prepared['handle']},
        {'op': 'submit', 'handle': prepared['handle'], 'submit': True},
        {'op': 'resolve', 'request_id': 'base'}, {'op': 'resume', 'request_id': 'base'},
        {'op': 'cancel', 'request_id': 'base', 'reason': 'unknown field should refuse before disposition'},
    ]
    before = t.snap('before-unknown-fields')
    for req in inputs:
        response = t.call(dict(req, surprise=True), ok=False)
        t.check('unknown' in response['message'].lower(), 'unknown-field diagnosis identifies schema cause')
    t.check(t.snap('after-unknown-fields') == before, 'unknown controls across every operation change no store bytes')


def planned_blob(t, request_id):
    """Only published README layout coordinates; no implementation imports."""
    path = t.store / ('request-' + digest(request_id.encode()) + '.json')
    raw = path.read_bytes()
    record(t.witnesses / ('layout-' + request_id + '.json'),
           {'path': str(path), 'sha256': digest(raw), 'authority': 'implementer README physical layout'})
    exclusive(t.witnesses / ('request-' + request_id + '.original.bin'), raw)
    binding = json.loads(raw)
    name = binding['blob']['name']
    t.check(Path(name).name == name, 'published blob coordinate is a single store member')
    return t.store / name


@case('corrupt_held_payload')
def corrupt_payload(t):
    t.init()
    added, _, _ = t.add('answer', b'uncorrupted live source remains')
    prep = t.prepare()
    blob = planned_blob(t, 'answer')
    original = blob.read_bytes()
    exclusive(t.witnesses / 'held-payload-before.bin', original)
    blob.write_bytes(b'CORRUPTED held bytes')
    record(t.dir / 'CORRUPTION.json', {'at': now(), 'path': str(blob),
           'before': digest(original), 'after': digest(blob.read_bytes()),
           'scope': 'owned specimen only; original and live source retained; never repaired'})
    for req in ({'op': 'inspect'}, {'op': 'read', 'handle': added['element']['handle']},
                {'op': 'prepare', 'request_id': 'damaged-prepare'},
                {'op': 'submit', 'handle': prep['handle'], 'submit': True}):
        t.call(req, ok=False, reason='integrity_error')
    t.check(blob.read_bytes() == b'CORRUPTED held bytes', 'live source never silently repairs damaged held payload')


@case('missing_held_payload')
def missing_payload(t):
    t.init()
    t.add('answer', b'missing held payload')
    prep = t.prepare()
    blob = planned_blob(t, 'answer')
    retained = t.witnesses / 'held-payload-renamed.bin'
    blob.rename(retained)
    record(t.dir / 'SOURCE-LOSS.json', {'at': now(), 'from': str(blob), 'retained': str(retained)})
    t.call({'op': 'submit', 'handle': prep['handle'], 'submit': True}, ok=False, reason='integrity_error')
    t.check(not blob.exists(), 'missing held file is not repaired from live source')


@case('corrupt_preparation_issuance')
def corrupt_preparation(t):
    t.init()
    added, _, _ = t.add('answer', b'held unchanged')
    prep = t.prepare()
    target = t.store / ('prepare-' + prep['handle'] + '.json')
    raw = target.read_bytes()
    exclusive(t.witnesses / 'preparation-before.bin', raw)
    target.write_bytes(b'{"damaged":true}')
    record(t.dir / 'CORRUPTION.json', {'path': str(target), 'before': digest(raw), 'after': digest(target.read_bytes())})
    t.call({'op': 'submit', 'handle': prep['handle'], 'submit': True}, ok=False, reason='integrity_error')
    for op in ('resolve', 'resume', 'cancel'):
        req = {'op': op, 'request_id': 'prepare'}
        if op == 'cancel':
            req['reason'] = 'damaged own issuance is not cancellation authority'
        t.call(req, ok=False, reason='integrity_error')
    t.check(not t.inspect()['submitted'], 'damaged issued record is not accepted as submitted')
    t.verify_read(added['element'], b'held unchanged')
    later, _, _ = t.add('independent-later', b'editing remains available')
    t.check(later['state']['elements'][0] == added['element'],
            'unsubmitted issuance damage does not impose dependency on independent answer edits')


@case('stale_unsubmitted_preparation_corruption_invariance')
def stale_issuance(t):
    t.init()
    t.add('answer', b'initial answer')
    prep = t.prepare('old-preparation')
    later, _, _ = t.add('later', b'later independent selection')
    target = t.store / ('prepare-' + prep['handle'] + '.json')
    raw = target.read_bytes()
    exclusive(t.witnesses / 'stale-issuance-before.bin', raw)
    target.write_bytes(b'{"damaged":true}')
    record(t.dir / 'CORRUPTION.json', {'path': str(target), 'before': digest(raw),
           'after': digest(target.read_bytes()), 'scope': 'stale unsubmitted issuance'})
    t.check(t.inspect() == later['state'], 'stale unsubmitted issuance is not a dependency of current inspection')
    t.verify_read(later['element'], b'later independent selection')
    t.call({'op': 'submit', 'handle': prep['handle'], 'submit': True}, ok=False, reason='integrity_error')
    t.call({'op': 'resolve', 'request_id': 'old-preparation'}, ok=False, reason='integrity_error')
    next_edit, _, _ = t.add('next', b'next independent element')
    t.check(next_edit['state']['elements'][:2] == later['state']['elements'],
            'fresh edit preserves prior elements despite unrelated stale issuance damage')


@case('submitted_preparation_corruption_refused')
def submitted_issuance(t):
    t.init()
    added, _, _ = t.add('answer', b'fixed exact result')
    prep = t.prepare('chosen-preparation')
    t.call({'op': 'submit', 'handle': prep['handle'], 'submit': True})
    target = t.store / ('prepare-' + prep['handle'] + '.json')
    raw = target.read_bytes()
    exclusive(t.witnesses / 'chosen-issuance-before.bin', raw)
    target.write_bytes(b'{"damaged":true}')
    record(t.dir / 'CORRUPTION.json', {'path': str(target), 'before': digest(raw),
           'after': digest(target.read_bytes()), 'scope': 'chosen issuance of submitted fixed result'})
    for req in ({'op': 'inspect'}, {'op': 'read', 'handle': added['element']['handle']},
                {'op': 'resolve', 'request_id': prep['handle']},
                {'op': 'submit', 'handle': prep['handle'], 'submit': True}):
        t.call(req, ok=False, reason='integrity_error')


for duplicate in ('top_escaped', 'nested'):
    def corrupt_request(t, duplicate=duplicate):
        t.init()
        source = t.source('pending', b'pending')
        req = t.request('add', 'pending', source, b'pending', name='pending')
        child = t.start(req, hook='before_publish')
        t.stopped(child)
        t.send(child, signal.SIGKILL, 'retained pending request corruption specimen')
        t.finish(child, parse=False)
        target = t.store / ('request-' + digest(b'pending') + '.json')
        raw = target.read_bytes()
        exclusive(t.witnesses / 'request-before.bin', raw)
        value = json.loads(raw)
        if duplicate == 'top_escaped':
            damaged = b'{"request_\\u0069d":"pending",' + raw.lstrip()[1:]
        else:
            needle = json.dumps(value['intent'], separators=(',', ':'), sort_keys=True)
            value['intent'] = {'op': 'placeholder'}
            compact = json.dumps(value, separators=(',', ':'), sort_keys=True)
            duplicated_intent = '{"op":' + json.dumps(req['op']) + ',' + needle[1:]
            damaged = compact.replace('{"op":"placeholder"}', duplicated_intent).encode()
        target.write_bytes(damaged)
        record(t.dir / 'CORRUPTION.json', {'path': str(target), 'kind': duplicate,
               'before': digest(raw), 'after': digest(damaged)})
        for op in ('resolve', 'resume', 'cancel'):
            request = {'op': op, 'request_id': 'pending'}
            if op == 'cancel':
                request['reason'] = 'damaged must not become missing'
            refusal = t.call(request, ok=False, reason='integrity_error')
            t.check('duplicate_key' in refusal['message'], 'record duplicate diagnostic survives integrity attribution')
    case('corrupt_request_duplicate_' + duplicate)(corrupt_request)


@case('corrupt_committed_record')
def corrupt_commit(t):
    t.init()
    result, req, _ = t.add('answer', b'committed witness')
    binding = json.loads((t.store / ('request-' + digest(b'answer') + '.json')).read_bytes())
    target = t.store / binding['commit_name']
    raw = target.read_bytes()
    exclusive(t.witnesses / 'commit-before.bin', raw)
    target.write_bytes(b'{"damaged":true}')
    record(t.dir / 'CORRUPTION.json', {'path': str(target), 'before': digest(raw), 'after': digest(target.read_bytes())})
    t.call({'op': 'inspect'}, ok=False, reason='integrity_error')
    t.call({'op': 'resolve', 'request_id': 'answer'}, ok=False, reason='integrity_error')
    t.call(req, ok=False, reason='integrity_error')


@case('missing_acknowledged_commit')
def missing_commit(t):
    t.init()
    t.add('answer', b'acknowledged selected bytes')
    binding = json.loads((t.store / ('request-' + digest(b'answer') + '.json')).read_bytes())
    target = t.store / binding['commit_name']
    retained = t.witnesses / 'acknowledged-commit-renamed.bin'
    target.rename(retained)
    record(t.dir / 'CORRUPTION.json', {'at': now(), 'missing': str(target),
           'retained': str(retained), 'sha256': digest(retained.read_bytes()),
           'scope': 'one acknowledged publication missing; no record repaired'})
    for req in ({'op': 'inspect'}, {'op': 'resolve', 'request_id': 'answer'},
                {'op': 'resume', 'request_id': 'answer'},
                {'op': 'cancel', 'request_id': 'answer', 'reason': 'must not erase acknowledged uncertainty'}):
        t.call(req, ok=False, reason='integrity_error')
    t.check(not target.exists(), 'missing authoritative commit is never silently restored from staging')


@case('missing_acknowledged_preparation')
def missing_preparation(t):
    t.init()
    t.add('answer', b'held')
    prep = t.prepare('issued')
    target = t.store / ('prepare-' + prep['handle'] + '.json')
    retained = t.witnesses / 'acknowledged-issuance-renamed.bin'
    target.rename(retained)
    record(t.dir / 'CORRUPTION.json', {'missing': str(target), 'retained': str(retained),
           'sha256': digest(retained.read_bytes())})
    for req in ({'op': 'resolve', 'request_id': 'issued'}, {'op': 'resume', 'request_id': 'issued'},
                {'op': 'cancel', 'request_id': 'issued', 'reason': 'missing acknowledged issuance'}):
        t.call(req, ok=False, reason='integrity_error')
    t.check(not target.exists(), 'missing acknowledged issuance never becomes a new preparation')


@case('corrupt_pending_plan_semantics')
def corrupt_pending_plan(t):
    t.init()
    source = t.source('pending', b'pending inconsistent plan')
    req = t.request('add', 'pending', source, b'pending inconsistent plan', name='pending')
    child = t.start(req, hook='before_publish')
    t.stopped(child)
    t.send(child, signal.SIGKILL, 'pending semantic-integrity specimen')
    t.finish(child, parse=False)
    target = t.store / ('request-' + digest(b'pending') + '.json')
    raw = target.read_bytes()
    exclusive(t.witnesses / 'pending-plan-before.bin', raw)
    value = json.loads(raw)
    value['candidate']['revision'] += 100
    target.write_bytes(encoded(value))
    record(t.dir / 'CORRUPTION.json', {'path': str(target), 'before': digest(raw),
           'after': digest(target.read_bytes()), 'change': 'candidate revision cannot follow recorded predecessor'})
    for op in ('resolve', 'resume', 'cancel'):
        req = {'op': op, 'request_id': 'pending'}
        if op == 'cancel':
            req['reason'] = 'invalid plan is not permission for attributed cancellation'
        t.call(req, ok=False, reason='integrity_error')


@case('pending_unplanned_equal_bytes_not_adopted')
def no_unplanned_adoption(t):
    t.init()
    base, _, _ = t.add('base', b'invariant prior selection')
    data = b'UNIQUE pending raw payload witness\x00\xff'
    source = t.source('pending', data)
    req = t.request('add', 'pending', source, data, name='pending')
    child = t.start(req, hook='after_stage')
    t.stopped(child)
    t.send(child, signal.SIGKILL, 'remove availability of only this pending request planned bytes')
    t.finish(child, parse=False)
    removed_coordinates = []
    for path in sorted(t.store.iterdir()):
        if path.is_file() and (path.name.startswith('blob-') or path.name.startswith('stage-')) and path.read_bytes() == data:
            retained = t.witnesses / ('unavailable-' + path.name)
            path.rename(retained)
            removed_coordinates.append({'from': str(path), 'retained': str(retained), 'sha256': digest(data)})
    t.check(len(removed_coordinates) >= 1, 'held/staged pending bytes were independently observed and retained outside store')
    source.rename(source.with_name('pending.source-unavailable'))
    unrelated = t.store / ('blob-' + '0' * 32 + '.bin')
    exclusive(unrelated, data)
    record(t.dir / 'UNAVAILABILITY.json', {'at': now(), 'planned_byte_locations_retained': removed_coordinates,
           'unplanned_equal_bytes': str(unrelated), 'source_renamed': True})
    t.call({'op': 'resume', 'request_id': 'pending'}, ok=False)
    t.check(t.inspect() == base['state'], 'equal bytes at an unplanned coordinate cannot substitute for own planned outputs')
    cancelled = t.call({'op': 'cancel', 'request_id': 'pending', 'reason': 'own planned bytes unavailable'})
    t.check(cancelled['status'] == 'cancelled', 'caller can disposition lost-byte pending operation without repair')
    t.check(unrelated.read_bytes() == data, 'unrelated matching bytes remain independent and untouched')


@case('source_symlink_and_special_refused')
def special_sources(t):
    t.init()
    base, _, source = t.add('base', b'ordinary source')
    link = t.sources / 'source-link'
    link.symlink_to(source)
    fifo = t.sources / 'source-fifo'
    os.mkfifo(fifo)
    for name, path in (('link', link), ('fifo', fifo)):
        t.call(t.request('add', name, path, b'ordinary source', name=name), ok=False)
    t.check(t.inspect() == base['state'], 'unsafe source types cannot alter current collection')


@case('attempt_unrelated_corruption_invariance')
def unrelated_attempt(t):
    t.init()
    base, _, _ = t.add('base', b'invariant current bytes')
    attempts = sorted(t.store.glob('attempt-' + digest(b'init') + '-*.json'))
    t.check(bool(attempts), 'published request-scoped init attempt coordinate exists')
    target = attempts[0]
    raw = target.read_bytes()
    exclusive(t.witnesses / 'unrelated-attempt-before.bin', raw)
    target.write_bytes(b'{"malformed unrelated retained attempt":')
    record(t.dir / 'CORRUPTION.json', {'path': str(target), 'request_id': 'init',
           'before': digest(raw), 'after': digest(target.read_bytes()),
           'scope': 'unrelated historical attempt only; raw failure remains'})
    t.check(t.inspect() == base['state'], 'unrelated attempt damage leaves supported current inspection invariant')
    t.verify_read(base['element'], b'invariant current bytes')
    new, _, _ = t.add('independent', b'independent later answer element')
    t.check(new['state']['elements'][0] == base['element'] and len(new['state']['elements']) == 2,
            'new edit succeeds without repairing or disposing unrelated damaged attempt')
    t.check(target.read_bytes() == b'{"malformed unrelated retained attempt":',
            'unrelated malformed evidence remains untouched')


@case('attempt_relevant_corruption_refused')
def relevant_attempt(t):
    t.init()
    source = t.source('pending', b'pending relevant attempt bytes')
    req = t.request('add', 'pending', source, b'pending relevant attempt bytes', name='pending')
    child = t.start(req, hook='before_publish')
    t.stopped(child)
    t.send(child, signal.SIGKILL, 'relevant attempt corruption control')
    t.finish(child, parse=False)
    attempts = sorted(t.store.glob('attempt-' + digest(b'pending') + '-*.json'))
    t.check(bool(attempts), 'published request-scoped pending attempt coordinate exists')
    target = attempts[0]
    raw = target.read_bytes()
    exclusive(t.witnesses / 'relevant-attempt-before.bin', raw)
    target.write_bytes(b'{"malformed relevant retained attempt":')
    record(t.dir / 'CORRUPTION.json', {'path': str(target), 'request_id': 'pending',
           'before': digest(raw), 'after': digest(target.read_bytes())})
    t.call({'op': 'resume', 'request_id': 'pending'}, ok=False, reason='integrity_error')
    t.check(target.read_bytes() == b'{"malformed relevant retained attempt":',
            'relevant damaged attempt keeps its diagnostic bytes')


for operation, hook in (('replace', 'before_publish'), ('replace', 'after_publish'),
                        ('delete', 'before_publish'), ('delete', 'after_sync')):
    def interrupted_other_edit(t, operation=operation, hook=hook):
        t.init()
        base, _, _ = t.add('base', b'old exact bytes')
        if operation == 'replace':
            source = t.source('replacement', b'new exact bytes')
            req = t.request('replace', 'changing', source, b'new exact bytes', name='replaced', handle=base['element']['handle'])
        else:
            req = {'op': 'delete', 'request_id': 'changing', 'handle': base['element']['handle']}
        child = t.start(req, hook=hook)
        t.stopped(child)
        t.send(child, signal.SIGKILL, 'other edit publication comparison')
        code, _ = t.finish(child, parse=False)
        t.check(code == -signal.SIGKILL, 'observed SIGKILL exit for edit')
        old = hook == 'before_publish'
        state = t.inspect()
        if old:
            t.check(state == base['state'], 'before publication exact old selection remains current')
            t.verify_read(base['element'], b'old exact bytes')
        else:
            t.check(state['revision'] == base['state']['revision'] + 1, 'after publication complete edit revision visible')
        result = t.call({'op': 'resume', 'request_id': 'changing'})
        current = t.inspect()
        t.check(current == result['state'], 'same-operation resume identifies complete current result')
        if operation == 'replace':
            t.verify_read(current['elements'][0], b'new exact bytes')
        else:
            t.check(current['elements'] == [], 'committed deletion exposes complete empty population')
    case(operation + '_' + hook + '_kill')(interrupted_other_edit)


class Harness:
    def __init__(self, args, selectors):
        self.evidence = Path(args.evidence).absolute()
        self.evidence.mkdir(parents=True, exist_ok=False)
        self.work = Path(tempfile.mkdtemp(prefix='stewart-submission-driver-', dir='/private/tmp')).resolve()
        self.binary = self.evidence / 'tested-binary'
        original = Path(args.binary).resolve(strict=True)
        shutil.copyfile(original, self.binary)
        self.binary.chmod(0o700)
        exclusive(self.evidence / 'driver-source.py', Path(__file__).read_bytes())
        self.other_binary = None
        if args.other_binary:
            other_source = Path(args.other_binary).resolve(strict=True)
            self.other_binary = self.evidence / 'other-tested-binary'
            shutil.copyfile(other_source, self.other_binary)
            self.other_binary.chmod(0o700)
            record(self.evidence / 'OTHER-BINARY.json', {'source': str(other_source),
                   'copy': str(self.other_binary), 'sha256': digest(self.other_binary.read_bytes()),
                   'size': self.other_binary.stat().st_size})
        self.assertions = 0
        self.invocations = 0
        self.results = []
        info = self.work.stat()
        record(self.evidence / 'START.json', {'at': now(), 'argv': sys.argv, 'pid': os.getpid(),
               'cwd': os.getcwd(), 'python': sys.version, 'executable': sys.executable,
               'platform': platform.platform(), 'machine': platform.machine(),
               'driver': str(Path(__file__).resolve()), 'driver_sha256': digest(Path(__file__).read_bytes()),
               'binary_source': str(original), 'binary_copy': str(self.binary),
               'binary_sha256': digest(self.binary.read_bytes()), 'binary_size': self.binary.stat().st_size,
               'working_tree': str(self.work), 'working_tree_device': info.st_dev,
               'working_tree_inode': info.st_ino, 'selected_cases': selectors,
               'retention': 'all stores, streams, raw witnesses and failures retained; no removal',
               'scope': 'local procedural prototype comparisons; no production/harness qualification'})

    def run(self, name):
        print('START ' + name, flush=True)
        trial = Trial(self, name)
        started = time.monotonic()
        error = None
        try:
            CASES[name](trial)
        except Exception:
            error = traceback.format_exc()
            exclusive(trial.dir / 'FAILURE.txt', error.encode())
        finally:
            try:
                trial.close()
            except Exception:
                close_error = traceback.format_exc()
                exclusive(trial.dir / 'CLOSE-FAILURE.txt', close_error.encode())
                error = (error or '') + close_error
        result = {'case': name, 'passed': error is None, 'assertions': trial.assertions,
                  'invocations': trial.n, 'seconds': time.monotonic() - started,
                  'evidence': str(trial.dir), 'store': str(trial.store), 'error': error}
        record(trial.dir / 'RESULT.json', result)
        self.results.append(result)
        print(('PASS ' if error is None else 'FAIL ') + name + f' ({trial.assertions} assertions, {trial.n} invocations)', flush=True)
        if error:
            print(error, file=sys.stderr, flush=True)

    def finish(self):
        passed = sum(r['passed'] for r in self.results)
        result = {'at': now(), 'selected_cases': len(self.results), 'passed_cases': passed,
                  'failed_cases': len(self.results) - passed, 'assertions': self.assertions,
                  'invocations': self.invocations, 'cases': self.results,
                  'working_tree': str(self.work), 'working_inventory': snapshot(self.work),
                  'qualification': 'local procedural prototype only; no production custody, power-loss durability, confinement, delivery, termination, reclamation, close, Linux/WSL or Python validation'}
        record(self.evidence / 'RESULT.json', result)
        print(json.dumps({key: result[key] for key in ('selected_cases', 'passed_cases', 'failed_cases', 'assertions', 'invocations', 'working_tree')}, sort_keys=True), flush=True)
        return 0 if passed == len(self.results) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog='All evidence is retained. This is a development prototype comparison, not production qualification.')
    parser.add_argument('--binary', help='absolute ready prototype executable; copied and hashed')
    parser.add_argument('--evidence', help='new directory for this invocation; must not exist')
    parser.add_argument('--other-binary', help='distinct valid build for explicit writer_identity_read_refusal_invariance selector')
    parser.add_argument('--only', action='append', metavar='SELECTOR', help='exact case selector; repeatable')
    parser.add_argument('--list', action='store_true', help='print exact independent case selectors without running')
    args = parser.parse_args()
    if args.list:
        print('\n'.join(CASES))
        return 0
    if not args.binary or not args.evidence:
        parser.error('--binary and --evidence are required unless --list is used')
    selectors = args.only or [name for name in CASES if name != 'writer_identity_read_refusal_invariance' or args.other_binary]
    if len(set(selectors)) != len(selectors) or any(name not in CASES for name in selectors):
        parser.error('selectors must name distinct known cases; use --list')
    if 'writer_identity_read_refusal_invariance' in selectors and not args.other_binary:
        parser.error('writer_identity_read_refusal_invariance requires --other-binary')
    harness = Harness(args, selectors)
    for name in selectors:
        harness.run(name)
    return harness.finish()


if __name__ == '__main__':
    raise SystemExit(main())
