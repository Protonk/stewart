"""Recorded resources: managed creation, enrollment, uses, closeout and retirement.

A resource is something an audit's work depends on beyond its session: a
manager worktree, a branch, a temporary directory, an exported package or a
retained deliverable. Its records live at repository level under
``<common>/stewart/resources/<rid>/`` so they outlive every audit that used it.

Managed creation writes ``CREATE.json`` (the audit context and intended
identity) before any side effect and ``CREATED.json`` (the observed identity,
or the failure) after; an interrupted creation is visible and grants nothing.
Enrollment of an external resource writes ``ENROLLED.json`` from verified
observations; enrolled resources are tracked and explained but never removed by
Stewart. ``associations/`` records later users. Live sessions and drafts that
pin a path inside a worktree or directory resource are derived users. A use
ends only when a closing record verifies for its lifetime; any doubt keeps it.

Only ``close`` retires. A claim ``claims/<n>.json`` is created exclusively with
the identity, full contents inventory, HEAD or tip that the evaluation judged
removable; a new claim needs every earlier one released, and none follows a
retirement. A container retires only with every recorded resource inside it,
deepest first. At use, uses, identity and contents are revalidated; any change
releases the claim and keeps the resource. Removal runs through pinned descriptors and Git runs from the
common directory, so retiring a manager worktree never needs that worktree.
``ACKNOWLEDGED.json`` records the manager's acknowledgment of an observed
absence as retirement outside Stewart; it grants nothing.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid as _uuid

from stewart import _removal
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_UNVERIFIED, StewartError, read_regular

RESOURCES = "stewart/resources"
RESOURCE_SCHEMA = "stewart.resource/1"
OUTCOME_SCHEMA = "stewart.resource-outcome/1"
ASSOCIATION_SCHEMA = "stewart.resource-association/1"
CLAIM_SCHEMA = "stewart.resource-claim/1"
ENDED_SCHEMA = "stewart.resource-claim-end/1"
ACKNOWLEDGMENT_SCHEMA = "stewart.resource-acknowledgment/1"
CLOSEOUT_SCHEMA = "stewart.closeout/1"
MARKER = "stewart-resource.json"
MANAGED_LOCK = "stewart managed worktree "
KINDS = ("worktree", "branch", "directory", "export", "retained")
#: Kinds Stewart may remove once their creation is recorded; exports and retained
#: deliverables are deliberate retention and go only as disposed dependencies.
TEMPORARY = ("worktree", "branch", "directory")
_RID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
_IN_PROGRESS = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG")


def resource_id(value: object) -> str:
    if not isinstance(value, str) or not _RID.fullmatch(value):
        raise StewartError("name a resource by the identifier Stewart printed for it", reason="resource_missing")
    return value


def location(common: str, rid: str) -> Path:
    from stewart.workspace import contained
    return contained(Path(common), f"{RESOURCES}/{resource_id(rid)}")


def _absolute(value: object, what: str) -> Path:
    if (not isinstance(value, (str, Path)) or not str(value).startswith("/") or "\0" in str(value)
            or ".." in PurePosixPath(str(value)).parts or PurePosixPath(str(value)).as_posix() != str(value)):
        raise StewartError(f"{what} must be an absolute canonical path: {value}", reason="resource_location")
    return Path(str(value))


def _inside(path: str | Path, root: str | Path) -> bool:
    return Path(path) == Path(root) or Path(path).is_relative_to(Path(root))


def _git_common(common: str, *args: str, check: bool = True):
    """Git run from the common directory: a context that survives removal of any worktree."""
    from stewart._git import git
    return git(Path(common), *args, check=check)


# --- reading records -----------------------------------------------------------------------------------


def _read(path: Path, what: str) -> tuple[dict, str]:
    from stewart.session import capture_receipt
    return capture_receipt(path, what=what)


def _claims(directory: Path) -> list[dict]:
    """Every claim generation with how it ended; at most the last may be active."""
    claims = []
    names = sorted(name for name in (os.listdir(directory / "claims") if (directory / "claims").is_dir() else [])
                   if re.fullmatch(r"[0-9]{4}\.json", name))
    for name in names:
        number = name.removesuffix(".json")
        entry: dict = {"number": int(number), "path": str(directory / "claims" / name), "state": "active"}
        try:
            claim, digest = _read(directory / "claims" / name, "resource claim")
            if claim.get("schema") != CLAIM_SCHEMA:
                raise StewartError("unsupported claim schema", reason="resource_record_invalid")
            entry.update(claim=claim, sha256=digest)
            for ending in ("RETIRED", "RELEASED"):
                ended = directory / "claims" / f"{number}.{ending}.json"
                if os.path.lexists(ended):
                    value, _ = _read(ended, "claim outcome")
                    if value.get("claim_sha256") != digest:
                        raise StewartError(f"{ended.name} does not bind its claim", reason="resource_record_invalid")
                    entry.update(state=ending.lower(), ended=value)
            entry["attempts"] = sorted(item for item in os.listdir(directory / "claims")
                                       if item.startswith(f"{number}.ATTEMPT-"))
        except StewartError as exc:
            entry.update(state="invalid", problem={"reason": "resource_record_invalid", "message": str(exc)})
        claims.append(entry)
    return claims


def load(common: str, rid: str) -> dict:
    """One resource's records with per-record diagnostics; nothing is repaired or inferred."""
    directory = location(common, rid)
    view: dict = {"rid": rid, "path": str(directory), "problems": []}
    if not directory.is_dir() or directory.is_symlink():
        raise StewartError(f"no resource {rid} is recorded", reason="resource_missing",
                           next_steps=["discover lists every recorded resource"])
    record = None
    for name in ("CREATE.json", "ENROLLED.json"):
        if os.path.lexists(directory / name):
            try:
                record, digest = _read(directory / name, "resource record")
                if record.get("schema") != RESOURCE_SCHEMA or record.get("rid") != rid or record.get("kind") not in KINDS:
                    raise StewartError("unsupported resource record", reason="resource_record_invalid")
                from stewart.audits import validate_context
                validate_context(record.get("context"))
                view.update(record=record, record_sha256=digest, origin=record["origin"], kind=record["kind"],
                            context=record["context"])
            except StewartError as exc:
                view["problems"].append({"reason": "resource_record_invalid", "message": str(exc)})
    if record is None and not view["problems"]:
        view["problems"].append({"reason": "resource_record_invalid", "message": "no creation or enrollment record"})
    if view.get("origin") == "managed":
        try:
            outcome, digest = _read(directory / "CREATED.json", "resource outcome")
            if outcome.get("schema") != OUTCOME_SCHEMA or outcome.get("create_sha256") != view["record_sha256"]:
                raise StewartError("creation outcome does not bind its start record", reason="resource_record_invalid")
            view["created"] = outcome
            view["identity"] = outcome.get("identity") if outcome.get("status") == "created" else None
            view["creation"] = outcome.get("status")
        except StewartError as exc:
            if exc.reason == "record_missing":
                view["creation"] = "unresolved"
            else:
                view["problems"].append({"reason": "resource_record_invalid", "message": str(exc)})
    elif view.get("origin") == "enrolled":
        view["identity"] = record.get("identity")
        view["creation"] = "enrolled"
    view["associations"] = []
    for name in sorted(os.listdir(directory / "associations")) if (directory / "associations").is_dir() else []:
        if not name.endswith(".json"):
            continue
        try:
            value, _ = _read(directory / "associations" / name, "resource association")
            from stewart.audits import validate_context
            validate_context(value.get("context"))
            view["associations"].append({"name": name.removesuffix(".json"), "context": value["context"],
                                         "actor": value.get("actor")})
        except StewartError as exc:
            view["problems"].append({"reason": "resource_record_invalid", "message": str(exc)})
    view["claims"] = _claims(directory)
    view["problems"] += [claim["problem"] for claim in view["claims"] if "problem" in claim]
    if os.path.lexists(directory / "ACKNOWLEDGED.json"):
        try:
            view["acknowledged"], _ = _read(directory / "ACKNOWLEDGED.json", "retirement acknowledgment")
        except StewartError as exc:
            view["problems"].append({"reason": "resource_record_invalid", "message": str(exc)})
    return view


def rids(common: str) -> list[str]:
    from stewart.audits import _names
    return [name for name in _names(Path(common) / RESOURCES) or [] if _RID.fullmatch(name)]


def retired(common: str, rid: str) -> bool:
    try:
        return any(claim["state"] == "retired" for claim in load(common, rid)["claims"])
    except StewartError:
        return False


def _contexts(view: dict) -> list[dict]:
    contexts = [{"source": "creation" if view.get("origin") == "managed" else "enrollment", **view["context"]}] \
        if view.get("context") else []
    return contexts + [{"source": f"association {item['name']}", **item["context"]} for item in view["associations"]]


def context_keys(common: str, problems: list[dict]) -> list[tuple[str, str]]:
    keys = []
    for rid in rids(common):
        try:
            keys += [(item["slug"], item["audit_id"]) for item in _contexts(load(common, rid))]
        except StewartError as exc:
            problems.append({"reason": "resource_record_invalid", "location": str(Path(common) / RESOURCES / rid),
                             "message": str(exc)})
    return sorted(set(keys))


def contexts_for(common: str, slug: str, ident: str) -> list[dict]:
    found = []
    for rid in rids(common):
        try:
            found += [item for item in _contexts(load(common, rid)) if item["slug"] == slug and item["audit_id"] == ident]
        except StewartError:
            continue
    return found


# --- observations ---------------------------------------------------------------------------------------


