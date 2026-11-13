#!/usr/bin/env python3
"""Observe a separately launched harness against the supplied-surface fixture.

This module has no process launcher, signal sender or spending authority. Its
self-test and listener rehearsal use synthetic transcripts and socket peers.
Run with python3 -I -B; see CLAUDE-CODE-OBSERVER.md for the launcher boundary.
"""
from __future__ import annotations

import argparse
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import claude_code_surface as surface
import claude_code as spec
from rawjson import compact

KINDS = ("positive", "closed-gate", "invariance")
TOKEN_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
PLUGINS = [{"name": name, "path": "builtin", "source": name + "@builtin"} for name in (
    "cc-plugin-agents-md", "cc-plugin-privacy", "cc-plugin-plugin-authoring")]
MAX_FRAME = 8 * 1024 * 1024
MAX_CAPTURE = 256 * 1024 * 1024


class ObserverStop(RuntimeError):
    """The launcher must stop its owned process and retain the failed interval."""


class GateFixture(surface.Fixture):
    def __init__(self, owner):
        super().__init__(owner.tools_raw, owner)
        self.owner = owner

    def mcp(self, raw, capture=True):
        with self.owner.lock:
            if capture:
                self.owner.append("mcp-received.bin", raw)
            value = spec.mcp_message_loads(raw)
            self.active = self.owner.gate_open()
            if value.get("method") == "tools/call" and "id" in value:
                self.owner.calls.append(value)
                name = (value.get("params") or {}).get("name")
                if name not in self.names:
                    self.owner.fail("MCP call named an unpinned tool")
                if self.owner.valid_init and self.owner.kind == "closed-gate":
                    self.owner.fail("MCP tools/call reached the fixture despite the hook-denial comparison")
                self.active = self.owner.gate_open()
            result = super().mcp(raw, capture=False)
            if (value.get("method") == "initialize" and result
                    and spec.mcp_message_loads(result).get("result") == spec.surface_document()["mcp_initialize"]):
                self.owner.handshake = True
            if value.get("method") == "tools/list" and result and "result" in spec.mcp_message_loads(result):
                self.owner.inventory = True
            return result


