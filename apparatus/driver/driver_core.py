#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Core of the independent black-box acceptance driver for Stewart.

Run the driver through its entrypoint, with an explicit interpreter and
isolated startup:

    python3 -I -B apparatus/driver/stewart_driver.py \\
        --binary /abs/stewart --test-binary /abs/stewart-test \\
        --evidence /abs/new-evidence-folder [--case PATTERN]... [--exclude PATTERN]...

`--list` prints the case inventory; `--self-test` checks the driver's own
helpers, the fake provider and the reacting auditor without any Stewart binary.

This module holds what every case shares: the pinned facts copied from the
specification, strict control JSON, references and handles, inventories,
submission folders, process control, the case registry (`case`), the per-case
context `T`, the `Driver` and the command line. Cases live in `cases_*.py`
modules beside it, which the entrypoint imports in name order; a new group of
cases is a new module and needs no edit here. Run support (the fake provider,
the reacting auditor, the answer witness) lives in its own modules.

The driver is written from docs/INTERFACE.md, docs/QUESTION-FORMS.md,
CONTRACTS.md and ACCEPTANCE.md alone; its authors did not read the
implementation in service/. It drives the binaries only through their command
line (`--json` replies, raw `receipt --read` and `run`), from fresh temporary
homes and working directories in nested paths unrelated to the repository.
The only provider it lets a binary reach is the fake on loopback.

Evidence rules it follows (ACCEPTANCE, "Rules every check follows"):

- Witness. Everything the driver supplies (question files, materials) is kept
  in its own witness under the evidence folder, outside every archive and
  outside anything a case removes. Readback is compared with the witness,
  never with Stewart's records.
- Inventory. Every archive is inventoried (path, type, inode, size, mode,
  mtime, SHA-256) before and after every command; an earlier entry may never
  disappear, change type or inode, or change bytes or mode (C6). The one
  exception is a file first seen while a Stewart process was still running:
  it may have been in progress, so it may grow, keeping its earlier bytes as a
  prefix ("An in-progress new file may be incomplete; it never replaces an
  earlier record"). Folders, homes and working directories must not change at
  all; destinations may only gain entries once a run can deliver.
- Controls. Each case with sabotage controls (INTERFACE Appendix C.2) runs
  three ways: the release binary, the test binary without sabotage (the
  baseline), and the test binary with each named sabotage. A control fires
  when one of its target checks fails; a control that does not fire is a
  broken check and fails the run. Fault cases (C.1) run on the test binary.
- Counts. RESULT.json and RESULTS.md report cases and checks run, passed,
  failed and skipped, which controls fired, and per-operation timings.

Linux-only expectations (the ext4/xfs/btrfs allowlist, OFD lock behaviour,
byte-string file names) are skipped with an explicit reason elsewhere.
The exit status is 0 only when every selected case passed (or was skipped with
a reason) and every control fired; 1 otherwise; 2 for a usage refusal.
"""
from __future__ import annotations

import argparse
import base64
import errno
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unicodedata

if sys.version_info < (3, 8):  # pragma: no cover
    sys.stderr.write("stewart_driver needs Python 3.8 or later\n")
    sys.exit(2)

DRIVER_SCHEMA = "stewart.acceptance-driver/1"
DRIVER_DIR = os.path.dirname(os.path.abspath(__file__))
# Self-tests registered by the driver's modules (selftest decorator below).
SELF_TESTS = []


def selftest(fn):
    """Register fn() -> iterable of (name, ok[, detail]) as a self-test needing no binary."""
    SELF_TESTS.append(fn)
    return fn


def loopback_listen_probe():
    """None when this process can listen on 127.0.0.1, else the reason it cannot."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return None
    except OSError as exc:
        return "loopback listening unavailable: %s" % exc
    finally:
        s.close()
# Paths an emulator creates under HOME on its own account (for example Rosetta's
# translation cache, .cache/rosetta, when x86_64 binaries run on Apple silicon).
# Set by --emulator-home-artifact; additions at these paths, their ancestors or
# their descendants in a watched home are recorded as emulator artifacts, not as
# writes by Stewart. Every other change to a home remains a violation.
EMULATOR_HOME_ARTIFACTS = []


def emulator_artifact(rel):
    for a in EMULATOR_HOME_ARTIFACTS:
        if rel == a or a.startswith(rel + "/") or rel.startswith(a + "/"):
            return True
    return False
REPLY_SCHEMA = "stewart.reply/1"
RECORD_SCHEMA = "stewart.record/1"

# ---------------------------------------------------------------------------
# Pinned facts from the specification (INTERFACE 1.3-1.6, 3, 4, 5, App. A-C;
# QUESTION-FORMS). These are the driver's own copies; Stewart's output is
# compared with them.
# ---------------------------------------------------------------------------

ENVELOPE_ORDER = ("schema", "operation", "outcome", "reason", "message",
                  "effects", "retained", "causes", "next", "data")
OUTCOMES = ("completed", "refused", "failed")
EXIT_FOR_OUTCOME = {"completed": 0, "refused": 3, "failed": 4}
EFFECT_VALUES = {
    "reference": ("none", "created", "unknown"),
    "preparation": ("none", "recorded", "unknown"),
    "attempt": ("none", "recorded", "partial", "unknown"),
    "acceptance": ("absent", "accepted", "unknown"),
    "run": ("not_started", "started", "ended", "still_held", "unknown"),
    "answer": ("unchanged", "changed", "unknown"),
    "seal": ("none", "recorded", "existing", "unknown"),
    "delivery": ("none", "failed", "partial", "verified_with_losses", "verified", "unknown"),
    "closure": ("none", "requested", "unfinished", "complete", "unknown"),
    "raw_capture": ("recorded", "failed", "not_applicable"),
    "diagnostic": ("durable", "reported_only"),
}
OP_EFFECTS = {
    "new": ("reference",),
    "prepare": ("preparation",),
    "commission": ("acceptance", "attempt"),
    "receipt": (),
    "status": (),
    "run": ("run", "answer", "seal", "delivery"),
    "close": ("run", "seal", "delivery", "closure"),
}
# Auditor tools (INTERFACE 1.4): record_<kind> is matched by prefix.
TOOL_EFFECTS = {
    "record_": ("answer", "raw_capture"),
    "replace": ("answer", "raw_capture"),
    "delete": ("answer", "raw_capture"),
    "submit": ("seal", "raw_capture"),
    "list": ("raw_capture",),
    "read": ("raw_capture",),
    "search": ("raw_capture",),
    "what_am_i_working_with": ("raw_capture",),
    "prepare": ("raw_capture",),
}


def tool_effect_keys(tool):
    if isinstance(tool, str) and tool.startswith("record_"):
        return TOOL_EFFECTS["record_"]
    return TOOL_EFFECTS.get(tool)


RUN_ENDINGS = ("sealed", "ended_unsubmitted", "limit_reached", "stopped_by_close", "damaged", "interrupted")
RUN_CAUSES = ("signal", "provider_unavailable", "provider_rejected", "context_exhausted", "provider_refusal",
              "max_tokens", "protocol_anomaly", "archive_write_failed", "process_gone")
ATTEMPT_OUTCOMES = ("response", "response_undecodable", "http_error", "timeout", "connection_failed",
                    "connection_lost", "aborted_by_close", "aborted_by_signal")
DELIVERY_OUTCOMES = ("verified", "verified_with_losses", "partial", "failed", "name_taken")
CLOSED_OUTCOMES = ("closed_without_acceptance", "closed_after_acceptance_before_launch", "closed_delivered",
                   "closed_with_surrendered_losses")
STATUS_CONDITIONS = ("preparing", "intake_in_progress", "intake_failed", "acceptance_uncertain", "log_damaged",
                     "not_started", "run_active", "interrupted", "ended_unsubmitted", "limit_reached", "damaged",
                     "sealed_undelivered", "delivered_open", "awaiting_confirmation", "close_unfinished",
                     "closed_before_launch", "closed")
# Status data members in order after evidence (INTERFACE 5.6).
STATUS_DATA_KEYS = ("headline", "condition", "summary", "evidence", "runs", "allowances", "answer", "seal",
                    "deliveries", "closure", "diagnostics", "provider_url_override", "provider_proxy",
                    "receipt_line")
STATUS_CLOSURE_KEYS = ("requested_at", "before_launch", "accepted", "unfinished_reason", "closed_at", "outcome",
                       "placement", "surrendered")
API_VERSION = "2026-10-21"
MAX_TOKENS_PER_REQUEST = 16000
COMMANDS = ("new", "prepare", "commission", "receipt", "status", "run", "close", "help")
READ_ONLY_OPS = ("status", "receipt", "receipt-read", "help", "usage")
LOG_KINDS = ("reference", "prepared", "intake_planned", "intake_ended", "accepted",
             "run_started", "entry", "seal", "run_ended", "delivery_planned",
             "delivery_ended", "notice", "close_requested", "closed")
INTAKE_ENDED_OUTCOMES = ("selection_changed", "source_unreadable", "capture_failed",
                         "capture_unverified", "receipt_record_failed", "closed",
                         "process_gone")
ITEM_DIAGNOSTICS = ("item_unknown", "item_damaged", "item_missing", "item_unreadable",
                    "item_unsupported")
VERIFY_STATES = ("verified", "damaged", "missing", "unreadable", "unsupported")
BOUNDS = {"question_bytes": 262144, "files": 128, "file_bytes": 16777216,
          "total_bytes": 134217728, "directories": 256, "path_bytes": 1024,
          "path_components": 32, "component_bytes": 255}
COMMISSION_CHECKS = ["capture_digests_match_preparation",
                     "source_identity_unchanged_during_copy",
                     "final_scan_matches_preparation"]
T3_EVIDENCE = {"fact": "intake 1 ended without acceptance",
               "evidence": "intake_planned without outcome; lock free"}
# Every sabotage control of INTERFACE Appendix C.2, in its order.
SABOTAGES = ("accept_without_affirmation", "accept_changed_source", "skip_hidden_entries",
             "normalize_newlines", "follow_symlinks", "readback_live_source",
             "regenerate_arrangement", "rewrite_record_in_place", "remove_partial_on_retry",
             "unknown_as_absent", "select_newer_store", "accept_unknown_field",
             "omit_effects_on_refusal", "whole_from_one_member",
             "extra_tool", "misspell_effort", "effort_in_prompt", "arrangement_mismatch", "read_live_source",
             "normalize_read",
             "paraphrase_question", "read_truncate_silently", "search_omit_last_page", "torn_as_entry",
             "merge_equal_adds", "replay_reexecutes", "stale_target_overwrites", "manager_seal_as_auditor",
             "reentry_omit_entry", "reentry_truncate_page", "reentry_omit_last_page", "reentry_mix_revisions",
             "reentry_placement_allowances", "drop_last_entry", "skip_delivery_verification",
             "deliver_conversation", "regenerate_rendering", "render_conclusion", "remove_superseded_payload",
             "remove_partial_package", "skip_search_capture", "framing_task_elsewhere", "grade_support",
             "block_incomplete", "reset_notice_allowance", "skip_confirmation", "seal_as_stopped",
             "empty_return_before_launch", "slow_list", "hide_provider_message", "rejection_as_unavailable",
             "relative_run_line", "commission_over_network",
             "reset_limits_on_continuation", "fresh_ledger_on_continuation", "drop_refused_capture",
             "manifest_verdict", "ended_as_submitted", "seal_as_delivered", "unknown_membership_empty",
             "stale_preparation_retargets", "prepare_claims_seal", "leak_custody_path",
             "accept_unknown_tool_field", "seal_uncertain_as_none", "submit_claims_delivery")
# Appendix C: the release binary contains none of these names; the test build all of them.
TEST_ENV_NAMES = (b"STEWART_TEST_FAULT", b"STEWART_TEST_SABOTAGE", b"STEWART_TEST_FAULT_DIR",
                  b"STEWART_TEST_TLS_ROOT", b"STEWART_TEST_PROVIDER_TIMEOUT", b"STEWART_TEST_RETRY_DELAYS")

ID_RE = r"[a-z2-7]{16}"
REF_RE = re.compile(r"^stw1:(a" + ID_RE + r"):(s" + ID_RE + r"):(/.*)$")
AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
MP_RE = re.compile(r"^mp([1-9][0-9]*)\.([a-z2-7]{6})$")
REASON_RE = re.compile(r"^[a-z][a-z0-9_]*$")

SCAFFOLD_FIELDS = [b"stewart: question/1", b"family: open-inquiry",
                   b"model: REPLACE-WITH-MODEL",
                   b"destination: REPLACE-WITH-ABSOLUTE-DIRECTORY",
                   b"limit-turns: 200", b"limit-input-tokens: 20000000",
                   b"limit-output-tokens: 400000"]
# The two comment lines of the 3.2 template about the optional effort, between the model
# field and the destination comment. The scaffold carries them and no `effort` field.
SCAFFOLD_EFFORT_COMMENTS = [
    b"# Optional effort for every request: low, medium, high, xhigh or max, as a",
    b"# line such as \"effort: high\". Without one, the model's provider default applies.",
]
SCAFFOLD_DESTINATION_COMMENT = b"# Existing directory in which Stewart creates the return package."
SCAFFOLD_COMMENTS = [
    b"# Question family: open-inquiry, inquiry-framing or comparison.",
    b"# Run `stewart help forms` to read each family's instructions.",
    b"# Provider model used for every run of this audit.",
] + SCAFFOLD_EFFORT_COMMENTS + [
    SCAFFOLD_DESTINATION_COMMENT,
    b"# Cumulative limits across all runs, from the provider's usage reports.",
    b"# Write your question below the closing --- line.",
]
# The effort levels of the `effort` front matter key (3.2), in the table's order. Stewart knows
# these names, not which levels a model accepts (CONTRACTS); a provider refusing one is a
# provider rejection (6.5).
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

# QUESTION-FORMS pinned texts: lines of a quoted paragraph joined by one space,
# paragraphs by two LF bytes, no trailing LF.
ORIENTATION = (
    "You are the auditor in a Stewart audit. The first user message is the manager's question, exactly as they wrote it. The materials they selected can be read with the list, read and search tools. The question and those materials are your whole world: you have no shell, no other files, no network, no way to run code and no way to ask the manager anything. Reports, logs and test results in the materials are claims by their authors, not executions you witnessed."
    "\n\n"
    "Your answer is the entries you record with the record tools, and each entry is attributed to you. You may record that the material is inadequate, that you are uncertain, that you disagree with the question's premise or that you found no supported finding. None of these needs a defect, a winner or a repair. An answer with missing sections, or with no entries, can be submitted."
    "\n\n"
    "Record your account early, even briefly, and replace it as your work develops. Replacing an entry keeps its place. To cite, use the ranges that read and search return, or give a quote of exact text. Searching for distinctive text gives a ready citation. Citations are checked only for exact location and quotation, never for whether they support what you say."
    "\n\n"
    "Use handles exactly as tools return them. If a tool says a handle is stale, read the current one before replacing it. If your context was summarized, or you are unsure what you have recorded, call what_am_i_working_with."
    "\n\n"
    "When you are ready, call prepare to see exactly what would be sealed, then call submit with that handle and confirm set to true. Submitting seals your answer, and it cannot be edited afterwards. Your limits are cumulative across the whole audit; what_am_i_working_with shows what remains."
)
FAMILY_TEXT = {
    "open-inquiry": "Address the question from the supplied materials. Begin your account with your direct response to the question and its reach, including when you cannot answer it as asked; do not leave a decisive inability only in a final limitation. Record observations that connect what you found to its basis in the materials. Record limits on what the materials let you establish. No positive finding and no universal assurance is required. When you use a label from the materials, such as a requirement number, explain it in ordinary words the first time.",
    "inquiry-framing": "The manager has described a concern. Formulate a working question that the supplied materials can bear on, record it, and record how it relates to the original concern. Then investigate it in this audit and record what you find. The manager's question stays as written; if it is already precise, it can be your working question. If useful bounded investigation is not possible with these materials, say so and explain why. Begin your account with your direct response and its reach. Record observations with their basis and record the limits of what you could establish. When you use a label from the materials, explain it in ordinary words the first time.",
    "comparison": "Compare the alternatives the question names, using the supplied evidence. Record the criterion, saying what the manager supplied and what is your interpretation of it. Use a comparison entry for a finding that relates the alternatives to each other, and an observation for a finding about one alternative or about the materials. Distinguish what you reasoned from the source yourself from what supplied materials report. If the evidence is unequal, the criterion is unavailable or a comparison is not possible, say so; no winner is required. Begin your account with your direct response and its reach, and record the limits of what you could establish. When you use a label from the materials, explain it in ordinary words the first time.",
}
REMINDER = "This turn ended without a submission. Your recorded answer remains unsealed. If you intend to submit it, use prepare and confirm its handle with submit."
NEAR_LIMIT = "Allowance notice: {turns} turns, {input_tokens} input tokens and {output_tokens} output tokens remain for this audit. When an allowance runs out the run stops, and an unsubmitted answer stays unsubmitted."
CONTINUATION = "This audit is continuing in a new conversation after an earlier run ended. Your recorded work is preserved, but this conversation does not contain it. Call what_am_i_working_with to see what you have recorded. Your last action before the interruption may or may not have been recorded; check before repeating it."

FAMILY_TOOLS = {
    "open-inquiry": ["record_account", "record_observation", "record_limit"],
    "inquiry-framing": ["record_working_question", "record_relation", "record_observation",
                        "record_account", "record_limit"],
    "comparison": ["record_criterion", "record_comparison", "record_observation",
                   "record_account", "record_limit"],
}
TOOL_DESC = {
    "list": "List the captured materials: their names (materials/…), sizes and line counts. Long lists come in pages.",
    "read": "Read exact text from the question (source \"question\"), a material (materials/…), one of your entries (its handle) or a prepared view. Returns up to 64 KiB per call, and a next call when more remains. For the question and materials, the reply's cite is a ready citation for what was returned. The exact text is the second content block, or the reply's text field when the page is blank; bytes recorded as base64 come in its base64 field.",
    "search": "Find exact, case-sensitive text in the question and all materials, or in the sources you name. Each hit's cite is a ready citation. The reply says whether the whole scope was searched; an incomplete search does not show that text is absent.",
    "record_account": "Record your account: the direct response to the question and its reach, including any inability to answer it as asked.",
    "record_observation": "Record one observation and its basis in the materials.",
    "record_limit": "Record a limit on what the materials let you establish.",
    "record_working_question": "Record the working question you will investigate.",
    "record_relation": "Record how the working question relates to the manager's original concern.",
    "record_criterion": "Record the criterion for the comparison, saying what the manager supplied and what is your interpretation.",
    "record_comparison": "Record a finding that relates the alternatives to each other.",
    "record_artifact": "Record a free-form artifact with a label: text, or base64 for bytes that are not text. It belongs to your answer but fills no section.",
    "replace": "Replace exactly one version of an entry, given its handle. Supply every field: text, citations and label for a recorded entry; label and text or base64 for an artifact. The entry keeps its place.",
    "delete": "Remove exactly one version of an entry from your answer.",
    "what_am_i_working_with": "Show the audit's state: what you have recorded and its handles, recent edits and refusals, the question and materials, and your remaining allowances. Use it when continuing or after your context was summarized.",
    "prepare": "Make the exact candidate that submit would seal, with its Markdown rendering and factual notes on empty sections. It changes nothing, and you can keep editing.",
    "submit": "Seal a prepared candidate as your answer. Without confirm set to true this is a dry run. After a confirmed submit the answer cannot be edited.",
}
CITATION_SCHEMA = {
    "type": "object",
    "properties": {
        "source": {"type": "string", "description": "question or materials/<name>."},
        "start": {"type": "integer", "minimum": 0, "description": "Byte offset where the cited span begins."},
        "end": {"type": "integer", "minimum": 1, "description": "Byte offset just after the cited span."},
        "quote": {"type": "string", "description": "Exact text of the cited span."},
    },
    "required": ["source"],
    "additionalProperties": False,
}
ARRANGEMENT_MEMBERS = ("model", "anthropic_version", "max_tokens_per_request", "system", "tools",
                       "request_extra", "texts", "limits", "near_limit_percent", "retry",
                       "request_timeout_seconds", "reader", "renderer", "family", "bindings")


def expected_tools(family):
    """The family's tools array (QUESTION-FORMS "Tools"), as parsed JSON values."""
    def s(desc):
        return {"type": "string", "description": desc}

    def cites(desc):
        return {"type": "array", "items": CITATION_SCHEMA, "maxItems": 64, "description": desc}

    record = {
        "text": s("Entry text. It may be empty."),
        "citations": cites("Citations: {source, start, end, quote?} from read or search, or {source, quote} with exact text."),
        "label": s("Optional short label shown in the rendering."),
    }
    table = [
        ("list", {"cursor": s("Cursor from the previous list reply's next call, for the next page.")}, []),
        ("read", {"source": s("What to read: question, materials/<name>, one of your entry handles or a prepared view."),
                  "start": {"type": "integer", "minimum": 0,
                            "description": "Byte offset to start from. Default 0; use the start that a reply's next call gives."}},
         ["source"]),
        ("search", {"text": s("Exact text to find. Matching is literal and case-sensitive."),
                    "sources": {"type": "array", "items": {"type": "string"}, "maxItems": 128,
                                "description": "Sources to search. Default: the question and every material."},
                    "cursor": s("Cursor from the previous search reply's next call. Give it with the same text and sources.")},
         ["text"]),
    ]
    table += [(k, record, ["text"]) for k in FAMILY_TOOLS[family]]
    table += [
        ("record_artifact", {"label": s("Required short label for the artifact, shown in the rendering."),
                             "text": s("Artifact content as text."),
                             "base64": s("Artifact bytes as base64, for content that is not text.")}, ["label"]),
        ("replace", {"entry": s("The exact handle of the entry version to replace."),
                     "label": s("Required label for the replacement, shown in the rendering. Give the current label to keep it."),
                     "text": s("Replacement text."),
                     "citations": cites("Replacement citations, as for the record tools. Use [] for none."),
                     "base64": s("Replacement artifact bytes as base64.")}, ["entry", "label"]),
        ("delete", {"entry": s("The exact handle of the entry version to remove.")}, ["entry"]),
        ("what_am_i_working_with", {"page": s("Cursor from the previous reply's next call, for the next page of entries.")}, []),
        ("prepare", {}, []),
        ("submit", {"prepared": s("The handle that prepare returned."),
                    "confirm": {"type": "boolean", "description": "Set to true to seal. Otherwise this is a dry run."}},
         ["prepared"]),
    ]
    return [{"name": n, "description": TOOL_DESC[n],
             "input_schema": {"type": "object", "properties": p, "required": r,
                              "additionalProperties": False}}
            for n, p, r in table]


def pinned_json_string(text):
    """JSON string escaping of QUESTION-FORMS "The structured answer"."""
    out = ['"']
    for ch in text:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif o < 0x20:
            out.append({8: '\\b', 12: '\\f', 10: '\\n', 13: '\\r', 9: '\\t'}.get(o, '\\u%04x' % o))
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)


