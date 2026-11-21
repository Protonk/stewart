# Local environment and process observations

[ORIGINS.json](ORIGINS.json) binds all nine files to their exact original bytes,
sizes and SHA-256 digests. [os_fixtures.py](../../os_fixtures.py) checks those
identities and projects recorded return values or exceptions onto synthetic
target IDs. Fixture readers never signal or inspect stored process IDs.

## Environment framing

The four `env-*.bin` files are complete stdout from `/usr/bin/env -0` on
2026-11-16, Darwin 25.6.0 ARM64. Each invocation received only the explicit
environment below; no caller variables were forwarded.
The saved capture script and command/environment records are in
`.tmp/readiness-os-fixtures-01/capture-20261116T180112Z-1f5f1540/`.

| Capture | Explicit environment | Expected difference |
| --- | --- | --- |
| `env-original.bin` | `A` = `line\nwith=equals`, `EMPTY` = empty string | LF belongs to the value; the first `=` separates its name. |
| `env-changed-value.bin` | The same, with LF replaced by one space | Only that value changes. |
| `env-reordered.bin` | The original two entries supplied in reverse order | Decoded values are identical. |
| `env-empty.bin` | No entries | Empty stdout represents the empty environment. |

Here `\n` denotes an actual LF. Each nonempty capture is 26 bytes. The runtime
selftest consumes these bytes and also removes the final NUL from a copy of the
original: that copy must refuse specifically as unterminated. Existing malformed
entry, duplicate-name and invalid-UTF-8 controls remain synthetic. These captures
ground decoding; the existing executable-wrapper comparisons separately observe
what the shell and Python add to their controlled launch environments.

## Process-group probes

`owned-group.json` records two successful `os.killpg(group, 0)` probes followed by
`ProcessLookupError`, errno 3, after the child exited and was reaped. The observer
created one Python child in a new session. `owned-child.json` preserves its
source and independent ready/acknowledgement/wait observations. The child had no
descendants. This capture is in the same 2026-11-16 directory as the environment
observations; the ready and acknowledgement stdout witnesses remain there.

`denied-group.json` comes from
`.tmp/readiness-os-fixtures-01/system-group-observation/observation.json` at
2026-11-16 18:01:57 UTC. UID 501's signal-0 probe of system group 1 returned
`PermissionError`, errno 1. The metadata-only `/bin/ps -p 1 -o pid=,pgid=,uid=`
invocation was also denied by the agent sandbox. No signal was delivered and
the target's membership or presence was not independently observed. The record
establishes a denied observation; it cannot establish absence or the precise
cause of the denial.
Unlike the owned-child collector, this inline collector was not saved as a
source file. The record retains the `ps` executable and error, but not its argv,
platform or collector digest; the command above comes from the capture invocation.

Runtime, probe and bounded-launcher tests replay the exact exception class,
errno and message. They must distinguish present, absent and unknown. Target-ID
invariance is synthetic: changing the requested ID cannot turn the supplied
denial into absence. Retry transitions and persistent denial are synthetic
schedules over the recorded outcomes; they do not reproduce kernel timing.
The existing owned-group firing/stopping controls still use actual processes.

## Linux procfs access

`procfs-arm64.json` and `procfs-amd64.json` are complete observer records from
the 2026-11-13 `acceptance-readiness-02` runs under Apple `container`. Both
used Linux userlands. The amd64 run used Rosetta. Each contains a readable same-UID control, a readable
then denied pre-input transition, and a denied during-request observation.
Denial is errno 13 for `environ`, `maps`, `mem` and `fd`; `cmdline` remains
readable. The records retain byte identities and counts, never environment or
memory contents. Their original observer scope and timing remain unchanged.

Credential selftests check those complete observations. Each differing variant
changes only one protected read's errno to 2: disappearance of even one item
must prevent a claim that all reads were denied. JSON member ordering preserves
the result. These are supplied-record predicate comparisons; the original Linux
case, including its independently readable control, owns the enforcement
evidence. Procfs denial and process-group denial are separate mechanisms.

### Podman interpreter and descriptor identity

The two `podman-python-*.json` fixtures record a synthetic Python child in the
rootless Stewart VM on 2026-11-21 UTC. Each observation names the probe by digest,
the observer and child by PID, the UID, the supplied argv and the time of each
sample. The parent read its child's complete NUL-terminated procfs cmdline while
the child waited with `PR_GET_DUMPABLE` equal to 1, then 0. At startup the child
tested descriptors 3 through 11 before opening a file containing 37 known bytes.

The Python OCI index was
`2c90493710bd462e097441e60b0218430d8f7e2b46779bfca3742b2efd386feb`.
Both userlands ran on the VM's aarch64 kernel, with networking disabled. The
recorded image manifests and original command, file identities and home
inventories are beside the observations identified by [ORIGINS.json](ORIGINS.json).

| Linux userland | Registry manifest (SHA-256) | Cmdline at dumpable 1, then 0 | Startup descriptors and subsequent reuse |
| --- | --- | --- | --- |
| arm64 | `dc354b0c18b5192842bc6800d22e624461383b149cdbbd9646fec78a28340721` | Supplied argv in both states | 3 and 4 closed. The file open reused 3. |
| amd64 through Rosetta | `b3ae2372f3c9b7f0a80ec21d1ae931002ea056509e04c5072f144efe9694732f` | Supplied argv, then the interpreter path followed by the complete supplied argv | 3 held `/usr/local/bin/python3.14`, 4 held `/mnt/lima-rosetta/rosetta`, and the file open reused 5. |

The interpreter prefix was exactly `/mnt/lima-rosetta/rosetta`. The matcher
checks the identity and length of the entire argument vector in each accepted
form. Controls change an argument, prepend a different executable, repeat the
interpreter prefix or append an argument. The descriptor control checks the
candidate against the observed EBADF and the descriptor returned by the open.

A native guest observer inventoried a separate, initially empty home before
and after each container. The arm64 home remained empty. The amd64 home gained
the directories `.cache` and `.cache/rosetta` with no files during this probe.