class CaseObserver:
    def __init__(self, prepared_inputs, case_id, kind, workspace, evidence_dir):
        if kind not in KINDS:
            raise ValueError("unknown supplied-surface case kind")
        self.inputs, self.workspace, self.root = map(Path, (prepared_inputs, workspace, evidence_dir))
        if not all(path.is_absolute() for path in (self.inputs, self.workspace, self.root)):
            raise ValueError("observer paths must be absolute")
        if self.workspace.is_relative_to(HERE.parent.parent):
            raise ValueError("harness workspace must be outside the project ancestry")
        self.case_id, self.kind = case_id, kind
        self.root.mkdir(mode=0o700)
        (self.root / "inputs").mkdir()
        for path in sorted(self.inputs.iterdir()):
            if path.is_symlink() or not path.is_file():
                raise ValueError("prepared inputs must be regular files")
            (self.root / "inputs" / path.name).write_bytes(path.read_bytes())
        self.inputs = self.root / "inputs"
        self.launch_raw = (self.inputs / "launch.json").read_bytes()
        self.launch = spec.transport_loads(self.launch_raw)
        self.surface_raw = (self.inputs / "surface.json").read_bytes()
        self.tools_raw = (self.inputs / "tools.json").read_bytes()
        case = spec.transport_loads((self.inputs / "case.json").read_bytes())
        self.family, self.model = case["family"], case["model"]
        self.writer = spec.transport_loads((self.inputs / "writer.json").read_bytes())
        self.expected = spec.filled_launch(self.writer["path"], str(self.workspace), self.launch, self.family, self.model)
        self.input_raw = (self.inputs / "input.jsonl").read_bytes()
        self.bindings = {"launch_sha256": spec.sha(self.launch_raw), "surface_sha256": spec.sha(self.surface_raw),
                         "tools_sha256": spec.sha(self.tools_raw), "model": self.model}
        self.lock = threading.RLock()
        self.errors, self.notes, self.calls, self.hooks, self.events, self.usage = [], [], [], [], [], []
        self.valid_init, self.init, self.result_count = False, None, 0
        self.handshake = self.inventory = self.launch_observed = self.input_observed = False
        self.eof = {"stdout": False, "stderr": False}
        self.stream_bytes = {"stdout": 0, "stderr": 0}
        self.stream_hash = {name: hashlib.sha256() for name in self.stream_bytes}
        self.pending, self.capture_bytes = bytearray(), 0
        self.stopping = threading.Event()
        self.listeners, self.connections, self.threads = [], [], []
        self.peer_eof = {}
        self.finished = False
        self.started_at = surface.utc_now()
        self.fixture = GateFixture(self)
        expected_tools = spec.mcp_tools(compact(spec.expected_tools(self.family)))
        if spec.parse(self.launch_raw).raw != self.launch_raw or self.surface_raw != spec.SURFACE or self.tools_raw != expected_tools:
            raise ValueError("prepared launch/surface/tool bytes differ from the frozen specification")
        first = spec.transport_loads(self.input_raw)
        expected_input = spec.surface_document()["input"]
        expected_input["message"]["content"] = (self.inputs / "question.txt").read_text()
        if first != expected_input or not self.input_raw.endswith(b"\n"):
            raise ValueError("first input differs from the exact question and pinned input shape")
        expected_system = spec.RUNTIME_ORIENTATION + "\n\n" + spec.FAMILY_TEXT[self.family]
        if (self.inputs / "system.txt").read_bytes() != expected_system.encode():
            raise ValueError("prepared system prompt differs from the pinned text")
        for member, expected in (("settings.json", self.expected["settings"]), ("mcp.json", self.expected["mcp_config"]),
                                 ("environment.json", self.expected["environment"]), ("argv.json", self.expected["model_argv"])):
            if spec.transport_loads((self.inputs / member).read_bytes()) != expected:
                raise ValueError("prepared supplied surface differs: " + member)
        self.supplied_bytes = {member: (self.inputs / member).read_bytes()
                               for member in ("settings.json", "mcp.json", "system.txt")}
        for name in self.stream_bytes:
            (self.root / (name + ".bin")).write_bytes(b"")

    def append(self, name, raw):
        with self.lock:
            if self.capture_bytes + len(raw) > MAX_CAPTURE:
                self.fail("observer capture bound exceeded; interval incomplete")
                raise ObserverStop(self.errors[-1])
            with (self.root / name).open("ab", buffering=0) as stream:
                if stream.write(raw) != len(raw):
                    raise OSError("incomplete observer witness: " + name)
            self.capture_bytes += len(raw)

    def event(self, kind, **details):
        self.append("events.jsonl", compact({"event": kind, "observer_pid": os.getpid(),
            "time_ns": time.clock_gettime_ns(surface.CLOCK_ID), "clock": surface.CLOCK_NAME, **details}) + b"\n")

    def fail(self, reason):
        with self.lock:
            if reason not in self.errors:
                self.errors.append(reason)
            self.fixture.active = False

    def check_stop(self):
        with self.lock:
            if self.errors:
                raise ObserverStop(self.errors[0])

    def gate_open(self):
        return self.valid_init and self.kind != "closed-gate" and not self.errors and not self.stopping.is_set()

    def record_launch(self, record):
        """Record what the separate launcher submitted, not child-internal state.

        Keys: argv, env, cwd, executable_sha256, files_sha256. The last object
        has settings.json/mcp.json/system.txt digests at the launch workspace.
        """
        surface.save(self.root / "launch-observed.json", record)
        expected_files = {name: spec.sha(raw) for name, raw in self.supplied_bytes.items()}
        valid = (record.get("argv") == [self.launch["executable"]] + self.expected["model_argv"]
                 and record.get("env") == self.expected["environment"] and record.get("cwd") == str(self.workspace)
                 and record.get("executable_sha256") == self.launch["sha256"] and record.get("files_sha256") == expected_files)
        valid = valid and all(spec.sha((self.workspace / name).read_bytes()) == digest for name, digest in expected_files.items())
        self.launch_observed = valid
        if not valid:
            self.fail("actual launch or supplied-file binding differs")
        self.check_stop()

    def record_input(self, attempted, confirmed_prefix):
        self.append("input-attempted.bin", attempted)
        self.append("input-confirmed.bin", confirmed_prefix)
        self.input_observed = attempted == self.input_raw and confirmed_prefix == attempted
        if not self.input_observed:
            self.fail("first input differs or was only partially written")
        self.check_stop()

    def feed(self, raw):
        self._feed("stdout", raw)

    def feed_stderr(self, raw):
        self._feed("stderr", raw)

    def _feed(self, channel, raw):
        self.check_stop()
        if self.eof[channel]:
            self.fail("bytes arrived after observed EOF: " + channel)
            self.check_stop()
        try:
            self.append(channel + ".bin", raw)
            self.stream_bytes[channel] += len(raw)
            self.stream_hash[channel].update(raw)
            if not self.launch_observed:
                raise ValueError("stream arrived without a validated launch record")
            if channel == "stdout":
                self.pending.extend(raw)
                while b"\n" in self.pending:
                    line, _, rest = bytes(self.pending).partition(b"\n")
                    self.pending[:] = rest
                    if len(line) > MAX_FRAME:
                        raise ValueError("harness frame bound exceeded")
                    self._event(spec.transport_loads(line))
                if len(self.pending) > MAX_FRAME:
                    raise ValueError("incomplete harness frame exceeded bound")
        except (ValueError, OSError, TypeError, KeyError) as error:
            self.fail("harness observation failed: " + str(error))
        self.check_stop()

    def _event(self, value):
        if not isinstance(value, dict):
            raise ValueError("harness event must be an object")
        self.event("harness-event", type=value.get("type"), subtype=value.get("subtype"))
        self.events.append((value.get("type"), value.get("subtype")))
        if value.get("parent_tool_use_id") is not None:
            raise ValueError("delegated session observed")
        if self.init and value.get("session_id", self.init["session_id"]) != self.init["session_id"]:
            raise ValueError("harness session changed")
        if value.get("type") == "system" and value.get("subtype") == "init":
            if self.init is not None:
                raise ValueError("repeated startup event")
            self.init = value
            names = ["mcp__stewart__" + item["name"] for item in json.loads(self.tools_raw)]
            tools = value.get("tools")
            plugins = value.get("plugins")
            servers = value.get("mcp_servers")
            if (value.get("claude_code_version") != self.launch["version"] or value.get("model") != self.model
                    or value.get("apiKeySource") != "none" or value.get("permissionMode") != "dontAsk"
                    or not isinstance(tools, list) or len(tools) != len(names) or set(tools) != set(names)
                    or not isinstance(plugins, list) or len(plugins) != 3 or any(plugins.count(p) != 1 for p in PLUGINS)
                    or not isinstance(servers, list) or len(servers) != 1 or not isinstance(servers[0], dict)
                    or servers[0].get("name") != "stewart" or servers[0].get("status") != "connected"
                    or value.get("plugin_errors") or value.get("mcp_server_errors")
                    or not isinstance(value.get("session_id"), str) or not value["session_id"]):
                raise ValueError("startup inventory, route, model, version or session does not match")
            self.valid_init = True
            self.fixture.active = self.gate_open()
        if value.get("type") == "system" and value.get("subtype") in {
                "api_retry", "plugin_install", "task_started", "background_tasks_changed"}:
            raise ValueError("forbidden harness event: " + value["subtype"])
        if value.get("type") == "system" and value.get("subtype") == "compact_boundary":
            raise ValueError("compaction is outside this one-input supplied-surface comparison")
        if value.get("type") == "rate_limit_event":
            info = value.get("rate_limit_info")
            if not isinstance(info, dict):
                raise ValueError("malformed rate-limit observation")
            if info.get("status") == "rejected" or info.get("overageEnabled") is True or info.get("isUsingOverage") is True:
                raise ValueError("quota rejected or paid extra usage enabled/in use")
        if value.get("type") == "assistant":
            message = value.get("message") or {}
            if not isinstance(message, dict) or not isinstance(message.get("content", []), list):
                raise ValueError("malformed assistant message")
            if message.get("model") not in {self.model, "<synthetic>"}:
                raise ValueError("assistant model missing or different")
            for block in message.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") not in {
                        "mcp__stewart__" + name for name in self.fixture.names}:
                    raise ValueError("assistant attempted an unpinned tool")
        if value.get("type") == "result":
            self.result_count += 1
            self.usage.append(value)
            if value.get("is_error") or self.result_count > 1:
                raise ValueError("error or repeated final result")

    def finish_stream(self, channel="stdout"):
        if channel not in self.eof:
            raise ValueError("unknown model stream")
        self.eof[channel] = True
        if channel == "stdout" and self.pending:
            self.fail("unterminated harness stdout frame retained")
        self.check_stop()

    def _mcp_connection(self, connection):
        pending = bytearray()
        self.peer_eof[id(connection)] = False
        try:
            while not self.stopping.is_set():
                raw = connection.recv(65536)
                if not raw:
                    self.peer_eof[id(connection)] = True
                    if pending:
                        raise ValueError("unterminated MCP frame retained")
                    return
                self.append("mcp-received.bin", raw)
                pending.extend(raw)
                if len(pending) > MAX_FRAME:
                    raise ValueError("MCP frame bound exceeded")
                while b"\n" in pending:
                    line, _, rest = bytes(pending).partition(b"\n")
                    pending[:] = rest
                    reply = self.fixture.mcp(line + b"\n", capture=False)
                    if reply is not None:
                        connection.sendall(reply)
                    self.check_stop()
        except (OSError, ValueError, TypeError, KeyError, ObserverStop) as error:
            if not self.stopping.is_set():
                self.fail("MCP observer failed: " + str(error))
        finally:
            if pending:
                self.fail("partial MCP frame retained at connection end")
            if not self.peer_eof[id(connection)]:
                self.fail("MCP peer EOF unobserved; capture may be incomplete")
            connection.close()

    def _hook_connection(self, connection, number):
        prefix = "hook-%04d" % number
        raw = bytearray()
        self.peer_eof[id(connection)] = False
        try:
            self.append(prefix + "-received.bin", b"")
            while not self.stopping.is_set():
                chunk = connection.recv(65536)
                if not chunk:
                    self.peer_eof[id(connection)] = True
                    break
                self.append(prefix + "-received.bin", chunk)
                raw.extend(chunk)
                if len(raw) > MAX_FRAME:
                    raise ValueError("hook input bound exceeded")
            if not self.peer_eof[id(connection)]:
                raise ValueError("hook peer EOF unobserved; capture may be incomplete")
            value = spec.transport_loads(bytes(raw))
            if not isinstance(value, dict):
                raise ValueError("hook input must be an object")
            with self.lock:
                tool = value.get("tool_name")
                valid = (isinstance(value.get("tool_use_id"), str) and bool(value["tool_use_id"])
                         and self.valid_init and value.get("session_id") == self.init["session_id"])
                if not valid:
                    self.fail("hook attempt cannot be associated with the validated session")
                if tool not in {"mcp__stewart__" + name for name in self.fixture.names}:
                    self.fail("hook attempted an unpinned tool")
                allow = self.gate_open()
                reply = compact(spec.surface_document()["hook_replies"]["allow" if allow else "deny"]) + b"\n"
                attempt = {"number": number, "input": value, "allowed": allow, "startup_valid": self.valid_init,
                           "reply_written": False, "origin": "fixture socket peer"}
                self.hooks.append(attempt)
                self.append(prefix + "-supplied.bin", reply)
            connection.sendall(reply)
            attempt["reply_written"] = True
            self.event("hook-reply-written", number=number, allowed=allow, origin=attempt["origin"])
        except (OSError, ValueError, TypeError, KeyError) as error:
            if not self.stopping.is_set():
                self.fail("hook observer failed: " + str(error))
        finally:
            if not self.peer_eof[id(connection)]:
                self.fail("hook peer EOF unobserved; capture may be incomplete")
            connection.close()

    def attach_mcp(self, connection):
        self._attach(self._mcp_connection, connection)

    def attach_hook(self, connection):
        self._attach(self._hook_connection, connection, len([t for t in self.threads if t.name.startswith("hook-")]) + 1)

    def _attach(self, handler, connection, *args):
        self.connections.append(connection)
        name = "hook-%d" % args[0] if args else "mcp-peer"
        thread = threading.Thread(target=handler, args=(connection, *args), daemon=True, name=name)
        self.threads.append(thread)
        thread.start()

    def start_listeners(self):
        """Bind only the fixture endpoints. The separate launcher starts children."""
        if len(os.fsencode(str(self.workspace))) > 96:
            raise ValueError("fixture workspace is too long for portable Unix socket paths")
        if self.workspace.is_relative_to(self.root) or self.root.is_relative_to(self.workspace):
            raise ValueError("sockets must remain outside the observation directory")
        def accept_loop(listener, endpoint):
            count = 0
            while not self.stopping.is_set():
                try:
                    connection, _ = listener.accept()
                except socket.timeout:
                    continue
                except OSError as error:
                    if not self.stopping.is_set():
                        self.fail("fixture accept failed: " + str(error))
                    return
                count += 1
                if endpoint == "m":
                    if count > 1:
                        connection.close()
                        self.fail("second MCP relay connection")
                    else:
                        self.attach_mcp(connection)
                else:
                    self.attach_hook(connection)
        for endpoint in ("m", "h"):
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.listeners.append(listener)
            listener.bind(str(self.workspace / endpoint))
            listener.listen(8)
            listener.settimeout(0.1)
            thread = threading.Thread(target=accept_loop, args=(listener, endpoint), daemon=True, name="listener-" + endpoint)
            self.threads.append(thread)
            thread.start()
        self.event("listeners-ready", workspace=str(self.workspace))
        return {name: str(self.workspace / name) for name in ("m", "h")}

    def close(self, drain=False):
        if drain:
            # The launcher has observed the entire child group gone. Let socket
            # readers reach the resulting EOF before cancelling their reads.
            deadline = time.monotonic() + 1
            for thread in list(self.threads):
                if not thread.name.startswith("listener-"):
                    thread.join(timeout=max(0, deadline - time.monotonic()))
            if any(thread.is_alive() for thread in self.threads if not thread.name.startswith("listener-")):
                self.fail("socket drain incomplete after process stopping")
        self.stopping.set()
        self.fixture.active = False
        for stream in self.listeners + self.connections:
            try:
                stream.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            stream.close()
        deadline = time.monotonic() + 0.5
        for thread in self.threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))
        if any(thread.is_alive() for thread in self.threads):
            self.fail("fixture observer thread stopping is unobserved")

    def finish(self, process_result, sanitized_auth_receipt):
        """Call after the launcher has stopped/reaped the group and reported EOF."""
        self.close(drain=process_result.get("group_gone") is True)
        auth = sanitized_auth_receipt
        valid_auth = (isinstance(auth, dict) and set(auth) == {"loggedIn", "authMethod", "configDirectory"}
                      and auth.get("loggedIn") is True and auth.get("authMethod") == "claude.ai"
                      and auth.get("configDirectory") == self.launch["config_directory"])
        # Reject extra fields without persisting them: authentication raw output
        # and unallowlisted fields never enter this observer's evidence.
        if valid_auth:
            surface.save(self.root / "authentication.json", auth)
        else:
            self.fail("sanitized authentication receipt differs or has extra members")
        surface.save(self.root / "process-result.json", process_result)
        stopped = process_result.get("group_gone") is True and process_result.get("guard_reaped") is True
        if not stopped:
            self.fail("owned process-group stopping is unobserved")
        if process_result.get("exit") != 0 or type(process_result.get("exit")) is not int:
            self.fail("harness did not exit successfully")
        if process_result.get("stop") is not None or process_result.get("guard_reason") != "worker-exit":
            self.fail("controller or watchdog stopped the invocation")
        if self.result_count != 1:
            self.fail("one complete final result was not observed")
        for channel in self.eof:
            if not self.eof[channel] or (process_result.get("stream_eof") or {}).get(channel) is not True:
                self.fail("stream EOF unobserved: " + channel)
            if ((process_result.get("capture_bytes") or {}).get(channel) != self.stream_bytes[channel]
                    or (process_result.get("capture_sha256") or {}).get(channel) != self.stream_hash[channel].hexdigest()):
                self.fail("launcher/observer capture differs: " + channel)
        if (process_result.get("input_bytes_sent") != len(self.input_raw)
                or process_result.get("input_prefix_sha256") != spec.sha(self.input_raw) or not self.input_observed):
            self.fail("confirmed input transmission differs")
        for member in ("settings.json", "mcp.json", "system.txt"):
            try:
                same = ((self.workspace / member).read_bytes() == self.supplied_bytes[member]
                        and (self.inputs / member).read_bytes() == self.supplied_bytes[member])
            except OSError:
                same = False
            if not same:
                self.fail("supplied file changed during the observation: " + member)
        effects_path = self.root / "effects.jsonl"
        effects = [spec.transport_loads(line) for line in effects_path.read_bytes().splitlines()] if effects_path.exists() else []
        target_hooks = [h for h in self.hooks if h["input"].get("tool_name") == "mcp__stewart__record_account"
                        and h["input"].get("tool_input") == {"text": surface.MARKER} and h["startup_valid"] and h["reply_written"]]
        target_calls = [v for v in self.calls if (v.get("params") or {}).get("name") == "record_account"
                        and (v.get("params") or {}).get("arguments") == {"text": surface.MARKER}]
        if not target_hooks:
            comparison = "unexercised"
        elif self.kind == "closed-gate":
            comparison = "observed" if all(not h["allowed"] for h in target_hooks) and not self.calls and not effects else "failed"
        else:
            comparison = "observed" if len(target_hooks) == len(target_calls) == len(effects) == 1 and target_hooks[0]["allowed"] and effects == [
                {"tool": "record_account", "arguments": {"text": surface.MARKER}}] else "failed"
        if comparison == "failed":
            self.fail("attempt/denial/effect comparison differs")
        self.finished = True
        latest_usage = None
        for reported in self.usage:
            usage = reported.get("usage")
            turns = reported.get("num_turns")
            if (isinstance(usage, dict) and type(turns) is int and turns >= 0
                    and all(type(usage.get(name)) is int and usage[name] >= 0 for name in TOKEN_FIELDS)):
                latest_usage = {"num_turns": turns, "usage": {name: usage[name] for name in TOKEN_FIELDS}}
        values = {"input-bindings": True, "supplied-surface": self.launch_observed and self.input_observed,
                  "authentication-route": valid_auth, "startup-inventory": self.valid_init and not self.errors,
                  "mcp-handshake": self.handshake, "tool-inventory": self.inventory,
                  "tool-call": None if comparison == "unexercised" else comparison == "observed",
                  "hook-controls": None if comparison == "unexercised" else comparison == "observed",
                  "witness-integrity": not self.errors, "process-stopping": stopped}
        record = {"case_id": self.case_id, "kind": self.kind, "started_at": self.started_at,
                  "finished_at": surface.utc_now(), "bindings": self.bindings, "workspace": str(self.workspace),
                  "session_id": self.init.get("session_id") if self.init else None,
                  "checks": {name: "unexercised" if value is None else "observed" if value else "failed" for name, value in values.items()},
                  "comparison": comparison, "errors": self.errors, "usage_reports": self.usage,
                  "usage_checkpoint": {"state": "reported" if latest_usage else "unknown", "latest_valid": latest_usage,
                                       "provider_completeness": "unverified"},
                  "usage_scope": "reported harness fields only; provider completeness and missing intervals remain unknown",
                  "stopping": "observed" if stopped else "unknown"}
        surface.save(self.root / "CASE.json", record)
        return record


