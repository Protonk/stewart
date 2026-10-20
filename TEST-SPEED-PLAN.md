# Test speed and evidence retention plan

Status: WP0 to WP3 done; the three approved follow-ups are done (provisioning
without rustc, a targeted WP5 change to `checkout_identity`, and the
concurrency probe; `TEST-SPEED-FINDINGS.md`). The user declined WP4. WP5's
instrumentation and census are done without runtime changes; further WP5
changes await the user's rulings and approval. Start with bounded
measurements and improvements to the test harness, then investigate the
remaining costs. This file sets the
order, evidence and acceptance of each work package;
`TEST-SPEED-DESIGN-CHOICES.md` sets out the mechanisms and the constraints
they must satisfy. Update a work package's status line when it
lands. Remove both files when their contracts have reached documentation and
tests; keep unresolved work explicit.

The `test-speed` branch is `main` at `764d97e` plus planning commits and,
since 2026-10-19, the commit that drops Python 3.11 (`db61a8d`): the project
supports Python 3.14 only. `rehome` has merged; there is no merge dependency
to wait for. The current population is 992 tests: the repair validation of
`764d97e` collected 992 (`baseline/repair-followups/full-311.json`). The
966-test measurements below are a historical baseline of an earlier source,
not the current population. Do not rewrite those receipts or combine their
timings with a different population as though they measured the same suite.

The question is which changes reduce elapsed time and retained bulk while
preserving independent tests, custody checks and the evidence needed to
understand a run. An exhaustive census and test deletion are not
prerequisites for the inexpensive harness improvements.

## Ground rules

- Work in this worktree (`stewart-test-speed`, branch `test-speed`). Leave
  sibling branches, worktrees, files and historical artifacts alone. The main
  checkout is on `main` and other sessions may use it; check actual branch,
  worktree and process state at pickup instead of assuming it is idle.
- Local evidence, ignored by Git and possibly absent in a fresh checkout.
  Paths below are relative to `.scratch/test-speed/` unless they say
  otherwise:
  - `baseline/`: the 966-test receipts, streams and logs (`repair-311.*`,
    `repair-314.*`) and, under `repair-followups/`, copies of the 992-test
    receipts, streams and logs with `SOURCES.sha256`.
  - `plan-review/`: the probes behind this revision's corrections; its README
    lists them.
  - `tools/`: the historical spawn-counting scripts. Their README is stale;
    read WP5 before reusing them.
  - `.scratch/wheelhouse` (at the worktree root): the locked wheels.

  The historical runs' artifact directories remain in the main checkout's
  `.scratch/identity/` and `.scratch/repair-followups/`. Read them if useful;
  never modify, move or delete them. If any of this evidence is missing, mark
  the dependent figures unavailable and make bounded new comparisons; do not
  invent missing provenance or require another worktree's trees.
- Supported interpreter: `/opt/homebrew/bin/python3.14` (3.14.8), in the
  development loop and for the single gate run. The WP0 runs made on 3.11
  before the 3.14-only decision are historical evidence; never combine their
  timings with 3.14 runs.
- During investigation use focused selections and keep each run to about two
  minutes of tests. A full run takes about 21–24 minutes on this machine
  (`reference/`); use full runs for the WP0 reference, the WP3 reassessment
  and the final gate, not to rank ideas.
  Run one interpreter and one check invocation at a time. Check for competing
  processes with `ps aux | rg '[p]ytest|[c]heck\.py'` as a command of its own,
  because a longer command line can match itself. A full run outlasts ordinary
  tool timeouts: start it as a background job and wait for its completion
  instead of polling it or starting other check work.
- Permission context changes outcomes.
  `tests/test_foundations.py::test_socket_and_empty_runtime_refuse` binds an
  AF_UNIX socket under `/tmp`. The default sandbox refuses the bind with
  `PermissionError`, so both 992-test full runs reported 1 failed, while the
  unchanged test and wheel passed with permissions enabled
  (`baseline/repair-followups/socket-check.*`, `socket-unsandboxed-311.*`,
  `socket-unsandboxed-314.*`, `validation.json`). Run the reference, timed
  comparisons and gate with permissions that allow the bind (ask the user to
  approve running outside the sandbox), and keep the permission context the
  same within a comparison. If a run is refused anyway, preserve its original
  outcome, run the separate comparison and report both; do not relabel the
  failed run.
- Until WP1.1 lands, do not pass a test path or node ID to `scripts/check.py`.
  It also passes its own `tests` directory, so pytest runs the whole suite and
  then the named tests a second time; under a `-k` filter only the filtered
  tests run, twice (observed: 6 passed for 3 selected;
  `plan-review/pytest_selection.out` reproduces the mechanism). Use `-k`
  alone, and add a path only together with `-k` when showing the defect.
