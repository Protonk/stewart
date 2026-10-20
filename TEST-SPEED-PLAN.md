# Test speed and profligacy investigation plan

Status: pending. Investigation only. This plan belongs to the `test-speed`
branch and its worktree. It produces findings and evidence, not changes to
`src/stewart`. `TEST-SPEED-DESIGN-CHOICES.md` is the companion for whoever
moves from these findings to implementation. Remove both files when their
contents have reached documentation and tests.

The question: the full suite takes about 34 minutes for 966 tests. Where does
the time go, which of it is waste, and what would each remedy actually save?
The baseline analysis below answers the first question for the biggest terms.
The work packages finish the census and turn "probably redundant" into
evidence.

## Ground rules

- Work only in this worktree. The sibling checkout `../stewart` is on `rehome`
  and another session runs tests from it. Never switch its branch, never write
  under it, and never delete anything under its `.scratch`.
- Everything this plan needs is under this worktree's `.scratch`, which Git
  ignores: `.scratch/wheelhouse` (the nine locked wheels, 668 KB),
  `.scratch/test-speed/baseline/` (the two full-run receipts this analysis
  used) and `.scratch/test-speed/tools/` (the spawn-counting scripts). The
  36 GB under the main checkout's `.scratch` is retained run output and is
  not needed.
- Never run the full suite under this plan. Select with `-k` and keep each run
  under about two minutes of tests. One interpreter per run, one run at a
  time. Before each run, look for other test processes
  (`ps aux | grep -E "[p]ytest|[c]heck.py"`) and shorten or wait when the
  machine is busy; load is shared with other sessions.
- Do not pass a test file path to `scripts/check.py`. It appends its own
  `tests` path as well, so pytest collects and runs every selected test twice
  (observed: 6 passed for 3 selected). Use `-k` until that is fixed.
- Commands use an explicit interpreter in isolated mode, for example:

  ```
  /opt/homebrew/bin/python3.11 -I -B scripts/check.py --result .scratch/test-speed/<topic>/<name>.json -k "<expression>"
  ```

- Measurement discipline, from `AGENTS.md`: a clean result needs a firing
  control, a case differing in the measured property, and an invariance case.
  An explanation stays a hypothesis until a comparison distinguishes it from
  its rivals. Preserve command outputs, name the selector, and report actual
  selected counts, never intended ones.
- Keep evidence under `.scratch/test-speed/<topic>/`. Write findings to
  `TEST-SPEED-FINDINGS.md` at the worktree root with every number traceable
  to a file under `.scratch/test-speed/`.
- Do not change `src/stewart`. Findings about the tool's own git spawns are
  recorded here; their implementation waits until `rehome` has merged, because
  it touches `_repository.py`, `prepare.py` and `collect.py`.

## What is already established

Source for the suite numbers: `.scratch/test-speed/baseline/repair-311.json`
(Python 3.11.17) and `repair-314.json` (Python 3.14.8). Both runs ran at the
same time, so each inflated the other by an unknown amount. Per-operation
numbers come from in-process counting with the scripts under
`.scratch/test-speed/tools/`, taken while another session had five test
processes running.

| Fact | Value |
| --- | --- |
| Suite | 966 tests, 2045 s on 3.11, 2103 s on 3.14, 965 passed 1 skipped |
| Per-test call time | median 1.53 s, p75 2.58 s, p90 4.12 s, p99 9.08 s |
| Per-test setup time | median 0.17 s, which is the `checkout` fixture's six git spawns |
| Four largest tests | authority 81.1 s, distribution 58.0 s, journey 25.4 s, runner 19.9 s; 184 s together |
| Everything else | a long tail; 767 of 966 tests exceed 0.5 s |
| Subprocesses through the `run_cmd` fixture | 7680 in one run: 6860 git, 585 `python -m stewart`, 199 other python |
| git through the fixture | 1539 add, 1537 commit, 1474 config, 1474 rev-parse, 742 init, 54 worktree |
| git inside `prepare()` | 41 spawns, 26 distinct argv, about 0.9 s |
| git inside `collect()` | 36 spawns, 19 distinct argv, about 0.8 s |
| Fixture `make_checkout` | 6 git spawns, 0.15 s; `prompt_commit` 3 spawns, 0.07 s |
| One `python -I -B -m stewart` spawn | 0.18 s before any git work; bare interpreter 0.02 s |
| git spawn cost | 17 ms through Apple's `/usr/bin/git` shim, 7 ms for the binary it execs, 3 ms for `/usr/bin/true` |
| Three resource tests through the harness, shim vs direct binary | 10.9, 10.7, 7.9 s vs 4.9, 5.0, 5.0 s |
| Collection alone through the harness | about 3 s after roughly 4 s of provisioning and build |
| Marker coverage of recorded time | `system` 628 tests 1466 s; `heavy` 62 tests 249 s; unmarked 251 tests 244 s; `smoke` 25 tests 84 s; `serial` unused |
| `--fast` selects | about 84 s of tests; `-m "not heavy"` still about 1794 s |
| Retained output per full run | 3.4 GB and 2414 entries; largest single test directory 62 MB |
| Main checkout `.scratch` | 36 GB, 2.68 million entries, 612k `.py` files, about 15 retained full runs |

