"""Retire a finished or abandoned audit: one closing record, then removal of what the session created.

While an audit is live its records are exclusive and preserved, failures
included. ``close`` is the only operation that deletes, and it removes only
what the session's own record names: the session directory, the locked
checkout with its runtimes and experiment homes, the session's retention refs
and its role registry row. Before removing anything it writes ``CLOSING.json``
under ``<common>/stewart/closed/<slug>/<audit-id>/<uuid>/``: identity, the
manager's acknowledgment, the observations the close rests on, the auditor's
attributed claims and the removal inventory. ``CLOSED.json`` then records what
each removal did. A rerun after interruption works only from the recorded
inventory, never a wider one. Stewart never removes closing records.

A concluded close needs records that verify, a triage bound to a complete
collection, no outstanding paused hold, no unresolved attempt and a checkout
unchanged since the triaged collection. An abandon is allowed in any state. It
releases the audit ID only when no chain of evidence can exist under it: the
preparation failed before writing any handoff, nothing was launched, recorded
or collected, and the checkout holds only preparation's own footprint.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat

from stewart import _util as _hash
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_UNVERIFIED, StewartError, read_regular
from stewart._git import git, git_text
from stewart._json import loads_control
from stewart.workspace import Workspace, contained

CLOSING_SCHEMA = "stewart.closing/1"
CLOSED_SCHEMA = "stewart.closed/1"
MODES = ("concluded", "abandoned")
_CLOSING_FIELDS = {"schema", "identity", "acknowledged", "observed", "attributed", "removal"}
_BASIS_FIELDS = {"failure_receipt", "private_handoff", "public_handoff", "launch_records", "exit_record",
                 "collections", "checkout"}


def closed_location(common: str, ws: Workspace, ident: str) -> Path:
    from stewart._repository import CLOSED
    return contained(Path(common), f"{CLOSED}/{ws.slug}/{ident}")


def releasable(basis: object) -> bool:
    """The single rule that frees an abandoned audit ID; every uncertainty keeps it reserved.

    ``close`` applies it to its observations and ``init``/``prepare`` reapply
    it to the recorded basis, so close and reuse cannot disagree.
    """
    if not isinstance(basis, dict) or set(basis) != _BASIS_FIELDS:
        return False
    failure, checkout = basis["failure_receipt"], basis["checkout"]
    return (isinstance(failure, dict) and failure.get("kind") == "file"
            and isinstance(failure.get("sha256"), str) and failure.get("stage") != "handoff"
            and basis["private_handoff"] == "missing" and basis["public_handoff"] == "missing"
            and basis["launch_records"] == 0 and basis["exit_record"] == "missing" and basis["collections"] == 0
            and isinstance(checkout, dict) and checkout.get("observed") is True and checkout.get("extra") == [])


def _facts(session: Path, record: dict | None, rows: list[dict], repo: Path) -> dict:
    """What close needs, from the session record or, when it is unreadable, the registry row.

    The record names everything in a healthy session. A row names the session
    path, its UUID and its worktree, so even an unreadable record can be
    retired; the checkout directory is the worktree's parent by the session
    layout. Retention refs are enumerated from Git under the session's UUID.
    """
    record = record if isinstance(record, dict) else {}
    row = rows[0] if rows else {}
    uuid = record.get("session_uuid") or row.get("session_uuid") or row.get("role_uuid")
    worktree = record.get("worktree") or row.get("worktree")
    if not isinstance(uuid, str) or not isinstance(worktree, str):
        raise StewartError("no session record or registry row identifies this session", reason="close_unidentified",
                           code=EXIT_UNVERIFIED, retained=[str(session)],
                           next_steps=["preserve the session directory; it names no worktree Stewart can retire"])
    runtime = (record.get("runtime") or {}).get("root") if isinstance(record.get("runtime"), dict) else None
    refs = []
    listed = git(repo, "for-each-ref", "--format=%(refname) %(objectname)", f"refs/stewart/sessions/{uuid}/", check=False)
    for line in listed.stdout.decode("utf-8", "replace").splitlines():
        name, _, commit = line.partition(" ")
        refs.append({"ref": name, "commit": commit})
    assignment = record.get("assignment") if isinstance(record.get("assignment"), dict) else {}
    handoff = record.get("handoff") if isinstance(record.get("handoff"), dict) else {}
    return {"session_uuid": uuid, "worktree": worktree, "audit_dir": record.get("audit_dir") or str(Path(worktree).parent),
            "runtime": runtime or str(Path(worktree).parent / "runtime"), "prompt_commit": record.get("prompt_commit"),
            "supplemental": [item for item in assignment.get("supplemental_inputs", []) if isinstance(item, dict)],
            "handoff": handoff.get("path"), "refs": refs, "record": record}


def _kind(location: Path) -> str:
    """The observed kind of one path, without following or reading it beyond a digest."""
    from stewart._bootstrap import capture_regular
    return capture_regular(location)["kind"]


def _count(directory: Path) -> int:
    return len(os.listdir(directory)) if directory.is_dir() and not directory.is_symlink() else 0


def _observe_checkout(facts: dict) -> dict:
    """What the checkout holds now beyond preparation's own footprint.

    Preparation leaves the committed tree, pinned supplemental copies, empty
    output directories and the issued handoff. Anything else Git reports, any
    special or unreadable entry, and a moved HEAD are extra. Failure to observe
    is recorded as such and never counts as an empty checkout.
    """
    import subprocess
    from stewart._bootstrap import SPECIAL_KINDS
    from stewart.collect import checkout_state, inventory
    worktree = Path(facts["worktree"])
    if not worktree.exists() and not worktree.is_symlink():
        return {"observed": True, "exists": False, "extra": [], "files": []}
    if facts["prompt_commit"] is None:
        return {"observed": False, "exists": True, "extra": [], "files": [],
                "error": "the session record names no prompt commit to compare against"}
    try:
        state, _ = checkout_state(worktree, facts["prompt_commit"])
        entries = inventory(worktree)["entries"]
    except (StewartError, OSError, subprocess.TimeoutExpired) as exc:
        return {"observed": False, "exists": True, "extra": [], "files": [], "error": str(exc)}
    supplied = {item.get("path"): item.get("sha256") for item in facts["supplemental"]}
    handoff = facts["handoff"]
    files = [{"path": item["path"], "kind": item["kind"], "sha256": item.get("sha256")} for item in state["files"]
             if item["path"] != handoff]
    extra = {item["path"] for item in files if not (item["kind"] == "file" and supplied.get(item["path"]) == item["sha256"])}
    extra.update(entry["path"] for entry in entries if entry["kind"] in SPECIAL_KINDS or entry["kind"] == "unreadable")
    if state["head"] != facts["prompt_commit"]:
        extra.add(f"HEAD at {state['head']}")
    return {"observed": True, "exists": True, "extra": sorted(extra), "files": files}


def _release_basis(session: Path, facts: dict, checkout: dict) -> dict:
    """Observations the release rule reads; recorded in CLOSING.json and reapplied at reuse."""
    failure_path = session / "PREPARE-ERROR.json"
    info, data = read_regular(failure_path)
    failure = {"kind": info["kind"], "sha256": info.get("sha256"), "stage": None}
    if data is not None:
        try:
            failure["stage"] = loads_control(data).get("stage")
        except (ValueError, RecursionError, AttributeError):
            failure["kind"] = "invalid"
    return {"failure_receipt": failure,
            "private_handoff": _kind(session / "LAUNCH.md"),
            # Without a recorded handoff path the public copy cannot be ruled out.
            "public_handoff": _kind(Path(facts["worktree"]) / facts["handoff"]) if facts["handoff"] else "unknown",
            "launch_records": _count(session / "launches"),
            "exit_record": _kind(session / "HARNESS-EXIT.txt"),
            "collections": _count(session / "collections"),
            "checkout": {"observed": checkout["observed"], "extra": checkout["extra"]}}


def _recorded_members(session: Path, facts: dict) -> list[str]:
    """Checkout-directory members the session's records name: runtimes and experiment homes."""
    from stewart.session import list_records, read_receipt
    members = [facts["runtime"]]
    for entry in list_records(session / "runtime-recoveries"):
        for name in ("RECOVERY.json", "STARTED.json"):
            try:
                members.append(read_receipt(entry / name, what="runtime recovery")["runtime"]["identity"]["root"])
                break
            except (StewartError, KeyError, TypeError):
                continue
    for entry in list_records(session / "releases", suffix=".json"):
        try:
            home = Path(read_receipt(entry, what="release record")["environment"]["HOME"])
        except (StewartError, KeyError, TypeError):
            continue
        members.append(str(home.parent))
    audit_dir = Path(facts["audit_dir"])
    return sorted({member for member in members if Path(member).is_relative_to(audit_dir) and Path(member) != audit_dir})


