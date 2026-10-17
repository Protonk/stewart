"""Execute issued commands against independent installations and destinations."""
from __future__ import annotations

import os
from pathlib import Path
import py_compile
import shutil
import sys

import pytest

from stewart._json import loads_control
from stewart._bootstrap import runtime_digest, runtime_manifest
from support import clean_environment, stage_runtime


def mark_installation(root, label):
    """A real CLI with an observable fixture label and executing module identity."""
    cli = root / "stewart/cli.py"
    source = cli.read_text()
    marker = '"exit_code": EXIT_REFUSED, "result": None, "error": None}'
    assert source.count(marker) == 1
    cli.write_text(source.replace(marker, marker + "\n    envelope['fixture'] = " +
                                  repr(label) + "\n    envelope['executed'] = __file__\n"
                                  "    from stewart.session import tool_identity\n    envelope['writer'] = tool_identity()\n"
                                  "    envelope['prefix'] = sys.prefix\n"
                                  "    envelope['cache'] = sys.pycache_prefix\n"
                                  "    envelope['cache_entries'] = list(Path(sys.pycache_prefix).iterdir()) if sys.pycache_prefix else None\n"))


def issue(installation, repo, cache, run_cmd, *, interpreter=None, arguments=None):
    script = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from stewart._invocation import retain_source
