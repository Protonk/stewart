# Claude Code runtime conformance

The gated adapter is implemented and aligned with the Messages path at the
manager's surface, including ordered tool-call queuing. Native offline checks
and Linux container acceptance against a synthetic harness pass. No real-Claude
service run exists. No Claude launch or resume is authorized: both earlier probe commissions are closed,
and the real-service run below needs its own commission.

## Decided scope

The [development runtime contract](CONTRACT.md) owns the selected
observation, placement-limit, startup and credential boundaries. The
[runtime reference](RUNTIME-REFERENCE.md) owns technical evidence
and remaining limits. Packaged releases exclude the adapter; the published
source keeps it behind the default-off feature. Its purpose is to be the main
means of exercising the manager's interface, so keep it in line with the
Messages path wherever the transport allows. Linux is in scope: a source
builder there is an intended user.

Preserve the [question-family meanings](../../CONTRACTS.md#question-families-and-open-inquiry),
common custody/attribution contract and
[evidence and judgment boundary](../../CONTRACTS.md#principles-and-scope). Family choice
never grants execution. Runtime telemetry does not establish the auditor's
understanding or intellectual completeness. Human and other runtime adapters
remain future work.

## Next steps, in order

Take these in order. Each step that changes the contract or the service is
written by one author, and its driver cases by another who has not read the
implementation.

1. **Build the real-service check and propose its commission.** Two pieces of
   apparatus remain: a real-harness controller and review workflow, and
   a full-service comparison with independent witnesses. The installation and
   profile producer, invocation library and independent offline helper fixture
   and observer are implemented and verified natively. No reviewed real-harness attestation exists, and the
   two-tool probe is not a full-service check. Write a concrete bounded commission: exact
   synthetic materials, model, session allowance, stopping conditions,
   executable and surface pins, the subscription route with paid extra usage
   disabled, and the witnesses retained. Rehearse it offline against the
   synthetic harness. Bring it to the principal; preparing it authorizes
   nothing.
2. **Run the real-service check under that commission.** Exercise the actual
   tool surface, compaction and re-entry, accounting, interruption,
   submission, delivery and close. Verify effective tools, instructions,
   authentication and access before and after compaction, including host and
   server-managed configuration; settings alone do not establish enforcement.
   The commission names these as explicit observations, each currently unknown
   for the real harness:
   - what usage a submitting placement reports. The runtime stops the harness
     after a confirmed submission; in synthetic runs that leaves the final
     interval unknown on every sealed audit, while a turn that ends with a
     result is reported;
   - how the harness issues several tool calls of one model response;
   - where a post-compaction notice is delivered, and whether startup can be
     validated before the first question reaches the provider;
   - whether the turn cap and per-response output request are enforced.

### Preparing the first profile check

The initial check observes the complete supplied launch surface with the actual
Stewart relay and hook helpers connected to an independent fixture's private
sockets. The fixture advertises the selected family's exact MCP tool inventory;
its effects remain explicitly fixture effects. This can establish harness
compatibility with the supplied surface, not service custody or publication.
After independent review, the profile producer can embed that check's bindings
and exact review digest. The actual-service comparison then uses the reviewed
profile. No placeholder or unperformed check is recorded as `observed`.

The installation producer verifies retained public signing evidence and the
native executable without executing Claude or reading credential storage. The
first fixture deliverable is offline only: it exercises actual helpers and
retains raw witnesses but leaves authentication/startup observations unexercised.
Its synthetic rehearsal cannot produce an eligible profile attestation.

Remaining implementation before proposing a live commission: integrate the
bounded invocation library and independent observer into a live controller,
complete the review workflow and add the actual-service comparison. The latter's independent
witnesses include original synthetic inputs, manager commands/readback, external
delivery inventories and process observations. Service-owned raw captures retain
that provenance; they are not independent peer witnesses or complete provider
transcripts. The [apparatus guide](../../apparatus/claude-code/README.md) owns the
artifact interfaces as they are implemented.

The combined host verification at `.tmp/bounded-observer/host.CD7Wrh` passed all
twelve commands, with unchanged source snapshots, no timeouts and all outer
command groups observed absent. Pin checks passed 3 tests, profile checks 16,
invocation checks 22, probe checks 24, protocol checks 14 Python tests and 9 Rust
tests, the surface fixture self-test 51 checks and the observer self-test 37
checks, with no failures or skips. The listener rehearsal at
`.scratch/claude-code-observer-rehearsal-01` passed all five controls. Review
verified all 209 evidence members, exact source/input bindings, three distinct
sessions/workspaces and both firing negative controls without effects.
Authentication and process results in the listener rehearsal are explicitly
synthetic; the separate invocation controls exercised actual Python process
stopping. The producer refused the synthetic observation, and no `CHECK.json`
or eligible profile was emitted. Reviews are retained at
`.tmp/bounded-observer/host-02-review.log` and
`.tmp/bounded-observer/listener-review-final.log`.

The earlier listener rehearsal at
`/private/tmp/stewart-observer-listeners-native-01` failed all five controls at
socket binding with `EPERM`, before any peer connection. No subprocess or Claude
was launched by that rehearsal. Preserve it and
`.tmp/runtime-queue/observer-listeners-native-01.log` through host review.

The first combined host check at `.tmp/bounded-observer/host.Qt0uwr` completed
ten commands: nine passed and the bounded tests errored. Those tests ran 21
cases: twenty passed, and owner-loss observation raised `PermissionError`
(`EPERM`) from `killpg(group, 0)`; its cleanup then raised the same error from
`killpg(group, SIGKILL)`. The remaining apparatus checks passed with no skips,
source snapshots matched and all outer command groups were observed absent.
The listener rehearsal and its evidence review were not run. Later read-only
inspection observed the recorded group absent; no historical group was signalled.
The supplementary `ps` inspection was denied by the agent sandbox. Original
outputs remain unchanged, with review at `.tmp/bounded-observer/host-01-review.log`.

The owner-loss test now retains bounded status probes, keeps `EPERM` unknown,
requires explicit absence to pass and records cleanup failures without masking
the primary result. It sends no cleanup signal after observed absence. A fresh
run reproduced one `EPERM` followed by absence about 24 milliseconds later.
The transition, persistent-denial, present and absence/invariance controls pass;
persistent denial cannot count as stopping. All 22 bounded tests passed with no
skips in `.tmp/bounded-observer/bounded-tests-owner-loss-fix.log`; exact group
observations and controls were reviewed in
`.tmp/bounded-observer/owner-loss-fix-review.log`. The invocation library and
independent observer are unchanged by this test correction. The reason for the
operating system's transient denial remains unestablished.

This completes native verification of the invocation library and independent
observer. There is no integrated live controller, eligible check or new spending
authority yet. Preserve the failed originals through review of this comparison.

The host verification at `.tmp/profile-bootstrap/host.Wxzodq` passed all eleven
commands with unchanged source snapshots and all owned process groups observed
absent. Pin checks passed 3 tests, profile checks 16, probe checks 24, protocol
checks 14 Python tests and 9 Rust tests, and the surface fixture self-test 51
checks, with no failures or skips. Review verified all fourteen public
installation-evidence members at `.scratch/claude-code-service-installation-01`.
The native helper rehearsal at `.scratch/claude-code-surface-rehearsal-01`
passed all seven comparisons, with 92 evidence members verified. Its observation
records eight observed comparisons and two intentionally unexercised comparisons:
authentication and real-harness startup. It cannot produce an eligible profile.
No Claude or authentication invocation occurred. The review output is
`.tmp/profile-bootstrap/host-review.log`.

The initial filename collision on case-insensitive macOS was corrected; its
failed output remains at `.tmp/toolchain-refresh/profile-tests.log`.
The earlier actual-helper sandbox rehearsal at
`/private/tmp/stewart-surface-rehearsal-native-02` retains seven socket-bind
`EPERM` failures before helper launch; all seven worker groups stopped with no
timeouts. Its observation has three observed, five failed and two unexercised
comparisons. The authentication and startup comparisons intentionally remain
unexercised in every synthetic rehearsal.

Use firing controls, differing cases and invariance cases under
[ACCEPTANCE](../../ACCEPTANCE.md#the-real-model-conformance-tier). Bind results to the
actual CLI, effective configuration, model, authentication route and binaries.
Model answer quality is not the gate. API results do not qualify the harness
profile, and native results do not qualify Linux.

## Desirable work

None of this blocks the steps above. Do it when it fits.

- Share driver cases for behavior common to both runtimes where independence
  allows. The two drivers now cover custody, submission, delivery and close
  separately, so a common behavior is specified once and checked twice by
  different code.
- Write the offline cases still missing: refusal of a second relay connection
  in a live placement (the stop after relay loss now ends the attempt first), a
  hook call after the placement has stopped admitting calls, and the
  near-limit notice. `run`'s re-verification of a pinned surface has unit
  coverage only, because one binary cannot hold an arrangement that pins
  another surface.

## Housekeeping

- Register the two native probes in the qualification index. Their result and
  state files carry no UTC run timestamp the indexer accepts. Resolve how to
  register that known gap; do not manufacture a timestamp or rewrite their
  receipts to fit. Until then their paths and retention purpose stay listed
  below.
- Once the principal has reviewed the evidence listed below, apply the
  [retention rules](../../development/DEVELOPMENT.md#evidence-and-retention):
  keep the current results and selected originals, and release the reproducible
  working trees and superseded runs.

## Evidence through review

The current Linux acceptance run `.scratch/acceptance-environment-observer-01`,
at `b4ccba4`, is qualified in the
[qualification index](../../apparatus/qualified.md). Each architecture passed
all 24 runtime cases, 9,892 checks and 73 controls, with no failures, skips or
unselected cases. The runtime self-test passed 205 checks. Release suites passed
128 cases on native arm64 and 126 on emulated amd64, with all 79 sabotage and
21 driver controls fired, and no failures outside the controls or skips. All
build/static/marker comparisons passed. Review verified binary/source digests,
40 independent environment witnesses per architecture and regular-file-only
evidence exports. This qualifies the recorded Linux synthetic behavior; it
does not establish real-harness conformance or native WSL2 qualification.

The earlier failed Linux run `.scratch/acceptance-runtime-queue-01` remains
retained through diagnosis. The release suites
passed all cases and required controls, and all build/static/marker comparisons
passed. The runtime suites each passed 10 cases and failed 13, with no skips.
Retain both driver containers and the exported runtime work archives through
diagnosis; the original evidence is unchanged.

In the positive case on each architecture, the independent harness witnessed
authentication, model launch, the supplied question, emitted startup and the
transmitted MCP initialization request. Stewart retained the complete
initialization reply, but the independent peer witnessed no reply. The
deadline case still observed group stopping. These observations locate the
failure boundary without establishing its cause.

The relay comparison in `.scratch/relay-diagnostic-01` was interrupted by the
host runner after 3,600 seconds. Only arm64 container-start output reached the
host; no case results or completion record were exported. The probe had
unbounded process-start and process-observation operations, and its host
wrapper had no container-command watchdog. Recovery evidence in
`.scratch/relay-inspection-01` confirms that diagnostic container was running
and is now stopped. At inspection, the probe's Python process was in disk
sleep and its relay child was alive with two threads. The partial export holds
only the environment and first case's supplied bytes, without observed bytes
or phase results. Neither the exact blocked operation nor the cause of the
original Linux initialization failure is established. Preserve both attempts
through diagnosis; do not restart the old probe.

The second comparison, `.scratch/relay-diagnostic-02`, completed with nine
observations: metadata and both empty-EOF cases passed; all six nonempty-reply
cases hit their nine-second worker deadline. Every case's socketpair reader
control and exact request forwarding succeeded. The nonempty cases retained
the reply write but stopped within stdout observation, without a read result.
The segmented cases sent only their first reply fragment, and the half-close
cases never reached shutdown. Neither is evidence about a complete segmented
reply or nonempty EOF. Optimized and debug behaved alike, and removing `/proc`
observation did not remove the failure. All worker groups and the diagnostic
container were observed stopped; the export is intact.

The paired comparison in `.scratch/relay-diagnostic-03` completed ten
observations with two failures. The retained Stewart and a standalone
standard-library-copy relay stalled in `os.read` after `select` on a
nonblocking stdout pipe when the reply socket stayed open. An otherwise
identical standalone relay using explicit read/write/flush delivered the exact
141-byte reply before EOF. All three candidates passed immediate half-close
and empty EOF; pipe and socketpair reader controls passed in every case.
The toolchain image matched the retained build image. Both containers and all
worker groups were observed stopped. This distinguishes the copy paths without
establishing the underlying kernel or library defect, or qualifying the full
service fix.

The service now uses the tested explicit reply-copy loop. A unit check covers
visibility before the next read, interrupted reads, short writes and raw bytes
without LF. An independent driver regression covers the actual helper with an
owner watchdog outside its pipe reads. Host verification in
`.tmp/relay-fix/host.KTpsns/`, with runtime witnesses at
`/private/tmp/stewart-relay-runtime.wx0dO3/run`, passed all three Cargo
configurations, builds, formatting and links with no skipped checks. The
runtime suite passed 24 cases, 9,766 checks and all 73 controls; its self-test
passed 176 checks with no failures or skips. The source snapshot stayed
unchanged and all three copied binary digests match the runtime environment
record. This completes native verification, not Linux qualification.

The host run resolves the sandbox's socket restrictions: retained runs in
`.tmp/relay-fix/` and `.tmp/runtime-queue/relay-driver-*.log` include loopback
skips, the `commission_over_network` bind failure and the direct-helper case's
four bind failures before helper launch. Keep those originals and
`/private/tmp/stewart-relay-forwarding-fix-01` through review of the Linux run.

The subsequent Linux run `.scratch/acceptance-relay-fix-01`, at `2ec1c94`,
was recorded as failed; its index entry remains in Git history.
Both architectures passed the direct relay regression's 64 checks. Each runtime
suite passed 13 cases and failed 11: 9,724 checks passed and 42 failed, with no
skips and all 73 controls fired. Every failed check reports the same extra
`LC_CTYPE=C.UTF-8` in the Python environment witness. All 15 specified values
match. Release suites, build/static/marker comparisons and both runtime
self-tests passed. The release driver itself exited zero; the enclosing driver
result is nonzero because of the runtime failures.

The witness previously observed only `os.environ` after Python startup. Its
replacement retains complete NUL-delimited bytes before Python, plus the later
snapshot. Contract checks use the earlier snapshot; an injected `LC_CTYPE` is
still refused. Its scope starts after shell startup, as described in the
[driver guide](../../apparatus/driver/CLAUDE-CODE.md). Native self-tests passed
205 checks with no failures or skips. Controls distinguished a normal launch,
an injected locale variable, changed `LANG`, another extra variable and normal
invariance. With `LANG=C`, the native interpreter added `LC_CTYPE=C.UTF-8` after
the earlier witness; the specified `LANG=en_US.UTF-8` did not produce that change
on the Mac.

That failed suite also exported eight relay sockets inside its witness trees.
The indexer now records special entries as failures and binds their paths and
types without opening them or changing originals. Its self-test passed 99
controls and the index check passed. Relay workspaces now live outside
`witness/`; the selected comparison below verifies the ordinary evidence export
contains only regular files and directories, with copied bytes unchanged.

Native selected cases in `/private/tmp/stewart-environment-observer-native-01`
remain failed because the agent sandbox denies Unix socket binding: 144 of 153
checks passed, nine failed, one of five controls fired, with no skips. A local
wrapper check in `.scratch/environment-observer-01` reproduced those failures;
its native witness is `/private/tmp/stewart-env-cbr34u6i/results`. A missing
argument guard also allowed that check to attempt `container system status`,
which the sandbox denied; no container was launched. The wrapper now parses
arguments before work and stops on native failure. Preserve both attempts.

The host comparison `.scratch/environment-observer-02` passed on native macOS,
Linux arm64 and Linux amd64. Each passed 205 self-tests and listed 24 cases; the
two selected cases passed all 499 checks and fired all five controls, with no
failures or skips and 22 cases explicitly unselected. The native witnesses are
at `/private/tmp/stewart-env-dr5n5rw3/results`; the Linux witnesses are in each
architecture's retained evidence tar and stopped container. This resolves the
sandbox restrictions above, without qualifying the full suite.

On each Linux architecture, all four authentication/model launch witnesses
contained the specified `LANG=en_US.UTF-8` and no `LC_CTYPE` before Python,
followed by `LC_CTYPE=C.UTF-8` in Python's snapshot. The Mac's four launches
showed no added locale variable. The normal/invariance controls agree, and an
explicitly supplied `LC_CTYPE=C.UTF-8` still fails the exact-environment check.
Review verified the original NUL framing, unique names, decoded contents and
digests, all seven frozen source/specification files, and all retained input
digests. Each platform exported 158 regular files matching their originals,
without special entries. All 17 host commands passed and their owned process
groups were absent; both Linux containers were observed stopped.

The full acceptance run above completes this comparison's Linux verification.
Retain the failed runs and comparison witnesses through review of the fix.

The queued-call and Linux suite changes passed host verification in
`.tmp/runtime-queue/host.yTveQl/`, with runtime witnesses at
`/private/tmp/stewart-queue-runtime.LGe6um/run`: all three Cargo configurations,
apparatus checks and optimized marker checks passed. The runtime suite passed
23 cases, 9,702 checks and 68 controls, with no skips or unselected cases.
Its self-test passed 158 checks; the qualification self-test passed 97 controls.
The source snapshot stayed unchanged and all three copied binary digests match
the runtime's environment record. No real harness was invoked.

The cancellation comparison witnessed a refused sibling without an effect,
and cancellation won all six further races. Its traffic does not independently
identify the instant a call entered the internal queue; deterministic unit
controls cover waiting-state cancellation and queue bounds. The host run
resolves the earlier sandbox loopback failures and skips retained beside it in
`.tmp/runtime-queue/`. Keep the host outputs, binaries and independent witnesses
through review of the Linux run.

The latest completed native validation of the earlier service baseline is `.tmp/alignment/host.x1DmST`,
with runtime witnesses at `/private/tmp/stewart-align-runtime.SbCg7Q/run`: all
applicable [DEVELOPMENT checks](../../development/DEVELOPMENT.md#what-to-run-for-what-you-changed)
passed with no skips and the source snapshot stayed unchanged. The corresponding run
of the independent driver against those same binaries is
`.tmp/driver-gaps/host.QdjlTD`, with witnesses at
`/private/tmp/stewart-gaps-runtime.sDdJDu/run`: 23 cases, 9,690 checks and 68
controls passed, with no skips. It adds the hook helper, a selected effort,
cancellation, relay loss, usage across two placements and compaction; its notes
record that cancellation won all six races, each answered `placement_stopped`.
Earlier validations are `.tmp/surface-binding/host.24wFiF` (first surface-bound
form, witnesses at `/private/tmp/stewart-surface-runtime.QTlDKw/run`) and
`.tmp/document-harmonization/host.VxyhfJ` (writer-bound form, witnesses at
`/private/tmp/stewart-doc-runtime.CGwaur/run`).

Keep `.tmp/document-harmonization/` through review of the later socket EOF
failure and its fix. `host.PMinwd` retains the failed native run. The paired
socket comparisons distinguish a blocked read after peer write-half shutdown
from an empty channel or missing EOF; they do not qualify Linux behavior.
The MCP reader's bounded idle-read retries passed the strengthened regression
and the native validation above.

Keep `.tmp/claude-code-adapter*`, the earlier host runs and their external
witnesses through this implementation review; each host directory's
`runtime-work.txt` locates its witness. The original socket-mode and driver
parser failures remain intact. The baseline in `4e7478a` has its own
`host.PZGw1h` results and `/private/tmp/stewart-cc-native.DyFPFv/run` witnesses;
those records are not rebound to the current binary. Also keep
`/private/tmp/stewart-claude-driver-checks.AhLaUX`, `/private/tmp/scc5`,
`/private/tmp/scc6`, `.tmp/claude-code-contract/` and `.tmp/claude-code-probe/`
through review of their offline controls and observer comparisons.

The original `.scratch/claude-code-probe-01` and
`.scratch/claude-code-probe-02` captures remain unchanged for review of the
selected launch arrangement. Each run's frozen inputs own what executed;
previous runs confer no new launch authority. Apply the normal
[evidence retention rules](../../development/DEVELOPMENT.md#evidence-and-retention)
after review rather than retaining reproducible working trees indefinitely.

Complete this plan when the selected integration has a reviewed qualification
outcome and failures or unexercised work have explicit dispositions. Keep
enduring behavior in the owning documentation and tests, then delete the plan.
