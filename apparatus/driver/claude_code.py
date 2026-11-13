#!/usr/bin/env python3
r"""Independent offline checks for the default-off Claude Code development profile.

This driver is authored from docs/claude-code/CONTRACT.md and the common
specifications, without reading service/src or service/tests. It never starts
Claude, logs in, or calls a provider. Native results are development evidence,
not qualification. Run with an explicit interpreter and isolated startup:

    python3 -I -B apparatus/driver/claude_code.py --self-test
    python3 -I -B apparatus/driver/claude_code.py --binary /abs/stewart \
        --work /abs/fresh-directory [--release-binary /abs/stewart-release] \
        [--variant-binary /abs/another-development-build]

Every input and command result is retained for review, including the independent
witness outside the archive. No successful or failed working tree is deleted.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import re
import select
import shlex
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
from driver_core import (CONTINUATION, FAMILY_TEXT, ORIENTATION, REMINDER,
                         expected_tools, strict_loads)
from rawjson import compact, parse


FIRST_PARAGRAPH = (
    "You are the auditor in a Stewart audit. The first user message is the "
    "manager's question, exactly as they wrote it. The materials they selected can "
    "be read with the list, read and search tools. The question and those "
    "materials are your whole world: use only Stewart's tools, with no shell, no "
    "other files, no network, no way to run code, no delegated auditors and no way "
    "to ask the manager anything. Harness instructions and system messages are "
    "runtime context, not additional evidence. Reports, logs and test results in "
    "the materials are claims by their authors, not executions you witnessed."
)
ORIENTATION_ID = "stewart.orientation/claude-code/2"
RUNTIME_ORIENTATION = FIRST_PARAGRAPH + "\n\n" + ORIENTATION.split("\n\n", 1)[1]
NEAR_LIMIT = (
    "Allowance notice: {seconds} seconds remain before this placement's deadline, "
    "and {placements} further placement starts remain for this audit. When execution "
    "stops, an unsubmitted answer stays unsubmitted."
)
COMPACTED = (
    "The harness has summarized your earlier conversation. Continue this audit. "
    "Call what_am_i_working_with to check your recorded work before repeating an "
    "action."
)
TEXTS = {"reminder": REMINDER, "near_limit": NEAR_LIMIT,
         "continuation": CONTINUATION, "compacted": COMPACTED}
SIGNER = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE"
MODEL = "synthetic-offline-model"
CANARY = b'#!/bin/sh\nprintf "unexpected local launch\\n" > "$0.started"\nexit 97\n'
ACCOUNT = "The supplied report claims success. This synthetic auditor did not witness execution.\n"
# Two cumulative main-loop checkpoints for one synthetic session. Only the
# later one may be reported; their sum must never appear.
CHECKPOINTS = (
    {"num_turns": 2, "usage": {"input_tokens": 11, "cache_creation_input_tokens": 120,
                               "cache_read_input_tokens": 300, "output_tokens": 40}},
    {"num_turns": 3, "usage": {"input_tokens": 17, "cache_creation_input_tokens": 120,
                               "cache_read_input_tokens": 950, "output_tokens": 65}},
)
PROFILE_SCHEMA = "stewart.claude-code.profile/2"
ARRANGEMENT_SCHEMA = "stewart.claude-code.arrangement/2"
SURFACE_SCHEMA = "stewart.claude-code.surface/1"
ARRANGEMENT_KEYS = {
    "schema", "family", "model", "guidance", "orientation", "system",
    "system_prompt", "tools", "mcp_tools", "runtime", "profile_sha256",
    "surface", "surface_sha256",
    "effort", "limits", "harness_max_turns", "harness_max_output_tokens",
    "texts", "reader", "renderer", "reading", "bindings",
}
# Shell/platform additions allowed only within the pre-Python observer's scope.
# Interpreter changes are retained separately and never exempt LC_CTYPE.
WRAPPER_ENVIRONMENT = {"PWD", "OLDPWD", "SHLVL", "_", "__CF_USER_TEXT_ENCODING"}
KEPT = "A pipelined note whose call was not cancelled.\n"
QUEUED = "The second pipelined note must follow the first.\n"
CANCELLED = "A pipelined note whose call was cancelled before it could be published.\n"
DUPLICATE = "A note sent under a request identifier this placement already used.\n"
SECOND_RELAY = "A note attempted through a second relay after the first was lost.\n"
# A fresh session's series; lower than the first session's on purpose.
SECOND_SESSION = {"num_turns": 1, "usage": {"input_tokens": 5, "cache_creation_input_tokens": 0,
                                            "cache_read_input_tokens": 210, "output_tokens": 9}}
RACES = 6


def race_text(number):
    """A quarter-mebibyte note, so that publishing it takes observable time."""
    line = "Race note %d: cancelled as soon as it was sent. " % number
    return (line + "x" * (127 - len(line)) + "\n") * 2048


CASES = (
    ("families", "All three families: preparation, commission, exact readback and status"),
    ("binding-controls", "Change each launch/check binding; reject it; restore the valid control"),
    ("surface-binding", "A check naming another surface, or an earlier profile form, refuses with the exact surface"),
    ("surface-two-builds", "Optional second build: same profile accepted by both writers; audits stay with their writer"),
    ("profile-input", "Strict profile JSON, bounds, regular-file and no-follow controls"),
    ("limit-fields", "One question version: placement bounds, mixed limit fields and the removed version refuse"),
    ("help-and-presentation", "Runtime help topic and notice; human output shows the profile by path and digest"),
    ("source-invariance", "Receipt stays captured after source/profile edits and CWD/HOME changes"),
    ("release-gate", "Optional featureless binary: runtime fields unknown, no topic or notice, same scaffold"),
    ("runtime-relay-forwarding", "Direct relay: arbitrary whole and segmented bytes before EOF, pipe observer control and bounded stopping"),
    ("runtime-submit", "Actual MCP record/prepare/submit, faithful delivery and fresh-session invariance"),
    ("runtime-ordinary-ending", "Unsubmitted turns, one reminder, a valid usage checkpoint, manager seal and confirmed close"),
    ("runtime-hooks-and-effort", "The hook helper admits only pinned tools after startup; a selected effort reaches the launch"),
    ("runtime-cancellation", "Ordered pipelined calls, cancellation behind a large call, late/unknown cancellations and reused IDs"),
    ("runtime-submit-publication", "Documented seal-publication pause: cancellation preserves placement; signal and deadline prevent sealing"),
    ("runtime-relay-loss", "The relay dies while the model lives: the placement stops, nothing else writes, a fresh session continues"),
    ("runtime-usage-series", "Two placements: each session's latest checkpoint is summed and a lost interval stays unknown"),
    ("runtime-compaction", "Each compaction boundary is followed by the pinned notice and spends neither allowance"),
    ("runtime-init-control", "Attempted authoring before a mismatched startup never changes the answer"),
    ("runtime-interruption", "Interrupted work and unknown usage continue in a fresh session without duplication"),
    ("runtime-deadline", "Deadline terminates the synthetic harness and its resistant descendant group"),
    ("runtime-owner-death", "Owner death terminates groups and preserves uncertainty for recovery"),
    ("runtime-unknown-stop", "An unresolved live group prevents restart and close cleanup without being signaled"),
    ("runtime-recorder-failure", "A witnessed capture-write failure stops before an attempted answer mutation"),
    ("runtime-credential-option", "A Claude Code run refuses an API credential option before invoking the harness"),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def environment_snapshot(raw):
    """Decode env -0 without accepting a truncated or ambiguous witness."""
    if raw and not raw.endswith(b"\0"):
        raise ValueError("environment witness is not NUL terminated")
    values = {}
    for item in raw[:-1].split(b"\0") if raw else ():
        name, separator, value = item.partition(b"=")
        if not separator or not name:
            raise ValueError("environment witness contains an invalid entry")
        name, value = name.decode("utf-8"), value.decode("utf-8")
        if name in values:
            raise ValueError("environment witness repeats a name: " + name)
        values[name] = value
    return values


def synthetic_executable(script, scenario, witness, *, python=None):
    """Snapshot before Python startup, using the supplied interpreter spelling when bound."""
    command = [str(python or sys.executable), "-I", "-B", str(script), "--synthetic-harness", str(scenario)]
    # mktemp creates a new mode-0600 file: concurrent launches and PID reuse
    # cannot overwrite a prior witness. All subsequent outputs retain it.
    return ("#!/bin/sh\n"
            "environment_witness=$(/usr/bin/mktemp "
            + shlex.quote(str(witness / "environment.XXXXXXXXXX")) + ") || exit 95\n"
            '/usr/bin/env -0 > "$environment_witness" || exit 95\n'
            "exec " + " ".join(shlex.quote(arg) for arg in command)
            + ' --environment-witness "$environment_witness" "$@"\n').encode("utf-8")


def publish_witness(path, data):
    """Publish a synchronization witness only after its full bytes are durable."""
    pending = path.with_name(path.name + ".pending")
    with open(pending, "xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(pending, path)


def mcp_tools(base):
    """Transform specification-owned bytes; never reconstruct input_schema."""
    out = []
    for tool in parse(base).items:
        out.append(b'{"name":' + tool.get("name").raw
                   + b',"description":' + tool.get("description").raw
                   + b',"inputSchema":' + tool.get("input_schema").raw + b'}')
    return b'[' + b','.join(out) + b']'


def surface_document():
    """Rebuild the launch surface from the contract's member table.

    This is written from the table and the wire contract's prose, not copied
    from the contract's worked example; the self-test compares the two.
    """
    def text_sha(text):
        return sha(text.encode("utf-8"))
    return {
        "schema": SURFACE_SCHEMA,
        "working_directory": "{workspace}",
        "auth_argv": ["auth", "status"],
        "model_argv": [
            "-p", "--input-format", "stream-json", "--output-format", "stream-json",
            "--verbose", "--restricted", "--tools", "", "--setting-sources", "",
            "--settings", "{workspace}/settings.json", "--strict-mcp-config",
            "--mcp-config", "{workspace}/mcp.json", "--allowedTools",
            "mcp__stewart__{tool}", "--permission-mode", "dontAsk",
            "--permission-prompts", "none", "--system-prompt-file",
            "{workspace}/system.txt", "--model", "{model}", "--max-turns", "200",
            "--no-session-persistence"],
        "effort_argv": ["--effort", "{effort}"],
        "settings": {
            "forceLoginMethod": "claudeai", "fastMode": False, "fallbackModel": [],
            "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
                {"type": "command", "command": "'{writer}' __stewart-cc-hook 'h'",
                 "timeout": 5}]}]}},
        "mcp_config": {"mcpServers": {"stewart": {
            "type": "stdio", "command": "{writer}", "args": ["__stewart-cc-relay", "m"]}}},
        "environment": {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8",
            "DISABLE_UPDATES": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
            "CLAUDE_CODE_DISABLE_AGENT_VIEW": "1", "CLAUDE_CODE_DISABLE_FAST_MODE": "1",
            "ENABLE_CLAUDEAI_MCP_SERVERS": "false", "ENABLE_TOOL_SEARCH": "false",
            "CLAUDE_CODE_MAX_RETRIES": "0", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "16000",
            "HOME": "{home}", "TMPDIR": "{temporary_directory}",
            "CLAUDE_CONFIG_DIR": "{config_directory}"},
        "controls": {"harness_max_turns": 200, "harness_max_output_tokens": 16000},
        "system_prompt": "{orientation}\n\n{guidance}",
        "input": {"type": "user", "session_id": "", "parent_tool_use_id": None,
                  "message": {"role": "user", "content": "{text}"}},
        "mcp_initialize": {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                           "serverInfo": {"name": "stewart", "version": "1"}},
        "hook_replies": {"allow": {}, "deny": {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "Tool is outside the validated active commission."}}},
        "texts": {"orientation": ORIENTATION_ID,
                  "orientation_sha256": text_sha(RUNTIME_ORIENTATION),
                  "reminder_sha256": text_sha(REMINDER),
                  "near_limit_sha256": text_sha(NEAR_LIMIT),
                  "continuation_sha256": text_sha(CONTINUATION),
                  "compacted_sha256": text_sha(COMPACTED)},
    }


SURFACE = compact(surface_document())
SURFACE_SHA = sha(SURFACE)


def shell_quoted(path):
    """The wire contract's single-quote form for the writer in the hook command."""
    return "'" + path.replace("'", "'\\''") + "'"


def filled_launch(writer, workspace, launch, family, model, effort=None):
    """Fill the surface placeholders for one launch of one family."""
    doc = surface_document()
    argv = []
    for arg in doc["model_argv"]:
        if arg == "mcp__stewart__{tool}":
            argv.extend("mcp__stewart__" + tool["name"] for tool in expected_tools(family))
        else:
            argv.append(arg.replace("{workspace}", workspace).replace("{model}", model))
    if effort is not None:
        argv.extend(arg.replace("{effort}", effort) for arg in doc["effort_argv"])
    settings = doc["settings"]
    settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = (
        shell_quoted(writer) + " __stewart-cc-hook 'h'")
    config = doc["mcp_config"]
    config["mcpServers"]["stewart"]["command"] = writer
    environment = {key: value.replace("{home}", launch["home"])
                   .replace("{temporary_directory}", launch["temporary_directory"])
                   .replace("{config_directory}", launch["config_directory"])
                   for key, value in doc["environment"].items()}
    return {"auth_argv": doc["auth_argv"], "model_argv": argv, "settings": settings,
            "mcp_config": config, "environment": environment,
            "mcp_initialize": doc["mcp_initialize"]}


def surface_example(spec):
    """The contract's worked example bytes and stated digest, read from its text."""
    section = spec.split("## Launch surface", 1)[1]
    block = section.split("```json\n", 1)[1].split("\n```", 1)[0]
    stated = re.search(r"Its SHA-256 is\s+`([0-9a-f]{64})`", section)
    return "".join(block.split("\n")).encode("utf-8"), stated.group(1) if stated else None


def platform_name():
    system, machine = platform.system(), platform.machine()
    value = {("Darwin", "arm64"): "macos-aarch64",
             ("Linux", "aarch64"): "linux-aarch64",
             ("Linux", "x86_64"): "linux-x86_64"}.get((system, machine))
    if value is None:
        raise ValueError("unsupported native driver platform: %s %s" % (system, machine))
    return value


def snapshot(root):
    """Observe names, types and regular-file identities without following links."""
    result = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        item = {"mode": info.st_mode, "inode": info.st_ino}
        if stat.S_ISREG(info.st_mode):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                item["sha256"] = sha(stream.read())
        elif stat.S_ISLNK(info.st_mode):
            item["target"] = os.readlink(path)
        result[str(path.relative_to(root))] = item
    return result


def immutable_changes(before, after):
    return [name for name, value in before.items() if after.get(name) != value]


def group_observation(group, probe=os.killpg):
    try:
        probe(group, 0)
        return "present"
    except ProcessLookupError:
        return "absent"
    except PermissionError:
        return "unknown"


def release_fault_pauses(directory, observe):
    """Release each documented pause once, preserving its first release evidence."""
    for paused in directory.glob("*.paused"):
        go = paused.with_suffix(".go")
        try:
            with go.open("xb"):
                pass
        except FileExistsError:
            continue
        observe("pause-released", pause=str(paused), go=str(go))


def capture_failure_diagnostic(text):
    """A case name or custody path is not an operation failure diagnosis."""
    if not isinstance(text, str):
        return False
    text = re.sub(r"/[^\s\"']+", "<path>", text.lower())
    return bool(re.search(r"\b(capture|capturing|recorder|archive_write_failed|capture_failed|raw_capture)\b", text)
                and any(word in text for word in ("fail", "denied", "permission", "error", "cannot", "could not")))


def summary_placement_fact(summary, name, value):
    """Associate a number with its stated meaning; unrelated numbers prove nothing."""
    n = r"\b%d\b" % value
    word = {"used": r"(?:used|reserved|started)", "allowed": r"(?:allowed|limit)", "remaining": r"remain(?:ing|s)?"}[name]
    return bool(re.search(n + r"\s+(?:placement starts?\s+|placements?\s+)?" + word + r"\b", summary, re.I)
                or re.search(r"\b" + word + r"\s*[:=]?\s*" + n, summary, re.I)
                or (name == "allowed" and re.search(r"\bused\s+of\s+" + n, summary, re.I))
                or (name == "allowed" and re.search(r"\bof\s+" + n + r"\s+(?:placement starts?|placements?|allowed)\b", summary, re.I)))


def transport_loads(data):
    """Decode MCP JSON or its independent witness, not Stewart control JSON.

    JSON-RPC error codes and arbitrary transport metadata may contain signed
    numbers. Stewart's core payloads, manager replies and records continue to
    use driver_core.strict_loads. Duplicate decoded keys remain ambiguous.
    """
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate transport key %r" % key)
            result[key] = value
        return result

    def no_constant(value):
        raise ValueError("not a JSON number: " + value)

    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data, object_pairs_hook=unique, parse_constant=no_constant)


def mcp_message_loads(data):
    """MCP 2025-11-25 base message envelope; embedded core text stays opaque.

    Sources: modelcontextprotocol.io/specification/2025-11-25/basic and
    /basic/transports; jsonrpc.org/specification, response and error objects.
    """
    value = transport_loads(data)
    if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
        raise ValueError("MCP message must be a JSON-RPC 2.0 object")

    def string(item, label):
        if not isinstance(item, str) or "\0" in item or any(0xD800 <= ord(ch) <= 0xDFFF for ch in item):
            raise ValueError(label + " must be a Unicode string without NUL")

    if "id" in value:
        if isinstance(value["id"], str):
            string(value["id"], "MCP id")
        elif value["id"] is None and "error" in value and "method" not in value:
            pass  # The originating request ID could not be established.
        elif type(value["id"]) is not int:
            raise ValueError("MCP id must be a string or integer")
    if "method" in value:
        string(value["method"], "MCP method")
        if "result" in value or "error" in value:
            raise ValueError("MCP request/notification cannot contain a result or error")
        if "params" in value and not isinstance(value["params"], dict):
            raise ValueError("MCP params must be an object")
    elif ("result" in value) == ("error" in value):
        raise ValueError("MCP response must contain exactly one result or error")
    elif "result" in value:
        if "id" not in value or not isinstance(value["result"], dict):
            raise ValueError("MCP result response needs an id and object result")
    else:
        if "id" not in value:
            raise ValueError("MCP error response needs an id (null when unknown)")
        error = value["error"]
        if not isinstance(error, dict) or type(error.get("code")) is not int:
            raise ValueError("MCP error code must be an integer")
        string(error.get("message"), "MCP error message")
    return value


class CaseStopped(Exception):
    pass


class RelayWitness:
    """Incremental independent traffic and progress, including before a read."""
    def __init__(self, directory, channel):
        self.directory, self.channel = directory, channel

    def event(self, stage, **details):
        self.publish({"kind": "phase", "stage": stage, "pid": os.getpid(),
                      "monotonic_ns": time.monotonic_ns(), **details})

    def publish(self, value):
        raw = compact(value) + b"\n"
        if len(raw) > 4000:
            raise ValueError("relay checkpoint exceeds atomic channel bound")
        # The owner receives this before a potentially blocking file operation.
        if os.write(self.channel, raw) != len(raw):
            raise RuntimeError("incomplete relay checkpoint publication")
        with (self.directory / "worker-events.jsonl").open("ab", buffering=0) as stream:
            if stream.write(raw) != len(raw):
                raise RuntimeError("incomplete relay checkpoint file")

    def bytes(self, name, raw):
        with (self.directory / name).open("ab", buffering=0) as stream:
            if stream.write(raw) != len(raw):
                raise RuntimeError("incomplete relay byte witness: " + name)


def relay_supervised(directory, action, seconds=8):
    """Bound setup, Popen, reads and cleanup in a separately owned session.

    A select deadline cannot bound a read that stalls after readiness. The
    owner never reads relay stdout; its checkpoint pipe is nonblocking and
    drained in bounded batches. This is not a bound on a stalled host/kernel.
    """
    directory.mkdir(mode=0o700)
    started = time.monotonic()
    record = {"budget_seconds": seconds, "cleanup_budget_seconds": 1.5,
              "timed_out": False, "worker_reaped": False, "worker_exit": None,
              "group_stopped": False, "last_phase": None, "result": None,
              "channel_error": None, "signals": []}
    (directory / "controller-start.json").write_bytes(compact(record) + b"\n")
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            os.setsid()
            witness = RelayWitness(directory, write_fd)
            witness.event("worker-session-established", group=os.getpgrp())
            result = action(witness)
            witness.publish({"kind": "result", "result": result})
            os._exit(0)
        except BaseException:
            try:
                RelayWitness(directory, write_fd).publish({"kind": "result", "result": {
                    "error": traceback.format_exc(), "checks": {}}})
            except BaseException:
                pass
            os._exit(1)
    os.close(write_fd)
    record["worker_pid"] = pid
    pending, total = bytearray(), 0

    def drain():
        nonlocal total
        for _ in range(16):
            try:
                raw = os.read(read_fd, 4096)
            except BlockingIOError:
                break
            if not raw:
                break
            total += len(raw)
            if total > 1 << 20:
                record["channel_error"] = "relay checkpoints exceed 1 MiB"
                return
            with (directory / "controller-events.jsonl").open("ab", buffering=0) as stream:
                if stream.write(raw) != len(raw):
                    record["channel_error"] = "incomplete controller checkpoint file"
                    return
            pending.extend(raw)
            while b"\n" in pending:
                line, _, rest = bytes(pending).partition(b"\n")
                pending[:] = rest
                try:
                    row = json.loads(line)
                except ValueError:
                    record["channel_error"] = "invalid relay checkpoint"
                    continue
                if row.get("kind") == "result":
                    record["result"] = row.get("result")
                else:
                    record["last_phase"] = row

    def reap():
        if not record["worker_reaped"]:
            got, status = os.waitpid(pid, os.WNOHANG)
            if got:
                record["worker_reaped"] = True
                record["worker_exit"] = os.waitstatus_to_exitcode(status)

    try:
        while True:
            drain()
            reap()
            if record["worker_reaped"]:
                break
            if time.monotonic() - started >= seconds or record["channel_error"]:
                record["timed_out"] = True
                break
            time.sleep(0.01)
    finally:
        # Reaping the worker is insufficient: its relay may still be alive.
        cleanup_end = time.monotonic() + 1.5
        for sig, allowance in ((signal.SIGTERM, 0.3), (signal.SIGKILL, 1.2)):
            reap()
            state = group_observation(pid)
            if record["worker_reaped"] and state == "absent":
                break
            record["signals"].append({"signal": sig.name, "group_state": state})
            try:
                if state == "present":
                    os.killpg(pid, sig)
                elif not record["worker_reaped"]:
                    # Setup may not have made the session yet. This remains
                    # our unreaped child; never signal the owner's group.
                    os.kill(pid, sig)
            except ProcessLookupError:
                pass
            until = min(cleanup_end, time.monotonic() + allowance)
            while time.monotonic() < until:
                reap()
                if record["worker_reaped"] and group_observation(pid) == "absent":
                    break
                time.sleep(0.01)
        drain()
        reap()
        record["final_group_state"] = group_observation(pid)
        record["group_stopped"] = record["worker_reaped"] and record["final_group_state"] == "absent"
        if (record["result"] or {}).get("stopping_uncertain"):
            record["group_stopped"] = False
        if pending:
            record["channel_error"] = "incomplete final relay checkpoint"
        os.close(read_fd)
        record["elapsed_seconds"] = time.monotonic() - started
        (directory / "controller-result.json").write_bytes(compact(record) + b"\n")
    return record


def relay_success(record):
    result = record.get("result") or {}
    return (record["group_stopped"] and record["worker_exit"] == 0 and not record["timed_out"]
            and not record["channel_error"] and not result.get("error")
            and bool(result.get("checks")) and all(result["checks"].values()))


