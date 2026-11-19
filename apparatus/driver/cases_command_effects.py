"""Independent command inspection and file-only lifecycle checks (INTERFACE 5.10, C21)."""
from __future__ import annotations

import copy
import contextlib
import ctypes
import json
import os
import re
import shlex
import signal
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from driver_core import (COMMANDS, F, case, check_commission_forecast, check_description, check_observation,
                         effect_text, forecast, selftest, sha256_hex)
import cases_after_launch as delivery
import fake_provider as fp
import run_support as rs

BODY = b"\xef\xbb\xbfWhich departures moved?\r\nCompare the submitted timetables."
REPORT = b"07:40 was moved to 07:45.\r\n"


@contextlib.contextmanager
def archive_access(root, observation):
    """Linux directory watches cover open/read events in the existing synthetic archive tree."""
    if sys.platform != "linux":
        yield
        return
    directories = [path for path, _, _ in os.walk(root)]
    libc = ctypes.CDLL(None, use_errno=True)
    fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
    if fd < 0:
        raise OSError(ctypes.get_errno(), "inotify_init1")
    watches = {}
    try:
        for directory in directories:
            descriptor = libc.inotify_add_watch(fd, os.fsencode(directory), 0x01 | 0x20)  # IN_ACCESS | IN_OPEN
            if descriptor < 0:
                raise OSError(ctypes.get_errno(), "inotify_add_watch", directory)
            watches[descriptor] = os.path.relpath(directory, root)
        observation["watched_directories"] = list(watches.values())
        observation["started_monotonic_ns"] = time.monotonic_ns()
        yield
        observation["finished_monotonic_ns"] = time.monotonic_ns()
        # A fixed-size synthetic archive and a bounded child execution keep the observation small.
        # Queue overflow, lost watches and an excessive volume of events invalidate the observation.
        events = observation["events"] = []
        while len(events) < 8192:
            try:
                chunk = os.read(fd, 65536)
            except BlockingIOError:
                break
            offset = 0
            while offset < len(chunk):
                watch, mask, _, size = struct.unpack_from("=iIII", chunk, offset)
                offset += 16
                if watch not in watches or mask & (0x4000 | 0x8000):  # IN_Q_OVERFLOW | IN_IGNORED
                    raise RuntimeError("archive access observation lost events or a watch")
                name = os.fsdecode(chunk[offset:offset + size].split(b"\x00", 1)[0])
                offset += size
                events.append({"path": os.path.normpath(os.path.join(watches[watch], name)), "mask": mask})
        if len(events) >= 8192:
            raise RuntimeError("archive access observation exceeded its event bound")
    finally:
        os.close(fd)


@selftest
def access_observation_selftest():
    if sys.platform != "linux":
        return [("effects.archive-open-read", None, "Linux inotify observer")]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "archive"
        capture = root / "intake" / "1" / "q.bin"
        capture.parent.mkdir(parents=True)
        capture.write_bytes(BODY)
        outside = Path(directory) / "another-original"
        outside.write_bytes(BODY)
        out = []
        for label, path in (("outside", outside), ("inside", capture)):
            row = {}
            with archive_access(root, row):
                result = subprocess.run(["/bin/cat", str(path)], stdout=subprocess.PIPE, timeout=5, check=True)
            events = row["events"]
            out.append(("effects.archive-" + label + "-original", result.stdout == BODY))
            if path == outside:
                out.append(("effects.archive-outside-unobserved", events == [], events))
            else:
                masks = [e["mask"] for e in events if e["path"] == "intake/1/q.bin"]
                out.append(("effects.archive-open-control", any(m & 0x20 for m in masks), events))
                out.append(("effects.archive-read-control", any(m & 0x01 for m in masks), events))
        return out


@case("c21.command-effect-access", ["C21", "C20"],
      "observe archive opens/reads on Linux, inherited descriptor consumption and connections to a designated local peer",
      needs=("loopback",))
