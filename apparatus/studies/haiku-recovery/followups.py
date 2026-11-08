"""Generate two small, independently checkable study tasks; no model calls."""
import csv
from decimal import Decimal
import io
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'apparatus/c10'))
from common import file_hash, require, source_hash, tree_hash, write_json
from study import study_proposal

root = Path(sys.argv[1]).absolute()
require(root.parent == REPO / '.scratch' and not root.exists(), 'use a new .scratch directory')
root.mkdir(mode=0o700)
(root / 'proposals').mkdir()
rng = random.Random(20261107)
rows = [(f'r{(i * 73) % 260 + 1:04d}', rng.randrange(20, 9900)) for i in range(260)]
rows[50] = (rows[50][0], 9973)
rows[247] = (rows[247][0], 10007)
values = [rng.randrange(-9999, 10000) for _ in range(64)]
page_question = '''Read materials/records.txt starting at byte zero and assess the whole file.
Report the number of DATA records, the largest value, and its record ID. Only
DATA rows count; note fields and headings carry no values for this question.
Give a supported account of the answer and the scope you actually examined.
'''
sum_question = '''From materials/values.csv, report the number of data rows and the exact
signed sum of the value column, in integer units. These are synthetic quantities,
not money. Show enough of your calculation to make your result inspectable, and
cite the supplied table. If you cannot establish an exact sum, say so.
'''
cases = {}
for variant in ['long', 'short', 'guided', 'invariant']:
    name = 'page-' + variant
    body = page_question
    if variant == 'guided':
        body += '\nA reply marked complete:false is partial. Use its ready next call until\ncompletion before making a claim about the whole file.\n'
    material = 'Synthetic records; only DATA rows count. The note field is inert.\n'
    if variant == 'invariant': material = 'Document label: records-Q7.\n' + material
    material += ''.join(f'DATA {identity} value={value:05d}' +
                        (' note=' + 'x' * 256 if variant != 'short' else '') + '\n'
                        for identity, value in rows)
    parsed = [(line.split()[1], int(line.split()[2].split('=')[1]))
              for line in material.splitlines() if line.startswith('DATA ')]
    require(parsed == rows and len(parsed) == 260, 'page reference differs')
    winner = max(parsed, key=lambda x: x[1])
    require(winner == rows[247], 'maximum differs')
    marker = f'DATA {winner[0]} value={winner[1]:05d}'.encode()
    if variant == 'short': require(len(material.encode()) < 65536, 'compact control does not fit')
    else: require(material.encode().index(marker) > 65536, 'maximum appears on the first page')
    cases[name] = (body, {'records.txt': material}, {'rows': 260, 'maximum': winner[1], 'id': winner[0],
                  'maximum_byte_start': material.encode().index(marker), 'bytes': len(material.encode())})
for variant in ['baseline', 'short', 'guided', 'invariant']:
    name = 'sum-' + variant
    chosen = values[:8] if variant == 'short' else values
    prefix = 'z' if variant == 'invariant' else 'r'
    material = 'item,value\n' + ''.join(f'{prefix}{i+1:03d},{value}\n' for i, value in enumerate(chosen))
    parsed = [int(row['value']) for row in csv.DictReader(io.StringIO(material))]
    decimal_total = sum(Decimal(line.partition(',')[2]) for line in material.splitlines()[1:])
    require(parsed == chosen and sum(parsed) == decimal_total, 'independent sum calculations disagree')
    body = sum_question
    if variant == 'guided':
        body += '\nCalculate consecutive groups of eight rows first, record each subtotal,\nthen combine the subtotals. Check the row count and signs before submitting.\n'
    cases[name] = (body, {'values.csv': material}, {'rows': len(chosen), 'sum': sum(parsed),
                  'subtotals_of_eight': [sum(chosen[i:i+8]) for i in range(0, len(chosen), 8)]})

hashes, references = {}, {}
for name, (body, materials, reference) in cases.items():
    folder = root / 'templates' / name
    (folder / 'materials').mkdir(parents=True)
    header = ('---\nstewart: question/1\nfamily: open-inquiry\nmodel: claude-haiku-5-5\n'
              'effort: medium\ndestination: unused-template-destination\nlimit-turns: 24\n'
              'limit-input-tokens: 300000\nlimit-output-tokens: 24000\ninquiry: haiku-recovery-' + name.split('-')[0] + '\n---\n')
    (folder / 'question.md').write_text(header + body)
    for file, text in materials.items(): (folder / 'materials' / file).write_text(text)
    packet = study_proposal('claude-haiku-5-5', [(name, folder)])
    packet.update(effort='medium', limits={'turns': 24, 'input_tokens': 300000, 'output_tokens': 24000})
    write_json(root / 'proposals' / (name + '.json'), packet)
    hashes[name] = tree_hash(folder)
    references[name] = reference
write_json(root / 'private-reference.json', references)
write_json(root / 'extension.json', {'order': list(cases), 'templates': hashes,
    'apparatus_sha256': source_hash(),
    'sources': {str(HERE / name): file_hash(HERE / name) for name in ['followups.py', 'FOLLOWUPS.md']},
    'private_reference_sha256': file_hash(root / 'private-reference.json')})
print(json.dumps({'templates': hashes, 'private_reference': references}, indent=2))
