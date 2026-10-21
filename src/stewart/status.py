"""Read-only session view: facts, acknowledgments, dispositions and next actions.

Observed facts, actor acknowledgments, auditor-reported completion and
maintainer dispositions live in separate fields and are never merged into a
grade. Missing, corrupt, unsupported or conflicting records are reported in
place and left untouched. The view's success is independent of the session's
failures: inspecting a broken session is itself a successful inspection.
"""

from __future__ import annotations

import os
from pathlib import Path

from stewart import _util as _hash
from stewart._git import git
from stewart.captured import collection_files, runtime_observations
from stewart.runtime import record_state
from stewart.collect import custody_gaps
from stewart._bootstrap import (
    EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, EXIT_UNVERIFIED, StewartError, capture_regular, combined_code, problem_code,
    read_regular,
)
from stewart.launch_profile import EXIT_LOG, handoff_prompt, load_profile, read_exit_log, render_command, render_probe
from stewart.session import (
    ATTEMPT_SCHEMA,
    COLLECTION_SCHEMA,
    LAUNCH_SCHEMA,
    MESSAGE_SCHEMA,
    PREPARE_STAGES,
    RELEASE_SCHEMA,
    RETENTION_SCHEMA,
    TRIAGE_SCHEMA,
    list_records,
    load_session,
    maintainer_state,
    read_receipt,
    session_dir,
    tool_identity,
)
from stewart.workspace import Workspace, contained
from stewart.triage import bound_disposition

#: Schema 11 separates failed captures and current launch readiness from custody.
#: Schema 12 adds the exit code and the attention items that set it, the lock
#: and storage locations, and drops the live report path; a recovery command
#: appears only when the supplied runtime fails verification.
#: Schema 13 adds the observed stage, a reference for the lifetime, the
#: writing and viewing implementations with any handoff, resource dispositions
#: and request records, and binds each action to its operands and lifetime.
STATUS_SCHEMA = "stewart.status/13"
LIST_SCHEMA = "stewart.status-list/1"
CLOSED_VIEW_SCHEMA = "stewart.status-closed/2"
DRAFT_VIEW_SCHEMA = "stewart.status-draft/1"


def _problem(problems: list[dict], record: str, exc: StewartError) -> None:
    problems.append({"record": record, "reason": exc.reason, "message": str(exc)})


def _git_head(location: Path, git_admin: str) -> str | None:
    """HEAD of the checkout at ``location``, asked of the administration its verified .git names."""
    result = git(location, f"--git-dir={git_admin}", "rev-parse", "HEAD", check=False)
    return result.stdout.decode("utf-8", "replace").strip() if result.returncode == 0 else None


def command(ws: Workspace, *args: str) -> dict:
    """Pin the manager implementation independently of the explicit destination."""
    from stewart._invocation import current
    return current().command("--repo", str(ws.repo), "--workspace", ws.rel, *args)


def _auditor_report(collection_dir: Path, name: str, expected_digest: str | None,
                        record: dict | None, collected_head: str | None) -> dict:
    """Attribute a validated captured declaration, never a live report or prose line."""
    from stewart.report_declaration import session_declaration_expectations, validate_report_declaration

    base = {"attributed_to": "auditor", "source": f"collection {name} REPORT.md",
            "note": "the auditor's declaration; not an observed process exit or a maintainer judgment"}
    def claims(*, declaration=None, **context):
        return {field: {**base, "value": declaration[field] if declaration else None, **context}
                for field in ("completion", "report_kind")}
    if record is None:
        return claims(reason="session_unavailable")
    if expected_digest is None:
        data = b""
        base["source"] = None
    else:
        info, data = read_regular(collection_dir / "REPORT.md")
        if data is None or info.get("sha256") != expected_digest:
            return claims(reason="evidence_tampered")
    expected, sources = session_declaration_expectations(record, collected_head)
    result = validate_report_declaration(data, expected=expected, sources=sources)
    return claims(declaration=result["declaration"] if result["status"] == "valid" else None, validation=result)


def _runtime_view(parent: Path, record: dict, phases: set[str], problems: list[dict],
                  session_record: dict | None) -> dict | None:
    """Expose verified captured observations, without consulting today's runtime."""
    try:
        state = record_state(record, session_record=session_record)
        if phases in ({"collection"}, {"before", "after"}):
            from stewart.runtime import record_assets
            record_assets(record, session_record=session_record)
        captures = runtime_observations(parent, state, phases=phases)
        return {"identity": state["identity"], "observations": {
            phase: {"path": str(parent / state["observations"][phase]["directory"]),
                    "state": capture.get("state", "captured"), "error": capture.get("error"),
                    **{key: capture[key] for key in ("matches_expected", "movement", "captured_files", "limit")}}
            for phase, capture in captures.items()}}
    except StewartError as exc:
        _problem(problems, "runtime", exc)
        return None


def _collections(session: Path, ident: str, session_record: dict | None) -> tuple[list[dict], dict[str, dict]]:
    """Collection views and their receipts, without promoting discovery to custody.

    A complete receipt can record an incomplete archive. Release associations
    must verify the selected captured bytes before claiming recoverability.
    """
    views = []
    receipts: dict[str, dict] = {}
    for entry in list_records(session / "collections"):
        name = entry.name
        # A locator is not a claim that capture succeeded. Keep it even for a
        # partial collection so recovery never substitutes the live report.
        view: dict = {"name": name, "path": str(entry), "report_path": str(entry / "REPORT.md"),
                      "complete": False, "problems": []}
        if not (entry / "STARTED.json").exists():
            view["problems"].append({"record": "STARTED.json", "reason": "record_missing",
                                     "message": "collection directory without a start record"})
        else:
            try:
                view["started_at"] = read_receipt(entry / "STARTED.json", what="collection start").get("collected_at")
            except StewartError:
                view["started_at"] = None
        try:
            receipt = read_receipt(entry / "collection.json", what="collection receipt")
        except StewartError as exc:
            if exc.reason == "record_missing":
                view["problems"].append({"record": "collection.json", "reason": "collection_incomplete",
                                         "message": "partial attempt: started but no receipt was written"})
            else:
                _problem(view["problems"], "collection.json", exc)
            views.append(view)
            continue
        if receipt.get("schema_version") != COLLECTION_SCHEMA or receipt.get("audit_id") != ident:
            view["problems"].append({"record": "collection.json", "reason": "collection_schema",
                                     "message": "unsupported receipt schema or foreign audit ID"})
            views.append(view)
            continue
        summary = receipt.get("inventory") or {}
        view.update({
            "complete": True,
            "collected_at": receipt.get("collected_at"),
            "errors": receipt.get("errors", []),
            "report_status": receipt.get("report_status"),
            "report_sha256": receipt.get("report_sha256"),
            "collected_head": receipt.get("checkout", {}).get("head"),
            "declaration": receipt.get("declaration"),
            "git_discovery": receipt.get("git_discovery"),
            "unexpected_paths": receipt.get("unexpected_paths"),
            "checkout_commit_changed": receipt.get("checkout_commit_changed"),
            "maintainer_status_changed_since_prepare": receipt.get("maintainer_status_changed_since_prepare"),
            "auditor_stopped": {"acknowledged": receipt.get("auditor_stopped"),
                                "by": receipt.get("auditor_stopped_acknowledged_by"),
                                "kind": receipt.get("auditor_stop_kind")},
            "inventory": {
                "sha256": summary.get("sha256"),
                "counts": summary.get("counts"),
                "archived": len(summary.get("archived", [])),
                "omitted": summary.get("omitted", []),
                "unreadable": summary.get("unreadable", []),
                "unsupported": summary.get("unsupported", []),
                "boundaries": summary.get("boundaries", []),
                "movement": summary.get("movement"),
            },
            "gaps": [gap["id"] for gap in custody_gaps(receipt)],
            "gap_codes": [{"id": gap["id"], "code": gap["code"]} for gap in custody_gaps(receipt)],
        })
        receipts[name] = receipt
        view["runtime"] = _runtime_view(entry, receipt, {"collection"}, view["problems"], session_record)
        views.append(view)
    # Names share a second-granular stamp; order by the recorded time so "newest" is the last collection taken.
    views.sort(key=lambda item: (item.get("collected_at") or "", item["name"]))
    return views, receipts


def _profile_summary(loaded: dict) -> dict:
    profile = loaded["profile"]
    return {"path": loaded["path"], "sha256": loaded["sha256"], "harness": profile["harness"],
            "style": profile["style"], "model": profile["model"], "effort": profile["effort"],
            "has_probe": profile.get("probe") is not None}


