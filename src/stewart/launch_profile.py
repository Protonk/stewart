"""A committed launch profile: the harness invocation as workspace data, not manager memory.

Everything after the prompt commit is mechanical, and the harness command is
the part every manager re-derived by hand: which model and effort to request,
which environment variables to set, how to quote the absolute paths. A
workspace can fix that once in ``LAUNCH-PROFILE.json`` beside its guidance.
Preparation validates the profile, pins its bytes into the session, and prints
the finished terminal command; status reprints it; ``launch --from-profile``
records the handoff from the pinned copy. A later edit to the file changes
nothing for sessions already prepared, unless a command names it as an
override, in which case both digests are recorded.

The names the profile carries belong to the harness vendor and can go stale
without notice. Two cheap defenses live here. A ``probe`` is a short
non-interactive invocation with the same flags, model and effort, printed
ahead of the launch so a stale name fails in the manager's face rather than in
a session nobody is watching. The launch block appends the harness's exit code
and time to ``HARNESS-EXIT.txt`` in the session, so status can report that the
command itself failed when no collection ever follows.

The profile reaches no auditor. Stewart still launches nothing: the manager
runs the printed commands. They are data for a shell, rendered from argv lists
with every token quoted, never assembled from a format string.
"""

from __future__ import annotations

from pathlib import Path
import re
import shlex

from stewart._bootstrap import StewartError, read_regular
from stewart._json import loads_control
from stewart.auditor_scope import ADAPTER, scoped_argv, validate_command, validate_scope
from stewart.workspace import Workspace, contained, relative

PROFILE_NAME = "LAUNCH-PROFILE.json"
PROFILE_SCHEMA = "stewart.launch-profile/2"
EXIT_LOG = "HARNESS-EXIT.txt"
#: Placeholders a command or probe token may carry. ``{prompt}`` is the
#: absolute first prompt and must appear in the command; the others let a
#: harness take the paths directly.
PLACEHOLDERS = ("{model}", "{effort}", "{prompt}", "{worktree}", "{launch}")
STYLES = ("terminal", "subagent", "other")
_REQUIRED = frozenset({"schema", "harness", "model", "effort", "command", "actor", "scope_adapter"})
_OPTIONAL = frozenset({"style", "env", "note", "probe"})
_ENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BRACED = re.compile(r"\{[^{}]*\}")
_EXIT_LINE = re.compile(r"(-?\d+) (\S+)")


def handoff_prompt(launch_path: Path | str, worktree: Path | str) -> str:
    """The first prompt for a fresh auditor thread, absolute so no working directory is assumed."""
    return f"Read {launch_path} and carry out the assigned audit in this worktree: {worktree}"


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StewartError(f"launch profile {what} must be nonempty text", reason="launch_profile")
    return value


def _argv(value: object, what: str, *, needs_prompt: bool) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(t, str) and t for t in value):
        raise StewartError(f"launch profile {what} must be a nonempty list of argv tokens", reason="launch_profile")
    for token in value:
        for braced in _BRACED.findall(token):
            if braced not in PLACEHOLDERS:
                raise StewartError(f"unknown placeholder {braced!r} in launch profile {what}; allowed: {PLACEHOLDERS}",
                                   reason="launch_profile")
        stripped = token
        for placeholder in PLACEHOLDERS:
            stripped = stripped.replace(placeholder, "")
        if "{" in stripped or "}" in stripped:
            # Braces are reserved for placeholders; a literal brace would be
            # passed to the harness silently, so refuse it instead.
            raise StewartError(f"stray brace in launch profile {what} token {token!r}; braces are reserved for placeholders",
                               reason="launch_profile")
    if needs_prompt and not any("{prompt}" in token for token in value):
        raise StewartError(f"launch profile {what} must carry {{prompt}}, the auditor's first prompt",
                           reason="launch_profile")
    return list(value)


