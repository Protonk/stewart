"""Request keys bound to references, locks, resources and resumption, through the installed wheel.

A keyed close whose removal fails stays ``partial`` until it is resumed
explicitly; resource outputs are observed through their own records; a kept
reference is revalidated only when the key's request will execute; ``--ref``
with ``--repo`` must name the reference's repository, and a reference whose
checkout is gone falls back only to checkouts of that repository; an
inspector's shared lock delays a submitter briefly while an executor's lock
makes it ``in_progress``; ``--resume-request`` needs a partial request; a
retry under another implementation hands off to ``request --key`` from the
invoking checkout; and ``close --plan`` exits with the code the close would
earn. Every repository is a disposable fixture whose workspace (``audits/ws``)
has no relation to a real one. Each measured guarantee pairs a firing control
(the condition happened: a removal failed, a lock is held, a checkout is
gone) with a case differing only in the measured property and an invariance
case (records unchanged by a replay, refusal, inspection or plan).
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import threading
import time

import pytest

from stewart import api
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, StewartError
from stewart.close import closed_location
from stewart.workspace import workspace
import stewart_support as support
from stewart_support import response_for, snapshot_tree
from test_close import _failed, _revised_prompt
from test_discovery import Stewart, _assign, _init, _linked, _remove_linked
from test_request_keys import (_cli, _collections, _common, _copy_request, _records, _refusal, _request,
                               _triaged)

pytestmark = pytest.mark.system

IDENT = "one-question"
WS = support.WS


# --- helpers -------------------------------------------------------------------------------------------


def _submit(checkout, key: str, *, stopped: str = "finished", **kwargs) -> dict:
    """A keyed collect of the fixture audit, in process."""
    return api.collect(checkout.ws, IDENT, auditor_stopped=stopped, request_key=key, **kwargs)


def _reserve_collect(checkout, monkeypatch, key: str, **kwargs) -> Path:
    """Publish a collect's binding and interrupt it before it plans anything; returns the request directory."""
    import stewart.collect as collect_module

    def interrupted(*args, **_):
        raise KeyboardInterrupt("synthetic interruption before the collection is planned")

    with monkeypatch.context() as patch:
        patch.setattr(collect_module, "mutable_session", interrupted)
        with pytest.raises(KeyboardInterrupt):
            _submit(checkout, key, **kwargs)
    request = _request(checkout, key)
    assert (request / "REQUEST.json").is_file() and list((request / "attempts").iterdir()) == []
    return request


def _reserve_close(checkout, monkeypatch, key: str, **kwargs) -> Path:
    """Publish a close's binding and interrupt it before it plans anything; returns the request directory."""
    import stewart.close as close_module

    def interrupted(*args, **_):
        raise KeyboardInterrupt("synthetic interruption before the close plans anything")

    with monkeypatch.context() as patch:
        patch.setattr(close_module, "_status_view", interrupted)
        with pytest.raises(KeyboardInterrupt):
            api.close(checkout.ws, IDENT, request_key=key, **kwargs)
    request = _request(checkout, key)
    assert (request / "REQUEST.json").is_file() and list((request / "attempts").iterdir()) == []
    return request


def _lock_available(directory: Path, operation: int) -> bool:
    """Whether a lock of this kind could be taken on the request directory now (released at once)."""
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, operation | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False
    finally:
        os.close(descriptor)


def _files(snapshot: dict[str, str]) -> dict[str, str]:
    """The files (not directories) of a snapshot, for proofs that nothing was recorded."""
    return {path: value for path, value in snapshot.items() if value != "dir"}


def _closing_directory(checkout) -> Path:
    (directory,) = list(closed_location(str(_common(checkout)), checkout.ws, IDENT).iterdir())
    return directory


# --- 1. a close whose removal fails is partial until resumed ---------------------------------------------


