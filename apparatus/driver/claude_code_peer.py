#!/usr/bin/env python3
"""Synthetic CLI peer for the bounded surface-check rehearsal; never Claude.

Only a validated gated Stewart binary's relay and hook helpers may be launched.
The independent controller owns the process group, authority and outer deadline.
Run with python3 -I -B. See CLAUDE-CODE-PEER.md.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import claude_code as spec
import claude_code_surface as surface
from rawjson import compact

VERSION = "synthetic-surface-check"
SCENARIOS = ("normal", "bad-init", "wrong-auth")
MAX_BYTES = 8 * 1024 * 1024
MODEL_SECONDS = 15
MAX_CAPTURE = 32 * 1024 * 1024
PLUGINS = [{"name": name, "path": "builtin", "source": name + "@builtin"} for name in (
    "cc-plugin-agents-md", "cc-plugin-privacy", "cc-plugin-plugin-authoring")]
SOURCE_NAMES = ("claude_code_peer.py", "claude_code_surface.py", "claude_code.py", "driver_core.py", "rawjson.py")


class Journal(surface.Journal):
    def __init__(self, root):
        super().__init__(root)
        self.written = 0

    def append(self, name, raw):
        if self.written + len(raw) > MAX_CAPTURE:
            raise ValueError("peer capture bound exceeded; retained interval is incomplete")
        super().append(name, raw)
        self.written += len(raw)


def now():
    return time.clock_gettime(surface.CLOCK_ID)


def case_key(cwd):
    return hashlib.sha256(os.fsencode(str(cwd))).hexdigest()


def regular_bytes(path, limit=MAX_BYTES):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError("expected a bounded regular file: " + str(path))
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("file exceeded its byte bound: " + str(path))
    return raw


def validate_environment(raw):
    initial = spec.environment_snapshot(raw)
    env = {name: value for name, value in initial.items() if name not in spec.WRAPPER_ENVIRONMENT}
    for name in ("HOME", "TMPDIR", "CLAUDE_CONFIG_DIR"):
        if not isinstance(env.get(name), str) or not Path(env[name]).is_absolute():
            raise ValueError("initial environment lacks an absolute " + name)
    launch = {"home": env["HOME"], "temporary_directory": env["TMPDIR"], "config_directory": env["CLAUDE_CONFIG_DIR"]}
    expected = spec.filled_launch("/unused", "/unused", launch, "open-inquiry", spec.MODEL)["environment"]
    if env != expected:
        raise ValueError("initial environment differs from the exact supplied surface")
    return env


def validate_surface(argv, cwd, env, files, writer_bytes):
    """Pure validation; writer_bytes is supplied by the caller, never executed here."""
    if argv == ["auth", "status"]:
        role, model = "auth", None
    else:
        role = "model"
        if argv.count("--model") != 1 or argv.index("--model") + 1 >= len(argv):
            raise ValueError("expected the complete pinned model argv or auth status")
        model = argv[argv.index("--model") + 1]
        if not model or "\0" in model:
            raise ValueError("model must be a nonempty string without NUL")
    families = [family for family in surface.FAMILIES if files["system.txt"] == (
        spec.RUNTIME_ORIENTATION + "\n\n" + spec.FAMILY_TEXT[family]).encode()]
    if len(families) != 1:
        raise ValueError("system prompt differs from the pinned family text")
    family = families[0]
    config = spec.transport_loads(files["mcp.json"])
    try:
        writer = config["mcpServers"]["stewart"]["command"]
    except (KeyError, TypeError):
        raise ValueError("MCP config has no pinned Stewart writer") from None
    if not isinstance(writer, str) or not Path(writer).is_absolute():
        raise ValueError("Stewart writer must be absolute")
    for marker in (b"Stewart development build: claude-code", b"__stewart-cc-relay", b"__stewart-cc-hook"):
        if marker not in writer_bytes:
            raise ValueError("writer is not the gated Stewart helper binary")
    launch = {"home": env["HOME"], "temporary_directory": env["TMPDIR"], "config_directory": env["CLAUDE_CONFIG_DIR"]}
    expected = spec.filled_launch(writer, str(cwd), launch, family, model or spec.MODEL)
    if config != expected["mcp_config"] or spec.transport_loads(files["settings.json"]) != expected["settings"]:
        raise ValueError("settings or MCP config differ from the exact helper arrangement")
    if role == "model" and argv != expected["model_argv"]:
        raise ValueError("model argv differs from the complete supplied surface")
    return {"role": role, "model": model, "family": family, "writer": writer,
            "writer_sha256": spec.sha(writer_bytes), "cwd": str(cwd), "environment": env,
            "tools": json.loads(spec.mcp_tools(compact(spec.expected_tools(family)))),
            "session_id": "synthetic-surface-" + case_key(cwd), "version": VERSION}


def first_input():
    value = spec.surface_document()["input"]
    value["message"]["content"] = surface.QUESTION
    return compact(value) + b"\n"


def auth_receipt(context, scenario):
    return {"loggedIn": True, "authMethod": "api-key" if scenario == "wrong-auth" else "claude.ai",
            "configDirectory": context["environment"]["CLAUDE_CONFIG_DIR"]}


def init_event(context, scenario):
    return {"type": "system", "subtype": "init", "session_id": context["session_id"],
            "claude_code_version": VERSION, "model": context["model"],
            "apiKeySource": "environment" if scenario == "bad-init" else "none", "permissionMode": "dontAsk",
            "tools": ["mcp__stewart__" + item["name"] for item in context["tools"]],
            "mcp_servers": [{"name": "stewart", "status": "connected"}], "plugins": copy.deepcopy(PLUGINS),
            "plugin_errors": [], "mcp_server_errors": []}


def read_input(fd, journal, deadline):
    raw = bytearray()
    os.set_blocking(fd, False)
    while True:
        if now() >= deadline:
            raise TimeoutError("model input did not reach EOF before the peer deadline")
        readable, _, _ = select.select([fd], [], [], min(0.05, max(0, deadline - now())))
        if not readable:
            continue
        journal.event("before-model-input-read")
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError:
            continue
        journal.event("after-model-input-read", bytes=len(chunk))
        if not chunk:
            break
        journal.append("model-input-received.bin", chunk)
        raw.extend(chunk)
        if len(raw) > MAX_BYTES:
            raise ValueError("model input exceeded its byte bound")
    return bytes(raw)


def wait_startup_ack(path, session, journal, deadline):
    journal.event("synthetic-coordination-wait", path=str(path), scope="rehearsal scheduling only")
    while True:
        if now() >= deadline:
            raise TimeoutError("synthetic startup acknowledgement was not observed")
        if path.exists():
            break
        time.sleep(min(0.01, max(0, deadline - now())))
    raw = regular_bytes(path, 4096)
    journal.append("startup-observed-received.bin", raw)
    if spec.transport_loads(raw) != {"session_id": session}:
        raise ValueError("synthetic startup acknowledgement differs from this session")
    journal.event("synthetic-coordination-observed", scope="not a real-harness barrier or enforcement observation")


def helper_argv(context, name):
    if name not in {"relay", "hook"}:
        raise ValueError("unknown helper")
    return [context["writer"], "__stewart-cc-" + name, "m" if name == "relay" else "h"]


def mcp_reply(raw, number):
    if not raw.endswith(b"\n") or b"\n" in raw[:-1] or len(raw) > MAX_BYTES:
        raise ValueError("MCP reply is not one bounded complete frame")
    value = spec.mcp_message_loads(raw)
    if value.get("id") != number or type(value.get("id")) is not type(number) or "result" not in value or "error" in value:
        raise ValueError("helper reply is not the expected successful response")
    return value["result"]


def hook_allowed(raw):
    if not raw.endswith(b"\n") or b"\n" in raw[:-1] or len(raw) > 64 * 1024:
        raise ValueError("hook reply is not one bounded complete LF-terminated frame")
    decision = spec.transport_loads(raw)
    choices = spec.surface_document()["hook_replies"]
    if decision not in (choices["allow"], choices["deny"]):
        raise ValueError("hook reply differs from both pinned decisions")
    return decision == choices["allow"]


class Helper:
    """Exact helper argv, inherited group, bounded ordinary pipe polling.

    Nonblocking mode handles readiness races; the controller's independent
    watchdog must still bound a blocked Popen, kernel read or cleanup operation.
    """
    def __init__(self, context, name, journal, deadline):
        argv = helper_argv(context, name)
        self.name, self.journal, self.deadline = name, journal, deadline
        self.pending, self.eof = bytearray(), set()
        writer = Path(context["writer"])
        if spec.sha(regular_bytes(writer, 512 * 1024 * 1024)) != context["writer_sha256"]:
            raise ValueError("writer bytes changed before helper start")
        journal.event("before-helper-start", helper=name, argv=argv, process_group=os.getpgrp())
        self.process = subprocess.Popen(argv, cwd=context["cwd"], env=context["environment"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, close_fds=True)
        try:
            group = os.getpgid(self.process.pid)
            journal.event("after-helper-start", helper=name, pid=self.process.pid, process_group=group)
            if group != os.getpgrp():
                raise ValueError("helper did not inherit the peer's process group")
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                os.set_blocking(stream.fileno(), False)
        except BaseException:
            self.stop()
            raise

    def pump(self, writable=False):
        remaining = self.deadline - now()
        if remaining <= 0:
            raise TimeoutError(self.name + " helper exceeded the peer deadline")
        channels = {stream.fileno(): name for name, stream in (
            ("stdout", self.process.stdout), ("stderr", self.process.stderr)) if name not in self.eof}
        output = [self.process.stdin.fileno()] if writable else []
        self.journal.event("before-helper-select", helper=self.name)
        ready, writes, _ = select.select(list(channels), output, [], min(0.05, remaining))
        self.journal.event("after-helper-select", helper=self.name, readable=ready, writable=writes)
        for fd in ready:
            channel = channels[fd]
            self.journal.event("before-helper-read", helper=self.name, channel=channel)
            try:
                chunk = os.read(fd, 65536)
            except BlockingIOError:
                continue
            self.journal.event("after-helper-read", helper=self.name, channel=channel, bytes=len(chunk))
            if not chunk:
                self.eof.add(channel)
            else:
                self.journal.append(self.name + "-" + channel + "-received.bin", chunk)
                if channel == "stdout":
                    self.pending.extend(chunk)
                    if len(self.pending) > MAX_BYTES:
                        raise ValueError("helper reply exceeded its byte bound")
        return bool(writes)

    def send(self, raw):
        self.journal.append(self.name + "-stdin-supplied.bin", raw)
        offset = 0
        while offset < len(raw):
            if not self.pump(writable=True):
                continue
            try:
                count = os.write(self.process.stdin.fileno(), raw[offset:])
            except BlockingIOError:
                continue
            if count <= 0:
                raise OSError("helper input write made no progress")
            self.journal.append(self.name + "-stdin-sent.bin", raw[offset:offset + count])
            offset += count

    def reply(self, number):
        while b"\n" not in self.pending:
            if "stdout" in self.eof:
                raise ValueError("helper reply ended before its complete frame")
            self.pump()
        raw, _, rest = bytes(self.pending).partition(b"\n")
        self.pending[:] = rest
        return mcp_reply(raw + b"\n", number)

    def finish(self):
        self.process.stdin.close()
        while len(self.eof) != 2:
            self.pump()
        status = self.process.wait(timeout=max(0.001, self.deadline - now()))
        self.journal.event("helper-exit-observed", helper=self.name, pid=self.process.pid, exit=status)
        if status != 0:
            raise ValueError(self.name + " helper exited unsuccessfully")
        raw = bytes(self.pending)
        self.pending.clear()
        return raw

    def stop(self):
        process = self.process
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=0.5)
            self.journal.event("helper-reaped", helper=self.name, pid=process.pid, exit=process.returncode)
        except (OSError, subprocess.TimeoutExpired) as error:
            self.journal.event("helper-stopping-unknown", helper=self.name, error=str(error))
            raise RuntimeError("helper stopping is unknown; controller must stop the owned group") from error
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


def run_model(context, scenario, journal, input_raw, emit, acknowledge, factory=Helper, deadline=None):
    if input_raw != first_input():
        raise ValueError("model input differs from the exact single synthetic question frame")
    deadline = now() + MODEL_SECONDS if deadline is None else deadline
    if now() >= deadline:
        raise TimeoutError("model input exhausted the peer deadline")
    helpers = []
    try:
        relay = factory(context, "relay", journal, deadline)
        helpers.append(relay)

        def request(number, method, params=None):
            message = {"jsonrpc": "2.0", "method": method}
            if number is not None:
                message["id"] = number
            if params is not None:
                message["params"] = params
            relay.send(compact(message) + b"\n")
            return relay.reply(number) if number is not None else None

        result = request(1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "synthetic-surface-check", "version": "1"}})
        if result != spec.surface_document()["mcp_initialize"]:
            raise ValueError("MCP initialization differs from the pinned response")
        request(None, "notifications/initialized")
        if request(2, "tools/list") != {"tools": context["tools"]}:
            raise ValueError("MCP tools/list differs from the full pinned family inventory")
        emit(init_event(context, scenario))
        acknowledge(context["session_id"], deadline)
        tool_id = "toolu-synthetic-surface"
        emit({"type": "assistant", "session_id": context["session_id"], "message": {"model": context["model"],
            "content": [{"type": "tool_use", "id": tool_id, "name": "mcp__stewart__record_account",
                         "input": {"text": surface.MARKER}}]}})
        hook = factory(context, "hook", journal, deadline)
        helpers.append(hook)
        hook.send(compact({"hook_event_name": "PreToolUse", "session_id": context["session_id"],
            "tool_use_id": tool_id, "tool_name": "mcp__stewart__record_account",
            "tool_input": {"text": surface.MARKER}}) + b"\n")
        reply = hook.finish()
        allowed = hook_allowed(reply)
        if allowed:
            result = request(3, "tools/call", {"name": "record_account", "arguments": {"text": surface.MARKER}})
            expected = {"content": [{"type": "text", "text": json.dumps({"outcome": "completed", "data": {"fixture_effect": True}})}]}
            if result != expected:
                raise ValueError("tool reply did not report the specified synthetic fixture effect")
        journal.event("synthetic-attempt-completed", hook_allowed=allowed, mcp_call_sent=allowed,
                      scope="peer-observed reply; independent fixture owns effect evidence")
        if relay.finish():
            raise ValueError("unexpected or partial trailing MCP reply")
        emit({"type": "result", "session_id": context["session_id"], "is_error": False, "num_turns": 1,
            "usage": {name: 1 for name in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")}})
        return {"hook_allowed": allowed, "mcp_call_sent": allowed, "helpers_exited": True}
    finally:
        errors = []
        for helper in reversed(helpers):
            try:
                helper.stop()
            except (OSError, RuntimeError) as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError("; ".join(errors))


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--self-test", action="store_true", help="pure offline validation and mocked-helper controls; launches nothing")
    parser.add_argument("--witness-root", type=Path, help="absolute controller-owned synthetic witness directory")
    parser.add_argument("--environment-witness", type=Path, help="unique pre-Python /usr/bin/env -0 snapshot under witness root")
    parser.add_argument("--scenario", choices=SCENARIOS)
    if "--" in argv:
        split = argv.index("--")
        options, forwarded = argv[:split], argv[split + 1:]
    else:
        options, forwarded = argv, []
    args = parser.parse_args(options)
    for option in ("--self-test", "--witness-root", "--environment-witness", "--scenario"):
        if sum(item == option or item.startswith(option + "=") for item in options) > 1:
            parser.error("repeated option: " + option)
    if args.self_test:
        if forwarded or len(options) != 1:
            parser.error("--self-test is used alone")
    else:
        for name in ("witness_root", "environment_witness"):
            if getattr(args, name) is None or not getattr(args, name).is_absolute():
                parser.error("--" + name.replace("_", "-") + " must be absolute")
        if args.scenario is None or not forwarded:
            parser.error("--scenario and argv after -- are required")
    return args, forwarded


def execute(args, argv):
    cwd = Path.cwd().resolve()
    root = args.witness_root.resolve(strict=True)
    if args.witness_root.is_symlink() or not root.is_dir() or cwd.is_relative_to(root) or cwd.is_relative_to(HERE.parent.parent):
        raise ValueError("witness root and workspace must be separate directories outside project ancestry")
    env_path = args.environment_witness
    if env_path.parent.resolve() != root:
        raise ValueError("environment witness must be a direct member of the witness root")
    raw_env = regular_bytes(env_path, 1024 * 1024)
    role = "auth" if argv == ["auth", "status"] else "model"
    case_root = root / case_key(cwd)
    case_root.mkdir(mode=0o700, exist_ok=True)
    if case_root.is_symlink():
        raise ValueError("case witness directory must not be a link")
    evidence = case_root / role
    evidence.mkdir(mode=0o700)
    journal = Journal(evidence)
    try:
        journal.event("peer-started", mode="synthetic-rehearsal", role=role, scenario=args.scenario)
        surface.save(evidence / "invocation.json", {"argv": argv, "cwd": str(cwd), "case_key": case_key(cwd),
            "interpreted_environment": dict(os.environ), "environment_scope": "snapshot after shell startup, before Python",
            "wrapper_environment_names": sorted(spec.WRAPPER_ENVIRONMENT),
            "environment_witness": str(env_path), "process_group": os.getpgrp(), "peer_pid": os.getpid(),
            "scenario": args.scenario, "mode": "synthetic-rehearsal"})
        journal.append("environment-initial.bin", raw_env)
        surface.save(evidence / "environment-initial.json", spec.environment_snapshot(raw_env))
        source = evidence / "sources"
        source.mkdir()
        for name in SOURCE_NAMES:
            (source / name).write_bytes((HERE / name).read_bytes())
        env = validate_environment(raw_env)
        files = {name: regular_bytes(cwd / name) for name in ("settings.json", "mcp.json", "system.txt")}
        supplied = evidence / "supplied"
        supplied.mkdir()
        for name, raw in files.items():
            (supplied / name).write_bytes(raw)
        config = spec.transport_loads(files["mcp.json"])
        try:
            writer = Path(config["mcpServers"]["stewart"]["command"])
        except (KeyError, TypeError):
            raise ValueError("MCP config does not name the Stewart writer") from None
        if not writer.is_absolute():
            raise ValueError("writer must be absolute")
        context = validate_surface(argv, cwd, env, files, regular_bytes(writer, 512 * 1024 * 1024))
        surface.save(evidence / "validated.json", context)
        if role == "auth":
            # No raw authentication stdout is copied, hashed or journaled here.
            raw = compact(auth_receipt(context, args.scenario)) + b"\n"
            sys.stdout.buffer.write(raw)
            sys.stdout.buffer.flush()
            journal.event("synthetic-auth-finished", raw_auth_retained=False)
        else:
            deadline = now() + MODEL_SECONDS
            raw_input = read_input(sys.stdin.fileno(), journal, deadline)

            def emit(value):
                raw = compact(value) + b"\n"
                journal.append("model-stdout-supplied.bin", raw)
                sys.stdout.buffer.write(raw)
                sys.stdout.buffer.flush()
                journal.append("model-stdout-sent.bin", raw)

            result = run_model(context, args.scenario, journal, raw_input, emit,
                lambda session, end: wait_startup_ack(case_root / "startup-observed.json", session, journal, end), deadline=deadline)
            surface.save(evidence / "RESULT.json", {"mode": "synthetic-rehearsal", **result})
        journal.event("peer-completed", role=role)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        surface.save(evidence / "FAILURE.json", {"error": str(error), "mode": "synthetic-rehearsal"})
        print("Synthetic peer failed: %s; evidence retained at %s" % (error, evidence), file=sys.stderr)
        return 1


def self_test():
    """No subprocess, socket listener, credential or ambient environment access."""
    root = Path(tempfile.mkdtemp(prefix="stewart-peer-selftest-")).resolve()
    checks = []

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})

    def refuses(name, call):
        try:
            call()
        except (ValueError, OSError, SystemExit):
            check(name, True)
        else:
            check(name, False)

    cwd = Path("/synthetic/workspace")
    writer = "/synthetic/gated-stewart"
    binary = b"Stewart development build: claude-code __stewart-cc-relay __stewart-cc-hook"
    launch = {"home": "/synthetic/home", "temporary_directory": "/synthetic/tmp", "config_directory": "/synthetic/config"}
    expected = spec.filled_launch(writer, str(cwd), launch, "open-inquiry", spec.MODEL)
    env = expected["environment"]
    env_raw = b"".join((name + "=" + value).encode() + b"\0" for name, value in env.items())
    files = {"settings.json": compact(expected["settings"]), "mcp.json": compact(expected["mcp_config"]),
             "system.txt": (spec.RUNTIME_ORIENTATION + "\n\n" + spec.FAMILY_TEXT["open-inquiry"]).encode()}
    argv = expected["model_argv"]
    context = validate_surface(argv, cwd, validate_environment(env_raw), files, binary)
    check("exact-environment", validate_environment(env_raw) == env)
    check("environment-order-invariance", validate_environment(b"\0".join(env_raw[:-1].split(b"\0")[::-1]) + b"\0") == env)
    wrapper_names = {"PWD", "OLDPWD", "SHLVL", "_", "__CF_USER_TEXT_ENCODING"}
    check("named-wrapper-scope", spec.WRAPPER_ENVIRONMENT == wrapper_names)
    wrapper_raw = b"".join((name + "=synthetic-shell-value").encode() + b"\0" for name in sorted(wrapper_names))
    check("shell-added-names", validate_environment(env_raw + wrapper_raw) == env)
    check("shell-added-values-invariance", validate_environment(wrapper_raw.replace(b"synthetic-shell-value", b"different") + env_raw) == env)
    for name in sorted(wrapper_names):
        check("shell-added-" + name, validate_environment(env_raw + (name + "=synthetic").encode() + b"\0") == env)
    for name, raw in (("extra-locale", env_raw + b"LC_CTYPE=C.UTF-8\0"), ("extra-variable", env_raw + b"EXTRA=1\0"),
                      ("changed-lang", env_raw.replace(b"LANG=en_US.UTF-8", b"LANG=C")),
                      ("duplicate", env_raw + b"LANG=en_US.UTF-8\0"), ("truncated", env_raw[:-1])):
        refuses("environment-" + name, lambda raw=raw: validate_environment(raw))
    for name, raw in (("locale", env_raw + b"LC_CTYPE=C.UTF-8\0"), ("extra", env_raw + b"EXTRA=1\0"),
                      ("lang", env_raw.replace(b"LANG=en_US.UTF-8", b"LANG=C"))):
        refuses("wrapper-does-not-excuse-" + name, lambda raw=raw: validate_environment(wrapper_raw + raw))
    check("full-argv", context["role"] == "model" and context["family"] == "open-inquiry")
    check("auth-argv", validate_surface(["auth", "status"], cwd, env, files, binary)["role"] == "auth")
    for name, changed in (("extra-flag", argv + ["--resume"]), ("missing-flag", argv[:-1]),
                          ("wrong-helper-command", ["auth", "login"]), ("repeated-model", argv + ["--model", spec.MODEL])):
        refuses("argv-" + name, lambda changed=changed: validate_surface(changed, cwd, env, files, binary))
    for name, member, raw in (("system", "system.txt", b"different"), ("settings", "settings.json", b"{}"),
                             ("config", "mcp.json", b"{}"), ("duplicate", "settings.json", b'{"hooks":{},"hooks":{}}')):
        changed = {**files, member: raw}
        refuses("supplied-" + name, lambda changed=changed: validate_surface(argv, cwd, env, changed, binary))
    for name, field, replacement in (("arbitrary-command", "command", "/bin/sh"), ("arbitrary-args", "args", ["-c", "echo no"])):
        config = copy.deepcopy(expected["mcp_config"])
        config["mcpServers"]["stewart"][field] = replacement
        changed = {**files, "mcp.json": compact(config)}
        refuses(name, lambda changed=changed: validate_surface(argv, cwd, env, changed, binary))
    refuses("ungated-writer", lambda: validate_surface(argv, cwd, env, files, b"not a gated binary"))
    check("auth-allowlist", set(auth_receipt(context, "normal")) == {"loggedIn", "authMethod", "configDirectory"})
    check("auth-negative", auth_receipt(context, "wrong-auth")["authMethod"] == "api-key")
    check("startup-negative", init_event(context, "bad-init")["apiKeySource"] != "none")
    check("case-isolation", case_key(cwd) != case_key(Path("/synthetic/other")))
    check("exact-helper-argv", helper_argv(context, "relay") == [writer, "__stewart-cc-relay", "m"]
          and helper_argv(context, "hook") == [writer, "__stewart-cc-hook", "h"])
    refuses("arbitrary-helper", lambda: helper_argv(context, "shell"))
    good_reply = b'{"jsonrpc":"2.0","id":1,"result":{}}\n'
    check("mcp-complete-reply", mcp_reply(good_reply, 1) == {})
    for name, raw in (("partial", good_reply[:-1]), ("two-frames", good_reply + good_reply),
                      ("wrong-id", good_reply.replace(b'"id":1', b'"id":2')),
                      ("id-type", good_reply.replace(b'"id":1', b'"id":"1"')),
                      ("error", b'{"jsonrpc":"2.0","id":1,"error":{"code":-32000,"message":"refused"}}\n'),
                      ("duplicate", b'{"jsonrpc":"2.0","id":1,"id":1,"result":{}}\n')):
        refuses("mcp-" + name, lambda raw=raw: mcp_reply(raw, 1))
    check("hook-allow", hook_allowed(b'{}\n'))
    check("hook-deny", not hook_allowed(compact(spec.surface_document()["hook_replies"]["deny"]) + b"\n"))
    for name, raw in (("partial", b'{}'), ("two-frames", b'{}\n{}\n'), ("wrong-shape", b'[]\n'),
                      ("different-decision", b'{"allow":true}\n')):
        refuses("hook-" + name, lambda raw=raw: hook_allowed(raw))
    with patch("sys.stderr", new=io.StringIO()):
        for name, options in (("unknown", ["--unknown"]), ("abbreviated", ["--self-t"]),
                              ("repeated", ["--self-test", "--self-test"]), ("mixed", ["--self-test", "--", "auth", "status"])):
            refuses("parser-" + name, lambda options=options: parse_arguments(options))
    check("parser-selftest", parse_arguments(["--self-test"])[0].self_test)
    args, forwarded = parse_arguments(["--witness-root", "/w", "--environment-witness", "/w/env.X", "--scenario", "normal", "--", "auth", "status"])
    check("parser-forwarding", forwarded == ["auth", "status"] and args.scenario == "normal")

    # Mock transports exercise both decisions and the exact protocol sequence.
    # Their provenance is deliberately distinct from actual helper execution.
    class MockHelper:
        def __init__(self, ctx, name, journal, deadline):
            self.name, self.journal, self.pending = name, journal, []
            self.raw = b""
            calls.append(name)

        def send(self, raw):
            self.raw += raw
            self.journal.append(self.name + "-mock-supplied.bin", raw)
            if self.name == "relay":
                reply = fixture.mcp(raw)
                if reply is not None:
                    self.pending.append(reply)

        def reply(self, number):
            value = spec.mcp_message_loads(self.pending.pop(0))
            if value.get("id") != number or "result" not in value:
                raise ValueError("mock protocol failure")
            return value["result"]

        def finish(self):
            return fixture.hook(self.raw) if self.name == "hook" else b""

        def stop(self):
            stopped.append(self.name)

    with patch.object(subprocess, "Popen", side_effect=AssertionError("self-test must not launch a subprocess")):
        for name, allow in (("positive", True), ("denial", False), ("invariance", True)):
            work = root / name
            work.mkdir()
            journal = Journal(work)
            fixture = surface.Fixture(compact(context["tools"]), journal)
            fixture.active = allow
            calls, stopped, emitted = [], [], []
            result = run_model(context, "normal", journal, first_input(), emitted.append,
                lambda session, end: check(name + "-ack-session", session == context["session_id"]), factory=MockHelper)
            check(name + "-effect-contrast", fixture.effects == ([{"text": surface.MARKER}] if allow else [])
                  and result["mcp_call_sent"] == allow)
            check(name + "-complete-transcript", len(emitted) == 3 and emitted[0] == init_event(context, "normal")
                  and emitted[-1]["type"] == "result" and calls == ["relay", "hook"] and stopped == ["hook", "relay"])
        refuses("partial-input", lambda: run_model(context, "normal", journal, first_input()[:-1], emitted.append,
            lambda *args: None, factory=MockHelper))
        refuses("extra-input", lambda: run_model(context, "normal", journal, first_input() + first_input(), emitted.append,
            lambda *args: None, factory=MockHelper))
        refuses("input-exhausted-deadline", lambda: run_model(context, "normal", journal, first_input(), emitted.append,
            lambda *args: None, factory=MockHelper, deadline=now()))
        ack = root / "ack.json"
        surface.save(ack, {"session_id": context["session_id"]})
        wait_startup_ack(ack, context["session_id"], journal, now() + 0.1)
        check("synthetic-ack", True)
        refuses("wrong-ack", lambda: wait_startup_ack(ack, "different", journal, now() + 0.1))
        refuses("missing-ack-deadline", lambda: wait_startup_ack(root / "absent", "different", journal, now()))
        witness_root = root / "witness-failure"
        witness_root.mkdir()
        failing = Journal(witness_root)
        (witness_root / "unwritable.bin").mkdir()
        refuses("witness-write-failure", lambda: failing.append("unwritable.bin", b"observed bytes"))
        failing.written = MAX_CAPTURE
        refuses("capture-bound", lambda: failing.append("overflow.bin", b"x"))
    surface.save(root / "SELFTEST.json", {"mode": "synthetic-rehearsal", "helper_transport": "mocked", "checks": checks})
    (root / "claude_code_peer.py").write_bytes(Path(__file__).read_bytes())
    failed = sum(not item["passed"] for item in checks)
    print("Peer self-test: %d passed, %d failed, 0 skipped" % (len(checks) - failed, failed))
    print("No process or socket launched; evidence retained: " + str(root))
    return int(bool(failed))


def main():
    args, argv = parse_arguments(sys.argv[1:])
    return self_test() if args.self_test else execute(args, argv)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("Synthetic peer refused: " + str(error), file=sys.stderr)
        sys.exit(1)
