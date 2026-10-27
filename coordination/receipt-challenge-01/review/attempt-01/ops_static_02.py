"""Static checks of root's two preflight fixes; never execute ops or helper."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path('/Users/raccoon/Desktop/Experiments/stewart')
OUT = ROOT / '.scratch/receipt-challenge-01/review/attempt-01/ops-static-02'
OUT.mkdir(exist_ok=False)


def put(name, raw):
    with (OUT / name).open('xb') as handle:
        handle.write(raw)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2) + '\n').encode()


checks = []


def check(name, value):
    checks.append({'name': name, 'passed': bool(value)})


pin_raw = (ROOT / '.scratch/receipt-challenge-01/OPS-REVISION-02.json').read_bytes()
pin = json.loads(pin_raw)
current = (ROOT / pin['source']).read_bytes()
snapshot = (ROOT / pin['snapshot']).read_bytes()
baseline = json.loads((ROOT / '.scratch/receipt-challenge-01/PREFLIGHT-INPUTS-01.json').read_bytes())
original_row = next(r for r in baseline['files'] if r['source'] == pin['source'])
original = (ROOT / original_row['snapshot']).read_bytes()
put('PIN.json', pin_raw)
put('original.py', original)
put('revised.py', snapshot)
put('check.py', Path(__file__).read_bytes())
put('PREFLIGHT-DRAFT-01.md', (ROOT / 'coordination/receipt-challenge-01/review/attempt-01/PREFLIGHT.md').read_bytes())
put('COMMAND.json', encoded({'at': datetime.now(timezone.utc).isoformat(), 'argv': ['/usr/bin/python3', '-I', '-B', '-S', 'coordination/receipt-challenge-01/review/attempt-01/ops_static_02.py'], 'cwd': str(ROOT), 'source_sha256': sha(Path(__file__).read_bytes())}))
check('revised current identity matches pin', len(current) == pin['bytes'] and sha(current) == pin['sha256'])
check('revised snapshot identity matches pin', len(snapshot) == pin['bytes'] and sha(snapshot) == pin['sha256'])
check('current equals snapshot', current == snapshot)
check('original identity still matches initial baseline', len(original) == original_row['bytes'] and sha(original) == original_row['sha256'])
tree = ast.parse(snapshot)
check('revised source syntax parses without execution', isinstance(tree, ast.Module))
old, new = original.decode(), snapshot.decode()
diff = ''.join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile='original.py', tofile='revised.py'))
put('source.diff', diff.encode())
check('four output requirement precedes fresh destination', new.index("('SELECTED.json','PROCESS.md','READS.json','PROGRESS.md')") < new.index('destination.mkdir(parents=True,exist_ok=False)'))
check('frozen selection comparison precedes helper launch', new.index('if read(frozen_selection)!=raw:') < new.index("argv=['/usr/bin/python3'") < new.index('process=subprocess.Popen'))
guard = new[new.index('    frozen_selection='):new.index("    argv=['/usr/bin/python3'")]
check('mismatch preserves exclusive failure and stops before launch', "write_receipt(destination/'FAILURE.json'" in guard and "'reason':'selection_changed_during_freeze'" in guard and 'raise ValueError' in guard and "path.open('xb')" in new)
check('post-exit checks include frozen selection identity', "'frozen_selection':read(frozen_selection)==raw" in new)
restored = new.replace("('SELECTED.json','PROCESS.md','READS.json','PROGRESS.md')", "('SELECTED.json','PROCESS.md','READS.json')")
restored = restored.replace(guard, '')
restored = restored.replace("checks={'raw_witness':read(destination/'input.raw')==raw,'frozen_selection':read(frozen_selection)==raw,\n        'helper_raw'", "checks={'raw_witness':read(destination/'input.raw')==raw,'helper_raw'")
check('all other source bytes unchanged', restored == old)
result = {'checks': checks, 'passed': sum(c['passed'] for c in checks), 'total': len(checks), 'subject_executions': 0, 'helper_executions': 0, 'ops_executions': 0, 'revised_ops_sha256': sha(snapshot), 'revised_ops_bytes': len(snapshot), 'scope': 'source identity, exact diff and normal-path source ordering only; no fault or concurrency execution'}
put('RESULT.json', encoded(result))
put('stdout.txt', encoded(result))
print(json.dumps(result, indent=2))
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
