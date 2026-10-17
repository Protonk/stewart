"""The runner must measure its test population, plugin origins and elapsed work."""
import json
import os
from pathlib import Path
import shutil
import sys
import types

import pytest

from support import budget_overruns, clean_environment, plugin_origins


@pytest.mark.smoke
def test_plugin_boundary_reads_origin_and_ignores_registration_names(tmp_path):
    builtin = tmp_path / "pytest"
    builtin.mkdir()
    conftest = tmp_path / "suite/conftest.py"
    plugin = types.ModuleType("example")
    plugin.__file__ = str(builtin / "plugin.py")
    assert plugin_origins([("one", plugin), ("blocked", None)], builtin, conftest)
    assert plugin_origins([("renamed", plugin)], builtin, conftest)
    plugin.__file__ = str(tmp_path / "foreign/plugin.py")
    with pytest.raises(AssertionError, match="unexpected pytest plugin"):
        plugin_origins([("one", plugin)], builtin, conftest)
    plugin.__file__ = str(conftest)
    assert plugin_origins([("local", plugin)], builtin, conftest)
    with pytest.raises(AssertionError, match="population vanished"):
        plugin_origins([], builtin, conftest)


@pytest.mark.smoke
def test_budget_charges_all_phases_and_ignores_node_names():
    phases = {"setup": 0.4, "call": 0.1, "teardown": 0.2}
    assert budget_overruns({"small": phases}, 0.8) == {}
    assert budget_overruns({"small": phases}, 0.6) == {"small": sum(phases.values())}
    assert list(budget_overruns({"renamed": phases}, 0.6).values()) == [sum(phases.values())]


def test_runner_budgets_fire_on_setup_and_total_work(tmp_path, run_cmd):
    source = Path(os.environ["STEWART_TEST_PROJECT"])
    project = tmp_path / "project"
    shutil.copytree(source, project, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".scratch", ".git", "dist", "build"))
    (project / "tests/test_budget_probe.py").write_text(
        "import time\nimport pytest\n@pytest.fixture\ndef slow_setup():\n"
        "    time.sleep(0.15)\n@pytest.mark.smoke\ndef test_budget_probe(slow_setup):\n    pass\n")
    for label, options, fails in (
        ("unlimited", [], False),
        ("test-limit", ["--test-budget-seconds", "0.05"], True),
        ("total-limit", ["--total-budget-seconds", "0.001"], True),
    ):
        result_path = tmp_path / (label + ".json")
        result = run_cmd([sys.executable, "-I", "-B", project / "scripts/check.py", "--fast",
                          "--result", result_path, *options, "-q", "-k", "test_budget_probe"],
                         env=clean_environment(), cwd=tmp_path)
        assert bool(result.returncode) == fails, result.stdout + result.stderr
        observed = json.loads(result_path.read_text())
        assert observed["selected"] == 1 and observed["outcomes"] == {"passed": 1}
        assert observed["collected"] > observed["selected"] and observed["fast"]
        assert observed["durations"][observed["nodes"][0]]["setup"] >= 0.15
        assert bool(observed["budget_overruns"]) == (label == "test-limit")
        assert observed["total_budget_exceeded"] == (label == "total-limit")
