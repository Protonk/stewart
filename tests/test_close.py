"""Closing an audit: one kept record, then removal of exactly what the session recorded.

A concluded close needs records that verify and a triaged, unchanged
checkout; an abandon is allowed in any state. Either writes CLOSING.json
before removing anything and CLOSED.json after. An abandoned audit ID is
released only when no chain of evidence can exist under it, and init and
prepare reapply that rule to the recorded basis.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import threading
from types import SimpleNamespace

import pytest

from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, EXIT_UNVERIFIED, StewartError
from stewart._git import git, git_text
from stewart.close import close, closed_location
from stewart.collect import collect
from stewart.prepare import prepare
from stewart.session import PREPARE_STAGES
from stewart.status import status, status_list
from stewart.triage import triage
import stewart_support as support
from stewart_support import response_for

pytestmark = pytest.mark.system

IDENT = "one-question"


def _common(checkout) -> Path:
    return Path(git_text(checkout.repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))


def _refs(checkout, uuid: str) -> list[str]:
    return git_text(checkout.repo, "for-each-ref", "--format=%(refname)", f"refs/stewart/sessions/{uuid}/").split()


def _row(checkout, uuid: str) -> Path:
    return _common(checkout) / "stewart/worktree-roles" / f"{uuid}.json"


def _triaged(checkout, *, mode: str = "snapshot"):
    prepared = support.prepared_session(checkout, mode=mode)
    collected = collect(checkout.ws, IDENT, auditor_stopped="finished")
    triage(checkout.ws, IDENT, collection=collected["collection"], response=response_for(collected), actor="manager")
    return prepared, collected


def _second_audit(checkout, ident: str = "other-question"):
    checkout.meta["audit_id"] = ident
    checkout.meta["report_path"] = checkout.ws.report_path(ident)
    prepared = prepare(checkout.ws, checkout.prompt_commit())
    checkout.meta["audit_id"] = IDENT
    checkout.meta["report_path"] = checkout.ws.report_path(IDENT)
    return prepared


def _failed(checkout, monkeypatch, *, stage: str = "worktree", revision: str | None = None):
    """Fail a preparation at ``stage``, leaving its receipt and partial state as prepare does."""
    import stewart.prepare as prepare_module
    revision = revision or checkout.prompt_commit()
    real_git, real_runtime = prepare_module.git, prepare_module.retain_runtime

    def failing_git(repo, *args, **kwargs):
        if stage == "worktree" and args[:2] == ("worktree", "add"):
            raise StewartError("synthetic Git administration denial", reason="git_failed")
        return real_git(repo, *args, **kwargs)

    def failing_runtime(*args, **kwargs):
        raise StewartError("synthetic runtime failure", reason="runtime_assets")

    with monkeypatch.context() as patch:
        patch.setattr(prepare_module, "git", failing_git)
        if stage == "runtime":
            patch.setattr(prepare_module, "retain_runtime", failing_runtime)
        with pytest.raises(StewartError) as refused:
            prepare(checkout.ws, revision)
    assert refused.value.reason == "prepare_failed"
    session = support.session_path(checkout, IDENT)
    record = support.read_json(session / "session.json")
    assert support.read_json(session / "PREPARE-ERROR.json")["stage"] == stage
    return SimpleNamespace(session=session, record=record, revision=revision,
                           worktree=Path(record["worktree"]), next_steps=refused.value.next_steps)


def _revised_prompt(checkout) -> str:
    """Another prompt-only commit that carries the same assignment."""
    text = support.assignment_text(checkout.meta, extra_sections={"Evidence": "The input, re-read after the failure."})
    return checkout.prompt_commit(text=text)


def _reason(callable_, *args, **kwargs) -> StewartError:
    with pytest.raises(StewartError) as refused:
        callable_(*args, **kwargs)
    return refused.value


@pytest.mark.heavy
def test_concluded_close_removes_exactly_the_recorded_inventory(checkout):
    prepared, _ = _triaged(checkout)
    other = _second_audit(checkout)
    uuid = prepared.prepared["session_uuid"]
    audit_dir = Path(prepared.prepared["audit_dir"])
    other_before = {"refs": _refs(checkout, other["session_uuid"]), "status": status(checkout.ws, "other-question")}
    assert _refs(checkout, uuid) and _row(checkout, uuid).is_file(), "control: the inventory exists before close"
    # Control: an entry no session record names is left in place and named.
    stray = audit_dir / "manager-notes.txt"
    stray.write_text("not the session's\n")

    result = close(checkout.ws, IDENT, actor="manager")

    assert result["mode"] == "concluded" and result["released"] is False
    assert result["leftovers"] == [str(stray)] and result["exit_code"] == EXIT_ATTENTION
    assert not prepared.worktree.exists() and not prepared.session.exists()
    assert not Path(prepared.prepared["runtime"]["root"]).exists()
    assert str(prepared.worktree) not in git_text(checkout.repo, "worktree", "list", "--porcelain")
    assert _refs(checkout, uuid) == [] and not _row(checkout, uuid).exists()
    assert stray.read_text() == "not the session's\n" and audit_dir.is_dir()
    closing = support.read_json(Path(result["closing"]))
    closed = support.read_json(Path(result["closed"]))
    assert closing["acknowledged"] == {"actor": "manager", "mode": "concluded", "reason": None}
    assert closing["attributed"]["decision"] == "No action; retain the report."
    assert closing["observed"]["triage"]["sha256"] and closing["observed"]["collection"]["sha256"]
    outcomes = {(item["kind"], item["item"]): item["outcome"] for item in closed["results"]}
    assert outcomes[("checkout directory", str(audit_dir))] == "kept: not empty"
    assert {kind for (kind, _), outcome in outcomes.items() if outcome == "removed"} == {
        "worktree", "checkout member", "retention ref", "registry row", "session"}
    assert "A partial report." not in json.dumps(closing), "report bytes stay out of the closing record"
    # Control: the other live session is untouched.
    assert _refs(checkout, other["session_uuid"]) == other_before["refs"]
    assert _row(checkout, other["session_uuid"]).is_file() and Path(other["worktree"]).is_dir()
    assert status(checkout.ws, "other-question") == other_before["status"]
    # Invariance: the closed view repeats exactly.
    first, second = status(checkout.ws, IDENT), status(checkout.ws, IDENT)
    assert first == second and first["audit_id_state"] == "reserved"
    assert [item["reason"] for item in first["attention"]] == ["close_leftovers"]
    stray.unlink()
    assert status(checkout.ws, IDENT)["exit_code"] == EXIT_OK, "a removed leftover is no longer news"
    # A concluded close always reserves the ID, for init and prepare alike.
    refused = _reason(prepare, checkout.ws, _revised_prompt(checkout))
    assert refused.reason == "audit_id_reserved" and refused.exit_code == EXIT_REFUSED
    from stewart.assignment import initialize
    refused = _reason(initialize, checkout.ws, IDENT, checkout.meta["target_commit"], inputs=["input.txt"])
    assert refused.reason == "audit_id_reserved"


def test_concluded_close_refuses_until_the_audit_is_finished(checkout):
    prepared = support.prepared_session(checkout)
    refused = _reason(close, checkout.ws, IDENT, actor="manager")
    assert refused.reason == "close_not_concluded" and refused.exit_code == EXIT_REFUSED
    assert prepared.session.is_dir() and not closed_location(str(_common(checkout)), checkout.ws, IDENT).exists()
    collected = collect(checkout.ws, IDENT, auditor_stopped="finished")
    triage(checkout.ws, IDENT, collection=collected["collection"], response=response_for(collected), actor="manager")
    # Measured: a write after the triaged collection is refused; nothing is removed.
    late = prepared.worktree / "late-note.txt"
    late.write_text("written after collection\n")
    refused = _reason(close, checkout.ws, IDENT, actor="manager")
    assert refused.reason == "checkout_changed" and str(prepared.worktree) in refused.retained
    assert late.exists() and prepared.session.is_dir()
    assert not closed_location(str(_common(checkout)), checkout.ws, IDENT).exists()
    # Control: the same checkout, unchanged since a fresh triaged collection, closes.
    collected = collect(checkout.ws, IDENT, auditor_stopped="finished")
    triage(checkout.ws, IDENT, collection=collected["collection"], response=response_for(collected), actor="manager")
    assert close(checkout.ws, IDENT, actor="manager")["exit_code"] == EXIT_OK


def test_concluded_close_refuses_with_3_where_status_returns_3(checkout, capsys):
    from stewart.cli import main
    prepared, collected = _triaged(checkout)
    launches = prepared.session / "launches"
    launches.mkdir(mode=0o700, exist_ok=True)
    (launches / "20260101T000000-deadbeef.json").write_text("not json")
    assert status(checkout.ws, IDENT)["exit_code"] == EXIT_UNVERIFIED
    argv = ["--repo", str(checkout.repo), "--workspace", checkout.ws.rel, "close", "--audit-id", IDENT,
            "--actor", "manager"]
    assert main(argv) == EXIT_UNVERIFIED
    assert "close_unverified" in capsys.readouterr().err and prepared.session.is_dir()
    # Abandoning stays available and records what it observed.
    assert main([*argv, "--abandon", "--reason", "launch record corrupted"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "Closed (abandoned)" in out and "reserved" in out
    view = status(checkout.ws, IDENT)
    assert view["closes"][0]["reason"] == "launch record corrupted"
    closing = support.read_json(Path(view["closes"][0]["path"]) / "CLOSING.json")
    assert "record_corrupt" in closing["observed"]["problems"]


def test_close_refusals_name_their_reason(checkout, capsys):
    from stewart.cli import main
    base = ["--repo", str(checkout.repo), "--workspace", checkout.ws.rel, "close", "--audit-id", IDENT,
            "--actor", "manager"]
    assert main(base) == EXIT_REFUSED and "session_missing" in capsys.readouterr().err
    support.prepared_session(checkout, report=None)
    for extra, reason in ((["--reason", "why"], "usage"), (["--discard-uncollected"], "usage"),
                          (["--abandon"], "reason_required"), (["--abandon", "--reason", " "], "reason_required")):
        assert main([*base, *extra]) == EXIT_REFUSED
        assert f"({reason})" in capsys.readouterr().err
    assert status(checkout.ws, IDENT)["schema"] != "stewart.status-closed/1", "control: nothing was closed"


def test_interrupted_close_finishes_from_its_recorded_inventory(checkout, monkeypatch):
    import stewart.close as close_module
    prepared, _ = _triaged(checkout)
    uuid = prepared.prepared["session_uuid"]
    real = close_module.git

    def interrupt(repo, *args, **kwargs):
        if args[:2] == ("worktree", "remove"):
            raise StewartError("synthetic interruption of the checkout removal", reason="git_failed")
        return real(repo, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(close_module, "git", interrupt)
        first = close(checkout.ws, IDENT, actor="manager")
    directory = Path(first["closing"]).parent
    assert first["closed"] is None and first["exit_code"] == EXIT_ATTENTION
    assert [item["kind"] for item in first["results"]] == ["worktree"], "removal stops at the first failure"
    assert [item["kind"] for item in first["failed"]] == ["worktree"] and prepared.session.is_dir()
    assert len(list(directory.glob("CLOSE-ATTEMPT-*.json"))) == 1 and not (directory / "CLOSED.json").exists()
    view = status(checkout.ws, IDENT)
    assert view["audit_id_state"] == "close_incomplete" and view["exit_code"] == EXIT_ATTENTION
    assert [action["action"] for action in view["next_actions"]] == ["close"]
    listing = status_list(checkout.ws)
    assert [(entry["audit_id"], entry["audit_id_state"]) for entry in listing["sessions"]] == [(IDENT, "close_incomplete")]
    assert listing["exit_code"] == EXIT_ATTENTION, "an unfinished close counts in the listing"
    assert _reason(prepare, checkout.ws, prepared.revision).reason == "close_incomplete"
    # Entries that appear after interruption are outside the recorded inventory.
    late_ref = f"refs/stewart/sessions/{uuid}/late"
    git(checkout.repo, "update-ref", late_ref, prepared.revision)
    late_file = Path(prepared.prepared["audit_dir"]) / "late.txt"
    late_file.write_text("after interruption\n")
    second = close(checkout.ws, IDENT, actor="someone else")
    assert second["resumed"] is True and second["closed"] and not prepared.session.exists()
    assert second["leftovers"] == sorted([str(late_file), f"ref {late_ref}"]) and late_file.exists()
    assert _refs(checkout, uuid) == [late_ref], "a rerun never widens the recorded inventory"
    closing = support.read_json(directory / "CLOSING.json")
    assert closing["acknowledged"]["actor"] == "manager", "the rerun keeps the original acknowledgment"
    assert status(checkout.ws, IDENT)["audit_id_state"] == "reserved"


def test_abandoning_a_clean_failure_releases_the_audit_id(checkout, monkeypatch):
    failed = _failed(checkout, monkeypatch)
    assert any("close --audit-id" in step for step in failed.next_steps)
    view = status(checkout.ws, IDENT)
    assert view["exit_code"] == EXIT_ATTENTION and [item["reason"] for item in view["attention"]] == ["prepare_failed"]
    assert [action["action"] for action in view["next_actions"]][:1] == ["close"]
    assert "--abandon" in view["next_actions"][0]["argv"]
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="Git administration was denied")
    assert result["released"] is True and result["exit_code"] == EXIT_OK
    assert not failed.session.exists() and _refs(checkout, failed.record["session_uuid"]) == []
    closed_view = status(checkout.ws, IDENT)
    assert closed_view["audit_id_state"] == "released" and closed_view["exit_code"] == EXIT_OK
    assert closed_view["next_actions"][0]["action"] == "prepare"
    # 3b: any prompt commit that carries the assignment may be prepared again.
    again = prepare(checkout.ws, _revised_prompt(checkout))
    assert again["session_uuid"] != failed.record["session_uuid"]
    live = status(checkout.ws, IDENT)
    assert live["schema"] != closed_view["schema"] and live["exit_code"] == EXIT_OK
    assert [item["mode"] for item in live["closes"]] == ["abandoned"], "the earlier attempt is listed beside it"


BLOCKERS = ["none", "private_handoff", "public_handoff", "launch_record", "launches_not_a_directory", "message",
            "exit_record", "collection", "checkout_extra", "checkout_empty_directory", "failure_receipt_missing",
            "failure_stage_missing", "checkout_unobservable"]


@pytest.mark.parametrize("blocker", BLOCKERS)
def test_each_release_blocker_alone_keeps_the_audit_id_reserved(checkout, monkeypatch, blocker):
    failed = _failed(checkout, monkeypatch, stage="runtime")
    session, worktree = failed.session, failed.worktree
    assert worktree.is_dir(), "a runtime-stage failure leaves the checkout for the footprint comparison"
    if blocker == "private_handoff":
        (session / "LAUNCH.md").write_text("handoff\n")
    elif blocker == "public_handoff":
        handoff = worktree / failed.record["handoff"]["path"]
        handoff.parent.mkdir(parents=True, exist_ok=True)
        handoff.write_text("handoff\n")
    elif blocker == "launch_record":
        (session / "launches").mkdir(mode=0o700)
        (session / "launches" / "20260101T000000-deadbeef.json").write_text("{}")
    elif blocker == "launches_not_a_directory":
        (session / "launches").write_text("not a directory, so its records cannot be counted\n")
    elif blocker == "message":
        (session / "messages").mkdir(mode=0o700)
        (session / "messages" / "20260101T000000-deadbeef.json").write_text("{}")
    elif blocker == "exit_record":
        (session / "HARNESS-EXIT.txt").write_text("0 2026-01-01T00:00:00Z\n")
    elif blocker == "collection":
        (session / "collections" / "20260101T000000-deadbeef").mkdir(parents=True)
    elif blocker == "checkout_extra":
        (worktree / "extra.txt").write_text("not preparation's\n")
    elif blocker == "checkout_empty_directory":
        (worktree / "made-by-someone").mkdir()
    elif blocker == "failure_stage_missing":
        failure = session / "PREPARE-ERROR.json"
        document = json.loads(failure.read_text())
        del document["stage"]
        failure.chmod(stat.S_IRUSR | stat.S_IWUSR)
        failure.write_text(json.dumps(document))
    elif blocker == "checkout_unobservable":
        (worktree / "input.txt").chmod(0)
    elif blocker == "failure_receipt_missing":
        # A crashed prepare leaves no receipt; it looks like one still running.
        (session / "PREPARE-ERROR.json").rename(checkout.tmp / "moved-aside.json")
    try:
        result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason=f"blocker {blocker}",
                       discard_uncollected=blocker in ("checkout_extra", "checkout_unobservable"))
    finally:
        if blocker == "checkout_unobservable" and (worktree / "input.txt").exists():
            (worktree / "input.txt").chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert result["released"] is (blocker == "none")
    revision = _revised_prompt(checkout)
    if blocker == "none":
        assert prepare(checkout.ws, revision)["audit_id"] == IDENT
    else:
        refused = _reason(prepare, checkout.ws, revision)
        assert refused.reason == "audit_id_reserved" and refused.retained and refused.next_steps


def test_reuse_reapplies_the_rule_and_fails_closed(checkout, monkeypatch):
    from stewart import _util
    failed = _failed(checkout, monkeypatch)
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="clean failure")
    assert result["released"]
    closing, closed = Path(result["closing"]), Path(result["closed"])
    originals = {closing: closing.read_bytes(), closed: closed.read_bytes()}
    for location in originals:
        location.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def rewrite(data: bytes, *, bind: bool = True) -> None:
        closing.write_bytes(data)
        document = json.loads(originals[closed])
        if bind:
            document["closing_sha256"] = _util.sha256_bytes(data)
        closed.write_bytes(json.dumps(document).encode())

    revision = _revised_prompt(checkout)
    # A recorded basis that no longer satisfies the rule keeps the ID reserved,
    # even when CLOSED.json binds it: reuse reapplies the rule.
    document = json.loads(originals[closing])
    document["observed"]["release_basis"]["collections"] = 1
    rewrite(json.dumps(document).encode())
    assert _reason(prepare, checkout.ws, revision).reason == "audit_id_reserved"
    assert status(checkout.ws, IDENT)["audit_id_state"] == "reserved"
    unsupported = json.dumps({**json.loads(originals[closing]), "schema": "stewart.closing/0"}).encode()
    repeated = originals[closing].replace(b'"acknowledged"', b'"acknowledged": {}, "acknowledged"', 1)
    for data, bind in ((b"not json", True), (unsupported, True), (repeated, True), (originals[closing] + b" ", False)):
        rewrite(data, bind=bind)
        refused = _reason(prepare, checkout.ws, revision)
        assert refused.reason == "closing_record_invalid" and refused.exit_code == EXIT_UNVERIFIED
        assert str(closing.parent) in refused.retained
        view = status(checkout.ws, IDENT)
        assert view["audit_id_state"] == "unverified" and view["exit_code"] == EXIT_UNVERIFIED
    # Control: the intact pair releases again.
    for location, data in originals.items():
        location.write_bytes(data)
    assert prepare(checkout.ws, revision)["audit_id"] == IDENT
    assert failed.record["session_uuid"] in json.dumps(status(checkout.ws, IDENT)["closes"])


def test_racing_prepares_on_a_released_id_admit_one(checkout, monkeypatch):
    import stewart.prepare as prepare_module
    _failed(checkout, monkeypatch)
    assert close(checkout.ws, IDENT, actor="manager", abandon=True, reason="clean failure")["released"]
    revision = _revised_prompt(checkout)
    real = prepare_module.require_fresh_audit_id
    gate = threading.Barrier(2, timeout=30)

    def both_pass(*args):
        real(*args)
        gate.wait()

    monkeypatch.setattr(prepare_module, "require_fresh_audit_id", both_pass)
    outcomes: list = []

    def attempt():
        try:
            outcomes.append(prepare(checkout.ws, revision)["session_uuid"])
        except StewartError as exc:
            outcomes.append(exc.reason)

    workers = [threading.Thread(target=attempt) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(120)
    assert sorted(outcome == "destination_exists" for outcome in outcomes) == [False, True]
    assert status(checkout.ws, IDENT)["exit_code"] == EXIT_OK


def test_abandon_refuses_to_discard_uncollected_changes_unless_told(checkout):
    prepared = support.prepared_session(checkout, report="A report nobody collected.\n")
    refused = _reason(close, checkout.ws, IDENT, actor="manager", abandon=True, reason="stopping")
    assert refused.reason == "uncollected_changes" and str(prepared.worktree) in refused.retained
    assert checkout.meta["report_path"] in str(refused) and prepared.report.exists()
    # Invariance: changes a collection captured are preserved there and need no flag.
    collect(checkout.ws, IDENT, auditor_stopped="interrupted")
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="stopping")
    closing = support.read_json(Path(result["closing"]))
    assert closing["observed"]["discarded"] == [] and not prepared.worktree.exists()


def test_discarded_changes_are_listed_with_their_digests(checkout):
    from stewart import _util
    prepared = support.prepared_session(checkout, report="A report nobody collected.\n")
    data = prepared.report.read_bytes()
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="stopping", discard_uncollected=True)
    closing = support.read_json(Path(result["closing"]))
    assert closing["observed"]["discarded"] == [{"path": checkout.meta["report_path"], "sha256": _util.sha256_bytes(data)}]
    assert result["released"] is False, "a prepared session's handoff keeps its ID reserved"


@pytest.mark.parametrize("mode", ["paused", "snapshot"])
def test_closing_a_paused_session_releases_no_hold(checkout, capsys, mode):
    from stewart.cli import main
    support.prepared_session(checkout, mode=mode, report=None)
    argv = ["--repo", str(checkout.repo), "--workspace", checkout.ws.rel, "close", "--audit-id", IDENT,
            "--actor", "manager", "--abandon", "--reason", "cancelled"]
    assert main(argv) == EXIT_OK
    out = capsys.readouterr().out
    assert ("tell the writers" in out) is (mode == "paused")
    view = status(checkout.ws, IDENT)
    closing = support.read_json(Path(view["closes"][0]["path"]) / "CLOSING.json")
    assert closing["observed"]["coordination"] == {"mode": mode, "hold_resumed": False}


def test_listing_includes_closed_audits(checkout, monkeypatch):
    _failed(checkout, monkeypatch)
    close(checkout.ws, IDENT, actor="manager", abandon=True, reason="clean failure")
    _second_audit(checkout)
    listing = status_list(checkout.ws)
    entries = {entry["audit_id"]: entry for entry in listing["sessions"]}
    assert set(entries) == {IDENT, "other-question"} and listing["exit_code"] == EXIT_OK
    assert entries[IDENT]["closed"] is True and entries[IDENT]["audit_id_state"] == "released"
    assert "closed" not in entries["other-question"]


@pytest.mark.parametrize("stage", ["worktree", "runtime", "handoff"])
def test_failed_preparation_is_attention_unless_its_records_fail_to_verify(checkout, monkeypatch, stage):
    import stewart.prepare as prepare_module
    if stage == "handoff":
        real = prepare_module.write_exclusive

        def fail_launch(path, data, **kwargs):
            if Path(path).name == "LAUNCH.md":
                raise OSError("synthetic handoff failure")
            return real(path, data, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(prepare_module, "write_exclusive", fail_launch)
            with pytest.raises(StewartError):
                prepare(checkout.ws, checkout.prompt_commit())
        session = support.session_path(checkout, IDENT)
    else:
        session = _failed(checkout, monkeypatch, stage=stage).session
    view = status(checkout.ws, IDENT)
    assert [item["reason"] for item in view["attention"]] == ["prepare_failed"], "never-written records are the failure"
    assert view["exit_code"] == EXIT_ATTENTION
    if stage == "handoff":
        # Measured: records a reached stage wrote are still verified.
        (session / "RUNTIME-PREPARED.json").rename(checkout.tmp / "moved-aside.json")
        assert status(checkout.ws, IDENT)["exit_code"] == EXIT_UNVERIFIED


def test_prepare_stage_names_match_the_recorded_order():
    import stewart.prepare as prepare_module
    source = Path(prepare_module.__file__).read_text(encoding="utf-8")
    assert tuple(re.findall(r'^\s+stage = "([a-z_]+)"$', source, flags=re.M)) == PREPARE_STAGES


def test_close_help_states_both_modes_and_the_kept_record(capsys):
    from stewart.cli import main
    with pytest.raises(SystemExit):
        main(["close", "--help"])
    text = " ".join(capsys.readouterr().out.split())
    for phrase in ("--abandon", "Closing records are never removed", "export first", "tell the writers",
                   "every doubt keeps it reserved"):
        assert phrase in text


def test_a_lost_session_is_abandoned_through_its_registry_row(checkout):
    import shutil
    prepared = support.prepared_session(checkout, report=None)
    uuid = prepared.prepared["session_uuid"]
    shutil.rmtree(prepared.session)
    refused = _reason(close, checkout.ws, IDENT, actor="manager")
    assert refused.reason == "session_missing", "control: a concluded close needs the session"
    # Without its record there is no prompt commit to compare the checkout with.
    refused = _reason(close, checkout.ws, IDENT, actor="manager", abandon=True, reason="session records were lost")
    assert refused.reason == "uncollected_changes" and prepared.worktree.is_dir()
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="session records were lost",
                   discard_uncollected=True)
    assert result["closed"] and result["released"] is False
    assert not prepared.worktree.exists() and _refs(checkout, uuid) == [] and not _row(checkout, uuid).exists()
    closing = support.read_json(Path(result["closing"]))
    assert closing["identity"]["session_sha256"] is None and closing["observed"]["release_basis"]["failure_receipt"]["kind"] == "missing"
    assert _reason(prepare, checkout.ws, _revised_prompt(checkout)).reason == "audit_id_reserved"


def test_finished_closes_never_count_in_the_listing(checkout):
    prepared, _ = _triaged(checkout)
    stray = Path(prepared.prepared["audit_dir"]) / "stray.txt"
    stray.write_text("left behind\n")
    close(checkout.ws, IDENT, actor="manager")
    assert status(checkout.ws, IDENT)["exit_code"] == EXIT_ATTENTION, "the targeted view names the leftover"
    listing = status_list(checkout.ws)
    assert listing["exit_code"] == EXIT_OK and listing["sessions"][0]["exit_code"] == EXIT_OK


def test_close_never_follows_or_removes_refs_it_did_not_record(checkout):
    prepared = support.prepared_session(checkout, report=None)
    uuid = prepared.prepared["session_uuid"]
    main = git_text(checkout.repo, "rev-parse", "refs/heads/main")
    planted = f"refs/stewart/sessions/{uuid}/notes"
    git(checkout.repo, "symbolic-ref", planted, "refs/heads/main")
    unrecorded = f"refs/stewart/sessions/{uuid}/extra"
    git(checkout.repo, "update-ref", unrecorded, prepared.revision)
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="planted refs")
    # Measured: the symbolic ref is kept and named, never followed to its target.
    assert git_text(checkout.repo, "rev-parse", "refs/heads/main") == main
    assert f"ref {planted}" in result["leftovers"] and f"ref {unrecorded}" in result["leftovers"]
    assert result["exit_code"] == EXIT_ATTENTION
    # Control: the recorded retention refs are removed.
    assert sorted(_refs(checkout, uuid)) == sorted([planted, unrecorded])
    closing = support.read_json(Path(result["closing"]))
    assert {entry["ref"] for entry in closing["removal"]["refs"]} == {
        f"refs/stewart/sessions/{uuid}/prompt", f"refs/stewart/sessions/{uuid}/target"}
    view = status(checkout.ws, IDENT)
    assert view["exit_code"] == EXIT_ATTENTION and f"ref {planted}" in view["closes"][0]["leftovers"]
    git(checkout.repo, "update-ref", "--no-deref", "-d", planted)
    git(checkout.repo, "update-ref", "-d", unrecorded)
    assert status(checkout.ws, IDENT)["exit_code"] == EXIT_OK, "leftovers are observed at read time"


def test_abandon_refuses_when_the_checkout_cannot_be_observed(checkout):
    prepared = support.prepared_session(checkout, report="A report nobody collected.\n")
    (prepared.worktree / "input.txt").chmod(0)
    try:
        refused = _reason(close, checkout.ws, IDENT, actor="manager", abandon=True, reason="stopping")
        assert refused.reason == "uncollected_changes" and "could not be observed" in str(refused)
        assert prepared.report.exists() and prepared.session.is_dir()
        result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="stopping", discard_uncollected=True)
    finally:
        if (prepared.worktree / "input.txt").exists():
            (prepared.worktree / "input.txt").chmod(stat.S_IRUSR | stat.S_IWUSR)
    closing = support.read_json(Path(result["closing"]))
    assert closing["observed"]["discarded"] is None, "an unobserved discard is recorded as unknown, not as nothing"
    assert closing["observed"]["checkout"]["observed"] is False and result["released"] is False


@pytest.mark.parametrize("damage", ["acknowledged_list", "observed_list", "removal_missing_field", "foreign_audit"])
def test_closing_records_of_the_wrong_shape_do_not_verify(checkout, monkeypatch, capsys, damage):
    from stewart import _util
    from stewart.cli import main
    _failed(checkout, monkeypatch)
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="clean failure")
    closing, closed = Path(result["closing"]), Path(result["closed"])
    document = json.loads(closing.read_bytes())
    if damage == "acknowledged_list":
        document["acknowledged"] = []
    elif damage == "observed_list":
        document["observed"] = []
    elif damage == "removal_missing_field":
        del document["removal"]["session"]
    else:
        document["identity"]["audit_id"] = "another-question"
    data = json.dumps(document).encode()
    for location in (closing, closed):
        location.chmod(stat.S_IRUSR | stat.S_IWUSR)
    closing.write_bytes(data)
    bound = json.loads(closed.read_bytes())
    bound["closing_sha256"] = _util.sha256_bytes(data)
    closed.write_bytes(json.dumps(bound).encode())
    refused = _reason(prepare, checkout.ws, _revised_prompt(checkout))
    assert refused.reason == "closing_record_invalid" and refused.exit_code == EXIT_UNVERIFIED
    argv = ["--repo", str(checkout.repo), "--workspace", checkout.ws.rel, "--json", "status", "--audit-id", IDENT]
    assert main(argv) == EXIT_UNVERIFIED
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["result"]["audit_id_state"] == "unverified"


def test_a_checkout_git_cannot_validate_is_still_removed(checkout):
    prepared, _ = _triaged(checkout)
    (prepared.worktree / ".git").unlink()
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="the checkout's .git file was lost",
                   discard_uncollected=True)
    assert result["closed"] and result["exit_code"] == EXIT_OK and not prepared.worktree.exists()
    assert str(prepared.worktree) not in git_text(checkout.repo, "worktree", "list", "--porcelain")


def test_a_link_in_place_of_the_checkout_is_removed_without_following_it(checkout, tmp_path):
    import shutil
    prepared, _ = _triaged(checkout)
    target = tmp_path / "unrelated"
    target.mkdir()
    (target / "keep.txt").write_text("not the session's\n")
    shutil.rmtree(prepared.worktree)
    prepared.worktree.symlink_to(target)
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="the checkout was replaced")
    assert result["closed"] and not os.path.lexists(prepared.worktree)
    assert (target / "keep.txt").read_text() == "not the session's\n"
    assert str(prepared.worktree) not in git_text(checkout.repo, "worktree", "list", "--porcelain")


def test_a_close_interrupted_before_its_record_can_be_rerun(checkout, monkeypatch):
    prepared, _ = _triaged(checkout)

    def crash(*args, **kwargs):
        raise KeyboardInterrupt("synthetic crash")

    import stewart.session as session_module
    with monkeypatch.context() as patch:
        patch.setattr(session_module, "write_receipt", crash)
        with pytest.raises(KeyboardInterrupt):
            close(checkout.ws, IDENT, actor="manager")
    directory = closed_location(str(_common(checkout)), checkout.ws, IDENT) / prepared.prepared["session_uuid"]
    assert directory.is_dir() and not os.listdir(directory), "control: the crash left an empty closing directory"
    assert status(checkout.ws, IDENT)["schema"] == "stewart.status/12", "an empty closing directory is not a close"
    result = close(checkout.ws, IDENT, actor="manager")
    assert result["closed"] and not prepared.session.exists()


def test_status_on_a_released_id_names_a_later_session_that_lost_its_records(checkout, monkeypatch):
    import shutil
    _failed(checkout, monkeypatch)
    close(checkout.ws, IDENT, actor="manager", abandon=True, reason="clean failure")
    again = prepare(checkout.ws, _revised_prompt(checkout))
    assert status(checkout.ws, IDENT)["schema"] == "stewart.status/12", "control: the live session is shown"
    shutil.rmtree(again["session"])
    refused = _reason(status, checkout.ws, IDENT)
    assert refused.reason == "session_records_missing" and refused.exit_code == EXIT_REFUSED


def test_a_link_in_place_of_attempts_is_kept_and_named(checkout, tmp_path):
    prepared, _ = _triaged(checkout)
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "attempt-a").mkdir(parents=True)
    attempts = Path(prepared.prepared["audit_dir"]) / "attempts"
    attempts.symlink_to(elsewhere)
    result = close(checkout.ws, IDENT, actor="manager")
    assert str(attempts) in result["leftovers"] and result["exit_code"] == EXIT_ATTENTION
    assert (elsewhere / "attempt-a").is_dir(), "the link's target is never removed"


def test_a_moved_checkout_is_kept_and_named(checkout, tmp_path):
    prepared = support.prepared_session(checkout, report=None)
    moved = tmp_path / "moved-checkout"
    checkout.git("worktree", "move", "--force", "--force", str(prepared.worktree), str(moved))
    # A checkout close cannot see where it was recorded is not observed.
    assert _reason(close, checkout.ws, IDENT, actor="manager", abandon=True,
                   reason="moved away").reason == "uncollected_changes"
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="moved away", discard_uncollected=True)
    assert f"checkout registered at {moved}" in result["leftovers"] and result["exit_code"] == EXIT_ATTENTION
    assert moved.is_dir() and str(moved) in git_text(checkout.repo, "worktree", "list", "--porcelain")


def test_an_unidentified_session_can_still_be_abandoned(checkout):
    session = support.session_path(checkout, IDENT)
    session.mkdir(parents=True, mode=0o700)
    refused = _reason(close, checkout.ws, IDENT, actor="manager")
    assert refused.reason in ("record_missing", "close_unidentified") and refused.exit_code == EXIT_UNVERIFIED
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="crashed before its record")
    assert result["closed"] and not session.exists() and result["released"] is False
    assert _reason(prepare, checkout.ws, checkout.prompt_commit()).reason == "audit_id_reserved"


def test_a_closed_records_folder_that_is_not_a_directory_keeps_the_id_reserved(checkout):
    folder = closed_location(str(_common(checkout)), checkout.ws, IDENT)
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.write_text("not a directory\n")
    refused = _reason(prepare, checkout.ws, checkout.prompt_commit())
    assert refused.reason == "closing_record_invalid" and refused.exit_code == EXIT_UNVERIFIED


def test_a_paused_hold_left_by_an_abandon_is_shown_in_the_closed_view(checkout, capsys):
    from stewart.cli import main
    support.prepared_session(checkout, mode="paused", report=None)
    close(checkout.ws, IDENT, actor="manager", abandon=True, reason="cancelled")
    view = status(checkout.ws, IDENT)
    assert view["closes"][0]["hold_outstanding"] is True
    assert main(["--repo", str(checkout.repo), "--workspace", checkout.ws.rel, "status", "--audit-id", IDENT]) == EXIT_OK
    assert "tell the writers" in capsys.readouterr().out


def test_a_concluded_close_waits_for_the_paused_hold(checkout):
    from stewart.triage import resume
    prepared, collected = _triaged(checkout, mode="paused")
    refused = _reason(close, checkout.ws, IDENT, actor="manager")
    assert refused.reason == "close_hold_outstanding" and refused.retained and refused.next_steps
    disposition = status(checkout.ws, IDENT)["dispositions"][-1]["name"]
    resume(checkout.ws, IDENT, triage=disposition, reason="triaged")
    result = close(checkout.ws, IDENT, actor="manager")
    assert result["closed"] and result["hold_outstanding"] is False


def test_retained_bytes_are_recorded_in_the_closing_record(checkout):
    from stewart import _util
    from stewart.triage import retain
    prepared, _ = _triaged(checkout)
    disposition = status(checkout.ws, IDENT)["dispositions"][-1]["name"]
    retain(checkout.ws, IDENT, triage=disposition, report=True)
    result = close(checkout.ws, IDENT, actor="manager")
    retained = support.read_json(Path(result["closing"]))["observed"]["retained"]
    destination = checkout.repo / checkout.meta["report_path"]
    assert retained == [{"path": str(destination), "sha256": _util.sha256_bytes(destination.read_bytes()),
                         "source": "REPORT.md"}]
    assert status(checkout.ws, IDENT)["closes"][0]["retained"] == retained


def test_an_earlier_close_leftover_is_not_news_for_the_live_session(checkout, monkeypatch):
    failed = _failed(checkout, monkeypatch)
    stray = failed.worktree.parent / "stray.txt"
    stray.write_text("left by hand\n")
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="clean failure")
    assert result["released"] and str(stray) in result["leftovers"]
    prepare(checkout.ws, _revised_prompt(checkout))
    view = status(checkout.ws, IDENT)
    assert view["exit_code"] == EXIT_OK and view["closes"][0]["leftovers"] == [str(stray)]
    assert status_list(checkout.ws)["exit_code"] == EXIT_OK


def test_abandon_refuses_when_bytes_sit_where_git_cannot_list_them(checkout):
    prepared = support.prepared_session(checkout, report=None)
    hidden = prepared.worktree / checkout.ws.rel / "scratch-notes"
    hidden.mkdir()
    (hidden / "findings.md").write_text("uncollected findings\n")
    hidden.chmod(0)
    try:
        refused = _reason(close, checkout.ws, IDENT, actor="manager", abandon=True, reason="stopping")
        assert refused.reason == "uncollected_changes" and "scratch-notes" in str(refused)
        assert prepared.session.is_dir(), "nothing was removed"
    finally:
        hidden.chmod(stat.S_IRWXU)
    # Control: once readable, the same bytes are named as uncollected files.
    refused = _reason(close, checkout.ws, IDENT, actor="manager", abandon=True, reason="stopping")
    assert refused.reason == "uncollected_changes" and "findings.md" in str(refused)


def test_an_uncollected_commit_is_not_discarded_silently(checkout):
    prepared = support.prepared_session(checkout, report=None)
    (prepared.worktree / "committed.txt").write_text("only in a commit\n")
    checkout.git("add", "committed.txt", cwd=prepared.worktree)
    checkout.git("commit", "-qm", "auditor commit", cwd=prepared.worktree)
    checkout.git("rm", "-q", "committed.txt", cwd=prepared.worktree)
    checkout.git("commit", "-qm", "and back", cwd=prepared.worktree)
    refused = _reason(close, checkout.ws, IDENT, actor="manager", abandon=True, reason="stopping")
    assert refused.reason == "uncollected_changes" and "HEAD at" in str(refused)
    collect(checkout.ws, IDENT, auditor_stopped="finished")
    # Invariance: a collection that recorded that HEAD preserved what it shows.
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="stopping")
    assert result["closed"]


def test_a_moved_checkout_is_found_through_its_git_administration(checkout, tmp_path):
    prepared = support.prepared_session(checkout, report=None)
    moved = tmp_path / "moved-unlocked"
    checkout.git("worktree", "unlock", str(prepared.worktree))
    checkout.git("worktree", "move", str(prepared.worktree), str(moved))
    refused = _reason(close, checkout.ws, IDENT, actor="manager", abandon=True, reason="moved away")
    assert refused.reason == "uncollected_changes" and str(moved) in str(refused)
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="moved away", discard_uncollected=True)
    assert f"checkout registered at {moved}" in result["leftovers"] and result["exit_code"] == EXIT_ATTENTION
    assert moved.is_dir() and str(moved) in git_text(checkout.repo, "worktree", "list", "--porcelain")


def test_a_planted_git_link_is_never_used_to_run_git(checkout):
    prepared, _ = _triaged(checkout)
    index = checkout.repo / ".git" / "index"
    before = index.read_bytes(), index.stat().st_mtime_ns
    gitfile = prepared.worktree / ".git"
    gitfile.unlink()
    gitfile.symlink_to(checkout.repo / ".git")
    collected = collect(checkout.ws, IDENT, auditor_stopped="finished")
    assert any(error["reason"] == "checkout_identity" for error in collected["receipt"]["errors"])
    assert collected["exit_code"] == EXIT_UNVERIFIED
    refused = _reason(close, checkout.ws, IDENT, actor="manager", abandon=True, reason="planted link")
    assert refused.reason == "uncollected_changes"
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="planted link", discard_uncollected=True)
    assert result["closed"] and not os.path.lexists(prepared.worktree)
    assert (index.read_bytes(), index.stat().st_mtime_ns) == before, "the maintainer's index was never written"
    assert (checkout.repo / ".git" / "HEAD").is_file(), "the link's target is untouched"


@pytest.mark.parametrize("damage", ["identity_without_uuid", "coordination_text", "member_outside", "prompt_number",
                                    "session_elsewhere", "ref_elsewhere", "uuid_not_canonical"])
def test_closing_records_that_would_direct_removal_elsewhere_do_not_verify(checkout, monkeypatch, damage):
    from stewart import _util
    from stewart.cli import main
    _failed(checkout, monkeypatch)
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="clean failure")
    closing, closed = Path(result["closing"]), Path(result["closed"])
    document = json.loads(closing.read_bytes())
    if damage == "identity_without_uuid":
        del document["identity"]["session_uuid"]
    elif damage == "coordination_text":
        document["observed"]["coordination"] = "paused"
    elif damage == "member_outside":
        document["removal"]["members"] = [str(checkout.repo)]
    elif damage == "prompt_number":
        document["identity"]["prompt_commit"] = 7
    elif damage == "session_elsewhere":
        document["removal"]["session"] = str(checkout.repo)
    elif damage == "ref_elsewhere":
        document["removal"]["refs"] = [{"ref": "refs/heads/main", "commit": "0" * 40}]
    else:
        document["identity"]["session_uuid"] = document["removal"]["session_uuid"] = "../../x"
    data = json.dumps(document).encode()
    for location in (closing, closed):
        location.chmod(stat.S_IRUSR | stat.S_IWUSR)
    closing.write_bytes(data)
    bound = json.loads(closed.read_bytes())
    bound["closing_sha256"] = _util.sha256_bytes(data)
    closed.write_bytes(json.dumps(bound).encode())
    assert _reason(prepare, checkout.ws, _revised_prompt(checkout)).reason == "closing_record_invalid"
    assert main(["--repo", str(checkout.repo), "--workspace", checkout.ws.rel, "status", "--audit-id", IDENT]) \
        == EXIT_UNVERIFIED
    assert git_text(checkout.repo, "rev-parse", "refs/heads/main"), "nothing outside the session was touched"


def test_a_record_outside_the_session_layout_directs_no_removal(checkout, tmp_path):
    prepared = support.prepared_session(checkout, report=None)
    decoy = tmp_path / "decoy"
    (decoy / "runtime").mkdir(parents=True)
    record_path = prepared.session / "session.json"
    record = json.loads(record_path.read_text())
    record["audit_dir"] = str(decoy)
    record["worktree"] = str(decoy / "worktree")
    record_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    record_path.write_text(json.dumps(record))
    result = close(checkout.ws, IDENT, actor="manager", abandon=True, reason="tampered record")
    assert (decoy / "runtime").is_dir(), "a path outside the layout is never removed"
    # The registry row still names the real checkout, which is retired.
    assert not prepared.worktree.exists() and result["closed"]


def test_a_crash_while_publishing_leaves_no_partial_record(checkout, monkeypatch):
    prepared, _ = _triaged(checkout)
    real = os.link

    def crash(source, destination, *args, **kwargs):
        if Path(destination).name == "CLOSING.json":
            raise KeyboardInterrupt("synthetic crash between staging and publication")
        return real(source, destination, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, "link", crash)
        with pytest.raises(KeyboardInterrupt):
            close(checkout.ws, IDENT, actor="manager")
    directory = closed_location(str(_common(checkout)), checkout.ws, IDENT) / prepared.prepared["session_uuid"]
    assert not (directory / "CLOSING.json").exists() and [p.name for p in directory.iterdir() if p.name.endswith(".staged")]
    assert status(checkout.ws, IDENT)["schema"] == "stewart.status/12", "a staged copy is not a close"
    assert close(checkout.ws, IDENT, actor="manager")["closed"]


def test_the_listing_names_a_lost_session_once(checkout, monkeypatch):
    import shutil
    _failed(checkout, monkeypatch)
    close(checkout.ws, IDENT, actor="manager", abandon=True, reason="clean failure")
    again = prepare(checkout.ws, _revised_prompt(checkout))
    shutil.rmtree(again["session"])
    listing = status_list(checkout.ws)
    assert [entry["audit_id"] for entry in listing["sessions"]] == [IDENT]
    assert listing["exit_code"] == EXIT_UNVERIFIED