Duplicate git work inside one operation, by argv:

- `prepare()`: the `checkout_identity` quartet (`--is-bare-repository`,
  `--show-toplevel`, `--absolute-git-dir`, `--git-common-dir`) runs three
  times, 12 spawns; `rev-parse --verify <same sha>^{commit}` five times;
  `worktree list`, `rev-parse HEAD`, `show <sha>:PROMPT.md` and
  `diff --name-only` twice each.
- `collect()`: `rev-parse --show-toplevel` and `--git-common-dir` three times;
  `status --porcelain` three times; `rev-parse HEAD` three times; the four
  diff forms, `ls-files --error-unmatch` and `branch --show-current` twice each.

The two outliers have known causes:

- `tests/test_authority.py::test_audit_custody_machinery_has_one_home` calls
  `source_python`, whose `rglob("*.py")` walks every entry under `.scratch`
  before the filter discards them. A walk that prunes the excluded top-level
  names first takes 0.04 s on the same tree.
- `tests/test_distribution.py::test_sdist_builds_same_wheel_without_git_or_network`
  builds an sdist from the project root. The sdist target sets
  `ignore-vcs = true`, lists `include` rather than `only-include`, and excludes
  nothing, so hatchling's `recurse_project_files` walks `.scratch`. Hatchling
  prunes directories named in `exclude` before descending.

Refuted hypotheses, so nobody re-tests them:

- Bytecode: a CLI spawn costs 0.18 s with or without compiled `.pyc` files,
  so `--no-compile` and `-B` are not a lever.
- git fsync: `core.fsync=none` and `core.fsyncMethod=batch` leave the
  init-config-add-commit sequence at 150 ms either way.
- git config lookup: `GIT_CONFIG_NOSYSTEM=1` changes nothing measurable.

## Work packages

Each package names its method, its deliverable and its exit criterion. They
are independent; run them in any order, though WP1 feeds WP2 and WP3.

### WP1. Spawn census for every operation

Method: extend `.scratch/test-speed/tools/measure2.py`, which wraps
`subprocess.run` and `subprocess.Popen` in-process and tabulates git argv with
paths and identities elided. Cover every operation the tests exercise:
`prepare`, `collect`, `close` and `close --plan`, `status`, `discover`,
`select`, `triage`, `retain`, `export`, the `resource` actions, keyed requests,
and `verify_inputs`. Drive each through `stewart.api` from one prepared
fixture so counts are per operation, not per test. Record for each: total
spawns, distinct argv, repeated argv with counts, wall time, and the Python
call path for each repeat (a stack sample at the wrapper is enough).

Deliverable: `.scratch/test-speed/spawns/census.md` with one row per operation
and one table of repeats with their call sites, plus the raw per-call JSON.

Exit: every operation in `src/stewart/api.py` has a row, and the repeat table
names the function that issues each duplicate.

### WP2. Per-test cost decomposition

