"""The runner must measure its test population, plugin origins and elapsed work."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import types

import pytest

from support import (budget_overruns, clean_environment, path_without_rustc, plugin_origins, project_copy_ignore,
                     reduced_project, rustc_stub)


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


@pytest.mark.smoke
def test_project_copy_leaves_successor_output_behind_and_keeps_the_same_names_elsewhere(tmp_path):
    """The successor's build output and FIFO-bearing evidence stay behind; the same names elsewhere copy."""
    source = tmp_path / "source"
    for name in ("successor/Cargo.toml", "successor/target/debug/x", "successor/evidence/case/request.json",
                 "tests/evidence/kept.txt", "src/target/kept.txt", ".scratch/run/x"):
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        (source / name).write_text("")
    os.mkfifo(source / "successor/evidence/case/material.bin")
    # Firing control: a copy that only skips the usual names stops at the FIFO.
    with pytest.raises(shutil.Error, match="named pipe"):
        shutil.copytree(source, tmp_path / "plain", ignore=shutil.ignore_patterns(".scratch"))
    shutil.copytree(source, tmp_path / "copy", ignore=project_copy_ignore(source))
    copied = sorted(str(path.relative_to(tmp_path / "copy")) for path in (tmp_path / "copy").rglob("*") if path.is_file())
    assert copied == ["src/target/kept.txt", "successor/Cargo.toml", "tests/evidence/kept.txt"], copied


def test_runner_budgets_fire_on_setup_and_total_work(tmp_path, run_cmd):
    source = Path(os.environ["STEWART_TEST_PROJECT"])
    project = tmp_path / "project"
    shutil.copytree(source, project, ignore=project_copy_ignore(source))
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


def load_check(tmp_path, monkeypatch):
    """Load a copy of scripts/check.py as a module; main() does not run and import starts no process."""
    script = tmp_path / "copy/scripts/check.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(Path(os.environ["STEWART_TEST_PROJECT"]) / "scripts/check.py", script)
    spec = importlib.util.spec_from_file_location("check_under_test", script)
    module = importlib.util.module_from_spec(spec)
    def spawn(*args, **kwargs):
        raise AssertionError(f"importing {script} started a process: {args!r}")
    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "Popen", spawn)
        spec.loader.exec_module(module)
    return module


