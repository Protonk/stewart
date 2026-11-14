"""Exercise explicit manager close and follow-up collection on a synthetic audit.

Only accepts a rehearsal control left unsubmitted: `control-unsubmitted`, or a
continued control whose last placement ended authoring unsubmitted. The script
explicitly inspects its synthetic return before confirming close; it never
launches a model.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import CONTINUED,file_hash,read_file,require,strict_json,write_json
from operations import operate
from batch import check_credential,next_snapshot
from verify import Evidence,verify


def exercise(root, *, private=None, out=None, target=None, key=None, local=True, audit='control-unsubmitted'):
    private=private if private is not None else root/'private'
    out=out if out is not None else root/'results'
    binding=strict_json(read_file(private/audit/'evidence/binding.json'))
    scenario=binding['run']['scenario']
    require(binding['mode']=='rehearse' and binding['commission']['model']=='rehearsal-only'
            and (scenario=='unsubmitted' or scenario in CONTINUED and CONTINUED[scenario]['endings'][-1][0]=='ended_unsubmitted'),
            'operator controls require a synthetic unsubmitted audit')
    info=strict_json(read_file(private/audit/'operator.json'))
    require(info['local'] is local,'operator control execution mode differs')
    target=target if target is not None else root/'operator-controls'
    target.mkdir()
    if key is None:
        require(local,'container operator controls need the synthetic credential')
        key=read_file(root/'credential-witness/canary.bin',4096)
    # Every snapshot already collected must survive the later custody actions unchanged.
    earlier={path.name:file_hash(path/'work.tar') for path in sorted((out/audit).iterdir())}
    expected=next_snapshot(out/audit).name
    unchanged=lambda:all(file_hash(out/audit/name/'work.tar')==value for name,value in earlier.items())
    checks=[]
    def record(name,ok,value):
        write_json(target/(name+'.json'),value)
        checks.append({'check':name,'passed':bool(ok)})
    before=operate(private,out,audit,'status',local=local)
    observed=strict_json(read_file(Path(before['private_reply'])))
    require(before['exit']==0 and observed['data']['runs']['held'] is False,
            'wrong-credential control requires a known stopped writer')
    require(info['audit']==audit and binding['run']['id']==audit and info['local'] is local,
            'wrong-credential control requires the bound audit')
    check_credential(private.parent/'credential-check'/(audit+'.json'),key)
    try:
        operate(private,out,audit,'collect',key=b'WRONG-SYNTHETIC-CREDENTIAL',local=local)
    except ValueError as error:
        reason='credential differs from the original placement; export withheld'
        record('wrong-credential',str(error)==reason and not (out/audit/expected).exists(),
               {'refused':True,'reason':str(error),'writer_held':False,'binding_checked':True})
    else:
        record('wrong-credential',False,{'refused':False})
    first=operate(private,out,audit,'close',local=local)
    record('manager-close',first['exit']==0 and first['state']['seal_actor']=='manager'
           and first['state']['delivery_verified'] and not first['state']['closed'],first)
    inspected=operate(private,out,audit,'inspect',local=local)
    require('confirmation_after_review' in inspected,'synthetic close must require confirmation')
    record('inspect',inspected['exit']==0 and inspected['state']['condition']=='awaiting_confirmation',inspected)
    # Test author explicitly confirms only after inspect verified this synthetic package.
    confirmed=operate(private,out,audit,'close',confirm=inspected['confirmation_after_review'],local=local)
    record('confirm-close',confirmed['exit']==0 and confirmed['state']['closed'] is True,confirmed)
    collected=operate(private,out,audit,'collect',key=key,local=local)
    record('followup-export',collected['export']['outcome']=='exported' and collected['snapshot']==expected,collected)
    second=out/audit/collected['snapshot']
    e=Evidence(second/'work.tar',collected['export']['archive']['sha256'])
    try:
        review=verify(e)
    finally:
        e.close()
    record('manager-seal-is-not-submission',review['outcome']=='checked'
           and review['delivery_verified'] and review['closed'] and not review['auditor_submitted'],review)
    if scenario in CONTINUED:
        # The later custody actions are reviewed with every placement's original evidence.
        record('every-placement-kept-through-close',review['outcome']=='checked'
               and [[row['ending'],row['cause']] for row in review['placements']]==CONTINUED[scenario]['endings'],
               {'placements':review.get('placements')})
    record('original-snapshot-unchanged',unchanged(),{'original_sha256':earlier})
    result={'schema':'stewart.c10-operator-controls/1','checks':checks,'run':len(checks),
            'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),
            'model_calls':0,'original_snapshot_unchanged':unchanged()}
    write_json(target/'RESULT.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    result=exercise(args.evidence)
    print(f"Operator controls: run={result['run']} passed={result['passed']} failed={result['failed']}; original snapshot unchanged={result['original_snapshot_unchanged']}")
    return result['failed']>0


if __name__=='__main__':
    raise SystemExit(main())
