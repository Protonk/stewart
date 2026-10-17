"""Supplied helpers select retained code; project history supplies only audit inputs."""
from __future__ import annotations

import json
from pathlib import Path
import py_compile
import shutil
import sys
from types import SimpleNamespace

import pytest

from stewart import _invocation, _util, runtime
from stewart._bootstrap import StewartError, read_regular, runtime_manifest
from stewart._git import git, git_text
from stewart._json import loads_control
from stewart.assignment import initialize
from stewart.captured import pristine_runtime
from stewart.workspace import workspace
from support import clean_environment


@pytest.fixture
def retained(installation, tmp_path, monkeypatch):
    helper = installation / "stewart/verify_inputs.py"
    text = helper.read_text()
    marker = '    code = 1 if result["failed"] else 0'
    assert text.count(marker) == 1
    helper.write_text(text.replace(marker, '''    result["runtime_probe"] = {
        "module": __file__, "prefix": sys.prefix, "isolated": sys.flags.isolated,
        "cache": sys.pycache_prefix, "cache_members": list(Path(sys.pycache_prefix).iterdir()),
        "manager_cli_loaded": "stewart.cli" in sys.modules}
''' + marker))
    invocation = SimpleNamespace(code_root=installation, manifest=runtime_manifest(installation))
    monkeypatch.setattr(_invocation, "current", lambda: invocation)
    selected = runtime.select_runtime(tmp_path / "exposed" / "runtime")
    session = tmp_path / "private-session"
    session.mkdir()
    runtime.retain_runtime(session, selected)
    return session, selected


@pytest.fixture
def auditor(project_repo, tmp_path):
    ws = workspace(project_repo, "reviews/example")
    target = git_text(project_repo, "rev-parse", "HEAD")
    meta = initialize(ws, "one-question", target, inputs=["input.txt"])["assignment"]
    text = "# Assignment\n\n```audit-assignment\n" + json.dumps(meta) + "\n```\n\n"
    for title in ("Question", "Decision", "Scope and exclusions", "Evidence", "Stop condition"):
        text += f"## {title}\nRead the committed input and report the comparison.\n\n"
    (project_repo / ws.prompt).write_text(text)
    git(project_repo, "add", ws.prompt)
    git(project_repo, "commit", "-qm", "prompt only")
    prompt = git_text(project_repo, "rev-parse", "HEAD")
    worktree = tmp_path / "auditor"
    git(project_repo, "worktree", "add", "--detach", str(worktree), prompt)
    (worktree / meta["report_path"]).parent.mkdir(parents=True, exist_ok=True)
    assert not (project_repo / "tools").exists() and not (worktree / "tools").exists()
    assert not git_text(project_repo, "log", "--all", "--format=%H", "--", "tools", "stewart"), (
        "the entire audited history must lack Stewart sources")
    arguments = ["--workspace", ws.rel, "--expected-worktree", str(worktree), "--launch-prompt-commit", prompt,
                 "--prompt-sha256", _util.sha256_bytes(text.encode()), "--launch-token", "0123456789abcdef"]
    return worktree, arguments, meta


def test_helpers_work_without_project_modules_and_ignore_decoys(retained, auditor, run_cmd):
    session, selected = retained
    root = Path(selected["identity"]["root"])
    worktree, arguments, meta = auditor
    command = runtime.helper_argv(selected["identity"], sys.executable, "inputs", *arguments, "--json")
    first = loads_control(run_cmd(command, cwd=worktree).stdout)
    assert first["result"]["selected"] == first["result"]["matched"] == 1
    # These are valid, distinguishable project packages. Ordinary module startup
    # executes one; the issued helper must continue using the supplied bytes.
    decoy = worktree / "stewart"
    decoy.mkdir(parents=True)
    for path in (decoy.parent / "__init__.py", decoy / "__init__.py"):
        path.write_text("")
    (decoy / "verify_inputs.py").write_text("print('PROJECT DECOY')\n")
    (worktree / "stewart.py").write_text("raise RuntimeError('project stewart')\n")
    ordinary = clean_environment()
    ordinary["PYTHONPATH"] = str(worktree)
    assert "PROJECT DECOY" in run_cmd([sys.executable, "-B", "-m", "stewart.verify_inputs"],
                                      cwd=worktree, env=ordinary).stdout
    hostile = {**ordinary, "PYTHONHOME": "/no-such-python-home", "PYTHONSTARTUP": str(worktree / "stewart.py")}
    result = loads_control(run_cmd(command, cwd=worktree, env=hostile).stdout)["result"]
    assert result["matched"] == 1 and result["failed"] == 0
    probe = result["runtime_probe"]
    assert probe["module"] == str(root / "stewart/verify_inputs.py")
    assert probe["prefix"] == sys.prefix and probe["isolated"] == 1 and probe["cache_members"] == []
    assert not probe["manager_cli_loaded"] and not Path(probe["cache"]).exists()
    for operation in (("start",), ("set", "--completion", "complete", "--report-kind", "answer"), ("check",)):
        issued = runtime.helper_argv(selected["identity"], sys.executable, "declaration", *operation, *arguments)
        run_cmd(issued, cwd=worktree, env=hostile)
    assert '"completion": "complete"' in (worktree / meta["report_path"]).read_text()
    assert not (session / "session.json").exists(), "helpers must not need private session receipts"


