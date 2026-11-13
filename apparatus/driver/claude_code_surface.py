#!/usr/bin/env python3
"""Independent full-surface fixture and offline rehearsal; never launch Claude.

Only the supplied Stewart binary's two private transport helpers are executed.
Tool effects below belong to this fixture, not Stewart's audit core. A rehearsal
cannot produce an eligible profile check or establish real-harness conformance.
Run with python3 -I -B. See CLAUDE-CODE-SURFACE.md for scope and commands.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import claude_code as spec
from driver_core import FAMILY_TEXT, expected_tools
from rawjson import compact

REQUIRED_CHECKS = (
    "input-bindings", "supplied-surface", "authentication-route", "startup-inventory",
    "mcp-handshake", "tool-inventory", "tool-call", "hook-controls",
    "witness-integrity", "process-stopping",
)
FAMILIES = ("open-inquiry", "inquiry-framing", "comparison")
MARKER = "This note is an effect in the independent synthetic fixture.\n"
QUESTION = ("This is a synthetic interface check. Call record_account once with the exact text "
            + json.dumps(MARKER) + ". Do not submit an audit or use any other tool.\n")
HELPERS = {"__stewart-cc-relay", "__stewart-cc-hook"}
CLOCK_NAME = "CLOCK_UPTIME_RAW" if sys.platform == "darwin" else "CLOCK_MONOTONIC"
CLOCK_ID = getattr(time, CLOCK_NAME)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def save(path, value):
    with path.open("xb") as stream:
        stream.write(compact(value) + b"\n")


class Journal:
    def __init__(self, root):
        self.root = root
        self.lock = threading.Lock()

    def append(self, name, raw):
        with self.lock, (self.root / name).open("ab", buffering=0) as stream:
            if stream.write(raw) != len(raw):
                raise OSError("incomplete independent witness: " + name)

    def event(self, kind, **details):
        self.append("events.jsonl", compact({"event": kind, "observer_pid": os.getpid(),
                    "time_ns": time.clock_gettime_ns(CLOCK_ID), "clock": CLOCK_NAME, **details}) + b"\n")


class Fixture:
    """Full inventory, one deliberately limited effect, no audit-core emulator."""
    def __init__(self, tools, journal):
        self.tools, self.journal = tools, journal
        self.names = {tool["name"] for tool in json.loads(tools)}
        self.active = False
        self.initialized = False
        self.effects = []
        self.used = set()

    def hook(self, raw, capture=True):
        if capture:
            self.journal.append("hook-received.bin", raw)
        try:
            value = spec.transport_loads(raw)
            name = value.get("tool_name")
            allow = self.active and name in {"mcp__stewart__" + item for item in self.names}
        except (ValueError, AttributeError):
            name, allow = None, False
        reply = compact(spec.surface_document()["hook_replies"]["allow" if allow else "deny"]) + b"\n"
        self.journal.event("fixture-hook-decision", tool=name, allowed=allow,
                           observer="fixture owner; not a real-harness attempt")
        self.journal.append("hook-generated.bin", reply)
        return reply

    def mcp(self, raw, capture=True):
        # Independent capture precedes parsing, including malformed frames.
        if capture:
            self.journal.append("mcp-received.bin", raw)
        value = spec.mcp_message_loads(raw)
        if "method" not in value:
            raise ValueError("fixture expects an MCP request or notification")
        identity = value.get("id")
        if "id" not in value:
            if value.get("method") == "notifications/initialized":
                self.initialized = True
            return None
        key = (type(identity).__name__, str(identity))
        error = None
        result = None
        if key in self.used:
            error = {"code": -32600, "message": "fixture request id already used"}
        else:
            self.used.add(key)
            method = value.get("method")
            if method == "initialize":
                result = compact(spec.surface_document()["mcp_initialize"])
            elif method == "ping":
                result = b"{}"
            elif not self.initialized:
                error = {"code": -32000, "message": "fixture initialize first"}
            elif method == "tools/list":
                result = b'{"tools":' + self.tools + b"}"
            elif method == "tools/call":
                params = value.get("params") or {}
                name, arguments = params.get("name"), params.get("arguments")
                if name not in self.names:
                    error = {"code": -32602, "message": "unknown fixture tool"}
                elif not self.active:
                    error = {"code": -32000, "message": "fixture startup gate closed"}
                elif name == "record_account" and arguments == {"text": MARKER}:
                    self.journal.event("fixture-effect-attempt", tool=name, arguments=arguments)
                    self.journal.append("effects.jsonl", compact({"tool": name, "arguments": arguments}) + b"\n")
                    self.effects.append(arguments)
                    self.journal.event("fixture-effect", tool=name, arguments=arguments)
                    result = compact({"content": [{"type": "text", "text": json.dumps({
                        "outcome": "completed", "data": {"fixture_effect": True}})}]})
                else:
                    # Listed schemas are exact; this fixture intentionally does
                    # not pretend to implement other core operations.
                    result = compact({"isError": True, "content": [{"type": "text", "text":
                        "This fixture implements only the specified record_account control; no core operation occurred."}]})
            else:
                error = {"code": -32601, "message": "unknown fixture method"}
        reply = b'{"jsonrpc":"2.0","id":' + compact(identity)
        reply += b',"error":' + compact(error) if error else b',"result":' + result
        reply += b"}\n"
        self.journal.append("mcp-supplied.bin", reply)
        return reply


def serve_mcp(listener, fixture, errors):
    try:
        connection, _ = listener.accept()
        pending = bytearray()
        with connection:
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    if pending:
                        raise ValueError("incomplete fixture frame")
                    break
                fixture.journal.append("mcp-received.bin", chunk)
                pending.extend(chunk)
                if len(pending) > 8 * 1024 * 1024:
                    raise ValueError("incomplete or oversized fixture frame")
                while b"\n" in pending:
                    line, _, rest = bytes(pending).partition(b"\n")
                    pending[:] = rest
                    reply = fixture.mcp(line + b"\n", capture=False)
                    if reply is not None:
                        connection.sendall(reply)
    except BaseException:
        errors.append(traceback.format_exc())


def serve_hook(listener, fixture, errors, empty=False):
    try:
        connection, _ = listener.accept()
        with connection:
            raw = bytearray()
            fixture.journal.append("hook-received.bin", b"")
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                fixture.journal.append("hook-received.bin", chunk)
                raw.extend(chunk)
                if len(raw) > 8 * 1024 * 1024:
                    raise ValueError("hook control exceeded fixture bound")
            reply = fixture.hook(bytes(raw), capture=False)
            supplied = b"" if empty else reply
            fixture.journal.append("hook-supplied.bin", supplied)
            connection.sendall(supplied)
    except BaseException:
        errors.append(traceback.format_exc())


class StoppingUncertain(RuntimeError):
    pass


def helper(binary, name, endpoint, cwd):
    if name not in HELPERS:
        raise ValueError("fixture may execute only Stewart's two transport helpers")
    process = subprocess.Popen([str(binary), name, endpoint], cwd=cwd,
                               env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.getpgid(process.pid) != os.getpgrp():
        process.kill()
        raise StoppingUncertain("helper escaped fixture worker group; stopping uncertain")
    return process


def exercise(binary, tools, workspace, kind, witness):
    """One owner-supervised worker; all helper/observer operations are inside it."""
    workspace.mkdir(mode=0o700)
    os.chdir(workspace)
    journal = Journal(witness.directory)
    fixture = Fixture(tools, journal)
    errors, checks = [], {}
    endpoint = "m" if kind.startswith("mcp") else "h"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.settimeout(3)
    process = None
    try:
        witness.event("before-listener-bind", endpoint=endpoint)
        listener.bind(endpoint)
        listener.listen(1)
        if endpoint == "m":
            fixture.active = kind != "mcp-closed"
            thread = threading.Thread(target=serve_mcp, args=(listener, fixture, errors), daemon=True)
            thread.start()
            witness.event("before-helper-launch", helper="relay")
            process = helper(binary, "__stewart-cc-relay", endpoint, workspace)
            os.set_blocking(process.stdout.fileno(), False)
            observer = spec.RelayObserver(witness)
            unread = bytearray()

            def request(value):
                raw = compact(value) + b"\n"
                journal.append("client-supplied.bin", raw)
                process.stdin.write(raw)
                process.stdin.flush()
                if "id" not in value:
                    return None
                deadline = time.monotonic() + 2
                while b"\n" not in unread and time.monotonic() < deadline:
                    got, eof = observer.read(process.stdout.fileno(), "client", seconds=0.05)
                    unread.extend(got)
                    if eof:
                        break
                line, separator, rest = bytes(unread).partition(b"\n")
                if not separator:
                    raise TimeoutError("fixture relay supplied no complete reply")
                unread[:] = rest
                journal.append("client-received.bin", line + b"\n")
                return spec.mcp_message_loads(line)

            init = request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "fixture", "version": "1"}}})
            checks["handshake"] = init.get("result") == spec.surface_document()["mcp_initialize"]
            request({"jsonrpc": "2.0", "method": "notifications/initialized"})
            listed = request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            checks["inventory"] = listed.get("result", {}).get("tools") == json.loads(tools)
            called = request({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                              "params": {"name": "record_account", "arguments": {"text": MARKER}}})
            checks["effect"] = (not fixture.effects and called.get("error", {}).get("code") == -32000
                                if kind == "mcp-closed" else fixture.effects == [{"text": MARKER}]
                                and "result" in called)
            effect_path = witness.directory / "effects.jsonl"
            effects = [json.loads(line) for line in effect_path.read_bytes().splitlines()] if effect_path.exists() else []
            checks["effect-witness"] = effects == ([] if kind == "mcp-closed" else [
                {"tool": "record_account", "arguments": {"text": MARKER}}])
            process.stdin.close()
            process.wait(timeout=2)
            thread.join(timeout=2)
            checks["exit"] = process.returncode == 0 and not thread.is_alive() and not errors
            checks["request-witness"] = (witness.directory / "client-supplied.bin").read_bytes() == (
                witness.directory / "mcp-received.bin").read_bytes()
            checks["reply-witness"] = (witness.directory / "client-received.bin").read_bytes() == (
                witness.directory / "mcp-supplied.bin").read_bytes()
        else:
            fixture.active = kind != "hook-closed"
            name = "Bash" if kind == "hook-unpinned" else "mcp__stewart__record_account"
            raw = compact({"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": {"text": MARKER}}) + b"\n"
            journal.append("client-supplied.bin", raw)
            thread = threading.Thread(target=serve_hook, args=(listener, fixture, errors, kind == "hook-empty"), daemon=True)
            thread.start()
            witness.event("before-helper-launch", helper="hook")
            process = helper(binary, "__stewart-cc-hook", endpoint, workspace)
            stdout, stderr = process.communicate(raw, timeout=3)
            journal.append("client-received.bin", stdout)
            journal.append("helper-stderr.bin", stderr)
            thread.join(timeout=2)
            checks["request-witness"] = (witness.directory / "hook-received.bin").read_bytes() == raw
            checks["reply-witness"] = (witness.directory / "hook-supplied.bin").read_bytes() == stdout
            checks["transport"] = (process.returncode == 2 and stdout == b"" if kind == "hook-empty"
                                   else process.returncode == 0 and stdout == (witness.directory / "hook-supplied.bin").read_bytes())
            expected = spec.surface_document()["hook_replies"]["allow" if kind == "hook-open" else "deny"]
            checks["decision"] = kind == "hook-empty" or spec.transport_loads(stdout) == expected
            checks["no-tool-effect"] = fixture.effects == []
            checks["server-stopped"] = not thread.is_alive() and not errors
        witness.event("helper-completed", exit=process.returncode)
        return {"checks": checks, "error": None, "effects": len(fixture.effects)}
    except BaseException as error:
        return {"checks": checks, "error": traceback.format_exc(),
                "stopping_uncertain": isinstance(error, StoppingUncertain)}
    finally:
        witness.event("before-fixture-cleanup")
        listener.close()
        if process:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed:
                    stream.close()
        witness.event("after-fixture-cleanup")


def manifest(root):
    members = []
    for path in sorted(root.rglob("*")):
        if path.parent == root and path.name in {"EVIDENCE.json", "OBSERVATION.json", "CHECK.json"}:
            continue
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("evidence is not a regular file: " + str(path))
        raw = path.read_bytes()
        members.append({"path": path.relative_to(root).as_posix(), "bytes": len(raw), "sha256": spec.sha(raw)})
    return {"schema": "stewart.claude-code.surface-evidence/1", "members": members}


def prepare(out, work, writer, launch_raw, family, model):
    launch = spec.transport_loads(launch_raw)
    if spec.parse(launch_raw).raw != launch_raw:
        raise ValueError("launch.json must contain exact JSON value bytes without surrounding whitespace")
    keys = {"executable", "sha256", "version", "platform", "config_directory", "home", "temporary_directory"}
    if not isinstance(launch, dict) or set(launch) != keys or not all(isinstance(value, str) for value in launch.values()):
        raise ValueError("launch.json must contain exactly the specified launch string members")
    for name in ("executable", "home", "temporary_directory", "config_directory"):
        if not Path(launch[name]).is_absolute():
            raise ValueError("launch path must be absolute: " + name)
    out.mkdir(mode=0o700)
    work.mkdir(mode=0o700)
    inputs = out / "inputs"
    inputs.mkdir()
    tools = spec.mcp_tools(compact(expected_tools(family)))
    supplied = spec.filled_launch(str(writer), str(work), launch, family, model)
    first_input = spec.surface_document()["input"]
    first_input["message"]["content"] = QUESTION
    files = {"launch.json": launch_raw, "surface.json": spec.SURFACE, "tools.json": tools,
             "question.txt": QUESTION.encode(), "system.txt": (spec.RUNTIME_ORIENTATION + "\n\n" + FAMILY_TEXT[family]).encode(),
             "settings.json": compact(supplied["settings"]), "mcp.json": compact(supplied["mcp_config"]),
             "environment.json": compact(supplied["environment"]), "argv.json": compact(supplied["model_argv"]),
             "input.jsonl": compact(first_input) + b"\n",
             "case.json": compact({"family": family, "model": model, "scope": "fixture effects only", "marker": MARKER})}
    for name, raw in files.items():
        (inputs / name).write_bytes(raw)
    for name in ("settings.json", "mcp.json", "system.txt"):
        (work / name).write_bytes(files[name])
    source = out / "sources"
    source.mkdir()
    for name in (Path(__file__).name, "claude_code.py", "driver_core.py", "rawjson.py", "fixture_expectations.py"):
        (source / name).write_bytes((HERE / name).read_bytes())
    save(inputs / "writer.json", {"path": str(writer), "sha256": spec.sha(writer.read_bytes())})
    return {"launch_sha256": spec.sha(launch_raw), "surface_sha256": spec.sha(files["surface.json"]),
            "tools_sha256": spec.sha(tools), "model": model}, tools


def rehearse(writer, launch_raw, family, model, out, work):
    # No path from launch.json is ever executed. Reject a common mistaken input
    # before calling the only executable this apparatus may start.
    binary = writer.read_bytes()
    if b"Stewart development build: claude-code" not in binary or b"__stewart-cc-relay" not in binary:
        raise ValueError("--binary must be the gated Stewart helper binary")
    started = utc_now()
    bindings, tools = prepare(out, work, writer, launch_raw, family, model)
    cases = ("mcp-positive", "mcp-closed", "mcp-invariance", "hook-open", "hook-closed", "hook-unpinned", "hook-empty")
    records = {}
    witness = out / "witness"
    witness.mkdir()
    for name in cases:
        records[name] = spec.relay_supervised(witness / name,
            lambda w: exercise(writer, tools, work / name, name, w), seconds=8)
        print(name + ": " + ("observed" if spec.relay_success(records[name]) else "failed"), flush=True)
        if not records[name]["group_stopped"]:
            break
    stopped = len(records) == len(cases) and all(item["group_stopped"] for item in records.values())
    success = lambda names: all(name in records and spec.relay_success(records[name]) for name in names)
    outcomes = {"input-bindings": True, "supplied-surface": True,
                "authentication-route": None, "startup-inventory": None,
                "mcp-handshake": success(cases[:3]), "tool-inventory": success(cases[:3]),
                "tool-call": success(cases[:3]), "hook-controls": success(cases[3:]),
                "witness-integrity": len(records) == len(cases) and all(
                    (item.get("result") or {}).get("checks", {}).get("request-witness") is True
                    and ((item.get("result") or {}).get("checks", {}).get("reply-witness", True) is True)
                    for item in records.values()), "process-stopping": stopped}
    save(out / "scope.json", {"mode": "synthetic-rehearsal", "helper_argv": sorted(HELPERS),
         "helper_workspace": str(work),
         "not_executed": ["Claude", "authentication-status", "model session", "audit core"],
         "supplied_surface": "prepared exact files; no claim that Claude received them",
         "fixture_operation": "record_account with the declared synthetic text only",
         "other_operations": "listed exactly, not implemented or qualified",
         "auth_rule": "future live observer discards raw auth output and keeps only loggedIn, authMethod, configDirectory",
         "cases_not_started": [name for name in cases if name not in records]})
    evidence = manifest(out)
    save(out / "EVIDENCE.json", evidence)
    checks = [{"id": name, "outcome": "unexercised" if value is None else "observed" if value else "failed",
               "evidence": ["scope.json"] if name in {"authentication-route", "startup-inventory"} else
                           [item["path"] for item in evidence["members"] if item["path"].startswith("inputs/")] if name in {"input-bindings", "supplied-surface"} else
                           [item["path"] for item in evidence["members"] if item["path"].endswith("controller-result.json")]
               } for name, value in outcomes.items()]
    record = {"schema": "stewart.claude-code.surface-observation/1", "mode": "synthetic-rehearsal",
              "scope": "supplied-surface", "started_at": started, "finished_at": utc_now(), **bindings,
              "evidence_manifest_sha256": spec.sha((out / "EVIDENCE.json").read_bytes()), "checks": checks,
              "stopping": "observed" if stopped else "unknown"}
    save(out / "OBSERVATION.json", record)
    counts = {state: sum(row["outcome"] == state for row in checks) for state in ("observed", "failed", "unexercised")}
    print(json.dumps(counts, sort_keys=True), flush=True)
    print("Offline rehearsal only; no CHECK.json or profile emitted. Retained: " + str(out), flush=True)
    return int(bool(counts["failed"]))


def self_test():
    root = Path(tempfile.mkdtemp(prefix="stewart-surface-selftest-"))
    checks = []
    def check(name, value):
        checks.append({"name": name, "passed": bool(value)})
    for family in FAMILIES:
        folder = root / family
        folder.mkdir()
        tools = spec.mcp_tools(compact(expected_tools(family)))
        fixture = Fixture(tools, Journal(folder))
        def call(number, method, **params):
            return spec.mcp_message_loads(fixture.mcp(compact({"jsonrpc": "2.0", "id": number,
                                                     "method": method, "params": params}) + b"\n"))
        check(family + ".initialize", call(1, "initialize")["result"] == spec.surface_document()["mcp_initialize"])
        fixture.mcp(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        check(family + ".complete-inventory", call(2, "tools/list")["result"]["tools"] == json.loads(tools))
        check(family + ".closed-gate", call(3, "tools/call", name="record_account", arguments={"text": MARKER})["error"]["code"] == -32000
              and fixture.effects == [])
        fixture.active = True
        check(family + ".positive-effect", "result" in call(4, "tools/call", name="record_account", arguments={"text": MARKER})
              and fixture.effects == [{"text": MARKER}])
        check(family + ".unknown-tool", "error" in call(5, "tools/call", name="Bash", arguments={}) and len(fixture.effects) == 1)
        check(family + ".invalid-arguments", call(6, "tools/call", name="record_account", arguments={"text": "different"})["result"]["isError"])
        check(family + ".duplicate-id", "error" in call(4, "tools/call", name="record_account", arguments={"text": MARKER}) and len(fixture.effects) == 1)
        for active, name, allowed in ((False, "mcp__stewart__record_account", False),
                                     (True, "Bash", False), (True, "mcp__stewart__record_account", True)):
            fixture.active = active
            reply = fixture.hook(compact({"tool_name": name}))
            check(family + ".hook-%s-%s" % (active, name), spec.transport_loads(reply) == spec.surface_document()["hook_replies"]["allow" if allowed else "deny"])
        fixture.active = True
        check(family + ".invariance", "result" in call(7, "tools/call", name="record_account", arguments={"text": MARKER}) and len(fixture.effects) == 2)
        # A failed independent effect witness must not produce a successful call.
        original = fixture.journal.append
        def fail_effect(name, raw):
            if name == "effects.jsonl":
                raise OSError("deliberate independent witness failure")
            original(name, raw)
        fixture.journal.append = fail_effect
        try:
            call(8, "tools/call", name="record_account", arguments={"text": MARKER})
        except OSError as error:
            refused = str(error) == "deliberate independent witness failure"
        else:
            refused = False
        check(family + ".failed-witness-stops-effect", refused and len(fixture.effects) == 2)
        malformed = b'{"jsonrpc":"1.0","id":9,"method":"tools/list"}\n'
        before_reply = (folder / "mcp-supplied.bin").read_bytes()
        try:
            fixture.mcp(malformed)
        except ValueError as error:
            refused = str(error) == "MCP message must be a JSON-RPC 2.0 object"
        else:
            refused = False
        check(family + ".malformed-captured-before-refusal", refused
              and (folder / "mcp-received.bin").read_bytes().endswith(malformed)
              and (folder / "mcp-supplied.bin").read_bytes() == before_reply)
    launch = {"executable": str(root / "never-executed"), "sha256": "0" * 64,
              "version": "synthetic", "platform": spec.platform_name(),
              "home": str(root / "home"), "temporary_directory": str(root / "temporary"),
              "config_directory": str(root / "no-credentials")}
    bindings, _ = prepare(root / "prepared", root / "workspace", Path(__file__).resolve(),
                          compact(launch), "open-inquiry", spec.MODEL)
    check("prepare.exact-launch-value-binding", bindings["launch_sha256"] == spec.sha(compact(launch)))
    from fixture_expectations import launch_expectation
    literal = launch_expectation(Path(__file__).resolve(), root / "workspace", launch,
                                 "open-inquiry", spec.MODEL, QUESTION)
    check("prepare.workspace-files-match", all((root / "workspace" / name).read_bytes() == raw
          and (root / "prepared/inputs" / name).read_bytes() == raw for name, raw in literal["files"].items()))
    check("prepare.exact-first-input", json.loads((root / "prepared/inputs/input.jsonl").read_bytes())["message"]["content"] == QUESTION)
    event = json.loads((root / "open-inquiry/events.jsonl").read_bytes().splitlines()[0])
    clock_name = "CLOCK_UPTIME_RAW" if sys.platform == "darwin" else "CLOCK_MONOTONIC"
    check("journal.shared-clock-and-observer", event["clock"] == clock_name
          and event["observer_pid"] == os.getpid() and event["time_ns"] <= time.clock_gettime_ns(getattr(time, clock_name)))
    for name, empty in (("normal", False), ("empty", True), ("invariance", False)):
        folder = root / ("hook-wire-" + name)
        folder.mkdir()
        fixture = Fixture(spec.mcp_tools(compact(expected_tools("open-inquiry"))), Journal(folder))
        fixture.active = True
        server, client = socket.socketpair()
        class Listener:
            def accept(self):
                return server, None
        errors = []
        thread = threading.Thread(target=serve_hook, args=(Listener(), fixture, errors, empty), daemon=True)
        thread.start()
        raw = compact({"tool_name": "mcp__stewart__record_account"})
        client.settimeout(1)
        try:
            client.sendall(raw)
            client.shutdown(socket.SHUT_WR)
            received = client.recv(4096)
            thread.join(timeout=1)
            check("hook-wire." + name, not errors and not thread.is_alive()
                  and (folder / "hook-generated.bin").read_bytes() == b"{}\n"
                  and (folder / "hook-supplied.bin").read_bytes() == received == (b"" if empty else b"{}\n")
                  and (folder / "hook-received.bin").read_bytes() == raw)
        finally:
            client.close()
    for name, serve in (("mcp", serve_mcp), ("hook", serve_hook)):
        folder = root / (name + "-partial")
        folder.mkdir()
        fixture = Fixture(spec.mcp_tools(compact(expected_tools("open-inquiry"))), Journal(folder))
        server, client = socket.socketpair()
        class Listener:
            def accept(self):
                return server, None
        errors = []
        thread = threading.Thread(target=serve, args=(Listener(), fixture, errors), daemon=True)
        thread.start()
        raw = b'{"jsonrpc":' if name == "mcp" else b'{"tool_name":'
        client.settimeout(1)
        try:
            client.sendall(raw)
            path = folder / (name + "-received.bin")
            until = time.monotonic() + 0.5
            while time.monotonic() < until and (not path.exists() or path.read_bytes() != raw):
                time.sleep(0.01)
            before_eof = path.exists() and path.read_bytes() == raw and not fixture.effects
            client.shutdown(socket.SHUT_WR)
            client.recv(4096)
            thread.join(timeout=1)
            check(name + ".partial-witness-before-eof", before_eof and not thread.is_alive()
                  and (bool(errors) if name == "mcp" else not errors))
        finally:
            client.close()
    try:
        prepare(root / "refused", root / "refused-work", Path(__file__).resolve(),
                compact(launch) + b"\n", "open-inquiry", spec.MODEL)
    except ValueError:
        refused = True
    else:
        refused = False
    check("prepare.refuses-surrounding-launch-whitespace", refused and not (root / "refused").exists())
    check("manifest-regular-files", len(manifest(root)["members"]) > 0)
    (root / "link-control").symlink_to("open-inquiry/events.jsonl")
    try:
        manifest(root)
    except ValueError:
        refused = True
    else:
        refused = False
    check("manifest-refuses-symlink", refused)
    save(root / "SELFTEST.json", {"checks": checks})
    for row in checks:
        if not row["passed"]:
            print("FAIL " + row["name"])
    failed = sum(not row["passed"] for row in checks)
    print("Self-test: %d passed, %d failed, 0 skipped" % (len(checks) - failed, failed))
    print("No helper process or Claude invocation in self-test. Retained: " + str(root))
    return int(bool(failed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--binary", type=Path, help="gated Stewart binary; only its relay and hook helpers are executed")
    parser.add_argument("--launch", type=Path, help="optional exact launch JSON bytes; default is explicitly synthetic and its executable is never invoked")
    parser.add_argument("--model", default=spec.MODEL, help="model binding only; no model is invoked")
    parser.add_argument("--family", choices=FAMILIES, default="open-inquiry")
    parser.add_argument("--work", type=Path, help="fresh evidence directory; separate helper workspace is retained and named in scope.json")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    for name in ("binary", "work"):
        value = getattr(args, name)
        if value is None or not value.is_absolute():
            parser.error("--" + name + " must be an absolute path")
    if args.launch is not None and not args.launch.is_absolute():
        parser.error("--launch must be absolute")
    if args.work.exists():
        parser.error("--work must be fresh; preserve existing evidence")
    workspace = Path(tempfile.mkdtemp(prefix="stewart-surface-helpers-")).resolve() / "work"
    print("Retained helper workspace: " + str(workspace), flush=True)
    if args.launch is None:
        placeholder = workspace.parent / "not-a-harness"
        placeholder.write_bytes(b"Synthetic rehearsal placeholder; this file is never executed.\n")
        launch_raw = compact({"executable": str(placeholder), "sha256": spec.sha(placeholder.read_bytes()),
            "version": "synthetic-rehearsal", "platform": spec.platform_name(),
            "home": str(workspace.parent / "synthetic-home"),
            "temporary_directory": str(workspace.parent / "synthetic-temporary"),
            "config_directory": str(workspace.parent / "no-credentials")})
    else:
        launch_raw = args.launch.read_bytes()
    try:
        return rehearse(args.binary, launch_raw, args.family, args.model, args.work, workspace)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        if args.work.exists():
            try:
                save(args.work / "FAILURE.json", {"error": str(error), "traceback": traceback.format_exc()})
            except OSError:
                pass
        print("Surface rehearsal failed: %s\nEvidence: %s\nHelper workspace: %s" % (
            error, args.work, workspace), file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("Surface fixture failed: " + str(error), file=sys.stderr)
        sys.exit(1)
