"""Characterize custodial-core facts about the frozen baseline; observations, not a contract.

1. Paths that collide at preparation. A target tree holding two names that
   differ only by case, or only by Unicode normalization, is prepared,
   collected (stop acknowledged, no auditor changes) and planned for close.
   The host volume's case and normalization behavior is probed and recorded
   beside the outcome. Controls hold no collision; the invariance case puts
   the same two names in different directories; ``unicode-nfd-alone``
   separates the effect of a decomposed name from the effect of a collision.
   ``case-collision-assigned-input`` makes one colliding name an assigned
   input, the one place preparation compares checked-out bytes.
2. Mirror operations and Stewart's refs. After ``prepare``, ``git clone
   --mirror`` and ``git push --mirror`` (local paths only) are inspected for
   ``refs/stewart/sessions/<uuid>/*`` and for the private session storage under
   the Git common directory. A hand-made ``refs/probe/x`` is the firing
   control; an ordinary clone is the invariance case.
3. Writes relative to collection. One write to a tracked checkout file is
   injected in-process, deterministically, by wrapping a collection internal
   as ``tests/test_verified_capture.py`` and ``tests/test_stewart.py`` do:
   after the before-inventory but before Git discovery, or after the archive
   and before the after-inventory. The same wrapper writing outside the
   checkout is the invariance case, no write the control, and a write after
   collection and triage (before close) the last case. The wrappers are
   installed in every case, so the control also shows they change nothing.

4. Checkout transformations on a file the auditor never touches. The target
   tree's ``.gitattributes`` imposes ``text eol=crlf`` on LF-committed
   ``other.txt``; a comment-only file is the control, the same attribute on a
   pattern matching no file the invariance case, and ``*.txt`` (which also
   matches the assigned input) an extra case. Each is prepared, collected,
   triaged, planned and then closed for real.
5. Moving the repository with a live session: status, collect and close
   --plan before a rename (control), after it, and after renaming it back;
   and, with a copy of the repository beside the original (invariance), the
   same operations on the original and on the copy.
6. A concluded close over a failed preparation: the replaced-input fixture of
   case-collision-assigned-input is collected, triaged and closed for real,
   concluded and abandoned, beside a successfully prepared collision fixture.

``close --plan`` is observed through ``close_plan``, the function the CLI's
plan calls; comparisons 1-3 perform no close. Every observation is saved into the
node's own directory before the assertions run.

The first executed run (comparisons-01) asserted only the fixture's firing
controls and the controls' clean outcomes. The ``OBSERVED_*`` tables, their
reducers and the assertions on them were then added from that run's saved
observations, unchanged in meaning, and the comparison was rerun. The collision
tables hold only on the volume and Git configuration they record, which are
asserted first. Comparisons 4-6 were added afterwards; their first run
(comparisons-03) asserted only their firing controls, and their ``OBSERVED_*``
tables were added from it in the same way before comparisons-04.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import unicodedata

import pytest

from stewart._bootstrap import StewartError
from stewart._git import git, tree_entries
import stewart.collect as collector
from stewart.close import close, close_plan, require_fresh_audit_id
from stewart.prepare import prepare
from stewart.status import status
from stewart.triage import triage
from stewart.workspace import workspace
import stewart_support as support

pytestmark = pytest.mark.system

NFC = "\u00e9.md"  # LATIN SMALL LETTER E WITH ACUTE, precomposed
NFD = "e\u0301.md"  # e followed by COMBINING ACUTE ACCENT
FIRST = b"first fixture bytes\n"
SECOND = b"second fixture bytes, of a different length\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


LABELS = {_sha(FIRST): "FIRST", _sha(SECOND): "SECOND"}


def _label(digest: str | None) -> str | None:
    return None if digest is None else LABELS.get(digest, "other")


def _save(directory: Path, name: str, value) -> None:
    (directory / f"{name}.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _attempt(function, *args, **kwargs):
    """``(result, None)``, or ``(None, refusal)`` with the refusal's JSON and exit code."""
    try:
        return function(*args, **kwargs), None
    except StewartError as exc:
        return None, {**exc.to_json(), "exit_code": exc.exit_code}


def _refusal(plan: dict | None):
    return None if plan is None else plan["audit"]["refusal"]


def _attention(view: dict | None) -> list | None:
    if view is None:
        return None
    return sorted([item["source"], item["reason"], item["message"], item["code"]] for item in view["attention"])


def _actions(view: dict | None) -> list | None:
    return None if view is None else [action["action"] for action in view["next_actions"]]


def _volume(probe_root: Path) -> dict:
    """How the volume holding the test's directories treats case and Unicode normalization in names."""
    probe = probe_root / "volume-probe"
    probe.mkdir()
    (probe / "CaseProbe.txt").write_bytes(b"case probe\n")
    nfd, nfc = "e\u0301-probe.txt", "\u00e9-probe.txt"
    (probe / nfd).write_bytes(b"normalization probe\n")
    listed = sorted(os.listdir(os.fsencode(probe)))
    return {
        "probe": str(probe),
        "case_insensitive_lookup": (probe / "caseprobe.txt").exists(),
        "case_preserved_in_listing": b"CaseProbe.txt" in listed,
        "normalization_insensitive_lookup": (probe / nfc).exists(),
        "nfd_name_preserved_in_listing": os.fsencode(nfd) in listed,
        "nfc_name_in_listing": os.fsencode(nfc) in listed,
        "listing_hex": [name.hex() for name in listed],
        "device": os.stat(probe).st_dev,
    }


def _name(path: str) -> dict:
    return {"path": path, "utf8_hex": os.fsencode(path).hex(),
            "is_nfc": unicodedata.normalize("NFC", path) == path}


# --- 1. paths that collide at preparation ----------------------------------------------------------

#: Each case: the fixture paths in commit order with their bytes, and the extra assigned inputs.
TREES = {
    "case-control": ([("Notes.md", FIRST), ("Other.md", SECOND)], []),
    "case-collision": ([("Notes.md", FIRST), ("notes.md", SECOND)], []),
    "case-separate-directories": ([("a/Notes.md", FIRST), ("b/notes.md", SECOND)], []),
    "case-collision-assigned-input": ([("Notes.md", FIRST), ("notes.md", SECOND)], ["Notes.md"]),
    "unicode-control": ([(NFC, FIRST), ("Other.md", SECOND)], []),
    "unicode-nfd-alone": ([(NFD, FIRST), ("Other.md", SECOND)], []),
    "unicode-collision": ([(NFC, FIRST), (NFD, SECOND)], []),
    "unicode-separate-directories": ([("a/" + NFC, FIRST), ("b/" + NFD, SECOND)], []),
}
CONTROLS = {"case-control", "unicode-control"}


def _commit_paths(checkout, entries) -> str:
    """Commit ``entries`` through the index alone and return the commit.

    A case- or normalization-insensitive volume cannot hold both names of a
    colliding pair, so every case, controls included, is built the same way:
    blobs from bytes, index entries from standard input with Git's
    precomposition and case folding disabled, then an ordinary commit. The
    maintainer's working tree never holds these paths in any case.
    """
    repo = checkout.repo
    lines = []
    for path, data in entries:
        oid = git(repo, "hash-object", "-w", "--stdin", input=data).stdout.decode("ascii").strip()
        lines.append(b"100644 " + oid.encode("ascii") + b"\t" + os.fsencode(path) + b"\n")
    git(repo, "-c", "core.precomposeunicode=false", "-c", "core.ignorecase=false",
        "update-index", "--add", "--index-info", input=b"".join(lines))
    checkout.git("commit", "-qm", "Fixture paths")
    return checkout.git("rev-parse", "HEAD")


def _checkout_view(worktree: Path, paths: list[str]) -> dict:
    """What the auditor checkout holds for the fixture paths: listings, lookups by each spelling, Git's view.

    Git runs with optional locks off (Stewart's hardened helper), so neither query rewrites the index.
    """
    listing = {}
    for directory in sorted({str(Path(path).parent) for path in paths}):
        where = worktree if directory == "." else worktree / directory
        try:
            names = sorted(os.listdir(os.fsencode(where)))
        except OSError as exc:
            listing[directory] = {"error": str(exc)}
            continue
        listing[directory] = [_name(os.fsdecode(name)) for name in names]
    lookups = {}
    for path in paths:
        location = worktree / path
        try:
            info = os.lstat(location)
        except FileNotFoundError:
            lookups[path] = {**_name(path), "found": False}
            continue
        data = location.read_bytes()
        lookups[path] = {**_name(path), "found": True, "inode": info.st_ino, "size": info.st_size,
                         "sha256": _sha(data), "bytes": _label(_sha(data))}
    found = [item["inode"] for item in lookups.values() if item["found"]]
    index = [os.fsdecode(row) for row in git(worktree, "ls-files", "-s", "-z").stdout.split(b"\0") if row]
    state = [os.fsdecode(row) for row in git(worktree, "status", "--porcelain=v1", "-z",
                                             "--untracked-files=all").stdout.split(b"\0") if row]
    return {"listing": listing, "lookups": lookups, "lookups_share_one_inode": len(found) > 1 and len(set(found)) == 1,
            "index": index, "git_status": state, "device": os.stat(worktree).st_dev}


