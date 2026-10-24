"""Characterize selected evidence availability without endorsing the present gate.

The comparison holds report bytes and their collection receipt fixed while a
retained runtime observation is damaged. An explicitly recorded initial capture
failure and a package exported before damage distinguish whole-capture integrity
from the recoverability of the selected report. Future semantic implementation
must deliberately revise or retire these baseline expectations.
"""
from __future__ import annotations

import errno
import json
from pathlib import Path

import pytest

from stewart._bootstrap import StewartError
from stewart._util import sha256_bytes
from stewart.collect import collect
from stewart.handoff import export_evidence, package_inputs
import stewart_support as support

pytestmark = pytest.mark.system


def _save(directory: Path, name: str, value: dict | list) -> None:
    """Keep inquiry output outside the fixture's custody records."""
    (directory / f"{name}.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


@pytest.mark.parametrize("condition", ["intact", "recorded_capture_failure", "damaged_capture"])
def test_custody_identity_report_export_dependency(tmp_path, run_cmd, monkeypatch, condition):
    checkout = support.make_checkout(tmp_path, run_cmd, ws_rel="reviews/nested/question")
    raw_report = "Independently captured report; its declaration is intentionally absent.\n"
    prepared = support.prepared_session(checkout, report=raw_report)
    ident = checkout.meta["audit_id"]
    runtime_root = Path(prepared.prepared["runtime"]["root"])
    exposed_before = support.snapshot_tree(runtime_root)

    # Reach the function retained by the production collector, even if another
    # test replaced the lazy package attribute while checking import behavior.
    observing = collect.__globals__["observe_phase"]
    original = observing.__globals__["capture_runtime"]
    selected = []

    def capture(identity, destination):
        if destination.name == "runtime-collection":
            selected.append(str(destination))
            if condition == "recorded_capture_failure":
                raise OSError(errno.ENOSPC, "injected initial runtime capture storage failure")
        return original(identity, destination)

    with monkeypatch.context() as patch:
        patch.setitem(observing.__globals__, "capture_runtime", capture)
        collected = collect(checkout.ws, ident, auditor_stopped="finished")
    directory = Path(collected["path"])
    receipt_path, report_path = directory / "collection.json", directory / "REPORT.md"
    receipt_bytes, report_bytes = receipt_path.read_bytes(), report_path.read_bytes()
    receipt_digest, report_digest = sha256_bytes(receipt_bytes), sha256_bytes(report_bytes)
    reference = collected["receipt"]["runtime"]["observations"]["collection"]
    _save(tmp_path, "01-collection", {
        "condition": condition, "collection": collected["collection"], "path": str(directory),
        "collection_sha256": receipt_digest, "report_sha256": report_digest,
        "report_status": collected["receipt"]["report_status"],
        "runtime_observation": reference, "errors": collected["receipt"]["errors"],
        "gaps": collected["gaps"], "exit_code": collected["exit_code"],
        "instrumented_capture_destinations": selected,
    })
    assert selected == [str(directory / "runtime-collection")], "the capture fault must reach production"
    assert report_bytes == raw_report.encode() and report_digest == collected["receipt"]["report_sha256"]
    assert ("error" in reference) is (condition == "recorded_capture_failure")
    if condition == "recorded_capture_failure":
        assert reference["error"]["reason"] == "runtime_capture_io"
        assert any(error["reason"] == "runtime_observation" for error in collected["receipt"]["errors"])

    before_export = export_evidence(checkout.ws, ident, collection=collected["collection"],
                                    selectors=["REPORT.md"], output=".scratch/package-before", actor="manager")
    _save(tmp_path, "02-export-before", before_export)
    before_inputs = package_inputs(checkout.repo, before_export["package"])
    _save(tmp_path, "03-import-before", before_inputs)
    package_root = Path(before_export["manifest"]).parent
    package_before = support.snapshot_tree(package_root)
    manifest = support.read_json(Path(before_export["manifest"]))
    assert [entry["selector"] for entry in manifest["entries"]] == ["REPORT.md"]
    assert manifest["source"]["receipt_sha256"] == receipt_digest
    assert (package_root / "source.json").read_bytes() == receipt_bytes
    assert (package_root / manifest["entries"][0]["file"]).read_bytes() == report_bytes

    perturbation = {"condition": condition, "changed": None}
    captured_member = directory / "runtime-collection/before.json"
    if condition == "damaged_capture":
        original_member = captured_member.read_bytes()
        # Deliberate damage to disposable fixture evidence, never a production
        # repair or an update of its historical pin. Report and receipt stay put.
        captured_member.write_bytes(b"damaged retained runtime observation\n")
        perturbation["changed"] = {"path": str(captured_member),
                                   "before_sha256": sha256_bytes(original_member),
                                   "after_sha256": sha256_bytes(captured_member.read_bytes())}
        assert perturbation["changed"]["before_sha256"] != perturbation["changed"]["after_sha256"]
    _save(tmp_path, "04-perturbation", perturbation)
    records_before_consumer = support.snapshot_tree(prepared.session)

    after_destination = checkout.repo / ".scratch/package-after"
    try:
        after_export = export_evidence(checkout.ws, ident, collection=collected["collection"],
                                       selectors=["REPORT.md"], output=".scratch/package-after", actor="manager")
    except StewartError as exc:
        after = {"state": "refused", "error": exc.to_json()}
    else:
        after = {"state": "exported", "result": after_export,
                 "imported_inputs": package_inputs(checkout.repo, after_export["package"])}
    _save(tmp_path, "05-export-after", after)
    if condition == "damaged_capture":
        assert after["state"] == "refused" and after["error"]["reason"] == "evidence_tampered"
        assert not after_destination.exists(), "the refusal precedes package publication"
    else:
        assert after["state"] == "exported"

    # Importing the previously exported package needs only its selected bytes
    # and pinned source receipt; the omitted runtime group stays omitted.
    after_inputs = package_inputs(checkout.repo, before_export["package"])
    _save(tmp_path, "06-import-existing-package-after", after_inputs)
    records_after_consumer = support.snapshot_tree(prepared.session)
    invariance = {
        "collection_sha256_before": receipt_digest,
        "collection_sha256_after": sha256_bytes(receipt_path.read_bytes()),
        "report_sha256_before": report_digest,
        "report_sha256_after": sha256_bytes(report_path.read_bytes()),
        "same_existing_package_inputs": after_inputs == before_inputs,
        "same_existing_package_bytes": support.snapshot_tree(package_root) == package_before,
        "same_exposed_runtime": support.snapshot_tree(runtime_root) == exposed_before,
        "existing_session_records_unchanged_by_consumers": all(
            records_after_consumer.get(name) == digest for name, digest in records_before_consumer.items()),
    }
    _save(tmp_path, "07-invariance", invariance)
    assert receipt_path.read_bytes() == receipt_bytes and report_path.read_bytes() == report_bytes
    assert all(invariance[key] for key in (
        "same_existing_package_inputs", "same_existing_package_bytes", "same_exposed_runtime",
        "existing_session_records_unchanged_by_consumers"))