def expected_system_bytes(family):
    return ('[{"type":"text","text":%s},{"type":"text","text":%s}]'
            % (pinned_json_string(ORIENTATION), pinned_json_string(FAMILY_TEXT[family]))).encode("utf-8")


# ---------------------------------------------------------------------------
# Strict control JSON (INTERFACE 1.2), used for every reply and record read.
# ---------------------------------------------------------------------------

class StrictJSONError(ValueError):
    pass


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise StrictJSONError("duplicate key %r (compared after escape decoding)" % k)
        out[k] = v
    return out


def _no_float(text):
    raise StrictJSONError("number %s is not an integer" % text)


def _unsigned_int(text):
    if text.startswith("-"):
        raise StrictJSONError("signed integer %s" % text)
    return int(text)


def _no_constant(text):
    raise StrictJSONError("constant %s" % text)


_DECODER = json.JSONDecoder(object_pairs_hook=_pairs, parse_float=_no_float,
                            parse_int=_unsigned_int, parse_constant=_no_constant, strict=True)
_JSON_WS = " \t\n\r"


def _walk_strict(value, depth, pointer):
    if isinstance(value, dict):
        if depth + 1 > 16:
            raise StrictJSONError("nesting deeper than 16 at %s" % (pointer or "/"))
        for k, v in value.items():
            _check_string(k, pointer + "/" + k)
            _walk_strict(v, depth + 1, pointer + "/" + k)
    elif isinstance(value, list):
        if depth + 1 > 16:
            raise StrictJSONError("nesting deeper than 16 at %s" % (pointer or "/"))
        for i, v in enumerate(value):
            _walk_strict(v, depth + 1, "%s/%d" % (pointer, i))
    elif isinstance(value, str):
        _check_string(value, pointer)


def _check_string(s, pointer):
    for ch in s:
        o = ord(ch)
        if o == 0:
            raise StrictJSONError("NUL in string at %s" % (pointer or "/"))
        if 0xD800 <= o <= 0xDFFF:
            raise StrictJSONError("lone surrogate at %s" % (pointer or "/"))


def strict_loads(data):
    """Decode bytes as strict control JSON or raise StrictJSONError."""
    if isinstance(data, str):
        data = data.encode("utf-8", "surrogatepass")
    if data.startswith(b"\xef\xbb\xbf"):
        raise StrictJSONError("byte-order mark")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StrictJSONError("invalid UTF-8 at byte %d" % exc.start)
    idx = 0
    while idx < len(text) and text[idx] in _JSON_WS:
        idx += 1
    try:
        value, end = _DECODER.raw_decode(text, idx)
    except StrictJSONError:
        raise
    except ValueError as exc:
        raise StrictJSONError("not JSON: %s" % exc)
    if text[end:].strip(_JSON_WS):
        raise StrictJSONError("data after the top-level value")
    _walk_strict(value, 0, "")
    return value


def is_compact_json(text):
    """True when no JSON whitespace occurs outside strings."""
    in_str = esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in _JSON_WS:
            return False
    return True


# ---------------------------------------------------------------------------
# Identifiers, references and handles (INTERFACE 2).
# ---------------------------------------------------------------------------

_SAFE_BYTES = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/._-")


def encode_root(path):
    return "".join(chr(b) if b in _SAFE_BYTES else "%%%02X" % b for b in path.encode("utf-8"))


def decode_root(enc):
    """Decode a reference's root; None when it is not in canonical form."""
    out = bytearray()
    i = 0
    while i < len(enc):
        c = enc[i]
        if c == "%":
            h = enc[i + 1:i + 3]
            if len(h) != 2 or not re.fullmatch(r"[0-9A-F]{2}", h):
                return None
            b = int(h, 16)
            if b in _SAFE_BYTES:
                return None
            out.append(b)
            i += 3
        else:
            if ord(c) > 127 or ord(c) not in _SAFE_BYTES:
                return None
            out.append(ord(c))
            i += 1
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError:
        return None


def make_reference(audit, store, root):
    return "stw1:%s:%s:%s" % (audit, store, encode_root(root))


def parse_reference(ref):
    m = REF_RE.match(ref or "")
    if not m:
        return None
    root = decode_root(m.group(3))
    if root is None:
        return None
    return {"audit": m.group(1), "store": m.group(2), "root": root}


def handle_check(store, audit, kind, obj, binding):
    """First 6 characters of lowercase base32 SHA-256 over the handle preimage (2.3)."""
    parts = ["stewart.handle/1", store, audit, kind, obj] + [str(b) for b in binding]
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).digest()
    return base64.b32encode(digest).decode("ascii").lower()[:6]


def random_id(prefix):
    alphabet = "abcdefghijklmnopqrstuvwxyz234567"
    raw = os.urandom(10)
    bits = int.from_bytes(raw, "big")
    return prefix + "".join(alphabet[(bits >> (5 * (15 - i))) & 31] for i in range(16))


# ---------------------------------------------------------------------------
# Small helpers.
# ---------------------------------------------------------------------------

def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def line_count(data):
    n = data.count(b"\n")
    return n + (1 if data and not data.endswith(b"\n") else 0)


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def short(value, limit=600):
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=repr)
    except Exception:
        text = repr(value)
    return text if len(text) <= limit else text[:limit] + "...(%d chars)" % len(text)


def iter_values(obj):
    """Every scalar and container value in a decoded JSON value, depth first."""
    yield obj
    if isinstance(obj, dict):
        for v in obj.values():
            for x in iter_values(v):
                yield x
    elif isinstance(obj, list):
        for v in obj:
            for x in iter_values(v):
                yield x


def contains_string(obj, s):
    return any(isinstance(v, str) and v == s for v in iter_values(obj))


def mentions(obj, s):
    """True when a string value contains s, or an integer equals int(s)."""
    for v in iter_values(obj):
        if isinstance(v, str) and s in v:
            return True
        if isinstance(v, int) and not isinstance(v, bool) and str(v) == s:
            return True
    return False


def norm_ws(text):
    text = re.sub(r"(?m)^\s*>\s?", " ", text)
    return " ".join(text.split())


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def is_linux():
    return sys.platform.startswith("linux")


def fs_type_of(path):
    """The filesystem type holding path on Linux (from mountinfo), else None."""
    if not is_linux():
        return None
    try:
        lines = open("/proc/self/mountinfo", encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return None
    best, best_type = "", None
    real = os.path.realpath(path)
    for line in lines:
        parts = line.split()
        try:
            sep = parts.index("-")
        except ValueError:
            continue
        mp = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), parts[4])
        if real == mp or real.startswith(mp.rstrip("/") + "/") or mp == "/":
            if len(mp) >= len(best):
                best, best_type = mp, parts[sep + 1]
    return best_type


def tmpfs_mounts():
    if not is_linux():
        return []
    out = []
    try:
        for line in open("/proc/self/mountinfo", encoding="utf-8", errors="replace"):
            parts = line.split()
            sep = parts.index("-")
            if parts[sep + 1] in ("tmpfs", "ramfs"):
                out.append((parts[4], parts[sep + 1]))
    except (OSError, ValueError):
        pass
    return out


# ---------------------------------------------------------------------------
# Inventories (C6) taken through descriptor-relative traversal, so a planted
# link is recorded rather than followed and deep paths need no PATH_MAX.
# ---------------------------------------------------------------------------

_FLAG_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_FLAG_DIR = getattr(os, "O_DIRECTORY", 0)
_FLAG_NONBLOCK = getattr(os, "O_NONBLOCK", 0)


class DigestCache:
    def __init__(self):
        self.cache = {}

    def digest(self, dir_fd, name, st):
        key = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        if key in self.cache:
            return self.cache[key]
        try:
            fd = os.open(name, os.O_RDONLY | _FLAG_NOFOLLOW | _FLAG_NONBLOCK, dir_fd=dir_fd)
        except OSError as exc:
            return "unreadable:%s" % errno.errorcode.get(exc.errno, exc.errno)
        try:
            h = hashlib.sha256()
            while True:
                chunk = os.read(fd, 1 << 20)
                if not chunk:
                    break
                h.update(chunk)
        finally:
            os.close(fd)
        value = h.hexdigest()
        self.cache[key] = value
        return value


def _kind_of(mode):
    if stat.S_ISDIR(mode):
        return "dir"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISLNK(mode):
        return "link"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    return "special"


