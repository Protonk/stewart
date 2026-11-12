#!/usr/bin/env python3
"""Review complete return packages; rehearse ONLY with the existing synthetic harness.

review_package launches nothing. --rehearse runs an actual gated Stewart binary
with synthetic Driver fixtures, never an installed profile, login or real model.
Run with python3 -I -B; see CLAUDE-CODE-SERVICE-WITNESS.md.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import answer_witness as answer
import claude_code as runtime
from rawjson import compact

WITNESS_SCHEMA = "stewart.claude-code.service-witness/1"
REVIEW_SCHEMA = "stewart.claude-code.service-package-review/1"
MAX_FILE = 64 * 1024 * 1024
MAX_PACKAGE = 256 * 1024 * 1024
SOURCE_NAMES = (Path(__file__).name, "answer_witness.py", "claude_code.py", "driver_core.py", "rawjson.py")
PENDING = ["real-harness profile eligibility and bounded commission", "live full-service comparison",
           "externally triggered interruption", "real compaction and post-compaction observations",
           "turn-cap and output-request enforcement", "Linux qualification"]


def _save(path, value):
    with Path(path).open("xb") as stream:
        stream.write(compact(value) + b"\n")


def _absolute(path):
    path = Path(path)
    if not path.is_absolute() or str(path) != os.path.normpath(str(path)):
        raise ValueError("path must be normalized and absolute: " + str(path))
    return path


def _overlap(left, right):
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _open_directory(path):
    """Walk every component through no-follow descriptors, including ancestors."""
    path = _absolute(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            following = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = following
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _directory_ancestors(path):
    """Inode identities catch containment under case aliases as well as spelling."""
    identities = set()
    current = _absolute(path)
    while True:
        descriptor = _open_directory(current)
        try:
            info = os.fstat(descriptor)
            identities.add((info.st_dev, info.st_ino))
        finally:
            os.close(descriptor)
        if current == current.parent:
            return identities
        current = current.parent


def _protected_directory_identity(path):
    try:
        descriptor = _open_directory(path)
    except OSError:
        return None  # The subsequent protected input read retains its failure.
    try:
        info = os.fstat(descriptor)
        return info.st_dev, info.st_ino
    finally:
        os.close(descriptor)


def _read_at(directory, name, limit=MAX_FILE):
    before = os.stat(name, dir_fd=directory, follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("not a regular file: " + name)
    if before.st_size > limit:
        raise ValueError("capture bound exceeded: " + name)
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _identity(opened) != _identity(before):
            raise ValueError("file identity changed before read: " + name)
        chunks, count = [], 0
        while True:
            chunk = os.read(descriptor, min(65536, limit - count + 1))
            if not chunk:
                break
            count += len(chunk)
            if count > limit:
                raise ValueError("capture bound exceeded during read: " + name)
            chunks.append(chunk)
        after = os.fstat(descriptor)
        named = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if _identity(before) != _identity(after) or _identity(after) != _identity(named):
            raise ValueError("file changed during read: " + name)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_file(path):
    directory = _open_directory(path.parent)
    try:
        return _read_at(directory, path.name)
    finally:
        os.close(directory)


def _write_at(directory, name, raw):
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("incomplete evidence write: " + name)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _blob(raw):
    return {"bytes": len(raw), "sha256": runtime.sha(raw), "raw_hex": raw.hex()}


def _unblob(value):
    if not isinstance(value, dict) or set(value) != {"bytes", "sha256", "raw_hex"}:
        raise ValueError("invalid input byte binding")
    raw = bytes.fromhex(value["raw_hex"])
    if type(value["bytes"]) is not int or value["bytes"] != len(raw) or value["sha256"] != runtime.sha(raw):
        raise ValueError("input byte binding differs")
    return raw


def write_witness(path, entries, revision, *, family, writer, actor, reference, status_raw, inputs, provenance):
    """Freeze attributed expectations once; return the pin required by review_package.

    Entry bytes and revision are the caller's outside witness. Audit/store and
    seal time come from manager replies and are identified separately as such.
    This function grants no authenticity to a caller's provenance declaration.
    """
    if any(entry.unproduced for entry in entries):
        raise ValueError("this comparison requires produced witness entries")
    status = runtime.transport_loads(status_raw)
    parts = reference.split(":", 3)
    if len(parts) != 4 or parts[0] != "stw1":
        raise ValueError("manager reference is not a Stewart reference")
    seal = status["data"]["seal"]
    value = {"schema": WITNESS_SCHEMA,
             "selection": {"revision": revision, "entries": [
                 {"id": entry.id, "version": entry.version, "kind": entry.kind, "label": entry.label,
                  "encoding": entry.encoding, "data_hex": entry.data.hex(), "citations": entry.citations}
                 for entry in entries]},
             "bindings": {"audit": parts[1], "store": parts[2], "family": family, "writer": writer,
                          "actor": actor, "sealed_at": seal["sealed_at"]},
             "inputs": {name: _blob(raw) for name, raw in inputs.items()},
             "provenance": provenance,
             "manager_observations": {"reference": reference, "status": _blob(status_raw),
                 "attribution": "audit/store identifiers and seal timestamp are learned through the manager interface, not independently predicted"}}
    path = _absolute(path)
    raw = compact(value) + b"\n"
    parent = _open_directory(path.parent)
    try:
        _write_at(parent, path.name, raw)
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            os.fchmod(descriptor, 0o400)
        finally:
            os.close(descriptor)
    finally:
        os.close(parent)
    return runtime.sha(raw)


def expected_package(value):
    """Reconstruct from frozen witness inputs, never from the delivered answer."""
    if not isinstance(value, dict) or value.get("schema") != WITNESS_SCHEMA:
        raise ValueError("unsupported service witness schema")
    if set(value) != {"schema", "selection", "bindings", "inputs", "provenance", "manager_observations"}:
        raise ValueError("unexpected service witness members")
    if not isinstance(value["provenance"], dict) or not all(
            isinstance(value["provenance"].get(key), str) and value["provenance"][key]
            for key in ("kind", "description")):
        raise ValueError("explicit selection provenance is required")
    if not isinstance(value["inputs"], dict) or not value["inputs"]:
        raise ValueError("outside input witnesses are required")
    for raw in value["inputs"].values():
        _unblob(raw)
    binding = value["bindings"]
    if set(binding) != {"audit", "store", "family", "writer", "actor", "sealed_at"}:
        raise ValueError("unexpected package binding members")
    if binding["family"] not in {name + "/1" for name in runtime.FAMILY_TEXT}:
        raise ValueError("unknown witness family")
    if not re.fullmatch(r"[0-9a-f]{64}", binding["writer"]):
        raise ValueError("invalid writer digest")
    if binding["actor"] not in {"auditor", "manager"}:
        raise ValueError("invalid seal actor")
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", binding["sealed_at"]):
        raise ValueError("invalid manager seal timestamp")
    manager = value["manager_observations"]
    parts = manager["reference"].split(":", 3)
    if len(parts) != 4 or parts[0] != "stw1" or parts[1:3] != [binding["audit"], binding["store"]]:
        raise ValueError("manager reference bindings differ")
    status = runtime.transport_loads(_unblob(manager["status"]))
    seal = status["data"]["seal"]
    selection = value["selection"]
    revision = selection["revision"]
    if type(revision) is not int or revision < 0 or set(selection) != {"revision", "entries"}:
        raise ValueError("invalid witness selection")
    if seal.get("state") != "present" or any(seal.get(key) != expected for key, expected in (
            ("actor", binding["actor"]), ("sealed_at", binding["sealed_at"]), ("revision", revision))):
        raise ValueError("manager seal observation differs from expected bindings")
    entries, ids = [], set()
    kinds = {tool["name"] for tool in runtime.expected_tools(binding["family"].removesuffix("/1"))
             if tool["name"].startswith("record_")}
    for entry in selection["entries"]:
        if set(entry) != {"id", "version", "kind", "label", "encoding", "data_hex", "citations"}:
            raise ValueError("invalid witness entry members")
        if not re.fullmatch(r"e[1-9][0-9]*", entry["id"]) or entry["id"] in ids:
            raise ValueError("invalid or duplicate witness entry ID")
        if type(entry["version"]) is not int or entry["version"] < 1 or entry["kind"] not in kinds:
            raise ValueError("invalid witness entry version or kind")
        if not isinstance(entry["label"], str) or not isinstance(entry["citations"], list):
            raise ValueError("invalid witness entry label or citations")
        if entry["kind"] == "record_artifact":
            if entry["encoding"] not in {"text", "binary"}:
                raise ValueError("invalid artifact encoding")
        elif entry["encoding"] is not None:
            raise ValueError("non-artifact encoding is not null")
        ids.add(entry["id"])
        entries.append(answer.Entry(entry["id"], entry["version"], entry["kind"], entry["label"],
                                    bytes.fromhex(entry["data_hex"]), entry["citations"], entry["encoding"]))
    raw = answer.answer_json(revision, entries)
    rendering = answer.render(entries)
    files = {"answer.json": raw, "answer.md": rendering}
    files.update({entry.member: entry.data for entry in entries if entry.kind == "record_artifact"})
    files["manifest.json"] = answer.manifest(binding["audit"], binding["store"], binding["family"],
        binding["writer"], binding["actor"], binding["sealed_at"], revision, answer.members(entries, raw, rendering))
    return files


def _manifest(root):
    rows = []
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("evidence contains a nonregular member: " + str(path))
        if path == root / "EVIDENCE.json":
            continue
        raw = _read_file(path)
        rows.append({"path": path.relative_to(root).as_posix(), "bytes": len(raw), "sha256": runtime.sha(raw)})
    return {"schema": "stewart.claude-code.service-evidence/1", "members": rows}


def review_package(package, witness_file, evidence_dir, *, witness_sha256, archive_root):
    """Launch-free review. Unsafe output locations refuse before any write.

    A safe fresh output retains diagnostics even when package/witness reads fail.
    Unlisted directories, links and specials are inventoried but never traversed.
    No archive content is read. Evidence is not a live-profile attestation.
    """
    package, witness_file, evidence_dir, archive_root = map(_absolute, (package, witness_file, evidence_dir, archive_root))
    if (_overlap(evidence_dir, package) or _overlap(evidence_dir, archive_root)
            or _overlap(evidence_dir, witness_file) or _overlap(witness_file, package)
            or _overlap(witness_file, archive_root)):
        raise ValueError("evidence and expected witness must remain outside package and archive")
    output_ancestors = _directory_ancestors(evidence_dir.parent)
    try:
        witness_ancestors = _directory_ancestors(witness_file.parent)
    except OSError:
        witness_ancestors = set()  # Unsafe witness ancestry is captured below.
    for protected in (package, archive_root):
        identity = _protected_directory_identity(protected)
        if identity is not None and identity in output_ancestors | witness_ancestors:
            raise ValueError("inode containment: output or witness lies inside package or archive")
    parent = _open_directory(evidence_dir.parent)
    try:
        os.mkdir(evidence_dir.name, mode=0o700, dir_fd=parent)
    finally:
        os.close(parent)
    result = {"schema": REVIEW_SCHEMA, "package": str(package), "witness": str(witness_file),
              "witness_sha256": witness_sha256, "qualification": False,
              "scope": "exact return-byte comparison against attributed outside witnesses; no semantic-quality or profile-eligibility claim",
              "outcome": "failed", "diagnostics": [], "inventory": [], "checks": [], "complete_capture": False}
    def check(name, passed, detail=None):
        row = {"name": name, "passed": bool(passed)}
        if not passed:
            row["detail"] = detail
        result["checks"].append(row)
    expected, observed = {}, {}
    try:
        raw = _read_file(witness_file)
        (evidence_dir / "WITNESS.json").write_bytes(raw)
        check("witness-pin", runtime.sha(raw) == witness_sha256, "expected witness bytes changed")
        if runtime.sha(raw) != witness_sha256:
            raise ValueError("expected witness digest differs from caller's pin")
        value = runtime.transport_loads(raw)
        expected = expected_package(value)
        result["provenance"] = value["provenance"]
        result["manager_attribution"] = value["manager_observations"]["attribution"]
        (evidence_dir / "expected").mkdir()
        for name, data in expected.items():
            (evidence_dir / "expected" / name).write_bytes(data)
        check("expected-input-bindings", True)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        result["diagnostics"].append({"stage": "expected-witness", "type": type(error).__name__, "detail": str(error)})
        check("expected-witness-readable-valid", False, str(error))
    (evidence_dir / "actual").mkdir()
    actual_fd = _open_directory(evidence_dir / "actual")
    package_fd = None
    try:
        package_fd = _open_directory(package)
        initial = os.fstat(package_fd)
        check("package-mode", stat.S_IMODE(initial.st_mode) == 0o700, stat.S_IMODE(initial.st_mode))
        names = sorted(os.listdir(package_fd))
        total = 0
        for name in names:
            row = {"name": name}
            result["inventory"].append(row)
            try:
                info = os.stat(name, dir_fd=package_fd, follow_symlinks=False)
                row["mode"] = stat.S_IMODE(info.st_mode)
                if stat.S_ISDIR(info.st_mode):
                    row["type"] = "directory"
                elif stat.S_ISLNK(info.st_mode):
                    row.update(type="symlink", target=os.readlink(name, dir_fd=package_fd))
                elif not stat.S_ISREG(info.st_mode):
                    row["type"] = "special"
                else:
                    row["type"] = "regular"
                    data = _read_at(package_fd, name, min(MAX_FILE, MAX_PACKAGE - total))
                    total += len(data)
                    observed[name] = data
                    _write_at(actual_fd, name, data)
                    row.update(bytes=len(data), sha256=runtime.sha(data), snapshot="actual/" + name)
                check("regular-file:" + name, row["type"] == "regular", row["type"])
                if row["type"] == "regular":
                    check("file-mode:" + name, row["mode"] == 0o600, row["mode"])
            except (OSError, ValueError) as error:
                row["error"] = str(error)
                result["diagnostics"].append({"stage": "package-member", "name": name, "detail": str(error)})
                check("member-captured:" + name, False, str(error))
        unchanged = names == sorted(os.listdir(package_fd)) and _identity(initial) == _identity(os.fstat(package_fd))
        # Recheck every captured file after the complete inventory to detect
        # replacements during another member's read.
        for name, data in observed.items():
            unchanged = (_read_at(package_fd, name) == data) and unchanged
        check("package-stable-during-observation", unchanged)
        result["complete_capture"] = unchanged and len(observed) == len(names)
        check("complete-package-capture", result["complete_capture"])
        check("member-inventory", bool(expected) and set(names) == set(expected),
              {"missing": sorted(set(expected) - set(names)), "extra": sorted(set(names) - set(expected))})
        for name, data in expected.items():
            check("exact-bytes:" + name, observed.get(name) == data)
    except (OSError, ValueError) as error:
        result["diagnostics"].append({"stage": "package", "type": type(error).__name__, "detail": str(error)})
        check("package-readable-complete", False, str(error))
    finally:
        if package_fd is not None:
            os.close(package_fd)
        os.close(actual_fd)
    result["counts"] = {"checks": len(result["checks"]), "passed": sum(row["passed"] for row in result["checks"]),
                        "failed": sum(not row["passed"] for row in result["checks"]), "skipped": 0}
    if expected and not result["diagnostics"] and result["counts"]["failed"] == 0:
        result["outcome"] = "observed"
    _save(evidence_dir / "REVIEW.json", result)
    _save(evidence_dir / "EVIDENCE.json", _manifest(evidence_dir))
    return result


class RehearsalDriver(runtime.Driver):
    """ONLY existing synthetic fixtures; no supplied profile or harness path."""
    def __init__(self, binary, work):
        super().__init__(binary, work, selected=("runtime-submit", "runtime-interruption"))
        self.pending_stop = False
        self.package_reviews = []
        for name in SOURCE_NAMES:
            path = self.work / "driver-snapshot" / name
            if not path.exists():
                path.write_bytes((HERE / name).read_bytes())

    def fixture(self, label, **kwargs):
        kwargs.update(timeout=15, placements=2)
        return super().fixture(label, **kwargs)

    def cmd(self, label, args, outcome="completed", **kwargs):
        starts = args[0] == "run"
        if self.launch_blocked and args[0] not in {"status", "receipt"}:
            self.require(label + ".mutation-blocked", False, self.launch_blocked)
        if starts and (self.launch_blocked or self.pending_stop):
            self.launch_blocked = self.launch_blocked or "prior run stopping was not independently observed"
            self.require(label + ".later-start-blocked", False, self.launch_blocked)
        if starts and outcome != "refused":
            self.pending_stop = True
        try:
            reply = super().cmd(label, args, outcome=outcome, **kwargs)
            if starts and outcome == "refused" and reply.get("outcome") != "refused":
                self.pending_stop = True
                self.launch_blocked = "expected no-launch refusal was not observed: " + label
                raise runtime.CaseStopped(self.launch_blocked)
            return reply
        except BaseException:
            self.launch_blocked = "command termination or its result is uncertain: " + label
            raise

    def _capture_stopping(self, f, run, stop_record):
        root = self.audit_path(f) / "runs" / str(run)
        record = {"run": run, "service_records": {}, "groups": [], "diagnostics": [],
                  "service_record_provenance": "exact copied service-owned process/stop records; not an independent launch witness",
                  "probe_provenance": "independent read-only group probes after run return; no signals sent"}
        for name in ("process-auth.json", "process-model.json") + (("runtime-stop.json",) if stop_record else ()):
            try:
                raw = _read_file(root / name)
                record["service_records"][name] = {"path": str(root / name), **_blob(raw)}
                value = runtime.transport_loads(raw)
                if name.startswith("process-"):
                    role = name[len("process-"):-len(".json")]
                    if (set(value) != {"schema", "group", "role"} or value["schema"] != "stewart.claude-code.process/1"
                            or value["role"] != role or type(value["group"]) is not int or value["group"] <= 1):
                        raise ValueError("invalid process record")
                    record["groups"].append({"role": role, "group": value["group"]})
                elif value.get("groups_gone") is not True:
                    raise ValueError("service stop record does not report groups gone")
            except (OSError, ValueError, KeyError, TypeError) as error:
                record["diagnostics"].append({"member": name, "detail": str(error)})
        return record

    def _retain_stopping(self, f, run, record):
        record["observations"] = []
        for group in record["groups"]:
            started = time.monotonic_ns()
            try:
                observed = runtime.group_observation(group["group"])
            except OSError as error:
                observed = "unknown"
                record["diagnostics"].append({"stage": "group-probe", "group": group["group"], "detail": str(error)})
            record["observations"].append({**group, "observation": observed,
                "started_monotonic_ns": started, "finished_monotonic_ns": time.monotonic_ns()})
        safe = (not record["diagnostics"] and len(record["observations"]) == 2
                and all(row["observation"] == "absent" for row in record["observations"]))
        record["stopping_observed"] = safe
        _save(f["witness"] / ("stopping-run-%04d.json" % run), record)
        return safe

    def groups_absent(self, f, run=1, stop_record=True):
        try:
            record = self._capture_stopping(f, run, stop_record)
            try:
                live = super().groups_absent(f, run, stop_record)
            except BaseException as error:
                record["diagnostics"].append({"stage": "inherited-stop-comparison", "detail": str(error)})
                raise
            finally:
                safe = self._retain_stopping(f, run, record)
        except BaseException:
            self.launch_blocked = "independent stop observation failed: " + f["label"]
            raise
        if live or not safe:
            self.launch_blocked = "owned groups are present or stopping is unknown: " + f["label"]
            raise runtime.CaseStopped(self.launch_blocked)
        self.pending_stop = False
        return live

    def check_delivery(self, f, status_reply, actor="auditor"):
        # Preserve the original baseline check and add full independent return
        # comparison. The fixed account belongs only to this synthetic scenario.
        package = super().check_delivery(f, status_reply, actor)
        events = self.harness_clean(f)
        calls = [event for event in events if event["event"] == "rpc-send"
                 and event["value"].get("method") == "tools/call"
                 and event["value"].get("params", {}).get("name") == "record_account"]
        self.require(f["label"] + ".one-witnessed-account-call", len(calls) == 1, calls)
        call = calls[0]
        self.eq(f["label"] + ".witnessed-account-input", call["value"]["params"]["arguments"], {"text": runtime.ACCOUNT})
        replies = [self.core_reply(event["value"]) for event in events if event["event"] == "rpc-receive"
                   and event["pid"] == call["pid"] and event["value"].get("id") == call["value"]["id"]]
        self.require(f["label"] + ".account-completed-at-peer", len(replies) == 1 and replies[0]
                     and replies[0].get("outcome") == "completed", replies)
        if f["label"] == "runtime-interruption":
            launches = [event for event in events if event["event"] == "launch" and event["role"] == "model"]
            self.require(f["label"] + ".two-model-placements", len(launches) == 2, launches)
            second = launches[1]["pid"]
            requests = {event["value"]["id"] for event in events if event["event"] == "rpc-send"
                        and event["pid"] == second and event["value"].get("method") == "tools/call"
                        and event["value"].get("params", {}).get("name") == "what_am_i_working_with"}
            reentries = [self.core_reply(event["value"]) for event in events if event["event"] == "rpc-receive"
                         and event["pid"] == second and event["value"].get("id") in requests]
            completed = [reply for reply in reentries if reply and reply.get("outcome") == "completed"]
            self.require(f["label"] + ".continuing-reentry-at-peer", len(completed) == 1, reentries)
            data = completed[0]["data"]
            self.eq(f["label"] + ".reentry-run", data.get("run"), {"number": 2, "continuing": True})
            self.eq(f["label"] + ".reentry-revision", data.get("revision"), 1)
            self.eq(f["label"] + ".reentry-prior-selection",
                    [(entry.get("id"), entry.get("kind"), entry.get("size")) for entry in data.get("entries", [])],
                    [("e1", "record_account", len(runtime.ACCOUNT.encode()))])
            self.check(f["label"] + ".reentry-prior-receipt", any(
                receipt.get("run") == 1 and receipt.get("tool") == "record_account"
                for receipt in data.get("receipts", [])), data.get("receipts"))
        entries = [answer.Entry("e1", 1, "record_account", "", runtime.ACCOUNT.encode())]
        witness = f["witness"] / "complete-return-witness.json"
        inputs = {name: (f["witness"] / name).read_bytes() for name in
                  ("question-file", "question-body", "report.txt", "profile.json", "tools.json", "mcp-tools.json",
                   "scenario-initial.json", "harness.jsonl")}
        digest = write_witness(witness, entries, 1, family=f["family"] + "/1", writer=runtime.sha(self.binary.read_bytes()),
            actor=actor, reference=f["reference"], status_raw=self.last_stdout, inputs=inputs,
            provenance={"kind": "synthetic-peer-input", "description": "fixed account bytes independently supplied and witnessed at the synthetic MCP peer; no real model output",
                        "interruption": "harness exit after a completed record" if f["label"] == "runtime-interruption" else "none"})
        f["complete_witness"], f["complete_witness_sha256"] = witness, digest
        self._review(f, package, "before-close")
        # The original cases close only the first positive. Closing here also
        # covers the fresh-session invariance and the two-placement continuation.
        self.close_after_delivery(f, package)
        return package

    def _review(self, f, package, stage):
        output = f["witness"] / ("package-" + stage)
        result = review_package(package, f["complete_witness"], output,
                                witness_sha256=f["complete_witness_sha256"], archive_root=f["archive"])
        self.package_reviews.append({"case": f["label"], "stage": stage, "path": str(output), "outcome": result["outcome"]})
        self.require(f["label"] + ".complete-package." + stage, result["outcome"] == "observed", result)
        return result

    def close_after_delivery(self, f, package):
        if f.get("complete_closed"):
            return  # runtime_submit also calls this method after check_delivery.
        label = f["label"]
        launches = self.launch_count(f)
        placements = sum(event["event"] == "launch" and event["role"] == "model" for event in self.harness_events(f))
        reply = self.cmd(label + ".complete-close", ["close", f["reference"]])
        self.eq(label + ".complete-close-effects", reply.get("effects"),
                {"run": "ended", "seal": "existing", "delivery": "verified", "closure": "complete"})
        data = reply.get("data") or {}
        for key, value in (("closure", "complete"), ("already_closed", False), ("before_launch", False),
                           ("placement", "delivered_before_close"), ("surrendered", [])):
            self.eq(label + ".complete-close-" + key, data.get(key), value)
        self.eq(label + ".complete-close-runs", data.get("runs"), {"count": placements, "held": False, "last_ending": "sealed"})
        self.runtime_allowances(label + ".complete-close", data, placements, f)
        self._review(f, package, "after-close")
        status_reply = self.cmd(label + ".complete-status-closed", ["status", f["reference"]])
        self.eq(label + ".complete-closed-condition", status_reply["data"].get("condition"), "closed")
        self.eq(label + ".complete-delivery-confirmed", status_reply["data"].get("headline", {}).get("delivered", {}).get("confirmed"), True)
        repeat = self.cmd(label + ".complete-close-again", ["close", f["reference"]])
        self.eq(label + ".complete-close-idempotent", repeat.get("data", {}).get("already_closed"), True)
        refused = self.cmd(label + ".complete-run-after-close", ["run", f["reference"]], outcome="refused")
        self.check(label + ".complete-run-after-close-reason", refused.get("reason") in {"reference_closed", "authoring_ended"}, refused)
        self.eq(label + ".complete-no-later-launch", self.launch_count(f), launches)
        self.eq(label + ".complete-one-package", sorted(path.name for path in package.parent.iterdir()), [package.name])
        self._review(f, package, "after-repeat")
        f["complete_closed"] = True


def rehearse(binary, work):
    binary, work = map(_absolute, (binary, work))
    if work.is_relative_to(HERE.parent.parent) or _overlap(binary, work):
        raise ValueError("rehearsal work must be outside the repository and binary")
    _read_file(binary)
    if not os.access(binary, os.X_OK):
        raise ValueError("Stewart binary must be executable")
    descriptor = _open_directory(work.parent)
    os.close(descriptor)
    driver = RehearsalDriver(binary, work)
    code = driver.run()
    report = runtime.transport_loads((work / "RESULT.json").read_bytes())
    result = {"schema": "stewart.claude-code.service-rehearsal/1", "mode": "synthetic-only",
              "qualification": False, "profile_eligible": False, "counts": report["counts"],
              "package_reviews": driver.package_reviews, "launch_blocked": driver.launch_blocked,
              "package_review_counts": {"reviews": len(driver.package_reviews),
                  "observed": sum(item["outcome"] == "observed" for item in driver.package_reviews),
                  "failed": sum(item["outcome"] != "observed" for item in driver.package_reviews)},
              "interruption": "synthetic harness exits after recording; no external interruption was exercised",
              "rehearsal_limits": {"max_placements": 2, "placement_timeout_seconds": 15,
                                    "scope": "offline fixtures only; no real-harness cap study"},
              "unexercised": PENDING}
    failed = bool(code or report["counts"]["skipped"] or len(driver.package_reviews) != 9
                  or any(item["outcome"] != "observed" for item in driver.package_reviews))
    result["outcome"] = "failed" if failed else "observed"
    _save(work / "REHEARSAL.json", result)
    # Retain raw runtime work in place, but bind only the regular independent
    # evidence trees here; archive and socket trees keep their actual provenance.
    members = []
    for name in ("driver-snapshot", "commands", "witness"):
        for member in _manifest(work / name)["members"]:
            members.append(dict(member, path=name + "/" + member["path"]))
    for name in ("environment.json", "RESULT.json", "REHEARSAL.json"):
        raw = _read_file(work / name)
        members.append({"path": name, "bytes": len(raw), "sha256": runtime.sha(raw)})
    _save(work / "EVIDENCE.json", {"schema": "stewart.claude-code.service-evidence/1", "members": members,
                                  "scope": "commands, independent witnesses, source snapshots and reports; original archive/work remains separately retained"})
    return int(failed)


def self_test():
    root = Path(tempfile.mkdtemp(prefix="stewart-service-witness-")).resolve()
    archive = root / "archive"
    archive.mkdir()
    checks = []
    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
    entries = [answer.Entry("e1", 1, "record_account", "", b"A supplied claim; no execution was witnessed.\n"),
               answer.Entry("e2", 1, "record_artifact", "bytes", b"\x00\xffartifact\n", encoding="binary")]
    status = {"data": {"seal": {"state": "present", "actor": "auditor", "sealed_at": "2026-11-12T00:00:00.000Z", "revision": 2}}}
    witness = root / "WITNESS.json"
    pin = write_witness(witness, entries, 2, family="open-inquiry/1", writer="1" * 64,
        actor="auditor", reference="stw1:synthetic-audit:synthetic-store:" + str(archive), status_raw=compact(status),
        inputs={"question": b"Inspect this synthetic claim.\n", "material": b"A supplied claim.\n"},
        provenance={"kind": "synthetic-self-test", "description": "expected Entry bytes supplied by this no-process control"})
    original = witness.read_bytes()
    value = runtime.transport_loads(original)
    expected = expected_package(value)
    baseline = root / "baseline"
    baseline.mkdir(mode=0o700)
    for name, raw in expected.items():
        (baseline / name).write_bytes(raw)
        (baseline / name).chmod(0o600)
    review_outputs = []
    def review(name, package=baseline, selected=witness, digest=pin):
        output = root / ("review-" + name)
        review_outputs.append(output)
        return review_package(package, selected, output, witness_sha256=digest, archive_root=archive)
    first = review("positive")
    check("complete-positive-package", first["outcome"] == "observed" and first["complete_capture"])
    repeat = review("repeat")
    check("repeat-observation-invariance", repeat["outcome"] == "observed" and repeat["inventory"] == first["inventory"])
    mutations = {
        "answer-change": lambda p: (p / "answer.json").write_bytes(b"{}\n"),
        "rendering-change": lambda p: (p / "answer.md").write_bytes(b"changed rendering\n"),
        "artifact-change": lambda p: (p / "artifact-e2.bin").write_bytes(b"changed artifact"),
        "missing-member": lambda p: (p / "answer.md").unlink(),
        "extra-member": lambda p: (p / "conversation.json").write_bytes(b"must not be delivered"),
        "duplicate-entry": lambda p: (p / "answer.json").write_bytes(answer.answer_json(2, entries + [entries[0]])),
        "writer-mismatch": lambda p: (p / "manifest.json").write_bytes(expected["manifest.json"].replace(b"1" * 64, b"2" * 64)),
        "symlink": lambda p: ((p / "answer.md").unlink(), (p / "answer.md").symlink_to(baseline / "answer.md")),
        "special-fifo": lambda p: ((p / "answer.md").unlink(), os.mkfifo(p / "answer.md")),
        "unlisted-directory": lambda p: (p / "nested").mkdir(),
        "wrong-file-mode": lambda p: (p / "answer.json").chmod(0o644),
        "wrong-package-mode": lambda p: p.chmod(0o755),
    }
    for name, mutate in mutations.items():
        package = root / name
        package.mkdir(mode=0o700)
        for member, raw in expected.items():
            (package / member).write_bytes(raw)
            (package / member).chmod(0o600)
        mutate(package)
        result = review(name, package)
        check(name, result["outcome"] == "failed" and (root / ("review-" + name) / "REVIEW.json").is_file(), result["diagnostics"])
    corrupt = copy.deepcopy(value)
    corrupt["inputs"]["question"]["sha256"] = "0" * 64
    changed = root / "wrong-input.json"
    _save(changed, corrupt)
    result = review("input-binding", selected=changed, digest=runtime.sha(changed.read_bytes()))
    check("input-binding-mismatch", result["outcome"] == "failed" and any("input byte binding differs" in d["detail"] for d in result["diagnostics"]))
    result = review("witness-pin", selected=changed)
    check("changed-immutable-witness-pin", result["outcome"] == "failed" and result["checks"][0]["passed"] is False)
    for field, altered in (("audit", "different-audit"), ("actor", "manager")):
        corrupt = copy.deepcopy(value)
        corrupt["bindings"][field] = altered
        changed = root / ("wrong-manager-" + field + ".json")
        _save(changed, corrupt)
        result = review("manager-binding-" + field, selected=changed, digest=runtime.sha(changed.read_bytes()))
        check("manager-binding-" + field, result["outcome"] == "failed" and bool(result["diagnostics"]))
    linked = root / "package-link"
    linked.symlink_to(baseline, target_is_directory=True)
    check("package-symlink", review("package-symlink", linked)["outcome"] == "failed")
    ancestor = root / "ancestor-link"
    ancestor.symlink_to(root, target_is_directory=True)
    check("symlink-ancestor", review("ancestor", ancestor / "baseline")["outcome"] == "failed")
    for name, output in (("package", baseline / "evidence"), ("archive", archive / "evidence")):
        try:
            review_package(baseline, witness, output, witness_sha256=pin, archive_root=archive)
        except ValueError:
            refused = True
        else:
            refused = False
        check("output-containment-" + name, refused and not output.exists())
    for name, protected in (("package", baseline), ("archive", archive)):
        alias = protected.with_name(protected.name.upper())
        output = alias / "case-alias-output"
        if alias.exists() and os.path.samefile(alias, protected):
            try:
                review_package(baseline, witness, output, witness_sha256=pin, archive_root=archive)
            except ValueError:
                refused = True
            else:
                refused = False
            check("case-alias-containment-" + name, refused and not output.exists())
        else:
            alias.mkdir(mode=0o700)
            result = review_package(baseline, witness, output, witness_sha256=pin, archive_root=archive)
            review_outputs.append(output)
            check("case-distinct-directory-invariance-" + name, result["outcome"] == "observed")
    check("originals-unchanged", witness.read_bytes() == original and
          {p.name: p.read_bytes() for p in baseline.iterdir()} == expected)
    for state in ("unknown", "present"):
        driver = object.__new__(RehearsalDriver)
        driver.launch_blocked, driver.pending_stop = None, True
        driver.checks, driver.current = [], "self-test"
        with patch.object(runtime.Driver, "groups_absent", return_value=[{"group": 123, "observation": state}]), \
                patch.object(driver, "_capture_stopping", return_value={}), patch.object(driver, "_retain_stopping", return_value=False):
            try:
                driver.groups_absent({"label": state})
            except runtime.CaseStopped:
                stopped = True
            else:
                stopped = False
        with patch.object(runtime.Driver, "cmd") as launch, patch.object(driver, "require", side_effect=runtime.CaseStopped("expected refusal")):
            try:
                driver.cmd("forbidden-later-start", ["run", "synthetic"])
            except runtime.CaseStopped:
                pass
        check("unresolved-stop-blocks-next-start-" + state, stopped and bool(driver.launch_blocked) and not launch.called)
    driver = object.__new__(RehearsalDriver)
    driver.launch_blocked, driver.pending_stop = None, False
    driver.checks, driver.current = [], "self-test"
    with patch.object(runtime.Driver, "cmd", side_effect=TimeoutError("synthetic lost command result")):
        try:
            driver.cmd("timeout", ["run", "synthetic"])
        except TimeoutError:
            pass
    with patch.object(runtime.Driver, "cmd") as launch, patch.object(driver, "require", side_effect=runtime.CaseStopped("expected refusal")):
        try:
            driver.cmd("forbidden-after-timeout", ["run", "synthetic"])
        except runtime.CaseStopped:
            pass
    check("uncertain-command-blocks-next-start", bool(driver.launch_blocked) and not launch.called)
    driver = object.__new__(RehearsalDriver)
    driver.launch_blocked, driver.pending_stop = None, False
    driver.checks, driver.current = [], "self-test"
    with patch.object(runtime.Driver, "cmd", return_value={"outcome": "completed"}):
        try:
            driver.cmd("unexpected-after-close", ["run", "synthetic"], outcome="refused")
        except runtime.CaseStopped:
            pass
    with patch.object(runtime.Driver, "cmd") as launch, patch.object(driver, "require", side_effect=runtime.CaseStopped("expected refusal")):
        try:
            driver.cmd("forbidden-close-after-uncertain-start", ["close", "synthetic"])
        except runtime.CaseStopped:
            pass
    check("unexpected-post-close-start-blocks-mutations", driver.pending_stop and bool(driver.launch_blocked) and not launch.called)
    driver = object.__new__(RehearsalDriver)
    driver.launch_blocked, driver.pending_stop = None, True
    with patch.object(runtime.Driver, "groups_absent", return_value=[]), \
            patch.object(driver, "_capture_stopping", return_value={}), patch.object(driver, "_retain_stopping", return_value=True):
        driver.groups_absent({"label": "stopped"})
    with patch.object(runtime.Driver, "cmd", return_value={"outcome": "refused"}) as launch:
        driver.cmd("ordinary-refusal-after-stopping", ["run", "synthetic"], outcome="refused")
    check("observed-stopping-preserves-next-command", not driver.pending_stop and not driver.launch_blocked and launch.call_count == 1)
    driver = object.__new__(RehearsalDriver)
    copied = {"run": 1, "service_records": {"process-auth.json": _blob(b"original service metadata\n")},
              "groups": [{"role": "auth", "group": 123}, {"role": "model", "group": 456}], "diagnostics": []}
    with patch.object(runtime, "group_observation", return_value="absent") as probe:
        safe = driver._retain_stopping({"witness": root}, 1, copied)
    retained = runtime.transport_loads((root / "stopping-run-0001.json").read_bytes())
    check("stopping-witness-retains-metadata-and-separate-probes", safe and probe.call_count == 2
          and _unblob(retained["service_records"]["process-auth.json"]) == b"original service metadata\n"
          and all(row["observation"] == "absent" and row["finished_monotonic_ns"] >= row["started_monotonic_ns"]
                  for row in retained["observations"]))
    driver = object.__new__(RehearsalDriver)
    driver.launch_blocked, driver.pending_stop = None, True
    fixture = {"label": "missing-process-records", "archive": archive,
               "reference": "stw1:missing-audit:synthetic-store:" + str(archive), "witness": root}
    with patch.object(runtime.Driver, "groups_absent", side_effect=runtime.CaseStopped("missing process record")), \
            patch.object(runtime, "group_observation") as probe:
        try:
            driver.groups_absent(fixture, run=2)
        except runtime.CaseStopped:
            pass
    missing = runtime.transport_loads((root / "stopping-run-0002.json").read_bytes())
    check("missing-stop-record-blocks-and-retains", bool(driver.launch_blocked) and not probe.called
          and missing["stopping_observed"] is False and len(missing["diagnostics"]) == 4)
    counts = {"passed": sum(row["passed"] for row in checks), "failed": sum(not row["passed"] for row in checks), "skipped": 0}
    _save(root / "SELFTEST.json", {"checks": checks, "counts": counts, "scope": "synthetic byte and filesystem controls; no subprocess"})
    source = root / "sources"
    source.mkdir()
    for name in SOURCE_NAMES:
        (source / name).write_bytes((HERE / name).read_bytes())
    # Source packages include intentionally unsafe input fixtures. The evidence
    # manifest names only safe review outputs, the original witness and sources.
    files = [root / "SELFTEST.json", witness, root / "stopping-run-0001.json", root / "stopping-run-0002.json"] + list(source.iterdir())
    for directory in sorted(review_outputs):
        files.extend(path for path in directory.rglob("*") if path.is_file())
    _save(root / "SELFTEST-EVIDENCE.json", {"members": [{"path": str(path.relative_to(root)),
          "bytes": len(path.read_bytes()), "sha256": runtime.sha(path.read_bytes())} for path in files]})
    for row in checks:
        if not row["passed"]:
            print("FAIL " + row["name"])
    print("Self-test: %d passed, %d failed, %d skipped" % (counts["passed"], counts["failed"], counts["skipped"]))
    print("No subprocess launched. Retained: " + str(root))
    return int(bool(counts["failed"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true", help="bounded byte/filesystem controls; no subprocess")
    mode.add_argument("--rehearse", action="store_true", help="SYNTHETIC ONLY: actual Stewart with the existing fake harness")
    parser.add_argument("--binary", type=Path, help="absolute gated Stewart binary; never a Claude executable")
    parser.add_argument("--work", type=Path, help="fresh physical absolute directory outside the repository")
    args = parser.parse_args()
    if args.self_test:
        if args.binary is not None or args.work is not None:
            parser.error("--self-test accepts no binary or work directory")
        return self_test()
    if args.binary is None or args.work is None:
        parser.error("--rehearse requires --binary and --work")
    return rehearse(args.binary, args.work)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print("Service witness refused: " + str(error), file=sys.stderr)
        sys.exit(2)
