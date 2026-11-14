"""Prepare, launch and review bounded C10 small-commission batches.

Rehearsals use offline Linux containers and synthetic credentials. Live launch
needs a qualified binary or explicitly bound unqualified study build, a matching rehearsal, an exact authorized
commission digest and hidden entry or an explicitly selected saved connection.
Each launch performs one placement. A later placement of a retained audit needs
its own continuation packet, approved by exact digest, and `continue`; nothing
continues, repeats or retries a placement on its own.
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
from common import (BINDINGS,CONTINUED,HERE,LIMITS,MAX_PLACEMENTS,REPO,SOURCE_PATHS,catalog,compact,digest,
    file_hash,identifier,proposal,read_file,rehearsal_packet,require,scan_tree,source_hash,strict_json,
    validate_continuation,validate_packet,write_json)
from launch import hidden_credential,host_environment,select_qualification
from batch import allowance_facts
from verify import Evidence,ordinary_submission,serial_names,verify
from session import failure_details
from reporting import ReportError, current_issues, review_exports, write_report
from connections import ConnectionError, lookup as connection_key, status as connection_status, validate_label
from study import (copy_submission, inspect_submission, resolve_submission,
                   study_proposal, supplied_runs)
import study_build


def bindings(qualification_id,build=None):
    env=host_environment()
    require(not subprocess.check_output(['git','status','--porcelain','--',*SOURCE_PATHS],cwd=REPO,env=env),
            'commit apparatus sources before binding or launching')
    result=subprocess.run(['python3','-I','-B','apparatus/qualified.py','check'],cwd=REPO,env=env,capture_output=True)
    require(result.returncode==0,'qualification record check failed')
    qualification,binaries=select_qualification(REPO,qualification_id)
    if build is not None:
        binaries=study_build.select(REPO,qualification,build)
    bound={'qualification_id':qualification_id,
        'binary_sha256':file_hash(binaries/'stewart'),
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,env=env).decode().strip(),
        'apparatus_sha256':source_hash(),'image':'docker.io/library/python@'+qualification['python_image'],
        'catalog_sha256':file_hash(HERE/'catalog.json')}
    return bound,binaries,result


def review_batch(root):
    return review_exports(Path(root)/'container')


CONTAINER=r'stewart-c10-[0-9]+-[0-9]+'
CODE=r'/work/code(-[0-9a-f]{12})?'
READY_SECONDS=300
# How long a placement process that was sent no credential gets to record its own refusal.
STOP_SECONDS=30


class Refused(ValueError):
    """A fixed reason written in this file, raised before any container or credential use."""


def refuse(ok,reason):
    if not ok:
        raise Refused(reason)


def safe_reason(error):
    """A reason authored in the apparatus may be shown; any other exception text may not."""
    text=str(error)
    return text if type(error) in [ValueError,Refused] and re.fullmatch(r"[A-Za-z0-9 ,;:'()./–-]{1,200}",text) else 'unreadable or malformed'


def scratch_folder(path,what):
    refuse(path.is_absolute() and path.parent==REPO/'.scratch' and identifier(path.name) and not path.is_symlink(),
           what+' must be an absolute path directly under .scratch, named with lowercase letters, digits and hyphens')
    return path


def retained_launch(evidence):
    """The original launch's own host records. They are read, never rewritten."""
    scratch_folder(evidence,'the retained evidence folder')
    refuse(evidence.is_dir(),'the retained evidence folder of the original launch does not exist')
    try:
        operator=strict_json(read_file(evidence/'host/operator.json'))
        launch_raw=read_file(evidence/'host/RESULT.json')
        launch=strict_json(launch_raw)
        raw=read_file(evidence/'staging/commission.json')
        packet=strict_json(raw)
        refuse(launch['schema']=='stewart.c10-launch/2' and launch['mode'] in ['rehearse','live'],
               'the evidence folder does not hold an original launch record')
        refuse(digest(raw)==launch['commission_sha256'],'the retained packet differs from its launch record')
        refuse(isinstance(operator['container'],str) and re.fullmatch(CONTAINER,operator['container'])
               and operator['container']==launch['container'] and isinstance(operator['audits'],list),
               'the retained container identity is missing or inconsistent')
        refuse(all(isinstance(launch['bindings'][key],str) for key in ['binary_sha256','image'])
               and isinstance(packet['limits'],dict),
               'the retained launch record names no writer or image')
    except Refused:
        raise
    except (OSError,ValueError,KeyError,TypeError):
        raise Refused('the retained launch records are missing or unreadable') from None
    return {'folder':evidence,'operator':operator,'launch':launch,'launch_sha256':digest(launch_raw),'packet':packet}


# --- The container half's interface. placements.py owns these records; only the
# members named here are relied on, so a difference is reconciled in one place.

def continuation_folder(evidence,audit,placement):
    """Where the retained container publishes one placement's attempts, seen through its /out mount."""
    return evidence/'container/continuations'/f'{audit}-p{placement}'


def attempt_folder(evidence,audit,placement,attempt):
    return continuation_folder(evidence,audit,placement)/f'attempt-{attempt}'


def next_attempt(evidence,audit,placement):
    """Which attempt of a placement may start now, from what the container already published.

    The container numbers attempts from 1 without gaps. Another attempt is
    permitted only when every earlier one holds its own result saying no model
    process was started. A missing or unreadable result, a failure record
    alone or any other state means the placement started or may have started,
    and it is never attempted again.
    """
    folder=continuation_folder(evidence,audit,placement)
    if not folder.exists() and not folder.is_symlink():
        return 1
    refuse(folder.is_dir() and not folder.is_symlink(),
           'the placement holds records that are not numbered attempts; reconcile them before any further launch')
    earlier=list(folder.iterdir())
    refuse(sorted(path.name for path in earlier)==sorted(f'attempt-{number}' for number in range(1,len(earlier)+1))
           and all(path.is_dir() and not path.is_symlink() for path in earlier),
           'the placement holds records that are not numbered attempts; reconcile them before any further launch')
    for path in earlier:
        try:
            record=strict_json(read_file(path/'RESULT.json'))
            settled=(record['schema']=='stewart.c10-continuation-session/1' and record['audit']==audit
                     and record['placement']==placement and record['placement_state']=='not_started')
        except (OSError,ValueError,KeyError,TypeError):
            settled=False
        refuse(settled,'an earlier attempt of this placement started or may have started; reconcile its retained records, never repeat it')
    return len(earlier)+1


def ready_record(audit,placement,attempt):
    return {'continuation_preflight_verified':True,'audit':audit,'placement':placement,'attempt':attempt}


def recorded_not_started(path,mode,audit,placement):
    """The stage at which the container says this attempt stopped before any model process, else None."""
    try:
        session=strict_json(read_file(path))
        if not (session['schema']=='stewart.c10-continuation-session/1' and session['mode']==mode
                and session['audit']==audit and session['placement']==placement
                and session['placement_state']=='not_started'):
            return None
        stage=(session.get('failure') or {}).get('phase')
        return stage if isinstance(stage,str) and re.fullmatch(r'[a-z0-9_.-]{1,80}',stage) else 'an unnamed stage'
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return None


def placement_argv(name,code,mode,packet_path):
    return ['container','exec','--interactive',name,'env','-i','PATH=/usr/local/bin:/usr/bin:/bin','HOME=/work',
            'python3','-I','-B',code+'/apparatus/c10/placements.py',mode,'--binary','/bin-in/stewart','--packet',packet_path]