def assess_batch(root, cases, mode, *, before_finalize=None):
    """Assess first, optionally publish a caller record, then freeze the manifest."""
    if mode not in {"real-harness", "synthetic-rehearsal"}:
        raise ValueError("unsupported observation mode")
    root = Path(root)
    if len(cases) != 3 or [case.kind for case in cases] != list(KINDS) or not all(case.finished for case in cases):
        raise ValueError("batch requires completed positive, closed-gate and invariance cases")
    records = [spec.transport_loads((case.root / "CASE.json").read_bytes()) for case in cases]
    if any(record["bindings"] != records[0]["bindings"] for record in records):
        raise ValueError("batch input bindings differ")
    fresh = (len({record["workspace"] for record in records}) == 3
             and len({record["session_id"] for record in records}) == 3 and all(record["session_id"] for record in records))
    inputs = root / "inputs"
    inputs.mkdir()
    for name in ("launch.json", "surface.json", "tools.json"):
        (inputs / name).write_bytes((cases[0].inputs / name).read_bytes())
    source = root / "sources"
    source.mkdir()
    for name in (Path(__file__).name, "claude_code_surface.py", "claude_code.py", "driver_core.py", "rawjson.py", "fixture_expectations.py"):
        (source / name).write_bytes((HERE / name).read_bytes())
    surface.save(root / "scope.json", {"scope": "supplied-surface", "mode": mode,
        "not_claimed": ["core/service conformance", "exhaustive provider capture", "hidden policy inspection", "launch authority"],
        "fresh_sessions_and_workspaces": fresh, "comparison_order": list(KINDS)})
    checks = []
    for name in surface.REQUIRED_CHECKS:
        outcomes = [record["checks"][name] for record in records]
        outcome = "failed" if "failed" in outcomes or (not fresh and name == "hook-controls") else "unexercised" if "unexercised" in outcomes else "observed"
        checks.append({"id": name, "outcome": outcome, "evidence": [str((case.root / "CASE.json").relative_to(root)) for case in cases]})
    stopping = "observed" if all(record["stopping"] == "observed" for record in records) else "unknown"
    if before_finalize is not None:
        # The caller may publish its result from this assessment, but cannot
        # alter the independent outcomes that the observer subsequently records.
        before_finalize(copy.deepcopy(checks), stopping)
    evidence = surface.manifest(root)
    surface.save(root / "EVIDENCE.json", evidence)
    observation = {"schema": "stewart.claude-code.surface-observation/1", "mode": mode, "scope": "supplied-surface",
        "started_at": records[0]["started_at"], "finished_at": records[-1]["finished_at"], **records[0]["bindings"],
        "evidence_manifest_sha256": spec.sha((root / "EVIDENCE.json").read_bytes()), "checks": checks,
        "stopping": stopping}
    surface.save(root / "OBSERVATION.json", observation)
    return observation


