"""Collect evidence from a stopped auditor's checkout without disturbing it.

Order is part of the claim. The report is captured first, before any Git work
that may fail. A no-follow filesystem inventory is taken before Git discovery
and again after archiving, so movement during collection is detected and so an
entry Git does not report (an untracked FIFO, an unreadable file) still appears
in the record. Nothing is deleted or reset; a failure leaves partial evidence
and the worktree in place.

Coverage claims are scoped to recorded file bytes and metadata below the
worktree root, excluding its Git administration. Extended attributes, other
mounts, shared caches, host services and transient effects are outside them.
"""

from __future__ import annotations

from collections import Counter
import errno
import os
from pathlib import Path
import stat
import subprocess
import tarfile

from stewart import _util as _hash
from stewart._git import git, git_text
from stewart import _bootstrap as _files
from stewart._bootstrap import StewartError
from stewart.runtime import observe_phase, runtime_state
from stewart.session import (
    COLLECTION_SCHEMA,
    load_session,
    maintainer_state,
    now,
    stamp,
    tool_identity,
    write_receipt,
)
from stewart.workspace import Workspace, contained


def inventory(root: Path) -> dict:
    """No-follow inventory of everything below ``root`` except its top-level Git administration.

    Entries are classified relative to pinned directory descriptors. Regular
    files are digested through a verified descriptor; symlinks record their
    target text without being followed; special entries are never read; an
    unreadable entry or directory is recorded as such. A nested ``.git``
    directory is a traversal boundary and is listed, not silently skipped.
    """
    entries: list[dict] = []
    exclusions: list[dict] = []
    boundaries: list[dict] = []

    def visit(directory: int, prefix: str) -> None:
        try:
            names = sorted(os.listdir(directory))
        except OSError as exc:
            entries.append({"path": prefix or ".", "kind": "unreadable", "detail": f"{exc.strerror} (listdir)"})
            return
        for name in names:
            rel = f"{prefix}/{name}" if prefix else name
            if rel == ".git":
                exclusions.append({"path": rel, "reason": "git administration is outside coverage"})
                continue
            try:
                st = os.stat(name, dir_fd=directory, follow_symlinks=False)
            except OSError as exc:
                entries.append({"path": rel, "kind": "unreadable", "detail": f"{exc.strerror} (lstat)"})
                continue
            kind = _files.entry_kind(st.st_mode)
            if kind == "directory":
                if name == ".git":
                    boundaries.append({"path": rel, "reason": "nested git administration was not traversed"})
                    entries.append({"path": rel, "kind": "directory", "traversed": False})
                    continue
                entry = {"path": rel, "kind": "directory", "traversed": False}
                entries.append(entry)
                try:
                    with _files.open_directory(Path(name), dir_fd=directory) as child:
                        opened = os.fstat(child)
                        if (st.st_dev, st.st_ino) != (opened.st_dev, opened.st_ino):
                            entry.update(kind="replaced", detail="directory identity changed before traversal")
                            continue
                        entry["traversed"] = True
                        visit(child, rel)
                        after = os.stat(name, dir_fd=directory, follow_symlinks=False)
                        if (after.st_dev, after.st_ino, after.st_mode) != (st.st_dev, st.st_ino, st.st_mode):
                            entry.update(kind="replaced", detail="directory changed during traversal")
                except OSError as exc:
                    entry.update(kind="replaced" if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.EMLINK) else "unreadable",
                                 detail=f"{exc.strerror} (directory open/traversal)")
            elif kind == "symlink":
                try:
                    entries.append({"path": rel, "kind": "symlink", "target": os.readlink(name, dir_fd=directory)})
                except OSError as exc:
                    entries.append({"path": rel, "kind": "unreadable", "detail": f"{exc.strerror} (readlink)"})
            elif kind == "file":
                entries.append({"path": rel, **_files.capture_regular(Path(name), dir_fd=directory)})
            else:
                entries.append({"path": rel, "kind": kind, "mode": stat.S_IMODE(st.st_mode)})

    try:
        with _files.open_directory(root) as directory:
            visit(directory, "")
    except OSError as exc:
        entries.append({"path": ".", "kind": "unreadable", "detail": f"{exc.strerror} (root open)"})
    counts = Counter(entry["kind"] for entry in entries)
    return {
        "root": str(root),
        "exclusions": exclusions,
        "boundaries": boundaries,
        "counts": dict(sorted(counts.items())),
        "entries": entries,
    }