def continuation_session(path,mode,audit,placement):
    """The container's result for one continuation; exit status alone establishes nothing."""
    session=strict_json(read_file(path))
    require(session['schema']=='stewart.c10-continuation-session/1' and session['mode']==mode
            and session['audit']==audit and session['placement']==placement,
            'continuation result names another placement')
    require(session['placement_state']=='observed' and session['failed'] is False,
            'continuation placement unobserved or failed; review retained results')
    if mode=='rehearse':
        require(session['expected_observation'] is True,'rehearsal continuation differs from its control')
        # After the placement the container offers the same packet to its preflight
        # again; the service's own placement count must be what refuses it.
        require(session['second_start']=={'refused':True,'phase':'preflight.prior_runs'},
                'a second start of the same placement was not refused by the placement count')
    return session


# Comparisons the container runs on a continued control after its final
# placement. Reviewer: (cases run, controls among them, controls without a
# subject in that control's evidence); one of the cases is an invariance. The
# unheld control's signal may or may not find a request on the wire, and only
# then has the request-cap control a subject, so it has two admissible shapes.
CONTINUED_REVIEW={'continue-cap':[(11,10,3)],'continue-entries':[(12,11,2)],'reminder-spent':[(14,13,0)],
    'reminder-spent-unheld':[(13,12,1),(14,13,0)],'reminder-spent-submits':[(14,13,0)],
    'reminder-unused':[(14,13,0)]}
CONTINUED_REPORT=14
CONTINUED_OPERATIONS=8


def continuation_controls(session,scenario):
    """Reviewer, report and operator comparisons the container ran on a control's finished audit.

    The reviewer and report comparisons run for every continued control, the
    operator comparisons (manager close, confirmation and follow-up export of
    a multi-placement audit) for exactly those that end unsubmitted. Every
    family must show its exact count, all passed, none failed or skipped,
    every reviewer control fired and its originals unchanged.
    """
    controls=session['controls']
    require(isinstance(controls,dict) and set(controls)=={'review','reporting','operations'},
            'continued-audit controls missing')
    def complete(family,run):
        return (family is not None and family['run']==family['passed']==run and type(family['run']) is int
                and family['failed']==0 and family['original_unchanged'] is True)
    review=controls['review']
    require(review is not None and isinstance(review['not_applicable'],list)
            and any(complete(review,run) and review['controls']==review['controls_fired']==fired
                    and len(review['not_applicable'])==absent for run,fired,absent in CONTINUED_REVIEW[scenario])
            and review['skipped']==0,'continued-audit reviewer controls failed, incomplete or differ in count')
    require(complete(controls['reporting'],CONTINUED_REPORT),
            'continued-audit report controls failed, incomplete or differ in count')
    if CONTINUED[scenario]['endings'][-1][0]=='ended_unsubmitted':
        require(complete(controls['operations'],CONTINUED_OPERATIONS),
                'continued-audit operator controls failed, incomplete or differ in count')
    else:
        require(controls['operations'] is None,'operator controls ran on a submitted audit')


# --- Prior state, read from an export's own log as INTERFACE 4.5 and 6.4 define it.

def placement_history(evidence):
    """Recorded placements of the one audit in an export: count, endings, usage and log head.

    Usage is the sum of every run_ended record's reported and estimated charge,
    which is what the cumulative limits count. A placement with no run_ended
    leaves `complete` false: its accounting needs reconciliation by the writer.
    """
    audits={name.split('/')[2] for name in evidence.names if name.startswith('archive/audits/')}
    require(len(audits)==1,'one_audit')
    names=serial_names(evidence.names,'archive/audits/'+audits.pop()+'/log/',r'([1-9][0-9]*)\.json')
    require(bool(names),'log_present')
    started,ended,endings,previous=[],[],[],None
    usage=dict.fromkeys(LIMITS,0)
    for name in names:
        raw=evidence.read(name)
        record=strict_json(raw)
        require(record['body']['prev']==previous,'log_chain')
        previous=digest(raw)
        body=record['body']
        if record['kind']=='run_started':
            started.append(body['run'])
        elif record['kind']=='run_ended':
            ended.append(body['run'])
            endings.append([body['ending'],body['cause']])
            for key in LIMITS:
                charge=body['usage'][key]
                require(all(type(charge[part]) is int and charge[part]>=0 for part in ['reported','estimated']),
                        'placement_usage')
                usage[key]+=charge['reported']+charge['estimated']
    return {'runs':len(started),'endings':endings,'usage':usage,'log_head_sha256':previous,
            'complete':started==ended==list(range(1,len(started)+1))}


def observed_prior(evidence,audit):
    """What the audit's latest export establishes. Nothing runs in the container."""
    try:
        rows=[row for row in review_batch(evidence)['audits'] if row['audit']==audit]
    except (OSError,ValueError,KeyError,TypeError):
        raise Refused('the retained exports cannot be reviewed') from None
    refuse(len(rows)==1 and bool(rows[0]['snapshots']),'the audit has no export to read its prior state from')
    latest=rows[0]['snapshots'][-1]
    refuse(latest['export']=='exported' and (latest.get('review') or {}).get('outcome')=='checked',
           'the latest export of this audit is not a checked observation; collect and review it before a continuation')
    try:
        reader=Evidence(evidence/'container'/audit/latest['snapshot']/'work.tar',latest['archive']['sha256'])
        try:
            info=reader.json('operator.json')
            history=placement_history(reader)
        finally:
            reader.close()
        refuse(info['audit']==audit and isinstance(info['reference'],str),'the export belongs to another audit')
    except Refused:
        raise
    except (OSError,ValueError,KeyError,TypeError,IndexError):
        raise Refused('the latest export does not hold a readable placement history') from None
    refuse(history['runs']>0 and history['complete'],
           'the last placement has no recorded ending; reconciling a dead placement is outside this apparatus')
    return {'snapshot':latest['snapshot'],'export_sha256':latest['archive']['sha256'],'reference':info['reference'],
            'runs':history['runs'],'last_ending':history['endings'][-1][0],'last_cause':history['endings'][-1][1],
            'log_head_sha256':history['log_head_sha256'],'usage':history['usage']}


def checked_continuation(value,**mode):
    try:
        return validate_continuation(value,**mode)
    except (ValueError,KeyError,TypeError,AttributeError) as error:
        raise Refused('continuation packet is not valid: '+safe_reason(error)) from None


def check_retained(packet,retained,evidence):
    """The packet continues exactly the audit, container and commission this launch retained."""
    operator,original=retained['operator'],retained['packet']
    refuse(packet['evidence']==str(evidence),'packet names another evidence folder')
    refuse(packet['container']==operator['container'],'packet names another container')
    refuse(packet['audit'] in operator['audits'],'packet names an audit this launch did not retain')
    refuse(packet['model']==original['model'] and packet['limits']==original['limits'],
           'model or cumulative limits differ from the retained commission')
    refuse(original['schema']!='stewart.interruption-commission/1'
           or packet['max_placements']==original['max_placements'],
           'placement ceiling differs from the one commissioned for this audit')


def check_prior(packet,observed):
    prior=packet['prior']
    refuse(packet['reference']==observed['reference'],'packet names another audit reference')
    refuse(all(prior[key]==observed[key] for key in ['runs','last_ending','last_cause']),
           'prior placement count or ending differs from the latest export')
    refuse(prior['log_head_sha256'] in [None,observed['log_head_sha256']],
           'prior log head differs from the latest export')
    refuse(prior['usage'] in [None,observed['usage']],'prior usage differs from the latest export')


def allowance_outlook(limits,usage,interruption):
    """What INTERFACE 6.3 and 6.4 leave a placement, as the container's preflight also records it.

    Sizing advice for whoever commissions the packet. Nothing is refused on it.
    """
    return allowance_facts({key:{'limit':limits[key],'used':usage[key]} for key in LIMITS},
                           None if interruption is None else {'after':interruption,'signal':'SIGTERM'})


