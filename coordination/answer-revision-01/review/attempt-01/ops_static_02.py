"""Focused static binding/revision inspection; no coordinator code execution."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[4]
out = root / '.scratch/answer-revision-01/review/attempt-01/ops-static-02'
out.mkdir()
checks = []


def save(name, raw):
    with (out / name).open('xb') as stream:
        stream.write(raw)


def check(name, condition):
    checks.append({'name': name, 'passed': bool(condition)})


raw = (root / '.scratch/answer-revision-01/OPS-PIN-02.json').read_bytes()
pin = json.loads(raw)
source = (root / pin['snapshot']).read_bytes()
save('OPS-PIN-02.json', raw)
save('study_ops-before-authors-02.py', source)
save('check.py', Path(__file__).read_bytes())
save('COMMAND.json', (json.dumps({'argv': [sys.executable, '-I', '-B', '-S', str(Path(__file__).resolve())], 'cwd': str(root), 'at': datetime.now(timezone.utc).isoformat()}, indent=2) + '\n').encode())
check('revised source pin identity', len(source) == pin['bytes'] and hashlib.sha256(source).hexdigest() == pin['sha256'])
check('live revised source equals pin', source == (root / pin['path']).read_bytes())
tree = ast.parse(source)
check('revised Python parses statically', bool(tree))
functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
text = source.decode()
lines = text.splitlines()


def body(name):
    node = functions[name]
    return '\n'.join(lines[node.lineno - 1:node.end_lineno])


capture = body('capture')
barrier = body('author_barrier')
packets = body('packets')
check('required author files precede capture destination creation', capture.index("for required in ('SELECTED-'") < capture.index('destination.mkdir()'))
check('capture requires all three named files', "'READS-' + phase + '.json', 'PROCESS-' + phase + '.md'" in capture and 'regular(source / required)' in capture)
check('barrier requires frozen read/process/selection files', "'READS-' + phase + '.json', 'PROCESS-' + phase + '.md'" in barrier and "regular(folder / 'author-files' / required)" in barrier)
check('barrier checks frozen selection equals submitted witness', "regular(folder / 'author-files' / ('SELECTED-' + phase + '.json')) != regular(folder / 'input.raw')" in barrier)
check('barrier refusal precedes writing frozen barrier', barrier.index("raise ValueError('Frozen author selection differs") < barrier.index("write_receipt(ROOT / ('AUTHOR-PHASE-'"))
check('packet assembly revalidates each frozen capture file', "for capture in barrier['captures']:" in packets and "for entry in capture['files']:" in packets and "len(raw) != entry['bytes'] or sha(raw) != entry['sha256']" in packets)
check('packet revalidation precedes packet creation', packets.index("raise ValueError('Frozen capture changed") < packets.index('packet.mkdir('))
check('common submitted metadata retained with explicit attribution label', "'submitted_metadata': {key: payload[key]" in packets and "'question_id', 'source_revision', 'author', 'response_kind', 'completion_claim'" in packets)
check('minimal receives no submitted_metadata invention', "'completion_claim')}} if common else {})" in packets)
result = {'checks': checks, 'assertions': len(checks), 'passed': sum(row['passed'] for row in checks),
          'failed': sum(not row['passed'] for row in checks), 'pin_manifest_bytes': len(raw),
          'pin_manifest_sha256': hashlib.sha256(raw).hexdigest(), 'coordinator_utility_executions': 0,
          'subject_executions': 0, 'qualification': 'Static revision checks; not execution, fault injection or hostile-writer qualification.'}
save('RESULT.json', (json.dumps(result, indent=2) + '\n').encode())
print(json.dumps(result, indent=2))
sys.exit(0 if not result['failed'] else 1)
