"""Scope adapters carry exact paths and exclude command-line widening options.

These are construction checks. Real harness allow/deny controls establish the
effective filesystem boundary separately; rendering alone is not that proof.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from stewart._bootstrap import StewartError
from stewart.auditor_scope import claude_settings, scope_for, scoped_argv, validate_command, validate_scope


@pytest.fixture
def scope(tmp_path):
    repo = tmp_path / "project with 'quotes'"
    return scope_for({"repo": str(repo), "worktree": str(repo / ".scratch/stewart/workspace/audit/worktree"),
                      "runtime": {"root": str(repo / ".scratch/stewart-runtimes/uuid")},
                      "common_dir": str(repo / ".git")},
                     manager_home=tmp_path / "manager", interpreter_prefix=tmp_path / "interpreter",
                     private_roots=[str(tmp_path / "other-checkout")])


def test_adapter_separates_file_tools_shell_and_private_paths(scope):
    command = ["/trusted/claude", "--model", "{model}", "--effort", "{effort}", "{prompt}"]
    validate_command(command)
    argv = scoped_argv(command, scope)
    assert "--restricted" in argv and "--safe-mode" in argv and "--strict-mcp-config" in argv
    assert argv[argv.index("--add-dir") + 1] == scope["runtime"]
    settings = json.loads(argv[argv.index("--settings") + 1])
    assert settings == claude_settings(scope)
    fs = settings["sandbox"]["filesystem"]
    assert scope["runtime"] in fs["allowRead"] and scope["runtime"] in fs["denyWrite"]
    assert str(Path(scope["runtime"]).parent) not in fs["allowRead"]
    assert str(Path(scope["worktree"]).parent) not in fs["allowRead"]
    assert scope["repository"] in fs["denyRead"] and scope["manager_home"] in fs["denyRead"]
    assert scope["git_common"] + "/stewart" in fs["denyRead"]
    assert str(Path.home() / ".cache/stewart/managers") in fs["denyRead"]
    assert any(root.endswith("other-checkout") for root in fs["denyRead"])
    assert settings["sandbox"]["failIfUnavailable"] and not settings["sandbox"]["allowUnsandboxedCommands"]
    assert not settings["sandbox"]["excludedCommands"] and not settings["sandbox"]["network"]["allowedDomains"]
    assert settings["permissions"]["deny"] == [f"{tool}(/{scope['runtime']}/**)" for tool in ("Edit", "Write")]
    changed = [*command[:-1], "different prompt"]
    assert scoped_argv(changed, scope)[1:-1] == argv[1:-1], "question content must not widen filesystem scope"


@pytest.mark.parametrize("options", [
    ["--add-dir", "/"], ["--settings", "wide.json"], ["--settings=wide.json"],
    ["--permission-mode", "bypassPermissions"], ["--dangerously-skip-permissions"],
    ["--tools", "Read,Bash"], ["--mcp-config", "extra.json"], ["--resume", "session"],
    ["--continue"], ["--model", "{model}", "--model", "different"], ["--", "extra-prompt"],
])
def test_scoped_profile_cannot_override_the_fixed_harness_policy(options):
    with pytest.raises(StewartError) as caught:
        validate_command(["/trusted/claude", *options, "{prompt}"])
    assert caught.value.reason == "launch_profile"


@pytest.mark.parametrize("field,value", [
    ("runtime", "private"), ("runtime", "/project/../private"), ("runtime", "/project/*"),
    ("runtime", "/project/[literal]"), ("manager_home", "/private\nextra"),
])
def test_scope_paths_are_literal_and_absolute(scope, field, value):
    with pytest.raises(StewartError) as caught:
        validate_scope({**scope, field: value})
    assert caught.value.reason == "auditor_scope"


def test_parent_grants_cannot_reopen_private_storage(scope):
    for override in ({"runtime": str(Path(scope["worktree"]).parent)},
                     {"manager_home": str(Path(scope["runtime"]) / "cache")},
                     {"interpreter_prefix": scope["repository"]}):
        with pytest.raises(StewartError) as caught:
            validate_scope({**scope, **override})
        assert caught.value.reason == "auditor_scope"


@pytest.mark.parametrize("field", ["model", "effort"])
def test_profile_values_cannot_be_harness_option_tokens(field):
    from stewart.launch_profile import validate_profile
    profile = {"schema": "stewart.launch-profile/2", "scope_adapter": "claude-code-restricted/1",
               "harness": "trusted harness", "model": "model-name", "effort": "high", "actor": "manager",
               "command": ["/trusted/claude", "--model", "{model}", "--effort", "{effort}", "{prompt}"]}
    assert validate_profile(profile)[field] == profile[field]
    with pytest.raises(StewartError) as caught:
        validate_profile({**profile, field: "--dangerously-skip-permissions"})
    assert caught.value.reason == "launch_profile"
    assert validate_profile({**profile, field: "ordinary-hyphenated-name"})[field] == "ordinary-hyphenated-name"