def executable(path, text="#!/bin/sh\nexit 0\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)
    return path


def git_layout(tmp_path):
    """Fake Apple layout: an earlier PATH entry, a shim directory and a developer directory.

    The probe records each command with the PATH it ran under and answers the
    commands the selection runs; any other command is reported as unable to
    start, as a missing xcrun would be.
    """
    fake = types.SimpleNamespace(early=tmp_path / "early", shims=tmp_path / "usr/bin", developer=tmp_path / "Developer",
                                 version="git version 2.54.0 (Apple Git-157)", calls=[])
    fake.tools, fake.core = fake.developer / "usr/bin", fake.developer / "usr/libexec/git-core"
    fake.core.mkdir(parents=True)
    fake.shim = executable(fake.shims / "git")
    os.link(fake.shim, fake.shims / "actool")  # another name served by the same shim
    executable(fake.shims / "xed", "#!/bin/sh\nexit 1\n")  # a different file
    executable(fake.early / "python3")
    for name in ("git", "actool", "xed", "python3", "newtool"):
        executable(fake.tools / name)
    candidate = str(fake.tools / "git")
    fake.responses = {(str(fake.shims / "xcrun"), "--find", "git"): (0, candidate),
                      (str(fake.shims / "xcode-select"), "-p"): (0, str(fake.developer)),
                      (str(fake.shim), "--version"): (0, fake.version), (str(fake.shim), "--exec-path"): (0, str(fake.core)),
                      (candidate, "--version"): (0, fake.version), (candidate, "--exec-path"): (0, str(fake.core))}
    def probe(argv, path):
        fake.calls.append((tuple(argv), path))
        return fake.responses.get(tuple(argv), (None, f"[Errno 2] No such file or directory: {argv[0]!r}"))
    fake.probe = probe
    return fake


@pytest.mark.smoke
def test_git_selection_inserts_a_wrapper_for_the_verified_direct_git_before_the_shim(tmp_path, monkeypatch):
    """auto exposes only a git script that execs the verified binary, not the developer directory."""
    check = load_check(tmp_path, monkeypatch)
    fake = git_layout(tmp_path)
    later = str(tmp_path / "later")
    inherited = os.pathsep.join([str(fake.early), str(fake.shims), later])
    wrapper_dir = tmp_path / "private/git-selection"
    wrapper, target = wrapper_dir / "git", str(fake.tools / "git")
    fake.responses.update({(str(wrapper), "--version"): (0, fake.version), (str(wrapper), "--exec-path"): (0, str(fake.core))})
    selected, record = check.select_git("auto", inherited, "darwin", fake.probe, wrapper_dir, "/bin/dash", shim=fake.shim)
    assert selected.split(os.pathsep) == [str(fake.early), str(wrapper_dir), str(fake.shims), later], (
        f"the wrapper's directory belongs immediately before the shim's entry: {selected}")
    assert wrapper.read_text() == f"#!/bin/dash\nexec {shlex.quote(target)} \"$@\"\n" and os.access(wrapper, os.X_OK), (
        f"the wrapper must exec the verified binary by absolute path: {wrapper.read_text()!r}")
    # Only git changes: actool, xed, newtool and python3 keep their old resolution.
    assert record == {"requested": "auto", "inserted": str(wrapper_dir), "before": str(fake.shims),
                      "wrapper": {"path": str(wrapper), "shell": "/bin/dash", "target": target},
                      "executable": str(wrapper), "realpath": os.path.realpath(wrapper), "version": fake.version,
                      "exec_path": str(fake.core), "fallback": None,
                      "changed": {"git": {"old": str(fake.shim), "new": str(wrapper)}}}, record
    assert json.loads(json.dumps(record)) == record
    # Verification runs the binary under the inherited PATH; the recorded version and exec
    # path come from the git the tests reach, the wrapper, run under their PATH.
    assert sorted(call for call in fake.calls if call[0][0] in (target, str(wrapper))) == sorted([
        ((target, "--version"), inherited), ((target, "--exec-path"), inherited),
        ((str(wrapper), "--version"), selected), ((str(wrapper), "--exec-path"), selected)]), fake.calls


@pytest.mark.smoke
@pytest.mark.parametrize("case, fallback", [
    ("direct", "not the xcrun shim"),
    ("platform", "only on darwin, not linux"),
    ("no-xcrun", "xcrun --find git failed (None)"),
    ("xcrun-fails", "xcrun --find git failed (1)"),
    ("link", "not an absolute executable regular file named git"),
    ("version", "--version reports"),
    ("outside", "outside the developer directory"),
    ("exec-path", "--exec-path reports"),
    ("path", None),
])
def test_git_selection_leaves_path_unchanged_without_a_verified_candidate(tmp_path, monkeypatch, case, fallback):
    check = load_check(tmp_path, monkeypatch)
    fake = git_layout(tmp_path)
    entries, platform, requested = [fake.early, fake.shims], "darwin", "auto"
    candidate, xcrun = str(fake.tools / "git"), (str(fake.shims / "xcrun"), "--find", "git")
    if case == "direct":
        entries = [fake.early, fake.tools, fake.shims]
    elif case == "platform":
        platform = "linux"
    elif case == "no-xcrun":
        del fake.responses[xcrun]
    elif case == "xcrun-fails":
        fake.responses[xcrun] = (1, "")
    elif case == "link":
        # Like Apple's Git, the link reports the same version and derives a missing
        # exec path from its own location; the link itself must already be refused.
        link = tmp_path / "linked/bin/git"
        link.parent.mkdir(parents=True)
        link.symlink_to(candidate)
        fake.responses.update({xcrun: (0, str(link)), (str(link), "--version"): (0, fake.version),
                               (str(link), "--exec-path"): (0, str(tmp_path / "linked/libexec/git-core"))})
    elif case == "version":
        fake.responses[(candidate, "--version")] = (0, "git version 2.39.5")
    elif case == "outside":
        fake.responses[(str(fake.shims / "xcode-select"), "-p")] = (0, str(tmp_path / "Other"))
    elif case == "exec-path":
        fake.responses[(candidate, "--exec-path")] = (0, str(fake.developer / "libexec/git-core"))
    elif case == "path":
        requested = "path"
    inherited = os.pathsep.join(map(str, entries))
    wrapper_dir = tmp_path / "private/git-selection"
    selected, record = check.select_git(requested, inherited, platform, fake.probe, wrapper_dir, "/bin/dash", shim=fake.shim)
    assert selected == inherited, f"{case}: PATH changed to {selected}"
    assert record["inserted"] is None and record["before"] is None and record["changed"] == {}, record
    assert record["wrapper"] is None and not wrapper_dir.exists(), f"{case}: a wrapper was written: {record}"
    assert record["executable"] == shutil.which("git", path=inherited) and record["requested"] == requested, record
    if fallback is None:
        assert record["fallback"] is None, record
    else:
        assert fallback in (record["fallback"] or ""), f"{case}: expected {fallback!r} in {record['fallback']!r}"


@pytest.mark.smoke
def test_git_selection_inserts_an_explicit_executable_by_the_path_it_was_given(tmp_path, monkeypatch):
    check = load_check(tmp_path, monkeypatch)
    fake = git_layout(tmp_path)
    wrapper = executable(tmp_path / "wrapped/git")
    fake.responses[(str(wrapper), "--version")] = (0, fake.version)
    inherited = os.pathsep.join([str(fake.early), str(fake.shims)])
    selected, record = check.select_git(str(wrapper), inherited, "darwin", fake.probe, tmp_path / "unused", "/bin/dash", shim=fake.shim)
    assert selected.split(os.pathsep) == [str(fake.early), str(wrapper.parent), str(fake.shims)], selected
    assert record["inserted"] == str(wrapper.parent) and record["before"] == str(fake.shims), record
    assert record["executable"] == str(wrapper) and record["version"] == fake.version and record["fallback"] is None, record
    assert record["wrapper"] is None and not (tmp_path / "unused").exists(), "an explicit executable needs no wrapper"
    assert record["changed"] == {"git": {"old": str(fake.shim), "new": str(wrapper)}}, record
    # A link on PATH to the same file is another invocation path, from which Apple's Git
    # would derive a missing exec path, so the requested directory still goes before it.
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "git").symlink_to(wrapper)
    through_link = os.pathsep.join([str(fake.early), str(linked), str(fake.shims)])
    selected, record = check.select_git(str(wrapper), through_link, "darwin", fake.probe, tmp_path / "unused", "/bin/dash", shim=fake.shim)
    assert selected.split(os.pathsep) == [str(fake.early), str(wrapper.parent), str(linked), str(fake.shims)], (
        f"PATH reached {linked / 'git'}, a link to {wrapper}, and kept it: {record}")
    assert record["before"] == str(linked) and record["changed"] == {
        "git": {"old": str(linked / "git"), "new": str(wrapper)}}, record
    # A wrapper that execs git by name passes under the inherited PATH but finds itself, and
    # loops until the probe times out, under the tests' PATH; the record must show the latter.
    looping = executable(tmp_path / "looping/git")
    def probe(argv, path):
        if argv[0] == str(looping):
            return (0, fake.version) if path == inherited else (None, "timed out after 60 seconds")
        return fake.probe(argv, path)
    selected, record = check.select_git(str(looping), inherited, "darwin", probe, tmp_path / "unused", "/bin/dash", shim=fake.shim)
    assert record["inserted"] == str(looping.parent) and record["executable"] == str(looping), record
    assert record["version"] is None and record["exec_path"] is None, (
        f"the version and exec path must be probed under the tests' PATH {selected}: {record}")
    # With no git on PATH the directory goes last, so every name that resolved still does.
    selected, record = check.select_git(str(wrapper), str(fake.early), "linux", fake.probe, tmp_path / "unused", "/bin/dash", shim=fake.shim)
    assert selected.split(os.pathsep) == [str(fake.early), str(wrapper.parent)] and record["before"] is None, record
    selected, record = check.select_git(str(fake.shim), inherited, "darwin", fake.probe, tmp_path / "unused", "/bin/dash", shim=fake.shim)
    assert selected == inherited and record["inserted"] is None, record
    assert "already resolves" in record["fallback"], record
    # An explicit executable the insertion does not reach (here, gone since validation) is
    # refused rather than replaced by whatever git PATH reaches.
    vanished = tmp_path / "vanished/git"
    with pytest.raises(RuntimeError, match=re.escape(f"not {vanished}; refused")):
        check.select_git(str(vanished), inherited, "darwin", fake.probe, tmp_path / "unused", "/bin/dash", shim=fake.shim)


