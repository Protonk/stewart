"""Retire a finished or abandoned audit: one closing record, then removal of what the session created.

While an audit is live its records are exclusive and preserved, failures
included. ``close`` is the only operation that deletes, and it removes only
what the session's own record names: the session directory, the locked
checkout with its runtimes and experiment homes, the session's retention refs
and its role registry row; after those, the managed resources whose last live
use it ends, each under an exclusive claim that freezes what was judged and is
revalidated at use. Before removing anything it writes ``CLOSING.json``
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
import stat
import uuid as _uuid

from stewart import _removal
from stewart import _util as _hash
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_UNVERIFIED, StewartError, read_regular
from stewart._git import git, git_text
from stewart._json import loads_control
from stewart.workspace import Workspace, contained

CLOSING_SCHEMA = "stewart.closing/1"
CLOSED_SCHEMA = "stewart.closed/1"
MODES = ("concluded", "abandoned")
_CLOSING_FIELDS = {"schema", "identity", "acknowledged", "observed", "attributed", "removal"}
_REMOVAL_FIELDS = {"session_uuid", "worktree", "git_admin", "members", "checkout_dir", "refs", "registry_row",
                   "session"}
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


def _canonical(value: object) -> str | None:
    from stewart._repository import session_uuid
    try:
        return session_uuid(value)
    except StewartError:
        return None


def _in_layout(common: str, uuid: str | None, checkout_dir: object) -> bool:
    """Whether a recorded checkout directory is ``<home>/<repo-key>/<uuid>``, so removal stays inside it."""
    from stewart._repository import repo_key
    if uuid is None or not isinstance(checkout_dir, str):
        return False
    path = Path(checkout_dir)
    return (path.is_absolute() and path.as_posix() == checkout_dir and ".." not in path.parts
            and path.name == uuid and path.parent.name == repo_key(common))


def _member_in_layout(checkout_dir: str, member: object) -> bool:
    """Runtimes and recoveries are children of the checkout directory; experiment homes are ``attempts/<name>``."""
    if not isinstance(member, str) or ".." in Path(member).parts:
        return False
    try:
        parts = Path(member).relative_to(checkout_dir).parts
    except ValueError:
        return False
    return len(parts) == 1 or (len(parts) == 2 and parts[0] == "attempts")


def _facts(session: Path, record: dict | None, rows: list[dict], repo: Path, common: str) -> dict:
    """What close needs, from the session record or, when it is unreadable, the registry row.

    The record names everything in a healthy session, including the exact
    retention refs and their commits. A row names the session path, its UUID,
    its worktree and its Git administration, so even an unreadable record can
    be retired; the checkout directory is the worktree's parent by the session
    layout, and the refs are the non-symbolic ones Git holds under the UUID.
    A UUID that is not canonical, or a checkout path outside the session
    layout, is not trusted: close then removes no checkout at all.
    """
    from stewart._git import COMMIT_ID
    record = record if isinstance(record, dict) else {}
    row = rows[0] if rows else {}
    uuid = _canonical(record.get("session_uuid")) or _canonical(row.get("session_uuid")) or _canonical(row.get("role_uuid"))
    # The record's checkout, else the row's; only one in the session layout is used.
    worktree = audit_dir = None
    for candidate_worktree, candidate_dir in ((record.get("worktree"), record.get("audit_dir")),
                                              (row.get("worktree"), None)):
        if candidate_dir is None and isinstance(candidate_worktree, str):
            candidate_dir = str(Path(candidate_worktree).parent)
        if _in_layout(common, uuid, candidate_dir) and candidate_worktree == str(Path(candidate_dir) / "worktree"):
            worktree, audit_dir = candidate_worktree, candidate_dir
            break
    git_admin = row.get("git_admin")
    if not (isinstance(git_admin, str) and Path(git_admin).parent == Path(common) / "worktrees"):
        git_admin = None
    retention = record.get("retention")
    if isinstance(retention, dict) and isinstance(retention.get("refs"), dict):
        refs = [{"ref": entry["ref"], "commit": entry["commit"]} for entry in retention["refs"].values()
                if isinstance(entry, dict) and isinstance(entry.get("ref"), str) and isinstance(entry.get("commit"), str)
                and uuid is not None and entry["ref"].startswith(f"refs/stewart/sessions/{uuid}/")
                and COMMIT_ID.fullmatch(entry["commit"])]
    else:
        refs = [{"ref": entry["ref"], "commit": entry["commit"]}
                for entry in (_session_refs(repo, uuid) if uuid else []) if entry["symref"] is None]
    assignment = record.get("assignment") if isinstance(record.get("assignment"), dict) else {}
    handoff = record.get("handoff") if isinstance(record.get("handoff"), dict) else {}
    prompt = record.get("prompt_commit")
    return {"session_uuid": uuid, "worktree": worktree, "audit_dir": audit_dir, "git_admin": git_admin, "common": common,
            "runtime": str(Path(audit_dir) / "runtime") if audit_dir else None, "repo": repo,
            "prompt_commit": prompt if isinstance(prompt, str) and COMMIT_ID.fullmatch(prompt) else None,
            "assignment": assignment,
            "supplemental": [item for item in assignment.get("supplemental_inputs", []) if isinstance(item, dict)],
            "handoff": handoff.get("path") if isinstance(handoff.get("path"), str) else None,
            "notes": None, "refs": refs, "record": record}


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
        return {"observed": False, "exists": None, "extra": [], "files": [], "unaccounted": [],
                "error": "no record names a checkout in the session layout"}
    worktree = Path(facts["worktree"])
    if not os.path.lexists(worktree):
        moved = _registered_elsewhere(facts["repo"], facts["session_uuid"], facts["git_admin"], worktree)
        if moved:
            return {"observed": False, "exists": True, "extra": [], "files": [], "unaccounted": [],
                    "error": f"the checkout is registered at {', '.join(moved)}"}
        return {"observed": True, "exists": False, "extra": [], "files": [], "unaccounted": []}
    if worktree.is_symlink() or not worktree.is_dir():
        return {"observed": True, "exists": True, "extra": [f"{worktree} is not a real directory"], "files": [],
                "unaccounted": []}
    prompt = facts["prompt_commit"]
    if prompt is None:
        return {"observed": False, "exists": True, "extra": [], "files": [], "unaccounted": [],
                "error": "the session record names no prompt commit to compare against"}
    from stewart._repository import checkout_git, checkout_git_admin
    try:
        # Git run through a planted .git, a link or a file naming another administration, would observe,
        # and write, another checkout or repository; only this session's own administration is used.
        git_admin = checkout_git_admin(worktree, facts["common"], facts["session_uuid"])
    except StewartError as exc:
        return {"observed": False, "exists": True, "extra": [], "files": [], "unaccounted": [], "error": str(exc)}
    try:
        state, _ = checkout_state(worktree, prompt, git_admin)
        entries = inventory(worktree)["entries"]
        tracked = set(os.fsdecode(git(worktree, *checkout_git(worktree, git_admin), "ls-tree", "-r", "-d",
                                      "--name-only", "-z", prompt).stdout).split("\0"))
    except (StewartError, OSError, subprocess.TimeoutExpired) as exc:
        return {"observed": False, "exists": True, "extra": [], "files": [], "unaccounted": [], "error": str(exc)}
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
    # Entries whose content was not observed (unreadable, replaced, not traversed, of unknown kind) are unknown.
    from stewart.coverage import classify
    unaccounted = sorted(entry["path"] for entry in classify(entries)[1])
    return {"observed": True, "exists": True, "extra": sorted(extra), "files": files, "unaccounted": unaccounted,
            "head": state["head"], "entries": entries}


def _admin_worktree(git_admin: Path) -> str | None:
    """The checkout path a worktree's Git administration names in its gitdir file."""
    _, data = read_regular(git_admin / "gitdir")
    if data is None:
        return None
    return str(Path(os.fsdecode(data.strip())).parent)


