"""Caller-chosen request keys: one exclusive binding, planned outputs, one recorded outcome.

A key names intended work within one repository. Its records live under
``<common>/stewart/requests/<sha256 of the key>/`` with the exact key inside,
so keys differing only in case or normalization never share a record.
``REQUEST.json`` is published exclusively before any side effect and binds
the operation, the selected audit, lifetime and resources, the implementation
and the semantic inputs (decoded control documents by canonical digest,
supplied files by byte digest). The invoking checkout is recorded beside the
binding, not in it, so the same key can be inspected or retried from any
maintainer checkout of the repository, including after the original one was
retired. An operation records its planned output identities in ``attempts/``
immediately before its first side effect, and ``OUTCOME.json`` records
completion or refusal with the output identities. Execution holds an exclusive
lock on the request directory, so a second caller sees ``in_progress`` instead
of starting the same work.

Reusing a key with a different binding is refused. A matching completed or
refused request returns its recorded outcome without executing again. A
request reserved without any attempt executes on retry: nothing was planned,
so nothing started. A request with attempts but no outcome is ``partial``: the
uncertainty is returned, never replayed; only operations with safe resumption
continue under the same key, and only when the caller asks explicitly. A key
does not prove whether an unrecorded side effect happened. Request records
outlive the sessions and resources they name. Without a key, every call is a
new request: nothing is deduplicated by payload, time or recency.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import errno
import fcntl
import os
from pathlib import Path
import re

from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_UNVERIFIED, StewartError, read_regular

BINDING_SCHEMA = "stewart.request-binding/1"
ATTEMPT_SCHEMA = "stewart.request-attempt/1"
OUTCOME_SCHEMA = "stewart.request-outcome/1"
VIEW_SCHEMA = "stewart.request/1"
REQUESTS = "stewart/requests"
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
#: Operations whose interrupted execution continues safely from their own records.
RESUMABLE = frozenset({"close", "resource-close"})
_BINDING_FIELDS = {"operation", "repository", "audit", "lifetime", "resources", "implementation", "inputs"}


class _Active:
    def __init__(self, directory: Path, attempt: str, key: str):
        self.directory, self.attempt, self.key, self.count = directory, attempt, key, 0

    def plan(self, outputs: list[dict]) -> None:
        from stewart.session import now, write_receipt
        self.count += 1
        write_receipt(self.directory / "attempts" / f"{self.attempt}-{self.count}.json", {
            "schema": ATTEMPT_SCHEMA, "key": self.key, "attempt": self.attempt, "recorded_at": now().isoformat(),
            "planned": outputs,
            "note": "recorded immediately before a side effect; it does not establish that the effect happened"})


_active: ContextVar[_Active | None] = ContextVar("stewart_request", default=None)


def plan(outputs: list[dict]) -> None:
    """Record planned output identities before an operation's first side effect; nothing happens without a key."""
    active = _active.get()
    if active is not None:
        active.plan(outputs)


def key_name(value: object) -> str:
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise StewartError("a request key is 1-128 letters, digits, '.', '_' or '-', starting with a letter or digit",
                           reason="request_key_format",
                           next_steps=["choose a key your caller persists before submitting the request"])
    return value


def location(common: str, key: str) -> Path:
    from stewart._util import sha256_text
    from stewart.workspace import contained
    return contained(Path(common), f"{REQUESTS}/{sha256_text(key_name(key))}")


def input_digest(value: object) -> str:
    """The canonical digest of a decoded control document supplied as an operation input."""
    from stewart._util import sha256_canonical_json
    return sha256_canonical_json(value)


def file_digest(path: Path | str) -> dict:
    """A supplied file's byte identity, or what was found instead."""
    info, _ = read_regular(Path(path))
    return {"kind": info["kind"], "sha256": info.get("sha256")}


@contextmanager
def _locked(directory: Path):
    """Hold the request's exclusive lock; yield False when another process holds it."""
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                yield False
                return
            raise
        yield True
    finally:
        os.close(descriptor)