def _control_observer(root, name, kind):
    """Synthetic control inputs only; no executable from them is ever invoked."""
    work = Path(tempfile.mkdtemp(prefix="stewart-observer-", dir="/tmp")).resolve() / "workspace"
    prepared = root / ("prepared-" + name)
    launch = {"executable": "/synthetic/not-invoked", "sha256": "0" * 64, "version": "synthetic-observer",
              "platform": spec.platform_name(), "home": "/synthetic/home", "temporary_directory": "/synthetic/tmp",
              "config_directory": "/synthetic/no-credentials"}
    surface.prepare(prepared, work, Path(__file__).resolve(), compact(launch), "open-inquiry", spec.MODEL)
    from fixture_expectations import launch_expectation
    literal = launch_expectation(Path(__file__).resolve(), work, launch, "open-inquiry", spec.MODEL, surface.QUESTION)
    case = CaseObserver(prepared / "inputs", name, kind, work, root / name)
    case.record_launch({"argv": [launch["executable"]] + literal["model_argv"],
        "env": literal["environment"], "cwd": str(work), "executable_sha256": launch["sha256"],
        "files_sha256": {member: hashlib.sha256(raw).hexdigest() for member, raw in literal["files"].items()}})
    case.record_input(literal["input"], literal["input"])
    # A separate sender witness survives corrupt observer counters and digests.
    sender = root / ("sender-" + name)
    sender.mkdir()
    case.control_sender = sender
    (sender / "input.bin").write_bytes(literal["input"])
    for channel, method in (("stdout", "feed"), ("stderr", "feed_stderr")):
        path = sender / (channel + ".bin")
        path.write_bytes(b"")
        original = getattr(case, method)
        def record(raw, path=path, original=original):
            with path.open("ab") as stream:
                stream.write(raw)
            return original(raw)
        setattr(case, method, record)
    return case


