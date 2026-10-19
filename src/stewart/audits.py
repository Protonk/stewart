"""Repository-level audit identity: draft records, registration, discovery and selection references.

An audit is a workspace and an audit ID within one repository; a lifetime is
one prepared session (its UUID). Sessions, closing records and role rows were
already repository-wide. This module adds records for audits that exist before
any session: ``init --replace-prompt`` writes a start record before it writes
anything and an outcome record after, and ``register`` records present
observations of an existing workspace without implying any earlier custody.

Discovery reads every repository-level record under the Git common directory
and writes nothing: no record of any kind, no runtime and no "current audit" setting.
Selection turns one discovered audit into a reference the caller keeps; every
operation revalidates it. Aliases are locators: an audit ID shared by several
workspaces, several draft checkouts, a lost owner, a replaced lifetime or an
unsupported record stays explicit and is never resolved by recency.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re

from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_UNVERIFIED, StewartError, combined_code, read_regular
from stewart._json import loads_control

DRAFT_SCHEMA = "stewart.draft/1"
REGISTRATION_SCHEMA = "stewart.registration/1"
REFERENCE_SCHEMA = "stewart.audit-ref/1"
DISCOVERY_SCHEMA = "stewart.discovery/1"
SELECTION_SCHEMA = "stewart.selection/1"
#: Repository-level audit records below the Git common directory.
AUDITS = "stewart/audits"
_REFERENCE_FIELDS = {"schema", "repository", "checkout", "owner", "workspace", "audit_id", "lifetime", "closes",
                     "implementation"}
_CONTEXT_FIELDS = {"workspace", "slug", "audit_id", "lifetime", "closed_before"}
_DIGEST = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Located:
    """A workspace known by its storage slug, enough to address the records filed under it."""

    slug: str
    rel: str | None = None


def records_location(common: str, slug: str, ident: str) -> Path:
    from stewart.workspace import contained
    return contained(Path(common), f"{AUDITS}/{slug}/{ident}")


def _names(directory: Path) -> list[str] | None:
    """Entries of a real directory reached without following links; None when it is not one."""
    from stewart import _removal
    try:
        with _removal.pinned(directory) as descriptor:
            return sorted(os.listdir(descriptor))
    except FileNotFoundError:
        return []
    except (_removal.Substituted, OSError):
        return None


# --- audit contexts and their liveness -------------------------------------------------------------


def closed_names(common: str, slug: str, ident: str) -> list[str]:
    """Closing-directory names recorded for an audit, including unfinished and unreadable ones."""
    from stewart.close import closing_entries
    return sorted(str(entry["session_uuid"]) for entry in closing_entries(common, Located(slug), ident))


def context(common: str, ws, ident: str, lifetime: str | None) -> dict:
    """The audit context a record carries: which audit, which lifetime, and the closes already recorded."""
    return {"workspace": ws.rel, "slug": ws.slug, "audit_id": ident, "lifetime": lifetime,
            "closed_before": closed_names(common, ws.slug, ident)}


def validate_context(value: object) -> dict:
    from stewart.assignment import audit_id
    from stewart.workspace import relative, workspace as _workspace
    if (not isinstance(value, dict) or set(value) != _CONTEXT_FIELDS or not isinstance(value["closed_before"], list)
            or not all(isinstance(name, str) for name in value["closed_before"])):
        raise StewartError("audit context has an unsupported shape", reason="record_corrupt")
    relative(value["workspace"])
    audit_id(value["audit_id"])
    if _workspace(Path("/"), value["workspace"]).slug != value["slug"]:
        raise StewartError("audit context slug does not match its workspace", reason="record_corrupt")
    if value["lifetime"] is not None:
        from stewart._repository import session_uuid
        session_uuid(value["lifetime"])
    return value


def context_live(common: str, value: dict) -> dict:
    """Whether a recorded context still counts as a user, with the reason.

    A lifetime ends once a closing record verifies for it (closing or closed).
    A context recorded before any session ends once a closing record verifies
    for a name it did not already know. A closing record that does not verify
    keeps every context of the audit live: doubt never ends a use.
    """
    from stewart.close import closing_entries
    entries = closing_entries(common, Located(value["slug"]), value["audit_id"])
    if any("problem" in entry for entry in entries):
        return {"live": True, "state": "unverified", "reason": "a closing record of this audit does not verify"}
    lifetime = value["lifetime"]
    names = [str(entry["session_uuid"]) for entry in entries]
    if lifetime is not None:
        ended = lifetime in names
    else:
        ended = any(name not in value["closed_before"] for name in names)
    if ended:
        return {"live": False, "state": "closed", "reason": "the audit lifetime has a closing record"}
    return {"live": True, "state": "live", "reason": "no closing record ends this use"}


# --- draft and registration records ----------------------------------------------------------------


def _audit_directory(common: str, ws, ident: str, kind: str) -> Path:
    from stewart._repository import private_directories, private_storage
    return private_directories(private_storage(common), records_location(common, ws.slug, ident) / kind)


def begin_init(ws, ident: str, *, intended: list[dict], prompt_before: dict, target: str,
               request_key: str | None) -> Path:
    """Write the start record of a mutating ``init`` before any of its writes."""
    from stewart._repository import maintainer
    from stewart.session import now, stamp, tool_identity, write_receipt
    identity = maintainer(ws.repo)
    common = identity["common_dir"]
    name = stamp()
    directory = _audit_directory(common, ws, ident, "init") / name
    directory.mkdir(mode=0o700)
    write_receipt(directory / "STARTED.json", {
        "schema": DRAFT_SCHEMA, "kind": "init", "phase": "started", "name": name, "recorded_at": now().isoformat(),
        "context": context(common, ws, ident, None), "checkout": str(ws.repo),
        "checkout_git_admin": identity["git_admin"], "intended": intended, "prompt_before": prompt_before,
        "target_commit": target, "request_key": request_key, "stewart": tool_identity(),
        "note": "intended writes, recorded before any of them; the outcome record says what happened"})
    return directory


def finish_init(directory: Path, *, written: list[dict], error: dict | None) -> None:
    from stewart.session import capture_receipt, now, tool_identity, write_receipt
    _, started = capture_receipt(directory / "STARTED.json", what="draft start record")
    write_receipt(directory / "OUTCOME.json", {
        "schema": DRAFT_SCHEMA, "kind": "init", "phase": "outcome", "name": directory.name,
        "recorded_at": now().isoformat(), "started_sha256": started,
        "status": "failed" if error else "completed", "written": written, "error": error,
        "stewart": tool_identity()})


def _prompt_names(data: bytes | None, ident: str) -> bool:
    """Whether a prompt's single assignment block names this audit ID; prose and markers are not read."""
    from stewart.assignment import FENCE
    if data is None:
        return False
    blocks = re.findall(rf"^```{FENCE}\s*\n(.*?)^```\s*$", data.decode("utf-8", "replace"), re.M | re.S)
    if len(blocks) != 1:
        return False
    try:
        meta = loads_control(blocks[0])
    except (ValueError, RecursionError):
        return False
    return isinstance(meta, dict) and meta.get("audit_id") == ident


