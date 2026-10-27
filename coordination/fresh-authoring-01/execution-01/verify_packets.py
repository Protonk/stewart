"""Verify materialized packet bytes against the witnessed author selection.

No subject code or proposed experiment is imported or executed. This check uses
the independently retained raw final envelope rather than trusting packet pins.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '.scratch/fresh-authoring-01/pilot-01'
rows = []


def check(name, passed, detail=None):
    rows.append({'check': name, 'passed': bool(passed), 'detail': detail})


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Repeated control key: ' + repr(key))
        value[key] = item
    return value


def load(path):
    return json.loads(path.read_text(), object_pairs_hook=unique)


def ident(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def run():
    witness = BASE / 'witness/final-01/files/FINAL-ENVELOPE.json'
    raw = witness.read_bytes()
    envelope = load(witness)
    snapshot = load(BASE / 'final-submission-01/SNAPSHOT.json')
    check('helper raw equals independent final witness', raw == (BASE/'final-submission-01/attempt.raw').read_bytes())
    check('snapshot retains exact envelope', snapshot['envelope'] == envelope)
    check('snapshot binds original transport', snapshot['byte_observations']['raw_transport'] == ident(raw))
    expected = {obj['id']: obj for obj in envelope['support']}
    check('selected object IDs unique', len(expected) == len(envelope['support']))
    original_order = [obj['id'] for obj in envelope['support']]
    decision = load(ROOT/'coordination/fresh-authoring-01/execution-01/OMISSION.json')
    missing = decision['omitted_id']
    check('omission is one selected object', missing in expected)
    source_root = ROOT/'.scratch/fresh-authoring-01/subject-01'
    inputs = load(BASE/'INPUTS.json')
    source_pins = [item for item in inputs['inputs']
                   if item['path'].startswith('.scratch/fresh-authoring-01/subject-01/')]
    check('source grant has exactly eight pinned files', len(source_pins) == 8)
    check('current source membership matches initial grant',
          sorted(p.name for p in source_root.iterdir()) == sorted(Path(item['path']).name for item in source_pins))
    for item in source_pins:
        pinned = (ROOT/item['snapshot']).read_bytes()
        check('initial snapshot identity '+item['path'], ident(pinned)=={k:item[k] for k in ('bytes','sha256')})
        check('source unchanged since dispatch '+item['path'], (ROOT/item['path']).read_bytes()==pinned)
    selections = {}
    for recipient in ('r01','r02','r03'):
        packet = BASE/'packets'/recipient
        selection = load(packet/'return/SELECTION.json');selections[recipient]=selection
        for key in ('question_id','source_revision','author','response_kind','completion_claim'):
            check(recipient+': unchanged '+key, selection[key] == envelope[key])
        check(recipient+': answer exact bytes', (packet/'return/ANSWER.md').read_bytes() == envelope['answer'].encode())
        check(recipient+': answer identity', {k:selection['answer'][k] for k in ('bytes','sha256')} == ident(envelope['answer'].encode()))
        ids = [obj['id'] for obj in selection['support']]
        wanted_order = list(reversed(original_order)) if recipient == 'r03' else original_order
        check(recipient+': intended presentation order', ids == wanted_order)
        check(recipient+': descriptors retain exact membership', set(ids) == set(expected) and len(ids) == len(expected))
        available_files=[]
        for descriptor in selection['support']:
            obj = expected[descriptor['id']];content=obj['text'].encode()
            label=recipient+': '+obj['id']
            check(label+' metadata exact', all(descriptor[k]==obj[k] for k in ('id','role','encoding')))
            check(label+' content identity', {k:descriptor[k] for k in ('bytes','sha256')}==ident(content))
            available=not(recipient=='r02' and obj['id']==missing)
            check(label+' availability explicit', descriptor['available'] is available)
            if available:
                path=packet/'return'/descriptor['path']
                available_files.append(str(path.relative_to(packet/'return')))
                check(label+' actual bytes exact', path.read_bytes()==content)
            else:
                check(label+' unavailable has no read path', descriptor['path'] is None)
        object_dir=packet/'return/objects'
        actual_files=[str(p.relative_to(packet/'return')) for p in object_dir.iterdir()] if object_dir.exists() else []
        check(recipient+': no extra or missing support files', sorted(actual_files)==sorted(available_files))
        for item in source_pins:
            name=Path(item['path']).name
            check(recipient+': common source exact '+name, (packet/'source'/name).read_bytes()==(ROOT/item['snapshot']).read_bytes())
        check(recipient+': common source membership', sorted(p.name for p in (packet/'source').iterdir())==sorted(Path(item['path']).name for item in source_pins))
    one={obj['id']:obj for obj in selections['r01']['support']}
    three={obj['id']:obj for obj in selections['r03']['support']}
    check('reordering preserves all ID associations',one==three)
    changed=[key for key in one if one[key]!={obj['id']:obj for obj in selections['r02']['support']}[key]]
    check('exactly one support descriptor changes for omission',changed==[missing])
    check('first response freeze absent before packet admission',not (BASE/'responses/first/FREEZE.json').exists())


try:
    run()
except Exception as exc:
    check('verification completed without inspection exception',False,repr(exc))
result={'at':datetime.now(timezone.utc).isoformat(),'checks':rows,'passed':sum(r['passed'] for r in rows),
        'total':len(rows),'scope':'Static byte/selection verification; no helper repeat, subject execution, pytest or enforcement evidence.'}
destination=Path(sys.argv[1])
with destination.open('x') as stream:
    json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps({'passed':result['passed'],'total':result['total'],'record':str(destination)}))
raise SystemExit(0 if result['passed']==result['total'] else 1)
