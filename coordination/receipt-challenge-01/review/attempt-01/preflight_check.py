"""Independent static provenance/binding checks; no study module execution."""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('/Users/raccoon/Desktop/Experiments/stewart')
OUT = ROOT / '.scratch/receipt-challenge-01/review/attempt-01/static-check-01'
OUT.mkdir(exist_ok=False)
checks = []


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def put(name, raw):
    with (OUT / name).open('xb') as handle:
        handle.write(raw)


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Repeated JSON key: ' + repr(key))
        value[key] = item
    return value


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique)


def check(name, condition, detail=None):
    checks.append({'name': name, 'passed': bool(condition), 'detail': detail})


baseline = parse((ROOT / '.scratch/receipt-challenge-01/PREFLIGHT-INPUTS-01.json').read_bytes())
pins = {row['source']: row for row in baseline['files']}


def data(path):
    row = pins[path]
    raw = (ROOT / row['snapshot']).read_bytes()
    if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
        raise ValueError('Frozen identity changed: ' + path)
    return raw


def doc(path):
    return parse(data(path))


command = {'at': datetime.now(timezone.utc).isoformat(), 'argv': ['/usr/bin/python3', '-I', '-B', '-S', 'coordination/receipt-challenge-01/review/attempt-01/preflight_check.py'], 'cwd': str(ROOT), 'source_sha256': sha(Path(__file__).read_bytes())}
put('COMMAND.json', encoded(command))
put('check.py', Path(__file__).read_bytes())
try:
    supplement_raw = (ROOT / '.scratch/receipt-challenge-01/PREFLIGHT-SOURCES-01.json').read_bytes()
    supplement = parse(supplement_raw)
    put('PREFLIGHT-SOURCES-01.json', supplement_raw)
    for row in supplement['files']:
        for kind in ('source', 'snapshot'):
            raw = (ROOT / row[kind]).read_bytes()
            check('supplement ' + kind + ': ' + row['source'], len(raw) == row['bytes'] and sha(raw) == row['sha256'])
    recipe_raw = (ROOT / 'src/stewart/resources/QUESTION-TYPE.md').read_bytes()
    origins = doc('.scratch/receipt-challenge-01/subject/ORIGINS.json')
    recipe_pin = origins['recipe_source']
    check('recipe source identity', len(recipe_raw) == recipe_pin['bytes'] and sha(recipe_raw) == recipe_pin['sha256'])
    lines = recipe_raw.splitlines(keepends=True)
    start, end = origins['recipe_lines']
    check('unchanged recipe exact source range', b''.join(lines[start-1:end]) == data('.scratch/receipt-challenge-01/subject/RECIPE.md'), {'first': start, 'last': end})
    check('recipe section starts at intended heading', lines[start-1].strip() == b'## Receipt sufficiency')
    check('recipe section ends before next section', lines[end].startswith(b'## '))
    git_argv = ['/usr/bin/git', 'show', supplement['git_object']]
    proc = subprocess.run(git_argv, cwd=ROOT, capture_output=True)
    put('git.stdout', proc.stdout)
    put('git.stderr', proc.stderr)
    put('GIT.json', encoded({'argv': git_argv, 'cwd': str(ROOT), 'exit': proc.returncode, 'stdout_sha256': sha(proc.stdout), 'stderr_bytes': len(proc.stderr)}))
    check('exact authorized Git source read exit', proc.returncode == 0)
    check('Git source read stderr empty', proc.stderr == b'')
    helper = data('coordination/receipt-challenge-01/capture.py')
    check('candidate writer matches exact Git object', proc.stdout == data('.scratch/receipt-challenge-01/subject/capture.py'))
    check('new helper matches exact Git object', proc.stdout == helper)
    inventory_raw = data('.scratch/answer-revision-01/EVIDENCE-INVENTORY-01.json')
    inventory = parse(inventory_raw)
    completion = doc('.scratch/answer-revision-01/COMPLETION.json')
    check('completion pins prior inventory', completion['evidence_inventory']['bytes'] == len(inventory_raw) and completion['evidence_inventory']['sha256'] == sha(inventory_raw))
    check('origins pins same prior inventory', origins['prior_inventory']['bytes'] == len(inventory_raw) and origins['prior_inventory']['sha256'] == sha(inventory_raw))
    old_rows = inventory['files']
    old_by_path = {row['path']: row for row in old_rows}
    check('prior inventory identities are unambiguous', len(old_by_path) == len(old_rows), {'entries': len(old_rows)})
    selected_rows = []
    for origin in origins['files']:
        subject = data('.scratch/receipt-challenge-01/subject/' + origin['packet_file'])
        check('subject matches origin: ' + origin['packet_file'], len(subject) == origin['bytes'] and sha(subject) == origin['sha256'])
        if origin['packet_file'] != 'capture.py':
            expected = {'path': origin['path'], 'bytes': len(subject), 'sha256': sha(subject)}
            check('subject matches prior inventory: ' + origin['packet_file'], old_by_path.get(origin['path']) == expected)
            selected_rows.append(old_by_path.get(origin['path']))
    put('PRIOR-SELECTED-ROWS.json', encoded(selected_rows))
    manifest = doc('.scratch/receipt-challenge-01/subject/MANIFEST.json')
    check('subject manifest exact seven-file population', {r['file'] for r in manifest['files']} == {'ACCEPTED.json', 'ORIGINS.json', 'QUESTION.md', 'RECIPE.md', 'SNAPSHOT.json', 'capture.py', 'payload.raw'} and len(manifest['files']) == 7)
    for row in manifest['files']:
        raw = data('.scratch/receipt-challenge-01/subject/' + row['file'])
        check('subject manifest identity: ' + row['file'], len(raw) == row['bytes'] and sha(raw) == row['sha256'])
    check('packet question equals issued question', data('.scratch/receipt-challenge-01/subject/QUESTION.md') == data('coordination/receipt-challenge-01/QUESTION.md'))
    author_texts = []
    for author in ('a01', 'a02'):
        brief = data('coordination/receipt-challenge-01/authors/' + author + '/BRIEF.md').decode()
        before, rest = brief.split('Your assigned form is ', 1)
        _, after = rest.split('Both forms have ', 1)
        author_texts.append((before + 'Both forms have ' + after).replace(author, 'AUTHOR'))
    check('author grant and output duties identical apart from form and actor coordinates', author_texts[0] == author_texts[1])
    raw = data('.scratch/receipt-challenge-01/subject/payload.raw')
    payload = parse(raw)
    snapshot = doc('.scratch/receipt-challenge-01/subject/SNAPSHOT.json')
    accepted = doc('.scratch/receipt-challenge-01/subject/ACCEPTED.json')
    raw_id = {'bytes': len(raw), 'sha256': sha(raw)}
    check('acceptance binds supplied raw bytes', accepted['raw_transport'] == raw_id)
    check('snapshot binds supplied raw bytes', snapshot['byte_observations']['raw_transport'] == raw_id)
    check('snapshot envelope exactly equals decoded raw payload', snapshot['envelope'] == payload)
    check('acceptance and snapshot metadata agree', accepted['capture_metadata'] == snapshot['capture_metadata'])
    check('payload question/source match capture expected identity', accepted['capture_metadata']['expected_identity'] == {key: payload[key] for key in ('question_id', 'source_revision')})
    check('historical capture issued provenance labels a03 phase 02', accepted['capture_metadata']['issued_provenance'] == {'author_id': 'a03', 'phase': '02'})
    check('acceptance retains no intellectual assessment', accepted['intellectual_assessment'] == 'not_performed')
    check('snapshot retains no intellectual assessment', snapshot['intellectual_assessment'] == 'not_performed')
    observations = snapshot['byte_observations']
    primary = payload['answer'].encode()
    check('snapshot primary exact UTF-8 binding', observations['decoded_primary_text_utf8'] == {'bytes': len(primary), 'sha256': sha(primary)})
    expected_items = []
    for i, item in enumerate(payload['support']):
        value = item['text'].encode()
        expected_items.append({'position': i, 'id': item['id'], 'bytes': len(value), 'sha256': sha(value)})
    check('snapshot ordered artifact exact UTF-8 bindings', observations['decoded_artifact_text_utf8_in_submission_order'] == expected_items)
    check('snapshot decoded text byte total', observations['decoded_primary_and_artifact_utf8_bytes'] == len(primary) + sum(i['bytes'] for i in expected_items))
    reconstruction = (json.dumps(snapshot['envelope'], ensure_ascii=False, indent=2) + '\n').encode()
    put('reconstructed-payload.raw', reconstruction)
    reconstruction_result = {'method': "(json.dumps(snapshot['envelope'], ensure_ascii=False, indent=2) + '\\n').encode('utf-8')", 'bytes': len(reconstruction), 'sha256': sha(reconstruction), 'equals_original': reconstruction == raw, 'matches_acceptance': {'bytes': len(reconstruction), 'sha256': sha(reconstruction)} == accepted['raw_transport'], 'source': 'frozen subject SNAPSHOT.json; no subject/helper execution'}
    put('RECONSTRUCTION.json', encoded(reconstruction_result))
    alternative = json.dumps(snapshot['envelope'], ensure_ascii=False, separators=(',', ':')).encode()
    put('alternate-serialization.raw', alternative)
    check('serialization distinction fires for raw digest', sha(alternative) != sha(raw))
    check('serialization control decoded envelope invariant', parse(alternative) == payload)
    check('serialization control primary bytes invariant', parse(alternative)['answer'].encode() == primary)
    check('serialization control ordered artifact bytes invariant', [i['text'].encode() for i in parse(alternative)['support']] == [i['text'].encode() for i in payload['support']])
    historical = doc('.scratch/answer-revision-01/transport/attempt-01/check-run-01/RESULT.json')
    summary = doc('coordination/answer-revision-01/transport/attempt-01/CHECK-RESULT.json')
    check('prior qualification helper identity is current byte identity', historical['helper_identity'] == {'bytes': len(helper), 'sha256': sha(helper)})
    check('prior summary and run count 571 assertions', historical['assertions'] == summary['assertions'] == 571)
    check('prior run retains 41 unique capture invocations', len(historical['invocations']) == historical['helper_invocations'] == 41 and len({i['name'] for i in historical['invocations']}) == 41)
    forms = Counter(i['name'].split('-', 1)[0] for i in historical['invocations'])
    check('prior recorded form split matches summary', dict(forms) == summary['capture_invocations_by_form'] == {'common': 22, 'minimal': 19})
    check('prior extra help is separate from captures', summary['additional_help_invocations'] == 1 and summary['all_helper_invocations'] == 42)
    check('prior scope excludes subject and installed-wheel tests', historical['project_subject_executions'] == historical['installed_wheel_pytest_nodes'] == 0)
    for name in ('common', 'minimal'):
        names = {i['name'] for i in historical['invocations']}
        check('prior ' + name + ' distinguishing and invariance names recorded', all(name + '-' + case in names for case in ('baseline', 'changed-artifact', 'reordered', 'escaped-json')))
    for source in ('coordination/receipt-challenge-01/capture.py', 'coordination/receipt-challenge-01/ops.py'):
        tree = ast.parse(data(source))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        check('static syntax and standard-library imports: ' + source, set(imports) <= {'argparse', 'datetime', 'hashlib', 'json', 'math', 'os', 'pathlib', 'signal', 'subprocess', 'sys'}, imports)
    result = {'status': 'passed' if all(r['passed'] for r in checks) else 'failed', 'checks': checks, 'passed': sum(r['passed'] for r in checks), 'total': len(checks), 'reconstruction': reconstruction_result, 'subject_executions': 0, 'helper_executions': 0, 'ops_executions': 0, 'pytest_nodes': 0, 'git_read_only_invocations': 1, 'historical_helper_counts_reused': {'assertions': 571, 'captures': 41, 'help': 1}, 'observer_scope': 'Static byte/source/retained-record inspection; no continuous monitoring, access-enforcement or historical-execution claim.'}
except Exception as exc:
    result = {'status': 'review_check_error', 'exception': type(exc).__name__ + ': ' + str(exc), 'checks': checks, 'passed': sum(r['passed'] for r in checks), 'total': len(checks)}
put('RESULT.json', encoded(result))
put('stdout.txt', encoded(result))
print(json.dumps(result, indent=2))
sys.exit(0 if result['status'] == 'passed' else 1)
