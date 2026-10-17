"""Control JSON refuses ambiguity; raw evidence remains byte-preserving.

Unique counterparts and formatting/order variations exercise the useful paths.
Rehashed duplicate metadata distinguishes semantic refusal from digest checks.
The child control fires before its duplicate-bearing evidence is exported.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from stewart import _util as _hash
from stewart.assignment import initialize
from stewart._bootstrap import StewartError
from stewart.experiment import release, run
from stewart.handoff import export_evidence, package_inputs
from stewart.prepare import prepare
from stewart.session import capture_receipt
import stewart_support as support
from test_stewart_handoff import captured, export
from test_stewart_launch_profile import profile, write_profile

pytestmark = pytest.mark.system


@pytest.mark.parametrize("raw", [
    '{"key":1,"key":1}', '{"key":1,"key":2}', '{"key":2,"key":1}',
    '{"outer":[{"key":1,"key":2}]}', r'{"key":1,"\u006bey":2}',
])
def test_control_receipt_refuses_repeats_and_preserves_bytes(tmp_path, raw):
    location = tmp_path / "record.json"
    location.write_text(raw)
    before = support.snapshot_tree(tmp_path)
    with pytest.raises(StewartError) as caught:
        capture_receipt(location, what="custody record")
    assert caught.value.reason == "record_corrupt" and "key" in str(caught.value)
    assert caught.value.retained == [str(location)] and caught.value.next_steps
    assert support.snapshot_tree(tmp_path) == before


@pytest.mark.parametrize("raw", [
    '{"outer":[{"key":1},{"key":2}],"key":3}',
    ' { "key": 3, "outer": [ {"key": 1}, {"key": 2} ] }\n',
    r'{"outer":[{"\u006bey":1},{"key":2}],"key":3}',
])
def test_control_receipt_accepts_distinct_objects_and_unique_representation_variants(tmp_path, raw):
    location = tmp_path / "record.json"
    location.write_text(raw)
    decoded, digest = capture_receipt(location, what="custody record")
    assert decoded == {"outer": [{"key": 1}, {"key": 2}], "key": 3}
    assert digest == _hash.sha256_bytes(raw.encode()), "semantic equivalence does not normalize custody bytes"


@pytest.mark.parametrize("mutation", ["identical", "conflicting", "escaped", "nested", "unique", "reordered"])
def test_profile_uniqueness_is_checked_before_session_allocation(checkout, mutation):
    doc = profile(env={"TZ": "UTC"})
    raw = json.dumps(doc)
    if mutation == "identical":
        raw = raw.replace('"model": "opus"', '"model": "opus", "model": "opus"', 1)
    elif mutation == "conflicting":
        raw = raw.replace('"model": "opus"', '"model": "other", "model": "opus"', 1)
    elif mutation == "escaped":
        raw = raw.replace('"model": "opus"', '"model": "opus", "mo\\u0064el": "opus"', 1)
    elif mutation == "nested":
        raw = raw.replace('"env": {"TZ": "UTC"}', '"env": {"TZ": "UTC", "TZ": "UTC"}')
    elif mutation == "reordered":
        raw = json.dumps(dict(reversed(list(doc.items()))), indent=3) + "\n"
    location = write_profile(checkout, doc)
    location.write_text(raw)
    revision = checkout.prompt_commit()
    if mutation in {"unique", "reordered"}:
        result = prepare(checkout.ws, revision)
        assert result["launch_profile"]["sha256"] == _hash.sha256_bytes((location).read_bytes())
        assert "--model opus" in result["launch_command"]
    else:
        with pytest.raises(StewartError) as caught:
            prepare(checkout.ws, revision)
        assert caught.value.reason == "launch_profile" and "unique keys" in str(caught.value)
        assert not (checkout.repo / ".scratch").exists(), "reject before allocating custody state"
    assert location.read_text() == raw


@pytest.mark.parametrize("mutation", ["root", "nested", "escaped", "unique", "reordered"])
def test_pinned_protected_manifest_cannot_choose_endpoint_population(tmp_path, run_cmd, mutation):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    location = checkout.repo / support.MANIFEST
    doc = support.read_json(location)
    raw = json.dumps(doc)
    if mutation == "root":
        raw = raw.replace('"files":', '"files": {}, "files":', 1)
    elif mutation in {"nested", "escaped"}:
        key = '"input.txt"' if mutation == "nested" else '"input\\u002etxt"'
        raw = raw.replace('"input.txt":', key + ': "' + '0' * 64 + '", "input.txt":', 1)
    elif mutation == "reordered":
        doc["files"] = dict(reversed(list(doc["files"].items())))
        raw = json.dumps(dict(reversed(list(doc.items()))), indent=3) + "\n"
    location.write_text(raw)
    checkout.git("add", "--", support.MANIFEST)
    checkout.git("commit", "-qm", "Pin protected-manifest specimen")
    checkout.meta["target_commit"] = checkout.git("rev-parse", "HEAD")
    checkout.prompt_text = support.assignment_text(checkout.meta, extra_sections=support.AUTHORIZATION)
    exp = support.prepared_experiment(checkout)
    before = support.snapshot_tree(exp.session)
    if mutation in {"unique", "reordered"}:
        result = release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
        assert result["record"]["frozen"][support.MANIFEST] == _hash.sha256_bytes((location).read_bytes())
    else:
        with pytest.raises(StewartError) as caught:
            release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
        assert caught.value.reason == "record_corrupt", "ambiguous pinned bytes, not input drift, must cause refusal"
        after = support.snapshot_tree(exp.session)
        assert all(after[name] == value for name, value in before.items()), "refusal preserves all prior evidence"
        assert not list((exp.session / "releases").glob("*.json")), "observing a runtime does not authorize a release"
        assert not (exp.session / "attempts").exists(), "refusal cannot reserve an attempt"
        assert list((exp.session / "releases").glob("runtime-*/capture.json")), "retain the preceding runtime observation"
    assert (exp.worktree / support.MANIFEST).read_text() == raw


@pytest.mark.parametrize("member,mutation", [
    ("manifest", "root"), ("manifest", "nested"), ("source", "root"),
    ("source", "nested"), ("source", "stale_digest"), ("source", "reordered"),
])
def test_package_control_bytes_need_both_identity_and_unique_names(checkout, member, mutation):
    _, collection, _ = captured(checkout)
    exported = export(checkout, collection, ["REPORT.md"])
    location = checkout.repo / exported["package"]
    manifest = support.read_json(location)
    target = location if member == "manifest" else location.parent / "source.json"
    doc = support.read_json(target)
    raw = json.dumps(doc)
    if mutation == "reordered":
        raw = json.dumps(dict(reversed(list(doc.items()))), indent=3) + "\n"
    elif mutation == "nested":
        # A duplicate in irrelevant tool metadata must still be refused; field
        # selection cannot silently erase ambiguity before validating the object.
        raw = raw.replace('"stewart": {', '"stewart": {"extra": 1, "extra": 1,', 1)
    else:
        first = next(iter(doc))
        encoded = json.dumps(first) + ":"
        raw = raw.replace(encoded, encoded + json.dumps(doc[first]) + ", " + encoded, 1)
    assert raw != json.dumps(doc), "the intended raw specimen must actually change bytes"
    target.write_text(raw)
    if member == "source" and mutation != "stale_digest":
        manifest["source"]["receipt_sha256"] = _hash.sha256_bytes((target).read_bytes())
        location.write_text(json.dumps(manifest))
    before = support.snapshot_tree(checkout.repo)
    kwargs = dict(inputs=[], evidence_packages=[exported["package"]],
                  input_manifest=".scratch/receiver.json", replace_prompt=True)
    if mutation == "reordered":
        result = initialize(checkout.ws, "receiver", "HEAD", **kwargs)
        assert result["written"] and len(package_inputs(checkout.repo, exported["package"])) == 3
    else:
        with pytest.raises(StewartError) as caught:
            initialize(checkout.ws, "receiver", "HEAD", **kwargs)
        reason = "evidence_tampered" if mutation == "stale_digest" else (
            "record_corrupt" if member == "manifest" else "package_schema")
        assert caught.value.reason == reason
        assert support.snapshot_tree(checkout.repo) == before, "refuse before publishing inventory or replacing prompt"


def test_duplicate_raw_child_evidence_survives_attempt_export_and_import(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    # Append raw fixtures after the normal child writes. Every ledger row has
    # repeated kind names; the existing control still disagrees.
    exp.script.write_text(exp.script.read_text() + '''
raw_receipt = b'{"claim": "earlier", "claim": "later"}\\n'
(output / "receipt.json").write_bytes(raw_receipt)
rows = output / "ledger.jsonl"
rows.write_bytes(rows.read_bytes().replace(b'"kind":', b'"kind": "discarded", "kind":'))
''')
    released = release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
    attempted = run(checkout.ws, "one-question", release=released["release"], timeout=30)
    assert attempted["errors"] == []
    record = attempted["record"]
    assert record["child_receipt"]["state"] == "parsed"
    assert record["ledger"]["summary"]["control"]["mismatches"] == 1
    assert record["ledger"]["summary"]["ordinary"]["compared"] == 2
    exported = export_evidence(checkout.ws, "one-question", attempt=attempted["attempt"],
                               selectors=["child-receipt.json", "ledger.jsonl"],
                               output=".scratch/raw-package", actor="manager")
    package = checkout.repo / exported["package"]
    manifest = support.read_json(package)
    for entry in manifest["entries"]:
        retained = (Path(attempted["path"]) / entry["selector"]).read_bytes()
        assert (package.parent / entry["file"]).read_bytes() == retained
        if entry["selector"] == "child-receipt.json":
            assert retained.count(b'"claim":') == 2
        else:
            assert b'"discarded"' in retained, "the raw ledger specimen must actually contain duplicate names"
    result = initialize(checkout.ws, "raw-receiver", "HEAD", inputs=[], evidence_packages=[exported["package"]])
    assert len(result["assignment"]["supplemental_inputs"]) == 4, "payloads remain opaque when control metadata is decoded"
