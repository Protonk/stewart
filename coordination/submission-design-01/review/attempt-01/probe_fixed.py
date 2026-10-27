"""Finite independent fixed-candidate review probes. Keep all specimens and witnesses."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path('/Users/raccoon/Desktop/Experiments/stewart')
OUT = ROOT / '.scratch/submission-prototype-01/review/probe-fixed-01'
PIN = ROOT / '.scratch/submission-prototype-01/REVIEW-INPUTS-02.json'
OUT.mkdir()
PINS = json.loads(PIN.read_text())
BINARY = Path(PINS['binaries'][0]['path'])
checks = []
for item in PINS['inputs']:
    actual = hashlib.sha256((ROOT / item['snapshot']).read_bytes()).hexdigest()
    checks.append({'path': item['snapshot'], 'expected': item['sha256'], 'actual': actual, 'ok': actual == item['sha256']})
actual = hashlib.sha256(BINARY.read_bytes()).hexdigest()
checks.append({'path': str(BINARY), 'expected': PINS['binaries'][0]['sha256'], 'actual': actual, 'ok': actual == PINS['binaries'][0]['sha256']})
(OUT / 'pins.json').write_text(json.dumps(checks, indent=2) + '\n')
assert all(x['ok'] for x in checks)
WORK = Path(tempfile.mkdtemp(prefix='stewart-submission-review-', dir='/private/tmp'))
CWD = WORK / 'unrelated' / 'nested'
CWD.mkdir(parents=True)
COUNT = 0
OBS = []
LIVE = []

def write_json(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2)
        f.write('\n')

write_json(OUT / 'START.json', {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'pid': os.getpid(), 'argv': sys.argv, 'cwd': str(Path.cwd()), 'work': str(WORK), 'binary': str(BINARY), 'binary_sha256': actual, 'grant': 'at most 24 invocations; frozen fixed primary binary only; retained reviewer stores; no deletion'})

def snapshot(store, label):
    dest = OUT / 'snapshots' / label
    dest.mkdir(parents=True)
    entries = []
    for path in sorted(store.iterdir()):
        stat = path.lstat()
        raw = path.read_bytes()
        (dest / path.name).write_bytes(raw)
        entries.append({'name': path.name, 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'dev': stat.st_dev, 'ino': stat.st_ino})
    write_json(dest / 'SNAPSHOT.json', {'store': str(store), 'entries': entries})

def invoke(store, request, hook=None):
    global COUNT
    COUNT += 1
    assert COUNT <= 24
    dest = OUT / 'commands' / f'{COUNT:03d}'
    dest.mkdir(parents=True)
    raw = json.dumps(request, separators=(',', ':')).encode()
    (dest / 'stdin.bin').write_bytes(raw)
    env = {k: v for k, v in os.environ.items() if k != 'STEWART_PROTO_PAUSE'}
    if hook:
        env['STEWART_PROTO_PAUSE'] = hook
    argv = [str(BINARY), '--store', str(store)]
    stdout = (dest / 'stdout.bin').open('xb')
    stderr = (dest / 'stderr.bin').open('xb')
    process = subprocess.Popen(argv, cwd=CWD, env=env, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
    LIVE.append(process)
    write_json(dest / 'START.json', {'argv': argv, 'cwd': str(CWD), 'pid': process.pid, 'request': request, 'hook': hook, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    process.stdin.write(raw)
    process.stdin.close()
    if hook:
        deadline = time.monotonic() + 15
        stopped = None
        marker = None
        while time.monotonic() < deadline:
            data = (dest / 'stderr.bin').read_bytes()
            if data:
                marker = json.loads(data.splitlines()[0])
            pid, status = os.waitpid(process.pid, os.WNOHANG | os.WUNTRACED)
            if pid and os.WIFSTOPPED(status):
                stopped = {'pid': pid, 'status': status, 'signal': os.WSTOPSIG(status)}
                break
            if pid:
                raise RuntimeError(f'Process exited before stop: {pid}, {status}')
            time.sleep(0.01)
        assert marker and marker['hook'] == hook and stopped and stopped['signal'] == signal.SIGSTOP
        write_json(dest / 'BARRIER.json', {'marker': marker, 'kernel_stop': stopped})
        snapshot(store, f'{COUNT:03d}-stopped')
        os.kill(process.pid, signal.SIGKILL)
        write_json(dest / 'SIGNAL.json', {'pid': process.pid, 'signal': signal.SIGKILL, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    code = process.wait(timeout=15)
    stdout.close()
    stderr.close()
    out = (dest / 'stdout.bin').read_bytes()
    result = json.loads(out) if out else None
    write_json(dest / 'EXIT.json', {'pid': process.pid, 'exit_code': code, 'result': result})
    LIVE.remove(process)
    OBS.append({'invocation': COUNT, 'store': str(store), 'request': request, 'exit_code': code, 'result': result})
    print(json.dumps(OBS[-1]), flush=True)
    return result

def fresh(name):
    store = WORK / name
    store.mkdir()
    return store

def clone(base, name):
    store = WORK / name
    shutil.copytree(base, store)
    return store

def corrupt(path, replacement, label):
    witness = OUT / 'corruption-witnesses'
    witness.mkdir(exist_ok=True)
    previous = witness / (label + '.original')
    path.rename(previous)
    with path.open('xb') as f:
        f.write(replacement)
    write_json(witness / (label + '.json'), {'path': str(path), 'retained_original': str(previous), 'replacement_sha256': hashlib.sha256(replacement).hexdigest()})

try:
    source = WORK / 'source.bin'
    payload = b'Fixed-candidate independent bytes\x00\xff\n'
    source.write_bytes(payload)
    (OUT / 'source.witness.bin').write_bytes(payload)
    add = {'op': 'add', 'request_id': 'answer-a', 'name': 'answer', 'source': str(source), 'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
    base = fresh('base')
    invoke(base, {'op': 'init', 'audit': 'review-a', 'commission_sha256': '0' * 64, 'request_id': 'init-a'})
    initial = invoke(base, add)
    assert initial['ok']
    snapshot(base, 'base')
    intact = clone(base, 'intact-control')
    good = invoke(intact, {**add, 'request_id': 'answer-b'})
    assert good['ok'] and good['state']['revision'] == 2

    # R3 correction: irrelevant malformed attempt no longer blocks a new edit.
    damaged = clone(base, 'unrelated-attempt-damaged')
    init_ref = 'request-' + hashlib.sha256(b'init-a').hexdigest() + '.json'
    old_attempt = next(path for path in damaged.glob('attempt-*.json') if json.loads(path.read_bytes())['request']['name'] == init_ref)
    corrupt(old_attempt, b'{"schema":"prototype-attempt-v1","schema":"prototype-attempt-v1"}', 'unrelated-init-attempt')
    continued = invoke(damaged, {**add, 'request_id': 'answer-b'})
    read = invoke(damaged, {'op': 'read', 'handle': initial['element']['handle']})
    state = invoke(damaged, {'op': 'inspect'})
    assert continued['ok'] and continued['state']['revision'] == 2 and bytes.fromhex(read['bytes_hex']) == payload and state['state'] == continued['state']
    snapshot(damaged, 'unrelated-attempt-final')

    # Relevant corruption control: a selected same-request attempt still refuses.
    pending = clone(base, 'pending-relevant-attempt')
    invoke(pending, {**add, 'request_id': 'pending-b'}, hook='after_stage')
    invalid_plan = clone(pending, 'pending-plan-damaged')
    pending_ref = 'request-' + hashlib.sha256(b'pending-b').hexdigest() + '.json'
    own_attempt = next(path for path in pending.glob('attempt-*.json') if json.loads(path.read_bytes())['request']['name'] == pending_ref)
    corrupt(own_attempt, b'{"schema":"prototype-attempt-v1","schema":"prototype-attempt-v1"}', 'relevant-pending-attempt')
    refused = invoke(pending, {'op': 'resume', 'request_id': 'pending-b'})
    unchanged = invoke(pending, {'op': 'inspect'})
    assert refused['reason'] == 'integrity_error' and unchanged['state'] == initial['state']
    snapshot(pending, 'relevant-attempt-final')

    # R2 correction: schema-valid but invalid planned transition remains diagnostic.
    request_path = invalid_plan / pending_ref
    plan = json.loads(request_path.read_bytes())
    plan['candidate']['audit'] = 'foreign-audit'
    corrupt(request_path, json.dumps(plan, separators=(',', ':')).encode(), 'pending-plan-audit')
    for op in ('resolve', 'cancel', 'resume'):
        req = {'op': op, 'request_id': 'pending-b'}
        if op == 'cancel':
            req['reason'] = 'Review must not disposition an invalid transition'
        result = invoke(invalid_plan, req)
        assert result['reason'] == 'integrity_error'
    snapshot(invalid_plan, 'pending-plan-final')

    # R1 correction: missing acknowledged tail cannot regress or become cancellable.
    missing = clone(base, 'acknowledged-tail-missing')
    commit = sorted(missing.glob('commit-*.json'))[-1]
    retained = OUT / 'acknowledged-tail.original.json'
    commit.rename(retained)
    write_json(OUT / 'tail-move.json', {'original': str(commit), 'retained': str(retained)})
    for req in ({'op': 'resolve', 'request_id': 'answer-a'}, {'op': 'inspect'}, {'op': 'cancel', 'request_id': 'answer-a', 'reason': 'Review of missing acknowledged outcome'}):
        result = invoke(missing, req)
        assert result['reason'] == 'integrity_error'
    snapshot(missing, 'acknowledged-tail-final')

    # Possible new coupling: an obsolete preparation is unrelated to current edits.
    prepared_store = clone(base, 'obsolete-preparation-base')
    old_preparation = invoke(prepared_store, {'op': 'prepare', 'request_id': 'old-prepare'})
    advanced = invoke(prepared_store, {**add, 'request_id': 'advance'})
    control = clone(prepared_store, 'obsolete-preparation-intact')
    next_good = invoke(control, {**add, 'request_id': 'next'})
    assert next_good['ok'] and next_good['state']['revision'] == 3
    lost = clone(prepared_store, 'obsolete-preparation-missing')
    publication = lost / ('prepare-' + old_preparation['handle'] + '.json')
    witness = OUT / 'obsolete-preparation.original.json'
    publication.rename(witness)
    write_json(OUT / 'obsolete-preparation-move.json', {'original': str(publication), 'retained': str(witness), 'preparation_revision': old_preparation['state']['revision'], 'current_revision': advanced['state']['revision']})
    blocked_inspect = invoke(lost, {'op': 'inspect'})
    blocked_read = invoke(lost, {'op': 'read', 'handle': initial['element']['handle']})
    blocked_edit = invoke(lost, {**add, 'request_id': 'next'})
    appropriate_refusal = invoke(lost, {'op': 'resolve', 'request_id': 'old-prepare'})
    assert all(x['reason'] == 'integrity_error' for x in (blocked_inspect, blocked_read, blocked_edit, appropriate_refusal))
    snapshot(lost, 'obsolete-preparation-final')
    write_json(OUT / 'RESULT.json', {'completed': True, 'invocations': COUNT, 'observations': OBS, 'static_pin_checks': len(checks), 'static_pin_passes': sum(x['ok'] for x in checks), 'comparisons': ['R3 unrelated-attempt correction with relevant-attempt refusal and exact-byte invariance', 'R2 pending-transition diagnostic correction', 'R1 missing-acknowledged-tail diagnostic correction', 'obsolete preparation damage creates current-reading/editing dependency'], 'limitations': 'Controlled fresh specimen damage; no host confinement, physical deletion, power-loss or historical authentication claim.'})
except BaseException as error:
    write_json(OUT / 'FAILURE.json', {'type': type(error).__name__, 'message': str(error), 'invocations': COUNT, 'live_pids': [p.pid for p in LIVE]})
    raise
