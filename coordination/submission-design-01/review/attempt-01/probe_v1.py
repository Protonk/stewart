"""Finite independent v1 review probes. Keep all specimens and witnesses."""
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
OUT = ROOT / '.scratch/submission-prototype-01/review/probe-v1-01'
PIN = ROOT / '.scratch/submission-prototype-01/REVIEW-INPUTS-01.json'
OUT.mkdir()
PINS = json.loads(PIN.read_text())
BINARY = Path(PINS['binary'])
checks = []
for item in PINS['inputs']:
    actual = hashlib.sha256((ROOT / item['snapshot']).read_bytes()).hexdigest()
    checks.append({'path': item['snapshot'], 'expected': item['sha256'], 'actual': actual, 'ok': actual == item['sha256']})
actual = hashlib.sha256(BINARY.read_bytes()).hexdigest()
checks.append({'path': str(BINARY), 'expected': PINS['binary_sha256'], 'actual': actual, 'ok': actual == PINS['binary_sha256']})
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

write_json(OUT / 'START.json', {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'pid': os.getpid(), 'argv': sys.argv, 'cwd': str(Path.cwd()), 'work': str(WORK), 'binary': str(BINARY), 'binary_sha256': actual, 'grant': 'at most 24 invocations; frozen v1 binary only; retained reviewer stores; no deletion'})

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
    payload = b'Independent original bytes\x00\xff\n'
    source.write_bytes(payload)
    (OUT / 'source.witness.bin').write_bytes(payload)
    add = {'op': 'add', 'request_id': 'answer-a', 'name': 'answer', 'source': str(source), 'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
    base = fresh('base')
    invoke(base, {'op': 'init', 'audit': 'review-a', 'commission_sha256': '0' * 64, 'request_id': 'init-a'})
    initial = invoke(base, add)
    assert initial['ok']
    snapshot(base, 'base')

    # Firing control: fresh exact-source edit succeeds in an intact clone.
    intact = clone(base, 'intact-control')
    good = invoke(intact, {**add, 'request_id': 'answer-b'})
    assert good['ok'] and good['state']['revision'] == 2

    # Changed property: only an unrelated old attempt record becomes malformed.
    damaged = clone(base, 'unrelated-attempt-damaged')
    init_ref = 'request-' + hashlib.sha256(b'init-a').hexdigest() + '.json'
    old_attempt = next(path for path in damaged.glob('attempt-*.json') if json.loads(path.read_bytes())['request']['name'] == init_ref)
    corrupt(old_attempt, b'{"schema":"prototype-attempt-v1","schema":"prototype-attempt-v1"}', 'unrelated-init-attempt')
    broken = invoke(damaged, {**add, 'request_id': 'answer-b'})
    stable = invoke(damaged, {'op': 'inspect'})
    read = invoke(damaged, {'op': 'read', 'handle': initial['element']['handle']})
    cancel = invoke(damaged, {'op': 'cancel', 'request_id': 'answer-b', 'reason': 'Independent review disposition of refused edit'})
    again = invoke(damaged, {**add, 'request_id': 'answer-c'})
    assert broken['reason'] == 'integrity_error' and stable['state'] == initial['state'] and bytes.fromhex(read['bytes_hex']) == payload and cancel['status'] == 'cancelled' and again['reason'] == 'integrity_error'
    snapshot(damaged, 'unrelated-attempt-final')

    # Known v1 omission: preserve the acknowledged tail elsewhere, then resolve.
    missing = clone(base, 'acknowledged-tail-missing')
    commit = sorted(missing.glob('commit-*.json'))[-1]
    retained = OUT / 'acknowledged-tail.original.json'
    commit.rename(retained)
    write_json(OUT / 'tail-move.json', {'original': str(commit), 'retained': str(retained)})
    unresolved = invoke(missing, {'op': 'resolve', 'request_id': 'answer-a'})
    lost_view = invoke(missing, {'op': 'inspect'})
    lost_cancel = invoke(missing, {'op': 'cancel', 'request_id': 'answer-a', 'reason': 'Review of wrongly downgraded acknowledged operation'})
    assert unresolved['status'] == 'pending' and lost_view['state']['revision'] == 0 and lost_cancel['status'] == 'cancelled'
    snapshot(missing, 'acknowledged-tail-final')

    # Known pending-plan validation gap, with a real precommit interruption.
    pending = clone(base, 'pending-plan-damaged')
    invoke(pending, {**add, 'request_id': 'pending-b'}, hook='after_stage')
    pending_request = pending / ('request-' + hashlib.sha256(b'pending-b').hexdigest() + '.json')
    plan = json.loads(pending_request.read_bytes())
    plan['candidate']['audit'] = 'foreign-audit'
    corrupt(pending_request, json.dumps(plan, separators=(',', ':')).encode(), 'pending-plan-audit')
    bad_resolve = invoke(pending, {'op': 'resolve', 'request_id': 'pending-b'})
    bad_cancel = invoke(pending, {'op': 'cancel', 'request_id': 'pending-b', 'reason': 'Review of unverifiable pending plan'})
    assert bad_resolve['status'] == 'pending' and bad_cancel['status'] == 'cancelled'
    snapshot(pending, 'pending-plan-final')
    write_json(OUT / 'RESULT.json', {'completed': True, 'invocations': COUNT, 'observations': OBS, 'static_pin_checks': len(checks), 'static_pin_passes': sum(x['ok'] for x in checks), 'comparisons': ['unrelated malformed attempt versus intact edit, with old-view/read invariance', 'missing acknowledged commit versus retained independent witness', 'invalid pending candidate after observed after_stage SIGSTOP/SIGKILL'], 'limitations': 'Controlled fresh specimen damage; no host confinement, physical deletion, power-loss or historical authentication claim.'})
except BaseException as error:
    write_json(OUT / 'FAILURE.json', {'type': type(error).__name__, 'message': str(error), 'invocations': COUNT, 'live_pids': [p.pid for p in LIVE]})
    raise
