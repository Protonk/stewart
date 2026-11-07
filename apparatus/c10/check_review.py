"""Exercise the reviewer against retained synthetic evidence and altered views.

No model calls, container operations or original-record edits. Every changed byte
and omitted member is retained alongside the comparison result.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import compact,digest,read_file,require,strict_json,write_json
from verify import Evidence,verify


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
    run=base+'runs/1/'
    entry=next(n for n in sorted(original.names) if n.startswith(base+'log/')
               and original.json(n)['kind']=='entry' and original.json(n)['body']['citations'])
    seal=next(original.json(n)['body'] for n in original.names if n.startswith(base+'log/') and original.json(n)['kind']=='seal')
    delivered=next(n for n in original.names if n.startswith('returns/') and n.endswith('/answer.md'))
    material=next(n for n in original.names if n.startswith('evidence/input-witness/materials/'))
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
    unchanged=verify(Evidence(root))
    require(unchanged==baseline,'original changed during controls')
    result={'schema':'stewart.c10-review-controls/1','cases':rows,'run':len(rows),
            'passed':sum(r['outcome']=='pass' for r in rows),'failed':sum(r['outcome']=='fail' for r in rows),
            'controls':sum(r['control'] for r in rows),'controls_fired':sum(r['control'] and r['outcome']=='pass' for r in rows),
            'original_unchanged':True,'model_calls':0}
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
    print(f"Review controls: run={result['run']} passed={result['passed']} failed={result['failed']} controls_fired={result['controls_fired']}/{result['controls']}; original unchanged")
    return result['failed']>0


if __name__=='__main__':
    raise SystemExit(main())