def register(ws, ident: str, *, actor: str, request_key: str | None = None) -> dict:
    """Record an existing, named workspace's present observations as a draft audit.

    The guidance files and the prompt are read through verified descriptors;
    the prompt's assignment block must name ``ident``. The record states what
    was observed now and claims no earlier custody of any of it.
    """
    from stewart.request_keys import keyed
    return keyed(ws, ident, "register", {"actor": actor}, request_key, lambda plan: _register(ws, ident, actor, plan),
                 outputs=lambda result: [{"kind": "registration", "path": result["path"],
                                          "sha256": result["sha256"]}])


def _register(ws, ident: str, actor: str, plan) -> dict:
    from stewart._git import git
    from stewart._repository import maintainer, registered_session, session_location
    from stewart.assignment import audit_id
    from stewart.close import require_fresh_audit_id
    from stewart.session import capture_receipt, now, stamp, tool_identity, write_receipt
    from stewart.workspace import contained
    if not isinstance(actor, str) or not actor.strip():
        raise StewartError("a registration needs an attributed actor", reason="actor_required",
                           next_steps=["rerun with --actor NAME naming who registers the workspace"])
    identity = maintainer(ws.repo)
    common = identity["common_dir"]
    audit_id(ident)
    folder = contained(ws.repo, ws.rel)
    if not folder.is_dir():
        raise StewartError(f"workspace {ws.rel} is not a directory in {ws.repo}", reason="workspace_guidance",
                           next_steps=["create the workspace with its AUDITOR.md, MAINTAINER.md and PROMPT.md first"])
    observed = {}
    for role, rel in (("auditor_guidance", ws.auditor_guidance), ("maintainer_guidance", ws.maintainer_guidance),
                      ("prompt", ws.prompt)):
        info, data = read_regular(contained(ws.repo, rel))
        if data is None:
            raise StewartError(f"{rel} is not a readable regular file ({info['kind']})", reason="workspace_guidance",
                               retained=[str(ws.repo / rel)])
        observed[role] = {"path": rel, "kind": info["kind"], "sha256": info["sha256"], "size": info["size"]}
        if role == "prompt" and not _prompt_names(data, ident):
            raise StewartError(f"{rel} has no single assignment block naming audit {ident}",
                               reason="assignment_schema",
                               next_steps=[f"init --audit-id {ident} drafts one, or name the audit in the block"])
    require_fresh_audit_id(common, ws, ident)
    from stewart.holdings import refuse_retiring
    refuse_retiring(common, [ws.repo], what="a registration")
    session = session_location(common, ws, ident)
    if os.path.lexists(session):
        raise StewartError(f"a session already records audit {ident}; it is discoverable without registration",
                           reason="audit_recorded", retained=[str(session)])
    registered_session(common, session)
    head = git(ws.repo, "rev-parse", "--verify", "HEAD", check=False)
    observed["head"] = os.fsdecode(head.stdout).strip() if not head.returncode else None
    name = stamp()
    destination = _audit_directory(common, ws, ident, "registrations") / f"{name}.json"
    plan([{"kind": "registration", "path": str(destination)}])
    write_receipt(destination, {
        "schema": REGISTRATION_SCHEMA, "name": name, "recorded_at": now().isoformat(),
        "context": context(common, ws, ident, None), "checkout": str(ws.repo),
        "checkout_git_admin": identity["git_admin"], "actor": actor, "observed": observed,
        "note": "present observations at registration; no earlier custody of these bytes is implied",
        "stewart": tool_identity()})
    _, digest = capture_receipt(destination, what="registration record")
    return {"audit_id": ident, "workspace": ws.rel, "registration": name, "path": str(destination), "sha256": digest,
            "observed": observed}


