"""Record a status or close invocation inside the retained sanity container.

No credential is needed. Close ends authoring; this command never automatically
confirms a new manager-sealed delivery or surrenders loss on the operator's behalf.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import re

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_support import write_json
from session import safe_choice, safe_usage
from exercise import verify_package, digest


def safe_allowances(value):
    """Preserve known limits and explicit unknown usage without forwarding raw text."""
    if value is None:
        return None
    if not isinstance(value, dict):
        return 'unknown'
    result = {}
    for dimension in ['turns', 'input_tokens', 'output_tokens']:
        part = value.get(dimension)
        if not isinstance(part, dict):
            result[dimension] = 'unknown'
            continue
        result[dimension] = {key: part[key] if type(part.get(key)) is int and part[key] >= 0 else 'unknown'
                             for key in ['used', 'reported', 'estimated', 'limit']}
    return result


def safe_state(reply):
    data = reply.get('data', {})
    run = data.get('runs', {}).get('last') or {}
    ending = data.get('ending', run.get('ending', data.get('runs', {}).get('last_ending')))
    cause = data.get('cause', run.get('cause'))
    headline = data.get('headline', {})
    seal = data.get('seal', headline.get('seal', {}))
    authoring = headline.get('authoring', {})
    delivery = data.get('delivery') or {}
    return {'outcome': safe_choice(reply.get('outcome'), ['completed', 'failed', 'refused']),
        'condition': safe_choice(data.get('condition'), ['preparing', 'intake_in_progress', 'intake_failed', 'acceptance_uncertain', 'log_damaged', 'not_started', 'run_active', 'interrupted', 'ended_unsubmitted', 'limit_reached', 'damaged', 'sealed_undelivered', 'delivered_open', 'awaiting_confirmation', 'close_unfinished', 'closed_before_launch', 'closed']),
        'ending': safe_choice(ending, ['sealed', 'ended_unsubmitted', 'limit_reached', 'stopped_by_close', 'damaged', 'interrupted']),
        'cause': safe_choice(cause, ['signal', 'provider_unavailable', 'provider_rejected', 'context_exhausted', 'provider_refusal', 'max_tokens', 'protocol_anomaly', 'archive_write_failed', 'process_gone', 'credential_reflected']),
        'authoring': {'state': safe_choice(authoring.get('state'), ['not_started', 'open', 'ended']),
                      'ended_by': None if authoring.get('state') != 'ended' else safe_choice(authoring.get('ended_by'), ['seal', 'ordinary_ending', 'limit', 'damage', 'close'])},
        'seal_state': safe_choice(seal.get('state') if isinstance(seal, dict) else None, ['absent', 'present']),
        'seal_actor': (safe_choice(seal.get('actor'), ['auditor', 'manager'])
                       if isinstance(seal, dict) and seal.get('state') == 'present' else None),
        'delivery_verified': (headline.get('delivered', {}).get('verified')
                              if type(headline.get('delivered', {}).get('verified')) is bool
                              else delivery.get('outcome') == 'verified' if delivery.get('outcome') in ['verified', 'verified_with_losses', 'partial', 'failed', 'name_taken'] else 'unknown'),
        'closed': (headline['closed'] == 'yes' if headline.get('closed') in ['yes', 'no', 'unfinished']
                   else data['closure'] == 'complete' if data.get('closure') in ['complete', 'unfinished'] else 'unknown'),
        'allowances': safe_allowances(data.get('allowances', 'unknown')),
        'diagnostics_present': bool(data.get('diagnostics') or data.get('bad_records') or reply.get('causes')),
        'retained_locations_count': len(reply.get('retained', [])),
        'usage': safe_usage(data.get('usage'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['status', 'close', 'inspect'])
    parser.add_argument('--scenario', default='live')
    parser.add_argument('--confirm', help='close only, after the operator has inspected the newly delivered copy')
    args = parser.parse_args()
    if args.scenario not in ['live', 'submitted', 'unsubmitted', 'provider-rejected', 'interrupted', 'reflected-body', 'export-contamination', 'export-failure']:
        parser.error('unknown scenario')
    root = Path('/work/private') / args.scenario
    if args.confirm is not None and (args.operation != 'close' or not re.fullmatch(r'[A-Za-z0-9._:-]{1,512}', args.confirm)):
        parser.error('--confirm requires close and a valid confirmation handle')
    operator = json.loads((root / 'operator.json').read_bytes())
    lock = (root.parent / (root.name + '.operator.lock')).open('a+b')
    fcntl.flock(lock, fcntl.LOCK_EX)
    stem = root / 'evidence' / f'operator-{time.time_ns()}-{args.operation}'
    argv = [operator['binary'], 'status' if args.operation == 'inspect' else args.operation, operator['reference'], '--json']
    if args.confirm is not None:
        argv += ['--confirm', args.confirm]
    with stem.with_suffix('.stdout').open('xb') as stdout, stem.with_suffix('.stderr').open('xb') as stderr:
        result = subprocess.run(argv, env={'PATH': '/usr/bin:/bin', 'HOME': operator['home']},
            cwd=root, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            user=1000, group=1000, extra_groups=[], umask=0o077)
    write_json(stem.with_suffix('.json'), {'argv': argv, 'exit': result.returncode, 'at': time.time()})
    reply = json.loads(stem.with_suffix('.stdout').read_bytes())
    if reply.get('schema') != 'stewart.reply/2':
        raise ValueError('unsupported Stewart reply schema')
    summary = {'operation': args.operation, 'exit': result.returncode,
        'reply_retained': str(stem.with_suffix('.stdout')),
        'confirmation_requested': args.confirm is not None, 'loss_surrendered': False,
        'state': safe_state(reply)}
    if args.operation == 'inspect' and result.returncode == 0:
        data = reply['data']
        location = data.get('headline', {}).get('delivered', {}).get('location')
        package = Path(location) if isinstance(location, str) else None
        if package is None or package.parent != root / 'returns' or not re.fullmatch(r'stewart-return-[a-z0-9-]+', package.name):
            parser.exit(1, 'No recognized delivered package is available for inspection.\n')
        manifests = list((root / 'archive').glob('audits/*/seal/manifest-*.json'))
        if len(manifests) != 1:
            parser.exit(1, 'One retained seal manifest was expected.\n')
        manifest = manifests[0].read_bytes()
        if digest(manifest) != data['seal']['manifest_sha256']:
            parser.exit(1, 'The retained manifest differs from the seal.\n')
        verify_package(package, manifest)
        summary['verified_package'] = str(package)
        summary['answer_to_inspect_privately'] = str(package / 'answer.md')
        token = next((item.get('confirmation') for item in reversed(data.get('deliveries', [])) if item.get('confirmation')), None)
        if token is not None and re.fullmatch(r'[A-Za-z0-9._:-]{1,512}', token):
            summary['confirmation_after_review'] = token
        summary['inspection_note'] = 'Read the delivered answer privately before close --confirm. This command verifies bytes but does not perform that human review or export the package.'
    print(json.dumps(summary, indent=2))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
