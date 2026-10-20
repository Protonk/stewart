"""Installed archive membership, bundled policy and isolated entrypoint contracts."""
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tarfile
import tomllib
import zipfile

import pytest
import stewart
from stewart._bootstrap import SOURCE_FILES, SOURCE_MODULES, SOURCE_RESOURCES, StewartError
from stewart.session import package_identity


def require_wheel_members(names):
    prefix = "stewart-0.1.0"
    expected = {"stewart/" + name for name in SOURCE_FILES}
    expected.update(f"{prefix}.data/scripts/{name}" for name in ("stewart", "_stewart-python"))
    expected.update(f"{prefix}.dist-info/{name}" for name in ("METADATA", "WHEEL", "licenses/LICENSE", "RECORD"))
    assert len(names) == len(set(names)), "archive members must be unique"
    assert set(names) == expected, f"wheel membership differs: {set(names) ^ expected}"


@pytest.mark.smoke
def test_wheel_members_version_and_guidance_are_complete():
    wheel = Path(os.environ["STEWART_TEST_WHEEL"])
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        require_wheel_members(names)
        selected = {name.removeprefix("stewart/") for name in names if name.startswith("stewart/")}
        assert selected == set(SOURCE_FILES)
        assert len(SOURCE_MODULES) == 35 and len(SOURCE_RESOURCES) == 9
        scripts = [name for name in names if ".data/scripts/" in name]
        assert {name.rsplit("/", 1)[-1] for name in scripts} == {"stewart", "_stewart-python"}
        for name in selected:
            assert archive.read("stewart/" + name) == (Path(stewart.__file__).parent / name).read_bytes()
        metadata = archive.read(next(name for name in names if name.endswith(".dist-info/METADATA"))).decode()
    identity = package_identity(Path(stewart.__file__).parent)
    assert identity["version"] == importlib.metadata.version("stewart") == "0.1.0"
    assert "Requires-Python: >=3.14" in metadata and "Requires-Dist:" not in metadata
    assert identity["commit"] is None and identity["dirty"] is None


@pytest.mark.smoke
def test_archive_membership_compares_every_entry_and_ignores_order():
    with zipfile.ZipFile(os.environ["STEWART_TEST_WHEEL"]) as archive:
        names = archive.namelist()
    require_wheel_members(names)
    require_wheel_members(list(reversed(names)))
    for changed in (names + ["unrelated_project/__init__.py"], names[:-1], names + [names[0]]):
        with pytest.raises(AssertionError):
            require_wheel_members(changed)


@pytest.mark.parametrize("member", ["unexpected.py", "_json/__init__.py", "resources/extra.md"])
def test_source_selection_refuses_added_members(installation, member):
    package = installation / "stewart"
    before = package_identity(package)
    extra = package / member
    extra.parent.mkdir(exist_ok=True)
    extra.write_text("# planted member\n")
    with pytest.raises(StewartError) as error:
        package_identity(package)
    assert error.value.reason == "runtime_layout"
    extra.unlink()
    if member.startswith("_json/"):
        extra.parent.rmdir()
    assert package_identity(package) == before


