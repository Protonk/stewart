"""Worktree roles and retained commits, with real Git and destructive controls only in fixtures."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
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


#: The merged identity query, spelled here so that a change to it is a test change.
MERGED = ("rev-parse", "--is-bare-repository", "--show-toplevel", "--absolute-git-dir", "--path-format=absolute",
          "--git-common-dir")


def identity_trace(monkeypatch, function, path, answer=None):
    """``function(path)``'s outcome and the argv of each process it asked ``subprocess.Popen`` to start.

    Git's argv is listed after Stewart's ``-c`` settings. The outcome is the identity, or a refusal's
    type, reason and message. An ``answer`` stands in for the merged query's ``subprocess.run``: a
    (returncode, stdout) pair, or an exception to raise. It starts no process but is listed; every
    other query runs Git. Both patches replace ``subprocess`` attributes process-wide while
    ``function`` runs.
    """
    real_run, real_popen, calls = subprocess.run, subprocess.Popen, []

    def query(argv):
        argv = [str(arg) for arg in argv]
        if argv[:1] != ["git"]:
            return tuple(argv)
        argv = argv[1:]
        while argv[:1] == ["-c"]:
            argv = argv[2:]
        return tuple(argv)

    class Started(real_popen):
        def __init__(self, args, *rest, **kwargs):
            calls.append(query(args))
            super().__init__(args, *rest, **kwargs)

    def run(*args, **kwargs):
        argv = kwargs["args"] if "args" in kwargs else args[0]
        if answer is None or query(argv) != MERGED:
            return real_run(*args, **kwargs)  # starts its process through the recording Popen
        calls.append(MERGED)
        if isinstance(answer, BaseException):
            raise answer
        return subprocess.CompletedProcess(argv, answer[0], answer[1], b"")

    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "Popen", Started)
        patch.setattr(subprocess, "run", run)
        try:
            outcome = function(path)
        except StewartError as exc:
            outcome = (type(exc), exc.reason, str(exc))
    return outcome, calls


def assert_identity_replays(monkeypatch, cases, answers=None):
    """Each selection's outcome is the separate queries' own; the merged answer alone decides only a clean root.

    A decided selection starts the merged query only. Any other starts it and then exactly the
    queries ``_separate_identity`` starts on its own for the resolved selection.
    """
    import stewart._repository as repository  # private: a rename fails these tests, not importers' collection
    outcomes = {}
    for name, (path, decided) in cases.items():
        outcome, calls = identity_trace(monkeypatch, checkout_identity, path, (answers or {}).get(name))
        expected, queries = identity_trace(monkeypatch, repository._separate_identity, path.resolve())
        assert outcome == expected, f"{name}: the merged query answered {outcome}, the separate queries {expected}"
        wanted = [MERGED, *([] if decided else queries)]
        assert calls == wanted, f"{name}: started {calls}, expected {wanted}"
        outcomes[name] = outcome
    return outcomes


def test_checkout_identity_decides_only_a_clean_root_from_one_query(project_repo, tmp_path, run_cmd, monkeypatch):
    base = tmp_path.resolve()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(base))  # the test directory may lie inside a checkout
    linked, broken, bare, outside = base / "linked", base / "line\nbreak", base / "bare.git", base / "outside"
    # The separate queries trim both ends of Git's answers, so the merged decoding must too: a root
    # ending in a space is refused, and an administration ending in one is recorded trimmed.
    trailing, separate = base / "trail ", base / "separate"
    for worktree in (linked, broken, trailing):
        run_cmd(["git", "worktree", "add", "-q", "--detach", worktree], cwd=project_repo, check=True)
    run_cmd(["git", "init", "-q", "--separate-git-dir", base / "admin ", separate], check=True)
    run_cmd(["git", "clone", "-q", "--bare", project_repo, bare], check=True)
    # Below "held\n/" every piece of a split answer is an absolute path; only the line count tells.
    held, beside = base / "held\n" / "repo", base / "beside-held"
    held.mkdir(parents=True)
    run_cmd(["git", "init", "-q"], cwd=held, check=True)
    run_cmd(["git", "commit", "-q", "--allow-empty", "-m", "held"], cwd=held, check=True)
    run_cmd(["git", "worktree", "add", "-q", "--detach", beside], cwd=held, check=True)
    link, broken_link = base / "link", base / "line-break-link"  # selections spelled through a symlink
    link.symlink_to(project_repo, target_is_directory=True)
    broken_link.symlink_to(broken, target_is_directory=True)
    outside.mkdir()
    assert run_cmd(["git", "rev-parse", "--git-dir"], cwd=outside).returncode == 128, "outside lies in a repository"
    cases = {  # selection: (path, decided by the merged answer alone)
        "main root": (project_repo, True), "linked root": (linked, True), "root through a link": (link, True),
        "subdirectory": (project_repo / REL, False), "bare repository": (bare, False),
        ".git directory": (project_repo / ".git", False),
        "worktree administration": (project_repo / ".git/worktrees/linked", False),
        "outside any repository": (outside, False), "missing directory": (base / "missing", False),
        "root holding a line break": (broken, False), "line-break root through a link": (broken_link, False),
        "administration holding a line break": (beside, False),
        "root ending in a space": (trailing, False), "administration ending in a space": (separate, True),
    }
    outcomes = assert_identity_replays(monkeypatch, cases)
    # Each selection is what its name says, by the separate queries' own answers.
    for name in ("main root", "linked root", "root holding a line break", "administration holding a line break",
                 "administration ending in a space"):
        assert outcomes[name]["root"] == str(cases[name][0]), name
    assert outcomes["root through a link"] == outcomes["main root"]
    assert outcomes["line-break root through a link"] == outcomes["root holding a line break"]
    assert outcomes["linked root"]["common_dir"] == outcomes["main root"]["common_dir"] == str(project_repo / ".git")
    assert "\n" in outcomes["administration holding a line break"]["git_admin"]
    assert outcomes["subdirectory"] == (StewartError, "repository_root", f"select the worktree root explicitly: "
                                        f"{project_repo}; subdirectories are refused")
    assert (outcomes["bare repository"] == outcomes["outside any repository"]
            == (StewartError, "repository_root", "repository must be a non-bare Git working tree"))
    assert outcomes[".git directory"][:2] == outcomes["worktree administration"][:2] == (StewartError, "git_failed")
    assert outcomes["missing directory"][:2] == (StewartError, "repository_root")
    assert outcomes["missing directory"][2].startswith("cannot inspect the selected Git worktree: ")
    # Each call observes again: the linked root, re-created from the bare clone, is another repository's.
    run_cmd(["git", "worktree", "remove", linked], cwd=project_repo, check=True)
    run_cmd(["git", "worktree", "add", "-q", "--detach", linked], cwd=bare, check=True)
    again = assert_identity_replays(monkeypatch, {"re-created linked root": (linked, True),
                                                  "unchanged main root": (project_repo, True)})
    assert again["re-created linked root"]["common_dir"] == str(bare)
    assert again["unchanged main root"] == outcomes["main root"]


def test_checkout_identity_decides_only_clean_substituted_answers(project_repo, tmp_path, run_cmd, monkeypatch):
    """Substituted merged answers; the separate queries still run real Git.

    The real answer, substituted unchanged, is the decided control. Each other answer fails one
    condition, and a timeout gives none. Git before 2.25 printed nothing for --show-toplevel without
    a work tree, and Git before 2.31 does not know --path-format and echoes it as it echoes any
    unknown option, so inside a .git directory such a Git answers four lines: false, that directory,
    the echoed option and a relative common directory.
    """
    bare = tmp_path.resolve() / "bare.git"
    run_cmd(["git", "clone", "-q", "--bare", project_repo, bare], check=True)
    admin = project_repo / ".git"
    real = git(project_repo, *MERGED).stdout

    def lines(*values):
        return b"".join(os.fsencode(value) + b"\n" for value in values)

    answers = {
        "the real answer": (0, real),
        "an older Git inside .git": (0, lines("false", admin, "--path-format=absolute", ".git")),
        "bare with exit status 0": (0, lines("true", bare, bare, bare)),
        "complete with exit status 128": (128, lines("false", admin, admin, admin)),
        "an unterminated fifth line": (0, real + b"/unterminated"),
        "the merged query timing out": subprocess.TimeoutExpired(["git", *MERGED], 120),
    }
    cases = {"the real answer": (project_repo, True), "an older Git inside .git": (admin, False),
             "bare with exit status 0": (bare, False), "complete with exit status 128": (admin, False),
             "an unterminated fifth line": (project_repo, False), "the merged query timing out": (project_repo, False)}
    outcomes = assert_identity_replays(monkeypatch, cases, answers)
    assert (outcomes["the real answer"] == outcomes["an unterminated fifth line"]
            == outcomes["the merged query timing out"] == checkout_identity(project_repo))
    assert outcomes["an older Git inside .git"][:2] == (StewartError, "git_failed")
    assert outcomes["complete with exit status 128"][:2] == (StewartError, "git_failed")
    assert outcomes["bare with exit status 0"][:2] == (StewartError, "repository_root")


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