- Commands use an explicit interpreter in isolated mode, for example (create
  the result directory first and use a fresh result name per run):

  ```
  /opt/homebrew/bin/python3.14 -I -B scripts/check.py --result .scratch/test-speed/<topic>/<name>.json -k "<expression>" > .scratch/test-speed/<topic>/<name>.out 2>&1
  ```

  `check.py` writes `<name>.json` and `<name>.log` and creates
  `<name>-artifacts-*` and `<name>-dist` beside the result. The WP0 helper adds
  `<name>.out` and `<name>.provenance.json`; WP2 adds `<name>.pytest.log`. Do
  not reuse these names for anything else. Until WP2, `check.py` keeps every
  test directory: about 3.6 GB allocated and 207,000 entries per full run.
  That bulk lands inside the tree two tests walk (see "Two outliers"), so
  record the `.scratch` entry count before every run.
- Measurement discipline, from `AGENTS.md`: a clean result needs a firing
  control, a case differing in the measured property, and an invariance case.
  An explanation stays a hypothesis until a comparison distinguishes it from
  its rivals. Preserve command outputs, name the selector, and report actual
  collected, selected and deselected counts. For a timing comparison run at
  least three repetitions per condition in interleaved order (A B A B A B)
  under comparable load, retain every timing, and report median and range.
  The primary timing is the selected nodes' summed setup + call + teardown
  from the receipt's `durations`; keep the run's `total_seconds` as well,
  since it adds about seven seconds of provisioning, build and collection.
  Call a difference established only when every repetition of one condition
  is faster than every repetition of the other and their outcomes are
  identical. Call invariance shown when the conditions' ranges overlap and
  their medians differ by less than the larger range. Report anything else
  as not distinguished, and investigate before relying on it.
- Record provenance for every run (WP0 provides the helper): the Git
  executable the harness environment resolves, with its realpath, version and
  exec path; the interpreter; the wheel digest; test/harness/configuration
  source identity (commit plus digests of changed and untracked files); full
  argv and cwd; selector; worker count; permission context; competing load
  (load averages and matching processes); and the `.scratch` entry count. The
  wheel alone does not identify the tests. Keep pytest stdout/stderr: today's
  `.log` contains provisioning and build output, not the pytest streams.
- Keep evidence under `.scratch/test-speed/<topic>/`. Write findings to
  `TEST-SPEED-FINDINGS.md` at the worktree root with every number traceable
  to a file under `.scratch/test-speed/`.
- Scope starts with `scripts/check.py`, test infrastructure and build
  configuration. Runtime changes require the targeted evidence and
  revalidation analysis in WP5. Test removal is a separate follow-up in WP6;
  neither is required to deliver the initial harness improvements.

## Historical observations and limits

`plan-review/receipt_summary.py` reproduces the receipt-derived figures below
(output `plan-review/receipt_summary.out`) and inventories the artifact
directories the receipts name. Its `run_cmd` counts also followed pytest's
`<prefix>current` symlinks and counted those tests' records twice; the
`run_cmd` rows below come from `plan-review/receipt_summary_corrected.py`
(output `receipt_summary_corrected.out`), whose output differs only in the
`run_cmd` record and git-verb lines (`pickup/run-cmd-count/count_records.out`).
The pytest session times come from the runs' `.out` streams in `baseline/`. In each pair the 3.11 and 3.14
invocations ran at the same time, so contention affected their timings by an
unknown amount.
The change in elapsed time from 966 to 992 tests cannot be attributed:
source, population and load all differ.

| Fact | 966 tests (earlier source) | 992 tests (`764d97e`) |
| --- | --- | --- |
| Receipts | `baseline/repair-311.json`, `repair-314.json` | `baseline/repair-followups/full-311.json`, `full-314.json` |
| Wheel SHA-256 | `86d61eaf…` | `ce003ae9…` |
| Outcome | 965 passed, 1 skipped | 990 passed, 1 failed (sandbox socket refusal), 1 skipped |
| pytest session time, 3.11 / 3.14 | 2045.04 s / 2103.48 s | 2407.30 s / 2474.03 s |
| Call time on 3.11: median, p75, p90, p99 (inclusive quantiles) | 1.53, 2.58, 4.12, 8.94 s | 1.90, 2.99, 4.58, 9.43 s |
| Tests over 0.5 s of setup + call + teardown, 3.11 / 3.14 | 714 / 725 | 758 / 758 |
| Largest tests, 3.11 | authority 81.1 s, sdist 58.0, journey 25.4, runner 19.9 | authority 65.4 s, sdist 44.6, journey 28.1, resource safety 19.3 |
| Commands through `run_cmd` per run | 7,680: 6,860 git, 530 `python -I -B -m stewart`, 262 other python, 28 other | 7,901: 7,076 git, 535 `python -I -B -m stewart`, 262 other python, 28 other |
| git verbs through `run_cmd` | add 1539, commit 1538, config 1474, rev-parse 1474, init 742, worktree 54 | add 1585, commit 1584, config 1526, rev-parse 1520, init 768, worktree 54 |
| Retained artifacts per run, 3.11 | 3.61 GB allocated (3.24 GB apparent), 202,719 entries; 2,414 top-level: 965 private HOMEs, 965 test directories beside them, 484 pytest `*current` links | 3.58 GB allocated (3.21 GB apparent), 207,540 entries; 2,471 top-level: 991, 991, 489 links |

