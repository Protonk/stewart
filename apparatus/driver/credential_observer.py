#!/usr/bin/env python3
"""Observe Linux process access without retaining environment or memory bytes.

Run as the intended observer account: python3 -I -B credential_observer.py PID.
This neither changes the target nor claims protection against its administrator.
The launch apparatus can use the same observer under another unprivileged UID.
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
    if len(sys.argv) != 2 or not sys.argv[1].isdigit() or int(sys.argv[1]) < 1:
        raise SystemExit("usage: credential_observer.py PID")
    print(json.dumps(observe(int(sys.argv[1])), sort_keys=True))