def _collection_view(collected: dict) -> dict:
    """One collection's recorded outcome, its inventory's file entries and its archive members."""
    directory = Path(collected["path"])
    receipt = collected["receipt"]
    inventory = support.read_json(directory / "inventory.json")
    members = None
    if (directory / "files.tar").is_file():
        members = []
        with tarfile.open(directory / "files.tar", mode="r:") as archive:
            for member in archive.getmembers():
                row = {**_name(member.name), "type": "file" if member.isfile() else
                       "symlink" if member.issym() else "other"}
                if member.isfile():
                    stream = archive.extractfile(member)
                    digest = _sha(stream.read()) if stream is not None else None
                    row.update(sha256=digest, bytes=_label(digest))
                members.append(row)
    raw_status = directory / "status.z"
    summary = receipt.get("inventory") or {}
    return {
        "name": collected["collection"],
        "exit_code": collected["exit_code"],
        "gaps": [[gap["id"], gap["code"]] for gap in collected["gaps"]],
        "errors": receipt.get("errors"),
        "git_discovery": receipt.get("git_discovery"),
        "archive_sha256_recorded": "archive_sha256" in receipt,
        "unexpected_paths": receipt.get("unexpected_paths"),
        "checkout_files": [{**_name(item["path"]), "kind": item["kind"], "sha256": item.get("sha256"),
                            "bytes": _label(item.get("sha256")), "listed_by_git": item.get("listed_by_git", True)}
                           for item in (receipt.get("checkout") or {}).get("files", [])],
        "inventory_summary": {key: summary.get(key) for key in
                              ("counts", "archived", "omitted", "unreadable", "unsupported", "movement")},
        "inventory_files": [{**_name(entry["path"]), "kind": entry["kind"], "sha256": entry.get("sha256"),
                             "bytes": _label(entry.get("sha256"))}
                            for entry in inventory["entries"] if entry["kind"] != "directory"],
        "archive_members": members,
        "status_z": [os.fsdecode(row) for row in raw_status.read_bytes().split(b"\0") if row]
        if raw_status.is_file() else None,
        "inventory_after_recorded": (directory / "inventory-after.json").exists(),
    }


#: Top-level names every fixture checkout holds besides the fixture paths.
BASE = {".git", ".gitignore", "audits", "input.txt", "other.txt"}


def _fixture(path: str) -> bool:
    return path.split("/")[0] not in BASE


def _comparison_one(summary: dict) -> dict:
    """The measured facts of one collision case, reduced from its saved summary; pure, for the assertions."""
    held, collection = summary["checkout"], summary["collection"]
    failure = summary["prepare_error_record"]

    def reason(refusal):
        return None if refusal is None else refusal["reason"]

    return {
        "prepare": reason(summary["prepare_refusal"]),
        "prepare_failure": None if failure is None else [failure["reason"], failure["stage"]],
        "listing": {directory: [name["path"] for name in names if _fixture(name["path"]) or directory != "."]
                    for directory, names in held["listing"].items()},
        "lookups": {path: row["bytes"] if row["found"] else None for path, row in held["lookups"].items()},
        "one_inode": held["lookups_share_one_inode"],
        "git_status": [row for row in held["git_status"] if _fixture(row[3:])],
        "collect": reason(summary["collect_refusal"]),
        "exit_code": collection["exit_code"],
        "errors": [error["reason"] for error in collection["errors"]],
        "gaps": sorted(gap for gap, _ in collection["gaps"]),
        "unexpected_paths": collection["unexpected_paths"],
        "movement": collection["inventory_summary"]["movement"],
        "archive_recorded": collection["archive_sha256_recorded"],
        "receipt_files": {row["path"]: row["bytes"] for row in collection["checkout_files"] if _fixture(row["path"])},
        "inventory": {row["path"]: row["bytes"] for row in collection["inventory_files"] if _fixture(row["path"])},
        "archive": {row["path"]: row.get("bytes") for row in collection["archive_members"] if _fixture(row["path"])},
        "plan_untriaged": reason(summary["close_plan_untriaged_refusal"]),
        "triage": reason(summary["triage_refusal"]),
        "status_state": summary["status_preparation_state"],
        "status_attention": sorted({item[1] for item in summary["status_attention"]}),
        "status_actions": summary["status_next_actions"],
        "plan": reason(summary["close_plan_refusal"]),
        "plan_abandon": reason(summary["close_plan_abandon_refusal"]),
    }


#: The volume comparisons-01 ran on: lookup ignores case and normalization, and a listing keeps the
#: spelling a name was created with (APFS defaults), under core.ignorecase and core.precomposeunicode.
OBSERVED_VOLUME = {"case_insensitive_lookup": True, "case_preserved_in_listing": True,
                   "normalization_insensitive_lookup": True, "nfd_name_preserved_in_listing": True,
                   "nfc_name_in_listing": False}
OBSERVED_CONFIG = {"core.ignorecase": "true", "core.precomposeunicode": "true"}
_CLEAN = {"prepare": None, "prepare_failure": None, "collect": None, "exit_code": 1, "errors": [],
          "gaps": ["declaration_missing"], "unexpected_paths": [], "movement": False, "archive_recorded": True,
          "receipt_files": {}, "archive": {}, "git_status": [], "one_inode": False,
          "plan_untriaged": "close_not_concluded", "triage": None, "status_state": "ready", "status_attention": [],
          "status_actions": ["retain"], "plan": None, "plan_abandon": None}
