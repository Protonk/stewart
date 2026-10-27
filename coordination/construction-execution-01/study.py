"""Development-only preparation and single launch; never a product executor.

Use an explicit Python with -I -B -S. `prepare` creates a fresh evidence root;
`run` requires its exact reviewed PREPARATION and an exclusive reservation.
Failures are retained. Neither command retries the observer or imports it here.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import traceback

REPO = Path(__file__).resolve().parents[2]
DOC = Path(__file__).resolve().parent
ROOT = REPO / '.scratch/construction-execution-01'
HEAD = '9ffad1fd5a628d90d17da75000a5b3a385031d8c'
SOURCE = '81b557a78db156e7bfc5e8d35ece9d1438608d87'
ENV = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'TZ': 'UTC'}
SPECIMENS = ('A-complete.jsonl', 'B-duplicate.jsonl', 'C-note-invariant.jsonl',
             'D-control-extinguished.jsonl', 'E-admission-before-reach.jsonl',
             'F-parse-problem.jsonl')
SUPPORT = ('review.json', *SPECIMENS, 'PREDICTIONS.md', 'CONSTRUCTION.md',
           'observe-proposed.py')
SOURCE_FILES = ('ledger.py', '_json.py', 'test_stewart_ledger.py')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('Repeated control key: ' + key)
        out[key] = value
    return out


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique)


def write_bytes(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def write_receipt(path, value):
    write_bytes(path, (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode())


def identity(path):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Expected a regular nonlink file: ' + str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read()
        after = os.fstat(stream.fileno())
    keys = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_mtime_ns', 'st_ctime_ns')
    if any(getattr(before, key) != getattr(opened, key) or
           getattr(opened, key) != getattr(after, key) for key in keys):
        raise ValueError('File changed during identity observation: ' + str(path))
    return {'bytes': len(raw), 'sha256': digest(raw),
            'device': after.st_dev, 'inode': after.st_ino,
            'mode': stat.S_IMODE(after.st_mode), 'mtime_ns': after.st_mtime_ns,
            'ctime_ns': after.st_ctime_ns}


def inventory(root):
    result = {}
    for path in [root, *sorted(root.rglob('*'))]:
        s = path.lstat()
        name = str(path.relative_to(root))
        if path.is_symlink() or '__pycache__' in path.parts or path.suffix == '.pyc':
            raise ValueError('Link/cache in protected inventory: ' + str(path))
        if stat.S_ISDIR(s.st_mode):
            result[name + '/'] = {'device': s.st_dev, 'inode': s.st_ino,
                                  'mode': stat.S_IMODE(s.st_mode), 'kind': 'directory'}
        elif stat.S_ISREG(s.st_mode):
            result[name] = {'kind': 'file', **identity(path)}
        else:
            raise ValueError('Special entry in protected inventory: ' + str(path))
    return result


def expected_observations():
    # Manual transcription of the already-frozen PREDICTIONS.md, not execution.
    diagnostics = ('unexpected_admission compared_without_admission undeclared '
                   'inconsistent_comparisons sequence_problems malformed_rows declaration_conflicts '
                   'unreviewed_cases missing_declarations unreached unresolved_admission uncompared '
                   'missing_measurements duplicate_measurements unexpected_measurements').split()
    baseline = {name: [] for name in diagnostics}
    baseline['populations'] = {
        'ordinary': dict(declared=1, reached=1, admitted=1, refused=0, compared=3, mismatches=0),
        'control': dict(declared=1, reached=1, admitted=1, refused=0, compared=1, mismatches=1)}
    baseline['mismatching_cases'] = {'ordinary': [], 'control': ['switch-control']}
    result = {name: {'parsed_rows': 10, 'raw_valid_compare_rows': 4,
                     'summary': copy.deepcopy(baseline), 'prerequisites': [],
                     'parse_problem': None} for name in SPECIMENS}
    b = result[SPECIMENS[1]]
    b['summary']['populations']['ordinary']['compared'] = 1
    b['summary']['missing_measurements'] = [{'case': 'parcel-check', 'measurement': 'label'}]
    b['summary']['duplicate_measurements'] = [{'case': 'parcel-check', 'measurement': 'seal'}]
    b['prerequisites'] = ['missing measurements: parcel-check:label',
                          'duplicate measurements: parcel-check:seal']
    d = result[SPECIMENS[3]]
    d['summary']['populations']['control']['mismatches'] = 0
    d['summary']['mismatching_cases']['control'] = []
    d['summary']['inconsistent_comparisons'] = ['switch-control']
    d['prerequisites'] = [
        'no control produced a nonzero disagreement; the instrument was not observed to fire',
        'mismatch flags contradict recorded operands for: switch-control']
    e = result[SPECIMENS[4]]
    e['summary']['populations']['ordinary'].update(admitted=0, compared=0)
    e['summary']['compared_without_admission'] = ['parcel-check']
    e['summary']['unresolved_admission'] = ['parcel-check']
    e['summary']['sequence_problems'] = ['parcel-check: admission requires prior reach and cannot repeat']
    e['prerequisites'] = [
        'no ordinary comparison was recorded',
        'comparisons recorded while cases were not admitted: parcel-check',
        'cases without an admission outcome: parcel-check',
        'parcel-check: admission requires prior reach and cannot repeat']
    result[SPECIMENS[5]]['parse_problem'] = {'count': 1, 'line': 11,
                                           'prefix': 'invalid JSON row:'}
    return result


def prepare():
    ROOT.mkdir()  # Never reuse an earlier preparation or evidence population.
    checks, commands = [], []

    def check(label, ok):
        checks.append({'check': label, 'passed': bool(ok)})
        if not ok:
            raise ValueError(label)

    def witness(label, raw):
        write_bytes(ROOT / 'witness' / label, raw)
        return raw

    def git_bytes(revision, path):
        argv = ['/usr/bin/git', 'show', revision + ':' + path]
        proc = subprocess.run(argv, cwd=REPO, stdin=subprocess.DEVNULL, capture_output=True)
        commands.append({'argv': argv, 'cwd': str(REPO), 'exit': proc.returncode,
                         'stderr': proc.stderr.decode(errors='replace'),
                         'stdout_bytes': len(proc.stdout), 'stdout_sha256': digest(proc.stdout)})
        check('git show ' + path, proc.returncode == 0)
        return proc.stdout

    try:
        prior = REPO / '.scratch/fresh-authoring-01/pilot-01'
        completion = decode(witness('prior/COMPLETION.json', (prior / 'COMPLETION.json').read_bytes()))
        pins = {x['path']: x for x in completion['evidence_before_this_record']}
        historical = {}
        for name in ('attempt.raw', 'SNAPSHOT.json', 'ACCEPTED.json'):
            path = prior / 'final-submission-01' / name
            raw = witness('prior/' + name, path.read_bytes())
            pin = pins[str(path.relative_to(REPO))]
            check('earlier retained identity: ' + name,
                  len(raw) == pin['bytes'] and digest(raw) == pin['sha256'])
            historical[name] = raw
        envelope_path = 'coordination/fresh-authoring-01/author/attempt-01/FINAL-ENVELOPE.json'
        raw = witness('FINAL-ENVELOPE.json', git_bytes(HEAD, envelope_path))
        check('committed/raw envelope equality', raw == historical['attempt.raw'])
        envelope = decode(raw)
        check('snapshot/envelope equality', decode(historical['SNAPSHOT.json'])['envelope'] == envelope)
        accepted = decode(historical['ACCEPTED.json'])
        check('acceptance raw binding', accepted['raw_transport'] == {'bytes': len(raw), 'sha256': digest(raw)})
        check('selection identity', envelope['question_id'] == 'ledger-membership-construction-01'
              and envelope['source_revision'] == SOURCE and len(envelope['support']) == 18)
        objects = {entry['id']: entry for entry in envelope['support']}
        check('support identities unique', len(objects) == len(envelope['support']))
        packet = REPO / '.scratch/fresh-authoring-01/subject-01'
        subject = decode(witness('packet/SUBJECT.json', (packet / 'SUBJECT.json').read_bytes()))
        check('subject revision', subject['source_revision'] == SOURCE)
        names = {'SUBJECT.json', 'QUESTION.md'} | {x['packet_file'] for x in subject['subject_files']}
        check('finite source inventory', {p.name for p in packet.iterdir()} == names and len(names) == 8)
        question = witness('packet/QUESTION.md', (packet / 'QUESTION.md').read_bytes())
        check('question identity', digest(question) == subject['question_sha256']
              and len(question) == subject['question_bytes'])
        for entry in subject['subject_files']:
            data = witness('packet/' + entry['packet_file'], (packet / entry['packet_file']).read_bytes())
            check('packet identity: ' + entry['packet_file'], digest(data) == entry['packet_sha256']
                  and len(data) == entry['packet_bytes'])
            source = witness('git-source/' + entry['source_path'], git_bytes(SOURCE, entry['source_path']))
            check('Git source identity: ' + entry['source_path'], digest(source) == entry['source_sha256']
                  and len(source) == entry['source_bytes'])
            if entry['selected_ranges'] is None:
                check('full source equality: ' + entry['packet_file'], data == source)
        staged = {}
        for name in SOURCE_FILES:
            staged['packet/' + name] = (ROOT / 'witness/packet' / name).read_bytes()
        for name in SUPPORT:
            check('selected UTF-8 support: ' + name, objects[name]['encoding'] == 'utf-8')
            staged['specimens/' + name] = objects[name]['text'].encode('utf-8')
        for name, data in staged.items():
            write_bytes(ROOT / 'stage' / name, data)
            write_bytes(ROOT / 'witness/stage' / name, data)
        write_receipt(ROOT / 'EXPECTED.json', expected_observations())
        for folder in (ROOT / 'stage', ROOT / 'witness'):
            for p in sorted(folder.rglob('*'), reverse=True):
                p.chmod(0o555 if p.is_dir() else 0o444)
            folder.chmod(0o555)
        frozen = inventory(ROOT / 'stage')
        check('exact protected inventory', set(frozen) == set(staged) | {'./', 'packet/', 'specimens/'})
        for name, data in staged.items():
            check('staged identity/mode: ' + name,
                  frozen[name]['bytes'] == len(data) and frozen[name]['sha256'] == digest(data)
                  and frozen[name]['mode'] == 0o444)
        interpreter = Path('/opt/homebrew/bin/python3.14').resolve(strict=True)
        binary = identity(interpreter)
        probe_source = """import sys, platform, json
