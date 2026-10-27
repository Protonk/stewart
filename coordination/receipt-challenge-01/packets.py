"""Construct explicit whole-artifact variants and exact recipient packets."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
DOC=Path(__file__).resolve().parent
ROOT=REPO/'.scratch/receipt-challenge-01'
FORMS={'a01':'common','a02':'minimal'}


def read(p):
    if p.is_symlink() or not p.is_file():raise ValueError('Expected ordinary file: '+str(p))
    return p.read_bytes()


def load(p):return json.loads(read(p))
def sha(raw):return hashlib.sha256(raw).hexdigest()


def put(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(b)


def write_receipt(p,o):put(p,(json.dumps(o,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
def pin(p):
    b=read(p);return {'path':str(p.relative_to(REPO)),'bytes':len(b),'sha256':sha(b)}


def variant(author,omitted):
    source=ROOT/'captures'/author/'original/input.raw'
    original=load(source); common=FORMS[author]=='common'; key='support' if common else 'artifacts'; namekey='id' if common else 'name'
    names=[i[namekey] for i in original[key]]
    if not omitted or len(set(omitted))!=len(omitted) or not set(omitted)<=set(names):
        raise ValueError('Name a nonempty unique subset of actual selected artifacts')
    removed=[i for i in original[key] if i[namekey] in omitted]
    retained=[i for i in original[key] if i[namekey] not in omitted]
    output={**original,key:retained}
    destination=DOC/'variants'/author
    destination.mkdir(parents=True,exist_ok=False)
    write_receipt(destination/'PLAN.json',{'at':datetime.now(timezone.utc).isoformat(),'source':pin(source),'removed_names':omitted,
        'planned':['SELECTED.json','PROVENANCE.json'],'rule':'Whole artifacts only; original primary and all other fields preserved.'})
    write_receipt(destination/'SELECTED.json',output)
    checks={'only_artifact_array_changed':all(output[k]==v for k,v in original.items() if k!=key),
        'retained_order_and_content':output[key]==[i for i in original[key] if i[namekey] not in omitted],
        'exact_removed_membership':set(i[namekey] for i in removed)==set(omitted),'original_witness_unchanged':pin(source)==load(destination/'PLAN.json')['source']}
    write_receipt(destination/'PROVENANCE.json',{'at':datetime.now(timezone.utc).isoformat(),'origin':'coordinator construction, not author selection',
        'author_original':pin(source),'selection':pin(destination/'SELECTED.json'),'removed':removed,
        'retained_names':[i[namekey] for i in retained],'checks':checks,'passed':sum(checks.values()),'total':len(checks)})
    print(author,'removed',omitted,'retained',len(retained),'checks',sum(checks.values()),'/',len(checks))


def packets():
    disposition=load(ROOT/'VARIANT-DISPOSITION.json')
    if not disposition['ready']:raise ValueError('No accepted concrete variant review')
    for row in disposition['inputs']:
        b=read(REPO/row['path'])
        if len(b)!=row['bytes'] or sha(b)!=row['sha256']:raise ValueError('Reviewed input changed: '+row['path'])
    population=[]
    for reader,author,kind in [('r01','a01','original'),('r02','a01','reduced'),('r03','a02','original'),('r04','a02','reduced')]:
        cap=ROOT/'captures'/author/kind
        if load(cap/'CHECKS.json')['exit']!=0:raise ValueError('Capture not admitted')
        raw=read(cap/'input.raw');snapshot=load(cap/'helper/SNAPSHOT.json');payload=json.loads(raw)
        if snapshot['envelope']!=payload:raise ValueError('Payload differs from snapshot')
        packet=ROOT/'reader-packets'/reader;packet.mkdir(parents=True,exist_ok=False)
        for name in ('QUESTION.md','RECIPE.md','ACCEPTED.json','capture.py','ORIGINS.json'):
            put(packet/'base'/name,read(ROOT/'subject'/name))
        common=FORMS[author]=='common'; primary=payload['answer' if common else 'text'];items=payload['support' if common else 'artifacts']; objects=[]
        put(packet/'RETURN.raw',raw);put(packet/'primary.txt',primary.encode())
        for n,item in enumerate(items,1):
            name=f'artifact-{n:02}.txt';b=item['text'].encode();put(packet/name,b)
            objects.append({'file':name,'submitted_name':item['id' if common else 'name'],'bytes':len(b),'sha256':sha(b),
                **({'submitted_role':item['role']} if common else {})})
        write_receipt(packet/'RETURN-MANIFEST.json',{'issued':{'reader':reader,'author':author,'form':FORMS[author],'version':kind,
            'provenance':'unchanged author selection' if kind=='original' else 'coordinator removed whole selected artifacts; this reduced version is not the author original'},
            'raw':{'bytes':len(raw),'sha256':sha(raw)},'artifacts':objects,
            **({'submitted_metadata':{k:payload[k] for k in ('question_id','source_revision','author','response_kind','completion_claim')}} if common else {})})
        put(packet/'NOTICE.md',('This is the '+('unchanged author-selected return.' if kind=='original' else 'explicitly coordinator-reduced version of an author return. Whole selected artifacts were removed; primary text, other metadata and retained artifact contents/order are unchanged. Do not attribute this reduced selection to its author.')+'\n\nThe packet contains exactly your admitted base context and selected return. Recorded original paths and unavailable private packet files grant no additional reads. Structural admission is not an intellectual assessment. Inspect what this actual version supports; no conclusion is prescribed.\n').encode())
        entries=[{'file':str(p.relative_to(packet)),'bytes':len(read(p)),'sha256':sha(read(p))} for p in sorted(packet.rglob('*')) if p.is_file()]
        write_receipt(packet/'PACKET.json',{'files':entries,'capture_metadata':snapshot['capture_metadata']})
        population.append({'reader':reader,'author':author,'kind':kind,'files':[pin(p) for p in sorted(packet.rglob('*')) if p.is_file()]})
    write_receipt(ROOT/'READER-PACKETS.json',{'at':datetime.now(timezone.utc).isoformat(),'packets':population})
    print('Four exact recipient packets created.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('variant','packets'));p.add_argument('--author',choices=tuple(FORMS));p.add_argument('--omit',action='append')
    a=p.parse_args()
    if a.action=='packets':packets()
    elif not a.author or not a.omit:p.error('variant requires --author and --omit')
    else:variant(a.author,a.omit)
