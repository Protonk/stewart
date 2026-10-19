"""Collection-bound maintainer dispositions, retention and paused-session resume.

A triage record is the maintainer's separate response to one named collection.
It binds to that collection's receipt digest and to the captured report's
digest (or an explicit report gap), so a later report edit, a new collection or
a changed response never inherits an earlier review. Retention publishes only
bytes the review bound, read from the immutable capture, never from the mutable
checkout. Resume records a release decision; it controls no process.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import re

from stewart import _util as _hash
from stewart.collect import custody_gaps
from stewart.captured import collection_files, load_collection
from stewart._bootstrap import StewartError, read_regular
from stewart.report_declaration import session_declaration_expectations, validate_report_declaration
from stewart.session import (
    RESUME_SCHEMA,
    RETENTION_SCHEMA,
    TRIAGE_SCHEMA,
    bind_lifetime,
    load_session,
    mutable_session,
    output,
    capture_receipt,
    now,
    record_name,
    stamp,
    tool_identity,
    write_receipt,
)
from stewart.workspace import Workspace, contained, relative

_RESPONSE_FIELDS = frozenset({
    "collection", "collection_sha256",
    "report_sha256", "report_gap", "accepted", "rejected", "unresolved",
    "custody_gaps", "support_reviewed", "decision", "applicability", "follow_up",
})
_CLAIM_FIELDS = frozenset({"claim", "reason", "evidence"})
FOLLOW_UP_KINDS = ("needs-evidence", "reframe")
FOLLOW_UP_DISPOSITIONS = ("accept", "decline", "defer")


def _captured_declaration(data: bytes, receipt: dict, session_record: dict) -> dict:
    """Revalidate captured bytes; a cached receipt summary cannot choose the hand-back."""
    expected, sources = session_declaration_expectations(session_record, receipt.get("checkout", {}).get("head"))
    return validate_report_declaration(data, expected=expected, sources=sources)


def _report_kind(declaration: dict) -> str | None:
    """Only a structurally valid, identity-matched declaration can request follow-up."""
    return declaration["declaration"]["report_kind"] if declaration["status"] == "valid" else None


def triage_draft(ws: Workspace, ident: str, *, collection: str, lifetime: str | None = None) -> dict:
    """Return an unanswered response and separate context; write no record.

    The response carries the collection name and receipt digest through submission.
    It alone is suitable for editing and submitting to triage. Null
    values deliberately fail validate_response until the manager answers them.
    Captured report bytes must still match their receipt, including empty ones.
    """
    session, session_record = load_session(ws, ident)
    bind_lifetime(session_record, lifetime, session)
    directory, receipt, digest = load_collection(session, ident, collection, session_record=session_record)
    if receipt.get("workspace") != ws.rel:
        raise StewartError("collection belongs to another workspace", reason="collection_schema")
    data = b""
    if receipt.get("report_status") in ("present", "empty"):
        data = collection_files(directory, receipt, ["REPORT.md"])["REPORT.md"]
    declaration = _captured_declaration(data, receipt, session_record)
    kind = _report_kind(declaration)
    gaps = custody_gaps(receipt)
    response = {"collection": collection, "collection_sha256": digest,
                "accepted": [], "rejected": [], "unresolved": [],
                "custody_gaps": {gap["id"]: None for gap in gaps},
                "decision": None, "support_reviewed": []}
    if kind in FOLLOW_UP_KINDS:
        response["follow_up"] = {"report_kind": kind, "disposition": None, "reason": None}
    if receipt.get("report_status") == "present":
        response["report_sha256"] = receipt["report_sha256"]
    else:
        response["report_gap"] = None
    return {"response": response, "context": {
        "collection": collection, "collection_sha256": digest,
        "report_status": receipt.get("report_status"), "declaration": declaration,
        "runtime": receipt.get("runtime"),
        "report_kind": kind,
        "follow_up_choices": list(FOLLOW_UP_DISPOSITIONS) if kind in FOLLOW_UP_KINDS else [],
        "custody_gaps": gaps, "note": "Unanswered draft; no triage recorded or claims accepted."}}


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StewartError(f"{what} must be nonempty text", reason="response_schema")
    return value


def _claims(value: object, *, bucket: str) -> list[dict]:
    """Validate one claim list; accepted claims need evidence, others need a reason."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise StewartError(f"{bucket} must be a list of claim objects", reason="response_schema")
    claims = []
    for item in value:
        if not isinstance(item, dict) or not set(item) <= _CLAIM_FIELDS:
            raise StewartError(
                f"each {bucket} claim is an object with claim, reason and evidence fields only",
                reason="response_schema",
            )
        _text(item.get("claim"), f"{bucket} claim")
        evidence = item.get("evidence", [])
        if not isinstance(evidence, list) or not all(isinstance(e, str) and e.strip() for e in evidence):
            raise StewartError(f"{bucket} evidence must be a list of nonempty references", reason="response_schema")
        if bucket == "accepted" and not evidence:
            raise StewartError("an accepted claim needs at least one evidence reference", reason="response_schema")
        if bucket != "accepted":
            _text(item.get("reason"), f"{bucket} reason")
        claims.append({"claim": item["claim"], "reason": item.get("reason"), "evidence": evidence})
    return claims


