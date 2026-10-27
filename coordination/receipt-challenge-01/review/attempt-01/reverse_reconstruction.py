"""Independent data reconstruction from raw/acceptance; no writer code executes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path('/Users/raccoon/Desktop/Experiments/stewart')
OUT=ROOT/'.scratch/receipt-challenge-01/review/attempt-01/reverse-reconstruction-01'
OUT.mkdir(exist_ok=False)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return (json.dumps(value,ensure_ascii=True,indent=2,allow_nan=False)+'\n').encode('ascii')
def put(name,raw):
    with (OUT/name).open('xb') as stream:stream.write(raw)
def unique(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ValueError('Repeated key')
        value[key]=item
    return value
def parse(raw):return json.loads(raw,object_pairs_hook=unique)
def identity(raw):return {'bytes':len(raw),'sha256':sha(raw)}


baseline_raw=(ROOT/'.scratch/receipt-challenge-01/INTEGRATION-INPUTS-01.json').read_bytes()
pins={r['source']:r for r in parse(baseline_raw)['files']}
reads=[]
def read_subject(name):
    source='.scratch/receipt-challenge-01/subject/'+name;row=pins[source]
    raw=(ROOT/row['snapshot']).read_bytes()
    if identity(raw)!={'bytes':row['bytes'],'sha256':row['sha256']}:raise ValueError('Changed input')
    reads.append({'source':source,**identity(raw)})
    return raw


put('COMMAND.json',encoded({'at':datetime.now(timezone.utc).isoformat(),'argv':['/usr/bin/python3','-I','-B','-S','coordination/receipt-challenge-01/review/attempt-01/reverse_reconstruction.py'],'cwd':str(ROOT),'baseline_sha256':sha(baseline_raw)}))
put('check.py',Path(__file__).read_bytes())
raw=read_subject('payload.raw');payload=parse(raw)
acceptance=parse(read_subject('ACCEPTED.json'))
origins=parse(read_subject('ORIGINS.json'))
writer=read_subject('capture.py')
# This independent literal layout comes from static reading of the candidate's
# snapshot/json_bytes source, never from its import, execution or original output.
primary=identity(payload['answer'].encode('utf-8'))
items=[dict(position=n,id=item['id'],**identity(item['text'].encode('utf-8'))) for n,item in enumerate(payload['support'])]
candidate={
    'format':'answer-revision-capture-v1',
    'structural_acceptance':True,
    'intellectual_assessment':'not_performed',
    'capture_metadata':acceptance['capture_metadata'],
    'attribution':{'payload':'submitted author-selected content','author':'submitted claim','completion_claim':'submitted claim'},
    'envelope':payload,
    'byte_observations':{
        'raw_transport':identity(raw),
        'primary_text_field':'answer',
        'decoded_primary_text_utf8':primary,
        'artifact_array_field':'support',
        'decoded_artifact_text_utf8_in_submission_order':items,
        'decoded_primary_and_artifact_utf8_bytes':primary['bytes']+sum(i['bytes'] for i in items),
    },
    'qualification':'Study observation only; no intellectual verdict, custody, access enforcement, durability, delivery or replay claim.',
}
candidate_raw=encoded(candidate)
put('candidate-SNAPSHOT.json',candidate_raw)
# Only after constructing and preserving the candidate, read the original as a
# comparison witness. ORIGINS already supplies the digest a recipient could use.
original=read_subject('SNAPSHOT.json')
snapshot_origin=next(r for r in origins['files'] if r['packet_file']=='SNAPSHOT.json')
changed=dict(candidate,structural_acceptance=False)
changed_raw=encoded(changed);put('changed-metadata-control.json',changed_raw)
checks={
    'input_raw_matches_acceptance':identity(raw)==acceptance['raw_transport'],
    'candidate_matches_supplied_origin_identity':identity(candidate_raw)=={'bytes':snapshot_origin['bytes'],'sha256':snapshot_origin['sha256']},
    'candidate_equals_retained_snapshot_exactly':candidate_raw==original,
    'changed_metadata_fires_origin_identity_difference':sha(changed_raw)!=snapshot_origin['sha256'],
    'changed_metadata_preserves_envelope':parse(changed_raw)['envelope']==payload,
}
result={'checks':checks,'passed':sum(checks.values()),'total':len(checks),'candidate':identity(candidate_raw),'construction_inputs':reads[:-1],'comparison_only_input':reads[-1],'writer_read_as_text_only':identity(writer),'scope':'Reviewer independent static structure/serialization reconstruction after readers stopped. This was not performed by r04 and no new bytes were in its reduced packet. Matching digest supports byte identity under existing assumptions, not actual historical execution or original-file delivery.','subject_helper_executions':0}
put('RESULT.json',encoded(result));put('stdout.txt',encoded(result))
print(json.dumps(result,indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