invocation = retain_source(cache=Path(sys.argv[3]))
print(json.dumps(invocation.command('--repo', sys.argv[2], '--workspace', 'reviews/example', *sys.argv[4:])))
'''
    arguments = arguments or ["--json", "init", "--audit-id", "one-question", "--input", "input.txt"]
    result = run_cmd([interpreter or sys.executable, "-I", "-B", "-c", script,
                      installation, repo, cache, *arguments], check=True)
    return loads_control(result.stdout)


def execute(action, cwd, run_cmd, **env):
    environment = clean_environment()
    environment.update(env)
    return run_cmd(action["argv"], cwd=cwd, env=environment, check=False)


@pytest.mark.parametrize("decoy", [False, True])
def test_manager_code_and_repository_are_independent(installation, project_repo, tmp_path, run_cmd, decoy):
    mark_installation(installation, "A")
    if decoy:
        stage_runtime(project_repo)
        mark_installation(project_repo, "B")
    paste = tmp_path / "paste"
    stage_runtime(paste)
    mark_installation(paste, "PASTE")
    action = issue(installation, project_repo, tmp_path / "managers", run_cmd)
    assert action["argv"][:3] == [sys.executable, "-I", "-B"]
    assert action["env"] == {}
    runtime = Path(action["runtime"]["code_root"])
    for cwd in (project_repo, paste):
        result = execute(action, cwd, run_cmd, PYTHONPATH=str(paste), PYTHONHOME="/does/not/exist")
        assert result.returncode == 0, result.stderr + result.stdout
        payload = loads_control(result.stdout)
        assert payload["fixture"] == "A"
        assert payload["executed"] == str(runtime / "stewart/cli.py")
        assert payload["result"]["assignment"]["input_files"] == ["input.txt"]
        head = run_cmd(["git", "rev-parse", "HEAD"], cwd=project_repo).stdout.strip()
        assert payload["result"]["assignment"]["target_commit"] == head
        assert payload["cache_entries"] == []
        assert not Path(payload["cache"]).exists(), "private process cache must be removed after exit"
    # The same project with a different selected implementation runs different code.
    alternative = issue(paste, project_repo, tmp_path / "other-managers", run_cmd)
    assert loads_control(execute(alternative, project_repo, run_cmd).stdout)["fixture"] == "PASTE"
    # A plain -m invocation really is shadowed; the isolation instrument can fire.
    hazard = run_cmd([sys.executable, "-B", "-m", "stewart", "--repo", str(project_repo),
                      "--workspace", "reviews/example", "--json", "init", "--audit-id", "hazard", "--input", "input.txt"],
                     cwd=paste, env={**clean_environment(), "PYTHONPATH": str(installation)}, check=False)
    assert hazard.returncode == 0, hazard.stderr
    assert loads_control(hazard.stdout)["fixture"] == "PASTE"
    assert loads_control(hazard.stdout)["writer"]["invocation"]["source_package"] == str(paste / "stewart")


@pytest.mark.parametrize("damage", ["changed", "missing", "package", "pyc", "link", "hidden", "root"])
def test_issued_command_refuses_runtime_drift_before_import(installation, project_repo, tmp_path, run_cmd, damage):
    mark_installation(installation, "A")
    action = issue(installation, project_repo, tmp_path / "managers", run_cmd)
    assert execute(action, tmp_path, run_cmd).returncode == 0, "undamaged control must execute"
    root = Path(action["runtime"]["code_root"])
    package = root / "stewart"
    cli = package / "cli.py"
    fired = tmp_path / "executed-unverified"
    if damage == "changed":
        cli.write_text(cli.read_text() + f"\nPath({str(fired)!r}).touch()\n")
    elif damage == "missing":
        cli.unlink()
    elif damage == "package":
        (package / "cli").mkdir()
        (package / "cli/__init__.py").write_text(f"from pathlib import Path\nPath({str(fired)!r}).touch()\n")
    elif damage == "pyc":
        cache = package / "__pycache__"
        cache.mkdir()
        py_compile.compile(str(cli), cfile=str(cache / f"cli.{sys.implementation.cache_tag}.pyc"), doraise=True)
    elif damage == "link":
        saved = tmp_path / "saved.py"
        cli.rename(saved)
        cli.symlink_to(saved)
    elif damage == "hidden":
        (package / ".added").write_text("unexpected resource")
    else:
        root.rename(root.with_name("missing-runtime"))
    result = execute(action, project_repo, run_cmd)
    assert result.returncode == 2
    value = loads_control(result.stdout)
    assert value["error"]["reason"] in {"runtime_mismatch", "runtime_inventory"}
    assert not fired.exists(), "verification must precede importing any selected member"
    assert "fixture" not in value, "a package-side check would already have imported the selected CLI"


def test_retained_source_deployment_and_private_cache(installation, project_repo, tmp_path, run_cmd):
    mark_installation(installation, "A")
    cache = tmp_path / "managers"
    original = issue(installation, project_repo, cache, run_cmd)
    assert issue(installation, project_repo, cache, run_cmd) == original
    cli = installation / "stewart/cli.py"
    cli.write_text(cli.read_text().replace("envelope['fixture'] = 'A'", "envelope['fixture'] = 'EDITED'"))
    edited = issue(installation, project_repo, cache, run_cmd)
    assert original["runtime"]["runtime_sha256"] != edited["runtime"]["runtime_sha256"]
    assert loads_control(execute(original, tmp_path, run_cmd).stdout)["fixture"] == "A"
    assert loads_control(execute(edited, tmp_path, run_cmd).stdout)["fixture"] == "EDITED"
    assert loads_control(execute(original, tmp_path, run_cmd).stdout)["cache"] != loads_control(
        execute(original, tmp_path, run_cmd).stdout)["cache"], "each process needs a fresh empty cache"


def test_startup_flags_cannot_be_removed(installation, project_repo, tmp_path, run_cmd):
    action = issue(installation, project_repo, tmp_path / "managers", run_cmd)
    fired = tmp_path / "stdlib-shadow-ran"
    (Path(action["runtime"]["launcher"]).parent / "json.py").write_text(
        f"open({str(fired)!r}, 'w').write('shadowed')\n")
    for flag in ("-I", "-B"):
        changed = {**action, "argv": [arg for arg in action["argv"] if arg != flag]}
        result = execute(changed, tmp_path, run_cmd)
        assert result.returncode == 2 and loads_control(result.stdout)["error"]["reason"] == "startup_isolation"
        assert not fired.exists(), "refusal must precede imports that could consult the script directory"


def test_manager_cache_and_source_links_are_refused(installation, project_repo, tmp_path, run_cmd):
    cache = tmp_path / "shared-managers"
    cache.mkdir(mode=0o755)
    with pytest.raises(AssertionError, match="runtime_cache|private to the current user"):
        issue(installation, project_repo, cache, run_cmd)
    cache.chmod(0o700)
    action = issue(installation, project_repo, cache, run_cmd)
    assert execute(action, tmp_path, run_cmd).returncode == 0
    cli = installation / "stewart/cli.py"
    original = tmp_path / "linked-cli.py"
    cli.rename(original)
    cli.symlink_to(original)
    with pytest.raises(AssertionError, match="distribution members must be readable regular"):
        issue(installation, project_repo, cache, run_cmd)


def test_matching_inventory_does_not_authorize_an_unsupported_layout(installation, project_repo, tmp_path, run_cmd):
    action = issue(installation, project_repo, tmp_path / "managers", run_cmd)
    unsupported = tmp_path / "ordinary-tree"
    unsupported.mkdir()
    (unsupported / "ordinary.py").write_text("raise AssertionError('not a manager')\n")
    action["argv"][action["argv"].index("--code-root") + 1] = str(unsupported)
    action["argv"][action["argv"].index("--runtime-sha256") + 1] = runtime_digest(runtime_manifest(unsupported))
    result = execute(action, tmp_path, run_cmd)
    assert result.returncode == 2
    assert loads_control(result.stdout)["error"]["reason"] == "runtime_layout"


def test_venv_interpreter_spelling_survives(installation, project_repo, tmp_path, run_cmd):
    venv = tmp_path / "venv"
    run_cmd([sys.executable, "-I", "-B", "-m", "venv", "--without-pip", venv])
    interpreter = venv / "bin/python"
    mark_installation(installation, "VENV")
    action = issue(installation, project_repo, tmp_path / "managers", run_cmd, interpreter=interpreter)
    assert action["argv"][0] == str(interpreter)
    result = execute(action, tmp_path, run_cmd)
    assert result.returncode == 0, result.stderr + result.stdout
    assert loads_control(result.stdout)["prefix"] == str(venv)


def test_repo_is_required_but_help_needs_no_git(installation, tmp_path, run_cmd):
    action = issue(installation, tmp_path / "absent", tmp_path / "managers", run_cmd, arguments=["--help"])
    assert execute(action, tmp_path, run_cmd, PATH="/absent").returncode == 0
    boundary = action["argv"].index("--")
    action["argv"] = action["argv"][:boundary + 1] + ["--workspace", "reviews/example", "status", "--audit-id", "x"]
    result = execute(action, tmp_path, run_cmd, PATH="/absent")
    assert result.returncode == 2 and "--repo" in result.stderr
    action["argv"].insert(boundary + 1, "--json")
    result = execute(action, tmp_path, run_cmd, PATH="/absent")
    assert result.returncode == 2 and loads_control(result.stdout)["error"]["reason"] == "usage"
    assert "--repo" in loads_control(result.stdout)["error"]["message"]


def test_source_entry_uses_the_same_verified_manager_startup(installation, project_repo, tmp_path, run_cmd):
    mark_installation(installation, "SOURCE")
    result = run_cmd([sys.executable, "-I", "-B", installation / "stewart/_bootstrap.py",
                      "source", "--manager-home", tmp_path / "managers", "--",
                      "--repo", project_repo, "--workspace", "reviews/example", "--json",
                      "init", "--audit-id", "source-entry", "--input", "input.txt"], cwd=project_repo,
                     env={**clean_environment(), "PYTHONPATH": str(project_repo), "PYTHONHOME": "/absent"})
    value = loads_control(result.stdout)
    assert value["fixture"] == "SOURCE"
    assert str(tmp_path / "managers") in value["executed"]
    assert value["cache_entries"] == []


def test_deployment_never_borrows_its_storage_repository_provenance(installation, project_repo, tmp_path, run_cmd):
    mark_installation(installation, "A")
    # Both ignored and untracked storage lie inside a different committed repo.
    (project_repo / ".git/info/exclude").write_text("ignored-manager/\n")
    for name in ("ignored-manager", "untracked-manager"):
        action = issue(installation, project_repo, project_repo / name, run_cmd)
        value = loads_control(execute(action, tmp_path, run_cmd).stdout)
        assert value["writer"]["commit"] is None and value["writer"]["dirty"] is None
        assert value["writer"]["invocation"]["source_package"] == str(installation / "stewart")
        assert value["writer"]["invocation"]["loaded_package"] != value["writer"]["invocation"]["source_package"]
    # An unrelated Git commit cannot alter the selected code or its provenance.
    (project_repo / "other.txt").write_text("unrelated\n")
    run_cmd(["git", "add", "other.txt"], cwd=project_repo)
    run_cmd(["git", "commit", "-qm", "unrelated"], cwd=project_repo)
    later = loads_control(execute(action, tmp_path, run_cmd).stdout)
    assert later["writer"] == value["writer"]


def test_flag_refusal_precedes_future_import(installation, project_repo, tmp_path, run_cmd):
    action = issue(installation, project_repo, tmp_path / "managers", run_cmd)
    sentinel = tmp_path / "future-imported"
    shadow = Path(action["runtime"]["launcher"]).parent / "__future__.py"
    shadow.write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n")
    changed = {**action, "argv": [a for a in action["argv"] if a != "-I"]}
    value = execute(changed, tmp_path, run_cmd, PYTHONPATH=str(shadow.parent))
    assert value.returncode == 2 and loads_control(value.stdout)["error"]["reason"] == "startup_isolation"
    assert not sentinel.exists()
    run_cmd([sys.executable, "-B", "-c", "import __future__"], cwd=tmp_path,
            env={**clean_environment(), "PYTHONPATH": str(shadow.parent)})
    assert sentinel.exists(), "the same planted import must fire when actually selected"


def test_launcher_survives_missing_deployment_and_accepts_readonly_runtime(installation, project_repo, tmp_path, run_cmd):
    action = issue(installation, project_repo, tmp_path / "managers", run_cmd)
    root = Path(action["runtime"]["code_root"])
    entries = [root.parent, root, *root.rglob("*")]
    modes = {p: p.stat().st_mode & 0o777 for p in entries}
    try:
        for p in entries:
            p.chmod(0o500 if p.is_dir() else 0o400)
        assert execute(action, tmp_path, run_cmd).returncode == 0
    finally:
        for p, mode in modes.items():
            p.chmod(mode)
    shutil.rmtree(root.parent)
    assert Path(action["runtime"]["launcher"]).is_file()
    refused = execute(action, tmp_path, run_cmd)
    assert refused.returncode == 2 and loads_control(refused.stdout)["error"]["reason"] == "runtime_inventory"
    # Recreate the exact source deployment at its pinned coordinate.
    assert issue(installation, project_repo, tmp_path / "managers", run_cmd) == action
    assert execute(action, tmp_path, run_cmd).returncode == 0


def test_source_selection_is_explicit_and_home_is_absolute_unlinked(installation, project_repo, tmp_path, run_cmd):
    cache = tmp_path / "managers"
    (installation / ".notes.txt").write_text("unrelated note outside the distribution")
    action = issue(installation, project_repo, cache, run_cmd)
    added = installation / "stewart/.hidden.py"
    added.write_text("HIDDEN = True\n")
    with pytest.raises(AssertionError, match="distribution membership"):
        issue(installation, project_repo, cache, run_cmd)
    added.unlink()
    assert issue(installation, project_repo, cache, run_cmd) == action
    with pytest.raises(AssertionError, match="absolute path"):
        issue(installation, project_repo, Path("relative-home"), run_cmd)
    link = tmp_path / "manager-link"
    link.symlink_to(cache, target_is_directory=True)
    with pytest.raises(AssertionError, match="cannot traverse a link"):
        issue(installation, project_repo, link, run_cmd)


def test_runtime_refusal_class_and_usage_are_structured(installation, project_repo, tmp_path, run_cmd):
    invocation = installation / "stewart/_invocation.py"
    source = invocation.read_text()
    source = source.replace('    global _running\n', '    raise StewartError("fixture refusal", reason="fixture_bind")\n    global _running\n')
    invocation.write_text(source)
    action = issue(installation, project_repo, tmp_path / "managers", run_cmd)
    result = execute(action, tmp_path, run_cmd)
    assert result.returncode == 2 and loads_control(result.stdout)["error"]["reason"] == "fixture_bind"
    assert "Traceback" not in result.stderr
    boundary = action["argv"].index("--")
    action["argv"] = action["argv"][:boundary] + ["--unknown-launcher-option", "--", "--json"]
    result = execute(action, tmp_path, run_cmd)
    assert result.returncode == 2 and loads_control(result.stdout)["error"]["reason"] == "usage"


def test_inprocess_commands_reuse_one_source_selection(installation, tmp_path, run_cmd):
    script = '''
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from stewart import _invocation
os.environ['STEWART_MANAGER_HOME'] = sys.argv[2]
first = _invocation.current()
source = Path(sys.argv[1]) / 'stewart/status.py'
source.write_text(source.read_text() + '\\n# changed after the first command selection\\n')
assert _invocation.current() is first
assert _invocation.current().command('--help') == first.command('--help')
os.environ['STEWART_MANAGER_HOME'] = sys.argv[3]
second = _invocation.current()
assert second.identity()['runtime_sha256'] != first.identity()['runtime_sha256']
print('one retained selection per manager home')
'''
    result = run_cmd([sys.executable, "-I", "-B", "-c", script, installation,
                      tmp_path / "first-managers", tmp_path / "second-managers"])
    assert result.stdout.strip() == "one retained selection per manager home"
