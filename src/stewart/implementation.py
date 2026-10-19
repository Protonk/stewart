"""Implementation identity and explicit runtime handoff, from verified records only.

A record's ``stewart`` stamp names the package that wrote it by the digest of
its complete member inventory, which does not depend on where the package is
installed. Mutating a session, resuming a close or retrying a request under a
different implementation is refused with ``implementation_mismatch``.

When the writer's recorded invocation verifies through descriptor reads alone
(its retained deployment holds exactly the recorded members under the recorded
runtime digest, its launcher has the recorded bytes and the interpreter is
present), the supported isolated-manager argv is returned for the caller to run
explicitly. Nothing here imports or executes recorded code, relays recorded
command text or falls back to the current installation. Verification
establishes consistency with the recorded pin, not authenticity or permission.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import stat

from stewart._bootstrap import (
    EXIT_UNVERIFIED, MANIFEST_SCHEMA, StewartError, observe_runtime, read_regular, runtime_digest, validate_manifest,
)

#: The only invocation form a handoff constructs.
ROUTE = "isolated-manager/1"
_DIGEST = re.compile(r"[0-9a-f]{64}")
_LIMIT = "consistency with the recorded pin only; not authenticity, not permission to execute"


def recorded_digest(stamp: object) -> str | None:
    """The writing package's byte identity, or None when the stamp is absent or malformed."""
    if isinstance(stamp, dict) and isinstance(stamp.get("package_sha256"), str) \
            and _DIGEST.fullmatch(stamp["package_sha256"]):
        return stamp["package_sha256"]
    return None


def viewer() -> dict:
    """The running implementation's stamp."""
    from stewart.session import tool_identity
    return tool_identity()


def _canonical(value: object) -> bool:
    return (isinstance(value, str) and value.startswith("/") and "\0" not in value
            and PurePosixPath(value).as_posix() == value and ".." not in PurePosixPath(value).parts)


