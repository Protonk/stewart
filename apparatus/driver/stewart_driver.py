#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent black-box acceptance driver for Stewart step 3 (manager foundation).

Run it with an explicit interpreter and isolated startup:

    python3 -I -B apparatus/driver/stewart_driver.py \\
        --binary /abs/stewart --test-binary /abs/stewart-test \\
        --evidence /abs/new-evidence-folder [--case PATTERN]... [--exclude PATTERN]...

`--list` prints the case inventory; `--self-test` checks the driver's own
helpers without any Stewart binary.

The driver is written from docs/INTERFACE.md, CONTRACTS.md and ACCEPTANCE.md
alone; its author did not read the implementation in service/. It drives the
binaries only through their command line (`--json` replies and raw
`receipt --read`), from fresh temporary homes and working directories in
nested paths unrelated to the repository.

Evidence rules it follows (ACCEPTANCE, "Rules every check follows"):

- Witness. Everything the driver supplies (question files, materials) is kept
  in its own witness under the evidence folder, outside every archive and
  outside anything a case removes. Readback is compared with the witness,
  never with Stewart's records.
- Inventory. Every archive is inventoried (path, type, inode, size, mode,
  mtime, SHA-256) before and after every command; an earlier entry may never
  disappear, change type or inode, or change bytes or mode (C6). Folders,
  destinations, homes and working directories must not change at all.
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

DRIVER_SCHEMA = "stewart.step3-driver/1"
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
SABOTAGES = ("accept_without_affirmation", "accept_changed_source", "skip_hidden_entries",
             "normalize_newlines", "follow_symlinks", "readback_live_source",
             "regenerate_arrangement", "rewrite_record_in_place", "remove_partial_on_retry",
             "unknown_as_absent", "select_newer_store", "accept_unknown_field",
             "omit_effects_on_refusal", "whole_from_one_member")
