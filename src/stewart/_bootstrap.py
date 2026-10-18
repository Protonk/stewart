"""Trusted startup, runtime inventories and descriptor custody primitives.

This file is executable with ``python -I -B`` and uses only the standard library
until runtime verification succeeds. A manager retains its own copy outside auditor grants, so verifying a
supplied runtime never asks that runtime to attest to itself. The same verified
descriptor readers serve collection and startup; no weaker bootstrap reader is
maintained alongside the custody reader.
"""
import sys

# Refuse before this script imports anything except the preloaded sys module.
# Interpreter startup hooks run before any script and remain a trust root.
if __name__ == "__main__" and (not sys.flags.isolated or not sys.dont_write_bytecode):
    if "--json" in sys.argv:
        sys.stdout.write('{"schema":"stewart.result/2","command":null,"ok":false,"exit_code":2,"result":null,"error":{"reason":"startup_isolation","message":"use the complete explicit interpreter -I -B command","retained":[],"next_steps":[]}}\n')
    else:
        sys.stderr.write("Refused (startup_isolation): use the complete explicit interpreter -I -B command\n")
    raise SystemExit(2)

import argparse
from collections.abc import Iterable
from contextlib import ExitStack, contextmanager
import errno
import hashlib
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import types

CHILD_LEDGER_MODULE = "_stewart_ledger_v1"
CHILD_LEDGER_FILE = "stewart/ledger.py"


def child_project_paths(worktree: Path, script: str) -> list[str]:
    """The Python script directory precedes the explicitly selected project root."""
    path = PurePosixPath(script)
    if (not worktree.is_absolute() or not script or path.is_absolute() or path.as_posix() != script
            or ".." in path.parts or "\0" in script):
        raise StewartError("child script must be a literal project-relative path", reason="child_layout")
    return [str(worktree / path.parent), str(worktree)]


def check_child_imports(paths: list[str]) -> None:
    """Reserve one ledger import name; project stewart names remain free.

    Reject the reserved basename and any dotted suffix in each inserted search
    directory, including packages, source, bytecode and native extension forms.
    Directory entries are observed without following possible planted links.
    """
    if CHILD_LEDGER_MODULE in sys.modules:
        raise StewartError("reserved child ledger module is already loaded", reason="ledger_collision")
    for path in dict.fromkeys(paths):
        try:
            with open_directory(Path(path)) as directory:
                collisions = sorted(name for name in os.listdir(directory)
                                    if name == CHILD_LEDGER_MODULE or name.startswith(CHILD_LEDGER_MODULE + "."))
        except OSError as exc:
            raise StewartError("cannot inspect the child's project search directory", reason="child_layout",
                               retained=[path]) from exc
        if collisions:
            raise StewartError("project search path collides with the reserved ledger name", reason="ledger_collision",
                               retained=[str(Path(path) / name) for name in collisions],
                               next_steps=["preserve the conflicting project entries; choose a project namespace outside the reserved ledger name"])


