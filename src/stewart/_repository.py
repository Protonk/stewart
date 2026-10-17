"""Explicit Git worktree selection, auditor roles, and durable commit refs.

Git administration is manager-owned. A lifetime marker distinguishes linked
worktrees even after a move or reuse of an old administrative pathname. Neither
the marker nor its retained registry row defends against someone who can rewrite
Git administration.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import uuid

from stewart._bootstrap import StewartError, open_directory, read_regular
from stewart._git import COMMIT_ID, create_refs, git, git_text, resolve_commit
from stewart._json import loads_control

ROLE_SCHEMA = "stewart.worktree-role/2"
ROLE_MARKER = "stewart-auditor.json"
LOCK_PREFIX = "stewart auditor "
RETENTION_SCHEMA = "stewart.commit-retention/1"
PRIVATE_ROOTS = (".scratch/stewart", ".scratch/stewart-runtimes")


def checkout_identity(repo: Path) -> dict:
    """Require exactly an explicitly selected non-bare Git worktree root."""
    root = Path(repo).resolve()
    try:
        bare = git(root, "rev-parse", "--is-bare-repository", check=False)
        if bare.returncode or bare.stdout.strip() != b"false":
            raise StewartError("repository must be a non-bare Git working tree", reason="repository_root")
        actual = Path(git_text(root, "rev-parse", "--show-toplevel")).resolve()
        if actual != root:
            raise StewartError(f"select the worktree root explicitly: {actual}; subdirectories are refused",
                               reason="repository_root")
        return {"root": str(root),
                "git_admin": str(Path(git_text(root, "rev-parse", "--absolute-git-dir")).resolve()),
                "common_dir": str(Path(git_text(root, "rev-parse", "--path-format=absolute",
                                                "--git-common-dir")).resolve())}
    except OSError as exc:
        raise StewartError(f"cannot inspect the selected Git worktree: {exc}", reason="repository_root") from exc


def _reserved_auditor_root(root: Path) -> bool:
    parts = root.parts
    return any(parts[i:i + 2] == (".scratch", "stewart") and parts[i + 4] == "worktree"
               for i in range(len(parts) - 4))


def _registry(common: str) -> Path:
    return Path(common) / "stewart/worktree-roles"


def _role_records(common: str) -> list[dict]:
    """Read the complete registry through pinned no-follow descriptors."""
    root = _registry(common)
    records = []
    try:
        with open_directory(root) as directory:
            for name in sorted(os.listdir(directory)):
                info, data = read_regular(Path(name), dir_fd=directory)
                if data is None:
                    raise ValueError(f"unreadable role entry {name}: {info}")
                value = loads_control(data)
                fields = {"schema_version", "role", "role_uuid", "common_dir", "git_admin", "worktree",
                          "session", "session_sha256", "session_uuid"}
                if not isinstance(value, dict) or set(value) != fields:
                    raise ValueError(f"invalid role entry {name}")
                if value["schema_version"] != ROLE_SCHEMA or value["role"] != "auditor" or value["common_dir"] != common:
                    raise ValueError(f"conflicting role entry {name}")
                for key in ("common_dir", "git_admin", "worktree", "session"):
                    path = value[key]
                    if (not isinstance(path, str) or not Path(path).is_absolute()
                            or Path(path).as_posix() != path or ".." in Path(path).parts):
                        raise ValueError(f"invalid {key} in {name}")
                if (name != session_uuid(value["role_uuid"]) + ".json"
                        or not isinstance(value["session_sha256"], str)
                        or re.fullmatch(r"[0-9a-f]{64}", value["session_sha256"]) is None):
                    raise ValueError(f"invalid role identity in {name}")
                if value["session_uuid"] is not None:
                    session_uuid(value["session_uuid"])
                records.append(value)
    except FileNotFoundError:
        return []
    except (OSError, ValueError, RecursionError) as exc:
        raise StewartError(f"worktree-role registry cannot establish a role: {exc}",
                           reason="worktree_role_registry", retained=[str(root)],
                           next_steps=["preserve the registry and resolve its conflicting or unreadable records"]) from exc
    return records


def _marker(identity: dict) -> dict | None:
    """A worktree's administrative marker has that worktree's lifetime.

    Git may reuse an administrative directory's name after removal. Its marker
    is removed with the directory, so historical registry rows cannot classify
    a later checkout that happens to receive the same administrative pathname.
    """
    location = Path(identity["git_admin"]) / ROLE_MARKER
    info, data = read_regular(location)
    if info["kind"] == "missing":
        return None
    try:
        if data is None:
            raise ValueError(f"marker is not a readable regular file: {info}")
        value = loads_control(data)
        if (not isinstance(value, dict) or set(value) != {"schema_version", "role_uuid"}
                or value["schema_version"] != ROLE_SCHEMA):
            raise ValueError("unsupported marker schema")
        session_uuid(value["role_uuid"])
        return value
    except (ValueError, RecursionError) as exc:
        raise StewartError(f"worktree role marker cannot establish a role: {exc}",
                           reason="worktree_role_registry", retained=[str(location)]) from exc


def custody_roots(repo: Path, common: str) -> list[str]:
    """Snapshot Git's checkout roots and retained session locations for a scope.

    Registry paths keep removed or moved checkouts' private sessions excluded.
    This is operation-time discovery, not a claim about future worktree moves.
    """
    roots = {str(repo)}
    for field in git(repo, "worktree", "list", "--porcelain", "-z").stdout.split(b"\0"):
        if field.startswith(b"worktree "):
            roots.add(os.fsdecode(field[len(b"worktree "):]))
    for row in _role_records(common):
        roots.update((row["session"], row["worktree"]))
    return sorted(roots)


def maintainer(repo: Path) -> dict:
    """Any branch or detached HEAD is valid; a known auditor role is not."""
    identity = checkout_identity(repo)
    root = Path(identity["root"])
    if _reserved_auditor_root(root):
        raise StewartError("the selected root is in reserved auditor worktree storage",
                           reason="auditor_worktree", next_steps=["select the maintainer working tree explicitly"])
    rows = _role_records(identity["common_dir"])
    marker = _marker(identity)
    if marker is not None:
        matches = [row for row in rows if row["role_uuid"] == marker["role_uuid"]]
        if matches and matches[0]["git_admin"] != identity["git_admin"]:
            raise StewartError("auditor marker and registry administration disagree", reason="worktree_role_registry")
        raise StewartError("the selected worktree carries an auditor role marker",
                           reason="auditor_worktree", retained=[row["session"] for row in matches],
                           next_steps=["select a maintainer worktree; moving an auditor checkout does not change its role"])
    # Git creates this lock as part of worktree add. It covers a failure between
    # creation and exclusive marker/registry publication. Successful preparation
    # unlocks only after the persistent marker has been published.
    info, lock = read_regular(Path(identity["git_admin"]) / "locked")
    if info["kind"] != "missing" and lock is None:
        raise StewartError("worktree lock is unreadable", reason="worktree_role_registry")
    if lock is not None and lock.startswith(LOCK_PREFIX.encode()):
        raise StewartError("the selected worktree has an unfinished auditor registration",
                           reason="auditor_worktree", next_steps=["preserve the failed preparation; select its maintainer"])
    return identity


def _prospective_role(manager: dict, worktree: Path, session: Path) -> dict:
    """Validate a registration without publishing either its marker or row."""
    auditor = checkout_identity(worktree)
    if auditor["common_dir"] != manager["common_dir"] or auditor["git_admin"] == manager["git_admin"]:
        raise StewartError("auditor must be a separate linked worktree of this repository", reason="worktree_role_identity")
    info, data = read_regular(session / "session.json")
    if data is None:
        raise StewartError("session cannot be read for role registration", reason="worktree_role_identity")
    record = loads_control(data)
    if (not isinstance(record, dict) or worktree != session / "worktree"
            or record.get("repo") != manager["root"] or record.get("common_dir") != manager["common_dir"]
            or record.get("worktree") != auditor["root"]):
        raise StewartError("session and observed worktree disagree", reason="worktree_role_identity")
    if (git_text(worktree, "branch", "--show-current")
            or git_text(worktree, "rev-parse", "HEAD") != record.get("prompt_commit")):
        raise StewartError("auditor registration requires its detached prompt checkout", reason="worktree_role_identity")
    marker = _marker(auditor)
    role_uuid = (marker["role_uuid"] if marker is not None else record.get("session_uuid") or str(uuid.uuid4()))
    session_uuid(role_uuid)
    if record.get("session_uuid") is not None and role_uuid != record["session_uuid"]:
        raise StewartError("auditor marker differs from its session UUID", reason="worktree_role_conflict")
    role = {"schema_version": ROLE_SCHEMA, "role": "auditor", "role_uuid": role_uuid,
            "common_dir": manager["common_dir"],
            "git_admin": auditor["git_admin"], "worktree": auditor["root"], "session": str(session),
            "session_sha256": info["sha256"], "session_uuid": record.get("session_uuid")}
    for existing in _role_records(manager["common_dir"]):
        if existing["role_uuid"] == role_uuid:
            if existing == role:
                return existing
            raise StewartError("existing auditor role differs; preserve it", reason="worktree_role_conflict",
                               retained=[existing["session"], str(_registry(manager["common_dir"]) / (role_uuid + ".json"))])
    return role


def _publish_role(role: dict) -> dict:
    """Publish the lifetime marker first; a later row failure cannot erase role."""
    from stewart.session import write_receipt

    root = _registry(role["common_dir"])
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = root / (role["role_uuid"] + ".json")
    marker = {"schema_version": ROLE_SCHEMA, "role_uuid": role["role_uuid"]}
    try:
        existing_marker = _marker(role)
        if existing_marker is None:
            write_receipt(Path(role["git_admin"]) / ROLE_MARKER, marker)
        elif existing_marker != marker:
            raise StewartError("auditor marker changed before publication", reason="worktree_role_conflict")
        existing = [row for row in _role_records(role["common_dir"]) if row["role_uuid"] == role["role_uuid"]]
        if not existing:
            write_receipt(destination, role)
        elif existing != [role]:
            raise StewartError("auditor role changed before publication", reason="worktree_role_conflict",
                               retained=[existing[0]["session"], str(destination)])
    except FileExistsError as exc:
        raise StewartError("role registration raced another writer; inspect the retained record",
                           reason="worktree_role_conflict", retained=[str(destination)]) from exc
    return role


def register_auditor(repo: Path, worktree: Path, session: Path) -> dict:
    """Publish a role exclusively before handoff, binding the session's bytes."""
    return _publish_role(_prospective_role(maintainer(repo), worktree, session))


