"""Check this study's frozen bytes and boundaries; never execute subject code.

Run with explicit Python -I -B -S and a fresh --output path. Checks describe
finite observed files, not hostile-path enforcement or participant access logs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
DOC = Path(__file__).resolve().parent
ROOT = REPO / '.scratch/answer-revision-01'
REV = '5f00082d86768368478ed7cc85b52dd56a60255b'
FORMS = {'a01': 'common', 'a02': 'minimal', 'a03': 'common', 'a04': 'minimal'}
checks, commands, observations = [], [], []


def read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected ordinary study file: ' + str(path))
    return path.read_bytes()


def load(path):
    return json.loads(read(path))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check(label, condition):
    checks.append({'check': label, 'passed': bool(condition)})


def pin(row, path):
    data = read(path)
    check(str(path.relative_to(REPO)) + ' pinned bytes',
          len(data) == row['bytes'] and sha(data) == row['sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for row in load(ROOT / 'ASSEMBLY.json')['files']:
        pin(row, REPO / row['path'])
    selection = load(ROOT / 'SOURCE-SELECTION.json')
    for command in selection['commands']:
        result = subprocess.run(command['argv'], cwd=REPO, capture_output=True)
        commands.append({'argv': command['argv'], 'exit': result.returncode,
                         'stdout_sha256': sha(result.stdout), 'stdout_bytes': len(result.stdout),
                         'stderr': result.stderr.decode()})
        source = command['argv'][-1].split(':', 1)[1]
        check(source + ' exact original Git source', result.returncode == 0 and
              result.stderr == b'' and result.stdout == read(ROOT / 'witness/source' / source))
    for row in selection['selections']:
        lines = read(ROOT / 'witness/source' / row['source_path']).splitlines(keepends=True)
        expected = b''
        for start, end in row['ranges']:
            expected += (f'--- {REV}:{row["source_path"]}, original lines {start}-{end} ---\n').encode()
            expected += b''.join(lines[start-1:end]) + b'\n'
        check(row['packet_file'] + ' exact selected ranges', expected == read(ROOT / 'subject' / row['packet_file']))
    for phase in ('01', '02'):
        for capture in load(ROOT / ('AUTHOR-PHASE-' + phase + '-FROZEN.json'))['captures']:
            for row in capture['files']:
                pin(row, REPO / row['path'])
        for row in load(ROOT / ('READER-PHASE-' + phase + '-FROZEN.json'))['files']:
            pin(row, REPO / row['snapshot'])
            if Path(row['source']).name in ('FIRST.md', 'SECOND.md', 'READS-FIRST.json', 'READS-SECOND.json'):
                pin(row, REPO / row['source'])
        for a, form in FORMS.items():
            r = 'r' + a[1:]
            cap = ROOT / 'captures' / a / ('phase-' + phase)
            packet = ROOT / 'recipient-packets' / r / ('phase-' + phase)
            raw = read(cap / 'input.raw')
            payload = json.loads(raw)
            common = form == 'common'
            check(a + phase + ' live selection/frozen/helper/recipient raw identity', all(raw == read(p) for p in (
                DOC / 'authors' / a / 'attempt-01' / ('SELECTED-' + phase + '.json'),
                cap / 'author-files' / ('SELECTED-' + phase + '.json'),
                cap / 'helper/attempt.raw', packet / 'RETURN.raw')))
            snapshot = load(cap / 'helper/SNAPSHOT.json')
            check(a + phase + ' admitted payload', snapshot['envelope'] == payload)
            metadata = snapshot['capture_metadata']
            check(a + phase + ' explicit phase/form identity', metadata['form'] == form and metadata['issued_provenance'] == {'author_id': a, 'phase': phase})
            command = load(cap / 'COMMAND.json')['argv']
            check(a + phase + ' isolated interpreter and explicit CLI phase', command[:4] == ['/usr/bin/python3', '-I', '-B', '-S'] and command[-1] == phase)
            capture_checks = load(cap / 'CAPTURE-CHECKS.json')
            check(a + phase + ' original capture checks/exit', capture_checks['passed'] == capture_checks['total'] == 10 and load(cap / 'EXIT.json')['exit'] == 0)
            manifest = load(packet / 'RETURN-MANIFEST.json')
            check(a + phase + ' exact primary', read(packet / 'primary.txt') == payload['answer' if common else 'text'].encode())
            artifacts = payload['support' if common else 'artifacts']
            check(a + phase + ' artifact count', len(manifest['artifacts']) == len(artifacts))
            for index, item in enumerate(artifacts, 1):
                entry = manifest['artifacts'][index-1]
                check(a + phase + ' artifact ' + str(index), read(packet / entry['file']) == item['text'].encode() and
                      entry['submitted_name'] == item['id' if common else 'name'] and
                      (entry['submitted_role'] == item['role'] if common else 'submitted_role' not in entry))
            check(a + phase + ' common metadata retained or minimal not invented',
                  manifest.get('submitted_metadata') == {k: payload[k] for k in ('question_id', 'source_revision', 'author', 'response_kind', 'completion_claim')} if common else 'submitted_metadata' not in manifest)
            inventory = load(packet / 'PACKET.json')['files']
            for row in inventory:
                pin(row, packet / row['file'])
            expected_names = {row['file'] for row in inventory} | {'PACKET.json'}
            actual_names = {str(p.relative_to(packet)) for p in packet.rglob('*') if p.is_file()}
            check(a + phase + ' packet inventory exhaustive', expected_names == actual_names)
            expected_top = {'PACKET.json', 'RETURN.raw', 'RETURN-MANIFEST.json', 'primary.txt'} | {f'artifact-{i:02}.txt' for i in range(1,len(artifacts)+1)}
            check(a + phase + ' selected content only', {p.name for p in packet.iterdir() if p.is_file()} == expected_top)
            subject = ROOT / 'grants' / a / 'phase-01' if phase == '01' else ROOT / 'subject'
            expected_subject = {p.name for p in subject.iterdir() if p.is_file()} | ({'AVAILABILITY.md'} if phase == '02' else set())
            check(a + phase + ' subject membership', {p.name for p in (packet / 'subject').iterdir()} == expected_subject)
            for name in expected_subject - ({'AVAILABILITY.md'} if phase == '02' else set()):
                check(a + phase + ' exact subject ' + name, read(subject / name) == read(packet / 'subject' / name))
            check(a + phase + ' consumer availability', (packet / 'subject/consumer-source.txt').exists() == (phase == '02' or a in ('a02', 'a03')))
            observations.append({'author': a, 'phase': phase, 'form': form, 'raw_bytes': len(raw), 'artifacts': len(artifacts),
                'primary_utf8_bytes': len(payload['answer' if common else 'text'].encode()),
                'artifact_utf8_bytes': sum(len(i['text'].encode()) for i in artifacts),
                'common_metadata': manifest.get('submitted_metadata')})
    for a in FORMS:
        for name in ('SELECTED-01.json', 'READS-01.json', 'PROCESS-01.md'):
            original = read(ROOT / 'captures' / a / 'phase-01/author-files' / name)
            check(a + ' preserved first ' + name, original == read(ROOT / 'captures' / a / 'phase-02/author-files' / name) == read(DOC / 'authors' / a / 'attempt-01' / name))
        check(a + ' identical release bytes', read(ROOT / 'releases' / a / 'consumer-source.txt') == read(ROOT / 'subject/consumer-source.txt'))
    for row in load(ROOT / 'RELEASE-GRANTS.json')['grants']:
        pin(row, REPO / row['path'])
    for name in ('RECIPIENT-GRANTS-02.json', 'READER-RELEASE-ACTIVATION.json'):
        for row in load(ROOT / name)['files']:
            pin(row, REPO / row['path'])
    for row in load(ROOT / 'RECIPIENT-GRANTS-01.json')['readers']:
        for key in ('brief', 'packet_manifest'):
            check(row[key] + ' predispatch binding', sha(read(REPO / row[key])) == row[key + '_sha256'])
    activation = load(ROOT / 'AUTHOR-RELEASE-ACTIVATION.json')
    check('author release bound to first barrier', sha(read(ROOT / 'AUTHOR-PHASE-01-FROZEN.json')) == activation['barrier_sha256'])
    check('a03 unchanged raw selection with distinct phase captures', read(ROOT / 'captures/a03/phase-01/input.raw') == read(ROOT / 'captures/a03/phase-02/input.raw'))
    for a in ('a01', 'a02', 'a04'):
        check(a + ' changed raw selection', read(ROOT / 'captures' / a / 'phase-01/input.raw') != read(ROOT / 'captures' / a / 'phase-02/input.raw'))
    approval = load(ROOT / 'PREFLIGHT-DISPOSITION.json')
    for file, key in [('transport/attempt-01/capture.py','helper_sha256'), ('study_ops.py','ops_sha256')]:
        check(file + ' reviewed implementation unchanged', sha(read(DOC / file)) == approval[key])
    result = {'at': datetime.now(timezone.utc).isoformat(), 'checks': checks,
              'passed': sum(c['passed'] for c in checks), 'total': len(checks),
              'commands': commands, 'observations': observations, 'subject_executions': 0,
              'note': 'Static file/byte checks only. Historical 80 capture assertions are not new trials.'}
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(result['passed'], '/', result['total'], 'static integration checks')
    for row in checks:
        if not row['passed']:
            print('FAIL:', row['check'])
    return 0 if all(c['passed'] for c in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