def _draft_record(common: str, slug: str, ident: str, kind: str, location: Path, value: dict | None,
                  problem: dict | None) -> dict:
    view: dict = {"kind": kind, "path": str(location), "name": location.name.removesuffix(".json")}
    if problem is not None:
        return {**view, "state": "invalid", "problem": problem}
    try:
        validate_context(value.get("context"))
        if value["context"]["slug"] != slug or value["context"]["audit_id"] != ident:
            raise StewartError("record names another audit", reason="record_corrupt")
        if not isinstance(value.get("checkout"), str) or not Path(value["checkout"]).is_absolute():
            raise StewartError("record names no absolute checkout", reason="record_corrupt")
    except (StewartError, AttributeError, KeyError, TypeError) as exc:
        return {**view, "state": "invalid", "problem": {"reason": "draft_record_invalid", "message": str(exc)}}
    view.update(workspace=value["context"]["workspace"], checkout=value["checkout"],
                closed_before=value["context"]["closed_before"], recorded_at=value.get("recorded_at"),
                writer=(value.get("stewart") or {}).get("package_sha256"))
    return view


def draft_records(common: str, slug: str, ident: str) -> list[dict]:
    """Every init and registration record of an audit, each with its own state and diagnostics."""
    from stewart.session import RECORD_NAME, capture_receipt
    base = records_location(common, slug, ident)
    views = []
    for name in _names(base / "init") or []:
        directory = base / "init" / name
        if not RECORD_NAME.fullmatch(name):
            continue
        try:
            started, _ = capture_receipt(directory / "STARTED.json", what="draft start record")
            if started.get("schema") != DRAFT_SCHEMA or started.get("kind") != "init":
                raise StewartError("unsupported draft record schema", reason="record_schema")
        except StewartError as exc:
            views.append(_draft_record(common, slug, ident, "init", directory, None,
                                       {"reason": "draft_record_invalid", "message": str(exc)}))
            continue
        view = _draft_record(common, slug, ident, "init", directory, started, None)
        if view.get("state") == "invalid":
            views.append(view)
            continue
        try:
            outcome, _ = capture_receipt(directory / "OUTCOME.json", what="draft outcome record")
            view["state"] = outcome.get("status") if outcome.get("status") in ("completed", "failed") else "invalid"
            view["written"] = outcome.get("written") if isinstance(outcome.get("written"), list) else []
        except StewartError as exc:
            view["state"] = "partial" if exc.reason == "record_missing" else "invalid"
            if exc.reason != "record_missing":
                view["problem"] = {"reason": "draft_record_invalid", "message": str(exc)}
            view["written"] = []
        view["intended"] = started.get("intended") if isinstance(started.get("intended"), list) else []
        views.append(view)
    for name in _names(base / "registrations") or []:
        location = base / "registrations" / name
        if not RECORD_NAME.fullmatch(name.removesuffix(".json")) or not name.endswith(".json"):
            continue
        try:
            value, _ = capture_receipt(location, what="registration record")
            if value.get("schema") != REGISTRATION_SCHEMA:
                raise StewartError("unsupported registration record schema", reason="record_schema")
        except StewartError as exc:
            views.append(_draft_record(common, slug, ident, "registration", location, None,
                                       {"reason": "draft_record_invalid", "message": str(exc)}))
            continue
        view = _draft_record(common, slug, ident, "registration", location, value, None)
        if "state" not in view:
            view["state"] = "completed"
            view["observed"] = value.get("observed")
            view["actor"] = value.get("actor")
        views.append(view)
    return sorted(views, key=lambda item: (item.get("recorded_at") or "", item["name"]))