`run_cmd` counts cover only commands a test ran through that fixture. Git
spawned in-process by `stewart.api` calls, or by a CLI child, is not recorded
there. The previous revision's figures of 767 tests over 0.5 s and a p99 of
9.08 s do not reproduce from these receipts and have no retained source; do
not use them (`pickup/run-cmd-count/other_old_figures.out`). Its 7,680 fixture
subprocesses (6,860 git; 1,539 add, 742 init, 54 worktree) do reproduce from
the 966-test artifacts once the `current` links are not followed.

The following were observed with the scripts under `tools/` or by hand while
another session had five test processes running. Their outputs were not
retained. Treat them as leads to validate, not as attributions of the current
suite's runtime:

| Observation | Value |
| --- | --- |
| Marker coverage of the 966-test time | `system` 628 tests 1466 s; `heavy` 62 tests 249 s; unmarked 251 tests 244 s; `smoke` 25 tests 84 s; `serial` unused |
| Selections | `--fast` (`smoke and not heavy`) about 84 s; `-m "not heavy"` about 1794 s. `tests/test_authority.py` is module-marked `smoke`, so its 81 s walk was nearly all of `--fast` |
| git inside `prepare()` | 41 spawns, 26 distinct argv, about 0.9 s; a lower bound (WP5) |
| git inside `collect()` | 36 spawns, 19 distinct argv, about 0.8 s; a lower bound |
| Fixture `make_checkout` | 6 git spawns, 0.15 s; `prompt_commit` 3 spawns, 0.07 s |
| One `python -I -B -m stewart` spawn | 0.18 s before any git work; bare interpreter 0.02 s |
| git spawn cost | 17 ms through Apple's `/usr/bin/git` shim, 7 ms for the binary it execs, 3 ms for `/usr/bin/true` |
| Three unnamed resource tests, shim vs direct binary | 10.9, 10.7, 7.9 s vs 4.9, 5.0, 5.0 s |
| Collection alone through the harness | about 3 s after roughly 4 s of provisioning and build |
| Main checkout `.scratch` | 36 GB, 2.68 million entries, 612k `.py` files, about 15 retained full runs; not re-measured |

Receipts do not record markers; WP2 adds them so WP3 can recompute tier costs.

Repeated Git argv inside one operation (candidates for investigation, not
proof of redundant observations):

- `prepare()`: the `checkout_identity` quartet (`--is-bare-repository`,
  `--show-toplevel`, `--absolute-git-dir`, `--git-common-dir`) runs three
  times, 12 spawns; `rev-parse --verify <same sha>^{commit}` five times;
  `worktree list`, `rev-parse HEAD`, `show <sha>:PROMPT.md` and
  `diff --name-only` twice each.
- `collect()`: `rev-parse --show-toplevel` and `--git-common-dir` three times;
  `status --porcelain` three times; `rev-parse HEAD` three times; the four
  diff forms, `ls-files --error-unmatch` and `branch --show-current` twice each.

Two outliers have identified traversal costs. Both walk
`STEWART_TEST_PROJECT`, the checkout running `check.py`, so their cost grows
with that checkout's `.scratch`, including the artifacts of this plan's own
runs:

- `tests/test_authority.py::test_audit_custody_machinery_has_one_home` calls
  `source_python`, whose `rglob("*.py")` walks every entry under `.scratch`
  before the filter discards them. A walk that prunes the excluded top-level
  names first took 0.04 s on the same tree. The module is marked `smoke`, so
  `--fast` also pays for this walk.
- `tests/test_distribution.py::test_sdist_builds_same_wheel_without_git_or_network`
  builds an sdist from the project root. `[tool.hatch.build]` sets
  `ignore-vcs = true` and the sdist target lists `include` rather than
  `only-include`, so hatchling's `recurse_project_files` walks every directory
  it does not prune. Hatchling 1.27.0 prunes a directory only when the directory is in
  its built-in list (which includes `.git` and `.venv`) or, with
  `skip-excluded-dirs = true`, when it matches `exclude`. That setting
  defaults to false, so adding `/.scratch` to `exclude` alone leaves the walk
  in place (`plan-review/hatchling_walk.out`: all 401 synthetic scratch
  directories still entered; none with `skip-excluded-dirs`; identical
  members).

Not supported under the measured conditions:

