"""One placement per launch of each planned audit; retained, immutable evidence and exports.

A first placement may carry a witnessed interruption. Later placements of a
retained audit are started one at a time by placements.py.
"""
import argparse
import fcntl
import hashlib
import hmac
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import subprocess
import sys
import tarfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CONTINUED, catalog, credential_bytes, digest, file_hash, inventory, question_file,
    read_file, require, scan_tree, source_hash, strict_json, validate_packet, write_json)
from session import LogPoint, Session, export_evidence_state, failure_details, placement_folder
from control import safe_state
from fake import Auditor
from verify import Evidence, inventory_from_evidence, ordinary_submission, verify
from study import copy_submission, inspect_submission, resolve_submission, supplied_runs


def event(root, kind, **data):
    folder = root / 'events'
    folder.mkdir(exist_ok=True)
    # Exclusive publication also refuses accidental concurrent re-use.
    n = len(list(folder.iterdir())) + 1
    write_json(folder / f'{n:04d}.json', {'kind':kind, 'at':time.time(), **data})


def credential_marker(path, key):
    nonce = os.urandom(32)
    write_json(path, {'nonce':nonce.hex(), 'tag':hmac.digest(key, nonce, 'sha256').hex()})


def check_credential(path, key):
    marker = strict_json(read_file(path))
    require(hmac.compare_digest(marker['tag'], hmac.digest(key, bytes.fromhex(marker['nonce']), 'sha256').hex()),
            'credential differs from the original placement; export withheld')


def rehearsal_script(packet, run):
    """The fake auditor's script for one rehearsal audit."""
    scenario = run['scenario']
    if packet.get('schema') != 'stewart.interruption-commission/1':
        return scenario
    after = packet['interruption']['after']
    if scenario in CONTINUED:
        require(CONTINUED[scenario]['interruption'] == after,
                'rehearsal interruption differs from its control scenario')
        return scenario
    # A supplied study may only name `submitted`, which never reaches a point.
    # Its rehearsal therefore follows the fixed control that does: prose that
    # draws the reminder and a later unprompted submission, or entries first.
    # Both are held controls by choice, so this rehearsal shows the request
    # aborted in flight; the unheld timing is the fixed control's alone.
    # Expectations come from that CONTINUED entry.
    return {'reminder_notice': 'reminder-spent-submits', 'entry_record': 'reminder-unused'}[after]


def first_interruption(packet, run, mode):
    """The witnessed point of a first placement, or None: the packet's, else the control's."""
    if packet.get('schema') == 'stewart.interruption-commission/1':
        return packet['interruption']
    after = CONTINUED.get(run['scenario'], {}).get('interruption') if mode == 'rehearse' else None
    return None if after is None else {'after': after, 'signal': 'SIGTERM'}


def allowance_facts(allowances, interruption=None):
    """What INTERFACE 6.3 and 6.4 determine before a start, as plain numbers.

    A limit is exhausted when no turn remains, the input allowance is used up or
    fewer than 1,024 output tokens remain; a placement started then ends
    `limit_reached` before any request. A request aborted by a signal after any
    byte was written is charged its whole `max_tokens`, the lesser of 16,000 and
    the remaining output allowance. Output reported before the point lowers what
    remains further, so these figures are the most favourable case.
    """
    left = {name: max(0, allowances[name]['limit'] - allowances[name]['used'])
            for name in ['turns', 'input_tokens', 'output_tokens']}
    facts = {'used': {name: allowances[name]['used'] for name in left},
             'limit': {name: allowances[name]['limit'] for name in left}, 'remaining': left,
             'this_placement_ends_limit_reached_before_any_request':
                 left['turns'] == 0 or left['input_tokens'] == 0 or left['output_tokens'] < 1024,
             'planned_interruption': None}
    if interruption is not None:
        estimate = min(16000, left['output_tokens'])
        after = left['output_tokens'] - estimate
        facts['planned_interruption'] = {'point': interruption['after'],
            'output_charge_if_one_request_is_aborted_in_flight': estimate,
            'output_remaining_after_that_charge': after,
            'next_placement_ends_limit_reached_before_any_request': after < 1024,
            'reported_output_before_the_point_that_still_leaves_1024': max(0, after - 1024),
            'also_charged': 'one estimated turn and ceil(request body bytes / 3) input tokens'}
    return facts