@pytest.mark.smoke
def test_git_option_refusals_and_probe_failures_name_their_cause(tmp_path, monkeypatch):
    check = load_check(tmp_path, monkeypatch)
    wrapper = executable(tmp_path / "wrapped/git")
    assert [check.git_executable(value) for value in ("auto", "path", str(wrapper))] == ["auto", "path", str(wrapper)]
    plain = tmp_path / "plain/git"
    plain.parent.mkdir()
    plain.write_text("")
    for value in ("git", "wrapped/git", str(tmp_path / "missing/git"), str(executable(tmp_path / "bin/python3")),
                  str(plain), str(tmp_path)):
        with pytest.raises(argparse.ArgumentTypeError, match="auto, path or the absolute path of an executable file named git"):
            check.git_executable(value)
    # PATH would split this directory into two entries and reach some other git.
    split = executable(tmp_path / f"a{os.pathsep}b/git")
    with pytest.raises(argparse.ArgumentTypeError, match=re.escape(f"{split.parent} contains {os.pathsep!r}")):
        check.git_executable(str(split))
    # A failing tool explains itself on stderr (an unaccepted licence, say), and
    # undecodable output must not escape as an error.
    python = [sys.executable, "-I", "-B", "-c"]
    failure = check.run_probe([*python, "import sys; sys.exit('licence not accepted')"], clean_environment())
    assert failure == (1, "licence not accepted"), f"a failing tool's stderr must become the probe output: {failure}"
    status, output = check.run_probe([*python, "import sys; sys.stdout.buffer.write(b'git \\xff')"], clean_environment())
    assert status == 0 and output.startswith("git "), (status, output)
    status, output = check.run_probe([tmp_path / "missing/xcrun", "--find", "git"], clean_environment())
    assert status is None and str(tmp_path / "missing/xcrun") in output, output


