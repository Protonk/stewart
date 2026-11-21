"""Offline controller controls; real-mode documents here are labelled parser fixtures."""

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('controller_test_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = load('surface_check')
profile_tests = load('test_profile')
RUN = Path(tempfile.mkdtemp(prefix='stewart-controller-controls-')).resolve()


class ControllerControls(unittest.TestCase):
    def setUp(self):
        self.root = RUN / self._testMethodName
        self.root.mkdir()
        self.writer = self.root / 'writer-canary'
        self.marker = self.root / 'writer-started'
        self.writer.write_text('#!/bin/sh\n# Stewart development build: claude-code __stewart-cc-relay __stewart-cc-hook\n'
                               'printf unexpected > ' + c.shlex.quote(str(self.marker)) + '\nexit 97\n')
        self.writer.chmod(0o700)
        self.packet = self.root / 'packet'

    def test_campaign_allows_subscription_warning_and_records_window(self):
        ledger = self.root / 'harness-reservations'
        ledger.mkdir()
        observer = c.campaign.AllowanceObserver(self.root / 'envelope.json', 'pinned', 'claude-sonnet-5-5', 'S0', 0)
        warning = {
            'status': 'allowed_warning', 'resetsAt': 1795482000, 'rateLimitType': 'seven_day',
            'utilization': 0.82, 'overageStatus': 'rejected', 'overageDisabledReason': 'org_level_disabled',
            'isUsingOverage': False, 'overageEnabled': False, 'surpassedThreshold': 0.75,
            'unifiedWindows': {'seven_day': {'utilization': 0.82, 'resetsAt': 1795482000,
                                            'status': 'allowed_warning', 'surpassedThreshold': 0.75}},
        }
        # Reassemble a split native frame and process the next frame from the same read.
        frame = json.dumps({'type': 'rate_limit_event', 'rate_limit_info': warning}).encode()
        observer.feed('stdout', frame[:15])
        observer.feed('stdout', frame[15:] + b'\n{"type":"rate_limit_event","rate_limit_info":{"status":"allowed"}}\n')
        observer.feed('stdout', b'{"type":"assistant","message":{"content":"a rate_limit_event"}}\n')
        other_model = {'status': 'allowed', 'unifiedWindows': {'seven_day_opus': {'status': 'rejected'}}}
        observer.feed('stdout', json.dumps({'type': 'rate_limit_event', 'rate_limit_info': other_model}).encode() + b'\n')
        self.assertFalse((ledger / 'STOP').exists())
        notice, = (ledger / 'warnings.jsonl').read_text().splitlines()
        record = json.loads(notice)
        self.assertEqual((record['trial'], record['placement']), ('S0', 0))
        self.assertEqual(record['rate_limit_info'], {
            'status': 'allowed_warning', 'rateLimitType': 'seven_day', 'resetsAt': 1795482000, 'utilization': 0.82})

    def test_campaign_missing_warning_telemetry_is_optional(self):
        ledger = self.root / 'harness-reservations'
        ledger.mkdir()
        observer = c.campaign.AllowanceObserver(self.root / 'envelope.json', 'pinned', 'claude-sonnet-5-5', 'S0', 0)
        observer.feed('stdout', b'{"type":"rate_limit_event","rate_limit_info":{"status":"allowed_warning"}}\n')
        self.assertEqual(json.loads((ledger / 'warnings.jsonl').read_text())['rate_limit_info'],
                         {'status': 'allowed_warning'})

    def test_campaign_stops_on_rejection_overage_or_ambiguous_status(self):
        safe = {'status': 'allowed_warning', 'overageEnabled': False, 'isUsingOverage': False,
                'overageStatus': 'rejected'}
        examples = [
            (dict(safe, status='rejected'), 'quota rejected'),
            (dict(safe, overageEnabled=True), 'paid extra usage'),
            (dict(safe, isUsingOverage=True), 'paid extra usage'),
            (dict(safe, overageStatus='allowed'), 'paid extra usage'),
            (dict(safe, status='unknown'), 'invalid'),
            (dict(safe, isUsingOverage='false'), 'invalid'),
            (dict(safe, rateLimitType='seven_day', unifiedWindows={'seven_day': {'status': 'rejected'}}),
             'quota rejected'),
            (dict(safe, rateLimitType='seven_day', unifiedWindows={'seven_day': {'status': 'allowed'}}),
             'conflicting'),
            (dict(safe, unifiedWindows={'five_hour': {'status': 'rejected'}}), 'quota rejected'),
            (dict(safe, unifiedWindows={'seven_day_sonnet': {'status': 'rejected'}}), 'quota rejected'),
            (dict(safe, unifiedWindows={'overage': {'status': 'allowed'}}), 'paid extra usage'),
            (dict(safe, utilization=1.5), 'invalid'),
            ({}, 'invalid'), (None, 'invalid'),
        ]
        for n, (info, reason) in enumerate(examples):
            with self.subTest(info=info):
                case = self.root / str(n)
                ledger = case / 'harness-reservations'
                ledger.mkdir(parents=True)
                observer = c.campaign.AllowanceObserver(case / 'envelope.json', 'pinned', 'claude-sonnet-5-5', 'S0', 0)
                frame = json.dumps({'type': 'rate_limit_event', 'rate_limit_info': info}).encode()
                observer.feed('stdout', frame)
                with self.assertRaisesRegex(ValueError, reason):
                    observer.finish('stdout')
                self.assertIn(reason, (ledger / 'STOP').read_text())
                self.assertFalse((ledger / 'warnings.jsonl').exists())

    def test_duplicate_billing_status_stops(self):
        ledger = self.root / 'harness-reservations'
        ledger.mkdir()
        observer = c.campaign.AllowanceObserver(self.root / 'envelope.json', 'pinned', 'claude-sonnet-5-5', 'S0', 0)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            observer.feed('stdout', b'{"type":"rate_limit_event","rate_limit_info":'
                                    b'{"status":"rejected","status":"allowed"}}\n')
        self.assertTrue((ledger / 'STOP').exists())

    def test_final_diagnostic_without_newline_stops(self):
        ledger = self.root / 'harness-reservations'
        ledger.mkdir()
        observer = c.campaign.AllowanceObserver(self.root / 'envelope.json', 'pinned', 'claude-sonnet-5-5', 'S0', 0)
        observer.feed('stderr', b'usage limit')
        with self.assertRaisesRegex(ValueError, 'allowance diagnostic'):
            observer.finish('stderr')

    def test_version_mismatch_stops_before_later_slots(self):
        ledger = self.root / 'harness-reservations'
        ledger.mkdir()
        observer = c.campaign.AllowanceObserver(self.root / 'envelope.json', 'pinned', 'claude-sonnet-5-5', 'S0', 0)
        with self.assertRaisesRegex(ValueError, 'version'):
            observer.feed('stdout', b'{"type":"system","subtype":"init","claude_code_version":"other"}\n')
        self.assertTrue((ledger / 'STOP').exists())

    def test_review_must_attest_reserved_surface_observation(self):
        root = self.root / 'harness-reservations'
        root.mkdir()
        packet = self.root / 'S0'
        out = packet / 'observation'
        out.mkdir(parents=True)
        c.save(packet / 'COMMISSION.json', {})
        digest = c.digest_file(packet / 'COMMISSION.json')
        c.save(out / 'OBSERVATION.json', {})
        c.save(out / 'RESULT.json', {'outcome': 'observed', 'commission_sha256': digest})
        claim = root / '001.json'
        c.save(claim, {'trial': 'S0', 'packet': str(packet), 'commission_sha256': digest})
        checked = out / 'CHECK.json'
        review = {'schema': 'stewart.claude-code.reviewed-check/1', 'outcome': 'observed', 'observation_sha256': '0'*64}
        c.save(checked, review)
        with self.assertRaisesRegex(ValueError, 'reserved observation'):
            c.campaign.acknowledge(claim, checked, c.digest_file(checked))
        checked.unlink()
        review['observation_sha256'] = c.digest_file(out / 'OBSERVATION.json')
        c.save(checked, review)
        c.campaign.acknowledge(claim, checked, c.digest_file(checked))
        self.assertTrue(claim.with_suffix('.review.json').is_file())

    def test_ledger_accounts_one_campaign_across_packets(self):
        ledger = self.root / 'harness-reservations'
        ledger.mkdir()
        env = self.root / 'envelope.json'
        data = {'schema': 'stewart.runtime-trials.envelope/1', 'waves': 2, 'harness': {
            'model': 'test', 'version': 'pin', 'service_starts': 2, 'wave_one_service_starts': 1,
            'extra_usage_allowed': False, 'billing': 'included-subscription-only'}}
        c.save(env, data)
        digest = c.digest_file(env)
        def slot(wave, name, number):
            return c.campaign.reserve(env, digest, wave, name, self.root / name, 'a' * 64, number, 'test', 'pin')
        def reviewed(path):
            c.save(path.with_suffix('.review.json'), {'reservation_sha256': c.digest_file(path),
                                                      'safe_to_continue': True})
        reviewed(slot(1, 'S0', 0))
        with self.assertRaisesRegex(ValueError, 'already reserved'):
            slot(1, 'S0', 0)
        first = slot(1, 'R1', 1)
        with self.assertRaisesRegex(ValueError, 'reviewed disposition'):
            slot(2, 'adaptive', 1)
        reviewed(first)
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            slot(1, 'R2', 1)
        reviewed(slot(2, 'adaptive', 1))
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            slot(2, 'adaptive', 2)

    def synthetic(self, family='open-inquiry', scenario='normal'):
        return c.prepare_packet(self.packet, self.writer, 'synthetic-control-model', family, scenario=scenario)

    def real_fixture(self):
        fixture = profile_tests.ProfileControls('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        commission = c.prepare_packet(self.packet, self.writer, 'synthetic-control-model', installation=fixture.install)
        self.assertFalse(fixture.marker.exists())
        return commission, fixture

    def test_login_directory_is_excluded_before_packet_creation_or_writer_hashing(self):
        fixture = profile_tests.ProfileControls('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for packet, writer in ((fixture.config / 'packet', self.writer),
                               (self.packet, fixture.config / '.credentials.json')):
            with self.subTest(packet=packet, writer=writer), patch.object(c, 'helper_binary') as hash_writer:
                with self.assertRaisesRegex(ValueError, 'overlaps the harness login directory'):
                    c.prepare_packet(packet, writer, 'synthetic-control-model', installation=fixture.install)
                hash_writer.assert_not_called()
                self.assertFalse(packet.exists())

    def rewrite_budget(self, change):
        path = self.packet / 'invocations/BUDGET.json'
        value = c.p.decode(path.read_bytes())
        change(value)
        path.write_bytes(c.p.compact(value) + b'\n')
        path = self.packet / 'COMMISSION.json'
        commission = c.p.decode(path.read_bytes())
        commission['budget_sha256'] = c.digest_file(self.packet / 'invocations/BUDGET.json')
        path.write_bytes(c.p.compact(commission) + b'\n')

    def test_preparation_freezes_three_pairs_and_all_family_inputs_without_launch(self):
        for family in c.surface.FAMILIES:
            self.packet = self.root / family
            commission = self.synthetic(family)
            verified, _ = c.verify_packet(self.packet)
            self.assertEqual(verified, commission)
            budget = c.p.decode((self.packet / 'invocations/BUDGET.json').read_bytes())
            self.assertEqual([slot['id'] for slot in budget['invocations']],
                             [kind + '-' + role for kind in c.KINDS for role in ('auth', 'model')])
            self.assertEqual(len({case['workspace'] for case in commission['cases']}), 3)
            self.assertFalse((self.packet / 'invocations/START.json').exists())
            self.assertFalse((self.packet / 'observation').exists())
            self.assertFalse(self.marker.exists())
        with self.assertRaises(FileExistsError):
            self.synthetic()

    def test_changed_executable_source_or_supplied_file_refuses(self):
        commission = self.synthetic()
        paths = [self.writer, self.packet / 'synthetic-harness', self.packet / c.CONTROLLER,
                 Path(commission['cases'][0]['workspace']) / 'settings.json',
                 self.packet / 'prepared/positive/inputs/input.jsonl']
        for path in paths:
            raw = path.read_bytes()
            path.write_bytes(raw + b'\nchanged')
            with self.assertRaisesRegex(ValueError, 'bound file changed'):
                c.verify_packet(self.packet)
            path.write_bytes(raw)
        c.verify_packet(self.packet)
        self.assertFalse(self.marker.exists())

    def test_missing_binding_is_not_excused_by_rehashed_budget(self):
        self.synthetic()
        self.rewrite_budget(lambda value: value['bindings'].remove(next(
            item for item in value['bindings'] if item['path'].endswith('/surface_check.py'))))
        with self.assertRaisesRegex(ValueError, 'inventory'):
            c.verify_packet(self.packet)

    def test_changed_surface_timeout_or_allowance_refuses(self):
        for name in ('argv', 'input', 'timeout', 'allowance'):
            self.packet = self.root / name
            self.synthetic()
            if name == 'allowance':
                path = self.packet / 'COMMISSION.json'
                value = c.p.decode(path.read_bytes())
                value['allowance']['model_invocations'] = 1
                path.write_bytes(c.p.compact(value))
            else:
                def change(value):
                    slot = value['invocations'][1]
                    if name == 'argv': slot['argv'].append('--unexpected')
                    elif name == 'input': slot['stdin_base64'] = 'Y2hhbmdlZA=='
                    else: slot['timeout_seconds'] += 1
                self.rewrite_budget(change)
            with self.assertRaisesRegex(ValueError, 'invocation|allowance'):
                c.verify_packet(self.packet)

    def test_unlisted_and_special_immutable_files_refuse(self):
        self.synthetic()
        extra = self.packet / 'unexpected'
        extra.write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            c.verify_packet(self.packet)
        extra.unlink()
        extra.symlink_to(self.writer)
        with self.assertRaisesRegex(ValueError, 'link or special'):
            c.verify_packet(self.packet)

    def test_live_authority_gate_precedes_budget_and_process_start(self):
        commission, fixture = self.real_fixture()
        raw = (self.packet / 'COMMISSION.json').read_bytes()
        digest = c.p.sha(raw)
        with patch.object(c, '__file__', str(self.packet / c.CONTROLLER)):
            for approved, disabled in ((None, False), (digest, False), ('0' * 64, True)):
                with patch.object(c.bounded, 'Budget') as budget:
                    with self.assertRaisesRegex(ValueError, 'principal-approved'):
                        c.run_packet(self.packet, approved, disabled)
                    budget.assert_not_called()
            # Firing control: the exact approval/condition reaches the budget,
            # replaced here before it can create state or invoke any process.
            with patch.object(c.bounded, 'Budget', side_effect=RuntimeError('authorized control reached budget')) as budget:
                with self.assertRaisesRegex(RuntimeError, 'authorized control'):
                    c.run_packet(self.packet, digest, True)
                budget.assert_called_once_with(self.packet / 'invocations', commission['budget_sha256'], True)
        self.assertFalse(fixture.marker.exists())
        self.assertFalse((self.packet / 'invocations/START.json').exists())

    def test_rehearsal_cannot_select_real_installation_or_receive_live_review(self):
        self.real_fixture()
        with patch.object(c, '__file__', str(self.packet / c.CONTROLLER)):
            with self.assertRaisesRegex(ValueError, 'synthetic packet'):
                c.run_packet(self.packet, rehearsal=True)
        self.packet = self.root / 'synthetic'
        self.synthetic()
        with patch.object(c, '__file__', str(self.packet / c.CONTROLLER)):
            with self.assertRaisesRegex(ValueError, 'principal-approved'):
                c.run_packet(self.packet, c.digest_file(self.packet / 'COMMISSION.json'), True)
        with self.assertRaisesRegex(ValueError, 'rehearsals cannot'):
            c.attest(self.packet, '0' * 64, 'synthetic reviewer', self.root / 'CHECK.json')
        self.assertFalse((self.root / 'CHECK.json').exists())

    def test_run_requires_frozen_controller(self):
        self.synthetic()
        with self.assertRaisesRegex(ValueError, 'frozen controller'):
            c.run_packet(self.packet, rehearsal=True)

    def test_duplicate_session_stops_before_third_pair(self):
        commission = self.synthetic()
        calls = []
        controller = self

        class FakeBudget:
            def __init__(self, root, *args):
                self.root, self.index, self.failed = root, 0, False
                self.value = c.p.decode((root / 'BUDGET.json').read_bytes())
            def __enter__(self):
                (self.root / 'uses').mkdir()
                c.save(self.root / 'START.json', {'scope': 'synthetic no-process controller control'})
                return self
            def execute(self, identity, **kwargs):
                slot = self.value['invocations'][self.index]
                self.index += 1
                calls.append(identity)
                out = self.root / 'uses' / identity
                out.mkdir()
                if slot['role'] == 'auth':
                    c.save(out / 'auth-status.json', {'loggedIn': True, 'authMethod': 'claude.ai',
                        'configDirectory': slot['environment']['CLAUDE_CONFIG_DIR']})
                return {'stop': None, 'group_gone': True, 'stream_eof': {'stdout': True, 'stderr': True},
                        'input_bytes_sent': len(c.base64.b64decode(slot['stdin_base64']))}
            def halt(self, reason):
                self.failed = True
                c.save(self.root / 'HALT.json', {'reason': reason, 'scope': 'synthetic no-process control'})
            def __exit__(self, *args):
                c.save(self.root / 'FINISH.json', {'invocations_reserved': self.index,
                    'invocations_unstarted': 6 - self.index, 'failed': self.failed, 'resume_allowed': False})

        class FakeCase:
            def __init__(self, inputs, identity, kind, workspace, evidence):
                self.case_id, self.root, self.workspace = identity, evidence, workspace
                evidence.mkdir()
            def start_listeners(self): pass
            def record_launch(self, value): pass
            def feed(self, raw): pass
            def feed_stderr(self, raw): pass
            def check_stop(self): pass
            def finish_stream(self, channel): pass
            def record_input(self, attempted, prefix): pass
            def close(self): pass
            def finish(self, process, auth):
                value = {'errors': [], 'checks': {name: 'observed' for name in c.surface.REQUIRED_CHECKS},
                    'stopping': 'observed', 'bindings': commission['bindings'],
                    'workspace': str(self.workspace), 'session_id': 'deliberately-reused-synthetic-session'}
                c.save(self.root / 'CASE.json', value)
                return value

        with patch.object(c, '__file__', str(self.packet / c.CONTROLLER)), \
                patch.object(c.bounded, 'Budget', FakeBudget), patch.object(c.observer, 'CaseObserver', FakeCase):
            self.assertEqual(c.run_packet(self.packet, rehearsal=True), 1)
        self.assertEqual(calls, ['positive-auth', 'positive-model', 'closed-gate-auth', 'closed-gate-model'])
        result = c.p.decode((self.packet / 'observation/RESULT.json').read_bytes())
        self.assertEqual(result['outcome'], 'failed')
        self.assertIn('fresh session', result['failures'][0]['error'])
        self.assertTrue(c.p.decode((self.packet / 'invocations/FINISH.json').read_bytes())['failed'])
        self.assertFalse((self.packet / 'observation/OBSERVATION.json').exists())
        self.assertFalse(self.marker.exists())

    def test_synthetic_ack_is_complete_at_publication_and_does_not_overwrite(self):
        marker = self.root / 'peer/startup-observed.json'
        link = c.os.link
        def observed_link(source, destination, **kwargs):
            self.assertFalse(marker.exists())
            self.assertEqual(c.p.decode((marker.parent / source).read_bytes()), {'session_id': 'synthetic-session'})
            return link(source, destination, **kwargs)
        with patch.object(c.os, 'link', side_effect=observed_link):
            c.publish_ack(marker, 'synthetic-session')
        self.assertEqual(c.p.decode(marker.read_bytes()), {'session_id': 'synthetic-session'})
        self.assertFalse((marker.parent / 'startup-observed.pending').exists())
        with self.assertRaises(FileExistsError):
            c.publish_ack(marker, 'different')
        self.assertEqual(c.p.decode(marker.read_bytes()), {'session_id': 'synthetic-session'})

    def review_fixture(self):
        commission, _ = self.real_fixture()
        out = self.packet / 'observation'
        (out / 'inputs').mkdir(parents=True)
        (out / 'execution').mkdir()
        for name in ('launch.json', 'surface.json', 'tools.json'):
            (out / 'inputs' / name).write_bytes((self.packet / 'prepared/positive/inputs' / name).read_bytes())
        (out / 'execution/BUDGET.json').write_bytes((self.packet / 'invocations/BUDGET.json').read_bytes())
        c.save(out / 'execution/START.json', {'mode': 'real-harness', 'budget_sha256': commission['budget_sha256'],
            'approved_digest': commission['budget_sha256'], 'extra_usage_disabled': True})
        c.save(out / 'execution/FINISH.json', {'invocations_reserved': 6, 'invocations_unstarted': 0, 'failed': False, 'resume_allowed': False})
        c.save(out / 'RESULT.json', {'schema': 'stewart.claude-code.surface-run/1', 'mode': 'real-harness', 'outcome': 'observed', 'failures': [],
            'commission_sha256': c.digest_file(self.packet / 'COMMISSION.json'),
            'attempted_cases': list(c.KINDS), 'completed_cases': list(c.KINDS)})
        (out / 'parser-fixture.txt').write_text('Synthetic review parser fixture; no real harness or authentication was invoked.\n')
        c.save(out / 'EVIDENCE.json', c.surface.manifest(out))
        observation = {'schema': 'stewart.claude-code.surface-observation/1', 'mode': 'real-harness',
            'scope': 'supplied-surface', 'started_at': '2026-11-12T00:00:00Z', 'finished_at': '2026-11-12T00:01:00Z',
            **commission['bindings'], 'evidence_manifest_sha256': c.digest_file(out / 'EVIDENCE.json'),
            'checks': [{'id': name, 'outcome': 'observed', 'evidence': ['parser-fixture.txt']} for name in c.surface.REQUIRED_CHECKS],
            'stopping': 'observed'}
        c.save(out / 'OBSERVATION.json', observation)
        return out, observation

    def test_review_requires_explicit_exact_observation_and_preserves_digest(self):
        out, _ = self.review_fixture()
        digest = c.digest_file(out / 'OBSERVATION.json')
        with self.assertRaisesRegex(ValueError, 'digest differs'):
            c.attest(self.packet, '0' * 64, 'synthetic parser reviewer', out / 'CHECK.json')
        self.assertFalse((out / 'CHECK.json').exists())
        c.attest(self.packet, digest, 'synthetic parser reviewer; no real check occurred', out / 'CHECK.json')
        review = c.p.decode((out / 'CHECK.json').read_bytes())
        self.assertEqual(review['observation_sha256'], digest)
        self.assertEqual(review['outcome'], 'observed')
        c.p.evidence(out, (out / 'EVIDENCE.json').read_bytes())
        with self.assertRaises(FileExistsError):
            c.attest(self.packet, digest, 'synthetic parser reviewer', out / 'CHECK.json')

    def test_review_refuses_an_incomplete_budget_and_input_directory_output(self):
        # Observation eligibility belongs to profile.validate_observation (test_profile).
        out, _ = self.review_fixture()
        digest = c.digest_file(out / 'OBSERVATION.json')
        with self.assertRaisesRegex(ValueError, 'outside the frozen packet'):
            c.attest(self.packet, digest, 'synthetic parser reviewer', self.packet / 'invalid-review.json')
        # An otherwise eligible observation whose budget left a slot unstarted.
        (out / 'execution/FINISH.json').write_bytes(c.p.compact({'invocations_reserved': 5, 'invocations_unstarted': 1,
                                                                 'failed': False, 'resume_allowed': False}) + b'\n')
        (out / 'EVIDENCE.json').write_bytes(c.p.compact(c.surface.manifest(out)) + b'\n')
        observation = c.p.decode((out / 'OBSERVATION.json').read_bytes())
        observation['evidence_manifest_sha256'] = c.digest_file(out / 'EVIDENCE.json')
        (out / 'OBSERVATION.json').write_bytes(c.p.compact(observation))
        with self.assertRaisesRegex(ValueError, 'complete approved budget'):
            c.attest(self.packet, c.digest_file(out / 'OBSERVATION.json'), 'synthetic parser reviewer', out / 'CHECK.json')
        self.assertFalse((out / 'CHECK.json').exists())

if __name__ == '__main__':
    print('Retained offline controller controls: ' + str(RUN), flush=True)
    unittest.main(verbosity=2)
