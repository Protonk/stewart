"""Verify actual packet bytes and complete membership; never run study code."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import stat
import sys

ROOT=Path('/Users/raccoon/Desktop/Experiments/stewart')
OUT=ROOT/'.scratch/receipt-challenge-01/review/attempt-01/packet-check-01'
OUT.mkdir(exist_ok=False)
checks=[]


def sha(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return (json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode()
def put(name,raw):
    with (OUT/name).open('xb') as stream:stream.write(raw)
def unique(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ValueError('Repeated key: '+repr(key))
        value[key]=item
    return value
def parse(raw):return json.loads(raw,object_pairs_hook=unique)
def check(name,condition,detail=None):checks.append({'name':name,'passed':bool(condition),'detail':detail})


baseline_raw=(ROOT/'.scratch/receipt-challenge-01/PACKET-REVIEW-INPUTS-01.json').read_bytes()
baseline=parse(baseline_raw)
pins={r['source']:r for r in baseline['files']}
earlier=parse((ROOT/'.scratch/receipt-challenge-01/VARIANT-INPUTS-01.json').read_bytes())
previous={r['source']:r for r in earlier['files']}


def data(source):
    row=pins[source] if source in pins else previous[source]
    raw=(ROOT/row['snapshot']).read_bytes()
    if len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:raise ValueError('Frozen identity mismatch: '+source)
    return raw
def doc(source):return parse(data(source))
def identity(raw):return {'bytes':len(raw),'sha256':sha(raw)}
def strings(value):
    if isinstance(value,str):return [value]
    if isinstance(value,dict):return [s for v in value.values() for s in strings(v)]
    if isinstance(value,list):return [s for v in value for s in strings(v)]
    return []


put('BASELINE.json',baseline_raw);put('check.py',Path(__file__).read_bytes())
put('COMMAND.json',encoded({'at':datetime.now(timezone.utc).isoformat(),'argv':['/usr/bin/python3','-I','-B','-S','coordination/receipt-challenge-01/review/attempt-01/packet_check.py'],'cwd':str(ROOT),'baseline_sha256':sha(baseline_raw),'code_sha256':sha(Path(__file__).read_bytes())}))
try:
    check('55 unique frozen sources',len(pins)==len(baseline['files'])==55)
    for source,row in pins.items():
        frozen=(ROOT/row['snapshot']).read_bytes()
        check('frozen identity: '+source,identity(frozen)=={'bytes':row['bytes'],'sha256':row['sha256']})
        current=(ROOT/source).read_bytes()
        check('current identity: '+source,identity(current)=={'bytes':row['bytes'],'sha256':row['sha256']})
    check('builder remains accepted version 02',pins['coordination/receipt-challenge-01/packets.py']['bytes']==7225 and pins['coordination/receipt-challenge-01/packets.py']['sha256']=='503475c8e76167bebd4a4f135b3321324dc92203ebacd4f24c4ee799d3503407')
    disposition=doc('.scratch/receipt-challenge-01/VARIANT-DISPOSITION.json')
    disposition_inputs={row['path']:row for row in disposition['inputs']}
    check('assembly disposition is explicit ready with unambiguous pins',disposition['ready'] is True and len(disposition_inputs)==len(disposition['inputs']))
    for source,row in disposition_inputs.items():
        current=(ROOT/source).read_bytes()
        check('assembly input identity: '+source,identity(current)=={'bytes':row['bytes'],'sha256':row['sha256']})
        if source in pins or source in previous:
            expected=data(source)
            check('assembly input agrees with reviewed bytes: '+source,current==expected)
        else:
            check('only extra review-owned disposition source',source=='coordination/receipt-challenge-01/review/attempt-01/VARIANT-REVIEW.md')
    base_names=('QUESTION.md','RECIPE.md','ACCEPTED.json','capture.py','ORIGINS.json')
    consumed={'.scratch/receipt-challenge-01/subject/'+name for name in base_names}
    consumed.add('coordination/receipt-challenge-01/packets.py')
    mapping=[('r01','a01','original','common'),('r02','a01','reduced','common'),('r03','a02','original','minimal'),('r04','a02','reduced','minimal')]
    for reader,author,kind,form in mapping:
        cap='.scratch/receipt-challenge-01/captures/'+author+'/'+kind+'/'
        consumed.update(cap+name for name in ('CHECKS.json','input.raw','helper/SNAPSHOT.json'))
        consumed.add('coordination/receipt-challenge-01/recipients/'+reader+'/BRIEF.md')
    check('disposition pins every external assembly operand plus builder and briefs',consumed<=set(disposition_inputs),{'required':len(consumed),'pinned':len(disposition_inputs),'missing':sorted(consumed-set(disposition_inputs))})
    put('CONSUMED-INPUTS.json',encoded({'required_external_operands_and_dispatch_briefs':sorted(consumed),'disposition_path':'.scratch/receipt-challenge-01/VARIANT-DISPOSITION.json','disposition_identity':identity(data('.scratch/receipt-challenge-01/VARIANT-DISPOSITION.json')),'note':'Disposition is itself bound by this review baseline. The builder additionally reads all disposition-listed pins; those 44 values are verified separately. Its reads of outputs it just created are checked by exact packet membership below.'}))
    inventory=doc('.scratch/receipt-challenge-01/READER-PACKETS.json')
    check('exact four ordered packet mappings',[(p['reader'],p['author'],p['kind']) for p in inventory['packets']]==[(r,a,k) for r,a,k,f in mapping])
    summaries=[]
    for (reader,author,kind,form),entry in zip(mapping,inventory['packets']):
        prefix='.scratch/receipt-challenge-01/reader-packets/'+reader+'/'
        cap='.scratch/receipt-challenge-01/captures/'+author+'/'+kind+'/'
        raw=data(prefix+'RETURN.raw');payload=parse(raw)
        primary_field,array_field,name_field=('answer','support','id') if form=='common' else ('text','artifacts','name')
        expected_names={'NOTICE.md','PACKET.json','RETURN-MANIFEST.json','RETURN.raw','primary.txt'}|{'base/'+n for n in base_names}|{f'artifact-{i:02}.txt' for i in range(1,len(payload[array_field])+1)}
        frozen_names={p[len(prefix):] for p in pins if p.startswith(prefix)}
        check(reader+' exact frozen file membership',frozen_names==expected_names)
        packet_path=ROOT/prefix
        actual=list(packet_path.rglob('*'))
        check(reader+' actual packet entries ordinary and unlinked',all(not p.is_symlink() and (stat.S_ISREG(p.lstat().st_mode) or stat.S_ISDIR(p.lstat().st_mode)) for p in actual))
        actual_files={str(p.relative_to(packet_path)) for p in actual if p.is_file()}
        actual_dirs={str(p.relative_to(packet_path)) for p in actual if p.is_dir()}
        check(reader+' actual files exactly reviewed population',actual_files==expected_names)
        check(reader+' actual directories only base',actual_dirs=={'base'})
        check(reader+' raw selection equals admitted capture',raw==data(cap+'input.raw'))
        check(reader+' exact primary UTF-8 extraction',data(prefix+'primary.txt')==payload[primary_field].encode())
        for name in base_names:
            check(reader+' unchanged shared base: '+name,data(prefix+'base/'+name)==data('.scratch/receipt-challenge-01/subject/'+name))
        expected_objects=[]
        for i,item in enumerate(payload[array_field],1):
            filename=f'artifact-{i:02}.txt';value=item['text'].encode()
            check(reader+' exact ordered selected artifact: '+filename,data(prefix+filename)==value)
            obj={'file':filename,'submitted_name':item[name_field],**identity(value)}
            if form=='common':obj['submitted_role']=item['role']
            expected_objects.append(obj)
        return_manifest=doc(prefix+'RETURN-MANIFEST.json')
        issued={'reader':reader,'author':author,'form':form,'version':kind,'provenance':'unchanged author selection' if kind=='original' else 'coordinator removed whole selected artifacts; this reduced version is not the author original'}
        expected_manifest={'issued':issued,'raw':identity(raw),'artifacts':expected_objects}
        if form=='common':expected_manifest['submitted_metadata']={k:payload[k] for k in ('question_id','source_revision','author','response_kind','completion_claim')}
        check(reader+' exact return manifest including provenance and metadata',return_manifest==expected_manifest)
        expected_notice=('This is the '+('unchanged author-selected return.' if kind=='original' else 'explicitly coordinator-reduced version of an author return. Whole selected artifacts were removed; primary text, other metadata and retained artifact contents/order are unchanged. Do not attribute this reduced selection to its author.')+'\n\nThe packet contains exactly your admitted base context and selected return. Recorded original paths and unavailable private packet files grant no additional reads. Structural admission is not an intellectual assessment. Inspect what this actual version supports; no conclusion is prescribed.\n').encode()
        check(reader+' exact appropriate version notice',data(prefix+'NOTICE.md')==expected_notice)
        packet=doc(prefix+'PACKET.json')
        packet_rows=packet['files'];packet_names=[r['file'] for r in packet_rows]
        check(reader+' internal manifest exact membership without self',len(set(packet_names))==len(packet_names) and set(packet_names)==expected_names-{'PACKET.json'})
        for row in packet_rows:
            check(reader+' internal manifest byte binding: '+row['file'],identity(data(prefix+row['file']))=={'bytes':row['bytes'],'sha256':row['sha256']})
        check(reader+' capture provenance matches actual admitted snapshot',packet['capture_metadata']==doc(cap+'helper/SNAPSHOT.json')['capture_metadata'])
        expected_population=[{'path':prefix+name,**identity(data(prefix+name))} for name in sorted(expected_names)]
        check(reader+' outer population inventory exact',entry['files']==expected_population)
        brief_source='coordination/receipt-challenge-01/recipients/'+reader+'/BRIEF.md'
        check(reader+' dispatch brief unchanged',data(brief_source)==(ROOT/previous[brief_source]['snapshot']).read_bytes())
        if kind=='reduced':
            all_strings=[]
            for name in sorted(expected_names):
                value=data(prefix+name)
                all_strings.append(value.decode())
                if name.endswith('.json') or name=='RETURN.raw':all_strings.extend(strings(parse(value)))
            for companion in ('payload.raw','SNAPSHOT.json'):
                check(reader+' no complete removed companion reintroduced: '+companion,not any(data('.scratch/receipt-challenge-01/subject/'+companion).decode() in s for s in all_strings))
            for private in ('PROCESS.md','READS.json','PROGRESS.md'):
                value=data('coordination/receipt-challenge-01/authors/'+author+'/attempt-01/'+private).decode()
                check(reader+' no full private account reintroduced: '+private,not any(value in s for s in all_strings))
        summaries.append({'reader':reader,'author':author,'kind':kind,'form':form,'files':len(expected_names),'objects':len(payload[array_field]),'raw':identity(raw),'capture_metadata':packet['capture_metadata']})
    check('48 packet files total',sum(p['files'] for p in summaries)==48)
    result={'status':'passed' if all(c['passed'] for c in checks) else 'failed','passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'packets':summaries,'baseline_sha256':sha(baseline_raw),'disposition_inputs':len(disposition_inputs),'required_external_operands_and_briefs':len(consumed),'reviewer_subject_helper_builder_executions':0,'pytest_nodes':0,'observation_scope':'Exact frozen/current endpoint bytes and finite packet directory inventories; no continuous monitoring or access enforcement.'}
except Exception as exc:
    result={'status':'review_check_error','exception':type(exc).__name__+': '+str(exc),'checks':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks)}
put('RESULT.json',encoded(result));put('stdout.txt',encoded(result))
print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
if any(not c['passed'] for c in checks):print(json.dumps([c for c in checks if not c['passed']],indent=2))
sys.exit(0 if result['status']=='passed' else 1)
