"""A close removes a checkout only when its bytes are preserved: in a verified capture or in the prompt commit.

A concluded close needs its triaged collection to be a verified capture: Git discovery completed, an archive digest
was recorded, the archive's bytes and members verify, and every entry of the recorded inventory is contentless or held
with the same kind and content by that archive or the prompt commit. Status, close planning, close and the recheck
before removing a checkout share the check. An abandon counts as collected only what a verified archive holds. A
checkout that no longer matches what its close judged stops removal and keeps everything that remains.

Each comparison has a firing control (the state named is observed to arise), a case differing in the measured
property and an invariance case.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import stewart.close as closing
import stewart.collect as collector
from stewart._bootstrap import StewartError
from stewart._git import git
from stewart.close import close, close_plan
from stewart.status import status
from stewart.triage import retain, triage
import stewart_support as support
from stewart_support import read_json

pytestmark = pytest.mark.system

NOTE = b"auditor observation not retained with the report\n"


def _reason(function, *args, **kwargs) -> StewartError:
    with pytest.raises(StewartError) as caught:
        function(*args, **kwargs)
    return caught.value


def _note(checkout, worktree: Path) -> Path:
    note = worktree / checkout.ws.scratch_prefix(checkout.meta["audit_id"]) / "notes" / "unsaved.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_bytes(NOTE)
    return note


def _triage_and_retain(checkout, collected) -> None:
    ident = checkout.meta["audit_id"]
    response = triage(checkout.ws, ident, collection=collected["collection"], response=support.response_for(collected),
                      actor="manager")
    retain(checkout.ws, ident, triage=response["triage"], report=True)


def _offers_close(view: dict) -> bool:
    return any(action["action"] == "close" for action in view["next_actions"])


def _nothing_closed(checkout) -> bool:
    common = git(checkout.repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.decode().strip()
    return not closing.closed_location(common, checkout.ws, checkout.meta["audit_id"]).exists()


CAPTURES = {"verified": None, "git administration missing": "capture_not_recorded",
            "git administration of another checkout": "capture_not_recorded",
            "movement, then restored": "capture_not_recorded", "archive missing": "capture_unverified",
            "archive damaged": "capture_unverified"}


@pytest.mark.parametrize("case", CAPTURES)
def test_a_concluded_close_needs_a_verified_capture_whatever_the_triage_says(checkout, monkeypatch, case):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    note = _note(checkout, prepared.worktree)
    if case.startswith("git administration"):
        named = checkout.tmp / "absent-admin" if case.endswith("missing") else checkout.repo / ".git"
        (prepared.worktree / ".git").write_text(f"gitdir: {named}\n")
    real = collector.archive_files

    def archive_then_move(*args, **kwargs):
        result = real(*args, **kwargs)
        if case == "movement, then restored":
            note.write_bytes(b"a concurrent writer\n")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(collector, "archive_files", archive_then_move)
        collected = collector.collect(checkout.ws, ident, auditor_stopped="finished")
    receipt, archive = collected["receipt"], Path(collected["path"]) / "files.tar"
    # Firing controls: each case produces the state it names before the triage disposes its gaps.
    if case.startswith("git administration"):
        assert receipt["git_discovery"] == "failed" and not archive.exists()
    elif case == "movement, then restored":
        assert receipt["inventory"]["movement"] is True and "archive_sha256" not in receipt and archive.is_file()
        note.write_bytes(NOTE)
    else:
        assert receipt["git_discovery"] == "complete" and receipt["archive_sha256"]
    if case == "archive missing":
        archive.unlink()
    elif case == "archive damaged":
        archive.write_bytes(b"damaged archive\n")
    _triage_and_retain(checkout, collected)
    view = status(checkout.ws, ident)
    refusal = close_plan(checkout.ws, ident)["audit"]["refusal"]
    expected = CAPTURES[case]
    if expected is None:
        # Differing case: a verified capture is offered and closes as before.
        assert _offers_close(view) and refusal is None
        assert close(checkout.ws, ident, actor="manager")["closed"] and not prepared.worktree.exists()
        return
    assert not _offers_close(view)
    assert any(line.startswith(f"a concluded close is not offered ({expected})") for line in view["outstanding"])
    assert refusal["reason"] == expected and refusal["exit_code"] == (3 if expected == "capture_unverified" else 2)
    refused = _reason(close, checkout.ws, ident, actor="manager")
    assert refused.reason == expected and collected["collection"] in str(refused)
    assert str(prepared.worktree) in refused.retained and str(prepared.session) in refused.retained
    assert note.read_bytes() == NOTE and prepared.session.is_dir() and _nothing_closed(checkout)
    # Invariance: an abandon still retires the session and records what no verified capture holds.
    abandoned = close(checkout.ws, ident, actor="manager", abandon=True, reason="capture unavailable",
                      discard_uncollected=True)
    discarded = read_json(Path(abandoned["closing"]))["observed"]["discarded"]
    note_rel = note.relative_to(prepared.worktree).as_posix()
    assert discarded is None or note_rel in [item["path"] for item in discarded]


KINDS = {"unchanged tracked files": None, "special file (FIFO)": None, "symbolic link": None,
         "unreadable directory": "capture_uncovered", "nested repository": "capture_uncovered",
         "nested .git file": "capture_uncovered", "change Git is told to skip": "capture_uncovered",
         "link replacing a file Git is told to skip": "capture_uncovered"}


@pytest.mark.parametrize("kind", KINDS)
def test_coverage_is_decided_by_bytes_not_by_what_git_reports(checkout, run_cmd, kind):
    prepared = support.prepared_session(checkout)
    ident, worktree = checkout.meta["audit_id"], prepared.worktree
    notes = worktree / checkout.ws.scratch_prefix(ident) / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    tracked = worktree / "input.txt"
    locked = notes / "locked"
    if kind == "special file (FIFO)":
        os.mkfifo(notes / "pipe")
    elif kind == "symbolic link":
        (notes / "link").symlink_to("a-target-that-does-not-exist")
    elif kind == "unreadable directory":
        locked.mkdir()
        (locked / "inside.txt").write_bytes(b"inside an unreadable directory\n")
        locked.chmod(0)
    elif kind == "nested repository":
        (notes / "nested").mkdir()
        run_cmd(["git", "init", "-q"], cwd=notes / "nested", check=True)
        (notes / "nested" / "inside.txt").write_bytes(b"inside a nested repository\n")
    elif kind == "nested .git file":
        (notes / "pointer").mkdir()
        (notes / "pointer" / ".git").write_text(f"gitdir: {checkout.tmp / 'elsewhere'}\n")
    elif kind != "unchanged tracked files":
        git(worktree, "update-index", "--skip-worktree", "input.txt")
        tracked.unlink()
        if kind == "change Git is told to skip":
            tracked.write_bytes(b"changed where Git does not look\n")
        else:
            tracked.symlink_to("input.txt.elsewhere")
        listed = os.fsdecode(git(worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout)
        assert "input.txt" not in listed, "firing control: Git reports no change to the skipped file"
    try:
        collected = collector.collect(checkout.ws, ident, auditor_stopped="finished")
        assert collected["receipt"]["archive_sha256"], "control: every case records an archive claim that verifies"
        _triage_and_retain(checkout, collected)
        view = status(checkout.ws, ident)
        refusal = close_plan(checkout.ws, ident)["audit"]["refusal"]
        abandon = close_plan(checkout.ws, ident, abandon=True)["audit"]["refusal"]
        expected = KINDS[kind]
        if expected is None:
            # Contentless entries, links held by the archive and files equal to the prompt commit need nothing more.
            assert _offers_close(view) and refusal is None and abandon is None
            assert close(checkout.ws, ident, actor="manager")["closed"] and not worktree.exists()
            return
        assert not _offers_close(view) and refusal["reason"] == expected
        # The abandon's own count of what is uncollected comes from the same bytes.
        assert abandon["reason"] == "uncollected_changes"
        refused = _reason(close, checkout.ws, ident, actor="manager")
        assert refused.reason == expected and worktree.is_dir() and prepared.session.is_dir()
        if kind.endswith("Git is told to skip"):
            assert "input.txt" in str(refused) and "input.txt" in abandon["message"]
    finally:
        if locked.exists():
            locked.chmod(0o700)


def _interrupted_close(checkout, monkeypatch, *, abandon: bool = False) -> dict:
    """A close that wrote its inventory and stopped before deleting the checkout."""
    def interrupt(parent, name, **_):
        raise OSError("synthetic interruption before checkout removal")

    with monkeypatch.context() as patch:
        patch.setattr(closing, "_delete_checkout", interrupt)
        first = close(checkout.ws, checkout.meta["audit_id"], actor="manager",
                      **({"abandon": True, "reason": "cancelled", "discard_uncollected": True} if abandon else {}))
    assert first["closed"] is None and first["failed"][0]["kind"] == "worktree"
    assert "reason" not in first["failed"][0], "control: a failed removal is not a judgment stop"
    return first


def test_a_resumed_close_rechecks_its_capture_and_stops_keeping_everything(checkout, monkeypatch):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    note = _note(checkout, prepared.worktree)
    collected = collector.collect(checkout.ws, ident, auditor_stopped="finished")
    _triage_and_retain(checkout, collected)
    first = _interrupted_close(checkout, monkeypatch)
    assert read_json(Path(first["closing"]))["observed"]["collection"]["name"] == collected["collection"]
    archive = Path(collected["path"]) / "files.tar"
    original = archive.read_bytes()
    archive.write_bytes(b"damaged after planning\n")
    planned = close_plan(checkout.ws, ident)["audit"]["refusal"]
    assert planned["reason"] == "capture_unverified" and planned["exit_code"] == 3
    rerun = close(checkout.ws, ident, actor="manager")
    step = rerun["results"][0]
    assert step["outcome"] == "failed" and step["reason"] == "capture_unverified" and rerun["closed"] is None
    assert rerun["exit_code"] == planned["exit_code"], "the plan reports the code the close earns"
    assert [item["kind"] for item in rerun["results"]] == ["worktree"], "nothing after the checkout is removed"
    assert note.read_bytes() == NOTE and prepared.session.is_dir() and archive.is_file()
    view = status(checkout.ws, ident)
    stopped = [item for item in view["attention"] if item["reason"] == "close_incomplete"]
    assert stopped and "capture_unverified" in stopped[0]["message"]
    assert any("no command cancels or supersedes a stopped close" in step for action in view["next_actions"]
               for step in action["prerequisites"])
    # Invariance: with the captured bytes restored the same close finishes from its recorded inventory.
    archive.write_bytes(original)
    done = close(checkout.ws, ident, actor="manager")
    assert done["closed"] and not prepared.worktree.exists() and not prepared.session.exists()


def test_an_abandon_counts_only_verified_captures_as_collected(checkout):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    note = _note(checkout, prepared.worktree)
    rel = note.relative_to(prepared.worktree).as_posix()
    # Firing control: before any collection the note is uncollected.
    assert rel in close_plan(checkout.ws, ident, abandon=True)["audit"]["refusal"]["message"]
    collected = collector.collect(checkout.ws, ident, auditor_stopped="finished")
    # Differing case: a verified capture holds the note, so the abandon needs no discard.
    assert close_plan(checkout.ws, ident, abandon=True)["audit"]["refusal"] is None
    archive = Path(collected["path"]) / "files.tar"
    archive.write_bytes(b"damaged archive\n")
    refusal = close_plan(checkout.ws, ident, abandon=True)["audit"]["refusal"]
    assert refusal["reason"] == "uncollected_changes" and rel in refusal["message"]
    closed = close(checkout.ws, ident, actor="manager", abandon=True, reason="capture damaged",
                   discard_uncollected=True)
    discarded = read_json(Path(closed["closing"]))["observed"]["discarded"]
    assert rel in [item["path"] for item in discarded] and not prepared.worktree.exists()


def test_an_abandon_counts_a_changed_handoff_as_uncollected(checkout):
    prepared = support.prepared_session(checkout, report=None)
    ident = checkout.meta["audit_id"]
    handoff = prepared.worktree / read_json(prepared.session / "session.json")["handoff"]["path"]
    # Invariance: the handoff exactly as issued is preparation's own, so nothing is uncollected.
    assert handoff.is_file() and close_plan(checkout.ws, ident, abandon=True)["audit"]["refusal"] is None
    rel = handoff.relative_to(prepared.worktree).as_posix()
    handoff.write_text("the auditor's own work, written over the handoff\n")
    refusal = close_plan(checkout.ws, ident, abandon=True)["audit"]["refusal"]
    assert refusal["reason"] == "uncollected_changes" and rel in refusal["message"]
    closed = close(checkout.ws, ident, actor="manager", abandon=True, reason="handoff overwritten",
                   discard_uncollected=True)
    assert rel in [item["path"] for item in read_json(Path(closed["closing"]))["observed"]["discarded"]]


@pytest.mark.parametrize("window", ["report changed after its capture", "movement error after the archive claim"])
def test_every_collection_that_records_movement_is_not_a_capture(checkout, monkeypatch, window):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    real_report, real_outputs = collector.capture_report, collector.unexpected_outputs

    def report_then_change(*args, **kwargs):
        result = real_report(*args, **kwargs)
        prepared.report.write_text("A report changed after its capture.\n")
        return result

    def movement_after_claim(*args, **kwargs):
        raise StewartError("a writer moved the checkout after the archive claim", reason="movement")

    with monkeypatch.context() as patch:
        if window == "report changed after its capture":
            patch.setattr(collector, "capture_report", report_then_change)
        else:
            patch.setattr(collector, "unexpected_outputs", movement_after_claim)
        collected = collector.collect(checkout.ws, ident, auditor_stopped="finished")
    receipt = collected["receipt"]
    assert "movement" in [error["reason"] for error in receipt["errors"]], "firing control: movement is recorded"
    if window == "report changed after its capture":
        # Both report versions are kept, and the receipt makes no full-capture claim.
        assert "archive_sha256" not in receipt and receipt["inventory"]["movement"] is True
    else:
        assert receipt["archive_sha256"], "control: this receipt claims an archive and still records movement"
    _triage_and_retain(checkout, collected)
    assert not _offers_close(status(checkout.ws, ident))
    assert close_plan(checkout.ws, ident)["audit"]["refusal"]["reason"] == "capture_not_recorded"


@pytest.mark.parametrize("replaced", ["blob", "commit"])
def test_replacement_objects_cannot_make_a_change_look_committed(checkout, replaced):
    import subprocess
    prepared = support.prepared_session(checkout)
    ident, worktree, prompt = checkout.meta["audit_id"], prepared.worktree, prepared.revision
    changed = b"changed where Git does not look\n"
    (worktree / "input.txt").write_bytes(changed)
    original = git(checkout.repo, "rev-parse", f"{prompt}:input.txt").stdout.decode().strip()
    forged = git(checkout.repo, "hash-object", "-w", "--stdin", input=changed).stdout.decode().strip()
    if replaced == "blob":
        git(checkout.repo, "replace", original, forged)
    else:
        # A stand-in prompt commit whose tree holds the changed bytes; the checkout's index agrees with it.
        index = {**os.environ, "GIT_INDEX_FILE": str(checkout.tmp / "forged.index")}
        subprocess.run(["git", "read-tree", prompt], cwd=checkout.repo, env=index, check=True)
        subprocess.run(["git", "update-index", "--cacheinfo", f"100644,{forged},input.txt"], cwd=checkout.repo,
                       env=index, check=True)
        tree = subprocess.run(["git", "write-tree"], cwd=checkout.repo, env=index, check=True,
                              capture_output=True).stdout.decode().strip()
        fake = git(checkout.repo, "commit-tree", tree, "-m", "a stand-in for the prompt").stdout.decode().strip()
        git(checkout.repo, "replace", prompt, fake)
        git(worktree, "update-index", "--cacheinfo", f"100644,{forged},input.txt")
    git(worktree, "update-index", "--skip-worktree", "input.txt")
    # Firing controls: Git reports nothing, and with replacements honoured the prompt appears to hold the change.
    assert "input.txt" not in os.fsdecode(git(worktree, "status", "--porcelain=v1", "-z").stdout)
    assert git(checkout.repo, "cat-file", "-p", f"{prompt}:input.txt").stdout == changed
    assert git(checkout.repo, "--no-replace-objects", "cat-file", "-p", f"{prompt}:input.txt").stdout != changed
    collected = collector.collect(checkout.ws, ident, auditor_stopped="finished")
    assert "input.txt" not in collected["receipt"]["inventory"]["archived"], "control: the change is not archived"
    _triage_and_retain(checkout, collected)
    refusal = close_plan(checkout.ws, ident)["audit"]["refusal"]
    assert refusal["reason"] == "capture_uncovered" and "input.txt" in refusal["message"]
    assert close_plan(checkout.ws, ident, abandon=True)["audit"]["refusal"]["reason"] == "uncollected_changes"


def test_archive_members_are_verified_beyond_the_archive_digest(checkout, monkeypatch):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    note = _note(checkout, prepared.worktree)
    real = collector.archive_files

    def archive_other_bytes(*args, **kwargs):
        # The archive is written while the note briefly holds other bytes, then the note is restored.
        note.write_bytes(b"bytes the receipt never recorded\n")
        try:
            return real(*args, **kwargs)
        finally:
            note.write_bytes(NOTE)

    with monkeypatch.context() as patch:
        patch.setattr(collector, "archive_files", archive_other_bytes)
        patch.setattr(collector, "verify_archive", lambda *args, **kwargs: None)
        collected = collector.collect(checkout.ws, ident, auditor_stopped="finished")
    receipt, archive = collected["receipt"], Path(collected["path"]) / "files.tar"
    # Firing control: the archive's digest is the receipt's, but its member is not the recorded file.
    import hashlib, tarfile
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == receipt["archive_sha256"]
    with tarfile.open(archive) as bundle:
        assert bundle.extractfile(note.relative_to(prepared.worktree).as_posix()).read() != NOTE
    _triage_and_retain(checkout, collected)
    refusal = close_plan(checkout.ws, ident)["audit"]["refusal"]
    assert refusal["reason"] == "capture_unverified" and "archive members differ" in refusal["message"]
    rel = note.relative_to(prepared.worktree).as_posix()
    assert rel in close_plan(checkout.ws, ident, abandon=True)["audit"]["refusal"]["message"]


def test_the_inventory_record_must_be_the_one_the_receipt_names(checkout):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    locked = prepared.worktree / checkout.ws.scratch_prefix(ident) / "notes" / "locked"
    locked.mkdir(parents=True)
    (locked / "inside.txt").write_bytes(b"inside an unreadable directory\n")
    locked.chmod(0)
    try:
        collected = collector.collect(checkout.ws, ident, auditor_stopped="finished")
        _triage_and_retain(checkout, collected)
        assert close_plan(checkout.ws, ident)["audit"]["refusal"]["reason"] == "capture_uncovered", "control"
        record = Path(collected["path"]) / "inventory.json"
        document = read_json(record)
        document["entries"] = [entry for entry in document["entries"] if entry["kind"] != "unreadable"]
        record.chmod(0o600)
        record.write_text(json.dumps(document))
        # Firing control: the rewritten record hides the unreadable entry and is not the one the receipt names.
        assert all(entry["kind"] != "unreadable" for entry in read_json(record)["entries"])
        refusal = close_plan(checkout.ws, ident)["audit"]["refusal"]
        assert refusal["reason"] == "capture_unverified" and "inventory record" in refusal["message"]
    finally:
        locked.chmod(0o700)


def test_an_attempt_record_that_does_not_verify_keeps_its_diagnostic(checkout, monkeypatch):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    collected = collector.collect(checkout.ws, ident, auditor_stopped="finished")
    _triage_and_retain(checkout, collected)
    first = _interrupted_close(checkout, monkeypatch)
    # Control: an intact attempt record reports an ordinary incomplete close.
    assert [item["reason"] for item in status(checkout.ws, ident)["attention"]] == ["close_incomplete"]
    [attempt] = sorted(Path(first["closing"]).parent.glob("CLOSE-ATTEMPT-*.json"))
    attempt.chmod(0o600)
    attempt.write_bytes(attempt.read_bytes()[:20])
    view = status(checkout.ws, ident)
    invalid = [item for item in view["attention"] if item["reason"] == "closing_record_invalid"]
    assert view["exit_code"] == 3 and invalid and attempt.name in invalid[0]["message"]
    assert not _offers_close(view), "a concluded close that would refuse is not offered"
    refused = _reason(close, checkout.ws, ident, actor="manager")
    assert refused.exit_code == 3 and prepared.worktree.is_dir() and prepared.session.is_dir()