#: What comparisons-01 observed for each case, reduced by ``_comparison_one``.
OBSERVED_COLLISIONS = {
    "case-control": {**_CLEAN, "listing": {".": ["Notes.md", "Other.md"]},
                     "lookups": {"Notes.md": "FIRST", "Other.md": "SECOND"},
                     "inventory": {"Notes.md": "FIRST", "Other.md": "SECOND"}},
    "case-separate-directories": {**_CLEAN, "listing": {"a": ["Notes.md"], "b": ["notes.md"]},
                                  "lookups": {"a/Notes.md": "FIRST", "b/notes.md": "SECOND"},
                                  "inventory": {"a/Notes.md": "FIRST", "b/notes.md": "SECOND"}},
    # Git wrote Notes.md, then replaced it with notes.md: one file under the later spelling, holding the
    # later entry's bytes. Git reports the earlier entry modified; the receipt and archive record that
    # spelling with the later entry's bytes, the inventory the on-disk spelling.
    "case-collision": {**_CLEAN, "listing": {".": ["notes.md"]},
                       "lookups": {"Notes.md": "SECOND", "notes.md": "SECOND"}, "one_inode": True,
                       "git_status": [" M Notes.md"], "gaps": ["declaration_missing", "unexpected_path:Notes.md"],
                       "unexpected_paths": ["Notes.md"], "receipt_files": {"Notes.md": "SECOND"},
                       "inventory": {"notes.md": "SECOND"}, "archive": {"Notes.md": "SECOND"}},
    # The input pin catches the replaced entry; the failed session is still collected, triaged, and planned.
    "case-collision-assigned-input": {
        **_CLEAN, "prepare": "prepare_failed", "prepare_failure": ["input_mismatch", "inputs"],
        "listing": {".": ["notes.md"]}, "lookups": {"Notes.md": "SECOND", "notes.md": "SECOND"}, "one_inode": True,
        "git_status": [" M Notes.md"], "exit_code": 3, "errors": ["handoff_changed", "runtime_changed"],
        "gaps": ["collection_error:0", "collection_error:1", "declaration_missing", "report_missing",
                 "unexpected_path:Notes.md"],
        "unexpected_paths": ["Notes.md"], "receipt_files": {"Notes.md": "SECOND"}, "inventory": {"notes.md": "SECOND"},
        "archive": {"Notes.md": "SECOND"}, "plan_untriaged": "close_unverified", "status_state": "failed",
        "status_attention": ["prepare_failed"], "status_actions": ["close", "fresh_assignment"]},
    "unicode-control": {**_CLEAN, "listing": {".": ["Other.md", NFC]}, "lookups": {NFC: "FIRST", "Other.md": "SECOND"},
                        "inventory": {"Other.md": "SECOND", NFC: "FIRST"}},
    # A decomposed name alone, no collision: the file keeps its spelling on disk, Git (precomposing what it
    # lists) reports the composed spelling untracked, and the receipt and archive record that spelling.
    "unicode-nfd-alone": {**_CLEAN, "listing": {".": ["Other.md", NFD]}, "lookups": {NFD: "FIRST", "Other.md": "SECOND"},
                          "git_status": ["?? " + NFC], "gaps": ["declaration_missing", "unexpected_path:" + NFC],
                          "unexpected_paths": [NFC], "receipt_files": {NFC: "FIRST"},
                          "inventory": {"Other.md": "SECOND", NFD: "FIRST"}, "archive": {NFC: "FIRST"}},
    # The decomposed entry is written first and replaced by the composed one: one file, composed spelling,
    # the composed entry's bytes; Git reports the decomposed entry modified.
    "unicode-collision": {**_CLEAN, "listing": {".": [NFC]}, "lookups": {NFC: "FIRST", NFD: "FIRST"}, "one_inode": True,
                          "git_status": [" M " + NFD], "gaps": ["declaration_missing", "unexpected_path:" + NFD],
                          "unexpected_paths": [NFD], "receipt_files": {NFD: "FIRST"}, "inventory": {NFC: "FIRST"},
                          "archive": {NFD: "FIRST"}},
    # Separate directories remove the collision but not the decomposed-name effect of unicode-nfd-alone.
    "unicode-separate-directories": {
        **_CLEAN, "listing": {"a": [NFC], "b": [NFD]}, "lookups": {"a/" + NFC: "FIRST", "b/" + NFD: "SECOND"},
        "git_status": ["?? b/" + NFC], "gaps": ["declaration_missing", "unexpected_path:b/" + NFC],
        "unexpected_paths": ["b/" + NFC], "receipt_files": {"b/" + NFC: "SECOND"},
        "inventory": {"a/" + NFC: "FIRST", "b/" + NFD: "SECOND"}, "archive": {"b/" + NFC: "SECOND"}},
}


@pytest.mark.parametrize("case", sorted(TREES))
def test_custodial_core_paths_colliding_at_preparation(checkout, tmp_path, case):
    entries, extra_inputs = TREES[case]
    paths = [path for path, _ in entries]
    ident = checkout.meta["audit_id"]
    volume = _volume(tmp_path)
    config = {key: os.fsdecode(git(checkout.repo, "config", "--get", key, check=False).stdout).strip() or None
              for key in ("core.ignorecase", "core.precomposeunicode")}
    target = _commit_paths(checkout, entries)
    tree = [path for _, _, path in tree_entries(checkout.repo, target)]
    checkout.meta["target_commit"] = target
    checkout.meta["input_files"] = ["input.txt", *extra_inputs]
    revision = checkout.prompt_commit()
    prepared, prepare_refusal = _attempt(prepare, checkout.ws, revision)
    session = Path(prepared["session"]) if prepared else support.session_path(checkout, ident)
    record = support.read_json(session / "session.json")
    worktree = Path(record["worktree"])
    prepare_error = support.read_json(session / "PREPARE-ERROR.json") if (session / "PREPARE-ERROR.json").exists() else None
    held = _checkout_view(worktree, paths) if worktree.is_dir() else None
    if prepared:
        (worktree / checkout.meta["report_path"]).write_text("A partial report.\n", encoding="utf-8")
    collected, collect_refusal = _attempt(collector.collect, checkout.ws, ident, auditor_stopped="finished")
    collection = _collection_view(collected) if collected else None
    plan_untriaged = close_plan(checkout.ws, ident)
    disposition, triage_refusal = (None, None)
    if collected:
        disposition, triage_refusal = _attempt(triage, checkout.ws, ident, collection=collected["collection"],
                                               response=support.response_for(collected), actor="fixture manager")
    view, status_refusal = _attempt(status, checkout.ws, ident)
    plan = close_plan(checkout.ws, ident)
    plan_abandon = close_plan(checkout.ws, ident, abandon=True)
    _save(tmp_path, "01-prepare", prepared if prepared else {"refusal": prepare_refusal, "error_record": prepare_error})
    if collected:
        _save(tmp_path, "02-collection", collected)
    _save(tmp_path, "03-close-plan-untriaged", plan_untriaged)
    if disposition:
        _save(tmp_path, "04-triage", disposition)
    _save(tmp_path, "05-status", view if view else {"refusal": status_refusal})
    _save(tmp_path, "06-close-plan", plan)
    _save(tmp_path, "07-close-plan-abandon", plan_abandon)
    summary = {
        "case": case,
        "volume": volume,
        "maintainer_git_config": config,
        "fixture_paths": [_name(path) for path in paths],
        "extra_inputs": extra_inputs,
        "target_tree_paths": [_name(path) for path in tree],
        "prepare_refusal": prepare_refusal,
        "prepare_error_record": prepare_error,
        "checkout": held,
        "collect_refusal": collect_refusal,
        "collection": collection,
        "close_plan_untriaged_refusal": _refusal(plan_untriaged),
        "triage_refusal": triage_refusal,
        "triage": None if disposition is None else disposition.get("triage"),
        "status_refusal": status_refusal,
        "status_preparation_state": None if view is None else view["preparation"].get("state"),
        "status_attention": _attention(view),
        "status_next_actions": _actions(view),
        "close_plan_refusal": _refusal(plan),
        "close_plan_abandon_refusal": _refusal(plan_abandon),
    }
    _save(tmp_path, "09-summary", summary)
    comparison = _comparison_one(summary)
    _save(tmp_path, "10-comparison", comparison)

    # Firing control for the fixture: the target commit holds every fixture name with its exact bytes,
    # including both members of a pair the volume cannot hold side by side.
    for path in paths:
        assert path in tree, path
    # The volume probe describes the checkout's volume only when both sit on one device.
    assert held is None or held["device"] == volume["device"]
    if case in CONTROLS:
        assert prepare_refusal is None and collect_refusal is None and triage_refusal is None
        for (path, data) in entries:
            assert held["lookups"][path]["found"] and held["lookups"][path]["sha256"] == _sha(data)
        assert collection["errors"] == [] and collection["unexpected_paths"] == []
        assert collection["inventory_summary"]["movement"] is False and collection["archive_sha256_recorded"]
        assert _refusal(plan) is None
    # Observed in comparisons-01 and asserted from comparisons-02 on: they hold for the volume and Git
    # configuration recorded above, so those are asserted first.
    assert {key: volume[key] for key in OBSERVED_VOLUME} == OBSERVED_VOLUME
    assert config == OBSERVED_CONFIG
    assert comparison == OBSERVED_COLLISIONS[case]


# --- 2. mirror operations and Stewart's refs -------------------------------------------------------

def _refs(repository: Path) -> list[str]:
    listed = git(repository, "for-each-ref", "--format=%(refname) %(objectname)").stdout.decode()
    return sorted(line for line in listed.splitlines() if line)


def _storage(git_dir: Path, uuid: str) -> dict:
    """Whether Stewart's private storage, or anything naming the session, sits under a Git directory."""
    named_stewart, naming_session, session_records = [], [], []
    for location in sorted(git_dir.rglob("*")):
        rel = str(location.relative_to(git_dir))
        if "stewart" in location.parts[len(git_dir.parts):]:
            named_stewart.append(rel)
        if uuid in rel:
            naming_session.append(rel)
        if location.name == "session.json":
            session_records.append(rel)
    return {"git_dir": str(git_dir), "stewart_directory": (git_dir / "stewart").exists(),
            "worktrees_directory": (git_dir / "worktrees").exists(),
            "top_level": sorted(entry.name for entry in git_dir.iterdir()),
            "entries_named_stewart": named_stewart[:50], "entries_named_stewart_count": len(named_stewart),
            "entries_naming_session": naming_session, "session_records": session_records}