def _release_capture(release: dict, complete: list[dict], receipts: dict[str, dict],
                     record: dict | None,
                     verified: dict[tuple[str, str], tuple[str | None, dict | None]]) -> None:
    """Associate frozen artifacts with bytes recoverable during this status read.

    The script and frozen declarations are auditor-written bytes, and a
    supplemental manifest is copied bytes, so a collection can capture them. A
    committed manifest and the committed ledger module cannot appear in a
    capture unless changed, and release refuses a changed pinned input, so they
    are left out. Discovery digests only select candidates: the shared capture
    reader verifies archive identity, unique regular members and payload bytes.
    Results are cached within one status call, never across observations.
    """
    grant = release.get("grant") or {}
    frozen = release.get("frozen") or {}
    supplemental = {item["path"] for item in (record or {}).get("inputs", []) if item.get("kind") == "supplemental"}
    candidates = [grant.get("script"), *(grant.get("freeze") or [])]
    if grant.get("protected_manifest") in supplemental:
        candidates.append(grant["protected_manifest"])
    artifacts = [rel for rel in candidates if isinstance(rel, str) and rel in frozen]
    release["frozen_artifacts"] = artifacts
    release["capture_problems"] = []
    for collection in complete:
        if collection["problems"]:
            continue
        name = collection["name"]
        receipt = receipts[name]
        # A different or absent source digest cannot match this release. Do not
        # read unrelated archived artifacts merely to summarize this one.
        files = receipt.get("checkout", {}).get("files", [])
        matching = [rel for rel in artifacts if any(
            item.get("path") == rel and item.get("sha256") == frozen[rel] for item in files)]
        pending = [rel for rel in matching if (name, rel) not in verified]
        directory = Path(collection["path"])

        def check(paths: list[str]) -> None:
            payloads = collection_files(directory, receipt, [f"files.tar:{rel}" for rel in paths])
            for rel in paths:
                verified[name, rel] = (_hash.sha256_bytes(payloads[f"files.tar:{rel}"]), None)

        if pending:
            try:
                # Healthy collections need one archive read for all candidates.
                check(pending)
            except StewartError as exc:
                if len(pending) == 1:
                    verified[name, pending[0]] = (None, {"reason": exc.reason, "message": str(exc)})
                else:
                    # One absent/ambiguous member must not hide a recoverable
                    # sibling. The same verifier decides each selected member.
                    for rel in pending:
                        try:
                            check([rel])
                        except StewartError as member_error:
                            verified[name, rel] = (None, {"reason": member_error.reason, "message": str(member_error)})
        for rel in matching:
            _, problem = verified[name, rel]
            if problem is not None:
                release["capture_problems"].append({"collection": name, "artifact": rel, **problem})
    release["captured_in"] = [
        c["name"] for c in complete
        if artifacts and all(verified.get((c["name"], rel), (None, None))[0] == frozen[rel] for rel in artifacts)
    ]
    release["uncaptured_artifacts"] = [
        rel for rel in artifacts
        if not any(verified.get((c["name"], rel), (None, None))[0] == frozen[rel] for c in complete)
    ]


def _records(session: Path, subdir: str, schema: int, ident: str, fields: tuple[str, ...]) -> list[dict]:
    views = []
    for entry in list_records(session / subdir, suffix=".json"):
        name = entry.name[: -len(".json")]
        view: dict = {"name": name, "path": str(entry), "problems": []}
        try:
            record = read_receipt(entry, what=f"{subdir} record")
        except StewartError as exc:
            _problem(view["problems"], entry.name, exc)
            views.append(view)
            continue
        if record.get("schema_version") != schema or record.get("audit_id") != ident:
            view["problems"].append({"record": entry.name, "reason": "record_schema",
                                     "message": "unsupported schema or foreign audit ID"})
        if not view["problems"] and "runtime" in fields:
            try:
                record_state(record)
            except StewartError as exc:
                _problem(view["problems"], entry.name, exc)
        view.update({field: record.get(field) for field in fields})
        views.append(view)
    views.sort(key=lambda item: (item.get("recorded_at") or "", item["name"]))
    return views


def _attempts(session: Path, ident: str, session_record: dict | None) -> list[dict]:
    views = []
    for entry in list_records(session / "attempts"):
        view: dict = {"name": entry.name, "path": str(entry), "problems": [], "resolved": False}
        reserved = entry / "RESERVED.json"
        if not reserved.exists():
            view["problems"].append({"record": "RESERVED.json", "reason": "record_missing",
                                     "message": "attempt directory without a reservation"})
        try:
            record = read_receipt(entry / "ATTEMPT.json", what="attempt record")
        except StewartError as exc:
            if exc.reason == "record_missing":
                view["problems"].append({"record": "ATTEMPT.json", "reason": "attempt_unresolved",
                                         "message": "reserved but never resolved; it is not reusable"})
            else:
                _problem(view["problems"], "ATTEMPT.json", exc)
            views.append(view)
            continue
        if record.get("schema_version") != ATTEMPT_SCHEMA or record.get("audit_id") != ident:
            view["problems"].append({"record": "ATTEMPT.json", "reason": "record_schema",
                                     "message": "unsupported schema or foreign audit ID"})
        view.update({
            "resolved": True,
            "release": record.get("release"),
            "process": record.get("process"),
            "approved_argv": record.get("approved_argv"),
            "child": record.get("child"),
            "endpoint": record.get("endpoint"),
            "child_receipt": record.get("child_receipt"),
            "ledger": record.get("ledger"),
            "errors": record.get("errors", []),
        })
        if not view["problems"]:
            view["runtime"] = _runtime_view(entry, record, {"before", "after"}, view["problems"], session_record)
        views.append(view)
    return views


