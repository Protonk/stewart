"""Launch a retained Linux sanity session, with no credential in argv or environment.

Rehearse uses a generated nonfunctional canary and an offline container. Live
requires an exact commission digest and hidden terminal input after verified
credential-free intake. Neither mode repeats a placement or removes a container.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_support import credential_bytes, digest, rehearsal_commission, scan_tree, strict_json, submission_identity, validate_commission, write_json


def host_environment():
    return {k: v for k, v in os.environ.items() if k in ['PATH', 'HOME', 'TMPDIR', 'USER', 'LOGNAME']}


def hidden_credential():
    # getpass otherwise falls back to echoed stdin. Treat its warning as failure.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            value = getpass.getpass('Anthropic test key (hidden; sent through a pipe): ')
        except (getpass.GetPassWarning, EOFError):
            raise RuntimeError('hidden terminal input unavailable; no credential was sent') from None
    try:
        return credential_bytes(value.encode('ascii'))
    except (UnicodeEncodeError, ValueError):
        raise RuntimeError('invalid credential; no credential was sent') from None


def credential_cases_qualified(result):
    for name in ['credentials.arguments', 'credentials.input', 'credentials.reflection', 'credentials.process']:
        cases = [case for case in result.get('cases', []) if case.get('id') == name]
        if len(cases) != 1:
            return False
        variants = [variant for variant in cases[0].get('variants', []) if variant.get('binary') == 'release' and variant.get('sabotage') is None]
        if not variants or any(variant.get('outcome') != 'pass' or variant.get('parts_skipped') or variant.get('skip_reason') for variant in variants):
            return False
    return True


def select_qualification(repo, identity):
    record = strict_json((repo / 'apparatus/qualified.json').read_bytes())
    found = [item for item in record['entries'] if item['id'] == identity]
    if len(found) != 1:
        raise ValueError('qualification ID not found')
    entry = found[0]
    if entry.get('suite') != 'acceptance' or entry.get('outcome') != 'qualified':
        raise ValueError('qualification must name a qualified acceptance run')
    platform = entry['platforms']['linux-aarch64']
    if platform['outcome'] != 'qualified':
        raise ValueError('native aarch64 binary is not qualified')
    binary_dir = repo / entry['evidence']['path'] / 'bin-arm64'
    if digest((binary_dir / 'stewart').read_bytes()) != platform['release_sha256']:
        raise ValueError('binary does not match the qualification record')
    evidence = repo / entry['evidence']['path'] / 'driver-arm64/evidence/RESULT.json'
    raw = evidence.read_bytes()
    result = strict_json(raw)
    if digest(raw) != platform['result_sha256'] or result['binaries']['release']['sha256'] != platform['release_sha256'] or not credential_cases_qualified(result):
        raise ValueError('native credential qualification is missing, skipped or does not match this binary')
    return entry, binary_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['rehearse', 'live'])
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--qualification', required=True)
    parser.add_argument('--commission', type=Path)
    parser.add_argument('--approved-commission', metavar='SHA256', help='live only: the exact packet digest authorized by the principal')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    out = args.evidence
    if not out.is_absolute() or out.parent != repo / '.scratch' or out.exists():
        parser.error('evidence must be a new absolute path directly under this checkout\'s .scratch')
    env = host_environment()
    if args.mode == 'live':
        if args.commission is None or args.approved_commission is None:
            parser.error('live needs --commission and --approved-commission; no implicit spending authority')
        raw = args.commission.read_bytes()
        if digest(raw) != args.approved_commission:
            parser.error('commission differs from the approved digest')
        try:
            commission = validate_commission(strict_json(raw))
        except (ValueError, json.JSONDecodeError) as error:
            parser.error(str(error))
        if not commission['spending_authority'] or not commission['spending_authority'].strip():
            parser.error('record the principal\'s bounded spending authorization before live launch')
        if not all(isinstance(value, str) and value.strip() for value in commission['account'].values()):
            parser.error('record the non-secret account, workspace and credential labels before live launch')
    else:
        if args.commission is not None or args.approved_commission is not None:
            parser.error('rehearsal has a fixed synthetic commission and accepts no live packet')
        commission = rehearsal_commission()
        raw = (json.dumps(commission, indent=2) + '\n').encode()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', 'apparatus/sanity', 'apparatus/driver/credential_observer.py'], cwd=repo, env=env)
    if dirty:
        parser.error('commit apparatus/sanity first; the container uses committed source')
    try:
        qualification, binary_dir = select_qualification(repo, args.qualification)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    # The qualification checker re-extracts retained evidence before we rely on it.
    checked = subprocess.run(['python3', '-I', '-B', 'apparatus/qualified.py', 'check'], cwd=repo, env=env, stdout=subprocess.DEVNULL)
    if checked.returncode:
        parser.error('qualification record check failed')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, env=env).decode().strip()
    actual_bindings = {'qualification_id': args.qualification,
        'binary_sha256': qualification['platforms']['linux-aarch64']['release_sha256'],
        'source_commit': source, 'submission_sha256': submission_identity(repo)}
    if args.mode == 'live' and commission['bindings'] != actual_bindings:
        parser.error('approved packet bindings differ from selected binary, source or specimen; prepare and review a new packet')
    if args.mode == 'rehearse':
        commission['bindings'] = actual_bindings
        raw = (json.dumps(commission, indent=2) + '\n').encode()
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    out.mkdir(mode=0o700)
    host, staging, exported = [out / n for n in ['host', 'staging', 'container']]
    for path in [host, staging, exported]:
        path.mkdir(mode=0o700)
    (staging / 'commission.json').write_bytes(raw)
    started = time.time()
    name = f'stewart-sanity-{int(started)}-{os.getpid()}'
    image = 'docker.io/library/python@' + qualification['python_image']
    report = {'schema': 'stewart.sanity-launch/1', 'mode': args.mode, 'started_at': started,
        'container': name, 'qualification': args.qualification,
        'binary_sha256': qualification['platforms']['linux-aarch64']['release_sha256'],
        'binary_source': qualification['source_commit'], 'commission_sha256': digest(raw),
        'source': source, 'bindings': actual_bindings,
        'model_calls': 0 if args.mode == 'rehearse' else None, 'credential_sent': False}

    def step(label, argv):
        with (host / (label + '.stdout')).open('xb') as stdout, (host / (label + '.stderr')).open('xb') as stderr:
            result = subprocess.run(argv, cwd=repo, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        (host / (label + '.exit')).write_text(str(result.returncode) + '\n')
        if result.returncode:
            raise RuntimeError(label + ' failed; inspect retained host records')

    proc = None
    try:
        step('version', ['container', '--version'])
        if 'version 1.6.1 ' not in (host / 'version.stdout').read_text():
            raise RuntimeError('this launcher requires Apple container 1.6.1')
        step('system-status', ['container', 'system', 'status'])
        step('image', ['container', 'image', 'inspect', image])
        step('archive', ['git', 'archive', '--format=tar', '-o', str(staging / 'source.tar'), 'HEAD', 'apparatus/sanity', 'apparatus/driver/credential_observer.py'])
        report['source_archive_sha256'] = digest((staging / 'source.tar').read_bytes())
        argv = ['container', 'run', '--name', name, '--detach', '--init', '--ulimit', 'core=0:0',
                '--cpus', '2', '--memory', '512M', '--platform', 'linux/arm64',
                '--network', 'none' if args.mode == 'rehearse' else 'default',
                '--mount', f'type=bind,source={staging},target=/in,readonly',
                '--mount', f'type=bind,source={binary_dir},target=/bin-in,readonly',
                '--mount', f'type=bind,source={exported},target=/out', image,
                'sh', '-c', 'umask 077; ulimit -c 0; mkdir -p /work/code && chmod 711 /work && chmod 755 /work/code && tar -xf /in/source.tar -C /work/code && touch /work/code/.ready && exec sleep infinity']
        write_json(host / 'container.argv.json', argv)
        (host / 'container.name').write_text(name + '\n')
        step('container-start', argv)
        step('container-ready', ['container', 'exec', name, 'sh', '-c', 'n=0; until test -f /work/code/.ready; do n=$((n+1)); test "$n" -lt 100 || exit 1; sleep 0.1; done'])
        # Independent operator calls can run while the foreground session is busy.
        operator_base = ['container', 'exec', name, 'env', '-i', 'PATH=/usr/local/bin:/usr/bin:/bin',
            'python3', '-I', '-B', '/work/code/apparatus/sanity/control.py']
        write_json(host / 'operator.json', {'container': name, 'status': operator_base + ['status'],
            'close': operator_base + ['close'], 'close_ends_authoring': True,
            'private_records': '/work/private', 'no_automatic_continuation': True})
        print('Retained container ' + name + '; operator commands: ' + str(host / 'operator.json'), flush=True)
        argv = ['container', 'exec', '--interactive', name, 'env', '-i',
                'PATH=/usr/local/bin:/usr/bin:/bin', 'HOME=/work', 'python3', '-I', '-B',
                '/work/code/apparatus/sanity/session.py', args.mode, '--binary', '/bin-in/stewart',
                '--packet', '/in/commission.json']
        write_json(host / 'session.argv.json', argv)
        with (host / 'container.stdout').open('xb') as stdout, (host / 'container.stderr').open('xb') as stderr:
            proc = subprocess.Popen(argv, cwd=repo, env=env, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
            deadline = time.monotonic() + 180
            while not (exported / 'READY.json').exists():
                if proc.poll() is not None:
                    raise RuntimeError('container ended before verified intake; no credential sent')
                if time.monotonic() >= deadline:
                    raise RuntimeError('intake readiness timed out; no credential sent')
                time.sleep(0.1)
            ready = strict_json((exported / 'READY.json').read_bytes())
            if ready.get('credential_free_intake_verified') is not True:
                raise RuntimeError('intake did not verify; no credential sent')
            key = (b'stewart-canary-NOT-A-CREDENTIAL-' + os.urandom(24).hex().encode()) if args.mode == 'rehearse' else hidden_credential()
            proc.stdin.write(key)
            proc.stdin.close()
            report['credential_sent'] = True
            report['container_exit'] = proc.wait()
        step('inspect', ['container', 'inspect', name])
        report['host_credential_scan'] = scan_tree(out, key)
        del key
        if report['host_credential_scan']['files_with_matches'] or report['host_credential_scan']['errors']:
            raise RuntimeError('host credential exposure or incomplete observation; private records retained for review')
        result = strict_json((exported / 'RESULT.json').read_bytes())
        report['session_outcome'] = result['outcome']
        report['outcome'] = ('completed' if args.mode == 'rehearse' else 'observed_review_required') if report['container_exit'] == 0 else 'failed'
    except (Exception, KeyboardInterrupt):
        # Values from an exception could include credential-bearing source bytes.
        report['outcome'] = 'failed'
        report['error'] = 'launch or observation failed; inspect retained records and container before any further action'
        if proc is not None and proc.stdin is not None and not proc.stdin.closed:
            proc.stdin.close()
        if proc is not None and proc.poll() is None:
            # Do not infer that a lost host reply stopped the service or repeat it.
            report['container_process_state'] = 'unknown; use recorded status/close commands'
    report['ended_at'] = time.time()
    write_json(host / 'RESULT.json', report)
    print(json.dumps(report, indent=2))
    return report['outcome'] not in ['completed', 'observed_review_required']


if __name__ == '__main__':
    raise SystemExit(main())