TEST_ENV_NAMES = (b"STEWART_TEST_FAULT", b"STEWART_TEST_SABOTAGE")

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
SCAFFOLD_COMMENTS = [
    b"# Question family: open-inquiry, inquiry-framing or comparison.",
    b"# Run `stewart help forms` to read each family's instructions.",
    b"# Provider model used for every run of this audit.",
    b"# Existing directory in which Stewart creates the return package.",
    b"# Cumulative limits across all runs, from the provider's usage reports.",
    b"# Write your question below the closing --- line.",
]

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
                nl=b"\n", bom=False, extra=(), omit=(), comments=True):
    def enc(v):
        return v if isinstance(v, bytes) else str(v).encode("utf-8")

    fields = [("stewart", b"question/1"), ("family", enc(family)), ("model", enc(model)),
              ("destination", enc(dest)), ("limit-turns", enc(turns)),
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

    def __init__(self, t, folder, dest, archive, question, entries, root_entries, family, model, limits):
        self.t, self.folder, self.dest, self.archive = t, folder, dest, archive
        self.question = question
        self.body = split_question(question)
        self.entries = list(entries)
        self.root_entries = list(root_entries)
        self.family, self.model, self.limits = family, model, limits
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
        self.writer = binary["path"]
        self.faults = self.mkdir("faults")
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
        """mode 'archive': earlier entries must stay identical; 'frozen': nothing may change."""
        if path in self.watches:
            return
        self.watches[path] = {"mode": mode, "label": label or path,
                              "last": snapshot(path, self.cache)}

    def sync(self, label, readonly=False):
        for path, w in self.watches.items():
            snap = snapshot(path, self.cache)
            only_add = w["mode"] == "archive"
            violations, added = compare_snapshots(w["last"], snap, only_add)
            if readonly and only_add and added:
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

    def rebaseline(self, note):
        for path, w in self.watches.items():
            w["last"] = snapshot(path, self.cache)
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
            env["STEWART_TEST_FAULT_DIR"] = self.faults
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

    def wait_paused(self, point, h=None, timeout=30.0):
        """Wait until a pause fault created <point...>.paused; return its stem."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            for name in sorted(os.listdir(self.faults)):
                if name.endswith(".paused") and name.startswith(point):
                    stem = name[:-len(".paused")]
                    if not os.path.exists(os.path.join(self.faults, stem + ".go")):
                        return stem
            if h is not None and not h["proc"].running():
                self.check("fault.%s.paused" % point, False, "process exited before pausing")
                return None
            time.sleep(0.01)
        self.check("fault.%s.paused" % point, False, "no .paused file within %ss" % timeout)
        return None

    def release(self, stem):
        if stem:
            with open(os.path.join(self.faults, stem + ".go"), "wb"):
                pass

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
            self.check("exit.matches-outcome", rep.rc == EXIT_FOR_OUTCOME[outcome],
                       "%s: outcome %s exited %s" % (name, outcome, rep.rc))
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

    def intake_dirs(self, sub):
        d = os.path.join(sub.audit_dir, "intake")
        try:
            return sorted(os.listdir(d))
        except OSError:
            return []

    # -- submissions ------------------------------------------------------
    def submission(self, entries, *, question=None, body=b"Audit our app to make sure there are no bugs.\n",
                   family="open-inquiry", model="claude-opus-5-5", archive=None, root_entries=(),
                   q=None, folder=None, dest=None, make_question=True, make_materials=True):
        folder = folder or self.folder_path()
        dest = dest or self.dest_path()
        q = dict(q or {})
        limits = (int(q.get("turns", 200)) if str(q.get("turns", 200)).isdigit() else None,
                  int(q.get("input_tokens", 20000000)) if str(q.get("input_tokens", 20000000)).isdigit() else None,
                  int(q.get("output_tokens", 400000)) if str(q.get("output_tokens", 400000)).isdigit() else None)
        if question is None:
            question = question_md(body, family=family, model=model, dest=q.pop("dest", dest), **q)
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
                  family, model, limits)
        self.watch(folder, "frozen", "folder")
        self.watch(dest, "frozen", "destination")
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
        self.eq("%s.reader" % name, d.get("reader"), {"id": "utf8-text/1", "transformations": "none"})
        self.eq("%s.bounds" % name, d.get("bounds"), BOUNDS)

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
# Shared case material.
# ---------------------------------------------------------------------------

NFD_E = unicodedata.normalize("NFD", "é")
FAULT_POINT_NAMES = (b"prepare.before_prepared_link", b"commission.after_capture",
                     b"commission.source_read", b"commission.capture_write",
                     b"commission.capture_corrupt", b"commission.receipt_write",
                     b"commission.before_accepted_link", b"commission.accepted_dirsync",
                     b"commission.after_accepted_link", b"close.before_closed_link")


def basic_entries():
    return [F("a.txt", b"alpha\nbeta\n"), F("b.txt", b"bravo\n"), F("src/c.py", b"def f():\n    return 1\n")]


def population_entries():
    return [
        F(".hidden", b"hidden file\n"),
        F(".git/config", b"[core]\n\tbare = false\n"),
        F("dir/.env", b"KEY=value\n"),
        F("empty.txt", b""),
        D("empty-dir"),
        D("nested/deeper/empty"),
        F("bom.txt", b"\xef\xbb\xbfBOM first line\n"),
        F("crlf.txt", b"one\r\ntwo\r\nthree\r\n"),
        F("lone-cr.txt", b"a\rb\r"),
        F("mixed.txt", b"lf\ncrlf\r\nnone"),
        F("multibyte.txt", "é 日本語 \U0001F600\nΩ≈ç√\n".encode("utf-8")),
        F("no-final-newline.txt", b"last line without newline"),
        F("only-newline.txt", b"\n"),
        F("name with spaces.txt", b"spaces\n"),
        F("ünïcødé/文件.txt", "unicode name\n".encode("utf-8")),
        F("nfd-" + NFD_E + ".txt", b"nfd name\n"),
        F("#hash%percent+plus~tilde.txt", b"punctuation\n"),
        F("nbsp name.txt", b"no-break space is not a control character\n"),
        F("hard-a.txt", b"linked bytes\n"),
        HARD("hard-b.txt", "hard-a.txt"),
        F("report.pdf", b"%PDF-1.4 this nominal document is plain text\n"),
        F("data.json", b'{"a": 1, "a": 2}\n'),
        F("image.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>\n"),
        F("long-line.txt", b"x" * 70000 + b"\n"),
    ]


POPULATION_BODY = ("Audit our app — ünïcødé included.\r\n"
                   "---\nThat line was body, not a delimiter.\n\tTabbed\nNo final newline").encode("utf-8")


def mat(sub, rel):
    return os.path.join(sub.folder, "materials", rel)


def set_file(t, sub, rel, data, note=None):
    """Write a material in the folder and update the witness (a manager edit)."""
    def fn():
        p = mat(sub, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
    t.driver_change(note or "edit materials/%s" % rel, fn)
    key = rel.encode("utf-8")
    sub.files[key] = {"data": data, "size": len(data), "sha256": sha256_hex(data), "lines": line_count(data)}


def remove_file(t, sub, rel):
    t.driver_change("remove materials/%s" % rel, lambda: os.unlink(mat(sub, rel)))
    sub.files.pop(rel.encode("utf-8"), None)


def add_dir(t, sub, rel):
    t.driver_change("mkdir materials/%s" % rel, lambda: os.mkdir(mat(sub, rel)))
    sub.dirs.add(rel.encode("utf-8"))


def stealth_edit(t, sub, rel, data):
    """Same size, mtime restored: only a digest comparison can see it."""
    p = mat(sub, rel)
    st = os.stat(p)
    assert len(data) == st.st_size, "stealth edit must keep the size"

    def fn():
        with open(p, "r+b") as f:
            f.write(data)
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    t.driver_change("same-size edit of materials/%s with mtime restored" % rel, fn)
    sub.files[rel.encode("utf-8")] = {"data": data, "size": len(data), "sha256": sha256_hex(data),
                                      "lines": line_count(data)}


def find_items(obj, ids):
    """Receipt items located structurally: item ID -> the dict that names it."""
    best = {}
    for v in iter_values(obj):
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            found = {}
            for x in v:
                names = [val for val in x.values() if isinstance(val, str) and val in ids]
                if names:
                    found[names[0]] = x
            if len(found) > len(best):
                best = found
    return best


def item_state(item):
    states = [v for v in item.values() if isinstance(v, str) and v in VERIFY_STATES]
    return states[0] if len(states) == 1 else (states or None)


def item_argv(item, writer):
    for v in item.values():
        if isinstance(v, list) and v and v[0] == writer and all(isinstance(a, str) for a in v):
            return v
    return None


def no_diag(effects):
    return {k: v for k, v in effects.items() if k != "diagnostic"}


def names_bound(rep, bound, limit, entry=None):
    blob = rep.data if rep.data else {}
    text = json.dumps(blob, ensure_ascii=False) + " " + str((rep.obj or {}).get("message", ""))
    ok_bound = bound in text
    ok_limit = mentions(blob, str(limit)) or re.search(r"(?<![0-9])%d(?![0-9])" % limit, text.replace(",", "")) is not None
    ok_entry = entry is None or entry in text
    return ok_bound, ok_limit, ok_entry


def names_offset(rep, entry, offset):
    blob = rep.data if rep.data else {}
    text = json.dumps(blob, ensure_ascii=False) + " " + str((rep.obj or {}).get("message", ""))
    has_offset = (any(isinstance(v, int) and not isinstance(v, bool) and v == offset for v in iter_values(blob))
                  or re.search(r"(?<![0-9])%d(?![0-9])" % offset, str((rep.obj or {}).get("message", ""))) is not None)
    return entry in text, has_offset


# ---------------------------------------------------------------------------
# Apparatus.
# ---------------------------------------------------------------------------

@case("apparatus.identity", [], "binary identities; test-only names exist only in the test build", mode="driver")
def c_identity(t):
    """Records both binaries. The release build must not contain the test environment
    variable names, sabotage names or fault point names (App. C); the test build must
    contain the variable names, which is the firing control for this string check."""
    rel, test = t.drv.release, t.drv.test
    t.check("identity.builds-differ", rel["sha256"] != test["sha256"], "release and test binaries are identical")
    rb, tb = read_bytes(rel["path"]), read_bytes(test["path"])
    for name in TEST_ENV_NAMES + (b"STEWART_TEST_FAULT_DIR",):
        t.check("identity.release-lacks.%s" % name.decode(), name not in rb, "release contains %s" % name.decode())
    for name in TEST_ENV_NAMES:
        t.check("identity.test-has.%s" % name.decode(), name in tb, "test build lacks %s" % name.decode())
    for s in SABOTAGES:
        t.check("identity.release-lacks.%s" % s, s.encode() not in rb, "release contains sabotage name %s" % s)
    for p in FAULT_POINT_NAMES:
        t.check("identity.release-lacks.%s" % p.decode(), p not in rb, "release contains fault point %s" % p.decode())
    if is_linux():
        fst = fs_type_of(t.root)
        t.check("identity.work-filesystem", fst in ("ext4", "xfs", "btrfs"),
                "work directory is on %r; archives need ext4, xfs or btrfs" % fst)
    else:
        t.skip_part("work filesystem allowlist", "Linux-only expectation: macOS development builds have no ext4/xfs/btrfs allowlist")


@case("apparatus.driver-controls", [], "the driver's own checks fail on deliberately broken inputs", mode="driver")
def c_driver_controls(t):
    """Firing controls for the driver's inventory, envelope, witness and timing checks,
    independent of the test build."""
    d = t.mkdir("inventory control")
    build_entries(d, [F("a.json", b"{}\n"), F("b.json", b"[]\n")])
    s1 = snapshot(d, t.cache)
    with open(os.path.join(d, "a.json"), "r+b") as f:
        f.write(b"{}\n")
    v, _ = compare_snapshots(s1, snapshot(d, t.cache), True)
    t.driver_control("inventory_rewrite_in_place", any(x[0] == "rewritten" for x in v), v)
    s2 = snapshot(d, t.cache)
    tmp = os.path.join(d, "a.tmp")
    with open(tmp, "wb") as f:
        f.write(b"{}\n")
    os.replace(tmp, os.path.join(d, "a.json"))
    v, _ = compare_snapshots(s2, snapshot(d, t.cache), True)
    t.driver_control("inventory_replace_by_rename", any(x[0] == "replaced" for x in v), v)
    s3 = snapshot(d, t.cache)
    os.unlink(os.path.join(d, "b.json"))
    v, _ = compare_snapshots(s3, snapshot(d, t.cache), True)
    t.driver_control("inventory_removal", any(x[0] == "removed" for x in v), v)
    # Envelope: a refusal without effects, and one with unordered keys, must fail.
    saved = t.checks
    for label, raw in (("envelope_missing_effects",
                        b'{"schema":"stewart.reply/1","operation":"status","outcome":"refused","reason":"x",'
                        b'"message":"m","retained":[],"next":[]}'),
                       ("envelope_duplicate_key",
                        b'{"schema":"stewart.reply/1","schema":"stewart.reply/1","operation":"status",'
                        b'"outcome":"completed","effects":{},"next":[],"data":{}}'),
                       ("envelope_escaped_duplicate_key",
                        b'{"schema":"stewart.reply/1","operation":"status","outcome":"completed",'
                        b'"effects":{},"\\u006eext":[],"next":[],"data":{}}')):
        t.checks = []
        fake = Reply("status", {"rc": 3 if b"refused" in raw else 0, "stdout": raw, "stdout_len": len(raw),
                                "stdout_sha256": sha256_hex(raw), "stderr": b"", "wall_ms": 0,
                                "timed_out": False}, label)
        t.check_envelope("status", fake, None, label)
        failed = [c["name"] for c in t.checks if not c["ok"]]
        t.checks = saved
        t.driver_control(label, bool(failed), failed)
    # Witness: readback compared with a witness that differs by one byte must fail.
    t.driver_control("witness_one_byte", b"alpha\n" != b"alphb\n", "comparison of differing bytes")
    # Timing gate: a reply delayed by 150 ms must fail the tens-of-milliseconds gate.
    argv = ["/bin/sh", "-c", 'sleep 0.15; exec "$0" "$@"', t.bin["path"], "help"]
    res = Proc(argv, t.env(), t.cwd, 30).wait()
    ok, worst = t.drv.timing_gate_ok([res["wall_ms"]])
    t.driver_control("timing_gate_delay", not ok, {"delayed_ms": res["wall_ms"], "threshold_ms": t.drv.gate_ms})


@case("apparatus.release-ignores-test-env", ["C17"], "the release binary has no fault or sabotage behaviour")
def c_release_ignores(t):
    """With STEWART_TEST_FAULT and STEWART_TEST_SABOTAGE set, the release binary behaves
    exactly as without them: no kill, and commission still needs the affirmation."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    rep = t.prepare(sub, name="release.prepare", fault="prepare.before_prepared_link=kill")
    t.check("release.prepare-not-killed", rep.rc == 0, rep.rc)
    h = sub.handles[-1] if sub.handles else "mp1.aaaaaa"
    t.commission(sub, h, flag=False, name="release.no-flag", expect="refused", reason="affirmation_missing",
                 env={"STEWART_TEST_SABOTAGE": "accept_without_affirmation"})
    rep = t.commission(sub, h, name="release.commission", fault="commission.after_accepted_link=kill")
    t.check("release.commission-not-killed", rep.rc == 0, rep.rc)


# ---------------------------------------------------------------------------
# C11 and C9: help and the scaffold.
# ---------------------------------------------------------------------------

@case("c11.help", ["C11", "C9"], "help lists commands and topics without an archive")
def c_help(t):
    """`stewart help` and each topic exit 0 with text that names what it covers; help
    touches no archive (STEWART_ARCHIVE points at an absent path that stays absent).
    Timings feed the C9 gate."""
    absent = os.path.join(t.root, "no archive here")
    env = {"STEWART_ARCHIVE": absent}
    outs = {}
    for topic in (None, "commands", "forms", "limits", "reader", "close"):
        args = ["help"] + ([topic] if topic else [])
        r = t.cmd(args, op="help", json_reply=False, envelope=False, name="help-%s" % (topic or "index"), env=env)
        t.eq("help.%s.exit" % (topic or "index"), r.rc, 0)
        t.check("help.%s.text" % (topic or "index"), len(r.stdout.strip()) > 0, "empty help")
        outs[topic] = r.stdout.decode("utf-8", "replace")
    idx = outs[None]
    for c in COMMANDS:
        t.check("help.index.lists.%s" % c, re.search(r"(?<![A-Za-z_-])%s(?![A-Za-z_])" % c, idx), "help does not list %s" % c)
    cm = outs["commands"]
    for word in ("question.md", "materials", "--i-am-finished", "prepare", "commission"):
        t.check("help.commands.mentions.%s" % word, word in cm, word)
    t.check("help.commands.finish-before-prepare", re.search(r"finish", cm, re.I) and re.search(r"unchanged|leave", cm, re.I),
            "help commands should explain finishing edits and leaving the folder unchanged")
    fm = norm_ws(outs["forms"])
    for fam, text in FAMILY_TEXT.items():
        t.check("help.forms.%s" % fam, fam in outs["forms"], fam)
        t.check("help.forms.%s.instructions" % fam, norm_ws(text) in fm, "family instructions not printed exactly")
        for tool in FAMILY_TOOLS[fam]:
            t.check("help.forms.%s.%s" % (fam, tool), tool in outs["forms"], tool)
    lim = outs["limits"].replace(",", "")
    for key, alts in (("question", ("262144", "256 KiB")), ("files", ("128",)), ("file", ("16777216", "16 MiB")),
                      ("total", ("134217728", "128 MiB")), ("directories", ("256",)), ("path", ("1024",)),
                      ("components", ("32",)), ("component", ("255",))):
        t.check("help.limits.%s" % key, any(a in lim for a in alts), alts)
    t.check("help.reader", "utf8-text/1" in outs["reader"], "reader id")
    for word in ("--confirm", "--destination", "--surrender"):
        t.check("help.close.%s" % word, word in outs["close"], word)
    t.check("help.no-archive", not os.path.lexists(absent), "help created %s" % absent)


@case("c11.scaffold", ["C11", "C18", "C20"], "new creates the archive and the documented scaffold")
def c_scaffold(t):
    """new on an absent folder and absent archive (existing parents) creates both; the
    scaffold is the documented front matter with placeholders, an empty body and an
    empty materials/. Prepare refuses each placeholder and the empty body."""
    archive = t.archive_path()
    folder = t.folder_path()
    dest = t.dest_path()
    t.watch(archive, "archive", "archive")
    rep = t.cmd(["new", folder, "--archive", archive], name="scaffold.new", expect="completed")
    sub = Sub(t, folder, dest, archive, b"", [], [], "open-inquiry", "claude-opus-5-5", (200, 20000000, 400000))
    if rep.outcome == "completed":
        t.check_new_reply(rep, sub, "scaffold.new", True, t.bin["path"])
        t.eq("scaffold.archive_created", rep.data.get("archive_created"), True)
    t.require("scaffold.folder", os.path.isdir(folder), "folder not created")
    t.watch(folder, "frozen", "folder")
    q = read_bytes(os.path.join(folder, "question.md"))
    lines = q.split(b"\n")
    t.check("scaffold.starts", q.startswith(b"---\n"), q[:20])
    t.check("scaffold.empty-body", q.endswith(b"\n---\n"), q[-20:])
    pos = [lines.index(f) if f in lines else -1 for f in SCAFFOLD_FIELDS]
    t.check("scaffold.fields", all(p > 0 for p in pos) and pos == sorted(pos), dict(zip([f.decode() for f in SCAFFOLD_FIELDS], pos)))
    for c in SCAFFOLD_COMMENTS:
        t.check("scaffold.comment", c in lines, c.decode())
    t.check("scaffold.split", split_question(q) == b"", "body is not empty")
    t.eq("scaffold.materials-empty", sorted(os.listdir(os.path.join(folder, "materials"))), [])
    t.eq("scaffold.folder-entries", sorted(os.listdir(folder)), ["materials", "question.md"])
    if sub.ref is None:
        return
    t.prepare(sub, name="scaffold.untouched", expect="refused", reason=("setting_invalid", "question_empty"))
    body = b"Is the reminder sent twice?\n"
    t.edit(os.path.join(folder, "question.md"), q.replace(b"REPLACE-WITH-ABSOLUTE-DIRECTORY", dest.encode()) + body)
    t.prepare(sub, name="scaffold.model-placeholder", expect="refused", reason="setting_invalid")
    t.edit(os.path.join(folder, "question.md"), q.replace(b"REPLACE-WITH-MODEL", b"claude-opus-5-5") + body)
    t.prepare(sub, name="scaffold.destination-placeholder", expect="refused", reason="setting_invalid")
    filled = q.replace(b"REPLACE-WITH-MODEL", b"claude-opus-5-5").replace(b"REPLACE-WITH-ABSOLUTE-DIRECTORY", dest.encode())
    t.edit(os.path.join(folder, "question.md"), filled)
    t.prepare(sub, name="scaffold.empty-body", expect="refused", reason="question_empty")
    t.edit(os.path.join(folder, "question.md"), filled + body)
    rep = t.prepare(sub, name="scaffold.filled", expect="completed")


# ---------------------------------------------------------------------------
# C11 and C17: commissioning.
# ---------------------------------------------------------------------------

@case("c11.affirmation", ["C11", "C20"], "commission without --i-am-finished accepts nothing",
      controls=[Control("accept_without_affirmation", [r"^affirmation\."])])
def c_affirmation(t):
    """Without the affirmation commission refuses affirmation_missing with acceptance
    absent and attempt none, publishes no log record and captures nothing; misspellings
    are usage errors; the affirmed call then accepts."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    kinds = t.log_kinds(sub)
    rep = t.commission(sub, h, flag=False, name="affirmation", expect="refused", reason="affirmation_missing")
    t.eq("affirmation.effects", no_diag(rep.effects), {"acceptance": "absent", "attempt": "none"})
    t.eq("affirmation.log-unchanged", t.log_kinds(sub), kinds)
    t.eq("affirmation.no-intake", t.intake_dirs(sub), [])
    st = t.status(sub, name="affirmation-status")
    t.check_status(st, sub, "affirmation.status", condition="preparing", accepted="no",
                   next_cmds=("prepare", "commission", "close"), handle=h)
    for label, flag in (("abbreviated", "--i-am-finish"), ("valued", "--i-am-finished=yes"),
                        ("uppercase", "--I-AM-FINISHED")):
        r = t.cmd(["commission", sub.ref, h, flag], op="usage", envelope=False, name="affirmation-%s" % label)
        t.eq("affirmation.usage.%s" % label, r.rc, 2)
    t.eq("affirmation.still-no-intake", t.intake_dirs(sub), [])
    t.commission(sub, h, name="affirmed")


@case("c11.changed-selection", ["C11", "C17", "C2"],
      "T2: a changed selection refuses; fresh preparation commissions the revision",
      controls=[Control("accept_changed_source", [r"^changed\."])])
def c_changed(t):
    """After prepare, a content edit, a same-size edit with mtime restored (visible only to
    the digest comparison), an added file, a removed file and an added directory each
    make commission refuse selection_changed with effects {absent, partial}, the names
    listed, intake_ended selection_changed and next prepare/close. A fresh preparation
    then commissions exactly the revised selection under the same reference."""
    sub = t.submission([F("a.txt", b"alpha\n"), F("b.txt", b"bravo\n"), F("c.txt", b"charlie\n")])
    t.new_ref(sub)
    steps = [
        ("content", lambda: set_file(t, sub, "a.txt", b"alpha changed\n"), {"changed": ["materials/a.txt"]}),
        ("stealth", lambda: stealth_edit(t, sub, "a.txt", b"alphA changed\n"), {"changed": ["materials/a.txt"]}),
        ("added", lambda: set_file(t, sub, "new.txt", b"new file\n"), {"added": ["materials/new.txt"]}),
        ("removed", lambda: remove_file(t, sub, "b.txt"), {"removed": ["materials/b.txt"]}),
        ("added-dir", lambda: add_dir(t, sub, "newdir"), {"added": ["materials/newdir"]}),
    ]
    for label, change, lists in steps:
        t.prepare(sub, name="prepare-before-%s" % label)
        h = sub.handles[-1]
        change()
        rep = t.commission(sub, h, name="changed.%s" % label, expect="refused", reason="selection_changed")
        p = "changed.%s" % label
        t.eq(p + ".effects", no_diag(rep.effects), {"acceptance": "absent", "attempt": "partial"})
        for key in ("added", "removed", "changed"):
            t.eq("%s.%s" % (p, key), rep.data.get(key), lists.get(key, []))
        kinds = t.log_kinds(sub)
        t.eq(p + ".log", kinds[-2:], ["intake_planned", "intake_ended"])
        bodies = t.log_bodies(sub, "intake_ended")
        t.check(p + ".intake-ended-outcome", bodies and isinstance(bodies[-1], dict) and bodies[-1].get("outcome") == "selection_changed",
                bodies[-1:] if bodies else None)
        ret = (rep.obj or {}).get("retained") or []
        t.check(p + ".retained-attempt", any(re.search(r"/intake/[^/]+$", x) and x.startswith(sub.audit_dir) for x in ret), ret)
        argvs = rep.next_argvs()
        t.check(p + ".next-prepare", [sub.writer, "prepare", sub.ref] in argvs, rep.next)
        t.check(p + ".next-close", [sub.writer, "close", sub.ref] in argvs, rep.next)
        st = t.status(sub, name="status-after-%s" % label)
        t.check_status(st, sub, p + ".status", condition="intake_failed", accepted="no",
                       next_cmds=("prepare", "commission", "close"))
    rep = t.prepare(sub, name="changed.final-prepare")
    if rep.outcome == "completed":
        t.check_prepare_witness(rep, sub, "changed.final-prepare")
    t.commission(sub, sub.handles[-1], name="changed.final-commission")
    for item, exp in sub.items().items():
        t.check_readback_ok(sub, item, exp, "changed.readback")


@case("c11.compose", ["C11", "C15", "C20"], "prepare and commission compose; repeats return the recorded acceptance")
def c_compose(t):
    """Commission runs from prepare's own next argv with no pause. Repeating the accepted
    handle returns the recorded acceptance (same receipt digest and time) without new
    records; another handle and a later prepare refuse reference_already_accepted; source
    edits after acceptance change no readback."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub, name="compose.prepare-1")
    t.prepare(sub, name="compose.prepare-2")
    h1, h2 = sub.handles[0], sub.handles[-1]
    t.check("compose.distinct-handles", h1 != h2, sub.handles)
    prep = [a for a in t.cmd(["status", sub.ref], name="status-prepared").next_argvs() if a[1] == "commission"]
    t.check("compose.status-offers-commission", bool(prep), "status offers no commission argv")
    argv = sub.prep_next.get(h2)
    t.require("compose.prepare-suggested-commission", argv is not None, "prepare's next has no commission argv")
    rep = t.cmd(argv[1:], name="compose.commission", expect="completed", binary=argv[0])
    first = rep.data
    if rep.outcome == "completed":
        t.check_accepted(rep, sub, h2, "compose.commission", sub.writer)
    kinds, intakes = t.log_kinds(sub), t.intake_dirs(sub)
    rep2 = t.commission(sub, h2, name="compose.repeat", already=True)
    t.eq("compose.repeat.receipt", rep2.data.get("receipt_sha256"), first.get("receipt_sha256"))
    t.eq("compose.repeat.accepted_at", rep2.data.get("accepted_at"), first.get("accepted_at"))
    t.eq("compose.repeat.no-log", t.log_kinds(sub), kinds)
    t.eq("compose.repeat.no-intake", t.intake_dirs(sub), intakes)
    original = sub.items()
    t.edit(mat(sub, "a.txt"), b"edited after acceptance\n")
    t.driver_change("remove materials/b.txt after acceptance", lambda: os.unlink(mat(sub, "b.txt")))
    rep3 = t.commission(sub, h2, name="compose.repeat-after-edit", already=True)
    t.eq("compose.repeat-after-edit.receipt", rep3.data.get("receipt_sha256"), first.get("receipt_sha256"))
    t.commission(sub, h1, name="compose.other-handle", expect="refused", reason="reference_already_accepted")
    t.prepare(sub, name="compose.prepare-after", expect="refused", reason="reference_already_accepted")
    for item, exp in original.items():
        t.check_readback_ok(sub, item, exp, "compose.readback")
    st = t.status(sub, name="compose.status")
    t.check_status(st, sub, "compose.status", condition="not_started", accepted="yes", next_cmds=("run", "close"))


# ---------------------------------------------------------------------------
# C15: readback.
# ---------------------------------------------------------------------------

@case("c15.readback", ["C15", "C2", "C18"], "readback recovers every item without the source, session, HOME or key")
def c_readback(t):
    """After acceptance the source folder is removed. From an unrelated directory, a new
    HOME and no provider key, receipt lists exactly the item IDs with witness sizes and
    digests; each item's own readback argv returns the witness bytes, with the
    qualification on stderr. Status gives the receipt line. A copy of the binary at
    another path reads the same bytes, and its next argv names the recorded writer."""
    sub = t.submission(population_entries(), body=POPULATION_BODY)
    h, _ = t.accept(sub)
    expected = sub.items()
    t.driver_change("remove the source folder", lambda: shutil.rmtree(sub.folder))
    home2, cwd2 = t.fresh_dir("other home"), t.fresh_dir("other cwd")
    env = {"HOME": home2, "ANTHROPIC_API_KEY": None, "STEWART_ARCHIVE": None}
    rep = t.cmd(["receipt", sub.ref], name="readback.receipt", env=env, cwd=cwd2, expect="completed")
    d = rep.data
    items = find_items(d, set(expected))
    t.eq("readback.item-ids", sorted(items), sorted(expected))
    t.check("readback.reference", contains_string(d, sub.ref), "receipt lacks the reference")
    t.check("readback.handle", contains_string(d, h), "receipt lacks the accepted handle")
    t.check("readback.declaration", any(v == {"i_am_finished": True} for v in iter_values(d)), "declaration")
    t.check("readback.checks", any(v == COMMISSION_CHECKS for v in iter_values(d)), "matched checks")
    t.check("readback.run_line", any(v == [sub.writer, "run", sub.ref] for v in iter_values(d)), "run line")
    t.check("readback.run_needs", isinstance(d.get("run_needs"), list) and d.get("run_needs"), d.get("run_needs"))
    for sha in (sha256_hex(sub.question), sha256_hex(sub.body)):
        t.check("readback.question-digests", contains_string(d, sha), sha)
    for item, exp in expected.items():
        it = items.get(item, {})
        size = exp["size"] if isinstance(exp, dict) else len(exp)
        sha = exp["sha256"] if isinstance(exp, dict) else sha256_hex(exp)
        t.check("readback.item.size", it.get("size") == size, {"item": item, "got": it.get("size"), "expected": size})
        t.check("readback.item.sha256", it.get("sha256") == sha, {"item": item, "got": it.get("sha256"), "expected": sha})
        t.check("readback.item.not-verified-by-default", item_state(it) != "verified", {"item": item, "entry": it})
        argv = item_argv(it, sub.writer)
        t.check("readback.item.argv", argv is not None and "--read" in argv and item in argv, {"item": item, "entry": it})
        if argv:
            t.check_readback_ok(sub, item, exp, "readback.read", argv=argv, env=env, cwd=cwd2)
    st = t.status(sub, name="readback.status", env=env, cwd=cwd2)
    t.eq("readback.status.receipt_line", st.data.get("receipt_line"), [sub.writer, "receipt", sub.ref])
    other = t.mkdir("other install", "bin dir")
    copy = os.path.join(other, "stewart")
    shutil.copy2(t.bin["path"], copy)
    t.drv.register_alias(copy, t.bin)
    for item in ("question-body", "materials/crlf.txt", "materials/" + "nfd-" + NFD_E + ".txt"):
        t.check_readback_ok(sub, item, expected[item], "readback.copy", binary=copy, env=env, cwd=cwd2)
    st2 = t.status(sub, name="readback.status-from-copy", binary=copy, env=env, cwd=cwd2, writer=sub.writer)
    t.eq("readback.copy.receipt_line", st2.data.get("receipt_line"), [sub.writer, "receipt", sub.ref])


@case("c15.damage", ["C15", "C18"], "damaged, missing, unreadable and planted captures are diagnosed separately",
      controls=[Control("whole_from_one_member", [r"^verify\."])])
def c_damage(t):
    """One flipped bit makes that item item_damaged with no bytes written, while another
    material still verifies. receipt --verify reports each item's own state and never
    the whole commission from one member. A moved-away capture is item_missing, a mode
    000 capture item_unreadable (unprivileged only), a capture replaced by a link to a
    good copy item_unsupported. The default receipt is unchanged throughout."""
    entries = [F("a.txt", b"apple\n"), F("b.txt", b"banana\n"), F("c.txt", b"cherry\n"), F("d.txt", b"date\n"),
               F("e.txt", b"elderberry\n")]
    sub = t.submission(entries)
    t.accept(sub)
    expected = sub.items()
    r0 = t.cmd(["receipt", sub.ref], name="damage.receipt-before", expect="completed").data
    caps = t.capture_paths(sub)
    t.require("damage.captures-located", all(len(caps.get("materials/%s.txt" % x, [])) == 1 for x in "abcde"), caps)

    def verify(label, states):
        rep = t.cmd(["receipt", sub.ref, "--verify"], name="verify-%s" % label, expect="completed")
        items = find_items(rep.data, set(expected))
        got = {k: item_state(v) for k, v in items.items()}
        for item in expected:
            want = states.get(item, "verified")
            t.check("verify.%s.%s" % (label, "own-state" if item in states else "others-verified"), got.get(item) == want,
                    {"item": item, "expected": want, "got": got.get(item)})
        r = t.cmd(["receipt", sub.ref], name="receipt-after-%s" % label, expect="completed")
        t.eq("damage.%s.receipt-unchanged" % label, r.data, r0)

    verify("intact", {})
    t.flip_bit(caps["materials/a.txt"][0])
    t.check_readback_refused(sub, "materials/a.txt", "item_damaged", "damage.read-damaged")
    t.check_readback_ok(sub, "materials/e.txt", expected["materials/e.txt"], "damage.read-other")
    verify("damaged", {"materials/a.txt": "damaged"})
    quarantine = t.mkdir("quarantine")
    t.driver_change("move a capture out of the archive",
                    lambda: shutil.move(caps["materials/b.txt"][0], os.path.join(quarantine, "b.bin")))
    t.check_readback_refused(sub, "materials/b.txt", "item_missing", "damage.read-missing")
    states = {"materials/a.txt": "damaged", "materials/b.txt": "missing"}
    verify("missing", states)
    if os.geteuid() != 0:
        p = caps["materials/c.txt"][0]
        t.mode_exempt.add(p)
        t.driver_change("chmod 000 a capture", lambda: os.chmod(p, 0))
        t.cleanup(lambda: os.chmod(p, 0o600))
        t.check_readback_refused(sub, "materials/c.txt", "item_unreadable", "damage.read-unreadable")
        states["materials/c.txt"] = "unreadable"
        verify("unreadable", states)
    else:
        t.skip_part("unreadable capture", "running as root: permissions do not stop reads")
    p = caps["materials/d.txt"][0]
    good = os.path.join(quarantine, "d-good.bin")
    shutil.copy2(p, good)

    def plant():
        os.unlink(p)
        os.symlink(good, p)
    t.mode_exempt.add(p)
    t.driver_change("replace a capture with a link to an identical copy", plant)
    t.check_readback_refused(sub, "materials/d.txt", ("item_unsupported", "item_unreadable"), "damage.read-link")
    rep = t.cmd(["receipt", sub.ref, "--verify"], name="verify-link", expect="completed")
    st = item_state(find_items(rep.data, set(expected)).get("materials/d.txt", {}))
    t.check("verify.link.own-state", st in ("unsupported", "unreadable"), st)


@case("c15.arrangement-damage", ["C15", "C19"], "readback returns pinned arrangement bytes or diagnoses damage",
      controls=[Control("regenerate_arrangement", [r"^arrangement-damage\."])])
def c_arrangement_damage(t):
    """The arrangement items read back exactly the bytes pinned at prepare. After one bit
    of arrangement.json is flipped, readback of `arrangement` writes no bytes and reports
    item_damaged (a regenerated arrangement would verify), while
    `arrangement-readable` still verifies."""
    sub = t.submission(basic_entries())
    h, _ = t.accept(sub)
    exp = sub.items()
    t.check_readback_ok(sub, "arrangement", exp["arrangement"], "arrangement-damage.intact")
    t.check_readback_ok(sub, "arrangement-readable", exp["arrangement-readable"], "arrangement-damage.readable-intact")
    machine = (sub.prep.get(h, {}).get("arrangement") or {}).get("machine")
    t.require("arrangement-damage.located", isinstance(machine, str) and os.path.isfile(machine), machine)
    t.flip_bit(machine, 10)
    t.check_readback_refused(sub, "arrangement", "item_damaged", "arrangement-damage.read")
    t.check_readback_ok(sub, "arrangement-readable", exp["arrangement-readable"], "arrangement-damage.readable")
    rep = t.cmd(["receipt", sub.ref, "--verify"], name="arrangement-damage.verify", expect="completed")
    items = find_items(rep.data, set(exp))
    t.eq("arrangement-damage.verify-state", item_state(items.get("arrangement", {})), "damaged")


@case("c15.live-source", ["C15", "C2"], "readback never consults the live folder",
      controls=[Control("readback_live_source", [r"^live-source\."])])
def c_live_source(t):
    """After acceptance a material is rewritten and another removed in the folder;
    readback still returns the accepted bytes for both."""
    sub = t.submission(basic_entries())
    t.accept(sub)
    exp = sub.items()
    t.edit(mat(sub, "a.txt"), b"rewritten after acceptance, longer than before\n")
    t.driver_change("remove materials/b.txt", lambda: os.unlink(mat(sub, "b.txt")))
    t.edit(os.path.join(sub.folder, "question.md"), sub.question + b"appended later\n")
    for item in ("materials/a.txt", "materials/b.txt", "question-file", "question-body", "materials/src/c.py"):
        t.check_readback_ok(sub, item, exp[item], "live-source")


@case("c15.items-exact", ["C15", "C20", "C19"], "item names are exact; near misses are item_unknown")
def c_items_exact(t):
    """Near-miss item names (case, ./ and // components, leading or trailing slash,
    missing prefix, other normalization form) are refused item_unknown without bytes."""
    sub = t.submission([F("a.txt", b"alpha\n"), F("caf" + NFD_E + ".txt", b"nfd\n")])
    t.accept(sub)
    nfc = "materials/caf" + unicodedata.normalize("NFC", NFD_E) + ".txt"
    for item in ("materials/A.txt", "materials/./a.txt", "materials//a.txt", "/materials/a.txt",
                 "materials/a.txt/", "a.txt", "question", "Question-file", "arrangement.json",
                 "materials/../materials/a.txt", nfc, "materials/a.txt\n"):
        t.check_readback_refused(sub, item, "item_unknown", "items-exact")
    t.check_readback_ok(sub, "materials/caf" + NFD_E + ".txt", b"nfd\n", "items-exact.nfd")


@case("c15.not-accepted", ["C15", "C16"], "receipt before acceptance refuses not_accepted")
def c_not_accepted(t):
    """Before acceptance receipt refuses not_accepted (an incomplete commission is never
    called accepted), and raw readback writes no bytes; both are read-only."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.cmd(["receipt", sub.ref], name="not-accepted.receipt", expect="refused", reason="not_accepted")
    t.check_readback_refused(sub, "materials/a.txt", ("not_accepted", "item_unknown", "item_missing"), "not-accepted.read")
    t.prepare(sub)
    t.cmd(["receipt", sub.ref], name="not-accepted.receipt-prepared", expect="refused", reason="not_accepted")
    r = t.cmd(["receipt", sub.ref, "--verify"], name="not-accepted.verify", expect="refused", reason="not_accepted")


# ---------------------------------------------------------------------------
# C16: status before launch.
# ---------------------------------------------------------------------------

@case("c16.prelaunch", ["C16", "C11"], "status names each pre-launch condition with evidence and next calls")
def c_prelaunch(t):
    """preparing (with and without a preparation), intake_failed and not_started, each
    with its headline, evidence list and next calls. Status is read-only, and a later
    status after time passes reports the same facts. The human presentation exits as
    the JSON one does."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    st = t.status(sub, name="prelaunch.new")
    t.check_status(st, sub, "prelaunch.new", condition="preparing", accepted="no", next_cmds=("prepare", "close"))
    t.prepare(sub)
    h = sub.handles[-1]
    st = t.status(sub, name="prelaunch.prepared")
    t.check_status(st, sub, "prelaunch.prepared", condition="preparing", accepted="no",
                   next_cmds=("prepare", "commission", "close"), handle=h)
    set_file(t, sub, "a.txt", b"changed\n")
    t.commission(sub, h, name="prelaunch.changed", expect="refused", reason="selection_changed")
    st = t.status(sub, name="prelaunch.failed-intake")
    t.check_status(st, sub, "prelaunch.failed-intake", condition="intake_failed", accepted="no",
                   next_cmds=("prepare", "commission", "close"))
    t.prepare(sub)
    t.commission(sub, sub.handles[-1], name="prelaunch.commission")
    st = t.status(sub, name="prelaunch.accepted")
    t.check_status(st, sub, "prelaunch.accepted", condition="not_started", accepted="yes", next_cmds=("run", "close"))
    time.sleep(1.2)
    st2 = t.status(sub, name="prelaunch.accepted-later")
    t.eq("prelaunch.elapsed-time-invariant", st2.data, st.data)
    hum = t.cmd(["status", sub.ref], json_reply=False, envelope=False, name="prelaunch.human")
    t.eq("prelaunch.human.exit", hum.rc, 0)
    t.check("prelaunch.human.text", hum.stdout.strip() and not hum.stdout.lstrip().startswith(b"{"), hum.stdout[:200])
    t.check("prelaunch.human.mentions-receipt", b"receipt" in hum.stdout, "human status lacks the readback route")


@case("c16.intake-in-progress", ["C16", "C17"], "a live intake holds the lock: status and a second commission see it",
      mode="test", needs=("lock",), linux_reason="OFD lock behaviour (F_OFD_SETLK/GETLK) is a Linux-only expectation")
def c_intake_in_progress(t):
    """With commission paused after its first capture, status reports intake_in_progress
    (next status/close) and a second commission refuses intake_in_progress with no
    effect; once released the first commission completes."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    bg = t.start(["commission", sub.ref, h, "--i-am-finished"], name="paused-commission",
                 fault="commission.after_capture:1=pause")
    stem = t.wait_paused("commission.after_capture", bg)
    st = t.status(sub, name="in-progress.status")
    t.check_status(st, sub, "in-progress.status", condition="intake_in_progress", accepted="no",
                   next_cmds=("status", "close"))
    rep = t.commission(sub, h, name="in-progress.second", expect="refused", reason="intake_in_progress")
    t.eq("in-progress.second.effects", no_diag(rep.effects), {"acceptance": "absent", "attempt": "none"})
    t.release(stem)
    rep = t.finish(bg, expect="completed")
    if rep.outcome == "completed":
        t.check_accepted(rep, sub, h, "in-progress.first", sub.writer)
    st = t.status(sub, name="in-progress.after")
    t.check_status(st, sub, "in-progress.after", condition="not_started", accepted="yes", next_cmds=("run", "close"))


@case("c16.log-damaged", ["C16", "C17", "C20"], "damage after acceptance: log_damaged, mutations refuse, receipt reads")
def c_log_damaged(t):
    """A non-record file at the next log number makes the log damaged after a readable
    accepted record: status log_damaged naming it, prepare and commission refuse
    log_damaged (acceptance unknown), close stays unfinished publishing nothing, and
    the receipt still reads back the witness."""
    sub = t.submission(basic_entries())
    h, _ = t.accept(sub)
    n = len(t.log_kinds(sub))
    bad = os.path.join(sub.audit_dir, "log", "%d.json" % (n + 1))
    t.tampered_logs.add(sub.audit)
    def torn():
        with open(bad, "wb") as f:
            f.write(b'{"record":"stewart.rec')
    t.driver_change("write a torn log record", torn)
    t.mode_exempt.add(bad)
    st = t.status(sub, name="damaged.status")
    t.check_status(st, sub, "damaged.status", condition="log_damaged", accepted="yes", next_cmds=("receipt",))
    t.check("damaged.status.names-record", mentions(st.data.get("diagnostics"), "%d.json" % (n + 1)), st.data.get("diagnostics"))
    t.prepare(sub, name="damaged.prepare", expect="refused", reason="log_damaged")
    rep = t.commission(sub, h, name="damaged.commission", expect="refused", reason="log_damaged")
    t.eq("damaged.commission.acceptance", rep.effects.get("acceptance"), "unknown")
    names = sorted(os.listdir(os.path.join(sub.audit_dir, "log")))
    rep = t.cmd(["close", sub.ref], name="damaged.close", expect="completed")
    t.eq("damaged.close.closure", rep.data.get("closure"), "unfinished")
    t.eq("damaged.close.reason", rep.data.get("unfinished_reason"), "log_damaged")
    t.eq("damaged.close.published-nothing", sorted(os.listdir(os.path.join(sub.audit_dir, "log"))), names)
    t.cmd(["receipt", sub.ref], name="damaged.receipt", expect="completed")
    for item in ("question-body", "materials/a.txt"):
        t.check_readback_ok(sub, item, sub.items()[item], "damaged.readback")


# ---------------------------------------------------------------------------
# C17: controlled failures (Appendix C.1).
# ---------------------------------------------------------------------------

@case("c17.t1-lost-commission-reply", ["C17", "C20", "C15"],
      "T1: commission killed after acceptance; the repeat returns the recorded receipt", mode="test")
def c_t1(t):
    """commission.after_accepted_link=kill leaves no reply after accepted is linked. After
    the manager edits materials/a.txt, commission with the same handle returns
    already_accepted with the recorded receipt digest, plans no new intake, and
    readback still returns the original bytes."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    r = t.cmd(["commission", sub.ref, h, "--i-am-finished"], name="t1.killed", envelope=False,
              fault="commission.after_accepted_link=kill")
    t.eq("t1.killed.signal", r.rc, -signal.SIGKILL)
    t.eq("t1.killed.no-reply", r.stdout, b"")
    t.eq("t1.log", t.log_kinds(sub), ["reference", "prepared", "intake_planned", "accepted"])
    original = sub.items()
    st = t.status(sub, name="t1.status")
    t.check_status(st, sub, "t1.status", condition="not_started", accepted="yes", next_cmds=("run", "close"))
    t.edit(mat(sub, "a.txt"), b"alpha edited after the lost reply\n")
    kinds, intakes = t.log_kinds(sub), t.intake_dirs(sub)
    t.commission(sub, h, name="t1.repeat", already=True)
    t.eq("t1.repeat.no-new-log", t.log_kinds(sub), kinds)
    t.eq("t1.repeat.no-new-intake", t.intake_dirs(sub), intakes)
    for item in ("materials/a.txt", "question-file"):
        t.check_readback_ok(sub, item, original[item], "t1.readback")


