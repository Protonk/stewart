"""Worktree roles and retained commits, with real Git and destructive controls only in fixtures."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import uuid

import pytest

from stewart._bootstrap import StewartError
from stewart._git import git, git_text
from stewart._repository import (
    DEFAULT_CHECKOUT_HOME, REGISTRATION_LOCK, ROLE_MARKER, checkout_identity, maintainer, register_auditor,
    retention_for, retain_commits,
    verify_retention,
)
from stewart.assignment import initialize
from stewart.collect import collect
from stewart.prepare import prepare
from stewart.session import load_session
from stewart.status import status
from stewart.workspace import Workspace, workspace

REL = "reviews/example"


@pytest.fixture
def ready_project(project_repo):
    """A project as it stands: Stewart's storage needs no ignore rule."""
    return project_repo


def assigned(repo, *, ident="one-question", base=False):
    ws = workspace(repo, REL)
    target = git_text(repo, "rev-parse", "HEAD")
    meta = initialize(ws, ident, target, inputs=["input.txt"], base=target if base else None)["assignment"]
    sections = {"Question": "Does the input preserve its value?", "Decision": "Whether to investigate.",
                "Scope and exclusions": "Read the input only.", "Evidence": "A committed input.",
                "Stop condition": "Report the comparison."}
    text = "# Assignment\n\n```audit-assignment\n" + json.dumps(meta) + "\n```\n\n"
    text += "".join(f"## {name}\n{body}\n\n" for name, body in sections.items())
    (repo / ws.prompt).write_text(text)
    git(repo, "add", ws.prompt)
    git(repo, "commit", "-qm", "prompt only")
    return ws, git_text(repo, "rev-parse", "HEAD"), target


def assert_reason(reason, function, *args, **kwargs):
    with pytest.raises(StewartError) as caught:
        function(*args, **kwargs)
    assert caught.value.reason == reason


def test_exact_repository_root_and_symlink_spelling(project_repo, tmp_path, run_cmd):
    root = checkout_identity(project_repo)
    assert root["root"] == str(project_repo)
    link = tmp_path / "selected-link"
    link.symlink_to(project_repo, target_is_directory=True)
    assert checkout_identity(link) == root
    assert workspace(link, REL).repo == project_repo
    assert_reason("repository_root", maintainer, project_repo / REL)
    assert_reason("repository_root", maintainer, tmp_path)
    bare = tmp_path / "bare.git"
    run_cmd(["git", "clone", "--bare", project_repo, bare])
    assert_reason("repository_root", maintainer, bare)
    # Constructing Workspace directly cannot bypass the operation-time guard.
    assert_reason("repository_root", initialize, Workspace(project_repo / REL, "nested"),
                  "one-question", "HEAD", inputs=["input.txt"])
    assert not (project_repo / REL / "nested").exists()


@pytest.mark.parametrize("selection", ["main", "other-branch", "linked", "detached"])
def test_preparation_accepts_maintainer_roles_independent_of_branch(ready_project, tmp_path, selection):
    repo = ready_project
    if selection in ("main", "other-branch"):
        git(repo, "branch", "-m", selection)
    elif selection == "linked":
        linked = tmp_path / "linked-maintainer"
        git(repo, "worktree", "add", "-b", "linked-review", str(linked))
        repo = linked
    else:
        git(repo, "checkout", "--detach")
    ws, prompt, _ = assigned(repo, base=True)
    result = prepare(ws, prompt)
    _, record = load_session(ws, "one-question")
    assert record["session_uuid"] == result["session_uuid"]
    assert str(uuid.UUID(record["session_uuid"])) == record["session_uuid"]
    assert set(verify_retention(repo, record)["refs"]) == {"prompt", "target", "base"}
    assert "main_before" not in record and "maintainer_before" in record
    view = status(ws, "one-question")
    assert view["schema"] == "stewart.status/13" and "main" not in view["identities"]
    assert view["identities"]["retention"] == {"status": "verified", "pins": record["retention"]}
    assert git_text(Path(result["worktree"]), "branch", "--show-current") == ""