def validate_profile(document: object) -> dict:
    """Check the profile's shape; its wisdom (a model that exists, a flag the harness knows) is not checked here."""
    if not isinstance(document, dict) or not _REQUIRED <= set(document) or set(document) - _REQUIRED - _OPTIONAL:
        raise StewartError(
            f"launch profile fields: required {sorted(_REQUIRED)}, optional {sorted(_OPTIONAL)}",
            reason="launch_profile",
        )
    if document["schema"] != PROFILE_SCHEMA:
        raise StewartError(f"launch profile schema must be {PROFILE_SCHEMA!r}", reason="launch_profile")
    profile = {
        "schema": PROFILE_SCHEMA,
        "scope_adapter": document["scope_adapter"],
        "harness": _text(document["harness"], "harness"),
        "style": document.get("style", "terminal"),
        "model": _text(document["model"], "model"),
        "effort": _text(document["effort"], "effort"),
        "actor": _text(document["actor"], "actor"),
        "env": document.get("env", {}),
        "command": _argv(document["command"], "command", needs_prompt=True),
        "probe": None if document.get("probe") is None else _argv(document["probe"], "probe", needs_prompt=False),
        "note": document.get("note", ""),
    }
    if profile["style"] not in STYLES:
        raise StewartError(f"launch profile style must be one of {STYLES}", reason="launch_profile")
    for key in ("model", "effort"):
        if profile[key].startswith("-"):
            raise StewartError(f"launch profile {key} cannot be an option token", reason="launch_profile")
    if not isinstance(profile["note"], str):
        raise StewartError("launch profile note must be text", reason="launch_profile")
    env = profile["env"]
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and _ENV_KEY.fullmatch(k) and isinstance(v, str) for k, v in env.items()
    ):
        raise StewartError("launch profile env must map environment variable names to string values",
                           reason="launch_profile")
    if profile["scope_adapter"] != ADAPTER:
        raise StewartError(f"unsupported scope adapter; expected {ADAPTER}", reason="launch_profile",
                           next_steps=["use a qualified scope adapter, or a manual handoff with equivalent harness configuration"])
    if any(key not in {"LANG", "LC_ALL", "TZ", "CLAUDE_CODE_DISABLE_AUTO_MEMORY"}
           or key == "CLAUDE_CODE_DISABLE_AUTO_MEMORY" and value != "1" for key, value in env.items()):
        raise StewartError("profile environment may set locale/timezone and disable memory only; harness controls are fixed",
                           reason="launch_profile")
    validate_command(profile["command"])
    if profile["probe"] is not None:
        validate_command(profile["probe"], probe=True)
    return profile


def load_profile(ws: Workspace, rel: str | None = None) -> dict | None:
    """A profile as pinned data: the workspace's own, or a named override.

    The workspace's profile may be absent, which means the workspace has none.
    A named override must exist. A symlink, directory or unreadable entry at
    either path is refused rather than ignored: silence there would print no
    command and leave the manager guessing why.
    """
    named = rel is not None
    rel = rel if named else f"{ws.rel}/{PROFILE_NAME}"
    relative(rel)
    location = contained(ws.repo, rel, leaf_link=True)
    if location.is_symlink():
        raise StewartError(f"launch profile must be a regular file, not a link: {rel}", reason="launch_profile")
    if not location.exists():
        if named:
            raise StewartError(f"launch profile not found: {rel}", reason="launch_profile")
        return None
    info, data = read_regular(location)
    if data is None:
        raise StewartError(f"launch profile is not a readable regular file: {rel} ({info.get('kind')})",
                           reason="launch_profile")
    try:
        document = loads_control(data)
    except (ValueError, RecursionError) as exc:
        raise StewartError(f"launch profile is not valid control JSON: {rel}: {exc}", reason="launch_profile",
                           retained=[str(location)],
                           next_steps=["preserve the original profile and author an unambiguous replacement"]) from exc
    return {"path": rel, "sha256": info["sha256"], "profile": validate_profile(document)}