@case("c17.reply-write-failure", ["C17", "C20"], "a commission reply that cannot be written; the repeat recovers it",
      mode="test")
def c_reply_write(t):
    """reply.write=epipe on a successful commission: no usable reply, acceptance stands;
    status reports it and the repeat returns the recorded acceptance without a new
    capture."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    r = t.cmd(["commission", sub.ref, h, "--i-am-finished"], name="reply-lost.commission", envelope=False,
              fault="reply.write=epipe")
    usable = False
    try:
        usable = isinstance(strict_loads(r.stdout.rstrip(b"\n")), dict)
    except StrictJSONError:
        pass
    t.check("reply-lost.no-usable-reply", not usable, r.stdout[:200])
    t.check("reply-lost.not-success-exit", r.rc != 0, r.rc)
    st = t.status(sub, name="reply-lost.status")
    t.check_status(st, sub, "reply-lost.status", condition="not_started", accepted="yes", next_cmds=("run", "close"))
    intakes = t.intake_dirs(sub)
    t.commission(sub, h, name="reply-lost.repeat", already=True)
    t.eq("reply-lost.no-new-intake", t.intake_dirs(sub), intakes)


@case("c17.t3-intake-killed", ["C17", "C6", "C16"], "T3: intake killed mid-copy; status and the next commission reconcile",
      mode="test", controls=[Control("remove_partial_on_retry", [r"^inventory\.", r"^t3\.attempt1"])])
def c_t3(t):
    """commission.after_capture:2=kill. Status reports intake_failed with the exact T3
    evidence. The next commission publishes intake_ended process_gone, plans attempt 2
    with fresh capture names and accepts; attempt 1's files remain unchanged."""
    sub = t.submission([F("a.txt", b"alpha\n"), F("b.txt", b"bravo\n"), F("c.txt", b"charlie\n")])
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    r = t.cmd(["commission", sub.ref, h, "--i-am-finished"], name="t3.killed", envelope=False,
              fault="commission.after_capture:2=kill")
    t.eq("t3.killed.signal", r.rc, -signal.SIGKILL)
    atts = t.intake_dirs(sub)
    t.require("t3.one-attempt", len(atts) == 1, atts)
    d1 = os.path.join(sub.audit_dir, "intake", atts[0])
    files1 = {n: sha256_file(os.path.join(d1, n)) for n in sorted(os.listdir(d1))}
    t.eq("t3.two-captures", len([n for n in files1 if n.endswith(".bin")]), 2)
    st = t.status(sub, name="t3.status")
    t.check_status(st, sub, "t3.status", condition="intake_failed", accepted="no",
                   next_cmds=("prepare", "commission", "close"))
    t.check("t3.status.evidence", T3_EVIDENCE in (st.data.get("evidence") or []), st.data.get("evidence"))
    t.commission(sub, h, name="t3.retry")
    kinds = t.log_kinds(sub)
    t.eq("t3.log", kinds, ["reference", "prepared", "intake_planned", "intake_ended", "intake_planned", "accepted"])
    bodies = t.log_bodies(sub, "intake_ended")
    t.check("t3.process-gone", bodies and isinstance(bodies[0], dict) and bodies[0].get("outcome") == "process_gone", bodies)
    atts2 = t.intake_dirs(sub)
    t.eq("t3.two-attempts", len(atts2), 2)
    t.check("t3.attempt1-kept", os.path.isdir(d1) and {n: sha256_file(os.path.join(d1, n)) for n in sorted(os.listdir(d1))} == files1,
            "attempt 1 changed")
    for item, exp in sub.items().items():
        t.check_readback_ok(sub, item, exp, "t3.readback")


@case("c17.t4-uncertain-acceptance", ["C17", "C16", "C20"],
      "T4: a failed log sync after linking accepted is reported as uncertain, then reconciled", mode="test")
def c_t4(t):
    """commission.accepted_dirsync=eio: failed acceptance_record_uncertain, acceptance
    unknown, attempt recorded, diagnostic durable, retained intake and diagnostic, an
    EIO cause, next status and the same commission. Status then reads accepted: yes and
    the repeat returns the recorded acceptance without a fresh capture."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    rep = t.commission(sub, h, name="t4.uncertain", expect="failed", reason="acceptance_record_uncertain",
                       fault="commission.accepted_dirsync=eio")
    t.eq("t4.effects", rep.effects, {"acceptance": "unknown", "attempt": "recorded", "diagnostic": "durable"})
    ret = (rep.obj or {}).get("retained") or []
    t.check("t4.retained-intake", any(x.startswith(sub.audit_dir + "/intake/") for x in ret), ret)
    t.check("t4.retained-diagnostic", any(x.startswith(sub.audit_dir + "/diag/") for x in ret), ret)
    causes = (rep.obj or {}).get("causes") or [{}]
    t.eq("t4.cause-error", causes[0].get("error") if isinstance(causes[0], dict) else None, "EIO")
    argvs = rep.next_argvs()
    t.check("t4.next-status", [sub.writer, "status", sub.ref] in argvs, rep.next)
    t.check("t4.next-same-commission", [sub.writer, "commission", sub.ref, h, "--i-am-finished"] in argvs, rep.next)
    st = t.status(sub, name="t4.status")
    t.check_status(st, sub, "t4.status", condition="not_started", accepted="yes", next_cmds=("run", "close"))
    intakes = t.intake_dirs(sub)
    t.commission(sub, h, name="t4.repeat", already=True)
    t.eq("t4.no-fresh-capture", t.intake_dirs(sub), intakes)


@case("c17.acceptance-uncertain", ["C17", "C16", "C20", "C8"],
      "T4: a log damaged before any readable accepted is acceptance_uncertain, never absent",
      controls=[Control("unknown_as_absent", [r"^uncertain\."])])
def c_acceptance_uncertain(t):
    """The accepted record is torn. Status reports acceptance_uncertain with accepted
    unknown, naming the bad record; commission refuses log_damaged with acceptance
    unknown and offers no fresh capture; prepare refuses log_damaged; close stays
    unfinished (log_damaged) and publishes nothing."""
    sub = t.submission(basic_entries())
    h, _ = t.accept(sub)
    recs = t.read_log(sub)
    idx = [i for i, r in enumerate(recs) if (r["obj"] or {}).get("kind") == "accepted"]
    t.require("uncertain.accepted-located", len(idx) == 1, [r["name"] for r in recs])
    rec = recs[idx[0]]
    path = os.path.join(sub.audit_dir, "log", rec["name"])
    t.tampered_logs.add(sub.audit)
    t.driver_change("tear the accepted record", lambda: os.truncate(path, len(rec["raw"]) // 2))
    st = t.status(sub, name="uncertain.status")
    t.check_status(st, sub, "uncertain.status", condition="acceptance_uncertain", accepted="unknown",
                   next_cmds=("status",))
    t.check("uncertain.status.names-record", mentions(st.data.get("diagnostics"), rec["name"]), st.data.get("diagnostics"))
    intakes = t.intake_dirs(sub)
    rep = t.commission(sub, h, name="uncertain.commission", expect="refused", reason="log_damaged")
    t.eq("uncertain.commission.acceptance", rep.effects.get("acceptance"), "unknown")
    t.check("uncertain.commission.no-fresh-capture-offer",
            not any(a[1] == "commission" for a in rep.next_argvs()), rep.next)
    t.eq("uncertain.no-new-intake", t.intake_dirs(sub), intakes)
    t.prepare(sub, name="uncertain.prepare", expect="refused", reason="log_damaged")
    names = sorted(os.listdir(os.path.join(sub.audit_dir, "log")))
    rep = t.cmd(["close", sub.ref], name="uncertain.close", expect="completed")
    t.eq("uncertain.close.closure", rep.data.get("closure"), "unfinished")
    t.eq("uncertain.close.reason", rep.data.get("unfinished_reason"), "log_damaged")
    t.eq("uncertain.close.published-nothing", sorted(os.listdir(os.path.join(sub.audit_dir, "log"))), names)


@case("c17.t11-diagnostic-write", ["C17", "C20"], "T11: a failed diagnostic write keeps the original cause first",
      mode="test")
def c_t11(t):
    """diag.write=eio with a selection_changed refusal: the reason stays
    selection_changed, effects.diagnostic is reported_only, causes are [original,
    diagnostic write], and no diagnostic file appears."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    set_file(t, sub, "a.txt", b"alpha changed\n")
    diag = os.path.join(sub.audit_dir, "diag")
    before = sorted(os.listdir(diag)) if os.path.isdir(diag) else []
    rep = t.commission(sub, h, name="t11", expect="refused", reason="selection_changed", fault="diag.write=eio")
    t.eq("t11.diagnostic", rep.effects.get("diagnostic"), "reported_only")
    causes = (rep.obj or {}).get("causes") or []
    t.check("t11.two-causes", len(causes) >= 2, causes)
    if causes:
        t.check("t11.original-first", "EIO" not in json.dumps(causes[0]), causes)
        t.check("t11.diagnostic-write-last", "EIO" in json.dumps(causes[-1]), causes)
    after = sorted(os.listdir(diag)) if os.path.isdir(diag) else []
    t.eq("t11.no-diagnostic-file", after, before)


