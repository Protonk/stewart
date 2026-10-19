"""Request keys: one exclusive binding per caller-chosen key, one recorded outcome, no replayed uncertainty.

A key names intended work within one repository. The tests drive the
installed wheel through ``stewart.api`` and the CLI in a fresh isolated
process, in disposable repositories whose workspace (``audits/ws``) has no
relation to any real one. Each measured guarantee pairs a firing control (the
condition happened: a side effect exists, a lock is held, a record names
another build) with a case differing only in the measured property and an
invariance case (records and collections unchanged by a replay, inspection
or refusal).
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import threading

import pytest

from stewart import api
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, EXIT_UNVERIFIED, StewartError
from stewart._git import git_text
from stewart.close import closed_location
from stewart.request_keys import location
import stewart_support as support
from stewart_support import response_for, snapshot_tree

pytestmark = pytest.mark.system

IDENT = "one-question"


# --- helpers -------------------------------------------------------------------------------------------


def _common(checkout) -> Path:
    return Path(git_text(checkout.repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))


def _records(checkout) -> dict[str, str]:
    """Every Stewart record under the Git common directory, for write-nothing proofs."""
    return snapshot_tree(_common(checkout) / "stewart")


def _collections(checkout) -> list[str]:
    folder = support.session_path(checkout, IDENT) / "collections"
    return sorted(entry.name for entry in folder.iterdir()) if folder.is_dir() else []


def _request(checkout, key: str) -> Path:
    return location(str(_common(checkout)), key)


def _collect(checkout, key: str | None = None, *, stopped: str = "finished", ident: str = IDENT, **kwargs) -> dict:
    return api.collect(checkout.ws, ident, auditor_stopped=stopped, request_key=key, **kwargs)


def _refusal(callable_, *args, **kwargs) -> StewartError:
    with pytest.raises(StewartError) as refused:
        callable_(*args, **kwargs)
    return refused.value


def _cli(run_cmd, checkout, *argv, allowed=(EXIT_OK,)) -> dict:
    """One fresh isolated process from the installed wheel; returns its JSON envelope."""
    command = [sys.executable, "-I", "-B", "-m", "stewart", "--json", "--repo", str(checkout.repo), *map(str, argv)]
    result = run_cmd(command, cwd=checkout.tmp)
    assert result.returncode in allowed, f"{argv}: {result.returncode}\n{result.stdout}\n{result.stderr}"
    envelope = json.loads(result.stdout)
    assert envelope["schema"] == "stewart.result/3" and envelope["exit_code"] == result.returncode
    return envelope


def _cli_collect(run_cmd, checkout, key: str, *extra, allowed=(EXIT_OK, EXIT_ATTENTION)) -> dict:
    return _cli(run_cmd, checkout, "--workspace", checkout.ws.rel, f"--request-key={key}", *extra, "collect",
                "--audit-id", IDENT, "--auditor-stopped", "finished", allowed=allowed)


def _triaged(checkout):
    prepared = support.prepared_session(checkout)
    collected = api.collect(checkout.ws, IDENT, auditor_stopped="finished")
    api.triage(checkout.ws, IDENT, collection=collected["collection"], response=response_for(collected),
               actor="manager")
    return prepared, collected


def _interrupt_close(checkout, monkeypatch, key: str) -> Path:
    """A keyed close interrupted after CLOSING.json and before its checkout's removal; returns its directory."""
    import stewart.close as close_module

    def interrupted(parent, name):
        raise KeyboardInterrupt("synthetic interruption before checkout removal")

    with monkeypatch.context() as patch:
        patch.setattr(close_module, "_delete_checkout", interrupted)
        with pytest.raises(KeyboardInterrupt):
            api.close(checkout.ws, IDENT, actor="manager", request_key=key)
    folder = closed_location(str(_common(checkout)), checkout.ws, IDENT)
    (directory,) = list(folder.iterdir())
    return directory


def _folds_case(root: Path) -> bool:
    probe = root / "Case-Probe"
    probe.mkdir()
    try:
        return os.path.lexists(root / "case-probe")
    finally:
        probe.rmdir()


# --- 1. key grammar and exact keys ------------------------------------------------------------------------


BAD_KEYS = ["", "-leading-dash", ".leading-dot", "_leading-underscore", "has space", "a/b", "..", "k" * 129,
            "ключ", "café", "line\nbreak", "tab\tkey", "semi;colon"]