def _whole_directory_rule(repo: Path, root: str) -> bool:
    """Require a literal rule for this directory or an ancestor.

    A trailing-slash check alone also matches a children glob, whose negated
    descendants can still be staged. Refuse such partial rules rather than
    trying to prove all possible future filenames with a few fixed probes.
    """
    result = git(repo, "check-ignore", "--verbose", "-z", "--no-index", "--stdin",
                 input=(root + "/\0").encode(), check=False)
    fields = result.stdout.split(b"\0")
    if result.returncode or len(fields) != 5 or fields[-1] != b"":
        return False
    origin, _, pattern, _ = map(os.fsdecode, fields[:-1])
    if not pattern or any(c in pattern for c in "!*?[\\"):
        return False
    literal = pattern.removeprefix("/").removesuffix("/")
    parts = tuple(literal.split("/"))
    if any(part in ("", ".", "..") for part in parts):
        return False
    origin_path = Path(origin)
    if not origin_path.is_absolute():
        origin_path = repo / origin_path
    scope = ()
    if origin_path.name == ".gitignore":
        try:
            scope = origin_path.parent.relative_to(repo).parts
        except ValueError:
            pass  # Global excludes are relative to the repository root.
    path = Path(root).parts
    if path[:len(scope)] != scope:
        return False
    remainder = path[len(scope):]
    return (remainder[:len(parts)] == parts if pattern.startswith("/") or "/" in literal
            else literal in remainder)


