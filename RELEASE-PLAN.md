# Release and work plan

This plan owns work order and the remaining first-release work. Individual plans
own their task's decisions and execution details. Product behavior is specified
in [CONTRACTS.md](CONTRACTS.md) and [docs/INTERFACE.md](docs/INTERFACE.md);
[ACCEPTANCE.md](ACCEPTANCE.md) defines the evidence owed.

## Work order

| Stage | Work | Working document |
| --- | --- | --- |
| Next | Prepare and authorize bounded Haiku testing on minimal questions with the current arrangement | The small-commission work in [C10-PLAN.md](C10-PLAN.md) |
| Separately commissioned conformance | Complete the C10 apparatus and run the full gate for each named model | [C10-PLAN.md](C10-PLAN.md) |
| Separately commissioned studies | Haiku instruction/presentation comparisons and question-family dogfooding | The study sections below |
| Runtime follow-on, separately scheduled | Implement and qualify Claude Code as a peer auditor runtime | [CLAUDE-CODE-PLAN.md](CLAUDE-CODE-PLAN.md) |

The Messages API sanity commission has run: one simple commission travelled
through the real provider loop, used Stewart's tools and reached a faithfully
preserved outcome. It did not qualify all question families or replace release
conformance. The small-commission apparatus has a reviewed Linux rehearsal; the
next step is a concrete bounded packet for minimal-question Haiku tests.
Full C10 qualification remains a release gate; completing its live
compaction and recovery runs is not a prerequisite for those initial tests.
Instruction/presentation variants are a separately identified study. These API
runs do not depend on the Claude Code runtime. The other release backlog is not
a prerequisite list for this sequence. Model-consuming work requires the
principal's bounded authorization under [AGENTS.md](AGENTS.md).

## Evidence and retained work

[The qualification record](apparatus/qualified.md) owns suite identities, binary
digests, counts and outcomes. Run `python3 -I -B apparatus/qualified.py check`
before relying on it. Its Linux acceptance front covers effort, provider error
reporting, compaction and stopping. Current credential checks passed on native
aarch64 and emulated x86_64.
The toolchain record establishes service reproducibility on both architectures.

The first real-model result is `.scratch/sanity-live-02`, pinned in the
qualification record with its review in `review/result.json`: `claude-haiku-5-5`
read both materials, recorded four cited entries, submitted, and the auditor
seal, verified delivery and ordinary close followed, within 8 turns, 55,401
input and 2,713 output tokens. `.scratch/sanity-live-01` is the
preceding attempt that never reached the provider because a host VPN was active;
it consumed nothing and its audit remains open in its retained container.
`.scratch/sanity-live-03` to `-06` are four mechanism runs, each pinned with a
`review/result.json`: provider rejection, a turn limit with the manager close
path, effort high, and the minimum output allowance. The `sanity-live-06`
audit remains open at its limit. Each run's container is named in its
`host/container.name`.

The launcher rehearsal in `.scratch/sanity-launch-03` passed all seven
scenarios, and `.scratch/sanity-launch-04` repeated that result on its recorded
launch code. Its reviewed evidence is in `review/result.json` within that folder;
`host/RESULT.json` binds the apparatus source, qualified executable, specimen and
container. It demonstrates synthetic credential delivery, process-access
controls, interruption, exact delivery and export withholding. It establishes
the native Linux path against local fakes, not real-provider conformance.

The small-commission rehearsal `.scratch/c10-launch-01` is pinned with its
review in `review/result.json`. It binds commit `043a2c4`, the qualified
`acceptance-05` aarch64 executable and the pinned image. It covers all six fixed
commissions, failure/export controls, independent input readback, procedural
review and immutable follow-up collection. The report retains actual counts,
scope limits and the container identity. It completes small-commission apparatus
readiness; it makes no model-support claim.