def draft_files(view: dict) -> list[dict]:
    """Observe a draft's recorded files in its checkout now; an absent checkout makes them unavailable.

    A registration cannot recover bytes: when the checkout or the file is gone,
    the recorded digest only says what was there.
    """
    files = (view.get("written") or []) if view["kind"] == "init" else [
        item for key, item in (view.get("observed") or {}).items() if key != "head" and isinstance(item, dict)]
    checkout = Path(view["checkout"]) if view.get("checkout") else None
    observed = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        entry = {"path": item["path"], "recorded_sha256": item.get("sha256")}
        if checkout is None or not checkout.is_dir():
            entry["state"] = "unavailable"
        else:
            location = Path(item["path"]) if Path(item["path"]).is_absolute() else checkout / item["path"]
            info, _ = read_regular(location)
            entry["observed_sha256"] = info.get("sha256")
            entry["state"] = ("missing" if info["kind"] == "missing" else
                              "unchanged" if info.get("sha256") == item.get("sha256") else "changed")
        observed.append(entry)
    return observed


# --- discovery ----------------------------------------------------------------------------------------


def _envelope(value: dict, slug: str) -> dict:
    """The supported discovery envelope: schema, a workspace whose slug matches the location, the writer stamp."""
    from stewart.workspace import workspace as _workspace
    from stewart.implementation import recorded_digest
    schema = value.get("schema", value.get("schema_version"))
    rel = value.get("workspace")
    try:
        rel = rel if isinstance(rel, str) and _workspace(Path("/"), rel).slug == slug else None
    except StewartError:
        rel = None
    stamp = value.get("stewart") if isinstance(value.get("stewart"), dict) else None
    return {"schema": schema if isinstance(schema, (str, int)) else None, "workspace": rel,
            "writer": recorded_digest(stamp), "stamp": stamp}


def _session_view(common: str, slug: str, ident: str) -> dict | None:
    """A session located under the repository: its envelope, and its identity only when the schema is supported."""
    from stewart._repository import session_location
    from stewart.session import SESSION_SCHEMA, capture_receipt
    session = session_location(common, Located(slug), ident)
    if not os.path.lexists(session):
        return None
    view: dict = {"path": str(session), "supported": False, "problems": []}
    try:
        value, _ = capture_receipt(session / "session.json", what="session record")
    except StewartError as exc:
        view["problems"].append({"reason": exc.reason, "message": str(exc)})
        view["envelope"] = {"schema": None, "workspace": None, "writer": None, "stamp": None}
        return view
    view["envelope"] = _envelope(value, slug)
    if value.get("schema_version") != SESSION_SCHEMA:
        view["problems"].append({"reason": "session_schema_unsupported",
                                 "message": f"session schema {value.get('schema_version')!r} is not supported by this "
                                            "implementation; no lifecycle state is inferred from its fields"})
        return view
    from stewart._repository import session_uuid
    try:
        view.update(uuid=session_uuid(value.get("session_uuid")), owner=value.get("repo"), supported=True)
    except StewartError as exc:
        view["problems"].append({"reason": exc.reason, "message": str(exc)})
        return view
    failure = session / "PREPARE-ERROR.json"
    view["stage"] = ("preparation_failed" if os.path.lexists(failure) else
                     "prepared" if os.path.lexists(session / "LAUNCH.md") else "preparation_incomplete")
    view["collections"] = len([name for name in _names(session / "collections") or []
                               if os.path.lexists(session / "collections" / name / "collection.json")])
    return view


def _audit_keys(common: str, rows: list[dict]) -> tuple[dict[tuple[str, str], set[str]], list[dict]]:
    """Every (slug, audit ID) any repository-level record names, with the record families that name it."""
    from stewart._repository import CLOSED, SESSIONS
    keys: dict[tuple[str, str], set[str]] = {}
    problems: list[dict] = []
    for family, root in (("session", Path(common) / SESSIONS), ("closed", Path(common) / CLOSED),
                         ("draft", Path(common) / AUDITS)):
        slugs = _names(root)
        if slugs is None:
            problems.append({"reason": "record_unreadable", "location": str(root),
                             "message": "storage is not a real directory; nothing below it was read"})
            continue
        for slug in slugs:
            idents = _names(root / slug)
            if idents is None:
                problems.append({"reason": "record_unreadable", "location": str(root / slug),
                                 "message": "storage is not a real directory; nothing below it was read"})
                continue
            for ident in idents:
                keys.setdefault((slug, ident), set()).add(family)
    prefix = Path(common) / SESSIONS
    for row in rows:
        session = Path(row["session"])
        if session.parent.parent == prefix:
            keys.setdefault((session.parent.name, session.name), set()).add("role")
    from stewart.holdings import context_keys
    for slug, ident in context_keys(common, problems):
        keys.setdefault((slug, ident), set()).add("resource")
    return keys, problems


