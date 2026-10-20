"""Assert test independence and publish the actual collection population."""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import sys

import pytest
import _pytest

from support import run_cmd as _run_cmd, stage_runtime, plugin_origins, budget_overruns


def pytest_configure(config):
    config.stewart_outcomes = Counter()
    config.stewart_node_outcomes = {}
    config.stewart_durations = {}
    project = Path(__file__).resolve().parents[1]
    assert config.inipath == project / "pyproject.toml", f"wrong pytest configuration: {config.inipath}"
    assert config.getini("testpaths") == ["tests"], "local pytest testpaths were not applied"
    assert config.option.strict_markers, "local pytest strict marker policy was not applied"
    argv = list(config.invocation_params.args)
    assert "-c" in argv and argv[argv.index("-c") + 1] == str(config.inipath), "explicit pytest configuration is required"
    assert f"--confcutdir={project}" in argv, "explicit conftest boundary is required"
    assert os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1"
    assert os.environ.get("STEWART_TEST_RUNTIME"), "use scripts/check.py to select an isolated installation"
    assert str(project) == os.environ.get("STEWART_TEST_SUITE"), "wrong staged test suite"
    assert project != Path(os.environ["STEWART_TEST_PROJECT"]).resolve(), "tests must run from their staged copy"
    import stewart as installed
    expected = Path(os.environ["STEWART_TEST_RUNTIME"]) / "stewart"
    assert Path(installed.__file__).resolve() == expected / "__init__.py", "wrong Stewart installation"
    assert list(installed.__path__) == [str(expected)], "package search path escapes the selected installation"
    from stewart._bootstrap import source_payloads
    manifest, payloads = source_payloads(expected)
    config.stewart_source_members = sorted(payloads)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_collection_modifyitems(session, config, items):
    """Count discovered nodes before pytest's marker and keyword deselection.

    Overlapping arguments (a file and one of its node IDs) make pytest collect
    and run a node twice, so a repeated node or a test outside this staged
    suite's tests directory refuses the selection instead of being deduplicated.
    Outside tests are refused first and named by path: pytest names a module
    outside the rootdir relative to the argument that named it, so their node
    IDs can repeat one another or a staged node's.
    """
    config.stewart_collected_nodes = [item.nodeid for item in items]
    tests = Path(__file__).resolve().parent
    outside = [f"{item.nodeid} ({item.path})" for item in items if not item.path.resolve().is_relative_to(tests)]
    if outside:
        raise pytest.UsageError(f"Stewart test selection names tests outside the staged suite's tests "
                                f"directory {tests}: {outside}; name tests relative to the suite root, "
                                "as tests/<file>.py or tests/<file>.py::<test>")
    repeated = sorted(node for node, count in Counter(config.stewart_collected_nodes).items() if count > 1)
    if repeated:
        raise pytest.UsageError(f"Stewart test selection collects a node more than once: {repeated}; "
                                "name each test file or node ID once")
    outcome = yield
    try:
        outcome.get_result()
    except BaseException:
        return  # pytest could not parse -k or -m; pluggy raises that error after this wrapper
    config.stewart_selection_finished = True


def pytest_collection_finish(session):
    # Cover every active plugin, including injected objects and conftests,
    # instead of naming one containing project's known plugin.
    session.config.stewart_plugins = plugin_origins(
        session.config.pluginmanager.list_name_plugin(), Path(_pytest.__file__).parent, Path(__file__))
    # Pytest also calls this hook after a refused or failed collection (a
    # repeated node, a path it cannot find, an unparsable -k). Nothing was
    # selected then, and that error must reach the caller unmasked.
    if not getattr(session.config, "stewart_selection_finished", False):
        session.config.stewart_nodes = []
        return
    session.config.stewart_nodes = [item.nodeid for item in session.items]
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    if reporter:
        reporter.write_line(f"Stewart selected tests: {len(session.items)}")
    if not session.items:
        raise pytest.UsageError("Stewart test selection is empty")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    item.config.stewart_durations.setdefault(item.nodeid, {})[report.when] = report.duration
    if report.when == "call" or (report.when in {"setup", "teardown"} and report.outcome != "passed"):
        item.config.stewart_outcomes[report.outcome] += 1
        item.config.stewart_node_outcomes.setdefault(item.nodeid, {})[report.when] = report.outcome


