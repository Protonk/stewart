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

Removal never follows a link. A symbolic or moved ref, a link in place of a
recorded directory and a checkout registered elsewhere are kept and named as
leftovers, never resolved.

A concluded close needs records that verify, a triage bound to a complete
collection, no outstanding paused hold, no unresolved attempt and a checkout
unchanged since the triaged collection. An abandon is allowed in any state. It
releases the audit ID only when no chain of evidence can exist under it: the
preparation recorded its failure before writing any handoff, the session holds
nothing beyond preparation's own records, and the checkout holds only
preparation's footprint.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import uuid as _uuid

from stewart import _util as _hash
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_UNVERIFIED, StewartError, read_regular
from stewart._git import git, git_text
from stewart._json import loads_control
from stewart.workspace import Workspace, contained

CLOSING_SCHEMA = "stewart.closing/1"
CLOSED_SCHEMA = "stewart.closed/1"
MODES = ("concluded", "abandoned")
_CLOSING_FIELDS = {"schema", "identity", "acknowledged", "observed", "attributed", "removal"}
_REMOVAL_FIELDS = {"session_uuid", "worktree", "members", "checkout_dir", "refs", "registry_row", "session"}
_BASIS_FIELDS = {"failure_receipt", "private_handoff", "public_handoff", "session_entries", "checkout"}
#: What a session holds when preparation failed before writing any handoff:
#: its record, its failure receipt and the runtime records the runtime stage
#: writes. Any other entry is activity, or doubt, and keeps the ID reserved.
_SESSION_FOOTPRINT = frozenset({"session.json", "PREPARE-ERROR.json", "runtime-pristine", "runtime-prepared",
                                "RUNTIME-PREPARED.json"})


def closed_location(common: str, ws: Workspace, ident: str) -> Path:
    from stewart._repository import CLOSED
    return contained(Path(common), f"{CLOSED}/{ws.slug}/{ident}")


def releasable(basis: object) -> bool:
    """The single rule that frees an abandoned audit ID; every uncertainty keeps it reserved.

    ``close`` applies it to its observations and ``init``/``prepare`` reapply
    it to the recorded basis, so close and reuse cannot disagree.
    """
    from stewart.session import PREPARE_STAGES
    if not isinstance(basis, dict) or set(basis) != _BASIS_FIELDS:
        return False
    failure, checkout = basis["failure_receipt"], basis["checkout"]
    return (isinstance(failure, dict) and failure.get("kind") == "file"
            and isinstance(failure.get("sha256"), str) and failure.get("stage") in PREPARE_STAGES[:-1]
            and basis["private_handoff"] == "missing" and basis["public_handoff"] == "missing"
            and basis["session_entries"] == []
            and isinstance(checkout, dict) and checkout.get("observed") is True and checkout.get("extra") == [])


def _session_refs(repo: Path, uuid: str) -> list[dict]:
    """Every ref Git holds under a session's namespace, symbolic ones marked and never followed."""
    listed = git(repo, "for-each-ref", "--format=%(refname)%00%(objectname)%00%(symref)",
                 f"refs/stewart/sessions/{uuid}/", check=False)
    refs = []
    for line in listed.stdout.decode("utf-8", "replace").splitlines():
        name, commit, symref = (line.split("\0") + ["", ""])[:3]
        refs.append({"ref": name, "commit": commit, "symref": symref or None})
    return refs