def c_effect_access(t):
    sub = t.submission([F("timetable.txt", REPORT)], body=BODY)
    t.accept(sub)
    peer = rs.provider(t, fp.Script([fp.HttpError(413)]), label="access-observer")
    env = {"STEWART_ARCHIVE": sub.archive, "STEWART_PROVIDER_URL": peer.url}
    marker = peer.key.encode("ascii") + b"\n"
    observations = []
    if sys.platform != "linux":
        t.skip_part("archive-open-read-observation", "Linux inotify observes open/read events in the marked archive")
    def observe(label, args, **options):
        row = {"label": label, "archive": sub.archive, "provider": peer.url}
        observations.append(row)
        read_fd, write_fd = os.pipe()
        try:
            with os.fdopen(write_fd, "wb") as output:
                output.write(marker)
            reply = t.cmd(args, name=label, env=env, stdin=read_fd, timeout=15,
                          observation=archive_access(sub.archive, row), **options)
            remaining = os.read(read_fd, len(marker) + 1)
        finally:
            os.close(read_fd)
        row["descriptor_bytes_remaining"] = len(remaining)
        row["connections_after"] = peer.provider.conn_seq
        (Path(t.evid) / "access-observations.json").write_text(json.dumps(observations, indent=2), encoding="utf-8")
        return reply, row, remaining

    for command, binary in [(name, t.bin["path"]) for name in COMMANDS] + [("run", wrapper(t))]:
        label = "access.describe-%d-%s" % (len(observations), command)
        reply, row, remaining = observe(label, ["describe", command], binary=binary, expect="completed")
        t.eq(label + ".command", reply.data.get("command"), command)
        t.eq(label + ".unread-marker", remaining == marker, True)
        t.eq(label + ".no-connection", row["connections_after"], 0)
        if sys.platform == "linux":
            t.eq(label + ".no-archive-open-or-read", row["events"], [])

    # An ordinary read of the very same capture must fire the archive observer.
    raw, row, remaining = observe("access.receipt-control", ["receipt", sub.ref, "--read", "question-body"],
                                  op="receipt-read", json_reply=False, envelope=False)
    t.eq("access.readback-control", raw.stdout, BODY)
    t.eq("access.receipt-keeps-descriptor", remaining == marker, True)
    if sys.platform == "linux":
        captured = [e for e in row["events"] if e["path"].endswith("/q.bin")]
        t.driver_control("archive-open-and-read", any(e["mask"] & 0x20 for e in captured)
                         and any(e["mask"] & 0x01 for e in captured), captured)
    # A genuine run consumes exactly these marker bytes and contacts the same peer.
    run, row, remaining = observe("access.run-control", ["run", sub.ref, "--key-fd", "0"], expect="completed")
    t.eq("access.run-cause", run.data.get("cause"), "provider_rejected")
    peer.stop()  # Join accepted connections before judging the entire observation, including empty connections.
    t.driver_control("credential-descriptor-consumed", not remaining, {"remaining": len(remaining)})
    t.driver_control("provider-contact", peer.provider.conn_seq == 1 and len(peer.exchanges) == 1,
                     {"connections": peer.provider.conn_seq, "requests": len(peer.exchanges)})


def wrapper(t):
    directory = t.mkdir("manager wrapper")
    p = Path(directory) / "stewart wrapper"
    p.write_text('#!/bin/sh\nexec ' + shlex.quote(t.bin["path"]) + ' "$@"\n', encoding="utf-8")
    p.chmod(0o700)
    t.watch(directory, "frozen", "manager wrapper")
    return str(p)


@case("c21.command-effects", ["C21", "C20"],
      "inspect every command with empty environment and a shell wrapper; reject malformed requests without a reference")
def c_command_effects(t):
    wrapped = wrapper(t)
    empty = {"PATH": None, "HOME": None, "TMPDIR": None}
    invalid_archive = Path(t.root) / "unused archive"
    elsewhere = t.fresh_dir("other invocation directory")
    t.watch(str(invalid_archive), "frozen", "unused archive")
    help_text = t.cmd(["help", "commands"], op="help", name="effects.help", json_reply=False, envelope=False).stdout.decode()
    for command in COMMANDS:
        label = "effects." + command
        direct = t.cmd(["describe", command], name=label + ".direct", env=empty, expect="completed")
        t.require(label + ".present", isinstance(direct.obj, dict), direct.stdout)
        text = check_description(t, label, direct.obj, command)
        other = t.cmd(["describe", command], name=label + ".wrapped", cwd=elsewhere,
                      env={"STEWART_ARCHIVE": str(invalid_archive)}, binary=wrapped, expect="completed")
        t.eq(label + ".invariant", other.obj, direct.obj)
        for v in direct.data["variants"]:
            for e in v["possible"]:
                t.check(label + ".ordinary-help", " ".join(e["description"].split()) in " ".join(help_text.split()),
                        e["description"])
        if command == "commission":
            # Mutate a copy of the observed forecast, leaving its own inspection result intact.
            changed = copy.deepcopy(direct.obj)
            for v in changed["data"]["variants"]:
                v["possible"] = [e for e in v["possible"] if not re.search(
                    r"partial|incomplete|retain(ed|s)? (?:an? |the )?(?:intake|attempt|capture)",
                    e["when"] + " " + e["description"], re.I)]
            observer = copy.copy(t)
            observer.checks = []
            check_commission_forecast(observer, "changed", effect_text(changed["data"]["variants"]))
            failed = [c["name"] for c in observer.checks if not c["ok"]]
            t.driver_control("omitted-partial-commission", "changed.partial" in failed and bool(text), failed)
            changed = dict(direct.obj, effects={"acceptance": "accepted", "attempt": "recorded"})
            observer.checks = []
            check_observation(observer, "changed", changed)
            failed = [c["name"] for c in observer.checks if not c["ok"]]
            t.driver_control("forecast-reported-as-executed", failed == ["changed.inspection-effects"], failed)
    for i, args in enumerate(([], ["missing"], ["st1.reference"], ["run", "extra"], ["run", "--details"])):
        reply = t.cmd(["describe"] + args, op="usage", name="effects.usage-%d" % i,
                      envelope=False, env=empty, binary=wrapped)
        t.eq("effects.usage-%d.exit" % i, reply.rc, 2)
    t.check("effects.no-archive", not invalid_archive.exists(), str(invalid_archive))


