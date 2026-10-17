"""Distribution-local byte contracts and explicit-root display paths.

These small operations are intentionally independent of the containing project.
Receipt serialization includes a trailing newline; canonical identity JSON does
not. Neither operation parses control JSON or discovers a repository. File bytes
must come from the verified descriptor readers in ``_bootstrap``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    """SHA-256 of exactly the supplied bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """SHA-256 of UTF-8 text, with no newline or normalization added."""
    return sha256_bytes(text.encode("utf-8"))


def canonical_json(value: Any) -> str:
    """Compact sorted ASCII JSON used in existing content identities."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_canonical_json(value: Any) -> str:
    """Digest the compact encoding, not the pretty receipt encoding."""
    return sha256_text(canonical_json(value))


def receipt_json_bytes(value: Any) -> bytes:
    """Deterministic plain JSON bytes for the exclusive receipt publisher."""
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def require_rel(value: str | Path) -> str:
    """Reject absolute paths and parent traversal; custody adds stricter rules."""
    parsed = Path(value)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError(f"path must be repo-relative: {value}")
    return str(value)


def rel(value: str | Path, repo_root: Path) -> str:
    """Display an explicit-root relative path, preserving external spellings.

    This is presentation only: it is not a custody-path authorization check.
    Absolute paths are not resolved, so external aliases keep their spelling.
    """
    root = repo_root if repo_root.is_absolute() else repo_root.resolve()
    location = Path(value)
    if not location.is_absolute():
        location = (root / location).resolve()
    return str(location.relative_to(root)) if location.is_relative_to(root) else str(location)