def test_key_grammar_is_refused_before_anything_else_is_validated_or_recorded(checkout, run_cmd):
    support.prepared_session(checkout)
    requests = _common(checkout) / "stewart/requests"
    before = _records(checkout)
    for bad in BAD_KEYS:
        refused = _refusal(_collect, checkout, bad)
        assert refused.reason == "request_key_format" and refused.exit_code == EXIT_REFUSED, bad
    assert _refusal(_collect, checkout, 7).reason == "request_key_format", "a non-string key is not a key"
    # Invariance: the key is resolved first, so a missing audit cannot answer before the grammar does.
    assert _refusal(_collect, checkout, "-leading-dash", ident="never-prepared").reason == "request_key_format"
    for bad in ("-leading-dash", "has space", "k" * 129):
        envelope = _cli_collect(run_cmd, checkout, bad, allowed=(EXIT_REFUSED,))
        assert envelope["error"]["reason"] == "request_key_format", bad
    assert _records(checkout) == before and not requests.exists(), "a refused key records nothing"
    assert _collections(checkout) == []
    # Firing control: keys at the grammar's edges are accepted and recorded exactly.
    for good in ("k" * 128, "0", "A.b_c-9"):
        result = _collect(checkout, good)
        assert result["request"]["key"] == good and result["request"]["replayed"] is False
        assert support.read_json(_request(checkout, good) / "REQUEST.json")["key"] == good
    assert len(_collections(checkout)) == 3


def test_keys_differing_only_in_case_are_two_requests_with_their_exact_keys(checkout, tmp_path):
    support.prepared_session(checkout)
    folds = _folds_case(tmp_path)
    if folds:
        # Firing control: on this filesystem, directories named by the keys themselves would be one entry.
        (tmp_path / "Collect-Case").mkdir()
        assert os.path.lexists(tmp_path / "collect-case"), "this filesystem folds case"
    upper = _collect(checkout, "Collect-Case")
    lower = _collect(checkout, "collect-case")
    assert upper["request"]["replayed"] is False and lower["request"]["replayed"] is False, \
        "the second key executed instead of answering from the first key's record"
    assert upper["collection"] != lower["collection"] and len(_collections(checkout)) == 2
    upper_dir, lower_dir = _request(checkout, "Collect-Case"), _request(checkout, "collect-case")
    assert upper_dir.name.lower() != lower_dir.name.lower(), "record names stay distinct under case folding"
    assert upper_dir.is_dir() and lower_dir.is_dir() and not os.path.samefile(upper_dir, lower_dir)
    assert support.read_json(upper_dir / "REQUEST.json")["key"] == "Collect-Case"
    assert support.read_json(lower_dir / "REQUEST.json")["key"] == "collect-case"
    # Invariance: each key keeps answering with its own collection, and nothing new is captured.
    assert _collect(checkout, "Collect-Case")["outputs"][0]["name"] == upper["collection"]
    assert _collect(checkout, "collect-case")["outputs"][0]["name"] == lower["collection"]
    assert api.inspect_request(checkout.repo, "Collect-Case")["key"] == "Collect-Case"
    assert len(_collections(checkout)) == 2
    found = {item["key"] for item in api.discover(checkout.repo)["requests"]}
    assert found == {"Collect-Case", "collect-case"}


# --- 2. completed replay, distinct keys, conflicts, no deduplication without a key ------------------------


def test_completed_keyed_collect_replays_its_collection_without_capturing_again(checkout, run_cmd):
    support.prepared_session(checkout)
    first = _collect(checkout, "collect-1")
    assert first["request"] == {"key": "collect-1", "state": "completed", "replayed": False,
                                "path": str(_request(checkout, "collect-1"))}
    collections, records = _collections(checkout), _records(checkout)
    assert collections == [first["collection"]], "control: the first call captured one collection"

    replay = _collect(checkout, "collect-1")
    assert replay["schema"] == "stewart.request/1" and replay["state"] == "completed" and replay["replayed"]
    (output,) = replay["outputs"]
    assert output["name"] == first["collection"] and output["sha256"] == first["collection_sha256"]
    assert output["availability"] == "available" and output["lifetime"] == first["session_uuid"]
    assert replay["exit_code"] == first["exit_code"] and "collection" not in replay
    assert _collections(checkout) == collections and _records(checkout) == records, \
        "a replay creates no collection and changes no record"
    # The same replay through a fresh process.
    envelope = _cli_collect(run_cmd, checkout, "collect-1")
    assert envelope["result"]["state"] == "completed" and envelope["result"]["replayed"]
    assert envelope["result"]["outputs"][0]["name"] == first["collection"]
    assert _collections(checkout) == collections and _records(checkout) == records


