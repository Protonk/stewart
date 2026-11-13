"""Offline controls for service admission, capture correlation and stopped snapshots."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('service_check', Path(__file__).with_name('service_check.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class Controls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='stewart-service-procedure-')
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def selection(self):
        audit = self.root / 'audit'
        for path in ['log', 'runs/1', 'payload']:
            (audit / path).mkdir(parents=True, exist_ok=True)
        payload = b'Independent supplied claim.\n'
        call = {'jsonrpc': '2.0', 'method': 'tools/call', 'id': 4,
                'params': {'name': 'record_account', 'arguments': {'text': payload.decode()}}}
        call_raw = c.p.compact(call) + b'\n'
        (audit / 'runs/1/call-1.json').write_bytes(call_raw)
        (audit / 'payload/e1.v1.bin').write_bytes(payload)
        edit = {'prev': None, 'action': 'add', 'tool': 'record_account',
                'invocation': {'run': 1, 'tool_use_id': 'mcp-4', 'call': 1}, 'target': None,
                'id': 'e1', 'version': 1, 'kind': 'record_account', 'label': '',
                'payload': {'file': 'payload/e1.v1.bin', 'sha256': c.p.sha(payload), 'size': len(payload)},
                'encoding': None, 'citations': [], 'revision': 1}
        c.save(audit / 'log/1.json', {'kind': 'entry', 'body': edit})
        reply = {'operation': 'record_account', 'outcome': 'completed',
                 'data': {'entry': 'e1.v1.fixture', 'revision': 1}}
        result = {'call': 1, 'call_sha256': c.p.sha(call_raw), 'call_bytes': len(call_raw),
                  'input_sha256': c.p.sha(c.witness.runtime.parse(call_raw).get('params').get('arguments').raw),
                  'tool': 'record_account', 'tool_use_id': 'mcp-4', 'outcome': 'completed',
                  'replay_of': None, 'revision': 1, 'log_record': 'log/1.json', 'is_error': False,
                  'content': [{'type': 'text', 'text': json.dumps(reply)}]}
        c.save(audit / 'runs/1/result-1.json', {'body': result})
        (audit / 'runs/1/runtime-1-mcp.bin').write_bytes(call_raw)
        c.save(audit / 'runs/1/runtime-2-mcp-out.bin',
               {'jsonrpc': '2.0', 'id': 4, 'result': {'content': result['content'], 'isError': False}})
        return audit, payload

    def append_call(self, audit, tool, operands, revision, data, edit=None):
        run = audit / 'runs/1'
        number = len(list(run.glob('result-*.json'))) + 1
        call = {'jsonrpc': '2.0', 'method': 'tools/call', 'id': number + 3,
                'params': {'name': tool, 'arguments': operands}}
        raw = c.p.compact(call) + b'\n'
        (run / ('call-%d.json' % number)).write_bytes(raw)
        log_name = None
        if edit is not None:
            logs = sorted((audit / 'log').glob('*.json'), key=lambda path: int(path.stem))
            edit.update(prev=c.p.sha(logs[-1].read_bytes()), tool=tool, revision=revision,
                        invocation={'run': 1, 'tool_use_id': 'mcp-%d' % (number + 3), 'call': number})
            log_name = 'log/%d.json' % (len(logs) + 1)
            c.save(audit / log_name, {'kind': 'entry', 'body': edit})
        reply = {'operation': tool, 'outcome': 'completed', 'data': data}
        content = [{'type': 'text', 'text': json.dumps(reply)}]
        result = {'call': number, 'call_sha256': c.p.sha(raw), 'call_bytes': len(raw),
                  'input_sha256': c.p.sha(c.witness.runtime.parse(raw).get('params').get('arguments').raw),
                  'tool': tool, 'tool_use_id': 'mcp-%d' % (number + 3), 'outcome': 'completed',
                  'replay_of': None, 'revision': revision, 'log_record': log_name, 'is_error': False, 'content': content}
        c.save(run / ('result-%d.json' % number), {'body': result})
        (run / ('runtime-%d-mcp.bin' % (number * 2 - 1))).write_bytes(raw)
        c.save(run / ('runtime-%d-mcp-out.bin' % (number * 2)),
               {'jsonrpc': '2.0', 'id': number + 3, 'result': {'content': content, 'isError': False}})

    def removed_selection(self):
        audit, payload = self.selection()
        self.append_call(audit, 'delete', {'entry': 'e1.v1.fixture'}, 2,
                         {'removed': {'id': 'e1', 'version': 1}, 'revision': 2, 'already_removed': False},
                         {'action': 'delete', 'target': {'id': 'e1', 'version': 1}})
        return audit, payload

    def test_repeated_delete_keeps_revision_and_empty_selection(self):
        audit, _ = self.removed_selection()
        self.append_call(audit, 'delete', {'entry': 'e1.v1.fixture'}, 2,
                         {'removed': {'id': 'e1', 'version': 1}, 'revision': 2, 'already_removed': True})
        entries, revision, counts = c.capture_selection(audit, {})
        self.assertEqual((entries, revision, counts['completed_calls']), ([], 2, 3))

    def test_repeated_delete_changed_target_refuses(self):
        audit, _ = self.removed_selection()
        self.append_call(audit, 'delete', {'entry': 'e1.v1.fixture'}, 2,
                         {'removed': {'id': 'e2', 'version': 1}, 'revision': 2, 'already_removed': True})
        with self.assertRaisesRegex(ValueError, 'prior removal'):
            c.capture_selection(audit, {})

    def test_repeated_delete_changed_revision_refuses(self):
        audit, _ = self.removed_selection()
        self.append_call(audit, 'delete', {'entry': 'e1.v1.fixture'}, 3,
                         {'removed': {'id': 'e1', 'version': 1}, 'revision': 3, 'already_removed': True})
        with self.assertRaisesRegex(ValueError, 'prior removal'):
            c.capture_selection(audit, {})

    def test_deleted_id_cannot_be_reallocated(self):
        audit, payload = self.removed_selection()
        self.append_call(audit, 'record_account', {'text': payload.decode()}, 3,
                         {'entry': 'e1.v1.reused', 'revision': 3},
                         {'action': 'add', 'id': 'e1', 'version': 1, 'kind': 'record_account',
                          'label': '', 'citations': [], 'encoding': None,
                          'payload': {'file': 'payload/e1.v1.bin', 'sha256': c.p.sha(payload), 'size': len(payload)}})
        with self.assertRaisesRegex(ValueError, 'addition identity'):
            c.capture_selection(audit, {})

    def test_utf8_artifact_capture(self):
        audit, _ = self.selection()
        payload = 'Unverified café report.\n'.encode()
        (audit / 'payload/e2.v1.bin').write_bytes(payload)
        self.append_call(audit, 'record_artifact', {'label': 'Note', 'text': payload.decode()}, 2,
                         {'entry': 'e2.v1.fixture', 'revision': 2},
                         {'action': 'add', 'id': 'e2', 'version': 1, 'kind': 'record_artifact',
                          'label': 'Note', 'citations': None, 'encoding': 'utf-8',
                          'payload': {'file': 'payload/e2.v1.bin', 'sha256': c.p.sha(payload), 'size': len(payload)}})
        entries, revision, _ = c.capture_selection(audit, {})
        self.assertEqual((revision, entries[1].encoding, entries[1].data), (2, 'utf-8', payload))

    def test_exact_selection_and_invariance(self):
        audit, payload = self.selection()
        for _ in range(2):
            entries, revision, counts = c.capture_selection(audit, {})
            self.assertEqual((revision, len(entries), entries[0].data), (1, 1, payload))
            self.assertEqual(counts, {'completed_calls': 1, 'refused_or_failed_calls': 0,
                                     'citations_checked': 0, 'auditor_submitted': False,
                                     'incoming_tool_calls': 1, 'tool_results': 1, 'unresolved_mcp_calls': 0})

    def test_missing_original_frame_refuses(self):
        audit, _ = self.selection()
        (audit / 'runs/1/runtime-1-mcp.bin').write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'original MCP frame'):
            c.capture_selection(audit, {})

    def test_changed_call_refuses(self):
        audit, _ = self.selection()
        (audit / 'runs/1/call-1.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'call binding'):
            c.capture_selection(audit, {})

    def test_changed_payload_refuses(self):
        audit, _ = self.selection()
        (audit / 'payload/e1.v1.bin').write_bytes(b'not the authored bytes')
        with self.assertRaisesRegex(ValueError, 'payload differs'):
            c.capture_selection(audit, {})

    def test_first_free_suffixed_payload(self):
        audit, payload = self.selection()
        (audit / 'payload/e1.v1.bin').rename(audit / 'payload/e1.v1-2.bin')
        log = audit / 'log/1.json'
        value = json.loads(log.read_bytes())
        value['body']['payload']['file'] = 'payload/e1.v1-2.bin'
        log.write_text(json.dumps(value))
        entries, revision, _ = c.capture_selection(audit, {})
        self.assertEqual((revision, entries[0].data), (1, payload))

    def test_suffixed_payload_cannot_name_other_entry_or_escape(self):
        audit, _ = self.selection()
        log = audit / 'log/1.json'
        value = json.loads(log.read_bytes())
        for name in ['payload/e2.v1-2.bin', '../payload/e1.v1-2.bin', 'payload/e1.v1-02.bin', 'payload/e1.v1-1.bin']:
            with self.subTest(name=name):
                value['body']['payload']['file'] = name
                log.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, 'unexpected payload path'):
                    c.capture_selection(audit, {})

    def test_missing_call_does_not_erase_entry(self):
        audit, _ = self.selection()
        (audit / 'runs/1/result-1.json').unlink()
        with self.assertRaisesRegex(ValueError, 'every entry effect'):
            c.capture_selection(audit, {})

    def test_digest_chain_control(self):
        audit, _ = self.selection()
        c.save(audit / 'log/2.json', {'kind': 'run_ended', 'body': {'prev': '0' * 64}})
        with self.assertRaisesRegex(ValueError, 'digest chain'):
            c.capture_selection(audit, {})

    def test_snapshot_preserves_members_and_refuses_links(self):
        source = self.root / 'source'
        source.mkdir()
        (source / 'empty').mkdir()
        (source / 'data').write_bytes(b'exact\0bytes')
        rows = c.snapshot(source, self.root / 'copy')
        self.assertEqual(rows, c.inventory(self.root / 'copy'))
        (source / 'link').symlink_to(source / 'data')
        with self.assertRaisesRegex(ValueError, 'nonregular'):
            c.snapshot(source, self.root / 'refused')
        self.assertFalse((self.root / 'refused').exists())

    def test_missing_or_inexact_authority_starts_nothing(self):
        manifest, raw = {'mode': 'real-harness'}, b'approved exact bytes'
        for digest, extra in [(None, False), ('wrong', True), (c.p.sha(raw), False)]:
            with self.subTest(digest=digest, extra=extra), patch.object(c, 'verify', return_value=(manifest, raw)), \
                    patch.object(c, 'command') as launch:
                with self.assertRaisesRegex(ValueError, 'principal approval'):
                    c.run(self.root, digest, extra)
                launch.assert_not_called()
                self.assertFalse((self.root / 'execution').exists())

    def test_real_packet_cannot_use_rehearsal_entry(self):
        with patch.object(c, 'verify', return_value=({'mode': 'real-harness'}, b'x')), patch.object(c, 'command') as launch:
            with self.assertRaisesRegex(ValueError, 'rehearsal refuses'):
                c.run(self.root, rehearsal=True)
            launch.assert_not_called()

    def test_entered_packet_refuses_before_any_command(self):
        (self.root / 'execution').mkdir()
        with patch.object(c, 'verify', return_value=({'mode': 'real-harness'}, b'x')), \
                patch.object(c, 'frozen_executor'), patch.object(c, 'command') as launch:
            with self.assertRaises(FileExistsError):
                c.run(self.root, c.p.sha(b'x'), True)
            launch.assert_not_called()

    def test_changed_controller_cannot_use_frozen_authority(self):
        with self.assertRaisesRegex(ValueError, 'frozen controller'):
            c.frozen_executor(self.root, {'python': str(Path(sys.executable).resolve())})

    def test_changed_or_missing_execution_capture_refuses(self):
        (self.root / 'capture').write_bytes(b'original')
        c.save(self.root / 'EVIDENCE.json', {'members': c.inventory(self.root)})
        c.execution_evidence(self.root)
        (self.root / 'capture').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'execution evidence'):
            c.execution_evidence(self.root)
        (self.root / 'capture').unlink()
        with self.assertRaisesRegex(ValueError, 'execution evidence'):
            c.execution_evidence(self.root)

    def test_missing_stopping_record_is_not_absence(self):
        with patch.object(c.witness.runtime, 'group_observation') as probe:
            self.assertFalse(c.stopping(self.root, self.root / 'STOPPING.json'))
            probe.assert_not_called()
        self.assertEqual(len(json.loads((self.root / 'STOPPING.json').read_bytes())['diagnostics']), 2)

    def test_present_or_unknown_group_refuses(self):
        run = self.root / 'runs/1'
        run.mkdir(parents=True)
        for role in ('auth', 'model'):
            c.save(run / ('process-' + role + '.json'), {'schema': 'stewart.claude-code.process/1', 'group': 12345, 'role': role})
        for state in ('present', 'unknown', 'absent'):
            with patch.object(c.witness.runtime, 'group_observation', return_value=state):
                self.assertEqual(c.stopping(self.root, self.root / (state + '.json')), state == 'absent')

    def test_close_requires_explicit_review_digest(self):
        (self.root / 'review').mkdir()
        c.save(self.root / 'review/REVIEW.json', {'outcome': 'observed', 'auditor_submitted': True,
                                               'package_review': {'outcome': 'observed'}})
        with patch.object(c, 'verify', return_value=({}, b'x')), patch.object(c, 'command') as launch:
            with self.assertRaisesRegex(ValueError, 'explicit review'):
                c.close(self.root, 'wrong')
            launch.assert_not_called()

    def test_command_timeout_fires_and_fresh_command_still_works(self):
        python = str(Path(sys.executable).resolve())
        good = c.command(self.root, 'positive', [python, '-I', '-B', '-c', "print('complete')"], 5)
        self.assertEqual(good['exit'], 0)
        code = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('partial',flush=True); time.sleep(30)"
        with self.assertRaisesRegex(ValueError, 'observation deadline'):
            c.command(self.root, 'timeout', [python, '-I', '-B', '-c', code], 0.2)
        stopped = json.loads((self.root / 'timeout.result.json').read_bytes())
        self.assertTrue(stopped['timed_out'] and stopped['client_reaped'] and stopped['client_group_absent'])
        self.assertEqual((self.root / 'timeout.stdout').read_bytes(), b'partial\n')
        fresh = c.command(self.root, 'invariance', [python, '-I', '-B', '-c', "print('complete')"], 5)
        self.assertEqual(fresh['exit'], 0)
        self.assertEqual((self.root / 'positive.stdout').read_bytes(), (self.root / 'invariance.stdout').read_bytes())


if __name__ == '__main__':
    unittest.main()
