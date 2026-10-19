"""Explicit Git worktree selection, auditor roles, private storage and durable commit refs.

Git administration is manager-owned. Private custody lives under the Git
common directory (``<common>/stewart``), which ``git clean`` never touches and
which every linked worktree shares, so sessions are addressed repo-wide.
Auditor-facing checkouts live in a per-user checkout home outside every
working tree, one UUID-named directory per session. A lifetime marker
distinguishes linked worktrees even after a move or reuse of an old
administrative pathname. Neither the marker nor its retained registry row
defends against someone who can rewrite Git administration.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import uuid

from stewart._bootstrap import StewartError, open_directory, read_regular
from stewart._git import COMMIT_ID, create_refs, git, git_text, resolve_commit
from stewart._json import loads_control
from stewart._util import sha256_text
from stewart.workspace import contained

ROLE_SCHEMA = "stewart.worktree-role/2"
ROLE_MARKER = "stewart-auditor.json"
#: Git lock reasons. Preparation locks a new checkout under the first while it
#: registers the role; a registered auditor checkout then keeps the second for
#: its lifetime, so ordinary worktree cleanup refuses to remove or move it.
REGISTRATION_LOCK = "stewart auditor registration "
LIFETIME_LOCK = "stewart auditor checkout "
RETENTION_SCHEMA = "stewart.commit-retention/1"
#: Private custody below the Git common directory.
STORAGE = "stewart"
SESSIONS = f"{STORAGE}/sessions"
#: Closing records of retired audits; Stewart never removes them.
CLOSED = f"{STORAGE}/closed"
#: The per-user checkout home used when ``prepare`` names none.
DEFAULT_CHECKOUT_HOME = ".local/state/stewart/checkouts"


def private_storage(common: str) -> Path:
    """``<common>/stewart``, created with mode 0700; a link there is refused."""
    root = Path(common) / STORAGE
    if root.is_symlink():
        raise StewartError(f"private storage cannot be a link: {root}", reason="path_symlink", retained=[str(root)])
    root.mkdir(mode=0o700, exist_ok=True)
    return root


def private_directories(root: Path, directory: Path) -> Path:
    """Create ``directory`` below an existing ``root`` with mode 0700, refusing links; return it."""
    rel = directory.relative_to(root)
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise StewartError(f"storage path cannot traverse a link: {current}", reason="path_symlink",
                               retained=[str(current)])
        current.mkdir(mode=0o700, exist_ok=True)
    return directory


def session_location(common: str, ws, ident: str) -> Path:
    """One session's private directory: repo-wide, by workspace slug and audit ID."""
    return contained(Path(common), f"{SESSIONS}/{ws.slug}/{ident}")


def workspace_sessions(common: str, ws) -> list[str]:
    """Audit IDs with a session directory for this workspace, in name order."""
    folder = Path(common) / SESSIONS / ws.slug
    if not folder.is_dir() or folder.is_symlink():
        return []
    return sorted(entry.name for entry in folder.iterdir() if entry.is_dir() and not entry.is_symlink())


def repo_key(common: str) -> str:
    """A readable repository name plus a digest of its common directory path."""
    path = Path(common)
    name = path.parent.name if path.name == ".git" else path.name
    return f"{name}-{sha256_text(str(path))[:12]}"


def resolve_checkout_home(selected: Path | None = None) -> Path:
    """The checkout home's path, checked for shape and links; nothing is created.

    The default is ``~/.local/state/stewart/checkouts``; no environment
    variable selects it.
    """
    home = Path(selected) if selected is not None else Path.home() / DEFAULT_CHECKOUT_HOME
    if not home.is_absolute() or ".." in home.parts or "\0" in str(home):
        raise StewartError(f"checkout home must be an absolute path: {home}", reason="checkout_home",
                           next_steps=["pass --checkout-home with an absolute, unlinked directory"])
    for part in [*reversed(home.parents), home]:
        if part.is_symlink():
            raise StewartError(f"checkout home cannot traverse a link: {part}", reason="checkout_home",
                               next_steps=["choose a checkout home whose every ancestor is a real directory"])
    return home