def _publish(directory: Path, document: dict) -> bool:
    """Publish REQUEST.json from a complete staged copy; False when the key already holds a binding."""
    from stewart.session import stamp, write_receipt
    staged = directory / f".REQUEST.json.{stamp()}.staged"
    write_receipt(staged, document)
    try:
        os.link(staged, directory / "REQUEST.json")
        return True
    except FileExistsError:
        return False
    finally:
        staged.unlink()


def _read(directory: Path, key: str | None = None) -> tuple[dict, str]:
    from stewart.session import capture_receipt
    value, digest = capture_receipt(directory / "REQUEST.json", what="request binding")
    if (value.get("schema") != BINDING_SCHEMA or not isinstance(value.get("binding"), dict)
            or set(value["binding"]) != _BINDING_FIELDS or not isinstance(value.get("key"), str)
            or (key is not None and value["key"] != key)):
        raise StewartError(f"request binding has an unsupported shape or names another key: {directory}",
                           reason="request_record_invalid", retained=[str(directory)])
    return value, digest


def keyed(ws, ident: str | None, operation: str, inputs: dict, request_key: str | None, execute, *,
          outputs, lifetime: str | None = None, resources: list[str] = (), resume: bool = False,
          common: str | None = None, repo: Path | None = None) -> dict:
    """Run ``execute(plan)`` once per key, or return the key's recorded state without executing.

    ``ws`` and ``ident`` name the selected audit (None for repository
    operations, which pass ``common`` and ``repo``); ``lifetime`` is the
    lifetime the caller selected. The key is resolved before the operation
    validates anything else. ``outputs(result)`` lists the output identities a
    completed request records.
    """
    if request_key is None:
        if resume:
            raise StewartError("--resume-request needs the request key it resumes", reason="usage")
        return execute(plan)
    from stewart._repository import maintainer, private_directories, private_storage
    from stewart.implementation import require, viewer
    from stewart.session import now, stamp, write_receipt
    key = key_name(request_key)
    checkout = Path(repo if repo is not None else ws.repo)
    common = common or maintainer(checkout)["common_dir"]
    current = viewer()
    binding = {"operation": operation, "repository": common,
               "audit": None if ws is None else {"workspace": ws.rel, "audit_id": ident},
               "lifetime": lifetime, "resources": sorted(resources),
               "implementation": current["package_sha256"], "inputs": inputs}
    directory = location(common, key)
    private_directories(private_storage(common), directory.parent)
    directory.mkdir(mode=0o700, exist_ok=True)
    (directory / "attempts").mkdir(mode=0o700, exist_ok=True)
    with _locked(directory) as held:
        if not held:
            # Another caller is executing this key now; report that, never a guess from partial records.
            view = inspect(common, key)
            view["replayed"] = True
            return view
        fresh = _publish(directory, {"schema": BINDING_SCHEMA, "key": key, "binding": binding,
                                     "invoked_from": str(checkout), "recorded_at": now().isoformat(),
                                     "stewart": current})
        if not fresh:
            try:
                recorded, _ = _read(directory, key)
            except StewartError as exc:
                raise StewartError(f"request {key} has a binding record that does not verify: {exc}",
                                   reason="request_record_invalid", retained=[str(directory)], code=EXIT_UNVERIFIED,
                                   next_steps=["preserve the request record; use a new key for new work"]) from exc
            if recorded["binding"]["implementation"] != binding["implementation"]:
                require(recorded.get("stewart"), record=directory / "REQUEST.json", arguments=[])
            differing = sorted(field for field in _BINDING_FIELDS if recorded["binding"][field] != binding[field])
            if differing:
                raise StewartError(f"request key {key} is bound to different work (differs in: {', '.join(differing)})",
                                   reason="request_key_conflict", retained=[str(directory)],
                                   next_steps=["reuse a key only for the identical request; use a new key for new work",
                                               f"request --key {key} shows what the key is bound to"])
            view = inspect(common, key, locked=True)
            if view["state"] in ("completed", "refused", "unverifiable") or (view["state"] == "partial"
                                                                             and not resume):
                view["replayed"] = True
                return view
            if view["state"] == "partial" and operation not in RESUMABLE:
                raise StewartError(f"{operation} has no safe resumption; its uncertain outcome is never replayed",
                                   reason="request_not_resumable", retained=[str(directory)],
                                   next_steps=["inspect the planned outputs request --key shows, then decide "
                                               "explicitly; new work needs a new key"])
        attempt = stamp()
        token = _active.set(_Active(directory, attempt, key))
        try:
            result = execute(plan)
        except StewartError as exc:
            write_receipt(directory / "OUTCOME.json", {
                "schema": OUTCOME_SCHEMA, "key": key, "attempt": attempt, "recorded_at": now().isoformat(),
                "status": "refused", "exit_code": exc.exit_code, "error": exc.to_json(), "outputs": []})
            raise
        finally:
            _active.reset(token)
        produced = outputs(result)
        write_receipt(directory / "OUTCOME.json", {
            "schema": OUTCOME_SCHEMA, "key": key, "attempt": attempt, "recorded_at": now().isoformat(),
            "status": "completed", "exit_code": result.get("exit_code", EXIT_OK), "error": None,
            "outputs": produced})
    result["request"] = {"key": key, "state": "completed", "path": str(directory), "replayed": False}
    return result


