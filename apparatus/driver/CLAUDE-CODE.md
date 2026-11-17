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
repository descendants, and a work directory with an entry named `.git`,
`CLAUDE.md`, `AGENTS.md` or `.claude` in any ancestor, before creating its work
directory or any fixtures: `run` refuses a launch directory with such ancestry.
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
Every transformed tool carries the runtime contract's fixed result-size
annotation. Binding controls refuse a profile checked against the otherwise
identical unannotated inventory, and the restored inventory prepares normally.
This checks Stewart's supplied bytes and profile binding; the synthetic harness
does not establish that a real harness honors the annotation or avoids external
copies.

`runtime-captured-authoring` exercises the [C4/C5 captured authoring
forms](testdata/README.md#c4c5-authoring-and-error-forms): required-field recovery,
full flattened refusal, exact-version long replacement, stale-target refusal,
prepared/delivered answer equality and submit-to-stop. Array-form invariance
keeps the same answer; a changed error flag interrupts with the prior version
preserved. All supplied material and historical payload bytes have external
witnesses. Its combined schedule is synthetic and makes no live near-limit claim.

The reply-fidelity cases use the short control and two full pages from the native
C3 encounter (2026-11-13, CLI 2.1.322, `claude-haiku-5-5`), repeated unchanged in
the annotated-page encounter (2026-11-15, the same CLI/model). The generator pins
the exact source bytes, including each tail label:

| Source slice | Bytes | SHA-256 |
| --- | ---: | --- |
| `control.txt`, start 0 | 49,152 | `947ae167c6e71f036d5c603c3f273706c2252b1b18d381bbf7da3045da49e0d2` |
| `two-pages.txt`, start 0 | 65,536 | `e68bd1dcda95edf47c668475d810f587ad80c382afe00cc8bfa8f36ae969ca2a` |
| `two-pages.txt`, start 65536 | 65,536 | `7f451bbeacea11971c367fd63b96f513ddbdeea38edf74bd68e7c8fbfec12a92` |

Original sources and MCP/assistant/hook/conversation captures are retained in the
[C3 and annotated-page evidence](../qualified.md#readiness-c3-01). The two C3
conversation substitution strings have original decoded UTF-8 digests
`40567555b890b8d1ac20737aa03b0c479fad1a088834e45bec027ca78be9642c` and
`c3bf6e1d68e7a60e891adca34be624d411dcad44daa231a4752e4d8ca8cc6f75`.
The fixture replaces only each absolute external filename with
`/synthetic/external/tool-result.json`; the notice and truncated preview stay
unchanged. No fixture opens or creates that named file. The runnable driver has
no dependency on the retained run directories.

`runtime-reply-fidelity` sends each actual Stewart reply through correlated
assistant, admitted hook, MCP metadata and conversation records. It checks the
material bytes independently of the echo. Positive and object-order/omitted-false
invariance cases seal normally. Differing cases change one conversation property:
the C3 notice, one removed text byte, an error flag or success-text flattening.
Their auxiliary arrays remain exact. A range/quote refusal reproduces the short
error shape; exact error-text flattening is accepted, while the wrong flag stops.
Absent and duplicate echoes remain unknown without preventing submission.
Mismatch cases preserve the first account, stop both groups, retain a diagnostic
whose byte references resolve, and interrupt without a seal. Explicit continuation
submits that unchanged account; exhausted starts offer no direct run.

`runtime-fidelity-publication` withholds a page echo until the documented seal
publication pause. The mismatch must stop the model group while the owner is
still paused, then refuse the pending seal with `placement_stopped`. An exact
held echo permits sealing. Separate TERM-triggered echoes exercise shutdown drain:
the winning seal and its delivered package survive a late mismatch, with warnings
through close and repeated close. Their independent raw witness sits outside the
archive. The existing owner-death case also requires a missing final fidelity
record to remain explicitly unknown. These comparisons exercise observable
conversation records, not hidden provider traffic or real-harness prevention.

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
The positive control releases it unchanged, then closes the delivered audit
without changing its auditor attribution or package. A close-winning control
publishes the close request while submit is paused, observes the live model
group stop before releasing submit, and requires the retained refusal
`authoring_ended`, with the exact close timestamp and absent seal observation.
The placement must end `stopped_by_close`; only close may then seal, with
manager attribution, preserving the submitted account bytes. That close has
its own seal pause in a separate fault directory. With the placement ended and
the active lock still held, both status and a second close must report
`close_in_progress`; the second close has a 40-second caller bound around the
documented 30-second lock wait. Releasing the manager's seal permits delivery,
which still needs explicit confirmation. The witness records each release and
the close/stop/seal log order. A cancellation followed by an
acknowledged ping must refuse that submit with `placement_stopped`, publish no
seal, allow re-entry and then permit a second submit in the same placement.
The signal control first observes the independently witnessed model group
present, then sends SIGTERM and waits for group absence while the owner remains
alive at the unreleased pause. Only that observed stopping permits release;
signal transmission alone is insufficient. Separate controls allow the
placement deadline to pass before releasing the pause. Release is recorded once,
including during cleanup, preserving the original marker and witness chronology.
The signal and deadline controls require the retained submit refusal, no seal
and the actual global ending: interrupted by signal or deadline, or `limit_reached`
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
directory containing these partial witnesses and watchdog results. It checks the
pipe packing rule for both platforms with controls (merging, page-sized and large
writes, packet mode, other geometries), then compares it with fresh unread pipes
on the host and prints the host's packing facts. On Linux that comparison is the
direct kernel witness for the notice cases' page packing.
Environment controls exercise the actual wrapper and inspection path with the
specified environment, an injected `LC_CTYPE=C.UTF-8`, a changed `LANG`, an extra
variable and a repeated normal launch. They retain raw and interpreted snapshots
and report their differences without requiring a platform to change its locale.
The decoder and group-observer selfchecks also use [captured local OS
observations](testdata/os/README.md), keeping denied observations unknown and
distinguishing captured results from synthetic retry schedules.

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

The `runtime-near-limit` case holds the same partial account and observes input
for 16 seconds with a 20-second and a 200-second placement deadline. The short
case must receive one exact near-limit message; the long case none. Both
explicitly submit after the window. A third audit interrupts upon receipt of
the notice, leaving time for stopping, then continues through a full short
window: its prior account and
spent notice allowance must survive, without a second notice or duplicate
entry. Re-entry must still show an unsealed answer and unused reminder before
submission. Each peer's exact input bytes are compared with the archive; notice
text, remaining starts and time units are checked against the logged claim and
run reply. All resulting packages preserve the supplied account through close.
The case checks time values against the configured bound; it does not measure
subsecond rounding or the exact threshold crossing.

This notice fixture is grounded in C4's short placement on 2026-11-14, using
Claude Code 2.1.322 and `claude-haiku-5-5`. Its retained input is
`.scratch/readiness-c4-01/short/packet/closure/service-archive/audits/ah3m7bxzpowsvmtfn/runs/1/runtime-316-input.bin`:
283 bytes, SHA-256 `1e6192fe759bc3a8bd0a20708601f7afcad94dddda72290a4ab271adc95c1adf`.
The corresponding `log/20.json` is 569 bytes, SHA-256
`31c4884f8012889f53657eba16c58403ddfe8debc1682288f4d1038e55fb1443`.
The self-test reconstructs the original 12-second/two-start input byte for byte;
runtime variants change the deadline and, for continuation, exit upon receipt
of the notice. They use synthetic inputs and a fixed partial account,
and do not replay the live audit or depend on its retained directory. The
original input was a service-owned capture, not a provider-network witness.

The timing case uses the [captured C4 partial account](testdata/README.md#c4-partial-account-in-the-timing-comparison)
as its one authored entry. Its complete arguments, retained payload and exact
expected answer must agree across the timing/continuation paths. Only the
synthetic schedule changes; the original multi-entry audit is not replayed.

The `runtime-captured-accounting` case projects the repeated usage fields from
four C5 assistant frames and replays C5's complete synthetic cap-message shape.
The usage projection preserves every usage member and the repeated message-ID
and null-stop semantics. Content, model and envelope identities are synthetic;
the cap frame changes only its session ID. Missing final results must leave
totals unknown, and repeating the four-frame projection twice must change no
reported consumption. A separate control supplies one known cumulative result,
receives the still-unused ordinary reminder, then supplies another partial
assistant frame: the checkpoint counts survive while the later interval remains
unknown. Retained usage records must not promote partial fields to reported
totals, and the last record must agree with the final usage object. Their file
count is not a model-report count: records also preserve stopping observations.
All variants author and submit the same supplied account after the cap,
then close without changing its package. The cap text is harness output, never
Stewart's input or an English-text instruction to its accounting logic.

The originals are from 2026-11-15, Claude Code 2.1.322 and `claude-haiku-5-5`,
under `.scratch/readiness-c5-01/checklist/archive/audits/aplifuihi4h2xrht5/runs/1/`.
Concatenating stdout chunks in numeric order gives 611,370 bytes with SHA-256
`0e4f7791fa55bc78eb8dbb124262b478c966bdd65f4e20b6be45907ff682736a`.
The selected LF-terminated assistant frames have these offsets and digests:

| Offset | Bytes | SHA-256 |
| --- | --- | --- |
| 2764 | 1829 | `1b2733a90a651f98d40ddeb5438296e4ddb44d6f33a82a23c7c1b6f314a551c0` |
| 4593 | 1069 | `65f850391a86406d9b3eb9e39a1d202542720e20b45088dd1c54f1d9e746031a` |
| 5662 | 1015 | `2652549cb33d88fd81121beb344d72e4fb5f76f01fbc0c87a0df46c0d51878f1` |
| 15533 | 1034 | `8e19536e52030fd5254c378111c2cfcb717db484fa81b4d9143a084d6a25eb1d` |

Their identical compact usage objects are 251 bytes, SHA-256
`db6136588bc9b971abaf7a1a6da35f877e3a05253ddad40d54e5b0ec018272c9`.
The cap is the complete 447-byte `runtime-339-stdout.bin`, at combined offset
497621, SHA-256 `7a5ec002a7e8dc060c463d2d7ec9394130cd708c8b36c9074dea6b407e262a78`.
The self-test pins these reconstructed cap and usage bytes. The valid cumulative
checkpoint control is synthetic: this live encounter contained no result frame.
These fixtures establish neither the exact output-token cap nor provider billing.

The `runtime-tool-names` case changes only the name in a synthetic assistant
tool-use frame: a pinned prefixed name, its unprefixed stem, or an unlisted
prefixed name. The positive control sends an ordinary bare-name MCP call and
submits its account. The two negative peers remain alive until Stewart stops
them; they must end with a protocol anomaly, no answer entry or seal, and
observed absent groups. Those stopped, unsubmitted controls remain for review.
The negative names are synthetic; C2–C5 supplied no such assistant frame.

C2–C5 supplied no final result checkpoints or compaction boundaries. The
checkpoint and `system/compact_boundary` comparisons remain synthetic; no other
compaction form is grounded in those encounters. C5's cap message was followed
by authoring, not a terminal cap result. These fixtures make no claim about
unobserved terminal-cap forms or actual harness cap enforcement.

Scripted sequences use the synthetic harness's `scripted` mode. The outer driver
writes the scenario's `script`: an ordered list of tool calls, each with a label,
arguments and optionally a fixed request ID. An argument
`{"$ref": [label, key, ...], "$append": text}` takes a value from the core reply
of an earlier labelled step, such as a prepared handle or a page's `cite`. A
step marked `follow` keeps calling the same tool with each reply's `next` input
until the page reports completion. The harness records every request, MCP reply
and decoded core reply as a `script-step` event. A `final` confirmed submit is
sent without awaiting its reply, so only Stewart's stop ends the session;
otherwise `script_end: "exit"` exits like an interrupted harness. The harness
draws no conclusions; every expectation is in the outer case.

- **Family sequences.** `runtime-family-sequences` runs the release driver's
  `c7.families` operations over MCP for each family, with its materials and
  citation operands. Each audit checks:
  - empty preparation: `answer_empty`, zero counts in tools order and the
    empty views;
  - an inability account, plus the comparison observation or framing working
    question, then `section_unfilled` notices in tools order; the comparison
    observation fills no section;
  - for open inquiry, recorded and refused citations, with ambiguous quotes
    listing their ready citations;
  - an equal-label pair (`label_duplicate` on the second), its exact delete and
    the repeated delete;
  - the final selection and rendering views;
  - the core's `tools/list` result against the pinned MCP mapping, members in
    order.

  The delivered manifest, answer, rendering and artifacts are compared with
  independently built bytes. Each family also seals an empty answer. An audit
  with no materials lists nothing and records only an artifact: every section
  stays unfilled and `answer_empty` is not reported.
- **Reads and search.** `runtime-read-search` checks:
  - pages of a 3-byte-character file without a final LF;
  - start refusals naming the nearest boundaries, and the empty page at the
    end;
  - literal overlapping search hits in pages of at most 128, with `sc.` cursors
    and completion, under default and explicit scope;
  - absence only when complete, and the search text bound;
  - the question read whole, and `list`.
- **Request identity.** `runtime-identity-across-placements` reuses one request
  ID in a fresh placement, which must record a new entry. Reused again inside
  that placement, the ID must be answered with no effect, and a fresh ID with the
  same arguments records another entry.
- **Drain unknowns.** `runtime-fidelity-drain-unknown` makes the TERM-time echo
  missing or duplicated. The fidelity record must stay unknown with no mismatch
  or diagnostic, while the seal, delivery and close are unchanged.
- **Late close.** With the fault-enabled variant, `runtime-sealed-late-close`
  pauses the run's delivery after an auditor seal and requests close. The seal
  must keep its actor, the run must deliver attempt 1 after `close_requested`,
  close must await confirmation for that copy, and confirmation closes it
  unchanged.

Sequences use the synthetic harness's `sequence` mode. The outer driver writes
the scenario's `steps`, an ordered list of harness events: record an account,
emit a `result` with a chosen `is_error`, `subtype` and checkpoint, await an input
of a named kind (reminder, near-limit, continuation or compaction notice), expose
compaction boundaries, send a tool call without awaiting its reply, emit an
assistant tool use with a chosen name, resist TERM (each received TERM is written
to a separate witness, so shutdown must escalate), stop reading input, wait for a
driver-written file or a wall-clock instant, expose as many compaction boundaries
as their notices fit in the unread input pipe (optionally more), publish a marker,
then submit, exit or hang. Stopping reading records any other process holding the
input pipe's read side. Wall-clock instants are used because monotonic clocks are
not shared between processes on every host. The harness draws no conclusions.

- **Start reservation.** With the fault-enabled variant, `runtime-start-races-close`
  holds `run` immediately before linking `run_started` and holds close after its
  `close_requested`. Released, `run` must refuse `reference_closed` with exactly
  `close` and `status` next, launch nothing, create no run directory and use no
  placement start; close then completes before launch. The same reply follows
  when close was requested before `run` began; the same hold without close starts
  and seals.
- **First condition.** `runtime-first-condition` lets the harness end its second
  turn after the reminder while resisting TERM. SIGTERM sent once shutdown has
  begun, before `run_ended`, must leave `ended_unsubmitted` and authoring ended;
  SIGTERM while the placement is live is `interrupted` with cause `signal`. An
  unprefixed tool name emitted one second before the earliest possible deadline,
  with shutdown outlasting the deadline (witnessed by `runtime-stop.json`), must
  stay `protocol_anomaly`, also on the final placement; with no earlier condition
  the deadline decides. `runtime-late-close` (variant) makes the late condition a
  close held after its request: the run still records `ended_unsubmitted`, the log
  orders `close_requested` before `run_ended`, the headline's first ending is
  `close`, and close seals as manager. A close requested while the placement is
  live stops it.
- **Final placement.** `runtime-final-interruption` interrupts the only permitted
  placement by a harness exit and by an unprefixed tool name. Status keeps the
  ending, cause and condition, offers only `close` and states no remaining start;
  both headlines show authoring ended by `limit`; `run` refuses `authoring_ended`
  with that `run_ended` as `data.record` and `close` and `status` next, launching
  nothing. With a start remaining, authoring stays open and a continuation seals.
  When the only placement's owner dies, `run` must record its `run_ended`
  (`interrupted`, `process_gone`) and then refuse `authoring_ended` naming that
  record, launching nothing; with a start remaining it reconciles and seals.
- **Unknown stopping.** `runtime-unknown-stop-advice` repeats the controlled
  unresolved group of `runtime-unknown-stop`. Status and the refused `run` must
  offer only `status`, and the summary names placement 1; once the group is gone,
  status offers `run` and `close` and a continuation seals.
- **Launch directory.** `runtime-launch-directory` plants `.git` (directory and
  file), `CLAUDE.md`, `AGENTS.md` or `.claude` in the profile's temporary directory
  or an ancestor after acceptance. `run` must refuse `runtime_profile_invalid`
  without `run_started`, a run directory, a harness start or a used placement;
  removing the entry lets the same audit seal. Near-miss names start normally. A
  temporary directory that is the archive, the submission folder or the
  directory of a byte-identical writer copy, or lies within the archive or the
  submission folder, refuses the same way.
- **Notices.** `runtime-notice-transmission` sends the reminder, a compaction
  boundary, the near-limit notice and another boundary, each awaited before the
  next harness event: both notices are `sent`, numbered 1 and 2 in log order, the
  near-limit notice's remaining seconds are at most a fifth of the timeout and
  its starts are the unused ones. The opposite order, followed by owner death,
  must leave both claims `unknown` after recovery. A final placement with a long
  timeout gets no notice. A harness that stops reading exposes as many
  boundaries as their notices fit in its input pipe, then ends its turn, so the
  reminder's frame cannot fit: captured, it is `unknown`; never captured,
  `not_sent`, and the arm reports that the incomplete write was not reached.
  Fit follows the platform's packing, not raw bytes. A macOS pipe holds 65,536
  bytes. A Linux pipe holds `F_GETPIPE_SZ` / page size page buffers, and a small
  write merges into the last one only when it fits there whole (`fs/pipe.c`), so
  the 255-byte notice fits 256 times in sixteen 4 KiB pages, not 257. The harness
  probes fresh unread pipes of the same capacity, and they must accept exactly
  what that rule predicts. The capture, packed by the same rule, must show that
  the unread input before the reminder left it no room. The harness then hangs, so
  the reminder's write fails only when the supervisor stops the group at the
  deadline, and the deadline must decide the ending, as in the blocked-write case.
  This assumes that no other holder of the input pipe's read side reads it; the
  harness records such holders.
  `runtime-notice-not-sent` (variant) fails the reminder claim's directory sync:
  the placement ends `archive_write_failed`, the reminder frame is not captured
  and the claim is `not_sent`.
- **Blocked write.** `runtime-blocked-write` exposes one boundary more than fit,
  so Stewart's write of the last notice cannot complete while the harness hangs.
  The supervisor's deadline stop makes that write fail after the deadline, which
  must decide the ending: `interrupted` with `placement_deadline` and authoring
  open when starts remain, `limit_reached` with authoring ended by `limit` on the
  only placement. `runtime-stop.json` must show stopping observed after the
  deadline. Differing: the harness exits once the driver has seen the blocked
  notice captured, long before a 30-second deadline. Stopping observed before the
  deadline must leave `interrupted` with `protocol_anomaly`. No result is
  emitted, so the reminder is never due; a near-limit notice could only queue
  behind the blocked write and must not be `sent`.
- **Results.** `runtime-result-rules`: a `result` with `is_error` true and subtype
  `success` interrupts with `protocol_anomaly` and claims no reminder; its usage
  is the latest reported checkpoint but its interval stays unknown. `is_error`
  false with subtype `error_max_turns` receives the reminder and its usage is the
  checkpoint; an ordinary ending whose last result has `is_error` false leaves no
  interval unknown. `runtime-result-during-call` (variant)
  holds a record call before its entry link and emits an ordinary result: the
  model group must stop while the call is held, the call is refused
  `placement_stopped`, and the placement ends `protocol_anomaly` without a
  reminder.
- **Drain ending.** `runtime-fidelity-drain-ending` holds a page echo until
  Stewart's shutdown TERM. After an ordinary ending, a substituted echo must turn
  `ended_unsubmitted` into `interrupted`/`protocol_anomaly` with a `drain`
  diagnostic and authoring open; an exact echo leaves `ended_unsubmitted`. After
  the driver's SIGTERM decided the ending, the same substitution keeps
  `interrupted`/`signal`.
- **Request reuse.** `runtime-identity-across-placements` also requires JSON-RPC
  error `-32600` with the reused ID, for an identical repeated call and for a
  `ping`, contiguous call numbers and one call file per ID.

Preparation acceptance reads back every selected material, not only the default
report, against the driver's own bytes.

Not exercised: the internal waiting state or queue count/byte overflow;
`run`'s own re-verification of a pinned surface, which has no
black-box firing control because one binary cannot hold an arrangement that
pins a different surface; a hook call after the placement has stopped admitting
calls. The contract's
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
