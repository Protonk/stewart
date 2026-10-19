"""Recorded resources and their closeout through the installed wheel.

Managed creation records its start before any side effect and its outcome
after; enrollment tracks an external resource without ever granting removal.
Shared use delays a managed resource's retirement until its last use closes,
and a resource left behind is retired later by an explicit, gated resource
close. Every removal rests on one exclusively created claim, revalidated at
use. Manual retirement is acknowledged in its own record, never inferred.

Each measured guarantee has a firing control (the condition is shown to have
happened), a case differing only in the measured property, and an invariance
case. All repositories, homes and manager storage are disposable fixtures.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import threading
from types import SimpleNamespace

import pytest

from stewart import _util, api
import stewart._git as git_module
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, StewartError
from stewart._git import git_text
import stewart.holdings as holdings
from stewart.workspace import workspace
import stewart_support as support
from stewart_support import assignment_text, snapshot_tree

pytestmark = pytest.mark.system

WS = support.WS
OTHER = "audits/other"
IDENT = "one-question"
SECOND = "other-question"
THIRD = "third-question"
HOLDER = "holder-audit"
PARTNER = "partner-audit"


# --- helpers ---------------------------------------------------------------------------------------------


class Stewart:
    """One fresh isolated process per call from the installed wheel; returns its JSON envelope."""

    def __init__(self, run_cmd, cwd: Path):
        self.run_cmd, self.cwd = run_cmd, cwd

    def __call__(self, *argv, allowed=(EXIT_OK,)) -> dict:
        command = [sys.executable, "-I", "-B", "-m", "stewart", "--json", *map(str, argv)]
        result = self.run_cmd(command, cwd=self.cwd)
        assert result.returncode in allowed, f"{argv}: {result.returncode}\n{result.stdout}\n{result.stderr}"
        envelope = json.loads(result.stdout)
        assert envelope["schema"] == "stewart.result/3" and envelope["exit_code"] == result.returncode
        return envelope


def _cli(run_cmd, base: Path) -> Stewart:
    """Commands run from an unrelated directory: nothing may depend on the current directory."""
    elsewhere = base / "elsewhere"
    elsewhere.mkdir(exist_ok=True)
    return Stewart(run_cmd, elsewhere)


def _common(repo: Path) -> Path:
    return Path(git_text(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))


def _records(common: Path, rid: str | None = None) -> Path:
    root = common / "stewart/resources"
    return root if rid is None else root / rid


def _rids(common: Path) -> list[str]:
    root = _records(common)
    return sorted(os.listdir(root)) if root.is_dir() else []


def _claim_files(common: Path, rid: str) -> list[str]:
    """Claim generations and their endings, without staging leftovers (none may remain)."""
    claims = _records(common, rid) / "claims"
    return sorted(os.listdir(claims)) if claims.is_dir() else []


def _generations(common: Path, rid: str) -> dict[int, str | None]:
    """Each claim generation and how it ended (RETIRED, RELEASED, or None while active)."""
    files = _claim_files(common, rid)
    found = {}
    for name in files:
        number, _, rest = name.partition(".")
        if rest == "json":
            ended = [ending for ending in ("RETIRED", "RELEASED") if f"{number}.{ending}.json" in files]
            found[int(number)] = ended[0] if ended else None
    return found


def _rid(made: dict, kind: str) -> str:
    return next(item["rid"] for item in made["resources"] if item["kind"] == kind)


def _by_rid(items: list[dict]) -> dict[str, dict]:
    return {item["rid"]: item for item in items}


def _ref(repo: Path, ref: str) -> str | None:
    found = git_text(repo, "for-each-ref", "--format=%(objectname)", ref)
    return found or None


def _worktrees(repo: Path) -> dict[str, dict]:
    """Git's own registration of every worktree, keyed by path."""
    found = {}
    for block in git_text(repo, "worktree", "list", "--porcelain").split("\n\n"):
        fields = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            fields[key] = value
        if "worktree" in fields:
            found[fields["worktree"]] = fields
    return found


def _reason(callable_, *args, **kwargs) -> StewartError:
    with pytest.raises(StewartError) as refused:
        callable_(*args, **kwargs)
    return refused.value


def _two_workspaces(tmp_path: Path, run_cmd) -> SimpleNamespace:
    """The support checkout plus a second workspace, both committed in the target."""
    checkout = support.make_checkout(tmp_path, run_cmd)
    folder = checkout.repo / OTHER
    folder.mkdir(parents=True)
    (folder / "AUDITOR.md").write_text("Auditor instructions\n", encoding="utf-8")
    (folder / "MAINTAINER.md").write_text("Maintainer instructions\n", encoding="utf-8")
    (folder / "PROMPT.md").write_text("**UNASSIGNED**\n", encoding="utf-8")
    checkout.git("add", "--", OTHER)
    checkout.git("commit", "-qm", "Second workspace")
    checkout.base = checkout.git("rev-parse", "HEAD")
    return checkout


def _assign(checkout, rel: str, ident: str, target: str) -> str:
    """Commit one workspace's assigned prompt alone; return the prompt commit."""
    ws = workspace(checkout.repo, rel)
    meta = {"audit_id": ident, "target_commit": target, "report_path": ws.report_path(ident),
            "input_files": ["input.txt"], "external_sources": []}
    (checkout.repo / rel / "PROMPT.md").write_text(assignment_text(meta), encoding="utf-8")
    checkout.git("add", "--", f"{rel}/PROMPT.md")
    checkout.git("commit", "-qm", f"Assign {ident}")
    return checkout.git("rev-parse", "HEAD")


def _abandon(cli: Stewart, repo: Path, rel: str, ident: str, *extra, allowed=(EXIT_OK,)) -> dict:
    return cli("--repo", repo, "--workspace", rel, "close", "--audit-id", ident, "--actor", "manager", "--abandon",
               "--reason", f"{ident} is finished with its resources", *extra, allowed=allowed)["result"]


def _plan(cli: Stewart, repo: Path, rel: str, ident: str, *extra) -> dict[str, dict]:
    plan = cli("--repo", repo, "--workspace", rel, "close", "--audit-id", ident, "--plan", *extra)["result"]
    assert plan["schema"] == "stewart.closeout/1"
    return _by_rid(plan["resources"])


def _refused(cli: Stewart, *argv) -> dict:
    return cli(*argv, allowed=(EXIT_REFUSED,))["error"]


# --- 1. creation boundary and placement ------------------------------------------------------------------


