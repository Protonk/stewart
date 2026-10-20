"""Recorded-resource retirement never removes what its claim did not freeze.

Nested and foreign checkouts, branches that alone hold a commit, records that
cannot be read, a substituted ``.git``, a write in the gap between evaluation
and claim, an interrupted removal, and a resource or session checkout replaced
just before its removal: in each, Stewart keeps what it cannot vouch for and
records why.

Each measured guarantee has a firing control (the condition is shown to have
happened), a case differing only in the measured property, and an invariance
case. Every repository, home and manager store is a disposable fixture.
"""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import shutil

import pytest

from stewart import _removal, api
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, StewartError
import stewart.close as close_module
import stewart.holdings as holdings
import stewart_support as support
from stewart_support import snapshot_tree
import test_resources as base

pytestmark = pytest.mark.system

WS = base.WS
HOLDER = base.HOLDER
PARTNER = base.PARTNER


# --- helpers ---------------------------------------------------------------------------------------------


def _plan(cli, repo: Path, ident: str, *, code: int) -> dict[str, dict]:
    """The abandon's closeout plan by resource, asserting its exit code (1 while any resource stays blocked).

    These audits exist only as resource contexts, so an abandon is the close they get; a concluded plan would
    report the refusal (session_missing) that close raises for them.
    """
    plan = cli("--repo", repo, "--workspace", WS, "close", "--audit-id", ident, "--plan", "--abandon",
               allowed=(code,))["result"]
    assert plan["schema"] == "stewart.closeout/1"
    return base._by_rid(plan["resources"])


def _close_resources(cli, repo: Path, *rids: str, allowed=(EXIT_OK,)) -> dict:
    argv = ["--repo", repo, "close", "--actor", "manager"]
    for rid in rids:
        argv += ["--resource", rid]
    return cli(*argv, allowed=allowed)["result"]


def _refused_close(cli, repo: Path, *rids: str) -> dict:
    argv = ["--repo", repo, "close", "--actor", "manager"]
    for rid in rids:
        argv += ["--resource", rid]
    return base._refused(cli, *argv)


def _outcomes(items: list[dict]) -> list[tuple[str, str]]:
    return [(item["rid"], item["outcome"]) for item in items]


def _attempts(common: Path, rid: str) -> list[str]:
    """Removal attempts of the first claim generation, each recorded before its first removal step."""
    return [name for name in base._attempt_files(common, rid) if name.startswith("0001.ATTEMPT-")]


def _fill(directory: Path) -> None:
    for rel in ("a.txt", "b.txt", "c.txt", "sub/d.txt"):
        (directory / rel).parent.mkdir(exist_ok=True)
        (directory / rel).write_text(f"frozen content of {rel}\n", encoding="utf-8")


class _UnlinkFailsAfter:
    """Stands in for ``os`` inside ``_removal`` only: file unlinks beyond ``allowed`` fail.

    This is an interruption partway through a descriptor-relative removal:
    some entries are gone, the rest are untouched, and the error propagates.
    """

    def __init__(self, allowed: int, *, first: str | None = None):
        self.allowed, self.first = allowed, first
        self.removed: list[str] = []
        self.refused: list[str] = []

    def __getattr__(self, name):
        return getattr(os, name)

    def listdir(self, path):
        names = os.listdir(path)
        # With ``first``, a fixed enumeration order a filesystem may produce: that name, then the rest by name.
        return names if self.first is None else sorted(names, key=lambda name: (name != self.first, name))

    def unlink(self, path, *, dir_fd=None):
        if len(self.removed) >= self.allowed:
            self.refused.append(str(path))
            raise OSError(errno.EIO, "synthetic interruption partway through a retirement")
        os.unlink(path, dir_fd=dir_fd)
        self.removed.append(str(path))


# --- 1. a worktree nested in a managed directory -----------------------------------------------------------


@pytest.mark.parametrize("route", ["audit_close", "resource_close"])
def test_a_worktree_nested_in_a_managed_directory_retires_first_and_both_retire(checkout, tmp_path, run_cmd, route):
    work = tmp_path.resolve()
    cli = base._cli(run_cmd, work)
    common = base._common(checkout.repo)
    outer = work / "outer-dir"
    outer_rid = api.create_directory(checkout.ws, HOLDER, path=str(outer), actor="manager")["rid"]
    inner = outer / "inner-tree"
    made = api.create_worktree(checkout.ws, HOLDER, path=str(inner), actor="manager")
    inner_rid, admin = base._rid(made, "worktree"), Path(made["identity"]["git_admin"])
    # Firing control: Git registers the recorded worktree inside the recorded directory.
    assert str(inner) in base._worktrees(checkout.repo) and inner.is_relative_to(outer)
    plan = _plan(cli, checkout.repo, HOLDER, code=EXIT_OK)
    assert plan[outer_rid]["disposition"] == plan[inner_rid]["disposition"] == "remove"

    if route == "resource_close":
        # The audit close leaves both behind (an untracked note blocks the worktree, so its container stays);
        # once the note is gone, the two are retired together by name.
        (inner / "note.txt").write_text("left at the audit close\n", encoding="utf-8")
        closed = base._abandon(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_ATTENTION,))
        closeout = base._by_rid(closed["closeout"])
        assert closeout[inner_rid]["disposition"] == closeout[outer_rid]["disposition"] == "blocked"
        assert closed["resources"] == []
        (inner / "note.txt").unlink()
        envelope = _close_resources(cli, checkout.repo, outer_rid, inner_rid, allowed=(EXIT_OK, EXIT_ATTENTION))
        outcomes = envelope["results"]
    else:
        closed = base._abandon(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_OK, EXIT_ATTENTION))
        closeout = base._by_rid(closed["closeout"])
        assert closeout[outer_rid]["disposition"] == closeout[inner_rid]["disposition"] == "claimed by this close"
        outcomes = closed["resources"]
    # Deepest first: the worktree is retired, then the directory that contained it.
    assert _outcomes(outcomes) == [(inner_rid, "removed"), (outer_rid, "removed")], outcomes
    assert not outer.exists() and not admin.exists() and str(inner) not in base._worktrees(checkout.repo)
    for rid in (inner_rid, outer_rid):
        assert base._generations(common, rid) == {1: "RETIRED"}