class RelayObserver:
    def __init__(self, witness):
        self.witness, self.captures = witness, {}

    def read(self, fd, name, wanted=None, seconds=0.6):
        """Read available bytes, or until the wanted bytes/EOF/window end."""
        got, eof = bytearray(), False
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.witness.event("before-select", stream=name, fd=fd, deadline=deadline)
            ready, _, _ = select.select([fd], [], [], max(0, deadline - time.monotonic()))
            self.witness.event("after-select", stream=name, fd=fd, ready=ready)
            if not ready:
                break
            self.witness.event("before-os-read", stream=name, fd=fd, requested_bytes=512)
            try:
                raw = os.read(fd, 512)
            except BlockingIOError:
                self.witness.event("after-os-read", stream=name, fd=fd, outcome="EAGAIN")
                continue
            self.witness.event("after-os-read", stream=name, fd=fd,
                               outcome="bytes" if raw else "EOF", raw_hex=raw.hex())
            self.witness.bytes("observed-" + name + ".bin", raw)
            self.captures.setdefault(name, bytearray()).extend(raw)
            if len(self.captures[name]) > 65536:
                raise ValueError("unexpected relay traffic exceeds 64 KiB")
            if not raw:
                eof = True
                break
            got.extend(raw)
            if wanted is not None and bytes(got) == wanted:
                break
        return bytes(got), eof

    def send(self, fd, name, raw):
        self.witness.bytes("supplied-" + name + ".bin", raw)
        position, deadline = 0, time.monotonic() + 0.6
        while position < len(raw):
            if time.monotonic() >= deadline:
                raise TimeoutError("relay write deadline: " + name)
            _, ready, _ = select.select([], [fd], [], max(0, deadline - time.monotonic()))
            if not ready:
                raise TimeoutError("relay write deadline: " + name)
            self.witness.event("before-os-write", stream=name, fd=fd, bytes=len(raw) - position)
            try:
                size = os.write(fd, raw[position:])
            except BlockingIOError:
                continue
            self.witness.event("after-os-write", stream=name, fd=fd, bytes=size,
                               raw_hex=raw[position:position + size].hex())
            if not size:
                raise RuntimeError("relay write made no progress")
            self.witness.bytes("transmitted-" + name + ".bin", raw[position:position + size])
            position += size


RELAY_REQUEST = b"\x00\xffinput without a final LF\nsecond line\r\x01tail"
RELAY_REPLY = b"\xfe\x00reply without a final LF\r\nsecond line\x7ftail"


def relay_pipe_control(witness):
    observer, checks = RelayObserver(witness), {}
    reader, writer = os.pipe()
    try:
        os.set_blocking(reader, False)
        os.set_blocking(writer, False)
        checks["idle"] = observer.read(reader, "pipe", seconds=0.03) == (b"", False)
        observer.send(writer, "pipe", RELAY_REPLY)
        checks["bytes-while-writer-open"] = observer.read(reader, "pipe", RELAY_REPLY) == (RELAY_REPLY, False)
        os.close(writer)
        writer = None
        checks["empty-eof"] = observer.read(reader, "pipe") == (b"", True)
        return {"checks": checks, "error": None}
    finally:
        os.close(reader)
        if writer is not None:
            os.close(writer)


