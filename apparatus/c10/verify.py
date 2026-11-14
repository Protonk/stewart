"""Read-only procedural review, with explicit witness scope and no quality grade."""
import base64
from collections import Counter
import copy
import hashlib
from pathlib import Path
import re
import tarfile

from common import (MAX_FILE, LIMITS, compact, digest, file_hash, inventory,
                    question_file, read_file, relative, require, strict_json)
import answer_witness as answer
import driver_core as spec
import rawjson
from study import case_from_question
from study_build import family_id, system_bytes


class Evidence:
    """Read regular files or a verified export without extracting any member."""
    def __init__(self, root, expected_hash=None):
        self.root = Path(root)
        self.archive = None
        if expected_hash is None:
            items = inventory(root)
            self.names = {item['path'] for item in items if item['type'] == 'file'}
            self.directories = {item['path'] for item in items if item['type'] == 'directory'}
        else:
            require(file_hash(root) == expected_hash, 'export_digest')
            self.archive = tarfile.open(root, 'r:')
            self.members = {}
            try:
                for member in self.archive:
                    relative(member.name)
                    require(member.name == 'private' or member.name.startswith('private/'), 'export_root')
                    require(member.name not in self.members, 'duplicate_export_member')
                    require(member.isfile() or member.isdir(), 'nonregular_export_member')
                    self.members[member.name] = member
            except BaseException:
                self.archive.close()
                raise
            self.names = {name[len('private/'):] for name, item in self.members.items() if item.isfile()}
            self.directories = {name[len('private/'):] for name, item in self.members.items()
                                if item.isdir() and name != 'private'}

    def read(self, name, limit=MAX_FILE):
        relative(name)
        require(name in self.names, 'missing_evidence')
        if self.archive is None:
            return read_file(self.root / name, limit)
        member = self.members['private/' + name]
        require(member.size <= limit, 'oversized_evidence')
        with self.archive.extractfile(member) as stream:
            raw = stream.read(limit + 1)
        require(len(raw) == member.size, 'incomplete_export_member')
        return raw

    def json(self, name):
        return strict_json(self.read(name))

    def close(self):
        if self.archive is not None:
            self.archive.close()


def serial_names(names, prefix, pattern):
    selected = [name for name in names if name.startswith(prefix) and '/' not in name[len(prefix):]]
    matches = []
    for name in selected:
        match = re.fullmatch(pattern, name[len(prefix):])
        require(match is not None, 'unexpected_numbered_member')
        matches.append((int(match[1]), name))
    matches.sort()
    require([n for n, _ in matches] == list(range(1, len(matches) + 1)), 'noncontiguous_records')
    return [name for _, name in matches]


def usage_counts(value):
    keys = ['input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens']
    iterations = value.get('iterations')
    rows = iterations if iterations is not None else [value]
    require(isinstance(rows, list) and bool(rows), 'invalid_usage_iterations')
    total = dict.fromkeys(keys, 0)
    for row in rows:
        if iterations is not None:
            require(row.get('type') in ['message', 'compaction'], 'invalid_usage_iteration_type')
        for key in keys:
            n = row.get(key, 0) if key.startswith('cache_') else row[key]
            if n is None and key.startswith('cache_'):
                n = 0
            require(type(n) is int and 0 <= n <= 2**48, 'invalid_usage_count')
            total[key] += n
            require(total[key] <= 2**48, 'usage_sum_overflow')
    return total


def verify(evidence):
    """Conservative small-commission report. Unsupported mechanisms stay incomplete."""
    report = {'schema': 'stewart.c10-review/3', 'outcome': 'incomplete',
        'checks': [], 'failures': [], 'coverage': None, 'model_qualified': False,
        'unassessed': ['full C10 repetition matrix', 'compaction',
                       'a placement reconciled after its process died (process_gone)',
                       'a response the provider cut off or that Stewart could not decode'],
        'witness_scope': None}
    def check(condition, code):
        require(condition, code)
        if code not in report['checks']:
            report['checks'].append(code)
    try:
        _verify(evidence, report, check)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, UnicodeError,
            answer.CitationDefect, RecursionError) as error:
        # Do not echo arbitrary provider text or an offending authored operand.
        code = str(error) if type(error) is ValueError and re.fullmatch(r'[a-z_]{1,80}', str(error)) else 'unreadable_or_unsupported_evidence'
        report['failures'].append(code)
        report['outcome'] = 'incomplete'
        # Partial checks are diagnostic, not a current custody or coverage finding.
        for field in ['coverage', 'usage', 'ending', 'cause', 'placements', 'auditor_submitted',
                      'seal_actor', 'delivery_verified', 'closed', 'guidance']:
            report[field] = None
    return report


CAUSES = [None, 'provider_rejected', 'signal', 'max_tokens', 'provider_unavailable',
          'context_exhausted', 'provider_refusal', 'protocol_anomaly', 'archive_write_failed',
          'process_gone', 'credential_reflected']


def placement_evidence(placement):
    """The launcher's records of one placement; the first keeps its original names."""
    return 'evidence/' if placement == 1 else f'evidence/placement-{placement:04d}/'


def text_block(text):
    """INTERFACE 6.2: a text block, its string escaped as in stewart.answer/1."""
    return b'{"type":"text","text":' + spec.pinned_json_string(text).encode() + b'}'


def user_message(blocks):
    return b'{"role":"user","content":[' + b','.join(blocks) + b']}'


def first_message(question, continuing):
    """INTERFACE 6.2 and 6.7: the question exactly; then the continuation notice."""
    return user_message([text_block(question)] + ([text_block(spec.CONTINUATION)] if continuing else []))


def ordinary_body(arrnode, max_tokens, active):
    """INTERFACE 4.5: an ordinary request body spliced from pinned bytes and active messages."""
    extra = arrnode.get('request_extra')
    suffix = b''.join(b',' + extra.data[start:value.end] for _, start, _, value in extra.members)
    return (b'{"model":' + arrnode.get('model').raw + b',"max_tokens":' + str(max_tokens).encode()
        + b',"system":' + arrnode.get('system').raw + b',"tools":' + arrnode.get('tools').raw
        + suffix + b',"messages":[' + b','.join(active) + b']}')


def limit_exhausted(limits, used):
    """INTERFACE 6.4: no turn remains, the input allowance is used up, or under 1,024 output tokens remain."""
    return (used['turns'] >= limits['turns'] or used['input_tokens'] >= limits['input_tokens']
            or limits['output_tokens'] - used['output_tokens'] < 1024)


def near_limit(limits, used):
    """INTERFACE 6.4: whether the notice is triggered, and the amounts its template states."""
    remaining = {key: max(0, limits[key] - used[key]) for key in LIMITS}
    return any(remaining[key] * 100 <= 20 * limits[key] for key in LIMITS), remaining


