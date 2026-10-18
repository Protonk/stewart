"""Prepare a disposable detached checkout for one committed assignment.

Preparation validates the prompt commit's shape and ancestry, pins the audited
inputs, creates the private session and the worktree, copies the selected
supplemental bytes, and writes a launch handoff. It launches nothing and grants
nothing: coordination mode is a recorded acknowledgment, not process control.
"""

from __future__ import annotations

import os
import secrets
import shlex
import sys
import uuid
from pathlib import Path

from stewart import _util as _hash
from stewart import assignment as _assignment
from stewart._bootstrap import StewartError, write_exclusive
from stewart._git import git, git_text, resolve_commit
from stewart.launch_profile import EXIT_LOG, load_profile, render_command, render_probe
from stewart.report_declaration import SCHEMA_VERSION as DECLARATION_SCHEMA
from stewart.runtime import helper_argv, retain_runtime, select_runtime
from stewart.auditor_scope import scope_for
from stewart._invocation import current
from stewart.session import SESSION_SCHEMA, maintainer_state, now, tool_identity, write_receipt
from stewart._repository import LOCK_PREFIX, maintainer, register_auditor, require_private_exclusions, retention_for, retain_commits
from stewart.workspace import Workspace, contained


def prepare(ws: Workspace, revision: str, *, mode: str = "snapshot", writers_paused: bool = False,
            pause_note: str | None = None) -> dict:
    """Validate a prompt-only commit and build its session; return the session facts.

    Helpers are supplied from the selected distribution, independently of
    project history. Their pristine private assets and exposed runtime are
    verified before the public handoff is written. Preparation executes no
    project code and never grants access to the private session parent.

    A paused session records who was paused and how in ``pause_note``; the flag
    alone would say only that someone claimed a pause.
    """
    repo = ws.repo
    repository = maintainer(repo)
    require_private_exclusions(repo)
    if mode not in {"snapshot", "paused"}:
        raise StewartError("mode must be snapshot or paused", reason="mode")
    if mode == "paused" and not writers_paused:
        raise StewartError(
            "paused mode requires an actual writer pause, then --writers-paused", reason="pause_unacknowledged",
        )
    if mode == "snapshot" and (writers_paused or pause_note is not None):
        raise StewartError("--writers-paused and --pause-note require --mode paused", reason="mode")
    if mode == "paused" and (not isinstance(pause_note, str) or not pause_note.strip()):
        raise StewartError(
            "paused mode requires --pause-note naming which writers were paused and how the pause was arranged",
            reason="pause_note_required",
            next_steps=["arrange the pause with every affected writer first; then acknowledge it with "
                        "--writers-paused --pause-note 'who was paused, how, and who else still writes'"],
        )
    prompt_commit = resolve_commit(repo, revision, exact=False)
    parents = git_text(repo, "rev-list", "--parents", "-n", "1", prompt_commit).split()
    if len(parents) != 2:
        raise StewartError("prompt commit must be a normal one-parent commit", reason="prompt_commit_shape")
    changed = git(repo, "diff", "--name-only", "--no-renames", "-z", parents[1], prompt_commit).stdout
    if changed.split(b"\0") != [ws.prompt.encode(), b""]:
        raise StewartError(f"prompt commit must change {ws.prompt} alone", reason="prompt_commit_shape")
    prompt_bytes = git(repo, "show", f"{prompt_commit}:{ws.prompt}").stdout
    if contained(repo, ws.prompt).read_bytes() != prompt_bytes:
        raise StewartError("working PROMPT.md differs from the chosen prompt commit", reason="prompt_drift")
    meta = _assignment.expand_input_manifest(ws, _assignment.prompt_metadata(prompt_bytes.decode("utf-8"), ws))
    target = resolve_commit(repo, meta["target_commit"])
    if meta.get("base_commit") is not None:
        resolve_commit(repo, meta["base_commit"])
    if git(repo, "merge-base", "--is-ancestor", target, prompt_commit, check=False).returncode:
        raise StewartError("target_commit must be an ancestor of the prompt commit", reason="target_ancestry")
    intervening = {
        name
        for name in os.fsdecode(
            git(repo, "diff", "--name-only", "--no-renames", "-z", target, prompt_commit).stdout
        ).split("\0")
        if name
    }
    if any(not name.startswith(ws.rel + "/") for name in intervening):
        raise StewartError(
            "target bytes changed outside the workspace between target and prompt commits",
            reason="target_drift",
        )
    # Audit material may be added after the target, but an audited input must be
    # target bytes even when it lives inside the workspace. Without this, a
    # workspace placed over implementation would let a later edit pose as audit
    # material and be read as if it were the audited revision.
    drifted = sorted(set(meta["input_files"]) & intervening)
    if drifted:
        raise StewartError(
            "assigned inputs changed between target and prompt commits: " + ", ".join(drifted)
            + "; choose a target that contains the bytes to audit",
            reason="input_drift",
        )
    for name in ws.guidance_files():
        entry = git_text(repo, "ls-tree", prompt_commit, "--", name)
        if not entry.startswith("100644 blob "):
            raise StewartError(
                f"committed {name} must be a regular guidance/assignment file", reason="workspace_guidance",
            )
    report = contained(repo, meta["report_path"])
    if (
        report.exists()
        or git(repo, "cat-file", "-e", f"{prompt_commit}:{meta['report_path']}", check=False).returncode == 0
    ):
        raise StewartError(
            "report destination already exists; choose a fresh audit ID", reason="destination_exists",
        )
    receipts = _assignment.input_receipts(repo, meta, prompt_commit)
    # The launch profile is manager-side data pinned here so that a later edit
    # cannot change what this session prints or records. A broken profile is a
    # refusal before any session exists, not a surprise at paste time.
    launch_profile = load_profile(ws)
    session = contained(repo, ws.session(meta["audit_id"]))
    if session.exists():
        raise StewartError(f"session already exists: {session}; choose a fresh audit ID",
                           reason="destination_exists", retained=[str(session)])
    worktree = session / "worktree"
    session_identity = str(uuid.uuid4())
    retention = retention_for(session_identity, prompt_commit, target, meta.get("base_commit"))
    selected_runtime = select_runtime(contained(repo, f".scratch/stewart-runtimes/{session_identity}"))
    record = {
        "schema_version": SESSION_SCHEMA,
        "session_uuid": session_identity,
        "runtime": selected_runtime["identity"],
        "runtime_assets": selected_runtime["assets"],
        "helper_interpreter": current().interpreter,
        "retention": retention,
        "report_declaration_schema": DECLARATION_SCHEMA,
        "workspace": ws.rel,
        "workspace_slug": ws.slug,
        "assignment": meta,
        "target_commit": target,
        "prompt_commit": prompt_commit,
        "prompt_sha256": _hash.sha256_bytes(prompt_bytes),
        "launch_token": secrets.token_hex(8),
        "repo": str(repo),
        "worktree": str(worktree),
        "prepared_at": now().isoformat(),
        "mode": mode,
        "writers_paused": writers_paused,
        "writers_paused_acknowledged_by": "maintainer via --writers-paused" if writers_paused else None,
        "writers_paused_note": pause_note if writers_paused else None,
        "maintainer_before": maintainer_state(repo),
        "inputs": receipts,
        "common_dir": repository["common_dir"],
        "maintainer_git_admin": repository["git_admin"],
        "launch_profile": launch_profile,
        "stewart": tool_identity(),
    }
    from stewart._repository import custody_roots
    record["auditor_scope"] = scope_for(record, manager_home=current().launcher.parent.parent,
                                        interpreter_prefix=Path(sys.prefix).resolve(),
                                        private_roots=custody_roots(repo, repository["common_dir"]))
    launch = _render_handoff(ws, record)
    record["handoff"] = {"path": f"{ws.rel}/.stewart-handoffs/{session_identity}.md",
                         "sha256": _hash.sha256_bytes(launch.encode("utf-8"))}
    try:
        session.mkdir(parents=True, mode=0o700, exist_ok=False)
    except FileExistsError:
        raise StewartError(
            f"session already exists: {session}; choose a fresh audit ID", reason="destination_exists",
            retained=[str(session)],
        ) from None
    write_receipt(session / "session.json", record)
    stage = "retention"
    worktree_add_completed = False
    try:
        retain_commits(repo, retention)
        stage = "worktree"
        git(repo, "worktree", "add", "--detach", "--lock", "--reason", LOCK_PREFIX + session_identity,
            str(worktree), prompt_commit)
        worktree_add_completed = True
        stage = "role"
        register_auditor(repo, worktree, session)
        git(repo, "worktree", "unlock", str(worktree))
        stage = "inputs"
        for item in meta["supplemental_inputs"]:
            _assignment.copy_supplemental(repo, worktree, item)
        for item in _assignment.observe_inputs(worktree, receipts):
            if not item["matches"]:
                raise StewartError(
                    f"checked-out input differs from its receipt: {item['path']}", reason="input_mismatch",
                )
        # Make the output parent, but leave the report itself for the auditor.
        contained(worktree, meta["report_path"]).parent.mkdir(parents=True, exist_ok=True)
        notes = ws.scratch_prefix(meta["audit_id"]) + "notes"
        if notes in meta["scratch_paths"]:
            contained(worktree, notes).mkdir(parents=True, exist_ok=True)
        stage = "runtime"
        retain_runtime(session, selected_runtime)
        stage = "handoff"
        write_exclusive(session / "LAUNCH.md", launch.encode("utf-8"))
        public_handoff = contained(worktree, record["handoff"]["path"])
        public_handoff.parent.mkdir(parents=True, exist_ok=True)
        write_exclusive(public_handoff, launch.encode("utf-8"))
    except Exception as exc:
        failure_path = session / "PREPARE-ERROR.json"
        write_receipt(failure_path, {
            "error": str(exc), "reason": getattr(exc, "reason", "prepare_failed"), "stage": stage,
            "worktree_add_completed": worktree_add_completed,
            "worktree_exists_after_failure": worktree.is_dir(),
            "cleanup_performed": False,
            "stewart": record["stewart"],
        })
        raise StewartError(
            f"preparation failed during {stage}: {exc}", reason="prepare_failed",
            retained=[str(session), str(failure_path)],
            next_steps=[
                "inspect PREPARE-ERROR.json and preserve any partial worktree; no launch handoff was completed",
                "correct the reported cause (Git administration writes may require harness authorization)",
                "initialize a fresh audit ID, author and commit its prompt alone, then prepare it; "
                "this session is retained and cannot be retried in place",
                "a recorded writer pause still needs explicit coordination; preparation failure releases no hold",
            ],
        ) from exc
    return {
        "audit_id": meta["audit_id"],
        "session_uuid": session_identity,
        "retention": retention,
        "session": str(session),
        "worktree": str(worktree),
        "launch": str(worktree / record["handoff"]["path"]),
        "private_launch": str(session / "LAUNCH.md"),
        "runtime": record["runtime"],
        "auditor_scope": record["auditor_scope"],
        "prompt_commit": prompt_commit,
        "target_commit": target,
        "prompt_sha256": record["prompt_sha256"],
        "launch_token": record["launch_token"],
        "mode": mode,
        "writers_paused": writers_paused,
        "writers_paused_note": record["writers_paused_note"],
        "launch_profile": None if launch_profile is None else {
            "path": launch_profile["path"], "sha256": launch_profile["sha256"],
            "harness": launch_profile["profile"]["harness"], "style": launch_profile["profile"]["style"],
            "model": launch_profile["profile"]["model"], "effort": launch_profile["profile"]["effort"],
        },
        "launch_command": None if launch_profile is None else render_command(
            launch_profile["profile"], worktree=worktree, launch_path=worktree / record["handoff"]["path"],
            exit_log=session / EXIT_LOG, scope=record["auditor_scope"]),
        "probe_command": None if launch_profile is None else render_probe(
            launch_profile["profile"], worktree=worktree, launch_path=worktree / record["handoff"]["path"], scope=record["auditor_scope"]),
        "exit_log": str(session / EXIT_LOG),
    }