def handoff(stamp: object, arguments: list[str]) -> dict:
    """The writer's verified invocation with ``arguments`` appended, or why it cannot be offered.

    The deployment must have the layout ``<home>/deployments/<digest>/runtime``
    beside ``<home>/launchers/<launcher digest>.py``; any other recorded path is
    not observed at all. Missing prerequisites are named and their diagnostics
    retained; the result is never executed here.
    """
    missing: list[str] = []
    diagnostics: list[str] = []

    def unresolved() -> dict:
        return {"state": "unresolved", "missing": missing, "diagnostics": diagnostics,
                "note": "no other installation is substituted; restore the recorded implementation or "
                        "continue with the build that wrote these records"}

    invocation = stamp.get("invocation") if isinstance(stamp, dict) else None
    if not isinstance(invocation, dict):
        missing.append("invocation")
        diagnostics.append("the writer recorded no launcher invocation (an in-process caller or an unstamped record)")
        return unresolved()
    code_root, launcher, interpreter = (invocation.get(key) for key in ("code_root", "launcher", "interpreter"))
    runtime_sha256, launcher_sha256 = invocation.get("runtime_sha256"), invocation.get("launcher_sha256")
    if (invocation.get("route") != ROUTE or not all(_canonical(item) for item in (code_root, launcher, interpreter))
            or not all(isinstance(item, str) and _DIGEST.fullmatch(item) for item in (runtime_sha256, launcher_sha256))):
        missing.append("invocation")
        diagnostics.append("the recorded invocation is not the supported isolated-manager form with absolute "
                           "canonical paths and full digests")
        return unresolved()
    root, retained = Path(code_root), Path(launcher)
    if (root.name != "runtime" or root.parent.name != runtime_sha256 or root.parent.parent.name != "deployments"
            or retained.parent != root.parent.parent.parent / "launchers" or retained.name != f"{launcher_sha256}.py"):
        missing.append("invocation")
        diagnostics.append("the recorded deployment and launcher are not in the supported manager-home layout")
        return unresolved()
    members = stamp.get("members")
    try:
        validate_manifest(members)
        if runtime_digest(members) != recorded_digest(stamp):
            raise StewartError("member inventory differs from the recorded package digest", reason="runtime_manifest")
    except StewartError as exc:
        missing.append("package_identity")
        diagnostics.append(f"the record's package identity does not verify: {exc}")
        return unresolved()
    observed, _ = observe_runtime(root)
    entries = observed["entries"]
    expected = [{"path": "stewart", "kind": "directory", "size": None, "sha256": None},
                *({**entry, "path": f"stewart/{entry['path']}"} for entry in members["entries"])]
    if not entries or entries[0].get("kind") == "unreadable" and entries[0].get("path") == ".":
        missing.append("runtime")
        diagnostics.append(f"the recorded deployment is missing or unreadable: {code_root}")
    elif entries != expected or runtime_digest({"schema_version": MANIFEST_SCHEMA, "entries": entries}) != runtime_sha256:
        missing.append("runtime")
        diagnostics.append(f"the recorded deployment's members or bytes differ from the recorded pin: {code_root}")
    info, data = read_regular(retained)
    bootstrap = next((entry.get("sha256") for entry in members["entries"] if entry["path"] == "_bootstrap.py"), None)
    if data is None or info.get("sha256") != launcher_sha256 or launcher_sha256 != bootstrap:
        missing.append("launcher")
        diagnostics.append(f"the recorded launcher is {info.get('kind', 'unreadable')} or differs from its pin: {launcher}")
    try:
        found = os.stat(interpreter)
        if not stat.S_ISREG(found.st_mode) or not os.access(interpreter, os.X_OK):
            raise OSError("not an executable regular file")
    except OSError as exc:
        missing.append("interpreter")
        diagnostics.append(f"the recorded interpreter is unavailable: {interpreter} ({exc})")
    if missing:
        return unresolved()
    return {"state": "verified", "env": {}, "limit": _LIMIT,
            "argv": [interpreter, "-I", "-B", launcher, "manager", "--code-root", code_root,
                     "--runtime-sha256", runtime_sha256, "--", *arguments],
            "runtime": {"code_root": code_root, "runtime_sha256": runtime_sha256, "launcher": launcher,
                        "launcher_sha256": launcher_sha256, "interpreter": interpreter, "route": ROUTE}}


def compare(stamp: object, arguments: list[str], *, current: dict | None = None) -> dict:
    """The recorded writer beside the viewer; a handoff only when they differ."""
    current = current or viewer()
    recorded = recorded_digest(stamp)
    same = None if recorded is None else recorded == current["package_sha256"]
    view = {"recorded": recorded, "viewer": current["package_sha256"], "same": same,
            "version": stamp.get("version") if isinstance(stamp, dict) else None}
    if same is False:
        view["handoff"] = handoff(stamp, arguments)
    return view


def require(stamp: object, *, record: Path, arguments: list[str]) -> None:
    """Refuse a mutation of records written by another implementation, naming the explicit handoff."""
    recorded = recorded_digest(stamp)
    if recorded is None:
        raise StewartError(f"the record names no verifiable writing implementation: {record}",
                           reason="implementation_unrecorded", code=EXIT_UNVERIFIED, retained=[str(record)],
                           next_steps=["preserve the record; a mutation needs the implementation that wrote it"])
    current = viewer()["package_sha256"]
    if recorded == current:
        return
    offered = handoff(stamp, arguments)
    if offered["state"] == "verified":
        import shlex
        steps = ["run this verified command explicitly with the recorded implementation (Stewart does not run it): "
                 + shlex.join(offered["argv"])]
    else:
        steps = ["the recorded implementation cannot be offered: missing " + ", ".join(offered["missing"])
                 + "; " + "; ".join(offered["diagnostics"]),
                 "restore that implementation's deployment, launcher and interpreter; no other installation is used"]
    error = StewartError(f"records were written by implementation {recorded[:12]}…, this is {current[:12]}…; "
                         "a mutation needs an explicit handoff to the recorded implementation",
                         reason="implementation_mismatch", retained=[str(record)], next_steps=steps)
    error.handoff = offered
    raise error
