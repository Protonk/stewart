"""scripts/prune.py removes only bound artifacts directories, records every removal and keeps each run's record."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from support import clean_environment

pytestmark = pytest.mark.system

# Refuses one file's unlink inside prune.py, as a filesystem can; shutil keeps its descriptor-based walk.
REFUSING_UNLINK = """\
import os, runpy, sys
original = os.unlink
def unlink(path, *arguments, **options):
    if os.path.basename(os.fsdecode(path)) == "prune-probe-unremovable":
        raise PermissionError(1, "removal refused by the prune probe", os.fsdecode(path))
    return original(path, *arguments, **options)
os.unlink = unlink
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def receipt(root, name, **fields):
    """A check.py-shaped receipt at root/name.json binding root/name-artifacts-probe, with content inside."""
    path = root / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    artifacts = path.with_name(f"{path.stem}-artifacts-probe")
    (artifacts / "test_probe0/commands/0001").mkdir(parents=True)
    (artifacts / "test_probe0/commands/0001/stdout.txt").write_text(name + "\n")
    (artifacts / "test_probe0-home").mkdir()
    (artifacts / "test_probe0-home/.gitconfig").write_text("[user]\n\tname = probe\n")
    os.symlink("test_probe0", artifacts / "test_probecurrent")
    wheel = path.with_name(f"{path.stem}-dist") / "stewart-0.1.0-py3-none-any.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"not a wheel\n")
    value = {"artifacts": str(artifacts), "wheel": str(wheel), "nodes": ["tests/test_probe.py::test_probe"],
             "outcomes": {"passed": 1}, "exit_status": 0, "runner_exit_status": 0, "budget_overruns": {},
             "total_budget_exceeded": False, "retention": {"policy": "failed", "keep_nodes": [], "withheld": None,
                                                           "planned": [], "results": {}, "kept": {}}}
    value.update(fields)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    path.with_suffix(".log").write_text("provisioning\n")
    return path, artifacts


def git_project(run_cmd, project, citing):
    """A Git work tree whose one tracked file names the given stems."""
    project.mkdir()
    (project / "NOTES.md").write_text("Evidence: " + ", ".join(f"`{stem}.json`" for stem in citing) + "\n")
    for argv in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "prune probe"]):
        run_cmd(argv, cwd=project, check=True)
    return project


def prune(run_cmd, root, project, *arguments, launcher=()):
    script = Path(os.environ["STEWART_TEST_PROJECT"]) / "scripts/prune.py"
    return run_cmd([sys.executable, "-I", "-B", *launcher, script, "--root", root, "--project", project, *arguments],
                   env=clean_environment(), cwd=root)


def decisions(result):
    """Each printed run or orphan line's decision, keyed by the name or orphan path the line names."""
    observed = {}
    for line in result.stdout.splitlines():
        if line.startswith("[prune] ") and " -> " in line:
            label, decision = line[len("[prune] "):].split(" -> ", 1)
            observed[label.split(":", 1)[0]] = decision
    return observed


