"""Serial host dispatch for a delegated campaign; never a shell or a retry loop.

The operator starts this outside the agent sandbox. Requests select existing C10
operations. Each accepted request has an exclusive claim before execution, and
is never dispatched again. See HOST-QUEUE.md for authority and crash recovery.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (REPO, HERE, SOURCE_PATHS, digest, fields, identifier, read_file,
                    require, source_hash, strict_json, validate_continuation, validate_packet,
                    write_json)
from connections import validate_label
from launch import host_environment


def configuration(value, live):
    fields(value, ['campaign', 'authority', 'model', 'account', 'qualification',
                  'synthetic_connection', 'placement_ceiling', 'budget_usd', 'console'], 'host configuration')
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
        require(console['month'] == datetime.now(timezone.utc).strftime('%Y-%m'),
                'refresh the Console observation for this billing month; campaign allowance does not renew')
    return value


def evidence_path(value):
    path = Path(value)
    require(path.is_absolute() and path.parent == REPO / '.scratch'
            and identifier(path.name) and not path.is_symlink(), 'use evidence directly under .scratch')
    return path


def command(request, config, live):
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
            require(identifier(name) and Path(folder).is_absolute(), 'invalid submission')
            argv += ['--submission', name, folder]
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


def dispatch(queue, name, request_raw, argv, charge, config_hash):
    """A crash anywhere after mkdir leaves a claim, never an implicit retry."""
    claim = queue / 'claims' / name
    claim.mkdir(mode=0o700)
    (claim / 'request.json').write_bytes(request_raw)
    write_json(claim / 'command.json', {'argv': argv, 'placement_charge': charge,
                                      'configuration_sha256': config_hash, 'started_at': time.time()})
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


def placement_charge(claim):
    try:
        value = strict_json(read_file(claim / 'command.json'))['placement_charge']
        require(type(value) is int and value in [0, 1], 'invalid claim charge')
        return value
    except (OSError, ValueError, KeyError, TypeError):
        # A crash can interrupt the metadata write. Never infer no placement,
        # and do not make its damaged metadata prevent custody-only operations.
        return 1


def serve(queue, config_path, live, once=False):
    raw = read_file(config_path)
    config = configuration(strict_json(raw), live)
    config_hash = digest(raw)
    queue.mkdir(mode=0o700, exist_ok=True)
    for name in ['requests', 'claims', 'sessions']:
        (queue / name).mkdir(mode=0o700, exist_ok=True)
    with (queue / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        identity = queue / 'campaign.json'
        scope = {k: config[k] for k in ['campaign', 'authority', 'model', 'placement_ceiling', 'budget_usd']}
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
                require(identifier(name), 'invalid queue request name')
                if (queue / 'claims' / name).exists():
                    continue
                # A request is published by atomic rename after writing it fully.
                request_raw = read_file(path)
                request = strict_json(request_raw)
                argv, charge = command(request, config, live)
                claims = list((queue / 'claims').iterdir())
                require(charge == 0 or all(reconciled(p) for p in claims),
                        'unfinished host claim: reconcile effects before paid work')
                require(not charge or sum(placement_charge(p) for p in claims) + charge <= config['placement_ceiling'],
                        'campaign placement ceiling reached')
                code = dispatch(queue, name, request_raw, argv, charge, config_hash)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('queue', type=Path)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--live', action='store_true', help='Operator enables paid requests under the recorded campaign')
    parser.add_argument('--once', action='store_true', help='Process at most one new request, then exit')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        return serve(args.queue.resolve(), args.config.resolve(), args.live, args.once)
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