def test_custodial_core_mirror_operations_and_session_refs(checkout, tmp_path, run_cmd):
    prepared = support.prepared_session(checkout)
    record = support.read_json(prepared.session / "session.json")
    uuid = record["session_uuid"]
    repo = checkout.repo
    common = Path(record["common_dir"])
    checkout.git("update-ref", "refs/probe/x", "HEAD")
    probe_commit = checkout.git("rev-parse", "refs/probe/x")
    mirror, pushed, plain = tmp_path / "mirror.git", tmp_path / "pushed.git", tmp_path / "plain"
    run_cmd(["git", "clone", "--mirror", "-q", str(repo), str(mirror)], check=True)
    run_cmd(["git", "init", "--bare", "-q", str(pushed)], check=True)
    push = run_cmd(["git", "push", "--mirror", str(pushed)], cwd=repo, check=True)
    run_cmd(["git", "clone", "-q", str(repo), str(plain)], check=True)
    session_prefix = f"refs/stewart/sessions/{uuid}/"
    recorded = sorted(f"{entry['ref']} {entry['commit']}" for entry in record["retention"]["refs"].values())

    def carried(refs):
        return {"stewart_session_refs": [ref for ref in refs if ref.startswith(session_prefix)],
                "any_refs_stewart": [ref for ref in refs if ref.startswith("refs/stewart/")],
                "probe_ref": [ref for ref in refs if ref.startswith("refs/probe/")], "all_refs": refs}

    places = {"maintainer": (repo, common), "mirror_clone": (mirror, mirror), "mirror_push": (pushed, pushed),
              "ordinary_clone": (plain, plain / ".git")}
    observed = {name: {**carried(_refs(where)), "storage": _storage(git_dir, uuid)}
                for name, (where, git_dir) in places.items()}
    summary = {"session_uuid": uuid, "recorded_retention_refs": recorded, "probe_ref": f"refs/probe/x {probe_commit}",
               "push_stderr": push.stderr, "observed": observed,
               "retention_refs_match_record": {name: sorted(value["stewart_session_refs"]) == recorded
                                               for name, value in observed.items()}}
    _save(tmp_path, "09-summary", summary)

    # Firing controls: the maintainer holds the recorded session refs and the private storage the probe
    # looks for, and a hand-made ref outside refs/heads and refs/tags reaches both mirror operations.
    assert summary["retention_refs_match_record"]["maintainer"]
    assert observed["maintainer"]["storage"]["stewart_directory"]
    assert observed["maintainer"]["storage"]["session_records"]
    for name in ("mirror_clone", "mirror_push"):
        assert observed[name]["probe_ref"] == [f"refs/probe/x {probe_commit}"], name
    # Observed in comparisons-01: both mirror operations carry the session's retention refs with their
    # recorded commits and nothing of the private storage (no stewart/ or worktrees/ directory, no session
    # record, no name of the session outside its refs); an ordinary clone carries neither refs nor storage.
    for name in ("mirror_clone", "mirror_push"):
        storage = observed[name]["storage"]
        assert summary["retention_refs_match_record"][name], name
        assert observed[name]["any_refs_stewart"] == observed[name]["stewart_session_refs"], name
        assert not storage["stewart_directory"] and not storage["worktrees_directory"], name
        assert storage["session_records"] == [], name
        assert [rel for rel in storage["entries_naming_session"]
                if not rel.startswith(session_prefix.rstrip("/"))] == [], name
    plain = observed["ordinary_clone"]
    assert plain["any_refs_stewart"] == [] and plain["probe_ref"] == []
    assert not plain["storage"]["stewart_directory"] and not plain["storage"]["worktrees_directory"]
    assert plain["storage"]["session_records"] == [] and plain["storage"]["entries_naming_session"] == []


# --- 3. writes relative to collection --------------------------------------------------------------

WRITES = ["no-writer", "during-before-discovery", "during-after-archive", "during-outside-checkout",
          "after-collection"]
APPENDED = b"a writer's line, appended by the comparison\n"


def _member_bytes(directory: Path, rel: str, original: bytes, changed: bytes) -> str:
    """Which version of ``rel`` a collection archive holds: original, changed, other or absent."""
    archive = directory / "files.tar"
    if not archive.is_file():
        return "no archive"
    with tarfile.open(archive, mode="r:") as bundle:
        try:
            stream = bundle.extractfile(rel)
        except KeyError:
            return "absent"
        data = stream.read() if stream is not None else None
    return {original: "original", changed: "changed"}.get(data, "other")


def _entry_bytes(entries: list[dict], rel: str, original: bytes, changed: bytes) -> str:
    entry = next((item for item in entries if item["path"] == rel), None)
    if entry is None:
        return "absent"
    return {_sha(original): "original", _sha(changed): "changed"}.get(entry.get("sha256"), "other")


def _comparison_three(summary: dict) -> dict:
    """The measured facts of one write case, reduced from its saved summary; pure, for the assertions."""
    def reason(refusal):
        return None if refusal is None else refusal["reason"]

    abandon = summary["close_plan_abandon_refusal"]
    return {
        "exit_code": summary["exit_code"],
        "errors": [error["reason"] for error in summary["errors"]],
        "gaps": sorted(gap for gap, _ in summary["gaps"]),
        "git_discovery": summary["git_discovery"],
        "movement": summary["movement"],
        "archive_recorded": summary["archive_sha256_recorded"],
        "unexpected_paths": summary["unexpected_paths"],
        "other_txt": summary["other_txt"],
        "outside_file_written": summary["outside_file_written"],
        "receipt_unchanged_through_plan": summary["receipt_unchanged_through_plan"],
        "triage": reason(summary["triage_refusal"]),
        "status": reason(summary["status_refusal"]),
        "status_attention": summary["status_attention"],
        "status_actions": summary["status_next_actions"],
        "plan_before_write": reason(summary["close_plan_before_write_refusal"]),
        "plan": reason(summary["close_plan_refusal"]),
        "plan_abandon": reason(abandon),
        "plan_abandon_message": None if abandon is None else abandon["message"],
    }


_UNMOVED = {"exit_code": 1, "errors": [], "gaps": ["declaration_missing"], "git_discovery": "complete",
            "movement": False, "archive_recorded": True, "unexpected_paths": [],
            "other_txt": {"archive": "absent", "receipt_checkout_files": "absent", "inventory": "original",
                          "inventory_after": None, "live_at_plan": "original"},
            "outside_file_written": False, "receipt_unchanged_through_plan": True, "triage": None, "status": None,
            "status_attention": [], "status_actions": ["retain"], "plan_before_write": None, "plan": None,
            "plan_abandon": None, "plan_abandon_message": None}
_MOVED = {**_UNMOVED, "errors": ["movement"], "gaps": ["collection_error:0", "declaration_missing", "movement_detected"],
          "movement": True, "archive_recorded": False, "unexpected_paths": None,
          "plan_before_write": "capture_not_recorded", "plan": "capture_not_recorded",
          "plan_abandon": "uncollected_changes",
          "plan_abandon_message": "the checkout holds changes no collection captured: "
                                  "audits/ws/reports/one-question.md, other.txt"}
#: What comparisons-01 observed for each case, reduced by ``_comparison_three``.
OBSERVED_WRITES = {
    "no-writer": _UNMOVED,
    # The archive and the receipt's Git view hold the written bytes; the before-inventory does not.
    "during-before-discovery": {**_MOVED, "other_txt": {"archive": "changed", "receipt_checkout_files": "changed",
                                                        "inventory": "original", "inventory_after": "changed",
                                                        "live_at_plan": "changed"}},
    # Only the after-observations hold the written bytes.
    "during-after-archive": {**_MOVED, "other_txt": {"archive": "absent", "receipt_checkout_files": "absent",
                                                     "inventory": "original", "inventory_after": "changed",
                                                     "live_at_plan": "changed"}},
    "during-outside-checkout": {**_UNMOVED, "outside_file_written": True},
    # The receipt stands unchanged and status reports nothing; close's own inventory comparison refuses.
    "after-collection": {**_UNMOVED, "other_txt": {**_UNMOVED["other_txt"], "live_at_plan": "changed"},
                         "plan": "checkout_changed", "plan_abandon": "uncollected_changes",
                         "plan_abandon_message": "the checkout holds changes no collection captured: other.txt"},
}