The qualification record pins that rehearsal, the earlier failed attempts and
their diagnostic controls. Keep their original containers and independent
credential witnesses through review. Current acceptance containers are named in
`.scratch/acceptance-05/host/driver-<arch>.container`; each launcher container is
named in its `host/container.name`. Disposal is the user's
decision under [DEVELOPMENT.md](DEVELOPMENT.md#evidence-and-retention).

## Messages API sanity commission

Completed; the result is recorded above. The specimen, procedure and
[commission proposal](apparatus/sanity/COMMISSION.md) remain the template for
a further bounded run. Remaining observation: reconcile the reported usage with
the Console's billing records for the `stewart-exp` key, which Stewart cannot
observe. The retained containers and the open `sanity-live-01` audit await the
user's review and disposal decision under
[DEVELOPMENT.md](DEVELOPMENT.md#evidence-and-retention).

## Haiku framing study

Find how much guidance helps an auditor answer the manager's question without
repeating Stewart's harness structure. Vary instructions and presentation
separately:

| | Current presentation | Plain presentation |
| --- | --- | --- |
| Current instructions | Baseline | Presentation change alone |
| Lean instructions | Instruction change alone | Both changes |

Lean instructions retain the commission, evidence/access boundaries and
submission mechanics while removing duplicated coaching. Plain presentation
foregrounds the auditor's text without automatically added Account, Observation
or Limit headings. Preserve records, citations, attribution and custody behavior.
Initially keep recording tools unchanged, along with the question, materials and
model/settings within each comparison.

Use a few small commissions with repeated runs. Inspect model-authored prose
separately from the rendering: engagement with the question, relevant uncertainty,
unnecessary harness discussion, tool use and submission. Fewer words or
qualifications are not automatically better. Recording categories and preparation
notices remain possible influences for later comparisons.

Record whether the auditor reads the prepared rendering; that optional exposure
may affect edits. Compare presentations of the same recorded answer without a
new model call when studying the manager's reading experience. Such views are
study artifacts, not replacements for sealed returns. Retain the original
outputs and conditions.

Needs: exact Haiku model/settings, variants, specimens, repetitions and
spending/retry limits. Prompt wording and rendering changes remain to be designed.
Results apply to the tested arrangement; transfer to another runtime or model
needs checking. Findings do not automatically change defaults or submission rules.

## Question-family dogfooding

The five purposes and shared boundaries are in
[CONTRACTS.md](CONTRACTS.md#question-families-and-open-inquiry). Investigate:

- Material recipes, prompt guidance and expected sections.
- Recording vocabulary for claim examination and experimental inquiry, whose
  dedicated forms are not implemented.
- Useful read-only experimental contributions, the manager's repair work and
  the usefulness of model returns.

Preserve the common custody and attribution contract, legitimate returns across
families, and the distinction between notices and blocking checks. Execution
permission is independent of family choice. Any deployed form needs consistent
specification, service, help/examples and independent-driver changes with the
applicable checks. A proposed substantive restriction requires a product decision.

## First-release requirements

| Requirement | Remaining work |
| --- | --- |
| Linux container qualification | Run the scripted acceptance suite on the release source and binaries, on both architectures with the required controls. |
| Native WSL2 qualification | Package the same binary, driver and fake provider; arrange and review the user's native run. |
| Real-model conformance | Complete [C10-PLAN.md](C10-PLAN.md) and qualify each model the release names under an authorized budget. |
| Public release gate | Set the binary release schedule with the principal. |

The requirements remain those of ACCEPTANCE while its review is open.

### Coverage and acceptance-policy review

Check driver cases against every ACCEPTANCE claim. Uncovered requirements need a
case or an explicit disposition. Candidate gaps include C17's secondary logging
errors, blind repetition after reply failure and omitted partial effects; C18's
pressure pruning, confusion between retained and delivered bytes, and missing
archives reported clean; and C11's scans presented as snapshot proof. Driver
changes require an implementation-independent author.

Resolve these acceptance-policy questions without silently changing the current
requirements:

- Reconcile ACCEPTANCE's per-change tier/image language with batched container
  qualification and the current pinned Python runner.
- Confirm the platform and real-model release gates and coverage scope.
- Decide whether and how to add Linux Cargo tests, toolchain-digest enforcement
  and native/emulated execution recording to the toolchain suite.
- Review qualification rules for skips, timing gates and failures across
  platforms. Native protocol timings approach the limit; emulated x86_64 has no
  enforced timing gate.
- Decide whether to support running the apparatus from a Linux host; the
  documented host route uses macOS and Apple `container`.

### WSL2 package

The package must carry the same qualified release/test binaries, driver and fake
provider. Run with the home on the WSL filesystem and a destination under `/mnt/`;
record Windows/WSL versions, distribution, kernel, architecture and filesystems.
The native timing gate applies. Native x86_64 is unexercised, so its timings must
be measured rather than inferred from Rosetta.

Needs: a package builder, instructions and the user's scheduled run.

### Real-model conformance

[C10-PLAN.md](C10-PLAN.md) owns the specimens and run matrix, reusable launcher,
continuation and evidence collection, procedural verifier, compaction and
provider-coverage work, checks and bounded run packets. Its small-commission and
full-apparatus milestones distinguish readiness to test from model qualification.
The gate remains [ACCEPTANCE C10](ACCEPTANCE.md#the-real-model-conformance-tier);
a model is supported only after it passes that gate.

### Build and test coverage

- **Cargo tests on Linux.** The service's tests have run on the development Mac;
  the Linux suites build the crate and exercise it through the independent driver.
  Add an offline container test route with `STEWART_IT_TMP` on ext4, xfs or btrfs
  if selected in the acceptance review.
- **Toolchain identity.** The Containerfile pins its base image, but target and
  package installation can change a rebuilt image. Built image digests are the
  actual pins. Acceptance records image inspections by tag but does not enforce
  equality with the toolchain record; decide the intended enforcement.

### Documentation and test discrepancies

- Align CONTRACTS' illustrative prepare/submit field names with INTERFACE 7.6
  (`prepared_handle`, `answer_revision` and the notice key `section` differ).
  Clarify the synonymous family/form terminology where needed.
- Correct INTERFACE 9's claim that named fault traces run against the release
  binary; fault points are test-build features. Correct CLI help's assertion
  that every non-help command accepts `--json`: raw receipt readback does not.
- Have an implementation-independent author correct the TLS fixture README's
  expired-certificate validity and its description of wrong-name/expired
  self-test fixtures as driver controls.
- Add a check that prepares the worked examples. Make unavailable loopback tests
  report actual skips rather than printing SKIPPED and returning as passed.

Deferred product scope belongs in CONTRACTS; it is not additional release work.
