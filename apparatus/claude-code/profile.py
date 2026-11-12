"""Prepare installation evidence and assemble a reviewed runtime profile without launching Claude."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('profile_pin', HERE / 'pin.py')
pin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin)
HEX = re.compile(r'[0-9a-f]{64}')
BINDINGS = ('launch_sha256', 'surface_sha256', 'tools_sha256', 'model')


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('duplicate JSON member: ' + key)
            value[key] = item
        return value
    def invalid(value):
        raise ValueError('non-finite JSON number: ' + value)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)


def exact(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(label + ' has unexpected or missing members')


def text(value, label):
    if not isinstance(value, str) or not value or '\0' in value:
        raise ValueError(label + ' must be nonempty text without NUL')
    value.encode('utf-8')
    return value


def checksum(value, label):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError(label + ' must be a lowercase SHA-256')
    return value


def absolute(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('expected an absolute path without ..: ' + str(path))
    return path


def directory(path):
    """Open each component without following links, including ancestors."""
    path = absolute(path)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_file(path, limit=16 * 1024 * 1024, hash_only=False):
    path = absolute(path)
    parent = directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('expected a regular file: ' + str(path))
        digest, chunks, size = hashlib.sha256(), [], 0
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            if limit is not None and size > limit:
                raise ValueError('input exceeds size bound: ' + str(path))
            digest.update(chunk)
            if not hash_only:
                chunks.append(chunk)
    return (digest.hexdigest(), size) if hash_only else b''.join(chunks)


def publish(path, raw):
    path = absolute(path)
    parent = directory(path.parent)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
    finally:
        os.close(parent)


def verification_inventory(root):
    os.close(directory(root))
    members = []
    for path in sorted(root.rglob('*')):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            digest, size = read_file(path, limit=None, hash_only=True)
            members.append({'path': str(path.relative_to(root)), 'bytes': size, 'sha256': digest})
        elif not stat.S_ISDIR(mode):
            raise ValueError('installation verification contains a link or special entry: ' + str(path))
    return members


def verify_public_installation(output, receipt_path):
    """Reverify retained public release evidence; never execute the signed binary."""
    raw = read_file(receipt_path)
    receipt = decode(raw)
    exact(receipt, ('version', 'platform', 'binary', 'sha256', 'manifest_sha256', 'signer', 'verification'), 'pin receipt')
    if receipt['version'] != pin.VERSION or receipt['platform'] != pin.PLATFORM or receipt['signer'] != pin.FINGERPRINT:
        raise ValueError('installation differs from the selected native release pin')
    executable = absolute(text(receipt['binary'], 'pinned executable'))
    for key in ('sha256', 'manifest_sha256'):
        checksum(receipt[key], key)
    public = output / 'installation'
    public.mkdir(mode=0o700)
    publish(public / 'pin.json', raw)
    for name in ('claude-code.asc', 'manifest.json', 'manifest.json.sig'):
        publish(public / name, read_file(receipt_path.parent / name))
    manifest = read_file(public / 'manifest.json')
    if sha(manifest) != receipt['manifest_sha256'] or pin.manifest_checksum(manifest) != receipt['sha256']:
        raise ValueError('release manifest does not match the installation receipt')
    gpg, gpgv = shutil.which('gpg'), shutil.which('gpgv')
    if not gpg or not gpgv:
        raise ValueError('gpg and gpgv are required to verify the retained public signature')
    verification = public / 'verification'
    verification.mkdir(mode=0o700)
    keyring = verification / 'release-key.gpg'
    pin.run_logged(verification, 'dearmor', [gpg, '--no-options', '--homedir', str(verification), '--batch',
                   '--dearmor', '--output', str(keyring), str(public / 'claude-code.asc')])
    status = pin.run_logged(verification, 'signature', [gpgv, '--homedir', str(verification), '--keyring', str(keyring),
                            '--status-fd', '1', str(public / 'manifest.json.sig'), str(public / 'manifest.json')])
    if not pin.signed_by_release_key(status.decode('utf-8')):
        raise ValueError('signature does not identify the pinned release key')
    if read_file(executable, limit=None, hash_only=True)[0] != receipt['sha256']:
        raise ValueError('pinned executable differs from the authenticated manifest')
    pin.run_logged(verification, 'codesign', ['/usr/bin/codesign', '--verify', '--verbose', str(executable)])
    if read_file(executable, limit=None, hash_only=True)[0] != receipt['sha256']:
        raise ValueError('pinned executable changed during installation verification')
    return receipt


def prepare(receipt_path, output, config, home, temporary):
    for path in (config, home, temporary):
        os.close(directory(path))  # Directory metadata only; never read login contents.
    os.close(directory(output.parent))
    output.mkdir(mode=0o700)
    receipt = verify_public_installation(output, receipt_path)
    launch = {'executable': receipt['binary'], 'sha256': receipt['sha256'], 'version': receipt['version'],
              'platform': 'macos-aarch64', 'config_directory': str(config), 'home': str(home),
              'temporary_directory': str(temporary)}
    installation = {'manifest_sha256': receipt['manifest_sha256'], 'signer': receipt['signer'],
                    'binary_sha256': receipt['sha256']}
    publish(output / 'launch.json', compact(launch))
    publish(output / 'installation.json', compact(installation))
    publish(output / 'PREPARATION.json', compact({
        'schema': 'stewart.claude-code.installation-evidence/1', 'scope': 'installation-only',
        'verified_at': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'launch_sha256': sha(compact(launch)), 'installation_sha256': sha(compact(installation)),
        'pin_receipt_sha256': sha(read_file(output / 'installation/pin.json')),
        'verification_files': verification_inventory(output / 'installation')}) + b'\n')
    print('Installation verified. Exact launch bytes: ' + str(output / 'launch.json'))
    print('No profile check was attested and no Claude process was started.')


def timestamp(value, label):
    text(value, label)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value):
        raise ValueError(label + ' must be a complete UTC timestamp ending in Z')
    result = datetime.fromisoformat(value[:-1] + '+00:00')
    return result


def evidence(root, manifest_raw):
    manifest = decode(manifest_raw)
    exact(manifest, ('schema', 'members'), 'evidence manifest')
    if manifest['schema'] != 'stewart.claude-code.surface-evidence/1' or not isinstance(manifest['members'], list):
        raise ValueError('unsupported evidence manifest')
    members = set()
    for item in manifest['members']:
        exact(item, ('path', 'bytes', 'sha256'), 'evidence member')
        name = text(item['path'], 'evidence path')
        path = Path(name)
        if path.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')) or name in members:
            raise ValueError('unsafe or repeated evidence path: ' + name)
        if name in ('OBSERVATION.json', 'CHECK.json', 'EVIDENCE.json'):
            raise ValueError('cyclic evidence manifest member: ' + name)
        if type(item['bytes']) is not int or item['bytes'] < 0:
            raise ValueError('invalid evidence size: ' + name)
        expected = checksum(item['sha256'], name)
        if read_file(root / path, limit=None, hash_only=True) != (expected, item['bytes']):
            raise ValueError('evidence bytes changed: ' + name)
        members.add(name)
    # Missing or unlisted witnesses must not be silently omitted from review.
    present = set()
    for path in root.rglob('*'):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            present.add(str(path.relative_to(root)))
        elif not stat.S_ISDIR(mode):
            raise ValueError('evidence contains a link or special entry: ' + str(path))
    if present - {'OBSERVATION.json', 'CHECK.json', 'EVIDENCE.json'} != members:
        raise ValueError('evidence manifest omits files or names absent files')
    return members


def validated_installation(installation_root):
    """Recheck retained public evidence and executable bytes; never launch Claude."""
    launch_raw = read_file(installation_root / 'launch.json', 65536)
    installation_raw = read_file(installation_root / 'installation.json', 65536)
    launch, installation = decode(launch_raw), decode(installation_raw)
    prepared = decode(read_file(installation_root / 'PREPARATION.json'))
    exact(prepared, ('schema', 'scope', 'verified_at', 'launch_sha256', 'installation_sha256',
                     'pin_receipt_sha256', 'verification_files'),
          'installation evidence')
    if (prepared['schema'] != 'stewart.claude-code.installation-evidence/1'
            or prepared['scope'] != 'installation-only' or prepared['launch_sha256'] != sha(launch_raw)
            or prepared['installation_sha256'] != sha(installation_raw)
            or prepared['pin_receipt_sha256'] != sha(read_file(installation_root / 'installation/pin.json'))):
        raise ValueError('installation evidence bindings changed')
    timestamp(prepared['verified_at'], 'installation verification time')
    if prepared['verification_files'] != verification_inventory(installation_root / 'installation'):
        raise ValueError('installation verification evidence changed or is missing')
    exact(launch, ('executable', 'sha256', 'version', 'platform', 'config_directory', 'home', 'temporary_directory'), 'launch')
    exact(installation, ('manifest_sha256', 'signer', 'binary_sha256'), 'installation')
    receipt = decode(read_file(installation_root / 'installation/pin.json'))
    exact(receipt, ('version', 'platform', 'binary', 'sha256', 'manifest_sha256', 'signer', 'verification'), 'pin receipt')
    if (launch['sha256'] != receipt['sha256'] or launch['executable'] != receipt['binary']
            or launch['version'] != pin.VERSION or launch['platform'] != 'macos-aarch64'
            or receipt['version'] != pin.VERSION or receipt['platform'] != pin.PLATFORM
            or receipt['signer'] != pin.FINGERPRINT
            or installation != {'manifest_sha256': receipt['manifest_sha256'], 'signer': pin.FINGERPRINT,
                                'binary_sha256': launch['sha256']}):
        raise ValueError('installation and launch bindings differ')
    public = installation_root / 'installation'
    manifest = read_file(public / 'manifest.json')
    if (sha(manifest) != installation['manifest_sha256']
            or pin.manifest_checksum(manifest) != launch['sha256']):
        raise ValueError('retained installation manifest changed')
    for name in ('dearmor', 'signature', 'codesign'):
        if read_file(public / 'verification' / (name + '.exit')).strip() != b'0':
            raise ValueError('installation verification did not pass: ' + name)
    if not pin.signed_by_release_key(read_file(public / 'verification/signature.stdout').decode('utf-8')):
        raise ValueError('retained signature does not name the pinned release key')
    if read_file(absolute(launch['executable']), limit=None, hash_only=True)[0] != launch['sha256']:
        raise ValueError('harness executable changed since the check')
    for key in ('config_directory', 'home', 'temporary_directory'):
        os.close(directory(absolute(text(launch[key], key))))
    return launch_raw, installation_raw


def assemble(installation_root, observation_root, review_path, output):
    output = absolute(output)
    os.close(directory(output.parent))
    for root, label in ((installation_root, 'installation'), (observation_root, 'observation')):
        os.close(directory(root))
        # Directory identity also catches spelling aliases on case-insensitive
        # filesystems; a lexical prefix check alone would permit mutation there.
        if any(os.path.samefile(root, ancestor) for ancestor in output.parents):
            raise ValueError('profile output must stay outside the ' + label + ' evidence directory')
    # This inventory is owned by the implementation-independent fixture author.
    sys.path.insert(0, str(HERE.parent / 'driver'))
    from claude_code_surface import REQUIRED_CHECKS

    raw_observation = read_file(observation_root / 'OBSERVATION.json')
    observation = decode(raw_observation)
    exact(observation, ('schema', 'mode', 'scope', 'started_at', 'finished_at', *BINDINGS,
                       'evidence_manifest_sha256', 'checks', 'stopping'), 'observation')
    if (observation['schema'] != 'stewart.claude-code.surface-observation/1'
            or observation['mode'] != 'real-harness' or observation['scope'] != 'supplied-surface'
            or observation['stopping'] != 'observed'):
        raise ValueError('profile requires a stopped, real-harness supplied-surface observation; rehearsal is not eligible')
    started = timestamp(observation['started_at'], 'observation start')
    finished = timestamp(observation['finished_at'], 'observation finish')
    if finished < started:
        raise ValueError('observation finish precedes start')
    raw_review = read_file(review_path)
    review = decode(raw_review)
    exact(review, ('schema', 'scope', *BINDINGS, 'checked_at', 'observation_sha256',
                   'reviewer', 'reviewed_at', 'outcome'), 'reviewed check')
    if (review['schema'] != 'stewart.claude-code.reviewed-check/1' or review['scope'] != 'supplied-surface'
            or review['outcome'] != 'observed' or review['observation_sha256'] != sha(raw_observation)
            or review['checked_at'] != observation['finished_at']):
        raise ValueError('review does not attest this completed observation')
    text(review['reviewer'], 'reviewer')
    if timestamp(review['reviewed_at'], 'review time') < finished:
        raise ValueError('review predates the completed observation')
    for key in BINDINGS:
        if review[key] != observation[key]:
            raise ValueError('review binding differs: ' + key)
        (text if key == 'model' else checksum)(review[key], key)
    manifest_raw = read_file(observation_root / 'EVIDENCE.json')
    if sha(manifest_raw) != observation['evidence_manifest_sha256']:
        raise ValueError('evidence manifest differs from the observed binding')
    members = evidence(observation_root, manifest_raw)
    for name, key in (('launch', 'launch_sha256'), ('surface', 'surface_sha256'), ('tools', 'tools_sha256')):
        member = 'inputs/' + name + '.json'
        if member not in members or sha(read_file(observation_root / member)) != review[key]:
            raise ValueError('exact input binding differs: ' + name)
    checks = observation['checks']
    if not isinstance(checks, list):
        raise ValueError('checks must be an array')
    identifiers = []
    for check in checks:
        exact(check, ('id', 'outcome', 'evidence'), 'observed check')
        identifiers.append(check['id'])
        if (check['outcome'] != 'observed' or not isinstance(check['evidence'], list)
                or not check['evidence'] or any(not isinstance(n, str) or n not in members for n in check['evidence'])):
            raise ValueError('required comparison is not observed with retained evidence: ' + str(check['id']))
    if len(identifiers) != len(REQUIRED_CHECKS) or set(identifiers) != set(REQUIRED_CHECKS):
        raise ValueError('required comparison inventory is incomplete or repeated')
    launch_raw, installation_raw = validated_installation(installation_root)
    installation = decode(installation_raw)
    if launch_raw != read_file(observation_root / 'inputs/launch.json'):
        raise ValueError('observed launch differs from the installation preparation')
    # Splice the original launch value bytes: internal whitespace is part of its binding.
    if launch_raw.strip() != launch_raw:
        raise ValueError('launch file must contain exactly the JSON value without surrounding whitespace')
    check = {key: review[key] for key in ('surface_sha256', 'launch_sha256', 'tools_sha256', 'model', 'checked_at')}
    check.update(evidence_sha256=sha(raw_review), outcome='observed')
    profile = (b'{"schema":"stewart.claude-code.profile/2","launch":' + launch_raw
               + b',"installation":' + compact(installation) + b',"check":' + compact(check) + b'}\n')
    if len(profile) > 65536:
        raise ValueError('profile exceeds 64 KiB')
    publish(output, profile)
    print('Profile written: ' + str(output))
    print('Attests reviewed supplied-surface compatibility only; confers no launch authority.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    install = sub.add_parser('prepare', help='verify retained public native-installation evidence; no harness execution')
    for name in ('pin-receipt', 'output', 'config-directory', 'home', 'temporary-directory'):
        install.add_argument('--' + name, type=absolute, required=True)
    build = sub.add_parser('assemble', help='assemble a profile from a separately reviewed real-harness check')
    for name in ('installation-directory', 'observation-directory', 'review', 'output'):
        build.add_argument('--' + name, type=absolute, required=True)
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            prepare(args.pin_receipt, args.output, args.config_directory, args.home, args.temporary_directory)
        else:
            assemble(args.installation_directory, args.observation_directory, args.review, args.output)
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, 'profile refused: %s\n' % exc)


if __name__ == '__main__':
    main()
