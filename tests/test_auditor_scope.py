"""Scope adapters carry exact paths and exclude command-line widening options.

These are construction checks. Real harness allow/deny controls establish the
effective filesystem boundary separately; rendering alone is not that proof.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from stewart._bootstrap import StewartError
from stewart._bootstrap import MANAGER_HOME
from stewart._repository import read_denials
from stewart.auditor_scope import claude_settings, scope_for, scoped_argv, validate_command, validate_scope


@pytest.fixture
def scope(tmp_path):
    repo = tmp_path / "project with 'quotes'"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "notes.txt").write_text("maintainer notes\n")
    audit = tmp_path / "checkouts" / "project-0123456789ab" / "uuid"
    roots = read_denials([str(repo), str(tmp_path / "other-checkout")], [str(repo / ".git"), str(tmp_path / "interpreter")])
    return scope_for({"repo": str(repo), "worktree": str(audit / "worktree"),
                      "runtime": {"root": str(audit / "runtime")}, "common_dir": str(repo / ".git")},
                     manager_home=tmp_path / "manager", interpreter_prefix=tmp_path / "interpreter",
                     private_roots=roots)


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
    # The maintainer checkout contains the Git common directory, so it is
    # denied entry by entry: a broader deny would win over the Git grant.
    assert scope["repository"] not in fs["denyRead"] and scope["git_common"] not in fs["denyRead"]
    assert {scope["repository"] + "/src", scope["repository"] + "/notes.txt"} <= set(fs["denyRead"])
    assert scope["git_common"] in fs["allowRead"] and scope["manager_home"] in fs["denyRead"]
    assert scope["git_common"] + "/stewart" in fs["denyRead"]
    assert str(Path.home() / MANAGER_HOME) in fs["denyRead"]
    assert any(root.endswith("other-checkout") for root in fs["denyRead"])
    for grant in fs["allowRead"]:
        assert not any(Path(grant).is_relative_to(denied) for denied in fs["denyRead"] if "*" not in denied), grant
    assert settings["sandbox"]["failIfUnavailable"] and not settings["sandbox"]["allowUnsandboxedCommands"]
    assert not settings["sandbox"]["excludedCommands"] and not settings["sandbox"]["network"]["allowedDomains"]
    assert settings["permissions"]["deny"] == [f"Edit(/{scope['runtime']}/**)"], "Edit rules cover every file tool"
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


def test_a_private_root_cannot_contain_a_granted_path(scope):
    # Control: the fixture's expanded roots validate.
    assert validate_scope(scope) == scope
    for grant in ("git_common", "worktree", "runtime", "interpreter_prefix"):
        widened = sorted({*scope["private_roots"], str(Path(scope[grant]).parent)})
        with pytest.raises(StewartError) as caught:
            validate_scope({**scope, "private_roots": widened})
        assert caught.value.reason == "auditor_scope", grant


def test_read_denials_descend_to_kept_paths_and_refuse_pattern_names(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".venv/lib").mkdir(parents=True)
    (repo / ".venv/pyvenv.cfg").write_text("home\n")
    (repo / "src").mkdir()
    other = tmp_path / "other"
    denied = read_denials([str(repo), str(other)], [str(repo / ".git"), str(repo / ".venv")])
    assert denied == sorted([str(repo / "src"), str(other)])
    # Measured: a name a literal denial cannot express is refused, not left readable.
    for name in ("odd[1].txt", "notes (private)"):
        (repo / name).write_text("pattern syntax\n")
        with pytest.raises(StewartError) as refused:
            read_denials([str(repo)], [str(repo / ".git"), str(repo / ".venv")])
        assert refused.value.reason == "scope_uncovered" and str(repo / name) in refused.value.retained
        assert refused.value.next_steps
        (repo / name).unlink()
    # Invariance: a root that contains no kept path is denied whole, unchanged.
    assert read_denials([str(other)], [str(repo / ".git")]) == [str(other)]
    # A kept path deeper down is reached by descending, denying its siblings.
    (repo / "tools/bin").mkdir(parents=True)
    (repo / "tools/readme").write_text("r\n")
    deeper = read_denials([str(repo)], [str(repo / ".git"), str(repo / "tools/bin")])
    assert str(repo / "tools/readme") in deeper and str(repo / "tools") not in deeper and str(repo / "tools/bin") not in deeper


def test_a_scope_must_deny_the_maintainer_checkout_entries(scope):
    assert validate_scope(scope) == scope, "control: the issued scope validates"
    repository = Path(scope["repository"])
    stripped = [root for root in scope["private_roots"] if Path(root).parent != repository]
    with pytest.raises(StewartError) as refused:
        validate_scope({**scope, "private_roots": stripped})
    assert refused.value.reason == "auditor_scope" and refused.value.next_steps
    # Denying the whole repository is no substitute when it contains the Git grant.
    whole = sorted({*stripped, scope["repository"]})
    with pytest.raises(StewartError) as refused:
        validate_scope({**scope, "private_roots": whole})
    assert "deny a granted path" in str(refused.value), "a whole-repository deny would cover its Git grant"
