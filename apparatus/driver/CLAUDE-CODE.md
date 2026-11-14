# Offline development profile checks

`claude_code.py` independently checks preparation, custody and synthetic runtime behavior in the
[Claude Code development runtime contract](../../docs/claude-code/CONTRACT.md).
Its author works from that contract, the common specifications and this driver's
specification-owned forms, without reading the service implementation or tests.
It is a standalone driver, run separately from the release driver both natively
and by the Linux container acceptance suite.

Run from the repository root with an explicit Python 3.9 or later interpreter.
The driver supports macOS arm64 and Linux aarch64/x86_64. Runtime checks need a
host that permits Unix-domain socket listeners and observation and signalling
of owned process groups. A sandbox denying those operations prevents the
controls from firing; it does not establish a passing runtime result.
Use a binary built with the default-off `claude-code` feature for `--binary`
and a featureless binary for `--release-binary` (see
[development checks](../../development/DEVELOPMENT.md#what-to-run-for-what-you-changed)).

```sh
python3 -I -B apparatus/driver/claude_code.py --self-test
python3 -I -B apparatus/driver/claude_code.py --list
python3 -I -B apparatus/driver/claude_code.py \
  --binary /absolute/path/to/development/stewart \
  --release-binary /absolute/path/to/featureless/stewart \
  --variant-binary /absolute/path/to/another/development/stewart \
  --work /absolute/path/to/fresh-work-directory
```

`--work` must be absent and its parent must exist. Use a physical absolute path
without symlink components because the profile contract requires no-follow
reads. Put the work directory outside the repository checkout so that the
synthetic launch directory is outside the writer tree. The driver refuses known
repository descendants before creating its work directory or any fixtures.
Keep the selected
binaries in a separate directory from the work tree and unchanged during the run.
`--release-binary` is optional; omitting it reports the featureless-build
case as skipped. `--variant-binary` is optional too: it names a second build
with `claude-code,fault-injection` and a different digest. It exercises both
writer invariance and the documented `log.publish:seal=pause` control. Omitting
it skips those cases; a variant without fault injection skips the publication
case. The
driver never substitutes a skipped check for a pass.
Use repeatable `--case NAME` options to diagnose selected cases; `RESULT.json`
names the unselected cases separately. The default runs every case.

The preparation cases use local `new`, `prepare`, `commission`, `receipt` and
`status` operations and a shell canary that records an unexpected invocation.
Runtime cases call `run` with a synthetic executable implemented by this driver.
It supplies synthetic authentication and startup observations and talks to the
actual Stewart MCP adapter through its configured stdio command. It never invokes
a Claude executable, real authentication probe, login, provider or model.
The embedded installation and check entries are
synthetic attestations for offline input validation; they establish no signature
verification, installation check or authority for a real session.

The direct `runtime-relay-forwarding` case invokes only the hidden
`__stewart-cc-relay m` helper against an independently owned Unix socket. It
requires exact arbitrary bytes, including NUL, invalid UTF-8 and a final segment
without LF, in each direction while both inputs remain open. The same bytes sent
whole and in three segments must arrive before EOF; each segment is observed
before the next is sent. Separate cases half-close the socket immediately after
sending a reply, before observing stdout, and close empty inputs. A raw pipe
control exercises the same observer with an idle writer, bytes while the writer
remains open, and EOF.

Each direct helper runs in a worker's process group. A separate owner bounds the
whole worker, including setup, process creation, reads and cleanup: eight seconds
per traffic variant, two for the pipe control, then up to 1.5 seconds each for
group stopping. The owner retains incremental progress and byte witnesses and
never reads helper stdout. A stalled read therefore cannot hold that owner inside
the read. If group absence cannot be observed, further selected cases are skipped
with that explicit reason; qualification cannot pass. This watchdog assumes the
owner and host continue running. The synthetic harness's nonblocking reader also
records read checkpoints and handles ordinary readiness races; nonblocking mode
alone does not bound a kernel read stall.
Relay sockets and working directories live under `relay-work/`; their independent
progress and byte witnesses live under `witness/relay-forwarding/`.

MCP envelopes and independent transport witnesses use a separate JSON decoder
that accepts signed JSON-RPC error codes. Embedded Stewart core replies and
archive records retain their strict control decoding. Envelope checks follow
the [MCP base protocol](https://modelcontextprotocol.io/specification/2025-11-25/basic)
and [stdio framing](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).
The self-test exercises a negative transport error through witness readback and
the invalid-startup checks, with malformed and duplicate-member controls.

The cases exercise all three question families, exact transformed MCP schemas
and pinned texts, profile/check binding refusals, strict JSON and profile path
controls, and captured receipt readback. Field cases cover the one question
version: placement bounds, a missing placement field, a Messages limit beside a
profile, a placement field without one, and the removed version refused by
name. Help and presentation cases check the build notice, the runtime topic's
stated facts, the four run requirements, the summary's placement facts and
agreement in number, and that human output names the profile by path and digest
without printing its text. With a featureless binary, the runtime fields are
unknown keys, the topic and notice are absent, and both builds write the same
scaffold.
Invariance cases change outer profile whitespace, manager HOME/CWD and accepted
source files.

The driver rebuilds the [launch surface](../../docs/claude-code/CONTRACT.md#launch-surface)
from the contract's member table and its own copies of the pinned texts. Its
self-test compares that reconstruction with the contract's worked example and
stated digest, byte for byte. Against a binary, a check naming another surface
must refuse with the digest and exact document the binary requires, and the
earlier profile identifier, the earlier form and its writer member must refuse.
Every refused profile is checked for the stated reason and surface data. With
a second build, the same profile file must be accepted by both writers, each
pinning the same surface, while the second writer still refuses to run the
first writer's audit. Runtime cases compare each synthetic launch's arguments,
environment, settings file, MCP configuration, working directory and MCP
initialization result with the surface, placeholders filled. Before executing
Python, the shell wrapper uses `/usr/bin/mktemp` and `/usr/bin/env -0` to retain a
unique, mode-0600 environment witness. Inspection checks its complete NUL framing,
unique names, digest and decoded contents. The launch event keeps this snapshot
as `environment`, with the later Python snapshot as `interpreted_environment`.
Contract checks use the earlier snapshot: interpreter startup can change locale
variables, so the later snapshot alone does not establish what was supplied.
An extra `LC_CTYPE`, including `C.UTF-8`, is still refused.

This observer starts after shell startup; it does not witness the raw environment
passed to `execve`. Its existing shell/platform exceptions are `PWD`, `OLDPWD`,
`SHLVL`, `_` and `__CF_USER_TEXT_ENCODING`. Both snapshots are retained, including
changes during shell exec and Python startup; those changes are observations,
not new exceptions to the launch contract. A recorded canary start fails the local-operation check. Archive
inventory checks detect changes or removals of earlier records around synchronous
manager commands. The owner-death, missing-stop and recorder-failure cases
separately witness the process or archive state they deliberately alter.
Runtime controls include successful auditor submission and verified delivery,
followed by an ordinary close that leaves the delivered package unchanged and
admits no further launch. An ordinary-ending case ends two turns without
submitting: it witnesses the single reminder as the second input, reports only
the later of two cumulative usage checkpoints, refuses another run, and closes
through a manager seal and a confirmed placement. Further controls cover
attempted authoring before startup followed by delayed valid and mismatched-model
startup controls, interrupted work followed by a fresh session, placement exhaustion,
deadline and owner-death stopping with a resistant descendant, and API credential
option rejection. A controlled missing-stop case retains the original process
metadata, substitutes an independently owned live group, and checks that restart
and close cannot silently treat it as stopped or signal that unrelated group.
Close may record the manager's `close_requested` before its stopping refusal;
the case requires earlier log bytes to remain unchanged and permits no
reconciliation, seal, delivery or completion record. A repeat adds nothing.
A recorder-failure case waits for independently witnessed startup, removes write
permission from the synthetic run directory, proves a directory write is refused,
and releases one witnessed authoring attempt. It requires actual group stopping,
no answer mutation and an explicit capture/write diagnostic. Permissions are
restored only after observed stopping; the permission witness stays outside the
archive. Running as root skips this case explicitly because root can bypass the
permission control.
Harness observations and attempted MCP calls are independently
witnessed outside the archive. Missing final checkpoints must remain unknown.

The submit-publication case uses the fault-enabled variant and fresh fault
directories. It pauses a confirmed submit immediately before its seal log link.
The positive control releases it unchanged. A cancellation followed by an
acknowledged ping must refuse that submit with `placement_stopped`, publish no
seal, allow re-entry and then permit a second submit in the same placement.
The signal control first observes the independently witnessed model group
present, then sends SIGTERM and waits for group absence while the owner remains
alive at the unreleased pause. Only that observed stopping permits release;
signal transmission alone is insufficient. Separate controls allow the
placement deadline to pass before releasing the pause. Release is recorded once,
including during cleanup, preserving the original marker and witness chronology.
These controls require the retained submit refusal, no seal and the
actual global ending: interrupted by signal or deadline, or `limit_reached`
on the last allowed placement. A specification-only MCP peer exercises the
fake harness's cancellation/re-entry/retry sequence in the self-test.

Five further runtime cases use the same synthetic executable:

- **Hooks and effort.** The harness runs the configured hook command as it
  would before a tool call. The helper must deny a pinned tool before startup
  has passed, admit pinned tools afterwards and deny four unpinned names, with
  the exact denial object of the launch surface. A question that selects an
  effort must reach the launch as the surface's effort arguments.
- **Cancellation and queuing.** A cancellation arriving after completion and
  one naming no request change nothing. A reused request identifier is answered
  and has no effect. Two uncancelled calls written together must both complete,
  with their replies and entries in arrival order. A separate pair puts a small
  call behind a large predecessor, followed in the same write by cancellation
  of the second call: the predecessor completes, and the cancelled call must
  receive `placement_stopped` with no entry. Independent traffic and effects
  are retained. This external observation does not identify the instant at which
  the second call entered the internal queue; the case reports that limit.
  Six further calls are each written together with their own cancellation.
  Either side may win such a race, so the case requires only that an entry
  exists exactly when its call received a completed reply, and reports as a
  note how many cancellations won. A run in which none won has not exercised a
  winning in-flight cancellation. The retained `mcp` stream equals the bytes
  sent, and received replies are a prefix of the retained `mcp-out`.
- **Relay loss.** The harness kills its relay and stays alive. Stewart must
  stop the placement well before its deadline, keep the recorded entry, and
  let a fresh session finish with nothing added. The harness also starts a
  second relay in the dead placement; the stop usually ends that attempt
  first, and a note says whether it finished.
- **Usage series.** One session reports a checkpoint and dies during its
  reminder turn; a second session reports a lower one and ends unsubmitted.
  The report is the sum of each session's latest checkpoint, one interval stays
  unknown, and the reminder is sent once for the audit.
- **Compaction.** Each of two compaction boundaries is followed by the pinned
  notice, re-entry still works, and the reminder remains available afterwards.
  The retained `stdout` and `input` streams equal what the harness wrote and read.

The self-test runs every synthetic scenario against a small specification-only
peer first, so a sequencing fault in the harness shows before a binary is used.
It also exercises the direct relay observer with a raw pipe, actual blocked-read
workers at setup/read/cleanup checkpoints, a resistant descendant after its
worker exits, subsequent normal operation, and the refusal to launch further
selected cases after unresolved stopping. The self-test prints the retained
directory containing these partial witnesses and watchdog results.
Environment controls exercise the actual wrapper and inspection path with the
specified environment, an injected `LC_CTYPE=C.UTF-8`, a changed `LANG`, an extra
variable and a repeated normal launch. They retain raw and interpreted snapshots
and report their differences without requiring a platform to change its locale.

The offline service controller can also supply an immutable scenario with mode
`continued-deadline` or `continued-limit`. Each requires `continued_accounts`,
three distinct nonblank strings of at most 200 UTF-8 bytes, and the existing
base `session` identifier. `continued-deadline` additionally requires
`utf8_artifact: {label, text}`. Use three reviewed placements with the same
scenario bytes; neither mode starts another placement itself.

Only model invocations claim `model-start-0001.json` through
`model-start-0003.json`, using exclusive creation. Authentication invocations do
not consume an ordinal. Each claim binds the scenario digest, PID, process group
and fresh session ID `<session>-placement-000N`. A fourth model invocation refuses
before reading input or starting its MCP peer. `model-session-000N.jsonl` retains
that session's events separately; the shared `harness.jsonl` remains available.

Before adding work, every placement checks its re-entry revision, current
selection and prior receipts. Later placements read each earlier account through
its current handle and compare the exact bytes with the supplied strings. They
also witness the initial question and pinned continuation notice. Starts one,
two and three each add their distinct account, yielding `e1`, `e2`, `e3`, all
version one, at revisions one, two and three. The first two then remain alive
for Stewart's actual deadline. On the third start, `continued-deadline` adds the
UTF-8 artifact as `e4` at revision four and submits that cumulative selection.
`continued-limit` remains alive after the third account, so the final deadline
must end authoring with `limit_reached` and no seal.

Only the first placement emits a valid main-loop result: two harness turns,
11 input tokens, 120 cache-creation input tokens, 300 cache-read input tokens and
40 output tokens. It consumes the single pinned reminder, then emits an
assistant snapshot. All three placements emit two overlapping assistant snapshots
with the same message ID: output tokens zero, then that placement's
`CONTINUED_ASSISTANT_USAGE` count, with unchanged input counts. These partial observations must not be added to the
main-loop result. Subsequent placements emit no result, avoiding an ordinary
ending after the audit-wide reminder has been used. After each stop, the expected
reported-placement count remains one and the unknown-interval count is one,
two, then three. The provider completeness remains unverified. A six-second
placement timeout exercises the deadline; native evidence must establish the
actual ending and group absence before another start.

The self-test preserves three-start fake-peer sequences, unchanged scenario and
prior-session witnesses, and controls for missing/malformed re-entry, changed
prior account bytes and a fourth model invocation. Its own controller terminates
the waiting fake processes; that sequencing test does not establish Stewart's
deadline enforcement. Its retained evidence path is printed with the self-test.

Not exercised: the internal waiting state or queue count/byte overflow;
`run`'s own re-verification of a pinned surface, which has no
black-box firing control because one binary cannot hold an arrangement that
pins a different surface; a hook call after the placement has stopped admitting
calls; and the near-limit notice. The contract's
[demonstrated scope](../../docs/claude-code/CONTRACT.md) distinguishes this
synthetic runtime evidence from other checks and remaining qualification work.

`RESULT.json` reports per-case outcomes, check counts, explicit skipped cases,
firing controls, timings and notes. A note records an observation that decides
no outcome, such as which side won a race. `commands/` retains exact argv, stdout and stderr;
`witness/` retains independent question, material, profile and tool inputs outside
the archive. `driver-snapshot/` preserves the executable synthetic harness and
its specification-derived helpers used by that run. Keep the work directory
through review, then apply the repository's
[evidence retention rules](../../development/DEVELOPMENT.md#evidence-and-retention).
Native results are development evidence only. The container suite runs this
driver on both supported Linux architectures, with distinct release-profile
and debug-profile development writers and a featureless release binary. It
requires every case and control, exports `RESULT.json`, `environment.json`,
`commands/`, `witness/` and `driver-snapshot/` to `runtime-evidence/`, and retains
the original container through review. It also exports the whole work tree to
`runtime-work.tar` on every run: launch markers beside fixture executables are
independent witnesses outside `witness/`. The qualification extractor
checks actual counts, full source case inventory, source/binary identities,
the exported evidence listing and the complete work archive's digest. The standalone report makes no qualification
claim itself; the enclosing Linux suite qualifies only the adapter and process
controls it exercises, never real-harness behavior or provider consumption.