def test_a_shared_inner_worktree_keeps_its_container_until_its_last_use_closes(checkout, tmp_path, run_cmd):
    work = tmp_path.resolve()
    cli = base._cli(run_cmd, work)
    common = base._common(checkout.repo)
    outer = work / "outer-dir"
    outer_rid = api.create_directory(checkout.ws, HOLDER, path=str(outer), actor="manager")["rid"]
    inner = outer / "inner-tree"
    made = api.create_worktree(checkout.ws, HOLDER, path=str(inner), actor="manager")
    inner_rid, admin = base._rid(made, "worktree"), Path(made["identity"]["git_admin"])
    # Control: unshared, the close would propose both for removal.
    plan = _plan(cli, checkout.repo, HOLDER, code=EXIT_OK)
    assert plan[outer_rid]["disposition"] == plan[inner_rid]["disposition"] == "remove"

    # Changed property: a second, live audit uses the inner worktree.
    cli("--repo", checkout.repo, "--workspace", WS, "resource", "associate", "--audit-id", PARTNER, "--actor",
        "manager", "--resource", inner_rid)
    plan = _plan(cli, checkout.repo, HOLDER, code=EXIT_ATTENTION)
    assert plan[inner_rid]["disposition"] == "shared" and plan[outer_rid]["disposition"] == "blocked"
    before = snapshot_tree(outer)
    closed = base._abandon(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_ATTENTION,))
    closeout = base._by_rid(closed["closeout"])
    assert closeout[inner_rid]["disposition"] == "shared"
    assert f"{WS}:{PARTNER}" in " ".join(closeout[inner_rid]["reasons"])
    assert closeout[outer_rid]["disposition"] == "blocked"
    outer_reasons = " ".join(closeout[outer_rid]["reasons"])
    assert f"contains recorded worktree {inner_rid}" in outer_reasons
    assert f"other checkouts are registered inside it: {inner}" in outer_reasons
    # Nothing was claimed or removed.
    assert closed["resources"] == [] and snapshot_tree(outer) == before
    assert base._claim_files(common, outer_rid) == [] == base._claim_files(common, inner_rid)
    assert str(inner) in base._worktrees(checkout.repo) and admin.is_dir()
    # Invariance: explicit retirement is refused the same way, alone or named together, and writes nothing.
    refused = _refused_close(cli, checkout.repo, outer_rid)
    assert refused["reason"] == "resource_blocked" and f"contains recorded worktree {inner_rid}" in refused["message"]
    assert _refused_close(cli, checkout.repo, outer_rid, inner_rid)["reason"] == "resource_shared"
    assert base._claim_files(common, outer_rid) == [] == base._claim_files(common, inner_rid)
    assert snapshot_tree(outer) == before

    # The last use ends: the partner's close retires the worktree, and then the directory retires alone.
    last = base._abandon(cli, checkout.repo, WS, PARTNER)
    assert _outcomes(last["resources"]) == [(inner_rid, "removed")]
    assert outer.is_dir() and not inner.exists() and not admin.exists()
    retired = _close_resources(cli, checkout.repo, outer_rid)
    assert _outcomes(retired["results"]) == [(outer_rid, "removed")] and not outer.exists()
    for rid in (inner_rid, outer_rid):
        assert base._generations(common, rid) == {1: "RETIRED"}


# --- 2. a checkout Stewart did not record ---------------------------------------------------------------------


def test_an_unrecorded_checkout_inside_a_managed_directory_blocks_it_until_git_removes_it(checkout, tmp_path, run_cmd):
    work = tmp_path.resolve()
    cli = base._cli(run_cmd, work)
    common = base._common(checkout.repo)
    host, plain = work / "host-dir", work / "plain-dir"
    host_rid = api.create_directory(checkout.ws, HOLDER, path=str(host), actor="manager")["rid"]
    plain_rid = api.create_directory(checkout.ws, HOLDER, path=str(plain), actor="manager")["rid"]
    foreign = host / "foreign-tree"
    checkout.git("worktree", "add", "-q", "--detach", str(foreign), "HEAD")
    # Firing control: Git registers a checkout inside the managed directory, and no record names it.
    assert str(foreign) in base._worktrees(checkout.repo)
    assert [(holdings.load(str(common), rid).get("identity") or {}).get("path") for rid in base._rids(common)] \
        .count(str(foreign)) == 0
    foreign_bytes = snapshot_tree(foreign)

    closed = base._abandon(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_ATTENTION,))
    closeout = base._by_rid(closed["closeout"])
    assert closeout[host_rid]["disposition"] == "blocked"
    assert f"other checkouts are registered inside it: {foreign}" in " ".join(closeout[host_rid]["reasons"])
    # Differing only in the foreign checkout: the other directory of the same audit retires.
    assert _outcomes(closed["resources"]) == [(plain_rid, "removed")] and not plain.exists()
    assert host.is_dir() and snapshot_tree(foreign) == foreign_bytes
    assert base._claim_files(common, host_rid) == []
    for _ in range(2):  # Invariance: each later refusal is the same and writes nothing.
        refused = _refused_close(cli, checkout.repo, host_rid)
        assert refused["reason"] == "resource_blocked" and str(foreign) in refused["message"]
    assert base._claim_files(common, host_rid) == [] and snapshot_tree(foreign) == foreign_bytes
    assert str(foreign) in base._worktrees(checkout.repo)

    checkout.git("worktree", "remove", str(foreign))
    assert str(foreign) not in base._worktrees(checkout.repo) and os.listdir(host) == []
    retired = _close_resources(cli, checkout.repo, host_rid)
    assert _outcomes(retired["results"]) == [(host_rid, "removed")] and not host.exists()
    assert base._generations(common, host_rid) == {1: "RETIRED"}


# --- 3. branches that alone hold a commit ---------------------------------------------------------------------


def test_two_managed_branches_that_alone_hold_a_commit_are_both_kept(checkout, tmp_path, run_cmd):
    work = tmp_path.resolve()
    cli = base._cli(run_cmd, work)
    common = base._common(checkout.repo)
    first = api.create_branch(checkout.ws, HOLDER, branch="audit/first", actor="manager")["rid"]
    second = api.create_branch(checkout.ws, HOLDER, branch="audit/second", actor="manager")["rid"]
    merged = api.create_branch(checkout.ws, HOLDER, branch="audit/merged", actor="manager")["rid"]
    head, tree = checkout.git("rev-parse", "HEAD"), checkout.git("rev-parse", "HEAD^{tree}")
    shared = checkout.git("commit-tree", tree, "-p", head, "-m", "work held only by two managed branches")
    elsewhere = checkout.git("commit-tree", tree, "-p", head, "-m", "work an unmanaged branch also holds")
    for ref, commit in (("audit/first", shared), ("audit/second", shared), ("audit/merged", elsewhere)):
        checkout.git("update-ref", f"refs/heads/{ref}", commit)
    checkout.git("branch", "keeper", elsewhere)
    # Firing control: exactly the two managed refs contain the new commit.
    holders = checkout.git("for-each-ref", "--contains", shared, "--format=%(refname)").split()
    assert sorted(holders) == ["refs/heads/audit/first", "refs/heads/audit/second"]

    closed = base._abandon(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_ATTENTION,))
    closeout = base._by_rid(closed["closeout"])
    for rid in (first, second):
        assert closeout[rid]["disposition"] == "blocked", closeout[rid]
        reasons = " ".join(closeout[rid]["reasons"])
        assert "unmerged work" in reasons
        assert "removable only while resources retiring with it are kept" in reasons
        assert base._claim_files(common, rid) == []
    # Differing only in the property: a tip that a ref which is not retiring also contains retires.
    assert closeout[merged]["disposition"] == "claimed by this close"
    assert _outcomes(closed["resources"]) == [(merged, "removed")]
    assert base._ref(checkout.repo, "refs/heads/audit/merged") is None
    assert base._ref(checkout.repo, "refs/heads/keeper") == elsewhere
    # Invariance: the commit is still reachable from both refs, and naming them together changes nothing.
    assert base._ref(checkout.repo, "refs/heads/audit/first") == base._ref(checkout.repo, "refs/heads/audit/second") \
        == shared
    refused = _refused_close(cli, checkout.repo, first, second)
    assert refused["reason"] == "resource_blocked" and "unmerged work" in refused["message"]
    assert base._claim_files(common, first) == [] == base._claim_files(common, second)
    # One at a time, the commit never loses its last ref.
    assert _outcomes(_close_resources(cli, checkout.repo, first)["results"]) == [(first, "removed")]
    refused = _refused_close(cli, checkout.repo, second)
    assert refused["reason"] == "resource_blocked" and "unmerged work" in refused["message"]
    assert base._ref(checkout.repo, "refs/heads/audit/second") == shared
    assert base._claim_files(common, second) == []


