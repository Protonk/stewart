"""Coordinator study capture and packet assembly; never executes subject code."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
DOC = Path(__file__).resolve().parent
ROOT = REPO / '.scratch/answer-revision-01'
REV = '5f00082d86768368478ed7cc85b52dd56a60255b'
QUESTION = 'declaration-status-preservation-01'
FORMS = {'a01': 'common', 'a02': 'minimal', 'a03': 'common', 'a04': 'minimal'}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path):
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode):
        raise ValueError('Not a regular file: ' + str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if (s.st_dev, s.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError('File identity changed: ' + str(path))
        return stream.read()


def put(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def write_receipt(path, value):
    put(path, (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode())


def unique(pairs):
    out = {}
    for name, value in pairs:
        if name in out:
            raise ValueError('Repeated control key: ' + name)
        out[name] = value
    return out


def load(path):
    return json.loads(regular(path), object_pairs_hook=unique)


def freeze_tree(source, destination):
    rows = []
    if not source.exists():
        return rows
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('No link traversal in author/reader freeze: ' + str(path))
        if path.is_dir():
            continue
        raw = regular(path)
        target = destination / path.relative_to(source)
        put(target, raw)
        rows.append({'source': str(path.relative_to(REPO)), 'snapshot': str(target.relative_to(REPO)),
                     'bytes': len(raw), 'sha256': sha(raw)})
    return rows


def verify_assembly():
    for row in load(ROOT / 'ASSEMBLY.json')['files']:
        raw = regular(REPO / row['path'])
        if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            raise ValueError('Issued source/release changed: ' + row['path'])


def capture(author, phase):
    approval = load(ROOT / 'PREFLIGHT-DISPOSITION.json')
    helper = DOC / 'transport/attempt-01/capture.py'
    if not approval['ready'] or sha(regular(helper)) != approval['helper_sha256']:
        raise ValueError('Exact helper lacks reviewed preflight disposition')
    verify_assembly()
    source = DOC / 'authors' / author / 'attempt-01'
    for required in ('SELECTED-' + phase + '.json', 'READS-' + phase + '.json', 'PROCESS-' + phase + '.md'):
        regular(source / required)
    destination = ROOT / 'captures' / author / ('phase-' + phase)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()  # Nonreusable even after an uncertain effect.
    selected = source / ('SELECTED-' + phase + '.json')
    write_receipt(destination / 'PLAN.json', {'at': now(), 'author': author, 'phase': phase,
                  'form': FORMS[author], 'source': str(selected.relative_to(REPO)),
                  'planned': ['input.raw', 'freeze.json', 'COMMAND.json', 'PID.json', 'stdout', 'stderr',
                              'EXIT.json', 'helper/', 'CAPTURE-CHECKS.json'],
                  'helper_sha256': approval['helper_sha256']})
    # Independent witness precedes helper stdin or validation.
    raw = regular(selected)
    put(destination / 'input.raw', raw)
    rows = freeze_tree(source, destination / 'author-files')
    rows += freeze_tree(ROOT / 'authors' / author / 'attempt-01', destination / 'author-scratch')
    write_receipt(destination / 'freeze.json', {'at': now(), 'files': rows})
    argv = ['/usr/bin/python3', '-I', '-B', '-S', str(helper), '--destination', str(destination / 'helper'),
            '--form', FORMS[author], '--question-id', QUESTION, '--source-revision', REV,
            '--author-id', author, '--phase', phase]
    write_receipt(destination / 'COMMAND.json', {'at': now(), 'argv': argv, 'cwd': str(REPO),
                  'stdin': 'input.raw', 'stdout': 'stdout', 'stderr': 'stderr', 'timeout_seconds': 30})
    with (destination / 'input.raw').open('rb') as inp, (destination / 'stdout').open('xb') as out, (destination / 'stderr').open('xb') as err:
        child = subprocess.Popen(argv, cwd=REPO, stdin=inp, stdout=out, stderr=err, start_new_session=True)
        write_receipt(destination / 'PID.json', {'at': now(), 'pid': child.pid})
        try:
            code = child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            write_receipt(destination / 'TIMEOUT.json', {'at': now(), 'pid': child.pid, 'next_action': 'terminate process group'})
            os.killpg(child.pid, signal.SIGTERM)
            try:
                code = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                write_receipt(destination / 'KILL.json', {'at': now(), 'pid': child.pid})
                os.killpg(child.pid, signal.SIGKILL)
                code = child.wait(timeout=5)
    write_receipt(destination / 'EXIT.json', {'at': now(), 'pid': child.pid, 'exit': code})
    checks = []

    def check(label, ok):
        checks.append({'check': label, 'passed': bool(ok)})

    check('raw witness unchanged', regular(destination / 'input.raw') == raw)
    check('helper captured exact raw witness', regular(destination / 'helper/attempt.raw') == raw)
    check('helper bytes unchanged', sha(regular(helper)) == approval['helper_sha256'])
    check('helper stderr empty', regular(destination / 'stderr') == b'')
    output = load(destination / 'stdout')
    if code == 0:
        snapshot = load(destination / 'helper/SNAPSHOT.json')
        accepted = load(destination / 'helper/ACCEPTED.json')
        payload = json.loads(raw, object_pairs_hook=unique)
        check('snapshot payload equality', snapshot['envelope'] == payload)
        check('accepted raw identity', accepted['raw_transport'] == {'bytes': len(raw), 'sha256': sha(raw)})
        check('stdout/acceptance equality', output == accepted)
        check('explicit capture identity', snapshot['capture_metadata'] == {
            'form': FORMS[author], 'expected_identity': {'question_id': QUESTION, 'source_revision': REV},
            'issued_provenance': {'author_id': author, 'phase': phase},
            'provenance_source': 'explicit coordinator CLI arguments; not inferred from submitted text'})
        common = FORMS[author] == 'common'
        text = payload['answer' if common else 'text'].encode()
        check('primary exact identity', snapshot['byte_observations']['decoded_primary_text_utf8'] == {'bytes': len(text), 'sha256': sha(text)})
        artifacts = payload['support' if common else 'artifacts']
        expected = []
        for index, item in enumerate(artifacts):
            data = item['text'].encode()
            key = 'id' if common else 'name'
            expected.append({'position': index, key: item[key], 'bytes': len(data), 'sha256': sha(data)})
        check('ordered exact artifact identities', snapshot['byte_observations']['decoded_artifact_text_utf8_in_submission_order'] == expected)
    write_receipt(destination / 'CAPTURE-CHECKS.json', {'at': now(), 'checks': checks,
                  'passed': sum(row['passed'] for row in checks), 'total': len(checks),
                  'helper_exit': code, 'structural_status': output.get('status'), 'subject_executions': 0})
    print(author, phase, 'capture exit', code, 'checks', sum(row['passed'] for row in checks), '/', len(checks), 'raw bytes', len(raw))
    return code if all(row['passed'] for row in checks) else 1


def author_barrier(phase):
    verify_assembly()
    records = []
    for author in FORMS:
        folder = ROOT / 'captures' / author / ('phase-' + phase)
        record = load(folder / 'CAPTURE-CHECKS.json')
        if record['helper_exit'] != 0 or record['passed'] != record['total']:
            raise ValueError('Unresolved capture at barrier: ' + author)
        for required in ('SELECTED-' + phase + '.json', 'READS-' + phase + '.json', 'PROCESS-' + phase + '.md'):
            regular(folder / 'author-files' / required)
        if regular(folder / 'author-files' / ('SELECTED-' + phase + '.json')) != regular(folder / 'input.raw'):
            raise ValueError('Frozen author selection differs from submitted witness: ' + author)
        files = []
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                raw = regular(path)
                files.append({'path': str(path.relative_to(REPO)), 'bytes': len(raw), 'sha256': sha(raw)})
        records.append({'author': author, 'phase': phase, 'files': files})
    write_receipt(ROOT / ('AUTHOR-PHASE-' + phase + '-FROZEN.json'), {'at': now(), 'captures': records, 'release_allowed': phase == '01'})
    print('All four author selections captured/frozen for phase', phase)


def packets(phase):
    barrier = load(ROOT / ('AUTHOR-PHASE-' + phase + '-FROZEN.json'))
    for capture in barrier['captures']:
        for entry in capture['files']:
            raw = regular(REPO / entry['path'])
            if len(raw) != entry['bytes'] or sha(raw) != entry['sha256']:
                raise ValueError('Frozen capture changed before recipient assembly: ' + entry['path'])
    verify_assembly()
    populations = []
    for author, form in FORMS.items():
        reader = 'r' + author[1:]
        packet = ROOT / 'recipient-packets' / reader / ('phase-' + phase)
        packet.mkdir(parents=True, exist_ok=False)
        capture_root = ROOT / 'captures' / author / ('phase-' + phase)
        snapshot = load(capture_root / 'helper/SNAPSHOT.json')
        payload = snapshot['envelope']
        subject = ROOT / 'grants' / author / 'phase-01' if phase == '01' else ROOT / 'subject'
        for path in sorted(subject.iterdir()):
            if path.is_file():
                put(packet / 'subject' / path.name, regular(path))
        if phase == '02':
            put(packet / 'subject/AVAILABILITY.md', b'# Phase-two source\n\nThe complete selected route, including the exact consumer source, is now supplied. This may add source or repeat source already supplied; it is not new execution evidence.\n')
        put(packet / 'RETURN.raw', regular(capture_root / 'input.raw'))
        common = form == 'common'
        primary = payload['answer' if common else 'text'].encode()
        put(packet / 'primary.txt', primary)
        objects = []
        for index, item in enumerate(payload['support' if common else 'artifacts'], 1):
            filename = f'artifact-{index:02d}.txt'
            raw = item['text'].encode()
            put(packet / filename, raw)
            entry = {'file': filename, 'bytes': len(raw), 'sha256': sha(raw),
                     'submitted_name': item['id' if common else 'name']}
            if common:
                entry['submitted_role'] = item['role']
            objects.append(entry)
        write_receipt(packet / 'RETURN-MANIFEST.json', {
            'issued': {'author': author, 'phase': phase, 'form': form, 'question_id': QUESTION, 'source_revision': REV},
            'raw': {'file': 'RETURN.raw', 'bytes': len(regular(packet / 'RETURN.raw')), 'sha256': sha(regular(packet / 'RETURN.raw'))},
            'primary': {'file': 'primary.txt', 'bytes': len(primary), 'sha256': sha(primary)},
            **({'submitted_metadata': {key: payload[key] for key in (
                'question_id', 'source_revision', 'author', 'response_kind', 'completion_claim')}} if common else {}),
            'artifacts': objects, 'note': 'Exact selected content only; no author process records or scratch. Structural admission is not intellectual assessment. Common author claims remain in RETURN.raw; no kind/completion/roles are invented for minimal.'})
        entries = []
        for path in sorted(packet.rglob('*')):
            if path.is_file():
                raw = regular(path)
                entries.append({'file': str(path.relative_to(packet)), 'bytes': len(raw), 'sha256': sha(raw)})
        write_receipt(packet / 'PACKET.json', {'at': now(), 'files': entries, 'source_capture': str(capture_root.relative_to(REPO))})
        populations.append({'reader': reader, 'author': author, 'packet': str(packet.relative_to(REPO)), 'files': entries})
    write_receipt(ROOT / ('RECIPIENT-PACKETS-' + phase + '.json'), {'at': now(), 'packets': populations})
    print('Four exact recipient packets created for phase', phase)


def freeze_readers(phase):
    rows = []
    for author in FORMS:
        reader = 'r' + author[1:]
        source = DOC / 'recipients' / reader / 'attempt-01'
        required = ('FIRST.md', 'READS-FIRST.json') if phase == '01' else ('SECOND.md', 'READS-SECOND.json')
        for name in required:
            regular(source / name)
        destination = ROOT / 'reader-freezes' / reader / ('phase-' + phase)
        rows += freeze_tree(source, destination)
    write_receipt(ROOT / ('READER-PHASE-' + phase + '-FROZEN.json'), {'at': now(), 'files': rows})
    print('Four recipient response phases frozen:', phase)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('capture', 'author-barrier', 'packets', 'freeze-readers'))
    parser.add_argument('--author', choices=tuple(FORMS))
    parser.add_argument('--phase', choices=('01', '02'), required=True)
    args = parser.parse_args()
    if args.action == 'capture':
        if not args.author:
            parser.error('capture requires --author')
        sys.exit(capture(args.author, args.phase))
    {'author-barrier': author_barrier, 'packets': packets, 'freeze-readers': freeze_readers}[args.action](args.phase)