def test_auditor_role_survives_move_and_unregistered_reserved_root_is_refused(ready_project, tmp_path):
    ws, prompt, _ = assigned(ready_project)
    result = prepare(ws, prompt)
    auditor = Path(result["worktree"])
    assert_reason("auditor_worktree", prepare, workspace(auditor, REL), prompt)
    assert not (auditor / ".git").is_dir(), "the auditor checkout is a linked worktree holding no Stewart storage"
    old_admin = checkout_identity(auditor)["git_admin"]
    moved = tmp_path / "moved-auditor"
    # The lifetime lock refuses a move until the manager unlocks it on purpose.
    assert git(ready_project, "worktree", "move", str(auditor), str(moved), check=False).returncode != 0
    git(ready_project, "worktree", "unlock", str(auditor))
    git(ready_project, "worktree", "move", str(auditor), str(moved))
    assert checkout_identity(moved)["git_admin"] == old_admin
    for operation in (initialize,):
        assert_reason("auditor_worktree", operation, workspace(moved, REL), "another", "HEAD", inputs=["input.txt"])
    assert_reason("auditor_worktree", status, workspace(moved, REL), "one-question")
    linked = tmp_path / "legitimate-linked"
    git(ready_project, "worktree", "add", "--detach", str(linked), "HEAD")
    assert maintainer(linked)["root"] == str(linked)
    # Backstop: a repository inside the default checkout home is never a maintainer.
    orphan = Path.home() / DEFAULT_CHECKOUT_HOME / "orphan-key" / "unregistered" / "worktree"
    orphan.mkdir(parents=True)
    git(orphan, "init", "-q")
    assert_reason("auditor_worktree", maintainer, orphan)


def test_scope_keeps_other_checkouts_and_retired_session_locations_private(ready_project, tmp_path):
    from stewart.auditor_scope import claude_settings
    ws, prompt, _ = assigned(ready_project)
    first = prepare(ws, prompt)
    linked = tmp_path / "linked"
    git(ready_project, "worktree", "add", "-b", "other-maintainer", str(linked))
    git(ready_project, "worktree", "remove", "--force", "--force", str(first["worktree"]))
    other_ws, other_prompt, _ = assigned(linked, ident="second-question")
    second = prepare(other_ws, other_prompt)
    record = json.loads((Path(second["session"]) / "session.json").read_bytes())
    roots = record["auditor_scope"]["private_roots"]
    # The main checkout holds the Git common directory, so its entries are
    # denied instead of the checkout itself; the linked maintainer is denied whole.
    assert str(ready_project) not in roots and str(ready_project / "input.txt") in roots and str(linked) in roots
    assert first["session"] in roots, "removing a checkout must not remove its private session exclusion"
    assert first["audit_dir"] in roots, "another session's checkout directory stays private"
    denied = claude_settings(record["auditor_scope"])["sandbox"]["filesystem"]["denyRead"]
    assert set(roots).issubset(denied)
    (ready_project / "unrelated.txt").write_text("unrelated change")
    assert load_session(other_ws, "second-question")[1]["auditor_scope"] == record["auditor_scope"]
    # The receipt remains a snapshot; interpreting it never rewrites it using
    # today's worktree population. Effective harness behavior has a separate gate.


@pytest.mark.parametrize("damage", ["corrupt", "symlink", "unknown-role", "unreadable"])
def test_role_registry_fails_closed_but_ignores_unrelated_files(ready_project, tmp_path, damage):
    ws, prompt, _ = assigned(ready_project)
    prepare(ws, prompt)
    registry = ready_project / ".git/stewart/worktree-roles"
    row = next(registry.iterdir())
    original = row.read_bytes()
    (ready_project / "unrelated.txt").write_text("does not change a role")
    assert maintainer(ready_project)
    if damage == "corrupt":
        row.write_text("invalid JSON")
    elif damage == "symlink":
        outside = tmp_path / "role.json"
        outside.write_bytes(original)
        row.unlink()
        row.symlink_to(outside)
    elif damage == "unknown-role":
        value = json.loads(original)
        value["role"] = "maintainer"
        row.write_text(json.dumps(value))
    else:
        row.chmod(0)
    try:
        assert_reason("worktree_role_registry", maintainer, ready_project)
    finally:
        if damage == "unreadable":
            row.chmod(0o600)