def require_private_exclusions(repo: Path) -> None:
    """Private custody/runtime directories need whole-directory Git exclusions."""
    for root in PRIVATE_ROOTS:
        if git(repo, "ls-files", "-z", "--", root).stdout:
            raise StewartError(f"private storage contains tracked paths: {root}", reason="private_storage_tracked")
        if not _whole_directory_rule(repo, root):
            raise StewartError(f"private storage needs a literal whole-directory Git exclusion: {root}",
                               reason="private_storage_not_ignored",
                               next_steps=["add /.scratch/stewart/ and /.scratch/stewart-runtimes/ to "
                                           "the project's ignore rules or this repository's info/exclude; "
                                           "child globs are insufficient. Stewart never changes or stages rules automatically"])


def session_uuid(value: object) -> str:
    """Canonical UUID identity shared by retention refs and supplied runtimes."""
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError("noncanonical UUID")
    except (ValueError, AttributeError) as exc:
        raise StewartError("session requires its canonical UUID", reason="session_identity") from exc
    return value


def retention_for(ident: str, prompt: str, target: str, base: str | None) -> dict:
    session_uuid(ident)
    commits = {"prompt": prompt, "target": target, **({"base": base} if base is not None else {})}
    if any(not isinstance(commit, str) or COMMIT_ID.fullmatch(commit) is None for commit in commits.values()):
        raise StewartError("retention requires full recorded commit identities", reason="session_retention")
    return {"schema_version": RETENTION_SCHEMA,
            "refs": {name: {"ref": f"refs/stewart/sessions/{ident}/{name}", "commit": commit}
                     for name, commit in commits.items()}}