def checkout_state(worktree: Path, prompt_commit: str) -> tuple[dict, dict[str, bytes]]:
    """Capture index and worktree separately, including ignored and untracked bytes.

    Diffs use the assigned commit, not HEAD: an unexpected auditor commit must
    not make its changes disappear. NUL delimiters preserve unusual filenames.
    Entries Git reports that are not regular files or links are recorded, not
    refused; the inventory and the receipt make them visible.
    """
    diff = ("--no-ext-diff", "--no-textconv", "--no-renames", "--binary", "--full-index")
    raw = {
        "working.patch": git(worktree, "diff", *diff, prompt_commit).stdout,
        "index.patch": git(worktree, "diff", "--cached", *diff, prompt_commit).stdout,
        "status.z": git(worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout,
    }
    names: set[str] = set()
    for args in (
        ("diff", "--name-only", "--no-renames", "-z", prompt_commit),
        ("diff", "--cached", "--name-only", "--no-renames", "-z", prompt_commit),
        # Intentionally omit --exclude-standard: ignored files are recovery data.
        ("ls-files", "--others", "-z"),
    ):
        names.update(os.fsdecode(git(worktree, *args).stdout).split("\0"))
    names.discard("")
    files = []
    for rel in sorted(names):
        try:
            candidate = contained(worktree, rel, leaf_link=True)
        except StewartError as exc:
            files.append({"path": rel, "kind": "unsupported", "detail": str(exc)})
            continue
        try:
            mode = candidate.lstat().st_mode
        except FileNotFoundError:
            files.append({"path": rel, "kind": "missing"})
            continue
        except OSError as exc:
            files.append({"path": rel, "kind": "unreadable", "detail": f"{exc.strerror} (lstat)"})
            continue
        if stat.S_ISLNK(mode):
            files.append({"path": rel, "kind": "symlink", "target": os.readlink(candidate)})
        elif stat.S_ISREG(mode):
            files.append({"path": rel, **_files.capture_regular(candidate)})
        else:
            files.append({"path": rel, "kind": _files.entry_kind(mode), "mode": stat.S_IMODE(mode)})
    state = {
        "head": git_text(worktree, "rev-parse", "HEAD"),
        "branch": git_text(worktree, "branch", "--show-current"),
        "files": files,
        "receipts": {name: _hash.sha256_bytes(data) for name, data in raw.items()},
    }
    return state, raw


def archive_files(archive: Path, worktree: Path, files: list[dict]) -> tuple[list[str], list[dict]]:
    """Archive Git-reported regular files and links; report what could not be archived.

    Regular files are added through the same verified descriptor discipline as
    the inventory, so the archive never follows a link planted after discovery
    and never reads a special entry. Deletions are carried by the patches.
    """
    archived: list[str] = []
    omitted: list[dict] = []
    with tarfile.open(archive, "x", dereference=False) as bundle:
        for item in files:
            rel = item["path"]
            if item["kind"] == "symlink":
                info = tarfile.TarInfo(rel)
                info.type = tarfile.SYMTYPE
                info.linkname = item["target"]
                bundle.addfile(info)
                archived.append(rel)
            elif item["kind"] == "file":
                try:
                    fd, st = _files._open_regular(contained(worktree, rel, leaf_link=True))
                except _files._Unavailable as unavailable:
                    omitted.append({"path": rel, "kind": unavailable.kind, "detail": unavailable.detail})
                    continue
                info = tarfile.TarInfo(rel)
                info.type = tarfile.REGTYPE
                info.size = st.st_size
                info.mode = stat.S_IMODE(st.st_mode)
                info.mtime = int(st.st_mtime)
                with os.fdopen(fd, "rb") as fh:
                    bundle.addfile(info, fh)
                archived.append(rel)
            elif item["kind"] == "missing":
                continue
            else:
                omitted.append({
                    "path": rel, "kind": item["kind"],
                    "detail": item.get("detail", "special entries are inventoried, not archived"),
                })
    return archived, omitted


def verify_archive(archive: Path, files: list[dict], archived: list[str]) -> None:
    """Check what was archived, not only whether the source stayed still."""
    with tarfile.open(archive, "r") as bundle:
        for item in files:
            if item["path"] not in archived:
                continue
            if item["kind"] == "file":
                member = bundle.extractfile(item["path"])
                if member is None or _files.verified_stream_digest(member) != item["sha256"]:
                    raise StewartError(
                        f"archive bytes differ from captured file: {item['path']}", reason="archive_mismatch",
                    )
            elif item["kind"] == "symlink" and bundle.getmember(item["path"]).linkname != item["target"]:
                raise StewartError(
                    f"archived link differs from captured link: {item['path']}", reason="archive_mismatch",
                )


def _inventory_summary(record: dict, archived: list[str], omitted: list[dict], movement: bool,
                       digest: str | None) -> dict:
    entries = record["entries"]
    return {
        "root": record["root"],
        "record": "inventory.json",
        "sha256": digest,
        "exclusions": record["exclusions"],
        "boundaries": record["boundaries"],
        "counts": record["counts"],
        "archived": archived,
        "omitted": omitted,
        "unreadable": [entry["path"] for entry in entries if entry["kind"] == "unreadable"],
        "unsupported": [
            {"path": entry["path"], "kind": entry["kind"]} for entry in entries if entry["kind"] in _files.SPECIAL_KINDS
        ],
        "movement": movement,
    }


def collect(ws: Workspace, ident: str, *, auditor_stopped: str) -> dict:
    """Preserve a fresh capture; acknowledge finished, interrupted, or blocked.

    The stop kind is the maintainer's claim, not an observed process exit. Raw
    report capture precedes declaration validation; invalid declarations become
    custody gaps and never prevent preservation.
    """
    if auditor_stopped not in ("finished", "interrupted", "blocked"):
        raise StewartError(
            "stop the auditor, then pass --auditor-stopped finished|interrupted|blocked before collection",
            reason="auditor_not_stopped",
            next_steps=["stopping the auditor is external to this tool; acknowledge it only after it happened"],
        )
    # A broken retention ref must not erase a still-readable raw report. Record
    # that failure after preservation; subsequent recovery actions remain gated.
    session, record = load_session(ws, ident, check_retention=False)
    worktree = contained(session, "worktree")
    name = stamp()
    collection = session / "collections" / name
    collection.mkdir(parents=True, mode=0o700)
    receipt: dict = {
        "schema_version": COLLECTION_SCHEMA,
        "name": name,
        "collected_at": now().isoformat(),
        "audit_id": ident,
        "workspace": ws.rel,
        "auditor_stopped": True,
        "auditor_stop_kind": auditor_stopped,
        "auditor_stopped_acknowledged_by": "maintainer via --auditor-stopped",
        "prompt_commit": record["prompt_commit"],
        "mode": record["mode"],
        "errors": [],
        "report_status": "unassessed",
        "git_discovery": "unassessed",
        "worktree_retained": True,
        "inventory": None,
        "runtime": runtime_state(record['runtime']),
        "runtime_assets": record['runtime_assets'],
        "stewart": tool_identity(),
    }
    write_receipt(collection / "STARTED.json", receipt)
    meta = record["assignment"]
    # Preserve a usable report even if later Git inspection or archiving fails.
    # An unassessed report is different from one actually observed to be absent.
    try:
        report = contained(worktree, meta["report_path"], leaf_link=True)
        if report.is_symlink():
            receipt["report_status"] = "symlink"
        elif not report.exists():
            receipt["report_status"] = "missing"
        else:
            info, data = _files.read_regular(report)
            if data is None:
                receipt["report_status"] = "unsupported"
                receipt["report_detail"] = info
            else:
                (collection / "REPORT.md").write_bytes(data)
                receipt["report_status"] = "present" if data.strip() else "empty"
                receipt["report_sha256"] = info["sha256"]
    except (StewartError, OSError) as exc:
        receipt["errors"].append(f"report capture: {exc}")
    before_inventory = inventory(worktree)
    write_receipt(collection / "inventory.json", before_inventory)
    # An untracked supplied handoff can disappear without a Git diff. Compare
    # the preserved complete inventory to its prepared pin, keeping absence
    # and unreadability as gaps after raw report preservation.
    handoff = record["handoff"]
    observed_handoff = next((item for item in before_inventory["entries"] if item["path"] == handoff["path"]), None)
    if (observed_handoff is None or observed_handoff["kind"] != "file"
            or observed_handoff.get("sha256") != handoff["sha256"]):
        receipt["errors"].append("supplied public handoff is absent, unreadable or differs from preparation")
    inventory_digest = _hash.sha256_bytes(_hash.receipt_json_bytes(before_inventory))
    archived: list[str] = []
    omitted: list[dict] = []
    movement = False
    # Exposed helpers cannot suppress this independent manager observation or
    # the raw report already preserved above it.
    try:
        observe_phase(receipt['runtime'], collection, 'collection')
        from stewart.captured import runtime_observations
        captures = runtime_observations(collection, receipt['runtime'], phases={'collection'})
        if not captures['collection']['matches_expected']:
            receipt['errors'].append('supplied runtime membership or bytes differ from preparation')
    except (StewartError, OSError) as exc:
        receipt['errors'].append(f'runtime observation: {exc}')
    from stewart._repository import verify_retention
    try:
        receipt["retention"] = {"status": "verified", "pins": verify_retention(ws.repo, record)}
    except StewartError as exc:
        receipt["retention"] = {"status": "invalid", "error": exc.to_json()}
        receipt["errors"].append(f"commit retention: {exc}")
    try:
        common = git_text(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if common != record["common_dir"] or git_text(worktree, "rev-parse", "--show-toplevel") != str(worktree):
            raise StewartError(
                "audit checkout identity changed; refuse to collect another repository",
                reason="checkout_identity",
            )
        state, raw = checkout_state(worktree, record["prompt_commit"])
        receipt["checkout"] = state
        for raw_name, data in raw.items():
            (collection / raw_name).write_bytes(data)
        archive = collection / "files.tar"
        archived, omitted = archive_files(archive, worktree, state["files"])
        verify_archive(archive, state["files"], archived)
        after, _ = checkout_state(worktree, record["prompt_commit"])
        after_inventory = inventory(worktree)
        movement = after != state or after_inventory["entries"] != before_inventory["entries"]
        receipt["git_discovery"] = "complete"
        if movement:
            write_receipt(collection / "inventory-after.json", after_inventory)
            raise StewartError(
                "checkout changed during collection; partial archive retained, collect again after stopping writers",
                reason="movement",
            )
        archive_info = _files.capture_regular(archive)
        if archive_info["kind"] != "file":
            raise StewartError(f"collection archive is unreadable: {archive_info}", reason="archive_unreadable")
        receipt["archive_sha256"] = archive_info["sha256"]
        report_entry = next((item for item in state["files"] if item["path"] == meta["report_path"]), None)
        if report_entry and report_entry["kind"] == "file":
            if receipt.get("report_sha256") != report_entry["sha256"]:
                raise StewartError(
                    "report changed before archive capture; both versions retained, collect again",
                    reason="movement",
                )
        supplied = {item["path"]: item["sha256"] for item in meta["supplemental_inputs"]}
        supplied[record["handoff"]["path"]] = record["handoff"]["sha256"]
        receipt["unexpected_paths"] = [
            item["path"] for item in state["files"]
            if item["path"] != meta["report_path"]
            and not any(item["path"] == p or item["path"].startswith(p + "/") for p in meta["scratch_paths"])
            and not (item["kind"] == "file" and supplied.get(item["path"]) == item.get("sha256"))
        ]
        receipt["checkout_commit_changed"] = state["head"] != record["prompt_commit"]
        # The maintainer can advance during a snapshot audit. This signal is informational;
        # it neither invalidates pinned inputs nor certifies a pause was honored.
        receipt["maintainer_status_changed_since_prepare"] = maintainer_state(ws.repo) != record["maintainer_before"]
    except (StewartError, OSError, ValueError, tarfile.TarError, subprocess.TimeoutExpired) as exc:
        receipt["errors"].append(str(exc))
        if receipt["git_discovery"] == "unassessed":
            receipt["git_discovery"] = "failed"
    # Parse only the preserved bytes, after capture and Git observation. Even an
    # unexpected validator failure is evidence, never a reason to lose a report.
    try:
        from stewart.report_declaration import session_declaration_expectations, validate_report_declaration

        expected, sources = session_declaration_expectations(record, receipt.get("checkout", {}).get("head"))
        if "report_sha256" in receipt:
            info, captured = _files.read_regular(collection / "REPORT.md")
            if captured is None or info.get("sha256") != receipt["report_sha256"]:
                raise StewartError("captured report changed before declaration validation", reason="evidence_tampered")
        else:
            captured = b""
        receipt["declaration"] = validate_report_declaration(captured, expected=expected, sources=sources)
        receipt["declaration"]["source"] = "REPORT.md" if "report_sha256" in receipt else None
    except Exception as exc:
        receipt["declaration"] = {"status": "invalid", "declaration": None, "comparisons": {},
                                  "diagnostics": [{"reason": getattr(exc, "reason", "validation_error"),
                                                   "message": str(exc)}]}
        receipt["errors"].append(f"declaration validation: {exc}")
    receipt["inventory"] = _inventory_summary(before_inventory, archived, omitted, movement, inventory_digest)
    write_receipt(collection / "collection.json", receipt)
    return {
        "audit_id": ident,
        "collection": name,
        "path": str(collection),
        "receipt": receipt,
        "gaps": custody_gaps(receipt),
    }


def custody_gaps(receipt: dict) -> list[dict]:
    """Every custody fact in a collection that a triage must disposition explicitly.

    The list is derived from the receipt, so a response that addresses each ID is
    bound to this collection's actual coverage rather than to a generic checklist.
    Validating that each gap has a disposition does not validate the reasoning.
    """
    gaps: list[dict] = []
    for index, error in enumerate(receipt.get("errors", [])):
        gaps.append({"id": f"collection_error:{index}", "description": error})
    status = receipt.get("report_status")
    if status != "present":
        gaps.append({"id": f"report_{status}", "description": f"no nonempty regular report was captured (status {status})"})
    if receipt.get("git_discovery") != "complete":
        gaps.append({"id": "git_discovery_incomplete", "description": "Git discovery did not complete; archive coverage is unknown"})
    if receipt.get("checkout_commit_changed"):
        gaps.append({"id": "checkout_commit_changed", "description": "the worktree HEAD is not the prompt commit (unexpected commit)"})
    for rel in receipt.get("unexpected_paths", []):
        gaps.append({"id": f"unexpected_path:{rel}", "description": "a changed, untracked or ignored path outside the assigned outputs"})
    declaration = receipt.get("declaration") or {"status": "missing"}
    if declaration["status"] == "missing":
        gaps.append({"id": "declaration_missing", "description": "captured report has no declaration; no completion inferred"})
    elif declaration["status"] == "invalid":
        for diagnostic in declaration["diagnostics"]:
            gaps.append({"id": f"declaration_invalid:{diagnostic['reason']}", "description": diagnostic["message"]})
    elif declaration["status"] == "mismatch":
        for diagnostic in declaration["diagnostics"]:
            field = diagnostic["field"]
            gap_id = "declaration_stale" if field == "observed_checkout_commit" else f"declaration_mismatch:{field}"
            gaps.append({"id": gap_id, "description": diagnostic["message"] +
                         " Identity comparison only; mutation chronology is not established."})
    claim = declaration.get("declaration") or {}
    if claim.get("completion") == "complete" and receipt.get("auditor_stop_kind") == "interrupted":
        gaps.append({"id": "completion_stop_discrepancy", "description":
                     "auditor declared complete; maintainer acknowledged interrupted. Explain the discrepancy; "
                     "completion followed by interruption can make both claims true."})
    summary = receipt.get("inventory") or {}
    if summary.get("movement"):
        gaps.append({"id": "movement_detected", "description": "the checkout changed during collection"})
    for item in summary.get("omitted", []):
        gaps.append({"id": f"omitted:{item['path']}", "description": f"Git-reported entry not archived ({item['kind']}): {item.get('detail', '')}"})
    for rel in summary.get("unreadable", []):
        gaps.append({"id": f"unreadable:{rel}", "description": "inventory entry could not be read"})
    for item in summary.get("unsupported", []):
        gaps.append({"id": f"unsupported:{item['path']}", "description": f"inventory entry of kind {item['kind']} was recorded, not captured"})
    for item in summary.get("boundaries", []):
        gaps.append({"id": f"boundary:{item['path']}", "description": item["reason"]})
    return gaps