def _facts(session: Path, record: dict | None, rows: list[dict], repo: Path) -> dict:
    """What close needs, from the session record or, when it is unreadable, the registry row.

    The record names everything in a healthy session, including the exact
    retention refs and their commits. A row names the session path, its UUID
    and its worktree, so even an unreadable record can be retired; the checkout
    directory is the worktree's parent by the session layout, and the refs are
    the non-symbolic ones Git holds under the UUID. With neither, only the
    session directory itself is known.
    """
    record = record if isinstance(record, dict) else {}
    row = rows[0] if rows else {}
    uuid = record.get("session_uuid") or row.get("session_uuid") or row.get("role_uuid")
    uuid = uuid if isinstance(uuid, str) else None
    worktree = record.get("worktree") or row.get("worktree")
    worktree = worktree if isinstance(worktree, str) else None
    retention = record.get("retention")
    if isinstance(retention, dict) and isinstance(retention.get("refs"), dict):
        refs = [{"ref": entry["ref"], "commit": entry["commit"]} for entry in retention["refs"].values()
                if isinstance(entry, dict) and isinstance(entry.get("ref"), str) and isinstance(entry.get("commit"), str)
                and uuid is not None and entry["ref"].startswith(f"refs/stewart/sessions/{uuid}/")]
    else:
        refs = [{"ref": entry["ref"], "commit": entry["commit"]}
                for entry in (_session_refs(repo, uuid) if uuid else []) if entry["symref"] is None]
    audit_dir = record.get("audit_dir") or (str(Path(worktree).parent) if worktree else None)
    runtime = record.get("runtime").get("root") if isinstance(record.get("runtime"), dict) else None
    assignment = record.get("assignment") if isinstance(record.get("assignment"), dict) else {}
    handoff = record.get("handoff") if isinstance(record.get("handoff"), dict) else {}
    return {"session_uuid": uuid, "worktree": worktree, "audit_dir": audit_dir,
            "runtime": runtime or (str(Path(audit_dir) / "runtime") if audit_dir else None),
            "prompt_commit": record.get("prompt_commit"), "assignment": assignment,
            "supplemental": [item for item in assignment.get("supplemental_inputs", []) if isinstance(item, dict)],
            "handoff": handoff.get("path"), "notes": None, "refs": refs, "record": record}


def _kind(location: Path) -> str:
    """The observed kind of one path, without following or reading it beyond a digest."""
    from stewart._bootstrap import capture_regular
    return capture_regular(location)["kind"]


def _ancestors(rel: str) -> set[str]:
    return {parent.as_posix() for parent in Path(rel).parents if parent.as_posix() != "."}


def _observe_checkout(facts: dict) -> dict:
    """What the checkout holds now beyond preparation's own footprint.

    Preparation leaves the committed tree, pinned supplemental copies, the
    report's parent and notes directories and the issued handoff. Anything
    else Git reports, any other directory, any special or unreadable entry and
    a moved HEAD are extra. Failure to observe is recorded as such and never
    counts as an empty checkout.
    """
    import subprocess
    from stewart._bootstrap import SPECIAL_KINDS
    from stewart.collect import checkout_state, inventory
    if facts["worktree"] is None:
        return {"observed": False, "exists": None, "extra": [], "files": [],
                "error": "no record names the session's checkout"}
    worktree = Path(facts["worktree"])
    if not os.path.lexists(worktree):
        return {"observed": True, "exists": False, "extra": [], "files": []}
    if worktree.is_symlink() or not worktree.is_dir():
        return {"observed": True, "exists": True, "extra": [f"{worktree} is not a real directory"], "files": []}
    prompt = facts["prompt_commit"]
    if prompt is None:
        return {"observed": False, "exists": True, "extra": [], "files": [],
                "error": "the session record names no prompt commit to compare against"}
    try:
        state, _ = checkout_state(worktree, prompt)
        entries = inventory(worktree)["entries"]
        tracked = set(os.fsdecode(git(worktree, "ls-tree", "-r", "-d", "--name-only", "-z", prompt).stdout).split("\0"))
    except (StewartError, OSError, subprocess.TimeoutExpired) as exc:
        return {"observed": False, "exists": True, "extra": [], "files": [], "error": str(exc)}
    supplied = {item.get("path"): item.get("sha256") for item in facts["supplemental"]}
    handoff = facts["handoff"]
    report = facts["assignment"].get("report_path")
    directories = tracked - {""}
    for rel in [report, handoff, *supplied]:
        if isinstance(rel, str):
            directories |= _ancestors(rel)
    if facts["notes"]:
        directories |= {facts["notes"], *_ancestors(facts["notes"])}
    files = [{"path": item["path"], "kind": item["kind"], "sha256": item.get("sha256")} for item in state["files"]
             if item["path"] != handoff]
    extra = {item["path"] for item in files if not (item["kind"] == "file" and supplied.get(item["path"]) == item["sha256"])}
    extra.update(entry["path"] for entry in entries if entry["kind"] in SPECIAL_KINDS
                 or entry["kind"] in ("unreadable", "replaced")
                 or (entry["kind"] == "directory" and entry["path"] not in directories))
    if state["head"] != prompt:
        extra.add(f"HEAD at {state['head']}")
    return {"observed": True, "exists": True, "extra": sorted(extra), "files": files}


