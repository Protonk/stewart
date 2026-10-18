"""Input inventories and the auditor checker preserve a fixed comparison population.

Relevant pairs change a selected byte or pin; ignored pairs change an unselected
file or report prose. Unsafe entries remain failed rows, never a smaller count.
All CLI executions use disposable checkouts and execute no selected input.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex

import pytest

from stewart import _util as _hash
from stewart import assignment
from stewart.collect import collect
from stewart._bootstrap import StewartError
from stewart.prepare import prepare
from stewart.verify_inputs import main, verify_inputs
from stewart.workspace import workspace
import stewart_support as support

pytestmark = pytest.mark.system
MANIFEST = ".scratch/audit-inputs/one-question.json"


def initialized(checkout, *, write=True):
    supplied = checkout.repo / "ignored/supplied.txt"
    supplied.parent.mkdir(exist_ok=True)
    supplied.write_text("retained bytes\n")
    second = supplied.with_name("second.txt")
    second.write_text("second retained bytes\n")
    return assignment.initialize(
        checkout.ws, "one-question", checkout.meta["target_commit"], inputs=["input.txt"],
        supplemental=[("ignored/supplied.txt", "one shared origin"), ("ignored/second.txt", "one shared origin")],
        input_manifest=MANIFEST, replace_prompt=write,
    )


def prepared_inventory(checkout):
    draft = initialized(checkout)
    checkout.meta.clear()
    checkout.meta.update(draft["assignment"])
    prepared = support.prepared_session(checkout, report=None)
    kwargs = dict(expected_worktree=prepared.worktree, launch_prompt_commit=prepared.revision,
                  prompt_sha256=prepared.prepared["prompt_sha256"], launch_token=prepared.prepared["launch_token"])
    return prepared, workspace(prepared.worktree, support.WS), kwargs


def cli_args(kwargs):
    return ["--workspace", support.WS, *[token for k, v in kwargs.items()
                                        for token in ("--" + k.replace("_", "-"), str(v))]]


def test_manifest_preview_and_publication_preserve_population_with_short_prose_first_prompt(checkout):
    result = initialized(checkout, write=False)
    assert not (checkout.repo / MANIFEST).exists()
    assert (checkout.repo / checkout.ws.prompt).read_text() == "**UNASSIGNED**\n"
    assert result["written"] is None and result["input_manifest"]["written"] is None
    doc = result["input_manifest"]["document"]
    assert doc["input_files"] == ["input.txt"]
    assert doc["provenance"] == {"source-1": "one shared origin"}
    assert [r["provenance"] for r in doc["supplemental_inputs"]] == ["source-1", "source-1"]
    assert result["draft"].index("## Question") < result["draft"].index("```audit-assignment")
    assert "retained bytes" not in result["draft"] and "supplemental_inputs" not in result["draft"]
    written = initialized(checkout)
    assert written["draft"] == result["draft"], "preview must describe the bytes actually published"
    assert _hash.sha256_bytes((checkout.repo / MANIFEST).read_bytes()) == written["assignment"]["input_manifest"]["sha256"]
    expanded = assignment.expand_input_manifest(checkout.ws, assignment.assignment_metadata(written["assignment"], checkout.ws))
    assert expanded["input_files"] == ["input.txt"]
    assert [r["path"] for r in expanded["supplemental_inputs"]] == ["ignored/supplied.txt", "ignored/second.txt", MANIFEST]
    assert expanded["supplemental_inputs"][0]["provenance"] == "one shared origin"
    assert expanded["scratch_paths"] == [f"{support.WS}/scratch/one-question/notes"]
    before = support.snapshot_tree(checkout.repo)
    with pytest.raises(StewartError) as caught:
        initialized(checkout)
    assert caught.value.reason == "destination_exists"
    assert support.snapshot_tree(checkout.repo) == before, "refusing a reused inventory must not rewrite the prompt"


def test_prepared_inventory_is_copied_checked_and_captured(checkout, run_cmd):
    prepared, ws, kwargs = prepared_inventory(checkout)
    note_dir = prepared.worktree / checkout.meta["scratch_paths"][0]
    assert note_dir.is_dir()
    launch = (prepared.session / "LAUNCH.md").read_text()
    assert str(note_dir) in launch and "checksum lists" in launch
    command = next(c for c in re.findall(r"```sh\n(.*?)\n```", launch, re.S) if "--helper inputs" in c)
    parts = shlex.split(command)
    before = support.snapshot_tree(prepared.worktree)
    result = run_cmd(parts[3:] + ["--json"], cwd=prepared.worktree,
                     env={"PYTHONPATH": str(prepared.worktree)}, timeout=30)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)["result"]
    assert (observed["selected"], observed["matched"], observed["failed"]) == (4, 4, 0)
    assert {r["path"] for r in observed["inputs"]} == {"input.txt", "ignored/supplied.txt", "ignored/second.txt", MANIFEST}
    assert support.snapshot_tree(prepared.worktree) == before and not prepared.report.exists(), "checker writes nothing"
    assert observed == verify_inputs(ws, **kwargs)
    # Collection preserves the inventory itself, not just its expanded members.
    captured = collect(checkout.ws, "one-question", auditor_stopped="interrupted")
    assert MANIFEST in json.dumps(captured["receipt"])
    assert (prepared.worktree / MANIFEST).read_bytes() == (checkout.repo / MANIFEST).read_bytes()


def test_checker_compares_selected_bytes_and_ignores_report_prose_and_other_files(checkout, monkeypatch, capsys):
    prepared, ws, kwargs = prepared_inventory(checkout)
    monkeypatch.chdir(prepared.worktree)
    baseline = verify_inputs(ws, **kwargs)
    (prepared.worktree / "other.txt").write_text("irrelevant change\n")
    prepared.report.write_text("an unvalidated conclusion\n")
    assert verify_inputs(ws, **kwargs) == baseline, "the checker does not grade or parse report prose"
    (prepared.worktree / "input.txt").write_text("selected change\n")
    # A changed committed input can be restored from Git: action needed (1).
    assert main(cli_args(kwargs) + ["--json"]) == 1
    rows = {r["path"]: r for r in json.loads(capsys.readouterr().out)["result"]["inputs"]}
    assert rows["input.txt"]["code"] == 1 and "git checkout" in rows["input.txt"]["fix"]
    (prepared.worktree / "ignored/supplied.txt").unlink()
    # A missing supplemental input cannot be restored by the auditor: 3 takes precedence.
    assert main(cli_args(kwargs) + ["--json"]) == 3
    result = json.loads(capsys.readouterr().out)["result"]
    assert (result["selected"], result["matched"], result["failed"]) == (4, 2, 2), "failures stay in denominator"
    rows = {r["path"]: r for r in result["inputs"]}
    assert rows["input.txt"]["expected_sha256"] == _hash.sha256_bytes(b"committed input\n")
    assert rows["input.txt"]["observed_sha256"] == _hash.sha256_bytes(b"selected change\n")
    assert rows["ignored/supplied.txt"]["observed_kind"] == "missing"
    assert rows["ignored/supplied.txt"]["code"] == 3 and "git checkout" not in rows["ignored/supplied.txt"]["fix"]
    assert main(cli_args(kwargs)) == 3
    printed = capsys.readouterr().out
    assert "FAIL input.txt" in printed and "FAIL ignored/supplied.txt" in printed and "MATCH" not in printed
    assert main(cli_args(kwargs) + ["--print"]) == 3
    assert "MATCH ignored/second.txt" in capsys.readouterr().out


@pytest.mark.parametrize("kind", ["symlink", "ancestor_symlink", "fifo", "directory"])
def test_unsafe_selected_entries_fail_without_following_or_blocking(checkout, run_cmd, kind):
    prepared, _, kwargs = prepared_inventory(checkout)
    selected = prepared.worktree / "ignored/supplied.txt"
    if kind == "ancestor_symlink":
        selected.parent.rename(prepared.worktree / "moved")
        selected.parent.symlink_to(prepared.worktree / "moved", target_is_directory=True)
    else:
        selected.unlink()
        if kind == "symlink":
            selected.symlink_to(checkout.repo / "ignored/supplied.txt")  # Same bytes must still fail.
        elif kind == "fifo":
            os.mkfifo(selected)
        else:
            selected.mkdir()
    before = support.snapshot_tree(prepared.worktree)
    from stewart.runtime import helper_argv
    record = support.read_json(prepared.session / "session.json")
    result = run_cmd(helper_argv(record["runtime"], record["helper_interpreter"], "inputs", *cli_args(kwargs), "--json"),
                     cwd=prepared.worktree, env={"PYTHONPATH": str(prepared.worktree)}, timeout=15)
    assert result.returncode == 3, "a supplemental input the auditor cannot restore does not verify"
    output = json.loads(result.stdout)["result"]
    row = next(r for r in output["inputs"] if r["path"] == "ignored/supplied.txt")
    assert not row["matches"] and row["observed_sha256"] is None
    assert row["observed_detail"], "a failed entry needs a cause, not only the generic 'replaced' kind"
    assert output["selected"] == 4
    assert support.snapshot_tree(prepared.worktree) == before


@pytest.mark.parametrize("fault", ["digest", "symlink", "duplicate_key", "duplicate_path", "unsafe_path", "unknown_provenance", "empty", "self_member", "writable_overlap"])
def test_bad_manifest_refuses_before_reserving_session(checkout, fault):
    result = initialized(checkout)
    checkout.meta.clear()
    checkout.meta.update(result["assignment"])
    file = checkout.repo / MANIFEST
    doc = json.loads(file.read_bytes())
    if fault == "symlink":
        moved = file.with_suffix(".saved")
        file.rename(moved)
        file.symlink_to(moved)
    else:
        if fault == "duplicate_path":
            doc["input_files"].append("input.txt")
        elif fault == "unsafe_path":
            doc["input_files"] = ["../outside"]
        elif fault == "unknown_provenance":
            doc["supplemental_inputs"][0]["provenance"] = "missing"
        elif fault == "empty":
            doc["input_files"], doc["supplemental_inputs"] = [], []
        elif fault == "self_member":
            doc["input_files"].append(MANIFEST)
        elif fault == "writable_overlap":
            item = doc["supplemental_inputs"][0]
            item["path"] = checkout.meta["scratch_paths"][0] + "/input.txt"
        payload = json.dumps(doc)
        if fault == "duplicate_key":
            payload = payload.replace('"schema":', '"schema": "discarded", "schema":')
        file.write_text(payload)
        if fault != "digest":
            checkout.meta["input_manifest"]["sha256"] = _hash.sha256_bytes((file).read_bytes())
    revision = checkout.prompt_commit()
    with pytest.raises(StewartError) as caught:
        prepare(checkout.ws, revision)
    assert caught.value.reason == {
        "digest": "input_manifest", "symlink": "input_manifest", "duplicate_key": "input_manifest",
        "duplicate_path": "assignment_schema", "unsafe_path": "path_escape",
        "unknown_provenance": "input_manifest", "empty": "input_manifest",
        "self_member": "assignment_schema", "writable_overlap": "input_overlap",
    }[fault]
    assert not (checkout.repo / checkout.ws.session("one-question")).exists()


@pytest.mark.parametrize("fault,reason", [("inventory", "input_manifest"), ("prompt", "prompt_drift"), ("root", "checkout_root")])
def test_checker_context_and_inventory_faults_refuse_with_actionable_json(checkout, monkeypatch, capsys, fault, reason):
    prepared, _, kwargs = prepared_inventory(checkout)
    monkeypatch.chdir(prepared.worktree)
    if fault == "inventory":
        inventory = prepared.worktree / MANIFEST
        inventory.write_bytes(inventory.read_bytes() + b"\n")
    elif fault == "prompt":
        prompt = prepared.worktree / checkout.ws.prompt
        prompt.write_bytes(prompt.read_bytes() + b"\n")
    else:
        kwargs["expected_worktree"] = checkout.repo
    # A changed inventory is a supplemental input the auditor cannot restore (3);
    # a drifted prompt or a wrong root refuses before anything is compared (2).
    assert main(cli_args(kwargs) + ["--json"]) == (3 if fault == "inventory" else 2)
    error = json.loads(capsys.readouterr().out)["error"]
    assert error["reason"] == reason and error["next_steps"]
    assert not prepared.report.exists()


def test_manifest_members_cannot_bypass_workspace_input_drift_check(checkout):
    selected = f"{support.WS}/selected.txt"
    (checkout.repo / selected).write_text("target\n")
    checkout.git("add", selected)
    checkout.git("commit", "-qm", "Selected workspace file")
    target = checkout.git("rev-parse", "HEAD")
    draft = assignment.initialize(checkout.ws, "one-question", target, inputs=[selected], input_manifest=MANIFEST, replace_prompt=True)
    (checkout.repo / selected).write_text("changed after target\n")
    checkout.git("add", selected)
    checkout.git("commit", "-qm", "Later audit material")
    checkout.meta.clear()
    checkout.meta.update(draft["assignment"])
    with pytest.raises(StewartError) as caught:
        prepare(checkout.ws, checkout.prompt_commit())
    assert caught.value.reason == "input_drift"


@pytest.mark.parametrize("include_protected", [True, False])
def test_experiment_membership_is_checked_after_manifest_expansion(tmp_path, run_cmd, include_protected):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    draft = assignment.initialize(checkout.ws, "one-question", checkout.meta["target_commit"],
                                  inputs=checkout.meta["input_files"], scratch=checkout.meta["scratch_paths"],
                                  experiment=checkout.grant, input_manifest=MANIFEST, replace_prompt=True)
    checkout.meta.clear()
    checkout.meta.update(draft["assignment"])
    if not include_protected:
        inventory = checkout.repo / MANIFEST
        doc = json.loads(inventory.read_bytes())
        doc["input_files"].remove(support.MANIFEST)
        inventory.write_text(json.dumps(doc))
        checkout.meta["input_manifest"]["sha256"] = _hash.sha256_bytes((inventory).read_bytes())
    prompt = support.assignment_text(checkout.meta, extra_sections=support.AUTHORIZATION)
    revision = checkout.prompt_commit(text=prompt)
    if include_protected:
        prepared = prepare(checkout.ws, revision)
        assert support.MANIFEST in support.read_json(Path(prepared["session"]) / "session.json")["assignment"]["input_files"]
    else:
        with pytest.raises(StewartError) as caught:
            prepare(checkout.ws, revision)
        assert caught.value.reason == "grant_containment"
        assert not (checkout.repo / checkout.ws.session("one-question")).exists()


@pytest.mark.parametrize("destination,reason", [
    ("input.txt", "input_overlap"), ("other.txt", "input_collision"),
    (f"{support.WS}/scratch/one-question/notes/inventory.json", "input_overlap"),
    (f"{support.WS}/scratch/one-question", "input_overlap"),
])
def test_initializer_manifest_destination_cannot_cover_inputs_or_outputs(checkout, destination, reason):
    before = support.snapshot_tree(checkout.repo)
    with pytest.raises(StewartError) as caught:
        assignment.initialize(checkout.ws, "one-question", "HEAD", inputs=["input.txt"],
                              input_manifest=destination, replace_prompt=True)
    assert caught.value.reason == reason
    assert support.snapshot_tree(checkout.repo) == before


def test_failed_prompt_write_names_preserved_inventory(checkout, monkeypatch):
    original = Path.write_text
    def fail_prompt(location, *args, **kwargs):
        if location == checkout.repo / checkout.ws.prompt:
            raise OSError("injected prompt write failure")
        return original(location, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", fail_prompt)
    with pytest.raises(StewartError) as caught:
        assignment.initialize(checkout.ws, "one-question", "HEAD", inputs=["input.txt"],
                              input_manifest=MANIFEST, replace_prompt=True)
    assert caught.value.reason == "initialization_failed"
    assert caught.value.retained == [str(checkout.repo / MANIFEST)] and caught.value.next_steps
    assert (checkout.repo / MANIFEST).is_file()


def test_initializer_cli_manifest_preview_and_write_are_explicit(checkout, capsys):
    from stewart.cli import main as stewart_main

    argv = ["--repo", str(checkout.repo), "--workspace", support.WS, "--json", "init", "--audit-id", "one-question",
            "--input", "input.txt", "--input-manifest", MANIFEST]
    assert stewart_main(argv) == 0
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["input_manifest"]["document"]["input_files"] == ["input.txt"]
    assert not (checkout.repo / MANIFEST).exists()
    assert stewart_main(argv + ["--replace-prompt"]) == 0
    written = json.loads(capsys.readouterr().out)["result"]
    assert written["input_manifest"]["sha256"] == result["input_manifest"]["sha256"]
    assert written["input_manifest"]["written"] == str(checkout.repo / MANIFEST)
