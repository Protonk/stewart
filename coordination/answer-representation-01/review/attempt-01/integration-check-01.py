from pathlib import Path
import hashlib,json,re
base=Path('.scratch/answer-representation-01'); out=Path('coordination/answer-representation-01/review/attempt-01'); checks=[]
def ck(n,b,d=''): checks.append(dict(name=n,passed=bool(b),detail=d))
def sha(b):return hashlib.sha256(b).hexdigest()
snapshot=json.loads((base/'integration-inputs-01.json').read_text())
for f in snapshot['files']:
 b=Path(f['path']).read_bytes(); ck('integration snapshot:'+f['path'],sha(b)==f['sha256'] and len(b)==f['bytes'])
records=[]; phase_times={}
for pattern in ('first-freeze-*.json','support-freeze-*.json','review-response-freeze-01.json'):
 for p in sorted(base.glob(pattern)):
  doc=json.loads(p.read_text())
  for r in doc['records']:
   b=Path(r['copy']).read_bytes(); ck('frozen copy:'+r['copy'],sha(b)==r['sha256'] and len(b)==r['bytes']); records.append(r)
   if Path(r['path']).name in ('FIRST-PASS.md','SOURCES.json','SUPPORT-RESPONSE.md','REVIEW-RESPONSE.md'):
    ck('unchanged response:'+r['path'],Path(r['path']).read_bytes()==b)
   if Path(r['path']).name in ('FIRST-PASS.md','SUPPORT-RESPONSE.md','REVIEW-RESPONSE.md'):phase_times[(r['recipient'],Path(r['path']).name)]=doc['at']
for actor in ('r01','r02','r03','r04'):
 files=[r for r in records if r['recipient']==actor and Path(r['path']).name in ('FIRST-PASS.md','SUPPORT-RESPONSE.md','REVIEW-RESPONSE.md')]
 ck('three frozen response phases:'+actor,len(files)==3)
 ck('phase freeze order:'+actor,phase_times[(actor,'FIRST-PASS.md')]<phase_times[(actor,'SUPPORT-RESPONSE.md')]<phase_times[(actor,'REVIEW-RESPONSE.md')])
 d=Path('coordination/answer-representation-01/recipients')/actor
 paths=json.loads((d/'attempt-01/SOURCES.json').read_text())['consulted']
 allowed=set(json.loads((base/'packets'/('p'+actor[1:])/'READ-MANIFEST.json').read_text())['allowed_files']); allowed.add(str(d/'BRIEF.md'))
 for r in paths:ck('declared source boundary:'+r['path'],r['path'] in allowed)
 ck('truncation disclosed:'+actor,'truncat' in (d/'attempt-01/SOURCES.json').read_text())
for kind in ('BRIEF.md','SUPPORT-BRIEF.md','REVIEW-BRIEF.md'):
 docs=[(Path('coordination/answer-representation-01/recipients')/a/kind).read_text() for a in ('r01','r02','r03','r04')]
 normalized=[re.sub(r'\b[pr]0[1-4]\b','ACTOR',s) for s in docs]
 ck('equal brief body:'+kind,len(set(normalized))==1)
inv=json.loads((base/'producer/INVENTORY.json').read_text()); omitted=sum(len({n for a,z,why in ranges for n in range(a,z+1)}) for ranges in inv['omissions'].values()); ck('250 unique omitted source lines',omitted==250,str(omitted))
v=json.loads((base/'recipient-validation-01.json').read_text());ck('reported coordinator 100 checks',len(v['checks'])==100 and all(r['passed'] for r in v['checks']))
with (out/'INTEGRATION-CHECKS.json').open('x') as f:json.dump({'checks':checks,'pytest_selected':0,'product_executions':0},f,indent=2)
print(json.dumps({'checks':len(checks),'passed':sum(c['passed'] for c in checks),'failures':[c for c in checks if not c['passed']],'snapshot_files':len(snapshot['files']),'frozen_records':len(records),'response_phases':len(phase_times)},indent=2))