def test_runner_gives_the_tests_the_selected_git(tmp_path, run_cmd):
    git = shutil.which("git")
    assert git, "the end-to-end selection needs a git on this test's PATH"
    version = run_cmd([git, "--version"], check=True).stdout.strip()
    exec_path = run_cmd([git, "--exec-path"], check=True).stdout.strip()
    # The wrapper execs this test's git by absolute path, which keeps that git's exec
    # path and makes the outcome independent of the selection the outer run made.
    wrapper = executable(tmp_path / "wrapped/git", f"#!/bin/sh\nexec {shlex.quote(git)} \"$@\"\n")
    seen = tmp_path / "seen.json"
    probe = ("import json, shutil, subprocess\nfrom pathlib import Path\n\n\ndef test_git_probe():\n"
             "    git = shutil.which('git')\n"
             "    exec_path = subprocess.run([git, '--exec-path'], capture_output=True, text=True, check=True).stdout.strip()\n"
             f"    Path({str(seen)!r}).write_text(json.dumps({{'git': git, 'exec_path': exec_path}}))\n")
    project = reduced_project(Path(os.environ["STEWART_TEST_PROJECT"]), tmp_path / "project", {"test_git_probe.py": probe})
    result_path = tmp_path / "git.json"
    result = run_cmd([sys.executable, "-I", "-B", project / "scripts/check.py", "--result", result_path,
                      "--git-executable", wrapper, "-q"], env=clean_environment(), cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result_path.read_text())
    assert observed["selected"] == 1 and observed["outcomes"] == {"passed": 1}, observed["node_outcomes"]
    record = observed["git_selection"]
    assert record["requested"] == str(wrapper) and record["inserted"] == str(wrapper.parent), record
    assert record["wrapper"] is None, record
    assert os.path.join(record["before"], "git") == git and record["fallback"] is None, (
        f"the wrapper belongs immediately before the entry that supplied {git}: {record}")
    assert record["executable"] == str(wrapper) and record["realpath"] == os.path.realpath(wrapper), record
    assert record["version"] == version and record["exec_path"] == exec_path, record
    assert record["changed"] == {"git": {"old": git, "new": str(wrapper)}}, record
    assert json.loads(seen.read_text()) == {"git": str(wrapper), "exec_path": exec_path}, (
        "the probe test did not reach the selected git and its exec path")
    transcript = result_path.with_suffix(".log").read_text().splitlines()
    assert [json.loads(line) for line in transcript if line.startswith('{"git_selection"')] == [{"git_selection": record}], (
        "the .log must carry the receipt's selection record once")
    assert f"[stewart] git {wrapper} ({version}): inserted {wrapper.parent}" in result.stdout, result.stdout
    # The option parser refuses a malformed request before any environment is provisioned.
    refused = run_cmd([sys.executable, "-I", "-B", project / "scripts/check.py", "--result", tmp_path / "refused.json",
                       "--git-executable", "git"], env=clean_environment(), cwd=tmp_path)
    assert refused.returncode == 2 and "argument --git-executable: expected auto, path" in refused.stderr, refused.stderr
    assert not result_path.with_name("refused.log").exists(), "a refused request opened a transcript"


@pytest.mark.smoke
def test_provisioning_path_drops_each_entry_that_supplies_rustc(tmp_path, monkeypatch):
    """Only entries where shutil.which, pip's own lookup, finds rustc go; the rest keep their order.

    support.path_without_rustc, which the suite's own pip starts use, agrees on every case.
    """
    check = load_check(tmp_path, monkeypatch)
    supplier, other, plain, directory = (tmp_path / name for name in ("supplier", "other", "plain", "directory"))
    executable(supplier / "rustc")
    executable(other / "cargo")
    (plain / "rustc").parent.mkdir()
    (plain / "rustc").write_text("")  # not executable, so pip cannot run it either
    (directory / "rustc").mkdir(parents=True)
    entries = [str(other), str(supplier), str(plain), str(directory), str(supplier)]
    kept, removed = check.provisioning_path(os.pathsep.join(entries))
    assert removed == [str(supplier), str(supplier)], removed
    assert kept.split(os.pathsep) == [str(other), str(plain), str(directory)], kept
    assert shutil.which("rustc", path=kept) is None and shutil.which("cargo", path=kept) == str(other / "cargo")
    unchanged = os.pathsep.join([str(other), str(plain)])
    assert check.provisioning_path(unchanged) == (unchanged, []) and check.provisioning_path("") == ("", [])
    # shutil.which finds nothing in path='', so an empty entry stays; a relative entry is
    # judged in check.py's working directory.
    empty_first = os.pathsep.join(["", str(other)])
    assert check.provisioning_path(empty_first) == (empty_first, [])
    monkeypatch.chdir(tmp_path)
    assert check.provisioning_path("supplier") == ("", ["supplier"])
    # The suite's own pip starts get the same PATH.
    for value in (os.pathsep.join(entries), unchanged, "", empty_first, "supplier"):
        assert path_without_rustc(value) == check.provisioning_path(value)[0], value


