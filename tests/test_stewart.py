"""Audit custody against real disposable Git repositories, without an auditor.

Controls vary commit membership independently of bytes, preserve dirty main
state, and plant unexpected staged/ignored/committed output before collection.
These contracts were carried over from the workspace-local helper this package
replaced; the migration and API controls at the end are new. The other
``test_stewart_*`` files own the session view, triage and retention, the
filesystem inventory, the caller contract and the experiment wrapper.
"""

from __future__ import annotations

from datetime import timedelta
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile

import pytest

from stewart import _util as _hash
import stewart
from stewart import collect as collect_mod
from stewart import session as session_mod
from stewart.assignment import initialize, prompt_metadata
from stewart.collect import collect
from stewart._bootstrap import StewartError
from stewart.prepare import prepare
from stewart.status import status
from stewart.triage import resume, triage
from stewart.workspace import workspace
import stewart_support as support
from stewart_support import WS, assignment_text, read_json, response_for

INSTALLED_LIB = Path(stewart.__file__).parent.parent
pytestmark = pytest.mark.system


def cli_base(checkout, *, ws_rel: str = WS) -> list[str]:
    return [sys.executable, "-I", "-B", "-m", "stewart", "--repo", str(checkout.repo), "--workspace", ws_rel]


def test_initializer_pins_inputs_without_summarizing_or_launching_them(checkout):
    repo, ws, meta, git = checkout.repo, checkout.ws, checkout.meta, checkout.git
    original = (repo / ws.prompt).read_bytes()
    (repo / "input.txt").write_text("dirty live input, excluded from the audit\n")
    git("add", "input.txt")
    selected = repo / "ignored/specimen.bin"
    selected.parent.mkdir()
    selected.write_bytes(b"selected\x00bytes")
    before = git("status", "--porcelain=v1")
    result = initialize(
        ws, "independent-question", "HEAD", inputs=["input.txt"], base="HEAD",
        sources=[("https://example.invalid/spec", "Check the declared contract")],
        supplemental=[("ignored/specimen.bin", "Authored specimen")],
        scratch=[f"{WS}/scratch/independent-question/notes"],
    )
    draft = result["draft"]
    assert result["written"] is None, "without replace_prompt nothing is written"
    assert (repo / ws.prompt).read_bytes() == original
    assert git("status", "--porcelain=v1") == before
    assert not (repo / ".git/stewart").exists()
    with pytest.raises(StewartError, match="unassigned") as refused:
        prompt_metadata(draft, ws)
    assert refused.value.reason == "unassigned_prompt"
    authored = "\n".join(line for line in draft.splitlines() if not line.startswith("**UNASSIGNED"))
    with pytest.raises(StewartError, match="Question"):
        prompt_metadata(authored, ws)
    # Author the substantive fields independently of the initializer's metadata.
    for title, body in (
        ("Question", "Does the value survive the reader boundary?"),
        ("Decision", "Whether to change the reader."),
        ("Scope and exclusions", "Follow readers of input.txt; exclude unrelated routes."),
        ("Evidence", "input.txt is primary evidence; the specimen is an authored control."),
        ("Stop condition", "Identify the first loss or the evidence needed to resolve it."),
    ):
        authored = authored.replace(f"## {title}", f"## {title}\n{body}")
    generated = prompt_metadata(authored, ws)
    assert generated["target_commit"] == generated["base_commit"] == meta["target_commit"]
    assert generated["report_path"] == ws.report_path("independent-question")
    assert generated["supplemental_inputs"] == [{
        "path": "ignored/specimen.bin", "provenance": "Authored specimen",
        "sha256": _hash.sha256_bytes(b"selected\x00bytes"),
    }]
    (repo / ws.prompt).write_text(authored)
    git("add", "--", ws.prompt)
    git("commit", "--only", "-qm", "Authored initialized assignment", "--", ws.prompt)
    prepared = prepare(ws, git("rev-parse", "HEAD"))
    session = Path(prepared["session"])
    assert (Path(prepared["worktree"]) / "input.txt").read_bytes() == b"committed input\n"
    assert (Path(prepared["worktree"]) / "ignored/specimen.bin").read_bytes() == selected.read_bytes()
    assert git("show", ":input.txt") == "dirty live input, excluded from the audit"


