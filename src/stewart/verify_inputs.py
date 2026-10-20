"""Read-only auditor input verification, bound to the issued checkout and prompt.

No source is executed, no report or checksum list is written, and no manager
session is read. The committed prompt (and its pinned manifest, if supplied)
defines the population. A match establishes current byte identity only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from stewart.assignment import expand_input_manifest, expected_inputs, observe_inputs, prompt_metadata
from stewart._git import git, git_text
from stewart._bootstrap import EXIT_ATTENTION, EXIT_REFUSED, EXIT_UNVERIFIED, StewartError, combined_code
from stewart.report_declaration import auditor_context, restore_command
from stewart.workspace import Workspace, workspace


def verify_inputs(ws: Workspace, *, expected_worktree: Path, launch_prompt_commit: str,
                  prompt_sha256: str, launch_token: str) -> dict:
    """Return every selected file's expected/observed digest, including failures.

    Context or manifest problems refuse before comparing a population whose
    identity is uncertain. Missing, changed, linked and special input files are
    explicit failed rows. Unselected files and report prose are irrelevant.
    """
    context_args = dict(expected_worktree=expected_worktree, launch_prompt_commit=launch_prompt_commit,
                        prompt_sha256=prompt_sha256, launch_token=launch_token)
    from stewart._repository import checkout_git
    context = auditor_context(ws, **context_args)
    # Every question goes to the administration the context verified, never to whatever .git names now.
    options = checkout_git(ws.repo, context[3])
    prompt = git(ws.repo, *options, "show", f"{launch_prompt_commit}:{ws.prompt}").stdout
    try:
        meta = expand_input_manifest(ws, prompt_metadata(prompt.decode("utf-8"), ws))
    except StewartError as exc:
        # The inventory was copied and verified at preparation; a mismatch now
        # is a supplemental input changed in this checkout, which the auditor
        # cannot restore. Collection records the same path with code 3.
        if exc.reason == "input_manifest":
            exc.code = EXIT_UNVERIFIED
            exc.next_steps = ["not yours to repair: describe the changed input inventory in the report, declare, and stop"]
        raise
    rows = observe_inputs(ws.repo, expected_inputs(ws.repo, meta, meta["target_commit"], options=options))
    if auditor_context(ws, **context_args) != context:
        raise StewartError("checkout/prompt changed during input verification", reason="context_changed")
    # Recheck the inventory binding after reading files; it is not a mutable
    # source of replacement expectations during this operation.
    if expand_input_manifest(ws, prompt_metadata(prompt.decode("utf-8"), ws)) != meta:
        raise StewartError("input manifest changed during verification", reason="input_manifest")
    # Preparation verified every input before handoff, so a failed row changed
    # inside this checkout. A committed input can be restored from Git (1); a
    # supplemental input's original bytes are private, so it cannot (3).
    for row in rows:
        row["code"] = 0 if row["matches"] else EXIT_ATTENTION if row["kind"] == "committed" else EXIT_UNVERIFIED
        if not row["matches"]:
            row["fix"] = (f"restore it with {restore_command(launch_prompt_commit, row['path'])}"
                          if row["kind"] == "committed" else
                          "not yours to repair: describe it in the report, declare, and stop")
    failed = sum(not row["matches"] for row in rows)
    return {"schema": "stewart.input-check/2", "audit_id": meta["audit_id"],
            "prompt_sha256": prompt_sha256, "observed_checkout_commit": context[1]["observed_checkout_commit"],
            "selected": len(rows), "matched": len(rows) - failed, "failed": failed, "inputs": rows,
            "exit_code": combined_code(row["code"] for row in rows),
            "limit": "Byte identity at read time only; not execution provenance, read coverage, permission compliance or scientific sufficiency."}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check all supplied input bytes in the prepared audit checkout, without writing or executing inputs.",
        epilog="Exit 0: all selected files match. 1: a committed input you changed; restore it with the printed "
               "git command and run this again. 2: identity/manifest refusal or invalid usage; nothing done. "
               "3: a supplemental input differs; you cannot restore it: describe it in the report, declare, and stop. "
               "Default output includes every failed row.")
    parser.add_argument("--workspace", required=True, help="repo-relative assignment workspace")
    parser.add_argument("--expected-worktree", required=True, type=Path, help="absolute prepared checkout from handoff")
    parser.add_argument("--launch-prompt-commit", required=True, help="handoff commit; checked against detached HEAD")
    parser.add_argument("--prompt-sha256", required=True, help="handoff digest; checked against committed and working prompt")
    parser.add_argument("--launch-token", required=True, help="issued handoff token; only the manager verifies its issued value")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--print", dest="print_rows", action="store_true", help="print all paths and expected/observed digests")
    output.add_argument("--json", action="store_true", help="print one result or refusal document, with no extra stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = Path(git_text(Path.cwd(), "rev-parse", "--show-toplevel"))
        result = verify_inputs(workspace(root, args.workspace), expected_worktree=args.expected_worktree,
                               launch_prompt_commit=args.launch_prompt_commit, prompt_sha256=args.prompt_sha256,
                               launch_token=args.launch_token)
    except (StewartError, OSError, subprocess.TimeoutExpired) as exc:
        reason = getattr(exc, "reason", "context_unavailable")
        code = getattr(exc, "exit_code", EXIT_REFUSED)
        next_steps = getattr(exc, "next_steps", []) or ["preserve inputs; compare the issued handoff and report the problem"]
        if args.json:
            print(json.dumps({"ok": False, "exit_code": code, "error": {"reason": reason, "message": str(exc), "next_steps": next_steps}}))
        else:
            print(f"Refused ({reason}): {exc} Next: {'; '.join(next_steps)}", file=sys.stderr)
        return code
    code = result["exit_code"]
    if args.json:
        print(json.dumps({"ok": code == 0, "exit_code": code, "result": result}, indent=2))
    else:
        print(f"audit={result['audit_id']} selected={result['selected']} matched={result['matched']} failed={result['failed']}")
        for row in result["inputs"]:
            if args.print_rows or not row["matches"]:
                observed = row["observed_sha256"] or row["observed_kind"]
                if row["observed_detail"]:
                    observed += ": " + row["observed_detail"]
                print(f"{'MATCH' if row['matches'] else 'FAIL'} {row['path']}: expected {row['expected_sha256']}; "
                      f"observed {observed}" + (f"; fix: {row['fix']}" if not row["matches"] else ""))
        print(result["limit"])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