@case("c17.t11-unwritable-diag", ["C17"], "T11 with diag/ made unwritable", needs=("nonroot",))
def c_t11_chmod(t):
    """With the diag/ directory mode 0500 (unprivileged run), a refused commission still
    replies with both causes and diagnostic reported_only."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    t.commission(sub, h, flag=False, name="t11u.first-refusal", expect="refused", reason="affirmation_missing")
    diag = os.path.join(sub.audit_dir, "diag")
    if not os.path.isdir(diag):
        t.skip("diag/ does not exist after a refusal, so it cannot be made unwritable without creating it")
    t.mode_exempt.add(diag)
    t.driver_change("chmod 0500 diag/", lambda: os.chmod(diag, 0o500))
    t.cleanup(lambda: os.chmod(diag, 0o700))
    set_file(t, sub, "a.txt", b"alpha changed\n")
    rep = t.commission(sub, h, name="t11u", expect="refused", reason="selection_changed")
    t.eq("t11u.diagnostic", rep.effects.get("diagnostic"), "reported_only")
    t.check("t11u.two-causes", len((rep.obj or {}).get("causes") or []) >= 2, (rep.obj or {}).get("causes"))


@case("c17.source-unreadable", ["C17", "C6"], "a source read failure refuses with context; retry keeps attempt 1",
      mode="test", controls=[Control("remove_partial_on_retry", [r"^inventory\.", r"^unreadable\.attempt1"])])
def c_source_unreadable(t):
    """commission.source_read:<name>=eio refuses source_unreadable naming the file and the
    error, publishes intake_ended source_unreadable and retains the attempt. Without the
    fault the same handle commissions; attempt 1 stays."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    fault = "commission.source_read:b.txt=eio,commission.source_read:materials/b.txt=eio"
    rep = t.commission(sub, h, name="unreadable", expect="refused", reason="source_unreadable", fault=fault)
    t.eq("unreadable.effects", no_diag(rep.effects), {"acceptance": "absent", "attempt": "partial"})
    text = json.dumps(rep.obj, ensure_ascii=False) if rep.obj else ""
    t.check("unreadable.names-file", "b.txt" in text, text[:400])
    t.check("unreadable.names-error", "EIO" in text, text[:400])
    bodies = t.log_bodies(sub, "intake_ended")
    t.check("unreadable.intake-ended", bodies and bodies[-1].get("outcome") == "source_unreadable", bodies)
    ret = (rep.obj or {}).get("retained") or []
    t.check("unreadable.retained", any(x.startswith(sub.audit_dir + "/intake/") for x in ret), ret)
    atts = t.intake_dirs(sub)
    d1 = os.path.join(sub.audit_dir, "intake", atts[0]) if atts else None
    files1 = {n: sha256_file(os.path.join(d1, n)) for n in sorted(os.listdir(d1))} if d1 else {}
    t.commission(sub, h, name="unreadable.retry")
    t.check("unreadable.attempt1-kept", d1 and os.path.isdir(d1) and
            {n: sha256_file(os.path.join(d1, n)) for n in sorted(os.listdir(d1))} == files1, "attempt 1 changed")


@case("c17.source-permission", ["C17", "C19"], "a permission change: unreadable refuses, restored or readable proceeds",
      needs=("nonroot",))
def c_source_permission(t):
    """After prepare, mode 000 on a material makes commission refuse source_unreadable;
    restoring the mode lets the same handle commission. A permission change that keeps
    every file readable (0444 file, 0555 directory) never manufactures a changed
    selection."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    p = mat(sub, "b.txt")
    t.driver_change("chmod 000 materials/b.txt", lambda: os.chmod(p, 0))
    t.cleanup(lambda: os.chmod(p, 0o644))
    rep = t.commission(sub, h, name="permission.unreadable", expect="refused", reason="source_unreadable")
    t.check("permission.names-file", "b.txt" in json.dumps(rep.obj or {}, ensure_ascii=False), rep.obj)
    t.driver_change("chmod 0444 materials/b.txt", lambda: os.chmod(p, 0o444))
    srcdir = mat(sub, "src")
    t.driver_change("chmod 0555 materials/src", lambda: os.chmod(srcdir, 0o555))
    t.cleanup(lambda: os.chmod(srcdir, 0o755))
    t.commission(sub, h, name="permission.restored")
    for item, exp in sub.items().items():
        t.check_readback_ok(sub, item, exp, "permission.readback")


@case("c17.capture-failures", ["C17", "C6"], "capture, verification and receipt failures each keep their own account",
      mode="test")
def c_capture_failures(t):
    """capture_write eio/enospc fail capture_failed, capture_corrupt fails
    capture_unverified, receipt_write fails receipt_record_failed. Each: acceptance
    absent, a partial attempt, a durable diagnostic, retained locations, a cause with the
    injected error, intake_ended with its own outcome, a next action, and status
    intake_failed. The same handle then commissions; every attempt stays."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    cases_ = [("capture-eio", "commission.capture_write=eio", "capture_failed", "EIO", ("partial",)),
              ("capture-enospc", "commission.capture_write=enospc", "capture_failed", "ENOSPC", ("partial",)),
              ("capture-corrupt", "commission.capture_corrupt=corrupt", "capture_unverified", None, ("partial",)),
              ("receipt-eio", "commission.receipt_write=eio", "receipt_record_failed", "EIO", ("partial", "recorded"))]
    for label, fault, reason, err, attempts in cases_:
        n0 = len(t.intake_dirs(sub))
        rep = t.commission(sub, h, name="failure.%s" % label, expect="failed", reason=reason, fault=fault)
        p = "failure.%s" % label
        t.eq(p + ".acceptance", rep.effects.get("acceptance"), "absent")
        t.check(p + ".attempt", rep.effects.get("attempt") in attempts, rep.effects)
        t.eq(p + ".diagnostic", rep.effects.get("diagnostic"), "durable")
        ret = (rep.obj or {}).get("retained") or []
        t.check(p + ".retained", any(x.startswith(sub.audit_dir + "/intake/") for x in ret)
                and any(x.startswith(sub.audit_dir + "/diag/") for x in ret), ret)
        if err:
            t.check(p + ".cause", err in json.dumps((rep.obj or {}).get("causes")), (rep.obj or {}).get("causes"))
        t.check(p + ".next", bool(rep.next), "a failure must offer a supported next action")
        bodies = t.log_bodies(sub, "intake_ended")
        t.check(p + ".intake-ended", bodies and bodies[-1].get("outcome") == reason, bodies[-1:] if bodies else None)
        t.eq(p + ".new-attempt", len(t.intake_dirs(sub)), n0 + 1)
        st = t.status(sub, name="status-after-%s" % label)
        t.check_status(st, sub, p + ".status", condition="intake_failed", accepted="no",
                       next_cmds=("prepare", "commission", "close"))
    t.commission(sub, h, name="failure.retry")
    t.eq("failure.all-attempts-kept", len(t.intake_dirs(sub)), len(cases_) + 1)
    for item, exp in sub.items().items():
        t.check_readback_ok(sub, item, exp, "failure.readback")


@case("c17.before-accepted-kill", ["C17", "C6"], "killed before accepted is linked: no acceptance; the next attempt accepts",
      mode="test")
def c_before_accepted_kill(t):
    """commission.before_accepted_link=kill: status intake_failed with the T3 evidence
    shape; the unpublished receipt stays; the next commission accepts as attempt 2."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    r = t.cmd(["commission", sub.ref, h, "--i-am-finished"], name="pre-accept.killed", envelope=False,
              fault="commission.before_accepted_link=kill")
    t.eq("pre-accept.signal", r.rc, -signal.SIGKILL)
    t.check("pre-accept.no-accepted", "accepted" not in t.log_kinds(sub), t.log_kinds(sub))
    st = t.status(sub, name="pre-accept.status")
    t.check_status(st, sub, "pre-accept.status", condition="intake_failed", accepted="no",
                   next_cmds=("prepare", "commission", "close"))
    t.check("pre-accept.evidence", T3_EVIDENCE in (st.data.get("evidence") or []), st.data.get("evidence"))
    t.cmd(["receipt", sub.ref], name="pre-accept.receipt", expect="refused", reason="not_accepted")
    t.commission(sub, h, name="pre-accept.retry")
    t.eq("pre-accept.attempts", len(t.intake_dirs(sub)), 2)


@case("c17.prepare-killed", ["C17", "C6"], "prepare killed before its record: an unpublished candidate, never a handle",
      mode="test")
def c_prepare_killed(t):
    """prepare.before_prepared_link=kill: no prepared record; status stays preparing
    without offering a commission; the written preparation files stay; the next prepare
    claims a new number and its handle commissions."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    r = t.cmd(["prepare", sub.ref], name="prep-killed.prepare", envelope=False, fault="prepare.before_prepared_link=kill")
    t.eq("prep-killed.signal", r.rc, -signal.SIGKILL)
    t.eq("prep-killed.log", t.log_kinds(sub), ["reference"])
    prep = os.path.join(sub.audit_dir, "prep")
    left = sorted(os.listdir(prep)) if os.path.isdir(prep) else []
    t.check("prep-killed.files-written", len(left) == 1, left)
    st = t.status(sub, name="prep-killed.status")
    t.check_status(st, sub, "prep-killed.status", condition="preparing", accepted="no", next_cmds=("prepare", "close"))
    t.check("prep-killed.no-commission-offer", not any(a[1] == "commission" for a in st.next_argvs()), st.next)
    t.prepare(sub, name="prep-killed.again")
    t.check("prep-killed.new-number", len(os.listdir(prep)) == 2, os.listdir(prep))
    t.commission(sub, sub.handles[-1], name="prep-killed.commission")


@case("c17.prepare-reply-lost", ["C17", "C16", "C20"], "a lost prepare reply: status supplies the recorded handle",
      mode="test")
def c_prepare_reply_lost(t):
    """reply.write=epipe on prepare: the preparation is recorded but the reply is lost.
    Status offers the commission argv with the recorded handle (its check binds the
    prepared record), and that argv commissions."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.cmd(["prepare", sub.ref], name="prep-lost.prepare", envelope=False, fault="reply.write=epipe")
    t.eq("prep-lost.log", t.log_kinds(sub), ["reference", "prepared"])
    st = t.status(sub, name="prep-lost.status")
    offers = [a for a in st.next_argvs() if a[1] == "commission"]
    t.require("prep-lost.offer", len(offers) == 1 and len(offers[0]) == 5 and offers[0][4] == "--i-am-finished", st.next)
    h = offers[0][3]
    m = MP_RE.match(h)
    sums = [sha256_hex(r["raw"]) for r in t.read_log(sub) if (r["obj"] or {}).get("kind") == "prepared"]
    t.check("prep-lost.handle-binding", m and any(handle_check(sub.store, sub.audit, "mp", h.split(".")[0], [s]) == m.group(2)
                                                  for s in sums), h)
    rep = t.cmd(offers[0][1:], name="prep-lost.commission", expect="completed")


@case("c17.human", ["C17", "C16"], "human presentation: same exit status, stable reason named")
def c_human(t):
    """Without --json, a refusal exits 3 and names its reason identifier; status exits 0.
    Nothing in the human output is required to be JSON."""
    sub = t.submission(basic_entries(), make_materials=False)
    t.new_ref(sub)
    r = t.cmd(["prepare", sub.ref], json_reply=False, envelope=False, name="human.refusal")
    t.eq("human.refusal.exit", r.rc, 3)
    t.check("human.refusal.reason", "folder_incomplete" in r.text(), r.text()[:400])
    r = t.cmd(["status", sub.ref], json_reply=False, envelope=False, name="human.status")
    t.eq("human.status.exit", r.rc, 0)
    r = t.cmd(["status", "stw1:not-a-reference"], json_reply=False, envelope=False, name="human.bad-ref")
    t.eq("human.bad-ref.exit", r.rc, 3)
    t.check("human.bad-ref.reason", "reference_invalid" in r.text(), r.text()[:400])


@case("c17.human-failure", ["C17"], "human presentation of a failure", mode="test")
def c_human_failure(t):
    """A capture failure without --json exits 4 and names capture_failed."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    r = t.cmd(["commission", sub.ref, sub.handles[-1], "--i-am-finished"], json_reply=False, envelope=False,
              name="human.failure", fault="commission.capture_write=eio")
    t.eq("human.failure.exit", r.rc, 4)
    t.check("human.failure.reason", "capture_failed" in r.text(), r.text()[:400])


# ---------------------------------------------------------------------------
# C6: publication races.
# ---------------------------------------------------------------------------

@case("c6.log-race", ["C6", "C20"], "two prepares race for one log number; EEXIST advances, nothing is overwritten",
      mode="test", controls=[Control("rewrite_record_in_place", [r"^inventory\.", r"^race\.", r"^log\."])])
def c_log_race(t):
    """Prepare A pauses at log.publish:prepared with its number chosen; prepare B
    publishes that number; A is released and must take the next number. Both handles
    bind their own records, the chain is intact and no earlier file changed."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    bg = t.start(["prepare", sub.ref], name="race.paused-prepare", fault="log.publish:prepared=pause")
    stem = t.wait_paused("log.publish", bg)
    t.prepare(sub, name="race.other-prepare")
    t.release(stem)
    rep = t.finish(bg, expect="completed", prefix="race.paused-prepare")
    if rep.outcome == "completed":
        t.check_prepared(rep, sub, "race.paused-prepare", sub.writer)
    t.eq("race.log", t.log_kinds(sub), ["reference", "prepared", "prepared"])
    t.check("race.distinct-handles", len(set(sub.handles)) == 2, sub.handles)
    t._verify_log(sub.archive, sub.audit)
    t.commission(sub, sub.handles[0], name="race.commission")


# ---------------------------------------------------------------------------
# Close before launch (C8 pre-launch, C16).
# ---------------------------------------------------------------------------

@case("close.before-launch", ["C8", "C16", "C18", "C15"], "close before launch: closed, no answer, folder intact",
      tags=("close",))
def c_close_before_launch(t):
    """Close after new, after prepare and after acceptance: completed with closure
    complete, close_requested then closed (before_launch), no seal or answer files,
    status closed_before_launch with no next calls, a repeat returns already_closed and
    publishes nothing, prepare/commission refuse reference_closed. After acceptance the
    receipt still reads the witness."""
    for label, stage in (("new", 0), ("prepared", 1), ("accepted", 2)):
        sub = t.submission(basic_entries())
        t.new_ref(sub, name="close.%s.new" % label)
        if stage >= 1:
            t.prepare(sub, name="close.%s.prepare" % label)
        if stage >= 2:
            t.commission(sub, sub.handles[-1], name="close.%s.commission" % label)
        p = "close.%s" % label
        rep = t.cmd(["close", sub.ref], name=p, expect="completed")
        t.eq(p + ".effects", no_diag(rep.effects), {"run": "not_started", "seal": "none", "delivery": "none", "closure": "complete"})
        t.eq(p + ".data.closure", rep.data.get("closure"), "complete")
        kinds = t.log_kinds(sub)
        t.eq(p + ".log", kinds[-2:], ["close_requested", "closed"])
        closed = t.log_bodies(sub, "closed")
        t.check(p + ".before_launch", closed and closed[-1].get("before_launch") is True, closed)
        for d in ("seal", "prepared", "payload", "runs", "delivery"):
            t.check(p + ".no-%s" % d, not os.path.exists(os.path.join(sub.audit_dir, d)) or not os.listdir(os.path.join(sub.audit_dir, d)), d)
        st = t.status(sub, name=p + ".status")
        t.check_status(st, sub, p + ".status", condition="closed_before_launch", accepted="yes" if stage == 2 else "no",
                       closed="yes")
        t.eq(p + ".status.next", st.next, [])
        n = len(kinds)
        rep = t.cmd(["close", sub.ref], name=p + ".repeat", expect="completed")
        t.eq(p + ".repeat.already_closed", rep.data.get("already_closed"), True)
        t.eq(p + ".repeat.no-new-log", len(t.log_kinds(sub)), n)
        t.prepare(sub, name=p + ".prepare-after", expect="refused",
                  reason="reference_closed" if stage < 2 else ("reference_closed", "reference_already_accepted"))
        if stage == 1:
            t.commission(sub, sub.handles[-1], name=p + ".commission-after", expect="refused", reason="reference_closed")
            t.check(p + ".no-intake", t.intake_dirs(sub) == [], t.intake_dirs(sub))
        elif stage == 2:
            n_int = t.intake_dirs(sub)
            t.commission(sub, sub.handles[-1], name=p + ".commission-after", already=True)
            t.eq(p + ".commission-after.no-capture", t.intake_dirs(sub), n_int)
        if stage == 2:
            t.cmd(["receipt", sub.ref], name=p + ".receipt", expect="completed")
            for item, exp in sub.items().items():
                t.check_readback_ok(sub, item, exp, p + ".readback")


@case("close.killed-before-closed", ["C8", "C16", "C17"], "close killed before closed: unfinished, then completed by close",
      mode="test", tags=("close",))
def c_close_killed(t):
    """close.before_closed_link=kill leaves close_requested without closed. Status
    reports close_unfinished (closed: unfinished) with next close; prepare refuses
    reference_closed; close again completes."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    r = t.cmd(["close", sub.ref], name="close-killed.close", envelope=False, fault="close.before_closed_link=kill")
    t.eq("close-killed.signal", r.rc, -signal.SIGKILL)
    t.eq("close-killed.log", t.log_kinds(sub)[-1:], ["close_requested"])
    st = t.status(sub, name="close-killed.status")
    t.check_status(st, sub, "close-killed.status", condition="close_unfinished", accepted="no", closed="unfinished",
                   next_cmds=("close",))
    t.prepare(sub, name="close-killed.prepare", expect="refused", reason="reference_closed")
    rep = t.cmd(["close", sub.ref], name="close-killed.again", expect="completed")
    t.eq("close-killed.again.closure", rep.data.get("closure"), "complete")
    st = t.status(sub, name="close-killed.final-status")
    t.check_status(st, sub, "close-killed.final-status", condition="closed_before_launch", accepted="no", closed="yes")