def test_runner_withholds_rustc_from_provisioning(tmp_path, run_cmd):
    """Provisioning starts no rustc, while the tests' PATH still reaches it.

    pip runs `rustc --version` for its user agent wherever rustc resolves, and under a
    test's empty HOME a rustup proxy would start installing a toolchain. The stub comes
    first on PATH and shadows any proxy. Its probe test reads the stub's log before
    anything else, then starts pip under the tests' PATH (the firing control: the
    installed pip still probes) and the stub by name.
    """
    calls = tmp_path / "rustc-calls.log"
    calls.write_text("")
    stub = rustc_stub(tmp_path / "rustc-stub", calls)
    seen = tmp_path / "rustc-seen.json"
    probe = ("import json, shutil, subprocess, sys\nfrom pathlib import Path\n\n\ndef test_rustc_probe(tmp_path):\n"
             f"    calls = Path({str(calls)!r})\n"
             "    before = calls.read_text()\n"
             "    pip = subprocess.run([sys.executable, '-I', '-B', '-m', 'pip', 'install', '--no-index', '--no-deps',\n"
             "                          '--dry-run', '--find-links', str(tmp_path), 'absent-package']).returncode\n"
             "    after_pip = calls.read_text()\n"
             "    status = subprocess.run(['rustc', '--probe']).returncode\n"
             f"    Path({str(seen)!r}).write_text(json.dumps({{'rustc': shutil.which('rustc'), 'before': before, "
             "'pip': pip, 'after_pip': after_pip, 'status': status}))\n")
    project = reduced_project(Path(os.environ["STEWART_TEST_PROJECT"]), tmp_path / "project", {"test_rustc_probe.py": probe})
    env = clean_environment()
    env["PATH"] = os.pathsep.join([str(stub.parent), env.get("PATH", os.defpath)])
    result_path = tmp_path / "rustc.json"
    result = run_cmd([sys.executable, "-I", "-B", project / "scripts/check.py", "--result", result_path, "-q"],
                     env=env, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result_path.read_text())
    assert observed["selected"] == 1 and observed["outcomes"] == {"passed": 1}, observed["node_outcomes"]
    probed = json.loads(seen.read_text())
    assert probed["before"] == "", (
        f"rustc started before the tests (ensurepip, the pip installs or the build): {probed['before'].splitlines()}")
    assert probed["pip"] == 1 and probed["after_pip"] == "--version\n", (
        f"pip under the tests' PATH must start {stub} once for its user agent, or the empty log shows nothing: {probed}")
    assert probed["rustc"] == str(stub) and probed["status"] == 1, f"the tests' PATH must still reach {stub}: {probed}"
    assert calls.read_text() == "--version\n--probe\n", f"only the probe test starts {stub}: {calls.read_text().splitlines()}"
    removed = [entry for entry in env["PATH"].split(os.pathsep) if shutil.which("rustc", path=entry)]
    assert removed[0] == str(stub.parent) and observed["provisioning_path_removed"] == removed, (
        f"the result must name every PATH entry withheld from provisioning, {removed}: "
        f"{observed.get('provisioning_path_removed')}")
    transcript = result_path.with_suffix(".log").read_text().splitlines()
    assert [json.loads(line) for line in transcript if line.startswith('{"provisioning_path_removed"')] == [
        {"provisioning_path_removed": removed}], "the .log must carry the result's removed entries once"
    assert f"[stewart] provisioning PATH omits {os.pathsep.join(removed)}" in result.stdout, result.stdout