def snapshot(path, cache):
    """Map relative path -> entry dict for the tree at path; None when absent."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        return {"": {"kind": "error", "error": str(exc)}}
    out = {"": {"kind": _kind_of(st.st_mode), "ino": st.st_ino, "mode": stat.S_IMODE(st.st_mode)}}
    if not stat.S_ISDIR(st.st_mode):
        return out
    try:
        fd = os.open(path, os.O_RDONLY | _FLAG_DIR | _FLAG_NOFOLLOW)
    except OSError as exc:
        out[""]["error"] = str(exc)
        return out
    try:
        _walk(fd, "", out, cache)
    finally:
        os.close(fd)
    return out


def _walk(fd, prefix, out, cache):
    try:
        with os.scandir(fd) as it:
            entries = sorted(it, key=lambda e: os.fsencode(e.name))
    except OSError as exc:
        out[prefix.rstrip("/")]["error"] = "unlistable: %s" % exc
        return
    for e in entries:
        rel = prefix + e.name
        try:
            st = e.stat(follow_symlinks=False)
        except OSError as exc:
            out[rel] = {"kind": "error", "error": str(exc)}
            continue
        kind = _kind_of(st.st_mode)
        entry = {"kind": kind, "ino": st.st_ino, "mode": stat.S_IMODE(st.st_mode)}
        if kind == "file":
            entry["size"] = st.st_size
            entry["mtime_ns"] = st.st_mtime_ns
            entry["sha256"] = cache.digest(fd, e.name, st)
        elif kind == "link":
            try:
                entry["target"] = os.readlink(e.name, dir_fd=fd)
            except OSError as exc:
                entry["target"] = "error: %s" % exc
        out[rel] = entry
        if kind == "dir":
            try:
                sub = os.open(e.name, os.O_RDONLY | _FLAG_DIR | _FLAG_NOFOLLOW, dir_fd=fd)
            except OSError as exc:
                entry["error"] = "unopenable: %s" % exc
                continue
            try:
                _walk(sub, rel + "/", out, cache)
            finally:
                os.close(sub)


def compare_snapshots(before, after, only_additions):
    """(violations, additions). With only_additions, earlier entries must stay identical."""
    violations, added = [], []
    if before is None and after is None:
        return violations, added
    if before is None:
        if only_additions:
            return violations, sorted(after)
        return [("created", "")], sorted(after)
    if after is None:
        return [("removed", "")], added
    for rel, b in before.items():
        a = after.get(rel)
        if a is None:
            violations.append(("removed", rel))
        elif a.get("kind") != b.get("kind") or a.get("ino") != b.get("ino"):
            violations.append(("replaced", rel))
        elif b.get("kind") == "file" and (a.get("size"), a.get("sha256"), a.get("mtime_ns")) != (
                b.get("size"), b.get("sha256"), b.get("mtime_ns")):
            violations.append(("rewritten", rel))
        elif a.get("mode") != b.get("mode"):
            violations.append(("mode_changed", rel))
        elif b.get("kind") == "link" and a.get("target") != b.get("target"):
            violations.append(("retargeted", rel))
    for rel in after:
        if rel not in before:
            added.append(rel)
    if not only_additions and added:
        violations.extend(("added", rel) for rel in sorted(added))
    return violations, sorted(added)


# ---------------------------------------------------------------------------
# Building submission folders through descriptors.
# ---------------------------------------------------------------------------

def F(rel, data):
    return ("file", rel.encode("utf-8") if isinstance(rel, str) else rel, data)


def D(rel):
    return ("dir", rel.encode("utf-8") if isinstance(rel, str) else rel, None)


def L(rel, target):
    return ("link", rel.encode("utf-8") if isinstance(rel, str) else rel, target)


def FIFO(rel):
    return ("fifo", rel.encode("utf-8") if isinstance(rel, str) else rel, None)


def SOCK(rel):
    return ("socket", rel.encode("utf-8") if isinstance(rel, str) else rel, None)


def HARD(rel, other):
    return ("hard", rel.encode("utf-8") if isinstance(rel, str) else rel,
            other.encode("utf-8") if isinstance(other, str) else other)


def BIG(rel, size, seed):
    return ("big", rel.encode("utf-8") if isinstance(rel, str) else rel, (size, seed))


def big_chunks(size, seed):
    """Deterministic valid UTF-8 text without NUL, generated in 1 MiB pieces."""
    line = (hashlib.sha256(seed.encode("utf-8")).hexdigest() + "\n").encode("ascii")
    block = line * ((1 << 20) // len(line) + 1)
    left = size
    while left > 0:
        piece = block[:min(left, len(block))]
        yield piece
        left -= len(piece)


def big_identity(size, seed):
    h = hashlib.sha256()
    lf = 0
    last = b""
    for piece in big_chunks(size, seed):
        h.update(piece)
        lf += piece.count(b"\n")
        last = piece[-1:]
    lines = lf + (1 if size and last != b"\n" else 0)
    return {"size": size, "sha256": h.hexdigest(), "lines": lines}


class SocketHolder:
    sockets = []


def _open_dir_path(root_fd, parts, create):
    fd = os.dup(root_fd)
    for part in parts:
        try:
            if create:
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            nfd = os.open(part, os.O_RDONLY | _FLAG_DIR | _FLAG_NOFOLLOW, dir_fd=fd)
        except Exception:
            os.close(fd)
            raise
        os.close(fd)
        fd = nfd
    return fd


def build_entries(base, entries):
    """Create entries (relative byte paths) below the existing directory base."""
    root_fd = os.open(base, os.O_RDONLY | _FLAG_DIR | _FLAG_NOFOLLOW)
    try:
        for kind, rel, payload in entries:
            parts = [p for p in rel.split(b"/")]
            parent = _open_dir_path(root_fd, parts[:-1], True)
            name = parts[-1]
            try:
                if kind == "dir":
                    try:
                        os.mkdir(name, 0o755, dir_fd=parent)
                    except FileExistsError:
                        pass
                elif kind == "file":
                    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _FLAG_NOFOLLOW, 0o644, dir_fd=parent)
                    try:
                        view = memoryview(payload)
                        while view:
                            n = os.write(fd, view)
                            view = view[n:]
                    finally:
                        os.close(fd)
                elif kind == "big":
                    size, seed = payload
                    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _FLAG_NOFOLLOW, 0o644, dir_fd=parent)
                    try:
                        for piece in big_chunks(size, seed):
                            view = memoryview(piece)
                            while view:
                                n = os.write(fd, view)
                                view = view[n:]
                    finally:
                        os.close(fd)
                elif kind == "link":
                    os.symlink(payload, name, dir_fd=parent)
                elif kind == "fifo":
                    if os.mkfifo in os.supports_dir_fd:
                        os.mkfifo(name, 0o644, dir_fd=parent)
                    else:  # macOS system Python: mkfifo has no dir_fd
                        here = os.open(".", os.O_RDONLY)
                        try:
                            os.fchdir(parent)
                            os.mkfifo(name, 0o644)
                        finally:
                            os.fchdir(here)
                            os.close(here)
                elif kind == "hard":
                    oparts = payload.split(b"/")
                    oparent = _open_dir_path(root_fd, oparts[:-1], False)
                    try:
                        os.link(oparts[-1], name, src_dir_fd=oparent, dst_dir_fd=parent)
                    finally:
                        os.close(oparent)
                elif kind == "socket":
                    here = os.open(".", os.O_RDONLY)
                    try:
                        os.fchdir(parent)
                        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        s.bind(os.fsdecode(name))
                        SocketHolder.sockets.append(s)
                    finally:
                        os.fchdir(here)
                        os.close(here)
                else:
                    raise ValueError("unknown entry kind %s" % kind)
            finally:
                os.close(parent)
    finally:
        os.close(root_fd)


def material_witness(entries):
    """files: public name (bytes) -> {'data'|'size','sha256','lines'}; dirs: set of names."""
    files, dirs, data_of = {}, set(), {}
    for kind, rel, payload in entries:
        parts = rel.split(b"/")
        for i in range(1, len(parts)):
            dirs.add(b"/".join(parts[:i]))
        if kind == "dir":
            dirs.add(rel)
        elif kind == "file":
            data_of[rel] = payload
            files[rel] = {"data": payload, "size": len(payload), "sha256": sha256_hex(payload),
                          "lines": line_count(payload)}
        elif kind == "hard":
            payload_data = data_of[payload]
            files[rel] = {"data": payload_data, "size": len(payload_data),
                          "sha256": sha256_hex(payload_data), "lines": line_count(payload_data)}
        elif kind == "big":
            ident = big_identity(*payload)
            ident["big"] = list(payload)
            files[rel] = ident
    return files, dirs


def question_md(body=b"Audit our app to make sure there are no bugs.\n", *, family="open-inquiry",
                model="claude-opus-5-5", dest="/nonexistent", turns="200",
                input_tokens="20000000", output_tokens="400000", inquiry=None, varies=None,
                nl=b"\n", bom=False, extra=(), omit=(), comments=True, effort=None):
    """A question.md. effort, when given, is written as an `effort` field after `model`,
    where the 3.2 template documents it."""
    def enc(v):
        return v if isinstance(v, bytes) else str(v).encode("utf-8")

    fields = [("stewart", b"question/1"), ("family", enc(family)), ("model", enc(model))]
    if effort is not None:
        fields.append(("effort", enc(effort)))
    fields += [("destination", enc(dest)), ("limit-turns", enc(turns)),
              ("limit-input-tokens", enc(input_tokens)), ("limit-output-tokens", enc(output_tokens))]
    if inquiry is not None:
        fields.append(("inquiry", enc(inquiry)))
    if varies is not None:
        fields.append(("varies", enc(varies)))
    lines = [b"---"]
    for i, (k, v) in enumerate(fields):
        if k in omit:
            continue
        if comments and i == 1:
            lines.append(b"# Question family for this audit.")
        lines.append(k.encode("ascii") + b": " + v)
    for line in extra:
        lines.append(line)
    if comments:
        lines.append(b"")
    lines.append(b"---")
    head = nl.join(lines) + nl
    return (b"\xef\xbb\xbf" if bom else b"") + head + body


def split_question(data):
    """The body per question/1 (3.2) for a well-formed file; None otherwise."""
    rest = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    if rest.startswith(b"---\r\n"):
        nl = b"\r\n"
    elif rest.startswith(b"---\n"):
        nl = b"\n"
    else:
        return None
    pos = 3 + len(nl)
    while True:
        end = rest.find(nl, pos)
        if end < 0:
            return None
        if rest[pos:end] == b"---":
            return rest[end + len(nl):]
        pos = end + len(nl)


# ---------------------------------------------------------------------------
# Process control. wait4 gives each command its own resource usage.
# ---------------------------------------------------------------------------

class Proc:
    """One spawned Stewart process; wait() collects its streams and status."""

    KEEP = 64 << 20

    def __init__(self, argv, env, cwd, timeout):
        self.argv, self.env, self.cwd, self.timeout = argv, env, cwd, timeout
        self.out = bytearray()
        self.err = bytearray()
        self.out_hash = hashlib.sha256()
        self.out_len = 0
        self.status = None
        self.rusage = None
        self.t_end = None
        self.timed_out = False
        self.t0 = time.perf_counter()
        self.started_at = utc_now()
        self.p = subprocess.Popen(argv, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  start_new_session=True)
        self._threads = [threading.Thread(target=self._read_out, daemon=True),
                         threading.Thread(target=self._read_err, daemon=True)]
        self._waiter = threading.Thread(target=self._wait, daemon=True)
        for th in self._threads:
            th.start()
        self._waiter.start()

    def _read_out(self):
        while True:
            chunk = self.p.stdout.read1(1 << 16) if hasattr(self.p.stdout, "read1") else self.p.stdout.read(1 << 16)
            if not chunk:
                break
            self.out_hash.update(chunk)
            self.out_len += len(chunk)
            if len(self.out) < self.KEEP:
                self.out.extend(chunk)

    def _read_err(self):
        while True:
            chunk = self.p.stderr.read1(1 << 16) if hasattr(self.p.stderr, "read1") else self.p.stderr.read(1 << 16)
            if not chunk:
                break
            if len(self.err) < (8 << 20):
                self.err.extend(chunk)

    def _wait(self):
        while True:
            try:
                _, status, rusage = os.wait4(self.p.pid, 0)
                break
            except InterruptedError:
                continue
            except ChildProcessError:
                status, rusage = None, None
                break
        self.t_end = time.perf_counter()
        self.status, self.rusage = status, rusage
        if status is not None:
            self.p.returncode = (-os.WTERMSIG(status) if os.WIFSIGNALED(status)
                                 else os.WEXITSTATUS(status))

    def running(self):
        return self._waiter.is_alive()

    def kill(self):
        try:
            os.killpg(self.p.pid, signal.SIGKILL)
        except OSError:
            pass

    def wait(self, timeout=None):
        limit = self.timeout if timeout is None else timeout
        self._waiter.join(limit)
        if self._waiter.is_alive():
            self.timed_out = True
            self.kill()
            self._waiter.join(10)
        for th in self._threads:
            th.join(10)
        rc = self.p.returncode
        wall = ((self.t_end or time.perf_counter()) - self.t0) * 1000.0
        maxrss = None
        if self.rusage is not None:
            maxrss = self.rusage.ru_maxrss // (1024 if sys.platform == "darwin" else 1)
        return {"rc": rc, "stdout": bytes(self.out), "stdout_len": self.out_len,
                "stdout_sha256": self.out_hash.hexdigest(), "stderr": bytes(self.err),
                "wall_ms": round(wall, 3), "maxrss_kib": maxrss, "timed_out": self.timed_out,
                "started_at": self.started_at}


# ---------------------------------------------------------------------------
# Cases, variants and checks.
# ---------------------------------------------------------------------------

class Skip(Exception):
    pass


class Abort(Exception):
    pass


class Control:
    def __init__(self, sabotage, targets, note=""):
        assert sabotage in SABOTAGES, sabotage
        self.sabotage = sabotage
        self.targets = [re.compile(t) for t in targets]
        self.target_text = list(targets)
        self.note = note


class CaseSpec:
    def __init__(self, cid, claims, title, fn, mode, needs, controls, heavy, tags, linux_reason):
        self.id, self.claims, self.title, self.fn = cid, claims, title, fn
        self.mode, self.needs, self.controls, self.heavy, self.tags = mode, needs, controls, heavy, tags
        self.linux_reason = linux_reason
        self.doc = " ".join((fn.__doc__ or "").split())


CASES = []


def case(cid, claims, title, *, mode="release", needs=(), controls=(), heavy=False, tags=(),
         linux_reason=None):
    """Register a case. mode: release (release binary, plus test baseline when it has
    controls), test (test binary only: fault cases), both (release and test baseline)."""
    def deco(fn):
        CASES.append(CaseSpec(cid, list(claims), title, fn, mode, set(needs), list(controls),
                              heavy, set(tags), linux_reason))
        return fn
    return deco


class Reply:
    def __init__(self, op, res, name):
        self.op, self.name = op, name
        self.rc = res["rc"]
        self.stdout = res["stdout"]
        self.stdout_len = res["stdout_len"]
        self.stdout_sha256 = res["stdout_sha256"]
        self.stderr = res["stderr"]
        self.wall_ms = res["wall_ms"]
        self.timed_out = res["timed_out"]
        self.obj = None
        self.stderr_json = None

    @property
    def outcome(self):
        return self.obj.get("outcome") if isinstance(self.obj, dict) else None

    @property
    def reason(self):
        return self.obj.get("reason") if isinstance(self.obj, dict) else None

    @property
    def effects(self):
        v = self.obj.get("effects") if isinstance(self.obj, dict) else None
        return v if isinstance(v, dict) else {}

    @property
    def data(self):
        v = self.obj.get("data") if isinstance(self.obj, dict) else None
        return v if isinstance(v, dict) else {}

    @property
    def next(self):
        v = self.obj.get("next") if isinstance(self.obj, dict) else None
        return v if isinstance(v, list) else []

    def next_argvs(self):
        return [n.get("argv") for n in self.next if isinstance(n, dict) and isinstance(n.get("argv"), list)]

    def text(self):
        return (self.stdout + b"\n" + self.stderr).decode("utf-8", "replace")


class Sub:
    """One submission: a folder the driver built, its destination and its reference."""

    def __init__(self, t, folder, dest, archive, question, entries, root_entries, family, model, limits,
                 effort=None):
        self.t, self.folder, self.dest, self.archive = t, folder, dest, archive
        self.question = question
        self.body = split_question(question)
        self.entries = list(entries)
        self.root_entries = list(root_entries)
        self.family, self.model, self.limits = family, model, limits
        # The front matter's effort level (3.2), or None when the question sets none. A case
        # that edits question.md to change it updates this too.
        self.effort = effort
        self.files, self.dirs = material_witness(entries)
        self.ref = self.audit = self.store = None
        self.handles = []
        self.prep = {}       # handle -> prepare data
        self.arrangement = {}  # handle -> {"machine": bytes, "readable": bytes}
        self.accepted_handle = None
        self.writer = None
        self.prep_next = {}   # handle -> the commission argv prepare suggested
        self.witness_dir = None

    @property
    def audit_dir(self):
        return os.path.join(self.archive, "audits", self.audit)

    def public(self, rel):
        return "materials/" + rel.decode("utf-8")

    def items(self, handle=None):
        """Receipt item ID -> expected bytes or {'big':..., 'sha256':..., 'size':...}."""
        h = handle or self.accepted_handle
        out = {"question-file": self.question, "question-body": self.body}
        arr = self.arrangement.get(h)
        if arr:
            out["arrangement"] = arr["machine"]
            out["arrangement-readable"] = arr["readable"]
        for rel, w in self.files.items():
            out[self.public(rel)] = w["data"] if "data" in w else w
        return out


_DEFAULT = object()


class T:
    """Context of one case variant: binary, private directories, watches and checks."""

    def __init__(self, drv, spec, variant, binary, control):
        self.drv, self.spec, self.variant, self.bin, self.control = drv, spec, variant, binary, control
        self.sabotage = control.sabotage if control else None
        slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", variant)
        self.root = os.path.join(drv.work, spec.id, slug)
        os.makedirs(self.root)
        self.evid = os.path.join(drv.evidence, "cases", spec.id, slug)
        os.makedirs(os.path.join(self.evid, "commands"))
        self.checks, self.commands, self.inventory_log, self.parts_skipped = [], [], [], []
        self.watches = {}
        self.cache = DigestCache()
        self.counter = 0
        self.k = 0
        self.bg = []
        self.cleanups = []
        self.tampered_logs = set()
        self.mode_exempt = set()
        self.premade_roots = set()
        self.audit_writer = {}
        self.drv_controls = []
        # Protocol-call timings measured by the fake provider (C9): dicts with tool, ms, gated.
        self.protocol_timings = []
        self.writer = binary["path"]
        # Each command given a fault gets its own fault directory under faults/ (fault_dir): a
        # pause point pauses once per process, and a .paused or .go file left by an earlier
        # process must never be seen by a later one (Appendix C.1).
        self.faults_base = self.mkdir("faults")
        self.faults = self.faults_base
        self.fault_seq = 0
        self.home = self.fresh_dir("home")
        self.cwd = self.fresh_dir("cwd")
        self.tmp = self.fresh_dir("tmp")

    # -- paths -----------------------------------------------------------
    def next_k(self):
        self.k += 1
        return self.k

    def mkdir(self, *parts):
        p = os.path.join(self.root, *parts)
        os.makedirs(p, exist_ok=True)
        return p

    def fresh_dir(self, label):
        p = self.mkdir("%s %d" % (label, self.next_k()))
        self.watch(p, "frozen", label)
        return p

    def archive_path(self):
        k = self.next_k()
        parent = self.mkdir("vault %d" % k, "Schätze")
        return os.path.join(parent, "Ärchive store %d" % k)

    def folder_path(self):
        k = self.next_k()
        parent = self.mkdir("src %d" % k, "Prép q%d" % k)
        return os.path.join(parent, "folder")

    def dest_path(self):
        return self.mkdir("returns %d" % self.next_k())

    # -- checks ----------------------------------------------------------
    def check(self, name, cond, detail=None):
        ok = bool(cond)
        self.checks.append({"name": name, "ok": ok, "detail": None if ok else short(detail, 1500)})
        return ok

    def eq(self, name, actual, expected):
        return self.check(name, actual == expected, {"actual": actual, "expected": expected})

    def require(self, name, cond, detail=None):
        if not self.check(name, cond, detail):
            raise Abort(name)

    def skip(self, reason):
        raise Skip(reason)

    def skip_part(self, part, reason):
        self.parts_skipped.append({"part": part, "reason": reason})

    def driver_control(self, name, fired, detail):
        """A firing control for the driver's own checks; one that does not fire fails the case."""
        self.drv_controls.append({"name": name, "fired": bool(fired), "detail": short(detail)})
        self.check("controls.%s.fires" % name, fired, detail)

    # -- watches ----------------------------------------------------------
    def watch(self, path, mode, label=None):
        """mode 'archive': earlier entries must stay identical (and archive modes and logs are
        verified at the end); 'additions': the same rule for a destination; 'frozen': nothing
        may change."""
        if path in self.watches:
            if mode != self.watches[path]["mode"] and mode in ("archive", "additions"):
                self.watches[path]["mode"] = mode
            return
        self.watches[path] = {"mode": mode, "label": label or path,
                              "last": snapshot(path, self.cache), "last_live": self.writer_live()}

    def writer_live(self):
        """True while a background Stewart process started by this case is running."""
        return any(h["proc"].running() for h in self.bg)

    def _grew(self, path, rel, before, after):
        """A file that kept its inode and its earlier bytes as a prefix (an in-progress new file)."""
        if before.get("kind") != "file" or after.get("kind") != "file" or before.get("ino") != after.get("ino"):
            return False
        if not (isinstance(before.get("size"), int) and isinstance(after.get("size"), int)
                and after["size"] >= before["size"]):
            return False
        try:
            fd = os.open(os.path.join(path, rel), os.O_RDONLY | _FLAG_NOFOLLOW | _FLAG_NONBLOCK)
        except OSError:
            return False
        try:
            h, left = hashlib.sha256(), before["size"]
            while left > 0:
                chunk = os.read(fd, min(left, 1 << 20))
                if not chunk:
                    return False
                h.update(chunk)
                left -= len(chunk)
            return h.hexdigest() == before.get("sha256")
        finally:
            os.close(fd)

    def sync(self, label, readonly=False):
        live_now = self.writer_live()
        for path, w in self.watches.items():
            snap = snapshot(path, self.cache)
            only_add = w["mode"] in ("archive", "additions")
            violations, added = compare_snapshots(w["last"], snap, only_add)
            if only_add and w.get("last_live") and violations:
                grown = [v for v in violations if v[0] == "rewritten" and snap and w["last"]
                         and self._grew(path, v[1], w["last"][v[1]], snap[v[1]])]
                if grown:
                    violations = [v for v in violations if v not in grown]
                    self.inventory_log.append({"at": label, "watch": w["label"], "path": path,
                                               "grew_while_writer_live": [g[1] for g in grown][:50]})
            if readonly and (live_now or w.get("last_live")):
                readonly_here = False   # additions cannot be attributed while a run is writing
            else:
                readonly_here = readonly
            if not only_add and EMULATOR_HOME_ARTIFACTS and "home" in str(w["label"]):
                artifacts = [v for v in violations if v[0] == "added" and emulator_artifact(v[1])]
                if artifacts:
                    violations = [v for v in violations if v not in artifacts]
                    self.inventory_log.append({"at": label, "watch": w["label"], "path": path,
                                               "emulator_artifacts": artifacts[:50]})
            if readonly_here and only_add and added:
                violations = violations + [("added_by_read_only", a) for a in added]
            if violations or added:
                self.inventory_log.append({"at": label, "watch": w["label"], "path": path,
                                           "added": added[:200], "added_count": len(added),
                                           "violations": violations[:200]})
            if violations:
                kind = "inventory" if only_add else "frozen"
                self.check("%s.%s" % (kind, "-".join(sorted({v[0] for v in violations}))), False,
                           {"at": label, "watch": w["label"], "violations": violations[:20]})
            w["last"] = snap
            w["last_live"] = live_now

    def rebaseline(self, note):
        live_now = self.writer_live()
        for path, w in self.watches.items():
            w["last"] = snapshot(path, self.cache)
            w["last_live"] = live_now
        self.inventory_log.append({"at": "driver: " + note, "rebaseline": True})

    def driver_change(self, note, fn):
        """A deliberate change made by the driver (a test specimen), outside the C6 rule."""
        self.sync("before driver change: " + note)
        try:
            return fn()
        finally:
            self.rebaseline(note)

    def cleanup(self, fn):
        self.cleanups.append(fn)

    # -- commands ----------------------------------------------------------
    def env(self, extra=None, fault=None):
        env = {"PATH": "/usr/bin:/bin", "HOME": self.home, "TMPDIR": self.tmp}
        if self.sabotage:
            env["STEWART_TEST_SABOTAGE"] = self.sabotage
        if fault:
            env["STEWART_TEST_FAULT"] = fault
            env["STEWART_TEST_FAULT_DIR"] = self.fault_dir()
        for k, v in (extra or {}).items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        return env

    def _record(self, name, op, argv, env, cwd, res, fault, background):
        self.counter += 1
        n = self.counter
        stem = "%03d-%s" % (n, re.sub(r"[^A-Za-z0-9_.-]+", "_", name)[:60])
        base = os.path.join(self.evid, "commands", stem)
        keep_out = res["stdout_len"] <= (1 << 20)
        with open(base + ".stdout", "wb") as f:
            f.write(res["stdout"] if keep_out else b"")
        with open(base + ".stderr", "wb") as f:
            f.write(res["stderr"])
        delta = {k: v for k, v in env.items() if k not in ("PATH",)}
        meta = {"n": n, "name": name, "op": op, "argv": argv, "cwd": cwd, "env": delta,
                "fault": fault, "sabotage": self.sabotage, "background": background,
                "binary": self.bin_kind_of(argv[0]), "rc": res["rc"], "wall_ms": res["wall_ms"],
                "maxrss_kib": res["maxrss_kib"], "timed_out": res["timed_out"],
                "started_at": res["started_at"], "stdout_bytes": res["stdout_len"],
                "stdout_sha256": res["stdout_sha256"], "stdout_kept": keep_out}
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        self.commands.append(meta)
        return meta

    def bin_kind_of(self, path):
        rp = os.path.realpath(path)
        for b in (self.drv.release, self.drv.test):
            if b and rp == os.path.realpath(b["path"]):
                return b["kind"]
        if rp in self.drv.aliases:
            return self.drv.aliases[rp]["kind"] + "-copy"
        return "other"

    def cmd(self, args, *, op=None, json_reply=True, binary=None, env=None, fault=None, cwd=None,
            timeout=120, readonly=None, expect=None, reason=None, name=None, writer=_DEFAULT,
            envelope=True, prefix=None):
        """Run one command with inventories before and after. writer is the path every
        suggested argv must begin with (default: this variant's binary; None skips it)."""
        binary = binary or self.bin["path"]
        if writer is _DEFAULT:
            writer = self.writer
        op = op or args[0]
        argv = [binary] + list(args) + (["--json"] if json_reply else [])
        name = name or op
        full_env = self.env(env, fault)
        cwd = cwd or self.cwd
        self.sync("before " + name)
        proc = Proc(argv, full_env, cwd, timeout)
        res = proc.wait()
        if readonly is None:
            readonly = op in READ_ONLY_OPS
        self.sync("after " + name, readonly=readonly)
        self._record(name, op, argv, full_env, cwd, res, fault, False)
        rep = Reply(op, res, name)
        self.check("process.%s.finished" % name, not res["timed_out"], "timed out after %ss" % timeout)
        if json_reply and envelope:
            rep.obj = self.check_envelope(op, rep, writer, name)
        if expect is not None:
            self.expect(rep, expect, reason, prefix or name)
        return rep

    def start(self, args, *, op=None, binary=None, env=None, fault=None, cwd=None, timeout=120, name=None):
        """Start a command in the background (json reply); finish() collects it."""
        binary = binary or self.bin["path"]
        op = op or args[0]
        argv = [binary] + list(args) + ["--json"]
        full_env = self.env(env, fault)
        cwd = cwd or self.cwd
        self.sync("before start " + (name or op))
        proc = Proc(argv, full_env, cwd, timeout)
        h = {"proc": proc, "op": op, "argv": argv, "env": full_env, "cwd": cwd, "name": name or op,
             "fault": fault}
        self.bg.append(h)
        return h

    def finish(self, h, *, expect=None, reason=None, writer=_DEFAULT, envelope=True, sync=True,
               timeout=None, prefix=None):
        if writer is _DEFAULT:
            writer = self.writer
        res = h["proc"].wait(timeout)
        if h in self.bg:
            self.bg.remove(h)
        if sync and not any(x["proc"].running() for x in self.bg):
            self.sync("after background " + h["name"])
        self._record(h["name"], h["op"], h["argv"], h["env"], h["cwd"], res, h["fault"], True)
        rep = Reply(h["op"], res, h["name"])
        self.check("process.%s.finished" % h["name"], not res["timed_out"], "timed out")
        if envelope:
            rep.obj = self.check_envelope(h["op"], rep, writer, h["name"])
        if expect is not None:
            self.expect(rep, expect, reason, prefix or h["name"])
        return rep

    def fault_dir(self):
        """A new, empty fault directory for one process; it also becomes self.faults."""
        self.fault_seq += 1
        d = os.path.join(self.faults_base, "f%03d" % self.fault_seq)
        os.makedirs(d)
        self.faults = d
        return d

    def wait_paused(self, point, h=None, timeout=30.0):
        """Wait until a pause fault created <point...>.paused in the fault directory of the
        background handle h (else the most recent one); return the stem as an absolute path,
        which release() takes."""
        fdir = (h or {}).get("env", {}).get("STEWART_TEST_FAULT_DIR") or self.faults
        deadline = time.time() + timeout
        while time.time() < deadline:
            for name in sorted(os.listdir(fdir)):
                if name.endswith(".paused") and name.startswith(point):
                    stem = name[:-len(".paused")]
                    if not os.path.exists(os.path.join(fdir, stem + ".go")):
                        return os.path.join(fdir, stem)
            if h is not None and not h["proc"].running():
                self.check("fault.%s.paused" % point, False, "process exited before pausing")
                return None
            time.sleep(0.01)
        self.check("fault.%s.paused" % point, False, "no .paused file within %ss" % timeout)
        return None

    def release(self, stem):
        """Create <stem>.go for a stem from wait_paused (absolute; a bare name is taken in
        the most recent fault directory)."""
        if stem:
            with open(os.path.join(self.faults, stem + ".go"), "wb"):
                pass

    def signal(self, h, sig):
        """Send sig to the Stewart process of a background handle (not its process group)."""
        try:
            os.kill(h["proc"].p.pid, sig)
            return True
        except OSError as exc:
            self.check("process.%s.signal" % h["name"], False, "could not signal: %s" % exc)
            return False

    def expect(self, rep, outcome, reason, prefix):
        self.check("%s.outcome" % prefix, rep.outcome == outcome,
                   {"expected": outcome, "got": rep.outcome, "reason": rep.reason, "rc": rep.rc,
                    "message": rep.obj.get("message") if isinstance(rep.obj, dict) else None,
                    "stdout": rep.stdout[:400].decode("utf-8", "replace"),
                    "stderr": rep.stderr[-400:].decode("utf-8", "replace")})
        if reason is not None:
            reasons = (reason,) if isinstance(reason, str) else tuple(reason)
            self.check("%s.reason" % prefix, rep.reason in reasons,
                       {"expected": reasons, "got": rep.reason})

    def check_envelope(self, op, rep, writer, name):
        """INTERFACE 1.3-1.6 for one manager --json reply. Checks are named envelope.*."""
        raw = rep.stdout
        if rep.rc is not None and rep.rc < 0:
            self.check("envelope.present", False, "%s: killed by signal %d" % (name, -rep.rc))
            return None
        text_raw = raw[:-1] if raw.endswith(b"\n") else raw
        if not self.check("envelope.present", bool(text_raw), "%s: empty stdout (rc %s)" % (name, rep.rc)):
            return None
        try:
            obj = strict_loads(text_raw)
        except StrictJSONError as exc:
            self.check("envelope.strict-json", False, "%s: %s: %r" % (name, exc, raw[:300]))
            return None
        self.check("envelope.one-object", isinstance(obj, dict), "%s: top level is not an object" % name)
        if not isinstance(obj, dict):
            return None
        text = text_raw.decode("utf-8")
        self.check("envelope.compact", is_compact_json(text), "%s: whitespace between tokens" % name)
        self.check("envelope.single-line", b"\n" not in text_raw, "%s: newline inside reply" % name)
        keys = list(obj)
        unknown = [k for k in keys if k not in ENVELOPE_ORDER]
        self.check("envelope.known-keys", not unknown, "%s: unknown keys %s" % (name, unknown))
        known = [k for k in keys if k in ENVELOPE_ORDER]
        self.check("envelope.key-order", known == sorted(known, key=ENVELOPE_ORDER.index),
                   "%s: key order %s" % (name, keys))
        self.eq("envelope.schema", obj.get("schema"), REPLY_SCHEMA)
        self.check("envelope.operation", obj.get("operation") == op,
                   "%s: operation %r, expected %r" % (name, obj.get("operation"), op))
        outcome = obj.get("outcome")
        self.check("envelope.outcome", outcome in OUTCOMES, "%s: outcome %r" % (name, outcome))
        bad = outcome in ("refused", "failed")
        r = obj.get("reason")
        self.check("envelope.reason", (isinstance(r, str) and bool(REASON_RE.match(r))) if bad else ("reason" not in obj),
                   "%s: outcome %s with reason %r" % (name, outcome, r))
        m = obj.get("message")
        self.check("envelope.message", (isinstance(m, str) and m.strip() != "") if bad else ("message" not in obj),
                   "%s: outcome %s with message %r" % (name, outcome, m))
        eff = obj.get("effects")
        if self.check("envelope.effects", isinstance(eff, dict), "%s: effects missing or not an object: %r" % (name, eff)):
            expected = set(OP_EFFECTS.get(op, ()))
            got = set(eff)
            self.check("envelope.effects-keys", got - {"diagnostic"} == expected,
                       "%s: effect keys %s, expected %s (+diagnostic)" % (name, sorted(got), sorted(expected)))
            for k, v in eff.items():
                self.check("envelope.effects-values", k in EFFECT_VALUES and v in EFFECT_VALUES[k],
                           "%s: effects.%s = %r" % (name, k, v))
        ret = obj.get("retained")
        if bad:
            self.check("envelope.retained", isinstance(ret, list) and all(isinstance(x, str) and x.startswith("/") for x in ret),
                       "%s: retained must be a list of absolute paths on a manager %s reply: %r" % (name, outcome, ret))
        else:
            self.check("envelope.retained", "retained" not in obj, "%s: retained on a completed reply" % name)
        causes_due = outcome == "failed" or (isinstance(eff, dict) and eff.get("diagnostic") == "reported_only")
        causes = obj.get("causes")
        if causes_due:
            self.check("envelope.causes", isinstance(causes, list) and len(causes) >= 1 and all(isinstance(c, dict) for c in causes),
                       "%s: causes required: %r" % (name, causes))
        else:
            self.check("envelope.causes", "causes" not in obj, "%s: causes present without failure or reported_only" % name)
        nxt = obj.get("next")
        if self.check("envelope.next", isinstance(nxt, list), "%s: next missing or not a list: %r" % (name, nxt)):
            for item in nxt:
                ok = (isinstance(item, dict) and set(item) == {"argv", "why"}
                      and isinstance(item.get("argv"), list) and len(item["argv"]) >= 2
                      and all(isinstance(a, str) for a in item["argv"])
                      and isinstance(item.get("why"), str) and item["why"].strip() != "")
                self.check("envelope.next-item", ok, "%s: next item %r" % (name, item))
                if ok:
                    if writer is not None:
                        self.check("envelope.next-writer", item["argv"][0] == writer,
                                   "%s: next argv[0] %r, recorded writer %r" % (name, item["argv"][0], writer))
                    self.check("envelope.next-command", item["argv"][1] in COMMANDS,
                               "%s: next argv %r" % (name, item["argv"]))
        if outcome == "completed":
            self.check("envelope.data", isinstance(obj.get("data"), dict), "%s: data missing on completed reply" % name)
        elif "data" in obj:
            self.check("envelope.data", isinstance(obj.get("data"), dict), "%s: data is not an object" % name)
        if rep.rc is not None and outcome in EXIT_FOR_OUTCOME:
            want = EXIT_FOR_OUTCOME[outcome]
            data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
            if op == "run" and outcome == "completed" and data.get("ending") == "interrupted":
                want = 5   # INTERFACE 1.6, 5.7: an interrupted placement, recorded
            self.check("exit.matches-outcome", rep.rc == want,
                       "%s: outcome %s (ending %r) exited %s, expected %s" % (
                           name, outcome, data.get("ending"), rep.rc, want))
        return obj

    # -- archive reading --------------------------------------------------
    def read_log(self, sub):
        d = os.path.join(sub.audit_dir, "log")
        recs = []
        try:
            names = os.listdir(d)
        except OSError:
            return recs
        def key(n):
            m = re.fullmatch(r"([1-9][0-9]*)\.json", n)
            return (0, int(m.group(1))) if m else (1, n)
        for n in sorted(names, key=key):
            raw = read_bytes(os.path.join(d, n))
            rec = {"name": n, "raw": raw, "obj": None, "error": None}
            try:
                rec["obj"] = strict_loads(raw)
            except StrictJSONError as exc:
                rec["error"] = str(exc)
            recs.append(rec)
        return recs

    def log_kinds(self, sub):
        return [(r["obj"] or {}).get("kind") for r in self.read_log(sub)]

    def log_bodies(self, sub, kind):
        return [r["obj"].get("body") for r in self.read_log(sub)
                if isinstance(r["obj"], dict) and r["obj"].get("kind") == kind]

    # Folders whose entries are locations a manager reply's `retained` must list (1.3).
    RETAINED_DIRS = ("intake", "prep", "prepared", "seal", "delivery", "diag", "runs", "payload")

    def audit_locations(self, sub):
        """Absolute paths of the entries of the audit's location folders (RETAINED_DIRS), taken
        by the driver itself, to compare `retained` with what an invocation actually created."""
        out = set()
        for d in self.RETAINED_DIRS:
            base = os.path.join(sub.audit_dir, d)
            try:
                out |= {os.path.join(base, n) for n in os.listdir(base)}
            except OSError:
                pass
        return out

    def check_retained(self, rep, sub, name, before, outside=()):
        """1.3 (as amended in 2c927ab): `retained` on a refused or failed manager reply lists
        every location this invocation created and kept: each directory it created (a capture
        attempt, a preparation, a run directory runs/<n>, a delivery package) and each file it
        created in a directory it did not create (an entry payload, a seal manifest, a delivery
        plan, its diagnostic when written); and, on log_damaged, the log directory. Log records
        and stage files are not listed.

        Compared exactly with the new entries of the audit's location folders (RETAINED_DIRS)
        since `before` (an audit_locations() taken before the command), plus `outside`
        (created locations elsewhere, such as a package at a destination)."""
        ret = (rep.obj or {}).get("retained") or []
        created = (self.audit_locations(sub) - set(before)) | set(outside)
        if rep.reason == "log_damaged":
            created.add(os.path.join(sub.audit_dir, "log"))
        self.eq(name + ".retained", sorted(set(ret)), sorted(created))
        self.check(name + ".retained-kept", all(os.path.lexists(x) for x in ret), ret)
        if rep.effects.get("diagnostic") == "durable":
            self.check(name + ".retained-diagnostic", any(os.sep + "diag" + os.sep in x for x in ret), ret)

    def intake_dirs(self, sub):
        d = os.path.join(sub.audit_dir, "intake")
        try:
            return sorted(os.listdir(d))
        except OSError:
            return []

    # -- submissions ------------------------------------------------------
    def submission(self, entries, *, question=None, body=b"Audit our app to make sure there are no bugs.\n",
                   family="open-inquiry", model="claude-opus-5-5", archive=None, root_entries=(),
                   q=None, folder=None, dest=None, make_question=True, make_materials=True,
                   dest_watch="frozen", effort=None):
        """Build a submission folder and its witness. dest_watch is 'frozen' before launch
        (nothing may appear) and 'additions' where a run or close may deliver. effort sets the
        front matter's effort level (3.2); None leaves the key out."""
        folder = folder or self.folder_path()
        dest = dest or self.dest_path()
        q = dict(q or {})
        limits = (int(q.get("turns", 200)) if str(q.get("turns", 200)).isdigit() else None,
                  int(q.get("input_tokens", 20000000)) if str(q.get("input_tokens", 20000000)).isdigit() else None,
                  int(q.get("output_tokens", 400000)) if str(q.get("output_tokens", 400000)).isdigit() else None)
        if question is None:
            question = question_md(body, family=family, model=model, dest=q.pop("dest", dest), effort=effort, **q)
        os.makedirs(folder)
        if make_question:
            with open(os.path.join(folder, "question.md"), "wb") as f:
                f.write(question)
        if make_materials:
            os.mkdir(os.path.join(folder, "materials"))
            build_entries(os.path.join(folder, "materials"), entries)
        if root_entries:
            build_entries(folder, root_entries)
        sub = Sub(self, folder, dest, archive or self.archive_path(), question, entries, root_entries,
                  family, model, limits, effort=effort)
        self.watch(folder, "frozen", "folder")
        self.watch(dest, dest_watch, "destination")
        self.save_witness(sub)
        return sub

    def save_witness(self, sub, label=None):
        label = label or "w%d" % self.next_k()
        d = os.path.join(self.drv.evidence, "witness", self.spec.id,
                         re.sub(r"[^A-Za-z0-9_.-]+", "-", self.variant), label)
        os.makedirs(d, exist_ok=True)
        manifest = {"folder": sub.folder, "question_sha256": sha256_hex(sub.question),
                    "question_bytes": len(sub.question),
                    "body_sha256": sha256_hex(sub.body) if sub.body is not None else None,
                    "files": [], "dirs": sorted(x.hex() for x in sub.dirs)}
        with open(os.path.join(d, "question.md.bin"), "wb") as f:
            f.write(sub.question)
        for i, (rel, w) in enumerate(sorted(sub.files.items())):
            entry = {"name_hex": rel.hex(), "size": w["size"], "sha256": w["sha256"], "lines": w["lines"]}
            if "data" in w:
                blob = "blob-%04d.bin" % i
                with open(os.path.join(d, blob), "wb") as f:
                    f.write(w["data"])
                entry["blob"] = blob
            else:
                entry["generator"] = w.get("big")
            manifest["files"].append(entry)
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=1)
        sub.witness_dir = d

    def new_ref(self, sub, *, name="new", expect="completed", env=None, binary=None, archive_arg=True,
                scaffold=False):
        self.watch(sub.archive, "archive", "archive")
        args = ["new", sub.folder] + (["--archive", sub.archive] if archive_arg else [])
        rep = self.cmd(args, name=name, expect=expect, env=env, binary=binary,
                       writer=binary or self.bin["path"])
        if rep.outcome == "completed":
            self.check_new_reply(rep, sub, name, scaffold, binary or self.bin["path"])
        elif expect == "completed":
            raise Abort(name)   # nothing later in the case can run without the reference
        return rep

    def check_new_reply(self, rep, sub, name, scaffold, binary):
        d = rep.data
        self.eq("%s.effects" % name, rep.effects, {"reference": "created"})
        ref = d.get("reference")
        parsed = parse_reference(ref) if isinstance(ref, str) else None
        self.require("%s.reference-form" % name, parsed is not None, ref)
        self.eq("%s.reference-root" % name, parsed["root"], sub.archive)
        self.eq("%s.reference-encoding" % name, ref, make_reference(parsed["audit"], parsed["store"], sub.archive))
        sub.ref, sub.audit, sub.store = ref, parsed["audit"], parsed["store"]
        sub.writer = binary
        self.eq("%s.data.archive" % name, d.get("archive"), sub.archive)
        self.eq("%s.data.folder" % name, d.get("folder"), sub.folder)
        self.eq("%s.data.scaffold_created" % name, d.get("scaffold_created"), scaffold)
        self.check("%s.data.archive_created" % name, isinstance(d.get("archive_created"), bool), d.get("archive_created"))
        self.check("%s.data.notices" % name, isinstance(d.get("notices"), list), d.get("notices"))
        digest = self.drv.digest_of(binary)
        self.eq("%s.data.writer" % name, d.get("writer"), {"path": binary, "sha256": digest})
        self.check("%s.next-prepare" % name, [binary, "prepare", ref] in rep.next_argvs(), rep.next)
        self.audit_writer[sub.audit] = digest
        # Archive layout written by new (4.2, 4.9, 4.6).
        store = os.path.join(sub.archive, "STORE.json")
        try:
            sobj = strict_loads(read_bytes(store))
            self.check("%s.store-marker" % name, contains_string(sobj, sub.store), "STORE.json lacks the store id")
            ino = os.stat(sub.archive).st_ino
            self.check("%s.store-marker-inode" % name, any(isinstance(v, int) and v == ino for v in iter_values(sobj)),
                       "STORE.json does not record the root inode %d" % ino)
            self.check("%s.store-marker-path" % name, contains_string(sobj, sub.archive), "STORE.json lacks the creation path")
        except (OSError, StrictJSONError) as exc:
            self.check("%s.store-marker" % name, False, str(exc))
        try:
            robj = strict_loads(read_bytes(os.path.join(sub.audit_dir, "REFERENCE.json")))
            self.check("%s.reference-record-writer" % name, mentions(robj, digest), "REFERENCE.json lacks the writer digest")
            self.check("%s.reference-record-writer-path" % name, contains_string(robj, binary),
                       "REFERENCE.json lacks the writer's resolved path")
        except (OSError, StrictJSONError) as exc:
            self.check("%s.reference-record" % name, False, str(exc))
        lock = os.path.join(sub.audit_dir, "active.lock")
        try:
            st = os.lstat(lock)
            self.check("%s.active-lock" % name, stat.S_ISREG(st.st_mode) and st.st_size == 0, "active.lock is not an empty file")
        except OSError as exc:
            self.check("%s.active-lock" % name, False, str(exc))
        kinds = self.log_kinds(sub)
        self.eq("%s.log" % name, kinds[:1], ["reference"])

    def prepare(self, sub, *, name="prepare", expect="completed", reason=None, env=None, fault=None,
                binary=None, writer=None, timeout=120):
        rep = self.cmd(["prepare", sub.ref], name=name, expect=expect, reason=reason, env=env,
                       fault=fault, binary=binary, writer=writer or sub.writer, timeout=timeout)
        if rep.outcome == "completed":
            self.check_prepared(rep, sub, name, writer or sub.writer)
        elif rep.outcome in ("refused", "failed"):
            self.check("%s.effects-none" % name, rep.effects.get("preparation") in ("none", "unknown"), rep.effects)
        if expect == "completed" and rep.outcome != "completed":
            raise Abort(name)   # later steps need the handle
        return rep

    def check_prepared(self, rep, sub, name, writer):
        d = rep.data
        h = d.get("prepared")
        self.require("%s.handle-form" % name, isinstance(h, str) and MP_RE.match(h), h)
        self.eq("%s.effects" % name, rep.effects, {"preparation": "recorded"})
        sub.handles.append(h)
        sub.prep[h] = d
        self.check("%s.next-commission" % name,
                   [writer, "commission", sub.ref, h, "--i-am-finished"] in rep.next_argvs(), rep.next)
        offers = [a for a in rep.next_argvs() if len(a) >= 4 and a[1] == "commission" and a[3] == h]
        if offers:
            sub.prep_next[h] = offers[0]
        # The handle check binds the prepared log record (2.3).
        m = MP_RE.match(h)
        sums = [sha256_hex(r["raw"]) for r in self.read_log(sub)
                if isinstance(r["obj"], dict) and r["obj"].get("kind") == "prepared"]
        self.check("%s.handle-binding" % name,
                   any(handle_check(sub.store, sub.audit, "mp", h.split(".")[0], [s]) == m.group(2) for s in sums),
                   {"handle": h, "prepared_records": len(sums)})
        # Arrangement records: copy them into the witness now, as pinned at prepare.
        arr = d.get("arrangement") if isinstance(d.get("arrangement"), dict) else {}
        mpath, rpath = arr.get("machine"), arr.get("readable")
        prep_root = os.path.join(sub.audit_dir, "prep") + os.sep
        ok = all(isinstance(p, str) and p.startswith(prep_root) for p in (mpath, rpath))
        self.check("%s.arrangement-locations" % name, ok, arr)
        if ok:
            if sub.witness_dir is None:
                self.save_witness(sub)
            try:
                mb, rb = read_bytes(mpath), read_bytes(rpath)
                sub.arrangement[h] = {"machine": mb, "readable": rb}
                with open(os.path.join(sub.witness_dir, "arrangement-%s.json.bin" % h.split(".")[0]), "wb") as f:
                    f.write(mb)
                with open(os.path.join(sub.witness_dir, "arrangement-%s.md.bin" % h.split(".")[0]), "wb") as f:
                    f.write(rb)
                self.eq("%s.arrangement-sha256" % name, arr.get("sha256"), sha256_hex(mb))
            except OSError as exc:
                self.check("%s.arrangement-readable" % name, False, str(exc))

    def check_prepare_witness(self, rep, sub, name):
        """Prepare's reply against the witness (3.3, 5.3)."""
        d = rep.data
        q = d.get("question") or {}
        self.eq("%s.question" % name, q, {"file_bytes": len(sub.question), "file_sha256": sha256_hex(sub.question),
                                         "body_bytes": len(sub.body), "body_sha256": sha256_hex(sub.body)})
        exp_files = []
        for rel in sorted(sub.files):
            w = sub.files[rel]
            exp_files.append({"name": sub.public(rel), "size": w["size"], "sha256": w["sha256"], "lines": w["lines"]})
        mats = d.get("materials") or {}
        got = mats.get("files")
        got_core = [{k: f.get(k) for k in ("name", "size", "sha256", "lines")} for f in got] if isinstance(got, list) else got
        if got_core != exp_files:
            gnames = [f.get("name") for f in got] if isinstance(got, list) else None
            self.check("%s.files" % name, False,
                       {"missing": [f["name"] for f in exp_files if gnames is None or f["name"] not in gnames],
                        "unexpected": [n for n in (gnames or []) if n not in [f["name"] for f in exp_files]],
                        "differing": [f for f in exp_files if isinstance(got, list) and f not in got_core][:10]})
        else:
            self.check("%s.files" % name, True)
        self.eq("%s.count" % name, mats.get("count"), len(exp_files))
        self.eq("%s.bytes" % name, mats.get("bytes"), sum(f["size"] for f in exp_files))
        exp_dirs = {"materials"} | {"materials/" + x.decode("utf-8") for x in sub.dirs}
        gd = mats.get("directories")
        self.eq("%s.directories" % name, sorted(gd) if isinstance(gd, list) else gd, sorted(exp_dirs))
        s = d.get("settings") or {}
        self.eq("%s.settings.family" % name, s.get("family"), sub.family)
        self.eq("%s.settings.model" % name, s.get("model"), sub.model)
        self.eq("%s.settings.destination" % name, s.get("destination"), sub.dest)
        self.eq("%s.settings.limits" % name, s.get("limits"),
                {"turns": sub.limits[0], "input_tokens": sub.limits[1], "output_tokens": sub.limits[2]})
        # 5.3 does not list the reply's settings members beyond its example; the prepared record
        # (check_prepared_settings) is exact. Here: no effort member without an effort, and the
        # given level when the reply shows one.
        if sub.effort is None:
            self.check("%s.settings.no-effort" % name, "effort" not in s, s)
        elif "effort" in s:
            self.eq("%s.settings.effort" % name, s.get("effort"), sub.effort)
        self.eq("%s.reader" % name, d.get("reader"), {"id": "utf8-text/1", "transformations": "none"})
        self.eq("%s.bounds" % name, d.get("bounds"), BOUNDS)

    def check_prepared_settings(self, sub, name, inquiry=False, varies=False):
        """The latest `prepared` record's settings (4.4), in order: family, model, destination,
        limits {turns, input_tokens, output_tokens}, then effort, inquiry and varies only when
        given. sub.effort is the level the question sets, or None; inquiry and varies say whether
        the question gives them (4.4 does not spell out their recorded form, so only their
        presence and place are judged)."""
        bodies = [b for b in self.log_bodies(sub, "prepared") if isinstance(b, dict)]
        s = bodies[-1].get("settings") if bodies else None
        want = {"family": sub.family, "model": sub.model, "destination": sub.dest,
                "limits": {"turns": sub.limits[0], "input_tokens": sub.limits[1], "output_tokens": sub.limits[2]}}
        if sub.effort is not None:
            want["effort"] = sub.effort
        for key, given in (("inquiry", inquiry), ("varies", varies)):
            if given:
                want[key] = "given"
        got = {k: ("given" if k in ("inquiry", "varies") else v) for k, v in s.items()} if isinstance(s, dict) else s
        self.eq("%s.record.settings" % name, got, want)
        order = lambda v: ([(k, order(x)) for k, x in v.items()] if isinstance(v, dict) else None)
        self.eq("%s.record.settings-order" % name, order(got), order(want))
        return s

    def request_extra_of(self, sub, handle=None):
        """The `request_extra` member of the arrangement pinned at prepare (6.2), decoded, or the
        string 'missing' when the arrangement or the member is unavailable."""
        arr = sub.arrangement.get(handle or (sub.handles[-1] if sub.handles else None))
        if not arr:
            return "missing"
        try:
            obj = strict_loads(arr["machine"])
        except StrictJSONError:
            return "missing"
        members = obj if isinstance(obj, dict) and "request_extra" in obj else (
            obj.get("body") if isinstance(obj, dict) and isinstance(obj.get("body"), dict) else {})
        v = members.get("request_extra", "missing") if isinstance(members, dict) else "missing"
        if isinstance(v, str) and v != "missing":
            try:
                v = strict_loads(v.encode("utf-8"))
            except StrictJSONError:
                pass
        return v

    def commission(self, sub, handle, *, flag=True, name="commission", expect="completed", reason=None,
                   fault=None, env=None, binary=None, writer=None, already=False, timeout=120):
        args = ["commission", sub.ref, handle] + (["--i-am-finished"] if flag else [])
        rep = self.cmd(args, name=name, expect=expect, reason=reason, fault=fault, env=env,
                       binary=binary, writer=writer or sub.writer, timeout=timeout)
        if rep.outcome == "completed":
            self.check_accepted(rep, sub, handle, name, writer or sub.writer, already)
        elif expect == "completed":
            raise Abort(name)   # later steps need the acceptance
        return rep

    def check_accepted(self, rep, sub, handle, name, writer, already=False):
        d = rep.data
        # A repeat that returns the recorded acceptance made no attempt (INTERFACE 5.4).
        self.eq("%s.effects" % name, rep.effects,
                {"acceptance": "accepted", "attempt": "none" if already else "recorded"})
        self.eq("%s.data.reference" % name, d.get("reference"), sub.ref)
        self.check("%s.data.accepted_at" % name, isinstance(d.get("accepted_at"), str) and AT_RE.match(d.get("accepted_at")), d.get("accepted_at"))
        rs = d.get("receipt_sha256")
        self.check("%s.data.receipt_sha256" % name, isinstance(rs, str) and HEX64_RE.match(rs), rs)
        self.eq("%s.data.already_accepted" % name, d.get("already_accepted"), already)
        self.eq("%s.data.checks" % name, d.get("checks"), COMMISSION_CHECKS)
        self.eq("%s.data.declaration" % name, d.get("declaration"), {"i_am_finished": True})
        self.eq("%s.data.materials" % name, d.get("materials"),
                {"count": len(sub.files), "bytes": sum(w["size"] for w in sub.files.values())})
        self.eq("%s.data.run_line" % name, d.get("run_line"), [writer, "run", sub.ref])
        self.eq("%s.data.receipt_line" % name, d.get("receipt_line"), [writer, "receipt", sub.ref])
        rn = d.get("run_needs")
        self.check("%s.data.run_needs" % name, isinstance(rn, list) and rn and all(isinstance(x, str) for x in rn)
                   and any("ANTHROPIC_API_KEY" in x for x in rn) and any("background" in x for x in rn), rn)
        argvs = rep.next_argvs()
        self.check("%s.next-run" % name, [writer, "run", sub.ref] in argvs, rep.next)
        self.check("%s.next-close" % name, [writer, "close", sub.ref] in argvs, rep.next)
        sub.accepted_handle = handle
        # The receipt digest names an exclusive receipt in an intake attempt.
        found = None
        for att in self.intake_dirs(sub):
            p = os.path.join(sub.audit_dir, "intake", att, "receipt.json")
            if os.path.isfile(p) and sha256_hex(read_bytes(p)) == rs:
                found = att
        self.check("%s.receipt-file" % name, found is not None, "no intake/*/receipt.json hashes to %s" % rs)
        if found is not None and not already:
            self.check_captures(sub, found, name)
        return found

    def check_captures(self, sub, attempt, name):
        """The attempt's capture files hold exactly the witness bytes (q.bin and m*.bin, 4.2)."""
        d = os.path.join(sub.audit_dir, "intake", attempt)
        q = os.path.join(d, "q.bin")
        self.check("%s.capture-question" % name, os.path.isfile(q) and sha256_file(q) == sha256_hex(sub.question),
                   "intake/%s/q.bin does not hold question.md" % attempt)
        got = []
        inos = set()
        for n in sorted(os.listdir(d)):
            if re.fullmatch(r"m[0-9]{4,}\.bin", n):
                p = os.path.join(d, n)
                got.append(sha256_file(p))
                inos.add(os.lstat(p).st_ino)
        exp = sorted(w["sha256"] for w in sub.files.values())
        self.eq("%s.capture-materials" % name, sorted(got), exp)
        self.check("%s.capture-separate" % name, len(inos) == len(got), "capture files share inodes")

    def readback(self, sub, item, *, name=None, binary=None, env=None, cwd=None, argv=None, timeout=300):
        name = name or "read %s" % item
        args = argv[1:] if argv else ["receipt", sub.ref, "--read", item]
        rep = self.cmd(args, op="receipt-read", json_reply=False, envelope=False, name=name,
                       binary=(argv[0] if argv else binary), env=env, cwd=cwd, timeout=timeout)
        lines = [l for l in rep.stderr.split(b"\n") if l.strip()]
        if lines:
            try:
                rep.stderr_json = strict_loads(lines[-1])
            except StrictJSONError as exc:
                rep.stderr_json = None
                self.check("readback.stderr-json", False, "%s: last stderr line is not strict JSON: %s" % (name, exc))
        else:
            self.check("readback.stderr-json", False, "%s: no stderr line" % name)
        return rep

    def check_readback_ok(self, sub, item, expected, prefix, **kw):
        rep = self.readback(sub, item, name="%s %s" % (prefix, item), **kw)
        if isinstance(expected, dict):
            ok = rep.stdout_len == expected["size"] and rep.stdout_sha256 == expected["sha256"]
            size, sha = expected["size"], expected["sha256"]
        else:
            ok = rep.stdout == expected
            size, sha = len(expected), sha256_hex(expected)
        self.check("%s.bytes" % prefix, ok, {"item": item, "got_bytes": rep.stdout_len, "expected_bytes": size,
                                             "got_sha256": rep.stdout_sha256, "expected_sha256": sha})
        self.eq("%s.exit" % prefix, rep.rc, 0)
        j = rep.stderr_json if isinstance(rep.stderr_json, dict) else {}
        self.check("%s.qualification" % prefix,
                   j.get("verified") is True and contains_string(j, item) and j.get("size") == size and j.get("sha256") == sha,
                   {"item": item, "stderr_json": j})
        return rep

    def check_readback_refused(self, sub, item, diags, prefix, **kw):
        rep = self.readback(sub, item, name="%s %s" % (prefix, item), **kw)
        diags = (diags,) if isinstance(diags, str) else tuple(diags)
        self.check("%s.no-bytes" % prefix, rep.stdout_len == 0, {"item": item, "stdout_bytes": rep.stdout_len})
        self.check("%s.exit" % prefix, rep.rc not in (0, None) and rep.rc > 0, rep.rc)
        j = rep.stderr_json if isinstance(rep.stderr_json, dict) else {}
        self.check("%s.diagnostic" % prefix, any(contains_string(j, x) for x in diags) and j.get("verified") is not True,
                   {"item": item, "expected": diags, "stderr_json": j})
        return rep

    def status(self, sub, *, name="status", binary=None, env=None, cwd=None, writer=None, expect="completed",
               reason=None):
        return self.cmd(["status", sub.ref], name=name, binary=binary, env=env, cwd=cwd,
                        writer=writer or sub.writer, expect=expect, reason=reason)

    def check_status(self, rep, sub, name, *, condition, accepted, launched="no", closed="no",
                     next_cmds=(), handle=None, writer=None):
        """Headline, evidence and next calls (5.6). On a damaged log a headline value that
        depends on the unreadable part may be unknown instead of its pre-launch value."""
        d = rep.data
        writer = writer or sub.writer
        damaged = condition in ("acceptance_uncertain", "log_damaged")
        self.eq("%s.condition" % name, d.get("condition"), condition)
        hl = d.get("headline") if isinstance(d.get("headline"), dict) else {}
        self.eq("%s.headline.accepted" % name, hl.get("accepted"), accepted)

        def headline(key, expected):
            got = hl.get(key)
            ok = got == expected or (damaged and "unknown" in json.dumps(got))
            self.check("%s.headline.%s" % (name, key), ok, {"expected": expected, "got": got})
        headline("launched", launched)
        headline("sealed", {"by": "none"})
        headline("delivered", {"verified": False, "confirmed": False})
        headline("closed", closed)
        self.check("%s.summary" % name, isinstance(d.get("summary"), str) and d.get("summary").strip(), d.get("summary"))
        ev = d.get("evidence")
        self.check("%s.evidence" % name, isinstance(ev, list) and all(
            isinstance(e, dict) and set(e) == {"fact", "evidence"} and all(isinstance(v, str) for v in e.values())
            for e in ev), ev)
        self.check("%s.diagnostics" % name, isinstance(d.get("diagnostics"), list), d.get("diagnostics"))
        argvs = rep.next_argvs()
        for c in next_cmds:
            if c == "commission" and handle:
                self.check("%s.next.commission" % name, [writer, "commission", sub.ref, handle, "--i-am-finished"] in argvs, rep.next)
            else:
                self.check("%s.next.%s" % (name, c), any(a[1] == c and (len(a) < 3 or a[2] == sub.ref) for a in argvs), rep.next)
        if accepted == "yes":
            self.eq("%s.receipt_line" % name, d.get("receipt_line"), [writer, "receipt", sub.ref])
        if launched == "no" and not damaged:
            self.check_prelaunch_status_data(rep, sub, name, accepted=accepted, closed=closed)

    def check_prelaunch_status_data(self, rep, sub, name, *, accepted, closed):
        """The members of status data before launch (INTERFACE 5.6, as extended for runs): their
        order, no run or answer facts yet, allowances only after acceptance, closure only after a
        close request, and no provider override or proxy."""
        d = rep.data
        self.eq("%s.data-keys" % name, list(d), list(STATUS_DATA_KEYS))
        self.eq("%s.runs" % name, d.get("runs"), {"count": 0, "held": False, "holder": None, "last": None})
        if accepted == "yes" and sub.limits and None not in sub.limits:
            lim = dict(zip(("turns", "input_tokens", "output_tokens"), sub.limits))
            self.eq("%s.allowances" % name, d.get("allowances"),
                    {k: {"used": 0, "reported": 0, "estimated": 0, "limit": lim[k]} for k in lim})
        elif accepted == "no":
            self.eq("%s.allowances" % name, d.get("allowances"), None)
        self.eq("%s.answer" % name, d.get("answer"), None)
        self.eq("%s.seal" % name, d.get("seal"), None)
        self.eq("%s.deliveries" % name, d.get("deliveries"), [])
        self.eq("%s.provider" % name, [d.get("provider_url_override"), d.get("provider_proxy")], [None, None])
        cl = d.get("closure")
        if closed == "no":
            self.eq("%s.closure" % name, cl, None)
            return
        if not self.check("%s.closure-keys" % name, isinstance(cl, dict) and list(cl) == list(STATUS_CLOSURE_KEYS), cl):
            return
        self.check("%s.closure.requested_at" % name, isinstance(cl["requested_at"], str) and AT_RE.match(cl["requested_at"]),
                   cl["requested_at"])
        self.eq("%s.closure.before_launch" % name, cl["before_launch"], True)
        if accepted in ("yes", "no"):
            self.eq("%s.closure.accepted" % name, cl["accepted"], accepted == "yes")
        if closed == "yes":
            self.eq("%s.closure.unfinished_reason" % name, cl["unfinished_reason"], None)
            self.check("%s.closure.closed_at" % name, isinstance(cl["closed_at"], str) and AT_RE.match(cl["closed_at"]),
                       cl["closed_at"])
            self.eq("%s.closure.outcome" % name, cl["outcome"],
                    "closed_after_acceptance_before_launch" if accepted == "yes" else "closed_without_acceptance")
            # Before launch the closed record has no placement or surrender (4.4): both null.
            self.eq("%s.closure.placement-surrendered" % name, [cl["placement"], cl["surrendered"]], [None, None])
        else:
            self.eq("%s.closure.closed" % name, [cl["closed_at"], cl["outcome"], cl["placement"], cl["surrendered"]],
                    [None, None, None, None])

    def accept(self, sub, *, prefix="", check_witness=False):
        """new, prepare and commission (through prepare's own next argv)."""
        self.new_ref(sub, name=prefix + "new")
        rep = self.prepare(sub, name=prefix + "prepare")
        self.require(prefix + "prepare.completed", rep.outcome == "completed", rep.obj)
        if check_witness:
            self.check_prepare_witness(rep, sub, prefix + "prepare")
        h = sub.handles[-1]
        rep2 = self.commission(sub, h, name=prefix + "commission")
        self.require(prefix + "commission.completed", rep2.outcome == "completed", rep2.obj)
        return h, rep2

    def capture_paths(self, sub):
        """Capture files of the accepted attempt keyed by the witness name they hold."""
        out = {}
        for att in self.intake_dirs(sub):
            d = os.path.join(sub.audit_dir, "intake", att)
            for n in sorted(os.listdir(d)):
                if re.fullmatch(r"m[0-9]{4,}\.bin", n):
                    p = os.path.join(d, n)
                    digest = sha256_file(p)
                    for rel, w in sub.files.items():
                        if w["sha256"] == digest:
                            out.setdefault(sub.public(rel), []).append(p)
        return out

    def flip_bit(self, path, offset=0):
        def fn():
            fd = os.open(path, os.O_RDWR | _FLAG_NOFOLLOW)
            try:
                b = os.pread(fd, 1, offset)
                os.pwrite(fd, bytes([b[0] ^ 0x01]), offset)
            finally:
                os.close(fd)
        self.driver_change("flip one bit of %s" % path, fn)

    def edit(self, path, data, note=None):
        def fn():
            with open(path, "wb") as f:
                f.write(data)
        self.driver_change(note or "write %s" % path, fn)

    # -- end of variant ---------------------------------------------------
    def finish_variant(self):
        for h in list(self.bg):
            running = h["proc"].running()
            self.check("driver.background-finished", not running, "%s still running at end of case" % h["name"])
            h["proc"].kill()
            self.finish(h, envelope=False, sync=False)
        if self.cleanups:
            # Judge everything Stewart did before cleanups restore driver-changed state; the
            # rebaseline below may only absorb the driver's own restoration.
            self.sync("before cleanup")
        for fn in reversed(self.cleanups):
            try:
                fn()
            except Exception as exc:
                self.check("driver.cleanup", False, str(exc))
        if self.cleanups:
            self.rebaseline("restore driver-changed permissions")
        self.sync("end of case")
        self.verify_archives()

    def verify_archives(self):
        """Log names, strict records, header, prev chain and modes in every watched archive."""
        for path, w in self.watches.items():
            if w["mode"] != "archive" or not os.path.isdir(os.path.join(path, "audits")):
                continue
            self._verify_modes(path)
            for audit in sorted(os.listdir(os.path.join(path, "audits"))):
                if audit in self.tampered_logs or audit not in self.audit_writer:
                    continue
                self._verify_log(path, audit)

    def _verify_modes(self, root):
        snap = snapshot(root, self.cache) or {}
        bad = []
        for rel, e in snap.items():
            full = os.path.join(root, rel) if rel else root
            if full in self.mode_exempt or (rel == "" and root in self.premade_roots):
                continue
            if e.get("kind") == "dir" and e.get("mode") != 0o700:
                bad.append((rel or ".", oct(e.get("mode"))))
            elif e.get("kind") == "file" and e.get("mode") != 0o600:
                bad.append((rel, oct(e.get("mode"))))
            elif e.get("kind") not in ("dir", "file"):
                bad.append((rel, e.get("kind")))
        self.check("archive.modes", not bad, {"root": root, "entries": bad[:20]})

    def _verify_log(self, root, audit):
        d = os.path.join(root, "audits", audit, "log")
        try:
            names = os.listdir(d)
        except OSError as exc:
            self.check("log.readable", False, str(exc))
            return
        n = len(names)
        self.eq("log.names", sorted(names, key=lambda x: (len(x), x)), ["%d.json" % i for i in range(1, n + 1)])
        prev = None
        problems = []
        for i in range(1, n + 1):
            p = os.path.join(d, "%d.json" % i)
            if not os.path.isfile(p):
                problems.append((i, "missing"))
                prev = None
                continue
            raw = read_bytes(p)
            try:
                obj = strict_loads(raw)
            except StrictJSONError as exc:
                problems.append((i, "not strict JSON: %s" % exc))
                prev = sha256_hex(raw)
                continue
            if not isinstance(obj, dict) or set(obj) != {"record", "kind", "audit", "writer", "at", "body"}:
                problems.append((i, "header keys %s" % (sorted(obj) if isinstance(obj, dict) else type(obj))))
            else:
                if obj["record"] != RECORD_SCHEMA:
                    problems.append((i, "record %r" % obj["record"]))
                if obj["kind"] not in LOG_KINDS:
                    problems.append((i, "kind %r" % obj["kind"]))
                if obj["audit"] != audit:
                    problems.append((i, "audit %r" % obj["audit"]))
                if obj["writer"] != self.audit_writer.get(audit):
                    problems.append((i, "writer %r" % obj["writer"]))
                if not (isinstance(obj["at"], str) and AT_RE.match(obj["at"])):
                    problems.append((i, "at %r" % obj["at"]))
                body = obj["body"]
                if not isinstance(body, dict) or "prev" not in body:
                    problems.append((i, "body lacks prev"))
                elif body["prev"] != prev:
                    problems.append((i, "prev %r, expected %r" % (body["prev"], prev)))
                if i == 1 and obj["kind"] != "reference":
                    problems.append((i, "first record is %r" % obj["kind"]))
            prev = sha256_hex(raw)
        self.check("log.records", not problems, {"audit": audit, "problems": problems[:20]})


