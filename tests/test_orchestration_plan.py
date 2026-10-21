"""The orchestration outflow cites only interfaces the installed wheel provides.

ORCHESTRATION-PLAN.md is written against the shipped CLI, API and schemas; a
cited command, flag, API name, schema or test that does not exist would send a
fresh agent after an invented interface.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

import pytest

pytestmark = pytest.mark.smoke

PROJECT = Path(os.environ["STEWART_TEST_PROJECT"])
SUITE = Path(os.environ["STEWART_TEST_SUITE"])


def _plan() -> str:
    return (PROJECT / "ORCHESTRATION-PLAN.md").read_text(encoding="utf-8")


def _parser_surface() -> tuple[set[str], set[str], set[str]]:
    """Every subcommand, resource action and option string the installed CLI accepts.

    A delegated command's options belong to its Click leaf, not to the root parser.
    """
    import argparse
    from stewart.cli import build_parser
    from stewart.click_commands import COMMANDS
    commands, actions, options = set(), set(), set()

    def walk(parser: argparse.ArgumentParser, top: bool) -> None:
        for action in parser._actions:
            options.update(item for item in action.option_strings if item.startswith("--"))
            if isinstance(action, argparse._SubParsersAction):
                for name, child in action.choices.items():
                    (commands if top else actions).add(name)
                    if child.delegated:
                        options.update(item for param in COMMANDS[name].params for item in param.opts
                                       if item.startswith("--"))
                    else:
                        walk(child, False)

    walk(build_parser(), True)
    return commands, actions, options


def test_every_cited_command_flag_api_name_schema_and_test_exists():
    import stewart
    import stewart.api as api
    plan = _plan()
    commands, actions, options = _parser_surface()
    cited_commands = set(re.findall(r"`stewart ([a-z][a-z-]*)", plan))
    cited_flags = set(re.findall(r"`(--[a-z][a-z-]*)`", plan))
    cited_api = set(re.findall(r"`api\.([a-z_]+)`", plan))
    cited_schemas = set(re.findall(r"`(stewart\.[a-z][a-z-]*/\d+)`", plan))
    cited_tests = set(re.findall(r"`(tests/test_[a-z_]+\.py)`", plan))
    cited_actions = set(re.findall(r"`(create-worktree|create-branch|create-directory|enroll|associate|"
                                   r"acknowledge|show)`", plan))
    # Firing control: the extraction finds the citations this plan is built on.
    assert {"discover", "select", "status", "request", "close", "resource"} <= cited_commands
    assert {"--request-key", "--ref", "--lifetime", "--resume-request", "--plan"} <= cited_flags
    assert {"discover", "select", "bind", "close_plan"} <= cited_api
    assert "stewart.request/1" in cited_schemas and cited_tests
    assert not cited_commands - commands, f"cited commands the CLI lacks: {sorted(cited_commands - commands)}"
    assert not cited_actions - actions, f"cited resource actions the CLI lacks: {sorted(cited_actions - actions)}"
    assert not cited_flags - options, f"cited flags the CLI lacks: {sorted(cited_flags - options)}"
    assert not cited_api - set(api.__all__), f"cited API names that do not exist: {sorted(cited_api - set(api.__all__))}"
    for name in cited_api:
        assert callable(getattr(api, name)), name
    source = "\n".join(path.read_text(encoding="utf-8") for path in Path(stewart.__file__).parent.rglob("*.py"))
    missing = sorted(schema for schema in cited_schemas if f'"{schema}"' not in source)
    assert not missing, f"cited schemas no module defines: {missing}"
    absent = sorted(test for test in cited_tests if not (SUITE / test).is_file())
    assert not absent, f"cited tests that do not exist: {absent}"


def test_the_outflow_is_self_contained_and_reachable():
    plan = _plan()
    # Invariance: the outflow stands alone after the completed execution plan is removed.
    assert "IDENTITY-AND-CLOSEOUT-PLAN" not in plan
    assert "pending" in plan.split("\n\n", 2)[1].lower(), "the outflow states that orchestration is not implemented"
    assert "ORCHESTRATION-PLAN.md" in (PROJECT / "README.md").read_text(encoding="utf-8")
    assert "ORCHESTRATION-PLAN.md" in (PROJECT / "AGENTS.md").read_text(encoding="utf-8")
