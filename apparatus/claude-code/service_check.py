"""One prepared native service placement, with explicit authority and retained evidence.

Preparation and review launch no Claude process. Run consumes its packet once;
it never retries, continues, closes or advances to another audit automatically.
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


def profile_from(preparation):
    reply = p.decode(p.read_file(Path(preparation)))
    require(reply['operation'] == 'prepare' and reply['outcome'] == 'completed',
            'a completed local preparation is required')
    settings = reply['data']['settings']
    require(settings['family'] == 'open-inquiry' and settings['runtime']['kind'] == 'claude-code/1',
            'this procedure covers runtime open inquiry only')
    require(settings['limits']['max_placements'] == 1, 'this procedure permits one placement only')
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
    require(type(seconds) is int and 1 <= seconds <= 600, 'placement exceeds this procedure bound')
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
    manifest = {'schema': 'stewart.claude-code.service-commission/1', 'mode': mode,
                'prepared_at': utc(), 'reference': reference, 'folder': str(folder),
                'archive': str(archive), 'writer': str(writer), 'python': str(Path(sys.executable).resolve()),
                'prepared_handle': reply['data']['prepared'], 'model': settings['model'],
                'placement_timeout_seconds': seconds, 'service_command_timeout_seconds': seconds + 15,
                'max_service_starts': 1, 'max_authentication_invocations': 1, 'max_model_invocations': 1,
                'environment': ENV, 'cwd': '/private/tmp', 'submission': inventory(folder),
                'bindings': [{'path': str(path), 'sha256': p.read_file(path, limit=None, hash_only=True)[0]}
                             for path in dict.fromkeys(paths)],
                'scope': 'One prepared service placement; retain status, stopped archive and package for review. No automatic close, continuation or replacement.',
                'authority': None, 'synthetic': synthetic,
                'extra_usage': 'Included subscription use only; paid extra usage must be disabled.',
                'witness_scope': 'Outside input/package snapshots and group probes; private service captures retain service-owned provenance.'}
    save(output / 'COMMISSION.json', manifest)
    return p.sha(p.read_file(output / 'COMMISSION.json'))


def verify(packet):
    packet = p.absolute(packet)
    raw = p.read_file(packet / 'COMMISSION.json')
    value = p.decode(raw)
    require(value['schema'] == 'stewart.claude-code.service-commission/1', 'unknown commission schema')
    require(value['mode'] in ('real-harness', 'synthetic-rehearsal')
            and value['max_service_starts'] == value['max_authentication_invocations'] == value['max_model_invocations'] == 1,
            'commission is outside one-placement scope')
    require(value['environment'] == ENV and value['cwd'] == '/private/tmp', 'manager environment changed')
    for row in value['bindings']:
        require(p.read_file(Path(row['path']), limit=None, hash_only=True)[0] == row['sha256'],
                'bound input changed: ' + row['path'])
    require(inventory(Path(value['folder'])) == value['submission'], 'submission membership or bytes changed')
    reply, settings, profile = profile_from(packet / 'inputs/prepare.json')
    require(value['prepared_handle'] == reply['data']['prepared']
            and value['model'] == settings['model']
            and value['placement_timeout_seconds'] == settings['limits']['placement_timeout_seconds']
            and 1 <= value['placement_timeout_seconds'] <= 600
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
    reply = p.decode(p.read_file(directory / (label + '.stdout')))
    require(result['exit'] in allowed, label + ': unexpected exit ' + str(result['exit']))
    return reply


def stopping(audit, output):
    record = {'service_records': {}, 'observations': [], 'diagnostics': [],
              'scope': 'Copied service-owned group identities; independent read-only absence probes after run return.'}
    for role in ('auth', 'model'):
        try:
            raw = p.read_file(audit / 'runs/1' / ('process-' + role + '.json'))
            value = p.decode(raw)
            record['service_records'][role] = {'raw_base64': base64.b64encode(raw).decode(), 'sha256': p.sha(raw)}
            require(value['schema'] == 'stewart.claude-code.process/1' and value['role'] == role
                    and type(value['group']) is int and value['group'] > 1, 'invalid group record')
            before = time.monotonic_ns()
            observation = witness.runtime.group_observation(value['group'])
            record['observations'].append({'role': role, 'group': value['group'], 'observation': observation,
                                           'started_monotonic_ns': before, 'finished_monotonic_ns': time.monotonic_ns()})
        except (OSError, ValueError, KeyError, TypeError) as error:
            record['diagnostics'].append(str(error))
    record['observed'] = not record['diagnostics'] and len(record['observations']) == 2 and all(
        row['observation'] == 'absent' for row in record['observations'])
    save(output, record)
    return record['observed']


def run(packet, approved=None, extra_usage_disabled=False, rehearsal=False):
    manifest, raw = verify(packet)
    if rehearsal:
        require(manifest['mode'] == 'synthetic-rehearsal' and approved is None and not extra_usage_disabled,
                'rehearsal refuses live authority or a real profile')
    else:
        require(manifest['mode'] == 'real-harness' and approved == p.sha(raw) and extra_usage_disabled is True,
                'exact principal approval and paid-extra-usage-disabled assertion required')
    frozen_executor(packet, manifest)
    out = packet / 'execution'
    out.mkdir(mode=0o700)
    save(out / 'START.json', {'started_at': utc(), 'commission_sha256': p.sha(raw),
         'approved_commission': approved, 'extra_usage_disabled': extra_usage_disabled, 'resume_allowed': False})
    result = {'scope': manifest['scope'], 'started': False, 'stopping_observed': False,
              'outcome': 'incomplete', 'failure': None, 'review_required': True, 'resume_allowed': False}
    reference = manifest['reference']
    audit = Path(manifest['archive']) / 'audits' / reference.split(':', 3)[1]
    try:
        status = json_command(out, 'status-before', manifest, ['status', reference])
        require(status['data']['headline']['accepted'] == 'no' and status['data']['headline']['launched'] == 'no',
                'packet requires the untouched local preparation')
        accepted = json_command(out, 'commission', manifest,
                                ['commission', reference, manifest['prepared_handle'], '--i-am-finished'])
        require(accepted['outcome'] == 'completed' and accepted['data']['reference'] == reference,
                'acceptance was not established')
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
        save(out / 'RUN-RESERVATION.json', {'at': utc(), 'reference': reference, 'max_starts': 1})
        result['started'] = True  # Reservation, not a claim that authentication/model exec occurred.
        result['run_reply'] = json_command(out, 'run', manifest, ['run', reference], allowed=(0, 3, 4, 5))
        result['stopping_observed'] = stopping(audit, out / 'STOPPING.json')
        status = json_command(out, 'status-after', manifest, ['status', reference])
        for label, extra in [('status-default', []), ('status-details', ['--details'])]:
            form = command(out, label, [manifest['writer'], 'status', reference, *extra], 30)
            require(form['exit'] == 0, 'status form failed')
        require(result['stopping_observed'] and not status['data']['runs']['held'],
                'stopping not established; do not close or start another placement')
        result['archive_inventory'] = snapshot(Path(manifest['archive']), out / 'service-archive')
        result['archive_provenance'] = 'Exact private copy of service-owned records after stopping; not independent provider evidence.'
        delivered = status['data']['headline']['delivered']
        if delivered['verified']:
            result['package_inventory'] = snapshot(Path(delivered['location']), out / 'package')
        result['outcome'] = 'retained'
    except Exception as error:
        result['failure'] = repr(error)
    result['finished_at'] = utc()
    save(out / 'RESULT.json', result)
    save(out / 'EVIDENCE.json', {'members': inventory(out), 'scope': 'Private execution observations and copied service records.'})
    print('Retained service placement: ' + str(out))
    print('Outcome: ' + result['outcome'] + '; no close or later start performed.')
    return int(result['outcome'] != 'retained')


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
    run = audit / 'runs/1'
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
            require(edit['invocation'] == {'run': 1, 'tool_use_id': result['tool_use_id'], 'call': result['call']},
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
    require(consumed == set(records), 'not every entry effect is accounted for')
    return list(selected.values()), revision, {'completed_calls': completed, 'refused_or_failed_calls': refusals,
              'citations_checked': citations, 'auditor_submitted': submitted,
              'incoming_tool_calls': len(wire_calls), 'tool_results': len(files),
              'unresolved_mcp_calls': len(wire_calls) - len(files)}


def review(packet):
    manifest, commission_raw = verify(packet)
    frozen_executor(packet, manifest)
    out = packet / 'execution'
    evidence_digest = execution_evidence(out)
    result = p.decode(p.read_file(out / 'RESULT.json'))
    require(result['outcome'] == 'retained' and result['stopping_observed'], 'a complete stopped capture is required')
    review_dir = packet / 'review'
    review_dir.mkdir(mode=0o700)
    report = {'outcome': 'incomplete', 'scope': 'Service-owned capture correlation and independent package rendering; no intellectual quality grade.',
              'failure': None, 'package_review': None, 'human_review_required': True,
              'commission_sha256': p.sha(commission_raw),
              'execution_result_sha256': p.sha(p.read_file(out / 'RESULT.json')),
              'execution_evidence_sha256': evidence_digest}
    try:
        require(inventory(out / 'service-archive') == result['archive_inventory'], 'retained archive changed')
        audit = out / 'service-archive/audits' / manifest['reference'].split(':', 3)[1]
        inputs = packet / 'inputs/submission'
        sources = {'question': p.read_file(inputs / 'question.md').split(b'\n---\n', 1)[1]}
        sources.update({row['path']: p.read_file(inputs / row['path']) for row in manifest['submission']
                        if row['type'] == 'file' and row['path'].startswith('materials/')})
        entries, revision, counts = capture_selection(audit, sources)
        status_raw = p.read_file(out / 'status-after.stdout')
        status = p.decode(status_raw)
        require(status['data']['answer'] == {'revision': revision, 'entries': len(entries)}, 'status selection differs')
        report.update(counts, revision=revision, selected_entries=len(entries))
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
        report['outcome'] = 'observed'
    except Exception as error:
        report['failure'] = repr(error)
    report['finished_at'] = utc()
    save(review_dir / 'REVIEW.json', report)
    print(p.compact(report).decode())
    return int(report['outcome'] != 'observed')


def close(packet, reviewed):
    manifest, commission_raw = verify(packet)
    raw = p.read_file(packet / 'review/REVIEW.json')
    assessment = p.decode(raw)
    require(reviewed == p.sha(raw) and assessment['outcome'] == 'observed'
            and assessment['auditor_submitted'] and assessment['package_review']['outcome'] == 'observed',
            'ordinary close requires explicit review of the complete auditor-submitted package')
    frozen_executor(packet, manifest)
    require(assessment['commission_sha256'] == p.sha(commission_raw)
            and assessment['execution_result_sha256'] == p.sha(p.read_file(packet / 'execution/RESULT.json'))
            and assessment['execution_evidence_sha256'] == execution_evidence(packet / 'execution'),
            'reviewed execution evidence or commission changed; close refused')
    out = packet / 'closure'
    out.mkdir(mode=0o700)
    save(out / 'START.json', {'at': utc(), 'reviewed_review_sha256': reviewed})
    reference = manifest['reference']
    status = json_command(out, 'status-before', manifest, ['status', reference])
    require(not status['data']['runs']['held'] and status['data']['seal']['actor'] == 'auditor'
            and status['data']['headline']['delivered']['verified'], 'current close state differs')
    audit = Path(manifest['archive']) / 'audits' / reference.split(':', 3)[1]
    require(stopping(audit, out / 'STOPPING.json'), 'current stopping is unknown')
    delivered = Path(status['data']['headline']['delivered']['location'])
    before = inventory(delivered)
    original = p.decode(p.read_file(packet / 'execution/RESULT.json'))
    require(before == original['package_inventory'], 'delivered package changed since reviewed capture')
    reply = json_command(out, 'close', manifest, ['close', reference])
    require(reply['outcome'] == 'completed', 'ordinary close did not complete')
    status = json_command(out, 'status-after', manifest, ['status', reference])
    require(status['data']['headline']['closed'] == 'yes', 'closure not established')
    require(inventory(delivered) == before, 'package changed during close')
    snapshot(delivered, out / 'package')
    snapshot(Path(manifest['archive']), out / 'service-archive')
    save(out / 'RESULT.json', {'finished_at': utc(), 'outcome': 'closed', 'package_unchanged': True})
    print('Closed reviewed auditor submission; package unchanged. No model launched.')
    return 0


def prepare_rehearsal(output, writer, work):
    """Only the existing synthetic peer; no installed profile is an input."""
    output, writer, work = map(p.absolute, (output, writer, work))
    output.mkdir(mode=0o700)
    driver = witness.runtime.Driver(writer, work, selected=())
    rows = []
    for kind, scenario in [('positive', 'submit'), ('bad-init', 'bad-init'), ('invariance', 'submit')]:
        fixture = driver.fixture(kind, scenario=scenario, timeout=15, placements=1,
                                 python=str(Path(sys.executable).resolve()))
        if kind != 'bad-init':
            driver.change_scenario(fixture, utf8_artifact=witness.UTF8_ARTIFACT)
        reply = driver.prepare(fixture)
        preparation = output / (kind + '-preparation.json')
        save(preparation, reply)
        packet = output / kind
        digest = prepare(packet, preparation, fixture['reference'], fixture['folder'], writer,
                         mode='synthetic-rehearsal', synthetic={'script': str(driver.harness_script),
                         'scenario': str(fixture['scenario']), 'witness': str(fixture['witness'])})
        rows.append({'kind': kind, 'packet': str(packet), 'commission_sha256': digest})
    save(output / 'REHEARSAL.json', {'schema': 'stewart.claude-code.service-procedure-rehearsal/1',
         'prepared_at': utc(), 'work': str(work), 'packets': rows, 'scope': 'Synthetic peers only; no real profile or launch authority.'})
    print('Prepared three offline service-procedure comparisons: ' + str(output))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prep = commands.add_parser('prepare', help='freeze one existing local preparation; launches nothing')
    for name in ('output', 'preparation', 'folder', 'writer'):
        prep.add_argument('--' + name, type=p.absolute, required=True)
    prep.add_argument('--reference', required=True)
    rehearsal_parser = commands.add_parser('prepare-rehearsal', help='prepare three existing synthetic fixtures; no real harness')
    for name in ('output', 'writer', 'work'):
        rehearsal_parser.add_argument('--' + name, type=p.absolute, required=True)
    for name in ('inspect', 'run', 'run-rehearsal', 'review', 'close'):
        command_parser = commands.add_parser(name)
        command_parser.add_argument('--packet', type=p.absolute, required=True)
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
    if args.action == 'inspect':
        manifest, raw = verify(args.packet)
        print(p.compact({'commission_sha256': p.sha(raw), 'commission': manifest}).decode())
        return 0
    if args.action == 'review':
        return review(args.packet)
    if args.action == 'close':
        return close(args.packet, args.reviewed_review)
    return run(args.packet, getattr(args, 'approved_commission', None),
               getattr(args, 'extra_usage_disabled', False), args.action == 'run-rehearsal')


if __name__ == '__main__':
    os.umask(0o077)
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit('Service comparison refused: ' + str(error))