# --- 4. a write between evaluation and claim --------------------------------------------------------------------


def test_a_write_between_evaluation_and_claim_releases_the_claim(checkout, tmp_path, monkeypatch):
    work = tmp_path.resolve()
    common = base._common(checkout.repo)
    gap, steady = work / "gap-dir", work / "steady-dir"
    gap_rid = api.create_directory(checkout.ws, HOLDER, path=str(gap), actor="manager")["rid"]
    steady_rid = api.create_directory(checkout.ws, HOLDER, path=str(steady), actor="manager")["rid"]
    for folder in (gap, steady):
        (folder / "early.txt").write_text("present when the close evaluated it\n", encoding="utf-8")
    real = holdings._claim
    fired: list[str] = []

    def write_then_claim(common_, view, evaluation, claimant):
        if view["rid"] == gap_rid:
            assert base._claim_files(common, gap_rid) == [], "the write precedes the claim record"
            assert evaluation["disposition"] == "remove"
            (gap / "late.txt").write_text("written after evaluation, before the claim\n", encoding="utf-8")
            fired.append(evaluation["frozen"]["snapshot"]["sha256"])
        return real(common_, view, evaluation, claimant)

    with monkeypatch.context() as patch:
        patch.setattr(holdings, "_claim", write_then_claim)
        closed = api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="resources done")
    assert len(fired) == 1, "firing control: the directory changed between its evaluation and its claim"
    claim = support.read_json(base._records(common, gap_rid) / "claims/0001.json")
    # The claim froze the evaluation's inventory, not what was there when the claim was written.
    assert [entry["path"] for entry in claim["frozen"]["snapshot"]["entries"]] == ["early.txt"]
    assert claim["frozen"]["snapshot"]["sha256"] == fired[0]
    outcomes = base._by_rid(closed["resources"])
    assert outcomes[gap_rid]["outcome"] == "kept"
    assert any("contents changed after the claim was frozen" in item for item in outcomes[gap_rid]["reasons"])
    # Differing only in the write: the other directory claimed by the same close retires.
    assert outcomes[steady_rid]["outcome"] == "removed" and not steady.exists()
    assert base._generations(common, gap_rid) == {1: "RELEASED"}
    released = support.read_json(base._records(common, gap_rid) / "claims/0001.RELEASED.json")
    assert any("contents changed" in item for item in released["observation"])
    assert sorted(os.listdir(gap)) == ["early.txt", "late.txt"]
    assert (gap / "late.txt").read_text() == "written after evaluation, before the claim\n"
    # Invariance: without the late write, a new generation retires it; the released one is kept as it was.
    (gap / "late.txt").unlink()
    retired = api.close_resources(checkout.repo, [gap_rid], actor="manager")
    assert _outcomes(retired["results"]) == [(gap_rid, "removed")] and not gap.exists()
    assert base._generations(common, gap_rid) == {1: "RELEASED", 2: "RETIRED"}
    assert support.read_json(base._records(common, gap_rid) / "claims/0001.RELEASED.json") == released


# --- 5. a draft record that does not verify -------------------------------------------------------------------


