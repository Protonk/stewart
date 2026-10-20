"""The runner must measure its test population, plugin origins and elapsed work."""
import json
import os
from pathlib import Path
import shutil
import sys
import types

import pytest

from support import budget_overruns, clean_environment, plugin_origins, reduced_project


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


PROBES = {"test_probe_a.py": "import pytest\n@pytest.mark.smoke\ndef test_alpha():\n    pass\ndef test_beta():\n    pass\n",
          "test_probe_b.py": "def test_gamma():\n    pass\ndef test_epsilon():\n    pass\n"}
ALPHA, BETA, GAMMA, EPSILON = ("tests/test_probe_a.py::test_alpha", "tests/test_probe_a.py::test_beta",
                               "tests/test_probe_b.py::test_gamma", "tests/test_probe_b.py::test_epsilon")


def check_probes(tmp_path, run_cmd, *arguments, env=None):
    """Run check.py over a copy of the project whose tests are only the harness and PROBES."""
    project = reduced_project(Path(os.environ["STEWART_TEST_PROJECT"]), tmp_path / "project", PROBES)
    arguments = [str(argument) for argument in arguments]
    result_path = tmp_path / "selection.json"
    result = run_cmd([sys.executable, "-I", "-B", project / "scripts/check.py", "--result", result_path, *arguments],
                     env=env or clean_environment(), cwd=tmp_path)
    output = result.stdout + result.stderr
    assert result_path.is_file(), f"check.py {arguments} wrote no receipt\n{output}"
    return result.returncode, output, json.loads(result_path.read_text())


@pytest.mark.parametrize("arguments,collected,selected", [
    (["tests/test_probe_a.py", EPSILON], [ALPHA, BETA, EPSILON], [ALPHA, BETA, EPSILON]),
    (["-k", "beta or gamma", "--deselect", GAMMA], [ALPHA, BETA, GAMMA, EPSILON], [BETA]),
    (["--fast"], [ALPHA, BETA, GAMMA, EPSILON], [ALPHA]),
], ids=["file-and-node", "keyword", "fast"])
def test_runner_selection_runs_each_node_once(tmp_path, run_cmd, arguments, collected, selected):
    """A named file or node ID runs only its own nodes, once; -k, --deselect and --fast deselect as before.

    check.py used to pass the suite's tests directory ahead of the caller's
    arguments, so pytest collected every test and then the named ones again.
    A --deselect prefix names a node as pytest does and must reach it unchanged.
    """
    status, output, receipt = check_probes(tmp_path, run_cmd, *arguments)
    assert (receipt["collected_nodes"], receipt["nodes"]) == (collected, selected), (
        f"{arguments} collected {receipt['collected_nodes']} and selected {receipt['nodes']}\n{output}")
    assert (receipt["collected"], receipt["selected"], receipt["deselected"]) == (
        len(collected), len(selected), len(collected) - len(selected))
    assert status == 0 and receipt["outcomes"] == {"passed": len(selected)}, output
    assert receipt["fast"] == ("--fast" in arguments)


@pytest.mark.parametrize("arguments,refusal,collected,deselected,named", [
    (["tests/test_probe_a.py", ALPHA, "-k", "beta"], "collects a node more than once", [ALPHA, BETA, ALPHA], 0, [ALPHA]),
    (["-k", "no_probe_matches"], "Stewart test selection is empty", [ALPHA, BETA, GAMMA, EPSILON], 4, []),
    (["test_probe_a.py"], "file or directory not found: test_probe_a.py", [], 0, []),
    (["-k", "beta and ("], "Wrong expression passed to '-k'", [ALPHA, BETA, GAMMA, EPSILON], 0, []),
], ids=["overlap", "empty", "missing", "unparsable"])
def test_runner_refuses_unrunnable_selections(tmp_path, run_cmd, arguments, refusal, collected, deselected, named):
    """Pytest runs a node once per overlapping argument; the harness refuses rather than deduplicate.

    The repeat is refused at collection, before -k applies, so the receipt
    selects and deselects nothing. A path pytest cannot find (here without the
    tests/ prefix) or a -k expression it cannot parse reports pytest's own
    error, not an empty selection, and its receipt selects nothing either.
    """
    status, output, receipt = check_probes(tmp_path, run_cmd, *arguments)
    lines = [line for line in output.splitlines() if refusal in line]
    assert status == pytest.ExitCode.USAGE_ERROR and lines, (
        f"{arguments} should be refused with {refusal!r}; check.py exited {status}\n{output}")
    assert all(node in lines[0] for node in named), f"the refusal must name {named}: {lines[0]}"
    assert not any(node in lines[0] for node in {ALPHA, BETA, GAMMA, EPSILON} - set(named)), (
        f"the refusal names nodes beyond {named}: {lines[0]}")
    assert (receipt["collected_nodes"], receipt["nodes"], receipt["deselected"]) == (collected, [], deselected), (
        f"{arguments} recorded collected {receipt['collected_nodes']}, selected {receipt['nodes']} and "
        f"{receipt['deselected']} deselected")
    assert receipt["outcomes"] == {}, f"a refused selection ran tests: {receipt['node_outcomes']}"