# ---------------------------------------------------------------------------
# The driver: variants, controls, timings, evidence.
# ---------------------------------------------------------------------------

GATED_OPS = ("help", "status", "usage")


def _rmtree(path):
    def onerror(func, p, exc):
        try:
            os.chmod(os.path.dirname(p), 0o700)
            os.chmod(p, 0o700)
        except OSError:
            pass
        try:
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, onerror=onerror)


def copy_tree_safe(src, dst, limit):
    """Copy regular files, directories and links (as links); skip special files.
    Returns notes. Stops when more than limit bytes would be copied."""
    notes, total = [], 0
    for dirpath, dirnames, filenames in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        target = os.path.join(dst, rel) if rel != "." else dst
        try:
            os.makedirs(target, exist_ok=True)
        except OSError as exc:
            notes.append("uncopied directory %s: %s" % (dirpath, exc))
            dirnames[:] = []
            continue
        for name in list(dirnames):
            p = os.path.join(dirpath, name)
            if os.path.islink(p):
                os.symlink(os.readlink(p), os.path.join(target, name))
                dirnames.remove(name)
        for name in filenames:
            p = os.path.join(dirpath, name)
            try:
                st = os.lstat(p)
            except OSError as exc:
                notes.append("unstatable %s: %s" % (p, exc))
                continue
            if stat.S_ISLNK(st.st_mode):
                os.symlink(os.readlink(p), os.path.join(target, name))
            elif stat.S_ISREG(st.st_mode):
                total += st.st_size
                if total > limit:
                    notes.append("stopped: more than %d bytes" % limit)
                    return notes
                try:
                    shutil.copyfile(p, os.path.join(target, name))
                except OSError as exc:
                    notes.append("uncopied %s: %s" % (p, exc))
            else:
                notes.append("special file not copied: %s" % p)
    return notes