def continuation_proposal(evidence,audit=None,*,max_placements=None,interruption=None,stop_after_seconds=None):
    """An unpaid, unbound packet for the audit's next placement, from retained records alone."""
    retained=retained_launch(evidence)
    original,audits=retained['packet'],retained['operator']['audits']
    if audit is None:
        refuse(len(audits)==1,'this launch retained several audits; name one with --audit')
        audit=audits[0]
    refuse(audit in audits and identifier(audit),'this launch did not retain that audit')
    observed=observed_prior(evidence,audit)
    if max_placements is None:
        refuse(original['schema']=='stewart.interruption-commission/1',
               'the retained commission allowed one placement; state the newly commissioned ceiling with --max-placements')
        max_placements=original['max_placements']
    packet={'schema':'stewart.c10-continuation/1','evidence':str(evidence),'audit':audit,
        'container':retained['operator']['container'],'reference':observed['reference'],
        'placement':observed['runs']+1,'max_placements':max_placements,
        'prior':{key:observed[key] for key in ['runs','last_ending','last_cause','log_head_sha256','usage']},
        'model':original['model'],'limits':original['limits'],'endpoint':original['endpoint'],'proxy':None,
        'interruption':None if interruption is None else {'after':interruption,'signal':'SIGTERM'},
        'permitted_request_attempts':4,'automatic_continuation':False,
        'stop_after_seconds':original['stop_after_seconds'] if stop_after_seconds is None else stop_after_seconds,
        'spending_authority':None,'account':dict.fromkeys(['account_label','workspace_id','credential_label']),
        'bindings':dict.fromkeys(BINDINGS)}
    checked_continuation(packet,rehearsal=retained['launch']['mode']=='rehearse')
    check_retained(packet,retained,evidence)
    return packet


def interrupted_study(packet,point,max_placements):
    """A study whose first placement is signalled at a witnessed point; common validates it."""
    return {**packet,'schema':'stewart.interruption-commission/1','max_placements':max_placements,
            'interruption':{'after':point,'signal':'SIGTERM'}}


def bind_continuation(value,qualification):
    """Bind an unpaid continuation proposal to the committed apparatus and the audit's own writer."""
    refuse(isinstance(value,dict),'continuation packet is not valid: not an object')
    checked_continuation(value,rehearsal=value.get('model')=='rehearsal-only')
    refuse(value['spending_authority'] is None and all(v is None for v in value['account'].values()),
           'bind an unpaid proposal with null account fields')
    evidence=Path(value['evidence'])
    retained=retained_launch(evidence)
    check_retained(value,retained,evidence)
    bound,_,_=bindings(qualification,retained['packet'].get('study_build'))
    refuse(all(bound[key]==retained['launch']['bindings'][key] for key in ['binary_sha256','image']),
           'the qualified writer or image differs from the retained launch')
    return {**value,'bindings':bound}


# --- Delivery into an existing container. Both scripts run there as
# `python3 -I -B -c SCRIPT TARGET SHA256` with the bytes on standard input, and
# touch nothing outside TARGET. /work/code and every earlier directory stay as they are.

DELIVER_SOURCE=r'''
import hashlib, io, json, os, sys, tarfile
target, expected = sys.argv[1], sys.argv[2]
raw = sys.stdin.buffer.read()
if hashlib.sha256(raw).hexdigest() != expected:
    sys.exit('source archive differs from its digest; nothing was written')
os.umask(0o022)
want = {}
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
    for member in archive:
        name = member.name.rstrip('/')
        parts = name.split('/')
        if (not name or any(part in ('', '.', '..') for part in parts) or name in want
                or not (member.isfile() or member.isdir())):
            sys.exit('source archive has an unsafe, repeated or nonregular member; nothing was written')
        for depth in range(1, len(parts)):
            want.setdefault('/'.join(parts[:depth]), None)
        want[name] = (archive.extractfile(member).read(), member.mode) if member.isfile() else None
try:
    os.mkdir(target, 0o755)
    created = True
except FileExistsError:
    created = False
if created:
    for name in sorted(want):
        path = os.path.join(target, name)
        if want[name] is None:
            os.mkdir(path, 0o755)
        else:
            mode = 0o755 if want[name][1] & 0o100 else 0o644
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode), 'wb') as stream:
                stream.write(want[name][0])
    with open(os.path.join(target, '.ready'), 'xb'):
        pass
else:
    found = {}
    for folder, directories, files in os.walk(target):
        for name in directories + files:
            path = os.path.join(folder, name)
            key = os.path.relpath(path, target)
            if os.path.islink(path):
                found[key] = 'link'
            elif os.path.isdir(path):
                found[key] = None
            else:
                with open(path, 'rb') as stream:
                    found[key] = stream.read()
    expected_tree = {name: None if value is None else value[0] for name, value in want.items()}
    expected_tree['.ready'] = b''
    if found != expected_tree:
        sys.exit('existing code directory differs from the committed source; nothing was changed')
print(json.dumps({'created': created, 'members': len(want)}))
'''

DELIVER_PACKET=r'''
import hashlib, json, os, sys
target, expected = sys.argv[1], sys.argv[2]
raw = sys.stdin.buffer.read()
if hashlib.sha256(raw).hexdigest() != expected:
    sys.exit('packet differs from its digest; nothing was written')
os.umask(0o077)
folder = os.path.dirname(target)
os.makedirs(os.path.dirname(folder), mode=0o700, exist_ok=True)
try:
    os.mkdir(folder, 0o700)
except FileExistsError:
    sys.exit('a packet was already delivered for this record folder; nothing was changed')
with open(target, 'xb') as stream:
    stream.write(raw)
print(json.dumps({'delivered': True, 'sha256': expected}))
'''


def in_container(name,command,*,interactive=False):
    return ['container','exec']+(['--interactive'] if interactive else [])+[name,
            'env','-i','PATH=/usr/local/bin:/usr/bin:/bin',*command]


def network_preflight(name):
    return in_container(name,['python3','-I','-B','-c','import socket; s=socket.create_connection(("api.anthropic.com",443),timeout=15); s.close(); print("TCP connection established; no credential or API request sent")'])


def run_step(host,env,label,argv,source=None):
    """Retain one host command's argv, both streams and exit. Input bytes come from a retained file."""
    write_json(host/(label+'.argv.json'),argv)
    with (host/(label+'.stdout')).open('xb') as stdout,(host/(label+'.stderr')).open('xb') as stderr:
        if source is None:
            result=subprocess.run(argv,cwd=REPO,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr)
        else:
            with source.open('rb') as stream:
                result=subprocess.run(argv,cwd=REPO,env=env,stdin=stream,stdout=stdout,stderr=stderr)
    (host/(label+'.exit')).write_text(str(result.returncode)+'\n')
    require(result.returncode==0,'host step failed; inspect retained records')


def await_ready(path,proc,seconds,ended,expired):
    """Wait for a published readiness record. The caller sends no credential unless this returns."""
    deadline=time.monotonic()+seconds
    while True:
        try:
            if path.stat().st_size:
                return strict_json(read_file(path))
        except FileNotFoundError:
            pass
        require(proc.poll() is None,ended)
        require(time.monotonic()<deadline,expired)
        time.sleep(.05)


def check_rehearsal_inputs(rehearsed,packet=None):
    validate_packet(rehearsed,rehearsal=True)
    expected=rehearsed['runs']
    fixed=[{k:v for k,v in run.items() if k!='submission_folder'} for run in expected if run.get('submission_folder') is None]
    require(fixed==rehearsal_packet()['runs'],'rehearsal omitted or changed fixed conformance controls')
    if packet is not None:
        require(rehearsed.get('study_build')==packet.get('study_build'),
                'study build differs from rehearsal')
        coverage={run['submission_sha256'] for run in supplied_runs(rehearsed)}
        require(all(run['submission_sha256'] in coverage for run in supplied_runs(packet)),
                'study inputs need their own successful rehearsal intake and review')
    return expected


