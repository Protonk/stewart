"""Submodules: Stewart neither populates nor audits them, says so loudly, and never loses what lies below them.

A prompt commit holding a gitlink is refused until the maintainer acknowledges it; the session
records the paths and the handoff lists them. Git lists nothing written below a submodule path,
so collection archives such files from Stewart's own walk and names them, and an abandon counts
them as uncollected. Each guarantee has a firing control, a differing case and an invariance case.
"""
from __future__ import annotations

import os
from pathlib import Path
import tarfile

import pytest

from stewart._bootstrap import StewartError
from stewart._git import git
from stewart.assignment import initialize
from stewart.close import close
from stewart.collect import collect
from stewart.prepare import prepare
from stewart.status import status
import stewart_support as support
from stewart_support import read_json

pytestmark = pytest.mark.system

GITLINK = "1" * 40


def _reason(function, *args, **kwargs) -> StewartError:
    with pytest.raises(StewartError) as caught:
        function(*args, **kwargs)
    return caught.value


def _with_submodule(checkout) -> str:
    """Commit a gitlink at vendor/lib as the audited target, then the prompt; return the prompt commit."""
    checkout.git("update-index", "--add", "--cacheinfo", f"160000,{GITLINK},vendor/lib")
    checkout.git("commit", "-qm", "A submodule the audit does not cover")
    checkout.meta["target_commit"] = checkout.git("rev-parse", "HEAD")
    return checkout.prompt_commit()


def test_a_prompt_commit_with_submodules_is_refused_until_acknowledged_and_its_paths_are_handed_over(
        checkout, tmp_path, run_cmd):
    # Invariance: a repository without submodules prepares as before and records none.
    plain = support.make_checkout(tmp_path, run_cmd, name="plain")
    plain_session = Path(prepare(plain.ws, plain.prompt_commit())["session"])
    assert read_json(plain_session / "session.json")["submodules"] is None
    assert initialize(plain.ws, "plain-draft", plain.meta["target_commit"], inputs=["input.txt"])["submodules"] == []

    revision = _with_submodule(checkout)
    assert initialize(checkout.ws, "submodule-draft", checkout.meta["target_commit"],
                      inputs=["input.txt"])["submodules"] == ["vendor/lib"], "init warns before the prompt is written"
    refused = _reason(prepare, checkout.ws, revision)
    assert refused.reason == "submodules_present" and "vendor/lib" in str(refused)
    assert not support.session_path(checkout).exists(), "a refusal prepares nothing"

    prepared = prepare(checkout.ws, revision, submodules_acknowledged=True)
    record = read_json(Path(prepared["session"]) / "session.json")
    assert record["submodules"] == {"gitlinks": [{"path": "vendor/lib", "commit": GITLINK}],
                                    "acknowledged_by": "maintainer via --submodules-acknowledged"}
    worktree = Path(prepared["worktree"])
    assert (worktree / "vendor/lib").is_dir() and not os.listdir(worktree / "vendor/lib"), "Git leaves it empty"
    handoff = (worktree / record["handoff"]["path"]).read_text(encoding="utf-8")
    assert "Submodule paths" in handoff and str(worktree / "vendor/lib") in handoff
    view = status(checkout.ws, checkout.meta["audit_id"])
    assert any(item.startswith("the prompt commit holds submodules") and "vendor/lib" in item
               for item in view["outstanding"])


def test_files_git_does_not_list_below_a_submodule_path_are_archived_named_and_never_discarded_silently(checkout):
    revision = _with_submodule(checkout)
    prepared = prepare(checkout.ws, revision, submodules_acknowledged=True)
    worktree, ident, report = Path(prepared["worktree"]), checkout.meta["audit_id"], checkout.meta["report_path"]
    (worktree / report).write_text("A report.\n", encoding="utf-8")
    (worktree / "vendor/lib/NOTES.md").write_text("notes beside the empty submodule\n", encoding="utf-8")
    # Firing control: Git itself lists the report but nothing below the submodule path.
    listed = os.fsdecode(git(worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout)
    assert report in listed and "vendor/lib" not in listed

    collected = collect(checkout.ws, ident, auditor_stopped="finished")
    files = {item["path"]: item for item in collected["receipt"]["checkout"]["files"]}
    assert files["vendor/lib/NOTES.md"]["listed_by_git"] is False
    assert "listed_by_git" not in files[report], "differing case: a Git-reported entry is recorded as before"
    assert collected["receipt"]["checkout"]["gitlinks"] == ["vendor/lib"]
    with tarfile.open(Path(collected["path"]) / "files.tar") as archive:
        assert archive.extractfile("vendor/lib/NOTES.md").read() == b"notes beside the empty submodule\n"
    gaps = {gap["id"] for gap in collected["gaps"]}
    assert {"gitlink_contents:vendor/lib", "unexpected_path:vendor/lib/NOTES.md"} <= gaps

    # Written after the collection, a file there is uncollected: abandon refuses, then lists what it discards.
    (worktree / "vendor/lib/LATER.md").write_text("written after the collection\n", encoding="utf-8")
    refused = _reason(close, checkout.ws, ident, actor="manager", abandon=True, reason="done")
    assert refused.reason == "uncollected_changes" and "vendor/lib/LATER.md" in str(refused)
    assert "vendor/lib/NOTES.md" not in str(refused), "invariance: the archived file is not uncollected"
    closed = close(checkout.ws, ident, actor="manager", abandon=True, reason="done", discard_uncollected=True)
    discarded = read_json(Path(closed["closing"]))["observed"]["discarded"]
    assert [item["path"] for item in discarded] == ["vendor/lib/LATER.md"]
    assert not worktree.exists()
