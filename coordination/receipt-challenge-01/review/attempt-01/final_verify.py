"""Terminal verification of the reviewer's own final outputs only."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path('/Users/raccoon/Desktop/Experiments/stewart')
WORK = ROOT / 'coordination/receipt-challenge-01/review/attempt-01'
OUT = ROOT / '.scratch/receipt-challenge-01/review/attempt-01/terminal-verification-01'
OUT.mkdir(exist_ok=False)


def retain(name, raw):
    with (OUT / name).open('xb') as stream:
        stream.write(raw)


retain('check.py', Path(__file__).read_bytes())
retain('COMMAND.json', (json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'argv': ['/usr/bin/python3', '-I', '-B', '-S', str(Path(__file__))], 'cwd': str(ROOT)}, indent=2) + '\n').encode())
rows = []
for name in ('INTEGRATION-REVIEW.md', 'CHECKPOINT-12.md'):
    data = (WORK / name).read_bytes()
    rows.append({'path': str(WORK / name), 'passed': bool(data.decode('utf-8').strip()), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
result = {'checks': rows, 'passed': sum(r['passed'] for r in rows), 'total': len(rows), 'scope': 'Final reviewer-owned output readability only; no further study inspection.'}
retain('RESULT.json', (json.dumps(result, indent=2) + '\n').encode())
output = str(result['passed']) + '/' + str(result['total']) + ' terminal output checks\n'
retain('stdout.txt', output.encode())
retain('stderr.txt', b'')
code = 0 if all(r['passed'] for r in rows) else 1
retain('EXIT.json', (json.dumps({'exit': code}) + '\n').encode())
print(output, end='')
raise SystemExit(code)