def _audit_entry(common: str, repo: Path, slug: str, ident: str, families: set[str], current: dict) -> dict:
    from stewart.close import closing_entries
    from stewart.implementation import compare
    entry: dict = {"slug": slug, "audit_id": ident, "workspace": None, "workspace_candidates": [],
                   "found_in": sorted(families), "problems": []}
    session = _session_view(common, slug, ident)
    closes = closing_entries(common, Located(slug), ident)
    drafts = draft_records(common, slug, ident)
    candidates: set[str] = set()
    if session is not None and session["envelope"]["workspace"]:
        candidates.add(session["envelope"]["workspace"])
    for close in closes:
        rel = ((close.get("closing") or {}).get("identity") or {}).get("workspace")
        if isinstance(rel, str):
            candidates.add(rel)
    candidates.update(item["workspace"] for item in drafts if item.get("workspace"))
    from stewart.holdings import contexts_for
    contexts = contexts_for(common, slug, ident)
    candidates.update(item["workspace"] for item in contexts)
    entry["workspace_candidates"] = sorted(candidates)
    if len(candidates) == 1:
        entry["workspace"] = next(iter(candidates))
    elif len(candidates) > 1:
        entry["problems"].append({"reason": "record_corrupt", "message": "records under one location name different "
                                  "workspaces: " + ", ".join(sorted(candidates))})
    rows_only = families == {"role"}
    unfinished = [item for item in closes if not item["complete"] and "problem" not in item]
    invalid_closes = [item for item in closes if "problem" in item]
    stamp = None
    checkout = None
    lifetime = None
    if session is not None:
        entry["session"] = {key: session.get(key) for key in
                            ("path", "uuid", "supported", "owner", "stage", "collections", "problems")}
        entry["session"]["envelope"] = {key: value for key, value in session["envelope"].items() if key != "stamp"}
        stamp = session["envelope"]["stamp"]
        checkout = session.get("owner")
        lifetime = session.get("uuid")
        entry["problems"] += session["problems"]
    entry["closes"] = [{"session_uuid": item["session_uuid"], "path": item["path"], "complete": item["complete"],
                        "released": item["released"], "mode": item.get("mode"),
                        **({"problem": item["problem"]} if "problem" in item else {})} for item in closes]
    entry["problems"] += [{"reason": "closing_record_invalid", "message": item["problem"]["message"]}
                          for item in invalid_closes]
    entry["drafts"] = [{**item, "files": draft_files(item)} if item.get("state") != "invalid" else item
                       for item in drafts]
    entry["problems"] += [item["problem"] for item in drafts if "problem" in item]
    entry["contexts"] = len(contexts)
    if unfinished:
        stage = "closing"
        lifetime = unfinished[-1]["session_uuid"]
        stamp = stamp or ((unfinished[-1]["closing"].get("identity") or {}).get("stewart"))
    elif session is not None:
        # An unsupported schema is located but not interpreted; an unreadable record is unverified.
        stage = session.get("stage") or ("unsupported" if session["envelope"]["schema"] is not None else "unverified")
    elif rows_only or ("role" in families and "session" not in families and not closes):
        stage = "records_missing"
        entry["problems"].append({"reason": "session_records_missing",
                                  "message": "a role row names this audit's session, whose directory is missing"})
    elif closes:
        # A draft recorded after every close (a released ID drafted again) is the present stage.
        known = {str(item["session_uuid"]) for item in closes}
        stage = "draft" if any(item.get("state") != "invalid" and known <= set(item.get("closed_before", []))
                               for item in drafts) else "closed"
    elif drafts:
        stage = "draft"
    else:
        stage = "context"
    entry["stage"] = stage
    entry["lifetime"] = lifetime
    draft_checkouts = sorted({item["checkout"] for item in drafts if item.get("checkout")})
    entry["checkout"] = checkout if checkout else (draft_checkouts[0] if len(draft_checkouts) == 1 and stage == "draft"
                                                   else None)
    entry["draft_checkouts"] = draft_checkouts
    entry["checkout_available"] = None if entry["checkout"] is None else Path(entry["checkout"]).is_dir()
    if entry["checkout"] is not None and not entry["checkout_available"]:
        message = f"the recorded checkout is gone: {entry['checkout']}"
        if checkout:
            entry["problems"].append({"reason": "session_owner_missing", "message": message})
        else:
            entry["problems"].append({"reason": "draft_checkout_missing", "message": message})
    if session is not None and session.get("supported") and stage != "closing" and entry["workspace"] \
            and checkout and entry["checkout_available"]:
        # The envelope alone does not make a session usable: it must load as status and mutations load it.
        from stewart.session import load_session
        from stewart.workspace import workspace as _workspace
        try:
            load_session(_workspace(Path(checkout), entry["workspace"]), ident, check_retention=False)
        except StewartError as exc:
            # A registry row that does not verify is a repository-level problem discovery reports once;
            # it does not make this session's own records unverified.
            if exc.reason != "worktree_role_registry":
                entry["problems"].append({"reason": exc.reason, "message": str(exc)})
                stage = entry["stage"] = "unverified"
    for draft in drafts:
        if draft.get("state") == "partial":
            entry["problems"].append({"reason": "draft_incomplete", "message": f"init {draft['name']} recorded its "
                                      "intended writes but no outcome; inspect the prompt it intended"})
    if stamp is not None or session is not None:
        arguments = (["--repo", entry["checkout"] or str(repo), "--workspace", entry["workspace"], "status",
                      "--audit-id", ident] if entry["workspace"] else [])
        entry["implementation"] = compare(stamp, arguments, current=current)
        if not entry["workspace"] and entry["implementation"].get("handoff", {}).get("state") == "verified":
            entry["implementation"]["handoff"] = {"state": "unresolved", "missing": ["workspace"],
                                                  "diagnostics": ["the record's workspace cannot be established"]}
    else:
        entry["implementation"] = None
    from stewart.holdings import resources_for_audit
    entry["resources"] = resources_for_audit(common, slug, ident)
    codes = []
    for problem in entry["problems"]:
        from stewart._bootstrap import problem_code
        codes.append(problem_code(problem.get("reason", "")))
    if stage in ("closing", "preparation_failed", "preparation_incomplete"):
        codes.append(EXIT_ATTENTION)
    if stage in ("unsupported", "unverified"):
        codes.append(EXIT_UNVERIFIED)
    entry["exit_code"] = combined_code(codes)
    return entry


