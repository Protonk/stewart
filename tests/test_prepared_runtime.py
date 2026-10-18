"""Production preparation keeps auditor access and recoverable evidence separate."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import re
import shlex
import shutil

import pytest

from stewart._bootstrap import StewartError
from stewart._git import git_text
from stewart.captured import pristine_runtime, runtime_observations
from stewart.collect import collect
from stewart.prepare import prepare
from stewart.session import load_session
from stewart.status import status
from test_repository import assigned, ready_project


def test_preparation_supplies_every_issued_helper_without_project_sources(ready_project, run_cmd):
    ws, prompt, _ = assigned(ready_project)
    prepared = prepare(ws, prompt)
    session, record = load_session(ws, "one-question")
    worktree, runtime = Path(record["worktree"]), Path(record["runtime"]["root"])
    assert not git_text(ws.repo, "log", "--all", "--format=%H", "--", "tools", "stewart")
    assert not (worktree / "tools").exists()
    assert not runtime.is_relative_to(session) and not runtime.is_relative_to(worktree)
    public = Path(prepared["launch"])
    assert public.is_relative_to(worktree)
    assert public.read_bytes() == (session / "LAUNCH.md").read_bytes()
    assert prepared["auditor_scope"]["runtime"] == str(runtime)
    assert pristine_runtime(session, record)
    captured = json.loads((session / "RUNTIME-PREPARED.json").read_bytes())
    observations = runtime_observations(session, captured["runtime"], phases={"preparation"})
    assert observations["preparation"]["matches_expected"] is True
    commands = re.findall(r"```sh\n(.*?)\n```", public.read_text(), re.S)
    assert len(commands) == 4
    for command in commands:
        argv = shlex.split(command)
        assert argv[:3] == ["cd", str(worktree), "&&"]
        assert argv[4:6] == ["-I", "-B"]
        result = run_cmd(argv[3:], cwd=worktree)
        assert "audit=one-question" in result.stdout
    assert '"completion": "complete"' in (worktree / record["assignment"]["report_path"]).read_text()
    view = status(ws, "one-question")
    assert view["preparation"]["state"] == "ready"
    assert view["preparation"]["pristine_runtime_available"] is True
    # Historical preparation remains recoverable without the exposed copy.
    shutil.rmtree(runtime)
    view = status(ws, "one-question")
    assert view["preparation"]["runtime"]["observations"]["preparation"]["matches_expected"] is True
    assert view["preparation"]["pristine_runtime_available"] is True


@pytest.mark.parametrize("change", ["none", "unrelated", "changed", "missing", "symlink"])
def test_collection_observes_supplied_handoff_even_if_git_has_no_deletion(ready_project, change):
    ws, prompt, _ = assigned(ready_project)
    prepared = prepare(ws, prompt)
    worktree, public = Path(prepared["worktree"]), Path(prepared["launch"])
    report = worktree / ws.report_path("one-question")
    report.write_text("Malformed report still preserved\n")
    if change == "unrelated":
        (worktree / "unrelated.txt").write_text("unrelated\n")
    elif change == "changed":
        public.write_text("different handoff\n")
    elif change in {"missing", "symlink"}:
        public.unlink()
        if change == "symlink":
            public.symlink_to(prepared["private_launch"])
    observed = collect(ws, "one-question", auditor_stopped="interrupted")
    assert (Path(observed["path"]) / "REPORT.md").read_bytes() == report.read_bytes()
    damaged = change in {"changed", "missing", "symlink"}
    assert any("public handoff" in error["message"] for error in observed["receipt"]["errors"]) == damaged
    view = status(ws, "one-question")
    assert view["preparation"]["handoff_matches"] == {"private": True, "public": not damaged}
    assert view["preparation"]["state"] == ("incomplete" if damaged else "ready")


@pytest.mark.parametrize("failure", ["materialize", "private_assets"])
def test_failed_supply_and_damaged_pristine_assets_never_get_launch_actions(ready_project, monkeypatch, failure):
    ws, prompt, _ = assigned(ready_project)
    if failure == "materialize":
        runtime = importlib.import_module("stewart.runtime")
        def refuse(*args):
            raise StewartError("injected publication failure", reason="runtime_mismatch")
        monkeypatch.setattr(runtime, "materialize", refuse)
        with pytest.raises(StewartError) as caught:
            prepare(ws, prompt)
        assert caught.value.reason == "prepare_failed"
        session, record = load_session(ws, "one-question")
        error = json.loads((session / "PREPARE-ERROR.json").read_bytes())
        assert error["stage"] == "runtime"
        assert not (session / "LAUNCH.md").exists()
        assert pristine_runtime(session, record), "failed exposure must preserve the private assets"
    else:
        prepared = prepare(ws, prompt)
        session = Path(prepared["session"])
        (session / "runtime-pristine/files.tar").write_bytes(b"damaged private archive")
    view = status(ws, "one-question")
    assert view["preparation"]["state"] == ("failed" if failure == "materialize" else "incomplete")
    assert not any(action["action"] in {"handoff", "launch"} for action in view["next_actions"])
    assert view["session"]["problems"]
