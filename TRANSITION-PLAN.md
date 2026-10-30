# Transition plan: implement the decided Stewart design

Current account, 2026-10-29. The design review is closed. The user accepted the
machine-interface rules and commissioned consolidation and retirement of review
exhaust. The extraction is committed and the superseded material is removed.
That closure commissions no model runs or runtime implementation by itself.

**Commission of 2026-10-29: steps 1–6, the local scripted build; completed
2026-10-30** (evidence below). Its endpoint was the first integrated
end-to-end audit against the fake provider.
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
fat LTO. The mechanism, traced later in the toolchain sources, is under "Not
done, and why".

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
what the control breaks. All fixed by `dc85948` (the driver's reacting
auditor had been skipping its allowance comparison in every case, found
through the unfired continuation control); native check of `dc85948`: every
service test passes, driver 95/95 runnable cases, 61 controls fired, exit 0.
Steps 4–6 milestone met by `.scratch/acceptance-02` (source `dc85948`,
2026-10-30): `failures=0`. Every apparatus check and control passed on both
architectures; driver self-test 246/246 on both. aarch64 native: 110/110
cases, all 66 sabotage control variants fired (every one of the 62 Appendix
C.2 controls), 8/8 driver controls, timing gate passed (worst 2.0 ms).
x86_64 under Rosetta: 108/108 cases, 66/66 and 8/8, timings reported only
(worst 40 ms). The integrated end-to-end audit (`e2e.reacting-audit`: prepare,
commission, a reacting fake auditor working through the run, submit and seal,
verified delivery, close) passed 764/764 checks on the release binary of each
architecture. Release binaries: aarch64
`5b3c40b802a9a03c71691d7dbee1c39ad81cd54b4c1290ba57d4706725dcb46d`, x86_64
`c30ff785d7c0e6ac7d1b91dd3fa9cbeec7fe1795ab1e21d5e2e1666aefd7e6d6`. This is
the endpoint of the current commission (steps 1–6, no model spend). Next
steps (7: whole-suite qualification and the WSL handoff; 8: real-model
conformance with a named budget) need a new commission.

## Not done, and why (2026-10-30)

The steps 1–6 commission ended at its endpoint. Nothing below is in progress;
each item needs the decision or commission named.

- **Opus effort default: decided, not implemented.** The user decided at the
  end of the commission that requests to Opus models should carry effort
  `high` by default. Today the arrangement pins `request_extra` as `{}` and the
  release allowlist is empty (INTERFACE 6.2), so requests set no effort and
  Opus 5.5 runs at its API default, `medium`. Implementing it changes the
  pinned arrangement bytes and the request shape: INTERFACE 6.2 (allowlist and
  how the arrangement pins effort per model), the arrangement and its readable
  form, the driver's request witness (C1), and a container suite run. It was
  decided after the milestone and is the first change for whoever builds the
  real-model apparatus.
- **Step 7, qualification and the WSL2 handoff: not commissioned.** The whole
  scripted suite already passes on both Linux architectures
  (`.scratch/acceptance-02`). Still owed: a claim-by-claim check of the driver
  plan (apparatus/README.md, "Driver plan") against ACCEPTANCE for anything not
  covered, the binary/driver/fake-provider handoff for native WSL2, and the
  user's WSL run, which is an external dependency.
- **Step 8, real-model conformance: not commissioned.** Needs named models,
  settings (including the effort default above) and an explicit budget before
  any model-consuming run. The release's TLS path to the real provider with its
  built-in web PKI roots has not been exercised: the scripted tier reaches TLS
  and the CONNECT proxy only through the test build's extra trust root.
  `max_tokens_per_request` (16,000) and the 600 s timeout are pinned but
  unqualified against real responses.
- **Step 9, retiring Python: not started**, by design (it follows step 8).
- **Fat-LTO `getrandom`: worked around; mechanism traced in source, not yet
  confirmed by a run.** In the fat-LTO static musl release build Stewart's
  `libc::getrandom` call linked to nothing (observations and reproduction
  steps: `.scratch/fat-lto-getrandom-01/REPORT.md`). The toolchain sources at
  rustc `b940084d7` account for every observation
  (`.scratch/fat-lto-getrandom-02/ANALYSIS.md`). std declares `getrandom`
  `extern_weak` for its own syscall fallback. Fat LTO links every other
  module into the binary's three-line `main` module in name order, and LLVM
  keeps the first declaration's linkage, so std's weak declaration, sorting
  before the `stewart` library's strong one, governs the library's call.
  ld then links no definition and the call resolves to address 0. The six
  small programs and the in-crate example worked because they made the call
  from the binary crate itself. Stewart calls the raw syscall instead
  (`service/src/platform.rs`). The deciding comparison (the same code with
  the library crate named to sort after or before `std`) is written as a
  request to Riker, `.scratch/fat-lto-getrandom-02/RIKER-REQUEST.md`; it
  has been neither sent nor run. Exposure: only direct libc calls to
  functions std declares weak (`.scratch/fat-lto-getrandom-02/std-weak-symbols.txt`).
  Stewart makes none today, since `getrandom` and `statx` are raw syscalls,
  but a toolchain upgrade can add to std's list.
- **Decisions made during the build that a reviewer may revisit** (reported to
  the user, not contested): damaged commissioned material refuses `run`
  (`commission_damaged`) rather than running with that material refused;
  members damaged after the seal become surrenderable delivery-stage losses,
  and a later close retries them if they verify again.
- **Development setting on the user's machine:** loopback listening was
  enabled for native iteration. The container suite does not need it.

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
