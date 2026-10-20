# Test speed: design choices for implementation

Status: companion to `TEST-SPEED-PLAN.md`. The correctness and evidence
requirements below constrain implementation; mechanisms and savings remain
proposals to verify. The branch includes `main` at `764d97e` and no longer
waits for `rehome`. The historical figures describe 966 tests; the latest
repair validation collected 992. New comparisons must identify their own
population and source, including test/harness changes outside the wheel.

Git process startup is a promising large cost: the old sample measured six
checkout spawns, three prompt-commit spawns, 41 in `prepare()` and 36 in
`collect()`. Repeated argv identifies candidates, not redundant checks.
The recorded runs had competing load, so neither a complete attribution of
suite time nor a suite-wide speedup is established.

Sequence: Git executable selection, directory pruning and collection repair
(plan WP1), bounded retention (WP2), then reassess (WP3). Sharding (WP4) and
runtime observation reuse (WP5) need evidence that the remaining cost warrants
them. Exhaustive decomposition and test removal are not entry requirements;
consolidation can be a separate follow-up (WP6).

## 1. Which git binary the harness runs

Choice: leave `git` resolution to PATH, or have `scripts/check.py` resolve a
non-shim binary for the test environment.

Evidence: the historical sample measured about 17 ms per spawn through
Apple's `/usr/bin/git` shim versus 7 ms through the binary found with
`xcrun --find git`. Three Git-heavy tests improved substantially. The old
34-to-18-minute suite estimate was an extrapolation from spawn counts, not a
measured result. Repeat interleaved comparisons before relying on it.

Recommendation: the check script builds the pytest environment already, so on
macOS, when `shutil.which("git")` resolves to the shim, it should prepend the
directory from `xcrun --find git` to PATH for the subprocesses after verifying
the candidate. Keep an explicit executable override for comparisons; choose
a name such as `--git-executable` to avoid confusion with Git's `--git-dir`.
Preserve normal PATH selection on other platforms and when no usable direct
binary is available. Record the requested choice, actual executable and
version, and any fallback. This is harness environment; Stewart continues
invoking `git` by name. Homebrew Git was not measured.

Pinned by: nothing. `tests/acceptance.py` names `/usr/bin/git` explicitly but
is not collected by pytest.

## 2. The two tests that walk `.scratch`

Choice: prune traversal, limit future artifact growth, or both.

Evidence: 81 s and 58 s in the historical run. A pruned walk
in `source_python` takes 0.04 s. Hatchling prunes directories named in the
sdist `exclude` before descending.

Recommendation: both. Prune excluded top-level names before `rglob` in
`tests/test_authority.py`, and add `.scratch` and `.venv` to the sdist
`exclude` in `pyproject.toml`, keeping `ignore-vcs = true` because the
distribution test's point is that the build needs no Git. Limit future
artifact growth through section 7; cleanup of historical artifacts remains
the user's decision. The firing comparison, clean-tree invariance and
unchanged file/member sets are in plan WP1. Retention limits future growth but does not replace
correct pruning.

Pinned by: `test_sdist_builds_same_wheel_without_git_or_network` asserts the
sdist member set; an `exclude` of directories that were never included does
not change it.

## 3. Sharding inside the check script

Choice: pytest-xdist, a shard loop in `scripts/check.py`, or nothing.

Evidence: the original machine had ten cores, four of them performance
cores, with competing load. That is no basis for a fixed worker count. The
conftest's `plugin_origins` assertion admits only pytest's own plugins and
the local conftest, and the wheelhouse is hash-locked, so xdist would require
new locked dependencies plus a widened assertion.
The `serial` marker is declared and unused. Each test already has a private
`tmp_path`, HOME and manager home.

Recommendation, if WP3 warrants it: prefer an opt-in shard loop, with
`--workers` defaulting to one, after WP4's independence audit. Assign files
using compatible duration evidence or a deterministic fallback. Each worker
needs its own result path, streams and `--basetemp`; no worker overwrites the
aggregate or another worker's evidence. Measure useful worker counts under
comparable load. Run interpreters sequentially.

Establish the invocation's expected collected and selected node sets before
dispatch. Workers must execute each selected node exactly once, or identify
it as incomplete. Reject duplicate, missing and foreign nodes before merging
maps or counts; a union can conceal duplicates. Preserve collection and
deselection meanings even if workers receive already-selected node IDs.
Document aggregate outcome/exit semantics and keep every worker's raw result;
numeric maximum of exit codes alone cannot explain collection errors,
interruptions, missing/stale receipts or an incomplete worker.

