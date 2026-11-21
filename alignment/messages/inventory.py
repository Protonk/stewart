"""Compare Messages attempt records with their original response bytes in reviewed work exports."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import tarfile


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apparatus/c10'))
from common import strict_json


COUNTS = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')
RUN = re.compile(r'(.*/archive/audits/([^/]+))/runs/(\d+)/(attempt|response)-(\d+)-(\d+)\.(json|bin)')
STOPS = {'tool_use', 'end_turn', 'max_tokens', 'compaction', 'refusal', 'model_context_window_exceeded'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return sha256(raw).hexdigest()


def file_digest(path):
    h = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def shape(observation, request, arrangement, response):
    body = observation['body']
    result = {'status': body['status'], 'outcome': body['outcome'], 'basis': body['charged']['basis'],
              'written': body['request_written'], 'summary_request': request['compaction'],
              'after_reset': request['reset'], 'request_body_sha256': request['body_sha256'],
              'model': arrangement['model'], 'family': arrangement['family'],
              'effort': arrangement['request_extra'].get('output_config', {}).get('effort'),
              'api_version': arrangement['anthropic_version'], 'beta': arrangement['anthropic_beta'],
              'request_id_observed': bool((body.get('headers') or {}).get('request-id'))}
    reflection = body['credential_reflection']
    require(not reflection['body'] and not reflection['headers'], 'positive credential-reflection observation')
    metadata = body['response']
    if response is None:
        require(metadata is None and body['outcome'] != 'response', 'referenced response missing')
        return result
    require(metadata and len(response) == metadata['bytes'] and digest(response) == metadata['sha256'],
            'attempt and response bytes differ')
    result.update(response_sha256=digest(response), complete=metadata['complete'])
    require(metadata['complete'], 'partial response needs separate review')
    envelope = strict_json(response)
    result['members'] = sorted(envelope)
    if envelope['type'] == 'error':
        require(body['outcome'] == 'http_error' and body['status'] >= 400
                and isinstance(envelope['error'].get('message'), str), 'error envelope differs')
        result['error_type'] = envelope['error']['type']
        return result
    require(envelope['type'] == 'message' and body['outcome'] == 'response' and body['status'] == 200,
            'unexpected success envelope')
    require(envelope['model'] == result['model'] == body['model'], 'model identity differs')
    stop = envelope['stop_reason']
    require(stop in STOPS and stop == body['stop_reason'], 'unresolved stop reason')
    usage = envelope['usage']
    iterations = usage.get('iterations')
    rows = [usage] if iterations is None else iterations
    require(isinstance(rows, list) and rows, 'missing usage rows')
    totals = {}
    for key in COUNTS:
        values = [row.get(key) for row in rows]
        require(all((v is None and key.startswith('cache_')) or (type(v) is int and v >= 0)
                    for v in values), 'invalid usage count')
        totals[key] = sum(value or 0 for value in values)
    require(totals == body['usage'] and body['charged']['basis'] == 'reported'
            and sum(totals[k] for k in COUNTS[:-1]) == body['charged']['input_tokens']
            and totals['output_tokens'] == body['charged']['output_tokens'], 'recorded usage differs')
    require(not totals['cache_read_input_tokens'] and not totals['cache_creation_input_tokens'],
            'nonzero cache accounting needs rate-band comparison')
    content = envelope['content']
    require(bool(request['compaction']) == (stop == 'compaction'), 'summary request and response differ')
    if request['compaction']:
        require(stop == 'compaction' and [block['type'] for block in content] == ['compaction']
                and content[0].get('signature') and any(row.get('type') == 'compaction' for row in rows),
                'summary shape differs')
    result.update(stop=stop, blocks=[block['type'] for block in content],
                  block_members=[sorted(block) for block in content],
                  usage_members=sorted(usage), iterations=[row['type'] for row in iterations or []],
                  top_level_zero=usage['input_tokens'] == usage['output_tokens'] == 0,
                  usage=totals)
    return result


def inventory(exports):
    attempts = {}
    sources = []
    for export in exports:
        receipt = export.with_name('EXPORT.json')
        metadata = strict_json(receipt.read_bytes())
        fingerprint = file_digest(export)
        require(metadata['outcome'] == 'exported' and metadata['evidence_state'] == 'complete'
                and metadata['archive']['bytes'] == export.stat().st_size
                and metadata['archive']['sha256'] == fingerprint, f'export receipt differs: {export}')
        source = {'path': str(export), 'sha256': fingerprint, 'receipt_sha256': file_digest(receipt)}
        with tarfile.open(export) as tf:
            members = {}
            for member in tf:
                if member.isfile():
                    require(member.name not in members, 'duplicate export member')
                    members[member.name] = member
            def raw(name):
                with tf.extractfile(members[name]) as stream:
                    return stream.read()
            pairs = {}
            for name in members:
                match = RUN.fullmatch(name)
                if match:
                    prefix, audit, placement, kind, request, attempt, ext = match.groups()
                    require((kind, ext) in (('attempt', 'json'), ('response', 'bin')), 'unexpected capture suffix')
                    pairs.setdefault((prefix, audit, placement, request, attempt), {})[kind] = name
            require(pairs, f'no archived attempts in {export}')
            for (prefix, audit, placement, number, attempt), pair in sorted(pairs.items()):
                require('attempt' in pair, 'response has no attempt record')
                name = pair['attempt']
                obs_raw = raw(name)
                obs = strict_json(obs_raw)
                run = name.rsplit('/', 1)[0]
                req_raw = raw(f'{run}/request-{number}.json')
                arrangements = [n for n in members if re.fullmatch(re.escape(prefix) + r'/prep/\d+/arrangement.json', n)]
                require(len(arrangements) == 1, 'ambiguous prepared arrangement')
                arr_raw = raw(arrangements[0])
                req, arr = strict_json(req_raw), strict_json(arr_raw)
                require(obs['audit'] == audit == arr['audit'] and arr['writer'] == obs['writer']
                        and obs['body']['request'] == req['request'] == int(number)
                        and obs['body']['attempt'] == int(attempt), 'attempt identity differs')
                response = raw(pair['response']) if 'response' in pair else None
                metadata = obs['body']['response']
                if response is not None:
                    require(metadata and metadata['file'] == pair['response'].rsplit('/', 1)[1], 'response member differs')
                row = shape(obs, req, arr['body'], response)
                row.update(writer=obs['writer'], attempt_sha256=digest(obs_raw), arrangement_sha256=digest(arr_raw),
                           request_record_sha256=digest(req_raw))
                key = '/'.join((audit, placement, number, attempt))
                where = {'export': len(sources), 'member': name}
                if key in attempts:
                    require(attempts[key]['observation'] == row, 'overlapping exports disagree')
                    attempts[key]['sources'].append(where)
                else:
                    attempts[key] = {'observation': row, 'sources': [where]}
        sources.append(source)
    counts = Counter(row['observation'].get('stop', row['observation']['outcome']) for row in attempts.values())
    return {'schema': 'stewart.messages-shape-inventory/1', 'exports': sources,
            'counts': dict(sorted(counts.items())), 'attempts': attempts}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exports', nargs='+', type=Path, help='Reviewed original work.tar files')
    parser.add_argument('--output', required=True, type=Path, help='Fresh private JSON result')
    args = parser.parse_args()
    result = inventory(args.exports)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(f"{len(result['exports'])} exports, {len(result['attempts'])} unique attempts: {result['counts']}")


if __name__ == '__main__':
    main()