def status(ws: Workspace, ident: str, *, profile: str | None = None, lifetime: str | None = None) -> dict:
    """Build the session view without writing, repairing or acknowledging anything.

    ``profile`` names a working-tree launch profile to render the handoff from
    instead of the one pinned at preparation, for a session whose pinned recipe
    went stale; the view names both so the departure is visible. ``lifetime``
    binds the view to one session lifetime; another one is refused.
    """
    from stewart._repository import checkout_git_admin, maintainer, registered_session
    from stewart.close import close_summary, closing_entries
    common = maintainer(ws.repo)["common_dir"]
    session = session_dir(ws, ident)
    closes = [close_summary(entry, ws.repo) for entry in closing_entries(common, ws, ident)]
    if lifetime is not None and not session.is_dir() and lifetime not in [item["session_uuid"] for item in closes]:
        raise StewartError(f"audit {ident} has no lifetime {lifetime}", reason="reference_stale",
                           next_steps=["discover and select the audit again"])
    finished = closes and all(item["complete"] and "problem" not in item for item in closes)
    if not session.is_dir() and (not closes or finished):
        from stewart.audits import draft_records
        from stewart.holdings import contexts_for
        drafts = draft_records(common, ws.slug, ident)
        known = {str(item["session_uuid"]) for item in closes}
        # A draft recorded after every close (a released ID drafted again) is the present stage.
        later = [item for item in drafts if item.get("state") != "invalid" and known <= set(item.get("closed_before", []))]
        if (later if closes else (drafts or contexts_for(common, ws.slug, ident))):
            # A registry row means a session existed and lost its records; that comes first.
            try:
                registered_session(common, session)
            except StewartError as exc:
                exc.code = EXIT_REFUSED
                raise
            return _draft_view(ws, ident, common, closes)
    # Closing records come first: a closed or closing session's removed
    # records are the close's doing, not records that went missing. Every
    # session under one ID shares its directory, and an incomplete close
    # refuses any new preparation, so an incomplete close is this session's.
    unfinished = any(not item["complete"] and "problem" not in item for item in closes)
    if closes and (unfinished or not session.is_dir()):
        if not unfinished:
            # A later session prepared under a released ID may itself have
            # lost its records; its registry row says so.
            try:
                registered_session(common, session)
            except StewartError as exc:
                exc.code = EXIT_REFUSED
                raise
        return _closed_view(ws, ident, closes, common)
    if not session.is_dir():
        # A registry row for this path means the ID was prepared and its
        # records went missing: that refusal names the row and the refs. A
        # targeted view refuses (2); the listing reports the loss as 3.
        try:
            registered_session(common, session)
        except StewartError as exc:
            exc.code = EXIT_REFUSED
            raise
        raise StewartError(
            f"no session for audit {ident} in workspace {ws.rel}: {session}", reason="session_missing",
            next_steps=["check the audit ID against the committed prompt's audit_id; status without "
                        "--audit-id lists this workspace's sessions",
                        "if the ID is right and the assignment was never prepared, prepare the committed prompt"],
        )
    try:
        owner = read_receipt(session / "session.json", what="session record").get("repo")
    except StewartError:
        owner = None
    if owner is not None and owner != str(ws.repo):
        from stewart.session import owner_refusal
        raise owner_refusal(owner, session, ident)
    viewer = tool_identity()
    view: dict = {
        "schema": STATUS_SCHEMA,
        "audit_id": ident,
        "workspace": ws.to_json(),
        "tool": viewer,
        "session": {"path": str(session), "schema_version": None, "supported": False, "problems": [],
                    "stewart": None, "same_build_as_viewer": None},
        "assignment": None,
        "identities": {},
        "coordination": {},
        "launch_profile": None,
        "launch_profile_override": None,
        "harness_exits": [],
        "launches": [],
        "messages": [],
        "collections": [],
        "auditor_reported": {field: {"value": None, "attributed_to": "auditor", "source": None}
                             for field in ("completion", "report_kind")},
        "dispositions": [],
        "retentions": [],
        "releases": [],
        "attempts": [],
        "runtime_recoveries": [],
        "preparation": {"state": "unknown"},
        "experiment": {"state": "unknown"},
        "manager_storage": _manager_storage(common, None),
        "closes": closes,
        "outstanding": [],
        "next_actions": [],
    }
    problems = view["session"]["problems"]
    failure = None
    failure_present = (session / "PREPARE-ERROR.json").exists() or (session / "PREPARE-ERROR.json").is_symlink()
    if failure_present:
        try:
            failure = read_receipt(session / "PREPARE-ERROR.json", what="preparation failure")
            problems.append({"record": "PREPARE-ERROR.json", "reason": "prepare_failed",
                             "message": str(failure.get("error"))})
        except StewartError as exc:
            _problem(problems, "PREPARE-ERROR.json", exc)
    # A preparation that recorded its failure at or before a stage may never
    # have written what that stage writes; its absence is that failure, not
    # records that went missing. Anything present is still verified.
    stage = failure.get("stage") if isinstance(failure, dict) else None

    def unreached(step: str) -> bool:
        return stage in PREPARE_STAGES[:PREPARE_STAGES.index(step) + 1]

    record = None
    retention = {"status": "unassessed", "pins": None}
    try:
        _, record = load_session(ws, ident, check_retention=False)
        view["session"]["supported"] = True
        from stewart._repository import verify_retention
        try:
            retention = {"status": "verified", "pins": verify_retention(ws.repo, record)}
        except StewartError as exc:
            listed = git(ws.repo, "for-each-ref", "--format=%(refname)",
                         f"refs/stewart/sessions/{record['session_uuid']}/", check=False)
            if unreached("retention") and not listed.returncode and not listed.stdout.strip():
                retention = {"status": "not_created", "pins": record.get("retention"),
                             "note": f"preparation failed during {stage}, before its refs existed"}
            else:
                retention = {"status": "invalid", "pins": record.get("retention"), "error": exc.to_json()}
                _problem(problems, "session commit retention", exc)
    except StewartError as exc:
        _problem(problems, "session.json", exc)
    try:
        raw = read_receipt(session / "session.json", what="session record")
        view["session"]["schema_version"] = raw.get("schema_version")
        # Which Stewart wrote the session is a recorded fact; whether it is the
        # same build as the viewer is derived, and None when the record is unstamped.
        writer = raw.get("stewart")
        view["session"]["stewart"] = writer if isinstance(writer, dict) else None
        if isinstance(writer, dict) and isinstance(writer.get("package_sha256"), str):
            view["session"]["same_build_as_viewer"] = writer["package_sha256"] == viewer["package_sha256"]
    except StewartError:
        pass
    if record is not None:
        meta = record["assignment"]
        view["assignment"] = meta
        worktree = Path(record["worktree"])
        present = worktree.is_dir()
        # Git runs in the auditor checkout only through the administration its own .git names
        # and this session's lifetime owns: a planted link or pointer would answer for another
        # repository or another session's checkout.
        git_admin = admin_error = None
        if present:
            try:
                git_admin = checkout_git_admin(worktree, record["common_dir"], record["session_uuid"])
            except StewartError as exc:
                git_admin, admin_error = None, str(exc)
        worktree_head = _git_head(worktree, git_admin) if git_admin else None
        try:
            destination_exists = contained(ws.repo, meta["report_path"]).exists()
        except StewartError as exc:
            destination_exists = None
            _problem(problems, "report destination", exc)
        maintainer_now = None
        try:
            maintainer_now = maintainer_state(ws.repo)
        except StewartError as exc:
            _problem(problems, "maintainer checkout", exc)
        view["identities"] = {
            "session_uuid": record["session_uuid"],
            "retention": retention,
            "prompt_commit": record["prompt_commit"],
            "target_commit": record.get("target_commit"),
            "prompt_sha256": record["prompt_sha256"],
            "prepared_at": record["prepared_at"],
            "worktree": {
                "path": str(worktree),
                "exists": present,
                "head": worktree_head,
                "head_matches_prompt": None if worktree_head is None else worktree_head == record["prompt_commit"],
            },
            "maintainer": {
                "head": None if maintainer_now is None else maintainer_now["head"],
                "status_changed_since_prepare": None if maintainer_now is None else maintainer_now != record["maintainer_before"],
            },
            "report_destination_exists": destination_exists,
        }
        view["identities"]["worktree"]["lock"] = _lock_view(present, git_admin, admin_error, record["session_uuid"])
        view["manager_storage"] = _manager_storage(common, record)
        private_launch = capture_regular(session / "LAUNCH.md")
        public_launch = worktree / record["handoff"]["path"]
        launch = capture_regular(public_launch)
        pinned_handoff = record["handoff"]["sha256"]
        private_matches = private_launch.get("sha256") == pinned_handoff
        public_matches = launch.get("sha256") == pinned_handoff
        runtime_preparation, pristine_available = None, False
        if not (unreached("runtime") and not os.path.lexists(session / "runtime-pristine")):
            try:
                from stewart.captured import pristine_runtime
                pristine_runtime(session, record)
                pristine_available = True
            except StewartError as exc:
                _problem(problems, "runtime-pristine", exc)
        if not (unreached("runtime") and not os.path.lexists(session / "RUNTIME-PREPARED.json")):
            try:
                prepared_runtime = read_receipt(session / "RUNTIME-PREPARED.json", what="runtime preparation")
                runtime_preparation = _runtime_view(session, prepared_runtime, {"preparation"}, problems, record)
            except StewartError as exc:
                _problem(problems, "RUNTIME-PREPARED.json", exc)
        runtime_prepared = (runtime_preparation is not None and pristine_available
                            and runtime_preparation["observations"]["preparation"]["matches_expected"])
        # Historical custody is checked above. Starting another auditor also
        # requires the currently exposed code, without executing any of it.
        from stewart._bootstrap import observe_runtime
        from stewart.runtime import observation_matches, ENDPOINT_LIMIT
        try:
            observed, _ = observe_runtime(Path(record["runtime"]["root"]))
            current_runtime = {"matches_expected": observation_matches(observed, record["runtime"]),
                               "observation": observed, "error": None, "limit": ENDPOINT_LIMIT}
        except (OSError, StewartError) as exc:
            current_runtime = {"matches_expected": False, "observation": None, "error": str(exc),
                               "limit": ENDPOINT_LIMIT}
        view["preparation"] = {
            "state": ("failed" if failure_present else
                      ("ready" if current_runtime["matches_expected"] else "runtime_unavailable")
                      if private_matches and public_matches and worktree.is_dir() and runtime_prepared else
                      "worktree_missing" if private_matches and not worktree.is_dir() else "incomplete"),
            "failure": failure,
            "failure_path": str(session / "PREPARE-ERROR.json") if failure_present else None,
            "launch_path": str(public_launch),
            "launch_handoff": launch,
            "private_launch_path": str(session / "LAUNCH.md"),
            "private_launch_handoff": private_launch,
            "handoff_matches": {"private": private_matches, "public": public_matches},
            "auditor_scope": record["auditor_scope"],
            "runtime": runtime_preparation,
            "current_runtime": current_runtime,
            "pristine_runtime_available": pristine_available,
            # Offered only when the supplied runtime itself fails verification.
            "runtime_recovery": command(ws, "recover-runtime", "--audit-id", ident, "--actor", "<name>")
            if pristine_available and not current_runtime["matches_expected"] else None,
            "note": "handoff and filesystem observations only; no auditor start or stop is inferred",
        }
        from stewart.captured import runtime_recovery
        for entry in list_records(session / "runtime-recoveries"):
            item = {"name": entry.name, "path": str(entry), "state": "unassessed", "problems": []}
            try:
                recovered, capture = runtime_recovery(session, entry.name, record)
                item.update({"state": "recovered" if recovered["materialized"] and not recovered.get("error")
                             and not recovered.get("observation_error") else "failed",
                             "runtime": recovered["runtime"]["identity"], "capture": capture,
                             "error": recovered.get("error"), "observation_error": recovered.get("observation_error"),
                             "actor": recovered["actor"], "activation": recovered["activation"]})
            except StewartError as exc:
                item["state"] = "incomplete" if exc.reason == "record_missing" else "invalid"
                _problem(item["problems"], "RECOVERY.json", exc)
            view["runtime_recoveries"].append(item)
        pinned = record.get("launch_profile")
        if isinstance(pinned, dict):
            view["launch_profile"] = _profile_summary(pinned)
        if profile is not None:
            # An override is read from the working tree on request only; the
            # pinned copy stays what the session recorded.
            override = load_profile(ws, profile)
            view["launch_profile_override"] = _profile_summary(override)
        exits, exit_problems = read_exit_log(session)
        view["harness_exits"] = exits
        for message in exit_problems:
            problems.append({"record": EXIT_LOG, "reason": "exit_log_malformed", "message": message})
        resumed = None
        if (session / "RESUMED.json").exists():
            try:
                resumed = read_receipt(session / "RESUMED.json", what="resume record")
            except StewartError as exc:
                _problem(problems, "RESUMED.json", exc)
        view["coordination"] = {
            "mode": record["mode"],
            "writers_paused": {"acknowledged": record["writers_paused"],
                               "by": record.get("writers_paused_acknowledged_by"),
                               "note": record.get("writers_paused_note")},
            "hold": "paused hold recorded; release requires a bound triage and resume"
            if record["mode"] == "paused" else "none (snapshot)",
            "resumed": None if resumed is None else {
                "at": resumed.get("resumed_at"), "triage": resumed.get("triage"),
                "collection": resumed.get("collection"), "reason": resumed.get("reason"),
            },
        }
    view["launches"] = _records(session, "launches", LAUNCH_SCHEMA, ident,
                                ("recorded_at", "actor", "style", "model", "effort", "note", "launch_token"))
    view["messages"] = _records(session, "messages", MESSAGE_SCHEMA, ident,
                                ("recorded_at", "actor", "direction", "channel", "text"))
    view["collections"], receipts = _collections(session, ident, record)
    complete = [c for c in view["collections"] if c["complete"]]
    if complete:
        newest = complete[-1]
        view["auditor_reported"] = _auditor_report(
            Path(newest["path"]), newest["name"], newest.get("report_sha256"), record, newest.get("collected_head"))
    view["dispositions"] = _records(
        session, "triage", TRIAGE_SCHEMA, ident,
        ("recorded_at", "actor", "collection", "collection_sha256", "report_sha256", "report_gap",
         "decision", "counts", "follow_up"),
    )
    for disposition in view["dispositions"]:
        if disposition["problems"]:
            continue
        try:
            if record is None:
                raise StewartError("cannot validate disposition without its supported session", reason="session_unavailable")
            bound, _, _, _ = bound_disposition(session, ident, disposition["name"], ws.rel, session_record=record)
            disposition.update({key: bound[key] for key in disposition if key in bound and key not in ("name", "path", "problems")})
        except StewartError as exc:
            _problem(disposition["problems"], "evidence binding", exc)
            view["outstanding"].append(f"triage {disposition['name']} cannot authorize retention or resume: {exc}")
    view["retentions"] = _records(session, "retention", RETENTION_SCHEMA, ident,
                                  ("recorded_at", "triage", "collection", "published"))
    view["releases"] = _records(session, "releases", RELEASE_SCHEMA, ident,
                                ("recorded_at", "actor", "approved_argv", "argv", "child", "frozen", "grant", "runtime"))
    verified: dict[tuple[str, str], tuple[str | None, dict | None]] = {}
    for item in view["releases"]:
        item["consumed"] = (session / "attempts" / item["name"]).exists()
        # A failed read has no grant, and a foreign/unsupported record's grant
        # cannot describe our artifacts. Keep its diagnostics without deriving
        # capture associations or assuming the success-only fields exist.
        if not item["problems"]:
            item["runtime"] = _runtime_view(session / "releases", item, {"release"}, item["problems"], record)
        if not item["problems"]:
            _release_capture(item, complete, receipts, record, verified)
        item.pop("grant", None)
    view["attempts"] = _attempts(session, ident, record)
    if record is not None:
        grant = record["assignment"].get("experiment")
        valid_releases = [item for item in view["releases"] if not item["problems"]]
        # A missing completed attempt receipt is the unresolved case. Every
        # other record problem is invalid evidence, even beside a healthy
        # release or a genuinely unresolved reservation.
        invalid_records = any(item["problems"] for item in view["releases"]) or any(
            problem["reason"] != "attempt_unresolved"
            for item in view["attempts"] for problem in item["problems"])
        view["experiment"] = {
            "permission": None if grant is None else grant["permission"],
            "state": ("not_granted" if grant is None else
                      "construction_only" if grant["permission"] == "construction" else
                      "records_invalid" if invalid_records else
                      "attempt_unresolved" if any(not item["resolved"] for item in view["attempts"]) else
                      "released" if any(not item["consumed"] for item in valid_releases) else
                      "attempt_recorded" if view["attempts"] else
                      "records_invalid" if view["releases"] else "awaiting_review"),
            "note": "authorization and recorded operations only; neither artifact readiness nor scientific success",
        }
    if record is not None:
        from stewart.session import bind_lifetime
        bind_lifetime(record, lifetime, session)
    _derive_actions(ws, ident, view, record, profile)
    _identity_and_holdings(ws, ident, view, record, common, raw_stamp=view["session"]["stewart"])
    view["attention"] = _attention(view)
    view["exit_code"] = combined_code(item["code"] for item in view["attention"])
    return view