def test_an_unreadable_draft_record_blocks_path_resources_until_it_verifies(checkout, tmp_path, run_cmd):
    work = tmp_path.resolve()
    cli = base._cli(run_cmd, work)
    common = base._common(checkout.repo)
    scratch = work / "scratch-dir"
    scratch_rid = api.create_directory(checkout.ws, HOLDER, path=str(scratch), actor="manager")["rid"]
    branch_rid = api.create_branch(checkout.ws, HOLDER, branch="audit/scratch", actor="manager")["rid"]
    draft = api.initialize(checkout.ws, "drafted-question", "HEAD", inputs=["input.txt"], replace_prompt=True)
    record = Path(draft["draft_record"]) / "STARTED.json"
    assert record.parent.parent == common / "stewart/audits" / checkout.ws.slug / "drafted-question" / "init"
    original = record.read_bytes()
    # Control: a draft that verifies pins only its own checkout, which lies outside the directory.
    plan = _plan(cli, checkout.repo, HOLDER, code=EXIT_OK)
    assert plan[scratch_rid]["disposition"] == plan[branch_rid]["disposition"] == "remove"

    # Changed property: the other audit's start record no longer parses.
    record.write_bytes(original[: len(original) // 2])
    plan = _plan(cli, checkout.repo, HOLDER, code=EXIT_ATTENTION)
    reasons = " ".join(plan[scratch_rid]["reasons"])
    assert plan[scratch_rid]["disposition"] == "blocked"
    assert "records that cannot be read may use it" in reasons and str(record.parent) in reasons
    # Invariance: a branch has no path such a record could pin; it is still proposed.
    assert plan[branch_rid]["disposition"] == "remove"
    closed = base._abandon(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_ATTENTION,))
    assert base._by_rid(closed["closeout"])[scratch_rid]["disposition"] == "blocked"
    assert _outcomes(closed["resources"]) == [(branch_rid, "removed")]
    assert scratch.is_dir() and base._claim_files(common, scratch_rid) == []
    refused = _refused_close(cli, checkout.repo, scratch_rid)
    assert refused["reason"] == "resource_blocked" and "records that cannot be read" in refused["message"]
    assert base._claim_files(common, scratch_rid) == []

    record.write_bytes(original)
    retired = _close_resources(cli, checkout.repo, scratch_rid)
    assert _outcomes(retired["results"]) == [(scratch_rid, "removed")] and not scratch.exists()
    assert base._generations(common, scratch_rid) == {1: "RETIRED"}
    assert record.read_bytes() == original


# --- 6. a substituted .git ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("substitute", ["other_gitdir", "directory"])
def test_a_managed_worktree_whose_gitfile_was_replaced_is_never_removed(checkout, tmp_path, run_cmd, substitute):
    work = tmp_path.resolve()
    cli = base._cli(run_cmd, work)
    common = base._common(checkout.repo)
    tree = work / "managed-tree"
    made = api.create_worktree(checkout.ws, HOLDER, path=str(tree), actor="manager")
    rid, admin = base._rid(made, "worktree"), Path(made["identity"]["git_admin"])
    gitfile = tree / ".git"
    original = gitfile.read_bytes()
    assert original.strip() == f"gitdir: {admin}".encode()
    # Control: with its own gitdir file the worktree is proposed for removal.
    assert _plan(cli, checkout.repo, HOLDER, code=EXIT_OK)[rid]["disposition"] == "remove"
    other = work / "other-tree"
    checkout.git("worktree", "add", "-q", "--detach", str(other), "HEAD")
    other_admin = (other / ".git").read_text(encoding="utf-8").strip().removeprefix("gitdir: ")
    gitfile.unlink()
    if substitute == "other_gitdir":
        gitfile.write_text(f"gitdir: {other_admin}\n", encoding="utf-8")
    else:
        gitfile.mkdir()
        (gitfile / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    held, other_bytes = snapshot_tree(tree), snapshot_tree(other)

    closed = base._abandon(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_ATTENTION,))
    item = base._by_rid(closed["closeout"])[rid]
    assert item["disposition"] == "blocked"
    assert any(".git is not the regular gitdir file" in reason for reason in item["reasons"]), item["reasons"]
    assert closed["resources"] == [] and base._claim_files(common, rid) == []
    refused = _refused_close(cli, checkout.repo, rid)
    assert refused["reason"] == "resource_blocked" and ".git is not the regular gitdir file" in refused["message"]
    # Invariance: nothing in either checkout changed, and both registrations remain.
    assert snapshot_tree(tree) == held and snapshot_tree(other) == other_bytes
    assert str(tree) in base._worktrees(checkout.repo) and admin.is_dir() and base._claim_files(common, rid) == []

    # Differing only in the .git entry: its recorded bytes restored, the worktree retires.
    if gitfile.is_dir():
        shutil.rmtree(gitfile)
    else:
        gitfile.unlink()
    gitfile.write_bytes(original)
    retired = _close_resources(cli, checkout.repo, rid)
    assert _outcomes(retired["results"]) == [(rid, "removed")]
    assert not tree.exists() and not admin.exists() and str(tree) not in base._worktrees(checkout.repo)
    assert snapshot_tree(other) == other_bytes and str(other) in base._worktrees(checkout.repo)


# --- 7. an interrupted retirement ---------------------------------------------------------------------------------


@pytest.mark.parametrize("added", [False, True], ids=["unchanged", "added"])
@pytest.mark.parametrize("kind", ["directory", "worktree"])
def test_an_interrupted_retirement_resumes_only_over_what_it_froze(checkout, tmp_path, run_cmd, monkeypatch, kind,
                                                                   added):
    work = tmp_path.resolve()
    cli = base._cli(run_cmd, work)
    common = base._common(checkout.repo)
    target = work / f"managed-{kind}"
    admin = None
    if kind == "directory":
        rid = api.create_directory(checkout.ws, HOLDER, path=str(target), actor="manager")["rid"]
        _fill(target)
    else:
        made = api.create_worktree(checkout.ws, HOLDER, path=str(target), actor="manager")
        rid, admin = base._rid(made, "worktree"), Path(made["identity"]["git_admin"])
    before = snapshot_tree(target)
    stand_in = _UnlinkFailsAfter(1)

    with monkeypatch.context() as patch:
        patch.setattr(_removal, "os", stand_in)
        closed = api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="resources done")
    # Firing control: one entry was removed, then the removal failed and the failure was recorded.
    assert len(stand_in.removed) == 1 and len(stand_in.refused) == 1
    [outcome] = closed["resources"]
    assert (outcome["rid"], outcome["outcome"]) == (rid, "failed")
    assert "synthetic interruption" in outcome["detail"]
    attempts = _attempts(common, rid)
    assert len(attempts) == 1 and base._generations(common, rid) == {1: None}
    claim_bytes = (base._records(common, rid) / "claims/0001.json").read_bytes()
    remaining = snapshot_tree(target)
    assert target.is_dir() and set(remaining) < set(before)
    assert all(before[path] == digest for path, digest in remaining.items()), "what is left is what was frozen"
    if admin is not None:
        assert admin.is_dir() and str(target) in base._worktrees(checkout.repo)
    shown = cli("--repo", checkout.repo, "resource", "show", "--resource", rid, allowed=(EXIT_ATTENTION,))["result"]
    assert shown["disposition"] == "claimed" and shown["claims"][0]["attempts"] == attempts

    late = target / "added-after-interruption.txt"
    if added:
        late.write_text("not in the frozen inventory\n", encoding="utf-8")
    resumed = _close_resources(cli, checkout.repo, rid, allowed=(EXIT_ATTENTION,) if added else (EXIT_OK,))
    [item] = resumed["results"]
    assert item["rid"] == rid and item["resumed"] is True
    if added:
        # Changed property: an entry the claim never froze ends the claim and keeps everything left.
        assert item["outcome"] == "kept"
        expected = f"its contents changed after the claim was frozen (added or changed: {late.name})"
        assert expected in " ".join(item["reasons"])
        assert base._generations(common, rid) == {1: "RELEASED"}
        assert late.read_text(encoding="utf-8") == "not in the frozen inventory\n"
        assert {path: digest for path, digest in snapshot_tree(target).items() if path != late.name} == remaining
        if admin is not None:
            assert admin.is_dir() and str(target) in base._worktrees(checkout.repo)
    else:
        # Only removals happened since the claim: the same generation finishes, accepting the partial removal.
        assert item["outcome"] == "removed" and not target.exists()
        assert base._generations(common, rid) == {1: "RETIRED"}
        if admin is not None:
            assert not admin.exists() and str(target) not in base._worktrees(checkout.repo)
    # Invariance: no new generation; the claim and the first attempt's records are as they were. A resumed
    # removal records its own attempt before removing anything; a released claim attempts nothing.
    assert (base._records(common, rid) / "claims/0001.json").read_bytes() == claim_bytes
    after = _attempts(common, rid)
    assert after == attempts if added else (len(after) == 2 and attempts[0] in after)
    assert base._attempt_files(common, rid, failed=True) == [attempts[0].removesuffix(".json") + ".FAILED.json"]