def _require_collection_binding(value: dict, directory: Path, digest: str, *, reason: str) -> None:
    """Compare a response or recorded disposition with the exact receipt read.

    Report bytes and gap membership can stay unchanged across different captures.
    Keep this comparison shared by submission and later custody consumers; never
    replace a submitted identity with the destination selected by the caller.
    """
    if value.get("collection") != directory.name or value.get("collection_sha256") != digest:
        raise StewartError(
            f"collection binding expected {directory.name!r} with receipt SHA-256 {digest}, "
            f"observed {value.get('collection')!r} with {value.get('collection_sha256')!r}",
            reason=reason, retained=[str(directory)],
            next_steps=["run triage-draft for the intended collection and review that capture before submitting; "
                        "do not transplant decisions by changing only the binding fields"],
        )


def validate_response(response: object, receipt: dict, collection_dir: Path, *, collection_sha256: str,
                      session_record: dict) -> dict:
    """Check a maintainer response's shape and its binding to one collection.

    This validates structure and identity only: that every custody gap has a
    disposition and that the submitted collection and report identities match
    the capture. collection_sha256 must come from load_collection's single read,
    not a reserialization or a second path read. This does not judge reasoning.
    """
    if not isinstance(response, dict) or not set(response) <= _RESPONSE_FIELDS:
        raise StewartError(
            f"response fields must be among {sorted(_RESPONSE_FIELDS)}", reason="response_schema",
        )
    validated: dict = {
        "accepted": _claims(response.get("accepted"), bucket="accepted"),
        "rejected": _claims(response.get("rejected"), bucket="rejected"),
        "unresolved": _claims(response.get("unresolved"), bucket="unresolved"),
        "decision": _text(response.get("decision"), "decision"),
    }
    _require_collection_binding(response, collection_dir, collection_sha256, reason="collection_binding")
    validated.update(collection=response["collection"], collection_sha256=response["collection_sha256"])
    data = b""
    if receipt.get("report_status") == "present":
        stated = response.get("report_sha256")
        if not isinstance(stated, str) or not re.fullmatch(r"[0-9a-f]{64}", stated):
            raise StewartError(
                "the collection captured a report; state its SHA-256 in report_sha256 to bind the review to those bytes",
                reason="report_binding",
            )
        info, data = read_regular(collection_dir / "REPORT.md")
        captured = info.get("sha256")
        if data is None or captured != receipt.get("report_sha256"):
            raise StewartError(
                "captured REPORT.md no longer matches the collection receipt; the capture was tampered with or damaged",
                reason="evidence_tampered", retained=[str(collection_dir)],
            )
        if stated != captured:
            raise StewartError(
                f"report_sha256 {stated[:12]}… is not the captured report {captured[:12]}…; review the captured bytes",
                reason="report_binding",
            )
        if response.get("report_gap") is not None:
            raise StewartError("report_gap applies only when no report was captured", reason="response_schema")
        validated["report_sha256"] = stated
        validated["report_gap"] = None
    else:
        if response.get("report_sha256") is not None:
            raise StewartError("no report was captured; use report_gap, not report_sha256", reason="report_binding")
        validated["report_sha256"] = None
        validated["report_gap"] = _text(response.get("report_gap"), "report_gap (no report was captured)")
    kind = _report_kind(_captured_declaration(data, receipt, session_record))
    follow_up = response.get("follow_up")
    if kind in FOLLOW_UP_KINDS:
        # This response is a disposition of the auditor's request, separate
        # from accepting findings. It never mutates the assignment or grants.
        if (not isinstance(follow_up, dict)
                or set(follow_up) != {"report_kind", "disposition", "reason"}
                or follow_up["report_kind"] != kind
                or follow_up["disposition"] not in FOLLOW_UP_DISPOSITIONS
                or not isinstance(follow_up["reason"], str) or not follow_up["reason"].strip()):
            raise StewartError(
                f"captured {kind} report requires follow_up with report_kind={kind!r}, "
                "disposition accept|decline|defer, and a nonempty reason",
                reason="follow_up_required", retained=[str(collection_dir)],
                next_steps=["review the request in this capture and fill its triage-draft follow_up; "
                            "accepted follow-up still needs a fresh assignment for changed inputs or scope"],
            )
        validated["follow_up"] = dict(follow_up)
    else:
        if follow_up is not None:
            raise StewartError("follow_up applies only to a valid captured needs-evidence or reframe declaration",
                               reason="follow_up_unexpected", retained=[str(collection_dir)])
        validated["follow_up"] = None
    required = {gap["id"]: gap["description"] for gap in custody_gaps(receipt)}
    given = response.get("custody_gaps", {})
    if not isinstance(given, dict) or not all(isinstance(k, str) for k in given):
        raise StewartError("custody_gaps must map gap IDs to dispositions", reason="response_schema")
    missing = sorted(set(required) - set(given))
    unknown = sorted(set(given) - set(required))
    if missing or unknown:
        detail = []
        if missing:
            detail.append("undispositioned: " + ", ".join(missing))
        if unknown:
            detail.append("not a gap of this collection: " + ", ".join(unknown))
        raise StewartError("custody gaps must each have a disposition; " + "; ".join(detail), reason="custody_gaps")
    for gap_id, disposition in given.items():
        _text(disposition, f"disposition of {gap_id}")
    validated["custody_gaps"] = {gap_id: given[gap_id] for gap_id in sorted(given)}
    reviewed = response.get("support_reviewed", [])
    if not isinstance(reviewed, list):
        raise StewartError("support_reviewed must be a list of captured paths", reason="response_schema")
    captured_files = {
        item["path"]: item for item in receipt.get("checkout", {}).get("files", []) if item.get("kind") == "file"
    }
    for rel in reviewed:
        relative(rel)
        if rel not in captured_files:
            raise StewartError(
                f"support_reviewed names a path the collection did not capture as a regular file: {rel}",
                reason="support_unavailable",
            )
    validated["support_reviewed"] = sorted(set(reviewed))
    if response.get("applicability") is not None:
        validated["applicability"] = _text(response["applicability"], "applicability")
    return validated


