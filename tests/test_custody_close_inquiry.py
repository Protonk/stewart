"""Characterize close's sidecar evidence boundary without performing removal.

These are inquiry comparisons, not a proposed cleanup contract. They retain
their observations outside session custody. Two comparisons stop a real close
at entry to _finish, after CLOSING.json freezes its inventory and before the
first removal or resource claim; the intervention is named in their evidence.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import tarfile

import pytest

from stewart.captured import runtime_observations, runtime_recovery
from stewart.close import close, close_plan
from stewart.collect import collect, inventory
from stewart.experiment import release
from stewart.runtime import recover_runtime
from stewart.status import status
from stewart.triage import triage
import stewart_support as support

pytestmark = pytest.mark.system


def _save(directory, name, value):
    (directory / f"{name}.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _triage(checkout):
    collected = collect(checkout.ws, checkout.meta["audit_id"], auditor_stopped="finished")
    disposition = triage(checkout.ws, checkout.meta["audit_id"], collection=collected["collection"],
                         response=support.response_for(collected), actor="fixture manager")
    return collected, disposition


def _freeze_without_removal(checkout, monkeypatch):
    """Exercise the production closing writer, intercept its removal boundary."""
    module = importlib.import_module("stewart.close")
    captured = {}

    class StoppedBeforeRemoval(Exception):
        pass

    def stop(repo, common, directory, closing, closing_sha256, **kwargs):
        captured.update(path=str(directory / "CLOSING.json"), record=closing,
                        sha256=closing_sha256,
                        intervention="test intercepted _finish before all removal and resource claims")
        raise StoppedBeforeRemoval

    with monkeypatch.context() as patch:
        patch.setattr(module, "_finish", stop)
        with pytest.raises(StoppedBeforeRemoval):
            close(checkout.ws, checkout.meta["audit_id"], actor="fixture manager")
    assert support.read_json(Path(captured["path"])) == captured["record"]
    assert not Path(captured["path"]).with_name("CLOSED.json").exists()
    return captured


@pytest.mark.parametrize("change_at", ["none", "unrelated", "before_collection", "after_collection"])
def test_custody_close_original_runtime_capture_boundary(checkout, tmp_path, change_at):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    record = support.read_json(prepared.session / "session.json")
    member = Path(record["runtime"]["root"]) / "stewart/verify_inputs.py"
    original = member.read_bytes()
    changed = original + b"\n# fixture runtime-only change, never executed\n"
    before_inventory = inventory(prepared.worktree)
    if change_at == "before_collection":
        member.write_bytes(changed)
    collected, disposition = _triage(checkout)
    directory = Path(collected["path"])
    observation = runtime_observations(directory, collected["receipt"]["runtime"],
                                       phases={"collection"})["collection"]
    reference = collected["receipt"]["runtime"]["observations"]["collection"]
    with tarfile.open(directory / reference["directory"] / "files.tar", mode="r:") as archive:
        stream = archive.extractfile("stewart/verify_inputs.py")
        assert stream is not None
        captured_bytes = stream.read()
    if change_at == "after_collection":
        member.write_bytes(changed)
    elif change_at == "unrelated":
        (Path(record["audit_dir"]) / "unrecorded-manager-note.txt").write_text("outside recorded member trees\n")
        checkout.git("commit", "--allow-empty", "-qm", "Unrelated manager advancement")
    before_records = support.snapshot_tree(prepared.session)
    view = status(checkout.ws, ident)
    planned = close_plan(checkout.ws, ident)
    _save(tmp_path, "01-collection", collected)
    _save(tmp_path, "02-verified-runtime-observation", observation)
    _save(tmp_path, "03-triage", disposition)
    _save(tmp_path, "04-status", view)
    _save(tmp_path, "05-close-plan", planned)
    assert inventory(prepared.worktree) == before_inventory
    assert support.snapshot_tree(prepared.session) == before_records
    assert observation["matches_expected"] == (change_at != "before_collection")
    assert observation["movement"] is False
    assert captured_bytes == (changed if change_at == "before_collection" else original)
    assert str(member.parent.parent) in planned["audit"]["removes"]["members"]
    if change_at in {"before_collection", "after_collection"}:
        assert {item["reason"] for item in view["attention"]} == {"runtime_unavailable"}
        assert planned["audit"]["refusal"]["reason"] == "close_unverified"
        assert planned["audit"]["refusal"]["exit_code"] == 3
        # Restoring readiness changes the close outcome without changing any
        # captured runtime evidence or its already-recorded disposition.
        member.write_bytes(original)
        restored = close_plan(checkout.ws, ident)
        _save(tmp_path, "06-restored-runtime-close-plan", restored)
        assert restored["audit"]["refusal"] is None
        assert support.snapshot_tree(prepared.session) == before_records
    else:
        assert planned["audit"]["refusal"] is None


def test_custody_close_recovered_runtime_drift_is_in_frozen_removal(checkout, tmp_path, monkeypatch):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    _triage(checkout)
    recovered = recover_runtime(checkout.ws, ident, actor="fixture manager")
    root = Path(recovered["runtime"]["root"])
    record = support.read_json(prepared.session / "session.json")
    _, captured_before = runtime_recovery(prepared.session, recovered["recovery"], record)
    baseline = close_plan(checkout.ws, ident)
    _save(tmp_path, "01-recovered-baseline", baseline)
    assert baseline["audit"]["refusal"] is None
    assert str(root) in baseline["audit"]["removes"]["members"]
    (Path(record["audit_dir"]) / "unrecorded-manager-note.txt").write_text("adjacent invariance control\n")
    invariant = close_plan(checkout.ws, ident)
    _save(tmp_path, "02-adjacent-invariance", invariant)
    assert invariant["audit"]["refusal"] is None
    assert invariant["audit"]["removes"] == baseline["audit"]["removes"]
    records = support.snapshot_tree(prepared.session)
    checkout_before = inventory(prepared.worktree)
    late = root / "only-after-recovery.txt"
    late.write_text("new inspection work absent from the recovery capture\n")
    _, captured_after = runtime_recovery(prepared.session, recovered["recovery"], record)
    changed = close_plan(checkout.ws, ident)
    _save(tmp_path, "03-recovery-capture", captured_after)
    _save(tmp_path, "04-changed-recovery-plan", changed)
    assert captured_after == captured_before and captured_after["matches_expected"] is True
    assert changed["audit"]["refusal"] is None
    assert changed["audit"]["removes"] == baseline["audit"]["removes"]
    assert inventory(prepared.worktree) == checkout_before
    assert support.snapshot_tree(prepared.session) == records
    frozen = _freeze_without_removal(checkout, monkeypatch)
    _save(tmp_path, "05-frozen-with-removal-intercepted", frozen)
    assert frozen["record"]["removal"] == changed["audit"]["removes"]
    assert str(root) in frozen["record"]["removal"]["members"]
    assert late.is_file() and prepared.worktree.is_dir() and prepared.session.is_dir()
    assert support.snapshot_tree(prepared.session) == records


def test_custody_close_nonempty_experiment_home_is_in_frozen_removal(tmp_path, run_cmd, monkeypatch):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    prepared = support.prepared_experiment(checkout)
    ident = checkout.meta["audit_id"]
    released = release(checkout.ws, ident, review=support.REVIEW, actor="fixture manager")
    home = Path(released["record"]["environment"]["HOME"])
    _triage(checkout)
    baseline = close_plan(checkout.ws, ident)
    _save(tmp_path, "01-unlaunched-release-plan", baseline)
    assert baseline["audit"]["refusal"] is None
    assert str(home.parent) in baseline["audit"]["removes"]["members"]
    before = inventory(prepared.worktree)
    records = support.snapshot_tree(prepared.session)
    home.mkdir(parents=True)
    late = home / "only-in-home.txt"
    late.write_text("fixture stand-in for child-writable bytes; no child ran\n")
    changed = close_plan(checkout.ws, ident)
    _save(tmp_path, "02-nonempty-home-plan", changed)
    _save(tmp_path, "03-home-observation", {"path": str(home), "inventory": inventory(home),
                                            "limit": "synthetic write to the released HOME; no child was executed"})
    assert changed["audit"]["refusal"] is None
    assert changed["audit"]["removes"] == baseline["audit"]["removes"]
    assert inventory(prepared.worktree) == before
    assert support.snapshot_tree(prepared.session) == records
    frozen = _freeze_without_removal(checkout, monkeypatch)
    _save(tmp_path, "04-frozen-with-removal-intercepted", frozen)
    assert frozen["record"]["removal"] == changed["audit"]["removes"]
    assert str(home.parent) in frozen["record"]["removal"]["members"]
    assert late.is_file() and prepared.worktree.is_dir() and prepared.session.is_dir()
    assert support.snapshot_tree(prepared.session) == records
