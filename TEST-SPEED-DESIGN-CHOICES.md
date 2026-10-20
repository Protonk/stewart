# Test speed: design choices for implementation

Status: companion to `TEST-SPEED-PLAN.md`. The correctness and evidence
requirements below constrain implementation; mechanisms and savings remain
proposals to verify. The branch is `main` at `764d97e` plus planning commits
and no longer waits for `rehome`. The historical figures describe 966 tests
of an earlier source; the current population is 992 tests
(`baseline/repair-followups/full-311.json`). New comparisons must identify
their own population and source, including test/harness changes outside the
wheel. Evidence paths such as `plan-review/...` are relative to
`.scratch/test-speed/`.

Git process startup is a promising large cost. A full run sends 6,860 (966
tests) or 7,076 (992 tests) git commands through the `run_cmd` fixture
alone (`plan-review/receipt_summary_corrected.out`; the earlier 10,422 and
10,677 counted records twice through pytest's `current` links), and the old
sample measured six checkout spawns, three prompt-commit spawns, and at least
41 in `prepare()` and 36 in `collect()`. Repeated argv identifies candidates, not
redundant checks. The recorded runs had competing load, so neither a complete
attribution of suite time nor a suite-wide speedup is established.

Sequence: pickup and a reference run (plan WP0); selection repair, directory
pruning and Git executable selection (WP1); bounded retention (WP2); then
reassess (WP3). Sharding (WP4) and runtime observation reuse (WP5) need
evidence that the remaining cost warrants them and the user's agreement.
Exhaustive decomposition and test removal are not entry requirements;
consolidation can be a separate follow-up (WP6).

## 1. Which git binary the harness runs

Choice: leave `git` resolution to PATH, or have `scripts/check.py` expose a
non-shim binary to the tests.

Evidence: the historical sample measured about 17 ms per spawn through
Apple's `/usr/bin/git` shim versus 7 ms through the binary found with
`xcrun --find git`. Three Git-heavy tests improved substantially. The old
34-to-18-minute suite estimate was an extrapolation from spawn counts, not a
measured result. None of these outputs were retained; repeat interleaved
comparisons before relying on them.

Two mechanisms fail (`plan-review/git_direct_path.out`):

- A symlink to or copy of the direct binary in a private directory. Apple's
  Git derives its exec path and templates from the path it was invoked by.
  Through a link at `<dir>/bin/git`, `git --exec-path` names
  `<dir>/libexec/git-core`, which does not exist; `git init` warns that
  templates are missing, and `git submodule` is not found.
- The developer `usr/bin` first on PATH. On this machine that directory holds
  114 tools, and its `python3` (3.9), `pip3` and `pydoc3` would shadow
  Homebrew's. Nothing in the suite runs `python3` by name today, but the
  experiment launcher forwards PATH to auditor children
  (`src/stewart/experiment.py:198`).

Recommendation: on macOS, when `shutil.which("git")` resolves to the xcrun
shim, resolve `xcrun --find git` and verify the candidate: it is executable,
reports the same `--version` as the shim, and its `--exec-path` is an
existing directory under the same developer directory. Then insert the
candidate's directory into the tests' PATH immediately before the PATH entry
that supplied the shim, so entries earlier on PATH keep precedence. On this
machine the insertion changes 111 names, not the 48 first reported: 22 whose
`/usr/bin` entry is that same shim, 24 developer tools whose `/usr/bin` entry
is a different file (`actool` through `xed`), and 65 that resolved nowhere
before, among them `python3.9`, `pip3.9`, `pydoc3.9`, `2to3` and `scalar`
(`levers/git/changed_names.out`; `plan-review/git_direct_path.sh` counted only
names with a `/usr/bin` entry). The experiment launcher forwards them to
auditor children.

Provide `--git-executable auto|path|<absolute path>`, default `auto`. `path`
leaves PATH untouched. An absolute path inserts that executable's directory
by the same rule; the plan's logging wrapper, which attributes each call to
a node through `PYTEST_CURRENT_TEST`, goes in this way.
Preserve normal PATH selection on other platforms and when no verified direct
binary is available, recording the fallback. Record the requested choice,
inserted entry, actual executable, realpath, version, exec path and changed
names in the receipt and the `.log`. This is harness environment; Stewart
continues invoking `git` by name. Homebrew Git was not measured and is not
installed here.

A private directory holding only a `git` script that `exec`s the direct
binary by absolute path keeps the exec path correct and changes nothing else,
at the cost of one shell start per call. Given the 65 newly resolvable names,
the user chose (2026-10-19) to measure it as a third condition and prefer it:
`auto` creates the wrapper in `check.py`'s private directory when its saving
is established; the directory insertion needs an established advantage over
the wrapper and the user's agreement.

Pinned by: nothing yet. `tests/acceptance.py` names `/usr/bin/git` explicitly
but is not collected by pytest. Tests that construct PATH themselves bypass
the selection (`tests/test_auditor_runtime.py:125` uses `os.defpath`). Plan
WP1.3 lists the new regressions.

## 2. The two tests that walk `.scratch`

Choice: prune traversal, limit future artifact growth, or both.

Evidence: 81 s and 58 s in the historical 966-test run on 3.11, and 65 s and
45 s in the 992-test run. Their cost tracks the size of the running
checkout's `.scratch`, not the code under test. A pruned walk in
`source_python` took 0.04 s. The authority module is marked `smoke`, so
`--fast` pays for its walk. Hatchling 1.27.0 prunes a directory before
descending only if the directory is in its built-in list (`.git`, `.venv`,
`__pycache__` and others) or, with `skip-excluded-dirs = true`, if it matches
`exclude`. The setting defaults to false, so `exclude` alone does not prevent
the walk (`plan-review/hatchling_walk.out`).

Recommendation: both. In `tests/test_authority.py`, walk with `os.walk` and
drop the top-level names `.scratch`, `.git`, `dist` and `build` from
`dirnames` before descending. Keep the current top-level-only exclusion, the
refusal to descend through symlinked directories, and the treatment of
`*.py` entries that are not regular files; the resulting name list must
equal the old one. In `pyproject.toml`, add `"/.scratch"` to
`[tool.hatch.build] exclude` and set `skip-excluded-dirs = true` under
`[tool.hatch.build.targets.sdist]`. Do not add an sdist-level `exclude`:
hatchling uses a target's `exclude` instead of the global list, not in
addition to it. `.venv` is already pruned. Keep `ignore-vcs = true`, because
the distribution test's point is that the build needs no Git. Limit future
artifact growth through section 7; cleanup of historical artifacts remains
the user's decision. Plan WP1.2 has the firing comparison across two bloat
levels, the invariance case and the unchanged file and member sets.
Retention limits future growth but does not replace correct pruning.

Pinned by: `test_sdist_builds_same_wheel_without_git_or_network` asserts the
sdist member set and that the rebuilt wheel matches; pruning a directory that
contributes no members changes neither. The authority test's assertion that
at least 29 runtime sources remain guards against gross over-pruning, but
only an explicit list comparison shows the population is unchanged.

## 3. Sharding inside the check script

Choice: pytest-xdist, a shard loop in `scripts/check.py`, or nothing.

Evidence: the original machine had ten cores, four of them performance
cores, with competing load. That is no basis for a fixed worker count. The
conftest's `plugin_origins` assertion admits only pytest's own plugins and
the local conftest, and the wheelhouse is hash-locked, so xdist would require
new locked dependencies plus a widened assertion.
The `serial` marker is declared and unused. Each test already has a private
`tmp_path`, HOME and manager home.

Recommendation, if WP3 warrants it and the user agrees: prefer an opt-in
shard loop, with `--workers` defaulting to one, after WP4's independence
audit. Assign files using compatible duration evidence or a deterministic
fallback. Each worker needs its own result path, streams and `--basetemp`; no
worker overwrites the aggregate or another worker's evidence. Measure useful
worker counts under comparable load.

Establish the invocation's expected collected and selected node sets before
dispatch. Workers must execute each selected node exactly once, or identify
it as incomplete. Reject duplicate, missing and foreign nodes before merging
maps or counts; a union can conceal duplicates. Preserve collection and
deselection meanings even if workers receive already-selected node IDs.
Document aggregate outcome/exit semantics and keep every worker's raw result;
numeric maximum of exit codes alone cannot explain collection errors,
interruptions, missing/stale receipts or an incomplete worker. Apply section
7's retention once, over the merged membership.

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
establish equivalent cwd, inputs or observation boundaries. The counts are
lower bounds: the duplicate table came from `tools/measure2.py`, which sees
only `subprocess.run`, while every `prepare()` also starts
`git update-ref --stdin` through a direct `Popen` (`create_refs`,
`_git.py:63`). The calls are candidates to inspect, not a measured fraction
that can safely be removed.

Recommendation, if WP3 implicates an operation and the user agrees:
investigate only that operation. For each proposed reuse, record the original
check, its later consumer, intervening side effects or possible external
changes, and why the consumer does not require a fresh observation. Passing
an identity dictionary down within one call can still skip required
revalidation. Keep repeated calls where that boundary matters; do not
introduce a cross-operation cache.

WP5's instrumentation must wrap `Popen` as well as `run` without double
counting, time direct `Popen` processes, and retain raw argv, cwd, relevant
configuration and inputs, phase and call sites. Spawns inside child
processes need a PATH-level logging wrapper. Bound spawn counts for stable
representative paths before changing them, but pair performance checks with
regressions that change identity, contents or uses between checking and
acting, and with unchanged controls. A low spawn count cannot establish safe
custody.

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
`test_resources.py`; `Stewart` classes in `test_discovery.py` and
`test_resources.py` (subclassed in `test_closeout_doubt.py`); `_run` in
`test_stewart_cli.py` and `test_stewart_experiment.py`; `cli_base` in
`test_stewart.py`; `cli_args` in `test_stewart_inputs.py`; a `Stewart` class
and `_git` in `test_journey.py`; `run_block` in
`test_stewart_launch_profile.py`. They differ in how they parse the JSON
envelope, which exit codes they allow, and whether they pass `-I -B`.

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
allowed exit codes. It also makes later cost and overlap analysis easier.
Preserve each caller's intended allowed exits, envelope assertions and
isolated startup; centralizing must not silently broaden successful outcomes.

What not to do: do not share prepared sessions across tests at module or
session scope. Nearly every test mutates its repository, the conftest's first
line promises test independence, and the custody semantics under test are
about what one operation sees. Even nominally read-only assertions need an
independence argument before sharing setup. Prefer independent copies; do not
introduce a shared prepared session as part of a mechanical helper refactor.

Sequencing: refactor per file when it supports measured work; avoid a
suite-wide prerequisite before the narrow harness fixes.

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

What the historical full runs retained (`plan-review/receipt_summary.out`):
3.61 GB allocated (3.24 GB apparent) and 202,719 entries for the 966-test
run, and 3.58 GB (3.21 GB) and 207,540 entries for the 992-test run. The
966-test run's 2,414 top-level entries are 965 private HOMEs, a test
directory beside each, and 484 pytest `<prefix>current` links. A test directory holds a checkout, a
worktree, `commands/NNNN/` records with both streams, and for some tests a
staged runtime copy or a nested venv; the HOME holds a gitconfig and any
checkout or manager homes derived from it. About fifteen retained runs
accounted for the observed 36 GB in the main checkout's `.scratch`; neither
size is a current inventory.

What to retain for every run or selected evidence case:

- The receipt: actual membership, phase outcomes and durations, plugins,
  interpreter, wheel digest and configuration. Add every phase outcome per
  node (today `node_outcomes` omits passing setup and teardown, so a passing
  teardown looks the same as one that never reported), node markers, the
  paths each node owns, test/harness source identity, Git executable and
  version, selector, workers and permission context. A runtime wheel does not
  identify the test source. Keep the meaning of the existing `node_outcomes`
  and `outcomes` fields; tests assert them.
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

Mechanism: keep `--basetemp`. The autouse fixture that creates each test's
private HOME records, per node, the `tmp_path` and `-home` paths it owns.
After pytest exits, `check.py` reads this invocation's receipt (matched by
its `artifacts` path, as the budget augmentation already does) and plans
removals: a node's owned paths go only when setup, call and teardown are all
recorded as passed and the node is not selected for retention. Everything
else stays, including skipped nodes, nodes with a missing phase, and any
top-level entry no node owns. No receipt, or a receipt from another
invocation, means nothing is removed, so a killed run keeps everything. Write
the plan into the receipt before the first removal, then record each path's
result. Remove only verified direct children of the artifacts directory that
are directories rather than links; use `shutil.rmtree`, which avoids symlink
attacks on macOS; restore owner permissions inside the tree when a test left
it unwritable. Remove a pytest `*current` link only when its target was
removed by the same pass. Record removal failures, keep what remains, and
never let them change test outcomes.

