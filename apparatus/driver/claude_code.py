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
    "manager's question, exactly as they wrote it. Use only the commissioned "
    "question, captured materials and Stewart's MCP tools for this inquiry. "
    "Do not use shell, general file access, network retrieval, project execution "
    "or delegated auditors. Harness instructions and system messages are runtime "
    "context, not additional evidence. Reports, logs and test results in the "
    "materials are claims by their authors, not executions you witnessed."
)
RUNTIME_ORIENTATION = FIRST_PARAGRAPH + "\n\n" + ORIENTATION.split("\n\n", 1)[1]
NEAR_LIMIT = (
    "Allowance notice: {seconds} seconds remain before this placement's deadline, "
    "and {placements} further placement starts remain for this audit. When execution "
    "stops, an unsubmitted answer stays unsubmitted."
)
COMPACTED = (
    "The harness reports that it summarized earlier conversation. Continue this "
    "audit from your recorded work; call what_am_i_working_with before repeating "
    "an action."
)
TEXTS = {"reminder": REMINDER, "near_limit": NEAR_LIMIT,
         "continuation": CONTINUATION, "compacted": COMPACTED}
SIGNER = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE"
MODEL = "synthetic-offline-model"
CANARY = b'#!/bin/sh\nprintf "unexpected local launch\\n" > "$0.started"\nexit 97\n'
ACCOUNT = "The supplied report claims success. This synthetic auditor did not witness execution.\n"
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
# A shell wrapper and the interpreter's platform runtime add these to the
# synthetic harness's own environment; Stewart supplies none of them.
WRAPPER_ENVIRONMENT = {"PWD", "OLDPWD", "SHLVL", "_", "__CF_USER_TEXT_ENCODING"}
CASES = (
    ("families", "All three families: preparation, commission, exact readback and status"),
    ("binding-controls", "Change each launch/check binding; reject it; restore the valid control"),
    ("surface-binding", "A check naming another surface, or an earlier profile form, refuses with the exact surface"),
    ("surface-two-builds", "Optional second build: same profile accepted by both writers; audits stay with their writer"),
    ("profile-input", "Strict profile JSON, bounds, regular-file and no-follow controls"),
    ("limit-fields", "Placement bounds; API fields and runtime fields on question/1 refuse"),
    ("source-invariance", "Receipt stays captured after source/profile edits and CWD/HOME changes"),
    ("release-gate", "Optional featureless binary refuses the new version and runtime fields"),
    ("runtime-submit", "Actual MCP record/prepare/submit, faithful delivery and fresh-session invariance"),
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
        "texts": {"orientation": "stewart.orientation/claude-code/1",
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


def filled_launch(writer, workspace, launch, family, model):
    """Fill the surface placeholders for one launch of one family."""
    doc = surface_document()
    argv = []
    for arg in doc["model_argv"]:
        if arg == "mcp__stewart__{tool}":
            argv.extend("mcp__stewart__" + tool["name"] for tool in expected_tools(family))
        else:
            argv.append(arg.replace("{workspace}", workspace).replace("{model}", model))
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


def capture_failure_diagnostic(text):
    """A case name or custody path is not an operation failure diagnosis."""
    if not isinstance(text, str):
        return False
    text = re.sub(r"/[^\s\"']+", "<path>", text.lower())
    return bool(re.search(r"\b(capture|capturing|recorder|write|writing|archive_write_failed|capture_failed|raw_capture)\b", text)
                and any(word in text for word in ("fail", "denied", "permission", "error", "cannot", "could not")))


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
        error = value["error"]
        if not isinstance(error, dict) or type(error.get("code")) is not int:
            raise ValueError("MCP error code must be an integer")
        string(error.get("message"), "MCP error message")
    return value


class CaseStopped(Exception):
    pass


class Driver:
    def __init__(self, binary, work, release=None, selected=None, variant=None):
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
        self.current = None
        self.serial = 0
        self.archives = []
        self.canaries = []
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
                  "qualification": False, "scope": "native offline preparation and synthetic MCP runtime"})

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

    def control(self, name, fired):
        self.controls.append({"case": self.current, "name": name, "fired": bool(fired)})
        self.check(name + ".fired", fired, "deliberately invalid input was not refused")

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

    def fixture(self, label, family="open-inquiry", binary=None, scenario=None, timeout=600, placements=3):
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
                       "auth_private": "synthetic-auth-private-output-" + label}) + b"\n")
            (witness / "scenario-initial.json").write_bytes(scenario_path.read_bytes())
            command = [sys.executable, "-I", "-B", str(self.harness_script),
                       "--synthetic-harness", str(scenario_path)]
            executable.write_text("#!/bin/sh\nexec " + " ".join(shlex.quote(arg) for arg in command) + ' "$@"\n')
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
        fields = {"stewart": "question/claude-code/1", "family": family, "model": MODEL,
                  "destination": str(destination), "runtime-profile": str(profile_path),
                  "max-placements": str(placements), "placement-timeout-seconds": str(timeout)}
        (folder / "materials" / "report.txt").write_bytes(material)
        fixture = {"label": label, "root": root, "folder": folder, "archive": archive,
                   "reference": reference, "profile_path": profile_path, "profile": profile,
                   "family": family, "tools": tools, "fields": fields, "body": body,
                   "launch": launch,
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
                    "orientation": "stewart.orientation/claude-code/1",
                    "system_prompt": RUNTIME_ORIENTATION + "\n\n" + FAMILY_TEXT[f["family"]],
                    "runtime": {"kind": "claude-code/1", "profile_path": str(f["profile_path"]),
                                "profile": f["profile"].decode()},
                    "profile_sha256": sha(f["profile"]), "surface_sha256": SURFACE_SHA,
                    "effort": None,
                    "limits": f["limits"], "harness_max_turns": 200,
                    "harness_max_output_tokens": 16000, "texts": TEXTS}
        for key, value in expected.items():
            self.eq(label + "." + key, obj.get(key), value)
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
        run_needs = json.dumps(reply.get("data", {}).get("run_needs", []))
        self.check(f["label"] + ".no-api-credential-request",
                   "ANTHROPIC_API_KEY" not in run_needs and "--key-fd" not in run_needs, run_needs)
        receipt = self.cmd(f["label"] + ".receipt", ["receipt", f["reference"], "--verify"])
        self.eq(f["label"] + ".receipt-settings", receipt["data"].get("settings"), prepared["data"]["settings"])
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
        return receipt, status_reply, raw

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
            self.profile_refusal("binding." + section + "-" + key, reply)
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
        self.profile_refusal("binding.platform", reply)
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
            fields = dict(f["fields"])
            del fields[key]
            self.question(f, fields)
            reply = self.prepare(f, key + "-missing", "refused")
            self.control(key + "-missing", reply.get("outcome") == "refused")
        for key in ("limit-turns", "limit-input-tokens", "limit-output-tokens"):
            self.question(f, dict(f["fields"], **{key: "200"}))
            reply = self.prepare(f, key, "refused")
            self.control(key, reply.get("outcome") == "refused")
        fields = {key: value for key, value in f["fields"].items()
                  if key not in ("runtime-profile", "max-placements", "placement-timeout-seconds")}
        fields.update({"stewart": "question/1", "limit-turns": "200",
                       "limit-input-tokens": "20000000", "limit-output-tokens": "400000"})
        self.question(f, fields)
        self.prepare(f, "api-positive")
        for key in ("runtime-profile", "max-placements", "placement-timeout-seconds"):
            self.question(f, dict(fields, **{key: f["fields"][key]}))
            reply = self.prepare(f, key + "-on-api", "refused")
            self.control(key + "-on-api", reply.get("outcome") == "refused")
        self.question(f)
        self.prepare(f, "restored")

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
        reply = self.cmd("release-gate.version", ["prepare", f["reference"]], "refused", binary=self.release)
        self.control("featureless-version", reply.get("outcome") == "refused")
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

    def harness_events(self, f):
        path = f["witness"] / "harness.jsonl"
        return [transport_loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []

    def audit_path(self, f):
        return f["archive"] / "audits" / f["reference"].split(":")[1]

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
            expected = filled_launch(str(self.binary), workspace, f["launch"], f["family"], MODEL)
            self.eq(p + ".argv", argv, expected["model_argv"])
            env = event["environment"]
            self.eq(p + ".env.supplied", {key: env.get(key) for key in expected["environment"]},
                    expected["environment"])
            self.eq(p + ".env.nothing-else",
                    sorted(set(env) - set(expected["environment"]) - WRAPPER_ENVIRONMENT), [])
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
                self.eq(p + ".auth-env.supplied",
                        {key: auth["environment"].get(key) for key in expected["environment"]},
                        expected["environment"])
                self.eq(p + ".auth-env.nothing-else",
                        sorted(set(auth["environment"]) - set(expected["environment"]) - WRAPPER_ENVIRONMENT), [])
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

    def check_delivery(self, f, status_reply):
        data = status_reply["data"]
        self.eq(f["label"] + ".auditor-seal", data.get("seal", {}).get("actor"), "auditor")
        delivery = data.get("headline", {}).get("delivered", {})
        self.require(f["label"] + ".verified-delivery", delivery.get("verified") is True, delivery)
        package = Path(delivery["location"])
        expected = (b'{"schema":"stewart.answer/1","revision":1,"entries":[\n'
                    + compact({"id": "e1", "version": 1, "kind": "record_account", "label": "",
                               "text": ACCOUNT, "citations": []}) + b']}\n')
        (f["witness"] / "expected-answer.json").write_bytes(expected)
        self.eq(f["label"] + ".faithful-answer", (package / "answer.json").read_bytes().decode(), expected.decode())

    def runtime_submit(self):
        for label in ("runtime-positive", "runtime-fresh-invariance"):
            f = self.fixture(label, scenario="submit")
            self.accept(f)
            env = dict(self.env, DRIVER_INJECTION="must-not-forward", HTTPS_PROXY="http://127.0.0.1:1")
            self.cmd(label + ".run", ["run", f["reference"]], env=env)
            self.groups_absent(f)
            self.check_delivery(f, self.inspect_runtime(f))

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
        reply = self.cmd(f["label"] + ".key-fd", ["run", f["reference"], "--key-fd", "0"],
                         outcome="refused", input_bytes=b"synthetic-not-a-credential\n")
        self.eq(f["label"] + ".not-launched", marker.exists(), False)
        self.control("api-credential-option", reply.get("outcome") == "refused" and not marker.exists())

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
            reply = self.cmd(f["label"] + ".blocked-restart", ["run", f["reference"]], outcome="refused")
            self.eq(f["label"] + ".no-start-after-unknown-stop", marker.read_bytes(), before)
            self.eq(f["label"] + ".recovery-did-not-signal", unrelated.poll(), None)
            self.control("unknown-stop-blocks-restart", reply.get("outcome") == "refused" and marker.read_bytes() == before)
            closed = self.cmd(f["label"] + ".blocked-close", ["close", f["reference"]], outcome=None)
            self.check(f["label"] + ".close-unfinished", closed.get("effects", {}).get("closure") != "complete", closed)
            self.eq(f["label"] + ".close-did-not-signal", unrelated.poll(), None)
            self.control("unknown-stop-blocks-close", closed.get("effects", {}).get("closure") != "complete")
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
        report = {"schema": "stewart.claude-code.offline-driver/1", "qualification": False,
                  "scope": "native offline preparation and synthetic MCP runtime; no Claude or provider invocation",
                  "elapsed_seconds": time.monotonic() - self.started,
                  "cases": self.cases, "checks": self.checks, "controls": self.controls,
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
        print("Development evidence only; retained work: %s" % self.work, flush=True)
        return 1 if report["counts"]["failed"] else 0


def synthetic_harness(scenario_path, argv):
    """Synthetic executable only: no provider or real harness is ever invoked."""
    scenario = strict_loads(Path(scenario_path).read_bytes())
    witness = Path(scenario["witness"])
    event_lock = threading.Lock()

    def event(kind, **data):
        with event_lock:
            with open(witness / "harness.jsonl", "ab") as stream:
                stream.write(compact({"event": kind, "pid": os.getpid(), "monotonic_ns": time.monotonic_ns(), **data}) + b"\n")

    with open(scenario["marker"], "ab") as stream:
        stream.write(compact(argv) + b"\n")
    role = "auth" if argv == ["auth", "status"] else "model"
    launch = {"role": role, "argv": argv, "environment": dict(os.environ), "cwd": os.getcwd()}
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
        if scenario["mode"] not in ("bad-init", "delayed-valid-init"):
            emit(init)
        server = config["mcpServers"]["stewart"]
        mcp = subprocess.Popen([server["command"]] + server["args"], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=open(witness / (scenario["session"] + "-mcp.stderr"), "wb"),
                               env=os.environ.copy())
        sequence = 0

        def send(method, params=None, notification=False):
            nonlocal sequence
            value = {"jsonrpc": "2.0", "method": method}
            if not notification:
                sequence += 1
                value["id"] = sequence
            if params is not None:
                value["params"] = params
            raw = compact(value) + b"\n"
            event("rpc-send", value=value, raw_hex=raw.hex())
            transmit(mcp.stdin, raw, "rpc-transmitted", id=value.get("id"), method=method)
            return sequence

        def receive(identity, timeout=8):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                ready, _, _ = select.select([mcp.stdout], [], [], max(0, deadline - time.monotonic()))
                if not ready:
                    break
                raw = mcp.stdout.readline()
                if not raw:
                    raise RuntimeError("MCP server ended before reply")
                event("rpc-observed", raw_hex=raw.hex())
                value = mcp_message_loads(raw)
                event("rpc-receive", value=value, raw_hex=raw.hex())
                if value.get("id") == identity:
                    return value
            raise TimeoutError("no MCP reply for id %s" % identity)

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
        prepared = tool("prepare", {})
        if prepared.get("outcome") != "completed":
            raise RuntimeError("prepare did not complete: %r" % prepared)
        # Submission's recorded core reply is deliberately not awaited: the
        # common contract stops the placement without transmitting that reply.
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
    valid_error = b'{"jsonrpc":"2.0","id":3,"error":{"code":-32000,"message":"startup pending"}}'
    check("mcp.signed-error", mcp_message_loads(valid_error)["error"]["code"] == -32000)
    check("mcp.signed-id", mcp_message_loads(b'{"jsonrpc":"2.0","id":-1,"result":{}}')["id"] == -1)
    check("mcp.unknown-id-error", "id" not in mcp_message_loads(b'{"jsonrpc":"2.0","error":{"code":-32700,"message":"parse error"}}'))
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
        for source, target in zip(parse(base).items, parse(mapped).items):
            check(family + ".schema." + source.get("name").value(),
                  source.get("input_schema").raw == target.get("inputSchema").raw)
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
    check("recorder-diagnostic.path-invariance", capture_failure_diagnostic("write capture failed: Permission denied /unrelated/path"))
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
        prefix = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--synthetic-harness", str(root / "scenario.json")]
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
            argv = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--synthetic-harness",
                    str(child_root / "scenario.json"), "-p", "--settings", str(root / "settings.json"),
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
        return synthetic_harness(sys.argv[2], sys.argv[3:])
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true", help="check the independent helpers without a binary")
    parser.add_argument("--list", action="store_true", help="list the standalone offline cases")
    parser.add_argument("--case", action="append", choices=[name for name, _ in CASES],
                        help="run only a named case; repeat to select several (default: all)")
    parser.add_argument("--binary", type=Path, help="absolute path to the claude-code development binary")
    parser.add_argument("--release-binary", type=Path, help="optional absolute featureless binary for rejection controls")
    parser.add_argument("--variant-binary", type=Path,
                        help="optional absolute second claude-code build with a different digest, for writer invariance")
    parser.add_argument("--work", type=Path, help="absolute directory that must not already exist; all evidence is retained")
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
