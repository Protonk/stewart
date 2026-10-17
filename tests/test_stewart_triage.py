"""Collection-bound triage, retention and resume.

Each control pairs a refusal with the nearest admissible case so the test reads
the property the tool compares (binding to a named capture) rather than only
that some planted break turns it red.
"""

from __future__ import annotations

import json
from pathlib import Path
import tarfile

import pytest

from stewart import _util as _hash
from stewart import collect as collect_mod
from stewart.collect import collect
from stewart._bootstrap import StewartError
from stewart.triage import resume, retain, triage
import stewart_support as support
from stewart_support import WS, read_json, response_for

pytestmark = pytest.mark.system


def _triaged(checkout, *, report="Report A\n", mode="snapshot", **response_overrides):
    prepared = support.prepared_session(checkout, mode=mode, report=report)
    collected = collect(checkout.ws, checkout.meta["audit_id"], auditor_stopped="finished")
    disposition = triage(checkout.ws, checkout.meta["audit_id"], collection=collected["collection"],
                         response=response_for(collected, **response_overrides), actor="maintainer")
    return prepared, collected, disposition


def test_retention_publishes_the_reviewed_capture_not_the_live_report(checkout):
    """Collect A, review A, change the live report to B: retention publishes A unchanged."""
    repo, ws, meta = checkout.repo, checkout.ws, checkout.meta
    prepared, collected, disposition = _triaged(checkout, report="Report A\n")
    prepared.report.write_text("Report B, edited after review\n")
    published = retain(ws, meta["audit_id"], triage=disposition["triage"], report=True)["published"]
    assert (repo / meta["report_path"]).read_bytes() == b"Report A\n"
    assert published[0]["sha256"] == _hash.sha256_bytes(b"Report A\n") == disposition["record"]["report_sha256"]
    assert checkout.git("diff", "--cached", "--name-only") == "", "retention stages nothing"


@pytest.mark.parametrize("target", ["REPORT.md", "files.tar", "collection.json"])
def test_tampered_capture_is_refused_with_evidence_retained(checkout, target):
    ws, meta = checkout.ws, checkout.meta
    # Build the session with a reviewed support file so both retention routes exist.
    meta["scratch_paths"] = [f"{WS}/scratch/one-question/notes.txt"]
    prepared = support.prepared_session(checkout, report="Report A\n")
    notes = prepared.worktree / WS / "scratch/one-question/notes.txt"
    notes.parent.mkdir(parents=True)
    notes.write_text("support\n")
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    disposition = triage(ws, meta["audit_id"], collection=collected["collection"],
                         response=response_for(collected, support_reviewed=[f"{WS}/scratch/one-question/notes.txt"]),
                         actor="maintainer")
    directory = Path(collected["path"])
    victim = directory / target
    original = victim.read_bytes()
    victim.write_bytes(original + b"\n")
    with pytest.raises(StewartError) as refused:
        retain(ws, meta["audit_id"], triage=disposition["triage"], report=True,
               support=[f"{WS}/scratch/one-question/notes.txt"])
    assert refused.value.reason in {"evidence_tampered", "binding_mismatch"}
    assert refused.value.retained == [str(directory / "files.tar" if target == "files.tar" else directory)]
    assert not (checkout.repo / meta["report_path"]).exists()
    # Control: restoring the exact bytes makes the same retention admissible.
    victim.write_bytes(original)
    retain(ws, meta["audit_id"], triage=disposition["triage"], report=True,
           support=[f"{WS}/scratch/one-question/notes.txt"])
    assert (checkout.repo / meta["report_path"]).read_bytes() == b"Report A\n"


def test_a_new_collection_cannot_inherit_an_earlier_disposition(checkout):
    repo, ws, meta = checkout.repo, checkout.ws, checkout.meta
    prepared, first, disposition = _triaged(checkout, report="Report A\n")
    prepared.report.write_text("Report B\n")
    second = collect(ws, meta["audit_id"], auditor_stopped="finished")
    # The earlier review still publishes A, never B, and B needs its own review.
    retain(ws, meta["audit_id"], triage=disposition["triage"], report=True)
    assert (repo / meta["report_path"]).read_bytes() == b"Report A\n"
    with pytest.raises(StewartError) as refused:
        triage(ws, meta["audit_id"], collection=second["collection"],
               response=response_for(first), actor="maintainer")  # A's digest against B
    assert refused.value.reason == "collection_binding"
    accepted = triage(ws, meta["audit_id"], collection=second["collection"],
                      response=response_for(second), actor="maintainer")
    assert accepted["record"]["report_sha256"] == second["receipt"]["report_sha256"]