def _observe(common: str, output: dict) -> dict:
    """Whether a recorded output is available now, retired with its lifetime or resource, missing or changed."""
    observed = dict(output)
    path = output.get("path")
    if not isinstance(path, str):
        return {**observed, "availability": "unknown"}
    if output.get("sha256"):
        info, _ = read_regular(Path(path))
        present = info["kind"] == "file"
        changed = present and info.get("sha256") != output["sha256"]
    else:
        present, changed = os.path.lexists(path), False
    if present:
        return {**observed, "availability": "changed" if changed else "available"}
    retired = False
    audit, lifetime = output.get("audit"), output.get("lifetime")
    if isinstance(audit, dict) and lifetime:
        from stewart.audits import Located
        from stewart.close import closing_entries
        try:
            retired = any(str(entry["session_uuid"]) == lifetime and "problem" not in entry
                          for entry in closing_entries(common, Located(audit.get("slug")), audit.get("audit_id")))
        except (StewartError, TypeError):
            retired = False
    if output.get("resource"):
        from stewart.holdings import retired as resource_retired
        retired = retired or resource_retired(common, output["resource"])
    return {**observed, "availability": "retired" if retired else "missing"}


def inspect(common: str, key: str, *, locked: bool = False) -> dict:
    """The recorded state of one key; reading never repeats a side effect.

    ``locked`` says the caller already holds the request lock; otherwise a
    held lock means another process is executing the request now.
    """
    from stewart.session import capture_receipt
    directory = location(common, key)
    view: dict = {"schema": VIEW_SCHEMA, "key": key, "path": str(directory), "state": "unverifiable",
                  "binding": None, "invoked_from": None, "outcome": None, "attempts": [], "outputs": [],
                  "problems": [], "replayed": False}
    if not os.path.lexists(directory):
        raise StewartError(f"no request is recorded under key {key}", reason="request_missing",
                           next_steps=["discover lists every recorded request key"])
    running = False
    if not locked:
        with _locked(directory) as held:
            running = not held
    try:
        recorded, _ = _read(directory, key)
        view.update(binding=recorded["binding"], invoked_from=recorded.get("invoked_from"),
                    recorded_at=recorded.get("recorded_at"))
    except StewartError as exc:
        if exc.reason == "record_missing" and running:
            view["state"] = "in_progress"
        elif exc.reason == "record_missing":
            raise StewartError(f"no request is recorded under key {key}", reason="request_missing",
                               retained=[str(directory)],
                               next_steps=["a reservation interrupted before its binding was published recorded "
                                           "nothing; the same key and inputs may run"]) from exc
        else:
            view["problems"].append({"reason": "request_record_invalid", "message": str(exc)})
        return _finish_view(view)
    planned = []
    attempts = directory / "attempts"
    for entry in sorted(attempts.iterdir()) if attempts.is_dir() and not attempts.is_symlink() else []:
        if entry.name.startswith(".") or not entry.name.endswith(".json"):
            continue
        try:
            attempt, _ = capture_receipt(entry, what="request attempt")
            view["attempts"].append({"name": entry.name.removesuffix(".json"), "attempt": attempt.get("attempt"),
                                     "planned": attempt.get("planned")})
            planned += [item for item in attempt.get("planned") or [] if isinstance(item, dict)]
        except StewartError as exc:
            view["problems"].append({"reason": "request_record_invalid", "message": str(exc)})
    try:
        outcome, _ = capture_receipt(directory / "OUTCOME.json", what="request outcome")
        if outcome.get("schema") != OUTCOME_SCHEMA or outcome.get("status") not in ("completed", "refused"):
            raise StewartError("request outcome has an unsupported shape", reason="request_record_invalid")
        view["outcome"] = {name: outcome.get(name) for name in ("status", "exit_code", "error", "attempt",
                                                                "recorded_at")}
        view["state"] = outcome["status"]
        view["outputs"] = [_observe(common, item) for item in outcome.get("outputs") or [] if isinstance(item, dict)]
    except StewartError as exc:
        if exc.reason != "record_missing":
            view["problems"].append({"reason": "request_record_invalid", "message": str(exc)})
        else:
            view["state"] = "in_progress" if running else "partial" if view["attempts"] else "reserved"
            view["outputs"] = [_observe(common, item) for item in planned]
    if view["problems"]:
        view["state"] = "unverifiable"
    return _finish_view(view)