- Bytecode: a CLI spawn cost about 0.18 s with or without compiled `.pyc`
  files; that comparison did not show a useful saving.
- git fsync: `core.fsync=none` and `core.fsyncMethod=batch` leave the
  init-config-add-commit sequence at 150 ms either way.
- git config lookup: `GIT_CONFIG_NOSYSTEM=1` changed nothing measurable.

Revisit these only when a changed environment or new evidence justifies it.

## Work packages, in order

Each work package ends with its evidence under `.scratch/test-speed/<topic>/`,
its regressions passing in a focused run, an entry in
`TEST-SPEED-FINDINGS.md`, an updated status line here, and a focused commit.
Show each new regression failing against the unchanged harness once and keep
that output; a regression that cannot fail is not a firing control.

### WP0. Pickup, provenance and reference

Status: done. Named selections; two 3.11 references and 3.11 baselines,
historical since the 3.14-only decision; a 3.14 reference and 3.14 baselines
on `db61a8d`, which WP1 to WP3 use. See `TEST-SPEED-FINDINGS.md`.

1. Confirm state: the worktree is clean on `test-speed` at or after the
   commit that added this revision (ignored `.scratch` content does not
   count); `git worktree list`; no competing check or pytest processes; both
   interpreters; the wheelhouse; which local evidence above is present.
2. Write the run helper as `.scratch/test-speed/tools/run_check.py` (ignored
   by Git; leave the historical scripts beside it unchanged). It wraps one
   `check.py` invocation without changing `check.py`'s behavior:
   - it takes the interpreter, the result path, the `check.py` arguments, an
     explicit `--permission sandboxed|unsandboxed` label and optional
     environment overrides (WP1.3 needs a different PATH);
   - it refuses a result name that already exists;
   - before the run it records the ground rules' provenance fields and the
     result of a socket probe that binds an AF_UNIX socket under `/tmp` as the
     socket test does, so the permission label is checked rather than assumed;
   - it captures combined stdout/stderr as `<name>.out`, and after the run
     adds the exit status, wall time, the receipt's collected, selected and
     deselected counts and its wheel digest to `<name>.provenance.json`.
   Use it for every run in this plan.
3. Write the logging Git wrapper: a directory such as
   `.scratch/test-speed/tools/git-log/bin/` holding only an executable `git`
   script. It appends a timestamp, `$PYTEST_CURRENT_TEST` and its arguments
   to a log named by an environment variable, then `exec`s the Git it wraps
   by absolute path (record which). Pytest sets `PYTEST_CURRENT_TEST` for the
   running node and child processes inherit it, so attribute only lines that
   name a selected node; lines without it come from provisioning or other
   processes. Insert the directory before `/usr/bin` through the helper's
   PATH override. Tests that build their own PATH bypass it (WP1.3 names
   them). The wrapper adds a process start per call, so use it for counts,
   never for timings.
4. Define named selections in `.scratch/test-speed/selections.json`, each with
   its selector, expected selected count and role:
   - `walkers`: `-k "test_audit_custody_machinery_has_one_home or test_sdist_builds_same_wheel_without_git_or_network"`.
   - `git-heavy`: three to five tests, about two minutes together, with the
     most Git work per test. Rank candidates by git `command.json` records per
     top-level directory in a retained full run's artifacts, and confirm each
     directory's owning test by name. Record counts are lower bounds; confirm
     the chosen tests' Git use with the logging wrapper.
   - `no-git`: tests that start no Git process, for invariance. Choose static
     or pure-Python tests that use neither `checkout` nor `run_cmd`, such as
     `tests/test_runner.py::test_budget_charges_all_phases_and_ignores_node_names`,
     and confirm with the logging wrapper that no line names them.
   - `smoke`: `--fast`.
5. Take one pre-change reference full run on 3.14 with the gate's permission
   context and no competing load, under `.scratch/test-speed/reference/`. WP1
   checks the unfiltered node list against it and WP3 compares against it
   node by node. Record the `.scratch` entry count before and after; its
   retained artifacts become part of the tree the walkers traverse.
6. Then run each named selection three times on 3.14 under the same
   conditions, recording counts and timings. These runs are the baseline
   that WP1's comparisons start from and that WP3 repeats.

### WP1. Validate and implement the inexpensive fixes

Status: done. Do the three items in this order. The selection fix makes
node-ID selections usable for the later comparisons. Pruning removes the
walkers' dependence on accumulating artifacts before the Git comparison.

#### WP1.1. Positional selection without duplicates

Status: done; with the user's approval, `check.py` also fails an invocation
that wrote no receipt, which closes the outside-path-only gap
(`TEST-SPEED-FINDINGS.md`).

`scripts/check.py:94` passes `str(suite / "tests")` before the caller's
arguments, and the pinned pytest collects an explicitly named file again
after its directory. Pytest also runs overlapping arguments twice (a file and
one of its node IDs: 3 run for 2 tests; the same file twice: 4 for 2) and
deduplicates only identical node IDs (`plan-review/pytest_selection.out`).

