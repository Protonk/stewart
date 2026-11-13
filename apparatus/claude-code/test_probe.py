"""Offline controls; every subprocess is Python, never Claude."""

import base64
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import shutil
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
        with patch.dict(os.environ, {"LANG": "C", "ANTHROPIC_API_KEY": "synthetic", "ANTHROPIC_BASE_URL": "synthetic", "DYLD_INSERT_LIBRARIES": "", "HTTPS_PROXY": "synthetic"}):
            env = probe.environment(self.root)
            inherited = dict(os.environ)
        self.assertFalse(set(env) & {"ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "DYLD_INSERT_LIBRARIES", "HTTPS_PROXY"})
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(self.root))
        self.assertEqual(env["DISABLE_UPDATES"], "1")
        script = ('import json,os; print(json.dumps({k:os.environ.get(k) for k in '
                  '["LANG","ANTHROPIC_API_KEY","HTTPS_PROXY"]}))')
        def child(environment):
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script],
                                    env=environment, capture_output=True, check=True, timeout=5)
            return json.loads(result.stdout)
        self.assertEqual(child(env), {'LANG': 'C', 'ANTHROPIC_API_KEY': None, 'HTTPS_PROXY': None})
        self.assertEqual(child(inherited), {'LANG': 'C', 'ANTHROPIC_API_KEY': 'synthetic', 'HTTPS_PROXY': 'synthetic'})

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
                 "mcp_servers": [{"name": "probe", "status": "connected"}], "permissionMode": "dontAsk", "plugins": copy.deepcopy(probe.BUILTIN_PLUGINS)}
        probe.validate_event(event)
        event["apiKeySource"] = "ANTHROPIC_API_KEY"
        with self.assertRaises(ValueError):
            probe.validate_event(event)

    def test_plugin_inventory_and_server_errors_are_distinct(self):
        event = {"type": "system", "subtype": "init", "model": probe.MODEL,
                 "tools": sorted(probe.fixture.TOOLS), "apiKeySource": "none", "claude_code_version": probe.pin.VERSION,
                 "mcp_servers": [{"name": "probe", "status": "connected"}], "permissionMode": "dontAsk", "plugins": copy.deepcopy(probe.BUILTIN_PLUGINS)}
        probe.validate_event(event)
        with self.assertRaisesRegex(ValueError, "unexpected plugin inventory"):
            probe.validate_event(dict(event, plugins=[{"name": "cc-plugin-privacy", "path": "builtin"}]))
        with self.assertRaisesRegex(ValueError, "startup reported plugin errors"):
            probe.validate_event(dict(event, plugin_errors=[{"message": "synthetic error"}]))
        with self.assertRaisesRegex(ValueError, "startup reported MCP server errors"):
            probe.validate_event(dict(event, mcp_server_errors=[{"message": "synthetic error"}]))

    def test_witness_clocks_share_origin_across_processes(self):
        code = ("import importlib.util,json,sys,time; "
                "s=importlib.util.spec_from_file_location('fixture',sys.argv[1]); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "time.sleep(float(sys.argv[2])); print(json.dumps(m.observation(kind='clock-control')))")
        for delay in ["0", "0.05"]:
            before = probe.fixture.clock_ns()
            observed = json.loads(subprocess.check_output([sys.executable, "-I", "-B", "-c", code, str(fixture), delay]))
            after = probe.fixture.clock_ns()
            self.assertEqual(observed["clock"], probe.fixture.CLOCK_NAME)
            self.assertNotEqual(observed["observer_pid"], os.getpid())
            self.assertLessEqual(before, observed["time_ns"])
            self.assertLessEqual(observed["time_ns"], after)

    def test_help_is_not_an_inventory_of_hidden_flags(self):
        text = "\n".join(probe.VISIBLE_FLAGS) + "\n--system-prompt[-file]\n"
        probe.check_help(text)
        probe.check_help(text + "\n--max-turns\n--system-prompt-file\n")
        with self.assertRaises(ValueError):
            probe.check_help(text.replace("--restricted", ""))

    def seed_prior(self):
        prior = self.root / "prior"
        prior.mkdir()
        binary = self.root / "never-run-claude"
        binary.write_text("synthetic executable identity; must never launch")
        config = self.root / "harness-config"
        config.mkdir()
        pin_path = self.root / "pin.json"
        probe.write_json(pin_path, {"version": probe.pin.VERSION, "signer": probe.pin.FINGERPRINT,
                         "platform": "darwin-arm64", "binary": str(binary), "sha256": probe.pin.digest(binary)})
        for name, content in [("version", probe.pin.VERSION + " (Claude Code)"), ("help", "\n".join(probe.VISIBLE_FLAGS))]:
            (prior / name).mkdir()
            (prior / name / "stdout.bin").write_text(content)
        state = probe.State(prior)
        state.data.update(binary=str(binary), config=str(config), environment=probe.environment(config),
                          setup_complete=True, live_complete=True, bindings={str(binary): probe.pin.digest(binary)})
        for name, method, logged_in, rc in [("auth-empty", "none", False, 1), ("auth-selected", "claude.ai", True, 0)]:
            (prior / name).mkdir()
            probe.write_json(prior / name / "auth-status.json", {"loggedIn": logged_in, "authMethod": method,
                             "configDirectory": str(prior / "empty-config") if name == "auth-empty" else str(config)})
            state.data["uses"][name] = {"exit": rc, "stop": None, "group_gone": True}
        state.data["uses"]["login"] = {"exit": 0}
        state.data["uses"]["case-1"] = {"exit": 143, "stop": "old refusal", "group_gone": True}
        state.save()
        probe.write_json(prior / "RESULT.json", {"cases": [{"case": 1, "outcome": "failed"}]})
        proposal = self.root / "proposal.md"
        proposal.write_text("Synthetic proposed commission; not launch authority.\n")
        return {"PREVIOUS": prior, "PIN": pin_path, "PROPOSAL": proposal, "RUN": self.root / "run"}

    def remember_work_directory(self, state):
        self.addCleanup(shutil.rmtree, str(Path(state.data["setup_cwd"]).parent))

    def test_preparation_is_offline_preserves_prior_and_never_reuses_slots(self):
        paths = self.seed_prior()
        originals = {p: p.read_bytes() for p in paths["PREVIOUS"].rglob("*") if p.is_file()}
        with patch.multiple(probe, **paths), patch.object(probe.subprocess, "Popen") as spawn, \
             patch.object(probe.sys, "stdout", io.StringIO()):
            probe.prepare()
            state = probe.State(probe.RUN)
            self.remember_work_directory(state)
            self.assertEqual(state.data["uses"], {})
            self.assertIsNone(state.data["approval"])
            probe.bindings(state)
            with self.assertRaises(ValueError):
                probe.prepare()
            for approved, included_only in [(False, True), (True, False)]:
                with self.assertRaises(ValueError):
                    probe.live(state, approved=approved, extra_usage_disabled=included_only)
            spawn.assert_not_called()
        self.assertEqual({p: p.read_bytes() for p in originals}, originals)

    def test_preparation_refuses_failed_prior_auth_before_new_run(self):
        paths = self.seed_prior()
        prior = probe.State(paths["PREVIOUS"])
        prior.data["uses"]["auth-selected"]["group_gone"] = False
        prior.save()
        with patch.multiple(probe, **paths), patch.object(probe.subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(ValueError, "unsuccessful or uncertain"):
                probe.prepare()
            spawn.assert_not_called()
        self.assertFalse(paths["RUN"].exists())

    def rehearse_commission(self, mode):
        paths = self.seed_prior()
        real_supervise = probe.supervise
        calls = []
        def offline_supervise(argv, cwd, env, out, timeout, **kwargs):
            calls.append(argv[1:])
            self.assertEqual(argv[0], str(self.root / "never-run-claude"))
            if argv[1:] == ["auth", "status"]:
                report = {"loggedIn": mode != "auth-conflict", "authMethod": "claude.ai", "configDirectory": env["CLAUDE_CONFIG_DIR"]}
                replacement = [sys.executable, "-I", "-B", "-c", "import sys; print(sys.argv[1])", json.dumps(report)]
            else:
                case_mode = "deny" if out.parent.name == "case-2" else mode
                replacement = [sys.executable, "-I", "-B", str(fake), str(out.parent), case_mode]
                self.assertEqual(argv[argv.index("--max-turns") + 1], "4")
                self.assertEqual(kwargs["delay"], 5 if out.parent.name == "case-1" else 0)
                kwargs["delay"] = 0.1  # Exercise the same supervisor with a short offline wait.
            return real_supervise(replacement, cwd, env, out, timeout, **kwargs)
        with patch.multiple(probe, **paths), patch.object(probe.sys, "stdout", io.StringIO()):
            probe.prepare()
            state = probe.State(probe.RUN)
            self.remember_work_directory(state)
            with patch.object(probe, "supervise", side_effect=offline_supervise):
                if mode == "auth-conflict":
                    with self.assertRaisesRegex(ValueError, "unexpected authentication"):
                        probe.live(state, approved=True, extra_usage_disabled=True)
                else:
                    probe.live(state, approved=True, extra_usage_disabled=True)
                with self.assertRaises(ValueError):
                    probe.live(probe.State(probe.RUN), approved=True, extra_usage_disabled=True)
            result = probe.RUN / "RESULT.json"
            return state, json.loads(result.read_text()) if result.exists() else None, calls

    def test_fresh_commission_auth_then_three_offline_cases(self):
        state, result, calls = self.rehearse_commission("allow")
        self.assertEqual(calls[0], ["auth", "status"])
        self.assertEqual(len(calls), 4)
        self.assertEqual(set(state.data["uses"]), {"auth-selected", "case-1", "case-2", "case-3"})
        self.assertEqual([c["outcome"] for c in result["cases"]], ["observed"] * 3)
        self.assertTrue(state.data["live_complete"])

    def test_fresh_commission_stops_on_additional_plugin(self):
        state, result, calls = self.rehearse_commission("extra-plugin")
        self.assertEqual(len(calls), 2)
        self.assertEqual(set(state.data["uses"]), {"auth-selected", "case-1"})
        self.assertIn("unexpected plugin inventory", state.data["uses"]["case-1"]["stop"])
        self.assertEqual([c["outcome"] for c in result["cases"]], ["failed", "unexercised", "unexercised"])

    def test_fresh_auth_failure_never_starts_a_model_session_or_retries(self):
        state, result, calls = self.rehearse_commission("auth-conflict")
        self.assertEqual(calls, [["auth", "status"]])
        self.assertEqual(set(state.data["uses"]), {"auth-selected"})
        self.assertIsNone(result)

    def test_pinned_plugin_identity_is_exact_but_order_is_irrelevant(self):
        expected = copy.deepcopy(probe.BUILTIN_PLUGINS)
        probe.validate_plugins(expected)
        probe.validate_plugins(list(reversed(expected)))
        for field, value in [("name", "another"), ("source", "cc-plugin-privacy@another"), ("path", "/external")]:
            changed = copy.deepcopy(expected)
            changed[1][field] = value
            with self.assertRaisesRegex(ValueError, "unexpected plugin inventory"):
                probe.validate_plugins(changed)
        for changed in [None, [], expected[:2], expected + [expected[0]], [expected[0]] * 3,
                        [dict(expected[0], extra="unexpected")] + expected[1:]]:
            with self.assertRaisesRegex(ValueError, "unexpected plugin inventory"):
                probe.validate_plugins(changed)


if __name__ == "__main__":
    unittest.main()