@pytest.mark.parametrize("moment", ["before_add", "after_add"])
def test_interrupted_creation_keeps_its_start_record_and_grants_no_removal(checkout, tmp_path, run_cmd, monkeypatch,
                                                                         moment):
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    common = _common(checkout.repo)
    complete, interrupted = base / "complete-tree", base / "interrupted-tree"

    # Differing only in the interruption: an uninterrupted creation for the same audit.
    made = api.create_worktree(checkout.ws, HOLDER, path=str(complete), branch="audit/complete", actor="manager")
    complete_rid, complete_branch = _rid(made, "worktree"), _rid(made, "branch")
    assert sorted(os.listdir(_records(common, complete_rid))) == ["CREATE.json", "CREATED.json"]
    # A managed worktree is locked with its resource ID and marked in its own Git administration.
    registered = _worktrees(checkout.repo)[str(complete)]
    assert registered["locked"].startswith(f"stewart managed worktree {complete_rid}")
    marker = support.read_json(Path(made["identity"]["git_admin"]) / "stewart-resource.json")
    assert marker["rid"] == complete_rid
    assert Path(made["identity"]["git_admin"]).parent == common / "worktrees"

    real = git_module.git
    seen: dict = {}

    def interrupt(repo, *args, **kwargs):
        if args[:2] == ("worktree", "add") and str(interrupted) in args:
            seen["records"] = {rid: sorted(os.listdir(_records(common, rid))) for rid in _rids(common)}
            if moment == "after_add":
                real(repo, *args, **kwargs)
            raise KeyboardInterrupt("synthetic interruption of a managed creation")
        return real(repo, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(git_module, "git", interrupt)
        with pytest.raises(KeyboardInterrupt):
            api.create_worktree(checkout.ws, HOLDER, path=str(interrupted), branch="audit/interrupted",
                                actor="manager")
    # Firing control: both start records preceded the side effect, and neither has an outcome now.
    started = sorted(set(seen["records"]) - {complete_rid, complete_branch})
    assert len(started) == 2 and all(seen["records"][rid] == ["CREATE.json"] for rid in started)
    assert all(sorted(os.listdir(_records(common, rid))) == ["CREATE.json"] for rid in started)
    kinds = {support.read_json(_records(common, rid) / "CREATE.json")["kind"]: rid for rid in started}
    interrupted_rid, interrupted_branch = kinds["worktree"], kinds["branch"]
    if moment == "after_add":
        assert interrupted.is_dir() and str(interrupted) in _worktrees(checkout.repo)
        assert _ref(checkout.repo, "refs/heads/audit/interrupted"), "control: Git created the branch"
    else:
        assert not interrupted.exists() and not _ref(checkout.repo, "refs/heads/audit/interrupted")
        # Something found at the path later is not shown to be the operation's creation.
        interrupted.mkdir()
    (interrupted / "found-later.txt").write_text("found at the recorded path\n", encoding="utf-8")
    found = snapshot_tree(interrupted)

    for rid in (interrupted_rid, interrupted_branch):
        shown = cli("--repo", checkout.repo, "resource", "show", "--resource", rid, allowed=(EXIT_ATTENTION,))["result"]
        assert shown["creation"] == "unresolved" and shown["disposition"] == "blocked"
        assert any("creation was interrupted" in reason for reason in shown["reasons"])

    closed = _abandon(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_ATTENTION,))
    closeout = _by_rid(closed["closeout"])
    assert closeout[interrupted_rid]["disposition"] == closeout[interrupted_branch]["disposition"] == "blocked"
    assert {item["rid"]: item["outcome"] for item in closed["resources"]} == {
        complete_rid: "removed", complete_branch: "removed"}, "control: the completed creation retires"
    assert not complete.exists() and not _ref(checkout.repo, "refs/heads/audit/complete")
    records = {rid: snapshot_tree(_records(common, rid)) for rid in started}
    for _ in range(2):  # Invariance: every later close refuses identically and writes nothing.
        refused = _refused(cli, "--repo", checkout.repo, "close", "--resource", interrupted_rid, "--actor", "manager")
        assert refused["reason"] == "resource_blocked" and "creation was interrupted" in refused["message"]
    assert snapshot_tree(interrupted) == found
    assert {rid: snapshot_tree(_records(common, rid)) for rid in started} == records
    assert _claim_files(common, interrupted_rid) == [] and _claim_files(common, interrupted_branch) == []
    if moment == "after_add":
        assert _ref(checkout.repo, "refs/heads/audit/interrupted"), "the interrupted branch is never deleted"


@pytest.mark.parametrize("kind", ["worktree", "directory"])
def test_managed_placement_stays_outside_checkout_homes_and_git_storage(checkout, tmp_path, kind):
    base = tmp_path.resolve()
    common = _common(checkout.repo)
    create = (lambda path: api.create_worktree(checkout.ws, HOLDER, path=str(path), actor="manager")) \
        if kind == "worktree" else (lambda path: api.create_directory(checkout.ws, HOLDER, path=str(path),
                                                                     actor="manager"))
    home = Path.home()
    refused_at = {
        "inside the checkout home": home / ".local/state/stewart/checkouts/managed",
        "around the checkout home": home / ".local",
        "inside the Git common directory": common / "managed",
        "inside the manager home": Path(os.environ["STEWART_MANAGER_HOME"]) / "managed",
    }
    for what, path in refused_at.items():
        assert not path.exists(), what
        error = _reason(create, path)
        assert error.reason == "resource_location", what
        assert not path.exists(), what
    assert _rids(common) == [], "a refused placement records no resource"
    # Control, differing only in the location: an ordinary path outside every private root is accepted.
    accepted = base / f"managed-{kind}"
    made = create(accepted)
    rid = _rid(made, "worktree") if kind == "worktree" else made["rid"]
    assert accepted.is_dir() and _rids(common) == [rid]
    # Invariance: a second creation at an existing path is refused; nothing is adopted.
    assert _reason(create, accepted).reason == "destination_exists" and _rids(common) == [rid]


# --- 2. enrollment --------------------------------------------------------------------------------------


