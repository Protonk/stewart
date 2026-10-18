"""Explicit harness filesystem scope, separate from model and auditor policy.

The harness executable and its managed settings remain trust roots. The Claude
Code adapter combines restricted file tools with a required shell sandbox;
neither mechanism covers the other's tools. Scope describes access, not a grant
to execute arbitrary code or to read every accessible project file.
"""
from __future__ import annotations

from pathlib import Path

from stewart._bootstrap import StewartError
from stewart._repository import ROLE_MARKER
from stewart._util import canonical_json

#: Schema 3: the worktree and runtime are siblings in the session's checkout
#: directory, outside every working tree, and no private root may contain a
#: granted path, because the qualified harness lets a broader deny win.
SCOPE_SCHEMA = "stewart.auditor-scope/3"
ADAPTER = "claude-code-restricted/1"
_PATH_FIELDS = {"repository", "worktree", "runtime", "git_common", "manager_home", "interpreter_prefix"}
_FIELDS = {"schema", "private_roots", *_PATH_FIELDS}


def validate_scope(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != _FIELDS or value["schema"] != SCOPE_SCHEMA:
        raise StewartError("unsupported auditor filesystem scope", reason="auditor_scope")
    roots = value["private_roots"]
    if (not isinstance(roots, list) or not roots or not all(isinstance(p, str) for p in roots)
            or roots != sorted(set(roots))):
        raise StewartError("scope requires its sorted private storage exclusions", reason="auditor_scope")
    for key, name in [*((key, value[key]) for key in _PATH_FIELDS), *(("private_roots", p) for p in roots)]:
        if (not isinstance(name, str) or not Path(name).is_absolute() or Path(name).as_posix() != name
                or ".." in Path(name).parts or any(c in name for c in "*?[]{}()\\\n\r\0")):
            raise StewartError(f"scope {key} must be an absolute literal path without pattern syntax", reason="auditor_scope")
    repository, common = Path(value["repository"]), Path(value["git_common"])
    # A repository that contains the Git common directory is covered by its
    # entries beside the path to it (see read_denials); any other repository
    # is denied whole.
    covered = value["repository"] in roots or common.is_relative_to(repository)
    if value["manager_home"] not in roots or not covered:
        raise StewartError("scope omits its repository or manager storage", reason="auditor_scope")
    worktree, runtime, manager = (Path(value[key]) for key in ("worktree", "runtime", "manager_home"))
    if worktree.parent != runtime.parent or worktree == runtime:
        raise StewartError("the worktree and runtime must be siblings in the session's checkout directory",
                           reason="auditor_scope")
    if (worktree.is_relative_to(repository) or runtime.is_relative_to(repository)
            or worktree.is_relative_to(common) or runtime.is_relative_to(common)):
        raise StewartError("auditor roots must lie outside the maintainer checkout and Git administration",
                           reason="auditor_scope")
    if (manager.is_relative_to(worktree) or manager.is_relative_to(runtime)
            or worktree.is_relative_to(manager) or runtime.is_relative_to(manager)):
        raise StewartError("auditor roots overlap private manager storage", reason="auditor_scope")
    prefix = Path(value["interpreter_prefix"])
    if worktree.parent.is_relative_to(prefix) or manager.is_relative_to(prefix) or runtime.is_relative_to(prefix):
        raise StewartError("interpreter read scope would include private custody storage", reason="auditor_scope")
    if any(Path(root).is_relative_to(grant) for root in roots for grant in (worktree, runtime, prefix)):
        raise StewartError("auditor read scope would reopen a private root", reason="auditor_scope")
    if any(grant.is_relative_to(root) for root in map(Path, roots) for grant in (worktree, runtime, common, prefix)):
        raise StewartError("a private root would deny a granted path; the broader deny wins in the qualified harness",
                           reason="auditor_scope")
    return value


def scope_for(record: dict, *, manager_home: Path, interpreter_prefix: Path,
              private_roots: list[str]) -> dict:
    """Build operation-time access paths; no filesystem or Git discovery here."""
    from stewart._bootstrap import MANAGER_HOME
    roots = sorted({*private_roots, str(manager_home), str(Path.home() / MANAGER_HOME)})
    return validate_scope({"schema": SCOPE_SCHEMA, "private_roots": roots,
                           "repository": record["repo"], "worktree": record["worktree"],
                           "runtime": record["runtime"]["root"], "git_common": record["common_dir"],
                           "manager_home": str(manager_home), "interpreter_prefix": str(interpreter_prefix)})


def claude_settings(scope: dict) -> dict:
    """Require the tested shell and file-tool boundaries without parent grants."""
    validate_scope(scope)
    common = Path(scope["git_common"])
    denied = list(dict.fromkeys([*scope["private_roots"], str(common / "stewart"),
                                 str(common / "worktrees" / "*" / ROLE_MARKER)]))
    readonly = [scope["runtime"], str(common),
                *(root for root in scope["private_roots"] if not Path(scope["worktree"]).is_relative_to(root))]
    return {
        "autoMemoryEnabled": False, "disableAllHooks": True,
        "permissions": {
            "allow": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
            # Edit rules cover every file-editing tool; the harness does not
            # match Write rules against file permissions (step 0, 2026-10-18).
            "deny": [f"Edit(/{scope['runtime']}/**)"],
            "blockReadsOutsideWorkingDirectories": True,
        },
        "sandbox": {
            "enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False,
            "autoAllowBashIfSandboxed": True, "excludedCommands": [],
            "filesystem": {
                "denyRead": denied,
                "allowRead": [scope["worktree"], scope["runtime"], str(common), scope["interpreter_prefix"]],
                "denyWrite": readonly,
            },
            "network": {"allowedDomains": []},
        },
    }


def validate_command(tokens: list[str], *, probe: bool = False) -> None:
    """Only model, effort and output options may accompany the fixed scope adapter.

    In particular, a command cannot add another directory, settings source,
    MCP server, tool set, session-resume route or permission override. The
    configured executable is trusted to implement this harness protocol.
    """
    if len(tokens) < 2:
        raise StewartError("scoped harness command needs an executable and final prompt", reason="launch_profile")
    final = tokens[-1]
    if (not probe and final != "{prompt}") or final.startswith("-"):
        raise StewartError("scoped harness command needs one final prompt token", reason="launch_profile")
    index, seen = 1, set()
    values = {"--model": {"{model}"}, "--effort": {"{effort}"},
              "--output-format": {"text", "json", "stream-json"}}
    flags = {"-p", "--print", "--verbose", "--no-session-persistence"}
    while index < len(tokens) - 1:
        flag = tokens[index]
        if flag in seen:
            raise StewartError("scoped harness option occurs more than once", reason="launch_profile")
        seen.add(flag)
        if flag in values and index + 1 < len(tokens) - 1 and tokens[index + 1] in values[flag]:
            index += 2
        elif flag in flags:
            index += 1
        else:
            raise StewartError(f"unsupported option in scoped harness command: {flag}", reason="launch_profile")


def scoped_argv(argv: list[str], scope: dict) -> list[str]:
    """Inject fixed isolation options into a previously validated profile argv."""
    settings = canonical_json(claude_settings(scope))
    return [argv[0], "--restricted", "--safe-mode", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--permission-mode", "dontAsk", "--tools", "Read,Glob,Grep,Edit,Write,Bash",
            "--add-dir", scope["runtime"], "--settings", settings, *argv[1:-1], "--", argv[-1]]
