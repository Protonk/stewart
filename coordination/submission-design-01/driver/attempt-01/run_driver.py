#!/usr/bin/env python3
"""Retain live driver streams outside the driver's own evidence directory."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', required=True)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--other-binary')
    parser.add_argument('--only', action='append', default=[])
    args = parser.parse_args()
    evidence = Path(args.evidence).absolute()
    launch = evidence.with_name(evidence.name + '.launch')
    launch.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-I', '-B', str(Path(args.driver).absolute()),
               '--binary', str(Path(args.binary).absolute()), '--evidence', str(evidence)]
    for selector in args.only:
        command += ['--only', selector]
    if args.other_binary:
        command += ['--other-binary', str(Path(args.other_binary).absolute())]
    write(launch / 'COMMAND.json', {'at': dt.datetime.now(dt.timezone.utc).isoformat(),
          'argv': command, 'cwd': str(Path.cwd()), 'launcher_argv': sys.argv})
    with (launch / 'stdout.bin').open('xb') as out, (launch / 'stderr.bin').open('xb') as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err)
        write(launch / 'START.json', {'pid': proc.pid, 'at': dt.datetime.now(dt.timezone.utc).isoformat()})
        code = proc.wait()
    write(launch / 'EXIT.json', {'pid': proc.pid, 'exit_code': code,
          'at': dt.datetime.now(dt.timezone.utc).isoformat()})
    print(json.dumps({'exit_code': code, 'launch': str(launch), 'evidence': str(evidence)}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