1. Stop passing the suite directory. With no positional argument, the pinned
   pytest uses `testpaths` when the invocation directory is the rootdir.
   `check.py` runs pytest with `cwd=suite` and `-c suite/pyproject.toml`,
   which makes the suite the rootdir, and the conftest already asserts
   `testpaths == ["tests"]`. Without a positional argument pytest still loads
   `tests/conftest.py` from the invocation directory before collection, so the
   boundary assertions keep running first. Check the unfiltered collection
   with `check.py --collect-only -q`. Its node list must equal the WP0
   reference's plus exactly the node IDs this change adds, with the shared
   nodes in the same order and none repeated.
2. Update the `suite` case of `test_runner_measures_each_selected_boundary`.
   At `tests/test_foundations.py:408` it looks up `str(suite / 'tests')` in the
   pytest argv, which would raise `ValueError` once the argument is gone. Drop
   that replacement: pointing `-c`, `--confcutdir` and `cwd` at the project
   still makes pytest load the project's conftest, which must still refuse
   with "wrong staged test suite". Keep the test's diagnostic assertion.
   `test_runner_applies_config_contents_and_reports_selection` should pass
   unchanged.
3. Positional paths and node IDs are interpreted relative to the staged suite
   root, which mirrors the project root (`tests/test_runner.py::<name>`). Do
   not rewrite arguments in `check.py`: option values such as `-k`
   expressions and `--deselect` prefixes must reach pytest unchanged.
   Document the form in `--help` and the README.
4. In the conftest, refuse at collection when two collected items share a
   node ID or an item lies outside the staged suite's `tests` directory. Use
   `pytest.UsageError` as the empty-selection refusal does, and name the
   offending nodes. Do not deduplicate silently.

Regressions run `check.py` over a reduced copy of the project: the project as
`tests/test_runner.py` copies it, but with `tests/` holding only `conftest.py`,
`support.py` (which imports only the standard library) and small probe test
files. A full copy would run the whole suite whenever the old harness is shown
failing. Each `check.py` invocation still costs several seconds of
provisioning and build, so group invocations. Cover: a file argument runs
each of its nodes once; a file plus one of its node IDs is refused with the
duplicate named; `-k` and `--fast` select and deselect as before; the
empty-selection refusal still fires. Evidence under `levers/selection/`:
before/after counts for a path combined with `-k` on the real suite, and the
unfiltered node-list comparison from step 1.

#### WP1.2. Prune the two walkers

Status: done (`TEST-SPEED-FINDINGS.md`).

1. In `tests/test_authority.py`, replace `rglob` plus filter with `os.walk`
   and remove the top-level names `.scratch`, `.git`, `dist` and `build` from
   `dirnames` before descending. Keep the current semantics exactly: exclusion only at the top level (the filter
   tests `parts[0]`), no descent through symlinked directories, and the same
   treatment of entries named `*.py` that are not regular files. The new name
   list must equal the old one.
2. In `pyproject.toml`, add `"/.scratch"` to `[tool.hatch.build] exclude` and
   set `skip-excluded-dirs = true` under `[tool.hatch.build.targets.sdist]`.
   Do not add an `exclude` key under the sdist target: a target-level
   `exclude` replaces the global list. `.venv` needs nothing. Keep
   `ignore-vcs = true`; the build's independence from Git is the distribution
   test's point.
3. Measure `walkers` at two levels of excluded content: the existing tree
   (record its entry count) and the existing tree plus synthetic bloat of
   about 200,000 entries under `levers/pruning/bloat/`, comparable to one
   retained full run. At each level interleave the old and new source three
   times each, applying and reverting the change as a patch and recording the
   source digests in provenance. Firing: before the change, bloat raises both
   tests' times. Invariance: after the change, their times do not depend on
   bloat. Populations: the authority name list and the sdist member list are
   identical across all four conditions. Save both lists, not only the
   assertions' outcome: provision a venv under `levers/pruning/` from the
   wheelhouse (`requirements.lock`) plus the built wheel, load
   `tests/test_authority.py` from each source version and call
   `source_python` on the project root, and build the sdist there with
   `python -I -B -m build --no-isolation --sdist` and list its members.
   Remove only the bloat and the venv you created and record their removal.
