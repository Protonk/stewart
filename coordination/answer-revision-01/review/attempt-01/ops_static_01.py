"""Preserved source of the inline OPS-PIN-01 static binding check already run.

The original invocation was /usr/bin/python3 -I -B -S - with the body below.
Do not rerun against its exclusive destinations.
"""
import ast,hashlib,json
from pathlib import Path
r=Path('.scratch/answer-revision-01/review/attempt-01')
p=Path('.scratch/answer-revision-01/OPS-PIN-01.json'); raw=p.read_bytes(); pin=json.loads(raw)
snap=Path(pin['snapshot']).read_bytes(); live=Path(pin['path']).read_bytes()
checks=[{'name':'snapshot exact OPS pin','passed':len(snap)==pin['bytes'] and hashlib.sha256(snap).hexdigest()==pin['sha256']},{'name':'live matches snapshot at review','passed':live==snap},{'name':'static Python parses','passed':bool(ast.parse(snap))}]
for name,data in [('OPS-PIN-01.json',raw),('study_ops-before-authors.py',snap)]:
 with (r/name).open('xb') as f:f.write(data)
result={'checks':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks),'pin_manifest_sha256':hashlib.sha256(raw).hexdigest(),'pin_manifest_bytes':len(raw),'subject_executions':0,'coordinator_utility_executions':0,'command':'/usr/bin/python3 -I -B -S inline static binding check'}
with (r/'OPS-STATIC-01.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result,indent=2))
