"""Prepare, launch and review bounded C10 small-commission batches.

Rehearsals use offline Linux containers and synthetic credentials. Live launch
needs a qualified binary, a matching successful rehearsal, an exact authorized
commission digest and hidden terminal entry. Nothing resumes a placement.
"""
import argparse
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import (REPO,HERE,SOURCE_PATHS,catalog,compact,digest,file_hash,identifier,
    proposal,read_file,rehearsal_packet,require,scan_tree,source_hash,strict_json,validate_packet,write_json)
from launch import hidden_credential,host_environment,select_qualification
from verify import Evidence,verify


def bindings(qualification_id):
    env=host_environment()
    require(not subprocess.check_output(['git','status','--porcelain','--',*SOURCE_PATHS],cwd=REPO,env=env),
            'commit apparatus sources before binding or launching')
    result=subprocess.run(['python3','-I','-B','apparatus/qualified.py','check'],cwd=REPO,env=env,capture_output=True)
    require(result.returncode==0,'qualification record check failed')
    qualification,binaries=select_qualification(REPO,qualification_id)
    bound={'qualification_id':qualification_id,
        'binary_sha256':qualification['platforms']['linux-aarch64']['release_sha256'],
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,env=env).decode().strip(),
        'apparatus_sha256':source_hash(),'image':'docker.io/library/python@'+qualification['python_image'],
        'catalog_sha256':file_hash(HERE/'catalog.json')}
    return bound,binaries,result


def review_batch(root):
    root=Path(root)
    plan=strict_json(read_file(root/'container/PLAN.json'))
    packet=plan['commission']
    results=[]
    for item in packet['runs']:
        require(identifier(item['id']),'invalid audit identity in plan')
        folder=root/'container'/item['id']
        snapshots=[]
        if folder.exists():
            for path in sorted(folder.iterdir()):
                require(re.fullmatch(r'export-[0-9]{4}',path.name) and path.is_dir(),'unknown export member')
                meta=strict_json(read_file(path/'EXPORT.json'))
                row={'snapshot':path.name,'export':meta['outcome']}
                if meta['outcome']=='exported':
                    require((path/'work.tar').stat().st_size==meta['archive']['bytes'],'export size differs')
                    e=Evidence(path/'work.tar',meta['archive']['sha256'])
                    try:
                        row['review']=verify(e)
                        binding=e.json('evidence/binding.json')
                        require(binding['commission']==packet and binding['run']==item
                                and binding['binary_sha256']==plan['binary_sha256'],'export crossed audit binding')
                    finally:
                        e.close()
                snapshots.append(row)
        results.append({'audit':item['id'],'case':item['case'],'snapshots':snapshots,
                        'state':'not_exported' if not snapshots else snapshots[-1]['export']})
    return {'schema':'stewart.c10-batch-review/1','planned':len(packet['runs']),
            'audits':results,'model_qualified':False}


def check_rehearsal(path,bound):
    host=strict_json(read_file(path/'host/RESULT.json'))
    session=strict_json(read_file(path/'container/RESULT.json'))
    require(host['mode']=='rehearse' and host['outcome']=='completed'
        and session['outcome']=='passed' and session['local_iteration_only'] is False,
        'a successful retained Linux rehearsal is required')
    for key in ['apparatus_sha256','binary_sha256','image','catalog_sha256']:
        require(host['bindings'][key]==bound[key],'rehearsal source, binary, image or catalog differs')
    expected=rehearsal_packet()['runs']
    require(session['planned']==len(expected) and session['observed']==len(expected)
        and session['failed']==session['not_started']==0
        and session['skipped_checks']==[]
        and [r['audit'] for r in session['audits']]==[r['id'] for r in expected]
        and all(r['expected_observation'] is True for r in session['audits']), 'incomplete rehearsal inventory')
    report=review_batch(path)
    controls=strict_json(read_file(path/'container/review-controls/RESULT.json'))
    require(controls['failed']==0 and controls['controls']==controls['controls_fired']==12
            and controls['passed']==controls['run']==14 and controls['original_unchanged'] is True,
            'reviewer controls missing or incomplete')
    operations=strict_json(read_file(path/'container/operator-controls/RESULT.json'))
    require(operations['failed']==0 and operations['passed']==operations['run']==7
            and operations['original_snapshot_unchanged'] is True,
            'operator controls missing or incomplete')
    for row,item in zip(report['audits'],expected):
        latest=row['snapshots'][0]
        if item['scenario'] in ['submitted','empty','lost-run-reply']:
            require(latest.get('review',{}).get('outcome')=='procedural_checks_passed','rehearsal procedural review failed')
    first=path/'container/open-ordinary-r1/export-0001'
    meta=strict_json(read_file(first/'EXPORT.json'))
    e=Evidence(first/'work.tar',meta['archive']['sha256'])
    try:
        obs=e.json('evidence/process-observation-index.json')
        require(obs['controls_fired']==2 and obs['inspection_denied'] is True,'process protection controls missing')
    finally:
        e.close()
    return report