@case("close.during-intake", ["C8", "C17"], "close races a live intake; their recorded outcomes agree",
      mode="test", needs=("lock",), tags=("close",),
      linux_reason="close waits on the OFD lock held by the intake; OFD locks are a Linux-only expectation")
def c_close_during_intake(t):
    """Commission pauses after its first capture; close publishes close_requested and
    waits; the intake is released within the wait. The commission refuses
    reference_closed (acceptance absent), close completes, no accepted record exists
    and intake_ended closed precedes closed."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    bg = t.start(["commission", sub.ref, h, "--i-am-finished"], name="race-intake.commission",
                 fault="commission.after_capture:1=pause")
    stem = t.wait_paused("commission.after_capture", bg)
    cl = t.start(["close", sub.ref], name="race-intake.close")
    deadline = time.time() + 8
    while time.time() < deadline and "close_requested" not in t.log_kinds(sub):
        time.sleep(0.02)
    t.check("race-intake.close-requested", "close_requested" in t.log_kinds(sub), t.log_kinds(sub))
    t.release(stem)
    rc = t.finish(bg, expect="refused", reason="reference_closed", sync=False, prefix="race-intake.commission")
    t.eq("race-intake.commission.acceptance", rc.effects.get("acceptance"), "absent")
    t.check("race-intake.commission.attempt", rc.effects.get("attempt") in ("partial", "recorded"), rc.effects)
    rcl = t.finish(cl, expect="completed", prefix="race-intake.close")
    t.eq("race-intake.close.closure", rcl.data.get("closure"), "complete")
    kinds = t.log_kinds(sub)
    t.check("race-intake.no-accepted", "accepted" not in kinds, kinds)
    t.check("race-intake.order", kinds[-1:] == ["closed"] and "intake_ended" in kinds
            and kinds.index("intake_ended") < kinds.index("closed"), kinds)
    bodies = t.log_bodies(sub, "intake_ended")
    t.check("race-intake.intake-ended-closed", bodies and bodies[-1].get("outcome") == "closed", bodies)
    st = t.status(sub, name="race-intake.status")
    t.check_status(st, sub, "race-intake.status", condition="closed_before_launch", accepted="no", closed="yes")


@case("close.intake-still-running", ["C8", "C16"], "close gives up after its 10 s intake wait, then completes later",
      mode="test", needs=("lock",), tags=("close",),
      linux_reason="close waits on the OFD lock held by the intake; OFD locks are a Linux-only expectation")
def c_close_intake_running(t):
    """With the intake paused throughout, close replies completed with closure unfinished
    and unfinished_reason intake_still_running after waiting about 10 s. The released
    intake refuses reference_closed; close then completes."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    bg = t.start(["commission", sub.ref, h, "--i-am-finished"], name="still-running.commission",
                 fault="commission.after_capture:1=pause")
    stem = t.wait_paused("commission.after_capture", bg)
    rep = t.cmd(["close", sub.ref], name="still-running.close", expect="completed", timeout=60)
    t.eq("still-running.close.closure", rep.data.get("closure"), "unfinished")
    t.eq("still-running.close.reason", rep.data.get("unfinished_reason"), "intake_still_running")
    t.check("still-running.close.waited", 9000 <= rep.wall_ms <= 30000, rep.wall_ms)
    t.check("still-running.close.effects", rep.effects.get("closure") in ("unfinished", "requested"), rep.effects)
    t.check("still-running.close.next", any(a[1] == "close" for a in rep.next_argvs()), rep.next)
    t.release(stem)
    t.finish(bg, expect="refused", reason="reference_closed", prefix="still-running.commission")
    rep = t.cmd(["close", sub.ref], name="still-running.close-again", expect="completed")
    t.eq("still-running.close-again.closure", rep.data.get("closure"), "complete")
    t.check("still-running.no-accepted", "accepted" not in t.log_kinds(sub), t.log_kinds(sub))


# ---------------------------------------------------------------------------
# C18: designated custody.
# ---------------------------------------------------------------------------

@case("c18.archive-roots", ["C18", "C20"], "explicit archive selection; existing roots are used or refused, never replaced")
def c_archive_roots(t):
    """An existing empty directory becomes a store; an existing store is reused (same
    store, new audit, archive_created false); a non-empty non-store refuses
    archive_not_a_store and stays unchanged; an absent parent creates nothing.
    STEWART_ARCHIVE serves new only when --archive is absent; neither is
    archive_unspecified. Relative paths create nothing."""
    empty = t.archive_path()
    os.makedirs(empty)
    t.premade_roots.add(empty)
    s1 = t.submission(basic_entries(), archive=empty)
    t.new_ref(s1, name="roots.empty-dir")
    s2 = t.submission(basic_entries(), archive=empty)
    rep = t.new_ref(s2, name="roots.reuse")
    t.eq("roots.reuse.store", s2.store, s1.store)
    t.check("roots.reuse.new-audit", s2.audit != s1.audit, (s1.audit, s2.audit))
    t.eq("roots.reuse.archive_created", rep.data.get("archive_created"), False)
    other = t.archive_path()
    os.makedirs(other)
    with open(os.path.join(other, "notes.txt"), "wb") as f:
        f.write(b"not a store\n")
    t.watch(other, "frozen", "non-store directory")
    s3 = t.submission(basic_entries(), archive=other)
    rep = t.cmd(["new", s3.folder, "--archive", other], name="roots.not-a-store", expect="refused",
                reason="archive_not_a_store")
    t.eq("roots.not-a-store.effects", no_diag(rep.effects), {"reference": "none"})
    orphan = os.path.join(t.root, "absent parent %d" % t.next_k(), "archive")
    t.cmd(["new", s3.folder, "--archive", orphan], name="roots.absent-parent", expect="refused")
    t.check("roots.absent-parent.nothing", not os.path.lexists(os.path.dirname(orphan)), orphan)
    s4 = t.submission(basic_entries())
    rep = t.cmd(["new", s4.folder], name="roots.unspecified", expect="refused", reason="archive_unspecified")
    t.eq("roots.unspecified.effects", no_diag(rep.effects), {"reference": "none"})
    envroot = t.archive_path()
    t.watch(envroot, "archive", "env archive")
    rep = t.cmd(["new", s4.folder], name="roots.env", expect="completed", env={"STEWART_ARCHIVE": envroot})
    t.eq("roots.env.archive", rep.data.get("archive"), envroot)
    flagroot = t.archive_path()
    t.watch(flagroot, "archive", "flag archive")
    s5 = t.submission(basic_entries())
    envroot2 = t.archive_path()
    rep = t.cmd(["new", s5.folder, "--archive", flagroot], name="roots.flag-wins", expect="completed",
                env={"STEWART_ARCHIVE": envroot2})
    t.eq("roots.flag-wins.archive", rep.data.get("archive"), flagroot)
    t.check("roots.flag-wins.env-untouched", not os.path.lexists(envroot2), envroot2)
    rel = "relative-archive"
    r = t.cmd(["new", s5.folder, "--archive", rel], name="roots.relative", envelope=False)
    t.check("roots.relative.refused", r.rc in (2, 3), r.rc)
    t.check("roots.relative.nothing", not os.path.lexists(os.path.join(t.cwd, rel)), rel)
    r = t.cmd(["new", "relative-folder", "--archive", flagroot], name="roots.relative-folder", envelope=False)
    t.check("roots.relative-folder.refused", r.rc in (2, 3), r.rc)
    t.check("roots.relative-folder.nothing", not os.path.lexists(os.path.join(t.cwd, "relative-folder")), "created")


@case("c18.archive-symlink", ["C18"], "an archive path through a symlink is refused before anything is created")
def c_archive_symlink(t):
    """The root's path has a symlink component: archive_path_symlink, nothing created at
    the link target; a symlink that is the root itself is refused too."""
    real = t.mkdir("real parent %d" % t.next_k())
    link = os.path.join(t.root, "linked parent %d" % t.next_k())
    os.symlink(real, link)
    t.watch(real, "frozen", "link target")
    sub = t.submission(basic_entries())
    rep = t.cmd(["new", sub.folder, "--archive", os.path.join(link, "archive")], name="symlink.component",
                expect="refused", reason="archive_path_symlink")
    t.eq("symlink.component.effects", no_diag(rep.effects), {"reference": "none"})
    real2 = t.mkdir("real root %d" % t.next_k())
    link2 = os.path.join(t.root, "root link %d" % t.next_k())
    os.symlink(real2, link2)
    t.watch(real2, "frozen", "link target 2")
    t.cmd(["new", sub.folder, "--archive", link2], name="symlink.root", expect="refused", reason="archive_path_symlink")


@case("c18.overlap", ["C18"], "archive, folder and destination may not contain one another, by opened identity")
def c_overlap(t):
    """new refuses an archive inside the folder, a folder inside the archive, the same
    directory for both, and a folder reached through a symlink into the archive.
    Prepare refuses destinations equal to or inside the archive or folder, including
    one reached through a symlink alias. Each is location_overlap and creates nothing."""
    sub = t.submission(basic_entries())
    inside = os.path.join(sub.folder, "materials", "archive-here")
    t.cmd(["new", sub.folder, "--archive", inside], name="overlap.archive-in-folder", expect="refused",
          reason="location_overlap")
    t.check("overlap.archive-in-folder.nothing", not os.path.lexists(inside), inside)
    t.cmd(["new", sub.folder, "--archive", sub.folder], name="overlap.same", expect="refused", reason="location_overlap")
    base = t.submission(basic_entries())
    t.new_ref(base, name="overlap.base")
    nested = os.path.join(base.archive, "audits", "my-folder")
    t.cmd(["new", nested, "--archive", base.archive], name="overlap.folder-in-archive", expect="refused",
          reason="location_overlap")
    t.check("overlap.folder-in-archive.nothing", not os.path.lexists(nested), nested)
    alias = os.path.join(t.root, "alias to archive %d" % t.next_k())
    os.symlink(base.archive, alias)
    t.cmd(["new", os.path.join(alias, "folder-via-alias"), "--archive", base.archive], name="overlap.folder-alias",
          expect="refused", reason="location_overlap")
    t.check("overlap.folder-alias.nothing", not os.path.lexists(os.path.join(base.archive, "folder-via-alias")), "created")
    qpath = os.path.join(base.folder, "question.md")
    sub_dir = mat(base, "src")
    for label, dest in (("archive-root", base.archive), ("archive-inner", os.path.join(base.archive, "audits")),
                        ("folder", base.folder), ("materials-dir", sub_dir), ("alias", alias)):
        t.edit(qpath, question_md(dest=dest))
        t.prepare(base, name="overlap.destination.%s" % label, expect="refused", reason="location_overlap")
    t.edit(qpath, question_md(dest=base.dest))
    t.prepare(base, name="overlap.destination.disjoint")


@case("c18.missing-archive", ["C18", "C15"], "a missing archive is diagnosed, never recreated")
def c_missing_archive(t):
    """With the archive moved away every command refuses archive_unavailable and nothing
    appears at the old path; moved back, the same reference reads its accepted audit."""
    sub = t.submission(basic_entries())
    h, _ = t.accept(sub)
    away = sub.archive + " moved"
    t.driver_change("move the archive away", lambda: os.rename(sub.archive, away))
    t.watch(away, "archive", "moved archive")
    for label, args in (("status", ["status", sub.ref]), ("receipt", ["receipt", sub.ref]),
                        ("prepare", ["prepare", sub.ref]), ("commission", ["commission", sub.ref, h, "--i-am-finished"]),
                        ("close", ["close", sub.ref])):
        t.cmd(args, name="missing.%s" % label, expect="refused", reason="archive_unavailable")
        t.check("missing.%s.not-recreated" % label, not os.path.lexists(sub.archive), sub.archive)
    t.check_readback_refused(sub, "materials/a.txt", ("archive_unavailable", "item_missing", "item_unreadable"),
                             "missing.read")
    t.driver_change("move the archive back", lambda: os.rename(away, sub.archive))
    st = t.status(sub, name="missing.restored")
    t.check_status(st, sub, "missing.restored", condition="not_started", accepted="yes", next_cmds=("run", "close"))


@case("c18.replaced-archive", ["C18", "C20"], "a different store at the reference's path is archive_replaced",
      controls=[Control("select_newer_store", [r"^replaced\."])])
def c_replaced_archive(t):
    """The archive is moved away and a new store created at the same path. The old
    reference refuses archive_replaced for status, receipt, prepare, commission and
    close, and reads no bytes; the new store's own audit is unaffected."""
    sub = t.submission(basic_entries())
    h, _ = t.accept(sub)
    away = sub.archive + " old"
    t.driver_change("move the archive away", lambda: os.rename(sub.archive, away))
    t.watch(away, "archive", "old archive")
    other = t.submission(basic_entries(), archive=sub.archive)
    t.new_ref(other, name="replaced.new-store")
    t.check("replaced.different-store", other.store != sub.store, (other.store, sub.store))
    for label, args in (("status", ["status", sub.ref]), ("receipt", ["receipt", sub.ref]),
                        ("prepare", ["prepare", sub.ref]), ("commission", ["commission", sub.ref, h, "--i-am-finished"]),
                        ("close", ["close", sub.ref])):
        t.cmd(args, name="replaced.%s" % label, expect="refused", reason="archive_replaced")
    t.check_readback_refused(sub, "materials/a.txt", ("archive_replaced",), "replaced.read")
    st = t.status(other, name="replaced.other-status")
    t.check_status(st, other, "replaced.other-status", condition="preparing", accepted="no", next_cmds=("prepare",))


@case("c18.copied-archive", ["C18", "C15"], "a copied archive can be read but never mutated")
def c_copied_archive(t):
    """A copy of the archive at another path, addressed by a reference to the copy, serves
    status and readback; prepare, commission and close refuse archive_moved_or_copied;
    the original archive is unchanged."""
    sub = t.submission(basic_entries())
    h, _ = t.accept(sub)
    copy_root = os.path.join(os.path.dirname(sub.archive), "copied store")

    def copy():
        shutil.copytree(sub.archive, copy_root, symlinks=True)
    t.driver_change("copy the archive", copy)
    t.watch(copy_root, "archive", "copied archive")
    ref2 = make_reference(sub.audit, sub.store, copy_root)
    clone = Sub(t, sub.folder, sub.dest, copy_root, sub.question, sub.entries, [], sub.family, sub.model, sub.limits)
    clone.ref, clone.audit, clone.store, clone.writer = ref2, sub.audit, sub.store, sub.writer
    clone.files, clone.arrangement, clone.accepted_handle = sub.files, sub.arrangement, sub.accepted_handle
    st = t.status(clone, name="copied.status")
    t.check("copied.status.read", st.outcome == "completed", st.obj)
    for item in ("materials/a.txt", "question-file"):
        t.check_readback_ok(clone, item, sub.items()[item], "copied.read")
    for label, args in (("prepare", ["prepare", ref2]), ("commission", ["commission", ref2, h, "--i-am-finished"]),
                        ("close", ["close", ref2])):
        t.cmd(args, name="copied.%s" % label, expect="refused", reason="archive_moved_or_copied")


@case("c18.invariance", ["C18", "C12", "C20"], "the reference selects its archive from any directory, HOME or install path")
def c_custody_invariance(t):
    """Status and receipt give the same data from another working directory and HOME
    with STEWART_ARCHIVE naming another store, and from a byte-identical copy of the
    binary at another path; suggested argv names the recorded writer. A mutation from
    the copy (same digest) is accepted and still names the recorded path. The other
    store is unchanged."""
    sub = t.submission(basic_entries())
    h, _ = t.accept(sub)
    st0 = t.status(sub, name="invariance.status")
    rc0 = t.cmd(["receipt", sub.ref], name="invariance.receipt", expect="completed")
    decoy = t.submission(basic_entries())
    t.new_ref(decoy, name="invariance.decoy")
    other = t.mkdir("other install %d" % t.next_k())
    copy = os.path.join(other, "stewart")
    shutil.copy2(t.bin["path"], copy)
    t.drv.register_alias(copy, t.bin)
    env = {"HOME": t.fresh_dir("home b"), "STEWART_ARCHIVE": decoy.archive}
    cwd = t.fresh_dir("cwd b")
    st1 = t.status(sub, name="invariance.status-elsewhere", binary=copy, env=env, cwd=cwd, writer=sub.writer)
    t.eq("invariance.status-data", st1.data, st0.data)
    rc1 = t.cmd(["receipt", sub.ref], name="invariance.receipt-elsewhere", binary=copy, env=env, cwd=cwd,
                writer=sub.writer, expect="completed")
    t.eq("invariance.receipt-data", rc1.data, rc0.data)
    fresh = t.submission(basic_entries())
    t.new_ref(fresh, name="invariance.fresh")
    rep = t.prepare(fresh, name="invariance.prepare-from-copy", binary=copy, env=env, writer=fresh.writer)
    t.check("invariance.copy-may-write", rep.outcome == "completed", rep.obj)


@case("c18.writer-mismatch", ["C18", "C20"], "another binary reads but never mutates an audit")
def c_writer_mismatch(t):
    """An audit created by the release binary: the test binary (another digest) refuses
    prepare, commission and close with writer_mismatch naming the recorded path and
    digest, but reads status, receipt and raw items."""
    other = t.drv.test["path"]
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    for label, args in (("prepare", ["prepare", sub.ref]),):
        rep = t.cmd(args, name="mismatch.%s" % label, binary=other, writer=sub.writer, expect="refused",
                    reason="writer_mismatch")
        text = json.dumps(rep.obj or {}, ensure_ascii=False)
        t.check("mismatch.%s.names-writer" % label, sub.writer in text and t.bin["sha256"] in text, text[:500])
    t.prepare(sub)
    h = sub.handles[-1]
    t.cmd(["commission", sub.ref, h, "--i-am-finished"], name="mismatch.commission", binary=other, writer=sub.writer,
          expect="refused", reason="writer_mismatch")
    t.eq("mismatch.no-intake", t.intake_dirs(sub), [])
    t.commission(sub, h)
    t.cmd(["close", sub.ref], name="mismatch.close", binary=other, writer=sub.writer, expect="refused",
          reason="writer_mismatch")
    t.status(sub, name="mismatch.status", binary=other, writer=sub.writer)
    t.cmd(["receipt", sub.ref], name="mismatch.receipt", binary=other, writer=sub.writer, expect="completed")
    t.check_readback_ok(sub, "materials/a.txt", sub.items()["materials/a.txt"], "mismatch.read", binary=other)


@case("c18.permissions", ["C18", "C17"], "insufficient permissions give a contextual account and broaden nothing",
      needs=("nonroot",))
