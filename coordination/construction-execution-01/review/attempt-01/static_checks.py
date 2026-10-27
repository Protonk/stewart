"""Independent static review only: no target import, compile or execution.

The only subprocesses are read-only git show calls for manifest-named objects.
All receipts/logs are exclusively created beneath this review attempt.
"""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import traceback

REPO = Path('/Users/raccoon/Desktop/Experiments/stewart')
ROOT = REPO / '.scratch/construction-execution-01'
OUT = ROOT / 'review/attempt-01'
HEAD = '9ffad1fd5a628d90d17da75000a5b3a385031d8c'
SOURCE = '81b557a78db156e7bfc5e8d35ece9d1438608d87'
CHECKS = []
COMMANDS = []


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Repeated decoded key: ' + key)
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique)


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


def check(name, actual, expected=True):
    okay = canonical(actual) == canonical(expected)
    record = {'check': name, 'passed': okay}
    if not okay:
        record.update(actual=actual, expected=expected)
    CHECKS.append(record)


def write(name, raw):
    with (OUT / name).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def receipt(name, value):
    write(name, (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode())


def git_read(revision, path):
    argv = ['/usr/bin/git', 'show', revision + ':' + path]
    proc = subprocess.run(argv, cwd=REPO, stdin=subprocess.DEVNULL, capture_output=True)
    index = len(COMMANDS) + 1
    write(f'git-{index:02d}.stdout', proc.stdout)
    write(f'git-{index:02d}.stderr', proc.stderr)
    COMMANDS.append({'argv': argv, 'cwd': str(REPO), 'exit': proc.returncode,
                     'stdout_bytes': len(proc.stdout), 'stdout_sha256': sha(proc.stdout),
                     'stdout': f'git-{index:02d}.stdout', 'stderr': f'git-{index:02d}.stderr'})
    check('git show succeeded: ' + path, proc.returncode, 0)
    check('git show stderr empty: ' + path, proc.stderr == b'')
    return proc.stdout


def main():
    manifest_raw = (ROOT / 'REVIEW-INPUTS-01.json').read_bytes()
    manifest = decode(manifest_raw)
    write('REVIEW-INPUTS-01.json', manifest_raw)
    pins = {item['path']: item for item in manifest['inputs']}
    check('frozen manifest source HEAD', manifest['source_head'], HEAD)
    check('frozen input count', len(manifest['inputs']), 63)
    check('frozen path uniqueness', len(pins), 63)
    for item in manifest['inputs']:
        path = REPO / item['snapshot']
        check('frozen regular nonlink: ' + item['path'], stat.S_ISREG(path.lstat().st_mode))
        raw = path.read_bytes()
        check('frozen bytes/hash: ' + item['path'], [len(raw), sha(raw)], [item['bytes'], item['sha256']])

    def frozen(path):
        return (REPO / pins[path]['snapshot']).read_bytes()

    def evidence(name):
        return frozen('.scratch/construction-execution-01/' + name)

    def obj(name):
        return decode(evidence(name))

    prep = obj('PREPARATION.json')
    prep_checks = obj('PREPARATION-CHECKS.json')
    check('preparation checks retained complete', [prep_checks['passed'], prep_checks['total']], [60, 60])
    check('every preparation check reported passed', all(x['passed'] is True for x in prep_checks['checks']))
    check('preparation HEAD and source', [prep['source_head'], prep['source_revision']], [HEAD, SOURCE])
    check('current preparation bytes equal frozen preparation', (ROOT / 'PREPARATION.json').read_bytes() == evidence('PREPARATION.json'))
    envelope_raw = evidence('witness/FINAL-ENVELOPE.json')
    envelope = decode(envelope_raw)
    check('committed final envelope equals witness', git_read(HEAD, 'coordination/fresh-authoring-01/author/attempt-01/FINAL-ENVELOPE.json') == envelope_raw)
    check('prior raw equals final envelope', evidence('witness/prior/attempt.raw') == envelope_raw)
    check('prior snapshot envelope equals final envelope', obj('witness/prior/SNAPSHOT.json')['envelope'], envelope)
    accepted = obj('witness/prior/ACCEPTED.json')
    check('acceptance raw binding', accepted['raw_transport'], {'bytes': len(envelope_raw), 'sha256': sha(envelope_raw)})
    check('acceptance only structural', [accepted['status'], accepted['intellectual_assessment']], ['structurally_accepted', 'not_performed'])
    prior_pins = {entry['path']: entry for entry in obj('witness/prior/COMPLETION.json')['evidence_before_this_record']}
    for name in ('attempt.raw', 'SNAPSHOT.json', 'ACCEPTED.json'):
        old = prior_pins['.scratch/fresh-authoring-01/pilot-01/final-submission-01/' + name]
        raw = evidence('witness/prior/' + name)
        check('prior completion pin: ' + name, [len(raw), sha(raw)], [old['bytes'], old['sha256']])
    check('envelope question and source', [envelope['question_id'], envelope['source_revision']], ['ledger-membership-construction-01', SOURCE])
    support = {item['id']: item for item in envelope['support']}
    check('18 unique support objects', [len(support), len(envelope['support'])], [18, 18])
    subject = obj('witness/packet/SUBJECT.json')
    check('subject revision', subject['source_revision'], SOURCE)
    question = evidence('witness/packet/QUESTION.md')
    check('packet question pin', [len(question), sha(question)], [subject['question_bytes'], subject['question_sha256']])
    for item in subject['subject_files']:
        source = evidence('witness/git-source/' + item['source_path'])
        packet = evidence('witness/packet/' + item['packet_file'])
        check('source pin: ' + item['source_path'], [len(source), sha(source)], [item['source_bytes'], item['source_sha256']])
        check('source matches Git: ' + item['source_path'], git_read(SOURCE, item['source_path']) == source)
        check('packet pin: ' + item['packet_file'], [len(packet), sha(packet)], [item['packet_bytes'], item['packet_sha256']])
        if item['selected_ranges'] is None:
            check('full source packet: ' + item['packet_file'], packet == source)
        else:
            lines = source.decode().splitlines(keepends=True)
            selected = ''.join('\n--- ' + item['source_path'] + ', original lines ' + str(a) + '-' + str(b) + ' ---\n' + ''.join(lines[a-1:b]) for a, b in item['selected_ranges'])
            check('exact source excerpt: ' + item['packet_file'], packet.decode(), selected)
    specimens = ('A-complete.jsonl', 'B-duplicate.jsonl', 'C-note-invariant.jsonl', 'D-control-extinguished.jsonl', 'E-admission-before-reach.jsonl', 'F-parse-problem.jsonl')
    packet_names = ('ledger.py', '_json.py', 'test_stewart_ledger.py')
    support_names = ('review.json', *specimens, 'PREDICTIONS.md', 'CONSTRUCTION.md', 'observe-proposed.py')
    stage_names = {'packet/' + name for name in packet_names} | {'specimens/' + name for name in support_names}
    check('preparation protected inventory membership', sorted(prep['stage']), sorted(stage_names | {'./', 'packet/', 'specimens/'}))
    check('13 protected files', len(stage_names), 13)
    for name in sorted(stage_names):
        raw = evidence('stage/' + name)
        entry = prep['stage'][name]
        check('stage pin: ' + name, [len(raw), sha(raw), entry['mode']], [entry['bytes'], entry['sha256'], 0o444])
        check('stage witness: ' + name, evidence('witness/stage/' + name) == raw)
        if name.startswith('specimens/'):
            item = support[name.split('/', 1)[1]]
            check('selected support bytes: ' + name, [item['encoding'], item['text'].encode() == raw], ['utf-8', True])
        else:
            check('selected source bytes: ' + name, evidence('witness/' + name) == raw)
    for name in ('./', 'packet/', 'specimens/'):
        check('stage directory mode: ' + name, prep['stage'][name]['mode'], 0o555)
    # The following are ordinary current endpoint reads, not continuous monitoring.
    actual_names = {'./'}
    for path in (ROOT / 'stage').rglob('*'):
        mode = path.lstat().st_mode
        rel = str(path.relative_to(ROOT / 'stage'))
        check('current stage ordinary entry: ' + rel, stat.S_ISREG(mode) or stat.S_ISDIR(mode))
        actual_names.add(rel + '/' if stat.S_ISDIR(mode) else rel)
    check('current stage exact inventory', sorted(actual_names), sorted(prep['stage']))
    for name, entry in prep['stage'].items():
        path = ROOT / 'stage' / name.rstrip('/')
        st = path.lstat()
        check('current stage inode/mode: ' + name, [st.st_dev, st.st_ino, stat.S_IMODE(st.st_mode)], [entry['device'], entry['inode'], entry['mode']])
        if entry['kind'] == 'file':
            check('current stage exact bytes: ' + name, path.read_bytes() == evidence('stage/' + name))
    probe, probe_plan = obj('probe.stdout'), obj('PROBE-PLAN.json')
    check('probe successful and stderr empty', [obj('PROBE-EXIT.json')['exit'], evidence('probe.stderr') == b''], [0, True])
    check('probe identity and launch agreement', [prep['probe'], prep['argv'][0]], [probe, probe_plan['argv'][0]])
    check('probe isolated Python 3.14', [probe['version_info'][:2], probe['isolated'], probe['no_site'], probe['dont_write_bytecode'], probe['site_loaded'], probe['pycache_prefix']], [[3, 14], 1, 1, True, False, None])
    expected_argv = [probe['executable'], '-I', '-B', '-S', str(ROOT / 'stage/specimens/observe-proposed.py'), '--packet', str(ROOT / 'stage/packet'), '--specimens', str(ROOT / 'stage/specimens')]
    check('exact observer argv', prep['argv'], expected_argv)
    check('exact observer launch settings', [prep['cwd'], prep['env'], prep['stdin'], prep['timeout_seconds'], prep['start_new_session']], [str(ROOT / 'stage'), {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'TZ': 'UTC'}, 'DEVNULL', 30, True])
    check('preparation preservation qualification', prep['continuous_preservation_established'], False)
    driver = frozen('coordination/construction-execution-01/study.py')
    check('driver frozen pin', [len(driver), sha(driver)], [prep['driver']['bytes'], prep['driver']['sha256']])
    # Root is revising the known caught-parent-exception path. The original
    # preparation binding is checked here; the new driver gets separate review.
    expected = obj('EXPECTED.json')
    check('expected frozen pin', [len(evidence('EXPECTED.json')), sha(evidence('EXPECTED.json'))], [prep['expected']['bytes'], prep['expected']['sha256']])
    check('expected six identities', sorted(expected), sorted(specimens))
    # Parse syntax and literal constants only. Do not exec, compile or import targets.
    observer_tree = ast.parse(evidence('stage/specimens/observe-proposed.py'))
    constants = {node.targets[0].id: ast.literal_eval(node.value) for node in observer_tree.body if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ('PINNED', 'SPECIMENS')}
    check('observer exact specimen order', list(constants['SPECIMENS']), list(specimens))
    check('observer pinned sources', constants['PINNED'], {name: prep['stage']['packet/' + name]['sha256'] for name in packet_names})
    ledger_tree = ast.parse(evidence('stage/packet/ledger.py'))
    summary_function = next(n for n in ledger_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'summarize')
    source_keys = [ast.literal_eval(key) for n in summary_function.body if isinstance(n, ast.Return) for key in n.value.keys]
    diagnostics = set(source_keys) - {'populations', 'mismatching_cases'}
    review = obj('stage/specimens/review.json')
    check('review exact four fields', sorted(review), sorted(['cases', 'admissibility_reasoning', 'static_review', 'limits']))
    check('review nonempty cases', isinstance(review['cases'], list) and bool(review['cases']))
    check('review case IDs unique', len({c['id'] for c in review['cases']}), len(review['cases']))
    for case in review['cases']:
        prefix = 'review ' + case['id'] + ': '
        check(prefix + 'six exact fields', sorted(case), sorted(['id', 'population', 'role', 'expected_admission', 'prediction', 'measurements']))
        check(prefix + 'nonempty identity', isinstance(case['id'], str) and bool(case['id']))
        check(prefix + 'population', case['population'] in ('ordinary', 'control'))
        check(prefix + 'boolean admission', type(case['expected_admission']) is bool)
        check(prefix + 'text reasoning', all(isinstance(case[x], str) and bool(case[x].strip()) for x in ('role', 'prediction')))
        measurements = case['measurements']
        check(prefix + 'unique nonempty measurement strings', isinstance(measurements, list) and all(isinstance(m, str) and bool(m.strip()) for m in measurements) and len(measurements) == len(set(measurements)))
        check(prefix + 'measurement/admission consistency', bool(measurements), case['expected_admission'])
    check('review admissibility reasoning exists', isinstance(review['admissibility_reasoning'], str) and bool(review['admissibility_reasoning'].strip()))
    for key in ('static_review', 'limits'):
        check('review text array: ' + key, isinstance(review[key], list) and all(isinstance(v, str) and bool(v.strip()) for v in review[key]))
    check('review static reasoning exists', bool(review['static_review']))
    raw = {name: evidence('stage/specimens/' + name) for name in specimens}
    a = raw[specimens[0]]
    check('B exact label-to-seal bytes only', raw[specimens[1]] == a.replace(b'"measurement":"label"', b'"measurement":"seal"', 1))
    check('C exact note bytes only', raw[specimens[2]] == a.replace(b'"measurement":"label","expected":{"route":"north","batch":7},"actual":{"route":"north","batch":7},"mismatch":false,"note":"authored specimen"', b'"measurement":"label","expected":{"route":"north","batch":7},"actual":{"route":"north","batch":7},"mismatch":false,"note":"annotation changed; operands and membership are unchanged"', 1))
    check('D exact true-to-false operand only', raw[specimens[3]] == a.replace(b'"actual":true', b'"actual":false', 1))
    lines = a.splitlines(keepends=True)
    check('E exact reach/admit swap only', raw[specimens[4]] == b''.join([lines[0], lines[2], lines[1], *lines[3:]]))
    check('F exact malformed line append only', raw[specimens[5]] == a + b'not a JSON row\n')
    rows = {}
    for name in specimens:
        data_lines = raw[name].splitlines()
        rows[name] = [decode(line) for line in data_lines[:10]]
        check('specimen physical lines: ' + name, len(data_lines), 11 if name == specimens[5] else 10)
        check('specimen valid parsed JSON rows: ' + name, len(rows[name]), 10)
        check('specimen raw compare count: ' + name, sum(r['kind'] == 'compare' for r in rows[name]), 4)
        for case, row in zip(review['cases'], (rows[name][0], rows[name][6])):
            check('declaration matches review: ' + name + ':' + case['id'], {k: v for k, v in row.items() if k not in ('kind', 'case')}, {k: v for k, v in case.items() if k != 'id'})
    check('A ordinary operands agree', all(r['expected'] == r['actual'] and r['mismatch'] is False for r in rows[specimens[0]][3:6]))
    check('A control operands disagree', [rows[specimens[0]][9]['expected'], rows[specimens[0]][9]['actual'], rows[specimens[0]][9]['mismatch']], [False, True, True])
    check('D equal operands retain inconsistent flag', [rows[specimens[3]][9]['expected'], rows[specimens[3]][9]['actual'], rows[specimens[3]][9]['mismatch']], [False, False, True])
    predictions = evidence('stage/specimens/PREDICTIONS.md').decode()
    blocks = [decode(v) for v in re.findall(r'```json\n(.*?)\n```', predictions, re.S)]
    check('prediction JSON block count', len(blocks), 5)
    table = [line for line in predictions.splitlines() if re.match(r'\| [A-F]-', line)]
    check('prediction table row count', len(table), 6)
    for index, name in enumerate(specimens):
        exp = expected[name]
        fields = [p.strip() for p in table[index].split('|')[1:-1]]
        check('prediction table identity: ' + name, fields[0], name[:-6])
        check('prediction parsed rows: ' + name, exp['parsed_rows'], int(fields[1]))
        check('prediction raw compare rows: ' + name, exp['raw_valid_compare_rows'], 4)
        check('complete summary schema: ' + name, sorted(exp['summary']), sorted(source_keys))
        for population, col in [('ordinary', 3), ('control', 4)]:
            compared, mismatches = map(int, fields[col].split(' / '))
            population_expected = {'declared': 1, 'reached': 1, 'admitted': 0 if (index == 4 and population == 'ordinary') else 1, 'refused': 0, 'compared': compared, 'mismatches': mismatches}
            check('complete population prediction: ' + name + ':' + population, exp['summary']['populations'][population], population_expected)
        check('complete mismatching case prediction: ' + name, exp['summary']['mismatching_cases'], {'ordinary': [], 'control': [] if index == 3 else ['switch-control']})
        nonempty = {} if index in (0, 2, 5) else blocks[0] if index == 1 else {'inconsistent_comparisons': ['switch-control']} if index == 3 else blocks[3]
        check('all diagnostic predictions: ' + name, {key: exp['summary'][key] for key in diagnostics}, {key: nonempty.get(key, []) for key in diagnostics})
        prereq = [] if index in (0, 2, 5) else blocks[1] if index == 1 else blocks[2] if index == 3 else blocks[4]
        check('exact ordered prerequisite prediction: ' + name, exp['prerequisites'], prereq)
        check('parse problem transcription: ' + name, exp['parse_problem'], {'count': 1, 'line': 11, 'prefix': 'invalid JSON row:'} if index == 5 else None)
    comparator_pin_raw = (ROOT / 'COMPARATOR-PIN.json').read_bytes()
    comparator = (ROOT / 'comparator-before-run.py').read_bytes()
    write('COMPARATOR-PIN.json', comparator_pin_raw)
    write('comparator-before-run.py', comparator)
    comparator_pin = decode(comparator_pin_raw)
    check('supplemental comparator pin', [len(comparator), sha(comparator)], [comparator_pin['bytes'], comparator_pin['sha256']])
    check('supplemental comparator current bytes', (REPO / comparator_pin['path']).read_bytes() == comparator)
    check('supplemental comparator frozen before launch claim', comparator_pin['observer_launched'], False)
    for name in ('RUN-RESERVATION.json', 'PID.json', 'observer.stdout', 'observer.stderr'):
        check('no launch evidence at preflight: ' + name, (ROOT / name).exists(), False)


if __name__ == '__main__':
    failure = None
    try:
        main()
    except BaseException:
        failure = traceback.format_exc()
    result = {'at': datetime.now(timezone.utc).isoformat(), 'checks': CHECKS,
              'passed': sum(c['passed'] for c in CHECKS), 'total': len(CHECKS),
              'exception': failure, 'commands': COMMANDS,
              'observer_invocations': 0, 'pytest_nodes': 0,
              'review_code_sha256': sha(Path(__file__).read_bytes())}
    receipt('STATIC-CHECKS-01.json', result)
    print(f"Static preflight checks: {result['passed']}/{result['total']}; exception: {bool(failure)}")
    if failure:
        print(failure, file=sys.stderr)
    for item in CHECKS:
        if not item['passed']:
            print(json.dumps(item, sort_keys=True), file=sys.stderr)
    sys.exit(1 if failure or result['passed'] != result['total'] else 0)
