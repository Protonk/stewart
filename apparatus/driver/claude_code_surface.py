#!/usr/bin/env python3
"""Independent full-surface fixture for the supplied-surface check; never launch Claude.

This module prepares inputs and serves fixture tool effects; it executes nothing.
Tool effects below belong to this fixture, not Stewart's audit core. Nothing here
produces an eligible profile check or establishes real-harness conformance.
Run with python3 -I -B. See CLAUDE-CODE-SURFACE.md for scope and commands.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import time

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
    print("No process or Claude invocation in self-test. Retained: " + str(root))
    return int(bool(failed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    return self_test()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print("Surface fixture failed: " + str(error), file=sys.stderr)
        sys.exit(1)