def test_distinct_keys_and_unkeyed_submissions_are_separate_collections(checkout):
    support.prepared_session(checkout)
    first = _collect(checkout, "collect-a")
    second = _collect(checkout, "collect-b")
    # Control: the report bytes are identical, so only the key distinguishes the requests.
    assert first["receipt"]["report_sha256"] == second["receipt"]["report_sha256"]
    assert first["collection"] != second["collection"]
    assert first["collection_sha256"] != second["collection_sha256"]
    requests = sorted(entry.name for entry in (_common(checkout) / "stewart/requests").iterdir())
    # Without a key every call is a new request: nothing is deduplicated by payload or time.
    third, fourth = _collect(checkout), _collect(checkout)
    assert "request" not in third and "request" not in fourth
    assert len({first["collection"], second["collection"], third["collection"], fourth["collection"]}) == 4
    assert third["receipt"]["report_sha256"] == fourth["receipt"]["report_sha256"] == first["receipt"]["report_sha256"]
    assert len(_collections(checkout)) == 4
    assert sorted(entry.name for entry in (_common(checkout) / "stewart/requests").iterdir()) == requests, \
        "an unkeyed call records no request"
    # Invariance: each key still answers with its own collection.
    assert _collect(checkout, "collect-a")["outputs"][0]["name"] == first["collection"]
    assert _collect(checkout, "collect-b")["outputs"][0]["name"] == second["collection"]
    assert len(_collections(checkout)) == 4


def test_same_key_with_different_inputs_is_refused_naming_the_differing_field(checkout, run_cmd):
    prepared = support.prepared_session(checkout)
    first = _collect(checkout, "collect-1")
    request = _request(checkout, "collect-1")
    collections, records = _collections(checkout), _records(checkout)

    refused = _refusal(_collect, checkout, "collect-1", stopped="interrupted")
    assert refused.reason == "request_key_conflict" and refused.exit_code == EXIT_REFUSED
    assert "differs in: inputs" in str(refused) and str(request) in refused.retained
    # The bound lifetime is part of the binding too.
    rebound = _refusal(_collect, checkout, "collect-1", lifetime=prepared.prepared["session_uuid"])
    assert rebound.reason == "request_key_conflict" and "differs in: lifetime" in str(rebound)
    envelope = _cli(run_cmd, checkout, "--workspace", checkout.ws.rel, "--request-key", "collect-1", "collect",
                    "--audit-id", IDENT, "--auditor-stopped", "blocked", allowed=(EXIT_REFUSED,))
    assert envelope["error"]["reason"] == "request_key_conflict" and "inputs" in envelope["error"]["message"]
    assert _collections(checkout) == collections and _records(checkout) == records, \
        "a conflicting retry executes nothing and records nothing"
    # Changed property only: the identical inputs replay; a new key runs the other input.
    assert _collect(checkout, "collect-1")["outputs"][0]["name"] == first["collection"]
    other = _collect(checkout, "collect-2", stopped="interrupted")
    assert other["receipt"]["auditor_stop_kind"] == "interrupted" and len(_collections(checkout)) == 2


# --- 3. concurrency ---------------------------------------------------------------------------------------


#: Where the executing caller is held when the second same-key caller arrives.
WINDOWS = {
    "binding-unpublished": ("stewart.request_keys", "_publish"),
    "binding-published": ("stewart.collect", "mutable_session"),
    "outputs-planned": ("stewart.collect", "capture_report"),
}