def test_a_worktree_retirement_interrupted_anywhere_never_retires_while_git_registers_it(checkout, tmp_path,
                                                                                         monkeypatch):
    """Sweep every unlink of one worktree retirement as the interruption point, then resume it.

    Removal enumerates entries with the marker first and the rest by name, an
    order a filesystem may produce; the sweep covers the worktree's own
    entries and its Git administration.
    """
    work = tmp_path.resolve()
    common = base._common(checkout.repo)
    rows: dict[int, dict] = {}
    for point in range(1, 61):
        ident = f"sweep-{point:02d}"
        target = work / f"tree-{point:02d}"
        made = api.create_worktree(checkout.ws, ident, path=str(target), actor="manager")
        rid, admin = base._rid(made, "worktree"), Path(made["identity"]["git_admin"])
        stand_in = _UnlinkFailsAfter(point - 1, first=holdings.MARKER)
        with monkeypatch.context() as patch:
            patch.setattr(_removal, "os", stand_in)
            closed = api.close(checkout.ws, ident, actor="manager", abandon=True, reason="interruption sweep")
        [first] = closed["resources"]
        if not stand_in.refused:
            # Control: past the last unlink, the uninterrupted retirement removes the path and its administration.
            assert first["outcome"] == "removed" and base._generations(common, rid) == {1: "RETIRED"}
            assert not target.exists() and not admin.exists() and str(target) not in base._worktrees(checkout.repo)
            break
        assert first["outcome"] == "failed" and base._generations(common, rid) == {1: None}
        row = {"path_present": os.path.lexists(target), "admin_present": admin.is_dir(),
               "marker_present": (admin / holdings.MARKER).exists()}
        resumed = api.close_resources(checkout.repo, [rid], actor="manager")
        [item] = resumed["results"]
        row.update(resumed=item["outcome"], ending=base._generations(common, rid)[1], admin=admin.exists(),
                   registered=str(target) in base._worktrees(checkout.repo))
        rows[point] = row
    else:
        raise AssertionError("the sweep never reached an uninterrupted retirement")
    # Firing control: interruptions fell inside the worktree's own entries and, with the path already gone,
    # inside its administration (here, after its marker was unlinked).
    assert any(row["path_present"] for row in rows.values())
    assert any(not row["path_present"] and row["admin_present"] for row in rows.values()), rows
    # Differing in where it fell: interrupted inside the worktree's own entries, resuming drops everything.
    inside = {point: row for point, row in rows.items() if row["path_present"]}
    assert all(row["ending"] == "RETIRED" and not row["admin"] and not row["registered"]
               for row in inside.values()), inside
    # Invariance: wherever the interruption fell, a claim that ended RETIRED left no Git registration behind.
    left = {point: row for point, row in rows.items() if row["ending"] == "RETIRED" and (row["registered"]
                                                                                           or row["admin"])}
    assert left == {}, left


# --- 8. a leaf replaced after revalidation -----------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["directory", "worktree"])
def test_a_resource_replaced_after_revalidation_is_left_in_place(checkout, tmp_path, run_cmd, monkeypatch, kind):
    work = tmp_path.resolve()
    cli = base._cli(run_cmd, work)
    common = base._common(checkout.repo)
    target, steady = work / f"managed-{kind}", work / "steady-dir"
    if kind == "directory":
        rid = api.create_directory(checkout.ws, HOLDER, path=str(target), actor="manager")["rid"]
        _fill(target)
    else:
        rid = base._rid(api.create_worktree(checkout.ws, HOLDER, path=str(target), actor="manager"), "worktree")
    steady_rid = api.create_directory(checkout.ws, HOLDER, path=str(steady), actor="manager")["rid"]
    original = snapshot_tree(target)
    aside = work / f"{kind}-moved-aside"
    real = holdings._revalidate
    fired: list[list[str]] = []

    def replace_after_revalidation(common_, view, claim, index):
        findings = real(common_, view, claim, index)
        if view["rid"] == rid:
            fired.append(findings)
            target.rename(aside)
            target.mkdir()
            (target / "impostor.txt").write_text("not the frozen resource\n", encoding="utf-8")
        return findings

    with monkeypatch.context() as patch:
        patch.setattr(holdings, "_revalidate", replace_after_revalidation)
        closed = api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="resources done")
    # Firing control: the frozen resource passed revalidation, and only then was its leaf replaced.
    assert fired == [[]]
    outcomes = base._by_rid(closed["resources"])
    assert outcomes[rid]["outcome"] == "failed" and "not the recorded entry" in outcomes[rid]["detail"]
    # Differing only in the replacement: the other directory claimed by the same close retires.
    assert outcomes[steady_rid]["outcome"] == "removed" and not steady.exists()
    assert sorted(os.listdir(target)) == ["impostor.txt"]
    assert (target / "impostor.txt").read_text(encoding="utf-8") == "not the frozen resource\n"
    assert snapshot_tree(aside) == original, "the frozen original, moved aside, is not removed through the path"
    assert len(_attempts(common, rid)) == 1 and base._generations(common, rid) == {1: None}

    # Invariance: resuming the claim never removes the replacement; it ends the claim instead.
    resumed = _close_resources(cli, checkout.repo, rid, allowed=(EXIT_ATTENTION,))
    [item] = resumed["results"]
    assert item["outcome"] == "kept" and item["resumed"] is True
    assert "not the one frozen in the claim" in " ".join(item["reasons"])
    assert base._generations(common, rid) == {1: "RELEASED"}
    assert sorted(os.listdir(target)) == ["impostor.txt"] and snapshot_tree(aside) == original


