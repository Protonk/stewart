"""One later placement of one retained audit, bound to its observed prior state.

Run inside the audit's retained container. No placement record is made in the
audit until a credential-free preflight has matched the packet, the exact writer
and a fresh status against the retained records, and the supplied credential has
matched the original placement's marker. Then exactly one placement is started,
observed, reviewed with every earlier placement and exported as the next
immutable snapshot.

Every invocation claims a new attempt folder first. Another attempt at the same
placement is admitted only while every earlier one recorded that `stewart run`
was never spawned; an attempt that may have started the placement, or whose
record is missing, blocks it for good. What actually prevents a second start is
the service's own record: the fresh status must show exactly the placements the
packet names as prior. Nothing here retries, replaces or continues automatically.
"""
import argparse
import os
from pathlib import Path
import platform
import resource
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CONTINUED, MAX_PLACEMENTS, credential_bytes, digest, file_hash, identifier,
    read_file, require, scan_tree, source_hash, strict_json, validate_continuation, write_json)
from batch import (Audit, allowance_facts, check_credential, continued_match, event, locked_export,
    next_snapshot, rehearsal_script, stop_reason)
from session import failure_details, numbered_records, placement_folder
from control import safe_state
from verify import Evidence, inventory_from_evidence


# Reviewer controls a fixed control's evidence cannot carry: nothing was
# recorded before continue-cap's interruption, and only the reminder controls
# are signalled at a witnessed point. Each control still fires in another script.
NO_SUBJECT = {'continue-cap': ['changed-interruption-timing', 'changed-interruption-witness', 'repeated-effect-across-placements'],
              'continue-entries': ['changed-interruption-timing', 'changed-interruption-witness'],
              'reminder-spent': [], 'reminder-spent-unheld': [], 'reminder-spent-submits': [], 'reminder-unused': []}


class Refused(ValueError):
    """No attempt folder was made; earlier records are unchanged."""


def claim(out, packet):
    """This attempt's record folder, made exclusively before anything else.

    Attempts are numbered from 1. A new one is admitted only when every earlier
    attempt at the placement holds a result saying the run command was never
    spawned. Anything else is left for a person to inspect.
    """
    audit, placement = packet.get('audit'), packet.get('placement')
    if not (identifier(audit) and type(placement) is int and 2 <= placement <= MAX_PLACEMENTS):
        raise Refused('the packet names no valid audit placement')
    folder = out/'continuations'/f'{audit}-p{placement}'
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    names = [path.name for path in folder.iterdir()]
    earlier = [f'attempt-{k}' for k in range(1, len(names) + 1)]
    # Compared as a set of numbered names: attempt-10 follows attempt-9.
    if sorted(names) != sorted(earlier):
        raise Refused('unknown members beside the attempts of this placement')
    for name in earlier:
        try:
            record = strict_json(read_file(folder/name/'RESULT.json'))
            settled = (record['schema'] == 'stewart.c10-continuation-session/1' and record['audit'] == audit
                       and record['placement'] == placement and record['placement_state'] == 'not_started')
        except (OSError, ValueError, KeyError, TypeError):
            settled = False
        if not settled:
            raise Refused(f'{name} of this placement may have started it or left no readable result; '
                          'inspect its retained records and the audit status')
    attempt = len(earlier) + 1
    (folder/f'attempt-{attempt}').mkdir(mode=0o700)
    return folder/f'attempt-{attempt}', attempt


def log_head(audit):
    """The newest record of the audit's log, by name and bytes."""
    folder = audit.log_folder()
    numbers = sorted(int(path.stem) for path in folder.iterdir() if path.name == f'{path.stem}.json' and path.stem.isdigit())
    require(numbers and numbers == list(range(1, len(numbers) + 1))
            and len(numbers) == len(list(folder.iterdir())), 'log names are not exactly 1..N')
    return {'record': f'log/{numbers[-1]}.json', 'sha256': digest(read_file(folder/f'{numbers[-1]}.json'))}


