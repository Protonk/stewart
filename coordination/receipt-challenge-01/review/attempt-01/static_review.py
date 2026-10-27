"""Review-only byte reads and hashes; never imports or executes study code."""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path('/Users/raccoon/Desktop/Experiments/stewart')
SCRATCH = ROOT / '.scratch/receipt-challenge-01/review/attempt-01'
BASELINE = ROOT / '.scratch/receipt-challenge-01/PREFLIGHT-INPUTS-01.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('mode', choices=['verify', 'read'])
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--stop', type=int)
    args = parser.parse_args()
    baseline = json.loads(BASELINE.read_bytes())
    pinned = {row['source']: row for row in baseline['files']}
    output = []
    if args.mode == 'verify':
        rows = []
        for row in baseline['files']:
            result = {'source': row['source'], 'expected_bytes': row['bytes'], 'expected_sha256': row['sha256']}
            for field, path in [('snapshot', row['snapshot']), ('current', row['source'])]:
                try:
                    data = (ROOT / path).read_bytes()
                    result[field] = {'bytes': len(data), 'sha256': digest(data), 'matches': len(data) == row['bytes'] and digest(data) == row['sha256']}
                except Exception as exc:
                    result[field] = {'error': type(exc).__name__ + ': ' + str(exc)}
            rows.append(result)
        output.append(json.dumps({'baseline_sha256': digest(BASELINE.read_bytes()), 'count': len(rows), 'rows': rows}, indent=2))
    else:
        for requested in args.paths:
            row = pinned.get(requested)
            if row is None:
                raise ValueError('Read requires a pinned source: ' + requested)
            data = (ROOT / row['snapshot']).read_bytes()
            if len(data) != row['bytes'] or digest(data) != row['sha256']:
                raise ValueError('Snapshot identity mismatch: ' + requested)
            lines = data.decode('utf-8').splitlines(keepends=True)
            selected = lines[args.start-1:args.stop]
            output.append('FILE: ' + requested + ' LINES: ' + str(args.start) + '-' + str(args.stop or len(lines)) + '\n' + ''.join(selected))
    result = '\n\n'.join(output) + '\n'
    with (SCRATCH / (args.label + '.output.txt')).open('x') as handle:
        handle.write(result)
    record = {'at': datetime.now(timezone.utc).isoformat(), 'interpreter': '/usr/bin/python3 -I -B -S', 'script': 'coordination/receipt-challenge-01/review/attempt-01/static_review.py', 'label': args.label, 'mode': args.mode, 'paths': args.paths, 'line_selection': [args.start, args.stop], 'baseline_sha256': digest(BASELINE.read_bytes()), 'output_sha256': digest(result.encode()), 'output_bytes': len(result.encode()), 'exit': 0}
    with (SCRATCH / (args.label + '.command.json')).open('x') as handle:
        json.dump(record, handle, indent=2)
        handle.write('\n')
    print(result, end='')


if __name__ == '__main__':
    main()