Method: for every test in the baseline receipt, split its recorded time into
fixture spawns (from the retained `commands/*/command.json` records in the
main checkout's artifacts, read only, or re-derived in this worktree from
`conftest.py` and `stewart_support.py`), in-process operation spawns (WP1
counts times the operations the test calls), CLI spawns (0.18 s plus the
operation's git), and residue. Classify each test's subject: CLI contract
(argv, exit code, JSON envelope), API behavior, custody invariant, or harness
and meta (`test_foundations.py`, `test_runner.py`, `test_authority.py`,
`test_distribution.py`, `test_orchestration_plan.py`).

Flag three kinds of waste with counts and seconds: tests that spawn the CLI
although their subject is not the CLI; parametrized sweeps whose cases do not
differ in the measured property; tests whose setup and preparation exceed
their assertion work by an order of magnitude.

Deliverable: `.scratch/test-speed/decomposition/by-test.csv` and a summary
table in the findings grouped by subject and by test file.

Exit: the residue column is under 10% of the suite, or the findings say what
it is.

### WP3. Overlap map and redundancy candidates

Method: build a static signature per test: operations called, refusal reason
identifiers asserted, fixtures used, markers, and the files it writes. The
suite defines 153 reason identifiers in `src/stewart`; 129 appear somewhere in
the tests and 24 never do, so the identifier set is a usable coverage axis.
Cluster tests whose signatures are equal or nested, with attention to the
files layered by review history: `test_close.py`, `test_close_regressions.py`
and `test_closeout_doubt.py`; `test_stewart_status.py` and
`test_exit_codes.py`; `test_request_keys.py`, `test_request_bindings.py` and
`test_action_bindings.py`; `test_stewart.py` and `test_stewart_cli.py`.

Confirm the top clusters by mutation: break one behavior in a scratch copy of
the installed package (the `installation` fixture and `stage_runtime` already
support deliberate mutation), run the cluster's tests with `-k`, and record
which tests fire. A test that never fires alone across the mutations tried is
a candidate. Budget: no more than about twenty mutations, each run under two
minutes.

Deliverable: `.scratch/test-speed/overlap/clusters.md` listing each cluster,
the mutations tried, which tests fired, and for each candidate the retained
test that covers the same failure. Candidates are evidence for the user's
decision, never deletions.

Exit: every cluster whose members sum to more than 30 s has a mutation
result, and no candidate is the only test asserting a reason identifier.

### WP4. Harness retention and independence

Method, retention: list what one run retains by category (checkout, worktree,
private HOME, `commands/` records, staged runtime copies, nested venvs from
`test_runner.py`) with sizes from the baseline artifacts directory. For each
category state whether re-running the single test reproduces it; a passing
test's tree is reproducible in seconds. Note that pytest 7.4.3 supports
`tmp_path_retention_policy`, and that `private_manager_storage` creates its
HOME beside `tmp_path`, outside that policy's reach.

Method, independence: audit every test for state shared across processes:
fixed paths (`test_foundations.py` uses `/tmp` directly), ports, `Path.home()`
assumptions outside the private HOME, environment mutation without
`monkeypatch`, and anything that reads the artifacts directory. Confirm the
`serial` marker is unused. From the baseline durations, compute a file-level
bin packing for 2, 3 and 4 shards and the resulting longest shard.

Deliverable: `.scratch/test-speed/harness/retention.md` and `independence.md`.

Exit: the retention table says for each category whether it is reproducible,
and the independence audit lists every finding with a file and line.

### WP5. Validate the two known levers with firing controls

Method, git binary: the three resource tests above are the differing case.
Add an invariance case: a test that spawns no git (for example one from
`tests/test_stewart_ledger.py`) must not change. Record the shim and direct
timings for both selections with the binary path named in the receipt.

Method, walkers: this worktree's `.scratch` is nearly empty, so the 81 s and
58 s will not reproduce here. Build a synthetic bloat of about 200k empty
files under `.scratch/test-speed/bloat/`, time the current `source_python`
and a pruned walk against it, then remove the bloat. For the sdist, build
once with the current configuration and once with `.scratch` excluded, with
the bloat present, through `python -I -B -m build --sdist --no-isolation`.

Deliverable: `.scratch/test-speed/levers/` with both comparisons.

Exit: each lever has a firing control, a differing case and an invariance
case recorded with actual counts.

## Deliverables

- `TEST-SPEED-FINDINGS.md` at the worktree root: the decomposition summary,
  the ranked levers with measured savings where WP5 measured them and
  estimates clearly labeled elsewhere, the redundancy candidates with their
  evidence, and the harness findings.
- `.scratch/test-speed/` holding every receipt, script and raw table the
  findings cite.
- No changes under `src/stewart`, no deletions under the main checkout, no
  commits unless the user asks.

## Exit criteria

The findings answer, with numbers traceable to retained evidence: how much of
the 34 minutes is git spawn cost, how much of that is duplicate work inside
operations, how much is fixture and CLI overhead, which tests are redundancy
candidates and why, what a run must retain, and whether the suite can be
sharded safely.