def _session_entries(session: Path) -> list[str]:
    """Session entries beyond preparation's own records; doubt counts as an entry."""
    if session.is_symlink() or not session.is_dir():
        return ["<session directory unavailable>"]
    try:
        names = os.listdir(session)
    except OSError as exc:
        return [f"<session directory unreadable: {exc.strerror}>"]
    return sorted(name for name in names if name not in _SESSION_FOOTPRINT)


def _release_basis(session: Path, facts: dict, checkout: dict) -> dict:
    """Observations the release rule reads; recorded in CLOSING.json and reapplied at reuse."""
    info, data = read_regular(session / "PREPARE-ERROR.json")
    failure = {"kind": info["kind"], "sha256": info.get("sha256"), "stage": None}
    if data is not None:
        try:
            stage = loads_control(data).get("stage")
            failure["stage"] = stage if isinstance(stage, str) else None
        except (ValueError, RecursionError, AttributeError):
            failure["kind"] = "invalid"
    worktree = Path(facts["worktree"]) if facts["worktree"] else None
    # Without a recorded handoff path, or with no real checkout directory to
    # look in, the public copy cannot be ruled out.
    public = "unknown"
    if worktree is not None and not os.path.lexists(worktree):
        public = "missing"
    elif facts["handoff"] and worktree is not None and worktree.is_dir() and not worktree.is_symlink():
        try:
            public = _kind(contained(worktree, facts["handoff"], leaf_link=True))
        except StewartError:
            public = "unknown"
    return {"failure_receipt": failure, "private_handoff": _kind(session / "LAUNCH.md"), "public_handoff": public,
            "session_entries": _session_entries(session),
            "checkout": {"observed": checkout["observed"], "extra": checkout["extra"]}}


def _recorded_members(session: Path, facts: dict) -> list[str]:
    """Checkout-directory members the session's records name: runtimes and experiment homes."""
    from stewart.session import list_records, read_receipt
    if facts["audit_dir"] is None:
        return []
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
    return sorted({member for member in members if isinstance(member, str)
                   and Path(member).is_relative_to(audit_dir) and Path(member) != audit_dir})


def _removal(session: Path, facts: dict, common: str) -> dict:
    from stewart._repository import _registry
    uuid = facts["session_uuid"]
    return {"session_uuid": uuid, "worktree": facts["worktree"], "members": _recorded_members(session, facts),
            "checkout_dir": facts["audit_dir"], "refs": facts["refs"],
            "registry_row": str(_registry(common) / f"{uuid}.json") if uuid else None, "session": str(session)}


def _not_real_between(base: Path, path: Path) -> Path | None:
    """The first of ``base`` and the ancestors of ``path`` below it that is a link or not a directory."""
    for candidate in [base, *(base / part for part in path.relative_to(base).parent.parts)]:
        if candidate.is_symlink() or (os.path.lexists(candidate) and not candidate.is_dir()):
            return candidate
    return None


def _remove_tree(path: Path) -> str:
    """Remove a recorded directory without following links; a link is removed, never followed."""
    if path.is_symlink():
        path.unlink()
        return "removed link"
    if not path.exists():
        return "absent"
    if not path.is_dir():
        path.unlink()
        return "removed"
    for root, directories, _ in os.walk(path, followlinks=False):
        for name in directories:
            child = Path(root) / name
            if not child.is_symlink():
                child.chmod(stat.S_IRWXU)
    path.chmod(stat.S_IRWXU)
    shutil.rmtree(path)
    return "removed"


def _registrations(repo: Path) -> list[dict]:
    """Git's registered checkouts, each with its lock reason, from the porcelain listing."""
    blocks, current = [], {}
    for line in git_text(repo, "worktree", "list", "--porcelain").splitlines() + [""]:
        if not line:
            if current:
                blocks.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return blocks