@pytest.mark.parametrize("swap", [False, True], ids=["recorded", "swapped"])
def test_a_session_checkout_swapped_before_deletion_is_left_in_place(checkout, monkeypatch, swap):
    prepared = support.prepared_session(checkout)
    worktree = prepared.worktree
    inspected = os.stat(worktree, follow_symlinks=False)
    held = worktree.with_name(worktree.name + "-original")
    real = close_module._delete_checkout
    calls: list[tuple[str, dict]] = []

    def swap_then_delete(parent, name, **kwargs):
        calls.append((name, kwargs))
        if swap:
            worktree.rename(held)
            worktree.mkdir()
            (worktree / "impostor.txt").write_text("not the recorded checkout\n", encoding="utf-8")
        return real(parent, name, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(close_module, "_delete_checkout", swap_then_delete)
        result = close_module.close(checkout.ws, "one-question", actor="manager", abandon=True,
                                    reason="disposable swap comparison", discard_uncollected=True)
    # Firing control: deletion was handed the identity inspected before planning was rechecked.
    assert calls == [(worktree.name, {"identity": (inspected.st_dev, inspected.st_ino)})]
    step = result["results"][0]
    assert step["kind"] == "worktree"
    if not swap:
        # Differing only in the swap: the recorded checkout is the one removed.
        assert step["outcome"] == "removed" and not worktree.exists() and not held.exists()
        assert result["closed"] is not None and result["failed"] == []
        return
    assert step["outcome"] == "failed" and "not the recorded entry" in step["detail"]
    assert result["closed"] is None and result["failed"] == [step]
    assert sorted(os.listdir(worktree)) == ["impostor.txt"]
    assert held.is_dir() and (held / ".git").is_file(), "the recorded checkout moved aside is untouched"
    assert prepared.session.is_dir(), "removal stopped at the failure; the session's records remain"

    # Invariance: rerunning the close keeps the impostor and names it as a leftover.
    rerun = close_module.close(checkout.ws, "one-question", actor="manager")
    assert rerun["results"][0]["kind"] == "worktree" and rerun["results"][0]["outcome"].startswith("kept: ")
    assert str(worktree) in rerun["leftovers"]
    assert (worktree / "impostor.txt").read_text(encoding="utf-8") == "not the recorded checkout\n"
    assert held.is_dir() and (held / ".git").is_file()


# --- 9. another filesystem inside a resource (simulated device boundary) ----------------------------------


def _foreign_device(monkeypatch, name: str) -> list[str]:
    """Report a different device for directory entries called ``name``, as a mount point inside would.

    This simulates the device boundary with ``os.stat`` results only; no filesystem is mounted, so it qualifies
    how Stewart treats a device change, not any particular mount type.
    """
    real_stat = os.stat
    seen: list[str] = []

    def stat(path, *args, **kwargs):
        found = real_stat(path, *args, **kwargs)
        if os.fspath(path) == name and kwargs.get("dir_fd") is not None:
            seen.append(name)
            fields = list(found[:10])
            fields[2] = found.st_dev + 1
            return os.stat_result(fields)
        return found

    monkeypatch.setattr(os, "stat", stat)
    return seen


def test_another_filesystem_inside_a_resource_blocks_it_and_removal_never_enters_it(checkout, tmp_path,
                                                                                   monkeypatch):
    work = tmp_path.resolve()
    host, steady = work / "host-dir", work / "steady-dir"
    host_rid = api.create_directory(checkout.ws, HOLDER, path=str(host), actor="manager")["rid"]
    steady_rid = api.create_directory(checkout.ws, HOLDER, path=str(steady), actor="manager")["rid"]
    (host / "mounted").mkdir()
    (host / "mounted/keep.txt").write_text("on another filesystem\n", encoding="utf-8")
    common = base._common(checkout.repo)
    records = snapshot_tree(base._records(common))

    with monkeypatch.context() as patch:
        seen = _foreign_device(patch, "mounted")
        first = base._by_rid(api.close_plan(checkout.ws, HOLDER, abandon=True)["resources"])
        again = base._by_rid(api.close_plan(checkout.ws, HOLDER, abandon=True)["resources"])
    assert seen, "firing control: the entry inside reported another device"
    assert first[host_rid]["disposition"] == "blocked"
    assert "another filesystem is mounted inside it: mounted" in " ".join(first[host_rid]["reasons"])
    # Differing only in the device: the sibling directory without a boundary is removable.
    assert first[steady_rid]["disposition"] == "remove"
    # Invariance: planning again reports the same and writes nothing.
    assert again == first and snapshot_tree(base._records(common)) == records

    # Removal itself never descends across a device change, even when asked to remove the tree directly.
    with monkeypatch.context() as patch:
        _foreign_device(patch, "mounted")
        with pytest.raises(OSError) as raised:
            _removal.remove_path(host)
    assert raised.value.errno == errno.EXDEV
    assert (host / "mounted/keep.txt").read_text(encoding="utf-8") == "on another filesystem\n"
    # Control: with the real device, the same tree is removed whole.
    assert _removal.remove_path(host) == "removed" and not host.exists()


# --- 10. a disposal decision never overrides another audit's live use (review finding R1) ------------------


def _export_inside(checkout, ident: str, container: Path, durable: Path) -> tuple[str, str, dict]:
    """A managed directory holding a recorded export, beside an export with a durable destination outside it."""
    collected = api.collect(checkout.ws, ident, auditor_stopped="finished")
    container_rid = api.create_directory(checkout.ws, ident, path=str(container), actor="manager")["rid"]
    inside = api.export_evidence(checkout.ws, ident, collection=collected["collection"], selectors=["REPORT.md"],
                                 output=str(container / "package"), actor="manager")
    api.export_evidence(checkout.ws, ident, collection=collected["collection"], selectors=["REPORT.md"],
                        output=str(durable), actor="manager")
    return container_rid, inside["resource"], snapshot_tree(durable)


@pytest.mark.parametrize("shared", [False, True])
def test_a_disposed_export_another_live_audit_uses_keeps_its_container(checkout, tmp_path, run_cmd, shared):
    work = tmp_path.resolve()
    cli = base._cli(run_cmd, work)
    common = base._common(checkout.repo)
    ident = checkout.meta["audit_id"]
    support.prepared_session(checkout)
    container, durable = work / "container", work / "durable"
    container_rid, export_rid, outside = _export_inside(checkout, ident, container, durable)
    package = snapshot_tree(container / "package")
    if shared:
        api.associate(checkout.ws, PARTNER, rid=export_rid, actor="manager")
    # Firing control: the export lies inside the container, and only when shared does another audit use it.
    users = api.show_resource(checkout.repo, export_rid)["users"]
    assert any(user["live"] and user["audit"]["audit_id"] == PARTNER for user in users) == shared

    planned = base._by_rid(api.close_plan(checkout.ws, ident, abandon=True, dispose=[export_rid])["resources"])
    closed = api.close(checkout.ws, ident, actor="manager", abandon=True, reason="done", dispose=[export_rid])
    evaluation = base._by_rid(closed["closeout"])[container_rid]
    if not shared:
        # Differing only in the other audit's use: the recorded disposal decision removes both.
        assert planned[container_rid]["disposition"] == "remove" and not container.exists()
        assert base._generations(common, container_rid) == {1: "RETIRED"}
        assert base._generations(common, export_rid) == {1: "RETIRED"}
    else:
        blocker = f"contained export {export_rid} is still used by {WS}:{PARTNER}"
        for item in (planned[container_rid], evaluation):
            assert item["disposition"] == "blocked" and blocker in " ".join(item["reasons"])
        assert snapshot_tree(container / "package") == package
        assert base._claim_files(common, container_rid) == [] == base._claim_files(common, export_rid)
        records = snapshot_tree(base._records(common))
        refused = _refused_close(cli, checkout.repo, container_rid)
        assert refused["reason"] == "resource_blocked", "the disposal decision does not override the live use"
        assert snapshot_tree(base._records(common)) == records
        # Once the other audit's use ends, the same decision retires both under the explicit close.
        base._abandon(cli, checkout.repo, WS, PARTNER)
        retired = cli("--repo", checkout.repo, "close", "--actor", "manager", "--resource", container_rid,
                      "--dispose", export_rid)["result"]
        assert retired["results"][0]["outcome"] == "removed" and not container.exists()
        assert base._generations(common, export_rid) == {1: "RETIRED"}
    # Invariance: the export with a durable destination outside the container is untouched in every case.
    assert snapshot_tree(durable) == outside


def test_a_use_of_a_disposed_export_that_appears_after_the_claim_keeps_the_container(checkout, tmp_path,
                                                                                    monkeypatch):
    work = tmp_path.resolve()
    common = base._common(checkout.repo)
    ident = checkout.meta["audit_id"]
    support.prepared_session(checkout)
    container, durable = work / "container", work / "durable"
    container_rid, export_rid, outside = _export_inside(checkout, ident, container, durable)
    package = snapshot_tree(container / "package")
    real_retire, real_refuse = holdings.retire_claim, holdings.refuse_retiring
    seen: list[str] = []

    def associate_then_retire(common_, view, claim):
        if view["rid"] == container_rid and not seen:
            # An association made now, inside a container being retired, is refused before it is recorded.
            with pytest.raises(StewartError) as refused:
                api.associate(checkout.ws, PARTNER, rid=export_rid, actor="manager")
            seen.append(refused.value.reason)
            # One that passed that check before the claim existed lands now; revalidation still sees it.
            holdings.refuse_retiring = lambda *args, **kwargs: None
            try:
                api.associate(checkout.ws, PARTNER, rid=export_rid, actor="manager")
            finally:
                holdings.refuse_retiring = real_refuse
        return real_retire(common_, view, claim)

    with monkeypatch.context() as patch:
        patch.setattr(holdings, "retire_claim", associate_then_retire)
        closed = api.close(checkout.ws, ident, actor="manager", abandon=True, reason="done", dispose=[export_rid])
    # Firing control: the container was claimed, and the late association was refused, then forced through.
    assert seen == ["resource_retiring"]
    outcome = base._by_rid(closed["resources"])[container_rid]
    assert outcome["outcome"] == "kept"
    assert f"contained export {export_rid} is still used by" in " ".join(outcome["reasons"])
    assert base._generations(common, container_rid) == {1: "RELEASED"} and _attempts(common, container_rid) == []
    assert snapshot_tree(container / "package") == package and snapshot_tree(durable) == outside


def _damage_creation(common: Path, rid: str, state: str) -> None:
    """Inject missing or invalid historical evidence in a disposable fixture; product code never repairs it."""
    record = base._records(common, rid)
    outcome = record / "CREATED.json"
    if state == "malformed":
        outcome.write_bytes(b'{"interrupted":')
    elif state == "missing":
        outcome.unlink()
    elif state == "failed":
        value = support.read_json(outcome)
        value.update(status="failed", identity=None, error={"reason": "resource_creation", "message": "failed"})
        outcome.write_text(json.dumps(value) + "\n", encoding="utf-8")
    elif state == "unlocatable":
        (record / "CREATE.json").write_bytes(b'{"interrupted":')


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("state", ["valid", "malformed", "missing", "failed", "unlocatable"])
def test_a_contained_export_without_verified_creation_never_gains_disposal_authority(checkout, tmp_path,
                                                                                     shared, state):
    common, ident = base._common(checkout.repo), checkout.meta["audit_id"]
    support.prepared_session(checkout)
    container, durable = tmp_path.resolve() / "container", tmp_path.resolve() / "durable"
    container_rid, export_rid, outside = _export_inside(checkout, ident, container, durable)
    package = snapshot_tree(container / "package")
    if shared:
        api.associate(checkout.ws, PARTNER, rid=export_rid, actor="manager")
    _damage_creation(common, export_rid, state)
    record = snapshot_tree(base._records(common, export_rid))
    # Firing control: the outcome's identity disappears, though the payload and any other audit's use remain.
    shown = api.show_resource(checkout.repo, export_rid)
    assert bool(shown["identity"]) == (state == "valid")
    assert snapshot_tree(container / "package") == package
    plan = base._by_rid(api.close_plan(checkout.ws, ident, abandon=True, dispose=[export_rid])["resources"])
    closed = api.close(checkout.ws, ident, actor="manager", abandon=True, reason="done", dispose=[export_rid])
    if state == "valid" and not shared:
        # Changing only the record's validity permits the otherwise eligible, unshared disposal.
        assert plan[container_rid]["disposition"] == "remove" and not container.exists()
        assert base._generations(common, export_rid) == {1: "RETIRED"}
    else:
        assert plan[container_rid]["disposition"] == "blocked"
        assert base._by_rid(closed["closeout"])[container_rid]["disposition"] == "blocked"
        assert snapshot_tree(container / "package") == package
        assert snapshot_tree(base._records(common, export_rid)) == record
        assert base._claim_files(common, container_rid) == [], "uncertainty never grants a removal claim"
        if state == "unlocatable":
            assert "cannot be located" in " ".join(plan[container_rid]["reasons"])
        elif state in ("missing", "failed"):
            assert "intended location only blocks removal" in " ".join(plan[container_rid]["reasons"])
    # Invariance: the independent durable export is untouched, including when uncertainty is unlocatable.
    assert snapshot_tree(durable) == outside


@pytest.mark.parametrize("inside", [False, True])
def test_an_unresolved_intended_location_only_blocks_containers_it_can_intersect(checkout, tmp_path, inside):
    common, work = base._common(checkout.repo), tmp_path.resolve()
    container = work / "container"
    container_rid = api.create_directory(checkout.ws, HOLDER, path=str(container), actor="manager")["rid"]
    uncertain = (container if inside else work) / "uncertain"
    rid = api.create_directory(checkout.ws, HOLDER, path=str(uncertain), actor="manager")["rid"]
    _fill(uncertain)
    _damage_creation(common, rid, "missing")
    record, payload = snapshot_tree(base._records(common, rid)), snapshot_tree(uncertain)
    assert api.show_resource(checkout.repo, rid)["creation"] == "unresolved"
    planned = base._by_rid(api.close_plan(checkout.ws, HOLDER, abandon=True)["resources"])
    assert planned[container_rid]["disposition"] == ("blocked" if inside else "remove")
    api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="done")
    assert container.exists() == inside
    # The intended location can establish exclusion; it never grants authority over the uncertain payload.
    assert snapshot_tree(uncertain) == payload and snapshot_tree(base._records(common, rid)) == record