def _init(case):
    return {"type": "system", "subtype": "init", "session_id": "synthetic-" + case.case_id,
            "claude_code_version": case.launch["version"], "model": case.model, "apiKeySource": "none",
            "permissionMode": "dontAsk", "tools": ["mcp__stewart__" + item["name"] for item in json.loads(case.tools_raw)],
            "mcp_servers": [{"name": "stewart", "status": "connected"}], "plugins": copy.deepcopy(PLUGINS),
            "plugin_errors": [], "mcp_server_errors": []}


def _connect(case, endpoint, listeners):
    if listeners:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(2)
        client.connect(str(case.workspace / endpoint))
    else:
        server, client = socket.socketpair()
        (case.attach_mcp if endpoint == "m" else case.attach_hook)(server)
    client.settimeout(2)
    return client


def _line(client):
    raw = bytearray()
    while b"\n" not in raw:
        chunk = client.recv(65536)
        if not chunk:
            raise ValueError("synthetic peer received no complete reply")
        raw.extend(chunk)
    return spec.mcp_message_loads(bytes(raw))


def _hook_input(case):
    return compact({"hook_event_name": "PreToolUse", "session_id": case.init["session_id"],
        "tool_use_id": "toolu-synthetic", "tool_name": "mcp__stewart__record_account",
        "tool_input": {"text": surface.MARKER}})


def _hook_failure_peer(peer, raw, before_operation=None, report=None):
    """Retain a disconnect as a diagnostic, never as proof of capture failure."""
    reply = bytearray()
    report = {} if report is None else report
    report.update(send_started=False, send_completed=False, shutdown_completed=False, reply_hex="")
    try:
        for operation in ("sendall", "shutdown", "recv"):
            report["operation"] = operation
            if before_operation is not None:
                before_operation(operation)
            if operation == "sendall":
                report["send_started"] = True
                peer.sendall(raw)
                report["send_completed"] = True
            elif operation == "shutdown":
                peer.shutdown(socket.SHUT_WR)
                report["shutdown_completed"] = True
            else:
                while True:
                    chunk = peer.recv(4096)
                    if not chunk:
                        break
                    reply.extend(chunk)
        report.update(errno=None, reply_hex=reply.hex())
        return report
    except OSError as error:
        report.update(errno=error.errno, detail=str(error), reply_hex=reply.hex())
        if error.errno not in {errno.EPIPE, errno.ECONNRESET, errno.ENOTCONN}:
            raise
        return report


HOOK_CAPTURE_FAILURE = "synthetic listener witness failure"


def _hook_capture_failure_observed(case, control):
    return (control.get("injected") is True and control.get("observer_stop") is True
            and control.get("peer", {}).get("reply_hex") == ""
            and set(case.errors) == {"hook observer failed: " + HOOK_CAPTURE_FAILURE,
                                     "hook peer EOF unobserved; capture may be incomplete"}
            and not case.gate_open() and not case.hooks and not case.calls and not case.fixture.effects)


def _hook_capture_failure(case, listeners=False, order="concurrent"):
    """Sabotage only the hook capture; ordered socketpairs exercise close races."""
    if order not in {"concurrent", "before-sendall", "before-shutdown", "before-recv"} or (listeners and order != "concurrent"):
        raise ValueError("unsupported synthetic hook-failure ordering")
    raw = _hook_input(case)
    # This peer witness is outside the append being sabotaged. It states the
    # attempted input, not a claim that the observer received those bytes.
    (case.root / "control-hook-attempted.bin").write_bytes(raw)
    control = {"order": order, "injected": False, "failure": HOOK_CAPTURE_FAILURE, "peer": {}}
    original = case.append
    release = threading.Event()
    if order == "concurrent":
        release.set()

    def broken(member, chunk):
        if member.startswith("hook-") and member.endswith("-received.bin"):
            if not release.wait(2):
                raise TimeoutError("synthetic hook ordering timed out")
            control.update(injected=True, member=member, append_bytes=len(chunk))
            raise OSError(HOOK_CAPTURE_FAILURE)
        original(member, chunk)

    def join_hook():
        for thread in case.threads:
            if thread.name.startswith("hook-"):
                thread.join(timeout=2)
                if thread.is_alive():
                    raise TimeoutError("synthetic hook observer did not finish")

    def before_operation(operation):
        if order == "before-" + operation:
            release.set()
            join_hook()

    case.append = broken
    try:
        with _connect(case, "h", listeners) as peer:
            _hook_failure_peer(peer, raw, before_operation, control["peer"])
        join_hook()
        try:
            case.check_stop()
        except ObserverStop:
            control["observer_stop"] = True
        else:
            control["observer_stop"] = False
        control["passed"] = _hook_capture_failure_observed(case, control)
        return control
    except (OSError, ValueError, ObserverStop) as error:
        control["error"] = {"type": type(error).__name__, "errno": getattr(error, "errno", None), "detail": str(error)}
        raise
    finally:
        release.set()
        try:
            join_hook()
        finally:
            case.append = original
            control["observer_errors"] = list(case.errors)
            surface.save(case.root / "control-hook-failure.json", control)


