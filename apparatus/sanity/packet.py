"""Bind an unapproved sanity proposal to qualified binary and committed inputs.

This is provider-free preparation. Account identity and spending authority stay
unfilled; review and authorize the final packet separately before live launch.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from launch import host_environment, select_qualification
from session_support import digest, strict_json, submission_identity, validate_commission


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('proposal', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--qualification', required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    if not args.output.is_absolute() or args.output.exists():
        parser.error('output must be a new absolute file in an existing private directory')
    env = host_environment()
    if subprocess.check_output(['git', 'status', '--porcelain', '--', 'apparatus/sanity', 'apparatus/driver/credential_observer.py'], cwd=repo, env=env):
        parser.error('commit the launch apparatus and specimen before binding a packet')
    if subprocess.run(['python3', '-I', '-B', 'apparatus/qualified.py', 'check'], cwd=repo, env=env, stdout=subprocess.DEVNULL).returncode:
        parser.error('qualification record check failed')
    try:
        packet = validate_commission(strict_json(args.proposal.read_bytes()))
        qualification, _ = select_qualification(repo, args.qualification)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    if packet['spending_authority'] is not None or any(value is not None for value in packet['account'].values()):
        parser.error('packet preparation starts from an unapproved proposal with account and spending fields null')
    packet['bindings'] = {'qualification_id': args.qualification,
        'binary_sha256': qualification['platforms']['linux-aarch64']['release_sha256'],
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, env=env).decode().strip(),
        'submission_sha256': submission_identity(repo)}
    raw = (json.dumps(packet, indent=2) + '\n').encode()
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'packet': str(args.output), 'sha256': digest(raw), 'approved': False,
        'bindings': packet['bindings'], 'model_calls': 0}, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