def test_preparation_needs_no_ignore_rule_and_leaves_no_working_tree_footprint(ready_project):
    ws, prompt, _ = assigned(ready_project)
    exclude = ready_project / ".git/info/exclude"
    exclude.write_text("# existing project configuration\n")
    footprint = ["status", "--porcelain=v1", "--ignored", "--untracked-files=all"]
    before = git_text(ready_project, *footprint)
    result = prepare(ws, prompt)
    report = Path(result["worktree"]) / ws.report_path("one-question")
    report.write_text("a report\n")
    collect(ws, "one-question", auditor_stopped="finished")
    assert git_text(ready_project, *footprint) == before, "custody lives outside the working tree"
    assert exclude.read_text() == "# existing project configuration\n"
    assert not git(ready_project, "add", "--all", "--dry-run").stdout, "nothing Stewart wrote is stageable"
    # Control: an ordinary new file in the same checkout does appear.
    (ready_project / "ordinary.txt").write_text("new\n")
    assert "?? ordinary.txt" in git_text(ready_project, *footprint)


@pytest.mark.parametrize("keep_refs", [True, False])
def test_prepared_prompt_and_target_survive_gc_only_with_their_refs(ready_project, keep_refs):
    original_head = git_text(ready_project, "rev-parse", "HEAD")
    (ready_project / "target-only.txt").write_text("a distinct audited target\n")
    git(ready_project, "add", "target-only.txt")
    git(ready_project, "commit", "-qm", "target not on the later maintainer branch")
    ws, prompt, target = assigned(ready_project, base=True)
    prompt_bytes = (ready_project / ws.prompt).read_bytes()
    git(ready_project, "reset", "--hard", original_head)
    (ready_project / ws.prompt).write_bytes(prompt_bytes)
    assert git_text(ready_project, "branch", "--contains", prompt) == ""
    result = prepare(ws, prompt)
    _, record = load_session(ws, "one-question")
    git(ready_project, "worktree", "remove", "--force", "--force", result["worktree"])
    if not keep_refs:
        for entry in record["retention"]["refs"].values():
            git(ready_project, "update-ref", "-d", entry["ref"])
    (ready_project / "irrelevant-prose.txt").write_text("not a retention mechanism\n")
    git(ready_project, "reflog", "expire", "--expire=now", "--all")
    git(ready_project, "gc", "--prune=now")
    for commit in (prompt, target):
        assert (git(ready_project, "cat-file", "-e", commit, check=False).returncode == 0) is keep_refs, (
            "identically prepared and removed checkouts differ only in whether their refs remain")
    if keep_refs:
        assert verify_retention(ready_project, record) == record["retention"]


def test_retention_transaction_is_create_only_and_atomic(ready_project):
    target = git_text(ready_project, "rev-parse", "HEAD")
    pins = retention_for(str(uuid.uuid4()), target, target, None)
    git(ready_project, "update-ref", pins["refs"]["target"]["ref"], target)
    assert_reason("session_retention", retain_commits, ready_project, pins)
    assert git(ready_project, "rev-parse", "--verify", pins["refs"]["prompt"]["ref"], check=False).returncode != 0
    assert git_text(ready_project, "rev-parse", pins["refs"]["target"]["ref"]) == target


def test_failed_preparation_keeps_its_refs_and_failure_stage(ready_project, monkeypatch):
    import importlib
    prepare_module = importlib.import_module("stewart.prepare")
    original = prepare_module.git

    def fail_worktree(repo, *args, **kwargs):
        if args[:2] == ("worktree", "add"):
            raise StewartError("fixture worktree failure", reason="git_failed")
        return original(repo, *args, **kwargs)

    ws, prompt, _ = assigned(ready_project)
    monkeypatch.setattr(prepare_module, "git", fail_worktree)
    assert_reason("prepare_failed", prepare, ws, prompt)
    directory, record = load_session(ws, "one-question")
    assert verify_retention(ready_project, record) == record["retention"]
    assert json.loads((directory / "PREPARE-ERROR.json").read_text())["stage"] == "worktree"
    assert not (directory / "LAUNCH.md").exists()