def _own_administrations(common: str, uuid: str | None, worktree: Path) -> list[Path]:
    """Git administrations that name the recorded checkout path and belong to this lifetime."""
    from stewart._repository import admin_lifetime
    root = Path(common) / "worktrees"
    if uuid is None:
        return []
    try:
        with _removal.pinned(root) as directory:
            names = sorted(os.listdir(directory))
    except (FileNotFoundError, _removal.Substituted):
        return []
    return [root / name for name in names
            if _admin_worktree(root / name) == str(worktree) and admin_lifetime(root / name) == uuid]


def _registered_elsewhere(repo: Path, uuid: str | None, git_admin: str | None, worktree: Path) -> list[str]:
    """Paths where Git registers this session's checkout other than the recorded one.

    A checkout is recognized by its lock reason naming the session UUID, or by
    the gitdir file in the Git administration its registry row recorded when
    that administration still belongs to this lifetime. A later checkout that
    reused the administrative name is another lifetime and is never claimed.
    """
    from stewart._repository import admin_lifetime
    found = []
    registered = _registrations(repo)
    if uuid:
        found += [entry["worktree"] for entry in registered if uuid in (entry.get("locked") or "")]
        if git_admin and admin_lifetime(Path(git_admin)) == uuid:
            location = _admin_worktree(Path(git_admin))
            found += [entry["worktree"] for entry in registered if location and entry.get("worktree") == location]
    return sorted({path for path in found if path and path != str(worktree)})


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
    try:
        recoveries = list_records(session / "runtime-recoveries")
        releases = list_records(session / "releases", suffix=".json")
    except OSError:
        recoveries, releases = [], []
    for entry in recoveries:
        for name in ("RECOVERY.json", "STARTED.json"):
            try:
                members.append(read_receipt(entry / name, what="runtime recovery")["runtime"]["identity"]["root"])
                break
            except (StewartError, KeyError, TypeError):
                continue
    for entry in releases:
        try:
            home = Path(read_receipt(entry, what="release record")["environment"]["HOME"])
        except (StewartError, KeyError, TypeError):
            continue
        members.append(str(home.parent))
    return sorted({member for member in members if _member_in_layout(facts["audit_dir"], member)})


def _removal_inventory(session: Path, facts: dict, common: str) -> dict:
    from stewart._repository import _registry
    uuid = facts["session_uuid"]
    return {"session_uuid": uuid, "worktree": facts["worktree"], "git_admin": facts["git_admin"],
            "members": _recorded_members(session, facts),
            "checkout_dir": facts["audit_dir"], "refs": facts["refs"],
            "registry_row": str(_registry(common) / f"{uuid}.json") if uuid else None, "session": str(session)}


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


def _revalidate_plan(closing: dict, repo: Path, common: str) -> None:
    """Refuse to remove the checkout unless what the close judged still holds; raises with the reason.

    A concluded close judged a checkout equal to its triaged collection, and
    that collection a verified capture; an abandon judged exactly the
    uncollected changes it listed. Work written after planning, including
    after an interruption, or a capture that no longer verifies, stops removal
    there, so the checkout and the session's records stay together. An
    abandon that authorized discarding unobservable changes (``discarded`` is
    null) planned no list.
    """
    from stewart.collect import inventory
    from stewart.coverage import require_capture
    from stewart.session import capture_receipt
    removal, observed = closing["removal"], closing["observed"]
    worktree, session = Path(removal["worktree"]), Path(removal["session"])
    retained = [str(worktree), str(session)]
    if closing["acknowledged"]["mode"] == "concluded":
        frozen = observed.get("collection") if isinstance(observed.get("collection"), dict) else {}
        try:
            directory = contained(session, f"collections/{frozen.get('name')}")
            receipt, digest = capture_receipt(directory / "collection.json", what="triaged collection receipt")
        except StewartError as exc:
            raise StewartError(f"the triaged collection cannot be read to compare the checkout with it ({exc.reason})",
                               reason="capture_unverified", retained=retained) from None
        if digest != frozen.get("sha256"):
            raise StewartError("the triaged collection's receipt changed; the checkout cannot be compared with it",
                               reason="capture_unverified", retained=retained)
        require_capture(repo, directory, receipt, retained=retained)
        current = _hash.sha256_bytes(_hash.receipt_json_bytes(inventory(worktree)))
        if current != (receipt.get("inventory") or {}).get("sha256"):
            raise StewartError("the checkout changed after the close was planned", reason="checkout_changed",
                               retained=retained)
        return
    discarded = observed.get("discarded")
    if discarded is None:
        return
    from stewart._repository import _role_records
    record = None
    try:
        record, _ = capture_receipt(session / "session.json", what="session record")
    except StewartError:
        pass
    rows = [row for row in _role_records(common) if row["session"] == str(session)]
    facts = _facts(session, record, rows, repo, common)
    identity = closing["identity"]
    notes = f"{identity['workspace']}/scratch/{identity['audit_id']}/notes"
    facts["notes"] = notes if notes in (facts["assignment"].get("scratch_paths") or []) else None
    checkout = _observe_checkout(facts)
    uncollected = _uncollected(checkout, session, facts) if checkout["observed"] and checkout["exists"] else (
        [] if checkout["observed"] else None)
    if uncollected is None:
        raise StewartError("the checkout can no longer be observed fully; changes made after planning cannot be "
                           "ruled out", reason="uncollected_changes", retained=retained)
    planned = {(item.get("path"), item.get("sha256"), item.get("target")) for item in discarded if isinstance(item, dict)}
    added = sorted(item["path"] for item in uncollected
                   if (item["path"], item["sha256"], item.get("target")) not in planned)
    if added:
        raise StewartError("changes written after the close was planned: " + ", ".join(added[:10]),
                           reason="checkout_changed", retained=retained)


