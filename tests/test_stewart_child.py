"""Release authorizes one script invocation and reserves only its ledger import name."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from stewart._bootstrap import CHILD_LEDGER_MODULE, StewartError
from stewart.experiment import release, run
import stewart_support as support

pytestmark = pytest.mark.system


@pytest.mark.parametrize("template", [
    ["sh", "{interpreter}", "{script}"],
    ["{interpreter}", "-c", "{script}"],
    ["{interpreter}", "-m", "{script}"],
    ["{interpreter}", "-I", "{script}"],
    ["{interpreter}", "-B", "-B", "{script}"],
    ["{interpreter}", "{script}", "{interpreter}"],
    ["{interpreter}", "{script}", "{script}"],
    ["{script}", "{interpreter}"],
])
def test_unsupported_script_templates_refuse_before_preparation(tmp_path, run_cmd, template):
    checkout = support.experiment_checkout(tmp_path, run_cmd, argv_template=template)
    with pytest.raises(StewartError) as caught:
        support.prepared_experiment(checkout)
    assert caught.value.reason == "child_argv"
    assert not (checkout.repo / checkout.ws.session("one-question")).exists()


@pytest.mark.parametrize("where", ["root", "script"])
@pytest.mark.parametrize("when", ["release", "run"])
def test_reserved_module_is_checked_before_release_and_again_before_execution(tmp_path, run_cmd, where, when):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    prepared = support.prepared_experiment(checkout)
    released = release(checkout.ws, "one-question", review=support.REVIEW, actor="manager") if when == "run" else None
    directory = prepared.worktree if where == "root" else prepared.script.parent
    collision = directory / (CHILD_LEDGER_MODULE + ".py")
    collision.write_text("raise RuntimeError('project ledger must never run')\n")
    with pytest.raises(StewartError) as caught:
        if when == "release":
            release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
        else:
            run(checkout.ws, "one-question", release=released["release"])
    assert caught.value.reason == "ledger_collision"
    if when == "release":
        assert not list((prepared.session / "releases").glob("*.json"))
    else:
        attempt = support.read_json(prepared.session / "attempts" / released["release"] / "ATTEMPT.json")
        assert attempt["process"]["launched"] is False and attempt["errors"]
    # The exact same project source under an unrelated name cannot block a
    # fresh release, and the supplied ledger's firing control remains visible.
    collision.rename(collision.with_name("unrelated_ledger.py"))
    accepted = release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
    attempt = run(checkout.ws, "one-question", release=accepted["release"])["record"]
    assert not attempt["errors"] and attempt["ledger"]["summary"]["control"]["mismatches"] == 1


@pytest.mark.parametrize("optional_b", [True, False])
def test_both_supported_templates_keep_approved_and_effective_commands(tmp_path, run_cmd, optional_b):
    template = support.grant()["argv_template"]
    if not optional_b:
        template.remove("-B")
    checkout = support.experiment_checkout(tmp_path, run_cmd, argv_template=template)
    prepared = support.prepared_experiment(checkout)
    assert not (prepared.worktree / "tools").exists()
    released = release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
    record = released["record"]
    assert ("-B" in record["approved_argv"]) == optional_b
    assert record["argv"][1:3] == ["-I", "-B"]
    assert not Path(record["child"]["launcher"]["path"]).is_relative_to(Path(prepared.prepared["runtime"]["root"]))
    attempt = run(checkout.ws, "one-question", release=released["release"])["record"]
    assert attempt["approved_argv"] == record["approved_argv"]
    assert attempt["process"]["argv"] == record["argv"]
    assert attempt["child"] == record["child"] and not attempt["errors"]


@pytest.mark.parametrize("field", ["approved_argv", "argv", "project_paths", "ledger", "launcher"])
def test_changed_child_binding_cannot_redirect_execution(tmp_path, run_cmd, field):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    prepared = support.prepared_experiment(checkout)
    released = release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
    location = Path(released["path"])
    record = support.read_json(location)
    if field in {"approved_argv", "argv"}:
        record[field].append("added argument")
    elif field == "project_paths":
        record["child"][field].reverse()
    elif field == "ledger":
        record["child"][field]["module"] = "project_ledger"
    else:
        Path(record["child"][field]["path"]).write_text("raise SystemExit(99)\n")
    if field != "launcher":
        location.write_text(json.dumps(record))
    with pytest.raises(StewartError) as caught:
        run(checkout.ws, "one-question", release=released["release"])
    assert caught.value.reason == ("launcher_mismatch" if field == "launcher" else "release_invalidated")
    attempt = support.read_json(prepared.session / "attempts" / released["release"] / "ATTEMPT.json")
    assert attempt["process"]["launched"] is False and attempt["errors"]