def _snapshot(path: Path) -> dict | None:
    """Every entry below a resource path, read through descriptors pinned without following links.

    Nothing is excluded: a worktree's ``.git`` file and nested repositories are
    contents like any other. A directory on another filesystem is listed as
    ``foreign`` and not entered. None when the path is not a real directory
    reached without links.
    """
    from stewart import _util
    from stewart._bootstrap import capture_regular, entry_kind
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    entries: list[dict] = []
    foreign: list[str] = []
    try:
        with _removal.pinned(path.parent) as parent:
            top = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(top.st_mode):
                return None
            root = os.open(path.name, flags, dir_fd=parent)
    except (FileNotFoundError, _removal.Substituted, OSError):
        return None

    def visit(descriptor: int, prefix: str) -> None:
        try:
            names = sorted(os.listdir(descriptor))
        except OSError as exc:
            entries.append({"path": prefix or ".", "kind": "unreadable", "detail": exc.strerror})
            return
        for name in names:
            rel = f"{prefix}/{name}" if prefix else name
            try:
                found = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                kind = entry_kind(found.st_mode)
                item: dict = {"path": rel, "kind": kind}
                if kind == "directory":
                    if found.st_dev != top.st_dev:
                        foreign.append(rel)
                    else:
                        child = os.open(name, flags, dir_fd=descriptor)
                        try:
                            visit(child, rel)
                        finally:
                            os.close(child)
                elif kind == "file":
                    item.update({key: value for key, value in capture_regular(Path(name), dir_fd=descriptor).items()
                                 if key != "mode"})
                elif kind == "symlink":
                    item["target"] = os.readlink(name, dir_fd=descriptor)
                entries.append(item)
            except OSError as exc:
                entries.append({"path": rel, "kind": "unreadable", "detail": exc.strerror})

    try:
        opened = os.fstat(root)
        if (opened.st_dev, opened.st_ino) != (top.st_dev, top.st_ino):
            return None
        visit(root, "")
    finally:
        os.close(root)
    return {"identity": {"dev": top.st_dev, "ino": top.st_ino}, "entries": entries, "foreign": foreign,
            "sha256": _util.sha256_bytes(_util.receipt_json_bytes(entries))}


def _directory_identity(path: Path) -> dict | None:
    try:
        with _removal.pinned(path.parent) as parent:
            found = _removal.entry(parent, path.name)
    except (FileNotFoundError, _removal.Substituted):
        return None
    if found is None or not stat.S_ISDIR(found.st_mode):
        return None
    return {"dev": found.st_dev, "ino": found.st_ino}


def _admin_for(common: str, rid: str) -> Path | None:
    """The worktree administration carrying this resource's marker; a reused name without it is another lifetime."""
    from stewart._json import loads_control
    from stewart.audits import _names
    root = Path(common) / "worktrees"
    for name in _names(root) or []:
        _, data = read_regular(root / name / MARKER)
        try:
            value = loads_control(data) if data is not None else None
        except (ValueError, RecursionError):
            continue
        if isinstance(value, dict) and value.get("rid") == rid:
            return root / name
    return None


def _ref_tip(common: str, ref: str) -> tuple[str | None, bool]:
    """A ref's commit and whether it is symbolic, never following it."""
    listed = _git_common(common, "for-each-ref", "--format=%(objectname)%00%(symref)", ref, check=False)
    for line in listed.stdout.decode("utf-8", "replace").splitlines():
        commit, _, symref = line.partition("\0")
        return commit, bool(symref)
    return None, False


def _registrations(common: str) -> list[dict]:
    from stewart.close import _registrations as registered
    return registered(Path(common))


def _admin_worktree(admin: Path) -> str | None:
    from stewart.close import _admin_worktree as named
    return named(admin)


def _location(view: dict) -> dict:
    """The identity to observe: the recorded one, or the intended one of an unfinished or failed creation."""
    if view.get("identity"):
        return view["identity"]
    return ((view.get("record") or {}).get("intended") or {}) if view.get("creation") in ("unresolved", "failed") \
        else {}


def observe(common: str, view: dict) -> dict:
    """What is at the resource's recorded location now: present, absent, moved or changed, per kind."""
    identity = _location(view)
    kind = view.get("kind")
    if kind == "branch":
        commit, symbolic = _ref_tip(common, identity.get("ref", ""))
        if commit is None:
            return {"state": "absent", "ref": identity.get("ref")}
        return {"state": "present", "ref": identity.get("ref"), "commit": commit, "symbolic": symbolic}
    if kind == "retained":
        files = []
        for item in identity.get("files", []):
            info, _ = read_regular(Path(item["path"]))
            files.append({"path": item["path"], "kind": info["kind"], "sha256": info.get("sha256")})
        state = "absent" if files and all(item["kind"] == "missing" for item in files) else "present"
        return {"state": state, "files": files}
    path = identity.get("path")
    if not isinstance(path, str):
        return {"state": "unknown"}
    present = os.path.lexists(path)
    observation: dict = {"path": path}
    if kind == "worktree":
        admin = _admin_for(common, view["rid"])
        registered = [item for item in _registrations(common) if item.get("worktree") == path]
        observation.update(administration=str(admin) if admin else None, registered=bool(registered))
        moved = _admin_worktree(admin) if admin is not None else None
        if moved and moved != path:
            # Git moved the same lifetime (its marker names this resource): reported, never removed.
            return {**observation, "state": "moved", "registered_at": moved}
        if not present and admin is None and not registered:
            return {**observation, "state": "absent"}
        if not present:
            return {**observation, "state": "registration_remains"}
    elif not present:
        return {**observation, "state": "absent"}
    if kind == "export":
        info, _ = read_regular(Path(path) / "manifest.json")
        observation["manifest_sha256"] = info.get("sha256")
        return {**observation, "state": "present" if info.get("sha256") == identity.get("manifest_sha256")
                else "changed"}
    found = _directory_identity(Path(path))
    if found is None:
        return {**observation, "state": "replaced"}
    if kind == "directory" and identity.get("dev") is not None and \
            (found["dev"], found["ino"]) != (identity["dev"], identity["ino"]):
        return {**observation, "state": "replaced"}
    return {**observation, "state": "present"}


# --- uses ------------------------------------------------------------------------------------------------


def _session_paths(record: dict) -> list[str]:
    """Every absolute location a live session depends on."""
    paths = [record.get(key) for key in ("repo", "checkout_home", "audit_dir", "worktree", "helper_interpreter")]
    runtime = record.get("runtime") if isinstance(record.get("runtime"), dict) else {}
    paths.append(runtime.get("root"))
    invocation = (record.get("stewart") or {}).get("invocation") if isinstance(record.get("stewart"), dict) else None
    if isinstance(invocation, dict):
        paths += [invocation.get(key) for key in ("interpreter", "code_root", "launcher")]
    return [path for path in paths if isinstance(path, str) and path.startswith("/")]


class Index:
    """One read of the repository's uses: sessions, drafts and resource contexts with their liveness."""

    def __init__(self, common: str):
        from stewart._repository import SESSIONS
        from stewart.audits import _names, context_live, draft_records
        from stewart.session import capture_receipt
        self.common = common
        self.uses: list[dict] = []
        self.unverifiable: list[dict] = []
        self._live: dict[tuple, dict] = {}
        root = Path(common) / SESSIONS

        def listed(directory: Path) -> list[str]:
            # Storage that cannot be listed hides its uses; that doubt blocks retirement like an unreadable record.
            names = _names(directory)
            if names is None:
                self.unverifiable.append({"session": str(directory), "reason": "record_unreadable",
                                          "message": "storage is not a real directory; its uses cannot be read"})
            return names or []

        for slug in listed(root):
            for ident in listed(root / slug):
                session = root / slug / ident
                try:
                    record, _ = capture_receipt(session / "session.json", what="session record")
                    from stewart._repository import session_uuid
                    lifetime = session_uuid(record.get("session_uuid"))
                    rel = record.get("workspace")
                    if not isinstance(rel, str):
                        raise StewartError("session names no workspace", reason="session_identity")
                except StewartError as exc:
                    self.unverifiable.append({"session": str(session), "reason": exc.reason, "message": str(exc)})
                    continue
                context = {"workspace": rel, "slug": slug, "audit_id": ident, "lifetime": lifetime, "closed_before": []}
                self.uses.append({"source": f"session {slug}/{ident}", "context": context,
                                  "paths": _session_paths(record), "live": self.live(context)})
        from stewart.audits import AUDITS
        for slug in listed(Path(common) / AUDITS):
            for ident in listed(Path(common) / AUDITS / slug):
                for draft in draft_records(common, slug, ident):
                    if draft.get("state") == "invalid" or not draft.get("checkout"):
                        # A draft or registration that does not verify may name any checkout as its own.
                        self.unverifiable.append({"session": draft["path"], "reason": "draft_record_invalid",
                                                  "message": (draft.get("problem") or {}).get("message", "")})
                        continue
                    context = {"workspace": draft["workspace"], "slug": slug, "audit_id": ident, "lifetime": None,
                               "closed_before": draft.get("closed_before", [])}
                    self.uses.append({"source": f"{draft['kind']} {draft['name']}", "context": context,
                                      "paths": [draft["checkout"]], "live": self.live(context)})

    def live(self, context: dict) -> dict:
        from stewart.audits import context_live
        key = (context["slug"], context["audit_id"], context["lifetime"], tuple(context["closed_before"]))
        if key not in self._live:
            self._live[key] = context_live(self.common, context)
        return self._live[key]

    def resources(self) -> dict[str, dict]:
        if not hasattr(self, "_resources"):
            self._resources = {}
            for rid in rids(self.common):
                try:
                    self._resources[rid] = load(self.common, rid)
                except StewartError:
                    continue
        return self._resources

    def users(self, view: dict) -> list[dict]:
        """Every recorded and derived use of a resource, each with its liveness.

        A managed branch is also used by every user of the managed worktree
        created with it, while that worktree is not retired.
        """
        found = [{"source": item["source"], "audit": {key: item[key] for key in ("workspace", "audit_id",
                                                                                   "lifetime")},
                  "context": {key: item[key] for key in ("workspace", "slug", "audit_id", "lifetime",
                                                         "closed_before")},
                  **self.live(item)} for item in _contexts(view)]
        if view.get("kind") == "branch":
            for other in self.resources().values():
                if (other.get("kind") == "worktree" and (other.get("identity") or {}).get("branch_rid") == view["rid"]
                        and not any(claim["state"] == "retired" for claim in other["claims"])
                        and not other.get("acknowledged")):
                    found += [{**user, "source": f"{user['source']} via worktree {other['rid']}"}
                              for user in self.users(other)]
        path = (view.get("identity") or {}).get("path")
        if view.get("kind") in ("worktree", "directory") and isinstance(path, str):
            for use in self.uses:
                if any(_inside(pinned, path) for pinned in use["paths"]):
                    found.append({"source": f"{use['source']} (pins a path inside)",
                                  "audit": {key: use["context"][key] for key in ("workspace", "audit_id",
                                                                                 "lifetime")},
                                  "context": use["context"], **use["live"]})
        return found


