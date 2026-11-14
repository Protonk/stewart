# Claude installation and check apparatus

This apparatus prepares installation evidence and reviewed runtime profiles,
and retains the earlier two-tool native experiments. Profile preparation and
assembly launch no Claude process. The closed probes and their offline controls
remain separate from Stewart's service and independent acceptance driver.
Python uses only its standard library.

## Preparing a profile

`profile.py prepare` verifies the retained public manifest/signature again with
an isolated GPG keyring, checks the selected native executable's digest and
Apple code signature, and writes exact `launch.json` and `installation.json`
values. `PREPARATION.json` records the verification time, their bindings and an
inventory of every retained public verification input and command result. The
producer checks the named login directory's existence without reading its
contents. It does not execute Claude, query authentication or issue a check
attestation. It currently uses the selected native pin supported by `pin.py`.

```sh
python3 -I -B apparatus/claude-code/profile.py prepare \
  --pin-receipt /absolute/retained-pin/pin.json --output /absolute/new-installation \
  --config-directory /absolute/dedicated-login --home /absolute/home \
  --temporary-directory /absolute/temporary
```

An initial supplied-surface check uses the actual Stewart helpers with an
independent fixture's sockets and complete selected-family tool inventory.
Its observations concern the supplied surface and fixture effects, not the
audit core. A separately reviewed, real-harness result can supply the profile
attestation needed for a subsequent service comparison. Synthetic rehearsals
cannot. No live runner or live commission is supplied by the profile producer.

```sh
python3 -I -B apparatus/claude-code/profile.py assemble \
  --installation-directory /absolute/installation \
  --observation-directory /absolute/observation --review /absolute/CHECK.json \
  --output /absolute/new-profile.json
```

Assembly checks every retained evidence member, the original launch bytes,
surface/tool/model bindings, required observed comparisons and stopping, and
the independent review's binding to the observation. It rechecks the installed
executable's digest. The profile preserves the original launch JSON value,
including internal whitespace. Its `check.evidence_sha256` is the SHA-256 of
the exact `CHECK.json` bytes. Existing outputs, missing/unlisted evidence,
links, special files, failed/unexercised comparisons and rehearsal observations
are refused. Output must stay outside both input evidence directories, so
publication cannot invalidate their inventories. Reading installation receipts during assembly does not repeat
the signature verification performed by `prepare`. Neither command grants
authority to launch or resume Claude.

### Check evidence interface

The observation directory contains `OBSERVATION.json`, `EVIDENCE.json` and its
regular-file members. `CHECK.json` is supplied separately by an independent
reviewer and may be stored there too. The manifest covers every other file;
it excludes these three records to avoid circular hashes. Socket workspaces
stay outside the evidence directory.

- `EVIDENCE.json`: schema `stewart.claude-code.surface-evidence/1` and `members`,
  an array of `{path,bytes,sha256}`. Paths are unique relative paths without
  traversal. The required exact input files are `inputs/launch.json`,
  `inputs/surface.json` and `inputs/tools.json`; their hashes bind file bytes.
- `OBSERVATION.json`: schema `stewart.claude-code.surface-observation/1`,
  `mode` (`real-harness` or `synthetic-rehearsal`), `scope` (`supplied-surface`),
  `started_at`, `finished_at`, `launch_sha256`, `surface_sha256`, `tools_sha256`,
  `model`, `evidence_manifest_sha256`, `checks` and `stopping` (`observed` or
  `unknown`). A check has `id`, `outcome` (`observed`, `failed` or `unexercised`)
  and `evidence`, a list of retained manifest paths. The independent fixture's
  `REQUIRED_CHECKS` inventory owns the required comparisons.