def test_enrollment_explains_external_resources_and_never_grants_removal(checkout, tmp_path, run_cmd):
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    common = _common(checkout.repo)
    external_dir, external_tree, managed = base / "external-dir", base / "external-tree", base / "managed-dir"
    external_dir.mkdir()
    (external_dir / "kept.txt").write_text("created outside Stewart\n", encoding="utf-8")
    checkout.git("worktree", "add", "-q", "--detach", str(external_tree), "HEAD")
    enrolled_dir = api.enroll(checkout.ws, HOLDER, kind="directory", path=str(external_dir), actor="manager")["rid"]
    enrolled_tree = api.enroll(checkout.ws, HOLDER, kind="worktree", path=str(external_tree), actor="manager")["rid"]
    managed_rid = api.create_directory(checkout.ws, HOLDER, path=str(managed), actor="manager")["rid"]
    trees = {path: snapshot_tree(path) for path in (external_dir, external_tree)}
    enrolled_bytes = {rid: (_records(common, rid) / "ENROLLED.json").read_bytes() for rid in (enrolled_dir, enrolled_tree)}

    plan = _plan(cli, checkout.repo, WS, HOLDER)
    # Control, differing only in origin: the managed directory of the same audit is proposed for removal.
    assert plan[managed_rid]["disposition"] == "remove"
    for rid in (enrolled_dir, enrolled_tree):
        assert plan[rid]["disposition"] == "manual" and plan[rid]["origin"] == "enrolled"
        assert any("retired by hand" in reason for reason in plan[rid]["reasons"])
        refused = _refused(cli, "--repo", checkout.repo, "close", "--resource", rid, "--actor", "manager")
        assert refused["reason"] == "resource_not_managed"

    closed = _abandon(cli, checkout.repo, WS, HOLDER)
    assert {item["rid"]: item["outcome"] for item in closed["resources"]} == {managed_rid: "removed"}
    assert not managed.exists()
    closeout = _by_rid(closed["closeout"])
    assert closeout[enrolled_dir]["disposition"] == closeout[enrolled_tree]["disposition"] == "manual"
    # Invariance: with no live use left, an enrolled resource is still never removal-eligible.
    for rid in (enrolled_dir, enrolled_tree):
        refused = _refused(cli, "--repo", checkout.repo, "close", "--resource", rid, "--actor", "manager")
        assert refused["reason"] == "resource_not_managed"
        assert _claim_files(common, rid) == []
        assert (_records(common, rid) / "ENROLLED.json").read_bytes() == enrolled_bytes[rid]
    assert {path: snapshot_tree(path) for path in trees} == trees
    assert str(external_tree) in _worktrees(checkout.repo)


# --- 3. shared use and explicit retirement ----------------------------------------------------------------


@pytest.mark.heavy
def test_shared_worktree_and_branch_retire_only_when_their_last_use_closes(tmp_path, run_cmd):
    checkout = _two_workspaces(tmp_path, run_cmd)
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    common = _common(checkout.repo)
    first_prompt = _assign(checkout, WS, IDENT, checkout.base)
    second_prompt = _assign(checkout, OTHER, SECOND, first_prompt)
    tree, scratch = base / "manager-tree", base / "scratch-dir"
    made = api.create_worktree(checkout.ws, IDENT, path=str(tree), branch="audit/shared", actor="manager")
    tree_rid, branch_rid = _rid(made, "worktree"), _rid(made, "branch")
    scratch_rid = api.create_directory(checkout.ws, IDENT, path=str(scratch), actor="manager")["rid"]
    # A third audit uses the worktree by explicit association, with no session at all.
    api.associate(checkout.ws, THIRD, rid=tree_rid, actor="manager")
    first = api.prepare(workspace(tree, WS), first_prompt)
    second = api.prepare(workspace(tree, OTHER), second_prompt)
    for prepared in (first, second):
        assert support.read_json(Path(prepared["session"]) / "session.json")["repo"] == str(tree)
    main_tip = _ref(checkout.repo, "refs/heads/main")

    plan = _plan(cli, tree, WS, IDENT)
    assert plan[tree_rid]["disposition"] == plan[branch_rid]["disposition"] == "shared"
    users = " ".join(plan[tree_rid]["reasons"])
    assert f"{OTHER}:{SECOND}" in users and f"{WS}:{THIRD}" in users and f"{WS}:{IDENT} " not in users
    assert plan[scratch_rid]["disposition"] == "remove", "control: a single-audit directory is proposed"

    closed = _abandon(cli, tree, WS, IDENT, "--discard-uncollected")
    closeout = _by_rid(closed["closeout"])
    assert closeout[tree_rid]["disposition"] == closeout[branch_rid]["disposition"] == "shared"
    assert closeout[scratch_rid]["disposition"] == "claimed by this close"
    assert {item["rid"]: item["outcome"] for item in closed["resources"]} == {scratch_rid: "removed"}
    assert not scratch.exists() and tree.is_dir() and _ref(checkout.repo, "refs/heads/audit/shared")
    assert _claim_files(common, tree_rid) == [] and _claim_files(common, branch_rid) == []

    # The second session closes; the still-live association keeps both in shared use.
    closed = _abandon(cli, tree, OTHER, SECOND, "--discard-uncollected")
    closeout = _by_rid(closed["closeout"])
    assert closeout[tree_rid]["disposition"] == closeout[branch_rid]["disposition"] == "shared"
    users = " ".join(closeout[tree_rid]["reasons"])
    assert f"{WS}:{THIRD}" in users and SECOND not in users
    assert closed["resources"] == [] and tree.is_dir() and _ref(checkout.repo, "refs/heads/audit/shared")

    # The last use ends; this close runs against the very worktree it retires.
    history = snapshot_tree(common / "stewart/closed")
    last = _abandon(cli, tree, WS, THIRD)
    assert {item["rid"]: item["outcome"] for item in last["resources"]} == {tree_rid: "removed",
                                                                           branch_rid: "removed"}
    assert not tree.exists() and str(tree) not in _worktrees(checkout.repo)
    assert not Path(made["identity"]["git_admin"]).exists()
    assert not _ref(checkout.repo, "refs/heads/audit/shared")
    assert _ref(checkout.repo, "refs/heads/main") == main_tip
    assert _claim_files(common, tree_rid) == ["0001.RETIRED.json", "0001.json"]
    after = snapshot_tree(common / "stewart/closed")
    assert {path: after.get(path) for path in history} == history, "earlier closing records are unchanged"