@pytest.mark.heavy
@pytest.mark.parametrize("window", sorted(WINDOWS))
def test_concurrent_same_key_submissions_admit_one_execution(checkout, monkeypatch, run_cmd, window):
    import stewart._repository as repository_module
    import stewart.collect as collect_module
    support.prepared_session(checkout)
    key = "collect-race"
    module_name, attribute = WINDOWS[window]
    module = importlib.import_module(module_name)
    held, second_returned, release = threading.Event(), threading.Event(), threading.Event()
    guard = threading.Lock()
    executions: list[int] = []
    leader: list[int] = []
    paused: list[int] = []

    real_collect = collect_module._collect

    def counted(*args, **kwargs):
        executions.append(threading.get_ident())
        return real_collect(*args, **kwargs)

    original = getattr(module, attribute)

    def pause(*args, **kwargs):
        with guard:
            first = not paused
            paused.append(threading.get_ident())
        if first:
            held.set()
            assert release.wait(120), "the test never released the executing caller"
        return original(*args, **kwargs)

    real_private = repository_module.private_directories

    def ordered(*args, **kwargs):
        # Both threads leave the barrier together; the one that reaches the request first runs, and the other
        # is let through only once the first is held inside its execution, so it arrives while that runs.
        with guard:
            if not leader:
                leader.append(threading.get_ident())
        if leader[0] != threading.get_ident():
            assert held.wait(120), "the executing caller never reached its window"
        return real_private(*args, **kwargs)

    monkeypatch.setattr(collect_module, "_collect", counted)
    monkeypatch.setattr(module, attribute, pause)
    monkeypatch.setattr(repository_module, "private_directories", ordered)
    barrier = threading.Barrier(2)
    results: dict[str, object] = {}

    def submit(name: str):
        try:
            barrier.wait(60)
            results[name] = _collect(checkout, key)
        except BaseException as exc:  # noqa: BLE001 - surfaced on the test thread below
            results[name] = exc
        finally:
            if leader and leader[0] != threading.get_ident():
                second_returned.set()

    threads = {name: threading.Thread(target=submit, args=(name,), daemon=True) for name in ("a", "b")}
    for thread in threads.values():
        thread.start()
    try:
        assert held.wait(120), "control: one caller entered its execution"
        assert second_returned.wait(120), "the second caller returned while the first was held"
        # Firing control: the first caller holds the request now, as an independent inspection observes.
        assert api.inspect_request(checkout.repo, key)["state"] == "in_progress"
        # A caller in another process at the same moment.
        other_process = _cli_collect(run_cmd, checkout, key, allowed=(EXIT_ATTENTION, EXIT_UNVERIFIED))["result"]
    finally:
        release.set()
        for thread in threads.values():
            thread.join(120)
    assert not any(thread.is_alive() for thread in threads.values())
    errors = {name: value for name, value in results.items() if isinstance(value, BaseException)}
    assert not errors, errors
    executed = [value for value in results.values() if "request" in value]
    answered = [value for value in results.values() if value.get("schema") == "stewart.request/1"]
    assert len(executions) == 1 and len(paused) == 1, "exactly one caller executed"
    assert len(executed) == 1 and len(answered) == 1
    (winner,), (second,) = executed, answered
    assert winner["request"]["state"] == "completed" and winner["request"]["replayed"] is False
    assert _collections(checkout) == [winner["collection"]], "exactly one collection was created"
    assert second["replayed"] and "collection" not in second
    # Invariance: once the execution ends, the same key answers with its one collection.
    replay = _collect(checkout, key)
    assert replay["state"] == "completed" and replay["outputs"][0]["name"] == winner["collection"]
    assert _collections(checkout) == [winner["collection"]]
    # Measured: a caller that arrives while another holds the request is told it is in progress.
    assert {"thread": (second["state"], second["exit_code"]), "process": (other_process["state"],
                                                                         other_process["exit_code"])} == {
        "thread": ("in_progress", EXIT_ATTENTION), "process": ("in_progress", EXIT_ATTENTION)}, window


# --- 4. interruption before and after the side effect -----------------------------------------------------


def _interrupt_before_planning(checkout, monkeypatch, key: str) -> None:
    """Interrupt a keyed collect after its binding is published and before it plans any output."""
    import stewart.collect as collect_module

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt("synthetic interruption before the collection is planned")

    with monkeypatch.context() as patch:
        patch.setattr(collect_module, "mutable_session", interrupted)
        with pytest.raises(KeyboardInterrupt):
            _collect(checkout, key)