def check_rehearsal(path,bound,packet=None,*,connection=False):
    host=strict_json(read_file(path/'host/RESULT.json'))
    session=strict_json(read_file(path/'container/RESULT.json'))
    require(host['schema']=='stewart.c10-launch/2' and session['schema']=='stewart.c10-session/2'
        and host['mode']=='rehearse' and host['outcome']=='completed'
        and session['outcome']=='passed' and session['local_iteration_only'] is False,
        'a successful retained Linux rehearsal is required')
    for key in ['apparatus_sha256','binary_sha256','image','catalog_sha256']:
        require(host['bindings'][key]==bound[key],'rehearsal source, binary, image or catalog differs')
    rehearsed=strict_json(read_file(path/'container/PLAN.json'))['commission']
    expected=check_rehearsal_inputs(rehearsed,packet)
    if connection:
        require(host.get('credential_source',{}).get('kind')=='keychain'
                and read_file(path/'host/connection-collect.exit')==b'0\n',
                'saved connections require a synthetic connection rehearsal and later collection')
    require(session['planned']==len(expected) and session['observed']==len(expected)
        and session['failed']==session['not_started']==0
        and session['skipped_checks']==[]
        and [r['audit'] for r in session['audits']]==[r['id'] for r in expected]
        and all(r['expected_observation'] is True for r in session['audits']), 'incomplete rehearsal inventory')
    report=review_batch(path)
    controls=strict_json(read_file(path/'container/review-controls/RESULT.json'))
    extra=2 if rehearsed.get('study_build') else 0
    require(controls['failed']==0 and controls['controls']==controls['controls_fired']==12+extra
            and controls['passed']==controls['run']==14+extra and controls['original_unchanged'] is True,
            'reviewer controls missing or incomplete')
    operations=strict_json(read_file(path/'container/operator-controls/RESULT.json'))
    require(operations['failed']==0 and operations['passed']==operations['run']==7
            and operations['original_snapshot_unchanged'] is True,
            'operator controls missing or incomplete')
    reporting=strict_json(read_file(path/'container/report-controls/RESULT.json'))
    require(reporting['failed']==0 and reporting['passed']==reporting['run']==11
            and reporting['original_unchanged'] is True,'report controls missing or incomplete')
    for run in supplied_runs(rehearsed):
        controls=strict_json(read_file(path/'container/study-review-controls'/run['id']/'RESULT.json'))
        reviewed = next(r for r in report['audits'] if r['audit'] == run['id'])['snapshots'][0]['review']
        guidance_extra = 4 if (reviewed.get('guidance') or {}).get('source') == 'guidance.md' else 0
        require(controls['failed']==0 and controls['passed']==controls['run']==18+extra+guidance_extra
                and controls['controls']==controls['controls_fired']==16+extra+guidance_extra and controls['original_unchanged'] is True,
                'study template controls missing or incomplete')
    for row,item in zip(report['audits'],expected):
        latest=row['snapshots'][0]
        if item['scenario'] in ['submitted','empty','lost-run-reply']:
            require(latest.get('review') is not None and ordinary_submission(latest['review']),'rehearsal submission review failed')
    if connection:
        first_audit=report['audits'][0]
        require(len(first_audit['snapshots'])>=2
                and ordinary_submission(first_audit['snapshots'][-1].get('review') or {'outcome':'incomplete'}),
                'saved-connection follow-up collection is missing or incomplete')
    check_rehearsed_continuations(path,host,expected,report,connection=connection)
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
        require(getattr(args,'study_build',None) is None,'live study identity comes from the approved packet')
        require(not getattr(args,'submission',None),'live submissions come from the approved packet')
        require(args.commission is not None and args.approved_commission is not None and args.rehearsal is not None,
                'live needs an exact approved commission and a retained rehearsal')
        raw=read_file(args.commission)
        require(digest(raw)==args.approved_commission,'commission differs from approved digest')
        packet=validate_packet(strict_json(raw),approved=True)
    else:
        require(args.commission is None and args.approved_commission is None and args.rehearsal is None,
                'rehearsal accepts no live packet')
        packet=(study_proposal('rehearsal-only',args.submission,rehearsal=True)
                if getattr(args,'submission',None) else rehearsal_packet())
        if getattr(args,'study_build',None) is not None:
            packet=study_build.attach(packet,strict_json(read_file(args.study_build)))
    connection=getattr(args,'connection',None)
    if connection is not None:
        validate_label(connection,packet if mode=='live' else None)
        if mode=='rehearse':
            packet['account']={'account_label':'synthetic connection rehearsal',
                'workspace_id':'offline','credential_label':connection}
    if mode=='rehearse':
        # Each continued control's later placement keeps its host records in its
        # own new folder beside this one, exactly as a live continuation does.
        for run in packet['runs']:
            if run['scenario'] in CONTINUED:
                record=continuation_record(out,run['id'],len(CONTINUED[run['scenario']]['endings']))
                refuse(identifier(record.name) and not record.exists(),
                       'continuation controls keep their records in new folders named after the rehearsal folder: give it a short unused name of lowercase letters, digits and hyphens')
    for run in supplied_runs(packet):
        case=inspect_submission(resolve_submission(run),run['case'],run['submission_sha256'])
        require(not packet.get('study_build') or case.get('guidance') is None,
                'choose supplied guidance or a study-build override, not both')
    bound,binaries,checked=bindings(args.qualification,packet.get('study_build'))
    if mode=='live':
        require(packet['bindings']==bound,'approved packet bindings changed')
        check_rehearsal(args.rehearsal,bound,packet,connection=connection is not None)
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
    report={'schema':'stewart.c10-launch/2','mode':mode,'bindings':bound,'container':name,
        'commission_sha256':digest(raw),'credential_sent':False,'started_at':time.time(),'outcome':'failed'}
    report['credential_source']={'kind':'keychain','service':'stewart-provider','account':connection} if connection else {'kind':'generated' if mode=='rehearse' else 'hidden-entry'}
    env=host_environment()
    phase='preparation'
    def step(label,argv):
        nonlocal phase
        phase=label
        run_step(host,env,label,argv)
    proc=None
    key=None
    synthetic=None
    try:
        if supplied_runs(packet):
            (staging/'submissions').mkdir(mode=0o700)
            for run in supplied_runs(packet):
                copy_submission(resolve_submission(run),staging/'submissions'/run['id'],run['submission_sha256'])
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
            step('network-preflight',network_preflight(name))
        write_json(host/'operator.json',{'container':name,'audits':[r['id'] for r in packet['runs']],'code':'/work/code',
            'command':['python3','-I','-B','apparatus/c10/c10.py','control',str(out),'AUDIT','status'],
            'close_ends_authoring':True,'automatic_continuation':False})
        argv=['container','exec','--interactive',name,'env','-i','PATH=/usr/local/bin:/usr/bin:/bin','HOME=/work',
              'python3','-I','-B','/work/code/apparatus/c10/batch.py',mode,'--binary','/bin-in/stewart','--packet','/in/commission.json']
        if supplied_runs(packet):
            argv+=['--submissions','/in/submissions']
        write_json(host/'session.argv.json',argv)
        print('Retained container '+name+'; operator commands in '+str(host/'operator.json'),flush=True)
        with (host/'container.stdout').open('xb') as stdout,(host/'container.stderr').open('xb') as stderr:
            phase='intake'
            proc=subprocess.Popen(argv,cwd=REPO,env=env,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr)
            ready=await_ready(exported/'READY.json',proc,READY_SECONDS,
                'container ended before intake completed; no credential sent',
                'intake deadline expired; inspect retained container')
            require(ready=={'credential_free_intake_verified':True,'audits':[r['id'] for r in packet['runs']]},'intake readiness differs from packet')
            print(json.dumps({'provider':'Anthropic','endpoint':packet['endpoint'],
                'manager_supplied_account':packet['account'],'credential_source':report['credential_source']}),flush=True)
            phase='credential-handoff'
            key=(connection_key(connection,rehearsal=mode=='rehearse',record=host/'connection.json')
                 if connection else (b'c10-NONFUNCTIONAL-'+os.urandom(24).hex().encode())
                 if mode=='rehearse' else hidden_credential())
            proc.stdin.write(key)
            proc.stdin.close()
            report['credential_sent']=True
            phase='placement'
            report['container_exit']=proc.wait()
        step('container-inspect',['container','inspect',name])
        phase='host-scan'
        report['host_scan']=scan_tree(out,key)
        require(not report['host_scan']['files_with_matches'] and not report['host_scan']['errors'],'host scan failed or uncertain')
        phase='batch-result'
        session=strict_json(read_file(exported/'RESULT.json'))
        report['session']={'path':'container/RESULT.json','sha256':file_hash(exported/'RESULT.json')}
        require(session['schema']=='stewart.c10-session/2' and report['container_exit']==0
                and session['failed']==0,'batch incomplete; review retained results')
        if mode=='rehearse':
            phase='rehearsal-controls'
            require(session['not_started']==0,'rehearsal inventory incomplete')
            controls=strict_json(read_file(exported/'review-controls/RESULT.json'))
            require(controls['failed']==0,'reviewer controls failed')
            controls=strict_json(read_file(exported/'operator-controls/RESULT.json'))
            require(controls['failed']==0,'operator controls failed')
            controls=strict_json(read_file(exported/'report-controls/RESULT.json'))
            require(controls['failed']==0,'report controls failed')
        report['outcome']='completed' if mode=='rehearse' else 'observed'
    except (Exception,KeyboardInterrupt) as error:
        report['error']=f'Launch observation incomplete at {phase}; inspect its retained command records and audit status before another action.'
        report['failure']=failure_details(error,'host')
        report['failure']['step']=phase
        if isinstance(error,ConnectionError):
            report['connection_error']=error.code
            report['error']=str(error)
        if proc is not None and proc.stdin is not None and not proc.stdin.closed:
            proc.stdin.close()
        if proc is not None and proc.poll() is None:
            report['container_process_state']='unknown; use recorded operator commands'
    finally:
        # Without a saved connection the continuation controls below reuse the
        # generated synthetic key from memory; it is never written or re-derived.
        if mode=='rehearse' and connection is None and report['outcome']=='completed':
            synthetic=key
        key=None
        report['ended_at']=time.time()
        write_json(host/'RESULT.json',report)
    print(json.dumps(report,indent=2))
    if mode=='rehearse' and report['outcome']=='completed':
        if connection:
            # A second launcher process makes a new Keychain lookup for later
            # collection. Its original placement and first snapshot stay unchanged.
            argv=[sys.executable,'-I','-B',str(HERE/'c10.py'),'control',str(out),
                  'open-ordinary-r1','collect','--connection',connection]
            try:
                step('connection-collect',argv)
            except (ValueError,OSError):
                print('Synthetic follow-up collection failed; inspect retained connection-collect records.',file=sys.stderr)
                return True
        if rehearse_continuations(out,packet,args.qualification,connection,synthetic):
            print('A continuation control failed or was not started; inspect host/continuations.json and each record folder. The rehearsal admits no live launch.',file=sys.stderr)
            return True
    return report['outcome']=='failed'