@pytest.mark.parametrize("fault", ["missing", "directory", "symlink", "collision", "source"])
def test_initializer_validation_preserves_existing_prompt(checkout, fault):
    repo, ws = checkout.repo, checkout.ws
    prompt = repo / ws.prompt
    prompt.write_text("Existing assignment must survive a refused replacement.\n")
    before = prompt.read_bytes()
    candidate = repo / "specimen"
    options = {"inputs": ["input.txt"], "replace_prompt": True}
    if fault == "directory":
        candidate.mkdir()
    elif fault == "symlink":
        candidate.symlink_to(repo / "input.txt")
    elif fault == "collision":
        candidate = repo / "input.txt"
    if fault == "source":
        options["sources"] = [("http://example.invalid/spec", "not HTTPS")]
    else:
        options["supplemental"] = [(candidate.name, "Selected input")]
    with pytest.raises(StewartError):
        initialize(ws, "new-question", "HEAD", **options)
    assert prompt.read_bytes() == before
    assert not (repo / ".git/stewart").exists()


def test_initializer_cli_preview_and_full_replacement(checkout, run_cmd):
    repo, ws, meta, git = checkout.repo, checkout.ws, checkout.meta, checkout.git
    prompt = repo / ws.prompt
    prompt.write_text("Earlier assignment text must not accumulate.\n")
    before = prompt.read_bytes()
    base = [*cli_base(checkout), "init", "--audit-id", "fresh-question", "--input", "input.txt"]
    env = {"PYTHONPATH": str(INSTALLED_LIB)}
    preview = run_cmd(base, cwd=INSTALLED_LIB, env=env, check=True)
    assert prompt.read_bytes() == before
    assert meta["target_commit"] in preview.stdout
    assert '"report_path":' in preview.stdout and "UNASSIGNED" in preview.stdout
    replaced = run_cmd([*base, "--replace-prompt"], cwd=INSTALLED_LIB, env=env, check=True)
    assert "Unassigned draft written" in replaced.stdout
    assert prompt.read_text() == preview.stdout.rstrip("\n") + "\n"
    assert "Earlier assignment" not in prompt.read_text()
    assert git("diff", "--cached", "--name-only") == ""
    # The draft is recorded at repository level: its intent before the write, its outcome after.
    records = list((repo / ".git/stewart/audits").glob("*/fresh-question/init/*"))
    assert len(records) == 1 and {path.name for path in records[0].iterdir()} == {"STARTED.json", "OUTCOME.json"}
    started = read_json(records[0] / "STARTED.json")
    assert started["intended"][0]["sha256"] == _hash.sha256_bytes(prompt.read_bytes())
    assert started["prompt_before"]["sha256"] == _hash.sha256_bytes(before)
    assert read_json(records[0] / "OUTCOME.json")["status"] == "completed"


