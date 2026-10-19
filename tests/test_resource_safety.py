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
import os
from pathlib import Path
import shutil

import pytest

from stewart import _removal, api
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK
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
    """The closeout plan by resource, asserting the exit code it earns (1 while any resource stays blocked)."""
    plan = cli("--repo", repo, "--workspace", WS, "close", "--audit-id", ident, "--plan", allowed=(code,))["result"]
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
    return [name for name in base._claim_files(common, rid) if name.startswith("0001.ATTEMPT-")]


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
    # Invariance: no new generation; the claim and its attempt record are as they were.
    assert (base._records(common, rid) / "claims/0001.json").read_bytes() == claim_bytes
    assert _attempts(common, rid) == attempts


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