def relay_traffic(binary, variant, env, workspace, witness):
    """Exercise only the specified byte conduit, without an audit or harness."""
    observer, checks = RelayObserver(witness), {}
    listener = connection = process = None
    stopping_uncertain = False
    try:
        cwd = workspace
        witness.event("before-workspace")
        cwd.mkdir(mode=0o700)
        os.chdir(cwd)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.settimeout(1)
        witness.event("before-listener-bind")
        listener.bind("m")
        listener.listen(1)
        witness.event("before-popen", argv=[str(binary), "__stewart-cc-relay", "m"])
        process = subprocess.Popen([str(binary), "__stewart-cc-relay", "m"], env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        witness.event("after-popen", relay_pid=process.pid)
        if os.getpgid(process.pid) != os.getpgrp():
            stopping_uncertain = True
            process.kill()
            raise RuntimeError("relay escaped the owned worker group")
        connection, _ = listener.accept()
        connection.setblocking(False)
        for stream in (process.stdin, process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False)
        inp, out, peer = process.stdin.fileno(), process.stdout.fileno(), connection.fileno()
        checks["idle-stdout"] = observer.read(out, "stdout", seconds=0.03) == (b"", False)
        checks["idle-socket"] = observer.read(peer, "socket", seconds=0.03) == (b"", False)
        request = b"" if variant == "empty-eof" else RELAY_REQUEST
        reply = b"" if variant == "empty-eof" else RELAY_REPLY
        segments = (slice(0, 1), slice(1, 7), slice(7, None)) if variant == "segmented-open" else (slice(None),)
        for index, segment in enumerate(segments):
            if request:
                observer.send(inp, "stdin", request[segment])
                checks["request-open-%d" % index] = observer.read(peer, "socket", request[segment]) == (request[segment], False)
            if reply:
                observer.send(peer, "socket", reply[segment])
                if variant != "immediate-half-close":
                    checks["reply-open-%d" % index] = observer.read(out, "stdout", reply[segment]) == (reply[segment], False)
        # In this variant, shutdown happens before any nonempty stdout read.
        witness.event("before-peer-half-close", variant=variant)
        connection.shutdown(socket.SHUT_WR)
        witness.event("after-peer-half-close", variant=variant)
        tail, _ = observer.read(out, "stdout", reply if variant == "immediate-half-close" else None,
                                seconds=0.6 if variant == "immediate-half-close" else 0.03)
        checks["half-close-tail"] = tail == (reply if variant == "immediate-half-close" else b"")
        witness.event("before-stdin-close")
        process.stdin.close()
        witness.event("after-stdin-close")
        checks["socket-eof"] = observer.read(peer, "socket") == (b"", True)
        checks["exact-final-stdout"] = bytes(observer.captures.get("stdout", b"")) == reply
        checks["exact-final-socket"] = bytes(observer.captures.get("socket", b"")) == request
        end = time.monotonic() + 0.6
        while process.poll() is None and time.monotonic() < end:
            time.sleep(0.01)
        checks["relay-exit"] = process.poll() == 0
        checks["stdout-eof"] = observer.read(out, "stdout") == (b"", True)
        observer.read(process.stderr.fileno(), "stderr", seconds=0.03)
        return {"checks": checks, "error": None}
    except BaseException:
        return {"checks": checks, "error": traceback.format_exc(), "stopping_uncertain": stopping_uncertain}
    finally:
        witness.event("before-worker-cleanup")
        if connection is not None:
            connection.close()
        if listener is not None:
            listener.close()
        if process:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed:
                    stream.close()
        witness.event("after-worker-cleanup")


def validate_work_path(work):
    """Reject known project ancestry before constructing launch fixtures."""
    if work.resolve().is_relative_to(HERE.parent.parent.resolve()):
        raise ValueError("--work must be outside the driver repository; use a fresh physical temporary directory")


class Driver:
    def __init__(self, binary, work, release=None, selected=None, variant=None):
        validate_work_path(work)
        self.binary, self.work, self.release, self.variant = binary, work, release, variant
        self.selected = set(selected) if selected else {name for name, _ in CASES}
        self.work.mkdir(mode=0o700, parents=False, exist_ok=False)
        source = work / "driver-snapshot"
        source.mkdir()
        for name in ("claude_code.py", "driver_core.py", "rawjson.py"):
            (source / name).write_bytes((HERE / name).read_bytes())
        self.harness_script = source / "claude_code.py"
        self.witness = work / "witness"
        self.witness.mkdir()
        self.commands = work / "commands"
        self.commands.mkdir()
        self.home = work / "manager-home"
        self.home.mkdir()
        self.cwd = work / "manager-cwd"
        self.cwd.mkdir()
        self.env = {"PATH": "/usr/bin:/bin", "HOME": str(self.home),
                    "LANG": "C.UTF-8", "TMPDIR": str(work)}
        self.cases, self.checks, self.controls = [], [], []
        self.notes = []
        self.current = None
        self.serial = 0
        self.archives = []
        self.canaries = []
        self.launch_blocked = None
        self.started = time.monotonic()
        self.save("environment.json", {"platform": platform.platform(),
                  "python": sys.version, "environment": self.env,
                  "binary": str(binary), "binary_sha256": sha(binary.read_bytes()),
                  "release_binary": str(release) if release else None,
                  "release_sha256": sha(release.read_bytes()) if release else None,
                  "variant_binary": str(variant) if variant else None,
                  "variant_sha256": sha(variant.read_bytes()) if variant else None,
                  "surface_sha256": SURFACE_SHA,
                  "driver_sha256": sha(Path(__file__).read_bytes()),
                  "qualification": False, "scope": "offline preparation and synthetic MCP runtime"})

    def save(self, name, obj):
        (self.work / name).write_bytes(compact(obj) + b"\n")

    def check(self, name, ok, detail=None):
        row = {"case": self.current, "name": name, "passed": bool(ok)}
        if not ok:
            row["detail"] = json.loads(json.dumps(detail, default=lambda value:
                {"bytes_hex": value.hex()} if isinstance(value, bytes) else str(value)))
            print("FAIL %s: %s" % (name, detail), flush=True)
        self.checks.append(row)
        return bool(ok)

    def eq(self, name, got, expected):
        return self.check(name, got == expected, {"got": got, "expected": expected})

    def require(self, name, ok, detail=None):
        if not self.check(name, ok, detail):
            raise CaseStopped(name)

    def note(self, name, text):
        """An observation that is reported and decides nothing."""
        self.notes.append({"case": self.current, "name": name, "note": text})
        print("NOTE %s: %s" % (name, text), flush=True)

    def control(self, name, fired, detail="deliberately invalid input was not refused"):
        self.controls.append({"case": self.current, "name": name, "fired": bool(fired)})
        self.check(name + ".fired", fired, detail)

    def runtime_relay_forwarding(self):
        root = self.witness / "relay-forwarding"
        root.mkdir()
        workspaces = self.work / "relay-work"
        workspaces.mkdir()

        def observe(name, action, seconds=8):
            try:
                return relay_supervised(root / name, action, seconds)
            except Exception:
                self.launch_blocked = "relay observer controller failed; stopping is unresolved; see %s" % (root / name)
                raise

        def inspect(name, record):
            self.check(name + ".deadline", not record["timed_out"], record)
            self.check(name + ".group-stopped", record["group_stopped"], record)
            if not record["group_stopped"]:
                self.launch_blocked = "owned relay observer group %s has not been observed stopped; see %s" % (
                    record["worker_pid"], root / name / "controller-result.json")
                raise CaseStopped(self.launch_blocked)
            result = record.get("result") or {}
            self.check(name + ".worker-result", record["worker_exit"] == 0
                       and not record["channel_error"] and not result.get("error")
                       and bool(result.get("checks")), record)
            for label, passed in result.get("checks", {}).items():
                self.check(name + "." + label, passed, result)

        record = observe("pipe-control", relay_pipe_control, 2)
        inspect("pipe-control", record)
        self.control("relay-pipe-observer-idle-open-bytes-eof", relay_success(record),
                     "pipe observer did not observe idle/open-writer bytes/EOF")
        for variant in ("whole-open", "segmented-open", "immediate-half-close", "empty-eof"):
            record = observe(variant, lambda witness: relay_traffic(
                self.binary, variant, self.env, workspaces / variant, witness))
            inspect(variant, record)
            self.control("relay-" + variant, relay_success(record), "relay forwarding comparison did not pass")
        self.note("relay-observer-scope", "Each direct helper worker owns an 8-second deadline plus "
                  "1.5 seconds for observed group stopping. Pipe readiness and nonblocking mode alone "
                  "do not bound a stalled read; the owner never reads helper stdout. Byte and progress "
                  "witnesses remain outside the audit, including after a worker timeout.")

    def cmd(self, label, args, outcome="completed", binary=None, raw=False, env=None, cwd=None, input_bytes=None):
        self.serial += 1
        prefix = "%04d-%s" % (self.serial, label)
        argv = [str(binary or self.binary)] + [str(x) for x in args] + ([] if raw else ["--json"])
        before = {str(a): snapshot(a) for a in self.archives}
        starts_before = {str(p): p.read_bytes() if p.exists() else None for p in self.canaries}
        started = time.monotonic()
        try:
            process = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     env=env or self.env, cwd=cwd or self.cwd, input=input_bytes, timeout=30)
        except subprocess.TimeoutExpired as exc:
            (self.commands / (prefix + ".stdout")).write_bytes(exc.stdout or b"")
            (self.commands / (prefix + ".stderr")).write_bytes(exc.stderr or b"")
            self.save("commands/" + prefix + ".json", {"argv": argv, "timeout": True})
            self.require(label + ".deadline", False, "local command exceeded 30 seconds")
        (self.commands / (prefix + ".stdout")).write_bytes(process.stdout)
        (self.commands / (prefix + ".stderr")).write_bytes(process.stderr)
        self.last_stdout = process.stdout
        self.save("commands/" + prefix + ".json", {"argv": argv, "exit": process.returncode,
                  "elapsed_seconds": time.monotonic() - started})
        for archive in self.archives:
            after = snapshot(archive)
            self.eq(label + ".immutable." + archive.parent.name,
                    immutable_changes(before[str(archive)], after), [])
        if args[0] != "run":
            self.eq(label + ".no-harness-start",
                    {str(p): p.read_bytes() if p.exists() else None for p in self.canaries}, starts_before)
        if raw:
            self.eq(label + ".exit", process.returncode, 0)
            try:
                metadata = strict_loads(process.stderr)
            except ValueError as exc:
                self.require(label + ".metadata", False, str(exc))
            self.eq(label + ".verified", metadata.get("verified"), True)
            self.eq(label + ".digest", metadata.get("sha256"), sha(process.stdout))
            self.eq(label + ".size", metadata.get("size"), len(process.stdout))
            return process.stdout
        try:
            reply = strict_loads(process.stdout)
        except ValueError as exc:
            self.require(label + ".reply", False, str(exc))
        self.require(label + ".object", isinstance(reply, dict), reply)
        self.eq(label + ".schema", reply.get("schema"), "stewart.reply/2")
        self.eq(label + ".operation", reply.get("operation"), args[0])
        if outcome is not None:
            self.eq(label + ".outcome", reply.get("outcome"), outcome)
        expected_exit = {"completed": 0, "refused": 3, "failed": 4}.get(reply.get("outcome"))
        if args[0] == "run" and reply.get("outcome") == "completed" and reply.get("data", {}).get("ending") == "interrupted":
            expected_exit = 5
        self.eq(label + ".exit", process.returncode, expected_exit)
        return reply

    def plain(self, label, args, binary=None):
        """Run a command for its human output; keep exact argv, stdout and stderr."""
        self.serial += 1
        prefix = "%04d-%s" % (self.serial, label)
        argv = [str(binary or self.binary)] + [str(x) for x in args]
        starts_before = {str(p): p.read_bytes() if p.exists() else None for p in self.canaries}
        process = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=self.env, cwd=self.cwd, timeout=30)
        (self.commands / (prefix + ".stdout")).write_bytes(process.stdout)
        (self.commands / (prefix + ".stderr")).write_bytes(process.stderr)
        self.save("commands/" + prefix + ".json", {"argv": argv, "exit": process.returncode})
        self.eq(label + ".no-harness-start",
                {str(p): p.read_bytes() if p.exists() else None for p in self.canaries}, starts_before)
        return process.returncode, process.stdout.decode("utf-8", "replace"), process.stderr.decode("utf-8", "replace")

    def facts(self, label, text, words):
        """Presence and relevance: each stated fact's words appear, case-insensitively."""
        lowered = text.lower()
        for word in words:
            self.check(label + ".states." + word.replace(" ", "-")[:32], word.lower() in lowered, text[:600])

    def fixture(self, label, family="open-inquiry", binary=None, scenario=None, timeout=600, placements=3,
                effort=None, *, python=None):
        root = self.work / label
        root.mkdir()
        witness = self.witness / label
        witness.mkdir()
        folder, archive, destination = root / "submission", root / "archive", root / "returns"
        destination.mkdir()
        self.archives.append(archive)
        reply = self.cmd(label + ".new", ["new", folder, "--archive", archive], binary=binary)
        self.require(label + ".reference", reply.get("outcome") == "completed", reply)
        reference = reply["data"]["reference"]
        launch_dir = root / "runtime"
        launch_dir.mkdir()
        for directory in ("config", "home", "temporary"):
            (launch_dir / directory).mkdir()
        executable = launch_dir / "synthetic-harness"
        if scenario is None:
            executable.write_bytes(CANARY)
        else:
            scenario_path = root / "scenario.json"
            scenario_path.write_bytes(compact({"mode": scenario, "witness": str(witness),
                       "marker": str(executable) + ".started", "config": str(launch_dir / "config"),
                       "version": "synthetic-offline-1", "model": MODEL, "family": family,
                       "session": label + "-session-1", "account": ACCOUNT,
                       "kept": KEPT, "queued": QUEUED, "cancelled": CANCELLED, "duplicate": DUPLICATE,
                       "second_relay": SECOND_RELAY,
                       "auth_private": "synthetic-auth-private-output-" + label}) + b"\n")
            (witness / "scenario-initial.json").write_bytes(scenario_path.read_bytes())
            executable.write_bytes(synthetic_executable(self.harness_script, scenario_path, witness, python=python))
        executable.chmod(0o700)
        self.canaries.append(Path(str(executable) + ".started"))
        launch = {"executable": str(executable), "sha256": sha(executable.read_bytes()),
                  "version": "synthetic-offline-1", "platform": platform_name(),
                  "config_directory": str(launch_dir / "config"), "home": str(launch_dir / "home"),
                  "temporary_directory": str(launch_dir / "temporary")}
        # Noncompact launch bytes make reserialization an observable binding error.
        launch_raw = json.dumps(launch, ensure_ascii=False, indent=2).encode()
        tools = compact(expected_tools(family))
        check = {"surface_sha256": SURFACE_SHA,
                 "launch_sha256": sha(launch_raw), "tools_sha256": sha(mcp_tools(tools)),
                 "model": MODEL, "checked_at": "2026-11-10T00:00:00.000Z",
                 "evidence_sha256": sha(b"synthetic offline attestation; no model or signature check"),
                 "outcome": "observed"}
        profile = (b'{"schema":' + compact(PROFILE_SCHEMA) + b',"launch":' + launch_raw
                   + b',"installation":' + compact({"manifest_sha256": sha(b"synthetic manifest"),
                     "signer": SIGNER, "binary_sha256": launch["sha256"]})
                   + b',"check":' + compact(check) + b'}\n')
        profile_path = root / "profile.json"
        profile_path.write_bytes(profile)
        body = b"Inspect only the selected report. It is a supplied claim.\r\nKeep uncertainty explicit.\n"
        material = "Supplied report: café passed.\r\nThis is not an observed execution.\n".encode()
        fields = {"stewart": "question/1", "family": family, "model": MODEL,
                  "destination": str(destination), "runtime-profile": str(profile_path),
                  "max-placements": str(placements), "placement-timeout-seconds": str(timeout)}
        if effort is not None:
            fields["effort"] = effort
        (folder / "materials" / "report.txt").write_bytes(material)
        fixture = {"label": label, "root": root, "folder": folder, "archive": archive,
                   "reference": reference, "profile_path": profile_path, "profile": profile,
                   "family": family, "tools": tools, "fields": fields, "body": body,
                   "launch": launch, "effort": effort,
                   "material": material, "witness": witness, "executable": executable,
                   "limits": {"max_placements": placements, "placement_timeout_seconds": timeout},
                   "scenario": root / "scenario.json" if scenario else None}
        self.question(fixture)
        for name, data in (("profile.json", profile), ("question-file", fixture["question"]),
                           ("question-body", body), ("report.txt", material), ("tools.json", tools),
                           ("mcp-tools.json", mcp_tools(tools)), ("synthetic-harness", executable.read_bytes())):
            (witness / name).write_bytes(data)
        return fixture

    def question(self, fixture, fields=None):
        fields = fixture["fields"] if fields is None else fields
        content = ("---\n" + "".join("%s: %s\n" % item for item in fields.items()) + "---\n").encode() + fixture["body"]
        (fixture["folder"] / "question.md").write_bytes(content)
        fixture["question"] = content
        number = fixture.get("question_revision", 0) + 1
        fixture["question_revision"] = number
        (fixture["witness"] / ("question-input-%03d.md" % number)).write_bytes(content)

    def prepare(self, f, suffix="prepare", expected="completed"):
        reply = self.cmd(f["label"] + "." + suffix, ["prepare", f["reference"]], expected)
        if expected == "completed":
            self.require(f["label"] + "." + suffix + ".usable", reply.get("outcome") == "completed", reply)
        elif expected == "refused":
            self.eq(f["label"] + "." + suffix + ".no-preparation",
                    reply.get("effects", {}).get("preparation"), "none")
        return reply

    def arrangement(self, f, data, raw):
        label = f["label"] + ".arrangement"
        node = parse(raw)
        if node.get("record"):
            node = node.get("body")
        obj = strict_loads(node.raw)
        self.eq(label + ".keys", sorted(obj), sorted(ARRANGEMENT_KEYS))
        expected = {"schema": ARRANGEMENT_SCHEMA, "model": MODEL,
                    "orientation": ORIENTATION_ID,
                    "system_prompt": RUNTIME_ORIENTATION + "\n\n" + FAMILY_TEXT[f["family"]],
                    "runtime": {"kind": "claude-code/1", "profile_path": str(f["profile_path"]),
                                "profile": f["profile"].decode()},
                    "profile_sha256": sha(f["profile"]), "surface_sha256": SURFACE_SHA,
                    "effort": f["effort"],
                    "limits": f["limits"], "harness_max_turns": 200,
                    "harness_max_output_tokens": 16000, "texts": TEXTS}
        for key, value in expected.items():
            self.eq(label + "." + key, obj.get(key), value)
        self.eq(label + ".reading", obj.get("reading"), {
            "read_page_bytes": 65536, "binary_page_bytes": 49152, "search_text_bytes": 1024,
            "search_hits_per_page": 128, "search_context_bytes_per_page": 32768,
            "context_bytes_per_hit": 240, "list_page_materials": 128, "tool_input_bytes": 4194304})
        system = compact([{"type": "text", "text": RUNTIME_ORIENTATION},
                          {"type": "text", "text": FAMILY_TEXT[f["family"]]}])
        for key, value in (("system", system), ("tools", f["tools"]), ("mcp_tools", mcp_tools(f["tools"])),
                           ("surface", SURFACE)):
            actual = node.get(key)
            self.eq(label + "." + key + "-bytes", actual.raw.decode() if actual else None, value.decode())
        bindings = obj.get("bindings", {})
        self.eq(label + ".binding-keys", sorted(bindings), ["material_index_sha256", "question_body_sha256"])
        self.eq(label + ".question-binding", bindings.get("question_body_sha256"), sha(f["body"]))
        material = (f["witness"] / "report.txt").read_bytes()
        index = {"files": [{"name": "materials/report.txt", "size": len(material),
                            "sha256": sha(material), "lines": material.count(b"\n")}], "directories": ["materials"]}
        self.eq(label + ".material-index-binding", bindings.get("material_index_sha256"), sha(compact(index)))
        self.eq(label + ".reply-digest", data["arrangement"]["sha256"], sha(raw))
        self.eq(label + ".settings-runtime", data["settings"].get("runtime"), expected["runtime"])
        self.eq(label + ".settings-limits", data["settings"].get("limits"), f["limits"])

    def accept(self, f):
        prepared = self.prepare(f)
        question = (f["witness"] / "question-file").read_bytes()
        body = (f["witness"] / "question-body").read_bytes()
        material = (f["witness"] / "report.txt").read_bytes()
        self.eq(f["label"] + ".question-inventory", prepared["data"].get("question"),
                {"file_bytes": len(question), "file_sha256": sha(question),
                 "body_bytes": len(body), "body_sha256": sha(body)})
        self.eq(f["label"] + ".material-inventory", prepared["data"].get("materials"),
                {"count": 1, "bytes": len(material), "directories": ["materials"],
                 "files": [{"name": "materials/report.txt", "size": len(material),
                            "sha256": sha(material), "lines": material.count(b"\n")}]})
        raw = Path(prepared["data"]["arrangement"]["machine"]).read_bytes()
        self.arrangement(f, prepared["data"], raw)
        reply = self.cmd(f["label"] + ".commission",
                         ["commission", f["reference"], prepared["data"]["prepared"], "--i-am-finished"])
        self.require(f["label"] + ".accepted", reply.get("outcome") == "completed", reply)
        self.eq(f["label"] + ".acceptance", reply.get("effects", {}).get("acceptance"), "accepted")
        needs = reply.get("data", {}).get("run_needs", [])
        run_needs = json.dumps(needs)
        self.check(f["label"] + ".no-api-credential-request",
                   "ANTHROPIC_API_KEY" not in run_needs and "--key-fd" not in run_needs, run_needs)
        self.require(f["label"] + ".run-needs-four", isinstance(needs, list) and len(needs) == 4
                     and all(isinstance(item, str) for item in needs), needs)
        for index, words in enumerate((("authority", "restart"), ("harness", "login", "extra usage"),
                                       ("credential", "fallback"),
                                       ("foreground", "deadline", "background", "unknown"))):
            self.facts(f["label"] + ".run-needs-%d" % (index + 1), needs[index], words)
        receipt = self.cmd(f["label"] + ".receipt", ["receipt", f["reference"], "--verify"])
        self.eq(f["label"] + ".receipt-settings", receipt["data"].get("settings"), prepared["data"]["settings"])
        self.eq(f["label"] + ".receipt-run-needs", receipt["data"].get("run_needs"), needs)
        for item, expected in (("question-file", (f["witness"] / "question-file").read_bytes()),
                               ("question-body", (f["witness"] / "question-body").read_bytes()),
                               ("materials/report.txt", (f["witness"] / "report.txt").read_bytes()),
                               ("arrangement", raw)):
            got = self.cmd(f["label"] + ".read-" + item.replace("/", "-"),
                           ["receipt", f["reference"], "--read", item], raw=True)
            self.eq(f["label"] + ".read-" + item, got.hex(), expected.hex())
        status_reply = self.cmd(f["label"] + ".status", ["status", f["reference"]])
        self.eq(f["label"] + ".not-started", status_reply["data"].get("condition"), "not_started")
        self.eq(f["label"] + ".launched", status_reply["data"].get("headline", {}).get("launched"), "no")
        usage = {"runtime": "claude-code/1", "placements": 0, "unknown_intervals": 0,
                 "stopped": 0, "reported_placements": 0, "reported_main_loop": None,
                 "provider_completeness": "unverified"}
        self.eq(f["label"] + ".allowances", status_reply["data"].get("allowances"),
                {"runtime": "claude-code/1", "placements": {"used": 0, "limit": f["limits"]["max_placements"],
                 "remaining": f["limits"]["max_placements"]},
                 "placement_timeout_seconds": f["limits"]["placement_timeout_seconds"], "usage": usage})
        for key in ("provider_url_override", "provider_proxy"):
            self.check(f["label"] + ".common-member." + key,
                       key in status_reply["data"] and status_reply["data"][key] is None,
                       status_reply["data"].get(key, "absent"))
        self.summary_facts(f["label"] + ".summary", status_reply["data"].get("summary"), f, 0)
        return receipt, status_reply, raw

    def summary_facts(self, label, summary, f, used):
        """The human summary's placement facts and its agreement in number."""
        if not self.check(label + ".text", isinstance(summary, str), summary):
            return
        limits = f["limits"]
        timeout = limits["placement_timeout_seconds"]
        self.check(label + ".timeout", re.search(r"\b%d seconds?\b" % timeout, summary) is not None, summary)
        for name, value in (("used", used), ("allowed", limits["max_placements"]),
                            ("remaining", limits["max_placements"] - used)):
            self.check(label + ".starts-" + name, summary_placement_fact(summary, name, value), summary)
        self.check(label + ".number-agreement",
                   re.search(r"\b1 placements\b|\b1 have\b|\b(?:0|[2-9]|[1-9][0-9]+) placement has\b", summary) is None,
                   summary)
        if used == 1:
            self.check(label + ".singular", re.search(r"\b1 placement\b", summary) is not None, summary)
        else:
            self.check(label + ".plural", re.search(r"\b%d placements\b" % used, summary) is not None, summary)

    def families(self):
        for family in FAMILY_TEXT:
            self.accept(self.fixture(family, family))

    def profile_refusal(self, label, reply, named=()):
        """A profile prepare cannot accept: the stated reason and the exact surface."""
        self.eq(label + ".reason", reply.get("reason"), "runtime_profile_invalid")
        surface = (reply.get("data") or {}).get("surface")
        if not self.check(label + ".surface-object", isinstance(surface, dict), reply.get("data")):
            return
        self.eq(label + ".surface-keys", list(surface), ["schema", "sha256", "document"])
        self.eq(label + ".surface-schema", surface.get("schema"), SURFACE_SCHEMA)
        self.eq(label + ".surface-digest", surface.get("sha256"), SURFACE_SHA)
        document = parse(self.last_stdout).get("data").get("surface").get("document")
        self.eq(label + ".surface-document-bytes", document.raw.decode() if document else None,
                SURFACE.decode())
        message = reply.get("message") or ""
        for value in named:
            self.check(label + ".message-names." + value[:24], value in message, message)

    def replace_profile(self, f, label, mutated):
        f["profile_path"].write_bytes(mutated)
        (f["witness"] / (label + ".json")).write_bytes(mutated)

    def surface_binding(self):
        f = self.fixture("surface")
        self.prepare(f, "positive")
        # A check naming another surface refuses and tells the manager, without
        # any launch, the digest and document this binary requires.
        other = sha(SURFACE + b" ")
        node = parse(f["profile"]).get("check").get("surface_sha256")
        self.replace_profile(f, "other-surface",
                             f["profile"][:node.start] + compact(other) + f["profile"][node.end:])
        reply = self.prepare(f, "other-surface", "refused")
        self.control("other-surface", reply.get("outcome") == "refused")
        self.profile_refusal("surface.other-surface", reply, named=(other, SURFACE_SHA))
        # The earlier profile identifier is refused by name; nothing reads it.
        earlier = "stewart.claude-code.profile/1"
        renamed = f["profile"].replace(compact(PROFILE_SCHEMA), compact(earlier), 1)
        self.replace_profile(f, "earlier-identifier", renamed)
        reply = self.prepare(f, "earlier-identifier", "refused")
        self.control("earlier-profile-identifier", reply.get("outcome") == "refused")
        self.profile_refusal("surface.earlier-identifier", reply, named=(earlier, PROFILE_SCHEMA))
        # The whole earlier form, with a correct writer digest, is refused too.
        writer = compact(sha(self.binary.read_bytes()))
        earlier_form = renamed.replace(b'"surface_sha256":' + compact(SURFACE_SHA),
                                       b'"writer_sha256":' + writer, 1)
        self.require("surface.earlier-form-built", earlier_form != renamed, "check member not found")
        self.replace_profile(f, "earlier-form", earlier_form)
        reply = self.prepare(f, "earlier-form", "refused")
        self.control("earlier-profile-form", reply.get("outcome") == "refused")
        self.profile_refusal("surface.earlier-form", reply, named=(earlier,))
        # The current identifier admits neither the old member in place of the
        # surface binding nor beside it.
        in_place = f["profile"].replace(b'"surface_sha256":' + compact(SURFACE_SHA),
                                        b'"writer_sha256":' + writer, 1)
        beside = f["profile"].replace(b'"surface_sha256":',
                                      b'"writer_sha256":' + writer + b',"surface_sha256":', 1)
        for label, mutated in (("writer-member-in-place", in_place), ("writer-member-beside", beside)):
            self.require("surface." + label + "-built", mutated != f["profile"], "check member not found")
            self.replace_profile(f, label, mutated)
            reply = self.prepare(f, label, "refused")
            self.control(label, reply.get("outcome") == "refused")
            self.profile_refusal("surface." + label, reply)
        f["profile_path"].write_bytes(f["profile"])
        self.prepare(f, "restored")

    def surface_two_builds(self):
        if self.variant is None:
            return "--variant-binary was not supplied; writer invariance of the check not exercised"
        digests = sha(self.binary.read_bytes()), sha(self.variant.read_bytes())
        self.require("two-builds.distinct-writers", digests[0] != digests[1], digests)
        a = self.fixture("two-builds-a")
        _, _, raw_a = self.accept(a)
        # The second writer creates its own reference and is given the very
        # same profile file: same path, same bytes, same check.
        b = self.fixture("two-builds-b", binary=self.variant)
        self.question(b, dict(b["fields"], **{"runtime-profile": str(a["profile_path"])}))
        prepared = self.cmd("two-builds-b.prepare", ["prepare", b["reference"]], binary=self.variant)
        self.require("two-builds-b.accepts-same-profile", prepared.get("outcome") == "completed", prepared)
        raw_b = Path(prepared["data"]["arrangement"]["machine"]).read_bytes()
        nodes = []
        for raw in (raw_a, raw_b):
            node = parse(raw)
            nodes.append(node.get("body") if node.get("record") else node)
        for name, node in zip(("a", "b"), nodes):
            surface, digest = node.get("surface"), node.get("surface_sha256")
            self.eq("two-builds-%s.surface-bytes" % name, surface.raw.decode() if surface else None,
                    SURFACE.decode())
            self.eq("two-builds-%s.surface-digest" % name, digest.value() if digest else None, SURFACE_SHA)
        self.eq("two-builds-b.same-profile-captured",
                prepared["data"]["settings"].get("runtime", {}).get("profile"), a["profile"].decode())
        # Firing control under the second writer: it requires the same digest.
        other = sha(SURFACE + b" ")
        node = parse(a["profile"]).get("check").get("surface_sha256")
        self.replace_profile(a, "variant-other-surface",
                             a["profile"][:node.start] + compact(other) + a["profile"][node.end:])
        reply = self.cmd("two-builds-b.other-surface", ["prepare", b["reference"]], "refused",
                         binary=self.variant)
        self.control("variant-other-surface", reply.get("outcome") == "refused")
        self.profile_refusal("two-builds-b.other-surface", reply, named=(other, SURFACE_SHA))
        a["profile_path"].write_bytes(a["profile"])
        # Sharing a check does not share an audit: the one-writer rule stands.
        marker = Path(str(a["executable"]) + ".started")
        reply = self.cmd("two-builds.variant-run-on-first-audit", ["run", a["reference"]], "refused",
                         binary=self.variant)
        self.eq("two-builds.writer-mismatch", reply.get("reason"), "writer_mismatch")
        self.check("two-builds.no-harness-start", not marker.exists(), str(marker))
        self.control("one-writer-per-audit", reply.get("outcome") == "refused"
                     and reply.get("reason") == "writer_mismatch" and not marker.exists())

    def binding_controls(self):
        f = self.fixture("binding")
        self.prepare(f, "positive")
        for section, key, value in (
                ("check", "surface_sha256", "0" * 64),
                ("check", "launch_sha256", sha(compact(json.loads(f["profile"])["launch"]))),
                ("check", "tools_sha256", "0" * 64), ("check", "model", "wrong-model"),
                ("check", "outcome", "unobserved"), ("installation", "signer", "0" * 40),
                ("installation", "binary_sha256", "0" * 64)):
            # Replace only the selected value, preserving the original launch span.
            node = parse(f["profile"]).get(section).get(key)
            mutated = f["profile"][:node.start] + compact(value) + f["profile"][node.end:]
            f["profile_path"].write_bytes(mutated)
            (f["witness"] / (section + "-" + key + ".json")).write_bytes(mutated)
            reply = self.prepare(f, section + "-" + key, "refused")
            self.control(section + "-" + key, reply.get("outcome") == "refused")
            named = "tool" if key == "tools_sha256" else key.split("_")[0]
            self.profile_refusal("binding." + section + "-" + key, reply, named=(named,))
        changed_launch = json.loads(f["profile"])["launch"]
        changed_launch["platform"] = "linux-x86_64" if platform_name() != "linux-x86_64" else "macos-aarch64"
        node = parse(f["profile"]).get("launch")
        changed_raw = compact(changed_launch)
        mutated = f["profile"][:node.start] + changed_raw + f["profile"][node.end:]
        node = parse(mutated).get("check").get("launch_sha256")
        mutated = mutated[:node.start] + compact(sha(changed_raw)) + mutated[node.end:]
        f["profile_path"].write_bytes(mutated)
        (f["witness"] / "wrong-platform-profile.json").write_bytes(mutated)
        reply = self.prepare(f, "platform", "refused")
        self.control("platform", reply.get("outcome") == "refused")
        self.profile_refusal("binding.platform", reply, named=("platform",))
        f["profile_path"].write_bytes(f["profile"])
        executable = f["executable"].read_bytes()
        f["executable"].write_bytes(executable + b"# changed digest\n")
        (f["witness"] / "changed-executable").write_bytes(f["executable"].read_bytes())
        reply = self.prepare(f, "executable-changed", "refused")
        self.control("executable-digest", reply.get("outcome") == "refused")
        self.profile_refusal("binding.executable-changed", reply)
        f["executable"].write_bytes(executable)
        # External JSON whitespace changes no launch value or check binding.
        f["profile_path"].write_bytes(b" \n" + f["profile"] + b"\t")
        (f["witness"] / "outer-whitespace-profile.json").write_bytes(f["profile_path"].read_bytes())
        self.prepare(f, "outer-whitespace-invariance")
        f["profile_path"].write_bytes(f["profile"])
        self.prepare(f, "restored")

    def profile_input(self):
        f = self.fixture("profile-input")
        self.prepare(f, "positive")
        boundary = f["profile"] + b" " * (65536 - len(f["profile"]))
        f["profile_path"].write_bytes(boundary)
        (f["witness"] / "exact-64-kib.json").write_bytes(boundary)
        self.prepare(f, "exact-64-kib")
        for label, mutated in (
                ("unknown-member", f["profile"].rstrip()[:-1] + b',"unknown":true}'),
                ("duplicate-member", f["profile"].replace(b'{"schema":', b'{"schema":"duplicate","schema":', 1)),
                ("over-64-kib", boundary + b" "),
                ("invalid-utf8", f["profile"] + b"\xff")):
            f["profile_path"].write_bytes(mutated)
            (f["witness"] / (label + ".json")).write_bytes(mutated)
            reply = self.prepare(f, label, "refused")
            self.control(label, reply.get("outcome") == "refused")
            self.profile_refusal("profile-input." + label, reply)
        f["profile_path"].unlink()
        original = f["root"] / "original-profile.json"
        original.write_bytes(f["profile"])
        f["profile_path"].symlink_to(original)
        reply = self.prepare(f, "file-link", "refused")
        self.control("profile-file-link", reply.get("outcome") == "refused")
        self.profile_refusal("profile-input.file-link", reply)
        f["profile_path"].unlink()
        f["profile_path"].mkdir()
        reply = self.prepare(f, "directory", "refused")
        self.control("profile-not-regular", reply.get("outcome") == "refused")
        self.profile_refusal("profile-input.directory", reply)
        f["profile_path"].rmdir()
        os.mkfifo(f["profile_path"], mode=0o600)
        reply = self.prepare(f, "fifo", "refused")
        self.control("profile-fifo", reply.get("outcome") == "refused")
        self.profile_refusal("profile-input.fifo", reply)
        f["profile_path"].unlink()
        f["profile_path"].write_bytes(f["profile"])
        alias = f["root"] / "directory-link"
        alias.symlink_to(f["root"], target_is_directory=True)
        fields = dict(f["fields"], **{"runtime-profile": str(alias / "profile.json")})
        self.question(f, fields)
        reply = self.prepare(f, "directory-link", "refused")
        self.control("profile-directory-link", reply.get("outcome") == "refused")
        self.profile_refusal("profile-input.directory-link", reply)
        self.question(f)
        self.prepare(f, "restored")

    def limit_fields(self):
        f = self.fixture("limit-fields")
        self.prepare(f, "positive")
        for key, upper in (("max-placements", 10000), ("placement-timeout-seconds", 86400)):
            for value in ("1", str(upper)):
                self.question(f, dict(f["fields"], **{key: value}))
                self.prepare(f, key + "-" + value)
            for value in ("0", str(upper + 1), "01", "-1"):
                self.question(f, dict(f["fields"], **{key: value}))
                reply = self.prepare(f, key + "-" + value, "refused")
                self.control(key + "-" + value, reply.get("outcome") == "refused")
                self.defect("limit-fields." + key + "-" + value, reply, "setting_invalid", key)
            fields = dict(f["fields"])
            del fields[key]
            self.question(f, fields)
            reply = self.prepare(f, key + "-missing", "refused")
            self.control(key + "-missing", reply.get("outcome") == "refused")
            self.defect("limit-fields." + key + "-missing", reply, "setting_missing", key)
        # A runtime question admits no Messages limit, even a valid one.
        for key in ("limit-turns", "limit-input-tokens", "limit-output-tokens"):
            self.question(f, dict(f["fields"], **{key: "200"}))
            reply = self.prepare(f, key, "refused")
            self.control(key, reply.get("outcome") == "refused")
            self.defect("limit-fields." + key, reply, "setting_invalid", key)
        # The removed version is refused by name; restoring only that line prepares.
        removed = "question/claude-code/1"
        self.question(f, dict(f["fields"], stewart=removed))
        reply = self.prepare(f, "removed-version", "refused")
        self.control("removed-question-version", reply.get("outcome") == "refused")
        for value in (removed, "question/1"):
            self.check("limit-fields.removed-version.names." + value, value in (reply.get("message") or ""),
                       reply.get("message"))
        self.question(f)
        self.prepare(f, "version-restored")
        fields = {key: value for key, value in f["fields"].items()
                  if key not in ("runtime-profile", "max-placements", "placement-timeout-seconds")}
        fields.update({"stewart": "question/1", "limit-turns": "200",
                       "limit-input-tokens": "20000000", "limit-output-tokens": "400000"})
        self.question(f, fields)
        self.prepare(f, "api-positive")
        # Naming the profile makes it a runtime question, which these limits then defeat.
        self.question(f, dict(fields, **{"runtime-profile": f["fields"]["runtime-profile"]}))
        reply = self.prepare(f, "runtime-profile-with-limits", "refused")
        self.control("runtime-profile-with-limits", reply.get("outcome") == "refused")
        # Without the profile, a placement field has nothing to bound.
        for key in ("max-placements", "placement-timeout-seconds"):
            self.question(f, dict(fields, **{key: f["fields"][key]}))
            reply = self.prepare(f, key + "-without-profile", "refused")
            self.control(key + "-without-profile", reply.get("outcome") == "refused")
            self.defect("limit-fields." + key + "-without-profile", reply, "setting_invalid", key)
        self.question(f)
        self.prepare(f, "restored")

    def defect(self, label, reply, reason, key):
        self.eq(label + ".reason", reply.get("reason"), reason)
        self.check(label + ".names-key", key in (reply.get("message") or ""), reply.get("message"))

    def help_and_presentation(self):
        # The build notice and the added topic.
        status, overview, _ = self.plain("help.overview", ["help"])
        self.eq("help.overview-exit", status, 0)
        notice = overview.split("\n\n", 1)[0]
        self.check("help.notice-points-to-topic", "stewart help runtime" in notice, notice)
        self.check("help.notice-names-no-source-path", "/" not in notice and ".md" not in notice, notice)
        topics = [line for line in overview.splitlines() if line.startswith("Topics:")]
        self.check("help.topics-line", len(topics) == 1 and topics[0].rstrip().endswith("runtime")
                   and all(name in topics[0] for name in ("commands", "forms", "limits", "reader", "close")),
                   topics)
        status, topic, _ = self.plain("help.runtime", ["help", "runtime"])
        self.eq("help.runtime-exit", status, 0)
        self.facts("help.runtime", topic, (
            "question/1", "limit-", "runtime-profile", "max-placements", "placement-timeout-seconds",
            PROFILE_SCHEMA, "executable", "check", "surface", "prepare",
            "login", "extra usage", "--key-fd", "Messages API", "foreground", "deadline", "unknown"))
        for name, bound in (("max-placements", "10,?000"), ("placement-timeout-seconds", "86,?400")):
            self.check("help.runtime.bound." + name, re.search(r"\b1\b.{0,12}\b" + bound + r"\b", topic) is not None,
                       topic[:900])
        status, _, complaint = self.plain("help.unknown-topic", ["help", "no-such-topic"])
        self.check("help.unknown-topic-refused", status != 0, status)
        self.check("help.unknown-topic-lists-runtime", "runtime" in complaint, complaint)
        self.control("unknown-help-topic", status != 0)
        # Human preparation and receipt name the profile by path and digest only.
        f = self.fixture("presentation")
        digest = sha(f["profile"])
        status, shown, _ = self.plain("presentation.prepare", ["prepare", f["reference"]])
        self.eq("presentation.prepare-exit", status, 0)
        prepared = self.prepare(f, "prepare-json")
        self.eq("presentation.json-keeps-profile-text",
                prepared["data"]["settings"].get("runtime", {}).get("profile"), f["profile"].decode())
        reply = self.cmd("presentation.commission",
                         ["commission", f["reference"], prepared["data"]["prepared"], "--i-am-finished"])
        self.require("presentation.accepted", reply.get("outcome") == "completed", reply)
        status, receipt, _ = self.plain("presentation.receipt", ["receipt", f["reference"]])
        self.eq("presentation.receipt-exit", status, 0)
        for name, text in (("prepare", shown), ("receipt", receipt)):
            self.check("presentation.%s.profile-path" % name, str(f["profile_path"]) in text, text[:800])
            self.check("presentation.%s.profile-digest" % name, digest in text, text[:800])
            for fragment in ('"installation"', SIGNER, '"evidence_sha256"'):
                self.check("presentation.%s.no-profile-text.%s" % (name, fragment.strip('"')[:16]),
                           fragment not in text, fragment)
        status, summary, _ = self.plain("presentation.status", ["status", f["reference"]])
        self.eq("presentation.status-exit", status, 0)
        self.summary_facts("presentation.status", summary, f, 0)

    def source_invariance(self):
        f = self.fixture("source-invariance")
        receipt, status_reply, raw = self.accept(f)
        f["profile_path"].write_bytes(b'{"changed":"source is no longer the captured profile"}\n')
        (f["folder"] / "question.md").write_bytes(b"source question changed\n")
        (f["folder"] / "materials" / "report.txt").write_bytes(b"source material changed\n")
        for name, path in (("changed-profile.json", f["profile_path"]),
                           ("changed-question.md", f["folder"] / "question.md"),
                           ("changed-report.txt", f["folder"] / "materials" / "report.txt")):
            (f["witness"] / name).write_bytes(path.read_bytes())
        other_home, other_cwd = f["root"] / "other-home", f["root"] / "other-cwd"
        other_home.mkdir()
        other_cwd.mkdir()
        env = dict(self.env, HOME=str(other_home))
        after = self.cmd("source-invariance.receipt-after", ["receipt", f["reference"], "--verify"], env=env, cwd=other_cwd)
        self.eq("source-invariance.receipt-fixed", after.get("data"), receipt.get("data"))
        status_after = self.cmd("source-invariance.status-after", ["status", f["reference"]], env=env, cwd=other_cwd)
        self.eq("source-invariance.status-fixed", status_after.get("data"), status_reply.get("data"))
        for item, expected in (("arrangement", raw), ("question-file", (f["witness"] / "question-file").read_bytes()),
                               ("materials/report.txt", (f["witness"] / "report.txt").read_bytes())):
            actual = self.cmd("source-invariance.read-after-" + item.replace("/", "-"),
                              ["receipt", f["reference"], "--read", item], raw=True, env=env, cwd=other_cwd)
            self.eq("source-invariance.fixed-" + item, actual.hex(), expected.hex())

    def release_gate(self):
        if self.release is None:
            return "--release-binary was not supplied; featureless rejection not checked"
        f = self.fixture("release-gate", binary=self.release)
        reply = self.cmd("release-gate.runtime-question", ["prepare", f["reference"]], "refused", binary=self.release)
        self.control("featureless-runtime-question", reply.get("outcome") == "refused")
        self.eq("release-gate.runtime-question.reason", reply.get("reason"), "front_matter_invalid")
        fields = {key: value for key, value in f["fields"].items()
                  if key not in ("runtime-profile", "max-placements", "placement-timeout-seconds")}
        fields.update({"stewart": "question/1", "limit-turns": "200",
                       "limit-input-tokens": "20000000", "limit-output-tokens": "400000"})
        self.question(f, fields)
        self.cmd("release-gate.api-positive", ["prepare", f["reference"]], binary=self.release)
        for key in ("runtime-profile", "max-placements", "placement-timeout-seconds"):
            self.question(f, dict(fields, **{key: f["fields"][key]}))
            reply = self.cmd("release-gate." + key, ["prepare", f["reference"]], "refused", binary=self.release)
            self.control("featureless-" + key, reply.get("outcome") == "refused")
            self.defect("release-gate." + key, reply, "front_matter_invalid", key)
        self.question(f, dict(fields, stewart="question/claude-code/1"))
        reply = self.cmd("release-gate.removed-version", ["prepare", f["reference"]], "refused", binary=self.release)
        self.control("featureless-removed-version", reply.get("outcome") == "refused")
        # No topic and no notice in the featureless build; the same scaffold in both.
        status, overview, _ = self.plain("release-gate.help", ["help"], binary=self.release)
        self.eq("release-gate.help-exit", status, 0)
        self.check("release-gate.no-notice", "runtime" not in overview and "claude" not in overview.lower(),
                   overview[:400])
        status, _, _ = self.plain("release-gate.help-runtime", ["help", "runtime"], binary=self.release)
        self.check("release-gate.no-runtime-topic", status != 0, status)
        self.control("featureless-no-runtime-topic", status != 0)
        scaffolds = {}
        for name, binary in (("development", self.binary), ("featureless", self.release)):
            folder = self.work / ("scaffold-" + name)
            reply = self.cmd("release-gate.scaffold-" + name,
                             ["new", folder, "--archive", self.work / ("scaffold-archive-" + name)], binary=binary)
            self.require("release-gate.scaffold-" + name + ".created", reply.get("outcome") == "completed", reply)
            scaffolds[name] = {str(path.relative_to(folder)): path.read_bytes().hex()
                               for path in sorted(folder.rglob("*")) if path.is_file()}
        self.check("release-gate.scaffold-nonempty", "question.md" in scaffolds["development"],
                   sorted(scaffolds["development"]))
        self.eq("release-gate.same-scaffold", scaffolds["development"], scaffolds["featureless"])

    def harness_events(self, f):
        path = f["witness"] / "harness.jsonl"
        return [transport_loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []

    def audit_path(self, f):
        return f["archive"] / "audits" / f["reference"].split(":")[1]

    def inspect_environment(self, prefix, event, expected, witness):
        # Check the independently retained pre-Python bytes, not os.environ
        # after interpreter startup (which may have coerced LC_CTYPE).
        name = event.get("environment_witness", "")
        self.require(prefix + ".witness-name", bool(re.fullmatch(r"environment\.[A-Za-z0-9]+", name)), name)
        raw = (witness / name).read_bytes()
        self.eq(prefix + ".witness-sha256", sha(raw), event.get("environment_sha256"))
        env = environment_snapshot(raw)
        self.eq(prefix + ".witness-content", env, event["environment"])
        self.eq(prefix + ".supplied", {key: env.get(key) for key in expected}, expected)
        self.eq(prefix + ".nothing-else", sorted(set(env) - set(expected) - WRAPPER_ENVIRONMENT), [])
        return env

    def inspect_runtime(self, f, placements=1, terminal=False):
        events = self.harness_events(f)
        launches = [e for e in events if e["event"] == "launch"]
        self.eq(f["label"] + ".auth-count", sum(e["role"] == "auth" for e in launches), placements)
        self.eq(f["label"] + ".model-count", sum(e["role"] == "model" for e in launches), placements)
        auths = [e for e in launches if e["role"] == "auth"]
        for index, event in enumerate(e for e in launches if e["role"] == "model"):
            p = f["label"] + ".launch-%d" % (index + 1)
            argv = event["argv"]
            # The supplied files are named absolutely inside the private
            # working directory; take that directory from the launch itself.
            named = argv[argv.index("--settings") + 1] if "--settings" in argv[:-1] else ""
            workspace = named[:-len("/settings.json")] if named.endswith("/settings.json") else named
            self.check(p + ".workspace-absolute", workspace.startswith("/"), named)
            self.eq(p + ".workspace-is-cwd", os.path.realpath(workspace), os.path.realpath(event["cwd"]))
            expected = filled_launch(str(self.binary), workspace, f["launch"], f["family"], MODEL, f["effort"])
            self.eq(p + ".argv", argv, expected["model_argv"])
            env = self.inspect_environment(p + ".env", event, expected["environment"], f["witness"])
            for key in ("DRIVER_INJECTION", "HTTPS_PROXY", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
                self.check(p + ".no-forward." + key, key not in env, env.get(key))
            cwd = Path(event["cwd"])
            for outside in (f["folder"], f["archive"], HERE.parent.parent):
                self.check(p + ".cwd-outside." + outside.name,
                           not cwd.is_relative_to(outside), str(cwd))
            self.eq(p + ".system-prompt", event.get("system_prompt"),
                    RUNTIME_ORIENTATION + "\n\n" + FAMILY_TEXT[f["family"]])
            self.eq(p + ".settings", event.get("settings"), expected["settings"])
            self.eq(p + ".mcp-config", event.get("mcp_config"), expected["mcp_config"])
            if index < len(auths):
                auth = auths[index]
                self.eq(p + ".auth-argv", auth["argv"], expected["auth_argv"])
                self.eq(p + ".auth-cwd", os.path.realpath(auth["cwd"]), os.path.realpath(event["cwd"]))
                self.inspect_environment(p + ".auth-env", auth, expected["environment"], f["witness"])
        handshakes = [e["value"]["result"] for e in events if e["event"] == "rpc-receive"
                      and isinstance(e["value"].get("result"), dict)
                      and "protocolVersion" in e["value"]["result"]]
        if any(e["role"] == "model" for e in launches):
            self.check(f["label"] + ".mcp-initialize",
                       bool(handshakes) and all(h == surface_document()["mcp_initialize"] for h in handshakes),
                       handshakes)
        inputs = [e["value"] for e in events if e["event"] == "input"]
        self.check(f["label"] + ".exact-first-question", bool(inputs) and inputs[0] == {
            "type": "user", "session_id": "", "parent_tool_use_id": None,
            "message": {"role": "user", "content": f["body"].decode()}}, inputs[:1])
        scenario = strict_loads(f["scenario"].read_bytes())
        leaked = []
        for path in self.audit_path(f).rglob("*"):
            if path.is_file() and scenario["auth_private"].encode() in path.read_bytes():
                leaked.append(str(path))
        self.eq(f["label"] + ".auth-private-not-archived", leaked, [])
        status_reply = self.cmd(f["label"] + ".runtime-status", ["status", f["reference"]])
        usage = status_reply["data"].get("allowances", {}).get("usage", {})
        self.eq(f["label"] + ".reserved", usage.get("placements"), placements)
        self.summary_facts(f["label"] + ".runtime-summary", status_reply["data"].get("summary"), f, placements)
        self.eq(f["label"] + ".provider-completeness", usage.get("provider_completeness"), "unverified")
        if not terminal:
            self.eq(f["label"] + ".unknown-intervals", usage.get("unknown_intervals"), placements)
            self.eq(f["label"] + ".no-invented-checkpoint", usage.get("reported_main_loop"), None)
        return status_reply

    def groups_absent(self, f, run=1, stop_record=True):
        root = self.audit_path(f) / "runs" / str(run)
        paths = [root / "process-auth.json", root / "process-model.json"]
        groups = []
        for path in paths:
            self.require(f["label"] + ".process-record." + path.name, path.exists(), str(path))
            record = strict_loads(path.read_bytes())
            self.eq(f["label"] + ".process-keys." + path.name, sorted(record), ["group", "role", "schema"])
            self.eq(f["label"] + ".process-schema." + path.name, record.get("schema"), "stewart.claude-code.process/1")
            self.require(f["label"] + ".valid-group." + path.name,
                         type(record.get("group")) is int and record["group"] > 1, record)
            groups.append(record["group"])
        deadline = time.monotonic() + 8
        live = groups
        while live and time.monotonic() < deadline:
            live = [{"group": group, "observation": state} for group in groups
                    for state in [group_observation(group)] if state != "absent"]
            if live:
                time.sleep(0.05)
        self.eq(f["label"] + ".groups-observed-absent.run-%d" % run, live, [])
        if stop_record:
            stop = root / "runtime-stop.json"
            self.require(f["label"] + ".stop-record", stop.exists(), str(stop))
            record = strict_loads(stop.read_bytes())
            self.eq(f["label"] + ".stop-observation", record.get("groups_gone"), True)
            for key in ("elapsed_ms", "deadline_ms"):
                self.check(f["label"] + ".stop." + key, type(record.get(key)) is int and record[key] >= 0, record)
        return live

    def check_delivery(self, f, status_reply, actor="auditor"):
        data = status_reply["data"]
        self.eq(f["label"] + "." + actor + "-seal", data.get("seal", {}).get("actor"), actor)
        delivery = data.get("headline", {}).get("delivered", {})
        self.require(f["label"] + ".verified-delivery", delivery.get("verified") is True, delivery)
        package = Path(delivery["location"])
        expected = (b'{"schema":"stewart.answer/1","revision":1,"entries":[\n'
                    + compact({"id": "e1", "version": 1, "kind": "record_account", "label": "",
                               "text": ACCOUNT, "citations": []}) + b']}\n')
        (f["witness"] / "expected-answer.json").write_bytes(expected)
        self.eq(f["label"] + ".faithful-answer", (package / "answer.json").read_bytes().decode(), expected.decode())
        return package

    def package_identity(self, package):
        return {path.name: sha(path.read_bytes()) for path in sorted(package.iterdir())}

    def runtime_allowances(self, label, data, used, f):
        allowances = data.get("allowances") or {}
        self.eq(label + ".allowances-runtime", allowances.get("runtime"), "claude-code/1")
        self.eq(label + ".allowances-placements", allowances.get("placements"),
                {"used": used, "limit": f["limits"]["max_placements"],
                 "remaining": f["limits"]["max_placements"] - used})
        self.check(label + ".no-api-allowances",
                   not {"turns", "input_tokens", "output_tokens"} & set(allowances), sorted(allowances))

    def launch_count(self, f):
        return sum(e["event"] == "launch" for e in self.harness_events(f))

    def close_after_delivery(self, f, package):
        """An ordinary close of a copy delivered before close, as on the Messages path."""
        label = f["label"]
        delivered = self.package_identity(package)
        launches = self.launch_count(f)
        reply = self.cmd(label + ".close", ["close", f["reference"]])
        self.eq(label + ".close-effects", reply.get("effects"),
                {"run": "ended", "seal": "existing", "delivery": "verified", "closure": "complete"})
        data = reply.get("data") or {}
        for key, value in (("closure", "complete"), ("already_closed", False), ("before_launch", False),
                           ("placement", "delivered_before_close"), ("surrendered", [])):
            self.eq(label + ".close-" + key, data.get(key), value)
        self.eq(label + ".close-seal-actor", (data.get("seal") or {}).get("actor"), "auditor")
        self.eq(label + ".close-runs", data.get("runs"), {"count": 1, "held": False, "last_ending": "sealed"})
        self.runtime_allowances(label + ".close", data, 1, f)
        status_reply = self.cmd(label + ".status-closed", ["status", f["reference"]])
        headline = status_reply["data"].get("headline", {})
        self.eq(label + ".closed-headline", headline.get("closed"), "yes")
        self.eq(label + ".closed-condition", status_reply["data"].get("condition"), "closed")
        self.eq(label + ".delivery-confirmed", headline.get("delivered", {}).get("confirmed"), True)
        repeat = self.cmd(label + ".close-again", ["close", f["reference"]])
        self.eq(label + ".close-again-already", (repeat.get("data") or {}).get("already_closed"), True)
        self.eq(label + ".package-unchanged", self.package_identity(package), delivered)
        self.eq(label + ".one-package", [path.name for path in sorted(package.parent.iterdir())], [package.name])
        refused = self.cmd(label + ".run-after-close", ["run", f["reference"]], "refused")
        self.check(label + ".run-after-close-reason",
                   refused.get("reason") in ("reference_closed", "authoring_ended"), refused.get("reason"))
        self.eq(label + ".no-launch-after-close", self.launch_count(f), launches)

    def runtime_ordinary_ending(self):
        f = self.fixture("runtime-ordinary-ending", scenario="no-submit")
        label = f["label"]
        self.accept(f)
        reply = self.cmd(label + ".run", ["run", f["reference"]])
        data = reply.get("data") or {}
        self.eq(label + ".ending", data.get("ending"), "ended_unsubmitted")
        self.eq(label + ".reminder-notice",
                [n for n in data.get("notices", []) if n.get("type") == "reminder"],
                [{"type": "reminder", "sent": "sent"}])
        self.eq(label + ".no-seal-from-ending", (data.get("seal") or {}).get("state"), "absent")
        self.groups_absent(f)
        events = self.harness_events(f)
        self.require(label + ".no-harness-fatal", not any(e["event"] == "fatal" for e in events),
                     str(f["witness"] / "harness.jsonl"))
        inputs = [e["value"] for e in events if e["event"] == "input"]
        self.eq(label + ".inputs", inputs, [
            {"type": "user", "session_id": "", "parent_tool_use_id": None,
             "message": {"role": "user", "content": text}} for text in (f["body"].decode(), REMINDER)])
        results = [e["value"] for e in events if e["event"] == "output" and e["value"].get("type") == "result"]
        self.eq(label + ".two-turn-endings", len(results), 2)
        status_reply = self.inspect_runtime(f, terminal=True)
        usage = status_reply["data"].get("allowances", {}).get("usage", {})
        latest = dict(CHECKPOINTS[1]["usage"], harness_turns=CHECKPOINTS[1]["num_turns"])
        summed = {key: CHECKPOINTS[0]["usage"][key] + CHECKPOINTS[1]["usage"][key] for key in CHECKPOINTS[0]["usage"]}
        self.eq(label + ".latest-checkpoint", usage.get("reported_main_loop"), latest)
        self.control("checkpoints-not-summed", usage.get("reported_main_loop") is not None
                     and usage.get("reported_main_loop") != dict(summed, harness_turns=5))
        for key, value in (("reported_placements", 1), ("unknown_intervals", 0), ("stopped", 1)):
            self.eq(label + ".usage-" + key, usage.get(key), value)
        self.eq(label + ".run-usage", data.get("usage"), usage)
        checkpoints = sorted((self.audit_path(f) / "runs" / "1").glob("runtime-usage-*.json"))
        self.check(label + ".checkpoint-records", bool(checkpoints), str(self.audit_path(f) / "runs" / "1"))
        self.eq(label + ".recorded-entry", (status_reply["data"].get("answer") or {}).get("entries"), 1)
        # Authoring has ended: another run launches nothing, and close seals for the manager.
        launches = self.launch_count(f)
        refused = self.cmd(label + ".run-again", ["run", f["reference"]], "refused")
        self.eq(label + ".run-again-reason", refused.get("reason"), "authoring_ended")
        self.eq(label + ".no-second-launch", self.launch_count(f), launches)
        self.control("ordinary-ending-ends-authoring", refused.get("reason") == "authoring_ended"
                     and self.launch_count(f) == launches)
        closing = self.cmd(label + ".close", ["close", f["reference"]])
        self.eq(label + ".close-effects", closing.get("effects"),
                {"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"})
        cdata = closing.get("data") or {}
        self.eq(label + ".close-unfinished", cdata.get("unfinished_reason"), "awaiting_confirmation")
        self.eq(label + ".manager-seal", (cdata.get("seal") or {}).get("actor"), "manager")
        token = cdata.get("confirmation")
        self.require(label + ".confirmation-token", isinstance(token, str) and token.startswith("cf1."), token)
        self.runtime_allowances(label + ".close", cdata, 1, f)
        package = self.check_delivery(f, self.cmd(label + ".status-sealed", ["status", f["reference"]]), "manager")
        delivered = self.package_identity(package)
        again = self.cmd(label + ".close-without-token", ["close", f["reference"]])
        self.eq(label + ".repeat-is-not-confirmation", (again.get("data") or {}).get("closure"), "unfinished")
        done = self.cmd(label + ".close-confirm", ["close", f["reference"], "--confirm", token])
        ddata = done.get("data") or {}
        self.eq(label + ".closed", ddata.get("closure"), "complete")
        self.eq(label + ".placement-confirmed", ddata.get("placement"), "confirmed")
        self.eq(label + ".package-unchanged", self.package_identity(package), delivered)
        self.eq(label + ".no-launch-during-close", self.launch_count(f), launches)

    def runtime_submit(self):
        for label in ("runtime-positive", "runtime-fresh-invariance"):
            f = self.fixture(label, scenario="submit")
            self.accept(f)
            env = dict(self.env, DRIVER_INJECTION="must-not-forward", HTTPS_PROXY="http://127.0.0.1:1")
            self.cmd(label + ".run", ["run", f["reference"]], env=env)
            self.groups_absent(f)
            package = self.check_delivery(f, self.inspect_runtime(f))
            if label == "runtime-positive":
                self.close_after_delivery(f, package)

    def harness_clean(self, f):
        events = self.harness_events(f)
        self.require(f["label"] + ".no-harness-fatal", not any(e["event"] == "fatal" for e in events),
                     [e.get("error") for e in events if e["event"] == "fatal"])
        return events

    def message_contents(self, events):
        inputs = [e["value"] for e in events if e["event"] == "input"]
        shaped = all(set(i) == {"type", "session_id", "parent_tool_use_id", "message"} and i["type"] == "user"
                     and i["session_id"] == "" and i["parent_tool_use_id"] is None
                     and set(i["message"]) == {"role", "content"} and i["message"]["role"] == "user"
                     for i in inputs)
        return shaped, [i.get("message", {}).get("content") for i in inputs]

    def core_reply(self, response):
        """The Stewart core reply carried by an MCP tool response, if there is one."""
        if not isinstance(response, dict) or not isinstance(response.get("result"), dict):
            return None
        content = response["result"].get("content") or []
        if not content or content[0].get("type") != "text":
            return None
        try:
            return strict_loads(content[0]["text"].encode())
        except ValueError:
            return None

    def usage_of(self, status_reply):
        return status_reply["data"].get("allowances", {}).get("usage", {})

    def runtime_hooks_and_effort(self):
        f = self.fixture("runtime-hooks-and-effort", scenario="hooks", effort="high")
        label = f["label"]
        self.accept(f)
        self.cmd(label + ".run", ["run", f["reference"]])
        self.groups_absent(f)
        events = self.harness_clean(f)
        # inspect_runtime compares the launch with the surface, effort arguments included.
        self.check_delivery(f, self.inspect_runtime(f))
        model = next((e for e in events if e["event"] == "launch" and e["role"] == "model"), {})
        self.eq(label + ".effort-arguments", model.get("argv", [])[-2:], ["--effort", "high"])
        pinned = {"mcp__stewart__" + tool["name"] for tool in expected_tools(f["family"])}
        deny = surface_document()["hook_replies"]["deny"]
        hooks = [e for e in events if e["event"] == "hook"]
        self.eq(label + ".hook-calls", [h["when"] for h in hooks], ["before-startup"] + ["after-startup"] * 6)
        verdicts = []
        for index, call in enumerate(hooks):
            name = "%s.hook-%d" % (label, index + 1)
            output = bytes.fromhex(call.get("output_hex", ""))
            self.check(name + ".answered", not call.get("timed_out"), call)
            self.check(name + ".one-line", output.endswith(b"\n") and output.count(b"\n") == 1, output)
            try:
                reply = strict_loads(output)
            except ValueError:
                reply = None
            admitted = call["when"] == "after-startup" and call["tool"] in pinned
            self.eq(name + (".admits" if admitted else ".denies"), reply, {} if admitted else deny)
            if admitted:
                self.eq(name + ".exit", call.get("exit"), 0)
            verdicts.append((call["when"], call["tool"] in pinned, reply))
        self.control("hook-denies-before-startup",
                     any(when == "before-startup" and is_pinned and reply == deny for when, is_pinned, reply in verdicts))
        self.control("hook-denies-unpinned-tools",
                     sum(when == "after-startup" and not is_pinned and reply == deny
                         for when, is_pinned, reply in verdicts) == 4)
        self.check(label + ".hook-admits-pinned",
                   sum(when == "after-startup" and is_pinned and reply == {}
                       for when, is_pinned, reply in verdicts) == 2, verdicts)
        # Hook traffic after startup is retained in order on its two channels.
        for channel, key in (("hook-in", "input_hex"), ("hook-out", "output_hex")):
            captured, position = self.captured_channel(f, channel), 0
            for index, call in enumerate(hooks):
                if call["when"] != "after-startup":
                    continue
                piece = bytes.fromhex(call.get(key, ""))
                found = captured.find(piece, position) if piece else -1
                self.check("%s.%s-%d" % (label, channel, index + 1), found >= 0,
                           {"channel": channel, "bytes": len(captured), "sought": piece})
                position = found + len(piece) if found >= 0 else position

    def runtime_cancellation(self):
        f = self.fixture("runtime-cancellation", scenario="cancel")
        label = f["label"]
        self.accept(f)
        self.cmd(label + ".run", ["run", f["reference"]])
        self.groups_absent(f)
        events = self.harness_clean(f)
        status_reply = self.inspect_runtime(f)
        seen = {e["name"]: e["response"] for e in events if e["event"] == "observation"}
        races = ["race-%d" % number for number in range(1, RACES + 1)]
        self.eq(label + ".observations", list(seen),
                ["first", "ping", "duplicate", "kept", "queued", "predecessor", "cancelled"] + races + ["reentry"])

        def completed(name):
            return (self.core_reply(seen.get(name)) or {}).get("outcome") == "completed"
        self.check(label + ".first-completed", completed("first"), seen.get("first"))
        self.check(label + ".kept-completed", completed("kept"), seen.get("kept"))
        self.check(label + ".queued-completed", completed("queued"), seen.get("queued"))
        self.check(label + ".predecessor-completed", completed("predecessor"), seen.get("predecessor"))
        pairs = [(e["ids"][0], e["ids"][1]) for e in events
                 if e["event"] == "rpc-transmitted" and len(e["methods"]) >= 2
                 and e["methods"][:2] == ["tools/call", "tools/call"]]
        replies = [e["value"].get("id") for e in events if e["event"] == "rpc-receive"]
        self.require(label + ".two-pipelined-pairs", len(pairs) == 2, pairs)
        for index, (first, second) in enumerate(pairs, 1):
            self.check("%s.pair-%d.reply-order" % (label, index),
                       first in replies and second in replies and replies.index(first) < replies.index(second), replies)
        self.eq(label + ".ping", (seen.get("ping") or {}).get("result"), {})
        self.check(label + ".duplicate-answered", seen.get("duplicate") is not None, "no reply to a reused request ID")
        delivery = status_reply["data"].get("headline", {}).get("delivered", {})
        self.require(label + ".verified-delivery", delivery.get("verified") is True, delivery)
        answer = strict_loads((Path(delivery["location"]) / "answer.json").read_bytes())
        texts = [entry.get("text") for entry in answer.get("entries", [])]
        # An effect exists exactly when its call got a completed reply.
        for name, text, control in (("duplicate", DUPLICATE, "reused-request-id-refused"),
                                    ("cancelled", CANCELLED, "cancelled-pipelined-call-has-no-effect")):
            self.eq(label + "." + name + ".effect-iff-completed", text in texts, completed(name))
            self.control(control, text not in texts and not completed(name))
        cancelled = self.core_reply(seen.get("cancelled")) or {}
        self.eq(label + ".cancelled-reason", cancelled.get("reason"), "placement_stopped")
        self.note(label + ".cancellation-observer-scope",
                  "The peer sent a large predecessor, its sibling and cancellation in one write; "
                  "the sibling was refused without effect. Transport and effects are witnessed; "
                  "the instant at which the sibling entered the service queue is not independently observed.")
        # A cancellation racing its own call may win or lose. Either way the
        # entry exists exactly when the call got a completed reply.
        landed = []
        for number, name in enumerate(races, 1):
            self.eq(label + "." + name + ".effect-iff-completed", race_text(number) in texts, completed(name))
            if completed(name):
                landed.append(race_text(number))
            else:
                self.eq(label + "." + name + ".stopped-reason",
                        (self.core_reply(seen.get(name)) or {}).get("reason"), "placement_stopped")
        lost = [name for name in races if not completed(name)]
        answers = sorted({json.dumps(seen.get(name))[:200] for name in lost})
        self.note(label + ".cancellation-races", "cancellation won %d of %d races%s" % (
            len(lost), RACES, "; won races were answered " + " | ".join(answers) if lost else
            "; a winning in-flight cancellation was not exercised in this run"))
        # A cancellation that arrives after completion, or names no request, changes nothing.
        self.eq(label + ".delivered-entries", [text[:60] for text in texts],
                [text[:60] for text in [ACCOUNT, KEPT, QUEUED, race_text(0)] + landed])
        self.eq(label + ".reentry-after-cancellation", (seen.get("reentry") or {}).get("outcome"), "completed")
        # Exact traffic: what the peer sent is what was retained, and every
        # reply the peer received had been retained before it was sent.
        sent = b"".join(bytes.fromhex(e["raw_hex"]) for e in events if e["event"] == "rpc-send")
        self.eq(label + ".mcp-capture", self.captured_channel(f, "mcp").hex(), sent.hex())
        received = b"".join(bytes.fromhex(e["raw_hex"]) for e in events if e["event"] == "rpc-observed")
        retained = self.captured_channel(f, "mcp-out")
        self.check(label + ".mcp-out-capture", bool(received) and retained.startswith(received),
                   {"received": len(received), "retained": len(retained)})

    def runtime_submit_publication(self):
        if self.variant is None or b"STEWART_TEST_FAULT" not in self.variant.read_bytes():
            return "--variant-binary with claude-code,fault-injection is required for the documented publication pause"
        original = self.binary
        self.binary = self.variant
        try:
            for action, placements in (("positive", 3), ("cancel", 3), ("signal", 3),
                                       ("deadline", 3), ("deadline-last", 1)):
                self.submit_publication(action, placements)
        finally:
            self.binary = original

    def submit_publication(self, action, placements):
        label = "submit-publication-" + action
        seconds = 6 if action.startswith("deadline") else 60
        f = self.fixture(label, scenario="submit-publication", timeout=seconds, placements=placements)
        self.change_scenario(f, publication_action=action)
        self.accept(f)
        faults = f["witness"] / "faults"
        faults.mkdir()
        env = dict(self.env, STEWART_TEST_FAULT="log.publish:seal=pause", STEWART_TEST_FAULT_DIR=str(faults))
        argv = [str(self.binary), "run", f["reference"], "--json"]
        stdout_path, stderr_path = f["witness"] / "run.stdout", f["witness"] / "run.stderr"
        before = snapshot(f["archive"])
        started = time.monotonic()
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, env=env, cwd=self.cwd)
            paused = []
            def await_fact(predicate, bound=12):
                until = time.monotonic() + bound
                while process.poll() is None and time.monotonic() < until:
                    if predicate():
                        return True
                    time.sleep(0.01)
                return bool(predicate())
            def observed(name):
                return [e for e in self.harness_events(f) if e.get("event") == name]
            def boundary(event, **facts):
                with (f["witness"] / "publication-boundary.jsonl").open("ab") as record:
                    record.write(compact({"event": event, "monotonic_ns": time.monotonic_ns(), **facts}) + b"\n")
            def release():
                release_fault_pauses(faults, boundary)
            try:
                self.require(label + ".publication-pause", await_fact(lambda: bool(list(faults.glob("log.publish*.paused")))),
                             {"exit": process.poll(), "stderr": stderr_path.read_text(errors="replace")})
                paused = list(faults.glob("log.publish*.paused"))
                self.require(label + ".independent-submit-sent", bool(observed("submit-publication")),
                             str(f["witness"] / "harness.jsonl"))
                status = self.cmd(label + ".status-before-link", ["status", f["reference"]])
                self.eq(label + ".no-seal-before-link", status["data"].get("seal"), {"state": "absent", "actor": None})
                if action == "cancel":
                    (f["witness"] / "cancel-submit").write_bytes(b"")
                    self.require(label + ".cancellation-observed-before-release",
                                 await_fact(lambda: bool(observed("submit-cancellation-ping"))),
                                 "ordered cancellation and following ping were not acknowledged")
                elif action == "signal":
                    supplied = observed("submit-publication")[0]
                    model_group = supplied["group"]
                    process_record = strict_loads((self.audit_path(f) / "runs" / "1" / "process-model.json").read_bytes())
                    self.eq(label + ".group-matches-independent-harness", process_record.get("group"), model_group)
                    self.eq(label + ".group-matches-process-observation", os.getpgid(supplied["pid"]), model_group)
                    present = group_observation(model_group)
                    boundary("before-signal", owner_pid=process.pid, owner_alive=process.poll() is None,
                             model_group=model_group, group_observation=present)
                    self.require(label + ".model-group-present-control", present == "present", present)
                    process.send_signal(signal.SIGTERM)
                    boundary("signal-sent", owner_pid=process.pid, signal="SIGTERM")
                    self.save("witness/" + label + "/signal.json", {"pid": process.pid, "signal": "SIGTERM",
                              "model_group": model_group, "monotonic_ns": time.monotonic_ns()})
                    prior_state = [present]
                    def stopped():
                        state = group_observation(model_group)
                        if state != prior_state[-1]:
                            boundary("model-group-observation", model_group=model_group, observation=state)
                            prior_state.append(state)
                        return state == "absent"
                    absent = await_fact(stopped, bound=8)
                    owner_alive = process.poll() is None
                    still_paused = all(p.exists() and not p.with_suffix(".go").exists() for p in paused)
                    boundary("stopping-observed-before-release", model_group_absent=absent,
                             owner_alive=owner_alive, still_paused=still_paused)
                    self.require(label + ".stopping-won-before-release", absent and owner_alive and still_paused,
                                 {"group_observations": prior_state, "owner_exit": process.poll(), "still_paused": still_paused})
                elif action.startswith("deadline"):
                    # The placement was reserved before this acknowledged pause;
                    # a full placement interval after it establishes expiry.
                    end = time.monotonic() + seconds + 0.1
                    while time.monotonic() < end and process.poll() is None:
                        time.sleep(0.02)
                release()
                if action == "cancel":
                    self.require(label + ".refusal-and-continuation-observed",
                                 await_fact(lambda: bool(observed("submit-cancelled-reentry"))),
                                 str(f["witness"] / "harness.jsonl"))
                    status = self.cmd(label + ".status-after-cancel", ["status", f["reference"]])
                    self.eq(label + ".cancel-published-no-seal", status["data"].get("seal"), {"state": "absent", "actor": None})
                    self.eq(label + ".cancel-kept-placement", process.poll(), None)
                    (f["witness"] / "retry-submit").write_bytes(b"")
                process.wait(timeout=15)
            except BaseException:
                self.launch_blocked = ("publication control did not finish; inspect retained owner/group evidence at "
                                       + str(f["witness"]) + " before another launch")
                raise
            finally:
                release()
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                self.save("witness/" + label + "/run-command.json", {"argv": argv, "env": env,
                          "exit": process.returncode, "elapsed_seconds": time.monotonic() - started,
                          "pause_files": [str(p) for p in paused]})
        reply = strict_loads(stdout_path.read_bytes())
        ending = "sealed" if action in ("positive", "cancel") else "limit_reached" if placements == 1 else "interrupted"
        cause = "signal" if action == "signal" else "placement_deadline" if action == "deadline" else None
        self.eq(label + ".outcome", reply.get("outcome"), "completed")
        self.eq(label + ".ending", reply.get("data", {}).get("ending"), ending)
        self.eq(label + ".cause", reply.get("data", {}).get("cause"), cause)
        self.eq(label + ".exit", process.returncode, 5 if ending == "interrupted" else 0)
        self.eq(label + ".retained-earlier-bytes", immutable_changes(before, snapshot(f["archive"])), [])
        self.groups_absent(f)
        status = self.inspect_runtime(f)
        if action in ("positive", "cancel"):
            self.check_delivery(f, status)
        else:
            self.eq(label + ".no-seal-after-stop", status["data"].get("seal"), {"state": "absent", "actor": None})
            self.eq(label + ".stop-effects-seal", reply.get("effects", {}).get("seal"), "none")
        event = observed("submit-publication")[0]
        run = self.audit_path(f) / "runs" / "1"
        calls = [path for path in run.glob("call-*.json")
                 if transport_loads(path.read_bytes()).get("id") == event["id"]]
        self.require(label + ".submitted-call-retained", len(calls) == 1, [str(p) for p in calls])
        result = strict_loads((run / calls[0].name.replace("call-", "result-")).read_bytes())["body"]
        core = strict_loads(result["content"][0]["text"].encode())
        if action == "positive":
            self.eq(label + ".positive-submit", core.get("outcome"), "completed")
        else:
            self.eq(label + ".submit-refusal", (core.get("outcome"), core.get("reason")), ("refused", "placement_stopped"))
            self.eq(label + ".submit-refusal-effects", {k: v for k, v in core.get("effects", {}).items() if k != "diagnostic"},
                    {"seal": "none", "raw_capture": "recorded"})
            self.eq(label + ".refusal-published-no-log-record", result.get("log_record"), None)
            self.control(label + "-stops-publication", core.get("reason") == "placement_stopped"
                         and core.get("effects", {}).get("seal") == "none")
        if action == "cancel":
            reentry = observed("submit-cancelled-reentry")[0]["response"]
            self.eq(label + ".later-call-completed", reentry.get("outcome"), "completed")
            self.eq(label + ".one-placement", status["data"].get("runs", {}).get("count"), 1)

    def runtime_relay_loss(self):
        f = self.fixture("runtime-relay-loss", scenario="relay-loss", timeout=20)
        label = f["label"]
        self.accept(f)
        started = time.monotonic()
        reply = self.cmd(label + ".run-1", ["run", f["reference"]], outcome=None)
        elapsed = time.monotonic() - started
        self.require(label + ".relay-was-killed", (f["witness"] / "relay-ready.json").exists(),
                     "the synthetic model never reached the relay kill")
        events = self.harness_clean(f)
        self.groups_absent(f)
        data = reply.get("data") or {}
        self.eq(label + ".ending", data.get("ending"), "interrupted")
        stop = strict_loads((self.audit_path(f) / "runs" / "1" / "runtime-stop.json").read_bytes())
        before_deadline = (data.get("cause") != "placement_deadline" and elapsed < 12
                           and stop.get("elapsed_ms", 10 ** 9) < stop.get("deadline_ms", 0))
        self.check(label + ".stopped-before-deadline", before_deadline,
                   {"cause": data.get("cause"), "elapsed_seconds": elapsed, "stop": stop})
        status_reply = self.inspect_runtime(f)
        self.eq(label + ".retained-entry", (status_reply["data"].get("answer") or {}).get("entries"), 1)
        self.eq(label + ".no-seal", status_reply["data"].get("seal", {}).get("state"), "absent")
        # The synthetic model sleeps after killing its relay and never exits by
        # itself, so observed group absence is Stewart's stop.
        killed = any(e["event"] == "relay-killed" for e in events)
        self.control("relay-loss-stops-the-live-model", killed and before_deadline
                     and data.get("ending") == "interrupted")
        self.change_scenario(f, mode="submit", skip_record=True, session=label + "-session-2")
        self.cmd(label + ".run-2", ["run", f["reference"]])
        self.groups_absent(f, run=2)
        package = self.check_delivery(f, self.inspect_runtime(f, placements=2))
        answer = (package / "answer.json").read_bytes().decode()
        self.check(label + ".nothing-from-a-second-relay",
                   SECOND_RELAY.strip() not in answer and ACCOUNT.strip() in answer, answer[:400])
        second = next((e for e in events if e["event"] == "second-relay"), None)
        self.note(label + ".second-relay", "the attempt finished before the stop and received %d bytes"
                  % (len(second.get("received_hex", "")) // 2) if second else
                  "the placement was stopped before the second relay's attempt finished; "
                  "refusal of a second connection was not exercised")
        self.note(label + ".cause", "relay loss ended the placement with cause %s after %.1f seconds"
                  % (data.get("cause"), elapsed))

    def runtime_usage_series(self):
        f = self.fixture("runtime-usage-series", scenario="checkpoint-then-crash")
        label = f["label"]
        self.accept(f)
        first = self.cmd(label + ".run-1", ["run", f["reference"]], outcome=None)
        self.groups_absent(f)
        self.harness_clean(f)
        self.eq(label + ".first-ending", (first.get("data") or {}).get("ending"), "interrupted")
        one = dict(CHECKPOINTS[1]["usage"], harness_turns=CHECKPOINTS[1]["num_turns"])
        usage = self.usage_of(self.inspect_runtime(f, terminal=True))
        self.eq(label + ".first-session-report", usage.get("reported_main_loop"), one)
        for key, value in (("reported_placements", 1), ("unknown_intervals", 1), ("stopped", 1)):
            self.eq(label + ".first-" + key, usage.get(key), value)
        self.change_scenario(f, mode="resume-no-submit", session=label + "-session-2")
        second = self.cmd(label + ".run-2", ["run", f["reference"]])
        self.groups_absent(f, run=2)
        events = self.harness_clean(f)
        ending = (second.get("data") or {}).get("ending")
        self.eq(label + ".second-ending", ending, "ended_unsubmitted")
        total = {key: one[key] + SECOND_SESSION["usage"][key] for key in SECOND_SESSION["usage"]}
        total["harness_turns"] = one["harness_turns"] + SECOND_SESSION["num_turns"]
        usage = self.usage_of(self.inspect_runtime(f, placements=2, terminal=True))
        self.eq(label + ".sum-of-latest-per-session", usage.get("reported_main_loop"), total)
        for key, value in (("placements", 2), ("reported_placements", 2), ("unknown_intervals", 1), ("stopped", 2)):
            self.eq(label + ".total-" + key, usage.get(key), value)
        # The second series starts below the first; that is not a regression.
        self.control("fresh-session-is-a-separate-series", usage.get("reported_main_loop") == total
                     and usage.get("reported_placements") == 2)
        self.control("lost-interval-stays-unknown", usage.get("unknown_intervals") == 1)
        shaped, contents = self.message_contents(events)
        self.check(label + ".input-shape", shaped, contents)
        self.eq(label + ".inputs", contents, [f["body"].decode(), REMINDER, f["body"].decode(), CONTINUATION])
        self.control("reminder-is-audit-wide", contents.count(REMINDER) == 1 and ending == "ended_unsubmitted")

    def runtime_compaction(self):
        f = self.fixture("runtime-compaction", scenario="compaction")
        label = f["label"]
        self.accept(f)
        reply = self.cmd(label + ".run", ["run", f["reference"]])
        self.groups_absent(f)
        events = self.harness_clean(f)
        status_reply = self.inspect_runtime(f, terminal=True)
        self.check_delivery(f, status_reply)
        data = reply.get("data") or {}
        self.eq(label + ".ending", data.get("ending"), "sealed")
        shaped, contents = self.message_contents(events)
        self.check(label + ".input-shape", shaped, contents)
        self.eq(label + ".inputs", contents, [f["body"].decode(), COMPACTED, COMPACTED, REMINDER])
        self.control("notice-follows-each-boundary", contents.count(COMPACTED) == 2)
        # Two compaction notices spent neither audit-wide allowance.
        notices = data.get("notices", [])
        self.eq(label + ".reminder-notice", [n for n in notices if n.get("type") == "reminder"],
                [{"type": "reminder", "sent": "sent"}])
        self.eq(label + ".no-near-limit-notice", [n for n in notices if n.get("type") == "near_limit"], [])
        self.control("compaction-spends-no-reminder", REMINDER in contents and data.get("ending") == "sealed")
        seen = {e["name"]: e["response"] for e in events if e["event"] == "observation"}
        self.eq(label + ".reentry-after-compaction", (seen.get("reentry-after-compaction") or {}).get("outcome"),
                "completed")
        # Compaction grants no slot and replaces no checkpoint.
        usage = self.usage_of(status_reply)
        self.eq(label + ".one-placement", usage.get("placements"), 1)
        self.eq(label + ".checkpoint", usage.get("reported_main_loop"),
                dict(CHECKPOINTS[0]["usage"], harness_turns=CHECKPOINTS[0]["num_turns"]))
        self.eq(label + ".reported-placements", usage.get("reported_placements"), 1)
        # Exact traffic on the harness streams, boundaries included.
        emitted = b"".join(bytes.fromhex(e["raw_hex"]) for e in events if e["event"] == "output")
        self.eq(label + ".stdout-capture", self.captured_channel(f, "stdout").hex(), emitted.hex())
        supplied = b"".join(bytes.fromhex(e["raw_hex"]) for e in events if e["event"] == "input")
        self.eq(label + ".input-capture", self.captured_channel(f, "input").hex(), supplied.hex())

    def runtime_init_control(self):
        valid = self.fixture("runtime-delayed-valid-init", scenario="delayed-valid-init")
        self.accept(valid)
        self.cmd(valid["label"] + ".run", ["run", valid["reference"]])
        self.groups_absent(valid)
        events = self.harness_events(valid)
        self.require(valid["label"] + ".no-harness-fatal", not any(e["event"] == "fatal" for e in events),
                     str(valid["witness"] / "harness.jsonl"))
        calls = [e for e in events if e["event"] == "rpc-send" and e["value"].get("params", {}).get("name") == "record_account"]
        startups = [e for e in events if e["event"] == "output" and e["value"].get("subtype") == "init"]
        self.require(valid["label"] + ".matched-delayed-startup", len(calls) == 2 and len(startups) == 1
                     and events.index(calls[0]) < events.index(startups[0]) < events.index(calls[1]),
                     {"record_attempts": len(calls), "startup_events": len(startups)})
        self.check_delivery(valid, self.inspect_runtime(valid))
        f = self.fixture("runtime-init-control", scenario="bad-init")
        self.accept(f)
        self.cmd(f["label"] + ".run", ["run", f["reference"]], outcome=None)
        events = self.harness_events(f)
        self.check_invalid_init_witness(f, events)
        status_reply = self.inspect_runtime(f)
        data = status_reply["data"]
        self.eq(f["label"] + ".no-entry", (data.get("answer") or {}).get("entries"), 0)
        self.eq(f["label"] + ".no-seal", data.get("seal", {}).get("state"), "absent")
        self.control("mismatched-init-authoring", (data.get("answer") or {}).get("entries") == 0
                     and data.get("seal", {}).get("state") == "absent")
        self.groups_absent(f)

    def check_invalid_init_witness(self, f, events):
        self.require(f["label"] + ".no-harness-fatal", not any(e["event"] == "fatal" for e in events),
                     str(f["witness"] / "harness.jsonl"))
        attempted = [e for e in events if e["event"] == "rpc-send" and e["value"].get("method") == "tools/call"
                     and e["value"].get("params", {}).get("name") == "record_account"]
        summary = {"witness": str(f["witness"] / "harness.jsonl"), "events": [
            {"event": e["event"], "method": e.get("value", e).get("method"),
             "id": e.get("value", e).get("id")} for e in events]}
        self.require(f["label"] + ".independent-attempt", bool(attempted), summary)
        invalid_init = [e for e in events if e["event"] == "output" and
                        e["value"].get("type") == "system" and e["value"].get("subtype") == "init"
                        and e["value"].get("model") == "deliberately-wrong-model"]
        transmitted = {e["sha256"] for e in events if e["event"] == "output-transmitted"}
        self.require(f["label"] + ".invalid-startup-transmitted", len(invalid_init) == 1 and
                     sha(bytes.fromhex(invalid_init[0]["raw_hex"])) in transmitted, summary)
        expected = bytes.fromhex(invalid_init[0]["raw_hex"])
        self.eq(f["label"] + ".invalid-startup-captured", self.captured_channel(f, "stdout").hex(), expected.hex())

    def captured_channel(self, f, channel, run=1):
        root = self.audit_path(f) / "runs" / str(run)
        pattern = re.compile(r"^runtime-([1-9][0-9]*)-" + re.escape(channel) + r"\.bin$")
        chunks = [(int(match.group(1)), path) for path in root.iterdir()
                  for match in [pattern.fullmatch(path.name)] if match]
        result = []
        for _, path in sorted(chunks):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                result.append(stream.read())
        return b"".join(result)

    def change_scenario(self, f, **changes):
        current = strict_loads(f["scenario"].read_bytes())
        current.update(changes)
        f["scenario"].write_bytes(compact(current) + b"\n")
        (f["witness"] / ("scenario-" + current["session"] + ".json")).write_bytes(f["scenario"].read_bytes())

    def runtime_interruption(self):
        f = self.fixture("runtime-interruption", scenario="record-then-exit")
        self.accept(f)
        self.cmd(f["label"] + ".run-1", ["run", f["reference"]], outcome=None)
        self.groups_absent(f)
        status_reply = self.inspect_runtime(f)
        self.eq(f["label"] + ".retained-entry", (status_reply["data"].get("answer") or {}).get("entries"), 1)
        self.change_scenario(f, mode="submit", skip_record=True, session="runtime-interruption-session-2")
        self.cmd(f["label"] + ".run-2", ["run", f["reference"]])
        self.groups_absent(f, run=2)
        self.check_delivery(f, self.inspect_runtime(f, placements=2))
        inputs = [e["value"] for e in self.harness_events(f) if e["event"] == "input"]
        self.check(f["label"] + ".continuation-notice", any(e.get("message", {}).get("content") == CONTINUATION for e in inputs), inputs)

    def runtime_deadline(self):
        for label, placements in (("runtime-deadline", 3), ("runtime-last-deadline", 1)):
            # Authentication and startup consume placement time too. Leave
            # enough time for the resistant descendant to fire before expiry.
            placement_deadline = 6
            stop_bound = placement_deadline + 4
            f = self.fixture(label, scenario="hang", timeout=placement_deadline, placements=placements)
            self.accept(f)
            started = time.monotonic()
            self.cmd(f["label"] + ".run", ["run", f["reference"]], outcome=None)
            elapsed = time.monotonic() - started
            self.require(f["label"] + ".descendant-fired", (f["witness"] / "ready.json").exists(), "synthetic resistant descendant never started")
            live = self.groups_absent(f)
            status_reply = self.inspect_runtime(f)
            self.eq(f["label"] + ".deadline-disposition", status_reply["data"].get("condition"),
                    "limit_reached" if placements == 1 else "interrupted")
            if placements > 1:
                self.eq(f["label"] + ".deadline-cause", status_reply["data"].get("runs", {}).get("last", {}).get("cause"),
                        "placement_deadline")
            stop = strict_loads((self.audit_path(f) / "runs" / "1" / "runtime-stop.json").read_bytes())
            deadline_observed = stop.get("elapsed_ms", -1) >= stop.get("deadline_ms", 1)
            self.check(f["label"] + ".deadline-observed", deadline_observed, stop)
            self.check(f["label"] + ".bounded-observed-stop", elapsed <= stop_bound,
                       {"elapsed_seconds": elapsed, "deadline_seconds": placement_deadline, "escalation_seconds": 2})
            self.control(label + "-stops-resistant-group", elapsed <= stop_bound and not live and deadline_observed)
            if placements == 1:
                before = Path(str(f["executable"]) + ".started").read_bytes()
                reply = self.cmd(f["label"] + ".exhausted-run", ["run", f["reference"]], outcome="refused")
                self.eq(f["label"] + ".no-extra-start", Path(str(f["executable"]) + ".started").read_bytes(), before)
                self.control("placement-cap", reply.get("outcome") == "refused")

    def kill_run_owner(self, f):
        stdout = open(f["witness"] / "owner.stdout", "wb")
        stderr = open(f["witness"] / "owner.stderr", "wb")
        argv = [str(self.binary), "run", f["reference"], "--json"]
        process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, cwd=self.cwd, env=self.env)
        try:
            deadline = time.monotonic() + 10
            while process.poll() is None and not (f["witness"] / "ready.json").exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.require(f["label"] + ".started-before-owner-kill", (f["witness"] / "ready.json").exists(), {"exit": process.poll()})
            process.kill()
            process.wait(timeout=5)
            (f["witness"] / "owner-kill.json").write_bytes(compact({"argv": argv, "pid": process.pid, "signal": "SIGKILL", "exit": process.returncode}) + b"\n")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            stdout.close()
            stderr.close()

    def runtime_owner_death(self):
        f = self.fixture("runtime-owner-death", scenario="hang")
        self.accept(f)
        self.kill_run_owner(f)
        self.groups_absent(f, stop_record=False)
        status_reply = self.cmd(f["label"] + ".after-owner-death", ["status", f["reference"]])
        usage = status_reply["data"].get("allowances", {}).get("usage", {})
        self.check(f["label"] + ".missing-end-not-zero", usage.get("unknown_intervals") == 1,
                   status_reply["data"].get("allowances"))
        self.change_scenario(f, mode="submit", session="runtime-owner-death-session-2")
        self.cmd(f["label"] + ".recover", ["run", f["reference"]])
        self.groups_absent(f, run=2)
        self.check_delivery(f, self.inspect_runtime(f, placements=2))

    def runtime_credential_option(self):
        f = self.fixture("runtime-credential-option", scenario="submit")
        self.accept(f)
        marker = Path(str(f["executable"]) + ".started")
        attempts = [("key-fd", ["--key-fd", "0"], self.env)]
        for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
            for label, value in (("empty", ""), ("supplied", "synthetic-not-a-credential")):
                attempts.append((key + "-" + label, [], dict(self.env, **{key: value})))
        for suffix, args, env in attempts:
            name = f["label"] + "." + suffix
            reply = self.cmd(name, ["run", f["reference"]] + args, env=env,
                             outcome="refused", input_bytes=b"synthetic-not-a-credential\n")
            self.eq(name + ".named-refusal", reply.get("reason"), "runtime_credential_forbidden")
            self.eq(name + ".effects", {k: v for k, v in reply.get("effects", {}).items() if k != "diagnostic"},
                    {"run": "not_started", "answer": "unchanged", "seal": "none", "delivery": "none"})
            self.eq(name + ".not-launched", marker.exists(), False)
            self.control("credential-option-" + suffix, reply.get("reason") == "runtime_credential_forbidden"
                         and not marker.exists())
        status = self.cmd(f["label"] + ".no-start-reserved", ["status", f["reference"]])
        self.eq(f["label"] + ".no-start-reserved", status["data"].get("runs", {}).get("count"), 0)

    def runtime_unknown_stop(self):
        f = self.fixture("runtime-unknown-stop", scenario="hang")
        self.accept(f)
        self.kill_run_owner(f)
        self.require(f["label"] + ".original-groups-gone", not self.groups_absent(f, stop_record=False))
        process_record = self.audit_path(f) / "runs" / "1" / "process-model.json"
        original = process_record.read_bytes()
        (f["witness"] / "original-process-model.json").write_bytes(original)
        stop_record = self.audit_path(f) / "runs" / "1" / "runtime-stop.json"
        if stop_record.exists():
            (f["witness"] / "original-runtime-stop.json").write_bytes(stop_record.read_bytes())
        # Independent controlled damage emulates an unresolved process identity.
        # Never ask recovery to signal it: the live group belongs to this driver.
        unrelated = subprocess.Popen(["/bin/sleep", "60"], start_new_session=True)
        try:
            self.eq(f["label"] + ".external-group-observed-present", group_observation(unrelated.pid), "present")
            changed = strict_loads(original)
            changed["group"] = unrelated.pid
            process_record.write_bytes(compact(changed) + b"\n")
            (f["witness"] / "unresolved-process-model.json").write_bytes(process_record.read_bytes())
            if stop_record.exists():
                # Preserve any independently written stop claim, then exercise
                # its absence. No run-ended owner observation was published.
                stop_record.unlink()
            marker = Path(str(f["executable"]) + ".started")
            before = marker.read_bytes()
            log_before = snapshot(self.audit_path(f) / "log")
            reply = self.cmd(f["label"] + ".blocked-restart", ["run", f["reference"]], outcome="refused")
            self.eq(f["label"] + ".named-stop-refusal", reply.get("reason"), "runtime_stop_unknown")
            self.eq(f["label"] + ".no-start-after-unknown-stop", marker.read_bytes(), before)
            self.eq(f["label"] + ".restart-published-nothing", snapshot(self.audit_path(f) / "log"), log_before)
            self.eq(f["label"] + ".recovery-did-not-signal", unrelated.poll(), None)
            self.control("unknown-stop-blocks-restart", reply.get("outcome") == "refused" and marker.read_bytes() == before)
            closed = self.cmd(f["label"] + ".blocked-close", ["close", f["reference"]], outcome="refused")
            self.eq(f["label"] + ".named-close-stop-refusal", closed.get("reason"), "runtime_stop_unknown")
            log_after = snapshot(self.audit_path(f) / "log")
            preserved = self.eq(f["label"] + ".prior-log-bytes-preserved", immutable_changes(log_before, log_after), [])
            added = [strict_loads((self.audit_path(f) / "log" / name).read_bytes())
                     for name in sorted(set(log_after) - set(log_before))]
            # INTERFACE 5.8 step 4 records the request before the stopping
            # prerequisite. Unknown stopping prevents reconciliation, sealing,
            # delivery and completion; it does not erase the manager's request.
            only_request = self.eq(f["label"] + ".only-close-requested", [r.get("kind") for r in added],
                                   ["close_requested"])
            for record in added:
                self.eq(f["label"] + ".close-request.schema", record.get("record"), "stewart.record/1")
                self.eq(f["label"] + ".close-request.audit", record.get("audit"), f["reference"].split(":")[1])
                self.eq(f["label"] + ".close-request.writer", record.get("writer"), sha(self.binary.read_bytes()))
                self.eq(f["label"] + ".close-request.flags", record.get("body", {}).get("flags"),
                        {"confirm": None, "surrender": [], "destination": None})
            self.eq(f["label"] + ".close-did-not-signal", unrelated.poll(), None)
            self.control("unknown-stop-blocks-close", closed.get("reason") == "runtime_stop_unknown"
                         and preserved and only_request)
            repeated = self.cmd(f["label"] + ".repeat-blocked-close", ["close", f["reference"]], outcome="refused")
            self.eq(f["label"] + ".repeat-named-stop-refusal", repeated.get("reason"), "runtime_stop_unknown")
            self.eq(f["label"] + ".repeat-published-nothing", snapshot(self.audit_path(f) / "log"), log_after)
            self.eq(f["label"] + ".repeat-did-not-signal", unrelated.poll(), None)
        finally:
            if unrelated.poll() is None:
                unrelated.terminate()
            unrelated.wait(timeout=5)

    def runtime_recorder_failure(self):
        if os.geteuid() == 0:
            return "permission control requires an ordinary user; root can bypass directory write permissions"
        f = self.fixture("runtime-recorder-failure", scenario="capture-failure")
        self.accept(f)
        run_dir = self.audit_path(f) / "runs" / "1"
        ready = f["witness"] / "capture-ready.json"
        release = f["witness"] / "release-capture-attempt"
        stdout_path, stderr_path = f["witness"] / "recorder-run.stdout", f["witness"] / "recorder-run.stderr"
        stdout, stderr = open(stdout_path, "wb"), open(stderr_path, "wb")
        argv = [str(self.binary), "run", f["reference"], "--json"]
        process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, cwd=self.cwd, env=self.env)
        original_mode = None
        observation = {"argv": argv, "owner_pid": process.pid, "observer": "independent driver",
                       "scope": "run directory permission, completed attempt transmission and process-group absence"}
        groups_gone = False
        natural_stop = False
        try:
            deadline = time.monotonic() + 10
            while process.poll() is None and not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.require(f["label"] + ".startup-witness", ready.exists(), {"exit": process.poll()})
            startup = strict_loads(ready.read_bytes())
            self.require(f["label"] + ".live-before-permission-change",
                         process.poll() is None and group_observation(startup["group"]) == "present", startup)
            events = self.harness_events(f)
            self.eq(f["label"] + ".no-earlier-mutation", [e for e in events if e["event"] == "rpc-send"
                    and e["value"].get("params", {}).get("name") == "record_account"], [])
            original_mode = stat.S_IMODE(run_dir.stat().st_mode)
            restricted_mode = original_mode & ~0o222
            run_dir.chmod(restricted_mode)
            observation.update(path=str(run_dir), original_mode=oct(original_mode),
                               restricted_mode=oct(restricted_mode), restricted_at_ns=time.monotonic_ns())
            probe = run_dir / ".independent-write-control"
            try:
                fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            except PermissionError as exc:
                observation["write_control"] = {"refused": True, "errno": exc.errno, "error": str(exc)}
            else:
                os.close(fd)
                probe.unlink()
                observation["write_control"] = {"refused": False}
            (f["witness"] / "recorder-permissions.json").write_bytes(compact(observation) + b"\n")
            self.require(f["label"] + ".write-control-fired", observation["write_control"]["refused"], observation)
            observation["released_at_ns"] = time.monotonic_ns()
            publish_witness(release, b"The independent write-refusal control fired; attempt the recorded mutation.\n")
            try:
                process.wait(timeout=15)
                natural_stop = True
            except subprocess.TimeoutExpired:
                self.check(f["label"] + ".bounded-owner-stop", False, "owner remained active for 15 seconds after recorder failure")
            self.check(f["label"] + ".owner-stopped-without-controller-signal", natural_stop,
                       {"exit": process.poll()})
        finally:
            if process.poll() is None:
                observation["cleanup_owner_kill"] = True
                process.kill()
                process.wait(timeout=5)
            stdout.close()
            stderr.close()
            observation["owner_exit"] = process.returncode
            if original_mode is not None:
                # The stop record itself may be impossible to write. Observe
                # groups independently before restoring any permission.
                groups_gone = not self.groups_absent(f, stop_record=False)
                observation["groups_observed_absent"] = groups_gone
                observation["stop_observed_at_ns"] = time.monotonic_ns()
                if groups_gone:
                    run_dir.chmod(original_mode)
                    observation["permissions_restored_at_ns"] = time.monotonic_ns()
                else:
                    observation["permissions_not_restored"] = "process-group stopping remains unobserved"
            (f["witness"] / "recorder-permissions-final.json").write_bytes(compact(observation) + b"\n")
        events = self.harness_events(f)
        calls = [e for e in events if e["event"] == "rpc-send" and e["value"].get("method") == "tools/call"
                 and e["value"].get("params", {}).get("name") == "record_account"]
        transmitted = {e["id"] for e in events if e["event"] == "rpc-transmitted"}
        self.require(f["label"] + ".attempt-witness", len(calls) == 1 and calls[0]["value"]["id"] in transmitted, calls)
        barriers = [e for e in events if e["event"] == "capture-barrier-released"]
        self.check(f["label"] + ".attempt-after-permission-change",
                   len(barriers) == 1 and barriers[0]["release_sha256"] == sha(release.read_bytes())
                   and events.index(barriers[0]) < events.index(calls[0]), barriers)
        records = [strict_loads(path.read_bytes()) for path in sorted((self.audit_path(f) / "log").glob("*.json"))]
        self.eq(f["label"] + ".no-entry-record", [r for r in records if r.get("kind") == "entry"], [])
        reply = strict_loads(stdout_path.read_bytes())
        self.eq(f["label"] + ".final-reply-schema", reply.get("schema"), "stewart.reply/2")
        contexts = [reply.get("reason"), reply.get("message"), stderr_path.read_text(errors="replace")]
        contexts += [json.dumps(cause) for cause in reply.get("causes", [])]
        for record in records:
            if record.get("kind") == "run_ended":
                contexts.extend([record["body"].get("cause"), record["body"].get("message")])
        # Restrict this check to diagnostic fields and remove paths: the case
        # name contains 'recorder-failure' and must not make its own check pass.
        contexts = [re.sub(r"/[^\s\"']+", "<path>", text.lower()) for text in contexts if isinstance(text, str)]
        explicit = any(capture_failure_diagnostic(text) for text in contexts)
        self.check(f["label"] + ".explicit-capture-write-failure", explicit, contexts)
        status_reply = self.cmd(f["label"] + ".status-after-failure", ["status", f["reference"]])
        answer = status_reply.get("data", {}).get("answer") or {}
        self.eq(f["label"] + ".no-answer-mutation", answer.get("entries"), 0)
        self.control("recorder-failure-stops-before-effects", natural_stop and groups_gone and explicit
                     and not any(r.get("kind") == "entry" for r in records) and answer.get("entries") == 0)

    def run(self):
        for name, _ in CASES:
            if name not in self.selected:
                continue
            self.current = name
            start = len(self.checks)
            reason = None
            try:
                if self.launch_blocked:
                    reason = self.launch_blocked
                else:
                    reason = getattr(self, name.replace("-", "_"))()
            except CaseStopped:
                pass
            except Exception:
                self.check(name + ".unexpected-error", False, traceback.format_exc())
            failures = sum(not row["passed"] for row in self.checks[start:])
            state = "failed" if failures else "skipped" if reason else "passed"
            self.cases.append({"name": name, "outcome": state, "checks": len(self.checks) - start,
                               "failures": failures, "skip_reason": reason})
            print("%s %s (%d checks)" % (state.upper(), name, len(self.checks) - start), flush=True)
        report = {"schema": "stewart.claude-code.offline-driver/2", "qualification": False,
                  "scope": "offline preparation and synthetic MCP runtime; no Claude or provider invocation",
                  "elapsed_seconds": time.monotonic() - self.started,
                  "cases": self.cases, "checks": self.checks, "controls": self.controls,
                  "notes": self.notes,
                  "not_selected": [name for name, _ in CASES if name not in self.selected],
                  "counts": {"cases": len(self.cases),
                             **{state: sum(c["outcome"] == state for c in self.cases)
                                for state in ("passed", "failed", "skipped")},
                             "checks": len(self.checks),
                             "checks_passed": sum(c["passed"] for c in self.checks),
                             "checks_failed": sum(not c["passed"] for c in self.checks),
                             "controls": len(self.controls),
                             "controls_fired": sum(c["fired"] for c in self.controls)}}
        self.save("RESULT.json", report)
        print(json.dumps(report["counts"], sort_keys=True), flush=True)
        print("Synthetic observations; qualification belongs to the enclosing suite. Retained work: %s" % self.work, flush=True)
        return 1 if report["counts"]["failed"] else 0