# --- creation, enrollment and association ----------------------------------------------------------------


def _new(common: str) -> tuple[str, Path]:
    from stewart._repository import private_directories, private_storage
    rid = str(_uuid.uuid4())
    directory = location(common, rid)
    private_directories(private_storage(common), directory.parent)
    directory.mkdir(mode=0o700)
    return rid, directory


def _audit_context(ws, ident: str) -> tuple[str, dict]:
    """The recorded audit context for a new resource or use; a closed audit has no use left to give."""
    from stewart._repository import maintainer, session_location
    from stewart.assignment import audit_id
    from stewart.audits import context
    from stewart.close import closing_entries
    from stewart.session import capture_receipt
    common = maintainer(ws.repo)["common_dir"]
    audit_id(ident)
    session = session_location(common, ws, ident)
    lifetime = None
    if os.path.lexists(session):
        record, _ = capture_receipt(session / "session.json", what="session record")
        lifetime = record.get("session_uuid")
    value = context(common, ws, ident, lifetime)
    entries = closing_entries(common, ws, ident)
    if lifetime is not None and lifetime in [str(entry["session_uuid"]) for entry in entries]:
        raise StewartError(f"audit {ident}'s lifetime {lifetime} is closing; it can take no new resource",
                           reason="audit_closed")
    if lifetime is None and entries and not all(entry.get("released") for entry in entries):
        # A closed audit uses nothing more; a use recorded now could only end by abandoning it again.
        raise StewartError(f"audit {ident} is closed and its ID reserved; it can take no new resource",
                           reason="audit_closed", retained=[entry["path"] for entry in entries],
                           next_steps=["record the resource for a live or freshly drafted audit"])
    return common, value


def _recorded_checkout_homes(common: str) -> list[str]:
    from stewart._repository import SESSIONS
    from stewart.audits import _names
    from stewart.session import capture_receipt
    homes = set()
    root = Path(common) / SESSIONS
    for slug in _names(root) or []:
        for ident in _names(root / slug) or []:
            try:
                record, _ = capture_receipt(root / slug / ident / "session.json", what="session record")
            except StewartError:
                continue
            if isinstance(record.get("checkout_home"), str) and record["checkout_home"].startswith("/"):
                homes.add(record["checkout_home"])
    return sorted(homes)


def refuse_retiring(common: str, paths: list[str | Path], *, what: str) -> None:
    """Refuse to add a use inside a resource that an unfinished claim is retiring."""
    for rid in rids(common):
        try:
            view = load(common, rid)
        except StewartError:
            continue
        path = (view.get("identity") or {}).get("path")
        if not isinstance(path, str) or not any(claim["state"] == "active" for claim in view["claims"]):
            continue
        if any(_inside(item, path) for item in paths):
            raise StewartError(f"{what} would use {path}, which resource {rid} is being retired from",
                               reason="resource_retiring", retained=[view["path"]],
                               next_steps=[f"finish or inspect the retirement (close --resource {rid}) first"])


def _placement(common: str, path: Path, *, kind: str) -> None:
    """A managed path lies outside Stewart's own storage and every registered auditor checkout."""
    from stewart._bootstrap import MANAGER_HOME
    from stewart._repository import DEFAULT_CHECKOUT_HOME, _role_records
    from stewart._invocation import verified_invocation
    configured = os.environ.get("STEWART_MANAGER_HOME")
    forbidden = [(Path(common), "the Git common directory"), (Path.home() / DEFAULT_CHECKOUT_HOME, "the checkout home"),
                 (Path(configured) if configured else Path.home() / MANAGER_HOME, "the manager home")]
    running = verified_invocation()
    if running is not None:
        forbidden.append((running.launcher.parent.parent, "the running manager home"))
    forbidden += [(Path(row["worktree"]).parent, "a registered auditor checkout directory")
                  for row in _role_records(common)]
    # Checkout homes named by recorded sessions, not only the default one.
    forbidden += [(Path(home), "a recorded checkout home") for home in _recorded_checkout_homes(common)]
    for root, what in forbidden:
        if _inside(path, root) or _inside(root, path):
            raise StewartError(f"a managed {kind} cannot overlap {what}: {root}", reason="resource_location",
                               next_steps=["choose a path outside Stewart's storage and auditor checkouts"])
    try:
        with _removal.pinned(path.parent):
            pass
    except (FileNotFoundError, _removal.Substituted) as exc:
        raise StewartError(f"the parent of {path} must be an existing real directory", reason="resource_location",
                           retained=[str(path.parent)]) from exc
    if os.path.lexists(path):
        raise StewartError(f"{path} already exists; managed creation never adopts an existing entry",
                           reason="destination_exists", retained=[str(path)],
                           next_steps=["enroll an existing resource instead; enrollment grants no removal"])


def _record(directory: Path, name: str, value: dict) -> str:
    from stewart.session import capture_receipt, write_receipt
    write_receipt(directory / name, value)
    return capture_receipt(directory / name, what="resource record")[1]


#: The disposition each kind is created for: temporary resources may retire once no use remains;
#: exports and retained deliverables are evidence kept on purpose.
DISPOSITIONS = {"worktree": "temporary", "branch": "temporary", "directory": "temporary", "export": "retained",
                "retained": "retained"}


def _start(common: str, directory: Path, rid: str, kind: str, context: dict, intended: dict, actor: str | None) -> str:
    from stewart.session import now, tool_identity
    return _record(directory, "CREATE.json", {
        "schema": RESOURCE_SCHEMA, "rid": rid, "kind": kind, "origin": "managed", "recorded_at": now().isoformat(),
        "context": context, "intended": {**intended, "disposition": DISPOSITIONS[kind]}, "actor": actor,
        "stewart": tool_identity(),
        "note": "recorded before the creation's side effects; CREATED.json records what happened"})


def _finish(directory: Path, rid: str, create_sha256: str, identity: dict | None, error: dict | None) -> None:
    from stewart.session import now, tool_identity
    _record(directory, "CREATED.json", {
        "schema": OUTCOME_SCHEMA, "rid": rid, "recorded_at": now().isoformat(), "create_sha256": create_sha256,
        "status": "failed" if error else "created", "identity": identity, "error": error,
        "stewart": tool_identity()})


def _actor(actor: object) -> str:
    if not isinstance(actor, str) or not actor.strip():
        raise StewartError("a resource record needs an attributed actor", reason="actor_required",
                           next_steps=["rerun with --actor NAME"])
    return actor


def create_worktree(ws, ident: str, *, path: str, actor: str, branch: str | None = None,
                    existing_branch: str | None = None, start: str = "HEAD", request_key: str | None = None) -> dict:
    """Create a managed manager worktree (and a managed branch with ``branch``) for an audit.

    ``branch`` creates a new managed branch; ``existing_branch`` borrows one,
    which the worktree never gains deletion rights over; neither detaches HEAD.
    """
    from stewart.request_keys import keyed
    inputs = {"path": path, "branch": branch, "existing_branch": existing_branch, "start": start, "actor": actor}
    return keyed(ws, ident, "resource-create-worktree", inputs, request_key,
                 lambda plan: _create_worktree(ws, ident, path, actor, branch, existing_branch, start, plan),
                 outputs=lambda result: [{"kind": "resource", "resource": item["rid"],
                                          "path": str(Path(item["record"]) / "CREATED.json")}
                                         for item in result["resources"]])


