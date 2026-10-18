"""Coordination records, tool identity and the status facts added after two rehearsals.

Each test pairs the property being read with one that must be ignored: a
package digest that moves on module bytes but not on a note beside them; a
release that a collection captured against one it did not; a child that accepts
the wrapper's output area against one that demands its absence; a pasted
command that survives a decoy package in the caller's directory.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
import tarfile

import pytest

from stewart.cli import EXIT_OK, main
from stewart import _util as _hash
from stewart.collect import collect
from stewart.coordination import record_launch, record_message
from stewart._bootstrap import StewartError
from stewart.experiment import release, run
from stewart.handoff import export_evidence
from stewart.prepare import prepare
from stewart.session import package_identity, tool_identity
from stewart.status import status
from stewart.triage import retain, triage
import stewart_support as support
from stewart_support import MANIFEST, PREDICTION, SCRIPT, read_json, response_for, snapshot_tree

pytestmark = pytest.mark.system


def test_package_identity_reads_distribution_bytes_and_git_state(installation, tmp_path, run_cmd):
    package = installation / "stewart"
    outside = package_identity(package)
    assert outside["modules"] == 29 and len(outside["package_sha256"]) == 64
    assert outside["version"] == "0.1.0" and len(outside["resources"]) == 9
    assert outside["commit"] is None and outside["dirty"] is None
    (installation / "NOTE-PLAN.md").write_text("ephemeral note\n")
    (package / "__pycache__").mkdir()
    (package / "__pycache__" / "_json.cpython-314.pyc").write_bytes(b"\x00")
    assert package_identity(package)["package_sha256"] == outside["package_sha256"], (
        "outside notes and source-installation caches are not executable runtime members")
    member = package / "_json.py"
    member.write_text(member.read_text() + "\n# changed source\n")
    changed = package_identity(package)
    assert changed["package_sha256"] != outside["package_sha256"]
    run_cmd(["git", "init", "-q", "-b", "main"], cwd=installation, check=True)
    run_cmd(["git", "add", "."], cwd=installation, check=True)
    run_cmd(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "pkg"],
            cwd=installation, check=True)
    committed = package_identity(package)
    assert committed["package_sha256"] == changed["package_sha256"]
    assert committed["commit"] and len(committed["commit"]) == 40 and committed["dirty"] is False
    (installation / "elsewhere.txt").write_text("dirty outside the package\n")
    assert package_identity(package)["dirty"] is False
    resource = package / "resources/AUDITOR.md"
    resource.write_text(resource.read_text() + "\nChanged policy.\n")
    modified = package_identity(package)
    assert modified["dirty"] is True and modified["package_sha256"] != committed["package_sha256"]
    assert modified["resources"] != committed["resources"]
    me = tool_identity()
    assert me["package"].endswith("stewart") and me["modules"] == 29


def test_every_record_names_the_build_that_wrote_it(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    ident = checkout.meta["audit_id"]
    me = tool_identity()
    (exp.worktree / checkout.meta["report_path"]).write_text("Status: complete\nConstructed.\n")
    launched = record_launch(checkout.ws, ident, style="subagent", model="opus", effort="max", actor="manager")
    messaged = record_message(checkout.ws, ident, direction="to-auditor", text="ruling", actor="manager")
    collected = collect(checkout.ws, ident, auditor_stopped="finished")
    disposition = triage(checkout.ws, ident, collection=collected["collection"],
                         response=response_for(collected), actor="manager")
    retained = retain(checkout.ws, ident, triage=disposition["triage"], report=True)
    released = release(checkout.ws, ident, review=support.REVIEW, actor="manager")
    attempted = run(checkout.ws, ident, release=released["release"], timeout=60)
    exported = export_evidence(checkout.ws, ident, attempt=released["release"], selectors=["ATTEMPT.json"],
                               output=".scratch/identity-package", actor="manager")
    records = {
        "session.json": exp.session / "session.json",
        "STARTED.json": Path(collected["path"]) / "STARTED.json",
        "collection.json": Path(collected["path"]) / "collection.json",
        "launch": Path(launched["path"]),
        "message": Path(messaged["path"]),
        "triage": Path(disposition["path"]),
        "retention": Path(retained["path"]),
        "release": Path(released["path"]),
        "ATTEMPT.json": Path(attempted["path"]) / "ATTEMPT.json",
        "manifest.json": checkout.repo / exported["package"],
    }
    for name, location in records.items():
        stamp = read_json(location).get("stewart")
        assert isinstance(stamp, dict), f"{name} carries no tool identity"
        assert stamp["package_sha256"] == me["package_sha256"] and stamp["package"] == me["package"], name
        assert set(stamp) == {"package", "version", "modules", "members", "resources", "package_sha256", "commit", "dirty"}, name
    view = status(checkout.ws, ident)
    assert view["tool"]["package_sha256"] == me["package_sha256"]
    assert view["session"]["stewart"]["package_sha256"] == me["package_sha256"]
    assert view["session"]["same_build_as_viewer"] is True
    # Control: a session stamped by another build is reported as such, never rewritten.
    record_path = exp.session / "session.json"
    original = read_json(record_path)
    foreign = dict(original, stewart=dict(original["stewart"], package_sha256="0" * 64))
    record_path.write_text(json.dumps(foreign, indent=2, sort_keys=True) + "\n")
    before = snapshot_tree(exp.session)
    view = status(checkout.ws, ident)
    assert view["session"]["same_build_as_viewer"] is False and view["session"]["supported"] is True
    assert snapshot_tree(exp.session) == before
    unstamped = dict(original)
    del unstamped["stewart"]
    record_path.write_text(json.dumps(unstamped, indent=2, sort_keys=True) + "\n")
    assert status(checkout.ws, ident)["session"]["same_build_as_viewer"] is None, "an unstamped record is unknown, not foreign"


def test_launch_and_message_records_are_acknowledgments_that_status_lists(checkout, capsys):
    ident = checkout.meta["audit_id"]
    prepared = support.prepared_session(checkout, report=None)
    assert (prepared.session / "LAUNCH.md").read_text().count("absolute paths rooted there") == 1, (
        "the handoff must tell a harness that starts elsewhere how to behave")
    view = status(checkout.ws, ident)
    assert [a["action"] for a in view["next_actions"]] == ["handoff", "launch", "collect"]
    for bad in ({"style": "cloud"}, {"model": ""}, {"effort": " "}, {"actor": ""}):
        with pytest.raises(StewartError) as refused:
            record_launch(checkout.ws, ident, **{"style": "terminal", "model": "opus", "effort": "max",
                                                 "actor": "manager", **bad})
        assert refused.value.reason == "coordination_schema", bad
    assert not (prepared.session / "launches").exists(), "a refused record writes nothing"
    launched = record_launch(checkout.ws, ident, style="subagent", model="opus", effort="max", actor="manager",
                             note="Agent tool; inherits the manager's cwd")
    record = launched["record"]
    assert record["launch_token"] == prepared.prepared["launch_token"]
    assert record["prompt_commit"] == prepared.revision and record["style"] == "subagent"
    assert "launched nothing" in record["meaning"]
    view = status(checkout.ws, ident)
    assert [a["action"] for a in view["next_actions"]] == ["handoff", "collect"], "a recorded launch is not asked for again"
    assert view["launches"][0]["name"] == launched["launch"] and view["launches"][0]["note"].startswith("Agent tool")
    for bad in ({"direction": "sideways"}, {"text": ""}):
        with pytest.raises(StewartError) as refused:
            record_message(checkout.ws, ident, **{"direction": "to-auditor", "text": "ruling", "actor": "manager", **bad})
        assert refused.value.reason == "coordination_schema", bad
    sent = record_message(checkout.ws, ident, direction="to-auditor", actor="manager", channel="harness message",
                          text="Ruling: select_terminal inside inspect_blob is inside the grant.\nAmend nothing else.")
    received = record_message(checkout.ws, ident, direction="from-auditor", actor="manager",
                              text="Amendment applied; check passed.")
    view = status(checkout.ws, ident)
    assert [m["name"] for m in view["messages"]] == [sent["message"], received["message"]]
    assert view["messages"][0]["channel"] == "harness message" and "not authenticated" in sent["record"]["meaning"]
    prepared.report.write_text("Status: partial\n")
    collect(checkout.ws, ident, auditor_stopped="finished")
    view = status(checkout.ws, ident)
    assert not any("no launch record" in item for item in view["outstanding"]), (
        "the outstanding note is for sessions whose launch was never recorded")
    base = ["--repo", str(checkout.repo), "--workspace", checkout.ws.rel]
    assert main(base + ["launch", "--audit-id", ident, "--style", "terminal", "--model", "opus", "--effort",
                        "max", "--actor", "cli"]) == EXIT_OK
    assert main(base + ["message", "--audit-id", ident, "--direction", "from-auditor", "--text", "hand-back",
                        "--actor", "cli"]) == EXIT_OK
    # The collected report has no declaration: an untriaged gap is news (exit 1).
    assert main(base + ["status", "--audit-id", ident]) == 1
    out = capsys.readouterr().out
    assert "Launch recorded:" in out and "observed no auditor" in out
    assert "Message recorded:" in out and "not proof it was read" in out
    assert "Launches: 2 (manager acknowledgments, not observations)" in out
    assert "Messages: 3 (as relayed by the manager)" in out
    assert "to-auditor by manager: Ruling: select_terminal" in out and "\nAmend" not in out


def test_release_waits_for_a_collection_and_status_names_which_collection_captured_the_frozen_bytes(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    ident = checkout.meta["audit_id"]
    (exp.worktree / checkout.meta["report_path"]).write_text("Status: complete\nConstructed.\n")
    view = status(checkout.ws, ident)
    assert view["experiment"]["state"] == "awaiting_review"
    assert not any(a["action"] == "release" for a in view["next_actions"]), (
        "a release before any collection would freeze bytes nothing has captured")
    assert any("no collection has captured" in item for item in view["outstanding"])
    first = collect(checkout.ws, ident, auditor_stopped="finished")
    view = status(checkout.ws, ident)
    assert any(a["action"] == "release" for a in view["next_actions"])
    released = release(checkout.ws, ident, review=support.REVIEW, actor="manager")
    view = status(checkout.ws, ident)
    item = next(r for r in view["releases"] if r["name"] == released["release"])
    assert item["frozen_artifacts"] == [SCRIPT, PREDICTION], (
        "the fixture's manifest is committed, like the ledger module; neither can be captured unchanged")
    assert MANIFEST in released["record"]["frozen"], "the manifest is still frozen, just not a capture candidate"
    assert item["captured_in"] == [first["collection"]] and item["uncaptured_artifacts"] == []
    assert "grant" not in item and not any("artifacts without verified captures" in o for o in view["outstanding"])
    # Pair: the same release flow with one frozen artifact edited after the capture.
    run(checkout.ws, ident, release=released["release"], timeout=60)
    (exp.worktree / PREDICTION).write_text("revised after the first capture\n")
    with pytest.raises(StewartError) as refused:
        release(checkout.ws, ident, review=support.REVIEW, actor="manager")
    assert refused.value.reason == "destination_exists", "the consumed release's output area is still in the worktree"
    assert refused.value.retained == [str(exp.worktree / support.OUTPUT)]
    assert any("collect" in step and "by hand" in step for step in refused.value.next_steps)
    assert any("fresh audit ID" in step for step in refused.value.next_steps)
    import shutil
    second = collect(checkout.ws, ident, auditor_stopped="finished")  # captures the run outputs and the edit
    shutil.rmtree(exp.worktree / support.OUTPUT)
    (exp.worktree / PREDICTION).write_text("revised again, after every capture\n")
    again = release(checkout.ws, ident, review=support.REVIEW, actor="manager")
    view = status(checkout.ws, ident)
    item = next(r for r in view["releases"] if r["name"] == again["release"])
    assert item["captured_in"] == [] and item["uncaptured_artifacts"] == [PREDICTION]
    assert any(f"release {again['release']} has artifacts without verified captures: {PREDICTION}" in o
               for o in view["outstanding"])
    third = collect(checkout.ws, ident, auditor_stopped="finished")
    item = next(r for r in status(checkout.ws, ident)["releases"] if r["name"] == again["release"])
    assert item["captured_in"] == [third["collection"]] and item["uncaptured_artifacts"] == []
    assert second["collection"] not in item["captured_in"], "an earlier capture of different bytes does not count"


@pytest.mark.parametrize("archive_failure", [False, True], ids=["captured", "archive-interrupted"])
def test_release_capture_requires_recoverable_bytes_and_ignores_live_edits(tmp_path, run_cmd, monkeypatch,
                                                                          archive_failure):
    """Discovery and release see identical bytes; only archive completion varies.

    The export is checked against the constructed bytes, not against status's
    digests. Changing the live script must affect neither retained-byte claim.
    """
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    ident = checkout.meta["audit_id"]
    original = exp.script.read_bytes()
    report = exp.worktree / checkout.meta["report_path"]
    report.write_text("Construction only; the script has not run.\n")
    released = release(checkout.ws, ident, review=support.REVIEW, actor="manager")
    addfile = tarfile.TarFile.addfile

    def interrupt_script_archive(bundle, member, fileobj=None):
        if member.name == SCRIPT:
            raise OSError("injected archive write failure before script preservation")
        return addfile(bundle, member, fileobj)

    with monkeypatch.context() as fault:
        if archive_failure:
            fault.setattr(tarfile.TarFile, "addfile", interrupt_script_archive)
        collected = collect(checkout.ws, ident, auditor_stopped="finished")
    receipt = collected["receipt"]
    discovered = next(item for item in receipt["checkout"]["files"] if item["path"] == SCRIPT)
    assert discovered["sha256"] == released["record"]["frozen"][SCRIPT], (
        "both trials must discover exactly the script frozen by the release")
    assert exp.script.read_bytes() == original, "archive failure must not change the source operand"
    assert bool(receipt["errors"]) is archive_failure
    assert bool(receipt.get("archive_sha256")) is not archive_failure

    observations = []
    for phase in ("original-live-file", "changed-live-file"):
        if phase == "changed-live-file":
            exp.script.write_bytes(b'raise RuntimeError("live file must not supply captured evidence")\n')
        before = snapshot_tree(exp.session)
        view = status(checkout.ws, ident)
        assert snapshot_tree(exp.session) == before, "status must preserve the partial and successful captures"
        item = next(r for r in view["releases"] if r["name"] == released["release"])
        export_reason = None
        try:
            exported = export_evidence(checkout.ws, ident, collection=collected["collection"],
                                       selectors=[f"files.tar:{SCRIPT}"], output=f".scratch/export-{phase}",
                                       actor="capture reviewer")
        except StewartError as exc:
            export_reason = exc.reason
        else:
            manifest = checkout.repo / exported["package"]
            entry, = read_json(manifest)["entries"]
            assert (manifest.parent / entry["file"]).read_bytes() == original, (
                "recoverability means the exported bytes equal the constructed original")
        observations.append({"phase": phase, "captured_in": item["captured_in"],
                             "uncaptured_artifacts": item["uncaptured_artifacts"],
                             "capture_problems": item["capture_problems"],
                             "export_refusal": export_reason})
    (tmp_path / "capture-observations.json").write_text(json.dumps({
        "archive_failure": archive_failure, "collection": collected["collection"],
        "collection_errors": receipt["errors"], "observations": observations,
    }, indent=2) + "\n")
    for observation in observations:
        assert observation["export_refusal"] == ("support_unavailable" if archive_failure else None)
        assert observation["captured_in"] == ([] if archive_failure else [collected["collection"]]), (
            "matching discovery digests cannot establish preservation when the archive never captured the script; "
            f"status/export observation: {observation}")
        assert observation["uncaptured_artifacts"] == ([SCRIPT, PREDICTION] if archive_failure else [])
        assert {p["reason"] for p in observation["capture_problems"]} == (
            {"support_unavailable"} if archive_failure else set())
    if archive_failure:
        failed_receipt = (Path(collected["path"]) / "collection.json").read_bytes()
        exp.script.write_bytes(original)
        recovered = collect(checkout.ws, ident, auditor_stopped="finished")
        item, = status(checkout.ws, ident)["releases"]
        assert item["captured_in"] == [recovered["collection"]] and item["uncaptured_artifacts"] == [], (
            "a new successful collection can preserve the release while the failed collection stays visible")
        assert {p["collection"] for p in item["capture_problems"]} == {collected["collection"]}
        assert (Path(collected["path"]) / "collection.json").read_bytes() == failed_receipt


@pytest.mark.parametrize("change", ["missing", "corrupt", "symlink", "fifo"])
def test_release_capture_rechecks_archive_availability_without_rewriting_history(tmp_path, run_cmd, capsys, change):
    """A historical capture and its unchanged receipt do not certify current availability."""
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    ident = checkout.meta["audit_id"]
    (exp.worktree / checkout.meta["report_path"]).write_text("Captured construction report.\n")
    collected = collect(checkout.ws, ident, auditor_stopped="finished")
    release(checkout.ws, ident, review=support.REVIEW, actor="manager")
    assert status(checkout.ws, ident)["releases"][0]["captured_in"] == [collected["collection"]]
    archive = Path(collected["path"]) / "files.tar"
    # Preserve the original outside the session, including a valid link target:
    # following that link would wrongly make the symlink control look healthy.
    original_archive = tmp_path / "original-files.tar"
    archive.rename(original_archive)
    if change == "corrupt":
        archive.write_bytes(b"damaged archive")
    elif change == "symlink":
        archive.symlink_to(original_archive)
    elif change == "fifo":
        os.mkfifo(archive)
    before = snapshot_tree(exp.session)
    # Bound the first read in a separate process: a regression that opens the
    # FIFO for blocking input must fail the test instead of hanging the suite.
    observed = run_cmd([sys.executable, "-m", "stewart", "--repo", str(checkout.repo),
                        "--workspace", checkout.ws.rel, "--json", "status", "--audit-id", ident],
                       cwd=support.INSTALLED_LIB,
                       env={"PYTHONPATH": str(support.INSTALLED_LIB), "PYTHONDONTWRITEBYTECODE": "1"},
                       timeout=10)
    view = json.loads(observed.stdout)["result"]
    assert observed.returncode == view["exit_code"] == 3, "captured bytes that fail verification are exit 3"
    assert snapshot_tree(exp.session) == before, "verification must not repair or rewrite the historical record"
    item, = view["releases"]
    assert item["captured_in"] == [], f"an archive observed as {change} cannot supply frozen artifact bytes"
    assert item["uncaptured_artifacts"] == [SCRIPT, PREDICTION]
    reason = "evidence_tampered" if change == "corrupt" else "evidence_unavailable"
    assert {(p["collection"], p["artifact"], p["reason"]) for p in item["capture_problems"]} == {
        (collected["collection"], rel, reason) for rel in (SCRIPT, PREDICTION)}
    with pytest.raises(StewartError) as refused:
        export_evidence(checkout.ws, ident, collection=collected["collection"], selectors=[f"files.tar:{SCRIPT}"],
                        output=".scratch/unavailable-script", actor="reviewer")
    assert refused.value.reason == reason
    exported = export_evidence(checkout.ws, ident, collection=collected["collection"], selectors=["REPORT.md"],
                               output=".scratch/usable-report", actor="reviewer")
    package = checkout.repo / exported["package"]
    entry, = read_json(package)["entries"]
    assert (package.parent / entry["file"]).read_text() == "Captured construction report.\n", (
        "archive unavailability must not suppress the separately captured report")
    base = ["--repo", str(checkout.repo), "--workspace", checkout.ws.rel]
    # Archive bytes that fail verification at read time keep status at exit 3.
    assert main(base + ["status", "--audit-id", ident]) == 3
    text = capsys.readouterr().out
    assert "verified recoverable in no collection" in text and reason in text
    assert main(base + ["--json", "status", "--audit-id", ident]) == 3
    assert json.loads(capsys.readouterr().out)["result"]["releases"][0]["capture_problems"] == item["capture_problems"]


@pytest.mark.parametrize("change,reason", [
    ("missing", "support_unavailable"), ("duplicate", "support_unavailable"),
    ("different_bytes", "evidence_tampered"),
])
def test_release_capture_checks_members_even_with_matching_archive_digest(tmp_path, run_cmd, change, reason):
    """Archive identity alone cannot prove a unique member or its payload identity.

    Fault fixtures deliberately rebind the archive digest while leaving source
    discovery unchanged. The unaffected prediction remains independently usable.
    """
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    ident = checkout.meta["audit_id"]
    collected = collect(checkout.ws, ident, auditor_stopped="finished")
    release(checkout.ws, ident, review=support.REVIEW, actor="manager")
    directory = Path(collected["path"])
    archive = directory / "files.tar"
    original = tmp_path / "original-files.tar"
    archive.rename(original)
    (tmp_path / "original-collection.json").write_bytes((directory / "collection.json").read_bytes())
    with tarfile.open(original, "r") as source, tarfile.open(archive, "w") as target:
        for member in source.getmembers():
            payload = source.extractfile(member).read() if member.isfile() else None
            if member.name == SCRIPT and change == "missing":
                continue
            if member.name == SCRIPT and change == "different_bytes":
                payload = b"different script bytes\n"
                member.size = len(payload)
            target.addfile(member, io.BytesIO(payload) if payload is not None else None)
            if member.name == SCRIPT and change == "duplicate":
                target.addfile(member, io.BytesIO(payload))
    receipt = read_json(directory / "collection.json")
    receipt["archive_sha256"] = _hash.sha256_bytes((archive).read_bytes())
    (directory / "collection.json").write_text(json.dumps(receipt))
    before = snapshot_tree(exp.session)
    item, = status(checkout.ws, ident)["releases"]
    assert snapshot_tree(exp.session) == before
    assert item["captured_in"] == [] and item["uncaptured_artifacts"] == [SCRIPT], (
        "one unusable member must prevent a whole-release claim without hiding its usable sibling")
    assert [(p["artifact"], p["reason"]) for p in item["capture_problems"]] == [(SCRIPT, reason)]
    with pytest.raises(StewartError) as refused:
        export_evidence(checkout.ws, ident, collection=collected["collection"], selectors=[f"files.tar:{SCRIPT}"],
                        output=".scratch/unavailable-member", actor="reviewer")
    assert refused.value.reason == reason
    exported = export_evidence(checkout.ws, ident, collection=collected["collection"],
                               selectors=[f"files.tar:{PREDICTION}"], output=".scratch/prediction", actor="reviewer")
    package = checkout.repo / exported["package"]
    entry, = read_json(package)["entries"]
    assert (package.parent / entry["file"]).read_bytes() == (exp.worktree / PREDICTION).read_bytes()


@pytest.mark.parametrize("child", ["accepts_existing", "requires_absent"])
def test_run_creates_the_output_area_before_launch(tmp_path, run_cmd, child):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    before = {
        "accepts_existing": 'out = Path(args.output)\n'
                            'assert out.is_dir() and not out.is_symlink() and not any(out.iterdir()), '
                            '"the wrapper creates the output area, empty"\n'
                            'assert not Path(__import__("os").environ["HOME"]).resolve().is_relative_to(out.resolve()), '
                            '"HOME lies outside the output area"\n',
        "requires_absent": 'Path(args.output).mkdir()  # a construction that assumes it creates the area\n',
    }[child]
    support.prepared_experiment(checkout, before=before)
    released = release(checkout.ws, checkout.meta["audit_id"], review=support.REVIEW, actor="manager")
    result = run(checkout.ws, checkout.meta["audit_id"], release=released["release"], timeout=60)
    attempt = result["record"]
    assert attempt["schema_version"] == 8
    assert attempt["output_area"]["created_by_wrapper"] is True
    assert attempt["output_area"]["path"] == support.OUTPUT
    assert not Path(attempt["output_area"]["home"]).is_relative_to(Path(attempt["process"]["cwd"]) / support.OUTPUT)
    if child == "accepts_existing":
        assert result["errors"] == [] and attempt["process"]["exit_code"] == 0
        assert attempt["ledger"]["mismatching_cases"] == {"control": ["c1"], "ordinary": []}
        assert "mismatching_cases" not in attempt["ledger"]["anomalies"], "a fired control is not an anomaly"
    else:
        assert attempt["process"]["exit_code"] == 1 and "child exited 1" in result["errors"]
        assert "FileExistsError" in (Path(result["path"]) / "stderr.txt").read_text()
        assert attempt["ledger"]["rows"] == 0, "the child stopped before any row; the wrapper records that, not a verdict"
    assert "creates the output area empty" in released["record"]["output_area_policy"], (
        "the release record states the wrapper's contract for the child's author to read")


def test_pause_note_is_required_recorded_and_shown(checkout, capsys):
    revision = checkout.prompt_commit()
    with pytest.raises(StewartError) as refused:
        prepare(checkout.ws, revision, mode="paused", writers_paused=True)
    assert refused.value.reason == "pause_note_required" and refused.value.next_steps
    with pytest.raises(StewartError) as refused:
        prepare(checkout.ws, revision, mode="paused", writers_paused=True, pause_note="   ")
    assert refused.value.reason == "pause_note_required"
    with pytest.raises(StewartError) as refused:
        prepare(checkout.ws, revision, mode="snapshot", pause_note="nobody")
    assert refused.value.reason == "mode", "a pause note without a pause is a contradiction, not a default"
    assert not (checkout.repo / ".git/stewart").exists()
    prepared = prepare(checkout.ws, revision, mode="paused", writers_paused=True, pause_note=support.PAUSE_NOTE)
    assert prepared["writers_paused_note"] == support.PAUSE_NOTE
    assert read_json(Path(prepared["session"]) / "session.json")["writers_paused_note"] == support.PAUSE_NOTE
    base = ["--repo", str(checkout.repo), "--workspace", checkout.ws.rel]
    assert main(base + ["status", "--audit-id", checkout.meta["audit_id"]]) == EXIT_OK
    assert f"  pause note: {support.PAUSE_NOTE}" in capsys.readouterr().out


def test_missing_session_refusal_names_the_audit_id_check_before_prepare(checkout):
    with pytest.raises(StewartError) as refused:
        status(checkout.ws, "one-questoin")
    assert refused.value.reason == "session_missing"
    assert "audit ID" in refused.value.next_steps[0] and "prepare" in refused.value.next_steps[1], (
        "a misspelled ID must not be routed to prepare a different assignment")


def test_triage_draft_prose_renders_each_identity_comparison_on_its_own_line(checkout, capsys):
    from stewart.report_declaration import report_declaration
    from stewart.workspace import workspace

    ident = checkout.meta["audit_id"]
    prepared = support.prepared_session(checkout, report=None)
    kwargs = dict(expected_worktree=prepared.worktree, launch_prompt_commit=prepared.revision,
                  prompt_sha256=prepared.prepared["prompt_sha256"], launch_token=prepared.prepared["launch_token"])
    local = workspace(prepared.worktree, checkout.ws.rel)
    report_declaration(local, "start", **kwargs)
    collected = collect(checkout.ws, ident, auditor_stopped="finished")
    base = ["--repo", str(checkout.repo), "--workspace", checkout.ws.rel]
    assert main(base + ["triage-draft", "--audit-id", ident, "--collection", collected["collection"]]) == EXIT_OK
    out, err = capsys.readouterr()
    assert json.loads(out)["collection"] == collected["collection"], "stdout stays the response object alone"
    assert "Report status: present" in err and "Declaration validation: valid" in err
    for field in ("audit_id", "launch_prompt_commit", "launch_token", "observed_checkout_commit",
                  "prompt_sha256", "target_commit"):
        assert f"  {field}: matches; expected " in err, field
    assert "source: pinned session" in err and "source: HEAD observed at collection" in err
    # Pair: a missing declaration renders its status without comparison lines.
    prepared.report.write_text("no declaration here\n")
    again = collect(checkout.ws, ident, auditor_stopped="finished")
    assert main(base + ["triage-draft", "--audit-id", ident, "--collection", again["collection"]]) == EXIT_OK
    _, err = capsys.readouterr()
    assert "Declaration validation: missing" in err and ": matches; expected" not in err
    assert "declaration_missing:" in err