def continue_placement(args,*,synthetic_key=None):
    """One separately approved later placement of one retained audit, in its existing container.

    Every refusal above the first `mkdir` happens before the container or any
    credential is touched. After it, a failure leaves a record that is
    incomplete at a named phase, or `not_started` when the container's own
    result says it stopped before any model process. Nothing here retries; a
    further attempt is a new launch with a new record folder.
    """
    mode,evidence=args.mode,args.evidence
    out=scratch_folder(args.record,'the new record folder')
    refuse(not out.exists(),'the record folder already exists; each placement gets a new one and nothing is repeated')
    connection=getattr(args,'connection',None)
    try:
        raw=read_file(args.packet)
        value=strict_json(raw)
    except (OSError,ValueError):
        raise Refused('continuation packet is unreadable') from None
    if mode=='live':
        refuse(args.approved_packet is not None and args.rehearsal is not None,
               'a live continuation needs --approved-packet and a retained --rehearsal')
        refuse(digest(raw)==args.approved_packet,'packet differs from the approved digest')
    else:
        refuse(args.approved_packet is None and args.rehearsal is None,
               'a rehearsal continuation accepts no approval or rehearsal argument')
        refuse(connection is not None or synthetic_key is not None,
               'a rehearsal continuation needs its rehearsal\'s own synthetic credential: pass --connection, or let rehearse run it')
    packet=checked_continuation(value,rehearsal=mode=='rehearse',approved=mode=='live')
    if connection is not None:
        validate_label(connection,packet)
    retained=retained_launch(evidence)
    check_retained(packet,retained,evidence)
    refuse(retained['launch']['mode']==mode,'a rehearsal audit continues only in rehearsal and a live audit only live')
    refuse(retained['launch']['outcome'] in ['completed','observed'],
           'the original launch record is incomplete; reconcile it before a continuation')
    audit,placement,name=packet['audit'],packet['placement'],packet['container']
    attempt=next_attempt(evidence,audit,placement)
    published=attempt_folder(evidence,audit,placement,attempt)
    observed=observed_prior(evidence,audit)
    check_prior(packet,observed)
    try:
        bound,binaries,checked=bindings(args.qualification,retained['packet'].get('study_build'))
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        raise Refused('bindings unavailable: '+safe_reason(error)) from None
    refuse(packet['bindings']==bound,'packet bindings differ from the committed apparatus and selected qualification')
    refuse(all(bound[key]==retained['launch']['bindings'][key] for key in ['binary_sha256','image']),
           'the qualified writer or image differs from the retained launch')
    if mode=='live':
        try:
            check_rehearsal(args.rehearsal,bound,retained['packet'],connection=connection is not None)
        except (ValueError,OSError,KeyError,TypeError,IndexError) as error:
            raise Refused('retained rehearsal refused: '+safe_reason(error)) from None
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    out.mkdir(mode=0o700)
    host,staging=out/'host',out/'staging'
    for folder in [host,staging]:
        folder.mkdir(mode=0o700)
    (staging/'commission.json').write_bytes(raw)
    (host/'qualification-check.stdout').write_bytes(checked.stdout)
    (host/'qualification-check.stderr').write_bytes(checked.stderr)
    (host/'qualification-check.exit').write_text(str(checked.returncode)+'\n')
    report={'schema':'stewart.c10-continuation-launch/1','mode':mode,'evidence':str(evidence),
        'retained_launch':{'path':str(evidence/'host/RESULT.json'),'sha256':retained['launch_sha256']},
        'container':name,'audit':audit,'placement':placement,'attempt':attempt,'reference':packet['reference'],
        'bindings':bound,'commission_sha256':digest(raw),'prior_observed':observed,
        'credential_sent':False,'started_at':time.time(),'outcome':'failed'}
    report['credential_source']=({'kind':'keychain','service':'stewart-provider','account':connection} if connection
        else {'kind':'rehearsal-generated' if mode=='rehearse' else 'hidden-entry'})
    env=host_environment()
    phase='preparation'
    def step(label,argv,source=None):
        nonlocal phase
        phase=label
        run_step(host,env,label,argv,source)
    proc=None
    key=None
    consistent=True
    try:
        step('version',['container','--version'])
        require('version 1.6.1 ' in (host/'version.stdout').read_text(),'Apple container 1.6.1 required')
        step('system-status',['container','system','status'])
        step('container-ready',['container','exec',name,'sh','-c','test -d /work/c10-private/'+audit])
        step('source',['git','archive','--format=tar','-o',str(staging/'source.tar'),'HEAD',*SOURCE_PATHS])
        archive=file_hash(staging/'source.tar')
        code='/work/code-'+archive[:12]
        step('source-delivery',in_container(name,['python3','-I','-B','-c',DELIVER_SOURCE,code,archive],interactive=True),
             staging/'source.tar')
        delivered=strict_json(read_file(host/'source-delivery.stdout'))
        require(type(delivered['created']) is bool,'source delivery reply differs')
        report['code']={'directory':code,'source_archive_sha256':archive,'created':delivered['created']}
        target=f'/work/continuation-packets/{out.name}/commission.json'
        step('packet-delivery',in_container(name,['python3','-I','-B','-c',DELIVER_PACKET,target,digest(raw)],interactive=True),
             staging/'commission.json')
        report['packet']=target
        if mode=='live':
            step('network-preflight',network_preflight(name))
        write_json(host/'operator.json',{'container':name,'audits':[audit],'code':code,'evidence':str(evidence),
            'placement':placement,'attempt':attempt,'command':['python3','-I','-B','apparatus/c10/c10.py','control',str(out),'AUDIT','status'],
            'close_ends_authoring':True,'automatic_continuation':False})
        argv=placement_argv(name,code,mode,target)
        write_json(host/'placement.argv.json',argv)
        print('Continuing in retained container '+name+'; operator commands in '+str(host/'operator.json'),flush=True)
        with (host/'placement.stdout').open('xb') as stdout,(host/'placement.stderr').open('xb') as stderr:
            phase='preflight'
            proc=subprocess.Popen(argv,cwd=REPO,env=env,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr)
            ready=await_ready(published/'READY.json',proc,READY_SECONDS,
                'placement process ended before its preflight completed; no credential sent',
                'preflight deadline expired; no credential sent')
            # The container chose its attempt number itself; it must be the one expected here.
            consistent=ready==ready_record(audit,placement,attempt)
            require(consistent,'preflight readiness names another audit, placement or attempt; no credential sent')
            require(proc.poll() is None,'placement process ended before credential handoff; no credential sent')
            print(json.dumps({'provider':'Anthropic','endpoint':packet['endpoint'],
                'manager_supplied_account':packet['account'],'credential_source':report['credential_source']}),flush=True)
            phase='credential-handoff'
            key=(connection_key(connection,rehearsal=mode=='rehearse',record=host/'connection.json')
                 if connection else synthetic_key if mode=='rehearse' else hidden_credential())
            proc.stdin.write(key)
            proc.stdin.close()
            report['credential_sent']=True
            phase='placement'
            report['container_exit']=proc.wait()
        step('container-inspect',['container','inspect',name])
        phase='host-scan'
        # New exports and the continuation's records land in the earlier folder
        # through the container's existing /out mount, so both trees are scanned.
        report['host_scan']={'record':scan_tree(out,key),'evidence':scan_tree(evidence,key)}
        require(all(not scan['files_with_matches'] and not scan['errors'] for scan in report['host_scan'].values()),
                'host scan failed or uncertain')
        phase='placement-result'
        report['session']={'path':str(published/'RESULT.json'),'sha256':file_hash(published/'RESULT.json')}
        session=continuation_session(published/'RESULT.json',mode,audit,placement)
        scenario=next((run['scenario'] for run in retained['packet']['runs'] if run['id']==audit),None)
        if mode=='rehearse' and scenario in CONTINUED and placement==len(CONTINUED[scenario]['endings']):
            # The fixed control is finished: its comparisons are part of this result.
            continuation_controls(session,scenario)
        require(report['container_exit']==0,'placement incomplete; review retained results')
        report['outcome']='completed' if mode=='rehearse' else 'observed'
    except (Exception,KeyboardInterrupt) as error:
        report['error']=f'Continuation observation incomplete at {phase}; inspect its retained command records and audit status before another action. Nothing is retried.'
        report['failure']=failure_details(error,'host')
        report['failure']['step']=phase
        if isinstance(error,ConnectionError):
            report['connection_error']=error.code
            report['error']=str(error)
        if proc is not None and proc.stdin is not None and not proc.stdin.closed:
            proc.stdin.close()
        if proc is not None and proc.poll() is None and not report['credential_sent']:
            # Its input ended with no credential, so it can only refuse; let it record that.
            try:
                proc.wait(timeout=STOP_SECONDS)
            except subprocess.TimeoutExpired:
                pass
        if proc is not None and proc.poll() is None:
            report['container_process_state']='unknown; use recorded operator commands'
        elif proc is not None:
            report.setdefault('container_exit',proc.returncode)
    finally:
        key=None
        # The container's own records of this attempt, by reference only.
        for label,member in [('session','RESULT.json'),('container_failure','FAILURE.json')]:
            try:
                report.setdefault(label,{'path':str(published/member),'sha256':file_hash(published/member)})
            except (OSError,ValueError):
                pass
        if report['outcome']=='failed' and consistent and proc is not None and proc.poll() is not None:
            stage=recorded_not_started(published/'RESULT.json',mode,audit,placement)
            if stage is not None:
                # Not an observation gap: the container says it stopped before any model process.
                report['outcome']='not_started'
                report['not_started']={'container_stage':stage,'host_step':phase}
                report['error']=(f'Not started at {stage}: the container recorded that this attempt stopped before any model process. '
                    'A further attempt is permitted as a new launch with a new record folder; nothing is retried here.')
        report['ended_at']=time.time()
        write_json(host/'RESULT.json',report)
    print(json.dumps(report,indent=2))
    return report['outcome'] not in ['completed','observed']