4. Regressions that fail without the change:
   - Split the walk from `source_python`'s population assertion (at least 29
     runtime sources) so the walk can run on a planted tree. On a temporary
     tree with `.scratch/x.py`, `dist/y.py`, `pkg/build/z.py` and a symlinked
     directory, it returns exactly the expected names (the nested `build` stays
     included; nothing under the symlinked directory is listed, as with
     `rglob`) and, recording visited directories by wrapping `os.scandir`,
     never enters `.scratch`. Show the old `rglob` walk entering `.scratch`
     (an `os.scandir` wrapper observes pathlib's `rglob` on 3.14 too;
     `levers/pruning/rglob-scandir-probe.out`).
   - Copy the project's `pyproject.toml` into a temporary project with a
     planted `.scratch` subtree, run the pinned hatchling's `SdistBuilder`
     in-process with its directory walk wrapped as
     `plan-review/hatchling_walk.py` does, and assert that `.scratch` is never
     entered and the members match the planted sources. Hatchling is in the
     check environment because the wheel build uses it. This relies on
     internals of the pinned version; if it proves brittle, assert the two
     configuration keys instead and keep the behavior in the evidence.

Evidence under `levers/pruning/`; the sdist and wheel member sets are
unchanged.

#### WP1.3. Git executable selection in the harness

Status: done, with a `dash` wrapper the user chose after a confirmation
run (`TEST-SPEED-FINDINGS.md`).

1. Compare before implementing. `check.py` passes its PATH through to the
   tests, so run `git-heavy` and `no-git` interleaved under three conditions:
   the inherited PATH (shim); the directory of `xcrun --find git` inserted
   immediately before `/usr/bin` (directory); and a private directory holding
   only a `git` script that `exec`s that binary by absolute path, inserted at
   the same place (wrapper). `git-heavy` is the firing and differing case;
   `no-git` is the invariance case, already confirmed Git-free with the WP0
   logging wrapper. Give every condition as an explicit PATH value through the
   helper's override, so the inserted entry is the only difference.
2. The directory insertion changes 111 names on this machine, 65 of which
   resolved nowhere before (among them `python3.9` and `pip3.9`;
   `levers/git/changed_names.out`), so the user chose the wrapper: implement
   `--git-executable` with the wrapper if its saving is established. Consider
   the directory insertion only if it is established faster than the wrapper,
   and then ask the user first. Insert immediately before the PATH entry that
   supplied the shim, never first; never link or copy the Git binary. Record
   the requested mode, the inserted entry or none, the wrapper and the binary
   it runs, the resolved executable and its realpath, `git --version`,
   `git --exec-path`, any fallback reason, and every name whose PATH
   resolution changed, in the receipt and the `.log`.
3. Leave Stewart's runtime Git invocation alone (`_git.py` runs `git` by
   name). Tests that build their own PATH bypass the selection:
   `tests/test_auditor_runtime.py:125` uses `os.defpath`, while
   `tests/test_stewart_launch_profile.py` prepends to the inherited PATH. The
   experiment launcher forwards PATH to auditor children
   (`src/stewart/experiment.py:198`). Name these in the findings.

Regressions: the selection decision is a function of PATH, platform and the
probes, exercised by loading `scripts/check.py` from a copied project (its
import has no side effects). Cover a shim on PATH, an already direct PATH, no
`xcrun` or a candidate failing verification (PATH unchanged, fallback
recorded), `path`, and an explicit executable. One end-to-end invocation
asserts the receipt's record and that a probe test sees the selected Git and
its exec path. Evidence under `levers/git/`, with each timing.

Deliverable for WP1: focused harness/configuration changes, their regression
coverage, and comparisons under `.scratch/test-speed/levers/`. Do not infer
suite-wide savings from a small sample; identify extrapolations explicitly.

### WP2. Bound retention while preserving evidence

Status: done; WP3's full run measures the space (`TEST-SPEED-FINDINGS.md`).

Inventory one available run by category first: checkout/worktree, private
HOME, command records, staged runtime and nested environments. The retained
historical trees can be read for this. Then implement design choices section
7:

1. Receipt additions, leaving the meaning of `node_outcomes` and `outcomes`
   unchanged because tests assert them: every phase outcome per node,
   including passing setup and teardown (today a passing teardown and a
   teardown that never reported look the same); the paths each node owns
   (its `tmp_path` and the sibling `-home` the autouse fixture creates); each
   node's markers; per-file digests of the staged suite and of `check.py`;
   and the project commit and dirty state when Git can report them, recorded
   as absent otherwise.
2. `check.py` tees pytest stdout/stderr to `<name>.pytest.log` beside the
   receipt while still printing them, so startup and collection failures are
   kept even without a receipt.
3. After pytest exits, `check.py` plans retention from this invocation's
   receipt. It removes a node's owned paths only when setup, call and
   teardown are all recorded as passed and the node was not selected for
   retention. It keeps everything else, including skipped nodes, nodes with a
   missing phase, and top-level entries no node owns. Without this
   invocation's receipt it removes nothing. Write the plan into the receipt,
   remove, then record each path's result, including pytest's `*current`
   links left dangling by a removal. Removal failures are recorded and
   printed and never change test outcomes.
