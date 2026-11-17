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
import base64
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
from driver_core import (CONTINUATION, FAMILY_TEXT, FAMILY_TOOLS, ORIENTATION, REMINDER,
                         expected_tools, iter_values, parse_reference, reading_problem, strict_loads)
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
# C5 usage projection and complete cap frame; origins/digests in CLAUDE-CODE.md.
C5_PARTIAL_USAGE = {
    "input_tokens": 2, "cache_creation_input_tokens": 5116, "cache_read_input_tokens": 0,
    "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 5116},
    "output_tokens": 7, "service_tier": "standard", "inference_geo": "global", "speed": "standard",
}
C5_CAP = {
    "type": "user", "message": {"role": "user", "content": [{"type": "text", "text":
        "Output token limit hit. Resume directly — no apology, no recap of what you were doing. "
        "Pick up mid-thought if that is where the cut happened. Break remaining work into smaller pieces."}]},
    "parent_tool_use_id": None, "session_id": "e108dc8c-2a43-432a-9895-b7ce02dc1560",
    "uuid": "d7d37c01-0dfc-4792-8ee8-379a675585ef", "timestamp": "2026-11-15T20:01:34.772Z",
    "isSynthetic": True,
}


def c5_partial_frame(session, serial, later=False):
    # Only the usage object and repeated/null-stop semantics are projected from
    # the capture. Content, envelope identities and model are synthetic.
    return {"type": "assistant", "session_id": session, "parent_tool_use_id": None,
            "uuid": "00000000-0000-4000-8000-%012d" % serial,
            "message": {"model": MODEL, "id": "c5-later" if later else "c5-repeated",
                        "type": "message", "role": "assistant",
                        "content": [{"type": "text", "text": "Synthetic partial snapshot; work continues."}],
                        "stop_reason": None, "stop_sequence": None, "usage": copy.deepcopy(C5_PARTIAL_USAGE)}}


CONTINUED_MODES = {"continued-deadline", "continued-limit"}
CONTINUED_ASSISTANT_USAGE = (
    {"input_tokens": 101, "cache_creation_input_tokens": 1001, "cache_read_input_tokens": 10001, "output_tokens": 41},
    {"input_tokens": 202, "cache_creation_input_tokens": 2002, "cache_read_input_tokens": 20002, "output_tokens": 82},
    {"input_tokens": 303, "cache_creation_input_tokens": 3003, "cache_read_input_tokens": 30003, "output_tokens": 123},
)
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
    ("runtime-captured-authoring", "C4 field recovery and C5 full refusal, exact-version replacement and submit stop"),
    ("runtime-reply-fidelity", "Grounded pages, substitutions, error flattening and unknown echoes; explicit continuation"),
    ("runtime-fidelity-publication", "Reply mismatch closes a paused seal gate; late drain preserves a winning seal"),
    ("runtime-ordinary-ending", "Unsubmitted turns, one reminder, a valid usage checkpoint, manager seal and confirmed close"),
    ("runtime-hooks-and-effort", "The hook helper admits only pinned tools after startup; a selected effort reaches the launch"),
    ("runtime-cancellation", "Ordered pipelined calls, cancellation behind a large call, late/unknown cancellations and reused IDs"),
    ("runtime-submit-publication", "Seal-publication order: close owns the seal; cancellation preserves placement; signal and deadline stop"),
    ("runtime-relay-loss", "The relay dies while the model lives: the placement stops, nothing else writes, a fresh session continues"),
    ("runtime-usage-series", "Two placements: each session's latest checkpoint is summed and a lost interval stays unknown"),
    ("runtime-captured-accounting", "C5 cap and overlapping partial reports: unknown totals, duplicate invariance and checkpoint control"),
    ("runtime-tool-names", "Prefixed assistant tools and bare MCP calls work; unprefixed and unlisted assistant tools stop"),
    ("runtime-near-limit", "C4-grounded notice: deadline comparison, explicit submission and audit-wide allowance across continuation"),
    ("runtime-compaction", "Each compaction boundary is followed by the pinned notice and spends neither allowance"),
    ("runtime-init-control", "Attempted authoring before a mismatched startup never changes the answer"),
    ("runtime-interruption", "Interrupted work and unknown usage continue in a fresh session without duplication"),
    ("runtime-deadline", "Deadline terminates the synthetic harness and its resistant descendant group"),
    ("runtime-owner-death", "Owner death terminates groups and preserves uncertainty for recovery"),
    ("runtime-unknown-stop", "An unresolved live group prevents restart and close cleanup without being signaled"),
    ("runtime-recorder-failure", "A witnessed capture-write failure stops before an attempted answer mutation"),
    ("runtime-credential-option", "A Claude Code run refuses an API credential option before invoking the harness"),
    ("runtime-family-sequences", "All three families over MCP: preparation notices, citations, labels, delete, "
                                 "empty answer, empty materials and exact packages"),
    ("runtime-read-search", "Paged reads across multibyte boundaries, start refusals, literal search pages, "
                            "scope invariance and list over MCP"),
    ("runtime-identity-across-placements", "A request ID reused in a fresh placement is a new call; "
                                           "reused inside a placement it has no effect"),
    ("runtime-fidelity-drain-unknown", "Missing and duplicate echoes in the shutdown drain stay unknown; "
                                       "the seal and delivery stand"),
    ("runtime-sealed-late-close", "Close while an auditor seal's delivery is paused keeps the seal; "
                                  "the later copy awaits confirmation"),
    ("runtime-start-races-close", "Close winning the log order while run holds its start: refused reference_closed, "
                                  "nothing launched, no start used"),
    ("runtime-first-condition", "The first stopping condition decides: a later signal keeps an ordinary ending; "
                                "a violation keeps its cause when shutdown outlasts the deadline"),
    ("runtime-late-close", "A close requested after an ordinary ending was decided ends authoring by its record "
                           "and leaves the ending"),
    ("runtime-final-interruption", "An interrupted final placement ends authoring as limit; a remaining start "
                                   "leaves it open"),
    ("runtime-unknown-stop-advice", "While stopping is unknown, status and run offer only status; observed absence "
                                    "restores run and close"),
    ("runtime-launch-directory", "Instruction entries above the launch directory, or one within custody, refuse "
                                 "before reservation; clean directories start"),
    ("runtime-notice-transmission", "Notices are sent when claimed and numbered by position; unknown after recovery "
                                    "or a blocked write; never due by placements"),
    ("runtime-notice-not-sent", "A claim whose directory sync fails stops the placement before capture and "
                                "is listed not_sent"),
    ("runtime-blocked-write", "A write to the harness that fails only once the deadline stopped it is the deadline; "
                              "a harness exit observed before the deadline stays a harness error"),
    ("runtime-result-rules", "An error result interrupts whatever its subtype; is_error false with any subtype "
                             "receives the reminder"),
    ("runtime-result-during-call", "A result while a call executes stops the placement; the held call is refused "
                                   "at its link"),
    ("runtime-fidelity-drain-ending", "A drain-time reply mismatch turns a decided ordinary ending into a protocol "
                                      "anomaly; other decided endings keep their value"),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture_material_index(materials):
    """Expected inventory from supplied fixture bytes, never a service reply."""
    directories = {"materials"}
    for name in materials:
        directories.update(str(parent) for parent in Path(name).parents if str(parent) != ".")
    return {"files": [{"name": name, "size": len(data), "sha256": sha(data),
                       "lines": data.count(b"\n") + int(bool(data) and not data.endswith(b"\n"))}
                      for name, data in sorted(materials.items(), key=lambda pair: pair[0].encode())],
            "directories": sorted(directories, key=lambda name: name.encode())}


# Retained C3 material bytes, reconstructed without depending on a run directory.
FIDELITY_PAGES = (
    ("Short control source", 49152, "C3_CONTROL_8A79D4", "materials/control.txt", 0,
     "947ae167c6e71f036d5c603c3f273706c2252b1b18d381bbf7da3045da49e0d2"),
    ("First full page of the two-page source", 65536, "C3_PAGE_ONE_B613F2", "materials/two-pages.txt", 0,
     "e68bd1dcda95edf47c668475d810f587ad80c382afe00cc8bfa8f36ae969ca2a"),
    ("Second full page of the two-page source", 65536, "C3_PAGE_TWO_E90C75", "materials/two-pages.txt", 65536,
     "7f451bbeacea11971c367fd63b96f513ddbdeea38edf74bd68e7c8fbfec12a92"),
)


