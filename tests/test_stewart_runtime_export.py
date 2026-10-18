"""Runtime packages preserve both pristine assets and independently observed damage."""
from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import tarfile

import pytest

from stewart._bootstrap import StewartError
from stewart._util import sha256_bytes
from stewart.collect import collect
from stewart.experiment import release, run
from stewart.handoff import export_evidence, package_inputs
import stewart_support as support

pytestmark = pytest.mark.system


@pytest.mark.parametrize("fault", ["none", "mismatch", "storage_failure"])
@pytest.mark.parametrize("kind", ["collection", "attempt"])
def test_failed_runtime_capture_preserves_independent_custody(tmp_path, run_cmd, monkeypatch, kind, fault):
    import errno
    from stewart.status import status
    from stewart.triage import triage_draft
    checkout = (support.make_checkout(tmp_path, run_cmd) if kind == "collection"
                else support.experiment_checkout(tmp_path, run_cmd))
    prepared = (support.prepared_session(checkout, report="preserved raw report\n") if kind == "collection"
                else support.prepared_experiment(checkout))
    phase = "collection" if kind == "collection" else "after"
    # Import-laziness controls can replace package attributes while consumers
    # retain their already imported function. Inject into that exact consumer.
    observing = (collect if kind == "collection" else run).__globals__["observe_phase"]
    original = observing.__globals__["capture_runtime"]
    selected = []
    def capture(identity, destination):
        if destination.name == f"runtime-{phase}":
            selected.append(str(destination))
            if fault == "storage_failure":
                raise OSError(errno.ENOSPC, "injected storage failure")
            if fault == "mismatch":
                (Path(identity["root"]) / "extra.py").write_text("extra")
        return original(identity, destination)
    monkeypatch.setitem(observing.__globals__, "capture_runtime", capture)
    if kind == "collection":
        result = collect(checkout.ws, "one-question", auditor_stopped="finished")
        source = {"collection": result["collection"]}
        selectors = ["REPORT.md"]
        assert triage_draft(checkout.ws, "one-question", **source)
        record = result["receipt"]
    else:
        released = release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
        result = run(checkout.ws, "one-question", release=released["release"])
        source = {"attempt": result["attempt"]}
        selectors = ["ledger.jsonl", "stdout.txt", "ATTEMPT.json"]
        record = result["record"]
        assert record["process"]["exit_code"] == 0
    reference = record["runtime"]["observations"][phase]
    assert len(selected) == 1, "the fault instrument must reach the selected production capture"
    assert ("error" in reference) is (fault == "storage_failure")
    exported = export_evidence(checkout.ws, "one-question", **source, selectors=selectors,
                               output=".scratch/raw-package", actor="manager")
    assert package_inputs(checkout.repo, exported["package"])
    view = status(checkout.ws, "one-question")
    item = view["collections" if kind == "collection" else "attempts"][0]
    observation = item["runtime"]["observations"][phase]
    assert observation["matches_expected"] is (fault == "none")
    assert observation["state"] == ("failed" if fault == "storage_failure" else "captured")
    if fault == "storage_failure":
        with pytest.raises(StewartError) as caught:
            export_evidence(checkout.ws, "one-question", **source,
                            selectors=[f"runtime-observation:{phase}"], output=".scratch/no-observation", actor="manager")
        assert caught.value.reason == "runtime_capture_unavailable"
        # Absence is not equivalent to the explicit recorded failure.
        from stewart.captured import runtime_observations
        broken = {**record["runtime"], "observations": {}}
        with pytest.raises(StewartError) as caught:
            runtime_observations(Path(prepared.prepared["session"]), broken, phases={phase})
        assert caught.value.reason == "runtime_capture_schema"


def exported(checkout):
    prepared = support.prepared_session(checkout, report="raw report\n")
    root = Path(prepared.prepared["runtime"]["root"])
    (root / "unexpected.py").write_text("raise RuntimeError('never execute captured code')\n")
    collection = collect(checkout.ws, "one-question", auditor_stopped="finished")
    shutil.rmtree(root)
    shutil.rmtree(prepared.worktree)
    result = export_evidence(checkout.ws, "one-question", collection=collection["collection"],
                             selectors=["REPORT.md", "runtime-assets", "runtime-observation:collection"],
                             output=".scratch/runtime-package", actor="fixture manager")
    return prepared, result, checkout.repo / result["package"]


def test_collection_runtime_groups_import_without_any_original_storage(tmp_path, run_cmd):
    checkout = support.make_checkout(tmp_path / "source", run_cmd)
    _, result, path = exported(checkout)
    manifest = support.read_json(path)
    assert len(manifest["entries"]) == 7
    assert {entry["selector"].split(':')[0] for entry in manifest["entries"]} == {
        "REPORT.md", "runtime-assets", "runtime-observation"}
    observed = next(entry for entry in manifest["entries"] if entry["selector"] == "runtime-observation:collection:capture.json")
    assert support.read_json(path.parent / observed["file"])["matches_expected"] is False
    receiving = support.make_checkout(tmp_path / "receiving", run_cmd)
    destination = receiving.repo / ".scratch/transferred"
    destination.parent.mkdir(exist_ok=True)
    shutil.copytree(path.parent, destination)
    shutil.rmtree(checkout.repo)
    inputs = package_inputs(receiving.repo, ".scratch/transferred/manifest.json")
    assert len(inputs) == 9 and all(item["custody"]["package"] == ".scratch/transferred/manifest.json" for item in inputs)