def notice_sent(capture_exists, written):
    """INTERFACE 6.4: `sent` once an attempt of the planned request wrote any byte."""
    if any(state != 'none' for state in written):
        return 'sent'
    return 'unknown' if capture_exists else 'not_sent'


def preview(data):
    """INTERFACE 7.5: the first 200 bytes on a character boundary."""
    cut = data[:200]
    while True:
        try:
            return cut.decode('utf-8')
        except UnicodeDecodeError:
            cut = cut[:-1]


def ordinary_submission(report):
    """The existing automatic-close/admission condition, not an answer grade."""
    return (report['outcome'] == 'checked' and report['ending'] == 'sealed'
            and report['auditor_submitted'] is True and report['delivery_verified'] is True)


class PagingObservation:
    """Count captured read/search affordances, not comprehension or answer quality.

    A follow is an exact tool/input match with a previously offered next call.
    Semantically equivalent operands are outside this deliberately narrow check.
    """
    def __init__(self):
        self.pending = []
        self.counts = dict(completed_read_search_calls=0, incomplete_pages=0,
                           next_calls_offered=0, exact_next_call_attempts=0)

    def observe(self, tool, operands, reply):
        call = {'tool':tool, 'input':operands}
        if call in self.pending:
            self.counts['exact_next_call_attempts'] += 1
            self.pending.remove(call)
        if tool not in ['read','search'] or reply['outcome'] != 'completed':
            return
        require(type(reply['data']['complete']) is bool and isinstance(reply['next'],list),
                'paging_observation_shape')
        self.counts['completed_read_search_calls'] += 1
        self.counts['incomplete_pages'] += not reply['data']['complete']
        for item in reply['next']:
            if item['tool'] == tool:
                require(isinstance(item['input'],dict), 'paging_observation_shape')
                self.pending.append({'tool':tool, 'input':item['input']})
                self.counts['next_calls_offered'] += 1


