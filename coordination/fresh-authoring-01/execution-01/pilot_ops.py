"""Exclusive study witnesses and packet assembly; never executes subject code.

Run with /usr/bin/python3 -I -B. This cooperative study utility does not claim
descriptor-pinned adversarial access, durable custody or complete observation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '.scratch/fresh-authoring-01/pilot-01'
STUDY = ROOT / 'coordination/fresh-authoring-01'
SUBJECT = ROOT / '.scratch/fresh-authoring-01/subject-01'


def now():
    return datetime.now(timezone.utc).isoformat()


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Only observed regular files may be read: ' + str(path))
    return path.read_bytes()


def put(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def record(path, value):
    put(path, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode())


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Repeated JSON key: ' + repr(key))
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique)


def relative(path):
    return str(path.relative_to(ROOT))


def snapshot(source, destination):
    started = now()
    destination.mkdir(parents=True)
    rows = []
    for path in sorted(source.rglob('*')):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        raw = read(path)
        target = destination / 'files' / path.relative_to(source)
        put(target, raw)
        rows.append({'source': relative(path), 'copy': relative(target), **identity(raw)})
    record(destination / 'FILES.json', {
        'observer': 'root via pilot_ops.py', 'started_at': started,
        'finished_at': now(), 'source': relative(source), 'files': rows,
        'scope': 'Saved regular files at a returned checkpoint; no unsaved or continuous observation.'})
    return rows


def submit(phase):
    source = STUDY / 'author/attempt-01'
    scratch = BASE / 'author/attempt-01'
    witness = BASE / 'witness' / (phase + '-01')
    snapshot(source, witness)
    scratch_present = scratch.exists()
    if scratch_present:
        if not stat.S_ISDIR(scratch.lstat().st_mode):
            raise ValueError('Author scratch root must be an observed directory')
        snapshot(scratch, witness / 'scratch')
    record(witness / 'SCOPE.json', {
        'at': now(), 'author_output_root': relative(source),
        'author_scratch_root': relative(scratch), 'author_scratch_present': scratch_present,
        'scope': 'Both granted author output roots observed before helper invocation; missing scratch is recorded explicitly.'})
    envelope = witness / 'files' / (phase.upper() + '-ENVELOPE.json')
    raw = read(envelope)
    destination = BASE / (phase + '-submission-01')
    commands = BASE / 'commands' / (phase + '-01')
    commands.mkdir(parents=True)
    helper = STUDY / 'prototype/attempt-01/submit.py'
    argv = ['/usr/bin/python3', '-I', '-B', str(helper), '--destination', str(destination),
            '--question-id', 'ledger-membership-construction-01', '--source-revision',
            '81b557a78db156e7bfc5e8d35ece9d1438608d87']
    record(commands / 'PLAN.json', {'at': now(), 'cwd': str(ROOT), 'argv': argv,
           'stdin': relative(envelope), 'input_identity': identity(raw),
           'helper_identity': identity(read(helper)), 'destination': relative(destination),
           'planned_outputs': ['stdout.json', 'stderr.txt', 'RESULT.json']})
    started = now()
    with envelope.open('rb') as incoming, (commands/'stdout.json').open('xb') as out, (commands/'stderr.txt').open('xb') as err:
        child = subprocess.Popen(argv, cwd=str(ROOT), stdin=incoming, stdout=out, stderr=err)
        pid = child.pid
        code = child.wait()
    captured = destination / 'attempt.raw'
    checks = {'captured_input_matches_independent_witness': captured.exists() and read(captured) == raw}
    snap = destination / 'SNAPSHOT.json'
    if code == 0:
        value = decode(read(snap))
        selected = decode(raw)
        checks['snapshot_envelope_equals_submitted_envelope'] = value['envelope'] == selected
        checks['raw_identity_matches'] = value['byte_observations']['raw_transport'] == identity(raw)
        checks['answer_identity_matches'] = value['byte_observations']['decoded_answer_utf8'] == identity(selected['answer'].encode())
        expected = [dict(id=obj['id'], **identity(obj['text'].encode())) for obj in selected['support']]
        checks['support_identities_match'] = value['byte_observations']['decoded_support_text_utf8_in_submission_order'] == expected
    result = {'started_at': started, 'finished_at': now(), 'pid': pid, 'exit_code': code,
              'checks': checks, 'witness': relative(witness), 'destination': relative(destination)}
    record(commands / 'RESULT.json', result)
    print(json.dumps(result, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


def materialize(omitted_id):
    decision = decode(read(STUDY / 'execution-01/OMISSION.json'))
    if decision['omitted_id'] != omitted_id:
        raise ValueError('Omission must match the pre-response decision')
    snap_path = BASE / 'final-submission-01/SNAPSHOT.json'
    value = decode(read(snap_path)); envelope = value['envelope']
    objects = envelope['support']
    if omitted_id not in {obj['id'] for obj in objects}:
        raise ValueError('Unknown omitted support ID')
    by_id = {obj['id']: obj for obj in objects}
    canonical = {obj['id']: 'object-{:02d}.txt'.format(i+1) for i,obj in enumerate(objects)}
    output = []
    for recipient, arm in [('r01', 'complete'), ('r02', 'omitted'), ('r03', 'reordered')]:
        target = BASE / 'packets' / recipient
        target.mkdir(parents=True)
        pins = []
        for path in sorted(SUBJECT.iterdir()):
            raw = read(path); dest = target / 'source' / path.name
            put(dest, raw); pins.append({'path': str(dest.relative_to(target)), **identity(raw)})
        answer = envelope['answer'].encode(); put(target/'return/ANSWER.md', answer)
        selected = list(reversed(objects)) if arm == 'reordered' else objects
        descriptors = []
        for obj in selected:
            available = not (arm == 'omitted' and obj['id'] == omitted_id)
            raw = obj['text'].encode()
            descriptor = {key: obj[key] for key in ('id','role','encoding')}
            descriptor.update(identity(raw))
            descriptor.update({'available': available, 'path': 'objects/'+canonical[obj['id']] if available else None})
            if available:
                put(target/'return/objects'/canonical[obj['id']], raw)
            descriptors.append(descriptor)
        selection = {key: envelope[key] for key in ('question_id','source_revision','author','response_kind','completion_claim')}
        selection.update({'answer': {'path':'ANSWER.md', **identity(answer)}, 'support': descriptors,
            'selection_note': 'Only available objects are supplied. Unavailable descriptors name content without supplying it; their hashes do not make the bytes available. Claims remain attributed to the author.'})
        record(target/'return/SELECTION.json', selection)
        record(target/'PACKET.json', {'kind':'recipient-inspection-packet','source':pins,
            'return_selection':'return/SELECTION.json',
            'scope':'Static inspection only; references grant no additional reads or execution.'})
        output.append({'recipient':recipient,'arm':arm,'path':relative(target),
                       'support_order':[obj['id'] for obj in selected],
                       'available_ids':[obj['id'] for obj in descriptors if obj['available']]})
    record(BASE/'PACKETS.json', {'created_at':now(),'source_snapshot':relative(snap_path),
        'source_identity':identity(read(snap_path)), 'omission_decision_identity':identity(read(STUDY/'execution-01/OMISSION.json')),
        'packets':output})
    print(json.dumps(output, indent=2))


def freeze(phase):
    names = ['FIRST.md','READS-FIRST.json'] if phase == 'first' else ['SECOND.md','READS-SECOND.json']
    destination = BASE / 'responses' / phase
    destination.mkdir(parents=True)
    rows=[]
    for recipient in ('r01','r02','r03'):
        output_root=STUDY/'recipients'/recipient/'attempt-01'
        scratch_root=BASE/'recipients'/recipient/'attempt-01'
        snapshot(output_root, destination/recipient/'checkpoint')
        scratch_present=scratch_root.exists()
        if scratch_present:
            snapshot(scratch_root, destination/recipient/'scratch')
        record(destination/recipient/'SCOPE.json', {'at':now(),
            'output_root':relative(output_root),'scratch_root':relative(scratch_root),
            'scratch_present':scratch_present,
            'scope':'Returned saved files before the next phase; includes supporting static inspection records.'})
        for name in names:
            source=output_root/name
            raw=read(source);target=destination/recipient/name;put(target,raw)
            rows.append({'recipient':recipient,'source':relative(source),'copy':relative(target),**identity(raw)})
    record(destination/'FREEZE.json', {'at':now(),'phase':phase,'files':rows})
    print(json.dumps({'phase':phase,'frozen_files':len(rows),'path':relative(destination)}))


def reveal():
    read(BASE/'responses/first/FREEZE.json')
    decision=decode(read(STUDY/'execution-01/OMISSION.json'))
    envelope=decode(read(BASE/'final-submission-01/SNAPSHOT.json'))['envelope']
    obj=next(item for item in envelope['support'] if item['id']==decision['omitted_id'])
    raw=obj['text'].encode();rows=[]
    for recipient in ('r01','r02','r03'):
        destination=BASE/'reveal'/recipient;destination.mkdir(parents=True)
        put(destination/'SUPPORT.txt',raw)
        record(destination/'OBJECT.json',{key:obj[key] for key in ('id','role','encoding')})
        rows.append({'recipient':recipient,'path':relative(destination/'SUPPORT.txt'),**identity(raw)})
    record(BASE/'REVEAL.json',{'at':now(),'first_freeze_identity':identity(read(BASE/'responses/first/FREEZE.json')),'object_id':obj['id'],'files':rows})
    print(json.dumps(rows,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('submit');p.add_argument('phase',choices=['draft','final'])
    p=sub.add_parser('materialize');p.add_argument('omitted_id')
    p=sub.add_parser('freeze');p.add_argument('phase',choices=['first','second'])
    sub.add_parser('reveal')
    args=parser.parse_args()
    if args.command=='submit':submit(args.phase)
    elif args.command=='materialize':materialize(args.omitted_id)
    elif args.command=='freeze':freeze(args.phase)
    else:reveal()


if __name__=='__main__':
    main()