def file_submission(t, label, binary):
    """Only files cross the commissioning boundary. The recorded writer is the exec'ed binary."""
    sub = t.submission([F("timetable.txt", REPORT)], body=BODY, dest_watch="additions")
    t.watch(sub.archive, "archive", "archive")
    result = t.cmd(["new", sub.folder, "--archive", sub.archive], binary=binary, name=label + ".new", expect="completed")
    t.check_new_reply(result, sub, label + ".new", False, t.bin["path"])
    t.prepare(sub, name=label + ".prepare", binary=binary)
    return sub


@case("c21.file-only", ["C21", "C5", "C8", "C15"],
      "complete direct and wrapped file-only audits, conditional key refusal, readback, empty manager seal and repeat close",
      needs=("loopback",))
def c_file_only(t):
    direct_members = None
    for route, binary in (("direct", t.bin["path"]), ("wrapped", wrapper(t))):
        label = "files." + route
        cwd = t.fresh_dir(label + " cwd")
        home = t.fresh_dir(label + " home")
        sub = file_submission(t, label, binary)
        handle = sub.handles[-1]
        refused = t.commission(sub, handle, name=label + ".no-affirmation", flag=False, binary=binary,
                               expect="refused", reason="affirmation_missing")
        t.eq(label + ".no-attempt", refused.effects.get("attempt"), "none")
        accepted = t.commission(sub, handle, name=label + ".commission", binary=binary)
        t.edit(os.path.join(sub.folder, "question.md"), b"An unrelated live question\n")
        again = t.commission(sub, handle, name=label + ".retry", binary=binary, already=True)
        t.eq(label + ".accepted-once", again.data.get("receipt_sha256"), accepted.data.get("receipt_sha256"))
        t.check_readback_ok(sub, "question-body", BODY, label + ".captured-body", binary=binary, cwd=cwd)
        a = delivery.Audit(t, label, sub)
        delivery.with_script(t, a, [fp.HttpError(413), delivery.end_step("End."), delivery.end_step("Still ended.")])
        # Observe the same designated loopback endpoint before inspection, refusal and real placement.
        env = rs.run_env(t, a.fx, {"HOME": home})
        described = t.cmd(["describe", "run"], name=label + ".effects", binary=binary, cwd=cwd, env=env, expect="completed")
        check_description(t, label + ".effects", described.obj, "run")
        missing = rs.run(t, sub, a.fx, name=label + ".no-key", env={"HOME": home, "ANTHROPIC_API_KEY": None},
                         binary=binary, cwd=cwd, expect="refused", reason="provider_key_missing")
        forecast(t, label + ".key-remedy", missing.obj.get("message", ""), {"env": "ANTHROPIC_API_KEY", "fd": "--key-fd"})
        rs.check_refused_before_request(t, missing, sub, a.fx, label + ".no-key")
        t.eq(label + ".no-connections", [e for e in a.fx.provider.events if e.get("event") != "no_request"], [])
        failed = label + ".provider-rejection"
        rejected = rs.run(t, sub, a.fx, name=failed, binary=binary, cwd=cwd, env={"HOME": home})
        exchanges = a.fx.exchanges_of(failed)
        t.require(failed + ".one-attempt", len(exchanges) == 1, len(exchanges))
        known = rs.provider_expected(exchanges[0], 1, 1)
        rs.check_run_reply(t, rejected, sub, failed, ending="interrupted", cause="provider_rejected", run_number=1,
                           fx=a.fx, limits=rs.limits_of(sub), provider=known)
        rs.check_run_ended(t, sub, 1, failed, ending="interrupted", cause="provider_rejected", provider=known,
                           requests=1, attempts=1)
        t.eq(failed + ".exit", rejected.rc, 5)
        run = rs.run(t, sub, a.fx, name=label + ".run", env={"HOME": home}, binary=binary, cwd=cwd)
        rs.check_run_reply(t, run, sub, label + ".run", ending="ended_unsubmitted", run_number=2,
                           fx=a.fx, limits=rs.limits_of(sub))
        rs.check_fake(t, a.fx, label)
        status = t.cmd(["status", sub.ref], name=label + ".status", cwd=cwd, binary=binary, expect="completed")
        t.eq(label + ".unsubmitted", status.data.get("condition"), "ended_unsubmitted")
        def close(suffix, *opts):
            return t.cmd(["close", sub.ref, *opts], name=label + suffix, cwd=cwd, binary=binary, expect="completed")
        result = close(".close")
        delivery.manager_sealed(t, a, result.data.get("seal"), label + ".seal", [], 0)
        delivery.check_delivery_view(t, label + ".delivery", result.data.get("delivery"), a, attempt=1, outcome="verified")
        package = Path(delivery.check_package_at(t, a, label, 1))
        originals = {"question.md": BODY, "answer.json": b'{"schema":"stewart.answer/1","revision":0,"entries":[]}\n',
                     "answer.md": b"No answer entries recorded.\n"}
        actual = {name: (package / name).read_bytes() for name in originals}
        t.eq(label + ".literal-members", actual, originals)
        if direct_members is not None:
            t.eq(label + ".same-return", actual, direct_members)
        direct_members = actual
        token = delivery.cf_token(t, a, 1)
        t.require(label + ".confirmation-offered", token and token == result.data.get("confirmation"), result.data)
        done = close(".confirm", "--confirm", token)
        t.eq(label + ".closed", done.data.get("outcome"), "closed_delivered")
        history = t.log_kinds(sub)
        repeat = close(".repeat")
        t.eq(label + ".already-closed", repeat.data.get("already_closed"), True)
        t.eq(label + ".no-new-history", t.log_kinds(sub), history)