def discover(repo: Path) -> dict:
    """Every audit the repository's records name, across workspaces and maintainer checkouts; writes nothing.

    Unsupported, invalid and unreadable records are listed with their location
    and diagnostics. A workspace that was never recorded is absent.
    """
    from stewart._repository import observer
    from stewart.holdings import resource_summaries
    from stewart.request_keys import request_summaries
    identity = observer(Path(repo))
    common = identity["common_dir"]
    from stewart.implementation import viewer
    current = viewer()
    keys, problems = _audit_keys(common, identity["rows"])
    problems += identity["registry_problems"]
    audits = [_audit_entry(common, Path(identity["root"]), slug, ident, families, current)
              for (slug, ident), families in sorted(keys.items())]
    by_id: dict[str, list[dict]] = {}
    for entry in audits:
        by_id.setdefault(entry["audit_id"], []).append(entry)
    for entry in audits:
        others = [item for item in by_id[entry["audit_id"]] if item is not entry]
        entry["shares_audit_id_with"] = [item["workspace"] or item["slug"] for item in others]
    resources = resource_summaries(common, problems)
    requests = request_summaries(common, problems)
    codes = [entry["exit_code"] for entry in audits] + [item.get("exit_code", EXIT_OK) for item in resources] \
        + [item.get("exit_code", EXIT_OK) for item in requests] + [EXIT_UNVERIFIED for _ in problems]
    return {"schema": DISCOVERY_SCHEMA, "repository": common, "checkout": identity["root"],
            "viewer": {key: current.get(key) for key in ("package_sha256", "version")},
            "audits": audits, "resources": resources, "requests": requests, "problems": problems,
            "exit_code": combined_code(codes),
            "note": "read-only; selection is a reference you keep, and every operation revalidates it"}


# --- selection references -------------------------------------------------------------------------------


