"""Status, close, inspect or collect one retained C10 audit; never starts a model."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import credential_bytes, digest, identifier, read_file, require, strict_json, write_json
from batch import check_credential, event, export_snapshot, next_snapshot
from control import safe_state
from exercise import verify_package


def operate(private, out, audit_id, operation, *, confirm=None, key=None, local=False):
    require(identifier(audit_id),'invalid audit identity')
    require(operation in ['status','close','inspect','collect'],'unknown operator command')
    require(confirm is None or operation=='close' and re.fullmatch(r'[A-Za-z0-9._:-]{1,512}',confirm), 'confirmation needs close and a valid token')
    root=private/audit_id
    info=strict_json(read_file(root/'operator.json'))
    require(info['audit']==audit_id and info['local'] is local,'operator binding differs')
    with (private/(audit_id+'.operator.lock')).open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        stem=root/'evidence'/f'operator-{time.time_ns()}-{operation}'
        argv=[info['binary'],'close' if operation=='close' else 'status',info['reference'],'--json']
        if confirm is not None:
            argv+=['--confirm',confirm]
        options={} if local else {'user':1000,'group':1000,'extra_groups':[]}
        with stem.with_suffix('.stdout').open('xb') as stdout, stem.with_suffix('.stderr').open('xb') as stderr:
            result=subprocess.run(argv,cwd=root,env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':info['home']},
                stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,umask=0o077,**options)
        write_json(stem.with_suffix('.json'),{'argv':argv,'exit':result.returncode,'at':time.time()})
        reply=strict_json(read_file(stem.with_suffix('.stdout')))
        require(reply.get('schema')=='stewart.reply/2','unsupported Stewart reply schema')
        summary={'audit':audit_id,'operation':operation,'exit':result.returncode,'state':safe_state(reply),
                 'private_reply':str(stem.with_suffix('.stdout')),'loss_surrendered':False}
        if operation=='inspect' and result.returncode==0:
            data=reply['data']
            location=data.get('headline',{}).get('delivered',{}).get('location')
            package=Path(location) if isinstance(location,str) else None
            require(package is not None and package.parent==root/'returns'
                and re.fullmatch(r'stewart-return-[a-z0-9-]+',package.name),'no recognized delivered package')
            manifests=list((root/'archive').glob('audits/*/seal/manifest-*.json'))
            require(len(manifests)==1,'expected one seal manifest')
            raw=read_file(manifests[0])
            require(digest(raw)==data['seal']['manifest_sha256'],'seal manifest differs')
            verify_package(package,raw)
            summary['answer_to_read_privately']=str(package/'answer.md')
            token=next((d.get('confirmation') for d in reversed(data.get('deliveries',[])) if d.get('confirmation')),None)
            if token is not None and re.fullmatch(r'[A-Za-z0-9._:-]{1,512}',token):
                summary['confirmation_after_review']=token
        if operation=='collect':
            require(result.returncode==0 and reply['data']['runs']['held'] is False,'writer state uncertain; export withheld')
            require(key is not None,'collection needs the original credential for scanning')
            check_credential(private.parent/'credential-check'/(audit_id+'.json'),key)
            folder=out/audit_id
            folder.mkdir(mode=0o700,exist_ok=True)
            next_export=next_snapshot(folder)
            event(root/'evidence','followup_collection',snapshot=next_export.name)
            summary['export']=export_snapshot(root,next_export,key)
            summary['snapshot']=next_export.name
        return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit')
    parser.add_argument('operation',choices=['status','close','inspect','collect'])
    parser.add_argument('--confirm')
    args=parser.parse_args()
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    key=credential_bytes(sys.stdin.buffer.read(4098)) if args.operation=='collect' else None
    try:
        result=operate(Path('/work/c10-private'),Path('/out'),args.audit,args.operation,confirm=args.confirm,key=key)
        import json
        print(json.dumps(result,indent=2))
        if result.get('export',{}).get('outcome','exported') != 'exported':
            print('Collection did not export: '+', '.join(result['export']['reasons'])+
                  '. Private originals remain; no repeat or continuation is authorized.',file=sys.stderr)
        return result['exit'] != 0 or result.get('export',{}).get('outcome','exported')!='exported'
    except Exception:
        print('Operator observation incomplete; private command records remain. Inspect status before another action.',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