def _remove(removal: dict, repo: Path) -> tuple[list[dict], list[str]]:
    """Remove the recorded inventory, auditor-facing items first and the session last.

    Removal stops at the first failure, so the session's own records go only
    after everything else is gone; a rerun resumes from CLOSING.json. What is
    kept rather than removed (a link where a directory was recorded, a ref
    that is symbolic or moved, a checkout registered elsewhere) and entries no
    record names are reported as leftovers.
    """
    from stewart._repository import lifetime_lock_reason
    results: list[dict] = []
    kept: list[str] = []
    uuid = removal["session_uuid"]
    worktree = Path(removal["worktree"]) if removal["worktree"] else None
    checkout_dir = Path(removal["checkout_dir"]) if removal["checkout_dir"] else None

    def remove_worktree() -> str:
        registered = _registrations(repo)
        if not any(entry.get("worktree") == str(worktree) for entry in registered):
            moved = [entry["worktree"] for entry in registered
                     if uuid and uuid in (entry.get("locked") or "") and entry.get("worktree")]
            if moved:
                kept.extend(f"checkout registered at {path}" for path in moved)
                return "kept: registered elsewhere"
            return _remove_tree(worktree)
        # Git never operates through a link standing in for the checkout.
        unlinked = worktree.is_symlink()
        if unlinked:
            worktree.unlink()
        git(repo, "worktree", "unlock", str(worktree), check=False)
        if not git(repo, "worktree", "remove", "--force", "--force", str(worktree), check=False).returncode:
            return "removed link and registration" if unlinked else "removed"
        # Git refuses a checkout it cannot validate, such as one whose .git
        # file is gone. Remove the recorded directory itself; Git then drops
        # the registration of the missing checkout.
        try:
            _remove_tree(worktree)
            git(repo, "worktree", "remove", "--force", "--force", str(worktree))
        except (OSError, StewartError):
            if uuid:
                git(repo, "worktree", "lock", "--reason", lifetime_lock_reason(uuid), str(worktree), check=False)
            raise
        return "removed (Git could not validate it)"

    def remove_member(member: Path) -> str:
        blocked = _not_real_between(checkout_dir, member)
        if blocked is not None:
            kept.append(str(member))
            return f"kept: {blocked} is not a real directory"
        return _remove_tree(member)

    def remove_empty(directory: Path) -> str:
        if not os.path.lexists(directory):
            return "absent"
        if directory.is_symlink() or not directory.is_dir():
            kept.append(str(directory))
            return "kept: not a real directory"
        if os.listdir(directory):
            return "kept: not empty"
        directory.rmdir()
        return "removed"

    def remove_ref(entry: dict) -> str:
        found = [ref for ref in _session_refs(repo, uuid) if ref["ref"] == entry["ref"]] if uuid else []
        if not found:
            return "absent"
        if found[0]["symref"] is not None or found[0]["commit"] != entry["commit"]:
            kept.append(f"ref {entry['ref']}")
            return "kept: symbolic or moved"
        git(repo, "update-ref", "--no-deref", "-d", entry["ref"], entry["commit"])
        return "removed"

    def remove_row() -> str:
        row = Path(removal["registry_row"])
        if not os.path.lexists(row):
            return "absent"
        row.unlink()
        return "removed"

    def remove_session() -> str:
        session = Path(removal["session"])
        if _not_real_between(session.parent, session) is not None:
            kept.append(str(session))
            return "kept: its parent is not a real directory"
        return _remove_tree(session)

    steps = [(removal["worktree"], "worktree", remove_worktree)] if worktree is not None else []
    if checkout_dir is not None:
        steps += [(member, "checkout member", lambda member=member: remove_member(Path(member)))
                  for member in removal["members"]]
        steps += [(str(directory), "checkout directory", lambda directory=directory: remove_empty(directory))
                  for directory in (checkout_dir / "attempts", checkout_dir)]
    steps += [(entry["ref"], "retention ref", lambda entry=entry: remove_ref(entry)) for entry in removal["refs"]]
    if removal["registry_row"] is not None:
        steps.append((removal["registry_row"], "registry row", remove_row))
    steps.append((removal["session"], "session", remove_session))
    for item, kind, action in steps:
        try:
            results.append({"item": item, "kind": kind, "outcome": action()})
        except (OSError, StewartError) as exc:
            results.append({"item": item, "kind": kind, "outcome": "failed", "detail": str(exc)})
            break
    leftovers = list(kept)
    recorded = {removal["worktree"], *removal["members"], *kept}
    if checkout_dir is not None:
        attempts = checkout_dir / "attempts"
        for directory in (checkout_dir, attempts):
            if directory.is_dir() and not directory.is_symlink() and not _not_real_between(checkout_dir, directory):
                leftovers += [str(directory / name) for name in os.listdir(directory)
                              if str(directory / name) not in recorded and directory / name != attempts]
    if uuid:
        # Refs under the session's namespace that it did not record, or that
        # removal kept; recorded refs a stopped removal never reached are not.
        named = {item.removeprefix("ref ") for item in kept} | {entry["ref"] for entry in removal["refs"]}
        leftovers += [f"ref {ref['ref']}" for ref in _session_refs(repo, uuid) if ref["ref"] not in named]
    return results, sorted(set(leftovers))