def test_unrelated_main_changes_cannot_redirect_retention(checkout):
    repo, ws, meta, git = checkout.repo, checkout.ws, checkout.meta, checkout.git
    prepared, collected, disposition = _triaged(checkout, report="Report A\n")
    # Main's prompt now names a different report path; retention follows the session record.
    other = dict(meta, audit_id="other-question", report_path=ws.report_path("other-question"))
    (repo / ws.prompt).write_text(support.assignment_text(other))
    git("add", "--", ws.prompt)
    git("commit", "-qm", "A later assignment on main")
    published = retain(ws, meta["audit_id"], triage=disposition["triage"], report=True)["published"]
    assert published[0]["path"] == str(repo / meta["report_path"])
    assert not (repo / other["report_path"]).exists()


def test_existing_destination_symlinked_parent_and_escaping_paths_are_refused(checkout):
    repo, ws, meta = checkout.repo, checkout.ws, checkout.meta
    prepared, collected, disposition = _triaged(checkout, report="Report A\n")
    destination = repo / meta["report_path"]
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"Existing retained report must survive.\n")
    with pytest.raises(StewartError) as refused:
        retain(ws, meta["audit_id"], triage=disposition["triage"], report=True)
    assert refused.value.reason == "destination_exists"
    assert destination.read_bytes() == b"Existing retained report must survive.\n"
    destination.unlink()
    destination.parent.rmdir()
    outside = repo.parent / "outside-reports"
    outside.mkdir()
    (repo / WS / "reports").symlink_to(outside, target_is_directory=True)
    with pytest.raises(StewartError) as refused:
        retain(ws, meta["audit_id"], triage=disposition["triage"], report=True)
    assert refused.value.reason == "path_symlink"
    assert list(outside.iterdir()) == []
    with pytest.raises(StewartError) as refused:
        retain(ws, meta["audit_id"], triage=disposition["triage"], support=["../escape.txt"])
    assert refused.value.reason == "path_escape"


def test_custody_gaps_need_explicit_dispositions_and_empty_claims_are_valid(checkout):
    ws, meta = checkout.ws, checkout.meta
    prepared = support.prepared_session(checkout, report=None)
    (prepared.worktree / "stray.txt").write_text("unexpected\n")
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    gap_ids = {gap["id"] for gap in collected["gaps"]}
    assert {"report_missing", "unexpected_path:stray.txt"} <= gap_ids
    incomplete = response_for(collected)
    del incomplete["custody_gaps"]["report_missing"]
    with pytest.raises(StewartError, match="undispositioned: report_missing") as refused:
        triage(ws, meta["audit_id"], collection=collected["collection"], response=incomplete, actor="m")
    assert refused.value.reason == "custody_gaps"
    invented = response_for(collected)
    invented["custody_gaps"]["unexpected_path:never-there.txt"] = "made up"
    with pytest.raises(StewartError, match="not a gap of this collection"):
        triage(ws, meta["audit_id"], collection=collected["collection"], response=invented, actor="m")
    cancelled = triage(ws, meta["audit_id"], collection=collected["collection"],
                       response=response_for(collected, decision="Cancelled; no findings assessed."), actor="m")
    assert cancelled["record"]["counts"] == {"accepted": 0, "rejected": 0, "unresolved": 0}
    assert cancelled["record"]["report_gap"].startswith("no report captured")
    with pytest.raises(StewartError) as refused:
        retain(ws, meta["audit_id"], triage=cancelled["triage"], report=True)
    assert refused.value.reason == "report_unavailable", "a missing report cannot be retained as a success"


def test_report_binding_rejects_wrong_digest_and_misplaced_gap(checkout):
    ws, meta = checkout.ws, checkout.meta
    support.prepared_session(checkout, report="Report A\n")
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    wrong = response_for(collected, report_sha256=_hash.sha256_bytes(b"not the captured bytes"))
    with pytest.raises(StewartError) as refused:
        triage(ws, meta["audit_id"], collection=collected["collection"], response=wrong, actor="m")
    assert refused.value.reason == "report_binding"
    misplaced = response_for(collected, report_gap="there is a report, so this is contradictory")
    with pytest.raises(StewartError) as refused:
        triage(ws, meta["audit_id"], collection=collected["collection"], response=misplaced, actor="m")
    assert refused.value.reason == "response_schema"
    bad_claim = response_for(collected, accepted=[{"claim": "accepted without evidence"}])
    with pytest.raises(StewartError, match="evidence") as refused:
        triage(ws, meta["audit_id"], collection=collected["collection"], response=bad_claim, actor="m")
    assert refused.value.reason == "response_schema"
    with pytest.raises(StewartError) as refused:
        triage(ws, meta["audit_id"], collection=collected["collection"], response=response_for(collected), actor="  ")
    assert refused.value.reason == "actor_required"


