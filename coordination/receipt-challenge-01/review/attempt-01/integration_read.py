"""Read only exact frozen integration inputs; all study programs remain inert."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path('/Users/raccoon/Desktop/Experiments/stewart')
OUT = ROOT / '.scratch/receipt-challenge-01/review/attempt-01'
BASELINE = ROOT / '.scratch/receipt-challenge-01/INTEGRATION-INPUTS-01.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('mode', choices=['verify', 'read', 'selection'])
    parser.add_argument('sources', nargs='*')
    args = parser.parse_args()
    baseline_raw = BASELINE.read_bytes()
    baseline = json.loads(baseline_raw)
    pins = {row['source']: row for row in baseline['files']}
    result = []
    if args.mode == 'verify':
        rows = []
        for row in baseline['files']:
            raw = (ROOT / row['snapshot']).read_bytes()
            rows.append({'source': row['source'], 'passed': len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'bytes': len(raw), 'sha256': sha(raw)})
        result.append(json.dumps({'count': len(rows), 'passed': sum(r['passed'] for r in rows), 'unique_sources': len(pins), 'baseline_sha256': sha(baseline_raw), 'rows': rows}, indent=2))
    else:
        for source in args.sources:
            row = pins[source]
            raw = (ROOT / row['snapshot']).read_bytes()
            if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
                raise ValueError('Frozen input changed: ' + source)
            if args.mode == 'read':
                text = raw.decode()
            else:
                value = json.loads(raw)
                common = 'answer' in value
                field, name = ('support', 'id') if common else ('artifacts', 'name')
                text = json.dumps({key: item for key, item in value.items() if key not in (field, 'answer', 'text')}, indent=2) + '\nPRIMARY:\n' + value['answer' if common else 'text']
                for i, item in enumerate(value[field]):
                    text += '\n\nARTIFACT ' + str(i) + ': ' + item[name] + '\n' + item['text']
            result.append('SOURCE: ' + source + '\n' + text)
    output = '\n\n'.join(result) + '\n'
    command = {'at': datetime.now(timezone.utc).isoformat(), 'argv': ['/usr/bin/python3', '-I', '-B', '-S', 'coordination/receipt-challenge-01/review/attempt-01/integration_read.py', args.label, args.mode] + args.sources, 'cwd': str(ROOT), 'baseline_sha256': sha(baseline_raw), 'script_sha256': sha(Path(__file__).read_bytes()), 'output_sha256': sha(output.encode()), 'exit': 0}
    for suffix, raw in [('output.txt', output.encode()), ('command.json', (json.dumps(command, indent=2) + '\n').encode()), ('code.py', Path(__file__).read_bytes())]:
        with (OUT / (args.label + '.' + suffix)).open('xb') as handle:
            handle.write(raw)
    if args.mode == 'verify':
        print(json.dumps({'passed': sum(r['passed'] for r in rows), 'total': len(rows), 'baseline_sha256': sha(baseline_raw)}))
    else:
        print(output, end='')


if __name__ == '__main__':
    main()
