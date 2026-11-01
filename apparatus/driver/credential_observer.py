#!/usr/bin/env python3
"""Observe Linux process access without retaining environment or memory bytes.

Run as the intended observer account: python3 -I -B credential_observer.py PID.
This neither changes the target nor claims protection against its administrator.
The launch apparatus can use the same observer under another unprivileged UID.
With --descriptor-reuse SYNTHETIC_FILE, witness a fresh process's low descriptor
before and after opening that file; retain only targets and byte identities.
"""
from __future__ import annotations

import datetime
import errno
import hashlib
import json
import os
import re
import sys
import time


def descriptor_reuse_observation(path):
    """Witness a closed low descriptor, then deliberately reuse it for a file.

    Run in a fresh interpreter with no inherited descriptors above stderr. The
    Rosetta interpreter holds its guest executable at 3 and itself at 4; the
    exact active descriptor target, not the CPU architecture, selects that case.
    """
    targets = {}
    for fd in (3, 4):
        try:
            targets[str(fd)] = os.readlink("/proc/self/fd/%d" % fd)
        except OSError:
            targets[str(fd)] = None
    rosetta = targets["4"] == "/run/rosetta/rosetta"
    selected = 5 if rosetta else 3
    try:
        os.fstat(selected)
        before_errno = None
    except OSError as exc:
        before_errno = exc.errno
    fd = os.open(path, os.O_RDONLY)
    try:
        data = os.read(fd, 4096)
        return {"schema": "stewart.credential-descriptor-observation/1",
                "observer_pid": os.getpid(), "observer_uid": os.geteuid(),
                "startup_targets": targets, "rosetta": rosetta,
                "selected_fd": selected, "before_errno": before_errno,
                "opened_fd": fd, "read_bytes": len(data),
                "read_sha256": hashlib.sha256(data).hexdigest()}
    finally:
        os.close(fd)


def cmdline_forms(argv):
    """Exact procfs identities, including the observed Rosetta interpreter argv.

    Rosetta can expose its own absolute executable before the complete guest
    argv after the guest becomes non-dumpable. Nothing is stripped or accepted
    by suffix: each candidate includes every original argument and terminator.
    """
    result = {}
    for form, prefix in (("direct", []), ("rosetta", ["/run/rosetta/rosetta"])):
        data = b"\0".join(os.fsencode(arg) for arg in prefix + list(argv)) + b"\0"
        result[form] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return result


def match_cmdline(observation, argv):
    """Return the exact matched form, retaining only identities in evidence."""
    if observation.get("access", {}).get("cmdline", {}).get("allowed") is not True:
        return None
    for form, identity in cmdline_forms(argv).items():
        if (observation.get("cmdline_sha256") == identity["sha256"]
                and observation.get("cmdline_bytes") == identity["bytes"]):
            return form
    return None


def observe(pid):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    clock = time.monotonic()
    root = "/proc/%d" % pid
    result = {"schema": "stewart.credential-observation/1",
              "observer_uid": os.geteuid(), "observer_pid": os.getpid(), "target_pid": pid,
              "started_at": started, "scope": "Linux procfs reads; no ptrace or administrator claim",
              "access": {}}
    maps = None
    for name in ("cmdline", "environ", "maps", "fd"):
        try:
            if name == "fd":
                os.listdir(root + "/fd")
            else:
                with open(root + "/" + name, "rb") as f:
                    data = f.read(1 << 20)
                if name == "maps":
                    maps = data
                elif name == "cmdline":
                    result["cmdline_sha256"] = hashlib.sha256(data).hexdigest()
                    result["cmdline_bytes"] = len(data)
            result["access"][name] = {"allowed": True}
        except OSError as exc:
            result["access"][name] = {"allowed": False, "errno": exc.errno}
    try:
        fd = os.open(root + "/mem", os.O_RDONLY)
        try:
            # Opening mem establishes access. When maps is readable, also prove a
            # read succeeds; retain only its length, never the byte itself.
            address = next((int(line.split(b"-")[0], 16) for line in (maps or b"").splitlines()
                            if len(line.split()) >= 2 and line.split()[1].startswith(b"r")), None)
            sample = os.pread(fd, 1, address) if address is not None else None
            result["access"]["mem"] = {"allowed": True, "read_bytes": len(sample) if sample is not None else None}
        finally:
            os.close(fd)
    except OSError as exc:
        result["access"]["mem"] = {"allowed": False, "errno": exc.errno}
    try:
        with open(root + "/status", encoding="ascii") as f:
            status = f.read()
        match = re.search(r"^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", status, re.M)
        result["target_uids"] = [int(x) for x in match.groups()] if match else None
    except OSError as exc:
        result["status_errno"] = exc.errno
    try:
        with open(root + "/limits", encoding="ascii") as f:
            limits = f.read()
        match = re.search(r"^Max core file size\s+(\S+)\s+(\S+)", limits, re.M)
        result["core_limits"] = list(match.groups()) if match else None
    except OSError as exc:
        result["limits_errno"] = exc.errno
    result["elapsed_ms"] = round((time.monotonic() - clock) * 1000, 3)
    return result


def inspection_denied(observation):
    """Require access denied, not a dead/missing process or another read error."""
    access = observation.get("access", {})
    return all(access.get(name, {}).get("allowed") is False
               and access[name].get("errno") in (errno.EACCES, errno.EPERM)
               for name in ("environ", "maps", "mem", "fd"))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--descriptor-reuse":
        result = descriptor_reuse_observation(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1].isdigit() and int(sys.argv[1]) >= 1:
        result = observe(int(sys.argv[1]))
    else:
        raise SystemExit("usage: credential_observer.py PID | --descriptor-reuse SYNTHETIC_FILE")
    print(json.dumps(result, sort_keys=True))