def _finish_view(view: dict) -> dict:
    state = view["state"]
    view["exit_code"] = (EXIT_UNVERIFIED if state == "unverifiable" else
                         EXIT_ATTENTION if state in ("partial", "in_progress", "reserved") else
                         (view["outcome"] or {}).get("exit_code", EXIT_OK))
    view["next_steps"] = {
        "completed": ["the work is recorded; each output says whether it is still available or retired; "
                      "nothing is recreated"],
        "refused": ["the request was refused and is not repeated under this key; correct the cause and use a new key"],
        "in_progress": ["another process holds this request now; inspect it again after that process ends"],
        "reserved": ["the request was reserved but no side effect was planned; the same key and inputs may run it"],
        "partial": ["no outcome was recorded: the request was interrupted before or after a side effect. Inspect "
                    "the planned outputs; resume explicitly only where the operation supports it "
                    "(--resume-request); otherwise decide and use a new key"],
        "unverifiable": ["preserve the request records; their state cannot be established"],
    }[state]
    return view


def request_summaries(common: str, problems: list[dict]) -> list[dict]:
    """Every recorded request with its exact key, operation, audit and state, for inspection after a lost key."""
    from stewart.audits import _names
    root = Path(common) / REQUESTS
    names = _names(root)
    if names is None:
        problems.append({"reason": "record_unreadable", "location": str(root),
                         "message": "request storage is not a real directory; nothing below it was read"})
        return []
    summaries = []
    for name in names:
        if not re.fullmatch(r"[0-9a-f]{64}", name):
            continue
        try:
            recorded, _ = _read(root / name)
            view = inspect(common, recorded["key"])
        except StewartError as exc:
            summaries.append({"key": None, "path": str(root / name), "state": "unverifiable",
                              "problems": [exc.to_json()], "exit_code": EXIT_UNVERIFIED})
            continue
        binding = view["binding"] or {}
        summaries.append({"key": view["key"], "path": view["path"], "operation": binding.get("operation"),
                          "audit": binding.get("audit"), "lifetime": binding.get("lifetime"),
                          "state": view["state"], "recorded_at": view.get("recorded_at"),
                          "invoked_from": view.get("invoked_from"), "problems": view["problems"],
                          # A recorded outcome is history; only uncertainty or unverifiable records are news.
                          "exit_code": EXIT_UNVERIFIED if view["state"] == "unverifiable" else
                          EXIT_ATTENTION if view["state"] in ("partial", "in_progress", "reserved") else EXIT_OK})
    return summaries


def show(repo: Path, key: str) -> dict:
    """Inspect one request from any maintainer checkout of the repository."""
    from stewart._repository import observer
    return inspect(observer(Path(repo))["common_dir"], key_name(key))
