from pathlib import Path
from datetime import datetime,timezone
import difflib,hashlib,json
root=Path('.')
scratch=root/'.scratch/receipt-challenge-01'
old=json.loads((scratch/'INTEGRATION-DELTA-02.json').read_bytes())
newraw=(scratch/'INTEGRATION-DELTA-03.json').read_bytes();new=json.loads(newraw)
pins={r['source']:r for r in old['files']}
checks=[];diff=[]
for row in new['files']:
 data=(root/row['snapshot']).read_bytes()
 ident={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 checks.append({'check':'delta03 frozen '+row['source'],'passed':ident=={k:row[k] for k in ident}})
 checks.append({'check':'delta03 current '+row['source'],'passed':(root/row['source']).read_bytes()==data})
 diff.extend(difflib.unified_diff((root/pins[row['source']]['snapshot']).read_text().splitlines(True),data.decode().splitlines(True),fromfile='delta02 '+row['source'],tofile='delta03 '+row['source']))
result={'at':datetime.now(timezone.utc).isoformat(),'manifest_sha256':hashlib.sha256(newraw).hexdigest(),'checks':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks)}
for suffix,data in [('diff',''.join(diff).encode()),('checks.json',(json.dumps(result,indent=2)+'\n').encode())]:
 with (scratch/'review/attempt-01'/('integration-delta-03.'+suffix)).open('xb') as f:f.write(data)
print(''.join(diff));print(json.dumps(result,indent=2))
