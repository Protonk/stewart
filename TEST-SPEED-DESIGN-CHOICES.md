# Test speed: design choices for implementation

Status: options, not decisions. Written for the agent who inherits
`TEST-SPEED-PLAN.md` and its findings and moves to implementation. Each
section states the choice, what the evidence says, a recommendation, and what
pins the current behavior. Where the plan's work packages would change a
number here, the findings win. The three questions the user asked are
answered in sections 5, 6 and 7.

Orientation. Nearly all suite time is git process spawns: about 100 per test
at 17 ms each on this Mac, split between fixtures (9 per test), the tool's
operations (41 in `prepare()`, 36 in `collect()`, with a third of each
duplicated), and CLI spawns that repeat the operation's git behind 0.18 s of
interpreter startup. Four tests account for 184 s; everything else is a long
tail. Any plan that does not reduce either the cost per spawn or the number
of spawns is working on the margins.

## 1. Which git binary the harness runs

Choice: leave `git` resolution to PATH, or have `scripts/check.py` resolve a
non-shim binary for the test environment.

Evidence: Apple's `/usr/bin/git` is a shim that costs 17 ms per spawn versus
7 ms for the binary it execs, found with `xcrun --find git`. Three git-heavy
tests halved through the real harness. Expected effect on the suite: 34
minutes to roughly 18, as an extrapolation from spawn counts.

Recommendation: the check script builds the pytest environment already, so on
macOS, when `shutil.which("git")` resolves to the shim, it should prepend the
directory from `xcrun --find git` to PATH for the subprocesses and print the
binary it chose. Keep a `--git-dir` override for other machines and for the
comparison runs. This is harness environment, not tool logic; the tool keeps
invoking `git` by name. Homebrew git should perform the same but was not
measured.

Pinned by: nothing. `tests/acceptance.py` names `/usr/bin/git` explicitly but
is not collected by pytest.

## 2. The two tests that walk `.scratch`

Choice: fix the walkers, prune the directory, or both.

Evidence: 81 s and 58 s today, growing with every retained run. A pruned walk
in `source_python` takes 0.04 s. Hatchling prunes directories named in the
sdist `exclude` before descending.

Recommendation: both. Prune excluded top-level names before `rglob` in
`tests/test_authority.py`, and add `.scratch` and `.venv` to the sdist
`exclude` in `pyproject.toml`, keeping `ignore-vcs = true` because the
distribution test's point is that the build needs no Git. The directory
cleanup is the user's decision, covered in section 7. The firing control is
in the plan's WP5.

Pinned by: `test_sdist_builds_same_wheel_without_git_or_network` asserts the
sdist member set; an `exclude` of directories that were never included does
not change it.

## 3. Sharding inside the check script

Choice: pytest-xdist, a shard loop in `scripts/check.py`, or nothing.

Evidence: ten cores, of which four are performance cores, and other sessions
keep the load near 4 to 5. The conftest's `plugin_origins` assertion admits
only pytest's own plugins and the local conftest, and the wheelhouse is
hash-locked, so xdist means two new locked wheels plus a widened assertion.
The `serial` marker is declared and unused. Each test already has a private
`tmp_path`, HOME and manager home.

Recommendation: a shard loop in the check script. Split test files across N
pytest subprocesses, packed by the previous receipt's durations when one is
given and round-robin otherwise, each with its own `--basetemp` under the
artifacts directory, then merge the receipts: `collected` and `selected` as
sums, `nodes` and `durations` as unions, `exit_status` as the maximum. Add
`--workers`, default 1 so nothing changes unless asked, and document 3 as the
working number on a shared machine. Files carrying `serial` go to shard 0.
Budgets apply per shard. The plugin population is untouched. Once this
exists, run the two interpreters one after another, never together.

Pinned by: `tests/test_runner.py` lines 58 to 60 and
`tests/test_foundations.py` lines 430 to 432 assert the receipt's `selected`,
`collected`, `collected_nodes`, `deselected`, `outcomes`, `durations` and
`nodes`. The merged receipt must keep those meanings, and the plan's
independence audit must come back clean first.

## 4. Deduplicating git inside operations

Choice: leave the tool alone, or remove repeated identical git calls within a
single operation.

Evidence: `checkout_identity` costs four spawns and runs three times per
`prepare()` and twice per `collect()`; the same commit is resolved five times
per `prepare()`; `status --porcelain` runs three times per `collect()`. About
35 to 40% of in-process git is repeats of a query the same operation already
made.