def retain_commits(repo: Path, retention: dict) -> None:
    """Create all session refs atomically; never replace an existing ref."""
    for entry in retention["refs"].values():
        resolve_commit(repo, entry["commit"])
    try:
        create_refs(repo, {entry["ref"]: entry["commit"] for entry in retention["refs"].values()})
    except StewartError as exc:
        raise StewartError(f"cannot create session retention refs: {exc}", reason="session_retention",
                           next_steps=["preserve existing refs and locks; use a fresh assignment and UUID"]) from exc


def verify_retention(repo: Path, record: dict) -> dict:
    """Recover only while the recorded refs still name exactly their commits."""
    expected = retention_for(record.get("session_uuid"), record.get("prompt_commit"), record.get("target_commit"),
                             record["assignment"].get("base_commit"))
    if record.get("retention") != expected:
        raise StewartError("session retention names or commits disagree with its identities", reason="session_retention")
    for entry in expected["refs"].values():
        alias = git(repo, "symbolic-ref", "--quiet", entry["ref"], check=False)
        if alias.returncode == 0:
            raise StewartError(f"session retention must remain a direct ref: {entry['ref']}",
                               reason="session_retention")
        found = git(repo, "rev-parse", "--verify", entry["ref"], check=False)
        if found.returncode or os.fsdecode(found.stdout).strip() != entry["commit"]:
            raise StewartError(f"session retention ref is absent or changed: {entry['ref']}", reason="session_retention",
                               next_steps=["preserve the session and restore its recorded commit/ref identity; do not relabel evidence"])
        try:
            resolve_commit(repo, entry["commit"])
        except StewartError as exc:
            raise StewartError(f"retained session commit is unavailable: {entry['commit']}",
                               reason="session_retention") from exc
    return expected