def _prepare_child(code_root: Path, manifest: dict, worktree: Path, script: str, script_sha256: str):
    """Load pinned ledger bytes before admitting project imports; execute no project code."""
    import importlib.util
    paths = child_project_paths(worktree, script)
    if Path.cwd() != worktree:
        raise StewartError("child working directory differs from the released project", reason="child_layout")
    check_child_imports(paths)
    ledger_path = code_root / CHILD_LEDGER_FILE
    ledger_pin = next((item for item in manifest["entries"] if item["path"] == CHILD_LEDGER_FILE), None)
    info, ledger_bytes = read_regular(ledger_path)
    if ledger_pin is None or ledger_bytes is None or info.get("sha256") != ledger_pin["sha256"]:
        raise StewartError("supplied ledger differs from its runtime pin", reason="runtime_mismatch")
    script_path = worktree / script
    info, script_bytes = read_regular(script_path)
    if script_bytes is None or info.get("sha256") != script_sha256:
        raise StewartError("child script differs from its released pin", reason="child_script_mismatch")
    spec = importlib.util.spec_from_file_location(CHILD_LEDGER_MODULE, ledger_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[CHILD_LEDGER_MODULE] = module
    # Execute descriptor-read source bytes, not a second pathname/bytecode read.
    exec(compile(ledger_bytes, str(ledger_path), "exec"), module.__dict__)
    sys.path[:0] = paths
    return script_bytes, script_path


def _execute_child(script_bytes: bytes, script_path: Path, arguments: list[str]) -> int:
    """Match script-mode argv/module semantics; child exceptions keep their meaning."""
    module = types.ModuleType("__main__")
    module.__dict__.update(__file__=str(script_path), __package__=None, __spec__=None,
                           __cached__=None, __loader__=SourceFileLoader("__main__", str(script_path)))
    sys.modules["__main__"] = module
    sys.argv = list(arguments)
    exec(compile(script_bytes, str(script_path), "exec"), module.__dict__)
    return 0


#: Exit codes shared by every Stewart command and auditor helper. Exit 0 means
#: nothing needs anyone's attention; there is no "succeeded with warnings".
#: Codes never depend on what an audit says (completion, report kind, prose,
#: triage outcomes): only on whether the records and checkout are in order.
EXIT_OK = 0
#: Action is needed within the caller's role; every message names the change.
EXIT_ATTENTION = 1
#: Refused; nothing was done. Fix the command or its preconditions.
EXIT_REFUSED = 2
#: Something the caller cannot repair does not verify. Preserve it and report
#: it; an auditor describes it in the report and stops. Takes precedence over 1.
EXIT_UNVERIFIED = 3

#: Refusal reasons whose cause is evidence, records or bytes that fail
#: verification. Every other classified reason refuses with exit 2. A reason
#: identifier is part of the JSON contract; tests require each literal reason
#: in the source to appear in exactly one of these two sets.
UNVERIFIED_REASONS = frozenset({
    "archive_mismatch", "archive_unreadable", "attempt_schema", "binding_mismatch", "capture_unavailable",
    "checkout_identity", "child_binding", "child_script_mismatch", "collection_binding", "collection_schema",
    "coordination_schema", "evidence_tampered", "evidence_unavailable", "exit_log_malformed",
    "frozen_unavailable", "input_mismatch", "launcher_mismatch", "package_binding", "package_schema",
    "pinned_input_changed",
    "protected_baseline_mismatch", "record_corrupt", "record_schema", "record_unreadable",
    "release_invalidated", "release_schema", "report_binding", "report_unavailable", "runtime_assets",
    "runtime_capture", "runtime_capture_io", "runtime_capture_schema", "runtime_capture_unavailable",
    "runtime_helper", "runtime_identity", "runtime_inventory", "runtime_layout", "runtime_manifest",
    "runtime_mismatch", "runtime_recovery", "runtime_unreadable", "session_identity", "session_retention",
    "session_schema_unsupported", "session_unavailable", "support_unavailable", "triage_schema",
    "validation_error", "worktree_missing", "worktree_role_conflict", "worktree_role_identity",
    "worktree_role_registry",
})
REFUSED_REASONS = frozenset({
    "actor_required", "already_resumed", "assignment_schema", "assignment_sections", "attempt_unresolved",
    "audit_id", "audit_id_format", "auditor_not_stopped", "auditor_scope", "auditor_worktree",
    "byte_order_mark", "capture_selector", "checkout_commit", "checkout_detached", "checkout_git_file",
    "checkout_root", "child_argv", "child_layout", "collection_incomplete", "collection_not_found",
    "commit_format", "commit_id", "completion", "context_changed", "context_unavailable", "crlf",
    "custody_gaps", "destination_exists", "documentation", "duplicate_blocks", "duplicate_input_key",
    "duplicate_key", "execution_not_granted", "expected_worktree", "export_failed", "export_selection",
    "export_source", "failed", "fence_trailing_space", "field_type", "follow_up_required",
    "follow_up_unexpected", "git_failed", "git_ref_transaction", "grant_containment", "grant_schema",
    "handoff_identity", "identity_format", "identity_mismatch", "initialization_failed", "input_collision",
    "input_drift", "input_file", "input_manifest", "input_missing", "input_overlap",
    "interpreter_unavailable", "invalid_json", "launch_profile", "launch_profile_missing", "ledger_collision",
    "malformed_fence", "manifest_schema", "missing", "missing_field", "mode", "movement", "nested_block",
    "no_grant", "no_hold", "non_object", "path_escape", "path_noncanonical", "path_symlink",
    "pause_note_required", "pause_unacknowledged", "prepare_failed", "private_storage_not_ignored",
    "private_storage_tracked", "prompt_commit_shape", "prompt_digest", "prompt_drift", "reason_required",
    "record_missing", "record_name", "refused", "release_consumed", "report_changed", "report_kind", "report_kind_required",
    "report_unreadable", "report_write", "repository_root", "response_schema", "retain_nothing",
    "review_schema", "runtime_cache", "schema_version", "session_missing", "startup_failed",
    "startup_isolation", "support_unreviewed", "target_ancestry", "target_drift", "unassigned_prompt",
    "unknown_field", "unterminated_block", "usage", "workspace_guidance", "workspace_path",
})
#: Status problem reasons that describe a recorded, partial state awaiting a
#: manager action rather than records that fail verification. Only a missing
#: completion receipt supports these labels; any other problem is unverified.
STATE_REASONS = frozenset({"attempt_unresolved", "collection_incomplete", "prepare_failed"})


def exit_code_for(reason: str) -> int:
    """The exit code a refusal with ``reason`` earns; unclassified reasons refuse."""
    return EXIT_UNVERIFIED if reason in UNVERIFIED_REASONS else EXIT_REFUSED


def combined_code(codes: Iterable[int]) -> int:
    """Combine attention (1) and unverified (3) findings; 3 takes precedence."""
    values = set(codes)
    return EXIT_UNVERIFIED if EXIT_UNVERIFIED in values else EXIT_ATTENTION if EXIT_ATTENTION in values else EXIT_OK


class StewartError(ValueError):
    """A refused or failed custody operation; existing files are never removed.

    ``exit_code`` follows the reason table unless the raise site knows better,
    for example when a record read inside session validation fails.
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str = "refused",
        retained: Iterable[str] = (),
        next_steps: Iterable[str] = (),
        code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.retained = [str(item) for item in retained]
        self.next_steps = [str(item) for item in next_steps]
        self.code = code

    @property
    def exit_code(self) -> int:
        return self.code if self.code in (EXIT_REFUSED, EXIT_UNVERIFIED) else exit_code_for(self.reason)

    def to_json(self) -> dict:
        return {
            "reason": self.reason,
            "message": str(self),
            "retained": list(self.retained),
            "next_steps": list(self.next_steps),
        }


class RefusalParser(argparse.ArgumentParser):
    """Usage refusals share the CLI's structured error contract."""

    def error(self, message: str) -> None:
        raise StewartError(message, reason="usage", next_steps=["consult --help for the complete command"])


# O_NOFOLLOW makes a late symlink fail instead of being followed; O_NONBLOCK keeps a
# late FIFO from hanging the collector; fstat on the descriptor is the observation
# that is trusted, because a prior lstat describes an entry that may have changed.
_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
_DIRECTORY_FLAGS = _OPEN_FLAGS | os.O_DIRECTORY
# Traversal needs search permission, not permission to list every ancestor.
# This lets a scoped helper reach its allowed subtree without exposing private
# parent directory contents. The final directory still needs read permission.
_SEARCH_FLAGS = (getattr(os, "O_SEARCH", getattr(os, "O_PATH", os.O_RDONLY))
                 | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))