def pytest_sessionfinish(session, exitstatus):
    budget = os.environ.get("STEWART_TEST_BUDGET_SECONDS")
    overruns = budget_overruns(session.config.stewart_durations, float(budget)) if budget else {}
    if overruns:
        session.exitstatus = int(exitstatus) or 1
        reporter = session.config.pluginmanager.getplugin("terminalreporter")
        if reporter:
            reporter.write_line(f"Stewart test budget exceeded ({budget}s, setup + call + teardown): {overruns}", red=True)
    destination = os.environ.get("STEWART_TEST_RESULT")
    if destination:
        collected = getattr(session.config, "stewart_collected_nodes", [])
        selected = getattr(session.config, "stewart_nodes", [])
        # Deselection counts only for a selection pytest finished; a refused or
        # failed one runs nothing, whatever it collected.
        finished = getattr(session.config, "stewart_selection_finished", False)
        value = {"nodes": selected, "collected_nodes": collected,
                 "collected": len(collected), "selected": len(selected),
                 "deselected": len(collected) - len(selected) if finished else 0,
                 "exit_status": int(session.exitstatus),
                 "plugins": getattr(session.config, "stewart_plugins", {}),
                 "durations": session.config.stewart_durations,
                 "test_budget_seconds": float(budget) if budget else None, "budget_overruns": overruns,
                 "outcomes": dict(session.config.stewart_outcomes),
                 "node_outcomes": session.config.stewart_node_outcomes,
                 "source_members": getattr(session.config, "stewart_source_members", []),
                 "wheel": os.environ["STEWART_TEST_WHEEL"],
                 "wheel_sha256": os.environ["STEWART_TEST_WHEEL_SHA256"],
                 "artifacts": os.environ["STEWART_TEST_ARTIFACTS"],
                 "config": str(session.config.inipath), "python": sys.version,
                 "runtime": os.environ["STEWART_TEST_RUNTIME"]}
        Path(destination).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def run_cmd(tmp_path):
    """Retain every command's arguments and streams in the owning fixture."""
    directory = tmp_path / "commands"
    directory.mkdir(exist_ok=True)
    count = 0
    def invoke(argv, **kwargs):
        nonlocal count
        count += 1
        checked = kwargs.pop("check", False)
        supplied = kwargs.get("env")
        kwargs["env"] = {"STEWART_MANAGER_HOME": os.environ["STEWART_MANAGER_HOME"], "HOME": os.environ["HOME"],
                         **(dict(os.environ) if supplied is None else supplied)}
        result = _run_cmd(argv, check=False, **kwargs)
        item = directory / f"{count:04d}"
        item.mkdir()
        (item / "command.json").write_text(json.dumps({"argv": list(map(str, argv)),
            "cwd": str(kwargs.get("cwd")), "returncode": result.returncode}) + "\n")
        (item / "stdout.txt").write_text(result.stdout)
        (item / "stderr.txt").write_text(result.stderr)
        if checked and result.returncode:
            raise AssertionError(f"command failed ({result.returncode}); {item}\n{result.stdout}\n{result.stderr}")
        return result
    return invoke


@pytest.fixture(autouse=True)
def private_manager_storage(tmp_path, monkeypatch):
    """Commands must never populate the developer's actual manager or checkout homes.

    Stewart's default checkout home and manager home derive from HOME, so each
    test, and each command it runs through ``run_cmd``, gets a private HOME.
    Git reads its global configuration there too; a minimal identity keeps
    commits independent of the developer's own configuration.
    """
    monkeypatch.setenv("STEWART_MANAGER_HOME", str(tmp_path / "api-manager-home"))
    # Beside the test's directory, so tests that measure tmp_path see only their own entries.
    home = tmp_path.with_name(tmp_path.name + "-home")
    home.mkdir(mode=0o700)
    (home / ".gitconfig").write_text("[user]\n\tname = Stewart test\n\temail = stewart-test@example.invalid\n")
    monkeypatch.setenv("HOME", str(home))


@pytest.fixture
def installation(tmp_path):
    return stage_runtime(tmp_path / "installation")


@pytest.fixture
def checkout(tmp_path, run_cmd):
    import stewart_support
    return stewart_support.make_checkout(tmp_path, run_cmd)


@pytest.fixture
def project_repo(tmp_path, run_cmd):
    """Ordinary target project: no tool modules, marker or project virtualenv."""
    root = (tmp_path / "project").resolve()
    root.mkdir()
    run_cmd(["git", "init", "-q", "-b", "review"], cwd=root)
    run_cmd(["git", "config", "user.name", "Stewart test"], cwd=root)
    run_cmd(["git", "config", "user.email", "stewart@example.invalid"], cwd=root)
    (root / "input.txt").write_text("project input\n", encoding="utf-8")
    guidance = root / "reviews/example"
    guidance.mkdir(parents=True)
    (guidance / "AUDITOR.md").write_text("Read the bounded assignment.\n", encoding="utf-8")
    (guidance / "MAINTAINER.md").write_text("Collect and review the assigned evidence.\n", encoding="utf-8")
    run_cmd(["git", "add", "."], cwd=root)
    run_cmd(["git", "commit", "-qm", "project"], cwd=root)
    return root