PROBE = "tests/test_retention_probe.py::"
# Every way a node can end, each leaving command records and a HOME to retain or remove.
# Pytest runs these in file order: test_interrupts ends the session, so only test_killed follows it.
RETENTION_PROBE = """\
import os
import signal
import sys
import time

import pytest


def record(run_cmd, label):
    run_cmd([sys.executable, "-I", "-B", "-c", f"print({label!r})"], check=True)


@pytest.fixture
def failing_setup(run_cmd):
    record(run_cmd, "setup")
    raise RuntimeError("probe setup failure")


@pytest.fixture
def failing_teardown(run_cmd):
    yield
    record(run_cmd, "teardown")
    raise RuntimeError("probe teardown failure")


def test_passes(run_cmd):
    record(run_cmd, "passes")


@pytest.mark.smoke
def test_kept(run_cmd):
    record(run_cmd, "kept")


def test_locks_its_tree(tmp_path):
    sealed = tmp_path / "locked/sealed"
    sealed.mkdir(parents=True)
    (sealed / "inner.txt").write_text("inner\\n")
    sealed.chmod(0)
    sealed.parent.chmod(0o500)


def test_leaves_unowned_entry(tmp_path_factory):
    (tmp_path_factory.getbasetemp() / "unowned-probe").mkdir()


def test_leaves_unremovable(tmp_path):
    (tmp_path / "stuck").mkdir()
    (tmp_path / "stuck/retention-probe-unremovable").write_text("refused only where a test injects the fault\\n")


def test_overruns_budget(run_cmd):
    record(run_cmd, "overruns")
    time.sleep(1.5)


def test_skips():
    pytest.skip("probe skip")


@pytest.mark.skip(reason="probe skip mark")
def test_skip_marked():
    pass


def test_setup_fails(failing_setup):
    pass


def test_call_fails(run_cmd):
    record(run_cmd, "call")
    raise AssertionError("probe call failure")


def test_teardown_fails(failing_teardown):
    pass


def test_interrupts(run_cmd):
    record(run_cmd, "interrupts")
    raise KeyboardInterrupt


def test_killed(run_cmd):
    record(run_cmd, "killed")
    print("probe killed next", file=sys.stderr, flush=True)
    os.kill(os.getpid(), signal.SIGKILL)
"""
# check.py with one probe file's removal refused, as a filesystem can refuse it. shutil
# is imported first, so rmtree keeps the descriptor-based walk it chose for the real unlink.
REFUSING_UNLINK = """\
import os, runpy, shutil, sys
original = os.unlink
def unlink(path, *arguments, **options):
    if os.path.basename(os.fsdecode(path)) == "retention-probe-unremovable":
        raise PermissionError(1, "removal refused by the retention probe", os.fsdecode(path))
    return original(path, *arguments, **options)
os.unlink = unlink
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def retention_project(tmp_path):
    return reduced_project(Path(os.environ["STEWART_TEST_PROJECT"]), tmp_path / "project",
                           {"test_retention_probe.py": RETENTION_PROBE})


def run_check(run_cmd, project, result_path, *arguments, launcher=()):
    """Probes that fail by design make the invocation exit nonzero; callers assert on the result."""
    return run_cmd([sys.executable, "-I", "-B", *launcher, project / "scripts/check.py", "--result", result_path,
                    *arguments], env=clean_environment(), cwd=result_path.parent)


def retention_receipt(result, result_path):
    """The invocation's result; when pytest or check.py stopped before completing it, their streams say why."""
    assert result_path.is_file(), f"no result at {result_path}\n" + result.stdout + result.stderr
    observed = json.loads(result_path.read_text())
    assert "retention" in observed, f"{result_path} records no retention plan\n" + result.stdout + result.stderr
    return observed


def logged(streams, label, text):
    """Whether the pytest stream log holds a line of this stream containing text."""
    return any(line.startswith(label + ": ") and text in line for line in streams.read_text().splitlines())