def prior_members(root, folder):
    """Compare the newest exported snapshot with the private originals it was copied from.

    Every regular member of that snapshot must still be present with identical
    bytes: a later placement adds records and rewrites none.
    """
    snapshots = sorted(folder.iterdir(), reverse=True) if folder.exists() else []
    for path in snapshots:
        meta = strict_json(read_file(path/'EXPORT.json'))
        if meta['outcome'] != 'exported':
            continue
        e = Evidence(path/'work.tar', meta['archive']['sha256'])
        try:
            missing = sorted(name for name in e.names if not (root/name).is_file() or (root/name).is_symlink())
            changed = sorted(name for name in e.names - set(missing) if file_hash(root/name) != digest(e.read(name)))
        finally:
            e.close()
        return {'snapshot': path.name, 'archive_sha256': meta['archive']['sha256'], 'members': len(e.names),
                'missing': len(missing), 'changed': len(changed), 'examples': (missing + changed)[:20],
                'unchanged': not missing and not changed}
    # Nothing was ever exported, so there is nothing to compare; this is not a finding of no change.
    return {'snapshot': None, 'archive_sha256': None, 'members': 0, 'missing': None, 'changed': None,
            'examples': [], 'unchanged': None}


def preflight(binary, private, packet, mode, result, stage, *, local):
    """Everything that can be established without the credential."""
    bound, name = packet['bindings'], packet['audit']
    stage('preflight.binary_binding')
    require(file_hash(binary) == bound['binary_sha256'], 'binary differs from the packet')
    stage('preflight.apparatus_binding')
    require(source_hash() == bound['apparatus_sha256'], 'apparatus source differs from the packet')
    stage('preflight.audit_binding')
    root = private/name
    audit = Audit.attach(binary, root, mode=mode, stop_after_seconds=packet['stop_after_seconds'], local=local)
    binding = strict_json(read_file(audit.evidence/'binding.json'))
    commission = binding['commission']
    require(binding['binary_sha256'] == bound['binary_sha256'], "binary differs from the audit's recorded writer")
    require(audit.ref == packet['reference'], 'operator reference differs from the packet')
    require(commission['model'] == packet['model'] and commission['limits'] == packet['limits']
            and commission['endpoint'] == packet['endpoint'], "packet differs from the audit's commission")
    require(commission['schema'] != 'stewart.interruption-commission/1'
            or packet['placement'] <= commission['max_placements'], "placement exceeds the audit's commissioned ceiling")
    stage('preflight.input_witness')
    require(inventory_from_evidence(Evidence(root), 'evidence/input-witness/') == binding['input_inventory'],
            'input witness changed')
    stage('preflight.credential_marker')
    marker = private.parent/'credential-check'/(name + '.json')
    require(set(strict_json(read_file(marker))) == {'nonce', 'tag'}, 'original credential marker is unreadable')
    stage('preflight.status')
    status, _, _ = audit.command('status-before-placement', 'status', audit.ref)
    data, prior = status['data'], packet['prior']
    runs, head, allowances = data['runs'], data['headline'], data['allowances']
    state = safe_state(status)
    newest = log_head(audit)
    # Recorded before any comparison, so a refusal still says what was found.
    result['prior_observed'] = {
        'state': {key: state[key] for key in ['condition', 'ending', 'cause', 'authoring', 'seal_state', 'closed']},
        'accepted': head['accepted'] == 'yes', 'launched': head['launched'] == 'yes',
        'lock_held': runs['held'] if type(runs['held']) is bool else 'unknown',
        'runs': runs['count'] if type(runs['count']) is int else 'unknown',
        'allowances': state['allowances'], 'log_head': newest,
        'bound_by_packet': {'usage': prior['usage'] is not None, 'log_head': prior['log_head_sha256'] is not None},
        'allowance_facts': None}
    # The service's own count of placements is what prevents a second start of
    # this one, whatever the attempt records say; it is compared first.
    stage('preflight.prior_runs')
    require(type(runs['count']) is int and runs['count'] == runs['last']['number'] == prior['runs'],
            'placement count differs from the packet')
    stage('preflight.audit_state')
    require(head['accepted'] == 'yes' and head['launched'] == 'yes'
            and head['authoring'] == {'state': 'open', 'ended_by': None}
            and head['seal'] == {'state': 'absent', 'actor': None} and head['closed'] == 'no'
            and data['closure'] is None and data['condition'] == 'interrupted' and runs['held'] is False,
            'audit is not accepted, launched, open, unsealed, unclosed and unheld')
    stage('preflight.prior_ending')
    require(runs['last']['ending'] == prior['last_ending'] and runs['last']['cause'] == prior['last_cause'],
            'last ending or cause differs from the packet')
    stage('preflight.prior_usage')
    require(all(type(allowances[key][part]) is int for key in packet['limits'] for part in ['used', 'limit'])
            and {key: allowances[key]['limit'] for key in packet['limits']} == packet['limits'],
            'cumulative usage or limits cannot be established')
    # INTERFACE 6.3 and 6.4 as plain numbers; the commission, not this launcher, decides on them.
    result['prior_observed']['allowance_facts'] = allowance_facts(allowances, packet['interruption'])
    require(prior['usage'] is None or {key: allowances[key]['used'] for key in packet['limits']} == prior['usage'],
            'cumulative usage differs from the packet')
    stage('preflight.prior_log_head')
    require(prior['log_head_sha256'] is None or newest['sha256'] == prior['log_head_sha256'],
            'newest log record differs from the packet')
    script = None
    if mode == 'rehearse':
        # The fake has a script, and an expected ending, only for the fixed controls.
        stage('preflight.rehearsal_inventory')
        script = rehearsal_script(commission, binding['run'])
        require(script in CONTINUED and packet['placement'] <= len(CONTINUED[script]['endings'])
                and packet['interruption'] is None, 'rehearsal continuation is outside the fixed controls')
    # Launcher records of this placement without a service record of it: an
    # earlier attempt stopped between its intent and its spawn. Left to a person.
    stage('preflight.placement_already_launched')
    require(not placement_folder(audit.evidence, packet['placement']).exists(), 'this placement already has launcher records')
    return audit, script, marker


