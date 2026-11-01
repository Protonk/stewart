"""Provider-free controls for sanity launch, export and offline review helpers."""
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parent))
import launch
import review
from control import safe_state
from session import Session, export_evidence_state, export_work, failure_details, safe_choice, safe_observation, safe_usage
from session_support import credential_bytes, digest, scan_tree, secret_matches, strict_json, validate_commission, write_json


class LaunchTests(unittest.TestCase):
    def complete_evidence(self, root):
        evidence = root / 'evidence'
        evidence.mkdir()
        write_json(evidence / 'RESULT.json', {'failure': False})
        write_json(evidence / '01-run.json', {'argv': ['/bin-in/stewart', 'run', 'stw1:fixture', '--json', '--key-fd', '3'], 'exit': 0, 'timed_out': False, 'pid': 123})
        write_json(evidence / '02-status-after-run.json', {'argv': ['/bin-in/stewart', 'status', 'stw1:fixture', '--json'], 'exit': 0, 'timed_out': False, 'pid': 124})
        write_json(evidence / '02-status-after-run.stdout', {'data': {'runs': {'held': False, 'count': 1, 'last': {'number': 1, 'ending': 'sealed'}}}})
        audit = root / 'archive/audits/audit'
        (audit / 'log').mkdir(parents=True)
        write_json(audit / 'log/1.json', {'kind': 'run_started', 'body': {'run': 1}})
        write_json(audit / 'log/2.json', {'kind': 'run_ended', 'body': {'run': 1, 'requests': 1, 'attempts': 1}})
        run = audit / 'runs/1'
        (run / 'stage').mkdir(parents=True)
        write_json(run / 'request-1.json', {'request': 1})
        write_json(run / 'attempt-1-1.json', {'kind': 'provider_attempt', 'body': {'request': 1, 'attempt': 1, 'response': None, 'credential_reflection': {'body': False, 'headers': []}}})
        return run

    def packet(self):
        return {'schema': 'stewart.sanity-commission/1', 'model': 'example-model', 'effort': None,
            'limits': {'turns': 12, 'input_tokens': 160000, 'output_tokens': 12000},
            'endpoint': 'https://api.anthropic.com', 'proxy': None, 'max_placements': 1,
            'permitted_request_attempts': 4, 'automatic_continuation': False,
            'stop_after_seconds': 900, 'spending_authority': None,
            'account': {'account_label': None, 'workspace_id': None, 'credential_label': None},
            'bindings': {'qualification_id': None, 'binary_sha256': None, 'source_commit': None, 'submission_sha256': None}}

    def test_credential_bounds_and_no_whitespace_trimming(self):
        self.assertEqual(credential_bytes(b'canary\n'), b'canary')
        self.assertEqual(credential_bytes(b'x' * 4096), b'x' * 4096)
        for bad in [b'', b'\n', b' x', b'x\r\n', b'x\n\n', b'x' * 4097, b'\x7f', b'\xff']:
            with self.subTest(value_length=len(bad)), self.assertRaises(ValueError):
                credential_bytes(bad)

    def test_getpass_cannot_fall_back_to_echo(self):
        def fallback(prompt):
            warnings.warn('cannot control echo', launch.getpass.GetPassWarning)
            return 'should-not-be-read'
        with mock.patch.object(launch.getpass, 'getpass', fallback), self.assertRaises(RuntimeError):
            launch.hidden_credential()

    def test_host_environment_excludes_credentials_and_routing(self):
        with mock.patch.dict(os.environ, {'PATH': '/bin', 'HOME': '/home/test',
                'ANTHROPIC_API_KEY': 'synthetic', 'STEWART_PROVIDER_URL': 'http://127.0.0.1:1',
                'HTTPS_PROXY': 'http://127.0.0.1:2', 'PYTHONPATH': '/tmp/injected'}, clear=True):
            self.assertEqual(launch.host_environment(), {'PATH': '/bin', 'HOME': '/home/test'})

    def test_commission_refuses_fallbacks_and_unbounded_repetition(self):
        validate_commission(self.packet())
        for field, changed in [('endpoint', 'http://127.0.0.1:1'), ('proxy', 'http://localhost:1'),
                ('max_placements', 2), ('automatic_continuation', True), ('model', 'REPLACE-WITH-MODEL'),
                ('stop_after_seconds', 0), ('permitted_request_attempts', 5),
                ('max_placements', True), ('permitted_request_attempts', 4.0)]:
            packet = self.packet()
            packet[field] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_commission(packet)
        packet = self.packet()
        packet['limits']['turns'] = True
        with self.assertRaises(ValueError):
            validate_commission(packet)

    def test_duplicate_commission_keys_are_rejected(self):
        for raw in ['{"model":"first","model":"second"}', '{"limits":{"turns":1,"turns":2}}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)

    def test_tracked_proposal_is_valid_and_unapproved(self):
        value = validate_commission(strict_json((Path(__file__).parent / 'commission-proposal.json').read_bytes()))
        self.assertIsNone(value['spending_authority'])
        self.assertTrue(all(v is None for v in value['account'].values()))
        self.assertTrue(all(v is None for v in value['bindings'].values()))

    def test_live_authority_is_required_before_credential_or_container(self):
        with tempfile.TemporaryDirectory() as folder:
            packet = Path(folder) / 'commission.json'
            raw = (json.dumps(self.packet()) + '\n').encode()
            packet.write_bytes(raw)
            out = Path(__file__).resolve().parents[2] / '.scratch/test-live-must-not-exist'
            argv = ['launch.py', 'live', str(out), '--qualification', 'unused',
                '--commission', str(packet), '--approved-commission', digest(raw)]
            with mock.patch.object(sys, 'argv', argv), mock.patch.object(launch, 'hidden_credential') as hidden, mock.patch.object(launch.subprocess, 'run') as run, redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                launch.main()
            self.assertEqual(stopped.exception.code, 2)
            hidden.assert_not_called()
            run.assert_not_called()
            self.assertFalse(out.exists())

    def test_literal_escaped_mixed_and_truncated_reflections(self):
        key = b'canary-X/Y"Z'
        for content in [key, json.dumps(key.decode()).encode(),
                b'prefix canary-\\u0058\\/Y\\"Z trailing',
                b'{"partial":"' + b''.join(('\\u%04x' % x).encode() for x in key)]:
            with self.subTest(content_length=len(content)):
                self.assertTrue(secret_matches(content, key))
        self.assertFalse(secret_matches(b'an unrelated diagnostic', key))

    def test_scan_detects_cross_chunk_match_and_refuses_symlink(self):
        key = b'canary-long-needle'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'ordinary').write_bytes(b'x' * 65530 + key + b'y' * 100)
            result = scan_tree(root, key)
            self.assertEqual(result['files_with_matches'], 1)
            (root / 'ordinary').write_bytes(b'unchanged non-secret diagnostic')
            self.assertEqual(scan_tree(root, key)['files_with_matches'], 0)
            (root / 'link').symlink_to(root / 'ordinary')
            self.assertEqual(scan_tree(root, key)['errors'], 1)

    def test_scan_refuses_missing_root_and_nonregular_members(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(scan_tree(root / 'absent', b'needle')['errors'], 1)
            (root / 'file').write_bytes(b'ordinary')
            self.assertEqual(scan_tree(root / 'file', b'needle')['errors'], 1)
            os.mkfifo(root / 'fifo')
            self.assertEqual(scan_tree(root, b'needle')['errors'], 1)

    def test_scan_reports_directory_walk_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            def denied(root, *, followlinks, onerror):
                onerror(PermissionError('deliberate unreadable directory'))
                return iter([])
            with mock.patch('session_support.os.walk', denied):
                self.assertEqual(scan_tree(Path(folder), b'needle')['errors'], 1)

    def test_export_control_clean_invariance_and_failure_preserve_original(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / 'private'
            root.mkdir()
            self.complete_evidence(root)
            original = root / 'record'
            original.write_bytes(b'unchanged ordinary evidence')
            for name in ['clean', 'contaminated', 'failure']:
                (base / name).mkdir()
            good = export_work(root, base / 'clean', b'canary-secret')
            self.assertEqual(good['outcome'], 'exported')
            control = root / 'control'
            control.write_bytes(b'canary-secret')
            bad = export_work(root, base / 'contaminated', b'canary-secret')
            self.assertEqual(bad['outcome'], 'withheld')
            self.assertFalse((base / 'contaminated/work.tar').exists())
            self.assertEqual(control.read_bytes(), b'canary-secret')
            self.assertEqual(original.read_bytes(), b'unchanged ordinary evidence')
            failure = export_work(root, base / 'failure', b'another-needle', force_failure=True)
            self.assertEqual(failure['outcome'], 'failed')
            self.assertTrue(original.exists())

    def test_export_requires_complete_witness_and_clean_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertNotEqual(export_evidence_state(root), 'complete')
            run = self.complete_evidence(root)
            self.assertEqual(export_evidence_state(root), 'complete')
            attempt = run / 'attempt-1-1.json'
            original = attempt.read_bytes()
            reflected = json.loads(original)
            reflected['body']['credential_reflection']['body'] = True
            attempt.write_text(json.dumps(reflected))
            self.assertEqual(export_evidence_state(root), 'credential_reflection_recorded')
            attempt.write_bytes(original)
            (run / 'response-9-1.bin').write_bytes(b'orphaned raw body')
            self.assertEqual(export_evidence_state(root), 'unaccounted_capture')
            self.assertTrue((run / 'response-9-1.bin').exists())

    def test_run_observation_distinguishes_status_metadata_and_requires_same_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.complete_evidence(root)
            # Both real command records end in '-run.json'; only the exact
            # numbered run-command filename identifies the launched placement.
            self.assertEqual(len(list((root / 'evidence').glob('*-run.json'))), 2)
            self.assertEqual(export_evidence_state(root), 'complete')
            status = root / 'evidence/02-status-after-run.json'
            original = status.read_bytes()
            changed = json.loads(original)
            changed['argv'][2] = 'stw1:different-audit'
            status.write_text(json.dumps(changed))
            self.assertEqual(export_evidence_state(root), 'mismatched_run_observation')
            status.write_bytes(original)
            self.assertEqual(export_evidence_state(root), 'complete')

    def test_incomplete_response_and_missing_marker_withhold_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = self.complete_evidence(root)
            attempt = run / 'attempt-1-1.json'
            body = json.loads(attempt.read_bytes())
            del body['body']['credential_reflection']
            attempt.write_text(json.dumps(body))
            self.assertEqual(export_evidence_state(root), 'missing_or_malformed_evidence')
            body['body']['credential_reflection'] = {'body': False, 'headers': []}
            body['body']['response'] = {'file': 'response-1-1.bin', 'complete': False, 'bytes': 3, 'sha256': digest(b'abc')}
            (run / 'response-1-1.bin').write_bytes(b'abc')
            attempt.write_text(json.dumps(body))
            self.assertEqual(export_evidence_state(root), 'incomplete_response_evidence')

    def test_omitted_attempt_and_response_cannot_look_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = self.complete_evidence(root)
            end = root / 'archive/audits/audit/log/2.json'
            original = end.read_bytes()
            changed = json.loads(original)
            changed['body']['attempts'] = 2
            end.write_text(json.dumps(changed))
            self.assertEqual(export_evidence_state(root), 'capture_counts_disagree')
            end.write_bytes(original)
            self.assertEqual(export_evidence_state(root), 'complete')

    def test_export_rejects_noninteger_or_nonpositive_record_identities(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = self.complete_evidence(root)
            attempt = run / 'attempt-1-1.json'
            body = json.loads(attempt.read_bytes())
            body['body']['response'] = {'file': 'response-1-1.bin', 'complete': True, 'bytes': 1, 'sha256': digest(b'x')}
            (run / 'response-1-1.bin').write_bytes(b'x')
            attempt.write_text(json.dumps(body))
            self.assertEqual(export_evidence_state(root), 'complete')
            fields = [
                (root / 'evidence/02-status-after-run.stdout', ['data', 'runs', 'count']),
                (root / 'evidence/02-status-after-run.stdout', ['data', 'runs', 'last', 'number']),
                (root / 'archive/audits/audit/log/1.json', ['body', 'run']),
                *[(root / 'archive/audits/audit/log/2.json', ['body', key]) for key in ['run', 'requests', 'attempts']],
                *[(attempt, ['body', key]) for key in ['request', 'attempt']],
                (run / 'request-1.json', ['request']),
                (attempt, ['body', 'response', 'bytes']),
            ]
            for path, keys in fields:
                original = path.read_bytes()
                for bad in [True, False, 1.0, 0, -1, '1']:
                    with self.subTest(path=path.name, keys=keys, bad=bad):
                        changed = json.loads(original)
                        target = changed
                        for key in keys[:-1]:
                            target = target[key]
                        target[keys[-1]] = bad
                        path.write_text(json.dumps(changed) + '\n')
                        self.assertNotEqual(export_evidence_state(root), 'complete')
                path.write_bytes(original)
                self.assertEqual(export_evidence_state(root), 'complete')

    def test_credential_qualification_requires_each_unskipped_release_case(self):
        cases = [{'id': name, 'variants': [{'binary': 'release', 'sabotage': None, 'outcome': 'pass', 'parts_skipped': [], 'skip_reason': None}]} for name in ['credentials.arguments', 'credentials.input', 'credentials.reflection', 'credentials.process']]
        self.assertTrue(launch.credential_cases_qualified({'cases': cases}))
        self.assertFalse(launch.credential_cases_qualified({'cases': cases[:-1]}))
        cases[0]['variants'][0]['parts_skipped'] = ['process observation unavailable']
        self.assertFalse(launch.credential_cases_qualified({'cases': cases}))

    def test_safe_summary_does_not_forward_arbitrary_provider_strings(self):
        self.assertEqual(safe_choice('potential-secret', ['interrupted']), 'unknown')
        self.assertIsNone(safe_usage({'turns': 'potential-secret'}))
        state = safe_state({'outcome': 'completed', 'data': {'ending': 'potential-secret', 'cause': 'potential-secret', 'provider': {'message': 'potential-secret'}}})
        self.assertNotIn('potential-secret', json.dumps(state))

    def test_failure_details_report_safe_phase_type_and_errno_only(self):
        detail = failure_details(PermissionError(13, 'potential-secret', '/potential-secret'), 'command.new', 'submitted')
        self.assertEqual(detail['phase'], 'command.new')
        self.assertEqual(detail['error_type'], 'PermissionError')
        self.assertEqual(detail['errno'], 13)
        self.assertNotIn('potential-secret', json.dumps(detail))
        detail = failure_details(KeyError('potential-secret'), 'new-reply', 'submitted')
        self.assertEqual(detail['error_type'], 'KeyError')
        self.assertNotIn('potential-secret', json.dumps(detail))

    def test_observation_summary_excludes_arbitrary_bytes_and_messages(self):
        value = {'observer_uid': 1001, 'target_uids': [1000] * 4, 'core_limits': ['0', 'potential-secret'],
            'message': 'potential-secret', 'access': {'mem': {'allowed': False, 'errno': 13, 'raw': 'potential-secret'},
                                                   'environ': {'allowed': True, 'raw': 'potential-secret'}}}
        result = safe_observation(value)
        self.assertEqual(result['observer_uid'], 1001)
        self.assertEqual(result['access']['mem'], {'allowed': False, 'errno': 13})
        self.assertEqual(result['core_limits'], ['0', 'unknown'])
        self.assertNotIn('potential-secret', json.dumps(result))

    def test_observer_failure_retains_command_metadata_and_stops_child(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            case = Session.__new__(Session)
            case.binary, case.root, case.evidence = Path(sys.executable), root, root
            case.env = {'PATH': os.environ['PATH'], 'HOME': str(root)}
            case.commission, case.mode, case.index, case.process = {'stop_after_seconds': 60}, 'submitted', 0, None
            case.observe_process = mock.Mock(side_effect=RuntimeError('potential-secret'))
            event, release = mock.Mock(), mock.Mock()
            event.wait.return_value = True
            original_popen = subprocess.Popen
            children = []
            def local_child(*args, **kwargs):
                # This test exercises real child termination as the local user;
                # the UID1000 transition belongs to the Linux rehearsal.
                for key in ['user', 'group', 'extra_groups']:
                    kwargs.pop(key, None)
                child = original_popen(*args, **kwargs)
                children.append(child)
                return child
            try:
                with mock.patch('session.subprocess.Popen', local_child), self.assertRaises(RuntimeError):
                    case.command('run', '-I', '-B', '-c', 'import time; time.sleep(60)', observe=(event, release))
                value = strict_json((root / '01-run.json').read_bytes())
                self.assertEqual(value['process_state'], 'exited')
                self.assertEqual(value['pid'], children[0].pid)
                self.assertEqual(value['exit'], children[0].returncode)
                self.assertIsNotNone(children[0].poll())
                self.assertEqual(value['failure']['phase'], 'process-observation')
                self.assertEqual(value['failure']['error_type'], 'RuntimeError')
                self.assertNotIn('potential-secret', json.dumps(value))
                self.assertTrue((root / '01-run.stdout').exists())
                self.assertTrue((root / '01-run.stderr').exists())
            finally:
                for child in children:
                    if child.poll() is None:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=5)

    def test_observer_control_requires_actual_reads_even_when_prctl_is_unsupported(self):
        for advisory_errno, readable in [(22, True), (22, False), (0, True)]:
            with self.subTest(advisory_errno=advisory_errno, readable=readable), tempfile.TemporaryDirectory() as folder:
                case = Session.__new__(Session)
                case.evidence = Path(folder)
                def control(*args, **kwargs):
                    uid = kwargs['user']
                    initialized = {'uid': uid, 'euid': uid, 'gid': uid, 'dumpable': 1,
                        'pr_set_ptracer_return': -1 if advisory_errno else 0, 'errno': advisory_errno}
                    proc = mock.Mock(pid=uid + 100)
                    proc.stdout = io.BytesIO(json.dumps(initialized).encode() + b'\n')
                    proc.poll.return_value = 0
                    return proc
                def observer(argv, **kwargs):
                    uid, target = kwargs['user'], int(argv[-1])
                    is_control = target == uid + 100
                    access = {name: {'allowed': readable if is_control else name == 'cmdline'}
                              for name in ['cmdline', 'environ', 'maps', 'mem', 'fd']}
                    if is_control:
                        access['mem']['read_bytes'] = 1 if readable else 0
                    else:
                        for name in ['environ', 'maps', 'mem', 'fd']:
                            access[name]['errno'] = 13
                    value = {'observer_uid': uid, 'target_pid': target,
                        'target_uids': [uid if is_control else 1000] * 4,
                        'core_limits': ['0', '0'], 'access': access}
                    return subprocess.CompletedProcess(argv, 0, json.dumps(value).encode(), b'')
                with mock.patch('session.subprocess.Popen', side_effect=control), mock.patch('session.subprocess.run', side_effect=observer) as observations:
                    if readable:
                        case.observe_process(123)
                        self.assertEqual(observations.call_count, 4)
                        index = strict_json((case.evidence / 'process-observation-index.json').read_bytes())
                        self.assertEqual(index['controls_fired'], 2)
                        self.assertTrue(index['inspection_denied'])
                        self.assertEqual([item['errno'] for item in index['control_initializations']], [advisory_errno] * 2)
                    else:
                        with self.assertRaises(RuntimeError):
                            case.observe_process(123)
                        self.assertEqual(observations.call_count, 1)
                        self.assertEqual(case.observer_state['code'], 'control_firing')
                        self.assertFalse((case.evidence / 'process-observation-index.json').exists())
                initialization = strict_json((case.evidence / 'observer-1000-control-init.json').read_bytes())
                self.assertEqual(initialization['errno'], advisory_errno)

    def test_review_detects_altered_export_and_keeps_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            place = root / 'container/submitted'
            place.mkdir(parents=True)
            path = place / 'work.tar'
            with tarfile.open(path, 'w') as archive:
                raw = json.dumps({'argv': ['/bin/stewart', 'status'], 'exit': 0}).encode()
                info = tarfile.TarInfo('private/evidence/01-status.json')
                info.size = len(raw)
                archive.addfile(info, io.BytesIO(raw))
            report = {'mode': 'rehearse', 'outcome': 'passed', 'failures': [], 'scenarios': [],
                'exports': [{'scenario': 'submitted', 'outcome': 'exported', 'scan': {},
                    'archive': {'bytes': path.stat().st_size, 'sha256': digest(path.read_bytes())}}]}
            write_json(root / 'container/RESULT.json', report)
            self.assertEqual(len(review.summarize(root)['operations']), 1)
            with path.open('ab') as stream:
                stream.write(b'deliberate alteration')
            with self.assertRaises(ValueError):
                review.summarize(root)
            self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