Pytest 7.4.3's `tmp_path_retention_policy = "failed"` is insufficient by
itself: its `tmp_path` teardown checks the call outcome, defaults a missing
call to success for cleanup (so a setup failure is deleted), and cannot see a
later teardown failure. It also never removes the sibling HOME. Do not enable
that early deletion beneath a policy that promises to keep such failures.

Provide `--keep-artifacts failed|all` (default `failed`) and a repeatable
`--keep-node NODEID` for retaining passing evidence. A requested node that
did not execute makes the runner exit nonzero and is recorded in the receipt;
an evidence run that lost its control is not evidence. Skipped and otherwise
non-passing cases are retained. No `none` mode is needed for this work.
Verify each phase failure, interruption, a killed run, ordinary passing
cleanup, unowned entries and selected passing retention. Measure the
resulting space rather than promise a fixed reduction.

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

- Fix the duplicate collection in `scripts/check.py` by not passing the
  suite's `tests` directory, so pytest falls back to `testpaths` when no
  positional argument is given. Positional arguments stay relative to the
  staged suite root and are not rewritten. The pinned pytest also runs
  overlapping arguments twice (`tests/a.py tests/a.py::t` runs `t` twice), so
  the conftest refuses duplicate node IDs and items outside the staged suite
  at collection (`plan-review/pytest_selection.out`). The `suite` case of
  `test_runner_measures_each_selected_boundary` looks up the removed argument
  and must be updated to keep its refusal.
- Keep `--fast` as the existing smoke selection. The historical `not heavy`
  tier was about 1794 s versus 84 s for smoke, and most of smoke's 84 s was
  the authority walk that section 2 removes. If a broader developer tier is
  useful, name and measure it separately; do not silently expand `--fast`.
- Python 3.14 only, in the developer loop and at the gate, whether or not
  sharding exists (the project dropped 3.11 at `db61a8d`).
- Historical CLI spawns cost about 0.18 s of startup each, and the 992-test
  run started 535 of them through `run_cmd`
  (`plan-review/receipt_summary_corrected.out`). Keep subprocess tests where
  the CLI contract is the subject and let the rest use `stewart.api`. This is
  a small lever on its own and follows naturally from section 5.
- Add the targeted performance and revalidation guards from section 4 before
  changing runtime observations. The number of commands is a separate claim
  from their behavioral adequacy.
