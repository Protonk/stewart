"""Explicit study submissions, kept separate from the six conformance specimens.

The supplied folder is a template with ordinary question/1 front matter.
The packet owns model, effort and allowances; the launcher owns destination.
Family, inquiry, varies, exact body bytes and material bytes come from the
hashed template. Both that template and the rendered intake are witnessed.
"""
from pathlib import Path

from common import (FAMILIES, inventory, read_file, require, tree_hash,
                    proposal, rehearsal_packet, validate_packet)


def case_from_question(raw, name):
    text = raw.decode('utf-8-sig')
    lines = text.splitlines(keepends=True)
    require(lines and lines[0] in ['---\n', '---\r\n'], 'study question needs question/1 front matter')
    ending = lines[0][3:]
    settings = {}
    for n, line in enumerate(lines[1:], 1):
        require(line.endswith(ending) and not (ending == '\n' and line.endswith('\r\n')),
                'mixed or incomplete study front-matter line endings')
        value = line[:-len(ending)]
        if value == '---':
            body = ''.join(lines[n+1:])
            break
        if not value or value.startswith('#'):
            continue
        key, separator, item = value.partition(': ')
        require(separator and key not in settings and item and item == item.strip(),
                'invalid or duplicate study front-matter field')
        settings[key] = item
    else:
        raise ValueError('study front matter has no closing delimiter')
    required = {'stewart', 'family', 'model', 'destination', 'limit-turns',
                'limit-input-tokens', 'limit-output-tokens'}
    require(required <= settings.keys() <= required | {'effort', 'inquiry', 'varies'},
            'study front-matter fields differ from question/1')
    require(settings['stewart'] == 'question/1' and settings['family'] in FAMILIES,
            'unknown study form')
    require(body.strip() and '\0' not in text, 'study question needs a nonblank UTF-8 body without NUL')
    inquiry = settings.get('inquiry')
    require(inquiry is not None and 1 <= len(inquiry) <= 128
            and not any(ord(c) < 32 or ord(c) == 127 for c in inquiry), 'study needs an inquiry label')
    varies = settings.get('varies')
    require(varies is None or varies.startswith('stw1:') and not any(c.isspace() for c in varies),
            'varies must be a Stewart reference; omit it until there is an earlier audit')
    return {'id': name, 'family': settings['family'], 'variant': 'study',
            'question': body, 'inquiry': inquiry, 'varies': varies}


def inspect_submission(root, name, expected=None):
    root = Path(root)
    identity = tree_hash(root)
    require(expected is None or identity == expected, 'study submission differs from packet')
    require({p.name for p in root.iterdir()} == {'question.md', 'materials'}
            and (root/'materials').is_dir(), 'study submission needs only question.md and materials/')
    case = case_from_question(read_file(root/'question.md'), name)
    for item in inventory(root/'materials'):
        if item['type'] == 'file':
            raw = read_file(root/'materials'/item['path'])
            require(b'\0' not in raw, 'NUL in study material')
            raw.decode('utf-8')
    require(tree_hash(root) == identity, 'study submission changed during inspection')
    return {**case, 'root': root, 'sha256': identity}


def copy_submission(source, target, expected):
    """Exclusive regular-file copies, with before/after membership checks."""
    source, target = Path(source), Path(target)
    require(tree_hash(source) == expected, 'study submission changed before copy')
    items = inventory(source)
    target.mkdir(mode=0o700)
    for item in items:
        path = target/item['path']
        if item['type'] == 'directory':
            path.mkdir(mode=0o700)
        else:
            with path.open('xb') as stream:
                stream.write(read_file(source/item['path']))
    require(tree_hash(source) == tree_hash(target) == expected, 'study submission changed during copy')


def study_proposal(model, submissions, *, rehearsal=False):
    require(bool(submissions), 'supply at least one study submission')
    packet = rehearsal_packet() if rehearsal else proposal(model)
    packet['schema'] = 'stewart.study-commission/1'
    packet['runs'] = ([{**run, 'submission_folder': None} for run in packet['runs']]
                      if rehearsal else [])
    for name, folder in submissions:
        folder = Path(folder).absolute()
        case = inspect_submission(folder, name)
        packet['runs'].append({'id': name, 'case': name, 'repetition': 1, 'scenario': 'submitted',
            'submission_folder': str(folder), 'submission_sha256': case['sha256']})
    return validate_packet(packet, rehearsal=rehearsal)


def supplied_runs(packet):
    return [run for run in packet['runs'] if run.get('submission_folder') is not None]


def resolve_submission(run, staged=None):
    return Path(run['submission_folder']) if staged is None else Path(staged)/run['id']