def next_snapshot(folder):
    """The next immutable export of one audit; an unknown member refuses."""
    numbers = []
    for path in folder.iterdir():
        match = re.fullmatch(r'export-([0-9]{4})', path.name)
        require(match is not None and path.is_dir(), 'unknown export membership')
        numbers.append(int(match[1]))
    return folder/f'export-{max(numbers, default=0)+1:04d}'


class Audit(Session):
    def __init__(self, binary, root, packet, run, *, mode, local=False, submissions=None):
        self.binary, self.root, self.commission, self.mode = Path(binary), Path(root), packet, mode
        supplied = run.get('submission_folder') is not None
        self.specimen = (inspect_submission(resolve_submission(run, submissions), run['case'], run['submission_sha256'])
                         if supplied else catalog()[run['case']])
        require(not packet.get('study_build') or self.specimen.get('guidance') is None,
                'choose supplied guidance or a study-build override, not both')
        self.run_item, self.local = run, local
        self.phase, self.observer_state, self.witness = 'setup', None, None
        self.index, self.ref, self.process = 0, None, None
        self.root.mkdir(mode=0o700)
        self.folder, self.archive, self.destination, self.evidence = [self.root / name for name in ['submission','archive','returns','evidence']]
        if supplied:
            copy_submission(self.specimen['root'], self.folder, run['submission_sha256'])
        else:
            shutil.copytree(self.specimen['root'], self.folder)
        self.destination.mkdir(mode=0o700)
        self.evidence.mkdir(mode=0o700)
        if supplied:
            copy_submission(self.specimen['root'], self.evidence/'submission-template', run['submission_sha256'])
        (self.root / 'home').mkdir(mode=0o700)
        self.question = self.specimen['question']
        (self.folder / 'question.md').write_bytes(question_file(self.specimen, packet, self.destination))
        self.materials = {p.relative_to(self.folder).as_posix():read_file(p)
                          for p in sorted((self.folder / 'materials').rglob('*')) if p.is_file()}
        shutil.copytree(self.folder, self.evidence / 'input-witness')
        self.env = {'PATH':'/usr/local/bin:/usr/bin:/bin', 'HOME':str(self.root/'home'), 'LANG':'C.UTF-8'}
        if not local:
            for p in [self.root, *self.root.rglob('*')]:
                os.chown(p,1000,1000)
        e = Evidence(self.root)
        inputs = inventory_from_evidence(e, 'evidence/input-witness/')
        write_json(self.evidence / 'specimen.json', {'case':{key:value for key,value in self.specimen.items() if key not in ['root','sha256']},
            'materials':[item for item in inventory(self.specimen['root']) if item['path'] == 'materials' or item['path'].startswith('materials/')]})
        write_json(self.evidence / 'binding.json', {'schema':'stewart.c10-audit/1',
            'commission':packet, 'run':run, 'family':self.specimen['family'], 'mode':mode,
            'binary_sha256':file_hash(binary), 'input_inventory':inputs, 'destination':str(self.destination),
            'input_directories':[item['path'] for item in inventory(self.folder) if item['type']=='directory']})

    @classmethod
    def attach(cls, binary, root, *, mode, stop_after_seconds, local=False):
        """Bind to a retained audit for a later placement; create and rewrite nothing.

        Everything comes from the audit's own retained records, never from the
        catalog or a staged submission, so it also fits a root made by an
        earlier launcher. Command records continue after the highest number used.
        """
        self = cls.__new__(cls)
        self.binary, self.root, self.mode, self.local = Path(binary), Path(root), mode, local
        self.folder, self.archive, self.destination, self.evidence = [self.root / name for name in ['submission','archive','returns','evidence']]
        binding = strict_json(read_file(self.evidence/'binding.json'))
        require(binding['schema'] == 'stewart.c10-audit/1' and binding['mode'] == mode, 'audit binding differs')
        info = strict_json(read_file(self.root/'operator.json'))
        require(info['audit'] == binding['run']['id'] == self.root.name and info['local'] is local,
                'operator binding differs')
        # The audit keeps its commission; only this placement's watchdog is new.
        self.commission = {**binding['commission'], 'stop_after_seconds': stop_after_seconds}
        self.run_item, self.ref = binding['run'], info['reference']
        self.specimen = strict_json(read_file(self.evidence/'specimen.json'))['case']
        witness = self.evidence/'input-witness'
        self.question = read_file(witness/'question.md').split(b'---\n', 2)[2].decode()
        self.materials = {path.relative_to(witness).as_posix():read_file(path)
                          for path in sorted((witness/'materials').rglob('*')) if path.is_file()}
        self.env = {'PATH':'/usr/local/bin:/usr/bin:/bin', 'HOME':info['home'], 'LANG':'C.UTF-8'}
        self.index_after_retained()
        self.phase, self.observer_state, self.witness, self.process = 'attached', None, None, None
        self.before, self.run_attempted = None, False
        return self

    def index_after_retained(self):
        """Number the next command record after every one already retained."""
        used = [int(match[1]) for match in (re.match(r'([0-9]{2,})-', path.name) for path in self.evidence.iterdir()) if match]
        self.index = max(used, default=0)

    def log_folder(self):
        audits = list((self.archive/'audits').iterdir())
        require(len(audits) == 1, 'expected one audit in its archive')
        return audits[0]/'log'

    def spawn(self, argv, **options):
        if self.local:
            # Only smoke.py constructs this test path; the live CLI has no local option.
            require(self.mode == 'rehearse', 'local execution is synthetic only')
            return subprocess.Popen(argv, umask=0o077, **options)
        return super().spawn(argv, **options)

    def intake(self):
        event(self.evidence, 'intake_started')
        new, _, _ = self.command('new', 'new', str(self.folder), '--archive', str(self.archive))
        self.ref = new['data']['reference']
        write_json(self.root/'operator.json', {'binary':str(self.binary), 'reference':self.ref,
            'home':self.env['HOME'], 'local':self.local, 'audit':self.run_item['id']})
        prepared, _, _ = self.command('prepare', 'prepare', self.ref)
        self.command('commission', 'commission', self.ref, prepared['data']['prepared'], '--i-am-finished')
        self.command('receipt-verify', 'receipt', self.ref, '--verify')
        readbacks = []
        expected_inputs = {'question-file':read_file(self.folder/'question.md'),
                           'question-body':self.question.encode(), **self.materials}
        if self.specimen.get('guidance') is not None:
            expected_inputs['guidance-file'] = read_file(self.folder/'guidance.md')
        for n, (item, expected) in enumerate(expected_inputs.items(), 1):
            label = f'readback-{n:04d}'
            raw = self.command(label, 'receipt', self.ref, '--read', item, raw=True)
            require(raw == expected, 'input readback differs from independent witness')
            readbacks.append({'item':item,'command':f'{self.index:02}-{label}', 'sha256':digest(raw)})
        write_json(self.evidence/'readbacks.json', readbacks)
        self.before, _, _ = self.command('status-before', 'status', self.ref)
        event(self.evidence, 'intake_verified')

    def execute(self, key, witness=None):
        return self.place(key, witness, 1, first_interruption(self.commission, self.run_item, self.mode))

    def place(self, key, witness, placement, interruption, intent=None):
        """Start one placement, observe its ending and review the whole audit."""
        self.phase = 'provider-setup'
        # False until the run command is about to be spawned: a failure before
        # then provably started nothing.
        self.run_attempted = False
        folder = placement_folder(self.evidence, placement)
        if placement > 1:
            # Exclusive: a placement's records are made once and never reused.
            folder.mkdir(mode=0o700)
        fake, observe, release, point = None, None, None, None
        scenario = self.run_item['scenario']
        name = self.run_item['id'] if placement == 1 else f"{self.run_item['id']}-p{placement}"
        if self.mode == 'rehearse':
            fake_root = folder/'fake-provider'
            fake_root.mkdir()
            witnessed = witness / name
            witnessed.mkdir(mode=0o700)
            def auth(n, received):
                (witnessed/f'received-{n}.bin').write_bytes(received)
                write_json(witnessed/f'received-{n}.json', {'matches_canary':received==key,
                    'bytes':len(received), 'observed_at':time.time()})
            fake = Auditor(rehearsal_script(self.commission, self.run_item), fake_root, self.materials,
                           self.question, self.specimen['family'], auth, packet=self.commission,
                           guidance=read_file(self.evidence/'input-witness/guidance.md')
                               if self.specimen.get('guidance') else None, placement=placement)
            fake.key = key.decode('ascii')
            if not self.local and placement == 1 and self.run_item['id'] == 'open-ordinary-r1':
                seen, release = threading.Event(), threading.Event()
                original = fake.respond
                def held(body):
                    if fake.requests == 1:
                        seen.set()
                        release.wait(20)
                    return original(body)
                fake.respond = held
                observe = seen, release
            endpoint = f'http://127.0.0.1:{fake.server.server_port}'
            fake.__enter__()
        else:
            endpoint = self.commission['endpoint']
        try:
            write_json(folder/'launch-intent.json', {'reference':self.ref, 'placement':placement,
                'at':time.time(), 'automatic_continuation':False, 'interruption':interruption, **(intent or {})})
            event(self.evidence, 'placement_requested', placement=placement)
            if interruption is not None:
                # Reads the log before the start: only this placement's records can be the point.
                # Only a held control waits for its fake to hold the request; an
                # unheld one, like a live placement, is signalled on sight.
                held = fake is not None and CONTINUED.get(fake.mode, {}).get('held') is True
                point = LogPoint(self.log_folder(), interruption['after'], folder/'interruption',
                                 in_flight=fake.holding if held else None)
            self.run_attempted = True
            reply, rc, timed_out = self.command('run','run',self.ref,key=key,endpoint=endpoint,
                                                observe=observe,interrupt=point)
        finally:
            if release is not None:
                release.set()
            if fake is not None:
                fake.release.set()
                fake.__exit__(None,None,None)
        if fake is not None:
            require(not fake.failures, 'fake exchange failed')
            require(all(strict_json(read_file(p))['matches_canary'] is True for p in witnessed.glob('received-*.json')),
                    'synthetic credential delivery differs')
        lost_reply = scenario == 'lost-run-reply'
        # Controlled loss at the caller boundary: retain original stdout and never re-run.
        if lost_reply:
            reply = None
            event(self.evidence, 'caller_reply_lost', placement_effects='unknown')
        status, _, _ = self.command('status-after-run','status',self.ref)
        event(self.evidence, 'placement_observed', state=safe_state(status), caller_reply_lost=lost_reply)
        write_json(folder/'RESULT.json', {'failure':False, 'caller_reply_lost':lost_reply,
            'exit':rc, 'timed_out':timed_out})
        observation = verify(Evidence(self.root))
        write_json(folder/'review-before-close.json', observation)
        # Only a fully checked auditor submission takes ordinary automatic close.
        closure = None
        if ordinary_submission(observation) and not lost_reply:
            _, close_exit, close_timeout = self.command('close','close',self.ref)
            final, status_exit, status_timeout = self.command('status-final','status',self.ref)
            closure = {'close_exit':close_exit, 'status_exit':status_exit,
                       'timed_out':close_timeout or status_timeout, 'state':safe_state(final)}
        if scenario == 'export-contamination':
            (self.root/'deliberately-contaminated-control').write_bytes(key)
        return {'audit':self.run_item['id'], 'placement':'observed', 'run':placement,
                'exit':rc, 'timed_out':timed_out, 'caller_reply_lost':lost_reply,
                'interruption':point.summary() if point is not None else None,
                'review_before_close':observation, 'automatic_close':closure,
                'fake_requests':fake.requests if fake else None}