def _removal(session: Path, facts: dict, common: str) -> dict:
    from stewart._repository import _registry
    return {"worktree": facts["worktree"], "members": _recorded_members(session, facts),
            "checkout_dir": facts["audit_dir"], "refs": facts["refs"],
            "registry_row": str(_registry(common) / f"{facts['session_uuid']}.json"), "session": str(session)}


def _remove_tree(path: Path) -> str:
    """Remove a recorded directory without following links; a link is removed, never followed."""
    if path.is_symlink():
        path.unlink()
        return "removed link"
    if not path.exists():
        return "absent"
    for root, directories, _ in os.walk(path, followlinks=False):
        for name in directories:
            child = Path(root) / name
            if not child.is_symlink():
                child.chmod(stat.S_IRWXU)
    path.chmod(stat.S_IRWXU)
    shutil.rmtree(path)
    return "removed"


def _remove(removal: dict, repo: Path) -> tuple[list[dict], list[str]]:
    """Remove the recorded inventory, auditor-facing items first and the session last.

    Removal stops at the first failure, so the session's own records go only
    after everything else is gone; a rerun resumes from CLOSING.json. Entries
    of the checkout directory that no record names are left and reported.
    """
    results: list[dict] = []
    worktree = Path(removal["worktree"])
    checkout_dir = Path(removal["checkout_dir"])

    def remove_worktree() -> str:
        listed = git_text(repo, "worktree", "list", "--porcelain").splitlines()
        if f"worktree {removal['worktree']}" not in listed:
            # No longer a Git checkout; the recorded directory is still the session's.
            return _remove_tree(worktree)
        # Git removes a registered checkout whose directory is already gone.
        git(repo, "worktree", "unlock", str(worktree), check=False)
        git(repo, "worktree", "remove", "--force", "--force", str(worktree))
        return "removed"

    def remove_empty(directory: Path) -> str:
        if not directory.is_dir() or directory.is_symlink():
            return "absent"
        if os.listdir(directory):
            return "kept: not empty"
        directory.rmdir()
        return "removed"

    def remove_ref(entry: dict) -> str:
        if git(repo, "rev-parse", "--verify", "--quiet", entry["ref"], check=False).returncode:
            return "absent"
        git(repo, "update-ref", "-d", entry["ref"], entry["commit"])
        return "removed"

    def remove_row() -> str:
        row = Path(removal["registry_row"])
        if not row.exists() and not row.is_symlink():
            return "absent"
        row.unlink()
        return "removed"

    steps = [(removal["worktree"], "worktree", remove_worktree)]
    steps += [(member, "checkout member", lambda member=member: _remove_tree(Path(member)))
              for member in removal["members"]]
    steps += [(str(directory), "checkout directory", lambda directory=directory: remove_empty(directory))
              for directory in (checkout_dir / "attempts", checkout_dir)]
    steps += [(entry["ref"], "retention ref", lambda entry=entry: remove_ref(entry)) for entry in removal["refs"]]
    steps += [(removal["registry_row"], "registry row", remove_row),
              (removal["session"], "session", lambda: _remove_tree(Path(removal["session"])))]
    for item, kind, action in steps:
        try:
            results.append({"item": item, "kind": kind, "outcome": action()})
        except (OSError, StewartError) as exc:
            results.append({"item": item, "kind": kind, "outcome": "failed", "detail": str(exc)})
            break
    recorded = {removal["worktree"], *removal["members"], str(checkout_dir / "attempts")}
    leftovers = []
    for directory in (checkout_dir, checkout_dir / "attempts"):
        if directory.is_dir() and not directory.is_symlink():
            leftovers += [str(directory / name) for name in os.listdir(directory) if str(directory / name) not in recorded]
    return results, sorted(leftovers)


