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

`probe.py` prepares a fresh bounded commission in `.scratch/claude-code-probe-02`.
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

Run from the repository root, before any real harness invocation:

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

This is not a service adapter or an acceptance driver. The pending-publication
controls model ordering in memory. Private named-socket attachment, actual
archive publication/recovery, orphan stopping and Linux enforcement remain
integration work. See the [runtime reference](../../docs/claude-code/RUNTIME-REFERENCE.md#offline-rust-protocol-check)
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

## Running a commissioned probe

These commands require the principal's bounded permission; documentation is
not authority to start Claude. The pin's version, model and limits are fixed
in the scripts. No model substitution, resumed session or replacement attempt
is implemented.

The executable pin and harness-owned login must already be verified. The
current preparation reads the pin receipt and prior nonsecret setup/run
records, checks the executable and snapshots the new inputs. It preserves the
stopped run and creates new working directories,
source snapshots and witnesses; no invocation reservation is transferred.

Prepare the inputs without launching Claude:

```sh
python3 -I -B apparatus/claude-code/probe.py prepare
```

Preparation is exclusive. If it already began or failed partway through, inspect
its files before further action; never erase evidence to force a retry. Both
source copies and working sources are hashed, so an edit after preparation
stops execution for review.

Only after explicit approval of probe 02, with paid overflow disabled, run on
the native host:

```sh
python3 -I -B apparatus/claude-code/probe.py live --approved-probe-02 --extra-usage-disabled
```

This first spends one non-model `auth status` invocation, with a 30-second
deadline, requiring the dedicated directory, a logged-in `claude.ai` route and
exit 0. A failed or uncertain check consumes that attempt and blocks model use.
The approval flag relays the principal's decision; documentation is not approval.

It starts at most three sequential sessions, each with one input and at most
four harness turns. Each session is terminated at 120 seconds; the whole phase
has a six-minute deadline. Termination allows five seconds before SIGKILL.
Process-group stopping is observed and recorded. Startup must report exactly
the two probe tools and the three pinned built-ins: `cc-plugin-agents-md`,
`cc-plugin-privacy` and `cc-plugin-plugin-authoring`, each with `path: "builtin"`
and its own `@builtin` source. Missing, extra, duplicated or changed plugin
entries refuse; inventory ordering has no meaning. Unexpected startup inventory,
API-key routing, model selection, background work, retries, compaction, quota
exhaustion or failed supervision ends the batch. The final summary records
unlaunched cases as unexercised. Missing usage is unknown, never zero.

Inspect `RESULT.json`, each case's `assessment.json`, `process/` captures and
the independent `effects.jsonl`, hook and MCP journals. A hook denial is only
observed when an attempted record is witnessed and never reaches the handler.
Absent attempts are unexercised. A matching startup inventory does not prove
the absence of unobservable instructions, internal requests or managed policy.
The code does not establish filesystem confinement or a complete credential
leak detector. Raw model/harness output stays private and is not automatically
exported.

Keep the original failed and successful observations through review under
[evidence and retention](../../development/DEVELOPMENT.md#evidence-and-retention).
