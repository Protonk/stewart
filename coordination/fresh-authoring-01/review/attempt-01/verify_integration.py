"""Independent static evidence comparisons; imports no study/project code."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

BASE = Path('.scratch/fresh-authoring-01/pilot-01')
OUT = BASE / 'review/attempt-01'
manifest = json.loads((BASE / 'INTEGRATION-INPUTS.json').read_bytes())
index = {row['path']: row for row in manifest['files']}
reads = []
checks = []

def read(path):
    path = str(path)
    row = index[path]
    raw = Path(row['snapshot']).read_bytes()
    reads.append(path)
    return raw

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Repeated JSON key: ' + key)
        result[key] = value
    return result

def load(path):
    return json.loads(read(path), object_pairs_hook=unique)

def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def check(name, value):
    checks.append({'name': name, 'passed': bool(value)})

def bound(row, raw):
    return identity(raw) == {k: row[k] for k in ('bytes', 'sha256')}

def main():
    envelopes = {}
    for phase in ('draft', 'final'):
        witness = BASE / 'witness' / (phase + '-01')
        result = load(BASE / 'commands' / (phase + '-01') / 'RESULT.json')
        scope = load(witness / 'SCOPE.json')
        check(phase + ': both author roots recorded', scope['author_scratch_present'] and scope['author_output_root'].endswith('/author/attempt-01') and scope['author_scratch_root'].endswith('/author/attempt-01'))
        check(phase + ': witness scope precedes child', scope['at'] < result['started_at'])
        for suffix in ('FILES.json', 'scratch/FILES.json'):
            inventory = load(witness / suffix)
            check(phase + ': inventory ends before child ' + suffix, inventory['finished_at'] < result['started_at'])
            for item in inventory['files']:
                check(phase + ': witnessed identity ' + item['copy'], bound(item, read(item['copy'])))
        raw = read(witness / 'files' / (phase.upper() + '-ENVELOPE.json'))
        env = json.loads(raw, object_pairs_hook=unique)
        envelopes[phase] = env
        sub = BASE / (phase + '-submission-01')
        snap = load(sub / 'SNAPSHOT.json')
        accepted = load(sub / 'ACCEPTED.json')
        stdout = load(BASE / 'commands' / (phase + '-01') / 'stdout.json')
        check(phase + ': child accepted', result['exit_code'] == 0 and accepted['status'] == stdout['status'] == 'structurally_accepted')
        check(phase + ': stderr empty', read(BASE / 'commands' / (phase + '-01') / 'stderr.txt') == b'')
        check(phase + ': raw retained exactly', read(sub / 'attempt.raw') == raw)
        check(phase + ': decoded selection exact', snap['envelope'] == env)
        check(phase + ': raw identity exact', snap['byte_observations']['raw_transport'] == identity(raw))
        check(phase + ': answer identity exact', snap['byte_observations']['decoded_answer_utf8'] == identity(env['answer'].encode()))
        check(phase + ': object identities exact', snap['byte_observations']['decoded_support_text_utf8_in_submission_order'] == [dict(id=o['id'], **identity(o['text'].encode())) for o in env['support']])
    draft, final = envelopes['draft'], envelopes['final']
    check('all 13 draft objects preserved unchanged in final prefix', len(draft['support']) == 13 and final['support'][:13] == draft['support'])
    check('final has 18 unique IDs', len(final['support']) == len({o['id'] for o in final['support']}) == 18)
    for item in load(BASE / 'witness/draft-01/FILES.json')['files']:
        final_copy = item['copy'].replace('/witness/draft-01/', '/witness/final-01/')
        if final_copy in index:
            check('draft checkpoint remains exact: ' + item['copy'], read(item['copy']) == read(final_copy))
    selection = {o['id']: o for o in final['support']}
    omission = load('coordination/fresh-authoring-01/execution-01/OMISSION.json')
    omitted = omission['omitted_id']
    check('omission binds final snapshot', omission['final_snapshot_sha256'] == hashlib.sha256(read(BASE / 'final-submission-01/SNAPSHOT.json')).hexdigest())
    check('omission exact selected object', identity(selection[omitted]['text'].encode()) == {'bytes': omission['omitted_bytes'], 'sha256': omission['omitted_sha256']})
    check('no exact observer duplicate in another selected object', all(selection[omitted]['text'] not in o['text'] for o in final['support'] if o['id'] != omitted))
    inputs = load(BASE / 'INPUTS.json')
    source_pins = [o for o in inputs['inputs'] if o['path'].startswith('.scratch/fresh-authoring-01/subject-01/')]
    original_order = [o['id'] for o in final['support']]
    descriptors = {}
    for rid in ('r01', 'r02', 'r03'):
        packet = BASE / 'packets' / rid
        sel = load(packet / 'return/SELECTION.json')
        descriptors[rid] = {o['id']: o for o in sel['support']}
        check(rid + ': attribution unchanged', all(sel[k] == final[k] for k in ('question_id', 'source_revision', 'author', 'response_kind', 'completion_claim')))
        check(rid + ': answer bytes unchanged', read(packet / 'return/ANSWER.md') == final['answer'].encode())
        check(rid + ': intended descriptor order', [o['id'] for o in sel['support']] == (list(reversed(original_order)) if rid == 'r03' else original_order))
        expected_paths = set()
        for desc in sel['support']:
            obj = selection[desc['id']]
            available = rid != 'r02' or desc['id'] != omitted
            check(rid + ': exact descriptor ' + desc['id'], all(desc[k] == obj[k] for k in ('id', 'role', 'encoding')) and bound(desc, obj['text'].encode()) and desc['available'] is available)
            if available:
                p = str(packet / 'return' / desc['path'])
                expected_paths.add(p)
                check(rid + ': exact support ' + desc['id'], read(p) == obj['text'].encode())
            else:
                check(rid + ': omission has no content path', desc['path'] is None)
        actual = {p for p in index if p.startswith(str(packet / 'return/objects') + '/')}
        check(rid + ': exact available object population', actual == expected_paths)
        expected_source = {str(packet / 'source' / Path(o['path']).name) for o in source_pins}
        actual_source = {p for p in index if p.startswith(str(packet / 'source') + '/')}
        check(rid + ': exact eight source population', actual_source == expected_source and len(actual_source) == 8)
        for o in source_pins:
            raw = read(o['snapshot'])
            check(rid + ': initial pin and unchanged source ' + Path(o['path']).name, bound(o, raw) and read(o['path']) == raw and read(packet / 'source' / Path(o['path']).name) == raw)
        for p in sorted(actual | actual_source | {str(packet/'return/ANSWER.md'), str(packet/'return/SELECTION.json'), str(packet/'PACKET.json')}):
            issued = BASE / 'recipient-inputs' / rid / p
            check(rid + ': issued copy exact ' + p, read(issued) == read(p))
    check('full/reordered ID associations equal', descriptors['r01'] == descriptors['r03'])
    check('omission changes exactly one descriptor', [i for i in descriptors['r01'] if descriptors['r01'][i] != descriptors['r02'][i]] == [omitted])
    dispatch = load(BASE / 'RECIPIENT-DISPATCH.json')
    gate = load(BASE / 'PACKET-CHECKS-01.json')
    check('packet gate all pass before dispatch', gate['passed'] == gate['total'] == 299 and gate['at'] < dispatch['at'])
    check('omission before recipient dispatch', omission['decided_at'] < dispatch['at'])
    for phase in ('first', 'second'):
        freeze = load(BASE / 'responses' / phase / 'FREEZE.json')
        check(phase + ': six required files', len(freeze['files']) == 6)
        for item in freeze['files']:
            check(phase + ': frozen current identity ' + item['copy'], bound(item, read(item['copy'])) and read(item['copy']) == read(item['source']))
        for rid in ('r01', 'r02', 'r03'):
            root = BASE / 'responses' / phase / rid
            scope = load(root / 'SCOPE.json')
            check(phase + ' ' + rid + ': both output roots observed', scope['scratch_present'] and scope['at'] < freeze['at'])
            for suffix in ('checkpoint/FILES.json', 'scratch/FILES.json'):
                inv = load(root / suffix)
                for item in inv['files']:
                    check(phase + ' ' + rid + ': retained auxiliary ' + item['copy'], bound(item, read(item['copy'])))
    first = load(BASE / 'responses/first/FREEZE.json')
    reveal = load(BASE / 'REVEAL.json')
    second = load(BASE / 'responses/second/FREEZE.json')
    check('first freeze before reveal before second freeze', first['at'] < reveal['at'] < second['at'])
    check('reveal binds exact first freeze and object ID', reveal['first_freeze_identity'] == identity(read(BASE/'responses/first/FREEZE.json')) and reveal['object_id'] == omitted)
    for item in reveal['files']:
        rid = item['recipient']
        check(rid + ': exact same revealed object', bound(item, read(item['path'])) and read(item['path']) == selection[omitted]['text'].encode())
        check(rid + ': reveal metadata exact', load(BASE/'reveal'/rid/'OBJECT.json') == {k:selection[omitted][k] for k in ('id','role','encoding')})
        for name in ('FIRST.md', 'READS-FIRST.json'):
            check(rid + ': first preserved in second checkpoint ' + name, read(BASE/'responses/first'/rid/name) == read(BASE/'responses/second'/rid/'checkpoint/files'/name))
    objects = {k: v['text'].encode() for k, v in selection.items()}
    a = objects['A-complete.jsonl'].splitlines(keepends=True)
    b = objects['B-duplicate.jsonl'].splitlines(keepends=True)
    check('B differs from A only label-to-seal literal at line five', b == a[:4] + [a[4].replace(b'"measurement":"label"', b'"measurement":"seal"')] + a[5:] and b != a)
    check('F adds only invalid line', objects['F-parse-problem.jsonl'] == objects['A-complete.jsonl'] + b'not a JSON row\n')
    c = objects['C-note-invariant.jsonl'].splitlines()
    d = objects['D-control-extinguished.jsonl'].splitlines()
    e = objects['E-admission-before-reach.jsonl'].splitlines(keepends=True)
    check('E swaps only reach/admission lines', e == a[:1] + [a[2], a[1]] + a[3:])
    av = [json.loads(line) for line in a]
    cv = [json.loads(line) for line in c]
    dv = [json.loads(line) for line in d]
    changed = dict(av[4]); changed['note'] = cv[4]['note']
    check('C changes only one note', cv == av[:4] + [changed] + av[5:] and cv != av)
    changed = dict(av[9]); changed['actual'] = False
    check('D changes only control actual operand', dv == av[:9] + [changed] and dv != av)

try:
    main()
except Exception as exc:
    checks.append({'name': 'review script completed', 'passed': False, 'exception': repr(exc)})
result = {'at': datetime.now(timezone.utc).isoformat(), 'checks': checks, 'passed': sum(r['passed'] for r in checks), 'total': len(checks), 'reads': reads, 'scope': 'Independent static byte/JSON comparisons only; no study/project/observer execution.'}
with (OUT / 'INDEPENDENT-CHECKS-01.json').open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('checks','reads')}, indent=2))
print(json.dumps([r for r in checks if not r['passed']], indent=2))
