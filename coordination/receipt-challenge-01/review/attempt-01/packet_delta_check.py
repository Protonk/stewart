"""Review the exact builder guard delta without importing/executing it."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path

ROOT=Path('/Users/raccoon/Desktop/Experiments/stewart')
OUT=ROOT/'.scratch/receipt-challenge-01/review/attempt-01/packet-delta-02'
OUT.mkdir(exist_ok=False)


def put(name, raw):
    with (OUT/name).open('xb') as stream: stream.write(raw)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return (json.dumps(value,indent=2)+'\n').encode()


pin_raw=(ROOT/'.scratch/receipt-challenge-01/PACKET-CODE-02.json').read_bytes()
pin=json.loads(pin_raw)
current=(ROOT/pin['source']).read_bytes()
frozen=(ROOT/pin['snapshot']).read_bytes()
baseline=json.loads((ROOT/'.scratch/receipt-challenge-01/VARIANT-INPUTS-01.json').read_bytes())
oldrow=next(r for r in baseline['files'] if r['source']==pin['source'])
old=(ROOT/oldrow['snapshot']).read_bytes()
for name, raw in [('PIN.json',pin_raw),('builder-01.py',old),('builder-02.py',frozen),('check.py',Path(__file__).read_bytes()),('VARIANT-REVIEW-DRAFT-01.md',(ROOT/'coordination/receipt-challenge-01/review/attempt-01/VARIANT-REVIEW.md').read_bytes())]:put(name,raw)
put('COMMAND.json',encoded({'at':datetime.now(timezone.utc).isoformat(),'argv':['/usr/bin/python3','-I','-B','-S','coordination/receipt-challenge-01/review/attempt-01/packet_delta_check.py'],'cwd':str(ROOT),'code_sha256':sha(Path(__file__).read_bytes())}))
checks=[]
def check(name,condition):checks.append({'name':name,'passed':bool(condition)})
check('current code matches new pin',len(current)==pin['bytes'] and sha(current)==pin['sha256'])
check('frozen code matches new pin',len(frozen)==pin['bytes'] and sha(frozen)==pin['sha256'])
check('current and frozen code identical',current==frozen)
check('original builder remains pinned',len(old)==oldrow['bytes'] and sha(old)==oldrow['sha256'])
check('new code parses without execution',isinstance(ast.parse(frozen),ast.Module))
text=frozen.decode();prior=old.decode()
check('decoded-key duplicate hook supplied',"object_pairs_hook=unique" in text and "if key in result:raise ValueError('Repeated control key: '+key)" in text)
check('nonfinite constants and overflow both refused in decoder source',"parse_constant=reject_constant,parse_float=finite_float" in text and "if not math.isfinite(parsed):raise ValueError" in text)
check('file and raw decoding use the strict function',"def load(p):return decode(read(p))" in text and 'payload=decode(raw)' in text)
check('all reported capture checks required before packet creation',text.index("if outcome['exit']!=0 or outcome['passed']!=outcome['total'] or not outcome['checks'] or not all(outcome['checks'].values()):") < text.index("packet=ROOT/'reader-packets'/reader;packet.mkdir"))
restored=text.replace('import math\n','')
start=restored.index('def unique(pairs):')
end=restored.index('def sha(raw):')
restored=restored[:start]+"def load(p):return json.loads(read(p))\n"+restored[end:]
restored=restored.replace("        outcome=load(cap/'CHECKS.json')\n        if outcome['exit']!=0 or outcome['passed']!=outcome['total'] or not outcome['checks'] or not all(outcome['checks'].values()):\n            raise ValueError('Capture has unresolved admission/byte checks')", "        if load(cap/'CHECKS.json')['exit']!=0:raise ValueError('Capture not admitted')")
restored=restored.replace('payload=decode(raw)','payload=json.loads(raw)')
check('only reviewed guard changes are present',restored==prior)
put('source.diff',''.join(difflib.unified_diff(prior.splitlines(keepends=True),text.splitlines(keepends=True),fromfile='builder-01.py',tofile='builder-02.py')).encode())
result={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'reviewer_builder_executions':0,'source_bytes':len(frozen),'source_sha256':sha(frozen),'scope':'Static exact-source/diff/order review; no fault, concurrent-writer or subject execution.'}
put('RESULT.json',encoded(result));put('stdout.txt',encoded(result))
print(json.dumps(result,indent=2))
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
