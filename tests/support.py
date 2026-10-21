"""Standalone subprocess support, with no containing-project imports."""
from __future__ import annotations

import ast
import inspect
from importlib.util import resolve_name
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def plugin_origins(plugins, builtin_directory: Path, local_conftest: Path) -> dict[str, str]:
    """Allow only the selected pytest's own plugins and this suite's conftest."""
    origins = {}
    for name, plugin in plugins:
        if plugin is None:  # Explicitly blocked registrations are not executable.
            continue
        module = plugin if inspect.ismodule(plugin) else inspect.getmodule(plugin if inspect.isclass(plugin) else type(plugin))
        filename = getattr(module, "__file__", None)
        origin = Path(filename).resolve() if filename else None
        assert origin is not None and (origin == local_conftest.resolve()
            or origin.is_relative_to(builtin_directory.resolve())), f"unexpected pytest plugin: {name} ({origin})"
        origins[name] = str(origin)
    assert origins, "pytest plugin population vanished"
    return origins


def budget_overruns(durations, limit):
    """Charge fixture setup and teardown to their test, not just its call body."""
    return {node: sum(phases.values()) for node, phases in durations.items() if sum(phases.values()) > limit}


def package_import_violations(sources: dict[str, str], allowed: dict[str, set[str]] | None = None) -> list[str]:
    """Reject nonstdlib dependencies in statements and literal dynamic imports.

    ``allowed`` names, per module, the external top-level packages it may
    import; nothing else is admitted anywhere. Direct and simple assigned
    aliases are tracked, without general reassignment or scope dataflow.
    Computed targets and arbitrary reflection are outside this guard; cold
    imports separately exercise every module without project paths.
    """
    allowed = allowed or {}
    violations = []
    for name, source in sources.items():
        tree = ast.parse(source, filename=name)
        namespace = "stewart"
        package = ".".join((namespace, *Path(name).parts[:-1]))
        modules = {"importlib"}
        functions = {"__import__"}
        builtin_importers = {"__import__"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.asname or alias.name for alias in node.names if alias.name == "importlib")
            elif isinstance(node, ast.ImportFrom) and node.module in {"importlib", "builtins"}:
                functions.update(alias.asname or alias.name for alias in node.names
                                 if alias.name in {"import_module", "__import__"})
                if node.module == "builtins":
                    builtin_importers.update(alias.asname or alias.name for alias in node.names if alias.name == "__import__")

        def importer(node):
            return (isinstance(node, ast.Name) and node.id in functions
                    or isinstance(node, ast.Attribute) and node.attr == "import_module"
                    and isinstance(node.value, ast.Name) and node.value.id in modules)

        # Follow simple aliases such as load = importlib.import_module. Cyclic
        # aliases cannot add names, so the finite set reaches a fixed point.
        previous = None
        while previous != functions:
            previous = functions.copy()
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and importer(node.value):
                    functions.update(target.id for target in node.targets if isinstance(target, ast.Name))
                    if isinstance(node.value, ast.Name) and node.value.id in builtin_importers:
                        builtin_importers.update(target.id for target in node.targets if isinstance(target, ast.Name))

        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    try:
                        targets = [resolve_name("." * node.level + (node.module or ""), package)]
                    except ImportError:
                        violations.append(f"{name}:{node.lineno}: import escapes package")
                else:
                    targets = [node.module or ""]
            elif isinstance(node, ast.Call) and importer(node.func):
                keywords = {argument.arg: argument.value for argument in node.keywords}
                target = node.args[0] if node.args else keywords.get("name")
                if isinstance(target, ast.Constant) and isinstance(target.value, str):
                    value = target.value
                    if isinstance(node.func, ast.Name) and node.func.id in builtin_importers:
                        level = node.args[4] if len(node.args) > 4 else keywords.get("level")
                        if isinstance(level, ast.Constant) and type(level.value) is int and level.value > 0:
                            try:
                                targets = [resolve_name("." * level.value + value, package)]
                            except ImportError:
                                violations.append(f"{name}:{node.lineno}: import escapes package")
                            value = None
                    if value is not None and value.startswith("."):
                        context = node.args[1] if len(node.args) > 1 else keywords.get("package")
                        if isinstance(context, ast.Constant) and isinstance(context.value, str):
                            context = context.value
                        elif isinstance(context, ast.Name) and context.id == "__package__":
                            context = package
                        else:
                            violations.append(f"{name}:{node.lineno}: relative import has unknown package")
                            continue
                        try:
                            value = resolve_name(value, context)
                        except (ImportError, ValueError):
                            violations.append(f"{name}:{node.lineno}: import escapes package")
                            continue
                    if value is not None:
                        targets = [value]
            for target in targets:
                if target == namespace or target.startswith(namespace + "."):
                    continue
                top = target.split(".")[0]
                if top not in sys.stdlib_module_names and top not in allowed.get(name, ()):
                    violations.append(f"{name}:{node.lineno}: external import {target}")
    return violations


def stage_runtime(destination: Path) -> Path:
    """Copy the selected installed wheel package for deliberate mutation controls.

    The test subject is the installed wheel, never a source-path import shim.
    Copies let tests plant damaged or distinguishable installations safely.
    """
    import stewart
    from stewart._bootstrap import source_payloads
    _, payloads = source_payloads(Path(stewart.__file__).parent)
    package = destination / "stewart"
    for name, data in payloads.items():
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return destination


def reduced_project(source: Path, destination: Path, probes: dict[str, str]) -> Path:
    """Copy the project with only the harness modules and the given probe files under tests/.

    A full copy would run the whole suite whenever a harness regression shows
    the old behavior. Each check.py invocation over the copy still provisions an
    environment and builds a wheel, so callers group their invocations.
    """
    harness = {"conftest.py", "support.py"}

    def ignore(directory, names):
        skipped = {"__pycache__", ".pytest_cache", ".scratch", ".git", "dist", "build"}.intersection(names)
        return skipped | set(names) - harness if Path(directory) == source / "tests" else skipped

    shutil.copytree(source, destination, ignore=ignore)
    for name, text in probes.items():
        (destination / "tests" / name).write_text(text)
    return destination


def clean_environment() -> dict[str, str]:
    """Remove inherited pytest selection/plugin settings; isolate Python at startup."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("PYTEST_", "STEWART_TEST_"))}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def path_without_rustc(path_value: str) -> str:
    """path_value without every entry in which rustc resolves, as scripts/check.py provisions.

    pip runs `rustc --version` for its user agent wherever shutil.which finds rustc,
    and under a test's empty HOME a rustup proxy would start installing a toolchain
    from the network. Tests that start pip give it this PATH; tests/test_runner.py
    keeps it in step with check.py's provisioning_path.
    """
    return os.pathsep.join(entry for entry in path_value.split(os.pathsep) if not shutil.which("rustc", path=entry))


def rustc_stub(directory: Path, calls: Path) -> Path:
    """Write directory/rustc, which appends its arguments to calls and fails, as pip tolerates.

    First on PATH it records every start and shadows any rustup proxy behind it.
    """
    directory.mkdir(parents=True)
    stub = directory / "rustc"
    stub.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> {shlex.quote(str(calls))}\nexit 1\n")
    stub.chmod(0o755)
    return stub


def run_cmd(argv, *, cwd=None, env=None, check=False, timeout=60):
    """Capture both streams and include them in a failed-command diagnostic."""
    result = subprocess.run([str(arg) for arg in argv], cwd=cwd, env=env,
                            text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise AssertionError(f"command {argv!r} exited {result.returncode}\n"
                             f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result
