"""Read-only finite verification of selected independent-driver evidence."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import signal
import stat

ROOT = Path('/Users/raccoon/Desktop/Experiments/stewart')
BASE = ROOT / '.scratch/submission-prototype-01/driver'
parser = argparse.ArgumentParser()
parser.add_argument('--runs', nargs='+', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
assert len(set(args.runs)) == len(args.runs)
checks = []
summaries = []

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def read_json(path):
    return json.loads(path.read_bytes())

def check(ok, label, path, detail=None):
    checks.append({'ok': bool(ok), 'label': label, 'path': str(path), 'detail': detail})

for run in args.runs:
    assert run.startswith('run-') and '/' not in run
    path = BASE / run
    start = read_json(path / 'START.json')
    result = read_json(path / 'RESULT.json')
    check(digest((path / 'tested-binary').read_bytes()) == start['binary_sha256'], 'tested binary pin', path)
    check(digest((path / 'driver-source.py').read_bytes()) == start['driver_sha256'], 'driver source pin', path)
    wanted = start['selected_cases']
    actual = [x['case'] for x in result['cases']]
    check(len(wanted) == len(set(wanted)) and wanted == actual, 'exact ordered unique selected case population', path)
    check(set(x.name for x in (path / 'cases').iterdir()) == set(wanted), 'case directory population', path)
    check(result['selected_cases'] == len(actual), 'selected case count', path)
    case_passes = 0
    assertions = 0
    invocations = 0
    barriers = 0
    for row in result['cases']:
        case = path / 'cases' / row['case']
        recorded = read_json(case / 'RESULT.json')
        check(recorded == row, 'case result binding', case)
        rows = [json.loads(line) for line in (case / 'assertions.jsonl').read_bytes().splitlines()]
        check(len(rows) == row['assertions'], 'assertion count', case)
        check([x['number'] for x in rows] == list(range(1, len(rows) + 1)), 'assertion identity population', case)
        check(not row['passed'] or all(x['pass'] for x in rows), 'passed case has no failed assertion', case)
        check(row['passed'] == (row['error'] is None), 'result retains failure distinction', case)
        case_passes += int(row['passed'])
        assertions += len(rows)
        commands = sorted((case / 'commands').iterdir())
        check(len(commands) == row['invocations'], 'invocation count', case)
        check([x.name for x in commands] == [f'{n:04d}' for n in range(1, len(commands) + 1)], 'invocation identity population', case)
        invocations += len(commands)
        for command in commands:
            begin = read_json(command / 'START.json')
            end = read_json(command / 'EXIT.json')
            stdin = (command / 'stdin.bin').read_bytes()
            stdout = (command / 'stdout.bin').read_bytes()
            stderr = (command / 'stderr.bin').read_bytes()
            check(begin['stdin_size'] == len(stdin) and begin['stdin_sha256'] == digest(stdin), 'raw input binding', command)
            check(end['stdout_size'] == len(stdout) and end['stdout_sha256'] == digest(stdout) and end['stderr_sha256'] == digest(stderr), 'raw output bindings', command)
            check(begin['pid'] == end['pid'], 'process identity', command)
            check(str(begin['cwd']).startswith('/private/tmp/stewart-submission-driver-'), 'unrelated retained subprocess cwd', command)
            if begin['argv'][1:] == ['--help']:
                check(end['exit_code'] == 0 and b'stewart-submission-prototype' in stdout, 'documented non-JSON help outcome', command)
            elif end['exit_code'] in (0, 2):
                value = json.loads(stdout)
                check(isinstance(value, dict) and value.get('ok') == (end['exit_code'] == 0), 'structured process outcome agrees with exit', command)
            if end['exit_code'] == -signal.SIGKILL:
                signals = [read_json(x) for x in command.glob('SIGNAL-*.json')]
                check(any(x['pid'] == begin['pid'] and x['signal'] == 'SIGKILL' for x in signals), 'killed process has same-PID signal record', command)
            barrier = command / 'BARRIER.json'
            if barrier.exists():
                b = read_json(barrier)
                marker = b.get('marker')
                stopped = b.get('kernel_stop')
                barriers += 1
                check(marker in [json.loads(line) for line in stderr.splitlines()], 'barrier marker is in raw stderr', command)
                check(stopped and stopped['pid'] == begin['pid'] and stopped['stop_signal'] == signal.SIGSTOP, 'independent kernel stop matches PID', command)
                check(marker and marker['hook'] == begin['hook'], 'requested barrier identity', command)
                if marker:
                    snap = read_json(case / f'stopped-{command.name}.snapshot.json')
                    check((marker['commit'] in snap) == (marker['hook'] in ('after_publish', 'after_sync')), 'snapshot proves publication side', command)
    check(case_passes == result['passed_cases'] and len(actual) - case_passes == result['failed_cases'], 'pass/failure counts', path)
    check(assertions == result['assertions'], 'total assertion count', path)
    check(invocations == result['invocations'], 'total invocation count', path)
    # Verify finite final inventory against the retained independent working tree.
    work = Path(result['working_tree'])
    assert str(work).startswith('/private/tmp/stewart-submission-driver-')
    inventory = result['working_inventory']
    actual_members = set()
    for directory, dirs, files in os.walk(work, followlinks=False):
        for name in dirs + files:
            actual_members.add(str((Path(directory) / name).relative_to(work)))
    check(actual_members == set(inventory), 'exact retained working-tree population', work)
    for name, item in inventory.items():
        target = work / name
        s = target.lstat()
        if item['kind'] == 'file':
            check(stat.S_ISREG(s.st_mode) and s.st_size == item['size'] and digest(target.read_bytes()) == item['sha256'], 'retained regular-file byte identity', target)
        elif item['kind'] == 'symlink':
            check(stat.S_ISLNK(s.st_mode) and os.readlink(target) == item['target'], 'retained symlink identity without traversal', target)
        elif item['kind'] == 'directory':
            check(stat.S_ISDIR(s.st_mode), 'retained directory kind', target)
        else:
            check(not stat.S_ISREG(s.st_mode) and not stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode), 'retained special kind without reading', target)
    summaries.append({'run': run, 'binary_sha256': start['binary_sha256'], 'driver_sha256': start['driver_sha256'], 'selected': len(actual), 'passed': case_passes, 'failed': len(actual) - case_passes, 'assertions': assertions, 'invocations': invocations, 'barriers': barriers, 'failed_cases': [x['case'] for x in result['cases'] if not x['passed']]})

output = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'pid': os.getpid(), 'runs': summaries, 'check_count': len(checks), 'passed_checks': sum(x['ok'] for x in checks), 'failed_checks': [x for x in checks if not x['ok']], 'checks': checks, 'scope': 'finite read-only trace and retained-inventory verification; no subject execution or historical authentication'}
with Path(args.output).open('x') as stream:
    json.dump(output, stream, indent=2)
    stream.write('\n')
print(json.dumps({k: v for k, v in output.items() if k != 'checks'}, indent=2))
