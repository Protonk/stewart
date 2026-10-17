"""Pinned child ledger loading preserves script semantics and legitimate imports."""
from __future__ import annotations

import json
from pathlib import Path
import signal
import sys

import pytest

from stewart import runtime
from stewart._bootstrap import (
    CHILD_LEDGER_MODULE, StewartError, check_child_imports, observe_runtime, stage_source,
)
from stewart._util import sha256_bytes
from support import clean_environment


@pytest.fixture
def child_runtime(installation, tmp_path):
    deployment = stage_source(installation / "stewart", cache=tmp_path / "manager")
    identity = runtime.binding(tmp_path / "supplied", deployment["manifest"])
    _, payloads = observe_runtime(deployment["code_root"])
    runtime.materialize(identity, payloads)
    launcher = {"path": str(deployment["launcher"]), "sha256": deployment["launcher_sha256"]}
    return identity, launcher


def command(selected, project, script, *args):
    identity, launcher = selected
    return runtime.child_command(identity, interpreter=sys.executable, worktree=project, script=script,
                                 script_sha256=sha256_bytes((project / script).read_bytes()),
                                 arguments=list(args), launcher=launcher)


def test_child_preserves_script_mode_and_ordered_project_imports(child_runtime, tmp_path, run_cmd):
    project = tmp_path / "project with 'quotes'"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    for directory, name, value in ((scripts, "sibling", "sibling"), (project, "root_only", "root"),
                                   (scripts, "same", "script first"), (project, "same", "root second")):
        (directory / (name + ".py")).write_text(f"VALUE = {value!r}\n")
    for name in ("tools", "stewart"):
        package = project / name
        package.mkdir()
        (package / "__init__.py").write_text(f"VALUE = 'project {name}'\n")
    script = "scripts/probe.py"
    (project / script).write_text('''import json, os, sys
import sibling, root_only, same, tools, stewart
ledger = sys.modules.get("_stewart_ledger_v1")
print(json.dumps({"argv":sys.argv, "file":__file__, "name":__name__, "package":__package__,
                  "spec":__spec__, "cached":__cached__, "cwd":os.getcwd(), "paths":sys.path[:2],
                  "values":[sibling.VALUE,root_only.VALUE,same.VALUE,tools.VALUE,stewart.VALUE],
                  "ledger":None if ledger is None else ledger.__file__,
                  "isolated":sys.flags.isolated, "cache":sys.pycache_prefix}))
''')
    arguments = ["literal with spaces", "--json", "--root", str(project)]
    issued = command(child_runtime, project, script, *arguments)
    ordinary_env = {**clean_environment(), "PYTHONPATH": str(project)}
    ordinary = json.loads(run_cmd([sys.executable, "-B", script, *arguments], cwd=project, env=ordinary_env).stdout)
    hostile = {**ordinary_env, "PYTHONHOME": "/absent-python-home"}
    actual = json.loads(run_cmd(issued["argv"], cwd=project, env=hostile).stdout)
    for key in ("argv", "file", "name", "package", "spec", "cached", "cwd", "paths", "values"):
        assert actual[key] == ordinary[key], key
    assert actual["values"] == ["sibling", "root", "script first", "project tools", "project stewart"]
    assert actual["ledger"] == issued["ledger"]["path"] and ordinary["ledger"] is None
    assert actual["isolated"] == 1 and not Path(actual["cache"]).exists()
    assert str(Path(child_runtime[0]["root"])) not in actual["paths"]
    # A root-only launcher cannot preserve the script's sibling imports. The
    # same runtime and project under a deliberately narrowed trusted launcher
    # provide the non-zero control for the path-order assertion.
    original = Path(child_runtime[1]["path"])
    source = original.read_text()
    assert source.count("sys.path[:0] = paths") == 1
    wrong = original.with_name("root-only-control.py")
    wrong.write_text(source.replace("sys.path[:0] = paths", "sys.path[:0] = paths[1:]"))
    narrowed = command((child_runtime[0], {"path": str(wrong), "sha256": sha256_bytes(wrong.read_bytes())}),
                       project, script, *arguments)
    failed = run_cmd(narrowed["argv"], cwd=project, env=hostile, check=False)
    assert failed.returncode == 1 and "No module named 'sibling'" in failed.stderr