def _render_handoff(ws: Workspace, record: dict) -> str:
    """Render auditor instructions without granting the private session parent."""
    meta = record["assignment"]
    worktree = Path(record["worktree"])
    prompt_commit, target, mode = record["prompt_commit"], record["target_commit"], record["mode"]
    def helper_command(module, *extra):
        argv = helper_argv(record["runtime"], record["helper_interpreter"], module, *extra,
                "--workspace", ws.rel, "--expected-worktree", str(worktree),
                "--launch-prompt-commit", prompt_commit, "--prompt-sha256", record["prompt_sha256"],
                "--launch-token", record["launch_token"])
        return f"cd {shlex.quote(str(worktree))} && " + shlex.join(argv)

    launch = (
        f"# Launch audit {meta['audit_id']}\n\n"
        "You are the auditor for this assignment. Your role is independent of the model or harness.\n\n"
        f"Start a fresh auditor thread in this detached worktree:\n\n{worktree}\n\n"
        f"Read `{ws.auditor_guidance}` first, then `{ws.prompt}`.\n"
        f"Prompt and checkout commit: `{prompt_commit}`.\n"
        f"Audited target commit: `{target}`. Differences are confined to audit material.\n"
        f"Prompt SHA-256: `{record['prompt_sha256']}`.\n"
        f"Launch token: `{record['launch_token']}` (agreement with this handoff, not proof of reading or security).\n"
        f"Coordination mode: `{mode}`.\n"
        f"Write the report to `{meta['report_path']}` inside that worktree.\n"
        "If your harness did not start inside that worktree, use absolute paths rooted there for "
        "every project read, search and write. The separately supplied runtime below is the only extra code-reading scope.\n"
    )
    launch += (
        "\nDeclared writable scratch paths (absolute; create files only within the assigned scope):\n"
        + ("".join(f"- `{contained(worktree, rel)}`\n" for rel in meta["scratch_paths"]) or "- None declared.\n")
        + "Use declared notes directories for prose, checksum lists and read-only verification output. "
        "Do not place agent-authored temporary files in the harness scratchpad or elsewhere outside the checkout. "
        "The supplied helpers may allocate their fresh private cache directory in system temporary storage. "
        "This grants no experiment construction or execution.\n"
    )
    launch += (
        "\nVerify supplied input bytes without writing files (not scientific validation or a reading attestation):\n\n```sh\n"
        + helper_command("inputs") + "\n```\n"
        "Add `--print` for every expected/observed digest, or `--json` for one result document. "
        "Each failed row names its fix.\n"
        "\nEvery helper uses the same exit codes. 0: nothing to change. 1: change what is listed, then run it again. "
        "2: refused, nothing done; copy the issued command exactly. 3: something you cannot repair does not verify; "
        "describe it in the report, declare, and stop. Completion and report kind never change the code.\n"
        "\nThe narrow declaration helper commands below, and their --help, are authorized. "
        "The read-only input verifier above and its --help are also authorized. "
        "Other execution requires its own grant. Keep completion qualifications in prose.\n\n"
        "Create the partial skeleton before analysis:\n\n```sh\n"
        + helper_command("declaration", "start") + "\n```\n\n"
        "After editing the report, choose completion (partial, complete, or blocked) and report kind "
        "(answer, needs-evidence, or reframe). The command below illustrates an ordinary answer; "
        "replace its kind for an evidence request or proposed reframe. A complete report must choose a kind. "
        "Explain the request or proposal in prose; it grants no new reading, construction or execution scope.\n\n```sh\n"
        + helper_command("declaration", "set", "--completion", "complete",
                         "--report-kind", "answer") + "\n```\n\n"
        "Run check as the last action before stopping. It reports, without writing, everything a collection "
        "of this checkout would ask you to fix; exit 0 means nothing:\n\n```sh\n"
        + helper_command("declaration", "check", "--print") + "\n```\n"
    )
    root = record["runtime"]["root"]
    launch += (
        f"\nSupplied runtime (read-only): `{root}`.\n"
        f"Complete runtime SHA-256: `{record['runtime']['sha256']}`.\n"
        f"Helper protocol: `{record['runtime']['protocols']['helpers']}`.\n"
        "Read this exact subtree, never its parent or the private session directory. "
        "It contains the complete Stewart distribution, including manager CLI code; "
        "only the issued helper operations are authorized. Do not run manager operations.\n"
        f"Bundled question guide: `{root}/stewart/resources/QUESTION-TYPE.md`.\n"
        f"Bundled conditional protocols: `{root}/stewart/resources/AUDIT-PROTOCOLS.md`.\n"
        f"Bundled custody manual: `{root}/stewart/resources/README.md`.\n"
        "Read only the assigned sections. These documents supply no additional capability grant.\n"
        "Configure the harness with read-only runtime access, worktree access, and denied access "
        "to private receipts, role records and manager runtime storage. The manager's scope profile "
        "supplies the required shell and file-tool restrictions. A manual handoff needs equivalent "
        "explicit harness configuration. Reading this handoff grants no broader filesystem access.\n"
    )
    if meta.get("experiment") is not None:
        launch += (
            f"\nThe granted Python experiment uses `from {record['runtime']['protocols']['ledger']} import Ledger`. "
            "The manager's private launcher loads that pinned ledger before the script directory and worktree root "
            "enter the child's import path. Do not create a project module under the reserved ledger name. "
            "Preloaded standard-library modules keep their bindings. The supplied ledger is available only in "
            "the initial process; keep ledger imports/writes there, guarded by `if __name__ == \"__main__\":` "
            "when using multiprocessing spawn. "
            "Construction alone still grants no execution; the manager releases and runs the reviewed command.\n"
        )
    return launch