def _interrupt_before_outcome(checkout, monkeypatch, key: str) -> None:
    """Interrupt a keyed collect after collection.json is written and before OUTCOME.json."""
    import stewart.session as session_module
    real_write = session_module.write_receipt

    def interrupted(destination, value, **kwargs):
        if Path(destination).name == "OUTCOME.json":
            raise KeyboardInterrupt("synthetic interruption before the outcome record")
        return real_write(destination, value, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(session_module, "write_receipt", interrupted)
        with pytest.raises(KeyboardInterrupt):
            _collect(checkout, key)


def test_interruption_before_any_side_effect_leaves_a_reserved_request_that_runs_once(checkout, monkeypatch):
    support.prepared_session(checkout)
    request = _request(checkout, "collect-r")
    _interrupt_before_planning(checkout, monkeypatch, "collect-r")
    # Firing control: the binding was published, and no side effect was planned or happened.
    assert (request / "REQUEST.json").is_file() and not (request / "OUTCOME.json").exists()
    assert list((request / "attempts").iterdir()) == [] and _collections(checkout) == []
    view = api.inspect_request(checkout.repo, "collect-r")
    assert view["state"] == "reserved" and view["attempts"] == [] and view["outputs"] == []
    assert view["exit_code"] == EXIT_ATTENTION and view["binding"]["operation"] == "collect"

    retried = _collect(checkout, "collect-r")
    assert retried["request"]["state"] == "completed" and retried["request"]["replayed"] is False
    assert _collections(checkout) == [retried["collection"]], "the reserved request ran exactly once"
    assert len(list((request / "attempts").iterdir())) == 1
    assert support.read_json(request / "OUTCOME.json")["status"] == "completed"
    # Invariance: a further retry answers from the record.
    again = _collect(checkout, "collect-r")
    assert again["replayed"] and again["outputs"][0]["name"] == retried["collection"]
    assert _collections(checkout) == [retried["collection"]]


def test_interruption_after_the_side_effect_is_partial_and_never_replayed(checkout, monkeypatch, run_cmd):
    support.prepared_session(checkout)
    request = _request(checkout, "collect-p")
    _interrupt_before_outcome(checkout, monkeypatch, "collect-p")
    # Firing control: the collection was captured; only the outcome is missing.
    (planned,) = _collections(checkout)
    collection = support.session_path(checkout, IDENT) / "collections" / planned
    assert (collection / "collection.json").is_file() and not (request / "OUTCOME.json").exists()
    (attempt,) = list((request / "attempts").iterdir())
    assert [item["name"] for item in support.read_json(attempt)["planned"]] == [planned]
    records = snapshot_tree(request)

    retry = _collect(checkout, "collect-p")
    assert retry["schema"] == "stewart.request/1" and retry["state"] == "partial" and retry["replayed"]
    assert retry["exit_code"] == EXIT_ATTENTION and "collection" not in retry
    assert [(item["name"], item["availability"]) for item in retry["outputs"]] == [(planned, "available")]
    envelope = _cli_collect(run_cmd, checkout, "collect-p", allowed=(EXIT_ATTENTION,))
    assert envelope["result"]["state"] == "partial" and envelope["result"]["replayed"]
    assert _collections(checkout) == [planned] and snapshot_tree(request) == records, \
        "an uncertain request is reported, never replayed"
    # Changed property: a fresh key is new work and captures again.
    fresh = _collect(checkout, "collect-p2")
    assert fresh["request"]["replayed"] is False
    assert sorted(_collections(checkout)) == sorted([planned, fresh["collection"]])


def test_explicit_resumption_of_a_partial_collect_is_refused(checkout, monkeypatch, run_cmd):
    support.prepared_session(checkout)
    request = _request(checkout, "collect-p")
    _interrupt_before_outcome(checkout, monkeypatch, "collect-p")
    (planned,) = _collections(checkout)
    records = snapshot_tree(request)
    # Control: without the flag the same key reports its uncertainty.
    plain = _cli_collect(run_cmd, checkout, "collect-p", allowed=(EXIT_ATTENTION,))
    assert plain["result"]["state"] == "partial"
    # Collection has no safe resumption (only close has): an explicit resume is refused, and nothing runs.
    resumed = _cli_collect(run_cmd, checkout, "collect-p", "--resume-request",
                           allowed=(EXIT_OK, EXIT_ATTENTION, EXIT_REFUSED, EXIT_UNVERIFIED))
    # Invariance: either way, no collection is captured and the request records are unchanged.
    assert _collections(checkout) == [planned] and snapshot_tree(request) == records
    assert (resumed["exit_code"], (resumed["error"] or {}).get("reason")) == (EXIT_REFUSED, "request_not_resumable"), \
        {"exit_code": resumed["exit_code"], "error": resumed["error"],
         "state": (resumed["result"] or {}).get("state")}


# --- 5. refusals are recorded outcomes ---------------------------------------------------------------------


def test_a_refused_keyed_request_returns_its_recorded_refusal_without_executing(checkout, run_cmd):
    refused = _refusal(_collect, checkout, "collect-x")
    assert refused.reason == "session_missing"
    request = _request(checkout, "collect-x")
    outcome = support.read_json(request / "OUTCOME.json")
    # Firing control: the refusal itself is the recorded outcome.
    assert outcome["status"] == "refused" and outcome["error"]["reason"] == "session_missing"
    assert outcome["exit_code"] == EXIT_REFUSED and outcome["outputs"] == []

    # The cause is fixed: the audit is prepared now. The key still names the refused work.
    support.prepared_session(checkout)
    records = snapshot_tree(request)
    replay = _collect(checkout, "collect-x")
    assert replay["state"] == "refused" and replay["replayed"] and replay["exit_code"] == EXIT_REFUSED
    assert replay["outcome"]["error"]["reason"] == "session_missing"
    envelope = _cli_collect(run_cmd, checkout, "collect-x", allowed=(EXIT_REFUSED,))
    assert envelope["result"]["state"] == "refused" and envelope["error"]["reason"] == "session_missing"
    assert _collections(checkout) == [] and snapshot_tree(request) == records, "the refused key never executes"
    # Changed property: a new key proceeds now that the cause is fixed.
    fresh = _collect(checkout, "collect-y")
    assert fresh["request"]["state"] == "completed" and _collections(checkout) == [fresh["collection"]]


# --- 6. keyed close resumption -----------------------------------------------------------------------------


@pytest.mark.heavy
def test_interrupted_keyed_close_is_partial_until_explicitly_resumed(checkout, monkeypatch, run_cmd):
    prepared, _ = _triaged(checkout)
    directory = _interrupt_close(checkout, monkeypatch, "close-k")
    request = _request(checkout, "close-k")
    # Firing control: the closing record exists, removal has not happened, and no outcome was recorded.
    assert (directory / "CLOSING.json").is_file() and not (directory / "CLOSED.json").exists()
    assert prepared.worktree.is_dir() and prepared.session.is_dir()
    assert not (request / "OUTCOME.json").exists() and len(list((request / "attempts").iterdir())) == 1
    before = {"records": _records(checkout), "worktree": snapshot_tree(prepared.worktree)}

    pending = api.close(checkout.ws, IDENT, actor="manager", request_key="close-k")
    assert pending["state"] == "partial" and pending["replayed"] and pending["exit_code"] == EXIT_ATTENTION
    envelope = _cli(run_cmd, checkout, "--workspace", checkout.ws.rel, "--request-key", "close-k", "close",
                    "--audit-id", IDENT, "--actor", "manager", allowed=(EXIT_ATTENTION,))
    assert envelope["result"]["state"] == "partial"
    assert {"records": _records(checkout), "worktree": snapshot_tree(prepared.worktree)} == before, \
        "a partial close is reported, and nothing is removed or recorded"

    resumed = api.close(checkout.ws, IDENT, actor="manager", request_key="close-k", resume=True)
    assert resumed["closed"] == str(directory / "CLOSED.json") and resumed["resumed"] is True
    assert resumed["request"]["state"] == "completed" and resumed["request"]["replayed"] is False
    assert not prepared.worktree.exists() and not prepared.session.exists()
    view = api.inspect_request(checkout.repo, "close-k")
    assert view["state"] == "completed" and len(view["attempts"]) == 2, "the resumption appended an attempt"
    closed = (directory / "CLOSED.json").read_bytes()
    records = _records(checkout)
    # Invariance: the completed key answers from its record, with or without --resume-request.
    for extra in ((), ("--resume-request",)):
        again = _cli(run_cmd, checkout, "--workspace", checkout.ws.rel, "--request-key", "close-k", *extra, "close",
                     "--audit-id", IDENT, "--actor", "manager")
        assert again["result"]["state"] == "completed" and again["result"]["replayed"]
    assert _records(checkout) == records and (directory / "CLOSED.json").read_bytes() == closed


@pytest.mark.heavy
def test_keyed_close_finished_by_an_unkeyed_rerun_is_recorded_completed_when_resumed(checkout, monkeypatch):
    prepared, _ = _triaged(checkout)
    directory = _interrupt_close(checkout, monkeypatch, "close-k")
    request = _request(checkout, "close-k")
    finished = api.close(checkout.ws, IDENT, actor="manager")
    # Firing control: the unkeyed rerun finished the same close.
    assert finished["resumed"] is True and finished["closed"] == str(directory / "CLOSED.json")
    assert "request" not in finished and not prepared.worktree.exists()
    closed = (directory / "CLOSED.json").read_bytes()
    # Changed property: without an explicit resume the key still reports its own uncertainty.
    pending = api.close(checkout.ws, IDENT, actor="manager", request_key="close-k")
    assert pending["state"] == "partial" and not (request / "OUTCOME.json").exists()
    assert {item["kind"]: item["availability"] for item in pending["outputs"]} == {"closing": "available",
                                                                                   "closed": "available"}

    resumed = api.close(checkout.ws, IDENT, actor="manager", request_key="close-k", resume=True)
    assert resumed["request"]["state"] == "completed" and resumed["closing"] == str(directory / "CLOSING.json")
    outcome = support.read_json(request / "OUTCOME.json")
    assert outcome["status"] == "completed" and outcome["outputs"][0]["path"] == str(directory / "CLOSING.json")
    assert (directory / "CLOSED.json").read_bytes() == closed, "the finished close is reported, not redone"
    assert sorted(entry.name for entry in directory.iterdir()) == ["CLOSED.json", "CLOSING.json"]
    # Invariance: the request now answers completed.
    assert api.inspect_request(checkout.repo, "close-k")["state"] == "completed"


# --- 7. history after closeout, inspection and discovery -------------------------------------------------


@pytest.mark.heavy
def test_retry_after_closeout_reports_retired_outputs_and_recreates_nothing(checkout, run_cmd):
    prepared = support.prepared_session(checkout)
    first = _collect(checkout, "collect-h")
    api.triage(checkout.ws, IDENT, collection=first["collection"], response=response_for(first), actor="manager")
    # Changed property: before closeout the same output is available.
    assert api.inspect_request(checkout.repo, "collect-h")["outputs"][0]["availability"] == "available"
    api.close(checkout.ws, IDENT, actor="manager")
    # Firing control: the collection's lifetime was retired with its session.
    assert not prepared.session.exists() and not prepared.worktree.exists()
    records = _records(checkout)

    retry = _collect(checkout, "collect-h")
    assert retry["state"] == "completed" and retry["replayed"]
    assert [(item["name"], item["availability"]) for item in retry["outputs"]] == [(first["collection"], "retired")]
    envelope = _cli_collect(run_cmd, checkout, "collect-h")
    assert [item["availability"] for item in envelope["result"]["outputs"]] == ["retired"]
    assert not prepared.session.exists() and _records(checkout) == records, "retry recreates nothing"
    # Invariance: new work under a new key is refused; the closed session is not reopened.
    assert _refusal(_collect, checkout, "collect-after").reason == "session_missing"
    assert not prepared.session.exists()


def test_inspection_writes_nothing_and_discovery_lists_requests_after_a_lost_key(checkout, monkeypatch, run_cmd):
    prepared = support.prepared_session(checkout)
    done = _collect(checkout, "k-done")
    _refusal(_collect, checkout, "k-refused", ident="absent-audit")
    _interrupt_before_planning(checkout, monkeypatch, "k-reserved")
    _interrupt_before_outcome(checkout, monkeypatch, "k-partial")
    _collect(checkout)  # unkeyed: no request record
    expected = {"k-done": "completed", "k-refused": "refused", "k-reserved": "reserved", "k-partial": "partial"}
    worktree = snapshot_tree(prepared.worktree)
    records = _records(checkout)

    # Inspection reads each state and executes nothing, in process and through the CLI.
    for key, state in expected.items():
        assert api.inspect_request(checkout.repo, key)["state"] == state, key
        envelope = _cli(run_cmd, checkout, "request", "--key", key,
                        allowed=(EXIT_OK, EXIT_ATTENTION, EXIT_REFUSED))
        assert envelope["result"]["state"] == state and envelope["result"]["replayed"] is False, key
    assert api.inspect_request(checkout.repo, "k-done")["outputs"][0]["name"] == done["collection"]
    missing = _refusal(api.inspect_request, checkout.repo, "never-submitted")
    assert missing.reason == "request_missing"
    assert _cli(run_cmd, checkout, "request", "--key", "never-submitted",
                allowed=(EXIT_REFUSED,))["error"]["reason"] == "request_missing"
    assert _records(checkout) == records and snapshot_tree(prepared.worktree) == worktree, "inspection writes nothing"
    assert api.inspect_request(checkout.repo, "k-reserved")["state"] == "reserved", "inspection did not run it"

    # The caller lost its keys: discovery lists every recorded request with its exact key, and nothing else.
    found = api.discover(checkout.repo)
    listed = {item["key"]: item for item in found["requests"]}
    assert set(listed) == set(expected)
    for key, state in expected.items():
        assert listed[key]["operation"] == "collect" and listed[key]["state"] == state, key
        assert listed[key]["audit"] == {"workspace": checkout.ws.rel,
                                        "audit_id": "absent-audit" if key == "k-refused" else IDENT}
        # Each listed key reselects its request explicitly.
        assert api.inspect_request(checkout.repo, listed[key]["key"])["path"] == listed[key]["path"]
    assert _records(checkout) == records, "discovery writes nothing"


# --- 8. implementation identity --------------------------------------------------------------------------


def _copy_request(checkout, source: str, key: str, *, implementation: str | None, outcome: bool) -> Path:
    """A fixture request under ``key`` copied from ``source``, optionally recorded by another implementation."""
    origin, target = _request(checkout, source), _request(checkout, key)
    target.mkdir(mode=0o700)
    (target / "attempts").mkdir(mode=0o700)

    def copy(path: Path, destination: Path) -> None:
        value = support.read_json(path)
        value["key"] = key
        if implementation is not None and "binding" in value:
            value["binding"]["implementation"] = implementation
            value["stewart"]["package_sha256"] = implementation
        destination.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")

    copy(origin / "REQUEST.json", target / "REQUEST.json")
    if outcome:
        for attempt in (origin / "attempts").iterdir():
            copy(attempt, target / "attempts" / attempt.name)
        copy(origin / "OUTCOME.json", target / "OUTCOME.json")
    return target


def test_a_request_recorded_by_another_implementation_is_refused_on_retry(checkout, run_cmd):
    support.prepared_session(checkout)
    first = _collect(checkout, "impl-k")
    current = api.tool_identity()["package_sha256"]
    other = hashlib.sha256(b"another Stewart build").hexdigest()
    same = _copy_request(checkout, "impl-k", "impl-same", implementation=None, outcome=True)
    completed = _copy_request(checkout, "impl-k", "impl-other", implementation=other, outcome=True)
    reserved = _copy_request(checkout, "impl-k", "impl-other-reserved", implementation=other, outcome=False)
    # Firing control: the copies record another writer, and are still readable for inspection.
    assert other != current
    for key in ("impl-other", "impl-other-reserved"):
        view = api.inspect_request(checkout.repo, key)
        assert view["binding"]["implementation"] == other and view["state"] in ("completed", "reserved"), key
    records = {path: snapshot_tree(path) for path in (same, completed, reserved)}
    collections = _collections(checkout)

    # Changed property only: the same copy under this implementation replays.
    replay = _collect(checkout, "impl-same")
    assert replay["state"] == "completed" and replay["outputs"][0]["name"] == first["collection"]
    for key in ("impl-other", "impl-other-reserved"):
        refused = _refusal(_collect, checkout, key)
        assert refused.reason == "implementation_mismatch" and refused.exit_code == EXIT_REFUSED, key
        assert refused.handoff["state"] == "unresolved" and "invocation" in refused.handoff["missing"]
    envelope = _cli_collect(run_cmd, checkout, "impl-other-reserved", allowed=(EXIT_REFUSED,))
    assert envelope["error"]["reason"] == "implementation_mismatch" and "handoff" in envelope["error"]
    # Invariance: nothing executed or was recorded, and the original key still replays.
    assert _collections(checkout) == collections
    assert {path: snapshot_tree(path) for path in records} == records
    assert not (reserved / "OUTCOME.json").exists() and list((reserved / "attempts").iterdir()) == []
    assert _collect(checkout, "impl-k")["outputs"][0]["name"] == first["collection"]
