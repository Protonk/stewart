# Transition plan: implement the decided Stewart design

Current account, 2026-10-29. The design review is closed. The user accepted the
machine-interface rules and commissioned consolidation and retirement of review
exhaust. The extraction is committed and the superseded material is removed.
That closure commissions no model runs or runtime implementation by itself.

**Current commission (2026-10-29): steps 1–6, the local scripted build.** Its
endpoint is the first integrated end-to-end audit against the fake provider.
No model-consuming run is included. The coordinator's shell sandbox cannot reach
Apple `container` (its Rosetta check is denied), so the coordinator prepares
container commands and scripts and the user runs them with `!`.

Progress: step 1 is specified in [docs/INTERFACE.md](docs/INTERFACE.md) and
[docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md). The new crate is `service/`
(binary `stewart`); the commission-bundle slice stays in `successor/`.

Step 2 run `.scratch/apparatus-01` (driver `apparatus/step2.sh`, source
`47e5a59`, 2026-10-30): `failures=0`. Toolchain images
`stewart-toolchain:1-arm64` `sha256:03baac7fedd2437d0b448415a1e7352b670f03c8ca85be480940e71d972dae8a`
and `-amd64` `sha256:15ecee566d9ed3c6da79edce13738babb3861206fcad068cd9214fcf737916f4`
(rustc 1.99.0, musl 1.2.5). Two offline builds per architecture were identical:
aarch64 `5febe49834927c764a1433a430615949c69d1c00a8c8dcc97f0b00ada7c8702b`
(static executable), x86_64
`a028cba9713f87b25b59993e8cbaa00cdc101b19401e9cb0c8441238babf0be1` (static PIE).
Neither requests a program interpreter, and both ran in their toolchain image and
in alpine. The run had no firing controls for its static and reproducibility
checks; the step 3 driver adds them (a glibc build must fail the static check).

Working arrangement from step 3 on (agreed 2026-10-30): the coordinator iterates
natively on the development Mac with the vendored crates, with small
development-only fallbacks for the Linux-only calls. The user runs one Linux
container suite per milestone; only that suite counts as evidence. The
implementation (`service/`) and the independent driver (`apparatus/driver/`) are
written separately from the spec, and the driver's author does not read the
implementation. Test builds use the `fault-injection` and `sabotage` features;
the release binary contains neither.

Step 3 milestone run `.scratch/step3-01` (source `e714629`): the Linux code
compiled and every apparatus control fired on both architectures, but the
driver failed on both: all-zero identifiers on aarch64 (stage-name collisions)
and SIGSEGV in `new` on x86_64. Diagnostics `.scratch/diag-linux-01` to `-03`
located it: every Linux-only call worked in isolation; only the fat-LTO release
build failed; in it musl's `getrandom` was absent from the binary while thin LTO
linked it. Calling the raw `SYS_getrandom` syscall fixed both architectures under
fat LTO. The mechanism behind the missing symbol is not established.

Step 3 milestone met by `.scratch/step3-03` (source `3c4e795`, 2026-10-30):
`failures=0`. aarch64 native: 70/70 cases, 16/16 sabotage and 8/8 driver
controls fired, timing gate passed (worst 2.3 ms). x86_64 under Rosetta: 69/69
cases, 16/16 and 8/8 controls, timings reported only (worst 29 ms). Every
apparatus control fired on both. Release binaries: aarch64
`909accb9833c74709fd6bac36ce16a97e85022c309bf6ff072af4fc1f94e477f`, x86_64
`dcf0c2267988987f7c45d35cf0d5c2f02850e48f7b8285a7a28cae93e943d13b`. The run
before it, `.scratch/step3-02`, passed on aarch64; on x86_64 the driver counted
Rosetta's own `$HOME/.cache/rosetta` as a write by Stewart, now recorded as an
emulator artifact under detected emulation only.

