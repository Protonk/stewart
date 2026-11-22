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

sys.path.insert(0, str(HERE.parents[1] / "apparatus"))
import qualified

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


class QualificationChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ctx = qualified.Ctx(str(self.root))
        self.run_id = 'series'
        self.folder = self.root / '.scratch' / self.run_id
        self.folder.mkdir(parents=True)
        self.tracked = self.root / 'alignment/messages/records/series.json'
        self.tracked.parent.mkdir(parents=True)
        self.files = {}
        runs = {}
        writer = {'binary_sha256': 'a' * 64, 'qualification_id': 'release'}
        self.suites = [{'id': 'release', 'kind': 'suite', 'suite': 'acceptance', 'outcome': 'qualified',
                        'platforms': {'linux': {'outcome': 'qualified', 'release_sha256': 'a' * 64}}}]
        for slot, family in [('open', 'open-inquiry/1'), ('framing', 'inquiry-framing/1'),
                             ('comparison', 'comparison/1'), ('compaction', 'open-inquiry/1')]:
            prefix = slot + '/'
            (self.folder / slot).mkdir()
            def save(name, value):
                raw = json.dumps(value).encode()
                (self.folder / (prefix + name)).write_bytes(raw)
                self.files[prefix + name] = digest(raw)
                return digest(raw)
            receipt = save('work.tar', 'export bytes')
            grant = save('commission.json', 'commission')
            auth = save('authorization.json', {'grant_sha256': grant})
            export = save('EXPORT.json', {'outcome': 'exported', 'evidence_state': 'complete', 'archive': {'sha256': receipt}})
            effort = 'medium' if slot == 'framing' else None
            packet = {'model': 'example', 'effort': effort, 'limits': {}, 'bindings': writer,
                      'endpoint': 'https://example.invalid', 'proxy': None, 'runs': [{'id': slot}]}
            packet_digest = save('packet.json', packet)
            save('meter.json', {'packet_sha256': packet_digest, 'archive_sha256': receipt, 'cents': 1})
            usage = {k: {'reported': 1, 'estimated': 0} for k in ('turns', 'input_tokens', 'output_tokens')}
            report = {'audit': slot, 'auditor_submitted': True, 'closed': True, 'delivery_verified': True,
                      'ending': 'sealed', 'cause': None, 'seal_actor': 'auditor', 'usage': usage}
            compaction = {'successful_summaries': int(slot == 'compaction')}
            save('review.json', dict(report, failures=[], outcome='checked', placements=[{}],
                                     coverage={'compaction': compaction, 'citations_checked': 0, 'operations': {}}))
            seen = {'model': 'example', 'writer': writer['binary_sha256'], 'api_version': 'version',
                    'beta': 'beta', 'effort': effort}
            save('shapes.json', {'attempts': {'1': {'observation': seen}}, 'counts': {'tool_use': 1},
                                 'exports': [{'sha256': receipt, 'receipt_sha256': export}]})
            run = dict(report, model='example', family=family, response_models=['example'], limits={}, bindings=writer,
                       evidence_variant='inadequate' if slot == 'framing' else 'ordinary', effort=effort,
                       placements=1, operations={}, compaction=compaction, citations_checked=0, calculated_usd='0.01',
                       settled_cents=1, packet_sha256=packet_digest, authorization_sha256=auth,
                       commission_sha256=grant, export={'path': prefix + 'work.tar', 'sha256': receipt},
                       response_stops={'tool_use': 1})
            if slot == 'compaction':
                run.update(summary_and_reset=[{'request': 2}], prior_entry_revisions=[{'id': 'e1'}],
                           delivered_after_reset=[{'all_delivered': True, 'matching_duplicate_additions': []}])
                save('entry-delivery.json', run['delivered_after_reset'])
            observation = {}
            if slot == 'framing':
                observation = {'allowable_efforts': ['medium'], 'compaction_trigger_tokens': 100,
                               'compaction_request': {}, 'max_tokens_per_request': 1000}
            if slot == 'compaction':
                observation = {'gate_passed': True, 'gates': {'delivery': True}, 'summaries': run['summary_and_reset'],
                               'continuity': run['prior_entry_revisions']}
            save('observation.json', observation)
            runs[slot] = run
        self.ctx.blob = lambda commit, name: b'fixture'
        rows = {'A%d' % n: {'observed': 'yes', 'disposition': 'match', 'conclusion': 'reviewed',
                             'evidence': ['open/review.json'], 'fixtures': []} for n in range(1, 14)}
        self.doc = {'schema': 'stewart.messages-alignment/1', 'id': 'series', 'model': 'example',
                    'settings': {'model': 'example', 'route': 'direct', 'endpoint': 'https://example.invalid',
                                 'api_version': 'version', 'compaction_beta': 'beta', 'max_tokens_per_request': 1000,
                                 'effort_allowlist': ['medium'], 'compaction': {'trigger_tokens': 100, 'request': {}}},
                    'at': '2026-01-01T00:00:00Z', 'release_writer': writer, 'runs': runs, 'comparison': rows,
                    'capture_examples': {slot: {} for slot in runs}, 'files': self.files, 'fixtures_added': [],
                    'witness_limits': ['direct route'], 'currency': 'while pins hold', 'documentation_checked_on': '2026-01-01',
                    'fixture_source': {'commit': 'f' * 40, 'files': {'fixture.json': digest(b'fixture')}},
                    'reported_attempts': 4, 'estimated_attempts': 0, 'settled_cents': 4, 'calculated_usd': '0.04'}

    def decision(self, doc):
        raw = json.dumps(doc).encode()
        self.tracked.write_bytes(raw)
        (self.folder / 'ALIGNMENT.json').write_bytes(raw)
        return qualified.alignment_document(self.ctx, self.run_id, self.suites)

    def test_gate_refuses_unresolved_row_missing_family_and_wrong_writer(self):
        self.decision(self.doc)
        for which, edit in [('protocol', lambda d: d['comparison'].pop('A9')),
                            ('unresolved', lambda d: d['comparison']['A6'].update(disposition='open')),
                            ('run set', lambda d: d['runs'].pop('framing')),
                            ('writer', lambda d: d['release_writer'].update(binary_sha256='b' * 64)),
                            ('continuity', lambda d: d['runs']['compaction'].update(prior_entry_revisions=[]))]:
            with self.subTest(which=which), self.assertRaisesRegex(qualified.Refusal, which):
                doc = copy.deepcopy(self.doc)
                edit(doc)
                self.decision(doc)

    def test_checks_private_evidence_and_ignores_unrelated_files(self):
        entry, doc = self.decision(self.doc)
        qualified.verify_alignment_files(self.ctx, entry, doc)
        (self.folder / 'unrelated').write_bytes(b'unrelated')
        qualified.verify_alignment_files(self.ctx, entry, doc)
        (self.folder / 'open/work.tar').write_bytes(b'changed')
        with self.assertRaisesRegex(qualified.Refusal, 'open/work.tar'):
            qualified.verify_alignment_files(self.ctx, entry, doc)

    def test_changed_request_pin_with_unchanged_observation(self):
        self.doc['settings']['compaction']['trigger_tokens'] += 1
        entry, doc = self.decision(self.doc)
        with self.assertRaisesRegex(qualified.Refusal, 'release request pins'):
            qualified.verify_alignment_files(self.ctx, entry, doc)

    def test_changed_claim_with_unchanged_procedural_review(self):
        self.doc['runs']['open']['citations_checked'] = 10
        entry, doc = self.decision(self.doc)
        with self.assertRaisesRegex(qualified.Refusal, 'procedural review'):
            qualified.verify_alignment_files(self.ctx, entry, doc)


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
    def test_single_explicit_effort_packet(self):
        model = 'claude-haiku-5-5'
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / 'draft'
            manifest = prepare(dest, 'framing-inadequate', 'medium', HERE / 'pricing-2026-11-21.json',
                               models=(model,))
            row, = manifest['proposals']
            packet = strict_json((dest / row['file']).read_bytes())
            self.assertEqual((row['model'], packet['model'], packet['effort']), (model, model, 'medium'))
            self.assertEqual(packet['runs'][0]['case'], 'framing-inadequate')
            self.assertEqual(manifest['maximum_reserved_cents'], row['reserved_cents'])
            self.assertIsNone(packet['spending_authority'])

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