def select(repo: Path, *, audit_id: str, workspace: str | None = None, lifetime: str | None = None) -> dict:
    """Resolve an audit alias to one reference; ambiguity and unsupported records are refusals, never guesses.

    ``repo`` is the explicitly selected repository context. A draft recorded in
    several maintainer checkouts is bound to ``repo`` when it is one of them;
    otherwise the caller names one by running select from it.
    """
    from stewart.assignment import audit_id as _audit_id
    from stewart.workspace import workspace as _workspace
    _audit_id(audit_id)
    slug = _workspace(Path("/"), workspace).slug if workspace is not None else None
    found = discover(repo)
    candidates = [entry for entry in found["audits"] if entry["audit_id"] == audit_id
                  and (slug is None or entry["slug"] == slug)]
    if not candidates:
        raise StewartError(f"no recorded audit {audit_id}" + (f" in workspace {workspace}" if workspace else ""),
                           reason="selection_missing",
                           next_steps=["discover lists every recorded audit; a never-recorded workspace is absent",
                                       "init --replace-prompt or register records a draft audit"])
    if len(candidates) > 1:
        raise StewartError(f"audit ID {audit_id} names several recorded audits; name the workspace",
                           reason="selection_ambiguous",
                           retained=[item["workspace"] or item["slug"] for item in candidates],
                           next_steps=["rerun select with --workspace naming one of the retained workspaces"])
    entry = candidates[0]
    if entry["workspace"] is None or entry["stage"] in ("unsupported", "unverified", "records_missing"):
        raise StewartError(f"audit {audit_id} cannot be selected by this implementation: its records do not establish "
                           "a supported workspace and lifetime", reason="selection_unresolved",
                           retained=[(entry.get("session") or {}).get("path") or entry["slug"]],
                           next_steps=["inspect discover's diagnostics; the implementation that wrote the records "
                                       "may read them (implementation.handoff)"])
    here = found["checkout"]
    stage, chosen_lifetime = entry["stage"], entry["lifetime"]
    owner = entry["checkout"]
    if lifetime is not None and lifetime != chosen_lifetime:
        if lifetime not in [item["session_uuid"] for item in entry["closes"]]:
            raise StewartError(f"audit {audit_id} has no lifetime {lifetime}", reason="selection_missing",
                               retained=[str(item["session_uuid"]) for item in entry["closes"]])
        stage, chosen_lifetime, owner = "closed", lifetime, None
    if stage == "draft" or (stage == "context" and entry["draft_checkouts"]):
        options = entry["draft_checkouts"]
        if here in options:
            owner = here
        elif len(options) > 1:
            raise StewartError(f"audit {audit_id} has drafts in several maintainer checkouts; run select from the one "
                               "to continue", reason="selection_ambiguous", retained=options,
                               next_steps=["rerun select with --repo naming one of the retained checkouts"])
        elif options:
            owner = options[0]
    bound = chosen_lifetime if stage not in ("draft", "context") else None
    checkout = owner if owner and Path(owner).is_dir() else here
    writer = (entry.get("implementation") or {}).get("recorded") if bound and bound == entry["lifetime"] else None
    reference = {"schema": REFERENCE_SCHEMA, "repository": found["repository"], "checkout": checkout,
                 "owner": owner, "workspace": entry["workspace"], "audit_id": audit_id, "lifetime": bound,
                 "closes": sorted(str(item["session_uuid"]) for item in entry["closes"]), "implementation": writer}
    return {"schema": SELECTION_SCHEMA, "reference": reference, "stage": stage, "audit": entry,
            "note": "nothing was written; keep the reference and pass it back with --ref, or select again"}


def reference(common: str, ws, ident: str, lifetime: str | None, *, implementation: str | None) -> dict:
    """A reference to one audit lifetime, operated from the workspace's checkout."""
    return {"schema": REFERENCE_SCHEMA, "repository": common, "checkout": str(ws.repo), "owner": str(ws.repo),
            "workspace": ws.rel, "audit_id": ident, "lifetime": lifetime,
            "closes": closed_names(common, ws.slug, ident), "implementation": implementation}


def validate_reference(value: object) -> dict:
    from stewart.assignment import audit_id
    from stewart.workspace import relative
    if not isinstance(value, dict) or set(value) != _REFERENCE_FIELDS or value["schema"] != REFERENCE_SCHEMA:
        raise StewartError(f"an audit reference needs exactly {sorted(_REFERENCE_FIELDS)} with schema "
                           f"{REFERENCE_SCHEMA}", reason="reference_schema",
                           next_steps=["select the audit again and keep the printed reference unchanged"])
    for key in ("repository", "checkout"):
        if not isinstance(value[key], str) or not Path(value[key]).is_absolute():
            raise StewartError(f"reference {key} must be an absolute path", reason="reference_schema")
    relative(value["workspace"])
    audit_id(value["audit_id"])
    if value["lifetime"] is not None:
        from stewart._repository import session_uuid
        session_uuid(value["lifetime"])
    if value["implementation"] is not None and (not isinstance(value["implementation"], str)
                                                or not _DIGEST.fullmatch(value["implementation"])):
        raise StewartError("reference implementation must be a package digest or null", reason="reference_schema")
    if value["owner"] is not None and (not isinstance(value["owner"], str) or not Path(value["owner"]).is_absolute()):
        raise StewartError("reference owner must be an absolute path or null", reason="reference_schema")
    if not isinstance(value["closes"], list) or not all(isinstance(name, str) for name in value["closes"]):
        raise StewartError("reference closes must list closing names", reason="reference_schema")
    return value