def _create_worktree(ws, ident, path, actor, branch, existing_branch, start, plan) -> dict:
    from stewart._git import COMMIT_ID, git_text, resolve_commit
    from stewart.session import write_receipt
    _actor(actor)
    target = _absolute(path, "--path")
    if branch is not None and existing_branch is not None:
        raise StewartError("choose --branch (new, managed) or --existing-branch (borrowed), not both", reason="usage")
    common, context = _audit_context(ws, ident)
    _placement(common, target, kind="worktree")
    commit = resolve_commit(ws.repo, start, exact=False)
    for name in (branch, existing_branch):
        if name is not None and (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", name) or ".." in name
                                 or name.endswith((".lock", "/")) or "//" in name):
            raise StewartError(f"unsupported branch name: {name!r}", reason="resource_location")
    if branch is not None:
        found, _ = _ref_tip(common, f"refs/heads/{branch}")
        if found is not None:
            raise StewartError(f"branch {branch} already exists; borrow it with --existing-branch",
                               reason="destination_exists")
    if existing_branch is not None:
        found, _ = _ref_tip(common, f"refs/heads/{existing_branch}")
        if found is None:
            raise StewartError(f"branch {existing_branch} does not exist", reason="resource_missing")
    refuse_retiring(common, [target], what="a new worktree")
    created = []
    branch_rid = None
    if branch is not None:
        branch_rid, branch_dir = _new(common)
        branch_start = _start(common, branch_dir, branch_rid, "branch", context,
                              {"ref": f"refs/heads/{branch}", "commit": commit, "by": "worktree"}, actor)
        created.append((branch_rid, branch_dir, branch_start))
    rid, directory = _new(common)
    intended = {"path": str(target), "start": commit, "branch_rid": branch_rid,
                "branch": f"refs/heads/{branch}" if branch else None,
                "borrowed_branch": f"refs/heads/{existing_branch}" if existing_branch else None}
    started = _start(common, directory, rid, "worktree", context, intended, actor)
    plan([{"kind": "resource", "resource": item[0], "path": str(item[1] / "CREATED.json")}
          for item in [*created, (rid, directory, started)]])
    arguments = ["worktree", "add", "--lock", "--reason", f"{MANAGED_LOCK}{rid}: retire it with stewart close --resource"]
    arguments += (["-b", branch, str(target), commit] if branch else [str(target), existing_branch] if existing_branch
                  else ["--detach", str(target), commit])
    from stewart._git import git
    try:
        git(ws.repo, *arguments)
        admin = Path(git_text(target, "rev-parse", "--absolute-git-dir"))
        if admin.parent != Path(common) / "worktrees":
            raise StewartError("the new worktree's administration is not under the common directory",
                               reason="resource_identity")
        write_receipt(admin / MARKER, {"schema": RESOURCE_SCHEMA, "rid": rid})
        head = git_text(target, "rev-parse", "HEAD")
        identity = {"path": str(target), "git_admin": str(admin), "head": head,
                    "branch": intended["branch"] or intended["borrowed_branch"], "borrowed_branch":
                    intended["borrowed_branch"], "branch_rid": branch_rid, "lock": arguments[4]}
        error = None
    except (StewartError, OSError) as exc:
        identity, error = None, (exc.to_json() if isinstance(exc, StewartError) else
                                 {"reason": "resource_creation", "message": str(exc)})
    for item_rid, item_dir, item_started in created:
        tip, _ = _ref_tip(common, f"refs/heads/{branch}")
        _finish(item_dir, item_rid, item_started,
                None if error or tip is None or COMMIT_ID.fullmatch(tip) is None else
                {"ref": f"refs/heads/{branch}", "commit": tip, "created_commit": commit}, error)
    _finish(directory, rid, started, identity, error)
    if error:
        raise StewartError(f"managed worktree creation failed: {error['message']}", reason="resource_creation",
                           retained=[str(directory), str(target)],
                           next_steps=["inspect the recorded start and outcome; a partial result grants no removal"])
    resources = [{"rid": item[0], "kind": "branch", "record": str(item[1])} for item in created]
    resources.append({"rid": rid, "kind": "worktree", "record": str(directory)})
    return {"audit_id": ident, "resources": resources, "worktree": str(target), "identity": identity}


def create_branch(ws, ident: str, *, branch: str, actor: str, start: str = "HEAD",
                  request_key: str | None = None) -> dict:
    """Create a managed branch for an audit with a create-only ref update."""
    from stewart.request_keys import keyed
    return keyed(ws, ident, "resource-create-branch", {"branch": branch, "start": start, "actor": actor}, request_key,
                 lambda plan: _create_branch(ws, ident, branch, actor, start, plan),
                 outputs=lambda result: [{"kind": "resource", "resource": result["rid"],
                                          "path": str(Path(result["record"]) / "CREATED.json")}])


def _create_branch(ws, ident, branch, actor, start, plan) -> dict:
    from stewart._git import create_refs, resolve_commit
    _actor(actor)
    if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", branch) or ".." in branch:
        raise StewartError(f"unsupported branch name: {branch!r}", reason="resource_location")
    common, context = _audit_context(ws, ident)
    commit = resolve_commit(ws.repo, start, exact=False)
    ref = f"refs/heads/{branch}"
    if _ref_tip(common, ref)[0] is not None:
        raise StewartError(f"branch {branch} already exists; enroll it instead", reason="destination_exists")
    rid, directory = _new(common)
    started = _start(common, directory, rid, "branch", context, {"ref": ref, "commit": commit, "by": "create-branch"},
                     actor)
    plan([{"kind": "resource", "resource": rid, "path": str(directory / "CREATED.json")}])
    try:
        create_refs(Path(common), {ref: commit})
        identity, error = {"ref": ref, "commit": commit, "created_commit": commit}, None
    except StewartError as exc:
        identity, error = None, exc.to_json()
    _finish(directory, rid, started, identity, error)
    if error:
        raise StewartError(f"managed branch creation failed: {error['message']}", reason="resource_creation",
                           retained=[str(directory)])
    return {"audit_id": ident, "rid": rid, "record": str(directory), "identity": identity}


def create_directory(ws, ident: str, *, path: str, actor: str, request_key: str | None = None) -> dict:
    """Create a managed temporary directory (mode 0700) for an audit."""
    from stewart.request_keys import keyed
    return keyed(ws, ident, "resource-create-directory", {"path": path, "actor": actor}, request_key,
                 lambda plan: _create_directory(ws, ident, path, actor, plan),
                 outputs=lambda result: [{"kind": "resource", "resource": result["rid"],
                                          "path": str(Path(result["record"]) / "CREATED.json")}])


def _create_directory(ws, ident, path, actor, plan) -> dict:
    _actor(actor)
    target = _absolute(path, "--path")
    common, context = _audit_context(ws, ident)
    _placement(common, target, kind="directory")
    refuse_retiring(common, [target], what="a new directory")
    rid, directory = _new(common)
    started = _start(common, directory, rid, "directory", context, {"path": str(target)}, actor)
    plan([{"kind": "resource", "resource": rid, "path": str(directory / "CREATED.json")}])
    try:
        with _removal.pinned(target.parent) as parent:
            os.mkdir(target.name, mode=0o700, dir_fd=parent)
            found = os.stat(target.name, dir_fd=parent, follow_symlinks=False)
        identity, error = {"path": str(target), "dev": found.st_dev, "ino": found.st_ino}, None
    except (OSError, _removal.Substituted) as exc:
        identity, error = None, {"reason": "resource_creation", "message": str(exc)}
    _finish(directory, rid, started, identity, error)
    if error:
        raise StewartError(f"managed directory creation failed: {error['message']}", reason="resource_creation",
                           retained=[str(directory)])
    return {"audit_id": ident, "rid": rid, "record": str(directory), "identity": identity}


def record_output(ws, ident: str, *, kind: str, actor: str | None, identity_for, perform,
                  plan_outputs: list[dict]) -> tuple:
    """Record an export or retained deliverable as a managed resource around its creating operation.

    The start record precedes the operation's writes; the outcome binds the
    identity the operation produced, or its failure.
    """
    from stewart._repository import maintainer
    from stewart.audits import context
    from stewart.request_keys import plan
    from stewart.session import capture_receipt
    common = maintainer(ws.repo)["common_dir"]
    session = None
    from stewart._repository import session_location
    location_ = session_location(common, ws, ident)
    try:
        record, _ = capture_receipt(location_ / "session.json", what="session record")
        session = record.get("session_uuid")
    except StewartError:
        session = None
    rid, directory = _new(common)
    started = _start(common, directory, rid, kind, context(common, ws, ident, session),
                     {"by": kind, "intended": plan_outputs}, actor)
    plan([*plan_outputs, {"kind": "resource", "resource": rid, "path": str(directory / "CREATED.json")}])
    try:
        result = perform()
    except BaseException as exc:
        error = exc.to_json() if isinstance(exc, StewartError) else {"reason": "resource_creation",
                                                                     "message": f"{type(exc).__name__}: {exc}"}
        if isinstance(exc, (StewartError, OSError)):
            _finish(directory, rid, started, None, error)
        raise
    _finish(directory, rid, started, identity_for(result), None)
    return result, rid


def enroll(ws, ident: str, *, kind: str, actor: str, path: str | None = None, branch: str | None = None,
           note: str | None = None, request_key: str | None = None) -> dict:
    """Track an externally created resource from verified observations; it is never removal-eligible."""
    from stewart.request_keys import keyed
    inputs = {"kind": kind, "path": path, "branch": branch, "actor": actor, "note": note}
    return keyed(ws, ident, "resource-enroll", inputs, request_key,
                 lambda plan: _enroll(ws, ident, kind, actor, path, branch, note, plan),
                 outputs=lambda result: [{"kind": "resource", "resource": result["rid"],
                                          "path": str(Path(result["record"]) / "ENROLLED.json")}])


def _enroll(ws, ident, kind, actor, path, branch, note, plan) -> dict:
    from stewart._git import git_text
    from stewart.session import now, tool_identity
    _actor(actor)
    common, context = _audit_context(ws, ident)
    if kind == "branch":
        if branch is None or path is not None:
            raise StewartError("enroll a branch with --branch only", reason="usage")
        ref = f"refs/heads/{branch}"
        commit, symbolic = _ref_tip(common, ref)
        if commit is None or symbolic:
            raise StewartError(f"branch {branch} is absent or symbolic", reason="resource_missing")
        identity = {"ref": ref, "commit": commit}
    elif kind in ("worktree", "directory"):
        if path is None or branch is not None:
            raise StewartError(f"enroll a {kind} with --path only", reason="usage")
        target = _absolute(path, "--path")
        found = _directory_identity(target)
        if found is None:
            raise StewartError(f"{target} is not a real directory reached without links", reason="resource_missing")
        identity = {"path": str(target), **found, "contents_sha256": (_snapshot(target) or {}).get("sha256")}
        if kind == "worktree":
            registered = [item for item in _registrations(common) if item.get("worktree") == str(target)]
            if not registered:
                raise StewartError(f"Git registers no worktree at {target}", reason="resource_missing")
            identity.update(head=registered[0].get("HEAD"), branch=registered[0].get("branch"),
                            git_admin=git_text(target, "rev-parse", "--absolute-git-dir"))
    else:
        raise StewartError("enroll a worktree, branch or directory", reason="usage")
    refuse_retiring(common, [identity["path"]] if "path" in identity else [], what="an enrollment")
    rid, directory = _new(common)
    plan([{"kind": "resource", "resource": rid, "path": str(directory / "ENROLLED.json")}])
    _record(directory, "ENROLLED.json", {
        "schema": RESOURCE_SCHEMA, "rid": rid, "kind": kind, "origin": "enrolled", "recorded_at": now().isoformat(),
        "context": context, "identity": identity, "actor": actor, "note": note, "stewart": tool_identity(),
        "disposition": "manual",
        "acknowledgment": "tracked for association and closeout explanations only; Stewart never removes it"})
    return {"audit_id": ident, "rid": rid, "record": str(directory), "identity": identity}


