"""Independent static review of frozen bytes; no study/subject import or execution."""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / '.scratch/answer-revision-01/review/attempt-01/static-check-01'
OUT.mkdir()
REV = '5f00082d86768368478ed7cc85b52dd56a60255b'
checks = []


def write(name, raw):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def dump(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def check(condition, name, detail=None):
    checks.append({'name': name, 'passed': bool(condition), 'detail': detail})


write('COMMAND.json', dump({'argv': [sys.executable, '-I', '-B', '-S', str(Path(__file__).resolve())],
                          'cwd': os.getcwd(), 'pid': os.getpid(),
                          'at': datetime.now(timezone.utc).isoformat(),
                          'observer': 'Independent static reader; snapshots and retained output only. Git show reads source objects; no subject or transport execution.'}))
write('check.py', Path(__file__).read_bytes())
admitted = {}
bindings = []
for manifest_name, wanted in [('REVIEW-INPUTS-01.json', 117), ('REVIEW-TRANSPORT-INPUTS-01.json', 471)]:
    path = ROOT / '.scratch/answer-revision-01' / manifest_name
    raw = path.read_bytes()
    write(manifest_name, raw)
    document = json.loads(raw)
    bindings.append({'path': str(path.relative_to(ROOT)), **identity(raw), 'entries': len(document['inputs'])})
    check(len(document['inputs']) == wanted, manifest_name + ' count')
    check(len({item['path'] for item in document['inputs']}) == wanted, manifest_name + ' unique originals')
    mapping = {}
    current_changes = []
    for item in document['inputs']:
        snap = ROOT / item['snapshot']
        raw = snap.read_bytes()
        check(identity(raw) == {'bytes': item['bytes'], 'sha256': item['sha256']}, 'snapshot binding: ' + item['snapshot'])
        mapping[item['path']] = raw
        current = ROOT / item['path']
        if not current.exists() or current.read_bytes() != raw:
            current_changes.append(item['path'])
    admitted[manifest_name] = mapping
    write(manifest_name + '.live-differences.json', dump(current_changes))
write('ADMITTED.json', dump(bindings))
initial = admitted['REVIEW-INPUTS-01.json']
transport = admitted['REVIEW-TRANSPORT-INPUTS-01.json']


def first(path):
    return initial['.scratch/answer-revision-01/' + path]


def t(path):
    return transport['.scratch/answer-revision-01/transport/attempt-01/' + path]


selection = json.loads(first('SOURCE-SELECTION.json'))
check(selection['revision'] == REV, 'selection revision')
sources = {}
for item in selection['selections']:
    source = item['source_path']
    if source not in sources:
        argv = ['/usr/bin/git', 'show', REV + ':' + source]
        proc = subprocess.run(argv, cwd=ROOT, capture_output=True)
        name = 'git/' + source.replace('/', '__')
        write(name + '.COMMAND.json', dump({'argv': argv, 'cwd': str(ROOT)}))
        write(name + '.stdout', proc.stdout)
        write(name + '.stderr', proc.stderr)
        write(name + '.OUTCOME.json', dump({'exit': proc.returncode}))
        witness = first('witness/source/' + source)
        check(proc.returncode == 0 and proc.stderr == b'' and proc.stdout == witness, 'Git object equals source witness: ' + source)
        sources[source] = witness
    raw = sources[source]
    check(identity(raw) == {'bytes': item['source_bytes'], 'sha256': item['source_sha256']}, 'source identity: ' + item['packet_file'])
    expected = b''
    lines = raw.splitlines(keepends=True)
    for start, end in item['ranges']:
        check(1 <= start <= end <= len(lines), 'range bounds: ' + item['packet_file'])
        expected += ('--- %s:%s, original lines %s-%s ---\n' % (REV, source, start, end)).encode()
        expected += b''.join(lines[start - 1:end]) + b'\n'
    packet = first('subject/' + item['packet_file'])
    check(packet == expected, 'exact source extraction: ' + item['packet_file'])
    check(identity(packet) == {'bytes': item['packet_bytes'], 'sha256': item['packet_sha256']}, 'excerpt identity: ' + item['packet_file'])
    check((ROOT / '.scratch/answer-revision-01/subject' / item['packet_file']).read_bytes() == packet, 'live excerpt frozen: ' + item['packet_file'])

symbols = [('declaration-source.txt', 'session_declaration_expectations'), ('consumer-source.txt', '_auditor_report'),
           ('audit-id-source.txt', 'audit_id'), ('error-source.txt', 'StewartError')]
for name, symbol in symbols:
    item = next(item for item in selection['selections'] if item['packet_file'] == name)
    node = next(node for node in ast.parse(sources[item['source_path']]).body if getattr(node, 'name', None) == symbol)
    start, end = item['ranges'][0]
    check(end == node.end_lineno and (start == 1 if name == 'declaration-source.txt' else start == node.lineno), 'complete selected definition: ' + symbol)
recipe = next(item for item in selection['selections'] if item['packet_file'] == 'RECIPE.md')
recipe_lines = sources[recipe['source_path']].splitlines()
check(recipe['ranges'] == [[recipe_lines.index(b'## Information preservation') + 1,
                            recipe_lines.index(b'## Constrained experiment construction')]], 'unchanged complete information-preservation recipe')

subject_paths = {path.removeprefix('.scratch/answer-revision-01/subject/'): raw for path, raw in initial.items()
                 if path.startswith('.scratch/answer-revision-01/subject/')}
packets = {}
for author, schedule in [('a01', 'delayed'), ('a02', 'complete'), ('a03', 'complete'), ('a04', 'delayed')]:
    prefix = 'grants/' + author + '/phase-01/'
    manifest = json.loads(first(prefix + 'MANIFEST.json'))
    check(manifest['question_id'] == 'declaration-status-preservation-01' and manifest['source_revision'] == REV and manifest['no_subject_execution'] is True, author + ' packet identities')
    files = {item['file']: item for item in manifest['files']}
    check(len(files) == len(manifest['files']), author + ' unique file membership')
    expected_names = set(subject_paths) | {'AVAILABILITY.md'}
    if schedule == 'delayed':
        expected_names.remove('consumer-source.txt')
    check(set(files) == expected_names, author + ' intended subject membership')
    directory = ROOT / '.scratch/answer-revision-01' / prefix
    check({p.name for p in directory.iterdir()} == expected_names | {'MANIFEST.json'}, author + ' no extra live packet entry')
    packet = {}
    for name, item in files.items():
        raw = first(prefix + name)
        check(identity(raw) == {'bytes': item['bytes'], 'sha256': item['sha256']} and (directory / name).read_bytes() == raw, author + ' member bytes: ' + name)
        packet[name] = raw
        if name != 'AVAILABILITY.md':
            check(raw == subject_paths[name], author + ' common source equality: ' + name)
    packets[author] = packet
    consumer_body = first('subject/consumer-source.txt').split(b'\n', 1)[1].strip()
    if schedule == 'delayed':
        check(all(consumer_body not in raw and b'def _auditor_report(' not in raw for raw in packet.values()), author + ' consumer implementation absent')
        check(b'has not been supplied' in packet['AVAILABILITY.md'], author + ' omission explicit')
    else:
        check(packet['consumer-source.txt'] == subject_paths['consumer-source.txt'], author + ' complete control consumer identity')
    release = first('releases/' + author + '/consumer-source.txt')
    release_manifest = json.loads(first('releases/' + author + '/MANIFEST.json'))
    check(release == subject_paths['consumer-source.txt'] and identity(release) == {key: release_manifest[key] for key in ('bytes', 'sha256')}, author + ' fixed release identity')
    check(release_manifest['previously_supplied'] == (schedule == 'complete'), author + ' release schedule')
    check((ROOT / '.scratch/answer-revision-01/releases' / author / 'consumer-source.txt').read_bytes() == release, author + ' live release remains frozen')
check(packets['a01'] == packets['a04'], 'delayed evidence matches across forms')
check(packets['a02'] == packets['a03'], 'complete evidence matches across forms')
check({k: v for k, v in packets['a01'].items() if k != 'AVAILABILITY.md'} ==
      {k: v for k, v in packets['a02'].items() if k not in {'AVAILABILITY.md', 'consumer-source.txt'}}, 'schedule changes only consumer and notice')

entries = json.loads(first('subject/ENTRIES.json'))
check(len(entries['reports']) == 6, 'six hypothetical report fixtures')
check('hypothetical' in entries['status'] and 'not executed' in entries['status'], 'fixtures labeled hypothetical')
for item in entries['reports']:
    raw = first('subject/' + item['file'])
    check(identity(raw) == {key: item[key] for key in ('bytes', 'sha256')} and item['expected_digest'] == item['sha256'], 'fixture byte/digest identity: ' + item['file'])


def payload(name):
    return first('subject/' + name).split(b'```audit-report\n', 1)[1].split(b'\n```', 1)[0]


valid = json.loads(payload('report-valid.md'))
mismatch = json.loads(payload('report-mismatch.md'))
partial = json.loads(payload('report-partial-null.md'))
session = entries['session_record']
expected = {'audit_id': session['assignment']['audit_id'], 'target_commit': session['target_commit'],
            'launch_prompt_commit': session['prompt_commit'], 'prompt_sha256': session['prompt_sha256'],
            'launch_token': session['launch_token'], 'observed_checkout_commit': entries['collected_head']}
check({key: valid[key] for key in expected} == expected, 'valid fixture exactly matches all stipulated identities')
check(valid['schema_version'] == 2 and valid['completion'] == 'complete' and valid['report_kind'] == 'answer', 'valid fixture claim fields')
check({key for key in valid if valid[key] != mismatch[key]} == {'target_commit'} and mismatch['target_commit'] == 'f' * 40, 'mismatch changes only target identity')
check({key for key in valid if valid[key] != partial[key]} == {'completion', 'report_kind'} and partial['completion'] == 'partial' and partial['report_kind'] is None, 'partial/null fixture changes only declared claim values')
check(b'```audit-report' not in first('subject/report-missing.md') and b'complete' in first('subject/report-missing.md'), 'missing declaration despite completion prose')
invalid_pairs = json.loads(payload('report-invalid.md'), object_pairs_hook=list)
check([value for key, value in invalid_pairs if key == 'completion'] == ['partial', 'complete'], 'invalid fixture retains both competing completion keys')
check(payload('report-valid.md') == payload('report-prose-variant.md') and first('subject/report-valid.md') != first('subject/report-prose-variant.md'), 'prose-only invariance fixture')

helper = transport['coordination/answer-revision-01/transport/attempt-01/capture.py']
check(helper == t('check-run-01/capture.py'), 'reviewed helper equals executed source copy')
helper_ast = ast.parse(helper)
old_ast = ast.parse(t('check-run-01/pinned-submit.py'))
old_fn = next(node for node in old_ast.body if getattr(node, 'name', None) == 'decode_validate')
new_fn = next(node for node in helper_ast.body if getattr(node, 'name', None) == 'validate_common')
split = next(i for i, node in enumerate(old_fn.body) if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'require_fields')
check([ast.dump(node) for node in old_fn.body[split:]] == [ast.dump(node) for node in new_fn.body], 'common validator unchanged from pinned prototype')
report = json.loads(t('check-run-01/RESULT.json'))
check(report['status'] == 'passed' and report['error'] is None and report['assertions'] == 571, 'retained transport assertion count/status')
check(len(report['invocations']) == report['helper_invocations'] == 41, 'retained transport 41 capture invocations')
check(Counter(item['name'].split('-', 1)[0] for item in report['invocations']) == {'common': 22, 'minimal': 19}, 'transport form counts')
observed = {}
for invocation in report['invocations']:
    name = invocation['name']
    prefix = 'check-run-01/' + name + '/'
    command = json.loads(t(prefix + 'COMMAND.json'))
    process = json.loads(t(prefix + 'PROCESS.json'))
    outcome = json.loads(t(prefix + 'OUTCOME.json'))
    emission = json.loads(t(prefix + 'stdout.raw'))
    raw = t(prefix + 'input.raw')
    form = name.split('-', 1)[0]
    check(process['pid'] == outcome['pid'] == invocation['pid'] and outcome == invocation, name + ' process/outcome binding')
    check(command['argv'][1:4] == ['-I', '-B', '-S'] and command['input_identity'] == identity(raw) and command['witness_saved_before_launch'] is True, name + ' isolated command and independent input')
    check(t(prefix + 'stderr.raw') == b'' and outcome['exit_code'] == (0 if emission['reason'] == 'structure_accepted' else 2), name + ' exit and stderr')
    if emission['reason'] == 'destination_exists':
        check(emission['retained_by_this_invocation'] == [] and not any(key.startswith('.scratch/answer-revision-01/transport/attempt-01/' + prefix + 'capture/') for key in transport), name + ' reuse does not claim new capture')
        continue
    check(t(prefix + 'capture/attempt.raw') == raw, name + ' raw outside witness equals captured bytes')
    if emission['reason'] != 'structure_accepted':
        failure = json.loads(t(prefix + 'capture/FAILURE.json'))
        check(failure == emission and failure['input_capture_complete'] is True and failure['raw_transport'] == {'bytes_read': len(raw), 'sha256_of_bytes_read': identity(raw)['sha256']}, name + ' preserved rejected input and diagnostic')
        continue
    snap = json.loads(t(prefix + 'capture/SNAPSHOT.json'))
    accepted = json.loads(t(prefix + 'capture/ACCEPTED.json'))
    check(accepted == emission and snap['envelope'] == json.loads(raw), name + ' complete selected payload preserved')
    obs = snap['byte_observations']
    text_key, array_key, id_key = ('answer', 'support', 'id') if form == 'common' else ('text', 'artifacts', 'name')
    primary = t(prefix + 'expected-primary.utf8')
    check(snap['envelope'][text_key].encode('utf-8') == primary and obs['decoded_primary_text_utf8'] == identity(primary), name + ' independent decoded primary witness')
    artifact_observations = []
    for i, item in enumerate(snap['envelope'][array_key]):
        witness = t(prefix + 'expected-artifact-%02d.utf8' % i)
        check(item['text'].encode('utf-8') == witness, name + ' independent artifact witness ' + str(i))
        artifact_observations.append({'position': i, id_key: item[id_key], **identity(witness)})
    check(obs['raw_transport'] == identity(raw) and obs['decoded_artifact_text_utf8_in_submission_order'] == artifact_observations, name + ' observed raw and ordered artifact identities')
    check(obs['decoded_primary_and_artifact_utf8_bytes'] == len(primary) + sum(item['bytes'] for item in artifact_observations), name + ' selected byte total')
    check(snap['capture_metadata'] == emission['capture_metadata'] and snap['intellectual_assessment'] == 'not_performed', name + ' separate provenance and no verdict')
    observed[name] = snap
for form in ('common', 'minimal'):
    baseline = observed[form + '-baseline']
    changed = observed[form + '-changed-artifact']
    reordered = observed[form + '-reordered']
    escaped = observed[form + '-escaped-json']
    b, c = baseline['byte_observations'], changed['byte_observations']
    check(b['decoded_artifact_text_utf8_in_submission_order'][0]['sha256'] != c['decoded_artifact_text_utf8_in_submission_order'][0]['sha256'], form + ' changed-artifact control fires')
    check(b['decoded_artifact_text_utf8_in_submission_order'][1] == c['decoded_artifact_text_utf8_in_submission_order'][1] and b['decoded_primary_text_utf8'] == c['decoded_primary_text_utf8'], form + ' untouched artifact and primary invariant')
    id_key = 'id' if form == 'common' else 'name'
    def by_name(snap):
        return {item[id_key]: {key: item[key] for key in ('bytes', 'sha256')} for item in snap['byte_observations']['decoded_artifact_text_utf8_in_submission_order']}
    check(by_name(baseline) == by_name(reordered), form + ' reorder invariant by artifact identity')
    check(baseline['envelope'] == escaped['envelope'] and b['raw_transport'] != escaped['byte_observations']['raw_transport'], form + ' alternate JSON syntax preserves decoded content')
check(json.loads(t('help.OUTCOME.json'))['exit_code'] == 0 and t('help.stderr') == b'' and b'--form' in t('help.stdout'), 'separately captured help passed')

failures = [item for item in checks if not item['passed']]
result = {'status': 'passed' if not failures else 'failed', 'assertions': len(checks),
          'passed': len(checks) - len(failures), 'failed': len(failures), 'failures': failures,
          'bindings': bindings, 'checks': checks, 'subject_executions': 0,
          'transport_executions_by_this_review': 0, 'installed_wheel_pytest_nodes': 0,
          'git_source_reads': len(sources), 'at': datetime.now(timezone.utc).isoformat()}
write('RESULT.json', dump(result))
print(json.dumps({key: result[key] for key in ('status', 'assertions', 'passed', 'failed', 'failures', 'subject_executions', 'transport_executions_by_this_review', 'installed_wheel_pytest_nodes', 'git_source_reads')}, indent=2))
sys.exit(0 if not failures else 1)