def never_spawned(audit, started):
    """Proof that this attempt created no `stewart run` process.

    Either the launcher never reached the spawn, or the one command record it
    then wrote says the spawn itself failed. Anything else is not proof.
    """
    if not audit.run_attempted:
        return True
    try:
        commands = numbered_records(audit.evidence, r'([0-9]{2,})-run\.json')[0]
        return len(commands) == started + 1 and strict_json(read_file(commands[-1]))['process_state'] == 'not_started'
    except (OSError, ValueError, KeyError, TypeError):
        return False


def second_start(binary, private, packet, mode, *, local):
    """Rehearsal control: the same packet again, straight to preflight, after its placement ran.

    This bypasses the attempt records on purpose. The service's status now shows
    one placement more than the packet's prior state, so preflight must refuse
    there, before any readiness, credential or start.
    """
    at = [None]
    try:
        preflight(binary, private, packet, mode, {}, lambda code: at.__setitem__(0, code), local=local)
    except ValueError:
        return {'refused': True, 'phase': at[0]}
    return {'refused': False, 'phase': None}


def no_subject(script, review, limits):
    """Reviewer controls this finished control's evidence cannot carry, from its script and its arithmetic.

    The request-cap control needs earlier placements to have used enough output
    that the last placement's first `max_tokens` falls below the 16,000 cap
    (INTERFACE 6.4). Every held or capped control does. The unheld one does only
    when its signal found a request on the wire, which charges the estimate.
    """
    earlier = sum(sum(row['usage']['output_tokens'].values()) for row in review['placements'][:-1])
    at_cap = limits['output_tokens'] - earlier >= 16000
    return sorted(NO_SUBJECT[script] + (['reset-request-cap'] if at_cap else []))


