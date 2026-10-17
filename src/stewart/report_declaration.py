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
import subprocess
import sys
import uuid

from stewart import _util as _hash
from stewart._bootstrap import StewartError, open_directory, read_regular, write_exclusive
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
             prompt_sha256: str, launch_token: str) -> tuple[Path, dict, dict]:
    """Shared checkout/prompt binding for narrow auditor helpers; no report read or session access."""
    if not Path(expected_worktree).is_absolute():
        raise _refuse("expected_worktree", "--expected-worktree", "absolute handoff path", str(expected_worktree))
    actual = Path(git_text(ws.repo, "rev-parse", "--show-toplevel")).resolve()
    expected_root = Path(expected_worktree).resolve()
    if actual != expected_root:
        raise _refuse("checkout_root", "repository root", str(expected_root), str(actual),
                      "run the issued command in the prepared checkout")
    info, gitfile = read_regular(actual / ".git")
    if gitfile is None or not gitfile.startswith(b"gitdir: "):
        raise _refuse("checkout_git_file", ".git", "worktree-style regular file", info)
    symbolic = git(actual, "symbolic-ref", "-q", "HEAD", check=False)
    if symbolic.returncode != 1:
        raise _refuse("checkout_detached", "HEAD", "detached", symbolic.stdout.decode(errors="replace"))
    head = git_text(actual, "rev-parse", "HEAD")
    if head != launch_prompt_commit:
        raise _refuse("checkout_commit", "HEAD", launch_prompt_commit, head,
                      "report the unexpected commit; do not hide it by resetting HEAD")
    prompt = git(actual, "show", f"{launch_prompt_commit}:{ws.prompt}").stdout
    digest = _hash.sha256_bytes(prompt)
    if digest != prompt_sha256:
        raise _refuse("prompt_digest", "committed prompt SHA-256", prompt_sha256, digest,
                      "compare the command with the issued handoff and report the mismatch")
    prompt_path = contained(actual, ws.prompt)
    info, working = read_regular(prompt_path)
    if working != prompt:
        raise _refuse("prompt_drift", str(prompt_path), digest, info.get("sha256", info["kind"]),
                      "report working-prompt drift; do not derive a destination from changed bytes")
    meta = prompt_metadata(prompt.decode("utf-8"), ws)
    expected = {"audit_id": meta["audit_id"], "target_commit": meta["target_commit"],
                "launch_prompt_commit": launch_prompt_commit, "prompt_sha256": prompt_sha256,
                "launch_token": launch_token, "observed_checkout_commit": head}
    sources = {"audit_id": "committed prompt assignment", "target_commit": "committed prompt assignment",
               "launch_prompt_commit": "handoff argument checked against local HEAD",
               "prompt_sha256": "handoff argument checked against committed prompt bytes",
               "launch_token": "handoff argument; only Stewart can verify the issued value",
               "observed_checkout_commit": "local HEAD observed by helper"}
    return contained(actual, meta["report_path"]), expected, sources


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
    """Start exclusively, set only the block, or check without writing.

    Returns the validated declaration, comparisons and report path; raises an
    actionable StewartError on refusal. The CLI prints a success line (plus the
    declaration with --print), exits 0 on success and 2 on refusal. Qualification
    and scientific reasoning remain prose. No private session is accessed.
    """
    if operation not in ("start", "set", "check") or (operation == "set" and completion not in COMPLETIONS):
        raise _refuse("usage", "operation/completion", "start, set --completion VALUE, or check", (operation, completion))
    if report_kind is not None and (operation != "set" or report_kind not in REPORT_KINDS):
        raise _refuse("report_kind", "set --report-kind", REPORT_KINDS, report_kind)
    kwargs = dict(expected_worktree=expected_worktree, launch_prompt_commit=launch_prompt_commit,
                  prompt_sha256=prompt_sha256, launch_token=launch_token)
    report, expected, sources = auditor_context(ws, **kwargs)
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
    if operation != "check":
        def verify():
            if auditor_context(ws, **kwargs) != (report, expected, sources):
                raise _refuse("context_changed", "checkout context", expected, "changed inputs")
        _publish(report, data, original, signature, verify)
    return {**result, "report_path": str(report), "report_path_source": "committed prompt assignment"}


def report_declaration(ws: Workspace, operation: str, *, expected_worktree: Path,
                       launch_prompt_commit: str, prompt_sha256: str, launch_token: str,
                       completion: str | None = None, report_kind: str | None = None) -> dict:
    """Validate start/set/check and return its declaration, comparisons and path.

    Refusals raise StewartError with retained paths and correction steps. No
    output is printed here; the CLI prints one success line, --print adds JSON,
    and exits 0 on success or 2 on refusal. Only start and set publish bytes.
    """
    try:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Declare auditor completion and report kind; validates structure and identities only.",
        epilog="Success prints completion, report kind, audit ID, observed HEAD and report path. --print adds the validated JSON. "
               "Exit 0: validated success; exit 2: refused or invalid usage. Run check as the last action before stopping.")
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("start", "set", "check"):
        command = commands.add_parser(name, help={"start": "exclusively create a partial report skeleton",
            "set": "replace only the declaration; preserve all surrounding bytes", "check": "validate without writing"}[name],
            epilog=parser.epilog)
        command.add_argument("--workspace", required=True, help="repo-relative assignment workspace")
        command.add_argument("--expected-worktree", required=True, type=Path, help="absolute prepared checkout from handoff")
        command.add_argument("--launch-prompt-commit", required=True, help="transcribe from handoff; checked against HEAD")
        command.add_argument("--prompt-sha256", required=True, help="transcribe from handoff; checked against committed prompt")
        command.add_argument("--launch-token", required=True, help="transcribe from handoff; only Stewart verifies issued token")
        command.add_argument("--print", dest="print_declaration", action="store_true", help="also print the full validated declaration")
        if name == "set":
            command.add_argument("--completion", required=True, choices=COMPLETIONS)
            command.add_argument("--report-kind", choices=REPORT_KINDS,
                                 help="answer, missing-evidence request, or proposed reframe; omission preserves the current kind. "
                                      "A complete report needs a selected kind. Requests grant no new scope; explain them in prose.")
    return parser


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
        print(f"Refused ({exc.reason}): {exc} Next: {'; '.join(exc.next_steps) or 'inspect the issued handoff and context'}", file=sys.stderr)
        return 2
    value = result["declaration"]
    print(f"{value['completion']} audit={value['audit_id']} HEAD={value['observed_checkout_commit']} "
          f"report_kind={value['report_kind'] or 'unset'} report={result['report_path']}")
    if args.print_declaration:
        print(json.dumps(value, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