@pytest.mark.smoke
def test_installed_entrypoints_ignore_caller_startup_and_ship_docs(tmp_path, run_cmd):
    marker = tmp_path / "caller-executed"
    hook = tmp_path / "sitecustomize.py"
    hook.write_text(f"from pathlib import Path; Path({str(marker)!r}).write_text('caller hook')\n")
    decoy = tmp_path / "stewart"
    decoy.mkdir()
    (decoy / "__init__.py").write_text(f"from pathlib import Path; Path({str(marker)!r}).write_text('project package')\n")
    (decoy / "__main__.py").write_text("raise SystemExit(31)\n")
    environment = dict(os.environ, PYTHONPATH=str(tmp_path), PYTHONHOME="/nonexistent/stewart-pythonhome",
                       PYTHONSTARTUP=str(hook))
    console = Path(sys.executable).parent / "stewart"
    for command in ([str(console)], [sys.executable, "-I", "-B", "-m", "stewart"]):
        result = run_cmd([*command, "--json", "docs", "auditor"], cwd=tmp_path, env=environment, check=True)
        resource = json.loads(result.stdout)["result"]
        assert resource["name"] == "auditor" and "assigned" in resource["text"]
        assert Path(resource["path"]).is_file()
        assert not marker.exists(), "caller code ran before isolation"
    environment.pop("PYTHONHOME")
    run_cmd([sys.executable, "-B", "-c", "pass"], cwd=tmp_path, env=environment, check=True)
    assert marker.read_text() == "caller hook", "the hostile startup control must fire"
    marker.unlink()
    result = run_cmd([sys.executable, "-B", "-m", "stewart"], cwd=tmp_path, env=environment)
    assert result.returncode == 31 and marker.read_text() == "project package"


def test_templates_route_roles_without_selecting_a_harness():
    from stewart.docs import document
    agents, claude = document("agents"), document("claude")
    assert agents["text"] == claude["text"]
    for role in ("AUDITOR", "MAINTAINER"):
        assert f"{role}.md" in agents["text"]
        text = document(role.lower())["text"]
        assert text and text not in agents["text"]
        assert "--model" not in text and "scope_adapter" not in text
    for resource in ("manual", "questions", "protocols"):
        assert document(resource)["sha256"]


def test_console_preserves_quoted_installation_paths(tmp_path, run_cmd):
    prefix = tmp_path / "Stewart's installed environment"
    run_cmd([sys.executable, "-I", "-B", "-m", "venv", prefix], check=True)
    python = prefix / "bin/python"
    run_cmd([python, "-I", "-B", "-m", "pip", "install", "--no-index", "--no-deps", "--no-compile",
             os.environ["STEWART_TEST_WHEEL"]], check=True)
    result = run_cmd([prefix / "bin/stewart", "--json", "docs", "questions"], cwd=tmp_path,
                     env=dict(os.environ, PYTHONHOME="/nonexistent/stewart-home"), check=True)
    value = json.loads(result.stdout)["result"]
    assert value["name"] == "questions" and "Choose a question" in value["text"]


def test_sdist_builds_same_wheel_without_git_or_network(tmp_path, run_cmd):
    project = Path(os.environ["STEWART_TEST_PROJECT"])
    environment = dict(os.environ, PIP_NO_INDEX="1")
    run_cmd([sys.executable, "-I", "-B", "-m", "build", "--no-isolation", "--sdist",
             "--outdir", tmp_path / "archives", project], env=environment, check=True)
    archives = list((tmp_path / "archives").glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0]) as archive:
        members = archive.getmembers()
        names = {name.split("/", 1)[1] for name in archive.getnames() if "/" in name}
        assert len(members) == len(archive.getnames()) == len(set(archive.getnames()))
        assert all(member.isfile() or member.isdir() for member in members)
        assert {name.removeprefix("src/stewart/") for name in names if name.startswith("src/stewart/")}
        assert {name for name in names if name.startswith("src/stewart/")} == {"src/stewart/" + name for name in SOURCE_FILES}
        assert {"LICENSE", "README.md", "AGENTS.md", "pyproject.toml", "requirements.lock", "scripts/check.py", "tests/conftest.py", "tests/acceptance.py"} <= names
        assert all(not {".scratch", ".git", "__pycache__"}.intersection(Path(name).parts)
                   and not name.endswith("-PLAN.md") for name in names)
        assert archive.extractfile("stewart-0.1.0/.gitignore").read() == (project / ".gitignore").read_bytes()
        archive.extractall(tmp_path / "unpacked", filter="data")
    unpacked = next((tmp_path / "unpacked").iterdir())
    assert not (unpacked / ".git").exists()
    run_cmd([sys.executable, "-I", "-B", "-m", "build", "--no-isolation", "--wheel",
             "--outdir", tmp_path / "rebuilt", unpacked], cwd=unpacked, env=environment, check=True)
    rebuilt = next((tmp_path / "rebuilt").glob("*.whl"))
    with zipfile.ZipFile(rebuilt) as actual, zipfile.ZipFile(os.environ["STEWART_TEST_WHEEL"]) as expected:
        assert set(actual.namelist()) == set(expected.namelist())
        assert {name: actual.read(name) for name in actual.namelist()} == {name: expected.read(name) for name in expected.namelist()}