def _verify(e, report, check):
    binding = e.json('evidence/binding.json')
    check(binding['schema'] == 'stewart.c10-audit/1', 'audit_binding_schema')
    packet, run = binding['commission'], binding['run']
    family = binding['family']
    versioned_family = family_id(packet, family)
    if packet.get('study_build') is not None:
        from common import validate_packet
        validate_packet(packet, rehearsal=binding['mode'] == 'rehearse', approved=binding['mode'] == 'live')
        report['binary_status'] = 'unqualified_study'
        report['study_build'] = packet['study_build']
    specimen = e.json('evidence/specimen.json')
    if run.get('submission_folder') is not None:
        check(packet['schema'] in ['stewart.study-commission/1', 'stewart.interface-commission/1',
                                   'stewart.interruption-commission/1']
              and run in packet['runs'], 'study_packet_binding')
        template = tree_inventory_from_evidence(e, 'evidence/submission-template/')
        check(digest(compact(template)) == run['submission_sha256'], 'study_template_binding')
        case = case_from_question(e.read('evidence/submission-template/question.md'), run['case'])
        check(specimen == {'case': case, 'materials': [item for item in template if item['path'] == 'materials' or item['path'].startswith('materials/')]},
              'study_specimen_binding')
    else:
        check(digest(compact(specimen)) == run['submission_sha256'], 'specimen_binding')
    check(specimen['case']['id'] == run['case'] and specimen['case']['family'] == family, 'specimen_binding')
    report.update(audit=run['id'], case=run['case'], repetition=run['repetition'], mode=binding['mode'])
    report['witness_scope'] = {'inputs': 'independent copies before intake',
        'provider': 'independent fake exchanges' if binding['mode'] == 'rehearse' else 'Stewart-owned captures; no independent live provider witness',
        'custody': 'specification-derived checks of captures, ledger and delivered bytes'}
    check(inventory_from_evidence(e, 'evidence/input-witness/') == binding['input_inventory'], 'input_witness_identity')
    qfile = e.read('evidence/input-witness/question.md')
    check(qfile == question_file(specimen['case'], packet, binding['destination']), 'rendered_submission_binding')
    qbody = qfile.split(b'---\n', 2)[2]
    selected_guidance = specimen['case'].get('guidance')
    guidance = e.read('evidence/input-witness/guidance.md', 262144) if selected_guidance else None
    if selected_guidance:
        check(selected_guidance == 'guidance.md' and family == 'open-inquiry'
              and b'\0' not in guidance and bool(guidance.decode('utf-8').strip()), 'guidance_selection')
        check(guidance == e.read('evidence/submission-template/guidance.md'), 'guidance_template_binding')

    sources = {'question': qbody}
    sources.update({name[len('evidence/input-witness/'):]: e.read(name) for name in e.names
                    if name.startswith('evidence/input-witness/materials/')})
    expected_materials = {item['path']:item for item in specimen['materials'] if item['type']=='file'}
    check(set(sources)-{'question'} == set(expected_materials), 'specimen_material_population')
    for name,item in expected_materials.items():
        check(digest(sources[name]) == item['sha256'] and len(sources[name]) == item['bytes'], 'specimen_material_bytes')
    prefixes = {name.split('/')[2] for name in e.names if name.startswith('archive/audits/')}
    check(len(prefixes) == 1, 'one_audit')
    audit = prefixes.pop()
    base = 'archive/audits/' + audit + '/'
    names = serial_names(e.names, base + 'log/', r'([1-9][0-9]*)\.json')
    check(bool(names), 'log_present')
    records, by_name, previous = [], {}, None
    for name in names:
        raw, value = e.read(name), e.json(name)
        check(raw.endswith(b'\n') and value['record'] == 'stewart.record/1'
              and value['audit'] == audit and value['writer'] == binding['binary_sha256']
              and value['body']['prev'] == previous, 'log_chain_and_writer')
        previous = digest(raw)
        records.append(value)
        by_name[name[len(base):]] = value
    def one(kind):
        values = [r for r in records if r['kind'] == kind]
        check(len(values) == 1, 'one_' + kind)
        return values[0]
    accepted = one('accepted')['body']
    receipt_raw = e.read(base + relative(accepted['receipt']))
    check(digest(receipt_raw) == accepted['receipt_sha256'], 'receipt_binding')
    receipt = strict_json(receipt_raw)['body']
    readbacks = e.json('evidence/readbacks.json')
    expected_readbacks = {'question-file':qfile, 'question-body':qbody,
                          **{k:v for k,v in sources.items() if k!='question'}}
    if guidance is not None:
        expected_readbacks['guidance-file'] = guidance
    check(len(readbacks) == len(expected_readbacks) and {r['item'] for r in readbacks} == set(expected_readbacks), 'readback_membership')
    for item in readbacks:
        check(re.fullmatch(r'[0-9]{2,}-readback-[0-9]{4}',item['command']) is not None, 'readback_command_identity')
        stem = 'evidence/' + item['command']
        command = e.json(stem+'.json')
        check(command['argv'][1:] == ['receipt',receipt['reference'],'--read',item['item']]
              and command['exit'] == 0 and command['timed_out'] is False
              and e.read(stem+'.stdout') == expected_readbacks[item['item']]
              and item['sha256'] == digest(expected_readbacks[item['item']]), 'exact_receipt_readback')
    check(receipt['settings']['family'] == family and receipt['settings']['model'] == packet['model']
          and receipt['settings']['limits'] == packet['limits']
          and receipt['settings'].get('effort') == packet['effort']
          and receipt['settings'].get('guidance') == selected_guidance, 'commission_settings')
    if guidance is not None:
        g = receipt['guidance']
        check(receipt['schema'] == 'stewart.receipt/2' and g['file'] == 'guidance.md'
              and g['size'] == len(guidance) and g['sha256'] == digest(guidance)
              and e.read(base + relative(g['capture'])) == guidance, 'guidance_capture')
    elif receipt.get('schema') == 'stewart.receipt/2':
        check(receipt['guidance'] is None, 'guidance_selection')
    check(e.read(base + relative(receipt['question']['capture'])) == qfile, 'question_capture')
    check(receipt['question']['body_sha256'] == digest(qbody), 'question_body_binding')
    materials = receipt['materials']['files']
    check(sorted(receipt['materials']['directories']) == sorted(binding['input_directories']), 'material_directories')
    check(len(materials) == len(sources) - 1 and {m['name'] for m in materials} == set(sources) - {'question'}, 'material_membership')
    for member in materials:
        check(e.read(base + relative(member['capture'])) == sources[member['name']]
              and member['sha256'] == digest(sources[member['name']])
              and member['size'] == len(sources[member['name']]), 'material_capture')
    arrangement_raw = e.read(base + relative(receipt['arrangement']['machine']))
    check(digest(arrangement_raw) == receipt['arrangement']['sha256'], 'arrangement_binding')
    arrnode = rawjson.parse(arrangement_raw).get('body')
    arr = arrnode.value()
    check(arr['family'] == versioned_family and arr['model'] == packet['model']
          and arr['limits'] == packet['limits'], 'arrangement_settings')
    check(arrnode.get('system').raw == system_bytes(packet, family, guidance)
          and arrnode.get('tools').raw == compact(spec.expected_tools(family)), 'specified_system_and_tools')
    if guidance is not None or arr.get('schema') == 'stewart.arrangement/2':
        effective = strict_json(system_bytes(packet, family, guidance))[1]['text'].encode()
        identity = {'source': 'guidance.md' if guidance is not None else 'builtin',
                    'size': len(effective), 'sha256': digest(effective)}
        check(arr['schema'] == 'stewart.arrangement/2' and arr['guidance'] == identity, 'guidance_identity')
        report['guidance'] = identity
    expected_extra = {} if packet['effort'] is None else {'output_config': {'effort': packet['effort']}}
    check(arr['request_extra'] == expected_extra, 'effort_parameter')
    check(arr['max_tokens_per_request'] == 16000 and arr['request_timeout_seconds'] == 600,
          'release_request_bounds')
    limits = packet['limits']
    index = {record_name: n for n, record_name in enumerate(by_name, 1)}
    starts = [(n, r['body']) for n, r in enumerate(records, 1) if r['kind'] == 'run_started']
    ends = [(n, r['body']) for n, r in enumerate(records, 1) if r['kind'] == 'run_ended']
    check(bool(starts) and len(starts) == len(ends), 'placement_boundaries')
    count = len(starts)
    for placement, ((opened, started), (closed_at, ended)) in enumerate(zip(starts, ends), 1):
        # A new placement starts only after the one before it has its ending (INTERFACE 4.4).
        check(started['run'] == ended['run'] == placement and started['continuing'] is (placement > 1)
              and started['dir'] == f'runs/{placement}' and opened < closed_at
              and (placement == count or closed_at < starts[placement][0]), 'placement_sequence')
        # Reconciliation of a dead process is recorded by another operation from
        # what it found. This reviewer does not reconstruct that accounting.
        check(ended['recorded_by'] == 'run' and ended['cause'] != 'process_gone',
              'process_gone_placement_unassessed')
    check({name[len(base + 'runs/'):].split('/')[0] for name in e.names if name.startswith(base + 'runs/')}
          == {str(n) for n in range(1, count + 1)}, 'run_membership')
    # The launcher's own record of each start and of the status it then observed.
    commands = serial_commands(e.names, r'evidence/[0-9]{2,}-run\.json')
    observed = serial_commands(e.names, r'evidence/[0-9]{2,}-status-after-run\.stdout')
    check(len(commands) == count and len(observed) == count, 'placement_command_count')
    notices = [(n, r['body']) for n, r in enumerate(records, 1) if r['kind'] == 'notice']
    for kind in ['reminder', 'near_limit']:
        # Each allowance is audit-wide: a continuing placement neither resets nor resends it.
        check(sum(body['type'] == kind for _, body in notices) <= 1, 'notice_once_per_audit')
    check(all(body['type'] in ['reminder', 'near_limit'] for _, body in notices), 'notice_type')
    planned = {}
    for position, body in notices:
        check(type(body['run']) is int and 1 <= body['run'] <= count
              and starts[body['run']-1][0] < position < ends[body['run']-1][0], 'notice_within_placement')
        planned.setdefault((body['run'], body['request']), []).append(body)
    reminder = next((body for _, body in notices if body['type'] == 'reminder'), None)
    if reminder is not None:
        check(reminder['text'] == spec.REMINDER and reminder['remaining'] is None, 'reminder_text')
    seal_position = next((n for n, r in enumerate(records, 1) if r['kind'] == 'seal'), None)

    total = {key: {'reported': 0, 'estimated': 0} for key in LIMITS}
    def used():
        return {key: sum(total[key].values()) for key in LIMITS}
    responses, response_blocks, used_blocks = {}, {}, set()
    request_bodies, response_names = {}, set()
    entry_records = {name: record for name, record in by_name.items() if record['kind'] == 'entry'}
    selected, handles, prepared, consumed = {}, {}, {}, set()
    version_handles, receipts, refusals_by_tool = {}, [], {}
    revision, citations_checked, submitted = 0, 0, False
    submit_invocation, submit_data = None, None
    operations = Counter()
    paging = PagingObservation()
    refusals, order = 0, 0
    near_expected, near_done = None, False
    additions, repeated_payloads = {}, 0
    rows = []
    for placement, ((opened, started), (closed_at, ended)) in enumerate(zip(starts, ends), 1):
        folder = placement_evidence(placement)
        check(started['arrangement_sha256'] == digest(arrangement_raw)
              and started['provider']['proxy'] is None
              and (started['provider']['base_url'].startswith('http://127.0.0.1:') if binding['mode'] == 'rehearse'
                   else started['provider']['base_url'] == packet['endpoint']), 'placement_arrangement_and_route')
        intent = e.json(folder + 'launch-intent.json')
        check(intent['placement'] == placement and intent['reference'] == receipt['reference']
              and intent['automatic_continuation'] is False, 'placement_launch_intent')
        command = e.json(commands[placement-1])
        check(command['argv'][1:3] == ['run', receipt['reference']], 'placement_command_identity')
        state = e.json(observed[placement-1])['data']['runs']
        check(state['held'] is False and state['count'] == placement and state['last']['number'] == placement
              and [state['last'][key] for key in ['ending', 'cause', 'recorded_by']]
                  == [ended[key] for key in ['ending', 'cause', 'recorded_by']], 'placement_status_observation')
        # INTERFACE 5.7: exit status 5 for an interrupted ending, 0 for any other recorded one.
        check(command['timed_out'] is False and command['exit'] == (5 if ended['ending'] == 'interrupted' else 0),
              'run_exit_status')
        runbase = base + f'runs/{placement}/'
        requests = sorted([n for n in e.names if re.fullmatch(re.escape(runbase) + r'request-[1-9][0-9]*\.json', n)],
                          key=lambda n: int(n.rsplit('-', 1)[1][:-5]))
        check(len(requests) == ended['requests'] and [n[len(runbase):] for n in requests]
              == [f'request-{i}.json' for i in range(1, len(requests) + 1)], 'request_membership')
        results = sorted([n for n in e.names if re.fullmatch(re.escape(runbase) + r'result-[1-9][0-9]*\.json', n)],
                         key=lambda n: int(n.rsplit('-',1)[1][:-5]))
        answered = {}
        for name in results:
            node = rawjson.parse(e.read(name)).get('body')
            answered.setdefault((node.get('request').value(), node.get('attempt').value()), []).append(node)
        spent = {key: dict(value) for key, value in total.items()}
        active, taken, stops, written, after, facts = [], {}, {}, {}, {}, {}
        attempts_seen = []
        fake_exchange = 0
        for number, name in enumerate(requests, 1):
            raw = e.read(name)
            reqnode = rawjson.parse(raw)
            req = reqnode.value()
            check(raw.endswith(b'\n') and req['request'] == number and req['compaction'] is False
                  and req['reset'] is False, 'ordinary_request_capture')
            appended = [item.raw for item in reqnode.get('appended').items]
            # A placement's conversation starts empty: no earlier one is replayed (INTERFACE 6.7).
            active.extend(appended)
            body = ordinary_body(arrnode, req['max_tokens'], active)
            check(len(body) == req['body_bytes'] and digest(body) == req['body_sha256'], 'request_body_binding')
            request_bodies[placement, number] = body
            opening = [{'type':'text','text':qbody.decode()}]
            if placement == 1:
                check(strict_json(body)['messages'][0] == {'role': 'user', 'content': opening}, 'first_question_unchanged')
            else:
                check(strict_json(body)['messages'][0] == {'role': 'user', 'content': opening
                      + [{'type':'text','text':spec.CONTINUATION}]}, 'continuation_notice_first_message')
            if number == 1:
                expected = [first_message(qbody.decode(), placement > 1)]
            else:
                # INTERFACE 6.2: the response's content verbatim, then one result per
                # tool_use block in order, the reminder when planned for this
                # request, then the near-limit notice when planned for it.
                check(number - 1 in taken, 'request_follows_a_used_response')
                previous = responses[placement, number - 1, taken[number - 1]]
                blocks = sorted(answered.get((number - 1, taken[number - 1]), []), key=lambda node: node.get('block').value())
                check([node.get('block').value() for node in blocks]
                      == [i for i, block in enumerate(previous.get('content').items)
                          if block.kind == 'object' and block.get('type') is not None and block.get('type').value() == 'tool_use'],
                      'every_tool_block_answered')
                carried = [b'{"type":"tool_result","tool_use_id":' + node.get('tool_use_id').raw + b',"content":'
                           + node.get('content').raw + b',"is_error":' + node.get('is_error').raw + b'}' for node in blocks]
                for kind in ['reminder', 'near_limit']:
                    carried += [text_block(body_['text']) for body_ in planned.get((placement, number), []) if body_['type'] == kind]
                expected = [b'{"role":"assistant","content":' + previous.get('content').raw + b'}', user_message(carried)]
            check(appended == expected, 'conversation_message_layout')
            # Allowances are cumulative across placements (INTERFACE 6.4).
            remaining = limits['output_tokens'] - sum(total['output_tokens'].values())
            check(req['max_tokens'] == min(16000, remaining) and remaining >= 1024
                  and all(sum(total[k].values()) < limits[k] for k in ['turns', 'input_tokens']), 'request_allowances')
            attempt_names = sorted([n for n in e.names if re.fullmatch(re.escape(runbase) + f'attempt-{number}-[1-9][0-9]*\\.json', n)],
                                   key=lambda n: int(n.rsplit('-', 1)[1][:-5]))
            # A stop can come between a request's capture and its first attempt;
            # only then, and only for the placement's last request, is there none.
            stopped = ended['ending'] == 'stopped_by_close' or (ended['ending'], ended['cause']) == ('interrupted', 'signal')
            check((0 < len(attempt_names) <= 4 or not attempt_names and number == len(requests) and stopped)
                  and [n[len(runbase):] for n in attempt_names]
                  == [f'attempt-{number}-{i}.json' for i in range(1, len(attempt_names)+1)], 'attempt_membership')
            written[number], facts[number] = [], []
            for attempt_number, attempt_name in enumerate(attempt_names, 1):
                check(all(sum(total[k].values()) < limits[k] for k in ['turns','input_tokens'])
                      and limits['output_tokens']-sum(total['output_tokens'].values()) >= 1024,
                      'attempt_within_allowances')
                attempt_record = e.json(attempt_name)
                a = attempt_record['body']
                check(attempt_record['kind'] == 'provider_attempt' and a['request'] == number
                      and a['attempt'] == attempt_number and a['timeout_seconds'] == 600, 'attempt_identity')
                check(a['credential_reflection'] == {'body': False, 'headers': []}, 'clean_reflection_marker')
                check(a['outcome'] in spec.ATTEMPT_OUTCOMES and a['request_written'] in ['none', 'partial', 'complete']
                      and a['then'] in ['use', 'retry', 'end'], 'attempt_vocabulary')
                written[number].append(a['request_written'])
                facts[number].append({'attempt': attempt_number, 'outcome': a['outcome'],
                    'request_written': a['request_written'], 'charge_basis': a['charged']['basis']})
                response = None
                if a['response'] is not None:
                    member = a['response']
                    # Only a response that was used as one must be whole; a stop or a
                    # lost connection can cut a body off (INTERFACE 4.5).
                    check(member['file'] == f'response-{number}-{attempt_number}.bin'
                          and (member['complete'] is True or member['complete'] is False and a['outcome'] in
                               ['response_undecodable', 'http_error', 'timeout', 'connection_lost',
                                'aborted_by_close', 'aborted_by_signal']), 'response_membership')
                    rr = e.read(runbase + member['file'], 32 * 1024 * 1024)
                    check(len(rr) == member['bytes'] and digest(rr) == member['sha256'], 'response_binding')
                    response_names.add(runbase + member['file'])
                    if a['outcome'] == 'response':
                        response = rawjson.parse(rr)
                        responses[placement, number, attempt_number] = response
                if binding['mode'] == 'rehearse':
                    # The fake keeps what reached it. A request whose response Stewart
                    # captured must be there with those bytes. One written without a
                    # captured response may or may not have been read by the fake
                    # before it shut down; if it was, the bytes must agree.
                    sent_ = f'{folder}fake-provider/request-{fake_exchange + 1}.json'
                    kept = f'{folder}fake-provider/response-{fake_exchange + 1}.json'
                    if a['response'] is not None:
                        fake_exchange += 1
                        check(e.read(sent_) == body and (e.read(kept) == rr if a['response']['complete']
                              else e.read(kept).startswith(rr)), 'independent_exchange_bytes')
                    elif a['request_written'] != 'none' and sent_ in e.names:
                        fake_exchange += 1
                        check(e.read(sent_) == body, 'independent_exchange_bytes')
                if a['outcome'] == 'response':
                    value = response.value()
                    counts = usage_counts(value['usage'])
                    check(a['usage'] == counts and a['stop_reason'] == value['stop_reason'], 'reported_response_usage')
                    charge = {'basis': 'reported', 'turns': 1,
                              'input_tokens': sum(counts[k] for k in counts if k != 'output_tokens'),
                              'output_tokens': counts['output_tokens']}
                    check(charge['output_tokens'] <= req['max_tokens'], 'response_output_cap')
                    if a['then'] == 'use':
                        for block_index, block in enumerate(response.get('content').items):
                            if block.get('type') is not None and block.get('type').value() == 'tool_use':
                                response_blocks[placement, number, attempt_number, block_index] = block.raw
                elif a['outcome'] in ['http_error', 'connection_failed'] or a['request_written'] == 'none':
                    charge = {'basis': 'none', 'turns': 0, 'input_tokens': 0, 'output_tokens': 0}
                else:
                    # Estimated, including a request aborted by a signal once any byte was written.
                    charge = {'basis': 'estimated', 'turns': 1, 'input_tokens': (len(body) + 2)//3,
                              'output_tokens': req['max_tokens']}
                check(a['charged'] == charge, 'attempt_charge')
                if attempt_number < len(attempt_names):
                    check(a['then'] == 'retry' and (a['outcome'] in ['timeout','connection_failed','connection_lost']
                          or a['outcome']=='http_error' and a['status'] in [408,429,500,502,503,504,529]), 'retry_policy')
                else:
                    check(a['then'] in ['use', 'end'] and (a['then'] == 'end' or a['outcome'] == 'response'), 'last_attempt_decision')
                    if a['then'] == 'use':
                        taken[number] = attempt_number
                        stops[number] = a['stop_reason']
                if charge['basis'] != 'none':
                    for key in LIMITS:
                        total[key][charge['basis']] += charge[key]
                due, left = near_limit(limits, used())
                if due and not near_done:
                    # Triggered once, when an attempt's accounting first crosses the threshold.
                    near_done, near_expected = True, {'type': 'near_limit', 'run': placement, 'request': number + 1,
                        'text': spec.NEAR_LIMIT.format(**left), 'remaining': left}
                attempts_seen.append(attempt_name)
            after[number] = copy.deepcopy(total)
        if binding['mode'] == 'rehearse':
            check(len([n for n in e.names if re.fullmatch(re.escape(folder) + r'fake-provider/request-[0-9]+\.json', n)])
                  == fake_exchange, 'independent_exchange_count')
        check(len(attempts_seen) == ended['attempts'], 'attempt_count')
        check(set(attempts_seen) == {n for n in e.names if n.startswith(runbase + 'attempt-')}, 'no_orphan_attempts')
        check({n for n in response_names if n.startswith(runbase)} == {n for n in e.names if n.startswith(runbase + 'response-')}, 'no_orphan_responses')
        charged = {key: {basis: total[key][basis] - spent[key][basis] for basis in ['reported', 'estimated']} for key in LIMITS}
        check(charged == ended['usage'], 'placement_usage')
        # INTERFACE 5.6: status totals are every ended placement's usage, never one placement's alone.
        check(e.json(observed[placement-1])['data']['allowances'] == {key: {'used': sum(total[key].values()),
              **total[key], 'limit': limits[key]} for key in LIMITS}, 'placement_status_allowances')
        check(ended['ending'] != 'limit_reached' or limit_exhausted(limits, used()), 'limit_reached_from_cumulative_usage')

        check([n[len(runbase):] for n in results] == [f'result-{i}.json' for i in range(1,len(results)+1)], 'result_membership')
        check({n for n in e.names if n.startswith(runbase + 'call-')} == {runbase + f'call-{i}.json' for i in range(1,len(results)+1)}, 'call_membership')
        previous_results, sealed_in = {}, None
        for call_number, name in enumerate(results, 1):
            result_record = e.json(name)
            result = result_record['body']
            check(result_record['kind'] == 'tool_result' and result['call'] == call_number
                  and result['call_file'] == f'call-{call_number}.json', 'tool_result_identity')
            raw = e.read(runbase + result['call_file'])
            location = placement, result['request'], result['attempt'], result['block']
            check(location not in used_blocks and response_blocks.get(location) == raw
                  and len(raw) == result['call_bytes'] and digest(raw) == result['call_sha256'], 'tool_response_binding')
            used_blocks.add(location)
            callnode = rawjson.parse(raw)
            call = callnode.value()
            tool = call.get('name')
            check(tool == result['tool'] and call.get('id') == result['tool_use_id'], 'tool_identity')
            operands = callnode.get('input')
            check((digest(operands.raw) if operands else None) == result['input_sha256'], 'tool_input_binding')
            reply = strict_json(result['content'][0]['text'])
            check(reply['schema'] == spec.REPLY_SCHEMA, 'tool_reply_schema')
            check(reply['outcome'] == result['outcome'] and reply['operation'] == tool, 'tool_reply_binding')
            paging.observe(tool, strict_json(operands.raw) if operands else None, reply)
            previous_results[call_number] = result
            known = tool in {item['name'] for item in arr['tools']}
            operations[tool if known else 'unknown_tool'] += 1
            order += 1
            if result['outcome'] != 'completed':
                refusals += 1
                if known and result['replay_of'] is None:
                    refusals_by_tool[tool] = (order, {'run': placement, 'tool_use_id': call['id'], 'tool': tool,
                        'outcome': result['outcome'], 'reason': result['reason'], 'revision': result['revision']})
                continue
            if result['replay_of'] is not None:
                # A replay is a repeated block of the same placement (INTERFACE 6.3).
                check(type(result['replay_of']) is int and 0 < result['replay_of'] < call_number, 'invocation_replay')
                old = previous_results[result['replay_of']]
                check(all(result[field] == old[field] for field in ['content','is_error','outcome','log_record']), 'replayed_outcome_unchanged')
                continue
            data, inp = reply['data'], strict_json(operands.raw)
            if tool == 'what_am_i_working_with' and 'page' not in inp:
                check(data['family'] == versioned_family, 'reentry_captured_family')
                check(data['authoring'] == {'state':'open','ended_by':None}
                      and data['seal'] == {'state':'absent','actor':None}, 'reentry_authoring_and_seal')
                # INTERFACE 7.5 from the ledger as this review has followed it, across placements.
                at = after[result['request']]
                listed = [{'id': entry.id, 'entry': version_handles[entry.id, entry.version], 'kind': entry.kind,
                           'label': entry.label, 'encoding': entry.encoding, 'size': len(entry.data), 'problem': None}
                          for entry in selected.values()]
                check(data['audit'] == audit and data['revision'] == revision
                      and data['run'] == {'number': placement, 'continuing': placement > 1}
                      and data['allowances'] == {key: {'used': sum(at[key].values()), **at[key], 'limit': limits[key]} for key in LIMITS}
                      and data['notices_used'] == {
                          'reminder': any(b['type'] == 'reminder' and (b['run'], b['request']) <= (placement, result['request']) for _, b in notices),
                          'near_limit': any(b['type'] == 'near_limit' and (b['run'], b['request']) <= (placement, result['request'] + 1) for _, b in notices)}
                      and [{key: item[key] for key in listed[0]} if listed else item for item in data['entries']] == listed[:64]
                      and all(item['preview'] is None if entry.encoding == 'binary' else
                              (item['preview'], item['preview_complete']) == (preview(entry.data), len(entry.data) <= 200)
                              for item, entry in zip(data['entries'], selected.values()))
                      and data['receipts'] == receipts[::-1][:16]
                      and data['latest_refusals'] == [row for _, row in sorted(refusals_by_tool.values(), key=lambda item: -item[0])]
                      and data['gaps'] == []
                      and data['question']['size'] == len(qbody)
                      and data['materials'] == {'count': len(sources) - 1, 'bytes': sum(len(v) for k, v in sources.items() if k != 'question')}
                      and data['page']['bound_revision'] == revision and data['page']['total'] == len(listed)
                      and data['page']['complete'] is (len(listed) <= 64), 'reentry_recorded_state')
            log_name = result['log_record']
            # INTERFACE 4.5: the entry or seal record the call published, or null.
            # A completed mutation published exactly one entry record of its own;
            # no second call, in this placement or a later one, may claim it.
            check(log_name not in consumed, 'entry_effect_claimed_once')
            check((log_name in entry_records) is (tool in ['replace', 'delete'] or isinstance(tool, str) and tool.startswith('record_')),
                  'entry_effect_binding')
            if log_name in entry_records and log_name not in consumed:
                record = entry_records[log_name]['body']
                check(record['invocation'] == {'run': placement, 'tool_use_id': call['id'], 'call': call_number}
                      and record['tool'] == tool, 'entry_invocation')
                check(opened < index[log_name] < closed_at, 'entry_within_placement')
                revision += 1
                check(record['revision'] == revision, 'entry_revision')
                receipt_row = {'run': placement, 'tool_use_id': call['id'], 'tool': tool, 'action': record['action'],
                               'target': None, 'entry': None, 'revision': revision}
                if record['action'] == 'delete':
                    target = handles.get(inp['entry'])
                    check(target is not None and record['target']['id'] == target[0]
                          and record['target']['version'] == target[1] and target[0] in selected, 'delete_target')
                    del selected[target[0]]
                    receipt_row['target'] = inp['entry']
                else:
                    if record['action'] == 'replace':
                        target = handles.get(inp['entry'])
                        check(target is not None and target[0] in selected and selected[target[0]].version == target[1]
                              and record['id'] == target[0] and record['version'] == target[1]+1, 'replace_target')
                        kind = selected[target[0]].kind
                        receipt_row['target'] = inp['entry']
                    else:
                        check(record['action'] == 'add' and record['id'] not in selected and record['version'] == 1, 'addition_identity')
                        kind = tool
                    payload = base64.b64decode(inp['base64'], validate=True) if 'base64' in inp else inp['text'].encode()
                    citations = [] if kind == 'record_artifact' else [answer.record_citation(c, sources) for c in inp.get('citations', [])]
                    citations_checked += len(citations)
                    encoding = ('binary' if 'base64' in inp else 'utf-8') if kind == 'record_artifact' else None
                    check(record['kind'] == kind and record['label'] == inp.get('label','')
                          and record['citations'] == (None if kind == 'record_artifact' else citations)
                          and record['encoding'] == encoding, 'entry_fields_and_citations')
                    p = record['payload']
                    check(e.read(base + relative(p['file'])) == payload and p['sha256'] == digest(payload)
                          and p['size'] == len(payload), 'payload_matches_authored_bytes')
                    if record['action'] == 'add':
                        # Equal bytes are a fresh entry, not evidence of a replay; counted for a reader.
                        repeated_payloads += any(run != placement for run in additions.get((kind, digest(payload)), []))
                        additions.setdefault((kind, digest(payload)), []).append(placement)
                    selected[record['id']] = answer.Entry(record['id'], record['version'], kind, record['label'], payload, citations, encoding)
                    handles[data['entry']] = (record['id'], record['version'])
                    version_handles[record['id'], record['version']] = data['entry']
                    receipt_row['entry'] = data['entry']
                receipts.append(receipt_row)
                consumed.add(log_name)
            if tool == 'prepare':
                check(data['family'] == versioned_family, 'preparation_captured_family')
                check(data['revision'] == revision and data['entry_count'] == len(selected), 'preparation_counts')
                prepared[data['prepared']] = (revision, answer.answer_json(revision, list(selected.values())), answer.render(list(selected.values())))
            if tool == 'submit' and inp.get('confirm') is True:
                check(inp['prepared'] in prepared and prepared[inp['prepared']][0] == revision
                      and data['seal']['state'] == 'present' and data['seal']['actor'] == 'auditor', 'confirmed_submission')
                submitted = True
                submit_invocation = {'run':placement,'tool_use_id':call['id'],'call':call_number}
                submit_data = data
                sealed_in = result['request']
            check(result['revision'] == revision, 'tool_revision')
        # Blocks run in order. A stop path can leave the last response's later
        # blocks unexecuted (INTERFACE 6.3); nothing else may.
        unexecuted = 0
        for number, attempt_number in taken.items():
            wanted = sorted(i for (run, k, a, i) in response_blocks if (run, k, a) == (placement, number, attempt_number))
            done = sorted(i for (run, k, a, i) in used_blocks if (run, k, a) == (placement, number, attempt_number))
            check(done == wanted[:len(done)], 'tool_blocks_executed_in_order')
            check(done == wanted or number == len(requests)
                  and ended['ending'] in ['stopped_by_close', 'interrupted', 'damaged'], 'all_used_tool_blocks_accounted')
            unexecuted += len(wanted) - len(done)
        # The reminder (INTERFACE 6.3, 6.4): after an unsealed end_turn or
        # stop_sequence with allowance left, once per audit; afterwards such an
        # ending ends authoring.
        for number in taken:
            ordinary = stops[number] in ['end_turn', 'stop_sequence'] and sealed_in != number
            mine = reminder is not None and (reminder['run'], reminder['request']) == (placement, number + 1)
            check(not mine or ordinary and not limit_exhausted(limits, {key: sum(after[number][key].values()) for key in LIMITS}),
                  'reminder_only_after_ordinary_ending')
            if ordinary and number < len(requests):
                check(mine, 'request_after_ordinary_ending_carries_the_reminder')
        last = len(requests)
        spent_before = reminder is not None and (reminder['run'], reminder['request']) <= (placement, last)
        check(ended['ending'] != 'ended_unsubmitted' or last in taken and stops[last] in ['end_turn', 'stop_sequence']
              and sealed_in != last and spent_before, 'unsubmitted_ending_after_spent_reminder')
        check(reminder is None or reminder['run'] != placement or reminder['request'] - 1 in taken, 'reminder_only_after_ordinary_ending')
        mine = [(position, body) for position, body in notices if body['run'] == placement]
        check(ended['notices'] == [{'type': body['type'], 'record': f'log/{position}.json',
              'sent': notice_sent(body['request'] <= len(requests), written.get(body['request'], []))}
              for position, body in mine], 'run_ended_notices')
        check(ended['seal'] == (f'log/{seal_position}.json' if seal_position is not None
              and opened < seal_position < closed_at else None), 'run_ended_seal')
        row = {'run': placement, 'continuing': started['continuing'], 'ending': ended['ending'],
               'cause': ended['cause'] if ended['cause'] in CAUSES else 'unknown', 'recorded_by': ended['recorded_by'],
               'requests': ended['requests'], 'attempts': ended['attempts'], 'usage': charged,
               'notices': [{'type': item['type'], 'sent': item['sent']} for item in ended['notices']],
               'unexecuted_tool_blocks': unexecuted, 'exit': command['exit'], 'interruption': None}
        if intent.get('interruption') is not None:
            row['interruption'] = interruption_witness(e, check, folder + 'interruption/', intent['interruption'],
                placement, base, by_name, index, (opened, closed_at), started, ended, command, len(requests), facts)
        rows.append(row)
    # INTERFACE 6.4: published when triggered, naming the next request, with the remaining amounts.
    check(next(({key: body[key] for key in ['type', 'run', 'request', 'text', 'remaining']}
                for _, body in notices if body['type'] == 'near_limit'), None) == near_expected,
          'near_limit_from_cumulative_usage')
    report['placements'] = rows
    report['usage'] = total
    report['ending'], report['cause'] = rows[-1]['ending'], rows[-1]['cause']
    report['witness_scope']['notices'] = ('the fake independently kept each request that carried a notice'
        if binding['mode'] == 'rehearse' else 'Stewart-owned request captures and attempt records; transmission not independently observed')
    if any(row['interruption'] is not None for row in rows):
        report['witness_scope']['interruption'] = ('launcher observation of the log record, process identity, signal and exit, '
            'kept outside the archive; the stop path and its charge are Stewart-recorded')
    check(consumed == set(entry_records), 'all_entry_effects_accounted')
    report['coverage'] = {'operations': dict(operations), 'refused_or_failed_calls': refusals,
        'citations_checked': citations_checked, 'selected_entries': len(selected),
        'pagination':paging.counts,
        'unused_tools': [tool['name'] for tool in arr['tools'] if not operations[tool['name']]],
        'equal_payload_additions_in_a_later_placement': repeated_payloads}
    seals = [r for r in records if r['kind'] == 'seal']
    report.update(auditor_submitted=False, seal_actor=None, delivery_verified=False,
                  closed=any(r['kind']=='closed' for r in records))
    if seals:
        check(len(seals) == 1, 'single_seal')
        seal = seals[0]['body']
        report['seal_actor'] = seal['actor'] if seal['actor'] in ['auditor','manager'] else 'unknown'
        if seal['actor'] == 'auditor':
            check(submitted and seal['invocation'] == submit_invocation
                  and submit_data['seal']['manifest_sha256'] == seal['manifest_sha256']
                  and submit_data['seal']['revision'] == seal['revision'], 'seal_submission_binding')
        check(seal['revision'] == revision, 'sealed_revision')
        expected_answer = answer.answer_json(revision, list(selected.values()))
        expected_render = answer.render(list(selected.values()))
        check(e.read(base + f"prepared/{seal['prepared']}/answer.json") == expected_answer
              and e.read(base + f"prepared/{seal['prepared']}/answer.md") == expected_render,
              'prepared_answer_and_rendering')
        manifest_raw = e.read(base + relative(seal['manifest']))
        manifest = strict_json(manifest_raw)
        check(digest(manifest_raw) == seal['manifest_sha256'] and seal['answer_sha256'] == digest(expected_answer)
              and seal['rendering_sha256'] == digest(expected_render), 'seal_digests')
        expected_manifest = answer.manifest(audit, receipt['store'], versioned_family, binding['binary_sha256'],
            seal['actor'], manifest['seal']['sealed_at'], revision,
            answer.members(list(selected.values()), expected_answer, expected_render))
        check(manifest_raw == expected_manifest, 'manifest_from_witnessed_selection')
        delivered = [r['body'] for r in records if r['kind']=='delivery_ended' and r['body']['outcome']=='verified']
        if delivered:
            delivery = delivered[-1]
            check(Path(delivery['package']).parent == Path(binding['destination']), 'delivery_destination')
            package = 'returns/' + Path(delivery['package']).name + '/'
            members = {'manifest.json': manifest_raw, 'answer.json': expected_answer, 'answer.md': expected_render}
            members.update({entry.member: entry.data for entry in selected.values() if entry.kind == 'record_artifact'})
            check(delivery['manifest_sha256'] == digest(manifest_raw) and not delivery['losses'], 'delivery_seal_binding')
            check({n[len(package):] for n in e.names if n.startswith(package)} == set(members), 'delivery_membership')
            for name, content in members.items():
                check(e.read(package + name) == content, 'exact_delivered_bytes')
            report['delivery_verified'] = True
        report['auditor_submitted'] = submitted and seal['actor'] == 'auditor'
    report['outcome'] = 'checked'