@pytest.mark.heavy
def test_resources_left_blocked_at_the_last_close_retire_once_the_blocker_clears(tmp_path, run_cmd):
    checkout = _two_workspaces(tmp_path, run_cmd)
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    common = _common(checkout.repo)
    first_prompt = _assign(checkout, WS, IDENT, checkout.base)
    second_prompt = _assign(checkout, OTHER, SECOND, first_prompt)
    tree = base / "manager-tree"
    made = api.create_worktree(checkout.ws, IDENT, path=str(tree), branch="audit/shared", actor="manager")
    tree_rid, branch_rid = _rid(made, "worktree"), _rid(made, "branch")
    api.prepare(workspace(tree, WS), first_prompt)
    api.prepare(workspace(tree, OTHER), second_prompt)
    closed = _abandon(cli, tree, WS, IDENT, "--discard-uncollected")
    assert _by_rid(closed["closeout"])[tree_rid]["disposition"] == "shared"

    # Work left behind: an untracked file, an ignored file and an unmerged commit on the shared branch.
    (tree / "untracked-note.txt").write_text("manager note\n", encoding="utf-8")
    (tree / "ignored").mkdir()
    (tree / "ignored/cache.txt").write_text("ignored, but still work\n", encoding="utf-8")
    (tree / "work.txt").write_text("unmerged work\n", encoding="utf-8")
    git_text(tree, "add", "--", "work.txt")
    git_text(tree, "commit", "-qm", "Unmerged work on the shared branch")
    assert "!! ignored/" in git_text(tree, "status", "--porcelain", "--ignored"), "control: Git ignores the file"

    last = _abandon(cli, tree, OTHER, SECOND, "--discard-uncollected", allowed=(EXIT_ATTENTION,))
    closeout = _by_rid(last["closeout"])
    assert closeout[tree_rid]["disposition"] == "blocked" and closeout[branch_rid]["disposition"] == "blocked"
    tree_reasons, branch_reasons = " ".join(closeout[tree_rid]["reasons"]), " ".join(closeout[branch_rid]["reasons"])
    assert "untracked-note.txt" in tree_reasons and "ignored/" in tree_reasons
    assert "unmerged work" in branch_reasons
    assert last["resources"] == [] and _claim_files(common, tree_rid) == [] == _claim_files(common, branch_rid)
    assert (tree / "ignored/cache.txt").is_file(), "ignored paths are never cleaned"
    history = snapshot_tree(common / "stewart/closed")
    resource_close = ("--repo", checkout.repo, "close", "--actor", "manager", "--resource")

    # Each blocker is cleared alone; only the property cleared changes the outcome.
    (tree / "untracked-note.txt").unlink()
    refused = _refused(cli, *resource_close, tree_rid)
    assert refused["reason"] == "resource_blocked"
    assert "ignored/" in refused["message"] and "untracked-note.txt" not in refused["message"]
    shutil.rmtree(tree / "ignored")
    retired = cli(*resource_close, tree_rid)["result"]
    assert [(item["rid"], item["outcome"]) for item in retired["results"]] == [(tree_rid, "removed")]
    assert not tree.exists() and str(tree) not in _worktrees(checkout.repo)
    refused = _refused(cli, *resource_close, branch_rid)
    assert refused["reason"] == "resource_blocked" and "unmerged work" in refused["message"]
    assert "checked out by" not in refused["message"]
    checkout.git("merge", "-q", "--ff-only", "audit/shared")
    retired = cli(*resource_close, branch_rid)["result"]
    assert [(item["rid"], item["outcome"]) for item in retired["results"]] == [(branch_rid, "removed")]
    assert not _ref(checkout.repo, "refs/heads/audit/shared") and (checkout.repo / "work.txt").is_file()
    for rid in (tree_rid, branch_rid):
        assert _claim_files(common, rid) == ["0001.RETIRED.json", "0001.json"]
    assert snapshot_tree(common / "stewart/closed") == history, "no closed audit's records changed"


def test_a_branch_checked_out_by_a_blocked_worktree_is_not_claimed(checkout, tmp_path, run_cmd):
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    common = _common(checkout.repo)
    tree = base / "manager-tree"
    made = api.create_worktree(checkout.ws, HOLDER, path=str(tree), branch="audit/held", actor="manager")
    tree_rid, branch_rid = _rid(made, "worktree"), _rid(made, "branch")
    (tree / "ignored").mkdir()
    (tree / "ignored/cache.txt").write_text("ignored work\n", encoding="utf-8")
    assert _worktrees(checkout.repo)[str(tree)]["branch"] == "refs/heads/audit/held", "control: it checks out the branch"

    plan = _plan(cli, checkout.repo, WS, HOLDER)
    assert plan[tree_rid]["disposition"] == "blocked" and "ignored/" in " ".join(plan[tree_rid]["reasons"])
    closed = _abandon(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_ATTENTION,))
    closeout = _by_rid(closed["closeout"])
    assert closeout[tree_rid]["disposition"] == "blocked"
    # The worktree remains, so the branch it checks out does not pass eligibility and is not claimed.
    assert closeout[branch_rid]["disposition"] == "blocked", closeout[branch_rid]
    assert "checked out by" in " ".join(closeout[branch_rid]["reasons"])
    assert _claim_files(common, branch_rid) == []
    assert tree.is_dir() and _ref(checkout.repo, "refs/heads/audit/held")
    # Clearing the blocker lets both retire together.
    shutil.rmtree(tree / "ignored")
    retired = cli("--repo", checkout.repo, "close", "--actor", "manager", "--resource", tree_rid, "--resource",
                  branch_rid)["result"]
    assert {item["rid"]: item["outcome"] for item in retired["results"]} == {tree_rid: "removed",
                                                                            branch_rid: "removed"}


# --- 4. change between the claim and its use --------------------------------------------------------------


