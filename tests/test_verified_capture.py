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
    assert close_plan(checkout.ws, ident)["audit"]["refusal"]["reason"] == "capture_unverified"
    rerun = close(checkout.ws, ident, actor="manager")
    step = rerun["results"][0]
    assert step["outcome"] == "failed" and step["reason"] == "capture_unverified" and rerun["closed"] is None
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
