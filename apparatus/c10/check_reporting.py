"""Read-only report comparisons over a completed fake batch and its later collection."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import CONTINUED, file_hash, read_file, require, strict_json, write_json
from reporting import assemble, current_issues, latest_review, render, write_report


def exercise(batch, target):
    batch, target = Path(batch).resolve(), Path(target).resolve()
    plan = strict_json(read_file(batch/'PLAN.json'))
    require(plan['commission']['model']=='rehearsal-only','report controls require a fake batch')
    require(not target.is_relative_to(batch),'report controls must stay outside the batch')
    target.mkdir(mode=0o700)
    sources = [batch/'PLAN.json',batch/'RESULT.json']
    for run in plan['commission']['runs']:
        for path in sorted((batch/run['id']).glob('export-*/*')):
            if path.name in ['EXPORT.json','work.tar']:
                sources.append(path)
    later = sorted((batch/'continuations').glob('*/attempt-*/RESULT.json')) if (batch/'continuations').is_dir() else []
    sources += later
    def source_identity(path):
        if path.is_dir():
            # The archive-write firing control deliberately puts an empty
            # directory where work.tar would have been. Preserve that witness too.
            require(not any(path.iterdir()),'unexpected contents in failed-export control')
            return {'kind':'empty_directory'}
        return {'kind':'file','sha256':file_hash(path)}
    original = {str(path):source_identity(path) for path in sources}
    write_json(target/'source-identities.json',original)
    proposal = target/'proposal.md'
    proposal.write_text('Can the report distinguish checked submission, no submission, later manager closure, '
        'lost caller reply and unavailable exports without grading an answer?\n\n'
        'This is an offline reporting comparison over the fixed fake batch. No model use or spending. '
        'The supplied batch includes deliberate adverse controls; each remains in the inventory.\n')
    block = target/'block.json'
    write_json(block,{'schema':'stewart.experiment-block/1',
        'proposal':{'author':'Apparatus control author','document':{'path':str(proposal),'sha256':file_hash(proposal)}},
        'batches':[{'path':str(batch/'PLAN.json'),'sha256':file_hash(batch/'PLAN.json')}]})
    report = write_report(block,target/'technical-return')
    audits = {row['audit']:row for row in report['technical']['batches'][0]['audits']}
    checks = []
    def check(name, condition):
        checks.append({'check':name,'passed':bool(condition)})
    check('every-planned-audit',list(audits)==[run['id'] for run in plan['commission']['runs']])
    ordinary = latest_review(audits['open-ordinary-r1'])
    check('ordinary-submission',ordinary and ordinary['auditor_submitted'] and ordinary['closed'])
    unsubmitted = audits['control-unsubmitted']['snapshots']
    before, after = unsubmitted[0]['review'],unsubmitted[-1]['review']
    check('before-close-is-not-submission',before and before['outcome']=='checked'
          and before['auditor_submitted'] is False and before['closed'] is False)
    check('later-manager-closure',len(unsubmitted)==2 and after and after['outcome']=='checked'
          and after['auditor_submitted'] is False and after['seal_actor']=='manager'
          and after['delivery_verified'] is True and after['closed'] is True)
    lost = audits['control-lost-run-reply']['snapshots'][-1]
    check('lost-reply-with-checked-submission',lost.get('caller_reply_lost') is True
          and lost['review'] and lost['review']['auditor_submitted'] is True
          and lost['review']['closed'] is False)
    adverse = ['control-reflected-body','control-export-contamination','control-export-failure']
    check('unavailable-exports-remain-unknown',all(latest_review(audits[name]) is None
          and audits[name]['snapshots'][-1]['reasons'] for name in adverse))
    check('technical-return-before-assessment',report['assessment'] is None
          and 'Pending.' in render(report))
    scenarios = {run['id']:run['scenario'] for run in plan['commission']['runs']}
    several = [row for row in audits.values() if scenarios[row['audit']] in CONTINUED
               and len((latest_review(row) or {}).get('placements') or [])>1]
    if several:
        # Only a batch that holds a later placement can show these; all three are counted when it does.
        def endings(review):
            return [[item['ending'],item['cause']] for item in (review or {}).get('placements') or []]
        check('continued-audit-shows-every-placement',all(
            endings(latest_review(row))==CONTINUED[scenarios[row['audit']]]['endings'][:len(endings(latest_review(row)))]
            for row in several))
        check('earlier-snapshot-keeps-its-own-placement',all(
            endings(row['snapshots'][0]['review'])==CONTINUED[scenarios[row['audit']]]['endings'][:1] for row in several))
        # An attempt whose session record is absent, as this one's is while its
        # controls run, is linked as missing and listed as remaining work.
        folders = sorted(str(path.relative_to(batch/'continuations')) for path in (batch/'continuations').glob('*/attempt-*'))
        linked = {f"{row['audit']}-p{item['placement']}/attempt-{item['attempt']}":item
                  for row in audits.values() for item in row['continuations']}
        unrecorded = [name for name in folders if not (batch/'continuations'/name/'RESULT.json').exists()]
        issues = [reason for _,reason in current_issues(report)]
        check('continuation-records-linked-or-remaining-work',sorted(linked)==folders
              and all(linked[name]['assessment']==('missing' if name in unrecorded else 'read') for name in folders)
              and issues.count('continuation_record_missing')==len(unrecorded))
    assessment = target/'assessment.md'
    assessment.write_text('This authored control assessment leaves its scientific judgment unresolved. '
        'There was no paid work; independent billing is not an apparatus observation. '
        'The lost-reply custody decision remains with the operator under the original authority.\n')
    account = {'schema':'stewart.experiment-assessment/1','technical_sha256':report['technical_sha256'],
        'assessment':{'author':'Named control experimenter',
                      'document':{'path':str(assessment),'sha256':file_hash(assessment)}}}
    write_json(target/'assessment.json',account)
    interpreted = write_report(block,target/'interpreted-return',target/'assessment.json')
    check('attribution-does-not-change-checked-position',interpreted['technical']==report['technical']
          and interpreted['assessment']['basis']=='current'
          and interpreted['assessment']['author']=='Named control experimenter')
    account['technical_sha256']='0'*64
    write_json(target/'earlier-assessment.json',account)
    earlier = write_report(block,target/'earlier-assessment-return',target/'earlier-assessment.json')
    check('earlier-assessment-does-not-clear-current-work',earlier['assessment']['basis']=='earlier_position'
          and 'not assumed current' in render(earlier) and earlier['technical']==report['technical'])
    check('identical-reassembly',assemble(block)['technical_sha256']==report['technical_sha256'])
    unchanged = all(source_identity(Path(path))==value for path,value in original.items())
    check('sources-unchanged',unchanged)
    result = {'schema':'stewart.c10-report-controls/1','checks':checks,'run':len(checks),
              'passed':sum(row['passed'] for row in checks),'failed':sum(not row['passed'] for row in checks),
              'model_calls':0,'original_unchanged':unchanged}
    write_json(target/'RESULT.json',result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch',type=Path,help='Retained results/ or container/ directory')
    parser.add_argument('output',type=Path,help='New control directory outside the retained batch')
    args = parser.parse_args()
    result = exercise(args.batch,args.output)
    for row in result['checks']:
        print(row['check'],'pass' if row['passed'] else 'fail')
    print(f"Report controls: run={result['run']} passed={result['passed']} failed={result['failed']}; original unchanged={result['original_unchanged']}; model_calls=0")
    return result['failed']>0


if __name__=='__main__':
    raise SystemExit(main())