def test_prepare_uses_committed_inputs_and_leaves_dirty_main_index_alone(checkout):
    repo, ws, meta, git = checkout.repo, checkout.ws, checkout.meta, checkout.git
    revision = checkout.prompt_commit()
    (repo / "input.txt").write_text("staged input\n", encoding="utf-8")
    git("add", "input.txt")
    (repo / "input.txt").write_text("unstaged input\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("local only\n", encoding="utf-8")
    before = git("status", "--porcelain=v1")

    prepared = prepare(ws, revision)
    session = Path(prepared["session"])
    worktree = Path(prepared["worktree"])
    receipt = read_json(session / "session.json")
    assert (worktree / "input.txt").read_text() == "committed input\n"
    assert not (worktree / "untracked.txt").exists()
    assert git("status", "--porcelain=v1") == before
    assert git("show", ":input.txt") == "staged input"
    assert git("rev-parse", "HEAD", cwd=worktree) == revision
    assert git("branch", "--show-current", cwd=worktree) == ""
    assert receipt["inputs"][0]["sha256"] == _hash.sha256_bytes(b"committed input\n")
    assert receipt["workspace"] == WS and receipt["schema_version"] == session_mod.SESSION_SCHEMA
    launch = (session / "LAUNCH.md").read_text()
    assert revision in launch and meta["target_commit"] in launch
    assert f"{WS}/AUDITOR.md" in launch, "the auditor role policy is named explicitly"
    assert "deadline" not in receipt and "budget_minutes" not in receipt["assignment"]
    with pytest.raises(StewartError) as refused:
        prepare(ws, revision)
    assert refused.value.reason == "destination_exists"


def test_prompt_commit_membership_matters_even_when_prompt_bytes_match(checkout):
    repo, ws, git = checkout.repo, checkout.ws, checkout.git
    (repo / "other.txt").write_text("another change\n", encoding="utf-8")
    mixed = checkout.prompt_commit(["other.txt"])
    with pytest.raises(StewartError, match="PROMPT.md alone") as refused:
        prepare(ws, mixed)
    assert refused.value.reason == "prompt_commit_shape"
    assert not (repo / ".git/stewart").exists()
    # Put identical prompt bytes in a prompt-only commit over the same target.
    prompt_bytes = (repo / ws.prompt).read_bytes()
    git("reset", "--soft", "HEAD^")
    git("restore", "--staged", "other.txt")
    git("commit", "-qm", "Prompt only")
    assert (repo / ws.prompt).read_bytes() == prompt_bytes
    prepare(ws, git("rev-parse", "HEAD"))


@pytest.mark.parametrize("changed_path", ["input.txt", f"{WS}/support.md"])
def test_target_comparison_allows_only_audit_material_changes(checkout, changed_path):
    repo, ws, git = checkout.repo, checkout.ws, checkout.git
    (repo / changed_path).write_text("intervening change\n", encoding="utf-8")
    git("add", "--", changed_path)
    git("commit", "-qm", "Intervening change")
    revision = checkout.prompt_commit()
    if changed_path == "input.txt":
        with pytest.raises(StewartError, match="target bytes changed") as refused:
            prepare(ws, revision)
        assert refused.value.reason == "target_drift"
    else:
        prepare(ws, revision)


def test_workspace_over_implementation_cannot_pass_changed_inputs_as_audit_material(tmp_path, run_cmd):
    """An assigned input inside the workspace must still be target bytes.

    The workspace rule admits intervening changes under the workspace. A
    workspace placed over code would otherwise let a post-target edit of an
    input be audited as if it were the target. The control changes a
    non-input file under the same workspace, which remains admissible.
    """
    checkout = support.make_checkout(tmp_path, run_cmd, ws_rel="lib")
    repo, ws, git, meta = checkout.repo, checkout.ws, checkout.git, checkout.meta
    (repo / "lib/module.py").write_text("VALUE = 1\n")
    git("add", "--", "lib/module.py")
    git("commit", "-qm", "Module at target")
    meta["target_commit"] = git("rev-parse", "HEAD")
    meta["input_files"] = ["lib/module.py"]
    (repo / "lib/module.py").write_text("VALUE = 2  # changed after the target\n")
    git("add", "--", "lib/module.py")
    git("commit", "-qm", "Edit under the workspace after the target")
    with pytest.raises(StewartError, match="assigned inputs changed") as refused:
        prepare(ws, checkout.prompt_commit())
    assert refused.value.reason == "input_drift"
    # Control: an intervening change to a non-input file under the workspace is audit material.
    git("reset", "-q", "--hard", meta["target_commit"])
    (repo / "lib/notes.md").write_text("support material\n")
    git("add", "--", "lib/notes.md")
    git("commit", "-qm", "Support under the workspace")
    prepared = prepare(ws, checkout.prompt_commit())
    assert (Path(prepared["worktree"]) / "lib/module.py").read_text() == "VALUE = 1\n"


@pytest.mark.parametrize("fault, message", [
    ("unassigned", "unassigned"), ("empty_question", "Question"),
    ("no_inputs", "no inputs"), ("removed_budget", "assignment fields"),
    ("path_escape", "repo-relative"), ("credentials", "without credentials"),
    ("duplicate_blocks", "exactly one"), ("unknown_field", "assignment fields"),
    ("duplicate_fields", "repeated JSON object key"),
])
def test_malformed_assignments_refuse_before_worktree_creation(checkout, fault, message):
    repo, ws, meta, git = checkout.repo, checkout.ws, checkout.meta, checkout.git
    if fault == "no_inputs":
        meta["input_files"] = []
    elif fault == "removed_budget":
        meta["budget_minutes"] = 10
    elif fault == "path_escape":
        meta["input_files"] = ["../elsewhere"]
    elif fault == "credentials":
        meta["external_sources"] = [{"url": "https://secret@example.invalid/", "purpose": "spec"}]
    elif fault == "unknown_field":
        meta["unknown"] = "unused"
    checkout.prompt_commit()
    text = (repo / ws.prompt).read_text()
    if fault == "unassigned":
        text = "**UNASSIGNED**\n" + text
    elif fault == "empty_question":
        text = text.replace("Does the implementation preserve the documented value?", "")
    elif fault == "duplicate_blocks":
        text += "\n```audit-assignment\n{}\n```\n"
    elif fault == "duplicate_fields":
        text = text.replace('"audit_id": "one-question",', '"audit_id": "one-question", "audit_id": "another",')
    (repo / ws.prompt).write_text(text)
    git("add", "--", ws.prompt)
    git("commit", "--amend", "--no-edit", "-q")
    with pytest.raises(StewartError, match=message):
        prepare(ws, git("rev-parse", "HEAD"))
    assert not (repo / ".git/stewart").exists()


def test_selected_supplemental_bytes_are_checked_then_copied(checkout):
    repo, ws, meta = checkout.repo, checkout.ws, checkout.meta
    source = repo / "ignored" / "specimen.bin"
    source.parent.mkdir()
    source.write_bytes(b"selected\0specimen")
    meta["supplemental_inputs"] = [{"path": "ignored/specimen.bin",
        "sha256": _hash.sha256_bytes((source).read_bytes()), "provenance": "Synthetic authored specimen"}]
    revision = checkout.prompt_commit()
    expected = source.read_bytes()
    source.write_bytes(b"changed bytes")
    with pytest.raises(StewartError, match="mismatched supplemental"):
        prepare(ws, revision)
    source.write_bytes(expected)
    prepared = prepare(ws, revision)
    assert (Path(prepared["worktree"]) / "ignored/specimen.bin").read_bytes() == expected
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    receipt = collected["receipt"]
    assert receipt["errors"] == [] and receipt["unexpected_paths"] == []


def test_collection_keeps_report_index_ignored_deletions_and_unexpected_commit(checkout):
    repo, ws, meta, git = checkout.repo, checkout.ws, checkout.meta, checkout.git
    prepared = support.prepared_session(checkout, report="Partial report: one input inspected.\n")
    worktree, report = prepared.worktree, prepared.report
    (worktree / "other.txt").write_text("unexpected committed change\n", encoding="utf-8")
    git("add", "other.txt", cwd=worktree)
    git("commit", "-qm", "Unexpected auditor commit", cwd=worktree)
    (worktree / "input.txt").write_text("staged version\n", encoding="utf-8")
    git("add", "input.txt", cwd=worktree)
    (worktree / "input.txt").unlink()
    hidden = worktree / "ignored" / "partial\noutput.bin"
    hidden.parent.mkdir()
    hidden.write_bytes(b"partial\x00output")
    external = repo.parent / "outside.txt"
    external.write_text("do not read this\n", encoding="utf-8")
    (worktree / "outside-link").symlink_to(external)
    main_before = git("status", "--porcelain=v1")

    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    receipt = collected["receipt"]
    directory = Path(collected["path"])
    assert receipt["errors"] == []
    assert receipt["checkout_commit_changed"]
    assert set(receipt["unexpected_paths"]) == {"input.txt", "other.txt", "ignored/partial\noutput.bin", "outside-link"}
    assert not receipt["maintainer_status_changed_since_prepare"]
    assert (directory / "REPORT.md").read_bytes() == report.read_bytes()
    assert b"staged version" in (directory / "index.patch").read_bytes()
    assert b"unexpected committed change" in (directory / "working.patch").read_bytes()
    with tarfile.open(directory / "files.tar") as archive:
        assert archive.extractfile("ignored/partial\noutput.bin").read() == b"partial\x00output"
        assert archive.getmember("outside-link").issym()
        assert "input.txt" not in archive.getnames()  # deletion is in the patch/receipt
    assert "do not read this" not in (directory / "inventory.json").read_text()
    assert git("status", "--porcelain=v1") == main_before
    assert not (repo / meta["report_path"]).exists()
    assert worktree.exists()


def test_collection_detects_movement_and_retains_partial_archive(checkout, monkeypatch):
    ws, meta = checkout.ws, checkout.meta
    prepared = support.prepared_session(checkout, report="First partial report\n")
    original = collect_mod.checkout_state
    count = 0

    def moving_checkout(*args):
        nonlocal count
        count += 1
        if count == 2:
            prepared.report.write_text("Changed during capture\n")
        return original(*args)

    monkeypatch.setattr(collect_mod, "checkout_state", moving_checkout)
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    receipt = collected["receipt"]
    assert "changed during collection" in receipt["errors"][0]["message"]
    assert receipt["inventory"]["movement"] is True
    directory = Path(collected["path"])
    assert (directory / "files.tar").exists() and (directory / "inventory-after.json").exists()
    assert prepared.worktree.exists()
    assert "movement_detected" in [gap["id"] for gap in collected["gaps"]]


def test_broken_git_does_not_prevent_preserving_a_partial_report(checkout, monkeypatch):
    ws, meta = checkout.ws, checkout.meta
    prepared = support.prepared_session(checkout, report="Partial report before a tool failure.\n")
    original = collect_mod.git

    def broken_checkout(where, *args, **kwargs):
        if where == prepared.worktree:
            raise StewartError("Synthetic Git inspection failure", reason="git_failed")
        return original(where, *args, **kwargs)

    monkeypatch.setattr(collect_mod, "git", broken_checkout)
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    receipt = collected["receipt"]
    assert receipt["report_status"] == "present"
    assert receipt["errors"] == [{"reason": "collection_failed", "message": "Synthetic Git inspection failure"}]
    assert receipt["git_discovery"] == "failed"
    assert (Path(collected["path"]) / "REPORT.md").read_bytes() == prepared.report.read_bytes()
    assert receipt["inventory"]["counts"]["file"] >= 1, "the inventory stands even when Git fails"
    assert prepared.worktree.exists()


def test_first_party_research_assignment_is_carried_without_fetching(checkout, monkeypatch):
    ws, meta = checkout.ws, checkout.meta
    meta["input_files"] = []
    meta["external_sources"] = [{"url": "https://docs.pytest.org/en/stable/explanation/fixtures.html",
                                  "purpose": "Read the fixture lifetime contract and cite it."}]

    def forbidden_connection(*args, **kwargs):
        raise AssertionError("prepare must leave retrieval to the auditor")

    monkeypatch.setattr(socket, "create_connection", forbidden_connection)
    prepared = prepare(ws, checkout.prompt_commit())
    session = Path(prepared["session"])
    assert read_json(session / "session.json")["assignment"]["external_sources"] == meta["external_sources"]
    assert prompt_metadata((Path(prepared["worktree"]) / ws.prompt).read_text(), ws)["external_sources"] == meta["external_sources"]


def test_maintainer_status_signal_is_bounded_and_cannot_certify_dirty_file_bytes(checkout):
    repo, ws, meta, git = checkout.repo, checkout.ws, checkout.meta, checkout.git
    revision = checkout.prompt_commit()
    source = repo / "input.txt"
    source.write_text("dirty before preparation\n")
    prepared = prepare(ws, revision)
    source.write_text("changed bytes with the same dirty status\n")
    first = collect(ws, meta["audit_id"], auditor_stopped="finished")
    assert not first["receipt"]["maintainer_status_changed_since_prepare"]
    git("add", "input.txt")  # only index membership changes; file bytes stay fixed
    second = collect(ws, meta["audit_id"], auditor_stopped="finished")
    assert second["receipt"]["maintainer_status_changed_since_prepare"]
    assert (Path(prepared["worktree"]) / "input.txt").read_text() == "committed input\n"


@pytest.mark.parametrize("mode", ["snapshot", "paused"])
def test_mode_controls_pause_and_resume_without_changing_snapshot_custody(checkout, mode):
    repo, ws, meta, git = checkout.repo, checkout.ws, checkout.meta, checkout.git
    revision = checkout.prompt_commit()
    # Same assignment and bytes; coordination alone changes acknowledgment/resume.
    if mode == "paused":
        with pytest.raises(StewartError, match="writers-paused") as refused:
            prepare(ws, revision, mode=mode)
        assert refused.value.reason == "pause_unacknowledged"
    else:
        with pytest.raises(StewartError, match="--mode paused"):
            prepare(ws, revision, mode=mode, writers_paused=True)
    assert not (repo / ".git/stewart").exists()
    prepared = prepare(ws, revision, mode=mode, writers_paused=(mode == "paused"),
                       pause_note=(support.PAUSE_NOTE if mode == "paused" else None))
    session = Path(prepared["session"])
    record = read_json(session / "session.json")
    assert record["mode"] == mode and record["writers_paused"] == (mode == "paused")
    assert record["writers_paused_acknowledged_by"] == ("maintainer via --writers-paused" if mode == "paused" else None)
    assert record["writers_paused_note"] == (support.PAUSE_NOTE if mode == "paused" else None)
    worktree = Path(prepared["worktree"])
    assert (worktree / "input.txt").read_bytes() == b"committed input\n"
    assert git("rev-parse", "HEAD", cwd=worktree) == revision
    with pytest.raises(StewartError, match="auditor-stopped") as refused:
        collect(ws, meta["audit_id"], auditor_stopped=False)
    assert refused.value.reason == "auditor_not_stopped"
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    receipt = collected["receipt"]
    assert receipt["mode"] == mode and receipt["report_status"] == "missing"
    assert receipt["errors"] == []
    assert not (session / "RESUMED.json").exists()
    disposition = triage(ws, meta["audit_id"], collection=collected["collection"],
                         response=response_for(collected, decision="Cancelled by operator; missing report remains a coverage gap."),
                         actor="operator")
    if mode == "snapshot":
        with pytest.raises(StewartError, match="no writer pause") as refused:
            resume(ws, meta["audit_id"], triage=disposition["triage"], reason="Triaged")
        assert refused.value.reason == "no_hold"
        assert not (session / "RESUMED.json").exists()
    else:
        resumed = resume(ws, meta["audit_id"], triage=disposition["triage"], reason="Cancelled by operator.")
        record = read_json(Path(resumed["path"]))
        assert record["collection_sha256"] == _hash.sha256_bytes((Path(collected["path"]) / "collection.json").read_bytes())
        assert record["triage_sha256"] == _hash.sha256_bytes((Path(disposition["path"])).read_bytes())
        with pytest.raises(StewartError) as refused:
            resume(ws, meta["audit_id"], triage=disposition["triage"], reason="Repeated decision")
        assert refused.value.reason == "already_resumed"
    assert worktree.exists()


def test_main_can_advance_and_collection_delay_does_not_grade_the_audit(checkout, monkeypatch):
    repo, ws, meta, git = checkout.repo, checkout.ws, checkout.meta, checkout.git
    prepared = support.prepared_session(
        checkout, report="Complete inspection; the available evidence cannot answer the question.\n",
    )
    first = collect(ws, meta["audit_id"], auditor_stopped="finished")
    before = first["receipt"]
    assert not before["maintainer_status_changed_since_prepare"]
    # Vary observation time alone: it must not create an overrun or grade a report.
    later = session_mod.now() + timedelta(days=365)
    monkeypatch.setattr(session_mod, "now", lambda: later)
    monkeypatch.setattr(collect_mod, "now", lambda: later)
    delayed = collect(ws, meta["audit_id"], auditor_stopped="finished")
    volatile = {"collected_at", "name", "runtime"}
    assert {k: v for k, v in delayed["receipt"].items() if k not in volatile} == {
        k: v for k, v in before.items() if k not in volatile
    }
    from stewart.captured import runtime_observations
    assert before["runtime"]["identity"] == delayed["receipt"]["runtime"]["identity"]
    first_runtime = runtime_observations(Path(first["path"]), before["runtime"], phases={"collection"})["collection"]
    later_runtime = runtime_observations(Path(delayed["path"]), delayed["receipt"]["runtime"], phases={"collection"})["collection"]
    assert {k: v for k, v in first_runtime.items() if k != "completed_at"} == {
        k: v for k, v in later_runtime.items() if k != "completed_at"
    }, "observation time changes its receipt digest, never the measured runtime facts"
    # At that same observation time, advancing main must change only its drift signal.
    (repo / "input.txt").write_text("development continues\n")
    git("add", "input.txt")
    git("commit", "-qm", "Advance main while auditing the pinned target")
    after = collect(ws, meta["audit_id"], auditor_stopped="finished")["receipt"]
    assert after["maintainer_status_changed_since_prepare"]
    assert after["errors"] == before["errors"] == []
    assert after["checkout"] == before["checkout"]
    assert after["report_sha256"] == before["report_sha256"]
    assert "deadline_exceeded" not in after
    assert after["report_status"] == before["report_status"] == "present"
    assert (prepared.worktree / "input.txt").read_bytes() == b"committed input\n"


@pytest.mark.parametrize("mode", ["snapshot", "paused"])
def test_cli_handoff_and_error_exit_codes(checkout, run_cmd, mode):
    meta = checkout.meta
    checkout.prompt_commit()
    base = cli_base(checkout)
    env = {"PYTHONPATH": str(INSTALLED_LIB)}
    refused = run_cmd([*base, "prepare", "--mode", "paused"], cwd=INSTALLED_LIB, env=env)
    assert refused.returncode == 2 and "writers-paused" in refused.stderr and refused.stdout == ""
    # Omit --mode for the snapshot case to exercise the public default.
    flags = ["--mode", "paused", "--writers-paused", "--pause-note", support.PAUSE_NOTE] if mode == "paused" else []
    prepared = run_cmd([*base, "prepare", *flags], cwd=INSTALLED_LIB, env=env, check=True)
    assert "LAUNCH.md" in prepared.stdout
    collected = run_cmd([*base, "collect", "--audit-id", meta["audit_id"], "--auditor-stopped", "finished"],
                        cwd=INSTALLED_LIB, env=env)
    assert collected.returncode == 1, "a missing report is news: the collection needs attention"
    assert "Report: missing" in collected.stdout
    expected = "hold remains" if mode == "paused" else "no hold to resume"
    assert expected in collected.stdout


# --- Migration and API controls --------------------------------------------


def test_import_and_help_perform_no_process_or_filesystem_work(monkeypatch, tmp_path, capsys):
    """Importing the package and asking for help spawn nothing and write nothing.

    Process hooks fail if reached, and the unrelated current directory provides
    no project context. Stronger cold-import filesystem instrumentation lives
    in the independent startup suite.
    """
    for name in list(sys.modules):
        if name.startswith("stewart"):
            monkeypatch.delitem(sys.modules, name)

    def forbidden(*args, **kwargs):
        raise AssertionError("import/help must not start a process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.chdir(tmp_path)
    package = importlib.import_module("stewart")
    assert not [name for name in sys.modules if name.startswith("stewart.")], "the surface loads lazily"
    cli = importlib.import_module("stewart.cli")
    with pytest.raises(SystemExit) as finished:
        cli.main(["--help"])
    assert finished.value.code == 0
    with pytest.raises(SystemExit) as finished:
        cli.main(["--workspace", "anywhere", "prepare", "--help"])
    assert finished.value.code == 0
    assert "writers-paused" in capsys.readouterr().out
    helper = importlib.import_module("stewart.report_declaration")
    for argv in (["--help"], ["start", "--help"], ["set", "--help"], ["check", "--help"]):
        with pytest.raises(SystemExit) as finished:
            helper.main(argv)
        assert finished.value.code == 0
    assert "last action before stopping" in " ".join(capsys.readouterr().out.split())
    assert list(tmp_path.iterdir()) == []
    api = importlib.import_module("stewart.api")
    assert "status" in api.__all__
    assert callable(api.report_declaration) and callable(api.validate_report_declaration) and callable(api.triage_draft)
    assert package.report_declaration is helper, "callables belong to api; package names stay modules"


def test_module_cli_and_package_api_agree(checkout, run_cmd):
    ws, meta = checkout.ws, checkout.meta
    support.prepared_session(checkout, report="- Status: partial\n")
    collect(ws, meta["audit_id"], auditor_stopped="finished")
    via_api = status(ws, meta["audit_id"])
    result = run_cmd([*cli_base(checkout), "--json", "status", "--audit-id", meta["audit_id"]],
                     cwd=INSTALLED_LIB, env={"PYTHONPATH": str(INSTALLED_LIB)})
    envelope = json.loads(result.stdout)
    # The report has no declaration, so an untriaged gap is news on both routes.
    assert result.returncode == envelope["exit_code"] == via_api["exit_code"] == 1
    assert envelope["ok"] is False and envelope["error"] is None and envelope["command"] == "status"
    via_cli = envelope["result"]
    invocation = via_cli["tool"].pop("invocation")
    assert invocation["source_package"] == via_api["tool"]["package"]
    assert invocation["loaded_package"] == str(Path(invocation["code_root"]) / "stewart")
    assert via_cli["tool"]["package"] == invocation["loaded_package"]
    assert via_cli["tool"]["package"] != via_api["tool"]["package"], (
        "the module CLI executes retained bytes; the API caller owns its initial imports")
    via_cli["tool"]["package"] = via_api["tool"]["package"]
    # Issued commands select the same frozen bytes; their descriptive loaded
    # location records whether the caller already entered the isolated runtime.
    pairs = [(a["runtime"], b["runtime"]) for a, b in zip(via_cli["next_actions"], via_api["next_actions"])
             if "runtime" in a]
    # The recovery command is offered only when the runtime fails verification.
    assert via_cli["preparation"]["runtime_recovery"] is None is via_api["preparation"]["runtime_recovery"]
    assert len(pairs) == 2
    for cli_runtime, api_runtime in pairs:
        assert cli_runtime == invocation
        assert api_runtime["loaded_package"] == invocation["source_package"]
        cli_runtime["loaded_package"] = api_runtime["loaded_package"]
    assert via_cli == via_api


@pytest.mark.parametrize("ws_rel", ["ws", "a/b/c/d/ws"])
def test_workspace_depth_does_not_matter(tmp_path, run_cmd, ws_rel):
    checkout = support.make_checkout(tmp_path, run_cmd, ws_rel=ws_rel)
    prepared = support.prepared_session(checkout, report="Report at depth.\n")
    assert checkout.meta["report_path"] == f"{ws_rel}/reports/one-question.md"
    assert prepared.report.exists()
    collected = collect(checkout.ws, checkout.meta["audit_id"], auditor_stopped="finished")
    assert collected["receipt"]["errors"] == [] and collected["receipt"]["report_status"] == "present"
    session = support.session_path(checkout)
    assert session.parent.name.startswith("ws-") and session.parent.parent.name == "sessions"
    assert session.is_relative_to(checkout.repo / ".git/stewart"), "sessions live under the Git common directory"


def test_same_audit_id_in_two_workspaces_cannot_cross_address_evidence(tmp_path, run_cmd):
    """Two workspaces sharing an audit ID get distinct sessions; one cannot name the other's collection."""
    checkout = support.make_checkout(tmp_path, run_cmd)
    repo, git = checkout.repo, checkout.git
    other = repo / "audits/other"
    other.mkdir()
    for name, text in (("MAINTAINER.md", "Maintainer\n"), ("AUDITOR.md", "Auditor\n"), ("PROMPT.md", "**UNASSIGNED**\n")):
        (other / name).write_text(text)
    git("add", "--", "audits/other")
    git("commit", "-qm", "Second workspace")
    checkout.meta["target_commit"] = git("rev-parse", "HEAD")
    first = support.prepared_session(checkout, report="First workspace report\n")
    collected = collect(checkout.ws, "one-question", auditor_stopped="finished")
    ws_other = workspace(repo, "audits/other")
    meta_other = {"audit_id": "one-question", "target_commit": git("rev-parse", "HEAD"),
                  "report_path": ws_other.report_path("one-question"), "input_files": ["input.txt"]}
    (repo / ws_other.prompt).write_text(assignment_text(meta_other))
    git("add", "--", ws_other.prompt)
    git("commit", "-qm", "Prompt for the other workspace")
    second = prepare(ws_other, git("rev-parse", "HEAD"))
    assert Path(second["session"]) != first.session
    assert ws_other.slug != checkout.ws.slug
    assert status(ws_other, "one-question")["collections"] == []
    with pytest.raises(StewartError) as refused:
        triage(ws_other, "one-question", collection=collected["collection"],
               response=response_for(collected), actor="tester")
    assert refused.value.reason == "collection_not_found"


@pytest.mark.parametrize("prelude", ["", "import stewart.collect\nimport stewart.workspace", "import stewart.cli"])
def test_documented_api_executes_in_fresh_processes_regardless_of_import_order(tmp_path, run_cmd, prelude):
    """Execute the README flow with fixture evidence supplied at the external auditor steps."""
    import re

    readme = (INSTALLED_LIB / "stewart/resources/README.md").read_text()
    example = re.search(r"## Python API.*?```python\n(.*?)```", readme, re.S).group(1)
    ws_rel = re.search(r'workspace\(repo_root, "([^"]+)"\)', example).group(1)
    checkout = support.make_checkout(tmp_path, run_cmd, ws_rel=ws_rel)
    revision = checkout.prompt_commit()
    statements = []
    for line in example.splitlines():
        statements.append(line)
        if line.startswith("prepared ="):
            statements.append('Path(prepared["worktree"]).joinpath(ws.report_path(audit_id)).write_text("Status: complete\\nA captured report.\\n")')
        if line.startswith("response ="):
            statements.append('response.update(custody_gaps={gap: "reviewed" for gap in response["custody_gaps"]}, decision="retain")')
    code = '\n'.join([
        prelude, 'from pathlib import Path',
        f'repo_root = Path({str(checkout.repo)!r})', f'prompt_commit = {revision!r}', 'audit_id = "one-question"',
        *statements,
        'assert callable(workspace) and callable(collect) and callable(status)',
        'assert view["retentions"] and not view["retentions"][0]["problems"]',
        'assert (repo_root / ws.report_path(audit_id)).read_text() == "Status: complete\\nA captured report.\\n"',
    ])
    result = run_cmd([sys.executable, "-B", "-c", code], cwd=INSTALLED_LIB, env={"PYTHONPATH": str(INSTALLED_LIB)})
    assert result.returncode == 0, result.stderr