def _substitute(tokens: list[str], profile: dict, worktree: Path | str, launch_path: Path | str) -> list[str]:
    values = {"{model}": profile["model"], "{effort}": profile["effort"],
              "{prompt}": handoff_prompt(launch_path, worktree),
              "{worktree}": str(worktree), "{launch}": str(launch_path)}
    argv = []
    for token in tokens:
        for placeholder, value in values.items():
            token = token.replace(placeholder, value)
        argv.append(token)
    return argv


def _block(profile: dict, argv: list[str], worktree: Path | str, trailer: list[str]) -> str:
    # The OR arm captures cd/harness failure even under shell errexit. A later
    # echo or successful log append must never replace that process status.
    lines = ["(", "  stewart_exit=0", f"  cd {shlex.quote(str(worktree))} &&"]
    env = " ".join(f"{key}={shlex.quote(value)}" for key, value in profile.get("env", {}).items())
    if env:
        lines.append(f"  {env} \\")
    lines += ["    " + shlex.join(argv) + " || stewart_exit=$?", *trailer, '  exit "$stewart_exit"', ")"]
    return "\n".join(lines)


def render_command(profile: dict, *, worktree: Path | str, launch_path: Path | str,
                   scope: dict, exit_log: Path | str | None = None) -> str:
    """The pasteable terminal block: subshell, cd, environment, the harness argv, then the exit record.

    Every token is shell-quoted after substitution, so a worktree path with
    spaces or quotes and a prompt with colons survive the paste. The subshell
    keeps the caller's directory unchanged. With ``exit_log`` the block appends
    the harness's exit code and UTC time to that file after the harness ends;
    if ``cd`` itself fails, that failure is what gets recorded. The final exit
    propagates this status even under shell errexit; logging cannot hide it.
    """
    profile = validate_profile(profile)
    validate_scope(scope)
    if str(worktree) != scope["worktree"]:
        raise StewartError("launch working directory differs from its scope", reason="auditor_scope")
    argv = scoped_argv(_substitute(profile["command"], profile, worktree, launch_path), scope)
    trailer = []
    if exit_log is not None:
        trailer = [f"  printf '%s %s\\n' \"$stewart_exit\" \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" >> {shlex.quote(str(exit_log))} || {{",
                   "    printf '%s\\n' 'Could not record harness exit; preserve the terminal output.' >&2",
                   '    [ "$stewart_exit" -ne 0 ] || stewart_exit=1', "  }"]
    return _block(profile, argv, worktree, trailer)


def render_probe(profile: dict, *, worktree: Path | str, launch_path: Path | str, scope: dict) -> str | None:
    """The probe block, or None when the profile has no probe.

    The probe runs the same model, effort and environment through a short
    non-interactive invocation and echoes and returns its exit code, so a renamed flag or a
    retired model name fails while the manager is still watching.
    """
    profile = validate_profile(profile)
    validate_scope(scope)
    if str(worktree) != scope["worktree"]:
        raise StewartError("probe working directory differs from its scope", reason="auditor_scope")
    if profile.get("probe") is None:
        return None
    argv = scoped_argv(_substitute(profile["probe"], profile, worktree, launch_path), scope)
    return _block(profile, argv, worktree, ['  echo "probe exit $stewart_exit"'])


def read_exit_log(session: Path) -> tuple[list[dict], list[str]]:
    """Parse the harness exit lines the launch block appended; malformed lines are reported, not dropped."""
    info, data = read_regular(session / EXIT_LOG)
    if info["kind"] == "missing":
        return [], []
    if data is None:
        return [], [f"{EXIT_LOG} is not a readable regular file ({info['kind']})"]
    exits, problems = [], []
    for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
        match = _EXIT_LINE.fullmatch(line.strip())
        if match:
            exits.append({"exit": int(match.group(1)), "at": match.group(2)})
        elif line.strip():
            problems.append(f"{EXIT_LOG} line {number} is not 'exit timestamp': {line.strip()!r}")
    return exits, problems