def export_snapshot(root, destination, key, *, force_failure=False):
    """One immutable snapshot; caller holds the audit operator lock and checked current status."""
    destination.mkdir(mode=0o700)
    state = export_evidence_state(root)
    scan = scan_tree(root,key)
    result = {'schema':'stewart.c10-export/2', 'started_at':time.time(), 'outcome':'withheld',
        'evidence_state':state, 'scan':scan, 'archive':None, 'reasons':[]}
    if state != 'complete':
        result['reasons'].append('evidence_incomplete')
    if scan['files_with_matches']:
        result['reasons'].append('credential_match')
    if scan['errors']:
        result['reasons'].append('scan_incomplete')
    if state == 'complete' and not scan['files_with_matches'] and not scan['errors']:
        target = destination/'work.tar'
        try:
            if force_failure:
                target.mkdir()
            with target.open('xb') as stream:
                # Copy regular bytes of hard-linked publication records. Originals remain in Linux.
                with tarfile.open(fileobj=stream, mode='w', dereference=True) as archive:
                    archive.add(root, arcname='private', recursive=True)
            result.update(outcome='exported', archive={'bytes':target.stat().st_size,'sha256':file_hash(target)})
        except OSError:
            result['outcome'] = 'failed'
            result['reasons'].append('archive_write_failed')
    result['ended_at'] = time.time()
    write_json(destination/'EXPORT.json',result)
    return result


