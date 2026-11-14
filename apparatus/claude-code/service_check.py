"""Bounded native service placements, with explicit authority and retained evidence.

Preparation and review launch no Claude process. Each numbered attempt is one-use;
continuation requires review of the preceding stopped placement. No automatic starts.
"""
import argparse
import base64
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'driver'))
import claude_code_service_witness as witness
import answer_witness as answer
spec = importlib.util.spec_from_file_location('service_profile', HERE / 'profile.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
SOURCES = ('claude-code/service_check.py', 'claude-code/profile.py', 'claude-code/pin.py',
           'driver/claude_code_service_witness.py', 'driver/answer_witness.py',
           'driver/claude_code.py', 'driver/driver_core.py', 'driver/rawjson.py')
ENV = {'PATH': '/usr/bin:/bin', 'TMPDIR': '/private/tmp', 'LANG': 'C.UTF-8'}
# Python before 3.10 gives macOS time.monotonic_ns() a process-local origin.
CLOCK_NAME = 'CLOCK_UPTIME_RAW' if sys.platform == 'darwin' else 'CLOCK_MONOTONIC'
CLOCK = getattr(time, CLOCK_NAME)
# After an abnormal run return the client may just have been stopped; allow
# the service's groups this many one-second read-only observations.
ABNORMAL_STOP_PROBES = 6


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def save(path, value):
    p.publish(path, p.compact(value) + b'\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inventory(root):
    """Physical regular files and directories only; no silent omitted members."""
    os.close(p.directory(root))
    rows = []
    for item in sorted(root.rglob('*')):
        mode = item.lstat().st_mode
        relative = str(item.relative_to(root))
        if stat.S_ISDIR(mode):
            rows.append({'path': relative, 'type': 'directory'})
        else:
            require(stat.S_ISREG(mode), 'nonregular tree member: ' + str(item))
            digest, size = p.read_file(item, limit=None, hash_only=True)
            rows.append({'path': relative, 'type': 'file', 'bytes': size, 'sha256': digest})
    return rows


def snapshot(source, target):
    """Copy a stopped tree privately, preserving exact bytes and checking stability."""
    before = inventory(source)
    require(sum(row.get('bytes', 0) for row in before) <= 512 * 1024 * 1024,
            'snapshot exceeds the 512 MiB apparatus bound; preserve original for review')
    target.mkdir(mode=0o700)
    for row in before:
        out = target / row['path']
        if row['type'] == 'directory':
            out.mkdir(mode=0o700)
        else:
            raw = p.read_file(source / row['path'], limit=None)
            require(p.sha(raw) == row['sha256'], 'tree changed during capture')
            p.publish(out, raw)
    require(inventory(source) == before and inventory(target) == before,
            'tree membership or bytes changed during capture')
    return before


def delivered_modes(root):
    """Permission bits of a delivered package, read from the original.

    snapshot() publishes its private copy as 0700/0600 whatever the source
    had, so a mode checked on that copy observes the apparatus, not delivery.
    """
    os.close(p.directory(root))
    rows = {'.': '%04o' % stat.S_IMODE(root.lstat().st_mode)}
    for item in sorted(root.rglob('*')):
        rows[str(item.relative_to(root))] = '%04o' % stat.S_IMODE(item.lstat().st_mode)
    return rows


def package_mode_defects(modes, rows):
    """INTERFACE 8.2: the package directory has mode 0700 and its files 0600."""
    if type(modes) is not dict:
        return ['delivered package modes were not captured from the original']
    defects = []
    if modes.get('.') != '0700':
        defects.append('package directory has mode %s, not 0700' % modes.get('.'))
    for row in rows:
        if row['type'] == 'file' and modes.get(row['path']) != '0600':
            defects.append('%s has mode %s, not 0600' % (row['path'], modes.get(row['path'])))
    if set(modes) - {'.'} != {row['path'] for row in rows}:
        defects.append('captured modes and captured membership name different members')
    return defects


def profile_from(preparation):
    reply = p.decode(p.read_file(Path(preparation)))
    require(reply['operation'] == 'prepare' and reply['outcome'] == 'completed',
            'a completed local preparation is required')
    settings = reply['data']['settings']
    require(settings['family'] == 'open-inquiry' and settings['runtime']['kind'] == 'claude-code/1',
            'this procedure covers runtime open inquiry only')
    require(type(settings['limits']['max_placements']) is int
            and 1 <= settings['limits']['max_placements'] <= 3,
            'this procedure permits one to three placements')
    return reply, settings, p.decode(settings['runtime']['profile'].encode())


def prepare(output, preparation, reference, folder, writer, mode='real-harness', synthetic=None):
    output, preparation, folder, writer = map(p.absolute, (output, preparation, folder, writer))
    require(mode in ('real-harness', 'synthetic-rehearsal'), 'unknown packet mode')
    reply, settings, profile = profile_from(preparation)
    parts = reference.split(':', 3)
    require(len(parts) == 4 and parts[0] == 'stw1', 'invalid reference')
    archive = p.absolute(parts[3])
    require(not any(output == path or output in path.parents or path in output.parents
                    for path in (archive, folder, writer)), 'packet overlaps protected inputs')
    audit = archive / 'audits' / parts[1]
    ref_raw = p.read_file(audit / 'REFERENCE.json')
    ref = p.decode(ref_raw)
    require(ref['body']['folder'] == str(folder) and ref['body']['archive'] == str(archive)
            and ref['body']['audit'] == parts[1] and ref['body']['store'] == parts[2]
            and ref['body']['writer'] == {'path': str(writer), 'sha256': p.read_file(writer, limit=None, hash_only=True)[0]},
            'reference, folder or original writer differs')
    seconds = settings['limits']['placement_timeout_seconds']
    placements = settings['limits']['max_placements']
    require(type(seconds) is int and 1 <= seconds <= 600, 'placement exceeds this procedure bound')
    require(seconds * placements <= 900, 'packet exceeds 900 seconds of total placement time')
    if mode == 'real-harness':
        require(synthetic is None and profile['launch']['version'] != 'synthetic-offline-1'
                and settings['model'] == 'claude-haiku-5-5', 'unexpected real profile/model')
    else:
        require(profile['launch']['version'] == 'synthetic-offline-1'
                and settings['model'] == witness.runtime.MODEL and seconds <= 15,
                'rehearsal accepts only the existing synthetic fixture')
        require(synthetic is not None, 'rehearsal must bind its original peer and scenario')
        wrapper = p.read_file(Path(profile['launch']['executable']))
        require(wrapper == witness.runtime.synthetic_executable(
            Path(synthetic['script']), Path(synthetic['scenario']), Path(synthetic['witness']),
            python=str(Path(sys.executable).resolve())),
            'rehearsal executable is not the exact synthetic peer wrapper')
    output.mkdir(mode=0o700)
    sources = output / 'sources'
    for name in SOURCES:
        dest = sources / name
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        p.publish(dest, p.read_file(HERE.parent / name))
    (output / 'inputs').mkdir(mode=0o700)
    snapshot(folder, output / 'inputs/submission')
    p.publish(output / 'inputs/prepare.json', p.read_file(preparation))
    p.publish(output / 'inputs/reference.json', ref_raw)
    p.publish(output / 'inputs/profile.json', settings['runtime']['profile'].encode())
    arrangement = Path(reply['data']['arrangement']['machine'])
    p.publish(output / 'inputs/arrangement.json', p.read_file(arrangement))
    p.publish(output / 'inputs/arrangement.md', p.read_file(Path(reply['data']['arrangement']['readable'])))
    paths = [writer, Path(sys.executable).resolve(), Path(profile['launch']['executable']),
             Path(settings['runtime']['profile_path']), audit / 'REFERENCE.json', arrangement,
             Path(reply['data']['arrangement']['readable'])]
    paths += [path for path in output.rglob('*') if path.is_file()]
    if synthetic:
        paths += [Path(synthetic['script']), Path(synthetic['scenario'])]
        paths += list(Path(synthetic['script']).parent.glob('*.py'))
    manifest = {'schema': 'stewart.claude-code.service-commission/2', 'mode': mode,
                'prepared_at': utc(), 'reference': reference, 'folder': str(folder),
                'archive': str(archive), 'writer': str(writer), 'python': str(Path(sys.executable).resolve()),
                'prepared_handle': reply['data']['prepared'], 'model': settings['model'],
                'placement_timeout_seconds': seconds, 'service_command_timeout_seconds': seconds + 15,
                'max_service_starts': placements, 'max_authentication_invocations': placements,
                'max_model_invocations': placements, 'max_placement_seconds': seconds * placements,
                'continuation_causes': ['placement_deadline'],
                'environment': ENV, 'cwd': '/private/tmp', 'submission': inventory(folder),
                'bindings': [{'path': str(path), 'sha256': p.read_file(path, limit=None, hash_only=True)[0]}
                             for path in dict.fromkeys(paths)],
                'scope': 'One prepared audit with numbered, individually reviewed service placements; retain every stopped capture. No automatic close, continuation or replacement.',
                'authority': None, 'synthetic': synthetic,
                'extra_usage': 'Included subscription use only; paid extra usage must be disabled.',
                'witness_scope': 'Outside input/package snapshots and group probes; private service captures retain service-owned provenance.'}
    save(output / 'COMMISSION.json', manifest)
    return p.sha(p.read_file(output / 'COMMISSION.json'))


def verify(packet):
    packet = p.absolute(packet)
    raw = p.read_file(packet / 'COMMISSION.json')
    value = p.decode(raw)
    require(value['schema'] == 'stewart.claude-code.service-commission/2', 'unknown commission schema')
    require(value['mode'] in ('real-harness', 'synthetic-rehearsal')
            and type(value['max_service_starts']) is int and 1 <= value['max_service_starts'] <= 3
            and value['max_service_starts'] == value['max_authentication_invocations'] == value['max_model_invocations'],
            'commission is outside bounded placement scope')
    require(value['environment'] == ENV and value['cwd'] == '/private/tmp', 'manager environment changed')
    require(value['continuation_causes'] == ['placement_deadline'], 'continuation scope changed')
    for row in value['bindings']:
        require(p.read_file(Path(row['path']), limit=None, hash_only=True)[0] == row['sha256'],
                'bound input changed: ' + row['path'])
    require(inventory(Path(value['folder'])) == value['submission'], 'submission membership or bytes changed')
    reply, settings, profile = profile_from(packet / 'inputs/prepare.json')
    require(value['prepared_handle'] == reply['data']['prepared']
            and value['model'] == settings['model']
            and value['placement_timeout_seconds'] == settings['limits']['placement_timeout_seconds']
            and value['max_service_starts'] == settings['limits']['max_placements']
            and 1 <= value['placement_timeout_seconds'] <= 600
            and value['max_placement_seconds'] == value['max_service_starts'] * value['placement_timeout_seconds']
            and value['max_placement_seconds'] <= 900
            and value['service_command_timeout_seconds'] == value['placement_timeout_seconds'] + 15,
            'commission differs from prepared scope or bounds')
    required = {value['writer'], value['python'], profile['launch']['executable'],
                settings['runtime']['profile_path'], str(Path(value['archive']) / 'audits' /
                value['reference'].split(':', 3)[1] / 'REFERENCE.json'),
                reply['data']['arrangement']['machine'], reply['data']['arrangement']['readable']}
    for directory in (packet / 'sources', packet / 'inputs'):
        required.update(str(directory / row['path']) for row in inventory(directory) if row['type'] == 'file')
    if value['synthetic']:
        required.update((value['synthetic']['script'], value['synthetic']['scenario']))
        required.update(str(path) for path in Path(value['synthetic']['script']).parent.glob('*.py'))
    require(len(value['bindings']) == len(required) and {row['path'] for row in value['bindings']} == required,
            'binding inventory omits or adds an input')
    if value['mode'] == 'synthetic-rehearsal':
        synthetic = value['synthetic']
        require(profile['launch']['version'] == 'synthetic-offline-1'
                and settings['model'] == witness.runtime.MODEL and value['placement_timeout_seconds'] <= 15,
                'rehearsal profile differs')
        require(p.read_file(Path(profile['launch']['executable'])) == witness.runtime.synthetic_executable(
                Path(synthetic['script']), Path(synthetic['scenario']), Path(synthetic['witness']), python=value['python']),
                'rehearsal wrapper differs')
    return value, raw


def frozen_executor(packet, manifest):
    require(Path(__file__).resolve() == packet / 'sources/claude-code/service_check.py'
            and str(Path(sys.executable).resolve()) == manifest['python'],
            'use the frozen controller and its bound Python interpreter')


def execution_evidence(out):
    raw = p.read_file(out / 'EVIDENCE.json')
    listed = p.decode(raw)['members']
    actual = [row for row in inventory(out) if row['path'] != 'EVIDENCE.json']
    require(actual == listed, 'execution evidence changed or has missing/unlisted members')
    return p.sha(raw)


def command(directory, label, argv, timeout):
    """Observe the direct client group; service-owned groups are checked separately."""
    save(directory / (label + '.start.json'), {'argv': argv, 'timeout_seconds': timeout,
         'environment': ENV, 'cwd': '/private/tmp', 'started_at': utc()})
    result = {'exit': None, 'timed_out': False, 'client_reaped': False, 'client_group_absent': False}
    started = time.monotonic()
    child = None
    try:
        with (directory / (label + '.stdout')).open('xb') as stdout, (directory / (label + '.stderr')).open('xb') as stderr:
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                     env=ENV, cwd='/private/tmp', start_new_session=True)
            save(directory / (label + '.process.json'), {'pid': child.pid, 'group': child.pid})
            try:
                result['exit'] = child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                result['timed_out'] = True
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    result['exit'] = child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    result['exit'] = child.wait(timeout=3)
            result['client_reaped'] = True
            result['client_group_absent'] = witness.runtime.group_observation(child.pid) == 'absent'
    except BaseException:
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
                result['exit'] = child.wait(timeout=3)
                result['client_reaped'] = True
                result['client_group_absent'] = witness.runtime.group_observation(child.pid) == 'absent'
            except (OSError, subprocess.TimeoutExpired):
                pass
        raise
    finally:
        result['elapsed_seconds'] = time.monotonic() - started
        save(directory / (label + '.result.json'), result)
    require(not result['timed_out'], label + ': command exceeded its observation deadline; inspect retained effects')
    require(result['client_reaped'] and result['client_group_absent'],
            label + ': command stopping is uncertain; inspect originals before any mutation')
    return result


def json_command(directory, label, manifest, args, allowed=(0,)):
    result = command(directory, label, [manifest['writer'], *args, '--json'],
                     manifest['service_command_timeout_seconds'] if args[0] == 'run' else 30)
    require(result['exit'] in allowed, label + ': unexpected exit ' + str(result['exit']))
    return p.decode(p.read_file(directory / (label + '.stdout')))


def stopping(audit, output, placement=1, probes=1, pause=1.0):
    """Probe the service-recorded groups; only observed absence of both is stopping.

    `probes` bounds repeated read-only observations after an abnormal return.
    The last one decides; every observation is retained.
    """
    record = {'service_records': {}, 'observations': [], 'diagnostics': [], 'probes': 0,
              'clock': CLOCK_NAME, 'observer_pid': os.getpid(), 'started_at': utc(),
              'scope': 'Copied service-owned group identities; independent read-only absence probes after run return.'}
    observed = False
    for probe in range(1, probes + 1):
        record['probes'] = probe
        rows, diagnostics = [], []
        for role in ('auth', 'model'):
            try:
                raw = p.read_file(audit / 'runs' / str(placement) / ('process-' + role + '.json'))
                value = p.decode(raw)
                record['service_records'][role] = {'raw_base64': base64.b64encode(raw).decode(), 'sha256': p.sha(raw)}
                require(value['schema'] == 'stewart.claude-code.process/1' and value['role'] == role
                        and type(value['group']) is int and value['group'] > 1, 'invalid group record')
                before = time.clock_gettime_ns(CLOCK)
                observation = witness.runtime.group_observation(value['group'])
                rows.append({'probe': probe, 'role': role, 'group': value['group'], 'observation': observation,
                             'started_ns': before, 'finished_ns': time.clock_gettime_ns(CLOCK)})
            except (OSError, ValueError, KeyError, TypeError) as error:
                diagnostics.append(str(error))
        record['observations'].extend(rows)
        record['diagnostics'] = diagnostics
        observed = not diagnostics and len(rows) == 2 and all(row['observation'] == 'absent' for row in rows)
        if observed or probe == probes:
            break
        time.sleep(pause)
    record['observed'] = observed
    record['finished_at'] = utc()
    save(output, record)
    return observed


def observed_run(out, manifest, audit, placement, result):
    """Run one reserved placement and probe stopping however the command returns.

    A timeout, unexpected exit or unusable reply stops only the client group.
    That is not an observation of the service's authentication and model
    groups, so they are probed before the failure propagates. `stopping_probed`
    separates "not probed" from "probed and not absent".
    """
    try:
        result['run_reply'] = json_command(out, 'run', manifest, ['run', manifest['reference']], allowed=(0, 3, 4, 5))
    except BaseException:
        result['stopping_observed'] = stopping(audit, out / 'STOPPING.json', placement, probes=ABNORMAL_STOP_PROBES)
        result['stopping_probed'] = True
        raise
    result['stopping_observed'] = stopping(audit, out / 'STOPPING.json', placement)
    result['stopping_probed'] = True


def deadline_established(manifest, run_result, stop, last_run, placement):
    """A commissioned deadline needs more than the service's cause label.

    The apparatus's own measurement of the run command must reach the placement
    deadline, and the retained stop record must show elapsed time and absent groups.
    """
    return (deadline_observed(last_run, stop, placement, manifest['max_service_starts'])
            and type(run_result['elapsed_seconds']) in (int, float)
            and run_result['elapsed_seconds'] >= manifest['placement_timeout_seconds'])


def placement_root(packet, manifest, placement):
    require(type(placement) is int and 1 <= placement <= manifest['max_service_starts'],
            'placement number exceeds the commissioned starts')
    return packet / 'placements' / str(placement)


def attempts(packet):
    root = packet / 'placements'
    if not root.exists():
        return []
    members = list(root.iterdir())
    require(all(path.is_dir() and not path.is_symlink() and re.fullmatch(r'[1-3]', path.name)
                for path in members), 'unexpected placement attempt member')
    return sorted(int(path.name) for path in members)


def continuation_state(manifest, status, placement):
    """A conservative apparatus gate; the service remains the lifecycle authority."""
    data = status['data']
    headline = data['headline']
    return (status['outcome'] == 'completed' and data['condition'] == 'interrupted'
            and data['runs']['count'] == placement and data['runs']['held'] is False
            and data['runs']['last']['number'] == placement
            and data['runs']['last']['ending'] == 'interrupted'
            and data['runs']['last']['cause'] in manifest['continuation_causes']
            and headline['accepted'] == headline['launched'] == 'yes'
            and headline['authoring'] == {'state': 'open', 'ended_by': None}
            and headline['closed'] == 'no' and data['seal']['state'] == 'absent'
            and data['closure'] is None and headline['delivered']['verified'] is False
            and data['allowances']['placements'] == {'used': placement,
                'limit': manifest['max_service_starts'], 'remaining': manifest['max_service_starts'] - placement}
            and data['allowances']['placement_timeout_seconds'] == manifest['placement_timeout_seconds']
            and placement < manifest['max_service_starts'])


def reviewed_execution(packet, manifest, commission_raw, placement, reviewed):
    root = placement_root(packet, manifest, placement)
    raw = p.read_file(root / 'review/REVIEW.json')
    assessment = p.decode(raw)
    require(reviewed == p.sha(raw) and assessment['outcome'] == 'observed',
            'explicit review of the preceding stopped execution is required')
    out = root / 'execution'
    require(assessment['placement'] == placement
            and assessment['commission_sha256'] == p.sha(commission_raw)
            and assessment['execution_result_sha256'] == p.sha(p.read_file(out / 'RESULT.json'))
            and assessment['execution_evidence_sha256'] == execution_evidence(out),
            'reviewed execution evidence or commission changed')
    result = p.decode(p.read_file(out / 'RESULT.json'))
    require(result['outcome'] == 'retained' and result['stopping_observed'],
            'reviewed placement lacks a complete stopped capture')
    if placement > 1:
        start = p.decode(p.read_file(out / 'START.json'))
        reviewed_execution(packet, manifest, commission_raw, placement - 1, start['reviewed_prior_sha256'])
    return assessment, result


def preserved_members(before, after):
    """New archive members may appear; earlier evidence must remain exact."""
    current = {row['path']: row for row in after}
    require(all(current.get(row['path']) == row for row in before),
            'earlier archive members changed or disappeared')


def run(packet, approved=None, extra_usage_disabled=False, rehearsal=False, placement=1, reviewed=None):
    manifest, raw = verify(packet)
    if rehearsal:
        require(manifest['mode'] == 'synthetic-rehearsal' and approved is None and not extra_usage_disabled,
                'rehearsal refuses live authority or a real profile')
    else:
        require(manifest['mode'] == 'real-harness' and approved == p.sha(raw) and extra_usage_disabled is True,
                'exact principal approval and paid-extra-usage-disabled assertion required')
    frozen_executor(packet, manifest)
    root = placement_root(packet, manifest, placement)
    require(attempts(packet) == list(range(1, placement)),
            'placement attempts must be consecutive and each is one-use')
    prior = None
    if placement > 1:
        assessment, prior = reviewed_execution(packet, manifest, raw, placement - 1, reviewed)
        status = p.decode(p.read_file(root.parent / str(placement - 1) / 'execution/status-after.stdout'))
        require(assessment['continuation_eligible'] and continuation_state(manifest, status, placement - 1),
                'the reviewed ending permits no continuation')
    else:
        require(reviewed is None, 'the initial placement has no preceding review')
    root.parent.mkdir(mode=0o700, exist_ok=True)
    root.mkdir(mode=0o700)
    out = root / 'execution'
    out.mkdir(mode=0o700)
    save(out / 'START.json', {'started_at': utc(), 'commission_sha256': p.sha(raw),
         'placement': placement, 'reviewed_prior_sha256': reviewed,
         'approved_commission': approved, 'extra_usage_disabled': extra_usage_disabled, 'retry_allowed': False})
    result = {'scope': manifest['scope'], 'placement': placement, 'started': False, 'stopping_observed': False,
              'stopping_probed': False, 'outcome': 'incomplete', 'failure': None, 'review_required': True, 'resume_allowed': False}
    reference = manifest['reference']
    audit = Path(manifest['archive']) / 'audits' / reference.split(':', 3)[1]
    interrupted = None
    try:
        status = json_command(out, 'status-before', manifest, ['status', reference])
        if placement == 1:
            require(status['data']['headline']['accepted'] == 'no' and status['data']['headline']['launched'] == 'no',
                    'packet requires the untouched local preparation')
            accepted = json_command(out, 'commission', manifest,
                                ['commission', reference, manifest['prepared_handle'], '--i-am-finished'])
            require(accepted['outcome'] == 'completed' and accepted['data']['reference'] == reference,
                    'acceptance was not established')
        else:
            require(continuation_state(manifest, status, placement - 1), 'current state permits no continuation')
            require(stopping(audit, out / 'STOPPING-BEFORE.json', placement - 1), 'current stopping is unknown')
            require(inventory(Path(manifest['archive'])) == prior['archive_inventory'],
                    'current archive differs from the reviewed preceding capture')
        receipt = json_command(out, 'receipt', manifest, ['receipt', reference, '--verify'])
        require(receipt['outcome'] == 'completed', 'receipt verification did not complete')
        inputs = packet / 'inputs/submission'
        question = p.read_file(inputs / 'question.md')
        items = {'question-file': question, 'question-body': question.split(b'\n---\n', 1)[1],
                 'arrangement': p.read_file(packet / 'inputs/arrangement.json'),
                 'arrangement-readable': p.read_file(packet / 'inputs/arrangement.md')}
        for row in manifest['submission']:
            if row['type'] == 'file' and row['path'].startswith('materials/'):
                items[row['path']] = p.read_file(inputs / row['path'])
        for index, (name, expected) in enumerate(items.items()):
            label = 'readback-%02d' % index
            read = command(out, label, [manifest['writer'], 'receipt', reference, '--read', name], 30)
            require(read['exit'] == 0 and p.read_file(out / (label + '.stdout')) == expected,
                    'accepted readback differs: ' + name)
        verify(packet)
        save(out / 'RUN-RESERVATION.json', {'at': utc(), 'reference': reference, 'placement': placement, 'max_starts': 1})
        result['started'] = True  # Reservation, not a claim that authentication/model exec occurred.
        observed_run(out, manifest, audit, placement, result)
        status = json_command(out, 'status-after', manifest, ['status', reference])
        for label, extra in [('status-default', []), ('status-details', ['--details'])]:
            form = command(out, label, [manifest['writer'], 'status', reference, *extra], 30)
            require(form['exit'] == 0, 'status form failed')
        require(result['stopping_observed'] and status['data']['runs']['held'] is False
                and status['data']['runs']['count'] == placement,
                'stopping not established; do not close or start another placement')
        result['archive_inventory'] = snapshot(Path(manifest['archive']), out / 'service-archive')
        if prior:
            preserved_members(prior['archive_inventory'], result['archive_inventory'])
        result['archive_provenance'] = 'Exact private copy of service-owned records after stopping; not independent provider evidence.'
        delivered = status['data']['headline']['delivered']
        if delivered['verified']:
            result['package_modes'] = delivered_modes(Path(delivered['location']))
            result['package_inventory'] = snapshot(Path(delivered['location']), out / 'package')
            require(delivered_modes(Path(delivered['location'])) == result['package_modes'],
                    'delivered package modes changed during capture')
        result['outcome'] = 'retained'
    except Exception as error:
        result['failure'] = repr(error)
    except BaseException as error:  # An operator interrupt still leaves its record.
        result['failure'] = repr(error)
        interrupted = error
    result['finished_at'] = utc()
    save(out / 'RESULT.json', result)
    save(out / 'EVIDENCE.json', {'members': inventory(out), 'scope': 'Private execution observations and copied service records.'})
    if interrupted is not None:
        print('Interrupted; retained what was observed: ' + str(out), file=sys.stderr)
        raise interrupted
    print('Retained service placement: ' + str(out))
    print('Outcome: ' + result['outcome'] + '; no close or later start performed.')
    return int(result['outcome'] != 'retained')


def runtime_channels(run):
    chunks = []
    for path in run.glob('runtime-*.bin'):
        match = re.fullmatch(r'runtime-([1-9][0-9]*)-(stdout|stderr|mcp|mcp-out|input|hook-in|hook-out)\.bin', path.name)
        require(match is not None, 'unknown runtime capture member')
        chunks.append((int(match[1]), match[2], path))
    chunks.sort()
    require([number for number, _, _ in chunks] == list(range(1, len(chunks) + 1)), 'runtime capture numbering gap')
    channels = {}
    for _, channel, path in chunks:
        channels.setdefault(channel, bytearray()).extend(p.read_file(path))
    return channels


def stream_observations(channels):
    """Expose per-message snapshots separately from result checkpoints; never sum them."""
    messages, results, diagnostics, initializations = {}, [], [], []
    assistant_frames = 0
    for number, line in enumerate(bytes(channels.get('stdout', b'')).splitlines(), 1):
        if not line:
            continue
        try:
            row = p.decode(line)
            if row.get('type') == 'assistant':
                assistant_frames += 1
                message = row.get('message', {})
                identity = message.get('id')
                if not isinstance(identity, str):
                    diagnostics.append({'line': number, 'reason': 'assistant message has no string id'})
                    continue
                observed = messages.setdefault(identity, {'id': identity, 'frames': 0, 'usage_snapshots': []})
                observed['frames'] += 1
                if 'usage' in message:
                    observed['usage_snapshots'].append(message['usage'])
            elif row.get('type') == 'result':
                results.append({'line': number, 'report': row})
            elif row.get('type') == 'system' and row.get('subtype') == 'init':
                initializations.append(row)
        except (ValueError, TypeError, AttributeError) as error:
            diagnostics.append({'line': number, 'bytes': len(line), 'sha256': p.sha(line), 'reason': str(error)})
    return {'assistant_frames': assistant_frames, 'assistant_messages': list(messages.values()),
            'result_reports': results, 'initializations': initializations, 'stdout_diagnostics': diagnostics,
            'scope': 'Observed stream frames and reports; overlapping message snapshots are not token totals or provider completeness.'}


def capture_selection(audit, sources):
    """Derive selected bytes from service-owned calls, independently render them.

    This is a correlation of Stewart's records, not an outside witness of every
    model action. An omitted call shared by those records can remain undetected.
    """
    records = {}
    previous = None
    logs = sorted((audit / 'log').glob('*.json'), key=lambda path: int(path.stem))
    require([int(path.stem) for path in logs] == list(range(1, len(logs) + 1)), 'ledger numbering gap')
    for path in logs:
        raw = p.read_file(path)
        row = p.decode(raw)
        require(row['body']['prev'] == previous, 'ledger digest chain differs')
        previous = p.sha(raw)
        if row['kind'] == 'entry':
            records['log/' + path.name] = row['body']
    selected, handles, prepared, consumed, allocated, deleted = {}, {}, {}, set(), set(), {}
    revision, citations, refusals, completed = 0, 0, 0, 0
    submitted = False
    runs = sorted((audit / 'runs').iterdir(), key=lambda path: int(path.name))
    require([int(path.name) for path in runs] == list(range(1, len(runs) + 1)), 'placement numbering gap')
    incoming_total, results_total, observations = 0, 0, []
    for number, run in enumerate(runs, 1):
        channels = runtime_channels(run)
        incoming = [p.decode(line) for line in bytes(channels.get('mcp', b'')).splitlines() if line]
        outgoing = [p.decode(line) for line in bytes(channels.get('mcp-out', b'')).splitlines() if line]
        wire_calls = [row for row in incoming if row.get('method') == 'tools/call']
        files = sorted(run.glob('result-*.json'), key=lambda path: int(path.stem.split('-')[1]))
        require([int(path.stem.split('-')[1]) for path in files] == list(range(1, len(files) + 1)),
                'tool-result numbering gap')
        for path in files:
            result = p.decode(p.read_file(path))['body']
            call_raw = p.read_file(run / ('call-%d.json' % result['call']))
            require(p.sha(call_raw) == result['call_sha256'] and len(call_raw) == result['call_bytes'],
                    'tool call binding differs')
            call = p.decode(call_raw)
            require(sum(row == call for row in wire_calls) == 1, 'call does not match one original MCP frame')
            operands_raw = witness.runtime.parse(call_raw).get('params').get('arguments').raw
            require(p.sha(operands_raw) == result['input_sha256'], 'tool input bytes differ')
            tool, operands = call['params']['name'], call['params']['arguments']
            require(tool == result['tool'] and call['method'] == 'tools/call', 'tool identity differs')
            reply = p.decode(result['content'][0]['text'].encode())
            matching = [row for row in outgoing if row.get('id') == call['id'] and 'result' in row]
            require(len(matching) == 1 and matching[0]['result'].get('content') == result['content']
                    and matching[0]['result'].get('isError', False) == result['is_error'],
                    'tool result differs from original outgoing MCP frame')
            require(reply['outcome'] == result['outcome'] and reply['operation'] == tool, 'tool reply differs')
            if result['outcome'] != 'completed':
                refusals += 1
                continue
            completed += 1
            require(result['replay_of'] is None, 'invocation replay needs separate review; never count it as a fresh edit')
            data = reply['data']
            log_name = result['log_record']
            repeated_delete = tool == 'delete' and data.get('already_removed') is True
            if repeated_delete:
                target = deleted.get(operands['entry'])
                require(target is not None and target[0] not in selected
                        and data['removed'] == {'id': target[0], 'version': target[1]}
                        and data['revision'] == revision and log_name in (None, target[2]),
                        'repeated deletion does not match its prior removal')
            elif tool.startswith('record_') or tool in ('replace', 'delete'):
                require(log_name in records and log_name not in consumed, 'missing or reused entry record')
                edit = records[log_name]
                revision += 1
                require(edit['revision'] == revision and edit['tool'] == tool, 'entry revision or tool differs')
                require(edit['invocation'] == {'run': number, 'tool_use_id': result['tool_use_id'], 'call': result['call']},
                        'entry invocation differs')
                if tool in ('replace', 'delete'):
                    target = handles[operands['entry']]
                    require(target[0] in selected and selected[target[0]].version == target[1], 'stale edit target')
                if tool == 'delete':
                    require(edit['action'] == 'delete' and edit['target']['id'] == target[0]
                            and edit['target']['version'] == target[1], 'deletion differs')
                    del selected[target[0]]
                    deleted[operands['entry']] = (target[0], target[1], log_name)
                else:
                    if tool == 'replace':
                        kind = selected[target[0]].kind
                        require(edit['action'] == 'replace' and (edit['id'], edit['version']) == (target[0], target[1] + 1),
                                'replacement identity differs')
                    else:
                        kind = tool
                        require(edit['action'] == 'add' and edit['id'] not in allocated and edit['version'] == 1,
                                'addition identity differs')
                        allocated.add(edit['id'])
                    payload = base64.b64decode(operands['base64'], validate=True) if 'base64' in operands else operands['text'].encode()
                    cites = [] if kind == 'record_artifact' else [answer.record_citation(c, sources) for c in operands.get('citations', [])]
                    citations += len(cites)
                    encoding = ('binary' if 'base64' in operands else 'utf-8') if kind == 'record_artifact' else None
                    require(edit['kind'] == kind and edit['label'] == operands.get('label', '')
                            and edit['citations'] == (None if kind == 'record_artifact' else cites)
                            and edit['encoding'] == encoding, 'entry fields or citations differ')
                    require(re.fullmatch(r'e[1-9][0-9]*', edit['id']) is not None
                            and type(edit['version']) is int and edit['version'] > 0, 'invalid entry identity')
                    payload_pattern = re.escape('payload/%s.v%d' % (edit['id'], edit['version'])) + r'(?:-(?:[2-9]|[1-9][0-9]+))?\.bin'
                    require(re.fullmatch(payload_pattern, edit['payload']['file']) is not None,
                            'unexpected payload path')
                    require(p.read_file(audit / edit['payload']['file']) == payload
                            and edit['payload']['sha256'] == p.sha(payload) and edit['payload']['size'] == len(payload),
                            'retained payload differs from captured call')
                    selected[edit['id']] = answer.Entry(edit['id'], edit['version'], kind, edit['label'], payload, cites, encoding)
                    handles[data['entry']] = (edit['id'], edit['version'])
                consumed.add(log_name)
            if tool == 'prepare':
                require(data['revision'] == revision and data['entry_count'] == len(selected), 'preparation selection differs')
                prepared[data['prepared']] = revision
            if tool == 'submit' and operands.get('confirm') is True:
                require(prepared.get(operands['prepared']) == revision and data['seal']['actor'] == 'auditor',
                        'submission differs from prepared selection')
                submitted = True
            require(result['revision'] == revision, 'tool-result revision differs')
        incoming_total += len(wire_calls)
        results_total += len(files)
        observations.append(dict(stream_observations(channels), placement=number,
                                 incoming_tool_calls=len(wire_calls), tool_results=len(files), revision=revision))
    require(consumed == set(records), 'not every entry effect is accounted for')
    return list(selected.values()), revision, {'completed_calls': completed, 'refused_or_failed_calls': refusals,
              'citations_checked': citations, 'auditor_submitted': submitted,
              'incoming_tool_calls': incoming_total, 'tool_results': results_total,
              'unresolved_mcp_calls': incoming_total - results_total, 'placements': observations}


def review(packet, placement=1):
    manifest, commission_raw = verify(packet)
    frozen_executor(packet, manifest)
    root = placement_root(packet, manifest, placement)
    out = root / 'execution'
    evidence_digest = execution_evidence(out)
    result = p.decode(p.read_file(out / 'RESULT.json'))
    require(result['outcome'] == 'retained' and result['stopping_observed'], 'a complete stopped capture is required')
    review_dir = root / 'review'
    review_dir.mkdir(mode=0o700)
    report = {'outcome': 'incomplete', 'scope': 'Service-owned capture correlation and independent package rendering; no intellectual quality grade.',
              'failure': None, 'package_review': None, 'human_review_required': True,
              'placement': placement, 'commission_sha256': p.sha(commission_raw),
              'execution_result_sha256': p.sha(p.read_file(out / 'RESULT.json')),
              'execution_evidence_sha256': evidence_digest}
    try:
        require(inventory(out / 'service-archive') == result['archive_inventory'], 'retained archive changed')
        if placement > 1:
            start = p.decode(p.read_file(out / 'START.json'))
            _, prior = reviewed_execution(packet, manifest, commission_raw, placement - 1, start['reviewed_prior_sha256'])
            preserved_members(prior['archive_inventory'], result['archive_inventory'])
        audit = out / 'service-archive/audits' / manifest['reference'].split(':', 3)[1]
        inputs = packet / 'inputs/submission'
        sources = {'question': p.read_file(inputs / 'question.md').split(b'\n---\n', 1)[1]}
        sources.update({row['path']: p.read_file(inputs / row['path']) for row in manifest['submission']
                        if row['type'] == 'file' and row['path'].startswith('materials/')})
        entries, revision, counts = capture_selection(audit, sources)
        status_raw = p.read_file(out / 'status-after.stdout')
        status = p.decode(status_raw)
        require(status['data']['runs']['count'] == placement and len(counts['placements']) == placement,
                'captured placement count differs')
        require(status['data']['answer'] == {'revision': revision, 'entries': len(entries)}, 'status selection differs')
        eligible = continuation_state(manifest, status, placement)
        if eligible:
            try:
                stop = p.decode(p.read_file(audit / 'runs' / str(placement) / 'runtime-stop.json'))
                run_result = p.decode(p.read_file(out / 'run.result.json'))
                eligible = deadline_established(manifest, run_result, stop, status['data']['runs']['last'], placement)
                report['continuation_basis'] = {
                    'run_command_elapsed_seconds': run_result['elapsed_seconds'],
                    'placement_timeout_seconds': manifest['placement_timeout_seconds'],
                    'service_stop_record': stop, 'deadline_established': eligible}
            except (OSError, ValueError, KeyError, TypeError) as error:
                eligible = False
                report['continuation_basis'] = {'deadline_established': False, 'diagnostic': str(error)}
        report.update(counts, revision=revision, selected_entries=len(entries),
                      continuation_eligible=eligible,
                      status_condition=status['data']['condition'], last_run=status['data']['runs']['last'],
                      reported_usage=status['data']['allowances']['usage'])
        if counts['auditor_submitted']:
            require(status['data']['seal']['actor'] == 'auditor' and status['data']['headline']['delivered']['verified'],
                    'auditor submission or verified delivery missing')
            pin = witness.write_witness(review_dir / 'WITNESS.json', entries, revision,
                  family='open-inquiry/1', writer=p.read_file(Path(manifest['writer']), limit=None, hash_only=True)[0],
                  actor='auditor', reference=manifest['reference'], status_raw=status_raw, inputs=sources,
                  provenance={'kind': 'service-owned-capture-correlation', 'description': report['scope']})
            package_review = witness.review_package(out / 'package', review_dir / 'WITNESS.json', review_dir / 'package',
                  witness_sha256=pin, archive_root=Path(manifest['archive']))
            report['package_review'] = {'outcome': package_review['outcome'], 'counts': package_review['counts'],
                                        'witness_sha256': pin}
            require(package_review['outcome'] == 'observed', 'complete package comparison failed')
            defects = package_mode_defects(result.get('package_modes'), result['package_inventory'])
            report['package_modes'] = {
                'observed_on': 'delivered package at capture, before the private copy',
                'modes': result.get('package_modes'), 'defects': defects,
                'copy_checks': 'The package witness ran its mode checks on the private copy, whose modes the '
                               'apparatus sets; they do not observe the delivered package.'}
            require(not defects, 'delivered package modes differ: ' + '; '.join(defects))
        report['outcome'] = 'observed'
    except Exception as error:
        report['failure'] = repr(error)
    report['finished_at'] = utc()
    save(review_dir / 'REVIEW.json', report)
    print(p.compact(report).decode())
    return int(report['outcome'] != 'observed')


def close(packet, reviewed, placement=1):
    manifest, commission_raw = verify(packet)
    assessment, original = reviewed_execution(packet, manifest, commission_raw, placement, reviewed)
    require(assessment['auditor_submitted'] and assessment['package_review']['outcome'] == 'observed',
            'ordinary close requires explicit review of the complete auditor-submitted package')
    frozen_executor(packet, manifest)
    require(attempts(packet) == list(range(1, placement + 1)), 'close requires the latest attempted placement')
    out = packet / 'closure'
    out.mkdir(mode=0o700)
    save(out / 'START.json', {'at': utc(), 'reviewed_review_sha256': reviewed})
    reference = manifest['reference']
    status = json_command(out, 'status-before', manifest, ['status', reference])
    require(not status['data']['runs']['held'] and status['data']['seal']['actor'] == 'auditor'
            and status['data']['headline']['delivered']['verified']
            and status['data']['runs']['count'] == placement, 'current close state differs')
    audit = Path(manifest['archive']) / 'audits' / reference.split(':', 3)[1]
    require(stopping(audit, out / 'STOPPING.json', placement), 'current stopping is unknown')
    require(inventory(Path(manifest['archive'])) == original['archive_inventory'],
            'current archive differs from reviewed capture')
    delivered = Path(status['data']['headline']['delivered']['location'])
    before = inventory(delivered)
    require(before == original['package_inventory'], 'delivered package changed since reviewed capture')
    modes = delivered_modes(delivered)
    require(modes == original.get('package_modes'), 'delivered package modes changed since reviewed capture')
    reply = json_command(out, 'close', manifest, ['close', reference])
    require(reply['outcome'] == 'completed', 'ordinary close did not complete')
    status = json_command(out, 'status-after', manifest, ['status', reference])
    require(status['data']['headline']['closed'] == 'yes', 'closure not established')
    require(inventory(delivered) == before and delivered_modes(delivered) == modes, 'package changed during close')
    snapshot(delivered, out / 'package')
    after = snapshot(Path(manifest['archive']), out / 'service-archive')
    preserved_members(original['archive_inventory'], after)
    save(out / 'RESULT.json', {'finished_at': utc(), 'outcome': 'closed', 'package_unchanged': True})
    print('Closed reviewed auditor submission; package unchanged. No model launched.')
    return 0


def prepare_rehearsal(output, writer, work):
    """Only the existing synthetic peer; no installed profile is an input."""
    output, writer, work = map(p.absolute, (output, writer, work))
    output.mkdir(mode=0o700)
    driver = witness.runtime.Driver(writer, work, selected=())
    rows = []
    for kind, scenario, placements in [('positive', 'submit', 3), ('bad-init', 'bad-init', 3),
            ('continued', 'continued-deadline', 3), ('invariance', 'continued-deadline', 3),
            ('limit', 'continued-limit', 3), ('ordinary-ending', 'no-submit', 3)]:
        fixture = driver.fixture(kind, scenario=scenario, timeout=6, placements=placements,
                                 python=str(Path(sys.executable).resolve()))
        if scenario.startswith('continued-'):
            driver.change_scenario(fixture, continued_accounts=[
                'First retained account.\n', 'Second retained account.\n', 'Third retained account.\n'],
                utf8_artifact=witness.UTF8_ARTIFACT)
        elif kind == 'positive':
            driver.change_scenario(fixture, utf8_artifact=witness.UTF8_ARTIFACT)
        reply = driver.prepare(fixture)
        preparation = output / (kind + '-preparation.json')
        save(preparation, reply)
        packet = output / kind
        digest = prepare(packet, preparation, fixture['reference'], fixture['folder'], writer,
                         mode='synthetic-rehearsal', synthetic={'script': str(driver.harness_script),
                         'scenario': str(fixture['scenario']), 'witness': str(fixture['witness'])})
        rows.append({'kind': kind, 'packet': str(packet), 'commission_sha256': digest})
    save(output / 'REHEARSAL.json', {'schema': 'stewart.claude-code.service-procedure-rehearsal/2',
         'prepared_at': utc(), 'work': str(work), 'packets': rows, 'scope': 'Synthetic peers only; no real profile or launch authority.'})
    print('Prepared six offline service-procedure comparisons: ' + str(output))
    return 0


def deadline_observed(last_run, stop, placement, limit):
    """A final deadline ends authoring; earlier deadlines interrupt it.

    INTERFACE 4.4 leaves cause null for an ending without one. The runtime
    contract assigns placement_deadline to the interrupted ending, not to
    limit_reached. Elapsed time and observed group absence are also required.
    """
    expected = ('interrupted', 'placement_deadline') if placement < limit else ('limit_reached', None)
    return (last_run['number'] == placement and (last_run['ending'], last_run['cause']) == expected
            and stop['deadline_ms'] > 0 and stop['elapsed_ms'] >= stop['deadline_ms']
            and stop['groups_gone'] is True)


def rehearse(suite, approved_digest):
    """Run only frozen fake peers, including refusal controls, without live authority."""
    raw = p.read_file(suite / 'REHEARSAL.json')
    plan = p.decode(raw)
    require(p.sha(raw) == approved_digest
            and plan['schema'] == 'stewart.claude-code.service-procedure-rehearsal/2',
            'rehearsal inventory differs')
    kinds = ['positive', 'bad-init', 'continued', 'invariance', 'limit', 'ordinary-ending']
    require([row['kind'] for row in plan['packets']] == kinds, 'rehearsal comparisons differ')
    manifests = {}
    for row in plan['packets']:
        packet = p.absolute(row['packet'])
        require(packet == suite / row['kind'], 'rehearsal packet is outside the suite')
        manifest, commission_raw = verify(packet)
        require(manifest['mode'] == 'synthetic-rehearsal' and p.sha(commission_raw) == row['commission_sha256'],
                'rehearsal requires unchanged synthetic packets')
        manifests[row['kind']] = manifest
    frozen_executor(suite / 'positive', manifests['positive'])
    host = suite / 'host'
    host.mkdir(mode=0o700)  # Consumed even if a later comparison fails.
    save(host / 'START.json', {'at': utc(), 'rehearsal_sha256': approved_digest,
         'scope': 'Synthetic-only native rehearsal; no real profile, credential or provider.'})
    report = {'outcome': 'incomplete', 'failure': None, 'checks': [], 'placements': [], 'retained_unsubmitted': []}

    def check(label, condition):
        report['checks'].append({'label': label, 'passed': bool(condition)})
        require(condition, 'rehearsal comparison failed: ' + label)

    def invoke(kind, label, action, placement, *extra):
        packet = suite / kind
        manifest = manifests[kind]
        return command(host, kind + '-' + label,
            [manifest['python'], '-I', '-B', str(packet / 'sources/claude-code/service_check.py'),
             action, '--packet', str(packet), '--placement', str(placement), *extra], 180)

    def refusal(kind, label, placement, digest, reason):
        packet = suite / kind
        manifest = manifests[kind]
        scenario = p.decode(p.read_file(Path(manifest['synthetic']['scenario'])))
        marker = Path(scenario['marker'])
        before = (attempts(packet), p.read_file(marker), inventory(Path(manifest['archive'])))
        result = invoke(kind, label, 'run-rehearsal', placement, '--reviewed-review', digest)
        check(kind + '.' + label + '.specific-refusal', result['exit'] != 0
              and reason.encode() in p.read_file(host / (kind + '-' + label + '.stderr')))
        after = (attempts(packet), p.read_file(marker), inventory(Path(manifest['archive'])))
        check(kind + '.' + label + '.no-start-or-mutation', before == after)

    try:
        for kind in kinds:
            packet, manifest = suite / kind, manifests[kind]
            continued = kind in ('continued', 'invariance', 'limit')
            count, digest = (3 if continued else 1), None
            for placement in range(1, count + 1):
                extra = ['--reviewed-review', digest] if digest else []
                result = invoke(kind, 'run-%d' % placement, 'run-rehearsal', placement, *extra)
                check(kind + '.run-%d.retained' % placement, result['exit'] == 0)
                result = invoke(kind, 'review-%d' % placement, 'review', placement)
                check(kind + '.review-%d.observed' % placement, result['exit'] == 0)
                root = packet / 'placements' / str(placement)
                review_raw = p.read_file(root / 'review/REVIEW.json')
                assessment = p.decode(review_raw)
                digest = p.sha(review_raw)
                report['placements'].append({'kind': kind, 'placement': placement, 'review_sha256': digest,
                    'condition': assessment['status_condition'], 'revision': assessment['revision'],
                    'entries': assessment['selected_entries'], 'usage': assessment['reported_usage']})
                if continued:
                    expected = 'interrupted' if placement < 3 else ('limit_reached' if kind == 'limit' else 'delivered_open')
                    check(kind + '.%d.condition' % placement, assessment['status_condition'] == expected)
                    revision = placement + int(placement == 3 and kind != 'limit')
                    check(kind + '.%d.preserved-selection' % placement,
                          assessment['revision'] == assessment['selected_entries'] == revision)
                    if placement < 3 or kind == 'limit':
                        audit = root / 'execution/service-archive/audits' / manifest['reference'].split(':', 3)[1]
                        stop = p.decode(p.read_file(audit / 'runs' / str(placement) / 'runtime-stop.json'))
                        check(kind + '.%d.deadline' % placement,
                              deadline_observed(assessment['last_run'], stop, placement, manifest['max_service_starts']))
                    expected_usage = dict(witness.runtime.CHECKPOINTS[0]['usage'],
                                          harness_turns=witness.runtime.CHECKPOINTS[0]['num_turns'])
                    usage = assessment['reported_usage']
                    check(kind + '.%d.checkpoint-not-message-sum' % placement,
                          usage['reported_main_loop'] == expected_usage and usage['reported_placements'] == 1
                          and usage['unknown_intervals'] == placement and usage['stopped'] == placement)
                    for observed in assessment['placements']:
                        check(kind + '.%d.stream-%d' % (placement, observed['placement']),
                              observed['assistant_frames'] > len(observed['assistant_messages']) > 0
                              and len(observed['result_reports']) == int(observed['placement'] == 1)
                              and not observed['stdout_diagnostics'])
                    if placement == 1:
                        refusal(kind, 'wrong-review', 2, '0' * 64, 'explicit review')
                        refusal(kind, 'skip-placement', 3, digest, 'consecutive')
                elif kind == 'positive':
                    check('positive.selection', assessment['revision'] == assessment['selected_entries'] == 2)
                elif kind == 'bad-init':
                    check('bad-init.no-entry-or-submission', assessment['revision'] == 0 and not assessment['auditor_submitted'])
                    check('bad-init.protocol-stop-with-spare-starts', assessment['status_condition'] == 'interrupted'
                          and assessment['last_run']['cause'] == 'protocol_anomaly' and not assessment['continuation_eligible'])
                else:
                    check('ordinary-ending.disposition', assessment['status_condition'] == 'ended_unsubmitted'
                          and not assessment['continuation_eligible'])
            # Without this, an unsubmitted positive case would take the refusal
            # branch below and the suite would still end observed.
            check(kind + '.auditor-submitted-as-expected',
                  assessment['auditor_submitted'] is (kind in ('positive', 'continued', 'invariance')))
            if assessment['auditor_submitted']:
                check(kind + '.package', assessment['package_review']['outcome'] == 'observed')
                check(kind + '.delivered-modes', assessment['package_modes']['defects'] == [])
                scenario = p.decode(p.read_file(Path(manifest['synthetic']['scenario'])))
                package = packet / 'placements' / str(count) / 'execution/package'
                answer_data = p.decode(p.read_file(package / 'answer.json'))
                accounts = scenario['continued_accounts'] if continued else [witness.runtime.ACCOUNT]
                check(kind + '.independent-package-accounts',
                      [entry['text'] for entry in answer_data['entries'] if entry['kind'] == 'record_account'] == accounts)
                artifact = answer_data['entries'][-1]
                check(kind + '.independent-package-artifact', artifact['encoding'] == 'utf-8'
                      and artifact['label'] == scenario['utf8_artifact']['label']
                      and p.read_file(package / ('artifact-e%d.bin' % (len(accounts) + 1)))
                      == scenario['utf8_artifact']['text'].encode())
                if count < manifest['max_service_starts']:
                    refusal(kind, 'sealed-refusal', count + 1, digest, 'permits no continuation')
                result = invoke(kind, 'close', 'close', count, '--reviewed-review', digest)
                check(kind + '.closed-preserved', result['exit'] == 0
                      and p.decode(p.read_file(packet / 'closure/RESULT.json'))['package_unchanged'])
            else:
                refusal(kind, 'ended-refusal', count + 1, digest,
                        'commissioned starts' if count == manifest['max_service_starts'] else 'permits no continuation')
                report['retained_unsubmitted'].append({'kind': kind, 'reference': manifest['reference'],
                    'disposition': 'Stopped synthetic control retained for independent review; no further start or automatic close.'})
            peer = Path(manifest['synthetic']['witness'])
            if kind == 'bad-init':
                events = [p.decode(line) for line in p.read_file(peer / 'harness.jsonl').splitlines()]
                wrong = [row for row in events if row['event'] == 'output'
                         and row['value'].get('subtype') == 'init'
                         and row['value'].get('model') == 'deliberately-wrong-model']
                transmitted = {row['sha256'] for row in events if row['event'] == 'output-transmitted'}
                check('bad-init.independent-firing-witness', len(wrong) == 1
                      and p.sha(bytes.fromhex(wrong[0]['raw_hex'])) in transmitted
                      and any(row['event'] == 'rpc-send' and row['value'].get('params', {}).get('name')
                              == 'record_account' for row in events))
            snapshot(peer, host / ('peer-' + kind))
        report['outcome'] = 'observed'
    except Exception as error:
        report['failure'] = repr(error)
    report['counts'] = {'passed': sum(row['passed'] for row in report['checks']),
                        'failed': sum(not row['passed'] for row in report['checks']),
                        'placements': len(report['placements'])}
    report['finished_at'] = utc()
    save(host / 'RESULT.json', report)
    save(host / 'EVIDENCE.json', {'members': inventory(host)})
    print(p.compact({'outcome': report['outcome'], 'failure': report['failure'], 'counts': report['counts'],
                     'retained': str(host)}).decode())
    return int(report['outcome'] != 'observed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prep = commands.add_parser('prepare', help='freeze one existing local preparation and its start limits; launches nothing')
    for name in ('output', 'preparation', 'folder', 'writer'):
        prep.add_argument('--' + name, type=p.absolute, required=True)
    prep.add_argument('--reference', required=True)
    rehearsal_parser = commands.add_parser('prepare-rehearsal', help='prepare six synthetic comparisons; no real harness')
    for name in ('output', 'writer', 'work'):
        rehearsal_parser.add_argument('--' + name, type=p.absolute, required=True)
    native = commands.add_parser('rehearse', help='execute the frozen synthetic suite once; no real harness')
    native.add_argument('--suite', type=p.absolute, required=True)
    native.add_argument('--rehearsal-sha256', required=True)
    for name in ('inspect', 'run', 'run-rehearsal', 'review', 'close'):
        command_parser = commands.add_parser(name)
        command_parser.add_argument('--packet', type=p.absolute, required=True)
        if name != 'inspect':
            command_parser.add_argument('--placement', type=int, required=True)
        if name in ('run', 'run-rehearsal'):
            command_parser.add_argument('--reviewed-review', help='required for continuation: exact preceding REVIEW.json SHA-256')
        if name == 'run':
            command_parser.add_argument('--approved-commission', required=True)
            command_parser.add_argument('--extra-usage-disabled', action='store_true')
        if name == 'close':
            command_parser.add_argument('--reviewed-review', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        print('Commission SHA-256: ' + prepare(args.output, args.preparation, args.reference, args.folder, args.writer))
        return 0
    if args.action == 'prepare-rehearsal':
        return prepare_rehearsal(args.output, args.writer, args.work)
    if args.action == 'rehearse':
        return rehearse(args.suite, args.rehearsal_sha256)
    if args.action == 'inspect':
        manifest, raw = verify(args.packet)
        print(p.compact({'commission_sha256': p.sha(raw), 'commission': manifest}).decode())
        return 0
    if args.action == 'review':
        return review(args.packet, args.placement)
    if args.action == 'close':
        return close(args.packet, args.reviewed_review, args.placement)
    return run(args.packet, getattr(args, 'approved_commission', None),
               getattr(args, 'extra_usage_disabled', False), args.action == 'run-rehearsal',
               args.placement, args.reviewed_review)


if __name__ == '__main__':
    os.umask(0o077)
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit('Service comparison refused: ' + str(error))
