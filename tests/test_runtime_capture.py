"""Runtime custody observes hostile bytes without importing them or reading links."""
from __future__ import annotations

import io
import os
from pathlib import Path
import py_compile
import shutil
import sys
import tarfile

import pytest

from stewart import _util, runtime
from stewart._bootstrap import StewartError, runtime_manifest
from stewart._json import loads_control
from stewart.captured import runtime_archive, runtime_observations


@pytest.fixture
def supplied(tmp_path):
    root = tmp_path / "supplied"
    root.mkdir()
    (root / "helper.py").write_text("raise RuntimeError('must never execute during capture')\n")
    return root, runtime.binding(root, runtime_manifest(root))


def observed(tmp_path, identity, name="capture"):
    state = runtime.runtime_state(identity)
    runtime.observe_phase(state, tmp_path, "collection", directory=name)
    return state, runtime_observations(tmp_path, state, phases={"collection"})["collection"]


@pytest.mark.parametrize("damage", ["source", "shadow-package", "valid-pyc", "missing", "link", "fifo", "unreadable", "gone"])
def test_manager_captures_damage_and_preserves_unexpected_bytes(supplied, tmp_path, damage):
    root, identity = supplied
    _, good = observed(tmp_path, identity, "good")
    assert good["matches_expected"] and good["captured_files"] == 1
    helper = root / "helper.py"
    if damage == "source":
        helper.write_text("def verify(): return True\n")
    elif damage == "shadow-package":
        (root / "helper").mkdir()
        (root / "helper/__init__.py").write_text("raise RuntimeError('shadow')\n")
    elif damage == "valid-pyc":
        py_compile.compile(str(helper), cfile=str(root / "__pycache__" / f"helper.{sys.implementation.cache_tag}.pyc"),
                           doraise=True)
    elif damage in {"missing", "link", "fifo"}:
        helper.unlink()
        if damage == "link":
            secret = tmp_path / "private"
            secret.write_bytes(b"must not capture this link target")
            helper.symlink_to(secret)
        elif damage == "fifo":
            os.mkfifo(helper)
    elif damage == "unreadable":
        helper.chmod(0)
    else:
        shutil.rmtree(root)
    try:
        state, bad = observed(tmp_path, identity)
        assert not bad["matches_expected"] and not bad["movement"], damage
        with pytest.raises(StewartError) as caught:
            runtime.require_match(tmp_path, state, phases={"collection"})
        assert caught.value.reason == "runtime_mismatch"
        before = loads_control((tmp_path / "capture/before.json").read_bytes())
        files = {item["path"]: item for item in before["entries"] if item["kind"] == "file"}
        payloads = runtime_archive((tmp_path / "capture/files.tar").read_bytes(), files)
        assert b"must not capture this link target" not in payloads.values()
        if damage == "shadow-package":
            assert payloads["helper/__init__.py"] == b"raise RuntimeError('shadow')\n"
        if damage == "valid-pyc":
            assert any(name.endswith(".pyc") for name in payloads), "unexpected executable files are evidence too"
        if damage == "unreadable":
            assert before["entries"][0]["kind"] == "unreadable", "the unreadable instrument must actually fire"
    finally:
        if damage == "unreadable":
            helper.chmod(0o600)


def test_capture_ignores_project_and_mtime_and_survives_runtime_removal(supplied, tmp_path):
    root, identity = supplied
    (tmp_path / "project.py").write_text("unrelated project change")
    os.utime(root / "helper.py", (1, 1))
    state, capture = observed(tmp_path, identity)
    assert capture["matches_expected"]
    shutil.rmtree(root)
    assert runtime_observations(tmp_path, state, phases={"collection"})["collection"] == capture
    runtime.require_match(tmp_path, state, phases={"collection"})


def test_failed_capture_is_explicit_and_never_passes_execution_or_complete_export(supplied, tmp_path, monkeypatch):
    from stewart.captured import runtime_capture_files, runtime_reference
    root, identity = supplied
    good, _ = observed(tmp_path, identity, "good")
    runtime.require_match(tmp_path, good, phases={"collection"})
    def fail_capture(expected, destination):
        destination.mkdir()
        (destination / "partial-bytes").write_bytes(b"preserved partial capture")
        raise OSError("injected capture failure")
    monkeypatch.setattr(runtime, "capture_runtime", fail_capture)
    state = runtime.runtime_state(identity)
    with pytest.raises(OSError):
        runtime.observe_phase(state, tmp_path, "collection")
    reference = state["observations"]["collection"]
    failed = runtime_observations(tmp_path, state, phases={"collection"})["collection"]
    assert failed["state"] == "failed" and not failed["matches_expected"] and failed["movement"] is None
    assert (tmp_path / reference["directory"] / "partial-bytes").read_bytes() == b"preserved partial capture"
    with pytest.raises(StewartError) as caught:
        runtime.require_match(tmp_path, state, phases={"collection"})
    assert caught.value.reason == "runtime_mismatch"
    with pytest.raises(StewartError) as caught:
        runtime_capture_files(tmp_path, reference)
    assert caught.value.reason == "runtime_capture_unavailable"
    for malformed in ({**reference, "sha256": "0" * 64}, {**reference, "error": {}}, {**reference, "error": None}):
        with pytest.raises(StewartError) as caught:
            runtime_reference(malformed)
        assert caught.value.reason == "runtime_capture_schema"


