"""Retained before/after comparison proposed by the stopped static auditor."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary', type=Path, required=True)
p.add_argument('--evidence', type=Path, required=True)
p.add_argument('--expect', choices=['omission', 'preserved'], required=True)
a = p.parse_args()
out = a.evidence.absolute()
out.mkdir(exist_ok=False)
sources = out / 'sources'
sources.mkdir()
q, m = sources / 'question', sources / 'material'
q.write_bytes(b'Which original undertaking was requested?\n')
material = b'expected selected material\n'
digest = lambda raw: hashlib.sha256(raw).hexdigest()
request = {
    'schema': 'stewart.commission-request/1', 'request_id': 'incomplete-recall',
    'custodian': 'root independent comparison', 'grants': 'Recall finite original undertaking.',
    'limits': 'No audit execution or deletion.',
    'members': [
        {'id': 'question', 'role': 'question', 'source': str(q), 'view': 'QUESTION',
         'size': q.stat().st_size, 'sha256': digest(q.read_bytes())},
        {'id': 'material', 'role': 'material', 'source': str(m), 'view': 'MATERIAL',
         'size': len(material), 'sha256': digest(material)},
    ],
}
rp = out / 'request.json'
rp.write_text(json.dumps(request, indent=2) + '\n')
(out / 'request-witness.json').write_bytes(rp.read_bytes())
commands, checks = [], []

def save(name, value):
    with (out / name).open('x') as stream:
        json.dump(value, stream, indent=2)

def check(label, passed):
    checks.append({'check': label, 'passed': bool(passed)})

def run(label, *args):
    argv = [str(a.binary.absolute()), *map(str, args)]
    save(label + '.START.json', {'argv': argv, 'cwd': str(out)})
    result = subprocess.run(argv, cwd=out, capture_output=True)
    for stream in ['stdout', 'stderr']:
        with (out / (label + '.' + stream)).open('xb') as f:
            f.write(getattr(result, stream))
    commands.append({'label': label, 'exit': result.returncode})
    return result

def reason(result):
    return json.loads(result.stderr)['error']['reason']

try:
    bundles = {k: out / k for k in ['changed', 'invariant', 'accepted']}
    for path in bundles.values():
        path.mkdir()
    for name in ['changed', 'invariant']:
        r = run(name + '-intake', 'accept', '--request', rp, '--bundle', bundles[name])
        check(name + ' legitimate incomplete intake', r.returncode == 2 and reason(r) == 'missing')
    m.write_bytes(material)
    r = run('accepted-intake', 'accept', '--request', rp, '--bundle', bundles['accepted'])
    check('healthy accepted firing control', r.returncode == 0)
    sources.rename(out / 'sources-unavailable')
    intent = (bundles['changed'] / 'INTENT.json').read_bytes()
    before = run('before', 'inspect', '--bundle', bundles['changed'])
    check('valid incomplete request visible before acknowledgment',
          before.returncode == 3 and json.loads(before.stdout)['original_undertaking'] == request)
    r = run('acknowledge', 'abandon', '--bundle', bundles['changed'], '--actor', 'root comparator',
            '--reason', 'Retain incomplete material; requested acceptance was not completed.')
    check('attributed incomplete acknowledgment succeeds', r.returncode == 0)
    after = run('after', 'inspect', '--bundle', bundles['changed'])
    visible = json.loads(after.stdout).get('original_undertaking')
    check('original request ' + a.expect + ' after acknowledgment', after.returncode == 0 and
          (visible is None if a.expect == 'omission' else visible == request))
    r = run('after-raw', 'read', '--bundle', bundles['changed'], '--member', '@request')
    check('raw request retrieval still requires absent acceptance', r.returncode == 2 and reason(r) == 'missing')
    check('original intent preserved unchanged', (bundles['changed'] / 'INTENT.json').read_bytes() == intent)
    r = run('invariance', 'inspect', '--bundle', bundles['invariant'])
    check('unacknowledged request visible with original sources unavailable',
          r.returncode == 3 and json.loads(r.stdout)['original_undertaking'] == request)
    r = run('accepted-raw', 'read', '--bundle', bundles['accepted'], '--member', '@request')
    check('accepted raw request remains recoverable without sources', r.returncode == 0 and r.stdout == rp.read_bytes())
    r = run('invariant-disposition', 'abandon', '--bundle', bundles['invariant'], '--actor', 'root comparator',
            '--reason', 'Comparison finished; retain incomplete control and its evidence without deletion.')
    check('control incomplete undertaking explicitly disposed after observation', r.returncode == 0)
except Exception as exc:
    check('driver completed', False)
    save('DRIVER-FAILURE.json', {'error': repr(exc)})
record = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'binary_sha256': digest(a.binary.read_bytes()), 'expected_projection': a.expect,
          'observer': 'root after audit stop; auditor proposed but did not execute this comparison',
          'checks': checks, 'passed': sum(c['passed'] for c in checks), 'total': len(checks),
          'commands': commands, 'retention': 'All specimens and independent witness retained; no disposal deletion.'}
save('RESULT.json', record)
print(json.dumps({'passed': record['passed'], 'total': record['total'], 'evidence': str(out)}))
raise SystemExit(record['passed'] != record['total'])
