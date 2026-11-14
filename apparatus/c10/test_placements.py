"""Offline controls for witnessed interruption, continuation and multi-placement export.

No Stewart binary, model, network or container. A shell stub stands in for
`stewart status`, so these establish the launcher's own gates and arithmetic.
What the service does at an interruption or a continuation is established only
by runs against the real binary (smoke.py natively, the Linux rehearsal for evidence).
"""
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import (CONTINUED, compact, digest, file_hash, read_file, rehearsal_packet, source_hash,
                    strict_json, validate_continuation, write_json)
import batch
from batch import (allowance_facts, continued_match, credential_marker, first_interruption, next_snapshot,
                   rehearsal_script)
import fake
from fake import Auditor
import placements
from placements import Refused, claim, prior_members, run_continuation
import session
from session import LogPoint, RequestSeen, Session, export_evidence_state
from study_build import system_bytes
import test_launch
import verify
from verify import Evidence, inventory_from_evidence
import driver_core as spec

KEY = b'c10-NONFUNCTIONAL-offline-control-key'
AUDIT = 'control-continue-cap'
REFERENCE = 'stw1:' + 'a' * 17 + ':' + 's' * 17 + ':/retained/archive'
APPARATUS = source_hash()


def record(kind, body):
    return {'record': 'stewart.record/1', 'kind': kind, 'audit': 'a1', 'writer': 'w', 'at': 't', 'body': body}