def closing_entries(common: str, ws: Workspace, ident: str) -> list[dict]:
    """Every closing record for an audit ID, oldest first, with its completion and validity.

    A closing directory that holds nothing is a close interrupted before its
    record was written, and is skipped. Anything that cannot be read as a
    closing record bound to this audit ID is a problem, never an absence.
    """
    from stewart.session import capture_receipt
    folder = closed_location(common, ws, ident)
    if not os.path.lexists(folder):
        return []
    if folder.is_symlink() or not folder.is_dir():
        return [{"session_uuid": None, "path": str(folder), "attempts": 0, "complete": False, "released": False,
                 "problem": {"reason": "closing_record_invalid", "message": f"not a real directory: {folder}",
                             "retained": [str(folder)], "next_steps": []}}]
    entries = []
    for directory in sorted(folder.iterdir()):
        entry: dict = {"session_uuid": directory.name, "path": str(directory), "attempts": 0}
        try:
            if directory.is_symlink() or not directory.is_dir():
                raise StewartError(f"not a real closing directory: {directory}", reason="closing_record_invalid",
                                   retained=[str(directory)])
            names = os.listdir(directory)
            if not names:
                continue
            entry["attempts"] = sum(name.startswith("CLOSE-ATTEMPT-") for name in names)
            closing, digest = _read(directory / "CLOSING.json", ws=ws, ident=ident, name=directory.name)
            entry.update(closing=closing, closing_sha256=digest, mode=closing["acknowledged"]["mode"],
                         complete=False, closed=None,
                         released=closing["acknowledged"]["mode"] == "abandoned"
                         and releasable(closing["observed"].get("release_basis")))
            done = directory / "CLOSED.json"
            if os.path.lexists(done):
                closed, _ = capture_receipt(done, what="closed record")
                if (closed.get("schema") != CLOSED_SCHEMA or closed.get("closing_sha256") != digest
                        or not isinstance(closed.get("leftovers"), list)
                        or not all(isinstance(item, str) for item in closed["leftovers"])):
                    raise StewartError(f"closed record does not bind its closing record: {done}",
                                       reason="closing_record_invalid", retained=[str(done)])
                entry.update(complete=True, closed=closed)
        except StewartError as exc:
            entry.update(problem={**exc.to_json(), "reason": "closing_record_invalid"}, complete=False, released=False)
        except (OSError, KeyError, TypeError, AttributeError, ValueError) as exc:
            entry.update(problem={"reason": "closing_record_invalid", "message": f"{type(exc).__name__}: {exc}",
                                  "retained": [str(directory)], "next_steps": []}, complete=False, released=False)
        entries.append(entry)
    return entries


def close_summary(entry: dict, repo: Path) -> dict:
    """One closing record as status shows it; leftovers are observed now, at read time."""
    summary = {"session_uuid": entry["session_uuid"], "path": entry["path"], "complete": entry["complete"],
               "released": entry["released"], "attempts": entry["attempts"]}
    if "problem" in entry:
        return {**summary, "problem": entry["problem"]}
    closing = entry["closing"]
    identity, acknowledged = closing["identity"], closing["acknowledged"]
    observed, attributed = closing["observed"], closing["attributed"]
    coordination = observed.get("coordination") if isinstance(observed.get("coordination"), dict) else {}
    recorded = (entry["closed"] or {}).get("leftovers") or []
    return {**summary, "mode": acknowledged["mode"], "actor": acknowledged["actor"], "reason": acknowledged["reason"],
            "closed_at": identity.get("closed_at"), "prompt_commit": identity.get("prompt_commit"),
            "session": closing["removal"]["session"],
            "decision": {"value": attributed.get("decision"), "attributed_to": attributed.get("decision_actor")},
            "auditor_completion": {"value": attributed.get("auditor_completion"), "attributed_to": "auditor"},
            "retained": observed["retained"], "discarded": observed["discarded"],
            # Stewart controls no writer: a paused session closed without
            # resume still has writers waiting on a person.
            "hold_outstanding": coordination.get("mode") == "paused" and coordination.get("hold_resumed") is not True,
            "leftovers": [item for item in recorded if _still_there(repo, item)]}