def test_a_change_after_the_claim_releases_it_and_a_new_generation_retires_later(checkout, tmp_path, run_cmd,
                                                                                monkeypatch):
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    common = _common(checkout.repo)
    tree, scratch = base / "managed-tree", base / "scratch-dir"
    tree_rid = _rid(api.create_worktree(checkout.ws, HOLDER, path=str(tree), actor="manager"), "worktree")
    scratch_rid = api.create_directory(checkout.ws, HOLDER, path=str(scratch), actor="manager")["rid"]
    real = holdings._revalidate
    fired = []

    def change_then_revalidate(common_, view, claim, index):
        if view["rid"] == tree_rid:
            assert Path(claim["path"]).is_file(), "the claim exists before the change"
            (tree / "late.txt").write_text("written after the claim was frozen\n", encoding="utf-8")
            fired.append(claim["path"])
        return real(common_, view, claim, index)

    with monkeypatch.context() as patch:
        patch.setattr(holdings, "_revalidate", change_then_revalidate)
        closed = api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="resources done")
    assert len(fired) == 1, "firing control: the contents changed between the claim and its use"
    outcomes = _by_rid(closed["resources"])
    assert outcomes[tree_rid]["outcome"] == "kept"
    assert any("contents changed" in reason for reason in outcomes[tree_rid]["reasons"])
    # Differing only in the change: the unchanged directory claimed by the same close retires.
    assert outcomes[scratch_rid]["outcome"] == "removed" and not scratch.exists()
    assert closed["exit_code"] == EXIT_ATTENTION
    assert _claim_files(common, tree_rid) == ["0001.RELEASED.json", "0001.json"]
    released = support.read_json(_records(common, tree_rid) / "claims/0001.RELEASED.json")
    assert released["ending"] == "released" and any("contents changed" in item for item in released["observation"])
    assert (tree / "late.txt").read_text() == "written after the claim was frozen\n"

    shown = cli("--repo", checkout.repo, "resource", "show", "--resource", tree_rid)["result"]
    assert shown["disposition"] == "blocked" and "late.txt" in " ".join(shown["reasons"])
    refused = _refused(cli, "--repo", checkout.repo, "close", "--resource", tree_rid, "--actor", "manager")
    assert refused["reason"] == "resource_blocked" and "late.txt" in refused["message"]
    assert _claim_files(common, tree_rid) == ["0001.RELEASED.json", "0001.json"], "a refusal claims nothing"
    (tree / "late.txt").unlink()
    retired = cli("--repo", checkout.repo, "close", "--resource", tree_rid, "--actor", "manager")["result"]
    assert [(item["rid"], item["outcome"], item["resumed"]) for item in retired["results"]] == [
        (tree_rid, "removed", False)]
    assert not tree.exists()
    # Invariance: the released generation is kept as it was; the retirement is a new generation.
    assert _claim_files(common, tree_rid) == ["0001.RELEASED.json", "0001.json", "0002.RETIRED.json", "0002.json"]
    assert support.read_json(_records(common, tree_rid) / "claims/0001.RELEASED.json") == released


# --- 5. controlled interleaving ---------------------------------------------------------------------------


class Interleaving:
    """Hold two operations at the claim seam: both passed eligibility before either claims.

    ``simultaneous`` releases both claimants together; ``after_retirement``
    lets the second claimant proceed only once the first operation has fully
    returned, so the second claims after the resource was already retired.
    """

    def __init__(self, mode: str):
        self.mode = mode
        self.closing = threading.Barrier(2, timeout=60)
        self.claiming = threading.Barrier(2, timeout=60)
        self.first_done = threading.Event()
        self.entered: list[tuple[str, str]] = []

    def gate_claim_for_close(self, real):
        def gated(*args, **kwargs):
            self.closing.wait()  # both closing records exist before either evaluates
            return real(*args, **kwargs)
        return gated

    def gate_claim(self, real):
        def gated(common, view, evaluation, claimant):
            self.entered.append((threading.current_thread().name, evaluation.get("disposition")))
            self.claiming.wait()
            if self.mode == "after_retirement" and threading.current_thread().name == "second":
                assert self.first_done.wait(120)
            return real(common, view, evaluation, claimant)
        return gated

    def run(self, first, second, *, allow: tuple = ()) -> tuple:
        """Run both on their own threads; an exception is a failure unless it is one of ``allow``."""
        box: dict = {}

        def work(name, call):
            try:
                box[name] = call()
            except BaseException as exc:  # noqa: BLE001 - reported on the test thread
                box[name] = exc
            finally:
                if name == "first":
                    self.first_done.set()

        threads = [threading.Thread(target=work, args=(name, call), name=name, daemon=True)
                   for name, call in (("first", first), ("second", second))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(180)
        assert not any(thread.is_alive() for thread in threads), "an interleaved operation did not finish"
        for name in ("first", "second"):
            if isinstance(box[name], BaseException) and not isinstance(box[name], allow):
                raise AssertionError(f"{name} raised {box[name]!r}") from box[name]
        return box["first"], box["second"]


@pytest.mark.parametrize("mode", ["sequential", "simultaneous", "after_retirement"])
def test_two_final_audit_closes_claim_a_shared_resource_once(checkout, tmp_path, monkeypatch, mode):
    common = _common(checkout.repo)
    shared = tmp_path.resolve() / "shared-dir"
    rid = api.create_directory(checkout.ws, HOLDER, path=str(shared), actor="manager")["rid"]
    api.associate(checkout.ws, PARTNER, rid=rid, actor="manager")
    calls = [lambda ident=ident: api.close(checkout.ws, ident, actor="manager", abandon=True,
                                           reason=f"{ident} is finished") for ident in (HOLDER, PARTNER)]
    claims = []
    real_claim = holdings._claim

    def counted(common_, view, evaluation, claimant):
        claims.append(evaluation.get("disposition"))
        return real_claim(common_, view, evaluation, claimant)

    if mode == "sequential":
        # Differing only in the interleaving: the first close sees the partner still using the resource.
        monkeypatch.setattr(holdings, "_claim", counted)
        first, second = calls[0](), calls[1]()
        assert _by_rid(first["closeout"])[rid]["disposition"] == "shared" and claims == ["remove"]
        assert _by_rid(second["closeout"])[rid]["disposition"] == "claimed by this close"
        winners, losers = [second], [first]
    else:
        plan = Interleaving(mode)
        monkeypatch.setattr(holdings, "claim_for_close", plan.gate_claim_for_close(holdings.claim_for_close))
        monkeypatch.setattr(holdings, "_claim", plan.gate_claim(real_claim))
        first, second = plan.run(*calls)
        # Firing control: both closes passed eligibility and reached the claim before either claimed.
        assert sorted(plan.entered) == [("first", "remove"), ("second", "remove")]
        dispositions = [_by_rid(item["closeout"])[rid]["disposition"] for item in (first, second)]
        # Exactly one inventory claims it; the other reports it as claimed (or retired) elsewhere.
        assert dispositions.count("claimed by this close") == 1, dispositions
        winners = [item for item in (first, second) if _by_rid(item["closeout"])[rid]["disposition"]
                   == "claimed by this close"]
        losers = [item for item in (first, second) if item not in winners]
        assert _by_rid(losers[0]["closeout"])[rid]["disposition"] in ("claimed", "retired"), dispositions
    assert [item["outcome"] for item in winners[0]["resources"]] == ["removed"]
    assert losers[0]["resources"] == [] and losers[0]["closed"] is not None
    # Invariance: whatever the interleaving, one claim generation retired the resource once.
    assert _claim_files(common, rid) == ["0001.RETIRED.json", "0001.json"]
    assert not shared.exists()
    assert api.show_resource(checkout.repo, rid)["disposition"] == "retired"


@pytest.mark.parametrize("mode", ["sequential", "simultaneous", "after_retirement"])
def test_two_resource_closes_claim_a_left_behind_resource_once(checkout, tmp_path, monkeypatch, mode):
    common = _common(checkout.repo)
    tree = tmp_path.resolve() / "left-tree"
    rid = _rid(api.create_worktree(checkout.ws, HOLDER, path=str(tree), actor="manager"), "worktree")
    (tree / "note.txt").write_text("left at the audit close\n", encoding="utf-8")
    closed = api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="leave the worktree behind")
    assert _by_rid(closed["closeout"])[rid]["disposition"] == "blocked", "control: the audit close left it behind"
    (tree / "note.txt").unlink()
    calls = [lambda actor=actor: api.close_resources(checkout.repo, [rid], actor=actor)
             for actor in ("manager-one", "manager-two")]
    if mode == "sequential":
        first = calls[0]()
        refused = _reason(calls[1])
        assert refused.reason == "resource_retired"
        winner = first
    else:
        plan = Interleaving(mode)
        monkeypatch.setattr(holdings, "_claim", plan.gate_claim(holdings._claim))
        first, second = plan.run(*calls, allow=(StewartError,))
        assert sorted(plan.entered) == [("first", "remove"), ("second", "remove")]
        winners = [item for item in (first, second) if isinstance(item, dict)
                   and item["results"][0]["outcome"] == "removed"]
        assert len(winners) == 1, (first, second)
        winner = winners[0]
        loser = second if first is winner else first
        # The other reports it as claimed elsewhere: a kept result, or a refusal with a stable reason.
        if isinstance(loser, StewartError):
            assert loser.reason in ("resource_retired", "resource_claimed"), loser.to_json()
        else:
            assert loser["results"][0]["outcome"] == "kept" and loser["exit_code"] == EXIT_ATTENTION
            assert "claimed" in " ".join(loser["results"][0]["reasons"])
    assert winner["exit_code"] == EXIT_OK and winner["results"][0]["rid"] == rid
    assert _claim_files(common, rid) == ["0001.RETIRED.json", "0001.json"]
    assert not tree.exists() and str(tree) not in _worktrees(checkout.repo)


