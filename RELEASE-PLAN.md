# Release and work plan

This plan owns work order and the remaining first-release work. Individual plans
own their task's decisions and execution details. Product behavior is specified
in [CONTRACTS.md](CONTRACTS.md) and [docs/INTERFACE.md](docs/INTERFACE.md);
[ACCEPTANCE.md](ACCEPTANCE.md) defines the evidence owed.

## Work order

| Stage | Work | Working document |
| --- | --- | --- |
| Next implementation | Specify, build and demonstrate the narrow rapid-iteration path described in its topic plan | [RAPID-QUESTION-ITERATION-PLAN.md](RAPID-QUESTION-ITERATION-PLAN.md) |
| Further auditor studies when selected | Name the uncertainty and bind model and budget before any launch | [INTERACTION-PLAN.md](INTERACTION-PLAN.md) |
| After self-contained rapid iteration is demonstrated | Consider the manager's consumption of answers; no redesign is commissioned | A scope to be agreed when selected |
| Deferred design marker; no implementation scheduled | Explore a deterministic linter for redundant read-only caveats after answer preparation | [FUTURE-LINTER-PLAN.md](FUTURE-LINTER-PLAN.md) |
| Separately commissioned conformance | Complete the C10 apparatus and run the full gate for each named model | [C10-PLAN.md](C10-PLAN.md) |
| Separately commissioned studies | Question-family dogfooding | The study section below |
| Runtime follow-on, separately scheduled | Implement and qualify Claude Code as a peer auditor runtime | [CLAUDE-CODE-PLAN.md](CLAUDE-CODE-PLAN.md) |

The completed model encounters supply reference observations for further work.
Further placements need a named question, exact model and bounded spending.
Small API comparisons can use the existing apparatus without completing the
full C10 gate or adding another runtime. Release gates remain separately
scheduled work.

## Current evidence

[README](README.md#status) owns product maturity and coverage limits;
[the qualification index](apparatus/qualified.md) owns current suite results
and selected evaluations. Retain originals for inspection under
[DEVELOPMENT](DEVELOPMENT.md#evidence-and-retention), not to reconstruct old
builds. Completed model placements confer no further spending authority.

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
  platforms. The native protocol tripwire is 200 ms; emulated x86_64 has no
  enforced timing gate. Retiring the absolute tripwire or moving performance
  trends into Linux CI remains a later policy option, not implementation
  scheduled now.
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
