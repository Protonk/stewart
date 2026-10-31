# Release plan

The remaining work toward Stewart's first binary release, and what the evidence
so far does not cover. This is a working account, not specification: the
behavior and the evidence owed are in [DESIGN.md](DESIGN.md),
[CONTRACTS.md](CONTRACTS.md), [ACCEPTANCE.md](ACCEPTANCE.md),
[docs/INTERFACE.md](docs/INTERFACE.md) and
[docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md). Update the plan when
decisions or remaining work change. When the release is made or the plan is
abandoned, give each open item a disposition, move what endures into
documentation and tests, and delete this file.

## Endpoint

A first release needs:

- **Linux container qualification of the release commit.** The scripted
  acceptance suite (`apparatus/acceptance.sh`) run at the commit the release is
  built from, qualified on both architectures with every control firing.
- **Native WSL2 qualification.** ACCEPTANCE ("Platforms") requires the
  scripted tier to run natively on WSL2 from a handoff package of the same
  binary, driver and fake provider. It takes the claim-by-claim check of the
  driver's cases against ACCEPTANCE, the handoff bundle and the user's run.
- **Real-model conformance** (ACCEPTANCE, "The real-model conformance tier",
  claim C10) for each model the release names, under a budget the user names
  before any model-consuming run.
- **The user's binary release schedule.** It is the public gate and is still
  to be set up.

The first three come from ACCEPTANCE. The discussion of what acceptance testing
Stewart needs ("To discuss", below) may change them.

## Current account (2026-10-31)

[apparatus/qualified.md](apparatus/qualified.md) records what the container
suites have shown: each run's source commit, counts, digests and outcome, and,
through `python3 -I -B apparatus/qualified.py check`, the changes since each
run's source commit. Its front is `acceptance-03` (`apparatus/acceptance.sh` at
`faa5579`) and `apparatus-01` (`apparatus/step2.sh` at `47e5a59`), both
qualified on both architectures. No run has consumed a model. The earlier runs,
including `acceptance-02`, are superseded; Git retains their accounts and
qualification records. Run records are under `.scratch/` on the
development Mac, which Git ignores, and stay while they are on the front,
pinned or cited (DEVELOPMENT.md, "Evidence and retention"). This section keeps
what the record does not hold.

`apparatus-01` built the crate skeleton of `47e5a59`, which only linked the
release dependency set, not the service. Its static and reproducibility checks
had no firing controls. `acceptance.sh` adds one for the static check (a glibc
build must fail it) and shows that `cmp` tells the release and test binaries
apart, but the two-build comparison runs only in `step2.sh`. In `acceptance-03`
the 74 sabotage control variants cover all 70 controls of INTERFACE Appendix
C.2. All 121 aarch64 and 119 emulated x86_64 cases passed, with no failed or
skipped cases; each architecture passed 149,139 checks with no failure outside
controls. All 8 driver controls fired and each self-test passed 298/298 checks.

The protocol timing gate, `c9.protocol-timing-gate`, requires every gated
protocol call, as the fake provider measures it, to take under 100 ms; a
full-material search is not gated. It passed natively on aarch64 in
`acceptance-03`; the release's slowest gated tool kind was
`record_observation`, at 92.542 ms. Under Rosetta on x86_64
the gate is off and timings are only reported.

### Not yet exercised

- Any real model, and the release's TLS path to the real provider with its
  built-in web PKI roots: the scripted tier reaches TLS and the CONNECT proxy
  only through the test build's extra trust root.
- `max_tokens_per_request` (16,000) and the 600 s request timeout, which are
  pinned (INTERFACE 6.2) but unqualified against real responses.
- Native WSL2.
- The service's own cargo tests on Linux.
- The two-build comparison on the service rather than the crate skeleton.
- The effort parameter against the real provider.

## Work items

Each item says what it needs. Container suites are host scripts that the user
runs (DEVELOPMENT.md, "Container suites"). Exact process exclusion and
stopping, crash publication, filesystem qualifications, front-matter encoding,
numerical response budgets and schema names are specification and build work,
not reasons to reopen settled manager or answer policy. If qualification shows
the design cannot support a promise, bring that specific unmet promise to the
user.

