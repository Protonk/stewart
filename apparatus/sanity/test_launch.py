"""Provider-free controls for sanity launch, export and offline review helpers."""
from contextlib import redirect_stderr
import copy
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
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'testdata'))
import acceptance_fixtures as captured_acceptance
import launch
import exercise
import review
from control import safe_state
from session import RequestSeen, Session, export_evidence_state, export_work, failure_details, safe_choice, safe_observation, safe_usage
from session_support import credential_bytes, digest, scan_tree, secret_matches, strict_json, validate_commission, write_json


def complete_evidence(root, placements=1):
    """Exportable records of an audit with PLACEMENTS observed placements, each sealed after one request.

    Returns the paths, relative to ROOT, that belong to the last placement, so
    one alteration can be applied to whichever placement comes last.
    """
    root = Path(root)
    evidence, audit = root / 'evidence', root / 'archive/audits/audit'
    (audit / 'log').mkdir(parents=True)
    for number in range(1, placements + 1):
        own = evidence if number == 1 else evidence / f'placement-{number:04d}'
        own.mkdir(parents=True)
        write_json(own / 'RESULT.json', {'failure': False})
        run_cmd, status = 2 * number - 1, 2 * number
        write_json(evidence / f'{run_cmd:02}-run.json', {'argv': ['/bin-in/stewart', 'run', 'stw1:fixture', '--json', '--key-fd', '3'], 'exit': 0, 'timed_out': False})
        write_json(evidence / f'{status:02}-status-after-run.json', {'argv': ['/bin-in/stewart', 'status', 'stw1:fixture', '--json'], 'exit': 0, 'timed_out': False})
        write_json(evidence / f'{status:02}-status-after-run.stdout', {'data': {'runs': {'held': False, 'count': number, 'last': {'number': number, 'ending': 'sealed'}}}})
        write_json(audit / f'log/{run_cmd}.json', {'kind': 'run_started', 'body': {'run': number}})
        write_json(audit / f'log/{status}.json', {'kind': 'run_ended', 'body': {'run': number, 'requests': 1, 'attempts': 1}})
        run = audit / f'runs/{number}'
        (run / 'stage').mkdir(parents=True)
        write_json(run / 'request-1.json', {'request': 1})
        write_json(run / 'attempt-1-1.json', {'kind': 'provider_attempt', 'body': {'request': 1, 'attempt': 1, 'response': None, 'credential_reflection': {'body': False, 'headers': []}}})
    last = placements
    return {'result': ('evidence' if last == 1 else f'evidence/placement-{last:04d}') + '/RESULT.json',
            'run': f'evidence/{2 * last - 1:02}-run.json', 'later_run': f'evidence/{2 * last + 1:02}-run.json',
            'status': f'evidence/{2 * last:02}-status-after-run.json', 'status_out': f'evidence/{2 * last:02}-status-after-run.stdout',
            'start': f'archive/audits/audit/log/{2 * last - 1}.json', 'end': f'archive/audits/audit/log/{2 * last}.json',
            'dir': f'archive/audits/audit/runs/{last}/', 'next_dir': f'archive/audits/audit/runs/{last + 1}/',
            'attempt': f'archive/audits/audit/runs/{last}/attempt-1-1.json',
            'next_placement': f'evidence/placement-{last + 1:04d}', 'number': last}


def bare_session(root):
    """A Session whose commands run local Python children; nothing is installed or launched."""
    case = Session.__new__(Session)
    case.binary, case.root, case.evidence = Path(sys.executable), Path(root), Path(root)
    case.env = {'PATH': os.environ['PATH'], 'HOME': str(root)}
    case.commission, case.mode, case.index, case.process = {'stop_after_seconds': 60}, 'submitted', 0, None
    case.spawn = subprocess.Popen
    return case


