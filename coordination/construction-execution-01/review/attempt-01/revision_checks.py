"""Static inspection of admitted preflight revision; never execute its code."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import stat
import sys
import traceback

REPO = Path('/Users/raccoon/Desktop/Experiments/stewart')
ROOT = REPO / '.scratch/construction-execution-01'
OUT = ROOT / 'review/attempt-01'
CHECKS = []


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(name, raw):
    with (OUT / name).open('xb') as stream:
        stream.write(raw)


def check(name, actual, expected=True):
    passed = json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)
    row = {'check': name, 'passed': passed}
    if not passed:
        row.update(actual=actual, expected=expected)
    CHECKS.append(row)


def main():
    raw_manifest = (ROOT / 'PREFLIGHT-REVISION-02.json').read_bytes()
    write('PREFLIGHT-REVISION-02.json', raw_manifest)
    manifest = json.loads(raw_manifest)
    check('revision exact membership', [Path(row['path']).name for row in manifest['inputs']], ['study.py', 'compare.py', 'PROTOCOL.md'])
    initial = ROOT / 'review-inputs-01/coordination/construction-execution-01'
    for entry in manifest['inputs']:
        name = Path(entry['path']).name
        new = (REPO / entry['snapshot']).read_bytes()
        write('revision-02-' + name, new)
        old = (ROOT / 'comparator-before-run.py').read_bytes() if name == 'compare.py' else (initial / name).read_bytes()
        identity = entry['identity']
        check('revised snapshot identity: ' + name, [len(new), sha(new)], [identity['bytes'], identity['sha256']])
        current = REPO / entry['path']
        st = current.lstat()
        check('revised current bytes: ' + name, current.read_bytes() == new)
        check('revised current identity: ' + name, [st.st_dev, st.st_ino, stat.S_IMODE(st.st_mode), st.st_mtime_ns, st.st_ctime_ns], [identity['device'], identity['inode'], identity['mode'], identity['mtime_ns'], identity['ctime_ns']])
        diff = ''.join(difflib.unified_diff(old.decode().splitlines(keepends=True), new.decode().splitlines(keepends=True), fromfile='initial/' + name, tofile='revision-02/' + name))
        write('revision-02-' + name + '.diff', diff.encode())
        if name == 'study.py':
            old_tree, new_tree = ast.parse(old), ast.parse(new)
            unaffected = lambda tree: [ast.dump(node) for node in tree.body if not (isinstance(node, ast.FunctionDef) and node.name == 'run_once')]
            check('driver changes confined to run_once', unaffected(old_tree), unaffected(new_tree))
            text = new.decode()
            check('driver uses reviewed driver binding', "identity(Path(__file__).resolve()) != approval['reviewed_driver']" in text)
            check('driver normal postrun explicitly records termination', "'termination_observed': process is not None" in text)
            check('driver unresolved termination avoids inventory branch', "'termination_observed': False,\n                          'inventory_not_attempted': 'Child termination is unresolved'" in text)
        elif name == 'compare.py':
            old_lines, new_lines = old.decode().splitlines(), new.decode().splitlines()
            removed = [s for s in difflib.ndiff(old_lines, new_lines) if s.startswith('- ')]
            check('comparator removes no original checks', removed, [])
            check('comparator compares reviewed driver', "read('PREFLIGHT-DISPOSITION.json')['reviewed_driver']" in new.decode())
            check('comparator requires child termination observation', "after['termination_observed'], True" in new.decode())
    initial_checks = json.loads((OUT / 'STATIC-CHECKS-01.json').read_bytes())
    failed = [r['check'] for r in initial_checks['checks'] if not r['passed']]
    check('original failed comparison explained exactly', failed, ['supplemental comparator current bytes'])
    original_pin = json.loads((ROOT / 'COMPARATOR-PIN.json').read_bytes())
    original = (ROOT / 'comparator-before-run.py').read_bytes()
    check('original comparator evidence preserved', [len(original), sha(original)], [original_pin['bytes'], original_pin['sha256']])
    pins = json.loads((ROOT / 'REVIEW-INPUTS-01.json').read_bytes())['inputs']
    for suffix in ('PREPARATION.json', 'EXPECTED.json'):
        pin = next(p for p in pins if p['path'] == '.scratch/construction-execution-01/' + suffix)
        raw = (ROOT / suffix).read_bytes()
        check('original preparation input preserved: ' + suffix, [len(raw), sha(raw)], [pin['bytes'], pin['sha256']])
    for name in ('RUN-RESERVATION.json', 'PID.json', 'observer.stdout', 'observer.stderr'):
        check('no launch evidence at revised preflight: ' + name, (ROOT / name).exists(), False)


if __name__ == '__main__':
    failure = None
    try:
        main()
    except BaseException:
        failure = traceback.format_exc()
    result = {'at': datetime.now(timezone.utc).isoformat(), 'checks': CHECKS,
              'passed': sum(c['passed'] for c in CHECKS), 'total': len(CHECKS),
              'exception': failure, 'observer_invocations': 0, 'pytest_nodes': 0,
              'review_code_sha256': sha(Path(__file__).read_bytes())}
    write('REVISION-CHECKS-02.json', (json.dumps(result, indent=2, sort_keys=True) + '\n').encode())
    print(f"Revision static checks: {result['passed']}/{result['total']}; exception: {bool(failure)}")
    if failure:
        print(failure, file=sys.stderr)
    for item in CHECKS:
        if not item['passed']:
            print(json.dumps(item, sort_keys=True), file=sys.stderr)
    sys.exit(1 if failure or result['passed'] != result['total'] else 0)