def test_sdist_walk_never_enters_scratch_and_keeps_the_planted_members(tmp_path, monkeypatch):
    """The project's sdist configuration prunes .scratch before hatchling descends into it.

    Retained check runs live under the running checkout's .scratch, so an unpruned walk costs
    time in proportion to them while contributing no member. This drives hatchling's own walk,
    which the check environment provides for the wheel build: ``recurse_included_files`` reaches
    ``recurse_project_files``, which calls ``safe_walk`` as a global of its interface module.
    The walk is asserted before the configuration keys because the old configuration, or either
    key alone, still yields the right members and differs only in entering ``.scratch``; the
    keys then pin how the pruning is achieved.
    """
    from hatchling.builders.plugin import interface
    from hatchling.builders.sdist import SdistBuilder

    moved = (f"the wrapper was derived from hatchling 1.27.0's interface.safe_walk and hatchling "
             f"{importlib.metadata.version('hatchling')} is running; if that version walks differently, "
             "re-derive the wrapper for it, or assert only the configuration keys and keep the walk's "
             "behavior in recorded evidence")
    assert hasattr(interface, "safe_walk"), moved

    project = Path(os.environ["STEWART_TEST_PROJECT"])
    config = tomllib.loads((project / "pyproject.toml").read_text())
    build = config["tool"]["hatch"]["build"]
    sdist = build["targets"]["sdist"]
    root = tmp_path / "project"
    # One member per include entry, plus the version file; real files are copied so the
    # configuration and metadata hatchling reads are the project's own.
    members = [config["tool"]["hatch"]["version"]["path"]]
    members.extend(name if (project / name).is_file() else f"{name}/planted.py"
                   for name in (pattern.removeprefix("/") for pattern in sdist["include"]))
    for name in members:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes((project / name).read_bytes() if (project / name).is_file() else b"")
    for run in range(3):
        (root / f".scratch/run{run}/deep").mkdir(parents=True)
        (root / f".scratch/run{run}/deep/f.py").write_text("")
    (root / ".scratch/stray.py").write_text("")
    entered, real_walk = [], interface.safe_walk

    def recording(path):
        for directory, dirnames, filenames in real_walk(path):
            entered.append(Path(os.path.relpath(directory, root)))
            yield directory, dirnames, filenames

    monkeypatch.setattr(interface, "safe_walk", recording)
    listed = sorted(item.relative_path for item in SdistBuilder(str(root)).recurse_included_files())
    scratch = sorted(str(directory) for directory in entered if directory.parts[:1] == (".scratch",))
    assert scratch == [], (
        f"hatchling's sdist walk entered {scratch}; pyproject.toml must exclude /.scratch globally "
        "and set skip-excluded-dirs = true for the sdist target")
    assert listed == sorted(members), f"sdist members differ from the planted sources: {sorted(set(listed) ^ set(members))}"
    walked = {Path(".")} | {parent for name in members for parent in Path(name).parents}
    assert set(entered) == walked, (
        f"the safe_walk recorder saw {sorted(map(str, set(entered)))}, expected {sorted(map(str, walked))}; {moved}")
    assert "/.scratch" in build.get("exclude", []), "[tool.hatch.build] exclude must name /.scratch"
    assert sdist.get("skip-excluded-dirs") is True, "the sdist target must prune excluded directories before descending"
    assert "exclude" not in sdist, "a target-level exclude replaces the global list in hatchling 1.27.0"