Steps 4–6 are being built as one milestone (decided 2026-10-30): a run must
deliver after an auditor seal, and close after launch shares the seal and
delivery code, so the answer protocol, run adapter, delivery and close after
launch are built together and qualified by one container suite ending in the
integrated end-to-end audit. Provider specification checked 2026-10-30: the
adapter pins `anthropic-version: 2026-10-21` and handles the
`model_context_window_exceeded` stop reason. Order: exact schemas for records,
captures, manifest, replies and test-build controls are added to INTERFACE
first; then implementation (answer protocol; run adapter; seal, delivery and
close after launch) and the independent driver with its fake provider proceed
in parallel from that text.

Steps 4–6 status (2026-10-30): built and integrated on main at `1bd98bf`
(specification amended through `2c927ab`). Native development runs on macOS
against `2c927ab` (not evidence): every service test passes in both
configurations; the independent driver passes all 95 cases that can run
natively (82 run and foundation cases, 13 after-launch cases); every
sabotage control variant that ran natively fired (50 and 11 as the two
authors' runs report them) and every driver control fired. Not yet exercised:
six cases that need Linux OFD locks (T7, interruptions, the submit/close race,
continuation, stopping, close while running), the five control variants that
only they carry, and two heavy bound cases. First contact between the driver
and the implementation produced eight specification amendments and three
implementation defects, all settled: a linked but uncertain seal was not
delivered, refusal and failure effects misreported delivery, closure and
retained locations, and close misread a run's exit as another close. The
milestone run is `apparatus/acceptance.sh` (container suite, both
architectures).

First milestone run `.scratch/acceptance-01` (source `1e061a6`): every
apparatus check and control passed on both architectures, and the driver
self-test passed (245/245). Driver: aarch64 108/110 cases (timing gate on,
worst 3.2 ms), x86_64 106/108, identical failures on both, all in the
Linux-only cases first run here: two driver errors (a race case reusing pause
files across repetitions; an aborted request expected uncharged), one
specification conflict (status charged a live placement's in-flight request
as if the process were gone; settled in `a1515e7`), a test-build pause that
continued silently on a stale file (now aborts), and two sabotage controls
(`torn_as_entry`, `reset_limits_on_continuation`) whose cases did not observe
what the control breaks. Fixes in progress; a second run follows.

There is one design in [DESIGN.md](DESIGN.md), one behavioral authority in
[CONTRACTS.md](CONTRACTS.md) and one acceptance specification in
[ACCEPTANCE.md](ACCEPTANCE.md). This is the only active development plan. No
earlier program, conversation or candidate architecture is a prerequisite.
Keep the current account here; retire the plan after implementation or explicit
abandonment, moving enduring material into documentation/tests.

## Starting state

- Frozen Python remains the usable legacy audit tool; it is not a parity baseline.
- `successor/` supplies a working, separately scoped commission-bundle binary.
  Reuse useful primitives, not its old public workflow or qualification claims.
- The paper examples have completed a bounded review. They support expression
  and presentation choices only, not executable protocol or model conformance.
- No worker, runtime build or model experiment is pending from the design review.

## Dependency path

| Step | Deliverable and exit evidence |
| --- | --- |
| 1. Specify the interfaces | Exact manager CLI and auditor-tool request/reply schemas; role-visible fields; handle bindings; records and publication boundaries; supported writer rules; strict decoding; pagination and limits; literal success/failure fixtures. Specify the three forms and deterministic renderer under `docs/QUESTION-FORMS.md`. Include dry run, empty/missing sections, stale targets/preparation, lost replies, manager seal, partial custody and uncertain acceptance. Naming and encoding are engineering choices; new authority, material access or substantive restrictions return to the user. |
| 2. Build the apparatus | Pinned Linux Rust/musl toolchain, small recorded dependency set and offline reproducible builds for aarch64/x86_64; test image with independent driver/fake provider; separate real-model apparatus. Build/test a trivial binary on both architectures and record binary/image identities. Preserve command outputs, witnesses, counts and controls under DEVELOPMENT.md's evidence rules; add successor-specific commands alongside implementation. |
| 3. Build the manager foundation | Explicit reference/archive, ordinary folder scaffold, strict local prepare/confirmed commission, safe captured bytes, pinned arrangement, receipt/raw readback, factual status and contextual failures. C2/C6/C9/C11/C15 and relevant C16–C20 cases. Reconcile interrupted acceptance before recapture; do not qualify merely by exercising the older intake binary. |
| 4. Build the answer protocol | Durable typed entries/raw artifacts, exact edits, bounded reads/re-entry, immutable prepared selection/rendering, actual seal and known-result replay. Selected families, citation checks, nonblocking omissions and empty submissions. C3/C4/C7/C20, relevant C5/C9. Faults and races use controlled synchronization and independent witnesses. |
| 5. Build the run adapter | Thin provider loop bound to the pinned arrangement, network/key boundary, run exclusion, limits and prompt allowances across placements, bounded provider retry, continuation and recorded observations. C1/C4/C12/C13; fake provider first. Qualify actual access and stopping control, including a run invoked by another process. |
| 6. Complete delivery and close | One close across preparation/intake/never-launched/live/sealed/delivered/damaged states; no answer before launch; actual seal actor; verified independent delivery; exact confirmation and named-loss surrender; unfinished close continuation; no removal. C5/C8/C16–C20. Exit is the first integrated end-to-end audit with honest failure routes. |
| 7. Qualify the scripted release and WSL | Entire acceptance suite on both Linux architectures, every control firing, actual response timings and counts. Prepare binary/driver/fake-provider handoff for native WSL2; qualify actual filesystem behavior and record environment. The user's WSL handoff timing is an external dependency. |
| 8. Qualify supported models | Separately authorized, bounded real-provider conformance: fixed commissions, compaction and kill/continuation, procedure rather than answer grading. Name models, settings, actual coverage and cost. Paper agents or fake-provider success cannot replace this gate. |
| 9. Retire Python | After the integrated audit service and at least one model-conformance pass, inventory live audits, independent resources/claims, recoveries, holds and partial requests. Settle their obligations under their writer, then obtain the user's retirement confirmation. Only then remove Python runtime/tests/manual/checker and revise installation guidance. No rewritten historical receipts or inferred transfer of execution authority. |

User help, structured error messages, documentation and acceptance fixtures grow
with each step. Freeze shared schemas before parallel operation implementations.
Coordinators own decomposition, Git and integration within the actual commission;
the user retains semantic control, consequential crossings and spending scope.

## Conditions before implementation and spending

The next commission should name its implementation endpoint. A complete local
scripted build can be scoped independently of paid model qualification. Name the
provider/model coverage and explicit budget before model-consuming runs; no
particular Claude launch is authorized by this plan. A first adapter can use the
Messages API direction without treating an old illustrative model/version as a
selected supported model. Verify current official provider specifications when
implementation reaches that dependency.

Exact process exclusion/stopping, crash publication, filesystem qualifications,
front-matter encoding, numerical response budgets and schema names are spec/build
work. They are not reasons to reopen settled manager or answer policy. Return a
specific unmet promise if qualification shows the design cannot support it.

## Disposition and later work

The old five-stage program, alternative workspace/history arrangements, separate
custody-first stage, unrun Python parity comparisons and orientation trial are
abandoned as programs. Applicable identity, custody, interruption, expression and
platform cases are in CONTRACTS/ACCEPTANCE. The Linux check remains historical
apparatus evidence, not release qualification. General resources, executor,
restart convenience, removal and a generic legacy reader are outside this build.

Person transport, hidden priors, larger form catalogues/module composition,
family-admission research and whether read-only inquiry is sufficient are later
work only if separately commissioned. They are not unfinished prerequisites.
Legacy obligations remain the retirement gate above. Retained evidence and local
run ownership are indexed in coordination/EVIDENCE.md, not another design queue.
