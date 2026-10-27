"""Read-only closeout checks; no subject execution and no evidence disposal."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / '.scratch/construction-execution-01'
DOC = REPO / 'coordination/construction-execution-01'
checks = []
commands = []


def check(label, value):
    checks.append({'check': label, 'passed': bool(value)})


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


for name in ('REVIEW-INPUTS-01.json', 'RESULT-REVIEW-INPUTS-01.json'):
    for row in load(ROOT / name)['inputs']:
        raw = (REPO / row['snapshot']).read_bytes()
        check(name + ' frozen copy: ' + row['path'],
              len(raw) == row['bytes'] and sha(raw) == row['sha256'])

prep = load(ROOT / 'PREPARATION.json')
for prefix, key in (('stage', 'stage'), ('witness', 'witness')):
    folder = ROOT / prefix
    actual = {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file()}
    expected = {name for name, row in prep[key].items() if row['kind'] == 'file'}
    check(prefix + ' finite file membership at closeout', actual == expected)
    check(prefix + ' no links or bytecode at closeout', not any(
        p.is_symlink() or p.suffix == '.pyc' or p.name == '__pycache__' for p in folder.rglob('*')))
    for name in sorted(expected):
        raw = (folder / name).read_bytes()
        row = prep[key][name]
        check(prefix + ' bytes at closeout: ' + name,
              len(raw) == row['bytes'] and sha(raw) == row['sha256'])

for source, tracked in (('observer.stdout', 'OBSERVATIONS.jsonl'), ('EXPECTED.json', 'EXPECTED.json')):
    check('tracked exact copy: ' + tracked, (ROOT / source).read_bytes() == (DOC / tracked).read_bytes())
end = load(ROOT / 'EXIT.json')
check('capture exit and empty stderr', end['exit'] == 0 and (ROOT / 'observer.stderr').read_bytes() == b'')
raw = (ROOT / 'observer.stdout').read_bytes()
check('captured stdout retained identity', len(raw) == end['stdout']['bytes'] and sha(raw) == end['stdout']['sha256'])
records = [json.loads(line) for line in raw.splitlines()]
check('eight records and six specimen evaluations', len(records) == 8 and sum(r['stage'] == 'specimen' for r in records) == 6)
check('one exclusive reservation and PID account', (ROOT / 'RUN-RESERVATION.json').is_file()
      and load(ROOT / 'PID.json')['pid'] == end['pid'])
check('no observed launch failure or intervention', not any((ROOT / name).exists() for name in (
    'RUN-FAILURE.json', 'TIMEOUT.json', 'KILL.json', 'PARENT-FAILURE-INTERVENTION.json', 'PARENT-FAILURE-KILL.json')))
comparison = load(ROOT / 'COMPARISON-01.json')
check('107/107 root comparisons, no exception', comparison['passed'] == comparison['total'] == 107
      and comparison['exception'] is None)

for name in ('study.py', 'compare.py', 'PROTOCOL.md'):
    rel = str((DOC / name).relative_to(REPO))
    argv = ['/usr/bin/git', 'show', '4bc6bd9:' + rel]
    process = subprocess.run(argv, cwd=REPO, capture_output=True)
    commands.append({'argv': argv, 'exit': process.returncode, 'stderr': process.stderr.decode(),
                     'stdout_bytes': len(process.stdout), 'stdout_sha256': sha(process.stdout)})
    check('reviewed preparation unchanged: ' + name, process.returncode == 0 and process.stdout == (DOC / name).read_bytes())

argv = ['/usr/bin/git', 'diff', '--exit-code', '9ffad1f', '--',
        'src', 'tests', 'coordination/fresh-authoring-01', 'CONTRACTS.md', 'AGENTS.md']
process = subprocess.run(argv, cwd=REPO, capture_output=True)
commands.append({'argv': argv, 'exit': process.returncode,
                 'stdout': process.stdout.decode(), 'stderr': process.stderr.decode()})
check('source/tests/prior-pilot/contracts/guidance unchanged by this commission', process.returncode == 0)

for path in sorted(DOC.rglob('*.md')) + [REPO / 'DEVELOPMENT-PLAN.md', REPO / 'coordination/COORDINATOR-NOTES.md']:
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text()):
        target = target.split('#', 1)[0]
        if not target or '://' in target or target.startswith('mailto:'):
            continue
        check('document link: ' + str(path.relative_to(REPO)) + ' -> ' + target,
              (path.parent / target).exists())

result = {'at': datetime.now(timezone.utc).isoformat(), 'checks': checks,
          'passed': sum(row['passed'] for row in checks), 'total': len(checks),
          'commands': commands, 'observer_invocations': 0, 'pytest_nodes': 0,
          'code_sha256': sha(Path(__file__).read_bytes())}
with (ROOT / 'FINAL-CHECKS-01.json').open('x') as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write('\n')
print(f"Final retained-evidence/document checks: {result['passed']}/{result['total']}")
sys.exit(0 if result['passed'] == result['total'] else 1)
