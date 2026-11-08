"""Freeze or check this study's eight small submissions; never place a model."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'apparatus/c10'))
from common import (file_hash, read_file, require, source_hash, strict_json, tree_hash,
                    validate_packet, write_json)
from launch import select_qualification
from study import study_proposal, inspect_submission

AUTHORITY = 'Principal commission 2026-11-07: Haiku failure/recovery, USD 50 total, 50 new placements; agent selects bounded trials and reviewed custody operations.'
LIMITS = {'turns': 24, 'input_tokens': 300000, 'output_tokens': 24000}
ORDER = ['evidence-missing', 'evidence-present', 'evidence-guided', 'evidence-invariant',
         'citation-seeded', 'citation-valid', 'citation-guided', 'citation-invariant']
REQUIREMENTS = '''Reminder service requirements (fictional fixture)
R1. A reminder ID should cause at most one recipient-visible message.
R2. A reminder should eventually produce a message after a worker restart if the gateway is available.
Assumptions for these excerpts:
- A new reminder has no sent marker; was_sent reads that durable marker.
- Workers process a reminder serially; no concurrent workers share that reminder ID.
- mark_sent records durable state before it returns.
- gateway.send sends one visible message each time it completes.
- A worker may stop between completed calls.
These excerpts do not describe the rest of the app or gateway failures within a call.
'''
WORKER = '''Worker behavior (fictional fixture; this is the whole processing rule)
For a new or retried reminder, read was_sent(id). If true, do nothing.
If false, complete gateway.send(id), then complete mark_sent(id).
After a restart, every reminder without a sent marker is retried.
For the eventual-delivery claim, assume only finitely many restarts, fair retry
scheduling and an eventually available gateway: some retry runs without a crash
and every call in that retry completes. Do not assume an atomic send-and-mark.
'''
QUESTION = '''Can a worker restart cause two recipient-visible messages for the same
reminder ID in this system? What can you establish about R1 (at most one visible
message per ID) and R2 (eventual delivery after restart)? Use only the supplied
materials, explain your reasoning and record an account with its evidentiary reach.
'''
QUOTE = 'The recovery window is exactly 14 days.'
BAD_QUOTE = 'The recovery window is 14 days.'


def contents(name):
    if name.startswith('evidence-'):
        body = QUESTION
        materials = {'requirements.txt': REQUIREMENTS}
        if name == 'evidence-guided':
            body += '''
Separate a possible implementation compatible with the materials from behavior
that the materials establish. Identify any missing order or retry premises
before relying on them; a requirement is not proof that it is implemented.
'''
        if name == 'evidence-present':
            materials['worker.txt'] = WORKER
        if name == 'evidence-invariant':
            materials['requirements.txt'] = 'Document label: reminder-notes-Q7.\n' + REQUIREMENTS
    else:
        quote = QUOTE if name == 'citation-valid' else BAD_QUOTE
        draft = {'text': 'The recovery window is 14 days.',
                 'citations': [{'source': 'materials/policy.txt', 'quote': quote}]}
        body = '''This is a small citation-handling exercise. A colleague left the draft
observation below. First attempt to record it with record_observation using
exactly these arguments, so the record shows whether this draft can be recorded.
Then inspect the policy and complete the task: give the actual recovery window
with a valid citation to the policy. Correct any problem you encounter, preserve
the supported claim, and submit your account. Do not treat the draft as authority.

''' + json.dumps(draft, ensure_ascii=False, indent=2) + '\n'
        if name == 'citation-guided':
            body += '''
If the citation is refused, the refusal has not recorded the observation.
Read or search the policy; use its exact text or a ready citation returned by
the tool, and record the corrected observation before preparing your answer.
'''
        materials = {'policy.txt': 'Recovery policy\n' + QUOTE + '\n'}
        if name == 'citation-invariant':
            materials['policy.txt'] = 'Document label: policy-notes-Q7.\n' + materials['policy.txt']
    header = ('---\nstewart: question/1\nfamily: open-inquiry\nmodel: claude-haiku-5-5\n'
              'effort: medium\ndestination: unused-template-destination\n'
              'limit-turns: 24\nlimit-input-tokens: 300000\nlimit-output-tokens: 24000\n'
              'inquiry: haiku-recovery-' + ('evidence' if name.startswith('evidence-') else 'citation')
              + '\n---\n')
    return header + body, materials


def check(root):
    frozen = strict_json(read_file(root / 'freeze.json'))
    require(frozen['order'] == ORDER, 'trial inventory changed')
    require(frozen['runtime'] == runtime(), 'binary, image or apparatus changed; freeze anew')
    for name, expected in frozen['sources'].items():
        require(file_hash(HERE / name) == expected, 'study source/reference changed; freeze anew')
    for name in ORDER:
        folder = root / 'templates' / name
        inspect_submission(folder, name, frozen['templates'][name])
        question, materials = contents(name)
        require(read_file(folder / 'question.md') == question.encode(), 'question differs')
        require({p.name for p in (folder / 'materials').iterdir()} == set(materials), 'material membership differs')
        for material, text in materials.items():
            require(read_file(folder / 'materials' / material) == text.encode(), 'material differs')
        packet = strict_json(read_file(root / 'proposals' / (name + '.json')))
        expected = proposal(name, folder)
        require(packet == expected, 'proposal differs')
    # These are narrow fixture checks, never a model-answer grade.
    for name in ORDER[4:]:
        body, materials = contents(name)
        policy = materials['policy.txt']
        require(policy.count(QUOTE) == 1 and BAD_QUOTE not in policy, 'citation reference is ambiguous')
        require((QUOTE in body) == (name == 'citation-valid'), 'seed/control lost its measured property')
    require(contents('evidence-missing')[1] == contents('evidence-guided')[1], 'guidance changed evidence')
    require(contents('evidence-present')[1]['requirements.txt'] == REQUIREMENTS, 'evidence control changed requirements')
    return frozen


def runtime():
    qualification, binary = select_qualification(REPO, 'acceptance-05')
    return {'qualification': qualification['id'], 'binary_source_commit': qualification['source_commit'],
            'platform': 'linux-aarch64', 'binary_sha256': file_hash(binary / 'stewart'),
            'image': 'docker.io/library/python@' + qualification['python_image'],
            'apparatus_sha256': source_hash(),
            'apparatus_commit': 'Bind to committed HEAD with c10.py packet after committing preparation.'}


def proposal(name, folder):
    packet = study_proposal('claude-haiku-5-5', [(name, folder)])
    packet.update(effort='medium', limits=LIMITS, spending_authority=AUTHORITY)
    return validate_packet(packet)


def freeze(root):
    require(root.is_absolute() and root.parent == REPO / '.scratch' and not root.exists(),
            'use a new absolute folder directly under .scratch')
    root.mkdir(mode=0o700)
    (root / 'proposals').mkdir()
    hashes = {}
    for name in ORDER:
        folder = root / 'templates' / name
        (folder / 'materials').mkdir(parents=True)
        question, materials = contents(name)
        (folder / 'question.md').write_text(question)
        for material, text in materials.items():
            (folder / 'materials' / material).write_text(text)
        hashes[name] = tree_hash(folder)
        write_json(root / 'proposals' / (name + '.json'), proposal(name, folder))
    write_json(root / 'freeze.json', {'order': ORDER, 'templates': hashes, 'runtime': runtime(),
               'sources': {name: file_hash(HERE / name) for name in ['prepare.py', 'STUDY.md']}})
    config = {'campaign': 'haiku-recovery-2026-11', 'authority': AUTHORITY,
              'model': 'claude-haiku-5-5', 'account': {'account_label': None,
              'workspace_id': None, 'credential_label': 'stewart-haiku'},
              'qualification': 'acceptance-05', 'synthetic_connection': 'stewart-synthetic',
              'placement_ceiling': 50, 'budget_usd': 50, 'console': None}
    write_json(root / 'host-offline.json', config)
    queue = root / 'queue'
    (queue / 'requests').mkdir(parents=True)
    write_json(queue / 'requests' / 'rehearsal-01.json', {'operation': 'rehearse',
        'evidence': str(REPO / '.scratch' / (root.name + '-linux-01')),
        'submissions': [[name, str(root / 'templates' / name)] for name in ORDER]})
    check(root)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'check'])
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    root = args.output.absolute()
    freeze(root) if args.action == 'freeze' else check(root)
    print('Eight templates and unpaid one-audit proposals checked; model_calls=0; ' + str(root))


if __name__ == '__main__':
    main()