def locked_export(audit, out, key, *, force_failure=False):
    with (audit.root.parent/(audit.root.name+'.operator.lock')).open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        status, _, _ = audit.command('status-export','status',audit.ref)
        require(status['data']['runs']['held'] is False, 'active or unobserved writer; export withheld')
        return export_snapshot(audit.root,out,key,force_failure=force_failure)


def stop_reason(observed, export):
    """Conservative placement policy; assessment never participates."""
    review = observed['review_before_close']
    closure = observed['automatic_close']
    if closure is not None and (closure['close_exit'] != 0 or closure['status_exit'] != 0
            or closure['timed_out'] or closure['state']['closed'] is not True):
        return 'custody_observation_incomplete'
    if review['outcome'] != 'checked':
        return 'review_incomplete'
    if export['outcome'] != 'exported':
        return 'export_' + export['outcome']
    if observed['caller_reply_lost']:
        return 'caller_reply_lost'
    if not ordinary_submission(review):
        return 'without_auditor_submission'
    return None


def continued_match(observed, export, script, placement):
    """A fixed continued control against its CONTINUED entry, one placement at a time."""
    review, witness = observed['review_before_close'], observed['interruption']
    ending, cause = CONTINUED[script]['endings'][placement-1]
    point = CONTINUED[script]['interruption'] if placement == 1 else None
    return (review['outcome'] == 'checked' and len(review['placements']) == placement
            and [review['ending'], review['cause']] == [ending, cause]
            and (ordinary_submission(review) if ending == 'sealed' else review['auditor_submitted'] is False)
            and (witness is None if point is None else witness is not None
                 and witness['after'] == point and witness['state'] == 'signalled'
                 and witness['termination'] is not None and witness['termination']['timed_out'] is False
                 and review['placements'][-1]['interruption']['followed_by_signal_ending'] is True)
            and export['outcome'] == 'exported' and observed['caller_reply_lost'] is False
            and observed['timed_out'] is False
            and stop_reason(observed, export) != 'custody_observation_incomplete')


