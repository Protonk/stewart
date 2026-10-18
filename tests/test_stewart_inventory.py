"""Explicit filesystem collection coverage beside Git discovery.

Special entries are planted next to readable evidence so each test reads the
property the inventory compares: what an entry is, not whether Git saw it.
A collector that blocked on a FIFO would hang; the deadline helper turns that
into a failure.
"""

from __future__ import annotations

import os
from pathlib import Path
import stat
import tarfile

import pytest

from stewart import _util as _hash
from stewart import collect as collect_mod, _bootstrap as _files
from stewart.collect import inventory
from stewart._bootstrap import StewartError
import stewart_support as support
from stewart_support import WS, read_json

pytestmark = pytest.mark.system


def _entries(record: dict) -> dict[str, dict]:
    return {entry["path"]: entry for entry in record["entries"]}


def test_untracked_fifo_omitted_by_git_is_inventoried_without_being_opened(checkout):
    prepared = support.prepared_session(checkout, report="Report beside a pipe\n")
    os.mkfifo(prepared.worktree / "pipe.fifo")
    collected = support.collect_with_deadline(checkout)
    receipt = collected["receipt"]
    assert receipt["errors"] == [] and receipt["report_status"] == "present"
    assert receipt["git_discovery"] == "complete"
    assert {"path": "pipe.fifo", "kind": "fifo"} in receipt["inventory"]["unsupported"]
    assert "unsupported:pipe.fifo" in [gap["id"] for gap in collected["gaps"]]
    git_reported = {item["path"] for item in receipt["checkout"]["files"]}
    assert "pipe.fifo" not in git_reported, "the control: Git discovery alone would have missed it"
    record = read_json(Path(collected["path"]) / "inventory.json")
    assert _entries(record)["pipe.fifo"]["kind"] == "fifo"
    with tarfile.open(Path(collected["path"]) / "files.tar") as archive:
        assert "pipe.fifo" not in archive.getnames()