- `CHECK.json`: schema `stewart.claude-code.reviewed-check/1`, `scope`
  (`supplied-surface`), the same four launch/surface/tools/model bindings,
  `checked_at` (the observation's `finished_at`), `observation_sha256`,
  `reviewer`, `reviewed_at` and `outcome` (`observed`). Times are actual UTC
  timestamps ending in `Z`; the review follows the completed observation.

The producer requires real-harness mode, every required comparison observed
with retained witnesses, and observed stopping. Authentication raw output is
never an evidence member: the invocation library discards it and retains only
the allowlisted `loggedIn`, `authMethod` and `configDirectory`. A review is an
attributed assessment, not a cryptographic identity or an exhaustive record of
provider activity, hidden instructions or managed policy.

## Supplied-surface controller

`surface_check.py` connects the invocation budget, independent observer and
actual Stewart helpers. Preparation creates a fresh packet with frozen source,
public installation evidence, exact inputs and three distinct workspaces. It
starts nothing. The proposed live allowance is three `auth status` invocations
of at most 30 seconds and three model sessions of at most 120 seconds, within
one 450-second process deadline. The comparisons are positive, hook denial and
fresh-session invariance for one selected family's complete tool inventory.
Only the fixture's declared `record_account` effect is implemented. This is
supplied-surface compatibility; service behavior and compaction remain separate.

```sh
python3 -I -B apparatus/claude-code/surface_check.py prepare \
  --output /absolute/new-packet --binary /absolute/gated-stewart \
  --installation-directory /absolute/installation --model SELECTED_MODEL
python3 -I -B apparatus/claude-code/surface_check.py inspect --packet /absolute/new-packet
```

The emitted `COMMISSION.json` binds the ordered invocation budget and names its
scope, model, supplied surface and unexercised properties. Review those exact
bytes, all six slots, synthetic question, tool inventory and stop conditions
before asking the principal for permission. Preparation and earlier commissions
confer none. Only after explicit bounded approval, use the printed frozen
controller with the packet's bound Python interpreter:

```sh
ABS_PYTHON -I -B /absolute/new-packet/sources/apparatus/claude-code/surface_check.py run \
  --packet /absolute/new-packet --approved-commission EXACT_APPROVED_SHA256 \
  --extra-usage-disabled
```

The digest argument conveys the principal's approval; it does not authenticate
the caller. The extra-usage flag asserts the required account setting rather
than changing or independently verifying billing controls. A fresh private
authentication check precedes each model start. Failed authentication, changed
inputs, observer failure, missing EOF, unknown stopping or a reused session
halts the batch. An entered packet cannot be restarted. Inspect uncertainty
before proposing any replacement; no retry or leftover allowance is automatic.

The run keeps process records, independent fixture witnesses and frozen inputs
under `observation/`. `RESULT.json` reflects the independent aggregate assessment
and is included before its manifest freezes. Partial runs retain a failed result
and evidence inventory; they cannot supply an eligible check. Real authentication
raw output stays private and is discarded. This workflow neither reads the
credential store nor executes any login flow.

Successful completion still requires independent review of the original streams,
positive/denial/invariance effects, exact bindings and process records. After
that review, an identified reviewer can record the exact observation digest:

```sh
ABS_PYTHON -I -B /absolute/new-packet/sources/apparatus/claude-code/surface_check.py attest \
  --packet /absolute/new-packet --reviewed-observation OBSERVATION_SHA256 \
  --reviewer REVIEWER --output /absolute/new-packet/observation/CHECK.json
```

`attest` checks the evidence inventory and completed budget, then records the
caller's explicit assessment. It does not perform the intellectual review or
authenticate the reviewer. `profile.py assemble` separately validates and embeds
that review. No run automatically writes a review or profile, and neither grants
authority to start a service placement.

### Synthetic controller rehearsal

`prepare-rehearsal --output /absolute/new-packet --binary /absolute/gated-stewart`
constructs a fixed [synthetic peer](../driver/CLAUDE-CODE-PEER.md) wrapper instead
of accepting a real installation. Run its frozen controller with
`run-rehearsal --packet /absolute/new-packet`. It accepts no live approval.
The three scenarios are `normal`, `bad-init` and `wrong-auth`; the latter two
are expected failure controls. Each has at most six synthetic invocations,
10 seconds per auth, 30 per model and 120 seconds overall. No Claude process,
provider or credential store is involved.

The peer exercises actual relay/hook helpers and keeps its own raw traffic and
environment witnesses. A fully written, exclusively published
`startup-observed.json` coordinates the synthetic peer after startup validation;
real mode never writes it. This schedules the fake peer and makes no claim about
real-harness startup ordering. Rehearsal observations remain explicitly synthetic
and both attestation and profile assembly refuse them. The controller's unit
review records are labelled parser fixtures, not live evidence.

## Native service comparison procedure

`service_check.py` freezes one already-prepared open-inquiry audit with a
reviewed profile. Its version-2 commission binds exact input, preparation,
arrangement and source bytes, the original writer, profile, harness executable
and Python interpreter. Preparation launches nothing. Experiment bounds are one
to three service starts, at most 600 seconds per placement and 900 seconds per
packet. Each start permits one authentication check and at most one model
session; the placement deadline includes authentication. These are apparatus
bounds, not product limits. The current controller refuses superseded packet
schemas; retained historical packets keep their original frozen source.

```sh
python3 -I -B apparatus/claude-code/service_check.py prepare \
  --output /absolute/fresh-packet --preparation /absolute/prepare-reply.json \
  --reference stw1:... --folder /absolute/submission --writer /absolute/stewart
```

Only after the principal approves the exact commission, use its bound Python
and frozen controller. The extra-usage flag conveys the account-setting
assertion; it does not verify billing or change a setting.

```sh
ABS_PYTHON -I -B /absolute/fresh-packet/sources/claude-code/service_check.py run \
  --packet /absolute/fresh-packet --placement 1 \
  --approved-commission EXACT_APPROVED_SHA256 --extra-usage-disabled
```

Each exclusive `placements/N` directory consumes that numbered attempt even if
acceptance or launch fails. Commissioning precedes the first run; exact receipt
readbacks precede every run. There is no automatic retry, continuation, close or
next audit. Each command retains its argv, environment, stdout, stderr and
process stopping observations. The run command's observation deadline adds
15 seconds for return and observation beyond the service placement deadline;
it grants no additional model time. Failed or uncertain work requires review.

After return, the procedure reads service-owned auth/model group identities and
independently probes absence. Missing, present or unknown groups block further
mutation. A run command that times out, exits unexpectedly or returns an unusable
reply stops only its client group, so the same probe still runs, up to six times
a second apart, before the failure is reported. `STOPPING.json` names its clock
and observer and keeps every observation; `stopping_probed` in the result
separates a probe that was never made from one that found a group present.
Once stopping is established, it retains complete archive and package
snapshots outside the archive and default, detailed and JSON status. These
private copies preserve service-owned provenance; they are not product exports
or independent provider captures. The copies are written with the procedure's
own modes, so the delivered package's directory and file modes are read from
the original at capture and compared with INTERFACE 8.2 in review. No raw
authentication output is read.

Use the frozen controller's `review --packet PATH --placement N`. It verifies
the complete execution inventory, correlates each placement's captured MCP calls
and replies with the cumulative entry ledger, and checks payloads and citations
against outside inputs. It reconstructs a submitted package with the independent
package witness. Reviews keep assistant frames and message usage snapshots
separate from result reports, without summing overlapping snapshots. A shared
omission in service-owned records can escape correlation. Original streams,
startup, usage, notice delivery and stopping still need independent review.

A later explicit `run` also requires `--reviewed-review SHA256`, naming the
preceding `placements/N/review/REVIEW.json`. The procedure revalidates that review
and every earlier execution, then checks current status, stopping and archive
bytes. Only an open audit interrupted by its commissioned placement deadline, with
unused starts, can continue. The service's cause label does not establish that
deadline alone: review also requires the procedure's own measurement of the run
command to reach the placement deadline and the retained stop record to show the
elapsed time and absent groups. Other interruptions need a separate disposition. Ended,
sealed, closed, damaged or uncertain work cannot. Every subsequent capture must
preserve earlier archive members. A failed attempt cannot be skipped or repeated.

After reviewing an auditor-submitted package, `close --packet PATH --placement N
--reviewed-review SHA256` permits ordinary close. It rechecks the latest attempt,
commission, evidence, current stopping and archive/package bytes and modes, then preserves
new snapshots and verifies all earlier members remain unchanged. Unsubmitted
cases remain retained for explicit disposition. Close launches no model.

For offline preparation use `prepare-rehearsal --output PATH --writer BINARY
--work FRESH_ABSOLUTE_PATH`. Six synthetic comparisons exercise early submission,
bad initialization, three-placement deadline continuation and its invariance,
the last allowed deadline, and ordinary unsubmitted ending. The continuing peer
keeps independent per-session witnesses and reads prior entries before adding
work. Its single result checkpoint and overlapping assistant snapshots distinguish
cumulative accounting from per-message reports. It never rewrites the scenario
between starts.

Run the positive packet's frozen controller with `rehearse --suite PATH
--rehearsal-sha256 SHA256`, binding the prepared `REHEARSAL.json`. This one-use
native runner accepts only synthetic packets. It exercises explicit run/review
steps, bad-review and skipped-start controls, refusal after seal/ending/exhaustion,
and reviewed close with unchanged packages. Each comparison must take its expected
submitted or unsubmitted branch, and each submitted package must show the
specified delivered modes. It retains unsubmitted controls and
copies the original peer witnesses for independent review. It launches no real
Claude process and establishes neither live authority nor Linux qualification.


## Bounded invocation library

`bounded.py` supplies launch controls for the supplied-surface controller. The
library has no live command-line entry or built-in commission. The
[independent observer](../driver/CLAUDE-CODE-OBSERVER.md) owns stream validation,
fixture sockets and comparison assessments. `prepare(root, budget)`
freezes `BUDGET.json` without executing anything. The
`stewart.claude-code.invocation-budget/1` record names a purpose, mode, overall
deadline allowance, file bindings and an ordered list of invocations. Each
invocation fixes its id, auth/model role, argument vector, complete environment,
working directory, base64 input bytes and timeout. Every executable must be a
bound regular file. A model slot requires its own immediately preceding auth
slot; a live pair must use the same executable, environment and directory.
These are apparatus controls, not a replacement for validating the full runtime
surface and the principal's commission.

`Budget(root, approved_digest, extra_usage_disabled)` locks the batch and refuses
a live budget without its exact approved digest and the assertion that paid extra
usage is disabled. It persists `START.json` before any reservation. The digest
argument records authority conveyed by the caller; it does not authenticate the
principal or infer permission. A rehearsal accepts no live approval. No started
batch can be reopened, even after a failure or lost reply. Unstarted allowances
are recorded at closure and cannot be reused.

`execute(id, on_stdout, on_stderr, check_stop)` rechecks all bound files and
the frozen budget before reserving the next slot. A separate guard establishes
its own session, waits for the owner to persist `group.json`, and only then may
fork and execute the requested process. Owner EOF or the shared kernel-clock
deadline stops the whole owned group with TERM followed by KILL after 0.3 seconds.
Normal worker exit also stops remaining descendants. The worker's exit and
observed group absence are separate results. This controls cooperative process
groups; it does not confine escaped descendants or guarantee progress during
host/kernel failure. Unknown stopping or any failed invocation blocks another
start. `halt(reason)` also closes the batch after an independent assessment fails.

Model stdout/stderr are retained before callbacks run. The periodic `check_stop`
callback lets a fixture failure stop an otherwise silent process. Results bind
retained stream bytes and the written input prefix and identify actual stream
EOF. The controller must pass those EOF observations to its independent observer,
review its final assessment, and halt on failure before another slot. Bytes
drained during stopping remain captured but are not parsed into a successful
observation. Authentication receives no callbacks: stdout/stderr stay in bounded
private buffers, raw output is discarded, and only the typed `loggedIn`,
`authMethod` and `configDirectory` fields are retained. A successful route is
exactly `true`, `claude.ai` and the bound configuration directory.

The apparatus permits at most 32 slots, six hours per batch, 1 MiB of input per
slot, 64 KiB of combined auth output and 32 MiB of model capture. Its intended
comparisons are short synthetic tasks. These bounds do not qualify Stewart's
product limits or authorize a usage-limit study.

## Closed native probes

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
python3 -I -B apparatus/claude-code/test_profile.py
python3 -I -B apparatus/claude-code/test_bounded.py
python3 -I -B apparatus/claude-code/test_surface_check.py
python3 -I -B apparatus/claude-code/test_probe.py
python3 -I -B apparatus/claude-code/test_protocol.py
python3 -I -B apparatus/claude-code/test_service_check.py
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

Profile controls use temporary synthetic signature/observation/review records,
never real-harness evidence. They exercise exact launch-byte preservation,
review/input bindings, changed/missing/unlisted witnesses, symlink/special-file
refusals, changed executables, failed installation verification, rehearsal
refusal and normal invariance. A canary executable witnesses that the producer
never starts the harness; credential-canary reads are separately refused.

The bounded-launch controls execute only Python peers. They retain their run
directory and cover approval/refusal without execution, reservation and group
record failures, exact capture before observer callbacks, authentication canary
discard, changed bindings, one-use slots, failed independent assessments, silent
fixture failure, worker/descendant stopping, owner loss and an observer that
stalls beyond the process deadline. The owner-loss control retains its bounded
group-status observations: permission denial remains unknown, and only an
explicit absence observation passes. Cleanup failures are recorded separately
and no cleanup signal is sent after observed absence. These controls establish
no real-harness observation.

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
The [qualification record](../qualified.md) identifies the integrated service's
Linux synthetic acceptance runs; they do not qualify this prototype or establish
real-harness conformance. See the
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