def test_reconsideration_adds_a_record_and_retention_needs_no_accepted_claim(checkout):
    ws, meta = checkout.ws, checkout.meta
    prepared, collected, first = _triaged(checkout, report="Report A\n", decision="Hold.")
    second = triage(ws, meta["audit_id"], collection=collected["collection"],
                    response=response_for(collected, decision="Reconsidered: retain.",
                                          rejected=[{"claim": "x", "reason": "unsupported"}]),
                    actor="maintainer")
    assert first["path"] != second["path"]
    assert read_json(Path(first["path"]))["decision"] == "Hold."
    assert read_json(Path(second["path"]))["counts"]["rejected"] == 1
    assert read_json(Path(second["path"]))["counts"]["accepted"] == 0
    retain(ws, meta["audit_id"], triage=second["triage"], report=True)
    assert (checkout.repo / meta["report_path"]).read_bytes() == b"Report A\n"


def test_support_retention_is_explicit_and_separately_reviewed(checkout):
    repo, ws, meta = checkout.repo, checkout.ws, checkout.meta
    meta["scratch_paths"] = [f"{WS}/scratch/one-question/reviewed.txt", f"{WS}/scratch/one-question/unreviewed.txt"]
    prepared = support.prepared_session(checkout, report="Report A\n")
    area = prepared.worktree / WS / "scratch/one-question"
    area.mkdir(parents=True)
    (area / "reviewed.txt").write_text("reviewed\n")
    (area / "unreviewed.txt").write_text("not reviewed\n")
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    with pytest.raises(StewartError) as refused:
        triage(ws, meta["audit_id"], collection=collected["collection"],
               response=response_for(collected, support_reviewed=["never/captured.txt"]), actor="m")
    assert refused.value.reason == "support_unavailable"
    disposition = triage(ws, meta["audit_id"], collection=collected["collection"],
                         response=response_for(collected, support_reviewed=[f"{WS}/scratch/one-question/reviewed.txt"]),
                         actor="m")
    with pytest.raises(StewartError) as refused:
        retain(ws, meta["audit_id"], triage=disposition["triage"], support=[f"{WS}/scratch/one-question/unreviewed.txt"])
    assert refused.value.reason == "support_unreviewed"
    with pytest.raises(StewartError) as refused:
        retain(ws, meta["audit_id"], triage=disposition["triage"])
    assert refused.value.reason == "retain_nothing"
    result = retain(ws, meta["audit_id"], triage=disposition["triage"],
                    support=[f"{WS}/scratch/one-question/reviewed.txt"])
    assert (repo / WS / "scratch/one-question/reviewed.txt").read_text() == "reviewed\n"
    assert not (repo / WS / "scratch/one-question/unreviewed.txt").exists()
    assert not (repo / meta["report_path"]).exists(), "support retention does not imply report retention"
    assert result["published"][0]["source"].startswith("files.tar:")


def test_paused_resume_needs_a_bound_triage_and_cancellation_survives_failed_collection(checkout, monkeypatch):
    ws, meta = checkout.ws, checkout.meta
    prepared = support.prepared_session(checkout, mode="paused", report="Partial\n")
    original = collect_mod.git

    def broken(where, *args, **kwargs):
        if where == prepared.worktree:
            raise StewartError("Synthetic Git failure", reason="git_failed")
        return original(where, *args, **kwargs)

    monkeypatch.setattr(collect_mod, "git", broken)
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    monkeypatch.setattr(collect_mod, "git", original)
    assert collected["receipt"]["errors"] == ["Synthetic Git failure"]
    with pytest.raises(StewartError) as refused:
        resume(ws, meta["audit_id"], triage="20260101T000000-00000000", reason="no triage exists")
    assert refused.value.reason == "record_missing"
    with pytest.raises(StewartError) as refused:
        resume(ws, meta["audit_id"], triage="not a record name", reason="x")
    assert refused.value.reason == "record_name"
    cancelled = triage(ws, meta["audit_id"], collection=collected["collection"],
                       response=response_for(collected, decision="Cancelled after failed collection."), actor="m")
    released = resume(ws, meta["audit_id"], triage=cancelled["triage"], reason="Cancelled; writers may continue.")
    record = read_json(Path(released["path"]))
    assert record["collection_errors"] == ["Synthetic Git failure"]
    assert record["process_control"].startswith("none")
    assert record["triage"] == cancelled["triage"]
    assert prepared.worktree.exists(), "no cleanup follows cancellation"