A planned empty shard may be omitted explicitly; an unexpectedly empty
worker or whole selection must not silently pass. Tests marked `serial` need
an exclusive phase after all concurrent workers have stopped, or before any
start. Assigning them to shard zero does not provide exclusivity. Preserve
the per-test phase budget and the end-to-end total budget, including all
setup and orchestration. Optional worker limits are additional.

Pinned by: collection/outcome recording in `tests/conftest.py`, receipt
assertions in `tests/test_foundations.py`, and budget/selection checks in
`tests/test_runner.py`. Add focused tests for membership corruption, worker
failure/interruption, serial exclusivity and aggregate budgets before relying
on parallel results. Preserve the plugin boundary and installed-wheel checks.

## 4. Deduplicating git inside operations

Choice: retain fresh Git observations, or reuse a verified observation where
the custody boundary permits it.

Evidence: historical `prepare()` repeated the identity quartet three times
and resolved the same commit five times; `collect()` repeated several
identity, status and diff commands. The raw argv-only grouping did not
establish equivalent cwd, inputs or observation boundaries. The calls are
candidates to inspect, not a measured fraction that can safely be removed.

Recommendation: investigate only the operations implicated after the early
fixes. For each proposed reuse, record the original check, its later consumer,
intervening side effects or possible external changes, and why the consumer
does not require a fresh observation. Passing an identity dictionary down
within one call can still skip required revalidation. Keep repeated calls
where that boundary matters; do not introduce a cross-operation cache.

WP5's instrumentation must retain raw argv, cwd, relevant configuration and
inputs, phase and call sites. Bound spawn counts for stable representative
paths before changing them, but pair performance checks with regressions that
change identity, contents or uses between checking and acting and with
unchanged controls. A low spawn count cannot establish safe custody.

Pinned by: `AGENTS.md` requires revalidation at use, including frozen resource
identity/inventory and uncertain dependencies. Preserve the current
`test_resource_safety.py` and close/request-binding regression behaviors.

## 5. Should fixtures be centralized?

Centralize invocation mechanics while keeping state independent. This can
improve consistency even where the measured speed benefit is small.

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

Potential saving: the historical checkout and prompt setup measured nine
Git spawns together. Extrapolating that to every test is only an estimate;
actual fixture use varies. A pristine checkout template copied into each
test's own directory might save some of this cost. Measure copying, verify
that no mutable state is shared, and check paths/configuration and commit
identity before adopting it. Do not treat every Git repository as relocatable
merely because it currently has no linked worktrees.

What it buys otherwise: one `stewart` fixture replacing the ten wrappers
gives a single place to observe the harness's Git selection, count spawns,
enforce timeouts, decode the envelope with `loads_control`, and declare
allowed exit codes. It also makes later cost and overlap analysis easier. Preserve each
caller's intended allowed exits, envelope assertions and isolated startup;
centralizing must not silently broaden successful outcomes.

What not to do: do not share prepared sessions across tests at module or
session scope. Nearly every test mutates its repository, the conftest's first
line promises test independence, and the custody semantics under test are
about what one operation sees. Even nominally read-only assertions need an
independence argument before sharing setup. Prefer independent copies; do not
introduce a shared prepared session as part of a mechanical helper refactor.

Sequencing: `rehome` is merged. Refactor per file when it supports measured
work; avoid a suite-wide prerequisite before the narrow harness fixes.

## 6. Should tests be deleted wholesale, and how?

Treat deletion as a separate maintainability decision, made on evidence one
cluster at a time. Removing a fraction of tests does not imply the same
fraction of elapsed time. No deletion is required for the initial speed work.

Where to look: `test_close.py`, `test_close_regressions.py` and
`test_closeout_doubt.py`; status/exit-code tests; and the request-key,
request-binding and action-binding families. Similar names or a review-cycle
history suggest places to inspect, not equivalent coverage. Use current
source counts if they help; the historical 966-test population is superseded.

Criteria that justify removal:

- No identified unique behavior after inspecting the assertions and cases,
  supported by discriminating mutations in plan WP6 for which a retained
  test fires. Finite mutation agreement is evidence of overlap within that
  comparison, not proof that no unique failure mode exists.
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
- The test is the only one asserting a reason identifier, lifecycle boundary
  or race behavior. Identifiers are part of the JSON contract; reason counts
  alone do not describe all the coverage worth keeping.
- The test is one leg of a firing-control, differing-case, invariance-case
  triplet. Fold the triplet into one test with shared setup if the setup
  dominates; do not drop a leg.

Process:

1. Take candidates and mutation results from WP6. A new candidate needs the
   same analysis before removal.
2. For each candidate, name the retained test that covers the same failure and
   the mutation that showed it, in the commit message.