def synthetic_harness(scenario_path, environment_path, argv):
    """Synthetic executable only: no provider or real harness is ever invoked."""
    scenario = strict_loads(Path(scenario_path).read_bytes())
    witness = Path(scenario["witness"])
    environment_path = Path(environment_path)
    if environment_path.parent != witness:
        raise ValueError("environment witness must be in the scenario witness directory")
    environment_raw = environment_path.read_bytes()
    initial_environment = environment_snapshot(environment_raw)
    event_lock = threading.Lock()

    def event(kind, **data):
        with event_lock:
            with open(witness / "harness.jsonl", "ab") as stream:
                stream.write(compact({"event": kind, "pid": os.getpid(), "monotonic_ns": time.monotonic_ns(), **data}) + b"\n")

    with open(scenario["marker"], "ab") as stream:
        stream.write(compact(argv) + b"\n")
    role = "auth" if argv == ["auth", "status"] else "model"
    launch = {"role": role, "argv": argv, "environment": initial_environment,
              "environment_witness": environment_path.name, "environment_sha256": sha(environment_raw),
              "interpreted_environment": dict(os.environ), "cwd": os.getcwd()}
    if role == "auth":
        event("launch", **launch)
        print(json.dumps({"loggedIn": True, "authMethod": "claude.ai", "configDirectory": scenario["config"],
                          "private_unretained_field": scenario["auth_private"]}), flush=True)
        return 0
    mcp = None
    input_thread = None
    stop_inputs = threading.Event()
    try:
        def option(name):
            return argv[argv.index(name) + 1]
        settings = strict_loads(Path(option("--settings")).read_bytes())
        config = strict_loads(Path(option("--mcp-config")).read_bytes())
        system_prompt = Path(option("--system-prompt-file")).read_text()
        launch.update(settings=settings, mcp_config=config, system_prompt=system_prompt)
        event("launch", **launch)
        incoming = queue.Queue()

        def read_inputs():
            # Main controls the brief transmission-witness critical section.
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
            pending = b""
            while not stop_inputs.is_set():
                ready, _, _ = select.select([sys.stdin.fileno()], [], [], 0.05)
                if not ready:
                    continue
                chunk = os.read(sys.stdin.fileno(), 65536)
                if not chunk:
                    return
                pending += chunk
                while b"\n" in pending:
                    raw, pending = pending.split(b"\n", 1)
                    raw += b"\n"
                    value = strict_loads(raw)
                    event("input", value=value, raw_hex=raw.hex())
                    incoming.put(value)
        input_thread = threading.Thread(target=read_inputs, daemon=True)
        input_thread.start()
        incoming.get(timeout=10)

        def transmit(stream, raw, kind, **fields):
            # A correct receiver may stop this process as soon as it receives
            # a bad startup or a call whose capture failed. Keep TERM pending
            # only through the completed-write witness, then honor it.
            previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
            try:
                stream.write(raw)
                stream.flush()
                event(kind, **fields)
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous)

        def emit(value):
            raw = compact(value) + b"\n"
            event("output", value=value, raw_hex=raw.hex())
            transmit(sys.stdout.buffer, raw, "output-transmitted", sha256=sha(raw))

        plugins = ["cc-plugin-agents-md", "cc-plugin-privacy", "cc-plugin-plugin-authoring"]
        init = {"type": "system", "subtype": "init", "session_id": scenario["session"],
                "claude_code_version": scenario["version"], "model": scenario["model"],
                "apiKeySource": "none", "permissionMode": "dontAsk",
                "tools": ["mcp__stewart__" + t["name"] for t in expected_tools(scenario["family"])],
                "mcp_servers": [{"name": "stewart", "status": "connected"}],
                "plugins": [{"name": name, "path": "builtin", "source": name + "@builtin"} for name in plugins],
                "plugin_errors": [], "mcp_server_errors": []}
        if scenario["mode"] not in ("bad-init", "delayed-valid-init", "hooks"):
            emit(init)
        server = config["mcpServers"]["stewart"]
        mcp = subprocess.Popen([server["command"]] + server["args"], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=open(witness / (scenario["session"] + "-mcp.stderr"), "wb"),
                               env=os.environ.copy())
        sequence = 0
        unread = bytearray()
        inbox = {}

        def frame(method, params=None, notification=False, identity=None):
            nonlocal sequence
            value = {"jsonrpc": "2.0", "method": method}
            if not notification:
                if identity is None:
                    sequence += 1
                    identity = sequence
                value["id"] = identity
            if params is not None:
                value["params"] = params
            return value

        def send_frames(values):
            """One write for all the frames, so a receiver sees them pipelined."""
            raws = [compact(value) + b"\n" for value in values]
            for value, raw in zip(values, raws):
                event("rpc-send", value=value, raw_hex=raw.hex())
            transmit(mcp.stdin, b"".join(raws), "rpc-transmitted",
                     id=values[0].get("id"), method=values[0]["method"],
                     ids=[value.get("id") for value in values],
                     methods=[value["method"] for value in values])

        def send(method, params=None, notification=False):
            value = frame(method, params, notification)
            send_frames([value])
            return value.get("id", sequence)

        def read_frame(deadline):
            # Read the descriptor directly: a buffered reader could hold a
            # second pipelined reply where select cannot see it. Nonblocking
            # mode handles readiness races; it does not bound a kernel read
            # stall. The direct relay case has an independent owner watchdog.
            descriptor = mcp.stdout.fileno()
            os.set_blocking(descriptor, False)
            while b"\n" not in unread:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                ready, _, _ = select.select([descriptor], [], [], remaining)
                if not ready:
                    return None
                event("rpc-before-read", fd=descriptor, requested_bytes=65536)
                try:
                    chunk = os.read(descriptor, 65536)
                except BlockingIOError:
                    event("rpc-after-read", fd=descriptor, outcome="EAGAIN")
                    continue
                event("rpc-after-read", fd=descriptor, outcome="bytes" if chunk else "EOF", bytes=len(chunk))
                if not chunk:
                    raise RuntimeError("MCP server ended before reply")
                unread.extend(chunk)
            line, _, rest = bytes(unread).partition(b"\n")
            unread[:] = rest
            return line + b"\n"

        def receive(identity, timeout=8):
            deadline = time.monotonic() + timeout
            while identity not in inbox:
                raw = read_frame(deadline)
                if raw is None:
                    raise TimeoutError("no MCP reply for id %s" % identity)
                event("rpc-observed", raw_hex=raw.hex())
                value = mcp_message_loads(raw)
                event("rpc-receive", value=value, raw_hex=raw.hex())
                if "id" in value:
                    inbox[value["id"]] = value
            return inbox.pop(identity)

        hook_serial = 0

        def hook(tool_name, when):
            """Run the configured PreToolUse hook as the harness would for one call."""
            nonlocal hook_serial
            hook_serial += 1
            command = settings["hooks"]["PreToolUse"][0]["hooks"][0]
            payload = compact({"session_id": scenario["session"], "transcript_path": "",
                               "cwd": os.getcwd(), "permission_mode": "dontAsk",
                               "hook_event_name": "PreToolUse", "tool_name": tool_name,
                               "tool_input": {}, "tool_use_id": "toolu_synthetic_%d" % hook_serial}) + b"\n"
            try:
                done = subprocess.run(["/bin/sh", "-c", command["command"]], input=payload,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      timeout=command["timeout"])
                event("hook", when=when, tool=tool_name, input_hex=payload.hex(),
                      output_hex=done.stdout.hex(), stderr_hex=done.stderr.hex(), exit=done.returncode)
            except subprocess.TimeoutExpired:
                event("hook", when=when, tool=tool_name, input_hex=payload.hex(), timed_out=True)

        def rpc(method, params=None):
            return receive(send(method, params))

        rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                           "clientInfo": {"name": "stewart-independent-synthetic", "version": "1"}})
        send("notifications/initialized", notification=True)
        rpc("tools/list", {})
        if scenario["mode"] in ("bad-init", "delayed-valid-init"):
            identity = send("tools/call", {"name": "record_account", "arguments": {"text": scenario["account"]}})
            try:
                receive(identity, timeout=0.3)
            except TimeoutError:
                pass
            if scenario["mode"] == "bad-init":
                init["model"] = "deliberately-wrong-model"
            emit(init)
            if scenario["mode"] == "bad-init":
                time.sleep(600)
                return 9
        if scenario["mode"] == "hooks":
            hook("mcp__stewart__record_account", "before-startup")
            emit(init)

        def tool(name, arguments):
            response = rpc("tools/call", {"name": name, "arguments": arguments})
            if "error" in response:
                return {"outcome": "refused", "transport_error": response["error"]}
            content = response.get("result", {}).get("content", [])
            if not content or content[0].get("type") != "text":
                raise RuntimeError("MCP text reply missing: %r" % response)
            return strict_loads(content[0]["text"].encode())

        # Re-entry is the specified readiness observation; fresh request IDs keep
        # an early, gated refusal distinct from the subsequent successful call.
        for _ in range(100):
            reentry = tool("what_am_i_working_with", {})
            if reentry.get("outcome") == "completed":
                break
            time.sleep(0.01)
        else:
            raise RuntimeError("MCP gate never admitted re-entry: %r" % reentry)
        if scenario["mode"] == "capture-failure":
            publish_witness(witness / "capture-ready.json", compact({"model_pid": os.getpid(),
                "group": os.getpgrp(), "after": "successful core re-entry", "monotonic_ns": time.monotonic_ns()}) + b"\n")
            deadline = time.monotonic() + 10
            while not (witness / "release-capture-attempt").exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("independent driver never released capture-failure barrier")
                time.sleep(0.01)
            event("capture-barrier-released", release_sha256=sha((witness / "release-capture-attempt").read_bytes()))
        def turn_ended(checkpoint):
            # A turn ends with a cumulative main-loop result and no submission.
            emit({"type": "result", "subtype": "success", "is_error": False,
                  "session_id": scenario["session"], "num_turns": checkpoint["num_turns"],
                  "usage": checkpoint["usage"]})

        def compacted(serial):
            emit({"type": "system", "subtype": "compact_boundary", "session_id": scenario["session"],
                  "uuid": "00000000-0000-4000-8000-%012d" % serial,
                  "compact_metadata": {"trigger": "auto", "pre_tokens": 150000 + serial}})

        if scenario["mode"] == "hooks":
            pinned = "mcp__stewart__" + expected_tools(scenario["family"])[0]["name"]
            for tool_name in (pinned, "mcp__stewart__record_account", "Bash",
                              "mcp__stewart__no_such_tool", "mcp__other__record_account",
                              "record_account"):
                hook(tool_name, "after-startup")
        if scenario["mode"] == "relay-loss":
            recorded = tool("record_account", {"text": scenario["account"]})
            if recorded.get("outcome") != "completed":
                raise RuntimeError("record_account did not complete: %r" % recorded)
            publish_witness(witness / "relay-ready.json", compact({"model_pid": os.getpid(),
                "group": os.getpgrp(), "relay_pid": mcp.pid, "monotonic_ns": time.monotonic_ns()}) + b"\n")
            mcp.kill()
            mcp.wait(timeout=5)
            event("relay-killed", pid=mcp.pid, model_pid=os.getpid())
            # The model stays alive. A second relay must not become a writer.
            try:
                second = subprocess.Popen([server["command"]] + server["args"], stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=os.environ.copy())
                attempt = b"".join(compact(value) + b"\n" for value in (
                    {"jsonrpc": "2.0", "id": 9001, "method": "initialize", "params": {
                        "protocolVersion": "2025-11-25", "capabilities": {},
                        "clientInfo": {"name": "stewart-independent-synthetic", "version": "1"}}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 9002, "method": "tools/call", "params": {
                        "name": "record_account", "arguments": {"text": scenario["second_relay"]}}}))
                try:
                    out, _ = second.communicate(attempt, timeout=2)
                except subprocess.TimeoutExpired:
                    second.kill()
                    out, _ = second.communicate()
                event("second-relay", sent_hex=attempt.hex(), received_hex=out.hex(), exit=second.returncode)
            except OSError as exc:
                event("second-relay", error=str(exc))
            time.sleep(600)
            return 9
        if scenario["mode"] == "cancel":
            first = frame("tools/call", {"name": "record_account", "arguments": {"text": scenario["account"]}})
            send_frames([first])
            event("observation", name="first", response=receive(first["id"]))
            # A completed call cannot be undone, and an unknown request is nobody's.
            send("notifications/cancelled", {"requestId": first["id"], "reason": "late"}, notification=True)
            send("notifications/cancelled", {"requestId": 424242, "reason": "unknown"}, notification=True)
            event("observation", name="ping", response=rpc("ping"))
            # A reused identifier is refused, whatever its arguments.
            send_frames([frame("tools/call", {"name": "record_account", "arguments": {"text": scenario["duplicate"]}},
                               identity=first["id"])])
            try:
                event("observation", name="duplicate", response=receive(first["id"], timeout=3))
            except TimeoutError:
                event("observation", name="duplicate", response=None)
            # Both calls are sent before either reply. The second must complete
            # after the first, with their effects in the same order.
            kept = frame("tools/call", {"name": "record_account", "arguments": {"text": scenario["kept"]}})
            queued = frame("tools/call", {"name": "record_account", "arguments": {"text": scenario["queued"]}})
            send_frames([kept, queued])
            event("observation", name="kept", response=receive(kept["id"]))
            event("observation", name="queued", response=receive(queued["id"]))
            # A large predecessor makes a waiting cancellation observable without
            # adding a product test barrier. The outer check requires cancellation
            # to win and reports the limit of this external observation.
            predecessor = frame("tools/call", {"name": "record_account", "arguments": {"text": race_text(0)}})
            dropped = frame("tools/call", {"name": "record_account", "arguments": {"text": scenario["cancelled"]}})
            send_frames([predecessor, dropped, frame("notifications/cancelled",
                                              {"requestId": dropped["id"], "reason": "superseded"}, notification=True)])
            event("observation", name="predecessor", response=receive(predecessor["id"]))
            try:
                event("observation", name="cancelled", response=receive(dropped["id"], timeout=3))
            except TimeoutError:
                event("observation", name="cancelled", response=None)
            # Each race sends one call and its own cancellation together. Either may
            # win; the driver holds the service to a consistent outcome and
            # reports how many cancellations won.
            for number in range(1, RACES + 1):
                for _ in range(200):
                    if tool("what_am_i_working_with", {}).get("outcome") == "completed":
                        break
                    time.sleep(0.01)
                raced = frame("tools/call", {"name": "record_account", "arguments": {"text": race_text(number)}})
                send_frames([raced, frame("notifications/cancelled",
                                          {"requestId": raced["id"], "reason": "race"}, notification=True)])
                try:
                    event("observation", name="race-%d" % number, response=receive(raced["id"], timeout=3))
                except TimeoutError:
                    event("observation", name="race-%d" % number, response=None)
            for _ in range(200):
                reentry = tool("what_am_i_working_with", {})
                if reentry.get("outcome") == "completed":
                    break
                time.sleep(0.01)
            event("observation", name="reentry", response=reentry)
            scenario["skip_record"] = True
        if scenario["mode"] == "checkpoint-then-crash":
            recorded = tool("record_account", {"text": scenario["account"]})
            if recorded.get("outcome") != "completed":
                raise RuntimeError("record_account did not complete: %r" % recorded)
            turn_ended(CHECKPOINTS[1])
            incoming.get(timeout=10)  # the reminder; then this session dies without another result
            event("deliberate-interruption")
            return 7
        if scenario["mode"] == "resume-no-submit":
            turn_ended(SECOND_SESSION)
            time.sleep(600)
            return 9
        if scenario["mode"] == "compaction":
            recorded = tool("record_account", {"text": scenario["account"]})
            if recorded.get("outcome") != "completed":
                raise RuntimeError("record_account did not complete: %r" % recorded)
            compacted(1)
            incoming.get(timeout=10)
            event("observation", name="reentry-after-compaction", response=tool("what_am_i_working_with", {}))
            compacted(2)
            incoming.get(timeout=10)
            turn_ended(CHECKPOINTS[0])
            incoming.get(timeout=10)  # the reminder, still unspent after two compaction notices
            scenario["skip_record"] = True
        if scenario["mode"] == "hang":
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            child = subprocess.Popen([sys.executable, "-I", "-B", "-c",
                                      "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(600)"])
            publish_witness(witness / "ready.json", compact({"model_pid": os.getpid(), "descendant_pid": child.pid,
                                                            "group": os.getpgrp()}) + b"\n")
            event("resistant-descendant", pid=child.pid, group=os.getpgrp())
            time.sleep(600)
            return 9
        if not scenario.get("skip_record", False):
            recorded = tool("record_account", {"text": scenario["account"]})
            if recorded.get("outcome") != "completed":
                raise RuntimeError("record_account did not complete: %r" % recorded)
        if scenario["mode"] == "record-then-exit":
            event("deliberate-interruption")
            return 7
        if scenario["mode"] == "no-submit":
            turn_ended(CHECKPOINTS[0])
            incoming.get(timeout=10)  # the single reminder, witnessed as an input event
            turn_ended(CHECKPOINTS[1])
            time.sleep(600)
            return 9
        if "utf8_artifact" in scenario:
            artifact = tool("record_artifact", scenario["utf8_artifact"])
            if artifact.get("outcome") != "completed":
                raise RuntimeError("record_artifact did not complete: %r" % artifact)
        prepared = tool("prepare", {})
        if prepared.get("outcome") != "completed":
            raise RuntimeError("prepare did not complete: %r" % prepared)
        if scenario["mode"] == "submit-publication":
            identity = send("tools/call", {"name": "submit", "arguments": {
                "prepared": prepared["data"]["prepared"], "confirm": True}})
            event("submit-publication", id=identity, group=os.getpgrp())
            if scenario.get("publication_action") == "cancel":
                def wait_marker(name):
                    until = time.monotonic() + 30
                    while not (witness / name).exists():
                        if time.monotonic() >= until:
                            raise TimeoutError("missing external publication control: " + name)
                        time.sleep(0.01)
                wait_marker("cancel-submit")
                send("notifications/cancelled", {"requestId": identity, "reason": "publication control"}, notification=True)
                event("submit-cancellation-ping", response=rpc("ping"))
                event("submit-cancelled-reply", response=receive(identity))
                event("submit-cancelled-reentry", response=tool("what_am_i_working_with", {}))
                wait_marker("retry-submit")
                prepared = tool("prepare", {})
                send("tools/call", {"name": "submit", "arguments": {
                    "prepared": prepared["data"]["prepared"], "confirm": True}})
                event("submit-retried")
            time.sleep(600)
            return 9
        # The runtime captures and attempts to send the submit reply before
        # stopping the harness. Its independent archive record is checked by
        # the outer driver even if shutdown wins the peer's next read.
        send("tools/call", {"name": "submit", "arguments": {"prepared": prepared["data"]["prepared"], "confirm": True}})
        time.sleep(600)
        return 9
    except Exception:
        event("fatal", error=traceback.format_exc())
        return 8
    finally:
        stop_inputs.set()
        if input_thread is not None:
            input_thread.join(timeout=1)
        if mcp is not None and mcp.stdin is not None:
            mcp.stdin.close()


