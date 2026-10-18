"""Private session records: append-only receipts under the maintainer checkout.

Every receipt is created exclusively. A retry never overwrites evidence; it
writes a new record with a fresh name. Serialization uses the distribution's
deterministic receipt encoding, but the exclusive
publisher here is a domain requirement and is not replaced by an overwriting
helper.

Record names are ``<UTC stamp>-<8 hex>``. Timestamps describe when the
maintainer ran a command, never when an auditor started, finished or paused.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import uuid

from stewart import _util as _hash
from stewart._util import receipt_json_bytes
from stewart._bootstrap import EXIT_UNVERIFIED, StewartError, read_regular, write_exclusive
from stewart._git import git, git_text
from stewart._json import loads_control
from stewart.workspace import Workspace

#: Schema 12 moves the session under the Git common directory and records the
#: per-user checkout home and the session's checkout directory beside it.
SESSION_SCHEMA = 12
#: Captures bind pristine assets and distinguish failed observation operations
#: from completed observations of a mismatching runtime. Schema 7 records errors
#: as reason/message objects and names unexpected paths that are supplemental
#: inputs, so each custody gap carries its exit code.
COLLECTION_SCHEMA = 7
TRIAGE_SCHEMA = 3
RETENTION_SCHEMA = 1
RESUME_SCHEMA = 1
RELEASE_SCHEMA = 5
#: Schema 4 moved ``mismatching_cases`` out of ``ledger.anomalies`` (a fired
#: control is the expected outcome, not an anomaly) and added ``output_area``.
#: Schema 5 binds independently captured supplied-runtime observations before
#: and after execution, apart from the child's report and project endpoints.
#: Schema 6 records the approved script argv separately from isolated startup,
#: with ordered project imports and the pinned ledger/private launcher binding.
ATTEMPT_SCHEMA = 8
LAUNCH_SCHEMA = 2
MESSAGE_SCHEMA = 1

MODES = ("snapshot", "paused")
#: Preparation's stages in order; PREPARE-ERROR.json names the one that failed.
#: Records a later stage writes were never written, not lost, when an earlier
#: stage failed.
PREPARE_STAGES = ("checkout_directory", "retention", "worktree", "role", "inputs", "runtime", "handoff")

RECORD_NAME = re.compile(r"[0-9]{8}T[0-9]{6}-[a-f0-9]{8}")


def package_identity(package: Path, *, source_git: bool = True) -> dict:
    """Observe the complete selected Stewart distribution, including policy data.

    Source files and resources share startup's explicit member selection. Only
    generated installation caches are excluded; a dedicated executable runtime
    excludes nothing. Git context is optional and belongs only to a checkout
    tracking every selected member. This does not attest to in-memory objects,
    interpreter/site hooks or the installed shell entrypoint that selected us.
    """
    from stewart._bootstrap import source_payloads, runtime_digest, SOURCE_MODULES
    package = Path(package).resolve()
    manifest, payloads = source_payloads(package)
    version = re.search(rb'^__version__ = "([0-9A-Za-z.+!-]+)"$', payloads['_version.py'], re.M)
    if version is None:
        raise StewartError("distribution version is not a literal version string", reason="runtime_layout")
    resources = {name: _hash.sha256_bytes(data) for name, data in sorted(payloads.items()) if name.startswith('resources/')}
    identity = {"package": str(package), "version": version.group(1).decode('ascii'),
                "modules": len(SOURCE_MODULES), "members": manifest,
                "package_sha256": runtime_digest(manifest), "resources": resources,
                "commit": None, "dirty": None}
    if not source_git:
        return identity
    try:
        tracked = git(package, "ls-files", "--error-unmatch", "--", *sorted(payloads), check=False)
        if tracked.returncode:
            return identity
        head = git(package, "rev-parse", "HEAD", check=False)
        if head.returncode == 0:
            identity["commit"] = os.fsdecode(head.stdout).strip() or None
            status = git(package, "status", "--porcelain=v1", "-z", "--", str(package), check=False)
            if status.returncode == 0:
                identity["dirty"] = bool(status.stdout.strip(b"\0"))
    except OSError:
        pass
    return identity


def tool_identity() -> dict:
    """Identity of the Stewart code performing the current operation, stamped as ``stewart`` on receipts.

    Isolated startup binds the executing deployment to its complete invocation
    identity. Its enclosing storage repository supplies no Git provenance.
    In-process callers instead receive the current source-file observation;
    neither mode attests to in-memory Python objects or interpreter immutability.
    """
    from stewart._invocation import verified_invocation

    invocation = verified_invocation()
    identity = package_identity(Path(__file__).parent, source_git=invocation is None)
    if invocation is not None:
        identity["invocation"] = invocation.identity()
    return identity


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp() -> str:
    """A fresh record name; the random suffix keeps same-second retries distinct."""
    return now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]


def record_name(value: object, *, what: str) -> str:
    if not isinstance(value, str) or not RECORD_NAME.fullmatch(value):
        raise StewartError(
            f"--{what} must name a record as printed by the tool, not a path", reason="record_name",
        )
    return value


def write_receipt(destination: Path, value: dict, *, dir_fd: int | None = None) -> None:
    """Create a receipt exclusively; an existing file is evidence and is kept."""
    data = receipt_json_bytes(value)
    write_exclusive(destination, data, dir_fd=dir_fd)


def capture_receipt(location: Path, *, what: str) -> tuple[dict, str]:
    """Read one unambiguous control object; preserve invalid records without repair."""
    info, data = read_regular(location)
    if info["kind"] == "missing":
        raise StewartError(f"{what} is missing: {location}", reason="record_missing") from None
    if data is None:
        raise StewartError(f"{what} is not a readable regular file: {location}: {info}", reason="record_unreadable")
    try:
        value = loads_control(data)
    except (ValueError, RecursionError) as exc:
        raise StewartError(f"{what} is not valid control JSON: {location}: {exc}", reason="record_corrupt",
                           retained=[str(location)],
                           next_steps=["preserve the invalid record; do not rewrite historical evidence"]) from exc
    if not isinstance(value, dict):
        raise StewartError(f"{what} is not a JSON object: {location}", reason="record_corrupt")
    return value, info["sha256"]


def read_receipt(location: Path, *, what: str) -> dict:
    """Parse one captured regular-file JSON object; never reopen it for a digest."""
    return capture_receipt(location, what=what)[0]


def session_dir(ws: Workspace, ident: str) -> Path:
    """The session's repo-wide private directory under the Git common directory."""
    from stewart._repository import maintainer, session_location
    return session_location(maintainer(ws.repo)["common_dir"], ws, ident)