def test_incomplete_collection_cannot_be_triaged(checkout):
    ws, meta = checkout.ws, checkout.meta
    prepared = support.prepared_session(checkout)
    partial = prepared.session / "collections" / "20260102T000000-cafef00d"
    partial.mkdir(parents=True)
    (partial / "STARTED.json").write_text("{}")
    with pytest.raises(StewartError) as refused:
        triage(ws, meta["audit_id"], collection="20260102T000000-cafef00d",
               response={"decision": "x", "custody_gaps": {}}, actor="m")
    assert refused.value.reason == "collection_incomplete"
    with pytest.raises(StewartError) as refused:
        triage(ws, meta["audit_id"], collection="20260102T000000-00000000",
               response={"decision": "x", "custody_gaps": {}}, actor="m")
    assert refused.value.reason == "collection_not_found"


@pytest.mark.parametrize("change", ["receipt", "report", "unrelated"])
def test_resume_and_status_revalidate_the_same_binding_as_retention(checkout, change):
    from stewart.status import status

    prepared, collected, disposition = _triaged(checkout, mode="paused")
    directory = Path(collected["path"])
    if change == "receipt":
        receipt = read_json(directory / "collection.json")
        receipt["errors"].append("new gap after review")
        (directory / "collection.json").write_text(json.dumps(receipt))
    elif change == "report":
        (directory / "REPORT.md").write_text("Status: complete\nchanged captured report")
    else:
        prepared.report.write_text("changed live report, outside the reviewed capture")
    before = support.snapshot_tree(prepared.session)
    view = status(checkout.ws, "one-question")
    assert support.snapshot_tree(prepared.session) == before, "status must never repair stale bindings"
    actions = {action["action"] for action in view["next_actions"]}
    if change == "unrelated":
        assert {"retain", "resume"} <= actions and view["dispositions"][0]["problems"] == []
        resume(checkout.ws, "one-question", triage=disposition["triage"], reason="reviewed capture remains valid")
        return
    assert not {"retain", "resume"} & actions
    assert view["dispositions"][0]["problems"] and view["outstanding"]
    if change == "report":
        assert view["auditor_reported"]["completion"]["value"] is None
    with pytest.raises(StewartError) as refused:
        resume(checkout.ws, "one-question", triage=disposition["triage"], reason="stale review")
    assert refused.value.reason == ("binding_mismatch" if change == "receipt" else "evidence_tampered")
    assert not (prepared.session / "RESUMED.json").exists()
    # Recovery uses fresh custody and an explicit cancellation, preserving the old evidence.
    fresh = collect(checkout.ws, "one-question", auditor_stopped="finished")
    cancelled = triage(checkout.ws, "one-question", collection=fresh["collection"],
                       response=response_for(fresh, decision="Cancel after reviewing fresh custody"), actor="manager")
    resume(checkout.ws, "one-question", triage=cancelled["triage"], reason="cancelled with evidence retained")
    assert directory.exists()


@pytest.mark.parametrize("field", ["collection", "collection_sha256"])
def test_response_binding_fields_are_required_not_filled_from_destination(checkout, field):
    prepared = support.prepared_session(checkout)
    collected = collect(checkout.ws, "one-question", auditor_stopped="finished")
    response = response_for(collected)
    response.pop(field)
    before = support.snapshot_tree(prepared.session)
    with pytest.raises(StewartError) as refused:
        triage(checkout.ws, "one-question", collection=collected["collection"], response=response, actor="manager")
    assert refused.value.reason == "collection_binding"
    assert support.snapshot_tree(prepared.session) == before
    # Supplying the actual capture binding enables this otherwise identical response.
    response[field] = response_for(collected)[field]
    recorded = triage(checkout.ws, "one-question", collection=collected["collection"], response=response, actor="manager")
    assert recorded["record"]["response"][field] == response[field]


def test_legacy_disposition_stays_unsupported_without_rewriting(checkout):
    from stewart.status import status

    prepared, collected, disposition = _triaged(checkout, mode="paused")
    location = Path(disposition["path"])
    legacy = read_json(location)
    legacy["schema_version"] = 1
    legacy["response"].pop("collection")
    legacy["response"].pop("collection_sha256")
    location.write_text(json.dumps(legacy))
    before = support.snapshot_tree(prepared.session)
    view = status(checkout.ws, "one-question")
    assert view["dispositions"][0]["problems"][0]["reason"] == "record_schema"
    assert not {"retain", "resume"} & {a["action"] for a in view["next_actions"]}
    for operation, kwargs in ((retain, {"report": True}), (resume, {"reason": "Review complete"})):
        with pytest.raises(StewartError) as refused:
            operation(checkout.ws, "one-question", triage=disposition["triage"], **kwargs)
        assert refused.value.reason == "triage_schema"
    assert support.snapshot_tree(prepared.session) == before
    fresh = triage(checkout.ws, "one-question", collection=collected["collection"],
                   response=response_for(collected), actor="manager")
    assert fresh["record"]["schema_version"] == 3 and read_json(location) == legacy
    assert {"retain", "resume"} <= {a["action"] for a in status(checkout.ws, "one-question")["next_actions"]}
