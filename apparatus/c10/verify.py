"""Read-only procedural review, with explicit witness scope and no quality grade."""
import base64
from collections import Counter
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
    report = {'schema': 'stewart.c10-review/1', 'outcome': 'incomplete',
        'checks': [], 'failures': [], 'coverage': {}, 'model_qualified': False,
        'unassessed': ['full C10 repetition matrix', 'compaction', 'interrupted continuation'],
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
    return report


def _verify(e, report, check):
    binding = e.json('evidence/binding.json')
    check(binding['schema'] == 'stewart.c10-audit/1', 'audit_binding_schema')
    packet, run = binding['commission'], binding['run']
    family = binding['family']
    specimen = e.json('evidence/specimen.json')
    if run.get('submission_folder') is not None:
        check(packet['schema'] == 'stewart.study-commission/1' and run in packet['runs'], 'study_packet_binding')
        template = tree_inventory_from_evidence(e, 'evidence/submission-template/')
        check(digest(compact(template)) == run['submission_sha256'], 'study_template_binding')
        case = case_from_question(e.read('evidence/submission-template/question.md'), run['case'])
        check(specimen == {'case': case, 'materials': [item for item in template if item['path'] != 'question.md']},
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
          and receipt['settings'].get('effort') == packet['effort'], 'commission_settings')
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
    check(arr['family'] == family + '/1' and arr['model'] == packet['model']
          and arr['limits'] == packet['limits'], 'arrangement_settings')
    check(arrnode.get('system').raw == spec.expected_system_bytes(family)
          and arrnode.get('tools').raw == compact(spec.expected_tools(family)), 'specified_system_and_tools')
    expected_extra = {} if packet['effort'] is None else {'output_config': {'effort': packet['effort']}}
    check(arr['request_extra'] == expected_extra, 'effort_parameter')
    check(arr['max_tokens_per_request'] == 16000 and arr['request_timeout_seconds'] == 600,
          'release_request_bounds')
    started, ended = one('run_started')['body'], one('run_ended')['body']
    check(started['run'] == ended['run'] == 1 and started['continuing'] is False,
          'single_placement')
    check(started['arrangement_sha256'] == digest(arrangement_raw)
          and started['provider']['proxy'] is None
          and (started['provider']['base_url'].startswith('http://127.0.0.1:') if binding['mode'] == 'rehearse'
               else started['provider']['base_url'] == packet['endpoint']), 'placement_arrangement_and_route')
    runbase = base + 'runs/1/'
    check({name[len(base + 'runs/'):].split('/')[0] for name in e.names if name.startswith(base + 'runs/')} == {'1'}, 'run_membership')
    requests = sorted([n for n in e.names if re.fullmatch(re.escape(runbase) + r'request-[1-9][0-9]*\.json', n)],
                      key=lambda n: int(n.rsplit('-', 1)[1][:-5]))
    check(len(requests) == ended['requests'] and [n[len(runbase):] for n in requests]
          == [f'request-{i}.json' for i in range(1, len(requests) + 1)], 'request_membership')
    total = {key: {'reported': 0, 'estimated': 0} for key in LIMITS}
    responses, response_blocks, used_blocks = {}, {}, set()
    request_bodies, attempts_seen, response_names = {}, [], set()
    active = []
    fake_exchange = 0
    for number, name in enumerate(requests, 1):
        raw = e.read(name)
        reqnode = rawjson.parse(raw)
        req = reqnode.value()
        check(raw.endswith(b'\n') and req['request'] == number and req['compaction'] is False
              and req['reset'] is False, 'ordinary_request_capture')
        active.extend(item.raw for item in reqnode.get('appended').items)
        extra = arrnode.get('request_extra')
        suffix = b''.join(b',' + extra.data[start:value.end] for _, start, _, value in extra.members)
        body = (b'{"model":' + arrnode.get('model').raw + b',"max_tokens":' + str(req['max_tokens']).encode()
            + b',"system":' + arrnode.get('system').raw + b',"tools":' + arrnode.get('tools').raw
            + suffix + b',"messages":[' + b','.join(active) + b']}')
        check(len(body) == req['body_bytes'] and digest(body) == req['body_sha256'], 'request_body_binding')
        request_bodies[number] = body
        check(strict_json(body)['messages'][0] == {'role': 'user', 'content': [{'type':'text','text':qbody.decode()}]}, 'first_question_unchanged')
        remaining = packet['limits']['output_tokens'] - sum(total['output_tokens'].values())
        check(req['max_tokens'] == min(16000, remaining) and remaining >= 1024
              and all(sum(total[k].values()) < packet['limits'][k] for k in ['turns', 'input_tokens']), 'request_allowances')
        attempt_names = sorted([n for n in e.names if re.fullmatch(re.escape(runbase) + f'attempt-{number}-[1-9][0-9]*\\.json', n)],
                               key=lambda n: int(n.rsplit('-', 1)[1][:-5]))
        check(0 < len(attempt_names) <= 4 and [n[len(runbase):] for n in attempt_names]
              == [f'attempt-{number}-{i}.json' for i in range(1, len(attempt_names)+1)], 'attempt_membership')
        for attempt_number, attempt_name in enumerate(attempt_names, 1):
            check(all(sum(total[k].values()) < packet['limits'][k] for k in ['turns','input_tokens'])
                  and packet['limits']['output_tokens']-sum(total['output_tokens'].values()) >= 1024,
                  'attempt_within_allowances')
            attempt_record = e.json(attempt_name)
            a = attempt_record['body']
            check(attempt_record['kind'] == 'provider_attempt' and a['request'] == number
                  and a['attempt'] == attempt_number and a['timeout_seconds'] == 600, 'attempt_identity')
            check(a['credential_reflection'] == {'body': False, 'headers': []}, 'clean_reflection_marker')
            response = None
            if a['response'] is not None:
                member = a['response']
                check(member['file'] == f'response-{number}-{attempt_number}.bin' and member['complete'] is True, 'response_membership')
                rr = e.read(runbase + member['file'], 32 * 1024 * 1024)
                check(len(rr) == member['bytes'] and digest(rr) == member['sha256'], 'response_binding')
                response_names.add(runbase + member['file'])
                response = rawjson.parse(rr)
                responses[number, attempt_number] = response
                if binding['mode'] == 'rehearse':
                    fake_exchange += 1
                    check(e.read(f'evidence/fake-provider/request-{fake_exchange}.json') == body
                          and e.read(f'evidence/fake-provider/response-{fake_exchange}.json') == rr,
                          'independent_exchange_bytes')
            if a['outcome'] == 'response':
                value = response.value()
                counts = usage_counts(value['usage'])
                check(a['usage'] == counts and a['stop_reason'] == value['stop_reason'], 'reported_response_usage')
                charge = {'basis': 'reported', 'turns': 1,
                          'input_tokens': sum(counts[k] for k in counts if k != 'output_tokens'),
                          'output_tokens': counts['output_tokens']}
                check(charge['output_tokens'] <= req['max_tokens'], 'response_output_cap')
                if a['then'] == 'use':
                    for index, block in enumerate(response.get('content').items):
                        if block.get('type') is not None and block.get('type').value() == 'tool_use':
                            response_blocks[number, attempt_number, index] = block.raw
            elif a['outcome'] in ['http_error', 'connection_failed'] or a['request_written'] == 'none':
                charge = {'basis': 'none', 'turns': 0, 'input_tokens': 0, 'output_tokens': 0}
            else:
                charge = {'basis': 'estimated', 'turns': 1, 'input_tokens': (len(body) + 2)//3,
                          'output_tokens': req['max_tokens']}
            check(a['charged'] == charge, 'attempt_charge')
            if attempt_number < len(attempt_names):
                check(a['then'] == 'retry' and (a['outcome'] in ['timeout','connection_failed','connection_lost']
                      or a['outcome']=='http_error' and a['status'] in [408,429,500,502,503,504,529]), 'retry_policy')
            if charge['basis'] != 'none':
                for key in LIMITS:
                    total[key][charge['basis']] += charge[key]
            attempts_seen.append(attempt_name)
    check(len(attempts_seen) == ended['attempts'], 'attempt_count')
    check(set(attempts_seen) == {n for n in e.names if n.startswith(runbase + 'attempt-')}, 'no_orphan_attempts')
    check(response_names == {n for n in e.names if n.startswith(runbase + 'response-')}, 'no_orphan_responses')
    check(total == ended['usage'], 'placement_usage')
    report['usage'] = total
    report['ending'] = ended['ending']
    report['cause'] = ended['cause'] if ended['cause'] in [None, 'provider_rejected', 'signal', 'max_tokens',
        'provider_unavailable','context_exhausted','provider_refusal','protocol_anomaly',
        'archive_write_failed','process_gone','credential_reflected'] else 'unknown'
    entry_records = {name: record for name, record in by_name.items() if record['kind'] == 'entry'}
    results = sorted([n for n in e.names if re.fullmatch(re.escape(runbase) + r'result-[1-9][0-9]*\.json', n)],
                     key=lambda n: int(n.rsplit('-',1)[1][:-5]))
    check([n[len(runbase):] for n in results] == [f'result-{i}.json' for i in range(1,len(results)+1)], 'result_membership')
    check({n for n in e.names if n.startswith(runbase + 'call-')} == {runbase + f'call-{i}.json' for i in range(1,len(results)+1)}, 'call_membership')
    selected, handles, prepared, consumed = {}, {}, {}, set()
    revision, citations_checked, submitted = 0, 0, False
    submit_invocation, submit_data, previous_results = None, None, {}
    operations = Counter()
    refusals = 0
    for call_number, name in enumerate(results, 1):
        result_record = e.json(name)
        result = result_record['body']
        check(result_record['kind'] == 'tool_result' and result['call'] == call_number
              and result['call_file'] == f'call-{call_number}.json', 'tool_result_identity')
        raw = e.read(runbase + result['call_file'])
        location = result['request'], result['attempt'], result['block']
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
        check(reply['outcome'] == result['outcome'] and reply['operation'] == tool, 'tool_reply_binding')
        previous_results[call_number] = result
        if tool in {item['name'] for item in arr['tools']}:
            operations[tool] += 1
        else:
            operations['unknown_tool'] += 1
        if result['outcome'] != 'completed':
            refusals += 1
            continue
        if result['replay_of'] is not None:
            check(type(result['replay_of']) is int and 0 < result['replay_of'] < call_number, 'invocation_replay')
            old = previous_results[result['replay_of']]
            check(all(result[field] == old[field] for field in ['content','is_error','outcome','log_record']), 'replayed_outcome_unchanged')
            continue
        data, inp = reply['data'], strict_json(operands.raw)
        log_name = result['log_record']
        if log_name in entry_records and log_name not in consumed:
            record = entry_records[log_name]['body']
            check(record['invocation'] == {'run': 1, 'tool_use_id': call['id'], 'call': call_number}
                  and record['tool'] == tool, 'entry_invocation')
            revision += 1
            check(record['revision'] == revision, 'entry_revision')
            if record['action'] == 'delete':
                target = handles.get(inp['entry'])
                check(target is not None and record['target']['id'] == target[0]
                      and record['target']['version'] == target[1] and target[0] in selected, 'delete_target')
                del selected[target[0]]
            else:
                if record['action'] == 'replace':
                    target = handles.get(inp['entry'])
                    check(target is not None and target[0] in selected and selected[target[0]].version == target[1]
                          and record['id'] == target[0] and record['version'] == target[1]+1, 'replace_target')
                    kind = selected[target[0]].kind
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
                selected[record['id']] = answer.Entry(record['id'], record['version'], kind, record['label'], payload, citations, encoding)
                handles[data['entry']] = (record['id'], record['version'])
            consumed.add(log_name)
        if tool == 'prepare':
            check(data['revision'] == revision and data['entry_count'] == len(selected), 'preparation_counts')
            prepared[data['prepared']] = (revision, answer.answer_json(revision, list(selected.values())), answer.render(list(selected.values())))
        if tool == 'submit' and inp.get('confirm') is True:
            check(inp['prepared'] in prepared and prepared[inp['prepared']][0] == revision
                  and data['sealer'] == 'auditor', 'confirmed_submission')
            submitted = True
            submit_invocation = {'run':1,'tool_use_id':call['id'],'call':call_number}
            submit_data = data
        check(result['revision'] == revision, 'tool_revision')
    check(consumed == set(entry_records), 'all_entry_effects_accounted')
    check(used_blocks == set(response_blocks), 'all_used_tool_blocks_accounted')
    report['coverage'] = {'operations': dict(operations), 'refused_or_failed_calls': refusals,
        'citations_checked': citations_checked, 'selected_entries': len(selected),
        'unused_tools': [tool['name'] for tool in arr['tools'] if not operations[tool['name']]]}
    seals = [r for r in records if r['kind'] == 'seal']
    report.update(auditor_submitted=False, delivery_verified=False, closed=any(r['kind']=='closed' for r in records))
    if seals:
        check(len(seals) == 1, 'single_seal')
        seal = seals[0]['body']
        report['seal_actor'] = seal['actor'] if seal['actor'] in ['auditor','manager'] else 'unknown'
        if seal['actor'] == 'auditor':
            check(submitted and seal['invocation'] == submit_invocation
                  and submit_data['manifest_sha256'] == seal['manifest_sha256']
                  and submit_data['revision'] == seal['revision'], 'seal_submission_binding')
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
        expected_manifest = answer.manifest(audit, receipt['store'], family+'/1', binding['binary_sha256'],
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
    report['outcome'] = ('procedural_checks_passed' if ended['ending'] == 'sealed'
        and report['auditor_submitted'] and report['delivery_verified'] else 'not_submitted')


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