def closing_entries(common: str, ws: Workspace, ident: str) -> list[dict]:
    """Every closing record for an audit ID, oldest first, with its completion and validity."""
    folder = closed_location(common, ws, ident)
    if not folder.is_dir() or folder.is_symlink():
        return []
    from stewart.session import capture_receipt
    entries = []
    for directory in sorted(folder.iterdir()):
        entry: dict = {"session_uuid": directory.name, "path": str(directory),
                       "attempts": len(list(directory.glob("CLOSE-ATTEMPT-*.json")))}
        try:
            closing, digest = _read(directory / "CLOSING.json")
            entry.update(closing=closing, closing_sha256=digest, mode=closing["acknowledged"]["mode"],
                         complete=False, closed=None,
                         released=closing["acknowledged"]["mode"] == "abandoned"
                         and releasable(closing["observed"].get("release_basis")))
            done = directory / "CLOSED.json"
            if done.exists() or done.is_symlink():
                closed, _ = capture_receipt(done, what="closed record")
                if closed.get("schema") != CLOSED_SCHEMA or closed.get("closing_sha256") != digest:
                    raise StewartError(f"closed record does not bind its closing record: {done}",
                                       reason="closing_record_invalid", retained=[str(done)])
                entry.update(complete=True, closed=closed)
        except StewartError as exc:
            entry.update(problem=exc.to_json(), complete=False, released=False)
        entries.append(entry)
    return entries