def self_test():
    checks = []
    def check(name, value):
        checks.append((name, bool(value)))
    specimen = (Path("/synthetic dir/harness.py"), Path("/scenario dir/scenario.json"), Path("/witness dir"))
    default_wrapper = synthetic_executable(*specimen)
    default_command = shlex.split(default_wrapper.decode().splitlines()[-1])
    check("synthetic-wrapper.default-interpreter", default_command == ["exec", sys.executable, "-I", "-B",
          "/synthetic dir/harness.py", "--synthetic-harness", "/scenario dir/scenario.json",
          "--environment-witness", "$environment_witness", "$@"])
    bound_wrapper = synthetic_executable(*specimen, python=Path("/bound interpreter/python3.9"))
    bound_command = shlex.split(bound_wrapper.decode().splitlines()[-1])
    check("synthetic-wrapper.bound-interpreter-only", bound_command ==
          ["exec", "/bound interpreter/python3.9"] + default_command[2:]
          and bound_wrapper.splitlines()[:-1] == default_wrapper.splitlines()[:-1])
    with tempfile.TemporaryDirectory(prefix="stewart-work-preflight-") as directory:
        outside = Path(directory).resolve()
        for label, path in (("external", outside / "new-work"), ("external-nested", outside / "nested" / "work")):
            try:
                validate_work_path(path)
            except ValueError:
                accepted = False
            else:
                accepted = True
            check("work-preflight." + label, accepted and not path.exists())
        forbidden = HERE.parent.parent / outside.name
        child = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                                "--binary", sys.executable, "--work", str(forbidden)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        check("work-preflight.repository-refused", child.returncode == 2
              and b"--work must be outside the driver repository" in child.stderr)
        check("work-preflight.refusal-has-no-files", not forbidden.exists())
        try:
            validate_work_path(HERE.parent.parent / "unused" / ".." / ".scratch" / "work")
        except ValueError:
            normalized_refused = True
        else:
            normalized_refused = False
        check("work-preflight.normalized-descendant-refused", normalized_refused)
    with tempfile.TemporaryDirectory(prefix="stewart-release-witness-") as directory:
        root = Path(directory)
        paused = root / "log.publish:seal.paused"
        paused.write_bytes(b"")
        events = []
        release_fault_pauses(root, lambda event, **facts: events.append((event, facts)))
        go = paused.with_suffix(".go")
        check("fault-release.positive", go.exists() and go.read_bytes() == b"" and len(events) == 1)
        go.write_bytes(b"first release witness")
        os.utime(go, ns=(123456789, 123456789))
        first_time = go.stat().st_mtime_ns
        release_fault_pauses(root, lambda event, **facts: events.append((event, facts)))
        check("fault-release.cleanup-keeps-first-bytes-and-time", go.read_bytes() == b"first release witness"
              and go.stat().st_mtime_ns == first_time)
        check("fault-release.cleanup-adds-no-second-event", len(events) == 1)
    environment_root = Path(tempfile.mkdtemp(prefix="stewart-environment-driver-selftest-"))
    print("Environment self-test evidence retained: %s" % environment_root, flush=True)
    check("environment.nul-decoder-values", environment_snapshot(b"A=line\nwith=equals\0EMPTY=\0")
          == {"A": "line\nwith=equals", "EMPTY": ""})
    check("environment.empty-decoder", environment_snapshot(b"") == {})
    for name, raw in (("truncated", b"A=1"), ("duplicate", b"A=1\0A=2\0"),
                      ("empty-entry", b"A=1\0\0"), ("no-equals", b"A\0"),
                      ("empty-name", b"=1\0"), ("invalid-utf8", b"A=\xff\0")):
        try:
            environment_snapshot(raw)
        except ValueError:
            refused = True
        else:
            refused = False
        check("environment.decoder-refuses-" + name, refused)
    scenario = {"witness": str(environment_root), "marker": str(environment_root / "started"),
                "config": str(environment_root), "auth_private": "synthetic-environment-control"}
    (environment_root / "scenario.json").write_bytes(compact(scenario))
    executable = environment_root / "synthetic-harness"
    executable.write_bytes(synthetic_executable(Path(__file__).resolve(), environment_root / "scenario.json", environment_root))
    executable.chmod(0o700)
    expected = {key: value.replace("{home}", str(environment_root / "home"))
                .replace("{temporary_directory}", str(environment_root / "temporary"))
                .replace("{config_directory}", str(environment_root / "config"))
                for key, value in surface_document()["environment"].items()}
    preserved, observations = {}, []
    for name, changes, rejected in (("normal", {}, None), ("locale-injection", {"LC_CTYPE": "C.UTF-8"}, "nothing-else"),
                                    ("changed-lang", {"LANG": "C"}, "supplied"),
                                    ("extra-variable", {"DRIVER_INJECTION": "synthetic"}, "nothing-else"),
                                    ("invariance", {}, None)):
        supplied = dict(expected, **changes)
        result = subprocess.run([str(executable), "auth", "status"], env=supplied, cwd=environment_root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        (environment_root / (name + ".stdout")).write_bytes(result.stdout)
        (environment_root / (name + ".stderr")).write_bytes(result.stderr)
        check("environment." + name + ".auth-ran", result.returncode == 0)
        events_path = environment_root / "harness.jsonl"
        events = [json.loads(line) for line in events_path.read_bytes().splitlines()] if events_path.exists() else []
        event = events[-1] if len(events) == len(observations) + 1 else {}
        if not event:
            check("environment." + name + ".launch-witness", False)
            continue
        observer = object.__new__(Driver)
        observer.checks, observer.current = [], "environment-self-test"
        with (environment_root / (name + ".inspection.stdout")).open("w") as stream, contextlib.redirect_stdout(stream):
            observer.inspect_environment(name, event, expected, environment_root)
        failed = [row["name"] for row in observer.checks if not row["passed"]]
        check("environment." + name + ".contract-observation", failed == ([name + "." + rejected] if rejected else []))
        check("environment." + name + ".supplied-values-witnessed",
              all(event["environment"].get(key) == value for key, value in supplied.items()))
        snapshot_path = environment_root / event["environment_witness"]
        check("environment." + name + ".unique-witness", snapshot_path.name not in preserved
              and all((environment_root / member).read_bytes() == raw for member, raw in preserved.items()))
        preserved[snapshot_path.name] = snapshot_path.read_bytes()
        before, after = event["environment"], event["interpreted_environment"]
        change = {"case": name, "before": before, "after": after,
                  "added": sorted(set(after) - set(before)), "removed": sorted(set(before) - set(after)),
                  "changed": sorted(key for key in before.keys() & after.keys() if before[key] != after[key])}
        observations.append(change)
        print("Environment control %s: post-Python added=%s changed=%s removed=%s" % (
            name, change["added"], change["changed"], change["removed"]), flush=True)
    (environment_root / "OBSERVATIONS.json").write_bytes(compact(observations) + b"\n")
    check("environment.normal-invariance", len(observations) == 5
          and observations[0]["before"] == observations[-1]["before"])
    relay_root = Path(tempfile.mkdtemp(prefix="stewart-relay-driver-selftest-"))
    print("Relay self-test evidence retained: %s" % relay_root, flush=True)

    def supervised_control(name, action, seconds=0.2):
        record = relay_supervised(relay_root / name, action, seconds)
        check("relay-owner." + name + ".group-stopped", record["group_stopped"])
        if not record["group_stopped"]:
            raise RuntimeError("self-test owned group stopping unknown: %s" % record)
        return record

    record = supervised_control("pipe-reader", relay_pipe_control, 2)
    check("relay-owner.pipe-idle-open-bytes-eof", relay_success(record))
    journal = [json.loads(raw) for raw in (relay_root / "pipe-reader/controller-events.jsonl").read_bytes().splitlines()]
    check("relay-owner.independent-byte-witness", (relay_root / "pipe-reader/observed-pipe.bin").read_bytes()
          == RELAY_REPLY and any(row.get("raw_hex") == RELAY_REPLY.hex() for row in journal))
    check("relay-owner.read-checkpoints", all(stage in {row.get("stage") for row in journal}
          for stage in ("before-select", "after-select", "before-os-read", "after-os-read")))

    def stall(witness, stage):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        witness.bytes("partial.bin", b"before stall\x00\xff")
        witness.event(stage)
        # A real blocking read with a writer kept open; the owner must remain
        # responsive even when no Python deadline can run in this worker.
        reader, writer = os.pipe()
        os.read(reader, 1)
        os.close(writer)
        os.close(reader)

    for stage in ("before-popen", "before-os-read", "before-worker-cleanup"):
        record = supervised_control(stage, lambda witness: stall(witness, stage))
        check("relay-owner." + stage + ".timeout", record["timed_out"] and not relay_success(record)
              and record["elapsed_seconds"] < 2 and record["last_phase"]["stage"] == stage
              and any(row["signal"] == "SIGKILL" for row in record["signals"]))
        check("relay-owner." + stage + ".partial-witness", (relay_root / stage / "partial.bin").read_bytes()
              == b"before stall\x00\xff")

    def lingering_descendant(witness):
        ready_r, ready_w = os.pipe()
        child = os.fork()
        if child == 0:
            os.close(ready_r)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            os.write(ready_w, b"r")
            time.sleep(30)
            os._exit(0)
        os.close(ready_w)
        os.read(ready_r, 1)
        os.close(ready_r)
        witness.event("resistant-descendant-ready", descendant=child)
        time.sleep(30)  # worker accepts TERM; descendant does not

    record = supervised_control("lingering-descendant", lingering_descendant)
    check("relay-owner.reaped-worker-does-not-hide-descendant", record["timed_out"]
          and record["elapsed_seconds"] < 2 and any(row["signal"] == "SIGKILL" for row in record["signals"]))
    record = supervised_control("invariance", relay_pipe_control, 2)
    check("relay-owner.invariance-after-timeouts", relay_success(record))

    # Exercise the driver's actual dispatch: uncertain stopping prevents the
    # next selected case from launching and remains visible as a skip.
    dispatcher = object.__new__(Driver)
    dispatcher.selected = {"families", "binding-controls"}
    dispatcher.launch_blocked = None
    dispatcher.cases, dispatcher.checks, dispatcher.controls, dispatcher.notes = [], [], [], []
    dispatcher.started, dispatcher.work = time.monotonic(), relay_root
    saved = {}
    dispatcher.save = lambda name, value: saved.update({name: value})
    def unknown_stop():
        dispatcher.launch_blocked = "self-test deliberately unresolved owned group"
        dispatcher.check("self-test.unresolved-group", False, "expected firing control")
        raise CaseStopped()
    dispatcher.families = unknown_stop
    dispatched = []
    dispatcher.binding_controls = lambda: dispatched.append("unexpected launch")
    with (relay_root / "dispatch-control.stdout").open("w") as stream, contextlib.redirect_stdout(stream):
        dispatcher.run()
    check("relay-owner.unknown-stop-blocks-launch", not dispatched
          and [row["outcome"] for row in saved["RESULT.json"]["cases"]] == ["failed", "skipped"]
          and saved["RESULT.json"]["cases"][1]["skip_reason"] == dispatcher.launch_blocked)
    valid_error = b'{"jsonrpc":"2.0","id":3,"error":{"code":-32000,"message":"startup pending"}}'
    check("mcp.signed-error", mcp_message_loads(valid_error)["error"]["code"] == -32000)
    check("mcp.signed-id", mcp_message_loads(b'{"jsonrpc":"2.0","id":-1,"result":{}}')["id"] == -1)
    check("mcp.unknown-id-error", mcp_message_loads(b'{"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"parse error"}}')["id"] is None)
    check("mcp.metadata-numbers", mcp_message_loads(b'{"jsonrpc":"2.0","id":"x","result":{},"_meta":{"n":-1.25}}')["_meta"]["n"] == -1.25)
    malformed = {
        "duplicate-code": b'{"jsonrpc":"2.0","id":3,"error":{"code":-32000,"code":0,"message":"x"}}',
        "escaped-duplicate-code": b'{"jsonrpc":"2.0","id":3,"error":{"code":-32000,"\\u0063ode":0,"message":"x"}}',
        "duplicate-id": b'{"jsonrpc":"2.0","id":3,"id":4,"result":{}}',
        "string-code": b'{"jsonrpc":"2.0","id":3,"error":{"code":"-32000","message":"x"}}',
        "bool-code": b'{"jsonrpc":"2.0","id":3,"error":{"code":true,"message":"x"}}',
        "fraction-code": b'{"jsonrpc":"2.0","id":3,"error":{"code":-32000.5,"message":"x"}}',
        "missing-message": b'{"jsonrpc":"2.0","id":3,"error":{"code":-32000}}',
        "null-id": b'{"jsonrpc":"2.0","id":null,"result":{}}',
        "missing-error-id": b'{"jsonrpc":"2.0","error":{"code":-32700,"message":"parse error"}}',
        "null-request-id": b'{"jsonrpc":"2.0","id":null,"method":"ping"}',
        "bool-id": b'{"jsonrpc":"2.0","id":true,"result":{}}',
        "fraction-id": b'{"jsonrpc":"2.0","id":1.5,"result":{}}',
        "wrong-version": b'{"jsonrpc":"1.0","id":3,"result":{}}',
        "both-results": b'{"jsonrpc":"2.0","id":3,"result":{},"error":{"code":-32000,"message":"x"}}',
        "neither-result": b'{"jsonrpc":"2.0","id":3}',
        "array-result": b'{"jsonrpc":"2.0","id":3,"result":[]}',
        "nan": b'{"jsonrpc":"2.0","id":3,"result":{"x":NaN}}',
        "nul-message": b'{"jsonrpc":"2.0","id":3,"error":{"code":-32000,"message":"\\u0000"}}',
        "surrogate-message": b'{"jsonrpc":"2.0","id":3,"error":{"code":-32000,"message":"\\ud800"}}',
        "trailing": valid_error + b'{}',
        "invalid-utf8": valid_error + b'\xff',
    }
    for name, raw in malformed.items():
        try:
            mcp_message_loads(raw)
        except ValueError:
            refused = True
        else:
            refused = False
        check("mcp.refuses." + name, refused)
    try:
        strict_loads(b'{"count":-1}')
    except ValueError:
        core_still_strict = True
    else:
        core_still_strict = False
    check("mcp.core-decoder-stays-unsigned", core_still_strict)
    spec = (HERE.parent.parent / "docs" / "claude-code" / "CONTRACT.md").read_text()
    paragraphs = []
    current = []
    for line in spec.splitlines() + [""]:
        if line.startswith("> "):
            current.append(line[2:])
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    for name, text in (("orientation", FIRST_PARAGRAPH), ("near-limit", NEAR_LIMIT), ("compacted", COMPACTED)):
        check("spec." + name, text in paragraphs)
    example, stated = surface_example(spec)
    check("surface.example-bytes", SURFACE == example)
    check("surface.example-digest", SURFACE_SHA == stated == sha(example))
    check("surface.ascii", all(byte < 128 for byte in SURFACE) and not SURFACE.endswith(b"\n"))
    check("surface.member-order", list(strict_loads(SURFACE)) == [
        "schema", "working_directory", "auth_argv", "model_argv", "effort_argv", "settings",
        "mcp_config", "environment", "controls", "system_prompt", "input", "mcp_initialize",
        "hook_replies", "texts"])
    check("surface.environment-count", len(surface_document()["environment"]) == 15)
    changed = surface_document()
    changed["environment"]["CLAUDE_CODE_MAX_RETRIES"] = "1"
    check("surface.value-firing-control", sha(compact(changed)) != SURFACE_SHA)
    changed = surface_document()
    changed["texts"]["reminder_sha256"] = sha((REMINDER + "\n").encode())
    check("surface.text-firing-control", sha(compact(changed)) != SURFACE_SHA)
    profile_launch = {"home": "/h", "temporary_directory": "/t", "config_directory": "/c"}
    first = filled_launch("/one/stewart", "/w1", profile_launch, "open-inquiry", MODEL)
    second = filled_launch("/two/it's/stewart", "/w2", profile_launch, "open-inquiry", MODEL)
    check("surface.placeholders-only-differ", first != second and compact(surface_document()) == SURFACE)
    check("surface.one-argument-per-tool", [a for a in first["model_argv"] if a.startswith("mcp__stewart__")]
          == ["mcp__stewart__" + tool["name"] for tool in expected_tools("open-inquiry")])
    check("surface.filled-paths", first["model_argv"][first["model_argv"].index("--settings") + 1]
          == "/w1/settings.json" and first["environment"]["HOME"] == "/h"
          and first["mcp_config"]["mcpServers"]["stewart"]["command"] == "/one/stewart")
    check("surface.hook-quoting", second["settings"]["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
          == "'/two/it'\\''s/stewart' __stewart-cc-hook 'h'")
    for family in FAMILY_TEXT:
        base = compact(expected_tools(family))
        mapped = mcp_tools(base)
        check(family + ".tool-order", [x["name"] for x in json.loads(mapped)] == [x["name"] for x in json.loads(base)])
        for source, target in zip(expected_tools(family), parse(mapped).items):
            expected_schema = json.dumps(source["input_schema"], ensure_ascii=False, separators=(",", ":")).encode()
            check(family + ".schema." + source["name"], expected_schema == target.get("inputSchema").raw)
        check(family + ".order", all(node.keys() == ["name", "description", "inputSchema"] for node in parse(mapped).items))
        changed = bytearray(mapped)
        changed[-2] = ord(" ")
        check(family + ".hash-control", sha(changed) != sha(mapped))
    unusual = b'[{"name":"x","description":"d","input_schema": { "type" : "object" }}]'
    check("mapping.raw-whitespace", b'"inputSchema":{ "type" : "object" }' in mcp_tools(unusual))
    profile = b'{"launch": { "model" : "x" },"check":1}'
    check("launch.raw-binding-control", sha(parse(profile).get("launch").raw) != sha(compact({"model": "x"})))
    check("launch.outer-whitespace-invariance", sha(parse(profile).get("launch").raw) == sha(parse(b"\n" + profile + b" ").get("launch").raw))
    before = {"item": {"sha256": "one", "inode": 5, "mode": 0o100600}}
    check("inventory.positive", immutable_changes(before, copy.deepcopy(before)) == [])
    changed = copy.deepcopy(before)
    changed["item"]["sha256"] = "two"
    check("inventory.firing-control", immutable_changes(before, changed) == ["item"])
    added = dict(before, new={"sha256": "new"})
    check("inventory.addition-invariance", immutable_changes(before, added) == [])
    check("recorder-diagnostic.positive", capture_failure_diagnostic("write capture failed: Permission denied"))
    check("recorder-diagnostic.nonfailure-control", not capture_failure_diagnostic("capture completed"))
    check("recorder-diagnostic.path-is-not-evidence", not capture_failure_diagnostic("writer /private/tmp/runtime-recorder-failure"))
    check("recorder-diagnostic.unrelated-write-is-not-capture", not capture_failure_diagnostic("write diagnostic failed: Permission denied"))
    check("recorder-diagnostic.path-invariance", capture_failure_diagnostic("write capture failed: Permission denied /unrelated/path"))
    for name, value in (("used", 1), ("allowed", 5), ("remaining", 4)):
        check("summary.placement." + name, summary_placement_fact("1 used, 5 allowed, 4 remaining; 60 seconds", name, value))
        check("summary.unrelated-numbers." + name, not summary_placement_fact("1, 5, 4; 60 seconds", name, value))
    check("summary.allowed-remaining-swap-fires", not summary_placement_fact("1 used, 4 allowed, 5 remaining", "allowed", 5)
          and not summary_placement_fact("1 used, 4 allowed, 5 remaining", "remaining", 4))
    check("summary.used-of-and-remain-invariance", all(summary_placement_fact(
        "Placement starts: 1 used of 5; 4 remain.", name, value)
        for name, value in (("used", 1), ("allowed", 5), ("remaining", 4))))
    owned = subprocess.Popen(["/bin/sleep", "10"], start_new_session=True)
    try:
        check("group-observer.live-firing-control", group_observation(owned.pid) == "present")
        owned.terminate()
        owned.wait(timeout=5)
        check("group-observer.absence", group_observation(owned.pid) == "absent")
        unrelated = subprocess.Popen(["/bin/sleep", "10"], start_new_session=True)
        try:
            check("group-observer.unrelated-group-invariance", group_observation(owned.pid) == "absent"
                  and group_observation(unrelated.pid) == "present")
        finally:
            unrelated.terminate()
            unrelated.wait(timeout=5)
        def denied(group, sig):
            raise PermissionError("synthetic observer denial")
        check("group-observer.denial-is-unknown", group_observation(owned.pid, denied) == "unknown")
    finally:
        if owned.poll() is None:
            owned.terminate()
            owned.wait(timeout=5)
    with tempfile.TemporaryDirectory(prefix="stewart-offline-canary-") as directory:
        canary = Path(directory) / "synthetic-harness"
        canary.write_bytes(CANARY)
        canary.chmod(0o700)
        marker = Path(str(canary) + ".started")
        check("canary.absent-before", not marker.exists())
        result = subprocess.run([str(canary)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={"PATH": "/usr/bin:/bin"}, timeout=5)
        check("canary.firing-control", result.returncode == 97 and marker.read_bytes() == b"unexpected local launch\n")
    # Each further scenario runs against a specification-only peer, so that
    # the synthetic harness's own sequencing is known before a binary is used.
    mode_peer = '''import json,sys
pending_submit=None
cancelled_submit=False
for raw in sys.stdin.buffer:
    q=json.loads(raw)
    if q["method"]=="notifications/cancelled" and pending_submit is not None:
        result={"content":[{"type":"text","text":json.dumps({"outcome":"refused","reason":"placement_stopped","effects":{"seal":"none","raw_capture":"recorded"}})}]}
        print(json.dumps({"jsonrpc":"2.0","id":pending_submit,"result":result}),flush=True)
        pending_submit=None
        cancelled_submit=True
    if publication and q.get("params",{}).get("name")=="submit" and not cancelled_submit:
        pending_submit=q["id"]
        continue
    if "id" not in q: continue
    method=q["method"]
    result={}
    if method=="initialize": result={"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"serverInfo":{"name":"self-test","version":"1"}}
    if method=="tools/list": result={"tools":[]}
    if method=="tools/call": result={"content":[{"type":"text","text":json.dumps({"outcome":"completed","data":{"prepared":"ap1.selftest"}})}]}
    print(json.dumps({"jsonrpc":"2.0","id":q["id"],"result":result}),flush=True)
'''
    def user(text):
        return compact({"type": "user", "session_id": "", "parent_tool_use_id": None,
                        "message": {"role": "user", "content": text}}) + b"\n"
    submitted = lambda e: e["event"] == "rpc-send" and e["value"].get("params", {}).get("name") == "submit"
    modes = (
        ("submit", 1, submitted),
        ("record-then-exit", 1, None),
        ("cancel", 1, submitted),
        ("submit-publication", 1, lambda e: e["event"] == "submit-retried"),
        ("compaction", 4, submitted),
        ("hooks", 1, submitted),
        ("relay-loss", 1, lambda e: e["event"] == "second-relay"),
        ("checkpoint-then-crash", 2, None),
        ("resume-no-submit", 1, lambda e: e["event"] == "output-transmitted" and e.get("last")),
        ("no-submit", 2, lambda e: e["event"] == "output-transmitted" and e.get("last")),
    )
    for mode, inputs, finished in modes:
        with tempfile.TemporaryDirectory(prefix="stewart-synthetic-mode-") as directory:
            root = Path(directory)
            scenario = {"mode": mode, "witness": str(root), "marker": str(root / "started"),
                        "config": str(root), "version": "synthetic-offline-1", "model": MODEL,
                        "family": "open-inquiry", "session": "synthetic-" + mode, "account": ACCOUNT,
                        "kept": KEPT, "queued": QUEUED, "cancelled": CANCELLED, "duplicate": DUPLICATE,
                        "second_relay": SECOND_RELAY, "auth_private": "synthetic-private-auth-field"}
            if mode in ("submit", "record-then-exit"):
                scenario["utf8_artifact"] = {"label": "synthetic UTF-8 artifact", "text": "Exact café trace.\r\n界\n"}
            if mode == "submit-publication":
                scenario["publication_action"] = "cancel"
                for marker in ("cancel-submit", "retry-submit"):
                    (root / marker).write_bytes(b"")
            (root / "scenario.json").write_bytes(compact(scenario))
            (root / "peer.py").write_text("publication=%r\n" % (mode == "submit-publication") + mode_peer)
            (root / "settings.json").write_bytes(compact({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
                {"type": "command", "command": "cat >/dev/null; printf '{}\\n'", "timeout": 5}]}]}}))
            (root / "prompt").write_text("synthetic self-test prompt")
            (root / "mcp.json").write_bytes(compact({"mcpServers": {"stewart": {"command": sys.executable,
                "args": ["-I", "-B", str(root / "peer.py")]}}}))
            executable = root / "synthetic-harness"
            executable.write_bytes(synthetic_executable(Path(__file__).resolve(), root / "scenario.json", root))
            executable.chmod(0o700)
            process = subprocess.Popen(
                [str(executable), "-p", "--settings", str(root / "settings.json"),
                 "--mcp-config", str(root / "mcp.json"), "--system-prompt-file", str(root / "prompt")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={"PATH": "/usr/bin:/bin"}, cwd=root)
            process.stdin.write(b"".join(user("synthetic input %d" % n) for n in range(inputs)))
            process.stdin.flush()
            deadline = time.monotonic() + 20
            events = []
            results = 2 if mode == "no-submit" else 1
            while time.monotonic() < deadline:
                log = root / "harness.jsonl"
                events = [json.loads(line) for line in log.read_bytes().splitlines()] if log.exists() else []
                if mode in ("resume-no-submit", "no-submit"):
                    # The last result's completed write is the marker for these two.
                    sent = [e for e in events if e["event"] == "output" and e["value"].get("type") == "result"]
                    done = [e for e in events if e["event"] == "output-transmitted"]
                    if len(sent) == results and done and done[-1]["sha256"] == sha(bytes.fromhex(sent[-1]["raw_hex"])):
                        break
                elif finished is None:
                    if process.poll() is not None:
                        break
                elif any(finished(e) for e in events) or any(e["event"] == "fatal" for e in events):
                    break
                time.sleep(0.02)
            if finished is None:
                code = process.wait(timeout=5)
            else:
                process.terminate()
                code = process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()
            fatal = [e.get("error") for e in events if e["event"] == "fatal"]
            check("mode." + mode + ".no-fatal", not fatal)
            if fatal:
                print(fatal[0])
            names = [e["name"] for e in events if e["event"] == "observation"]
            outputs = [e["value"] for e in events if e["event"] == "output"]
            kinds = [(o.get("type"), o.get("subtype")) for o in outputs]
            consumed = sum(e["event"] == "input" for e in events)
            if mode in ("submit", "record-then-exit"):
                calls = [e["value"]["params"] for e in events if e["event"] == "rpc-send"
                         and e["value"].get("method") == "tools/call"]
                recorded = [call for call in calls if call["name"] == "record_artifact"]
                check("mode." + mode + ".optional-artifact", recorded == ([{"name": "record_artifact",
                      "arguments": {"label": "synthetic UTF-8 artifact", "text": "Exact café trace.\r\n界\n"}}]
                      if mode == "submit" else []))
                authoring = [call["name"] for call in calls if call["name"] in
                             {"record_account", "record_artifact", "prepare", "submit"}]
                check("mode." + mode + ".authoring-order", authoring ==
                      (["record_account", "record_artifact", "prepare", "submit"] if mode == "submit" else ["record_account"]))
            elif mode == "cancel":
                check("mode.cancel.observations", names == ["first", "ping", "duplicate", "kept", "queued", "predecessor", "cancelled"]
                      + ["race-%d" % number for number in range(1, RACES + 1)] + ["reentry"])
                check("mode.cancel.pipelined", any(e["event"] == "rpc-transmitted" and e["methods"] ==
                      ["tools/call", "tools/call", "notifications/cancelled"] for e in events))
                check("mode.cancel.uncancelled-pipeline", any(e["event"] == "rpc-transmitted" and e["methods"] ==
                      ["tools/call", "tools/call"] for e in events))
                sent = [e["value"] for e in events if e["event"] == "rpc-send"]
                ids = [v["id"] for v in sent if v["method"] == "tools/call" and v["params"]["name"] == "record_account"]
                check("mode.cancel.reused-id", len(ids) == 6 + RACES and ids[0] == ids[1] and len(set(ids)) == 5 + RACES)
                cancels = [v["params"]["requestId"] for v in sent if v["method"] == "notifications/cancelled"]
                check("mode.cancel.cancel-targets", cancels == [ids[0], 424242] + ids[5:])
                check("mode.cancel.race-size", len(race_text(1)) == 262144 and race_text(1) != race_text(2))
                check("mode.cancel.submits", any(submitted(e) for e in events))
            elif mode == "submit-publication":
                transitions = [e["event"] for e in events if e["event"].startswith("submit-")]
                check("mode.submit-publication.order", transitions == ["submit-publication", "submit-cancellation-ping",
                      "submit-cancelled-reply", "submit-cancelled-reentry", "submit-retried"])
                refused = next((e["response"] for e in events if e["event"] == "submit-cancelled-reply"), {})
                check("mode.submit-publication.named-refusal", (Driver.core_reply(None, refused) or {}).get("reason") == "placement_stopped")
                check("mode.submit-publication.later-call", any(e["event"] == "submit-cancelled-reentry"
                      and e["response"].get("outcome") == "completed" for e in events))
                check("mode.submit-publication.confirmed-retry", sum(submitted(e) for e in events) == 2)
            elif mode == "compaction":
                check("mode.compaction.sequence", kinds == [("system", "init"), ("system", "compact_boundary"),
                      ("system", "compact_boundary"), ("result", "success")])
                check("mode.compaction.inputs", consumed == 4 and names == ["reentry-after-compaction"])
                check("mode.compaction.submits", any(submitted(e) for e in events))
            elif mode == "hooks":
                hooks = [e for e in events if e["event"] == "hook"]
                check("mode.hooks.count", [h["when"] for h in hooks] == ["before-startup"] + ["after-startup"] * 6)
                check("mode.hooks.replies", all(h.get("output_hex") == b"{}\n".hex() and h.get("exit") == 0 for h in hooks))
                order = [e["event"] for e in events if e["event"] == "hook"
                         or (e["event"] == "output" and e["value"].get("subtype") == "init")]
                check("mode.hooks.before-startup-precedes-init", order[:2] == ["hook", "output"])
                check("mode.hooks.submits", any(submitted(e) for e in events))
            elif mode == "relay-loss":
                check("mode.relay-loss.sequence", [e["event"] for e in events
                      if e["event"] in ("relay-killed", "second-relay")] == ["relay-killed", "second-relay"])
                check("mode.relay-loss.model-stays", code == -signal.SIGTERM)
                second = next((e for e in events if e["event"] == "second-relay"), {})
                check("mode.relay-loss.second-attempt-witnessed", bool(second.get("received_hex")))
            elif mode == "checkpoint-then-crash":
                check("mode.checkpoint-then-crash.exit", code == 7 and consumed == 2)
                check("mode.checkpoint-then-crash.result", [o["usage"] for o in outputs if o.get("type") == "result"]
                      == [CHECKPOINTS[1]["usage"]])
            elif mode == "resume-no-submit":
                check("mode.resume-no-submit.result", [o["usage"] for o in outputs if o.get("type") == "result"]
                      == [SECOND_SESSION["usage"]])
            elif mode == "no-submit":
                check("mode.no-submit.results", [o["num_turns"] for o in outputs if o.get("type") == "result"] == [2, 3])
    with tempfile.TemporaryDirectory(prefix="stewart-synthetic-protocol-") as directory:
        root = Path(directory)
        scenario = {"mode": "record-then-exit", "witness": str(root), "marker": str(root / "started"),
                    "config": str(root), "version": "synthetic-offline-1", "model": MODEL,
                    "family": "open-inquiry", "session": "synthetic-self-test", "account": ACCOUNT,
                    "auth_private": "synthetic-private-auth-field"}
        (root / "scenario.json").write_bytes(compact(scenario))
        # This tiny specification-only peer checks the synthetic harness's own
        # framing and sequencing. It is not evidence about the Stewart adapter.
        peer = '''import json,sys
for raw in sys.stdin.buffer:
    q=json.loads(raw)
    if "id" not in q: continue
    method=q["method"]
    result={}
    if method=="initialize": result={"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"serverInfo":{"name":"self-test","version":"1"}}
    if method=="tools/list": result={"tools":[]}
    if method=="tools/call": result={"content":[{"type":"text","text":json.dumps({"outcome":"completed","data":{}})}]}
    print(json.dumps({"jsonrpc":"2.0","id":q["id"],"result":result}),flush=True)
'''
        (root / "peer.py").write_text(peer)
        (root / "settings.json").write_bytes(b"{}")
        (root / "prompt").write_text("synthetic self-test prompt")
        (root / "mcp.json").write_bytes(compact({"mcpServers": {"stewart": {"command": sys.executable,
            "args": ["-I", "-B", str(root / "peer.py")]}}}))
        executable = root / "synthetic-harness"
        executable.write_bytes(synthetic_executable(Path(__file__).resolve(), root / "scenario.json", root))
        executable.chmod(0o700)
        prefix = [str(executable)]
        auth = subprocess.run(prefix + ["auth", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env={"PATH": "/usr/bin:/bin"}, timeout=5)
        check("synthetic.auth", auth.returncode == 0 and json.loads(auth.stdout)["loggedIn"] is True)
        first = compact({"type": "user", "session_id": "", "parent_tool_use_id": None,
                         "message": {"role": "user", "content": "synthetic question"}}) + b"\n"
        model = subprocess.run(prefix + ["-p", "--settings", str(root / "settings.json"),
                               "--mcp-config", str(root / "mcp.json"), "--system-prompt-file", str(root / "prompt")],
                               input=first, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env={"PATH": "/usr/bin:/bin"}, timeout=10)
        events = [json.loads(line) for line in (root / "harness.jsonl").read_bytes().splitlines()]
        check("synthetic.model-intentional-exit", model.returncode == 7)
        check("synthetic.init", json.loads(model.stdout)["subtype"] == "init")
        sent = [e["value"] for e in events if e["event"] == "rpc-send"]
        check("synthetic.protocol-version", sent[0]["params"]["protocolVersion"] == "2025-11-25")
        check("synthetic.notification-has-no-id", sent[1]["method"] == "notifications/initialized" and "id" not in sent[1])
        check("synthetic.notification-does-not-wait", [e["method"] for e in sent[:3]] ==
              ["initialize", "notifications/initialized", "tools/list"])
        check("synthetic.notification-transmission-id", any(e["event"] == "rpc-transmitted"
              and e["method"] == "notifications/initialized" and e["id"] is None for e in events))
        check("synthetic.output-transmission", any(e["event"] == "output-transmitted"
              and e["sha256"] == sha(model.stdout) for e in events))
        check("synthetic.actual-record-call", any(e.get("params", {}).get("name") == "record_account"
              and e["params"]["arguments"] == {"text": ACCOUNT} for e in sent))
        check("synthetic.independent-input", any(e["event"] == "input" and e["raw_hex"] == first.hex() for e in events))
        for variant, response, expected_init in (
                ("signed-error", valid_error, True),
                ("malformed-error", malformed["fraction-code"], False),
                ("duplicate-error", malformed["duplicate-code"], False)):
            child_root = root / variant
            child_root.mkdir()
            child_scenario = dict(scenario, mode="bad-init", witness=str(child_root),
                                  marker=str(child_root / "started"), session=variant)
            (child_root / "scenario.json").write_bytes(compact(child_scenario))
            error_peer = '''import json,sys
for raw in sys.stdin.buffer:
    q=json.loads(raw)
    if "id" not in q: continue
    if q["method"]=="tools/call":
        sys.stdout.buffer.write(RESPONSE)
        sys.stdout.buffer.flush()
        continue
    result={"tools":[]} if q["method"]=="tools/list" else {"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"serverInfo":{"name":"self-test","version":"1"}}
    print(json.dumps({"jsonrpc":"2.0","id":q["id"],"result":result}),flush=True)
'''.replace("RESPONSE", repr(response + b"\n"))
            (child_root / "peer.py").write_text(error_peer)
            (child_root / "mcp.json").write_bytes(compact({"mcpServers": {"stewart": {
                "command": sys.executable, "args": ["-I", "-B", str(child_root / "peer.py")]}}}))
            executable = child_root / "synthetic-harness"
            executable.write_bytes(synthetic_executable(Path(__file__).resolve(), child_root / "scenario.json", child_root))
            executable.chmod(0o700)
            argv = [str(executable), "-p", "--settings", str(root / "settings.json"),
                    "--mcp-config", str(child_root / "mcp.json"), "--system-prompt-file", str(root / "prompt")]
            process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       env={"PATH": "/usr/bin:/bin"}, start_new_session=True)
            first_output = b""
            finished = False
            try:
                process.stdin.write(first)
                process.stdin.flush()
                # Keep stdin open: parser-error exits must stop their reader
                # without Python's daemon BufferedReader shutdown failure.
                if expected_init:
                    ready, _, _ = select.select([process.stdout], [], [], 5)
                    if ready:
                        first_output = process.stdout.readline()
                else:
                    try:
                        process.wait(timeout=5)
                        finished = True
                    except subprocess.TimeoutExpired:
                        pass
            finally:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=2)
                deadline = time.monotonic() + 2
                while group_observation(process.pid) == "present" and time.monotonic() < deadline:
                    time.sleep(0.01)
                if group_observation(process.pid) == "present":
                    os.killpg(process.pid, signal.SIGKILL)
                remaining, diagnostics = process.communicate(timeout=2)
            checker = Driver.__new__(Driver)
            checker.current, checker.checks = "synthetic-transport-regression", []
            f = {"label": variant, "witness": child_root, "archive": child_root / "archive",
                 "reference": "stw1:a-self-test:s-self-test:/synthetic"}
            try:
                observed = checker.harness_events(f)
            except ValueError:
                observed = []
                check("synthetic." + variant + ".witness-reader", False)
            else:
                check("synthetic." + variant + ".witness-reader", True)
            check("synthetic." + variant + ".raw-response-retained", any(e["event"] == "rpc-observed"
                  and e["raw_hex"] == (response + b"\n").hex() for e in observed))
            check("synthetic." + variant + ".clean-reader-shutdown", b"_enter_buffered_busy" not in diagnostics
                  and b"Fatal Python error" not in diagnostics)
            check("synthetic." + variant + ".bounded-group-cleanup", group_observation(process.pid) == "absent")
            if expected_init:
                check("synthetic.signed-error.decoded-and-witnessed", any(e["event"] == "rpc-receive"
                      and e["value"].get("error", {}).get("code") == -32000 for e in observed))
                try:
                    invalid = json.loads(first_output + remaining)
                except ValueError:
                    invalid = {}
                check("synthetic.signed-error.reaches-invalid-init", invalid.get("model") == "deliberately-wrong-model")
                # Specification-derived chunks exercise the same exact-capture
                # assertion, including numeric order and other-channel invariance.
                raw_init = first_output + remaining
                capture = checker.audit_path(f) / "runs" / "1"
                capture.mkdir(parents=True)
                cut = len(raw_init) // 2
                (capture / "runtime-2-stdout.bin").write_bytes(raw_init[:cut])
                (capture / "runtime-3-stderr.bin").write_bytes(b"unrelated channel")
                (capture / "runtime-10-stdout.bin").write_bytes(raw_init[cut:])
                try:
                    checker.check_invalid_init_witness(f, observed)
                except CaseStopped:
                    valid_witness = False
                else:
                    valid_witness = all(row["passed"] for row in checker.checks)
                check("synthetic.signed-error.actual-invalid-init-checks", valid_witness)
            else:
                check("synthetic." + variant + ".firing-control", finished and process.returncode == 8
                      and any(e["event"] == "fatal" for e in observed)
                      and not any(e["event"] == "output-transmitted" for e in observed))
    for name, ok in checks:
        if not ok:
            print("FAIL " + name)
    print("Self-test: %d passed, %d failed, 0 skipped" % (sum(ok for _, ok in checks), sum(not ok for _, ok in checks)))
    return int(any(not ok for _, ok in checks))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--synthetic-harness":
        if len(sys.argv) < 5 or sys.argv[3] != "--environment-witness":
            raise ValueError("synthetic harness requires its pre-Python environment witness")
        return synthetic_harness(sys.argv[2], sys.argv[4], sys.argv[5:])
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true", help="check the independent helpers without a binary")
    parser.add_argument("--list", action="store_true", help="list the standalone offline cases")
    parser.add_argument("--case", action="append", choices=[name for name, _ in CASES],
                        help="run only a named case; repeat to select several (default: all)")
    parser.add_argument("--binary", type=Path, help="absolute path to the claude-code development binary")
    parser.add_argument("--release-binary", type=Path, help="optional absolute featureless binary for rejection controls")
    parser.add_argument("--variant-binary", type=Path,
                        help="optional absolute second claude-code build with a different digest, for writer invariance")
    parser.add_argument("--work", type=Path, help="fresh physical absolute directory outside the driver repository; all evidence is retained")
    args = parser.parse_args()
    if args.list:
        for name, description in CASES:
            print("%s: %s" % (name, description))
        return 0
    if args.self_test:
        return self_test()
    if args.binary is None or args.work is None:
        parser.error("--binary and --work are required unless --self-test or --list is selected")
    for label, path in (("--binary", args.binary), ("--work", args.work), ("--release-binary", args.release_binary),
                        ("--variant-binary", args.variant_binary)):
        if path is not None and not path.is_absolute():
            parser.error(label + " must be absolute")
    if args.work.exists():
        parser.error("--work already exists; preserve that evidence and choose a fresh path")
    for path in (args.binary, args.release_binary, args.variant_binary):
        if path is not None and (not path.is_file() or not os.access(path, os.X_OK)):
            parser.error("binary must be an executable regular file: " + str(path))
    try:
        platform_name()
        return Driver(args.binary, args.work, args.release_binary, args.case, args.variant_binary).run()
    except (OSError, ValueError) as exc:
        print("Driver setup failed: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
