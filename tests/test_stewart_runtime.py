"""Manager observations precede external helper execution and survive live removal."""
from __future__ import annotations

import importlib
from pathlib import Path
import shutil

import pytest

from stewart._bootstrap import StewartError
from stewart.captured import runtime_observations
from stewart.collect import collect
from stewart.experiment import release, run
from stewart.handoff import export_evidence, package_inputs
from stewart.status import status
from stewart.triage import retain, triage, triage_draft
import stewart_support as support

pytestmark = pytest.mark.system


@pytest.fixture
def supplied_runtime(monkeypatch):
    """Observe production selection at publication without changing its bytes."""
    module = importlib.import_module("stewart.prepare")
    original = module.write_receipt
    identities = []

    def write(location, value, **kwargs):
        if location.name == "session.json":
            identities.append(value["runtime"])
        return original(location, value, **kwargs)

    monkeypatch.setattr(module, "write_receipt", write)
    return identities


def test_changed_runtime_cannot_suppress_raw_report_or_claim_clean_collection(checkout, supplied_runtime):
    prepared = support.prepared_session(checkout, report="Malformed declaration is still evidence\n")
    identity = supplied_runtime[0]
    root = Path(identity["root"])
    (root / "stewart/verify_inputs.py").write_text("def self_check(): return True\n")
    (root / "stewart/verify_inputs").mkdir()
    (root / "stewart/verify_inputs/__init__.py").write_text("shadowing package\n")
    collected = collect(checkout.ws, checkout.meta["audit_id"], auditor_stopped="finished")
    directory = Path(collected["path"])
    assert (directory / "REPORT.md").read_bytes() == prepared.report.read_bytes()
    receipt = support.read_json(directory / "collection.json")
    assert any("runtime" in error["message"] for error in receipt["errors"])
    captures = runtime_observations(directory, receipt["runtime"], phases={"collection"})
    expected_files = sum(row["kind"] == "file" for row in identity["manifest"]["entries"])
    assert not captures["collection"]["matches_expected"]
    assert captures["collection"]["captured_files"] == expected_files + 1
    assert "declaration" in receipt, "malformed report bytes still reach declaration diagnosis"
    shutil.rmtree(root)
    before = support.snapshot_tree(prepared.session)
    draft = triage_draft(checkout.ws, checkout.meta["audit_id"], collection=collected["collection"])
    assert draft["context"]["runtime"] == receipt["runtime"]
    disposition = triage(checkout.ws, checkout.meta["audit_id"], collection=collected["collection"],
                         response=support.response_for(collected), actor="manager")
    retained = retain(checkout.ws, checkout.meta["audit_id"], triage=disposition["triage"], report=True)
    assert retained["published"] and (checkout.repo / checkout.meta["report_path"]).read_bytes() == prepared.report.read_bytes()
    exported = export_evidence(checkout.ws, checkout.meta["audit_id"], collection=collected["collection"],
                               selectors=["REPORT.md"], output=".scratch/runtime-package", actor="manager")
    manifest = support.read_json(checkout.repo / exported["package"])
    assert manifest["runtime"] == identity and package_inputs(checkout.repo, exported["package"])
    view = status(checkout.ws, checkout.meta["audit_id"])
    assert view["collections"][0]["runtime"]["observations"]["collection"]["matches_expected"] is False
    after = support.snapshot_tree(prepared.session)
    assert all(after[name] == digest for name, digest in before.items()), "no consumer rewrites captured evidence"
    # A sound record of a damaged exposed runtime is usable. Damage to the
    # retained observation instead invalidates every consumer, even report-only export.
    (directory / "runtime-collection/before.json").write_bytes(b"rewritten")
    actions = [
        lambda: triage_draft(checkout.ws, checkout.meta["audit_id"], collection=collected["collection"]),
        lambda: retain(checkout.ws, checkout.meta["audit_id"], triage=disposition["triage"], report=True),
        lambda: export_evidence(checkout.ws, checkout.meta["audit_id"], collection=collected["collection"],
                                selectors=["REPORT.md"], output=".scratch/corrupt-package", actor="manager"),
    ]
    for action in actions:
        with pytest.raises(StewartError) as caught:
            action()
        assert caught.value.reason == "evidence_tampered"
    view = status(checkout.ws, checkout.meta["audit_id"])
    assert view["collections"][0]["problems"][0]["reason"] == "evidence_tampered"


@pytest.mark.parametrize("change_at", ["none", "release", "before", "during"])
def test_release_and_execution_observe_runtime_at_each_boundary(tmp_path, run_cmd, supplied_runtime, change_at):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    prepared = support.prepared_experiment(checkout)
    root = Path(supplied_runtime[0]["root"])
    if change_at == "during":
        prepared.script.write_text(support.child_source(body=f"Path({str(root / 'added.py')!r}).write_text('added by child')"))
    if change_at == "release":
        (root / "stewart/verify_inputs.py").write_text("changed helper\n")
        with pytest.raises(StewartError) as caught:
            release(checkout.ws, checkout.meta["audit_id"], review=support.REVIEW, actor="manager")
        assert caught.value.reason == "runtime_mismatch"
        assert list((prepared.session / "releases").glob("runtime-*/capture.json"))
        assert not list((prepared.session / "releases").glob("*.json")), "no authorization after a runtime mismatch"
        return
    released = release(checkout.ws, checkout.meta["audit_id"], review=support.REVIEW, actor="manager")
    if change_at == "before":
        (root / "stewart/verify_inputs.py").write_text("changed helper\n")
    directory = prepared.session / "attempts" / released["release"]
    if change_at == "before":
        with pytest.raises(StewartError) as caught:
            run(checkout.ws, checkout.meta["audit_id"], release=released["release"])
        assert caught.value.reason == "runtime_mismatch"
        record = support.read_json(directory / "ATTEMPT.json")
    else:
        record = run(checkout.ws, checkout.meta["audit_id"], release=released["release"])["record"]
    observations = runtime_observations(directory, record["runtime"], phases={"before", "after"})
    assert observations["before"]["matches_expected"] == (change_at != "before")
    assert observations["after"]["matches_expected"] == (change_at == "none")
    assert record["process"]["launched"] == (change_at != "before")
    if change_at == "none":
        assert not record["errors"] and record["ledger"]["summary"]["control"]["mismatches"] == 1
    else:
        assert any("runtime" in error for error in record["errors"])
    if change_at == "during":
        assert (directory / "stdout.txt").read_text() == "done\n", "post-execution refusal must preserve child output"
    shutil.rmtree(root)
    exported = export_evidence(checkout.ws, checkout.meta["audit_id"], attempt=released["release"],
                               selectors=["ATTEMPT.json"], output=".scratch/attempt-package", actor="manager")
    assert package_inputs(checkout.repo, exported["package"])
    view = status(checkout.ws, checkout.meta["audit_id"])
    assert not view["attempts"][0]["problems"] and not view["releases"][0]["problems"]