def _delete_checkout(parent: int, name: str, *, identity: tuple[int, int] | None = None) -> str:
    """Delete the checkout below its pinned checkout directory; the one step that removes auditor work.

    ``identity`` is the entry inspected before planning was rechecked; a
    different entry at the name is left in place rather than removed instead.
    """
    return _removal.remove(parent, name, identity=identity)


def _remove(removal: dict, repo: Path, common: str, closing: dict) -> tuple[list[dict], list[str]]:
    """Remove the recorded inventory, auditor-facing items first and the session last.

    Removal stops at the first failure, so the session's own records go only
    after everything else is gone; a rerun resumes from CLOSING.json. Every
    removal runs relative to directory descriptors opened without following
    links from the filesystem root, so a link standing in for a recorded
    directory or any of its ancestors is kept and named, never traversed. The
    checkout's Git administration is removed only when it names the recorded
    path and belongs to this lifetime. A checkout that no longer matches what
    the close judged (``_revalidate_plan``) stops removal before anything is
    removed after it. What is kept rather than removed (a substituted
    directory, a ref that is symbolic or moved, a checkout registered
    elsewhere) and entries no record names are reported as leftovers.
    """
    results: list[dict] = []
    kept: list[str] = []
    uuid = removal["session_uuid"]
    worktree = Path(removal["worktree"]) if removal["worktree"] else None
    checkout_dir = Path(removal["checkout_dir"]) if removal["checkout_dir"] else None

    def substituted(exc: _removal.Substituted) -> str:
        kept.append(str(exc.location))
        return f"kept: {exc.location}: {exc.detail}"

    def remove_worktree() -> str:
        moved = _registered_elsewhere(repo, uuid, removal["git_admin"], worktree)
        if moved:
            kept.extend(f"checkout registered at {path}" for path in moved)
            return "kept: registered elsewhere"
        administrations = _own_administrations(common, uuid, worktree)
        try:
            with _removal.pinned(worktree.parent) as parent:
                found = _removal.entry(parent, worktree.name)
        except FileNotFoundError:
            found = None
        except _removal.Substituted as exc:
            kept.extend(str(admin) for admin in administrations)
            return substituted(exc)
        if found is not None:
            # A link standing in for the checkout holds no auditor work; it is
            # removed without being followed. Otherwise removal stops here,
            # before anything else goes, unless what the close judged holds.
            if not stat.S_ISLNK(found.st_mode):
                _revalidate_plan(closing, repo, common)
            try:
                with _removal.pinned(worktree.parent) as parent:
                    outcome = _delete_checkout(parent, worktree.name, identity=(found.st_dev, found.st_ino))
            except _removal.Substituted as exc:
                kept.extend(str(admin) for admin in administrations)
                return substituted(exc)
        else:
            outcome = "absent"
        # Git's own removal resolves the recorded pathname; drop only this
        # lifetime's administration, through pinned descriptors, instead.
        for admin in administrations:
            _removal.remove_path(admin)
        return outcome

    def remove_member(member: Path) -> str:
        try:
            return _removal.remove_path(member)
        except _removal.Substituted as exc:
            return substituted(exc)

    def remove_empty(directory: Path) -> str:
        try:
            return _removal.remove_empty(directory)
        except _removal.Substituted as exc:
            return substituted(exc)

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
        try:
            return _removal.remove_path(Path(removal["registry_row"]))
        except _removal.Substituted as exc:
            return substituted(exc)

    def remove_session() -> str:
        try:
            return _removal.remove_path(Path(removal["session"]))
        except _removal.Substituted as exc:
            return substituted(exc)

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
        except (OSError, StewartError, ValueError, TypeError, _removal.Replaced) as exc:
            results.append({"item": item, "kind": kind, "outcome": "failed", "detail": str(exc),
                            **({"reason": exc.reason} if isinstance(exc, StewartError) else {})})
            break
    leftovers = list(kept)
    recorded = {removal["worktree"], *removal["members"], *kept}
    if checkout_dir is not None:
        attempts = checkout_dir / "attempts"
        for directory in (checkout_dir, attempts):
            try:
                with _removal.pinned(directory) as descriptor:
                    names = os.listdir(descriptor)
            except (FileNotFoundError, _removal.Substituted):
                continue
            except OSError as exc:
                leftovers.append(f"{directory} (unreadable: {exc.strerror})")
                continue
            leftovers += [str(directory / name) for name in names
                          if str(directory / name) not in recorded and directory / name != attempts]
    if uuid:
        # Refs under the session's namespace that it did not record, or that
        # removal kept; recorded refs a stopped removal never reached are not.
        named = {item.removeprefix("ref ") for item in kept} | {entry["ref"] for entry in removal["refs"]}
        leftovers += [f"ref {ref['ref']}" for ref in _session_refs(repo, uuid) if ref["ref"] not in named]
    return results, sorted(set(leftovers))


