"""Stewart runs Git in an auditor checkout only through that checkout's own verified administration.

A substituted ``.git`` (a link, or a regular file naming the main repository, another checkout's
administration, one Git's repair pointed back here, an administration the auditor wrote, or
nothing) is first shown to redirect Git; then collection, the auditor's check, close's plan and
close itself each refuse it or record the checkout as unobserved, and the manager's operations
start no Git process in the checkout. The genuine file, as Git writes it and with relative paths,
is followed, and every query names the verified administration, so a ``.git`` swapped after
verification is ignored. Release and run judge HEAD the same way.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import stewart._repository as repository
from stewart import report_declaration as declaration
from stewart._bootstrap import EXIT_ATTENTION, EXIT_UNVERIFIED, StewartError
from stewart._git import git
from stewart.close import close, close_plan
from stewart.collect import collect
from stewart.experiment import release, run
import stewart_support as support
from stewart_support import read_json

pytestmark = pytest.mark.system

SUBSTITUTES = ["a link to the main repository", "a file naming the main repository",
               "a file naming another checkout's administration",
               "another checkout's administration that Git's repair points here",
               "an administration the auditor wrote", "a file naming nothing"]


def _reason(function, *args, **kwargs) -> StewartError:
    with pytest.raises(StewartError) as caught:
        function(*args, **kwargs)
    return caught.value


def _administration(worktree: Path) -> Path:
    return Path((worktree / ".git").read_text(encoding="utf-8").removeprefix("gitdir: ").strip())


def _substitute(checkout, worktree: Path, revision: str, kind: str) -> None:
    """Replace the checkout's .git with one substitute; the maintainer's HEAD has moved past the prompt."""
    gitfile, admin = worktree / ".git", _administration(worktree)
    common = admin.parent.parent
    gitfile.unlink()
    if kind == "a link to the main repository":
        gitfile.symlink_to(common, target_is_directory=True)
    elif kind == "a file naming the main repository":
        gitfile.write_text(f"gitdir: {common}\n")
    elif kind == "an administration the auditor wrote":
        forged = worktree / "forged-admin"
        forged.mkdir()
        (forged / "HEAD").write_text(revision + "\n")
        (forged / "commondir").write_text(f"{common}\n")
        (forged / "gitdir").write_text(f"{gitfile}\n")
        gitfile.write_text(f"gitdir: {forged}\n")
    elif kind == "a file naming nothing":
        gitfile.write_text(f"gitdir: {checkout.tmp / 'nowhere'}\n")
    else:
        other = checkout.tmp / "other-checkout"
        checkout.git("worktree", "add", "-q", "--detach", str(other))
        gitfile.write_text(f"gitdir: {admin.parent / other.name}\n")
        if kind.endswith("points here"):
            # Repair points the other administration back at this checkout; planted again, the
            # substitute passes the back-pointer check and only the lifetime binding refuses it.
            checkout.git("worktree", "repair", str(worktree))
            gitfile.write_text(f"gitdir: {admin.parent / other.name}\n")


def _check(checkout, prepared, monkeypatch, capsys) -> tuple[int, str]:
    """The auditor's issued check, run in its checkout."""
    monkeypatch.chdir(prepared.worktree)
    code = declaration.main(["check", "--workspace", checkout.ws.rel, "--expected-worktree", str(prepared.worktree),
                             "--launch-prompt-commit", prepared.revision,
                             "--prompt-sha256", prepared.prepared["prompt_sha256"],
                             "--launch-token", prepared.prepared["launch_token"]])
    output = capsys.readouterr()
    return code, output.err


def _move_main(checkout) -> str:
    (checkout.repo / "other.txt").write_text("main moved on\n", encoding="utf-8")
    checkout.git("add", "other.txt")
    checkout.git("commit", "-qm", "Unrelated development on main")
    return checkout.git("rev-parse", "HEAD")


@pytest.mark.parametrize("kind", SUBSTITUTES)
def test_no_operation_runs_git_through_a_substituted_checkout_git(checkout, monkeypatch, capsys, kind):
    prepared = support.prepared_session(checkout, report="A partial report.\n")
    ident, worktree = checkout.meta["audit_id"], prepared.worktree
    admin = _administration(worktree)
    _move_main(checkout)
    _substitute(checkout, worktree, prepared.revision, kind)
    # Firing control: asked in the checkout, Git no longer reaches the checkout's administration.
    answered = git(worktree, "rev-parse", "--absolute-git-dir", check=False)
    assert answered.stdout.decode().strip() != str(admin), "the substitute redirects Git"
    missing = kind == "a file naming nothing"
    places = []

    def manager(function, *args, **kwargs):
        result, started = support.git_working_directories(monkeypatch, function, *args, **kwargs)
        places.extend(started)
        return result

    collected = manager(collect, checkout.ws, ident, auditor_stopped="finished")
    receipt = collected["receipt"]
    reasons = [error["reason"] for error in receipt["errors"]]
    # A .git naming nothing is a Git discovery failure (exit 1, collect again); any other substitute is identity.
    assert ("collection_failed" if missing else "checkout_identity") in reasons
    assert "checkout" not in receipt and receipt["git_discovery"] == "failed"
    assert collected["exit_code"] == (EXIT_ATTENTION if missing else EXIT_UNVERIFIED)
    assert (Path(collected["path"]) / "REPORT.md").read_text() == "A partial report.\n", "the report is preserved"

    code, err = _check(checkout, prepared, monkeypatch, capsys)
    assert code != 0
    if not missing:
        assert "Refused (checkout_git_file):" in err, err

    plan = manager(close_plan, checkout.ws, ident, abandon=True)
    assert plan["audit"]["refusal"]["reason"] == "uncollected_changes"
    assert "could not be observed fully" in plan["audit"]["refusal"]["message"]
    refused = manager(_reason, close, checkout.ws, ident, actor="manager", abandon=True, reason="substituted .git")
    assert refused.reason == "uncollected_changes"
    closed = manager(close, checkout.ws, ident, actor="manager", abandon=True, reason="substituted .git",
                     discard_uncollected=True)
    closing = read_json(Path(closed["closing"]))
    assert closing["observed"]["discarded"] is None and closing["observed"]["checkout"]["observed"] is False
    assert "Git is not run through it" in closing["observed"]["checkout"]["error"] or missing
    assert places, "firing control: the operations ran Git, in the maintainer's checkout"
    assert not [place for place in places if place == worktree or worktree in place.parents], \
        "no Git process ran in the checkout through the substitute"