@case("c21.file-only-lost-reply", ["C21", "C17", "C20"],
      "reconcile partial intake and lost successful commission replies through the direct CLI and a wrapper", mode="test")
def c_lost_reply(t):
    for route, binary in (("direct", t.bin["path"]), ("wrapped", wrapper(t))):
        label = "recovery." + route
        sub = file_submission(t, label, binary)
        changed = Path(sub.folder) / "materials" / "timetable.txt"
        t.edit(str(changed), REPORT + b"A later schedule\n")
        reply = t.commission(sub, sub.handles[-1], name=label + ".changed", binary=binary,
                             expect="refused", reason="selection_changed")
        t.eq(label + ".partial", reply.effects.get("attempt"), "partial")
        t.eq(label + ".not-accepted", reply.effects.get("acceptance"), "absent")
        check_commission_forecast(t, label + ".forecast", effect_text(t.cmd(
            ["describe", "commission"], name=label + ".describe", binary=binary, expect="completed").data["variants"]))
        t.edit(str(changed), REPORT)
        t.prepare(sub, binary=binary, name=label + ".reprepare")
        handle = sub.handles[-1]
        lost = t.cmd(["commission", sub.ref, handle, "--i-am-finished"], name=label + ".lost",
                     binary=binary, envelope=False, fault="commission.after_accepted_link=kill")
        t.eq(label + ".interrupted", lost.rc, -signal.SIGKILL)
        t.eq(label + ".no-reply", lost.stdout, b"")
        status = t.cmd(["status", sub.ref], name=label + ".status", binary=binary, expect="completed")
        t.check_status(status, sub, label + ".recovered", accepted="yes", condition="not_started", next_cmds=("run", "close"))
        before = (t.log_kinds(sub), t.intake_dirs(sub))
        repeat = t.commission(sub, handle, binary=binary, name=label + ".retry", already=True)
        t.eq(label + ".accepted-once", t.log_kinds(sub).count("accepted"), 1)
        t.eq(label + ".recovered-without-new-intake", (t.log_kinds(sub), t.intake_dirs(sub)), before)
        t.check_readback_ok(sub, "question-body", BODY, label + ".question", binary=binary)
        receipt = t.cmd(["receipt", sub.ref], name=label + ".receipt", binary=binary, expect="completed")
        t.eq(label + ".fixed-run-line", receipt.data.get("run_line"), [sub.writer, "run", sub.ref])
        accepted = delivery.log_record(t, sub, "accepted")
        t.require(label + ".accepted-record", accepted is not None, t.log_kinds(sub))
        receipt_bytes = (Path(sub.audit_dir) / accepted[2]["receipt"]).read_bytes()
        t.eq(label + ".same-receipt", repeat.data.get("receipt_sha256"), sha256_hex(receipt_bytes))
        done = t.cmd(["close", sub.ref], name=label + ".close", binary=binary, expect="completed")
        t.eq(label + ".before-launch", done.data.get("before_launch"), True)
        t.eq(label + ".no-package", os.listdir(sub.dest), [])
