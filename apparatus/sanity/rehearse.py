"""Run the sanity procedure with local fakes in one retained offline arm64 container.

Usage: python3 -I -B apparatus/sanity/rehearse.py /absolute/new/.scratch/run
Uses the release binary retained by acceptance-03. No builds, image pulls,
model calls, real credentials, live mode or automatic retries. Source is HEAD.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    out = args.evidence
    if not out.is_absolute() or out.parent != repo / '.scratch' or out.exists():
        parser.error('evidence must be a new absolute path directly under this checkout\'s .scratch')
    env = {k: v for k, v in os.environ.items() if k in ['PATH', 'HOME', 'TMPDIR', 'USER', 'LOGNAME']}
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', 'apparatus/sanity'], cwd=repo, env=env)
    if dirty:
        parser.error('commit apparatus/sanity before rehearsal; source is archived from HEAD')
    record = json.loads((repo / 'apparatus/qualified.json').read_text())
    qualification = next(entry for entry in record['entries'] if entry['id'] == 'acceptance-03')
    expected = qualification['platforms']['linux-aarch64']['release_sha256']
    binary_dir = repo / qualification['evidence']['path'] / 'bin-arm64'
    if hashlib.sha256((binary_dir / 'stewart').read_bytes()).hexdigest() != expected:
        parser.error('retained release binary does not match acceptance-03')
    out.mkdir()
    host = out / 'host'
    host.mkdir()
    (out / 'staging').mkdir()
    (out / 'container').mkdir()
    def step(name, argv):
        with (host / (name + '.stdout')).open('xb') as stdout, (host / (name + '.stderr')).open('xb') as stderr:
            result = subprocess.run(argv, cwd=repo, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        (host / (name + '.exit')).write_text(str(result.returncode) + '\n')
        print(f'{name}: exit {result.returncode}', flush=True)
        return result.returncode
    now = datetime.datetime.now(datetime.timezone.utc)
    name = f'stewart-sanity-{now:%Y%m%dT%H%M%SZ}-{os.getpid()}'
    result = {'started_at': now.isoformat(), 'container': name, 'binary_sha256': expected, 'binary_source': qualification['source_commit'], 'source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, env=env).decode().strip(), 'mode': 'offline-rehearsal', 'model_calls': 0}
    image = 'docker.io/library/python@' + qualification['python_image']
    try:
        for label, argv in [
            ('version', ['container', '--version']),
            ('system-status', ['container', 'system', 'status']),
            ('image', ['container', 'image', 'inspect', image]),
            ('archive', ['git', 'archive', '--format=tar', '-o', str(out / 'staging/source.tar'), 'HEAD', 'apparatus/sanity']),
        ]:
            if step(label, argv):
                raise RuntimeError(label + ' failed; see host outputs')
        if 'version 1.6.1 ' not in (host / 'version.stdout').read_text():
            raise RuntimeError('this procedure requires container 1.6.1')
        result['source_archive_sha256'] = hashlib.sha256((out / 'staging/source.tar').read_bytes()).hexdigest()
        (host / 'container.name').write_text(name + '\n')
        argv = ['container', 'run', '--name', name, '--network', 'none', '--init', '--cpus', '2', '--memory', '1G', '--platform', 'linux/arm64',
                '--mount', f'type=bind,source={out / "staging"},target=/in,readonly',
                '--mount', f'type=bind,source={binary_dir},target=/bin-in,readonly',
                '--mount', f'type=bind,source={out / "container"},target=/out', image,
                'sh', '-c', 'mkdir -p /work/code && tar -xf /in/source.tar -C /work/code && sh /work/code/apparatus/sanity/inner.sh']
        (host / 'container.argv.json').write_text(json.dumps(argv, indent=2) + '\n')
        result['container_exit'] = step('container-run', argv)
        result['inspect_exit'] = step('container-inspect', ['container', 'inspect', name])
        if result['container_exit'] or result['inspect_exit']:
            raise RuntimeError('rehearsal or retained-container inspection failed')
        report = json.loads((out / 'container/evidence/RESULT.json').read_text())
        if report['failures'] or len(report['scenarios']) != 3:
            raise RuntimeError('rehearsal reported failures or missing scenarios')
        result['scenarios'] = report['scenarios']
        result['outcome'] = 'passed'
    except Exception as error:
        result['outcome'], result['error'] = 'failed', str(error)
    result['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (host / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return result['outcome'] != 'passed'


if __name__ == '__main__':
    raise SystemExit(main())