@pytest.mark.parametrize("case", WRITES)
def test_custodial_core_writes_relative_to_collection(checkout, tmp_path, monkeypatch, case):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    tracked = prepared.worktree / "other.txt"
    original = tracked.read_bytes()
    changed = original + APPENDED
    outside = tmp_path / "outside-writer.txt"
    calls = {"checkout_state": 0, "archive_files": 0, "writes": []}
    real_state, real_archive = collector.checkout_state, collector.archive_files

    def write(target: Path, when: str) -> None:
        with target.open("ab") as stream:
            stream.write(APPENDED)
        calls["writes"].append({"path": str(target), "when": when})

    def state_then(*args, **kwargs):
        # The first call is collection's Git discovery; the before-inventory was already written.
        calls["checkout_state"] += 1
        if case == "during-before-discovery" and calls["checkout_state"] == 1:
            write(tracked, "after the before-inventory, before Git discovery")
        return real_state(*args, **kwargs)

    def archive_then(*args, **kwargs):
        calls["archive_files"] += 1
        result = real_archive(*args, **kwargs)
        if case == "during-after-archive":
            write(tracked, "after the archive, before the after-inventory")
        elif case == "during-outside-checkout":
            write(outside, "after the archive, before the after-inventory, outside the checkout")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(collector, "checkout_state", state_then)
        patch.setattr(collector, "archive_files", archive_then)
        collected = collector.collect(checkout.ws, ident, auditor_stopped="finished")
    directory = Path(collected["path"])
    receipt_digest = _sha((directory / "collection.json").read_bytes())
    disposition, triage_refusal = _attempt(triage, checkout.ws, ident, collection=collected["collection"],
                                           response=support.response_for(collected), actor="fixture manager")
    plan_before_write = close_plan(checkout.ws, ident)
    if case == "after-collection":
        write(tracked, "after collection and triage, before close")
    view, status_refusal = _attempt(status, checkout.ws, ident)
    plan = close_plan(checkout.ws, ident)
    plan_abandon = close_plan(checkout.ws, ident, abandon=True)
    _save(tmp_path, "02-collection", collected)
    if disposition:
        _save(tmp_path, "04-triage", disposition)
    _save(tmp_path, "05-status", view if view else {"refusal": status_refusal})
    _save(tmp_path, "06-close-plan-before-write", plan_before_write)
    _save(tmp_path, "06-close-plan", plan)
    _save(tmp_path, "07-close-plan-abandon", plan_abandon)
    receipt = collected["receipt"]
    after_inventory = (support.read_json(directory / "inventory-after.json")["entries"]
                       if (directory / "inventory-after.json").exists() else None)
    summary = {
        "case": case,
        "injection": calls,
        "collection": collected["collection"],
        "exit_code": collected["exit_code"],
        "errors": receipt["errors"],
        "gaps": [[gap["id"], gap["code"]] for gap in collected["gaps"]],
        "git_discovery": receipt["git_discovery"],
        "movement": receipt["inventory"]["movement"],
        "archive_sha256_recorded": "archive_sha256" in receipt,
        "unexpected_paths": receipt.get("unexpected_paths"),
        "other_txt": {
            "archive": _member_bytes(directory, "other.txt", original, changed),
            "receipt_checkout_files": _entry_bytes((receipt.get("checkout") or {}).get("files", []), "other.txt",
                                                   original, changed),
            "inventory": _entry_bytes(support.read_json(directory / "inventory.json")["entries"], "other.txt",
                                      original, changed),
            "inventory_after": None if after_inventory is None else _entry_bytes(after_inventory, "other.txt",
                                                                                 original, changed),
            "live_at_plan": {original: "original", changed: "changed"}.get(tracked.read_bytes(), "other"),
        },
        "outside_file_written": outside.exists(),
        "receipt_unchanged_through_plan": _sha((directory / "collection.json").read_bytes()) == receipt_digest,
        "triage_refusal": triage_refusal,
        "triage": None if disposition is None else disposition.get("triage"),
        "status_attention": _attention(view),
        "status_next_actions": _actions(view),
        "status_refusal": status_refusal,
        "close_plan_before_write_refusal": _refusal(plan_before_write),
        "close_plan_refusal": _refusal(plan),
        "close_plan_abandon_refusal": _refusal(plan_abandon),
    }
    _save(tmp_path, "09-summary", summary)
    comparison = _comparison_three(summary)
    _save(tmp_path, "10-comparison", comparison)

    # Firing controls: collection ran its Git discovery through the wrappers, and each writing case wrote once.
    assert calls["checkout_state"] >= 1 and calls["archive_files"] == 1
    assert len(calls["writes"]) == (0 if case == "no-writer" else 1)
    if case == "no-writer":
        assert receipt["errors"] == [] and receipt["inventory"]["movement"] is False
        assert "archive_sha256" in receipt and triage_refusal is None
        assert _refusal(plan) is None and summary["other_txt"]["live_at_plan"] == "original"
    # Observed in comparisons-01 and asserted from comparisons-02 on.
    assert calls["checkout_state"] == 2
    assert comparison == OBSERVED_WRITES[case]


# --- 4. checkout transformations on a file the auditor never touches -------------------------------

#: Each case commits one .gitattributes in the target tree; only its text differs.
ATTRIBUTES = {
    "no-attributes": "# no attribute applies to any path\n",
    "eol-crlf-other": "other.txt text eol=crlf\n",
    "eol-crlf-unmatched": "absent.txt text eol=crlf\n",
    "eol-crlf-all-txt": "*.txt text eol=crlf\n",
}
TRANSFORMED = ("input.txt", "other.txt")


def _version(data: bytes | None, blob: bytes) -> str | None:
    """Whether bytes are the committed blob, the blob with CRLF line endings, or something else."""
    if data is None:
        return None
    return {blob: "blob", blob.replace(b"\n", b"\r\n"): "crlf"}.get(data, "other")


def _version_of_digest(digest: str | None, blob: bytes) -> str | None:
    if digest is None:
        return None
    return {_sha(blob): "blob", _sha(blob.replace(b"\n", b"\r\n")): "crlf"}.get(digest, "other")


def _member(directory: Path, rel: str) -> bytes | None:
    archive = directory / "files.tar"
    if not archive.is_file():
        return None
    with tarfile.open(archive, mode="r:") as bundle:
        try:
            stream = bundle.extractfile(rel)
        except KeyError:
            return None
        return stream.read() if stream is not None else None


def _closing_records(result: dict | None) -> tuple[dict | None, dict | None]:
    """The CLOSING.json and CLOSED.json a close wrote, as recorded."""
    if result is None:
        return None, None
    closing = support.read_json(Path(result["closing"]))
    closed = support.read_json(Path(result["closed"])) if result.get("closed") else None
    return closing, closed


def _close_result(result: dict | None) -> dict | None:
    if result is None:
        return None
    return {key: result.get(key) for key in ("mode", "closing", "closed", "released", "exit_code", "leftovers",
                                             "failed", "results")}


def _uncovered(refusal: dict | None) -> list[str] | None:
    """The paths a capture_uncovered refusal names as held by neither the archive nor the prompt commit."""
    if refusal is None or refusal["reason"] != "capture_uncovered":
        return None
    return sorted(re.findall(r"([^\s:;]+) \(file in neither the archive nor the prompt commit\)", refusal["message"]))


def _comparison_four(summary: dict) -> dict:
    """The measured facts of one attributes case, reduced from its saved summary; pure, for the assertions."""
    def reason(refusal):
        return None if refusal is None else refusal["reason"]

    result = summary["close_result"]
    return {
        "prepare": reason(summary["prepare_refusal"]),
        "prepare_failure": None if summary["prepare_failure"] is None else summary["prepare_failure"][:2],
        "checkout_bytes": summary["checkout_bytes"], "git_status": summary["git_status"],
        "collect": reason(summary["collect_refusal"]), "exit_code": summary["collection_exit_code"],
        "errors": summary["collection_errors"], "gaps": summary["collection_gaps"],
        "unexpected_paths": summary["unexpected_paths"], "archive_recorded": summary["archive_recorded"],
        "collected_files": summary["collected_files"],
        "plan_untriaged": reason(summary["close_plan_untriaged_refusal"]), "triage": reason(summary["triage_refusal"]),
        "status_attention": sorted({item[1] for item in summary["status_attention"]}),
        "status_actions": summary["status_next_actions"],
        "plan": reason(summary["close_plan_refusal"]), "plan_uncovered": _uncovered(summary["close_plan_refusal"]),
        "plan_abandon": reason(summary["close_plan_abandon_refusal"]),
        "close": reason(summary["close_refusal"]), "close_uncovered": _uncovered(summary["close_refusal"]),
        "close_mode": None if result is None else result["mode"],
        "close_exit_code": None if result is None else result["exit_code"],
        "closing_stage": summary["closing_observed_stage"], "after_close": summary["after_close"],
    }


