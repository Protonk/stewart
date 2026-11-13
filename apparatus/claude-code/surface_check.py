"""Prepare and supervise a bounded supplied-surface comparison.

Preparation is offline. Live execution requires the exact commission digest
explicitly approved by the principal and paid extra usage disabled. Rehearsals
execute only the independent synthetic peer and Stewart's transport helpers.
Neither execution mode writes CHECK.json or a profile automatically.
"""

import argparse
import base64
import importlib.util
import os
from pathlib import Path
import shlex
import stat
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def sibling(name):
    spec = importlib.util.spec_from_file_location('surface_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p, bounded = sibling('profile'), sibling('bounded')
sys.path.insert(0, str(HERE.parent / 'driver'))
import claude_code_surface as surface
import claude_code_observer as observer

KINDS = observer.KINDS
SCHEMA = 'stewart.claude-code.surface-commission/1'
CONTROLLER = 'sources/apparatus/claude-code/surface_check.py'
SOURCE_FILES = ('claude-code/surface_check.py', 'claude-code/bounded.py', 'claude-code/profile.py', 'claude-code/pin.py',
                'driver/claude_code_observer.py', 'driver/claude_code_surface.py', 'driver/claude_code.py',
                'driver/driver_core.py', 'driver/rawjson.py', 'driver/claude_code_peer.py',
                'driver/fixture_expectations.py')


def save(path, value):
    p.publish(path, p.compact(value) + b'\n')


def digest_file(path):
    return p.read_file(path, limit=None, hash_only=True)[0]


def publish_ack(marker, session):
    """The synthetic reader sees either no acknowledgement or its full bytes."""
    marker.parent.mkdir(mode=0o700, exist_ok=True)
    temporary = marker.with_name('startup-observed.pending')
    save(temporary, {'session_id': session})
    parent = p.directory(marker.parent)
    try:
        os.link(temporary.name, marker.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        os.unlink(temporary.name, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(parent)


def copy_file(source, target):
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    p.publish(target, p.read_file(source, limit=None))


def helper_binary(path):
    path = p.absolute(path)
    raw = p.read_file(path, limit=None)
    if b'Stewart development build: claude-code' not in raw or b'__stewart-cc-relay' not in raw:
        raise ValueError('writer must be the gated Stewart helper binary')
    return p.sha(raw)


def wrapper_bytes(packet, python, scenario):
    witness = packet / 'observation/peer'
    peer = packet / 'sources/apparatus/driver/claude_code_peer.py'
    command = ' '.join(shlex.quote(item) for item in (python, '-I', '-B', str(peer),
                          '--witness-root', str(witness), '--scenario', scenario))
    return ('#!/bin/sh\nset -eu\numask 077\n'
            'environment_witness=$(/usr/bin/mktemp ' + shlex.quote(str(witness / 'environment.XXXXXX')) + ')\n'
            '/usr/bin/env -0 > "$environment_witness"\n'
            'exec ' + command + ' --environment-witness "$environment_witness" -- "$@"\n').encode()


def prepare_packet(packet, writer, model, family='open-inquiry', installation=None, scenario=None):
    """Create fresh immutable inputs; no harness/helper/auth process starts."""
    packet, writer = p.absolute(packet), p.absolute(writer)
    os.close(p.directory(packet.parent))
    writer_hash = helper_binary(writer)
    if family not in surface.FAMILIES:
        raise ValueError('unknown question family')
    p.text(model, 'model')
    if (installation is None) == (scenario is None):
        raise ValueError('choose a real installation or an explicit synthetic scenario')
    if scenario is not None and scenario not in ('normal', 'bad-init', 'wrong-auth'):
        raise ValueError('unknown synthetic scenario')
    mode = 'real-harness' if installation is not None else 'synthetic-rehearsal'
    if installation is not None:
        launch_raw, _ = p.validated_installation(p.absolute(installation))
    python = str(Path(sys.executable).resolve())
    packet.mkdir(mode=0o700)
    for name in SOURCE_FILES:
        copy_file(HERE.parent / name, packet / 'sources/apparatus' / name)
    if installation is not None:
        installation = p.absolute(installation)
        for name in ('launch.json', 'installation.json', 'PREPARATION.json'):
            copy_file(installation / name, packet / 'installation' / name)
        for item in p.verification_inventory(installation / 'installation'):
            copy_file(installation / 'installation' / item['path'], packet / 'installation/installation' / item['path'])
        assert p.validated_installation(packet / 'installation')[0] == launch_raw
    else:
        identity = packet / 'synthetic-identity'
        identity.mkdir(mode=0o700)
        for name in ('home', 'temporary', 'configuration'):
            (identity / name).mkdir(mode=0o700)
        executable = packet / 'synthetic-harness'
        p.publish(executable, wrapper_bytes(packet, python, scenario))
        executable.chmod(0o700)
        launch_raw = p.compact({'executable': str(executable), 'sha256': digest_file(executable),
            'version': 'synthetic-surface-check', 'platform': surface.spec.platform_name(),
            'home': str(identity / 'home'), 'temporary_directory': str(identity / 'temporary'),
            'config_directory': str(identity / 'configuration')})
    launch = p.decode(launch_raw)
    base = Path(tempfile.mkdtemp(prefix='stewart-surface-', dir='/tmp')).resolve()
    (packet / 'prepared').mkdir(mode=0o700)
    cases, slots, external_files = [], [], {writer, Path(launch['executable']), Path(python)}
    for kind in KINDS:
        workspace, prepared = base / kind, packet / 'prepared' / kind
        bindings, _ = surface.prepare(prepared, workspace, writer, launch_raw, family, model)
        supplied = surface.spec.filled_launch(str(writer), str(workspace), launch, family, model)
        for name in ('settings.json', 'mcp.json', 'system.txt'):
            external_files.add(workspace / name)
        cases.append({'id': kind, 'workspace': str(workspace), 'prepared': str(prepared)})
        for role in ('auth', 'model'):
            args = surface.spec.surface_document()['auth_argv'] if role == 'auth' else supplied['model_argv']
            slots.append({'id': kind + '-' + role, 'role': role, 'argv': [launch['executable']] + args,
                'environment': supplied['environment'], 'working_directory': str(workspace),
                'stdin_base64': '' if role == 'auth' else base64.b64encode(p.read_file(prepared / 'inputs/input.jsonl')).decode(),
                'timeout_seconds': (30 if role == 'auth' else 120) if mode == 'real-harness' else (10 if role == 'auth' else 30)})
    immutable = {path for path in packet.rglob('*') if path.is_file()}
    immutable.update(external_files)
    file_bindings = [{'path': str(path), 'sha256': digest_file(path)} for path in sorted(immutable)]
    budget = {'schema': 'stewart.claude-code.invocation-budget/1', 'mode': mode,
        'purpose': 'Three supplied-surface fixture comparisons: positive, hook denial and fresh-session invariance.',
        'overall_timeout_seconds': 450 if mode == 'real-harness' else 120,
        'bindings': file_bindings, 'invocations': slots}
    budget_digest = bounded.prepare(packet / 'invocations', budget)
    commission = {'schema': SCHEMA, 'mode': mode, 'prepared_at': surface.utc_now(),
        'scope': 'supplied-surface fixture compatibility only', 'family': family, 'bindings': bindings,
        'writer': {'path': str(writer), 'sha256': writer_hash}, 'python': python,
        'cases': cases, 'budget_sha256': budget_digest, 'scenario': scenario,
        'allowance': {'authentication_invocations': 3, 'model_invocations': 3,
                      'overall_timeout_seconds': budget['overall_timeout_seconds']},
        'route': 'claude.ai subscription; paid extra usage disabled' if mode == 'real-harness' else 'synthetic; no provider',
        'not_exercised': ['audit core/custody/publication', 'compaction and re-entry',
            'provider completeness or billing enforcement', 'turn/output-limit enforcement', 'hidden managed policy'],
        'approval': 'No launch authority is conferred by this prepared packet.'}
    save(packet / 'COMMISSION.json', commission)
    return commission


def verify_packet(packet):
    """Verify frozen files and exact specification-derived invocation requests."""
    packet = p.absolute(packet)
    raw = p.read_file(packet / 'COMMISSION.json')
    commission = p.decode(raw)
    p.exact(commission, ('schema', 'mode', 'prepared_at', 'scope', 'family', 'bindings', 'writer', 'python',
                        'cases', 'budget_sha256', 'scenario', 'allowance', 'route', 'not_exercised', 'approval'), 'commission')
    if commission['schema'] != SCHEMA or commission['mode'] not in ('real-harness', 'synthetic-rehearsal'):
        raise ValueError('unsupported surface commission')
    p.timestamp(commission['prepared_at'], 'preparation time')
    budget_raw = p.read_file(packet / 'invocations/BUDGET.json')
    if p.sha(budget_raw) != commission['budget_sha256']:
        raise ValueError('invocation budget differs from its commission')
    budget = bounded.validate(p.decode(budget_raw))
    if budget['mode'] != commission['mode'] or len(budget['invocations']) != 6:
        raise ValueError('commission requires exactly three fresh auth/model pairs')
    total = 450 if commission['mode'] == 'real-harness' else 120
    if (budget['overall_timeout_seconds'] != total or commission['allowance'] != {
            'authentication_invocations': 3, 'model_invocations': 3, 'overall_timeout_seconds': total}
            or commission['scope'] != 'supplied-surface fixture compatibility only'):
        raise ValueError('commission allowance or scope differs from this comparison')
    bounded.verify_bindings(budget)
    if [case['id'] for case in commission['cases']] != list(KINDS):
        raise ValueError('case order differs from the commissioned comparisons')
    launch_raw = p.read_file(packet / 'prepared/positive/inputs/launch.json')
    launch = p.decode(launch_raw)
    if commission['mode'] == 'real-harness':
        if p.validated_installation(packet / 'installation')[0] != launch_raw or commission['scenario'] is not None:
            raise ValueError('real-harness launch differs from its verified installation')
    else:
        if (launch['executable'] != str(packet / 'synthetic-harness') or launch['version'] != 'synthetic-surface-check'
                or commission['scenario'] not in ('normal', 'bad-init', 'wrong-auth')
                or p.read_file(packet / 'synthetic-harness') != wrapper_bytes(packet, commission['python'], commission['scenario'])):
            raise ValueError('rehearsal may execute only the frozen synthetic peer wrapper')
    if helper_binary(Path(commission['writer']['path'])) != commission['writer']['sha256']:
        raise ValueError('Stewart helper binary changed')
    model, family = commission['bindings']['model'], commission['family']
    expected_bindings = {'launch_sha256': p.sha(launch_raw), 'surface_sha256': p.sha(surface.spec.SURFACE),
        'tools_sha256': p.sha(surface.spec.mcp_tools(surface.spec.compact(surface.spec.expected_tools(family)))), 'model': model}
    if commission['bindings'] != expected_bindings:
        raise ValueError('commission launch/surface/tools/model binding differs')
    required = {Path(commission['writer']['path']), Path(launch['executable']), Path(commission['python'])}
    for path in packet.rglob('*'):
        relative = path.relative_to(packet)
        if relative.parts[0] in ('observation', 'invocations') or relative == Path('COMMISSION.json'):
            continue
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            required.add(path)
        elif not stat.S_ISDIR(mode):
            raise ValueError('immutable packet contains a link or special entry')
    for index, case in enumerate(commission['cases']):
        kind, workspace = KINDS[index], Path(case['workspace'])
        if case['prepared'] != str(packet / 'prepared' / kind):
            raise ValueError('prepared inputs are outside their frozen packet location')
        if p.read_file(Path(case['prepared']) / 'inputs/launch.json') != launch_raw:
            raise ValueError('case launch bindings differ')
        supplied = surface.spec.filled_launch(commission['writer']['path'], str(workspace), launch, family, model)
        for name in ('settings.json', 'mcp.json', 'system.txt'):
            required.add(workspace / name)
        for offset, role in enumerate(('auth', 'model')):
            slot = budget['invocations'][index * 2 + offset]
            expected_args = surface.spec.surface_document()['auth_argv'] if role == 'auth' else supplied['model_argv']
            payload = b'' if role == 'auth' else p.read_file(Path(case['prepared']) / 'inputs/input.jsonl')
            expected_timeout = (30 if role == 'auth' else 120) if commission['mode'] == 'real-harness' else (10 if role == 'auth' else 30)
            if (slot['id'] != kind + '-' + role or slot['role'] != role or slot['working_directory'] != str(workspace)
                    or slot['environment'] != supplied['environment'] or slot['argv'] != [launch['executable']] + expected_args
                    or base64.b64decode(slot['stdin_base64'], validate=True) != payload
                    or slot['timeout_seconds'] != expected_timeout):
                raise ValueError('invocation differs from its frozen supplied surface')
    if {Path(item['path']) for item in budget['bindings']} != required:
        raise ValueError('immutable input binding inventory is incomplete or has unexpected members')
    return commission, raw


def accept_case(assessment, entry, bindings, workspaces, sessions):
    if (assessment['errors'] or set(assessment['checks']) != set(surface.REQUIRED_CHECKS)
            or any(value != 'observed' for value in assessment['checks'].values())
            or assessment['stopping'] != 'observed' or assessment['bindings'] != bindings
            or assessment['workspace'] != entry['workspace']):
        raise ValueError('independent comparison failed or was unexercised: ' + entry['id'])
    if (not assessment['session_id'] or assessment['session_id'] in sessions
            or assessment['workspace'] in workspaces):
        raise ValueError('comparison did not use a fresh session and workspace: ' + entry['id'])
    workspaces.add(assessment['workspace'])
    sessions.add(assessment['session_id'])


def run_packet(packet, approved=None, extra_usage_disabled=False, rehearsal=False):
    packet = p.absolute(packet)
    commission, raw = verify_packet(packet)
    if Path(__file__).resolve() != packet / CONTROLLER:
        raise ValueError('run the frozen controller at ' + str(packet / CONTROLLER))
    if str(Path(sys.executable).resolve()) != commission['python']:
        raise ValueError('run the frozen controller with its bound Python interpreter')
    mode = commission['mode']
    if rehearsal:
        if mode != 'synthetic-rehearsal' or approved is not None or extra_usage_disabled:
            raise ValueError('rehearsal accepts only its synthetic packet, without live approval')
    elif mode != 'real-harness' or approved != p.sha(raw) or extra_usage_disabled is not True:
        raise ValueError('live comparison needs the principal-approved exact commission digest and paid extra usage disabled')
    out = packet / 'observation'
    cases, failures, attempted = [], [], []
    workspaces, sessions = set(), set()
    # Opening a budget is one-use and durable. Nothing resumes after an uncertain
    # reply, even if no model invocation had yet started.
    with bounded.Budget(packet / 'invocations', None if rehearsal else commission['budget_sha256'],
                        False if rehearsal else extra_usage_disabled) as book:
        out.mkdir(mode=0o700)
        (out / 'cases').mkdir(mode=0o700)
        if rehearsal:
            (out / 'peer').mkdir(mode=0o700)
        for entry in commission['cases']:
            case = None
            identity, workspace = entry['id'], Path(entry['workspace'])
            try:
                if p.read_file(packet / 'COMMISSION.json') != raw:
                    raise ValueError('approved commission changed')
                case = observer.CaseObserver(Path(entry['prepared']) / 'inputs', identity, identity,
                                             workspace, out / 'cases' / identity)
                case.start_listeners()
                attempted.append(identity)
                auth = book.execute(identity + '-auth')
                if auth['stop'] is not None or not auth['group_gone']:
                    raise ValueError('fresh authentication failed; no model started for ' + identity)
                auth_receipt = p.decode(p.read_file(packet / 'invocations/uses' / (identity + '-auth') / 'auth-status.json'))
                if p.read_file(packet / 'COMMISSION.json') != raw:
                    raise ValueError('approved commission changed after authentication')
                slot = book.value['invocations'][book.index]
                case.record_launch({'argv': slot['argv'], 'env': slot['environment'], 'cwd': str(workspace),
                    'executable_sha256': digest_file(Path(slot['argv'][0])),
                    'files_sha256': {name: digest_file(workspace / name) for name in ('settings.json', 'mcp.json', 'system.txt')}})

                def feed(chunk):
                    case.feed(chunk)
                    if rehearsal and case.valid_init:
                        # This only schedules the synthetic peer; it is not a
                        # product handshake or evidence of real startup ordering.
                        marker = out / 'peer' / p.sha(os.fsencode(str(workspace))) / 'startup-observed.json'
                        if not marker.exists():
                            publish_ack(marker, case.init['session_id'])

                result = book.execute(identity + '-model', on_stdout=feed, on_stderr=case.feed_stderr,
                                      check_stop=case.check_stop)
                for channel in ('stdout', 'stderr'):
                    if result['stream_eof'][channel]:
                        try:
                            case.finish_stream(channel)
                        except observer.ObserverStop:
                            pass  # finish records the failed complete assessment.
                payload = base64.b64decode(slot['stdin_base64'], validate=True)
                try:
                    case.record_input(payload, payload[:result['input_bytes_sent']])
                except observer.ObserverStop:
                    pass
                assessment = case.finish(result, auth_receipt)
                cases.append(case)
                accept_case(assessment, entry, commission['bindings'], workspaces, sessions)
            except (Exception, KeyboardInterrupt) as error:
                failures.append({'case': identity, 'error': type(error).__name__ + ': ' + str(error)})
                if case is not None:
                    case.close()
                book.halt('comparison stopped; see retained controller failure')
                break
    # Freeze evidence only after the budget closes; its final ledger must be part
    # of the observation. Socket workspaces remain elsewhere.
    for path in sorted((packet / 'invocations').rglob('*')):
        if path.is_file():
            copy_file(path, out / 'execution' / path.relative_to(packet / 'invocations'))
    copy_file(packet / 'COMMISSION.json', out / 'commission.json')
    for name in SOURCE_FILES:
        copy_file(packet / 'sources/apparatus' / name, out / 'controller-sources/apparatus' / name)
    result = {'schema': 'stewart.claude-code.surface-run/1', 'mode': mode, 'commission_sha256': p.sha(raw),
        'attempted_cases': attempted, 'completed_cases': [case.case_id for case in cases], 'failures': failures,
        'outcome': 'failed',
        'synthetic_coordination': 'startup-observed.json schedules the fake peer only' if rehearsal else None,
        'review_required': True, 'launch_authority_for_another_run': False}
    if len(cases) == 3:
        def finalize(checks, stopping):
            result['outcome'] = 'observed' if not failures and stopping == 'observed' and all(
                check['outcome'] == 'observed' for check in checks) else 'failed'
            save(out / 'RESULT.json', result)
        observer.assess_batch(out, cases, mode, before_finalize=finalize)
    else:
        save(out / 'RESULT.json', result)
        save(out / 'EVIDENCE.json', surface.manifest(out))
    print('Retained comparison: ' + str(out))
    print('Outcome: ' + result['outcome'] + '; no CHECK.json or profile was written.')
    return int(result['outcome'] != 'observed')


def attest(packet, observation_digest, reviewer, output):
    """Record an explicit independent review; never infer it from run completion."""
    commission, commission_raw = verify_packet(packet)
    if commission['mode'] != 'real-harness':
        raise ValueError('synthetic rehearsals cannot receive a reviewed check')
    out = packet / 'observation'
    raw = p.read_file(out / 'OBSERVATION.json')
    observation = p.decode(raw)
    p.exact(observation, ('schema', 'mode', 'scope', 'started_at', 'finished_at', *p.BINDINGS,
                         'evidence_manifest_sha256', 'checks', 'stopping'), 'observation')
    if (observation['schema'] != 'stewart.claude-code.surface-observation/1'
            or observation['scope'] != 'supplied-surface'
            or p.timestamp(observation['finished_at'], 'finish') < p.timestamp(observation['started_at'], 'start')):
        raise ValueError('observation schema, scope or times differ')
    if observation_digest != p.sha(raw):
        raise ValueError('reviewed observation digest differs')
    p.text(reviewer, 'independent reviewer')
    manifest = p.read_file(out / 'EVIDENCE.json')
    members = p.evidence(out, manifest)
    run = p.decode(p.read_file(out / 'RESULT.json'))
    ledger = p.decode(p.read_file(out / 'execution/FINISH.json'))
    start = p.decode(p.read_file(out / 'execution/START.json'))
    if (run['schema'] != 'stewart.claude-code.surface-run/1'
            or run['outcome'] != 'observed' or run['mode'] != 'real-harness' or run['failures']
            or run['commission_sha256'] != p.sha(commission_raw)
            or run['completed_cases'] != list(KINDS) or run['attempted_cases'] != list(KINDS)
            or ledger != {'invocations_reserved': 6, 'invocations_unstarted': 0, 'failed': False, 'resume_allowed': False}
            or start['approved_digest'] != commission['budget_sha256'] or start['extra_usage_disabled'] is not True
            or start['mode'] != 'real-harness' or start['budget_sha256'] != commission['budget_sha256']
            or p.sha(p.read_file(out / 'execution/BUDGET.json')) != commission['budget_sha256']
            or observation['mode'] != 'real-harness' or observation['stopping'] != 'observed'
            or observation['evidence_manifest_sha256'] != p.sha(manifest)
            or {key: observation[key] for key in p.BINDINGS} != commission['bindings']
            or len(observation['checks']) != len(surface.REQUIRED_CHECKS)
            or {check['id'] for check in observation['checks']} != set(surface.REQUIRED_CHECKS)
            or any(check['outcome'] != 'observed' or not check['evidence']
                   or any(name not in members for name in check['evidence']) for check in observation['checks'])):
        raise ValueError('review requires a complete, stopped and observed real-harness comparison')
    for name, key in (('launch', 'launch_sha256'), ('surface', 'surface_sha256'), ('tools', 'tools_sha256')):
        if p.sha(p.read_file(out / 'inputs' / (name + '.json'))) != commission['bindings'][key]:
            raise ValueError('reviewed input binding differs')
    output = p.absolute(output)
    if output != out / 'CHECK.json':
        os.close(p.directory(output.parent))
        if any(os.path.samefile(packet, parent) for parent in output.parents):
            raise ValueError('review output must be observation/CHECK.json or outside the frozen packet')
    checked = observation['finished_at']
    if p.timestamp(checked, 'observation finish') > p.timestamp(surface.utc_now(), 'review time'):
        raise ValueError('observation finish lies after this review')
    save(output, {'schema': 'stewart.claude-code.reviewed-check/1', 'scope': 'supplied-surface',
        **commission['bindings'], 'checked_at': checked, 'observation_sha256': p.sha(raw),
        'reviewer': reviewer, 'reviewed_at': surface.utc_now(), 'outcome': 'observed'})
    print('Attributed review written: ' + str(output) + '; no launch authority conferred.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prepare = commands.add_parser('prepare', help='freeze a proposed live commission without launching anything')
    for name in ('output', 'binary', 'installation-directory'):
        prepare.add_argument('--' + name, type=p.absolute, required=True)
    prepare.add_argument('--model', required=True)
    prepare.add_argument('--family', choices=surface.FAMILIES, default='open-inquiry')
    rehearsal = commands.add_parser('prepare-rehearsal', help='freeze a synthetic peer comparison; no real installation accepted')
    for name in ('output', 'binary'):
        rehearsal.add_argument('--' + name, type=p.absolute, required=True)
    rehearsal.add_argument('--scenario', choices=('normal', 'bad-init', 'wrong-auth'), default='normal')
    rehearsal.add_argument('--model', default='synthetic-control-model')
    rehearsal.add_argument('--family', choices=surface.FAMILIES, default='open-inquiry')
    for action in ('inspect', 'run', 'run-rehearsal', 'attest'):
        command = commands.add_parser(action)
        command.add_argument('--packet', type=p.absolute, required=True)
        if action == 'run':
            command.add_argument('--approved-commission', required=True)
            command.add_argument('--extra-usage-disabled', action='store_true')
        if action == 'attest':
            command.add_argument('--reviewed-observation', required=True)
            command.add_argument('--reviewer', required=True)
            command.add_argument('--output', type=p.absolute, required=True)
    args = parser.parse_args()
    try:
        if args.action in ('prepare', 'prepare-rehearsal'):
            prepare_packet(args.output, args.binary, args.model, args.family,
                installation=args.installation_directory if args.action == 'prepare' else None,
                scenario=args.scenario if args.action == 'prepare-rehearsal' else None)
            commission, raw = verify_packet(args.output)
            print('Prepared: ' + str(args.output))
            print('Commission SHA-256: ' + p.sha(raw))
            print('Frozen controller: ' + str(args.output / CONTROLLER))
            print('No invocation has started; live use needs separate bounded approval.')
            return 0
        if args.action == 'inspect':
            commission, raw = verify_packet(args.packet)
            print(p.compact({'commission_sha256': p.sha(raw), 'commission': commission}).decode())
            return 0
        if args.action == 'attest':
            attest(args.packet, args.reviewed_observation, args.reviewer, args.output)
            return 0
        return run_packet(args.packet, getattr(args, 'approved_commission', None),
                          getattr(args, 'extra_usage_disabled', False), rehearsal=args.action == 'run-rehearsal')
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        parser.exit(1, 'surface comparison refused: ' + str(error) + '\n')


if __name__ == '__main__':
    sys.exit(main())