def continuation_record(evidence,audit,placement):
    """Host record folder a rehearsal uses for one control's later placement."""
    return evidence.parent/f'{evidence.name}-{audit}-p{placement}'


def rehearse_continuations(out,packet,qualification,connection,key):
    """Run the later placement of every continued control through `continue`.

    With a saved connection each one is a new launcher process making its own
    Keychain lookup. Otherwise the rehearsal's generated key is reused here and
    never written. The first failure leaves the remaining controls not started.
    """
    host,env=out/'host',host_environment()
    rows,halted=[],False
    for run in packet['runs']:
        if run['scenario'] not in CONTINUED:
            continue
        endings=CONTINUED[run['scenario']]['endings']
        record=continuation_record(out,run['id'],len(endings))
        row={'audit':run['id'],'record':str(record),'started':False,'failed':None}
        if not halted:
            try:
                proposed=continuation_proposal(out,run['id'],max_placements=len(endings))
                refuse([proposed['prior']['last_ending'],proposed['prior']['last_cause']]==endings[0],
                       'the first placement did not end as this control specifies')
                proposed.update(spending_authority=packet['spending_authority'],account=packet['account'],
                                bindings=packet['bindings'])
                path=host/('continuation-'+run['id']+'.json')
                write_json(path,proposed)
                row['packet_sha256']=file_hash(path)
                row['started']=True
                if connection:
                    run_step(host,env,'continue-'+run['id'],[sys.executable,'-I','-B',str(HERE/'c10.py'),'continue',
                        'rehearse',str(out),str(record),'--packet',str(path),'--qualification',qualification,
                        '--connection',connection])
                    row['failed']=False
                else:
                    row['failed']=bool(continue_placement(argparse.Namespace(mode='rehearse',evidence=out,record=record,
                        packet=path,approved_packet=None,rehearsal=None,qualification=qualification,connection=None),
                        synthetic_key=key))
            except (ValueError,OSError,KeyError,TypeError) as error:
                row['failed']=True
                row['failure']=failure_details(error,'host')
                row['reason']=safe_reason(error)
            halted=row['failed']
        rows.append(row)
    result={'schema':'stewart.c10-rehearsal-continuations/1','planned':len(rows),
        'completed':sum(row['failed'] is False for row in rows),'failed':sum(row['failed'] is True for row in rows),
        'not_started':sum(row['failed'] is None for row in rows),'continuations':rows}
    write_json(host/'continuations.json',result)
    print(json.dumps(result,indent=2))
    return result['completed']!=result['planned']


