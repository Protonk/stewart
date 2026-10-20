# Test speed findings

Findings for `TEST-SPEED-PLAN.md`, one section per work package. Every number
names its source under `.scratch/test-speed/` (paths below are relative to
it). Each run's `<name>.provenance.json` records the interpreter, Git, source
identity, argv, selector, permission context, load and `.scratch` entry count;
`<name>.json` is the receipt. Historical observations are labelled as such and
are not combined with new measurements.

## WP0. Pickup, provenance and reference

**Pickup** (`pickup/pickup.out`). Worktree clean on `test-speed` at `51c53af`;
four worktrees registered (main, an audit kit under `/private/tmp`,
`stewart-rehome-scope-manager`, this one); no competing pytest or `check.py`
process; Python 3.11.17 and 3.14.8 under `/opt/homebrew/bin`; every wheelhouse
wheel matches its `requirements.lock` hash; all local evidence the plan names
is present and `baseline/repair-followups/SOURCES.sha256` verifies. Apple Git
2.54.0 (Apple Git-157) at `/usr/bin/git` (the xcrun shim) and at
`/Applications/Xcode.app/Contents/Developer/usr/bin/git`. Machine: Mac17,3,
10 cores (4 performance, 6 efficiency), 16 GB.

**Permission context.** No Claude Code sandbox is configured in this session
(no `sandbox` setting; the shell is launched directly by `claude`), and the
socket probe that binds an AF_UNIX socket under `/tmp` as
`test_socket_and_empty_runtime_refuse` does succeeds in the default context
(`pickup/pickup.out`). The user approved running every reference, timed and
gate run in this default context. Every run below is therefore labelled
`unsandboxed`, and the helper refuses a label its probe contradicts. The
historical sandbox refusal was not reproduced here.

**Plan correction, committed separately (`77711f7`).** The plan's `run_cmd`
counts (11,912 records / 10,422 git for 966 tests; 12,173 / 10,677 for 992)
counted records twice: `plan-review/receipt_summary.py` globbed
`*/commands/*/command.json`, and `*` also matched pytest's `<prefix>current`
symlinks. Under real directories only the counts are 7,680 / 6,860 and
7,901 / 7,076 (`pickup/run-cmd-count/count_records.out`,
`kinds_without_links.out`; `plan-review/receipt_summary_corrected.out` differs
from the original output only in those lines). The user chose to correct the
plan and continue.

**Tools** (all ignored by Git):

- `tools/run_check.py` wraps one `check.py` invocation without changing it:
  refuses a used result name, probes the socket bind against the permission
  label, records the provenance fields of the ground rules before the run,
  captures `<name>.out`, and adds exit status, wall time, receipt counts,
  wheel digest and selected phase sum afterwards. From the second reference
  on it also samples load and busy processes outside its own process tree
  every 10 s into `<name>.load.jsonl` (the first reference has before/after
  load only).
- `tools/git-log/bin/git` logs one line per call (time, pid,
  `PYTEST_CURRENT_TEST`, cwd, quoted argv) and `exec`s `/usr/bin/git`;
  `tools/count_gitlog.py` attributes lines to selected nodes. Counts only.
- `tools/compare_timings.py`, `compare_nodes.py`, `per_node.py`,
  `make_bloat.py` for the later comparisons.

**Selections** (`selections.json`):

| Name | Selector | Selected / collected | Role and evidence |
| --- | --- | --- | --- |
| `walkers` | `-k` the two walker names | 2 / 992 | WP1.2 firing/differing case |
| `git-heavy` | `-k` five names | 5 / 992 | WP1.3 firing/differing case. The five tests with the most logged Git calls among 22 candidates: 1,256 (journey), 872, 650, 533, 529 (`selection/count-a.counts.out`; candidates and the other 17 in `selection/rank_git_records.out`, `count-b.counts.out`) |
| `no-git` | `-k` ten names | 10 / 992 | WP1.3 invariance case: static or in-process tests using neither `checkout` nor `run_cmd`; the wrapper logged no call naming them and no unattributed call besides the helper's own two probes (`selection/count-nogit.counts.out`). Three other candidates call `git ls-files` and were dropped |
| `smoke` | `--fast` | 25 / 992 | existing smoke tier (`selection/collect-fast.json`) |