4. Options: `--keep-artifacts failed|all` (default `failed`; `all` is today's
   behavior) and a repeatable `--keep-node NODEID`. A requested node that did
   not execute is an error recorded in the receipt, and the runner exits
   nonzero: an evidence run that lost its control is not evidence.
5. Do not enable pytest's `tmp_path_retention_policy = "failed"`.

Regressions, grouped into few `check.py` invocations over a reduced project
copy with probe tests, as in WP1.1:

- a passing node's `tmp_path` and HOME are removed;
- call, setup and teardown failures are each retained with their HOME and
  command records;
- an unowned directory is retained;
- `--keep-node` retains a passing node, and a missing `--keep-node` target
  is refused;
- `--keep-artifacts all` retains everything;
- an interrupted run (a probe that interrupts the session) retains its
  incomplete node;
- a run killed before writing its receipt removes nothing.

Deliverable: bounded default retention, explicit retention of selected
passing evidence or of all artifacts, and the regressions above. WP3's full
run supplies the retained space, measured against the WP0 reference; show
there that outcome and membership evidence remain. Historical artifacts in
other worktrees remain untouched.

### WP3. Reassess the remaining cost

Status: done; the gate ran as `wp3/gate-314` (after the evidence review's
documentation fixes superseded the first gate run). The user approved its
three recommendations; they are done, and the final gate is
`final/gate-314` (`TEST-SPEED-FINDINGS.md`).

After WP1 and WP2, repeat the WP0 selections three times each and take one
full 3.14 run under the reference conditions. The full run also supplies WP2's
space measurement and, if no source change follows it, is the gate run.
Compare per node on the node set shared
with the reference, and report new regression tests separately rather than
folding them into a suite total. Recompute marker tiers from the receipt. Keep
`--fast` as the small smoke selection; a broader tier needs a separate name
and measured cost.

Use a representative per-file or per-subject decomposition where it changes
the decision. Separate measured time from estimates based on static call
counts, and leave unexplained time visible. Do not require every test to be
explained within a fixed residual percentage before delivering useful fixes.
Centralizing invocation helpers can improve consistency; do not share mutable
prepared sessions to make the numbers smaller.

Deliverable: a ranked residual-cost table in `TEST-SPEED-FINDINGS.md`, with
measured savings, estimates and uncertainties separated, and a
recommendation on WP4 and WP5 with the expected benefit of each. Then stop
and present it. WP4 and WP5 start only after the user agrees. Stopping here,
with WP0 to WP2 delivered, both gate legs run and the recommendation
written, completes the initial work. WP6 is independent follow-up.

### WP4. Sharding, if the user approves it after WP3

Status: declined by the user ("no sharding") after the concurrency probe
WP3 asked for (about twice the throughput with four concurrent
invocations); not started.

Audit shared state before adding parallel workers: fixed paths/ports, HOME,
environment changes, artifact readers and subprocess lifetime. Temporary
files under `/tmp` are not inherently shared; inspect uniqueness and cleanup.
Use current durations to estimate file-level packing for 2, 3 and 4 workers,
then measure the useful choices under comparable machine load.

The contract is exact membership, not sums that happen to match. Establish
the expected collected and selected node sets for the invocation; assign each
selected node once and verify every assigned node's reported execution or
explicit incomplete state. Detect duplicates, omissions and foreign nodes.
Preserve per-worker receipts and streams. Classify planned empty shards,
unexpected empty selections, collection errors, interruptions, missing or
stale receipts and test failures separately; none may become a successful
partial run. Keep the existing empty whole-selection refusal.

Tests marked `serial` require a separate exclusive phase with no overlapping
workers. Merely placing them in shard zero is insufficient. Keep per-test
setup/call/teardown budgets and the end-to-end total budget, including
provisioning, build, collection, scheduling, serial work, workers and merge.
Per-worker limits may be additional limits, never a replacement. WP2's
retention runs once over the merged membership.

Deliverable: if adopted, opt-in workers (default one), documented aggregate
receipt semantics and regressions that inject membership errors and worker
failures as well as compare serial/parallel outcomes. Do not select a default
worker count from core count alone.

### WP5. Investigate specific runtime Git observations, if the user approves