def controls_after(audit, private, out, folder, key, script, review, *, local, operator_controls, report_controls):
    """Rehearsal only: exercise the reviewer, report and operator paths on a finished control."""
    from check_review import exercise as review_controls
    root = private.parent/'c10-continuation-controls'/f'{folder.parent.name}-{folder.name}'
    root.mkdir(mode=0o700, parents=True)
    counts = {'operations': None, 'reporting': None}
    found = review_controls(audit.root, root/'review')
    counts['review'] = {key_: found[key_] for key_ in ['run', 'passed', 'failed', 'skipped', 'controls',
                                                     'controls_fired', 'original_unchanged']}
    counts['review']['not_applicable'] = sorted(row['case'] for row in found['not_applicable'])
    # Which controls have no subject is worked out beforehand, never discovered and accepted.
    require(counts['review']['not_applicable'] == no_subject(script, review, audit.commission['limits']),
            'reviewer control inventory differs from its script')
    if operator_controls and CONTINUED[script]['endings'][-1][0] == 'ended_unsubmitted':
        # A control left unsealed with authoring ended: manager close on a continued audit.
        from check_operations import exercise as operator
        found = operator(private.parent, private=private, out=out, target=root/'operations', key=key,
                         local=local, audit=audit.run_item['id'])
        counts['operations'] = {'run': found['run'], 'passed': found['passed'], 'failed': found['failed'],
                                'original_unchanged': found['original_snapshot_unchanged']}
    if report_controls:
        from check_reporting import exercise as reporting
        found = reporting(out, root/'reporting')
        counts['reporting'] = {key_: found[key_] for key_ in ['run', 'passed', 'failed', 'original_unchanged']}
    scan = scan_tree(root, key)
    require(not scan['files_with_matches'] and not scan['errors'], 'continuation-control export scan failed')
    shutil.copytree(root, folder/'controls')
    return counts


