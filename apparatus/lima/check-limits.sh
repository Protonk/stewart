#!/bin/sh
# Run from each guest account, with the pinned local Python platform manifest.
set -eu
[ "$#" -eq 1 ] || { echo "usage: sh check-limits.sh PYTHON_IMAGE_AT_DIGEST" >&2; exit 2; }
case "$1" in *@sha256:*) ;; *) echo "supply an image by registry digest" >&2; exit 2 ;; esac
podman run --rm -i --pull=never --network none --cpus=.25 --memory=96m --memory-swap=96m \
    --pids-limit=40 --user 1000:1000 "$1" python3 -I -B - <<'PY'
from pathlib import Path
import json
import os
import signal
import time

group = Path("/sys/fs/cgroup")


def counters(name):
    return {k: int(v) for k, v in (line.split() for line in (group / name).read_text().splitlines())}


quota, period = map(int, (group / "cpu.max").read_text().split())
limit = int((group / "memory.max").read_text())
if quota * 4 != period or limit != 96 * 1024**2 or (group / "memory.swap.max").read_text().strip() != "0":
    raise SystemExit("unexpected cgroup limits")

before = counters("cpu.stat")
end = time.monotonic() + 2
while time.monotonic() < end:
    sum(range(500))
after = counters("cpu.stat")
if after["nr_throttled"] <= before["nr_throttled"]:
    raise SystemExit("CPU load did not exercise throttling")


def allocate(size):
    pid = os.fork()
    if pid == 0:
        memory = bytearray(size)
        os._exit(0 if memory[-1] == 0 else 1)
    return os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1])


events = counters("memory.events")
within = allocate(limit // 4)
middle = counters("memory.events")
excess = allocate(limit * 2)
final = counters("memory.events")
if within or middle["oom_kill"] != events["oom_kill"] or excess != -signal.SIGKILL or final["oom_kill"] <= middle["oom_kill"]:
    raise SystemExit("memory controls did not distinguish the two allocations")
print(json.dumps(dict(cpu_max=[quota, period], periods_throttled=after["nr_throttled"] - before["nr_throttled"],
                      memory_max=limit, within_exit=within, excessive_exit=excess,
                      oom_kills=final["oom_kill"] - middle["oom_kill"])))
PY