def checkout_home(selected: Path | None = None) -> Path:
    """The validated per-user checkout home: absolute, unlinked, private, created if absent.

    Missing directories are created with mode 0700; call this only after the
    overlap checks in ``require_separate_home`` pass.
    """
    home = resolve_checkout_home(selected)
    for part in [*reversed(home.parents), home]:
        if not part.exists():
            part.mkdir(mode=0o700)
    with open_directory(home) as descriptor:
        info = os.fstat(descriptor)
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise StewartError(f"checkout home must be private to the current user (mode 0700): {home}",
                           reason="checkout_home", retained=[str(home)],
                           next_steps=["choose a manager-owned directory with mode 0700"])
    return home


def require_separate_home(home: Path, *, repo: Path, worktrees: list[str], common: str, manager_home: Path,
                          prefix: Path) -> None:
    """The checkout home lies outside every working tree and every private or trusted root.

    Auditor checkouts are themselves working trees inside the home, so only a
    home inside a working tree, or the maintainer checkout inside the home,
    counts as overlap there.
    """
    nested = [(Path(root), "a working tree of this repository") for root in worktrees]
    if Path(repo) == home or Path(repo).is_relative_to(home):
        raise StewartError(f"the maintainer checkout {repo} lies inside the checkout home {home}",
                           reason="checkout_home", next_steps=["choose a checkout home outside the maintainer checkout"])
    for root, what in nested:
        if home == root or home.is_relative_to(root):
            raise StewartError(f"checkout home {home} lies inside {what}: {root}", reason="checkout_home",
                               next_steps=["choose a checkout home outside every working tree and private root"])
    for root, what in [(Path(common), "the Git common directory"), (Path(manager_home), "the manager home"),
                       (Path(prefix), "the interpreter prefix")]:
        if home == root or home.is_relative_to(root) or root.is_relative_to(home):
            raise StewartError(f"checkout home {home} overlaps {what}: {root}", reason="checkout_home",
                               next_steps=["choose a checkout home outside every working tree and private root"])


def audit_location(home: Path, common: str, session_identity: str) -> Path:
    """One session's checkout directory: its worktree, runtime and experiment homes."""
    return contained(Path(home), f"{repo_key(common)}/{session_identity}")


def worktree_roots(repo: Path) -> list[str]:
    """Every working tree Git lists for this repository."""
    roots = []
    for field in git(repo, "worktree", "list", "--porcelain", "-z").stdout.split(b"\0"):
        if field.startswith(b"worktree "):
            roots.append(os.fsdecode(field[len(b"worktree "):]))
    return roots


def read_denials(roots: list[str], keep: list[str]) -> list[str]:
    """Literal read denials that never cover a path the auditor is granted.

    In the qualified harness a broader ``denyRead`` wins over a nested
    ``allowRead`` (rehome step 0 qualification). A private root that contains
    a kept path, such as the Git common directory or an interpreter prefix in
    a project virtual environment, therefore cannot be denied whole: the
    auditor's Git or helpers would stop working. Such a root is replaced by its
    entries, descending along each path to a kept one, so everything else
    under it stays denied. Entries created later are not covered.

    An entry whose name holds pattern syntax cannot be denied literally, so
    preparation refuses rather than leave it readable.
    """
    targets = [Path(path) for path in keep]
    denied: set[str] = set()
    uncovered: list[str] = []
    for root in roots:
        path = Path(root)
        if any(target != path and target.is_relative_to(path) for target in targets):
            denied.update(_entries_beside(path, targets, uncovered))
        elif not any(path == target for target in targets):
            denied.add(root)
    if uncovered:
        raise StewartError("these private entries have names a literal read denial cannot express: "
                           + ", ".join(uncovered), reason="scope_uncovered", retained=uncovered,
                           next_steps=["rename or move them so their names hold none of * ? [ ] { } ( ) \\ "
                                       "or line breaks, then prepare; no session was created"])
    return sorted(denied)


def _entries_beside(root: Path, targets: list[Path], uncovered: list[str]) -> list[str]:
    found = []
    for name in sorted(os.listdir(root)):
        entry = root / name
        if any(entry == target for target in targets):
            continue
        if any(target.is_relative_to(entry) for target in targets):
            found.extend(_entries_beside(entry, targets, uncovered))
        elif any(c in name for c in "*?[]{}()\\\n\r"):
            uncovered.append(str(entry))
        else:
            found.append(str(entry))
    return found


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


