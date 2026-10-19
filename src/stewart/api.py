"""Lazy callable API for audit custody.

Import functions from this module; package submodule names remain modules.
Resolution performs imports only, never repository or process work. Keeping
this surface separate lets experiment children import the stdlib-only ledger
without loading custody code, regardless of prior imports.
"""

from __future__ import annotations

import importlib

_EXPORTS = {
    "StewartError": "stewart._bootstrap",
    "Workspace": "stewart.workspace",
    "workspace": "stewart.workspace",
    "initialize": "stewart.assignment",
    "verify_inputs": "stewart.verify_inputs",
    "export_evidence": "stewart.handoff",
    "recover_runtime": "stewart.runtime",
    "prompt_metadata": "stewart.assignment",
    "prepare": "stewart.prepare",
    "collect": "stewart.collect",
    "close": "stewart.close",
    "inventory": "stewart.collect",
    "custody_gaps": "stewart.collect",
    "report_declaration": "stewart.report_declaration",
    "validate_report_declaration": "stewart.report_declaration",
    "triage_draft": "stewart.triage",
    "triage": "stewart.triage",
    "retain": "stewart.triage",
    "resume": "stewart.triage",
    "status": "stewart.status",
    "release": "stewart.experiment",
    "run": "stewart.experiment",
    "Ledger": "stewart.ledger",
    "summarize": "stewart.ledger",
    "prerequisites": "stewart.ledger",
    "record_launch": "stewart.coordination",
    "load_profile": "stewart.launch_profile",
    "render_command": "stewart.launch_profile",
    "render_probe": "stewart.launch_profile",
    "read_exit_log": "stewart.launch_profile",
    "handoff_prompt": "stewart.launch_profile",
    "record_message": "stewart.coordination",
    "tool_identity": "stewart.session",
    "package_identity": "stewart.session",
    "main": "stewart.cli",
    "discover": "stewart.audits",
    "select": "stewart.audits",
    "bind": "stewart.audits",
    "load_reference": "stewart.audits",
    "register": "stewart.audits",
    "inspect_request": "stewart.request_keys",
    "create_worktree": "stewart.holdings",
    "create_branch": "stewart.holdings",
    "create_directory": "stewart.holdings",
    "enroll": "stewart.holdings",
    "associate": "stewart.holdings",
    "acknowledge": "stewart.holdings",
    "show_resource": "stewart.holdings",
    "close_resources": "stewart.holdings",
    "closeout": "stewart.holdings",
    "close_plan": "stewart.close",
    "runtime_handoff": "stewart.implementation",
}
#: API names whose function has another name in its module.
_ALIASES = {"inspect_request": "show", "show_resource": "show", "runtime_handoff": "handoff"}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    try:
        module_name = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module 'stewart.api' has no attribute {name!r}") from None
    value = getattr(importlib.import_module(module_name), _ALIASES.get(name, name))
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))