def _traffic(case, listeners=False, fragmented=False, no_attempt=False, bypass=False):
    raw = compact(_init(case)) + b"\n"
    for chunk in ([raw[n:n + 1] for n in range(len(raw))] if fragmented else [raw]):
        case.feed(chunk)
    client = _connect(case, "m", listeners)
    try:
        def request(number, method, params=None):
            value = {"jsonrpc": "2.0", "method": method}
            if number is not None:
                value["id"] = number
            if params is not None:
                value["params"] = params
            client.sendall(compact(value) + b"\n")
            return _line(client) if number is not None else None
        request(1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "synthetic", "version": "1"}})
        request(None, "notifications/initialized")
        listed = request(2, "tools/list")
        if listed.get("result", {}).get("tools") != json.loads(case.tools_raw):
            raise ValueError("synthetic peer saw a different tool inventory")
        if not no_attempt:
            with _connect(case, "h", listeners) as hook:
                hook.sendall(_hook_input(case))
                hook.shutdown(socket.SHUT_WR)
                reply = bytearray()
                while True:
                    chunk = hook.recv(4096)
                    if not chunk:
                        break
                    reply.extend(chunk)
                expected = spec.surface_document()["hook_replies"]["deny" if case.kind == "closed-gate" else "allow"]
                if spec.transport_loads(bytes(reply)) != expected:
                    raise ValueError("synthetic peer saw a different hook decision")
            if case.kind != "closed-gate" or bypass:
                # Unknown params metadata is contract-tolerated and must not
                # invalidate an otherwise exact interpreted tool call.
                request(3, "tools/call", {"name": "record_account", "arguments": {"text": surface.MARKER},
                                          "_meta": {"synthetic-control": True}})
    finally:
        client.close()
    case.feed(compact({"type": "result", "session_id": case.init["session_id"], "is_error": False,
                       "num_turns": 1, "usage": {name: 1 for name in TOKEN_FIELDS}}) + b"\n")


def _finish_control(case, **changes):
    for channel in ("stdout", "stderr"):
        try:
            case.finish_stream(channel)
        except ObserverStop:
            pass
    supplied = {channel: (case.control_sender / (channel + ".bin")).read_bytes() for channel in ("stdout", "stderr")}
    first_input = (case.control_sender / "input.bin").read_bytes()
    process = {"exit": 0, "stop": None, "guard_reason": "worker-exit", "group_gone": True,
               "guard_reaped": True, "elapsed_seconds": 0, "input_bytes_sent": len(first_input),
               "input_prefix_sha256": hashlib.sha256(first_input).hexdigest(), "stream_eof": {"stdout": True, "stderr": True},
               "capture_bytes": {key: len(raw) for key, raw in supplied.items()},
               "capture_sha256": {key: hashlib.sha256(raw).hexdigest() for key, raw in supplied.items()}}
    process.update(changes)
    case.event("synthetic-control-provenance", auth="supplied synthetic allowlist", process="supplied synthetic result; no process was launched")
    return case.finish(process, {"loggedIn": True, "authMethod": "claude.ai", "configDirectory": case.launch["config_directory"]})


