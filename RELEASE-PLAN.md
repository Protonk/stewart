# Release and work plan

This plan owns work order and the remaining first-release work. Individual plans
own their task's decisions and execution details. Product behavior is specified
in [CONTRACTS.md](CONTRACTS.md) and [docs/INTERFACE.md](docs/INTERFACE.md);
[ACCEPTANCE.md](ACCEPTANCE.md) defines the evidence owed.

## Work order

| Stage | Work | Working document |
| --- | --- | --- |
| Next action | Qualify the targeted citation-refusal repair from the completed Haiku comparison and close the vocabulary revision | [RESPONSE-VOCABULARY-PLAN.md](RESPONSE-VOCABULARY-PLAN.md) |
| After the Haiku vocabulary block | Broaden auditor studies, with Opus the intended next candidate; bind model and budget for that comparison | [INTERACTION-PLAN.md](INTERACTION-PLAN.md) |
| Retained next implementation candidate; not a prerequisite for broadening auditors | Select, build and demonstrate the narrow rapid-iteration path proposed in `.scratch/rapid-iteration-01/DECISION-BRIEF.md` | [RAPID-QUESTION-ITERATION-PLAN.md](RAPID-QUESTION-ITERATION-PLAN.md) |
| After self-contained rapid iteration is demonstrated | Consider the manager's consumption of answers; no redesign is commissioned | A scope to be agreed when selected |
| Deferred design marker; no implementation scheduled | Explore a deterministic linter for redundant read-only caveats after answer preparation | [FUTURE-LINTER-PLAN.md](FUTURE-LINTER-PLAN.md) |
| Separately commissioned conformance | Complete the C10 apparatus and run the full gate for each named model | [C10-PLAN.md](C10-PLAN.md) |
| Separately commissioned studies | Question-family dogfooding | The study section below |
| Runtime follow-on, separately scheduled | Implement and qualify Claude Code as a peer auditor runtime | [CLAUDE-CODE-PLAN.md](CLAUDE-CODE-PLAN.md) |

The interface study's earlier Haiku engagement is complete: the A/B baselines, the
guidance intervention, the Fable Problem B encounter and the five stress
one-offs have run and are reviewed, and every placement is consumed.
[INTERACTION-PLAN.md](INTERACTION-PLAN.md) owns those findings, candidate build
and evidence. The later autonomous failure-and-recovery campaign is also
complete; [its findings](apparatus/studies/haiku-recovery/RESULTS.md) own the
observed cases, resource accounting and explicit review limitations. Its host
worker is stopped, and no further placements are queued. Haiku has served as the
initial experimental auditor; the next phase broadens the evidence so its habits
do not become general design requirements. Additional Haiku runs should resolve
a named uncertainty or check a specific repair. The next models and spending
bounds remain the principal's decision.

The interface study used cheap model calls on the small-commission apparatus
without completing the full C10 apparatus.
Full C10 qualification remains a release gate; its live
compaction and recovery runs need their own commission. These API runs do not
depend on the Claude Code runtime. The other release backlog is not a
prerequisite list for this sequence. Model-consuming work requires the
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
`.scratch/sanity-launch-05` and `.scratch/c10-vocabulary-launch-01` repeat the
sanity and C10 rehearsals on the `acceptance-vocabulary-03` executable; both
are pinned with their reviews.

The reporting apparatus at `453a60d` passed the reviewed Linux aarch64 rehearsal
`.scratch/c10-report-linux-01`, pinned in the qualification record with its review
at `review/result.json`. This completes the four apparatus-reporting steps. The
run covers the fixed catalog, reviewer, operator and report comparisons, and
Linux process-access controls with the `acceptance-05` executable. It used no
models and does not qualify one. It did not exercise saved Keychain connections,
additional study templates or an unqualified build override.

The supplied-study and saved-connection rehearsal `.scratch/c10-study-launch-01` is pinned
with its review in `review/result.json`. It binds commit `751aa7c`, the qualified
`acceptance-05` aarch64 executable and the pinned image. It covers all six fixed
commissions, both frozen study templates, failure/export controls, independent
input readback, procedural review and immutable follow-up collection through the
saved synthetic connection. The report retains actual counts, scope limits and
the container identity. It matched the apparatus used for the baselines; its
source binding differs from the current reporting apparatus. It makes
no model-support claim. The earlier `.scratch/c10-launch-01` remains pinned
with its original evidence.

Interface-study evidence, from the Problem A and B baselines through the five
stress one-offs, is pinned in the qualification record and owned by its topic
plan; none of it qualifies a model. The host synthetic connection checks are
pinned separately at `.scratch/connection-checks-01/review-02.json`, which
preserves the failed attempt and limits on the locked-state observations.

The combined pilot review is pinned at
`.scratch/c10-haiku-commission-01/review/result.json`, with `report.md` linking
the six answers and their inspections. It owns aggregate counts, coverage limits,
calculated cost and the requirements-only framing concern. The individual runs
`.scratch/c10-live-01` through `.scratch/c10-live-06` are also pinned. The pilot
establishes no model qualification or authority for further model calls.

The qualification record pins the launcher rehearsals, the earlier failed attempts and
their diagnostic controls. Keep their original containers and independent
credential witnesses through review. Current acceptance containers are named in
`.scratch/acceptance-vocabulary-03/host/driver-<arch>.container`; each launcher container is
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
