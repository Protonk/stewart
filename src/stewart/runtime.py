"""Manager observations of supplied runtime bytes, independent of helper checks.

An executable manifest describes the expected complete tree. Observations also
retain unexpected files and nonregular failures. Capturing damaged bytes is
valid custody; it never authorizes their execution. Endpoint agreement cannot
detect a transient modification restored between observations.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
import re
import tarfile

from stewart._bootstrap import (
    CHILD_LEDGER_FILE, CHILD_LEDGER_MODULE, StewartError, child_project_paths,
    observe_runtime, open_directory, read_regular, runtime_digest,
    validate_manifest, verify_runtime, write_exclusive,
)
from stewart import _util
from stewart.session import now, write_receipt

RUNTIME_SCHEMA = "stewart.auditor-runtime/2"
CAPTURE_SCHEMA = "stewart.runtime-capture/1"
ASSETS_SCHEMA = "stewart.runtime-assets/1"
PROTOCOLS = {"helpers": "stewart.auditor-helpers/2", "ledger": CHILD_LEDGER_MODULE}
CHILD_SCHEMA = "stewart.child/1"
RECOVERY_SCHEMA = "stewart.runtime-recovery/2"
RECOVERY_ACTIVATION = "asset recovery only; existing session commands, scopes and releases remain bound to their original runtime"
ENDPOINT_LIMIT = "Observed endpoints only; transient changes restored between observations are not detected."


def binding(root: Path, manifest: dict) -> dict:
    """Identify a complete supplied tree without executing or trusting its code."""
    value = {"schema_version": RUNTIME_SCHEMA, "root": str(root),
             "manifest": manifest, "sha256": runtime_digest(manifest), "protocols": dict(PROTOCOLS)}
    return validate_binding(value)


def validate_binding(value: object) -> dict:
    if (not isinstance(value, dict)
            or set(value) != {"schema_version", "root", "manifest", "sha256", "protocols"}
            or value["schema_version"] != RUNTIME_SCHEMA or value["protocols"] != PROTOCOLS):
        raise StewartError("unsupported supplied runtime identity", reason="runtime_identity")
    root = value["root"]
    if (not isinstance(root, str) or not Path(root).is_absolute()
            or Path(root).as_posix() != root or ".." in Path(root).parts or "\0" in root):
        raise StewartError("supplied runtime root must be an explicit canonical absolute path", reason="runtime_identity")
    validate_manifest(value["manifest"])
    if (not isinstance(value["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None
            or runtime_digest(value["manifest"]) != value["sha256"]):
        raise StewartError("supplied runtime manifest differs from its identity", reason="runtime_identity")
    return value


def observation_matches(observed: dict, expected: dict) -> bool:
    """Compare entries, keeping observation and executable-manifest schemas distinct."""
    return observed["entries"] == expected["manifest"]["entries"]


def validate_assets(value: object) -> dict:
    """Validate the private asset pins without reading an exposed runtime."""
    if (not isinstance(value, dict) or set(value) != {"schema_version", "manifest_sha256", "archive_sha256"}
            or value["schema_version"] != ASSETS_SCHEMA
            or any(not isinstance(value[key], str) or re.fullmatch(r"[0-9a-f]{64}", value[key]) is None
                   for key in ("manifest_sha256", "archive_sha256"))):
        raise StewartError("invalid pristine runtime asset binding", reason="runtime_assets")
    return value


def archive_bytes(payloads: dict[str, bytes]) -> bytes:
    """Produce a deterministic regular-file archive from descriptor-read bytes."""
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, data in sorted(payloads.items()):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o600
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def select_runtime(root: Path) -> dict:
    """Snapshot the selected distribution, independently of project history."""
    from stewart._invocation import current
    selected = current()
    expected = binding(root, selected.manifest)
    observed, payloads = observe_runtime(selected.code_root)
    if not observation_matches(observed, expected):
        raise StewartError("selected distribution changed before runtime supply", reason="runtime_mismatch",
                           retained=[str(selected.code_root)])
    manifest = _util.receipt_json_bytes(expected["manifest"])
    archive = archive_bytes(payloads)
    return {"identity": expected, "payloads": payloads, "manifest_bytes": manifest, "archive_bytes": archive,
            "assets": {"schema_version": ASSETS_SCHEMA, "manifest_sha256": _util.sha256_bytes(manifest),
                       "archive_sha256": _util.sha256_bytes(archive)}}


def materialize(expected: dict, payloads: dict[str, bytes]) -> None:
    """Create a fresh verified runtime; never replace an existing directory.

    The complete manifest is checked against the bytes before publication. Each
    write uses pinned no-follow directory descriptors, including new ancestors.
    """
    validate_binding(expected)
    entries = expected["manifest"]["entries"]
    regular = {item["path"]: item for item in entries if item["kind"] == "file"}
    if (set(regular) != set(payloads) or any(len(payloads[name]) != pin["size"]
            or _util.sha256_bytes(payloads[name]) != pin["sha256"] for name, pin in regular.items())):
        raise StewartError("runtime payloads differ from the complete manifest", reason="runtime_mismatch")
    root = Path(expected["root"])
    ancestor = Path(root.anchor)
    for part in root.parent.parts[1:]:
        with open_directory(ancestor) as parent:
            try:
                os.mkdir(part, mode=0o700, dir_fd=parent)
            except FileExistsError:
                pass
        ancestor /= part
    try:
        with open_directory(root.parent) as parent:
            os.mkdir(root.name, mode=0o700, dir_fd=parent)
            with open_directory(Path(root.name), dir_fd=parent) as directory:
                for item in entries:
                    rel = Path(item["path"])
                    if item["kind"] == "directory":
                        with open_directory(rel.parent, dir_fd=directory) as ancestor:
                            os.mkdir(rel.name, mode=0o700, dir_fd=ancestor)
                    else:
                        write_exclusive(rel, payloads[item["path"]], dir_fd=directory)
        verify_runtime(root, expected["manifest"])
    except FileExistsError as exc:
        raise StewartError("runtime destination exists; it is never replaced", reason="destination_exists",
                           retained=[str(root)], next_steps=["preserve this directory and choose a fresh runtime destination"]) from exc


def retain_runtime(session: Path, selected: dict) -> dict:
    """Retain private pristine assets before exposing a separately scoped copy."""
    from stewart.captured import pristine_runtime
    private = session / "runtime-pristine"
    private.mkdir(mode=0o700, exist_ok=False)
    write_exclusive(private / "manifest.json", selected["manifest_bytes"])
    write_exclusive(private / "files.tar", selected["archive_bytes"])
    payloads = pristine_runtime(session, {"runtime": selected["identity"], "runtime_assets": selected["assets"]})
    materialize(selected["identity"], payloads)
    state = runtime_state(selected["identity"])
    observe_phase(state, session, "preparation", directory="runtime-prepared")
    require_match(session, state, phases={"preparation"})
    write_receipt(session / "RUNTIME-PREPARED.json", {"runtime": state})
    return state


def helper_argv(identity: dict, interpreter: str, helper: str, *arguments: str) -> list[str]:
    """Issue only the fixed auditor helper policies over the shared bootstrap."""
    validate_binding(identity)
    if helper not in {"inputs", "declaration"}:
        raise StewartError("unsupported auditor helper", reason="runtime_helper")
    root = Path(identity["root"])
    return [interpreter, "-I", "-B", str(root / "stewart/_bootstrap.py"), "helper",
            "--code-root", str(root), "--runtime-sha256", identity["sha256"], "--helper", helper,
            "--", *arguments]


def child_command(identity: dict, *, interpreter: str, worktree: Path, script: str,
                  script_sha256: str, arguments: list[str], launcher: dict | None = None) -> dict:
    """Bind effective child startup to a private launcher and the supplied ledger.

    Release selects the current manager-owned launcher. Execution supplies the
    recorded selection again; a newer installation cannot replace it silently.
    The approved script argv is recorded separately by the release producer.
    """
    validate_binding(identity)
    if launcher is None:
        from stewart._invocation import current
        selected = current()
        launcher = {"path": str(selected.launcher), "sha256": selected.launcher_sha256}
    if (not isinstance(launcher, dict) or set(launcher) != {"path", "sha256"}
            or not isinstance(launcher["path"], str) or not Path(launcher["path"]).is_absolute()
            or not isinstance(launcher["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", launcher["sha256"]) is None):
        raise StewartError("child launcher must have an explicit retained path and digest", reason="child_binding")
    info, data = read_regular(Path(launcher["path"]))
    if data is None or info.get("sha256") != launcher["sha256"]:
        raise StewartError("retained child launcher changed or disappeared", reason="launcher_mismatch",
                           retained=[launcher["path"]])
    ledger = next((item for item in identity["manifest"]["entries"] if item["path"] == CHILD_LEDGER_FILE), None)
    if ledger is None or ledger["kind"] != "file":
        raise StewartError("supplied runtime lacks its ledger", reason="runtime_identity")
    paths = child_project_paths(worktree, script)
    return {"schema": CHILD_SCHEMA, "launcher": launcher, "project_paths": paths,
            "ledger": {"module": CHILD_LEDGER_MODULE, "path": str(Path(identity["root"]) / CHILD_LEDGER_FILE),
                       "sha256": ledger["sha256"]},
            "argv": [interpreter, "-I", "-B", launcher["path"], "child", "--code-root", identity["root"],
                     "--runtime-sha256", identity["sha256"], "--worktree", str(worktree),
                     "--script-sha256", script_sha256, "--", script, *arguments]}


def capture_runtime(expected: dict, destination: Path) -> dict:
    """Preserve two observations and all first-observation regular bytes.

    The private capture directory is fresh. Archives contain bytes already read
    through verified descriptors, never another pathname read of the source.
    Links, missing roots and unreadable entries remain in the observations.
    """
    validate_binding(expected)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    write_receipt(destination / "STARTED.json", {"runtime": expected, "started_at": now().isoformat()})
    before, payloads = observe_runtime(Path(expected["root"]))
    write_receipt(destination / "before.json", before)
    write_exclusive(destination / "files.tar", archive_bytes(payloads))
    after, _ = observe_runtime(Path(expected["root"]))
    write_receipt(destination / "after.json", after)
    digests = {}
    for name in ("before.json", "after.json", "files.tar"):
        info, data = read_regular(destination / name)
        if data is None:
            raise StewartError(f"runtime capture became unreadable: {name}", reason="runtime_capture",
                               retained=[str(destination)])
        digests[name] = info["sha256"]
    movement = before != after
    matched = observation_matches(before, expected) and observation_matches(after, expected) and not movement
    record = {"schema_version": CAPTURE_SCHEMA, "runtime": expected, "digests": digests,
              "movement": movement, "matches_expected": matched, "captured_files": len(payloads),
              "completed_at": now().isoformat(), "limit": ENDPOINT_LIMIT}
    write_receipt(destination / "capture.json", record)
    info, data = read_regular(destination / "capture.json")
    if data is None:
        raise StewartError("runtime capture receipt became unreadable", reason="runtime_capture")
    return {"directory": destination.name, "sha256": info["sha256"]}


def runtime_state(expected: dict) -> dict:
    """A manager record keeps expected identity apart from observed captures."""
    return {"identity": validate_binding(expected), "observations": {}}


def record_state(record: dict, *, session_record: dict | None = None) -> dict:
    """Require an explicit observation binding, optionally checking preparation."""
    from stewart.captured import runtime_reference
    if "runtime" not in record:
        raise StewartError("record has no runtime binding", reason="runtime_capture_schema")
    state = record["runtime"]
    if not isinstance(state, dict) or set(state) != {"identity", "observations"}:
        raise StewartError("invalid runtime observation binding", reason="runtime_capture_schema")
    identity = validate_binding(state["identity"])
    if not isinstance(state["observations"], dict):
        raise StewartError("invalid runtime observation references", reason="runtime_capture_schema")
    for reference in state["observations"].values():
        runtime_reference(reference)
    if session_record is not None and identity != session_record["runtime"]:
        raise StewartError("observed runtime identity differs from preparation", reason="binding_mismatch")
    return state


def record_assets(record: dict, *, session_record: dict | None = None) -> dict:
    """Bind exportable pristine assets to the same preparation as the source record."""
    assets = validate_assets(record.get("runtime_assets"))
    if session_record is not None and assets != session_record["runtime_assets"]:
        raise StewartError("pristine asset pins differ from preparation", reason="binding_mismatch")
    return assets


def observe_phase(state: dict, parent: Path, phase: str, *, directory: str | None = None) -> None:
    destination = parent / (directory or f"runtime-{phase}")
    try:
        state["observations"][phase] = capture_runtime(state["identity"], destination)
    except (OSError, StewartError) as exc:
        # The enclosing exclusive receipt can still preserve this failure if a
        # capture operation fails. Do not invent a completed capture or discard
        # independently preserved report/child bytes because this phase failed.
        state["observations"][phase] = {"directory": destination.name,
                                        "error": {"reason": getattr(exc, "reason", "runtime_capture_io"),
                                                  "message": str(exc)}}
        raise


def require_match(parent: Path, state: dict, *, phases: set[str]) -> None:
    """Release/execution require independently captured matching endpoints."""
    from stewart.captured import runtime_observations
    records = runtime_observations(parent, state, phases=phases)
    if any(not record["matches_expected"] for record in records.values()):
        raise StewartError("supplied runtime differs from its prepared identity", reason="runtime_mismatch",
                           retained=[str(parent / entry["directory"]) for entry in state["observations"].values()],
                           next_steps=["preserve the changed runtime and captured observations; do not substitute current tool bytes"])


def recover_runtime(ws, ident: str, *, actor: str, lifetime: str | None = None,
                    request_key: str | None = None) -> dict:
    """Materialize retained code at a fresh path; see ``_recover_runtime``."""
    from stewart.request_keys import keyed
    from stewart.session import output
    return keyed(ws, ident, "recover-runtime", {"actor": actor}, request_key,
                 lambda plan: _recover_runtime(ws, ident, actor, lifetime, plan), lifetime=lifetime,
                 outputs=lambda result: [output(Path(result["path"]), "runtime-recovery", ws, ident,
                                                result["session_uuid"], name=result["recovery"])])


def _recover_runtime(ws, ident: str, actor: str, lifetime: str | None, plan) -> dict:
    """Materialize retained code at a fresh path without changing session grants.

    Recovery preserves assets for inspection or a separately authorized fresh
    assignment. It never retargets an existing helper command, harness scope or
    release. Its own capture survives loss of the materialized directory.
    """
    from stewart.captured import pristine_runtime
    from stewart.session import capture_receipt, mutable_session, stamp, tool_identity
    from stewart.workspace import contained
    if not isinstance(actor, str) or not actor.strip():
        raise StewartError("runtime recovery needs an attributed actor", reason="actor_required")
    session, record = mutable_session(ws, ident, lifetime=lifetime, check_retention=False)
    observed, session_digest = capture_receipt(session / "session.json", what="session record")
    if observed != record:
        raise StewartError("session changed before recovery", reason="binding_mismatch")
    name = stamp()
    destination = contained(Path(record["audit_dir"]), f"runtime-recovered-{name}")
    recovered = binding(destination, record["runtime"]["manifest"])
    directory = contained(session, f"runtime-recoveries/{name}")
    plan([{"kind": "runtime-recovery", "path": str(directory / "RECOVERY.json"),
           "audit": {"workspace": ws.rel, "slug": ws.slug, "audit_id": ident}, "lifetime": record["session_uuid"]},
          {"kind": "runtime", "path": str(destination)}])
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    document = {"schema_version": RECOVERY_SCHEMA, "name": name, "recorded_at": now().isoformat(),
                "audit_id": ident, "workspace": ws.rel, "session_sha256": session_digest,
                "source_runtime": record["runtime"], "runtime_assets": record["runtime_assets"],
                "runtime": runtime_state(recovered), "actor": actor, "materialized": False,
                "error": None, "stewart": tool_identity(),
                "activation": RECOVERY_ACTIVATION}
    write_receipt(directory / "STARTED.json", document)
    failure = None
    try:
        materialize(recovered, pristine_runtime(session, record))
        document["materialized"] = True
    except (StewartError, OSError) as exc:
        failure = exc
        document["error"] = exc.to_json() if isinstance(exc, StewartError) else {"reason": "runtime_recovery", "message": str(exc)}
    try:
        observe_phase(document["runtime"], directory, "recovery")
        if failure is None:
            require_match(directory, document["runtime"], phases={"recovery"})
    except (StewartError, OSError) as exc:
        document["observation_error"] = str(exc)
        failure = failure or exc
    write_receipt(directory / "RECOVERY.json", document)
    if failure is not None:
        raise StewartError(f"runtime recovery failed: {failure}", reason=getattr(failure, "reason", "runtime_recovery"),
                           retained=[str(directory), str(destination)],
                           next_steps=["preserve the failed recovery and its source assets; no current installation is substituted"]) from failure
    return {"audit_id": ident, "session_uuid": record["session_uuid"], "recovery": name,
            "path": str(directory / "RECOVERY.json"),
            "runtime": recovered, "record": document,
            "next_steps": ["inspect the recovered assets; execution requires a separately authorized fresh assignment"]}
