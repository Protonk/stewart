"""Retain exact argv, streams and outcomes for this audit's manager commands."""

import datetime
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[2]
run = root / '.scratch/opus-preparation-audit-01/run-001'
config = json.loads((run / 'CONFIG.json').read_text())
label, *arguments = sys.argv[1:]
if not label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in label):
    raise SystemExit('Use a new lowercase operation label.')
prefix = [config['python'], '-I', '-B', str(root / 'src/stewart/_bootstrap.py'),
          'source', '--manager-home', config['manager_home'], '--', '--json',
          '--repo', config['repo'], '--workspace', config['workspace']]
argv = prefix + arguments


def save(suffix, value):
    with (run / (label + suffix)).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


save('.start.json', {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     'argv': argv, 'cwd': str(root)})
with (run / (label + '.stdout')).open('xb') as out, (run / (label + '.stderr')).open('xb') as err:
    process = subprocess.Popen(argv, cwd=root, stdout=out, stderr=err)
    save('.process.json', {'pid': process.pid})
    code = process.wait()
save('.end.json', {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'exit_code': code})
print((run / (label + '.stdout')).read_text())
print((run / (label + '.stderr')).read_text(), file=sys.stderr)
raise SystemExit(code)