class FakeTransportTests(unittest.TestCase):
    def exchange(self, root, body, *, limit=None, declared=None, path='/v1/messages'):
        """Run the real HTTP handler with memory streams; only socket creation is replaced."""
        root.mkdir()
        with mock.patch.object(exercise, 'HTTPServer') as server:
            provider = exercise.Fake('submitted', root, {}, 'Question')
            handler_type = server.call_args.args[1]
        if limit is not None:
            provider.max_request_bytes = limit
        provider.respond = mock.Mock(return_value=(200, {'content': [], 'stop_reason': 'end_turn'}))
        handler = object.__new__(handler_type)
        handler.path = path
        handler.headers = {'Content-Length': str(len(body) if declared is None else declared),
            'x-api-key': provider.key, 'anthropic-version': exercise.API_VERSION,
            'anthropic-beta': exercise.ANTHROPIC_BETA}
        handler.rfile, handler.wfile = io.BytesIO(body), io.BytesIO()
        handler.send_response = mock.Mock()
        handler.send_header = mock.Mock()
        handler.end_headers = mock.Mock()
        handler.do_POST()
        return provider, handler

    def test_large_body_is_witnessed_exactly_and_small_body_is_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name, body in [('small', b'{"padding":"x"}'),
                               ('large', b'{"padding":"'+b'x'*(1024*1024)+b'"}')]:
                with self.subTest(name=name):
                    provider, handler=self.exchange(root/name,body)
                    self.assertEqual(provider.max_request_bytes,64*1024*1024)
                    handler.send_response.assert_called_once_with(200)
                    provider.respond.assert_called_once_with(json.loads(body))
                    self.assertEqual((root/name/'request-1.json').read_bytes(),body)
                    self.assertEqual(provider.failures,[])

    def test_inclusive_bound_and_over_bound_control(self):
        body=b'{"padding":"'+b'x'*1024+b'"}'
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            accepted, handler=self.exchange(root/'at-bound',body,limit=len(body))
            handler.send_response.assert_called_once_with(200)
            self.assertEqual(accepted.failures,[])
            refused, handler=self.exchange(root/'over-bound',body,limit=len(body)-1)
            handler.send_response.assert_called_once_with(400)
            refused.respond.assert_not_called()
            self.assertEqual(handler.rfile.tell(),0)
            self.assertFalse((root/'over-bound/request-1.json').exists())
            self.assertEqual(refused.failures,['request size outside fake provider bound'])

    def test_incomplete_body_and_wrong_endpoint_are_distinct_refusals(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name, options, reason in [
                ('short', {'declared':3}, 'incomplete fake provider request body'),
                ('path', {'path':'/wrong'}, 'unexpected endpoint'),
                ('empty', {'declared':0}, 'request size outside fake provider bound')]:
                with self.subTest(name=name):
                    provider, handler=self.exchange(root/name,b'{}',**options)
                    handler.send_response.assert_called_once_with(400)
                    provider.respond.assert_not_called()
                    self.assertEqual(provider.failures,[reason])
                    self.assertFalse((root/name/'request-1.json').exists())


class LaunchTests(unittest.TestCase):
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
        with mock.patch.object(launch.getpass, 'getpass', return_value='synthetic-hidden-key'):
            self.assertEqual(launch.hidden_credential(), b'synthetic-hidden-key')
        with mock.patch.object(launch.getpass, 'getpass', fallback), self.assertRaisesRegex(RuntimeError, 'hidden terminal input unavailable'):
            launch.hidden_credential()

    def test_real_hidden_entry_without_a_terminal_refuses_before_reading_stdin(self):
        script = ('import sys; sys.path.insert(0, sys.argv[1]); import launch; '
                  'launch.hidden_credential()')
        canary = b'synthetic-stdin-key\n'
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, canary)
        finally:
            os.close(write_fd)
        try:
            result = subprocess.run(
                [sys.executable, '-I', '-B', '-c', script, str(Path(__file__).parent.resolve())],
                stdin=read_fd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True, timeout=5,
            )
            self.assertEqual(os.read(read_fd, len(canary) + 1), canary)
        finally:
            os.close(read_fd)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'hidden terminal input unavailable; no credential was sent', result.stderr)
        self.assertNotIn(b'synthetic-stdin-key', result.stdout + result.stderr)

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
            value = self.packet()
            value['account'] = {'account_label': 'synthetic-account',
                                'workspace_id': 'synthetic-workspace', 'credential_label': 'synthetic-key'}
            raw = (json.dumps(value) + '\n').encode()
            packet.write_bytes(raw)
            out = Path(__file__).resolve().parents[2] / '.scratch/test-live-must-not-exist'
            argv = ['launch.py', 'live', str(out), '--qualification', 'unused',
                '--commission', str(packet), '--approved-commission', digest(raw)]
            stderr = io.StringIO()
            with mock.patch.object(sys, 'argv', argv), mock.patch.object(launch, 'hidden_credential') as hidden, mock.patch.object(launch.subprocess, 'run') as run, mock.patch.object(launch.subprocess, 'check_output') as checkout, redirect_stderr(stderr), self.assertRaises(SystemExit) as stopped:
                launch.main()
            self.assertEqual(stopped.exception.code, 2)
            self.assertIn("record the principal's bounded spending authorization", stderr.getvalue())
            hidden.assert_not_called()
            run.assert_not_called()
            checkout.assert_not_called()
            self.assertFalse(out.exists())
            # Only authority changes. A sentinel at the next boundary establishes
            # passage through this gate without reaching a credential or container.
            value['spending_authority'] = 'synthetic gate control; no live invocation'
            raw = (json.dumps(value) + '\n').encode()
            packet.write_bytes(raw)
            argv[-1] = digest(raw)
            with mock.patch.object(sys, 'argv', argv), mock.patch.object(launch, 'hidden_credential') as hidden, mock.patch.object(launch.subprocess, 'run') as run, mock.patch.object(launch.subprocess, 'check_output', side_effect=RuntimeError('authority gate passed')) as checkout:
                with self.assertRaisesRegex(RuntimeError, '^authority gate passed$'):
                    launch.main()
            checkout.assert_called_once()
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
        if os.geteuid() == 0:
            self.skipTest('a root process can read mode-000 directories')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            hidden = root / 'unreadable'
            hidden.mkdir()
            (hidden / 'member').write_bytes(b'ordinary evidence')
            self.assertEqual(scan_tree(root, b'needle')['errors'], 0)
            hidden.chmod(0)
            try:
                observed = scan_tree(root, b'needle')
                self.assertEqual(observed['errors'], 1)
                self.assertEqual(observed['files'], 0)
            finally:
                hidden.chmod(0o700)
            self.assertEqual(scan_tree(root, b'needle')['files'], 1)

    def test_export_control_clean_invariance_and_failure_preserve_original(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / 'private'
            root.mkdir()
            complete_evidence(root)
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

    def test_incomplete_evidence_withholds_export_until_completed(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / 'private'
            root.mkdir()
            for name in ['incomplete', 'complete']:
                (base / name).mkdir()
            incomplete = export_work(root, base / 'incomplete', b'synthetic-key')
            self.assertEqual(incomplete['outcome'], 'withheld')
            self.assertEqual(incomplete['reason'],
                'incomplete observation, reflection marker or credential scan; originals remain private')
            self.assertEqual(incomplete['scan']['files_with_matches'], 0)
            self.assertEqual(incomplete['scan']['errors'], 0)
            self.assertEqual(incomplete['evidence_state'], 'missing_or_malformed_evidence')
            self.assertFalse((base / 'incomplete/work.tar').exists())
            complete_evidence(root)
            complete = export_work(root, base / 'complete', b'synthetic-key')
            self.assertEqual(complete['outcome'], 'exported')
            self.assertNotIn('reason', complete)
            self.assertEqual(complete['evidence_state'], 'complete')
            self.assertTrue((base / 'complete/work.tar').is_file())

    def test_export_rejects_noninteger_or_nonpositive_record_identities(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = root / complete_evidence(root)['dir']
            attempt = run / 'attempt-1-1.json'
            body = json.loads(attempt.read_bytes())
            body['body']['response'] = {'file': 'response-1-1.bin', 'complete': True, 'bytes': 1, 'sha256': digest(b'x')}
            (run / 'response-1-1.bin').write_bytes(b'x')
            attempt.write_text(json.dumps(body))
            self.assertEqual(export_evidence_state(root), 'complete')
            fields = [
                (root / 'evidence/02-status-after-run.stdout', ['data', 'runs', 'count'], 'uncertain_writer_state'),
                (root / 'evidence/02-status-after-run.stdout', ['data', 'runs', 'last', 'number'], 'uncertain_writer_state'),
                (root / 'archive/audits/audit/log/1.json', ['body', 'run'], 'invalid_run_identity'),
                *[(root / 'archive/audits/audit/log/2.json', ['body', key], 'invalid_run_counts') for key in ['run', 'requests', 'attempts']],
                *[(attempt, ['body', key], 'invalid_attempt_identity') for key in ['request', 'attempt']],
                (run / 'request-1.json', ['request'], 'incomplete_request_evidence'),
                (attempt, ['body', 'response', 'bytes'], 'incomplete_response_evidence'),
            ]
            for path, keys, expected in fields:
                original = path.read_bytes()
                for bad in [True, False, 1.0, 0, -1, '1']:
                    with self.subTest(path=path.name, keys=keys, bad=bad):
                        changed = json.loads(original)
                        target = changed
                        for key in keys[:-1]:
                            target = target[key]
                        target[keys[-1]] = bad
                        path.write_text(json.dumps(changed) + '\n')
                        self.assertEqual(export_evidence_state(root), expected)
                path.write_bytes(original)
                self.assertEqual(export_evidence_state(root), 'complete')

    def test_credential_qualification_requires_each_unskipped_release_case(self):
        names=['credentials.arguments','credentials.input','credentials.reflection','credentials.process']
        for arch in ('arm64','amd64'):
            original=captured_acceptance.result(arch)
            self.assertTrue(launch.credential_cases_qualified(original))
            reordered=copy.deepcopy(original);reordered['cases'].reverse()
            self.assertTrue(launch.credential_cases_qualified(reordered))
            for name in names:
                for change in ('missing','duplicate','failed','partial-skip','skip-reason','wrong-binary','sabotage'):
                    value=copy.deepcopy(original)
                    entry=captured_acceptance.case(value,name)
                    variant=captured_acceptance.release(value,name)
                    if change=='missing':value['cases'].remove(entry)
                    elif change=='duplicate':value['cases'].append(copy.deepcopy(entry))
                    elif change=='failed':variant['outcome']='fail'
                    elif change=='partial-skip':variant['parts_skipped']=['process observation unavailable']
                    elif change=='skip-reason':variant['skip_reason']='process observation unavailable'
                    elif change=='wrong-binary':variant['binary']='test'
                    elif change=='sabotage':variant['sabotage']='synthetic-control'
                    with self.subTest(arch=arch,case=name,change=change):
                        self.assertFalse(launch.credential_cases_qualified(value))
        # This helper checks the credential cases only. The historical two-skip
        # run still passed those cases; it does not establish whole-run fitness.
        historical=captured_acceptance.result(run='readiness-01')
        self.assertEqual(historical['counts']['cases']['skipped'],2)
        self.assertTrue(launch.credential_cases_qualified(historical))

    def test_safe_summary_does_not_forward_arbitrary_provider_strings(self):
        self.assertEqual(safe_choice('potential-secret', ['interrupted']), 'unknown')
        self.assertIsNone(safe_usage({'turns': 'potential-secret'}))
        state = safe_state({'outcome': 'completed', 'data': {'ending': 'potential-secret', 'cause': 'potential-secret', 'provider': {'message': 'potential-secret'}}})
        self.assertNotIn('potential-secret', json.dumps(state))

    def test_vocabulary_observations_keep_unknowns_and_known_limits(self):
        state = safe_state({'outcome': 'completed', 'data': {
            'headline': {'authoring': {'state': 'ended', 'ended_by': 'limit'},
                         'seal': {'state': 'present', 'actor': 'manager'},
                         'delivered': {'verified': 'unknown'}, 'closed': 'unknown'},
            'runs': {'last_ending': 'limit_reached'},
            'allowances': {'turns': {'used': 'unknown', 'reported': 'unknown', 'estimated': 'unknown', 'limit': 12}},
            'diagnostics': [{'record': 'private', 'cause': 'private'}]}})
        self.assertEqual(state['authoring'], {'state': 'ended', 'ended_by': 'limit'})
        self.assertEqual(state['ending'], 'limit_reached')
        self.assertEqual(state['seal_state'], 'present')
        self.assertEqual(state['seal_actor'], 'manager')
        self.assertEqual(state['delivery_verified'], 'unknown')
        self.assertEqual(state['closed'], 'unknown')
        self.assertEqual(state['allowances']['turns'], {'used': 'unknown', 'reported': 'unknown', 'estimated': 'unknown', 'limit': 12})
        self.assertTrue(state['diagnostics_present'])
        self.assertNotIn('private', json.dumps(state))
        absent = safe_state({'data': {'headline': {'seal': {'state': 'absent', 'actor': None},
                                                  'authoring': {'state': 'open', 'ended_by': None},
                                                  'delivered': {'verified': False}, 'closed': 'no'}}})
        self.assertEqual(absent['seal_state'], 'absent')
        self.assertIsNone(absent['seal_actor'])
        unknown = safe_state({'data': {'headline': {'authoring': {'state': 'unknown', 'ended_by': None},
                                                   'seal': {'state': 'unknown', 'actor': None}}}})
        self.assertEqual(unknown['authoring'], {'state': 'unknown', 'ended_by': None})
        self.assertIsNone(unknown['seal_actor'])
        self.assertEqual(absent['authoring'], {'state': 'open', 'ended_by': None})
        self.assertIs(absent['delivery_verified'], False)
        self.assertIs(absent['closed'], False)

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

    def test_succeeding_observer_releases_and_records_child(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            case = Session.__new__(Session)
            case.binary, case.root, case.evidence = Path(sys.executable), root, root
            case.env = {'PATH': os.environ['PATH'], 'HOME': str(root)}
            case.commission, case.mode, case.index, case.process = {'stop_after_seconds': 60}, 'submitted', 0, None
            case.spawn = subprocess.Popen
            case.observe_process = mock.Mock()
            event, release = mock.Mock(), mock.Mock()
            event.wait.return_value = True
            case.command('run', '-I', '-B', '-c', 'print("completed")', raw=True, observe=(event, release))
            record = strict_json((root / '01-run.json').read_bytes())
            case.observe_process.assert_called_once_with(record['pid'])
            release.set.assert_called_once()
            self.assertEqual(record['exit'], 0)
            self.assertEqual(record['process_state'], 'exited')
            self.assertNotIn('failure', record)
            self.assertEqual((root / '01-run.stdout').read_bytes(), b'completed\n')

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



class ExportStateTests(unittest.TestCase):
    """Each withholding reason fires for the last placement, whether it is the only one or a later one."""
    SIZES = (1, 2)

    @staticmethod
    def change(key, keys, value):
        """Set one field of a last-placement record; a callable VALUE is given that placement's number."""
        def apply(root, last):
            target = root / last[key]
            data = json.loads(target.read_text())
            item = data
            for name in keys[:-1]:
                item = item[name]
            item[keys[-1]] = value(last['number']) if callable(value) else value
            target.write_text(json.dumps(data) + '\n')
        return apply

    @staticmethod
    def remove(*keys):
        return lambda root, last: [(root / last[key]).unlink() for key in keys]

    @staticmethod
    def add(key, name, content=b'orphan'):
        def apply(root, last):
            path = root / last[key] / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return apply

    def test_each_withholding_reason_fires_for_the_last_placement(self):
        def drop_marker(root, last):
            path = root / last['attempt']
            value = json.loads(path.read_text())
            del value['body']['credential_reflection']
            path.write_text(json.dumps(value))
        following = lambda number: number + 1
        def misordered(root, last):
            # As many starts as observations, but the last observation precedes its start.
            (root / last['run']).rename(root / last['later_run'])
        change, remove, add = self.change, self.remove, self.add
        cases = [
            ('complete', lambda root, last: (root / 'evidence/operator-1-status.json').write_text('{}')),   # unrelated (invariance)
            ('procedure_not_complete', change('result', ['failure'], True)),
            ('missing_or_malformed_evidence', remove('result')),
            ('missing_or_malformed_evidence', drop_marker),
            ('missing_run_observation', remove('status', 'status_out')),
            ('missing_run_observation', add('next_placement', 'launch-intent.json', b'{}')),
            ('missing_run_observation', misordered),
            ('mismatched_run_observation', change('run', ['argv', 2], 'stw1:another')),
            ('mismatched_run_observation', change('status', ['argv', 2], 'stw1:another')),
            ('uncertain_process_exit', change('run', ['exit'], -15)),
            ('uncertain_process_exit', change('run', ['timed_out'], True)),
            ('uncertain_writer_state', change('status_out', ['data', 'runs', 'count'], following)),
            ('uncertain_writer_state', change('status_out', ['data', 'runs', 'held'], True)),
            ('uncertain_writer_state', change('status_out', ['data', 'runs', 'last', 'number'], following)),
            ('missing_run_boundary', remove('end')),
            ('invalid_run_identity', change('start', ['body', 'run'], following)),
            ('invalid_run_counts', change('end', ['body', 'requests'], 0)),
            ('capture_counts_disagree', change('end', ['body', 'attempts'], 2)),
            ('unaccounted_capture', add('dir', 'response-9-1.bin')),
            ('credential_reflection_recorded', change('attempt', ['body', 'credential_reflection', 'body'], True)),
            ('missing_attempt_evidence', remove('attempt')),
            ('unknown_run_membership', add('next_dir', 'stage/x', b'')),
        ]
        for size in self.SIZES:
            for expected, alter in cases:
                with self.subTest(placements=size, expected=expected), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    last = complete_evidence(root, size)
                    self.assertEqual(export_evidence_state(root), 'complete')
                    alter(root, last)
                    self.assertEqual(export_evidence_state(root), expected)

    def test_bound_cut_off_body_is_a_complete_observation_only_for_a_stopped_or_failed_attempt(self):
        cut = b'{"id":"msg","content":[{"ty'
        def build(root, size, *, outcome='aborted_by_signal', complete=False, capture=cut, record=True, reflected=False):
            run = root / complete_evidence(root, size)['dir']
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
        for size in self.SIZES:
            for expected, options in cases:
                with self.subTest(placements=size, expected=expected, options=options), tempfile.TemporaryDirectory() as folder:
                    build(Path(folder), size, **options)
                    self.assertEqual(export_evidence_state(Path(folder)), expected)


class RequestSeenTests(unittest.TestCase):
    """The sanity interruption: a signal once the fake provider has seen the request."""
    def test_signal_follows_the_observed_request(self):
        seen = threading.Event()
        seen.set()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(RuntimeError):
                bare_session(root).command('run', '-I', '-B', '-c', 'import time; time.sleep(60)', interrupt=RequestSeen(seen))
            command = strict_json((root / '01-run.json').read_bytes())
        self.assertEqual((command['exit'], command['timed_out'], command['process_state']), (-signal.SIGTERM, False, 'exited'))
        self.assertNotIn('failure', command)

    def test_no_signal_without_the_request_witness(self):
        unseen = mock.Mock()
        unseen.wait.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'interruption witness did not observe the request'):
            RequestSeen(unseen).await_point(mock.Mock(), 60)
        unseen.wait.assert_called_once_with(20)
        self.assertEqual(RequestSeen(unseen).remaining(60), 60)

if __name__ == '__main__':
    unittest.main(verbosity=2)
