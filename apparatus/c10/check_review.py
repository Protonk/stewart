"""Exercise the reviewer against retained synthetic evidence and altered views.

No model calls, container operations or original-record edits. Every changed byte
and omitted member is retained alongside the comparison result.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import compact,digest,read_file,require,strict_json,tree_hash,write_json
from verify import Evidence,ordinary_body,text_block,verify
import driver_core as spec
import rawjson


class View:
    def __init__(self,original):
        self.original=original
        self.changes={}
        self.removed=set()
        self.added_directories=set()

    @property
    def names(self):
        return (self.original.names | set(self.changes)) - self.removed

    @property
    def directories(self):
        return (self.original.directories | self.added_directories) - self.removed

    def read(self,name,limit=64*1024*1024):
        require(name in self.names,'missing_evidence')
        raw=self.changes[name] if name in self.changes else self.original.read(name,limit)
        require(len(raw)<=limit,'oversized_evidence')
        return raw

    def json(self,name):
        return strict_json(self.read(name))

    def put(self,name,value):
        self.changes[name]=compact(value)+b'\n'

    def change_json(self,name,fn):
        value=self.json(name)
        fn(value)
        self.put(name,value)

    def rechain(self,base):
        previous=None
        names=sorted((n for n in self.names if n.startswith(base+'log/')),key=lambda n:int(n.rsplit('/',1)[1][:-5]))
        for name in names:
            value=self.json(name)
            value['body']['prev']=previous
            self.put(name,value)
            previous=digest(self.read(name))


def rebind(view,arrangement,run,number,change):
    """Change one request capture, then make its recorded size and digest fit the changed body.

    Only the measured property then differs: the capture still binds its own bytes.
    """
    active=[]
    for k in range(1,number+1):
        name=run+f'request-{k}.json'
        raw=view.read(name)
        if k==number:
            raw=change(raw)
        node=rawjson.parse(raw)
        active.extend(item.raw for item in node.get('appended').items)
    body=ordinary_body(arrangement,node.get('max_tokens').value(),active)
    for key,value in sorted([('body_bytes',str(len(body)).encode()),('body_sha256',b'"'+digest(body).encode()+b'"')],
                            key=lambda item:-node.get(item[0]).start):
        raw=raw[:node.get(key).start]+value+raw[node.get(key).end:]
    view.changes[name]=raw


def continued_cases(original,baseline,base,case,absent):
    """Controls for an audit with more than one placement; each names what it must trip.

    A control whose subject this audit's evidence does not contain (no entry
    before its interruption, no witnessed point) is listed as not applicable. It
    is never counted as run or fired.
    """
    names=sorted((n for n in original.names if n.startswith(base+'log/')),key=lambda n:int(n.rsplit('/',1)[1][:-5]))
    records=[original.json(n) for n in names]
    last=len(baseline['placements'])
    run=base+f'runs/{last}/'
    started=[n for n,r in zip(names,records) if r['kind']=='run_started']
    ended=[n for n,r in zip(names,records) if r['kind']=='run_ended']
    accepted=next(r['body'] for r in records if r['kind']=='accepted')
    receipt=original.json(base+accepted['receipt'])['body']
    arrangement=rawjson.parse(original.read(base+receipt['arrangement']['machine'])).get('body')
    limits=receipt['settings']['limits']
    captures=sorted(n for n in original.names if n.startswith(run))
    requests=len([n for n in captures if n.startswith(run+'request-')])
    case('omitted-placement-captures',lambda v:v.removed.update(captures),'run_membership')
    def omit_records(view):
        view.removed.update(captures)
        view.removed.update(names[names.index(started[-1]):])
    case('omitted-placement-records',omit_records,'placement_command_count')
    def changed_notice(raw):
        require(raw.count(b'continuing in a new conversation')==1,'continuation notice not found where the specification puts it')
        return raw.replace(b'continuing in a new conversation',b'continuing in the same conversation')
    case('changed-continuation-notice',lambda v:rebind(v,arrangement,run,1,changed_notice),'continuation_notice_first_message')
    reminder=next((r for r in records if r['kind']=='notice' and r['body']['type']=='reminder'),None)
    def twice(view):
        # A second reminder record, or two where the audit recorded none.
        for n in range(1 if reminder is not None else 2):
            again=copy.deepcopy(reminder if reminder is not None else records[-1])
            if reminder is None:
                again.update(kind='notice',body={'prev':None,'type':'reminder','text':spec.REMINDER,'remaining':None})
            again['body'].update(prev=digest(view.read(base+f'log/{len(names)+n}.json')),run=last,request=requests+1)
            view.put(base+f'log/{len(names)+n+1}.json',again)
    case('reminder-recorded-twice',twice,'notice_once_per_audit')
    planned=None if reminder is None or reminder['body']['run']!=last else reminder['body']['request']
    target=next(k for k in range(2,requests+1) if k!=planned)
    def resent(raw):
        require(raw.endswith(b']}]}\n'),'request capture layout')
        return raw[:-5]+b','+text_block(spec.REMINDER)+raw[-5:]
    case('reminder-resent-without-record',lambda v:rebind(v,arrangement,run,target,resent),'conversation_message_layout')
    # Status after the last placement, rewritten as if only that placement had been charged.
    status=sorted((n for n in original.names if n.startswith('evidence/') and n.endswith('-status-after-run.stdout')
                   and '/' not in n[len('evidence/'):]),key=lambda n:int(n[len('evidence/'):].split('-')[0]))[-1]
    own=baseline['placements'][-1]['usage']
    case('usage-reset-between-placements',lambda v:v.change_json(status,lambda r:r['data'].update(allowances={
        key:{'used':sum(own[key].values()),**own[key],'limit':limits[key]} for key in own})),'placement_status_allowances')
    recorded=rawjson.parse(original.read(run+'request-1.json')).get('max_tokens')
    reset=str(min(16000,limits['output_tokens'])).encode()
    if recorded.raw==reset:
        absent('reset-request-cap','earlier usage leaves the first request at the per-request cap either way')
    else:
        case('reset-request-cap',lambda v:rebind(v,arrangement,run,1,
             lambda raw:raw[:recorded.start]+reset+raw[recorded.end:]),'request_allowances')
    earlier=[n[len(base):] for n,r in zip(names,records) if r['kind']=='entry' and r['body']['invocation']['run']<last]
    results=sorted(n for n in captures if n.startswith(run+'result-'))
    if not earlier:
        absent('repeated-effect-across-placements','no entry was recorded before the last placement')
    else:
        # A call of the last placement claims an effect an earlier placement already accounts for.
        case('repeated-effect-across-placements',lambda v:v.change_json(results[0],
             lambda r:r['body'].update(log_record=earlier[0])),'entry_effect_claimed_once')
    case('changed-prior-placement-record',lambda v:v.change_json(ended[0],
         lambda r:r['body'].update(message=r['body']['message']+' Changed.')),'log_chain_and_writer')
    def prior_ending(view):
        view.change_json(ended[0],lambda r:r['body'].update(
            cause='provider_unavailable' if r['body']['cause']!='provider_unavailable' else 'signal'))
        view.rechain(base)
    case('changed-prior-placement-ending',prior_ending,'placement_status_observation')
    def dead(view):
        view.change_json(ended[0],lambda r:r['body'].update(cause='process_gone'))
        view.rechain(base)
    case('prior-placement-recorded-for-dead-process',dead,'process_gone_placement_unassessed')
    witness=next((n for n in sorted(original.names) if n.endswith('/interruption/point.json')),None)
    if witness is None:
        absent('changed-interruption-witness','no placement of this audit was signalled at a witnessed point')
        absent('changed-interruption-timing','no placement of this audit was signalled at a witnessed point')
    else:
        # The witness says the signal found another timing than the placement's records give.
        timing=witness[:-len('point.json')]+'timing.json'
        case('changed-interruption-timing',lambda v:v.change_json(timing,lambda r:r.update(
            timing='not_captured' if r['timing']!='not_captured' else 'answered')),'interruption_timing')
        case('changed-interruption-witness',lambda v:v.change_json(witness,lambda r:r.update(sha256='0'*64)),'interruption_witness')
    case('unrelated-note',lambda v:v.changes.update({'evidence/independent-note.txt':b'No change to the measured property.\n'}),None,control=False)


def exercise(root,out):
    require(root.is_absolute() and out.is_absolute() and not out.exists(),'use absolute source and a new output folder')
    original=Evidence(root)
    binding=original.json('evidence/binding.json')
    require(binding['mode']=='rehearse','review controls require synthetic evidence')
    baseline=verify(original)
    require(baseline['outcome']=='checked','source must pass before applying controls')
    out.mkdir(mode=0o700)
    write_json(out/'SOURCE.json',{'path':str(root),'binding_sha256':digest(original.read('evidence/binding.json')),
        'files':{name:digest(original.read(name)) for name in sorted(original.names)}})
    write_json(out/'baseline.json',baseline)
    base=next(n.split('/log/')[0]+'/' for n in original.names if '/log/' in n)
    rows=[]
    def case(name,change,expected,*,control=True):
        view=View(original)
        change(view)
        result=verify(view)
        ok=(result['outcome']=='incomplete' and expected in result['failures']) if control else result['outcome']=='checked'
        folder=out/name;folder.mkdir()
        changes=[]
        for n,(path,raw) in enumerate(sorted(view.changes.items()),1):
            member=f'changed-{n:04d}.bin';(folder/member).write_bytes(raw)
            changes.append({'path':path,'bytes':len(raw),'sha256':digest(raw),'content':member})
        write_json(folder/'view.json',{'changed':changes,'omitted':sorted(view.removed),
                                     'added_directories':sorted(view.added_directories)})
        write_json(folder/'review.json',result)
        rows.append({'case':name,'control':control,'expected':expected,'outcome':'pass' if ok else 'fail','observed':result['outcome'],'failures':result['failures']})
    missing=[]
    if len(baseline['placements'])>1:
        continued_cases(original,baseline,base,case,lambda name,reason:missing.append({'case':name,'reason':reason}))
        return finish(root,out,baseline,rows,missing)
    run=base+'runs/1/'
    entry=next(n for n in sorted(original.names) if n.startswith(base+'log/')
               and original.json(n)['kind']=='entry' and original.json(n)['body']['citations'])
    seal=next(original.json(n)['body'] for n in original.names if n.startswith(base+'log/') and original.json(n)['kind']=='seal')
    delivered=next(n for n in original.names if n.startswith('returns/') and n.endswith('/answer.md'))
    material=next(n for n in original.names if n.startswith('evidence/input-witness/materials/'))
    if binding['commission'].get('study_build') is not None:
        def change_interface(view, name, value):
            view.change_json('evidence/binding.json', lambda b:
                b['commission']['study_build']['interface'].update({name:value}))
        form=binding['commission']['study_build']['interface']
        require(form['family']==binding['family'],'interface controls need the changed family')
        case('changed-study-guidance',lambda v:change_interface(v,'instructions',form['instructions']+' Changed.'),
             'specified_system_and_tools')
        case('changed-study-version',lambda v:change_interface(v,'version',form['version']+1),
             'arrangement_settings')
    case('missing-call',lambda v:v.removed.add(run+'call-1.json'),'call_membership')
    case('missing-response',lambda v:v.removed.add(run+'response-1-1.bin'),'missing_evidence')
    case('changed-input',lambda v:v.changes.update({material:v.read(material)+b'changed'}),'input_witness_identity')
    case('changed-request',lambda v:v.change_json(run+'request-1.json',lambda r:r.update(body_sha256='0'*64)),'request_body_binding')
    case('wrong-usage',lambda v:v.change_json(run+'attempt-1-1.json',lambda r:r['body']['charged'].update(input_tokens=1)),'attempt_charge')
    case('missing-readback',lambda v:v.removed.add('evidence/'+original.json('evidence/readbacks.json')[0]['command']+'.stdout'),'missing_evidence')
    def bad_citation(view):
        view.change_json(entry,lambda r:r['body']['citations'][0]['stewart'].update(sha256='0'*64))
        view.rechain(base)
    case('invalid-citation-metadata',bad_citation,'entry_fields_and_citations')
    payload=original.json(entry)['body']['payload']['file']
    case('changed-authored-payload',lambda v:v.changes.update({base+payload:b'changed'}),'payload_matches_authored_bytes')
    case('changed-preparation',lambda v:v.changes.update({base+f"prepared/{seal['prepared']}/answer.json":b'{}\n'}),'prepared_answer_and_rendering')
    case('changed-return',lambda v:v.changes.update({delivered:v.read(delivered)+b'changed'}),'exact_delivered_bytes')
    def false_actor(view):
        name=next(n for n in view.names if n.startswith(base+'log/') and view.json(n)['kind']=='seal')
        view.change_json(name,lambda r:r['body'].update(actor='manager'))
        view.rechain(base)
    case('false-seal-actor',false_actor,'manifest_from_witnessed_selection')
    case('missing-placement',lambda v:v.removed.add(run+'request-1.json'),'request_membership')
    case('unrelated-note',lambda v:v.changes.update({'evidence/independent-note.txt':b'No change to the measured property.\n'}),None,control=False)
    def large_response(view):
        name=run+'response-1-1.bin'
        raw=view.read(name)+b' '*(2*1024*1024)
        view.changes[name]=raw
        view.changes['evidence/fake-provider/response-1.json']=raw
        view.change_json(run+'attempt-1-1.json',lambda r:r['body']['response'].update(bytes=len(raw),sha256=digest(raw)))
    case('large-response-invariance',large_response,None,control=False)
    if binding['run'].get('submission_folder') is not None:
        template='evidence/submission-template/'
        question=template+'question.md'
        selected=next(n for n in original.names if n.startswith(template+'materials/'))
        case('changed-template-question',lambda v:v.changes.update({question:v.read(question)+b'changed'}),'study_template_binding')
        case('changed-template-material',lambda v:v.changes.update({selected:v.read(selected)+b'changed'}),'study_template_binding')
        case('missing-template-material',lambda v:v.removed.add(selected),'study_template_binding')
        case('added-template-directory',lambda v:v.added_directories.add(template+'materials/control-empty-directory'),'study_template_binding')
    if (baseline.get('guidance') or {}).get('source') == 'guidance.md':
        receipt_name = next(original.json(n)['body']['receipt'] for n in original.names
                            if n.startswith(base+'log/') and original.json(n)['kind'] == 'accepted')
        capture = base + original.json(base+receipt_name)['body']['guidance']['capture']
        rb = next(r for r in original.json('evidence/readbacks.json') if r['item'] == 'guidance-file')
        case('changed-guidance-capture', lambda v:v.changes.update({capture:v.read(capture)+b'changed'}), 'guidance_capture')
        case('missing-guidance-capture', lambda v:v.removed.add(capture), 'missing_evidence')
        case('changed-template-guidance', lambda v:v.changes.update({'evidence/submission-template/guidance.md':b'changed'}), 'study_template_binding')
        case('changed-guidance-readback', lambda v:v.changes.update({'evidence/'+rb['command']+'.stdout':b'changed'}), 'exact_receipt_readback')
    return finish(root,out,baseline,rows,missing)


def finish(root,out,baseline,rows,missing):
    unchanged=verify(Evidence(root))
    require(unchanged==baseline,'original changed during controls')
    # Every listed case ran. `not_applicable` names controls with no subject in this evidence.
    result={'schema':'stewart.c10-review-controls/1','cases':rows,'run':len(rows),
            'passed':sum(r['outcome']=='pass' for r in rows),'failed':sum(r['outcome']=='fail' for r in rows),
            'skipped':0,'not_applicable':missing,
            'controls':sum(r['control'] for r in rows),'controls_fired':sum(r['control'] and r['outcome']=='pass' for r in rows),
            'original_unchanged':True,'model_calls':0}
    write_json(out/'RESULT.json',result)
    return result


def exercise_cut_off(root,out,key):
    """A recorded cut-off response body, on whole copies of one interrupted synthetic audit.

    INTERFACE 4.5 lets a stop cut a response body off and has the attempt record
    bind what was captured. The audit must hold an attempt aborted by a signal
    with its request written. Each copy gives that attempt a captured half body,
    as if the provider had begun to answer, and then differs in one property.
    The export guard and the reviewer are both asked; the original is only read.
    """
    from batch import export_snapshot
    from session import export_evidence_state
    require(root.is_absolute() and out.is_absolute() and not out.exists(),'use absolute source and a new output folder')
    binding=strict_json(read_file(root/'evidence/binding.json'))
    require(binding['mode']=='rehearse','cut-off controls require synthetic evidence')
    before=tree_hash(root)
    baseline=verify(Evidence(root))
    require(baseline['outcome']=='checked' and export_evidence_state(root)=='complete','source must pass before applying controls')
    found=[path for path in sorted(root.glob('archive/audits/*/runs/*/attempt-*.json'))
           if strict_json(read_file(path))['body']['outcome']=='aborted_by_signal'
           and strict_json(read_file(path))['body']['request_written']=='complete'
           and strict_json(read_file(path))['body']['response'] is None]
    require(len(found)==1,'cut-off controls need one request aborted on the wire without a captured response')
    attempt=found[0].relative_to(root)
    placement=int(attempt.parent.name)
    capture=attempt.with_name(attempt.name.replace('attempt-','response-').replace('.json','.bin'))
    provider=Path('evidence' if placement==1 else f'evidence/placement-{placement:04d}')/'fake-provider'
    number=max(int(path.stem.split('-')[1]) for path in (root/provider).glob('request-*.json'))
    answer=provider/f'response-{number}.json'
    # What the provider would have sent: its own answer where it gave one, else its previous one.
    full=read_file(root/answer) if (root/answer).exists() else read_file(root/provider/f'response-{number-1}.json')
    cut=full[:len(full)//2]
    out.mkdir(mode=0o700)
    def record(folder,change):
        """Rewrite the attempt record and its staged twin alike, as one publication would."""
        path=folder/attempt
        old=read_file(path)
        value=strict_json(old)
        change(value['body'])
        new=compact(value)+b'\n'
        for twin in [path,*(p for p in (path.parent/'stage').iterdir() if p.is_file() and read_file(p)==old)]:
            twin.write_bytes(new)
    def bound(folder,body=cut):
        (folder/capture).write_bytes(body)
        if not (folder/answer).exists():
            (folder/answer).write_bytes(full)
        record(folder,lambda b:b.update(status=200,response={'file':capture.name,'bytes':len(cut),
            'sha256':digest(cut),'complete':False}))
    rows=[]
    def case(name,change,state,exported,review,*,control=True):
        folder=out/name/root.name
        shutil.copytree(root,folder)
        change(folder)
        guard=export_evidence_state(folder)
        export=export_snapshot(folder,out/name/'export',key)
        seen=verify(Evidence(folder))
        ok=(guard==state and (export['outcome']=='exported') is exported
            and (seen['outcome']=='checked' if review is None else review in seen['failures']))
        write_json(out/name/'review.json',seen)
        rows.append({'case':name,'control':control,'expected':{'guard':state,'exported':exported,'review':review or 'checked'},
                     'outcome':'pass' if ok else 'fail','observed':{'guard':guard,'export':export['outcome'],
                     'export_reasons':export['reasons'],'review':seen['outcome'],'failures':seen['failures']}})
    case('bound-cut-off-body',bound,'complete',True,None,control=False)
    def changed(folder):
        bound(folder,bytes([cut[0]^1])+cut[1:])
    case('cut-off-body-one-byte-changed',changed,'incomplete_response_evidence',False,'response_binding')
    def as_response(folder):
        bound(folder)
        record(folder,lambda b:b.update(outcome='response'))
    case('cut-off-body-recorded-as-a-response',as_response,'incomplete_response_evidence',False,'response_membership')
    case('cut-off-body-without-a-record',lambda folder:(folder/capture).write_bytes(cut),'unaccounted_capture',False,'no_orphan_responses')
    def uncaptured(folder):
        bound(folder)
        (folder/capture).unlink()
    case('cut-off-record-without-its-capture',uncaptured,'missing_or_malformed_evidence',False,'missing_evidence')
    case('unaltered-copy',lambda folder:None,'complete',True,None,control=False)
    unchanged=tree_hash(root)==before and verify(Evidence(root))==baseline
    result={'schema':'stewart.c10-cut-off-controls/1','source':str(root),'attempt':str(attempt),'cut_bytes':len(cut),
            'cases':rows,'run':len(rows),'passed':sum(r['outcome']=='pass' for r in rows),
            'failed':sum(r['outcome']=='fail' for r in rows),'controls':sum(r['control'] for r in rows),
            'controls_fired':sum(r['control'] and r['outcome']=='pass' for r in rows),
            'original_unchanged':unchanged,'model_calls':0}
    write_json(out/'RESULT.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit',type=Path)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    result=exercise(args.audit,args.evidence)
    for row in result['cases']:
        print(row['case'],row['outcome'],','.join(row['failures']))
    for row in result['not_applicable']:
        print(row['case'],'not applicable:',row['reason'])
    print(f"Review controls: run={result['run']} passed={result['passed']} failed={result['failed']} controls_fired={result['controls_fired']}/{result['controls']} not_applicable={len(result['not_applicable'])}; original unchanged")
    return result['failed']>0


if __name__=='__main__':
    raise SystemExit(main())