def serial_commands(names, pattern):
    """The launcher's numbered command records of one kind, in the order issued."""
    return sorted((name for name in names if re.fullmatch(pattern, name)),
                  key=lambda name: int(name[len('evidence/'):].split('-', 1)[0]))


def signal_timing(captured, attempts):
    """Where the stop found one request, in the terms INTERFACE 6.4 charges and reports it."""
    if not captured:
        return 'not_captured'
    if any(row['outcome'] == 'response' for row in attempts):
        return 'answered'
    return 'written_unanswered' if any(row['request_written'] != 'none' for row in attempts) else 'captured_not_written'


def interruption_witness(e, check, folder, planned, placement, base, by_name, index, bounds, started, ended, command,
                         captured, facts):
    """Bind the launcher's witness of a planned interruption to the placement's own records.

    The witness says what was seen from outside and what was sent. Whether the
    placement then ended by that signal is reported as a fact, not required: a
    seal recorded first still ends `sealed` (INTERFACE 6.8).
    """
    chosen = e.json(folder + 'selected.json')
    check(chosen['point'] == planned['after'] and chosen['signal'] == planned['signal'] == 'SIGTERM', 'interruption_witness')
    matching = [name for name, record in by_name.items() if bounds[0] < index[name] < bounds[1] and (
        record['kind'] == 'notice' and record['body']['type'] == 'reminder' if planned['after'] == 'reminder_notice'
        else record['kind'] == 'entry')]
    if folder + 'unexercised.json' in e.names:
        missed = e.json(folder + 'unexercised.json')
        check(missed['signal_sent'] is False and folder + 'signal.json' not in e.names
              and missed['reason'] in ['placement_ended_first', 'watchdog_expired_first', 'placement_ended_at_the_point'],
              'interruption_witness')
        return {'point': planned['after'], 'state': 'unexercised', 'reason': missed['reason'], 'record': None,
                'point_record_published': bool(matching), 'followed_by_signal_ending': False}
    point, sent, stopped = [e.json(folder + name + '.json') for name in ['point', 'signal', 'termination']]
    # The first such record of this placement, by name and bytes.
    check(point['point'] == planned['after'] and matching and point['record'] == matching[0]
          and digest(e.read(base + point['record'])) == point['sha256'], 'interruption_witness')
    seen, recorded = point['process'], started['observations']
    check(seen['pid'] == recorded['pid'] == command['pid'] == sent['process_group']
          and (seen['start_ticks'] is None or recorded['start_ticks'] is None or seen['start_ticks'] == recorded['start_ticks'])
          and (seen['uid'] is None or seen['uid'] == recorded['uid']), 'interruption_witness')
    check(sent['signal'] == 'SIGTERM' and sent['number'] == 15 and point['observed_at'] <= sent['sent_at'] <= stopped['observed_at']
          and stopped['exit'] == command['exit'] and stopped['timed_out'] is False, 'interruption_witness')
    # What the signal found. No timing is required; the witness's account must be
    # the one the placement's own records give, and for the reminder it must
    # agree with the `sent` state INTERFACE 6.4 derives from the same records.
    notice = by_name[point['record']]['body'] if planned['after'] == 'reminder_notice' else None
    request = notice['request'] if notice is not None else (captured or None)
    rows = facts.get(request, [])
    timing = signal_timing(request is not None and request <= captured, rows)
    told = e.json(folder + 'timing.json')
    before = point['run_directory_when_seen']
    check({key: told[key] for key in ['placement', 'request', 'named_by_the_notice', 'request_captured', 'attempts',
                                      'requests_captured', 'timing']}
          == {'placement': placement, 'request': request, 'named_by_the_notice': notice is not None,
              'request_captured': request is not None and request <= captured, 'attempts': rows,
              'requests_captured': captured, 'timing': timing}
          and before['request_captures'] <= captured
          and before['attempt_records'] <= sum(len(item) for item in facts.values()), 'interruption_timing')
    if notice is not None:
        sent_state = next(item['sent'] for item in ended['notices'] if item['record'] == point['record'])
        check(sent_state == {'not_captured': 'not_sent', 'captured_not_written': 'unknown',
                             'written_unanswered': 'sent', 'answered': 'sent'}[timing], 'interruption_timing')
    return {'point': planned['after'], 'state': 'signalled', 'record': point['record'],
            'timing': timing, 'request': request,
            'request_written': [row['request_written'] for row in rows],
            'charge_basis': [row['charge_basis'] for row in rows],
            'process_identity_compared': [key for key in ['pid', 'start_ticks', 'uid']
                                          if seen[key] is not None and recorded.get(key) is not None],
            'process_group_gone': stopped['process_group_gone'],
            'followed_by_signal_ending': ended['ending'] == 'interrupted' and ended['cause'] == 'signal'}


def inventory_from_evidence(e, prefix):
    # Include empty directories through the independently recorded inventory;
    # regular member identities are compared here, directory membership at intake.
    return [{'path': name[len(prefix):], 'bytes': len(e.read(name)), 'sha256': digest(e.read(name))}
            for name in sorted(e.names) if name.startswith(prefix)]


def tree_inventory_from_evidence(e, prefix):
    """Reproduce the template identity, including empty directory membership."""
    names = {name[len(prefix):] for name in e.names | e.directories if name.startswith(prefix)}
    result = []
    def visit(parent):
        for name in sorted(n for n in names if str(Path(n).parent) == (parent or '.')):
            if prefix + name in e.directories:
                result.append({'path': name, 'type': 'directory'})
                visit(name)
            else:
                raw = e.read(prefix + name)
                result.append({'path': name, 'type': 'file', 'bytes': len(raw), 'sha256': digest(raw)})
    visit('')
    require(len(result) == len(names), 'study_template_membership')
    return result
