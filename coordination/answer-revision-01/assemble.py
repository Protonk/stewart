"""Freeze exact source ranges and hypothetical entry bytes; no subject imports."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
DOC = Path(__file__).resolve().parent
ROOT = REPO / '.scratch/answer-revision-01'
REV = '5f00082d86768368478ed7cc85b52dd56a60255b'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def put(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def receipt(path, value):
    put(path, (json.dumps(value, indent=2, sort_keys=True) + '\n').encode())


sources, commands, selections = {}, [], []
for name in ('src/stewart/report_declaration.py', 'src/stewart/_json.py',
             'src/stewart/_bootstrap.py', 'src/stewart/_git.py',
             'src/stewart/assignment.py', 'src/stewart/status.py',
             'src/stewart/resources/QUESTION-TYPE.md'):
    argv = ['/usr/bin/git', 'show', REV + ':' + name]
    proc = subprocess.run(argv, cwd=REPO, capture_output=True)
    commands.append({'argv': argv, 'exit': proc.returncode,
                     'stderr': proc.stderr.decode(), 'stdout_sha256': sha(proc.stdout),
                     'stdout_bytes': len(proc.stdout)})
    if proc.returncode:
        raise RuntimeError('Pinned Git read failed: ' + name)
    sources[name] = proc.stdout
    put(ROOT / 'witness/source' / name, proc.stdout)


def function(name, symbol):
    node = next(n for n in ast.parse(sources[name]).body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == symbol)
    return node.lineno, node.end_lineno


def excerpt(output, name, ranges):
    lines = sources[name].splitlines(keepends=True)
    body = b''
    for start, end in ranges:
        body += (f'--- {REV}:{name}, original lines {start}-{end} ---\n').encode()
        body += b''.join(lines[start-1:end]) + b'\n'
    put(ROOT / 'subject' / output, body)
    selections.append({'packet_file': output, 'source_path': name, 'source_revision': REV,
                       'source_bytes': len(sources[name]), 'source_sha256': sha(sources[name]),
                       'ranges': ranges, 'packet_bytes': len(body), 'packet_sha256': sha(body)})


name = 'src/stewart/report_declaration.py'
excerpt('declaration-source.txt', name, [(1, function(name, 'session_declaration_expectations')[1])])
name = 'src/stewart/_json.py'
excerpt('control-json-source.txt', name, [(1, len(sources[name].splitlines()))])
excerpt('error-source.txt', 'src/stewart/_bootstrap.py', [function('src/stewart/_bootstrap.py', 'StewartError')])
excerpt('audit-id-source.txt', 'src/stewart/assignment.py', [function('src/stewart/assignment.py', 'audit_id')])
lines = sources['src/stewart/_git.py'].splitlines()
line = next(i for i, value in enumerate(lines, 1) if value.startswith(b'COMMIT_ID ='))
excerpt('commit-id-source.txt', 'src/stewart/_git.py', [(line, line)])
excerpt('consumer-source.txt', 'src/stewart/status.py', [function('src/stewart/status.py', '_auditor_report')])
lines = sources['src/stewart/resources/QUESTION-TYPE.md'].splitlines()
start = lines.index(b'## Information preservation') + 1
end = lines.index(b'## Constrained experiment construction')
excerpt('RECIPE.md', 'src/stewart/resources/QUESTION-TYPE.md', [(start, end)])
put(ROOT / 'subject/QUESTION.md', (DOC / 'QUESTION.md').read_bytes())

session = {'assignment': {'audit_id': 'preservation-case'}, 'target_commit': 'a' * 40,
           'prompt_commit': 'b' * 40, 'prompt_sha256': 'c' * 64, 'launch_token': 'd' * 16}
declaration = {'schema_version': 2, 'audit_id': 'preservation-case',
               'target_commit': 'a' * 40, 'launch_prompt_commit': 'b' * 40,
               'prompt_sha256': 'c' * 64, 'launch_token': 'd' * 16,
               'observed_checkout_commit': 'e' * 40, 'completion': 'complete', 'report_kind': 'answer'}


def report(value, prose='Hypothetical report text; no execution is asserted.'):
    return ('# Hypothetical report\n\n' + prose + '\n\n```audit-report\n' +
            json.dumps(value, indent=2) + '\n```\n').encode()


fixtures = {
    'report-valid.md': report(declaration),
    'report-mismatch.md': report({**declaration, 'target_commit': 'f' * 40}),
    'report-missing.md': b'# Hypothetical report\n\nThe prose says work is complete, but supplies no declaration.\n',
    'report-invalid.md': report(declaration).replace(b'"completion": "complete",', b'"completion": "partial",\n  "completion": "complete",'),
    'report-partial-null.md': report({**declaration, 'completion': 'partial', 'report_kind': None}),
    'report-prose-variant.md': report(declaration, 'Different hypothetical commentary outside the identical declaration.'),
}
for name, raw in fixtures.items():
    put(ROOT / 'subject' / name, raw)
receipt(ROOT / 'subject/ENTRIES.json', {
    'status': 'Authored hypothetical entry artifacts, not executed outputs or historical receipts',
    'session_record': session, 'collected_head': 'e' * 40, 'collection_name': 'hypothetical-collection',
    'read_assumption': 'Each named read returns exact report bytes and listed sha256 metadata; no safe-read or provenance enforcement is qualified.',
    'reports': [{'file': name, 'bytes': len(raw), 'sha256': sha(raw), 'expected_digest': sha(raw)} for name, raw in fixtures.items()],
    'additional_branch_inputs': ['record=None', 'expected_digest=None', 'read returns unavailable bytes or a digest differing from expected_digest'],
    'additional_branch_note': 'These may be analyzed from supplied code, but no actual reads or executions occurred.'})
receipt(ROOT / 'SOURCE-SELECTION.json', {'at': datetime.now(timezone.utc).isoformat(), 'revision': REV,
                                      'selections': selections, 'commands': commands})

for author, form, schedule in (('a01', 'common', 'delayed'), ('a02', 'minimal', 'complete'),
                               ('a03', 'common', 'complete'), ('a04', 'minimal', 'delayed')):
    packet = ROOT / 'grants' / author / 'phase-01'
    selected = []
    for path in sorted((ROOT / 'subject').iterdir()):
        if path.name == 'consumer-source.txt' and schedule == 'delayed':
            continue
        raw = path.read_bytes()
        put(packet / path.name, raw)
        selected.append({'file': path.name, 'bytes': len(raw), 'sha256': sha(raw)})
    note = ('The implementation of status._auditor_report has not been supplied in this phase. '
            'Its source is outside your grant; do not reconstruct it from repository/history access.'
            if schedule == 'delayed' else 'The exact implementation of status._auditor_report is supplied in consumer-source.txt.')
    put(packet / 'AVAILABILITY.md', ('# Issued evidence\n\n' + note + '\n\nThe supplied source is finite; excluded enforcement and unrelated dependencies remain outside this question.\n').encode())
    raw = (packet / 'AVAILABILITY.md').read_bytes()
    selected.append({'file': 'AVAILABILITY.md', 'bytes': len(raw), 'sha256': sha(raw)})
    receipt(packet / 'MANIFEST.json', {'question_id': 'declaration-status-preservation-01',
            'source_revision': REV, 'files': selected, 'no_subject_execution': True})
    release = ROOT / 'releases' / author
    raw = (ROOT / 'subject/consumer-source.txt').read_bytes()
    put(release / 'consumer-source.txt', raw)
    receipt(release / 'MANIFEST.json', {'question_id': 'declaration-status-preservation-01',
            'source_revision': REV, 'file': 'consumer-source.txt', 'bytes': len(raw), 'sha256': sha(raw),
            'previously_supplied': schedule == 'complete', 'meaning': 'Exact source, not a new execution or instruction to change any conclusion.'})
receipt(ROOT / 'ASSEMBLY.json', {'at': datetime.now(timezone.utc).isoformat(),
        'authors': 4, 'source_executions': 0,
        'files': [{'path': str(p.relative_to(REPO)), 'bytes': len(p.read_bytes()), 'sha256': sha(p.read_bytes())}
                  for folder in ('subject', 'grants', 'releases', 'witness')
                  for p in sorted((ROOT / folder).rglob('*')) if p.is_file()]})
print('Subject, four initial grants and four fixed releases created; zero subject executions.')