#: Status actions that only read; every other action is a mutation bound to the session's writer.
_READ_ONLY_ACTIONS = frozenset({"triage-draft", "handoff"})


def _rebind(action: dict, handoff: dict, lifetime: str | None) -> dict | None:
    """The same operation arguments under another invocation prefix, bound to the session lifetime."""
    argv = action.get("argv")
    if not argv or "--" not in argv:
        return action
    arguments = argv[argv.index("--") + 1:]
    if lifetime is not None and "--lifetime" not in arguments and arguments[:1] == ["--repo"]:
        arguments = [*arguments[:4], "--lifetime", lifetime, *arguments[4:]]
    if handoff is None:
        return {**action, "argv": [*argv[:argv.index("--") + 1], *arguments]}
    if handoff["state"] != "verified":
        return None
    return {**action, "argv": [*handoff["argv"][:handoff["argv"].index("--") + 1], *arguments], "env": {},
            "runtime": handoff["runtime"], "handoff": "the recorded implementation; run it explicitly"}


_OPERATIONS = {"handoff": None, "launch": "record_launch", "collect": "collect", "triage-draft": "triage_draft",
               "triage": "triage", "retain": "retain", "resume": "resume", "run": "run", "release": "release",
               "close": "close", "fresh_assignment": "initialize", "recover-runtime": "recover_runtime",
               "prepare": "prepare"}


def _flag(action: dict, name: str) -> str | None:
    argv = action.get("argv") or []
    return argv[argv.index(name) + 1] if name in argv[:-1] else None


def _bind_operands(action: dict, view: dict) -> None:
    """Name the API operation and the exact records an action acts on, with the digests read for this view."""
    action["operation"] = _OPERATIONS.get(action["action"], action["action"])
    operands: dict = {}
    def digest(items: list[dict], name: str, record: str | None) -> str | None:
        found = next((item for item in items if item["name"] == name), None)
        if found is None:
            return None
        return read_regular(Path(found["path"]) / record if record else Path(found["path"]))[0].get("sha256")

    collection = _flag(action, "--collection")
    if collection is not None:
        operands.update(collection=collection,
                        collection_sha256=digest(view["collections"], collection, "collection.json"))
    triage = _flag(action, "--triage")
    if triage is not None:
        operands.update(triage=triage, triage_sha256=digest(view["dispositions"], triage, None))
    release = _flag(action, "--release")
    if release is not None:
        operands.update(release=release, release_sha256=digest(view["releases"], release, None))
    action["operands"] = operands


