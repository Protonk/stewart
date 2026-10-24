"""Characterize which collection a concluded close rests on once a later, untriaged collection exists.

These are inquiry comparisons, not a proposed contract: they record what a
concluded close would rest on, and what it refuses, when one or more
collections follow the triaged one (A). Nothing here performs a close;
``close_plan`` and the read-only preflight it shares with ``close`` are the
only observers, and the session tree is snapshotted around them to show they
write nothing.

``close_plan`` does not report the collection a concluded close would rest on
(it discards the preflight's observations), so two probes establish it: the
plan offered ``--collection A`` is accepted while ``--collection B`` is refused
as ``action_stale`` naming A, and the preflight's ``observed.collection`` is
captured directly. Every observation is saved into the node's directory.

The first executed run of this comparison (hypothesis-framed assertions)
contradicted the source reading for the two runtime-changed cases: a later,
untriaged collection whose runtime capture differs from preparation is the
latest complete collection, status surfaces its unacknowledged ``runtime_changed``
gap as an unverified attention item, and the close is refused
``close_unverified`` naming that collection. Those cases now assert the
observed behavior. The sixth case follows the mechanism one step further: a
later identical collection after the changed one leaves only its own gaps in
attention, so the concluded close again rests on A with the differing
observation unaddressed.

The hypothesis-framed run also expected status to offer close for A. Status
offers close only when no other action is pending, and the fixture always
leaves ``retain`` pending for the triaged collection, so every case asserts
that close is not offered. This docstring was extended after the recorded run
without changing any assertion.
"""
from __future__ import annotations

import json
from pathlib import Path
import tarfile

import pytest

from stewart import _util as _hash
from stewart._bootstrap import StewartError
from stewart.captured import runtime_observations
from stewart.close import _preflight, close_plan
from stewart.collect import collect, inventory
from stewart.status import status
from stewart.triage import triage
import stewart_support as support

pytestmark = pytest.mark.system

MEMBER = "stewart/verify_inputs.py"
# The steps each case takes after collection A is triaged, in order.
CASES = {
    "baseline": [],
    "later_identical": ["collect"],
    "later_runtime_changed_restored": ["change_runtime", "collect", "restore_runtime"],
    "later_runtime_changed_unrestored": ["change_runtime", "collect"],
    "later_checkout_changed": ["change_checkout", "collect"],
    "later_runtime_changed_then_identical": ["change_runtime", "collect", "restore_runtime", "collect"],
}
LATER = "bcdef"