def test_keyed_close_whose_checkout_removal_fails_stays_partial_until_resumed(checkout, monkeypatch, run_cmd,
                                                                             tmp_path):
    import stewart.close as close_module
    prepared, _ = _triaged(checkout)
    request = _request(checkout, "close-f")
    calls: list[str] = []

    def failing(parent, name, **kwargs):
        calls.append(name)
        raise OSError(errno.EACCES, "synthetic checkout removal failure", name)

    with monkeypatch.context() as patch:
        patch.setattr(close_module, "_delete_checkout", failing)
        result = api.close(checkout.ws, IDENT, actor="manager", request_key="close-f")
    directory = _closing_directory(checkout)
    # Firing control: the checkout's removal was attempted, failed, and the close kept its failed attempt.
    assert calls == ["worktree"]
    assert result["closed"] is None and result["exit_code"] == EXIT_ATTENTION
    assert [(item["kind"], item["outcome"]) for item in result["failed"]] == [("worktree", "failed")]
    assert "synthetic checkout removal failure" in result["failed"][0]["detail"]
    names = sorted(os.listdir(directory))
    assert "CLOSING.json" in names and "CLOSED.json" not in names
    assert len([name for name in names if name.startswith("CLOSE-ATTEMPT-")]) == 1
    assert prepared.worktree.is_dir() and prepared.session.is_dir()
    # Measured: the request has its planned attempt but no outcome, and says how it resumes.
    assert result["request"]["state"] == "partial" and result["request"]["replayed"] is False
    assert any("--resume-request" in step for step in result["request"]["next_steps"])
    assert not (request / "OUTCOME.json").exists() and len(list((request / "attempts").iterdir())) == 1
    view = api.inspect_request(checkout.repo, "close-f")
    assert view["state"] == "partial" and view["exit_code"] == EXIT_ATTENTION
    assert {item["kind"]: item["availability"] for item in view["outputs"]} == {"closing": "available",
                                                                                "closed": "missing"}

    # A plain retry reports the uncertainty and executes nothing, in process and through the CLI.
    before = {"records": _records(checkout), "worktree": snapshot_tree(prepared.worktree)}
    with monkeypatch.context() as patch:
        patch.setattr(close_module, "_delete_checkout", failing)
        replay = api.close(checkout.ws, IDENT, actor="manager", request_key="close-f")
    assert replay["schema"] == "stewart.request/1" and replay["state"] == "partial" and replay["replayed"]
    assert replay["exit_code"] == EXIT_ATTENTION and "closed" not in replay
    envelope = _cli(run_cmd, checkout, "--workspace", WS, "--request-key", "close-f", "close", "--audit-id", IDENT,
                    "--actor", "manager", allowed=(EXIT_ATTENTION,))
    assert envelope["result"]["state"] == "partial" and envelope["result"]["replayed"]
    assert calls == ["worktree"], "a replayed partial close attempted no removal"
    assert {"records": _records(checkout), "worktree": snapshot_tree(prepared.worktree)} == before

    # Changed property: the explicit resumption finishes the close and records the outcome.
    resumed = api.close(checkout.ws, IDENT, actor="manager", request_key="close-f", resume=True)
    assert resumed["closed"] == str(directory / "CLOSED.json") and resumed["resumed"] is True
    assert resumed["request"] == {"key": "close-f", "state": "completed", "path": str(request), "replayed": False}
    assert not prepared.worktree.exists() and not prepared.session.exists()
    outcome = support.read_json(request / "OUTCOME.json")
    assert outcome["status"] == "completed" and outcome["outputs"][0]["path"] == str(directory / "CLOSING.json")
    assert len(list((request / "attempts").iterdir())) == 2, "the resumption appended an attempt"
    assert api.inspect_request(checkout.repo, "close-f")["state"] == "completed"

    # Invariance: a keyed close whose removal succeeds records its outcome at once, in one attempt.
    other = support.make_checkout(tmp_path / "second", run_cmd)
    _triaged(other)
    done = api.close(other.ws, IDENT, actor="manager", request_key="close-ok")
    other_request = _request(other, "close-ok")
    assert done["closed"] and done["request"]["state"] == "completed" and done["request"]["replayed"] is False
    assert support.read_json(other_request / "OUTCOME.json")["status"] == "completed"
    assert len(list((other_request / "attempts").iterdir())) == 1
    assert api.inspect_request(other.repo, "close-ok")["state"] == "completed"


# --- 2. resource outputs are observed through their own records ------------------------------------------


def test_resource_outputs_report_retired_after_close_or_acknowledgment_and_missing_before(checkout, run_cmd):
    prepared = support.prepared_session(checkout, report=None)
    kept, dropped = (checkout.tmp / "scratch-kept").resolve(), (checkout.tmp / "scratch-dropped").resolve()
    made = {}
    for key, path in (("dir-kept", kept), ("dir-dropped", dropped)):
        envelope = _cli(run_cmd, checkout, "--workspace", WS, "--request-key", key, "resource", "create-directory",
                        "--audit-id", IDENT, "--path", path, "--actor", "manager")
        made[key] = envelope["result"]
        assert made[key]["request"]["state"] == "completed" and path.is_dir()
        outcome = support.read_json(_request(checkout, key) / "OUTCOME.json")
        assert [(item["kind"], item["resource"]) for item in outcome["outputs"]] == [("resource", made[key]["rid"])]

    def outputs(key: str) -> list[tuple]:
        view = _cli(run_cmd, checkout, "request", "--key", key)["result"]
        assert view["state"] == "completed" and view["replayed"] is False
        return [(item["kind"], item["resource"], item["availability"]) for item in view["outputs"]]

    kept_rid, dropped_rid = made["dir-kept"]["rid"], made["dir-dropped"]["rid"]
    # Control: both created directories are available.
    assert outputs("dir-kept") == [("resource", kept_rid, "available")]
    assert outputs("dir-dropped") == [("resource", dropped_rid, "available")]

    # Removed by hand and not acknowledged: missing, never retired.
    dropped.rmdir()
    assert outputs("dir-dropped") == [("resource", dropped_rid, "missing")]
    # The acknowledgment is the record that makes the absence a retirement.
    _cli(run_cmd, checkout, "resource", "acknowledge", "--resource", dropped_rid, "--actor", "manager",
         "--note", "removed by hand")
    assert outputs("dir-dropped") == [("resource", dropped_rid, "retired")]
    assert outputs("dir-kept") == [("resource", kept_rid, "available")], "the other output is unaffected"

    # The owning audit's close claims and retires the remaining directory.
    closed = api.close(checkout.ws, IDENT, actor="manager", abandon=True, reason="the scratch work is done")
    assert {item["rid"]: item["outcome"] for item in closed["resources"]} == {kept_rid: "removed"}
    assert not kept.exists() and not prepared.session.exists()
    assert outputs("dir-kept") == [("resource", kept_rid, "retired")]

    # Invariance: the same keyed request replays its record and recreates nothing.
    records = _records(checkout)
    replay = _cli(run_cmd, checkout, "--workspace", WS, "--request-key", "dir-kept", "resource", "create-directory",
                  "--audit-id", IDENT, "--path", kept, "--actor", "manager")["result"]
    assert replay["schema"] == "stewart.request/1" and replay["state"] == "completed" and replay["replayed"]
    assert [item["availability"] for item in replay["outputs"]] == ["retired"]
    assert not kept.exists() and not dropped.exists() and _records(checkout) == records