@pytest.mark.parametrize("damage", ["source", "package", "pyc", "missing", "link"])
def test_helper_startup_refuses_changed_runtime_before_import(retained, auditor, run_cmd, tmp_path, damage):
    _, selected = retained
    root = Path(selected["identity"]["root"])
    worktree, arguments, _ = auditor
    helper = root / "stewart/verify_inputs.py"
    if damage == "source":
        helper.write_text("raise RuntimeError('changed helper executed')\n")
    elif damage == "package":
        shadow = root / "stewart/verify_inputs"
        shadow.mkdir()
        (shadow / "__init__.py").write_text("raise RuntimeError('shadow helper executed')\n")
    elif damage == "pyc":
        # Timestamp-valid cache with different executable bytes, then restore
        # source mtime/size: -B alone would read it. Membership must refuse it.
        import os
        before = helper.stat()
        source = helper.read_bytes()
        planted = b"raise RuntimeError('planted helper executed')\n"
        helper.write_bytes(planted + b" " * (len(source) - len(planted)))
        os.utime(helper, ns=(before.st_atime_ns, before.st_mtime_ns))
        py_compile.compile(str(helper), cfile=str(helper.parent / "__pycache__" / f"verify_inputs.{sys.implementation.cache_tag}.pyc"),
                           doraise=True)
        helper.write_bytes(source)
        os.utime(helper, ns=(before.st_atime_ns, before.st_mtime_ns))
        control = run_cmd([sys.executable, "-B", "-m", "stewart.verify_inputs"], cwd=worktree,
                          env={"PATH": os.defpath, "PYTHONPATH": str(root)}, check=False)
        assert control.returncode != 0 and "planted helper executed" in control.stderr, (
            "the timestamp-valid cache must execute under ordinary -B startup before isolation can claim to reject it")
    else:
        helper.unlink()
        if damage == "link":
            target = tmp_path / "linked.py"
            target.write_text("raise RuntimeError('linked helper executed')\n")
            helper.symlink_to(target)
    command = runtime.helper_argv(selected["identity"], sys.executable, "inputs", *arguments, "--json")
    result = run_cmd(command, cwd=worktree, check=False)
    assert result.returncode == 2 and not result.stderr
    assert loads_control(result.stdout)["error"]["reason"] in {"runtime_inventory", "runtime_mismatch"}


def test_pristine_assets_survive_exposed_removal_and_materialize_only_fresh_paths(retained, tmp_path):
    session, selected = retained
    record = {"runtime": selected["identity"], "runtime_assets": selected["assets"]}
    root = Path(record["runtime"]["root"])
    original = pristine_runtime(session, record)
    with pytest.raises(StewartError) as caught:
        runtime.materialize(record["runtime"], original)
    assert caught.value.reason == "destination_exists"
    shutil.rmtree(root)
    assert pristine_runtime(session, record) == original
    fresh = runtime.binding(tmp_path / "recovered", record["runtime"]["manifest"])
    runtime.materialize(fresh, original)
    assert runtime_manifest(Path(fresh["root"])) == fresh["manifest"]
    (session / "runtime-pristine/files.tar").write_bytes(b"damaged archive")
    with pytest.raises(StewartError) as caught:
        pristine_runtime(session, record)
    assert caught.value.reason == "evidence_tampered"


def test_materialization_refuses_parent_links_without_writing_target(retained, tmp_path):
    _, selected = retained
    outside = tmp_path / "outside"
    outside.mkdir()
    alias = tmp_path / "linked"
    alias.symlink_to(outside, target_is_directory=True)
    identity = runtime.binding(alias / "nested/runtime", selected["identity"]["manifest"])
    with pytest.raises(OSError):
        runtime.materialize(identity, selected["payloads"])
    assert not list(outside.iterdir()), "even a newly created ancestor must not follow a planted link"


def test_search_only_ancestors_do_not_require_listing_private_directories(tmp_path):
    import os
    parent = tmp_path / "private-parent"
    allowed = parent / "allowed"
    allowed.mkdir(parents=True)
    (parent / "private.txt").write_text("private parent contents")
    (allowed / "public.txt").write_text("allowed subtree bytes")
    parent.chmod(0o100)
    try:
        with pytest.raises(PermissionError):
            os.listdir(parent)
        info, data = read_regular(allowed / "public.txt")
        assert info["kind"] == "file" and data == b"allowed subtree bytes"
        assert runtime_manifest(allowed)["entries"][0]["path"] == "public.txt"
        # Search traversal must keep no-follow semantics at those ancestors.
        alias = tmp_path / "alias"
        alias.symlink_to(parent, target_is_directory=True)
        _, data = read_regular(alias / "allowed/public.txt")
        assert data is None
    finally:
        parent.chmod(0o700)


def test_helper_policy_has_no_arbitrary_module_or_manager_entry(retained, auditor, run_cmd):
    _, selected = retained
    worktree, arguments, _ = auditor
    with pytest.raises(StewartError) as caught:
        runtime.helper_argv(selected["identity"], sys.executable, "cli", *arguments)
    assert caught.value.reason == "runtime_helper"
    argv = runtime.helper_argv(selected["identity"], sys.executable, "inputs", *arguments, "--json")
    argv[argv.index("--helper") + 1] = "cli"
    result = run_cmd(argv, cwd=worktree, check=False)
    assert result.returncode == 2 and loads_control(result.stdout)["error"]["reason"] == "usage"