def test_runner_removes_only_unselected_passing_artifacts(tmp_path, run_cmd):
    """Only a node whose setup, call and teardown all passed loses its directories, and only with this run's receipt.

    The first run ends in a KeyboardInterrupt after every other probe, so it
    also shows that an interrupted session still removes what passed and
    keeps its incomplete node. The second keeps everything under
    --keep-artifacts all and records a real commit and dirty state. The third
    is killed before pytest writes a receipt, beside another invocation's
    result, and must remove nothing and leave that result unrelabelled.
    """
    project = retention_project(tmp_path)
    result_path = tmp_path / "interrupted.json"
    try:
        result = run_check(run_cmd, project, result_path, "--keep-node", PROBE + "test_kept",
                           "--test-budget-seconds", "1", "-q", "-k", "not killed")
        assert result.returncode == 2, "test_interrupts interrupts the session\n" + result.stdout + result.stderr
        observed = retention_receipt(result, result_path)
        artifacts, owned, retention = Path(observed["artifacts"]), observed["owned_paths"], observed["retention"]
        phases = observed["phase_outcomes"]
        assert observed["exit_status"] == 2, f"the receipt records the interrupted session: {observed['exit_status']}"
        assert retention["policy"] == "failed", retention
        assert retention["keep_nodes"] == [PROBE + "test_kept"], retention
        assert retention["withheld"] is None and not retention["missing_keep_nodes"], retention
        passed = dict.fromkeys(("setup", "call", "teardown"), "passed")
        # test_locks_its_tree also needs owner access restored inside its tree.
        for name in ("test_passes", "test_locks_its_tree", "test_leaves_unowned_entry", "test_leaves_unremovable"):
            assert phases[PROBE + name] == passed, f"{PROBE + name}: {phases.get(PROBE + name)}"
            for path in owned[PROBE + name]:
                assert retention["results"].get(path) == "removed", (
                    f"{name} passed every phase and was not kept, so {path} goes: "
                    f"result {retention['results'].get(path)}, kept as {retention['kept'].get(path)}")
                assert not os.path.lexists(path), f"{path} is recorded as removed but remains"
        link = artifacts / "test_passescurrent"
        assert retention["results"].get(str(link)) == "removed", f"{link}: {retention['results'].get(str(link))}"
        assert not os.path.lexists(link), f"{link} is recorded as removed but remains"
        for name, label in (("test_kept", "kept"), ("test_skips", None), ("test_overruns_budget", "overruns"),
                            ("test_setup_fails", "setup"), ("test_call_fails", "call"),
                            ("test_teardown_fails", "teardown"), ("test_interrupts", "interrupts")):
            tmp, home = owned[PROBE + name]
            for path in (tmp, home):
                assert path in retention["kept"], f"{name} must keep {path}: result {retention['results'].get(path)}"
            assert (Path(home) / ".gitconfig").is_file(), f"{name} lost its private HOME {home}"
            if label:
                record = Path(tmp) / "commands/0001"
                assert (record / "command.json").is_file(), f"{name} lost its command record {record}"
                assert (record / "stdout.txt").read_text() == label + "\n", f"{name} lost its command streams {record}"
        overrun, overrun_tmp = PROBE + "test_overruns_budget", owned[PROBE + "test_overruns_budget"][0]
        assert overrun in observed["budget_overruns"], (
            f"{overrun} sleeps past the 1 s budget: {observed['budget_overruns']}")
        assert "over --test-budget-seconds" in retention["kept"][overrun_tmp], retention["kept"][overrun_tmp]
        assert phases[PROBE + "test_setup_fails"] == {"setup": "failed", "teardown": "passed"}, phases
        assert observed["node_outcomes"][PROBE + "test_setup_fails"] == {"setup": "failed"}, (
            "node_outcomes keeps its meaning: passing setup and teardown stay out of it")
        assert phases[PROBE + "test_teardown_fails"]["teardown"] == "failed", phases[PROBE + "test_teardown_fails"]
        assert phases[PROBE + "test_skips"]["call"] == "skipped", phases[PROBE + "test_skips"]
        # The interrupt left no call or teardown report; a missing phase is not a passing one.
        assert phases[PROBE + "test_interrupts"] == {"setup": "passed"}, phases[PROBE + "test_interrupts"]
        unowned = artifacts / "unowned-probe"
        assert retention["kept"].get(str(unowned)) == "no node owns this entry", retention["kept"].get(str(unowned))
        assert unowned.is_dir(), f"{unowned} is not owned by any node and stays"
        failed_link = artifacts / "test_call_failscurrent"
        assert failed_link.is_symlink(), f"{failed_link} names a kept directory and stays"
        markers = observed["markers"]
        assert markers[PROBE + "test_kept"] == ["smoke"], markers
        assert markers[PROBE + "test_passes"] == [], markers
        check_sha256 = hashlib.sha256((project / "scripts/check.py").read_bytes()).hexdigest()
        assert observed["check_sha256"] == check_sha256, f"check_sha256 {observed['check_sha256']} != {check_sha256}"
        suite = observed["suite_sha256"]
        assert suite.get("tests/test_retention_probe.py") == hashlib.sha256(RETENTION_PROBE.encode()).hexdigest(), suite
        assert {"pyproject.toml", "tests/conftest.py", "tests/support.py"} <= set(suite), suite
        # The copy has no repository of its own; a containing checkout must not describe it.
        assert observed["project_git"]["commit"] is None and observed["project_git"]["absent"], observed["project_git"]
        streams = tmp_path / "interrupted.pytest.log"
        assert logged(streams, "stdout", "probe call failure"), f"{streams}:\n{streams.read_text()}"
    finally:
        # A failed removal leaves the probe's locked tree; unlock it so the retained run stays deletable.
        for locked in tmp_path.glob("interrupted-artifacts-*/test_locks_its_tree*/locked"):
            locked.chmod(0o700)
            if (locked / "sealed").exists():
                (locked / "sealed").chmod(0o700)

    for argv in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "retention probe"]):
        run_cmd(argv, cwd=project, check=True)
    head = run_cmd(["git", "rev-parse", "HEAD"], cwd=project, check=True).stdout.strip()
    (project / "probe-untracked.txt").write_text("untracked\n")
    result_path = tmp_path / "all.json"
    result = run_check(run_cmd, project, result_path, "--keep-artifacts", "all", "-q", "-k", "test_passes")
    assert result.returncode == 0, result.stdout + result.stderr
    observed = retention_receipt(result, result_path)
    retention = observed["retention"]
    for path in observed["owned_paths"][PROBE + "test_passes"]:
        assert os.path.isdir(path), f"--keep-artifacts all removes nothing, yet {path} is gone: {retention}"
    assert retention["policy"] == "all" and retention["withheld"], retention
    assert not retention["planned"] and not retention["results"], retention
    git = observed["project_git"]
    assert git["commit"] == head and git["dirty"] and "?? probe-untracked.txt" in git["status"], git

    # SIGKILL ends pytest before its receipt, leaving another invocation's result at the
    # path; -s lets the probe's own stderr reach the pytest log.
    result_path = tmp_path / "killed.json"
    stale = (tmp_path / "interrupted.json").read_bytes()
    result_path.write_bytes(stale)
    result = run_check(run_cmd, project, result_path, "-s", "-q", "-k", "test_passes or test_killed")
    assert result.returncode, "pytest was killed\n" + result.stdout + result.stderr
    assert result_path.read_bytes() == stale, f"{result_path} belongs to another invocation and must not be relabelled"
    assert "was not written by this invocation" in result.stdout, result.stdout
    assert "retention: removed nothing" in result.stdout, result.stdout
    (artifacts,) = tmp_path.glob("killed-artifacts-*")
    remaining = {path.name for path in artifacts.iterdir()}
    assert {"test_passes0", "test_passes0-home", "test_killed0", "test_killed0-home"} <= remaining, (
        f"a run without its own receipt removes nothing: {artifacts} holds {sorted(remaining)}")
    killed_streams = artifacts / "test_killed0/commands/0001/stdout.txt"
    assert killed_streams.read_text() == "killed\n", f"{killed_streams} holds the killed node's command streams"
    streams = tmp_path / "killed.pytest.log"
    assert logged(streams, "stdout", "Stewart selected tests: 2"), f"{streams}:\n{streams.read_text()}"
    assert logged(streams, "stderr", "probe killed next"), f"{streams}:\n{streams.read_text()}"
    assert "probe killed next" in result.stderr, f"pytest's stderr reaches check.py's stderr:\n{result.stderr}"
    assert "probe killed next" not in result.stdout, f"pytest's stderr stays off check.py's stdout:\n{result.stdout}"


