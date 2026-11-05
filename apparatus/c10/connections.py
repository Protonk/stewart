"""Host Keychain lookup. Password bytes are returned privately, never recorded.

The caller chooses when a lookup is authorized, after intake for a launch.
No environment credential or alternate store is used on failure.
"""
import re
import subprocess
import time

from common import credential_bytes, write_json
from launch import host_environment

SERVICE = 'stewart-provider'
SYNTHETIC_PREFIX = b'c10-NONFUNCTIONAL-'
MESSAGES = {
    'invalid_label': 'Connection labels must contain 1–80 letters, digits, dots, underscores or hyphens, starting with a letter or digit.',
    'label_mismatch': 'Connection label differs from the packet credential_label; no lookup was made.',
    'missing_tool': 'The macOS security tool is unavailable.',
    'missing_item': 'No matching Keychain item was found in this execution context.',
    'locked_keychain': 'Keychain interaction is unavailable or the keychain is locked; use an interactive login session.',
    'access_denied': 'Keychain access was denied or cancelled.',
    'deadline': 'Keychain lookup exceeded its deadline; no credential was sent.',
    'lookup_failed': 'Keychain lookup failed; its raw output was withheld.',
    'invalid_credential': 'The Keychain value does not meet the credential input bounds.',
    'not_synthetic': 'Rehearsal requires a value beginning c10-NONFUNCTIONAL-; no credential was sent.',
}


class ConnectionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(MESSAGES[code])


def validate_label(label, packet=None):
    if not isinstance(label, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', label) is None:
        raise ConnectionError('invalid_label')
    if packet is not None and label != packet['account']['credential_label']:
        raise ConnectionError('label_mismatch')
    return label


def failure_code(status, stderr):
    # Exit statuses are truncated OSStatus values. Do not turn the observed
    # invalid-parameter + not-found combination into a claim of absence.
    message = stderr.lower()
    if b'parameters passed' in message or b'invalid parameter' in message:
        return 'lookup_failed'
    if status == 36 or b'interaction is not allowed' in message or b'keychain is locked' in message:
        return 'locked_keychain'
    if status in [51, 128] or b'user canceled' in message or b'user cancelled' in message or b'authorization' in message:
        return 'access_denied'
    if status == 44 and b'could not be found' in message:
        return 'missing_item'
    return 'lookup_failed'


def _query(label, *, password, timeout, record):
    validate_label(label)
    argv = ['security', 'find-generic-password', '-s', SERVICE, '-a', label]
    if password:
        argv.append('-w')
    observation = {'service': SERVICE, 'account': label, 'password_requested': password,
                   'started_at': time.time(), 'exit': None, 'outcome': 'lookup_failed'}
    try:
        try:
            result = subprocess.run(argv, env={**host_environment(), 'LC_ALL': 'C'},
                stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
        except FileNotFoundError:
            raise ConnectionError('missing_tool') from None
        except subprocess.TimeoutExpired:
            raise ConnectionError('deadline') from None
        except OSError:
            raise ConnectionError('lookup_failed') from None
        observation['exit'] = result.returncode
        if result.returncode != 0:
            raise ConnectionError(failure_code(result.returncode, result.stderr))
        observation['outcome'] = 'found'
        return result.stdout if password else None
    except ConnectionError as error:
        observation['outcome'] = error.code
        raise
    finally:
        observation['ended_at'] = time.time()
        # Never persist stdout, stderr or exception text: even an unexpected
        # tool diagnostic could contain credential bytes. Keep the classified
        # result and process exit status instead.
        if record is not None:
            write_json(record, observation)


def status(label, *, timeout=10, record=None):
    _query(label, password=False, timeout=timeout, record=record)
    return {'service': SERVICE, 'account': label, 'present': True,
            'password_read': False, 'access_policy_verified': False,
            'provider_access_verified': False}


def lookup(label, *, rehearsal=False, timeout=60, record=None):
    raw = _query(label, password=True, timeout=timeout, record=record)
    try:
        key = credential_bytes(raw)
    except ValueError:
        raise ConnectionError('invalid_credential') from None
    if rehearsal and not key.startswith(SYNTHETIC_PREFIX):
        raise ConnectionError('not_synthetic')
    return key