_UNTOUCHED = {"inventory": "blob", "receipt_checkout_files": None, "archive": None}
_CLOSED_CLEANLY = {
    "prepare": None, "prepare_failure": None, "checkout_bytes": {"input.txt": "blob", "other.txt": "blob"},
    "git_status": [], "collect": None, "exit_code": 1, "errors": [], "gaps": ["declaration_missing"],
    "unexpected_paths": [], "archive_recorded": True,
    "collected_files": {"input.txt": _UNTOUCHED, "other.txt": _UNTOUCHED},
    "plan_untriaged": "close_not_concluded", "triage": None, "status_attention": [], "status_actions": ["retain"],
    "plan": None, "plan_uncovered": None, "plan_abandon": None, "close": None, "close_uncovered": None,
    "close_mode": "concluded", "close_exit_code": 0, "closing_stage": "ready",
    "after_close": {"worktree_exists": False, "session_exists": False}}
_UNCOVERED = {"plan_abandon": "uncollected_changes", "close_mode": None, "close_exit_code": None, "closing_stage": None,
              "after_close": {"worktree_exists": True, "session_exists": True}}
#: What comparisons-03 observed for each case, reduced by ``_comparison_four``.
OBSERVED_ATTRIBUTES = {
    "no-attributes": _CLOSED_CLEANLY,
    "eol-crlf-unmatched": _CLOSED_CLEANLY,
    # Git reports the converted file clean, so nothing archives it, no gap names it and status offers retain;
    # the concluded close (plan and actual) refuses from the inventory's bytes, removing nothing.
    "eol-crlf-other": {**_CLOSED_CLEANLY, **_UNCOVERED, "checkout_bytes": {"input.txt": "blob", "other.txt": "crlf"},
                       "collected_files": {"input.txt": _UNTOUCHED, "other.txt": {**_UNTOUCHED, "inventory": "crlf"}},
                       "plan": "capture_uncovered", "plan_uncovered": ["other.txt"],
                       "close": "capture_uncovered", "close_uncovered": ["other.txt"]},
    # The attribute also converts the assigned input, which preparation's input check catches.
    "eol-crlf-all-txt": {**_CLOSED_CLEANLY, **_UNCOVERED, "prepare": "prepare_failed",
                         "prepare_failure": ["input_mismatch", "inputs"],
                         "checkout_bytes": {"input.txt": "crlf", "other.txt": "crlf"}, "exit_code": 3,
                         "errors": ["handoff_changed", "runtime_changed"],
                         "gaps": ["collection_error:0", "collection_error:1", "declaration_missing", "report_missing"],
                         "collected_files": {"input.txt": {**_UNTOUCHED, "inventory": "crlf"},
                                             "other.txt": {**_UNTOUCHED, "inventory": "crlf"}},
                         "plan_untriaged": "close_unverified", "status_attention": ["prepare_failed"],
                         "status_actions": ["close", "fresh_assignment"],
                         "plan": "capture_uncovered", "plan_uncovered": ["input.txt", "other.txt"],
                         "close": "capture_uncovered", "close_uncovered": ["input.txt", "other.txt"]},
}


@pytest.mark.parametrize("case", sorted(ATTRIBUTES))
def test_custodial_core_checkout_transformation_on_untouched_file(checkout, tmp_path, case):
    ident = checkout.meta["audit_id"]
    (checkout.repo / ".gitattributes").write_text(ATTRIBUTES[case])
    checkout.git("add", "--", ".gitattributes")
    checkout.git("commit", "-qm", "Attributes fixture")
    target = checkout.git("rev-parse", "HEAD")
    blobs = {rel: git(checkout.repo, "cat-file", "blob", f"{target}:{rel}").stdout for rel in TRANSFORMED}
    attributes = git(checkout.repo, "cat-file", "blob", f"{target}:.gitattributes").stdout
    checkout.meta["target_commit"] = target
    revision = checkout.prompt_commit()
    prepared, prepare_refusal = _attempt(prepare, checkout.ws, revision)
    session = Path(prepared["session"]) if prepared else support.session_path(checkout, ident)
    record = support.read_json(session / "session.json")
    worktree = Path(record["worktree"])
    failure = session / "PREPARE-ERROR.json"
    prepare_error = support.read_json(failure) if failure.exists() else None
    held = {rel: _version((worktree / rel).read_bytes() if (worktree / rel).is_file() else None, blobs[rel])
            for rel in TRANSFORMED}
    git_status = [os.fsdecode(row) for row in git(worktree, "status", "--porcelain=v1", "-z",
                                                  "--untracked-files=all").stdout.split(b"\0")
                  if row and not os.fsdecode(row)[3:].startswith("audits/")]
    if prepared:
        (worktree / checkout.meta["report_path"]).write_text("A partial report.\n", encoding="utf-8")
    collected, collect_refusal = _attempt(collector.collect, checkout.ws, ident, auditor_stopped="finished")
    files = {}
    if collected:
        directory, receipt = Path(collected["path"]), collected["receipt"]
        entries = support.read_json(directory / "inventory.json")["entries"]
        listed = (receipt.get("checkout") or {}).get("files", [])
        for rel in TRANSFORMED:
            entry = next((item for item in entries if item["path"] == rel), None)
            reported = next((item for item in listed if item["path"] == rel), None)
            files[rel] = {"inventory": None if entry is None else _version_of_digest(entry.get("sha256"), blobs[rel]),
                          "receipt_checkout_files": None if reported is None
                          else _version_of_digest(reported.get("sha256"), blobs[rel]),
                          "archive": _version(_member(directory, rel), blobs[rel])}
    plan_untriaged = close_plan(checkout.ws, ident)
    disposition, triage_refusal = (None, None)
    if collected:
        disposition, triage_refusal = _attempt(triage, checkout.ws, ident, collection=collected["collection"],
                                               response=support.response_for(collected), actor="fixture manager")
    view, status_refusal = _attempt(status, checkout.ws, ident)
    plan = close_plan(checkout.ws, ident)
    plan_abandon = close_plan(checkout.ws, ident, abandon=True)
    result, close_refusal = _attempt(close, checkout.ws, ident, actor="fixture manager")
    closing, closed = _closing_records(result)
    _save(tmp_path, "01-prepare", prepared if prepared else {"refusal": prepare_refusal, "error_record": prepare_error})
    if collected:
        _save(tmp_path, "02-collection", collected)
    _save(tmp_path, "03-close-plan-untriaged", plan_untriaged)
    if disposition:
        _save(tmp_path, "04-triage", disposition)
    _save(tmp_path, "05-status", view if view else {"refusal": status_refusal})
    _save(tmp_path, "06-close-plan", plan)
    _save(tmp_path, "07-close-plan-abandon", plan_abandon)
    _save(tmp_path, "08-close", {"result": result, "refusal": close_refusal, "closing": closing, "closed": closed})
    summary = {
        "case": case,
        "attributes": attributes.decode(),
        "prepare_refusal": prepare_refusal,
        "prepare_failure": None if prepare_error is None else [prepare_error["reason"], prepare_error["stage"],
                                                               prepare_error["error"]],
        "checkout_bytes": held,
        "git_status": git_status,
        "collect_refusal": collect_refusal,
        "collection_exit_code": None if collected is None else collected["exit_code"],
        "collection_errors": None if collected is None else [error["reason"] for error in collected["receipt"]["errors"]],
        "collection_gaps": None if collected is None else sorted(gap["id"] for gap in collected["gaps"]),
        "unexpected_paths": None if collected is None else collected["receipt"].get("unexpected_paths"),
        "archive_recorded": None if collected is None else "archive_sha256" in collected["receipt"],
        "collected_files": files,
        "close_plan_untriaged_refusal": _refusal(plan_untriaged),
        "triage_refusal": triage_refusal,
        "status_refusal": status_refusal,
        "status_attention": _attention(view),
        "status_next_actions": _actions(view),
        "close_plan_refusal": _refusal(plan),
        "close_plan_abandon_refusal": _refusal(plan_abandon),
        "close_refusal": close_refusal,
        "close_result": _close_result(result),
        "closing_observed_stage": None if closing is None else closing["observed"].get("stage"),
        "after_close": {"worktree_exists": worktree.exists(), "session_exists": session.exists()},
    }
    _save(tmp_path, "09-summary", summary)
    comparison = _comparison_four(summary)
    _save(tmp_path, "10-comparison", comparison)

    # Firing control for the fixture: the target tree carries exactly the case's attributes.
    assert attributes.decode() == ATTRIBUTES[case]
    if case == "no-attributes":
        assert prepare_refusal is None and held == {"input.txt": "blob", "other.txt": "blob"}
        assert summary["collection_errors"] == [] and summary["unexpected_paths"] == []
        assert summary["close_plan_refusal"] is None and close_refusal is None and result["closed"] is not None
        assert not worktree.exists()
    # Observed in comparisons-03 and asserted from comparisons-04 on.
    assert comparison == OBSERVED_ATTRIBUTES[case]


