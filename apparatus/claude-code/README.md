# Native Claude launch probe apparatus

This is a synthetic native experiment, separate from Stewart's service and
acceptance driver. It runs a two-tool MCP fixture and a command hook through
one pinned Claude executable. It does not implement an auditor adapter or
qualify Linux behavior. Python uses only its standard library.

`pin.py` fetches the public release key, manifest and signature, checks the
pinned signer with `gpgv`, compares the installed executable's SHA-256 and
preserves an exclusive copy outside the repository. It also checks Apple's
code signature. It never launches Claude. The public-key verification uses
an isolated keyring without a GPG agent or the user's trust configuration.

`probe.py` is bound to the completed commission in `.scratch/claude-code-probe-02`.
Both native probe commissions are closed. Its retained source supports inspection
and offline controls; the existing slots cannot be reused.
Invocation reservations are persisted before spawning. A failed or uncertain
reservation is not repeated; the authentication check and model phase start
only once.
The source, executable, prompt, settings and MCP configuration are hashed and
checked before invocation. Source inputs are copied into the run, and the MCP
server and hook execute that retained copy. The child environment is explicit; it includes the
real home identity for the harness's credential store but no inherited provider
keys, alternate endpoints, proxy or library-injection settings.

The dedicated login is at
`~/.local/share/stewart-claude-code/probe-config`. Only Claude accesses its
credential store. The existing manager-operated login is reused; the current
runner performs no login flow. Authentication reports retain only `loggedIn`,
`authMethod` and `configDirectory`; raw authentication output is discarded. Model inputs use
empty working directories under `/private/tmp`, outside the repository's
instruction ancestry. Their locations are recorded in the run state.

## Checks

Run these offline checks from the repository root:

```sh
python3 -I -B apparatus/claude-code/test_pin.py
python3 -I -B apparatus/claude-code/test_probe.py
python3 -I -B apparatus/claude-code/test_protocol.py
```

The pin/probe checks launch only synthetic Python processes. The probe checks cover actual
MCP/hook traffic, positive/denial/invariance cases, exact raw capture, broken
witnesses, malformed streams, unexpected tools, quota/auth routing refusal,
durable invocation reservations, and stopping an uncooperative process and a
descendant. Host process-group observation must work; an observation denied by
an agent sandbox is a failed check, not an inferred successful stop. Controls
for a fresh commission also verify offline preparation, prior-record
preservation, the approval gate, the single fresh
authentication check, all three synthetic cases and refusal of another start.

`test_protocol.py` compiles an offline Rust transport prototype with the native
toolchain and existing locked, vendored dependencies. Cargo runs offline; its
cache is `service/target-local/protocol-check/`. The test executables and
synthetic work directories are temporary. The check launches only those Rust
executables and its local peer, never Claude. It needs Unix socketpairs but no
listening network socket or credential. Retain command output through review.

The prototype owner captures received chunks before framing/decoding and the
response before sending it. Its sole tool records a synthetic note. The relay
forwards bytes over an inherited socket in both directions; it never opens
an archive, interprets arguments or reconnects. Peer bytes witness the capture
independently. Controls cover initialization, version negotiation, notifications,
typed request IDs, malformed input, protocol versus tool errors, exact argument
spans, capture failure, incomplete/oversized frames, pending cancellation,
publication refusal, duplex backpressure and owner loss. Numeric IDs in this
prototype use integer notation. The prototype caps frames at 8 MiB, arguments
at 4 MiB and request IDs at 4,096 per session; these are apparatus bounds.

The prototype is separate from the implemented service adapter and its
[independent driver](../driver/CLAUDE-CODE.md). Its pending-publication controls
model ordering in memory; they do not test the service's named socket, archive
publication/recovery or orphan stopping. The service driver exercises those
integrated paths with a synthetic harness, with its own stated coverage gaps.
Linux qualification remains outstanding. See the
[runtime reference](../../docs/claude-code/RUNTIME-REFERENCE.md#offline-rust-protocol-check)
for the protocol comparison and its limits.

`fake.py` is the offline harness peer. `fixture.py` is the same MCP server and
hook used by the real probe. Raw requests are captured before parsing. The
effect witness, hook observations and raw traffic live outside the controlled
working directories. A failed witness prevents a successful tool reply; a
failed hook witness returns a blocking exit code.

New observations name their clock and observer PID. They use the kernel's
`CLOCK_UPTIME_RAW` on macOS and `CLOCK_MONOTONIC` on Linux so separate processes
share a clock origin. Python versions before 3.10 give macOS
`time.monotonic_ns()` a process-local origin. Older records that used it support
timing within one observer only; never rewrite them to imply a shared clock.

## Inspecting the closed commissions

The original runs are `.scratch/claude-code-probe-01` and
`.scratch/claude-code-probe-02`. Their frozen `inputs/` own the source and scope
that executed. The [runtime reference](../../docs/claude-code/RUNTIME-REFERENCE.md#reviewed-native-comparison)
records the reviewed observations and their limits. No remaining invocation or
replacement authority exists. A full-service check needs new apparatus and a
separately approved bounded commission; these two-tool results cannot supply its
profile attestation.

Inspect `RESULT.json`, each case's `assessment.json`, `process/` captures and
the independent effect, hook and MCP journals. A hook denial is observed only
when an attempted record is witnessed and never reaches the handler. Absent
attempts are unexercised. A matching startup inventory does not prove the absence
of unobservable instructions, internal requests or managed policy. The code does
not establish filesystem confinement or a complete credential leak detector.
Raw model/harness output stays private and is not automatically exported.

Keep the original failed and successful observations through review under
[evidence and retention](../../development/DEVELOPMENT.md#evidence-and-retention).