`run_cmd` records are a gross lower bound on Git use: the journey test has 19
git records (`selection/rank_git_records.out`) but 1,256 logged calls, nearly
all from in-process `stewart.api` operations (969 `rev-parse`;
`selection/count-a.counts.out`). The five `git-heavy` tests take about 47 s
together today, not the plan's "about two minutes"; their historical durations
sum to 87.9 s under contention (`selections.json`).

**References.** Both pre-change full runs on 3.11 at `77711f7` (test and
harness identical to `764d97e`): 992 collected and selected, 991 passed,
1 skipped (the real-harness probe), wheel `ce003ae9…`, which equals the
historical 992-test wheel; the collected node list equals the historical one
in order (`reference/vs-historical.out`) and the two references' lists are
identical (`reference/nodes-r1-vs-r2.out`).

| Run | `total_seconds` | Load | `.scratch` entries before → after |
| --- | --- | --- | --- |
| `reference/full-311` | 1409.8 | `duetexpertd` (a macOS daemon) at ~99% of one core from about 20:44, roughly 13 of the run's 23.5 minutes (seen in `ps` after the run; not sampled); drafting agents active (file reads and wheel unzips only, no test or build processes); `reference/load-notes.txt` | 8,626 → 213,558 |
| `reference/full-311-r2` | 1263.3 | sampled every 10 s, max 1-minute load 3.12, only sporadic system daemons (`load_during` in its provenance); the user had stopped another project's test runs | 213,822 → 418,620 |

The second reference was taken because the first overlapped the daemon; both
are kept. Same source, same wheel, same nodes: all non-walker nodes took
1405.1 s in the first and 1256.3 s in the second (−10.6%); 869 of 992 nodes
were faster; per-node ratio median 0.896, 5th–95th percentile 0.71–1.01
(`reference/aa-noise.out`). Run conditions alone therefore moved a full run by
about 10%, and a single before/after full-run comparison cannot attribute a
smaller difference to a change. WP3 compares against `full-311-r2`. The
historical 992-test 3.11 run took 2410.0 s for the same wheel and nodes while
its 3.14 twin ran concurrently (`plan-review/receipt_summary.out`); a full run
here takes about 21–24 minutes, not 40.

**Walkers in this worktree.** Their cost tracks the running checkout's
`.scratch` (setup + call + teardown; `baseline-wp0/summary.out`):

| `.scratch` entries at start | authority | sdist |
| --- | --- | --- |
| 8,626 (`full-311`) | 0.11 s | 1.02 s |
| 213,822 (`full-311-r2`) | 1.99 s | 1.62 s |
| 418,623–423,601 (`baseline-wp0/walkers-*`) | 3.83–3.87 s | 2.44–2.46 s |

About 0.9 s per 100,000 entries for the authority walk and 0.35 s per 100,000
plus about 1 s for the sdist test, on this machine. The historical 65.4 s and
44.6 s came from the main checkout's much larger `.scratch` (about 2.7 million
entries, not re-measured) under contention.