def close_summary(entry: dict) -> dict:
    """One closing record as status shows it; leftovers are observed now, at read time."""
    summary = {"session_uuid": entry["session_uuid"], "path": entry["path"], "complete": entry["complete"],
               "released": entry["released"], "attempts": entry["attempts"]}
    if "problem" in entry:
        return {**summary, "problem": entry["problem"]}
    closing = entry["closing"]
    identity, acknowledged = closing["identity"], closing["acknowledged"]
    observed, attributed = closing["observed"], closing["attributed"]
    recorded = (entry["closed"] or {}).get("leftovers") or []
    return {**summary, "mode": acknowledged["mode"], "actor": acknowledged["actor"], "reason": acknowledged["reason"],
            "closed_at": identity.get("closed_at"), "prompt_commit": identity.get("prompt_commit"),
            "session": closing["removal"].get("session"),
            "decision": {"value": attributed.get("decision"), "attributed_to": attributed.get("decision_actor")},
            "auditor_completion": {"value": attributed.get("auditor_completion"), "attributed_to": "auditor"},
            "retained": observed.get("retained") or [], "discarded": observed.get("discarded") or [],
            "leftovers": [item for item in recorded if os.path.lexists(item)]}


def _read(location: Path) -> tuple[dict, str]:
    from stewart.session import capture_receipt
    value, digest = capture_receipt(location, what="closing record")
    if (value.get("schema") != CLOSING_SCHEMA or set(value) != _CLOSING_FIELDS
            or value["acknowledged"].get("mode") not in MODES):
        raise StewartError(f"closing record has an unsupported shape: {location}", reason="closing_record_invalid",
                           retained=[str(location)])
    return value, digest