def test_prune_plans_without_writing_and_removes_only_what_the_policy_or_the_caller_selects(tmp_path, run_cmd):
    """The default plan takes clean, uncited, non-evidence runs whose receipt binds their directory.

    Failed, cited and evidence runs stay until named; an unbound receipt, a
    link, an orphan and a directory a running process names stay regardless,
    and naming an unbound run refuses the whole invocation. Records are never
    touched; each removal is recorded before it starts and marked beside its
    receipt afterwards.
    """
    root = tmp_path / "scratch"
    project = git_project(run_cmd, tmp_path / "project", citing=["cited"])
    _, green = receipt(root, "green")
    _, nested = receipt(root, "group/nested")
    _, red = receipt(root, "red", outcomes={"failed": 1, "passed": 1}, exit_status=1, runner_exit_status=1)
    _, cited = receipt(root, "cited")
    _, evidence = receipt(root, "evidence", retention={"policy": "all", "keep_nodes": [], "withheld": "all",
                                                       "planned": [], "results": {}, "kept": {}})
    _, overrun = receipt(root, "overrun", budget_overruns={"tests/test_probe.py::test_probe": 9.0})
    _, busy = receipt(root, "busy")
    elsewhere_receipt, elsewhere = receipt(root, "elsewhere")
    moved = tmp_path / "moved-artifacts-probe"
    elsewhere.rename(moved)
    elsewhere_receipt.write_text(json.dumps({**json.loads(elsewhere_receipt.read_text()), "artifacts": str(moved)}))
    linked_receipt, linked = receipt(root, "linked")
    target = tmp_path / "link-target"
    linked.rename(target)
    os.symlink(target, linked)
    orphan = root / "orphan-artifacts-probe"
    (orphan / "test_probe0").mkdir(parents=True)
    (root / "wheelhouse").mkdir()
    (root / "wheelhouse/notes-artifacts-wheel").mkdir()  # inside an unentered directory: not a candidate
    (root / "validation.json").write_text(json.dumps({"runs": [str(green)]}) + "\n")  # not a receipt
    records = {path: path.read_bytes() for path in root.rglob("*") if path.is_file() and path.suffix in (".json", ".log", ".whl")}
    # Two commands, so the shell keeps running with the path among its arguments instead of
    # exec-ing sleep in its place; a trailing comment would be optimized away.
    holder = subprocess.Popen(["/bin/sh", "-c", "sleep 60; exit 0", str(busy)], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        result = prune(run_cmd, root, project)
        assert result.returncode == 0, result.stdout + result.stderr
        observed = decisions(result)
        assert observed["green"].startswith("planned") and observed["group/nested"].startswith("planned"), observed
        assert "1 failed" in observed["red"] and "exit status 1" in observed["red"], observed["red"]
        assert "cited by NOTES.md" in observed["cited"], observed["cited"]
        assert "evidence run (--keep-artifacts all)" in observed["evidence"], observed["evidence"]
        assert "over the test budget" in observed["overrun"], observed["overrun"]
        assert "named by a running process" in observed["busy"] and str(busy) in observed["busy"], observed["busy"]
        assert observed["elsewhere"].startswith("kept: the receipt names") and str(moved) in observed["elsewhere"]
        assert observed["linked"] == f"kept: the receipt names {linked}, which is not a directory (a link)", observed["linked"]
        assert observed["orphan orphan-artifacts-probe"] == "kept: no receipt binds it (remove orphans with --orphans)", observed
        assert "wheelhouse" not in result.stdout and "validation" not in result.stdout, result.stdout
        assert "dry run" in result.stdout and not (root / "pruned").exists(), result.stdout
        for path in (green, nested, red, cited, evidence, overrun, busy, moved, target, orphan):
            assert path.is_dir(), f"a dry run removed {path}"

        refused = prune(run_cmd, root, project, "--run", "elsewhere", "--run", "green", "--apply")
        assert refused.returncode == 2, refused.stdout + refused.stderr
        assert "refused: --run elsewhere: the receipt names" in refused.stderr, refused.stderr
        assert "nothing was removed" in refused.stderr and green.is_dir() and not (root / "pruned").exists()
        refused = prune(run_cmd, root, project, "--run", "absent", "--apply")
        assert refused.returncode == 2 and "names no receipt under the root" in refused.stderr, refused.stderr
        refused = prune(run_cmd, root, project, "--run", "busy", "--apply")
        assert refused.returncode == 2 and "named by a running process" in refused.stderr, refused.stderr
        assert busy.is_dir() and green.is_dir() and not (root / "pruned").exists()

        applied = prune(run_cmd, root, project, "--apply")
        assert applied.returncode == 0, applied.stdout + applied.stderr
        assert not green.exists() and not nested.exists(), applied.stdout
        for path in (red, cited, evidence, overrun, busy, moved, target, orphan):
            assert path.is_dir(), f"the default plan removed {path}\n{applied.stdout}"
        (record,) = (root / "pruned").glob("*.json")
        recorded = json.loads(record.read_text())
        assert sorted(recorded["planned"]) == sorted([str(green), str(nested)]), recorded["planned"]
        assert recorded["results"] == {str(green): "removed", str(nested): "removed"}, recorded["results"]
        assert recorded["runs"]["red"]["decision"].startswith("kept: outcomes 1 failed, 1 passed"), recorded["runs"]["red"]
        assert recorded["runs"]["green"]["marker"] == str(root / "green.pruned.json"), recorded["runs"]["green"]
        assert recorded["project"] == str(project) and recorded["citations_unknown"] is None, recorded
        marker = json.loads((root / "green.pruned.json").read_text())
        assert marker == {"record": str(record), "pruned_artifacts": str(green), "result": "removed",
                          "allocated_bytes": recorded["runs"]["green"]["allocated_bytes"],
                          "entries": recorded["runs"]["green"]["entries"]}, marker
        assert (root / "group/nested.pruned.json").is_file() and not (root / "red.pruned.json").exists()
        assert f"record {record}" in applied.stdout, applied.stdout
        again = decisions(prune(run_cmd, root, project))
        assert again["green"] == f"kept: its artifacts directory was pruned; {root / 'green.pruned.json'} names the record", again
    finally:
        holder.kill()
        holder.wait()

    named = prune(run_cmd, root, project, "--run", "red", "--run", "group/cited", "--run", "busy", "--orphans", "--apply")
    assert named.returncode == 2 and "--run group/cited names no receipt" in named.stderr, named.stdout + named.stderr
    assert red.is_dir() and orphan.is_dir(), "a refused invocation removes nothing"
    named = prune(run_cmd, root, project, "--run", "red", "--run", "cited.json", "--run", "busy", "--orphans", "--apply")
    assert named.returncode == 0, named.stdout + named.stderr
    for path in (red, cited, busy, orphan):
        assert not path.exists(), f"{path} was named or orphaned and should be gone\n{named.stdout}"
    for path in (evidence, overrun, moved, target):
        assert path.is_dir(), f"{path} was not named and stays"
    assert sorted((root / "pruned").glob("*.json")) and (root / "red.pruned.json").is_file()
    for path, content in records.items():
        assert path.read_bytes() == content, f"the record {path} changed"
    assert (root / "red-dist/stewart-0.1.0-py3-none-any.whl").is_file(), "the tested wheel is part of the record"


def test_prune_records_a_removal_failure_and_exits_nonzero(tmp_path, run_cmd):
    """A removal the filesystem refuses is recorded against the run, printed, and fails the invocation."""
    root = tmp_path / "scratch"
    project = git_project(run_cmd, tmp_path / "project", citing=[])
    _, stuck = receipt(root, "stuck")
    (stuck / "test_probe0/prune-probe-unremovable").write_text("refused only where a test injects the fault\n")
    _, clean = receipt(root, "clean")
    result = prune(run_cmd, root, project, "--apply", launcher=("-c", REFUSING_UNLINK))
    assert result.returncode == 1, result.stdout + result.stderr
    assert not clean.exists(), "the other planned run still goes"
    assert (stuck / "test_probe0/prune-probe-unremovable").is_file(), "what could not be removed remains"
    assert f"could not remove {stuck}" in result.stderr and "prune-probe-unremovable" in result.stderr, result.stderr
    (record,) = (root / "pruned").glob("*.json")
    recorded = json.loads(record.read_text())
    assert recorded["results"][str(clean)] == "removed" and recorded["results"][str(stuck)].startswith("failed:"), recorded
    marker = json.loads((root / "stuck.pruned.json").read_text())
    assert marker["result"].startswith("failed:") and "prune-probe-unremovable" in marker["result"], marker
