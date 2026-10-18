"""Command interface over the custody operations.

Rendering is separate from the operations: every command calls a package
function that returns a structured result, then prints it either as prose or as
one JSON document. JSON mode never mixes progress chatter into stdout.

Exit codes (shared with the auditor helpers):

* ``0`` nothing needs attention. There is no "succeeded with warnings".
* ``1`` the operation completed and something needs action within the caller's
  role: a custody gap to disposition, a capture to repeat, an attempt whose
  child or preservation check failed. The records are written; read them.
* ``2`` the operation was refused or failed before completing, or the command
  line was invalid. Nothing was done.
* ``3`` evidence, records or bytes the caller cannot repair do not verify. It
  takes precedence over 1: inspect, then recover or abandon.

Codes never depend on what the audit says: declared completion, report kind,
prose and triage outcomes are attributed claims, not tool results. A custody
operation succeeding is not an audit passing. A child process's exit status is
recorded in its attempt receipt and never becomes this tool's exit code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

from stewart._json import DuplicateKey, loads_control
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, RefusalParser, StewartError
from stewart.workspace import Workspace, workspace

RESULT_SCHEMA = "stewart.result/2"


def build_parser() -> argparse.ArgumentParser:
    """Build the parser; building it performs no repository or session work."""
    # Keep guide paths on their own lines so help never splits a filename at a
    # hyphen. These are prose entry points, not an assignment type registry.
    question_help = (
        "Question guide: stewart docs questions\n"
        "  Instrument discrimination; information preservation;\n"
        "  constrained experiment construction; receipt sufficiency.\n"
        "Conditional protocols: stewart docs protocols\n"
        "  Read only for assigned construction, execution or research.\n"
        "  Recipes and protocols grant no permissions."
    )
    parser = RefusalParser(
        prog="stewart",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Custody for managed audits: initialize an assignment, prepare a detached\n"
            "worktree, collect evidence, triage and retain it, release a paused hold,\n"
            "and inspect a session.\n"
            "Never launches an agent, runs project tests, commits, or deletes a worktree."
        ),
        epilog=(
            question_help + "\n\n"
            "Exit codes: 0 nothing needs attention; 1 completed, action needed (read the output);\n"
            "2 refused or invalid usage, nothing done; 3 records or bytes do not verify (takes precedence).\n"
            'Example: <venv>/bin/stewart --repo "$PWD" --workspace '
            "path/to/workspace status --audit-id one-bounded-question"
        ),
    )
    parser.add_argument("--repo", type=Path,
                        help="explicit maintainer checkout; never inferred from the tool or current directory")
    parser.add_argument("--workspace",
                        help="repo-relative assignment workspace holding AUDITOR.md, MAINTAINER.md and PROMPT.md; "
                             "roles are independent of the model or harness")
    parser.add_argument("--json", action="store_true",
                        help="print one JSON result document on stdout instead of prose")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    from stewart.docs import DOCUMENTS
    documentation = commands.add_parser(
        "docs", help="[no repository or session writes] print a bundled document or role template; no repository needed")
    documentation.add_argument("document", choices=sorted(DOCUMENTS))

    init = commands.add_parser(
        "init", help="[writes only with --replace-prompt] draft a prompt and optional pinned input manifest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Generate assignment metadata with pinned identities. Prints the draft unless\n"
                    "--replace-prompt is given, which creates the optional input inventory and\n"
                    "replaces PROMPT.md in full after validation. Choose a recipe from the caller's\n"
                    "guidance, and name its path and section in the prompt.",
        epilog=question_help,
    )
    init.add_argument("--audit-id", required=True, help="fresh audit ID; determines the report path")
    init.add_argument("--target-commit", default="HEAD", help="full target commit ID, or HEAD (default)")
    init.add_argument("--base-commit", help="optional comparison commit ID, or HEAD")
    init.add_argument("--input", action="append", default=[], help="committed entry file; repeat as needed")
    init.add_argument("--input-manifest", metavar="PATH",
                      help="new repo-relative uncommitted inventory path; factor file pins and shared provenance out of the prompt. "
                           "With --replace-prompt creates it exclusively; preview --json includes its document without writes")
    init.add_argument("--source", nargs=2, action="append", default=[], metavar=("URL", "PURPOSE"),
                      help="assigned HTTPS source and its purpose; apply the workspace's source-authority policy")
    init.add_argument("--supplemental", nargs=2, action="append", default=[], metavar=("PATH", "PROVENANCE"),
                      help="uncommitted input to hash and copy; repeat as needed")
    init.add_argument("--evidence-package", action="append", default=[], metavar="MANIFEST",
                      help="repo-relative exported manifest.json; verify and pin all members. Manifest/source objects "
                           "must have unique keys; payload bytes remain opaque. Repeat as needed")
    init.add_argument("--scratch", action="append", default=[],
                      help="permitted scratch path below workspace scratch/<audit-id>/; default: notes/ for prose and checksum lists; grants no execution")
    init.add_argument("--experiment-grant", type=Path, metavar="FILE",
                      help="JSON file holding a stewart.experiment-grant/2 Python-script grant to inline; "
                           "object keys must be unique at every nesting level")
    init.add_argument("--replace-prompt", action="store_true",
                      help="replace PROMPT.md in full after input validation; create the optional input manifest")

    prep = commands.add_parser(
        "prepare", help="[writes private custody, Git refs and a worktree] validate a committed prompt and build its checkout",
        description="Select an exact non-bare maintainer root, on any branch or detached HEAD, and refuse "
                    "registered auditor roots. Validate a prompt-only commit, retain its prompt/target/base commits "
                    "with create-only refs, pin inputs, and create the private session under the Git common "
                    "directory (<common>/stewart/sessions). The detached worktree, its supplied runtime and "
                    "experiment homes go in a UUID-named directory under the per-user checkout home, outside every "
                    "working tree; the worktree stays locked for its lifetime. Copies supplemental bytes and writes "
                    "the launch handoff. Supplies pinned declaration and input-verification helpers from the "
                    "selected Stewart installation independently of project history. The manager's harness must "
                    "allow writes to <common>/stewart and the checkout home (status names both). Failed "
                    "preparations are preserved and require a fresh audit ID. Launches nothing.",
    )
    prep.add_argument("--checkout-home", type=Path, metavar="DIRECTORY",
                      help="absolute, unlinked, private (0700) directory for auditor checkouts, outside every "
                           "working tree; default ~/.local/state/stewart/checkouts. No environment variable selects it")
    prep.add_argument("--prompt-commit", default="HEAD", help="full prompt-only commit ID, or HEAD")
    prep.add_argument("--mode", choices=("snapshot", "paused"), default="snapshot",
                      help="snapshot lets development continue (default); paused records a writer hold")
    prep.add_argument("--writers-paused", action="store_true",
                      help="acknowledge an actual, already-arranged writer pause; required only for paused mode")
    prep.add_argument("--pause-note", metavar="TEXT",
                      help="who was paused and how the pause was arranged; required with --writers-paused, "
                           "recorded verbatim, never verified")

    launch = commands.add_parser(
        "launch", help="[writes a session launch record] acknowledge how the handoff was made; launches nothing",
        description="Record the manager's acknowledgment of one handoff: the style (terminal recipe, harness "
                    "sub-agent, other), the model and effort requested, and a note. With --from-profile these come "
                    "from the launch profile pinned at preparation, and the record carries its digest and the exact "
                    "rendered command; explicit flags override single values. Stewart launches nothing and "
                    "observes no auditor; this is an attributed claim bound to the session's launch token.",
    )
    launch.add_argument("--audit-id", required=True)
    launch.add_argument("--from-profile", action="store_true",
                        help="take style, model, effort, actor and note from the session's pinned LAUNCH-PROFILE.json")
    launch.add_argument("--profile", metavar="PATH", default=None,
                        help="repo-relative launch profile to use instead of the pinned one; objects require unique keys; "
                             "the record keeps both digests")
    launch.add_argument("--style", choices=("terminal", "subagent", "other"),
                        help="terminal: the documented TUI recipe; subagent: a harness-spawned agent that inherits "
                             "the manager's working directory and context; other: explain in --note")
    launch.add_argument("--model", help="model requested of the harness, as named there")
    launch.add_argument("--effort", help="effort requested of the harness, as named there")
    launch.add_argument("--note", default=None, help="harness, first prompt, isolation caveats; optional")
    launch.add_argument("--actor", help="who made the handoff; required unless --from-profile supplies it")

    message = commands.add_parser(
        "message", help="[writes a session message record] relay a ruling or hand-back exchanged with the auditor",
        description="Record one message exchanged with the auditor after launch, as the manager relays it: a "
                    "ruling given to a stopped auditor, or a hand-back received outside the report. The record is "
                    "the manager's transcription; it authenticates nothing and does not establish that it was read.",
    )
    message.add_argument("--audit-id", required=True)
    message.add_argument("--direction", required=True, choices=("to-auditor", "from-auditor"))
    message.add_argument("--text", required=True, help="the message text as sent or received")
    message.add_argument("--channel", default=None, help="how it travelled (harness message, chat paste); optional")
    message.add_argument("--actor", required=True, help="who sent or relayed it")

    view = commands.add_parser(
        "status", help="[no repository or session writes] one session's facts and next actions, or every session",
        description="Inspect one session without writing or repairing anything; without --audit-id, list every "
                    "session of the workspace across the repository with its owner, state, checkout and lock. "
                    "Problems with records are reported in place. Returns absolute worktree, launch and "
                    "per-collection report locators, conditional manual handoff and collection-specific triage-draft "
                    "commands, the manager's write locations, launch "
                    "and message records, and which collections can recover each release's frozen artifacts. "
                    "Release capture associations verify archive and member bytes at read time; failures remain visible. "
                    "Missing receipts are distinct from invalid or unreadable records; neither is repaired. "
                    "Names the Stewart build that wrote the session and whether it is this one. "
                    "Locators do not certify file availability; auditor activity is unobserved. "
                    "Exit 0 means nothing needs attention; 1 lists anomalies and unaddressed gaps; 3 means records "
                    "or bytes do not verify. The exit code says nothing about the audit's outcome.",
    )
    view.add_argument("--audit-id", help="the session to inspect; omit it to list every session of the workspace")
    view.add_argument("--profile", metavar="PATH", default=None,
                      help="repo-relative launch profile to render the handoff from instead of the pinned one, "
                           "for a session whose pinned recipe went stale; objects require unique keys; both are named in the view")

    grab = commands.add_parser(
        "collect", help="[writes a session collection] preserve the report and checkout state; keeps the worktree",
        description="Capture the report first, then an independent no-follow inventory, then Git patches and an "
                    "archive of changed, untracked and ignored files. Partial evidence is retained on failure.",
    )
    grab.add_argument("--audit-id", required=True)
    grab.add_argument("--auditor-stopped", choices=("finished", "interrupted", "blocked"),
                      help="attribute the stop kind to the maintainer; the tool cannot observe process exit")

    recovery = commands.add_parser(
        "recover-runtime", help="[writes a fresh runtime and receipt] materialize retained pristine assets",
        description="Verify the session's private pristine assets, materialize a new runtime directory and retain "
                    "a recovery observation. Existing runtime paths, commands, scopes and releases are unchanged; "
                    "activating recovered code requires a fresh assignment. No replacement bytes are downloaded.")
    recovery.add_argument("--audit-id", required=True)
    recovery.add_argument("--actor", required=True, help="who requested asset recovery")

    export = commands.add_parser(
        "export", help="[writes a new package] select captured evidence for another assignment",
        description="Verify explicitly selected collection or attempt captures and publish a self-contained "
                    "package with their source receipt and digests. Reads no live worktree bytes. "
                    "Selection records custody, not claim acceptance. Existing destinations are refused.",
    )
    export.add_argument("--audit-id", required=True)
    source = export.add_mutually_exclusive_group(required=True)
    source.add_argument("--collection", help="collection record name")
    source.add_argument("--attempt", help="resolved attempt record name")
    export.add_argument("--select", action="append", required=True, metavar="CAPTURE",
                        help="repeat explicitly: collection REPORT.md or files.tar:<repo-relative-path>; "
                             "attempt ATTEMPT.json, ledger.jsonl, child-receipt.json, stdout.txt or stderr.txt; "
                             "either source: runtime-assets or runtime-observation:<collection|before|after> "
                             "for a complete captured runtime group")
    export.add_argument("--output", required=True, metavar="DIRECTORY",
                        help="new repo-relative package directory; parent must already exist; partial failures are kept")
    export.add_argument("--actor", required=True, help="who selected this evidence")

    draft = commands.add_parser(
        "triage-draft", help="[no repository or session writes] print an unanswered response bound to a named collection",
        description="Print response JSON on stdout and declaration/gap context on stderr. With --json, "
                    "result.response and result.context stay separate. The response includes collection identity "
                    "and receipt digest; preserve both. Null answers fail submission; no triage is recorded.",
        epilog='Claim examples: accepted: {"claim":"Named comparison agrees", "evidence":["REPORT.md:12"]}; '
               'rejected: {"claim":"Universal coverage", "reason":"Unselected cases were not measured"}; '
               'unresolved: {"claim":"Residual cause", "reason":"No check distinguishes the rivals"}. '
               'Fill decision, every custody_gaps value, and any follow_up (accept|decline|defer plus reason). '
               'Follow-up is a manager decision, not an execution grant. Submit the response object alone with triage --response FILE.',
    )
    draft.add_argument("--audit-id", required=True)
    draft.add_argument("--collection", required=True, help="collection name as printed by collect")

    triage = commands.add_parser(
        "triage", help="[writes a session triage record] record a maintainer response bound to one collection",
        description="Record accepted, rejected and unresolved claims, custody-gap dispositions and the decision, "
                    "bound to a named collection's receipt and captured report digests.",
    )
    triage.add_argument("--audit-id", required=True)
    triage.add_argument("--collection", required=True, help="collection name as printed by collect, not a path")
    triage.add_argument("--response", required=True, type=Path, metavar="FILE",
                        help="JSON response: collection and collection_sha256 from triage-draft, "
                             "accepted/rejected/unresolved, custody_gaps, decision, "
                             "report_sha256 or report_gap, required follow_up for needs-evidence/reframe, "
                             "optional support_reviewed and applicability; object keys must be unique "
                             "at every nesting level")
    triage.add_argument("--actor", required=True, help="who is recording this disposition")

    retain = commands.add_parser(
        "retain", help="[writes into the maintainer checkout] publish reviewed bytes from a triaged collection",
        description="Publish the captured report and/or reviewed support artifacts from the immutable capture "
                    "into the maintainer checkout. Destinations are created exclusively; nothing is staged or committed.",
    )
    retain.add_argument("--audit-id", required=True)
    retain.add_argument("--triage", required=True, help="triage record name as printed by triage")
    retain.add_argument("--report", action="store_true", help="publish the captured report to its assigned path")
    retain.add_argument("--support", action="append", default=[], metavar="PATH",
                        help="captured regular file listed in the triage's support_reviewed; repeat as needed")

    release_hold = commands.add_parser(
        "resume", help="[writes RESUMED.json] record the release of a paused hold, bound to a triage",
        description="Record a triage or cancellation decision as the release of a paused session's hold. "
                    "Revalidate the reviewed collection and report digests; changed evidence needs fresh review. "
                    "Snapshot sessions have no hold. The tool controls no writer process.",
    )
    release_hold.add_argument("--audit-id", required=True)
    release_hold.add_argument("--triage", required=True, help="triage record name as printed by triage")
    release_hold.add_argument("--reason", required=True, help="triage result or cancellation reason; retained")

    release = commands.add_parser(
        "release", help="[writes a session release record] freeze exact experiment artifacts within the grant",
        description="Record the manager's review and freeze the script, declarations, manifest and ledger "
                    "identities plus the resolved command. Pinned inputs must still match preparation, "
                    "and protected files must match that manifest. Authorizes exactly one invocation.",
    )
    release.add_argument("--audit-id", required=True)
    release.add_argument("--review", required=True, type=Path, metavar="FILE",
                         help="JSON review: cases with expected admission, population, role, prediction and measurement IDs; "
                              "admissibility_reasoning; static_review; limits; object keys must be unique "
                              "at every nesting level")
    release.add_argument("--actor", required=True, help="who reviewed and released")

    run = commands.add_parser(
        "run", help="[writes a session attempt; runs the released child] execute one released invocation",
        description="Re-validate frozen identities, reserve the single attempt, create the output area (empty) "
                    "and the attempt HOME outside it, then run the child with the recorded argv, capture its "
                    "output and compare named protected state at both endpoints. The child must accept an "
                    "existing empty output directory. Its receipt.json is one JSON document with no further "
                    "schema: the keys and digest are recorded, the bytes retained. Retain exact receipt/ledger "
                    "bytes, recompute comparisons and check reviewed case coverage. Exit 1 when the child failed "
                    "or preservation failed; the attempt record says which. A failed attempt leaves the output "
                    "area in the worktree; a new release needs it absent.",
    )
    run.add_argument("--audit-id", required=True)
    run.add_argument("--release", required=True, help="release record name as printed by release")
    run.add_argument("--timeout", type=float, default=None,
                     help="child-process time limit in seconds; custody duration is separate; special outputs never block reading")
    return parser


def _read_json_file(location: Path, what: str) -> dict:
    """Decode manager input without silently selecting among repeated fields.

    Reject duplicates before dispatch can authorize a release or record a
    disposition. The hook sees decoded names at every object depth, including
    escaped aliases and identical repeated values. This authoring rule is
    separate from preserving and interpreting raw child evidence.
    """
    from stewart._bootstrap import read_regular

    try:
        info, data = read_regular(location)
        if data is None:
            raise ValueError(f"{what} file is not a readable regular file: {location}: {info}")
        document = loads_control(data)
        if not isinstance(document, dict):
            raise ValueError(f"{what} file must contain one JSON object")
    except DuplicateKey as exc:
        raise StewartError(
            f"{what} file repeats object key {exc.key!r}; each object must have unique keys",
            reason="duplicate_input_key", retained=[str(location)],
            next_steps=["preserve the original file and author an unambiguous JSON object; "
                        "even identical repeated keys must be removed"],
        ) from exc
    except (ValueError, RecursionError) as exc:
        raise StewartError(str(exc), reason="input_file", retained=[str(location)],
                           next_steps=["supply a readable regular file containing one JSON object"]) from exc
    return document


def dispatch(ws: Workspace, args: argparse.Namespace) -> tuple[dict, int]:
    """Run one command; return its structured result and the exit code it earns."""
    from stewart._repository import maintainer
    maintainer(ws.repo)
    if args.command == "init":
        from stewart.assignment import initialize

        grant = _read_json_file(args.experiment_grant, "experiment grant") if args.experiment_grant else None
        result = initialize(
            ws, args.audit_id, args.target_commit, inputs=args.input, base=args.base_commit,
            sources=[tuple(item) for item in args.source],
            supplemental=[tuple(item) for item in args.supplemental],
            evidence_packages=args.evidence_package,
            scratch=args.scratch, experiment=grant, replace_prompt=args.replace_prompt, input_manifest=args.input_manifest,
        )
        return result, EXIT_OK
    if args.command == "prepare":
        from stewart.prepare import prepare

        return prepare(ws, args.prompt_commit, mode=args.mode, writers_paused=args.writers_paused,
                       pause_note=args.pause_note, checkout_home_path=args.checkout_home), EXIT_OK
    if args.command == "launch":
        from stewart.coordination import record_launch

        return record_launch(ws, args.audit_id, style=args.style, model=args.model, effort=args.effort,
                             actor=args.actor, note=args.note, from_profile=args.from_profile,
                             profile_path=args.profile), EXIT_OK
    if args.command == "message":
        from stewart.coordination import record_message

        return record_message(ws, args.audit_id, direction=args.direction, text=args.text,
                              actor=args.actor, channel=args.channel), EXIT_OK
    if args.command == "status":
        from stewart.status import status, status_list

        if args.audit_id is None:
            if args.profile is not None:
                raise StewartError("--profile needs --audit-id", reason="usage")
            listing = status_list(ws)
            return listing, listing["exit_code"]
        view = status(ws, args.audit_id, profile=args.profile)
        return view, view["exit_code"]
    if args.command == "collect":
        from stewart.collect import collect

        result = collect(ws, args.audit_id, auditor_stopped=args.auditor_stopped)
        return result, result["exit_code"]
    if args.command == "triage":
        from stewart.triage import triage

        response = _read_json_file(args.response, "response")
        return triage(ws, args.audit_id, collection=args.collection, response=response, actor=args.actor), EXIT_OK
    if args.command == "triage-draft":
        from stewart.triage import triage_draft

        return triage_draft(ws, args.audit_id, collection=args.collection), EXIT_OK
    if args.command == "export":
        from stewart.handoff import export_evidence

        return export_evidence(ws, args.audit_id, collection=args.collection, attempt=args.attempt,
                               selectors=args.select, output=args.output, actor=args.actor), EXIT_OK
    if args.command == "recover-runtime":
        from stewart.runtime import recover_runtime

        return recover_runtime(ws, args.audit_id, actor=args.actor), EXIT_OK
    if args.command == "retain":
        from stewart.triage import retain

        return retain(ws, args.audit_id, triage=args.triage, report=args.report, support=args.support), EXIT_OK
    if args.command == "resume":
        from stewart.triage import resume

        return resume(ws, args.audit_id, triage=args.triage, reason=args.reason), EXIT_OK
    if args.command == "release":
        from stewart.experiment import release

        review = _read_json_file(args.review, "review")
        return release(ws, args.audit_id, review=review, actor=args.actor), EXIT_OK
    if args.command == "run":
        from stewart.experiment import run

        result = run(ws, args.audit_id, release=args.release, timeout=args.timeout)
        return result, EXIT_ATTENTION if result["errors"] else EXIT_OK
    raise StewartError(f"unknown command {args.command}", reason="usage")


def _manager_grant(ws: Workspace, exc: PermissionError) -> StewartError:
    """A permission failure names the location the manager's harness must allow."""
    from stewart._repository import DEFAULT_CHECKOUT_HOME, STORAGE, maintainer
    target = Path(exc.filename) if exc.filename else None
    roots = [Path.home() / DEFAULT_CHECKOUT_HOME]
    try:
        roots.insert(0, Path(maintainer(ws.repo)["common_dir"]) / STORAGE)
    except StewartError:
        pass
    root = next((r for r in roots if target is not None and (target == r or target.is_relative_to(r))),
                target.parent if target is not None else None)
    return StewartError(f"permission denied at {target or 'an unnamed path'}: {exc.strerror}",
                        reason="manager_grant_missing", retained=[str(target)] if target else [],
                        next_steps=[f"allow the manager's harness to write {root}; "
                                    "status names this repository's write locations"])


