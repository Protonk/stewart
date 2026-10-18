"""Private custody under the Git common directory; checkouts outside every working tree.

Sessions live at ``<common>/stewart/sessions`` and survive any ``git clean``.
Each session's worktree, runtime and experiment homes live in a UUID-named
directory under the per-user checkout home, locked for their lifetime. These
tests run with a private HOME (see conftest), so the default homes resolve
inside the test's own directory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import sys

import pytest

from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, EXIT_UNVERIFIED, StewartError
from stewart._git import git
from stewart._repository import DEFAULT_CHECKOUT_HOME, LIFETIME_LOCK, REGISTRATION_LOCK, ROLE_MARKER
from stewart.collect import collect
from stewart.prepare import prepare
from stewart.status import status, status_list
from stewart.triage import triage
from stewart.workspace import workspace
import stewart_support as support
from stewart_support import WS, response_for

pytestmark = pytest.mark.system


def _prepared(checkout, **kwargs):
    revision = checkout.prompt_commit()
    return prepare(checkout.ws, revision, **kwargs), revision


@pytest.mark.heavy
def test_custody_survives_every_git_clean_and_status_is_unchanged(checkout):
    prepared, _ = _prepared(checkout)
    (Path(prepared["worktree"]) / checkout.meta["report_path"]).write_text("report\n")
    collect(checkout.ws, "one-question", auditor_stopped="finished")
    before = status(checkout.ws, "one-question")
    # Control: the clean really removes ignored and untracked files.
    ignored = checkout.repo / "ignored/scratch-output.bin"
    ignored.parent.mkdir(exist_ok=True)
    ignored.write_bytes(b"disposable\n")
    checkout.git("clean", "-ffdx")
    assert not ignored.exists()
    session = Path(prepared["session"])
    assert (session / "session.json").is_file() and list((session / "collections").iterdir())
    assert Path(prepared["worktree"]).is_dir() and Path(prepared["runtime"]["root"]).is_dir()
    after = status(checkout.ws, "one-question")
    assert after == before, "a clean of the maintainer checkout changes nothing Stewart observes"


def test_sessions_are_repo_wide_and_bound_to_their_maintainer(checkout, tmp_path):
    prepared, _ = _prepared(checkout)
    linked = tmp_path / "second-maintainer"
    checkout.git("worktree", "add", "-b", "second-maintainer", str(linked))
    other = workspace(linked, WS)
    # The same audit ID is the same session from every maintainer worktree.
    with pytest.raises(StewartError) as refused:
        prepare(other, checkout.git("rev-parse", "HEAD", cwd=linked))
    assert refused.value.reason == "destination_exists" and prepared["session"] in refused.value.retained
    with pytest.raises(StewartError) as refused:
        status(other, "one-question")
    assert refused.value.reason == "session_other_maintainer" and refused.value.exit_code == 2
    assert str(checkout.repo) in refused.value.next_steps[0]
    # Control: the owning maintainer still reads its own session.
    assert status(checkout.ws, "one-question")["session"]["supported"] is True


def test_a_session_whose_maintainer_checkout_is_gone_says_how_to_restore_it(checkout, tmp_path):
    from stewart.close import close
    revision = checkout.prompt_commit()
    linked = tmp_path / "linked-maintainer"
    checkout.git("worktree", "add", "-b", "linked-maintainer", str(linked), revision)
    owner = workspace(linked, WS)
    prepared = prepare(owner, revision)
    checkout.git("worktree", "remove", "--force", str(linked))
    with pytest.raises(StewartError) as refused:
        status(checkout.ws, "one-question")
    assert refused.value.reason == "session_owner_missing" and refused.value.exit_code == EXIT_REFUSED
    assert f"git worktree add {linked}" in refused.value.next_steps[0]
    with pytest.raises(StewartError) as refused:
        collect(checkout.ws, "one-question", auditor_stopped="finished")
    assert refused.value.reason == "session_owner_missing"
    # The named step works: the recreated checkout owns the session again.
    checkout.git("worktree", "add", str(linked), "linked-maintainer")
    assert status(workspace(linked, WS), "one-question")["session"]["supported"] is True
    checkout.git("worktree", "remove", "--force", str(linked))
    # Any maintainer of the repository may abandon it while its owner is gone.
    result = close(checkout.ws, "one-question", actor="manager", abandon=True, reason="owner removed")
    assert result["closed"] and not Path(prepared["worktree"]).exists()


def test_an_unwritable_checkout_home_is_refused_before_any_session(checkout, tmp_path, run_cmd):
    home = tmp_path / "readonly-home"
    home.mkdir(mode=0o700)
    home.chmod(stat.S_IRUSR | stat.S_IXUSR)
    revision = checkout.prompt_commit()
    try:
        import stewart
        installed = Path(stewart.__file__).parent.parent
        result = run_cmd([sys.executable, "-I", "-m", "stewart", "--repo", str(checkout.repo), "--workspace", WS,
                          "--json", "prepare", "--prompt-commit", revision, "--checkout-home", str(home)],
                         cwd=installed, env={})
    finally:
        home.chmod(stat.S_IRWXU)
    error = json.loads(result.stdout)["error"]
    assert result.returncode == EXIT_REFUSED and error["reason"] == "manager_grant_missing"
    assert str(home.resolve()) in error["next_steps"][0]
    assert not support.session_path(checkout).exists(), "the audit ID is not used up"
    # Control: the same ID prepares once the home is writable.
    assert prepare(checkout.ws, revision, checkout_home_path=home)["audit_id"] == "one-question"


@pytest.mark.parametrize("place", ["repository", "linked", "common", "manager", "prefix", "link", "mode", "relative"])
def test_checkout_home_must_be_separate_private_and_unlinked(checkout, tmp_path, place):
    revision = checkout.prompt_commit()
    linked = tmp_path / "linked-maintainer"
    checkout.git("worktree", "add", "--detach", str(linked), revision)
    homes = {
        "repository": checkout.repo / "checkouts", "linked": linked / "checkouts",
        "common": checkout.repo / ".git/checkouts", "manager": Path(os.environ["STEWART_MANAGER_HOME"]) / "checkouts",
        "prefix": Path(sys.prefix).resolve() / "checkouts", "relative": Path("relative-home"),
    }
    if place == "link":
        real = tmp_path / "real-home"
        real.mkdir(mode=0o700)
        homes[place] = tmp_path / "linked-home"
        homes[place].symlink_to(real, target_is_directory=True)
    elif place == "mode":
        homes[place] = tmp_path / "shared-home"
        homes[place].mkdir(mode=0o755)
        homes[place].chmod(0o755)
    if place == "prefix" and not os.access(Path(sys.prefix).resolve(), os.W_OK):
        pytest.skip("the interpreter prefix is not writable here")
    with pytest.raises(StewartError) as refused:
        prepare(checkout.ws, revision, checkout_home_path=homes[place])
    assert refused.value.reason == "checkout_home" and refused.value.next_steps
    assert not support.session_path(checkout).exists(), "a refused home allocates nothing"
    if place in ("repository", "linked", "common", "manager", "prefix"):
        assert not homes[place].exists(), "a refused home is not created"
    # Control: a separate private home succeeds, and the default resolves under HOME.
    chosen = tmp_path / "separate-home"
    result = prepare(checkout.ws, revision, checkout_home_path=chosen)
    assert Path(result["audit_dir"]).is_relative_to(chosen)
    assert stat.S_IMODE(chosen.stat().st_mode) == 0o700


def test_default_checkout_home_is_under_home(checkout):
    prepared, _ = _prepared(checkout)
    assert Path(prepared["checkout_home"]) == Path.home() / DEFAULT_CHECKOUT_HOME
    assert Path(prepared["worktree"]).is_relative_to(Path.home() / DEFAULT_CHECKOUT_HOME)


def test_checkouts_are_named_by_uuid_and_the_session_by_audit_id(tmp_path, run_cmd):
    checkout = support.make_checkout(tmp_path, run_cmd, ws_rel="audits/zebra-workspace")
    checkout.meta["audit_id"] = "quokka-question"
    checkout.meta["report_path"] = checkout.ws.report_path("quokka-question")
    prepared, _ = _prepared(checkout)
    worktree = Path(prepared["worktree"])
    listed = checkout.git("worktree", "list", "--porcelain", cwd=worktree)
    for name in ("quokka-question", "zebra-workspace"):
        assert name not in str(Path(prepared["audit_dir"])) and name not in listed.split("\n", 1)[1]
    assert Path(prepared["audit_dir"]).name == prepared["session_uuid"]
    # Control: the private session path names both.
    assert "quokka-question" in prepared["session"] and "zebra-workspace" in prepared["session"]


@pytest.mark.heavy
def test_lifetime_lock_refuses_cleanup_and_keeps_the_role(checkout, tmp_path):
    prepared, _ = _prepared(checkout)
    worktree = Path(prepared["worktree"])
    listed = checkout.git("worktree", "list", "--porcelain")
    assert f"locked {LIFETIME_LOCK}{prepared['session_uuid']}" in listed
    for force in ([], ["--force"]):
        assert git(checkout.repo, "worktree", "remove", *force, str(worktree), check=False).returncode != 0
    assert worktree.is_dir()
    # Invariance: the auditor's ordinary Git use is unaffected by the lock.
    assert checkout.git("rev-parse", "HEAD", cwd=worktree) == prepared["prompt_commit"]
    assert checkout.git("status", "--porcelain", cwd=worktree) == "?? audits/ws/.stewart-handoffs/"
    # Even after the directory itself is deleted, prune keeps the locked
    # registration and the role marker beside it.
    admin = Path(checkout.git("rev-parse", "--absolute-git-dir", cwd=worktree))
    import shutil
    shutil.rmtree(worktree)
    checkout.git("worktree", "prune")
    assert (admin / ROLE_MARKER).is_file() and str(worktree) in checkout.git("worktree", "list", "--porcelain")
    # The lifetime lock is not an unfinished registration.
    assert not (admin / "locked").read_text().startswith(REGISTRATION_LOCK)
    # Control: an unlocked plain worktree is removed by the same commands.
    plain = tmp_path / "plain"
    checkout.git("worktree", "add", "--detach", str(plain))
    checkout.git("worktree", "remove", str(plain))
    assert not plain.exists()


def test_maintainer_inside_a_registered_checkout_directory_is_refused(checkout):
    prepared, _ = _prepared(checkout)
    nested = Path(prepared["audit_dir"]) / "nested-maintainer"
    nested.mkdir()
    checkout.git("init", "-q", cwd=nested)
    with pytest.raises(StewartError) as refused:
        status(workspace(nested, WS), "one-question")
    assert refused.value.reason == "auditor_worktree"
    # The marker still refuses the auditor checkout itself.
    with pytest.raises(StewartError) as refused:
        status(workspace(Path(prepared["worktree"]), WS), "one-question")
    assert refused.value.reason == "auditor_worktree"


@pytest.mark.heavy
def test_lost_session_records_refuse_reuse_and_say_why(checkout, run_cmd):
    import shutil
    prepared, revision = _prepared(checkout)
    checkout.git("worktree", "unlock", prepared["worktree"])
    checkout.git("worktree", "remove", "--force", prepared["worktree"])
    shutil.rmtree(prepared["session"])
    with pytest.raises(StewartError) as refused:
        status(checkout.ws, "one-question")
    # A targeted view refuses (2); the listing below reports the loss (3).
    assert refused.value.reason == "session_records_missing" and refused.value.exit_code == EXIT_REFUSED
    assert any(item.endswith(".json") for item in refused.value.retained) and refused.value.next_steps
    with pytest.raises(StewartError) as refused:
        prepare(checkout.ws, revision)
    assert refused.value.reason == "session_records_missing" and "fresh audit ID" in refused.value.next_steps[0]
    from stewart.assignment import initialize
    with pytest.raises(StewartError) as refused:
        initialize(checkout.ws, "one-question", checkout.meta["target_commit"], inputs=["input.txt"])
    assert refused.value.reason == "session_records_missing", "init drafts no ID that prepare would refuse"
    listing = status_list(checkout.ws)
    assert listing["exit_code"] == EXIT_UNVERIFIED
    assert [entry["problem"]["reason"] for entry in listing["sessions"]] == ["session_records_missing"]
    # Control: a fresh audit ID prepares in the same repository.
    checkout.meta["audit_id"] = "second-question"
    checkout.meta["report_path"] = checkout.ws.report_path("second-question")
    assert prepare(checkout.ws, checkout.prompt_commit())["audit_id"] == "second-question"


def test_permission_failures_name_the_write_location(checkout, run_cmd):
    prepared, _ = _prepared(checkout)
    storage = checkout.repo / ".git/stewart"
    view = status(checkout.ws, "one-question")
    assert view["manager_storage"]["private"] == str(storage)
    assert view["manager_storage"]["checkout_home"] == prepared["checkout_home"]
    (Path(prepared["worktree"]) / checkout.meta["report_path"]).write_text("report\n")
    collections = Path(prepared["session"]) / "collections"
    collections.mkdir()
    collections.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        import stewart
        installed = Path(stewart.__file__).parent.parent
        result = run_cmd([sys.executable, "-I", "-m", "stewart", "--repo", str(checkout.repo), "--workspace", WS,
                          "--json", "collect", "--audit-id", "one-question", "--auditor-stopped", "finished"],
                         cwd=installed, env={})
    finally:
        collections.chmod(stat.S_IRWXU)
    error = json.loads(result.stdout)["error"]
    assert result.returncode == 2 and error["reason"] == "manager_grant_missing"
    assert str(storage) in error["next_steps"][0]
    # Control: once writable, the same command collects.
    assert collect(checkout.ws, "one-question", auditor_stopped="finished")["exit_code"] in (EXIT_OK, EXIT_ATTENTION)


def test_handoff_names_only_what_the_auditor_needs(checkout):
    prepared, _ = _prepared(checkout)
    handoff = Path(prepared["launch"]).read_text()
    session = Path(prepared["session"])
    for private in (str(session), str(checkout.repo / ".git/stewart"), "worktree-roles", os.environ["STEWART_MANAGER_HOME"],
                    "Configure the harness", "private session directory"):
        assert private not in handoff, private
    # Control: the auditor's own locations are named.
    assert prepared["worktree"] in handoff and prepared["runtime"]["root"] in handoff


@pytest.mark.heavy
def test_recovery_command_appears_only_when_the_runtime_fails_verification(checkout):
    prepared, _ = _prepared(checkout)
    healthy = status(checkout.ws, "one-question")
    assert healthy["preparation"]["runtime_recovery"] is None and healthy["exit_code"] == EXIT_OK
    assert "live_report_path" not in healthy["identities"], "the manager reads collected bytes"
    target = Path(prepared["runtime"]["root"]) / "stewart/_version.py"
    target.chmod(stat.S_IRUSR | stat.S_IWUSR)
    target.write_text(target.read_text() + "# changed\n")
    changed = status(checkout.ws, "one-question")
    assert changed["preparation"]["state"] == "runtime_unavailable"
    assert changed["preparation"]["runtime_recovery"]["argv"] and changed["exit_code"] == EXIT_UNVERIFIED
    # Invariance: nothing else in the view moved.
    for key in ("identities", "collections", "launches", "dispositions"):
        assert changed[key] == healthy[key], key


@pytest.mark.heavy
def test_status_exit_codes_follow_attention_not_routine_steps(checkout):
    prepared, _ = _prepared(checkout)
    assert status(checkout.ws, "one-question")["exit_code"] == EXIT_OK, "a ready session awaiting launch is no news"
    report = Path(prepared["worktree"]) / checkout.meta["report_path"]
    report.write_text("report without a declaration\n")
    collected = collect(checkout.ws, "one-question", auditor_stopped="finished")
    view = status(checkout.ws, "one-question")
    assert view["exit_code"] == EXIT_ATTENTION
    assert {item["message"] for item in view["attention"]} == {gap["id"] for gap in collected["gaps"]}
    triage(checkout.ws, "one-question", collection=collected["collection"], response=response_for(collected),
           actor="manager")
    assert status(checkout.ws, "one-question")["exit_code"] == EXIT_OK, "addressed gaps are history"
    receipt = Path(collected["path"]) / "collection.json"
    receipt.chmod(stat.S_IRUSR | stat.S_IWUSR)
    receipt.write_text("not json")
    corrupt = status(checkout.ws, "one-question")
    assert corrupt["exit_code"] == EXIT_UNVERIFIED


def test_listing_shows_every_session_with_its_owner(checkout, tmp_path):
    empty = status_list(checkout.ws)
    assert empty["sessions"] == [] and empty["exit_code"] == EXIT_OK, "an empty workspace lists nothing"
    prepared, _ = _prepared(checkout)
    linked = tmp_path / "linked-maintainer"
    checkout.git("worktree", "add", "-b", "other-owner", str(linked))
    other = workspace(linked, WS)
    checkout.meta["audit_id"] = "second-question"
    checkout.meta["report_path"] = checkout.ws.report_path("second-question")
    (linked / WS / "PROMPT.md").write_text(support.assignment_text(checkout.meta))
    checkout.git("add", "--", f"{WS}/PROMPT.md", cwd=linked)
    checkout.git("commit", "-qm", "second prompt", cwd=linked)
    prepare(other, checkout.git("rev-parse", "HEAD", cwd=linked))
    listing = status_list(checkout.ws)
    owners = {entry["audit_id"]: entry["owner"] for entry in listing["sessions"]}
    assert owners == {"one-question": str(checkout.repo), "second-question": str(linked)}
    assert listing["exit_code"] == EXIT_OK
    # An unreadable record is listed as a problem, never skipped.
    record = Path(prepared["session"]) / "session.json"
    record.chmod(0)
    try:
        entries = {entry["audit_id"]: entry for entry in status_list(checkout.ws)["sessions"]}
    finally:
        record.chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert entries["one-question"]["exit_code"] == EXIT_UNVERIFIED and "second-question" in entries


def test_experiment_home_lives_with_the_checkout(tmp_path, run_cmd):
    from stewart.experiment import release, run

    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    released = release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
    run(checkout.ws, "one-question", release=released["release"], timeout=60)
    home = Path(released["record"]["environment"]["HOME"])
    assert home.is_relative_to(Path(exp.prepared["audit_dir"])) and home.is_dir()
    assert (exp.session / "attempts" / released["release"] / "ATTEMPT.json").is_file(), "receipts stay private"