def _inside_auditor_checkout(root: Path, rows: list[dict]) -> bool:
    """A backstop beside the marker and registry: the default home or a registered checkout directory."""
    homes = [Path.home() / DEFAULT_CHECKOUT_HOME, *(Path(row["worktree"]).parent for row in rows)]
    return any(root == home or root.is_relative_to(home) for home in homes)


def _registry(common: str) -> Path:
    return Path(common) / "stewart/worktree-roles"


_ROLE_FIELDS = {"schema_version", "role", "role_uuid", "common_dir", "git_admin", "worktree", "session",
                "session_sha256", "session_uuid"}


def _role_row(name: str, info: dict, data: bytes | None, common: str) -> dict:
    """Validate one registry row; ValueError names what makes it unusable."""
    if data is None:
        raise ValueError(f"unreadable role entry {name}: {info}")
    value = loads_control(data)
    if not isinstance(value, dict) or set(value) != _ROLE_FIELDS:
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
    return value


def _role_records(common: str) -> list[dict]:
    """Read the complete registry through pinned no-follow descriptors; any bad row refuses."""
    root = _registry(common)
    records = []
    try:
        with open_directory(root) as directory:
            for name in sorted(os.listdir(directory)):
                info, data = read_regular(Path(name), dir_fd=directory)
                records.append(_role_row(name, info, data, common))
    except FileNotFoundError:
        return []
    except (OSError, ValueError, RecursionError) as exc:
        raise StewartError(f"worktree-role registry cannot establish a role: {exc}",
                           reason="worktree_role_registry", retained=[str(root)],
                           next_steps=["preserve the registry and resolve its conflicting or unreadable records"]) from exc
    return records


def role_rows(common: str) -> tuple[list[dict], list[dict]]:
    """Every usable registry row, and a located diagnostic for each row that is not.

    Read-only views list an unsupported, invalid or unreadable row instead of
    refusing; mutations keep the all-or-nothing reader.
    """
    root = _registry(common)
    rows, problems = [], []
    try:
        with open_directory(root) as directory:
            for name in sorted(os.listdir(directory)):
                info, data = read_regular(Path(name), dir_fd=directory)
                try:
                    rows.append(_role_row(name, info, data, common))
                except (ValueError, RecursionError) as exc:
                    problems.append({"reason": "worktree_role_registry", "location": str(root / name),
                                     "message": str(exc)})
    except FileNotFoundError:
        pass
    except OSError as exc:
        problems.append({"reason": "worktree_role_registry", "location": str(root),
                         "message": f"the registry cannot be listed: {exc}"})
    return rows, problems


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
    from stewart.holdings import private_roots
    # Live managed and enrolled worktrees and directories hold manager work an auditor has no grant to read.
    roots = {str(repo), str(Path(common) / STORAGE), *worktree_roots(repo), *private_roots(common)}
    for row in _role_records(common):
        # A registered checkout's directory also holds its runtime and
        # experiment homes; none of another session's material is needed.
        roots.update((row["session"], row["worktree"], str(Path(row["worktree"]).parent)))
    return sorted(roots)


def maintainer(repo: Path) -> dict:
    """Any branch or detached HEAD is valid; a known auditor role is not."""
    identity = checkout_identity(repo)
    root = Path(identity["root"])
    rows = _role_records(identity["common_dir"])
    if _inside_auditor_checkout(root, rows):
        raise StewartError("the selected root is inside auditor checkout storage",
                           reason="auditor_worktree", next_steps=["select the maintainer working tree explicitly"])
    marker = _marker(identity)
    if marker is not None:
        matches = [row for row in rows if row["role_uuid"] == marker["role_uuid"]]
        if matches and matches[0]["git_admin"] != identity["git_admin"]:
            raise StewartError("auditor marker and registry administration disagree", reason="worktree_role_registry")
        raise StewartError("the selected worktree carries an auditor role marker",
                           reason="auditor_worktree", retained=[row["session"] for row in matches],
                           next_steps=["select a maintainer worktree; moving an auditor checkout does not change its role"])
    # Git creates the registration lock as part of worktree add. It covers a
    # failure between creation and exclusive marker/registry publication.
    # Successful preparation then replaces it with the lifetime lock.
    lock = worktree_lock(identity["git_admin"])
    if lock is not None and lock.startswith(REGISTRATION_LOCK):
        raise StewartError("the selected worktree has an unfinished auditor registration",
                           reason="auditor_worktree", next_steps=["preserve the failed preparation; select its maintainer"])
    if lock is not None and lock.startswith(LIFETIME_LOCK):
        raise StewartError("the selected worktree is a locked Stewart auditor checkout",
                           reason="auditor_worktree", next_steps=["select the maintainer working tree explicitly"])
    return identity