def _identity_and_holdings(ws: Workspace, ident: str, view: dict, record: dict | None, common: str, *,
                           raw_stamp: dict | None) -> None:
    """Stage, reference, implementation, resources and requests; mutation actions follow the writer."""
    from stewart.audits import reference
    from stewart.implementation import compare, recorded_digest
    from stewart.request_keys import request_summaries
    from stewart.holdings import closeout
    lifetime = record["session_uuid"] if record is not None else None
    view["implementation"] = compare(raw_stamp, ["--repo", str(ws.repo), "--workspace", ws.rel, "status",
                                                 "--audit-id", ident], current=view["tool"])
    view["reference"] = reference(common, ws, ident, lifetime, implementation=recorded_digest(raw_stamp)) \
        if record is not None else None
    handoff = view["implementation"].get("handoff") if view["implementation"]["same"] is False else None
    actions = []
    for action in view["next_actions"]:
        _bind_operands(action, view)
        if action["action"] in _READ_ONLY_ACTIONS:
            actions.append(_rebind(action, None, lifetime) if action.get("argv") else action)
            continue
        if view["implementation"]["same"] is None and record is not None and not (
                action["action"] == "close" and "--abandon" in (action.get("argv") or [])):
            # Mutations refuse a session whose writer is unrecorded (implementation_unrecorded); only an
            # abandon accepts it, so no other mutation is offered.
            view["outstanding"].append(f"{action['action']} is withheld: the session record names no verifiable "
                                       "writing implementation, so mutations refuse it; close --abandon still "
                                       "retires it")
            continue
        rebound = _rebind(action, handoff, lifetime)
        if rebound is None:
            view["outstanding"].append(f"{action['action']} needs the implementation that wrote this session, which "
                                       "cannot be offered: missing " + ", ".join(handoff["missing"]))
        else:
            actions.append(rebound)
    if view["implementation"]["same"] is None and record is not None and not any(
            action["action"] == "close" and "--abandon" in (action.get("argv") or []) for action in actions):
        abandon = {"action": "close",
                   "prerequisites": ["the session record names no verifiable writing implementation; an abandon is "
                                     "the one mutation that accepts it, and it removes the session's checkout"],
                   **command(ws, "close", "--audit-id", ident, "--actor", "<name>", "--abandon", "--reason",
                             "<reason>")}
        _bind_operands(abandon, view)
        actions.append(_rebind(abandon, None, lifetime))
    view["next_actions"] = actions
    try:
        view["resources"] = closeout(ws, ident, lifetime=lifetime)
    except StewartError as exc:
        view["resources"] = []
        view["session"]["problems"].append({"record": "resources", "reason": exc.reason, "message": str(exc)})
    view["requests"] = [{key: item.get(key) for key in ("key", "operation", "state", "lifetime", "recorded_at")}
                        for item in request_summaries(common, [])
                        if (item.get("audit") or {}).get("audit_id") == ident
                        and (item.get("audit") or {}).get("workspace") == ws.rel]
    preparation = view["preparation"].get("state")
    complete = [c for c in view["collections"] if c["complete"]]
    triaged = {d.get("collection") for d in view["dispositions"] if not d["problems"]}
    view["stage"] = ("unverified" if record is None else
                     "closing" if any(not item["complete"] and "problem" not in item for item in view["closes"]) else
                     "preparation_failed" if preparation == "failed" else
                     "preparation_incomplete" if preparation == "incomplete" else
                     "triaged" if complete and complete[-1]["name"] in triaged else
                     "collected" if complete else "prepared")


def _draft_view(ws: Workspace, ident: str, common: str, closes: list[dict]) -> dict:
    """An audit recorded before any session: its draft records, their files now, and what comes next.

    Earlier closes of a released audit ID are history beside the new draft.
    """
    from stewart.audits import closed_names, draft_files, draft_records, reference
    from stewart.holdings import contexts_for, closeout
    from stewart.request_keys import request_summaries
    drafts = draft_records(common, ws.slug, ident)
    view: dict = {"schema": DRAFT_VIEW_SCHEMA, "audit_id": ident, "workspace": ws.to_json(), "tool": tool_identity(),
                  "stage": "draft" if drafts else "context",
                  "drafts": [{**item, "files": draft_files(item)} if item.get("state") != "invalid" else item
                             for item in drafts],
                  "contexts": contexts_for(common, ws.slug, ident),
                  "reference": {**reference(common, ws, ident, None, implementation=None),
                                "closes": closed_names(common, ws.slug, ident)},
                  "closes": closes, "outstanding": [], "next_actions": []}
    view["resources"] = closeout(ws, ident, lifetime=None)
    view["requests"] = [{key: item.get(key) for key in ("key", "operation", "state", "recorded_at")}
                        for item in request_summaries(common, [])
                        if (item.get("audit") or {}).get("audit_id") == ident
                        and (item.get("audit") or {}).get("workspace") == ws.rel]
    here = [item for item in drafts if item.get("checkout") == str(ws.repo) and item.get("state") != "invalid"]
    if not here:
        view["outstanding"].append("no draft of this audit was recorded in this checkout; select it from the checkout "
                                   "that holds its prompt")
    else:
        view["next_actions"].append({
            "action": "prepare", "operation": "prepare", "operands": {},
            "prerequisites": ["author the five sections and remove UNASSIGNED; commit PROMPT.md alone",
                              "the committed prompt commit is what prepare pins"],
            **command(ws, "prepare", "--prompt-commit", "<prompt-commit>")})
    items = []
    for item in drafts:
        if item.get("state") == "invalid":
            items.append({"code": EXIT_UNVERIFIED, "source": f"draft {item['name']}", "reason": "draft_record_invalid",
                          "message": item["problem"]["message"]})
        elif item.get("state") == "partial":
            items.append({"code": EXIT_ATTENTION, "source": f"draft {item['name']}", "reason": "draft_incomplete",
                          "message": "an init started but recorded no outcome; inspect the prompt it intended"})
    view["attention"] = items
    view["exit_code"] = combined_code(item["code"] for item in items)
    return view


def _unchanged_since(worktree: Path, collection: dict) -> bool:
    """Whether a fresh no-follow inventory equals the one a collection recorded; a gone checkout is unchanged."""
    from stewart.collect import inventory
    if not worktree.is_dir():
        return True
    recorded = (collection.get("inventory") or {}).get("sha256")
    return recorded is not None and _hash.sha256_bytes(_hash.receipt_json_bytes(inventory(worktree))) == recorded


def _verified_capture(ws: Workspace, collection: dict, outstanding: list[str]) -> bool:
    """Whether a concluded close's collection is a verified capture; when it is not, say which prerequisite fails."""
    from stewart.coverage import require_capture
    try:
        receipt = read_receipt(Path(collection["path"]) / "collection.json", what="collection receipt")
        require_capture(ws.repo, Path(collection["path"]), receipt)
    except StewartError as exc:
        outstanding.append(f"a concluded close is not offered ({exc.reason}): {exc}; "
                           + "; ".join(exc.next_steps))
        return False
    return True


