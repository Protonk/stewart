"""Connect to the launcher's Linux persistent keyring. Never retain keyctl streams."""
import getpass
import os
import re
import resource
import subprocess
import time
import warnings

from session_support import credential_bytes, write_json

SYNTHETIC_PREFIX = b'c10-NONFUNCTIONAL-'
MESSAGES = {
    'invalid_label': 'Connection labels must start with a letter or digit and use up to 80 letters, digits, dots, underscores or hyphens.',
    'label_mismatch': 'Connection differs from the packet credential_label.',
    'missing_tool': 'Install Debian keyutils for the launcher user.',
    'missing_item': 'No matching user key is searchable in the launcher persistent keyring.',
    'expired_key': 'The named key expired or was revoked.',
    'access_denied': 'Kernel keyring access was denied.',
    'deadline': 'Keyring operation exceeded its deadline.',
    'lookup_failed': 'Keyring operation failed. Raw diagnostics are withheld.',
    'invalid_credential': 'The key does not meet the credential input bounds.',
    'not_synthetic': 'Rehearsal requires a key beginning c10-NONFUNCTIONAL-.',
}


class ConnectionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(MESSAGES[code])


def host_environment():
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'USER', 'LOGNAME') if k in os.environ}
    env['XDG_RUNTIME_DIR'] = '/run/user/' + str(os.getuid())
    return env


def validate_label(label, packet=None):
    if not isinstance(label, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', label) is None:
        raise ConnectionError('invalid_label')
    if packet is not None and label != packet['account']['credential_label']:
        raise ConnectionError('label_mismatch')
    return label


def source(label):
    return {'kind': 'persistent-keyring', 'type': 'user', 'description': 'stewart-provider:' + validate_label(label)}


def hidden_credential():
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            value = getpass.getpass('Key for launcher keyring (hidden): ')
        except (getpass.GetPassWarning, EOFError):
            raise RuntimeError('hidden terminal input unavailable') from None
    try:
        return credential_bytes(value.encode('ascii'))
    except (UnicodeEncodeError, ValueError):
        raise ConnectionError('invalid_credential') from None


def keyctl(args, timeout, *, value=None):
    try:
        result = subprocess.run(['keyctl', *args], env={**host_environment(), 'LC_ALL': 'C'},
            stdin=subprocess.DEVNULL if value is None else None, input=value,
            capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise ConnectionError('missing_tool') from None
    except subprocess.TimeoutExpired:
        raise ConnectionError('deadline') from None
    except OSError:
        raise ConnectionError('lookup_failed') from None
    if result.returncode:
        message = result.stderr.lower()
        for fragment, code in [(b'permission denied', 'access_denied'), (b'operation not permitted', 'access_denied'),
                               (b'key has expired', 'expired_key'), (b'key has been revoked', 'expired_key'),
                               (b'required key not available', 'missing_item')]:
            if fragment in message:
                raise ConnectionError(code)
        raise ConnectionError('lookup_failed')
    return result.stdout


def serial(args, timeout, *, value=None):
    raw = keyctl(args, timeout, value=value)
    if re.fullmatch(rb'[1-9][0-9]{0,9}\n', raw) is None:
        raise ConnectionError('lookup_failed')
    return raw.decode('ascii').strip()


def provision(label):
    description = source(label)['description']
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    ring = serial(['get_persistent', '@s'], 10)
    key = serial(['padd', 'user', description, ring], 10, value=hidden_credential())
    # Give only this UID permissions, even if another process possesses a link.
    keyctl(['setperm', key, '0x003f0000'], 10)
    return {'stored': True, **source(label)}


def _query(label, *, payload, rehearsal, timeout, record):
    identity = source(label)
    observation = {'schema': 'stewart.keyring-lookup/1', **identity, 'payload_requested': payload,
                   'started_at': time.time(), 'stage': 'persistent-ring', 'outcome': 'failed'}
    try:
        ring = serial(['get_persistent', '@s'], timeout)
        observation['stage'] = 'search'
        key = serial(['search', ring, 'user', identity['description']], timeout)
        if payload:
            observation['stage'] = 'pipe'
            raw = keyctl(['pipe', key], timeout)
            try:
                secret = credential_bytes(raw)
            except ValueError:
                raise ConnectionError('invalid_credential') from None
            if rehearsal and not secret.startswith(SYNTHETIC_PREFIX):
                raise ConnectionError('not_synthetic')
        observation['outcome'] = 'found'
        return secret if payload else None
    except ConnectionError as error:
        observation['outcome'] = error.code
        raise
    finally:
        if record is not None:
            write_json(record, {**observation, 'ended_at': time.time()})


def status(label, *, timeout=10, record=None):
    _query(label, payload=False, rehearsal=False, timeout=timeout, record=record)
    return {**source(label), 'present': True, 'payload_read': False, 'provider_access_verified': False}


def lookup(label, *, rehearsal=False, timeout=10, record=None):
    return _query(label, payload=True, rehearsal=rehearsal, timeout=timeout, record=record)
