"""Manager acknowledgments of how an auditor was launched and what was said to it.

Stewart launches nothing and observes no auditor. The only record of how a
handoff was made (a terminal session, a harness sub-agent, something else), with
which model and effort, and of any ruling or message exchanged with the auditor
after launch, is the manager's own acknowledgment. These records are append-only
receipts in the session: they are attributed claims, not observations, and they
never grade the audit. A launch record binds to the handoff it acknowledges by
the session's launch token and prompt commit.
"""

from __future__ import annotations

from pathlib import Path

from stewart._bootstrap import StewartError
from stewart.launch_profile import EXIT_LOG, load_profile, render_command
from stewart.session import (
    LAUNCH_SCHEMA,
    MESSAGE_SCHEMA,
    load_session,
    now,
    stamp,
    tool_identity,
    write_receipt,
)
from stewart.workspace import Workspace

#: How the handoff reached the auditor. ``terminal`` is the documented TUI
#: recipe; ``subagent`` is a harness-spawned agent, which inherits the manager's
#: working directory and context; ``other`` must be explained in the note.
LAUNCH_STYLES = ("terminal", "subagent", "other")
MESSAGE_DIRECTIONS = ("to-auditor", "from-auditor")


def _text(value: object, what: str, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise StewartError(f"{what} must be nonempty text", reason="coordination_schema")
    return value


def record_launch(ws: Workspace, ident: str, *, style: str | None = None, model: str | None = None,
                  effort: str | None = None, actor: str | None = None, note: str | None = None,
                  from_profile: bool = False, profile_path: str | None = None) -> dict:
    """Record the manager's acknowledgment of one handoff; Stewart observed none of it.

    ``style``, ``model`` and ``effort`` are what the manager requested of the
    harness, not what the harness resolved. A note names anything the style
    does not capture: the harness, the first prompt used, an isolation caveat.
    With ``from_profile`` the values come from the launch profile pinned at
    preparation, and the record carries that profile's digest and the exact
    command it rendered; explicit arguments still override single values. A
    ``profile_path`` names a working-tree profile to use instead, for a session
    whose pinned recipe went stale; the record then carries both digests.
    """
    session, record = load_session(ws, ident)
    bound: dict = {}
    if from_profile or profile_path is not None:
        pinned = record.get("launch_profile")
        override = load_profile(ws, profile_path) if profile_path is not None else None
        chosen = override or pinned
        if not isinstance(chosen, dict):
            raise StewartError(
                "this session pinned no launch profile at preparation; name --style, --model, --effort and --actor, "
                "or --profile PATH to render from a working-tree profile",
                reason="launch_profile_missing",
                next_steps=["add LAUNCH-PROFILE.json to the workspace before preparing future sessions"],
            )
        profile = chosen["profile"]
        style = style or profile["style"]
        model = model or profile["model"]
        effort = effort or profile["effort"]
        actor = actor or profile["actor"]
        note = profile["note"] if note is None else note
        bound = {
            "harness": profile["harness"],
            "profile": None if not isinstance(pinned, dict) else {"path": pinned["path"], "sha256": pinned["sha256"]},
            "profile_override": None if override is None else {"path": override["path"], "sha256": override["sha256"]},
            "command": render_command({**profile, "model": model, "effort": effort}, worktree=Path(record["worktree"]),
                                      launch_path=Path(record["worktree"]) / record["handoff"]["path"],
                                      scope=record["auditor_scope"], exit_log=session / EXIT_LOG),
        }
    if style not in LAUNCH_STYLES:
        raise StewartError(f"launch style must be one of {LAUNCH_STYLES}", reason="coordination_schema")
    document = {
        "schema_version": LAUNCH_SCHEMA,
        "name": stamp(),
        "recorded_at": now().isoformat(),
        "audit_id": ident,
        "workspace": ws.rel,
        "actor": _text(actor, "actor"),
        "style": style,
        "model": _text(model, "model"),
        "effort": _text(effort, "effort"),
        "note": _text(note, "note", required=False),
        "prompt_commit": record["prompt_commit"],
        "launch_token": record["launch_token"],
        "harness": bound.get("harness"),
        "profile": bound.get("profile"),
        "profile_override": bound.get("profile_override"),
        "command": bound.get("command"),
        "meaning": "the manager's acknowledgment of how the handoff was made; "
                   "Stewart launched nothing and observed no auditor",
        "stewart": tool_identity(),
    }
    (session / "launches").mkdir(mode=0o700, exist_ok=True)
    location = session / "launches" / f"{document['name']}.json"
    write_receipt(location, document)
    return {"audit_id": ident, "launch": document["name"], "path": str(location), "record": document}


def record_message(ws: Workspace, ident: str, *, direction: str, text: str, actor: str,
                   channel: str | None = None) -> dict:
    """Record one message exchanged with the auditor after launch, as the manager relays it.

    A ruling the manager gives a stopped auditor, or a hand-back the auditor
    sends outside its report, otherwise leaves no trace in the session. The
    record carries the manager's transcription; it does not authenticate the
    auditor's words or establish that they were read.
    """
    if direction not in MESSAGE_DIRECTIONS:
        raise StewartError(f"message direction must be one of {MESSAGE_DIRECTIONS}", reason="coordination_schema")
    session, record = load_session(ws, ident)
    document = {
        "schema_version": MESSAGE_SCHEMA,
        "name": stamp(),
        "recorded_at": now().isoformat(),
        "audit_id": ident,
        "workspace": ws.rel,
        "actor": _text(actor, "actor"),
        "direction": direction,
        "channel": _text(channel, "channel", required=False),
        "text": _text(text, "text"),
        "prompt_commit": record["prompt_commit"],
        "meaning": "a message as the manager relays it; not authenticated and not proof it was read",
        "stewart": tool_identity(),
    }
    (session / "messages").mkdir(mode=0o700, exist_ok=True)
    location = session / "messages" / f"{document['name']}.json"
    write_receipt(location, document)
    return {"audit_id": ident, "message": document["name"], "path": str(location), "record": document}