def _publish(directory: Path, name: str, document: dict) -> None:
    """Create a record exclusively and never partially: a staged copy, then an exclusive link to its name.

    A crash or a full disk leaves at most a ``.staged`` copy, which readers
    ignore, never a truncated record under the final name.
    """
    from stewart.session import stamp, write_receipt
    staged = directory / f".{name}.{stamp()}.staged"
    write_receipt(staged, document)
    try:
        os.link(staged, directory / name)
    except FileExistsError:
        raise StewartError(f"{name} already exists: {directory / name}", reason="destination_exists",
                           retained=[str(directory / name)],
                           next_steps=["status shows the existing close; rerun close to finish an incomplete one"]) from None
    staged.unlink()


def _staged(name: str) -> bool:
    return name.startswith(".") and name.endswith(".staged")


def closing_entries(common: str, ws: Workspace, ident: str) -> list[dict]:
    """Every closing record for an audit ID, oldest first by closing time, with its completion and validity.

    A closing directory that holds nothing but staged copies is a close
    interrupted before its record was published, and is skipped. Anything that
    cannot be read as a closing record bound to this audit ID is a problem,
    never an absence.
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
            names = [name for name in os.listdir(directory) if not _staged(name)]
            if not names:
                continue
            entry["attempts"] = sum(name.startswith("CLOSE-ATTEMPT-") for name in names)
            closing, digest = _read(directory / "CLOSING.json", ws=ws, ident=ident, name=directory.name, common=common)
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
            elif entry["attempts"]:
                entry["stopped"] = _last_attempt(directory, [name for name in names if name.startswith("CLOSE-ATTEMPT-")],
                                                 digest)
        except StewartError as exc:
            entry.update(problem={**exc.to_json(), "reason": "closing_record_invalid"}, complete=False, released=False)
        except (OSError, KeyError, TypeError, AttributeError, ValueError) as exc:
            entry.update(problem={"reason": "closing_record_invalid", "message": f"{type(exc).__name__}: {exc}",
                                  "retained": [str(directory)], "next_steps": []}, complete=False, released=False)
        entries.append(entry)
    # Unreadable records sort first: they keep the ID reserved whatever follows.
    return sorted(entries, key=lambda item: ("problem" not in item,
                                             str(((item.get("closing") or {}).get("identity") or {}).get("closed_at"))))


#: Reasons a removal attempt stops because what its close judged no longer holds, rather than because a removal failed.
JUDGMENT_STOPS = frozenset({"checkout_changed", "uncollected_changes", "capture_not_recorded", "capture_unverified",
                            "capture_uncovered"})


def _last_attempt(directory: Path, names: list[str], closing_sha256: str) -> dict:
    """Where and why the latest removal attempt stopped, as its record says.

    Attempts are ordered by their recorded time: a name's random suffix orders
    nothing within one second. An attempt record that cannot be read or does
    not bind its closing record makes the close's records fail verification,
    as an invalid CLOSED.json does.
    """
    from stewart.session import capture_receipt
    attempts = []
    for name in names:
        location = directory / name
        attempt, _ = capture_receipt(location, what="close attempt record")
        failed = [item for item in attempt.get("results") or [] if isinstance(item, dict) and item.get("outcome") == "failed"]
        if (attempt.get("schema") != CLOSED_SCHEMA or attempt.get("closing_sha256") != closing_sha256 or not failed
                or not isinstance(attempt.get("recorded_at"), str)):
            raise StewartError(f"close attempt record does not bind its closing record: {location}",
                               reason="closing_record_invalid", retained=[str(location)])
        attempts.append((attempt["recorded_at"], name, location, failed[-1]))
    _, _, location, stop = max(attempts)
    return {"attempt": str(location), "item": stop.get("item"), "kind": stop.get("kind"),
            "reason": stop.get("reason"), "detail": stop.get("detail"),
            "judgment": stop.get("reason") in JUDGMENT_STOPS}


def close_summary(entry: dict, repo: Path) -> dict:
    """One closing record as status shows it; leftovers are observed now, at read time."""
    summary = {"session_uuid": entry["session_uuid"], "path": entry["path"], "complete": entry["complete"],
               "released": entry["released"], "attempts": entry["attempts"],
               **({"stopped": entry["stopped"]} if "stopped" in entry else {})}
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


def _read(location: Path, *, ws: Workspace, ident: str, name: str, common: str) -> tuple[dict, str]:
    """One closing record, its shape and its binding to this audit and directory checked before use.

    The removal inventory must name this audit's session location, refs under
    its own UUID and a checkout directory in the session layout, so even a
    record written by hand can direct removal nowhere else.
    """
    from stewart._git import COMMIT_ID
    from stewart._repository import _registry, session_location
    from stewart.session import capture_receipt
    value, digest = capture_receipt(location, what="closing record")

    def invalid(why: str) -> StewartError:
        return StewartError(f"closing record {why}: {location}", reason="closing_record_invalid",
                            retained=[str(location)],
                            next_steps=["preserve the closing record; it is never rewritten"])

    def optional(item: object, kind: type) -> bool:
        return item is None or isinstance(item, kind)

    if value.get("schema") != CLOSING_SCHEMA or set(value) != _CLOSING_FIELDS:
        raise invalid("has an unsupported shape")
    if not all(isinstance(value[group], dict) for group in _CLOSING_FIELDS - {"schema"}):
        raise invalid("has a group that is not an object")
    identity, acknowledged, observed, removal = (value[key] for key in ("identity", "acknowledged", "observed",
                                                                          "removal"))
    uuid = identity.get("session_uuid", "missing")
    if (identity.get("audit_id") != ident or identity.get("slug") != ws.slug
            or not (uuid is None or (_canonical(uuid) == uuid and uuid == name))
            or not optional(identity.get("prompt_commit"), str) or not optional(identity.get("closed_at"), str)):
        raise invalid("belongs to another audit, workspace or session")
    if (acknowledged.get("mode") not in MODES or not isinstance(acknowledged.get("actor"), str)
            or not optional(acknowledged.get("reason"), str)):
        raise invalid("has an unsupported acknowledgment")
    retained, discarded, coordination = observed.get("retained"), observed.get("discarded"), observed.get("coordination")
    if (not isinstance(retained, list)
            or not all(isinstance(item, dict) and isinstance(item.get("path"), str) for item in retained)
            or not (discarded is None or isinstance(discarded, list)
                    and all(isinstance(item, dict) and isinstance(item.get("path"), str) for item in discarded))
            or not isinstance(coordination, dict) or not optional(coordination.get("mode"), str)
            or not optional(coordination.get("hold_resumed"), bool)
            or not optional(observed.get("release_basis"), dict)):
        raise invalid("has unsupported observations")
    if (set(removal) != _REMOVAL_FIELDS or removal["session_uuid"] != uuid
            or removal["session"] != str(session_location(common, ws, ident))):
        raise invalid("names another session's removal")
    checkout_dir, worktree, members, refs = (removal[key] for key in ("checkout_dir", "worktree", "members", "refs"))
    if uuid is None:
        layout = checkout_dir is None and worktree is None and members == [] and refs == [] \
            and removal["registry_row"] is None and removal["git_admin"] is None
    else:
        layout = ((checkout_dir is None and worktree is None and members == []
                   or _in_layout(common, uuid, checkout_dir) and worktree == str(Path(checkout_dir) / "worktree")
                   and isinstance(members, list) and all(_member_in_layout(checkout_dir, m) for m in members))
                  and removal["registry_row"] == str(_registry(common) / f"{uuid}.json")
                  and (removal["git_admin"] is None or isinstance(removal["git_admin"], str)
                       and Path(removal["git_admin"]).parent == Path(common) / "worktrees")
                  and isinstance(refs, list)
                  and all(isinstance(r, dict) and set(r) == {"ref", "commit"} and isinstance(r["ref"], str)
                          and r["ref"].startswith(f"refs/stewart/sessions/{uuid}/") and ".." not in r["ref"]
                          and isinstance(r["commit"], str) and COMMIT_ID.fullmatch(r["commit"]) for r in refs))
    if not layout:
        raise invalid("has a removal inventory outside its session's layout")
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


def _uncollected(checkout: dict, session: Path, facts: dict) -> list[dict] | None:
    """Checkout entries whose bytes neither a verified capture nor the prompt commit preserves.

    An entry counts as collected only when a collection's verified archive
    holds the same kind and content at its path; a partial, missing or damaged
    archive saves nothing, and Git's report of what changed decides nothing.
    The issued handoff and supplemental copies are preparation's own while
    their bytes match their pins. None means the answer cannot be known:
    an entry whose content was not observed, or a moved HEAD that no verified
    capture recorded.
    """
    from stewart.coverage import archived, unpreserved
    from stewart.session import list_records, read_receipt
    held: dict[str, set] = {}
    heads: set[str] = set()
    try:
        entries = list_records(session / "collections")
    except OSError:
        entries = []
    for entry in entries:
        try:
            receipt = read_receipt(entry / "collection.json", what="collection receipt")
            members = archived(entry, receipt)
        except StewartError:
            continue
        for key, value in members.items():
            held.setdefault(key, set()).add(value)
        heads.add((receipt.get("checkout") or {}).get("head"))
    moved = any(item.startswith("HEAD at ") for item in checkout["extra"])
    if checkout["unaccounted"] or (moved and checkout.get("head") not in heads):
        return None
    from stewart.collect import _spelling
    handoff = facts["record"].get("handoff") if isinstance(facts["record"].get("handoff"), dict) else {}
    pins = [handoff, *facts["supplemental"]]
    exempt = {_spelling(item["path"]): ("file", item["sha256"]) for item in pins
              if isinstance(item.get("path"), str) and isinstance(item.get("sha256"), str)}
    missing, unresolved = unpreserved(checkout.get("entries", []), held, facts["repo"], facts["prompt_commit"],
                                      exempt=exempt)
    if unresolved:
        return None
    return [{"path": item["path"], "sha256": item.get("sha256"),
             **({"target": item["target"]} if item["kind"] == "symlink" else {})} for item in missing]


def close(ws: Workspace, ident: str, *, actor: str, abandon: bool = False, reason: str | None = None,
          discard_uncollected: bool = False, lifetime: str | None = None, dispose: list[str] = (),
          collection: str | None = None, request_key: str | None = None, resume: bool = False) -> dict:
    """Retire one audit: write CLOSING.json, remove the recorded inventory, write CLOSED.json.

    A concluded close refuses with 3 wherever status reports records that do
    not verify. An abandon accepts any state, including unreadable records,
    and records why. A previously interrupted close resumes from its own
    recorded inventory. After its closing record exists, a close claims each
    recorded resource whose last live use it ends, and retires those claims
    after the session's own items; ``dispose`` names contained exports or
    retained deliverables the manager decided to remove with their container.
    """
    from stewart.request_keys import keyed
    inputs = {"actor": actor, "abandon": abandon, "reason": reason, "discard_uncollected": discard_uncollected,
              "dispose": sorted(dispose), "collection": collection}
    return keyed(ws, ident, "close", inputs, request_key,
                 lambda plan: _close(ws, ident, actor=actor, abandon=abandon, reason=reason,
                                     discard_uncollected=discard_uncollected, lifetime=lifetime,
                                     dispose=list(dispose), collection=collection, resume=resume, plan=plan),
                 lifetime=lifetime, resume=resume,
                 # Removal that failed leaves the request partial; close --resume-request finishes it.
                 complete=lambda result: result["closed"] is not None
                 and not any(item["outcome"] == "failed" for item in result.get("resources", [])),
                 outputs=lambda result: [{"kind": "closing", "path": result["closing"],
                                          "sha256": read_regular(Path(result["closing"]))[0].get("sha256")},
                                         *({"kind": "resource", "resource": item["rid"]}
                                           for item in result.get("resources", []) if item.get("outcome") == "removed")])


def _known_audit(common: str, ws: Workspace, ident: str) -> bool:
    """Whether a draft, registration or resource context recorded after every close names this audit.

    A record that knew fewer closes than exist belongs to a use an earlier
    close already ended, so it leaves nothing to abandon.
    """
    from stewart.audits import closed_names, draft_records
    from stewart.holdings import contexts_for
    closes = set(closed_names(common, ws.slug, ident))
    records = [*draft_records(common, ws.slug, ident), *contexts_for(common, ws.slug, ident)]
    return any(closes <= set(item.get("closed_before") or []) for item in records)


def _resume_preflight(ws: Workspace, ident: str, entry: dict, lifetime: str | None) -> None:
    """What refuses resuming an unfinished close: another lifetime, or another implementation."""
    from stewart.implementation import require
    if lifetime is not None and entry["session_uuid"] != lifetime:
        raise StewartError(f"the unfinished close belongs to lifetime {entry['session_uuid']}, not {lifetime}",
                           reason="reference_stale", retained=[entry["path"]])
    # Resuming removal is a mutation: it runs under the implementation that planned it.
    require(entry["closing"]["identity"].get("stewart"), record=Path(entry["path"]) / "CLOSING.json",
            arguments=["--repo", str(ws.repo), "--workspace", ws.rel, "status", "--audit-id", ident])


def _preflight(ws: Workspace, ident: str, *, common: str, session: Path, rows: list[dict], abandon: bool,
               discard_uncollected: bool, lifetime: str | None, collection: str | None) -> dict:
    """Every check a close makes before writing anything, and the observations its closing record keeps.

    Read-only: ``close`` and ``close --plan`` share it, so a plan reports
    exactly the refusal the close would raise now.
    """
    from stewart.implementation import recorded_digest, require
    from stewart.session import capture_receipt, mutable_session, owner_refusal
    # A session whose directory is gone can still be abandoned through the
    # registry row that names its checkout and refs, and an audit recorded only
    # as a draft or resource context through those records.
    if not session.is_dir() and not (abandon and (rows or _known_audit(common, ws, ident))):
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
    if isinstance(record, dict):
        from stewart.session import bind_lifetime
        bind_lifetime(record, lifetime, session)
        # An unknown writer (no readable stamp) cannot be mismatched; a recorded one must be this one.
        if recorded_digest(record.get("stewart")) is not None:
            require(record.get("stewart"), record=session / "session.json",
                    arguments=["--repo", str(ws.repo), "--workspace", ws.rel, "status", "--audit-id", ident])
    if not abandon:
        mutable_session(ws, ident, lifetime=lifetime)
    facts = _facts(session, record, rows, ws.repo, common)
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
            uncollected = _uncollected(checkout, session, facts) if checkout["exists"] else []
        elif checkout["exists"] is None:
            uncollected = []  # no checkout is known, so none is removed
        else:
            uncollected = None
        if uncollected is None and not discard_uncollected:
            why = checkout.get("error") or "entries Git cannot list, or a commit no collection recorded: " + ", ".join(
                checkout["unaccounted"] or [item for item in checkout["extra"] if item.startswith("HEAD at ")])
            raise StewartError(f"the checkout could not be observed fully ({why}); "
                               "changes no collection captured cannot be ruled out", reason="uncollected_changes",
                               retained=[facts["worktree"]],
                               next_steps=["make the checkout readable and collect, or rerun with --discard-uncollected"])
        if uncollected and not discard_uncollected:
            raise StewartError("the checkout holds changes no collection captured: "
                               + ", ".join(item["path"] for item in uncollected[:10]),
                               reason="uncollected_changes", retained=[facts["worktree"]],
                               next_steps=["collect first to preserve them, or rerun with --discard-uncollected"])
        # None records a discard that could not be observed.
        observed["discarded"] = None if uncollected is None else [dict(item) for item in uncollected]
        observed["release_basis"] = _release_basis(session, facts, checkout)
        observed["checkout"] = {"observed": checkout["observed"], "exists": checkout.get("exists"),
                                "extra": checkout["extra"], "error": checkout.get("error")}
        # A triage recorded before abandoning is still the manager's attributed decision.
        good = [d for d in view["dispositions"] if not d["problems"]] if view is not None else []
        if good:
            attributed.update(decision=good[-1].get("decision"), decision_actor=good[-1].get("actor"))
    else:
        concluded = _concluded(view, facts, session, expected=collection)
        disposition = concluded.pop("disposition")
        observed.update(concluded)
        attributed.update(decision=disposition["decision"], decision_actor=disposition["actor"])
    return {"record": record, "session_digest": session_digest, "facts": facts, "observed": observed,
            "attributed": attributed}


def _validate_mode(*, abandon: bool, discard_uncollected: bool, reason: str | None = None) -> None:
    """Mode compatibility shared with planning; attribution and rationale are required only for mutation."""
    if not abandon and (reason is not None or discard_uncollected):
        raise StewartError("--reason and --discard-uncollected apply only with --abandon", reason="usage",
                           next_steps=["add --abandon, or drop --reason and --discard-uncollected"])


def _close(ws: Workspace, ident: str, *, actor: str, abandon: bool, reason: str | None, discard_uncollected: bool,
           lifetime: str | None, dispose: list[str], collection: str | None, resume: bool, plan) -> dict:
    from stewart._repository import _role_records, maintainer, private_storage, session_location
    from stewart.session import capture_receipt, now, tool_identity
    if not isinstance(actor, str) or not actor.strip():
        raise StewartError("a close needs an attributed actor", reason="actor_required",
                           next_steps=["rerun with --actor NAME naming who closes the audit"])
    if abandon and (not isinstance(reason, str) or not reason.strip()):
        raise StewartError("an abandon needs --reason naming why the audit is abandoned", reason="reason_required",
                           next_steps=["rerun with --abandon --reason TEXT"])
    _validate_mode(abandon=abandon, discard_uncollected=discard_uncollected, reason=reason)
    common = maintainer(ws.repo)["common_dir"]
    entries = closing_entries(common, ws, ident)
    for entry in entries:
        if not entry["complete"] and "problem" not in entry:
            _resume_preflight(ws, ident, entry, lifetime)
            plan([{"kind": "closing", "path": str(Path(entry["path"]) / "CLOSED.json")}])
            return _finish(ws.repo, common, Path(entry["path"]), entry["closing"], entry["closing_sha256"], resumed=True)
    session = session_location(common, ws, ident)
    rows = [row for row in _role_records(common) if row["session"] == str(session)]
    if resume and not session.is_dir() and not rows:
        from stewart.request_keys import planned
        ours = {item.get("path") for item in planned() or [] if item.get("kind") == "closing"}
        done = [entry for entry in entries if entry["complete"] and str(Path(entry["path"]) / "CLOSING.json") in ours
                and (lifetime is None or entry["session_uuid"] == lifetime)]
        if done:
            # The close this request planned was finished by another invocation; report it as it stands,
            # finishing only the resource claims that name it.
            return _finished_result(done[-1], common)
    pre = _preflight(ws, ident, common=common, session=session, rows=rows, abandon=abandon,
                     discard_uncollected=discard_uncollected, lifetime=lifetime, collection=collection)
    record, session_digest, facts = pre["record"], pre["session_digest"], pre["facts"]
    observed, attributed = pre["observed"], pre["attributed"]
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
        "removal": _removal_inventory(session, facts, common),
    }
    if not session.is_dir() and not rows:
        from stewart.audits import draft_records
        observed["drafts"] = [item["path"] for item in draft_records(common, ws.slug, ident)]
    folder = closed_location(common, ws, ident)
    parent = private_storage(common)
    for part in folder.relative_to(parent).parts:
        parent = parent / part
        if parent.is_symlink():
            raise StewartError(f"closed-record storage cannot traverse a link: {parent}", reason="path_symlink",
                               retained=[str(parent)], next_steps=["preserve and inspect the link; nothing was removed"])
        if os.path.lexists(parent) and not parent.is_dir():
            raise StewartError(f"closed-record storage is not a directory: {parent}", reason="closing_record_invalid",
                               code=EXIT_UNVERIFIED, retained=[str(parent)],
                               next_steps=["preserve and inspect it; nothing was removed"])
        parent.mkdir(mode=0o700, exist_ok=True)
    # An unidentified session gets a fresh name for its closing directory.
    directory = folder / (facts["session_uuid"] or str(_uuid.uuid4()))
    if os.path.lexists(directory):
        # Only a close interrupted before publishing its record leaves this
        # directory, holding staged copies at most; CLOSING.json is exclusive.
        if (directory.is_symlink() or not directory.is_dir()
                or any(not _staged(name) for name in os.listdir(directory))):
            raise StewartError(f"a closing record already exists for this session: {directory}",
                               reason="destination_exists", retained=[str(directory)],
                               next_steps=["status shows the existing close; rerun close to finish an incomplete one"])
    else:
        directory.mkdir(mode=0o700)
    plan([{"kind": "closing", "path": str(directory / "CLOSING.json")},
          {"kind": "closed", "path": str(directory / "CLOSED.json")}])
    _publish(directory, "CLOSING.json", closing)
    _, closing_digest = capture_receipt(directory / "CLOSING.json", what="closing record")
    return _finish(ws.repo, common, directory, closing, closing_digest, resumed=False,
                   claim={"slug": ws.slug, "ident": ident, "lifetime": facts["session_uuid"], "dispose": dispose})


def _status_view(ws: Workspace, ident: str) -> dict | None:
    """The live session view, or None when there is no live session to describe."""
    from stewart.status import STATUS_SCHEMA, status
    try:
        view = status(ws, ident)
    except (StewartError, OSError):
        return None
    return view if view.get("schema") == STATUS_SCHEMA else None


def _concluded(view: dict | None, facts: dict, session: Path, *, expected: str | None = None) -> dict:
    """The preconditions of a concluded close and the observations it rests on."""
    from stewart.collect import inventory
    from stewart.coverage import require_capture
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
    if expected is not None and expected != collection["name"]:
        raise StewartError(f"this close was offered for collection {expected}; the audit now rests on "
                           f"{collection['name']}", reason="action_stale", retained=[str(session)],
                           next_steps=["inspect status again and use the action it offers now"])
    disposition = [d for d in valid if d.get("collection") == collection["name"]][-1]
    receipt, collection_digest = capture_receipt(Path(collection["path"]) / "collection.json", what="collection receipt")
    _, triage_digest = capture_receipt(Path(disposition["path"]), what="triage record")
    worktree = Path(facts["worktree"])
    # A complete receipt is not a verified capture, and a triage does not make it one.
    require_capture(facts["repo"], Path(collection["path"]), receipt, retained=[str(session), str(worktree)])
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


def _finished_result(entry: dict, common: str) -> dict:
    """A completed close as a close result, for a request that finds its work already done.

    Claims naming this closing record that are still active are retired now;
    nothing new is claimed.
    """
    from stewart.holdings import retire_for_close
    closing, closed = entry["closing"], entry["closed"] or {}
    identity, acknowledged = closing["identity"], closing["acknowledged"]
    resources = retire_for_close(common, Path(entry["path"]))
    return {"audit_id": identity["audit_id"], "session_uuid": identity["session_uuid"], "mode": acknowledged["mode"],
            "closing": str(Path(entry["path"]) / "CLOSING.json"), "closed": str(Path(entry["path"]) / "CLOSED.json"),
            "resumed": True, "hold_outstanding": False, "released": entry["released"],
            "results": closed.get("results") or [], "leftovers": closed.get("leftovers") or [], "failed": [],
            "resources": resources, "closeout": [],
            "exit_code": EXIT_ATTENTION if closed.get("leftovers") or any(item["outcome"] != "removed"
                                                                          for item in resources) else EXIT_OK}


def _finish(repo: Path, common: str, directory: Path, closing: dict, closing_sha256: str, *, resumed: bool,
            claim: dict | None = None) -> dict:
    """Remove the recorded inventory, then claim and retire the resources this close ends the use of.

    Only the first attempt claims (``claim``), after CLOSING.json and the
    session's own items: this audit's uses have ended, and a concurrent close
    of another user sees this closing record before it claims. A resumed close
    retires only the claims naming it, never a wider set. CLOSED.json is
    written once every session item is gone; a resource whose removal fails
    keeps its claim and its own attempt record, and is resumed by rerunning
    this close or by ``close --resource``.
    """
    from stewart.holdings import claim_for_close, retire_for_close, used_by
    from stewart.session import now, stamp, tool_identity
    # What the audit uses is fixed before its session goes: removal takes away the paths it pinned.
    used = used_by(common, claim["slug"], claim["ident"]) if claim is not None else None
    results, leftovers = _remove(closing["removal"], repo, common, closing)
    failed = [item for item in results if item["outcome"] == "failed"]
    evaluations = []
    if claim is not None and not failed:
        evaluations = claim_for_close(common, claim["slug"], claim["ident"], lifetime=claim["lifetime"],
                                      closing=directory, dispose=claim["dispose"], used=used)
    resources = [] if failed else retire_for_close(common, directory)
    results += [{"item": item["rid"], "kind": f"resource {item['kind']}", "outcome": item["outcome"],
                 **({"detail": item["detail"]} if "detail" in item else {}),
                 **({"reasons": item["reasons"]} if "reasons" in item else {})} for item in resources]
    document = {"schema": CLOSED_SCHEMA, "closing_sha256": closing_sha256, "recorded_at": now().isoformat(),
                "results": results, "leftovers": leftovers, "resumed": resumed, "stewart": tool_identity()}
    if failed:
        # A failed removal leaves the close incomplete: status says so and a
        # rerun finishes it from CLOSING.json. Each attempt keeps its record.
        _publish(directory, f"CLOSE-ATTEMPT-{stamp()}.json", document)
        closed = None
    else:
        _publish(directory, "CLOSED.json", document)
        closed = str(directory / "CLOSED.json")
    identity, acknowledged = closing["identity"], closing["acknowledged"]
    coordination = closing["observed"].get("coordination") or {}
    return {"audit_id": identity["audit_id"], "session_uuid": identity["session_uuid"], "mode": acknowledged["mode"],
            "closing": str(directory / "CLOSING.json"), "closed": closed, "resumed": resumed,
            # Stewart controls no writer process: a paused session closed
            # without resume still has writers waiting on a person.
            "hold_outstanding": coordination.get("mode") == "paused" and coordination.get("hold_resumed") is not True,
            "released": acknowledged["mode"] == "abandoned" and releasable(closing["observed"].get("release_basis")),
            "results": results, "leftovers": leftovers, "failed": failed, "resources": resources,
            "closeout": evaluations,
            # A stop because a capture no longer verifies is 3; any other stop, leftover, or resource this close
            # leaves blocked or missing needs the manager; shared use is routine.
            "exit_code": _stop_code(failed) if failed else EXIT_ATTENTION if leftovers or any(
                item["outcome"] != "removed" for item in resources)
            or any(item.get("disposition") in ("blocked", "missing") for item in evaluations) else EXIT_OK}


def _stop_code(failed: list[dict]) -> int:
    """The code a stopped removal earns: 3 when its reason means records that do not verify, else 1."""
    from stewart._bootstrap import exit_code_for
    return EXIT_UNVERIFIED if any(item.get("reason") and exit_code_for(item["reason"]) == EXIT_UNVERIFIED
                                  for item in failed) else EXIT_ATTENTION


def close_plan(ws: Workspace, ident: str, *, lifetime: str | None = None, abandon: bool = False,
               discard_uncollected: bool = False, collection: str | None = None, dispose: list[str] = (),
               reason: str | None = None) -> dict:
    """The closeout description: what close would remove, preserve or leave, and why; writes nothing.

    Audit closure (the session's own inventory), retirement of the working
    resources around it, and retention of historical evidence are reported
    separately. The close's own read-only preflight runs here, so the refusal
    it would raise now (for either mode) is reported, not raised; nothing here
    claims a resource or records a decision.
    """
    from stewart._repository import _role_records, maintainer, session_location
    from stewart.holdings import CLOSEOUT_SCHEMA, _closeout, presented
    from stewart.request_keys import request_summaries
    from stewart.session import capture_receipt
    common = maintainer(ws.repo)["common_dir"]
    entries = closing_entries(common, ws, ident)
    session = session_location(common, ws, ident)
    rows = [row for row in _role_records(common) if row["session"] == str(session)]
    try:
        record, _ = capture_receipt(session / "session.json", what="session record")
    except StewartError:
        record = None
    facts = _facts(session, record, rows, ws.repo, common)
    audit: dict = {"mode": "abandoned" if abandon else "concluded", "refusal": None, "removes": None}
    unfinished = [entry for entry in entries if not entry["complete"] and "problem" not in entry]
    try:
        if unfinished:
            audit.update(state="close_incomplete", removes=unfinished[-1]["closing"]["removal"],
                         note="a rerun finishes this recorded inventory and never widens it",
                         stopped=unfinished[-1].get("stopped"))
        elif session.is_dir() or rows:
            audit.update(state="live", removes=_removal_inventory(session, facts, common))
        elif _known_audit(common, ws, ident):
            audit.update(state="draft", note="only an abandon retires a draft; the audit ID stays reserved")
        else:
            audit["state"] = "closed" if entries else "absent"
        _validate_mode(abandon=abandon, discard_uncollected=discard_uncollected, reason=reason)
        if unfinished:
            _resume_preflight(ws, ident, unfinished[-1], lifetime)
            worktree = unfinished[-1]["closing"]["removal"]["worktree"]
            if worktree is not None and os.path.isdir(worktree) and not os.path.islink(worktree):
                # The check a rerun makes before removing the checkout: whether it would stop again, with the
                # code that stop earns.
                try:
                    _revalidate_plan(unfinished[-1]["closing"], ws.repo, common)
                except StewartError as exc:
                    audit["refusal"] = {**exc.to_json(), "exit_code": _stop_code([{"reason": exc.reason}])}
        else:
            _preflight(ws, ident, common=common, session=session, rows=rows, abandon=abandon,
                       discard_uncollected=discard_uncollected, lifetime=lifetime, collection=collection)
    except StewartError as exc:
        audit["refusal"] = {**exc.to_json(), "exit_code": exc.exit_code}
    uuid = facts["session_uuid"] or (unfinished[-1]["session_uuid"] if unfinished else None)
    resources = presented(_closeout(common, ws.slug, ident, lifetime=uuid, dispose=set(dispose),
                                    closing_name=uuid or "<the new closing record>"))
    requests = [item for item in request_summaries(common, [])
                if (item.get("audit") or {}).get("audit_id") == ident and (item.get("audit") or {}).get("workspace")
                == ws.rel]
    return {"schema": CLOSEOUT_SCHEMA, "audit_id": ident, "workspace": ws.rel, "lifetime": uuid, "audit": audit,
            "resources": resources,
            "retained": {"closing_records": [entry["path"] for entry in entries],
                         "requests": [{"key": item["key"], "operation": item["operation"], "state": item["state"]}
                                      for item in requests],
                         "deliverables": [item["rid"] for item in resources if item.get("disposition") == "retained"],
                         "note": "closing records, request records and retained deliverables outlive the close"},
            "note": "a plan only: nothing was claimed or removed, and the close revalidates everything at use"}
