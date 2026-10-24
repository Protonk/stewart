"""Investigative baseline comparisons for status, not expectations of a new UI.

These tests preserve the old behavior while isolating its information boundary,
its live observations and a close dependency. They retain actual JSON/rendered
views in the node directory so the inquiry can cite evidence rather than infer
it from assertion success. A future contract implementation must deliberately
update or retire the baseline assertions; the controls remain useful.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from stewart.cli import _render_status
from stewart.close import close_plan
from stewart.collect import collect, inventory
from stewart.coordination import record_launch, record_message
from stewart.prepare import prepare
from stewart.status import status, status_list
from stewart.triage import triage
import stewart_support as support

pytestmark = pytest.mark.system


def _save(directory, name, value):
    """Write evidence outside session custody; never rewrite a fixture receipt."""
    (directory / f"{name}.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    if isinstance(value, dict) and value.get("schema") == "stewart.status/13":
        (directory / f"{name}.txt").write_text("\n".join(_render_status(value)) + "\n")


@pytest.mark.parametrize("workspace", ["reviews/one", "nested/area/inspections/question"])
def test_status_inquiry_relationship_records_and_live_report(tmp_path, run_cmd, monkeypatch, workspace):
    checkout = support.make_checkout(tmp_path, run_cmd, ws_rel=workspace, name="unrelated project")
    prepared = support.prepared_session(checkout, report=None)
    ident = checkout.meta["audit_id"]
    bootstrap = importlib.import_module("stewart._bootstrap")
    observe = bootstrap.observe_runtime
    observed_roots = []

    def observed(root, *args, **kwargs):
        observed_roots.append(str(root))
        return observe(root, *args, **kwargs)

    before_records = support.snapshot_tree(prepared.session)
    with monkeypatch.context() as patch:
        patch.setattr(bootstrap, "observe_runtime", observed)
        ordinary, git_places = support.git_working_directories(patch, status, checkout.ws, ident)
    _save(tmp_path, "01-ordinary", ordinary)
    _save(tmp_path, "02-observed-reads", {"runtime_roots": observed_roots,
                                         "git_working_directories": list(map(str, git_places))})
    assert ordinary["attention"] == [] and ordinary["exit_code"] == 0
    assert "no complete collection exists" in ordinary["outstanding"]
    assert [a["action"] for a in ordinary["next_actions"]] == ["handoff", "launch", "collect"]
    assert prepared.worktree in git_places, "baseline inspection really queries the auditor checkout"
    record = support.read_json(prepared.session / "session.json")
    assert record["runtime"]["root"] in observed_roots, "baseline inspection really scans the exposed runtime"
    assert support.snapshot_tree(prepared.session) == before_records

    record_launch(checkout.ws, ident, style="subagent", model="fixture", effort="fixture", actor="manager",
                  note="Fixture acknowledgment; no actual harness was launched.")
    acknowledged = status(checkout.ws, ident)
    _save(tmp_path, "03-launch-acknowledged", acknowledged)
    assert acknowledged["stage"] == ordinary["stage"] == "prepared"
    assert [a["action"] for a in acknowledged["next_actions"]] == ["handoff", "collect"]
    assert acknowledged["auditor_reported"]["completion"]["value"] is None

    prepared.report.write_text("Status: complete\nA live report is not a captured return.\n")
    live_report = status(checkout.ws, ident)
    _save(tmp_path, "04-live-report", live_report)
    assert live_report == acknowledged, "live report appearance does not establish activity or completion"
    before_records = support.snapshot_tree(prepared.session)
    assert status(checkout.ws, ident) == live_report
    assert support.snapshot_tree(prepared.session) == before_records

    record_message(checkout.ws, ident, direction="from-auditor", actor="manager", channel="fixture relay",
                   text="Fixture account of approval followed by the manager continuing its watcher.")
    relayed = status(checkout.ws, ident)
    _save(tmp_path, "05-relayed-account", relayed)
    assert relayed["messages"] and relayed["attention"] == []
    assert relayed["stage"] == "prepared" and relayed["auditor_reported"] == ordinary["auditor_reported"]

    # A fixture exit log is an observation input, not execution of a real harness.
    (prepared.session / "HARNESS-EXIT.txt").write_text("2 2026-10-23T00:00:00Z\n")
    failed = status(checkout.ws, ident)
    _save(tmp_path, "06-recorded-harness-exit", failed)
    assert failed["exit_code"] == 1
    assert {item["reason"] for item in failed["attention"]} == {"harness_exit_nonzero"}
    assert failed["auditor_reported"]["completion"]["value"] is None
    listing = status_list(checkout.ws)
    _save(tmp_path, "07-listing", listing)
    assert listing["exit_code"] == 1

    collected = collect(checkout.ws, ident, auditor_stopped="interrupted")
    captured = status(checkout.ws, ident)
    _save(tmp_path, "08-collected", captured)
    assert captured["stage"] == "collected"
    assert captured["collections"][0]["auditor_stopped"]["kind"] == "interrupted"
    assert captured["collections"][0]["report_path"] == str(Path(collected["path"]) / "REPORT.md")
    assert captured["auditor_reported"]["completion"]["value"] is None, "prose is not a valid declaration"
    assert not any(item["reason"] == "harness_exit_nonzero" for item in captured["attention"])
    assert captured["harness_exits"] == failed["harness_exits"], "capture changes attention, not history"


def test_status_inquiry_close_runtime_dependency(checkout, tmp_path, monkeypatch):
    """A live runtime change outside the checkout isolates the status-only gate."""
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    captured = collect(checkout.ws, ident, auditor_stopped="finished")
    triage(checkout.ws, ident, collection=captured["collection"],
           response=support.response_for(captured), actor="manager")
    before = close_plan(checkout.ws, ident)
    _save(tmp_path, "01-baseline-close-plan", before)
    assert before["audit"]["refusal"] is None

    checkout.git("commit", "--allow-empty", "-qm", "Unrelated manager advancement")
    invariant = close_plan(checkout.ws, ident)
    _save(tmp_path, "02-unrelated-advance", invariant)
    assert invariant["audit"]["refusal"] is None
    records = support.snapshot_tree(prepared.session)
    contents = inventory(prepared.worktree)
    identity = support.read_json(prepared.session / "session.json")["runtime"]
    member = Path(identity["root"]) / "stewart/verify_inputs.py"
    original = member.read_bytes()
    member.write_bytes(original + b"\n# investigative runtime-only perturbation\n")
    assert inventory(prepared.worktree) == contents, "the runtime change is outside the checkout inventory"
    damaged = status(checkout.ws, ident)
    refused = close_plan(checkout.ws, ident)
    _save(tmp_path, "03-runtime-changed-status", damaged)
    _save(tmp_path, "04-runtime-changed-close-plan", refused)
    assert {item["reason"] for item in damaged["attention"]} == {"runtime_unavailable"}
    assert refused["audit"]["refusal"]["reason"] == "close_unverified"
    assert refused["audit"]["refusal"]["exit_code"] == 3

    close_module = importlib.import_module("stewart.close")
    original_view = close_module._status_view

    def omit_runtime_diagnostic(*args, **kwargs):
        view = original_view(*args, **kwargs)
        return {**view, "attention": [item for item in view["attention"]
                                      if item["reason"] != "runtime_unavailable"]}

    # Experimental intervention only: no close is executed and production code
    # is unchanged. This distinguishes the status gate from independent checks.
    with monkeypatch.context() as patch:
        patch.setattr(close_module, "_status_view", omit_runtime_diagnostic)
        omitted = close_plan(checkout.ws, ident)
    _save(tmp_path, "05-test-local-diagnostic-omission", omitted)
    assert omitted["audit"]["refusal"] is None
    assert support.snapshot_tree(prepared.session) == records
    member.write_bytes(original)
    restored = close_plan(checkout.ws, ident)
    _save(tmp_path, "06-restored", restored)
    assert restored["audit"]["refusal"] is None


def test_status_inquiry_private_handoff_precedes_publication(tmp_path, run_cmd, monkeypatch):
    """A private handoff cannot certify completed public handoff publication."""
    checkout = support.make_checkout(tmp_path, run_cmd, ws_rel="review/deep/question")
    revision = checkout.prompt_commit()
    prepare_module = importlib.import_module("stewart.prepare")
    write = prepare_module.write_exclusive
    public_path = []

    def interrupted_public_write(path, data, *args, **kwargs):
        # The private copy is named LAUNCH.md; the public copy is lifetime.md.
        if Path(path).suffix == ".md" and Path(path).name != "LAUNCH.md":
            public_path.append(Path(path))
            raise KeyboardInterrupt("fixture interruption after private handoff")
        return write(path, data, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(prepare_module, "write_exclusive", interrupted_public_write)
        with pytest.raises(KeyboardInterrupt):
            prepare(checkout.ws, revision)
    session = support.session_path(checkout)
    assert len(public_path) == 1 and not public_path[0].exists()
    assert (session / "LAUNCH.md").is_file()
    assert (session / "RUNTIME-PREPARED.json").is_file()
    assert not (session / "PREPARE-ERROR.json").exists()
    before = support.snapshot_tree(session)
    view = status(checkout.ws, checkout.meta["audit_id"])
    _save(tmp_path, "01-interrupted-publication", view)
    _save(tmp_path, "02-retained-record-inventory", before)
    assert view["preparation"]["handoff_matches"] == {"private": True, "public": False}
    assert view["stage"] == "preparation_incomplete"
    assert any(item["reason"] == "handoff_changed" for item in view["attention"])
    assert support.snapshot_tree(session) == before


def test_status_inquiry_close_depends_on_manager_command_rendering(checkout, tmp_path):
    """Same writer bytes do not make a damaged cached command launcher usable."""
    from stewart._bootstrap import StewartError
    from stewart._invocation import current
    from stewart.implementation import require

    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    captured = collect(checkout.ws, ident, auditor_stopped="finished")
    triage(checkout.ws, ident, collection=captured["collection"],
           response=support.response_for(captured), actor="manager")
    baseline = close_plan(checkout.ws, ident)
    _save(tmp_path, "01-render-baseline", baseline)
    assert baseline["audit"]["refusal"] is None
    invocation = current()
    (invocation.launcher.parent / "unrelated-note.txt").write_text("not the launcher\n")
    assert close_plan(checkout.ws, ident)["audit"]["refusal"] is None

    record = support.read_json(prepared.session / "session.json")
    before = support.snapshot_tree(prepared.session)
    original = invocation.launcher.read_bytes()
    invocation.launcher.write_bytes(original + b"\n# changed cached launcher\n")
    # The loaded package still matches the record's writer. It is command
    # rendering during status that encounters the distinct damaged launcher.
    require(record["stewart"], record=prepared.session / "session.json", arguments=[])
    with pytest.raises(StewartError) as caught:
        status(checkout.ws, ident)
    assert caught.value.reason == "launcher_mismatch"
    _save(tmp_path, "02-status-render-refusal", caught.value.to_json())
    refused = close_plan(checkout.ws, ident)
    _save(tmp_path, "03-close-render-refusal", refused)
    assert refused["audit"]["refusal"]["reason"] == "close_unverified"
    assert refused["audit"]["refusal"]["message"] == "status cannot read this session"
    assert support.snapshot_tree(prepared.session) == before
    invocation.launcher.write_bytes(original)
    restored = close_plan(checkout.ws, ident)
    _save(tmp_path, "04-render-restored", restored)
    assert restored["audit"]["refusal"] is None