def _shell(action: dict) -> str:
    env = " ".join(f"{key}={shlex.quote(value)}" for key, value in action.get("env", {}).items())
    return (env + " " if env else "") + " ".join(shlex.quote(token) for token in action["argv"])


def render(command: str, result: dict) -> str:
    """Prose for one successful or error-recording result."""
    lines: list[str] = []
    if command == "init":
        if result["written"]:
            lines += [f"Unassigned draft written: {result['written']}",
                      "Next: author the five sections, remove the UNASSIGNED line, commit PROMPT.md alone, then prepare."]
            if result.get("input_manifest"):
                manifest = result["input_manifest"]
                lines += [f"Pinned input manifest: {manifest['written']} (SHA-256 {manifest['sha256']})",
                          "Keep these supplemental bytes available through prepare; the manifest is copied into the audit checkout."]
        else:
            lines.append(result["draft"].rstrip("\n"))
    elif command == "prepare":
        lines += [
            f"Prepared: {result['session']}",
            f"Worktree: {result['worktree']}",
            f"Launch instructions: {result['launch']}",
            f"Prompt commit: {result['prompt_commit']}",
            f"Target commit: {result['target_commit']}",
            f"Mode: {result['mode']}" + (" (writer pause acknowledged by maintainer)" if result["writers_paused"] else ""),
        ]
        if result.get("writers_paused_note"):
            lines.append(f"Pause note: {result['writers_paused_note']}")
        if result.get("launch_command"):
            profile = result["launch_profile"]
            if result.get("probe_command"):
                lines += ["Probe first (expect 'probe exit 0'; it runs the same flags, model and effort "
                          "non-interactively so a stale name fails while you are watching):",
                          result["probe_command"]]
            lines += [
                f"Launch command (from {profile['path']}, pinned in the session; run it in a terminal, "
                "Stewart launches nothing):",
                result["launch_command"],
                f"When the harness ends, its exit code and time are appended to {result['exit_log']}; status reads them.",
                f"Then record the handoff: launch --audit-id {result['audit_id']} --from-profile. After the auditor "
                "stops, collect --auditor-stopped finished|interrupted|blocked.",
            ]
        else:
            lines += [
                "Next: give LAUNCH.md to a fresh auditor thread, record the handoff with launch, and after the "
                "auditor stops, collect --auditor-stopped finished|interrupted|blocked.",
            ]
    elif command == "launch":
        record = result["record"]
        lines += [f"Launch recorded: {result['path']}",
                  f"Style {record['style']}; model {record['model']}; effort {record['effort']}; by {record['actor']}"]
        if record.get("profile_override"):
            lines.append(f"From override profile {record['profile_override']['path']} "
                         f"({record['profile_override']['sha256'][:12]}…), harness {record['harness']}; "
                         + (f"pinned profile {record['profile']['sha256'][:12]}… departed from" if record.get("profile")
                            else "no pinned profile") + "; the rendered command is in the record")
        elif record.get("profile"):
            lines.append(f"From profile {record['profile']['path']} ({record['profile']['sha256'][:12]}…), "
                         f"harness {record['harness']}; the rendered command is in the record")
        lines.append("This is your acknowledgment of the handoff; Stewart launched nothing and observed no auditor.")
    elif command == "message":
        record = result["record"]
        lines += [f"Message recorded: {result['path']}",
                  f"{record['direction']} by {record['actor']}" + (f" via {record['channel']}" if record["channel"] else ""),
                  "Recorded as relayed; not authenticated and not proof it was read."]
    elif command == "collect":
        receipt = result["receipt"]
        summary = receipt.get("inventory") or {}
        lines += [
            f"Collected: {result['path']}",
            f"Report: {receipt['report_status']}; Git discovery: {receipt['git_discovery']}; worktree retained.",
            "Inventory: " + ", ".join(f"{count} {kind}" for kind, count in (summary.get("counts") or {}).items())
            + f"; archived {len(summary.get('archived', []))}; omitted {len(summary.get('omitted', []))}"
            + f"; unreadable {len(summary.get('unreadable', []))}; unsupported {len(summary.get('unsupported', []))}",
        ]
        validation = receipt.get("declaration") or {}
        if validation.get("status") == "valid":
            declared = validation["declaration"]
            lines.append(f"Auditor-reported completion: {declared['completion']}; "
                         f"kind: {declared['report_kind'] or 'unset'} (not a maintainer judgment)")
        if receipt.get("unexpected_paths"):
            lines.append("Unexpected paths: " + ", ".join(receipt["unexpected_paths"]))
        if receipt.get("checkout_commit_changed"):
            lines.append("The worktree HEAD is not the prompt commit: an unexpected commit is recorded.")
        gaps = [gap["id"] + (" (does not verify)" if gap["code"] == 3 else "") for gap in result["gaps"]]
        lines.append("Custody gaps to disposition in triage: " + (", ".join(gaps) if gaps else "none"))
        if receipt["mode"] == "paused":
            lines.append("Paused session: the writer hold remains until a triage is recorded and resume is run.")
        else:
            lines.append("Snapshot session: triage the report; there is no hold to resume.")
        if receipt["errors"]:
            lines.append("Collection incomplete: " + "; ".join(error["message"] for error in receipt["errors"]))
            lines.append("Partial evidence and the worktree are retained; inspect, resolve, and collect again.")
        lines.append(f"Next: triage --collection {result['collection']} --response <response.json> --actor <name>")
    elif command == "export":
        source = result["source"]
        lines += [f"Evidence package: {result['package']}",
                  f"Source: {source['kind']} {source['record']} (receipt {source['receipt_sha256']})"]
        for item in result["entries"]:
            lines.append(f"  {item['selector']} -> {item['file']} ({item['sha256']})")
        lines += ["Selection records custody; the receiving manager still assesses these claims.",
                  f"Next: init --audit-id <fresh-audit-id> --evidence-package {shlex.quote(result['package'])}"]
    elif command == "recover-runtime":
        lines += [f"Runtime assets recovered: {result['runtime']['root']}",
                  f"Recovery receipt: {result['path']}",
                  f"Runtime digest: {result['runtime']['sha256']}", *result["next_steps"]]
    elif command == "triage":
        record = result["record"]
        counts = record["counts"]
        lines += [
            f"Triage recorded: {result['path']}",
            f"Collection: {result['collection']} (receipt {record['collection_sha256'][:12]}…)",
            "Report: " + (f"bound to {record['report_sha256'][:12]}…" if record["report_sha256"]
                          else f"gap: {record['report_gap']}"),
            f"Claims: {counts['accepted']} accepted, {counts['rejected']} rejected, {counts['unresolved']} unresolved",
            f"Decision: {record['decision']}",
        ]
        if record["report_sha256"]:
            lines.append(f"Next: retain --triage {result['triage']} --report (publishes the reviewed bytes; no commit)")
        if result.get("mode") == "paused":
            lines.append("Paused session: resume --triage " + result["triage"] + " --reason <reason> releases the hold")
    elif command == "retain":
        lines.append("Retained:")
        for item in result["published"]:
            lines.append(f"  {item['path']} ({item['sha256'][:12]}…) from {item['source']}")
        lines += [f"Record: {result['path']}", "Nothing was staged or committed; review and commit separately."]
    elif command == "resume":
        lines += [f"Resume recorded: {result['path']}",
                  "Tell the writers; the tool controls no process."]
    elif command == "status":
        lines += _render_listing(result) if "sessions" in result else _render_status(result)
    elif command == "release":
        lines += [
            f"Release recorded: {result['path']}",
            "Frozen: " + ", ".join(f"{name} {digest[:12]}…" for name, digest in result["record"]["frozen"].items()),
            "Command: " + _shell({"argv": result["record"]["argv"], "env": result["record"]["environment"]}),
            f"Next: run --release {result['release']} (exactly one invocation is authorized)",
        ]
    elif command == "run":
        record = result["record"]
        process = record["process"]
        lines += [
            f"Attempt recorded: {result['path']}/ATTEMPT.json",
            f"Process: launched {process['launched']}, exit {process['exit_code']}, signal {process['signal']}, "
            f"timed out {process['timed_out']}, interrupted {process['interrupted']}",
            f"Endpoint preservation: {record['endpoint']['preserved']} "
            f"({len(record['endpoint']['changed'])} changed of {record['endpoint']['compared']} compared); "
            f"claim: {record['endpoint']['claim']}",
            f"Child receipt: {record['child_receipt']['state']}; stdout/stderr retained beside the attempt record",
        ]
        ledger = record.get("ledger") or {}
        for label, capture in (("Ledger", ledger.get("capture")),
                               ("Child receipt", record["child_receipt"].get("capture"))):
            if capture:
                lines.append(f"{label} capture: {capture['kind']}; retained {capture.get('retained')}; "
                             f"SHA-256 {capture.get('sha256')}")
        for population, counts in (ledger.get("summary") or {}).items():
            lines.append(f"Ledger {population}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
        if ledger.get("unmet"):
            lines.append("Measurement prerequisites unmet: " + "; ".join(ledger["unmet"]))
        if record["errors"]:
            lines.append("Attempt errors: " + "; ".join(record["errors"]))
        lines.append("A completed attempt is not a scientific conclusion; triage the retained rows and receipts.")
    return "\n".join(lines)


def _build(identity: dict | None) -> str:
    if not isinstance(identity, dict) or not identity.get("package_sha256"):
        return "unstamped"
    text = f"package {identity['package_sha256'][:12]}"
    if identity.get("commit"):
        text += f" at commit {identity['commit'][:12]}"
    if identity.get("dirty"):
        text += " (package dirty)"
    return text


def _render_attention(code: int, items: list[dict]) -> list[str]:
    if code == EXIT_OK:
        return ["Status exit 0: nothing needs attention"]
    lines = [f"Status exit {code}: " + ("records or bytes do not verify" if code == 3 else "needs attention")]
    lines += [f"  [{item['code']}] {item['source']}: {item['reason']}: {item['message']}" for item in items]
    return lines


def _render_listing(listing: dict) -> list[str]:
    lines = [f"Sessions of workspace {listing['workspace']['rel']}: {len(listing['sessions'])}"]
    for entry in listing["sessions"]:
        if "problem" in entry:
            lines.append(f"  {entry['audit_id']} [{entry['exit_code']}]: {entry['problem']['reason']}: "
                         f"{entry['problem']['message']}")
            continue
        lock = entry.get("lock") or {}
        lines.append(f"  {entry['audit_id']} [{entry['exit_code']}]: preparation {entry['preparation']}; "
                     f"collections {entry['collections']}; owner {entry['owner']}")
        lines.append(f"    checkout {entry['checkout']}" + ("; locked" if lock.get("locked") else ""))
    storage = listing["manager_storage"]
    lines.append(f"Manager write locations: {storage['private']}; checkout home {storage['checkout_home']}")
    return [*_render_attention(listing["exit_code"], []), *lines]


def _render_status(view: dict) -> list[str]:
    session = view["session"]
    same = session.get("same_build_as_viewer")
    lines = [*_render_attention(view["exit_code"], view["attention"]),
             f"Audit {view['audit_id']} in workspace {view['workspace']['rel']}",
             f"Session: {session['path']} (schema {session['schema_version']}, "
             f"{'supported' if session['supported'] else 'NOT supported'})",
             f"Stewart: this view by {_build(view.get('tool'))}; session written by {_build(session.get('stewart'))}"
             + (" (same build)" if same is True else
                " (DIFFERENT build: another checkout's copy of the tool wrote or is reading these records)"
                if same is False else "")]
    lines += [f"Preparation: {view['preparation']['state']}",
              f"Experiment: {view['experiment']['state']} (recorded phase, not a scientific conclusion)"]
    for problem in view["session"]["problems"]:
        lines.append(f"  problem [{problem['reason']}] {problem['record']}: {problem['message']}")
    if "pristine_runtime_available" in view["preparation"]:
        lines.append("Pristine runtime assets: " + ("verified" if view["preparation"]["pristine_runtime_available"] else "unavailable or invalid"))
        recovery = view["preparation"].get("runtime_recovery")
        if recovery:
            lines += ["Asset recovery to a fresh path (existing commands/scopes remain unchanged):", "  " + _shell(recovery)]
    for item in view["runtime_recoveries"]:
        lines.append(f"Runtime recovery {item['name']}: {item['state']} ({item['path']})")
        for problem in item["problems"]:
            lines.append(f"  problem [{problem['reason']}]: {problem['message']}")
    identities = view.get("identities") or {}
    if identities:
        worktree = identities["worktree"]
        lines += [
            f"Prompt commit {identities['prompt_commit'][:12]}; target {str(identities.get('target_commit'))[:12]}",
            f"Worktree: {'present' if worktree['exists'] else 'absent'}; HEAD matches prompt: {worktree['head_matches_prompt']}",
            f"Worktree path: {worktree['path']}",
            f"Launch handoff path: {view['preparation']['launch_path']} ({view['preparation']['launch_handoff']['kind']})",
            f"Checkout lock: {(worktree.get('lock') or {}).get('reason') or 'not locked'} "
            "(removal goes through close; Stewart prints no unlock or remove commands)",
            f"Maintainer status changed since prepare: {identities['maintainer']['status_changed_since_prepare']}; "
            f"report destination exists in maintainer checkout: {identities['report_destination_exists']}",
        ]
    storage = view.get("manager_storage")
    if storage:
        lines.append(f"Manager write locations: {storage['private']}; checkout home {storage['checkout_home']}")
    coordination = view.get("coordination") or {}
    if coordination:
        paused = coordination["writers_paused"]
        lines.append(f"Coordination: {coordination['mode']}; writers paused acknowledged: {paused['acknowledged']}"
                     + (f" ({paused['by']})" if paused.get("by") else "") + f"; {coordination['hold']}")
        if paused.get("note"):
            lines.append(f"  pause note: {paused['note']}")
        if coordination.get("resumed"):
            lines.append(f"  resumed at {coordination['resumed']['at']} via triage {coordination['resumed']['triage']}")
    profile = view.get("launch_profile")
    if profile:
        lines.append(f"Launch profile: {profile['path']} ({profile['sha256'][:12]}…) pinned at preparation; "
                     f"harness {profile['harness']}, {profile['style']}, model {profile['model']}, effort {profile['effort']}"
                     + ("; probe present" if profile.get("has_probe") else "; no probe"))
    override = view.get("launch_profile_override")
    if override:
        lines.append(f"Launch profile override: {override['path']} ({override['sha256'][:12]}…) from the working tree; "
                     f"harness {override['harness']}, model {override['model']}, effort {override['effort']}")
    exits = view.get("harness_exits") or []
    if exits:
        last = exits[-1]
        lines.append(f"Harness exits: {len(exits)} recorded by the launch block; last exit {last['exit']} at {last['at']} "
                     "(the harness process, not the auditor)")
    lines.append(f"Launches: {len(view['launches'])} (manager acknowledgments, not observations)")
    for item in view["launches"]:
        if item["problems"]:
            lines.append(f"  {item['name']}: " + "; ".join(p["message"] for p in item["problems"]))
        else:
            lines.append(f"  {item['name']} by {item['actor']}: {item['style']}, model {item['model']}, "
                         f"effort {item['effort']}" + (f"; {item['note']}" if item.get("note") else ""))
    lines.append(f"Messages: {len(view['messages'])} (as relayed by the manager)")
    for item in view["messages"]:
        if item["problems"]:
            lines.append(f"  {item['name']}: " + "; ".join(p["message"] for p in item["problems"]))
        else:
            text = item["text"].replace("\n", " ")
            lines.append(f"  {item['name']} {item['direction']} by {item['actor']}: "
                         + (text if len(text) <= 120 else text[:117] + "..."))
    lines.append(f"Collections: {len(view['collections'])}")
    for c in view["collections"]:
        if c["complete"]:
            lines.append(f"  {c['name']}: report {c['report_status']}; git {c['git_discovery']}; "
                         f"errors {len(c['errors'])}; gaps {len(c['gaps'])}; "
                         f"auditor stopped acknowledged: {c['auditor_stopped']['acknowledged']}; "
                         f"stop kind: {c['auditor_stopped']['kind']} ({c['auditor_stopped']['by']})")
        else:
            lines.append(f"  {c['name']}: receipt not usable; see problems")
        lines.append(f"    Captured report location: {c['report_path']} (availability is described by the collection above)")
        for problem in c["problems"]:
            lines.append(f"    problem [{problem['reason']}] {problem['record']}: {problem['message']}")
    completion = view["auditor_reported"]["completion"]
    lines.append(f"Auditor-reported completion: {completion['value'] or 'unavailable'}"
                 + (f" ({completion['source']})" if completion.get("source") else "")
                 + "; attributed to the auditor, not observed")
    kind = view["auditor_reported"]["report_kind"]
    kind_label = kind["value"] or ("unset" if kind.get("validation", {}).get("status") == "valid" else "unavailable")
    lines.append(f"Auditor-reported kind: {kind_label}; attributed to the auditor, not a maintainer judgment")
    # Declaration diagnostics outlive triage: a disposition explains a gap but
    # does not make its underlying observation disappear from human status.
    validation = completion.get("validation")
    if validation:
        lines.append(f"  declaration validation: {validation['status']}")
        for diagnostic in validation["diagnostics"]:
            lines.append(f"  declaration [{diagnostic['reason']}]: {diagnostic['message']}")
            comparison = validation["comparisons"].get(diagnostic.get("field"))
            if comparison:
                lines.append(f"    expected {comparison['expected']!r}; observed {comparison['observed']!r}; "
                             f"source: {comparison['source']}")
    elif completion.get("reason"):
        lines.append(f"  declaration [{completion['reason']}]: completion unavailable from captured evidence")
    lines.append(f"Dispositions: {len(view['dispositions'])}")
    for d in view["dispositions"]:
        if d["problems"]:
            lines.append(f"  {d['name']}: " + "; ".join(p["message"] for p in d["problems"]))
        else:
            lines.append(f"  {d['name']} by {d['actor']} on collection {d['collection']}: {d['decision']}")
            if d.get("follow_up"):
                follow_up = d["follow_up"]
                lines.append(f"    Follow-up {follow_up['report_kind']}: {follow_up['disposition']}; "
                             f"{follow_up['reason']} (no new grant)")
    lines.append(f"Retentions: {len(view['retentions'])}; releases: {len(view['releases'])}; attempts: {len(view['attempts'])}")
    for release in view["releases"]:
        if release["problems"]:
            lines.append(f"  release {release['name']}:")
            for problem in release["problems"]:
                lines.append(f"    problem [{problem['reason']}] {problem['record']}: {problem['message']}")
            continue
        captured = release.get("captured_in") or []
        lines.append(f"  release {release['name']}: frozen artifacts verified recoverable in "
                     + (", ".join(captured) if captured else "no collection")
                     + (f"; unverified: {', '.join(release['uncaptured_artifacts'])}"
                        if release.get("uncaptured_artifacts") else "")
                     + ("; consumed" if release.get("consumed") else "; not yet run"))
        for problem in release["capture_problems"]:
            lines.append(f"    capture {problem['collection']} {problem['artifact']}: "
                         f"{problem['reason']}: {problem['message']}")
    for attempt in view["attempts"]:
        # Render the actual read diagnostics: an unusable receipt is not
        # evidence that a reserved operation never wrote its completed record.
        if attempt["problems"]:
            lines.append(f"  attempt {attempt['name']}:")
            for problem in attempt["problems"]:
                lines.append(f"    problem [{problem['reason']}] {problem['record']}: {problem['message']}")
    if view["outstanding"]:
        lines.append("Outstanding:")
        lines += [f"  - {item}" for item in view["outstanding"]]
    if view["next_actions"]:
        lines.append("Next actions:")
        for action in view["next_actions"]:
            if action["action"] == "handoff":
                lines += ["  handoff: manual, if not already handed off",
                          f"    working directory: {action['cwd']}",
                          f"    first prompt: {action['prompt']}"]
                if action.get("probe"):
                    lines.append("    probe first (expect 'probe exit 0'):")
                    lines += ["    " + line for line in action["probe"].splitlines()]
                if action.get("command"):
                    lines.append(f"    terminal command (from the {action.get('profile_source', 'pinned')} launch profile):")
                    lines += ["    " + line for line in action["command"].splitlines()]
                    lines.append(f"    the harness's exit code is appended to {action['exit_log']} when it ends")
            else:
                lines.append(f"  {action['action']}: {_shell(action)}")
            if action.get("external"):
                lines.append(f"    external: {action['external']}")
            for prerequisite in action.get("prerequisites", []):
                lines.append(f"    requires: {prerequisite}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw = list(sys.argv[1:] if argv is None else argv)
    envelope: dict = {"schema": RESULT_SCHEMA, "command": None, "ok": False,
                      "exit_code": EXIT_REFUSED, "result": None, "error": None}
    try:
        args = parser.parse_args(raw)
        envelope["command"] = args.command
        if args.command == "docs":
            from stewart.docs import document
            result, code = document(args.document), EXIT_OK
        else:
            missing = [flag for flag in ("repo", "workspace") if getattr(args, flag) is None]
            if missing:
                parser.error("the following arguments are required: " + ", ".join("--" + flag for flag in missing))
            repo = Path(args.repo).resolve()
            ws = workspace(repo, args.workspace)
            try:
                result, code = dispatch(ws, args)
            except PermissionError as exc:
                raise _manager_grant(ws, exc) from exc
        # ``ok`` means exit 0: a result that needs attention still carries its
        # result document, but it is not "ok".
        envelope.update(ok=code == EXIT_OK, exit_code=code, result=result)
        if args.json:
            print(json.dumps(envelope, indent=2, sort_keys=True))
        elif args.command == "docs":
            print(result["text"], end="")
        elif args.command == "triage-draft":
            print(json.dumps(result["response"], indent=2))
            context = result["context"]
            print(f"Collection {context['collection']}: {context['note']}", file=sys.stderr)
            print(f"Report status: {context['report_status']}", file=sys.stderr)
            # The same comparisons status renders: one line per identity field,
            # readable without parsing, so a mismatch is visible at a glance.
            declaration = context.get("declaration") or {}
            print(f"Declaration validation: {declaration.get('status', 'unavailable')}", file=sys.stderr)
            kind_label = context["report_kind"] or ("unset" if declaration.get("status") == "valid" else "unavailable")
            print(f"Auditor-reported kind: {kind_label}", file=sys.stderr)
            if context["follow_up_choices"]:
                print("Follow-up response required: accept, decline, or defer with a reason; grants no new scope.", file=sys.stderr)
            for field, comparison in sorted((declaration.get("comparisons") or {}).items()):
                print(f"  {field}: {'matches' if comparison.get('matches') else 'MISMATCH'}; "
                      f"expected {comparison.get('expected')!r}; observed {comparison.get('observed')!r}; "
                      f"source: {comparison.get('source')}", file=sys.stderr)
            for diagnostic in declaration.get("diagnostics") or []:
                print(f"  declaration [{diagnostic.get('reason')}]: {diagnostic.get('message')}", file=sys.stderr)
            for gap in context["custody_gaps"]:
                print(f"{gap['id']}: {gap['description']}", file=sys.stderr)
        else:
            print(render(args.command, result))
        return code
    except StewartError as exc:
        envelope["error"] = exc.to_json()
        envelope["exit_code"] = exc.exit_code
    except (OSError, ValueError, subprocess.TimeoutExpired, tarfile.TarError) as exc:
        envelope["error"] = {"reason": "failed", "message": f"{type(exc).__name__}: {exc}",
                             "retained": [], "next_steps": []}
    if "--json" in raw:
        print(json.dumps(envelope, indent=2, sort_keys=True))
    else:
        error = envelope["error"]
        print(f"Refused ({error['reason']}): {error['message']}", file=sys.stderr)
        for item in error["retained"]:
            print(f"Retained: {item}", file=sys.stderr)
        for item in error["next_steps"]:
            print(f"Next: {item}", file=sys.stderr)
    return envelope["exit_code"]
