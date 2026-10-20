"""Hardened Git invocation for custody work.

Hooks, external diff drivers and the file-system monitor are disabled so that
preparing or inspecting a checkout never executes code from it. Inherited Git
redirections are dropped so the checkout under ``cwd`` is the one addressed.
Nothing here derives a checkout root from this file's location.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import select
import subprocess
import tempfile
import time

from stewart._bootstrap import StewartError

COMMIT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def _invocation(repo: Path, *args: str) -> dict:
    """Share the hardened invocation between bounded commands and transactions."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        env.pop(key, None)
    return {"args": ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args],
            "cwd": repo, "env": env}


def tree_entries(repo: Path, commit: str, *options: str) -> list[tuple[str, str, str]]:
    """Every entry of a commit's tree, recursively, as (mode, object ID, path); paths verbatim.

    ``options`` are Git's global options, such as a verified ``--git-dir``.
    """
    entries = []
    for record in git(repo, *options, "ls-tree", "-r", "-z", "--full-tree", commit).stdout.split(b"\0"):
        if record:
            meta, _, path = record.partition(b"\t")
            mode, _, rest = meta.partition(b" ")
            entries.append((mode.decode("ascii"), rest.partition(b" ")[2].decode("ascii"), os.fsdecode(path)))
    return entries


def gitlinks(repo: Path, commit: str) -> list[dict]:
    """The commit's submodule entries (mode 160000): Git lists nothing below these paths in a checkout."""
    return [{"path": path, "commit": oid} for mode, oid, path in tree_entries(repo, commit) if mode == "160000"]


def git(repo: Path, *args: str, check: bool = True, timeout: int = 120,
        input: bytes | None = None) -> subprocess.CompletedProcess:
    """Run one Git command in ``repo`` with hooks and redirections neutralized."""
    result = subprocess.run(
        **_invocation(repo, *args), capture_output=True, timeout=timeout, input=input,
    )
    if check and result.returncode:
        raise StewartError(
            f"git {args[0]} failed: {os.fsdecode(result.stderr).strip()}", reason="git_failed",
        )
    return result


def create_refs(repo: Path, refs: dict[str, str], *, timeout: float = 120) -> None:
    """Create direct refs together, rejecting symbolic names while Git holds locks.

    Some Git versions accept a dangling symbolic ref as absent for ``create``
    even with ``no-deref``. Inspect the original names after ``prepare`` has
    locked every update, then commit only if none is symbolic. Git writers
    cannot substitute a ref between that inspection and commit. Raw writes to
    manager-owned Git administration remain outside the custody boundary.
    """
    if not refs or any(not ref.startswith("refs/") or any(c.isspace() or c == "\0" for c in ref)
                       or COMMIT_ID.fullmatch(commit) is None for ref, commit in refs.items()):
        raise StewartError("ref creation requires full ref names and commit identities", reason="git_ref_transaction")
    commands = ["start"]
    for ref, commit in refs.items():
        commands.extend(("option no-deref", f"create {ref} {commit}"))
    commands.extend(("prepare", ""))
    deadline = time.monotonic() + timeout
    with tempfile.TemporaryFile() as errors, subprocess.Popen(
            **_invocation(repo, "update-ref", "--stdin"),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors) as process:
        try:
            process.stdin.write("\n".join(commands).encode())
            process.stdin.flush()
            expected = b"start: ok\nprepare: ok\n"
            observed = b""
            while len(observed) < len(expected):
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([process.stdout], [], [], max(0, remaining))[0]:
                    raise TimeoutError("timed out waiting for Git to lock the ref transaction")
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                observed += chunk
            if observed != expected:
                raise ValueError(f"Git did not prepare the complete transaction: {observed!r}")
            for ref in refs:
                alias = git(repo, "symbolic-ref", "--quiet", ref, check=False,
                            timeout=max(0.1, deadline - time.monotonic()))
                if alias.returncode != 1:
                    raise ValueError(f"ref is symbolic or could not be inspected while locked: {ref}")
            output, _ = process.communicate(b"commit\n", timeout=max(0.1, deadline - time.monotonic()))
            if process.returncode or output != b"commit: ok\n":
                raise ValueError(f"Git did not commit the complete transaction: {output!r}")
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            errors.seek(0)
            detail = os.fsdecode(errors.read()).strip()
            raise StewartError(f"cannot create direct refs: {exc}; {detail}", reason="git_ref_transaction") from exc
        finally:
            if process.poll() is None:
                # Closing a transaction without commit aborts it. Ask explicitly
                # so ordinary refusals release locks; a stuck Git may leave locks
                # after termination, which subsequent operations must preserve.
                try:
                    process.communicate(b"abort\n", timeout=5)
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    process.kill()
                    process.communicate()


def git_text(repo: Path, *args: str) -> str:
    return os.fsdecode(git(repo, *args).stdout).strip()


def resolve_commit(repo: Path, value: str, *, exact: bool = True) -> str:
    """Resolve a full commit ID (or ``HEAD`` when selecting) to its verified identity."""
    if not isinstance(value, str) or not (COMMIT_ID.fullmatch(value) or (not exact and value == "HEAD")):
        raise StewartError(
            "use a full commit ID (or HEAD when selecting a revision)", reason="commit_id",
        )
    resolved = git_text(repo, "rev-parse", "--verify", f"{value}^{{commit}}")
    if exact and resolved != value:
        raise StewartError(f"not an exact commit ID: {value}", reason="commit_id")
    return resolved