def c_permissions(t):
    """With the archive root mode 000, status does not complete and readback writes no
    bytes; with an audit's log/ directory read-only, prepare does not complete and
    reports no recorded preparation. Each reply is a well-formed envelope with a
    stable reason. Restoring the modes restores ordinary operation."""
    sub = t.submission(basic_entries())
    t.accept(sub)
    root = sub.archive
    t.mode_exempt.add(root)
    t.driver_change("chmod 000 the archive root", lambda: os.chmod(root, 0))
    t.cleanup(lambda: os.chmod(root, 0o700))
    r = t.cmd(["status", sub.ref], name="perm.status")
    t.check("perm.status.not-completed", r.outcome in ("refused", "failed"), r.obj)
    t.check_readback_refused(sub, "materials/a.txt", ("archive_unavailable", "item_unreadable", "item_missing"),
                             "perm.read")
    t.driver_change("restore the archive root", lambda: os.chmod(root, 0o700))
    st = t.status(sub, name="perm.status-restored")
    t.check_status(st, sub, "perm.restored", condition="not_started", accepted="yes", next_cmds=("run", "close"))
    other = t.submission(basic_entries(), archive=root)
    t.new_ref(other, name="perm.other.new")
    log = os.path.join(other.audit_dir, "log")
    t.mode_exempt.add(log)
    t.driver_change("chmod 0500 log/", lambda: os.chmod(log, 0o500))
    t.cleanup(lambda: os.chmod(log, 0o700))
    r = t.cmd(["prepare", other.ref], name="perm.prepare", writer=other.writer)
    t.check("perm.prepare.not-completed", r.outcome in ("refused", "failed"), r.obj)
    t.check("perm.prepare.no-record", r.effects.get("preparation") in ("none", "unknown"), r.effects)
    t.eq("perm.prepare.log", t.log_kinds(other), ["reference"])
    t.driver_change("restore log/", lambda: os.chmod(log, 0o700))
    t.prepare(other, name="perm.prepare-restored")


@case("c18.filesystem-unsupported", ["C18"], "an archive on tmpfs is refused, naming the type",
      needs=("linux",), linux_reason="the ext4/xfs/btrfs allowlist is a Linux-only expectation")
def c_fs_unsupported(t):
    """new --archive on a writable tmpfs mount refuses archive_filesystem_unsupported,
    naming the observed type, and creates nothing there."""
    target = None
    for mp, kind in tmpfs_mounts():
        try:
            target = tempfile.mkdtemp(prefix="stewart-step3-fs-", dir=mp)
            fstype = kind
            break
        except OSError:
            continue
    if target is None:
        t.skip("no writable tmpfs mount found in /proc/self/mountinfo")
    t.cleanup(lambda: shutil.rmtree(target, ignore_errors=True))
    root = os.path.join(target, "archive")
    sub = t.submission(basic_entries())
    rep = t.cmd(["new", sub.folder, "--archive", root], name="fs.tmpfs", expect="refused",
                reason="archive_filesystem_unsupported")
    t.check("fs.names-type", fstype in json.dumps(rep.obj or {}), rep.obj)
    t.check("fs.nothing-created", not os.path.lexists(root), root)


@case("c18.status-archive", ["C18", "C16", "C11"], "status --archive lists references in creation order and selects none")
def c_status_archive(t):
    """Three references in one archive are listed in creation order with folder, inquiry
    label, varies note and headline; the listing is read-only. new on an already
    referenced folder adds folder_already_referenced and still creates a reference."""
    root = t.archive_path()
    varies = make_reference(random_id("a"), random_id("s"), "/elsewhere/archive")
    a = t.submission(basic_entries(), archive=root, q={"inquiry": "Reminder duplicates — round 2", "varies": varies})
    b = t.submission(basic_entries(), archive=root)
    c = t.submission(basic_entries(), archive=root)
    for s, label in ((a, "a"), (b, "b"), (c, "c")):
        t.new_ref(s, name="list.new-%s" % label)
    t.prepare(a, name="list.prepare-a")
    rep = t.cmd(["status", "--archive", root], name="list.status", expect="completed", writer=None)
    refs = []
    for v in iter_values(rep.data):
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            found = [next((y for y in x.values() if isinstance(y, str) and y.startswith("stw1:")), None) for x in v]
            if all(found) and len(found) > len(refs):
                refs, entries = found, v
    t.eq("list.order", refs, [a.ref, b.ref, c.ref])
    if refs == [a.ref, b.ref, c.ref]:
        for s, e in zip((a, b, c), entries):
            t.check("list.folder", contains_string(e, s.folder), e)
            t.check("list.headline", any(isinstance(v, dict) and "accepted" in v for v in iter_values(e)), e)
        t.check("list.inquiry", contains_string(entries[0], "Reminder duplicates — round 2"), entries[0])
        t.check("list.varies", contains_string(entries[0], varies), entries[0])
    rep = t.cmd(["new", a.folder, "--archive", root], name="list.again", expect="completed")
    notices = rep.data.get("notices") or []
    t.check("list.folder_already_referenced", mentions(notices, "folder_already_referenced") and mentions(notices, a.ref), notices)
    t.check("list.again.new-reference", rep.data.get("reference") not in (a.ref, b.ref, c.ref), rep.data.get("reference"))


# ---------------------------------------------------------------------------
# C19: literal text materials and preparation inspection.
# ---------------------------------------------------------------------------

@case("c19.population", ["C19", "C2", "C11", "C15"], "the literal population is prepared, captured and read back exactly",
      controls=[Control("skip_hidden_entries", [r"^population\.prepare\."]),
                Control("normalize_newlines", [r"^population\.commission", r"^population\.readback\."])])
def c_population(t):
    """Hidden names, empty files and directories, BOM, CRLF, lone CR, multibyte text and
    names, NFD names, missing final newlines, hard links, nominal documents and a long
    line: prepare's index, sizes, digests, line counts and directories equal the
    witness; commission captures each once; every item reads back byte for byte."""
    sub = t.submission(population_entries(), body=POPULATION_BODY)
    t.new_ref(sub)
    rep = t.prepare(sub, name="population.prepare")
    t.require("population.prepare.completed", rep.outcome == "completed", rep.obj)
    t.check_prepare_witness(rep, sub, "population.prepare")
    files = (rep.data.get("materials") or {}).get("files") or []
    names = [f.get("name") for f in files]
    t.eq("population.prepare.bytewise-order", names, sorted(names, key=lambda n: n.encode("utf-8")))
    t.commission(sub, sub.handles[-1], name="population.commission")
    for item, exp in sub.items().items():
        t.check_readback_ok(sub, item, exp, "population.readback")


@case("c19.question", ["C19", "C2", "C20"], "question files: exact body bytes, empty bodies and invalid text")
def c_question(t):
    """CRLF throughout, a BOM, and a body with no final newline each read back exactly
    (question-file and question-body). Two questions differing in one body byte read
    back differing in exactly that byte. Empty and blank bodies refuse question_empty;
    invalid UTF-8 and NUL in the body refuse material_not_text."""
    specimens = [
        ("crlf", question_md(b"Line one\r\nline two\r\n", nl=b"\r\n")),
        ("bom", question_md("Café — BOM file\n".encode("utf-8"), bom=True)),
        ("no-final-newline", question_md(b"No final newline here")),
        ("no-comments", question_md(b"Plain\n", comments=False)),
    ]
    witnesses = {}
    for label, q in specimens:
        dest = t.dest_path()
        q = q.replace(b"/nonexistent", dest.encode())
        sub = t.submission([F("a.txt", b"a\n")], question=q, dest=dest)
        t.accept(sub, prefix="question.%s." % label)
        for item in ("question-file", "question-body"):
            t.check_readback_ok(sub, item, sub.items()[item], "question.%s.readback" % label)
        witnesses[label] = sub
    one = t.submission([F("a.txt", b"a\n")], body=b"Is it X?\n")
    two = t.submission([F("a.txt", b"a\n")], body=b"Is it Y?\n")
    t.accept(one, prefix="question.diff-a.")
    t.accept(two, prefix="question.diff-b.")
    ra = t.readback(one, "question-body", name="question.diff.read-a")
    rb = t.readback(two, "question-body", name="question.diff.read-b")
    diffs = [i for i, (x, y) in enumerate(zip(ra.stdout, rb.stdout)) if x != y]
    t.check("question.differing-one-byte", len(ra.stdout) == len(rb.stdout) and diffs == [6], diffs)
    sub = t.submission([F("a.txt", b"a\n")])
    t.new_ref(sub)
    qpath = os.path.join(sub.folder, "question.md")
    for label, body, reason in (("empty", b"", "question_empty"), ("blank", b"  \n\t\r\n\n", "question_empty"),
                                ("invalid-utf8", b"bad \xc3\x28 byte\n", "material_not_text"),
                                ("nul", b"nul \x00 byte\n", "material_not_text")):
        t.edit(qpath, question_md(body, dest=sub.dest))
        rep = t.prepare(sub, name="question.%s" % label, expect="refused", reason=reason)
        if reason == "material_not_text":
            t.check("question.%s.names-file" % label, "question.md" in json.dumps(rep.obj or {}, ensure_ascii=False), rep.obj)


@case("c19.content-invalid", ["C19", "C2"], "non-text material refuses intake, naming file and first bad offset")
def c_content_invalid(t):
    """Invalid UTF-8 (bad continuation, overlong, surrogate, 0xFF, truncated at end, BOM
    then truncation) and NUL each refuse material_not_text naming the file and the byte
    offset of the first invalid byte; no preparation is recorded."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    specimens = [("bad-continuation", b"ok \xc3\x28 x\n"), ("overlong", b"\xc0\xaf"), ("surrogate", b"abc\xed\xa0\x80"),
                 ("ff", b"\xff"), ("truncated", b"abc\xe2\x82"), ("bom-truncated", b"\xef\xbb\xbf\xef\xbb"),
                 ("nul", b"nul\x00byte\n"), ("pdf-binary", b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")]
    for label, data in specimens:
        try:
            data.decode("utf-8")
            off = data.index(b"\x00")
        except UnicodeDecodeError as exc:
            off = exc.start
        set_file(t, sub, "bad.bin", data)
        n = t.log_kinds(sub).count("prepared")
        rep = t.prepare(sub, name="content.%s" % label, expect="refused", reason="material_not_text")
        has_file, has_off = names_offset(rep, "bad.bin", off)
        t.check("content.%s.names-file" % label, has_file, rep.obj)
        t.check("content.%s.names-offset" % label, has_off, {"offset": off, "reply": rep.obj})
        t.eq("content.%s.no-preparation" % label, t.log_kinds(sub).count("prepared"), n)
        remove_file(t, sub, "bad.bin")
    t.prepare(sub, name="content.clean")


@case("c19.unsupported-entries", ["C19", "C2", "C11"], "links and special files refuse intake unread",
      controls=[Control("follow_symlinks", [r"^unsupported\."])])
def c_unsupported(t):
    """A symlink to an outside file holding a secret, an inside alias, a directory link,
    a dangling link, a FIFO and a socket under materials/ each refuse unsupported_entry
    naming the entry, without hanging and without the secret reaching the archive."""
    outside = t.mkdir("outside %d" % t.next_k())
    secret = ("SECRET-%s" % os.urandom(8).hex()).encode()
    with open(os.path.join(outside, "secret.txt"), "wb") as f:
        f.write(secret + b"\n")
    specimens = [("link-outside", [L("link.txt", os.path.join(outside, "secret.txt"))], "link.txt"),
                 ("link-inside", [F("real.txt", b"real\n"), L("alias.txt", "real.txt")], "alias.txt"),
                 ("link-dir", [L("dirlink", outside)], "dirlink"),
                 ("link-dangling", [L("dangling", "nowhere/at/all")], "dangling"),
                 ("fifo", [FIFO("pipe")], "pipe"),
                 ("socket", [SOCK("sock")], "sock")]
    for label, extra, name in specimens:
        try:
            sub = t.submission(basic_entries() + extra)
        except OSError as exc:
            t.skip_part(label, "could not create the specimen: %s" % exc)
            continue
        t.new_ref(sub, name="unsupported.%s.new" % label)
        rep = t.prepare(sub, name="unsupported.%s" % label, expect="refused", reason="unsupported_entry")
        t.check("unsupported.%s.names-entry" % label, name in json.dumps(rep.obj or {}, ensure_ascii=False), rep.obj)
        if rep.outcome == "completed":
            t.commission(sub, sub.handles[-1], name="unsupported.%s.commission" % label, expect=None)
        leaked = []
        for rel, e in (snapshot(sub.archive, t.cache) or {}).items():
            if e.get("kind") == "file":
                try:
                    if secret in read_bytes(os.path.join(sub.archive, rel)):
                        leaked.append(rel)
                except OSError:
                    pass
        t.check("unsupported.%s.secret-not-captured" % label, not leaked, leaked)


@case("c19.folder-layout", ["C19", "C11"], "the folder holds exactly question.md and materials/")
def c_folder_layout(t):
    """Missing question.md or materials/ refuses folder_incomplete naming it; any other
    root entry (file, hidden file, directory) refuses unexpected_root_entry naming it;
    question.md or materials/ as a symlink, and materials as a file, are refused."""
    outside = t.mkdir("outside %d" % t.next_k())
    with open(os.path.join(outside, "question.md"), "wb") as f:
        f.write(question_md())
    os.makedirs(os.path.join(outside, "mats"))
    specimens = [
        ("no-question", dict(make_question=False), ("folder_incomplete",), "question.md"),
        ("no-materials", dict(make_materials=False), ("folder_incomplete",), "materials"),
        ("root-file", dict(root_entries=[F("notes.txt", b"n\n")]), ("unexpected_root_entry",), "notes.txt"),
        ("root-hidden", dict(root_entries=[F(".DS_Store", b"\x00")]), ("unexpected_root_entry",), ".DS_Store"),
        ("root-dir", dict(root_entries=[D("extra")]), ("unexpected_root_entry",), "extra"),
        ("question-link", dict(make_question=False, root_entries=[L("question.md", os.path.join(outside, "question.md"))]),
         ("unsupported_entry", "folder_incomplete"), "question.md"),
        ("materials-link", dict(make_materials=False, root_entries=[L("materials", os.path.join(outside, "mats"))]),
         ("unsupported_entry", "folder_incomplete"), "materials"),
        ("materials-file", dict(make_materials=False, root_entries=[F("materials", b"x\n")]),
         ("folder_incomplete", "unsupported_entry"), "materials"),
    ]
    for label, kw, reasons, name in specimens:
        sub = t.submission(basic_entries(), **kw)
        t.new_ref(sub, name="layout.%s.new" % label)
        rep = t.prepare(sub, name="layout.%s" % label, expect="refused", reason=reasons)
        t.check("layout.%s.names-entry" % label, name in json.dumps(rep.obj or {}, ensure_ascii=False), rep.obj)
        if label.startswith("root-"):
            nxt = json.dumps(rep.obj or {}, ensure_ascii=False)
            t.check("layout.%s.suggests-materials" % label, "materials" in nxt, rep.obj)


def _probe_names(t, names):
    """True when every byte-name can be created as a distinct entry here."""
    d = t.mkdir("probe %d" % t.next_k())
    try:
        for n in names:
            fd = os.open(os.path.join(os.fsencode(d), n), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            os.close(fd)
        return len(os.listdir(os.fsencode(d))) == len(names)
    except OSError:
        return False
    finally:
        shutil.rmtree(d, ignore_errors=True)


@case("c19.names", ["C19", "C20"], "names are exact UTF-8 without control characters; no normalization")
def c_names(t):
    """Control characters (C0, DEL, C1) and invalid UTF-8 in names refuse name_invalid.
    NFC and NFD spellings, and names differing only in case, are distinct materials
    where the filesystem allows them."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    bad = [("c0", "ctl\x01.txt"), ("tab", "tab\t.txt"), ("newline", "nl\n.txt"), ("del", "del\x7f.txt"),
           ("c1-nel", "c1\u0085.txt"), ("c1-9f", "c1\u009f.txt")]
    for label, name in bad:
        try:
            set_file(t, sub, name, b"x\n")
        except OSError as exc:
            t.skip_part("name %s" % label, "filesystem refused the name: %s" % exc)
            continue
        t.prepare(sub, name="names.%s" % label, expect="refused", reason="name_invalid")
        remove_file(t, sub, name)
    if _probe_names(t, [b"bad\xff.txt"]):
        p = os.path.join(os.fsencode(sub.folder), b"materials", b"bad\xff.txt")
        t.driver_change("create a non-UTF-8 name", lambda: open(p, "wb").close())
        t.prepare(sub, name="names.invalid-utf8", expect="refused", reason="name_invalid")
        t.driver_change("remove the non-UTF-8 name", lambda: os.unlink(p))
    else:
        t.skip_part("invalid UTF-8 name", "this filesystem refuses non-UTF-8 names (Linux-only expectation)")
    nfc = "caf" + unicodedata.normalize("NFC", NFD_E) + ".txt"
    nfd = "caf" + NFD_E + ".txt"
    if _probe_names(t, [nfc.encode(), nfd.encode()]):
        s2 = t.submission([F(nfc, b"nfc\n"), F(nfd, b"nfd\n")])
        t.accept(s2, prefix="names.nfc-nfd.", check_witness=True)
        t.check_readback_ok(s2, "materials/" + nfd, b"nfd\n", "names.nfd")
        t.check_readback_ok(s2, "materials/" + nfc, b"nfc\n", "names.nfc")
    else:
        t.skip_part("NFC and NFD siblings", "this filesystem treats the two spellings as one name")
    if _probe_names(t, [b"Case.txt", b"case.txt"]):
        s3 = t.submission([F("Case.txt", b"upper\n"), F("case.txt", b"lower\n")])
        t.accept(s3, prefix="names.case.", check_witness=True)
    else:
        t.skip_part("case siblings", "this filesystem is case-insensitive")


@case("c19.invariance", ["C19", "C2"], "location, extension and permissions change no content identity")
def c_c19_invariance(t):
    """The same materials under two unrelated folder locations get identical prepared
    entries and readback; equal bytes named .txt, .pdf and without extension share one
    digest; read-only modes change nothing."""
    entries = [F("a.txt", b"same bytes\n"), F("a.pdf", b"same bytes\n"), F("a", b"same bytes\n"), F("d/x.md", b"# x\n")]
    s1 = t.submission(entries)
    s2 = t.submission(entries)
    t.driver_change("chmod 0444 a file of s2", lambda: os.chmod(mat(s2, "a.txt"), 0o444))
    t.driver_change("chmod 0555 a directory of s2", lambda: os.chmod(mat(s2, "d"), 0o555))
    t.cleanup(lambda: os.chmod(mat(s2, "d"), 0o755))
    t.new_ref(s1, name="loc.new-1")
    t.new_ref(s2, name="loc.new-2")
    r1 = t.prepare(s1, name="loc.prepare-1")
    r2 = t.prepare(s2, name="loc.prepare-2")
    t.check_prepare_witness(r1, s1, "loc.prepare-1")
    t.eq("loc.same-index", (r2.data.get("materials") or {}).get("files"), (r1.data.get("materials") or {}).get("files"))
    files = (r1.data.get("materials") or {}).get("files") or []
    t.check("loc.extension-blind", len({f.get("sha256") for f in files if f.get("name", "").startswith("materials/a")}) == 1, files)
    t.commission(s1, s1.handles[-1], name="loc.commission-1")
    t.commission(s2, s2.handles[-1], name="loc.commission-2")
    for item in ("materials/a.txt", "materials/a.pdf", "materials/a", "materials/d/x.md"):
        a = t.readback(s1, item, name="loc.read-1 %s" % item)
        b = t.readback(s2, item, name="loc.read-2 %s" % item)
        t.check("loc.same-bytes", a.stdout == b.stdout == s1.items()[item], item)