Status: the user approved one targeted change, done: `checkout_identity`
answers its four queries with one `rev-parse` and replays them otherwise
(`c762b26`). The instrumentation below is built and a full-suite census and
custody review are done, with no runtime change ("WP5 census" in
`TEST-SPEED-FINDINGS.md`): the candidates are ranked and classified, four
rulings (R1–R4) are open, and seven pre-existing custody deviations are
reported. Deviations 1 and 2 are fixed (status's gate and the frozen HEAD), and
the remaining correctness problems are listed in the findings; further runtime
changes require the user's rulings and approval.

Start with operations implicated by WP3. Fix the instrumentation before
extending it:

- `tools/measure2.py` wraps `subprocess.run` only, although `tools/README.md`
  says both scripts wrap `Popen`. `tools/measure.py` also wraps `Popen` but
  records a 0.0 s duration for a direct `Popen`. Every `prepare()` reaches a
  direct `Popen`: `prepare.py:244` calls `retain_commits`
  (`_repository.py:520`), which calls `create_refs` (`_git.py:63`,
  `git update-ref --stdin`). The historical `prepare()`/`collect()` counts are
  therefore lower bounds. The README's "extend `measure2.py` for WP1" refers
  to an earlier plan's numbering.
- Wrap `Popen` once (`run` uses it internally), time each process until it
  is waited for, and distinguish in-process calls from child processes whose
  internal spawns the wrapper cannot see. For counts across processes, use
  the WP1.3 logging wrapper; it adds an exec per call, so use it for counts,
  not timings.
- Use isolated fixtures in the state appropriate to each operation; an
  exhaustive API census is optional.

Retain raw argv, cwd, relevant configuration/inputs, operation phase, observed
identities, elapsed time and call sites. Elide paths only in presentation.
Identical argv alone does not establish equivalent queries or safe reuse.

For each proposed removal of a query, name the original observation and
revalidation boundaries, what may change between them, and the evidence that
reuse preserves the custody rule. Within one call, other processes and the
operation itself can change the repository. Preserve a fresh observation
where the check requires it. Keep or add regressions that change identity,
contents or uses between checking and acting, alongside unchanged controls.
Spawn-count bounds are performance checks, not proof of this safety property.

Deliverable: targeted comparisons and, only for justified changes, runtime
edits with the corresponding safety regressions. Record rejected candidates
and the revalidation they must preserve. No cross-operation identity cache.

### WP6. Optional follow-up: overlap and consolidation

Status: not started; optional.

Use static signatures (operations, refusal reasons, fixtures, markers and
written files) to find candidates, then inspect their behavioral differences.
Reason identifiers are one coverage axis, not an equivalence test. Recompute
counts on the selected source instead of inheriting the old 153/129 counts.

For a promising cluster, mutate the installed package in an isolated scratch
fixture and record which tests fire. Use a bounded set of discriminating
mutations; matched results show overlap for those mutations, not proof that
all failure modes are covered. Preserve each firing/control/invariance role,
unique lifecycle/race case and CLI contract. Centralize invocation mechanics
without collapsing independent state.

Deliverable: candidates with the retained coverage, specific mutations and
limits of the evidence. No exhaustive map is needed for the speed work.
Present proposed removals to the user before deleting tests; existing
historical artifacts are also the user's separate decision.

## Completion and handoff

`TEST-SPEED-FINDINGS.md` should link each material claim to retained evidence,
report actual populations and outcomes, separate historical observations from
new measurements, and name implemented, rejected and deferred changes. Keep
raw scripts, receipts and comparisons under `.scratch/test-speed/`.

The initial work is complete when WP0 to WP2 are implemented and verified (or
a measured rejection explains a candidate), WP3 has assessed the residual
cost and recommended next steps, and any WP4/WP5 work the user approved meets
its contract. Deferred investigations or consolidation need not block
delivery. Run focused checks as changes land. At the implementation gate run
the full installed-wheel suite on 3.14 with the reference permission context
and no competing load; WP3's full run is the gate unless the source changed
after it. Report failures,
permission constraints and opt-in harness skips as observed, with separate
reruns when needed. Do not convert a changed test population into a claimed
speedup.

Carry the accepted contracts into `scripts/check.py --help`, the README's
"Run the standalone suite" section (selection form, `--git-executable`,
`--keep-artifacts`, `--keep-node`, and the files a run keeps), the
development paragraph of `AGENTS.md` if the documented commands change, and
regression tests. Commit `TEST-SPEED-FINDINGS.md` with each work package.
Keep both planning files, with updated status lines, while WP4 or WP5 awaits
the user's decision. When nothing in them is pending, remove them together
with `TEST-SPEED-FINDINGS.md` (unless the user asks to keep it), leaving any
deferred work in a concise handoff; the evidence stays under
`.scratch/test-speed/`. Use focused commits so the selection fix, pruning,
Git selection, retention, any runtime optimization and any later test
consolidation remain separately reviewable. Each commit message states its
validation (selector, counts, interpreter, permission context), as recent
commits do.

The work will be reviewed for:

- every number in `TEST-SPEED-FINDINGS.md` naming a file under
  `.scratch/test-speed/`, with population, selector, counts and provenance;
- each adopted change having a firing control, a differing case and an
  invariance case, with every repetition's timing retained;
- each contract above having a regression shown to fail without its change;
- unfiltered membership equal to the reference plus exactly the added
  nodes, and no node executed twice;
- historical receipts and artifacts, including the main checkout's, left
  unchanged;
- help text, README and failure messages describing the new behavior.
