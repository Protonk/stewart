"""Actions and references stay bound to the evidence they were derived from.

A status action names its operation, its operands with the digests read for
the view, and the session lifetime; a later collection cannot retarget an
offered close. A reference from another repository, and control records with
repeated or malformed fields, are refused before anything acts on them.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from stewart._bootstrap import EXIT_REFUSED, EXIT_UNVERIFIED, StewartError
from stewart.audits import bind, load_reference, select
from stewart.close import close
from stewart.collect import collect
from stewart.status import status
from stewart.triage import triage
import stewart_support as support
from stewart_support import response_for

pytestmark = pytest.mark.system

IDENT = "one-question"


def _reason(callable_, *args, **kwargs) -> StewartError:
    with pytest.raises(StewartError) as refused:
        callable_(*args, **kwargs)
    return refused.value


def _triaged(checkout):
    prepared = support.prepared_session(checkout)
    collected = collect(checkout.ws, IDENT, auditor_stopped="finished")
    triage(checkout.ws, IDENT, collection=collected["collection"], response=response_for(collected), actor="manager")
    return prepared, collected


def test_actions_name_their_operation_operands_and_lifetime(checkout):
    prepared = support.prepared_session(checkout)
    collected = collect(checkout.ws, IDENT, auditor_stopped="finished")
    view = status(checkout.ws, IDENT)
    draft = next(action for action in view["next_actions"] if action["action"] == "triage-draft")
    assert draft["operation"] == "triage_draft"
    assert draft["operands"] == {"collection": collected["collection"],
                                 "collection_sha256": collected["collection_sha256"]}
    arguments = draft["argv"][draft["argv"].index("--") + 1:]
    assert arguments[4:6] == ["--lifetime", prepared.prepared["session_uuid"]]
    # Invariance: an unchanged session derives the same bound actions again.
    assert status(checkout.ws, IDENT)["next_actions"] == view["next_actions"]


def test_a_new_collection_cannot_retarget_an_offered_close(checkout):
    prepared, collected = _triaged(checkout)
    retain_offered = status(checkout.ws, IDENT)
    disposition = next(d for d in retain_offered["dispositions"] if not d["problems"])
    from stewart.triage import retain
    retain(checkout.ws, IDENT, triage=disposition["name"], report=True)
    offered = next(action for action in status(checkout.ws, IDENT)["next_actions"] if action["action"] == "close")
    assert offered["operands"]["collection"] == collected["collection"], "firing control: close is offered"
    # A later collection of the unchanged checkout is triaged; the old action no longer describes the audit.
    later = collect(checkout.ws, IDENT, auditor_stopped="finished")
    triage(checkout.ws, IDENT, collection=later["collection"], response=response_for(later), actor="manager")
    refused = _reason(close, checkout.ws, IDENT, actor="manager", collection=collected["collection"])
    assert refused.reason == "action_stale" and refused.exit_code == EXIT_REFUSED
    assert prepared.session.is_dir(), "nothing was closed"
    # The current action, bound to the later collection, closes.
    current = next(action for action in status(checkout.ws, IDENT)["next_actions"] if action["action"] == "close")
    assert current["operands"]["collection"] == later["collection"]
    assert close(checkout.ws, IDENT, actor="manager", collection=later["collection"])["closed"]


def test_a_bound_lifetime_never_reaches_a_replacement_lifetime(checkout, monkeypatch):
    from test_close import _failed, _revised_prompt
    from stewart.prepare import prepare
    failed = _failed(checkout, monkeypatch)
    old = failed.record["session_uuid"]
    close(checkout.ws, IDENT, actor="manager", abandon=True, reason="clean failure")
    again = prepare(checkout.ws, _revised_prompt(checkout))
    assert again["session_uuid"] != old and status(checkout.ws, IDENT, lifetime=again["session_uuid"])
    for operation in (lambda: status(checkout.ws, IDENT, lifetime=old),
                      lambda: collect(checkout.ws, IDENT, auditor_stopped="finished", lifetime=old)):
        assert _reason(operation).reason == "reference_stale"
    held = again["reference"]
    assert bind(held).lifetime == again["session_uuid"]


def test_a_reference_from_another_repository_or_with_repeated_keys_is_refused(checkout, tmp_path, run_cmd):
    support.prepared_session(checkout, report=None)
    reference = select(checkout.repo, audit_id=IDENT)["reference"]
    other = support.make_checkout(tmp_path / "other", run_cmd)
    foreign = dict(reference, checkout=str(other.repo))
    assert _reason(bind, foreign).reason == "reference_mismatch"
    assert bind(reference).audit_id == IDENT, "control: the reference itself binds"
    saved = tmp_path / "ref.json"
    text = json.dumps(reference)
    saved.write_text(text[:-1] + ', "audit_id": "' + IDENT + '"}')
    assert _reason(load_reference, saved).reason == "reference_schema", "repeated names never choose a value"
    saved.write_text(json.dumps({**reference, "extra": 1}))
    assert _reason(load_reference, saved).reason == "reference_schema"
    saved.write_text(json.dumps({**reference, "lifetime": "not-a-uuid"}))
    assert _reason(load_reference, saved).reason == "session_identity"
    saved.write_text(json.dumps(reference))
    assert load_reference(saved) == reference
    # The CLI refuses explicit coordinates that disagree with the reference.
    result = run_cmd([sys.executable, "-I", "-B", "-m", "stewart", "--ref", saved, "--workspace", "audits/elsewhere",
                      "--json", "status"], cwd=tmp_path)
    assert result.returncode == EXIT_REFUSED and json.loads(result.stdout)["error"]["reason"] == "reference_mismatch"


def test_request_and_resource_records_with_repeated_keys_do_not_verify(checkout):
    from stewart import api
    from stewart._git import git_text
    prepared = support.prepared_session(checkout)
    api.collect(checkout.ws, IDENT, auditor_stopped="finished", request_key="keyed")
    view = api.inspect_request(checkout.repo, "keyed")
    assert view["state"] == "completed", "control: the untouched request verifies"
    binding = Path(view["path"]) / "REQUEST.json"
    original = binding.read_text()
    binding.chmod(0o600)
    binding.write_text(original[:-2] + ', "key": "keyed"}\n')
    damaged = api.inspect_request(checkout.repo, "keyed")
    assert damaged["state"] == "unverifiable" and damaged["exit_code"] == EXIT_UNVERIFIED
    refused = _reason(api.collect, checkout.ws, IDENT, auditor_stopped="finished", request_key="keyed")
    assert refused.reason == "request_record_invalid" and refused.exit_code == EXIT_UNVERIFIED
    # A resource record with a repeated field is a located problem, never a removal authority.
    rid = api.create_directory(checkout.ws, IDENT, path=str(checkout.tmp / "scratch-dir"), actor="manager")["rid"]
    common = Path(git_text(checkout.repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    record = common / "stewart/resources" / rid / "CREATE.json"
    text = record.read_text()
    record.chmod(0o600)
    record.write_text(text[:-2] + ', "kind": "directory"}\n')
    shown = api.show_resource(checkout.repo, rid)
    assert shown["disposition"] == "blocked" and shown["exit_code"] == EXIT_UNVERIFIED
    assert _reason(api.close_resources, checkout.repo, [rid], actor="manager").reason == "resource_blocked"
    assert (checkout.tmp / "scratch-dir").is_dir()