# --- 3. revalidation only when the key's request will execute --------------------------------------------


def test_a_stale_reference_is_revalidated_for_a_reserved_key_but_not_for_a_completed_one(checkout, monkeypatch,
                                                                                        run_cmd, tmp_path):
    cli = Stewart(run_cmd, checkout.tmp)
    reason = "preparation failed before any handoff"
    failed = _failed(checkout, monkeypatch)
    old = failed.record["session_uuid"]
    reference = api.select(checkout.repo, audit_id=IDENT)["reference"]
    assert reference["lifetime"] == old
    held = tmp_path / "old-lifetime-ref.json"
    held.write_text(json.dumps(reference))
    reserved = _reserve_collect(checkout, monkeypatch, "collect-r", lifetime=old)
    closed = api.close(checkout.ws, IDENT, actor="manager", abandon=True, reason=reason, lifetime=old,
                       request_key="close-done")
    assert closed["released"] is True and closed["request"]["state"] == "completed"
    again = api.prepare(checkout.ws, _revised_prompt(checkout))
    new = again["session_uuid"]
    # Firing control: the lifetime the reference names was replaced, so the reference itself is stale.
    assert new != old
    assert cli.refused("--ref", held, "status", reason="reference_stale")
    assert api.inspect_request(checkout.repo, "collect-r")["state"] == "reserved"
    records = _records(checkout)

    # A reserved key executes on retry, so its reference is revalidated first; nothing runs.
    refused = cli.refused("--ref", held, "--request-key", "collect-r", "collect", "--auditor-stopped", "finished",
                          reason="reference_stale")
    assert "lifetime" in refused["message"]
    assert _records(checkout) == records and list((reserved / "attempts").iterdir()) == []
    assert not (reserved / "OUTCOME.json").exists() and _collections(checkout) == []
    assert api.inspect_request(checkout.repo, "collect-r")["state"] == "reserved"
    # A new key would execute too: it is revalidated before anything is published under it.
    cli.refused("--ref", held, "--request-key", "collect-new", "collect", "--auditor-stopped", "finished",
                reason="reference_stale")
    assert not _request(checkout, "collect-new").exists() and _records(checkout) == records

    # Changed property: a completed key with the same stale reference answers from its record.
    replay = cli("--ref", held, "--request-key", "close-done", "close", "--actor", "manager", "--abandon",
                 "--reason", reason, allowed=(EXIT_OK, EXIT_ATTENTION))
    assert replay["result"]["schema"] == "stewart.request/1" and replay["result"]["state"] == "completed"
    assert replay["result"]["replayed"] and replay["exit_code"] == closed["exit_code"]
    assert replay["result"]["binding"]["lifetime"] == old
    # Invariance: the replacement lifetime is untouched and nothing was recorded.
    assert _records(checkout) == records and Path(again["session"]).is_dir()
    assert api.status(checkout.ws, IDENT, lifetime=new)["session"]["supported"] is True


# --- 4. --ref with --repo ----------------------------------------------------------------------------------


