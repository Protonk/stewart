"""Independent static verification of captured variants; no producer execution."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path('/Users/raccoon/Desktop/Experiments/stewart')
OUT = ROOT / '.scratch/receipt-challenge-01/review/attempt-01/variant-check-01'
OUT.mkdir(exist_ok=False)
checks = []


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def put(name, raw):
    with (OUT / name).open('xb') as handle:
        handle.write(raw)


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Repeated key: ' + repr(key))
        value[key] = item
    return value


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique)


def check(name, condition, detail=None):
    checks.append({'name': name, 'passed': bool(condition), 'detail': detail})


manifest_raw = (ROOT / '.scratch/receipt-challenge-01/VARIANT-INPUTS-01.json').read_bytes()
manifest = parse(manifest_raw)
pins = {row['source']: row for row in manifest['files']}


def data(source):
    row = pins[source]
    raw = (ROOT / row['snapshot']).read_bytes()
    if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
        raise ValueError('Changed frozen input: ' + source)
    return raw


def doc(source):
    return parse(data(source))


put('COMMAND.json', encode({'at': datetime.now(timezone.utc).isoformat(), 'argv': ['/usr/bin/python3', '-I', '-B', '-S', 'coordination/receipt-challenge-01/review/attempt-01/variant_check.py'], 'cwd': str(ROOT), 'baseline_sha256': sha(manifest_raw), 'code_sha256': sha(Path(__file__).read_bytes())}))
put('check.py', Path(__file__).read_bytes())
try:
    check('109 unambiguous frozen sources', len(pins) == len(manifest['files']) == 109)
    json_sources = [p for p in pins if p.endswith('.json')]
    for p in json_sources:
        doc(p)
    check('all frozen JSON inputs have unique decoded keys', True, {'files': len(json_sources)})
    prior = parse((ROOT / '.scratch/receipt-challenge-01/PREFLIGHT-INPUTS-01.json').read_bytes())
    prior_pins = {r['source']: r for r in prior['files']}
    for source in pins:
        if source.startswith('.scratch/receipt-challenge-01/subject/'):
            check('subject unchanged since preflight: ' + source, pins[source]['bytes'] == prior_pins[source]['bytes'] and pins[source]['sha256'] == prior_pins[source]['sha256'])
    check('capture helper remains admitted bytes', pins['coordination/receipt-challenge-01/capture.py']['sha256'] == '05ae9f5a12d2fa12daa46c63bef3eadd6ca93577828d09ed404a8432dbd73c52')
    check('capture wrapper remains admitted revision', pins['coordination/receipt-challenge-01/ops.py']['sha256'] == '676dc48425cc0f4de048791aeec829d3ac0188f977fdbb1ba72e37f80b73c34c')
    briefs = [data('coordination/receipt-challenge-01/recipients/' + r + '/BRIEF.md').decode().replace(r, 'READER') for r in ('r01', 'r02', 'r03', 'r04')]
    for n in range(1, 4):
        check('reader brief equal after coordinates: r0' + str(n+1), briefs[n] == briefs[0])
    subject_prefix = '.scratch/receipt-challenge-01/subject/'
    subject_raw = data(subject_prefix + 'payload.raw')
    subject_snapshot_raw = data(subject_prefix + 'SNAPSHOT.json')
    subject_payload = parse(subject_raw)
    summaries = []
    capture_summaries = []
    for author, form in [('a01', 'common'), ('a02', 'minimal')]:
        primary_field, array_field, name_field = ('answer', 'support', 'id') if form == 'common' else ('text', 'artifacts', 'name')
        author_dir = 'coordination/receipt-challenge-01/authors/' + author + '/attempt-01/'
        variant_dir = 'coordination/receipt-challenge-01/variants/' + author + '/'
        original_raw = data(author_dir + 'SELECTED.json')
        reduced_raw = data(variant_dir + 'SELECTED.json')
        original, reduced = parse(original_raw), parse(reduced_raw)
        original_items, reduced_items = original[array_field], reduced[array_field]
        original_names = [item[name_field] for item in original_items]
        omitted = {'payload.raw', 'SNAPSHOT.json'}
        check(author + ' original selected names unique', len(set(original_names)) == len(original_names))
        for companion in sorted(omitted):
            selected = [i for i in original_items if i[name_field] == companion]
            check(author + ' exact original companion: ' + companion, len(selected) == 1 and selected[0]['text'].encode() == data(subject_prefix + companion))
        check(author + ' reduced only removes two whole companions', reduced == {**original, array_field: [i for i in original_items if i[name_field] not in omitted]})
        check(author + ' primary UTF-8 invariant', reduced[primary_field].encode() == original[primary_field].encode())
        check(author + ' all non-artifact metadata invariant', {k:v for k,v in reduced.items() if k != array_field} == {k:v for k,v in original.items() if k != array_field})
        check(author + ' retained object order/full content invariant', reduced_items == [i for i in original_items if i[name_field] not in omitted])
        provenance = doc(variant_dir + 'PROVENANCE.json')
        plan = doc(variant_dir + 'PLAN.json')
        check(author + ' plan removal membership exact', set(plan['removed_names']) == omitted and len(plan['removed_names']) == 2)
        check(author + ' provenance removed objects exact', provenance['removed'] == [i for i in original_items if i[name_field] in omitted])
        check(author + ' provenance retained names exact', provenance['retained_names'] == [i[name_field] for i in reduced_items])
        check(author + ' provenance original binding', provenance['author_original']['bytes'] == len(original_raw) and provenance['author_original']['sha256'] == sha(original_raw))
        check(author + ' provenance reduction binding', provenance['selection']['bytes'] == len(reduced_raw) and provenance['selection']['sha256'] == sha(reduced_raw))
        check(author + ' transformation reports four passing checks', provenance['passed'] == provenance['total'] == 4 and len(provenance['checks']) == 4 and all(provenance['checks'].values()))
        remaining = reduced[primary_field] + '\n' + '\n'.join(i['text'] for i in reduced_items)
        check(author + ' retained text lacks exact full raw/snapshot copy', subject_raw.decode() not in remaining and subject_snapshot_raw.decode() not in remaining)
        check(author + ' retained text lacks complete historical primary', subject_payload['answer'] not in remaining)
        for item in subject_payload['support']:
            check(author + ' retained text lacks complete historical support: ' + item['id'], item['text'] not in remaining)
        read_account = doc(author_dir + 'READS.json')
        check(author + ' read account selected binding', read_account['selected_return']['bytes'] == len(original_raw) and read_account['selected_return']['sha256'] == sha(original_raw))
        for kind, raw, selected_source in [('original', original_raw, author_dir + 'SELECTED.json'), ('reduced', reduced_raw, variant_dir + 'SELECTED.json')]:
            cap = '.scratch/receipt-challenge-01/captures/' + author + '/' + kind + '/'
            label = author + ' ' + kind
            payload = parse(raw)
            snapshot = doc(cap + 'helper/SNAPSHOT.json')
            accepted = doc(cap + 'helper/ACCEPTED.json')
            check(label + ' witness equals selected bytes', data(cap + 'input.raw') == raw)
            check(label + ' helper raw equals witness', data(cap + 'helper/attempt.raw') == raw)
            check(label + ' helper decoded payload exact', snapshot['envelope'] == payload)
            check(label + ' stdout equals exclusive acceptance bytes', data(cap + 'stdout') == data(cap + 'helper/ACCEPTED.json'))
            check(label + ' stderr empty', data(cap + 'stderr') == b'')
            check(label + ' acceptance raw identity', accepted['raw_transport'] == {'bytes': len(raw), 'sha256': sha(raw)})
            check(label + ' metadata corresponds to snapshot', accepted['capture_metadata'] == snapshot['capture_metadata'])
            metadata = snapshot['capture_metadata']
            check(label + ' form and expected identity exact', metadata['form'] == form and metadata['expected_identity'] == {'question_id': 'receipt-acceptance-binding-01', 'source_revision': '43228273f0ee0e05a2977039ce6c3c3d97550e68'})
            check(label + ' external author/variant provenance exact', metadata['issued_provenance'] == {'author_id': author if kind == 'original' else 'coordinator-reduction-of-' + author, 'phase': kind})
            check(label + ' structural-only acceptance', accepted['status'] == 'structurally_accepted' and accepted['intellectual_assessment'] == snapshot['intellectual_assessment'] == 'not_performed')
            exit_record, pid, command = doc(cap + 'EXIT.json'), doc(cap + 'PID.json'), doc(cap + 'COMMAND.json')
            check(label + ' observed successful process identity', exit_record['exit'] == 0 and exit_record['pid'] == pid['pid'])
            argv = command['argv']
            expected_argv = ['/usr/bin/python3', '-I', '-B', '-S', str(ROOT/'coordination/receipt-challenge-01/capture.py'), '--destination', str(ROOT/cap/'helper'), '--form', form, '--question-id', 'receipt-acceptance-binding-01', '--source-revision', '43228273f0ee0e05a2977039ce6c3c3d97550e68', '--author-id', author if kind == 'original' else 'coordinator-reduction-of-' + author, '--phase', kind]
            check(label + ' recorded argv exactly expected isolated capture', argv == expected_argv)
            check(label + ' command reads independent witness', command['stdin'] == 'input.raw' and command['cwd'] == str(ROOT))
            freeze = doc(cap + 'FREEZE.json')
            for row in freeze['files']:
                frozen = data(row['snapshot'])
                check(label + ' frozen identity: ' + row['source'], len(frozen) == row['bytes'] and sha(frozen) == row['sha256'] and frozen == data(row['source']))
            expected_source_set = {author_dir + n for n in ('SELECTED.json', 'PROCESS.md', 'READS.json', 'PROGRESS.md')} if kind == 'original' else {variant_dir + n for n in ('SELECTED.json', 'PLAN.json', 'PROVENANCE.json')}
            check(label + ' exact required freeze population', {r['source'] for r in freeze['files']} == expected_source_set)
            check_record = doc(cap + 'CHECKS.json')
            check(label + ' nine reported checks all pass', check_record['passed'] == check_record['total'] == len(check_record['checks']) == 9 and all(check_record['checks'].values()) and check_record['exit'] == 0)
            observations = snapshot['byte_observations']
            primary = payload[primary_field].encode()
            expected_items = [{'position': n, name_field: i[name_field], 'bytes': len(i['text'].encode()), 'sha256': sha(i['text'].encode())} for n, i in enumerate(payload[array_field])]
            check(label + ' primary observation rederived', observations['decoded_primary_text_utf8'] == {'bytes': len(primary), 'sha256': sha(primary)})
            check(label + ' ordered item observations rederived', observations['decoded_artifact_text_utf8_in_submission_order'] == expected_items)
            check(label + ' raw observation rederived', observations['raw_transport'] == {'bytes': len(raw), 'sha256': sha(raw)})
            capture_summaries.append({'author': author, 'kind': kind, 'raw_bytes': len(raw), 'raw_sha256': sha(raw), 'objects': len(payload[array_field]), 'exit': exit_record['exit'], 'pid': pid['pid'], 'reported_passed': check_record['passed'], 'reported_total': check_record['total']})
        summaries.append({'author': author, 'original_names': original_names, 'remaining_names': [i[name_field] for i in reduced_items], 'removed_decoded_text_bytes': sum(len(i['text'].encode()) for i in original_items if i[name_field] in omitted), 'primary_bytes': len(original[primary_field].encode()), 'no_reconstruction_claim': 'Only exact full-text copy checks automated; review reads remaining analysis to assess other encodings or reconstruction. No universal non-reconstructability claimed.'})
    tree = ast.parse(data('coordination/receipt-challenge-01/packets.py'))
    check('packet builder syntax parses statically', isinstance(tree, ast.Module))
    result = {'status': 'passed' if all(c['passed'] for c in checks) else 'failed', 'checks': checks, 'passed': sum(c['passed'] for c in checks), 'total': len(checks), 'capture_population': capture_summaries, 'author_population': summaries, 'reviewer_subject_helper_ops_builder_executions': 0, 'pytest_nodes': 0, 'historical_qualification_not_recounted': True}
except Exception as exc:
    result = {'status': 'review_check_error', 'exception': type(exc).__name__ + ': ' + str(exc), 'checks': checks, 'passed': sum(c['passed'] for c in checks), 'total': len(checks)}
put('RESULT.json', encode(result))
put('stdout.txt', encode(result))
print(json.dumps({key: value for key, value in result.items() if key != 'checks'}, indent=2))
if any(not c['passed'] for c in checks):
    print(json.dumps([c for c in checks if not c['passed']], indent=2))
sys.exit(0 if result['status'] == 'passed' else 1)