class LogPointTests(unittest.TestCase):
    """The point is a record the running placement publishes; nothing else selects it."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.log = self.root / 'log'
        self.log.mkdir()

    def case(self):
        case = Session.__new__(Session)
        case.binary, case.root, case.evidence = Path(sys.executable), self.root, self.root
        case.env = {'PATH': os.environ['PATH'], 'HOME': str(self.root)}
        case.commission, case.mode, case.index, case.process = {'stop_after_seconds': 60}, 'submitted', 0, None
        case.spawn = subprocess.Popen
        return case

    def publish(self, number, value):
        (self.log / f'{number}.json').write_bytes(compact(value) + b'\n')

    def child(self, number, value, then='time.sleep(60)'):
        raw = compact(value) + b'\n'
        return ('import sys,time; open(sys.argv[1],"xb").write(bytes.fromhex(sys.argv[2])); ' + then,
                str(self.log / f'{number}.json'), raw.hex())

    def test_published_reminder_is_witnessed_then_signalled(self):
        self.publish(1, record('run_started', {'run': 1}))
        notice = record('notice', {'prev': 'x', 'type': 'reminder', 'run': 1, 'request': 5})
        point = LogPoint(self.log, 'reminder_notice', self.root / 'interruption')
        case = self.case()
        with self.assertRaises(RuntimeError):
            # A signalled Python child prints no JSON; the launcher refuses to read a result into it.
            case.command('run', '-I', '-B', '-c', *self.child(2, notice), interrupt=point)
        command = strict_json((self.root / '01-run.json').read_bytes())
        seen = strict_json((self.root / 'interruption/point.json').read_bytes())
        self.assertEqual(command['exit'], -signal.SIGTERM)
        self.assertEqual(seen['record'], 'log/2.json')
        self.assertEqual(seen['sha256'], digest((self.log / '2.json').read_bytes()))
        self.assertEqual(seen['process']['pid'], command['pid'])
        self.assertTrue(seen['process_running'])
        sent = strict_json((self.root / 'interruption/signal.json').read_bytes())
        stopped = strict_json((self.root / 'interruption/termination.json').read_bytes())
        self.assertEqual((sent['signal'], sent['number'], sent['process_group']), ('SIGTERM', 15, command['pid']))
        self.assertLessEqual(seen['observed_at'], sent['sent_at'])
        self.assertLessEqual(sent['sent_at'], stopped['observed_at'])
        self.assertEqual((stopped['exit'], stopped['timed_out'], stopped['process_group_gone']), (-15, False, True))
        self.assertEqual(point.summary()['state'], 'signalled')
        self.assertFalse((self.root / 'interruption/unexercised.json').exists())

    def test_witness_records_what_the_signal_found_in_the_run_directory(self):
        run = self.root / 'runs/1'
        run.mkdir(parents=True)
        def attempt(request, outcome, written, basis):
            write_json(run / f'attempt-{request}-1.json', {'kind': 'provider_attempt', 'body': {
                'request': request, 'attempt': 1, 'outcome': outcome, 'request_written': written, 'charged': {'basis': basis}}})
        (run / 'request-1.json').write_text('{}')
        attempt(1, 'response', 'complete', 'reported')
        notice = record('notice', {'prev': 'x', 'type': 'reminder', 'run': 1, 'request': 2})
        point = LogPoint(self.log, 'reminder_notice', self.root / 'interruption')
        with self.assertRaises(RuntimeError):
            self.case().command('run', '-I', '-B', '-c', *self.child(1, notice), interrupt=point)
        seen = point.summary()
        self.assertEqual(seen['point']['run_directory_when_seen'],
                         {'request_captures': 1, 'attempt_records': 1, 'carrying_request_captured': False})
        self.assertEqual({key: seen['timing'][key] for key in ['placement', 'request', 'named_by_the_notice',
                          'request_captured', 'attempts', 'requests_captured', 'timing']},
                         {'placement': 1, 'request': 2, 'named_by_the_notice': True, 'request_captured': False,
                          'attempts': [], 'requests_captured': 1, 'timing': 'not_captured'})
        # The same reading once the carrying request exists, unwritten and then written.
        (run / 'request-2.json').write_text('{}')
        self.assertEqual(point.timing()['timing'], 'captured_not_written')
        attempt(2, 'aborted_by_signal', 'complete', 'estimated')
        self.assertEqual((point.timing()['timing'], point.timing()['attempts']), ('written_unanswered',
            [{'attempt': 1, 'outcome': 'aborted_by_signal', 'request_written': 'complete', 'charge_basis': 'estimated'}]))

    def test_another_record_kind_does_not_select_the_point(self):
        # Differs only in the published record: an entry is not the reminder.
        entry = record('entry', {'prev': 'x', 'action': 'add', 'invocation': {'run': 1, 'tool_use_id': 't', 'call': 1}})
        point = LogPoint(self.log, 'reminder_notice', self.root / 'interruption')
        self.case().command('run', '-I', '-B', '-c', *self.child(1, entry, then='print("done")'), raw=True, interrupt=point)
        self.assertEqual(strict_json((self.root / '01-run.json').read_bytes())['exit'], 0)
        missed = strict_json((self.root / 'interruption/unexercised.json').read_bytes())
        self.assertEqual((missed['reason'], missed['signal_sent'], missed['new_log_records_seen']),
                         ('placement_ended_first', False, 1))
        self.assertFalse((self.root / 'interruption/signal.json').exists())
        self.assertEqual(point.summary()['state'], 'unexercised')

    def test_the_same_entry_selects_the_entry_point(self):
        entry = record('entry', {'prev': 'x', 'action': 'add', 'invocation': {'run': 1, 'tool_use_id': 't', 'call': 1}})
        LogPoint(self.log, 'entry_record', self.root / 'interruption')  # only the folder claim matters here
        point = LogPoint(self.log, 'entry_record', self.root / 'second')
        with self.assertRaises(RuntimeError):
            self.case().command('run', '-I', '-B', '-c', *self.child(1, entry), interrupt=point)
        self.assertEqual(point.summary()['point']['record'], 'log/1.json')

    def test_an_earlier_placements_reminder_never_selects_the_point(self):
        # Invariance: the record exists before this placement starts, so nothing is signalled.
        self.publish(1, record('notice', {'prev': None, 'type': 'reminder', 'run': 1, 'request': 5}))
        point = LogPoint(self.log, 'reminder_notice', self.root / 'interruption')
        self.case().command('run', '-I', '-B', '-c', 'print("done")', raw=True, interrupt=point)
        self.assertEqual(point.summary()['unexercised']['reason'], 'placement_ended_first')
        self.assertIsNone(point.summary()['signal'])

    def test_elapsed_time_only_ends_the_watch(self):
        point = LogPoint(self.log, 'reminder_notice', self.root / 'interruption')
        child = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(60)'], start_new_session=True)
        try:
            self.assertFalse(point.await_point(child, 0.2))
            self.assertIsNone(child.poll())
            self.assertEqual(point.remaining(0.2), 0)
            self.assertEqual(point.summary()['unexercised']['reason'], 'watchdog_expired_first')
            point.ended(child, None, True)
            self.assertFalse((self.root / 'interruption/termination.json').exists())
        finally:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)

    def test_rehearsal_waits_for_the_request_in_flight_and_fails_without_it(self):
        self.publish(1, record('notice', {'prev': None, 'type': 'reminder', 'run': 1, 'request': 2}))
        held = mock.Mock()
        held.wait.return_value = False
        point = LogPoint(self.log, 'reminder_notice', self.root / 'interruption', in_flight=held)
        point.before, point.next = [], 1
        child = mock.Mock(pid=1)
        child.poll.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'did not report the request in flight'):
            point.await_point(child, 5)
        self.assertFalse((self.root / 'interruption/point.json').exists())

    def test_process_gone_between_the_observation_and_the_signal_is_unexercised(self):
        notice = record('notice', {'prev': None, 'type': 'reminder', 'run': 1, 'request': 2})
        point = LogPoint(self.log, 'reminder_notice', self.root / 'interruption')
        with mock.patch.object(session.os, 'killpg', side_effect=ProcessLookupError()):
            self.case().command('run', '-I', '-B', '-c', *self.child(1, notice, then='time.sleep(0.5); print("done")'),
                                raw=True, interrupt=point)
        summary = point.summary()
        self.assertEqual((summary['state'], summary['unexercised']['reason'], summary['signal']),
                         ('unexercised', 'placement_ended_at_the_point', None))
        self.assertEqual(summary['point']['record'], 'log/1.json')
        self.assertFalse((self.root / 'interruption/termination.json').exists())

    def test_witness_folder_is_claimed_once_and_unknown_points_refuse(self):
        LogPoint(self.log, 'reminder_notice', self.root / 'interruption')
        with self.assertRaises(FileExistsError):
            LogPoint(self.log, 'reminder_notice', self.root / 'interruption')
        with self.assertRaises(ValueError):
            LogPoint(self.log, 'after_ten_seconds', self.root / 'other')

    def test_sanity_interruption_signals_once_its_request_is_seen(self):
        seen = threading.Event()
        seen.set()
        with self.assertRaises(RuntimeError):
            self.case().command('run', '-I', '-B', '-c', 'import time; time.sleep(60)', interrupt=RequestSeen(seen))
        command = strict_json((self.root / '01-run.json').read_bytes())
        self.assertEqual((command['exit'], command['timed_out'], command['process_state']), (-signal.SIGTERM, False, 'exited'))
        self.assertNotIn('failure', command)

    def test_sanity_interruption_still_needs_its_request_witness(self):
        unseen = mock.Mock()
        unseen.wait.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'interruption witness did not observe the request'):
            RequestSeen(unseen).await_point(mock.Mock(), 60)
        unseen.wait.assert_called_once_with(20)
        self.assertEqual(RequestSeen(unseen).remaining(60), 60)


class ExportStateTests(unittest.TestCase):
    """Every placement must be exportable alone before an audit with several exports."""
    def two_placements(self, root):
        test_launch.LaunchTests().complete_evidence(root)
        evidence, audit = root / 'evidence', root / 'archive/audits/audit'
        (evidence / 'placement-0002').mkdir()
        write_json(evidence / 'placement-0002/RESULT.json', {'failure': False})
        write_json(evidence / '03-run.json', {'argv': ['/bin-in/stewart', 'run', 'stw1:fixture', '--json', '--key-fd', '3'], 'exit': 0, 'timed_out': False})
        write_json(evidence / '04-status-after-run.json', {'argv': ['/bin-in/stewart', 'status', 'stw1:fixture', '--json'], 'exit': 0, 'timed_out': False})
        write_json(evidence / '04-status-after-run.stdout', {'data': {'runs': {'held': False, 'count': 2, 'last': {'number': 2, 'ending': 'sealed'}}}})
        write_json(audit / 'log/3.json', {'kind': 'run_started', 'body': {'run': 2}})
        write_json(audit / 'log/4.json', {'kind': 'run_ended', 'body': {'run': 2, 'requests': 1, 'attempts': 1}})
        run = audit / 'runs/2'
        (run / 'stage').mkdir(parents=True)
        write_json(run / 'request-1.json', {'request': 1})
        write_json(run / 'attempt-1-1.json', {'kind': 'provider_attempt', 'body': {'request': 1, 'attempt': 1, 'response': None, 'credential_reflection': {'body': False, 'headers': []}}})
        return run

    def test_two_complete_placements_export_and_an_unrelated_file_changes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.two_placements(root)
            self.assertEqual(export_evidence_state(root), 'complete')
            (root / 'evidence/operator-1-status.json').write_text('{}')
            self.assertEqual(export_evidence_state(root), 'complete')

    def test_each_withholding_reason_fires_for_the_later_placement(self):
        def change(path, keys, value):
            def apply(root):
                target = root / path
                data = json.loads(target.read_text())
                item = data
                for key in keys[:-1]:
                    item = item[key]
                item[keys[-1]] = value
                target.write_text(json.dumps(data) + '\n')
            return apply
        def remove(path):
            return lambda root: (root / path).unlink()
        def add(path, content=b'orphan'):
            return lambda root: ((root / path).parent.mkdir(parents=True, exist_ok=True), (root / path).write_bytes(content))
        run = 'archive/audits/audit/runs/2/'
        cases = [
            ('procedure_not_complete', change('evidence/placement-0002/RESULT.json', ['failure'], True)),
            ('missing_or_malformed_evidence', remove('evidence/placement-0002/RESULT.json')),
            ('missing_run_observation', lambda root: [(root / 'evidence' / name).unlink() for name in ['04-status-after-run.json', '04-status-after-run.stdout']]),
            ('missing_run_observation', add('evidence/placement-0003/launch-intent.json', b'{}')),
            ('mismatched_run_observation', change('evidence/03-run.json', ['argv', 2], 'stw1:another')),
            ('uncertain_process_exit', change('evidence/03-run.json', ['exit'], -15)),
            ('uncertain_process_exit', change('evidence/03-run.json', ['timed_out'], True)),
            ('uncertain_writer_state', change('evidence/04-status-after-run.stdout', ['data', 'runs', 'count'], 1)),
            ('uncertain_writer_state', change('evidence/04-status-after-run.stdout', ['data', 'runs', 'held'], True)),
            ('uncertain_writer_state', change('evidence/04-status-after-run.stdout', ['data', 'runs', 'last', 'number'], 1)),
            ('missing_run_boundary', remove('archive/audits/audit/log/4.json')),
            ('invalid_run_identity', change('archive/audits/audit/log/3.json', ['body', 'run'], 1)),
            ('invalid_run_counts', change('archive/audits/audit/log/4.json', ['body', 'requests'], 0)),
            ('capture_counts_disagree', change('archive/audits/audit/log/4.json', ['body', 'attempts'], 2)),
            ('unaccounted_capture', add(run + 'response-9-1.bin')),
            ('credential_reflection_recorded', change(run + 'attempt-1-1.json', ['body', 'credential_reflection', 'body'], True)),
            ('missing_attempt_evidence', remove(run + 'attempt-1-1.json')),
            ('unknown_run_membership', add('archive/audits/audit/runs/3/stage/x', b'')),
        ]
        for expected, alter in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.two_placements(root)
                self.assertEqual(export_evidence_state(root), 'complete')
                alter(root)
                self.assertEqual(export_evidence_state(root), expected)

    def test_bound_cut_off_body_is_a_complete_observation_only_for_a_stopped_or_failed_attempt(self):
        cut = b'{"id":"msg","content":[{"ty'
        def build(root, *, outcome='aborted_by_signal', complete=False, capture=cut, record=True, reflected=False):
            run = self.two_placements(root)
            body = {'request': 1, 'attempt': 1, 'outcome': outcome, 'response': None,
                    'credential_reflection': {'body': reflected, 'headers': []}}
            if outcome is None:
                del body['outcome']
            if record:
                body['response'] = {'file': 'response-1-1.bin', 'bytes': len(cut), 'sha256': digest(cut), 'complete': complete}
            (run / 'attempt-1-1.json').write_text(json.dumps({'kind': 'provider_attempt', 'body': body}))
            if capture is not None:
                (run / 'response-1-1.bin').write_bytes(capture)
        cases = [
            ('complete', {}),
            # INTERFACE 6.6 outcomes that received a status line and are not a decodable message.
            *[('complete', {'outcome': outcome}) for outcome in ['aborted_by_close', 'timeout', 'connection_lost',
                                                                 'http_error', 'response_undecodable']],
            ('complete', {'outcome': 'response', 'complete': True}),          # a whole body, as before
            ('incomplete_response_evidence', {'outcome': 'response'}),       # a used response must be whole
            ('incomplete_response_evidence', {'outcome': 'connection_failed'}),
            ('incomplete_response_evidence', {'outcome': None}),
            ('incomplete_response_evidence', {'outcome': 'made_up'}),
            ('incomplete_response_evidence', {'complete': None}),
            ('incomplete_response_evidence', {'complete': 'false'}),
            ('incomplete_response_evidence', {'capture': b'X' + cut[1:]}),   # same size, one byte changed
            ('incomplete_response_evidence', {'capture': cut[:-1]}),
            ('incomplete_response_evidence', {'capture': cut + b'"'}),
            ('credential_reflection_recorded', {'reflected': True}),
            ('unaccounted_capture', {'record': False}),
            ('missing_or_malformed_evidence', {'capture': None}),
        ]
        for expected, options in cases:
            with self.subTest(expected=expected, options=options), tempfile.TemporaryDirectory() as folder:
                build(Path(folder), **options)
                self.assertEqual(export_evidence_state(Path(folder)), expected)

    def test_run_and_status_observations_must_alternate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.two_placements(root)
            evidence = root / 'evidence'
            # Two starts and two observations, but the second observation precedes the second start.
            (evidence / '03-run.json').rename(evidence / '05-run.json')
            self.assertEqual(export_evidence_state(root), 'missing_run_observation')
            (evidence / '05-run.json').rename(evidence / '03-run.json')
            self.assertEqual(export_evidence_state(root), 'complete')

    def test_single_placement_fixture_is_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            test_launch.LaunchTests().complete_evidence(root)
            self.assertEqual(export_evidence_state(root), 'complete')
            (root / 'evidence/placement-0002').mkdir()
            self.assertEqual(export_evidence_state(root), 'missing_run_observation')


class ArithmeticTests(unittest.TestCase):
    """Expected values are worked from INTERFACE 6.3 and 6.4 by hand, not from any run."""
    def allowances(self, output_used, output_limit, turns_used=0, input_used=0):
        return {'turns': {'used': turns_used, 'limit': 12}, 'input_tokens': {'used': input_used, 'limit': 160000},
                'output_tokens': {'used': output_used, 'limit': output_limit}}

    def test_planned_interruption_under_a_small_allowance_ends_the_next_placement(self):
        point = {'after': 'reminder_notice', 'signal': 'SIGTERM'}
        small = allowance_facts(self.allowances(0, 12000), point)['planned_interruption']
        # min(16000, 12000) is the whole allowance: nothing remains, under 1,024.
        self.assertEqual((small['output_charge_if_one_request_is_aborted_in_flight'], small['output_remaining_after_that_charge']), (12000, 0))
        self.assertTrue(small['next_placement_ends_limit_reached_before_any_request'])
        enough = allowance_facts(self.allowances(0, 30000), point)['planned_interruption']
        self.assertEqual((enough['output_charge_if_one_request_is_aborted_in_flight'], enough['output_remaining_after_that_charge']), (16000, 14000))
        self.assertFalse(enough['next_placement_ends_limit_reached_before_any_request'])
        self.assertEqual(enough['reported_output_before_the_point_that_still_leaves_1024'], 12976)
        edge = allowance_facts(self.allowances(0, 17023), point)['planned_interruption']
        self.assertTrue(edge['next_placement_ends_limit_reached_before_any_request'])
        self.assertFalse(allowance_facts(self.allowances(0, 17024), point)['planned_interruption']['next_placement_ends_limit_reached_before_any_request'])

    def test_exhaustion_before_a_start_is_a_fact_and_no_point_means_no_forecast(self):
        self.assertIsNone(allowance_facts(self.allowances(0, 30000))['planned_interruption'])
        for values, expected in [((0, 30000), False), ((28977, 30000), True), ((28976, 30000), False),
                                 ((0, 30000, 12), True), ((0, 30000, 11), False), ((0, 30000, 0, 160000), True)]:
            with self.subTest(values=values):
                self.assertIs(allowance_facts(self.allowances(*values))['this_placement_ends_limit_reached_before_any_request'], expected)

    def test_notice_sent_states_follow_the_attempt_records(self):
        self.assertEqual(verify.notice_sent(True, ['complete']), 'sent')
        self.assertEqual(verify.notice_sent(True, ['none', 'partial']), 'sent')
        self.assertEqual(verify.notice_sent(True, ['none']), 'unknown')
        self.assertEqual(verify.notice_sent(True, []), 'unknown')   # a complete capture alone never establishes transmission
        self.assertEqual(verify.notice_sent(False, []), 'not_sent')

    def test_near_limit_and_exhaustion_thresholds(self):
        limits = {'turns': 12, 'input_tokens': 160000, 'output_tokens': 30000}
        used = {'turns': 9, 'input_tokens': 9000, 'output_tokens': 17800}
        self.assertEqual(verify.near_limit(limits, used), (False, {'turns': 3, 'input_tokens': 151000, 'output_tokens': 12200}))
        used['turns'] = 10   # 2 * 100 <= 20 * 12
        self.assertTrue(verify.near_limit(limits, used)[0])
        self.assertTrue(verify.near_limit(limits, {'turns': 0, 'input_tokens': 0, 'output_tokens': 24000})[0])
        self.assertFalse(verify.near_limit(limits, {'turns': 0, 'input_tokens': 0, 'output_tokens': 23999})[0])
        self.assertEqual(verify.near_limit(limits, {'turns': 13, 'input_tokens': 0, 'output_tokens': 0})[1]['turns'], 0)
        self.assertFalse(verify.limit_exhausted(limits, {'turns': 11, 'input_tokens': 159999, 'output_tokens': 28976}))
        for key, value in [('turns', 12), ('input_tokens', 160000), ('output_tokens', 28977)]:
            self.assertTrue(verify.limit_exhausted(limits, {'turns': 0, 'input_tokens': 0, 'output_tokens': 0, key: value}))

    def test_first_message_bytes_carry_the_continuation_notice_only_when_continuing(self):
        question = 'Why "this"?\nSecond line \\ é\n'
        self.assertEqual(json.loads(verify.first_message(question, False)), fake.first_message(question, 1))
        continuing = json.loads(verify.first_message(question, True))
        self.assertEqual(continuing, fake.first_message(question, 2))
        self.assertEqual([block['text'] for block in continuing['content']], [question, spec.CONTINUATION])
        self.assertTrue(verify.first_message(question, True).startswith(b'{"role":"user","content":[{"type":"text","text":"Why \\"this\\"?\\nSecond'))
        self.assertEqual(verify.preview('é'.encode() * 150), 'é' * 100)
        self.assertEqual(verify.preview(b'x' * 199 + 'é'.encode()), 'x' * 199)


class ControlInventoryTests(unittest.TestCase):
    def test_interruption_comes_from_the_packet_or_the_fixed_control(self):
        packet = rehearsal_packet()
        runs = {run['scenario']: run for run in packet['runs']}
        self.assertIsNone(first_interruption(packet, runs['submitted'], 'rehearse'))
        self.assertIsNone(first_interruption(packet, runs['continue-cap'], 'rehearse'))
        self.assertEqual(first_interruption(packet, runs['reminder-spent'], 'rehearse'), {'after': 'reminder_notice', 'signal': 'SIGTERM'})
        self.assertEqual(first_interruption(packet, runs['reminder-unused'], 'rehearse'), {'after': 'entry_record', 'signal': 'SIGTERM'})
        # A live ordinary packet never acquires an interruption from a scenario name.
        self.assertIsNone(first_interruption(packet, runs['reminder-spent'], 'live'))
        study = {'schema': 'stewart.interruption-commission/1', 'interruption': {'after': 'reminder_notice', 'signal': 'SIGTERM'}}
        self.assertEqual(first_interruption(study, runs['submitted'], 'live'), study['interruption'])

    def test_supplied_study_rehearsal_follows_the_matching_fixed_script(self):
        packet = rehearsal_packet()
        runs = {run['scenario']: run for run in packet['runs']}
        self.assertEqual(rehearsal_script(packet, runs['submitted']), 'submitted')
        for after, script in [('reminder_notice', 'reminder-spent-submits'), ('entry_record', 'reminder-unused')]:
            study = {'schema': 'stewart.interruption-commission/1', 'interruption': {'after': after, 'signal': 'SIGTERM'}}
            self.assertEqual(rehearsal_script(study, runs['submitted']), script)
            self.assertEqual(CONTINUED[script]['interruption'], after)
        study = {'schema': 'stewart.interruption-commission/1', 'interruption': {'after': 'entry_record', 'signal': 'SIGTERM'}}
        self.assertEqual(rehearsal_script(study, runs['reminder-unused']), 'reminder-unused')
        with self.assertRaises(ValueError):
            rehearsal_script(study, runs['reminder-spent'])

    def observed(self, ending, cause, placements, *, witness=None, submitted=False):
        rows = [{'interruption': None} for _ in range(placements)]
        if witness is not None:
            rows[-1]['interruption'] = {'followed_by_signal_ending': True}
        review = {'outcome': 'checked', 'ending': ending, 'cause': cause, 'placements': rows,
                  'auditor_submitted': submitted, 'delivery_verified': submitted}
        closure = {'close_exit': 0, 'status_exit': 0, 'timed_out': False, 'state': {'closed': True}} if submitted else None
        return {'review_before_close': review, 'interruption': witness, 'caller_reply_lost': False,
                'timed_out': False, 'automatic_close': closure}

    def test_continued_control_expectations_come_from_the_inventory(self):
        exported = {'outcome': 'exported'}
        witness = {'after': 'reminder_notice', 'state': 'signalled', 'termination': {'timed_out': False}}
        first = self.observed('interrupted', 'signal', 1, witness=witness)
        self.assertTrue(continued_match(first, exported, 'reminder-spent', 1))
        self.assertFalse(continued_match(first, {'outcome': 'withheld'}, 'reminder-spent', 1))
        self.assertFalse(continued_match(self.observed('interrupted', 'max_tokens', 1, witness=witness), exported, 'reminder-spent', 1))
        self.assertFalse(continued_match(self.observed('interrupted', 'signal', 1), exported, 'reminder-spent', 1))
        unexercised = {'after': 'reminder_notice', 'state': 'unexercised', 'termination': None}
        self.assertFalse(continued_match(self.observed('interrupted', 'signal', 1, witness=unexercised), exported, 'reminder-spent', 1))
        self.assertTrue(continued_match(self.observed('ended_unsubmitted', None, 2), exported, 'reminder-spent', 2))
        self.assertFalse(continued_match(self.observed('sealed', None, 2, submitted=True), exported, 'reminder-spent', 2))
        self.assertTrue(continued_match(self.observed('sealed', None, 2, submitted=True), exported, 'reminder-spent-submits', 2))
        # The second placement must be reviewed together with the first.
        self.assertFalse(continued_match(self.observed('sealed', None, 1, submitted=True), exported, 'reminder-spent-submits', 2))
        self.assertTrue(continued_match(self.observed('interrupted', 'max_tokens', 1), exported, 'continue-cap', 1))
        self.assertFalse(continued_match(self.observed('interrupted', 'max_tokens', 1, witness=witness), exported, 'continue-cap', 1))

    def test_holding_and_control_inventories_follow_the_frozen_table(self):
        self.assertEqual(sorted(placements.NO_SUBJECT), sorted(CONTINUED))
        self.assertEqual(sorted(fake.REENTRY), sorted(CONTINUED))
        for script, entry in CONTINUED.items():
            first = fake.SCRIPTS[script][0]
            with self.subTest(script=script):
                self.assertEqual(len(fake.SCRIPTS[script]), len(entry['endings']))
                # A held control withholds its last request; an unheld one answers every request.
                self.assertEqual({True: 'hold', False: 'idle'}.get(entry['held']),
                                 first[-1] if first[-1] in ['hold', 'idle'] else None)
                self.assertEqual(entry['held'] is None, entry['interruption'] is None)
        self.assertEqual([script for script, entry in CONTINUED.items() if entry['held'] is False], ['reminder-spent-unheld'])
        # The supplied-study mapping names held controls only.
        for after in ['reminder_notice', 'entry_record']:
            study = {'schema': 'stewart.interruption-commission/1', 'interruption': {'after': after, 'signal': 'SIGTERM'}}
            self.assertIs(CONTINUED[rehearsal_script(study, {'scenario': 'submitted'})]['held'], True)

    def test_request_cap_control_has_a_subject_only_after_enough_earlier_output(self):
        limits = {'turns': 12, 'input_tokens': 160000, 'output_tokens': 30000}
        def review(reported, estimated):
            return {'placements': [{'usage': {'output_tokens': {'reported': reported, 'estimated': estimated}}},
                                   {'usage': {'output_tokens': {'reported': 400, 'estimated': 0}}}]}
        # 30,000 - 800 leaves the next first request at the 16,000 cap; an estimate of 16,000 does not.
        self.assertEqual(placements.no_subject('reminder-spent-unheld', review(800, 0), limits), ['reset-request-cap'])
        self.assertEqual(placements.no_subject('reminder-spent-unheld', review(800, 16000), limits), [])
        self.assertEqual(placements.no_subject('reminder-spent-unheld', review(14000, 0), limits), ['reset-request-cap'])
        self.assertEqual(placements.no_subject('reminder-spent-unheld', review(14001, 0), limits), [])
        self.assertEqual(placements.no_subject('continue-cap', review(16000, 0), limits),
                         ['changed-interruption-timing', 'changed-interruption-witness', 'repeated-effect-across-placements'])

    def test_signal_timing_is_classified_from_capture_and_attempt_facts(self):
        aborted = {'outcome': 'aborted_by_signal', 'request_written': 'complete'}
        for captured, attempts, expected in [
                (False, [], 'not_captured'), (True, [], 'captured_not_written'),
                (True, [{'outcome': 'aborted_by_signal', 'request_written': 'none'}], 'captured_not_written'),
                (True, [aborted], 'written_unanswered'),
                (True, [{'outcome': 'aborted_by_signal', 'request_written': 'partial'}], 'written_unanswered'),
                (True, [{'outcome': 'response', 'request_written': 'complete'}], 'answered')]:
            with self.subTest(expected=expected):
                self.assertEqual(session.signal_timing(captured, attempts), expected)
                self.assertEqual(verify.signal_timing(captured, attempts), expected)

    def test_snapshot_numbering_refuses_unknown_members(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(next_snapshot(root).name, 'export-0001')
            (root / 'export-0001').mkdir()
            (root / 'export-0003').mkdir()
            self.assertEqual(next_snapshot(root).name, 'export-0004')
            (root / 'notes').mkdir()
            with self.assertRaises(ValueError):
                next_snapshot(root)


class FakeAuditorTests(unittest.TestCase):
    """The fake checks what it is sent against the specification text, then follows its script."""
    materials = {'materials/a.txt': b'alpha\n'}
    question = 'What happens on restart?\n'

    def auditor(self, script, placement=1):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        auditor = Auditor(script, Path(temp.name), self.materials, self.question, 'open-inquiry',
                          packet={'stop_after_seconds': 1}, placement=placement)
        self.addCleanup(auditor.server.server_close)
        return auditor

    def body(self, first, more=()):
        return {'model': 'rehearsal-only', 'max_tokens': 14000, 'system': strict_json(system_bytes({}, 'open-inquiry')),
                'tools': spec.expected_tools('open-inquiry'), 'messages': [first, *more]}

    def reply(self, call, reentry):
        data = {'list': {'materials': [{'source': name} for name in self.materials]},
                'what_am_i_working_with': reentry,
                'read': {'range': [0, 6], 'complete': True, 'text': 'alpha\n', 'cite': None},
                'record_account': {'entry': 'e1.v1.aaaaaa'}, 'record_artifact': {'entry': 'e2.v1.bbbbbb'},
                'prepare': {'prepared': 'pp1.cccccc', 'rendering': {'source': 'rendering'}}}.get(call['name'], {})
        text = json.dumps({'schema': 'stewart.reply/2', 'operation': call['name'], 'outcome': 'completed', 'data': data, 'next': []})
        return {'type': 'tool_result', 'tool_use_id': call['id'], 'content': [{'type': 'text', 'text': text}], 'is_error': False}

    def drive(self, auditor, steps, reentry=None, extra=()):
        """Answer `steps` requests in turn; return the last response and the conversation so far."""
        messages, response = [], None
        for step in range(steps):
            status, response = auditor.respond(self.body(fake.first_message(self.question, auditor.placement), messages))
            self.assertEqual(status, 200)
            results = [self.reply(call, reentry) for call in auditor.calls if any(
                block.get('id') == call['id'] for block in response['content'])]
            messages += [{'role': 'assistant', 'content': response['content']},
                         {'role': 'user', 'content': results + (list(extra) if step == steps - 1 else [])}]
        return response, messages

    def test_continuing_placement_needs_exactly_the_question_and_the_continuation_notice(self):
        second = self.auditor('continue-cap', 2)
        with self.assertRaisesRegex(ValueError, 'first message differs'):
            second.respond(self.body(fake.first_message(self.question, 1)))
        changed = fake.first_message(self.question, 2)
        changed['content'][1]['text'] = spec.CONTINUATION.replace('new conversation', 'new  conversation')
        with self.assertRaisesRegex(ValueError, 'first message differs'):
            second.respond(self.body(changed))
        status, response = second.respond(self.body(fake.first_message(self.question, 2)))
        self.assertEqual([block['name'] for block in response['content']], ['list', 'what_am_i_working_with'])
        first = self.auditor('continue-cap', 1)
        with self.assertRaisesRegex(ValueError, 'first message differs'):
            first.respond(self.body(fake.first_message(self.question, 2)))

    def test_cap_mirror_is_thinking_only_at_the_request_cap(self):
        status, response = self.auditor('continue-cap').respond(self.body(fake.first_message(self.question, 1)))
        self.assertEqual([block['type'] for block in response['content']], ['thinking'])
        self.assertEqual((response['stop_reason'], response['usage']['output_tokens']), ('max_tokens', 14000))

    def test_prose_must_be_followed_by_the_exact_reminder(self):
        reminder = {'type': 'text', 'text': spec.REMINDER}
        auditor = self.auditor('unsubmitted')
        response, messages = self.drive(auditor, 5)
        self.assertEqual(response['stop_reason'], 'end_turn')
        messages[-1]['content'] = [{'type': 'text', 'text': spec.REMINDER + ' '}]
        with self.assertRaisesRegex(ValueError, 'does not carry the exact reminder'):
            auditor.respond(self.body(fake.first_message(self.question, 1), messages))
        auditor = self.auditor('unsubmitted')
        response, messages = self.drive(auditor, 5, extra=[reminder])
        status, again = auditor.respond(self.body(fake.first_message(self.question, 1), messages))
        self.assertEqual(again['stop_reason'], 'end_turn')
        # A reminder nobody drew is refused as well.
        auditor = self.auditor('unsubmitted')
        response, messages = self.drive(auditor, 2, extra=[reminder])
        with self.assertRaisesRegex(ValueError, 'reminder it did not draw'):
            auditor.respond(self.body(fake.first_message(self.question, 1), messages))

    def test_request_after_the_point_is_held_and_never_answered(self):
        auditor = self.auditor('reminder-unused')
        response, messages = self.drive(auditor, 3)
        self.assertEqual([block['name'] for block in response['content']], ['record_account', 'record_artifact'])
        answers = []
        thread = threading.Thread(target=lambda: answers.append(
            auditor.respond(self.body(fake.first_message(self.question, 1), messages))))
        thread.start()
        self.assertTrue(auditor.holding.wait(5))
        self.assertEqual(answers, [])
        auditor.release.set()
        thread.join(5)
        self.assertEqual((answers, auditor.failures), ([None], []))
        # Never released: still no answer, and the rehearsal fails.
        auditor = self.auditor('reminder-unused')
        auditor.packet = {'stop_after_seconds': -30}
        response, messages = self.drive(auditor, 3)
        self.assertIsNone(auditor.respond(self.body(fake.first_message(self.question, 1), messages)))
        self.assertEqual(auditor.failures, ['held request was never released'])

    def test_unheld_control_answers_every_later_request_without_ending_or_withholding(self):
        reminder = {'type': 'text', 'text': spec.REMINDER}
        auditor = self.auditor('reminder-spent-unheld')
        response, messages = self.drive(auditor, 4, extra=[reminder])
        self.assertEqual(response['stop_reason'], 'end_turn')
        for _ in range(3):
            status, response = auditor.respond(self.body(fake.first_message(self.question, 1), messages))
            self.assertEqual(([block['name'] for block in response['content']], response['stop_reason']),
                             (['what_am_i_working_with'], 'tool_use'))
            messages += [{'role': 'assistant', 'content': response['content']},
                         {'role': 'user', 'content': [self.reply(auditor.calls[-1], {})]}]
        self.assertFalse(auditor.holding.is_set())
        self.assertEqual(auditor.failures, [])
        # The first request after the prose must still carry the exact reminder.
        auditor = self.auditor('reminder-spent-unheld')
        response, messages = self.drive(auditor, 4)
        with self.assertRaisesRegex(ValueError, 'does not carry the exact reminder'):
            auditor.respond(self.body(fake.first_message(self.question, 1), messages))
        # Its continuation accepts either accounting of the interrupted request.
        for estimated in [0, 1]:
            auditor = self.auditor('reminder-spent-unheld', 2)
            response, messages = self.drive(auditor, 1, self.reentry(allowances={'turns': {'estimated': estimated}}))
            status, prose = auditor.respond(self.body(fake.first_message(self.question, 2), messages))
            self.assertEqual(prose['stop_reason'], 'end_turn')
        auditor = self.auditor('reminder-spent-unheld', 2)
        response, messages = self.drive(auditor, 1, self.reentry(allowances={'turns': {'estimated': 2}}))
        with self.assertRaisesRegex(ValueError, 'estimated turns differ'):
            auditor.respond(self.body(fake.first_message(self.question, 2), messages))

    def reentry(self, **changes):
        data = {'run': {'number': 2, 'continuing': True}, 'authoring': {'state': 'open', 'ended_by': None},
                'seal': {'state': 'absent', 'actor': None}, 'revision': 2,
                'entries': [{'kind': 'record_account', 'entry': 'e1.v1.aaaaaa'}, {'kind': 'record_artifact', 'entry': 'e2.v1.bbbbbb'}],
                'receipts': [{'run': 1}, {'run': 1}], 'notices_used': {'reminder': True, 'near_limit': False},
                'allowances': {'turns': {'estimated': 1}}}
        data.update(changes)
        return data

    def test_reentry_must_show_what_the_script_recorded_before_the_interruption(self):
        auditor = self.auditor('reminder-spent', 2)
        response, messages = self.drive(auditor, 1, self.reentry())
        status, prose = auditor.respond(self.body(fake.first_message(self.question, 2), messages))
        self.assertEqual(prose['stop_reason'], 'end_turn')
        for changes in [{'notices_used': {'reminder': False, 'near_limit': False}}, {'revision': 0},
                        {'run': {'number': 1, 'continuing': False}}, {'receipts': [{'run': 1}, {'run': 2}]},
                        {'allowances': {'turns': {'estimated': 0}}}, {'entries': []}]:
            with self.subTest(changes=changes):
                auditor = self.auditor('reminder-spent', 2)
                response, messages = self.drive(auditor, 1, self.reentry(**changes))
                with self.assertRaisesRegex(ValueError, 'fake re-entry'):
                    auditor.respond(self.body(fake.first_message(self.question, 2), messages))
        # The control interrupted before any reminder expects the allowance unused.
        auditor = self.auditor('reminder-unused', 2)
        response, messages = self.drive(auditor, 1, self.reentry())
        with self.assertRaisesRegex(ValueError, 'reminder allowance differs'):
            auditor.respond(self.body(fake.first_message(self.question, 2), messages))

    def test_revision_after_continuation_uses_handles_from_reentry(self):
        auditor = self.auditor('continue-entries', 2)
        reentry = self.reentry(notices_used={'reminder': False, 'near_limit': False}, allowances={'turns': {'estimated': 0}})
        response, messages = self.drive(auditor, 3, reentry)
        self.assertEqual([(block['name'], block['input']['entry']) for block in response['content']],
                         [('replace', 'e1.v1.aaaaaa'), ('delete', 'e2.v1.bbbbbb')])


class ContinuationTests(unittest.TestCase):
    """The launcher's gates against a retained root, with a stub for `stewart status`."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name).resolve()
        self.private, self.out = self.work / 'c10-private', self.work / 'out'
        self.root = self.private / AUDIT
        self.binary = self.work / 'stewart'
        self.binary.write_text('#!/bin/sh\ncat "$(dirname "$0")/status.json"\n')
        self.binary.chmod(0o755)
        commission = rehearsal_packet()
        run = next(item for item in commission['runs'] if item['id'] == AUDIT)
        evidence = self.root / 'evidence'
        (evidence / 'input-witness/materials').mkdir(parents=True)
        (evidence / 'input-witness/question.md').write_text('---\nstewart: question/1\n---\nWhat happens?\n')
        (evidence / 'input-witness/materials/a.txt').write_text('alpha\n')
        (self.root / 'home').mkdir()
        log = self.root / 'archive/audits/a1/log'
        log.mkdir(parents=True)
        for number in range(1, 4):
            (log / f'{number}.json').write_bytes(compact(record('reference', {'prev': None, 'n': number})) + b'\n')
        self.head = digest((log / '3.json').read_bytes())
        write_json(self.root / 'operator.json', {'binary': '/bin-in/stewart', 'reference': REFERENCE,
            'home': str(self.root / 'home'), 'local': True, 'audit': AUDIT})
        write_json(evidence / 'specimen.json', {'case': {'id': 'open-ordinary', 'family': 'open-inquiry', 'question': 'What happens?\n'}, 'materials': []})
        write_json(evidence / '07-run.json', {'argv': [], 'exit': 5})
        inputs = [{'path': name, 'bytes': len(read_file(evidence / 'input-witness' / name)),
                   'sha256': file_hash(evidence / 'input-witness' / name)} for name in ['materials/a.txt', 'question.md']]
        write_json(evidence / 'binding.json', {'schema': 'stewart.c10-audit/1', 'commission': commission, 'run': run,
            'family': 'open-inquiry', 'mode': 'rehearse', 'binary_sha256': file_hash(self.binary),
            'input_inventory': inputs, 'destination': str(self.root / 'returns'), 'input_directories': ['materials']})
        (self.work / 'credential-check').mkdir()
        credential_marker(self.work / 'credential-check' / (AUDIT + '.json'), KEY)
        self.out.mkdir()
        self.status = {'schema': 'stewart.reply/2', 'operation': 'status', 'outcome': 'completed', 'data': {
            'headline': {'accepted': 'yes', 'launched': 'yes', 'authoring': {'state': 'open', 'ended_by': None},
                         'seal': {'state': 'absent', 'actor': None}, 'delivered': {'verified': False, 'confirmed': False}, 'closed': 'no'},
            'condition': 'interrupted',
            'runs': {'count': 1, 'held': False, 'holder': None,
                     'last': {'number': 1, 'ending': 'interrupted', 'cause': 'max_tokens', 'recorded_by': 'run'}},
            'allowances': {'turns': {'used': 1, 'reported': 1, 'estimated': 0, 'limit': 12},
                           'input_tokens': {'used': 1000, 'reported': 1000, 'estimated': 0, 'limit': 160000},
                           'output_tokens': {'used': 16000, 'reported': 16000, 'estimated': 0, 'limit': 30000}},
            'closure': None}}
        self.packet = {'schema': 'stewart.c10-continuation/1', 'evidence': '/retained/evidence', 'audit': AUDIT,
            'container': 'stewart-c10-1-1', 'reference': REFERENCE, 'placement': 2, 'max_placements': 2,
            'prior': {'runs': 1, 'last_ending': 'interrupted', 'last_cause': 'max_tokens', 'log_head_sha256': self.head,
                      'usage': {'turns': 1, 'input_tokens': 1000, 'output_tokens': 16000}},
            'model': 'rehearsal-only', 'limits': commission['limits'], 'endpoint': 'loopback-fake', 'proxy': None,
            'interruption': None, 'permitted_request_attempts': 4, 'automatic_continuation': False,
            'stop_after_seconds': 60, 'spending_authority': 'Offline fakes only.',
            'account': {'account_label': None, 'workspace_id': None, 'credential_label': None},
            'bindings': {'qualification_id': None, 'binary_sha256': file_hash(self.binary), 'source_commit': None,
                         'apparatus_sha256': APPARATUS, 'image': None, 'catalog_sha256': None}}
        validate_continuation(self.packet, rehearsal=True)
        self.keys = []

    def attempt(self, key=KEY, *, place=None, packet=None, status=None):
        (self.work / 'status.json').write_text(json.dumps(status or self.status))
        path = self.work / f'packet-{len(list(self.work.glob("packet-*")))}.json'
        path.write_text(json.dumps(packet or self.packet))
        def read_key():
            # The credential is asked for only after readiness was published for this attempt.
            ready = sorted((self.out / 'continuations' / f'{AUDIT}-p2').glob('attempt-*/READY.json'))
            self.keys.append(strict_json(ready[-1].read_bytes()) if ready else None)
            if isinstance(key, Exception):
                raise key
            return key
        def placed(audit, key_, witness, placement, interruption, intent=None):
            (audit.evidence / f'placement-{placement:04d}').mkdir()
            audit.run_attempted = True
            return {'audit': AUDIT, 'placement': 'observed', 'run': placement, 'exit': 0, 'timed_out': False,
                    'caller_reply_lost': False, 'interruption': None, 'automatic_close': None, 'fake_requests': 7,
                    'review_before_close': {'outcome': 'checked', 'ending': 'sealed', 'auditor_submitted': True,
                                            'delivery_verified': True, 'placements': [{}, {}]}}
        families = {'review': {'run': 11, 'passed': 11, 'failed': 0, 'skipped': 0, 'controls': 10, 'controls_fired': 10,
                               'original_unchanged': True, 'not_applicable': []}, 'operations': None, 'reporting': None}
        with mock.patch.object(batch.Audit, 'place', autospec=True, side_effect=place or placed) as start, \
                mock.patch.object(placements, 'locked_export', return_value={'outcome': 'exported'}), \
                mock.patch.object(placements, 'continued_match', return_value=True), \
                mock.patch.object(placements, 'second_start', return_value={'refused': True, 'phase': 'preflight.prior_runs'}), \
                mock.patch.object(placements, 'controls_after', return_value=families):
            result = run_continuation(self.binary, self.private, self.out, path, 'rehearse', read_key,
                                      local=True, witness=self.work / 'witness')
        return result, start

    def folder(self, attempt=1):
        return self.out / 'continuations' / f'{AUDIT}-p2' / f'attempt-{attempt}'

    def test_clean_preflight_publishes_readiness_then_reads_the_key_then_places_once(self):
        result, start = self.attempt()
        ready = {'continuation_preflight_verified': True, 'audit': AUDIT, 'placement': 2, 'attempt': 1}
        self.assertEqual(strict_json((self.folder() / 'READY.json').read_bytes()), ready)
        self.assertEqual(self.keys, [ready])
        start.assert_called_once()
        self.assertEqual(start.call_args.args[2:5], (self.work / 'witness', 2, None))
        self.assertEqual((result['placement_state'], result['failed'], result['outcome'], result['attempt']), ('observed', False, 'passed', 1))
        self.assertEqual(strict_json((self.folder() / 'RESULT.json').read_bytes()), result)
        self.assertFalse((self.folder() / 'FAILURE.json').exists())
        for name in ['mode', 'audit', 'placement', 'prior_observed', 'placement_state', 'exit', 'timed_out', 'interruption',
                     'review', 'automatic_close', 'export', 'stop_reason', 'failed', 'outcome', 'expected_observation']:
            self.assertIn(name, result)
        observed = result['prior_observed']
        self.assertEqual((observed['runs'], observed['lock_held'], observed['log_head']), (1, False, {'record': 'log/3.json', 'sha256': self.head}))
        self.assertEqual(observed['allowance_facts']['remaining'], {'turns': 11, 'input_tokens': 159000, 'output_tokens': 14000})
        self.assertFalse(observed['allowance_facts']['this_placement_ends_limit_reached_before_any_request'])
        self.assertEqual(result['prior_snapshot']['unchanged'], None)
        # The status observation was added under the next unused number; nothing retained was replaced.
        self.assertTrue((self.root / 'evidence/08-status-before-placement.stdout').is_file())

    def test_completed_placement_admits_no_further_attempt(self):
        first, start = self.attempt()
        kept = (self.folder() / 'RESULT.json').read_bytes()
        with self.assertRaises(Refused):
            self.attempt()
        self.assertFalse(self.folder(2).exists())
        self.assertEqual((self.folder() / 'RESULT.json').read_bytes(), kept)

    def test_wrong_key_starts_nothing_and_the_right_key_is_the_next_attempt(self):
        result, start = self.attempt(b'c10-NONFUNCTIONAL-another-key')
        start.assert_not_called()
        self.assertEqual((result['placement_state'], result['failed'], result['credential_checked']), ('not_started', True, False))
        self.assertEqual(result['failure']['phase'], 'credential.differs')
        failure = strict_json((self.folder() / 'FAILURE.json').read_bytes())
        self.assertEqual(set(failure), {'phase', 'error_type', 'scenario', 'private_originals_retained'})
        self.assertNotIn('credential differs', json.dumps(result))
        self.assertTrue((self.folder() / 'READY.json').exists())
        self.assertFalse((self.root / 'evidence/placement-0002').exists())
        again, start = self.attempt()
        start.assert_called_once()
        self.assertEqual((again['attempt'], again['placement_state'], again['failed']), (2, 'observed', False))
        self.assertEqual(self.keys[-1]['attempt'], 2)

    def test_missing_or_invalid_credential_records_not_started(self):
        for key in [ValueError('PRIVATE'), RuntimeError('PRIVATE')]:
            with self.subTest(kind=type(key).__name__):
                self.setUp()
                result, start = self.attempt(key)
                start.assert_not_called()
                self.assertEqual((result['placement_state'], result['failure']['phase']), ('not_started', 'credential.read'))
                self.assertNotIn('PRIVATE', (self.folder() / 'RESULT.json').read_text() + (self.folder() / 'FAILURE.json').read_text())

    def test_each_preflight_difference_refuses_before_readiness_and_credential(self):
        def status(change):
            value = json.loads(json.dumps(self.status))
            change(value['data'])
            return {'status': value}
        def packet(change):
            value = json.loads(json.dumps(self.packet))
            change(value)
            return {'packet': value}
        cases = [
            ('preflight.packet', packet(lambda p: p.update(automatic_continuation=True))),
            ('preflight.packet', packet(lambda p: p['prior'].update(last_ending='sealed'))),
            ('preflight.binary_binding', packet(lambda p: p['bindings'].update(binary_sha256='0' * 64))),
            ('preflight.apparatus_binding', packet(lambda p: p['bindings'].update(apparatus_sha256='0' * 64))),
            ('preflight.audit_binding', packet(lambda p: p.update(reference=REFERENCE + 'x'))),
            ('preflight.audit_binding', packet(lambda p: p['limits'].update(turns=13))),
            ('preflight.rehearsal_inventory', packet(lambda p: p.update(interruption={'after': 'reminder_notice', 'signal': 'SIGTERM'}))),
            ('preflight.prior_runs', status(lambda d: d['runs'].update(count=2))),
            ('preflight.prior_runs', status(lambda d: d['runs']['last'].update(number=2))),
            ('preflight.audit_state', status(lambda d: d['headline'].update(authoring={'state': 'ended', 'ended_by': 'limit'}))),
            ('preflight.audit_state', status(lambda d: d['headline'].update(seal={'state': 'present', 'actor': 'auditor'}))),
            ('preflight.audit_state', status(lambda d: d['headline'].update(closed='unfinished'))),
            ('preflight.audit_state', status(lambda d: d.update(closure={'requested_at': 't'}))),
            ('preflight.audit_state', status(lambda d: d['runs'].update(held=True))),
            ('preflight.audit_state', status(lambda d: d.update(condition='run_active'))),
            ('preflight.prior_ending', status(lambda d: d['runs']['last'].update(cause='signal'))),
            ('preflight.prior_ending', status(lambda d: d['runs']['last'].update(ending=None, cause=None))),
            ('preflight.prior_usage', status(lambda d: d['allowances']['output_tokens'].update(used=0))),
            ('preflight.prior_usage', status(lambda d: d['allowances']['turns'].update(used='unknown'))),
            ('preflight.prior_usage', status(lambda d: d['allowances']['turns'].update(limit=13))),
            ('preflight.prior_log_head', packet(lambda p: p['prior'].update(log_head_sha256='0' * 64))),
        ]
        for phase, change in cases:
            with self.subTest(phase=phase):
                self.setUp()
                result, start = self.attempt(**change)
                start.assert_not_called()
                self.assertEqual(self.keys, [])
                self.assertEqual((result['placement_state'], result['failed'], result['failure']['phase']), ('not_started', True, phase))
                self.assertFalse((self.folder() / 'READY.json').exists())
                self.assertTrue((self.folder() / 'FAILURE.json').exists())
                self.assertFalse((self.root / 'evidence/placement-0002').exists())
                if phase in ['preflight.prior_runs', 'preflight.audit_state', 'preflight.prior_ending', 'preflight.prior_usage']:
                    self.assertIsNotNone(result['prior_observed'])   # a refusal still says what was found

    def test_unbound_usage_and_log_head_are_observed_not_required(self):
        packet = json.loads(json.dumps(self.packet))
        packet['prior'].update(usage=None, log_head_sha256=None)
        result, start = self.attempt(packet=packet)
        start.assert_called_once()
        self.assertEqual(result['prior_observed']['bound_by_packet'], {'usage': False, 'log_head': False})
        self.assertEqual(result['prior_observed']['log_head']['sha256'], self.head)

    def test_changed_retained_input_or_marker_refuses(self):
        (self.root / 'evidence/input-witness/materials/a.txt').write_text('changed\n')
        result, start = self.attempt()
        self.assertEqual(result['failure']['phase'], 'preflight.input_witness')
        self.setUp()
        (self.work / 'credential-check' / (AUDIT + '.json')).unlink()
        result, start = self.attempt()
        self.assertEqual((result['failure']['phase'], result['placement_state']), ('preflight.credential_marker', 'not_started'))
        start.assert_not_called()

    def test_launcher_records_without_a_service_record_stop_later_attempts(self):
        (self.root / 'evidence/placement-0002').mkdir()
        result, start = self.attempt()
        start.assert_not_called()
        self.assertEqual((result['failure']['phase'], result['placement_state']), ('preflight.placement_already_launched', 'not_started'))

    def test_failure_before_the_spawn_is_not_started_and_after_it_unknown(self):
        def before(audit, *args, **kwargs):
            raise OSError('PRIVATE setup failure')
        result, start = self.attempt(place=before)
        self.assertEqual((result['placement_state'], result['failure']['phase'], result['credential_checked']), ('not_started', 'placement', True))
        self.setUp()
        def after(audit, *args, **kwargs):
            audit.run_attempted = True
            write_json(audit.evidence / '09-run.json', {'argv': [], 'exit': -9, 'process_state': 'exited'})
            raise RuntimeError('PRIVATE run did not return JSON')
        result, start = self.attempt(place=after)
        self.assertEqual((result['placement_state'], result['failed']), ('unknown', True))
        self.assertNotIn('PRIVATE', (self.folder() / 'RESULT.json').read_text())
        with self.assertRaises(Refused):
            self.attempt()
        self.setUp()
        def unspawned(audit, *args, **kwargs):
            audit.run_attempted = True
            write_json(audit.evidence / '09-run.json', {'argv': [], 'exit': None, 'process_state': 'not_started'})
            raise FileNotFoundError(2, 'PRIVATE')
        result, start = self.attempt(place=unspawned)
        self.assertEqual(result['placement_state'], 'not_started')
        self.setUp()
        def unrecorded(audit, *args, **kwargs):
            audit.run_attempted = True
            raise OSError('PRIVATE')
        result, start = self.attempt(place=unrecorded)
        self.assertEqual(result['placement_state'], 'unknown')

    def test_interrupt_after_the_spawn_was_attempted_is_recorded_unknown_and_blocks(self):
        def interrupted(audit, *args, **kwargs):
            audit.run_attempted = True
            write_json(audit.evidence / '09-run.json', {'argv': [], 'exit': None, 'process_state': 'unknown'})
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.attempt(place=interrupted)
        kept = strict_json((self.folder() / 'RESULT.json').read_bytes())
        self.assertEqual((kept['placement_state'], kept['failed'], kept['credential_checked'], kept['failure']['phase']),
                         ('unknown', True, True, 'placement'))
        self.assertTrue((self.folder() / 'FAILURE.json').is_file())
        with self.assertRaises(Refused):
            self.attempt()
        self.assertFalse(self.folder(2).exists())
        # Differs only in whether the spawn had been attempted: then nothing can have started.
        self.setUp()
        def early(audit, *args, **kwargs):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.attempt(place=early)
        self.assertEqual(strict_json((self.folder() / 'RESULT.json').read_bytes())['placement_state'], 'not_started')
        again, start = self.attempt()
        self.assertEqual((again['attempt'], again['placement_state']), (2, 'observed'))
        # An interrupt with no record of the command at all proves nothing either.
        self.setUp()
        def unrecorded(audit, *args, **kwargs):
            audit.run_attempted = True
            raise SystemExit(3)
        with self.assertRaises(SystemExit):
            self.attempt(place=unrecorded)
        self.assertEqual(strict_json((self.folder() / 'RESULT.json').read_bytes())['placement_state'], 'unknown')

    def test_tenth_and_later_attempts_follow_in_number_order(self):
        parent = self.out / 'continuations' / f'{AUDIT}-p2'
        good = {'schema': 'stewart.c10-continuation-session/1', 'audit': AUDIT, 'placement': 2, 'placement_state': 'not_started'}
        for number in range(1, 12):
            folder, attempt = claim(self.out, self.packet)
            self.assertEqual((folder, attempt), (parent / f'attempt-{number}', number))
            write_json(folder / 'RESULT.json', good)
        # A gap in the numbering is an unknown membership, whatever its text order.
        (parent / 'attempt-13').mkdir()
        with self.assertRaises(Refused):
            claim(self.out, self.packet)
        (parent / 'attempt-13').rmdir()
        write_json(parent / 'attempt-10/RESULT-copy.json', good)
        (parent / 'attempt-10/RESULT.json').unlink()
        with self.assertRaises(Refused):
            claim(self.out, self.packet)

    def test_only_recorded_not_started_attempts_admit_another(self):
        parent = self.out / 'continuations' / f'{AUDIT}-p2'
        def earlier(value):
            (parent / 'attempt-1').mkdir(parents=True)
            if value is not None:
                (parent / 'attempt-1/RESULT.json').write_text(value if isinstance(value, str) else json.dumps(value))
        good = {'schema': 'stewart.c10-continuation-session/1', 'audit': AUDIT, 'placement': 2, 'placement_state': 'not_started'}
        blocked = [None, 'not json', {**good, 'placement_state': 'unknown'}, {**good, 'placement_state': 'observed'},
                   {**good, 'audit': 'another'}, {**good, 'schema': 'other'}, {'placement_state': 'not_started'}]
        for value in blocked:
            with self.subTest(value=value):
                self.setUp()
                parent = self.out / 'continuations' / f'{AUDIT}-p2'
                earlier(value)
                if value is None:
                    write_json(parent / 'attempt-1/FAILURE.json', {'phase': 'credential.read'})
                with self.assertRaises(Refused):
                    claim(self.out, self.packet)
                self.assertEqual(sorted(path.name for path in parent.iterdir()), ['attempt-1'])
        self.setUp()
        parent = self.out / 'continuations' / f'{AUDIT}-p2'
        earlier(good)
        self.assertEqual(claim(self.out, self.packet), (parent / 'attempt-2', 2))
        write_json(parent / 'attempt-2/RESULT.json', good)
        self.assertEqual(claim(self.out, self.packet)[1], 3)
        (parent / 'notes.txt').write_text('x')
        with self.assertRaises(Refused):
            claim(self.out, self.packet)

    def test_claim_refuses_names_that_are_not_an_audit_placement(self):
        for audit, placement in [('../x', 2), ('Control', 2), (AUDIT, 1), (AUDIT, 5), (AUDIT, True), (AUDIT, '2')]:
            with self.subTest(audit=audit, placement=placement), self.assertRaises(Refused):
                claim(self.out, {'audit': audit, 'placement': placement})
        self.assertFalse((self.out / 'continuations').exists())

    def test_live_packet_must_be_approved_and_rehearsal_model_cannot_go_live(self):
        (self.work / 'status.json').write_text(json.dumps(self.status))
        path = self.work / 'packet-live.json'
        path.write_text(json.dumps(self.packet))
        with mock.patch.object(batch.Audit, 'place', autospec=True) as start:
            result = run_continuation(self.binary, self.private, self.out, path, 'live', lambda: KEY, local=True)
        start.assert_not_called()
        self.assertEqual((result['placement_state'], result['failure']['phase'], result['outcome']), ('not_started', 'preflight.packet', 'incomplete'))
        self.assertNotIn('expected_observation', result)

    def export(self, members):
        folder = self.out / AUDIT / 'export-0001'
        folder.mkdir(parents=True)
        with tarfile.open(folder / 'work.tar', 'w') as archive:
            for name, data in members.items():
                member = tarfile.TarInfo('private/' + name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        write_json(folder / 'EXPORT.json', {'outcome': 'exported', 'archive': {'sha256': file_hash(folder / 'work.tar')}})

    def test_prior_snapshot_members_must_still_be_present_with_the_same_bytes(self):
        root = self.work / 'kept'
        (root / 'evidence').mkdir(parents=True)
        (root / 'evidence/a').write_bytes(b'first')
        (root / 'evidence/b').write_bytes(b'second')
        self.assertIsNone(prior_members(root, self.out / AUDIT)['unchanged'])
        self.export({'evidence/a': b'first', 'evidence/b': b'second'})
        self.assertEqual(prior_members(root, self.out / AUDIT), {'snapshot': 'export-0001',
            'archive_sha256': file_hash(self.out / AUDIT / 'export-0001/work.tar'), 'members': 2, 'missing': 0,
            'changed': 0, 'examples': [], 'unchanged': True})
        (root / 'evidence/c').write_bytes(b'a later placement only adds')
        self.assertTrue(prior_members(root, self.out / AUDIT)['unchanged'])
        (root / 'evidence/a').write_bytes(b'FIRST')
        changed = prior_members(root, self.out / AUDIT)
        self.assertEqual((changed['unchanged'], changed['changed'], changed['missing'], changed['examples']), (False, 1, 0, ['evidence/a']))
        (root / 'evidence/b').unlink()
        self.assertEqual(prior_members(root, self.out / AUDIT)['missing'], 1)
        # A later withheld snapshot has nothing to compare; the newest exported one is still used.
        (self.out / AUDIT / 'export-0002').mkdir()
        write_json(self.out / AUDIT / 'export-0002/EXPORT.json', {'outcome': 'withheld', 'archive': None})
        self.assertEqual(prior_members(root, self.out / AUDIT)['snapshot'], 'export-0001')

    def test_changed_prior_member_withholds_the_next_snapshot(self):
        self.export({'evidence/binding.json': b'not what the root holds'})
        result, start = self.attempt()
        start.assert_called_once()
        self.assertEqual((result['placement_state'], result['stop_reason'], result['export'], result['failed']),
                         ('observed', 'prior_snapshot_members_changed', None, True))
        self.assertEqual(sorted(path.name for path in (self.out / AUDIT).iterdir()), ['export-0001'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