def test_runner_fails_a_selection_that_never_loads_the_staged_conftest(tmp_path, run_cmd):
    """Pytest anchors conftests on the named paths, so a test elsewhere named alone runs unchecked.

    No staged conftest means no boundary assertions, refusals or receipt; the
    probe itself passes, and check.py must still fail the invocation. The
    outside probe sits as test_runner_refuses_tests_outside_the_staged_suite
    places it, so no conftest along its path loads either.
    """
    temporary = (tmp_path / "temporary").resolve()
    temporary.mkdir()
    outside = temporary / "test_outside_probe.py"
    outside.write_text("def test_delta():\n    pass\n")
    project = reduced_project(Path(os.environ["STEWART_TEST_PROJECT"]), tmp_path / "project", PROBES)
    result_path = tmp_path / "selection.json"
    result = run_cmd([sys.executable, "-I", "-B", project / "scripts/check.py", "--result", result_path, outside],
                     env={**clean_environment(), "TMPDIR": str(temporary)}, cwd=tmp_path)
    output = result.stdout + result.stderr
    assert result.returncode != 0 and "without writing this invocation's receipt" in output, (
        f"{outside} alone ran without the staged conftest; check.py exited {result.returncode}\n{output}")
    assert not result_path.exists(), f"no staged conftest ran, yet {result_path} exists\n{output}"


def test_runner_refuses_tests_outside_the_staged_suite(tmp_path, run_cmd):
    """Tests named by absolute paths elsewhere are refused by path, although their node IDs repeat.

    The staged path makes pytest load the suite's conftest, which does the
    refusing. Pytest names a module outside its rootdir relative to the
    argument that named it, so both outside probes collect as one node ID.
    check.py's private directory goes under tmp_path, making the outside probes'
    directory an ancestor of the staged --confcutdir: pytest then loads no
    conftest along the probes' path, wherever the outer run keeps its results.
    """
    temporary = (tmp_path / "temporary").resolve()
    temporary.mkdir()
    outside = [temporary / "test_outside_probe.py", temporary / "test_outside_twin.py"]
    for probe in outside:
        probe.write_text("def test_delta():\n    pass\n")
    status, output, receipt = check_probes(tmp_path, run_cmd, "tests/test_probe_b.py", *outside,
                                           env={**clean_environment(), "TMPDIR": str(temporary)})
    lines = [line for line in output.splitlines() if "outside the staged suite's tests directory" in line]
    assert status == pytest.ExitCode.USAGE_ERROR and lines, (
        f"{outside} lie outside the staged suite and should be refused; check.py exited {status}\n{output}")
    assert all(str(probe) in lines[0] for probe in outside), f"the refusal must name {outside}: {lines[0]}"
    assert "test_delta" in lines[0] and not any(node in lines[0] for node in {GAMMA, EPSILON}), (
        f"only the outside tests are named: {lines[0]}")
    assert receipt["collected_nodes"][:2] == [GAMMA, EPSILON] and receipt["collected"] == 4, (
        f"expected the staged file's two nodes and both outside probes: {receipt['collected_nodes']}")
    assert (receipt["nodes"], receipt["deselected"]) == ([], 0), f"a refused selection selected {receipt['nodes']}"
    assert receipt["outcomes"] == {}, f"a refused selection ran tests: {receipt['node_outcomes']}"