def associate(ws, ident: str, *, rid: str, actor: str, request_key: str | None = None) -> dict:
    """Record that an audit uses a resource; the use ends only with that audit lifetime's closing record."""
    from stewart.request_keys import keyed
    return keyed(ws, ident, "resource-associate", {"actor": actor}, request_key,
                 lambda plan: _associate(ws, ident, rid, actor, plan), resources=[rid],
                 outputs=lambda result: [{"kind": "association", "resource": rid, "path": result["path"]}])


def _associate(ws, ident, rid, actor, plan) -> dict:
    from stewart.session import now, stamp, tool_identity
    _actor(actor)
    common, context = _audit_context(ws, ident)
    view = load(common, rid)
    if any(claim["state"] == "active" for claim in view["claims"]) or view.get("acknowledged") or \
            any(claim["state"] == "retired" for claim in view["claims"]):
        raise StewartError(f"resource {rid} is retiring or retired; it can take no new use",
                           reason="resource_retiring", retained=[view["path"]])
    directory = Path(view["path"]) / "associations"
    directory.mkdir(mode=0o700, exist_ok=True)
    name = stamp()
    plan([{"kind": "association", "resource": rid, "path": str(directory / f"{name}.json")}])
    _record(directory, f"{name}.json", {"schema": ASSOCIATION_SCHEMA, "rid": rid, "name": name,
                                        "recorded_at": now().isoformat(), "context": context, "actor": actor,
                                        "stewart": tool_identity()})
    return {"audit_id": ident, "rid": rid, "association": name, "path": str(directory / f"{name}.json")}


# --- closeout evaluation ----------------------------------------------------------------------------------


def _reachable_elsewhere(common: str, commit: str, excluded: set[str]) -> list[str]:
    """Refs outside Stewart's session namespaces and ``excluded`` that contain ``commit``."""
    listed = _git_common(common, "for-each-ref", "--contains", commit, "--format=%(refname)", check=False)
    return [ref for ref in listed.stdout.decode("utf-8", "replace").split()
            if not ref.startswith("refs/stewart/") and ref not in excluded]