def observer(repo: Path) -> dict:
    """The exact maintainer root for read-only views, with registry rows that do not verify as diagnostics.

    Auditor checkouts are refused as for any manager operation. Unlike
    ``maintainer``, one unusable registry row does not hide the rest.
    """
    identity = checkout_identity(repo)
    root = Path(identity["root"])
    rows, problems = role_rows(identity["common_dir"])
    if _inside_auditor_checkout(root, rows):
        raise StewartError("the selected root is inside auditor checkout storage",
                           reason="auditor_worktree", next_steps=["select the maintainer working tree explicitly"])
    marker = _marker(identity)
    if marker is not None:
        raise StewartError("the selected worktree carries an auditor role marker", reason="auditor_worktree",
                           next_steps=["select a maintainer worktree; moving an auditor checkout does not change its role"])
    lock = worktree_lock(identity["git_admin"])
    if lock is not None and lock.startswith((REGISTRATION_LOCK, LIFETIME_LOCK)):
        raise StewartError("the selected worktree is a Stewart auditor checkout", reason="auditor_worktree",
                           next_steps=["select the maintainer working tree explicitly"])
    return {**identity, "rows": rows, "registry_problems": problems}


def registered_session(common: str, session: Path) -> None:
    """Refuse an audit ID whose registered session has lost its records.

    A registry row names every prepared session's directory. When the row
    remains but the directory is gone, the ID already has an evidence chain;
    preparing it again would put a second one under the same name.
    """
    rows = [row for row in _role_records(common) if row["session"] == str(session)]
    if rows:
        refs = [f"refs/stewart/sessions/{row['session_uuid']}" for row in rows if row["session_uuid"]]
        raise StewartError(
            f"this audit ID was prepared before and its session records are missing: {session}",
            reason="session_records_missing",
            retained=[str(_registry(common) / f"{row['role_uuid']}.json") for row in rows] + refs,
            next_steps=["preserve the registry row and the session's refs; prepare the assignment under a fresh audit ID",
                        f"close --audit-id {session.name} --abandon --reason TEXT retires what the row names; "
                        "the ID stays reserved"])


def worktree_lock(git_admin: str) -> str | None:
    """The worktree's Git lock reason, or None when it is not locked."""
    info, lock = read_regular(Path(git_admin) / "locked")
    if info["kind"] == "missing":
        return None
    if lock is None:
        raise StewartError("worktree lock is unreadable", reason="worktree_role_registry")
    return lock.decode("utf-8", "replace")


def lifetime_lock_reason(session_identity: str) -> str:
    return (f"{LIFETIME_LOCK}{session_identity}: run stewart status before removing; "
            "close removes it with its session")


def _prospective_role(manager: dict, worktree: Path, session: Path) -> dict:
    """Validate a registration without publishing either its marker or row."""
    auditor = checkout_identity(worktree)
    if auditor["common_dir"] != manager["common_dir"] or auditor["git_admin"] == manager["git_admin"]:
        raise StewartError("auditor must be a separate linked worktree of this repository", reason="worktree_role_identity")
    info, data = read_regular(session / "session.json")
    if data is None:
        raise StewartError("session cannot be read for role registration", reason="worktree_role_identity")
    record = loads_control(data)
    if (not isinstance(record, dict) or str(worktree) != record.get("worktree")
            or Path(str(record.get("audit_dir"))) / "worktree" != worktree
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
