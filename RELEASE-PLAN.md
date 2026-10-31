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
- The Opus effort default, which is not implemented.

## Work items

Each item says what it needs. Container suites are host scripts that the user
runs (DEVELOPMENT.md, "Container suites"). Exact process exclusion and
stopping, crash publication, filesystem qualifications, front-matter encoding,
numerical response budgets and schema names are specification and build work,
not reasons to reopen settled manager or answer policy. If qualification shows
the design cannot support a promise, bring that specific unmet promise to the
user.

### Opus effort default: decided, not implemented

The user decided that requests to Opus models carry effort `high` by default.
Today the arrangement pins `request_extra` as `{}` and the release's allowlist
is empty (INTERFACE 6.2), so requests set no effort and Opus 5.5 runs at its
API default, `medium`. Implementing it changes the pinned arrangement bytes and
the request shape: INTERFACE 6.2 (the allowlist and how the arrangement pins
effort per model), the arrangement and its readable form, the service's tests,
and the driver's request witness (C1), which the driver's author changes from
the amended INTERFACE text. Conformance runs use the release's default effort
(ACCEPTANCE), so this comes before them.

Before it becomes contract text, the user settles:

- What counts as an Opus model: for example every model ID beginning
  `claude-opus-`, including models whose provider default is already `high`.
- Whether "default" means a fixed release setting or implies a manager
  override. An override would change the `question/1` grammar and what
  managers can express.
- How the allowlist admits it. Effort is a member of the top-level
  `output_config` object, and admitting `output_config` would also admit its
  other members, such as a task budget, so INTERFACE 6.2's allowlist would have
  to be value-level.
- Whether the arrangement's version (`stewart.arrangement/1`) changes.
- That thinking at `high` effort counts toward `max_tokens_per_request`
  (16,000), and whether that limit still fits.

Needs: those decisions, a check of the provider's current specification of
effort, the implementation, and the user's container run.

### Claim-by-claim coverage check

Check the driver's cases (apparatus/README.md, "Cases") against every claim
and case of ACCEPTANCE for anything not covered. A gap becomes a driver case,
written by the driver's author. Needs: the check itself; the user's container
run if cases are added.

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
fixed commissions for the three families, each run three times per model at
the release's default effort, plus one run with compaction forced and one
killed midway and continued. Its apparatus does not exist yet. Before any
model-consuming run the user names the models, their settings (including the
effort default) and an explicit budget. This plan authorizes no particular
Claude launch, and ACCEPTANCE's run counts are planning quantities, not
authorization to spend. A model named in an example, such as
`claude-opus-5-5`, is not thereby supported; a release lists only the models
that passed the gate.

Verify the provider's current specifications first. They were last checked on
2026-10-30; the adapter pins `anthropic-version: 2026-10-21` and handles the
`model_context_window_exceeded` stop reason. The release's TLS path with its
built-in roots is unexercised, and `max_tokens_per_request` and the 600 s
timeout are unqualified (above). ACCEPTANCE asks for compaction forced
"through a low compaction trigger or a run long enough to reach it", while the
adapter sends no `anthropic-beta` header (INTERFACE 6.1) and may enable no
provider-side context management (6.2); how a conformance run forces
compaction is not yet specified.

Needs: the user's models, settings and budget; the provider check; the
real-model apparatus; the effort default.

### Container runs for today's script changes

These changes to the apparatus have not run in a container:

- `aafcb57` changed nine apparatus code files and `apparatus/README.md`
  (`git show --stat aafcb57 -- apparatus`). Two changed behavior:
  `apparatus/step2.sh` and `apparatus/container/inner-build.sh` run
  `stewart help` where they ran bare `stewart`, because the binary now exits 2
  (usage, INTERFACE 1.6) without arguments. `apparatus/driver/answer_witness.py`
  changed its self-test data to follow corrected specification examples; the
  self-test passes natively (246/246, not evidence). The other six,
  `acceptance.sh`, `step3.sh`, `container/step3-inner-build.sh`,
  `container/step3-inner-driver.sh`, `driver/cases_run.py` and
  `driver/stewart_driver.py`, changed in comments or docstrings only.
- The two suites take their evidence folder as a required argument (2026-10-30).

The next `acceptance.sh` runs the self-test in a container. `step2.sh` refuses
to start while `service/vendor` exists, needs the network, and rebuilds both
toolchain images under the tags the other suites use, so a run can change the
images (see "Toolchain image rebuilds"). It would also repeat the two-build
comparison, this time on the service. Needs: a decision on the images and
`service/vendor` before `step2.sh` runs, and the user's container runs.

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
discarded unless copied out. Needs: a decision on what the suites keep, and a
container run.

### The service's tests on Linux

The service's own cargo tests have run only natively on the development Mac,
where the Linux-only calls use development fallbacks
(`service/src/platform.rs`). On Linux the service has been tested only through
the driver: the container suites build the crate but do not run its tests. A
containerized `cargo test`, offline in the toolchain images with
`STEWART_IT_TMP` on ext4, xfs or btrfs (DEVELOPMENT.md), is an option. Needs:
a decision whether to add it, a script, and the user's container run.

### Toolchain image rebuilds

The Containerfile pins its base image by digest, but `rustup target add` and
`apt-get install musl-tools` fetch when the image is built, so a rebuild can
produce a different image; the built image's digest is the actual pin
(DEVELOPMENT.md). `step2.sh` records the digests. `acceptance.sh` (and
`step3.sh`, retired below) recorded the inspection of the images they used, by
tag, and did not compare it with those digests. So far every inspection shows the digests
that `apparatus-01` recorded (apparatus/qualified.md). Needs: a decision
whether later suites compare against a recorded digest, and where that pin is
kept.

### `step3.sh`

