"""Independent frozen-evidence checks. Imports/executes no study or subject code."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / '.scratch/answer-revision-01/review/attempt-01/integration-check-01'
OUT.mkdir()
PREFIX = '.scratch/answer-revision-01/'
DOC = 'coordination/answer-revision-01/'
checks, observations = [], []


def put(name, raw):
    with (OUT / name).open('xb') as stream:
        stream.write(raw)


def dump(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def ident(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def check(name, condition, detail=None):
    checks.append({'name': name, 'passed': bool(condition), 'detail': detail})


manifest_raw = (REPO / PREFIX / 'INTEGRATION-INPUTS-01.json').read_bytes()
manifest = json.loads(manifest_raw)
put('INTEGRATION-INPUTS-01.json', manifest_raw)
put('check.py', Path(__file__).read_bytes())
put('COMMAND.json', dump({'argv': [sys.executable, '-I', '-B', '-S', str(Path(__file__).resolve())],
                         'cwd': os.getcwd(), 'pid': os.getpid(), 'at': datetime.now(timezone.utc).isoformat(),
                         'scope': 'Read frozen snapshots; no subject, helper or coordinator utility execution.'}))
check('1,745 admitted snapshots', len(manifest['files']) == 1745)
check('unique admitted source identities', len({r['source'] for r in manifest['files']}) == 1745)
check('unique snapshot paths', len({r['snapshot'] for r in manifest['files']}) == 1745)
data = {}
for row in manifest['files']:
    path = REPO / row['snapshot']
    raw = path.read_bytes()
    check('snapshot binding: ' + row['source'], stat.S_ISREG(path.lstat().st_mode) and ident(raw) == {k: row[k] for k in ('bytes', 'sha256')})
    data[row['source']] = raw


def raw(path):
    return data[path]


def load(path):
    return json.loads(raw(path))


def pin(row, path):
    check('referenced identity: ' + path, ident(raw(path)) == {k: row[k] for k in ('bytes', 'sha256')})


old = json.loads((REPO / PREFIX / 'review/attempt-01/static-check-01/REVIEW-INPUTS-01.json').read_bytes())
for row in old['inputs']:
    if row['path'] in data and row['path'] not in ('coordination/COORDINATOR-NOTES.md', DOC + 'PROGRESS.md'):
        check('preflight design unchanged: ' + row['path'], ident(raw(row['path'])) == {k: row[k] for k in ('bytes', 'sha256')})
check('reviewed helper unchanged', ident(raw(DOC + 'transport/attempt-01/capture.py'))['sha256'] == '05ae9f5a12d2fa12daa46c63bef3eadd6ca93577828d09ed404a8432dbd73c52')
check('reviewed coordinator utility unchanged', ident(raw(DOC + 'study_ops.py'))['sha256'] == '11fe44f36802c468f8884caf13579fb9d99a051663ba36c8c56b1760f963749f')
root_checks = load(PREFIX + 'INTEGRATION-CHECKS-01.json')
check('root reports 774 actual passing assertions', len(root_checks['checks']) == root_checks['total'] == root_checks['passed'] == 774 and all(c['passed'] for c in root_checks['checks']))
root_command = load(PREFIX + 'INTEGRATION-COMMAND-01.json')
check('root check completed with retained streams', root_command['exit'] == 0 and raw(root_command['stderr']) == b'' and raw(root_command['stdout']).strip() == b'774 / 774 static integration checks')

forms = {'a01': 'common', 'a02': 'minimal', 'a03': 'common', 'a04': 'minimal'}
author_barriers = {phase: load(PREFIX + 'AUTHOR-PHASE-' + phase + '-FROZEN.json') for phase in ('01', '02')}
reader_barriers = {phase: load(PREFIX + 'READER-PHASE-' + phase + '-FROZEN.json') for phase in ('01', '02')}
author_activation = load(PREFIX + 'AUTHOR-RELEASE-ACTIVATION.json')
reader_activation = load(PREFIX + 'READER-RELEASE-ACTIVATION.json')
check('author release references exact first barrier', author_activation['barrier_sha256'] == ident(raw(PREFIX + 'AUTHOR-PHASE-01-FROZEN.json'))['sha256'])
check('author activation follows first barrier', author_barriers['01']['at'] <= author_activation['at'])
check('reader activation follows first freeze', reader_barriers['01']['at'] <= reader_activation['at'])
for row in reader_activation['files']:
    pin(row, row['path'])
for phase in ('01', '02'):
    barrier = author_barriers[phase]
    check('four unique author captures in phase ' + phase, {r['author'] for r in barrier['captures']} == set(forms) and len(barrier['captures']) == 4)
    for capture in barrier['captures']:
        check(capture['author'] + phase + ' barrier phase identity', capture['phase'] == phase)
        for row in capture['files']:
            pin(row, row['path'])
    for row in reader_barriers[phase]['files']:
        pin(row, row['snapshot'])
        if Path(row['source']).name in ('FIRST.md', 'SECOND.md', 'READS-FIRST.json', 'READS-SECOND.json'):
            check('frozen recipient content: ' + row['source'] + ' phase ' + phase, raw(row['source']) == raw(row['snapshot']))

packets, payloads = {}, {}
for author, form in forms.items():
    reader = 'r' + author[1:]
    for phase in ('01', '02'):
        label = author + '/' + phase
        c = PREFIX + 'captures/' + author + '/phase-' + phase + '/'
        p = PREFIX + 'recipient-packets/' + reader + '/phase-' + phase + '/'
        selected = raw(DOC + 'authors/' + author + '/attempt-01/SELECTED-' + phase + '.json')
        for q in (c + 'input.raw', c + 'helper/attempt.raw', c + 'author-files/SELECTED-' + phase + '.json', p + 'RETURN.raw'):
            check(label + ' exact selected bytes: ' + q, raw(q) == selected)
        payload = json.loads(selected)
        payloads[author, phase] = payload
        snap, accept = load(c + 'helper/SNAPSHOT.json'), load(c + 'helper/ACCEPTED.json')
        command, pid, outcome = load(c + 'COMMAND.json'), load(c + 'PID.json'), load(c + 'EXIT.json')
        cc = load(c + 'CAPTURE-CHECKS.json')
        check(label + ' isolated explicit command', command['argv'][:4] == ['/usr/bin/python3', '-I', '-B', '-S'] and command['argv'][-1] == phase)
        check(label + ' successful bound process and streams', pid['pid'] == outcome['pid'] and outcome['exit'] == 0 and raw(c + 'stderr') == b'' and load(c + 'stdout') == accept)
        check(label + ' capture checks reflect ten successes', cc['total'] == cc['passed'] == len(cc['checks']) == 10 and cc['helper_exit'] == 0 and all(v['passed'] for v in cc['checks']))
        check(label + ' witness/process/return ordering', load(c + 'PLAN.json')['at'] <= load(c + 'freeze.json')['at'] <= command['at'] <= pid['at'] <= outcome['at'] <= cc['at'] <= author_barriers[phase]['at'])
        if phase == '02':
            check(label + ' second capture after source activation', command['at'] >= author_activation['at'])
        check(label + ' decoded payload unchanged', snap['envelope'] == payload)
        check(label + ' exact separate capture identity', snap['capture_metadata'] == {
            'form': form, 'expected_identity': {'question_id': 'declaration-status-preservation-01', 'source_revision': '5f00082d86768368478ed7cc85b52dd56a60255b'},
            'issued_provenance': {'author_id': author, 'phase': phase},
            'provenance_source': 'explicit coordinator CLI arguments; not inferred from submitted text'})
        common = form == 'common'
        text = payload['answer' if common else 'text'].encode('utf-8')
        items = payload['support' if common else 'artifacts']
        return_manifest = load(p + 'RETURN-MANIFEST.json')
        check(label + ' raw and primary identities', snap['byte_observations']['raw_transport'] == ident(selected) and accept['raw_transport'] == ident(selected) and raw(p + 'primary.txt') == text and snap['byte_observations']['decoded_primary_text_utf8'] == ident(text))
        check(label + ' ordered artifact count', len(items) == len(return_manifest['artifacts']))
        expected_artifact_observations = []
        for i, (item, entry) in enumerate(zip(items, return_manifest['artifacts'])):
            key = 'id' if common else 'name'
            b = item['text'].encode('utf-8')
            check(label + ' exact artifact ' + str(i), raw(p + entry['file']) == b and ident(b) == {k: entry[k] for k in ('bytes', 'sha256')} and entry['submitted_name'] == item[key] and (entry['submitted_role'] == item['role'] if common else 'submitted_role' not in entry))
            expected_artifact_observations.append({'position': i, key: item[key], **ident(b)})
        check(label + ' decoded observations retain order/association', snap['byte_observations']['decoded_artifact_text_utf8_in_submission_order'] == expected_artifact_observations)
        selected_text_bytes = len(text) + sum(len(i['text'].encode('utf-8')) for i in items)
        check(label + ' decoded byte sum', snap['byte_observations']['decoded_primary_and_artifact_utf8_bytes'] == selected_text_bytes)
        check(label + ' common claims retained/minimal not invented', return_manifest.get('submitted_metadata') == {k: payload[k] for k in ('question_id', 'source_revision', 'author', 'response_kind', 'completion_claim')} if common else 'submitted_metadata' not in return_manifest)
        inv = load(p + 'PACKET.json')
        expected_names = {r['file'] for r in inv['files']} | {'PACKET.json'}
        actual_names = {q[len(p):] for q in data if q.startswith(p)}
        check(label + ' packet unique/exhaustive membership', expected_names == actual_names and len(expected_names) == len(inv['files']) + 1)
        for row in inv['files']:
            pin(row, p + row['file'])
        expected_top = {'PACKET.json', 'RETURN.raw', 'RETURN-MANIFEST.json', 'primary.txt'} | {'artifact-%02d.txt' % (i + 1) for i in range(len(items))}
        check(label + ' no process/scratch bytes in recipient selection', {n for n in actual_names if '/' not in n} == expected_top)
        packet_subject = {n[len('subject/'):]: raw(p + n) for n in actual_names if n.startswith('subject/')}
        original_prefix = PREFIX + ('grants/' + author + '/phase-01/' if phase == '01' else 'subject/')
        original_subject = {q[len(original_prefix):]: b for q, b in data.items() if q.startswith(original_prefix)}
        if phase == '02':
            original_subject['AVAILABILITY.md'] = packet_subject['AVAILABILITY.md']
        check(label + ' exact subject membership/bytes', packet_subject == original_subject)
        check(label + ' consumer availability', ('consumer-source.txt' in packet_subject) == (phase == '02' or author in ('a02', 'a03')))
        if phase == '01' and author in ('a01', 'a04'):
            check(label + ' no consumer definition in recipient grant', not any(b'def _auditor_report(' in raw(p + name) for name in actual_names))
        packets[author, phase] = {r['file']: raw(p + r['file']) for r in inv['files']}
        observations.append({'author': author, 'phase': phase, 'form': form, 'raw_bytes': len(selected), 'selected_text_bytes': selected_text_bytes, 'artifacts': len(items), 'packet_entries': len(inv['files']), 'selection_sha256': ident(selected)['sha256']})
    for name in ('SELECTED-01.json', 'READS-01.json', 'PROCESS-01.md'):
        check(author + ' first record preserved: ' + name, raw(PREFIX + 'captures/' + author + '/phase-01/author-files/' + name) == raw(PREFIX + 'captures/' + author + '/phase-02/author-files/' + name) == raw(DOC + 'authors/' + author + '/attempt-01/' + name))
    for name in ('FIRST.md', 'READS-FIRST.json'):
        check(reader + ' first memo/account preserved: ' + name, raw(PREFIX + 'reader-freezes/' + reader + '/phase-01/' + name) == raw(PREFIX + 'reader-freezes/' + reader + '/phase-02/' + name) == raw(DOC + 'recipients/' + reader + '/attempt-01/' + name))
    check(author + ' fixed release equals preflight consumer', raw(PREFIX + 'releases/' + author + '/consumer-source.txt') == raw(PREFIX + 'subject/consumer-source.txt'))

check('a03 reselects exact same raw bytes', raw(PREFIX + 'captures/a03/phase-01/input.raw') == raw(PREFIX + 'captures/a03/phase-02/input.raw'))
for author in ('a01', 'a02', 'a04'):
    check(author + ' selected content changes', payloads[author, '01'] != payloads[author, '02'])
before = payloads['a02', '01']
after = payloads['a02', '02']
old_sentence = 'The supplied ENTRIES.json has a non-null HEAD, so all six identities are compared in the six report cases.'
new_sentence = 'The supplied ENTRIES.json has a non-null HEAD, so every successfully parsed declaration is compared on all six identities; the missing and invalid cases return before identity comparison, with empty comparisons.'
check('a02 route artifact only exact sentence correction', before['artifacts'][0]['text'].count(old_sentence) == 1 and before['artifacts'][0]['text'].replace(old_sentence, new_sentence) == after['artifacts'][0]['text'])
check('a02 second artifact unchanged', before['artifacts'][1] == after['artifacts'][1])
check('a02 original primary preserved with explicit note appended', after['text'].startswith(before['text']) and 'One scope sentence is corrected' in after['text'][len(before['text']):])
check('a01 formal kind tracks resolved gap', payloads['a01', '01']['response_kind'] == 'needs-evidence' and payloads['a01', '02']['response_kind'] == 'answer')
for author in forms:
    one, two = packets[author, '01'], packets[author, '02']
    subject_common = {k for k in one.keys() & two.keys() if k.startswith('subject/') and k != 'subject/AVAILABILITY.md'}
    check(author + ' substantive common subject unchanged', all(one[k] == two[k] for k in subject_common) and len(subject_common) == (14 if author in ('a01', 'a04') else 15))
    check(author + ' first subject manifest omitted explicitly in phase two', 'subject/MANIFEST.json' in one and 'subject/MANIFEST.json' not in two)

# Read/effect accounts are attributed statements, never complete access monitors.
ledger_rows = []
read_keys = ('paths_read', 'actual_paths_read', 'actual_additional_paths_read', 'read_paths', 'actual_content_read_paths', 'own_output_read_paths', 'own_output_reads', 'own_final_output_reads')
write_keys = ('output_paths', 'outputs_written', 'writes', 'written_paths', 'new_output_paths')
for source in sorted(data):
    if not source.startswith(DOC) or '/attempt-01/READS-' not in source or not any('/' + r + '/' in source for r in ('authors', 'recipients')):
        continue
    parts = source.split('/')
    role, actor = parts[2], parts[3]
    second = source.endswith('READS-02.json') or source.endswith('READS-SECOND.json')
    ledger = load(source)
    def paths(keys):
        result = []
        for key in keys:
            for entry in ledger.get(key, []):
                value = entry if isinstance(entry, str) else entry['path']
                result.append(value[len(str(REPO)) + 1:] if value.startswith(str(REPO) + '/') else value)
        return result
    reads, writes = paths(read_keys), paths(write_keys)
    own = [DOC + role + '/' + actor + '/attempt-01/', PREFIX + role + '/' + actor + '/attempt-01/']
    exact = {DOC + role + '/' + actor + '/BRIEF.md'}
    allowed = own[:]
    if role == 'authors':
        allowed.append(PREFIX + 'grants/' + actor + '/phase-01/')
        if second:
            allowed.append(PREFIX + 'releases/' + actor + '/')
            exact.add(DOC + role + '/' + actor + '/RELEASE-GRANT.md')
    else:
        allowed.append(PREFIX + 'recipient-packets/' + actor + '/phase-01/')
        if second:
            allowed.append(PREFIX + 'recipient-packets/' + actor + '/phase-02/')
            exact.add(DOC + role + '/' + actor + '/SECOND-GRANT.md')
    outside = [p for p in reads if p not in exact and not any(p.startswith(q) for q in allowed)]
    write_outside = [p for p in writes if not any(p.startswith(q) for q in own)]
    check('declared read grant: ' + source, bool(reads) and not outside, outside)
    check('declared write grant: ' + source, not write_outside, write_outside)
    if not second and actor in ('a01', 'a04', 'r01', 'r04'):
        check('no declared first-phase consumer read: ' + actor, not any(p.endswith('/consumer-source.txt') for p in reads))
    actions = ledger.get('commands_and_effects', ledger.get('actions', []))
    python_commands = []
    for action in actions:
        for key in ('command', 'interpreter_invocation'):
            command = action.get(key, '')
            if 'python3' in command and not command.startswith('command -v'):
                python_commands.append(command)
    check('declared isolated Python commands: ' + source, all('-I' in c and '-B' in c for c in python_commands))
    ledger_rows.append({'path': source, 'read_paths': reads, 'write_paths': writes, 'commands': actions, 'outside_read_grant': outside, 'outside_write_grant': write_outside})
check('all sixteen participant read accounts inspected', len(ledger_rows) == 16)
put('READ-ACCOUNT-INSPECTION.json', dump(ledger_rows))
put('OBSERVATIONS.json', dump(observations))
failures = [c for c in checks if not c['passed']]
result = {'input_manifest': {'path': PREFIX + 'INTEGRATION-INPUTS-01.json', **ident(manifest_raw), 'entries': 1745},
          'assertions': len(checks), 'passed': len(checks) - len(failures), 'failed': len(failures),
          'failures': failures, 'checks': checks, 'observations': observations,
          'subject_executions': 0, 'transport_invocations': 0, 'coordinator_utility_executions': 0,
          'installed_wheel_pytest_nodes': 0, 'at': datetime.now(timezone.utc).isoformat()}
put('RESULT.json', dump(result))
print(json.dumps({k: result[k] for k in ('input_manifest', 'assertions', 'passed', 'failed', 'failures', 'subject_executions', 'transport_invocations', 'coordinator_utility_executions', 'installed_wheel_pytest_nodes')}, indent=2))
sys.exit(0 if not failures else 1)
