"""Bounded files, fixed case inventory and strict C10 commission packets."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for folder in ['driver', 'sanity']:
    sys.path.insert(0, str(HERE.parent / folder))
from session_support import credential_bytes, digest, scan_tree, write_json

SOURCE_PATHS = ['apparatus/c10', 'apparatus/sanity',
    'apparatus/driver/credential_observer.py', 'apparatus/driver/driver_core.py',
    'apparatus/driver/rawjson.py', 'apparatus/driver/answer_witness.py']
FAMILIES = ['open-inquiry', 'inquiry-framing', 'comparison']
# Rehearsal controls that need more than one placement. Each first placement
# ends interrupted; a separately bound continuation packet starts the next one.
# `interruption` names the witnessed point after which the apparatus signals the
# placement, or None when the fake provider ends it. `held` says whether the
# fake withholds its response to the request in flight until the signal has been
# sent: True makes the aborted-in-flight case certain; False signals as soon as
# the record is seen, as a live interruption does, so the request may or may not
# have been written. `endings` are the (ending, cause) pairs INTERFACE 6.5 gives
# each placement in order; they hold for either timing.
CONTINUED = {
    # A thinking-only response at the output cap; no entry exists to preserve.
    'continue-cap': {'interruption': None, 'held': None,
        'endings': [['interrupted', 'max_tokens'], ['sealed', None]]},
    # The same ending after a recorded entry, which the next placement revises.
    'continue-entries': {'interruption': None, 'held': None,
        'endings': [['interrupted', 'max_tokens'], ['sealed', None]]},
    # Interrupted after its reminder; the next ordinary ending ends authoring.
    'reminder-spent': {'interruption': 'reminder_notice', 'held': True,
        'endings': [['interrupted', 'signal'], ['ended_unsubmitted', None]]},
    # The same without holding the request: the timing a live interruption has.
    'reminder-spent-unheld': {'interruption': 'reminder_notice', 'held': False,
        'endings': [['interrupted', 'signal'], ['ended_unsubmitted', None]]},
    # Interrupted after its reminder; the next placement submits unprompted.
    'reminder-spent-submits': {'interruption': 'reminder_notice', 'held': True,
        'endings': [['interrupted', 'signal'], ['sealed', None]]},
    # Interrupted before any reminder; the next placement receives the reminder.
    'reminder-unused': {'interruption': 'entry_record', 'held': True,
        'endings': [['interrupted', 'signal'], ['sealed', None]]},
}
INTERRUPTION_POINTS = ['reminder_notice', 'entry_record']
CONTINUABLE_CAUSES = ['signal', 'max_tokens', 'provider_unavailable', 'provider_rejected',
    'context_exhausted', 'provider_refusal', 'protocol_anomaly']
MAX_PLACEMENTS = 4
SCENARIOS = ['submitted', 'empty', 'unsubmitted', 'provider-rejected',
    'lost-run-reply', 'reflected-body', 'export-contamination', 'export-failure',
    *CONTINUED]
BINDINGS = ['qualification_id', 'binary_sha256', 'source_commit', 'apparatus_sha256',
            'image', 'catalog_sha256']
LIMITS = ['turns', 'input_tokens', 'output_tokens']
MAX_FILE = 64 * 1024 * 1024


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def bad_constant(value):
        raise ValueError('nonfinite JSON number')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=bad_constant)


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def fields(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), label + ' fields differ')


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9-]{0,79}', value) is not None


def relative(value):
    path = PurePosixPath(value)
    require(isinstance(value, str) and value and not path.is_absolute()
            and all(p not in ['', '.', '..'] for p in value.split('/')),
            'unsafe relative evidence path')
    return value


def read_file(path, limit=MAX_FILE):
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= limit,
                'nonregular or oversized evidence member')
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(len(raw) <= limit and (before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_ino, after.st_size, after.st_mtime_ns), 'evidence changed during read')
    return raw


def file_hash(path):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0)), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), 'hash needs a regular file')
        hashed = hashlib.sha256()
        for chunk in iter(lambda: stream.read(65536), b''):
            hashed.update(chunk)
        after = os.fstat(stream.fileno())
    require((before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_ino, after.st_size, after.st_mtime_ns), 'file changed during hashing')
    return hashed.hexdigest()


def inventory(root):
    root = Path(root)
    require(stat.S_ISDIR(root.lstat().st_mode), 'inventory root must be a directory')
    result = []
    def visit(folder):
        for path in sorted(folder.iterdir()):
            name = path.relative_to(root).as_posix()
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                result.append({'path': name, 'type': 'directory'})
                visit(path)
            else:
                require(stat.S_ISREG(mode), 'inventory contains a link or special file')
                result.append({'path': name, 'type': 'file', 'bytes': path.stat().st_size,
                               'sha256': file_hash(path)})
    visit(root)
    return result


def tree_hash(root):
    return digest(compact(inventory(root)))


def source_hash(repo=REPO):
    records = []
    for name in SOURCE_PATHS:
        path = repo / name
        if path.is_dir():
            records.extend({'root': name, **item} for item in inventory(path))
        else:
            records.append({'root': name, 'sha256': file_hash(path)})
    return digest(compact(records))


def catalog():
    value = strict_json(read_file(HERE / 'catalog.json'))
    fields(value, ['schema', 'cases'], 'catalog')
    require(value['schema'] == 'stewart.c10-catalog/1', 'unsupported catalog')
    found = {}
    for case in value['cases']:
        fields(case, ['id', 'family', 'variant', 'question', 'illustrative_return'], 'case')
        require(identifier(case['id']) and case['id'] not in found, 'invalid or repeated case')
        require(case['family'] in FAMILIES and case['variant'] in ['ordinary', 'inadequate'], 'unknown case family or variant')
        require(isinstance(case['question'], str) and case['question'].endswith('\n'), 'question must have exact terminal LF')
        root = HERE / 'specimens' / case['id']
        items = inventory(root)
        require({p.name for p in root.iterdir()} == {'materials'}, 'specimen must contain only materials')
        for item in items:
            if item['type'] == 'file':
                raw = read_file(root / item['path'])
                require(b'\0' not in raw, 'NUL in specimen')
                raw.decode('utf-8')
        found[case['id']] = {**case, 'root': root,
            'sha256': digest(compact({'case': case, 'materials': items}))}
    require(len(found) == 6 and {(c['family'], c['variant']) for c in found.values()}
            == {(family, variant) for family in FAMILIES for variant in ['ordinary', 'inadequate']},
            'catalog must cover ordinary and inadequate evidence for all three families')
    return found


def validate_interruption(value, *, rehearsal=False):
    """A witnessed point after which the apparatus sends one signal to the placement.

    Live packets may select only the recorded reminder notice. The point is a
    log record published by that placement; elapsed time never selects it.
    """
    fields(value, ['after', 'signal'], 'interruption')
    require(value['after'] in (INTERRUPTION_POINTS if rehearsal else ['reminder_notice'])
            and value['signal'] == 'SIGTERM', 'unsupported interruption point or signal')
    return value


def validate_packet(packet, *, rehearsal=False, approved=False):
    interface_study = packet.get('schema') == 'stewart.interface-commission/1'
    # A study audit whose first placement is interrupted at a witnessed point.
    # Later placements each need their own stewart.c10-continuation/1 packet.
    interrupted_study = packet.get('schema') == 'stewart.interruption-commission/1'
    fields(packet, ['schema', 'model', 'effort', 'limits', 'endpoint', 'proxy', 'runs',
        'max_placements', 'permitted_request_attempts', 'automatic_continuation',
        'stop_after_seconds', 'spending_authority', 'account', 'bindings']
        + (['study_build'] if interface_study else [])
        + (['interruption'] if interrupted_study else []), 'commission')
    require(packet['schema'] in ['stewart.c10-commission/1', 'stewart.study-commission/1',
                                'stewart.interface-commission/1',
                                'stewart.interruption-commission/1'], 'unsupported commission schema')
    study = packet['schema'] != 'stewart.c10-commission/1'
    if interrupted_study:
        validate_interruption(packet['interruption'], rehearsal=rehearsal)
        require(isinstance(packet['runs'], list) and len(packet['runs']) == 1,
                'an interrupted study names exactly one audit')
    if interface_study:
        from study_build import validate
        validate(packet['study_build'], bound=approved)
    model = packet['model']
    require(isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', model), 'invalid model')
    require((model == 'rehearsal-only') == rehearsal and not model.startswith('REPLACE'), 'model does not match launch mode')
    require(packet['effort'] in [None, 'low', 'medium', 'high', 'xhigh', 'max'], 'invalid effort')
    fields(packet['limits'], LIMITS, 'limits')
    require(all(type(n) is int and 0 < n <= 2**48 for n in packet['limits'].values()), 'invalid allowance')
    require(packet['limits']['output_tokens'] >= 1024, 'output allowance cannot launch')
    require(packet['endpoint'] == ('loopback-fake' if rehearsal else 'https://api.anthropic.com')
            and packet['proxy'] is None, 'unapproved provider route')
    # Every launch performs one placement. An interrupted study records the
    # audit's commissioned ceiling; its later placements are separately bound.
    require(type(packet['max_placements']) is int
            and (2 <= packet['max_placements'] <= MAX_PLACEMENTS if interrupted_study
                 else packet['max_placements'] == 1)
            and type(packet['permitted_request_attempts']) is int and packet['permitted_request_attempts'] == 4
            and packet['automatic_continuation'] is False, 'one placement per launch, built-in retries and no automatic continuation required')
    require(type(packet['stop_after_seconds']) is int and 60 <= packet['stop_after_seconds'] <= 14400, 'invalid watchdog')
    cases = catalog()
    require(isinstance(packet['runs'], list) and 0 < len(packet['runs']) <= 64, 'batch needs 1–64 explicit audits')
    identities, repetitions = set(), set()
    study_count = 0
    for run in packet['runs']:
        fields(run, ['id', 'case', 'repetition', 'scenario', 'submission_sha256']
               + (['submission_folder'] if study else []), 'run')
        require(identifier(run['id']) and run['id'] not in identities, 'invalid or repeated audit identity')
        identities.add(run['id'])
        supplied = study and run['submission_folder'] is not None
        if supplied:
            folder = run['submission_folder']
            require(isinstance(folder, str) and Path(folder).is_absolute()
                    and not any(ord(c) < 32 for c in folder), 'study submission needs an absolute folder')
            require(identifier(run['case']) and run['case'] == run['id']
                    and run['id'] not in cases and not run['id'].startswith('control-'), 'invalid study identity')
            require(run['repetition'] == 1 and run['scenario'] == 'submitted', 'study packet names each placement once')
            require(isinstance(run['submission_sha256'], str)
                    and re.fullmatch(r'[0-9a-f]{64}', run['submission_sha256']), 'invalid submission digest')
            study_count += 1
        else:
            require(not study or rehearsal, 'live study packets cannot select catalog cases')
            require(run['case'] in cases, 'unknown catalog case')
            require(run['submission_sha256'] == cases[run['case']]['sha256'], 'specimen differs from packet')
        require(type(run['repetition']) is int and 1 <= run['repetition'] <= 64, 'invalid case repetition')
        require(run['scenario'] in (SCENARIOS if rehearsal else ['submitted']), 'live packet cannot select a control')
        key = (run['case'], run['repetition'], run['scenario'])
        require(key not in repetitions, 'duplicate case repetition')
        repetitions.add(key)
    require(not study or study_count > 0 or interface_study and rehearsal,
            'study packet needs an explicit submission')
    fields(packet['bindings'], BINDINGS, 'bindings')
    fields(packet['account'], ['account_label', 'workspace_id', 'credential_label'], 'account')
    for value in [*packet['bindings'].values(), *packet['account'].values(), packet['spending_authority']]:
        require(value is None or isinstance(value, str) and 0 < len(value) <= 4096, 'invalid packet metadata')
        if approved:
            require(isinstance(value, str) and bool(value.strip()), 'approved packet has unfilled authority or bindings')
    return packet


def validate_continuation(packet, *, rehearsal=False, approved=False):
    """One later placement of one retained audit, bound to its observed prior state.

    `prior.log_head_sha256` and `prior.usage` may be null when the preceding
    placement has not happened yet; the launcher then records what it finds.
    Nothing here starts a placement automatically or permits a replacement.
    """
    fields(packet, ['schema', 'evidence', 'audit', 'container', 'reference', 'placement',
        'max_placements', 'prior', 'model', 'limits', 'endpoint', 'proxy', 'interruption',
        'permitted_request_attempts', 'automatic_continuation', 'stop_after_seconds',
        'spending_authority', 'account', 'bindings'], 'continuation')
    require(packet['schema'] == 'stewart.c10-continuation/1', 'unsupported continuation schema')
    evidence = packet['evidence']
    require(isinstance(evidence, str) and Path(evidence).is_absolute()
            and not any(ord(c) < 32 for c in evidence), 'continuation needs the absolute retained evidence folder')
    require(identifier(packet['audit']), 'invalid audit identity')
    require(isinstance(packet['container'], str)
            and re.fullmatch(r'stewart-c10-[0-9]+-[0-9]+', packet['container']), 'unknown container identity')
    require(isinstance(packet['reference'], str)
            and re.fullmatch(r'stw1:[a-z2-7]{17}:[a-z2-7]{17}:/[\x21-\x7e]{1,1024}', packet['reference']),
            'invalid audit reference')
    require(type(packet['placement']) is int and type(packet['max_placements']) is int
            and 2 <= packet['placement'] <= packet['max_placements'] <= MAX_PLACEMENTS,
            'placement outside the commissioned ceiling')
    prior = packet['prior']
    fields(prior, ['runs', 'last_ending', 'last_cause', 'log_head_sha256', 'usage'], 'prior state')
    require(prior['runs'] == packet['placement'] - 1 and prior['last_ending'] == 'interrupted'
            and prior['last_cause'] in CONTINUABLE_CAUSES,
            'only the next placement of an audit whose last placement was recorded interrupted')
    require(prior['log_head_sha256'] is None or isinstance(prior['log_head_sha256'], str)
            and re.fullmatch(r'[0-9a-f]{64}', prior['log_head_sha256']), 'invalid log head digest')
    if prior['usage'] is not None:
        fields(prior['usage'], LIMITS, 'prior usage')
        require(all(type(n) is int and 0 <= n <= 2**48 for n in prior['usage'].values()), 'invalid prior usage')
    model = packet['model']
    require(isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', model), 'invalid model')
    require((model == 'rehearsal-only') == rehearsal and not model.startswith('REPLACE'), 'model does not match launch mode')
    fields(packet['limits'], LIMITS, 'limits')
    require(all(type(n) is int and 0 < n <= 2**48 for n in packet['limits'].values()), 'invalid allowance')
    require(packet['endpoint'] == ('loopback-fake' if rehearsal else 'https://api.anthropic.com')
            and packet['proxy'] is None, 'unapproved provider route')
    if packet['interruption'] is not None:
        validate_interruption(packet['interruption'], rehearsal=rehearsal)
    require(type(packet['permitted_request_attempts']) is int and packet['permitted_request_attempts'] == 4
            and packet['automatic_continuation'] is False, 'built-in retries and no automatic continuation required')
    require(type(packet['stop_after_seconds']) is int and 60 <= packet['stop_after_seconds'] <= 14400, 'invalid watchdog')
    fields(packet['bindings'], BINDINGS, 'bindings')
    fields(packet['account'], ['account_label', 'workspace_id', 'credential_label'], 'account')
    for value in [*packet['bindings'].values(), *packet['account'].values(), packet['spending_authority']]:
        require(value is None or isinstance(value, str) and 0 < len(value) <= 4096, 'invalid packet metadata')
        if approved:
            require(isinstance(value, str) and bool(value.strip()), 'approved packet has unfilled authority or bindings')
    return packet


def proposal(model, case_ids=None, repetitions=1, *, rehearsal=False):
    cases = catalog()
    selected = list(cases) if case_ids is None else case_ids
    require(type(repetitions) is int and 1 <= repetitions <= 3, 'proposal repetitions must be 1–3')
    require(selected and len(set(selected)) == len(selected) and all(c in cases for c in selected), 'select known distinct cases')
    packet = {'schema': 'stewart.c10-commission/1', 'model': model, 'effort': None,
        'limits': {'turns': 12, 'input_tokens': 160000, 'output_tokens': 12000},
        'endpoint': 'loopback-fake' if rehearsal else 'https://api.anthropic.com', 'proxy': None,
        'runs': [{'id': f'{name}-r{n}', 'case': name, 'repetition': n, 'scenario': 'submitted',
                  'submission_sha256': cases[name]['sha256']} for name in selected for n in range(1, repetitions + 1)],
        'max_placements': 1, 'permitted_request_attempts': 4, 'automatic_continuation': False,
        'stop_after_seconds': 900, 'spending_authority': None,
        'account': {key: None for key in ['account_label', 'workspace_id', 'credential_label']},
        'bindings': {key: None for key in BINDINGS}}
    return validate_packet(packet, rehearsal=rehearsal)


def rehearsal_packet():
    packet = proposal('rehearsal-only', rehearsal=True)
    packet['stop_after_seconds'] = 60
    # A request aborted by a signal after any byte was written is charged its
    # whole max_tokens as an estimate (INTERFACE 6.4), and max_tokens is the
    # lesser of 16,000 and what remains. With the proposal's 12,000 the
    # interrupted controls would leave under 1,024 output tokens and the next
    # placement would end limit_reached before any request. 30,000 leaves room
    # for one such estimate while keeping later requests below the 16,000 cap.
    packet['limits']['output_tokens'] = 30000
    for scenario in SCENARIOS[1:]:
        packet['runs'].append({'id': 'control-' + scenario, 'case': 'open-ordinary',
            'repetition': 1, 'scenario': scenario,
            'submission_sha256': catalog()['open-ordinary']['sha256']})
    packet['spending_authority'] = 'Offline fakes only; zero model calls.'
    return validate_packet(packet, rehearsal=True)


def question_file(case, packet, destination):
    rows = ['---', 'stewart: question/1', 'family: ' + case['family'],
            'model: ' + packet['model'], 'destination: ' + str(destination)]
    if packet['effort'] is not None:
        rows.append('effort: ' + packet['effort'])
    for key in ['guidance', 'inquiry', 'varies']:
        if case.get(key) is not None:
            rows.append(key + ': ' + case[key])
    rows += ['limit-' + name.replace('_', '-') + ': ' + str(packet['limits'][name]) for name in LIMITS]
    return ('\n'.join(rows) + '\n---\n' + case['question']).encode()