def check_rehearsed_continuations(path,host,expected,report,*,connection=False):
    """Every continued control reached its specified endings through the host continuation path."""
    continued=[run for run in expected if run['scenario'] in CONTINUED]
    require([run['scenario'] for run in continued]==list(CONTINUED),'rehearsal omitted a continuation control')
    try:
        record=strict_json(read_file(path/'host/continuations.json'))
    except FileNotFoundError:
        record={'schema':None}
    require(record['schema']=='stewart.c10-rehearsal-continuations/1'
            and record['planned']==record['completed']==len(continued)
            and record['failed']==record['not_started']==0
            and [row['audit'] for row in record['continuations']]==[run['id'] for run in continued],
            'continuation controls missing, failed or not started')
    reviewed={row['audit']:row for row in report['audits']}
    for run,row in zip(continued,record['continuations']):
        endings=CONTINUED[run['scenario']]['endings']
        placement=len(endings)
        # A rehearsed control is continued once: its first attempt is the one that must have passed.
        result=attempt_folder(path,run['id'],placement,1)/'RESULT.json'
        launch=strict_json(read_file(continuation_record(path,run['id'],placement)/'host/RESULT.json'))
        require(launch['schema']=='stewart.c10-continuation-launch/1' and launch['mode']=='rehearse'
                and launch['outcome']=='completed' and launch['evidence']==str(path)
                and launch['container']==host['container'] and launch['audit']==run['id']
                and launch['placement']==placement and launch['attempt']==1 and launch['bindings']==host['bindings']
                and launch['commission_sha256']==row['packet_sha256']
                and launch['code']['directory']=='/work/code-'+launch['code']['source_archive_sha256'][:12]
                and launch['session']=={'path':str(result),'sha256':file_hash(result)},
                'continuation control did not complete through the host path')
        require(not connection or launch['credential_source']['kind']=='keychain',
                'saved connections require a synthetic connection continuation')
        continuation_controls(continuation_session(result,'rehearse',run['id'],placement),run['scenario'])
        snapshots=reviewed[run['id']]['snapshots']
        latest=snapshots[-1]
        require(len(snapshots)>=placement and latest['export']=='exported'
                and (latest.get('review') or {}).get('outcome')=='checked',
                'continued audit lacks a checked export after its final placement')
        reader=Evidence(path/'container'/run['id']/latest['snapshot']/'work.tar',latest['archive']['sha256'])
        try:
            history=placement_history(reader)
        finally:
            reader.close()
        require(history['complete'] and history['endings']==endings,
                'continued audit did not end as its control specifies')
        require(ordinary_submission(latest['review']) is (endings[-1][0]=='sealed'),
                'continued audit submission differs from its control')