def fidelity_page(specimen):
    title, size, label, _, _, _ = specimen
    head = (title + "\nThe repeated lines are filler, not evidence about the final label.\n").encode()
    tail = ("TAIL-LABEL: " + label + "\n").encode()
    filler = b"Ordinary padding line for the page transmission comparison.\n"
    space = size - len(head) - len(tail) - 1
    return head + (filler * ((space + len(filler) - 1) // len(filler)))[:space] + b"\n" + tail


def fidelity_echo(identity, result, variant="exact"):
    """Synthetic harness transformation, not the independent verdict."""
    block = {"type": "tool_result", "tool_use_id": identity,
             "content": json.loads(json.dumps(result["content"])),
             "is_error": result.get("isError", False)}
    if variant == "changed-text":
        block["content"][-1]["text"] = block["content"][-1]["text"][:-1]
    elif variant == "wrong-error":
        block["is_error"] = not block["is_error"]
    elif variant in ("error-flat", "success-flat"):
        block["content"] = result["content"][0]["text"]
    elif variant in ("c3-one", "c3-two"):
        block["content"] = C3_NOTICES[0 if variant == "c3-one" else 1]
    elif variant == "reordered":
        block["content"] = [dict(reversed(list(v.items()))) for v in block["content"]]
        if not block["is_error"]:
            del block["is_error"]
    return block


# Original conversation notice text with only the external path replaced.
# Provenance and original content digests are in CLAUDE-CODE.md.
C3_NOTICES = (
    (
        '<persisted-output>\nOutput too large (65.6KB). Full output saved to: /synthetic/external/to'
        'ol-result.json\n\nPreview (first 2KB):\n[\n  {\n    "type": "text",\n    "text": "{\\"schema\\":\\"'
        'stewart.reply/2\\",\\"operation\\":\\"read\\",\\"outcome\\":\\"completed\\",\\"effects\\":{\\"raw_capt'
        'ure\\":\\"recorded\\"},\\"next\\":[{\\"tool\\":\\"read\\",\\"input\\":{\\"source\\":\\"materials/two-pag'
        'es.txt\\",\\"start\\":65536},\\"why\\":\\"Read the rest of this source.\\"}],\\"data\\":{\\"source\\"'
        ':\\"materials/two-pages.txt\\",\\"kind\\":\\"material\\",\\"size\\":131072,\\"range\\":[0,65536],\\"l'
        'ines\\":[1,1093],\\"complete\\":false,\\"cite\\":{\\"source\\":\\"materials/two-pages.txt\\",\\"star'
        't\\":0,\\"end\\":65536}}}"\n  },\n  {\n    "type": "text",\n    "text": "First full page of the t'
        'wo-page source\\nThe repeated lines are filler, not evidence about the final label.\\nOrdina'
        'ry padding line for the page transmission comparison.\\nOrdinary padding line for the page '
        'transmission comparison.\\nOrdinary padding line for the page transmission comparison.\\nOrd'
        'inary padding line for the page transmission comparison.\\nOrdinary padding line for the pa'
        'ge transmission comparison.\\nOrdinary padding line for the page transmission comparison.\\n'
        'Ordinary padding line for the page transmission comparison.\\nOrdinary padding line for the'
        ' page transmission comparison.\\nOrdinary padding line for the page transmission comparison'
        '.\\nOrdinary padding line for the page transmission comparison.\\nOrdinary padding line for '
        'the page transmission comparison.\\nOrdinary padding line for the page transmission compari'
        'son.\\nOrdinary padding line for the page transmission comparison.\\nOrdinary padding line f'
        'or the page transmission comparison.\\nOrdinary padding line for the page transmission comp'
        'arison.\\nOrdinary padding line for the page transmission comparison.\\nOrdinary padding lin'
        'e for the page transmission comparison.\\nOrdinary padding line for the page transmission c'
        'omparison.\\nOrdinary padding line for the page transmission comparison.\\nOrdinary padding '
        'line for the page transmission comparison.\\nOrdinary padding line for the page transmissio'
        'n comparison.\\nOrdinary padding line for the page transmi\n...\n</persisted-output>'
    ),
    (
        '<persisted-output>\nOutput too large (65.5KB). Full output saved to: /synthetic/external/to'
        'ol-result.json\n\nPreview (first 2KB):\n[\n  {\n    "type": "text",\n    "text": "{\\"schema\\":\\"'
        'stewart.reply/2\\",\\"operation\\":\\"read\\",\\"outcome\\":\\"completed\\",\\"effects\\":{\\"raw_capt'
        'ure\\":\\"recorded\\"},\\"next\\":[],\\"data\\":{\\"source\\":\\"materials/two-pages.txt\\",\\"kind\\":'
        '\\"material\\",\\"size\\":131072,\\"range\\":[65536,131072],\\"lines\\":[1094,2186],\\"complete\\":t'
        'rue,\\"cite\\":{\\"source\\":\\"materials/two-pages.txt\\",\\"start\\":65536,\\"end\\":131072}}}"\n  '
        '},\n  {\n    "type": "text",\n    "text": "Second full page of the two-page source\\nThe repea'
        'ted lines are filler, not evidence about the final label.\\nOrdinary padding line for the p'
        'age transmission comparison.\\nOrdinary padding line for the page transmission comparison.\\'
        'nOrdinary padding line for the page transmission comparison.\\nOrdinary padding line for th'
        'e page transmission comparison.\\nOrdinary padding line for the page transmission compariso'
        'n.\\nOrdinary padding line for the page transmission comparison.\\nOrdinary padding line for'
        ' the page transmission comparison.\\nOrdinary padding line for the page transmission compar'
        'ison.\\nOrdinary padding line for the page transmission comparison.\\nOrdinary padding line '
        'for the page transmission comparison.\\nOrdinary padding line for the page transmission com'
        'parison.\\nOrdinary padding line for the page transmission comparison.\\nOrdinary padding li'
        'ne for the page transmission comparison.\\nOrdinary padding line for the page transmission '
        'comparison.\\nOrdinary padding line for the page transmission comparison.\\nOrdinary padding'
        ' line for the page transmission comparison.\\nOrdinary padding line for the page transmissi'
        'on comparison.\\nOrdinary padding line for the page transmission comparison.\\nOrdinary padd'
        'ing line for the page transmission comparison.\\nOrdinary padding line for the page transmi'
        'ssion comparison.\\nOrdinary padding line for the page transmission comparison.\\nOrdinary p'
        'adding line for the page transmission comparison.\\nOrdinary padding line for the page tran'
        'smission comparison.\\nOrdinary padding line for the page \n...\n</persisted-output>'
    ),
)


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
                   + b',"inputSchema":' + tool.get("input_schema").raw
                   + b',"_meta":{"anthropic/maxResultSizeChars":500000}}')
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


def authoring_capture(name):
    return transport_loads((HERE / "testdata" / "runtime" / (name + ".json")).read_bytes())


def authoring_arguments(name, entry=None):
    arguments = authoring_capture(name)["params"]["arguments"]
    if entry is not None:
        arguments["entry"] = entry
    return arguments


def authoring_materials():
    root = HERE / "testdata" / "runtime" / "authoring-materials"
    return {"materials/" + str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def authoring_echo(session, identity, variant):
    value = authoring_capture("c5-quote-result")
    value["session_id"] = session
    block = value["message"]["content"][0]
    block["tool_use_id"] = identity
    value["tool_result_meta"][0]["id"] = identity
    if variant == "array":
        block["content"] = [{"type": "text", "text": block["content"]}]
    elif variant == "wrong-flag":
        block["is_error"] = False
    elif variant != "flat":
        raise ValueError("unknown captured authoring variant")
    return value


def resolve_script_value(value, replies):
    """A scripted step's arguments with each {"$ref": [label, key, ...]} replaced by that
    value of the labelled step's first core reply, plus any "$append" text. An unresolvable
    reference becomes null, so the call itself shows the gap."""
    if isinstance(value, dict) and "$ref" in value:
        path = value["$ref"]
        node = replies.get(path[0])
        for key in path[1:]:
            try:
                node = node[key]
            except (KeyError, IndexError, TypeError):
                node = None
        if "$append" in value:
            return node + value["$append"] if isinstance(node, str) else None
        return node
    if isinstance(value, dict):
        return {key: resolve_script_value(item, replies) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_script_value(item, replies) for item in value]
    return value


def script_follow_input(core, tool):
    """The input of the reply's next call to the same tool while its page is incomplete
    (INTERFACE 7.1, 7.2, 7.5), else None."""
    if not isinstance(core, dict) or core.get("outcome") != "completed":
        return None
    data = core.get("data") if isinstance(core.get("data"), dict) else {}
    complete = data.get("complete") if "complete" in data else (data.get("page") or {}).get("complete")
    if complete is True:
        return None
    later = [n for n in core.get("next") or [] if isinstance(n, dict) and n.get("tool") == tool]
    return later[0]["input"] if later and isinstance(later[0].get("input"), dict) else None


# The release driver's scenario materials (cases_run.scenario_entries), so the runtime
# family sequences can use the same citation operands as the Messages c7.families case.
SCENARIO_MATERIALS = {
    "materials/a.py": b"def send(r):\n    deliver(r)\n    mark_sent(r)\n",
    "materials/notes/R1.txt": "R1. A reminder ID is sent at most once.\r\nrésumé line\r\n".encode(),
    "materials/empty.txt": b"",
}
# INTERFACE 7.6: the preparation reply's keys, in order.
PREPARE_KEYS = ["prepared", "family", "revision", "entry_count", "counts", "notices", "rendering", "selection"]
INABILITY = "I cannot answer this as asked: the materials do not show what happens across a restart."
PROSE = "See materials/a.py lines 1–2 [0, 13) \"def send(r):\" for the start."


def family_sections(family):
    """QUESTION-FORMS: the expected sections; comparison's observation tool is auxiliary."""
    return [name for name in FAMILY_TOOLS[family] if not (family == "comparison" and name == "record_observation")]


def expected_prepare(family, kinds):
    """INTERFACE 7.6 counts (tools order, then record_artifact) and notices for the selected kinds:
    answer_empty alone for an empty selection, else one section_unfilled per empty section.
    Artifacts fill no section (7.4)."""
    counts = {name: 0 for name in FAMILY_TOOLS[family] + ["record_artifact"]}
    for kind in kinds:
        counts[kind] += 1
    if not kinds:
        return counts, [("answer_empty", None)]
    return counts, [("section_unfilled", name) for name in family_sections(family) if counts[name] == 0]


def notice_pairs(data):
    return [(n.get("reason"), n.get("tool")) if n.get("reason") == "section_unfilled" else (n.get("reason"), None)
            for n in (data or {}).get("notices") or [] if isinstance(n, dict)]


def citation_cases(a):
    """c7.families' citation operands over SCENARIO_MATERIALS (INTERFACE 7.3): label,
    citations and the refusal reason, None when the call records an entry."""
    s = a.find(b"deliver(r)")
    return [
        ("range", [{"source": "materials/a.py", "start": s, "end": s + 10}], None),
        ("quote", [{"source": "materials/a.py", "quote": "mark_sent(r)"}], None),
        ("range-and-quote", [{"source": "materials/a.py", "start": s, "end": s + 10, "quote": "deliver(r)"}], None),
        ("changed-range", [{"source": "materials/a.py", "start": s, "end": s + 11, "quote": "deliver(r)"}],
         "citation_invalid"),
        ("missing-quote", [{"source": "materials/a.py", "quote": "not there"}], "quote_not_found"),
        ("ambiguous-quote", [{"source": "materials/a.py", "quote": "(r)"}], "quote_ambiguous"),
        ("irrelevant", [{"source": "materials/notes/R1.txt", "quote": "R1."}], None),
        ("prose", [], None),
        ("read-cite", [{"$ref": ["read-a", "data", "cite"]}], None),
    ]


def script_step(label, tool, arguments=None, **options):
    return dict({"label": label, "tool": tool, "arguments": arguments or {}}, **options)


def step_page_bytes(event):
    """A read page's bytes from a scripted step: the second text block, else data.text or
    data.base64 (INTERFACE 7.1)."""
    content = ((event.get("response") or {}).get("result") or {}).get("content") or []
    data = (event.get("core") or {}).get("data") or {}
    if isinstance(data.get("base64"), str):
        return base64.b64decode(data["base64"])
    if len(content) > 1 and content[1].get("type") == "text":
        return content[1]["text"].encode()
    return data["text"].encode() if isinstance(data.get("text"), str) else None


def scripted_selftest(check):
    """Pure checks of the scripted-sequence helpers and their expectations."""
    import answer_witness as aw
    replies = {"prepare": {"data": {"prepared": "ap1.x"}}, "read": {"data": {"cite": {"source": "q", "start": 0, "end": 1}}}}
    check("scripted.ref", resolve_script_value({"prepared": {"$ref": ["prepare", "data", "prepared"]}, "confirm": True},
                                               replies) == {"prepared": "ap1.x", "confirm": True})
    check("scripted.append", resolve_script_value({"$ref": ["prepare", "data", "prepared"], "$append": "/rendering"},
                                                  replies) == "ap1.x/rendering")
    check("scripted.nested-list", resolve_script_value([{"$ref": ["read", "data", "cite"]}], replies)
          == [{"source": "q", "start": 0, "end": 1}])
    check("scripted.unresolved-is-null", resolve_script_value({"$ref": ["absent", "data"]}, replies) is None
          and resolve_script_value({"$ref": ["prepare", "nothing"], "$append": "/x"}, replies) is None)
    page = {"outcome": "completed", "data": {"complete": False},
            "next": [{"tool": "list", "input": {}}, {"tool": "read", "input": {"source": "s", "start": 9}}]}
    check("scripted.follow-incomplete", script_follow_input(page, "read") == {"source": "s", "start": 9})
    check("scripted.follow-complete", script_follow_input(dict(page, data={"complete": True}), "read") is None)
    check("scripted.follow-reentry-page", script_follow_input(
        {"outcome": "completed", "data": {"page": {"complete": False}},
         "next": [{"tool": "what_am_i_working_with", "input": {"page": "pg.x"}}]}, "what_am_i_working_with")
        == {"page": "pg.x"})
    check("scripted.follow-refused", script_follow_input(dict(page, outcome="refused"), "read") is None)
    counts, notices = expected_prepare("comparison", ["record_account", "record_observation"])
    check("scripted.comparison-observation-not-a-section",
          notices == [("section_unfilled", "record_criterion"), ("section_unfilled", "record_comparison"),
                      ("section_unfilled", "record_limit")] and counts["record_observation"] == 1)
    # QUESTION-FORMS: comparison's observation is auxiliary, open inquiry's is a section.
    check("scripted.observation-is-auxiliary-only-in-comparison",
          ("section_unfilled", "record_observation") not in expected_prepare("comparison", ["record_account"])[1]
          and ("section_unfilled", "record_observation") in expected_prepare("open-inquiry", ["record_account"])[1])
    check("scripted.artifact-fills-no-section", expected_prepare("open-inquiry", ["record_artifact"])[1]
          == [("section_unfilled", "record_account"), ("section_unfilled", "record_observation"),
              ("section_unfilled", "record_limit")])
    check("scripted.empty", expected_prepare("inquiry-framing", []) ==
          ({name: 0 for name in FAMILY_TOOLS["inquiry-framing"] + ["record_artifact"]}, [("answer_empty", None)]))
    a = SCENARIO_MATERIALS["materials/a.py"]
    sources = dict(SCENARIO_MATERIALS, question=b"q")
    outcomes = []
    for label, citations, reason in citation_cases(a):
        if label == "read-cite":
            continue
        try:
            [aw.record_citation(c, sources) for c in citations]
            outcomes.append((label, None))
        except aw.CitationDefect as defect:
            outcomes.append((label, defect.reason))
    check("scripted.citation-cases-agree-with-witness",
          outcomes == [(label, reason) for label, _, reason in citation_cases(a) if label != "read-cite"])
    entries = [aw.Entry("e1", 1, "record_account", "", b"x"), aw.Entry("e2", 1, "record_limit", "", b"y")]
    check("scripted.control-dropped-entry-differs", aw.answer_json(2, entries) != aw.answer_json(2, entries[:1])
          and aw.render(entries) != aw.render(entries[:1]))
    check("scripted.page-bytes", step_page_bytes({"response": {"result": {"content": [{"type": "text", "text": "{}"},
                                                                                    {"type": "text", "text": "é"}]}},
                                                  "core": {"data": {}}}) == "é".encode()
          and step_page_bytes({"response": {"result": {"content": [{"type": "text", "text": "{}"}]}},
                               "core": {"data": {"text": ""}}}) == b"")


def sequence_selftest(check):
    """Pure checks of the sequence helpers, with controls."""
    for text, kind in ((REMINDER, "reminder"), (CONTINUATION, "continuation"), (COMPACTED, "compacted"),
                       (NEAR_LIMIT.format(seconds=4, placements=2), "near_limit"),
                       (REMINDER + " ", "other"), (NEAR_LIMIT, "other"), (None, "other")):
        check("sequence.input-kind." + kind + ("-control" if kind == "other" else ""), input_kind(text) == kind)
    frame = lambda text: compact({"type": "user", "session_id": "", "parent_tool_use_id": None,
                                  "message": {"role": "user", "content": text}}) + b"\n"
    check("sequence.input-frames", input_frames(frame("q") + frame(REMINDER)) == ["q", REMINDER])
    check("sequence.input-frames.cut-off-is-not-a-frame", input_frames(frame("q") + frame(REMINDER)[:-1]) == ["q"])
    read_end, write_end = os.pipe()
    child = subprocess.Popen(["/bin/sleep", "20"], stdin=read_end)
    try:
        held = pipe_readers(read_end)
        check("sequence.pipe-readers.other-holder", held is None or held == [[child.pid, 0]])
    finally:
        child.kill()
        child.wait(timeout=5)
    alone = pipe_readers(read_end)
    check("sequence.pipe-readers.sole-holder-control", alone is None or alone == [])
    os.close(read_end)
    os.close(write_end)
    pipe_packing_selftest(check)


def pipe_packing_selftest(check):
    """The packing rule for the runtime's notice frames, with controls, then the rule against
    the actual kernel through fresh unread pipes on this host."""
    notice, reminder = len(user_frame(COMPACTED)), len(user_frame(REMINDER))
    check("pipe-packing.frame-lengths", (notice, reminder) == (255, 249))
    linux = {"platform": "linux", "capacity": 65536, "page_size": 4096, "packet": False}
    macos = {"platform": "darwin", "capacity": MACOS_PIPE_BYTES, "page_size": None, "packet": False}
    # Linux: 16 notices fill a 4 KiB page (4,080 bytes), 16 pages hold 256; macOS holds 257 in
    # 65,535 bytes. Raw bytes overstate Linux by one notice.
    check("pipe-packing.linux-pages", pipe_frames_fit(notice, linux) == 256)
    check("pipe-packing.macos-bytes", pipe_frames_fit(notice, macos) == 257)
    check("pipe-packing.byte-count-control", 65536 // notice == 257 and pipe_accepts([notice] * 257, linux) == 256)
    # After the fitting notices the reminder cannot complete; one notice fewer leaves it room.
    check("pipe-packing.linux-reminder-blocked", pipe_accepts([notice] * 256 + [reminder], linux) == 256
          and pipe_accepts([notice] * 255 + [reminder], linux) == 256)
    check("pipe-packing.macos-reminder-blocked", pipe_accepts([notice] * 257 + [reminder], macos) == 257
          and pipe_accepts([notice] * 256 + [reminder], macos) == 257)
    # A sub-page write merges into the last page only when it fits there whole.
    check("pipe-packing.linux-merge-fits-whole", pipe_accepts([notice] * 256 + [16, 1], linux) == 257
          and pipe_accepts([notice] * 256 + [17], linux) == 256)
    check("pipe-packing.linux-page-write-takes-a-slot", pipe_accepts([4096] * 17, linux) == 16
          and pipe_accepts([1, 4096], dict(linux, capacity=4096)) == 1)
    check("pipe-packing.linux-packet-mode", pipe_frames_fit(notice, dict(linux, packet=True)) == 16)
    # Large writes: the sub-page remainder merges first, the rest takes whole pages.
    check("pipe-packing.linux-large-writes", pipe_accepts([30000] * 3, linux) == 2
          and pipe_accepts([30000] * 2 + [4096], linux) == 3 and pipe_accepts([30000] * 2 + [4097], linux) == 2)
    check("pipe-packing.linux-other-geometry", pipe_frames_fit(notice, dict(linux, capacity=8192)) == 32
          and pipe_frames_fit(notice, dict(linux, capacity=1 << 20, page_size=65536)) == 16 * 257)
    # The actual kernel, through fresh pipes of this host's default geometry.
    read_end, write_end = os.pipe()
    try:
        facts = input_pipe_facts(read_end)
    finally:
        os.close(read_end)
        os.close(write_end)
    fit = pipe_frames_fit(notice, facts)
    sequences = ([notice] * (fit + 1), [notice] * fit + [reminder], [notice] * (fit - 1) + [reminder],
                 [30000] * 3, [30000] * 2 + [4096])
    probed = [pipe_probe(writes, facts["capacity"]) for writes in sequences]
    print("Pipe packing on this host: %s; %d notice frames fit" % (compact(facts).decode(), fit))
    # By the rule: one notice more is refused, the reminder after them too, and one notice
    # fewer leaves the reminder room. The kernel must agree on every sequence.
    check("pipe-packing.host-rule", [pipe_accepts(writes, facts) for writes in sequences[:3]] == [fit, fit, fit])
    check("pipe-packing.host-probe", [p["accepted"] for p in probed] == [pipe_accepts(w, facts) for w in sequences])
    check("pipe-packing.host-probe-capacity", all(p["capacity"] == (facts["capacity"] if facts["page_size"] else None)
                                                   for p in probed))


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


def near_limit_values(text):
    if not isinstance(text, str):
        return None
    pattern = re.escape(NEAR_LIMIT).replace(re.escape("{seconds}"), r"(?P<seconds>0|[1-9][0-9]*)")
    pattern = pattern.replace(re.escape("{placements}"), r"(?P<placements>0|[1-9][0-9]*)")
    match = re.fullmatch(pattern, text)
    return {key: int(value) for key, value in match.groupdict().items()} if match else None


def input_kind(content):
    """Classify one supplied input by the pinned texts (CONTRACT, runtime texts)."""
    if content == REMINDER:
        return "reminder"
    if content == CONTINUATION:
        return "continuation"
    if content == COMPACTED:
        return "compacted"
    if near_limit_values(content) is not None:
        return "near_limit"
    return "other"


def user_frame(text):
    """One supplied input frame with this content, as CONTRACT's wire section defines it."""
    return compact({"type": "user", "session_id": "", "parent_tool_use_id": None,
                    "message": {"role": "user", "content": text}}) + b"\n"


def input_frames(stream):
    """The decoded contents of the complete LF-terminated input frames in a captured
    input stream; an unterminated tail is not a frame."""
    contents = []
    for raw in stream.split(b"\n")[:-1]:
        try:
            value = strict_loads(raw + b"\n")
        except ValueError:
            contents.append(None)
            continue
        contents.append(value.get("message", {}).get("content") if isinstance(value, dict) else None)
    return contents


def pipe_readers(fd=0):
    """Other processes holding the read side of the pipe on this process's descriptor fd,
    as sorted [pid, fd] pairs; None when this host gives no such observation. Linux reads
    /proc; macOS lists open files with lsof, whose device field names one pipe end."""
    me = os.getpid()
    if sys.platform.startswith("linux"):
        try:
            target = os.readlink("/proc/self/fd/%d" % fd)
        except OSError:
            return None
        if not target.startswith("pipe:"):
            return None
        holders = []
        for pid in os.listdir("/proc"):
            if not pid.isdigit() or int(pid) == me:
                continue
            try:
                names = os.listdir("/proc/%s/fd" % pid)
            except OSError:
                continue
            for name in names:
                try:
                    if os.readlink("/proc/%s/fd/%s" % (pid, name)) != target:
                        continue
                    with open("/proc/%s/fdinfo/%s" % (pid, name)) as info:
                        flags = next(int(line.split()[1], 8) for line in info if line.startswith("flags:"))
                except (OSError, StopIteration, ValueError, IndexError):
                    continue
                if flags & 3 != os.O_WRONLY:
                    holders.append([int(pid), int(name)])
        return sorted(holders)
    if sys.platform == "darwin" and os.path.exists("/usr/sbin/lsof"):
        def listing(arguments):
            try:
                # lsof must not inherit the descriptor under observation.
                done = subprocess.run(["/usr/sbin/lsof", "-b", "-w", "-nP", "-F", "ftd"] + arguments,
                                      stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                return None
            rows, pid, name, kind = [], None, None, None
            for line in done.stdout.decode("utf-8", "replace").splitlines():
                tag, value = line[:1], line[1:]
                if tag == "p":
                    pid = int(value)
                elif tag == "f":
                    name, kind = value, None
                elif tag == "t":
                    kind = value
                elif tag == "d" and kind == "PIPE":
                    rows.append((pid, name, value))
            return rows
        own = listing(["-a", "-p", str(me), "-d", str(fd)])
        own = [device for _, name, device in own or [] if name == str(fd)]
        everyone = listing([]) if len(own) == 1 else None
        if everyone is None:
            return None
        return sorted([pid, int(name)] for pid, name, device in everyone
                      if device == own[0] and name.isdigit() and (pid, name) != (me, str(fd)))
    return None


LINUX_F_SETPIPE_SZ = 1031
LINUX_F_GETPIPE_SZ = 1032
# XNU grows a pipe's single byte buffer on demand up to this bound (BIG_PIPE_SIZE). No call
# reports it; pipe_probe and the self-test observe it.
MACOS_PIPE_BYTES = 65536


def input_pipe_facts(fd=0):
    """The facts that decide how writes pack into the pipe on descriptor fd. On Linux,
    F_GETPIPE_SZ reports the pipe's page-buffer slots times the page size, and a packet-mode
    (O_DIRECT) pipe never merges writes. A macOS pipe is one byte buffer, so it has no page
    size here."""
    if sys.platform.startswith("linux"):
        import fcntl
        return {"platform": "linux", "capacity": fcntl.fcntl(fd, LINUX_F_GETPIPE_SZ),
                "page_size": os.sysconf("SC_PAGESIZE"),
                "packet": bool(fcntl.fcntl(fd, fcntl.F_GETFL) & getattr(os, "O_DIRECT", 0))}
    if sys.platform == "darwin":
        return {"platform": "darwin", "capacity": MACOS_PIPE_BYTES, "page_size": None, "packet": False}
    raise ValueError("no pipe packing rule for " + sys.platform)


def pipe_accepts(writes, facts):
    """How many of the leading writes complete in full, in order, in an initially empty pipe
    that nobody reads, each being one write(2) of that many bytes (facts from
    input_pipe_facts). The first write that cannot complete ends the count: a blocking writer
    waits there, holding everything after it.

    Linux pipes are page-granular (fs/pipe.c, pipe_write). When the pipe is not empty, a
    write's sub-page remainder merges into the last page buffer if it fits there whole;
    everything else takes fresh page buffers, of which the pipe has capacity / page size.
    Packet-mode pipes never merge. A macOS pipe accepts bytes up to its buffer bound."""
    if facts["page_size"] is None:
        used = 0
        for count, size in enumerate(writes):
            if used + size > facts["capacity"]:
                return count
            used += size
        return len(writes)
    page = facts["page_size"]
    slots = facts["capacity"] // page
    buffers = []  # bytes held by each page buffer in use, oldest first; nothing is read
    for count, size in enumerate(writes):
        if size <= 0:
            raise ValueError("a write has at least one byte")
        merged = size % page
        if not (buffers and merged and not facts["packet"] and buffers[-1] + merged <= page):
            merged = 0
        rest = size - merged
        if len(buffers) + -(-rest // page) > slots:
            return count
        if merged:
            buffers[-1] += merged
        while rest:
            buffers.append(min(page, rest))
            rest -= buffers[-1]
    return len(writes)


def pipe_frames_fit(frame_bytes, facts):
    """How many writes of frame_bytes each complete in an empty, unread pipe."""
    return pipe_accepts([frame_bytes] * (facts["capacity"] // frame_bytes + 1), facts)


def pipe_probe(writes, capacity=None):
    """Observe how many of the leading writes complete in full in a fresh pipe that nobody
    reads. Each is one nonblocking write(2) of that many bytes; the first that is refused or
    only partly written ends the count. On Linux the probe pipe first gets the stated
    capacity where it differs; the result reports the capacity it actually had."""
    read_end, write_end = os.pipe()
    try:
        os.set_blocking(write_end, False)
        observed = None
        if sys.platform.startswith("linux"):
            import fcntl
            if capacity is not None and fcntl.fcntl(write_end, LINUX_F_GETPIPE_SZ) != capacity:
                try:
                    fcntl.fcntl(write_end, LINUX_F_SETPIPE_SZ, capacity)
                except OSError:
                    pass  # the reported capacity shows the difference
            observed = fcntl.fcntl(write_end, LINUX_F_GETPIPE_SZ)
        for count, size in enumerate(writes):
            try:
                if os.write(write_end, b"\0" * size) != size:
                    return {"accepted": count, "capacity": observed}
            except BlockingIOError:
                return {"accepted": count, "capacity": observed}
        return {"accepted": len(writes), "capacity": observed}
    finally:
        os.close(read_end)
        os.close(write_end)


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


INSTRUCTION_ENTRIES = (".git", "CLAUDE.md", "AGENTS.md", ".claude")


def validate_work_path(work):
    """Reject known project ancestry before constructing launch fixtures. The profiles'
    temporary directories lie under --work, and run refuses one with an instruction entry
    in any ancestor (CONTRACT, wire and process), so such ancestry would refuse every start."""
    if work.resolve().is_relative_to(HERE.parent.parent.resolve()):
        raise ValueError("--work must be outside the driver repository; use a fresh physical temporary directory")
    for ancestor in work.resolve().parents:
        for name in INSTRUCTION_ENTRIES:
            if os.path.lexists(ancestor / name):
                raise ValueError("--work has %s in its ancestor %s; run refuses such a launch directory"
                                 % (name, ancestor))


class Driver:
    def __init__(self, binary, work, release=None, selected=None, variant=None):
        validate_work_path(work)
        self.binary, self.work, self.release, self.variant = binary, work, release, variant
        self.selected = set(selected) if selected else {name for name, _ in CASES}
        self.work.mkdir(mode=0o700, parents=False, exist_ok=False)
        source = work / "driver-snapshot"
        source.mkdir()
        for name in ("claude_code.py", "driver_core.py", "rawjson.py", "answer_witness.py"):
            (source / name).write_bytes((HERE / name).read_bytes())
        for path in (HERE / "testdata" / "runtime").rglob("*"):
            if path.is_file():
                target = source / path.relative_to(HERE)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
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

    def cmd(self, label, args, outcome="completed", binary=None, raw=False, env=None, cwd=None, input_bytes=None,
            timeout=30):
        self.serial += 1
        prefix = "%04d-%s" % (self.serial, label)
        argv = [str(binary or self.binary)] + [str(x) for x in args] + ([] if raw else ["--json"])
        before = {str(a): snapshot(a) for a in self.archives}
        starts_before = {str(p): p.read_bytes() if p.exists() else None for p in self.canaries}
        started = time.monotonic()
        try:
            process = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     env=env or self.env, cwd=cwd or self.cwd, input=input_bytes, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            (self.commands / (prefix + ".stdout")).write_bytes(exc.stdout or b"")
            (self.commands / (prefix + ".stderr")).write_bytes(exc.stderr or b"")
            self.save("commands/" + prefix + ".json", {"argv": argv, "timeout": True, "bound_seconds": timeout})
            self.require(label + ".deadline", False, "local command exceeded %s seconds" % timeout)
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
                effort=None, *, python=None, temporary=None):
        """A prepared submission, archive and profile. temporary, when given, names the
        profile's temporary_directory from (root, folder, archive) in place of the default
        empty directory beside the synthetic executable."""
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
                  "temporary_directory": str(temporary(root, folder, archive) if temporary
                                             else launch_dir / "temporary")}
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
                   "materials": {"materials/report.txt": material}, "witness": witness, "executable": executable,
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
        # CONTRACT: the common arrangement's exact reading bounds (INTERFACE 6.2),
        # which pins the fields, their values and their order.
        self.eq(label + ".reading", obj.get("reading"), {
            "read_page_bytes": 65536, "binary_page_bytes": 49152, "search_text_bytes": 1024,
            "search_hits_per_page": 128, "search_context_bytes_per_page": 32768,
            "context_bytes_per_hit": 240, "list_page_materials": 128, "tool_input_bytes": 4194304})
        self.eq(label + ".reading-order", reading_problem(obj.get("reading")), None)
        system = compact([{"type": "text", "text": RUNTIME_ORIENTATION},
                          {"type": "text", "text": FAMILY_TEXT[f["family"]]}])
        for key, value in (("system", system), ("tools", f["tools"]), ("mcp_tools", mcp_tools(f["tools"])),
                           ("surface", SURFACE)):
            actual = node.get(key)
            self.eq(label + "." + key + "-bytes", actual.raw.decode() if actual else None, value.decode())
        bindings = obj.get("bindings", {})
        self.eq(label + ".binding-keys", sorted(bindings), ["material_index_sha256", "question_body_sha256"])
        self.eq(label + ".question-binding", bindings.get("question_body_sha256"), sha(f["body"]))
        index = fixture_material_index(f["materials"])
        self.eq(label + ".material-index-binding", bindings.get("material_index_sha256"), sha(compact(index)))
        self.eq(label + ".reply-digest", data["arrangement"]["sha256"], sha(raw))
        self.eq(label + ".settings-runtime", data["settings"].get("runtime"), expected["runtime"])
        self.eq(label + ".settings-limits", data["settings"].get("limits"), f["limits"])

    def accept(self, f):
        prepared = self.prepare(f)
        question = (f["witness"] / "question-file").read_bytes()
        body = (f["witness"] / "question-body").read_bytes()
        index = fixture_material_index(f["materials"])
        self.eq(f["label"] + ".question-inventory", prepared["data"].get("question"),
                {"file_bytes": len(question), "file_sha256": sha(question),
                 "body_bytes": len(body), "body_sha256": sha(body)})
        self.eq(f["label"] + ".material-inventory", prepared["data"].get("materials"),
                {"count": len(index["files"]), "bytes": sum(row["size"] for row in index["files"]),
                 "directories": index["directories"], "files": index["files"]})
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
        # Every selected material reads back as the driver's own copy of its bytes (5.5).
        materials = sorted(f["materials"].items(), key=lambda pair: pair[0].encode())
        for item, expected in ([("question-file", (f["witness"] / "question-file").read_bytes()),
                                ("question-body", (f["witness"] / "question-body").read_bytes())]
                               + materials + [("arrangement", raw)]):
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
        # A previously checked inventory cannot attest the newly supplied
        # annotation. This is a different digest of otherwise identical tools.
        unannotated = json.loads(mcp_tools(f["tools"]))
        for tool in unannotated:
            del tool["_meta"]
        node = parse(f["profile"]).get("check").get("tools_sha256")
        stale = f["profile"][:node.start] + compact(sha(compact(unannotated))) + f["profile"][node.end:]
        f["profile_path"].write_bytes(stale)
        (f["witness"] / "unannotated-tools-profile.json").write_bytes(stale)
        reply = self.prepare(f, "unannotated-tools", "refused")
        self.profile_refusal("binding.unannotated-tools", reply, named=("tool",))
        marker = Path(str(f["executable"]) + ".started")
        self.control("unannotated-tools-binding", reply.get("outcome") == "refused" and not marker.exists())
        f["profile_path"].write_bytes(f["profile"])
        self.prepare(f, "annotation-restored")
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

    def check_delivery(self, f, status_reply, actor="auditor", *, expected=None):
        data = status_reply["data"]
        self.eq(f["label"] + "." + actor + "-seal", data.get("seal", {}).get("actor"), actor)
        delivery = data.get("headline", {}).get("delivered", {})
        self.require(f["label"] + ".verified-delivery", delivery.get("verified") is True, delivery)
        package = Path(delivery["location"])
        if expected is None:
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

    def close_after_delivery(self, f, package, placements=1, mismatch=False):
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
        self.eq(label + ".close-runs", data.get("runs"), {"count": placements, "held": False, "last_ending": "sealed"})
        self.runtime_allowances(label + ".close", data, placements, f)
        if mismatch:
            self.check(label + ".close-warning", "mismatch" in data.get("summary", "").lower(), data)
        status_reply = self.cmd(label + ".status-closed", ["status", f["reference"]])
        headline = status_reply["data"].get("headline", {})
        self.eq(label + ".closed-headline", headline.get("closed"), "yes")
        self.eq(label + ".closed-condition", status_reply["data"].get("condition"), "closed")
        self.eq(label + ".delivery-confirmed", headline.get("delivered", {}).get("confirmed"), True)
        repeat = self.cmd(label + ".close-again", ["close", f["reference"]])
        self.eq(label + ".close-again-already", (repeat.get("data") or {}).get("already_closed"), True)
        if mismatch:
            self.check(label + ".close-again-warning", "mismatch" in repeat.get("data", {}).get("summary", "").lower(), repeat)
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

    def runtime_captured_authoring(self):
        import answer_witness as aw
        initial = authoring_arguments("c4-account")
        corrected = authoring_arguments("c4-replace-corrected")
        replacement = authoring_arguments("c5-replace-account")
        materials = authoring_materials()
        citations = [aw.record_citation(c, materials) for c in replacement["citations"]]
        expected = aw.answer_json(3, [aw.Entry("e1", 3, "record_account", replacement["label"],
                                              replacement["text"].encode(), citations)])
        packages = []
        for variant in ("flat", "array", "wrong-flag"):
            label = "captured-authoring-" + variant
            f = self.fixture(label, scenario="fidelity", timeout=60)
            self.change_scenario(f, fidelity_variant="captured-authoring", authoring_variant=variant)
            for source, raw in materials.items():
                f["materials"][source] = raw
                for base in (f["folder"], f["witness"] / "supplied"):
                    path = base / source
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
            (f["witness"] / "expected-answer.json").write_bytes(expected)
            self.accept(f)
            reply = self.cmd(label + ".run", ["run", f["reference"]])
            self.groups_absent(f)
            events = self.harness_clean(f)
            mismatch = variant == "wrong-flag"
            status = self.inspect_runtime(f)
            self.eq(label + ".ending", reply["data"].get("ending"), "interrupted" if mismatch else "sealed")
            self.eq(label + ".cause", reply["data"].get("cause"), "protocol_anomaly" if mismatch else None)
            self.eq(label + ".answer", status["data"].get("answer"),
                    {"revision": 2 if mismatch else 3, "entries": 1})
            steps = {e["step"]: e for e in events if e["event"] == "authoring-step"}
            order = [e["step"] for e in events if e["event"] == "authoring-step"]
            sequence = ["initial", "missing-fields", "read-v1", "corrected", "missing-quote"]
            if not mismatch:
                sequence += ["read-v2", "long-replacement", "stale-target", "read-v3", "membership", "prepare", "selection"]
            self.require(label + ".sequence", order == sequence, order)
            for name, reason, data in (
                    ("missing-fields", "fields_invalid", {"entry_kind": "record_account", "missing": ["citations"], "not_allowed": []}),
                    ("missing-quote", "quote_not_found", {"index": 0, "source": "materials/R/frsr.R"})):
                core = steps[name]["core"]
                self.eq(label + "." + name + ".outcome", core.get("outcome"), "refused")
                self.eq(label + "." + name + ".reason", core.get("reason"), reason)
                self.eq(label + "." + name + ".data", core.get("data"), data)
                self.eq(label + "." + name + ".effects", core.get("effects"),
                        {"answer": "unchanged", "raw_capture": "recorded"})
            error = steps["missing-quote"]["response"]["result"]
            observed_text = authoring_capture("c5-quote-result")["message"]["content"][0]["content"]
            self.eq(label + ".full-refusal", error, {"content": [{"type": "text", "text": observed_text}], "isError": True})
            for number, args in ((1, initial), (2, corrected), (3, replacement)):
                if number == 3 and mismatch:
                    continue
                payload = self.audit_path(f) / "payload" / ("e1.v%d.bin" % number)
                self.require(label + ".retained-v%d" % number, payload.exists(), str(payload))
                self.eq(label + ".payload-v%d" % number, payload.read_bytes(), args["text"].encode())
                step = steps.get("read-v%d" % number)
                if step:
                    content = step["response"]["result"]["content"]
                    self.eq(label + ".read-v%d" % number, content[1:] , [{"type": "text", "text": args["text"]}])
                    self.eq(label + ".read-v%d-range" % number, step["core"].get("data", {}).get("range"),
                            [0, len(args["text"].encode())])
                    self.eq(label + ".read-v%d-complete" % number, step["core"].get("data", {}).get("complete"), True)
            self.fidelity_record(f, 4 if mismatch else 12, int(mismatch))
            for channel, event_name in (("stdout", "output"), ("input", "input"), ("mcp", "rpc-send")):
                sent = b"".join(bytes.fromhex(e["raw_hex"]) for e in events if e["event"] == event_name)
                self.eq(label + ".capture-" + channel, self.captured_channel(f, channel), sent)
            shaped, inputs = self.message_contents(events)
            self.check(label + ".one-input", shaped and inputs == [f["body"].decode()], inputs)
            submits = [e for e in events if e["event"] == "authoring-submit"]
            self.eq(label + ".explicit-submits", len(submits), 0 if mismatch else 1)
            submit_requests = [e for e in events if e["event"] == "rpc-send"
                               and e["value"].get("params", {}).get("name") == "submit"]
            self.eq(label + ".transmitted-submits", len(submit_requests), 0 if mismatch else 1)
            if mismatch:
                self.eq(label + ".no-seal", status["data"].get("seal"), {"state": "absent", "actor": None})
                diagnostics = [strict_loads(p.read_bytes())["body"] for p in (self.audit_path(f) / "diag").glob("*.json")]
                diagnostics = [d for d in diagnostics if d.get("reason") == "runtime_reply_mismatch"]
                self.control("captured-error-flag-stops", reply["data"].get("cause") == "protocol_anomaly"
                             and len(diagnostics) == 1)
                self.require(label + ".one-mismatch-diagnostic", len(diagnostics) == 1, diagnostics)
                context = diagnostics[0].get("context", {})
                for key, value in (("run", 1), ("phase", "live"), ("seal_record", None),
                                   ("tool_use_id", "toolu_fidelity_5")):
                    self.eq(label + ".diagnostic-" + key, context.get(key), value)
                observed = context["observed_stdout"]
                raw = self.captured_channel(f, "stdout")
                frame = raw[observed["offset"]:observed["offset"] + observed["length"]]
                self.eq(label + ".diagnostic-frame-digest", sha(frame), observed["sha256"])
                self.eq(label + ".diagnostic-target-frame", transport_loads(frame),
                        authoring_echo(label + "-session-1", "toolu_fidelity_5", "wrong-flag"))
                retained = context["expected_result"]
                self.eq(label + ".diagnostic-result-path", retained["path"],
                        "runs/1/result-%d.json" % context["call"])
                result_raw = (self.audit_path(f) / retained["path"]).read_bytes()
                self.eq(label + ".diagnostic-result-digest", sha(result_raw), retained["sha256"])
                result_body = strict_loads(result_raw)["body"]
                self.eq(label + ".diagnostic-expected-refusal", result_body.get("content"), error["content"])
                self.eq(label + ".diagnostic-expected-flag", result_body.get("is_error"), True)
                continue
            changed = steps["long-replacement"]["core"].get("data", {})
            for key, value in (("id", "e1"), ("version", 3), ("revision", 3), ("citations", citations)):
                self.eq(label + ".replacement-" + key, changed.get(key), value)
            stale = steps["stale-target"]["core"]
            self.eq(label + ".stale-reason", stale.get("reason"), "stale_entry")
            self.eq(label + ".stale-current", stale.get("data", {}).get("current"), changed.get("entry"))
            self.eq(label + ".stale-effects", stale.get("effects"), {"answer": "unchanged", "raw_capture": "recorded"})
            membership = steps["membership"]["core"].get("data", {})
            self.eq(label + ".membership-revision", membership.get("revision"), 3)
            self.eq(label + ".membership-entries", [e.get("entry") for e in membership.get("entries", [])], [changed.get("entry")])
            selection = steps["selection"]["response"]["result"]["content"][1:]
            self.eq(label + ".prepared-selection", selection, [{"type": "text", "text": expected.decode()}])
            delivery = status["data"].get("headline", {}).get("delivered", {})
            self.require(label + ".verified-delivery", delivery.get("verified") is True, delivery)
            package = Path(delivery["location"])
            self.eq(label + ".delivered-selection", (package / "answer.json").read_bytes(), expected)
            packages.append((package / "answer.json").read_bytes())
            self.close_after_delivery(f, package)
        self.control("captured-flat-and-array-invariance", packages == [expected, expected])

    def fidelity_fixture(self, label, variant, placements=3):
        f = self.fixture(label, scenario="fidelity", timeout=60, placements=placements)
        self.change_scenario(f, fidelity_variant=variant)
        for source in {p[3] for p in FIDELITY_PAGES}:
            data = b"".join(fidelity_page(p) for p in FIDELITY_PAGES if p[3] == source)
            f["materials"][source] = data
            (f["folder"] / source).write_bytes(data)
            (f["witness"] / Path(source).name).write_bytes(data)
        self.accept(f)
        return f

    def fidelity_record(self, f, exact, mismatches, unknown_min=1, run=1):
        label = f["label"] + ".fidelity-%d" % run
        path = self.audit_path(f) / "runs" / str(run) / "runtime-fidelity.json"
        self.require(label + ".exists", path.exists(), str(path))
        record = strict_loads(path.read_bytes())
        self.eq(label + ".members", sorted(record), sorted(("schema", "run", "supplied", "exact",
                  "mismatch", "unknown", "unmatched", "capture_complete")))
        self.eq(label + ".schema", record.get("schema"), "stewart.claude-code.fidelity/1")
        self.eq(label + ".run", record.get("run"), run)
        self.check(label + ".counts", all(type(record.get(k)) is int and record[k] >= 0
                   for k in ("supplied", "exact", "mismatch", "unknown", "unmatched")), record)
        self.eq(label + ".exact", record.get("exact"), exact)
        self.eq(label + ".mismatch", record.get("mismatch"), mismatches)
        self.check(label + ".unknown", record.get("unknown", -1) >= unknown_min, record)
        self.eq(label + ".capture-complete", record.get("capture_complete"), True)
        mcp = [transport_loads(raw) for raw in self.captured_channel(f, "mcp", run).splitlines()]
        outgoing = [transport_loads(raw) for raw in self.captured_channel(f, "mcp-out", run).splitlines()]
        calls = {v["id"] for v in mcp if v.get("method") == "tools/call" and "id" in v}
        supplied = [v for v in outgoing if v.get("id") in calls and isinstance(v.get("result"), dict)
                    and isinstance(v["result"].get("content"), list)]
        self.eq(label + ".supplied-raw-envelopes", record.get("supplied"), len(supplied))
        self.eq(label + ".partition", record.get("supplied"), sum(record[k] for k in ("exact", "mismatch", "unknown")))
        return record

    def fidelity_page_witness(self, f):
        events = self.harness_events(f)
        pages = [e for e in events if e.get("event") == "fidelity-result" and e.get("name") == "read"]
        self.require(f["label"] + ".page-comparison-fired", bool(pages), str(f["witness"]))
        for number, event in enumerate(pages):
            prefix = f["label"] + ".page-%d" % number
            result = event["response"]["result"]
            self.eq(prefix + ".success", result.get("isError", False), False)
            content = result["content"]
            self.require(prefix + ".two-blocks", len(content) == 2, len(content))
            core = strict_loads(content[0]["text"].encode())
            data = core["data"]
            matches = [p for p in FIDELITY_PAGES if p[3] == data["source"] and p[4] == data["range"][0]]
            self.require(prefix + ".requested-page", len(matches) == 1, data)
            specimen = matches[0]
            self.eq(prefix + ".source-bytes", sha(content[1]["text"].encode()), specimen[5])
            self.eq(prefix + ".range", data["range"], [specimen[4], specimen[4] + specimen[1]])
            self.eq(prefix + ".complete", data["complete"], specimen != FIDELITY_PAGES[1])
            self.eq(prefix + ".source-size", data["size"], 49152 if specimen == FIDELITY_PAGES[0] else 131072)

    def fidelity_diagnostics(self, f, mismatch, phase=None, sealed=False):
        label = f["label"]
        audit = self.audit_path(f)
        rows = [(p, strict_loads(p.read_bytes())["body"]) for p in sorted((audit / "diag").glob("*.json"))]
        rows = [(p, d) for p, d in rows if d.get("reason") == "runtime_reply_mismatch"]
        self.eq(label + ".mismatch-diagnostic-count", len(rows), 1 if mismatch else 0)
        for path, diagnostic in rows:
            self.eq(label + ".diagnostic-operation", diagnostic.get("operation"), "run")
            ctx = diagnostic.get("context") or {}
            self.eq(label + ".diagnostic-members", sorted(ctx), sorted(("run", "call", "tool_use_id", "phase",
                        "seal_record", "expected_result", "observed_stdout")))
            if phase:
                self.eq(label + ".observation-phase", ctx.get("phase"), phase)
            seal = ctx.get("seal_record")
            self.check(label + ".seal-at-detection", isinstance(seal, str) if sealed else seal is None, ctx)
            if isinstance(seal, str):
                self.check(label + ".diagnostic-seal-exists", (audit / seal).is_file(), ctx)
            expected = ctx["expected_result"]
            self.eq(label + ".expected-reference", expected["path"], "runs/%d/result-%d.json" % (ctx["run"], ctx["call"]))
            self.eq(label + ".expected-digest", sha((audit / expected["path"]).read_bytes()), expected["sha256"])
            ref = ctx["observed_stdout"]
            raw = self.captured_channel(f, "stdout", ctx["run"])
            frame = raw[ref["offset"]:ref["offset"] + ref["length"]]
            self.eq(label + ".observed-digest", sha(frame), ref["sha256"])
            self.check(label + ".observed-frame-boundary", frame.endswith(b"\n") and
                       (ref["offset"] == 0 or raw[ref["offset"] - 1] == 10), ref)
            value = transport_loads(frame)
            block = value["message"]["content"][ref["block_index"]]
            self.eq(label + ".observed-identity", block.get("tool_use_id"), ctx["tool_use_id"])
            witness = [e for e in self.harness_events(f) if e.get("event") == "fidelity-result"
                       and e.get("tool_use_id") == ctx["tool_use_id"]]
            self.require(label + ".independent-expected-reply", len(witness) == 1, witness)
            supplied = witness[0]["response"]["result"]
            self.eq(label + ".auxiliary-invariance", value.get("tool_use_result"), supplied["content"])
            # Express the verdict independently of the harness transformation.
            actual = block["content"]
            equal = actual == supplied["content"]
            if isinstance(actual, str) and supplied.get("isError") is True and len(supplied["content"]) == 1:
                equal = actual == supplied["content"][0]["text"]
            equal = equal and block.get("is_error", False) == supplied.get("isError", False)
            self.control(label + "-different-conversation-exact-auxiliary", not equal)
        return rows

    def runtime_reply_fidelity(self):
        mismatching = {"c3-one", "c3-two", "changed-text", "wrong-error", "success-flat", "error-wrong-flag"}
        for variant in ("exact", "reordered", "error-flat", "missing", "duplicate", "c3-one", "c3-two",
                        "changed-text", "wrong-error", "success-flat", "error-wrong-flag", "last-start"):
            mismatch = variant in mismatching or variant == "last-start"
            actual = "c3-two" if variant == "last-start" else variant
            f = self.fidelity_fixture("fidelity-" + variant, actual, placements=1 if variant == "last-start" else 3)
            label = f["label"]
            reply = self.cmd(label + ".run", ["run", f["reference"]])
            self.groups_absent(f)
            self.harness_clean(f)
            self.fidelity_page_witness(f)
            status = self.inspect_runtime(f)
            self.eq(label + ".ending", reply.get("data", {}).get("ending"), "interrupted" if mismatch else "sealed")
            self.eq(label + ".cause", reply.get("data", {}).get("cause"), "protocol_anomaly" if mismatch else None)
            self.eq(label + ".preserved-entry", status["data"].get("answer", {}).get("entries"), 1)
            exact = 2 if actual == "c3-one" else 4 if actual == "error-wrong-flag" else 3 if mismatch else 6 if variant == "error-flat" else 4 if variant in ("missing", "duplicate") else 5
            self.fidelity_record(f, exact, int(mismatch), unknown_min=2 if variant in ("missing", "duplicate") else 1)
            self.fidelity_diagnostics(f, mismatch, phase="live" if mismatch else None)
            self.check(label + ".summary-fidelity", "fidelity" in status["data"].get("summary", "").lower(), status["data"])
            if mismatch:
                self.eq(label + ".unsealed", status["data"].get("seal"), {"state": "absent", "actor": None})
                for context, data in (("run", reply["data"]), ("status", status["data"])):
                    self.check(label + "." + context + "-warning", "mismatch" in data.get("summary", "").lower(), data)
                advice = [item.get("argv") for item in status.get("next", [])]
                offers_run = [str(self.binary), "run", f["reference"]] in advice
                self.eq(label + ".continuation-advice", offers_run, variant != "last-start")
                if variant == "last-start":
                    launches = self.launch_count(f)
                    self.cmd(label + ".exhausted", ["run", f["reference"]], outcome="refused")
                    self.eq(label + ".no-extra-launch", self.launch_count(f), launches)
                if variant == "c3-two":
                    self.change_scenario(f, fidelity_variant="exact", skip_record=True, session="fidelity-resumed-session-2")
                    self.cmd(label + ".explicit-run", ["run", f["reference"]])
                    self.groups_absent(f, run=2)
                    self.fidelity_record(f, 4, 0, run=2)
                    continued = self.inspect_runtime(f, placements=2)
                    package = self.check_delivery(f, continued)
                    self.check(label + ".continuation-warning-preserved", "mismatch" in continued["data"]["summary"].lower(), continued)
                    self.close_after_delivery(f, package, placements=2, mismatch=True)
            else:
                package = self.check_delivery(f, status)
                if variant == "exact":
                    self.close_after_delivery(f, package)

    def runtime_fidelity_publication(self):
        # First show shutdown-drain behavior without a fault-injection build.
        for variant in ("late-exact", "late-mismatch"):
            f = self.fidelity_fixture("fidelity-" + variant, variant)
            reply = self.cmd(f["label"] + ".run", ["run", f["reference"]])
            self.groups_absent(f)
            self.harness_clean(f)
            self.fidelity_page_witness(f)
            late = f["witness"] / "late-echo.bin"
            self.require(f["label"] + ".late-transmitted", late.exists() and late.stat().st_size > 0, str(late))
            self.check(f["label"] + ".late-captured", late.read_bytes() in self.captured_channel(f, "stdout"), str(late))
            mismatch = variant == "late-mismatch"
            self.fidelity_record(f, 4 if mismatch else 5, int(mismatch))
            self.fidelity_diagnostics(f, mismatch, phase="drain" if mismatch else None, sealed=True)
            self.eq(f["label"] + ".seal-won", reply.get("data", {}).get("ending"), "sealed")
            status = self.inspect_runtime(f)
            package = self.check_delivery(f, status)
            if mismatch:
                self.check(f["label"] + ".sealed-warning", "mismatch" in status["data"]["summary"].lower(), status)
            self.close_after_delivery(f, package, mismatch=mismatch)
            if mismatch:
                closed = self.cmd(f["label"] + ".closed-status", ["status", f["reference"]])
                self.check(f["label"] + ".closed-warning", "mismatch" in closed["data"]["summary"].lower(), closed)
        if self.variant is None or b"STEWART_TEST_FAULT" not in self.variant.read_bytes():
            return "--variant-binary with claude-code,fault-injection is required for the fidelity publication pause"
        original = self.binary
        self.binary = self.variant
        try:
            for variant in ("paused-exact", "paused-mismatch"):
                self.fidelity_publication_pause(variant)
        finally:
            self.binary = original

    def fidelity_publication_pause(self, variant):
        f = self.fidelity_fixture("fidelity-" + variant, variant)
        label = f["label"]
        mismatch = variant == "paused-mismatch"
        faults = f["witness"] / "faults"
        faults.mkdir()
        env = dict(self.env, STEWART_TEST_FAULT="log.publish:seal=pause", STEWART_TEST_FAULT_DIR=str(faults))
        argv = [str(self.binary), "run", f["reference"], "--json"]
        stdout_path, stderr_path = f["witness"] / "run.stdout", f["witness"] / "run.stderr"
        before = snapshot(f["archive"])
        def boundary(event, **facts):
            with (f["witness"] / "publication-boundary.jsonl").open("ab") as stream:
                stream.write(compact({"event": event, "monotonic_ns": time.monotonic_ns(), **facts}) + b"\n")
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, env=env, cwd=self.cwd)
            def await_fact(predicate, seconds=12):
                until = time.monotonic() + seconds
                while process.poll() is None and time.monotonic() < until:
                    if predicate():
                        return True
                    time.sleep(0.01)
                return bool(predicate())
            try:
                self.require(label + ".paused", await_fact(lambda: bool(list(faults.glob("log.publish*.paused")))),
                             {"exit": process.poll(), "stderr": stderr_path.read_text(errors="replace")})
                submitted = [e for e in self.harness_events(f) if e.get("event") == "fidelity-submit"]
                self.require(label + ".submit-witness", len(submitted) == 1, submitted)
                group = submitted[0]["group"]
                self.eq(label + ".live-control", group_observation(group), "present")
                status = self.cmd(label + ".before-echo", ["status", f["reference"]])
                self.eq(label + ".no-seal-yet", status["data"]["seal"], {"state": "absent", "actor": None})
                (f["witness"] / "release-echo").write_bytes(b"")
                if mismatch:
                    stopped = await_fact(lambda: group_observation(group) == "absent", 8)
                    paused = list(faults.glob("log.publish*.paused"))
                    held = bool(paused) and all(not p.with_suffix(".go").exists() for p in paused)
                    boundary("mismatch-stop-before-publication", group_absent=stopped,
                             owner_alive=process.poll() is None, pause_held=held)
                    self.require(label + ".stopping-won", stopped and held and process.poll() is None,
                                 {"stopped": stopped, "held": held, "owner_exit": process.poll()})
                else:
                    self.require(label + ".exact-echo-sent", await_fact(lambda: any(
                        e.get("event") == "fidelity-held-echo-sent" for e in self.harness_events(f))), str(f["witness"]))
                    self.eq(label + ".exact-kept-model", group_observation(group), "present")
                release_fault_pauses(faults, boundary)
                process.wait(timeout=15)
            except BaseException:
                self.launch_blocked = "fidelity publication control failed; inspect retained owner/group evidence at " + str(f["witness"])
                raise
            finally:
                release_fault_pauses(faults, boundary)
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                self.save("witness/" + label + "/run-command.json", {"argv": argv, "env": env, "exit": process.returncode})
        reply = strict_loads(stdout_path.read_bytes())
        self.eq(label + ".outcome", reply.get("outcome"), "completed")
        self.eq(label + ".ending", reply.get("data", {}).get("ending"), "interrupted" if mismatch else "sealed")
        self.eq(label + ".exit", process.returncode, 5 if mismatch else 0)
        self.eq(label + ".earlier-bytes", immutable_changes(before, snapshot(f["archive"])), [])
        self.groups_absent(f)
        self.fidelity_record(f, 4 if mismatch else 5, int(mismatch))
        self.fidelity_diagnostics(f, mismatch, phase="live" if mismatch else None)
        status = self.inspect_runtime(f)
        if mismatch:
            self.eq(label + ".still-unsealed", status["data"]["seal"], {"state": "absent", "actor": None})
            run = self.audit_path(f) / "runs" / "1"
            calls = [p for p in run.glob("call-*.json") if transport_loads(p.read_bytes())["params"]["name"] == "submit"]
            self.require(label + ".submit-retained", len(calls) == 1, [p.name for p in calls])
            result = strict_loads((run / calls[0].name.replace("call-", "result-")).read_bytes())["body"]
            core = strict_loads(result["content"][0]["text"].encode())
            self.eq(label + ".publication-refused", (core.get("outcome"), core.get("reason")), ("refused", "placement_stopped"))
            self.control(label + "-gate-enforced", core.get("effects", {}).get("seal") == "none" and result.get("log_record") is None)
        else:
            self.check_delivery(f, status)

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
            for action, placements in (("positive", 3), ("close", 3), ("cancel", 3), ("signal", 3),
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
        close_process = None
        close_faults = f["witness"] / "close-faults"
        close_stdout, close_stderr = f["witness"] / "close.stdout", f["witness"] / "close.stderr"
        close_argv = [str(self.binary), "close", f["reference"], "--json"]
        close_requested = None
        before = snapshot(f["archive"])
        started = time.monotonic()
        with contextlib.ExitStack() as streams:
            stdout = streams.enter_context(stdout_path.open("wb"))
            stderr = streams.enter_context(stderr_path.open("wb"))
            process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, env=env, cwd=self.cwd)
            paused = []
            def await_fact(predicate, bound=12, owner=process):
                until = time.monotonic() + bound
                while owner.poll() is None and time.monotonic() < until:
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
                elif action in ("signal", "close"):
                    supplied = observed("submit-publication")[0]
                    model_group = supplied["group"]
                    process_record = strict_loads((self.audit_path(f) / "runs" / "1" / "process-model.json").read_bytes())
                    self.eq(label + ".group-matches-independent-harness", process_record.get("group"), model_group)
                    self.eq(label + ".group-matches-process-observation", os.getpgid(supplied["pid"]), model_group)
                    present = group_observation(model_group)
                    boundary("before-" + action, owner_pid=process.pid, owner_alive=process.poll() is None,
                             model_group=model_group, group_observation=present)
                    self.require(label + ".model-group-present-control", present == "present", present)
                    if action == "signal":
                        process.send_signal(signal.SIGTERM)
                        boundary("signal-sent", owner_pid=process.pid, signal="SIGTERM")
                        self.save("witness/" + label + "/signal.json", {"pid": process.pid, "signal": "SIGTERM",
                                  "model_group": model_group, "monotonic_ns": time.monotonic_ns()})
                    else:
                        close_faults.mkdir()
                        close_env = dict(self.env, STEWART_TEST_FAULT="log.publish:seal=pause",
                                         STEWART_TEST_FAULT_DIR=str(close_faults))
                        close_process = subprocess.Popen(close_argv,
                            stdout=streams.enter_context(close_stdout.open("wb")),
                            stderr=streams.enter_context(close_stderr.open("wb")),
                            env=close_env, cwd=self.cwd)
                        boundary("close-started", close_pid=close_process.pid, argv=close_argv)
                        def close_records():
                            return [r for p in (self.audit_path(f) / "log").glob("*.json")
                                    for r in [strict_loads(p.read_bytes())] if r.get("kind") == "close_requested"]
                        self.require(label + ".close-request-won-before-release", await_fact(close_records),
                                     str(self.audit_path(f) / "log"))
                        requests = close_records()
                        self.require(label + ".one-close-request", len(requests) == 1, requests)
                        close_requested = requests[0]
                        boundary("close-request-observed", record=close_requested)
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
                    if action == "close":
                        status = self.cmd(label + ".status-while-stopping", ["status", f["reference"]])
                        self.eq(label + ".close-has-no-seal-yet", status["data"].get("seal"),
                                {"state": "absent", "actor": None})
                        self.eq(label + ".close-waits-for-placement",
                                (status["data"].get("closure") or {}).get("unfinished_reason"), "run_still_held")
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
                if action == "close":
                    self.require(label + ".manager-seal-publication-paused",
                                 await_fact(lambda: bool(list(close_faults.glob("log.publish*.paused"))),
                                            owner=close_process),
                                 {"exit": close_process.poll(), "stderr": close_stderr.read_text(errors="replace")})
                    status = self.cmd(label + ".status-close-in-progress", ["status", f["reference"]])
                    self.eq(label + ".ended-before-manager-seal",
                            (status["data"].get("runs", {}).get("last") or {}).get("ending"), "stopped_by_close")
                    self.eq(label + ".status-close-in-progress",
                            (status["data"].get("closure") or {}).get("unfinished_reason"), "close_in_progress")
                    self.eq(label + ".manager-seal-not-yet-linked", status["data"].get("seal"),
                            {"state": "absent", "actor": None})
                    # INTERFACE 5.8 allows 30 seconds for the held active lock;
                    # this caller's bound must exceed that documented wait.
                    second = self.cmd(label + ".second-close", ["close", f["reference"]], timeout=40)
                    self.eq(label + ".second-close-in-progress",
                            second.get("data", {}).get("unfinished_reason"), "close_in_progress")
                    self.eq(label + ".second-close-no-holder", second.get("data", {}).get("holder"), None)
                    still_paused = (close_process.poll() is None and
                                    all(not p.with_suffix(".go").exists()
                                        for p in close_faults.glob("*.paused")))
                    self.control(label + "-close-in-progress",
                                 second.get("data", {}).get("unfinished_reason") == "close_in_progress"
                                 and still_paused)
                    boundary("second-close-finished", close_alive=close_process.poll() is None,
                             manager_seal_still_paused=still_paused, reply=second)
                    release_fault_pauses(close_faults, boundary)
                    close_process.wait(timeout=15)
            except BaseException:
                self.launch_blocked = ("publication control did not finish; inspect retained owner/group evidence at "
                                       + str(f["witness"]) + " before another launch")
                raise
            finally:
                release()
                release_fault_pauses(close_faults, boundary)
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                if close_process is not None:
                    try:
                        close_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        close_process.kill()
                        close_process.wait(timeout=5)
                    self.save("witness/" + label + "/close-command.json", {
                              "argv": close_argv, "env": close_env, "exit": close_process.returncode})
                self.save("witness/" + label + "/run-command.json", {"argv": argv, "env": env,
                          "exit": process.returncode, "elapsed_seconds": time.monotonic() - started,
                          "pause_files": [str(p) for p in paused]})
        reply = strict_loads(stdout_path.read_bytes())
        ending = ("sealed" if action in ("positive", "cancel") else "stopped_by_close" if action == "close"
                  else "limit_reached" if placements == 1 else "interrupted")
        cause = "signal" if action == "signal" else "placement_deadline" if action == "deadline" else None
        self.eq(label + ".outcome", reply.get("outcome"), "completed")
        self.eq(label + ".ending", reply.get("data", {}).get("ending"), ending)
        self.eq(label + ".cause", reply.get("data", {}).get("cause"), cause)
        self.eq(label + ".exit", process.returncode, 5 if ending == "interrupted" else 0)
        self.eq(label + ".retained-earlier-bytes", immutable_changes(before, snapshot(f["archive"])), [])
        self.groups_absent(f)
        status = self.inspect_runtime(f)
        if action in ("positive", "cancel"):
            package = self.check_delivery(f, status)
            if action == "positive":
                self.close_after_delivery(f, package)
        elif action == "close":
            self.eq(label + ".stopped-run-seal-effect", reply.get("effects", {}).get("seal"), "none")
            self.close_publication_result(f, close_process.returncode, strict_loads(close_stdout.read_bytes()), status)
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
            reason = "authoring_ended" if action == "close" else "placement_stopped"
            self.eq(label + ".submit-refusal", (core.get("outcome"), core.get("reason")), ("refused", reason))
            self.eq(label + ".submit-refusal-effects", {k: v for k, v in core.get("effects", {}).items() if k != "diagnostic"},
                    {"seal": "none", "raw_capture": "recorded"})
            self.eq(label + ".refusal-published-no-log-record", result.get("log_record"), None)
            self.control(label + "-stops-publication", core.get("reason") == reason
                         and core.get("effects", {}).get("seal") == "none")
            if action == "close":
                self.eq(label + ".close-refusal-data", core.get("data"), {
                    "ended_by": "close", "close_requested_at": close_requested["at"],
                    "seal": {"state": "absent", "actor": None}})
                self.eq(label + ".close-refusal-data-order", list(core.get("data", {})),
                        ["ended_by", "close_requested_at", "seal"])
        if action == "cancel":
            reentry = observed("submit-cancelled-reentry")[0]["response"]
            self.eq(label + ".later-call-completed", reentry.get("outcome"), "completed")
            self.eq(label + ".one-placement", status["data"].get("runs", {}).get("count"), 1)

    def close_publication_result(self, f, exit_code, closing, status):
        label = f["label"]
        self.eq(label + ".close-exit", exit_code, 0)
        self.eq(label + ".close-outcome", closing.get("outcome"), "completed")
        self.eq(label + ".close-effects", closing.get("effects"),
                {"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"})
        data = closing.get("data") or {}
        self.eq(label + ".close-awaits-confirmation", data.get("unfinished_reason"), "awaiting_confirmation")
        self.eq(label + ".close-runs", data.get("runs"),
                {"count": 1, "held": False, "last_ending": "stopped_by_close"})
        self.runtime_allowances(label + ".close", data, 1, f)
        records = [strict_loads(p.read_bytes()) for p in sorted((self.audit_path(f) / "log").glob("*.json"),
                                                              key=lambda p: int(p.stem))]
        selected = [r for r in records if r.get("kind") in ("close_requested", "run_ended", "seal")]
        self.eq(label + ".close-stop-seal-order", [r.get("kind") for r in selected],
                ["close_requested", "run_ended", "seal"])
        self.eq(label + ".only-manager-seal", [r["body"].get("actor") for r in selected if r["kind"] == "seal"],
                ["manager"])
        self.eq(label + ".manager-seal-has-no-auditor-invocation",
                [r["body"].get("invocation") for r in selected if r["kind"] == "seal"], [None])
        package = self.check_delivery(f, status, "manager")
        delivered = self.package_identity(package)
        launches = self.launch_count(f)
        token = data.get("confirmation")
        self.require(label + ".confirmation-token", isinstance(token, str) and token.startswith("cf1."), token)
        again = self.cmd(label + ".close-without-confirmation", ["close", f["reference"]])
        self.eq(label + ".repeat-still-awaits-confirmation", again.get("data", {}).get("unfinished_reason"),
                "awaiting_confirmation")
        done = self.cmd(label + ".confirm-close", ["close", f["reference"], "--confirm", token])
        self.eq(label + ".closed", done.get("data", {}).get("closure"), "complete")
        self.eq(label + ".confirmed-placement", done.get("data", {}).get("placement"), "confirmed")
        self.eq(label + ".preserved-manager-attribution", done.get("data", {}).get("seal", {}).get("actor"), "manager")
        self.eq(label + ".package-unchanged", self.package_identity(package), delivered)
        self.eq(label + ".one-package", [p.name for p in sorted(package.parent.iterdir())], [package.name])
        self.eq(label + ".no-launch-during-close", self.launch_count(f), launches)

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

    def runtime_captured_accounting(self):
        observations = {}
        for variant in ("missing", "duplicate", "checkpoint"):
            f = self.fixture("captured-accounting-" + variant, scenario="captured-accounting")
            label = f["label"]
            self.change_scenario(f, accounting_variant=variant)
            self.accept(f)
            reply = self.cmd(label + ".run", ["run", f["reference"]])
            self.groups_absent(f)
            self.eq(label + ".ending", reply.get("data", {}).get("ending"), "sealed")
            events = self.harness_clean(f)
            frames = [e["value"] for e in events if e["event"] == "output"]
            assistants = [v for v in frames if v.get("type") == "assistant"]
            repeats = 2 if variant == "duplicate" else 1
            expected_frames = [c5_partial_frame(label + "-session-1", n) for _ in range(repeats) for n in range(4)]
            if variant == "checkpoint":
                expected_frames += [c5_partial_frame(label + "-session-1", 4, later=True)]
            self.eq(label + ".exact-partial-projection", assistants, expected_frames)
            cap = copy.deepcopy(C5_CAP)
            cap["session_id"] = label + "-session-1"
            self.eq(label + ".captured-cap-shape", [v for v in frames if v.get("type") == "user"], [cap])
            self.eq(label + ".stdout-capture", self.captured_channel(f, "stdout").hex(),
                    b"".join(bytes.fromhex(e["raw_hex"]) for e in events if e["event"] == "output").hex())
            shaped, contents = self.message_contents(events)
            self.eq(label + ".input-shape", shaped, True)
            self.eq(label + ".cap-is-not-service-input", contents,
                    [f["body"].decode()] + ([REMINDER] if variant == "checkpoint" else []))
            self.eq(label + ".input-capture", self.captured_channel(f, "input").hex(),
                    b"".join(bytes.fromhex(e["raw_hex"]) for e in events if e["event"] == "input").hex())
            after_cap = [e["response"] for e in events if e["event"] == "accounting-after-cap"]
            self.require(label + ".cap-reentry", len(after_cap) == 1, after_cap)
            self.eq(label + ".cap-spends-no-notice", after_cap[0].get("data", {}).get("notices_used"),
                    {"reminder": False, "near_limit": False})
            self.eq(label + ".cap-keeps-authoring-open", after_cap[0].get("data", {}).get("authoring"),
                    {"state": "open", "ended_by": None})
            status = self.inspect_runtime(f, terminal=variant == "checkpoint")
            reported = (dict(CHECKPOINTS[1]["usage"], harness_turns=CHECKPOINTS[1]["num_turns"])
                        if variant == "checkpoint" else None)
            expected = {"runtime": "claude-code/1", "placements": 1, "unknown_intervals": 1,
                        "stopped": 1, "reported_placements": 1 if reported else 0,
                        "reported_main_loop": reported, "provider_completeness": "unverified"}
            self.eq(label + ".usage", self.usage_of(status), expected)
            self.eq(label + ".run-usage", reply.get("data", {}).get("usage"), expected)
            checkpoints = sorted((self.audit_path(f) / "runs/1").glob("runtime-usage-*.json"),
                                 key=lambda p: int(p.stem.rsplit("-", 1)[1]))
            self.require(label + ".usage-records-present", bool(checkpoints))
            records = [strict_loads(p.read_bytes()) for p in checkpoints]
            # These records include stopping observations; their number is not
            # the number of model reports. Check the retained accounting itself.
            self.eq(label + ".final-usage-record", records[-1], expected)
            self.check(label + ".no-partial-reports",
                       all(r.get("reported_main_loop") in (None, reported) for r in records), records)
            self.eq(label + ".notice-transmissions", reply.get("data", {}).get("notices"),
                    [{"type": "reminder", "sent": "sent"}] if reported else [])
            observations[variant] = self.usage_of(status)
            self.close_after_delivery(f, self.check_delivery(f, status))
        self.control("captured-partials-stay-unknown",
                     observations["missing"]["reported_main_loop"] is None
                     and observations["missing"]["unknown_intervals"] == 1)
        self.control("duplicated-partials-add-no-consumption", observations["duplicate"] == observations["missing"])
        self.control("valid-checkpoint-is-distinct-from-partials",
                     observations["checkpoint"]["reported_main_loop"] ==
                     dict(CHECKPOINTS[1]["usage"], harness_turns=CHECKPOINTS[1]["num_turns"])
                     and observations["checkpoint"]["unknown_intervals"] == 1)

    def runtime_tool_names(self):
        for variant, name in (("prefixed", "mcp__stewart__record_account"),
                              ("unprefixed", "record_account"), ("unlisted", "mcp__stewart__not_pinned")):
            f = self.fixture("tool-name-" + variant, scenario="tool-name", timeout=20)
            label = f["label"]
            self.change_scenario(f, assistant_tool=name)
            self.accept(f)
            reply = self.cmd(label + ".run", ["run", f["reference"]])
            self.groups_absent(f)
            events = self.harness_clean(f)
            selected = [e for e in events if e["event"] == "output" and e["value"].get("type") == "assistant"]
            self.require(label + ".assistant-frame-observed", len(selected) == 1, selected)
            block = selected[0]["value"]["message"]["content"][0]
            self.eq(label + ".named-tool", block.get("name"), name)
            self.eq(label + ".same-arguments", block.get("input"), {"text": ACCOUNT})
            self.check(label + ".assistant-frame-transmitted", any(e["event"] == "output-transmitted"
                       and e["sha256"] == sha(bytes.fromhex(selected[0]["raw_hex"])) for e in events))
            self.eq(label + ".stdout-capture", self.captured_channel(f, "stdout").hex(),
                    b"".join(bytes.fromhex(e["raw_hex"]) for e in events if e["event"] == "output").hex())
            status = self.inspect_runtime(f)
            if variant == "prefixed":
                self.eq(label + ".ending", reply.get("data", {}).get("ending"), "sealed")
                calls = [e["value"]["params"] for e in events if e["event"] == "rpc-send"
                         and e["value"].get("method") == "tools/call"]
                self.eq(label + ".bare-mcp-positive", [c for c in calls if c["name"] == "record_account"],
                        [{"name": "record_account", "arguments": {"text": ACCOUNT}}])
                self.close_after_delivery(f, self.check_delivery(f, status))
            else:
                data = reply.get("data") or {}
                self.eq(label + ".ending", data.get("ending"), "interrupted")
                self.eq(label + ".validation-cause", data.get("cause"), "protocol_anomaly")
                self.eq(label + ".no-entry", status["data"].get("answer"), {"revision": 0, "entries": 0})
                self.eq(label + ".no-seal", status["data"].get("seal"), {"state": "absent", "actor": None})
                self.control(label + "-stopped", data.get("ending") == "interrupted"
                             and data.get("cause") == "protocol_anomaly")

    def runtime_near_limit(self):
        import answer_witness as aw
        partial = authoring_arguments("c4-partial-account")
        expected = aw.answer_json(1, [aw.Entry("e1", 1, "record_account", partial["label"],
                                              partial["text"].encode())])
        # The same 16-second observation window crosses the short placement's
        # near-limit region, but not the long placement's. Both peers record the
        # same partial account before waiting and submit only after the window.
        for label, seconds in (("near-limit-submit", 20), ("near-limit-long", 200),
                               ("near-limit-continuation", 20)):
            f = self.fixture(label, scenario="near-limit", timeout=seconds)
            continuing = label == "near-limit-continuation"
            self.change_scenario(f, observe_seconds=16, interrupt_after_notice=continuing, captured_partial=True)
            self.accept(f)
            first = self.cmd(label + ".run-1", ["run", f["reference"]])
            self.groups_absent(f)
            self.eq(label + ".first-ending", first.get("data", {}).get("ending"),
                    "interrupted" if continuing else "sealed")
            self.inspect_near_limit(f, first, run=1, expected=0 if seconds == 200 else 1)
            if continuing:
                self.check(label + ".interruption-before-deadline",
                           first.get("data", {}).get("cause") != "placement_deadline", first.get("data"))
                status = self.inspect_runtime(f)
                self.eq(label + ".unsubmitted-seal", status["data"].get("seal"),
                        {"state": "absent", "actor": None})
                self.eq(label + ".preserved-partial-answer", status["data"].get("answer"),
                        {"revision": 1, "entries": 1})
                self.change_scenario(f, skip_record=True, interrupt_after_notice=False,
                                     session=label + "-session-2")
                second = self.cmd(label + ".run-2", ["run", f["reference"]])
                self.groups_absent(f, run=2)
                self.eq(label + ".continued-ending", second.get("data", {}).get("ending"), "sealed")
                self.inspect_near_limit(f, second, run=2, expected=0)
            placements = 2 if continuing else 1
            package = self.check_delivery(f, self.inspect_runtime(f, placements=placements), expected=expected)
            payload = self.audit_path(f) / "payload/e1.v1.bin"
            self.eq(label + ".captured-partial-retained", payload.read_bytes(), partial["text"].encode())
            calls = [e["value"]["params"]["arguments"] for e in self.harness_events(f)
                     if e["event"] == "rpc-send" and e["value"].get("params", {}).get("name") == "record_account"]
            self.eq(label + ".captured-partial-once", calls, [partial])
            self.close_after_delivery(f, package, placements=placements)
        self.control("near-limit-crosses-short-not-long-deadline",
                     self.near_counts.get(("near-limit-submit", 1)) == 1
                     and self.near_counts.get(("near-limit-long", 1)) == 0)
        self.control("near-limit-allowance-survives-continuation",
                     self.near_counts.get(("near-limit-continuation", 1)) == 1
                     and self.near_counts.get(("near-limit-continuation", 2)) == 0)

    def inspect_near_limit(self, f, reply, run, expected):
        label = f["label"] + ".notice-%d" % run
        events = self.harness_clean(f)
        models = [e for e in events if e["event"] == "launch" and e["role"] == "model"]
        self.require(label + ".model-count", len(models) == run, len(models))
        pid = models[-1]["pid"]
        current = [e for e in events if e["pid"] == pid]
        shaped, contents = self.message_contents(current)
        self.eq(label + ".input-shape", shaped, True)
        notices = [e for e in current if e["event"] == "input"
                   and near_limit_values(e["value"].get("message", {}).get("content")) is not None]
        count_ok = self.eq(label + ".notice-count", len(notices), expected)
        if not hasattr(self, "near_counts"):
            self.near_counts = {}
        self.near_counts[(f["label"], run)] = len(notices) if count_ok else None
        expected_contents = [f["body"].decode()] + ([CONTINUATION] if run > 1 else [])
        expected_contents += [e["value"]["message"]["content"] for e in notices]
        self.eq(label + ".only-expected-inputs", contents, expected_contents)
        self.eq(label + ".input-capture", self.captured_channel(f, "input", run).hex(),
                b"".join(bytes.fromhex(e["raw_hex"]) for e in current if e["event"] == "input").hex())
        windows = [e for e in current if e["event"] == "near-limit-window"]
        self.require(label + ".complete-window", len(windows) == 2, windows)
        self.eq(label + ".window-events", [e.get("phase") for e in windows], ["start", "end"])
        elapsed = (windows[1]["monotonic_ns"] - windows[0]["monotonic_ns"]) / 1_000_000_000
        interrupted = f["label"] == "near-limit-continuation" and run == 1
        self.eq(label + ".window-ended-by", windows[1].get("ended_by"), "notice" if interrupted else "timeout")
        if interrupted:
            self.require(label + ".notice-triggered-exit", len(notices) == 1, notices)
            self.check(label + ".receipt-before-interruption",
                       notices[0]["monotonic_ns"] < windows[1]["monotonic_ns"], windows)
        else:
            self.check(label + ".observed-full-window", elapsed >= 16, elapsed)
        submits = [e for e in current if e["event"] == "rpc-send"
                   and e["value"].get("params", {}).get("name") == "submit"]
        self.eq(label + ".explicit-submit-count", len(submits), 0 if interrupted else 1)
        self.eq(label + ".deliberate-interruption-count",
                sum(e["event"] == "deliberate-interruption" for e in current), 1 if interrupted else 0)
        if submits:
            self.check(label + ".submit-after-window",
                       submits[0]["monotonic_ns"] > windows[1]["monotonic_ns"], submits[0])
            self.check(label + ".notice-before-submit",
                       all(e["monotonic_ns"] < submits[0]["monotonic_ns"] for e in notices), notices)
        logs = [(p, strict_loads(p.read_bytes())) for p in (self.audit_path(f) / "log").glob("*.json")]
        near_records = [(p, r) for p, r in logs if r.get("kind") == "notice"
                        and r["body"].get("type") == "near_limit"]
        self.eq(label + ".audit-wide-claim-count", len(near_records),
                0 if f["label"] == "near-limit-long" else 1)
        this_run = [(p, r) for p, r in near_records if r["body"].get("run") == run]
        self.eq(label + ".this-run-claim-count", len(this_run), expected)
        for event, (path, record) in zip(notices, this_run):
            content = event["value"]["message"]["content"]
            values = near_limit_values(content)
            self.eq(label + ".remaining-starts", values["placements"], f["limits"]["max_placements"] - run)
            self.check(label + ".remaining-time-in-bounds",
                       0 <= values["seconds"] <= f["limits"]["placement_timeout_seconds"], values)
            self.eq(label + ".logged-text", record["body"].get("text"), content)
            self.eq(label + ".logged-remaining", record["body"].get("remaining"),
                    {"runtime": "claude-code/1", **values})
            ended = [r for _, r in logs if r["kind"] == "run_ended" and r["body"].get("run") == run]
            self.require(label + ".ending-record", len(ended) == 1, ended)
            self.eq(label + ".notice-transmission-record", ended[0]["body"].get("notices"),
                    [{"type": "near_limit", "record": "log/" + path.name, "sent": "sent"}])
        self.eq(label + ".run-notices", reply.get("data", {}).get("notices"),
                [{"type": "near_limit", "sent": "sent"}] if expected else [])
        reentries = [e["response"] for e in current if e["event"] == "near-limit-reentry"]
        self.require(label + ".reentry-observed", len(reentries) == 1, reentries)
        data = reentries[0].get("data") or {}
        self.eq(label + ".notices-used", data.get("notices_used"),
                {"reminder": False, "near_limit": f["label"] != "near-limit-long"})
        self.eq(label + ".notice-does-not-seal", data.get("seal"), {"state": "absent", "actor": None})
        self.eq(label + ".notice-does-not-edit", data.get("revision"), 1)
        self.eq(label + ".no-duplicate-account", len(data.get("entries", [])), 1)
        entry = (data.get("entries") or [{}])[0]
        partial = authoring_arguments("c4-partial-account")
        self.eq(label + ".preserved-account", entry.get("preview"), partial["text"].encode()[:200].decode())
        self.eq(label + ".partial-preview-complete", entry.get("preview_complete"), False)
        self.eq(label + ".partial-size", entry.get("size"), 708)
        self.eq(label + ".partial-label", entry.get("label"), "Overall checkpoint")
        claims = [r for _, r in logs if r["kind"] == "notice" and r["body"].get("type") == "reminder"]
        self.eq(label + ".no-reminder-spent", claims, [])

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
        fidelity = self.audit_path(f) / "runs" / "1" / "runtime-fidelity.json"
        self.eq(f["label"] + ".missing-final-fidelity", fidelity.exists(), False)
        summary = status_reply["data"].get("summary", "").lower()
        self.check(f["label"] + ".missing-fidelity-is-unknown", "fidelity" in summary and "unknown" in summary, summary)
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

    # -- scripted MCP sequences (specification-derived calls, outer expectations) -------------

    def scripted_fixture(self, label, family="open-inquiry", *, extra=None, empty=False, script=(), end=None):
        f = self.fixture(label, family, scenario="scripted")
        if empty:
            (f["folder"] / "materials" / "report.txt").unlink()
            f["materials"] = {}
        for name, data in (extra or {}).items():
            for base in (f["folder"], f["witness"] / "supplied"):
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            f["materials"][name] = data
        self.change_scenario(f, script=list(script), script_end=end)
        return f

    def run_script(self, f, suffix="run", run=1):
        reply = self.cmd(f["label"] + "." + suffix, ["run", f["reference"]], outcome=None)
        self.groups_absent(f, run=run)
        events = self.harness_clean(f)
        steps = {}
        for event in events:
            if event["event"] == "script-step":
                steps.setdefault(event["label"], []).append(event)
        return reply, events, steps

    def check_tools_list(self, f, events):
        """CONTRACT, arrangement and observation: the fixed tools/list result is the pinned
        MCP mapping, in family order, each tool's members exactly name, description,
        inputSchema, _meta."""
        label = f["label"] + ".tools-list"
        asked = [e["value"]["id"] for e in events if e["event"] == "rpc-send" and e["value"].get("method") == "tools/list"]
        replies = {e["value"].get("id"): e for e in events if e["event"] == "rpc-receive"}
        self.require(label + ".observed", bool(asked) and all(i in replies for i in asked), asked)
        want = json.loads(mcp_tools(f["tools"]))
        for identity in asked:
            node = parse(bytes.fromhex(replies[identity]["raw_hex"])).get("result")
            tools = node.get("tools") if node is not None else None
            self.eq(label + ".value", tools.value() if tools is not None else None, want)
            self.eq(label + ".member-order", [item.keys() for item in tools.items] if tools is not None else None,
                    [["name", "description", "inputSchema", "_meta"]] * len(want))

    def check_package_bytes(self, f, status, entries, revision, actor="auditor"):
        """The delivered package against independently built members (INTERFACE 8.2;
        QUESTION-FORMS answer and rendering)."""
        import answer_witness as aw
        label = f["label"] + ".package"
        answer = aw.answer_json(revision, entries)
        package = self.check_delivery(f, status, actor, expected=answer)
        rendering = aw.render(entries)
        self.eq(label + ".rendering", (package / "answer.md").read_bytes().decode(), rendering.decode())
        ids = parse_reference(f["reference"]) or {}
        seal = status["data"].get("seal") or {}
        manifest = aw.manifest(ids.get("audit"), ids.get("store"), f["family"] + "/1", sha(self.binary.read_bytes()),
                               actor, seal.get("sealed_at"), revision, aw.members(entries, answer, rendering))
        self.eq(label + ".manifest", (package / "manifest.json").read_bytes().decode(), manifest.decode())
        artifacts = {e.member: e.data for e in entries if e.kind == "record_artifact"}
        self.eq(label + ".members", sorted(p.name for p in package.iterdir()),
                sorted(["manifest.json", "answer.json", "answer.md"] + list(artifacts)))
        for member, data in artifacts.items():
            self.eq(label + "." + member, (package / member).read_bytes().hex(), data.hex())
        return package

    def check_prepare(self, f, label, data, kinds, revision):
        counts, notices = expected_prepare(f["family"], kinds)
        self.eq(label + ".keys", list(data), PREPARE_KEYS)
        self.eq(label + ".family", data.get("family"), f["family"] + "/1")
        self.eq(label + ".revision", (data.get("revision"), data.get("entry_count")), (revision, len(kinds)))
        self.eq(label + ".counts", data.get("counts"), counts)
        self.eq(label + ".counts-order", list(data.get("counts") or {}), list(counts))
        self.eq(label + ".notices", notice_pairs(data), notices)

    def runtime_family_sequences(self):
        for family in FAMILY_TEXT:
            self.family_sequence(family)
            self.family_empty_answer(family)
        self.family_empty_materials()

    def family_sequence(self, family):
        import answer_witness as aw
        a = SCENARIO_MATERIALS["materials/a.py"]
        script = [script_step("prepare-empty", "prepare"),
                  script_step("rendering-empty", "read", {"source": {"$ref": ["prepare-empty", "data", "prepared"],
                                                                      "$append": "/rendering"}}, follow=True),
                  script_step("selection-empty", "read", {"source": {"$ref": ["prepare-empty", "data", "prepared"],
                                                                      "$append": "/selection"}}, follow=True),
                  script_step("inability", "record_account", {"text": INABILITY})]
        aux = {"comparison": ("record_observation", "Only one alternative is described."),
               "inquiry-framing": ("record_working_question", "The question is precise; it is my working question.")}
        if family in aux:
            script.append(script_step("aux", aux[family][0], {"text": aux[family][1]}))
        script.append(script_step("prepare-partial", "prepare"))
        cases = citation_cases(a) if family == "open-inquiry" else []
        if cases:
            script.append(script_step("read-a", "read", {"source": "materials/a.py"}, follow=True))
            for lab, citations, _ in cases:
                text = PROSE if lab == "prose" else "Citation case %s." % lab
                script.append(script_step("cite-" + lab, "record_observation", {"text": text, "citations": citations}))
        script += [script_step("same-1", "record_observation", {"text": "Same words.", "label": "same"}),
                   script_step("same-2", "record_observation", {"text": "Same words.", "label": "same"}),
                   script_step("delete", "delete", {"entry": {"$ref": ["same-2", "data", "entry"]}}),
                   script_step("delete-again", "delete", {"entry": {"$ref": ["same-2", "data", "entry"]}}),
                   script_step("prepare-final", "prepare"),
                   script_step("selection-final", "read", {"source": {"$ref": ["prepare-final", "data", "prepared"],
                                                                      "$append": "/selection"}}, follow=True),
                   script_step("rendering-final", "read", {"source": {"$ref": ["prepare-final", "data", "prepared"],
                                                                      "$append": "/rendering"}}, follow=True),
                   script_step("submit", "submit", {"prepared": {"$ref": ["prepare-final", "data", "prepared"]},
                                                    "confirm": True}, final=True)]
        f = self.scripted_fixture("family-sequence-" + family, family, extra=SCENARIO_MATERIALS, script=script)
        label = f["label"]
        self.accept(f)
        reply, events, steps = self.run_script(f)
        sources = dict(f["materials"], question=f["body"])

        def core(name):
            return (steps.get(name) or [{}])[0].get("core") or {}

        def pages(name):
            got = [step_page_bytes(e) for e in steps.get(name) or []]
            return b"".join(got) if got and None not in got else None

        def outcome(name):
            c = core(name)
            return (c.get("outcome"), c.get("reason"))

        self.require(label + ".all-steps", all(s["label"] in steps for s in script if not s.get("final")),
                     sorted(set(s["label"] for s in script) - set(steps)))
        self.check_prepare(f, label + ".prepare-empty", core("prepare-empty").get("data") or {}, [], 0)
        self.check(label + ".prepare-empty.no-sealer", not {"seal", "sealer"} & set(core("prepare-empty").get("data") or {}),
                   core("prepare-empty"))
        self.eq(label + ".rendering-empty", pages("rendering-empty"), aw.EMPTY_RENDERING)
        self.eq(label + ".selection-empty", pages("selection-empty"), aw.answer_json(0, []))
        entries, kinds, revision, created = [], [], 0, 0

        def added(name, kind, text, citations=(), label_=""):
            nonlocal revision, created
            revision += 1
            created += 1
            data = core(name).get("data") or {}
            ident = "e%d" % created
            self.eq(label + "." + name, (outcome(name), data.get("id"), data.get("version"), data.get("revision")),
                    (("completed", None), ident, 1, revision))
            entries.append(aw.Entry(ident, 1, kind, label_, text.encode(), list(citations)))
            kinds.append(kind)
            return data

        added("inability", "record_account", INABILITY)
        if family in aux:
            added("aux", aux[family][0], aux[family][1])
        self.check_prepare(f, label + ".prepare-partial", core("prepare-partial").get("data") or {}, kinds, revision)
        if cases:
            read_pages = steps.get("read-a") or []
            page_cite = ((read_pages[0].get("core") or {}).get("data") or {}).get("cite") if read_pages else None
            self.eq(label + ".read-a.cite", page_cite, {"source": "materials/a.py", "start": 0, "end": len(a)})
            for lab, citations, reason in cases:
                name = "cite-" + lab
                resolved = [page_cite] if lab == "read-cite" else citations
                if reason is None:
                    want = [aw.record_citation(c, sources) for c in resolved]
                    data = added(name, "record_observation", PROSE if lab == "prose" else "Citation case %s." % lab, want)
                    self.eq(label + "." + name + ".citations", data.get("citations"), want)
                else:
                    c = core(name)
                    self.eq(label + "." + name, (c.get("outcome"), c.get("reason"), (c.get("effects") or {}).get("answer")),
                            ("refused", reason, "unchanged"))
                    if lab == "ambiguous-quote":
                        found = []
                        for value in iter_values(c.get("data")):
                            if isinstance(value, list) and value and all(isinstance(x, dict) and
                                                                         {"source", "start", "end"} <= set(x) for x in value):
                                found = value
                                break
                        self.eq(label + "." + name + ".occurrences",
                                [(x.get("source"), x.get("start"), x.get("end")) for x in found],
                                [("materials/a.py", o, o + 3) for o in aw.occurrences(a, b"(r)")[:8]])
            self.control("family-refused-citation-creates-no-entry",
                         all(outcome("cite-" + lab)[0] == "refused" for lab, _, reason in cases if reason))
        first = added("same-1", "record_observation", "Same words.", label_="same")
        self.check(label + ".same-1.no-label-notice", "label_duplicate" not in json.dumps(first.get("notices")), first)
        second = added("same-2", "record_observation", "Same words.", label_="same")
        self.check(label + ".same-2.label-duplicate", "label_duplicate" in json.dumps(second.get("notices")), second)
        removed = {"id": entries[-1].id, "version": 1}
        entries.pop()
        kinds.pop()
        revision += 1
        d1, d2 = core("delete"), core("delete-again")
        self.eq(label + ".delete", (d1.get("outcome"), (d1.get("data") or {}).get("removed"),
                                    (d1.get("data") or {}).get("already_removed"), (d1.get("data") or {}).get("revision")),
                ("completed", removed, False, revision))
        self.eq(label + ".delete-again", (d2.get("outcome"), (d2.get("data") or {}).get("removed"),
                                          (d2.get("data") or {}).get("already_removed"),
                                          (d2.get("data") or {}).get("revision"), (d2.get("effects") or {}).get("answer")),
                ("completed", removed, True, revision, "unchanged"))
        self.check_prepare(f, label + ".prepare-final", core("prepare-final").get("data") or {}, kinds, revision)
        self.eq(label + ".selection-final", pages("selection-final"), aw.answer_json(revision, entries))
        self.eq(label + ".rendering-final", pages("rendering-final"), aw.render(entries))
        self.eq(label + ".ending", (reply.get("data") or {}).get("ending"), "sealed")
        self.check_tools_list(f, events)
        status = self.inspect_runtime(f)
        package = self.check_package_bytes(f, status, entries, revision)
        self.close_after_delivery(f, package)

    def family_empty_answer(self, family):
        script = [script_step("prepare", "prepare"),
                  script_step("submit", "submit", {"prepared": {"$ref": ["prepare", "data", "prepared"]},
                                                   "confirm": True}, final=True)]
        f = self.scripted_fixture("family-empty-answer-" + family, family, script=script)
        self.accept(f)
        reply, events, steps = self.run_script(f)
        data = ((steps.get("prepare") or [{}])[0].get("core") or {}).get("data") or {}
        self.check_prepare(f, f["label"] + ".prepare", data, [], 0)
        self.eq(f["label"] + ".ending", (reply.get("data") or {}).get("ending"), "sealed")
        self.check_tools_list(f, events)
        self.check_package_bytes(f, self.inspect_runtime(f), [], 0)

    def family_empty_materials(self):
        import answer_witness as aw
        text = "No materials were selected, so nothing here is established from them.\n"
        script = [script_step("list", "list", follow=True),
                  script_step("artifact", "record_artifact", {"label": "note", "text": text}),
                  script_step("prepare", "prepare"),
                  script_step("submit", "submit", {"prepared": {"$ref": ["prepare", "data", "prepared"]},
                                                   "confirm": True}, final=True)]
        f = self.scripted_fixture("family-empty-materials", empty=True, script=script)
        label = f["label"]
        self.accept(f)
        reply, events, steps = self.run_script(f)
        listed = ((steps.get("list") or [{}])[0].get("core") or {})
        data = listed.get("data") or {}
        self.eq(label + ".list", (listed.get("outcome"), data.get("materials"), data.get("returned"), data.get("total"),
                                  data.get("complete")), ("completed", [], 0, 0, True))
        made = ((steps.get("artifact") or [{}])[0].get("core") or {})
        self.eq(label + ".artifact", (made.get("outcome"), (made.get("data") or {}).get("id"),
                                      (made.get("data") or {}).get("encoding")), ("completed", "e1", "utf-8"))
        # 7.4: artifacts fill no section, so every expected section is unfilled and the
        # selection is not empty.
        self.check_prepare(f, label + ".prepare", ((steps.get("prepare") or [{}])[0].get("core") or {}).get("data") or {},
                           ["record_artifact"], 1)
        self.eq(label + ".ending", (reply.get("data") or {}).get("ending"), "sealed")
        entry = aw.Entry("e1", 1, "record_artifact", "note", text.encode(), encoding="utf-8")
        self.check_package_bytes(f, self.inspect_runtime(f), [entry], 1)

    def runtime_read_search(self):
        import answer_witness as aw
        multi = b"zz" + ("€" * 30000).encode()
        extra = {"materials/multi.txt": multi, "materials/hits.txt": b"aaa\n" * 200 + b"abc\n",
                 "materials/few.txt": b"one aa here\n"}
        scope = ["question"] + sorted(list(extra) + ["materials/report.txt"], key=lambda n: n.encode())
        script = [script_step("read-multi", "read", {"source": "materials/multi.txt"}, follow=True),
                  script_step("start-mid", "read", {"source": "materials/multi.txt", "start": 3}),
                  script_step("start-past", "read", {"source": "materials/multi.txt", "start": len(multi) + 1}),
                  script_step("start-end", "read", {"source": "materials/multi.txt", "start": len(multi)}),
                  script_step("search-hits", "search", {"text": "aa", "sources": ["materials/hits.txt"]}, follow=True),
                  script_step("search-default", "search", {"text": "aa"}, follow=True),
                  script_step("search-explicit", "search", {"text": "aa", "sources": scope}, follow=True),
                  script_step("search-aaa", "search", {"text": "aaa", "sources": ["materials/hits.txt"]}, follow=True),
                  script_step("search-absent", "search", {"text": "not present anywhere"}, follow=True),
                  script_step("search-1025", "search", {"text": "q" * 1025}),
                  script_step("search-1024", "search", {"text": "q" * 1024}),
                  script_step("read-question", "read", {"source": "question"}, follow=True),
                  script_step("list", "list", follow=True),
                  script_step("prepare", "prepare"),
                  script_step("submit", "submit", {"prepared": {"$ref": ["prepare", "data", "prepared"]},
                                                   "confirm": True}, final=True)]
        f = self.scripted_fixture("read-search", extra=extra, script=script)
        label = f["label"]
        self.accept(f)
        reply, events, steps = self.run_script(f)
        sources = dict(f["materials"], question=f["body"])

        def cores(name):
            return [e.get("core") or {} for e in steps.get(name) or []]

        def witness_hits(text, names):
            return [{"source": s, "start": o, "end": o + len(text.encode()), "line": aw.line_of(sources[s], o)}
                    for s in names for o in aw.occurrences(sources[s], text.encode())]

        def hits_of(name):
            out = []
            for c in cores(name):
                out += [{k: h.get(k) for k in ("source", "start", "end", "line")}
                        for h in ((c.get("data") or {}).get("hits") or [])]
            return out

        pages = steps.get("read-multi") or []
        ranges = [((e.get("core") or {}).get("data") or {}).get("range") for e in pages]
        self.eq(label + ".read.ranges", ranges, [list(r) for r in aw.read_pages(multi)])
        got = [step_page_bytes(e) for e in pages]
        self.eq(label + ".read.bytes", b"".join(got).hex() if got and None not in got else None, multi.hex())
        for index, event in enumerate(pages):
            data = (event.get("core") or {}).get("data") or {}
            start, end = data.get("range") or (None, None)
            self.eq(label + ".read.page-%d" % index, (data.get("cite"), data.get("lines"), data.get("complete")),
                    ({"source": "materials/multi.txt", "start": start, "end": end},
                     aw.lines_span(multi, start, end) if isinstance(start, int) else None, index == len(pages) - 1))
        mid = (cores("start-mid") or [{}])[0]
        mid_ints = [v for v in iter_values(mid.get("data")) if type(v) is int]
        self.eq(label + ".range.mid-codepoint", (mid.get("outcome"), mid.get("reason"), 2 in mid_ints and 5 in mid_ints),
                ("refused", "range_invalid", True))
        past = (cores("start-past") or [{}])[0]
        self.eq(label + ".range.past-end", (past.get("outcome"), past.get("reason")), ("refused", "range_invalid"))
        at_end = (steps.get("start-end") or [{}])[0]
        data = (at_end.get("core") or {}).get("data") or {}
        blocks = ((at_end.get("response") or {}).get("result") or {}).get("content") or []
        self.eq(label + ".range.at-end", ((at_end.get("core") or {}).get("outcome"), data.get("range"), data.get("complete"),
                                          data.get("lines"), data.get("cite"), data.get("text"), len(blocks)),
                ("completed", [len(multi), len(multi)], True, None, None, "", 1))
        self.control("read-start-inside-code-point-refused", mid.get("reason") == "range_invalid")
        hits = cores("search-hits")
        self.eq(label + ".search.hits", hits_of("search-hits"), witness_hits("aa", ["materials/hits.txt"]))
        self.check(label + ".search.page-bound", all(len((c.get("data") or {}).get("hits") or []) <= 128 for c in hits),
                   [len((c.get("data") or {}).get("hits") or []) for c in hits])
        self.eq(label + ".search.completion", [(c.get("data") or {}).get("complete") for c in hits],
                [False] * (len(hits) - 1) + [True])
        self.check(label + ".search.cursors", len(hits) > 1 and all(
            any(n.get("tool") == "search" and str((n.get("input") or {}).get("cursor", "")).startswith("sc.")
                for n in c.get("next") or []) for c in hits[:-1]), [c.get("next") for c in hits])
        self.check(label + ".search.cites", all(h.get("cite") == {"source": h.get("source"), "start": h.get("start"),
                                                                   "end": h.get("end")}
                                                for c in hits for h in (c.get("data") or {}).get("hits") or []), "cite")
        self.eq(label + ".search.default-scope", hits_of("search-default"), witness_hits("aa", scope))
        self.eq(label + ".search.scope-stated", ((cores("search-default") or [{}])[0].get("data") or {}).get("scope"), scope)
        self.eq(label + ".search.invariance.explicit-scope", hits_of("search-explicit"), hits_of("search-default"))
        self.eq(label + ".search.differing.aaa", hits_of("search-aaa"), witness_hits("aaa", ["materials/hits.txt"]))
        absent = cores("search-absent")
        self.eq(label + ".search.absent", (hits_of("search-absent"), (absent[-1].get("data") or {}).get("complete")
                                           if absent else None), ([], True))
        self.eq(label + ".search.text-bounds", [((cores(n) or [{}])[0]).get("outcome") for n in ("search-1025", "search-1024")],
                ["refused", "completed"])
        question = [step_page_bytes(e) for e in steps.get("read-question") or []]
        self.eq(label + ".read.question", b"".join(question).hex() if question and None not in question else None,
                f["body"].hex())
        listed = cores("list")
        index = fixture_material_index(f["materials"])
        self.eq(label + ".list", [m for c in listed for m in (c.get("data") or {}).get("materials") or []],
                [{"source": row["name"], "size": row["size"], "lines": row["lines"]} for row in index["files"]])
        self.eq(label + ".list.complete", [((c.get("data") or {}).get("total"), (c.get("data") or {}).get("complete"))
                                           for c in listed[-1:]], [(len(index["files"]), True)])
        self.eq(label + ".ending", (reply.get("data") or {}).get("ending"), "sealed")
        self.check_package_bytes(f, self.inspect_runtime(f), [], 0)

    def runtime_identity_across_placements(self):
        import answer_witness as aw
        note = {"text": "The same words are recorded again.", "label": "same"}
        first = [script_step("first", "record_account", note, id="identity-same")]
        f = self.scripted_fixture("identity-across-placements", script=first, end="exit")
        label = f["label"]
        self.accept(f)
        reply, _, steps = self.run_script(f, "run-1")
        one = ((steps.get("first") or [{}])[0].get("core") or {})
        self.eq(label + ".first", (one.get("outcome"), (one.get("data") or {}).get("id")), ("completed", "e1"))
        self.eq(label + ".first-ending", (reply.get("data") or {}).get("ending"), "interrupted")
        second = [script_step("again", "record_account", note, id="identity-same"),
                  script_step("duplicate", "record_account", note, id="identity-same"),
                  script_step("fresh-id", "record_account", note, id="identity-fresh"),
                  script_step("reused-ping", None, method="ping", id="identity-fresh"),
                  script_step("prepare", "prepare"),
                  script_step("submit", "submit", {"prepared": {"$ref": ["prepare", "data", "prepared"]},
                                                   "confirm": True}, final=True)]
        self.change_scenario(f, script=second, script_end=None, session=label + "-session-2")
        reply, _, steps = self.run_script(f, "run-2", run=2)

        def step(name):
            event = (steps.get(name) or [{}])[0]
            return event.get("core") or {}, event.get("response")

        again, _ = step("again")
        duplicate, answered = step("duplicate")
        fresh, _ = step("fresh-id")
        # CONTRACT: request IDs are unique within a placement, so placement 2 may use the ID
        # again for a new invocation; inside it a repeated ID is refused with no effect.
        self.eq(label + ".new-placement-new-invocation", (again.get("outcome"), (again.get("data") or {}).get("id"),
                                                          (again.get("data") or {}).get("revision")), ("completed", "e2", 2))
        self.check(label + ".label-duplicate", "label_duplicate" in json.dumps((again.get("data") or {}).get("notices")),
                   again)
        self.check(label + ".duplicate-answered", bool(answered), "no reply to a reused request ID")
        self.check(label + ".duplicate-not-completed", duplicate.get("outcome") != "completed", duplicate)
        # CONTRACT, wire and process: a request reusing an ID, whatever its method or
        # arguments, receives JSON-RPC error -32600 naming the reuse, with that ID. It executes
        # nothing, takes no call number and writes no call-C.json. The identical repeat is not
        # a replay of the earlier reply.
        self.reused_id_error(label + ".duplicate", answered, "identity-same")
        self.reused_id_error(label + ".reused-ping", step("reused-ping")[1], "identity-fresh")
        rundir = self.audit_path(f) / "runs" / "2"
        def numbered(prefix):
            return sorted(int(m.group(1)) for p in rundir.glob(prefix + "-*.json")
                          for m in [re.fullmatch(prefix + r"-([1-9][0-9]*)\.json", p.name)] if m)
        calls = numbered("call")
        self.eq(label + ".call-numbers-contiguous", calls, list(range(1, len(calls) + 1)))
        self.eq(label + ".results-match-calls", numbered("result"), calls)
        ids = [transport_loads((rundir / ("call-%d.json" % n)).read_bytes()).get("id") for n in calls]
        self.eq(label + ".one-call-file-per-id", (ids.count("identity-same"), ids.count("identity-fresh")), (1, 1))
        self.eq(label + ".fresh-id", (fresh.get("outcome"), (fresh.get("data") or {}).get("id"),
                                      (fresh.get("data") or {}).get("revision")), ("completed", "e3", 3))
        self.eq(label + ".ending", (reply.get("data") or {}).get("ending"), "sealed")
        entries = [aw.Entry(e, 1, "record_account", "same", note["text"].encode()) for e in ("e1", "e2", "e3")]
        package = self.check_package_bytes(f, self.inspect_runtime(f, placements=2), entries, 3)
        self.control("reused-id-in-placement-has-no-effect", duplicate.get("outcome") != "completed"
                     and (package / "answer.json").read_bytes() == aw.answer_json(3, entries))

    def reused_id_error(self, label, response, identity):
        response = response if isinstance(response, dict) else {}
        error = response.get("error") if isinstance(response.get("error"), dict) else {}
        self.eq(label + ".jsonrpc-error", (response.get("id"), error.get("code"), "result" in response),
                (identity, -32600, False))
        message = error.get("message")
        self.check(label + ".names-reuse", isinstance(message, str)
                   and re.search(r"reus|duplicate|already", message, re.I) is not None, error)

    def runtime_fidelity_drain_unknown(self):
        """Missing and duplicate echoes during the shutdown drain stay unknown and leave a
        winning seal and its delivery alone (CONTRACT, observed reply fidelity)."""
        for variant in ("late-missing", "late-duplicate"):
            f = self.fidelity_fixture("fidelity-" + variant, variant)
            label = f["label"]
            reply = self.cmd(label + ".run", ["run", f["reference"]])
            self.groups_absent(f)
            self.harness_clean(f)
            self.fidelity_page_witness(f)
            late = f["witness"] / "late-echo.bin"
            self.require(label + ".late-handler-ran", late.exists(), str(late))
            if variant == "late-missing":
                self.eq(label + ".nothing-echoed", late.read_bytes(), b"")
            else:
                self.check(label + ".late-captured", late.stat().st_size > 0
                           and late.read_bytes() in self.captured_channel(f, "stdout"), str(late))
            self.fidelity_record(f, 4, 0, unknown_min=2)
            self.fidelity_diagnostics(f, False)
            self.eq(label + ".seal-won", (reply.get("data") or {}).get("ending"), "sealed")
            status = self.inspect_runtime(f)
            self.check(label + ".summary-fidelity", "fidelity" in status["data"].get("summary", "").lower(), status["data"])
            self.close_after_delivery(f, self.check_delivery(f, status))

    def runtime_fidelity_drain_ending(self):
        """A reply mismatch first observed during drain turns a decided ended_unsubmitted into
        interrupted with cause protocol_anomaly; with an exact drain echo the ordinary ending
        stands; a decided signal ending keeps its value and cause despite the same late
        mismatch (CONTRACT, observed reply fidelity; wire and process)."""
        expected = {"drain-ordinary-exact": ("ended_unsubmitted", None, 0),
                    "drain-ordinary-mismatch": ("interrupted", "protocol_anomaly", 5),
                    "drain-signal-mismatch": ("interrupted", "signal", 5)}
        seen = {}
        for variant, want in expected.items():
            f = self.fidelity_fixture("fidelity-" + variant, variant)
            label = f["label"]
            run = self.spawn(f, "run", ["run", f["reference"]])
            try:
                if variant == "drain-signal-mismatch":
                    self.require(label + ".pages-read", self.await_fact(
                        lambda: (f["witness"] / "pages-read.json").exists(), run["process"], 30), str(f["witness"]))
                    run["process"].send_signal(signal.SIGTERM)
                    self.boundary(f, "signal-sent", owner_pid=run["process"].pid)
                reply = self.collect(run, 60) or {}
            finally:
                self.stop_leftovers(run)
            self.groups_absent(f)
            events = self.harness_clean(f)
            self.fidelity_page_witness(f)
            late = f["witness"] / "late-echo.bin"
            self.require(label + ".echo-in-drain", late.exists() and late.stat().st_size > 0, str(late))
            self.check(label + ".echo-captured", late.read_bytes() in self.captured_channel(f, "stdout"), str(late))
            mismatch = variant.endswith("-mismatch")
            self.fidelity_record(f, 3 if mismatch else 4, int(mismatch))
            self.fidelity_diagnostics(f, mismatch, phase="drain" if mismatch else None)
            data = reply.get("data", {})
            got = (data.get("ending"), data.get("cause"), run["process"].returncode)
            self.eq(label + ".ending", got, want)
            body = (self.run_ended_record(f, 1)[1] or {}).get("body", {})
            self.eq(label + ".run_ended", (body.get("ending"), body.get("cause")), want[:2])
            status = self.cmd(label + ".status", ["status", f["reference"]])
            authoring = status["data"].get("headline", {}).get("authoring")
            if variant.startswith("drain-ordinary"):
                self.eq(label + ".reminder-sent", (data.get("notices"),
                        sum(e["event"] == "drain-second-turn-ended" for e in events)),
                        ([{"type": "reminder", "sent": "sent"}], 1))
            if variant == "drain-ordinary-exact":
                self.eq(label + ".authoring", authoring, {"state": "ended", "ended_by": "ordinary_ending"})
            else:
                self.eq(label + ".authoring-open", authoring, {"state": "open", "ended_by": None})
                self.eq(label + ".next", self.next_tools(status), ["close", "run"])
                self.check(label + ".mismatch-warning", "mismatch" in status["data"].get("summary", "").lower(),
                           status["data"].get("summary"))
            seen[variant] = got
        self.control("drain-mismatch-turns-ordinary-ending",
                     seen.get("drain-ordinary-exact") == expected["drain-ordinary-exact"]
                     and seen.get("drain-ordinary-mismatch") == expected["drain-ordinary-mismatch"])

    def runtime_sealed_late_close(self):
        if self.variant is None or b"STEWART_TEST_FAULT" not in self.variant.read_bytes():
            return "--variant-binary with claude-code,fault-injection is required for the delivery pause"
        original = self.binary
        self.binary = self.variant
        try:
            self.sealed_late_close()
        finally:
            self.binary = original

    def sealed_late_close(self):
        """An auditor seal is linked and the run pauses in its delivery; close is requested
        then. The seal stands with its actor, the run's delivery completes, and because that
        attempt ended after the first close_requested, close awaits confirmation
        (INTERFACE 5.8, 8.3, 8.4; CONTRACTS, close continues delivery)."""
        f = self.fixture("sealed-late-close", scenario="submit")
        label = f["label"]
        self.accept(f)
        faults = f["witness"] / "faults"
        faults.mkdir()
        env = dict(self.env, STEWART_TEST_FAULT="delivery.after_member:1=pause", STEWART_TEST_FAULT_DIR=str(faults))
        argv = [str(self.binary), "run", f["reference"], "--json"]
        close_argv = [str(self.binary), "close", f["reference"], "--json"]
        paths = {name: f["witness"] / name for name in ("run.stdout", "run.stderr", "close.stdout", "close.stderr")}
        before = snapshot(f["archive"])

        def boundary(event, **facts):
            with (f["witness"] / "publication-boundary.jsonl").open("ab") as stream:
                stream.write(compact({"event": event, "monotonic_ns": time.monotonic_ns(), **facts}) + b"\n")

        def records(kind):
            return [r for p in sorted((self.audit_path(f) / "log").glob("*.json"), key=lambda p: int(p.stem))
                    for r in [strict_loads(p.read_bytes())] if r.get("kind") == kind]

        def await_fact(predicate, owner, seconds=15):
            until = time.monotonic() + seconds
            while owner.poll() is None and time.monotonic() < until:
                if predicate():
                    return True
                time.sleep(0.01)
            return bool(predicate())

        close_process = None
        with contextlib.ExitStack() as streams:
            out = {name: streams.enter_context(path.open("wb")) for name, path in paths.items()}
            process = subprocess.Popen(argv, stdout=out["run.stdout"], stderr=out["run.stderr"], env=env, cwd=self.cwd)
            try:
                self.require(label + ".delivery-paused", await_fact(lambda: bool(list(faults.glob("delivery.after_member*.paused"))),
                                                                    process), paths["run.stderr"].read_text(errors="replace"))
                status = self.cmd(label + ".status-paused", ["status", f["reference"]])
                self.eq(label + ".seal-before-close", status["data"].get("seal", {}).get("actor"), "auditor")
                close_process = subprocess.Popen(close_argv, stdout=out["close.stdout"], stderr=out["close.stderr"],
                                                 env=self.env, cwd=self.cwd)
                self.require(label + ".close-requested-while-paused",
                             await_fact(lambda: bool(records("close_requested")), close_process), str(self.audit_path(f)))
                boundary("close-requested-observed", owner_alive=process.poll() is None)
                release_fault_pauses(faults, boundary)
                process.wait(timeout=30)
                close_process.wait(timeout=60)
            finally:
                release_fault_pauses(faults, boundary)
                for owner in (process, close_process):
                    if owner is not None and owner.poll() is None:
                        owner.kill()
                        owner.wait(timeout=5)
        reply = strict_loads(paths["run.stdout"].read_bytes())
        closing = strict_loads(paths["close.stdout"].read_bytes())
        data, cdata = reply.get("data") or {}, closing.get("data") or {}
        self.eq(label + ".run", (reply.get("outcome"), data.get("ending"), process.returncode,
                                 (data.get("seal") or {}).get("actor"), (data.get("delivery") or {}).get("outcome")),
                ("completed", "sealed", 0, "auditor", "verified"))
        self.eq(label + ".retained-earlier-bytes", immutable_changes(before, snapshot(f["archive"])), [])
        self.groups_absent(f)
        self.eq(label + ".close-effects", closing.get("effects"),
                {"run": "ended", "seal": "existing", "delivery": "verified", "closure": "unfinished"})
        self.eq(label + ".close", (closing.get("outcome"), close_process.returncode, cdata.get("unfinished_reason"),
                                   (cdata.get("seal") or {}).get("actor"), cdata.get("runs")),
                ("completed", 0, "awaiting_confirmation", "auditor", {"count": 1, "held": False, "last_ending": "sealed"}))
        token = cdata.get("confirmation")
        self.require(label + ".confirmation-token", isinstance(token, str) and token.startswith("cf1."), token)
        kinds = [r.get("kind") for p in sorted((self.audit_path(f) / "log").glob("*.json"), key=lambda p: int(p.stem))
                 for r in [strict_loads(p.read_bytes())]]
        order = [k for k in kinds if k in ("seal", "close_requested", "delivery_ended")]
        self.eq(label + ".seal-close-delivery-order", order, ["seal", "close_requested", "delivery_ended"])
        seals = records("seal")
        self.eq(label + ".one-auditor-seal", [(r["body"].get("actor"), r["body"].get("invocation") is not None)
                                               for r in seals], [("auditor", True)])
        ended = records("delivery_ended")
        self.eq(label + ".run-delivered", [(r["body"].get("attempt"), r["body"].get("outcome"), r["body"].get("recorded_by"))
                                           for r in ended], [(1, "verified", "run")])
        self.control("late-close-keeps-auditor-seal", [r["body"].get("actor") for r in seals] == ["auditor"]
                     and cdata.get("unfinished_reason") == "awaiting_confirmation")
        status = self.cmd(label + ".status-awaiting", ["status", f["reference"]])
        package = self.check_delivery(f, status)
        delivered = self.package_identity(package)
        done = self.cmd(label + ".confirm", ["close", f["reference"], "--confirm", token])
        ddata = done.get("data") or {}
        self.eq(label + ".closed", (ddata.get("closure"), ddata.get("placement"), (ddata.get("seal") or {}).get("actor")),
                ("complete", "confirmed", "auditor"))
        self.eq(label + ".package-unchanged", self.package_identity(package), delivered)
        self.eq(label + ".one-package", [p.name for p in sorted(package.parent.iterdir())], [package.name])

    # -- Sequences: specification-derived schedules of harness events --------------------

    def sequence_fixture(self, label, steps, *, timeout=60, placements=3, **extra):
        f = self.fixture(label, scenario="sequence", timeout=timeout, placements=placements)
        self.change_scenario(f, steps=list(steps), **extra)
        return f

    def spawn(self, f, name, args, env=None):
        """A manager command in the background; argv, environment and output are retained."""
        out = (f["witness"] / (name + ".stdout")).open("wb")
        err = (f["witness"] / (name + ".stderr")).open("wb")
        argv = [str(self.binary)] + [str(a) for a in args] + ["--json"]
        process = subprocess.Popen(argv, stdout=out, stderr=err, env=env or self.env, cwd=self.cwd)
        return {"process": process, "argv": argv, "env": env or self.env, "name": name, "files": (out, err),
                "stdout": f["witness"] / (name + ".stdout"), "label": f["label"], "started": time.monotonic()}

    def collect(self, h, seconds=60):
        """Wait for a background command and return its decoded reply, or None."""
        try:
            h["process"].wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            h["process"].kill()
            h["process"].wait(timeout=5)
            self.check(h["label"] + "." + h["name"] + ".bounded", False, "still running after %s seconds" % seconds)
        for stream in h["files"]:
            stream.close()
        self.save("witness/%s/%s-command.json" % (h["label"], h["name"]),
                  {"argv": h["argv"], "env": h["env"], "exit": h["process"].returncode,
                   "elapsed_seconds": time.monotonic() - h["started"]})
        raw = h["stdout"].read_bytes()
        try:
            return strict_loads(raw) if raw.strip() else None
        except ValueError as exc:
            self.check(h["label"] + "." + h["name"] + ".reply", False, str(exc))
            return None

    def stop_leftovers(self, *handles):
        for h in handles:
            if h is None:
                continue
            if h["process"].poll() is None:
                h["process"].kill()
                h["process"].wait(timeout=5)
            for stream in h["files"]:
                if not stream.closed:
                    stream.close()

    @staticmethod
    def await_fact(predicate, owner=None, seconds=15):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            if predicate():
                return True
            if owner is not None and owner.poll() is not None:
                break
            time.sleep(0.01)
        return bool(predicate())

    def boundary(self, f, event, **facts):
        with (f["witness"] / "sequence-boundary.jsonl").open("ab") as stream:
            stream.write(compact({"event": event, "monotonic_ns": time.monotonic_ns(), **facts}) + b"\n")

    def log_records(self, f):
        return [(int(p.stem), strict_loads(p.read_bytes()))
                for p in sorted((self.audit_path(f) / "log").glob("*.json"), key=lambda p: int(p.stem))]

    def log_kinds(self, f):
        return [record.get("kind") for _, record in self.log_records(f)]

    def run_ended_record(self, f, run):
        found = [(n, r) for n, r in self.log_records(f) if r.get("kind") == "run_ended" and r["body"].get("run") == run]
        return found[0] if len(found) == 1 else (None, None)

    def notice_records(self, f):
        return [(n, r["body"]) for n, r in self.log_records(f) if r.get("kind") == "notice"]

    @staticmethod
    def next_tools(reply):
        """The manager commands a reply's next calls offer, by name."""
        return sorted({item["argv"][1] for item in (reply or {}).get("next", [])
                       if isinstance(item, dict) and isinstance(item.get("argv"), list) and len(item["argv"]) > 1})

    def sequence_inputs(self, f, run=None):
        events = self.harness_events(f)
        if run is not None:
            models = [e for e in events if e["event"] == "launch" and e["role"] == "model"]
            pid = models[run - 1]["pid"] if len(models) >= run else None
            events = [e for e in events if e.get("pid") == pid]
        return [e["value"].get("message", {}).get("content") for e in events if e["event"] == "input"]

    def refusal_without_start(self, f, label, reply, reason, launches):
        """A run refusal before any reservation (INTERFACE 5.7; CONTRACT): nothing changed,
        no harness was started, no run_started exists and no placement start was used."""
        self.eq(label + ".reason", (reply or {}).get("reason"), reason)
        self.eq(label + ".effects", {k: v for k, v in (reply or {}).get("effects", {}).items() if k != "diagnostic"},
                {"run": "not_started", "answer": "unchanged", "seal": "none", "delivery": "none"})
        self.eq(label + ".no-harness-launch", self.launch_count(f), launches)
        self.eq(label + ".no-run-started", "run_started" in self.log_kinds(f), False)
        self.eq(label + ".no-run-directory", (self.audit_path(f) / "runs" / "1").exists(), False)
        status = self.cmd(label + ".status", ["status", f["reference"]])
        self.eq(label + ".runs", status["data"].get("runs", {}).get("count"), 0)
        self.runtime_allowances(label + ".status", status["data"], 0, f)
        return status

    # -- 5.7: close winning the start reservation ------------------------------------------

    def runtime_start_races_close(self):
        if self.variant is None or b"STEWART_TEST_FAULT" not in self.variant.read_bytes():
            return "--variant-binary with claude-code,fault-injection is required to hold run before its start"
        original = self.binary
        self.binary = self.variant
        try:
            seen = {arm: self.start_race(arm) for arm in ("close-wins", "close-before-run", "run-wins")}
        finally:
            self.binary = original
        self.eq("start-race.invariance", seen["close-wins"], seen["close-before-run"])
        self.control("start-race-close-wins", seen["close-wins"] is not None
                     and seen["close-wins"][:2] == ("refused", "reference_closed") and seen["run-wins"] is None)

    def start_race(self, arm):
        """close-wins: run is held at log.publish:run_started (Appendix C.1) after its checks;
        close publishes close_requested and is held after it; run is released and must refuse
        reference_closed with close and status next (INTERFACE 4.4, 5.7), launching nothing and
        using no start. close-before-run: the same reply without a race. run-wins: the same
        hold without close starts the placement, which seals."""
        label = "start-race-" + arm
        f = self.fixture(label, scenario="submit")
        self.accept(f)
        run_faults, close_faults = f["witness"] / "run-faults", f["witness"] / "close-faults"
        run_faults.mkdir()
        close_faults.mkdir()
        run_env = dict(self.env, STEWART_TEST_FAULT="log.publish:run_started=pause",
                       STEWART_TEST_FAULT_DIR=str(run_faults))
        close_env = dict(self.env, STEWART_TEST_FAULT="close.after_requested=pause",
                         STEWART_TEST_FAULT_DIR=str(close_faults))
        launches = self.launch_count(f)
        run = close = None
        observe = lambda event, **facts: self.boundary(f, event, **facts)
        try:
            if arm == "close-before-run":
                close = self.spawn(f, "close", ["close", f["reference"]], close_env)
                self.require(label + ".close-held", self.await_fact(
                    lambda: bool(list(close_faults.glob("close.after_requested*.paused"))), close["process"]))
                reply = self.cmd(label + ".run", ["run", f["reference"]], outcome="refused")
            else:
                run = self.spawn(f, "run", ["run", f["reference"]], run_env)
                self.require(label + ".run-held", self.await_fact(
                    lambda: bool(list(run_faults.glob("log.publish*.paused"))), run["process"]),
                    (f["witness"] / "run.stderr").read_text(errors="replace"))
                self.eq(label + ".held-before-start", "run_started" in self.log_kinds(f), False)
                if arm == "close-wins":
                    close = self.spawn(f, "close", ["close", f["reference"]], close_env)
                    self.require(label + ".close-held", self.await_fact(
                        lambda: bool(list(close_faults.glob("close.after_requested*.paused"))), close["process"]))
                    self.eq(label + ".close-requested-first",
                            [k for k in self.log_kinds(f) if k in ("close_requested", "run_started")], ["close_requested"])
                release_fault_pauses(run_faults, observe)
                reply = self.collect(run)
                self.eq(label + ".run-exit", run["process"].returncode,
                        0 if arm == "run-wins" else 3)
            if arm == "run-wins":
                self.eq(label + ".ending", (reply or {}).get("data", {}).get("ending"), "sealed")
                self.groups_absent(f)
                self.check_delivery(f, self.inspect_runtime(f))
                return None
            self.eq(label + ".outcome", (reply or {}).get("outcome"), "refused")
            self.refusal_without_start(f, label + ".refused", reply, "reference_closed", launches)
            writer = str(self.binary)
            self.eq(label + ".next", sorted(item.get("argv") for item in (reply or {}).get("next", [])),
                    sorted([[writer, "close", f["reference"]], [writer, "status", f["reference"]]]))
            release_fault_pauses(close_faults, observe)
            closing = self.collect(close)
            self.eq(label + ".close", ((closing or {}).get("outcome"), (closing or {}).get("data", {}).get("closure"),
                                       (closing or {}).get("data", {}).get("before_launch")), ("completed", "complete", True))
            self.eq(label + ".launches-after-close", self.launch_count(f), launches)
            return ((reply or {}).get("outcome"), (reply or {}).get("reason"),
                    {k: v for k, v in (reply or {}).get("effects", {}).items() if k != "diagnostic"},
                    self.next_tools(reply))
        finally:
            release_fault_pauses(run_faults, observe)
            release_fault_pauses(close_faults, observe)
            self.stop_leftovers(run, close)

    # -- First stopping condition decides the ending (CONTRACT, wire and process) -----------

    def term_received(self, f):
        path = f["witness"] / "term-received.jsonl"
        return path.exists() and path.stat().st_size > 0

    def late_after_ordinary(self, label, late, placements=3):
        """The harness resists TERM, then ends its second turn after the reminder: the ordinary
        ending is decided and shutdown waits two seconds before KILL. A later signal or close
        arrives inside that window, before run_ended."""
        steps = [{"op": "record"}, {"op": "result", "is_error": False, "checkpoint": 0},
                 {"op": "await_input", "expect": "reminder"}, {"op": "resist_term"},
                 {"op": "result", "is_error": False, "checkpoint": 1}, {"op": "hang"}]
        f = self.sequence_fixture(label, steps, placements=placements)
        self.accept(f)
        run = close = None
        close_faults = f["witness"] / "close-faults"
        close_faults.mkdir()
        observe = lambda event, **facts: self.boundary(f, event, **facts)
        try:
            run = self.spawn(f, "run", ["run", f["reference"]])
            self.require(label + ".shutdown-began", self.await_fact(lambda: self.term_received(f), run["process"], 20),
                         str(f["witness"]))
            if late == "signal":
                ended_before = self.run_ended_record(f, 1)[0] is not None
                run["process"].send_signal(signal.SIGTERM)
                self.boundary(f, "late-signal-sent", owner_pid=run["process"].pid, run_ended_before=ended_before)
            else:
                env = dict(self.env, STEWART_TEST_FAULT="close.after_requested=pause",
                           STEWART_TEST_FAULT_DIR=str(close_faults))
                close = self.spawn(f, "close", ["close", f["reference"]], env)
                self.require(label + ".close-held", self.await_fact(
                    lambda: bool(list(close_faults.glob("close.after_requested*.paused"))), close["process"]))
                ended_before = self.run_ended_record(f, 1)[0] is not None
                self.boundary(f, "late-close-requested", run_ended_before=ended_before)
            # Construction: the late condition preceded the recorded ending.
            self.require(label + ".late-before-run-ended", not ended_before and run["process"].poll() is None,
                         {"run_ended_before": ended_before, "owner_exit": run["process"].poll()})
            reply = self.collect(run, 30) or {}
            closing = None
            if close is not None:
                release_fault_pauses(close_faults, observe)
                closing = self.collect(close)
        finally:
            release_fault_pauses(close_faults, observe)
            self.stop_leftovers(run, close)
        data = (reply or {}).get("data", {})
        self.eq(label + ".ending", (data.get("ending"), data.get("cause"), run["process"].returncode),
                ("ended_unsubmitted", None, 0))
        number, ended = self.run_ended_record(f, 1)
        self.eq(label + ".run_ended", ((ended or {}).get("body", {}).get("ending"), (ended or {}).get("body", {}).get("cause")),
                ("ended_unsubmitted", None))
        self.groups_absent(f)
        return f, reply, closing

    def violation_near_deadline(self, label, placements, timeout=8):
        """The harness resists TERM and names an unprefixed tool one second before the earliest
        possible deadline (the reservation follows the driver's spawn), so the violation is the
        first condition and shutdown outlasts the deadline."""
        steps = [{"op": "record"}, {"op": "resist_term"}, {"op": "wait_until", "key": "violation_at"},
                 {"op": "assistant_tool", "name": "record_account"}, {"op": "hang"}]
        f = self.sequence_fixture(label, steps, timeout=timeout, placements=placements)
        self.accept(f)
        started = time.time_ns()
        self.change_scenario(f, violation_at=started + (timeout - 1) * 1_000_000_000)
        run = self.spawn(f, "run", ["run", f["reference"]])
        try:
            reply = self.collect(run, timeout + 20) or {}
        finally:
            self.stop_leftovers(run)
        reached = [e for e in self.harness_events(f) if e["event"] == "seq-time-reached"]
        self.require(label + ".violation-before-deadline", len(reached) == 1
                     and reached[0]["wall_ns"] < started + timeout * 1_000_000_000, reached)
        self.require(label + ".shutdown-began", self.term_received(f), str(f["witness"]))
        self.groups_absent(f)
        stop = strict_loads((self.audit_path(f) / "runs" / "1" / "runtime-stop.json").read_bytes())
        self.require(label + ".shutdown-outlasted-deadline", stop.get("elapsed_ms", 0) > stop.get("deadline_ms", 0), stop)
        data = (reply or {}).get("data", {})
        self.eq(label + ".ending", (data.get("ending"), data.get("cause"), run["process"].returncode),
                ("interrupted", "protocol_anomaly", 5))
        return f, reply

    def runtime_first_condition(self):
        # A signal after the decided ordinary ending changes nothing and cannot reopen authoring.
        f, reply, _ = self.late_after_ordinary("first-condition-late-signal", "signal")
        label = f["label"]
        self.eq(label + ".authoring", reply.get("data", {}).get("headline", {}).get("authoring"),
                {"state": "ended", "ended_by": "ordinary_ending"})
        status = self.cmd(label + ".status", ["status", f["reference"]])
        self.eq(label + ".condition", status["data"].get("condition"), "ended_unsubmitted")
        late_kept = reply.get("data", {}).get("ending") == "ended_unsubmitted"
        if late_kept:
            launches = self.launch_count(f)
            again = self.cmd(label + ".run-again", ["run", f["reference"]], outcome="refused")
            self.eq(label + ".not-reopened", (again.get("reason"), again.get("data", {}).get("ended_by")),
                    ("authoring_ended", "ordinary_ending"))
            self.eq(label + ".no-launch", self.launch_count(f), launches)
        else:
            self.note(label + ".run-again", "not run: the late signal already replaced the recorded ending")
        # Control: the signal first, while the placement is live, decides interrupted/signal.
        steps = [{"op": "record"}, {"op": "result", "is_error": False, "checkpoint": 0},
                 {"op": "await_input", "expect": "reminder"}, {"op": "marker", "name": "reminder-received"},
                 {"op": "hang"}]
        f = self.sequence_fixture("first-condition-signal-first", steps)
        label = f["label"]
        self.accept(f)
        run = self.spawn(f, "run", ["run", f["reference"]])
        try:
            self.require(label + ".reminder-received", self.await_fact(
                lambda: (f["witness"] / "reminder-received").exists(), run["process"], 20), str(f["witness"]))
            run["process"].send_signal(signal.SIGTERM)
            reply = self.collect(run, 30)
        finally:
            self.stop_leftovers(run)
        data = (reply or {}).get("data", {})
        self.eq(label + ".ending", (data.get("ending"), data.get("cause"), run["process"].returncode),
                ("interrupted", "signal", 5))
        self.eq(label + ".authoring-open", data.get("headline", {}).get("authoring"), {"state": "open", "ended_by": None})
        self.groups_absent(f)
        self.control("first-condition-signal", late_kept and data.get("cause") == "signal")
        # A violation decided before the deadline keeps its cause when shutdown outlasts it.
        f, reply = self.violation_near_deadline("first-condition-violation", placements=3)
        self.eq(f["label"] + ".authoring-open", reply.get("data", {}).get("headline", {}).get("authoring"),
                {"state": "open", "ended_by": None})
        kept = reply.get("data", {}).get("cause") == "protocol_anomaly"
        f, reply = self.violation_near_deadline("first-condition-violation-last", placements=1)
        self.eq(f["label"] + ".not-limit-reached", reply.get("data", {}).get("ending"), "interrupted")
        # Control: with no earlier condition the deadline decides.
        f = self.sequence_fixture("first-condition-deadline", [{"op": "record"}, {"op": "hang"}], timeout=6)
        self.accept(f)
        reply = self.cmd(f["label"] + ".run", ["run", f["reference"]], outcome=None, timeout=40)
        data = reply.get("data", {})
        self.eq(f["label"] + ".ending", (data.get("ending"), data.get("cause")), ("interrupted", "placement_deadline"))
        self.groups_absent(f)
        self.control("first-condition-deadline", kept and data.get("cause") == "placement_deadline")

    def runtime_late_close(self):
        if self.variant is None or b"STEWART_TEST_FAULT" not in self.variant.read_bytes():
            return "--variant-binary with claude-code,fault-injection is required to hold close after its request"
        original = self.binary
        self.binary = self.variant
        try:
            f, reply, closing = self.late_after_ordinary("late-close-after-ordinary", "close")
            label = f["label"]
            records = self.log_records(f)
            order = [r["kind"] for _, r in records if r.get("kind") in ("close_requested", "run_ended", "seal")]
            self.eq(label + ".log-order", order, ["close_requested", "run_ended", "seal"])
            # INTERFACE 1.6: the first recorded ending in log order is the close request.
            self.eq(label + ".authoring", reply.get("data", {}).get("headline", {}).get("authoring"),
                    {"state": "ended", "ended_by": "close"})
            self.eq(label + ".close", ((closing or {}).get("outcome"), (closing or {}).get("effects", {}).get("seal"),
                                       ((closing or {}).get("data", {}).get("seal") or {}).get("actor")),
                    ("completed", "recorded", "manager"))
            kept = reply.get("data", {}).get("ending") == "ended_unsubmitted"
            # Control: the close request first, while the placement is live.
            steps = [{"op": "record"}, {"op": "result", "is_error": False, "checkpoint": 0},
                     {"op": "await_input", "expect": "reminder"}, {"op": "marker", "name": "reminder-received"},
                     {"op": "hang"}]
            f = self.sequence_fixture("late-close-control", steps)
            label = f["label"]
            self.accept(f)
            faults = f["witness"] / "close-faults"
            faults.mkdir()
            observe = lambda event, **facts: self.boundary(f, event, **facts)
            run = close = None
            try:
                run = self.spawn(f, "run", ["run", f["reference"]])
                self.require(label + ".reminder-received", self.await_fact(
                    lambda: (f["witness"] / "reminder-received").exists(), run["process"], 20), str(f["witness"]))
                close = self.spawn(f, "close", ["close", f["reference"]], dict(
                    self.env, STEWART_TEST_FAULT="close.after_requested=pause", STEWART_TEST_FAULT_DIR=str(faults)))
                self.require(label + ".close-held", self.await_fact(
                    lambda: bool(list(faults.glob("close.after_requested*.paused"))), close["process"]))
                reply = self.collect(run, 30)
                release_fault_pauses(faults, observe)
                self.collect(close)
            finally:
                release_fault_pauses(faults, observe)
                self.stop_leftovers(run, close)
            data = (reply or {}).get("data", {})
            self.eq(label + ".ending", (data.get("ending"), run["process"].returncode), ("stopped_by_close", 0))
            self.groups_absent(f)
            self.control("late-close-keeps-ordinary-ending", kept and data.get("ending") == "stopped_by_close")
        finally:
            self.binary = original

    # -- The final permitted placement's interruption ends authoring as limit ----------------

    def final_interruption(self, label, placements, scenario, **changes):
        f = self.fixture(label, scenario=scenario, timeout=30, placements=placements)
        if changes:
            self.change_scenario(f, **changes)
        self.accept(f)
        reply = self.cmd(label + ".run", ["run", f["reference"]], outcome="completed")
        self.groups_absent(f)
        data = reply.get("data", {})
        # A harness exit and an unprefixed tool are stopping conditions with no other cause
        # (CONTRACT, wire and process).
        self.eq(label + ".interrupted", (data.get("ending"), data.get("cause")), ("interrupted", "protocol_anomaly"))
        status = self.cmd(label + ".status", ["status", f["reference"]])
        sdata = status["data"]
        last = sdata.get("runs", {}).get("last") or {}
        self.eq(label + ".status-keeps-ending", (sdata.get("condition"), last.get("ending"), last.get("cause")),
                ("interrupted", "interrupted", data.get("cause")))
        return f, reply, status

    def runtime_final_interruption(self):
        launches_ok = []
        for label, scenario, changes in (("final-interruption-exit", "sequence",
                                          {"steps": [{"op": "record"}, {"op": "exit", "code": 7}]}),
                                         ("final-interruption-violation", "tool-name",
                                          {"assistant_tool": "record_account"})):
            f, reply, status = self.final_interruption(label, 1, scenario, **changes)
            data, sdata = reply.get("data", {}), status["data"]
            limit = {"state": "ended", "ended_by": "limit"}
            self.eq(label + ".run-authoring", data.get("headline", {}).get("authoring"), limit)
            self.eq(label + ".status-authoring", sdata.get("headline", {}).get("authoring"), limit)
            self.eq(label + ".run-next", self.next_tools(reply), ["close"])
            self.eq(label + ".status-next", self.next_tools(status), ["close"])
            self.summary_facts(label + ".summary", sdata.get("summary"), f, 1)
            number, _ = self.run_ended_record(f, 1)
            launches = self.launch_count(f)
            again = self.cmd(label + ".run-again", ["run", f["reference"]], outcome="refused")
            self.eq(label + ".refusal", (again.get("reason"), again.get("data")),
                    ("authoring_ended", {"ended_by": "limit", "record": "log/%s.json" % number}))
            self.eq(label + ".refusal-next", self.next_tools(again), ["close", "status"])
            self.eq(label + ".refusal-effects", {k: v for k, v in again.get("effects", {}).items() if k != "diagnostic"},
                    {"run": "ended", "answer": "unchanged", "seal": "none", "delivery": "none"})
            self.eq(label + ".no-launch", self.launch_count(f), launches)
            launches_ok.append(again.get("reason") == "authoring_ended" and again.get("data", {}).get("ended_by") == "limit")
        # Differing: a start remains, so the same interruption leaves authoring open.
        f, reply, status = self.final_interruption("final-interruption-slots-remain", 2, "sequence",
                                                   steps=[{"op": "record"}, {"op": "exit", "code": 7}])
        label = f["label"]
        self.eq(label + ".authoring-open", status["data"].get("headline", {}).get("authoring"),
                {"state": "open", "ended_by": None})
        self.eq(label + ".status-next", self.next_tools(status), ["close", "run"])
        self.change_scenario(f, mode="submit", skip_record=True, session=label + "-session-2")
        second = self.cmd(label + ".run-2", ["run", f["reference"]])
        self.eq(label + ".continued", second.get("data", {}).get("ending"), "sealed")
        self.groups_absent(f, run=2)
        self.control("final-interruption-ends-authoring", all(launches_ok)
                     and second.get("data", {}).get("ending") == "sealed")
        # The final placement's process is gone without run_ended: run reconciles it and then
        # refuses authoring_ended at its start reservation, naming that record (CONTRACT,
        # limits; INTERFACE 5.7, 6.7). Differing: with a start left it reconciles and starts.
        refused = None
        for label, placements in (("final-interruption-process-gone", 1), ("process-gone-slots-remain", 2)):
            f = self.fixture(label, scenario="hang", placements=placements)
            self.accept(f)
            self.kill_run_owner(f)
            self.require(label + ".groups-gone", not self.groups_absent(f, stop_record=False))
            self.eq(label + ".no-run-ended-yet", self.run_ended_record(f, 1)[0], None)
            launches = self.launch_count(f)
            if placements == 1:
                reply = self.cmd(label + ".run", ["run", f["reference"]], outcome="refused")
                number, ended = self.run_ended_record(f, 1)
                body = (ended or {}).get("body", {})
                self.eq(label + ".reconciled", (body.get("ending"), body.get("cause"), body.get("recorded_by")),
                        ("interrupted", "process_gone", "run"))
                self.eq(label + ".refusal", (reply.get("reason"), reply.get("data")),
                        ("authoring_ended", {"ended_by": "limit", "record": "log/%s.json" % number}))
                self.eq(label + ".refusal-next", self.next_tools(reply), ["close", "status"])
                self.eq(label + ".refusal-effects",
                        {k: v for k, v in reply.get("effects", {}).items() if k != "diagnostic"},
                        {"run": "ended", "answer": "unchanged", "seal": "none", "delivery": "none"})
                self.eq(label + ".no-launch", self.launch_count(f), launches)
                self.eq(label + ".one-start", self.log_kinds(f).count("run_started"), 1)
                status = self.cmd(label + ".status", ["status", f["reference"]])
                self.eq(label + ".status-authoring", status["data"].get("headline", {}).get("authoring"),
                        {"state": "ended", "ended_by": "limit"})
                self.eq(label + ".status-next", self.next_tools(status), ["close"])
                refused = reply.get("reason") == "authoring_ended" and (reply.get("data") or {}).get("ended_by") == "limit"
            else:
                self.change_scenario(f, mode="submit", session=label + "-session-2")
                reply = self.cmd(label + ".run", ["run", f["reference"]])
                body = (self.run_ended_record(f, 1)[1] or {}).get("body", {})
                self.eq(label + ".reconciled", (body.get("ending"), body.get("cause"), body.get("recorded_by")),
                        ("interrupted", "process_gone", "run"))
                self.eq(label + ".continued", reply.get("data", {}).get("ending"), "sealed")
                self.groups_absent(f, run=2)
                self.control("final-process-gone-refused-at-reservation",
                             refused and reply.get("data", {}).get("ending") == "sealed")

    # -- Advice while stopping is unknown ------------------------------------------------------

    def runtime_unknown_stop_advice(self):
        f = self.fixture("unknown-stop-advice", scenario="hang")
        label = f["label"]
        self.accept(f)
        self.kill_run_owner(f)
        self.require(label + ".original-groups-gone", not self.groups_absent(f, stop_record=False))
        process_record = self.audit_path(f) / "runs" / "1" / "process-model.json"
        original = process_record.read_bytes()
        (f["witness"] / "original-process-model.json").write_bytes(original)
        stop_record = self.audit_path(f) / "runs" / "1" / "runtime-stop.json"
        if stop_record.exists():
            (f["witness"] / "original-runtime-stop.json").write_bytes(stop_record.read_bytes())
            stop_record.unlink()
        # The same controlled damage as runtime-unknown-stop: the recorded group names a live
        # group this driver owns, which recovery must neither treat as stopped nor signal.
        unrelated = subprocess.Popen(["/bin/sleep", "60"], start_new_session=True)
        try:
            changed = strict_loads(original)
            changed["group"] = unrelated.pid
            process_record.write_bytes(compact(changed) + b"\n")
            self.eq(label + ".unrelated-present", group_observation(unrelated.pid), "present")
            status = self.cmd(label + ".status-unknown", ["status", f["reference"]])
            self.eq(label + ".status-next-unknown", self.next_tools(status), ["status"])
            summary = status["data"].get("summary", "")
            self.check(label + ".summary-names-placement",
                       re.search(r"\b(?:placement|run)\s+1\b", summary, re.I) is not None, summary)
            refused = self.cmd(label + ".run-unknown", ["run", f["reference"]], outcome="refused")
            self.eq(label + ".run-refusal", refused.get("reason"), "runtime_stop_unknown")
            self.eq(label + ".run-next-unknown", self.next_tools(refused), ["status"])
            unknown_advice = self.next_tools(status) == ["status"] and self.next_tools(refused) == ["status"]
        finally:
            if unrelated.poll() is None:
                unrelated.terminate()
            unrelated.wait(timeout=5)
        self.require(label + ".unrelated-absent", self.await_fact(lambda: group_observation(unrelated.pid) == "absent",
                                                                  seconds=5))
        # Differing: once the recorded groups are observed absent the ordinary advice applies.
        status = self.cmd(label + ".status-known", ["status", f["reference"]])
        self.eq(label + ".status-next-known", self.next_tools(status), ["close", "run"])
        self.control("unknown-stop-advice", unknown_advice and self.next_tools(status) == ["close", "run"])
        self.change_scenario(f, mode="submit", session=label + "-session-2")
        continued = self.cmd(label + ".run-known", ["run", f["reference"]])
        self.eq(label + ".continued", continued.get("data", {}).get("ending"), "sealed")
        self.groups_absent(f, run=2)

    # -- Launch-directory checks before the reservation -----------------------------------------

    def launch_refused(self, f, label):
        launches = self.launch_count(f)
        log_before = snapshot(self.audit_path(f) / "log")
        reply = self.cmd(label + ".run", ["run", f["reference"]], outcome="refused")
        self.refusal_without_start(f, label, reply, "runtime_profile_invalid", launches)
        self.eq(label + ".log-unchanged", snapshot(self.audit_path(f) / "log"), log_before)
        return reply.get("reason") == "runtime_profile_invalid" and self.launch_count(f) == launches

    def runtime_launch_directory(self):
        fired = []
        # An instruction entry in the temporary directory or an ancestor refuses before the
        # reservation; removing it lets the same audit start (CONTRACT, wire and process).
        for label, up, name, kind in (("launch-dir-git-self", 0, ".git", "dir"),
                                      ("launch-dir-claude-md-parent", 1, "CLAUDE.md", "file"),
                                      ("launch-dir-agents-md-root", 2, "AGENTS.md", "file"),
                                      ("launch-dir-dot-claude-parent", 1, ".claude", "dir"),
                                      ("launch-dir-git-file-root", 2, ".git", "file")):
            f = self.fixture(label, scenario="submit", placements=2)
            self.accept(f)
            temporary = Path(f["launch"]["temporary_directory"])
            entry = (temporary.parents[up - 1] if up else temporary) / name
            if kind == "dir":
                entry.mkdir()
            else:
                entry.write_bytes(b"gitdir: /nonexistent\n" if name == ".git" else b"# Instructions.\n")
            (f["witness"] / "planted-entry.json").write_bytes(compact({"path": str(entry), "kind": kind}) + b"\n")
            refused = self.launch_refused(f, label + ".planted")
            entry.rmdir() if kind == "dir" else entry.unlink()
            number = self.cmd(label + ".before-clean", ["status", f["reference"]])["data"]["runs"]["count"] + 1
            reply = self.cmd(label + ".clean-run", ["run", f["reference"]])
            self.eq(label + ".clean-run-ending", reply.get("data", {}).get("ending"), "sealed")
            self.groups_absent(f, run=number)
            fired.append(refused and reply.get("data", {}).get("ending") == "sealed")
        # Invariance: near-miss names are not instruction entries.
        f = self.fixture("launch-dir-near-miss", scenario="submit", placements=2)
        self.accept(f)
        temporary = Path(f["launch"]["temporary_directory"])
        (temporary / ".gitignore").write_bytes(b"*\n")
        (temporary.parent / "CLAUDE.md.orig").write_bytes(b"# Not instructions.\n")
        (temporary.parents[1] / ".claude-old").mkdir()
        (temporary.parents[1] / "AGENTS").write_bytes(b"not instructions\n")
        reply = self.cmd("launch-dir-near-miss.run", ["run", f["reference"]])
        self.eq("launch-dir-near-miss.ending", reply.get("data", {}).get("ending"), "sealed")
        self.groups_absent(f)
        # A temporary directory that is or lies within the archive or the submission folder.
        for label, place in (("launch-dir-archive", lambda root, folder, archive: archive),
                             ("launch-dir-within-archive", lambda root, folder, archive: archive / "audits"),
                             ("launch-dir-submission", lambda root, folder, archive: folder),
                             ("launch-dir-within-submission", lambda root, folder, archive: folder / "materials")):
            f = self.fixture(label, scenario="submit", placements=2, temporary=place)
            self.accept(f)
            fired.append(self.launch_refused(f, label))
        # The writer's directory: a byte-identical writer in a directory the profile names.
        writer_dir = self.work / "launch-dir-writer-bin"
        writer_dir.mkdir()
        copy_path = writer_dir / "stewart"
        copy_path.write_bytes(self.binary.read_bytes())
        copy_path.chmod(0o700)
        original = self.binary
        self.binary = copy_path
        try:
            f = self.fixture("launch-dir-writer", binary=copy_path, scenario="submit", placements=2,
                             temporary=lambda root, folder, archive: writer_dir)
            self.accept(f)
            fired.append(self.launch_refused(f, "launch-dir-writer"))
        finally:
            self.binary = original
        self.control("launch-directory-refused-before-reservation", all(fired) and len(fired) == 10)

    # -- Notice transmission and request positions (CONTRACT, accounting record) ---------------

    def notice_expectations(self, f, run, label, *, types, sent, timeout):
        """Each notice record of the placement in log order: its type, request position from 1,
        text and, for the near-limit notice, remaining values; run_ended.notices lists them
        with the expected transmission. Returns the records' names."""
        records = [(n, b) for n, b in self.notice_records(f) if b.get("run") == run]
        self.eq(label + ".notice-types", [b.get("type") for _, b in records], types)
        self.eq(label + ".notice-requests", [b.get("request") for _, b in records], list(range(1, len(records) + 1)))
        for n, body in records:
            if body.get("type") == "reminder":
                self.eq(label + ".reminder-record", (body.get("text"), body.get("remaining")), (REMINDER, None))
            else:
                values = near_limit_values(body.get("text"))
                self.check(label + ".near-limit-text", values is not None, body.get("text"))
                values = values or {}
                self.eq(label + ".near-limit-remaining", body.get("remaining"), {"runtime": "claude-code/1", **values})
                self.eq(label + ".near-limit-placements", values.get("placements"), f["limits"]["max_placements"] - run)
                # Due only at or below a fifth of the placement timeout, rounded down.
                self.check(label + ".near-limit-due", 0 <= values.get("seconds", -1) <= timeout // 5, values)
        _, ended = self.run_ended_record(f, run)
        self.eq(label + ".run_ended-notices", (ended or {}).get("body", {}).get("notices"),
                [{"type": b.get("type"), "record": "log/%d.json" % n, "sent": state}
                 for (n, b), state in zip(records, sent)])
        return records

    def runtime_notice_transmission(self):
        timeout = 25
        # Reminder first, each notice followed by a compaction boundary: every notice is sent
        # when claimed, before the harness emits anything more, and none is resent.
        steps = [{"op": "record"}, {"op": "result", "is_error": False, "checkpoint": 0},
                 {"op": "await_input", "expect": "reminder"}, {"op": "compact", "serial": 1},
                 {"op": "await_input", "expect": "compacted"},
                 {"op": "await_input", "expect": "near_limit", "timeout": 30}, {"op": "compact", "serial": 2},
                 {"op": "await_input", "expect": "compacted"}, {"op": "submit"}]
        f = self.sequence_fixture("notice-order-reminder-first", steps, timeout=timeout)
        label = f["label"]
        self.accept(f)
        reply = self.cmd(label + ".run", ["run", f["reference"]], timeout=60)
        self.groups_absent(f)
        self.harness_clean(f)
        self.eq(label + ".ending", reply.get("data", {}).get("ending"), "sealed")
        inputs = self.sequence_inputs(f)
        self.eq(label + ".input-kinds", [input_kind(c) for c in inputs[1:]],
                ["reminder", "compacted", "near_limit", "compacted"])
        self.eq(label + ".no-timeouts", [e for e in self.harness_events(f) if e["event"] == "seq-input-timeout"], [])
        self.notice_expectations(f, 1, label, types=["reminder", "near_limit"], sent=["sent", "sent"], timeout=timeout)
        self.eq(label + ".reply-notices", reply.get("data", {}).get("notices"),
                [{"type": "reminder", "sent": "sent"}, {"type": "near_limit", "sent": "sent"}])
        self.eq(label + ".input-capture", self.captured_channel(f, "input").hex(), b"".join(
            bytes.fromhex(e["raw_hex"]) for e in self.harness_events(f) if e["event"] == "input").hex())
        sent_first = reply.get("data", {}).get("notices")
        # Near-limit first, then the reminder; then the owner dies. Recovery has no
        # transmission observation, so every claimed notice of that placement is unknown.
        steps = [{"op": "record"}, {"op": "await_input", "expect": "near_limit", "timeout": 30},
                 {"op": "result", "is_error": False, "checkpoint": 0}, {"op": "await_input", "expect": "reminder"},
                 {"op": "marker", "name": "ready.json"}, {"op": "hang"}]
        f = self.sequence_fixture("notice-order-near-limit-first", steps, timeout=timeout)
        label = f["label"]
        self.accept(f)
        self.kill_run_owner_after(f, 40)
        self.require(label + ".groups-gone", not self.groups_absent(f, stop_record=False))
        self.change_scenario(f, mode="submit", skip_record=True, session=label + "-session-2")
        second = self.cmd(label + ".recover", ["run", f["reference"]])
        self.eq(label + ".recovered-ending", second.get("data", {}).get("ending"), "sealed")
        self.groups_absent(f, run=2)
        number, ended = self.run_ended_record(f, 1)
        body = (ended or {}).get("body", {})
        self.eq(label + ".reconciled", (body.get("ending"), body.get("cause"), body.get("recorded_by")),
                ("interrupted", "process_gone", "run"))
        self.notice_expectations(f, 1, label, types=["near_limit", "reminder"], sent=["unknown", "unknown"],
                                 timeout=timeout)
        inputs = self.sequence_inputs(f, run=2)
        self.eq(label + ".continuation-inputs", [input_kind(c) for c in inputs[1:]], ["continuation"])
        # Never due by placements: the final placement with a long timeout gets no notice.
        steps = [{"op": "record"}, {"op": "await_input", "expect": "near_limit", "timeout": 4, "on_timeout": "continue"},
                 {"op": "submit"}]
        f = self.sequence_fixture("notice-final-placement-long", steps, timeout=200, placements=1)
        label = f["label"]
        self.accept(f)
        reply = self.cmd(label + ".run", ["run", f["reference"]])
        self.groups_absent(f)
        self.eq(label + ".ending", reply.get("data", {}).get("ending"), "sealed")
        self.eq(label + ".no-notice", ([input_kind(c) for c in self.sequence_inputs(f)[1:]],
                                       self.notice_records(f), reply.get("data", {}).get("notices")), ([], [], []))
        self.control("near-limit-due-by-time-not-placements",
                      sent_first == [{"type": "reminder", "sent": "sent"}, {"type": "near_limit", "sent": "sent"}]
                      and not self.notice_records(f))
        # A captured frame whose write cannot complete differs from one written in full.
        self.control("notice-write-incomplete-differs", self.notice_write_incomplete() != "sent"
                     and sent_first[0]["sent"] == "sent")

    def kill_run_owner_after(self, f, seconds):
        """Start run, wait for the harness's ready.json marker, then SIGKILL the owner."""
        run = self.spawn(f, "owner", ["run", f["reference"]])
        try:
            self.require(f["label"] + ".ready-before-owner-kill", self.await_fact(
                lambda: (f["witness"] / "ready.json").exists(), run["process"], seconds), str(f["witness"]))
            run["process"].kill()
            run["process"].wait(timeout=5)
            self.boundary(f, "owner-killed", pid=run["process"].pid, exit=run["process"].returncode)
        finally:
            self.stop_leftovers(run)
            self.collect(run, 5)

    def captured_reminder(self, f, run=1):
        """Whether the placement's input capture holds the reminder as a complete frame."""
        return REMINDER in input_frames(self.captured_channel(f, "input", run))

    def runtime_notice_not_sent(self):
        if self.variant is None or b"STEWART_TEST_FAULT" not in self.variant.read_bytes():
            return "--variant-binary with claude-code,fault-injection is required for the notice fault point"
        original = self.binary
        self.binary = self.variant
        try:
            self.notice_not_sent()
        finally:
            self.binary = original

    def notice_not_sent(self):
        """log.dirsync:notice=eio links the reminder's claim and fails its directory sync: an
        archive-write failure stops the placement before the frame is captured, so the claim
        is listed not_sent and no complete reminder frame is in the input capture."""
        steps = [{"op": "record"}, {"op": "result", "is_error": False, "checkpoint": 0},
                 {"op": "await_input", "expect": "reminder", "timeout": 8}, {"op": "hang"}]
        f = self.sequence_fixture("notice-not-sent", steps, timeout=30)
        label = f["label"]
        self.accept(f)
        faults = f["witness"] / "faults"
        faults.mkdir()
        env = dict(self.env, STEWART_TEST_FAULT="log.dirsync:notice=eio", STEWART_TEST_FAULT_DIR=str(faults))
        reply = self.cmd(label + ".run", ["run", f["reference"]], outcome=None, env=env, timeout=60)
        self.groups_absent(f)
        data = reply.get("data", {})
        self.eq(label + ".ending", (data.get("ending"), data.get("cause")), ("interrupted", "archive_write_failed"))
        self.eq(label + ".not-captured", self.captured_reminder(f), False)
        self.notice_expectations(f, 1, label, types=["reminder"], sent=["not_sent"], timeout=30)
        self.eq(label + ".reply-notices", data.get("notices"), [{"type": "reminder", "sent": "not_sent"}])
        self.control("notice-not-sent", data.get("notices") == [{"type": "reminder", "sent": "not_sent"}])

    def pipe_filled(self, f, label):
        """The harness's single fill and its probe witness. Fresh pipes of the same capacity
        accepted exactly the frames the platform's packing rule (pipe_accepts) predicted, one
        more was refused, and the outer driver's next frame, where given, was refused after
        them. Without that agreement the case cannot reach the blocked write it intends."""
        filled = [e for e in self.harness_events(f) if e["event"] == "seq-filled"]
        self.require(label + ".filled", len(filled) == 1, filled)
        fill = filled[0]
        facts, count, probe = fill["facts"], fill["count"], fill["probe"]
        self.eq(label + ".pipe-rule-count", count, pipe_frames_fit(fill["frame_bytes"], facts))
        observed = {"frames": probe["frames"]["accepted"], "next": (probe.get("next") or {}).get("accepted"),
                    "probe_capacity": probe["frames"]["capacity"]}
        expected = {"frames": count,
                    "next": None if fill["next_bytes"] is None
                    else pipe_accepts([fill["frame_bytes"]] * count + [fill["next_bytes"]], facts),
                    "probe_capacity": facts["capacity"] if facts["page_size"] is not None else None}
        self.eq(label + ".pipe-probe", observed, expected)
        return fill

    def unread_input(self, f, label):
        """The lengths and contents of the captured input frames after those the harness
        read, in order. The harness's reads must be a prefix of the capture."""
        read = b"".join(bytes.fromhex(e["raw_hex"]) for e in self.harness_events(f) if e["event"] == "input")
        stream = self.captured_channel(f, "input")
        self.require(label + ".read-prefix", stream.startswith(read),
                     {"read_bytes": len(read), "captured_bytes": len(stream)})
        pending = stream[len(read):]
        return [len(raw) + 1 for raw in pending.split(b"\n")[:-1]], input_frames(pending)

    def notice_write_incomplete(self):
        """The harness stops reading its input, then exposes as many compaction boundaries as
        their pinned notices fit in the input pipe, then ends a turn. The reminder is claimed
        when its frame no longer fits, so no write of it can complete: a complete capture is
        listed unknown, a frame never captured not_sent (CONTRACT, accounting record). The
        unread frames before it, from the capture and packed by the platform's rule, show it
        could not fit. This assumes no other holder of the pipe's read side reads the
        harness's input. The harness then hangs: the supervisor stops it at the deadline,
        so the failed write, first observed after the deadline, is the deadline (CONTRACT,
        wire and process); this audit has starts left."""
        timeout = 12
        frame = user_frame(COMPACTED)
        steps = [{"op": "record"}, {"op": "stop_reading"},
                 {"op": "fill_input", "frame_bytes": len(frame), "next_bytes": len(user_frame(REMINDER))},
                 {"op": "result", "is_error": False, "checkpoint": 0}, {"op": "marker", "name": "result-emitted"},
                 {"op": "hang"}]
        f = self.sequence_fixture("notice-write-incomplete", steps, timeout=timeout)
        label = f["label"]
        self.accept(f)
        reply = self.cmd(label + ".run", ["run", f["reference"]], outcome=None, timeout=timeout + 30)
        self.groups_absent(f)
        stopped = [e for e in self.harness_events(f) if e["event"] == "seq-stopped-reading"]
        self.require(label + ".stopped-reading", len(stopped) == 1 and not stopped[0]["reader_alive"], stopped)
        fill = self.pipe_filled(f, label)
        self.require(label + ".result-emitted", (f["witness"] / "result-emitted").exists(),
                     "the harness could not emit its result; its output was not read")
        claims = self.notice_records(f)
        self.require(label + ".reminder-claimed", [b.get("type") for _, b in claims] == ["reminder"],
                     "no reminder claim while input was blocked; the incomplete-write path was not exercised")
        captured = self.captured_reminder(f)
        if captured:
            # A write can be incomplete only if the unread input before the reminder leaves
            # no room for it, by the platform's packing: pages on Linux, bytes on macOS.
            lengths, contents = self.unread_input(f, label)
            at = contents.index(REMINDER)
            accepted = pipe_accepts(lengths[:at + 1], fill["facts"])
            detail = {"frames_before_reminder": at, "unread_before_reminder": sum(lengths[:at]),
                      "reminder_frame_bytes": lengths[at], "accepted": accepted, "facts": fill["facts"]}
            self.boundary(f, "input-pipe", **detail)
            self.require(label + ".input-pipe-full", accepted == at, detail)
        expected = "unknown" if captured else "not_sent"
        if not captured:
            self.note(label + ".path", "the reminder frame was never captured; not_sent applies and the "
                      "incomplete-write path was not reached")
        self.notice_expectations(f, 1, label, types=["reminder"], sent=[expected], timeout=timeout)
        self.eq(label + ".reply-notices", (reply or {}).get("data", {}).get("notices"),
                [{"type": "reminder", "sent": expected}])
        self.deadline_ending(f, label, reply, placements=3)
        return expected

    def deadline_ending(self, f, label, reply, *, placements):
        """The deadline decided the placement: stopping was observed once the deadline had
        passed; with starts left it is interrupted with placement_deadline and authoring stays
        open, and on the last allowed placement it is limit_reached (CONTRACT, wire and process;
        INTERFACE 1.6). Returns the recorded (ending, cause)."""
        stop = strict_loads((self.audit_path(f) / "runs" / "1" / "runtime-stop.json").read_bytes())
        self.require(label + ".stopped-after-deadline", stop.get("elapsed_ms", -1) >= stop.get("deadline_ms", 0)
                     and stop.get("groups_gone") is True, stop)
        last = placements == 1
        expected = ("limit_reached", None) if last else ("interrupted", "placement_deadline")
        data = (reply or {}).get("data", {})
        self.eq(label + ".deadline-ending", (data.get("ending"), data.get("cause")), expected)
        _, ended = self.run_ended_record(f, 1)
        body = (ended or {}).get("body", {})
        self.eq(label + ".deadline-run_ended", (body.get("ending"), body.get("cause")), expected)
        self.eq(label + ".deadline-authoring", data.get("headline", {}).get("authoring"),
                {"state": "ended", "ended_by": "limit"} if last else {"state": "open", "ended_by": None})
        status = self.cmd(label + ".deadline-status", ["status", f["reference"]])
        sdata = status.get("data", {})
        self.eq(label + ".deadline-status", (sdata.get("condition"), (sdata.get("runs", {}).get("last") or {}).get("cause"),
                                             self.next_tools(status)),
                (expected[0], expected[1], ["close"] if last else ["close", "run"]))
        return body.get("ending"), body.get("cause")

    # -- A blocked write to the harness and the deadline (CONTRACT, wire and process) ----------

    def blocked_notice_captured(self, f):
        """Whether the input capture already holds every exposed notice, including the one
        whose write cannot complete. Read while run is live: an incomplete record is absent."""
        try:
            lines = (f["witness"] / "harness.jsonl").read_bytes().split(b"\n")[:-1]
            exposed = [transport_loads(line)["exposed"] for line in lines if b'"seq-filled"' in line]
            return (len(exposed) == 1
                    and input_frames(self.captured_channel(f, "input")).count(COMPACTED) >= exposed[0])
        except (OSError, ValueError, KeyError):
            return False

    def blocked_write(self, label, *, placements, timeout, exit_early=False):
        """The harness stops reading, then exposes one compaction boundary more than their
        pinned notices fit in its input pipe by the platform's packing, so Stewart's write of
        the last notice cannot complete while the harness lives. The harness then hangs until
        the supervisor stops its group at the deadline or, with exit_early, exits as soon as
        the driver has seen that notice captured, long before the deadline. No result is
        emitted, so the reminder is never due. Returns the fixture, run reply and run exit."""
        frame = user_frame(COMPACTED)
        tail = ([{"op": "wait_file", "name": "release-exit", "timeout": timeout}, {"op": "exit", "code": 7}]
                if exit_early else [{"op": "hang"}])
        steps = [{"op": "record"}, {"op": "stop_reading"},
                 {"op": "fill_input", "frame_bytes": len(frame), "beyond": 1}] + tail
        f = self.sequence_fixture(label, steps, timeout=timeout, placements=placements)
        self.accept(f)
        blocked = None
        run = self.spawn(f, "run", ["run", f["reference"]])
        try:
            if exit_early:
                blocked = self.await_fact(lambda: self.blocked_notice_captured(f), run["process"], timeout)
                self.boundary(f, "release-exit", blocked_notice_captured=blocked, owner_exit=run["process"].poll())
                publish_witness(f["witness"] / "release-exit", compact({"blocked_notice_captured": blocked}) + b"\n")
            reply = self.collect(run, timeout + 30)
        finally:
            self.stop_leftovers(run)
        self.groups_absent(f)
        if exit_early:
            self.require(label + ".blocked-before-exit", blocked,
                         "the last notice was not captured before the harness exited; no blocked write was established")
        events = self.harness_events(f)
        stopped = [e for e in events if e["event"] == "seq-stopped-reading"]
        self.require(label + ".stopped-reading", len(stopped) == 1 and not stopped[0]["reader_alive"], stopped)
        fill = self.pipe_filled(f, label)
        # Every exposed notice was captured and none was read. The platform's packing admits
        # all but the last, so its write could not complete while the harness lived. A
        # near-limit notice, due in the deadline's last fifth, could only queue behind it.
        lengths, contents = self.unread_input(f, label)
        exposed = fill["exposed"]
        self.eq(label + ".unread-input", (contents[:exposed], [input_kind(c) for c in contents[exposed:]]),
                ([COMPACTED] * exposed, ["near_limit"] * (len(contents) - exposed)))
        accepted = pipe_accepts(lengths[:exposed], fill["facts"])
        detail = {"unread_notices": exposed, "accepted": accepted, "count": fill["count"], "facts": fill["facts"]}
        self.boundary(f, "input-pipe", **detail)
        self.require(label + ".last-write-blocked", accepted == exposed - 1 == fill["count"], detail)
        self.eq(label + ".harness-end", [e["event"] for e in events if e["event"] in
                                         ("seq-hang", "deliberate-interruption", "fatal")],
                ["deliberate-interruption"] if exit_early else ["seq-hang"])
        notices = (reply or {}).get("data", {}).get("notices")
        self.check(label + ".nothing-sent-after-block", isinstance(notices, list) and all(
            n.get("type") == "near_limit" and n.get("sent") != "sent" for n in notices), notices)
        return f, reply, run["process"].returncode

    def runtime_blocked_write(self):
        """CONTRACT, wire and process: the supervisor stops the harness group at the deadline
        on its own clock, so a failed write to the harness that the owner first observes once
        the deadline has passed is the deadline, not a harness error."""
        # Firing control: the write fails only when the deadline's stop closes the pipe.
        f, reply, code = self.blocked_write("blocked-write-deadline", placements=3, timeout=10)
        decided = self.deadline_ending(f, f["label"], reply, placements=3)
        self.eq(f["label"] + ".exit", code, 5)
        # Invariance: on the last allowed placement the same deadline ends it limit_reached.
        f, reply, code = self.blocked_write("blocked-write-deadline-last", placements=1, timeout=10)
        last = self.deadline_ending(f, f["label"], reply, placements=1)
        self.eq(f["label"] + ".exit", code, 0)
        # Differing: the harness exits while the same write is blocked, long before the
        # deadline. Stopping observed before the deadline means the owner observed the exit or
        # failed write first, and that is a harness error.
        f, reply, code = self.blocked_write("blocked-write-exit", placements=3, timeout=30, exit_early=True)
        label = f["label"]
        stop = strict_loads((self.audit_path(f) / "runs" / "1" / "runtime-stop.json").read_bytes())
        self.require(label + ".stopped-before-deadline", stop.get("elapsed_ms", 0) < stop.get("deadline_ms", 0)
                     and stop.get("groups_gone") is True, stop)
        data = (reply or {}).get("data", {})
        self.eq(label + ".ending", (data.get("ending"), data.get("cause"), code), ("interrupted", "protocol_anomaly", 5))
        _, ended = self.run_ended_record(f, 1)
        early = ((ended or {}).get("body", {}).get("ending"), (ended or {}).get("body", {}).get("cause"))
        self.eq(label + ".run_ended", early, ("interrupted", "protocol_anomaly"))
        self.eq(label + ".authoring-open", data.get("headline", {}).get("authoring"), {"state": "open", "ended_by": None})
        self.control("blocked-write-after-deadline-is-deadline",
                     decided == ("interrupted", "placement_deadline") and last == ("limit_reached", None)
                     and early == ("interrupted", "protocol_anomaly"),
                     {"after_deadline": decided, "after_deadline_last_placement": last, "before_deadline": early})

    # -- Result rules (CONTRACT, runtime texts) -------------------------------------------------

    def runtime_result_rules(self):
        # is_error true decides interruption whatever the subtype.
        steps = [{"op": "record"}, {"op": "result", "is_error": True, "subtype": "success", "checkpoint": 0},
                 {"op": "await_input", "expect": "reminder", "timeout": 4, "on_timeout": "continue"}, {"op": "hang"}]
        f = self.sequence_fixture("result-error", steps, timeout=20)
        label = f["label"]
        self.accept(f)
        reply = self.cmd(label + ".run", ["run", f["reference"]], outcome=None, timeout=60)
        self.groups_absent(f)
        data = reply.get("data", {})
        self.eq(label + ".ending", (data.get("ending"), data.get("cause")), ("interrupted", "protocol_anomaly"))
        self.eq(label + ".no-reminder", ([input_kind(c) for c in self.sequence_inputs(f)[1:]], self.notice_records(f),
                                         data.get("notices")), ([], [], []))
        # A well-formed error result is the session's latest reported checkpoint, but not a
        # valid terminal one: the interval it ends stays unknown (CONTRACT, wire and process).
        usage = self.usage_of(self.cmd(label + ".status", ["status", f["reference"]]))
        self.eq(label + ".reported-not-terminal", (usage.get("reported_main_loop"), usage.get("unknown_intervals")),
                (dict(CHECKPOINTS[0]["usage"], harness_turns=CHECKPOINTS[0]["num_turns"]), 1))
        errored = data.get("cause") == "protocol_anomaly"
        # Differing: an ordinary ending whose last result has is_error false is a valid terminal
        # checkpoint, so no interval is unknown.
        steps = [{"op": "record"}, {"op": "result", "is_error": False, "checkpoint": 0},
                 {"op": "await_input", "expect": "reminder"}, {"op": "result", "is_error": False, "checkpoint": 1},
                 {"op": "hang"}]
        f = self.sequence_fixture("result-terminal-valid", steps, timeout=60)
        self.accept(f)
        reply = self.cmd(f["label"] + ".run", ["run", f["reference"]])
        self.groups_absent(f)
        self.eq(f["label"] + ".ending", reply.get("data", {}).get("ending"), "ended_unsubmitted")
        usage = self.usage_of(self.cmd(f["label"] + ".status", ["status", f["reference"]]))
        self.eq(f["label"] + ".terminal", (usage.get("reported_main_loop"), usage.get("unknown_intervals")),
                (dict(CHECKPOINTS[1]["usage"], harness_turns=CHECKPOINTS[1]["num_turns"]), 0))
        # Differing: is_error false with an error subtype is an ordinary turn end.
        steps = [{"op": "record"}, {"op": "result", "is_error": False, "subtype": "error_max_turns", "checkpoint": 0},
                 {"op": "await_input", "expect": "reminder"}, {"op": "submit"}]
        f = self.sequence_fixture("result-subtype-ignored", steps, timeout=60)
        label = f["label"]
        self.accept(f)
        reply = self.cmd(label + ".run", ["run", f["reference"]])
        self.groups_absent(f)
        data = reply.get("data", {})
        self.eq(label + ".ending", data.get("ending"), "sealed")
        self.eq(label + ".reminder", ([input_kind(c) for c in self.sequence_inputs(f)[1:]], data.get("notices")),
                (["reminder"], [{"type": "reminder", "sent": "sent"}]))
        usage = self.usage_of(self.cmd(label + ".status", ["status", f["reference"]]))
        self.eq(label + ".checkpoint", usage.get("reported_main_loop"),
                dict(CHECKPOINTS[0]["usage"], harness_turns=CHECKPOINTS[0]["num_turns"]))
        self.control("result-is-error-decides", errored and data.get("ending") == "sealed")

    def runtime_result_during_call(self):
        if self.variant is None or b"STEWART_TEST_FAULT" not in self.variant.read_bytes():
            return "--variant-binary with claude-code,fault-injection is required to hold a call in execution"
        original = self.binary
        self.binary = self.variant
        try:
            self.result_during_call()
        finally:
            self.binary = original

    def result_during_call(self):
        """A record call is held at log.publish:entry while it executes; the harness then
        emits an ordinary result. That stops the placement interrupted, protocol_anomaly; the
        held call is refused placement_stopped at its link and no reminder is claimed."""
        steps = [{"op": "call_begin", "label": "held", "tool": "record_account", "arguments": {"text": ACCOUNT}},
                 {"op": "wait_file", "name": "emit-result"},
                 {"op": "result", "is_error": False, "checkpoint": 0}, {"op": "marker", "name": "result-emitted"},
                 {"op": "hang"}]
        f = self.sequence_fixture("result-during-call", steps, timeout=60)
        label = f["label"]
        self.accept(f)
        faults = f["witness"] / "faults"
        faults.mkdir()
        env = dict(self.env, STEWART_TEST_FAULT="log.publish:entry=pause", STEWART_TEST_FAULT_DIR=str(faults))
        observe = lambda event, **facts: self.boundary(f, event, **facts)
        run = self.spawn(f, "run", ["run", f["reference"]], env)
        try:
            self.require(label + ".call-held", self.await_fact(
                lambda: bool(list(faults.glob("log.publish*.paused"))), run["process"], 20),
                (f["witness"] / "run.stderr").read_text(errors="replace"))
            sent = [e for e in self.harness_events(f) if e["event"] == "seq-call-sent"]
            self.require(label + ".call-sent", len(sent) == 1, sent)
            group = sent[0]["group"]
            (f["witness"] / "emit-result").write_bytes(b"")
            self.require(label + ".result-emitted", self.await_fact(
                lambda: (f["witness"] / "result-emitted").exists(), run["process"], 10), str(f["witness"]))
            stopped = self.await_fact(lambda: group_observation(group) == "absent", run["process"], 10)
            held = all(not p.with_suffix(".go").exists() for p in faults.glob("*.paused"))
            self.boundary(f, "stopping-before-release", group_absent=stopped, owner_alive=run["process"].poll() is None,
                          still_held=held)
            self.check(label + ".stopped-while-call-executes", stopped and held and run["process"].poll() is None,
                       {"group_absent": stopped, "held": held, "owner_exit": run["process"].poll()})
            release_fault_pauses(faults, observe)
            reply = self.collect(run, 30)
        finally:
            release_fault_pauses(faults, observe)
            self.stop_leftovers(run)
        self.groups_absent(f)
        data = (reply or {}).get("data", {})
        self.eq(label + ".ending", (data.get("ending"), data.get("cause")), ("interrupted", "protocol_anomaly"))
        self.eq(label + ".no-reminder", (self.notice_records(f), data.get("notices")), ([], []))
        self.eq(label + ".no-entry", "entry" in self.log_kinds(f), False)
        call_id = sent[0]["id"]
        rundir = self.audit_path(f) / "runs" / "1"
        calls = [p for p in rundir.glob("call-*.json") if transport_loads(p.read_bytes()).get("id") == call_id]
        self.require(label + ".held-call-retained", len(calls) == 1, [p.name for p in calls])
        result = strict_loads((rundir / calls[0].name.replace("call-", "result-")).read_bytes())["body"]
        core = strict_loads(result["content"][0]["text"].encode())
        self.eq(label + ".held-call-refused", (core.get("outcome"), core.get("reason"), result.get("log_record")),
                ("refused", "placement_stopped", None))
        self.control("result-during-call-stops", data.get("cause") == "protocol_anomaly"
                     and core.get("reason") == "placement_stopped")

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


def claim_continued_session(scenario, scenario_raw):
    """Claim one of three model starts without modifying the scenario or old claims."""
    accounts = scenario.get("continued_accounts")
    if (not isinstance(accounts, list) or len(accounts) != 3
            or any(not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 200 for text in accounts)
            or len(set(accounts)) != 3):
        raise ValueError("continued_accounts must contain three distinct nonblank texts of at most 200 UTF-8 bytes")
    if scenario["mode"] == "continued-deadline":
        artifact = scenario.get("utf8_artifact")
        if (not isinstance(artifact, dict) or set(artifact) != {"label", "text"}
                or not all(isinstance(artifact[key], str) for key in artifact) or not artifact["label"]):
            raise ValueError("continued-deadline requires utf8_artifact with label and text")
    for ordinal in range(1, 4):
        path = Path(scenario["witness"]) / ("model-start-%04d.json" % ordinal)
        try:
            stream = path.open("xb")
        except FileExistsError:
            continue
        session = scenario["session"] + "-placement-%04d" % ordinal
        with stream:
            stream.write(compact({"ordinal": ordinal, "session": session, "mode": scenario["mode"],
                "pid": os.getpid(), "group": os.getpgrp(), "scenario_sha256": sha(scenario_raw),
                "monotonic_ns": time.monotonic_ns()}) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        return ordinal, session
    raise ValueError("three synthetic model starts are already claimed; no fourth placement")


def continued_reentry_handles(reply, ordinal, accounts):
    """Check independently expected prior work before this placement may add anything."""
    if not isinstance(reply, dict):
        raise ValueError("continued re-entry is not a reply object")
    data = reply.get("data")
    prior = ordinal - 1
    if (reply.get("outcome") != "completed" or not isinstance(data, dict)
            or data.get("run") != {"number": ordinal, "continuing": ordinal > 1}
            or data.get("revision") != prior or data.get("authoring") != {"state": "open", "ended_by": None}
            or data.get("seal") != {"state": "absent", "actor": None}
            or data.get("page") != {"bound_revision": prior, "returned": prior, "total": prior, "complete": True}
            or not isinstance(data.get("entries"), list) or len(data["entries"]) != prior
            or not isinstance(data.get("receipts"), list) or len(data["receipts"]) != prior):
        raise ValueError("continued re-entry does not describe the expected prior selection")
    handles = []
    for number, (entry, text) in enumerate(zip(data["entries"], accounts), 1):
        expected = {"id": "e%d" % number, "kind": "record_account", "label": "", "encoding": None,
                    "size": len(text.encode("utf-8")), "preview": text, "preview_complete": True, "problem": None}
        if (not isinstance(entry, dict) or any(entry.get(key) != value for key, value in expected.items())
                or not isinstance(entry.get("entry"), str)
                or not re.fullmatch(r"e%d\.v1\.[a-z2-7]{6}" % number, entry.get("entry", ""))):
            raise ValueError("continued re-entry changed or omitted prior account e%d" % number)
        handles.append(entry["entry"])
    for number, receipt in zip(range(prior, 0, -1), data["receipts"]):
        expected = {"run": number, "tool": "record_account", "action": "add", "target": None,
                    "entry": handles[number - 1], "revision": number}
        if not isinstance(receipt, dict) or any(receipt.get(key) != value for key, value in expected.items()):
            raise ValueError("continued re-entry changed or omitted prior receipt %d" % number)
    return handles


def synthetic_harness(scenario_path, environment_path, argv):
    """Synthetic executable only: no provider or real harness is ever invoked."""
    scenario_raw = Path(scenario_path).read_bytes()
    scenario = strict_loads(scenario_raw)
    witness = Path(scenario["witness"])
    environment_path = Path(environment_path)
    if environment_path.parent != witness:
        raise ValueError("environment witness must be in the scenario witness directory")
    environment_raw = environment_path.read_bytes()
    initial_environment = environment_snapshot(environment_raw)
    event_lock = threading.Lock()
    session_events = None
    ordinal = None

    def event(kind, **data):
        with event_lock:
            raw = compact({"event": kind, "pid": os.getpid(), "monotonic_ns": time.monotonic_ns(), **data}) + b"\n"
            for path in [witness / "harness.jsonl"] + ([session_events] if session_events else []):
                with open(path, "ab") as stream:
                    stream.write(raw)

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
        if scenario["mode"] in CONTINUED_MODES:
            ordinal, scenario["session"] = claim_continued_session(scenario, scenario_raw)
            session_events = witness / ("model-session-%04d.jsonl" % ordinal)
            with session_events.open("xb"):
                pass
            launch.update(ordinal=ordinal, session=scenario["session"])
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
        initial_input = incoming.get(timeout=10)

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

        if scenario["mode"] == "scripted":
            # A specification-derived call list from the outer driver; each step may name
            # values from earlier core replies. Its expectations live in the outer driver.
            replies = {}
            for step in scenario["script"]:
                label, name = step["label"], step["tool"]
                arguments = resolve_script_value(step.get("arguments", {}), replies)
                if step.get("final"):
                    value = frame("tools/call", {"name": name, "arguments": arguments}, identity=step.get("id"))
                    send_frames([value])
                    event("script-final", label=label, id=value["id"], name=name, arguments=arguments,
                          group=os.getpgrp())
                    time.sleep(600)  # Only Stewart's stop after a confirmed submit ends this process.
                    return 9
                page = 0
                while True:
                    if step.get("method"):
                        value = frame(step["method"], step.get("params"), identity=step.get("id"))
                    else:
                        value = frame("tools/call", {"name": name, "arguments": arguments},
                                      identity=step.get("id") if page == 0 else None)
                    send_frames([value])
                    try:
                        response = receive(value["id"])
                    except TimeoutError:
                        response = {}  # unanswered; the outer driver judges the missing reply
                    content = (response.get("result") or {}).get("content") or []
                    core = (strict_loads(content[0]["text"].encode())
                            if content and content[0].get("type") == "text" else None)
                    event("script-step", label=label, page=page, request=value, response=response, core=core)
                    replies.setdefault(label, core)
                    more = script_follow_input(core, name) if step.get("follow") else None
                    if more is None:
                        break
                    arguments, page = more, page + 1
            event("script-ended", end=scenario.get("script_end"))
            if scenario.get("script_end") == "exit":
                event("deliberate-interruption")
                return 7
            raise RuntimeError("a script without a final submit must end by exit")

        if scenario["mode"] == "sequence":
            # A specification-derived schedule of harness events from the outer driver
            # (CLAUDE-CODE.md, "Sequences"). The harness records what it emitted and
            # received; every expectation is in the outer case.
            pending = {}
            for index, step in enumerate(scenario["steps"]):
                op = step["op"]
                event("seq-step", index=index, op=op)
                if op == "record":
                    event("seq-record", reply=tool("record_account", {"text": step.get("text", scenario["account"])}))
                elif op == "result":
                    value = {"type": "result", "subtype": step.get("subtype", "success"),
                             "is_error": step["is_error"], "session_id": scenario["session"]}
                    if step.get("checkpoint") is not None:
                        checkpoint = CHECKPOINTS[step["checkpoint"]]
                        value.update(num_turns=checkpoint["num_turns"], usage=checkpoint["usage"])
                    emit(value)
                elif op == "await_input":
                    deadline = time.monotonic() + step.get("timeout", 10)
                    received = None
                    while received is None:
                        try:
                            value = incoming.get(timeout=max(0.01, deadline - time.monotonic()))
                        except queue.Empty:
                            break
                        kind = input_kind(value.get("message", {}).get("content"))
                        event("seq-input", expect=step["expect"], classified=kind)
                        if kind == step["expect"]:
                            received = value
                    if received is None:
                        event("seq-input-timeout", expect=step["expect"])
                        if step.get("on_timeout", "hang") == "hang":
                            event("seq-hang")
                            time.sleep(600)
                            return 9
                elif op == "compact":
                    for serial in range(step["serial"], step["serial"] + step.get("count", 1)):
                        compacted(serial)
                elif op == "fill_input":
                    # Expose as many boundaries as their pinned notices fit in the unread input
                    # pipe, packed by the platform's rule (pipe_accepts), then `beyond` more.
                    # Probes of fresh pipes with the same capacity witness that rule: the
                    # fitting frames plus one, and the outer driver's next frame after them.
                    facts = input_pipe_facts(0)
                    size = step["frame_bytes"]
                    count = pipe_frames_fit(size, facts)
                    probe = {"frames": pipe_probe([size] * (count + 1), facts["capacity"])}
                    if step.get("next_bytes"):
                        probe["next"] = pipe_probe([size] * count + [step["next_bytes"]], facts["capacity"])
                    exposed = count + step.get("beyond", 0)
                    for serial in range(1, exposed + 1):
                        compacted(serial)
                    event("seq-filled", count=count, exposed=exposed, capacity=facts["capacity"],
                          facts=facts, frame_bytes=size, next_bytes=step.get("next_bytes"), probe=probe)
                elif op == "call_begin":
                    value = frame("tools/call", {"name": step["tool"], "arguments": step.get("arguments", {})})
                    send_frames([value])
                    pending[step["label"]] = value["id"]
                    event("seq-call-sent", label=step["label"], id=value["id"], group=os.getpgrp())
                elif op == "marker":
                    publish_witness(witness / step["name"], compact({"model_pid": os.getpid(), "group": os.getpgrp(),
                                    "monotonic_ns": time.monotonic_ns()}) + b"\n")
                elif op == "wait_file":
                    until = time.monotonic() + step.get("timeout", 30)
                    while not (witness / step["name"]).exists():
                        if time.monotonic() >= until:
                            raise TimeoutError("the outer driver never wrote " + step["name"])
                        time.sleep(0.01)
                    event("seq-file-observed", name=step["name"])
                elif op == "wait_until":
                    # An absolute wall-clock instant the outer driver wrote before starting run;
                    # monotonic clocks need not be shared between processes.
                    while time.time_ns() < scenario[step["key"]]:
                        time.sleep(0.005)
                    event("seq-time-reached", key=step["key"], wall_ns=time.time_ns())
                elif op == "resist_term":
                    # Shutdown must then escalate to KILL. The handler shares no lock with
                    # event(); its separate witness records each TERM received.
                    term_fd = os.open(witness / "term-received.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                    def resisted(signum, frame_, fd=term_fd):
                        os.write(fd, compact({"signal": signum, "monotonic_ns": time.monotonic_ns()}) + b"\n")
                    signal.signal(signal.SIGTERM, resisted)
                    event("seq-resisting-term")
                elif op == "assistant_tool":
                    emit({"type": "assistant", "session_id": scenario["session"], "parent_tool_use_id": None,
                          "message": {"model": scenario["model"], "id": "sequence-%d" % index, "role": "assistant",
                                      "content": [{"type": "tool_use", "id": "toolu_sequence_%d" % index,
                                                   "name": step["name"], "input": {"text": scenario["account"]}}]}})
                elif op == "stop_reading":
                    # Input stays open and unread, so the pipe fills; other holders of its
                    # read side are recorded for review.
                    stop_inputs.set()
                    input_thread.join(timeout=2)
                    capacity = None
                    if sys.platform.startswith("linux"):
                        import fcntl
                        capacity = fcntl.fcntl(0, LINUX_F_GETPIPE_SZ)
                    event("seq-stopped-reading", readers=pipe_readers(0), parent=os.getppid(),
                          reader_alive=input_thread.is_alive(), pipe_capacity=capacity)
                elif op == "submit":
                    prepared = tool("prepare", {})
                    send("tools/call", {"name": "submit", "arguments": {
                        "prepared": prepared["data"]["prepared"], "confirm": True}})
                    event("seq-submit", group=os.getpgrp())
                    time.sleep(600)  # Only Stewart's stop after a confirmed submit ends this process.
                    return 9
                elif op == "exit":
                    event("deliberate-interruption")
                    return step.get("code", 7)
                elif op == "hang":
                    event("seq-hang")
                    time.sleep(600)
                    return 9
                else:
                    raise ValueError("unknown sequence operation: %r" % op)
            raise RuntimeError("a sequence must end by submit, exit or hang")

        if scenario["mode"] == "captured-accounting":
            variant = scenario["accounting_variant"]
            for _ in range(2 if variant == "duplicate" else 1):
                for serial in range(4):
                    emit(c5_partial_frame(scenario["session"], serial))
            cap = copy.deepcopy(C5_CAP)
            cap["session_id"] = scenario["session"]
            emit(cap)
            event("accounting-after-cap", response=tool("what_am_i_working_with", {}))
            if variant == "checkpoint":
                turn_ended(CHECKPOINTS[1])
                supplied = incoming.get(timeout=10)
                if supplied.get("message", {}).get("content") != REMINDER:
                    raise ValueError("ordinary result did not receive the still-unused reminder")
                emit(c5_partial_frame(scenario["session"], 4, later=True))

        if scenario["mode"] == "tool-name":
            name = scenario["assistant_tool"]
            emit({"type": "assistant", "session_id": scenario["session"], "parent_tool_use_id": None,
                  "message": {"model": scenario["model"], "id": "tool-name-control", "role": "assistant",
                              "content": [{"type": "tool_use", "id": "toolu_name_control", "name": name,
                                           "input": {"text": scenario["account"]}}]}})
            event("tool-name-frame-sent", name=name)
            if name != "mcp__stewart__record_account":
                # No self-ending result or voluntary exit: Stewart must stop
                # this live peer for the named protocol defect, not a deadline.
                time.sleep(600)
                return 9

        if scenario["mode"] == "fidelity":
            variant = scenario["fidelity_variant"]
            serial = 0

            def fidelity_start(name, arguments):
                nonlocal serial
                serial += 1
                identity = "toolu_fidelity_%d" % serial
                prefixed = "mcp__stewart__" + name
                emit({"type": "assistant", "session_id": scenario["session"], "parent_tool_use_id": None,
                      "message": {"model": scenario["model"], "id": "msg_fidelity_%d" % serial,
                                  "type": "message", "role": "assistant", "content": [
                                      {"type": "tool_use", "id": identity, "name": prefixed, "input": arguments}]}})
                payload = {"session_id": scenario["session"], "hook_event_name": "PreToolUse",
                           "tool_name": prefixed, "tool_input": arguments, "tool_use_id": identity}
                hook_command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
                probe = subprocess.run(["/bin/sh", "-c", hook_command], input=compact(payload) + b"\n",
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6)
                event("fidelity-hook", payload=payload, exit=probe.returncode,
                      stdout=probe.stdout.decode(), stderr=probe.stderr.decode())
                if probe.returncode or strict_loads(probe.stdout) != {}:
                    raise RuntimeError("fidelity fixture hook did not admit call")
                rpc_id = send("tools/call", {"name": name, "arguments": arguments,
                              "_meta": {"claudecode/toolUseId": identity}})
                return identity, rpc_id

            def fidelity_message(identity, result, change="exact"):
                block = fidelity_echo(identity, result, change)
                blocks = [block, block] if change == "duplicate" else [block]
                # The auxiliary array stays exact in every mismatch control.
                return {"type": "user", "session_id": scenario["session"], "parent_tool_use_id": None,
                        "message": {"role": "user", "content": blocks}, "tool_use_result": result["content"]}

            def fidelity_call(name, arguments, change="exact"):
                identity, rpc_id = fidelity_start(name, arguments)
                response = receive(rpc_id)
                result = response["result"]
                message = fidelity_message(identity, result, change)
                event("fidelity-result", id=rpc_id, tool_use_id=identity, name=name, change=change,
                      response=response)
                if change not in ("missing", "held"):
                    emit(message)
                return strict_loads(result["content"][0]["text"].encode()), message, response

            if "authoring_variant" in scenario:
                def step(label, name, arguments):
                    core, message, response = fidelity_call(name, arguments)
                    event("authoring-step", step=label, name=name, arguments=arguments,
                          core=core, response=response)
                    return core

                first = step("initial", "record_account", authoring_arguments("c4-account"))
                v1 = first["data"]["entry"]
                step("missing-fields", "replace", authoring_arguments("c4-replace-missing", v1))
                step("read-v1", "read", {"source": v1})
                second = step("corrected", "replace", authoring_arguments("c4-replace-corrected", v1))
                v2 = second["data"]["entry"]
                arguments = authoring_arguments("c5-quote-call")
                identity, rpc_id = fidelity_start("record_observation", arguments)
                response = receive(rpc_id)
                result = response["result"]
                captured = authoring_capture("c5-quote-result")["message"]["content"][0]["content"]
                if result != {"content": [{"type": "text", "text": captured}], "isError": True}:
                    raise RuntimeError("captured full refusal differs from the core reply")
                event("fidelity-result", id=rpc_id, tool_use_id=identity, name="record_observation",
                      change=scenario["authoring_variant"], response=response)
                event("authoring-step", step="missing-quote", name="record_observation", arguments=arguments,
                      core=strict_loads(captured.encode()), response=response)
                emit(authoring_echo(scenario["session"], identity, scenario["authoring_variant"]))
                if scenario["authoring_variant"] == "wrong-flag":
                    time.sleep(600)  # Stewart must stop this peer for the changed error flag.
                    return 9
                step("read-v2", "read", {"source": v2})
                third = step("long-replacement", "replace", authoring_arguments("c5-replace-account", v2))
                v3 = third["data"]["entry"]
                step("stale-target", "replace", authoring_arguments("c4-replace-corrected", v2))
                step("read-v3", "read", {"source": v3})
                step("membership", "what_am_i_working_with", {})
                prepared = step("prepare", "prepare", {})
                target = prepared["data"]["prepared"]
                step("selection", "read", {"source": target + "/selection"})
                event("authoring-submit", prepared=target, group=os.getpgrp())
                fidelity_start("submit", {"prepared": target, "confirm": True})
                time.sleep(600)  # No voluntary exit or result can impersonate submit-to-stop.
                return 9

            if not scenario.get("skip_record", False):
                recorded, _, _ = fidelity_call("record_account", {"text": scenario["account"]})
                if recorded.get("outcome") != "completed":
                    raise RuntimeError("fidelity fixture failed to preserve its first account")
            held = None
            for index, specimen in enumerate(FIDELITY_PAGES):
                change = "exact"
                target = 1 if variant == "c3-one" else 2
                if index == target:
                    change = variant if variant in ("changed-text", "wrong-error", "success-flat", "c3-one",
                                                    "c3-two", "reordered", "missing", "duplicate") else "exact"
                    if variant.startswith(("paused-", "late-", "drain-")):
                        change = "held"
                core, message, response = fidelity_call("read", {"source": specimen[3], "start": specimen[4]}, change)
                if core.get("outcome") != "completed":
                    raise RuntimeError("fidelity page was refused")
                if change == "held":
                    held = (message, response["result"])
                if change in ("changed-text", "wrong-error", "success-flat", "c3-one", "c3-two"):
                    time.sleep(600)  # only Stewart's observed stop ends this process
                    return 9
            if variant in ("error-flat", "error-wrong-flag"):
                change = "error-flat" if variant == "error-flat" else "wrong-error"
                refused, _, _ = fidelity_call("record_account", {"text": "Invalid range/quote control.",
                    "citations": [{"source": "materials/control.txt", "start": 0, "end": 49152,
                                   "quote": "TAIL-LABEL: C3_CONTROL_8A79D4"}]}, change)
                if refused.get("reason") != "citation_invalid":
                    raise RuntimeError("short-error control failed for the wrong reason")
                if variant == "error-wrong-flag":
                    time.sleep(600)
                    return 9
            if variant.startswith("drain-"):
                # The held page's echo appears only once Stewart's shutdown TERM arrives:
                # exact for drain-*-exact, the C3 substitution for drain-*-mismatch. The
                # ending is decided first, by an ordinary ending or by the driver's signal.
                message, result = held
                if variant.endswith("-mismatch"):
                    message = fidelity_message(message["message"]["content"][0]["tool_use_id"], result, "c3-two")
                raw = compact(message) + b"\n"
                drain_fd = os.open(witness / "late-echo.bin", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                def drain_echo(signum, frame_, raw=raw, fd=drain_fd):
                    offset = 0
                    while offset < len(raw):
                        offset += os.write(sys.stdout.fileno(), raw[offset:])
                    os.write(fd, raw)
                    os.fsync(fd)
                    os._exit(0)
                signal.signal(signal.SIGTERM, drain_echo)
                if variant.startswith("drain-ordinary"):
                    turn_ended(CHECKPOINTS[0])
                    event("drain-reminder", value=incoming.get(timeout=10))
                    turn_ended(CHECKPOINTS[1])
                    event("drain-second-turn-ended")
                else:
                    publish_witness(witness / "pages-read.json", compact({"model_pid": os.getpid(),
                                    "group": os.getpgrp(), "monotonic_ns": time.monotonic_ns()}) + b"\n")
                time.sleep(600)
                return 9
            prepared, _, _ = fidelity_call("prepare", {})
            if prepared.get("outcome") != "completed":
                raise RuntimeError("fidelity fixture could not prepare submission")
            if variant.startswith("late-"):
                message, result = held
                identity = message["message"]["content"][0]["tool_use_id"]
                if variant == "late-mismatch":
                    message = fidelity_message(identity, result, "c3-two")
                elif variant == "late-duplicate":
                    message = fidelity_message(identity, result, "duplicate")
                # late-missing: the held echo never appears, during the drain or after it.
                raw = b"" if variant == "late-missing" else compact(message) + b"\n"
                # No shared event lock in a signal handler. Its separate witness
                # is outside archive disposal and records completed transmission.
                late_fd = os.open(witness / "late-echo.bin", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                def late_echo(signum, frame):
                    offset = 0
                    while offset < len(raw):
                        offset += os.write(sys.stdout.fileno(), raw[offset:])
                    os.write(late_fd, raw)
                    os.fsync(late_fd)
                    os._exit(0)
                signal.signal(signal.SIGTERM, late_echo)
            identity, rpc_id = fidelity_start("submit", {"prepared": prepared["data"]["prepared"], "confirm": True})
            event("fidelity-submit", id=rpc_id, tool_use_id=identity, group=os.getpgrp())
            if variant.startswith("paused-"):
                until = time.monotonic() + 30
                while not (witness / "release-echo").exists():
                    if time.monotonic() >= until:
                        raise TimeoutError("driver did not release held fidelity echo")
                    time.sleep(0.01)
                message, result = held
                if variant == "paused-mismatch":
                    identity = message["message"]["content"][0]["tool_use_id"]
                    message = fidelity_message(identity, result, "c3-two")
                emit(message)
                event("fidelity-held-echo-sent")
            time.sleep(600)
            return 9

        if scenario["mode"] in CONTINUED_MODES:
            def continued_notice(expected, kind):
                # The six-second fixture can receive the audit's near-limit
                # notice while waiting for the reminder or continuation.
                near = re.escape(NEAR_LIMIT).replace(re.escape("{seconds}"), r"[0-9]+")
                near = near.replace(re.escape("{placements}"), str(3 - ordinal))
                deadline = time.monotonic() + 8
                while True:
                    notice = incoming.get(timeout=max(0.01, deadline - time.monotonic()))
                    content = notice.get("message", {}).get("content")
                    if content == expected:
                        event(kind, ordinal=ordinal, value=notice)
                        return
                    if isinstance(content, str) and re.fullmatch(near, content):
                        event("continued-near-limit", ordinal=ordinal, value=notice)
                    else:
                        raise ValueError("continued placement received an unexpected input while awaiting " + kind)
            event("continued-initial-input", ordinal=ordinal, value=initial_input)
            if ordinal > 1:
                continued_notice(CONTINUATION, "continued-notice")
            event("continued-reentry", ordinal=ordinal, reply=reentry)
            handles = continued_reentry_handles(reentry, ordinal, scenario["continued_accounts"])
            for number, handle in enumerate(handles, 1):
                response = rpc("tools/call", {"name": "read", "arguments": {"source": handle}})
                event("continued-prior-read", ordinal=ordinal, entry=handle, response=response)
                blocks = response.get("result", {}).get("content", [])
                core = strict_loads(blocks[0]["text"].encode()) if blocks else {}
                data = core.get("data") or {}
                text = blocks[1].get("text") if len(blocks) == 2 and blocks[1].get("type") == "text" else data.get("text")
                expected = scenario["continued_accounts"][number - 1]
                if (core.get("outcome") != "completed" or text != expected or data.get("source") != handle
                        or data.get("kind") != "entry" or data.get("complete") is not True
                        or data.get("size") != len(expected.encode("utf-8"))
                        or data.get("range") != [0, len(expected.encode("utf-8"))]):
                    raise ValueError("continued read changed or omitted prior account e%d" % number)
            recorded = tool("record_account", {"text": scenario["continued_accounts"][ordinal - 1]})
            event("continued-account", ordinal=ordinal, reply=recorded)
            if (recorded.get("outcome") != "completed" or recorded.get("data", {}).get("id") != "e%d" % ordinal
                    or recorded.get("data", {}).get("revision") != ordinal):
                raise ValueError("continued account was not added at the expected revision")
            if ordinal == 1:
                turn_ended(CHECKPOINTS[0])
                continued_notice(REMINDER, "continued-reminder")
            for output_tokens in (0, CONTINUED_ASSISTANT_USAGE[ordinal - 1]["output_tokens"]):
                emit({"type": "assistant", "session_id": scenario["session"], "message": {
                    "id": "synthetic-continued-%d" % ordinal, "type": "message", "role": "assistant", "model": "<synthetic>",
                    "content": [{"type": "text", "text": "Synthetic placement %d recorded e%d; this is not an execution finding." % (ordinal, ordinal)}],
                    "usage": dict(CONTINUED_ASSISTANT_USAGE[ordinal - 1], output_tokens=output_tokens)}})
            if ordinal < 3 or scenario["mode"] == "continued-limit":
                event("continued-waiting-for-deadline", ordinal=ordinal)
                time.sleep(600)
                return 9
            # Only the third explicitly started placement may prepare and submit.
            scenario["skip_record"] = True

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
            arguments = (authoring_arguments("c4-partial-account") if scenario.get("captured_partial")
                         else {"text": scenario["account"]})
            recorded = tool("record_account", arguments)
            if recorded.get("outcome") != "completed":
                raise RuntimeError("record_account did not complete: %r" % recorded)
        if scenario["mode"] == "near-limit":
            seconds = scenario["observe_seconds"]
            event("near-limit-window", phase="start", seconds=seconds)
            end = time.monotonic() + seconds
            ended_by = "timeout"
            while time.monotonic() < end:
                try:
                    value = incoming.get(timeout=max(0, end - time.monotonic()))
                except queue.Empty:
                    break
                text = value.get("message", {}).get("content")
                if near_limit_values(text) is None and not (scenario.get("skip_record") and text == CONTINUATION):
                    raise ValueError("unexpected input during near-limit observation")
                if near_limit_values(text) is not None and scenario.get("interrupt_after_notice"):
                    ended_by = "notice"
                    break
            if scenario.get("interrupt_after_notice") and ended_by != "notice":
                raise ValueError("no near-limit notice observed before the interruption bound")
            event("near-limit-window", phase="end", seconds=seconds, ended_by=ended_by)
            event("near-limit-reentry", response=tool("what_am_i_working_with", {}))
            if scenario.get("interrupt_after_notice"):
                event("deliberate-interruption")
                return 7
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


def continued_modes_selftest(check):
    """Actual fake processes and specification-only replies; no Stewart or deadline claim."""
    root = Path(tempfile.mkdtemp(prefix="stewart-c4-synthetic-")).resolve()
    accounts = ["First placement: supplied report remains a claim.\n",
                "Second placement: earlier work was re-read, not repeated.\n",
                "Third placement: preserve both earlier records.\n"]
    artifact = {"label": "UTF-8 continuation", "text": "Café trace.\r\n界\n"}
    peer = '''import json,sys
from pathlib import Path
root=Path(sys.argv[1])
ordinal=max(int(p.stem.split('-')[-1]) for p in root.glob('model-start-*.json'))
ledger_path=root/'peer-ledger.json'
ledger=json.loads(ledger_path.read_bytes()) if ledger_path.exists() else []
def handle(n): return 'e%d.v1.abcdef'%n
for raw in sys.stdin.buffer:
    q=json.loads(raw)
    if 'id' not in q: continue
    result={}
    if q['method']=='initialize': result={'protocolVersion':'2025-11-25','capabilities':{'tools':{}},'serverInfo':{'name':'c4-self-test','version':'1'}}
    if q['method']=='tools/list': result={'tools':[]}
    if q['method']=='tools/call':
        name=q['params']['name']; args=q['params']['arguments']; data={}
        control=(root/'peer-control').read_text() if (root/'peer-control').exists() else ''
        if name=='what_am_i_working_with':
            entries=[{'id':'e%d'%n,'entry':handle(n),'kind':'record_account','label':'','encoding':None,
                      'size':len(item['text'].encode()),'preview':item['text'],'preview_complete':True,'problem':None}
                     for n,item in enumerate(ledger,1)]
            receipts=[{'run':n,'tool':'record_account','action':'add','target':None,'entry':handle(n),'revision':n}
                      for n in range(len(ledger),0,-1)]
            data={'run':{'number':ordinal,'continuing':ordinal>1},'revision':len(ledger),
                  'authoring':{'state':'open','ended_by':None},'seal':{'state':'absent','actor':None},
                  'entries':entries,'receipts':receipts,
                  'page':{'bound_revision':len(ledger),'returned':len(ledger),'total':len(ledger),'complete':True}}
            if control=='missing': data['entries']=[]
            if control=='malformed': data=[]
        elif name=='read':
            number=int(args['source'].split('.')[0][1:]); text=ledger[number-1]['text']
            data={'source':args['source'],'kind':'entry','size':len(text.encode()),'range':[0,len(text.encode())],'complete':True}
            if control=='changed-bytes': text='!'+text[1:]
        elif name in ('record_account','record_artifact'):
            ledger.append({'kind':name,**args}); ledger_path.write_text(json.dumps(ledger))
            data={'id':'e%d'%len(ledger),'entry':handle(len(ledger)),'revision':len(ledger),'encoding':'utf-8' if name=='record_artifact' else None}
        elif name=='prepare': data={'prepared':'ap%d.abcdef'%len(ledger)}
        result={'content':[{'type':'text','text':json.dumps({'outcome':'completed','data':data})}]}
        if name=='read': result['content'].append({'type':'text','text':text})
    print(json.dumps({'jsonrpc':'2.0','id':q['id'],'result':result}),flush=True)
'''
    def setup(label, mode):
        folder = root / label
        folder.mkdir()
        scenario = {"mode": mode, "witness": str(folder), "marker": str(folder / "started"),
                    "config": str(folder), "version": "synthetic-offline-1", "model": MODEL,
                    "family": "open-inquiry", "session": label, "continued_accounts": accounts,
                    "utf8_artifact": artifact, "auth_private": "synthetic-only"}
        raw = compact(scenario) + b"\n"
        (folder / "scenario.json").write_bytes(raw)
        (folder / "peer.py").write_text(peer)
        (folder / "settings.json").write_bytes(b"{}\n")
        (folder / "prompt").write_bytes(b"synthetic C4 self-test\n")
        (folder / "mcp.json").write_bytes(compact({"mcpServers": {"stewart": {"command": sys.executable,
            "args": ["-I", "-B", str(folder / "peer.py"), str(folder)]}}}))
        executable = folder / "synthetic-harness"
        executable.write_bytes(synthetic_executable(Path(__file__).resolve(), folder / "scenario.json", folder))
        executable.chmod(0o700)
        return folder, executable, raw
    def user(text):
        return compact({"type": "user", "session_id": "", "parent_tool_use_id": None,
                        "message": {"role": "user", "content": text}}) + b"\n"
    def launch(folder, executable, ordinal, invalid=False):
        before = {p.name: p.read_bytes() for p in folder.glob("model-start-*.json")}
        auth = subprocess.run([str(executable), "auth", "status"], capture_output=True, timeout=5,
                              env={"PATH": "/usr/bin:/bin"})
        check("continued.%s.%d.auth-does-not-claim" % (folder.name, ordinal), auth.returncode == 0
              and before == {p.name: p.read_bytes() for p in folder.glob("model-start-*.json")})
        process = subprocess.Popen([str(executable), "-p", "--settings", str(folder / "settings.json"),
            "--mcp-config", str(folder / "mcp.json"), "--system-prompt-file", str(folder / "prompt")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"PATH": "/usr/bin:/bin"}, cwd=folder, start_new_session=True)
        events = []
        try:
            if ordinal <= 3:
                process.stdin.write(user("The original supplied question.\n")
                                    + user(REMINDER if ordinal == 1 else CONTINUATION))
                process.stdin.flush()
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                path = folder / "harness.jsonl"
                events = [json.loads(line) for line in path.read_bytes().splitlines()
                          if line] if path.exists() else []
                events = [event for event in events if event["pid"] == process.pid]
                done = any(event["event"] in {"continued-waiting-for-deadline", "fatal"}
                           or (event["event"] == "rpc-transmitted" and any(
                               sent["event"] == "rpc-send" and sent["value"].get("params", {}).get("name") == "submit"
                               and sent["value"].get("id") in event["ids"] for sent in events)) for event in events)
                if done or process.poll() is not None:
                    break
                time.sleep(0.01)
            if invalid:
                process.wait(timeout=3)
            elif process.poll() is None:
                process.terminate()
            out, err = process.communicate(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            if group_observation(process.pid) == "present":
                os.killpg(process.pid, signal.SIGKILL)
        (folder / ("selftest-model-%04d.stdout" % ordinal)).write_bytes(out)
        (folder / ("selftest-model-%04d.stderr" % ordinal)).write_bytes(err)
        check("continued.%s.%d.claims-preserved" % (folder.name, ordinal),
              all((folder / name).read_bytes() == raw for name, raw in before.items()))
        return events, process.returncode
    for mode in sorted(CONTINUED_MODES):
        folder, executable, original = setup(mode, mode)
        earlier_sessions = {}
        for ordinal in (1, 2, 3):
            events, code = launch(folder, executable, ordinal)
            prefix = "continued.%s.%d." % (mode, ordinal)
            check(prefix + "no-fatal", not any(e["event"] == "fatal" for e in events))
            calls = [e["value"]["params"] for e in events if e["event"] == "rpc-send"
                     and e["value"].get("method") == "tools/call"]
            check(prefix + "one-account", [c["arguments"] for c in calls if c["name"] == "record_account"]
                  == [{"text": accounts[ordinal - 1]}])
            check(prefix + "prior-reads", [c["arguments"]["source"] for c in calls if c["name"] == "read"]
                  == ["e%d.v1.abcdef" % n for n in range(1, ordinal)])
            ids = [e["value"]["id"] for e in events if e["event"] == "rpc-send" and "id" in e["value"]]
            check(prefix + "unique-request-ids", len(ids) == len(set(ids)))
            outputs = [e["value"] for e in events if e["event"] == "output"]
            check(prefix + "first-checkpoint-only", [o["usage"] for o in outputs if o["type"] == "result"]
                  == ([CHECKPOINTS[0]["usage"]] if ordinal == 1 else []))
            check(prefix + "assistant-snapshot", [o["message"]["usage"] for o in outputs if o["type"] == "assistant"]
                  == [dict(CONTINUED_ASSISTANT_USAGE[ordinal - 1], output_tokens=0), CONTINUED_ASSISTANT_USAGE[ordinal - 1]])
            check(prefix + "overlapping-message-identity", [o["message"]["id"] for o in outputs if o["type"] == "assistant"]
                  == ["synthetic-continued-%d" % ordinal] * 2)
            final = ordinal == 3 and mode == "continued-deadline"
            check(prefix + "submission-boundary", [c["name"] for c in calls if c["name"] in {"record_artifact", "prepare", "submit"}]
                  == (["record_artifact", "prepare", "submit"] if final else []))
            check(prefix + "prior-session-witnesses-preserved", all((folder / name).read_bytes() == raw
                  for name, raw in earlier_sessions.items()))
            path = folder / ("model-session-%04d.jsonl" % ordinal)
            earlier_sessions[path.name] = path.read_bytes()
            check(prefix + "session-and-scenario", (folder / "scenario.json").read_bytes() == original
                  and json.loads((folder / ("model-start-%04d.json" % ordinal)).read_bytes())["scenario_sha256"] == sha(original)
                  and [o["session_id"] for o in outputs if o["type"] == "system"] == [mode + "-placement-%04d" % ordinal])
        ledger = json.loads((folder / "peer-ledger.json").read_bytes())
        check("continued." + mode + ".cumulative-selection", ledger ==
              [{"kind": "record_account", "text": text} for text in accounts]
              + ([{"kind": "record_artifact", **artifact}] if mode == "continued-deadline" else []))
        events, code = launch(folder, executable, 4, invalid=True)
        check("continued." + mode + ".fourth-refused-before-interaction", code == 8
              and any(e["event"] == "fatal" and "no fourth placement" in e["error"] for e in events)
              and not any(e["event"] in {"input", "launch", "rpc-send", "output"} for e in events)
              and not (folder / "model-start-0004.json").exists())
    for defect in ("missing", "malformed", "changed-bytes"):
        folder, executable, original = setup(defect, "continued-deadline")
        launch(folder, executable, 1)
        prior = (folder / "peer-ledger.json").read_bytes()
        (folder / "peer-control").write_text(defect)
        events, code = launch(folder, executable, 2, invalid=True)
        check("continued.control." + defect, code == 8 and any(e["event"] == "fatal" and
              ("continued re-entry" in e["error"] or "continued read" in e["error"]) for e in events)
              and (folder / "peer-ledger.json").read_bytes() == prior
              and not any(e["event"] == "rpc-send" and e["value"].get("params", {}).get("name")
                          in {"record_account", "record_artifact", "prepare", "submit"} for e in events))
    print("C4 synthetic sequencing self-test evidence retained: " + str(root))


def authoring_selftest(check):
    import answer_witness as aw
    identities = {
        'c4-account.json': (2121, '053812aae916a50722882c238849af911c25b6628f401bb7c83261a1fe7f5328'),
        'c4-replace-missing.json': (1930, 'ef69aa5c530fe963dd5ef898673f102d5f2bdff454d9f4b460bf98368cc823d6'),
        'c4-replace-corrected.json': (1945, 'b8904a9aea51fbaa24a8b1b6459e68d32fa1e35cb96eca131ad4e3f368476bdb'),
        'c5-quote-call.json': (1391, '8bc749174d6ed1c3cde45f52f74acb027cc6d7126d391be98b910f68ee3928a2'),
        'c5-replace-account.json': (29128, 'c773ec95caccd20e1fe9b07d54812746a9da628e49b825293f01d6e836941c62'),
        'c5-quote-result.json': (1256, 'c4d932e271161c9e2de5e009307c9b117b5122efab43a9b403863b6aa459a180'),
        'authoring-materials/R/frsr.R': (7800, '5a96c182f9f322e9d04426c860c2f281d3f23d73ec8ede1993fd8ec5e14e41b0'),
        'authoring-materials/00-review-rules.txt': (1073, '5da12479c3a190c1b3864c2ec65bb09119d326e4e3b16f3be7438cf3ce976487'),
        'authoring-materials/R001-claim.txt': (390, '7a43df94f3dff98410a76eccb1a9c5e9b4cc3fbc3be09b2e8b25f5607ea35f1e'),
        'authoring-materials/R001-receipt.txt': (418, '3edccbfd1c4b0a931dc9509830eb1c22b97187912604221caf807b289e63775a'),
        'authoring-materials/R002-receipt.txt': (399, '53b97e0e54f98326b622911737fc813e2f65fa944bae120350e2774f554ff340'),
        'authoring-materials/R003-receipt.txt': (426, 'dd7dba83039e7a43e84e764f9b036aee8df3ccdd8ce2905e9a7f8b1a0fe8df54'),
        'authoring-materials/R004-claim.txt': (390, 'f80dce402282d4f3a0d7f14be975529d2515946d7fee3ee1cc8c53403692b9db'),
        'authoring-materials/R004-receipt.txt': (418, '801bac2f6439bd9d8898a0e8138a3c74c470712a46df7e0a8de064bfb367a49b'),
        'authoring-materials/R005-receipt.txt': (420, 'cd5032e8b9c0b1bec8685852c3bfa000e2b180371c8e6dbfa987c3a97be0fc53'),
        'authoring-materials/R006-claim.txt': (390, 'f801a3b8460ee9a542dd7f49aae4d5388ca66ea06dd30cf5eba6fb9677695e61'),
        'authoring-materials/R006-receipt.txt': (418, '5f6e37340feb19efde8c30ef3c8e052a4a07eb3ab2da06bac17eb67b1ea0b398'),
        'authoring-materials/R048-receipt.txt': (419, 'f5213f294bdf6a25828cc1ed28225e2ae5dd53f15195e5fd84d066130b1b9d55'),
    }
    for name, identity in identities.items():
        raw = (HERE / "testdata" / "runtime" / name).read_bytes()
        check("authoring.fixture." + name, (len(raw), sha(raw)) == identity)
    missing = authoring_arguments("c4-replace-missing")
    corrected = authoring_arguments("c4-replace-corrected")
    check("authoring.c4-correction-only-citations", corrected == dict(missing, citations=[]))
    for name in ("c4-replace-missing", "c4-replace-corrected", "c5-replace-account"):
        before = authoring_arguments(name)
        after = authoring_arguments(name, "e1.v2.synthetic")
        check("authoring.handle-only." + name, after == dict(before, entry="e1.v2.synthetic"))
    materials = authoring_materials()
    check("authoring.nested-material-directories", fixture_material_index(materials)["directories"] ==
          ["materials", "materials/R"])
    try:
        aw.record_citation(authoring_arguments("c5-quote-call")["citations"][0], materials)
    except aw.CitationDefect as defect:
        check("authoring.missing-quote-independent", defect.reason == "quote_not_found")
    else:
        check("authoring.missing-quote-independent", False)
    citations = [aw.record_citation(c, materials) for c in authoring_arguments("c5-replace-account")["citations"]]
    check("authoring.long-unique-citations", len(citations) == 12 and all("range" in c["stewart"] for c in citations))
    original = authoring_capture("c5-quote-result")
    flat = authoring_echo("fresh-session", "toolu_fresh", "flat")
    expected = copy.deepcopy(original)
    expected["session_id"] = "fresh-session"
    expected["message"]["content"][0]["tool_use_id"] = "toolu_fresh"
    expected["tool_result_meta"][0]["id"] = "toolu_fresh"
    check("authoring.echo-only-session-and-identities", flat == expected)
    full_text = flat["message"]["content"][0]["content"]
    check("authoring.full-refusal-digest", len(full_text.encode()) == 344 and sha(full_text.encode()) ==
          "4d287a2987efce5a306249415d9028f3ab98aa21f9dbac7900dfc91d8af4af09")
    check("authoring.auxiliary-keeps-error-prefix", flat["tool_use_result"] == "Error: " + full_text)
    expected = copy.deepcopy(flat)
    expected["message"]["content"][0]["content"] = [{"type": "text", "text": full_text}]
    check("authoring.array-only-content-form", authoring_echo("fresh-session", "toolu_fresh", "array") == expected)
    expected = copy.deepcopy(flat)
    expected["message"]["content"][0]["is_error"] = False
    check("authoring.wrong-flag-only", authoring_echo("fresh-session", "toolu_fresh", "wrong-flag") == expected)


def self_test():
    import os_fixtures
    checks = []
    def check(name, value):
        checks.append((name, bool(value)))
    authoring_selftest(check)
    scripted_selftest(check)
    sequence_selftest(check)
    check("c5.partial-usage-size", len(compact(C5_PARTIAL_USAGE)) == 251)
    check("c5.partial-usage-digest", sha(compact(C5_PARTIAL_USAGE)) ==
          "db6136588bc9b971abaf7a1a6da35f877e3a05253ddad40d54e5b0ec018272c9")
    check("c5.cap-size", len(compact(C5_CAP) + b"\n") == 447)
    check("c5.cap-digest", sha(compact(C5_CAP) + b"\n") ==
          "7a5ec002a7e8dc060c463d2d7ec9394130cd708c8b36c9074dea6b407e262a78")
    partial_raw = (HERE / "testdata/runtime/c4-partial-account.json").read_bytes()
    check("near-limit.partial-origin", (len(partial_raw), sha(partial_raw)) ==
          (931, '6b1cfbfd4c6d179d195a91489473ff7dcbb463b6f222e2535ad8d45caedbefe0'))
    partial = authoring_arguments("c4-partial-account")
    check("near-limit.partial-preview", len(partial["text"].encode()) == 708 and partial["text"].encode()[:200].decode() ==
          "Partial answer. Covered cases R001 through R016 in ascending order, each read from its claim and receipt. Not covered: R017 through R048; no account is recorded for them, and no conclusion is drawn fo")
    c4_notice = NEAR_LIMIT.format(seconds=12, placements=2)
    c4_input = compact({"type": "user", "session_id": "", "parent_tool_use_id": None,
                        "message": {"role": "user", "content": c4_notice}}) + b"\n"
    check("near-limit.c4-input-size", len(c4_input) == 283)
    check("near-limit.c4-input-digest", sha(c4_input) ==
          "1e6192fe759bc3a8bd0a20708601f7afcad94dddda72290a4ab271adc95c1adf")
    check("near-limit.c4-values", near_limit_values(c4_notice) == {"seconds": 12, "placements": 2})
    check("near-limit.zero-values", near_limit_values(NEAR_LIMIT.format(seconds=0, placements=0)) ==
          {"seconds": 0, "placements": 0})
    for name, value in (("wrong-units", c4_notice.replace("seconds", "tokens")),
                        ("leading-zero", c4_notice.replace("12 seconds", "012 seconds")),
                        ("negative", c4_notice.replace("12 seconds", "-1 seconds")),
                        ("extra-text", c4_notice + " Submit now."),
                        ("missing-ending", c4_notice.rsplit(" When", 1)[0]),
                        ("non-text", None)):
        check("near-limit.refuse-" + name, near_limit_values(value) is None)
    for index, page in enumerate(FIDELITY_PAGES):
        data = fidelity_page(page)
        check("fidelity.source-size-%d" % index, len(data) == page[1])
        check("fidelity.source-digest-%d" % index, sha(data) == page[5])
        check("fidelity.tail-%d" % index, data.endswith(("TAIL-LABEL: " + page[2] + "\n").encode()))
    check("fidelity.two-page-digest", sha(fidelity_page(FIDELITY_PAGES[1]) + fidelity_page(FIDELITY_PAGES[2])) ==
          "67926d9628757c6f2604e9154e8fe6a2ba015ad26846c48ccb1547cc42fff501")
    check("fidelity.notices-grounded", len(C3_NOTICES) == 2 and all(
          "<persisted-output>" in text and "/synthetic/external/tool-result.json" in text
          and "/Users/" not in text and "Preview (first 2KB)" in text for text in C3_NOTICES))
    check("fidelity.notices-omit-tails", all(page[2] not in text for page, text in zip(FIDELITY_PAGES[1:], C3_NOTICES)))
    fixture_materials = {"materials/report.txt":
        "Supplied report: café passed.\r\nThis is not an observed execution.\n".encode()}
    expected_files = [{"name": "materials/report.txt", "size": 67,
        "sha256": "a88e54595d1933a64e9877372085f09efcf70c0be7d7b31875d6d142ae2d08ba", "lines": 2}]
    check("fixture.single-material-invariance", fixture_material_index(fixture_materials) ==
          {"files": expected_files, "directories": ["materials"]})
    fixture_materials.update({"materials/control.txt": fidelity_page(FIDELITY_PAGES[0]),
        "materials/two-pages.txt": fidelity_page(FIDELITY_PAGES[1]) + fidelity_page(FIDELITY_PAGES[2])})
    expected_files = [{"name": "materials/control.txt", "size": 49152,
        "sha256": "947ae167c6e71f036d5c603c3f273706c2252b1b18d381bbf7da3045da49e0d2", "lines": 821}] + expected_files + [
        {"name": "materials/two-pages.txt", "size": 131072,
         "sha256": "67926d9628757c6f2604e9154e8fe6a2ba015ad26846c48ccb1547cc42fff501", "lines": 2186}]
    check("fixture.all-supplied-materials", fixture_material_index(fixture_materials) ==
          {"files": expected_files, "directories": ["materials"]})
    check("fixture.material-order-invariance", fixture_material_index(dict(reversed(list(fixture_materials.items())))) ==
          {"files": expected_files, "directories": ["materials"]})
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
        (outside / "instructions").mkdir()
        (outside / "instructions" / "AGENTS.md").write_bytes(b"# Instructions.\n")
        try:
            validate_work_path(outside / "instructions" / "nested" / "work")
        except ValueError as exc:
            ancestry_refused = "AGENTS.md" in str(exc)
        else:
            ancestry_refused = False
        check("work-preflight.instruction-ancestry-refused", ancestry_refused)
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
    check("environment.nul-decoder-values", environment_snapshot(os_fixtures.raw("env-original.bin"))
          == {"A": "line\nwith=equals", "EMPTY": ""})
    check("environment.changed-value", environment_snapshot(os_fixtures.raw("env-changed-value.bin"))
          == {"A": "line with=equals", "EMPTY": ""})
    check("environment.member-order-invariance", environment_snapshot(os_fixtures.raw("env-reordered.bin"))
          == {"A": "line\nwith=equals", "EMPTY": ""})
    check("environment.empty-decoder", environment_snapshot(os_fixtures.raw("env-empty.bin")) == {})
    try:
        environment_snapshot(os_fixtures.raw("env-original.bin")[:-1])
    except ValueError as error:
        check("environment.captured-truncation-control", str(error) == "environment witness is not NUL terminated")
    else:
        check("environment.captured-truncation-control", False)
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
        check(family + ".order", all(node.keys() == ["name", "description", "inputSchema", "_meta"]
                                     for node in parse(mapped).items))
        check(family + ".result-threshold", all(node.get("_meta").raw ==
              b'{"anthropic/maxResultSizeChars":500000}' for node in parse(mapped).items))
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
        denied = os_fixtures.group_probe("denied")
        check("group-observer.denial-is-unknown", group_observation(owned.pid, denied) == "unknown")
        check("group-observer.captured-present", group_observation(owned.pid, os_fixtures.group_probe("ready-child")) == "present")
        check("group-observer.captured-absence", group_observation(owned.pid, os_fixtures.group_probe("reaped-child")) == "absent")
        check("group-observer.denial-target-invariance", group_observation(owned.pid + 1, denied) == "unknown")
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
        ("near-limit", 2, submitted),
        ("near-limit-interrupt", 2, None),
        ("captured-accounting", 1, submitted),
        ("captured-accounting-duplicate", 1, submitted),
        ("captured-accounting-checkpoint", 2, submitted),
        ("tool-name", 1, submitted),
        ("tool-name-denied", 1, lambda e: e["event"] == "tool-name-frame-sent"),
        ("compaction", 4, submitted),
        ("hooks", 1, submitted),
        ("relay-loss", 1, lambda e: e["event"] == "second-relay"),
        ("checkpoint-then-crash", 2, None),
        ("resume-no-submit", 1, lambda e: e["event"] == "output-transmitted" and e.get("last")),
        ("no-submit", 2, lambda e: e["event"] == "output-transmitted" and e.get("last")),
        ("scripted", 1, lambda e: e["event"] == "script-final"),
        ("scripted-exit", 1, None),
        ("sequence", 3, submitted),
        ("sequence-controls", 1, None),
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
            if mode.startswith("near-limit"):
                scenario["mode"] = "near-limit"
                scenario["observe_seconds"] = 1
                scenario["captured_partial"] = True
                scenario["interrupt_after_notice"] = mode == "near-limit-interrupt"
            if mode.startswith("captured-accounting"):
                scenario["mode"] = "captured-accounting"
                scenario["accounting_variant"] = (mode.removeprefix("captured-accounting-")
                                                 if mode != "captured-accounting" else "missing")
            if mode.startswith("tool-name"):
                scenario["mode"] = "tool-name"
                scenario["assistant_tool"] = ("record_account" if mode.endswith("-denied")
                                             else "mcp__stewart__record_account")
            if mode.startswith("scripted"):
                scenario["mode"] = "scripted"
                scenario["script"] = [script_step("record", "record_account", {"text": "x", "label": "same"},
                                                  id="identity-41")]
                if mode == "scripted":
                    scenario["script"] += [script_step("prepare", "prepare"), script_step(
                        "submit", "submit", {"prepared": {"$ref": ["prepare", "data", "prepared"]}, "confirm": True},
                        final=True)]
                scenario["script_end"] = "exit" if mode == "scripted-exit" else None
            if mode == "sequence":
                scenario["steps"] = [{"op": "record"}, {"op": "result", "is_error": False, "checkpoint": 0},
                                     {"op": "await_input", "expect": "reminder"}, {"op": "compact", "serial": 1},
                                     {"op": "await_input", "expect": "compacted"},
                                     {"op": "marker", "name": "sequence-marker"}, {"op": "submit"}]
            if mode == "sequence-controls":
                scenario["mode"] = "sequence"
                scenario["reached"] = time.time_ns()
                scenario["steps"] = [{"op": "wait_until", "key": "reached"}, {"op": "resist_term"},
                                     {"op": "assistant_tool", "name": "record_account"}, {"op": "stop_reading"},
                                     {"op": "compact", "serial": 1, "count": 3},
                                     {"op": "fill_input", "frame_bytes": 30000, "next_bytes": 4096, "beyond": 1},
                                     {"op": "marker", "name": "stopped-reading"}, {"op": "exit", "code": 7}]
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
            supplied_inputs = [user("synthetic input %d" % n) for n in range(inputs)]
            if mode.startswith("near-limit"):
                supplied_inputs[1] = user(NEAR_LIMIT.format(seconds=12, placements=2))
            if mode == "captured-accounting-checkpoint":
                supplied_inputs[1] = user(REMINDER)
            if mode == "sequence":
                supplied_inputs[1:] = [user(REMINDER), user(COMPACTED)]
            process.stdin.write(b"".join(supplied_inputs))
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
            if mode.startswith("sequence"):
                # The loop's last read can precede a quick exit; take the complete record.
                log = root / "harness.jsonl"
                events = [json.loads(line) for line in log.read_bytes().splitlines()] if log.exists() else []
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
            elif mode.startswith("near-limit"):
                accounts = [e["value"]["params"]["arguments"] for e in events if e["event"] == "rpc-send"
                            and e["value"].get("params", {}).get("name") == "record_account"]
                check("mode." + mode + ".captured-partial", accounts == [authoring_arguments("c4-partial-account")])
                windows = [e.get("phase") for e in events if e["event"] == "near-limit-window"]
                check("mode." + mode + ".window", windows == ["start", "end"])
                check("mode." + mode + ".observed-input", consumed == 2)
                ended_at = next((i for i, e in enumerate(events)
                                 if e["event"] == "near-limit-window" and e["phase"] == "end"), None)
                submitted_at = next((i for i, e in enumerate(events) if submitted(e)), None)
                if mode == "near-limit-interrupt":
                    check("mode." + mode + ".exit-on-notice", code == 7 and ended_at is not None
                          and events[ended_at].get("ended_by") == "notice" and submitted_at is None)
                    check("mode." + mode + ".interruption-witness",
                          sum(e["event"] == "deliberate-interruption" for e in events) == 1)
                else:
                    check("mode." + mode + ".submits-after-window",
                          ended_at is not None and submitted_at is not None and ended_at < submitted_at)
            elif mode.startswith("captured-accounting"):
                partials = [o for o in outputs if o.get("type") == "assistant"]
                expected = 8 if mode.endswith("-duplicate") else 5 if mode.endswith("-checkpoint") else 4
                check("mode." + mode + ".partials", len(partials) == expected
                      and all(o["message"]["usage"] == C5_PARTIAL_USAGE for o in partials))
                check("mode." + mode + ".cap", sum(o.get("type") == "user" and o.get("isSynthetic") is True
                                                 for o in outputs) == 1)
                check("mode." + mode + ".checkpoint", sum(o.get("type") == "result" for o in outputs)
                      == (1 if mode.endswith("-checkpoint") else 0))
                check("mode." + mode + ".submits", sum(submitted(e) for e in events) == 1)
            elif mode.startswith("tool-name"):
                check("mode." + mode + ".assistant",
                      sum(o.get("type") == "assistant" for o in outputs) == 1)
                check("mode." + mode + ".submits", sum(submitted(e) for e in events)
                      == (0 if mode.endswith("-denied") else 1))
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
            elif mode.startswith("scripted"):
                labels = [e["label"] for e in events if e["event"] == "script-step"]
                requests = [e["request"] for e in events if e["event"] == "script-step"]
                final = [e for e in events if e["event"] == "script-final"]
                check("mode." + mode + ".steps", labels == (["record", "prepare"] if mode == "scripted" else ["record"]))
                check("mode." + mode + ".fixed-id", requests and requests[0]["id"] == "identity-41")
                if mode == "scripted":
                    check("mode.scripted.resolved-final", len(final) == 1 and final[0]["arguments"]
                          == {"prepared": "ap1.selftest", "confirm": True} and any(submitted(e) for e in events))
                else:
                    check("mode.scripted-exit.exit", code == 7 and not final
                          and sum(e["event"] == "deliberate-interruption" for e in events) == 1)
            elif mode == "no-submit":
                check("mode.no-submit.results", [o["num_turns"] for o in outputs if o.get("type") == "result"] == [2, 3])
            elif mode == "sequence":
                check("mode.sequence.outputs", kinds == [("system", "init"), ("result", "success"),
                                                         ("system", "compact_boundary")])
                check("mode.sequence.result", [(o["is_error"], o["num_turns"], o["usage"]) for o in outputs
                      if o.get("type") == "result"] == [(False, 2, CHECKPOINTS[0]["usage"])])
                check("mode.sequence.inputs", [(e["expect"], e["classified"]) for e in events if e["event"] == "seq-input"]
                      == [("reminder", "reminder"), ("compacted", "compacted")])
                check("mode.sequence.marker", (root / "sequence-marker").exists())
                check("mode.sequence.order", [e["op"] for e in events if e["event"] == "seq-step"] ==
                      ["record", "result", "await_input", "compact", "await_input", "marker", "submit"])
                check("mode.sequence.submits", sum(submitted(e) for e in events) == 1
                      and any(e["event"] == "seq-submit" for e in events))
            elif mode == "sequence-controls":
                stopped = [e for e in events if e["event"] == "seq-stopped-reading"]
                check("mode.sequence-controls.exit", code == 7)
                check("mode.sequence-controls.time-reached", any(e["event"] == "seq-time-reached" for e in events))
                check("mode.sequence-controls.resisting", any(e["event"] == "seq-resisting-term" for e in events))
                check("mode.sequence-controls.violation", [o["message"]["content"][0]["name"] for o in outputs
                      if o.get("type") == "assistant"] == ["record_account"])
                check("mode.sequence-controls.stopped-reading", len(stopped) == 1 and not stopped[0]["reader_alive"]
                      and stopped[0]["readers"] in (None, []) and (root / "stopped-reading").exists())
                filled = [e for e in events if e["event"] == "seq-filled"]
                fill = filled[0] if len(filled) == 1 else {}
                facts = fill.get("facts") or {}
                check("mode.sequence-controls.fill", bool(fill) and facts.get("capacity", 0) >= 4096
                      and fill["count"] == pipe_frames_fit(30000, facts) and fill["exposed"] == fill["count"] + 1)
                # The harness's probes agree with the packing rule; 4,096 more bytes fit after them.
                check("mode.sequence-controls.fill-probe", bool(fill)
                      and fill["probe"]["frames"]["accepted"] == fill["count"]
                      and fill["probe"]["next"]["accepted"] == pipe_accepts([30000] * fill["count"] + [4096], facts)
                      == fill["count"] + 1)
                check("mode.sequence-controls.compaction-count", kinds.count(("system", "compact_boundary"))
                      == 3 + fill.get("exposed", 0))
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
    continued_modes_selftest(check)
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