Recommendation: defer until `rehome` has merged, because the call sites are in
`_repository.py`, `prepare.py`, `collect.py` and `assignment.py`. When taken
up, pass the identity dictionary down from the operation that first verified
it rather than adding a cache with a lifetime, so that re-validation at use
stays where the custody rules put it and nothing survives across operations.
Before changing anything, add a regression guard: a test per operation that
counts spawns through the same wrapper the plan's WP1 used and asserts an
upper bound. That turns profligacy into a measured contract and catches the
next accidental triple lookup.

Pinned by: the custody rules in `AGENTS.md` on revalidating frozen identities
at use. A within-operation pass-down does not weaken them; a cross-operation
cache would.

## 5. Should fixtures be centralized?

Short answer: centralize the invocation layer, not the state. For speed it is
a minor lever; for the rest of this work it is the enabling one.

What exists: `conftest.py` holds `run_cmd`, the autouse private HOME, the
`checkout` and `project_repo` fixtures and `installation`;
`stewart_support.py` holds `make_checkout`, `prepared_session`,
`experiment_checkout` and `prepared_experiment`. On top of that, about ten
test files define their own CLI or git wrapper: `_cli` in
`test_closeout_doubt.py`, `test_exit_codes.py`, `test_request_keys.py` and
`test_resources.py`; `_run` in `test_stewart_cli.py` and
`test_stewart_experiment.py`; `cli_base` in `test_stewart.py`; `cli_args` in
`test_stewart_inputs.py`; a `Stewart` class and `_git` in `test_journey.py`;
`run_block` in `test_stewart_launch_profile.py`. They differ in how they parse
the JSON envelope, which exit codes they allow, and whether they pass `-I -B`.

What speed it buys: fixture work is about 9 git spawns per test, roughly 150 s
of the suite, 60 s once git is the direct binary. Building the checkout once
per session and copying the directory into each test's `tmp_path` would save
most of that. Git repositories without worktrees are relocatable, and the
template's HEAD commit is fixed once, so `meta["target_commit"]` stays
correct. That is about a minute. Nothing larger is available from fixtures
because the expensive spawns happen inside the operations, not around them.

What it buys otherwise: one `stewart` fixture replacing the ten wrappers
gives a single place to choose the git binary, count spawns, enforce
timeouts, decode the envelope with `loads_control`, and declare allowed exit
codes. The plan's WP2 and WP3 signatures become reliable when every test
calls the tool the same way, and a spawn budget per operation can be asserted
in one fixture rather than ten.

What not to do: do not share prepared sessions across tests at module or
session scope. Nearly every test mutates its repository, the conftest's first
line promises test independence, and the custody semantics under test are
about what one operation sees. A class-scoped prepared session shared by a
handful of read-only `status` and `discover` assertions is the only safe form,
and it is worth doing only where WP2 shows setup dominating.

Sequencing: a mechanical refactor across fifteen files will collide with
`rehome` wherever it touches `test_resource_safety.py` or the `test_close*`
files. Do it per file after `rehome` merges, or start with the files `rehome`
has not touched.

## 6. Should tests be deleted wholesale, and how?

Short answer: some, but for maintainability more than speed, and never on
suspicion. Deleting a fifth of the tests saves a fifth of the time at best;
the git levers save more and lose nothing. Treat deletion as a separate
decision from speed, made on evidence, one cluster at a time.

Why there are candidates: several files are layered by review cycle rather
than by subject. `test_close.py` has 65 tests, `test_close_regressions.py` 17
and `test_closeout_doubt.py` 21; `test_stewart_status.py` has 38 and
`test_exit_codes.py` 34; the request-key, request-binding and action-binding
files overlap by name. Each repair added tests and retired none. The 966 tests
occupy 17,855 lines against 14,939 lines of source.

Criteria that justify removal:

- No unique failure mode. Under every mutation tried in the plan's WP3, the
  test fired only when a cheaper retained test also fired. This is the main
  criterion and the only one that is evidence rather than taste.
- A parametrized case that does not differ in the measured property from a
  sibling case. The sweep stays; the duplicate parameter goes.
- A CLI subprocess test whose subject is API behavior already covered through
  the API, where the CLI contract itself (argv, exit code, envelope) has its
  own test.