@case("c19.arrangement", ["C19", "C11", "C1"], "the pinned arrangement carries the exact forms, tools and limits")
def c_arrangement(t):
    """For each family the machine arrangement pins the exact system bytes (orientation
    and family instructions), the family's tools in order with exact descriptions and
    schemas, the three notice texts, the limits, reader, renderer and bindings; the
    readable arrangement shows the same texts. Families differ exactly in recording
    tools and the second system block; different materials change neither."""
    got = {}
    for family in ("open-inquiry", "inquiry-framing", "comparison"):
        sub = t.submission(basic_entries(), family=family, q={"turns": "321", "input_tokens": "4321000",
                                                             "output_tokens": "54321"})
        t.new_ref(sub, name="arr.%s.new" % family)
        rep = t.prepare(sub, name="arr.%s.prepare" % family)
        if rep.outcome != "completed":
            continue
        got[family] = check_arrangement(t, sub, sub.handles[-1], family, "arr.%s" % family, (321, 4321000, 54321))
    alt = t.submission([F("other.txt", b"entirely different material\n")], q={"turns": "321", "input_tokens": "4321000",
                                                                              "output_tokens": "54321"})
    t.new_ref(alt, name="arr.alt.new")
    rep = t.prepare(alt, name="arr.alt.prepare")
    if rep.outcome == "completed" and "open-inquiry" in got:
        g = check_arrangement(t, alt, alt.handles[-1], "open-inquiry", "arr.alt", (321, 4321000, 54321))
        t.eq("arr.invariance.system", g.get("system"), got["open-inquiry"].get("system"))
        t.eq("arr.invariance.tools", g.get("tools"), got["open-inquiry"].get("tools"))
    if len(got) == 3:
        o, f, c = got["open-inquiry"], got["inquiry-framing"], got["comparison"]
        names = lambda g: [x.get("name") for x in (g.get("tools") or []) if isinstance(x, dict)]
        common = lambda ns: [n for n in ns if not n.startswith("record_") or n == "record_artifact"]
        t.eq("arr.differing.common-tools", common(names(f)), common(names(o)))
        t.eq("arr.differing.common-tools-2", common(names(c)), common(names(o)))
        sys_o, sys_f = o.get("system_value"), f.get("system_value")
        if isinstance(sys_o, list) and isinstance(sys_f, list) and len(sys_o) == len(sys_f) == 2:
            t.eq("arr.differing.orientation-shared", sys_f[0], sys_o[0])
            t.check("arr.differing.instructions-differ", sys_f[1] != sys_o[1], "family block identical")


def check_arrangement(t, sub, handle, family, p, limits):
    out = {}
    arr = sub.arrangement.get(handle)
    if not t.check(p + ".records", arr is not None, "arrangement records unavailable"):
        return out
    mb, rb = arr["machine"], arr["readable"]
    try:
        obj = strict_loads(mb)
    except StrictJSONError as exc:
        t.check(p + ".machine-strict-json", False, str(exc))
        return out
    members = obj if isinstance(obj, dict) and all(k in obj for k in ARRANGEMENT_MEMBERS) else (
        obj.get("body") if isinstance(obj, dict) and isinstance(obj.get("body"), dict) else obj)
    missing = [k for k in ARRANGEMENT_MEMBERS if not isinstance(members, dict) or k not in members]
    t.check(p + ".members", not missing, {"missing": missing})
    if not isinstance(members, dict):
        return out
    t.eq(p + ".model", members.get("model"), sub.model)
    sysv = members.get("system")
    expect_sys = expected_system_bytes(family)
    if isinstance(sysv, str):
        t.eq(p + ".system-bytes", sysv.encode("utf-8"), expect_sys)
        try:
            out["system_value"] = strict_loads(sysv)
        except StrictJSONError:
            out["system_value"] = None
    else:
        t.check(p + ".system-bytes", b'"system":' + expect_sys in mb, "exact system bytes are not pinned in arrangement.json")
        out["system_value"] = sysv
    out["system"] = out.get("system_value")
    tools = members.get("tools")
    if isinstance(tools, str):
        try:
            tools = strict_loads(tools)
        except StrictJSONError as exc:
            t.check(p + ".tools-json", False, str(exc))
            tools = None
    exp_tools = expected_tools(family)
    if isinstance(tools, list):
        t.eq(p + ".tool-names", [x.get("name") if isinstance(x, dict) else x for x in tools], [x["name"] for x in exp_tools])
        for e in exp_tools:
            g = next((x for x in tools if isinstance(x, dict) and x.get("name") == e["name"]), None)
            if g is None:
                continue
            t.check(p + ".tool-keys", set(g) == {"name", "description", "input_schema"}, {"tool": e["name"], "keys": list(g)})
            t.eq(p + ".tool-description.%s" % e["name"], g.get("description"), e["description"])
            t.eq(p + ".tool-schema.%s" % e["name"], g.get("input_schema"), e["input_schema"])
    else:
        t.check(p + ".tools", False, "tools is not an array: %r" % (type(tools),))
    out["tools"] = tools
    strings = [v for v in iter_values(members.get("texts")) if isinstance(v, str)]
    for label, text in (("reminder", REMINDER), ("near-limit", NEAR_LIMIT), ("continuation", CONTINUATION)):
        t.check(p + ".texts.%s" % label, text in strings, "pinned %s text missing" % label)
    for n in limits:
        t.check(p + ".limits", mentions(members.get("limits"), str(n)), {"limit": n, "limits": members.get("limits")})
    t.eq(p + ".near_limit_percent", members.get("near_limit_percent"), 20)
    t.eq(p + ".request_timeout_seconds", members.get("request_timeout_seconds"), 600)
    t.check(p + ".reader", mentions(members.get("reader"), "utf8-text/1"), members.get("reader"))
    t.check(p + ".renderer", mentions(members.get("renderer"), "stewart.render/1"), members.get("renderer"))
    t.check(p + ".family", mentions(members.get("family"), family), members.get("family"))
    t.check(p + ".bindings", contains_string(members.get("bindings"), sha256_hex(sub.body)), members.get("bindings"))
    readable = norm_ws(rb.decode("utf-8", "replace"))
    t.check(p + ".readable.orientation", norm_ws(ORIENTATION) in readable, "orientation text not in arrangement.md")
    t.check(p + ".readable.instructions", norm_ws(FAMILY_TEXT[family]) in readable, "family text not in arrangement.md")
    for e in exp_tools:
        t.check(p + ".readable.tools", e["name"] in readable, e["name"])
    for n in limits:
        t.check(p + ".readable.limits", str(n) in readable.replace(",", ""), n)
    t.check(p + ".readable.reader", "utf8-text/1" in readable, "reader")
    return out


@case("c19.settings", ["C19", "C20", "C11"], "each front matter setting at its bounds, just over them, and missing")
def c_settings(t):
    """Exact bounds complete; just-over and malformed values refuse setting_invalid; a
    missing required key refuses setting_missing; an absent or non-directory destination
    refuses destination_invalid. Refusals record no preparation."""
    sub = t.submission([F("a.txt", b"a\n")])
    t.new_ref(sub)
    qpath = os.path.join(sub.folder, "question.md")
    ok_model = "A" * 64 + "z9._:-" + "b" * 58
    good = [("model-128", dict(model=ok_model)), ("model-1", dict(model="m")),
            ("turns-1", dict(turns="1")), ("turns-10000", dict(turns="10000")),
            ("input-1", dict(input_tokens="1")), ("input-max", dict(input_tokens="2000000000")),
            ("output-1", dict(output_tokens="1")), ("output-max", dict(output_tokens="200000000")),
            ("inquiry-128", dict(inquiry="é" * 128)), ("varies", dict(varies=sub.ref)),
            ("family-framing", dict(family="inquiry-framing")), ("family-comparison", dict(family="comparison"))]
    bad = [("model-129", dict(model="m" * 129)), ("model-space", dict(model="claude opus")),
           ("model-nonascii", dict(model="café")), ("model-slash", dict(model="a/b")),
           ("turns-0", dict(turns="0")), ("turns-10001", dict(turns="10001")), ("turns-word", dict(turns="many")),
           ("turns-negative", dict(turns="-1")), ("turns-fraction", dict(turns="1.5")), ("turns-plus", dict(turns="+5")),
           ("input-0", dict(input_tokens="0")), ("input-over", dict(input_tokens="2000000001")),
           ("output-0", dict(output_tokens="0")), ("output-over", dict(output_tokens="200000001")),
           ("inquiry-129", dict(inquiry="i" * 129)), ("inquiry-control", dict(inquiry="bell\x07")),
           ("varies-not-reference", dict(varies="audit 12")), ("family-unknown", dict(family="survey")),
           ("destination-relative", dict(dest="returns")), ("destination-control", dict(dest=sub.dest + "\x01x")),
           ("destination-long", dict(dest="/" + "d" * 1024)),
           ("version", dict(extra_version=True))]
    for label, kw in good:
        t.edit(qpath, question_md(dest=sub.dest, **kw))
        t.prepare(sub, name="settings.%s" % label)
    for label, kw in bad:
        n = t.log_kinds(sub).count("prepared")
        if kw.pop("extra_version", False):
            q = question_md(dest=sub.dest).replace(b"stewart: question/1", b"stewart: question/2")
        else:
            kw.setdefault("dest", sub.dest)
            q = question_md(**kw)
        t.edit(qpath, q)
        t.prepare(sub, name="settings.%s" % label, expect="refused", reason="setting_invalid")
        t.eq("settings.%s.no-preparation" % label, t.log_kinds(sub).count("prepared"), n)
    for key in ("stewart", "family", "model", "destination", "limit-turns", "limit-input-tokens", "limit-output-tokens"):
        t.edit(qpath, question_md(dest=sub.dest, omit=(key,)))
        rep = t.prepare(sub, name="settings.missing-%s" % key, expect="refused", reason="setting_missing")
        t.check("settings.missing-%s.names-key" % key, key in json.dumps(rep.obj or {}), rep.obj)
    afile = os.path.join(t.root, "a file %d" % t.next_k())
    with open(afile, "wb") as f:
        f.write(b"x")
    for label, dest in (("absent", os.path.join(t.root, "no such returns")), ("file", afile)):
        t.edit(qpath, question_md(dest=dest))
        t.prepare(sub, name="settings.destination-%s" % label, expect="refused", reason="destination_invalid")
    long_dest = None
    if is_linux():
        path = t.mkdir("long %d" % t.next_k())
        while len(path.encode()) < 1024:
            left = 1024 - len(path.encode())       # bytes still to add, including the "/"
            n = min(200, left - 1)
            if left - 1 - n == 1:                  # never leave a single byte: "/" needs a name
                n -= 1
            path = path + "/" + "L" * n
        if len(path.encode()) == 1024:
            os.makedirs(path)
            long_dest = path
    if long_dest:
        t.watch(long_dest, "frozen", "1024-byte destination")
        t.edit(qpath, question_md(dest=long_dest))
        t.prepare(sub, name="settings.destination-1024")
    else:
        t.skip_part("1024-byte destination", "needs Linux PATH_MAX; macOS cannot create a 1,024-byte absolute path")


@case("c20.front-matter", ["C20", "C19", "C11"], "front matter is parsed strictly, naming the line",
      controls=[Control("accept_unknown_field", [r"^frontmatter\.unknown"])])
def c_front_matter(t):
    """Unknown, misspelled, uppercase and duplicate keys, missing or malformed delimiters,
    mixed line endings, a second BOM, an indented comment and malformed field lines all
    refuse; the unknown key names its line and the nearest key. Comments, empty lines,
    CRLF throughout and one BOM are admitted."""
    sub = t.submission([F("a.txt", b"a\n")])
    t.new_ref(sub)
    qpath = os.path.join(sub.folder, "question.md")
    d = sub.dest.encode()
    base = question_md(dest=sub.dest)

    def lines_of(q):
        return q.split(b"\n")

    def insert(q, line, at=3):
        ls = lines_of(q)
        return b"\n".join(ls[:at] + [line] + ls[at:])

    fm = "front_matter_invalid"
    loose = (fm, "setting_invalid")
    specimens = [
        ("unknown", insert(base, b"colour: blue", 3), (fm,), 4),
        ("unknown-typo", insert(base, b"modle: claude-opus-5-5", 3), (fm,), 4),
        ("unknown-uppercase", base.replace(b"model: ", b"Model: "), (fm,), None),
        ("duplicate", insert(base, b"model: claude-opus-5-5", 3), (fm,), None),
        ("no-opening", base[len(b"---\n"):], (fm,), None),
        ("no-closing", base.replace(b"\n---\n", b"\n"), (fm,), None),
        ("opening-trailing-space", b"--- " + base[3:], (fm,), None),
        ("crlf-then-lf", base.replace(b"\n", b"\r\n", 2), (fm,), None),
        ("lf-then-crlf", base.replace(b"model: claude-opus-5-5\n", b"model: claude-opus-5-5\r\n"), (fm, "setting_invalid"), None),
        ("two-boms", b"\xef\xbb\xbf\xef\xbb\xbf" + base, (fm,), None),
        ("indented-comment", insert(base, b" # indented", 3), loose, None),
        ("no-space", base.replace(b"model: claude", b"model:claude"), loose, None),
        ("two-spaces", base.replace(b"model: claude", b"model:  claude"), loose, None),
        ("trailing-space", base.replace(b"model: claude-opus-5-5", b"model: claude-opus-5-5 "), loose, None),
        ("empty-value", insert(base, b"inquiry: ", 3), loose, None),
        ("key-only", insert(base, b"inquiry", 3), loose, None),
    ]
    for label, q, reasons, line in specimens:
        t.edit(qpath, q)
        rep = t.prepare(sub, name="frontmatter.%s" % label, expect="refused", reason=reasons)
        if line is not None:
            text = json.dumps(rep.obj or {}, ensure_ascii=False)
            t.check("frontmatter.%s.names-line" % label, mentions(rep.data, str(line)) or re.search(r"\bline %d\b" % line, text),
                    rep.obj)
        if label == "unknown-typo":
            t.check("frontmatter.unknown-typo.nearest-key", "model" in json.dumps(rep.obj or {}), rep.obj)
    admitted = [("comments-everywhere", insert(insert(base, b"# a comment", 2), b"", 5)),
                ("crlf", base.replace(b"\n", b"\r\n")), ("bom", b"\xef\xbb\xbf" + base),
                ("bare", question_md(dest=sub.dest, comments=False))]
    for label, q in admitted:
        t.edit(qpath, q)
        t.prepare(sub, name="frontmatter.ok.%s" % label)


@case("c20.reference", ["C20", "C18"], "references are exact; malformed, unknown and foreign ones are refused")
def c_reference(t):
    """A root holding space, %, +, ~, #, @, : and non-ASCII is encoded byte for byte.
    Malformed references refuse reference_invalid; an unknown audit reference_unknown;
    a wrong store at a real root archive_replaced; an absent root archive_unavailable."""
    odd_parent = t.mkdir("odd %d" % t.next_k(), "a b%c+d~e#f@g:h ß文")
    sub = t.submission(basic_entries(), archive=os.path.join(odd_parent, "store"))
    t.new_ref(sub, name="ref.odd-root")
    t.eq("ref.encoding", sub.ref, make_reference(sub.audit, sub.store, sub.archive))
    t.check("ref.one-word", not re.search(r"\s", sub.ref), sub.ref)
    t.status(sub, name="ref.odd-root-status")
    a, s = sub.audit, sub.store
    enc = encode_root(sub.archive)
    t.require("ref.has-multibyte-escape", "%C3%9F" in enc, enc)
    r = lambda root, aa=a, ss=s: "stw1:%s:%s:%s" % (aa, ss, root)
    malformed = [
        ("empty", ""), ("prefix-only", "stw1"), ("prefix-colon", "stw1:"),
        ("other-version", "stw2:%s:%s:%s" % (a, s, enc)), ("uppercase-prefix", "STW1:%s:%s:%s" % (a, s, enc)),
        ("no-root", "stw1:%s:%s" % (a, s)), ("empty-root", r("")),
        ("uppercase-audit", r(enc, aa=a.upper())), ("short-audit", r(enc, aa=a[:-1])),
        ("audit-digit-0", r(enc, aa=a[:-1] + "0")), ("audit-digit-8", r(enc, aa=a[:-1] + "8")),
        ("swapped-ids", r(enc, aa=s, ss=a)), ("relative-root", r("relative/path")),
        ("dotdot-component", r(enc + "/../x")), ("dot-component", r(enc + "/./x")),
        ("empty-component", r(enc + "//x")), ("trailing-slash", r(enc + "/")),
        ("lowercase-escape", r(enc.replace("%C3%9F", "%c3%9f", 1))),
        ("unescaped-space", r(enc.replace("%20", " ", 1))), ("truncated-escape", r(enc + "%4")),
        ("escaped-safe-byte", r(enc.replace("store", "%73tore"))), ("raw-root", r(sub.archive)),
    ]
    for label, ref in malformed:
        rep = t.cmd(["status", ref], name="ref.malformed.%s" % label, expect="refused", reason="reference_invalid",
                    writer=None)
        t.eq("ref.malformed.%s.effects" % label, rep.effects, {})
    t.cmd(["prepare", malformed[3][1]], name="ref.malformed.prepare", expect="refused", reason="reference_invalid",
          writer=None)
    t.cmd(["status", make_reference(random_id("a"), s, sub.archive)], name="ref.unknown-audit", expect="refused",
          reason="reference_unknown", writer=None)
    t.cmd(["status", make_reference(a, random_id("s"), sub.archive)], name="ref.foreign-store", expect="refused",
          reason="archive_replaced", writer=None)
    t.cmd(["status", make_reference(a, s, os.path.join(t.root, "nowhere", "store"))], name="ref.absent-root",
          expect="refused", reason="archive_unavailable", writer=None)


