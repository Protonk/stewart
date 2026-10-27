"""Correct the line-based comparator preservation check using AST data only."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

REPO = Path('/Users/raccoon/Desktop/Experiments/stewart')
ROOT = REPO / '.scratch/construction-execution-01'
OUT = ROOT / 'review/attempt-01'
checks = []


def check(label, actual, expected):
    passed = actual == expected
    row = {'check': label, 'passed': passed}
    if not passed:
        row.update(actual=actual, expected=expected)
    checks.append(row)


def calls(raw):
    return {ast.dump(node.args[0]): node for node in ast.walk(ast.parse(raw))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'check'}


old = calls((ROOT / 'comparator-before-run.py').read_bytes())
new = calls((ROOT / 'preflight-revision-02/compare.py').read_bytes())
added = {ast.dump(ast.Constant(v)) for v in ('launch driver matches reviewed identity', 'child termination precedes postrun inventory')}
check('exactly two new comparator checks', sorted(set(new) - set(old)), sorted(added))
check('every original comparator check label retained', sorted(set(old) - set(new)), [])
special = ast.dump(ast.Constant('no run failure or intervention'))
unchanged = [key for key in old if key != special and ast.dump(old[key]) == ast.dump(new[key])]
check('every other original check call unchanged', len(unchanged), len(old) - 1)
old_call, new_call = old[special], new[special]
old_names = next(node for node in ast.walk(old_call) if isinstance(node, ast.Tuple))
new_names = next(node for node in ast.walk(new_call) if isinstance(node, ast.Tuple))
check('extended failure records exact selection', ast.literal_eval(new_names), ast.literal_eval(old_names) + ('PARENT-FAILURE-INTERVENTION.json', 'PARENT-FAILURE-KILL.json'))
new_names.elts = old_names.elts
check('failure check otherwise unchanged', ast.dump(new_call), ast.dump(old_call))
revision_result = json.loads((OUT / 'REVISION-CHECKS-02.json').read_bytes())
check('only original revision failure was line-based preservation predicate', [c['check'] for c in revision_result['checks'] if not c['passed']], ['comparator removes no original checks'])
manifest = json.loads((ROOT / 'PREFLIGHT-REVISION-02.json').read_bytes())
for row in manifest['inputs']:
    raw = (REPO / row['path']).read_bytes()
    check('revision remains pinned: ' + row['path'], [len(raw), hashlib.sha256(raw).hexdigest()], [row['identity']['bytes'], row['identity']['sha256']])
result = {'at': datetime.now(timezone.utc).isoformat(), 'checks': checks,
          'passed': sum(r['passed'] for r in checks), 'total': len(checks),
          'observer_invocations': 0, 'pytest_nodes': 0,
          'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'correction': 'A line replacement extends the same existing comparator check; deleted source lines did not establish a removed check. Original failure is preserved.'}
with (OUT / 'CORRECTION-CHECKS-03.json').open('x') as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write('\n')
print(f"Correction static checks: {result['passed']}/{result['total']}")
for row in checks:
    if not row['passed']:
        print(json.dumps(row), file=sys.stderr)
sys.exit(0 if result['passed'] == result['total'] else 1)