def _worktree_findings(common: str, identity: dict, rid: str, disposed_paths: list[str], excluded: set[str]) -> list[str]:
    """Why a managed worktree cannot be removed now; empty when it can."""
    from stewart._git import git
    path = Path(identity["path"])
    admin = _admin_for(common, rid)
    if admin is None or str(admin) != identity.get("git_admin"):
        return ["its Git administration with this resource's marker is not where it was recorded"]
    _, data = read_regular(admin / "gitdir")
    if data is None or os.fsdecode(data.strip()) != str(path / ".git"):
        return ["its Git administration names another location; it was moved or replaced"]
    info, gitfile = read_regular(path / ".git")
    if gitfile is None or gitfile.strip() != f"gitdir: {admin}".encode():
        return ["its .git is not the regular gitdir file naming its administration"]
    findings = []
    status = git(path, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored", check=False)
    if status.returncode:
        return ["Git cannot report its status"]
    entries = [os.fsdecode(item[3:]) for item in status.stdout.split(b"\0") if len(item) > 3]
    unexplained = [entry for entry in entries if not any(_inside(path / entry.rstrip("/"), disposed)
                                                         for disposed in disposed_paths)]
    if unexplained:
        findings.append("uncommitted, untracked or ignored content (never cleaned by Stewart): "
                        + ", ".join(sorted(unexplained)[:10]))
    head = _worktree_head(path)
    if head is None:
        findings.append("its HEAD cannot be read")
    elif head != identity.get("head") and not _reachable_elsewhere(common, head, excluded):
        findings.append(f"HEAD {head[:12]} carries commits no other ref contains")
    local = git(path, "for-each-ref", "--format=%(refname)", "refs/worktree", "refs/bisect", check=False)
    if local.stdout.strip():
        findings.append("it holds per-worktree refs: " + local.stdout.decode().strip().replace("\n", ", "))
    if any(os.path.lexists(admin / name) for name in _IN_PROGRESS):
        findings.append("a rebase, merge, cherry-pick, revert or bisect is in progress")
    return findings


def _running_paths() -> list[Path]:
    import sys
    import stewart
    from stewart._invocation import verified_invocation
    paths = [Path(stewart.__file__).parent, Path(sys.prefix), Path(sys.executable)]
    running = verified_invocation()
    if running is not None:
        paths += [running.code_root, running.launcher]
    return paths


def _foreign_inside(common: str, path: str, excluded: set[str]) -> list[str]:
    """Checkouts Git or the role registry places at or below ``path``, other than ``excluded`` ones.

    A registry row that cannot be read might place one there, so it is named too.
    """
    from stewart._repository import role_rows
    found = [item["worktree"] for item in _registrations(common)
             if item.get("worktree") and _inside(item["worktree"], path) and item["worktree"] not in excluded]
    rows, problems = role_rows(common)
    found += [row["worktree"] for row in rows if _inside(row["worktree"], path) and row["worktree"] not in excluded]
    found += [f"(unreadable role registry row {item['location']})" for item in problems]
    return sorted(set(found))


def _branch_refs(common: str, rids_: set[str]) -> set[str]:
    """The refs of managed branches among ``rids_`` and of branches whose claims are active."""
    refs = set()
    for rid in rids(common):
        try:
            view = load(common, rid)
        except StewartError:
            continue
        ref = (view.get("identity") or {}).get("ref")
        if view.get("kind") == "branch" and ref and (rid in rids_ or any(claim["state"] == "active"
                                                                          for claim in view["claims"])):
            refs.add(ref)
    return refs


def _contained(common: str, rid: str, path: str) -> list[dict]:
    """Recorded resources at or below ``path`` that are neither retired nor acknowledged."""
    found = []
    for other in rids(common):
        if other == rid:
            continue
        try:
            inner = load(common, other)
        except StewartError:
            continue
        if any(claim["state"] == "retired" for claim in inner["claims"]) or inner.get("acknowledged"):
            continue
        identity = inner.get("identity") or {}
        locations = [identity["path"]] if isinstance(identity.get("path"), str) else \
            [item["path"] for item in identity.get("files") or []]
        if any(_inside(item, path) for item in locations):
            found.append({"rid": other, "kind": inner.get("kind"), "identity": identity, "locations": locations,
                          "origin": inner.get("origin")})
    return found


def evaluate(common: str, view: dict, index: Index, *, ending=None, dispose: set[str] = frozenset(),
             inventory: set[str] = frozenset()) -> dict:
    """One resource's closeout disposition now, with every reason; nothing is written.

    ``ending(context)`` says which uses the calling close ends (its own audit
    lifetime); ``dispose`` names contained exports or retained deliverables the
    manager decided to remove with their container; ``inventory`` names the
    other resources the same close removes (only those whose own evaluation is
    ``remove``). A removable resource's evaluation carries the frozen state a
    claim records, taken now, so nothing judged here differs from what is frozen.
    """
    rid = view["rid"]
    result: dict = {"rid": rid, "kind": view.get("kind"), "origin": view.get("origin"),
                    "identity": view.get("identity"), "users": [], "reasons": [], "notes": []}
    borrowed = (view.get("identity") or {}).get("borrowed_branch")
    if borrowed:
        result["notes"].append(f"borrowed branch {borrowed} belongs to no resource here; retiring this worktree "
                               "never removes it")
    if view["problems"]:
        return {**result, "disposition": "blocked", "reasons": [item["message"] for item in view["problems"]]}
    claims = view["claims"]
    if any(claim["state"] == "retired" for claim in claims):
        return {**result, "disposition": "retired"}
    if view.get("acknowledged"):
        return {**result, "disposition": "acknowledged", "observation": observe(common, view)}
    active = [claim for claim in claims if claim["state"] == "active"]
    if active:
        return {**result, "disposition": "claimed", "claim": active[-1]["path"],
                "reasons": ["an unfinished claim holds it; close --resource finishes the retirement"]}
    observation = observe(common, view)
    result["observation"] = observation
    if view.get("creation") in ("unresolved", "failed"):
        # Stewart never owns what an interrupted or failed creation left; a person clears it and acknowledges.
        state = observation["state"]
        what = ("its creation was interrupted: the start record exists without an outcome"
                if view["creation"] == "unresolved" else "its recorded creation failed")
        return {**result, "disposition": "missing" if state == "absent" else "blocked",
                "reasons": [what + ", so ownership of whatever is found at its intended location is not established"
                            + ("; nothing is there now: acknowledge it if that is final" if state == "absent" else
                               "; remove what is there by hand if it is not wanted, then acknowledge it")]}
    users = index.users(view)
    result["users"] = [{**user, "ended_by_this_close": bool(ending and ending(user["context"]))} for user in users]
    live = [user for user in result["users"] if user["live"] and not user["ended_by_this_close"]]
    if observation["state"] in ("absent", "registration_remains"):
        remedy = ("; Git still registers it: `git worktree remove -f -f <path>` drops a locked registration"
                  if observation["state"] == "registration_remains" else "")
        return {**result, "disposition": "missing",
                "reasons": ["the recorded resource is absent; acknowledge its retirement outside Stewart if that is "
                            "what happened" + remedy]}
    if observation["state"] == "moved":
        return {**result, "disposition": "blocked",
                "reasons": [f"Git moved it to {observation['registered_at']}; it is kept where it is"]}
    if view.get("origin") == "enrolled":
        return {**result, "disposition": "manual",
                "reasons": ["enrolled external resource: tracked and explained, retired by hand and acknowledged"]}
    if view.get("kind") in ("export", "retained"):
        return {**result, "disposition": "retained",
                "reasons": ["deliberate retention; removed only as a disposed dependency of a retiring container"]}
    if live:
        return {**result, "disposition": "shared",
                "reasons": ["in use by " + "; ".join(f"{user['audit']['workspace']}:{user['audit']['audit_id']} "
                                                     f"({user['source']}, {user['state']})" for user in live)]}
    reasons = []
    identity = view.get("identity") or {}
    if observation["state"] != "present":
        reasons.append(f"what is at its location is {observation['state']}")
    if index.unverifiable and view.get("kind") in ("worktree", "directory"):
        reasons.append("records that cannot be read may use it: "
                       + ", ".join(item["session"] for item in index.unverifiable))
    path = identity.get("path")
    disposed, contained = [], []
    if isinstance(path, str):
        if any(_inside(item, path) for item in _running_paths()):
            reasons.append("the running Stewart package or interpreter lies inside it")
        # Its own registration, the worktrees retiring with it, and the checkouts of the uses this close
        # ends (removed before any claim) are not foreign.
        ended = {pinned for use in index.uses if ending and ending(use["context"]) for pinned in use["paths"]}
        foreign = _foreign_inside(common, path, {path} | _inventory_paths(common, inventory) | ended)
        if foreign:
            reasons.append("other checkouts are registered inside it: " + ", ".join(foreign))
        for inner in _contained(common, rid, path):
            if inner["rid"] in dispose and inner["kind"] in ("export", "retained"):
                disposed.append({key: inner[key] for key in ("rid", "kind", "identity", "locations")})
            elif inner["rid"] in inventory:
                continue
            elif inner["kind"] == "retained" and view.get("kind") == "worktree":
                # Committed, unchanged files are history (status decides); they retire with their container.
                contained.append({key: inner[key] for key in ("rid", "kind", "identity")})
            elif inner["kind"] in ("export", "retained"):
                reasons.append(f"it contains recorded {inner['kind']} {inner['rid']}; give it a durable destination "
                               f"or decide its disposal with --dispose {inner['rid']}")
            else:
                reasons.append(f"it contains recorded {inner['kind']} {inner['rid']}; retire that one first "
                               f"(close --resource {inner['rid']}, or by hand and acknowledged)")
    result["disposed"] = disposed
    retiring = _inventory_paths(common, inventory)
    retiring_refs = _branch_refs(common, inventory)
    snapshot = None
    if view.get("kind") in ("worktree", "directory") and isinstance(path, str):
        snapshot = _snapshot(Path(path))
        if snapshot is None:
            reasons.append("it cannot be read through real directories")
        elif snapshot["foreign"]:
            reasons.append("another filesystem is mounted inside it: " + ", ".join(snapshot["foreign"]))
        elif identity.get("dev") is not None and (snapshot["identity"]["dev"], snapshot["identity"]["ino"]) != \
                (identity["dev"], identity["ino"]):
            reasons.append("the directory at its path is not the one created")
    if view.get("kind") == "worktree":
        # Its branch, and every branch retiring with it, cannot vouch for its commits.
        reasons += _worktree_findings(common, identity, rid, [loc for item in disposed for loc in item["locations"]],
                                      retiring_refs | ({identity["branch"]} if identity.get("branch_rid") in inventory
                                                       else set()))
    tip = None
    if view.get("kind") == "branch":
        tip, symbolic = _ref_tip(common, identity["ref"])
        if symbolic:
            reasons.append("the branch ref is symbolic")
        elif tip is not None and tip != identity.get("created_commit") and \
                not _reachable_elsewhere(common, tip, {identity["ref"]} | retiring_refs):
            reasons.append(f"its tip {tip[:12]} carries commits no other ref contains (unmerged work)")
        holders = [item["worktree"] for item in _registrations(common)
                   if item.get("branch") == identity["ref"] and item["worktree"] not in retiring]
        if holders:
            reasons.append("checked out by " + ", ".join(holders))
    if reasons:
        return {**result, "disposition": "blocked", "reasons": reasons}
    frozen = {"identity": dict(identity)}
    if snapshot is not None:
        frozen.update(snapshot={key: snapshot[key] for key in ("identity", "entries", "sha256")})
    if view.get("kind") == "worktree":
        frozen["head"] = _worktree_head(Path(path))
    if view.get("kind") == "branch":
        frozen["tip"] = tip
    return {**result, "disposition": "remove", "contained_retained": contained, "frozen": frozen}


def _inventory_paths(common: str, inventory: set[str]) -> set[str]:
    """Paths of the worktrees retired in the same inventory, which are removed before any branch."""
    paths = set()
    for rid in inventory:
        try:
            view = load(common, rid)
        except StewartError:
            continue
        if view.get("kind") == "worktree" and isinstance((view.get("identity") or {}).get("path"), str):
            paths.add(view["identity"]["path"])
    return paths


def _worktree_head(path: Path) -> str | None:
    from stewart._git import git
    try:
        found = git(path, "rev-parse", "HEAD", check=False)
    except OSError:
        return None
    return os.fsdecode(found.stdout).strip() if not found.returncode else None


def closeout(ws, ident: str, *, lifetime: str | None, dispose: list[str] = (), closing_name: str | None = None) -> list[dict]:
    """How every resource this audit uses would be disposed of by its close; writes nothing."""
    from stewart._repository import maintainer
    common = maintainer(ws.repo)["common_dir"]
    return presented(_closeout(common, ws.slug, ident, lifetime=lifetime, dispose=set(dispose),
                               closing_name=closing_name))


def presented(evaluations: list[dict]) -> list[dict]:
    """Evaluations as views show them: the frozen inventory a claim would record stays in the claim."""
    return [{key: value for key, value in item.items() if key != "frozen"} for item in evaluations]


def _ending(slug: str, ident: str, lifetime: str | None, closing_name: str | None):
    def ending(context: dict) -> bool:
        if context["slug"] != slug or context["audit_id"] != ident:
            return False
        if context["lifetime"] is not None:
            return context["lifetime"] == lifetime
        return closing_name is not None and closing_name not in context["closed_before"]
    return ending


def used_by(common: str, slug: str, ident: str) -> list[str]:
    """Every recorded resource this audit uses now, by record or by a path its live records pin."""
    index = Index(common)
    found = []
    for rid in rids(common):
        try:
            view = load(common, rid)
        except StewartError:
            found.append(rid)
            continue
        if any(user["context"]["slug"] == slug and user["context"]["audit_id"] == ident
               for user in index.users(view)):
            found.append(rid)
    return found


def _closeout(common: str, slug: str, ident: str, *, lifetime, dispose: set[str], closing_name,
              used: list[str] | None = None) -> list[dict]:
    """Evaluate the resources this audit uses (``used``, when the close fixed them before its own removal).

    The removable set is found by fixpoint: start from every managed temporary
    resource, evaluate each against the others it would retire with, and drop
    any that is not removable until the set no longer shrinks. A container is
    removable only if everything recorded inside it is removed with it.
    """
    index = Index(common)
    ending = _ending(slug, ident, lifetime, closing_name or lifetime)
    views = []
    for rid in used if used is not None else used_by(common, slug, ident):
        try:
            views.append(load(common, rid))
        except StewartError as exc:
            views.append({"rid": rid, "disposition": "blocked", "reasons": [str(exc)]})
    loaded = [view for view in views if "claims" in view]
    removable = {view["rid"] for view in loaded if view.get("origin") == "managed" and view.get("kind") in TEMPORARY}
    dropped: dict[str, list[str]] = {}
    while True:
        evaluated = {view["rid"]: evaluate(common, view, index, ending=ending, dispose=dispose,
                                           inventory=removable - {view["rid"]}) for view in loaded}
        # The set only shrinks, so the loop ends; each resource keeps the reasons it was first dropped for.
        settled = {rid for rid in removable if evaluated[rid]["disposition"] == "remove"}
        for rid in removable - settled:
            dropped.setdefault(rid, evaluated[rid].get("reasons") or [])
        if settled == removable:
            break
        removable = settled
    for rid, item in evaluated.items():
        if item["disposition"] == "remove" and rid not in removable:
            # Removable alone only because resources this close keeps were evaluated as staying.
            evaluated[rid] = {**item, "disposition": "blocked", "frozen": None,
                              "reasons": dropped.get(rid, []) + ["it is removable only while resources retiring "
                                                                 "with it are kept; retire it with close --resource "
                                                                 "once that is settled"]}
    return [evaluated.get(view["rid"], view) for view in views]


def resources_for_audit(common: str, slug: str, ident: str) -> list[dict]:
    """Recorded resources naming this audit as creator or user, without evaluating eligibility."""
    found = []
    for rid in rids(common):
        try:
            view = load(common, rid)
        except StewartError:
            continue
        if any(item["slug"] == slug and item["audit_id"] == ident for item in _contexts(view)):
            found.append({"rid": rid, "kind": view.get("kind"), "origin": view.get("origin")})
    return found


# --- claims and retirement ---------------------------------------------------------------------------------


def _claim(common: str, view: dict, evaluation: dict, claimant: dict) -> dict | None:
    """Create the next claim generation exclusively; None when another claimant won it or it is retired."""
    from stewart.session import now, stamp, tool_identity, write_receipt
    directory = Path(view["path"]) / "claims"
    directory.mkdir(mode=0o700, exist_ok=True)
    claims = _claims(Path(view["path"]))
    # One active claim at a time, and none once the resource is retired: a racing close that
    # evaluated before another one finished finds the resource already claimed or gone.
    if any(claim["state"] in ("active", "invalid", "retired") for claim in claims):
        return None
    number = len(claims) + 1
    document = {"schema": CLAIM_SCHEMA, "rid": view["rid"], "number": number, "recorded_at": now().isoformat(),
                "claimant": claimant, "frozen": evaluation.get("frozen") or {"identity": view.get("identity")},
                "disposed": [{**item, "frozen": {"identity": item["identity"]}} for item in evaluation.get("disposed", [])],
                "contained": evaluation.get("contained_retained", []), "stewart": tool_identity()}
    staged = directory / f".{number:04d}.json.{stamp()}.staged"
    write_receipt(staged, document)
    try:
        os.link(staged, directory / f"{number:04d}.json")
    except FileExistsError:
        return None
    finally:
        staged.unlink()
    return _claims(Path(view["path"]))[number - 1]


def _end(claim: dict, ending: str, value: dict) -> None:
    from stewart.session import now, tool_identity, write_receipt
    location_ = Path(claim["path"]).with_name(f"{claim['number']:04d}.{ending}.json")
    write_receipt(location_, {"schema": ENDED_SCHEMA, "claim_sha256": claim["sha256"], "ending": ending.lower(),
                              "recorded_at": now().isoformat(), **value, "stewart": tool_identity()})


def _subset(current: list[dict], frozen: list[dict]) -> list[str]:
    """Entries present now that the frozen inventory does not hold exactly; empty when only removals happened."""
    recorded = {item["path"]: item for item in frozen}
    return sorted(item["path"] for item in current if recorded.get(item["path"]) != item)


def _revalidate(common: str, view: dict, claim: dict, index: Index) -> list[str]:
    """Why the claimed resource no longer matches its frozen state or freedom from use; empty when it does.

    A claim that already began removing (it has attempt records) accepts
    contents that only lost entries; anything added or changed is kept.
    """
    document = claim["claim"]
    frozen = document["frozen"]
    identity = frozen["identity"]
    started = bool(claim.get("attempts"))
    findings = []
    live = [user for user in index.users(view) if user["live"]]
    if live:
        findings.append("a live use appeared: " + "; ".join(f"{user['audit']['audit_id']} ({user['source']})"
                                                           for user in live))
    if index.unverifiable and view["kind"] in ("worktree", "directory"):
        findings.append("records that cannot be read may use it: "
                        + ", ".join(item["session"] for item in index.unverifiable))
    kind = view["kind"]
    if kind in ("worktree", "directory"):
        path = Path(identity["path"])
        snapshot = _snapshot(path)
        recorded = frozen.get("snapshot") or {}
        if snapshot is None:
            if not (started and not os.path.lexists(path)):
                findings.append("its directory cannot be read through real directories")
        else:
            if snapshot["identity"] != recorded.get("identity"):
                findings.append("the directory at its path is not the one frozen in the claim")
            elif snapshot["foreign"]:
                findings.append("another filesystem is mounted inside it: " + ", ".join(snapshot["foreign"]))
            elif started:
                added = _subset(snapshot["entries"], recorded.get("entries") or [])
                if added:
                    findings.append("contents were added or changed after the claim was frozen: "
                                    + ", ".join(added[:10]))
            elif snapshot["sha256"] != recorded.get("sha256"):
                findings.append("its contents changed after the claim was frozen")
            foreign = _foreign_inside(common, str(path), {str(path)})
            if foreign:
                findings.append("other checkouts are registered inside it: " + ", ".join(foreign))
            allowed = {item["rid"] for item in document.get("disposed", [])} | \
                {item["rid"] for item in document.get("contained", [])}
            inner = [item["rid"] for item in _contained(common, view["rid"], str(path)) if item["rid"] not in allowed]
            if inner:
                findings.append("it still holds recorded resources: " + ", ".join(inner))
            if kind == "worktree" and not started:
                if _worktree_head(path) != frozen.get("head"):
                    findings.append("its HEAD moved after the claim was frozen")
                # Branches whose claims are active are being retired too; they cannot vouch for its commits.
                findings += _worktree_findings(common, identity, view["rid"],
                                               [loc for item in document.get("disposed", [])
                                                for loc in item.get("locations", [])],
                                               _branch_refs(common, set()))
    if kind == "branch":
        commit, symbolic = _ref_tip(common, identity["ref"])
        if commit is not None and (commit != frozen.get("tip") or symbolic):
            findings.append(f"its tip moved after the claim was frozen ({frozen.get('tip')} -> {commit})")
        elif commit is not None and commit != identity.get("created_commit") and \
                not _reachable_elsewhere(common, commit, _branch_refs(common, set())):
            findings.append(f"its tip {commit[:12]} carries commits no other ref contains (unmerged work)")
        holders = [item["worktree"] for item in _registrations(common) if item.get("branch") == identity["ref"]]
        if holders:
            findings.append("checked out by " + ", ".join(holders))
    for item in document.get("disposed", []):
        inner = item.get("identity") or {}
        if item["kind"] == "export":
            info, _ = read_regular(Path(inner.get("path", "/")) / "manifest.json")
            if info.get("sha256") != inner.get("manifest_sha256") and info["kind"] != "missing":
                findings.append(f"disposed export {item['rid']} changed after the decision")
        if item["kind"] == "retained":
            for entry in inner.get("files", []):
                info, _ = read_regular(Path(entry["path"]))
                if info.get("sha256") not in (entry.get("sha256"), None):
                    findings.append(f"disposed retained file {entry['path']} changed after the decision")
    return findings


def _remove_worktree(common: str, rid: str, frozen: dict) -> str:
    """Remove the frozen worktree directory, then the administration this resource's marker names."""
    path = Path(frozen["identity"]["path"])
    recorded = (frozen.get("snapshot") or {}).get("identity") or {}
    admin = _admin_for(common, rid)
    outcome = _removal.remove_path(path, identity=(recorded["dev"], recorded["ino"]) if recorded else None)
    if admin is not None:
        _removal.remove_path(admin)
    return outcome


def retire_claim(common: str, view: dict, claim: dict) -> dict:
    """Remove one claimed resource after revalidating it; release the claim when anything changed."""
    from stewart.session import now, stamp, tool_identity, write_receipt
    index = Index(common)
    findings = _revalidate(common, view, claim, index)
    if findings:
        _end(claim, "RELEASED", {"observation": findings})
        return {"rid": view["rid"], "kind": view["kind"], "outcome": "kept", "reasons": findings}
    frozen = claim["claim"]["frozen"]
    identity = frozen["identity"]
    try:
        if view["kind"] == "worktree":
            outcome = _remove_worktree(common, view["rid"], frozen)
        elif view["kind"] == "directory":
            recorded = (frozen.get("snapshot") or {}).get("identity") or {}
            outcome = _removal.remove_path(Path(identity["path"]),
                                           identity=(recorded["dev"], recorded["ino"]) if recorded else None)
        elif view["kind"] == "branch":
            if _ref_tip(common, identity["ref"])[0] is None:
                outcome = "absent"
            else:
                _git_common(common, "update-ref", "--no-deref", "-d", identity["ref"], frozen["tip"])
                outcome = "removed"
        else:
            raise StewartError(f"a {view['kind']} is retained, not removed", reason="resource_not_managed")
    except (OSError, StewartError, _removal.Substituted, _removal.Replaced) as exc:
        write_receipt(Path(claim["path"]).with_name(f"{claim['number']:04d}.ATTEMPT-{stamp()}.json"),
                      {"schema": ENDED_SCHEMA, "claim_sha256": claim["sha256"], "ending": "attempt",
                       "recorded_at": now().isoformat(), "error": str(exc), "stewart": tool_identity()})
        return {"rid": view["rid"], "kind": view["kind"], "outcome": "failed", "detail": str(exc)}
    results = [{"rid": view["rid"], "kind": view["kind"], "outcome": outcome}]
    head = frozen.get("head")
    dependents = [(item, "removed with its container by the recorded disposal decision")
                  for item in claim["claim"].get("disposed", [])]
    dependents += [(item, f"retired with its container; its committed bytes remain in Git history at {head}")
                   for item in claim["claim"].get("contained", [])]
    for item, what in dependents:
        results.append({"rid": item["rid"], "kind": item["kind"], "outcome": what})
        try:
            inner = load(common, item["rid"])
            inner_claim = _claim(common, inner, {"disposed": []}, {"kind": "container", "rid": view["rid"]})
            if inner_claim is not None:
                _end(inner_claim, "RETIRED", {"results": [results[-1]]})
        except StewartError:
            pass
    _end(claim, "RETIRED", {"results": results})
    return {"rid": view["rid"], "kind": view["kind"], "outcome": outcome, "results": results}


def _retirement_order(view: dict) -> tuple:
    """Deepest worktrees and directories first, branches last, so nothing is removed inside a removed container."""
    path = (view.get("identity") or {}).get("path") or ""
    return (1 if view.get("kind") == "branch" else 0, -len(Path(path).parts), path)


def claim_for_close(common: str, slug: str, ident: str, *, lifetime: str | None, closing: Path,
                    dispose: list[str] = (), used: list[str] | None = None) -> list[dict]:
    """Claim each resource whose last live use this close ends; explain the rest.

    It runs once, in the close's first attempt, after CLOSING.json and after
    the session's own items are removed, so the frozen contents are what this
    close leaves behind (a checkout home inside a directory resource no longer
    holds the session's checkout). ``used`` is the set of resources the audit
    used before that removal took away the paths its session pinned.
    """
    evaluations = _closeout(common, slug, ident, lifetime=lifetime, dispose=set(dispose), closing_name=closing.name,
                            used=used)
    claimant = {"kind": "audit-close", "closing": str(closing / "CLOSING.json"), "slug": slug, "audit_id": ident,
                "lifetime": lifetime}
    for evaluation in sorted(evaluations, key=_retirement_order):
        if evaluation.get("disposition") != "remove":
            continue
        claim = _claim(common, load(common, evaluation["rid"]), evaluation, claimant)
        if claim is None:
            evaluation.update(disposition="claimed", reasons=["another close claimed it first"])
        else:
            evaluation.update(disposition="claimed by this close", claim=claim["path"])
    return presented(evaluations)


def retire_for_close(common: str, closing: Path) -> list[dict]:
    """Retire every active claim naming this closing record: deepest paths first, branches last."""
    results = []
    pending = []
    for rid in rids(common):
        try:
            view = load(common, rid)
        except StewartError:
            continue
        for claim in view["claims"]:
            if claim["state"] == "active" and (claim["claim"].get("claimant") or {}).get("closing") == \
                    str(closing / "CLOSING.json"):
                pending.append((view, claim))
    for view, claim in sorted(pending, key=lambda item: _retirement_order(item[0])):
        results.append(retire_claim(common, load(common, view["rid"]), claim))
    return results


def close_resources(repo: Path, rids_: list[str], *, actor: str, reason: str | None = None,
                    dispose: list[str] = (), request_key: str | None = None, resume: bool = False) -> dict:
    """Retire named resources with no live use, under the same claim discipline; resume an unfinished claim."""
    from stewart._repository import maintainer
    from stewart.request_keys import keyed
    common = maintainer(Path(repo))["common_dir"]
    for rid in rids_:
        resource_id(rid)
    inputs = {"resources": sorted(rids_), "actor": actor, "reason": reason, "dispose": sorted(dispose)}
    return keyed(None, None, "resource-close", inputs, request_key,
                 lambda plan: _close_resources(common, list(rids_), actor, reason, list(dispose), plan,
                                               resume=resume, repo=Path(repo)),
                 resources=list(rids_), resume=resume, common=common, repo=Path(repo),
                 complete=lambda result: not any(item["outcome"] == "failed" for item in result["results"]),
                 outputs=lambda result: [{"kind": "resource", "resource": item["rid"], "path": item.get("record")}
                                         for item in result["results"]])


def _close_resources(common: str, names: list[str], actor: str, reason: str | None, dispose: list[str], plan, *,
                     resume: bool = False, repo: Path | None = None) -> dict:
    from stewart.implementation import require
    _actor(actor)
    if not names:
        raise StewartError("name at least one resource with --resource", reason="usage")
    index = Index(common)
    views = {rid: load(common, rid) for rid in names}
    resumed, evaluations, done = {}, {}, set()
    for rid, view in views.items():
        active = [claim for claim in view["claims"] if claim["state"] == "active"]
        if active:
            require(active[-1]["claim"].get("stewart"), record=Path(active[-1]["path"]),
                    arguments=["--repo", str(repo or ""), "resource", "show", "--resource", rid])
            resumed[rid] = active[-1]
            continue
        if resume and any(claim["state"] == "retired" for claim in view["claims"]):
            # Resuming this request: a resource its interrupted attempt already retired is done.
            done.add(rid)
            continue
        evaluations[rid] = evaluate(common, view, index, dispose=set(dispose),
                                    inventory=set(names) - {rid})
    refused = {rid: item for rid, item in evaluations.items() if item["disposition"] != "remove"}
    if refused:
        dispositions = {item["disposition"] for item in refused.values()}
        message = "these resources cannot be retired now: " + "; ".join(
            f"{rid} {item['disposition']}: {' '.join(item.get('reasons') or [])}" for rid, item in refused.items())
        details = {"retained": [views[rid]["path"] for rid in refused],
                   "next_steps": ["close --plan for the audits that use them explains each blocker; enrolled "
                                  "resources are retired by hand and acknowledged"]}
        if dispositions & {"manual", "retained"}:
            raise StewartError(message, reason="resource_not_managed", **details)
        if dispositions & {"retired", "acknowledged"}:
            raise StewartError(message, reason="resource_retired", **details)
        if "shared" in dispositions:
            raise StewartError(message, reason="resource_shared", **details)
        raise StewartError(message, reason="resource_blocked", **details)
    plan([{"kind": "resource", "resource": rid, "path": views[rid]["path"]} for rid in names])
    claimant = {"kind": "resource-close", "actor": actor, "reason": reason}
    results = [{"rid": rid, "kind": views[rid].get("kind"), "outcome": "retired earlier under this request",
                "record": views[rid]["path"]} for rid in sorted(done)]
    for rid in sorted((rid for rid in names if rid not in done), key=lambda item: _retirement_order(views[item])):
        if rid in resumed:
            claim = resumed[rid]
        else:
            claim = _claim(common, load(common, rid), evaluations[rid], claimant)
            if claim is None:
                results.append({"rid": rid, "kind": views[rid].get("kind"), "outcome": "kept",
                                "reasons": ["another close claimed or retired it first"], "record": views[rid]["path"]})
                continue
        outcome = retire_claim(common, load(common, rid), claim)
        results.append({**outcome, "record": views[rid]["path"], "resumed": rid in resumed})
    failed = [item for item in results if item["outcome"] == "failed"]
    kept = [item for item in results if item["outcome"] == "kept"]
    return {"results": results, "exit_code": EXIT_ATTENTION if failed or kept else EXIT_OK}


# --- manual retirement acknowledgment ----------------------------------------------------------------------


def acknowledge(repo: Path, rid: str, *, actor: str, note: str | None = None,
                request_key: str | None = None) -> dict:
    """Record the manager's acknowledgment that an observed absence was retirement outside Stewart."""
    from stewart._repository import maintainer
    from stewart.request_keys import keyed
    common = maintainer(Path(repo))["common_dir"]
    return keyed(None, None, "resource-acknowledge", {"actor": actor, "note": note}, request_key,
                 lambda plan: _acknowledge(common, rid, actor, note, plan), resources=[rid], common=common,
                 repo=Path(repo), outputs=lambda result: [{"kind": "acknowledgment", "resource": rid,
                                                           "path": result["path"]}])


def _acknowledge(common: str, rid: str, actor: str, note: str | None, plan) -> dict:
    from stewart.session import now, tool_identity
    _actor(actor)
    view = load(common, rid)
    if view.get("acknowledged"):
        raise StewartError(f"resource {rid}'s retirement is already acknowledged", reason="destination_exists",
                           retained=[str(Path(view["path"]) / "ACKNOWLEDGED.json")])
    if any(claim["state"] in ("active", "retired") for claim in view["claims"]):
        raise StewartError(f"resource {rid} is claimed or retired by Stewart; there is no manual retirement to "
                           "acknowledge", reason="resource_claimed", retained=[view["path"]])
    observation = observe(common, view)
    if observation["state"] != "absent":
        raise StewartError(f"resource {rid} is not absent ({observation['state']}); an acknowledgment needs an "
                           "observed absence", reason="resource_present", retained=[view["path"]],
                           next_steps=["retire it by hand first; a managed worktree is locked, so drop its Git "
                                       "registration with `git worktree remove -f -f <path>` (or unlock it, then "
                                       "`git worktree prune`)"])
    location_ = Path(view["path"]) / "ACKNOWLEDGED.json"
    plan([{"kind": "acknowledgment", "resource": rid, "path": str(location_)}])
    _record(Path(view["path"]), "ACKNOWLEDGED.json", {
        "schema": ACKNOWLEDGMENT_SCHEMA, "rid": rid, "recorded_at": now().isoformat(),
        "observed": observation, "acknowledged": {"actor": actor, "note": note,
                                                  "claim": "retired outside Stewart"},
        "resource_record_sha256": view.get("record_sha256"), "stewart": tool_identity(),
        "limit": "an acknowledgment grants nothing and says nothing about how the resource was removed; "
                 "anything later found at its location is a new observation"})
    return {"rid": rid, "path": str(location_), "observed": observation}


# --- views ----------------------------------------------------------------------------------------------


def show(repo: Path, rid: str) -> dict:
    """One resource's records, present observation, uses and disposition; writes nothing."""
    from stewart._repository import observer
    common = observer(Path(repo))["common_dir"]
    view = load(common, resource_id(rid))
    index = Index(common)
    evaluation = evaluate(common, view, index)
    return {"schema": "stewart.resource-view/1", "rid": rid, "kind": view.get("kind"), "origin": view.get("origin"),
            "creation": view.get("creation"), "identity": view.get("identity"), "context": view.get("context"),
            "associations": view["associations"], "claims": [{key: claim.get(key) for key in
                                                              ("number", "path", "state", "attempts")}
                                                             for claim in view["claims"]],
            "acknowledged": _acknowledgment_view(view, common), "observation": evaluation.get("observation"),
            "users": evaluation.get("users", []), "disposition": evaluation["disposition"],
            "reasons": evaluation.get("reasons", []), "problems": view["problems"],
            "exit_code": _code(evaluation, view)}


def _acknowledgment_view(view: dict, common: str) -> dict | None:
    acknowledged = view.get("acknowledged")
    if not acknowledged:
        return None
    now_seen = observe(common, view)
    return {"observed_at_acknowledgment": acknowledged.get("observed"),
            "acknowledged": acknowledged.get("acknowledged"), "recorded_at": acknowledged.get("recorded_at"),
            "observed_now": now_seen,
            "note": "a new entry at the location is a new observation, not the retired resource"
            if now_seen["state"] != "absent" else None}


def _code(evaluation: dict, view: dict) -> int:
    if view["problems"]:
        return EXIT_UNVERIFIED
    if evaluation["disposition"] in ("missing", "claimed") or view.get("creation") == "unresolved":
        return EXIT_ATTENTION
    return EXIT_OK


def resource_summaries(common: str, problems: list[dict]) -> list[dict]:
    """Every recorded resource, explained: what it is, who uses it and what Stewart would do with it."""
    index = Index(common)
    summaries = []
    for rid in rids(common):
        try:
            view = load(common, rid)
        except StewartError as exc:
            summaries.append({"rid": rid, "disposition": "blocked", "problems": [exc.to_json()],
                              "exit_code": EXIT_UNVERIFIED})
            continue
        evaluation = evaluate(common, view, index)
        summaries.append({"rid": rid, "kind": view.get("kind"), "origin": view.get("origin"),
                          "creation": view.get("creation"), "identity": view.get("identity"),
                          "disposition": evaluation["disposition"], "reasons": evaluation.get("reasons", []),
                          "users": [{key: user[key] for key in ("source", "audit", "live", "state")}
                                    for user in evaluation.get("users", [])],
                          "acknowledged": _acknowledgment_view(view, common), "problems": view["problems"],
                          "exit_code": _code(evaluation, view)})
    return summaries


def private_roots(common: str) -> list[str]:
    """Live managed worktrees and directories, kept out of auditor read grants like other private roots."""
    roots = []
    for rid in rids(common):
        try:
            view = load(common, rid)
        except StewartError:
            continue
        path = (view.get("identity") or {}).get("path")
        if (view.get("origin") in ("managed", "enrolled") and view.get("kind") in ("worktree", "directory")
                and isinstance(path, str) and not any(claim["state"] == "retired" for claim in view["claims"])
                and not view.get("acknowledged")):
            roots.append(path)
    return roots