def test_regular_symlink_special_and_unreadable_entries_are_distinguished(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (root / "regular.txt").write_text("plain\n")
    secret = tmp_path / "secret.txt"
    secret.write_text("outside secret\n")
    (root / "link").symlink_to(secret)
    os.mkfifo(root / "pipe")
    (root / "nested").mkdir()
    (root / "nested" / ".git").mkdir()
    (root / "nested" / ".git" / "config").write_text("[core]\n")
    (root / "nested" / "inner.txt").write_text("inner\n")
    locked = root / "locked.txt"
    locked.write_text("cannot read\n")
    locked.chmod(0)
    try:
        record = inventory(root)
    finally:
        locked.chmod(0o644)
    entries = _entries(record)
    assert entries["regular.txt"]["kind"] == "file" and entries["regular.txt"]["size"] == 6
    assert entries["link"] == {"path": "link", "kind": "symlink", "target": str(secret)}
    assert entries["pipe"]["kind"] == "fifo"
    assert entries["nested/inner.txt"]["kind"] == "file"
    assert entries["nested/.git"] == {"path": "nested/.git", "kind": "directory", "traversed": False}
    assert record["boundaries"] == [{"path": "nested/.git", "reason": "nested git administration was not traversed"}]
    assert record["exclusions"] == [{"path": ".git", "reason": "git administration is outside coverage"}]
    assert ".git/HEAD" not in entries and "nested/.git/config" not in entries
    if os.geteuid() != 0:
        assert entries["locked.txt"]["kind"] == "unreadable" and "open" in entries["locked.txt"]["detail"]
    assert "outside secret" not in str(record), "a link's target is named, never read"
    assert record["counts"]["file"] >= 2 and record["counts"]["fifo"] == 1


def test_a_special_entry_does_not_hide_the_report_or_a_readable_sibling(checkout):
    prepared = support.prepared_session(checkout, report="Report\n")
    reports = prepared.report.parent
    os.mkfifo(reports / "beside.fifo")
    (reports / "sibling.txt").write_text("readable sibling\n")
    collected = support.collect_with_deadline(checkout)
    receipt = collected["receipt"]
    assert receipt["report_status"] == "present" and receipt["errors"] == []
    with tarfile.open(Path(collected["path"]) / "files.tar") as archive:
        assert archive.extractfile(f"{WS}/reports/sibling.txt").read() == b"readable sibling\n"
        assert f"{WS}/reports/beside.fifo" not in archive.getnames()
    unsupported = {item["path"] for item in receipt["inventory"]["unsupported"]}
    assert f"{WS}/reports/beside.fifo" in unsupported


def test_type_replacement_between_discovery_and_archiving_is_incomplete_custody_not_a_hang(checkout, monkeypatch):
    """A regular file that becomes a FIFO after lstat is omitted and the movement is recorded."""
    prepared = support.prepared_session(checkout, report="Report\n")
    extra = prepared.worktree / "extra.txt"
    extra.write_text("regular at discovery\n")
    original = collect_mod.checkout_state
    calls = 0

    def swapping_checkout(*args):
        nonlocal calls
        calls += 1
        state = original(*args)
        if calls == 1:
            extra.unlink()
            os.mkfifo(extra)
        return state

    monkeypatch.setattr(collect_mod, "checkout_state", swapping_checkout)
    collected = support.collect_with_deadline(checkout)
    receipt = collected["receipt"]
    assert any("changed during collection" in error["message"] for error in receipt["errors"])
    assert receipt["inventory"]["movement"] is True
    omitted = {item["path"]: item for item in receipt["inventory"]["omitted"]}
    assert omitted["extra.txt"]["kind"] == "replaced" and "fifo" in omitted["extra.txt"]["detail"]
    assert receipt["report_status"] == "present"
    with tarfile.open(Path(collected["path"]) / "files.tar") as archive:
        assert "extra.txt" not in archive.getnames()
    assert "archive_sha256" not in receipt, "no full-capture claim survives a movement"
    # Pair: a regular file that is swapped for another regular file is also movement, never a false full capture.
    gaps = {gap["id"] for gap in collected["gaps"]}
    assert {"movement_detected", "omitted:extra.txt"} <= gaps


def test_tracked_fifo_breaks_git_but_report_and_inventory_survive(checkout):
    prepared = support.prepared_session(checkout, report="Report\n")
    tracked = prepared.worktree / "other.txt"
    tracked.unlink()
    os.mkfifo(tracked)
    collected = support.collect_with_deadline(checkout)
    receipt = collected["receipt"]
    assert receipt["report_status"] == "present"
    assert (Path(collected["path"]) / "REPORT.md").read_text() == "Report\n"
    assert {"path": "other.txt", "kind": "fifo"} in receipt["inventory"]["unsupported"]
    if receipt["git_discovery"] == "complete":
        # If this Git tolerates the FIFO, it must still be recorded rather than archived.
        kinds = {item["path"]: item["kind"] for item in receipt["checkout"]["files"]}
        assert kinds.get("other.txt") in {"fifo", None}
        assert "other.txt" in {item["path"] for item in receipt["inventory"]["omitted"]} or "other.txt" not in kinds
    else:
        assert receipt["git_discovery"] == "failed" and receipt["errors"]
    assert "git_discovery_incomplete" in {gap["id"] for gap in collected["gaps"]} or receipt["git_discovery"] == "complete"
    assert prepared.worktree.exists()


def test_symlink_report_and_symlinked_directory_are_recorded_not_followed(checkout):
    prepared = support.prepared_session(checkout, report=None)
    outside = checkout.tmp / "outside.md"
    outside.write_text("not the auditor's report\n")
    prepared.report.symlink_to(outside)
    (prepared.worktree / "dirlink").symlink_to(checkout.tmp)
    collected = support.collect_with_deadline(checkout)
    receipt = collected["receipt"]
    assert receipt["report_status"] == "symlink" and receipt["errors"] == []
    assert not (Path(collected["path"]) / "REPORT.md").exists()
    kinds = {item["path"]: item for item in receipt["checkout"]["files"]}
    assert kinds["dirlink"]["kind"] == "symlink" and kinds["dirlink"]["target"] == str(checkout.tmp)
    with tarfile.open(Path(collected["path"]) / "files.tar") as archive:
        assert archive.getmember("dirlink").issym()
        assert "not the auditor's report" not in str(archive.getnames())
    assert "report_symlink" in {gap["id"] for gap in collected["gaps"]}


def test_capture_rejects_a_descriptor_that_is_not_a_regular_file(tmp_path):
    target = tmp_path / "entry"
    os.mkfifo(target)
    info = _files.capture_regular(target)
    assert info["kind"] == "replaced" and "fifo" in info["detail"]
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "missing")
    info = _files.capture_regular(link)
    assert info["kind"] in {"replaced", "unreadable"}
    regular = tmp_path / "regular"
    regular.write_bytes(b"bytes")
    info = _files.capture_regular(regular)
    assert info["kind"] == "file" and info["size"] == 5 and stat.S_IMODE(regular.stat().st_mode) == info["mode"]
    # The archive verifier compares digests, so an altered member is a refusal, not a pass.
    archive = tmp_path / "files.tar"
    with tarfile.open(archive, "x") as bundle:
        bundle.add(regular, arcname="regular", recursive=False)
    collect_mod.verify_archive(archive, [{"path": "regular", "kind": "file", "sha256": info["sha256"]}], ["regular"])
    with pytest.raises(StewartError) as refused:
        collect_mod.verify_archive(archive, [{"path": "regular", "kind": "file", "sha256": "0" * 64}], ["regular"])
    assert refused.value.reason == "archive_mismatch"