@pytest.mark.parametrize("state", ["valid", "malformed", "missing", "unlocatable", "unlocatable-outside"])
def test_a_dependency_losing_its_identity_after_the_claim_keeps_the_container(checkout, tmp_path, monkeypatch,
                                                                            state):
    common, ident = base._common(checkout.repo), checkout.meta["audit_id"]
    support.prepared_session(checkout)
    container, durable = tmp_path.resolve() / "container", tmp_path.resolve() / "durable"
    container_rid, export_rid, outside = _export_inside(checkout, ident, container, durable)
    package = snapshot_tree(container / "package")
    victim = (next(rid for rid in holdings.rids(str(common))
                   if (holdings.load(str(common), rid).get("identity") or {}).get("path") == str(durable))
              if state == "unlocatable-outside" else export_rid)
    real_retire, seen = holdings.retire_claim, []

    def damage_then_retire(common_, view, claim):
        if view["rid"] == container_rid and not seen:
            assert [item["rid"] for item in claim["claim"]["disposed"]] == [export_rid]
            _damage_creation(common, victim, "unlocatable" if state == "unlocatable-outside" else state)
            seen.append(snapshot_tree(base._records(common, victim)))
        return real_retire(common_, view, claim)

    with monkeypatch.context() as patch:
        patch.setattr(holdings, "retire_claim", damage_then_retire)
        closed = api.close(checkout.ws, ident, actor="manager", abandon=True, reason="done", dispose=[export_rid])
    assert len(seen) == 1, "the dependency changed after a claim froze its valid identity"
    outcome = base._by_rid(closed["resources"])[container_rid]
    assert outcome["outcome"] == ("removed" if state == "valid" else "kept")
    if state != "valid":
        assert base._generations(common, container_rid) == {1: "RELEASED"}
        assert _attempts(common, container_rid) == [], "revalidation refuses before a removal attempt"
        assert snapshot_tree(container / "package") == package
        assert snapshot_tree(base._records(common, victim)) == seen[0]
    assert snapshot_tree(durable) == outside