def rehearsal_match(observed, export, scenario):
    if scenario in CONTINUED:
        return continued_match(observed, export, scenario, 1)
    expected_export = {'reflected-body':'withheld','export-contamination':'withheld',
                       'export-failure':'failed'}.get(scenario,'exported')
    review = observed['review_before_close']
    if scenario == 'reflected-body':
        expected_review = review['outcome'] == 'incomplete'
    elif scenario in ['unsubmitted','provider-rejected']:
        expected_review = review['outcome'] == 'checked' and review['auditor_submitted'] is False
    else:
        expected_review = ordinary_submission(review)
    return (expected_review and export['outcome'] == expected_export
            and observed['caller_reply_lost'] is (scenario == 'lost-run-reply')
            and stop_reason(observed, export) != 'custody_observation_incomplete')


def execute_batch(binary, private, out, packet, mode, key, sessions, witness, *, local=False):
    rows, halt = [], None
    for audit in sessions:
        item = audit.run_item
        if halt is not None:
            event(audit.evidence,'not_started',reason=halt['reason'])
            rows.append({'audit':item['id'],'placement':'not_started','export':None})
            continue
        observed = None
        try:
            observed = audit.execute(key,witness)
            target = out/item['id']/'export-0001'
            target.parent.mkdir(mode=0o700)
            export = locked_export(audit,target,key,force_failure=item['scenario']=='export-failure')
            reason = stop_reason(observed, export)
            row = {**observed,'export':export}
            if mode == 'rehearse':
                row['expected_observation'] = rehearsal_match(observed,export,rehearsal_script(packet,item))
                row['failed'] = not row['expected_observation']
                reason = 'rehearsal_expectation_mismatch' if row['failed'] else None
            else:
                row['failed'] = reason not in [None,'without_auditor_submission','caller_reply_lost']
            rows.append(row)
            if reason is not None:
                halt = {'audit':item['id'],'reason':reason}
        except Exception as error:
            detail = failure_details(error,audit.phase,item['id'])
            detail['stage'] = 'export' if observed is not None else 'placement'
            write_json(audit.evidence/'failure.json',detail)
            row = observed if observed is not None else {'audit':item['id'],'placement':'unknown'}
            rows.append({**row,'failure':detail,'export':None,'failed':True})
            halt = {'audit':item['id'],'reason':'operation_failed'}
    failed = sum(r.get('failed') is True for r in rows)
    # Those controls need the fixed rehearsal inventory; a rehearsal of one
    # interrupted study says so here and therefore admits no live launch.
    lone_study = mode == 'rehearse' and packet.get('schema') == 'stewart.interruption-commission/1'
    report = {'schema':'stewart.c10-session/2', 'mode':mode, 'local_iteration_only':local,
        'outcome':('incomplete' if failed else 'observed') if mode=='live' else ('failed' if halt else 'passed'),
        'planned':len(sessions), 'observed':sum(r['placement']=='observed' for r in rows),
        'failed':failed, 'halt':halt,
        'not_started':sum(r['placement']=='not_started' for r in rows), 'audits':rows,
        'model_calls':0 if mode=='rehearse' else None, 'model_qualified':False,
        'skipped_checks':(['Linux process-access controls (native iteration)'] if local else [])
            + (['fixed-inventory reviewer, operator and report controls (one interrupted study)'] if lone_study else []),
        'environment':{'system':platform.system(),'machine':platform.machine(),'kernel':platform.release(),
                       'uid':os.getuid()}}
    write_json(out/'RESULT.json',report)
    return report


