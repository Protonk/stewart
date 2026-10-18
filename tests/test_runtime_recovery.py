"""Asset recovery preserves historical bindings and never replaces a live runtime."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from stewart._bootstrap import StewartError, verify_runtime
from stewart.captured import runtime_recovery
from stewart.cli import main
from stewart.prepare import prepare
from stewart.runtime import recover_runtime
from stewart.status import status
from test_repository import assigned, ready_project


@pytest.mark.parametrize("live", ["changed", "missing"])
def test_recovery_uses_private_bytes_and_keeps_prior_selection(ready_project, live, capsys):
    ws, prompt, _ = assigned(ready_project)
    prepared = prepare(ws, prompt)
    session = Path(prepared["session"])
    original = (session / "session.json").read_bytes()
    record = json.loads(original)
    exposed = Path(record["runtime"]["root"])
    if live == "changed":
        (exposed / "stewart/ledger.py").write_text("changed exposed bytes\n")
    else:
        shutil.rmtree(exposed)
    shutil.rmtree(Path(record["worktree"]))
    first = recover_runtime(ws, "one-question", actor="fixture manager")
    recovered = Path(first["runtime"]["root"])
    assert recovered != exposed and not recovered.is_relative_to(session)
    verify_runtime(recovered, record["runtime"]["manifest"])
    assert (session / "session.json").read_bytes() == original
    if live == "changed":
        assert (exposed / "stewart/ledger.py").read_text() == "changed exposed bytes\n"
    else:
        assert not exposed.exists()
    first_bytes = Path(first["path"]).read_bytes()
    shutil.rmtree(recovered)
    verified, capture = runtime_recovery(session, first["recovery"], record)
    assert verified["materialized"] is True and capture["matches_expected"] is True
    view = status(ws, "one-question")
    assert view["runtime_recoveries"][0]["state"] == "recovered"
    assert view["preparation"]["state"] == "worktree_missing"
    assert not any(action["action"] in {"handoff", "launch"} for action in view["next_actions"])
    argv = ["--repo", str(ws.repo), "--workspace", ws.rel, "--json", "recover-runtime",
            "--audit-id", "one-question", "--actor", "fixture manager"]
    assert main(argv) == 0
    second = json.loads(capsys.readouterr().out)["result"]
    assert second["runtime"]["root"] != first["runtime"]["root"]
    assert Path(first["path"]).read_bytes() == first_bytes
    assert (session / "session.json").read_bytes() == original


@pytest.mark.parametrize("damage", ["missing", "changed", "linked", "unreadable", "directory"])
def test_missing_private_assets_refuse_despite_healthy_live_and_manager_copies(ready_project, damage):
    ws, prompt, _ = assigned(ready_project)
    prepared = prepare(ws, prompt)
    session = Path(prepared["session"])
    private = session / "runtime-pristine/files.tar"
    saved = private.with_name("saved.tar")
    private.rename(saved)
    if damage == "changed":
        private.write_bytes(b"different archive")
    elif damage == "linked":
        private.symlink_to(saved)
    elif damage == "unreadable":
        private.write_bytes(saved.read_bytes())
        private.chmod(0)
    elif damage == "directory":
        private.mkdir()
    with pytest.raises(StewartError) as caught:
        recover_runtime(ws, "one-question", actor="fixture manager")
    reason = "evidence_tampered" if damage == "changed" else "evidence_unavailable"
    assert caught.value.reason == reason and caught.value.retained
    receipts = list((session / "runtime-recoveries").glob("*/RECOVERY.json"))
    assert len(receipts) == 1
    record = json.loads(receipts[0].read_bytes())
    assert record["materialized"] is False and record["error"]["reason"] == reason
    assert not Path(record["runtime"]["identity"]["root"]).exists()
    view = status(ws, "one-question")
    assert view["runtime_recoveries"][0]["state"] == "failed"
    assert not view["preparation"]["pristine_runtime_available"]


def test_recovery_capture_tampering_is_visible_after_materialized_copy_is_removed(ready_project):
    ws, prompt, _ = assigned(ready_project)
    prepared = prepare(ws, prompt)
    result = recover_runtime(ws, "one-question", actor="fixture manager")
    shutil.rmtree(result["runtime"]["root"])
    directory = Path(result["path"]).parent
    (directory / "runtime-recovery/files.tar").write_bytes(b"changed retained capture")
    view = status(ws, "one-question")
    assert view["runtime_recoveries"][0]["state"] == "invalid"
    assert view["runtime_recoveries"][0]["problems"][0]["reason"] == "evidence_tampered"
    assert Path(prepared["runtime"]["root"]).exists(), "the live original cannot repair a corrupt recovery observation"


@pytest.mark.parametrize("field", ["activation", "error", "actor", "runtime"])
def test_malformed_recovery_stays_visible_without_repair_or_status_crash(ready_project, field):
    ws, prompt, _ = assigned(ready_project)
    prepare(ws, prompt)
    result = recover_runtime(ws, "one-question", actor="fixture manager")
    path = Path(result["path"])
    record = json.loads(path.read_bytes())
    del record[field]
    damaged = json.dumps(record).encode()
    path.write_bytes(damaged)
    view = status(ws, "one-question")
    item = view["runtime_recoveries"][0]
    assert item["state"] == "invalid" and item["problems"]
    assert path.read_bytes() == damaged


@pytest.mark.parametrize("damage", ["none", "unrelated", "missing", "changed", "added", "linked", "unreadable"])
def test_status_launch_suggestions_require_current_runtime(ready_project, damage):
    ws, prompt, _ = assigned(ready_project)
    prepared = prepare(ws, prompt)
    runtime = Path(prepared["runtime"]["root"])
    member = runtime / "stewart/ledger.py"
    if damage == "unrelated":
        (Path(prepared["worktree"]) / "unrelated.txt").write_text("unrelated")
    elif damage == "missing":
        shutil.rmtree(runtime)
    elif damage == "changed":
        member.write_text("changed")
    elif damage == "added":
        (runtime / "extra.py").write_text("extra")
    elif damage == "linked":
        saved = member.with_suffix(".saved")
        member.rename(saved)
        member.symlink_to(saved)
    elif damage == "unreadable":
        member.chmod(0)
    view = status(ws, "one-question")
    ready = damage in {"none", "unrelated"}
    assert view["preparation"]["state"] == ("ready" if ready else "runtime_unavailable")
    assert view["preparation"]["current_runtime"]["matches_expected"] is ready
    assert view["preparation"]["runtime"]["observations"]["preparation"]["matches_expected"]
    # Private assets stay recoverable, but the command is offered only when
    # the supplied runtime itself fails verification.
    assert view["preparation"]["pristine_runtime_available"]
    assert bool(view["preparation"]["runtime_recovery"]) is not ready
    assert view["exit_code"] == (0 if ready else 3)
    actions = {action["action"] for action in view["next_actions"]}
    assert ({"handoff", "launch"}.issubset(actions) if ready else not {"handoff", "launch"} & actions)
    assert "collect" in actions