# --- 5. moving the repository with a live session ---------------------------------------------------

def _probe(ws, ident: str) -> dict:
    """status, collect and close --plan against one maintainer path: each outcome or refusal, with its code."""
    view, status_refusal = _attempt(status, ws, ident)
    collected, collect_refusal = _attempt(collector.collect, ws, ident, auditor_stopped="finished")
    plan, plan_raised = _attempt(close_plan, ws, ident)
    return {
        "repo": str(ws.repo),
        "status_refusal": status_refusal,
        "status": None if view is None else {"exit_code": view["exit_code"], "stage": view.get("stage"),
                                             "attention": _attention(view)},
        "collect_refusal": collect_refusal,
        "collect": None if collected is None else {
            "collection": collected["collection"], "path": collected["path"], "exit_code": collected["exit_code"],
            "errors": [error["reason"] for error in collected["receipt"]["errors"]],
            "gaps": sorted(gap["id"] for gap in collected["gaps"])},
        "close_plan_raised": plan_raised,
        "close_plan_refusal": None if plan is None else _refusal(plan),
    }


def _reasons(probe: dict) -> dict:
    """Each operation's refusal reason and exit code, or None where it ran."""
    def pair(refusal):
        return None if refusal is None else [refusal["reason"], refusal["exit_code"]]
    return {"status": pair(probe["status_refusal"]), "collect": pair(probe["collect_refusal"]),
            "close_plan": pair(probe["close_plan_raised"]), "close_plan_own_refusal": pair(probe["close_plan_refusal"])}


def _registry_rows(git_dir: Path) -> list[dict]:
    rows = []
    for location in sorted((git_dir / "stewart" / "worktree-roles").glob("*.json")):
        row = support.read_json(location)
        rows.append({"row": location.name, **{key: row.get(key) for key in ("common_dir", "git_admin", "session",
                                                                           "worktree")}})
    return rows


_OPERATING = {"status": None, "collect": None, "close_plan": None,
              "close_plan_own_refusal": ["close_not_concluded", 2]}
_REGISTRY_REFUSED = {"status": ["worktree_role_registry", 3], "collect": ["worktree_role_registry", 3],
                     "close_plan": ["worktree_role_registry", 3], "close_plan_own_refusal": None}


def test_custodial_core_repository_moved_with_live_session(checkout, tmp_path):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    original = checkout.repo
    before = _probe(checkout.ws, ident)
    moved = tmp_path / "moved-main"
    original.rename(moved)
    moved_ws = workspace(moved, support.WS)
    moved_session = moved / prepared.session.relative_to(original)
    session_before = support.snapshot_tree(moved_session)
    while_moved = _probe(moved_ws, ident)
    session_after = support.snapshot_tree(moved_session)
    rows = _registry_rows(moved / ".git")
    pointer = (prepared.worktree / ".git").read_text().strip()
    pointer_target = Path(pointer.removeprefix("gitdir: "))
    pointer_target_exists = pointer_target.exists()
    moved.rename(original)
    restored = _probe(checkout.ws, ident)
    summary = {
        "original": str(original), "moved": str(moved),
        "before": before, "while_moved": while_moved, "restored": restored,
        "reasons": {"before": _reasons(before), "while_moved": _reasons(while_moved), "restored": _reasons(restored)},
        "registry_rows_while_moved": rows, "moved_common_dir": str(moved / ".git"),
        "session_entries_added_while_moved": sorted(set(session_after) - set(session_before)),
        "session_entries_changed_while_moved": sorted(path for path in session_before
                                                      if session_after.get(path) != session_before[path]),
        "worktree_git_pointer": pointer, "pointer_target_exists_while_moved": pointer_target_exists,
    }
    _save(tmp_path, "09-summary", summary)

    # Firing control: the same three operations run before the move.
    assert _reasons(before) == {"status": None, "collect": None, "close_plan": None,
                                "close_plan_own_refusal": _reasons(before)["close_plan_own_refusal"]}
    # Observed in comparisons-03 and asserted from comparisons-04 on: every row names the old common
    # directory, all three operations refuse with 3 and write nothing, and moving back restores them.
    assert _reasons(before) == _reasons(restored) == _OPERATING
    assert _reasons(while_moved) == _REGISTRY_REFUSED
    assert [row["common_dir"] for row in rows] == [str(original / ".git")]
    assert summary["session_entries_added_while_moved"] == summary["session_entries_changed_while_moved"] == []
    assert not pointer_target_exists


def test_custodial_core_repository_copied_with_live_session(checkout, tmp_path):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    before = _probe(checkout.ws, ident)
    copy = tmp_path / "copied-main"
    shutil.copytree(checkout.repo, copy, symlinks=True)
    original_after_copy = _probe(checkout.ws, ident)
    original_session = support.snapshot_tree(prepared.session)
    worktree_before = support.snapshot_tree(prepared.worktree)
    copy_ws = workspace(copy, support.WS)
    copy_session = copy / prepared.session.relative_to(checkout.repo)
    copy_before = support.snapshot_tree(copy_session)
    copied = _probe(copy_ws, ident)
    copy_after = support.snapshot_tree(copy_session)
    original_session_after = support.snapshot_tree(prepared.session)
    worktree_after = support.snapshot_tree(prepared.worktree)
    original_final = _probe(checkout.ws, ident)
    summary = {
        "original": str(checkout.repo), "copy": str(copy),
        "before": before, "original_after_copy": original_after_copy, "copy_probe": copied,
        "original_final": original_final,
        "reasons": {"before": _reasons(before), "original_after_copy": _reasons(original_after_copy),
                    "copy": _reasons(copied), "original_final": _reasons(original_final)},
        "registry_rows_in_copy": _registry_rows(copy / ".git"), "copy_common_dir": str(copy / ".git"),
        "copy_session_entries_added": sorted(set(copy_after) - set(copy_before)),
        "original_session_unchanged_by_copy_probe": original_session_after == original_session,
        "worktree_unchanged_by_copy_probe": worktree_after == worktree_before,
    }
    _save(tmp_path, "09-summary", summary)

    # Firing control: the same three operations run before the copy exists.
    assert _reasons(before) == {"status": None, "collect": None, "close_plan": None,
                                "close_plan_own_refusal": _reasons(before)["close_plan_own_refusal"]}
    # Observed in comparisons-03 and asserted from comparisons-04 on: the original keeps working beside its
    # copy; the copy refuses all three operations with 3, writing nothing in either session or the checkout.
    assert _reasons(before) == _reasons(original_after_copy) == _reasons(original_final) == _OPERATING
    assert _reasons(copied) == _REGISTRY_REFUSED
    assert [row["common_dir"] for row in summary["registry_rows_in_copy"]] == [str(checkout.repo / ".git")]
    assert summary["copy_session_entries_added"] == []
    assert summary["original_session_unchanged_by_copy_probe"] and summary["worktree_unchanged_by_copy_probe"]


# --- 6. a concluded close over a failed preparation ---------------------------------------------------

#: Each case: extra assigned inputs (Notes.md is replaced at checkout) and whether the close abandons.
FAILED_CLOSE = {
    "prepared-concluded": ([], False),
    "failed-concluded": (["Notes.md"], False),
    "failed-abandoned": (["Notes.md"], True),
}


