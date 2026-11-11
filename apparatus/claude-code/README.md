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

`probe.py` runs one bounded commission in `.scratch/claude-code-probe-01`.
Invocation reservations are persisted before spawning. A failed or uncertain
reservation is not repeated; setup and the model phase each start only once.
The source, executable, prompt, settings and MCP configuration are hashed and
checked before invocation. Source inputs are copied into the run, and the MCP
server and hook execute that retained copy. The child environment is explicit; it includes the
real home identity for the harness's credential store but no inherited provider
keys, alternate endpoints, proxy or library-injection settings.

The dedicated login is at
`~/.local/share/stewart-claude-code/probe-config`. Only Claude accesses its
credential store. Setup requires a terminal and leaves the login interaction
uncaptured. Authentication reports retain only `loggedIn`, `authMethod` and
`configDirectory`; raw authentication output is discarded. Model inputs use
empty working directories under `/private/tmp`, outside the repository's
instruction ancestry. Their locations are recorded in the run state.

## Checks

Run from the repository root, before any real harness invocation:

```sh
python3 -I -B apparatus/claude-code/test_pin.py
python3 -I -B apparatus/claude-code/test_probe.py
```

These launch only synthetic Python processes. The probe checks cover actual
MCP/hook traffic, positive/denial/invariance cases, exact raw capture, broken
witnesses, malformed streams, unexpected tools, quota/auth routing refusal,
durable invocation reservations, and stopping an uncooperative process and a
descendant. Host process-group observation must work; an observation denied by
an agent sandbox is a failed check, not an inferred successful stop.

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

Fetch and verify the installed pin, retaining a new evidence directory:

```sh
python3 -I -B apparatus/claude-code/pin.py "$PWD/.scratch/claude-code-pin-01"
```

If only verification failed, `--verify-only` uses the existing downloads and
records a separate verification attempt. It does not overwrite the earlier
failure. Do not rerun after a successful `pin.json` receipt already exists.

After the offline checks pass, run setup **in the manager's own Terminal**:

```sh
python3 -I -B apparatus/claude-code/probe.py setup
```

It uses four non-model CLI invocations: version, help, authentication status
against an empty configuration, and status against the selected configuration.
Between the two status calls, the manager completes one harness-owned login.
Unexpected options or authentication stop setup. Login codes and credentials
must remain in that terminal/browser interaction.

The pinned CLI hides some supported options from help. The checker uses the
visible inventory together with the reviewed option registrations in the
authenticated binary; it does not treat help as an exhaustive inventory.
For the reviewed stop after successful version/help calls, continue in the
manager's own Terminal with:

```sh
python3 -I -B apparatus/claude-code/probe.py finish-setup
```

This accepts only that exact checkpoint and original checker binding. It
preserves the original controller and captured outputs, adds a correction
receipt and controller snapshot, and uses only the remaining authentication
checks and login. No completed or uncertain invocation is repeated, and the
approved arguments and limits stay the same. Any other stopped state needs
review before further action.

After setup, with paid overflow disabled, the commissioned model phase is:

```sh
python3 -I -B apparatus/claude-code/probe.py live --extra-usage-disabled
```

It starts at most three sequential sessions, each with one input and at most
four harness turns. Each session is terminated at 120 seconds; the whole phase
has a six-minute deadline. Termination allows five seconds before SIGKILL.
Process-group stopping is observed and recorded. Unexpected startup inventory,
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