def test_missing_retention_ref_refuses_recovery_after_preserving_raw_report(ready_project):
    ws, prompt, _ = assigned(ready_project)
    result = prepare(ws, prompt)
    report = Path(result["worktree"]) / ws.report_path("one-question")
    report.write_bytes(b"raw report without a declaration\n")
    pin = result["retention"]["refs"]["prompt"]["ref"]
    git(ready_project, "update-ref", "-d", pin)
    assert_reason("session_retention", load_session, ws, "one-question")
    captured = collect(ws, "one-question", auditor_stopped="finished")
    assert (Path(captured["path"]) / "REPORT.md").read_bytes() == report.read_bytes()
    assert captured["receipt"]["retention"]["status"] == "invalid"
    assert captured["receipt"]["errors"]
    view = status(ws, "one-question")
    assert any(p["reason"] == "session_retention" for p in view["session"]["problems"])
    assert view["identities"]["retention"]["status"] == "invalid"
    assert not view["next_actions"]
    git(ready_project, "update-ref", pin, prompt)
    assert load_session(ws, "one-question")[1]["prompt_commit"] == prompt


@pytest.mark.parametrize("remove_first", [True, False])
def test_new_auditor_lifetime_can_reuse_git_administrative_name(ready_project, remove_first):
    ws, prompt, _ = assigned(ready_project)
    first = prepare(ws, prompt)
    first_admin = checkout_identity(Path(first["worktree"]))["git_admin"]
    if remove_first:
        git(ready_project, "worktree", "remove", "--force", "--force", first["worktree"])
    ws, prompt, _ = assigned(ready_project, ident="second")
    second = prepare(ws, prompt)
    second_admin = checkout_identity(Path(second["worktree"]))["git_admin"]
    assert (second_admin == first_admin) is remove_first, "Git's name-reuse control must fire"
    marker = json.loads((Path(second_admin) / ROLE_MARKER).read_text())
    assert marker["role_uuid"] == second["session_uuid"] != first["session_uuid"]
    assert len(list((ready_project / ".git/stewart/worktree-roles").iterdir())) == 2
    assert_reason("auditor_worktree", maintainer, Path(second["worktree"]))


@pytest.mark.parametrize("basename", ["worktree", "another-name"])
def test_new_linked_maintainer_does_not_inherit_removed_auditor_role(ready_project, tmp_path, basename):
    ws, prompt, _ = assigned(ready_project)
    first = prepare(ws, prompt)
    old_admin = checkout_identity(Path(first["worktree"]))["git_admin"]
    git(ready_project, "worktree", "remove", "--force", "--force", first["worktree"])
    linked = tmp_path / basename
    git(ready_project, "worktree", "add", "--detach", str(linked), prompt)
    observed = maintainer(linked)
    assert (observed["git_admin"] == old_admin) is (basename == "worktree")
    assert not (Path(observed["git_admin"]) / ROLE_MARKER).exists()


