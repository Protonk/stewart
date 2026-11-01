"""Shared, provider-free helpers for the retained sanity session apparatus."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time


def digest(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON object key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def write_json(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write('\n')


def credential_bytes(value):
    """The transport accepts one optional LF; the credential itself is ASCII."""
    if value.endswith(b'\n'):
        value = value[:-1]
    if not 1 <= len(value) <= 4096 or any(c < 0x21 or c > 0x7e for c in value):
        raise ValueError('credential must contain 1–4096 visible ASCII bytes')
    return value


def decode_ascii_escapes(value):
    """Conservative disclosure detector, also usable on truncated JSON.

    Recognizing escapes in non-JSON text can over-report. That withholds an
    export; it never removes or rewrites the original evidence.
    """
    def replace(match):
        token = match.group(0)
        if token.startswith(b'\\u'):
            return bytes([int(token[2:], 16)])
        return {b'\\"': b'"', b'\\\\': b'\\', b'\\/': b'/'}[token]
    return re.sub(rb'\\u00[0-7][0-9a-fA-F]|\\["\\/]', replace, value)


def secret_matches(content, key):
    return key in content or key in decode_ascii_escapes(content)


def scan_tree(root, key):
    """Inspect every regular file without following links; failures withhold.

    The fixed overlap bounds a full 4096-byte credential in ASCII JSON escapes.
    Reports intentionally contain counts, never matching bytes or filenames.
    """
    started = time.time()
    files = matches = errors = 0
    root = Path(root)
    try:
        if not stat.S_ISDIR(root.lstat().st_mode):
            raise OSError('scan root is not a real directory')
    except OSError:
        return {'files': 0, 'files_with_matches': 0, 'errors': 1,
                'started_at': started, 'ended_at': time.time(),
                'scope': 'root missing, inaccessible or not a real directory'}
    def walk_error(error):
        nonlocal errors
        errors += 1
    for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        for name in dirs[:]:
            try:
                regular_directory = stat.S_ISDIR((Path(directory) / name).lstat().st_mode)
            except OSError:
                regular_directory = False
            if not regular_directory:
                errors += 1
                dirs.remove(name)
        for name in names:
            path = Path(directory) / name
            try:
                observed = path.lstat()
                if not stat.S_ISREG(observed.st_mode):
                    errors += 1
                    continue
                flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | os.O_NONBLOCK
                fd = os.open(path, flags)
                with os.fdopen(fd, 'rb') as stream:
                    before = os.fstat(stream.fileno())
                    if not stat.S_ISREG(before.st_mode) or (observed.st_dev, observed.st_ino) != (before.st_dev, before.st_ino):
                        errors += 1
                        continue
                    files += 1
                    tail = b''
                    found = False
                    while True:
                        chunk = stream.read(65536)
                        if not chunk:
                            break
                        content = tail + chunk
                        found = found or secret_matches(content, key)
                        tail = content[-24576:]
                    after = os.fstat(stream.fileno())
                    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                        errors += 1
                    matches += found
            except OSError:
                errors += 1
    return {'files': files, 'files_with_matches': matches, 'errors': errors,
            'started_at': started, 'ended_at': time.time(),
            'scope': 'regular-file bytes, literal and ASCII JSON escapes; no memory claim'}


def validate_commission(value):
    keys = {'schema', 'model', 'effort', 'limits', 'endpoint', 'proxy',
            'max_placements', 'permitted_request_attempts', 'automatic_continuation',
            'stop_after_seconds', 'spending_authority', 'account', 'bindings'}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError('commission fields differ from stewart.sanity-commission/1')
    if value['schema'] != 'stewart.sanity-commission/1':
        raise ValueError('unsupported commission schema')
    if not isinstance(value['model'], str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}', value['model']):
        raise ValueError('invalid model name')
    if value['model'].startswith('REPLACE') or value['model'] == 'rehearsal-only':
        raise ValueError('live commission must select a real model')
    if value['effort'] not in [None, 'low', 'medium', 'high', 'xhigh', 'max']:
        raise ValueError('invalid effort')
    limits = value['limits']
    if not isinstance(limits, dict) or set(limits) != {'turns', 'input_tokens', 'output_tokens'}:
        raise ValueError('commission must give all cumulative limits')
    if any(type(v) is not int or not 0 < v <= 2**48 for v in limits.values()):
        raise ValueError('invalid cumulative limit')
    if limits['output_tokens'] < 1024:
        raise ValueError('output allowance cannot launch a request')
    if value['endpoint'] != 'https://api.anthropic.com' or value['proxy'] is not None:
        raise ValueError('this launcher supports only the explicit direct Anthropic route')
    if type(value['max_placements']) is not int or value['max_placements'] != 1 or type(value['permitted_request_attempts']) is not int or value['permitted_request_attempts'] != 4 or value['automatic_continuation'] is not False:
        raise ValueError('this launcher permits one placement, built-in retries, and no continuation')
    if type(value['stop_after_seconds']) is not int or not 60 <= value['stop_after_seconds'] <= 14400:
        raise ValueError('watchdog must be 60–14400 seconds')
    if value['spending_authority'] is not None and not isinstance(value['spending_authority'], str):
        raise ValueError('spending_authority must be a statement or null')
    account = value['account']
    if not isinstance(account, dict) or set(account) != {'account_label', 'workspace_id', 'credential_label'} or any(v is not None and not isinstance(v, str) for v in account.values()):
        raise ValueError('account must identify the account, workspace and credential without secret values')
    bindings = value['bindings']
    if not isinstance(bindings, dict) or set(bindings) != {'qualification_id', 'binary_sha256', 'source_commit', 'submission_sha256'} or any(v is not None and not isinstance(v, str) for v in bindings.values()):
        raise ValueError('bindings must identify qualification, binary, source and specimen')
    return value


def rehearsal_commission():
    return {'schema': 'stewart.sanity-commission/1', 'model': 'rehearsal-only',
            'effort': None, 'limits': {'turns': 8, 'input_tokens': 80000, 'output_tokens': 6000},
            'endpoint': 'loopback-fake', 'proxy': None, 'max_placements': 1,
            'permitted_request_attempts': 4, 'automatic_continuation': False,
            'stop_after_seconds': 60, 'spending_authority': 'synthetic provider only; zero model calls',
            'account': {'account_label': 'offline rehearsal', 'workspace_id': 'synthetic', 'credential_label': 'nonfunctional canary'},
            'bindings': {'qualification_id': None, 'binary_sha256': None, 'source_commit': None, 'submission_sha256': None}}


def submission_identity(repo):
    root = Path(repo) / 'apparatus/sanity/submission'
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('sanity specimen must not contain symlinks')
        if path.is_file():
            raw = path.read_bytes()
            files.append({'path': path.relative_to(root).as_posix(), 'bytes': len(raw), 'sha256': digest(raw)})
        elif not path.is_dir():
            raise ValueError('sanity specimen has a nonregular member')
    if not files:
        raise ValueError('sanity specimen is absent or empty')
    return digest(json.dumps(files, separators=(',', ':'), ensure_ascii=True).encode())