@pytest.mark.parametrize("moment", ["discovered", "opened", "unrelated"])
def test_ancestor_directory_swaps_never_read_outside_the_inventory(tmp_path, monkeypatch, moment):
    """Swap after classification or at listing; the outside file is the distinguishing witness."""
    root = tmp_path / "root"
    child = root / "child"
    child.mkdir(parents=True)
    (child / "inside.txt").write_text("inside")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside-only.txt").write_text("must never be read")
    original_stat, original_lstat, original_listdir = os.stat, os.lstat, os.listdir
    identity = original_lstat(child)
    swapped = False

    def mutate(st):
        nonlocal swapped
        if not swapped and (st.st_dev, st.st_ino) == (identity.st_dev, identity.st_ino):
            swapped = True
            child.rename(tmp_path / "displaced")
            child.symlink_to(outside, target_is_directory=True)

    def observed_stat(*args, **kwargs):
        st = original_stat(*args, **kwargs)
        if moment == "discovered":
            mutate(st)
        return st

    def observed_lstat(*args, **kwargs):
        st = original_lstat(*args, **kwargs)
        if moment == "discovered":
            mutate(st)
        return st

    def listing(where):
        if moment == "opened":
            mutate(os.fstat(where) if isinstance(where, int) else original_lstat(where))
        return original_listdir(where)

    monkeypatch.setattr(os, "stat", observed_stat)
    monkeypatch.setattr(os, "lstat", observed_lstat)
    monkeypatch.setattr(os, "listdir", listing)
    if moment == "unrelated":
        (outside / "outside-only.txt").write_text("unrelated bytes changed")
    entries = _entries(inventory(root))
    assert not any("outside-only" in name for name in entries), "a parent swap must never expose its target"
    if moment == "unrelated":
        assert entries["child/inside.txt"]["sha256"] == _hash.sha256_bytes(b"inside")
        assert entries["child"]["kind"] == "directory"
    else:
        assert swapped and entries["child"]["kind"] == "replaced", "the lost path binding must be explicit"


def test_regular_reader_refuses_symlinked_ancestors_and_keeps_regular_control(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "value").write_bytes(b"witness")
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    info, data = _files.read_regular(alias / "value")
    assert data is None and info["kind"] == "replaced"
    info, data = _files.read_regular(outside / "value")
    assert data == b"witness" and info["kind"] == "file"
