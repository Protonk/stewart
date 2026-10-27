"""Finite byte/membership verification after all four reader returns."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
DOC=Path(__file__).resolve().parent
ROOT=REPO/'.scratch/receipt-challenge-01'
FORMS={'a01':'common','a02':'minimal'}
checks=[]


def read(path):
    if path.is_symlink() or not path.is_file():raise ValueError('Expected ordinary study file: '+str(path))
    return path.read_bytes()


def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Repeated control key: '+key)
        result[key]=value
    return result


def reject_constant(value):raise ValueError('Nonfinite control number: '+value)
def finite_float(value):
    parsed=float(value)
    if not math.isfinite(parsed):raise ValueError('Nonfinite control number: '+value)
    return parsed


def decode(raw):return json.loads(raw,object_pairs_hook=unique,parse_constant=reject_constant,parse_float=finite_float)
def load(p):return decode(read(p))
def sha(b):return hashlib.sha256(b).hexdigest()
def check(name,value):checks.append({'check':name,'passed':bool(value)})


def pinned(row,path):
    b=read(path);check(str(path.relative_to(REPO))+' pinned bytes',len(b)==row['bytes'] and sha(b)==row['sha256'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    for row in load(ROOT/'PREPARATION.json')['files']:pinned(row,REPO/row['path'])
    approval=load(ROOT/'PREFLIGHT-DISPOSITION.json')
    for name,key in [('capture.py','helper_sha256'),('ops.py','ops_sha256')]:
        check(name+' accepted identity',sha(read(DOC/name))==approval[key])
    for row in load(ROOT/'VARIANT-DISPOSITION.json')['inputs']:pinned(row,REPO/row['path'])
    observations=[]
    for a,form in FORMS.items():
        common=form=='common';key='support' if common else 'artifacts';nkey='id' if common else 'name'
        selections={}
        for kind in ('original','reduced'):
            cap=ROOT/'captures'/a/kind;raw=read(cap/'input.raw');o=decode(raw);selections[kind]=o
            source=DOC/'authors'/a/'attempt-01/SELECTED.json' if kind=='original' else DOC/'variants'/a/'SELECTED.json'
            check(a+kind+' original/current/raw/helper identity',read(source)==raw==read(cap/'helper/attempt.raw'))
            for row in load(cap/'FREEZE.json')['files']:
                pinned(row,REPO/row['snapshot'])
                if Path(row['source']).name in ('SELECTED.json','PROCESS.md','READS.json','PROGRESS.md'):
                    pinned(row,REPO/row['source'])
            snapshot=load(cap/'helper/SNAPSHOT.json');accepted=load(cap/'helper/ACCEPTED.json')
            check(a+kind+' snapshot exact payload',snapshot['envelope']==o)
            check(a+kind+' acceptance raw digest',accepted['raw_transport']=={'bytes':len(raw),'sha256':sha(raw)})
            check(a+kind+' stdout equals acceptance',load(cap/'stdout')==accepted and read(cap/'stderr')==b'')
            command=load(cap/'COMMAND.json')['argv'];meta=snapshot['capture_metadata']
            check(a+kind+' explicit isolated invocation',command[:4]==['/usr/bin/python3','-I','-B','-S'])
            expected_author=a if kind=='original' else 'coordinator-reduction-of-'+a
            check(a+kind+' issued identity',meta['form']==form and meta['issued_provenance']=={'author_id':expected_author,'phase':kind} and
                  meta['expected_identity']=={'question_id':'receipt-acceptance-binding-01','source_revision':'43228273f0ee0e05a2977039ce6c3c3d97550e68'})
            original_checks=load(cap/'CHECKS.json');exit_record=load(cap/'EXIT.json')
            check(a+kind+' capture outcome',original_checks['passed']==original_checks['total']==9 and all(original_checks['checks'].values()) and
                exit_record['exit']==0 and exit_record['pid']==load(cap/'PID.json')['pid'])
            primary=o['answer' if common else 'text'].encode();artifacts=o[key]
            check(a+kind+' primary byte observations',snapshot['byte_observations']['decoded_primary_text_utf8']=={'bytes':len(primary),'sha256':sha(primary)})
            expected=[{'position':i,nkey:item[nkey],'bytes':len(item['text'].encode()),'sha256':sha(item['text'].encode())} for i,item in enumerate(artifacts)]
            check(a+kind+' ordered artifact observations',snapshot['byte_observations']['decoded_artifact_text_utf8_in_submission_order']==expected)
            observations.append({'author':a,'form':form,'version':kind,'raw_bytes':len(raw),'primary_text_bytes':len(primary),
                'artifact_text_bytes':sum(len(i['text'].encode()) for i in artifacts),'artifacts':len(artifacts)})
        original=selections['original'];reduced=selections['reduced']
        check(a+' reduced only whole dependency group',reduced=={**original,key:[i for i in original[key] if i[nkey] not in ('payload.raw','SNAPSHOT.json')]})
        for name in ('payload.raw','SNAPSHOT.json'):
            items=[i for i in original[key] if i[nkey]==name]
            check(a+' exact selected '+name,len(items)==1 and items[0]['text'].encode()==read(ROOT/'subject'/name))
            check(a+' removed '+name,all(i[nkey]!=name for i in reduced[key]))
        provenance=load(DOC/'variants'/a/'PROVENANCE.json')
        check(a+' original variant provenance checks',provenance['passed']==provenance['total']==4 and all(provenance['checks'].values()))
    for r,a,kind in [('r01','a01','original'),('r02','a01','reduced'),('r03','a02','original'),('r04','a02','reduced')]:
        packet=ROOT/'reader-packets'/r;cap=ROOT/'captures'/a/kind;o=load(cap/'input.raw');common=FORMS[a]=='common'
        inventory=load(packet/'PACKET.json')['files']
        for row in inventory:pinned(row,packet/row['file'])
        names={str(p.relative_to(packet))for p in packet.rglob('*')if p.is_file()}
        check(r+' exact inventory membership',names=={row['file']for row in inventory}|{'PACKET.json'})
        base={'QUESTION.md','RECIPE.md','ACCEPTED.json','capture.py','ORIGINS.json'}
        check(r+' finite base context',{p.name for p in (packet/'base').iterdir()}==base)
        for name in base:check(r+' exact base '+name,read(packet/'base'/name)==read(ROOT/'subject'/name))
        check(r+' exact raw selection',read(packet/'RETURN.raw')==read(cap/'input.raw'))
        check(r+' exact primary',read(packet/'primary.txt')==o['answer' if common else 'text'].encode())
        manifest=load(packet/'RETURN-MANIFEST.json');items=o['support' if common else 'artifacts']
        check(r+' issued version',manifest['issued']['author']==a and manifest['issued']['version']==kind and manifest['issued']['reader']==r)
        check(r+' artifact membership',len(items)==len(manifest['artifacts']))
        for i,item in enumerate(items):
            entry=manifest['artifacts'][i]
            check(r+' artifact '+str(i),read(packet/entry['file'])==item['text'].encode() and entry['submitted_name']==item['id' if common else 'name'] and
                (entry['submitted_role']==item['role'] if common else 'submitted_role' not in entry))
        check(r+' attributed common metadata or no invented minimal fields',
            manifest.get('submitted_metadata')=={k:o[k]for k in ('question_id','source_revision','author','response_kind','completion_claim')} if common else 'submitted_metadata' not in manifest)
        expected_top={'RETURN.raw','primary.txt','RETURN-MANIFEST.json','NOTICE.md','PACKET.json'}|{f'artifact-{i:02}.txt'for i in range(1,len(items)+1)}
        check(r+' no private account delivery',{p.name for p in packet.iterdir()if p.is_file()}==expected_top)
    for row in load(ROOT/'READER-FREEZE.json')['files']:
        pinned(row,REPO/row['snapshot']);pinned(row,REPO/row['source'])
    for r in ('r01','r02','r03','r04'):
        for name in ('MEMO.md','READS.json','PROGRESS.md'):
            check(r+' required return '+name,(DOC/'recipients'/r/'attempt-01'/name).is_file())
    result={'at':datetime.now(timezone.utc).isoformat(),'checks':checks,'passed':sum(c['passed']for c in checks),'total':len(checks),'observations':observations,
        'note':'Finite static byte/membership checks; prior capture assertions are not new helper invocations. No subject or helper execution by this checker.'}
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(result['passed'],'/',result['total'],'integration checks')
    for c in checks:
        if not c['passed']:print('FAIL',c['check'])
    return 0 if all(c['passed']for c in checks) else 1


if __name__=='__main__':raise SystemExit(main())
