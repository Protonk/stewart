"""Close never traverses a substituted ancestor and never claims a reused Git administration.

Each comparison has a firing control (the substitution or the administrative
name reuse is observed to happen), a case differing only in the measured
property, and an invariance case. Decoys and unrelated siblings stand outside
the recorded checkout; the recorded checkout itself is the only thing removed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import stewart.close as closing
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, StewartError
from stewart._repository import ROLE_MARKER, checkout_identity
from stewart.session import capture_receipt
from stewart.status import status
import stewart_support as support
import test_close as baseline

pytestmark = pytest.mark.system


def _interrupt_before_checkout_removal(checkout, monkeypatch) -> dict:
    """A concluded close that wrote its inventory and stopped before deleting the checkout."""
    def interrupt(parent, name, **_):
        raise OSError("synthetic interruption before checkout removal")

    with monkeypatch.context() as patch:
        patch.setattr(closing, "_delete_checkout", interrupt)
        first = closing.close(checkout.ws, baseline.IDENT, actor="manager")
    assert first["closed"] is None and first["failed"][0]["kind"] == "worktree"
    return first


def _decoy(tmp_path: Path, position: str, prepared) -> tuple[Path, Path]:
    """Plant a decoy outside the recorded checkout; return its sentinel and the held real directory."""
    audit_dir = Path(prepared.prepared["audit_dir"])
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    held = None
    if position == "parent_link":
        (decoy / "worktree").mkdir()
        sentinel = decoy / "worktree/keep.txt"
        sentinel.write_text("outside recorded checkout\n")
        held = audit_dir.with_name(audit_dir.name + "-held")
        audit_dir.rename(held)
        audit_dir.symlink_to(decoy, target_is_directory=True)
    else:
        sentinel = decoy / "keep.txt"
        sentinel.write_text("outside recorded checkout\n")
        if position == "leaf_link":
            held = prepared.worktree.with_name("worktree-held")
            prepared.worktree.rename(held)
            prepared.worktree.symlink_to(decoy, target_is_directory=True)
        else:
            (prepared.worktree / "linked-decoy").symlink_to(decoy, target_is_directory=True)
    return sentinel, held


@pytest.mark.parametrize("route", ["first_abandon", "retry"])
@pytest.mark.parametrize("position", ["none", "inside_link", "leaf_link", "parent_link"])
def test_removal_never_traverses_a_substituted_checkout_ancestor(checkout, monkeypatch, tmp_path, route, position):
    prepared, _ = baseline._triaged(checkout)
    if route == "retry":
        _interrupt_before_checkout_removal(checkout, monkeypatch)
        assert prepared.worktree.is_dir(), "control: the interrupted close left the checkout"
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("invariant sibling\n")
    sentinel, held = (None, None) if position == "none" else _decoy(tmp_path, position, prepared)
    if sentinel is not None:
        assert sentinel.is_file(), "firing control: the decoy sentinel exists before close"
    if route == "first_abandon":
        result = closing.close(checkout.ws, baseline.IDENT, actor="manager", abandon=True,
                               reason="disposable link-position comparison", discard_uncollected=True)
    else:
        result = closing.close(checkout.ws, baseline.IDENT, actor="manager")
    assert result["closed"] is not None and result["failed"] == []
    assert unrelated.read_text() == "invariant sibling\n", "an unrelated sibling is never touched"
    worktree_step = result["results"][0]
    if position == "none":
        # Healthy control: the real recorded checkout and its registration are removed.
        assert worktree_step["outcome"] == "removed" and not prepared.worktree.exists()
        assert result["exit_code"] == EXIT_OK
        return
    assert sentinel.read_text() == "outside recorded checkout\n", "the decoy is never removed"
    if position == "parent_link":
        # The substitution is named and nothing below the link was traversed.
        audit_dir = Path(prepared.prepared["audit_dir"])
        assert worktree_step["outcome"].startswith(f"kept: {audit_dir}")
        assert str(audit_dir) in result["leftovers"] and result["exit_code"] == EXIT_ATTENTION
        assert (held / "worktree").is_dir(), "the real checkout moved aside is not reached through the link"
    elif position == "leaf_link":
        assert worktree_step["outcome"] == "removed link"
    elif route == "retry":
        # A link written after the close was planned is new work; the checkout is kept, not traversed.
        assert worktree_step["outcome"] == "kept: the checkout changed after the close was planned"
        assert (prepared.worktree / "linked-decoy").is_symlink()
    else:
        assert worktree_step["outcome"] == "removed" and not prepared.worktree.exists()


def test_a_replacement_between_validation_and_use_cannot_redirect_removal(checkout, monkeypatch, tmp_path):
    """The parent is pinned before deletion; substituting its pathname afterwards changes nothing removed."""
    prepared, _ = baseline._triaged(checkout)
    audit_dir = Path(prepared.prepared["audit_dir"])
    decoy = tmp_path / "decoy"
    (decoy / "worktree").mkdir(parents=True)
    sentinel = decoy / "worktree/keep.txt"
    sentinel.write_text("outside recorded checkout\n")
    held = audit_dir.with_name(audit_dir.name + "-held")
    real = closing._delete_checkout
    substituted = []

    def substitute_then_delete(parent, name, **kwargs):
        audit_dir.rename(held)
        audit_dir.symlink_to(decoy, target_is_directory=True)
        substituted.append(True)
        return real(parent, name, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(closing, "_delete_checkout", substitute_then_delete)
        result = closing.close(checkout.ws, baseline.IDENT, actor="manager")
    assert substituted, "firing control: the pathname was replaced after the checkout directory was pinned"
    assert sentinel.read_text() == "outside recorded checkout\n"
    assert not (held / "worktree").exists(), "the pinned, recorded checkout is the one removed"
    assert result["failed"] == [] and result["closed"]


def test_a_concluded_close_refuses_a_substituted_ancestor_before_writing_anything(checkout, tmp_path):
    prepared, _ = baseline._triaged(checkout)
    sentinel, _ = _decoy(tmp_path, "parent_link", prepared)
    refused = baseline._reason(closing.close, checkout.ws, baseline.IDENT, actor="manager")
    # The session's own checkout location no longer resolves without a link: refused, nothing written.
    assert refused.reason == "path_symlink" and str(Path(prepared.prepared["audit_dir"]).name) in str(refused)
    assert sentinel.read_text() == "outside recorded checkout\n"
    common = str(baseline._common(checkout))
    assert not closing.closed_location(common, checkout.ws, baseline.IDENT).exists(), "nothing was recorded"


def test_work_written_after_an_interrupted_close_is_kept(checkout, monkeypatch):
    prepared, _ = baseline._triaged(checkout)
    _interrupt_before_checkout_removal(checkout, monkeypatch)
    late = prepared.worktree / "after-interruption.txt"
    late.write_text("written after the close was planned\n")
    result = closing.close(checkout.ws, baseline.IDENT, actor="manager")
    assert result["results"][0]["outcome"] == "kept: the checkout changed after the close was planned"
    assert late.read_text() == "written after the close was planned\n"
    assert str(prepared.worktree) in result["leftovers"] and result["exit_code"] == EXIT_ATTENTION


def test_an_abandon_keeps_changes_written_after_its_plan(checkout, monkeypatch):
    prepared = support.prepared_session(checkout)
    (prepared.worktree / "planned.txt").write_text("discarded by decision\n")

    def interrupt(parent, name, **_):
        raise OSError("synthetic interruption before checkout removal")

    with monkeypatch.context() as patch:
        patch.setattr(closing, "_delete_checkout", interrupt)
        first = closing.close(checkout.ws, baseline.IDENT, actor="manager", abandon=True, reason="cancelled",
                              discard_uncollected=True)
    assert first["closed"] is None
    closing_record, _ = capture_receipt(Path(first["closing"]), what="closing record")
    assert {item["path"] for item in closing_record["observed"]["discarded"]} >= {"planned.txt"}
    # Invariance: the same planned discard resumes and removes the checkout.
    unchanged = closing.close(checkout.ws, baseline.IDENT, actor="manager")
    assert unchanged["closed"] and not prepared.worktree.exists()


def test_an_abandon_resume_keeps_an_addition_the_plan_did_not_list(checkout, monkeypatch):
    prepared = support.prepared_session(checkout)

    def interrupt(parent, name, **_):
        raise OSError("synthetic interruption before checkout removal")

    with monkeypatch.context() as patch:
        patch.setattr(closing, "_delete_checkout", interrupt)
        closing.close(checkout.ws, baseline.IDENT, actor="manager", abandon=True, reason="cancelled",
                      discard_uncollected=True)
    added = prepared.worktree / "added-after-plan.txt"
    added.write_text("not in the planned discard\n")
    result = closing.close(checkout.ws, baseline.IDENT, actor="manager")
    assert result["results"][0]["outcome"].startswith("kept: changes written after the close was planned")
    assert added.read_text() == "not in the planned discard\n"


@pytest.mark.parametrize("interleave", ["none", "before_close", "after_removal", "moved"])
def test_a_retry_never_claims_another_lifetime_at_a_reused_administrative_name(checkout, monkeypatch, interleave):
    prepared, _ = baseline._triaged(checkout)
    other = baseline._second_audit(checkout) if interleave == "before_close" else None
    common = str(baseline._common(checkout))
    if interleave == "moved":
        # The same lifetime genuinely moved: it is kept and named, never removed.
        first = _interrupt_before_checkout_removal(checkout, monkeypatch)
        moved = checkout.tmp / "moved-same-lifetime"
        checkout.git("worktree", "unlock", str(prepared.worktree))
        checkout.git("worktree", "move", str(prepared.worktree), str(moved))
        second = closing.close(checkout.ws, baseline.IDENT, actor="manager retry")
        assert second["results"][0]["outcome"] == "kept: registered elsewhere"
        assert f"checkout registered at {moved}" in second["leftovers"] and moved.is_dir()
        return
    real_git = closing.git

    def fail_later(repo, *args, **kwargs):
        if args[:1] == ("update-ref",):
            raise StewartError("synthetic failure after real checkout removal", reason="git_failed")
        return real_git(repo, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(closing, "git", fail_later)
        first = closing.close(checkout.ws, baseline.IDENT, actor="manager")
    assert first["closed"] is None and first["results"][0]["outcome"].startswith("removed")
    assert not prepared.worktree.exists() and first["failed"][0]["kind"] == "retention ref"
    frozen, _ = capture_receipt(Path(first["closing"]), what="closing record")
    old_admin = frozen["removal"]["git_admin"]
    if interleave == "after_removal":
        other = baseline._second_audit(checkout)
    marker_before = new_admin = None
    if other:
        new_admin = checkout_identity(Path(other["worktree"]))["git_admin"]
        if interleave == "after_removal":
            assert new_admin == old_admin, "firing control: Git reused the administrative name"
        else:
            assert new_admin != old_admin, "invariance control: a live lifetime keeps its own name"
        marker_before, _ = capture_receipt(Path(new_admin) / ROLE_MARKER, what="role marker")
        contents_before = support.snapshot_tree(Path(other["worktree"]))
    second = closing.close(checkout.ws, baseline.IDENT, actor="manager retry")
    assert second["resumed"] and second["closed"] and second["failed"] == []
    assert second["results"][0]["outcome"] == "absent" and second["leftovers"] == []
    assert second["exit_code"] == EXIT_OK and status(checkout.ws, baseline.IDENT)["exit_code"] == EXIT_OK
    if other:
        marker_after, _ = capture_receipt(Path(new_admin) / ROLE_MARKER, what="role marker")
        assert marker_before == marker_after and marker_after["role_uuid"] == other["session_uuid"]
        assert support.snapshot_tree(Path(other["worktree"])) == contents_before
        assert Path(new_admin).is_dir() and status(checkout.ws, "other-question")["exit_code"] == EXIT_OK
    assert closing._own_administrations(common, prepared.prepared["session_uuid"], prepared.worktree) == []
