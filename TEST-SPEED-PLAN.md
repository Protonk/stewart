# Test speed and evidence retention plan

Status: pending. Start with bounded measurements and improvements to the test
harness, then investigate the remaining costs. `TEST-SPEED-DESIGN-CHOICES.md`
sets out the implementation constraints. Remove both files when their
contracts have reached documentation and tests; keep unresolved work explicit.

The `test-speed` branch now includes `main` at `764d97e`, including the last
resource-containment and close-plan repairs. `rehome` has merged. There is no
merge dependency to wait for. The repair validation collected 992 tests;
the 966-test measurements below are a historical baseline, not the current
population. Do not rewrite those receipts or combine their timings with a
different population as though they measured the same suite.

The question is which changes reduce elapsed time and retained bulk while
preserving independent tests, custody checks and the evidence needed to
understand a run. An exhaustive census and test deletion are not prerequisites
for the inexpensive harness improvements.

## Ground rules

- Work in this worktree. Leave sibling branches, files and historical
  artifacts alone. The main checkout is on `main`; check actual branch and
  process state at pickup instead of assuming another session is idle.
- Local evidence is under `.scratch/test-speed/baseline/` and
  `.scratch/test-speed/tools/`; `.scratch/wheelhouse` holds the locked wheels.
  These ignored files may be absent in a fresh checkout. If so, mark the old
  measurements unavailable and make bounded new comparisons; do not invent
  missing provenance or require another worktree's retained trees.
- During investigation use focused selections and keep each run to about two
  minutes of tests. One interpreter and one check invocation at a time; check
  for competing processes with `ps aux | rg '[p]ytest|[c]heck.py'`. Use full
  runs for the final implementation gate, not repeatedly to rank ideas. Run
  the two supported interpreters sequentially. Parallel workers are a later,
  explicitly measured option within one invocation.
- Do not pass a test file path to `scripts/check.py`. It appends its own
  `tests` path as well, so pytest collects and runs every selected test twice
  (observed: 6 passed for 3 selected). Use `-k` until that is fixed.
- Commands use an explicit interpreter in isolated mode, for example
  (create the result directory first and use a fresh result name per run):

  ```
  /opt/homebrew/bin/python3.11 -I -B scripts/check.py --result .scratch/test-speed/<topic>/<name>.json -k "<expression>" > .scratch/test-speed/<topic>/<name>.out 2>&1
  ```

- Measurement discipline, from `AGENTS.md`: a clean result needs a firing
  control, a case differing in the measured property, and an invariance case.
  An explanation stays a hypothesis until a comparison distinguishes it from
  its rivals. Preserve command outputs, name the selector, and report actual
  collected, selected and deselected counts. Repeat comparisons in interleaved
  order under comparable load; retain individual timings and their spread.
- For every comparison record the actual Git executable and version,
  interpreter, wheel digest, test/harness/configuration source identity
  (commit plus changed-file digests when dirty), full argv and cwd, selector,
  worker count, permission context and competing load. The wheel alone does
  not identify the tests. Keep pytest stdout/stderr: today's `.log` contains
  provisioning and build output, not the inherited pytest streams.
- Separate environmental refusals from measured behavior. The latest repair
  runs failed at an AF_UNIX socket bind under the default sandbox, while the
  unchanged test passed with permissions enabled. Preserve each original
  outcome and the separate comparison; do not relabel a failed full run.
- Keep evidence under `.scratch/test-speed/<topic>/`. Write findings to
  `TEST-SPEED-FINDINGS.md` at the worktree root with every number traceable
  to a file under `.scratch/test-speed/`.
- Scope starts with `scripts/check.py`, test infrastructure and build
  configuration. Runtime changes require the targeted evidence and
  revalidation analysis in WP5. Test removal is a separate follow-up in WP6;
  neither is required to deliver the initial harness improvements.

## Historical observations and limits

Source for the suite numbers: `.scratch/test-speed/baseline/repair-311.json`
(Python 3.11.17) and `repair-314.json` (Python 3.14.8). Both runs ran at the
same time, so contention may have affected their timings by an unknown amount.
Per-operation numbers come from in-process counting with the scripts under
`.scratch/test-speed/tools/`, taken while another session had five test
processes running. Treat the table as observations under those conditions and
leads to validate, not an attribution of the entire current suite's runtime.

| Fact | Value |
| --- | --- |
| Suite | 966 tests, 2045 s on 3.11, 2103 s on 3.14, 965 passed 1 skipped |
| Per-test call time | median 1.53 s, p75 2.58 s, p90 4.12 s, p99 9.08 s |
| Per-test setup time | median 0.17 s; separately measured checkout setup includes six git spawns |
| Four largest tests | authority 81.1 s, distribution 58.0 s, journey 25.4 s, runner 19.9 s; 184 s together |
| Everything else | a long tail; 767 of 966 tests exceed 0.5 s |
| Subprocesses through the `run_cmd` fixture | 7680 in one run, including 6860 git, 585 `python -m stewart`, 199 other python |
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

Two outliers have identified traversal costs:

- `tests/test_authority.py::test_audit_custody_machinery_has_one_home` calls
  `source_python`, whose `rglob("*.py")` walks every entry under `.scratch`
  before the filter discards them. A walk that prunes the excluded top-level
  names first takes 0.04 s on the same tree.