**Baseline selections** (WP0.6; three round-robin rounds, 3.11, default
context; `baseline-wp0/summary.out`, each run's provenance and `.load.jsonl`):

| Selection | Phase sum median (range), s | `total_seconds` median (range) |
| --- | --- | --- |
| `walkers` | 6.290 (6.267–6.332) | 9.305 (9.206–9.480) |
| `git-heavy` | 47.151 (47.094–47.467) | 50.078 (50.059–50.467) |
| `no-git` | 1.177 (1.170–1.178) | 4.321 (4.175–4.540) |
| `smoke` | 5.629 (5.566–5.658) | 8.638 (8.447–8.700) |

Every run selected its expected count with identical outcomes; maximum
sampled 1-minute load 2.2. Each run retains its artifacts, so `.scratch` grew
from 418,623 to 425,798 entries across these runs. The authority walk is 3.84
of `smoke`'s 5.63 s.

**Move to Python 3.14 only.** After the 3.11 baselines the user decided to
drop Python 3.11. `db61a8d` sets `requires-python = ">=3.14"` and updates the
README, the bundled guidance, the distribution test's metadata assertion and
`LINUX-CONTAINERS-PLAN.md`. Under 3.11, `check.py` now stops at wheel
install with pip's "requires a different Python: 3.11.17 not in '>=3.14'"
(`support-314/refused-311.out`); on 3.14 the metadata and sdist tests pass
(`support-314/focused-314.json`: 2 of 992 selected, 2 passed). Everything
above is 3.11 and now historical; the rows below are the baselines WP1 to WP3
use, and the two sets are never combined.

**3.14 reference** (`reference/full-314`, `db61a8d`): 992 collected and
selected, 991 passed, 1 skipped; wheel `ac7d4271…`; `total_seconds` 1362.6;
node list identical to the 3.11 references (`reference/nodes-r2-vs-314.out`).
Load sampled every 10 s, max 1-minute load 3.52; interactive foreground load
was present: a Safari WebKit process up to 81% CPU in 52 of 137 samples and
WindowServer up to 42% in 87 (`load_during` in its provenance). `.scratch`
grew from 426,259 to 630,454 entries.

**3.14 baseline selections** (three round-robin rounds, default context,
`db61a8d` source; `baseline-wp0-314/summary.out`):

| Selection | Phase sum median (range), s | `total_seconds` median (range) | Walkers inside |
| --- | --- | --- | --- |
| `walkers` | 12.085 (12.004–12.102) | 15.364 (15.174–15.858) | authority 7.90–8.03 s, sdist 4.05–4.16 s |
| `git-heavy` | 50.129 (49.784–50.287) | 53.453 (53.166–53.642) | |
| `no-git` | 1.169 (1.155–1.172) | 4.629 (4.451–4.757) | |
| `smoke` | 9.851 (9.776–9.987) | 13.114 (12.917–13.299) | authority 7.94–8.08 s |

All with expected counts and identical outcomes; `.scratch` at 630,459 to
637,633 entries; maximum sampled 1-minute load 2.72; Safari WebKit and
WindowServer appear among busy foreign processes in several runs (each run's
`.load.jsonl`). On 3.14 the authority walk costs about 1.3 s per 100,000
entries at this size.

**Second plan correction (WP1.3).** Design choices section 1 said inserting
xcrun's Git directory before `/usr/bin` changes 48 names (24 shim, 24 other
files). It changes 111: 22 shim (Homebrew's `python3`, `pip3` and `pydoc3`
come earlier and stay), 24 other files, and 65 that resolved nowhere before,
among them `python3.9`, `pip3.9`, `pydoc3.9`, `2to3` and `scalar`
(`levers/git/changed_names.out`); the plan-review probe counted only names
with a `/usr/bin` entry. The user chose to time a third condition, a
directory holding only a `git` wrapper script, and to prefer it. The plan
and design choices were corrected in `b7985c9`.

**Residual cost found on the way (for WP3).** pip runs `rustc --version`
whenever `rustc` is on PATH (its user-agent string; 0.5 s timeout), even with
`--no-index`. Homebrew's rustup proxies are on PATH here, so in a test's empty
private HOME the proxy starts installing the stable toolchain from the network
until pip kills it. Each nested `check.py` makes three such pip calls
(`residual/rustup/proxy-calls.log`); eight reference tests left `.rustup`
trees of up to 34 MB, two with a partial `stable-aarch64-apple-darwin`
toolchain (`residual/rustup/README.txt`). Not changed; see WP3.

## WP1.1. Positional selection without duplicates

Implemented (Python 3.14, default context; evidence under `levers/selection/`):