def test_movement_retains_first_bytes_and_records_both_observations(supplied, tmp_path, monkeypatch):
    root, identity = supplied
    original = runtime.observe_runtime
    calls = []

    def moving(path):
        observation = original(path)
        calls.append(observation)
        if len(calls) == 1:
            (root / "helper.py").write_text("changed between observations\n")
        return observation

    monkeypatch.setattr(runtime, "observe_runtime", moving)
    _, capture = observed(tmp_path, identity)
    assert len(calls) == 2 and capture["movement"] and not capture["matches_expected"]
    files = {entry["path"]: entry for entry in calls[0][0]["entries"] if entry["kind"] == "file"}
    assert runtime_archive((tmp_path / "capture/files.tar").read_bytes(), files) == calls[0][1]


@pytest.mark.parametrize("member", ["capture.json", "before.json", "after.json", "files.tar"])
def test_capture_tampering_refuses_even_when_live_runtime_is_pristine(supplied, tmp_path, member):
    _, identity = supplied
    state, _ = observed(tmp_path, identity)
    (tmp_path / "capture" / member).write_bytes(b"rewritten capture")
    with pytest.raises(StewartError) as caught:
        runtime_observations(tmp_path, state, phases={"collection"})
    assert caught.value.reason == "evidence_tampered"


@pytest.mark.parametrize("damage", ["duplicate", "link", "different-bytes", "extra", "missing"])
def test_archive_checks_members_independently_of_outer_digest(supplied, tmp_path, damage):
    _, identity = supplied
    state, _ = observed(tmp_path, identity)
    directory = tmp_path / "capture"
    before = loads_control((directory / "before.json").read_bytes())
    files = {item["path"]: item for item in before["entries"] if item["kind"] == "file"}
    original = runtime_archive((directory / "files.tar").read_bytes(), files)["helper.py"]
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as bundle:
        names = [] if damage == "missing" else ["helper.py"]
        if damage in {"duplicate", "extra"}:
            names.append("helper.py" if damage == "duplicate" else "added.py")
        for name in names:
            member = tarfile.TarInfo(name)
            data = b"X" * len(original) if damage == "different-bytes" else original
            member.size = len(data)
            if damage == "link":
                member.type, member.linkname, member.size = tarfile.SYMTYPE, "elsewhere", 0
            bundle.addfile(member, io.BytesIO(data))
    # Rehash the synthetic private record to distinguish the member verifier
    # from the outer-byte check above. No real custody record is rewritten.
    archive = buf.getvalue()
    (directory / "files.tar").write_bytes(archive)
    receipt = loads_control((directory / "capture.json").read_bytes())
    receipt["digests"]["files.tar"] = _util.sha256_bytes(archive)
    encoded = _util.receipt_json_bytes(receipt)
    (directory / "capture.json").write_bytes(encoded)
    state["observations"]["collection"]["sha256"] = _util.sha256_bytes(encoded)
    with pytest.raises(StewartError) as caught:
        runtime_observations(tmp_path, state, phases={"collection"})
    assert caught.value.reason == "evidence_tampered"


def test_capture_claims_and_phase_membership_are_checked(supplied, tmp_path):
    _, identity = supplied
    state, _ = observed(tmp_path, identity)
    with pytest.raises(StewartError) as caught:
        runtime_observations(tmp_path, state, phases={"before", "after"})
    assert caught.value.reason == "runtime_capture_schema"


    location = tmp_path / "capture/capture.json"
    record = loads_control(location.read_bytes())
    record["matches_expected"] = False
    data = _util.receipt_json_bytes(record)
    location.write_bytes(data)
    state["observations"]["collection"]["sha256"] = _util.sha256_bytes(data)
    with pytest.raises(StewartError) as caught:
        runtime_observations(tmp_path, state, phases={"collection"})
    assert caught.value.reason == "runtime_capture_schema"


@pytest.mark.parametrize("record", [{}, {"runtime": None}, {"runtime": {}}, {"runtime": []}])
def test_missing_or_replaced_runtime_cannot_discard_prepared_identity(supplied, record):
    _, identity = supplied
    with pytest.raises(StewartError) as caught:
        runtime.record_state(record, session_record={"runtime": identity})
    assert caught.value.reason in {"runtime_capture_schema", "binding_mismatch"}