def test_ref_with_another_repositorys_checkout_is_refused_and_another_maintainer_worktree_is_accepted(
        checkout, run_cmd, tmp_path):
    cli = Stewart(run_cmd, checkout.tmp)
    prepared = support.prepared_session(checkout)
    _submit(checkout, "collect-1")
    held = tmp_path / "ref.json"
    held.write_text(json.dumps(prepared.prepared["reference"]))
    foreign = support.make_checkout(tmp_path / "foreign", run_cmd)
    foreign_common = _common(foreign)
    linked = _linked(checkout, "linked")
    # Control: the reference alone runs from its own checkout.
    own = cli("--ref", held, "status", allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert own["workspace"]["repo"] == str(checkout.repo)
    records = _records(checkout)

    for argv in (("status",), ("request", "--key", "collect-1"),
                 ("--request-key", "collect-x", "collect", "--auditor-stopped", "finished")):
        refused = cli.refused("--repo", foreign.repo, "--ref", held, *argv, reason="reference_mismatch")
        assert str(foreign.repo) in refused["retained"], argv
    assert _records(checkout) == records and not _request(checkout, "collect-x").exists()
    assert not (foreign_common / "stewart").exists(), "nothing was written in the other repository"
    assert _collections(checkout) == [api.inspect_request(checkout.repo, "collect-1")["outputs"][0]["name"]]

    # Changed property: another maintainer worktree of the same repository is accepted and used.
    # A replayed request carries its recorded exit code (the collect earned attention).
    view = cli("--repo", linked, "--ref", held, "request", "--key", "collect-1",
               allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert view["key"] == "collect-1" and view["state"] == "completed"
    # The command runs there: status reaches the session's owner rule, not the reference check.
    elsewhere = cli.refused("--repo", linked, "--ref", held, "status", reason="session_other_maintainer")
    assert str(checkout.repo) in elsewhere["next_steps"][0]
    # Invariance: neither accepted command wrote anything.
    assert _records(checkout) == records


# --- 5. a reference whose checkout is gone ----------------------------------------------------------------


def test_a_gone_reference_checkout_falls_back_to_the_owner_before_the_main_checkout(checkout, run_cmd, tmp_path):
    cli = Stewart(run_cmd, checkout.tmp)
    owner = _linked(checkout, "owner")
    selector = _linked(checkout, "selector")
    prepared = api.prepare(workspace(owner, WS), _assign(checkout, owner, WS, IDENT))
    # Selected while the owner is unavailable, select binds the selecting checkout and still names the owner.
    moved = owner.with_name("owner-moved")
    os.rename(owner, moved)
    try:
        reference = cli("--repo", selector, "--workspace", WS, "select", "--audit-id", IDENT)["result"]["reference"]
    finally:
        os.rename(moved, owner)
    assert (reference["checkout"], reference["owner"]) == (str(selector), str(owner))
    assert reference["lifetime"] == prepared["session_uuid"]
    held = tmp_path / "selector-ref.json"
    held.write_text(json.dumps(reference))
    unowned = tmp_path / "unowned-ref.json"
    unowned.write_text(json.dumps({**reference, "owner": str(tmp_path / "never-a-checkout")}))
    # Control: while the reference's checkout exists, the command runs there (and the owner rule applies).
    cli.refused("--ref", held, "status", reason="session_other_maintainer")

    _remove_linked(checkout, selector)
    records = _records(checkout)
    # The owner is still a checkout of the repository: it is used, so the live session is readable.
    live = cli("--ref", held, "status", allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert live["workspace"]["repo"] == str(owner) and live["session"]["supported"] is True
    # Changed property: without a usable owner the repository's main checkout is used, where the owner rule refuses.
    refused = cli.refused("--ref", unowned, "status", reason="session_other_maintainer")
    assert str(owner) in refused["next_steps"][0]
    assert _records(checkout) == records

    # Once the audit is closed, status needs no owner: both fallbacks read the closed audit.
    api.close(workspace(owner, WS), IDENT, actor="manager", abandon=True, reason="fallback check")
    by_owner = cli("--ref", held, "status", allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    by_main = cli("--ref", unowned, "status", allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert by_owner["schema"] == by_main["schema"] == "stewart.status-closed/2"
    assert by_owner["workspace"]["repo"] == str(owner) and by_main["workspace"]["repo"] == str(checkout.repo)


def test_a_gone_reference_checkout_without_any_fallback_is_refused_naming_repo(tmp_path, run_cmd):
    cli = Stewart(run_cmd, tmp_path)

    def git(*argv, cwd: Path) -> str:
        return run_cmd(["git", *argv], cwd=cwd, check=True).stdout.strip()

    # The repository's Git directory lives inside a checkout of another repository, so its parent is a
    # checkout, but not of the reference's common directory.
    store = (tmp_path / "store").resolve()
    store.mkdir()
    git("init", "-q", "-b", "main", cwd=store)
    separated = (tmp_path / "separated").resolve()
    git("init", "-q", "-b", "main", "--separate-git-dir", str(store / "repo.git"), str(separated), cwd=tmp_path)
    (separated / "input.txt").write_text("committed input\n", encoding="utf-8")
    folder = separated / WS
    folder.mkdir(parents=True)
    (folder / "AUDITOR.md").write_text("Auditor instructions\n", encoding="utf-8")
    (folder / "MAINTAINER.md").write_text("Maintainer instructions\n", encoding="utf-8")
    (folder / "PROMPT.md").write_text("**UNASSIGNED**\n", encoding="utf-8")
    git("add", "--", ".", cwd=separated)
    git("commit", "-qm", "Fixture with a separate Git directory", cwd=separated)
    common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=separated)).resolve()
    assert common == (store / "repo.git").resolve()
    assert Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=store)).resolve() != common
    linked = (tmp_path / "linked").resolve()
    git("worktree", "add", "-q", "-b", "maintainer/linked", str(linked), cwd=separated)
    _init(cli, linked, WS, IDENT)
    reference = cli("--repo", linked, "--workspace", WS, "select", "--audit-id", IDENT)["result"]["reference"]
    assert reference["repository"] == str(common) and Path(reference["repository"]).parent == store
    assert (reference["checkout"], reference["owner"]) == (str(linked), str(linked))
    held = tmp_path / "linked-ref.json"
    held.write_text(json.dumps(reference))
    # Control: the reference binds from its own checkout.
    assert cli("--ref", held, "status", allowed=(EXIT_OK, EXIT_ATTENTION))["result"]["workspace"]["repo"] == \
        str(linked)

    git("worktree", "remove", "--force", str(linked), cwd=separated)
    assert not linked.exists(), "firing control: the reference's checkout, which is also its owner, is gone"
    storage = snapshot_tree(common / "stewart")
    refused = cli.refused("--ref", held, "status", reason="reference_checkout_missing")
    assert str(linked) in refused["retained"]
    assert any("--repo" in step for step in refused["next_steps"])
    assert snapshot_tree(common / "stewart") == storage, "the refusal wrote nothing"
    # Changed property: an explicit --repo naming a checkout of the same repository is used instead.
    view = cli("--repo", separated, "--ref", held, "status", allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert view["workspace"]["repo"] == str(separated)
    # Invariance: the store's own checkout is another repository's, explicitly too.
    cli.refused("--repo", store, "--ref", held, "status", reason="reference_mismatch")
    assert snapshot_tree(common / "stewart") == storage


# --- 6. an inspector's shared lock versus an executor's exclusive one ------------------------------------


def test_a_reader_delays_a_submission_briefly_while_an_executor_makes_it_in_progress(checkout, monkeypatch):
    import stewart.collect as collect_module
    import stewart.request_keys as request_keys
    support.prepared_session(checkout)
    key = "collect-lock"
    request = _reserve_collect(checkout, monkeypatch, key)
    executions: list[float] = []
    real = collect_module._collect

    def counted(*args, **kwargs):
        executions.append(time.monotonic())
        return real(*args, **kwargs)

    monkeypatch.setattr(collect_module, "_collect", counted)
    records = snapshot_tree(request)

    # An executor holds the request exclusively (the test stands in for another process).
    descriptor = os.open(request, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Firing control: what an inspector takes cannot be had now.
        assert _lock_available(request, fcntl.LOCK_SH) is False
        assert api.inspect_request(checkout.repo, key)["state"] == "in_progress"
        started = time.monotonic()
        same = _submit(checkout, key)
        waited = time.monotonic() - started
        conflict = _refusal(_submit, checkout, key, stopped="interrupted")
    finally:
        os.close(descriptor)
    assert same["schema"] == "stewart.request/1" and same["state"] == "in_progress" and same["replayed"]
    assert same["exit_code"] == EXIT_ATTENTION and "collection" not in same
    assert waited >= request_keys._READER_GRACE, "the submitter waited out the reader grace before answering"
    assert conflict.reason == "request_key_conflict" and "differs in: inputs" in str(conflict)
    assert executions == [] and snapshot_tree(request) == records and _collections(checkout) == []
    assert api.inspect_request(checkout.repo, key)["state"] == "reserved", "nothing ran under the held lock"

    # Changed property: a reader holds the lock shared, for less than the grace; the submission waits and runs.
    hold = 1.5
    assert hold < request_keys._READER_GRACE
    locked, released = threading.Event(), []

    def reader():
        handle = os.open(request, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(handle, fcntl.LOCK_SH)
            locked.set()
            time.sleep(hold)
            released.append(time.monotonic())
        finally:
            os.close(handle)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    assert locked.wait(30), "the reader never took its shared lock"
    assert _lock_available(request, fcntl.LOCK_EX) is False, "firing control: the reader holds the lock"
    # Invariance: another inspector reads beside the reader and is not taken for an executor.
    assert api.inspect_request(checkout.repo, key)["state"] == "reserved"
    submitted = time.monotonic()
    result = _submit(checkout, key)
    thread.join(30)
    assert not thread.is_alive() and released and submitted < released[0], "the submission met the held lock"
    assert result["request"] == {"key": key, "state": "completed", "path": str(request), "replayed": False}
    assert len(executions) == 1 and executions[0] >= released[0], "it executed only after the reader finished"
    assert _collections(checkout) == [result["collection"]]
    # Invariance: the completed key now answers from its record.
    again = _submit(checkout, key)
    assert again["state"] == "completed" and again["outputs"][0]["name"] == result["collection"]
    assert len(executions) == 1 and _collections(checkout) == [result["collection"]]


# --- 7. --resume-request needs a partial request ---------------------------------------------------------


def test_resume_request_is_refused_for_a_missing_or_reserved_key(checkout, monkeypatch, run_cmd):
    prepared = support.prepared_session(checkout, report=None)
    reason = "the question was withdrawn"
    closing = ("close", "--audit-id", IDENT, "--actor", "manager", "--abandon", "--reason", reason)

    def close_cli(key: str, *extra: str, allowed) -> dict:
        return _cli(run_cmd, checkout, "--workspace", WS, "--request-key", key, *extra, *closing, allowed=allowed)

    closed_root = closed_location(str(_common(checkout)), checkout.ws, IDENT)
    before = _files(_records(checkout))
    missing = close_cli("close-fresh", "--resume-request", allowed=(EXIT_REFUSED,))
    assert missing["error"]["reason"] == "request_missing"
    fresh = _request(checkout, "close-fresh")
    assert not (fresh / "REQUEST.json").exists(), "nothing was published under the key"
    assert _files(_records(checkout)) == before and not closed_root.exists()
    assert prepared.session.is_dir() and prepared.worktree.is_dir()
    assert _refusal(api.close, checkout.ws, IDENT, actor="manager", abandon=True, reason=reason,
                    request_key="close-fresh", resume=True).reason == "request_missing"
    # The unbound residue is no request: inspection and discovery find nothing under it.
    assert _refusal(api.inspect_request, checkout.repo, "close-fresh").reason == "request_missing"
    assert str(fresh) not in [item["path"] for item in api.discover(checkout.repo)["requests"]]
    assert _files(_records(checkout)) == before

    # A reserved key planned nothing, so there is nothing to resume.
    reserved = _reserve_close(checkout, monkeypatch, "close-r", actor="manager", abandon=True, reason=reason)
    assert api.inspect_request(checkout.repo, "close-r")["state"] == "reserved"
    records = snapshot_tree(reserved)
    refused = close_cli("close-r", "--resume-request", allowed=(EXIT_REFUSED,))
    assert refused["error"]["reason"] == "request_not_resumable"
    assert snapshot_tree(reserved) == records and not closed_root.exists() and prepared.session.is_dir()
    assert api.inspect_request(checkout.repo, "close-r")["state"] == "reserved"

    # Changed property: without the flag the same key runs normally.
    ran = close_cli("close-r", allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert ran["closed"] and ran["request"]["state"] == "completed" and ran["request"]["replayed"] is False
    assert not prepared.session.exists() and not prepared.worktree.exists()
    assert support.read_json(reserved / "OUTCOME.json")["status"] == "completed"
    assert not (fresh / "REQUEST.json").exists(), "the refused fresh key stays unbound"


# --- 8. the retry handoff names request inspection from the invoking checkout -----------------------------


def test_a_retry_under_another_implementation_hands_off_to_request_inspection(checkout, monkeypatch):
    import stewart.implementation as implementation_module
    support.prepared_session(checkout)
    first = _submit(checkout, "impl-k")
    other = hashlib.sha256(b"another Stewart build").hexdigest()
    reserved = _copy_request(checkout, "impl-k", "impl-other", implementation=other, outcome=False)
    same = _copy_request(checkout, "impl-k", "impl-same", implementation=None, outcome=True)
    linked = _linked(checkout, "linked")
    assert support.read_json(reserved / "REQUEST.json")["invoked_from"] == str(checkout.repo)
    calls: list[dict] = []
    real = implementation_module.handoff

    def spy(stamp, arguments):
        offered = real(stamp, arguments)
        calls.append({"stamp": stamp, "arguments": list(arguments), "offered": offered})
        return offered

    monkeypatch.setattr(implementation_module, "handoff", spy)
    records = {path: snapshot_tree(path) for path in (reserved, same)}

    # Control: the same copy under this implementation replays and builds no handoff.
    assert _submit(checkout, "impl-same")["state"] == "completed" and calls == []
    refused = _refusal(_submit, checkout, "impl-other")
    assert refused.reason == "implementation_mismatch"
    (call,) = calls
    assert call["arguments"] == ["--repo", str(checkout.repo), "request", "--key", "impl-other"]
    assert call["stamp"]["package_sha256"] == other
    assert refused.handoff is call["offered"] and refused.handoff["state"] == "unresolved"

    # Changed property: from another maintainer checkout the handoff names that checkout, not the recorded one.
    refused = _refusal(api.collect, workspace(linked, WS), IDENT, auditor_stopped="finished",
                       request_key="impl-other")
    assert refused.reason == "implementation_mismatch"
    assert calls[-1]["arguments"] == ["--repo", str(linked), "request", "--key", "impl-other"]

    # While another process holds the key, the same comparison builds the same handoff.
    descriptor = os.open(reserved, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refused = _refusal(_submit, checkout, "impl-other")
    finally:
        os.close(descriptor)
    assert refused.reason == "implementation_mismatch"
    assert calls[-1]["arguments"] == ["--repo", str(checkout.repo), "request", "--key", "impl-other"]
    assert len(calls) == 3
    # Invariance: no retry executed or recorded anything.
    assert {path: snapshot_tree(path) for path in records} == records
    assert _collections(checkout) == [first["collection"]]


# --- 9. close --plan exits with the code the close would earn --------------------------------------------


def test_close_plan_exits_with_the_refusal_code_then_attention_for_blocked_or_missing_resources(checkout,
                                                                                               run_cmd):
    support.prepared_session(checkout)

    def plan(*extra: str, allowed) -> dict:
        envelope = _cli(run_cmd, checkout, "--workspace", WS, "close", "--audit-id", IDENT, "--plan", *extra,
                        allowed=allowed)
        return envelope["result"]

    def dispositions(planned: dict) -> dict:
        return {item["rid"]: item["disposition"] for item in planned["resources"]}

    gone = (checkout.tmp / "scratch-gone").resolve()
    gone_rid = api.create_directory(checkout.ws, IDENT, path=str(gone), actor="manager")["rid"]
    gone.rmdir()
    records = _records(checkout)
    # A concluded close would refuse (no triage): the refusal's code wins over the missing resource.
    concluded = plan(allowed=(EXIT_REFUSED,))
    assert concluded["audit"]["refusal"]["reason"] == "close_not_concluded"
    assert dispositions(concluded) == {gone_rid: "missing"}
    # An abandon runs its own checks: the uncollected report would make it refuse, as the abandon itself does.
    unready = plan("--abandon", allowed=(EXIT_REFUSED,))
    assert unready["audit"]["refusal"]["reason"] == "uncollected_changes"
    # Changed property: an abandon that discards it would not refuse; the missing resource needs attention.
    abandoned = plan("--abandon", "--discard-uncollected", allowed=(EXIT_ATTENTION,))
    assert abandoned["audit"]["refusal"] is None and dispositions(abandoned) == {gone_rid: "missing"}
    assert _records(checkout) == records, "plans write nothing"

    api.acknowledge(checkout.repo, gone_rid, actor="manager", note="removed by hand")
    clean_abandon = plan("--abandon", "--discard-uncollected", allowed=(EXIT_OK,))
    assert dispositions(clean_abandon) == {gone_rid: "acknowledged"}
    assert plan(allowed=(EXIT_REFUSED,))["audit"]["refusal"]["reason"] == "close_not_concluded"

    collected = api.collect(checkout.ws, IDENT, auditor_stopped="finished")
    api.triage(checkout.ws, IDENT, collection=collected["collection"], response=response_for(collected),
               actor="manager")
    clean = plan(allowed=(EXIT_OK,))
    assert clean["audit"]["refusal"] is None and dispositions(clean) == {gone_rid: "acknowledged"}
    # Invariance: a resource the close would remove is not attention.
    replaced = (checkout.tmp / "scratch-replaced").resolve()
    replaced_rid = api.create_directory(checkout.ws, IDENT, path=str(replaced), actor="manager")["rid"]
    assert dispositions(plan(allowed=(EXIT_OK,))) == {gone_rid: "acknowledged", replaced_rid: "remove"}
    # A directory replaced at the recorded path is blocked.
    os.rename(replaced, replaced.with_name("scratch-replaced.orig"))
    replaced.mkdir()
    records = _records(checkout)
    blocked = plan(allowed=(EXIT_ATTENTION,))
    assert blocked["audit"]["refusal"] is None
    assert dispositions(blocked) == {gone_rid: "acknowledged", replaced_rid: "blocked"}
    assert _records(checkout) == records and replaced.is_dir(), "the plan wrote and removed nothing"


# --- 11. a keyed creation plans its resource identity before writing it (review finding R3) ------------------


@pytest.mark.parametrize("moment", ["before_allocation", "after_start_record"])
def test_an_interrupted_keyed_creation_never_allocates_a_second_resource(checkout, monkeypatch, moment):
    import stewart.holdings as holdings
    common = str(_common(checkout))
    target = (checkout.tmp / "managed-dir").resolve()
    name = "_allocate" if moment == "before_allocation" else "_start"
    real = getattr(holdings, name)

    def interrupted(*args, **kwargs):
        if moment == "after_start_record":
            real(*args, **kwargs)
        raise KeyboardInterrupt(f"synthetic interruption at {name}")

    with monkeypatch.context() as patch:
        patch.setattr(holdings, name, interrupted)
        with pytest.raises(KeyboardInterrupt):
            api.create_directory(checkout.ws, IDENT, path=str(target), actor="manager", request_key="create-once")
    view = api.inspect_request(checkout.repo, "create-once")
    started = holdings.rids(common)
    assert not target.exists()
    if moment == "before_allocation":
        # Control: nothing was planned or written, so the request is reserved and its retry runs once.
        assert view["state"] == "reserved" and started == []
        made = api.create_directory(checkout.ws, IDENT, path=str(target), actor="manager", request_key="create-once")
        assert made["request"]["state"] == "completed" and holdings.rids(common) == [made["rid"]]
        assert target.is_dir()
        replay = api.create_directory(checkout.ws, IDENT, path=str(target), actor="manager",
                                      request_key="create-once")
        assert replay["replayed"] and holdings.rids(common) == [made["rid"]]
        return
    # Firing control: the start record exists, and the request planned that very identity before writing it.
    (rid,) = started
    assert (Path(holdings.load(common, rid)["path"]) / "CREATE.json").is_file()
    assert view["state"] == "partial" and [item.get("resource") for item in view["outputs"]] == [rid]
    records = snapshot_tree(_common(checkout) / "stewart")
    # Measured: the same key never allocates another identity; the uncertainty is returned, never replayed.
    for _ in range(2):
        retry = api.create_directory(checkout.ws, IDENT, path=str(target), actor="manager",
                                     request_key="create-once")
        assert retry["schema"] == "stewart.request/1" and retry["state"] == "partial" and retry["replayed"]
    assert holdings.rids(common) == [rid] and not target.exists()
    assert snapshot_tree(_common(checkout) / "stewart") == records, "a replayed partial request writes nothing"


# --- 12. a close plan runs the close's own checks (review finding R4) ------------------------------------------


def _agree(checkout, ident: str, **mode) -> str | None:
    """The plan's refusal for this close mode, asserted equal to the refusal the close itself raises.

    Only refusing modes are closed here; a mode the plan accepts is returned None without closing.
    """
    records = snapshot_tree(_common(checkout) / "stewart")
    planned = api.close_plan(checkout.ws, ident, **{key: value for key, value in mode.items() if key != "reason"})
    assert snapshot_tree(_common(checkout) / "stewart") == records, "a plan writes nothing"
    refusal = planned["audit"]["refusal"]
    if refusal is None:
        return None
    with pytest.raises(StewartError) as raised:
        api.close(checkout.ws, ident, actor="manager", **mode)
    assert raised.value.reason == refusal["reason"], (refusal, raised.value)
    assert raised.value.exit_code == refusal["exit_code"]
    assert snapshot_tree(_common(checkout) / "stewart") == records, "the refused close writes nothing either"
    return refusal["reason"]


def test_a_close_plan_reports_the_refusal_its_close_raises(checkout):
    # A draft-only audit: a concluded close refuses it; its abandon is planned without refusal.
    draft = "draft-only-question"
    api.create_directory(checkout.ws, draft, path=str((checkout.tmp / "draft-dir").resolve()), actor="manager")
    assert _agree(checkout, draft) == "session_missing"
    assert _agree(checkout, draft, abandon=True, reason="drafted only") is None

    support.prepared_session(checkout)
    # Firing control: the prepared checkout holds report bytes no collection captured.
    assert _agree(checkout, IDENT, abandon=True, reason="stopping") == "uncollected_changes"
    # Changed property: deciding to discard them, the abandon is planned without refusal.
    assert _agree(checkout, IDENT, abandon=True, reason="stopping", discard_uncollected=True) is None
    # A concluded close of the same session refuses until a complete collection is triaged.
    assert _agree(checkout, IDENT) == "close_not_concluded"

    collected = api.collect(checkout.ws, IDENT, auditor_stopped="finished")
    # Invariance: once collected, the abandon is planned without refusal and the close itself proceeds.
    assert _agree(checkout, IDENT, abandon=True, reason="stopping") is None
    api.triage(checkout.ws, IDENT, collection=collected["collection"], response=response_for(collected),
               actor="manager")
    assert _agree(checkout, IDENT, collection="not-the-triaged-collection") == "action_stale"
    assert _agree(checkout, IDENT) is None
    closed = api.close(checkout.ws, IDENT, actor="manager")
    assert closed["closed"] is not None and closed["exit_code"] == EXIT_OK


@pytest.mark.parametrize("abandon,discard,reason", [(False, False, None), (False, True, None),
                                                   (False, False, "done"), (True, True, None),
                                                   (True, False, "done")])
def test_close_plan_checks_mode_without_requiring_actor_or_rationale(checkout, run_cmd, abandon, discard, reason):
    _triaged(checkout)
    records = snapshot_tree(_common(checkout) / "stewart")
    mode = {"abandon": abandon, "discard_uncollected": discard, "reason": reason}
    plan = api.close_plan(checkout.ws, IDENT, **mode)
    flags = (["--abandon"] if abandon else []) + (["--discard-uncollected"] if discard else [])
    flags += ["--reason", reason] if reason is not None else []
    incompatible = not abandon and (discard or reason is not None)
    expected = EXIT_REFUSED if incompatible else EXIT_OK
    shown = _cli(run_cmd, checkout, "--workspace", WS, "close", "--audit-id", IDENT, "--plan", *flags,
                 allowed=(expected,))["result"]
    assert shown["audit"]["refusal"] == plan["audit"]["refusal"]
    assert shown["audit"]["state"] == plan["audit"]["state"] == "live"
    assert snapshot_tree(_common(checkout) / "stewart") == records, "both plans are read-only"
    if incompatible:
        assert plan["audit"]["refusal"]["reason"] == "usage"
        with pytest.raises(StewartError) as raised:
            api.close(checkout.ws, IDENT, actor="manager", **mode)
        assert raised.value.reason == "usage" and raised.value.exit_code == expected
        assert snapshot_tree(_common(checkout) / "stewart") == records
    else:
        # Dropping discard or choosing abandon is enough; planning never needed actor or rationale.
        assert plan["audit"]["refusal"] is None
        result = api.close(checkout.ws, IDENT, actor="manager", **{**mode, "reason": "done" if abandon else None})
        assert result["closed"] and result["exit_code"] == EXIT_OK