def require_fresh_audit_id(common: str, ws: Workspace, ident: str) -> None:
    """Refuse an audit ID that a closing record reserves; fail closed on any doubt.

    A released abandon frees the ID. A concluded close, an abandon whose basis
    does not release it, an incomplete close and an unreadable or unsupported
    closing record all keep it reserved.
    """
    for entry in closing_entries(common, ws, ident):
        if "problem" in entry:
            raise StewartError(f"a closing record for {ident} cannot be read: {entry['problem']['message']}",
                               reason="closing_record_invalid", retained=[entry["path"]], code=EXIT_UNVERIFIED,
                               next_steps=["preserve the closing record; prepare the assignment under a fresh audit ID"])
        if not entry["complete"]:
            raise StewartError(f"the close of audit {ident} is incomplete", reason="close_incomplete",
                               retained=[entry["path"]],
                               next_steps=[f"rerun close --audit-id {ident}; it finishes from the recorded inventory"])
        if not entry["released"]:
            raise StewartError(f"audit ID {ident} is reserved by its closing record ({entry['mode']})",
                               reason="audit_id_reserved", retained=[entry["path"]],
                               next_steps=["choose a fresh audit ID; a closed audit's ID names its evidence"])


def _uncollected(checkout: dict, session: Path) -> list[dict]:
    """Checkout files a collection has not captured: preserved nowhere if the checkout goes."""
    from stewart.session import list_records, read_receipt
    captured: set[tuple[str, str | None]] = set()
    for entry in list_records(session / "collections"):
        try:
            receipt = read_receipt(entry / "collection.json", what="collection receipt")
        except StewartError:
            continue
        if receipt.get("archive_sha256"):
            captured.update((item.get("path"), item.get("sha256")) for item in receipt.get("checkout", {}).get("files", []))
    return [item for item in checkout["files"]
            if item["path"] in checkout["extra"] and (item["path"], item["sha256"]) not in captured]