@case("c20.handles", ["C20", "C11"], "handles bind store, audit, kind and object; crossed or constructed ones refuse")
def c_handles(t):
    """The returned handle's check is the 2.3 digest of its prepared record. Wrong checks,
    malformed forms, other kinds, handles from another audit or store and constructed
    objects refuse handle_invalid with acceptance absent and no capture."""
    root = t.archive_path()
    a = t.submission(basic_entries(), archive=root)
    b = t.submission(basic_entries(), archive=root)
    c = t.submission(basic_entries())
    for s, n in ((a, "a"), (b, "b"), (c, "c")):
        t.new_ref(s, name="handles.new-%s" % n)
        t.prepare(s, name="handles.prepare-%s" % n)
    t.require("handles.prepared", all(x.handles for x in (a, b, c)), [x.handles for x in (a, b, c)])
    h = a.handles[-1]
    obj, chk = h.split(".")
    wrong = obj + "." + chk[:-1] + ("b" if chk[-1] == "a" else "a")
    sums = [sha256_hex(r["raw"]) for r in t.read_log(a) if (r["obj"] or {}).get("kind") == "prepared"]
    t.require("handles.prepared-record", len(sums) == 1, len(sums))
    candidates = [
        ("wrong-check", wrong), ("no-check", obj), ("empty-check", obj + "."), ("uppercase", h.upper()),
        ("short-check", h[:-1]), ("zero", "mp0." + chk), ("leading-zero", "mp0" + obj[2:] + "." + chk),
        ("seal-kind", "seal." + handle_check(a.store, a.audit, "seal", "seal", [sums[0]])),
        ("ap-kind", "ap1." + handle_check(a.store, a.audit, "ap", "ap1", [sums[0]])),
        ("mp-check-as-ap", "ap" + obj[2:] + "." + chk),
        ("entry-kind", "e1.v1." + handle_check(a.store, a.audit, "entry", "e1.v1", [sums[0]])),
        ("other-audit", b.handles[-1]), ("other-store", c.handles[-1]),
        ("constructed-next", "mp9." + handle_check(a.store, a.audit, "mp", "mp9", [sha256_hex(b"no such record")])),
        ("kind-confusion", obj + "." + handle_check(a.store, a.audit, "ap", obj, sums)),
    ]
    for label, cand in candidates:
        if cand == h:
            continue
        rep = t.commission(a, cand, name="handles.%s" % label, expect="refused", reason="handle_invalid")
        t.eq("handles.%s.effects" % label, no_diag(rep.effects), {"acceptance": "absent", "attempt": "none"})
    t.eq("handles.no-intake", t.intake_dirs(a), [])
    t.commission(a, h, name="handles.genuine")


@case("c20.cli-usage", ["C20", "C9"], "unparseable arguments exit 2 and begin no operation")
def c_cli_usage(t):
    """Unknown commands and flags, abbreviations, missing and extra operands exit 2 and
    leave the archive exactly as it was."""
    sub = t.submission(basic_entries())
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    cases_ = [("no-command", []), ("unknown-command", ["frobnicate"]), ("prepare-no-ref", ["prepare"]),
              ("prepare-extra", ["prepare", sub.ref, "extra"]), ("abbrev-json", ["status", sub.ref, "--jso"]),
              ("unknown-flag", ["status", sub.ref, "--verbose"]), ("status-both", ["status", sub.ref, "--archive", sub.archive]),
              ("new-no-folder", ["new"]), ("commission-no-handle", ["commission", sub.ref]),
              ("read-no-item", ["receipt", sub.ref, "--read"]), ("abbrev-archive", ["new", sub.folder, "--arch", sub.archive]),
              ("close-confirm-missing", ["close", sub.ref, "--confirm"]), ("help-extra", ["help", "commands", "extra"])]
    for label, args in cases_:
        r = t.cmd(args, op="usage", json_reply=False, envelope=False, name="usage.%s" % label)
        t.eq("usage.%s.exit" % label, r.rc, 2)
    t.eq("usage.no-intake", t.intake_dirs(sub), [])
    t.eq("usage.log", t.log_kinds(sub), ["reference", "prepared"])


@case("c20.records-strict", ["C20", "C17", "C6"], "archive records are decoded strictly; whitespace alone is not damage",
      controls=[Control("unknown_as_absent", [r"^records\."])])
def c_records_strict(t):
    """The accepted record is replaced by variants: duplicate key, escape-equivalent
    duplicate, unknown header key, BOM, trailing data, invalid UTF-8, NUL escape and
    lone surrogate each make status acceptance_uncertain and commission refuse
    log_damaged. The same record re-spaced (whitespace only) keeps accepted: yes. The
    original bytes are restored between specimens."""
    sub = t.submission(basic_entries())
    h, _ = t.accept(sub)
    recs = t.read_log(sub)
    rec = recs[-1]
    t.require("records.last-is-accepted", (rec["obj"] or {}).get("kind") == "accepted", [r["name"] for r in recs])
    path = os.path.join(sub.audit_dir, "log", rec["name"])
    raw = rec["raw"]
    core = raw.rstrip(b" \t\r\n")
    t.require("records.object", core.endswith(b"}"), raw[-20:])
    head = core[:-1]
    t.tampered_logs.add(sub.audit)
    variants = [("duplicate-key", head + b',"kind":"accepted"}'),
                ("escaped-duplicate", head + b',"\\u006bind":"accepted"}'),
                ("unknown-key", head + b',"extra":1}'),
                ("bom", b"\xef\xbb\xbf" + raw),
                ("trailing-data", core + b"x"),
                ("invalid-utf8", core.replace(b'"at":"', b'"at":"\xff', 1)),
                ("nul-escape", core.replace(b'"kind":"accepted"', b'"kind":"accepted\\u0000"', 1)),
                ("lone-surrogate", core.replace(b'"at":"', b'"at":"\\ud800', 1))]
    for label, data in variants:
        if data in (raw, core):
            t.skip_part(label, "variant could not be constructed from the record bytes")
            continue
        t.edit(path, data, "replace the accepted record: %s" % label)
        st = t.status(sub, name="records.%s.status" % label)
        t.eq("records.%s.condition" % label, st.data.get("condition"), "acceptance_uncertain")
        t.eq("records.%s.accepted" % label, (st.data.get("headline") or {}).get("accepted"), "unknown")
        rep = t.commission(sub, h, name="records.%s.commission" % label, expect="refused", reason="log_damaged")
        t.eq("records.%s.acceptance" % label, rep.effects.get("acceptance"), "unknown")
    spaced = json.dumps(rec["obj"], ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    t.edit(path, spaced, "re-space the accepted record")
    st = t.status(sub, name="records.whitespace.status")
    t.eq("records.whitespace.accepted", (st.data.get("headline") or {}).get("accepted"), "yes")
    t.edit(path, raw, "restore the accepted record")
    st = t.status(sub, name="records.restored.status")
    t.check_status(st, sub, "records.restored", condition="not_started", accepted="yes", next_cmds=("run", "close"))


@case("c20.envelope-refusals", ["C20", "C9"], "every refusal carries reason, message, effects and next",
      controls=[Control("omit_effects_on_refusal", [r"^envelope\.effects"])])
def c_envelope_refusals(t):
    """A set of refusals from every pre-launch command, each checked against the
    envelope rules (effects present with the operation's keys, retained, next)."""
    sub = t.submission(basic_entries(), make_materials=False)
    t.new_ref(sub)
    t.cmd(["new", t.folder_path()], name="refusals.new", expect="refused", reason="archive_unspecified")
    t.cmd(["status", "stw1:bad"], name="refusals.status", expect="refused", reason="reference_invalid", writer=None)
    t.cmd(["receipt", sub.ref], name="refusals.receipt", expect="refused", reason="not_accepted")
    t.prepare(sub, name="refusals.prepare", expect="refused", reason="folder_incomplete")
    t.cmd(["commission", sub.ref, "mp1.aaaaaa", "--i-am-finished"], name="refusals.commission", expect="refused",
          reason="handle_invalid")
    t.cmd(["commission", sub.ref, "mp1.aaaaaa"], name="refusals.commission-flag", expect="refused",
          reason=("affirmation_missing", "handle_invalid"))


# ---------------------------------------------------------------------------
# C19 bounds (and C9 timings at the size limits).
# ---------------------------------------------------------------------------

def _bound_refused(t, rep, p, bound, entry=None):
    ok_bound, ok_limit, ok_entry = names_bound(rep, bound, BOUNDS[bound], entry)
    t.check(p + ".names-bound", ok_bound, rep.obj)
    t.check(p + ".names-limit", ok_limit, rep.obj)
    if entry:
        t.check(p + ".names-entry", ok_entry, rep.obj)


@case("c19.bounds.question", ["C19"], "question.md at exactly 256 KiB is admitted; one byte more is refused")
def c_bound_question(t):
    """Exact question bytes 262,144 complete and commission; 262,145 refuse
    bound_exceeded naming question_bytes, the limit and question.md."""
    dest = t.dest_path()
    head = question_md(b"", dest=dest)
    body = (b"q" * 99 + b"\n") * ((BOUNDS["question_bytes"] - len(head)) // 100)
    body += b"z" * (BOUNDS["question_bytes"] - len(head) - len(body))
    q = head + body
    t.require("bound-q.exact-size", len(q) == BOUNDS["question_bytes"], len(q))
    sub = t.submission([F("a.txt", b"a\n")], question=q, dest=dest)
    t.accept(sub, prefix="bound-q.exact.", check_witness=True)
    t.check_readback_ok(sub, "question-file", q, "bound-q.readback")
    over = t.submission([F("a.txt", b"a\n")], question=q + b"!", dest=t.dest_path())
    t.new_ref(over, name="bound-q.over.new")
    rep = t.prepare(over, name="bound-q.over", expect="refused", reason="bound_exceeded")
    _bound_refused(t, rep, "bound-q.over", "question_bytes", "question.md")


@case("c19.bounds.files", ["C19"], "128 material files are admitted; 129 are refused")
def c_bound_files(t):
    """Exactly 128 files (some nested) prepare and commission; a 129th refuses
    bound_exceeded naming files and 128."""
    entries = [F("f%03d.txt" % i if i % 3 else "sub/f%03d.txt" % i, b"%d\n" % i) for i in range(128)]
    sub = t.submission(entries)
    t.accept(sub, prefix="bound-files.exact.", check_witness=True)
    over = t.submission(entries + [F("one-more.txt", b"x\n")])
    t.new_ref(over, name="bound-files.over.new")
    rep = t.prepare(over, name="bound-files.over", expect="refused", reason="bound_exceeded")
    _bound_refused(t, rep, "bound-files.over", "files")


@case("c19.bounds.directories", ["C19"], "256 directories including materials/ are admitted; 257 are refused")
def c_bound_dirs(t):
    """255 subdirectories (256 with materials/), mostly empty, prepare and commission with
    every directory listed; one more refuses bound_exceeded naming directories."""
    entries = [D("d%03d" % i) for i in range(251)] + [D("n/a/b/c")] + [F("n/a/file.txt", b"f\n")]
    sub = t.submission(entries)
    t.require("bound-dirs.count", len(sub.dirs) + 1 == BOUNDS["directories"], len(sub.dirs) + 1)
    t.accept(sub, prefix="bound-dirs.exact.", check_witness=True)
    over = t.submission(entries + [D("one-more")])
    t.new_ref(over, name="bound-dirs.over.new")
    rep = t.prepare(over, name="bound-dirs.over", expect="refused", reason="bound_exceeded")
    _bound_refused(t, rep, "bound-dirs.over", "directories")


@case("c19.bounds.paths", ["C19"], "path bytes, components and component length at and just over their bounds")
def c_bound_paths(t):
    """A 1,024-byte public name, 32 components and a 255-byte component are admitted and
    read back; 1,025 bytes and 33 components refuse bound_exceeded naming the bound.
    A 256-byte component is tested only where the filesystem can hold one."""
    p1024 = "/".join(["a" * 200] * 4 + ["f" * 220])
    p1025 = "/".join(["b" * 200] * 4 + ["g" * 221])
    c32 = "/".join(["c"] * 31 + ["leaf.txt"])
    c33 = "/".join(["e"] * 32 + ["leaf.txt"])
    comp255 = "k" * 251 + ".txt"
    t.require("bound-paths.sizes", len(p1024.encode()) == 1024 and len(p1025.encode()) == 1025
              and len(c32.split("/")) == 32 and len(c33.split("/")) == 33 and len(comp255) == 255, "specimen sizes")
    sub = t.submission([F(p1024, b"long path\n"), F(c32, b"deep\n"), F(comp255, b"long name\n")])
    t.accept(sub, prefix="bound-paths.exact.", check_witness=True)
    for name in (p1024, c32, comp255):
        t.check_readback_ok(sub, "materials/" + name, sub.items()["materials/" + name], "bound-paths.readback")
    for label, name, bound in (("bytes", p1025, "path_bytes"), ("components", c33, "path_components")):
        over = t.submission([F(name, b"over\n")])
        t.new_ref(over, name="bound-paths.%s.new" % label)
        rep = t.prepare(over, name="bound-paths.%s" % label, expect="refused", reason="bound_exceeded")
        _bound_refused(t, rep, "bound-paths.%s" % label, bound)
    if _probe_names(t, [b"m" * 256]):
        over = t.submission([F("m" * 256, b"x\n")])
        t.new_ref(over, name="bound-paths.component.new")
        rep = t.prepare(over, name="bound-paths.component", expect="refused", reason="bound_exceeded")
        _bound_refused(t, rep, "bound-paths.component", "component_bytes")
    else:
        t.skip_part("256-byte component", "the filesystem's NAME_MAX is 255, so no such entry can exist")


@case("c19.bounds.file-bytes", ["C19", "C9", "C15"], "a 16 MiB file is admitted, captured and read back; one byte more is refused",
      heavy=True)
def c_bound_file_bytes(t):
    """A material of exactly 16,777,216 bytes prepares and commissions (progress on
    stderr) and reads back with its digest and size; 16,777,217 bytes refuse
    bound_exceeded naming file_bytes and the file."""
    size = BOUNDS["file_bytes"]
    sub = t.submission([BIG("big.txt", size, "file-bound"), F("small.txt", b"s\n")])
    t.new_ref(sub)
    rep = t.prepare(sub, name="bound-file.exact.prepare", timeout=600)
    t.check_prepare_witness(rep, sub, "bound-file.exact.prepare")
    t.check("progress.prepare", rep.stderr.strip() != b"", "prepare reported no scope or progress on stderr")
    rep = t.commission(sub, sub.handles[-1], name="bound-file.exact.commission", timeout=600)
    t.check("progress.commission", rep.stderr.strip() != b"", "commission reported no size or progress on stderr")
    t.check_readback_ok(sub, "materials/big.txt", sub.items()["materials/big.txt"], "bound-file.readback")
    t.status(sub, name="status-at-file-bound")
    over = t.submission([BIG("big.txt", size + 1, "file-bound-over")])
    t.new_ref(over, name="bound-file.over.new")
    rep = t.prepare(over, name="bound-file.over", expect="refused", reason="bound_exceeded", timeout=600)
    _bound_refused(t, rep, "bound-file.over", "file_bytes", "big.txt")


@case("c19.bounds.total-bytes", ["C19", "C9"], "128 MiB of question and materials is admitted; one byte more is refused",
      heavy=True)
def c_bound_total(t):
    """Question plus materials of exactly 134,217,728 bytes prepare and commission, and
    status on that archive is timed; one byte more refuses bound_exceeded naming
    total_bytes."""
    dest = t.dest_path()
    q = question_md(dest=dest)
    fb = BOUNDS["file_bytes"]
    rest = BOUNDS["total_bytes"] - 7 * fb - len(q)
    entries = [BIG("part%d.txt" % i, fb, "total-%d" % i) for i in range(7)] + [BIG("last.txt", rest, "total-last")]
    sub = t.submission(entries, question=q, dest=dest)
    t.new_ref(sub)
    rep = t.prepare(sub, name="bound-total.exact.prepare", timeout=900)
    t.check_prepare_witness(rep, sub, "bound-total.exact.prepare")
    t.commission(sub, sub.handles[-1], name="bound-total.exact.commission", timeout=900)
    for i in range(3):
        t.status(sub, name="status-at-total-bound-%d" % i)
    dest2 = t.dest_path()
    q2 = question_md(dest=dest2)
    rest2 = BOUNDS["total_bytes"] - 7 * fb - len(q2) + 1
    entries2 = entries[:-1] + [BIG("last.txt", rest2, "total-last")]
    t.require("bound-total.over-size", len(q2) + 7 * fb + rest2 == BOUNDS["total_bytes"] + 1, rest2)
    over = t.submission(entries2, question=q2, dest=dest2)
    t.new_ref(over, name="bound-total.over.new")
    rep = t.prepare(over, name="bound-total.over", expect="refused", reason="bound_exceeded", timeout=900)
    _bound_refused(t, rep, "bound-total.over", "total_bytes")


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
        self.work = os.path.realpath(tempfile.mkdtemp(prefix="stewart-step3-", dir=work_parent))
        if (self.work + os.sep).startswith(repo + os.sep) and os.path.isdir(os.path.join(repo, "service")):
            _rmtree(self.work)
            raise SystemExit("refusing: the work directory %s is inside the repository %s; use --work" % (self.work, repo))
        if (os.path.realpath(self.evidence) + os.sep).startswith(self.work + os.sep):
            raise SystemExit("refusing: the evidence folder is inside the work directory")
        os.makedirs(self.evidence)
        self.release = self.install(args.binary, "release", "stewart")
        self.test = self.install(args.test_binary, "test", "stewart-test")

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
        return table, gate

    def run(self):
        selected = self.select()
        platform_info = {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
                         "python": sys.version, "euid": os.geteuid(), "work": self.work,
                         "work_filesystem": fs_type_of(self.work), "linux": is_linux()}
        start = {"schema": DRIVER_SCHEMA, "started_at": self.started_at, "argv": sys.argv,
                 "platform": platform_info, "binaries": {"release": self.release, "test": self.test},
                 "selected": [s.id for s in selected], "timing_gate": self.gate}
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
        lines = ["# Stewart step 3 driver results", "",
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
                  "- Driver controls: %(total)d, fired %(fired)d." % c["driver_controls"], ""]
        g = r["timing_gate"]
        lines += ["## Timing gate (C9)", "", "%s. Threshold %d ms over %s; %d samples; worst %s ms; passed %s." % (
            g["note"], g["threshold_ms"], ", ".join(g["ops"]), g["samples"],
            "-" if g["worst_ms"] is None else "%.1f" % g["worst_ms"], g["passed"]), ""]
        lines += ["| Operation/binary | n | median ms | p95 ms | max ms |", "| --- | --- | --- | --- | --- |"]
        for k, s in r["timings"].items():
            if s:
                lines.append("| %s | %d | %.1f | %.1f | %.1f |" % (k, s["n"], s["median_ms"], s["p95_ms"], s["max_ms"]))
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
    ok("split.body-delimiter", split_question(POPULATION_BODY.join([b"---\nk: v\n---\n", b""])) == POPULATION_BODY)
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
    bad = [r for r in results if not r[1]]
    for name, good, detail in results:
        sys.stdout.write("%s %s%s\n" % ("ok  " if good else "FAIL", name, (" (%s)" % detail) if (detail and not good) else ""))
    sys.stdout.write("self-test: %d checks, %d failed\n" % (len(results), len(bad)))
    return 1 if bad else 0


# ---------------------------------------------------------------------------
# Command line.
# ---------------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="stewart_driver.py",
        description="Independent black-box acceptance driver for Stewart step 3 (manager foundation). "
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


if __name__ == "__main__":
    sys.exit(main())