def _load_triage(session: Path, ident: str, name: str) -> tuple[dict, str]:
    location = contained(session, f"triage/{name}.json")
    record, digest = capture_receipt(location, what="triage record")
    if record.get("schema_version") != TRIAGE_SCHEMA or record.get("audit_id") != ident:
        raise StewartError(
            f"triage {name} has an unsupported schema or belongs to another audit", reason="triage_schema",
        )
    return record, digest


def bound_disposition(session: Path, ident: str, name: str, workspace: str, *,
                      session_record: dict) -> tuple[dict, str, Path, dict]:
    """Validate one disposition's evidence for status, retention and resume alike.

    Digests belong to the bytes parsed through one descriptor, never a second
    path read. A changed receipt or captured report cannot inherit a review.
    Cancellation still needs a fresh disposition of the available evidence.
    """
    record_name(name, what="triage")
    disposition, digest = _load_triage(session, ident, name)
    directory, receipt, collection_digest = load_collection(session, ident, disposition.get("collection"), session_record=session_record)
    if disposition.get("workspace") != workspace or receipt.get("workspace") != workspace:
        raise StewartError("triage or collection belongs to another workspace", reason="binding_mismatch")
    _require_collection_binding(disposition, directory, collection_digest, reason="binding_mismatch")
    # Recheck the response's report and gap bindings; stale report bytes matter
    # even when the collection receipt itself has not changed.
    validate_response(disposition.get("response"), receipt, directory, collection_sha256=collection_digest,
                      session_record=session_record)
    response = disposition["response"]
    if any(disposition.get(key) != response.get(key) for key in ("report_sha256", "report_gap", "decision", "follow_up")):
        raise StewartError("triage summary contradicts its response", reason="binding_mismatch")
    return disposition, digest, directory, receipt


def triage(ws: Workspace, ident: str, *, collection: str, response: dict, actor: str, lifetime: str | None = None,
           request_key: str | None = None) -> dict:
    """Record one maintainer response bound to one named collection.

    The request binding carries the response's canonical digest, so a retry
    with different judgments under the same key is refused.
    """
    from stewart.request_keys import input_digest, keyed
    inputs = {"collection": collection, "response_sha256": input_digest(response), "actor": actor}
    return keyed(ws, ident, "triage", inputs, request_key,
                 lambda plan: _triage(ws, ident, collection, response, actor, lifetime, plan), lifetime=lifetime,
                 outputs=lambda result: [output(Path(result["path"]), "triage", ws, ident, result["session_uuid"],
                                                name=result["triage"])])


