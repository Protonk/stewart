"""Finite study preparation/capture; no subject investigation or product imports."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess

REPO = Path(__file__).resolve().parents[2]
DOC = Path(__file__).resolve().parent
ROOT = REPO / '.scratch/receipt-challenge-01'
REV = '43228273f0ee0e05a2977039ce6c3c3d97550e68'
QUESTION = 'receipt-acceptance-binding-01'
FORMS = {'a01': 'common', 'a02': 'minimal'}
HELPER = DOC / 'capture.py'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected ordinary study file: ' + str(path))
    return path.read_bytes()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Repeated control key: ' + key)
        result[key] = value
    return result


def load(path):
    return json.loads(read(path), object_pairs_hook=unique)


def put(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def write_receipt(path, value):
    put(path, (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode())


def pin(path):
    raw = read(path)
    return {'path': str(path.relative_to(REPO)), 'bytes': len(raw), 'sha256': sha(raw)}


def verify(rows):
    for row in rows:
        raw = read(REPO / row['path'])
        if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            raise ValueError('Pinned input changed: ' + row['path'])


def freeze(paths, destination):
    rows = []
    for source in sorted(set(paths)):
        if source.is_symlink():
            raise ValueError('Unexpected study link: ' + str(source))
        if not source.is_file():
            continue
        raw = read(source)
        target = destination / source.relative_to(REPO)
        put(target, raw)
        rows.append({'source': str(source.relative_to(REPO)), 'snapshot': str(target.relative_to(REPO)),
                     'bytes': len(raw), 'sha256': sha(raw)})
    return rows


def prepare():
    ROOT.mkdir()
    old = REPO / '.scratch/answer-revision-01'
    prior = load(old / 'EVIDENCE-INVENTORY-01.json')
    prior_rows = {r['path']: r for r in prior['files']}
    origin = old / 'captures/a03/phase-02/helper'
    sources = {'ACCEPTED.json': origin/'ACCEPTED.json', 'SNAPSHOT.json': origin/'SNAPSHOT.json', 'payload.raw': origin/'attempt.raw',
               'capture.py': REPO/'coordination/answer-revision-01/transport/attempt-01/capture.py'}
    origins = []
    for name, source in sources.items():
        raw = read(source)
        row = pin(source)
        if name != 'capture.py':
            if row != prior_rows[row['path']]:
                raise ValueError('Prior inventory identity differs: ' + name)
        else:
            proc = subprocess.run(['/usr/bin/git','show',REV+':'+row['path']], cwd=REPO, capture_output=True)
            if proc.returncode or proc.stdout != raw:
                raise ValueError('Candidate writer differs from pinned Git')
            put(ROOT/'writer-git.stdout',proc.stdout);put(ROOT/'writer-git.stderr',proc.stderr)
            write_receipt(ROOT/'WRITER-GIT.json',{'argv':['/usr/bin/git','show',REV+':'+row['path']], 'exit':proc.returncode})
            put(HELPER, raw)
        put(ROOT/'subject'/name,raw)
        origins.append({'packet_file':name,**row,'identity_basis':'prior completion evidence inventory' if name != 'capture.py' else 'pinned Git source; candidate historical writer, not attested execution'})
    put(ROOT/'subject/QUESTION.md',read(DOC/'QUESTION.md'))
    recipe_source = REPO/'src/stewart/resources/QUESTION-TYPE.md'
    raw=read(recipe_source);lines=raw.splitlines(keepends=True)
    start=next(i for i,l in enumerate(lines) if l.strip()==b'## Receipt sufficiency')
    end=next(i for i in range(start+1,len(lines)) if lines[i].startswith(b'## '))
    put(ROOT/'subject/RECIPE.md',b''.join(lines[start:end]))
    write_receipt(ROOT/'subject/ORIGINS.json',{'source_revision':REV,'files':origins,
        'prior_inventory':pin(old/'EVIDENCE-INVENTORY-01.json'), 'recipe_source':pin(recipe_source),'recipe_lines':[start+1,end],
        'note':'Exact original bytes; historical absolute paths are inert coordinates. New source manifest is coordinator provenance, not historical writer attestation.'})
    write_receipt(ROOT/'subject/MANIFEST.json',{'files':[{'file':p.name,'bytes':len(read(p)),'sha256':sha(read(p))} for p in sorted((ROOT/'subject').iterdir())]})
    write_receipt(ROOT/'PREPARATION.json',{'at':now(),'files':[pin(p) for p in sorted((ROOT/'subject').iterdir())]+[pin(HELPER)],
        'prior_helper_qualification':{'assertions':571,'capture_invocations':41,'help_invocations':1,'new_invocations':0},'subject_executions':0})
    print('Prepared exact subject and reused helper; no helper or subject executed.')


def capture(author, variant):
    verify(load(ROOT/'PREPARATION.json')['files'])
    disposition=load(ROOT/'PREFLIGHT-DISPOSITION.json')
    if not disposition['ready'] or sha(read(HELPER)) != disposition['helper_sha256'] or sha(read(Path(__file__))) != disposition['ops_sha256']:
        raise ValueError('Exact capture utility lacks accepted preflight')
    kind='reduced' if variant else 'original'
    selected=DOC/'variants'/author/'SELECTED.json' if variant else DOC/'authors'/author/'attempt-01/SELECTED.json'
    if not variant:
        for name in ('SELECTED.json','PROCESS.md','READS.json','PROGRESS.md'):
            read(selected.parent/name)
    destination=ROOT/'captures'/author/kind
    destination.mkdir(parents=True,exist_ok=False)
    raw=read(selected)
    write_receipt(destination/'PLAN.json',{'at':now(),'author':author,'kind':kind,'form':FORMS[author], 'selected':str(selected.relative_to(REPO)),
        'planned':['input.raw','FREEZE.json','COMMAND.json','PID.json','stdout','stderr','EXIT.json','helper/','CHECKS.json']})
    put(destination/'input.raw',raw)
    paths=list(selected.parent.rglob('*'))
    if not variant: paths+=list((ROOT/'authors'/author/'attempt-01').rglob('*'))
    write_receipt(destination/'FREEZE.json',{'at':now(),'files':freeze(paths,destination/'frozen')})
    frozen_selection=destination/'frozen'/selected.relative_to(REPO)
    if read(frozen_selection)!=raw:
        write_receipt(destination/'FAILURE.json',{'at':now(),'reason':'selection_changed_during_freeze',
            'retained':['input.raw','FREEZE.json','frozen/'],'next_step':'Inspect the stopped author and both preserved byte versions; do not reuse this destination.'})
        raise ValueError('Frozen selection differs from independent raw witness; capture not launched')
    argv=['/usr/bin/python3','-I','-B','-S',str(HELPER),'--destination',str(destination/'helper'),'--form',FORMS[author],
          '--question-id',QUESTION,'--source-revision',REV,'--author-id',('coordinator-reduction-of-'+author if variant else author),'--phase',kind]
    write_receipt(destination/'COMMAND.json',{'at':now(),'argv':argv,'cwd':str(REPO),'stdin':'input.raw','timeout_seconds':30})
    with (destination/'input.raw').open('rb') as inp,(destination/'stdout').open('xb') as out,(destination/'stderr').open('xb') as err:
        process=subprocess.Popen(argv,cwd=REPO,stdin=inp,stdout=out,stderr=err,start_new_session=True)
        write_receipt(destination/'PID.json',{'at':now(),'pid':process.pid})
        try:code=process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            write_receipt(destination/'TIMEOUT.json',{'at':now(),'pid':process.pid,'next_action':'terminate group'})
            os.killpg(process.pid,signal.SIGTERM)
            try:code=process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                write_receipt(destination/'KILL.json',{'at':now(),'pid':process.pid});os.killpg(process.pid,signal.SIGKILL);code=process.wait(timeout=5)
    write_receipt(destination/'EXIT.json',{'at':now(),'pid':process.pid,'exit':code})
    checks={'raw_witness':read(destination/'input.raw')==raw,'frozen_selection':read(frozen_selection)==raw,
        'helper_raw':read(destination/'helper/attempt.raw')==raw,'stderr_empty':read(destination/'stderr')==b''}
    if code==0:
        payload=json.loads(raw,object_pairs_hook=unique);snapshot=load(destination/'helper/SNAPSHOT.json');accepted=load(destination/'helper/ACCEPTED.json')
        checks.update(payload=snapshot['envelope']==payload,stdout=load(destination/'stdout')==accepted,
            raw_identity=accepted['raw_transport']=={'bytes':len(raw),'sha256':sha(raw)},form=snapshot['capture_metadata']['form']==FORMS[author],
            phase=snapshot['capture_metadata']['issued_provenance']['phase']==kind)
    write_receipt(destination/'CHECKS.json',{'checks':checks,'passed':sum(checks.values()),'total':len(checks),'exit':code})
    print(author,kind,'exit',code,'checks',sum(checks.values()),'/',len(checks),'bytes',len(raw))
    return code if all(checks.values()) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','capture'))
    parser.add_argument('--author',choices=tuple(FORMS));parser.add_argument('--variant',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif not args.author:parser.error('capture requires --author')
    else:raise SystemExit(capture(args.author,args.variant))
