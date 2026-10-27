"""Finite final-candidate preparation-dependency review probes. Keep all specimens and witnesses."""
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
OUT = ROOT / '.scratch/submission-prototype-01/review/probe-final-01'
PIN = ROOT / '.scratch/submission-prototype-01/REVIEW-INPUTS-03.json'
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

write_json(OUT / 'START.json', {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'pid': os.getpid(), 'argv': sys.argv, 'cwd': str(Path.cwd()), 'work': str(WORK), 'binary': str(BINARY), 'binary_sha256': actual, 'grant': 'at most 24 invocations; frozen final primary binary only; retained reviewer stores; no deletion'})

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
    payload = b'Final-candidate selection witness\x00\xff\n'
    source.write_bytes(payload)
    (OUT / 'source.witness.bin').write_bytes(payload)
    add = {'op': 'add', 'request_id': 'answer-a', 'name': 'answer', 'source': str(source), 'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
    base = fresh('base')
    invoke(base, {'op': 'init', 'audit': 'review-a', 'commission_sha256': '0' * 64, 'request_id': 'init-a'})
    initial = invoke(base, add)
    prepared = invoke(base, {'op': 'prepare', 'request_id': 'prepare-a'})
    submit = {'op': 'submit', 'handle': prepared['handle'], 'submit': True}
    publication_name = 'prepare-' + prepared['handle'] + '.json'
    snapshot(base, 'base')

    # Current unsubmitted preparation damage preserves normal answer access.
    current = clone(base, 'current-unused-preparation-missing')
    (current / publication_name).rename(OUT / 'current-unused-preparation.original.json')
    inspected = invoke(current, {'op': 'inspect'})
    read = invoke(current, {'op': 'read', 'handle': initial['element']['handle']})
    refused_submit = invoke(current, submit)
    assert inspected['state'] == initial['state'] and bytes.fromhex(read['bytes_hex']) == payload and refused_submit['reason'] == 'integrity_error'
    for op in ('resolve', 'resume', 'cancel'):
        req = {'op': op, 'request_id': 'prepare-a'}
        if op == 'cancel':
            req['reason'] = 'Missing acknowledged issuance must remain diagnostic'
        result = invoke(current, req)
        assert result['reason'] == 'integrity_error'
    continued = invoke(current, {**add, 'request_id': 'next'})
    assert continued['ok'] and continued['state']['revision'] == 2
    snapshot(current, 'current-unused-final')

    # Stale preparation's malformed outcome is excluded before decoding.
    stale = clone(base, 'stale-preparation-outcome-damaged')
    advanced = invoke(stale, {**add, 'request_id': 'advance'})
    plan_path = stale / ('request-' + hashlib.sha256(b'prepare-a').hexdigest() + '.json')
    outcome = stale / json.loads(plan_path.read_bytes())['outcome_name']
    corrupt(outcome, b'{"schema":"prototype-outcome-v1","schema":"prototype-outcome-v1"}', 'stale-preparation-outcome')
    inspected = invoke(stale, {'op': 'inspect'})
    continued = invoke(stale, {**add, 'request_id': 'next'})
    refused_submit = invoke(stale, submit)
    refused_resolve = invoke(stale, {'op': 'resolve', 'request_id': 'prepare-a'})
    assert inspected['state'] == advanced['state'] and continued['state']['revision'] == 3 and refused_submit['reason'] == 'integrity_error' and refused_resolve['reason'] == 'integrity_error'
    snapshot(stale, 'stale-preparation-final')

    # A chosen submitted issuance remains a dependency of final-state claims.
    chosen = clone(base, 'submitted-chosen-issuance-damaged')
    sealed = invoke(chosen, submit)
    stable = invoke(chosen, {'op': 'inspect'})
    assert sealed['state']['submitted'] and stable['state'] == sealed['state']
    corrupt(chosen / publication_name, b'{"damaged":true}', 'submitted-chosen-issuance')
    for req in ({'op': 'inspect'}, {'op': 'read', 'handle': initial['element']['handle']}, submit):
        refusal = invoke(chosen, req)
        assert refusal['reason'] == 'integrity_error'
    snapshot(chosen, 'submitted-chosen-final')

    # State-changing acknowledgement remains globally binding after separation.
    tail = clone(base, 'submitted-tail-missing')
    sealed = invoke(tail, submit)
    assert sealed['state']['submitted']
    last = sorted(tail.glob('commit-*.json'))[-1]
    last.rename(OUT / 'submitted-tail.original.json')
    for req in ({'op': 'inspect'}, {'op': 'resolve', 'request_id': prepared['handle']}, {'op': 'cancel', 'request_id': prepared['handle'], 'reason': 'Missing submission must not become cancellable'}):
        refusal = invoke(tail, req)
        assert refusal['reason'] == 'integrity_error'
    snapshot(tail, 'submitted-tail-final')
    assert COUNT == 24
    write_json(OUT / 'RESULT.json', {'completed': True, 'invocations': COUNT, 'observations': OBS, 'static_pin_checks': len(checks), 'static_pin_passes': sum(x['ok'] for x in checks), 'comparisons': ['missing current unused issuance permits exact answer read and new edit but refuses its submit/resolve/resume/cancel', 'malformed stale preparation outcome permits current inspect and edit but refuses own submission/resolution', 'chosen submitted issuance damage still refuses final-state claims', 'missing acknowledged submission tail remains an integrity gap'], 'limitations': 'Controlled fresh specimen damage; no host confinement, physical deletion, power-loss or historical authentication claim.'})
except BaseException as error:
    write_json(OUT / 'FAILURE.json', {'type': type(error).__name__, 'message': str(error), 'invocations': COUNT, 'live_pids': [p.pid for p in LIVE]})
    raise
