"""Serial host dispatch for a delegated campaign; never a shell or a retry loop.

The operator starts this outside the agent sandbox. Requests select existing C10
operations. Each accepted request has an exclusive claim before execution, and
is never dispatched again. See HOST-QUEUE.md for authority and crash recovery.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import grp
import pwd
import re
import stat
import tempfile
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (REPO, HERE, SOURCE_PATHS, LIMITS, CONTINUED, compact, rehearsal_packet, tree_hash, digest, fields, identifier, read_file,
                    require, source_hash, strict_json, validate_continuation, validate_packet,
                    write_json)
from connections import validate_label
from launch import host_environment, select_qualification


def configuration(value, live):
    fields(value, ['campaign', 'authority', 'model', 'account', 'qualification',
                  'schema', 'synthetic_connection', 'placement_ceiling', 'budget_usd', 'console', 'envelope'], 'host configuration')
    require(value['schema'] == 'stewart.c10-campaign/2', 'unsupported campaign configuration')
    envelope = value['envelope']
    fields(envelope, ['cases', 'submissions', 'efforts', 'limits', 'max_placements', 'watchdog_seconds',
                      'study_build_sha256', 'pricing'], 'authorized campaign envelope')
    require(isinstance(envelope['cases'], list) and all(identifier(n) for n in envelope['cases']),
            'invalid campaign case identifiers')
    require(isinstance(envelope['submissions'], dict)
            and all(identifier(k) and isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v)
                    for k,v in envelope['submissions'].items()), 'invalid approved submission manifest')
    require(isinstance(envelope['efforts'],list) and envelope['efforts']
            and all(e in [None,'low','medium','high','xhigh','max'] for e in envelope['efforts']),
            'invalid campaign effort choices')
    fields(envelope['limits'], LIMITS, 'maximum per-audit limits')
    require(all(type(n) is int and n > 0 for n in [*envelope['limits'].values(),
            envelope['max_placements'],envelope['watchdog_seconds']]), 'invalid campaign bounds')
    build = envelope['study_build_sha256']
    require(build is None or isinstance(build,str) and re.fullmatch('[0-9a-f]{64}',build),
            'invalid reviewed study build digest')
    pricing=envelope['pricing']
    fields(pricing, ['input_cents_per_million','output_cents_per_million',
                     'max_input_per_attempt','max_output_per_attempt'], 'campaign pricing')
    require(all(type(n) is int and n > 0 for n in pricing.values()), 'positive integer billing bounds required')
    for key in ['campaign', 'authority', 'model', 'qualification']:
        require(isinstance(value[key], str) and value[key].strip(), 'empty host configuration field')
    require(identifier(value['campaign']), 'invalid campaign identifier')
    require(type(value['placement_ceiling']) is int and value['placement_ceiling'] > 0,
            'positive campaign placement ceiling required')
    require(type(value['budget_usd']) in [int, float] and value['budget_usd'] > 0,
            'positive campaign budget required')
    validate_label(value['synthetic_connection'])
    fields(value['account'], ['account_label', 'workspace_id', 'credential_label'], 'account')
    validate_label(value['account']['credential_label'])
    if live:
        require(all(isinstance(v, str) and v.strip() for v in value['account'].values()),
                'record the actual campaign account before live enabling')
        console = value['console']
        require(isinstance(console, dict), 'record the configured Console limit before live enabling')
        fields(console, ['scope', 'month', 'limit_usd', 'starting_spend_usd', 'recorded_by',
                         'recorded_at', 'credential_binding'], 'Console observation')
        require(all(isinstance(console[k], str) and console[k].strip() for k in
                    ['scope', 'month', 'recorded_by', 'recorded_at', 'credential_binding']),
                'Console metadata is incomplete')
        require(all(type(console[k]) in [int, float] and console[k] >= 0
                    for k in ['limit_usd', 'starting_spend_usd'])
                and console['limit_usd'] > console['starting_spend_usd'],
                'Console limit needs positive remaining headroom')
        cents(console['starting_spend_usd'])
        cents(console['limit_usd'])
        require(console['month'] == datetime.now(timezone.utc).strftime('%Y-%m'),
                'refresh the Console observation for this billing month; campaign allowance does not renew')
    cents(value['budget_usd'])
    return value


def evidence_path(value):
    path = Path(value)
    require(path.is_absolute() and path.parent == REPO / '.scratch'
            and identifier(path.name) and not path.is_symlink(), 'use evidence directly under .scratch')
    return path


def cents(amount):
    value = Decimal(str(amount)) * 100
    require(value.is_finite() and value >= 0 and value == value.to_integral_value(), 'use whole cents for dollar amounts')
    return int(value)


def reservation(config, slots):
    # INTERFACE 6.4 checks usage after a reply. Price every possible attempt,
    # including retries and the last request that can exceed the input allowance.
    envelope = config['envelope']
    price = envelope['pricing']
    per_attempt = (price['input_cents_per_million'] * price['max_input_per_attempt']
                   + price['output_cents_per_million'] * price['max_output_per_attempt'])
    numerator = slots * envelope['limits']['turns'] * 4 * per_attempt
    return (numerator + 999999) // 1000000


def check_envelope(packet, config, submissions):
    envelope = config['envelope']
    require(all(packet['limits'][key] <= envelope['limits'][key] for key in LIMITS)
            and packet['max_placements'] <= envelope['max_placements']
            and packet['stop_after_seconds'] <= envelope['watchdog_seconds'],
            'packet exceeds commissioned limits')
    if 'runs' in packet:
        require(packet['effort'] in envelope['efforts'], 'effort outside commission')
        if packet.get('study_build') is not None:
            require(digest(compact(packet['study_build'])) == envelope['study_build_sha256'],
                    'writer outside reviewed campaign builds')
            protected(Path(packet['study_build']['acceptance_folder'])/'bin-arm64/stewart')
        for run in packet['runs']:
            if run.get('submission_folder') is None:
                require(run['case'] in envelope['cases'], 'case outside commission')
            else:
                require(submissions is not None and run['submission_folder'] == str(submissions / run['case'])
                        and envelope['submissions'].get(run['case']) == run['submission_sha256'],
                        'submission outside commission')


def command(request, config, live, submissions=None):
    """Return argv and a conservative placement charge. No effects or key lookup."""
    require(isinstance(request, dict), 'request must be an object')
    kind = request.get('operation')
    base = [sys.executable, '-I', '-B', str(HERE / 'c10.py')]
    if kind == 'rehearse':
        fields(request, ['operation', 'evidence', 'submissions'], 'rehearsal request')
        out = evidence_path(request['evidence'])
        require(not out.exists(), 'rehearsal evidence already exists')
        argv = base + ['rehearse', str(out), '--qualification', config['qualification'],
                       '--connection', config['synthetic_connection']]
        require(isinstance(request['submissions'], list), 'submissions must be a list')
        for name, folder in request['submissions']:
            require(identifier(name) and submissions is not None and folder == str(submissions / name)
                    and name in config['envelope']['submissions'], 'invalid rehearsal submission')
            require(tree_hash(Path(folder)) == config['envelope']['submissions'][name], 'rehearsal submission changed')
            argv += ['--submission', name, folder]
        if config['model'] == 'rehearsal-only':
            fixed = rehearsal_packet()
            check_envelope(fixed, config, submissions)
            slots = len(fixed['runs']) + len(CONTINUED) + len(request['submissions'])
            return argv, slots
        return argv, 0
    if kind == 'live':
        fields(request, ['operation', 'evidence', 'packet', 'sha256', 'rehearsal'], 'live request')
        require(live, 'this host session is offline; restart with --live after enabling')
        configuration(config, True)
        out = evidence_path(request['evidence'])
        require(not out.exists(), 'live evidence already exists; reconcile it, never repeat it')
        raw = read_file(Path(request['packet']))
        require(digest(raw) == request['sha256'], 'packet digest differs')
        packet = validate_packet(strict_json(raw), approved=True)
        require(packet['model'] == config['model'] and packet['account'] == config['account']
                and packet['spending_authority'] == config['authority']
                and packet['bindings']['qualification_id'] == config['qualification'],
                'packet exceeds or differs from this campaign')
        check_envelope(packet,config,submissions)
        require(len(packet['runs']) == 1, 'dispatch one audit, then review before selecting another')
        return base + ['live', str(out), '--qualification', config['qualification'],
            '--commission', request['packet'], '--approved-commission', request['sha256'],
            '--rehearsal', str(evidence_path(request['rehearsal'])),
            '--connection', config['account']['credential_label']], 1
    if kind == 'continue':
        # One later placement of a retained audit. The launcher repeats every
        # check below and adds the retained-record, prior-state and writer checks.
        fields(request, ['operation', 'evidence', 'record', 'packet', 'sha256', 'rehearsal'],
               'continuation request')
        require(live, 'this host session is offline; restart with --live after enabling')
        configuration(config, True)
        evidence = evidence_path(request['evidence'])
        require(evidence.is_dir(), 'retained evidence of the original launch is missing')
        record = evidence_path(request['record'])
        require(not record.exists(), 'continuation record already exists; reconcile it, never repeat it')
        raw = read_file(Path(request['packet']))
        require(digest(raw) == request['sha256'], 'packet digest differs')
        packet = validate_continuation(strict_json(raw), approved=True)
        require(packet['model'] == config['model'] and packet['account'] == config['account']
                and packet['spending_authority'] == config['authority']
                and packet['bindings']['qualification_id'] == config['qualification'],
                'packet exceeds or differs from this campaign')
        check_envelope(packet,config,submissions)
        require(packet['evidence'] == str(evidence), 'packet continues an audit in another evidence folder')
        return base + ['continue', 'live', str(evidence), str(record),
            '--qualification', config['qualification'], '--packet', request['packet'],
            '--approved-packet', request['sha256'],
            '--rehearsal', str(evidence_path(request['rehearsal'])),
            '--connection', config['account']['credential_label']], 1
    require(kind in ['status', 'inspect', 'close', 'collect'], 'unsupported operation')
    fields(request, ['operation', 'evidence', 'audit', 'confirm'], 'operator request')
    out = evidence_path(request['evidence'])
    require(identifier(request['audit']), 'invalid audit identifier')
    packet = strict_json(read_file(out / 'staging/commission.json'))
    is_fake = packet['model'] == 'rehearsal-only'
    require(is_fake or packet['model'] == config['model']
            and packet['account'] == config['account']
            and packet['spending_authority'] == config['authority'],
            'operator target is outside this campaign')
    argv = base + ['control', str(out), request['audit'], kind]
    if request['confirm'] is not None:
        require(kind == 'close' and isinstance(request['confirm'], str)
                and not request['confirm'].startswith('-'), 'confirmation is only for ordinary close')
        argv += ['--confirm', request['confirm']]
    if kind == 'collect':
        argv += ['--connection', config['synthetic_connection'] if is_fake
                 else config['account']['credential_label']]
    return argv, 0


def dispatch(queue, name, request_raw, argv, charge, config_hash, reserved_cents):
    """A crash anywhere after mkdir leaves a claim, never an implicit retry."""
    claim = queue / 'claims' / name
    claim.mkdir(mode=0o700)
    (claim / 'request.json').write_bytes(request_raw)
    write_json(claim / 'command.json', {'argv': argv, 'placement_charge': charge,
                                      'reserved_cents': reserved_cents, 'configuration_sha256': config_hash, 'started_at': time.time()})
    for path in [claim / 'request.json', claim / 'command.json', claim, claim.parent]:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    with (claim / 'stdout').open('xb') as out, (claim / 'stderr').open('xb') as err:
        result = subprocess.run(argv, cwd=REPO, env=host_environment(), stdin=subprocess.DEVNULL,
                                stdout=out, stderr=err)
    write_json(claim / 'result.json', {'exit': result.returncode, 'ended_at': time.time()})
    return result.returncode


def reconciled(claim):
    result = claim / 'result.json'
    try:
        if strict_json(read_file(result)).get('exit') == 0:
            return True
    except (OSError, ValueError):
        pass  # A torn result can be reconciled without rewriting it.
    record = claim / 'reconciliation.json'
    if not record.exists():
        return False
    value = strict_json(read_file(record))
    fields(value, ['author', 'disposition', 'evidence'], 'claim reconciliation')
    require(all(isinstance(value[k], str) and value[k].strip() for k in ['author', 'disposition'])
            and isinstance(value['evidence'], list) and value['evidence'], 'reconciliation needs an attributed disposition and evidence')
    for ref in value['evidence']:
        fields(ref, ['path', 'sha256'], 'reconciliation evidence')
        require(digest(read_file(Path(ref['path']))) == ref['sha256'], 'reconciliation evidence differs')
    return True


def charges(claim, config):
    try:
        row = strict_json(read_file(claim / 'command.json'))
        slots, money = row['placement_charge'], row['reserved_cents']
        require(all(type(n) is int and n >= 0 for n in (slots,money)), 'invalid claim reservation')
        return slots, money
    except (OSError, ValueError, KeyError, TypeError):
        # Losing the metadata loses the admissible upper bound. Hold the
        # entire envelope. Custody-only operations may still proceed.
        return config['placement_ceiling'], cents(config['budget_usd'])


def snapshot_packet(request, queue, session, name):
    if request.get('operation') not in ['live', 'continue']:
        return request
    path = Path(request['packet'])
    require(path.parent == queue / 'packets' and path.suffix == '.json' and identifier(path.stem),
            'packets must be regular named JSON files directly in queue/packets')
    # The parent is launcher-owned. read_file opens its single untrusted leaf
    # O_NOFOLLOW, nonblocking, bounded and regular. Use these bytes throughout.
    raw = read_file(path, 1 << 20)
    snapshot = session / (name + '.packet.json')
    with snapshot.open('xb') as stream:
        stream.write(raw)
    return {**request, 'packet': str(snapshot)}


def publish_exports(results, evidence, audits):
    published = []
    for audit in audits:
        require(identifier(audit), 'invalid published audit')
        for snapshot in sorted((evidence/'container'/audit).glob('export-*')):
            require(re.fullmatch('export-[0-9]{4,}', snapshot.name) and not snapshot.is_symlink(),
                    'unexpected snapshot directory')
            receipt = strict_json(read_file(snapshot/'EXPORT.json'))
            if receipt['outcome'] != 'exported':
                continue
            require(receipt['schema']=='stewart.c10-export/2' and receipt['evidence_state']=='complete'
                    and not receipt['scan']['files_with_matches'] and not receipt['scan']['errors'],
                    'export lacks a completed clean credential scan')
            expected = receipt['archive']
            require(re.fullmatch('[0-9a-f]{64}',expected['sha256']), 'invalid export hash')
            filename = expected['sha256'] + '.tar'
            if not (results/filename).exists():
                # A partial copy stays launcher-private. Verify bytes before publication.
                with tempfile.NamedTemporaryFile(dir=results) as temp:
                    checksum = hashlib.sha256()
                    with os.fdopen(os.open(snapshot/'work.tar', os.O_RDONLY|os.O_NOFOLLOW), 'rb') as stream:
                        for chunk in iter(lambda:stream.read(1<<20), b''):
                            temp.write(chunk)
                            checksum.update(chunk)
                    require(temp.tell()==expected['bytes'] and checksum.hexdigest()==expected['sha256'],
                            'export differs from its receipt')
                    temp.flush()
                    os.fsync(temp.fileno())
                    os.fchmod(temp.fileno(),0o640)
                    os.link(temp.name, results/filename)
            published.append({'audit':audit,'snapshot':snapshot.name,'file':filename,**expected})
    return published


def result_summary(queue, name, request, code, charge, reserved, *, reason=None):
    value = {'schema':'stewart.c10-dispatch-result/1', 'operation':request['operation'],
             'exit':code, 'placement_charge':charge, 'reserved_cents':reserved}
    if reason is not None:
        value['reason'] = reason
    claim = queue/'claims'/name
    if code == 0 and request['operation'] in ['inspect','status','close','collect']:
        # operations.py emits its scoped operator summary, including the
        # ordinary close confirmation when needed. Raw child streams stay private.
        value['operator'] = strict_json(read_file(claim/'stdout'))
    if code == 0 and request['operation'] in ['rehearse','live','continue','collect']:
        record = evidence_path(request.get('record',request['evidence']))
        operator = strict_json(read_file(record/'host/operator.json'))
        require(operator['schema']=='stewart.c10-operator/1','unsupported publication record')
        evidence = evidence_path(operator.get('evidence',request['evidence']))
        audits = [request['audit']] if request['operation']=='collect' else operator['audits']
        value['exports'] = publish_exports(queue/'results', evidence, audits)
        if request['operation'] in ['live','rehearse','continue']:
            value['outcome'] = strict_json(read_file(record/'host/RESULT.json'))['outcome']
    # Publish exclusively through an atomic rename in the launcher-owned
    # setgid result directory. Readers see either a complete result or none.
    with tempfile.NamedTemporaryFile(dir=queue/'results', delete=False) as stream:
        stream.write(compact(value) + b'\n')
        os.fchmod(stream.fileno(), 0o640)
        os.fsync(stream.fileno())
    os.replace(stream.name, queue/'results'/(name+'.json'))


def owned_evidence(queue, path):
    for claim in (queue/'claims').iterdir():
        try:
            request = strict_json(read_file(claim/'request.json'))
            # A claim is recorded before spawn so an interrupted launch's
            # partial evidence remains available for custody operations.
            if ((request['operation'] in ['live','rehearse'] and request['evidence'] == path)
                    or (request['operation'] == 'continue' and request['record'] == path)):
                return True
        except (KeyError,OSError,ValueError,TypeError):
            continue
    return False


def serve(queue, config_path, live, once=False):
    raw = read_file(config_path)
    config = configuration(strict_json(raw), live)
    config_hash = digest(raw)
    queue.mkdir(mode=0o700, exist_ok=True)
    for name in ['requests', 'packets', 'results', 'submissions', 'claims', 'sessions']:
        (queue / name).mkdir(mode=0o700, exist_ok=True)
    with (queue / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        identity = queue / 'campaign.json'
        scope = {k: config[k] for k in ['schema', 'campaign', 'authority', 'model', 'account', 'qualification', 'envelope', 'placement_ceiling', 'budget_usd']}
        if identity.exists():
            require(strict_json(read_file(identity)) == scope, 'queue belongs to another campaign or ceiling')
        else:
            write_json(identity, scope)
        require(not subprocess.check_output(['git', 'status', '--porcelain', '--', *SOURCE_PATHS],
                                            cwd=REPO, env=host_environment()), 'commit apparatus before starting host dispatch')
        source = source_hash()
        session = queue / 'sessions' / str(time.time_ns())
        session.mkdir(mode=0o700)
        (session / 'configuration.json').write_bytes(raw)
        write_json(session / 'start.json', {'live_enabled': live, 'source_sha256': source,
                                           'pid': os.getpid(), 'started_at': time.time()})
        print('Host queue ready: ' + str(queue) + (' (live enabled)' if live else ' (offline)'), flush=True)
        while not (queue / 'STOP').exists():
            require(source_hash() == source, 'apparatus changed; stop and start a reviewed host session')
            for path in sorted((queue / 'requests').glob('*.json')):
                name = path.stem
                if not identifier(name):
                    continue
                if (queue / 'claims' / name).exists() or (queue / 'results' / (name + '.json')).exists():
                    continue
                # A request is published by atomic rename after writing it fully.
                try:
                    request_raw = read_file(path, 1 << 20)
                    original = strict_json(request_raw)
                    request = snapshot_packet(original, queue, session, name)
                    argv, charge = command(request, config, live, queue/'submissions')
                    if request['operation'] in ['status','inspect','close','collect','continue']:
                        require(owned_evidence(queue,request['evidence']), 'target was not launched by this campaign')
                    claims = list((queue / 'claims').iterdir())
                    reserved = reservation(config, charge)
                    if charge:
                        require(all(reconciled(p) for p in claims), 'unfinished host claim: reconcile effects before placements')
                        ledger = [charges(p,config) for p in claims]
                        require(sum(slots for slots,_ in ledger) + charge <= config['placement_ceiling'],
                                'campaign placement ceiling reached')
                        remaining = cents(config['budget_usd'])
                        if live:
                            console=config['console']
                            remaining=min(remaining,cents(console['limit_usd'])-cents(console['starting_spend_usd']))
                        require(sum(cost for _,cost in ledger) + reserved <= remaining,
                                'campaign budget or Console headroom exhausted')
                except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
                    # Outward reasons contain no request-supplied strings, stream
                    # fragments or launcher paths. Refusals reserve nothing.
                    known = ['campaign placement ceiling reached','campaign budget or Console headroom exhausted',
                             'unfinished host claim: reconcile effects before placements']
                    reason = str(error) if type(error) is ValueError and str(error) in known else 'request outside campaign or invalid'
                    result_summary(queue,name,{'operation':'refused'},1,0,0,reason=reason)
                    print(name + ': ' + reason, file=sys.stderr, flush=True)
                    if once:
                        return 1
                    continue
                code = dispatch(queue, name, request_raw, argv, charge, config_hash, reserved)
                result_summary(queue, name, request, code, charge, reserved)
                print(name + ': exit=' + str(code) + '; inspect retained claim and C10 records', flush=True)
                # One request per poll lets the agent review before publishing more.
                # A failed subprocess does not authorize repetition or a replacement.
                if code or once:
                    return code
                break
            else:
                if once:
                    return 0
            time.sleep(1)
    return 0


def protected(path):
    for item in [path, *path.parents]:
        info = item.lstat()
        require(info.st_uid in [0,os.getuid()] and not (info.st_mode & 0o022)
                and not stat.S_ISLNK(info.st_mode), 'launcher input or ancestor is writable by another account')


def deployment(queue, config):
    require(os.getuid() != 0 and pwd.getpwuid(os.getuid()).pw_name=='stewart-launch',
            'start the queue in the unprivileged stewart-launch login')
    gid = grp.getgrnam('stewart-queue').gr_gid
    for path in [queue,config,REPO,REPO/'.scratch']:
        protected(path)
    campaign = strict_json(read_file(config))
    _, binaries = select_qualification(REPO,campaign['qualification'])
    protected(binaries/'stewart')
    for name,mode in [('requests',0o3770),('packets',0o3770),('results',0o2750),
                      ('submissions',0o700),('claims',0o700),('sessions',0o700)]:
        info = (queue/name).lstat()
        permissions = stat.S_IMODE(info.st_mode)
        if mode==0o700:
            permissions &= ~stat.S_ISGID
        require(stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and permissions==mode
                and (mode==0o700 or info.st_gid==gid), 'queue directory ownership or permissions differ')
    check_repository(REPO)


def check_repository(repo):
    git = repo/'.git'
    require(git.is_dir() and not (git/'commondir').exists()
            and not (git/'objects/info/alternates').exists(),
            'use a standalone launcher clone with its own Git metadata and objects')
    # The reviewed copy, including its repository metadata, stays in a tree
    # whose ownership and modes exclude agent changes.
    for entry in [*SOURCE_PATHS,'apparatus/qualified.json','apparatus/qualified.py','.git']:
        root = repo/entry
        protected(root)
        if root.is_dir():
            for directory, folders, files in os.walk(root):
                for filename in folders+files:
                    protected(Path(directory)/filename)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('queue', type=Path)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--live', action='store_true', help='Operator enables paid requests under the recorded campaign')
    parser.add_argument('--once', action='store_true', help='Process at most one new request, then exit')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        queue, config = args.queue.absolute(), args.config.absolute()
        deployment(queue, config)
        return serve(queue, config, args.live, args.once)
    except ValueError as error:
        print('Host dispatch refused: ' + str(error) + '. Nothing is retried.', file=sys.stderr)
        return 1
    except (OSError, KeyError, TypeError):
        # Configs and requests are nonsecret, but arbitrary subprocess errors need
        # not be. Keep raw exceptions out of the shared transcript.
        print('Host dispatch stopped; inspect configuration, pending request and retained claims. Nothing is retried.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
