# Independent harness observer

`claude_code_observer.py` observes the
[supplied-surface fixture](CLAUDE-CODE-SURFACE.md) through a separately supervised
process. It derives its checks from the
[runtime contract](../../docs/claude-code/CONTRACT.md), without reading the service
implementation. It starts no process, sends no signal, approves no invocation and
changes no invocation budget. The root-owned launcher remains responsible for
permission, reservation, exact process creation, input writes, deadlines and
observed stopping. There is no live command in this module.

```sh
python3 -I -B apparatus/driver/claude_code_observer.py --self-test
python3 -I -B apparatus/driver/claude_code_observer.py \
  --rehearse-listeners --work /absolute/path/to/fresh-evidence
```

The self-test uses synthetic stream events and socketpairs. The listener rehearsal
adds actual Unix listeners with controlled synthetic peers. Both supply synthetic
authentication and process-result controls; neither launches a subprocess or
Claude. A socket-bind denial is a failed comparison, not a skipped or passing
control. Every generated directory remains available through review.

## Launcher boundary

Construct `CaseObserver(prepared_inputs, case_id, kind, workspace, evidence_dir)`
with absolute paths. Inputs follow the surface fixture's prepared files. `kind`
is `positive`, `closed-gate` or `invariance`. The workspace is outside the project
and evidence tree; its path must fit the Unix socket limit. The evidence directory
must be fresh. The observer copies the inputs before accepting observations.

| Method | Caller obligation and result |
| --- | --- |
| `start_listeners()` | Binds the fixture's `m` and `h` sockets; returns their paths. It launches nothing. |
| `record_launch(record)` | Call before model output is fed. The record has `argv`, `env`, `cwd`, `executable_sha256` and `files_sha256`, the latter mapping `settings.json`, `mcp.json` and `system.txt` to digests. Values must match the exact launch submitted by the separate launcher. Workspace file bytes are independently checked. |
| `feed(raw)`, `feed_stderr(raw)` | Receive only model stdout/stderr, after the launcher durably captures each chunk. The observer retains its own exact mirror. An `ObserverStop` requests termination by the launcher. |
| `check_stop()` | Poll while waiting, including when stdout is silent. Fixture-thread failures close the gate immediately and make this method raise `ObserverStop`. |
| `record_input(attempted, confirmed_prefix)` | Record the frozen first input and bytes actually written. The launcher may call this after its write completes or after execution, before `finish`. Partial or different writes fail. |
| `finish_stream(channel)` | Call only after actual EOF on `stdout` or `stderr`. An incomplete stdout frame fails and remains retained. |
| `finish(process_result, sanitized_auth_receipt)` | Call after stopping/reaping has been observed. This drains fixture connections for a bounded interval, checks independent capture/input digests and writes `CASE.json`. The caller must halt the batch on failed or unexercised assessment, including failures found after process exit. |

`process_result` uses the launcher's fields `exit`, `stop`, `group_gone`,
`guard_reaped`, `elapsed_seconds`, `input_bytes_sent`, `guard_reason`,
`capture_bytes`, `capture_sha256`, `input_prefix_sha256` and `stream_eof`.
The three channel maps use `stdout` and `stderr`. Success requires exit zero,
no controller stop, `guard_reason: worker-exit`, observed group absence and guard
reaping, both stream EOFs and matching complete captures. Exit zero alone cannot
turn a controller/watchdog stop into success. Final launcher drain bytes omitted
from observer callbacks produce a capture mismatch, preserving the incomplete
observation rather than reconstructing a pass.

Authentication is separate. The launcher privately buffers and validates it,
then passes exactly `loggedIn`, `authMethod` and `configDirectory`; the observer
accepts only `true`, `claude.ai` and the bound directory. It never receives raw
authentication stdout or stderr. Extra receipt members are rejected without
being written to evidence. Neither observer nor fixture reads the credential
store. Successful authentication and a matching startup are observations, not
authority or independent billing verification.

## Comparisons and limits

No fixture effect is admitted before the specified startup event passes.
Version, model, key route, permission mode, complete tools, the sole connected
server and all three built-in plugins are checked. A repeated or malformed init,
startup errors, a delegated session, unpinned assistant tool, background-task
start, plugin installation, retry, rejected quota or enabled/in-use overage
requests stopping. Unknown metadata remains captured. These checks cover the
named observable event forms, not all hidden provider work or managed policy.

After valid startup, the positive cases open the fixture gate. The denial case
keeps it closed. A denial comparison needs an actual hook attempt for the
specified `record_account`, correlated to the validated session and a tool-use
ID, the exact deny reply, and no MCP call or effect. No attempt is **unexercised**.
A call that reaches MCP despite denial is **failed**, even if the fixture refuses
it and no effect occurs. Positive/invariance cases need exactly one matching
hook, call and independent effect. The repeated case uses a distinct workspace
and fresh session. Controller-injected helper calls must never be used as evidence
of a real-harness attempt; the rehearsal identifies its synthetic peer origin.

The fixture implements one controlled effect while listing the complete selected
family's schemas. Its effects are not audit-core publication or service
conformance. This initial comparison uses one fixed input; an unexpected
compaction boundary stops it without claiming notice delivery or compaction
conformance. Those require the later controller and separately bounded work.
Original usage fields remain reported; missing or malformed checkpoints remain
unknown, and provider completeness is unverified.

Raw socket chunks are retained before framing or EOF. Hook connections have
separate received/supplied witnesses. Malformed input and partial bytes survive
failure. Forced socket closure is not mistaken for peer EOF: after the launcher
observes its group gone, the observer allows one second for peer-thread drain,
then closes its resources with a further half-second join budget. Incomplete
drain, missing EOF or a surviving observer thread fails the observation. These
local timeouts assume the observer and host continue running; the launcher must
keep its independent watchdog. Frames are bounded at 8 MiB and observer evidence
writes at 256 MiB per case. Events name their observer and shared kernel clock.

## Evidence

`assess_batch(root, cases, mode)` takes completed positive, closed-gate and
invariance observers in that order. The caller explicitly declares
`synthetic-rehearsal` or `real-harness`; this is a provenance declaration, never
permission. The function writes the existing `EVIDENCE.json` and `OBSERVATION.json`
forms consumed by the [profile producer](../claude-code/README.md), binding exact
launch, surface, tools, model, input files, case evidence and source snapshots.
It never writes a reviewed `CHECK.json` or profile. Independent review is still
required, and the producer refuses rehearsal observations.

Create all control results before manifest finalization. No additional evidence
files may be added afterward. The listener rehearsal writes `REHEARSAL.json`
before finalizing its manifest: five controls cover positive, denial, invariance,
bad startup and a listener witness failure. Negative-control failures remain in
their original case records. A run interrupted before all three comparisons
finish retains partial case evidence and does not emit an eligible batch record.
Keep originals under the repository's
[evidence rules](../../development/DEVELOPMENT.md#evidence-and-retention).