@contextmanager
def open_directory(location: Path, *, dir_fd: int | None = None):
    """Pin each ancestor with a no-follow directory descriptor; close all owned fds.

    An anchored relative path is interpreted against the supplied descriptor,
    never the current pathname of its directory. Without an anchor, start at
    the filesystem root. No caller-controlled ancestor is resolved through a
    symlink. Callers should pass a canonical trusted checkout root.
    """
    location = Path(location)
    if dir_fd is None:
        location = Path(os.path.abspath(location))
        parts = location.parts[1:]
        fd = os.open(location.anchor, _SEARCH_FLAGS if parts else _DIRECTORY_FLAGS)
    else:
        if location.is_absolute() or ".." in location.parts:
            raise ValueError("descriptor-relative paths cannot be absolute or contain '..'")
        fd = os.dup(dir_fd)
        parts = location.parts
    try:
        for index, component in enumerate(parts):
            flags = _DIRECTORY_FLAGS if index == len(parts) - 1 else _SEARCH_FLAGS
            following = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = following
        yield fd
    finally:
        os.close(fd)


_KINDS = (
    (stat.S_ISREG, "file"),
    (stat.S_ISDIR, "directory"),
    (stat.S_ISLNK, "symlink"),
    (stat.S_ISFIFO, "fifo"),
    (stat.S_ISSOCK, "socket"),
    (stat.S_ISCHR, "chardev"),
    (stat.S_ISBLK, "blockdev"),
)