def _triage(ws: Workspace, ident: str, collection: str, response: dict, actor: str, lifetime: str | None,
            plan) -> dict:
    session, session_record = mutable_session(ws, ident, lifetime=lifetime)
    name = record_name(collection, what="collection")
    directory, receipt, collection_digest = load_collection(session, ident, name, session_record=session_record)
    if not isinstance(actor, str) or not actor.strip():
        raise StewartError("a triage needs an attributed actor", reason="actor_required")
    if receipt.get("workspace") != ws.rel:
        raise StewartError("collection belongs to another workspace", reason="collection_schema")
    validated = validate_response(response, receipt, directory, collection_sha256=collection_digest,
                                  session_record=session_record)
    triage_name = stamp()
    record = {
        "schema_version": TRIAGE_SCHEMA,
        "name": triage_name,
        "recorded_at": now().isoformat(),
        "audit_id": ident,
        "workspace": ws.rel,
        "actor": actor,
        "collection": name,
        "collection_sha256": collection_digest,
        "report_sha256": validated["report_sha256"],
        "report_gap": validated["report_gap"],
        "custody_gaps_required": [gap["id"] for gap in custody_gaps(receipt)],
        "response": validated,
        "decision": validated["decision"],
        "follow_up": validated["follow_up"],
        "counts": {bucket: len(validated[bucket]) for bucket in ("accepted", "rejected", "unresolved")},
        "stewart": tool_identity(),
    }
    location = session / "triage" / f"{triage_name}.json"
    plan([{"kind": "triage", "name": triage_name, "path": str(location),
           "audit": {"workspace": ws.rel, "slug": ws.slug, "audit_id": ident},
           "lifetime": session_record["session_uuid"]}])
    (session / "triage").mkdir(mode=0o700, exist_ok=True)
    write_receipt(location, record)
    return {"audit_id": ident, "session_uuid": session_record["session_uuid"], "triage": triage_name,
            "triage_sha256": read_regular(location)[0].get("sha256"), "path": str(location), "collection": name,
            "record": record, "mode": session_record["mode"]}


def retain(ws: Workspace, ident: str, *, triage: str, report: bool = False,
           support: Sequence[str] = (), lifetime: str | None = None, request_key: str | None = None) -> dict:
    """Publish reviewed bytes from the triaged collection into the maintainer checkout.

    Sources are the immutable capture; every byte is re-hashed against the
    receipt and the triage binding before anything is written, and every
    destination is created exclusively. This neither stages nor commits. The
    published files are recorded as a retained resource beside the retention
    record, so a retiring manager worktree accounts for them.
    """
    from stewart.request_keys import keyed
    inputs = {"triage": triage, "report": bool(report), "support": sorted(support)}
    return keyed(ws, ident, "retain", inputs, request_key,
                 lambda plan: _retain(ws, ident, triage, report, support, lifetime), lifetime=lifetime,
                 outputs=lambda result: [output(Path(result["path"]), "retention", ws, ident, result["session_uuid"],
                                                name=result["retention"]),
                                         *({"kind": "published", "path": item["path"], "sha256": item["sha256"]}
                                           for item in result["published"])])