def launch_batch(args):
    mode=args.mode
    out=args.evidence
    require(out.is_absolute() and out.parent==REPO/'.scratch' and not out.exists(),
            'use a new absolute evidence folder directly under .scratch')
    if mode=='live':
        require(args.commission is not None and args.approved_commission is not None and args.rehearsal is not None,
                'live needs an exact approved commission and a retained rehearsal')
        raw=read_file(args.commission)
        require(digest(raw)==args.approved_commission,'commission differs from approved digest')
        packet=validate_packet(strict_json(raw),approved=True)
    else:
        require(args.commission is None and args.approved_commission is None and args.rehearsal is None,
                'rehearsal accepts no live packet')
        packet=rehearsal_packet()
    bound,binaries,checked=bindings(args.qualification)
    if mode=='live':
        require(packet['bindings']==bound,'approved packet bindings changed')
        check_rehearsal(args.rehearsal,bound)
    else:
        packet['bindings']=bound
        raw=json.dumps(packet,indent=2).encode()+b'\n'
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    out.mkdir(mode=0o700)
    host,staging,exported=[out/name for name in ['host','staging','container']]
    for folder in [host,staging,exported]:
        folder.mkdir(mode=0o700)
    (staging/'commission.json').write_bytes(raw)
    (host/'qualification-check.stdout').write_bytes(checked.stdout)
    (host/'qualification-check.stderr').write_bytes(checked.stderr)
    (host/'qualification-check.exit').write_text(str(checked.returncode)+'\n')
    name=f'stewart-c10-{int(time.time())}-{os.getpid()}'
    report={'schema':'stewart.c10-launch/1','mode':mode,'bindings':bound,'container':name,
        'commission_sha256':digest(raw),'credential_sent':False,'started_at':time.time(),'outcome':'failed'}
    env=host_environment()
    def step(label,argv):
        write_json(host/(label+'.argv.json'),argv)
        with (host/(label+'.stdout')).open('xb') as stdout, (host/(label+'.stderr')).open('xb') as stderr:
            result=subprocess.run(argv,cwd=REPO,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr)
        (host/(label+'.exit')).write_text(str(result.returncode)+'\n')
        require(result.returncode==0,'host step failed; inspect retained records')
    proc=None
    key=None
    try:
        step('version',['container','--version'])
        require('version 1.6.1 ' in (host/'version.stdout').read_text(),'Apple container 1.6.1 required')
        step('system-status',['container','system','status'])
        step('image',['container','image','inspect',bound['image']])
        step('source',['git','archive','--format=tar','-o',str(staging/'source.tar'),'HEAD',*SOURCE_PATHS])
        report['source_archive_sha256']=file_hash(staging/'source.tar')
        argv=['container','run','--name',name,'--detach','--init','--ulimit','core=0:0','--cpus','2','--memory','512M',
            '--platform','linux/arm64','--network','none' if mode=='rehearse' else 'default',
            '--mount',f'type=bind,source={staging},target=/in,readonly',
            '--mount',f'type=bind,source={binaries},target=/bin-in,readonly',
            '--mount',f'type=bind,source={exported},target=/out',bound['image'],
            'sh','-c','umask 077; ulimit -c 0; mkdir -p /work/code && chmod 755 /work /work/code && tar -xf /in/source.tar -C /work/code && touch /work/code/.ready && exec sleep infinity']
        (host/'container.name').write_text(name+'\n')
        step('container-start',argv)
        step('container-ready',['container','exec',name,'sh','-c','n=0; until test -f /work/code/.ready; do n=$((n+1)); test "$n" -lt 100 || exit 1; sleep 0.1; done'])
        if mode=='live':
            step('network-preflight',['container','exec',name,'env','-i','PATH=/usr/local/bin:/usr/bin:/bin',
                'python3','-I','-B','-c','import socket; s=socket.create_connection(("api.anthropic.com",443),timeout=15); s.close(); print("TCP connection established; no credential or API request sent")'])
        write_json(host/'operator.json',{'container':name,'audits':[r['id'] for r in packet['runs']],
            'command':['python3','-I','-B','apparatus/c10/c10.py','control',str(out),'AUDIT','status'],
            'close_ends_authoring':True,'automatic_continuation':False})
        argv=['container','exec','--interactive',name,'env','-i','PATH=/usr/local/bin:/usr/bin:/bin','HOME=/work',
              'python3','-I','-B','/work/code/apparatus/c10/batch.py',mode,'--binary','/bin-in/stewart','--packet','/in/commission.json']
        write_json(host/'session.argv.json',argv)
        print('Retained container '+name+'; operator commands in '+str(host/'operator.json'),flush=True)
        with (host/'container.stdout').open('xb') as stdout,(host/'container.stderr').open('xb') as stderr:
            proc=subprocess.Popen(argv,cwd=REPO,env=env,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr)
            deadline=time.monotonic()+300
            while not (exported/'READY.json').exists():
                require(proc.poll() is None,'container ended before intake completed; no credential sent')
                require(time.monotonic()<deadline,'intake deadline expired; inspect retained container')
                time.sleep(.1)
            ready=strict_json(read_file(exported/'READY.json'))
            require(ready=={'credential_free_intake_verified':True,'audits':[r['id'] for r in packet['runs']]},'intake readiness differs from packet')
            key=(b'c10-NONFUNCTIONAL-'+os.urandom(24).hex().encode()) if mode=='rehearse' else hidden_credential()
            proc.stdin.write(key)
            proc.stdin.close()
            report['credential_sent']=True
            report['container_exit']=proc.wait()
        step('container-inspect',['container','inspect',name])
        report['host_scan']=scan_tree(out,key)
        require(not report['host_scan']['files_with_matches'] and not report['host_scan']['errors'],'host scan failed or uncertain')
        session=strict_json(read_file(exported/'RESULT.json'))
        report['session_outcome']=session['outcome']
        require(report['container_exit']==0 and session['failed']==session['not_started']==0,'batch incomplete; review retained results')
        if mode=='rehearse':
            controls=strict_json(read_file(exported/'review-controls/RESULT.json'))
            require(controls['failed']==0,'reviewer controls failed')
            controls=strict_json(read_file(exported/'operator-controls/RESULT.json'))
            require(controls['failed']==0,'operator controls failed')
        report['outcome']='completed' if mode=='rehearse' else 'observed_review_required'
    except (Exception,KeyboardInterrupt):
        report['error']='Launch or observation incomplete; inspect retained records and status before another action.'
        if proc is not None and proc.stdin is not None and not proc.stdin.closed:
            proc.stdin.close()
        if proc is not None and proc.poll() is None:
            report['container_process_state']='unknown; use recorded operator commands'
    finally:
        key=None
        report['ended_at']=time.time()
        write_json(host/'RESULT.json',report)
    print(json.dumps(report,indent=2))
    return report['outcome']=='failed'


