"""Independent captured-data review; no observer, source, wrapper or test execution."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import traceback

REPO = Path('/Users/raccoon/Desktop/Experiments/stewart')
ROOT = REPO / '.scratch/construction-execution-01'
OUT = ROOT / 'review/attempt-01'
CHECKS = []


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Repeated decoded control name: ' + key)
        value[key] = item
    return value


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique)


def check(label, actual, expected=True):
    passed = json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False)
    item = {'check': label, 'passed': passed}
    if not passed:
        item.update(actual=actual, expected=expected)
    CHECKS.append(item)


def write(name, raw):
    with (OUT / name).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def identity(path):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Not a regular nonlink file: ' + str(path))
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read()
        after = os.fstat(stream.fileno())
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_mtime_ns', 'st_ctime_ns')
    if any(getattr(before, key) != getattr(opened, key) or getattr(opened, key) != getattr(after, key) for key in fields):
        raise ValueError('File changed across reviewer read: ' + str(path))
    return {'bytes': len(raw), 'sha256': sha(raw), 'device': after.st_dev,
            'inode': after.st_ino, 'mode': stat.S_IMODE(after.st_mode),
            'mtime_ns': after.st_mtime_ns, 'ctime_ns': after.st_ctime_ns}


def inventory(root):
    value = {}
    for path in [root, *sorted(root.rglob('*'))]:
        s = path.lstat()
        name = str(path.relative_to(root))
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            raise ValueError('Cache found in retained protected inventory')
        if stat.S_ISDIR(s.st_mode):
            value[name + '/'] = {'kind': 'directory', 'device': s.st_dev,
                                'inode': s.st_ino, 'mode': stat.S_IMODE(s.st_mode)}
        elif stat.S_ISREG(s.st_mode):
            value[name] = {'kind': 'file', **identity(path)}
        else:
            raise ValueError('Nonregular entry in retained protected inventory')
    return value


def main():
    manifest_raw = (ROOT / 'RESULT-REVIEW-INPUTS-01.json').read_bytes()
    write('RESULT-REVIEW-INPUTS-01.json', manifest_raw)
    manifest = decode(manifest_raw)
    pins = {row['path']: row for row in manifest['inputs']}
    check('48 unique frozen result inputs', [len(manifest['inputs']), len(pins)], [48, 48])
    check('recorded preparation commit', manifest['head'], '4bc6bd9')
    for row in manifest['inputs']:
        path = REPO / row['snapshot']
        observed = identity(path)
        check('frozen result identity: ' + row['path'], [observed['bytes'], observed['sha256']], [row['bytes'], row['sha256']])

    def frozen(path):
        return (REPO / pins[path]['snapshot']).read_bytes()

    def ev(name):
        return frozen('.scratch/construction-execution-01/' + name)

    def record(name):
        return decode(ev(name))

    def doc(name):
        return frozen('coordination/construction-execution-01/' + name)

    original_manifest = decode(ev('REVIEW-INPUTS-01.json'))
    original_pins = {row['path']: row for row in original_manifest['inputs']}
    for name in ('PREPARATION.json', 'EXPECTED.json'):
        pin = original_pins['.scratch/construction-execution-01/' + name]
        raw = ev(name)
        check('result retains original preflight input: ' + name, [len(raw), sha(raw)], [pin['bytes'], pin['sha256']])
    original_expected = (REPO / original_pins['.scratch/construction-execution-01/EXPECTED.json']['snapshot']).read_bytes()
    expected = decode(original_expected)
    check('tracked expected bytes equal original expectation', doc('EXPECTED.json') == original_expected)
    prep = record('PREPARATION.json')
    reservation, launch, exit_record = record('RUN-RESERVATION.json'), record('RUN-PLAN.json'), record('EXIT.json')
    pre, post, pid = record('PRELAUNCH.json'), record('POSTRUN.json'), record('PID.json')
    approval = record('PREFLIGHT-DISPOSITION.json')
    reviewer_approval = decode((OUT / 'PREFLIGHT.json').read_bytes())
    check('approval binds independent reviewer driver', approval['reviewed_driver'], reviewer_approval['reviewed_driver'])
    check('approval binds independent reviewer preparation', approval['preparation_sha256'], reviewer_approval['preparation_sha256'])
    check('reservation binds approved driver', reservation['driver'], approval['reviewed_driver'])
    check('reservation binds exact original preparation', reservation['preparation_sha256'], sha(ev('PREPARATION.json')))
    check('driver captured revision identity', [len(doc('study.py')), sha(doc('study.py'))], [approval['reviewed_driver']['bytes'], approval['reviewed_driver']['sha256']])
    for key in ('argv', 'cwd', 'env', 'stdin', 'timeout_seconds', 'start_new_session'):
        check('launch follows preparation: ' + key, launch[key], prep[key])
    check('launch capture destinations', [launch['stdout'], launch['stderr']], ['observer.stdout', 'observer.stderr'])
    check('PID and exit identify one retained process', [pid['pid'], exit_record['pid']], [69922, 69922])
    check('process normal exit', exit_record['exit'], 0)
    check('postrun observed termination', post['termination_observed'], True)
    check('event timestamps ordered', [datetime.fromisoformat(value['at']) for value in (approval, reservation, pre, launch, pid, exit_record, post)] == sorted(datetime.fromisoformat(value['at']) for value in (approval, reservation, pre, launch, pid, exit_record, post)))
    for scope in ('stage', 'witness'):
        check('parent prelaunch exact inventory: ' + scope, pre[scope], prep[scope])
        check('parent postrun exact inventory: ' + scope, post[scope], prep[scope])
        check('reviewer current exact inventory: ' + scope, inventory(ROOT / scope), prep[scope])
        check('parent endpoint claim: ' + scope, post[scope + '_matches_preparation'], True)
    check('parent interpreter endpoint claim', post['interpreter_matches_preparation'], True)
    check('parent explicit preservation limit', post['continuous_preservation_established'], False)
    for name in ('RUN-FAILURE.json', 'TIMEOUT.json', 'KILL.json', 'PARENT-FAILURE-INTERVENTION.json', 'PARENT-FAILURE-KILL.json'):
        check('no retained intervention record: ' + name, (ROOT / name).exists(), False)
    stdout, stderr = ev('observer.stdout'), ev('observer.stderr')
    write('captured-observer.stdout', stdout)
    write('captured-observer.stderr', stderr)
    for name, raw in (('stdout', stdout), ('stderr', stderr)):
        check('frozen raw output matches exit record: ' + name, [len(raw), sha(raw)], [exit_record[name]['bytes'], exit_record[name]['sha256']])
        check('retained output full current identity: ' + name, identity(ROOT / ('observer.' + name)), exit_record[name])
    check('empty captured stderr', stderr == b'')
    check('tracked observed bytes exact raw stdout', doc('OBSERVATIONS.jsonl') == stdout)
    capture = decode(doc('CAPTURE.json'))
    check('tracked capture exact exit record', capture['exit_record'], exit_record)
    check('tracked capture exact launch plan', capture['launch_plan'], launch)
    check('recorded selectors', [capture['observer_invocations'], capture['specimen_evaluations'], capture['pytest_nodes'], capture['installed_wheel_runs']], [1, 6, 0, 0])
    check('capture preservation scope', capture['continuous_preservation_established'], False)
    rows = [decode(line) for line in stdout.splitlines()]
    names = ('A-complete.jsonl', 'B-duplicate.jsonl', 'C-note-invariant.jsonl', 'D-control-extinguished.jsonl', 'E-admission-before-reach.jsonl', 'F-parse-problem.jsonl')
    check('eight records exact stage order', [row['stage'] for row in rows], ['before', *(['specimen'] * 6), 'after'])
    check('exact six evaluation names and order', [row['name'] for row in rows if row['stage'] == 'specimen'], list(names))
    if len(rows) != 8:
        raise ValueError('Refuse positional review of unexpected capture population')
    first, last = rows[0], rows[-1]
    expected_hashes = {}
    for name, item in prep['stage'].items():
        if item['kind'] != 'file':
            continue
        key = 'observer' if name == 'specimens/observe-proposed.py' else name.replace('specimens/', 'authored/', 1)
        expected_hashes[key] = item['sha256']
        pin = original_pins['.scratch/construction-execution-01/stage/' + name]
        original = (REPO / pin['snapshot']).read_bytes()
        check('original frozen selected byte identity: ' + name, [len(original), sha(original)], [item['bytes'], item['sha256']])
        check('stage equals original selected bytes: ' + name, (ROOT / 'stage' / name).read_bytes() == original)
        check('independent witness equals original selected bytes: ' + name, (ROOT / 'witness/stage' / name).read_bytes() == original)
    check('13 protected hash identities', len(expected_hashes), 13)
    for label, row in [('before', first), ('after', last)]:
        check('child exact protected hashes: ' + label, row['hashes'], expected_hashes)
        check('child leaves continuous preservation unestablished: ' + label, row['continuous_preservation_established'], False)
    check('child endpoint equality claim', last['same_at_endpoints'], first['hashes'] == last['hashes'])
    check('child version matches qualified probe', first['python'], prep['probe']['version'])
    check('child interpreter matches qualified probe', first['executable'], prep['probe']['executable'])
    for name, actual in zip(names, rows[1:7]):
        predicted = expected[name]
        input_identity = prep['stage']['specimens/' + name]
        check('read bytes identify selected specimen: ' + name, [actual['bytes'], actual['sha256']], [input_identity['bytes'], input_identity['sha256']])
        for key in ('parsed_rows', 'raw_valid_compare_rows', 'summary', 'prerequisites'):
            check('original complete prediction: ' + name + ':' + key, actual[key], predicted[key])
        if name == names[5]:
            check('F exactly one separate invalid-JSON line-11 problem', [[p['line'], p['problem'].startswith('invalid JSON row:')] for p in actual['parse_problems']], [[11, True]])
        else:
            check('original empty parse-problem prediction: ' + name, actual['parse_problems'], [])
    a, b, c, d, e, f = rows[1:7]
    check('A/B raw row and control invariance', [b['parsed_rows'], b['raw_valid_compare_rows'], b['summary']['populations']['control']], [a['parsed_rows'], a['raw_valid_compare_rows'], a['summary']['populations']['control']])
    check('A/B ordinary membership effect', [a['summary']['populations']['ordinary']['compared'], b['summary']['populations']['ordinary']['compared']], [3, 1])
    check('C complete semantic observation invariant', [c['parse_problems'], c['summary'], c['prerequisites']], [a['parse_problems'], a['summary'], a['prerequisites']])
    check('C emitted identity is distinct', [a['name'] != c['name'], a['bytes'] != c['bytes'], a['sha256'] != c['sha256']], [True, True, True])
    check('D control operand effect and attributed flag gap', [d['summary']['populations']['control']['mismatches'], d['summary']['inconsistent_comparisons']], [0, ['switch-control']])
    check('E absent coverage lists do not hide invalid admission', [e['summary']['populations']['ordinary']['admitted'], e['summary']['missing_measurements'], e['summary']['uncompared'], e['summary']['unresolved_admission']], [0, [], [], ['parcel-check']])
    check('F summary/prerequisites equal A with separate gap', [f['summary'], f['prerequisites'], len(f['parse_problems'])], [a['summary'], a['prerequisites'], 1])
    comparison = record('COMPARISON-01.json')
    check('root actual check totals and success', [comparison['passed'], comparison['total'], len(comparison['checks']), sum(r['passed'] is True for r in comparison['checks']), comparison['exception']], [107, 107, 107, 107, None])
    check('root comparator code pin', comparison['code_sha256'], sha(doc('compare.py')))
    check('root comparator is reviewed revision', sha(doc('compare.py')), reviewer_approval['reviewed_comparator']['sha256'])
    check('root comparator records no target invocation', comparison['observer_invocations_by_this_comparator'], 0)
    report = doc('RESULT.md').decode()
    table_rows = [line for line in report.splitlines() if re.match(r'\| [A-F] — ', line)]
    check('report has exactly six specimen table rows', len(table_rows), 6)
    for index, line in enumerate(table_rows):
        columns = [v.strip() for v in line.split('|')[1:-1]]
        actual = rows[index + 1]['summary']['populations']
        check('report ordinary/control counts: ' + names[index], [columns[1], columns[2]], [str(actual['ordinary']['compared']) + ' / ' + str(actual['ordinary']['mismatches']), str(actual['control']['compared']) + ' / ' + str(actual['control']['mismatches'])])
    check('report captured stdout digest', sha(stdout) in report)
    check('report actual selector statement', 'one observer process, six specimen\nevaluations, zero pytest nodes, zero installed-wheel runs' in report)
    command_raw = (ROOT / 'COMMAND-ACCOUNT.json').read_bytes()
    write('COMMAND-ACCOUNT.json', command_raw)
    account = decode(command_raw)
    check('outer command account candidly retrospective', 'after completed tool calls' in account['provenance'])
    check('outer account command count', len(account['commands']), 3)
    for index, command in enumerate(account['commands']):
        check('outer command reported exit: ' + str(index), command['outer_exit_observed'], 0)
        check('outer command isolated explicit interpreter: ' + str(index), command['argv'][:4], ['/opt/homebrew/bin/python3.14', '-I', '-B', '-S'])
        for channel, item in command['outputs'].items():
            output = frozen(item['path'])
            check('outer command retained output: ' + item['path'], [len(output), sha(output)], [item['bytes'], item['sha256']])
    # The author explicitly admitted this narrow correction after the frozen draft.
    corrected_report = (REPO / 'coordination/construction-execution-01/RESULT.md').read_bytes()
    write('RESULT-corrected-draft-01.md', corrected_report)
    text = corrected_report.decode()
    check('C overbroad entire-result wording removed in corrected draft', "C's note-only change leaves the\nfull result invariant." not in text and 'full result invariant' not in text)
    check('C corrected semantic invariance wording present', 'full summary and prerequisites unchanged' in text)


if __name__ == '__main__':
    failure = None
    try:
        main()
    except BaseException:
        failure = traceback.format_exc()
    result = {'at': datetime.now(timezone.utc).isoformat(), 'checks': CHECKS,
              'passed': sum(r['passed'] for r in CHECKS), 'total': len(CHECKS),
              'exception': failure, 'observer_invocations': 0, 'pytest_nodes': 0,
              'code_sha256': sha(Path(__file__).read_bytes()),
              'scope': 'Frozen captured-data comparisons and current endpoint reads; no target execution and no continuous monitoring.'}
    write('RESULT-CHECKS-01.json', (json.dumps(result, indent=2, sort_keys=True) + '\n').encode())
    print(f"Independent result checks: {result['passed']}/{result['total']}; exception: {bool(failure)}")
    if failure:
        print(failure, file=sys.stderr)
    for item in CHECKS:
        if not item['passed']:
            print(json.dumps(item, sort_keys=True), file=sys.stderr)
    sys.exit(1 if failure or result['passed'] != result['total'] else 0)