def run_continuation(binary, private, out, packet_path, mode, read_key, *, local=False, witness=None,
                     operator_controls=True, report_controls=True):
    """Preflight, credential, one placement, review, close when submitted, next snapshot."""
    raw = read_file(packet_path)
    packet = strict_json(raw)
    folder, attempt = claim(out, packet)
    name, placement = packet['audit'], packet['placement']
    result = {'schema': 'stewart.c10-continuation-session/1', 'mode': mode, 'local_iteration_only': local,
        'audit': name, 'placement': placement, 'attempt': attempt, 'packet_sha256': digest(raw), 'started_at': time.time(),
        'prior_observed': None, 'credential_checked': False, 'placement_state': 'not_started',
        'exit': None, 'timed_out': None, 'interruption': None, 'review': None, 'automatic_close': None,
        'prior_snapshot': None, 'export': None, 'snapshot': None, 'stop_reason': None,
        'failed': True, 'outcome': 'failed' if mode == 'rehearse' else 'incomplete',
        'model_calls': 0 if mode == 'rehearse' else None, 'model_qualified': False,
        'skipped_checks': ['Linux process-access and process-identity controls (native iteration)'] if local else [],
        'environment': {'system': platform.system(), 'machine': platform.machine(),
                        'kernel': platform.release(), 'uid': os.getuid()}}
    if mode == 'rehearse':
        result.update(expected_observation=None, second_start=None, controls=None)
    at = ['preflight.packet']
    def stage(code):
        at[0] = code
    audit, key, started = None, None, 0
    try:
        validate_continuation(packet, rehearsal=mode == 'rehearse', approved=mode == 'live')
        audit, script, marker = preflight(binary, private, packet, mode, result, stage, local=local)
        started = len(numbered_records(audit.evidence, r'([0-9]{2,})-run\.json')[0])
        stage('preflight.ready')
        write_json(folder/'READY.json', {'continuation_preflight_verified': True, 'audit': name,
                                         'placement': placement, 'attempt': attempt})
        stage('credential.read')
        key = read_key()
        # A different key starts nothing: the marker binds the original placement's credential.
        stage('credential.differs')
        check_credential(marker, key)
        result['credential_checked'] = True
        stage('placement')
        # From here a start is possible, so the record says `unknown` until the
        # placement has been observed. `not_started` comes back only on proof.
        result['placement_state'] = 'unknown'
        try:
            observed = audit.place(key, witness, placement, packet['interruption'],
                intent={'continuation_packet_sha256': digest(raw), 'prior_observed': result['prior_observed']})
        except BaseException:
            if never_spawned(audit, started):
                result['placement_state'] = 'not_started'
            raise
        result.update(placement_state='observed', exit=observed['exit'], timed_out=observed['timed_out'],
            interruption=observed['interruption'], review=observed['review_before_close'],
            automatic_close=observed['automatic_close'])
        if mode == 'rehearse':
            stage('second-start-control')
            result['second_start'] = second_start(binary, private, packet, mode, local=local)
            audit.index_after_retained()
        stage('export.prior_members')
        (out/name).mkdir(mode=0o700, exist_ok=True)
        target = next_snapshot(out/name)
        kept = prior_members(audit.root, out/name)
        write_json(placement_folder(audit.evidence, placement)/'prior-snapshot.json', kept)
        result['prior_snapshot'] = kept
        if kept['unchanged'] is False:
            # A rewritten or missing original is a custody finding, not something to export over.
            result['stop_reason'] = 'prior_snapshot_members_changed'
        else:
            stage('export')
            event(audit.evidence, 'placement_export', snapshot=target.name, placement=placement)
            export = locked_export(audit, target, key)
            result.update(export=export, snapshot=target.name, stop_reason=stop_reason(observed, export))
        failed = result['stop_reason'] not in [None, 'without_auditor_submission']
        if mode == 'rehearse':
            # Fixed controls only: the expected ending comes from CONTINUED, never from this run.
            matched = result['export'] is not None and continued_match(observed, result['export'], script, placement)
            result['expected_observation'] = matched
            failed = not matched or result['second_start'] != {'refused': True, 'phase': 'preflight.prior_runs'}
            if not failed and placement == len(CONTINUED[script]['endings']):
                stage('controls')
                counts = controls_after(audit, private, out, folder, key, script, result['review'], local=local,
                    operator_controls=operator_controls, report_controls=report_controls)
                result['controls'] = counts
                failed = any(family is not None and (family['failed'] or family['original_unchanged'] is not True)
                             for family in counts.values())
        result['failed'] = failed
        result['outcome'] = (('failed' if failed else 'passed') if mode == 'rehearse'
                             else ('incomplete' if failed else 'observed'))
    except BaseException as error:
        # Never expose raw exceptions: they may contain credential-bearing evidence.
        # An interrupt or exit is recorded like any failure and then passed on.
        detail = failure_details(error, at[0], name)
        result['failure'] = detail
        write_json(folder/'FAILURE.json', detail)
        if not isinstance(error, Exception):
            raise
    finally:
        key = None
        result['ended_at'] = time.time()
        write_json(folder/'RESULT.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['rehearse', 'live'])
    parser.add_argument('--binary', type=Path, required=True, help='The exact writer the audit recorded')
    parser.add_argument('--packet', type=Path, required=True, help='A stewart.c10-continuation/1 packet')
    parser.add_argument('--private', type=Path, default=Path('/work/c10-private'))
    parser.add_argument('--out', type=Path, default=Path('/out'))
    args = parser.parse_args()
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        require(sys.platform == 'linux' and os.geteuid() == 0, 'container administrator required')
        result = run_continuation(args.binary, args.private, args.out, args.packet, args.mode,
            lambda: credential_bytes(sys.stdin.buffer.read(4098)),
            witness=args.private.parent/'c10-credential-witness' if args.mode == 'rehearse' else None)
    except Refused as error:
        print(f'Continuation refused; no attempt was recorded and nothing was started: {error}.', file=sys.stderr)
        return 1
    except Exception:
        print('Continuation could not record its attempt or its result. Inspect the attempt folder, '
              'the retained records and the audit status before any other action.', file=sys.stderr)
        return 1
    print(f"Continuation {result['audit']} placement {result['placement']} attempt {result['attempt']}: "
          f"placement {result['placement_state']}, outcome {result['outcome']}. Private originals remain; "
          'nothing is retried or continued automatically.', file=sys.stderr)
    return not (result['placement_state'] == 'observed' and result['failed'] is False)


if __name__ == '__main__':
    raise SystemExit(main())