Retired on 2026-10-30, with `container/step3-inner-build.sh` and
`container/step3-inner-driver.sh`: `acceptance.sh` makes every check it made,
and the qualification record has no suite for it, so a change to it could never
be qualified. Git history holds the scripts (last at `aafcb57`).

### Qualification record: built, with open points

The record is built: `apparatus/qualified.py`, `qualified.json` and
`qualified.md` (DEVELOPMENT.md, "Evidence and retention"). Its open points:

- **Drift baseline.** `check` measures drift since each front run against the
  working tree, uncommitted and untracked files included. Needs: a decision
  whether to measure against `HEAD` instead.
- **Host architecture in `step2.sh`.** `step2.sh` does not record whether each
  platform ran natively or under emulation, so the record's toolchain entries
  give execution as not recorded. Needs: a decision whether `step2.sh` should
  record it, and the user's container run if it changes.
- **Conservative outcome rules.** By design, a skipped case or a native run
  with the timing gate off fails qualification, and a failure on one platform
  fails the run, so the front keeps the last qualified run on the other
  platform too. Needs: nothing unless the user revisits them.

### The retired Python tool's independent resources

Disposition proposed, awaiting the user. The tool's state in `.git/stewart/`
shows all five of its audits closed, no open session and an outcome for each
of its nine requests, so no undertaking is live. It records 24 independent
resources (12 exports, 6 retained copies, 5 worktrees and 1 branch), none
claimed or disposed. By the `kind` and intended location in each
`CREATE.json`:

- 19 name places in the separate `stewart-fieldwork` directory, which was not
  read for this account: 10 exports, 4 retained copies and the 5 worktrees.
- 4 name files that left the tree with the historical records and now exist
  only in Git history (at `267aaf0`): the return manifests under
  `reports/opus-preparation-audit-2026-10-27/` and
  `reports/commission-self-audit-2026-10-27/` (2 exports), and the reports
  under `audits/opus-preparation/` and `audits/commission-recall/` (2 retained
  copies).
- 1 is a branch of this repository, `refs/heads/fieldwork-run-003`, made for
  one of the worktrees; it names no path.

TRANSITION-PLAN.md at `aafcb57` counted 11 exports, 6 retained copies, 6
worktrees and 1 branch, with twenty naming places in `stewart-fieldwork`, and
an earlier statement to the user in chat on 2026-10-30 also gave twenty, with
different counts by kind. The records govern. On 2026-10-30, `.git/worktrees/`
held none of the administration directories the five worktree records name
(`manager`, `manager1`, `manager2`, `manager3`, `manager-004`), and
`refs/heads/fieldwork-run-003` did not exist. The proposed disposition: every
resource stays where it is, undisposed, with its records in `.git/stewart/`
untouched, and no tool removes it (CONTRACTS, "Versions and legacy
obligations"). Needs: the user's decision.

### Remote branches

GitHub carries `click-integration` and `review/1-rehome-close` besides `main`.
By the local remote-tracking refs, `click-integration` is not merged into
`main`, and the tip of `review/1-rehome-close` is an ancestor of `main`. The
local annotated tag `archive/2026-10-23/click-integration` points at
`56686e9`, the current `origin/click-integration` tip, so deleting the remote
branch loses nothing locally. The annotated tag
`archive/2026-10-23/fieldwork-run-003` preserves the branch that the retired
Python tool's branch resource named, `refs/heads/fieldwork-run-003`: the
resource recorded its creation at `2c4c706`, and the tag's commit, `cab483a`,
descends from it. Deleting either remote branch is an outward-facing change.
Needs: the user's decision.

### Fat-LTO `getrandom`: closed locally

The user closed this item locally on 2026-10-30. In the fat-LTO static musl
release build, a library's call to a libc function that std also declares weak
can link to nothing; Stewart's `libc::getrandom` call did (a silent no-op on
aarch64, SIGSEGV on x86_64). The mechanism is confirmed on both architectures
(`.scratch/fat-lto-getrandom-04/RESULT.md`; the source account is
`.scratch/fat-lto-getrandom-02/ANALYSIS.md`, the LLVM step
`.scratch/fat-lto-getrandom-03/RESULT.md` and the original observations
`.scratch/fat-lto-getrandom-01/REPORT.md`). Stewart calls the raw syscall
(`service/src/platform.rs`), and the crate docs (`service/src/lib.rs`) state
the rule for future calls and the functions it covers. No further local work:
a release-build guard, thin LTO and Riker's further suggestions (a byte-count
check, `-Wl,--require-defined`, a release sentinel test) are not pursued.

The upstream report is open. It is with the user, who decides its routing
after a Claude web agent's advice; there is no AI-written public issue. The
brief is `.scratch/fat-lto-getrandom-02/WEB-AGENT-REQUEST.md`. The evidence
the report rests on is `.scratch/fat-lto-getrandom-01` to
`.scratch/fat-lto-getrandom-04` and the Linux diagnostics that located the
cause, `.scratch/diag-linux-01`, `.scratch/diag-linux-02` and
`.scratch/diag-linux-03`: every Linux-only call worked in isolation; only the
fat-LTO release build failed, and in it musl's `getrandom` was absent from the
binary while thin LTO linked it.
Needs: the user's routing decision.

### Build decisions a reviewer may revisit

Reported to the user and not contested: damaged commissioned material refuses
`run` (`commission_damaged`) rather than running with that material refused;
members damaged after the seal become surrenderable delivery-stage losses, and
a later close retries them if they verify again. Needs: nothing unless the
user or a reviewer reopens one.

### Loopback development setting

Loopback listening was enabled on the user's machine for native iteration;
natively, the driver skips the cases that need the fake provider where
loopback listening is not permitted (DEVELOPMENT.md). The container suites do
not need it. Needs: the user's decision whether to keep it.

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
