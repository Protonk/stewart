"""Auditor declarations: one byte parser and explicit identity comparisons.

Completion and report kind are attributed claims, never execution observations
or verdicts. A kind requests manager attention, not permission to widen scope.
The auditor helper reads checkout identity and prompt bytes only; handoff values
are required inputs, never reconstructed from a private session. Import and
parser construction perform no filesystem or Git work.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import uuid

from stewart import _util as _hash
from stewart._bootstrap import StewartError, combined_code, open_directory, read_regular, write_exclusive
from stewart._git import COMMIT_ID, git, git_text
from stewart._json import DuplicateKey, loads_control
from stewart.assignment import audit_id, prompt_metadata
from stewart.workspace import Workspace, contained, workspace

SCHEMA_VERSION = 2
FENCE = b"```audit-report"
COMPLETIONS = ("partial", "complete", "blocked")
REPORT_KINDS = ("answer", "needs-evidence", "reframe")
IDENTITIES = ("audit_id", "target_commit", "launch_prompt_commit", "prompt_sha256",
              "launch_token", "observed_checkout_commit")
FIELDS = frozenset(("schema_version", "completion", "report_kind", *IDENTITIES))


def _refuse(reason: str, field: str, expected: object, observed: object,
            step: str = "correct the declaration and run check", *, retained=()) -> StewartError:
    return StewartError(f"{field} expected {expected!r}, observed {observed!r}.",
                        reason=reason, retained=retained, next_steps=[step])


def _parse(data: bytes) -> tuple[dict, int, int]:
    """Return the declaration and its exact byte span; prose is never rewritten.

    Fences are unindented triple backticks, LF terminated, without trailing
    spaces. Other fenced code is tracked to reject a nested declaration rather
    than accidentally treating an example as the auditor's claim.
    """
    if data.startswith(b"\xef\xbb\xbf"):
        raise _refuse("byte_order_mark", "report", "no UTF-8 BOM", "BOM")
    offset = 0
    outer = None
    start = payload_start = end = None
    spans = []
    for line in data.splitlines(keepends=True):
        raw = line.rstrip(b"\r\n")
        marker = re.match(rb"^[ \t]*(`{3,}|~{3,})(.*)$", raw)
        candidate = marker and marker[2].strip().startswith(b"audit-report")
        if candidate:
            if start is not None or spans:
                raise _refuse("duplicate_blocks", "report", "one declaration", "multiple blocks")
            if outer is not None:
                raise _refuse("nested_block", "declaration", "top-level fence", "nested fence")
            if line.endswith(b"\r\n"):
                raise _refuse("crlf", "declaration fence", "LF", "CRLF")
            if raw == FENCE + b" " or (raw.startswith(FENCE) and raw[len(FENCE):].strip() == b"" and raw != FENCE):
                raise _refuse("fence_trailing_space", "declaration fence", "no trailing whitespace", raw)
            if raw != FENCE or not line.endswith(b"\n"):
                raise _refuse("malformed_fence", "declaration fence", FENCE, raw)
            start, payload_start = offset, offset + len(line)
        elif start is not None:
            if b"\r" in line:
                raise _refuse("crlf", "declaration", "LF", "CR line ending")
            if marker:
                if raw.rstrip(b" \t") == b"```" and raw != b"```":
                    raise _refuse("fence_trailing_space", "closing fence", "no trailing whitespace", raw)
                if raw != b"```":
                    raise _refuse("malformed_fence", "closing fence", b"```", raw)
                end = offset + len(raw)
                spans.append((start, payload_start, offset, end))
                start = None
        elif marker:
            marks, suffix = marker.groups()
            if outer is None:
                outer = marks
            elif marks[:1] == outer[:1] and len(marks) >= len(outer) and not suffix.strip():
                outer = None
        offset += len(line)
    if start is not None:
        raise _refuse("unterminated_block", "declaration", "closing fence", "end of report")
    if not spans:
        raise _refuse("missing", "report", "one declaration", "no declaration",
                      "add the declaration manually using the issued handoff values, then run check")
    start, payload_start, payload_end, end = spans[0]
    try:
        value = loads_control(data[payload_start:payload_end].decode("utf-8"))
    except DuplicateKey as exc:
        raise _refuse("duplicate_key", exc.key, "one key", "duplicate key") from exc
    except (ValueError, RecursionError) as exc:
        raise _refuse("invalid_json", "declaration", "UTF-8 JSON object", str(exc)) from exc
    if not isinstance(value, dict):
        raise _refuse("non_object", "declaration", "JSON object", type(value).__name__)
    if "schema_version" in value and (type(value["schema_version"]) is not int
                                      or value["schema_version"] != SCHEMA_VERSION):
        raise _refuse("schema_version", "schema_version", SCHEMA_VERSION, value["schema_version"],
                      "preserve the report and use the tool version that issued its handoff; do not relabel old declarations")
    if set(value) - FIELDS:
        raise _refuse("unknown_field", "declaration fields", sorted(FIELDS), sorted(value))
    if FIELDS - set(value):
        raise _refuse("missing_field", "declaration fields", sorted(FIELDS), sorted(value))
    for field in IDENTITIES:
        if not isinstance(value[field], str) or not value[field]:
            raise _refuse("field_type", field, "nonempty string", value[field])
    try:
        audit_id(value["audit_id"])
    except StewartError as exc:
        raise _refuse("audit_id_format", "audit_id", "assignment audit ID", value["audit_id"]) from exc
    for field in ("target_commit", "launch_prompt_commit", "observed_checkout_commit"):
        if not COMMIT_ID.fullmatch(value[field]):
            raise _refuse("commit_format", field, "full lowercase commit ID", value[field])
    for field, width in (("prompt_sha256", 64), ("launch_token", 16)):
        if not re.fullmatch(rf"[0-9a-f]{{{width}}}", value[field]):
            raise _refuse("identity_format", field, f"{width} lowercase hex characters", value[field])
    if value["completion"] not in COMPLETIONS:
        raise _refuse("completion", "completion", COMPLETIONS, value["completion"])
    if value["report_kind"] is not None and value["report_kind"] not in REPORT_KINDS:
        raise _refuse("report_kind", "report_kind", [None, *REPORT_KINDS], value["report_kind"])
    if value["completion"] == "complete" and value["report_kind"] is None:
        raise _refuse("report_kind_required", "complete report_kind", REPORT_KINDS, None,
                      "select --report-kind answer, needs-evidence, or reframe when setting completion; "
                      "if the declaration was manually edited, correct its report_kind and run check")
    return value, start, end


def validate_report_declaration(data: bytes, *, expected: dict, sources: dict) -> dict:
    """Pure validation with explicit expectations and field-by-field provenance.

    Returns valid, missing, invalid, or mismatch plus diagnostics; never infers
    completion from prose. No writes or output. Callers decide whether an invalid
    result refuses an operation or records a custody gap after capture.
    """
    try:
        declaration, _, _ = _parse(data)
    except StewartError as exc:
        return {"status": "missing" if exc.reason == "missing" else "invalid", "declaration": None,
                "comparisons": {}, "diagnostics": [exc.to_json()]}
    comparisons = {}
    diagnostics = []
    for field, wanted in expected.items():
        observed = declaration[field]
        comparisons[field] = {"expected": wanted, "observed": observed, "source": sources[field],
                              "matches": wanted == observed}
        if observed != wanted:
            error = _refuse("identity_mismatch", field, wanted, observed).to_json()
            diagnostics.append({**error, "field": field})
    return {"status": "mismatch" if diagnostics else "valid", "declaration": declaration,
            "comparisons": comparisons, "diagnostics": diagnostics}


def session_declaration_expectations(record: dict, collected_head: str | None) -> tuple[dict, dict]:
    """Session-pinned identities and the separately observed collection HEAD."""
    expected = {"audit_id": record["assignment"]["audit_id"], "target_commit": record["target_commit"],
                "launch_prompt_commit": record["prompt_commit"], "prompt_sha256": record["prompt_sha256"],
                "launch_token": record["launch_token"]}
    sources = {field: "pinned session" for field in expected}
    if collected_head is not None:
        expected["observed_checkout_commit"] = collected_head
        sources["observed_checkout_commit"] = "HEAD observed at collection"
    return expected, sources


def _require_valid(result: dict) -> dict:
    if result["status"] != "valid":
        error = result["diagnostics"][0]
        raise StewartError(error["message"], reason=error["reason"], retained=error["retained"],
                           next_steps=error["next_steps"])
    return result["declaration"]


def auditor_context(ws: Workspace, *, expected_worktree: Path, launch_prompt_commit: str,
             prompt_sha256: str, launch_token: str) -> tuple[Path, dict, dict, str]:
    """Shared checkout/prompt binding for narrow auditor helpers; no report read or session access.

    Returns the report path, the expected identities and their sources, and the
    checkout's verified Git administration: callers ask every later question of
    that administration, and a revalidation compares it too.
    """
    from stewart._repository import checkout_git
    if not Path(expected_worktree).is_absolute():
        raise _refuse("expected_worktree", "--expected-worktree", "absolute handoff path", str(expected_worktree))
    actual = Path(git_text(ws.repo, "rev-parse", "--show-toplevel")).resolve()
    expected_root = Path(expected_worktree).resolve()
    if actual != expected_root:
        raise _refuse("checkout_root", "repository root", str(expected_root), str(actual),
                      "run the issued command in the prepared checkout")
    handoff = issued_handoff(ws, actual)
    git_admin = _own_administration(actual, handoff)
    options = checkout_git(actual, git_admin)
    if handoff is not None:
        for field, value in (("launch_prompt_commit", launch_prompt_commit), ("prompt_sha256", prompt_sha256),
                             ("launch_token", launch_token)):
            if value != handoff[1][field]:
                raise _refuse("handoff_identity", f"--{field.replace('_', '-')}", handoff[1][field], value,
                              "copy the issued command from the handoff exactly")
    symbolic = git(actual, *options, "symbolic-ref", "-q", "HEAD", check=False)
    if symbolic.returncode != 1:
        raise _refuse("checkout_detached", "HEAD", "detached", symbolic.stdout.decode(errors="replace"),
                      f"detach HEAD with `git checkout --detach {launch_prompt_commit}`; run check for anything else")
    head = git_text(actual, *options, "rev-parse", "HEAD")
    if head != launch_prompt_commit:
        raise _refuse("checkout_commit", "HEAD", launch_prompt_commit, head,
                      "run check: it names the fix and what to say in the report")
    prompt = git(actual, *options, "show", f"{launch_prompt_commit}:{ws.prompt}").stdout
    digest = _hash.sha256_bytes(prompt)
    if digest != prompt_sha256:
        raise _refuse("prompt_digest", "committed prompt SHA-256", prompt_sha256, digest,
                      "compare the command with the issued handoff and report the mismatch")
    prompt_path = contained(actual, ws.prompt)
    info, working = read_regular(prompt_path)
    if working != prompt:
        raise _refuse("prompt_drift", str(prompt_path), digest, info.get("sha256", info["kind"]),
                      f"restore the prompt with {restore_command(launch_prompt_commit, ws.prompt)}; "
                      "run check for anything else")
    meta = prompt_metadata(prompt.decode("utf-8"), ws)
    expected = {"audit_id": meta["audit_id"], "target_commit": meta["target_commit"],
                "launch_prompt_commit": launch_prompt_commit, "prompt_sha256": prompt_sha256,
                "launch_token": launch_token, "observed_checkout_commit": head}
    sources = {"audit_id": "committed prompt assignment", "target_commit": "committed prompt assignment",
               "launch_prompt_commit": "handoff argument checked against local HEAD",
               "prompt_sha256": "handoff argument checked against committed prompt bytes",
               "launch_token": "handoff argument; only Stewart can verify the issued value",
               "observed_checkout_commit": "local HEAD observed by helper"}
    return contained(actual, meta["report_path"]), expected, sources, git_admin


#: Identity lines in the issued handoff, rendered by preparation from the
#: session record. The auditor's check reads them as its source of truth.
HANDOFF_IDENTITY_LINES = {
    "launch_prompt_commit": "Prompt and checkout commit: `",
    "target_commit": "Audited target commit: `",
    "prompt_sha256": "Prompt SHA-256: `",
    "launch_token": "Launch token: `",
    "handoff_name": "Handoff file: `",
}
HANDOFF_DIRECTORY = ".stewart-handoffs"
HANDOFF_NAME = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.md")


def _own_administration(root: Path, handoff: tuple[str, dict] | None) -> str:
    """The checkout's own Git administration, verified as collection verifies it, or a refusal.

    The auditor's scope cannot read the role marker, so the session lifetime is
    taken from the administration's lock, and only when the issued handoff
    names the session. Collection binds the lifetime through the marker too.
    """
    from stewart._repository import checkout_git_admin
    common = git_text(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    lifetime = handoff[1]["handoff_name"].removesuffix(".md") if handoff is not None else None
    try:
        return checkout_git_admin(root, common, lifetime, marker=False)
    except StewartError as exc:
        raise _refuse("checkout_git_file", ".git", "this checkout's own gitdir file", str(exc),
                      "restore the checkout's own .git; Git is not run through anything else") from exc


def issued_handoff(ws: Workspace, root: Path) -> tuple[str, dict] | None:
    """The one issued handoff file and the session-pinned identities it names.

    Returns its repo-relative path and identities, or None when the handoff is
    absent, ambiguous or unreadable: then no identity can be confirmed against
    preparation, and the check says so.
    """
    folder = f"{ws.rel}/{HANDOFF_DIRECTORY}"
    issued = []
    try:
        with open_directory(contained(root, folder)) as directory:
            # Preparation names the handoff by its session UUID and the handoff
            # states that name, so a copy or a renamed handoff is not it;
            # anything else in the directory is an ordinary unexpected path.
            for name in sorted(os.listdir(directory)):
                if not HANDOFF_NAME.fullmatch(name):
                    continue
                _, data = read_regular(Path(name), dir_fd=directory)
                found = _handoff_identities(data)
                if found is not None and found["handoff_name"] == name:
                    issued.append((name, found))
    except (OSError, StewartError):
        return None
    if len(issued) != 1:
        return None
    return f"{folder}/{issued[0][0]}", issued[0][1]


def _handoff_identities(data: bytes | None) -> dict | None:
    if data is None:
        return None
    found = {}
    for line in data.decode("utf-8", errors="replace").splitlines():
        for field, prefix in HANDOFF_IDENTITY_LINES.items():
            if line.startswith(prefix) and field not in found:
                found[field] = line[len(prefix):].split("`", 1)[0]
    return found if set(found) == set(HANDOFF_IDENTITY_LINES) else None


UNREPAIRABLE_TEXT = "not yours to repair: describe it in the report, declare, and stop"
#: What the auditor can do about each checkout-attributable gap family. Fixes
#: for files write only the working tree, because the qualified harness denies
#: writes to Git administration, where the checkout's index lives. Moving HEAD
#: back or unstaging needs the same kind of Git write that made the change.
FIXES = {
    "report_": "write the report at the assigned path as a regular file, then run start or set",
    "checkout_commit_changed": "restore HEAD with `git reset --soft {prompt_commit}` (your changes stay in the "
                               "working tree), mention the commit in the report, then run set again",
    "unexpected_path:": "move this file under a declared scratch path; keep failed work rather than deleting it",
    "supplemental_missing:": UNREPAIRABLE_TEXT,
    "declaration_missing": "run the issued start command, or set if the report already exists",
    "declaration_invalid:": "repair the declaration block by rerunning the issued set command",
    "declaration_mismatch:": "rerun the issued set command exactly as the handoff prints it",
    "declaration_stale": "run the issued set command again so the declaration names the current HEAD",
    "omitted:": "make this entry a readable regular file or link, or remove it",
    "unreadable:": "make this entry readable, or remove it",
    "unsupported:": "remove this special entry; it cannot be captured",
    "boundary:": "remove this nested Git directory; its contents cannot be captured",
    "gitlink_contents:": "move these files under a declared scratch path: Stewart does not populate or audit "
                         "submodules; if the question needs this code, report needs-evidence",
    "collection_error:": "fix the named problem with the report path",
    "command_mismatch:": "copy the issued command from the handoff exactly",
}
#: Gaps the auditor cannot repair: describe them in the report and stop.
UNREPAIRABLE = UNREPAIRABLE_TEXT


def restore_command(prompt_commit: str, rel: str) -> str:
    """Restore one committed file's bytes without writing Git's index."""
    return f"`git show {prompt_commit}:{shlex.quote(rel)} > {shlex.quote(rel)}`"


def _fix(gap: dict, prompt_commit: str, tracked: set[str], staged: set[str]) -> str:
    if gap["code"] == 3:
        return UNREPAIRABLE
    rel = gap["id"].partition(":")[2]
    fix = "inspect and correct this entry"
    for prefix, text in FIXES.items():
        if gap["id"].startswith(prefix):
            fix = text.format(prompt_commit=prompt_commit)
            break
    if gap["id"].startswith("unexpected_path:"):
        if rel in tracked:
            fix = f"restore it with {restore_command(prompt_commit, rel)}"
        if rel in staged:
            # A staged change stays reported until the index matches again.
            fix = f"unstage it with `git reset -q {prompt_commit} -- {shlex.quote(rel)}`, then {fix}"
    return fix


def check_checkout(ws: Workspace, *, expected_worktree: Path, launch_prompt_commit: str,
                   prompt_sha256: str, launch_token: str) -> dict:
    """Assess the checkout exactly as a collection would, without writing anything.

    Identities come from the issued handoff, which preparation rendered from
    the session record, so the declaration is compared with the same values a
    collection uses. The result lists every checkout-attributable custody gap
    a collection of this unchanged checkout would record, each with its code
    and the change that clears it, and its overall exit code. Declared
    completion and report kind never change the code.
    """
    from stewart.assignment import expand_input_manifest
    from stewart.collect import assess_checkout, custody_gaps
    from stewart._repository import checkout_git

    if not Path(expected_worktree).is_absolute():
        raise _refuse("expected_worktree", "--expected-worktree", "absolute handoff path", str(expected_worktree))
    actual = Path(git_text(ws.repo, "rev-parse", "--show-toplevel")).resolve()
    if actual != Path(expected_worktree).resolve():
        raise _refuse("checkout_root", "repository root", str(Path(expected_worktree).resolve()), str(actual),
                      "run the issued command in the prepared checkout")
    git_admin = _own_administration(actual, issued_handoff(ws, actual))
    arguments = {"launch_prompt_commit": launch_prompt_commit, "prompt_sha256": prompt_sha256,
                 "launch_token": launch_token}
    extra = []
    handoff = issued_handoff(ws, actual)
    if handoff is None:
        extra.append({"id": "handoff_unavailable", "code": 3, "observable": True,
                      "description": "the issued handoff is absent, ambiguous or unreadable, so no identity "
                                     "can be confirmed against preparation"})
        handoff_path, issued = f"{ws.rel}/{HANDOFF_DIRECTORY}/", {**arguments, "target_commit": None}
    else:
        handoff_path, issued = handoff
        for field, value in arguments.items():
            if value != issued[field]:
                extra.append({"id": f"command_mismatch:{field}", "code": 1, "observable": True,
                              "description": f"this command's --{field.replace('_', '-')} {value!r} differs "
                                             f"from the issued handoff's {issued[field]!r}"})
    options = checkout_git(actual, git_admin)
    prompt = git(actual, *options, "show", f"{issued['launch_prompt_commit']}:{ws.prompt}", check=False)
    if prompt.returncode or _hash.sha256_bytes(prompt.stdout) != issued["prompt_sha256"]:
        raise _refuse("prompt_digest", "committed prompt SHA-256", issued["prompt_sha256"],
                      "unavailable" if prompt.returncode else _hash.sha256_bytes(prompt.stdout),
                      "compare the command with the issued handoff and report the mismatch")
    meta = prompt_metadata(prompt.stdout.decode("utf-8"), ws)
    manifest_verified = True
    try:
        meta = expand_input_manifest(ws, meta)
    except StewartError as exc:
        manifest_verified = False
        extra.append({"id": "input_manifest_changed", "code": 3, "observable": True,
                      "description": f"the pinned input manifest no longer verifies: {exc}"})
    expected = {"audit_id": meta["audit_id"], "target_commit": issued["target_commit"] or meta["target_commit"],
                "launch_prompt_commit": issued["launch_prompt_commit"], "prompt_sha256": issued["prompt_sha256"],
                "launch_token": issued["launch_token"]}
    sources = {field: "issued handoff" for field in expected}
    sources["audit_id"] = "committed prompt assignment"
    receipt = assess_checkout(actual, meta=meta, prompt_commit=issued["launch_prompt_commit"],
                              handoff_path=handoff_path, expected=expected, sources=sources, git_admin=git_admin)
    gaps = [gap for gap in custody_gaps(receipt) if gap["observable"]]
    if handoff is None:
        # Without the issued handoff, nothing in its directory can be told
        # apart from it; never suggest removing what may be the handoff.
        gaps = [gap for gap in gaps if not gap["id"].startswith(f"unexpected_path:{handoff_path}")]
    gaps += extra
    tracked = {rel for rel in receipt["unexpected_paths"]
               if git(actual, *options, "cat-file", "-e", f"{issued['launch_prompt_commit']}:{rel}",
                      check=False).returncode == 0}
    staged = set(os.fsdecode(git(actual, *options, "diff", "--cached", "--name-only", "--no-renames", "-z",
                                 issued["launch_prompt_commit"]).stdout).split("\0")) - {""}
    for gap in gaps:
        rel = gap["id"].partition(":")[2]
        if not manifest_verified and gap["id"].startswith("unexpected_path:") and rel not in tracked:
            # The changed manifest no longer says which uncommitted files are
            # supplied inputs; this one may be, so nothing here is a fix.
            gap.update(code=3, description=gap["description"] + "; while the input manifest does not verify, "
                       "this may be a supplied input")
        gap["fix"] = _fix(gap, issued["launch_prompt_commit"], tracked, staged)
    return {"schema": "stewart.auditor-check/1", "audit_id": meta["audit_id"],
            "exit_code": combined_code(gap["code"] for gap in gaps),
            "gaps": gaps, "declaration": receipt["declaration"], "report_path": meta["report_path"],
            "report_status": receipt["report_status"], "observed_checkout_commit": receipt["checkout"]["head"],
            "limit": "Custody structure only: whether a collection of this unchanged checkout would record "
                     "gaps you can see. It does not judge the audit, its completion or its report kind."}


def _block(declaration: dict) -> bytes:
    return FENCE + b"\n" + json.dumps(declaration, indent=2).encode("utf-8") + b"\n```"


def _signature(st) -> tuple:
    return st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns


def _publish(report: Path, data: bytes, original: bytes | None, signature: tuple | None, verify) -> None:
    """Stage bytes in a pinned directory, recheck inputs, then publish atomically.

    Start uses an exclusive hard-link publication; set renames the staged file.
    Checks are endpoint observations, not a lock against hostile concurrent
    writers. Failed staging is retained and named; custody inventory sees it.
    """
    temporary = report.with_name(f".{report.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open_directory(report.parent) as parent:
            write_exclusive(Path(temporary.name), data, dir_fd=parent)
            verify()
            with open_directory(report.parent) as current:
                if _signature(os.fstat(current))[:2] != _signature(os.fstat(parent))[:2]:
                    raise _refuse("report_changed", str(report.parent), "original directory", "replaced directory")
            if original is None:
                # link creates the final name exclusively: an occupied path is never replaced.
                os.link(temporary.name, report.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                os.unlink(temporary.name, dir_fd=parent)
            else:
                info, current_bytes = read_regular(Path(report.name), dir_fd=parent)
                current_stat = os.stat(report.name, dir_fd=parent, follow_symlinks=False)
                if current_bytes != original or _signature(current_stat) != signature:
                    raise _refuse("report_changed", str(report), _hash.sha256_bytes(original),
                                  info.get("sha256", info["kind"]), "preserve the changed report and run check")
                os.replace(temporary.name, report.name, src_dir_fd=parent, dst_dir_fd=parent)
    except (OSError, StewartError) as exc:
        raise StewartError(f"report publication expected intact inputs and atomic publication, observed {exc}. "
                           f"Staging path (if created) retained: {temporary}",
                           reason=getattr(exc, "reason", "report_write"), retained=[str(report), str(temporary)],
                           next_steps=["preserve the report and any named staging file; report the failure before retrying"]) from exc


def _operate(ws: Workspace, operation: str, *, expected_worktree: Path,
                       launch_prompt_commit: str, prompt_sha256: str, launch_token: str,
                       completion: str | None = None, report_kind: str | None = None) -> dict:
    """Start exclusively or set only the block.

    Returns the validated declaration, comparisons and report path; raises an
    actionable StewartError on refusal. The CLI prints a success line (plus the
    declaration with --print), exits 0 on success and 2 on refusal. Qualification
    and scientific reasoning remain prose. No private session is accessed.
    """
    if operation not in ("start", "set") or (operation == "set" and completion not in COMPLETIONS):
        raise _refuse("usage", "operation/completion", "start, or set --completion VALUE", (operation, completion))
    if report_kind is not None and (operation != "set" or report_kind not in REPORT_KINDS):
        raise _refuse("report_kind", "set --report-kind", REPORT_KINDS, report_kind)
    kwargs = dict(expected_worktree=expected_worktree, launch_prompt_commit=launch_prompt_commit,
                  prompt_sha256=prompt_sha256, launch_token=launch_token)
    report, expected, sources, git_admin = auditor_context(ws, **kwargs)
    original = None
    signature = None
    if operation == "start":
        if os.path.lexists(report):
            raise _refuse("destination_exists", str(report), "unoccupied destination", "occupied",
                          "use set to change completion or check to validate the existing report", retained=[str(report)])
        declaration = {"schema_version": SCHEMA_VERSION, **expected, "completion": "partial", "report_kind": None}
        data = (f"# Audit {expected['audit_id']}\n\n".encode() + _block(declaration)
                + b"\n\nCompletion qualification: \n\n## Answer and implication\n\n"
                  b"## Inputs, coverage and gaps\n\n## Findings and unresolved questions\n\n"
                  b"## Evidence request or proposed reframe\n\n"
                  b"For needs-evidence: name the undecidable premise, smallest missing evidence,\n"
                  b"answers it would distinguish, and whether it needs supply or new measurement.\n"
                  b"For reframe: answer the assigned question, cite the evidence motivating one\n"
                  b"bounded replacement question, and name the decision it would better inform.\n"
                  b"For answer: omit this section if no follow-up is proposed. No kind grants scope.\n\n"
                  b"## Stopping reason, failures and deviations\n")
    else:
        with open_directory(report.parent) as parent:
            signature = _signature(os.stat(report.name, dir_fd=parent, follow_symlinks=False))
            info, original = read_regular(Path(report.name), dir_fd=parent)
        if original is None:
            raise _refuse("report_unreadable", str(report), "readable regular file", info,
                          "preserve the unavailable report and report the problem", retained=[str(report)])
        declaration = _require_valid(validate_report_declaration(original, expected=expected, sources=sources))
        data = original
        if operation == "set":
            _, start, end = _parse(original)
            declaration = {**declaration, "completion": completion,
                           "observed_checkout_commit": expected["observed_checkout_commit"]}
            # Omitting the option preserves the auditor's existing selection;
            # it must never silently convert a request into an ordinary answer.
            if report_kind is not None:
                declaration["report_kind"] = report_kind
            data = original[:start] + _block(declaration) + original[end:]
    result = validate_report_declaration(data, expected=expected, sources=sources)
    _require_valid(result)
    def verify():
        if auditor_context(ws, **kwargs) != (report, expected, sources, git_admin):
            raise _refuse("context_changed", "checkout context", expected, "changed inputs")
    _publish(report, data, original, signature, verify)
    return {**result, "report_path": str(report), "report_path_source": "committed prompt assignment"}


def report_declaration(ws: Workspace, operation: str, *, expected_worktree: Path,
                       launch_prompt_commit: str, prompt_sha256: str, launch_token: str,
                       completion: str | None = None, report_kind: str | None = None) -> dict:
    """Run start, set or check.

    Start and set return the validated declaration, comparisons and path. Check
    returns the gaps a collection of the unchanged checkout would attribute to
    it, each with its code and fix, and the overall exit code. Refusals raise
    StewartError with retained paths and correction steps. No output is printed
    here. Only start and set publish bytes.
    """
    try:
        if operation == "check":
            return check_checkout(ws, expected_worktree=expected_worktree, launch_prompt_commit=launch_prompt_commit,
                                  prompt_sha256=prompt_sha256, launch_token=launch_token)
        return _operate(ws, operation, expected_worktree=expected_worktree,
                        launch_prompt_commit=launch_prompt_commit, prompt_sha256=prompt_sha256,
                        launch_token=launch_token, completion=completion, report_kind=report_kind)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _refuse("context_unavailable", "checkout/report", "readable prepared context", str(exc),
                      "preserve the report and report the unavailable input", retained=[str(ws.repo)]) from exc
    except StewartError as exc:
        if not exc.next_steps:
            exc.next_steps = ["preserve the report; compare the issued handoff and report the context problem"]
        if not exc.retained:
            exc.retained = [str(ws.repo)]
        raise


CODE_MEANINGS = {0: "accepted: nothing to change", 1: "action needed: change what is listed, then run check again",
                 2: "refused: nothing was done", 3: "something you cannot repair does not verify: "
                 "describe it in the report, declare, and stop"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Declare auditor completion and report kind, and check the checkout "
                                                 "the way collection will; validates structure and identities only.",
        epilog="Exit 0: nothing to change. 1: change what is listed and run check again. 2: refused, nothing done; "
               "reread the handoff command. 3: something you cannot repair does not verify; describe it in the report, "
               "declare, and stop. Completion and report kind never change the code. Run check as the last action "
               "before stopping: exit 0 means a collection of the unchanged checkout records nothing for you to fix.")
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("start", "set", "check"):
        command = commands.add_parser(name, help={"start": "exclusively create a partial report skeleton",
            "set": "replace only the declaration; preserve all surrounding bytes",
            "check": "report, without writing, what a collection would ask you to fix"}[name],
            epilog=parser.epilog)
        command.add_argument("--workspace", required=True, help="repo-relative assignment workspace")
        command.add_argument("--expected-worktree", required=True, type=Path, help="absolute prepared checkout from handoff")
        command.add_argument("--launch-prompt-commit", required=True, help="transcribe from handoff; checked against it and HEAD")
        command.add_argument("--prompt-sha256", required=True, help="transcribe from handoff; checked against it and the committed prompt")
        command.add_argument("--launch-token", required=True, help="transcribe from handoff; checked against the issued handoff")
        command.add_argument("--print", dest="print_declaration", action="store_true", help="also print the full validated declaration")
        if name == "check":
            command.add_argument("--json", action="store_true", help="print one result document, with no other stdout")
        if name == "set":
            command.add_argument("--completion", required=True, choices=COMPLETIONS)
            command.add_argument("--report-kind", choices=REPORT_KINDS,
                                 help="answer, missing-evidence request, or proposed reframe; omission preserves the current kind. "
                                      "A complete report needs a selected kind. Requests grant no new scope; explain them in prose.")
    return parser


def _render_check(result: dict) -> list[str]:
    code = result["exit_code"]
    validation = result["declaration"]
    declared = validation.get("declaration") or {}
    lines = [f"check exit {code}: {CODE_MEANINGS[code]}",
             f"audit={result['audit_id']} report={result['report_path']} ({result['report_status']}) "
             f"HEAD={result['observed_checkout_commit']} "
             f"declaration={validation['status']}"
             + (f" completion={declared['completion']} report_kind={declared['report_kind'] or 'unset'}"
                if declared else "")]
    for gap in result["gaps"]:
        lines += [f"[{gap['code']}] {gap['id']}: {gap['description']}", f"    fix: {gap['fix']}"]
    lines.append(result["limit"])
    return lines


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = Path(git_text(Path.cwd(), "rev-parse", "--show-toplevel"))
        result = report_declaration(workspace(root, args.workspace), args.operation,
            expected_worktree=args.expected_worktree, launch_prompt_commit=args.launch_prompt_commit,
            prompt_sha256=args.prompt_sha256, launch_token=args.launch_token,
            completion=getattr(args, "completion", None), report_kind=getattr(args, "report_kind", None))
    except (StewartError, OSError, subprocess.TimeoutExpired) as exc:
        if not isinstance(exc, StewartError):
            exc = _refuse("context_unavailable", "checkout/report", "readable prepared context", str(exc),
                          "preserve the report and report the unavailable input")
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "exit_code": exc.exit_code, "error": exc.to_json()}, indent=2))
        else:
            print(f"Refused ({exc.reason}): {exc} Next: {'; '.join(exc.next_steps) or 'inspect the issued handoff and context'}",
                  file=sys.stderr)
        return exc.exit_code
    if args.operation == "check":
        code = result["exit_code"]
        if args.json:
            print(json.dumps({"ok": code == 0, "exit_code": code, "result": result}, indent=2))
        else:
            print("\n".join(_render_check(result)))
            if args.print_declaration and result["declaration"].get("declaration"):
                print(json.dumps(result["declaration"]["declaration"], indent=2))
        return code
    value = result["declaration"]
    print(f"{value['completion']} audit={value['audit_id']} HEAD={value['observed_checkout_commit']} "
          f"report_kind={value['report_kind'] or 'unset'} report={result['report_path']}")
    if args.print_declaration:
        print(json.dumps(value, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