def _closed_view(ws: Workspace, ident: str, closes: list[dict], common: str) -> dict:
    """An audit ID whose session a close retired or is retiring: its closing records, read only.

    The view repeats the records' identity, acknowledgment and attributed
    claims, and observes at read time whether recorded leftovers remain. It
    passes no judgment on the audit.
    """
    view: dict = {"schema": CLOSED_VIEW_SCHEMA, "audit_id": ident, "workspace": ws.to_json(), "tool": tool_identity(),
                  "closes": closes, "audit_id_state": "reserved", "next_actions": []}
    items = _close_attention(closes)
    if any(item["reason"] == "closing_record_invalid" for item in items):
        view["audit_id_state"] = "unverified"
    elif any(item["reason"] == "close_incomplete" for item in items):
        view["audit_id_state"] = "close_incomplete"
        stopped = next(((item.get("stopped") or {}) for item in closes if not item["complete"] and "problem" not in item),
                       {})
        prerequisites = ["a rerun removes only what CLOSING.json recorded and writes CLOSED.json when done"]
        if stopped.get("judgment"):
            prerequisites = [f"the last attempt stopped before removing the checkout ({stopped['reason']}): "
                             f"{stopped['detail']}; everything that remained is kept",
                             "a rerun checks again and stops again unless the checkout is what the close judged "
                             "and its capture verifies; close --plan reports whether it would stop",
                             "no command cancels or supersedes a stopped close"]
        view["next_actions"].append({
            "action": "close",
            "prerequisites": prerequisites,
            **command(ws, "close", "--audit-id", ident, "--actor", "<name>"),
        })
    elif closes and all(item["released"] for item in closes):
        view["audit_id_state"] = "released"
        latest = closes[-1]
        view["next_actions"].append({
            "action": "prepare",
            "prerequisites": ["correct the cause the abandoned preparation recorded",
                              "any prompt commit that carries this assignment may be prepared"],
            **command(ws, "prepare", "--prompt-commit", latest.get("prompt_commit") or "<prompt-commit>"),
        })
    from stewart.audits import closed_names, reference
    from stewart.holdings import closeout
    view["reference"] = {**reference(common, ws, ident, None, implementation=None),
                         "closes": closed_names(common, ws.slug, ident)}
    # A closed audit uses nothing; what remains of the resources it used is explained here.
    view["resources"] = [item for item in closeout(ws, ident, lifetime=None)]
    view["attention"] = items
    view["exit_code"] = combined_code(item["code"] for item in items)
    return view


def _close_attention(closes: list[dict]) -> list[dict]:
    """Closing records are news when they do not verify (3), or a close is unfinished or left entries (1)."""
    items = []
    for item in closes:
        source = f"close {item['session_uuid']}"
        if "problem" in item:
            items.append({"code": EXIT_UNVERIFIED, "source": source, "reason": "closing_record_invalid",
                          "message": item["problem"]["message"]})
        elif not item["complete"] and (item.get("stopped") or {}).get("judgment"):
            items.append({"code": EXIT_ATTENTION, "source": source, "reason": "close_incomplete",
                          "message": "removal stopped before the checkout because what the close judged no longer "
                                     f"holds ({item['stopped']['reason']}): {item['stopped']['detail']}; the "
                                     "checkout and the session's records are kept"})
        elif not item["complete"]:
            items.append({"code": EXIT_ATTENTION, "source": source, "reason": "close_incomplete",
                          "message": "a removal stopped partway; rerun close to finish from the recorded inventory"})
        elif item["leftovers"]:
            items.append({"code": EXIT_ATTENTION, "source": source, "reason": "close_leftovers",
                          "message": "entries the session did not record remain in its checkout directory: "
                                     + ", ".join(item["leftovers"])})
    return items


def _lock_view(present: bool, git_admin: str | None, admin_error: str | None, lifetime: str) -> dict:
    """The auditor checkout's Git lock, read in the administration its verified .git names; Stewart never unlocks it.

    ``lifetime`` marks only this session's own lifetime lock; ``locked`` is None whenever the lock was not read.
    """
    from stewart._repository import LIFETIME_LOCK, worktree_lock
    if not present:
        return {"locked": None, "reason": None}
    if git_admin is None:
        return {"locked": None, "reason": None, "error": admin_error}
    try:
        reason = worktree_lock(git_admin)
    except StewartError as exc:
        return {"locked": None, "reason": None, "error": str(exc)}
    return {"locked": reason is not None, "reason": reason,
            "lifetime": reason is not None and reason.startswith(f"{LIFETIME_LOCK}{lifetime}:"),
            "note": "removal goes through close; Stewart prints no unlock or remove commands"}


def _manager_storage(common: str, record: dict | None) -> dict:
    """Where the manager's harness must allow writes for this repository's custody commands."""
    from stewart._repository import STORAGE, resolve_checkout_home
    home = record.get("checkout_home") if record else None
    if home is None:
        try:
            home = str(resolve_checkout_home())
        except StewartError:
            home = None
    return {"private": str(Path(common) / STORAGE), "checkout_home": home,
            "note": "every custody-writing command writes the private location; prepare, recover-runtime "
                    "and experiment runs also write the checkout home"}


def _attention(view: dict) -> list[dict]:
    """The items that make this view news, each with its exit code.

    Records that do not verify are 3. Recorded partial states (a failed
    preparation, a partial collection or unresolved attempt that is still the
    latest word) and gaps that no valid triage has addressed are news within
    the manager's role (1), as are a nonzero harness exit with no collection
    and records written by a different build. Routine next steps are not news.
    """
    items: list[dict] = []

    def add(code: int, source: str, reason: str, message: str) -> None:
        items.append({"code": code, "source": source, "reason": reason, "message": message})

    for problem in view["session"]["problems"]:
        add(problem_code(problem["reason"]), f"session {problem['record']}", problem["reason"], problem["message"])
    complete = [c for c in view["collections"] if c["complete"]]
    for c in view["collections"]:
        for problem in c["problems"]:
            # A complete collection taken after a partial one started supersedes it.
            superseded = (problem["reason"] == "collection_incomplete" and isinstance(c.get("started_at"), str)
                          and any((done.get("collected_at") or "") > c["started_at"] for done in complete))
            if not superseded:
                add(problem_code(problem["reason"]), f"collection {c['name']}", problem["reason"], problem["message"])
    triaged = {d.get("collection") for d in view["dispositions"] if not d["problems"]}
    if complete and complete[-1]["name"] not in triaged:
        for gap_id in complete[-1].get("gaps", []):
            code = next((gap["code"] for gap in complete[-1].get("gap_codes", []) if gap["id"] == gap_id), EXIT_ATTENTION)
            add(code, f"collection {complete[-1]['name']}", "custody_gap", gap_id)
    for kind in ("launches", "messages", "dispositions", "retentions", "releases", "runtime_recoveries"):
        for item in view[kind]:
            for problem in item.get("problems", []):
                add(problem_code(problem["reason"]), f"{kind} {item['name']}", problem["reason"], problem["message"])
    for release in view["releases"]:
        # Captured bytes that fail verification at read time do not verify.
        for problem in release.get("capture_problems", []):
            add(EXIT_UNVERIFIED, f"release {release['name']} capture {problem['collection']}", problem["reason"],
                f"{problem['artifact']}: {problem['message']}")
    attempts = view["attempts"]
    for index, attempt in enumerate(attempts):
        for problem in attempt["problems"]:
            if problem["reason"] == "attempt_unresolved" and index != len(attempts) - 1:
                continue
            add(problem_code(problem["reason"]), f"attempt {attempt['name']}", problem["reason"], problem["message"])
    preparation = view["preparation"]
    if preparation.get("state") == "runtime_unavailable":
        add(EXIT_UNVERIFIED, "supplied runtime", "runtime_unavailable",
            "the supplied runtime no longer matches its pinned manifest")
    elif preparation.get("state") == "worktree_missing":
        # Removal belongs to close; a checkout gone before any complete
        # collection took its evidence with it.
        if complete:
            add(EXIT_ATTENTION, "checkout", "worktree_missing",
                "the checkout is gone; only the existing collections remain as evidence")
        else:
            add(EXIT_UNVERIFIED, "checkout", "worktree_missing",
                "the checkout is gone and no complete collection captured it")
    elif preparation.get("state") == "incomplete":
        private = preparation.get("private_launch_handoff") or {}
        matches = preparation.get("handoff_matches") or {}
        if private.get("kind") == "missing":
            # The private copy is written first, so neither handoff was issued.
            add(EXIT_ATTENTION, "preparation", "preparation_incomplete",
                "no handoff exists and no failure was recorded: preparation was interrupted or is still running")
        else:
            for side in ("private", "public"):
                if matches.get(side) is False:
                    add(EXIT_UNVERIFIED, f"{side} handoff", "handoff_changed",
                        f"the {side} handoff is missing or differs from the digest preparation pinned")
    exits = view.get("harness_exits") or []
    if exits and exits[-1]["exit"] != 0 and not complete:
        add(EXIT_ATTENTION, "harness exit log", "harness_exit_nonzero",
            f"the launch command's harness exited {exits[-1]['exit']} and no collection exists")
    if view["session"].get("same_build_as_viewer") is False:
        add(EXIT_ATTENTION, "session writer", "different_build", "a different Stewart build wrote this session")
    # Earlier closes are history beside a live session, except records that
    # do not verify; their leftovers are news only in the closed view.
    items.extend(item for item in _close_attention(view["closes"]) if item["reason"] != "close_leftovers")
    return items