def close(ws: Workspace, ident: str, *, actor: str, abandon: bool = False, reason: str | None = None,
          discard_uncollected: bool = False) -> dict:
    """Retire one audit: write CLOSING.json, remove the recorded inventory, write CLOSED.json.

    A concluded close refuses with 3 wherever status reports records that do
    not verify. An abandon accepts any state, including unreadable records,
    and records why. A previously interrupted close resumes from its own
    recorded inventory.
    """
    from stewart._repository import _role_records, maintainer, private_storage, session_location
    from stewart.session import capture_receipt, load_session, now, owner_refusal, tool_identity, write_receipt
    if not isinstance(actor, str) or not actor.strip():
        raise StewartError("a close needs an attributed actor", reason="actor_required")
    if abandon and (not isinstance(reason, str) or not reason.strip()):
        raise StewartError("an abandon needs --reason naming why the audit is abandoned", reason="reason_required",
                           next_steps=["rerun with --abandon --reason TEXT"])
    if not abandon and (reason is not None or discard_uncollected):
        raise StewartError("--reason and --discard-uncollected apply only with --abandon", reason="usage")
    common = maintainer(ws.repo)["common_dir"]
    for entry in closing_entries(common, ws, ident):
        if not entry["complete"] and "problem" not in entry:
            return _finish(ws.repo, Path(entry["path"]), entry["closing"], entry["closing_sha256"], resumed=True)
    session = session_location(common, ws, ident)
    rows = [row for row in _role_records(common) if row["session"] == str(session)]
    # A session whose directory is gone can still be abandoned through the
    # registry row that names its checkout and refs.
    if not session.is_dir() and not (abandon and rows):
        raise StewartError(f"no live session for audit {ident} in workspace {ws.rel}", reason="session_missing",
                           next_steps=["status without --audit-id lists this workspace's sessions and closed audits"])
    try:
        record, session_digest = capture_receipt(session / "session.json", what="session record")
    except StewartError:
        if not abandon:
            raise
        record, session_digest = None, None
    owner = record.get("repo") if isinstance(record, dict) else None
    if owner not in (None, str(ws.repo)):
        refusal = owner_refusal(owner, session, ident)
        # Any maintainer of the repository may abandon a session whose own
        # maintainer checkout is gone; everything else goes through its owner.
        if not (abandon and refusal.reason == "session_owner_missing"):
            raise refusal
    if not abandon:
        load_session(ws, ident)
    facts = _facts(session, record, rows, ws.repo)
    view = _status_view(ws, ident)
    observed: dict = {"triage": None, "collection": None, "retained": [], "release_basis": None,
                      "discarded": [], "checkout": None, "stage": None, "problems": [],
                      "coordination": {"mode": facts["record"].get("mode"), "hold_resumed": None}}
    attributed: dict = {"decision": None, "decision_actor": None, "auditor_completion": None,
                        "auditor_report_kind": None,
                        "note": "attributed claims recorded as made; none is a verdict on the audit"}
    if view is not None:
        attributed.update(auditor_completion=view["auditor_reported"]["completion"]["value"],
                          auditor_report_kind=view["auditor_reported"]["report_kind"]["value"])
        observed["retained"] = [item for r in view["retentions"] if not r["problems"] for item in r.get("published") or []]
        observed["stage"] = view["preparation"].get("state")
        observed["problems"] = sorted({item["reason"] for item in view["attention"]})
        observed["coordination"]["hold_resumed"] = view["coordination"].get("resumed") is not None
    if abandon:
        checkout = _observe_checkout(facts)
        uncollected = _uncollected(checkout, session) if checkout["observed"] else []
        if uncollected and not discard_uncollected:
            raise StewartError("the checkout holds changes no collection captured: "
                               + ", ".join(item["path"] for item in uncollected[:10]),
                               reason="uncollected_changes", retained=[facts["worktree"]],
                               next_steps=["collect first to preserve them, or rerun with --discard-uncollected"])
        observed["discarded"] = [{"path": item["path"], "sha256": item["sha256"]} for item in uncollected]
        observed["release_basis"] = _release_basis(session, facts, checkout)
        observed["checkout"] = {"observed": checkout["observed"], "exists": checkout.get("exists"),
                                "extra": checkout["extra"], "error": checkout.get("error")}
    else:
        concluded = _concluded(view, facts, session)
        disposition = concluded.pop("disposition")
        observed.update(concluded)
        attributed.update(decision=disposition["decision"], decision_actor=disposition["actor"])
    closing = {
        "schema": CLOSING_SCHEMA,
        "identity": {"session_uuid": facts["session_uuid"], "workspace": ws.rel, "slug": ws.slug, "audit_id": ident,
                     "prompt_commit": facts["prompt_commit"], "target_commit": facts["record"].get("target_commit"),
                     "base_commit": (facts["record"].get("assignment") or {}).get("base_commit"),
                     "session_sha256": session_digest, "prepared_at": facts["record"].get("prepared_at"),
                     "closed_at": now().isoformat(), "stewart": tool_identity()},
        "acknowledged": {"actor": actor, "mode": "abandoned" if abandon else "concluded", "reason": reason},
        "observed": observed,
        "attributed": attributed,
        "removal": _removal(session, facts, common),
    }
    folder = closed_location(common, ws, ident)
    parent = private_storage(common)
    for part in folder.relative_to(parent).parts:
        parent = parent / part
        if parent.is_symlink():
            raise StewartError(f"closed-record storage cannot traverse a link: {parent}", reason="path_symlink",
                               retained=[str(parent)])
        parent.mkdir(mode=0o700, exist_ok=True)
    directory = folder / facts["session_uuid"]
    try:
        directory.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError:
        raise StewartError(f"a closing record already exists for this session: {directory}",
                           reason="destination_exists", retained=[str(directory)],
                           next_steps=["status shows the existing close; rerun close to finish an incomplete one"]) from None
    write_receipt(directory / "CLOSING.json", closing)
    _, closing_digest = capture_receipt(directory / "CLOSING.json", what="closing record")
    return _finish(ws.repo, directory, closing, closing_digest, resumed=False)


def _status_view(ws: Workspace, ident: str) -> dict | None:
    from stewart.status import status
    try:
        return status(ws, ident)
    except StewartError:
        return None


