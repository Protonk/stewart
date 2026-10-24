"""Characterize scope obligations without endorsing the present restrictions.

The gitlink comparison holds supplemental bytes and population size fixed
while varying the approved path across a gitlink boundary. An unassigned
descendant is the firing control; an empty gitlink with the approved copy
elsewhere is the invariance case. After capture, following the returned remedy
distinguishes a repair from damage to a pinned input. The second comparison
measures acknowledgment-schema acceptance, never auditor launch execution.

Outputs are retained outside fixture custody in tmp_path. These are inquiry
baselines: a future contract change should deliberately update or retire them.
"""
from __future__ import annotations

import json
from pathlib import Path
import tarfile

import pytest

from stewart._bootstrap import StewartError
from stewart._util import sha256_bytes
from stewart.collect import collect
from stewart.coordination import record_launch
from stewart.prepare import prepare
from stewart.report_declaration import report_declaration
from stewart.verify_inputs import verify_inputs
from stewart.workspace import workspace
import stewart_support as support

pytestmark = pytest.mark.system

GITLINK = "vendor/component"
DESCENDANT = f"{GITLINK}/specimen.txt"
OUTSIDE = "ignored/specimen.txt"
SPECIMEN = b"The same supplied reference bytes in every comparison.\n"


def _save(directory: Path, name: str, value: dict) -> None:
    """Save actual operation output separately from the fixture's receipts."""
    (directory / f"{name}.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


@pytest.mark.parametrize("condition", ["approved_below", "approved_outside", "unassigned_below"])
def test_custody_scope_supplemental_gitlink_remedy(tmp_path, run_cmd, condition):
    checkout = support.make_checkout(tmp_path, run_cmd, ws_rel="reviews/deep/independent-question",
                                     name="unrelated project")
    checkout.git("update-index", "--add", "--cacheinfo", f"160000,{'1' * 40},{GITLINK}")
    checkout.git("commit", "-qm", "Fixture target with an unpopulated gitlink")
    checkout.meta["target_commit"] = checkout.git("rev-parse", "HEAD")
    ident = checkout.meta["audit_id"]
    supplemental = DESCENDANT if condition == "approved_below" else OUTSIDE
    source = checkout.repo / supplemental
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(SPECIMEN)
    checkout.meta["supplemental_inputs"] = [
        {"path": supplemental, "sha256": sha256_bytes(SPECIMEN), "provenance": "inquiry fixture reference"},
    ]
    notes = checkout.ws.scratch_prefix(ident) + "notes"
    checkout.meta["scratch_paths"] = [notes]
    revision = checkout.prompt_commit()
    prepared = prepare(checkout.ws, revision, submodules_acknowledged=True)
    _save(tmp_path, "01-preparation", prepared)
    worktree = Path(prepared["worktree"])
    session = Path(prepared["session"])
    record = support.read_json(session / "session.json")
    _save(tmp_path, "02-assigned-population", {"condition": condition, "assignment": record["assignment"],
                                              "inputs": record["inputs"], "submodules": record["submodules"]})
    assert (worktree / supplemental).read_bytes() == SPECIMEN
    assert {item["path"] for item in record["inputs"]} == {"input.txt", supplemental}
    if condition == "unassigned_below":
        (worktree / DESCENDANT).write_bytes(SPECIMEN)
    elif condition == "approved_outside":
        assert not any((worktree / GITLINK).iterdir()), "the control gitlink remains unpopulated"

    auditor_ws = workspace(worktree, checkout.ws.rel)
    arguments = dict(expected_worktree=worktree, launch_prompt_commit=revision,
                     prompt_sha256=prepared["prompt_sha256"], launch_token=prepared["launch_token"])
    inputs = verify_inputs(auditor_ws, **arguments)
    _save(tmp_path, "03-input-verification", inputs)
    assert (inputs["selected"], inputs["matched"], inputs["failed"], inputs["exit_code"]) == (2, 2, 0, 0)
    report_declaration(auditor_ws, "start", **arguments)
    report_declaration(auditor_ws, "set", completion="complete", report_kind="answer", **arguments)
    report = worktree / checkout.meta["report_path"]
    report_bytes = report.read_bytes()
    (tmp_path / "04-declared-report.md").write_bytes(report_bytes)
    checked = report_declaration(auditor_ws, "check", **arguments)
    _save(tmp_path, "04-declaration-check", checked)
    captured = collect(checkout.ws, ident, auditor_stopped="finished")
    _save(tmp_path, "05-collection", captured)

    expected = set()
    if condition != "approved_outside":
        expected.add(f"gitlink_contents:{GITLINK}")
    if condition == "unassigned_below":
        expected.add(f"unexpected_path:{DESCENDANT}")
    gaps = {gap["id"]: gap for gap in checked["gaps"]}
    assert set(gaps) == {gap["id"] for gap in captured["gaps"]} == expected
    assert checked["declaration"]["status"] == captured["receipt"]["declaration"]["status"] == "valid"
    assert checked["declaration"]["declaration"]["completion"] == "complete"
    assert checked["exit_code"] == captured["exit_code"] == (1 if expected else 0)
    archived_paths = {supplemental}
    if condition != "approved_outside":
        archived_paths.add(DESCENDANT)
    with tarfile.open(Path(captured["path"]) / "files.tar") as archive:
        for index, path in enumerate(sorted(archived_paths)):
            member = archive.extractfile(path)
            assert member is not None, f"capture must preserve {path} before any remedy"
            data = member.read()
            (tmp_path / f"06-captured-specimen-{index}.bin").write_bytes(data)
            assert data == SPECIMEN

    if condition == "approved_outside":
        return
    remedy = gaps[f"gitlink_contents:{GITLINK}"]["fix"]
    assert "move these files under a declared scratch path" in remedy
    destination = worktree / notes / "moved-specimen.txt"
    (worktree / DESCENDANT).rename(destination)
    moved_inputs = verify_inputs(auditor_ws, **arguments)
    moved_check = report_declaration(auditor_ws, "check", **arguments)
    _save(tmp_path, "07-followed-remedy", {"issued_remedy": remedy, "from": DESCENDANT,
                                         "to": str(destination.relative_to(worktree)),
                                         "inputs": moved_inputs, "declaration_check": moved_check})
    assert destination.read_bytes() == SPECIMEN and report.read_bytes() == report_bytes
    assert moved_check["declaration"] == checked["declaration"], "moving evidence does not amend the claim"
    if condition == "approved_below":
        assert (moved_inputs["selected"], moved_inputs["matched"], moved_inputs["failed"]) == (2, 1, 1)
        assert moved_inputs["exit_code"] == moved_check["exit_code"] == 3
        missing = next(row for row in moved_inputs["inputs"] if row["path"] == supplemental)
        assert missing["observed_kind"] == "missing" and "not yours to repair" in missing["fix"]
        assert {gap["id"] for gap in moved_check["gaps"]} == {f"supplemental_missing:{DESCENDANT}"}
    else:
        assert moved_inputs == inputs, "moving an unassigned descendant does not change approved inputs"
        assert moved_check["gaps"] == [] and moved_check["exit_code"] == 0


def test_custody_scope_human_handoff_requires_model_shaped_metadata(tmp_path, run_cmd):
    """A recorded handoff claim is not execution or evidence of an auditor."""
    checkout = support.make_checkout(tmp_path, run_cmd, ws_rel="reviews/another/independent-question")
    prepared = support.prepared_session(checkout, report=None)
    ident = checkout.meta["audit_id"]
    records_before = support.snapshot_tree(prepared.session)
    common = {"style": "other", "actor": "fixture manager",
              "note": "Fixture claim: handoff supplied to a human reviewer; no auditor was launched."}
    for label, fields, required in (
        ("model-and-effort-omitted", {}, "model"),
        ("effort-omitted", {"model": "not applicable: human"}, "effort"),
    ):
        with pytest.raises(StewartError) as caught:
            record_launch(checkout.ws, ident, **common, **fields)
        _save(tmp_path, f"01-{label}", {"request": {**common, **fields}, "refusal": caught.value.to_json()})
        assert caught.value.reason == "coordination_schema"
        assert f"{required} must be nonempty text" in str(caught.value)
        assert support.snapshot_tree(prepared.session) == records_before

    # Explicit not-applicable strings expose the representational workaround;
    # acceptance does not verify that a human received or read anything.
    human = record_launch(checkout.ws, ident, **common,
                          model="not applicable: human", effort="not applicable: human")
    _save(tmp_path, "02-human-with-explicit-placeholders", human)
    ordinary = record_launch(checkout.ws, ident, style="subagent", actor="fixture manager",
                             model="fixture model", effort="fixture effort",
                             note="Ordinary agent metadata; acknowledgment only, no execution.")
    _save(tmp_path, "03-ordinary-agent-acknowledgment", ordinary)
    for result in (human, ordinary):
        assert result["record"]["command"] is None and result["record"]["harness"] is None
        assert "Stewart launched nothing and observed no auditor" in result["record"]["meaning"]
        assert result["record"]["launch_token"] == prepared.prepared["launch_token"]
    assert len(list((prepared.session / "launches").glob("*.json"))) == 2
    assert not prepared.report.exists()