def prepare_batch(binary, private, out, packet, mode, *, local=False, submissions=None):
    private.mkdir(mode=0o755)
    private.chmod(0o755)
    out.mkdir(mode=0o700,exist_ok=True)
    write_json(out/'PLAN.json', {'schema':'stewart.c10-plan/1','commission':packet,
        'binary_sha256':file_hash(binary), 'audits':[r['id'] for r in packet['runs']]})
    sessions, planned = [], []
    for run in packet['runs']:
        audit = Audit(binary,private/run['id'],packet,run,mode=mode,local=local,submissions=submissions)
        sessions.append(audit)
        audit.intake()
        interruption = first_interruption(packet,run,mode)
        if interruption is not None:
            # A plain fact for whoever commissions the next placement; never a refusal.
            facts = allowance_facts(audit.before['data']['allowances'],interruption)
            write_json(audit.evidence/'interruption-preflight.json',facts)
            planned.append({'audit':run['id'], **facts})
    if planned:
        write_json(out/'INTERRUPTION-PREFLIGHT.json',{'schema':'stewart.c10-interruption-preflight/1',
            'basis':'INTERFACE 6.3 and 6.4 applied to status before any placement','audits':planned})
    return sessions


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['rehearse','live'])
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--private',type=Path,default=Path('/work/c10-private'))
    parser.add_argument('--out',type=Path,default=Path('/out'))
    parser.add_argument('--submissions',type=Path)
    args=parser.parse_args()
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    require(sys.platform=='linux' and os.geteuid()==0,'container administrator required')
    packet=validate_packet(strict_json(read_file(args.packet)),rehearsal=args.mode=='rehearse',approved=args.mode=='live')
    require(file_hash(args.binary)==packet['bindings']['binary_sha256'],'binary binding changed')
    require(source_hash()==packet['bindings']['apparatus_sha256'],'container apparatus source differs from packet')
    try:
        sessions=prepare_batch(args.binary,args.private,args.out,packet,args.mode,submissions=args.submissions)
        filesystem=subprocess.run(['stat','-f','-c','%T',str(sessions[0].archive)],
            capture_output=True,check=False)
        write_json(args.out/'ENVIRONMENT.json',{'system':platform.system(),'kernel':platform.release(),
            'machine':platform.machine(),'python':platform.python_version(),'uid':os.getuid(),
            'archive_filesystem_observation':{'argv':filesystem.args,'exit':filesystem.returncode,
                'stdout':filesystem.stdout.decode('utf-8','replace'),'stderr':filesystem.stderr.decode('utf-8','replace')}})
        require(filesystem.returncode==0,'archive filesystem observation failed')
        write_json(args.out/'READY.json',{'credential_free_intake_verified':True,'audits':[s.run_item['id'] for s in sessions]})
        key=credential_bytes(sys.stdin.buffer.read(4098))
        checks=Path('/work/credential-check')
        checks.mkdir(mode=0o700)
        for audit in sessions:
            credential_marker(checks/(audit.root.name+'.json'),key)
        witness=Path('/work/c10-credential-witness') if args.mode=='rehearse' else None
        if witness is not None:
            witness.mkdir(mode=0o700)
            (witness/'canary.bin').write_bytes(key)
        report=execute_batch(args.binary,args.private,args.out,packet,args.mode,key,sessions,witness)
        if args.mode=='rehearse' and report['failed']==report['not_started']==0 and not report['skipped_checks']:
            from check_operations import exercise as exercise_operations
            operator_root=args.private.parent/'c10-operator-controls'
            operator_controls=exercise_operations(args.private.parent,private=args.private,out=args.out,
                target=operator_root,key=key,local=False)
            scan=scan_tree(operator_root,key)
            require(not scan['files_with_matches'] and not scan['errors'],'operator-control export scan failed')
            shutil.copytree(operator_root,args.out/'operator-controls')
            require(operator_controls['failed']==0,'operator controls failed')
            from check_review import exercise
            controls_root=args.private.parent/'c10-review-controls'
            controls=exercise(sessions[0].root,controls_root)
            scan=scan_tree(controls_root,key)
            require(not scan['files_with_matches'] and not scan['errors'],'review-control export scan failed')
            shutil.copytree(controls_root,args.out/'review-controls')
            require(controls['failed']==0,'reviewer controls failed')
            if supplied_runs(packet):
                study_controls=args.private.parent/'c10-study-review-controls'
                study_controls.mkdir(mode=0o700)
                for audit in sessions:
                    if audit.run_item.get('submission_folder') is not None:
                        result=exercise(audit.root,study_controls/audit.run_item['id'])
                        require(result['failed']==0,'study reviewer controls failed')
                scan=scan_tree(study_controls,key)
                require(not scan['files_with_matches'] and not scan['errors'],'study-review export scan failed')
                shutil.copytree(study_controls,args.out/'study-review-controls')
            from check_reporting import exercise as exercise_reporting
            reporting_root=args.private.parent/'c10-report-controls'
            reporting=exercise_reporting(args.out,reporting_root)
            scan=scan_tree(reporting_root,key)
            require(not scan['files_with_matches'] and not scan['errors'],'report-control export scan failed')
            shutil.copytree(reporting_root,args.out/'report-controls')
            require(reporting['failed']==0,'report controls failed')
        del key
        write_json(args.out/'RESOURCES.json',{'self_maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'children_maxrss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
            'scope':'Linux process high-water RSS, not simultaneous container memory or full C10 scale qualification'})
        return report['failed'] > 0 or args.mode == 'rehearse' and report['not_started'] > 0
    except Exception as error:
        # Never expose raw exceptions: they may contain credential-bearing evidence.
        write_json(args.out/'FAILURE.json',failure_details(error,'batch'))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
