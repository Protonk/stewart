"""Final document/record checks for the completed development study.

This is not the project checker: no runtime or tests changed, and no subject
execution is authorized. Run with /usr/bin/python3 -I -B and a fresh record path.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'.scratch/fresh-authoring-01/pilot-01'
checks=[]
commands=[]


def check(name, passed, detail=None):
    checks.append({'check':name,'passed':bool(passed),'detail':detail})


def git(*args):
    result=subprocess.run(['git',*args],cwd=str(ROOT),text=True,capture_output=True)
    commands.append({'argv':['git',*args],'cwd':str(ROOT),'exit_code':result.returncode,
                     'stdout':result.stdout,'stderr':result.stderr})
    return result


def load(name):
    return json.loads((BASE/name).read_text())


for args, label in [
    (('diff','--check'),'working diff whitespace'),
    (('diff','--cached','--check'),'staged diff whitespace including new files'),
    (('diff','--exit-code','aa55bc7','--','src/stewart','tests','AGENTS.md','CONTRACTS.md'),
     'runtime/tests/protected guidance unchanged during pilot'),
    (('diff','--exit-code','6582df2','--','src/stewart'),
     'production source matches frozen Python baseline'),
]:
    result=git(*args);check(label,result.returncode==0)

study=ROOT/'coordination/fresh-authoring-01'
documents=[ROOT/'DEVELOPMENT-PLAN.md',ROOT/'coordination/COORDINATOR-NOTES.md',
           study/'RESULT.md',study/'execution-01/PROTOCOL.md',
           study/'execution-01/REVIEW-DISPOSITION.md',study/'execution-01/PROGRESS.md',
           study/'review/attempt-01/INTEGRATION-REVIEW.md',study/'review/attempt-01/RETURN.md']
document_pins=[]
for path in documents:
    raw=path.read_bytes();text=raw.decode()
    document_pins.append({'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    check('nonempty document: '+str(path.relative_to(ROOT)),bool(text.strip()))
    for target in re.findall(r'\]\(([^)]+)\)',text):
        target=target.split('#',1)[0]
        if not target or '://' in target or target.startswith('mailto:'):
            continue
        check('local link: '+str(path.relative_to(ROOT))+' -> '+target,(path.parent/target).exists())

result_text=(study/'RESULT.md').read_text()
check('result no longer awaits integration review','review is pending' not in result_text and 'review\nis pending' not in result_text)
check('result retains explicit unexecuted distinction','six proposed\nevaluations, not six executed trials' in result_text)
check('result retains actual reading-order limitation','did not consume all content in reversed manifest order' in result_text)
check('result retains signaled-omission limitation','not blind detection of accidental' in result_text)

for record, wanted in [('PACKET-CHECKS-01.json',299),('AUTHOR-SELECTION-CHECKS.json',17),
                       ('FIRST-FREEZE-CHECKS.json',26),('RESPONSE-CHECKS-01.json',50)]:
    data=load(record)
    check('reported outcome: '+record,data['passed']==data['total']==wanted)
    check('actual check rows: '+record,len(data['checks'])==wanted and all(row['passed'] for row in data['checks']))
for phase in ('draft','final'):
    data=load('commands/'+phase+'-01/RESULT.json')
    check(phase+' helper child accepted',data['exit_code']==0)
    check(phase+' five comparison outcomes',len(data['checks'])==5 and all(data['checks'].values()))
    accepted=load(phase+'-submission-01/ACCEPTED.json')
    check(phase+' structural record',accepted['status']=='structurally_accepted' and accepted['intellectual_assessment']=='not_performed')
reveal=load('REVEAL-GRANTS.json')
check('six reveal checks',reveal['passed']==reveal['total']==len(reveal['reveal_checks'])==6 and all(r['passed'] for r in reveal['reveal_checks']))

manifest=load('INTEGRATION-INPUTS.json')
check('review source population is explicitly finite',manifest['file_count']==len(manifest['files'])==436)
check('review source is capture commit',manifest['development_head']=='2dcc95715568628412c8814cd63e3bc2293776a7')
pins=load('review/attempt-01/INTEGRATION-PIN-CHECKS.json')
check('reviewer recorded 436 matching snapshot identities',len(pins)==436 and all(p['passed'] for p in pins))
for name,wanted in [('INDEPENDENT-CHECKS-02.json',383),('INDEPENDENT-MEMBERSHIP-CHECKS.json',50)]:
    data=load('review/attempt-01/'+name)
    check('reviewer actual result: '+name,data['passed']==data['total']==len(data['checks'])==wanted and all(r['passed'] for r in data['checks']))
original=load('review/attempt-01/INDEPENDENT-CHECKS-01.json')
failures=[r for r in original['checks'] if not r['passed']]
check('original overstrict reviewer failure remains retained',original['passed']==383 and original['total']==384 and len(failures)==1 and failures[0]['name'].endswith('/PROGRESS.md'))

status=git('status','--short','--untracked-files=all')
check('status inspection succeeded',status.returncode==0)
changed=[line[3:] for line in status.stdout.splitlines() if line]
check('all pending paths stay in commissioned documentation/study scope',
      all(p in ('DEVELOPMENT-PLAN.md','coordination/COORDINATOR-NOTES.md') or p.startswith('coordination/fresh-authoring-01/') for p in changed))
record={'at':datetime.now(timezone.utc).isoformat(),'checks':checks,
        'passed':sum(c['passed'] for c in checks),'total':len(checks),
        'commands':commands,'documents':document_pins,
        'scope':'Document links, reported observation records and unchanged production endpoints. No pytest or subject execution; no repeat of the packet/response behavioral sequence.',
        'pytest_nodes':0,'project_experiments':0}
destination=Path(sys.argv[1])
with destination.open('x') as stream:
    json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps({'passed':record['passed'],'total':record['total'],'record':str(destination)}))
if record['passed']!=record['total']:
    for item in checks:
        if not item['passed']:
            print(json.dumps(item))
raise SystemExit(0 if record['passed']==record['total'] else 1)
