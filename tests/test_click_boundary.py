"""Where Click ends: the root parser lists every command; Click parses only delegated leaves.

``stewart.cli`` owns the registry, the global options and context, rendering
and exit codes. ``stewart.click_commands`` holds the Click leaves and is the
only module that imports Click. These tests pin that boundary and the Click
behaviours it deliberately avoids by never calling ``Command.main``.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pytest

import stewart

INSTALLED_LIB = Path(stewart.__file__).parent.parent


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    (commands,) = [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]
    return dict(commands.choices)


@pytest.mark.smoke
def test_the_delegated_commands_are_exactly_the_click_leaves():
    from stewart.cli import build_parser
    from stewart.click_commands import COMMANDS

    children = _subparsers(build_parser())
    delegated = {name for name, child in children.items() if child.delegated}
    assert delegated == set(COMMANDS) == {"docs", "request"}
    assert all(COMMANDS[name].name == name for name in delegated)
    # Everything else, including the resource actions, is still argparse's.
    assert not any(child.delegated for child in _subparsers(children["resource"]).values())


@pytest.mark.smoke
def test_only_the_leaf_module_loads_click(tmp_path, run_cmd):
    """Building the parser, root help and every other module import leave Click unloaded."""
    script = '''
import importlib, pathlib, sys
sys.path.insert(0, sys.argv[1])
names = sorted(p.stem for p in (pathlib.Path(sys.argv[1]) / "stewart").glob("*.py") if p.stem != "click_commands")
for name in names:
    importlib.import_module("stewart." + name)
from stewart.cli import build_parser, main
build_parser().format_help()
try:
    main(["--help"])
except SystemExit:
    pass
before = "click" in sys.modules
importlib.import_module("stewart.click_commands")
print(len(names), before, "click" in sys.modules)
'''
    result = run_cmd([sys.executable, "-I", "-B", "-c", script, INSTALLED_LIB], cwd=tmp_path, check=True)
    count, before, after = result.stdout.splitlines()[-1].split()  # after the root help
    assert int(count) >= 30 and before == "False"
    assert after == "True", "the firing control: the leaf module does load Click"


def test_a_completion_request_in_the_environment_is_ignored(tmp_path, run_cmd):
    """Click's Command.main answers _STEWART_COMPLETE with a shell script; Stewart never calls it."""
    environment = {"_STEWART_COMPLETE": "zsh_source"}
    packaged = (INSTALLED_LIB / "stewart/resources/AUDITOR.md").read_text(encoding="utf-8")
    shown = run_cmd([sys.executable, "-I", "-m", "stewart", "docs", "auditor"], cwd=tmp_path, env=environment)
    assert shown.returncode == 0 and shown.stdout == packaged and shown.stderr == ""
    # Firing control: the same leaf entered through Click's own main emits a completion script.
    control = run_cmd([sys.executable, "-I", "-B", "-c",
                       "from stewart.click_commands import docs; docs.main(['auditor'], prog_name='stewart')"],
                      cwd=tmp_path, env=environment)
    assert "_stewart_completion" in control.stdout and packaged not in control.stdout


def test_an_interrupt_inside_a_delegated_command_stays_an_interrupt(checkout, monkeypatch):
    """Ctrl-C keeps its meaning: KeyboardInterrupt propagates, as for every argparse command."""
    import click
    from stewart import cli, request_keys
    from stewart.click_commands import request

    def interrupted(repo, key):
        raise KeyboardInterrupt

    monkeypatch.setattr(request_keys, "show", interrupted)
    with pytest.raises(KeyboardInterrupt):
        cli.main(["--repo", str(checkout.repo), "request", "--key", "any-key"])
    # Firing control: Click's own entry turns the same interrupt into Abort, even outside standalone mode.
    with pytest.raises(click.exceptions.Abort):
        request.main(["--key", "any-key"], prog_name="stewart request", standalone_mode=False,
                     obj={"repo": checkout.repo})


def test_leaf_usage_errors_are_usage_refusals_and_help_exits_like_argparse(capsys):
    from stewart._bootstrap import StewartError
    from stewart.click_commands import parse

    with pytest.raises(StewartError) as refused:
        parse("request", ["--key"])
    assert refused.value.reason == "usage" and refused.value.exit_code == 2
    assert refused.value.next_steps == ["consult --help for the complete command"]
    with pytest.raises(SystemExit) as finished:
        parse("docs", ["-h"])
    assert finished.value.code == 0 and "Usage: stewart docs [OPTIONS] DOCUMENT" in capsys.readouterr().out
    context = parse("request", ["--key=k1"])
    assert context.params == {"key": "k1"} and context.command_path == "stewart request"


def test_a_missing_click_names_its_reason_in_the_json_contract(monkeypatch):
    """Only an import failure of Click itself becomes dependency_missing; other import errors stay errors."""
    import builtins
    from stewart import cli
    from stewart._bootstrap import EXIT_REFUSED, StewartError, exit_code_for

    assert exit_code_for("dependency_missing") == EXIT_REFUSED
    monkeypatch.delitem(sys.modules, "stewart.click_commands", raising=False)
    real = builtins.__import__

    def without(missing):
        def importer(name, *args, **kwargs):
            if name == missing or name.startswith(missing + "."):
                raise ModuleNotFoundError(f"No module named {missing!r}", name=missing)
            return real(name, *args, **kwargs)
        return importer

    namespace = argparse.Namespace(command="docs", leaf_tokens=["auditor"])
    monkeypatch.setattr(builtins, "__import__", without("click"))
    with pytest.raises(StewartError) as refused:
        cli._leaf(namespace)
    assert refused.value.reason == "dependency_missing"
    # Changed property: a missing Stewart module is a defect to surface, not a dependency to install.
    monkeypatch.setattr(builtins, "__import__", without("stewart.click_commands"))
    with pytest.raises(ModuleNotFoundError):
        cli._leaf(namespace)
    monkeypatch.setattr(builtins, "__import__", real)
    assert cli._leaf(argparse.Namespace(command="status")) is None