def status_list(ws: Workspace) -> dict:
    """Every session of this workspace across the repository, one entry each, then its closed audits.

    Sessions owned by another maintainer checkout are viewed through it. A
    registered session whose directory is missing is listed as records that
    do not verify. A closed audit ID without a live session is listed from its
    closing records. The exit code is the highest of any entry's.
    """
    from stewart._repository import _role_records, maintainer, session_location, workspace_sessions
    from stewart.workspace import Workspace as _Workspace
    common = maintainer(ws.repo)["common_dir"]
    entries = []
    for ident in workspace_sessions(common, ws):
        session = session_location(common, ws, ident)
        entry: dict = {"audit_id": ident, "session": str(session)}
        try:
            owner = read_receipt(session / "session.json", what="session record").get("repo") or str(ws.repo)
            entry["owner"] = owner
            view = status(ws if owner == str(ws.repo) else _Workspace(Path(owner), ws.rel), ident)
            if view["schema"] == CLOSED_VIEW_SCHEMA:
                # A close is under way: the session directory remains until it finishes.
                entries.append({**entry, **_closed_entry(ident, view)})
                continue
            complete = [c for c in view["collections"] if c["complete"]]
            worktree = view["identities"].get("worktree") or {}
            entry.update(preparation=view["preparation"]["state"], checkout=worktree.get("path"),
                         lock=worktree.get("lock"), collections=len(complete), exit_code=view["exit_code"],
                         attention=view["attention"])
        except StewartError as exc:
            entry.update(problem=exc.to_json(), exit_code=EXIT_UNVERIFIED)
        entries.append(entry)
    from stewart._repository import CLOSED, SESSIONS
    live = {entry["audit_id"] for entry in entries}
    closed_root = Path(common) / CLOSED / ws.slug
    for directory in sorted(closed_root.iterdir()) if closed_root.is_dir() and not closed_root.is_symlink() else []:
        if directory.name in live:
            continue
        located = {"session": str(session_location(common, ws, directory.name))}
        try:
            view = status(ws, directory.name)
        except StewartError as exc:
            entries.append({"audit_id": directory.name, "closed": True, "problem": exc.to_json(),
                            "exit_code": EXIT_UNVERIFIED, **located})
            continue
        entries.append({**_closed_entry(directory.name, view), **located})
    listed = {entry["session"] for entry in entries if "session" in entry}
    prefix = str(Path(common) / SESSIONS / ws.slug) + "/"
    for row in _role_records(common):
        if row["session"].startswith(prefix) and row["session"] not in listed and not Path(row["session"]).exists():
            entries.append({"audit_id": Path(row["session"]).name, "session": row["session"], "owner": None,
                            "problem": {"reason": "session_records_missing",
                                        "message": "a registered session's directory is missing"},
                            "exit_code": EXIT_UNVERIFIED})
    return {"schema": LIST_SCHEMA, "workspace": ws.to_json(), "sessions": entries,
            "manager_storage": _manager_storage(common, None),
            "exit_code": combined_code(entry["exit_code"] for entry in entries)}


def _closed_entry(ident: str, view: dict) -> dict:
    """A listing entry from a closed view; a finished close is history and counts only while unfinished or unverifiable."""
    counts = view["audit_id_state"] in ("close_incomplete", "unverified")
    return {"audit_id": ident, "closed": True, "audit_id_state": view["audit_id_state"],
            "closes": [{key: item.get(key) for key in ("session_uuid", "mode", "actor", "closed_at", "complete",
                                                       "released")} for item in view["closes"]],
            "exit_code": view["exit_code"] if counts else EXIT_OK, "attention": view["attention"]}