def _retain(ws: Workspace, ident: str, triage: str, report: bool, support: Sequence[str],
            lifetime: str | None) -> dict:
    from stewart.holdings import record_output
    session, record = mutable_session(ws, ident, lifetime=lifetime)
    triage_name = record_name(triage, what="triage")
    disposition, triage_digest, directory, receipt = bound_disposition(session, ident, triage_name, ws.rel,
                                                                    session_record=record)
    if not report and not support:
        raise StewartError("name --report and/or --support paths to retain", reason="retain_nothing")
    planned: list[tuple[Path, bytes, str, str]] = []
    if report and (receipt.get("report_status") != "present" or disposition.get("report_sha256") is None):
        raise StewartError("the triaged collection captured no nonempty report to retain", reason="report_unavailable")
    reviewed = set(disposition["response"].get("support_reviewed", []))
    for rel in support:
        relative(rel)
        if rel not in reviewed:
            raise StewartError(f"support artifact was not reviewed in triage {triage_name}: {rel}",
                               reason="support_unreviewed")
    selections = (["REPORT.md"] if report else []) + [f"files.tar:{rel}" for rel in support]
    payloads = collection_files(directory, receipt, selections)
    for selector, data in payloads.items():
        rel = record["assignment"]["report_path"] if selector == "REPORT.md" else selector[len("files.tar:"):]
        planned.append((contained(ws.repo, rel), data, selector, _hash.sha256_bytes(data)))
    for destination, _, _, _ in planned:
        if destination.exists() or destination.is_symlink():
            raise StewartError(
                f"destination already exists and is never overwritten: {destination}", reason="destination_exists",
            )
    published = []

    def publish() -> list[dict]:
        for destination, data, source, digest in planned:
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also refuses dangling links and repeat publication.
            with destination.open("xb") as stream:
                stream.write(data)
            published.append({"path": str(destination), "sha256": digest, "source": source})
        return published

    retention_name = stamp()
    _, rid = record_output(ws, ident, kind="retained", actor=None,
                           identity_for=lambda files: {"files": [{"path": item["path"], "sha256": item["sha256"]}
                                                                 for item in files], "checkout": str(ws.repo)},
                           perform=publish,
                           plan_outputs=[{"kind": "published", "path": str(destination), "sha256": digest}
                                         for destination, _, _, digest in planned]
                           + [{"kind": "retention", "name": retention_name,
                               "path": str(session / "retention" / f"{retention_name}.json"),
                               "audit": {"workspace": ws.rel, "slug": ws.slug, "audit_id": ident},
                               "lifetime": record["session_uuid"]}])
    retention = {
        "schema_version": RETENTION_SCHEMA,
        "name": retention_name,
        "recorded_at": now().isoformat(),
        "audit_id": ident,
        "workspace": ws.rel,
        "triage": triage_name,
        "triage_sha256": triage_digest,
        "collection": disposition["collection"],
        "published": published,
        "resource": rid,
        "staged_or_committed": False,
        "stewart": tool_identity(),
    }
    (session / "retention").mkdir(mode=0o700, exist_ok=True)
    location = session / "retention" / f"{retention_name}.json"
    write_receipt(location, retention)
    return {"audit_id": ident, "session_uuid": record["session_uuid"], "retention": retention_name,
            "path": str(location), "published": published, "resource": rid}


def resume(ws: Workspace, ident: str, *, triage: str, reason: str, lifetime: str | None = None,
           request_key: str | None = None) -> dict:
    """Record the release of a paused hold, bound to a triage and its evidence."""
    from stewart.request_keys import keyed
    return keyed(ws, ident, "resume", {"triage": triage, "reason": reason}, request_key,
                 lambda plan: _resume(ws, ident, triage, reason, lifetime, plan), lifetime=lifetime,
                 outputs=lambda result: [output(Path(result["path"]), "resume", ws, ident, result["session_uuid"])])


def _resume(ws: Workspace, ident: str, triage: str, reason: str, lifetime: str | None, plan) -> dict:
    session, record = mutable_session(ws, ident, lifetime=lifetime)
    if record["mode"] != "paused":
        raise StewartError(
            "snapshot audits have no writer pause to resume; collect and triage the report", reason="no_hold",
        )
    if not isinstance(reason, str) or not reason.strip():
        raise StewartError("resume needs a triage or cancellation reason", reason="reason_required")
    triage_name = record_name(triage, what="triage")
    disposition, triage_digest, directory, receipt = bound_disposition(session, ident, triage_name, ws.rel,
                                                                    session_record=record)
    resumed = session / "RESUMED.json"
    if resumed.exists():
        raise StewartError(
            "a resume decision is already recorded for this session", reason="already_resumed",
            retained=[str(resumed)],
        )
    payload = {
        "schema_version": RESUME_SCHEMA,
        "resumed_at": now().isoformat(),
        "audit_id": ident,
        "workspace": ws.rel,
        "reason": reason,
        "triage": triage_name,
        "triage_sha256": triage_digest,
        "collection": disposition["collection"],
        "collection_sha256": disposition["collection_sha256"],
        "collection_errors": receipt.get("errors", []),
        "decision": disposition["decision"],
        "worktree_retained": True,
        "process_control": "none; the maintainer tells the writers",
        "stewart": tool_identity(),
    }
    plan([{"kind": "resume", "path": str(resumed), "audit": {"workspace": ws.rel, "slug": ws.slug, "audit_id": ident},
           "lifetime": record["session_uuid"]}])
    write_receipt(resumed, payload)
    return {"audit_id": ident, "session_uuid": record["session_uuid"], "path": str(resumed), "record": payload}