### Before the first live API test

Discussion agenda reviewed 2026-10-31, excluding question-type design, wording
and answer-quality evaluation. This section owns the preparation questions for
the current Messages API adapter. The adopted
[five-purpose freeze](CONTRACTS.md#question-families-and-open-inquiry) settles the
commission's meanings. Family recipes, tool optimization and intellectual utility
are later dogfooding work. The later
runtime work is staged in
[CLAUDE-CODE-PLAN.md](CLAUDE-CODE-PLAN.md); none of its implementation is a
prerequisite to the first API test. The following recommendations do not add
release gates or authorize a model call.

The first paid Messages API test is a bounded sanity check: a simple commission
travels through the real model loop, exercises named tools and reaches a properly
preserved outcome. It can use an already implemented family. It does not wait for
the two additional families' final recording tools, prove five sets of
instructions optimal, or replace the release conformance tier. Preserve failed
outcomes honestly without calling an unexercised submission path successful.

| Topic for the next discussion | Decision or concrete preparation needed |
| --- | --- |
| What the first run should establish | Select one simple specimen using an existing family, preferably open inquiry, and name the procedural observations for real provider requests, auditor tool use, explicit submission and preserved delivery/close. Keep claims limited to operations actually exercised. Effort comparisons, actual compaction and forced interruption/continuation remain separately scoped follow-up work, not implied parts of this first sanity check. |
| Model, settings and spending | Name the exact model, effort setting or deliberate omission, provider/account route, total spending authority and run/token allowances. Include the permitted retries, continuations and stop conditions in the bounded commission. Stewart counts tokens and turns; it does not enforce a dollar ceiling. Recheck current provider support and pricing when costing the proposed run. |
| Binary and execution environment | Identify the committed source and release-binary digest, Linux environment, supported archive filesystem, destinations, endpoint/proxy configuration and credential delivery. The release's built-in TLS roots have not reached the real provider. Use explicit API authentication and record non-secret configuration. Decide the scripted qualification baseline for the first run. |
| Live runner and retained observations | Build a small, reviewable launch/observation procedure. The existing suites all use local fakes with `--network none`; they are not a live runner. Preserve original input copies independently, raw conversations and attempt records, stdout/stderr, run/status/receipt results, delivered bytes, actual usage and available provider cost records in a fresh retained run folder. Record observer scope and timing; credential values are not evidence artifacts. |
| Stopping, failures and recovery | Identify who operates close/interrupt and how the running process is observed. Distinguish request rejection, exhausted allowance, interrupted placement, unsubmitted ending, sealed answer and incomplete delivery. Check actual effects before retrying. A manager close must not turn an unsubmitted run into a claimed conformance pass. Studies of interruption or missing capture need an independent witness and controls retained through review. |

**Recommended preparation before spending:**

- **Done:** `acceptance-03` qualifies `faa5579` on both Linux architectures,
  including effort, compaction and the compaction-stopping case skipped on
  macOS. Its retained release binaries can supply the first live run.
- The [sanity packet and run sheet](apparatus/sanity/RUN-SHEET.md) now hold a
  small code specimen and an offline rehearsal of intake, tool use, outcome
  classification, delivery verification and close. The rehearsal is awaiting
  its host container run. The user has made API-key handling a separate task
  before a paid launch: map, harden and audit the credential path. No live
  credential loader or paid launch is enabled by the rehearsal. Exact model,
  settings, allowances and spending authority remain to be settled.
- Check the pinned provider interface against the chosen model: API version
  `2026-10-21`, compaction beta `compact-2026-09-04`, at most 16,000 output tokens
  per request, 600-second timeout and optional effort. Refusal is an observable
  outcome; changing a model or settings changes the proposed commission.
- For a later live compaction run, budget the specimen deliberately. It must reach the fixed
  150,000-token context trigger, and cumulative input consumption can be much
  larger than that figure. A short successful probe will not establish
  compaction conformance.
- Preserve every relevant working copy for the new evidence. The revised
  wrapper retains all driver work, exports an archive and leaves the original
  driver containers available through review; the
  [retention item](#retention-of-damaged-originals) is verified for
  `acceptance-03`. A live runner should retain its own originals and
  observations from the outset.

**Keep separate from first-run blockers:** the WSL2 package and native platform
runs, service-wide two-build reproducibility, the broad claim-by-claim coverage
audit, Linux runs of all Cargo tests, toolchain rebuild policy and the public
release schedule remain release work below. They do not automatically have to
finish before a bounded first provider probe. The known help/schema-example
slips should be corrected when they affect the chosen runbook; they are not a
reason to reopen question types. Full C10 coverage remains owed before naming
a model as supported, whatever the first probe shows.

Once the launch commission and procedure are agreed, record the exact bounded
run where its results will be kept. Replace this discussion agenda with the
remaining work after that run is reviewed; do not keep a second account of its
state in the Claude Code plan.

### Haiku framing study after API sanity

Planned follow-on, 2026-10-31. Use inexpensive Haiku trials to find how much
guidance helps the auditor answer the manager's question without repeating
Stewart's harness structure. This follows the first API sanity check; it is
exploration, not an additional gate for that check or proof of five-family
utility. It can use the Messages API path and inform later Claude Code
dogfooding without waiting for that adapter.

Vary instructions and presentation separately:

| | Current presentation | Plain presentation |
| --- | --- | --- |
| Current instructions | Baseline | Presentation change alone |
| Lean instructions | Instruction change alone | Both changes |

Lean instructions retain the commission, evidence/access boundaries and
submission mechanics while removing duplicated coaching. Plain presentation
foregrounds the auditor's own text without automatically added Account,
Observation or Limit headings. Preserve the underlying records, citations,
attribution and custody behavior. Initially keep recording tools unchanged,
along with the question, materials and model/settings within each comparison.

Use a few small commissions with repeated runs. Inspect model-authored prose
separately from the rendered answer: direct engagement with the question,
relevant uncertainty, unnecessary harness discussion, and successful tool use
and submission. Fewer words or qualifications are not automatically better.
Recording-tool categories and preparation notices remain possible influences
to investigate later, rather than changing everything at once.

Record whether the auditor reads the prepared rendering; it is optional and
can influence subsequent edits. For the manager's reading experience alone,
compare both presentations of the same recorded answer without another model
call. Such comparison views are study artifacts, not replacements for sealed
returns. Keep original outputs and conditions available for review.

Needs: a bounded study commission naming the exact Haiku model/settings,
variants, specimens, repetitions and spending/retry limits before execution.
Prompt wording, renderer implementation and trial counts remain to be worked
out then. Findings apply to the tested arrangement; transfer to another model
or runtime remains something to check. No default prompt, renderer or
substantive submission rule changes merely because this study is planned.

### Effort setting: Linux-qualified; live check pending

On 2026-10-31 the user replaced the earlier plan for an Opus default: Stewart
has no effort default of its own. A manager may set `effort:` in the front
matter (INTERFACE 3.2), and Stewart sends it as `output_config.effort` on every
request of that audit, never as text the auditor reads; without it no effort
is sent and the provider's default applies. Prepare refuses unknown level
names; Stewart does not check which levels a model accepts. A provider that
refuses the parameter or a level is reported as it answered, with its message
(INTERFACE 6.5). The crate's tests model provider drift with a declarative
fake (`Surface` in `service/tests/run.rs`): a renamed or removed parameter, a
withdrawn level and a refusal without an error object. The driver has matching
cases (ACCEPTANCE C1 and C9), and four sabotage controls show the checks fire.
A provider that silently ignores the parameter goes unreported; finding that
is out-of-band work, such as the conformance run below.

The Linux checks passed in `acceptance-03` at `faa5579`. Needs: separately
commissioned real-provider compatibility and effort conformance.

### Claim-by-claim coverage check

Check the driver's cases (apparatus/README.md, "Cases") against every claim
and case of ACCEPTANCE for anything not covered. A gap becomes a driver case,
written by the driver's author. Its scope follows the acceptance-testing
discussion. A cold read of the repository (2026-10-31) found sabotage items in
ACCEPTANCE with no control or disposition in INTERFACE Appendix C.2, including
C17's "replace the original failure with a secondary logging error", "blindly
repeat after a reply failure" and "omit a planned partial effect", C18's
"prune on pressure", "treat retained internal bytes as delivered elsewhere"
and "declare a missing archive closed and clean", and C11's "present matching
scans as proof of a source snapshot". Needs: the discussion, the check itself,
and the user's container run if cases are added.

### WSL2 handoff bundle and the user's run

ACCEPTANCE ("Platforms") requires the scripted tier natively on WSL2 from a
handoff package of the same binary, driver and fake provider, with the home on
the WSL filesystem and a destination under `/mnt/`, and a record of the
Windows and WSL versions, distribution, kernel, architecture and filesystem
types. No script builds or runs that package (apparatus/README.md). The driver
takes a release binary and a test build (`--binary`, `--test-binary`); an
`acceptance.sh` run keeps both in its `bin-<arch>/`, so the bundle can carry
the exact bytes a container suite qualified.

A risk: the WSL2 run is native, so the protocol timing gate applies, and its
margin so far is small: a release tool call of 92.542 ms against 100 ms (above). The
gate has not yet been applied on x86_64, where every driver run so far was
emulated. Slower hardware or a slower filesystem could fail it.

Needs: the bundle and its instructions, built after the changes that alter the
binaries or the driver; then the user's WSL2 run, an external dependency on the
user's timing.

### Real-model conformance

ACCEPTANCE's conformance tier (C10) checks procedure, never answer quality:
fixed commissions for the three families, each run three times per model without
an effort setting, plus one run with an effort set, one long enough to compact
and one killed midway and continued. Its apparatus does not exist yet. Before
any model-consuming run the user names the models, their settings (including the
effort for the effort run) and an explicit budget. This plan authorizes no
particular Claude launch, and ACCEPTANCE's run counts are planning quantities,
not authorization to spend. A model named in an example, such as
`claude-opus-5-5`, is not thereby supported; a release lists only the models
that passed the gate.

Verify the provider's current specifications first. They were last checked on
2026-10-31 for compaction; the adapter pins `anthropic-version: 2026-10-21`,
`anthropic-beta: compact-2026-09-04` and handles the
`model_context_window_exceeded` stop reason. The release's TLS path with its
built-in roots is unexercised, and `max_tokens_per_request` and the 600 s
timeout are unqualified (above). Thinking counts toward `max_tokens`, so at a
high effort a response is more likely to end `max_tokens` (which interrupts the
run, visibly and continuably); the effort run shows whether 16,000 still fits.
The compaction specimen must reach the release's fixed 150,000-token trigger
and show an actual provider summary and its usage; a fake summary or a changed
test-only trigger does not establish real-provider conformance.

Needs: the acceptance-testing discussion; the user's models, settings and
budget; the provider check; the real-model apparatus.

### Container runs for recent changes

`acceptance-03` at `faa5579` completes the pending acceptance-suite run:
the driver self-test, effort and provider-error cases, provider compaction and
its stopping case, and the revised working-copy retention all passed on both
architectures. This does not exercise the separate `step2.sh` toolchain suite.

Still pending for `step2.sh`: its required evidence-folder argument, the change
from bare `stewart` to `stewart help`, and the two-build comparison on the
service rather than the old crate skeleton. It refuses to start while
`service/vendor` exists, needs the network, and rebuilds both toolchain images
under the tags other suites use, so a run can change the images (see
"Toolchain image rebuilds"). Needs: the image discussion and the user's
separately scheduled toolchain run.

### Retention of damaged originals

ACCEPTANCE C18 requires witnesses and damaged originals to remain retained
through review. The previous wrapper used the driver's `--keep-work failed`
default and removed the container after copying only the independent evidence;
successful variants' working originals did not reach review.

The wrapper now uses `--keep-work all`, exports the independent witness
separately and archives `/work/tmp` to `work.tar` with its listing, digest and
observation times. Named driver containers remain until review, including if
export fails; the suite records their identities and fails on a failed export.
No driver or service code changed for this retention correction.

Verified in `acceptance-03`: both removal lists are empty, all 226 variant work
directories per architecture are present in the archives, both archive digests
match, and all export steps returned 0. Tar reported three omitted Unix socket
specimens per architecture; the original driver containers remain retained,
observed stopped by the host worker after the suite. Their names are in the
run's `host/driver-<arch>.container`. Review records and host inspections are in
`.scratch/linux-acceptance-prep-01`. Retain these containers and the run evidence
until the user decides their review is complete; no disposal is authorized by
this successful run. The prior run is not retroactively repaired.

### The service's tests on Linux

The service's own cargo tests have run only natively on the development Mac,
where the Linux-only calls use development fallbacks
(`service/src/platform.rs`). On Linux the service has been tested only through
the driver: the container suites build the crate but do not run its tests. A
containerized `cargo test`, offline in the toolchain images with
`STEWART_IT_TMP` on ext4, xfs or btrfs (DEVELOPMENT.md), is an option. Needs:
the acceptance-testing discussion; then a script and the user's container run.

### Toolchain image rebuilds

The Containerfile pins its base image by digest, but `rustup target add` and
`apt-get install musl-tools` fetch when the image is built, so a rebuild can
produce a different image; the built image's digest is the actual pin
(DEVELOPMENT.md). `step2.sh` records the digests. `acceptance.sh` (and the
retired `step3.sh`) recorded the inspection of the images they used, by tag,
and did not compare it with those digests. So far every inspection shows the
digests that `apparatus-01` recorded (apparatus/qualified.md). Needs: the
acceptance-testing discussion.

### Build decisions a reviewer may revisit

Reported to the user and not contested: damaged commissioned material refuses
`run` (`commission_damaged`) rather than running with that material refused;
members damaged after the seal become surrenderable delivery-stage losses, and
a later close retries them if they verify again. Needs: nothing unless the
user or a reviewer reopens one.

### Small fixes found by a cold read

On 2026-10-31 a fresh reader evaluated the repository at `f3ef7da` from the
root documents down, as an outside adopter would, and described the product
correctly. Of its findings, these are small fixes:

- **Specification and help slips.** CONTRACTS' illustrative prepare and submit
  example uses field names INTERFACE 7.6 does not (`prepared_handle`,
  `answer_revision`, a notice key `section`). "Family", "form" and "answer
  family" name the same thing across README, DESIGN, CONTRACTS and
  QUESTION-FORMS. INTERFACE 9 says fault traces run against the release
  binary, but named fault points exist only in the test build. `stewart help`
  says every command except `help` takes `--json`, but `receipt REF --read`
  refuses it. Needs: specification edits, and a service change for the help
  text, which a container run then qualifies.
- **Driver test data.** `apparatus/driver/testdata/README.md` gives the wrong
  validity for the expired certificate and calls the wrong-name and expired
  certificates controls, though only the driver's own TLS self-test uses them.
  Needs: an agent that has not read the implementation (AGENTS.md).
- **Unchecked claims in tests.** The worked examples are said to prepare as
  written, but no test or driver case prepares them. Cargo tests that need
  loopback print SKIPPED and return, so Cargo counts them as passed. Needs: a
  check that prepares the examples, and skips that Cargo reports as skips (for
  example `#[ignore]` with a reason).

### Provider compaction: Linux-qualified; live check pending

On 2026-10-31 the user commissioned keeping the Messages API loop and enabling
provider compaction. The earlier mismatch is resolved in specification and code:
the provider writes the summary, and Stewart resumes from its exact signed
block while preserving original captures, answer records and cumulative limits.
INTERFACE 6.2 specifies the on-demand API, automatically requested at 150,000
context tokens. Its explicit output cap keeps the summary within the existing
request allowance. A failed summary interrupts visibly without executing tools,
silently disabling compaction or changing models. Interrupted placements still
continue in a fresh conversation.

ACCEPTANCE C4 and the independent driver now distinguish actual provider-summary
transitions from the existing simulated memory-loss test of re-entry. Eight new
driver cases cover repeated compaction, byte preservation, retained captures,
usage, limits, notices, refusals, retry and stopping. Four sabotage controls
break the trigger, signed bytes, context replacement and usage accounting.

Native verification is complete. The user's host run in
`.scratch/compaction-host-02` ran both full Cargo configurations, both exit 0,
with no loopback skips. The default run reported 158 library tests and 21 run
integration tests passed; the feature run reported 159 and 31 respectively,
with all other test binaries passing. The feature run's 9 and 26 ignored
fault/sabotage child tests are invoked by their own runner tests (DEVELOPMENT).

The host C4 driver run in `.scratch/compaction-host-01/driver` exited 0:
9 cases selected, 8 passed, 0 failed and 1 skipped (the Linux-only compaction
stopping case); 29,125 checks passed, 0 failed outside controls. All 9 controls
fired, including the four new compaction controls. Its independent witness and
every variant's working copies remain retained with `--keep-work all`.
The driver's self-test reported 281 checks, 279 passed, 0 failed and 2 skipped
in the agent shell (loopback unavailable); `--list` loaded 119 cases.
Formatting, the link check and `git diff --check` passed.

Earlier outputs remain in `.scratch/compaction-native-01`,
`.scratch/compaction-driver-01` and `.scratch/compaction-host-01`. Agent-shell
loopback tests could not run. The first host Cargo runs each found one old
allowance fixture reporting 398,976 output tokens in one response; this now
triggered compaction. The fixture was corrected to use a 16,000-token allowance
and 14,976-token first response, preserving the same 1,024-token remainder and
notice boundary. The second host run above verifies that correction.

Linux qualification is complete in `acceptance-03` at `faa5579`: all eight
provider-compaction cases passed on both architectures, including the Linux
stopping case, with no skipped cases. Needs: separately budgeted real-model
conformance. No model call was made or authorized.
The later Claude Code work is staged in [CLAUDE-CODE-PLAN.md](CLAUDE-CODE-PLAN.md);
human and Codex/OpenAI adapters remain future possibilities (CONTRACTS).

### To discuss: what acceptance testing Stewart needs

Left by the user on 2026-10-31: a discussion of what acceptance testing Stewart
wants and needs. Until it happens, these items wait on it:

- **ACCEPTANCE's tiers.** Its table says the scripted tier runs on "every
  platform, every change" in a "Test image", and the other tiers in an
  "Experiment image". In practice changes land unqualified until the next
  container run, which the user batches; the suites mount binaries into a
  pinned Python image; and no experiment image exists.
- **The endpoint** above: Linux container qualification of the release commit,
  native WSL2 and real-model conformance, and with them the claim-by-claim
  coverage check and the WSL2 bundle.
- **What the suites check:** the service's cargo tests on Linux, whether suites compare the toolchain images
  against recorded digests, and whether `step2.sh` records native or emulated
  execution (the record now gives it as not recorded).
- **The record's outcome rules,** which are conservative by design: a skipped
  case or a native run with the timing gate off fails qualification, and a
  failure on one platform fails the run. The gate's native margin so far is
  92.542 ms against 100 ms in `acceptance-03`.
- **Where the apparatus runs.** The suites need macOS with Apple `container`;
  no route for a Linux host is documented.

## Outside this plan

CONTRACTS ("Declined and deferred scope") lists what the first release
declines or defers. Person transport, hidden priors, a larger family
catalogue, elaborate module composition, family-admission research and
whether read-only inquiry is intellectually useful are later work only if
separately commissioned. TRANSITION-PLAN.md at `aafcb57` abandoned the earlier
development programs (the five-stage program, alternative workspace and
history arrangements, a separate custody-first stage, unrun Python parity
comparisons and the orientation trial); their applicable identity, custody,
interruption, expression and platform cases are in CONTRACTS and ACCEPTANCE.
None of these is a prerequisite of this release.