SPECIAL_KINDS = frozenset({"fifo", "socket", "chardev", "blockdev", "unknown", "replaced"})


def entry_kind(mode: int) -> str:
    for test, name in _KINDS:
        if test(mode):
            return name
    return "unknown"


def verified_stream_digest(stream) -> str:
    """SHA-256 of a stream whose identity was verified before it was read.

    The collector hashes through a descriptor it has already checked with
    ``fstat`` (or a tar member it has already matched), so it must not reopen a
    path and must not hand the stream to a path-based helper.
    The digest equals ``sha256_bytes`` of the
    remaining bytes; chunking never affects it.
    """
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


class _Unavailable(Exception):
    """A regular file could not be opened as one; carries what was found instead."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def _open_regular(location: Path, *, dir_fd: int | None = None) -> tuple[int, os.stat_result]:
    """Open without following or blocking, then confirm the descriptor is a regular file."""
    try:
        with open_directory(location.parent, dir_fd=dir_fd) as parent:
            discovered = os.stat(location.name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(discovered.st_mode):
                raise _Unavailable("replaced", f"entry is a {entry_kind(discovered.st_mode)}, not a regular file")
            fd = os.open(location.name, _OPEN_FLAGS, dir_fd=parent)
    except OSError as exc:
        kind = "missing" if exc.errno == errno.ENOENT else (
            "replaced" if exc.errno in (errno.ELOOP, errno.EMLINK, errno.ENOTDIR) else "unreadable")
        raise _Unavailable(kind, f"{exc.strerror} (open, errno {exc.errno})") from exc
    try:
        st = os.fstat(fd)
    except OSError as exc:
        os.close(fd)
        raise _Unavailable("unreadable", f"{exc.strerror} (fstat)") from exc
    if not stat.S_ISREG(st.st_mode):
        os.close(fd)
        raise _Unavailable("replaced", f"entry became a {entry_kind(st.st_mode)} before it was opened")
    if (st.st_dev, st.st_ino) != (discovered.st_dev, discovered.st_ino):
        os.close(fd)
        raise _Unavailable("replaced", "regular file identity changed between discovery and open")
    return fd, st


def read_regular(location: Path, *, dir_fd: int | None = None) -> tuple[dict, bytes | None]:
    """Read a regular file's bytes through a verified descriptor, or say why not."""
    try:
        fd, st = _open_regular(location, dir_fd=dir_fd)
    except _Unavailable as unavailable:
        return {"kind": unavailable.kind, "detail": unavailable.detail}, None
    with os.fdopen(fd, "rb") as fh:
        try:
            data = fh.read()
        except OSError as exc:
            return {"kind": "unreadable", "detail": f"{exc.strerror} (read)"}, None
    info = {"kind": "file", "mode": stat.S_IMODE(st.st_mode), "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}
    return info, data


def capture_regular(location: Path, *, dir_fd: int | None = None) -> dict:
    """Digest a regular file through a verified descriptor without loading it whole."""
    try:
        fd, st = _open_regular(location, dir_fd=dir_fd)
    except _Unavailable as unavailable:
        return {"kind": unavailable.kind, "detail": unavailable.detail}
    with os.fdopen(fd, "rb") as fh:
        try:
            digest = verified_stream_digest(fh)
        except OSError as exc:
            return {"kind": "unreadable", "detail": f"{exc.strerror} (read)"}
    return {"kind": "file", "mode": stat.S_IMODE(st.st_mode), "size": st.st_size, "sha256": digest}


def write_exclusive(location: Path, data: bytes, *, dir_fd: int | None = None) -> None:
    """Create one file under verified ancestors; never replace a file or follow a link.

    Parents must already exist. The optional directory descriptor lets a package
    publisher keep its new directory pinned throughout publication.
    """
    with open_directory(location.parent, dir_fd=dir_fd) as parent:
        fd = os.open(location.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)


MANIFEST_SCHEMA = "stewart.runtime-manifest/1"
OBSERVATION_SCHEMA = "stewart.runtime-observation/1"
SOURCE_MODULES = frozenset({
    "__init__.py", "__main__.py", "_bootstrap.py", "_git.py", "_invocation.py", "_json.py",
    "_repository.py", "_util.py", "api.py", "assignment.py", "auditor_scope.py", "captured.py", "cli.py", "collect.py",
    "coordination.py", "experiment.py", "handoff.py", "launch_profile.py", "ledger.py",
    "prepare.py", "report_declaration.py", "runtime.py", "session.py", "status.py", "triage.py",
    "verify_inputs.py", "workspace.py", "docs.py", "_version.py",
})
SOURCE_RESOURCES = frozenset({"README.md", "QUESTION-TYPE.md", "AUDIT-PROTOCOLS.md", "AUDITOR.md",
                              "MAINTAINER.md", "AGENTS.md", "CLAUDE.md", "stewart", "_stewart-python"})
SOURCE_FILES = SOURCE_MODULES | {f"resources/{name}" for name in SOURCE_RESOURCES}
_MANAGER_ENTRY_FILES = frozenset(f"stewart/{name}" for name in SOURCE_FILES)


def validate_manifest(value: object) -> dict:
    """Accept only a complete, nonempty, executable inventory, never a failure.

    Observations preserve bad entries for custody. They cannot authorize startup,
    even when two observations of the same missing or unreadable bytes agree.
    Permission bits and inode identities are outside this byte contract; access
    grants and ownership remain separate checks.
    """
    def refuse(message: str) -> None:
        raise StewartError(f"invalid runtime manifest: {message}", reason="runtime_manifest",
                           next_steps=["recover a manifest sealed from a complete regular runtime"])

    if not isinstance(value, dict) or set(value) != {"schema_version", "entries"}:
        refuse("expected a versioned inventory object")
    if value["schema_version"] != MANIFEST_SCHEMA or not isinstance(value["entries"], list):
        refuse("unsupported schema or member list")
    members: dict[str, str] = {}
    paths = []
    for entry in value["entries"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "kind", "size", "sha256"}:
            refuse("member must contain exactly path, kind, size and sha256")
        name = entry["path"]
        if (not isinstance(name, str) or not name or "\x00" in name
                or PurePosixPath(name).is_absolute() or PurePosixPath(name).as_posix() != name
                or name == "." or ".." in PurePosixPath(name).parts or name in members):
            refuse("member names must be unique canonical relative paths")
        if (any(part.casefold() == "__pycache__" for part in PurePosixPath(name).parts)
                or PurePosixPath(name).suffix.casefold() in {".pyc", ".pyo", ".so", ".dylib"}):
            refuse(f"cache or native module is not a source/resource member: {name}")
        kind = entry["kind"]
        if kind == "file":
            if (type(entry["size"]) is not int or entry["size"] < 0
                    or not isinstance(entry["sha256"], str)
                    or re.fullmatch("[0-9a-f]{64}", entry["sha256"]) is None):
                refuse(f"regular member lacks its size and byte digest: {name}")
        elif kind == "directory":
            if entry["size"] is not None or entry["sha256"] is not None:
                refuse(f"directory cannot carry file bytes: {name}")
        else:
            refuse(f"member is not a regular file or directory: {name}")
        members[name] = kind
        paths.append(name)
    if not members or "file" not in members.values() or paths != sorted(paths):
        refuse("inventory must be sorted and contain at least one file")
    for name in paths:
        for parent in PurePosixPath(name).parents:
            if parent != PurePosixPath(".") and members.get(str(parent)) != "directory":
                refuse(f"parent directory is missing from inventory: {name}")
    return value


def observe_runtime(root: Path) -> tuple[dict, dict[str, bytes]]:
    """Inventory every entry and capture regular bytes; preserve failures as data.

    Directories stay pinned during descent, including the root's ancestors.
    Symlinks and special files are classified but never opened. A disappearing
    or replaced entry remains visible as a diagnostic. Callers needing movement
    detection compare separate observations around their operation.
    """
    entries: list[dict] = []
    payloads: dict[str, bytes] = {}

    def failed(rel: str, exc: OSError) -> None:
        entries.append({"path": rel, "kind": "unreadable", "size": None,
                        "sha256": None, "detail": f"{exc.strerror} (errno {exc.errno})"})

    def visit(fd: int, prefix: str) -> None:
        try:
            names = sorted(os.listdir(fd))
        except OSError as exc:
            failed(prefix or ".", exc)
            return
        for name in names:
            rel = f"{prefix}/{name}" if prefix else name
            try:
                before = os.stat(name, dir_fd=fd, follow_symlinks=False)
                kind = entry_kind(before.st_mode)
                entry = {"path": rel, "kind": kind, "size": None, "sha256": None}
                if kind == "directory":
                    with open_directory(Path(name), dir_fd=fd) as child:
                        opened = os.fstat(child)
                        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                            entry.update(kind="replaced", detail="directory identity changed during open")
                        else:
                            visit(child, rel)
                elif kind == "file":
                    info, data = read_regular(Path(name), dir_fd=fd)
                    entry.update({k: v for k, v in info.items() if k != "mode"})
                    if data is not None:
                        payloads[rel] = data
                elif kind == "symlink":
                    entry["target"] = os.readlink(name, dir_fd=fd)
                entries.append(entry)
            except OSError as exc:
                failed(rel, exc)

    try:
        with open_directory(root) as fd:
            visit(fd, "")
    except OSError as exc:
        failed(".", exc)
    return {"schema_version": OBSERVATION_SCHEMA,
            "entries": sorted(entries, key=lambda entry: entry["path"])}, payloads


def runtime_manifest(root: Path) -> dict:
    """Seal a nonempty regular source/resource tree for later exact comparison."""
    observed, _ = observe_runtime(root)
    try:
        return validate_manifest({"schema_version": MANIFEST_SCHEMA, "entries": observed["entries"]})
    except StewartError as exc:
        raise StewartError(f"runtime cannot be sealed: {exc}",
                           reason="runtime_inventory", retained=[str(root)],
                           next_steps=["stage a fresh complete runtime from the selected distribution"]) from exc


def runtime_digest(manifest: dict) -> str:
    """Hash a manifest or observation; a digest alone grants no execution permission."""
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()


def verify_runtime(root: Path, expected: object) -> dict:
    """Compare complete membership and bytes; never accept a matching subset."""
    validate_manifest(expected)
    observed, _ = observe_runtime(root)
    candidate = {"schema_version": MANIFEST_SCHEMA, "entries": observed["entries"]}
    if candidate != expected:
        raise StewartError("selected runtime membership or bytes changed", reason="runtime_mismatch",
                           retained=[str(root)],
                           next_steps=["recover the pinned runtime; do not substitute another installation"])
    return candidate


def manager_home(cache: Path | None = None) -> Path:
    """Require an explicit absolute, unlinked private deployment directory."""
    configured = os.environ.get("STEWART_MANAGER_HOME")
    cache = cache or (Path(configured) if configured else Path.home() / ".cache/stewart/managers")
    if not cache.is_absolute() or ".." in cache.parts:
        raise StewartError("manager storage must be an absolute path", reason="runtime_cache")
    # Check existing ancestors before mkdir, then pin and check the result. Do
    # not silently resolve an auditor-supplied link into an acceptable directory.
    for parent in [*reversed(cache.parents), cache]:
        if parent.is_symlink():
            raise StewartError("manager storage cannot traverse a link", reason="runtime_cache")
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open_directory(cache) as descriptor:
        permissions = os.fstat(descriptor)
    if permissions.st_uid != os.getuid() or permissions.st_mode & 0o077:
        raise StewartError("manager deployment storage must be private to the current user",
                           reason="runtime_cache", retained=[str(cache)],
                           next_steps=["select a manager-owned directory with mode 0700 outside auditor grants"])
    return cache


def source_payloads(source: Path) -> tuple[dict, dict[str, bytes]]:
    """Select the complete distribution source/resource population without imports.

    Generated installation caches are excluded from this trusted initial source
    selection; none is copied into the executable deployment. The deployment
    itself permits no ignored entries. Development files belong outside src/.
    """
    observed, payloads = observe_runtime(source)
    entries = [entry for entry in observed["entries"] if "__pycache__" not in PurePosixPath(entry["path"]).parts]
    found = {entry["path"]: entry for entry in entries}
    expected = SOURCE_FILES | {"resources"}
    if set(found) != expected:
        raise StewartError(f"distribution membership differs: missing {sorted(expected - set(found))}, "
                           f"unexpected {sorted(set(found) - expected)}", reason="runtime_layout")
    if any(found[name]["kind"] != ("directory" if name == "resources" else "file") for name in expected):
        raise StewartError("distribution members must be readable regular files and directories",
                           reason="runtime_unreadable", retained=[str(source)])
    manifest = validate_manifest({"schema_version": MANIFEST_SCHEMA, "entries": entries})
    return manifest, {name: payloads[name] for name in SOURCE_FILES}


def stage_source(source: Path, *, cache: Path | None = None) -> dict:
    """Deploy the loaded source package, excluding non-distribution project files.

    This first selection trusts the manager's source installation. Only the
    resulting dedicated tree is an executable inventory: every member of that
    tree is checked thereafter, with no ignored cache or hidden entries. Source
    edits create another deployment; already issued commands keep their pins.
    The manager owns the cache and must keep it outside auditor write grants.
    """
    source = source.resolve()
    if source.name != "stewart":
        raise StewartError("unsupported Stewart source installation layout", reason="runtime_layout",
                           next_steps=["use a complete supported Stewart distribution"])
    _, payloads = source_payloads(source)
    selected = {f"stewart/{name}": data for name, data in payloads.items()}
    cache = manager_home(cache)
    for name in ("deployments", "launchers", "process-cache"):
        manager_home(cache / name)
    with tempfile.TemporaryDirectory(prefix="stage-", dir=cache) as temporary:
        stage = Path(temporary)
        runtime = stage / "runtime"
        (runtime / "stewart/resources").mkdir(parents=True)
        for name, data in selected.items():
            write_exclusive(runtime / name, data)
        manifest = runtime_manifest(runtime)
        destination = cache / "deployments" / runtime_digest(manifest)
        bootstrap = selected["stewart/_bootstrap.py"]
        launcher_digest = hashlib.sha256(bootstrap).hexdigest()
        launcher = cache / "launchers" / f"{launcher_digest}.py"
        try:
            write_exclusive(launcher, bootstrap)
        except FileExistsError:
            pass
        try:
            # An existing nonempty deployment cannot be replaced by rename.
            # A concurrent publisher must have produced the same complete bytes.
            os.rename(stage, destination)
        except OSError:
            if not destination.exists():
                raise
        verify_runtime(destination / "runtime", manifest)
        info, retained = read_regular(launcher)
        if retained != bootstrap:
            raise StewartError("retained manager bootstrap differs from the selected source",
                               reason="launcher_mismatch", retained=[str(launcher)])
    return {"code_root": destination / "runtime", "launcher": launcher,
            "manifest": manifest, "launcher_sha256": info["sha256"], "source_package": source}


def launch(argv: list[str] | None = None) -> int:
    """Verify a dedicated runtime before any of its modules may be imported.

    The interpreter, its site-packages hooks and this retained script are trust
    roots. Isolation removes caller paths and PYTHON* settings, not interpreter
    compromise. Manager caches live beside the retained launcher; an auditor
    helper uses a fresh private system-temp directory outside its read-only
    supplied runtime. Child mode preloads only the pinned ledger, then admits
    the released script directory and project root in that order.
    """
    parser = RefusalParser(description="Isolated Stewart startup; fixed operation policies only")
    modes = parser.add_subparsers(dest="mode", required=True)
    manager = modes.add_parser("manager", help="run the explicitly pinned manager deployment")
    manager.add_argument("--code-root", required=True, type=Path)
    manager.add_argument("--runtime-sha256", required=True)
    manager.add_argument("--source-package", type=Path, help="source location at selection; never an import path")
    helper = modes.add_parser("helper", help="run one issued auditor helper without project imports")
    helper.add_argument("--code-root", required=True, type=Path)
    helper.add_argument("--runtime-sha256", required=True)
    helper.add_argument("--helper", required=True, choices=("inputs", "declaration"))
    child = modes.add_parser("child", help="run a released Python script with its pinned ledger")
    child.add_argument("--code-root", required=True, type=Path)
    child.add_argument("--runtime-sha256", required=True)
    child.add_argument("--worktree", required=True, type=Path)
    child.add_argument("--script-sha256", required=True)
    source = modes.add_parser("source", help="deploy this source installation, then use isolated manager startup")
    source.add_argument("--manager-home", type=Path, help="private retained-deployment directory")
    # Keep launcher options separate from CLI options. The separator is part of
    # the fixed route; project arguments cannot change the startup policy.
    raw = list(sys.argv[1:] if argv is None else argv)
    boundary = raw.index("--") if "--" in raw else len(raw)
    arguments = raw[boundary + 1:]
    runtime_error = StewartError
    with ExitStack() as stack:
        try:
            args = parser.parse_args(raw[:boundary])
            if not sys.flags.isolated or not sys.dont_write_bytecode:
                raise StewartError("startup requires the explicit interpreter with -I -B",
                                   reason="startup_isolation",
                                   next_steps=["run the complete issued argv without removing interpreter flags"])
            if args.mode == "source":
                deployed = stage_source(Path(__file__).parent, cache=args.manager_home)
                code_root, launcher = deployed["code_root"], deployed["launcher"]
                expected_digest = runtime_digest(deployed["manifest"])
                source_package = deployed["source_package"]
            else:
                code_root, launcher = args.code_root, Path(os.path.abspath(__file__))
                expected_digest = args.runtime_sha256
                source_package = getattr(args, "source_package", None)
            if not code_root.is_absolute() or re.fullmatch("[0-9a-f]{64}", expected_digest) is None:
                raise StewartError("runtime root and SHA-256 pin must be explicit", reason="runtime_layout")
            # The auditor cannot read the manager cache. Its helper uses a fresh
            # private system-temp directory, outside the read-only supplied tree.
            cache_root = None if args.mode == "helper" else manager_home(launcher.parent.parent / "process-cache")
            cache = stack.enter_context(tempfile.TemporaryDirectory(prefix="cache-", dir=cache_root))
            # -B prevents writes; it does not stop reads of existing bytecode.
            sys.pycache_prefix = cache
            try:
                manifest = runtime_manifest(code_root)
            except StewartError as exc:
                raise StewartError(f"pinned runtime is unavailable: {exc}", reason="runtime_inventory",
                                   retained=[str(code_root)], next_steps=[
                                       "preserve the damaged deployment; restore the exact pinned bytes at this path",
                                       "to select current source instead, use source --manager-home with a fresh absolute directory",
                                   ]) from exc
            if runtime_digest(manifest) != expected_digest:
                raise StewartError("selected runtime membership or bytes changed", reason="runtime_mismatch",
                                   retained=[str(code_root)],
                                   next_steps=["restore the pinned runtime; no alternate installation is selected"])
            regular = {entry["path"] for entry in manifest["entries"] if entry["kind"] == "file"}
            if not _MANAGER_ENTRY_FILES <= regular:
                raise StewartError("selected runtime lacks the supported manager entry points",
                                   reason="runtime_layout", retained=[str(code_root)],
                                   next_steps=["recover a complete Stewart deployment"])
            if args.mode == "child":
                if not arguments or re.fullmatch("[0-9a-f]{64}", args.script_sha256) is None:
                    raise StewartError("child startup needs an explicit script and released digest", reason="child_layout")
                script_bytes, script_path = _prepare_child(code_root, manifest, args.worktree,
                                                           arguments[0], args.script_sha256)
            else:
                sys.path.insert(0, str(code_root))
            if args.mode == "helper":
                from stewart._bootstrap import StewartError as runtime_error
                if args.helper == "inputs":
                    from stewart.verify_inputs import main
                else:
                    from stewart.report_declaration import main
                return main(arguments)
            if args.mode != "child":
                from stewart import _invocation
                runtime_error = _invocation.StewartError
                _invocation.bind_verified(code_root, launcher, manifest, source_package=source_package)
                from stewart.cli import main
                return main(arguments)
        except (StewartError, runtime_error, OSError) as exc:
            error = exc.to_json() if isinstance(exc, (StewartError, runtime_error)) else {
                "reason": "startup_failed", "message": str(exc), "retained": [],
                "next_steps": ["restore the selected manager deployment and its private cache access"]}
            code = getattr(exc, "exit_code", EXIT_REFUSED)
            if "--json" in raw:
                print(json.dumps({"schema": "stewart.result/2", "command": None,
                                  "ok": False, "exit_code": code, "result": None, "error": error}, sort_keys=True))
            else:
                print(f"Refused ({error['reason']}): {error['message']}", file=sys.stderr)
            return code
        # Project code runs outside the startup refusal handler. Its OSError,
        # SystemExit, signals and traceback must remain child outcomes.
        return _execute_child(script_bytes, script_path, arguments)


if __name__ == "__main__":
    raise SystemExit(launch())