def host_control(args):
    meta=strict_json(read_file(args.evidence/'host/operator.json'))
    require(args.audit in meta['audits'] and identifier(args.audit),'unknown audit')
    require(re.fullmatch(r'stewart-c10-[0-9]+-[0-9]+',meta['container']),'unknown container identity')
    argv=['container','exec']+(['--interactive'] if args.operation=='collect' else [])+[meta['container'],
        'env','-i','PATH=/usr/local/bin:/usr/bin:/bin','python3','-I','-B',
        '/work/code/apparatus/c10/operations.py',args.audit,args.operation]
    if args.confirm is not None:
        require(args.operation=='close' and re.fullmatch(r'[A-Za-z0-9._:-]{1,512}',args.confirm),'confirmation requires close')
        argv+=['--confirm',args.confirm]
    folder=args.evidence/'host/operators'
    folder.mkdir(mode=0o700,exist_ok=True)
    stem=folder/str(time.time_ns())
    write_json(stem.with_suffix('.argv.json'),argv)
    key=hidden_credential() if args.operation=='collect' else None
    with stem.with_suffix('.stdout').open('xb') as stdout,stem.with_suffix('.stderr').open('xb') as stderr:
        result=subprocess.run(argv,env=host_environment(),input=key,stdout=stdout,stderr=stderr)
    stem.with_suffix('.exit').write_text(str(result.returncode)+'\n')
    if key is not None:
        scan=scan_tree(args.evidence,key)
        write_json(stem.with_suffix('.scan.json'),scan)
        require(not scan['files_with_matches'] and not scan['errors'],'collection host scan failed; retained output withheld')
        key=None
    # Container operator emits only its controlled summary; raw replies stay private.
    sys.stdout.buffer.write(read_file(stem.with_suffix('.stdout')))
    sys.stderr.buffer.write(read_file(stem.with_suffix('.stderr')))
    return result.returncode


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='command',required=True)
    subs.add_parser('list',help='List fixed cases and the full C10 planning count')
    p=subs.add_parser('propose',help='Write an unbound, unpaid small-batch proposal')
    p.add_argument('--model',required=True)
    p.add_argument('--case',action='append',dest='cases')
    p.add_argument('--repetitions',type=int,default=1)
    p.add_argument('--output',type=Path,required=True)
    p=subs.add_parser('packet',help='Bind an unpaid proposal to committed apparatus and qualified binary')
    p.add_argument('proposal',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--qualification',required=True)
    for mode in ['rehearse','live']:
        p=subs.add_parser(mode,help='Retained Linux '+mode+'; never resumes or repeats a placement')
        p.set_defaults(mode=mode)
        p.add_argument('evidence',type=Path)
        p.add_argument('--qualification',required=True)
        p.add_argument('--commission',type=Path)
        p.add_argument('--approved-commission')
        p.add_argument('--rehearsal',type=Path)
    p=subs.add_parser('review',help='Read all immutable exports without extracting or launching')
    p.add_argument('evidence',type=Path)
    p=subs.add_parser('control',help='Operate one retained audit; collect requires hidden terminal entry')
    p.add_argument('evidence',type=Path)
    p.add_argument('audit')
    p.add_argument('operation',choices=['status','close','inspect','collect'])
    p.add_argument('--confirm')
    args=parser.parse_args()
    try:
        if args.command=='list':
            print(json.dumps({'cases':[{k:c[k] for k in ['id','family','variant']} for c in catalog().values()],
                'full_C10':{'fixed_commissions':6,'default_effort_audits':18,'additional_mechanism_audits':3,
                            'total_audits_per_model':21,'spending_authorized':False}},indent=2))
        elif args.command=='propose':
            require(args.output.is_absolute(),'proposal output must be absolute')
            write_json(args.output,proposal(args.model,args.cases,args.repetitions))
            print('Unbound proposal written; no spending authority.')
        elif args.command=='packet':
            value=validate_packet(strict_json(read_file(args.proposal)))
            require(value['spending_authority'] is None and all(v is None for v in value['account'].values()),'bind an unpaid proposal with null account fields')
            require(args.output.is_absolute(),'packet output must be absolute')
            value['bindings'],_,_=bindings(args.qualification)
            write_json(args.output,value)
            print(json.dumps({'packet':str(args.output),'sha256':file_hash(args.output),'approved':False},indent=2))
        elif args.command in ['rehearse','live']:
            return launch_batch(args)
        elif args.command=='review':
            report=review_batch(args.evidence)
            print(json.dumps(report,indent=2))
            return any(not r['snapshots'] or any(s.get('review',{}).get('outcome')=='incomplete' for s in r['snapshots']) for r in report['audits'])
        elif args.command=='control':
            return host_control(args)
        return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        if args.command in ['live','rehearse','control','review']:
            parser.exit(1,'Operation incomplete; inspect retained records. No automatic retry or continuation.\n')
        parser.exit(2,str(error)+'\n')


if __name__=='__main__':
    raise SystemExit(main())
