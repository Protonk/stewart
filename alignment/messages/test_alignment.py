"""Offline controls for raw-capture comparison and catalog packet sizing."""
import copy
import io
import tarfile
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from inventory import COUNTS, digest, inventory, shape
from prepare import prepare, worst_case
from common import strict_json

FIXTURES = HERE.parents[1] / 'apparatus/driver/testdata/messages'


def example(name, *, summary=False):
    raw = (FIXTURES / name).read_bytes()
    v = strict_json(raw)
    counts = {key: sum(row[key] for row in v['usage']['iterations']) for key in COUNTS}
    body = {'status': 200, 'outcome': 'response', 'charged': {'basis': 'reported',
            'input_tokens': sum(counts[key] for key in COUNTS[:-1]), 'output_tokens': counts['output_tokens']},
            'request_written': 'complete', 'response': {'bytes': len(raw), 'sha256': digest(raw), 'complete': True},
            'headers': {}, 'credential_reflection': {'body': False, 'headers': []},
            'usage': counts, 'model': v['model'], 'stop_reason': v['stop_reason']}
    request = {'compaction': summary, 'reset': False, 'body_sha256': 'a' * 64}
    arrangement = {'model': v['model'], 'family': 'open-inquiry/1', 'request_extra': {},
                   'anthropic_version': '2026-10-21', 'anthropic_beta': 'compact-2026-09-04'}
    return {'body': body}, request, arrangement, raw


class InventoryChecks(unittest.TestCase):
    def test_recorded_ordinary_usage(self):
        row = shape(*example('m3-ordinary-ending.json'))
        self.assertEqual(row['iterations'], ['message'])
        self.assertEqual(row['usage']['input_tokens'], 6660)

    def test_summary_uses_iteration_despite_zero_top_level(self):
        args = example('m4-summary.json', summary=True)
        row = shape(*args)
        self.assertTrue(row['top_level_zero'])
        self.assertEqual(row['usage']['input_tokens'], 344449)
        args[0]['body']['charged']['input_tokens'] = 0
        with self.assertRaisesRegex(ValueError, 'recorded usage'):
            shape(*args)

    def test_changed_or_missing_body(self):
        obs, req, arr, raw = example('m3-ordinary-ending.json')
        for replacement in (None, raw + b' '):
            with self.subTest(replacement_missing=replacement is None), self.assertRaises(ValueError):
                shape(obs, req, arr, replacement)

    def test_changed_model_reflection_and_request_kind(self):
        args = example('m4-summary.json', summary=True)
        for section, key, value in [(1, 'compaction', False), (2, 'model', 'another-model')]:
            changed = copy.deepcopy(args)
            changed[section][key] = value
            with self.assertRaises(ValueError):
                shape(*changed)
        args[0]['body']['credential_reflection']['body'] = True
        with self.assertRaisesRegex(ValueError, 'reflection'):
            shape(*args)

    def test_irrelevant_members_preserve_usage(self):
        obs, req, arr, raw = example('m3-ordinary-ending.json')
        v = json.loads(raw)
        v['opaque_extension'] = {'retained': True}
        modified = json.dumps(v).encode()
        obs['body']['response'].update(bytes=len(modified), sha256=digest(modified))
        row = shape(obs, req, arr, modified)
        self.assertEqual(row['usage']['input_tokens'], 6660)
        self.assertIn('opaque_extension', row['members'])

    def test_export_overlap_and_receipt_integrity(self):
        obs, req, arr, raw = example('m3-ordinary-ending.json')
        prefix = 'private/archive/audits/reference'
        obs.update(audit='reference', writer='fixture')
        obs['body'].update(request=1, attempt=1)
        obs['body']['response']['file'] = 'response-1-1.bin'
        req['request'] = 1
        members = {
            'prep/1/arrangement.json': json.dumps({'body': arr, 'audit': 'reference', 'writer': 'fixture'}).encode(),
            'runs/1/attempt-1-1.json': json.dumps(obs).encode(),
            'runs/1/request-1.json': json.dumps(req).encode(),
            'runs/1/response-1-1.bin': raw,
        }
        with tempfile.TemporaryDirectory() as td:
            folders = [Path(td) / 'first', Path(td) / 'second']
            exports = []
            for folder in folders:
                folder.mkdir()
                export = folder / 'work.tar'
                with tarfile.open(export, 'w') as tf:
                    for name, data in members.items():
                        member = tarfile.TarInfo(f'{prefix}/{name}')
                        member.size = len(data)
                        tf.addfile(member, io.BytesIO(data))
                metadata = {'outcome': 'exported', 'evidence_state': 'complete',
                            'archive': {'bytes': export.stat().st_size, 'sha256': digest(export.read_bytes())}}
                (folder / 'EXPORT.json').write_text(json.dumps(metadata))
                exports.append(export)
            result = inventory(exports)
            self.assertEqual(len(result['attempts']), 1)
            self.assertEqual(len(result['attempts']['reference/1/1/1']['sources']), 2)
            with exports[1].open('ab') as f:
                f.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'export receipt differs'):
                inventory(exports)


class PacketChecks(unittest.TestCase):
    def test_distinct_unpaid_packets_and_real_queue_pricing(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / 'drafts'
            prices = HERE / 'pricing-2026-11-21.json'
            m = prepare(dest, 'open-ordinary', None, prices)
            self.assertEqual(m['maximum_reserved_cents'], 1112)
            self.assertEqual([row['reserved_cents'] for row in m['proposals']], [124, 988])
            ids = []
            for row in m['proposals']:
                packet = strict_json((dest / row['file']).read_bytes())
                ids.append(packet['runs'][0]['id'])
                self.assertIsNone(packet['spending_authority'])
                self.assertIsNone(packet['effort'])
                self.assertFalse(any(packet['account'].values()))
                self.assertEqual(packet['max_placements'], 1)
                card = strict_json(prices.read_bytes())[packet['model']]
                with self.assertRaisesRegex(ValueError, 'compaction'):
                    worst_case(card, dict(packet['limits'], input_tokens=150000))
            self.assertEqual(len(set(ids)), 2)
            with self.assertRaises(FileExistsError):
                prepare(dest, 'open-ordinary', None, prices)


if __name__ == '__main__':
    unittest.main()