- `tests/test_distribution.py::test_sdist_builds_same_wheel_without_git_or_network`
  builds an sdist from the project root. The sdist target sets
  `ignore-vcs = true`, lists `include` rather than `only-include`, and excludes
  no scratch directory, so hatchling's `recurse_project_files` walks
  `.scratch`. Hatchling prunes directories named in `exclude` before descending.

Not supported under the measured conditions:

- Bytecode: a CLI spawn cost about 0.18 s with or without compiled `.pyc`
  files; that comparison did not show a useful saving.
- git fsync: `core.fsync=none` and `core.fsyncMethod=batch` leave the
  init-config-add-commit sequence at 150 ms either way.
- git config lookup: `GIT_CONFIG_NOSYSTEM=1` changed nothing measurable.

Revisit these only when a changed environment or new evidence justifies it.

## Work packages, in order

### WP1. Validate and implement the inexpensive fixes

Start with three narrow changes, recording before/after selections under the
measurement contract above:

1. Compare Apple's Git shim with the executable found by `xcrun --find git`.
   Use Git-heavy tests as the firing/differing cases and a no-Git case for
   invariance. If the saving holds, add harness-local executable selection
   and record what actually ran; leave Stewart's runtime Git invocation alone.
2. Prune excluded directories before the authority test's source traversal
   and exclude scratch/venv directories from sdist traversal. Use bounded
   synthetic bloat in this worktree for the firing comparison, a clean tree
   for invariance, and verify unchanged source/member sets. Keep the build's
   independence from Git. Remove only the synthetic bloat created for this run.
3. Fix positional test selection so `scripts/check.py` does not also pass the
   whole tests root. Resolve paths/node IDs against the staged suite. Verify
   unique selected nodes, including overlapping paths, correct `-k`/`-m`
   filtering, and unchanged default and smoke selections.

Deliverable: focused harness/configuration changes, their regression coverage,
and comparisons under `.scratch/test-speed/levers/`. Do not infer suite-wide
savings from a small sample; identify extrapolations explicitly.

### WP2. Bound retention while preserving evidence

Inventory one available run by category: checkout/worktree, private HOME,
command records, staged runtime and nested environments. Use the retention
contract in design choices section 7 when implementing cleanup. Always
retain the run receipt, actual pytest streams, provisioning/build log, wheel,
test-source identity and comparison data. Allow selected passing controls and
their command records to be retained for evidence runs.

Cleanup may remove bulky artifacts of known passing tests only after setup,
call and teardown outcomes are known. Preserve failures in any phase and
interrupted or unresolved tests, including their sibling HOME directories.
The pinned pytest's `tmp_path_retention_policy = "failed"` alone does not
provide this contract: its fixture cleanup uses the call outcome and can run
before a teardown failure is known. A rerun is a new observation, not recovery
of the original evidence.

Deliverable: bounded default retention, an explicit way to retain selected
passing evidence or all artifacts, and focused regressions for passing
cleanup, each failure phase, interruption and selected retention. Show the
space difference and that outcome/membership evidence remains available.
Historical artifacts in other worktrees remain untouched.

### WP3. Reassess the remaining cost

After WP1 and WP2, repeat the same bounded selections under the same source
population, Git, permissions and load conditions. Identify the largest
remaining costs and choose the next useful work. Keep `--fast` as the small
smoke selection. The historical `not heavy` selection took about 1794 s
against smoke's 84 s; a broader tier needs a separate name and measured cost.

Use a representative per-file or per-subject decomposition where it changes
the decision. Separate measured time from estimates based on static call
counts, and leave unexplained time visible. Do not require every test to be
explained within a fixed residual percentage before delivering useful fixes.
Centralizing invocation helpers can improve consistency; do not share mutable
prepared sessions to make the numbers smaller.

Deliverable: a ranked residual-cost table in `TEST-SPEED-FINDINGS.md`, with
measured savings, estimates and uncertainties separated. Decide whether WP4
or WP5 is warranted, and state what is deferred. WP6 is independent follow-up.

### WP4. Sharding, if remaining wall time warrants it

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
Per-worker limits may be additional limits, never a replacement.

Deliverable: if adopted, opt-in workers (default one), documented aggregate
receipt semantics and regressions that inject membership errors and worker
failures as well as compare serial/parallel outcomes. Do not select a default
worker count from core count alone.

### WP5. Investigate specific runtime Git observations

Start with operations implicated by WP3. Inspect the instrumentation before
extending it: `measure2.py` currently wraps `subprocess.run` only, despite its
README; `measure.py` also wraps `Popen`. Account for both without double
counting and distinguish in-process calls from child processes whose internal
spawns the wrapper cannot see. Use isolated fixtures in the state appropriate
to each operation; an exhaustive API census is optional.

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

The initial work is complete when WP1/WP2 changes are implemented and verified
(or a measured rejection explains a candidate), WP3 assesses the residual
cost, and any chosen WP4/WP5 work meets its contract. Deferred investigations
or consolidation need not block delivery. Run focused checks as changes land;
at the implementation gate run the full installed-wheel suite with both
supported explicit interpreters sequentially. Report failures, permission
constraints and opt-in harness skips as observed, with separate reruns when
needed. Do not convert a changed test population into a claimed speedup.

Carry the accepted contracts into help, durable documentation and regression
tests, retain any pending work in a concise handoff, and remove the completed
planning files. Use focused commits so harness changes, runtime optimizations
and any later test consolidation remain separately reviewable.