def test_failed_role_registration_stays_auditor_after_forced_move(ready_project, tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module("stewart.prepare")
    ws, prompt, _ = assigned(ready_project)

    def fail(*args):
        raise StewartError("induced publication failure", reason="worktree_role_conflict")

    monkeypatch.setattr(module, "register_auditor", fail)
    assert_reason("prepare_failed", prepare, ws, prompt)
    directory, record = load_session(ws, "one-question")
    original = Path(record["worktree"])
    admin = Path(checkout_identity(original)["git_admin"])
    assert (admin / "locked").read_text().strip() == REGISTRATION_LOCK + record["session_uuid"]
    assert not (admin / ROLE_MARKER).exists()
    moved = tmp_path / "failed-auditor-moved"
    git(ready_project, "worktree", "move", "--force", "--force", str(original), str(moved))
    assert_reason("auditor_worktree", maintainer, moved)
    assert maintainer(ready_project)["root"] == str(ready_project)
    assert verify_retention(ready_project, record) == record["retention"]


def test_retention_refs_reject_symbolic_substitution_and_dangling_collision(ready_project):
    ws, prompt, _ = assigned(ready_project)
    prepare(ws, prompt)
    _, record = load_session(ws, "one-question")
    pin = record["retention"]["refs"]["prompt"]["ref"]
    branch = git_text(ready_project, "symbolic-ref", "HEAD")
    assert verify_retention(ready_project, record)
    git(ready_project, "symbolic-ref", pin, branch)
    assert git_text(ready_project, "rev-parse", pin) == prompt, "same object, different retention mechanism"
    assert_reason("session_retention", verify_retention, ready_project, record)
    fresh = retention_for(str(uuid.uuid4()), prompt, prompt, None)
    collision = fresh["refs"]["target"]["ref"]
    destination = "refs/heads/not-created"
    git(ready_project, "symbolic-ref", collision, destination)
    assert_reason("session_retention", retain_commits, ready_project, fresh)
    assert git_text(ready_project, "symbolic-ref", collision) == destination
    assert git(ready_project, "rev-parse", "--verify", destination, check=False).returncode != 0
    assert git(ready_project, "rev-parse", "--verify", fresh["refs"]["prompt"]["ref"], check=False).returncode != 0


@pytest.mark.parametrize("decision", ["commit", "abort"])
def test_retention_inspection_holds_git_locks_and_abort_releases_them(ready_project, monkeypatch, decision):
    """The comparison runs under ref locks, and refusal publishes no partial set."""
    import stewart._git as module
    commit = git_text(ready_project, "rev-parse", "HEAD")
    retention = retention_for(str(uuid.uuid4()), commit, commit, commit)
    refs = {entry["ref"]: entry["commit"] for entry in retention["refs"].values()}
    # The competing writer works before confinement; it is not a broken probe.
    control = "refs/stewart/control-writer"
    git(ready_project, "update-ref", "--no-deref", control, commit, "0" * len(commit))
    assert git_text(ready_project, "rev-parse", control) == commit
    observed = []
    original = module.git

    def inspect(repo, *args, **kwargs):
        if args[:2] == ("symbolic-ref", "--quiet") and args[2] in refs:
            ref = args[2]
            observed.append(ref)
            attempt = original(repo, "update-ref", "--no-deref", ref, commit, "0" * len(commit), check=False)
            assert attempt.returncode != 0 and b"cannot lock ref" in attempt.stderr
            assert all(original(repo, "rev-parse", "--verify", name, check=False).returncode != 0 for name in refs)
            (repo / "unrelated-note.txt").write_text("Unrelated worktree bytes do not affect ref creation.\n")
            if decision == "abort":
                raise StewartError("injected inspection failure", reason="git_ref_transaction")
        return original(repo, *args, **kwargs)

    monkeypatch.setattr(module, "git", inspect)
    if decision == "abort":
        assert_reason("session_retention", retain_commits, ready_project, retention)
        assert observed == [next(iter(refs))]
        assert all(original(ready_project, "rev-parse", "--verify", name, check=False).returncode != 0 for name in refs)
        monkeypatch.setattr(module, "git", original)
        retain_commits(ready_project, retention)
    else:
        retain_commits(ready_project, retention)
        assert observed == list(refs)
    for name in refs:
        assert original(ready_project, "symbolic-ref", "--quiet", name, check=False).returncode == 1
        assert git_text(ready_project, "rev-parse", name) == commit
    assert git_text(ready_project, "rev-parse", control) == commit
    assert (ready_project / "unrelated-note.txt").read_text().startswith("Unrelated")


@pytest.mark.parametrize("damage", ["json", "link"])
def test_moved_auditor_marker_failures_are_not_unassigned_roles(ready_project, tmp_path, damage):
    ws, prompt, _ = assigned(ready_project)
    result = prepare(ws, prompt)
    worktree = Path(result["worktree"])
    moved = tmp_path / "moved-marker-case"
    git(ready_project, "worktree", "unlock", str(worktree))
    git(ready_project, "worktree", "move", str(worktree), str(moved))
    marker = Path(checkout_identity(moved)["git_admin"]) / ROLE_MARKER
    assert_reason("auditor_worktree", maintainer, moved)
    if damage == "json":
        marker.write_text("not a marker")
    else:
        outside = tmp_path / "marker.json"
        outside.write_bytes(marker.read_bytes())
        marker.unlink()
        marker.symlink_to(outside)
    assert_reason("worktree_role_registry", maintainer, moved)
    assert maintainer(ready_project)["root"] == str(ready_project)