Criteria that do not justify removal:

- The test is slow. Slowness is a reason to fix the test's cost, not its
  existence.
- The test checks the harness or the measurement discipline
  (`test_foundations.py`, `test_runner.py`, `test_authority.py`). Those exist
  because the project values them; make them cheap instead.
- The test is the only one asserting a reason identifier. The identifiers are
  part of the JSON contract and 24 of 153 are already asserted nowhere.
- The test is one leg of a firing-control, differing-case, invariance-case
  triplet. Fold the triplet into one test with shared setup if the setup
  dominates; do not drop a leg.

Process:

1. Take clusters and mutation results from WP3; do not generate new
   candidates during implementation.
2. For each candidate, name the retained test that covers the same failure and
   the mutation that showed it, in the commit message.
3. One commit per cluster, so any cluster can be reverted alone.
4. Prefer folding to deleting where the tests share a prepared session and
   differ only in assertions.
5. Present the list to the user before deleting anything. The user decides.
6. After each cluster, re-run the cluster's files with the mutation that
   justified it and confirm something still fires.

## 7. What to spin up, test, and throw away without logging

Short answer: keep the run's receipt and the trees of failing tests; throw
away the trees of passing tests. Re-running one test costs seconds, so an
archive of its passing-state scratch tree is reproducible at any time and
holds no evidence the receipt lacks. The custody rules in `AGENTS.md` govern
audits, not the test suite's own output; retaining every test's checkout as
if it were a receipt is the conflation to undo.

What one full run retains today: 3.4 GB and 2414 entries, spread thinly over
about 1200 test directories, each holding a checkout, a worktree, a private
HOME with a gitconfig, `commands/NNNN/` records with both streams, and for
some tests a staged runtime copy or a nested venv. The largest single
directory is 62 MB. About fifteen such runs are what the 36 GB in the main
checkout's `.scratch` is.

What is not reproducible by re-running, and so must be kept:

- The receipt: `durations`, `outcomes`, `node_outcomes`, `collected_nodes`,
  `plugins`, the wheel digest, the interpreter. About 580 KB.
- The transcript `.log` and the retained wheel under `-dist`. About 1 MB.
- A failing or erroring test's tree, because the failure may not recur and
  its `commands/` records show what the tool said at the time.
- Timings taken as evidence for a comparison, which belong in the receipt
  anyway.

What is reproducible and should go after a passing test: its checkout,
worktree, HOME, `commands/` records and staged copies. For the runner test,
its three nested venvs.

Mechanism: set `tmp_path_retention_policy = "failed"` in the pytest options
in `pyproject.toml`; pytest 7.4.3 honors it. The private HOME that
`private_manager_storage` creates beside `tmp_path` is outside that policy,
so its fixture must remove the directory on teardown when the test passed,
using the outcome the conftest's `pytest_runtest_makereport` already sees.
Keep `--basetemp` so failures land in a known place. Give the check script
`--keep-artifacts all|failed|none`, default `failed`, with `all` for the rare
run whose scratch trees someone wants to read. Expected result: tens of
megabytes per run instead of gigabytes, and the two walkers in section 2 stop
degrading even before their fix.

The existing pile: the main checkout's retained runs are the user's evidence
for past review cycles and the user's to delete. A reasonable policy is to
keep every run's receipt, log and wheel, and keep artifact directories only
for runs still under review.

Pinned by: nothing asserts on the retained trees. `tests/test_runner.py` and
`tests/test_foundations.py` assert on the receipt, which stays.

## 8. Smaller choices

- Fix the duplicate collection in `scripts/check.py`: when a positional test
  path is given, do not also append the suite's `tests` directory, or resolve
  the given path into the staged suite and pass only that.
- Make the tiers mean something: mark the authority, distribution and runner
  tests `heavy` so `-m "not heavy"` is a usable developer tier, and let
  `--fast` select it instead of the 25 `smoke` tests.
- One interpreter in the developer loop; both interpreters at the gate, one
  after the other once sharding exists.
- CLI spawns cost 0.18 s of startup each, 585 per run. Keep subprocess tests
  where the CLI contract is the subject and let the rest use `stewart.api`.
  This is a small lever on its own and follows naturally from section 5.
- Add the spawn budget tests from section 4 before any of the tool's git
  calls change, so the guard exists while `rehome` is still landing.