def load_reference(location: Path) -> dict:
    info, data = read_regular(Path(location))
    if data is None:
        raise StewartError(f"reference file is not a readable regular file: {location} ({info['kind']})",
                           reason="reference_schema", retained=[str(location)])
    try:
        value = loads_control(data)
    except (ValueError, RecursionError) as exc:
        raise StewartError(f"reference is not unambiguous control JSON: {exc}", reason="reference_schema",
                           retained=[str(location)]) from exc
    return validate_reference(value)


@dataclass(frozen=True)
class Binding:
    """A revalidated reference: the workspace to operate on, its audit ID and the bound lifetime."""

    ws: object
    audit_id: str
    lifetime: str | None
    stage: str


def bind(reference: dict, *, checkout: Path | None = None) -> Binding:
    """Revalidate a kept reference against the records as they are now.

    The checkout (the reference's own, or ``checkout`` when the caller runs
    from another maintainer checkout) must be a maintainer checkout of the
    reference's Git common directory. A reference bound to a lifetime refuses a
    replacement lifetime; one taken before any session refuses the session
    prepared since. A different recorded implementation makes it stale.
    """
    from stewart._repository import maintainer
    from stewart.workspace import workspace as _workspace
    reference = validate_reference(reference)
    checkout = Path(checkout if checkout is not None else reference["checkout"])
    if not checkout.is_dir():
        raise StewartError(f"the reference's checkout is gone: {checkout}", reason="reference_checkout_missing",
                           retained=[str(checkout)],
                           next_steps=["pass --repo naming another maintainer checkout of the same repository, or "
                                       "discover from one and select the audit again"])
    identity = maintainer(checkout)
    if identity["common_dir"] != reference["repository"]:
        raise StewartError("the reference names another repository than its checkout's", reason="reference_mismatch",
                           retained=[reference["repository"], identity["common_dir"]])
    ws = _workspace(checkout, reference["workspace"])
    stage = require_lifetime(identity["common_dir"], ws, reference["audit_id"], reference["lifetime"], bound=True,
                             implementation=reference["implementation"], closes=reference["closes"])
    return Binding(ws, reference["audit_id"], reference["lifetime"], stage)


def require_lifetime(common: str, ws, ident: str, lifetime: str | None, *, bound: bool = True,
                     implementation: str | None = None, closes: list[str] | None = None) -> str:
    """Refuse when the audit's present lifetime is not the bound one; return the observed stage."""
    from stewart._repository import session_location
    from stewart.close import closing_entries
    from stewart.session import capture_receipt
    if not bound and lifetime is None:
        return "unbound"
    session = session_location(common, ws, ident)
    entries = closing_entries(common, ws, ident)
    unfinished = [entry for entry in entries if not entry["complete"] and "problem" not in entry]
    if os.path.lexists(session) and not unfinished:
        try:
            record, _ = capture_receipt(session / "session.json", what="session record")
        except StewartError as exc:
            exc.code = EXIT_UNVERIFIED
            raise
        present = record.get("session_uuid")
        if lifetime is None:
            raise StewartError(f"audit {ident} was referenced before its session {present} existed; a draft "
                               "reference never selects a later lifetime", reason="reference_stale",
                               next_steps=["select the audit again to bind its session lifetime"])
        if present != lifetime:
            raise StewartError(f"audit {ident}'s present lifetime is {present}, not the referenced {lifetime}",
                               reason="reference_stale", retained=[str(session)],
                               next_steps=["select the audit again; a replacement lifetime is never chosen silently"])
        from stewart.implementation import recorded_digest
        if implementation is not None and recorded_digest(record.get("stewart")) != implementation:
            raise StewartError("the session's recorded implementation differs from the reference's",
                               reason="reference_stale", next_steps=["select the audit again"])
        return "live"
    names = [entry["session_uuid"] for entry in entries]
    if lifetime is None:
        newer = [str(name) for name in names if closes is not None and str(name) not in closes]
        if newer:
            raise StewartError(f"audit {ident} closed after this reference was taken ({', '.join(newer)}); a draft "
                               "reference never selects a later draft or lifetime", reason="reference_stale",
                               next_steps=["discover and select the audit again"])
        return "draft"
    if lifetime in names:
        return "closing" if any(entry["session_uuid"] == lifetime for entry in unfinished) else "closed"
    raise StewartError(f"audit {ident} has no lifetime {lifetime} any more", reason="reference_stale",
                       next_steps=["discover and select the audit again"])