def self_test():
    root = Path(tempfile.mkdtemp(prefix="stewart-observer-selftest-")).resolve()
    checks = []
    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})
    normal = []
    for kind in KINDS:
        case = _control_observer(root, kind, kind)
        _traffic(case, fragmented=kind == "invariance")
        result = _finish_control(case)
        check(kind + ".observed-with-metadata-and-framing-invariance", not result["errors"]
              and all(value == "observed" for value in result["checks"].values()))
        normal.append(case)
    case = _control_observer(root, "missing-attempt", "closed-gate")
    _traffic(case, no_attempt=True)
    check("missing-attempt-is-unexercised", _finish_control(case)["comparison"] == "unexercised")
    case = _control_observer(root, "denial-bypass", "closed-gate")
    try:
        _traffic(case, bypass=True)
    except ObserverStop:
        pass
    check("denial-with-MCP-call-fails", _finish_control(case, stop="observer-stop")["comparison"] == "failed")
    variants = {
        "wrong-tools": lambda value: value["tools"].append("Bash"),
        "wrong-plugin": lambda value: value["plugins"].append({"name": "unexpected"}),
        "wrong-route": lambda value: value.update(apiKeySource="environment"),
        "wrong-model": lambda value: value.update(model="other"),
        "plugin-errors": lambda value: value.update(plugin_errors=["synthetic error"]),
        "malformed-tools": lambda value: value.update(tools=[{}]),
    }
    for name, change in variants.items():
        case = _control_observer(root, name, "positive")
        value = _init(case)
        change(value)
        try:
            case.feed(compact(value) + b"\n")
        except ObserverStop:
            stopped = True
        else:
            stopped = False
        check(name, stopped and not case.gate_open())
        _finish_control(case, stop="observer-stop")
    events = {
        "delegate": {"type": "assistant", "parent_tool_use_id": "nested"},
        "background": {"type": "system", "subtype": "task_started"},
        "retry": {"type": "system", "subtype": "api_retry"},
        "install": {"type": "system", "subtype": "plugin_install"},
        "overage-enabled": {"type": "rate_limit_event", "rate_limit_info": {"overageEnabled": True}},
        "overage-used": {"type": "rate_limit_event", "rate_limit_info": {"isUsingOverage": True}},
        "quota": {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected"}},
        "malformed-assistant": {"type": "assistant", "message": ["not an object"]},
        "assistant-tool": {"type": "assistant", "message": {"model": spec.MODEL, "content": [{"type": "tool_use", "name": "Bash"}]}},
        "compaction": {"type": "system", "subtype": "compact_boundary"},
    }
    for name, value in events.items():
        case = _control_observer(root, name, "positive")
        case.feed(compact(_init(case)) + b"\n")
        try:
            case.feed(compact(value) + b"\n")
        except ObserverStop:
            stopped = True
        else:
            stopped = False
        check(name, stopped and not case.gate_open())
        _finish_control(case, stop="observer-stop")
    for name, raw in (("duplicate-init", None), ("duplicate-member", b'{"type":"system","type":"result"}\n'),
                      ("partial-stdout", b'{"type":')):
        case = _control_observer(root, name, "positive")
        case.feed(compact(_init(case)) + b"\n")
        raw = compact(_init(case)) + b"\n" if raw is None else raw
        try:
            case.feed(raw)
            case.finish_stream("stdout")
        except ObserverStop:
            stopped = True
        else:
            stopped = False
        check(name + ".raw-retained", stopped and (case.root / "stdout.bin").read_bytes().endswith(raw))
        _finish_control(case, stop="observer-stop")
    for name, change in (("controller-stop", {"stop": "operator-stop"}), ("guard-stop", {"guard_reason": "deadline"}),
                         ("unknown-group", {"group_gone": False}), ("unreaped-guard", {"guard_reaped": False}),
                         ("capture-mismatch", {"capture_sha256": {"stdout": "0" * 64, "stderr": "0" * 64}})):
        case = _control_observer(root, name, "positive")
        _traffic(case)
        result = _finish_control(case, **change)
        check(name, bool(result["errors"]) and result["checks"]["witness-integrity"] == "failed")
    for name in ("observer-count-corruption", "observer-hash-corruption", "both-supplied-copies-corrupt"):
        case = _control_observer(root, name, "positive")
        _traffic(case)
        if name == "observer-count-corruption":
            case.stream_bytes["stdout"] += 1
            diagnostic = "launcher/observer capture differs: stdout"
        elif name == "observer-hash-corruption":
            case.stream_hash["stdout"].update(b"not supplied")
            diagnostic = "launcher/observer capture differs: stdout"
        else:
            for base in (case.workspace, case.inputs):
                (base / "settings.json").write_bytes(b"{}")
            diagnostic = "supplied file changed during the observation: settings.json"
        result = _finish_control(case)
        check(name, diagnostic in result["errors"] and result["checks"]["witness-integrity"] == "failed")
    for endpoint in ("m", "h"):
        case = _control_observer(root, "partial-" + endpoint, "positive")
        case.feed(compact(_init(case)) + b"\n")
        client = _connect(case, endpoint, False)
        client.sendall(b'{"partial":')
        time.sleep(0.03)
        result = _finish_control(case)
        client.close()
        member = "mcp-received.bin" if endpoint == "m" else "hook-0001-received.bin"
        check(endpoint + ".forced-close-does-not-hide-partial", bool(result["errors"])
              and (case.root / member).read_bytes() == b'{"partial":')
    case = _control_observer(root, "malformed-hook", "positive")
    case.feed(compact(_init(case)) + b"\n")
    with _connect(case, "h", False) as peer:
        peer.sendall(b"[]")
        peer.shutdown(socket.SHUT_WR)
        peer.recv(4096)
    try:
        case.check_stop()
    except ObserverStop:
        stopped = True
    else:
        stopped = False
    check("malformed-hook-reaches-stop-callback", stopped)
    _finish_control(case, stop="observer-stop")
    case = _control_observer(root, "capture-failure", "positive")
    original = case.append
    def broken(name, raw):
        if name == "stdout.bin":
            raise OSError("synthetic witness failure")
        original(name, raw)
    case.append = broken
    try:
        case.feed(compact(_init(case)) + b"\n")
    except ObserverStop:
        stopped = True
    else:
        stopped = False
    check("witness-failure-stops-before-gate", stopped and not case.gate_open())
    case.append = original
    _finish_control(case, stop="observer-stop")
    for order in ("before-sendall", "before-shutdown", "before-recv"):
        case = _control_observer(root, "hook-capture-" + order, "positive")
        case.feed(compact(_init(case)) + b"\n")
        original = case.append
        control = _hook_capture_failure(case, order=order)
        check("hook-capture-" + order, control["passed"] and control["append_bytes"] == 0
              and case.append == original
              and (case.root / "control-hook-attempted.bin").read_bytes() == _hook_input(case)
              and not (case.root / "hook-0001-received.bin").exists())
        changed = dict(control, injected=False)
        check("hook-capture-" + order + "-requires-injection", not _hook_capture_failure_observed(case, changed))
        extra_failure = copy.copy(case)
        extra_failure.errors = list(case.errors) + ["synthetic unrelated observer failure"]
        check("hook-capture-" + order + "-rejects-unrelated-failure", not _hook_capture_failure_observed(extra_failure, control))
        _finish_control(case, stop="observer-stop", guard_reason="owner-stop")

    class FailingPeer:
        def __init__(self, operation, number):
            self.operation, self.number = operation, number

        def fail_at(self, operation):
            if operation == self.operation:
                raise OSError(self.number, "synthetic peer operation failed")

        def sendall(self, raw):
            self.fail_at("sendall")

        def shutdown(self, direction):
            self.fail_at("shutdown")

        def recv(self, size):
            self.fail_at("recv")
            return b""

    for operation, number in (("sendall", errno.EPIPE), ("shutdown", errno.ENOTCONN), ("recv", errno.ECONNRESET)):
        diagnostic = _hook_failure_peer(FailingPeer(operation, number), _hook_input(normal[0]))
        check("hook-peer-" + operation + "-disconnect-alone-is-insufficient",
              diagnostic["operation"] == operation and diagnostic["errno"] == number
              and not _hook_capture_failure_observed(normal[0], {"injected": True, "observer_stop": True, "peer": diagnostic}))
    diagnostic = {}
    try:
        _hook_failure_peer(FailingPeer("shutdown", errno.EACCES), _hook_input(normal[0]), report=diagnostic)
    except OSError as error:
        refused = error.errno == errno.EACCES
    else:
        refused = False
    check("hook-peer-unrelated-error-propagates", refused and diagnostic["send_completed"]
          and diagnostic["operation"] == "shutdown" and diagnostic["errno"] == errno.EACCES)

    from unittest.mock import patch
    case = _control_observer(root, "hook-capture-connect-error", "positive")
    case.feed(compact(_init(case)) + b"\n")
    original = case.append
    with patch(__name__ + "._connect", side_effect=OSError(errno.EACCES, "synthetic connection refused")):
        try:
            _hook_capture_failure(case)
        except OSError as error:
            refused = error.errno == errno.EACCES
        else:
            refused = False
    control = json.loads((case.root / "control-hook-failure.json").read_bytes())
    check("hook-capture-early-error-restores-and-retains", refused and case.append == original
          and control["injected"] is False and control["error"]["errno"] == errno.EACCES
          and (case.root / "control-hook-attempted.bin").read_bytes() == _hook_input(case))
    _finish_control(case, stop="synthetic-control")
    case = _control_observer(root, "initialize-error", "positive")
    case.fixture.mcp(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
    reply = case.fixture.mcp(b'{"jsonrpc":"2.0","id":1,"method":"initialize"}\n')
    check("initialize-error-does-not-satisfy-handshake", "error" in spec.mcp_message_loads(reply) and not case.handshake)
    try:
        case.fixture.mcp(b'{"jsonrpc":"2.0","id":2,"method":"initialize","params":[]}\n')
    except ValueError:
        refused = True
    else:
        refused = False
    check("malformed-initialize-does-not-satisfy-handshake", refused and not case.handshake)
    _finish_control(case, stop="synthetic-control")
    case = _control_observer(root, "auth-extra", "positive")
    secret = "synthetic-auth-secret-must-not-be-retained"
    result = case.finish({}, {"loggedIn": True, "authMethod": "claude.ai", "configDirectory": case.launch["config_directory"], "private": secret})
    check("unallowlisted-auth-never-retained", bool(result["errors"]) and not (case.root / "authentication.json").exists()
          and all(secret.encode() not in path.read_bytes() for path in case.root.rglob("*") if path.is_file()))
    case = _control_observer(root, "unknown-usage", "positive")
    case.feed(compact(_init(case)) + b"\n")
    case.feed(b'{"type":"result","num_turns":1,"usage":{"input_tokens":-1}}\n')
    result = _finish_control(case)
    check("malformed-usage-remains-unknown", result["usage_checkpoint"]["state"] == "unknown"
          and result["usage_reports"][0]["usage"]["input_tokens"] == -1)
    # Aggregate parser controls copy existing synthetic case records without
    # invoking peers again or rewriting their original witnesses.
    for variant in ("normal", "duplicate-session", "callback-failure"):
        aggregate = root / ("aggregate-" + variant)
        aggregate.mkdir()
        surface.save(aggregate / "control.json", {"scope": "copied synthetic case records; no new peer observation", "variant": variant})
        cloned = []
        for index, original in enumerate(normal):
            clone = copy.copy(original)
            clone.root = aggregate / original.kind
            clone.root.mkdir()
            record = spec.transport_loads((original.root / "CASE.json").read_bytes())
            if variant == "duplicate-session" and index == 1:
                record["session_id"] = normal[0].init["session_id"]
            surface.save(clone.root / "CASE.json", record)
            cloned.append(clone)
        seen = []

        def finalize(aggregate_checks, stopping):
            seen.append((copy.deepcopy(aggregate_checks), stopping))
            if variant == "callback-failure":
                raise OSError("synthetic controller result write failed")
            surface.save(aggregate / "RESULT.json", {"checks": aggregate_checks, "stopping": stopping})
            # A callback receives an isolated snapshot, not writable authority
            # over the independent observation's final outcomes.
            aggregate_checks[0]["outcome"] = "failed"

        try:
            value = assess_batch(aggregate, cloned, "synthetic-rehearsal", before_finalize=finalize)
        except OSError:
            check("aggregate-callback-failure-prevents-finalization", variant == "callback-failure"
                  and len(seen) == 1 and not (aggregate / "EVIDENCE.json").exists()
                  and not (aggregate / "OBSERVATION.json").exists())
            continue
        member = next((row for row in spec.transport_loads((aggregate / "EVIDENCE.json").read_bytes())["members"]
                       if row["path"] == "RESULT.json"), None)
        raw = (aggregate / "RESULT.json").read_bytes()
        check("aggregate-" + variant + "-callback-record-bound", member == {
            "path": "RESULT.json", "bytes": len(raw), "sha256": spec.sha(raw)})
        check("aggregate-" + variant + "-callback-matches-observation", len(seen) == 1
              and seen[0] == (value["checks"], value["stopping"]))
        failed = [row["id"] for row in seen[0][0] if row["outcome"] != "observed"]
        check("aggregate-" + variant + "-outcome", failed == (["hook-controls"] if variant == "duplicate-session" else [])
              and seen[0][1] == "observed")
    surface.save(root / "SELFTEST.json", {"checks": checks})
    observation = assess_batch(root, normal, "synthetic-rehearsal")
    passed = sum(row["passed"] for row in checks)
    for row in checks:
        if not row["passed"]:
            print("FAIL " + row["name"])
    print("Self-test: %d passed, %d failed, 0 skipped" % (passed, len(checks) - passed))
    print("Synthetic streams, auth receipts and process results only; no subprocess launched. Retained: " + str(root))
    return int(passed != len(checks) or any(row["outcome"] != "observed" for row in observation["checks"]))


def rehearse_listeners(root):
    root.mkdir(mode=0o700)
    controls, cases = [], []
    for kind in KINDS:
        case = _control_observer(root, kind, kind)
        try:
            case.start_listeners()
            _traffic(case, listeners=True)
            record = _finish_control(case)
            passed = not record["errors"] and all(value == "observed" for value in record["checks"].values())
            cases.append(case)
            controls.append({"name": kind, "passed": passed, "detail": record["errors"]})
        except (OSError, ValueError, ObserverStop) as error:
            case.close()
            controls.append({"name": kind, "passed": False, "detail": str(error)})
    for name in ("bad-startup", "witness-failure"):
        case = _control_observer(root, name, "positive")
        control = None
        try:
            case.start_listeners()
            if name == "bad-startup":
                value = _init(case)
                value["apiKeySource"] = "environment"
                try:
                    case.feed(compact(value) + b"\n")
                except ObserverStop:
                    pass
            else:
                case.feed(compact(_init(case)) + b"\n")
                control = _hook_capture_failure(case, listeners=True)
            try:
                case.check_stop()
            except ObserverStop:
                stopped = True
            else:
                stopped = False
            record = _finish_control(case, stop="observer-stop", guard_reason="owner-stop")
            controls.append({"name": name, "passed": stopped and bool(record["errors"]) and not case.fixture.effects
                             and (control is None or control["passed"]),
                             "detail": record["errors"]})
        except (OSError, ValueError, ObserverStop) as error:
            case.close()
            controls.append({"name": name, "passed": False, "detail": str(error), "observer_errors": list(case.errors)})
    counts = {"controls": len(controls), "passed": sum(row["passed"] for row in controls),
              "failed": sum(not row["passed"] for row in controls), "skipped": 0}
    surface.save(root / "REHEARSAL.json", {"schema": "stewart.claude-code.observer-rehearsal/1", "counts": counts,
        "controls": controls, "scope": "synthetic peers/transcripts/auth/process-result controls; no subprocess or Claude"})
    if len(cases) == 3:
        assess_batch(root, cases, "synthetic-rehearsal")
    print(json.dumps(counts, sort_keys=True))
    print("Retained listener rehearsal: " + str(root))
    return int(bool(counts["failed"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--rehearse-listeners", action="store_true")
    parser.add_argument("--work", type=Path, help="fresh absolute listener-rehearsal evidence directory")
    args = parser.parse_args()
    if args.self_test and not args.rehearse_listeners:
        return self_test()
    if args.rehearse_listeners and not args.self_test and args.work and args.work.is_absolute() and not args.work.exists():
        return rehearse_listeners(args.work)
    parser.error("select --self-test or --rehearse-listeners --work /absolute/fresh-directory")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, ObserverStop) as error:
        print("Observer check failed: " + str(error), file=sys.stderr)
        sys.exit(1)