def _stats(values):
    if not values:
        return None
    v = sorted(values)
    def pct(q):
        return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]
    return {"n": len(v), "min_ms": round(v[0], 3), "median_ms": round(pct(0.5), 3),
            "p95_ms": round(pct(0.95), 3), "max_ms": round(v[-1], 3)}


class Driver:
    def __init__(self, args):
        self.args = args
        self.evidence = os.path.abspath(args.evidence)
        self.gate_ms = 100.0
        self.gate = args.timing_gate == "on"
        self.aliases = {}
        self.results = []
        self.controls = []
        self.driver_controls = []
        self.removals = []
        self.started_at = utc_now()
        repo = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
        work_parent = os.path.realpath(args.work or tempfile.gettempdir())
        self.work = os.path.realpath(tempfile.mkdtemp(prefix="stewart-accept-", dir=work_parent))
        if (self.work + os.sep).startswith(repo + os.sep) and os.path.isdir(os.path.join(repo, "service")):
            _rmtree(self.work)
            raise SystemExit("refusing: the work directory %s is inside the repository %s; use --work" % (self.work, repo))
        if (os.path.realpath(self.evidence) + os.sep).startswith(self.work + os.sep):
            raise SystemExit("refusing: the evidence folder is inside the work directory")
        os.makedirs(self.evidence)
        self.release = self.install(args.binary, "release", "stewart")
        self.test = self.install(args.test_binary, "test", "stewart-test")
        # Cases that need the fake provider listen on 127.0.0.1. Where this process may not
        # listen (a sandbox without local binding), they are skipped with this reason.
        self.loopback_problem = loopback_listen_probe()
        self.protocol_samples = []

    def install(self, src, kind, name):
        d = os.path.join(self.work, "install", kind)
        os.makedirs(d)
        dst = os.path.join(d, name)
        shutil.copyfile(src, dst)
        os.chmod(dst, 0o755)
        return {"kind": kind, "source": os.path.abspath(src), "source_sha256": sha256_file(src),
                "path": os.path.realpath(dst), "sha256": sha256_file(dst), "size": os.path.getsize(dst)}

    def register_alias(self, path, b):
        self.aliases[os.path.realpath(path)] = b

    def digest_of(self, path):
        rp = os.path.realpath(path)
        for b in (self.release, self.test):
            if rp == b["path"]:
                return b["sha256"]
        if rp in self.aliases:
            return self.aliases[rp]["sha256"]
        return sha256_file(path)

    def timing_gate_ok(self, samples):
        worst = max(samples) if samples else None
        return (worst is not None and worst < self.gate_ms), worst

    # -- running ------------------------------------------------------------
    def select(self):
        chosen = []
        for spec in CASES:
            if self.args.case and not any(fnmatch.fnmatchcase(spec.id, p) for p in self.args.case):
                continue
            if self.args.exclude and any(fnmatch.fnmatchcase(spec.id, p) for p in self.args.exclude):
                continue
            chosen.append(spec)
        return chosen

    def skip_reason(self, spec):
        if ("linux" in spec.needs or "lock" in spec.needs) and not is_linux():
            return "Linux-only expectation: %s" % (spec.linux_reason or "needs Linux")
        if "nonroot" in spec.needs and os.geteuid() == 0:
            return "needs an unprivileged user: root bypasses file permissions"
        if spec.heavy and self.args.skip_heavy:
            return "heavy case skipped by --skip-heavy"
        if "loopback" in spec.needs and self.loopback_problem:
            return self.loopback_problem
        if "isolated" in spec.needs and not self.args.network_isolated:
            return ("needs --network-isolated: the binary would try to resolve provider.test itself, which is "
                    "only done where the run has no network (the container suite's --network none)")
        return None

    def variants(self, spec):
        out = []
        if spec.mode == "driver":
            return [("driver", self.release, None)]
        if spec.mode in ("release", "both"):
            out.append(("release", self.release, None))
        if spec.mode == "test":
            out.append(("test", self.test, None))
        elif spec.mode == "both" or spec.controls:
            out.append(("test-baseline", self.test, None))
        for c in spec.controls:
            out.append(("control-" + c.sabotage, self.test, c))
        return out

    def log(self, text):
        sys.stderr.write("%s %s\n" % (utc_now(), text))
        sys.stderr.flush()

    def run_case(self, spec):
        res = {"id": spec.id, "claims": spec.claims, "title": spec.title, "doc": spec.doc, "mode": spec.mode,
               "tags": sorted(spec.tags), "variants": [], "controls": []}
        reason = self.skip_reason(spec)
        if reason:
            res["outcome"], res["skip_reason"] = "skipped", reason
            for c in spec.controls:
                entry = {"case": spec.id, "sabotage": c.sabotage, "targets": c.target_text, "status": "skipped",
                         "reason": reason}
                res["controls"].append(entry)
                self.controls.append(entry)
            self.log("SKIP %s: %s" % (spec.id, reason))
            return res
        for name, binary, control in self.variants(spec):
            self.log("run  %s [%s]" % (spec.id, name))
            vr = self.run_variant(spec, name, binary, control)
            res["variants"].append(vr)
            self.log("%s %s [%s] %d/%d checks" % (vr["outcome"].upper().ljust(4), spec.id, name,
                                                 vr["checks_passed"], vr["checks_passed"] + vr["checks_failed"]))
        main = [v for v in res["variants"] if not v["name"].startswith("control-")]
        if any(v["outcome"] == "skipped" for v in main):
            res["outcome"] = "skipped"
            res["skip_reason"] = "; ".join(v.get("skip_reason") or "" for v in main if v["outcome"] == "skipped")
        elif all(v["outcome"] == "pass" for v in main):
            res["outcome"] = "pass"
        else:
            res["outcome"] = "fail"
        baseline = next((v for v in main if v["binary"] == "test"), None)
        for c in spec.controls:
            v = next(x for x in res["variants"] if x["name"] == "control-" + c.sabotage)
            matched = [f for f in v["failed_names"] if any(r.search(f) for r in c.targets)]
            if v["outcome"] == "skipped" or (baseline and baseline["outcome"] == "skipped"):
                status = "skipped"
            elif baseline is None or baseline["outcome"] != "pass":
                status = "baseline_failed"
            else:
                status = "fired" if matched else "not_fired"
            entry = {"case": spec.id, "sabotage": c.sabotage, "targets": c.target_text, "status": status,
                     "matched_failures": sorted(set(matched))[:20],
                     "other_failures": sorted(set(v["failed_names"]) - set(matched))[:20]}
            res["controls"].append(entry)
            self.controls.append(entry)
        return res

    def run_variant(self, spec, name, binary, control):
        t = T(self, spec, name, binary, control)
        t.drv_controls = []
        started = time.time()
        skip = None
        try:
            spec.fn(t)
        except Skip as exc:
            skip = str(exc)
        except Abort:
            pass
        except Exception:
            t.check("driver.exception", False, traceback.format_exc())
        try:
            t.finish_variant()
        except Exception:
            t.check("driver.finish", False, traceback.format_exc())
        for s in SocketHolder.sockets:
            try:
                s.close()
            except OSError:
                pass
        SocketHolder.sockets = []
        failed = [c for c in t.checks if not c["ok"]]
        outcome = "skipped" if skip else ("pass" if not failed else "fail")
        for dc in t.drv_controls:
            dc["case"] = spec.id
            self.driver_controls.append(dc)
        vr = {"name": name, "binary": binary["kind"], "sabotage": t.sabotage, "outcome": outcome,
              "skip_reason": skip, "checks_passed": len(t.checks) - len(failed), "checks_failed": len(failed),
              "failed_names": [c["name"] for c in failed], "failures": failed[:40],
              "parts_skipped": t.parts_skipped, "commands": len(t.commands),
              "seconds": round(time.time() - started, 3), "work": t.root}
        with open(os.path.join(t.evid, "RESULT.json"), "w", encoding="utf-8") as f:
            json.dump({"case": spec.id, "variant": vr, "checks": t.checks, "inventory": t.inventory_log,
                       "commands": t.commands}, f, ensure_ascii=False, indent=1)
        self.timing_samples = getattr(self, "timing_samples", [])
        for m in t.protocol_timings:
            self.protocol_samples.append(dict(m, binary=binary["kind"], sabotage=t.sabotage, case=spec.id,
                                              variant=name))
        for m in t.commands:
            self.timing_samples.append({"op": m["op"], "binary": m["binary"], "wall_ms": m["wall_ms"],
                                        "maxrss_kib": m["maxrss_kib"], "fault": m["fault"],
                                        "sabotage": m["sabotage"], "background": m["background"],
                                        "rc": m["rc"], "case": spec.id, "variant": name})
        is_control = control is not None
        purpose_served = (outcome == "pass" and not is_control) or (is_control and outcome == "fail")
        if purpose_served and self.args.keep_work != "all":
            plan = {"path": t.root, "case": spec.id, "variant": name, "planned_at": utc_now()}
            self.removals.append(plan)
            try:
                _rmtree(t.root)
                plan["removed"] = not os.path.lexists(t.root)
            except Exception as exc:
                plan["removed"] = False
                plan["error"] = str(exc)
        elif not purpose_served:
            notes = copy_tree_safe(t.root, os.path.join(t.evid, "work"), 64 << 20)
            vr["work_copy_notes"] = notes[:20]
        return vr

    def timing_report(self):
        samples = getattr(self, "timing_samples", [])
        by = {}
        for s in samples:
            if s["background"] or (s["rc"] is not None and s["rc"] < 0):
                continue
            key = "%s/%s%s" % (s["op"], s["binary"], "" if not (s["fault"] or s["sabotage"]) else "+test-env")
            by.setdefault(key, []).append(s["wall_ms"])
        table = {k: _stats(v) for k, v in sorted(by.items())}
        gated = [s for s in samples if s["op"] in GATED_OPS and s["binary"] == "release" and not s["fault"]
                 and not s["sabotage"] and not s["background"] and s["rc"] is not None and s["rc"] >= 0]
        ok, worst = self.timing_gate_ok([s["wall_ms"] for s in gated])
        slow = sorted(gated, key=lambda s: -s["wall_ms"])[:10]
        gate = {"enabled": self.gate, "threshold_ms": self.gate_ms, "ops": list(GATED_OPS),
                "samples": len(gated), "worst_ms": worst, "slowest": slow,
                "passed": (ok if gated else None) if self.gate else None,
                "note": ("gated: native run in the test image" if self.gate else
                         "reported, not gated: only native runs in the Linux test image gate (ACCEPTANCE C9)")}
        # Protocol calls (C9): the fake provider measures, for a response holding one tool call,
        # the time from its last byte sent to the first byte of the next request. That interval
        # bounds the call from above (it also holds Stewart's captures and the new connection).
        # A search over the whole default scope is excluded, as ACCEPTANCE C9 states.
        proto = getattr(self, "protocol_samples", [])
        for s in proto:
            key = "protocol:%s/%s%s" % (s["tool"], s["binary"], "+sabotage" if s.get("sabotage") else "")
            table.setdefault(key, None)
        pby = {}
        for s in proto:
            key = "protocol:%s/%s%s" % (s["tool"], s["binary"], "+sabotage" if s.get("sabotage") else "")
            pby.setdefault(key, []).append(s["ms"])
        for k, v in pby.items():
            table[k] = _stats(v)
        pg = [s for s in proto if s.get("gated") and s["binary"] == "release" and not s.get("sabotage")]
        pok, pworst = self.timing_gate_ok([s["ms"] for s in pg])
        gate["protocol"] = {"samples": len(pg), "worst_ms": pworst,
                            "slowest": sorted(pg, key=lambda s: -s["ms"])[:10],
                            "passed": (pok if pg else None) if self.gate else None}
        return table, gate

    def run(self):
        selected = self.select()
        platform_info = {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
                         "python": sys.version, "euid": os.geteuid(), "work": self.work,
                         "work_filesystem": fs_type_of(self.work), "linux": is_linux()}
        start = {"schema": DRIVER_SCHEMA, "started_at": self.started_at, "argv": sys.argv,
                 "platform": platform_info, "binaries": {"release": self.release, "test": self.test},
                 "selected": [s.id for s in selected], "timing_gate": self.gate,
                 "emulator_home_artifacts": list(EMULATOR_HOME_ARTIFACTS)}
        with open(os.path.join(self.evidence, "START.json"), "w", encoding="utf-8") as f:
            json.dump(start, f, ensure_ascii=False, indent=1)
        interrupted = False
        try:
            for spec in selected:
                self.results.append(self.run_case(spec))
        except KeyboardInterrupt:
            interrupted = True
        table, gate = self.timing_report()
        if gate["enabled"]:
            gres = {"id": "c9.timing-gate", "claims": ["C9"], "title": "startup, status and help within tens of milliseconds",
                    "outcome": "pass" if gate["passed"] else ("skipped" if gate["passed"] is None else "fail"),
                    "variants": [], "controls": [], "doc": "Every gated release-binary invocation under %d ms." % self.gate_ms}
            if gate["passed"] is None:
                gres["skip_reason"] = "no gated samples were collected"
            self.results.append(gres)
            pgate = gate["protocol"]
            pres = {"id": "c9.protocol-timing-gate", "claims": ["C9"],
                    "title": "every protocol call except a full-material search within tens of milliseconds",
                    "outcome": "pass" if pgate["passed"] else ("skipped" if pgate["passed"] is None else "fail"),
                    "variants": [], "controls": [],
                    "doc": "Every gated single-call interval measured by the fake provider under %d ms." % self.gate_ms}
            if pgate["passed"] is None:
                pres["skip_reason"] = "no gated protocol samples were collected"
            self.results.append(pres)
        return self.write_results(platform_info, table, gate, interrupted)

    def write_results(self, platform_info, table, gate, interrupted):
        cases = self.results
        count = lambda o: sum(1 for c in cases if c["outcome"] == o)
        variants = [v for c in cases for v in c["variants"]]
        checks_passed = sum(v["checks_passed"] for v in variants)
        checks_failed = sum(v["checks_failed"] for v in variants if not v["name"].startswith("control-"))
        cstat = lambda s: sum(1 for c in self.controls if c["status"] == s)
        dfired = sum(1 for d in self.driver_controls if d["fired"])
        broken = [c for c in self.controls if c["status"] in ("not_fired", "baseline_failed")]
        broken += [dict(d, status="not_fired") for d in self.driver_controls if not d["fired"]]
        failed_cases = [c["id"] for c in cases if c["outcome"] == "fail"]
        # Every sabotage control of Appendix C.2 must be assigned to a case and fire (ACCEPTANCE
        # "It can fail"). With --require-all-controls an unassigned or unfired name is a broken check.
        fired = {c["sabotage"] for c in self.controls if c["status"] == "fired"}
        assigned = {c.sabotage for spec in CASES for c in spec.controls}
        unassigned = [s for s in SABOTAGES if s not in assigned]
        unfired = [s for s in SABOTAGES if s in assigned and s not in fired]
        if self.args.require_all_controls:
            broken += [{"case": None, "sabotage": s, "status": "unassigned"} for s in unassigned]
            broken += [{"case": None, "sabotage": s, "status": "never_fired"} for s in unfired]
        exit_code = 1 if (failed_cases or broken or interrupted or not cases) else 0
        result = {
            "schema": DRIVER_SCHEMA, "started_at": self.started_at, "ended_at": utc_now(), "argv": sys.argv,
            "interrupted": interrupted, "platform": platform_info,
            "binaries": {"release": self.release, "test": self.test},
            "counts": {"cases": {"selected": len(cases), "ran": len(cases) - count("skipped"), "passed": count("pass"),
                                 "failed": count("fail"), "skipped": count("skipped")},
                       "variants": {"ran": len(variants), "passed": sum(1 for v in variants if v["outcome"] == "pass"),
                                    "failed": sum(1 for v in variants if v["outcome"] == "fail"),
                                    "skipped": sum(1 for v in variants if v["outcome"] == "skipped")},
                       "checks": {"passed": checks_passed, "failed_outside_controls": checks_failed,
                                  "failed_inside_controls": sum(v["checks_failed"] for v in variants if v["name"].startswith("control-"))},
                       "controls": {"total": len(self.controls), "fired": cstat("fired"), "not_fired": cstat("not_fired"),
                                    "baseline_failed": cstat("baseline_failed"), "skipped": cstat("skipped")},
                       "driver_controls": {"total": len(self.driver_controls), "fired": dfired}},
            "failed_cases": failed_cases, "broken_checks": broken,
            "controls_unassigned": unassigned, "controls_never_fired": unfired,
            "controls": self.controls, "driver_controls": self.driver_controls,
            "timing_gate": gate, "timings": table, "cases": cases, "removals": self.removals,
            "work": self.work, "exit": exit_code,
        }
        with open(os.path.join(self.evidence, "RESULT.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        with open(os.path.join(self.evidence, "RESULTS.md"), "w", encoding="utf-8") as f:
            f.write(self.summary_md(result))
        if self.args.keep_work != "all":
            leftover = [os.path.join(self.work, x) for x in os.listdir(self.work)]
            if all(x.endswith(os.sep + "install") for x in leftover):
                _rmtree(self.work)
        return exit_code

    def summary_md(self, r):
        c = r["counts"]
        lines = ["# Stewart acceptance driver results", "",
                 "Driver `%s`, %s to %s. Exit status %d." % (DRIVER_SCHEMA, r["started_at"], r["ended_at"], r["exit"]), "",
                 "Platform: %s %s %s, Python %s, euid %s, work filesystem %s." % (
                     r["platform"]["system"], r["platform"]["release"], r["platform"]["machine"],
                     r["platform"]["python"].split()[0], r["platform"]["euid"], r["platform"]["work_filesystem"]), "",
                 "| Binary | SHA-256 | Bytes |", "| --- | --- | --- |"]
        for k in ("release", "test"):
            b = r["binaries"][k]
            lines.append("| %s `%s` | `%s` | %d |" % (k, b["source"], b["sha256"], b["size"]))
        lines += ["", "## Counts", "",
                  "- Cases: %(selected)d selected, %(ran)d ran, %(passed)d passed, %(failed)d failed, %(skipped)d skipped." % c["cases"],
                  "- Variants: %(ran)d ran, %(passed)d passed, %(failed)d failed, %(skipped)d skipped." % c["variants"],
                  "- Checks: %d passed; %d failed outside control variants; %d failed inside control variants (expected)." % (
                      c["checks"]["passed"], c["checks"]["failed_outside_controls"], c["checks"]["failed_inside_controls"]),
                  "- Sabotage controls: %(total)d, fired %(fired)d, not fired %(not_fired)d, baseline failed %(baseline_failed)d, skipped %(skipped)d." % c["controls"],
                  "- Driver controls: %(total)d, fired %(fired)d." % c["driver_controls"],
                  "- Sabotage names of Appendix C.2: %d, assigned to no case %d, never fired %d." % (
                      len(SABOTAGES), len(r["controls_unassigned"]), len(r["controls_never_fired"])), ""]
        g = r["timing_gate"]
        lines += ["## Timing gate (C9)", "", "%s. Threshold %d ms over %s; %d samples; worst %s ms; passed %s." % (
            g["note"], g["threshold_ms"], ", ".join(g["ops"]), g["samples"],
            "-" if g["worst_ms"] is None else "%.1f" % g["worst_ms"], g["passed"]), ""]
        lines += ["| Operation/binary | n | median ms | p95 ms | max ms |", "| --- | --- | --- | --- | --- |"]
        for k, s in r["timings"].items():
            if s:
                lines.append("| %s | %d | %.1f | %.1f | %.1f |" % (k, s["n"], s["median_ms"], s["p95_ms"], s["max_ms"]))
        pg = g.get("protocol") or {}
        lines += ["", "Protocol calls: %s samples gated; worst %s ms; passed %s." % (
            pg.get("samples", 0), "-" if pg.get("worst_ms") is None else "%.1f" % pg["worst_ms"], pg.get("passed"))]
        lines += ["", "## Cases by claim", ""]
        claims = {}
        for case_ in r["cases"]:
            for cl in case_["claims"] or ["apparatus"]:
                claims.setdefault(cl, []).append(case_)
        order = sorted(claims, key=lambda x: (x == "apparatus", int(x[1:]) if x[1:].isdigit() else 0))
        for cl in order:
            lines.append("- **%s**: %s" % (cl, ", ".join("`%s` %s" % (x["id"], x["outcome"]) for x in claims[cl])))
        lines += ["", "## Controls", "", "| Case | Sabotage | Status |", "| --- | --- | --- |"]
        for x in r["controls"]:
            lines.append("| `%s` | `%s` | %s |" % (x["case"], x["sabotage"], x["status"]))
        for x in r["driver_controls"]:
            lines.append("| `%s` | driver: `%s` | %s |" % (x["case"], x["name"], "fired" if x["fired"] else "not_fired"))
        if r["broken_checks"]:
            lines += ["", "Broken checks (a control that did not make its check fail): " +
                      ", ".join("`%s`/`%s`" % (b.get("case"), b.get("sabotage") or b.get("name")) for b in r["broken_checks"])]
        fails = [x for x in r["cases"] if x["outcome"] == "fail"]
        if fails:
            lines += ["", "## Failed cases", ""]
            for x in fails:
                for v in x["variants"]:
                    if v["outcome"] == "fail" and not v["name"].startswith("control-"):
                        lines.append("- `%s` [%s]: %s" % (x["id"], v["name"], ", ".join(sorted(set(v["failed_names"]))[:12])))
        skipped = [x for x in r["cases"] if x["outcome"] == "skipped"]
        parts = [(x["id"], p) for x in r["cases"] for v in x["variants"] for p in v.get("parts_skipped", [])]
        if skipped or parts:
            lines += ["", "## Skipped", ""]
            lines += ["- `%s`: %s" % (x["id"], x.get("skip_reason")) for x in skipped]
            seen = set()
            for cid, p in parts:
                key = (cid, p["part"])
                if key not in seen:
                    seen.add(key)
                    lines.append("- `%s` part %s: %s" % (cid, p["part"], p["reason"]))
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-test of the driver's helpers (no Stewart binary needed).
# ---------------------------------------------------------------------------

def _section(text, heading):
    """The lines of a Markdown section after its heading, to the next heading outside a code
    fence (a fenced `# comment` line is not a heading)."""
    lines = text.split("\n")
    try:
        i = lines.index(heading)
    except ValueError:
        return []
    out, fenced = [], False
    for line in lines[i + 1:]:
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(r"^#{1,6} ", line):
            break
        out.append(line)
    return out


def _interface_copies(text):
    """(name, ok, detail) comparing the driver's copies of INTERFACE facts with docs/INTERFACE.md:
    the C.2 sabotage names in order, the 3.2 effort levels, and the 3.2 template's comment lines
    (the scaffold's) with the effort comments between the model field and the destination comment."""
    out = []
    c2 = _section(text, "### C.2 Sabotage controls")
    names = [m.group(1) for m in (re.match(r"^\| `([a-z_]+)` \|", l) for l in c2) if m]
    out.append(("docs.interface.sabotage-names", tuple(names) == SABOTAGES,
                {"missing_here": [n for n in names if n not in SABOTAGES],
                 "not_in_docs": [n for n in SABOTAGES if n not in names]}))
    s32 = _section(text, "### 3.2 Front matter (`question/1`)")
    row = next((l for l in s32 if l.startswith("| `effort` |")), "")
    levels = re.findall(r"`([a-z]+)`", row.split("|")[3]) if row.count("|") >= 4 else []
    out.append(("docs.interface.effort-levels", tuple(levels) == EFFORT_LEVELS, levels))
    block, inside = [], False
    for l in s32:
        if l.startswith("```"):
            if inside:
                break
            inside = True
            continue
        if inside:
            block.append(l.encode("utf-8"))
    missing = [c.decode() for c in SCAFFOLD_COMMENTS[:-1] if c not in block]
    out.append(("docs.interface.template-comments", block and not missing, missing))
    try:
        i_model = next(i for i, l in enumerate(block) if l.startswith(b"model: "))
        i_effort = block.index(SCAFFOLD_EFFORT_COMMENTS[0])
        placed = (i_effort == i_model + 1 and block[i_effort + 1] == SCAFFOLD_EFFORT_COMMENTS[1]
                  and block[i_effort + 2] == SCAFFOLD_DESTINATION_COMMENT)
    except (StopIteration, ValueError, IndexError):
        placed = False
    out.append(("docs.interface.template-effort-comments", placed, block))
    out.append(("docs.interface.template-no-effort-field", not any(l.startswith(b"effort:") for l in block), block))
    return out


def self_test():
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    def refuses(data):
        try:
            strict_loads(data)
            return False
        except StrictJSONError:
            return True

    ok("json.valid", strict_loads(b'{"a":[1,"x",true,null]}') == {"a": [1, "x", True, None]})
    ok("json.duplicate", refuses(b'{"a":1,"a":2}'))
    ok("json.escaped-duplicate", refuses(b'{"a":1,"\\u0061":2}'))
    ok("json.nested-duplicate", refuses(b'{"x":{"a":1,"a":1}}'))
    ok("json.bom", refuses(b'\xef\xbb\xbf{}'))
    ok("json.trailing", refuses(b'{} x'))
    ok("json.two-values", refuses(b'{}{}'))
    ok("json.float", refuses(b'{"a":1.0}'))
    ok("json.exponent", refuses(b'{"a":1e3}'))
    ok("json.negative", refuses(b'{"a":-1}'))
    ok("json.leading-zero", refuses(b'{"a":01}'))
    ok("json.nan", refuses(b'{"a":NaN}'))
    ok("json.surrogate", refuses(b'{"a":"\\ud800"}'))
    ok("json.nul", refuses(b'{"a":"\\u0000"}'))
    ok("json.invalid-utf8", refuses(b'{"a":"\xff"}'))
    ok("json.depth-16", not refuses(b"[" * 16 + b"]" * 16))
    ok("json.depth-17", refuses(b"[" * 17 + b"]" * 17))
    ok("json.whitespace-ok", strict_loads(b' {"a" : 1}\n') == {"a": 1})
    ok("compact.yes", is_compact_json('{"a":"b c","d":[1,2]}'))
    ok("compact.no", not is_compact_json('{"a": 1}'))
    ok("root.plain", encode_root("/home/ana/stewart-archive") == "/home/ana/stewart-archive")
    ok("root.escapes", encode_root("/a b/ß%") == "/a%20b/%C3%9F%25")
    ok("root.roundtrip", decode_root(encode_root("/x y/文:#@")) == "/x y/文:#@")
    ok("root.lowercase-escape", decode_root("/a%c3%9f") is None)
    ok("root.safe-escaped", decode_root("/%41") is None)
    ok("root.raw-space", decode_root("/a b") is None)
    a, s = random_id("a"), random_id("s")
    ok("ids.form", re.fullmatch(r"a[a-z2-7]{16}", a) and re.fullmatch(r"s[a-z2-7]{16}", s))
    ok("ref.parse", parse_reference(make_reference(a, s, "/r o")) == {"audit": a, "store": s, "root": "/r o"})
    chk = handle_check(s, a, "mp", "mp1", ["0" * 64])
    ok("handle.form", re.fullmatch(r"[a-z2-7]{6}", chk))
    ok("handle.binds", chk != handle_check(s, a, "mp", "mp2", ["0" * 64]) or chk != handle_check(s, a, "ap", "mp1", ["0" * 64]))
    ok("lines", (line_count(b""), line_count(b"\n"), line_count(b"a"), line_count(b"a\nb"), line_count(b"a\n")) == (0, 1, 1, 2, 1))
    ok("split.lf", split_question(b"---\na: b\n---\nbody\n") == b"body\n")
    ok("split.crlf", split_question(b"---\r\na: b\r\n---\r\nbody") == b"body")
    ok("split.bom", split_question(b"\xef\xbb\xbf---\n---\n") == b"")
    ok("split.unclosed", split_question(b"---\na: b\n") is None)
    body = "Body — x\r\n---\nnot a delimiter\n\tTab\nNo final newline".encode("utf-8")
    ok("split.body-delimiter", split_question(b"---\nk: v\n---\n" + body) == body)
    sysv = strict_loads(expected_system_bytes("comparison"))
    ok("system.decodes", sysv == [{"type": "text", "text": ORIENTATION}, {"type": "text", "text": FAMILY_TEXT["comparison"]}])
    ok("tools.counts", [len(expected_tools(f)) for f in ("open-inquiry", "inquiry-framing", "comparison")] == [12, 14, 14])
    ok("question.default-splits", split_question(question_md()) == b"Audit our app to make sure there are no bugs.\n")
    ok("question.crlf-splits", split_question(question_md(b"x\r\n", nl=b"\r\n")) == b"x\r\n")
    ident = big_identity(3 << 20, "seed")
    data = b"".join(big_chunks(3 << 20, "seed"))
    ok("big.identity", ident == {"size": len(data), "sha256": sha256_hex(data), "lines": line_count(data)})
    tmp = os.path.realpath(tempfile.mkdtemp(prefix="stewart-driver-selftest-"))
    try:
        base = os.path.join(tmp, "m")
        os.mkdir(base)
        ents = [F("a.txt", b"a\n"), HARD("b.txt", "a.txt"), D("e/f"), L("l", "a.txt"), FIFO("p"), F("d/deep.txt", b"")]
        build_entries(base, ents)
        files, dirs = material_witness([e for e in ents if e[0] in ("file", "hard", "dir")])
        ok("build.hardlink", os.stat(os.path.join(base, "a.txt")).st_ino == os.stat(os.path.join(base, "b.txt")).st_ino)
        ok("build.fifo", stat.S_ISFIFO(os.lstat(os.path.join(base, "p")).st_mode))
        ok("witness.dirs", dirs == {b"e", b"e/f", b"d"})
        cache = DigestCache()
        s1 = snapshot(base, cache)
        ok("snapshot.kinds", s1["l"]["kind"] == "link" and s1["p"]["kind"] == "fifo" and s1["a.txt"]["kind"] == "file")
        with open(os.path.join(base, "new.txt"), "wb") as f:
            f.write(b"n")
        v, added = compare_snapshots(s1, snapshot(base, cache), True)
        ok("snapshot.addition", not v and added == ["new.txt"])
        v, added = compare_snapshots(s1, snapshot(base, cache), False)
        ok("snapshot.frozen-addition", v and v[0][0] == "added")
        s2 = snapshot(base, cache)
        with open(os.path.join(base, "d", "deep.txt"), "wb") as f:
            f.write(b"x")
        v, _ = compare_snapshots(s2, snapshot(base, cache), True)
        ok("snapshot.rewrite", v and v[0] == ("rewritten", "d/deep.txt"))
        s3 = snapshot(base, cache)
        os.chmod(os.path.join(base, "a.txt"), 0o600)
        v, _ = compare_snapshots(s3, snapshot(base, cache), True)
        ok("snapshot.mode", any(x[0] == "mode_changed" for x in v))
        res = Proc(["/bin/sh", "-c", "printf out; printf err >&2; exit 3"], {"PATH": "/usr/bin:/bin"}, tmp, 10).wait()
        ok("proc.streams", res["rc"] == 3 and res["stdout"] == b"out" and res["stderr"] == b"err")
        res = Proc(["/bin/sh", "-c", "kill -9 $$"], {"PATH": "/usr/bin:/bin"}, tmp, 10).wait()
        ok("proc.signal", res["rc"] == -9)
        res = Proc(["/bin/sh", "-c", "sleep 5"], {"PATH": "/usr/bin:/bin"}, tmp, 0.3).wait()
        ok("proc.timeout", res["timed_out"])
    finally:
        _rmtree(tmp)
    docs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "QUESTION-FORMS.md")
    if os.path.isfile(docs):
        text = open(docs, encoding="utf-8").read()
        quoted, cur = [], []
        for line in text.split("\n"):
            if line.startswith(">"):
                cur.append(line[1:].lstrip(" ") if line != ">" else "")
            elif cur:
                quoted.append(cur)
                cur = []
        texts = []
        for block in quoted:
            paras, p = [], []
            for l in block:
                if l == "":
                    if p:
                        paras.append(" ".join(p))
                        p = []
                else:
                    p.append(l)
            if p:
                paras.append(" ".join(p))
            texts.append("\n\n".join(paras))
        for label, want in [("orientation", ORIENTATION), ("reminder", REMINDER), ("near-limit", NEAR_LIMIT),
                            ("continuation", CONTINUATION)] + [("family " + k, v) for k, v in FAMILY_TEXT.items()]:
            ok("docs.%s" % label, want in texts, "embedded text differs from docs/QUESTION-FORMS.md")
        for name, desc in TOOL_DESC.items():
            ok("docs.tool.%s" % name, ("| `%s` | %s |" % (name, desc)) in text, name)
    else:
        results.append(("docs.available", True, "docs/QUESTION-FORMS.md not beside the driver; skipped"))
    iface = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "INTERFACE.md")
    if os.path.isfile(iface):
        for item in _interface_copies(open(iface, encoding="utf-8").read()):
            ok(*item)
    else:
        results.append(("docs.interface-available", True, "docs/INTERFACE.md not beside the driver; skipped"))
    # Self-tests registered by the driver's other modules (fake provider, auditor, witness).
    for fn in SELF_TESTS:
        try:
            for item in fn():
                name, good = item[0], item[1]
                detail = item[2] if len(item) > 2 else ""
                results.append((name, None if good is None else bool(good), detail))
        except Exception:
            results.append(("%s.raised" % fn.__name__, False, traceback.format_exc()[-1500:]))
    # A check whose ok is None was skipped (with its reason as detail), never passed.
    bad = [r for r in results if r[1] is False]
    skipped = [r for r in results if r[1] is None]
    for name, good, detail in results:
        mark = "skip" if good is None else ("ok  " if good else "FAIL")
        sys.stdout.write("%s %s%s\n" % (mark, name, (" (%s)" % short(detail, 400)) if (detail and not good) else ""))
    sys.stdout.write("self-test: %d checks, %d passed, %d failed, %d skipped\n" % (
        len(results), len(results) - len(bad) - len(skipped), len(bad), len(skipped)))
    return 1 if bad else 0