# --- 6. manual retirement acknowledgment -------------------------------------------------------------------


@pytest.mark.heavy
def test_manual_retirement_is_acknowledged_in_its_own_record(checkout, tmp_path, run_cmd):
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    common = _common(checkout.repo)
    acknowledged_dir, unacknowledged_dir, tree = base / "external-one", base / "external-two", base / "managed-tree"
    for folder in (acknowledged_dir, unacknowledged_dir):
        folder.mkdir()
        (folder / "kept.txt").write_text("external\n", encoding="utf-8")
    enrolled = api.enroll(checkout.ws, HOLDER, kind="directory", path=str(acknowledged_dir), actor="manager")["rid"]
    unacknowledged = api.enroll(checkout.ws, HOLDER, kind="directory", path=str(unacknowledged_dir),
                                actor="manager")["rid"]
    tree_rid = _rid(api.create_worktree(checkout.ws, HOLDER, path=str(tree), actor="manager"), "worktree")
    acknowledge = ("--repo", checkout.repo, "resource", "acknowledge", "--actor", "manager", "--resource")
    show = ("--repo", checkout.repo, "resource", "show", "--resource")
    records = snapshot_tree(_records(common))
    enrolled_bytes = (_records(common, enrolled) / "ENROLLED.json").read_bytes()

    for rid in (enrolled, tree_rid):  # Present resources cannot be acknowledged as retired.
        assert _refused(cli, *acknowledge, rid)["reason"] == "resource_present"
    assert snapshot_tree(_records(common)) == records, "a refused acknowledgment writes nothing"

    shutil.rmtree(acknowledged_dir)
    shutil.rmtree(unacknowledged_dir)
    shutil.rmtree(tree)
    for rid in (enrolled, unacknowledged):
        missing = cli(*show, rid, allowed=(EXIT_ATTENTION,))["result"]
        assert missing["disposition"] == "missing" and missing["observation"]["state"] == "absent"
        assert missing["acknowledged"] is None
    # A worktree removed by hand while Git still registers it is not yet absent.
    lingering = cli(*show, tree_rid, allowed=(EXIT_ATTENTION,))["result"]
    assert lingering["disposition"] == "missing" and lingering["observation"]["state"] == "registration_remains"
    assert any("Git still registers it" in reason for reason in lingering["reasons"])
    assert _refused(cli, *acknowledge, tree_rid)["reason"] == "resource_present"
    checkout.git("worktree", "unlock", str(tree))
    checkout.git("worktree", "prune")
    assert cli(*show, tree_rid, allowed=(EXIT_ATTENTION,))["result"]["observation"]["state"] == "absent"

    for rid in (enrolled, tree_rid):
        cli(*acknowledge, rid, "--note", "removed by hand after review")
    view = cli(*show, enrolled)["result"]
    assert view["disposition"] == "acknowledged" and view["exit_code"] == EXIT_OK
    assert view["acknowledged"]["observed_at_acknowledgment"]["state"] == "absent"
    assert view["acknowledged"]["acknowledged"] == {"actor": "manager", "note": "removed by hand after review",
                                                   "claim": "retired outside Stewart"}
    assert view["acknowledged"]["observed_now"]["state"] == "absent" and view["acknowledged"]["note"] is None
    record = support.read_json(_records(common, enrolled) / "ACKNOWLEDGED.json")
    assert record["observed"]["state"] == "absent" and record["acknowledged"]["actor"] == "manager"
    assert "observed" not in record["acknowledged"] and "actor" not in record["observed"]
    # The acknowledgment binds the enrollment record, which is never edited.
    assert (_records(common, enrolled) / "ENROLLED.json").read_bytes() == enrolled_bytes
    assert record["resource_record_sha256"] == _util.sha256_bytes(enrolled_bytes)
    assert cli(*show, tree_rid)["result"]["disposition"] == "acknowledged"
    # Invariance: the never-acknowledged absence keeps its missing diagnostic.
    still = cli(*show, unacknowledged, allowed=(EXIT_ATTENTION,))["result"]
    assert still["disposition"] == "missing" and still["acknowledged"] is None
    assert any("acknowledge" in reason for reason in still["reasons"])

    # Something new at the acknowledged location is a new observation, not the retired resource.
    acknowledged_dir.mkdir()
    (acknowledged_dir / "new.txt").write_text("created after the acknowledgment\n", encoding="utf-8")
    view = cli(*show, enrolled)["result"]
    assert view["disposition"] == "acknowledged"
    assert view["acknowledged"]["observed_at_acknowledgment"]["state"] == "absent"
    # Reported as present or replaced (inode reuse decides which); either way it is observed anew.
    assert view["acknowledged"]["observed_now"]["state"] in ("present", "replaced")
    assert "new observation" in view["acknowledged"]["note"]
    # The acknowledgment grants nothing over the new entry, and is never repeated.
    assert _refused(cli, "--repo", checkout.repo, "close", "--resource", enrolled, "--actor",
                    "manager")["reason"] == "resource_retired"
    assert _refused(cli, *acknowledge, enrolled)["reason"] == "destination_exists"
    assert (acknowledged_dir / "new.txt").read_text() == "created after the acknowledgment\n"