def host_control(args):
    meta=strict_json(read_file(args.evidence/'host/operator.json'))
    require(args.audit in meta['audits'] and identifier(args.audit),'unknown audit')
    require(re.fullmatch(CONTAINER,meta['container']),'unknown container identity')
    # A continuation's record folder names the code directory delivered for it:
    # the launch-time /work/code of an older container cannot read later placements.
    code=meta.get('code','/work/code')
    require(isinstance(code,str) and re.fullmatch(CODE,code),'unknown code directory')
    earlier=None
    if 'evidence' in meta:
        # The container's /out is the original launch's folder; later exports land there.
        earlier=retained_launch(Path(meta['evidence']))
        require(earlier['operator']['container']==meta['container'] and args.audit in earlier['operator']['audits'],
                'record folder names another retained audit')
    connection=getattr(args,'connection',None)
    if connection is not None:
        require(args.operation=='collect','--connection is only used for collection')
        raw=read_file(args.evidence/'staging/commission.json')
        launch_record=strict_json(read_file(args.evidence/'host/RESULT.json'))
        require(digest(raw)==launch_record['commission_sha256'],'retained packet differs from launch')
        packet=strict_json(raw)
        validate_label(connection,packet)
    argv=['container','exec']+(['--interactive'] if args.operation=='collect' else [])+[meta['container'],
        'env','-i','PATH=/usr/local/bin:/usr/bin:/bin','python3','-I','-B',
        code+'/apparatus/c10/operations.py',args.audit,args.operation]
    if args.confirm is not None:
        require(args.operation=='close' and re.fullmatch(r'[A-Za-z0-9._:-]{1,512}',args.confirm),'confirmation requires close')
        argv+=['--confirm',args.confirm]
    folder=args.evidence/'host/operators'
    folder.mkdir(mode=0o700,exist_ok=True)
    stem=folder/str(time.time_ns())
    write_json(stem.with_suffix('.argv.json'),argv)
    key=(connection_key(connection,rehearsal=launch_record['mode']=='rehearse',record=stem.with_suffix('.connection.json'))
         if connection is not None else hidden_credential() if args.operation=='collect' else None)
    with stem.with_suffix('.stdout').open('xb') as stdout,stem.with_suffix('.stderr').open('xb') as stderr:
        result=subprocess.run(argv,env=host_environment(),input=key,stdout=stdout,stderr=stderr)
    stem.with_suffix('.exit').write_text(str(result.returncode)+'\n')
    if key is not None:
        scan=scan_tree(args.evidence,key)
        write_json(stem.with_suffix('.scan.json'),scan)
        clean=not scan['files_with_matches'] and not scan['errors']
        if earlier is not None:
            scan=scan_tree(earlier['folder'],key)
            write_json(stem.with_suffix('.evidence-scan.json'),scan)
            clean=clean and not scan['files_with_matches'] and not scan['errors']
        key=None
        require(clean,'collection host scan failed; retained output withheld')
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
    p.add_argument('--submission',action='append',nargs=2,metavar=('ID','FOLDER'),
                   help='Study submission template; packet settings replace model/effort/limits/destination, preserving body/materials')
    p.add_argument('--interrupt-after',choices=['reminder_notice'],
                   help='One study submission only: signal its first placement after this witnessed log record; later placements need continuation packets')
    p.add_argument('--max-placements',type=int,
                   help='With --interrupt-after: the ceiling commissioned for the audit, 2-%d'%MAX_PLACEMENTS)
    p=subs.add_parser('propose-continuation',help='Write an unbound, unpaid proposal for the next placement of a retained audit; reads its latest reviewed export and runs nothing')
    p.add_argument('evidence',type=Path,help='Evidence folder of the audit\'s original launch, directly under .scratch')
    p.add_argument('--audit',help='Needed when that launch retained more than one audit')
    p.add_argument('--max-placements',type=int,
                   help='Ceiling commissioned for this audit, 2-%d; defaults to an interrupted study\'s own ceiling'%MAX_PLACEMENTS)
    p.add_argument('--interrupt-after',choices=['reminder_notice'],
                   help='Signal this placement too, after its recorded reminder notice')
    p.add_argument('--stop-after-seconds',type=int,help='Watchdog for this placement; defaults to the retained commission\'s')
    p.add_argument('--output',type=Path,required=True)
    p=subs.add_parser('packet',help='Bind an unpaid proposal to committed apparatus and a qualified or declared study binary; a continuation proposal is bound to its retained audit\'s writer')
    p.add_argument('proposal',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--qualification',required=True)
    p.add_argument('--study-build',type=Path,help='Reviewed unqualified build descriptor; qualification names its base')
    p=subs.add_parser('study-build',help='Bind retained Linux acceptance evidence to declared family guidance; no qualification or spending')
    p.add_argument('interface',type=Path)
    p.add_argument('acceptance',type=Path)
    p.add_argument('expected',type=Path,help='Exact expected case/check and self-test failures after review of the retained run')
    p.add_argument('output',type=Path)
    p.add_argument('--qualification',required=True)
    p=subs.add_parser('continue',help='Start one separately approved later placement of a retained audit in its existing container; never repeats one that started or may have started')
    p.add_argument('mode',choices=['rehearse','live'],help='Must match the audit\'s original launch; rehearse uses only synthetic credentials and fakes')
    p.add_argument('evidence',type=Path,help='Retained evidence folder of the audit\'s original launch; its container publishes there, the host writes nothing to it')
    p.add_argument('record',type=Path,help='New folder directly under .scratch for this placement\'s host records')
    p.add_argument('--packet',type=Path,required=True,help='stewart.c10-continuation/1 packet from propose-continuation and packet')
    p.add_argument('--approved-packet',metavar='SHA256',help='Live: the exact packet digest the principal approved')
    p.add_argument('--rehearsal',type=Path,help='Live: retained Linux rehearsal made by this committed apparatus, with every continuation control passed')
    p.add_argument('--qualification',required=True,help='Qualification whose writer the retained audit already uses')
    p.add_argument('--connection',help='Read the stewart-provider Keychain item; the label must match credential_label and hold the original placement\'s key')
    for mode,text in [('rehearse','Retained Linux rehearsal: every first placement, then each continuation control through `continue`'),
                      ('live','Retained Linux live launch of first placements')]:
        p=subs.add_parser(mode,help=text+'; never resumes or repeats a placement')
        p.set_defaults(mode=mode)
        p.add_argument('evidence',type=Path)
        p.add_argument('--qualification',required=True)
        p.add_argument('--commission',type=Path)
        p.add_argument('--approved-commission')
        p.add_argument('--rehearsal',type=Path)
        p.add_argument('--study-build',type=Path,help='Rehearsal only: explicit unqualified family-guidance build')
        p.add_argument('--connection',help='Read the stewart-provider Keychain item; live label must match credential_label')
        p.add_argument('--submission',action='append',nargs=2,metavar=('ID','FOLDER'),
                       help='Rehearsal only: include these study inputs alongside all conformance controls')
    p=subs.add_parser('review',help='Read all immutable exports without extracting or launching')
    p.add_argument('evidence',type=Path)
    p=subs.add_parser('report',help='Assemble a proposal, checked technical return and optional attributed assessment; read-only')
    p.add_argument('block',type=Path,help='Block manifest with proposal and retained plan hashes')
    p.add_argument('output',type=Path,help='New directory for report.md and matching report.json')
    p.add_argument('--assessment',type=Path,help='Attributed assessment bound to a technical position')
    p=subs.add_parser('control',help='Operate one retained audit; collect needs its original credential')
    p.add_argument('evidence',type=Path,help='Launch folder, or the record folder of the audit\'s latest continuation, whose delivered code reads every placement')
    p.add_argument('audit')
    p.add_argument('operation',choices=['status','close','inspect','collect'])
    p.add_argument('--confirm')
    p.add_argument('--connection',help='Collection only: read the original credential from the named Keychain item')
    p=subs.add_parser('connection',help='Inspect local connection metadata without reading a password')
    actions=p.add_subparsers(dest='connection_action',required=True)
    p=actions.add_parser('status',help='Check presence; this does not test password access or provider authorization')
    p.add_argument('label')
    args=parser.parse_args()
    try:
        if args.command=='list':
            print(json.dumps({'cases':[{k:c[k] for k in ['id','family','variant']} for c in catalog().values()],
                'full_C10':{'fixed_commissions':6,'default_effort_audits':18,'additional_mechanism_audits':3,
                            'total_audits_per_model':21,'spending_authorized':False}},indent=2))
        elif args.command=='propose':
            require(args.output.is_absolute(),'proposal output must be absolute')
            require(not args.submission or args.cases is None and args.repetitions==1,
                    'study submissions cannot select catalog cases or implicit repetitions')
            require((args.interrupt_after is None)==(args.max_placements is None),
                    'an interrupted study needs both --interrupt-after and --max-placements')
            value=(study_proposal(args.model,args.submission) if args.submission
                   else proposal(args.model,args.cases,args.repetitions))
            if args.interrupt_after is not None:
                require(bool(args.submission),'only a study submission can be interrupted at a witnessed point')
                value=validate_packet(interrupted_study(value,args.interrupt_after,args.max_placements))
                print(json.dumps({'allowances':allowance_outlook(value['limits'],dict.fromkeys(LIMITS,0),
                                                                  args.interrupt_after)},indent=2))
            write_json(args.output,value)
            print('Unbound proposal written; no spending authority.')
        elif args.command=='propose-continuation':
            require(args.output.is_absolute(),'proposal output must be absolute')
            value=continuation_proposal(args.evidence,args.audit,max_placements=args.max_placements,
                interruption=args.interrupt_after,stop_after_seconds=args.stop_after_seconds)
            write_json(args.output,value)
            print(json.dumps({'proposal':str(args.output),'audit':value['audit'],'placement':value['placement'],
                'prior':value['prior'],'allowances':allowance_outlook(value['limits'],value['prior']['usage'],
                                                                       args.interrupt_after),
                'approved':False},indent=2))
            print('Unbound continuation proposal written; no spending authority. Nothing ran in the container.')
        elif args.command=='packet':
            value=strict_json(read_file(args.proposal))
            require(args.output.is_absolute(),'packet output must be absolute')
            if isinstance(value,dict) and value.get('schema')=='stewart.c10-continuation/1':
                refuse(args.study_build is None,'a continuation keeps the build its retained audit was launched with')
                value=bind_continuation(value,args.qualification)
            else:
                value=validate_packet(value)
                require(value['spending_authority'] is None and all(v is None for v in value['account'].values()),'bind an unpaid proposal with null account fields')
                if args.study_build:
                    require(value['schema']!='stewart.interruption-commission/1',
                            'an interrupted study uses a qualified binary; no study build')
                    value=study_build.attach(value,strict_json(read_file(args.study_build)))
                value['bindings'],_,_=bindings(args.qualification,value.get('study_build'))
            write_json(args.output,value)
            print(json.dumps({'packet':str(args.output),'sha256':file_hash(args.output),'approved':False},indent=2))
        elif args.command=='study-build':
            require(args.output.is_absolute(),'build descriptor output must be absolute')
            qualification,_=select_qualification(REPO,args.qualification)
            value=study_build.make(REPO,qualification,strict_json(read_file(args.interface)),
                                   args.acceptance,strict_json(read_file(args.expected)))
            write_json(args.output,value)
            print(json.dumps({'study_build':str(args.output),'status':'unqualified','sha256':file_hash(args.output)}))
        elif args.command in ['rehearse','live']:
            return launch_batch(args)
        elif args.command=='continue':
            return continue_placement(args)
        elif args.command=='review':
            report=review_batch(args.evidence)
            print(json.dumps(report,indent=2))
            return any(not r['snapshots'] or (r['snapshots'][-1].get('review') or {}).get('outcome')!='checked' for r in report['audits'])
        elif args.command=='report':
            report=write_report(args.block,args.output,args.assessment)
            issues=current_issues(report)
            print(f"Report: {args.output/'report.md'}; technical position {report['technical_sha256']}; technical gaps: {len(issues)}.")
            return bool(issues)
        elif args.command=='control':
            return host_control(args)
        elif args.command=='connection':
            print(json.dumps(connection_status(args.label),indent=2))
        return 0
    except ReportError as error:
        parser.exit(1,error.code+': report not assembled; inspect selected input paths and hashes. No source records changed.\n')
    except ConnectionError as error:
        parser.exit(1,error.code+': '+str(error)+'\n')
    except Refused as error:
        parser.exit(1,'Refused: '+str(error)+'. Nothing was started in the container and no credential was read.\n')
    except (ValueError,OSError,KeyError,TypeError) as error:
        if args.command in ['live','rehearse','continue','control','review','report']:
            parser.exit(1,'Operation incomplete; inspect retained records. No automatic retry or continuation.\n')
        parser.exit(2,str(error)+'\n')


if __name__=='__main__':
    raise SystemExit(main())
