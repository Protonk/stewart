"""Whether a checkout's bytes are preserved: in a verified collection archive or in the prompt commit.

Before close removes a checkout, a concluded close requires its triaged
collection to be a verified capture (``require_capture``), and an abandon
counts as collected only what a verified archive holds (``archived``). Both
decide from bytes, never from Git's report of what changed: index flags,
filters and configuration can steer that report, so an entry is preserved only
when an archive or the prompt commit holds the same kind and content at its
path. Entries without content (FIFOs, sockets, devices, and directories that
were traversed) need nothing preserved and are never read. An entry whose
content was not observed (unreadable or replaced, a directory that was not
traversed, an unknown kind) is unresolved and never counts as preserved.
"""
from __future__ import annotations

import os
from pathlib import Path

from stewart import _util as _hash
from stewart._bootstrap import StewartError
from stewart.captured import archive_identities, entry_identity as identity

#: Entry kinds that hold no bytes: the inventory records them, nothing reads them, and no archive needs them.
CONTENTLESS = frozenset({"fifo", "socket", "chardev", "blockdev"})

_PROMPT_KINDS = {"100644": "file", "100755": "file", "120000": "symlink"}


def classify(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Inventory entries with content, and those whose content is unresolved; contentless entries are in neither."""
    content, unresolved = [], []
    for entry in entries:
        if identity(entry) is not None:
            content.append(entry)
        elif not (entry.get("kind") in CONTENTLESS or entry.get("kind") == "directory" and entry.get("traversed") is True):
            unresolved.append(entry)
    return content, unresolved


def _key(rel: str) -> str:
    from stewart.collect import _spelling
    return _spelling(rel)


def prompt_identities(repo: Path, commit: str, paths: set[str]) -> dict[str, tuple[str, str]]:
    """The prompt commit's files and links at ``paths`` (spelled as ``_key`` spells them), as (kind, content).

    Blobs are read from Git's objects with replacement objects disabled and no
    filter applied, and Stewart hashes their bytes itself.
    """
    from stewart._git import git, tree_entries
    wanted = {}
    for mode, oid, path in tree_entries(repo, commit, "--no-replace-objects"):
        key = _key(path)
        if mode in _PROMPT_KINDS and key in paths:
            wanted[key] = (_PROMPT_KINDS[mode], oid)
    oids = sorted({oid for _, oid in wanted.values()})
    blobs: dict[str, bytes] = {}
    if oids:
        output = git(repo, "--no-replace-objects", "cat-file", "--batch",
                     input="".join(f"{oid}\n" for oid in oids).encode("ascii")).stdout
        offset = 0
        for oid in oids:
            end = output.find(b"\n", offset)
            header = output[offset:end].split(b" ")
            if end < 0 or len(header) != 3 or header[0] != oid.encode("ascii") or header[1] != b"blob":
                raise StewartError(f"the prompt commit's blob {oid} cannot be read", reason="git_failed")
            start = end + 1
            blobs[oid] = output[start:start + int(header[2])]
            offset = start + int(header[2]) + 1
    return {key: (kind, _hash.sha256_bytes(blobs[oid]) if kind == "file" else os.fsdecode(blobs[oid]))
            for key, (kind, oid) in wanted.items()}


def unpreserved(entries: list[dict], held: dict[str, set], repo: Path, commit: str, *,
                exempt: dict[str, tuple[str, str]] | None = None) -> tuple[list[dict], list[dict]]:
    """Entries whose content neither ``held`` (identities by path) nor the prompt commit preserves; unresolved entries.

    ``exempt`` names identities preserved elsewhere, such as preparation's own
    pinned copies; an exempt path with other content is not exempt.
    """
    content, unresolved = classify(entries)
    exempt = exempt or {}
    pending = [entry for entry in content if identity(entry) not in held.get(_key(entry["path"]), ())
               and exempt.get(_key(entry["path"])) != identity(entry)]
    prompt = prompt_identities(repo, commit, {_key(entry["path"]) for entry in pending}) if pending else {}
    return [entry for entry in pending if prompt.get(_key(entry["path"])) != identity(entry)], unresolved


def _refuse(reason: str, name: str, why: str, retained: list[str]) -> StewartError:
    lead = {"capture_not_recorded": f"collection {name} recorded no full capture",
            "capture_unverified": f"collection {name}'s capture is unavailable or fails verification",
            "capture_uncovered": f"collection {name} does not capture every byte its checkout held"}[reason]
    return StewartError(f"{lead}: {why}", reason=reason, retained=retained,
                        next_steps=["preserve this collection as it is; repair what this names, stop writers, "
                                    "collect again and triage that collection",
                                    "or close --abandon --reason TEXT, adding --discard-uncollected to discard "
                                    "what no verified capture holds"])


def archived(directory: Path, receipt: dict, *, retained: list[str] = ()) -> dict[str, tuple[str, str]]:
    """What a collection's archive verifiably holds, as identities by path; refuses unless its claim verifies.

    The claim is a completed Git discovery and a recorded archive digest, with
    no movement recorded anywhere in the receipt. The bytes must match that
    digest, and the members must be exactly the entries the receipt says were
    archived, with their kinds and contents. A movement collection's archive
    is preserved evidence and is never promoted.
    """
    name, retained = directory.name, [str(directory), *retained]
    if receipt.get("git_discovery") != "complete":
        raise _refuse("capture_not_recorded", name, "Git discovery did not complete, so archive coverage is unknown",
                      retained)
    summary = receipt.get("inventory") if isinstance(receipt.get("inventory"), dict) else {}
    errors = receipt.get("errors") if isinstance(receipt.get("errors"), list) else []
    moved = summary.get("movement") is True or any(
        isinstance(error, dict) and error.get("reason") == "movement" for error in errors)
    if moved or not isinstance(summary.get("movement"), bool) or not isinstance(receipt.get("archive_sha256"), str):
        raise _refuse("capture_not_recorded", name,
                      "the checkout changed during collection; its archive is preserved evidence, not a capture"
                      if moved else "the collection recorded no verified archive", retained)
    try:
        found = archive_identities(directory, receipt)
    except StewartError as exc:
        raise _refuse("capture_unverified", name, str(exc), retained) from None
    return {_key(rel): value for rel, value in found.items()}


def require_capture(repo: Path, directory: Path, receipt: dict, *, retained: list[str] = ()) -> None:
    """Refuse unless a collection is a verified capture of the checkout it recorded.

    Its archive must verify (``archived``), and every entry of its recorded
    inventory must be contentless or held, with the same kind and content, by
    that archive or the prompt commit. Triage and reviewed custody gaps do not
    discharge this; it is a property of the captured bytes.
    """
    from stewart.session import capture_receipt
    held = archived(directory, receipt, retained=retained)
    name, retained = directory.name, [str(directory), *retained]
    summary = receipt.get("inventory") if isinstance(receipt.get("inventory"), dict) else {}
    try:
        record, digest = capture_receipt(directory / "inventory.json", what="collection inventory")
    except StewartError as exc:
        raise _refuse("capture_unverified", name, str(exc), retained) from None
    entries = record.get("entries")
    if digest != summary.get("sha256") or not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise _refuse("capture_unverified", name, "its inventory record differs from the receipt", retained)
    prompt = receipt.get("prompt_commit")
    try:
        missing, unresolved = unpreserved(entries, {key: {value} for key, value in held.items()}, repo, prompt)
    except StewartError as exc:
        raise _refuse("capture_unverified", name, f"the prompt commit cannot be compared: {exc}", retained) from None
    if missing or unresolved:
        described = [f"{entry['path']} ({entry.get('kind')}, content not observed)" for entry in unresolved]
        described += [f"{entry['path']} ({entry['kind']} in neither the archive nor the prompt commit)"
                      for entry in missing]
        raise _refuse("capture_uncovered", name, "; ".join(described[:10])
                       + (f"; and {len(described) - 10} more" if len(described) > 10 else ""), retained)