@pytest.mark.parametrize("location", ["root", "script"])
@pytest.mark.parametrize("kind", ["source", "package", "bytecode", "native", "symlink"])
def test_child_refuses_reserved_import_collisions(child_runtime, tmp_path, run_cmd, location, kind):
    project = tmp_path / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    script = "scripts/child.py"
    (project / script).write_text("import _stewart_ledger_v1\nprint('child reached')\n")
    issued = command(child_runtime, project, script)
    assert "child reached" in run_cmd(issued["argv"], cwd=project).stdout
    directory = project if location == "root" else scripts
    suffix = {"source": ".py", "package": "", "bytecode": ".pyc", "native": ".abi3.so", "symlink": ".py"}[kind]
    collision = directory / (CHILD_LEDGER_MODULE + suffix)
    if kind == "package":
        collision.mkdir()
    elif kind == "symlink":
        collision.symlink_to(project / script)
    else:
        collision.write_bytes(b"project collision")
    refused = run_cmd(issued["argv"], cwd=project, check=False)
    assert refused.returncode == 2 and "ledger_collision" in refused.stderr and "child reached" not in refused.stdout
    collision.rename(collision.with_name("unrelated" + suffix))
    assert "child reached" in run_cmd(issued["argv"], cwd=project).stdout


@pytest.mark.parametrize("body,code,diagnostic", [
    ("raise SystemExit(7)", 7, ""),
    ("raise OSError('child failure')", 1, "OSError: child failure"),
    ("class StewartError(ValueError): pass\nraise StewartError('child-defined failure')", 1, "StewartError: child-defined failure"),
    ("import os, signal\nos.kill(os.getpid(), signal.SIGTERM)", -signal.SIGTERM, ""),
])
def test_child_exit_and_exceptions_are_not_startup_refusals(child_runtime, tmp_path, run_cmd, body, code, diagnostic):
    project = tmp_path / "project"
    project.mkdir()
    (project / "child.py").write_text("print('entered child', flush=True)\n" + body + "\n")
    result = run_cmd(command(child_runtime, project, "child.py")["argv"], cwd=project, check=False)
    assert result.returncode == code and result.stdout == "entered child\n"
    assert diagnostic in result.stderr and "Refused" not in result.stderr


def test_reserved_preloaded_module_refuses_without_hiding_other_modules(tmp_path, monkeypatch):
    check_child_imports([str(tmp_path)])
    monkeypatch.setitem(sys.modules, CHILD_LEDGER_MODULE, object())
    with pytest.raises(StewartError) as caught:
        check_child_imports([str(tmp_path)])
    assert caught.value.reason == "ledger_collision"
    monkeypatch.delitem(sys.modules, CHILD_LEDGER_MODULE)
    monkeypatch.setitem(sys.modules, "unrelated_ledger", object())
    check_child_imports([str(tmp_path)])


@pytest.mark.parametrize("name,preloaded", [("json", True), ("csv", False)])
def test_child_preloaded_standard_library_names_keep_their_binding(child_runtime, tmp_path, run_cmd, name, preloaded):
    project = tmp_path / "project"
    project.mkdir()
    (project / f"{name}.py").write_text("PROJECT_MARKER = True\n")
    script = project / "child.py"
    script.write_text(f"import {name}\nprint(getattr({name}, 'PROJECT_MARKER', False))\n")
    ordinary = run_cmd([sys.executable, "-B", str(script)], cwd=project,
                       env={**clean_environment(), "PYTHONPATH": str(project)})
    actual = run_cmd(command(child_runtime, project, "child.py")["argv"], cwd=project)
    assert ordinary.stdout.strip() == "True", "the project shadow must be reachable under plain startup"
    assert actual.stdout.strip() == str(not preloaded)


@pytest.mark.parametrize("import_kind", ["none", "guarded", "top_level"])
def test_spawn_workers_do_not_receive_the_initial_process_ledger(child_runtime, tmp_path, run_cmd, import_kind):
    project = tmp_path / "project"
    project.mkdir()
    ledger = "from _stewart_ledger_v1 import Ledger\n"
    header = ledger if import_kind == "top_level" else ""
    guarded = "    " + ledger if import_kind == "guarded" else ""
    (project / "child.py").write_text(header + '''import multiprocessing
if __name__ == "__main__":
''' + guarded + '''    worker = multiprocessing.get_context("spawn").Process(target=print, args=("worker ran",))
    worker.start()
    worker.join(10)
    if worker.is_alive():
        worker.terminate()
        worker.join()
        raise RuntimeError("spawn worker did not terminate")
    print("worker exit", worker.exitcode)
''')
    actual = run_cmd(command(child_runtime, project, "child.py")["argv"], cwd=project)
    if import_kind == "top_level":
        assert "worker exit 1" in actual.stdout and "No module named '_stewart_ledger_v1'" in actual.stderr
    else:
        assert "worker ran" in actual.stdout and "worker exit 0" in actual.stdout