- `scripts/check.py` no longer passes the staged `tests` directory, so pytest
  falls back to `testpaths` without a positional argument and collects a
  named file once. Arguments still reach pytest unchanged; `--help` and the
  README describe the `tests/<file>.py[::<test>]` form (`check-help.out`).
- `tests/conftest.py` refuses, with `pytest.UsageError`, tests outside the
  staged `tests` directory (named by path, because pytest gives a module
  outside its rootdir a node ID relative to the argument that named it, so
  such IDs can collide) and then any node collected more than once.
- pytest 7.4.3 calls `pytest_collection_finish` in a `finally` around
  `pytest_collection_modifyitems`, so the core change alone would have let a
  refused selection record every collected node as selected, and the
  empty-selection refusal already replaced pytest's own errors ("file or
  directory not found", an unparsable `-k`). A selection now counts as
  selected only after pytest's selection hooks finish; a refused or failed
  one records its collected nodes, nothing selected and 0 deselected, and
  pytest's error reaches the caller.
- Gap closed by the user's choice: with only paths outside the suite pytest
  never loads the staged conftest (its initial conftests anchor on the named
  paths), so no boundary check, refusal or receipt happens and pytest exits
  0. `check.py` now fails such an invocation (exit 1) and names the
  `tests/<file>.py` form. Side effect: pytest options that never start a
  session (`--version`, `--markers`) passed through `check.py` also exit
  nonzero.
- The `suite` case of `test_runner_measures_each_selected_boundary` no longer
  replaces the removed argument and still refuses with "wrong staged test
  suite".

Evidence:

| Run | Selector | Collected / selected | Outcome |
| --- | --- | --- | --- |
| `before-path-k` (3.11, `77711f7`) | `tests/test_runner.py -k test_budget_charges…` | 995 / 2 (the same node twice) | 2 passed |
| `before-path-k-314` (old `check.py` and conftest, current tests) | same | 1013 / 2 (the same node twice) | 2 passed |
| `after-path-k` | same | 12 / 1 | 1 passed |
| `collect-unfiltered` | `--collect-only -q` | 1001 / 1001 | equals `reference/full-314`'s 992 in the same order plus exactly the 9 new nodes, none repeated (`collect-unfiltered-vs-reference.out`) |
| `regressions-old-harness` (old `check.py` and conftest) | `-k` the four new tests | 1001 / 9 | 6 failed, 3 passed |
| `harness-files-new` | `tests/test_runner.py tests/test_foundations.py` | 54 / 54 | 54 passed |

Regressions (9 nodes in `tests/test_runner.py`, each one `check.py`
invocation over `support.reduced_project`): a file plus a node ID from another
file runs each once; `-k` with `--deselect`, and `--fast`, select and deselect
as before; a file plus one of its node IDs is refused with the repeat named;
an empty selection is still refused; a missing path and an unparsable `-k`
report pytest's own error with nothing selected; tests named by absolute
paths outside the suite are refused by path; an outside path alone fails the
invocation. Against the unchanged harness the six firing cases fail for the
intended reasons (exit 0 without refusal, every probe collected twice, the
empty-selection message instead of pytest's, all collected nodes recorded as
selected); the keyword, fast and empty cases pass on both, as controls
(`regressions-old-harness.out`).

Cost: each new node is one nested `check.py` run of about 3.9 s, 35.0 s for
the nine (`wp11-cost.out`), about 2.6% of `reference/full-314`'s 1362.6 s.
Part of every nested run is pip's `rustc --version` probe (see WP0's
residual note), so the WP3 rustup finding grows with these tests.
PolicyWitness testing had resumed during the `harness-files-new`,
`after-path-k` and `collect-unfiltered` runs; none of them is a timing
comparison.

Addendum: README.md is the package's long description, so WP1.1's README
edit changed the wheel's `METADATA` and digest (`ac7d4271…` at `db61a8d`,
`f44ee152…` from `22d9d88` on); the package modules are byte-identical
(`levers/selection/harness-files-new.json`, `levers/pruning/files-new.json`).

## WP1.2. Prune the two walkers

