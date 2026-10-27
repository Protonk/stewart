"""Resolve an overstrict reviewer predicate without replacing its retained run."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path('/Users/raccoon/Desktop/Experiments/stewart')
BASE = ROOT / '.scratch/receipt-challenge-01'
OUT = BASE / 'review/attempt-01/integration-count-resolution-01'
OUT.mkdir(exist_ok=False)


def retain(name, data):
    with (OUT / name).open('xb') as stream:
        stream.write(data)


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


retain('check.py', Path(__file__).read_bytes())
retain('COMMAND.json', (json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'argv': ['/usr/bin/python3', '-I', '-B', '-S', str(Path(__file__))], 'cwd': str(ROOT)}, indent=2) + '\n').encode())
manifest = json.loads((BASE / 'INTEGRATION-INPUTS-01.json').read_bytes())
pin = next(r for r in manifest['files'] if r['source'] == '.scratch/receipt-challenge-01/INTEGRATION-CHECKS-01.json')
raw = (ROOT / pin['snapshot']).read_bytes()
root = json.loads(raw)
prior_path = BASE / 'review/attempt-01/integration-check-01/RESULT.json'
prior_raw = prior_path.read_bytes()
prior = json.loads(prior_raw)
labels = Counter(r['check'] for r in root['checks'])
repeated = {name: count for name, count in labels.items() if count > 1}
expected = {'.scratch/receipt-challenge-01/subject/' + n + ' pinned bytes' for n in
            ('ACCEPTED.json', 'MANIFEST.json', 'ORIGINS.json', 'QUESTION.md', 'RECIPE.md', 'SNAPSHOT.json', 'capture.py', 'payload.raw')}
expected.update('coordination/receipt-challenge-01/authors/' + a + '/attempt-01/' + n + ' pinned bytes'
                for a in ('a01', 'a02') for n in ('PROCESS.md', 'PROGRESS.md', 'READS.json', 'SELECTED.json'))
expected.update('coordination/receipt-challenge-01/variants/' + a + '/SELECTED.json pinned bytes' for a in ('a01', 'a02'))
checks = [
    {'check': 'Exact root result identity and 289 successful assertion instances', 'passed': identity(raw) == {k: pin[k] for k in ('bytes', 'sha256')} and root['passed'] == root['total'] == len(root['checks']) == 289 and all(r['passed'] is True for r in root['checks'])},
    {'check': '271 labels with exactly 18 expected repeated pinned-byte checks', 'passed': len(labels) == 271 and repeated == {name: 2 for name in expected}},
    {'check': 'Prior 640 passes retained; sole failed predicate was uniqueness', 'passed': prior['passed'] == 640 and prior['total'] == 641 and prior['exit'] == 1 and prior['error'] is None and [r['check'] for r in prior['checks'] if not r['passed']] == ['root 289 unique successful recorded checks']},
]
result = {'checks': checks, 'passed': sum(r['passed'] for r in checks), 'total': len(checks),
          'root_result': identity(raw), 'retained_prior_result': identity(prior_raw), 'repeated_labels': repeated,
          'disposition': 'Withdraw reviewer-only unique-label expectation. The source checks preparation and variant disposition, then capture freezes/current selections; repeated labels do not make its asserted 289 successful check instances false. Original run remains unchanged. No root or subject code executed.'}
retain('RESULT.json', (json.dumps(result, indent=2) + '\n').encode())
code = 0 if all(r['passed'] for r in checks) else 1
output = str(result['passed']) + '/' + str(result['total']) + ' count-resolution checks\n'
retain('stdout.txt', output.encode())
retain('stderr.txt', b'')
retain('EXIT.json', (json.dumps({'exit': code}) + '\n').encode())
print(output, end='')
raise SystemExit(code)