def _comparison_six(summary: dict) -> dict:
    """The measured facts of one close case, reduced from its saved summary; pure, for the assertions."""
    observed, result = summary["closing_observed"] or {}, summary["close_result"] or {}
    basis = observed.get("release_basis")
    return {
        "prepare": summary["prepare_refusal"], "prepare_failure": summary["prepare_failure"],
        "collect": summary["collect_refusal"], "gaps": summary["collection_gaps"], "triage": summary["triage_refusal"],
        "status_stage": summary["status_stage"], "status_preparation": summary["status_preparation_state"],
        "status_attention": sorted({item[1] for item in summary["status_attention"]}),
        "status_actions": summary["status_next_actions"],
        "plan": None if summary["close_plan_refusal"] is None else summary["close_plan_refusal"]["reason"],
        "close": None if summary["close_refusal"] is None else summary["close_refusal"]["reason"],
        "close_mode": result.get("mode"), "close_exit_code": result.get("exit_code"), "released": result.get("released"),
        "closing_stage": observed.get("stage"), "closing_problems": observed.get("problems"),
        "closing_triage_recorded": observed.get("triage") is not None,
        "closing_collection_recorded": observed.get("collection") is not None,
        "closing_release_basis": None if basis is None else {"failure_stage": basis["failure_receipt"].get("stage"),
                                                             "session_entries": basis["session_entries"]},
        "closing_mentions_prepare_error": summary["closing_mentions_prepare_error"],
        "closing_mentions_failure_reason": summary["closing_mentions_failure_reason"],
        "after_close": summary["after_close"], "audit_id_reuse": summary["audit_id_reuse_refusal"],
        "status_after_close": summary["status_after_close"],
    }


_GONE = {"worktree_exists": False, "session_exists": False, "session_refs": [], "registry_row_exists": False}
_FAILED = {"prepare": ["prepare_failed", 2], "prepare_failure": ["input_mismatch", "inputs"], "collect": None,
           "gaps": ["collection_error:0", "collection_error:1", "declaration_missing", "report_missing",
                    "unexpected_path:Notes.md"],
           "triage": None, "status_stage": "preparation_failed", "status_preparation": "failed",
           "status_attention": ["prepare_failed"], "status_actions": ["close", "fresh_assignment"], "plan": None,
           "close": None, "close_exit_code": 0, "released": False, "closing_stage": "failed",
           "closing_problems": ["prepare_failed"], "closing_mentions_prepare_error": False,
           "closing_mentions_failure_reason": False, "after_close": _GONE, "audit_id_reuse": ["audit_id_reserved", 2],
           "status_after_close": {"stage": None, "exit_code": 0}}
#: What comparisons-03 observed for each case, reduced by ``_comparison_six``.
OBSERVED_CLOSES = {
    "prepared-concluded": {**_FAILED, "prepare": None, "prepare_failure": None,
                           "gaps": ["declaration_missing", "unexpected_path:Notes.md"], "status_stage": "triaged",
                           "status_preparation": "ready", "status_attention": [], "status_actions": ["retain"],
                           "close_mode": "concluded", "closing_stage": "ready", "closing_problems": [],
                           "closing_triage_recorded": True, "closing_collection_recorded": True,
                           "closing_release_basis": None},
    # The concluded close runs to completion over the failed preparation and removes PREPARE-ERROR.json with
    # the session; its record keeps the stage and the problem reason, not the failure's reason or digest.
    "failed-concluded": {**_FAILED, "close_mode": "concluded", "closing_triage_recorded": True,
                         "closing_collection_recorded": True, "closing_release_basis": None},
    # The documented route records the failure receipt's stage and digest in its release basis.
    "failed-abandoned": {**_FAILED, "close_mode": "abandoned", "closing_triage_recorded": False,
                         "closing_collection_recorded": False,
                         "closing_release_basis": {"failure_stage": "inputs", "session_entries": ["collections", "triage"]}},
}


@pytest.mark.parametrize("case", sorted(FAILED_CLOSE))
def test_custodial_core_close_over_failed_preparation(checkout, tmp_path, case):
    extra_inputs, abandon = FAILED_CLOSE[case]
    ident = checkout.meta["audit_id"]
    target = _commit_paths(checkout, TREES["case-collision"][0])
    checkout.meta["target_commit"] = target
    checkout.meta["input_files"] = ["input.txt", *extra_inputs]
    revision = checkout.prompt_commit()
    prepared, prepare_refusal = _attempt(prepare, checkout.ws, revision)
    session = Path(prepared["session"]) if prepared else support.session_path(checkout, ident)
    record = support.read_json(session / "session.json")
    worktree, uuid, common = Path(record["worktree"]), record["session_uuid"], Path(record["common_dir"])
    failure = session / "PREPARE-ERROR.json"
    prepare_error = support.read_json(failure) if failure.exists() else None
    if prepared:
        (worktree / checkout.meta["report_path"]).write_text("A partial report.\n", encoding="utf-8")
    collected, collect_refusal = _attempt(collector.collect, checkout.ws, ident, auditor_stopped="finished")
    disposition, triage_refusal = (None, None)
    if collected:
        disposition, triage_refusal = _attempt(triage, checkout.ws, ident, collection=collected["collection"],
                                               response=support.response_for(collected), actor="fixture manager")
    view, status_refusal = _attempt(status, checkout.ws, ident)
    plan = close_plan(checkout.ws, ident, abandon=abandon)
    result, close_refusal = _attempt(close, checkout.ws, ident, actor="fixture manager", abandon=abandon,
                                     reason="comparison abandon of the fixture" if abandon else None)
    closing, closed = _closing_records(result)
    refs = git(checkout.repo, "for-each-ref", "--format=%(refname)",
               f"refs/stewart/sessions/{uuid}/").stdout.decode().split()
    _, reuse_refusal = _attempt(require_fresh_audit_id, str(common), checkout.ws, ident)
    view_after, status_after_refusal = _attempt(status, checkout.ws, ident)
    _save(tmp_path, "01-prepare", prepared if prepared else {"refusal": prepare_refusal})
    if collected:
        _save(tmp_path, "02-collection", collected)
    if disposition:
        _save(tmp_path, "04-triage", disposition)
    _save(tmp_path, "05-status", view if view else {"refusal": status_refusal})
    _save(tmp_path, "06-close-plan", plan)
    _save(tmp_path, "08-close", {"result": result, "refusal": close_refusal, "closing": closing, "closed": closed})
    _save(tmp_path, "11-status-after-close", view_after if view_after else {"refusal": status_after_refusal})
    observed = None if closing is None else closing["observed"]
    summary = {
        "case": case, "abandon": abandon,
        "prepare_refusal": None if prepare_refusal is None else [prepare_refusal["reason"], prepare_refusal["exit_code"]],
        "prepare_failure": None if prepare_error is None else [prepare_error["reason"], prepare_error["stage"]],
        "collect_refusal": collect_refusal,
        "collection_gaps": None if collected is None else sorted(gap["id"] for gap in collected["gaps"]),
        "triage_refusal": triage_refusal,
        "status_stage": None if view is None else view.get("stage"),
        "status_preparation_state": None if view is None else view["preparation"].get("state"),
        "status_attention": _attention(view),
        "status_next_actions": _actions(view),
        "close_plan_refusal": _refusal(plan),
        "close_refusal": close_refusal,
        "close_result": _close_result(result),
        "closing_acknowledged": None if closing is None else closing["acknowledged"],
        "closing_observed": None if observed is None else {
            key: observed.get(key) for key in ("stage", "problems", "triage", "collection", "checkout",
                                               "release_basis", "discarded")},
        "closing_attributed": None if closing is None else closing["attributed"],
        "closing_mentions_prepare_error": None if closing is None else "PREPARE-ERROR" in json.dumps(closing),
        "closing_mentions_failure_reason": None if closing is None else "input_mismatch" in json.dumps(closing),
        "closed_leftovers": None if closed is None else closed["leftovers"],
        "after_close": {"worktree_exists": worktree.exists(), "session_exists": session.exists(),
                        "session_refs": refs,
                        "registry_row_exists": (common / "stewart" / "worktree-roles" / f"{uuid}.json").exists()},
        "audit_id_reuse_refusal": None if reuse_refusal is None else [reuse_refusal["reason"], reuse_refusal["exit_code"]],
        "status_after_close": None if view_after is None else {"stage": view_after.get("stage"),
                                                               "exit_code": view_after.get("exit_code")},
        "status_after_close_refusal": status_after_refusal,
    }
    _save(tmp_path, "09-summary", summary)
    comparison = _comparison_six(summary)
    _save(tmp_path, "10-comparison", comparison)

    # Firing controls: the failed cases fail preparation as the collision fixture did; the prepared case closes.
    if case == "prepared-concluded":
        assert prepare_refusal is None and close_refusal is None and result["closed"] is not None
    else:
        assert prepare_refusal["reason"] == "prepare_failed"
        assert summary["prepare_failure"] == ["input_mismatch", "inputs"]
    # Observed in comparisons-03 and asserted from comparisons-04 on.
    assert comparison == OBSERVED_CLOSES[case]
