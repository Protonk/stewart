"""Byte contracts, complete runtime membership and independent test startup."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import py_compile
import shutil
import socket
import sys
import tempfile

import pytest

from stewart import _util
from stewart._json import loads_control
from stewart._bootstrap import MANIFEST_SCHEMA, observe_runtime, runtime_digest, runtime_manifest, verify_runtime
from stewart._bootstrap import StewartError
from support import clean_environment, package_import_violations


@pytest.mark.smoke
def test_serialization_vectors():
    value = {"z": "é\n", "a": {"β": [1, True, None]}}
    compact = '{"a":{"\\u03b2":[1,true,null]},"z":"\\u00e9\\n"}'
    pretty = b'{\n  "a": {\n    "\\u03b2": [\n      1,\n      true,\n      null\n    ]\n  },\n  "z": "\\u00e9\\n"\n}\n'
    assert _util.canonical_json(value) == compact
    assert _util.receipt_json_bytes(value) == pretty
    assert _util.sha256_canonical_json(value) == "bb41ae41bf746f6cd7aaffacdadc71056ce0da6e569d33ff1804c7454179fbb4"
    assert _util.sha256_bytes(pretty) == "f06cdcd79cbadb1dedc44d0cf3300d7173bfd1c8c111997db92b0cc33eb2f180"
    assert _util.sha256_text("é\n") == "edd3a863872a04239eb29ad4bc12fc892b3d4ae57cc7e786a3697816f8e141c2"
    assert _util.sha256_canonical_json(dict(reversed(list(value.items())))) == _util.sha256_canonical_json(value)
    assert _util.sha256_bytes(pretty[:-1]) != _util.sha256_bytes(pretty)
    assert _util.sha256_text("é") != _util.sha256_text("é\n")
    inventory = {"schema_version": MANIFEST_SCHEMA, "entries": [
        {"path": "é.py", "kind": "file", "size": 0, "sha256": _util.sha256_bytes(b"")}]}
    assert runtime_digest(inventory) == _util.sha256_canonical_json(inventory), (
        "the standalone bootstrap's domain digest must retain the canonical receipt preimage")


@pytest.mark.smoke
def test_explicit_path_display(tmp_path):
    assert _util.rel(tmp_path / "member", tmp_path) == "member"
    assert _util.rel("member", tmp_path) == "member"
    assert _util.rel(Path("/tmp/external"), tmp_path) == "/tmp/external"
    assert _util.require_rel("a/b") == "a/b"
    for value in ("../member", "/member", "a/../b"):
        with pytest.raises(ValueError):
            _util.require_rel(value)


@pytest.mark.smoke
def test_package_dependency_boundary(installation):
    sources = {p.name: p.read_text() for p in (installation / "stewart").glob("*.py")}
    assert len(sources) >= 23, "source population unexpectedly lost the custody implementation"
    assert package_import_violations(sources) == []
    assert package_import_violations({"added.py": "from tools import hash\n"})
    assert package_import_violations({"added.py": "from .. import hash\n"})
    assert package_import_violations({"added.py": "import importlib; importlib.import_module('pawl.structure')\n"})
    assert package_import_violations({"added.py": "from stewart import _util\n# from tools import hash\n"}) == []


# Generic SHA-256/canonical-JSON helper spellings, including the private and
# alias forms a re-implementer reaches for. Digests with a domain name, such as
# the bootstrap's `runtime_digest`, are not generic helpers.
GENERIC_DIGEST_HELPERS = frozenset({
    "sha256", "sha256_bytes", "_sha256_bytes", "sha256_text", "_sha256_text", "sha256_path", "_sha256_path",
    "sha256_file", "_sha256_file", "sha256_canonical_json", "_sha256_canonical_json", "canonical_sha256",
    "_canonical_sha256", "digest_json", "_digest_json"})
UTILITY_HOME = "_util.py"


def generic_digest_redefinitions(sources: dict[str, str]) -> list[str]:
    """``module:line: name`` for each generic digest helper defined outside the utility home."""
    found = []
    for name, source in sorted(sources.items()):
        if name == UTILITY_HOME:
            continue
        for node in ast.walk(ast.parse(source, filename=name)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in GENERIC_DIGEST_HELPERS:
                found.append(f"{name}:{node.lineno}: {node.name}")
    return found


@pytest.mark.smoke
def test_generic_digest_helpers_have_one_home(installation):
    """`stewart._util` owns generic digests; other modules call it or use a domain name."""
    package = installation / "stewart"
    sources = {p.relative_to(package).as_posix(): p.read_text() for p in package.rglob("*.py")}
    assert len(sources) >= 29 and UTILITY_HOME in sources, "runtime source population vanished"
    assert {"sha256_bytes", "sha256_text", "sha256_canonical_json"} <= {
        node.name for node in ast.walk(ast.parse(sources[UTILITY_HOME])) if isinstance(node, ast.FunctionDef)}
    assert generic_digest_redefinitions(sources) == []
    # A planted duplicate fires anywhere outside the home, including a nested module.
    planted = "import hashlib\n\ndef sha256_bytes(data):\n    return hashlib.sha256(data).hexdigest()\n"
    for location in ("status.py", "resources/helper.py"):
        assert generic_digest_redefinitions({**sources, location: planted}) == [f"{location}:3: sha256_bytes"]
    # Calls, imports and domain-named digests are not redefinitions.
    allowed = ("from stewart._util import sha256_bytes\n\ndef runtime_digest(value):\n"
               "    return sha256_bytes(value)\n")
    assert generic_digest_redefinitions({**sources, "status.py": allowed}) == []


def test_cold_imports_and_parser_need_no_project(installation, project_repo, tmp_path, run_cmd):
    assert not (project_repo / "tools").exists()
    assert not (project_repo / ".pawl-root").exists()
    script = '''
import importlib, pathlib, sys
sys.path.insert(0, sys.argv[1])
names = sorted(p.stem for p in (pathlib.Path(sys.argv[1]) / 'stewart').glob('*.py'))
def audit(event, args):
    if event in {'subprocess.Popen', 'os.system'}:
        raise AssertionError('import/parser spawned a process')
sys.addaudithook(audit)
for name in names:
    importlib.import_module('stewart.' + name)
from stewart.cli import build_parser
assert 'Custody' in build_parser().format_help()
assert not any(n in sys.modules for n in ('tools.hash', 'tools.path', 'tools.emit', 'integration.support'))
print(len(names))
'''
    result = run_cmd([sys.executable, "-I", "-B", "-c", script, installation], cwd=tmp_path)
    assert int(result.stdout) >= 23


@pytest.fixture
def runtime_tree(tmp_path):
    root = tmp_path / "runtime"
    (root / "package/resources").mkdir(parents=True)
    (root / "bootstrap.py").write_text("# trusted bootstrap\n")
    (root / "package/__init__.py").write_text("VALUE = 1\n")
    (root / "package/_json.py").write_text("VALUE = 1\n")
    (root / "package/resources/policy.md").write_text("auditor policy\n")
    return root


@pytest.mark.parametrize("change", ["source", "missing", "package", "cache", "extension", "hidden", "link", "fifo"])
def test_runtime_inventory_detects_whole_population(runtime_tree, change, tmp_path):
    expected = runtime_manifest(runtime_tree)
    assert len(expected["entries"]) == 6
    original_digest = runtime_digest(observe_runtime(runtime_tree)[0])
    if change == "source":
        (runtime_tree / "package/_json.py").write_text("VALUE = 2\n")
    elif change == "missing":
        (runtime_tree / "package/_json.py").unlink()
    elif change == "package":
        (runtime_tree / "package/_json").mkdir()
        (runtime_tree / "package/_json/__init__.py").write_text("VALUE = 2\n")
    elif change == "cache":
        py_compile.compile(str(runtime_tree / "package/_json.py"),
                           cfile=str(runtime_tree / "package/__pycache__" / f"_json.{sys.implementation.cache_tag}.pyc"),
                           doraise=True)
    elif change == "extension":
        (runtime_tree / "package/_json.so").write_bytes(b"extension")
    elif change == "hidden":
        (runtime_tree / ".hidden").write_text("added")
    elif change == "link":
        (runtime_tree / "package/_json.py").unlink()
        (tmp_path / "secret").write_text("do not read")
        (runtime_tree / "package/_json.py").symlink_to(tmp_path / "secret")
    elif change == "fifo":
        os.mkfifo(runtime_tree / "pipe")
    observed, payloads = observe_runtime(runtime_tree)
    assert runtime_digest(observed) != original_digest
    assert b"do not read" not in payloads.values()
    with pytest.raises(StewartError) as exc:
        verify_runtime(runtime_tree, expected)
    assert exc.value.reason == "runtime_mismatch"


def test_runtime_identity_ignores_outside_and_mtime_changes(runtime_tree, tmp_path):
    expected = runtime_manifest(runtime_tree)
    (tmp_path / "notes.md").write_text("unrelated project prose")
    os.utime(runtime_tree / "package/_json.py", (1, 1))
    assert verify_runtime(runtime_tree, expected) == expected
    assert [entry["path"] for entry in expected["entries"]] == sorted(entry["path"] for entry in expected["entries"])


def test_runtime_never_follows_ancestor_links(runtime_tree, tmp_path):
    alias = tmp_path / "alias"
    alias.symlink_to(runtime_tree, target_is_directory=True)
    observed, payloads = observe_runtime(alias / "package")
    assert not payloads
    assert observed["entries"][0]["kind"] == "unreadable"
    with pytest.raises(StewartError) as exc:
        runtime_manifest(alias)
    assert exc.value.reason == "runtime_inventory"


@pytest.mark.system
def test_socket_and_empty_runtime_refuse(tmp_path):
    root = tmp_path / "runtime"
    root.mkdir()
    with pytest.raises(StewartError):
        runtime_manifest(root)
    # macOS's Unix-domain socket name limit is smaller than pytest's temp paths.
    with tempfile.TemporaryDirectory(prefix="st-", dir="/tmp") as temporary:
        short = Path(temporary).resolve()
        with socket.socket(socket.AF_UNIX) as sock:
            sock.bind(str(short / "socket"))
            observed, payloads = observe_runtime(short)
            assert observed["entries"][0]["kind"] == "socket"
            assert not payloads


def test_valid_bytecode_executes_under_b_but_fresh_prefix_uses_source(tmp_path, run_cmd):
    source = tmp_path / "subject.py"
    source.write_text("VALUE = 'cache'\n")
    py_compile.compile(str(source),
                       cfile=str(tmp_path / "__pycache__" / f"subject.{sys.implementation.cache_tag}.pyc"),
                       invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP, doraise=True)
    original_stat = source.stat()
    source.write_text("VALUE = 'truth'\n")
    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert source.stat().st_size == original_stat.st_size
    probe = "import sys; sys.path.insert(0, sys.argv[1]); import subject; print(subject.VALUE)"
    cached = run_cmd([sys.executable, "-I", "-B", "-c", probe, tmp_path])
    assert cached.stdout.strip() == "cache", "the planted-bytecode control did not fire"
    prefix = tmp_path / "fresh-cache"
    prefix.mkdir(mode=0o700)
    clean = run_cmd([sys.executable, "-I", "-B", "-c",
                     "import sys; sys.pycache_prefix = sys.argv[2]; " + probe, tmp_path, prefix])
    assert clean.stdout.strip() == "truth"
    assert not list(prefix.iterdir())


def test_added_package_changes_import_and_manifest(tmp_path, run_cmd):
    root = tmp_path / "runtime"
    root.mkdir()
    (root / "subject.py").write_text("VALUE = 'module'\n")
    expected = runtime_manifest(root)
    probe = "import sys; sys.path.insert(0, sys.argv[1]); import subject; print(subject.VALUE)"
    assert run_cmd([sys.executable, "-I", "-B", "-c", probe, root]).stdout.strip() == "module"
    (root / "subject").mkdir()
    (root / "subject/__init__.py").write_text("VALUE = 'package'\n")
    assert run_cmd([sys.executable, "-I", "-B", "-c", probe, root]).stdout.strip() == "package"
    with pytest.raises(StewartError):
        verify_runtime(root, expected)


def test_test_runner_rejects_parent_configuration(tmp_path, run_cmd):
    project = Path(os.environ["STEWART_TEST_PROJECT"])
    parent = tmp_path / "parent"
    child = parent / "stewart"
    shutil.copytree(project, child, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".scratch", ".git", "dist", "build"))
    sentinel = parent / "parent-plugin-fired"
    (parent / "pytest.ini").write_text("[pytest]\naddopts = --strict-markers\n")
    (parent / "conftest.py").write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('fired')\n")
    # Without the boundary the same parent plugin is actually reached.
    (parent / "test_probe.py").write_text("def test_probe(): pass\n")
    result = run_cmd([sys.executable, "-I", "-B", "-m", "pytest", str(parent / "test_probe.py"), "-q"],
                     env=clean_environment(), cwd=parent)
    assert sentinel.read_text() == "fired"
    sentinel.unlink()
    poisoned = clean_environment()
    poisoned.update(PYTEST_ADDOPTS="--option-that-does-not-exist", PYTEST_PLUGINS="unwanted_parent_plugin")
    result = run_cmd([sys.executable, "-I", "-B", child / "scripts/check.py", "-q", "-k", "test_serialization_vectors"],
                     env=poisoned, cwd=parent)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert not sentinel.exists(), "isolated runner loaded the parent conftest"


@pytest.mark.parametrize("source", [
    "from importlib import import_module; import_module('..hash', 'stewart')",
    "from importlib import import_module; import_module(name='tools.hash')",
    "from importlib import import_module as load; load('tools.hash')",
    "import importlib as loader; load = loader.import_module; load('tools.hash')",
    "import importlib; importlib.import_module('.hash', package='tools')",
    "__import__('path', level=2)",
    "from builtins import __import__ as load; load('path', level=2)",
])
def test_dependency_guard_literal_aliases_and_relative_targets(source):
    assert package_import_violations({"member.py": source})
    assert package_import_violations({"member.py": "# " + source}) == []
    allowed = source.replace("'tools.hash'", "'stewart._util'")
    if allowed != source:
        assert package_import_violations({"member.py": allowed}) == []
    assert package_import_violations({"member.py":
        "from importlib import import_module as load; load('._util', __package__)"}) == []


@pytest.mark.parametrize("bad", ["missing", "link", "unreadable", "cache", "empty"])
def test_failure_observations_cannot_authorize_runtime(tmp_path, bad):
    root = tmp_path / "runtime"
    root.mkdir()
    member = root / "member.py"
    member.write_text("VALUE = 1\n")
    good = runtime_manifest(root)
    assert verify_runtime(root, good) == good
    if bad == "missing":
        member.unlink()
        root.rmdir()
    elif bad == "link":
        member.unlink()
        outside = tmp_path / "outside.py"
        outside.write_text("VALUE = 1\n")
        member.symlink_to(outside)
    elif bad == "unreadable":
        member.chmod(0)
    elif bad == "cache":
        (root / "__pycache__").mkdir()
    elif bad == "empty":
        member.unlink()
    try:
        observed, _ = observe_runtime(root)
        if bad == "unreadable":
            assert observed["entries"][0]["kind"] == "unreadable", (
                "unreadable-file control did not fire; run these checks as an unprivileged user")
        # Neither preserved observations nor a caller relabeling them as a
        # manifest can promote matching failures into verified executable code.
        for expected in (observed, {**observed, "schema_version": MANIFEST_SCHEMA}):
            with pytest.raises(StewartError) as exc:
                verify_runtime(root, loads_control(_util.receipt_json_bytes(expected)))
            assert exc.value.reason == "runtime_manifest"
        with pytest.raises(StewartError) as exc:
            verify_runtime(root, good)
        assert exc.value.reason == "runtime_mismatch"
    finally:
        if bad == "unreadable":
            member.chmod(0o600)


@pytest.mark.parametrize("bad", [None, [], {}, {"schema_version": MANIFEST_SCHEMA, "entries": []}])
def test_invalid_manifest_types_have_stable_refusal(tmp_path, bad):
    with pytest.raises(StewartError) as exc:
        verify_runtime(tmp_path, bad)
    assert exc.value.reason == "runtime_manifest"


def test_manifest_structure_and_nonexecuting_resources(runtime_tree):
    expected = runtime_manifest(runtime_tree)
    malformed = [
        {**expected, "entries": [*expected["entries"], expected["entries"][0]]},
        {**expected, "entries": list(reversed(expected["entries"]))},
        {**expected, "entries": [e for e in expected["entries"] if e["path"] != "package"]},
        {**expected, "entries": [{**e, "size": True} if e["kind"] == "file" else e for e in expected["entries"]]},
    ]
    for bad in malformed:
        with pytest.raises(StewartError) as exc:
            verify_runtime(runtime_tree, bad)
        assert exc.value.reason == "runtime_manifest"
    # Resource bytes are covered even if their suffix could be executable under
    # some other search-path policy. Verification does not grant such a policy.
    (runtime_tree / "package/resources/data.zip").write_bytes(b"resource")
    (runtime_tree / "package/resources/notes.pth").write_text("resource notes")
    resources = runtime_manifest(runtime_tree)
    assert verify_runtime(runtime_tree, resources) == resources
    (runtime_tree / "package/_json.py").chmod(0o755)
    assert verify_runtime(runtime_tree, resources) == resources, "permission modes are outside byte identity"
    (runtime_tree / "package/module.PYC").write_bytes(b"cache")
    with pytest.raises(StewartError) as exc:
        runtime_manifest(runtime_tree)
    assert exc.value.reason == "runtime_inventory"


def test_package_identity_rejects_module_links_but_preserves_regular_bytes(tmp_path, installation):
    from stewart.session import package_identity
    package = installation / "stewart"
    member = package / "_json.py"
    expected = package_identity(package)
    (installation / "notes.md").write_text("unrelated prose")
    assert package_identity(package) == expected
    outside = tmp_path / "original.py"
    member.rename(outside)
    member.symlink_to(outside)
    with pytest.raises(StewartError) as exc:
        package_identity(package)
    assert exc.value.reason == "runtime_unreadable"
    member.unlink()
    member.write_bytes(outside.read_bytes())
    assert package_identity(package) == expected, "a new inode with the same module bytes preserves identity"


@pytest.mark.parametrize("change,diagnostic", [
    ("config_flags", "explicit pytest configuration is required"),
    ("plugin", "unexpected pytest plugin"),
    ("installation", "wrong Stewart installation"),
    ("suite", "wrong staged test suite"),
])
def test_runner_measures_each_selected_boundary(tmp_path, installation, run_cmd, change, diagnostic):
    """Mutate the actual child invocation, leaving the other protections intact."""
    project = Path(os.environ["STEWART_TEST_PROJECT"])
    probe = r'''
import os, pathlib, runpy, subprocess, sys
project, other, change = sys.argv[1:]
original = subprocess.run
def changed(argv, **kwargs):
    if '-m' not in argv or 'pytest' not in argv:
        return original(argv, **kwargs)
    env = kwargs['env']
    suite = pathlib.Path(env['STEWART_TEST_SUITE'])
    argv = list(argv)
    if change == 'config_flags':
        index = argv.index('-c')
        del argv[index:index+2]
        argv.remove('--confcutdir=' + str(suite))
    elif change == 'plugin':
        injected = suite / 'tests/injected_plugin.py'
        injected.write_text('def pytest_configure(config): pass\n')
        conftest = suite / 'tests/conftest.py'
        conftest.write_text(conftest.read_text() + '\npytest_plugins = [\"injected_plugin\"]\n')
    elif change == 'installation':
        env['STEWART_TEST_RUNTIME'] = other
    elif change == 'suite':
        argv[argv.index(str(suite / 'pyproject.toml'))] = str(pathlib.Path(project) / 'pyproject.toml')
        argv[argv.index('--confcutdir=' + str(suite))] = '--confcutdir=' + project
        kwargs['cwd'] = project
    return original(argv, **kwargs)
subprocess.run = changed
sys.argv = [str(pathlib.Path(project) / 'scripts/check.py'), '--result', str(pathlib.Path.cwd() / 'boundary.json'), '-q', '-k', 'test_serialization_vectors']
runpy.run_path(sys.argv[0], run_name='__main__')
'''
    result = run_cmd([sys.executable, "-I", "-B", "-c", probe, project, installation, change],
                     env=clean_environment(), cwd=tmp_path, check=False)
    assert result.returncode != 0
    assert diagnostic in result.stdout + result.stderr


def test_runner_applies_config_contents_and_reports_selection(tmp_path, run_cmd):
    project = Path(os.environ["STEWART_TEST_PROJECT"])
    child = tmp_path / "project"
    shutil.copytree(project, child, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".scratch", ".git", "dist", "build"))
    result_path = tmp_path / "selection.json"
    command = [sys.executable, "-I", "-B", child / "scripts/check.py", "--result", result_path,
               "-q", "-k", "test_serialization_vectors"]
    run_cmd(command, env=clean_environment(), cwd=tmp_path)
    counts = loads_control(result_path.read_bytes())
    assert counts["selected"] == 1 and counts["outcomes"] == {"passed": 1}
    assert counts["collected"] == len(counts["collected_nodes"]) > 1
    assert counts["deselected"] == counts["collected"] - 1
    config = child / 'pyproject.toml'
    config.write_text(config.read_text().replace('testpaths = ["tests"]', 'testpaths = ["missing"]'))
    result = run_cmd(command, env=clean_environment(), cwd=tmp_path, check=False)
    assert result.returncode != 0
    assert "local pytest testpaths were not applied" in result.stdout + result.stderr