# --- 7. exports inside a retiring worktree ------------------------------------------------------------------


@pytest.mark.heavy
def test_an_export_inside_a_retiring_worktree_needs_a_destination_or_disposal(checkout, tmp_path, run_cmd):
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    common = _common(checkout.repo)
    revision = checkout.prompt_commit()
    tree, durable = base / "manager-tree", base / "durable-package"
    tree_rid = _rid(api.create_worktree(checkout.ws, IDENT, path=str(tree), actor="manager"), "worktree")
    tree_ws = workspace(tree, WS)
    prepared = api.prepare(tree_ws, revision)
    Path(prepared["worktree"], checkout.meta["report_path"]).write_text("Reviewed report.\n", encoding="utf-8")
    collected = api.collect(tree_ws, IDENT, auditor_stopped="finished")
    inner = api.export_evidence(tree_ws, IDENT, collection=collected["collection"], selectors=["REPORT.md"],
                                output="inner-package", actor="manager")
    outer = api.export_evidence(tree_ws, IDENT, collection=collected["collection"], selectors=["REPORT.md"],
                                output=str(durable), actor="manager")
    inner_rid, outer_rid = inner["resource"], outer["resource"]
    assert Path(inner["manifest"]).is_relative_to(tree) and not Path(outer["manifest"]).is_relative_to(tree)
    durable_bytes = snapshot_tree(durable)

    plan = _plan(cli, tree, WS, IDENT, "--abandon")
    reasons = " ".join(plan[tree_rid]["reasons"])
    assert plan[tree_rid]["disposition"] == "blocked"
    assert f"contains recorded export {inner_rid}" in reasons and f"--dispose {inner_rid}" in reasons
    # Differing only in location: the durable export outside the tree blocks nothing.
    assert outer_rid not in reasons
    assert plan[inner_rid]["disposition"] == plan[outer_rid]["disposition"] == "retained"
    disposed = _plan(cli, tree, WS, IDENT, "--abandon", "--dispose", inner_rid)
    assert disposed[tree_rid]["disposition"] == "remove"
    assert [item["rid"] for item in disposed[tree_rid]["disposed"]] == [inner_rid]

    closed = _abandon(cli, tree, WS, IDENT, "--dispose", inner_rid)
    results = {item["rid"]: item["outcome"] for item in _by_rid(closed["resources"])[tree_rid]["results"]}
    assert results[tree_rid] == "removed" and set(results) == {tree_rid, inner_rid}
    assert results[inner_rid].startswith("removed with its container")
    assert not tree.exists() and not Path(inner["manifest"]).exists()
    claim = support.read_json(_records(common, tree_rid) / "claims/0001.json")
    assert [item["rid"] for item in claim["disposed"]] == [inner_rid], "the disposal decision is in the claim"
    assert api.show_resource(checkout.repo, inner_rid)["disposition"] == "retired"
    # Invariance: the durable package is untouched and stays deliberate retention.
    assert snapshot_tree(durable) == durable_bytes
    kept = cli("--repo", checkout.repo, "resource", "show", "--resource", outer_rid)["result"]
    assert kept["disposition"] == "retained" and kept["observation"]["state"] == "present"


# --- 8. an active claim refuses new uses and resumes without widening -----------------------------------


def test_an_active_claim_refuses_new_uses_and_resumes_the_same_generation(checkout, tmp_path, run_cmd, monkeypatch):
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    common = _common(checkout.repo)
    revision = checkout.prompt_commit()
    tree, bystander = base / "managed-tree", base / "bystander-dir"
    tree_rid = _rid(api.create_worktree(checkout.ws, HOLDER, path=str(tree), actor="manager"), "worktree")
    bystander_rid = api.create_directory(checkout.ws, PARTNER, path=str(bystander), actor="manager")["rid"]
    real = holdings._remove_worktree
    failures = []

    def fail_once(common_, rid, identity):
        if not failures:
            failures.append(rid)
            raise OSError("synthetic removal failure")
        return real(common_, rid, identity)

    with monkeypatch.context() as patch:
        patch.setattr(holdings, "_remove_worktree", fail_once)
        closed = api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="resources done")
    assert failures == [tree_rid], "firing control: the removal failed once"
    assert _by_rid(closed["resources"])[tree_rid]["outcome"] == "failed" and closed["exit_code"] == EXIT_ATTENTION
    attempts = [name for name in _claim_files(common, tree_rid) if name.startswith("0001.ATTEMPT-")]
    assert len(attempts) == 1 and _claim_files(common, tree_rid) == sorted(["0001.json", *attempts])
    assert tree.is_dir()
    assert cli("--repo", checkout.repo, "resource", "show", "--resource", tree_rid,
               allowed=(EXIT_ATTENTION,))["result"]["disposition"] == "claimed"

    # New uses inside the retiring tree are refused; nothing is written by the refusals.
    records = snapshot_tree(_records(common))
    assert _reason(api.prepare, workspace(tree, WS), revision).reason == "resource_retiring"
    assert not support.session_path(checkout, IDENT).exists()
    associate = ("--repo", checkout.repo, "--workspace", WS, "resource", "associate", "--audit-id", IDENT,
                 "--actor", "manager", "--resource")
    assert _refused(cli, *associate, tree_rid)["reason"] == "resource_retiring"
    assert _refused(cli, "--repo", checkout.repo, "--workspace", WS, "resource", "create-directory", "--audit-id",
                    IDENT, "--path", tree / "inner-dir", "--actor", "manager")["reason"] == "resource_retiring"
    assert not (tree / "inner-dir").exists() and snapshot_tree(_records(common)) == records
    # Differing only in the resource: one without an active claim takes the use; and preparing
    # the same prompt from a checkout outside the retiring tree proceeds.
    cli(*associate, bystander_rid)
    prepared = api.prepare(checkout.ws, revision)
    assert not Path(prepared["worktree"]).is_relative_to(tree)

    resumed = cli("--repo", checkout.repo, "close", "--resource", tree_rid, "--actor", "manager")["result"]
    assert [(item["rid"], item["outcome"], item["resumed"]) for item in resumed["results"]] == [
        (tree_rid, "removed", True)]
    assert not tree.exists()
    # Invariance: the resumed retirement ends the same generation; no new claim was made.
    assert _claim_files(common, tree_rid) == sorted(["0001.json", *attempts, "0001.RETIRED.json"])
    assert bystander.is_dir()