def test_runner_refuses_keep_node_that_did_not_execute(tmp_path, run_cmd):
    """A --keep-node target that did not execute fails the run and nothing is removed.

    An evidence run that lost its control is not evidence. Deselected and
    nonexistent IDs never report; pytest reports a skip mark as a skipped
    setup without a call, and pytest.skip() in a test as a skipped call.
    """
    project = retention_project(tmp_path)
    result_path = tmp_path / "missing.json"
    # Deselected, nonexistent, skipped in its call, and skipped by a mark before its fixtures.
    deselected, absent = PROBE + "test_kept", PROBE + "test_absent"
    skipped, skip_marked = PROBE + "test_skips", PROBE + "test_skip_marked"
    options = [option for node in (deselected, absent, skipped, skip_marked) for option in ("--keep-node", node)]
    result = run_check(run_cmd, project, result_path, *options, "-q", "-k", "test_passes or test_skip")
    assert result.returncode, (
        "a --keep-node target that did not execute fails the invocation\n" + result.stdout + result.stderr)
    observed = retention_receipt(result, result_path)
    assert observed["exit_status"] == 0, f"pytest itself passed: exit status {observed['exit_status']}"
    assert observed["outcomes"] == {"passed": 1, "skipped": 2}, observed["outcomes"]
    assert observed["runner_exit_status"] == result.returncode, (observed["runner_exit_status"], result.returncode)
    retention = observed["retention"]
    assert retention["missing_keep_nodes"] == {
        deselected: {}, absent: {}, skipped: {"setup": "passed", "call": "skipped", "teardown": "passed"},
        skip_marked: {"setup": "skipped", "teardown": "passed"}}, retention["missing_keep_nodes"]
    assert retention["withheld"], retention
    for node in (deselected, absent, skipped, skip_marked):
        assert node in result.stderr, f"stderr names the refused --keep-node {node}:\n{result.stderr}"
    assert not retention["planned"] and not retention["results"], retention
    for path in observed["owned_paths"][PROBE + "test_passes"]:
        assert os.path.isdir(path), f"a refused evidence run removes nothing, not even the passing {path}"


def test_runner_records_removal_failures_without_changing_outcomes(tmp_path, run_cmd):
    """A removal the filesystem refuses is recorded and printed, and the run still exits 0.

    The wrapper refuses one file's unlink inside check.py, as a filesystem can;
    the rest of that node's tree, its HOME and the other passing node still go,
    and its current link stays because its target remains.
    """
    project = retention_project(tmp_path)
    result_path = tmp_path / "refused.json"
    result = run_check(run_cmd, project, result_path, "-q", "-k", "test_passes or unremovable",
                       launcher=("-c", REFUSING_UNLINK))
    assert result.returncode == 0, "a removal failure changes no outcome\n" + result.stdout + result.stderr
    observed = retention_receipt(result, result_path)
    assert observed["exit_status"] == 0 == observed["runner_exit_status"], (
        observed["exit_status"], observed["runner_exit_status"])
    assert observed["outcomes"] == {"passed": 2}, observed["outcomes"]
    retention, owned, artifacts = observed["retention"], observed["owned_paths"], Path(observed["artifacts"])
    tmp, home = owned[PROBE + "test_leaves_unremovable"]
    failure = retention["results"].get(tmp, "")
    assert failure.startswith("failed:") and "retention-probe-unremovable" in failure, f"{tmp}: {failure!r}"
    assert (Path(tmp) / "stuck/retention-probe-unremovable").is_file(), f"{tmp} keeps what could not be removed"
    assert f"could not remove {tmp}" in result.stderr, result.stderr
    assert retention["results"].get(home) == "removed", f"{home}: {retention['results'].get(home)}"
    link = artifacts / "test_leaves_unremovablecurrent"
    assert retention["results"].get(str(link)) == f"kept: {tmp} was not removed", retention["results"].get(str(link))
    assert link.is_symlink(), f"{link} names a directory that remains and stays"
    for path in owned[PROBE + "test_passes"]:
        assert retention["results"].get(path) == "removed", f"{path}: {retention['results'].get(path)}"
        assert not os.path.lexists(path), f"{path} is recorded as removed but remains"