def _derive_actions(ws: Workspace, ident: str, view: dict, record: dict | None, profile_path: str | None) -> None:
    outstanding = view["outstanding"]
    actions = view["next_actions"]
    if record is None:
        outstanding.append("the session record cannot be interpreted; no action can be derived from it")
        return
    if view["identities"]["retention"]["status"] not in ("verified", "not_created"):
        outstanding.append("session commit retention is invalid; restore the recorded refs before recovery actions; "
                           "collection can still preserve raw bytes and record the retention failure")
        return
    complete = [c for c in view["collections"] if c["complete"]]
    exits = view["harness_exits"]
    if exits and exits[-1]["exit"] != 0 and not complete:
        # The block's own observation of the harness process, which is more than
        # Stewart otherwise has: a nonzero exit with no collection means the
        # auditor may never have started.
        outstanding.append(f"the launch command's harness exited {exits[-1]['exit']} at {exits[-1]['at']} and no "
                           "collection exists; the auditor may never have started. Run the profile's probe, fix "
                           "the profile or the harness, and launch again (status --profile PATH renders from a "
                           "working-tree profile)")
    for c in view["collections"]:
        if not c["complete"]:
            if any(problem["reason"] == "collection_incomplete" for problem in c["problems"]):
                outstanding.append(f"collection {c['name']} is a partial attempt; collect again and triage a complete one")
            else:
                outstanding.append(f"collection {c['name']} has an invalid or unreadable receipt; "
                                   "preserve it and inspect its problems before collecting again")
    identities = view["identities"]
    preparation = view["preparation"]["state"]
    if preparation == "runtime_unavailable":
        outstanding.append("the current supplied runtime is unavailable or changed; preserve it and recover assets for a fresh assignment")
    if preparation in {"failed", "incomplete"}:
        outstanding.append("preparation did not complete; close --abandon retires this session and reports whether "
                           "the audit ID is released for another prepare; otherwise prepare a fresh assignment")
        if not identities["worktree"]["exists"]:
            outstanding.append("no worktree exists for this incomplete preparation; no completed checkout is inferred")
        meta = record["assignment"]
        args = ["init", "--audit-id", "<fresh-audit-id>", "--target-commit", meta["target_commit"]]
        if meta.get("base_commit") is not None:
            args += ["--base-commit", meta["base_commit"]]
        for rel in meta.get("input_files", []):
            args += ["--input", rel]
        packages = set()
        for item in meta.get("supplemental_inputs", []):
            if "custody" in item:
                packages.add(item["custody"]["package"])
            else:
                args += ["--supplemental", item["path"], item["provenance"]]
        for package in sorted(packages):
            args += ["--evidence-package", package]
        for item in meta.get("external_sources", []):
            args += ["--source", item["url"], item["purpose"]]
        actions.append({
            "action": "close",
            "prerequisites": [
                "inspect the retained preparation error or partial state first; close removes them",
                "the ID is released only when preparation recorded its failure before writing either handoff, "
                "nothing was launched, recorded or collected, and the checkout holds only preparation's footprint",
            ],
            **command(ws, "close", "--audit-id", ident, "--actor", "<name>", "--abandon", "--reason", "<reason>"),
        })
        actions.append({
            "action": "fresh_assignment",
            "retained": [view["session"]["path"], *([view["preparation"]["failure_path"]]
                         if view["preparation"].get("failure_path") else [])],
            "prerequisites": [
                "only when close leaves this audit ID reserved; a released ID is prepared again instead",
                "inspect the retained preparation error or partial state and correct its cause",
                "choose a new audit ID; this command prints a draft and never repairs the failed session",
                "re-author scope, scratch paths and any experiment grant; commit the replacement prompt alone before prepare",
                "coordinate any existing writer hold explicitly; a new assignment does not release it",
            ],
            **command(ws, *args),
        })
    if identities["worktree"]["head_matches_prompt"] is False:
        outstanding.append("worktree HEAD differs from the prompt commit; a collection records the unexpected commit")
    if (record or {}).get("submodules"):
        outstanding.append("the prompt commit holds submodules, which Stewart does not populate or audit: "
                           + ", ".join(item["path"] for item in record["submodules"]["gitlinks"][:10]))
    if identities["worktree"]["exists"] and identities["worktree"]["head"] is None:
        why = (identities["worktree"].get("lock") or {}).get("error") or "Git cannot read it"
        outstanding.append(f"the worktree's HEAD is not observed ({why}); no handoff is offered until it is")
    if not identities["worktree"]["exists"] and preparation not in {"failed", "incomplete"}:
        outstanding.append("the worktree is gone; only existing collections remain as evidence")
    good_launches = [item for item in view["launches"] if not item["problems"]]
    if not complete:
        outstanding.append("no complete collection exists")
        if (not view["collections"] and preparation == "ready"
                and identities["worktree"]["head_matches_prompt"]):
            # No collection does not mean no launch. This is a conditional
            # manual handoff, never an instruction to start a second auditor.
            # The prompt is absolute so a harness that cannot set its working
            # directory (a sub-agent inherits the manager's) still opens the
            # right handoff and worktree.
            handoff = {
                "action": "handoff",
                "external": "use a fresh auditor thread in the supplied worktree; Stewart launches nothing",
                "prerequisites": ["the manager has not already handed off this assignment; auditor activity is unobserved"],
                "cwd": identities["worktree"]["path"],
                "launch": view["preparation"]["launch_path"],
                "prompt": handoff_prompt(view["preparation"]["launch_path"], identities["worktree"]["path"]),
                "auditor_scope": record["auditor_scope"],
            }
            pinned = record.get("launch_profile")
            chosen = load_profile(ws, profile_path) if profile_path is not None else pinned
            if isinstance(chosen, dict):
                # The pinned profile, not the working-tree file, unless an
                # override was named: what this session printed at preparation
                # is what it prints now.
                session_path = Path(view["session"]["path"])
                handoff["command"] = render_command(chosen["profile"], worktree=identities["worktree"]["path"],
                                                    launch_path=view["preparation"]["launch_path"],
                                                    exit_log=session_path / EXIT_LOG, scope=record["auditor_scope"])
                handoff["probe"] = render_probe(chosen["profile"], worktree=identities["worktree"]["path"],
                                                launch_path=view["preparation"]["launch_path"], scope=record["auditor_scope"])
                handoff["exit_log"] = str(session_path / EXIT_LOG)
                handoff["profile_source"] = "override" if profile_path is not None else "pinned"
            else:
                handoff["prerequisites"].append(
                    "configure the harness for the recorded auditor scope: exact runtime read-only, worktree access, "
                    "private receipts and manager storage denied; prose alone does not enforce access")
            actions.append(handoff)
        if preparation == "ready" and not good_launches:
            if isinstance(record.get("launch_profile"), dict) or profile_path is not None:
                extra = ["--profile", profile_path] if profile_path is not None else []
                actions.append({
                    "action": "launch",
                    "external": "record this after the handoff is made; it is the manager's acknowledgment, not an observation",
                    "prerequisites": ["the launch profile supplies style, model, effort and actor"],
                    **command(ws, "launch", "--audit-id", ident, "--from-profile", *extra),
                })
            else:
                actions.append({
                    "action": "launch",
                    "external": "record this after the handoff is made; it is the manager's acknowledgment, not an observation",
                    "prerequisites": ["name the style, model and effort you requested of the harness; "
                                      "a note can carry the harness, first prompt and isolation caveats"],
                    **command(ws, "launch", "--audit-id", ident, "--style", "<terminal|subagent|other>",
                              "--model", "<model>", "--effort", "<effort>", "--actor", "<name>"),
                })
        if identities["worktree"]["exists"]:
            actions.append({
                "action": "collect",
                "external": "stop the auditor first; the tool cannot stop it and will not infer that it stopped",
                "prerequisites": ["the auditor has stopped writing"],
                **command(ws, "collect", "--audit-id", ident, "--auditor-stopped", "<finished|interrupted|blocked>"),
            })
    if complete and not good_launches:
        outstanding.append("no launch record: how, with which model and at what effort the auditor was "
                           "launched is unrecorded; `launch` records the manager's acknowledgment")
    triaged = {d.get("collection") for d in view["dispositions"] if not d["problems"]}
    for c in complete:
        if c["name"] in triaged:
            continue
        gaps = c.get("gaps", [])
        actions.append({
            "action": "triage-draft",
            "prerequisites": ["inspect this collection's captured report and diagnostics; the draft leaves judgments unanswered"],
            **command(ws, "triage-draft", "--audit-id", ident, "--collection", c["name"]),
        })
        actions.append({
            "action": "triage",
            "prerequisites": [
                "fill this collection's triage-draft response with accepted/rejected/unresolved claims and a decision",
                "answer any follow_up with accept, decline, or defer and a reason; this grants no new scope",
                "preserve collection and collection_sha256 from triage-draft for this capture",
                "state report_sha256 of the captured report" if c.get("report_status") == "present"
                else "state report_gap because no report was captured",
                *( [f"disposition custody gaps: {', '.join(gaps)}"] if gaps else [] ),
            ],
            **command(ws, "triage", "--audit-id", ident, "--collection", c["name"],
                      "--response", "<response.json>", "--actor", "<name>"),
        })
    retained_reports = {
        p["source"] for r in view["retentions"] if not r["problems"] for p in (r.get("published") or [])
    }
    for d in view["dispositions"]:
        if d["problems"]:
            continue
        if d.get("report_sha256") and "REPORT.md" not in retained_reports:
            if identities.get("report_destination_exists"):
                outstanding.append(
                    "the report destination already exists in the maintainer checkout; report retention would be refused"
                )
            else:
                actions.append({
                    "action": "retain",
                    "prerequisites": ["the triage's report digest is the bytes you reviewed"],
                    **command(ws, "retain", "--audit-id", ident, "--triage", d["name"], "--report"),
                })
    coordination = view["coordination"]
    if coordination.get("mode") == "paused" and coordination.get("resumed") is None:
        good = [d for d in view["dispositions"] if not d["problems"]]
        if good:
            actions.append({
                "action": "resume",
                "external": "tell the writers; the tool controls no process",
                "prerequisites": ["a triage or cancellation decision is recorded"],
                **command(ws, "resume", "--audit-id", ident, "--triage", good[-1]["name"], "--reason", "<reason>"),
            })
        else:
            outstanding.append("paused hold remains until a triage or cancellation is recorded and resume is run")
    for attempt in view["attempts"]:
        if any(problem["reason"] == "attempt_unresolved" for problem in attempt["problems"]):
            outstanding.append(f"attempt {attempt['name']} is reserved but unresolved; it is not reusable")
        elif any(problem["record"] == "ATTEMPT.json" for problem in attempt["problems"]):
            outstanding.append(f"attempt {attempt['name']} has an invalid or unreadable receipt; "
                               "preserve it and inspect its problems; the reservation is not reusable")
    for release in view["releases"]:
        if release["problems"]:
            continue
        if release.get("uncaptured_artifacts"):
            outstanding.append(f"release {release['name']} has artifacts without verified captures: "
                               + ", ".join(release["uncaptured_artifacts"])
                               + "; no matching captured bytes could be verified during this status read; "
                               "preserve any remaining copies and inspect the collection evidence")
        if not release.get("consumed"):
            actions.append({
                "action": "run",
                "prerequisites": ["the frozen artifacts still match their recorded digests"],
                **command(ws, "run", "--audit-id", ident, "--release", release["name"]),
            })
    if view["experiment"]["state"] == "awaiting_review":
        outstanding.append("execution is granted but no release review is recorded; artifact readiness is unassessed")
        if not complete:
            outstanding.append("no collection has captured the constructed artifacts; release is not offered "
                               "until the constructor has stopped and a collection exists")
        elif preparation == "ready" and identities["worktree"]["head_matches_prompt"]:
            actions.append({
                "action": "release",
                "prerequisites": ["the constructor has stopped writing and the exact candidate artifacts are ready",
                                  "independently assess the reference, controls, measurement IDs and permitted effects",
                                  "author review JSON; release validates byte identities but not scientific merit"],
                **command(ws, "release", "--audit-id", ident, "--review", "<review.json>", "--actor", "<name>"),
            })
    hold_outstanding = coordination.get("mode") == "paused" and coordination.get("resumed") is None
    unresolved = any(problem["reason"] == "attempt_unresolved" for attempt in view["attempts"]
                     for problem in attempt["problems"])
    # Offered only where a concluded close would succeed and nothing else is
    # pending: closing before a retention, release or run would remove the
    # captured bytes they need. The latest complete collection is triaged and
    # the checkout is still exactly what it captured.
    latest = complete[-1] if complete else None
    if (not actions and preparation not in {"failed", "incomplete"} and not hold_outstanding and not unresolved
            and view["experiment"].get("state") not in ("awaiting_review", "released")
            and latest is not None and latest["name"] in triaged
            and _unchanged_since(Path(identities["worktree"]["path"]), latest)
            and _verified_capture(ws, latest, outstanding)):
        actions.append({
            "action": "close",
            "prerequisites": [
                "the auditor has stopped; a checkout changed since the triaged collection is refused",
                "retain reviewed bytes and export anything else worth keeping first; close removes the session, "
                "its checkout, refs and registry row and keeps only the closing record",
                "the audit ID stays reserved",
            ],
            **command(ws, "close", "--audit-id", ident, "--actor", "<name>", "--collection", latest["name"]),
        })