# --- 9. checkout homes inside managed directories and auditor scope ---------------------------------------


@pytest.mark.heavy
def test_a_checkout_home_inside_a_managed_directory_is_a_use_until_its_audit_closes(tmp_path, run_cmd):
    checkout = _two_workspaces(tmp_path, run_cmd)
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    common = _common(checkout.repo)
    first_prompt = _assign(checkout, WS, IDENT, checkout.base)
    second_prompt = _assign(checkout, OTHER, SECOND, first_prompt)
    holding, retired = base / "holding-dir", base / "retired-dir"
    holding_rid = api.create_directory(checkout.ws, HOLDER, path=str(holding), actor="manager")["rid"]
    retired_rid = api.create_directory(checkout.ws, PARTNER, path=str(retired), actor="manager")["rid"]
    assert api.close(checkout.ws, PARTNER, actor="manager", abandon=True,
                     reason="single-audit directory")["resources"][0]["outcome"] == "removed"
    assert not retired.exists()

    # Control: before any session pins a path inside it, the holder's close would remove it.
    assert _plan(cli, checkout.repo, WS, HOLDER)[holding_rid]["disposition"] == "remove"
    first = api.prepare(checkout.ws, first_prompt, checkout_home_path=holding / "home")
    assert Path(first["audit_dir"]).is_relative_to(holding / "home")
    plan = _plan(cli, checkout.repo, WS, HOLDER)
    assert plan[holding_rid]["disposition"] == "shared"
    assert f"{WS}:{IDENT}" in " ".join(plan[holding_rid]["reasons"])
    closed = _abandon(cli, checkout.repo, WS, HOLDER)
    assert _by_rid(closed["closeout"])[holding_rid]["disposition"] == "shared" and closed["resources"] == []
    assert holding.is_dir()
    shown = api.show_resource(checkout.repo, holding_rid)
    assert shown["disposition"] == "shared"
    assert [user["audit"]["audit_id"] for user in shown["users"] if user["live"]] == [IDENT]

    # A later session's auditor scope denies the live managed directory, not the retired one.
    second = api.prepare(workspace(checkout.repo, OTHER), second_prompt)
    roots = support.read_json(Path(second["session"]) / "session.json")["auditor_scope"]["private_roots"]
    assert str(holding) in roots and str(retired) not in roots

    # Invariance: the use ends with its audit; the directory is then retired without any live user.
    api.close(checkout.ws, IDENT, actor="manager", abandon=True, reason="done", discard_uncollected=True)
    after = api.show_resource(checkout.repo, holding_rid)
    assert after["disposition"] != "shared" and not [user for user in after["users"] if user["live"]]
    if after["disposition"] != "retired":
        # The close froze the directory with its own checkout inside, then removed that checkout,
        # so revalidation released the claim; the left-behind directory retires explicitly.
        retired_now = cli("--repo", checkout.repo, "close", "--resource", holding_rid, "--actor", "manager")["result"]
        assert [item["outcome"] for item in retired_now["results"]] == ["removed"]
    assert not holding.exists()
    endings = _generations(common, holding_rid)
    assert endings and None not in endings.values(), f"every claim generation ended: {endings}"
    assert endings[max(endings)] == "RETIRED" and list(endings.values()).count("RETIRED") == 1
    assert Path(second["worktree"]).is_dir(), "the other session's checkout is untouched"


# --- 10. a borrowed branch ----------------------------------------------------------------------------------


def test_a_borrowed_branch_survives_its_worktree_and_is_explained(checkout, tmp_path, run_cmd):
    base = tmp_path.resolve()
    cli = _cli(run_cmd, base)
    checkout.git("branch", "topic")
    tip = _ref(checkout.repo, "refs/heads/topic")
    borrowed_tree, owned_tree = base / "borrowed-tree", base / "owned-tree"
    borrowed = api.create_worktree(checkout.ws, HOLDER, path=str(borrowed_tree), existing_branch="topic",
                                   actor="manager")
    assert [item["kind"] for item in borrowed["resources"]] == ["worktree"], "no branch resource is created"
    borrowed_rid = borrowed["resources"][0]["rid"]
    # Differing only in branch ownership: a worktree with its own managed branch.
    owned = api.create_worktree(checkout.ws, HOLDER, path=str(owned_tree), branch="audit/owned", actor="manager")
    owned_rid, owned_branch = _rid(owned, "worktree"), _rid(owned, "branch")
    assert _worktrees(checkout.repo)[str(borrowed_tree)]["branch"] == "refs/heads/topic", "control: it borrows topic"

    note = "borrowed branch refs/heads/topic belongs to no resource here; retiring this worktree never removes it"
    plan = _plan(cli, checkout.repo, WS, HOLDER)
    assert plan[borrowed_rid]["disposition"] == "remove" and note in plan[borrowed_rid]["notes"]
    assert plan[owned_rid]["notes"] == []
    closed = _abandon(cli, checkout.repo, WS, HOLDER)
    assert {item["rid"]: item["outcome"] for item in closed["resources"]} == {
        borrowed_rid: "removed", owned_rid: "removed", owned_branch: "removed"}
    assert not borrowed_tree.exists() and not owned_tree.exists()
    assert not _ref(checkout.repo, "refs/heads/audit/owned")
    # Invariance: the borrowed branch is intact, and the retirement still explains it.
    assert _ref(checkout.repo, "refs/heads/topic") == tip
    after = _plan(cli, checkout.repo, WS, HOLDER)
    assert after[borrowed_rid]["disposition"] == "retired" and note in after[borrowed_rid]["notes"]
    shown = cli("--repo", checkout.repo, "resource", "show", "--resource", borrowed_rid)["result"]
    assert shown["identity"]["borrowed_branch"] == "refs/heads/topic" and shown["identity"]["branch_rid"] is None