@pytest.mark.parametrize("invalid", [False, True])
@pytest.mark.parametrize("ending", ["acknowledged", "retired"])
def test_only_verified_resource_endings_exclude_a_dependency_from_containment(checkout, tmp_path, ending,
                                                                             invalid):
    common, work = base._common(checkout.repo), tmp_path.resolve()
    container, child = work / "container", work / "container/child"
    outer = api.create_directory(checkout.ws, HOLDER, path=str(container), actor="manager")["rid"]
    inner = api.create_directory(checkout.ws, PARTNER, path=str(child), actor="manager")["rid"]
    if ending == "acknowledged":
        child.rmdir()
        api.acknowledge(checkout.repo, inner, actor="manager")
        ended = base._records(common, inner) / "ACKNOWLEDGED.json"
    else:
        api.close(checkout.ws, PARTNER, actor="manager", abandon=True, reason="done")
        ended = base._records(common, inner) / "claims/0001.RETIRED.json"
    child.mkdir()
    _fill(child)
    if invalid:
        # Keep the digest and every other field: a matching binding alone cannot validate an unsupported record.
        value = support.read_json(ended)
        value["schema"] = "unsupported/1"
        ended.write_text(json.dumps(value) + "\n", encoding="utf-8")
    shown = api.show_resource(checkout.repo, inner)
    assert bool(shown["problems"]) == invalid
    assert shown["disposition"] == ("blocked" if invalid else ending)
    record, payload = snapshot_tree(base._records(common, inner)), snapshot_tree(child)
    plan = base._by_rid(api.close_plan(checkout.ws, HOLDER, abandon=True)["resources"])
    assert plan[outer]["disposition"] == ("blocked" if invalid else "remove")
    api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="done")
    assert container.exists() == invalid
    if invalid:
        assert snapshot_tree(child) == payload
    assert snapshot_tree(base._records(common, inner)) == record


# --- 11. a killed remover resumes its own partial removal (review finding R2) ------------------------------


class _KilledAfterFirstUnlink:
    """Stands in for ``os`` inside ``_removal`` in a child process: the first unlink happens, then the process dies."""

    def __getattr__(self, name):
        return getattr(os, name)

    def listdir(self, path):
        return sorted(os.listdir(path))

    def unlink(self, path, *, dir_fd=None):
        os.unlink(path, dir_fd=dir_fd)
        os._exit(73)


@pytest.mark.parametrize("added", [False, True])
@pytest.mark.parametrize("kind", ["directory", "worktree"])
def test_a_removal_killed_after_its_first_unlink_resumes_over_what_it_froze(checkout, tmp_path, kind, added):
    work = tmp_path.resolve()
    common = base._common(checkout.repo)
    target = work / "target"
    if kind == "directory":
        rid = api.create_directory(checkout.ws, HOLDER, path=str(target), actor="manager")["rid"]
        _fill(target)
        admin = None
    else:
        made = api.create_worktree(checkout.ws, HOLDER, path=str(target), actor="manager")
        rid, admin = base._rid(made, "worktree"), Path(made["identity"]["git_admin"])
    before = snapshot_tree(target)
    sentinel = work / "untouched.txt"
    sentinel.write_text("invariant\n", encoding="utf-8")
    arguments = dict(actor="manager", abandon=True, reason="resources done", request_key="killed-close")

    child = os.fork()
    if child == 0:  # pragma: no cover - the child process ends at the first unlink, or with 74 if it never comes
        try:
            _removal.os = _KilledAfterFirstUnlink()
            api.close(checkout.ws, HOLDER, **arguments)
        finally:
            os._exit(74)
    _, status = os.waitpid(child, 0)
    # Firing control: the process died right after one removal step, recording no failure of its own.
    assert os.waitstatus_to_exitcode(status) == 73
    remaining = snapshot_tree(target)
    assert len(remaining) == len(before) - 1 and all(before[path] == digest for path, digest in remaining.items())
    assert len(_attempts(common, rid)) == 1 and base._attempt_files(common, rid, failed=True) == []
    assert base._generations(common, rid) == {1: None}
    assert api.inspect_request(checkout.repo, "killed-close")["state"] == "partial"

    late = target / "added-after-the-kill.txt"
    if added:
        late.write_text("not in the frozen inventory\n", encoding="utf-8")
    resumed = api.close(checkout.ws, HOLDER, resume=True, **arguments)
    [outcome] = resumed["resources"]
    if added:
        # Changed property: an entry the claim never froze ends the claim and keeps everything left.
        assert outcome["outcome"] == "kept" and late.is_file()
        assert base._generations(common, rid) == {1: "RELEASED"}
        assert {path: digest for path, digest in snapshot_tree(target).items() if path != late.name} == remaining
    else:
        # The attempt record written before the first unlink makes the partial removal recognizably its own.
        assert outcome["outcome"] == "removed" and not target.exists()
        assert base._generations(common, rid) == {1: "RETIRED"}
        assert resumed["request"]["state"] == "completed"
        if admin is not None:
            assert not admin.exists() and str(target) not in base._worktrees(checkout.repo)
    # Invariance: nothing outside the frozen resource changed.
    assert sentinel.read_text(encoding="utf-8") == "invariant\n"


@pytest.mark.parametrize("interrupted", [False, True])
def test_a_retirement_interrupted_while_ending_a_disposed_dependency_finishes_that_claim(checkout, tmp_path,
                                                                                      monkeypatch, interrupted):
    work = tmp_path.resolve()
    common = base._common(checkout.repo)
    ident = checkout.meta["audit_id"]
    support.prepared_session(checkout)
    container, durable = work / "container", work / "durable"
    container_rid, export_rid, outside = _export_inside(checkout, ident, container, durable)
    arguments = dict(actor="manager", abandon=True, reason="done", dispose=[export_rid], request_key="dispose-close")
    real_end = holdings._end
    stopped: list[str] = []

    def stop_before_the_dependency_ends(claim, ending, value):
        if interrupted and not stopped and Path(claim["path"]).parent.parent.name == export_rid:
            stopped.append(claim["path"])
            raise KeyboardInterrupt("synthetic interruption after the dependency was claimed, before it ended")
        return real_end(claim, ending, value)

    with monkeypatch.context() as patch:
        patch.setattr(holdings, "_end", stop_before_the_dependency_ends)
        if interrupted:
            with pytest.raises(KeyboardInterrupt):
                api.close(checkout.ws, ident, **arguments)
        else:
            api.close(checkout.ws, ident, **arguments)
    if interrupted:
        # Firing control: the container is gone and the export holds an active claim its container made.
        assert stopped and not container.exists()
        assert base._generations(common, export_rid) == {1: None} and base._generations(common, container_rid) == {
            1: None}
        assert api.inspect_request(checkout.repo, "dispose-close")["state"] == "partial"
        resumed = api.close(checkout.ws, ident, resume=True, **arguments)
        assert resumed["request"]["state"] == "completed"
    # Measured: the resumed retirement ends that same claim instead of releasing the container's; the
    # uninterrupted close (control) ends in the same records.
    assert base._generations(common, container_rid) == {1: "RETIRED"}
    assert base._generations(common, export_rid) == {1: "RETIRED"}
    # Invariance: the export with a durable destination outside the container is untouched.
    assert snapshot_tree(durable) == outside
