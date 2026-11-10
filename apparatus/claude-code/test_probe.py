"""Offline controls; every subprocess is Python, never Claude."""

import base64
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("probe", Path(__file__).with_name("probe.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
fixture = Path(__file__).with_name("fixture.py")
fake = Path(__file__).with_name("fake.py")


class ProbeControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="stewart-probe-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def exercise(self, mode, name="case"):
        case = self.root / name
        case.mkdir()
        result, events, _ = probe.supervise([sys.executable, "-I", "-B", str(fake), str(case), mode],
                         self.root, probe.environment(self.root / "config"), case / "process", 5,
                         payload=b'{"type":"user"}\n', delay=0.1, stream=True)
        return case, result, events

    def test_positive_denial_and_invariance(self):
        for mode, name in [("allow", "positive"), ("deny", "denial"), ("allow", "other-location")]:
            case, result, events = self.exercise(mode, name)
            self.assertEqual(result["exit"], 0, result)
            self.assertIsNone(result["stop"], result)
            self.assertTrue(result["group_gone"])
            self.assertEqual(probe.assessment(case, events, mode == "deny")["outcome"], "observed")
            original = base64.b64decode(probe.records(case / "mcp-in.jsonl")[0]["bytes_b64"])
            self.assertIn(b'"jsonrpc": "2.0", "id": 1', original)
        self.assertEqual(probe.assessment(case, events, True)["outcome"], "failed")

    def test_unexercised_is_not_denial_success(self):
        case, result, events = self.exercise("allow")
        (case / "hook-in.jsonl").unlink()
        self.assertEqual(probe.assessment(case, events, True)["outcome"], "unexercised")

    def test_malformed_stream_stops(self):
        case, result, _ = self.exercise("malformed")
        self.assertIsNotNone(result["stop"])
        self.assertTrue(result["group_gone"])
        self.assertIn(b"{broken", (case / "process/stdout.bin").read_bytes())

    def test_unexpected_tool_stops(self):
        case, result, _ = self.exercise("extra-tool")
        self.assertIn("inventory", result["stop"])
        self.assertTrue(result["group_gone"])

    def test_timeout_kills_a_term_ignoring_process(self):
        code = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('ready',flush=True); time.sleep(30)"
        result, _, _ = probe.supervise([sys.executable, "-I", "-B", "-c", code], self.root, {}, self.root / "timeout", 0.3)
        self.assertIn("wall-clock", result["stop"])
        self.assertEqual(result["exit"], -signal.SIGKILL)
        self.assertTrue(result["group_gone"])

    def test_recorder_failure_still_stops_child(self):
        append = probe.fixture.append
        def fail_capture(path, value):
            if value.get("kind") == "capture":
                raise OSError("witness unavailable")
            return append(path, value)
        with patch.object(probe.fixture, "append", side_effect=fail_capture):
            result, _, _ = probe.supervise([sys.executable, "-I", "-B", "-c", "import time; print('ready',flush=True); time.sleep(30)"],
                                          self.root, {}, self.root / "broken", 0.3)
        self.assertIn("witness unavailable", result["stop"])
        self.assertTrue(result["group_gone"], result)

    def test_unavailable_journal_refuses_before_spawning(self):
        with patch.object(probe.fixture, "append", side_effect=OSError("witness unavailable")):
            with patch.object(probe.subprocess, "Popen") as spawn:
                with self.assertRaises(OSError):
                    probe.supervise(["never-executed"], self.root, {}, self.root / "blocked", 1)
                spawn.assert_not_called()

    def test_timeout_stops_a_descendant_too(self):
        witness = self.root / "descendant.pid"
        code = ("import pathlib,signal,subprocess,sys,time; "
                "c=subprocess.Popen([sys.executable,'-I','-B','-c','import time; time.sleep(30)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(c.pid)); "
                "signal.signal(signal.SIGTERM,lambda s,f:(c.wait(timeout=2),sys.exit(0))); time.sleep(30)")
        result, _, _ = probe.supervise([sys.executable, "-I", "-B", "-c", code, str(witness)],
                                      self.root, {}, self.root / "descendants", 0.5)
        pid = int(witness.read_text())
        try:
            self.assertTrue(result["group_gone"], result)
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
        finally:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_failed_witness_never_yields_successful_tool_reply(self):
        case = self.root / "case"
        case.mkdir()
        (case / "effects.jsonl").mkdir()
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "record_note", "arguments": {"text": "orchard"}}},
        ]
        raw = b"".join((json.dumps(v) + "\n").encode() for v in requests)
        result = subprocess.run([sys.executable, "-I", "-B", str(fixture), "mcp", str(case)], input=raw, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertEqual(len(probe.records(case / "mcp-in.jsonl")), 3)

    def test_failed_hook_witness_denies(self):
        case = self.root / "case"
        case.mkdir()
        (case / "hook-in.jsonl").mkdir()
        result = subprocess.run([sys.executable, "-I", "-B", str(fixture), "hook", str(case)],
                                input=b'{"tool_name":"mcp__probe__record_note"}', capture_output=True)
        self.assertEqual(result.returncode, 2)

    def test_environment_omits_credentials_and_injection(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "synthetic", "ANTHROPIC_BASE_URL": "synthetic", "DYLD_INSERT_LIBRARIES": "synthetic", "HTTPS_PROXY": "synthetic"}):
            env = probe.environment(self.root)
        self.assertFalse(set(env) & {"ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "DYLD_INSERT_LIBRARIES", "HTTPS_PROXY"})
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(self.root))
        self.assertEqual(env["DISABLE_UPDATES"], "1")

    def test_reservation_survives_interruption(self):
        state = probe.State(self.root)
        state.claim("case-1")
        restored = probe.State(self.root)
        with self.assertRaises(ValueError):
            restored.claim("case-1")
        with self.assertRaises(ValueError):
            restored.claim("case-4")
        restored.claim("case-2")

    def test_quota_and_paid_overflow_stop(self):
        for info in [{"status": "rejected"}, {"status": "allowed_warning", "overageEnabled": True}]:
            with self.assertRaises(ValueError):
                probe.validate_event({"type": "rate_limit_event", "rate_limit_info": info})
        probe.validate_event({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed_warning", "overageEnabled": False}})

    def test_group_observation_does_not_treat_denial_as_absence(self):
        with patch.object(probe.os, "killpg", side_effect=[PermissionError(), ProcessLookupError()]):
            self.assertFalse(probe.group_alive(12345))
        with patch.object(probe.os, "killpg", side_effect=PermissionError()):
            with self.assertRaises(PermissionError):
                probe.group_alive(12345)

    def test_api_key_source_refuses(self):
        event = {"type": "system", "subtype": "init", "model": probe.MODEL,
                 "tools": sorted(probe.fixture.TOOLS), "apiKeySource": "none", "claude_code_version": probe.pin.VERSION,
                 "mcp_servers": [{"name": "probe", "status": "connected"}], "permissionMode": "dontAsk", "plugins": []}
        probe.validate_event(event)
        event["apiKeySource"] = "ANTHROPIC_API_KEY"
        with self.assertRaises(ValueError):
            probe.validate_event(event)


if __name__ == "__main__":
    unittest.main()