@pytest.mark.parametrize("fault", ["incomplete_assets", "incomplete_observation", "changed_asset", "changed_observation", "manifest_identity", "extra_archive_member", "unrelated_report"])
def test_runtime_package_checks_complete_groups_and_source_identity(checkout, fault):
    _, _, path = exported(checkout)
    manifest = support.read_json(path)
    source = support.read_json(path.parent / "source.json")
    def entry(selector):
        return next(item for item in manifest["entries"] if item["selector"] == selector)
    def replace(selector, data):
        item = entry(selector)
        (path.parent / item["file"]).write_bytes(data)
        item.update(sha256=sha256_bytes(data), size=len(data))
        return item["sha256"]
    if fault == "incomplete_assets":
        manifest["entries"].remove(entry("runtime-assets:files.tar"))
    elif fault == "incomplete_observation":
        manifest["entries"].remove(entry("runtime-observation:collection:after.json"))
    elif fault == "changed_asset":
        replace("runtime-assets:files.tar", b"substituted archive")
    elif fault == "changed_observation":
        replace("runtime-observation:collection:files.tar", b"substituted observation")
    elif fault == "manifest_identity":
        data = json.dumps({"schema_version": "invented", "entries": []}).encode()
        digest = replace("runtime-assets:manifest.json", data)
        manifest["runtime_assets"]["manifest_sha256"] = source["runtime_assets"]["manifest_sha256"] = digest
    elif fault == "extra_archive_member":
        item = entry("runtime-assets:files.tar")
        old = (path.parent / item["file"]).read_bytes()
        output = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(old), mode="r") as original, tarfile.open(fileobj=output, mode="w") as changed:
            for member in original.getmembers():
                changed.addfile(member, original.extractfile(member))
            member = tarfile.TarInfo("extra.py")
            member.size = 1
            changed.addfile(member, io.BytesIO(b"x"))
        digest = replace("runtime-assets:files.tar", output.getvalue())
        manifest["runtime_assets"]["archive_sha256"] = source["runtime_assets"]["archive_sha256"] = digest
    else:
        source["report_sha256"] = replace("REPORT.md", b"unrelated report prose changes\n")
    # Rehash the package's mutable controls deliberately. Runtime validation
    # must compare against file identity/membership, not merely the outer hash.
    data = json.dumps(source).encode()
    (path.parent / "source.json").write_bytes(data)
    manifest["source"]["receipt_sha256"] = sha256_bytes(data)
    path.write_text(json.dumps(manifest))
    if fault == "unrelated_report":
        assert len(package_inputs(checkout.repo, ".scratch/runtime-package/manifest.json")) == 9
    else:
        with pytest.raises(StewartError) as caught:
            package_inputs(checkout.repo, ".scratch/runtime-package/manifest.json")
        assert caught.value.reason in {"runtime_assets", "runtime_capture_schema", "package_binding", "evidence_tampered"}


def test_attempt_exports_both_observation_phases_after_live_removal(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    prepared = support.prepared_experiment(checkout)
    released = release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
    attempt = run(checkout.ws, "one-question", release=released["release"])
    assert attempt["record"]["ledger"]["summary"]["control"]["mismatches"] == 1
    shutil.rmtree(prepared.prepared["runtime"]["root"])
    shutil.rmtree(prepared.worktree)
    result = export_evidence(checkout.ws, "one-question", attempt=released["release"],
                             selectors=["ATTEMPT.json", "runtime-assets", "runtime-observation:before", "runtime-observation:after"],
                             output=".scratch/runtime-package", actor="manager")
    assert len(result["entries"]) == 11 and len(package_inputs(checkout.repo, result["package"])) == 13


@pytest.mark.parametrize("reference", [None, {"directory": "runtime-collection", "sha256": "invalid"}])
def test_report_only_import_still_validates_unselected_runtime_references(checkout, reference):
    _, _, path = exported(checkout)
    manifest = support.read_json(path)
    manifest["entries"] = [entry for entry in manifest["entries"] if entry["selector"] == "REPORT.md"]
    # A report-only package is valid without the runtime payload groups.
    path.write_text(json.dumps(manifest))
    assert len(package_inputs(checkout.repo, ".scratch/runtime-package/manifest.json")) == 3
    source = support.read_json(path.parent / "source.json")
    source["runtime"]["observations"]["collection"] = reference
    data = json.dumps(source).encode()
    (path.parent / "source.json").write_bytes(data)
    manifest["source"]["receipt_sha256"] = sha256_bytes(data)
    path.write_text(json.dumps(manifest))
    with pytest.raises(StewartError) as caught:
        package_inputs(checkout.repo, ".scratch/runtime-package/manifest.json")
    assert caught.value.reason == "runtime_capture_schema"