# ---------------------------------------------------------------------------
# Command line.
# ---------------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="stewart_driver.py",
        description="Independent black-box acceptance driver for Stewart. "
                    "Runs every selected case against the release binary, and each case's sabotage controls "
                    "and fault cases against the test binary, keeping a witness and inventories outside the archive. "
                    "Writes START.json, RESULT.json, RESULTS.md and per-command evidence into a new evidence folder.",
        epilog="Exit status: 0 when every selected case passed or was skipped with a reason and every control "
               "fired; 1 when a case failed or a control did not fire; 2 for a usage refusal.")
    p.add_argument("--binary", help="release `stewart` binary (built without test features)")
    p.add_argument("--test-binary", help="test build `stewart-test` (features fault-injection and sabotage)")
    p.add_argument("--evidence", help="new evidence folder; refused if it exists")
    p.add_argument("--case", action="append", default=[], metavar="PATTERN",
                   help="run only cases whose ID matches this glob (repeatable), e.g. 'c17.*'")
    p.add_argument("--exclude", action="append", default=[], metavar="PATTERN",
                   help="skip cases whose ID matches this glob (repeatable), e.g. 'close.*'")
    p.add_argument("--work", metavar="DIR",
                   help="parent for the temporary work directory (archives, folders, homes); default: the system "
                        "temporary directory. Must be outside the repository; on Linux use ext4, xfs or btrfs.")
    p.add_argument("--timing-gate", choices=("on", "off"), default="off",
                   help="gate startup, status and help at under 100 ms (only for native runs in the Linux test "
                        "image); default off, which reports timings without gating")
    p.add_argument("--skip-heavy", action="store_true", help="skip the 16 MiB and 128 MiB bound cases")
    p.add_argument("--require-all-controls", action="store_true",
                   help="fail unless every sabotage control of INTERFACE Appendix C.2 is assigned to a selected "
                        "case and fired (the full suite sets this)")
    p.add_argument("--network-isolated", action="store_true",
                   help="declare that this run has no network (container --network none); enables the cases in "
                        "which the binary resolves provider.test itself and must fail offline")
    p.add_argument("--emulator-home-artifact", action="append", default=[], metavar="RELPATH",
                   help="a path an emulator creates under HOME by itself (e.g. .cache/rosetta); "
                        "recorded as an emulator artifact instead of a write by Stewart")
    p.add_argument("--keep-work", choices=("failed", "all"), default="failed",
                   help="'failed' (default) removes the work directory of each passing variant after recording it "
                        "and copies small failing ones into the evidence; 'all' keeps every work directory")
    p.add_argument("--list", action="store_true", help="print the case inventory and exit")
    p.add_argument("--self-test", action="store_true", help="check the driver's own helpers and exit")
    args = p.parse_args(argv)
    if not (args.list or args.self_test):
        missing = [n for n in ("binary", "test_binary", "evidence") if not getattr(args, n)]
        if missing:
            p.error("missing --%s" % ", --".join(m.replace("_", "-") for m in missing))
        for n in ("binary", "test_binary"):
            path = getattr(args, n)
            if not (os.path.isfile(path) and os.access(path, os.X_OK)):
                p.error("--%s %s is not an executable file" % (n.replace("_", "-"), path))
        if os.path.lexists(args.evidence):
            p.error("--evidence %s exists; each run needs a new evidence folder" % args.evidence)
        if not os.path.isdir(os.path.dirname(os.path.abspath(args.evidence))):
            p.error("the parent of --evidence %s does not exist" % args.evidence)
        if args.work and not os.path.isdir(args.work):
            p.error("--work %s is not an existing directory" % args.work)
    return args


def list_cases():
    for spec in CASES:
        extra = []
        if spec.mode != "release":
            extra.append("mode=%s" % spec.mode)
        if spec.needs:
            extra.append("needs=%s" % ",".join(sorted(spec.needs)))
        if spec.heavy:
            extra.append("heavy")
        if spec.controls:
            extra.append("controls=%s" % ",".join(c.sabotage for c in spec.controls))
        sys.stdout.write("%-34s %-22s %s%s\n" % (spec.id, ",".join(spec.claims) or "-", spec.title,
                                                 (" [" + "; ".join(extra) + "]") if extra else ""))
    sys.stdout.write("%d cases\n" % len(CASES))


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    EMULATOR_HOME_ARTIFACTS[:] = [a.strip('/') for a in args.emulator_home_artifact]
    if args.list:
        list_cases()
        return 0
    if args.self_test:
        return self_test()
    os.umask(0o022)
    drv = Driver(args)
    code = drv.run()
    sys.stderr.write("evidence: %s (exit %d)\n" % (drv.evidence, code))
    return code