@pytest.mark.parametrize("spelling", ["absolute, as Git writes it", "relative, as worktree.useRelativePaths writes it"])
def test_a_genuine_checkout_is_observed_through_its_verified_administration(checkout, monkeypatch, capsys,
                                                                             spelling):
    prepared = support.prepared_session(checkout, report="A partial report.\n")
    ident, worktree = checkout.meta["audit_id"], prepared.worktree
    admin = _administration(worktree)
    if spelling.startswith("relative"):
        (worktree / ".git").write_text(f"gitdir: {os.path.relpath(admin, worktree)}\n")
        (admin / "gitdir").write_text(os.path.relpath(worktree / ".git", admin) + "\n")
    collected = collect(checkout.ws, ident, auditor_stopped="finished")
    state = collected["receipt"]["checkout"]
    assert state["git_admin"] == str(admin) and state["head"] == prepared.revision
    assert not [error for error in collected["receipt"]["errors"] if error["reason"] == "checkout_identity"]
    code, err = _check(checkout, prepared, monkeypatch, capsys)
    assert code in (0, 1) and "Refused" not in err, err
    closed = close(checkout.ws, ident, actor="manager", abandon=True, reason="done")
    assert closed["closed"] and not worktree.exists(), "invariance: the genuine checkout closes as before"


def test_a_git_swapped_after_verification_is_never_followed(checkout, monkeypatch):
    prepared = support.prepared_session(checkout, report="A partial report.\n")
    ident, worktree, gitfile = checkout.meta["audit_id"], prepared.worktree, prepared.worktree / ".git"
    genuine, admin = gitfile.read_bytes(), _administration(prepared.worktree)
    main_head = _move_main(checkout)
    real, fired = repository.checkout_git_admin, []

    def verify_then_swap(where, *args, **kwargs):
        verified = real(where, *args, **kwargs)
        if Path(where) == worktree and not fired:
            gitfile.unlink()
            gitfile.symlink_to(checkout.repo / ".git", target_is_directory=True)
            fired.append(verified)
        return verified

    monkeypatch.setattr(repository, "checkout_git_admin", verify_then_swap)
    collected = collect(checkout.ws, ident, auditor_stopped="finished")
    assert fired == [str(admin)], "firing control: .git was swapped right after its verification"
    assert git(worktree, "rev-parse", "HEAD").stdout.decode().strip() == main_head, "the swap redirects plain Git"
    state = collected["receipt"]["checkout"]
    # Every query named the verified administration, so the swap changed nothing collection saw.
    assert state["head"] == prepared.revision and state["git_admin"] == str(admin)
    monkeypatch.setattr(repository, "checkout_git_admin", real)
    gitfile.unlink()
    gitfile.write_bytes(genuine)
    again = collect(checkout.ws, ident, auditor_stopped="finished")
    assert again["receipt"]["checkout"]["head"] == state["head"], "invariance: the genuine .git restored"


def test_release_and_run_judge_head_only_through_the_verified_administration(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    gitfile = exp.worktree / ".git"
    genuine = gitfile.read_bytes()
    gitfile.unlink()
    gitfile.write_text(f"gitdir: {checkout.repo / '.git'}\n")
    # Firing control: through the substitute, plain Git answers the maintainer's HEAD, which is the prompt.
    assert git(exp.worktree, "rev-parse", "HEAD").stdout.decode().strip() == exp.revision
    refused = _reason(release, checkout.ws, checkout.meta["audit_id"], review=support.REVIEW, actor="manager")
    assert refused.reason == "checkout_identity" and "cannot be verified" in str(refused)
    gitfile.unlink()
    gitfile.write_bytes(genuine)
    released = release(checkout.ws, checkout.meta["audit_id"], review=support.REVIEW, actor="manager")
    gitfile.unlink()
    gitfile.write_text(f"gitdir: {checkout.repo / '.git'}\n")
    refused = _reason(run, checkout.ws, checkout.meta["audit_id"], release=released["release"], timeout=60)
    assert refused.reason == "release_invalidated" and "cannot be verified" in str(refused)
    attempt = read_json(Path(refused.retained[0]) / "ATTEMPT.json")
    assert attempt["process"]["launched"] is False, "nothing ran"