def _still_there(repo: Path, leftover: str) -> bool:
    """Whether a recorded leftover still exists; refs are looked up without being followed."""
    if leftover.startswith("ref "):
        ref = leftover[len("ref "):]
        listed = git(repo, "for-each-ref", "--format=%(refname)", ref, check=False)
        return ref in listed.stdout.decode("utf-8", "replace").splitlines()
    if leftover.startswith("checkout registered at "):
        path = leftover[len("checkout registered at "):]
        return any(entry.get("worktree") == path for entry in _registrations(repo))
    return os.path.lexists(leftover)


def _read(location: Path, *, ws: Workspace, ident: str, name: str) -> tuple[dict, str]:
    """One closing record, its shape and its binding to this audit and directory checked before use."""
    from stewart.session import capture_receipt
    value, digest = capture_receipt(location, what="closing record")

    def invalid(why: str) -> StewartError:
        return StewartError(f"closing record {why}: {location}", reason="closing_record_invalid",
                            retained=[str(location)],
                            next_steps=["preserve the closing record; it is never rewritten"])

    if value.get("schema") != CLOSING_SCHEMA or set(value) != _CLOSING_FIELDS:
        raise invalid("has an unsupported shape")
    if not all(isinstance(value[group], dict) for group in _CLOSING_FIELDS - {"schema"}):
        raise invalid("has a group that is not an object")
    identity, acknowledged, observed, removal = (value[key] for key in ("identity", "acknowledged", "observed",
                                                                          "removal"))
    if (identity.get("audit_id") != ident or identity.get("slug") != ws.slug
            or identity.get("session_uuid") not in (None, name)):
        raise invalid("belongs to another audit, workspace or session")
    if (acknowledged.get("mode") not in MODES or not isinstance(acknowledged.get("actor"), str)
            or not isinstance(acknowledged.get("reason"), (str, type(None)))):
        raise invalid("has an unsupported acknowledgment")
    retained, discarded = observed.get("retained"), observed.get("discarded")
    if (not isinstance(retained, list) or not all(isinstance(item, dict) and isinstance(item.get("path"), str)
                                                  for item in retained)
            or not (discarded is None or isinstance(discarded, list)
                    and all(isinstance(item, dict) and isinstance(item.get("path"), str) for item in discarded))):
        raise invalid("has unsupported observations")
    paths = [removal.get(key) for key in ("worktree", "checkout_dir", "registry_row", "session_uuid")]
    if (set(removal) != _REMOVAL_FIELDS or not isinstance(removal["session"], str)
            or not all(isinstance(path, (str, type(None))) for path in paths)
            or not isinstance(removal["members"], list) or not all(isinstance(m, str) for m in removal["members"])
            or not isinstance(removal["refs"], list)
            or not all(isinstance(r, dict) and isinstance(r.get("ref"), str) and isinstance(r.get("commit"), str)
                       for r in removal["refs"])):
        raise invalid("has an unsupported removal inventory")
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
        raise StewartError("a close needs an attributed actor", reason="actor_required",
                           next_steps=["rerun with --actor NAME naming who closes the audit"])
    if abandon and (not isinstance(reason, str) or not reason.strip()):
        raise StewartError("an abandon needs --reason naming why the audit is abandoned", reason="reason_required",
                           next_steps=["rerun with --abandon --reason TEXT"])
    if not abandon and (reason is not None or discard_uncollected):
        raise StewartError("--reason and --discard-uncollected apply only with --abandon", reason="usage",
                           next_steps=["add --abandon, or drop --reason and --discard-uncollected"])
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
    except StewartError as exc:
        if not abandon:
            # A session directory without a readable record does not verify.
            exc.code = EXIT_UNVERIFIED
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
    if facts["session_uuid"] is None and not abandon:
        raise StewartError("no session record or registry row identifies this session", reason="close_unidentified",
                           code=EXIT_UNVERIFIED, retained=[str(session)],
                           next_steps=[f"close --audit-id {ident} --abandon --reason TEXT retires the session "
                                       "directory alone; the audit ID stays reserved"])
    notes = ws.scratch_prefix(ident) + "notes"
    facts["notes"] = notes if notes in (facts["assignment"].get("scratch_paths") or []) else None
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
        if checkout["observed"]:
            uncollected = _uncollected(checkout, session)
        elif checkout["exists"] is None:
            uncollected = []  # no checkout is known, so none is removed
        else:
            uncollected = None
        if uncollected is None and not discard_uncollected:
            raise StewartError(f"the checkout could not be observed ({checkout.get('error')}); changes no collection "
                               "captured cannot be ruled out", reason="uncollected_changes",
                               retained=[facts["worktree"]],
                               next_steps=["make the checkout readable and collect, or rerun with --discard-uncollected"])
        if uncollected and not discard_uncollected:
            raise StewartError("the checkout holds changes no collection captured: "
                               + ", ".join(item["path"] for item in uncollected[:10]),
                               reason="uncollected_changes", retained=[facts["worktree"]],
                               next_steps=["collect first to preserve them, or rerun with --discard-uncollected"])
        # None records a discard that could not be observed.
        observed["discarded"] = (None if uncollected is None else
                                 [{"path": item["path"], "sha256": item["sha256"]} for item in uncollected])
        observed["release_basis"] = _release_basis(session, facts, checkout)
        observed["checkout"] = {"observed": checkout["observed"], "exists": checkout.get("exists"),
                                "extra": checkout["extra"], "error": checkout.get("error")}
        # A triage recorded before abandoning is still the manager's attributed decision.
        good = [d for d in view["dispositions"] if not d["problems"]] if view is not None else []
        if good:
            attributed.update(decision=good[-1].get("decision"), decision_actor=good[-1].get("actor"))
    else:
        concluded = _concluded(view, facts, session)
        disposition = concluded.pop("disposition")
        observed.update(concluded)
        attributed.update(decision=disposition["decision"], decision_actor=disposition["actor"])
    closing = {
        "schema": CLOSING_SCHEMA,
        "identity": {"session_uuid": facts["session_uuid"], "workspace": ws.rel, "slug": ws.slug, "audit_id": ident,
                     "prompt_commit": facts["prompt_commit"], "target_commit": facts["record"].get("target_commit"),
                     "base_commit": facts["assignment"].get("base_commit"),
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
                               retained=[str(parent)], next_steps=["preserve and inspect the link; nothing was removed"])
        parent.mkdir(mode=0o700, exist_ok=True)
    # An unidentified session gets a fresh name for its closing directory.
    directory = folder / (facts["session_uuid"] or str(_uuid.uuid4()))
    if os.path.lexists(directory):
        # Only a close interrupted before writing anything leaves an empty
        # directory; CLOSING.json itself is the exclusive record.
        if directory.is_symlink() or not directory.is_dir() or os.listdir(directory):
            raise StewartError(f"a closing record already exists for this session: {directory}",
                               reason="destination_exists", retained=[str(directory)],
                               next_steps=["status shows the existing close; rerun close to finish an incomplete one"])
    else:
        directory.mkdir(mode=0o700)
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
                           retained=[str(session)], next_steps=["close --abandon --reason TEXT"])
    unverified = [item for item in view["attention"] if item["code"] == EXIT_UNVERIFIED]
    if unverified:
        raise StewartError("a concluded close needs records that verify: "
                           + "; ".join(f"{item['source']}: {item['reason']}" for item in unverified[:5]),
                           reason="close_unverified", code=EXIT_UNVERIFIED, retained=[str(session)],
                           next_steps=["inspect the problems status lists, or close --abandon --reason TEXT"])
    # The latest complete collection that a valid triage addresses, and that
    # triage: the same choice status makes before offering close.
    valid = [d for d in view["dispositions"] if not d["problems"]]
    triaged = [c for c in view["collections"] if c["complete"] and any(d.get("collection") == c["name"] for d in valid)]
    if not triaged:
        raise StewartError("a concluded close needs a triage bound to a complete collection",
                           reason="close_not_concluded", retained=[str(session)],
                           next_steps=["triage a complete collection, or close --abandon --reason TEXT"])
    if view["coordination"].get("mode") == "paused" and view["coordination"].get("resumed") is None:
        raise StewartError("the paused hold is still outstanding", reason="close_hold_outstanding",
                           retained=[str(session)],
                           next_steps=["resume the hold with its triage and tell the writers, then close"])
    if any(problem["reason"] == "attempt_unresolved" for item in view["attempts"] for problem in item["problems"]):
        raise StewartError("an experiment attempt is unresolved", reason="close_attempt_unresolved",
                           retained=[str(session)],
                           next_steps=["close --abandon --reason TEXT keeps the unresolved attempt's record"])
    collection = triaged[-1]
    disposition = [d for d in valid if d.get("collection") == collection["name"]][-1]
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
