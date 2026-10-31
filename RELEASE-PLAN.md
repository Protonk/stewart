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

## Current account (2026-10-30)

[apparatus/qualified.md](apparatus/qualified.md) records what the container
suites have shown: each run's source commit, counts, digests and outcome, and,
through `python3 -I -B apparatus/qualified.py check`, the changes since each
run's source commit. Its front is `acceptance-02` (`apparatus/acceptance.sh` at
`dc85948`) and `apparatus-01` (`apparatus/step2.sh` at `47e5a59`), both
qualified on both architectures. No run has consumed a model. The earlier runs,
`acceptance-01` and `step3-01` to `-03`, are superseded; their account is in
TRANSITION-PLAN.md at `aafcb57`. Run records are under `.scratch/` on the
development Mac, which Git ignores, and stay while they are on the front,
pinned or cited (DEVELOPMENT.md, "Evidence and retention"). This section keeps
what the record does not hold.

`apparatus-01` built the crate skeleton of `47e5a59`, which only linked the
release dependency set, not the service. Its static and reproducibility checks
had no firing controls. `acceptance.sh` adds one for the static check (a glibc
build must fail it) and shows that `cmp` tells the release and test binaries
apart, but the two-build comparison runs only in `step2.sh`. In `acceptance-02`
the 66 sabotage control variants cover all 62 controls of INTERFACE Appendix
C.2.

The protocol timing gate, `c9.protocol-timing-gate`, requires every gated
protocol call, as the fake provider measures it, to take under 100 ms; a
full-material search is not gated. It passed natively on aarch64 in
`acceptance-02` with a worst call of 95.2 ms, a `record_observation` call in
`c3.limits`. Under Rosetta on x86_64
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

### Effort setting: built, unqualified

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

Needs: the user's container run of `acceptance.sh` ("Container runs for
recent changes").

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
margin so far is small: a worst call of 95.2 ms against 100 ms (above). The
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

These changes have not run in a container:

- `aafcb57` changed nine apparatus code files and `apparatus/README.md`
  (`git show --stat aafcb57 -- apparatus`). Two changed behavior:
  `apparatus/step2.sh` and `apparatus/container/inner-build.sh` run
  `stewart help` where they ran bare `stewart`, because the binary now exits 2
  (usage, INTERFACE 1.6) without arguments. `apparatus/driver/answer_witness.py`
  changed its self-test data to follow corrected specification examples; the
  self-test passes natively (246/246, not evidence). The other six changed in
  comments or docstrings only: `acceptance.sh`, `driver/cases_run.py`,
  `driver/stewart_driver.py`, and three files since retired with `step3.sh`.
- The two suites take their evidence folder as a required argument (2026-10-30).
- The effort setting and the provider's error message in run results
  (2026-10-31): the service, the specification and the driver's cases and
  controls ("Effort setting", above).
- Provider compaction (2026-10-31): summary requests, signed-summary resumption,
  retained request reconstruction, iteration usage, failure paths and four
  controls ("Provider compaction", below).

The next `acceptance.sh` runs the self-test in a container. `step2.sh` refuses
to start while `service/vendor` exists, needs the network, and rebuilds both
toolchain images under the tags the other suites use, so a run can change the
images (see "Toolchain image rebuilds"). It would also repeat the two-build
comparison, this time on the service. Needs: the user's container runs;
`step2.sh` waits on the image question, which the acceptance-testing
discussion takes up.

### Retention of damaged originals

ACCEPTANCE C18 requires witnesses and damaged originals to remain retained
through review. The driver keeps its witness in the evidence folder, but
with its default `--keep-work failed` it removes a variant's work (the
archives, folders and homes a case works on) once the variant has served its
purpose: it passed, or its control fired. The container suites run it with
that default, in a work directory on the container's own disk that is
discarded with the container, and copy out only the evidence folder. A passing
variant's damaged originals therefore do not reach review. `--keep-work all`
keeps every variant's work, but in the suites that work would still be
discarded unless copied out. Needs: the acceptance-testing discussion, then a
container run.

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

### Provider compaction: built, unqualified

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

Needs: the user's next scheduled `acceptance.sh` container run, including the
Linux stopping case, and separately budgeted real-model conformance. Native
iteration does not qualify the change. No model call was made or authorized.
Claude Code as a peer runtime is the next discussion; human and Codex/OpenAI
adapters remain future possibilities (CONTRACTS).

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
- **What the suites keep and check:** damaged originals for review (C18), the
  service's cargo tests on Linux, whether suites compare the toolchain images
  against recorded digests, and whether `step2.sh` records native or emulated
  execution (the record now gives it as not recorded).
- **The record's outcome rules,** which are conservative by design: a skipped
  case or a native run with the timing gate off fails qualification, and a
  failure on one platform fails the run. The gate's native margin so far is
  95.2 ms against 100 ms.
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