def load_session(ws: Workspace, ident: str, *, check_retention: bool = True) -> tuple[Path, dict]:
    """Load a session this tool can interpret and that belongs to this caller.

    An unsupported schema is refused with the session retained: evidence written
    by another version is never rewritten to fit this one.
    """
    from stewart.report_declaration import SCHEMA_VERSION as declaration_schema

    session = session_dir(ws, ident)
    if not session.is_dir():
        # An absent session is a wrong or unprepared audit ID (refused, 2); a
        # session directory without its record is evidence that does not verify.
        raise StewartError(f"no session for audit {ident} in workspace {ws.rel}: {session}", reason="session_missing",
                           next_steps=["check the audit ID against the committed prompt's audit_id; "
                                       "prepare the committed prompt if it was never prepared"])
    try:
        record = read_receipt(session / "session.json", what="session record")
    except StewartError as exc:
        exc.code = EXIT_UNVERIFIED
        raise
    schema = record.get("schema_version")
    if schema != SESSION_SCHEMA:
        raise StewartError(
            f"session schema {schema!r} is not supported; this tool reads schema {SESSION_SCHEMA}. "
            "Retain the session and recover it by hand or with the version that wrote it",
            reason="session_schema_unsupported", retained=[str(session)],
        )
    if record.get("mode") not in MODES:
        raise StewartError(
            "session records an unknown coordination mode; retain it for manual recovery",
            reason="session_schema_unsupported", retained=[str(session)],
        )
    if record.get("report_declaration_schema") != declaration_schema:
        raise StewartError("session report declaration schema differs from this tool; use its pinned tool version",
                           reason="session_schema_unsupported", retained=[str(session)])
    if not isinstance(record.get("launch_token"), str) or not re.fullmatch(r"[0-9a-f]{16}", record["launch_token"]):
        raise StewartError("session launch_token must be the issued 16-character lowercase hex value",
                           reason="session_identity", retained=[str(session)],
                           next_steps=["preserve the invalid session for manual recovery; do not rewrite it"])
    assignment = record.get("assignment")
    if record.get("workspace") != ws.rel or not isinstance(assignment, dict) or assignment.get("audit_id") != ident:
        raise StewartError("session does not belong to this workspace and audit ID", reason="session_identity",
                           retained=[str(session)])
    if record.get("repo") != str(ws.repo):
        # Sessions are repo-wide, but each belongs to the maintainer checkout
        # that prepared it: operate on it from there.
        raise StewartError(f"session {ident} belongs to the maintainer checkout {record.get('repo')}",
                           reason="session_other_maintainer", retained=[str(session)],
                           next_steps=[f"rerun with --repo {record.get('repo')}"])
    from stewart._repository import maintainer, session_uuid, verify_retention
    identity = maintainer(ws.repo)
    if (record.get("common_dir") != identity["common_dir"]
            or record.get("maintainer_git_admin") != identity["git_admin"]):
        raise StewartError("session maintainer Git administration changed", reason="session_identity")
    before = record.get("maintainer_before")
    if (not isinstance(before, dict) or set(before) != {"head", "status"}
            or not all(isinstance(before[key], str) for key in before)):
        raise StewartError("session lacks its maintainer preparation observation", reason="session_identity")
    session_uuid(record.get("session_uuid"))
    from stewart.runtime import validate_assets, validate_binding
    from stewart.auditor_scope import validate_scope
    runtime = validate_binding(record.get('runtime'))
    validate_assets(record.get('runtime_assets'))
    from stewart._repository import audit_location
    home, audit_dir = record.get("checkout_home"), record.get("audit_dir")
    if (not isinstance(home, str) or not isinstance(audit_dir, str)
            or str(audit_location(Path(home), record["common_dir"], record["session_uuid"])) != audit_dir
            or record.get("worktree") != str(Path(audit_dir) / "worktree")):
        raise StewartError("session checkout locations differ from its identity", reason="session_identity")
    if runtime['root'] != str(Path(audit_dir) / "runtime"):
        raise StewartError("runtime root differs from this session's supplied directory", reason="runtime_identity")
    scope = validate_scope(record.get('auditor_scope'))
    if any(scope[key] != expected for key, expected in {
            'repository': str(ws.repo), 'worktree': record['worktree'], 'runtime': runtime['root'],
            'git_common': record['common_dir']}.items()):
        raise StewartError("auditor scope differs from the prepared identities", reason="session_identity")
    interpreter = record.get('helper_interpreter')
    if not isinstance(interpreter, str) or not Path(interpreter).is_absolute():
        raise StewartError("session lacks an explicit helper interpreter", reason="session_identity")
    handoff = record.get('handoff')
    if (not isinstance(handoff, dict) or set(handoff) != {'path', 'sha256'}
            or handoff['path'] != f"{ws.rel}/.stewart-handoffs/{record['session_uuid']}.md"
            or not isinstance(handoff['sha256'], str) or re.fullmatch('[0-9a-f]{64}', handoff['sha256']) is None):
        raise StewartError("session lacks its pinned public handoff", reason="session_identity")
    if check_retention:
        verify_retention(ws.repo, record)
    return session, record


def maintainer_state(repo: Path) -> dict:
    """HEAD plus porcelain status: a coordination signal, not a byte baseline.

    Collection compares this against the prepared value as
    ``maintainer_status_changed_since_prepare``. It cannot see an edit to a file that
    was already dirty, and it cannot certify that a writer pause was honored.
    """
    return {
        "head": git_text(repo, "rev-parse", "HEAD"),
        "status": os.fsdecode(
            git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
        ),
    }


def list_records(directory: Path, *, suffix: str = "") -> list[Path]:
    """Sorted record entries under ``directory``; anything else is reported, not read."""
    if not directory.is_dir():
        return []
    found = []
    for entry in sorted(directory.iterdir()):
        name = entry.name[: -len(suffix)] if suffix and entry.name.endswith(suffix) else entry.name
        if RECORD_NAME.fullmatch(name) and (not suffix or entry.name.endswith(suffix)):
            found.append(entry)
    return found
