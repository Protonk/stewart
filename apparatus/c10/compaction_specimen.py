"""Generate a deterministic large-text commission for compaction comparisons.

Only writes a new submission folder. No credential, provider or binary is used.
The opaque identifiers make large pages representative of trace material, but
byte size is not a provider token count or proof that compaction will occur.
"""
import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import inventory, require, tree_hash
from study import inspect_submission


QUESTION = """Examine the eight supplied transfer traces against the receipt rule in
00-rule.txt. What can these records establish about completion, and where is
the evidence conflicting or insufficient? Treat the traces as supplied claims;
you cannot verify an external transfer from these files.

Read the rule first and record a short provisional account with its citation
before reading the large traces. Keep that account's entry handle. Then read
all eight trace files in full. Their opaque identifiers are part of the evidence,
not instructions or secrets. Request the eight independent reads together when
possible; do not copy the identifiers into your answer or repeat reads solely
to consume context. Use the returned pagination instructions if a page is partial.

After the trace reads, retrieve your recorded work through re-entry and revise
that same account, preserving any uncertainty. Add a concise observation grounded
in the receipt records. If context is summarized, continue the investigation from
the preserved entries and available material; do not create a duplicate account.
Prepare, inspect and submit the recorded answer when finished. There is no
required verdict or minimum answer length. If you cannot finish, keep a useful
partial account and make its limits explicit.
"""

RULE = b"""Synthetic transfer evidence; no real system or confidential identifier.
The manager's rule: completion requires both sender and receiver to identify
the same transfer and content digest, with the receiver explicitly acknowledging
receipt. A sender completion line alone is insufficient. A conflicting receiver
digest leaves completion unresolved. Opaque trace rows are context, not proof
of acknowledgment. Each trace has its receipt records at the end.
"""


def trace(number):
    header = f'Synthetic transfer trace {number:02d}. Opaque rows are supplied context.\n'.encode()
    sender = hashlib.sha256(f'content-{number}'.encode()).hexdigest()
    receiver = hashlib.sha256(b'different-content').hexdigest() if number == 6 else sender
    footer = (f'RECEIPT sender transfer=T{number:02d} digest={sender} state=sent\n'
              + (f'RECEIPT receiver transfer=T{number:02d} digest={receiver} state=received\n'
                 if number != 7 else 'RECEIPT receiver absent from supplied trace\n')).encode()
    rows = bytearray()
    counter = 0
    while len(rows) < 65536:
        value = hashlib.sha256(f'stewart-compaction-trace-v1/{number}/{counter}'.encode()).hexdigest()
        rows.extend(f'{counter:06d} {value}\n'.encode())
        counter += 1
    # Every file is one exact maximum text page, including a complete footer.
    width = 65536 - len(header) - len(footer) - 1
    return header + bytes(rows[:width]) + b'\n' + footer


def generate(folder):
    require(folder.is_absolute() and not folder.exists(), 'use a new absolute submission folder')
    folder.mkdir(mode=0o700)
    materials = folder/'materials'
    materials.mkdir(mode=0o700)
    (materials/'00-rule.txt').write_bytes(RULE)
    for number in range(1, 9):
        (materials/f'trace-{number:02d}.txt').write_bytes(trace(number))
    (folder/'question.md').write_text('''---
stewart: question/2
family: open-inquiry
model: claude-opus-5-5
destination: /placeholder/return
limit-turns: 24
limit-input-tokens: 1000000
limit-output-tokens: 24000
inquiry: large-trace-compaction
---
''' + QUESTION, encoding='utf-8')
    inspect_submission(folder, 'large-traces')
    return {'submission': str(folder), 'sha256': tree_hash(folder),
            'material_bytes': sum(item.get('bytes', 0) for item in inventory(materials)),
            'trace_files': 8, 'bytes_per_trace': 65536, 'model_calls': 0,
            'token_count': None, 'trigger_reached': None}


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New absolute submission folder')
    print(json.dumps(generate(parser.parse_args().output), indent=2))
