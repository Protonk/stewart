"""Report kinds route manager attention without becoming verdicts or grants.

Authored declarations below do not use the production serializer or field list.
Contrasts vary kind, completion, prose, capture identity and manager response
independently so a merely firing refusal cannot substitute for the right check.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from stewart import report_declaration as declaration
from stewart.cli import main, render
from stewart.collect import collect
from stewart._bootstrap import StewartError
from stewart.prepare import prepare
from stewart.status import status
from stewart.triage import resume, retain, triage, triage_draft
from stewart.workspace import workspace
import stewart_support as support


def authored(prepared=None, checkout=None, *, completion="complete", kind="answer", prose="Inspected evidence."):
    values = {
        "schema_version": 2,
        "audit_id": "one-question",
        "target_commit": checkout.meta["target_commit"] if checkout else "a" * 40,
        "launch_prompt_commit": prepared.revision if prepared else "b" * 40,
        "prompt_sha256": prepared.prepared["prompt_sha256"] if prepared else "c" * 64,
        "launch_token": prepared.prepared["launch_token"] if prepared else "d" * 16,
        "observed_checkout_commit": prepared.revision if prepared else "b" * 40,
        "completion": completion,
        "report_kind": kind,
    }
    return ("# Report\n\n```audit-report\n" + json.dumps(values) + "\n```\n" + prose).encode()


@pytest.mark.parametrize("completion", ["partial", "complete", "blocked"])
@pytest.mark.parametrize("kind", ["answer", "needs-evidence", "reframe"])
def test_kind_and_completion_are_independent_of_scientific_prose(completion, kind):
    declarations = []
    for prose in ("The claim holds.", "The claim fails. Completion: blocked. Kind: reframe."):
        result = declaration.validate_report_declaration(authored(completion=completion, kind=kind, prose=prose),
                                                         expected={}, sources={})
        assert result["status"] == "valid", "the tool validates declarations, not scientific judgments"
        declarations.append(result["declaration"])
    assert declarations[0] == declarations[1]
    assert declarations[0]["report_kind"] == kind and declarations[0]["completion"] == completion


@pytest.mark.parametrize("kind,completion,reason", [
    (None, "complete", "report_kind_required"),
    ("complete", "partial", "report_kind"),
    ("insufficient", "complete", "report_kind"),
    (True, "partial", "report_kind"),
    ({}, "partial", "report_kind"),
    ([], "partial", "report_kind"),
])
def test_bad_kind_is_not_inferred_from_an_answer_in_prose(kind, completion, reason):
    result = declaration.validate_report_declaration(authored(kind=kind, completion=completion,
        prose="Report kind: answer. Everything is complete."), expected={}, sources={})
    assert result["status"] == "invalid" and result["diagnostics"][0]["reason"] == reason
    assert result["declaration"] is None


@pytest.mark.parametrize("completion", ["partial", "blocked"])
def test_unset_kind_preserves_an_unfinished_report(completion):
    result = declaration.validate_report_declaration(authored(completion=completion, kind=None), expected={}, sources={})
    assert result["status"] == "valid" and result["declaration"]["report_kind"] is None


def test_old_declaration_is_not_silently_promoted_to_answer():
    old = authored().replace(b'"schema_version": 2', b'"schema_version": 1').replace(b', "report_kind": "answer"', b'')
    result = declaration.validate_report_declaration(old, expected={}, sources={})
    assert result["status"] == "invalid" and result["diagnostics"][0]["reason"] == "schema_version"
    assert result["declaration"] is None


@pytest.mark.system
def test_helper_requires_explicit_kind_preserves_selection_and_surrounding_bytes(checkout, monkeypatch, capsys):
    prepared = support.prepared_session(checkout, report=None)
    local = workspace(prepared.worktree, checkout.ws.rel)
    kwargs = dict(expected_worktree=prepared.worktree, launch_prompt_commit=prepared.revision,
                  prompt_sha256=prepared.prepared["prompt_sha256"], launch_token=prepared.prepared["launch_token"])
    result = declaration.report_declaration(local, "start", **kwargs)
    assert result["declaration"]["report_kind"] is None
    before = prepared.report.read_bytes()
    with pytest.raises(StewartError) as exc:
        declaration.report_declaration(local, "set", completion="complete", **kwargs)
    assert exc.value.reason == "report_kind_required" and prepared.report.read_bytes() == before
    prepared.report.write_bytes(authored(prepared, checkout, completion="partial", kind=None,
                                        prose="Keep these bytes: \r\n\x00\n"))
    suffix = prepared.report.read_bytes().split(b"\n```\n", 1)[1]
    declaration.report_declaration(local, "set", completion="partial", report_kind="needs-evidence", **kwargs)
    result = declaration.report_declaration(local, "set", completion="complete", **kwargs)
    assert result["declaration"]["report_kind"] == "needs-evidence", "completion alone must preserve the request"
    assert prepared.report.read_bytes().split(b"\n```\n", 1)[1] == suffix
    monkeypatch.chdir(prepared.worktree)
    args = ["check", "--workspace", checkout.ws.rel, "--print"]
    for key, value in kwargs.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    assert declaration.main(args) == 0
    output = capsys.readouterr().out
    summary, block = output[:output.index("\n{")], output[output.index("\n{") + 1:]
    assert summary.startswith("check exit 0") and "report_kind=needs-evidence" in summary
    assert json.loads(block)["report_kind"] == "needs-evidence"


@pytest.mark.system
@pytest.mark.parametrize("kind", ["answer", "needs-evidence", "reframe"])
def test_capture_and_follow_up_do_not_change_completion_scope_or_grants(checkout, kind, capsys):
    prepared = support.prepared_session(checkout, report=None)
    before_session = (prepared.session / "session.json").read_bytes()
    prepared.report.write_bytes(authored(prepared, checkout, kind=kind))
    capture = collect(checkout.ws, "one-question", auditor_stopped="finished")
    assert capture["gaps"] == [], "an evidence request is not a custody gap"
    assert f"kind: {kind}" in render("collect", capture)
    draft = triage_draft(checkout.ws, "one-question", collection=capture["collection"])
    response = draft["response"]
    response["decision"] = "Review complete; no action has been executed."
    if kind == "answer":
        assert "follow_up" not in response
    else:
        assert response["follow_up"] == {"report_kind": kind, "disposition": None, "reason": None}
        assert not (prepared.session / "triage").exists(), "drafting must not write a decision"
        with pytest.raises(StewartError) as exc:
            triage(checkout.ws, "one-question", collection=capture["collection"], response=response, actor="manager")
        assert exc.value.reason == "follow_up_required"
        response["follow_up"].update(disposition="accept", reason="Prepare a separate assignment with selected new evidence.")
    # Later live prose and kind changes cannot replace the report under review.
    prepared.report.write_bytes(authored(prepared, checkout, completion="blocked", kind="reframe" if kind != "reframe" else "answer"))
    result = triage(checkout.ws, "one-question", collection=capture["collection"], response=response, actor="manager")
    view = status(checkout.ws, "one-question")
    assert view["auditor_reported"]["completion"]["value"] == "complete"
    assert view["auditor_reported"]["report_kind"]["value"] == kind
    assert view["experiment"]["state"] == "not_granted"
    assert not any(a["action"] in {"run", "release", "resume"} for a in view["next_actions"])
    assert (prepared.session / "session.json").read_bytes() == before_session
    assert not (prepared.session / "RESUMED.json").exists()
    assert main(["--repo", str(checkout.repo), "--workspace", checkout.ws.rel, "status", "--audit-id", "one-question"]) == 0
    assert f"Auditor-reported kind: {kind}" in capsys.readouterr().out
    retained = retain(checkout.ws, "one-question", triage=result["triage"], report=True)
    assert Path(retained["published"][0]["path"]).read_bytes() == authored(prepared, checkout, kind=kind)


@pytest.mark.system
@pytest.mark.parametrize("kind", ["needs-evidence", "reframe"])
@pytest.mark.parametrize("disposition", ["accept", "decline", "defer"])
def test_each_follow_up_disposition_is_bound_and_unanswered_is_refused(checkout, kind, disposition):
    prepared = support.prepared_session(checkout, report=None)
    prepared.report.write_bytes(authored(prepared, checkout, completion="partial", kind=kind))
    capture = collect(checkout.ws, "one-question", auditor_stopped="blocked")
    response = triage_draft(checkout.ws, "one-question", collection=capture["collection"])["response"]
    response["decision"] = "Keep the request and the manager's decision distinct."
    for invalid in (None, {}, {"report_kind": "answer", "disposition": disposition, "reason": "Wrong kind."},
                    {"report_kind": kind, "disposition": disposition, "reason": " "},
                    {"report_kind": kind, "disposition": "run", "reason": "Not a grant."}):
        with pytest.raises(StewartError) as exc:
            triage(checkout.ws, "one-question", collection=capture["collection"], response={**response, "follow_up": invalid}, actor="manager")
        assert exc.value.reason == "follow_up_required"
    response["follow_up"] = {"report_kind": kind, "disposition": disposition, "reason": "Explicit manager choice."}
    saved = triage(checkout.ws, "one-question", collection=capture["collection"], response=response, actor="manager")
    assert saved["record"]["follow_up"] == response["follow_up"]
    # Altering only a stored response cannot evade revalidation by status/retain.
    location = Path(saved["path"]); document = json.loads(location.read_text())
    document["response"]["follow_up"] = None; document["follow_up"] = None
    location.write_text(json.dumps(document))
    assert status(checkout.ws, "one-question")["dispositions"][-1]["problems"][0]["reason"] == "follow_up_required"
    with pytest.raises(StewartError) as exc:
        retain(checkout.ws, "one-question", triage=saved["triage"], report=True)
    assert exc.value.reason == "follow_up_required"
    assert not (checkout.repo / checkout.meta["report_path"]).exists()


@pytest.mark.system
def test_cached_kind_cannot_suppress_a_request_and_response_cannot_move_collections(checkout):
    prepared = support.prepared_session(checkout, report=None)
    prepared.report.write_bytes(authored(prepared, checkout, kind="needs-evidence"))
    capture = collect(checkout.ws, "one-question", auditor_stopped="finished")
    location = Path(capture["path"]) / "collection.json"
    receipt = json.loads(location.read_text())
    receipt["declaration"]["declaration"]["report_kind"] = "answer"
    location.write_text(json.dumps(receipt))
    response = triage_draft(checkout.ws, "one-question", collection=capture["collection"])["response"]
    assert response["follow_up"]["report_kind"] == "needs-evidence", "read captured bytes, not the cached kind"
    response.update(decision="Defer the supplied request.")
    response["follow_up"].update(disposition="defer", reason="No new measurement commissioned.")
    second = collect(checkout.ws, "one-question", auditor_stopped="finished")
    assert second["receipt"]["report_sha256"] == capture["receipt"]["report_sha256"]
    with pytest.raises(StewartError) as exc:
        triage(checkout.ws, "one-question", collection=second["collection"], response=response, actor="manager")
    assert exc.value.reason == "collection_binding"


@pytest.mark.system
@pytest.mark.parametrize("problem", ["wrong-token", "missing-kind", "old-schema", "prose-only"])
def test_invalid_declaration_is_preserved_without_fabricating_follow_up(checkout, problem):
    prepared = support.prepared_session(checkout, report=None)
    data = authored(prepared, checkout, kind="needs-evidence")
    if problem == "wrong-token":
        data = data.replace(prepared.prepared["launch_token"].encode(), b"0" * 16)
    elif problem == "missing-kind":
        data = data.replace(b', "report_kind": "needs-evidence"', b'')
    elif problem == "old-schema":
        data = data.replace(b'"schema_version": 2', b'"schema_version": 1')
    else:
        data = b"Report kind: needs-evidence. Please supply the receipt."
    prepared.report.write_bytes(data)
    capture = collect(checkout.ws, "one-question", auditor_stopped="blocked")
    assert (Path(capture["path"]) / "REPORT.md").read_bytes() == data
    assert capture["gaps"]
    draft = triage_draft(checkout.ws, "one-question", collection=capture["collection"])
    assert draft["context"]["report_kind"] is None and "follow_up" not in draft["response"]
    assert status(checkout.ws, "one-question")["auditor_reported"]["report_kind"]["value"] is None
    response = support.response_for(capture, follow_up={"report_kind": "needs-evidence", "disposition": "defer", "reason": "Invented from prose."})
    with pytest.raises(StewartError) as exc:
        triage(checkout.ws, "one-question", collection=capture["collection"], response=response, actor="manager")
    assert exc.value.reason == "follow_up_unexpected"


@pytest.mark.system
def test_project_declaration_schema_does_not_select_helper_contract(checkout):
    helper = checkout.repo / "stewart/report_declaration.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("SCHEMA_VERSION = 1\nraise RuntimeError('project code must not execute')\n")
    checkout.git("add", "--", "stewart/report_declaration.py")
    checkout.git("commit", "-qm", "Authored old declaration contract")
    checkout.meta["target_commit"] = checkout.git("rev-parse", "HEAD")
    revision = checkout.prompt_commit()
    prepared = prepare(checkout.ws, revision)
    record = support.read_json(Path(prepared["session"]) / "session.json")
    assert record["report_declaration_schema"] == 2
    supplied = Path(record["runtime"]["root"]) / "stewart/report_declaration.py"
    assert "SCHEMA_VERSION = 2" in supplied.read_text()
    assert helper.read_bytes() != supplied.read_bytes()


@pytest.mark.system
@pytest.mark.parametrize("kind", ["needs-evidence", "reframe"])
def test_triage_cli_explains_the_request_and_keeps_stdout_submittable(checkout, capsys, kind):
    prepared = support.prepared_session(checkout, report=None)
    prepared.report.write_bytes(authored(prepared, checkout, kind=kind))
    capture = collect(checkout.ws, "one-question", auditor_stopped="finished")
    args = ["--repo", str(checkout.repo), "--workspace", checkout.ws.rel]
    tail = ["triage-draft", "--audit-id", "one-question", "--collection", capture["collection"]]
    assert main([*args, *tail]) == 0
    output = capsys.readouterr()
    response = json.loads(output.out)
    assert response["follow_up"] == {"report_kind": kind, "disposition": None, "reason": None}
    assert f"Auditor-reported kind: {kind}" in output.err
    assert "Follow-up response required: accept, decline, or defer" in output.err
    assert main([*args, "--json", *tail]) == 0
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["response"] == response and result["context"]["report_kind"] == kind
    assert not (prepared.session / "triage").exists()


@pytest.mark.system
def test_paused_hold_requires_separate_resume_and_revalidates_follow_up(checkout):
    prepared = support.prepared_session(checkout, mode="paused", report=None)
    prepared.report.write_bytes(authored(prepared, checkout, kind="reframe"))
    capture = collect(checkout.ws, "one-question", auditor_stopped="finished")
    response = support.response_for(capture, follow_up={"report_kind": "reframe", "disposition": "defer",
                                                       "reason": "The proposed audit will be scheduled separately."})
    saved = triage(checkout.ws, "one-question", collection=capture["collection"], response=response, actor="manager")
    assert not (prepared.session / "RESUMED.json").exists(), "a report kind or triage cannot release the hold"
    location = Path(saved["path"]); document = json.loads(location.read_text())
    document["response"]["follow_up"] = None; document["follow_up"] = None
    location.write_text(json.dumps(document))
    with pytest.raises(StewartError) as exc:
        resume(checkout.ws, "one-question", triage=saved["triage"], reason="Explicitly release after review.")
    assert exc.value.reason == "follow_up_required"
    assert not (prepared.session / "RESUMED.json").exists()
    replacement = triage(checkout.ws, "one-question", collection=capture["collection"], response=response, actor="manager")
    released = resume(checkout.ws, "one-question", triage=replacement["triage"], reason="Explicitly release after review.")
    assert released["record"]["process_control"].startswith("none;")