def _save(directory, name, value):
    (directory / f"{name}.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _triage(checkout, collected=None):
    if collected is None:
        collected = collect(checkout.ws, checkout.meta["audit_id"], auditor_stopped="finished")
    disposition = triage(checkout.ws, checkout.meta["audit_id"], collection=collected["collection"],
                         response=support.response_for(collected), actor="fixture manager")
    return collected, disposition


def _observe(collected):
    """One collection's verified collection-phase runtime observation and the member bytes it captured."""
    directory = Path(collected["path"])
    observation = runtime_observations(directory, collected["receipt"]["runtime"], phases={"collection"})["collection"]
    reference = collected["receipt"]["runtime"]["observations"]["collection"]
    with tarfile.open(directory / reference["directory"] / "files.tar", mode="r:") as archive:
        stream = archive.extractfile(MEMBER)
        assert stream is not None
        captured = stream.read()
    return observation, captured


def _rests_on(checkout, ident):
    """What a concluded close would record now, through the read-only preflight close_plan shares, or its refusal."""
    from stewart._repository import _role_records, maintainer, session_location
    common = maintainer(checkout.ws.repo)["common_dir"]
    session = session_location(common, checkout.ws, ident)
    rows = [row for row in _role_records(common) if row["session"] == str(session)]
    try:
        pre = _preflight(checkout.ws, ident, common=common, session=session, rows=rows, abandon=False,
                         discard_uncollected=False, lifetime=None, collection=None)
    except StewartError as exc:
        return {"refusal": exc.to_json(), "observed": None, "attributed": None}
    return {"refusal": None, "observed": pre["observed"], "attributed": pre["attributed"]}


def _differing_paths(before: dict, after: dict) -> set[str]:
    """Inventory paths whose entries differ between two no-follow inventories."""
    first = {entry["path"]: entry for entry in before["entries"]}
    second = {entry["path"]: entry for entry in after["entries"]}
    return {path for path in set(first) | set(second) if first.get(path) != second.get(path)}


def _status_runtime_view(view: dict, name: str):
    """Status's own report of one collection's collection-phase capture, or None where it has none."""
    row = next((c for c in view["collections"] if c["name"] == name), None)
    if row is None or not isinstance(row.get("runtime"), dict):
        return None
    return (row["runtime"].get("observations") or {}).get("collection")


def _refusal(plan: dict | None):
    return None if plan is None else plan["audit"]["refusal"]


def _attention(view: dict) -> list[tuple]:
    return sorted((item["source"], item["reason"], item["message"], item["code"]) for item in view["attention"])


def _plans(checkout, ident, names):
    """The plain plan, one probe per named collection, and the preflight's own observations."""
    planned = close_plan(checkout.ws, ident)
    probes = {name: close_plan(checkout.ws, ident, collection=name) for name in names}
    return planned, probes, _rests_on(checkout, ident)


@pytest.mark.parametrize("case", sorted(CASES))
def test_custody_close_rests_on_triaged_collection_despite_later_return(checkout, tmp_path, case):
    prepared = support.prepared_session(checkout)
    ident = checkout.meta["audit_id"]
    record = support.read_json(prepared.session / "session.json")
    member = Path(record["runtime"]["root"]) / MEMBER
    original = member.read_bytes()
    changed = original + b"\n# fixture runtime-only change, never executed\n"
    tracked = prepared.worktree / "other.txt"
    before_inventory = inventory(prepared.worktree)
    collection_a, disposition_a = _triage(checkout)
    name_a = collection_a["collection"]
    _save(tmp_path, "01-collection-a", collection_a)
    _save(tmp_path, "02-triage-a", disposition_a)

    later: list[dict] = []  # each later collection with its verified observation and captured member bytes
    for step in CASES[case]:
        if step == "change_runtime":
            member.write_bytes(changed)
        elif step == "restore_runtime":
            member.write_bytes(original)
        elif step == "change_checkout":
            with tracked.open("ab") as stream:
                stream.write(b"later manager edit inside the checkout, never collected into a triage\n")
        elif step == "collect":
            collected = collect(checkout.ws, ident, auditor_stopped="finished")
            observation, captured = _observe(collected)
            letter = LATER[len(later)]
            later.append({"letter": letter, "collected": collected, "observation": observation, "captured": captured})
            _save(tmp_path, f"03-collection-{letter}", collected)
            _save(tmp_path, f"04-verified-runtime-observation-{letter}", observation)
            assert collected["collection"] != name_a
            assert observation["movement"] is False
        else:  # pragma: no cover - CASES names every step above
            raise AssertionError(step)
    names = [item["collected"]["collection"] for item in later]
    assert len(set(names)) == len(names)

    before_records = support.snapshot_tree(prepared.session)
    view = status(checkout.ws, ident)
    planned, probes, preflight = _plans(checkout, ident, [name_a, *names])
    _save(tmp_path, "05-status", view)
    _save(tmp_path, "06-close-plan", planned)
    _save(tmp_path, "07-close-plan-probe-a", probes[name_a])
    for item in later:
        _save(tmp_path, f"07-close-plan-probe-{item['letter']}", probes[item["collected"]["collection"]])
    _save(tmp_path, "08-preflight-observed", preflight)
    assert support.snapshot_tree(prepared.session) == before_records

    after_inventory = inventory(prepared.worktree)
    actions = [action["action"] for action in view["next_actions"]]
    summary = {
        "case": case,
        "steps": CASES[case],
        "collection_a": name_a,
        "triage_a": disposition_a["triage"],
        "later_collections": [{
            "letter": item["letter"], "name": item["collected"]["collection"],
            "matches_expected": item["observation"]["matches_expected"], "movement": item["observation"]["movement"],
            "captured_member": MEMBER, "captured_sha256": _hash.sha256_bytes(item["captured"]),
            "captured_equals_original": item["captured"] == original,
            "captured_equals_changed": item["captured"] == changed,
            "receipt_errors": item["collected"]["receipt"].get("errors"),
            "gaps": item["collected"].get("gaps"),
            "inventory_sha256": (item["collected"]["receipt"].get("inventory") or {}).get("sha256"),
            "status_runtime_view": _status_runtime_view(view, item["collected"]["collection"]),
        } for item in later],
        "a_inventory_sha256": (collection_a["receipt"].get("inventory") or {}).get("sha256"),
        "member_bytes_at_plan": "original" if member.read_bytes() == original else "changed",
        "checkout_paths_changed_since_prepare": sorted(_differing_paths(before_inventory, after_inventory)),
        "status_attention": _attention(view),
        "status_next_actions": actions,
        "status_preparation_state": view["preparation"].get("state"),
        "close_plan_refusal": _refusal(planned),
        "probe_refusals": {name: _refusal(plan) for name, plan in probes.items()},
        "preflight_rests_on": (preflight["observed"] or {}).get("collection"),
        "preflight_triage": (preflight["observed"] or {}).get("triage"),
        "preflight_refusal": preflight["refusal"],
    }
    _save(tmp_path, "09-summary", summary)

    # Status offers close only when nothing else is pending; the fixture always leaves `retain` pending for
    # the triaged collection, and every later case leaves the latest collection untriaged.
    assert "close" not in actions
    if case == "later_checkout_changed":
        assert _differing_paths(before_inventory, after_inventory) == {"other.txt"}
        assert summary["later_collections"][0]["inventory_sha256"] != summary["a_inventory_sha256"]
    else:
        assert after_inventory == before_inventory
        for item in later:
            assert (item["collected"]["receipt"].get("inventory") or {}).get("sha256") == summary["a_inventory_sha256"]
    for item in later:
        assert _status_runtime_view(view, item["collected"]["collection"]) is not None

    def rests_on(name, disposition_name, *, among):
        """The plain plan is allowed, the probe for ``name`` is allowed, every other probe is stale naming it."""
        assert _refusal(planned) is None
        assert _refusal(probes[name]) is None
        for other in among:
            if other != name:
                assert _refusal(probes[other])["reason"] == "action_stale"
                assert name in _refusal(probes[other])["message"]
        assert preflight["refusal"] is None
        assert preflight["observed"]["collection"]["name"] == name
        assert preflight["observed"]["triage"]["name"] == disposition_name

    if case == "baseline":
        assert view["attention"] == []
        rests_on(name_a, disposition_a["triage"], among=[name_a])
    elif case == "later_identical":
        b = later[0]
        assert b["observation"]["matches_expected"] is True and b["captured"] == original
        # B's only gap is the fixture report's missing declaration, an attention item (1), not unverified (3).
        assert {item["reason"] for item in view["attention"]} == {"custody_gap"}
        assert {item["code"] for item in view["attention"]} == {1}
        assert {item["source"] for item in view["attention"]} == {f"collection {names[0]}"}
        rests_on(name_a, disposition_a["triage"], among=[name_a, *names])
    elif case == "later_runtime_changed_restored":
        b = later[0]
        assert b["observation"]["matches_expected"] is False and b["captured"] == changed
        assert [error["reason"] for error in b["collected"]["receipt"]["errors"]] == ["runtime_changed"]
        # Observed, contrary to the source reading: B is the latest complete collection and untriaged, so
        # its runtime_changed gap is an unverified attention item and the concluded close is refused.
        assert {item["reason"] for item in view["attention"]} == {"custody_gap"}
        assert {item["source"] for item in view["attention"]} == {f"collection {names[0]}"}
        assert ("collection_error:0", 3) in {(item["message"], item["code"]) for item in view["attention"]}
        for plan in (planned, *probes.values()):
            assert _refusal(plan)["reason"] == "close_unverified" and _refusal(plan)["exit_code"] == 3
            assert names[0] in _refusal(plan)["message"]
        assert preflight["refusal"]["reason"] == "close_unverified"
        # Acknowledging B's gaps through triage moves the close onto B: the later evidence is addressed by
        # the manager's disposition, not by any comparison of its content with A.
        _, disposition_b = _triage(checkout, b["collected"])
        _save(tmp_path, "10-triage-b", disposition_b)
        after_triage = support.snapshot_tree(prepared.session)
        added = sorted(set(after_triage) - set(before_records))
        _save(tmp_path, "10-triage-b-session-additions", added)
        assert all(after_triage[path] == before_records[path] for path in before_records)
        assert str(Path(disposition_b["path"]).relative_to(prepared.session)) in added
        view_b = status(checkout.ws, ident)
        planned, probes, preflight = _plans(checkout, ident, [name_a, *names])
        _save(tmp_path, "11-status-after-triage-b", view_b)
        _save(tmp_path, "12-close-plan-after-triage-b", planned)
        _save(tmp_path, "12-close-plan-after-triage-b-probe-a", probes[name_a])
        _save(tmp_path, "12-close-plan-after-triage-b-probe-b", probes[names[0]])
        _save(tmp_path, "13-preflight-observed-after-triage-b", preflight)
        assert support.snapshot_tree(prepared.session) == after_triage
        assert view_b["attention"] == []
        rests_on(names[0], disposition_b["triage"], among=[name_a, *names])
        assert _observe(b["collected"])[0] == b["observation"]
    elif case == "later_runtime_changed_unrestored":
        b = later[0]
        assert b["observation"]["matches_expected"] is False and b["captured"] == changed
        assert {item["reason"] for item in view["attention"]} == {"custody_gap", "runtime_unavailable"}
        assert _refusal(planned)["reason"] == "close_unverified" and _refusal(planned)["exit_code"] == 3
        assert "runtime_unavailable" in _refusal(planned)["message"] and names[0] in _refusal(planned)["message"]
        assert preflight["refusal"]["reason"] == "close_unverified"
        # Restoring the live runtime removes only the runtime_unavailable reason; B's recorded gap still
        # refuses the close, unlike the single-collection case where restoration alone sufficed.
        member.write_bytes(original)
        restored = close_plan(checkout.ws, ident)
        restored_view = status(checkout.ws, ident)
        _save(tmp_path, "10-restored-close-plan", restored)
        _save(tmp_path, "11-restored-status", restored_view)
        assert support.snapshot_tree(prepared.session) == before_records
        assert {item["reason"] for item in restored_view["attention"]} == {"custody_gap"}
        assert _refusal(restored)["reason"] == "close_unverified" and _refusal(restored)["exit_code"] == 3
        assert "runtime_unavailable" not in _refusal(restored)["message"]
        assert _observe(b["collected"])[0] == b["observation"]
    elif case == "later_checkout_changed":
        b = later[0]
        assert b["observation"]["matches_expected"] is True and b["captured"] == original
        assert {item["reason"] for item in view["attention"]} == {"custody_gap"}
        assert {item["code"] for item in view["attention"]} == {1}
        assert _refusal(planned)["reason"] == "checkout_changed" and _refusal(planned)["exit_code"] == 2
        assert _refusal(probes[name_a])["reason"] == "checkout_changed"
        # The offered-collection check precedes the checkout comparison: the audit still rests on A.
        assert _refusal(probes[names[0]])["reason"] == "action_stale"
        assert name_a in _refusal(probes[names[0]])["message"]
        assert preflight["refusal"]["reason"] == "checkout_changed"
    elif case == "later_runtime_changed_then_identical":
        # The firing case the source reading predicts: B recorded a runtime differing from preparation
        # with identical checkout bytes; a later identical C hides B's gap from attention, and the
        # concluded close rests on A with B's observation unaddressed.
        b, c = later
        assert b["observation"]["matches_expected"] is False and b["captured"] == changed
        assert c["observation"]["matches_expected"] is True and c["captured"] == original
        assert [error["reason"] for error in b["collected"]["receipt"]["errors"]] == ["runtime_changed"]
        assert {item["source"] for item in view["attention"]} == {f"collection {names[1]}"}
        assert {item["code"] for item in view["attention"]} == {1}
        rests_on(name_a, disposition_a["triage"], among=[name_a, *names])
    else:  # pragma: no cover - the parametrization names every case above
        raise AssertionError(case)