def _concluded(view: dict | None, facts: dict, session: Path) -> dict:
    """The preconditions of a concluded close and the observations it rests on."""
    from stewart.collect import inventory
    from stewart.session import capture_receipt
    if view is None:
        raise StewartError("status cannot read this session", reason="close_unverified", code=EXIT_UNVERIFIED,
                           next_steps=["close --abandon --reason TEXT"])
    unverified = [item for item in view["attention"] if item["code"] == EXIT_UNVERIFIED]
    if unverified:
        raise StewartError("a concluded close needs records that verify: "
                           + "; ".join(f"{item['source']}: {item['reason']}" for item in unverified[:5]),
                           reason="close_unverified", code=EXIT_UNVERIFIED, retained=[str(session)],
                           next_steps=["inspect the problems status lists, or close --abandon --reason TEXT"])
    complete = {c["name"]: c for c in view["collections"] if c["complete"]}
    triaged = [d for d in view["dispositions"] if not d["problems"] and d.get("collection") in complete]
    if not triaged:
        raise StewartError("a concluded close needs a triage bound to a complete collection",
                           reason="close_not_concluded",
                           next_steps=["triage a complete collection, or close --abandon --reason TEXT"])
    if view["coordination"].get("mode") == "paused" and view["coordination"].get("resumed") is None:
        raise StewartError("the paused hold is still outstanding", reason="close_hold_outstanding",
                           next_steps=["resume the hold with its triage and tell the writers, then close"])
    if any(problem["reason"] == "attempt_unresolved" for item in view["attempts"] for problem in item["problems"]):
        raise StewartError("an experiment attempt is unresolved", reason="close_attempt_unresolved",
                           next_steps=["close --abandon --reason TEXT keeps the unresolved attempt's record"])
    disposition = triaged[-1]
    collection = complete[disposition["collection"]]
    receipt, collection_digest = capture_receipt(Path(collection["path"]) / "collection.json", what="collection receipt")
    _, triage_digest = capture_receipt(Path(disposition["path"]), what="triage record")
    worktree = Path(facts["worktree"])
    unchanged = None
    if worktree.is_dir():
        current = _hash.sha256_bytes(_hash.receipt_json_bytes(inventory(worktree)))
        unchanged = current == (receipt.get("inventory") or {}).get("sha256")
        if not unchanged:
            raise StewartError("the checkout changed since the triaged collection", reason="checkout_changed",
                               retained=[str(worktree)],
                               next_steps=["collect again and triage that collection, "
                                           "or close --abandon --reason TEXT --discard-uncollected"])
    return {"triage": {"name": disposition["name"], "sha256": triage_digest},
            "collection": {"name": collection["name"], "sha256": collection_digest},
            "checkout": {"exists": worktree.is_dir(), "unchanged_since_collection": unchanged},
            "disposition": disposition}


def _finish(repo: Path, directory: Path, closing: dict, closing_sha256: str, *, resumed: bool) -> dict:
    """Remove the recorded inventory; CLOSED.json only once every recorded item is gone."""
    from stewart.session import now, stamp, tool_identity, write_receipt
    results, leftovers = _remove(closing["removal"], repo)
    failed = [item for item in results if item["outcome"] == "failed"]
    document = {"schema": CLOSED_SCHEMA, "closing_sha256": closing_sha256, "recorded_at": now().isoformat(),
                "results": results, "leftovers": leftovers, "resumed": resumed, "stewart": tool_identity()}
    if failed:
        # A failed removal leaves the close incomplete: status says so and a
        # rerun finishes it from CLOSING.json. Each attempt keeps its record.
        write_receipt(directory / f"CLOSE-ATTEMPT-{stamp()}.json", document)
        closed = None
    else:
        write_receipt(directory / "CLOSED.json", document)
        closed = str(directory / "CLOSED.json")
    identity, acknowledged = closing["identity"], closing["acknowledged"]
    coordination = closing["observed"].get("coordination") or {}
    return {"audit_id": identity["audit_id"], "session_uuid": identity["session_uuid"], "mode": acknowledged["mode"],
            "closing": str(directory / "CLOSING.json"), "closed": closed, "resumed": resumed,
            # Stewart controls no writer process: a paused session closed
            # without resume still has writers waiting on a person.
            "hold_outstanding": coordination.get("mode") == "paused" and coordination.get("hold_resumed") is not True,
            "released": acknowledged["mode"] == "abandoned" and releasable(closing["observed"].get("release_basis")),
            "results": results, "leftovers": leftovers, "failed": failed,
            "exit_code": EXIT_ATTENTION if failed or leftovers else EXIT_OK}