Implemented: `tests/test_authority.py` walks with `os.walk` and removes the
top-level names `.scratch`, `.git`, `dist` and `build` from `dirnames` before
descending (`python_names`); `pyproject.toml` adds `/.scratch` to the global
hatch `exclude` and sets `skip-excluded-dirs = true` on the sdist target. The
authority test also records `os.scandir` at its real call site and fails if
the walk enters an excluded tree. The wheel is unchanged by WP1.2
(`f44ee152…` before and after).

Comparison (3.14, default context, PolicyWitness stopped; `walkers`
selection, old and new source interleaved three times at each level by
applying and reverting `levers/pruning/wp12.patch`; `levers/pruning/`):

| Level (`.scratch` entries) | Old phase sum, median (range) | New phase sum, median (range) | Verdict |
| --- | --- | --- | --- |
| existing tree (644,251–644,946) | 12.393 s (12.329–12.451) | 0.448 s (0.448–0.453) | new faster in every repetition (`compare-existing314-old-vs-existing314-new.out`) |
| plus 201,001 synthetic entries (846,204–846,899) | 16.745 s (16.694–16.890) | 0.453 s (0.448–0.455) | new faster in every repetition (`compare-bloat314-old-vs-bloat314-new.out`) |

- Firing: on the old source the bloat raised the walkers from 12.393 to
  16.745 s, every repetition (`compare-existing314-old-vs-bloat314-old.out`).
- Invariance: on the new source the walkers do not depend on the bloat
  (0.448 vs 0.453 s; ranges overlap; `compare-existing314-new-vs-bloat314-new.out`).
- Per walker (`per-walker.out`): authority 8.188 → 0.003 s and sdist 4.206 →
  0.445 s at the existing tree; 10.541 → 0.003 s and 6.188 → 0.449 s with
  the bloat. `total_seconds` medians 15.594 → 3.707 and 20.036 → 3.720.
- Populations: the authority name list (87 names) and the sdist member list
  (103 members) are identical across all four conditions, computed in a venv
  provisioned from the wheelhouse plus the built wheel
  (`pop-*.authority-names.txt`, `pop-*.sdist-members.txt`, `pop-*.json`).
  The bloat (201,001 entries) and the venv (1,562 entries) were removed
  afterwards (`bloat-remove.out`, `venv-remove.out`).
- A first attempt (`walkers-existing-old-1`, `ABORTED-existing.txt`) failed
  because the driver still named the 3.11 interpreter; it is kept and the
  series was rerun under new names.

Regressions, each shown failing against the old behavior on 3.14
(`demo-i-old-walk.out`, `demo-ii-old-pyproject.out`):

- `test_walk_prunes_excluded_top_level_trees_and_lists_what_rglob_listed`: on
  a planted tree (`.scratch/x.py`, `.git/g.py`, `dist/y.py`, `build/w.py`,
  `pkg/build/z.py`, a symlinked directory, a symlink to a directory named
  `alias.py`, a dangling `dangling.py`, a directory `odd.py`) `python_names`
  returns rglob's names, never enters an excluded tree and equals the old
  filter's output. With the old rglob walk it fails: "entered excluded
  top-level trees ['.git', '.scratch', 'build', 'dist']".
- `test_audit_custody_machinery_has_one_home` (changed): the old walk entered
  191,448 directories under `.scratch` on the real tree.
- `test_sdist_walk_never_enters_scratch_and_keeps_the_planted_members`: drives
  the pinned hatchling's `SdistBuilder` in-process with `safe_walk` recorded;
  with the old `pyproject.toml` the walk entered the planted `.scratch`
  directories. It also pins the two configuration keys.

Focused run: `tests/test_authority.py tests/test_distribution.py`, 22
collected and selected, 22 passed (`files-new`). The walk regression is in a
module marked `smoke`, so `--fast` now selects 26 nodes (25 at WP0); the sdist
regression is unmarked. Extrapolation, not measured: the saving grows with
the running checkout's `.scratch`; the main checkout's (about 2.7 million
entries) made these two tests take 65 s and 45 s historically.