3. One commit per cluster, so any cluster can be reverted alone.
4. Prefer folding repeated assertions within a case when it preserves the
   behavioral distinctions and control roles. Keep state independent across
   cases that depend on different observations or lifecycle histories.
5. Present the list to the user before deleting anything. The user decides.
6. After each cluster, re-run the cluster's files with the mutation that
   justified it and confirm something still fires.

## 7. Retention without losing the run's evidence

Default to keeping evidence and removing bulky fixtures of known passing
tests. A rerun is a new observation; it cannot recover the original command
streams, timing conditions or passing controls. Allow evidence runs to retain
selected passing artifacts, and keep incomplete outcomes conservatively.

What the historical full run retained: 3.4 GB and 2414 entries, spread over
about 1200 test directories, each holding a checkout, a worktree, a private
HOME with a gitconfig, `commands/NNNN/` records with both streams, and for
some tests a staged runtime copy or a nested venv. The largest single
directory was 62 MB. About fifteen retained runs accounted for the observed
36 GB in the main checkout's `.scratch`; neither size is a current inventory.

What to retain for every run or selected evidence case:

- The receipt: actual membership, phase outcomes and durations, plugins,
  interpreter, wheel digest and configuration. Add test/harness source
  identity, Git executable/version, selector, workers and permission context;
  a runtime wheel does not identify the test source.
- Actual pytest stdout/stderr as well as `.log` (currently only provisioning
  and build output), the retained wheel under `-dist`, and per-worker records
  if sharding is used. Capture startup/collection failures even without a
  completed pytest receipt.
- Failure artifacts for setup, call or teardown, plus artifacts of interrupted
  or unresolved tests. Include the sibling private HOME and command records.
- Selected passing evidence: for example a comparison's firing/control cases
  and the `commands/` streams on which its explanation relies. Copy evidence
  out of disposable directories before cleanup or explicitly retain them.
- Raw comparison timings and provenance, not just aggregate summaries.

The bulky checkout, worktree, HOME, staged copies and nested environments of
a known passing test may go after that evidence decision. Unselected command
records may go with them; never claim the receipt necessarily contains all
their evidence. Record the retention policy and what was kept or discarded.

Mechanism: keep `--basetemp` and map artifacts, including sibling HOME, to
their owning tests. Decide cleanup only after setup, call and teardown reports
are complete, preferably in a runner-owned post-test pass. Missing phase
information or interrupted finalization must retain the affected artifacts.
Pytest 7.4.3's `tmp_path_retention_policy = "failed"` is insufficient by itself:
its `tmp_path` teardown checks the call outcome, defaults a missing call to
success for cleanup, and cannot see a later teardown failure. Do not enable
that early deletion beneath a policy that promises to keep such failures.

Provide `--keep-artifacts failed|all` (default `failed`) and a repeatable
node selection for retaining passing evidence. Define treatment of skipped
or otherwise non-passing cases explicitly; absent a completed pass, retain.
No `none` mode is needed for this work. Verify each phase failure, interruption,
ordinary passing cleanup and selected passing retention. Measure the resulting
space rather than promise a fixed reduction.

The existing pile: the main checkout's retained runs are the user's evidence
for past review cycles and the user's to delete. A reasonable policy is to
inventory each run's receipt, streams, wheel and cited evidence before deciding
which remaining artifact directories to delete. The new default does not
authorize retroactive cleanup.

Pinned by: receipts in `tests/test_runner.py` and `tests/test_foundations.py`,
command evidence and private HOME in `tests/conftest.py`. Add retention tests
for the new contract; a lack of old retention assertions is not proof that
passing artifacts have no evidentiary value.

## 8. Smaller choices

- Fix the duplicate collection in `scripts/check.py`: when a positional test
  path is given, do not also append the suite's `tests` directory, or resolve
  the given path into the staged suite and pass only that. Handle overlapping
  explicit paths/node IDs without duplicate execution; test actual membership.
- Keep `--fast` as the existing smoke selection. The historical `not heavy`
  tier was about 1794 s versus 84 s for smoke. If a broader developer tier is
  useful, name and measure it separately; do not silently expand `--fast`.
- One interpreter in the developer loop; both interpreters at the gate, one
  after the other whether or not sharding exists.
- Historical CLI spawns cost about 0.18 s of startup each, 585 per run. Keep
  subprocess tests where the CLI contract is the subject and let the rest
  use `stewart.api`.
  This is a small lever on its own and follows naturally from section 5.
- Add the targeted performance and revalidation guards from section 4 before
  changing runtime observations. The number of commands is a separate claim
  from their behavioral adequacy.