print(json.dumps({'version': sys.version, 'version_info': list(sys.version_info),
'implementation': sys.implementation.name, 'executable': sys.executable,
'base_executable': sys._base_executable, 'prefix': sys.prefix, 'base_prefix': sys.base_prefix,
'platform': platform.platform(), 'machine': platform.machine(), 'sys_path': sys.path,
'isolated': sys.flags.isolated, 'no_site': sys.flags.no_site,
'dont_write_bytecode': sys.dont_write_bytecode, 'site_loaded': 'site' in sys.modules,
'pycache_prefix': sys.pycache_prefix}, sort_keys=True))
"""
        probe_argv = [str(interpreter), '-I', '-B', '-S', '-c', probe_source]
        write_receipt(ROOT / 'PROBE-PLAN.json', {'at': now(), 'argv': probe_argv,
                      'cwd': str(ROOT), 'env': ENV, 'interpreter': binary})
        with (ROOT / 'probe.stdout').open('xb') as out, (ROOT / 'probe.stderr').open('xb') as err:
            proc = subprocess.run(probe_argv, cwd=ROOT, env=ENV, stdin=subprocess.DEVNULL,
                                  stdout=out, stderr=err, timeout=30)
        write_receipt(ROOT / 'PROBE-EXIT.json', {'at': now(), 'exit': proc.returncode})
        check('interpreter probe exit', proc.returncode == 0)
        probe = decode((ROOT / 'probe.stdout').read_bytes())
        check('Python 3.14 isolated qualification', probe['version_info'][:2] == [3, 14]
              and probe['isolated'] == 1 and probe['no_site'] == 1
              and probe['dont_write_bytecode'] and not probe['site_loaded']
              and probe['pycache_prefix'] is None and (ROOT / 'probe.stderr').read_bytes() == b'')
        check('interpreter identity stable through probe', identity(interpreter) == binary)
        argv = [str(interpreter), '-I', '-B', '-S', str(ROOT / 'stage/specimens/observe-proposed.py'),
                '--packet', str(ROOT / 'stage/packet'), '--specimens', str(ROOT / 'stage/specimens')]
        write_receipt(ROOT / 'PREPARATION.json', {
            'at': now(), 'source_head': HEAD, 'source_revision': SOURCE,
            'argv': argv, 'cwd': str(ROOT / 'stage'), 'env': ENV,
            'stdin': 'DEVNULL', 'timeout_seconds': 30, 'start_new_session': True,
            'interpreter': binary, 'probe': probe, 'stage': frozen,
            'witness': inventory(ROOT / 'witness'), 'expected': identity(ROOT / 'EXPECTED.json'),
            'driver': identity(Path(__file__).resolve()),
            'continuous_preservation_established': False,
            'scope': 'Cooperative one-owner staging, parent endpoint checks and attributed child hashes; no hostile enforcement.'})
    except BaseException:
        write_receipt(ROOT / 'PREPARATION-FAILURE.json', {'at': now(), 'traceback': traceback.format_exc()})
        raise
    finally:
        write_receipt(ROOT / 'PREPARATION-CHECKS.json', {'at': now(), 'checks': checks,
                      'passed': sum(x['passed'] for x in checks), 'total': len(checks), 'commands': commands})
    print('Prepared; observer not launched. Checks:', len(checks))


def run_once():
    prep_raw = (ROOT / 'PREPARATION.json').read_bytes()
    prep = decode(prep_raw)
    approval = decode((ROOT / 'PREFLIGHT-DISPOSITION.json').read_bytes())
    if approval['ready_for_single_launch'] is not True or approval['preparation_sha256'] != digest(prep_raw):
        raise ValueError('Preflight disposition does not bind this preparation')
    write_receipt(ROOT / 'RUN-RESERVATION.json', {'at': now(), 'preparation_sha256': digest(prep_raw),
                  'driver': identity(Path(__file__).resolve()), 'rule': 'No second launch, including after failure.'})
    process = None
    try:
        if identity(Path(__file__).resolve()) != approval['reviewed_driver']:
            raise ValueError('Driver changed after independent preflight review')
        if identity(ROOT / 'EXPECTED.json') != prep['expected']:
            raise ValueError('Expected observations changed after preparation')
        if identity(Path(prep['argv'][0])) != prep['interpreter']:
            raise ValueError('Interpreter changed after qualification')
        stage, witness = inventory(ROOT / 'stage'), inventory(ROOT / 'witness')
        write_receipt(ROOT / 'PRELAUNCH.json', {'at': now(), 'stage': stage, 'witness': witness})
        if stage != prep['stage'] or witness != prep['witness']:
            raise ValueError('Protected inventory changed before launch')
        for name, entry in stage.items():
            if entry['kind'] == 'file':
                if entry['sha256'] != witness['stage/' + name]['sha256']:
                    raise ValueError('Stage/witness mismatch: ' + name)
        write_receipt(ROOT / 'RUN-PLAN.json', {'at': now(), 'argv': prep['argv'], 'cwd': prep['cwd'],
                      'env': prep['env'], 'stdin': prep['stdin'], 'timeout_seconds': prep['timeout_seconds'],
                      'start_new_session': True, 'stdout': 'observer.stdout', 'stderr': 'observer.stderr'})
        with (ROOT / 'observer.stdout').open('xb') as out, (ROOT / 'observer.stderr').open('xb') as err:
            process = subprocess.Popen(prep['argv'], cwd=prep['cwd'], env=prep['env'],
                                       stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       start_new_session=True)
            write_receipt(ROOT / 'PID.json', {'at': now(), 'pid': process.pid})
            try:
                code = process.wait(timeout=prep['timeout_seconds'])
            except subprocess.TimeoutExpired:
                write_receipt(ROOT / 'TIMEOUT.json', {'at': now(), 'pid': process.pid,
                              'next_action': 'SIGTERM process group, then SIGKILL after 5 seconds if still running'})
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    code = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    write_receipt(ROOT / 'KILL.json', {'at': now(), 'pid': process.pid})
                    os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait(timeout=5)
            out.flush()
            err.flush()
            os.fsync(out.fileno())
            os.fsync(err.fileno())
        write_receipt(ROOT / 'EXIT.json', {'at': now(), 'pid': process.pid, 'exit': code,
                      'stdout': identity(ROOT / 'observer.stdout'), 'stderr': identity(ROOT / 'observer.stderr')})
    except BaseException:
        failure = traceback.format_exc()
        if process is not None and process.poll() is None:
            # A caught parent capture failure must not skip the child's stop.
            # If even the intervention record cannot be saved, still attempt
            # bounded shutdown; the parent's captured traceback retains that
            # recording failure. Abrupt parent/host death is not qualified.
            try:
                write_receipt(ROOT / 'PARENT-FAILURE-INTERVENTION.json', {
                    'at': now(), 'pid': process.pid, 'traceback': failure,
                    'next_action': 'SIGTERM process group; SIGKILL after 5 seconds if still live'})
            finally:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        write_receipt(ROOT / 'PARENT-FAILURE-KILL.json', {'at': now(), 'pid': process.pid})
                    finally:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait(timeout=5)
        write_receipt(ROOT / 'RUN-FAILURE.json', {'at': now(), 'pid': process.pid if process else None,
                      'traceback': failure, 'observed_exit': process.poll() if process else None,
                      'next_step': 'Reconcile retained effects; do not relaunch observer.'})
        raise
    finally:
        if process is not None and process.poll() is None:
            write_receipt(ROOT / 'POSTRUN.json', {'at': now(), 'pid': process.pid,
                          'termination_observed': False,
                          'inventory_not_attempted': 'Child termination is unresolved',
                          'continuous_preservation_established': False})
        else:
            stage, witness = inventory(ROOT / 'stage'), inventory(ROOT / 'witness')
            write_receipt(ROOT / 'POSTRUN.json', {'at': now(), 'stage': stage, 'witness': witness,
                          'termination_observed': process is not None,
                          'stage_matches_preparation': stage == prep['stage'],
                          'witness_matches_preparation': witness == prep['witness'],
                          'interpreter_matches_preparation': identity(Path(prep['argv'][0])) == prep['interpreter'],
                          'continuous_preservation_established': False})
    print('One observer invocation ended. Exit:', code, 'Captured output awaits comparison.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    args = parser.parse_args()
    {'prepare': prepare, 'run': run_once}[args.action]()
