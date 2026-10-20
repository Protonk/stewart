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
process; Python 3.11.17 and 3.14.8 (`/opt/homebrew/bin/python3.11` and
`python3.14`, resolving to `/opt/homebrew/opt/python@3.1x/bin`); every
wheelhouse wheel matches its `requirements.lock` sha256 (matched by digest in
`pickup/pickup.out`; digests in `pickup/wheelhouse-digests.out`); all local evidence the plan names
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
from the original output only in its `run_cmd` record and git-verb lines, two
per receipt). The user chose to correct the
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
| `git-heavy` | `-k` five names | 5 / 992 | WP1.3 firing/differing case. The five tests with the most logged Git calls among 22 candidates (count-a's 7 and count-b's 15 selections, chosen from `selection/rank_git_records.out`): 1,256 (journey), 872, 650, 533, 529 (`selection/count-a.counts.out`; the other 17 in `count-a.counts.out` and `count-b.counts.out`) |
| `no-git` | `-k` ten names | 10 / 992 | WP1.3 invariance case: static or in-process tests using neither `checkout` nor `run_cmd`; the wrapper logged no call naming them and no unattributed call besides the helper's own two probes (`selection/count-nogit.counts.out`). Three other candidates call `git ls-files` and were dropped |
| `smoke` | `--fast` | 25 / 992 | existing smoke tier (`selection/collect-fast.json`) |

`run_cmd` records are a gross lower bound on Git use: the journey test has 19
git records (`selection/rank_git_records.out`) but 1,256 logged calls (969
`rev-parse`; `selection/count-a.counts.out`), mostly from the Git commands
Stewart runs inside the 43 `python -I -B -m stewart` children the test starts
(`run_cmd` records the CLI command, not the Git it runs;
`residual/gitcount/residual-per-node.json`), plus one in-process `prepare`. The five `git-heavy` tests take about 47 s
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
| `reference/full-311` | 1409.8 | `duetexpertd` (a macOS daemon) running from about 20:44, about 14 of the run's 23.5 minutes, at 99% of one core when observed two minutes after the run (its share during the run is unknown; not sampled); drafting agents active (file reads and wheel unzips only, no test or build processes); `reference/load-notes.txt` | 8,626 → 213,558 |
| `reference/full-311-r2` | 1263.3 | sampled every 10 s, max 1-minute load 3.12, only sporadic system daemons (`load_during` in its provenance); the user had stopped another project's test runs | 213,822 → 418,620 |

The second reference was taken because the first overlapped the daemon; both
are kept. Same source, same wheel, same nodes: all non-walker nodes took
1405.1 s in the first and 1256.3 s in the second (−10.6%); 869 of 992 nodes
were faster (`reference/aa-comparison.out`); over the 714 non-walker nodes
above 0.5 s the per-node ratio has median 0.896 and 5th–95th percentile
0.71–1.01 (`reference/aa-noise.out`). Run conditions alone therefore moved a full run by
about 10%, and a single before/after full-run comparison cannot attribute a
smaller difference to a change. (This set WP3's baseline as `full-311-r2`;
after the move to 3.14 below, WP3 compares against `reference/full-314`.) The
historical 992-test 3.11 run took 2410.0 s for the same wheel and nodes
(`plan-review/receipt_summary.out`) while its 3.14 twin ran concurrently
(per the plan; both logs in `baseline/repair-followups/` were created at
16:56:22); a full run here takes about 21–24 minutes, not 40.

**Walkers in this worktree.** Their cost tracks the running checkout's
`.scratch` (setup + call + teardown; `baseline-wp0/summary.out`):

| `.scratch` entries at start | authority | sdist |
| --- | --- | --- |
| 8,626 (`full-311`) | 0.11 s | 1.02 s |
| 213,822 (`full-311-r2`) | 1.99 s | 1.62 s |
| 418,623–423,601 (`baseline-wp0/walkers-*`) | 3.83–3.87 s | 2.44–2.46 s |

About 0.9 s per 100,000 entries for the authority walk and 0.35 s per 100,000
plus about 1 s for the sdist test, on 3.11 on this machine. Hypothesis, not
established: the historical 65.4 s and 44.6 s came from the main checkout's
larger `.scratch` (counted by hand at about 2.68 million entries, an
unretained observation in the plan's historical table) under contention. At
these rates 2.68 million entries would explain only about 24 s and 10 s; the
rest is unattributed.

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
(`support-314/refused-311.log`; the `.out` holds `check.py`'s error); on 3.14 the metadata and sdist tests pass
(`support-314/focused-314.json`: 2 of 992 selected, 2 passed). Everything
above is 3.11 and now historical; the rows below are the baselines WP1 to WP3
use, and the two sets are never combined.

**3.14 reference** (`reference/full-314`, `db61a8d`): 992 collected and
selected, 991 passed, 1 skipped; wheel `ac7d4271…`; `total_seconds` 1362.6;
node list identical to the 3.11 references (`reference/nodes-r2-vs-314.out`).
Load sampled every 10 s, max 1-minute load 3.52; interactive foreground load
was present: a Safari WebKit process up to 81% CPU in 52 of 137 samples,
WindowServer up to 42% in 87, and single samples of `duetexpertd` (97%) and
two `xcodebuild` processes (90%, 86%), among others (`load_during` in its
provenance). `.scratch`
grew from 426,259 to 630,454 entries.

**3.14 baseline selections** (three round-robin rounds, default context, at
`b7985c9`, a documentation-only commit on `db61a8d`;
`baseline-wp0-314/summary.out`):

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
whenever `rustc` is on PATH (its user-agent string, with a 0.5 s timeout:
`residual/rustup/pip-session-excerpt.txt`, from the bundled pip 26.2.1), even
with `--no-index`. Homebrew's rustup proxies are on PATH here, so in a test's empty
private HOME the proxy starts installing the stable toolchain from the network
until pip kills it. Each nested `check.py` makes three such pip calls
(`residual/rustup/proxy-calls.log`, observed on 3.11 at `77711f7`); in the
first 3.11 reference eight tests left `.rustup` trees of up to 34 MB, two
with a partial `stable-aarch64-apple-darwin` toolchain
(`residual/rustup/README.txt`); the later references' HOMEs also hold `.rustup`
trees. Not changed; see WP3.

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
  refused selection record every collected node as selected; already, the
  empty-selection refusal replaced pytest's "file or directory not found",
  and an unparsable `-k` reached the caller but recorded every collected node
  as selected. A selection now counts as
  selected only after pytest's selection hooks finish; a refused or failed
  one records its collected nodes, nothing selected and 0 deselected, and
  pytest's error reaches the caller.
- Gap closed by the user's choice: with only paths outside the suite pytest
  never loads the staged conftest (its initial conftests anchor on the named
  paths), so no boundary check, refusal or receipt happens and pytest exits
  0 (those tests run, without the suite's checks). `check.py` now fails such
  an invocation (exit 1) and names the `tests/<file>.py` form. Side effect:
  pytest options that end it before a session also exit nonzero: observed for
  `--version` (`version-option.out`, exit 1), inferred from pytest 7.4.3's
  code for `--markers`.
- The `suite` case of `test_runner_measures_each_selected_boundary` no longer
  replaces the removed argument and still refuses with "wrong staged test
  suite".

Evidence:

| Run | Selector | Collected / selected | Outcome |
| --- | --- | --- | --- |
| `before-path-k` (3.11, `f5ea437`, code identical to `77711f7`) | `tests/test_runner.py -k test_budget_charges…` | 995 / 2 (the same node twice) | 2 passed |
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
invocation. Against the unchanged harness the six firing cases fail (exit 0
without refusal, each named probe collected twice, the empty-selection
message instead of pytest's, all collected nodes recorded as selected); the
keyword, fast and empty cases pass on both, as controls
(`regressions-old-harness.out`; `-k` the four new test names, 9 of 1001
collected). Under the old harness the outside-path-alone case fails because
the outside test runs unrefused (the old harness still loaded the conftest),
so it does not isolate the receipt guard; with only the guard removed from
the new `check.py` it fails (`demo-no-receipt-guard.out`, 1 of 1019 selected,
1 failed; mutation in `mutations/no-receipt-guard.*`) and with the guard it
passes (`control-receipt-guard.out`, 1 passed).

Cost: each new node is one nested `check.py` run of about 3.9 s, 35.0 s for
the nine (`wp11-cost.out`, from `harness-files-new.json`, a correctness run
under PolicyWitness load; `regressions-old-harness.json` gives 34.2 s), about
2.6% of `reference/full-314`'s 1362.6 s; WP3's full run measures 35.8 s.
Part of every nested run is pip's `rustc --version` probe (see WP0's
residual note), so the WP3 rustup finding grows with these tests.
PolicyWitness testing had resumed during every 3.14 run in
`levers/selection/` from `regressions-old-harness` on (their `.load.jsonl`
samples); none of them is a timing comparison.

Addendum: README.md is the package's long description, so README edits
change the wheel's `METADATA` and `RECORD` and its digest: `ac7d4271…` at
`db61a8d` (`reference/full-314.json`), `f44ee152…` from `22d9d88` through
`8e968bf`, `8de99b31…` after WP1.3, `39199094…` after WP2, `c4a7987c…` after
the manual update (which also changes `stewart/resources/README.md`); every
other member is byte-identical (`wheel-members.out`).

## WP1.2. Prune the two walkers

Implemented: `tests/test_authority.py` walks with `os.walk` and removes the
top-level names `.scratch`, `.git`, `dist` and `build` from `dirnames` before
descending (`python_names`); `pyproject.toml` adds `/.scratch` to the global
hatch `exclude` and sets `skip-excluded-dirs = true` on the sdist target. The
authority test also records `os.scandir` at its real call site and fails if
the walk enters an excluded tree. The wheel is unchanged by WP1.2
(`f44ee152…` before and after).

Comparison (3.14, default context, PolicyWitness stopped (none in the runs'
load samples); `walkers` selection, `-k` the two walker names, 2 of 1001
collected on the old source and 2 of 1003 on the new, 2 passed each; old and
new source interleaved three times at each level by applying and reverting
`levers/pruning/wp12.patch`; `levers/pruning/`):

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
  the bloat. `total_seconds` medians 15.594 → 3.707 and 20.036 → 3.720
  (the two old-versus-new `compare-*.out`).
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
(`demo-i-old-walk.out`: 2 of 1003 selected, 2 failed;
`demo-ii-old-pyproject.out`: 1 of 1003 selected, 1 failed; PolicyWitness was
active during demo (i) and `files-new`, correctness runs only):

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
module marked `smoke`, so `--fast` gains one node (WP3 collects 38 = 25 + 1
+ 12 from WP1.3; `wp3/collect-fast.json`); the sdist regression is unmarked.
The saving was measured to grow from 11.9 s to 16.3 s between about 644,000
and 846,000 entries; beyond that range it is an extrapolation (see WP0 on the
historical times).

## WP1.3. Git executable selection in the harness

**Comparison before implementing** (3.14, default context, PolicyWitness
stopped; each condition an explicit PATH through the helper, Latin-square
order over three repetitions; `levers/git/`, `conditions.out` shows every
condition reaching Apple Git 2.54.0 with the developer exec path and
templates):

| `git-heavy` (5 of 1003) | Phase sum, median (range) | Change vs shim | Verdict |
| --- | --- | --- | --- |
| shim (inherited PATH, `/usr/bin/git`) | 49.702 s (49.517–49.704) | | |
| directory (`xcrun --find git`'s directory before `/usr/bin`) | 26.957 s (26.910–26.984) | −45.8% | established (`compare-git-heavy-shim-vs-directory.out`) |
| wrapper (`#!/bin/sh` git script before `/usr/bin`) | 35.347 s (35.178–35.578) | −28.9% | established (`compare-git-heavy-shim-vs-wrapper.out`) |

The directory was also established faster than the `sh` wrapper
(`compare-git-heavy-directory-vs-wrapper.out`). `no-git` showed invariance
for every pair (medians 1.158–1.172 s; `compare-no-git-*.out`). Per call
(`spawn_bench.out`, 200 interleaved `git --version` calls each): shim
7.99 ms, direct binary 2.44, `sh` wrapper 4.46, `dash` wrapper 3.29, `zsh -f`
wrapper 4.35. The five `git-heavy` tests made 3,840 logged Git calls
(`selection/count-a.counts.out`), so the in-suite shim-to-directory saving
is at most about 5.9 ms per logged call (an estimate: the 22.7 s median
difference over those calls, beside the micro-benchmark's 5.55 ms).

The directory insertion changes 111 names (`changed_names.out`: 22 that
were the shim, 24 that were other files, 65 newly resolvable), so per the
user's rule I asked before choosing; the user chose a `dash` wrapper after a confirmation run
(`confirm-*`, shim vs `dash` wrapper, alternating order):

| Confirmation | Phase sum, median (range) | Verdict |
| --- | --- | --- |
| `git-heavy` shim | 49.584 s (49.309–49.731) | |
| `git-heavy` `dash` wrapper | 30.523 s (30.498–30.674), −38.4% | established (`compare-confirm-git-heavy-shim-vs-wrapper-dash.out`) |
| `no-git` shim vs `dash` wrapper | 1.166 vs 1.170 s | invariance shown (`compare-confirm-no-git-shim-vs-wrapper-dash.out`) |

Against the directory result of the separate series run minutes earlier
the `dash` wrapper recovers about 84% of the directory's saving (not
interleaved with the confirmation; an estimate), matching the per-call
figures (85%). The choice is recorded in design choices section 1.

One aborted series is kept, not used: `ABORTED-zsh-splitting.txt` (a zsh
loop passed an empty PATH: `git-heavy` failed 5/5, `no-git` passed).

**Implemented**: `scripts/check.py --git-executable auto|path|/ABSOLUTE/git`,
default `auto`. `auto`, on darwin when git resolves to `/usr/bin/git`,
verifies the binary `xcrun --find git` names (a regular executable named
git, the shim's `--version`, an existing `--exec-path`, both inside
`xcode-select -p`), writes `<private dir>/git-selection/git`, a script for
`/bin/dash` (else `/bin/sh`) that `exec`s that binary by absolute path, and
inserts its directory immediately before the PATH entry that supplied the
shim. Otherwise PATH is unchanged and the reason recorded. `path` changes
nothing; an absolute path inserts that executable's directory by the same
rule (the logging wrapper goes in this way). Only the tests' environment gets
the PATH; provisioning and the build keep the inherited one. The record
(requested mode, inserted entry, the entry it precedes, wrapper path, shell
and target, resolved executable and realpath, version and exec path probed
under the tests' PATH, fallback, every changed name) goes to the `.log`, the
receipt (`git_selection`) and a one-line summary. Validation is an argparse
`type=`; an explicit executable the insertion cannot reach is refused. The
helper `tools/run_check.py` now copies `git_selection` into provenance and
labels its own Git field as the inherited PATH's.

Real `auto` through `check.py` (`auto-git-heavy`, single run, no PATH
override, 5 of 1016 collected, at `8e968bf` plus the uncommitted WP1.3 diff
whose `check.py` digest is the committed one): the wrapper targets the Xcode
Git, changed names `["git"]`, exec path the developer `git-core`;
`git-heavy` 31.540 s, 5 passed.

Regressions (13 nodes in `tests/test_runner.py`, 12 marked `smoke`): `auto`
writes the wrapper and inserts it before the shim's entry with only `git`
changed; nine fallback cases leave PATH unchanged and write no wrapper (git
already elsewhere, not darwin, no xcrun, xcrun failing, a symlinked
candidate, a version mismatch, outside the developer directory, a missing
exec path, `path` mode); explicit executables (insertion, a link on PATH,
probes under the tests' PATH, appending, already selected, refusal); option
validation and probe diagnostics; one end-to-end `check.py` run with an
explicit wrapper whose probe test sees the selected Git and exec path.
Firing (`demo-*.out`, each `-k 'git_selection or git_option or
selected_git'`, 13 of 1016 collected): against the old `check.py` all 13
fail; with `auto` inserting the developer directory, the tests keeping the
inherited PATH, no `.log` record, or the entry inserted first
(`mutations/*`), the targeted tests fail (1, 1, 1 and 2 of 13); restored, 13
pass (`wp13-nodes-new`). Focused run: `tests/test_runner.py
tests/test_foundations.py`, 67 collected and selected, 67 passed
(`harness-files-final`, at `7c8516c`, the pre-amend form of `7787b96`, which
differs only in this file; `harness-files-new` passed the same before a
one-line change to the summary wording).

Bypasses (read at `8e968bf`): `tests/test_auditor_runtime.py:125` builds
`PATH` from `os.defpath` and so reaches the shim; `tests/test_invocation.py`
sets `PATH=/absent` on purpose (lines 193, 196, 199);
`tests/test_stewart_launch_profile.py` (lines 56, 361, 385) prepends a stub
directory to the inherited PATH and so sees the selection;
`src/stewart/experiment.py:198` forwards PATH to auditor children, which now
see only the extra `git`. Stewart's runtime still runs `git` by name.
The README change moved the wheel digest again (`METADATA` and `RECORD`
only; `8de99b31…`; `wheel-members.out`).

## WP2. Bound retention while preserving evidence

**Inventory first** (`retention/inventory.py`; the figures are the 3.14
reference's, `inventory-reference-314.out`; the 3.11 reference's
`inventory-reference.out` agrees on top-level counts and on every share
within about 1 percentage point): `reference/full-314` (992 nodes, 991
passed, 1 skipped) retained 3.56 GB allocated in 204,184 entries; 991 test
directories, 991 private HOMEs and 489 pytest `current` links (the skipped
real-harness probe has neither). By allocated bytes: Git checkouts and
worktrees inside test directories 54.1%; other test-directory content 25.9%,
chiefly `api-manager-home` (0.767 GB, no Git; 82 of 103 `project` trees are
Git checkouts and count as repository; `inventory-reference-314-children.out`);
private HOMEs 16.3%, which also hold Stewart checkout worktrees under
`.local`; staged runtimes 2.0%; `run_cmd` records 1.3% (but 15.5% of
entries); nested virtual environments 0.4%. Nearly all bulk sits in the two
paths each node owns.

**Implemented** (ported onto WP1.3 by a subagent, then reviewed and run here):

- Receipt additions, leaving `node_outcomes` and `outcomes` unchanged:
  `phase_outcomes` (every phase, including passing setup and teardown),
  `owned_paths` (each node's `tmp_path` and sibling `-home`, recorded by the
  autouse fixture), `markers` (all of a node's marker names, so WP3 must
  filter for the tier markers), `suite_sha256` (every staged file),
  `check_sha256`, and `project_git` (commit, `git status` lines and dirty
  state when the project is the top of its own work tree, else `absent` with
  the reason).
- `check.py` relays pytest's stdout and stderr to the console and to
  `<name>.pytest.log`, each line labelled with its stream, so startup and
  collection failures are kept without a receipt. pytest no longer sees a
  terminal (no colour, width 80).
- After pytest exits, retention is planned from this invocation's receipt
  only (matched by its artifacts path; repeated keys refused). A node's owned
  paths go only when setup, call and teardown all passed, it is not named by
  `--keep-node`, and it did not exceed `--test-budget-seconds` (a conservative
  choice the plan neither requires nor forbids). Everything else stays:
  failed, skipped, interrupted and over-budget nodes, entries no node owns,
  anything not a directory. The plan is written into the receipt before the
  first removal; each path's result follows. Removal takes only verified
  direct children (device and inode re-checked), never a link, with
  `shutil.rmtree(onexc=…)` restoring owner permissions once; a `current` link
  goes only with its target. Removal failures are printed and recorded and
  change neither the exit status nor any outcome. Without this invocation's
  receipt nothing is removed.
- `--keep-artifacts failed|all` (default `failed`) and repeatable
  `--keep-node NODEID`. A named node that did not execute (no call phase, or
  a skipped one, which is how pytest reports skips and xfails) is recorded,
  fails the invocation and withholds all removal: an evidence run that lost
  its control is not evidence, and a mistyped ID must not cost the evidence
  meant to be kept. pytest's `tmp_path_retention_policy` is not used.

Regressions (3 nodes in `tests/test_runner.py`, 5 nested `check.py` runs over
`support.reduced_project`; every run below used `-k 'removes_only_unselected
or refuses_keep_node or records_removal_failures'`, 3 of 1019 collected): a passing node's `tmp_path` and HOME are removed;
setup, call and teardown failures each keep their HOME and command records;
an unowned directory stays; `--keep-node` keeps a passing node; a missing,
deselected, skipped or skip-marked `--keep-node` target is refused and
nothing is removed; `--keep-artifacts all` keeps everything; an interrupted
session keeps its incomplete node; a run killed before writing its receipt
removes nothing and leaves a stale receipt at the same path untouched; an
over-budget node stays; an injected removal failure is recorded without
changing the exit. Firing (`retention/`): against the old `check.py` and
conftest all 3 fail (`demo-old-harness.out`: `--keep-node` unknown, no
result, no retention plan); each of six single mutations (skipped
`--keep-node` accepted, a removal failure changing the exit, an unrecorded
removal failure, a stale receipt relabelled, an over-budget node removed, a
missing phase counted as passed; `mutations/<name>.patch`, each demo
receipt's `check_sha256` matching its patched `check.py`) fails exactly its
targeted test, 1 of 3 (`demo-*.out`). New harness: `regressions-new`, 3 of 3 passed; focused
`tests/test_runner.py tests/test_foundations.py`, 70 collected and selected,
70 passed, its own retention removing 140 directories and 34 links in 0.15 s
(`harness-files-new`).

The space this saves on a full run is measured by WP3's full run.

## WP3. Reassess the remaining cost

All runs on Python 3.14 in the default context; evidence under `wp3/`. For
the timed window the user stopped PolicyWitness and closed a Storage
settings scan (`wp3/load-notes.txt`). The full run's samples show
WindowServer up to 39% and brief samples of `duetexpertd` (100%, one
sample), Sublime Text (28%, two) and a Codex session, among others; max
1-minute load 2.64 (`full-314.provenance.json`). `fseventsd` stayed at or
below 32% while tests ran and peaked at 236% only in the last two samples,
during retention's removal and at exit (`fseventsd-timeline.out`). The
reference also had foreground load (WP0).

**Gate.** `wp3/full-314` at `5e41acf` (clean): no selector; 1019 collected,
1019 selected, 0 deselected; 1018 passed, 1 skipped (the opt-in real-harness
probe); `total_seconds` 855.7; Git through the `dash` wrapper (changed names
`["git"]`). An evidence review then corrected help, messages and
documentation (`cb8eed7`), which changes `check.py` and the shipped manual,
so the gate was rerun on the final source: `wp3/gate-314` at `e45824a` (code `cb8eed7`; clean, `project_git` not dirty): 1019 collected, 1019 selected, 0 deselected; 1018 passed, 1 skipped; `total_seconds` 853.8, wall 861.0 s; node list identical to `wp3/full-314`'s; retention removed 2,036 directories and 503 links in 7.0 s and kept nothing; load samples show WindowServer up to 39%, Safari WebKit up to 52% (9 samples), `talagentd` up to 43% (5) and `duetexpertd` 99% (1), among others, with `fseventsd` at or below 21% during the tests and 197% only at exit (`fseventsd-timeline.out`); max 1-minute load 3.41 (`gate-314.provenance.json`). PolicyWitness, including cases a Codex agent had started, was paused by the user (`load-notes.txt`). The project is 3.14-only,
so there is no second interpreter leg.

**Space (WP2).** In `wp3/full-314` retention removed 2,036 owned directories
and 503 `current` links in 7.3 s and kept nothing: every node passed, and the
skipped node had no directories. Retained artifacts went from 204,184
entries and 3.559 GB allocated (`reference/full-314`) to 0 entries; the
receipt grew from 0.6 MB to 2.3 MB; `.scratch` grew by 9 entries over the run
(`space.out`, `full-314.provenance.json`). Outcome and membership evidence
remain in the receipt (`phase_outcomes`, `owned_paths`, `markers`,
`retention`).

**Selections against the WP0 3.14 baselines** (selectors as in
`selections.json`, 1019 collected; three round-robin repetitions at
`5e41acf`; `selections-vs-wp0.out`, `compare-*.out`):

| Selection | WP0 phase sum, median (range) | WP3 phase sum, median (range) | Verdict |
| --- | --- | --- | --- |
| `walkers` (2) | 12.085 s (12.004–12.102) | 0.450 s (0.445–0.454) | faster in every repetition |
| `git-heavy` (5) | 50.129 s (49.784–50.287) | 30.373 s (30.307–30.518) | faster in every repetition (−39.4%) |
| `no-git` (10) | 1.169 s (1.155–1.172) | 1.179 s (1.158–1.214) | invariance shown |
| `smoke`, 25 shared nodes | 9.851 s (9.776–9.987) | 1.693 s (1.595–1.707) | faster in every repetition, same outcomes |

`smoke` now selects 38 nodes; the 13 new ones (WP1.2 and WP1.3 unit
regressions; membership in `wp3/collect-fast.json`) take 0.087 s together
(`selections-vs-wp0.out`). Each selection's non-test time (`total_seconds`
minus the phase sum, per run) rose by a median 0.22 to 0.45 s (walkers 0.45,
git-heavy 0.22, no-git 0.31, smoke 0.36), separated in every repetition
except for the walkers (`nontest-time.out`). WP1.3's probes and WP2's
digests, project status and stream relay are the likely sources, a
hypothesis: no comparison separates them from the larger collection (1019
against 992 nodes) and the larger `.scratch` (about 892,000 against 630,000
entries).

**Full run, node by node, against `reference/full-314`**
(`per-node-vs-reference.out`, `totals.out`): the 992 shared nodes took
1358.7 s and now 790.0 s (−568.7 s, −41.9%); 881 were faster and 111
slower; no shared node's outcome changed. The largest increases, +0.07 to
+0.33 s per node (0.07 to 0.25 s per nested run), are nested-`check.py`
tests, of the same order as the top-level rise above; the rest are small. The
walkers account for 7.35 s of the saving (authority 4.97 → 0.00 s, sdist
2.84 → 0.46 s). The other 561.3 s falls in the Git-using nodes: −461.3 s in
the in-process API tests and −100.9 s in the CLI-starting tests, against
−0.6 s for tests without Git or the CLI and +1.5 s for the nested-`check.py`
tests (`saving-by-group.out`, grouped as in `residual/gitcount/residual.out`).
At the measured per-call costs the Git change predicts 96,030 × (7.99 − 3.29)
ms ≈ 451 s, about 80% of that (an estimate; the rest lies within the roughly
10% that conditions alone moved a full run in WP0's A/A pair, and the
reference ran with foreground load). The same model reproduces the in-suite
`git-heavy` difference: 3,840 calls (the five nodes' logged calls,
`selection/count-a.counts.out` and `residual/gitcount/residual.out`) × 4.70 ms
= 18.0 s predicted, 19.1 s measured
(`levers/git/compare-confirm-git-heavy-shim-vs-wrapper-dash.out`).
New nodes, reported separately (27 nodes, 61.7 s): WP1.1 9 nodes 35.8 s,
WP1.2 2 nodes 0.0 s, WP1.3 13 nodes 4.4 s, WP2 3 nodes 21.6 s.

Marker tiers from the receipt (a node counts under each of its tier markers;
`unmarked` means none of `system`, `heavy`, `smoke`): `system` 719 nodes
690.4 s; `heavy` 62 nodes 107.1 s; unmarked 265 nodes 159.5 s; `smoke` 38
nodes 2.0 s, all of them also `--fast` (`smoke and not heavy`); `not heavy`
957 nodes 744.6 s. `--fast` is now 2.0 s of tests, where the authority walk
once dominated it.

**Where the remaining time goes** (`residual/gitcount/residual.out`: Git
calls per node from a full counting run with the logging wrapper,
`residual/gitcount/full-count`, 1016 collected, 1015 passed, 1 skipped at
`7787b96`, counts only; `run_cmd` spawns from that run's retained artifacts;
time from `wp3/full-314`; 1016 joined nodes, 830.2 s; the 3 WP2 nodes,
21.6 s, postdate the counting run). Measured time and counted spawns are
kept apart from estimates, which multiply counts by per-call costs measured
in isolation (`levers/git/spawn_bench.out`, `git --version` process starts;
`residual/bench/spawn_costs.out`):

| Rank | Subject | Nodes | Measured (of 830.2 s) | Counted | Estimate (not measured in the suite) | Not decomposed |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | in-process API tests that use Git | 661 | 543.1 s (65.4%) | 79,218 Git calls | Git process starts ≈ 261 s at 3.29 ms | ≈ 282 s: Git's own work after starting, Python work, file I/O, other subprocesses |
| 2 | tests that start the `stewart` CLI | 103 | 192.0 s (23.1%) | 535 CLI starts, 16,810 Git calls | CLI starts ≈ 57 s at `--help`'s 106 ms (bare interpreter 13 ms; real commands probably cost more); Git starts ≈ 55 s | ≈ 80 s, same contents |
| 3 | tests that run a nested `check.py` | 17 | 86.4 s (10.4%) | 21 nested runs (+5 in the 3 WP2 nodes, by construction: `tests/test_runner.py` lines 582, 655, 671, 702, 730 at `5e41acf`; 21.6 s outside the base) | pip's `rustc` probe ≈ 40 s: 25 provisioning runs (one counted run is refused before provisioning, `tests/test_runner.py` lines 431-435) × 3 pip processes (observed on 3.11 at `77711f7`, `residual/rustup/proxy-calls.log`; still the venv's ensurepip plus two installs in `scripts/check.py`) × +535 ms (693 vs 158 ms with rustup removed from PATH, each in a fresh empty HOME, whereas a test's runs share one HOME) | venv creation, lock install, wheel build, pytest start |
| 4 | static or in-process tests without Git or CLI | 233 | 8.3 s (1.0%) | | | |
| 5 | the walkers | 2 | 0.5 s (0.1%) | | | |

Outside the nodes: provisioning, build and collection (`total_seconds` 855.7
minus the 851.8 s phase sum) and 7.3 s of retention after `total_seconds`;
wall time 863.2 s (`full-314.provenance.json`).

The wrapper logged 96,632 Git calls: 96,030 attributed to nodes, 601 without
`PYTEST_CURRENT_TEST` (nested runs, rebuilt environments and `check.py`'s
own Git probes), and 1 naming an unselected node; tests that build PATH
without the inherited value bypass it and are not counted. Attributed calls
are 13.6 times the 7,078 `run_cmd` git records of the same nodes. By origin
(`residual/gitcount/verbs.out`): 89,511 carry Stewart's `-c core.hooksPath`
prefix (the runtime's own calls; 55,529 of them `rev-parse`) and 7,121 are
fixture and test calls (add 1585, commit 1584, config 1526, rev-parse 1520,
init 768). Starting the runtime's processes costs an estimated 294 s at
3.29 ms; what each call does after starting is unmeasured, so that is
neither Git's whole cost nor a ceiling on removing calls. Through the shim
the attributed calls would have cost about 767 s (an estimate).

**A concrete WP5 candidate** (counts measured, time estimated;
`residual/gitcount/verbs.out`): 9,857 complete `checkout_identity`
sequences, the four `rev-parse` queries `--is-bare-repository`,
`--show-toplevel`, `--absolute-git-dir` and `--path-format=absolute
--git-common-dir` issued in turn by one node in one directory
(`src/stewart/_repository.py:203-219`), account for 39,428 calls, 44.0% of the
runtime's (108 of the sequences come from unattributed lines). Asking all
four in one `rev-parse` process would avoid three process starts per check,
about 97 s (an estimate), plus repeated repository discovery (unmeasured),
with no observation reused across time. It needs WP5's custody argument: in
a bare repository, inside a `.git` directory and outside any repository the
merged call exits 128 after at most the first answer
(`residual/gitcount/revparse-merged.out`), so the
`repository_root` refusals must be decided from partial output, and its
newline-separated output cannot carry a path containing a line break, which
the separate calls preserve. Regressions must cover both.

**Recommendation on WP4 and WP5**, with expected benefit and uncertainty:

1. *First, outside WP4 and WP5 (small, for the user to approve):* keep
   rustup's proxies away from pip in `check.py`'s provisioning (a
   provisioning PATH without them, or `RUSTUP_AUTO_INSTALL=0`). Expected
   ≈ 40 s per full run for the PATH option (an estimate from isolated pip
   calls; `RUSTUP_AUTO_INSTALL=0` still starts the proxy for every pip call
   and is unmeasured), and no more network toolchain downloads into tests'
   private HOMEs. Measure it on the nested-`check.py` nodes before and
   after.
2. *WP5, targeted (approve if the total work per run matters; in the
   single-process suite it also shortens wall time):* start with
   `checkout_identity` (≈ 97 s, about 12% of the 830.2 s joined node time,
   an estimate) and the plan's instrumentation for the operations that issue
   it most; every removal needs a custody revalidation argument and
   regressions that change identity between checking and acting. The
   runtime's process starts are an estimated ≈ 294 s in all; merging calls
   also saves repeated discovery and configuration reads, which are
   unmeasured, so that figure is not a bound.
3. *WP4 (approve if wall time matters, after a probe):* file-level
   longest-first packing of WP3's per-file times gives 425.9 / 284.9 /
   213.1 s for 2 / 3 / 4 workers against ideals of 425.9 / 283.9 / 212.9 s
   (`wp3/packing.out`; the largest file is `tests/test_runner.py` at 77.3 s,
   the largest node 15.5 s), so packing does not limit 4 workers. That is a
   lower bound: it assumes no contention, and the only concurrent
   observation, the historical sandboxed shim-era 3.11/3.14 pair, ran each
   process at 1.63–1.83 times its solo non-walker time (`wp3/historical-pair.out`,
   confounded). The machine has 4 performance and 6 efficiency cores; how
   the file-event daemon and Git's own I/O behave under several workers is
   unmeasured (with one worker `fseventsd` stayed at or below 0.32 cores
   during tests). Before building
   WP4's membership machinery, measure two concurrent `check.py` invocations
   over disjoint file sets against the same sets run alone (this needs a
   deliberate exception to one check run at a time). The default stays one
   worker (plan WP4).
4. *Not recommended now:* the directory insertion would save about 0.85 ms
   more per Git call, ≈ 82 s per run (an estimate), at the cost of the 110
   extra names the user declined; moving CLI-start tests whose subject is
   not the CLI to `stewart.api` (WP6 territory) would save at most ≈ 57 s
   at `--help`'s start cost if every CLI start moved (an estimate; real
   commands probably cost more per start, but only an uncounted subset would
   move).

## Approved after WP3: provisioning PATH, `checkout_identity`, concurrency probe

The user approved WP3's three recommendations. All runs on Python 3.14 in
the default context. The two before/after comparisons, the probe and the
final gate ran in one window during which the user paused PolicyWitness and
a Codex agent's test runs (recorded in `final/gate-314.provenance.json`'s
note). Foreign load remained (`followup-foreign-load.out`): Safari WebKit over
100% in a few samples of each group (1 of 36 in the rustup comparison, 3 of 39
in the identity comparison, 2 of 75 in the gate) and, in the probe, more
often in the four-way batches of repetitions 2 and 3 (mean WebKit 72% and
65%, against 19–36% elsewhere); another session's Python tests
(`construction-broker-v2/broker_tests.py`) appear in a few probe and gate
samples. Both before/after comparisons applied their patch to `e9353fc`, so
each measures its change alone; the commit messages of `1d17cd8` and
`c762b26` misstate their populations as "1021/1023 collected", which should
read 1019 (old) and 1021 (new).

### Provisioning without rustc (`1d17cd8`; evidence under `rustup/`)

`check.py` runs `ensurepip` itself (venv's own `ensurepip` inherited
`os.environ`) and gives every provisioning command (ensurepip, both pip
installs, the build and any `--parity-output` run) the inherited PATH minus
each entry in which `rustc` resolves. The removed entries go to the `.log`
and to the result as `provisioning_path_removed`; the tests keep the
inherited PATH. The console test's own venv and pip install use the same
filtered PATH (`support.path_without_rustc`).

| Comparison (interleaved 3x; `rustup/compare/`) | Old phase sum, median (range) | New, median (range) | Verdict |
| --- | --- | --- | --- |
| `nested-check` (7 of 1019 old / 1021 new collected; each one nested `check.py`) | 27.515 s (27.129–27.698) | 14.618 s (14.353–14.698) | new faster in every repetition (−46.9%) |
| `no-git` (10) | 1.168 s (1.150–1.207) | 1.165 s (1.149–1.199) | invariance shown |

The saving is about 1.8 s per nested run, more than WP3's 1.6 s estimate.
With all artifacts kept, the outer tests' private HOMEs holding `.rustup`
went from 7 of 7 to 0 of 7 in every repetition, so the network toolchain
downloads stopped (`rustup/compare/summary.out`). `no-git`'s
`total_seconds` also fell from 4.802 to 4.402 s, probably because the outer
`check.py`'s own pip calls no longer start the proxy (a hypothesis). Regressions: `test_runner_withholds_rustc_from_provisioning`
(one nested run: a logging `rustc` stub first on PATH is never started
before the tests, while pip under the tests' PATH still starts it once, the
firing control, and the tests still reach it) and
`test_provisioning_path_drops_each_entry_that_supplies_rustc` (unit,
`smoke`). Against the unchanged `check.py` both fail, the nested one with
three `rustc --version` starts, one per pip process (`demo-old-check.out`);
venv's own ensurepip restored, `run()` inheriting PATH, or only the first
supplying entry removed each fails its targeted test
(`demo-env-builder-with-pip.out`, `demo-run-inherits-path.out`,
`demo-first-entry-only.out`; `mutations/`).

### WP5, targeted: one `rev-parse` for `checkout_identity` (`c762b26`; evidence under `wp5/`)

`checkout_identity` (`src/stewart/_repository.py`) asks `rev-parse
--is-bare-repository --show-toplevel --absolute-git-dir --path-format=absolute
--git-common-dir` in one process and decides from that answer only a clean
root: exit status 0, exactly four newline-terminated lines, `false`, three
absolute paths and a top level that resolves to the selected root. Every
other outcome, a refusal, a path holding a line break, an older Git, a
timeout or an `OSError`, replays `_separate_identity`, the previous four
queries unchanged, which make every refusal and raise every exception as
before. A clean root takes one Git process instead of four; any other
selection takes one more than before.

Observation and revalidation: each of the four queries discovered the
repository in its own process; now one process discovers it once and works
out each answer in turn, so a rename during the call can still give
disagreeing answers, as it could across four processes. Nothing is kept for
a later call: each call and each replay observes again, and callers receive
the same dictionary and revalidate as before. Rejected: deciding refusals
from the merged call's partial output (it exits 128 after at most the first
answer in a bare repository, inside `.git` and outside any repository;
`residual/gitcount/revparse-merged.out`) and splitting an answer whose path
holds a line break; both replay. Also rejected: re-raising a merged timeout
(it would name the merged argv), so a hung Git now waits out two 120 s
timeouts before the previous exception. By reasoning only, an older Git
(before 2.31 it echoes `--path-format=absolute`; before 2.25 it printed
nothing for `--show-toplevel` without a work tree) gives another line count
or a relative line and replays.

| Comparison (interleaved 3x; `wp5/compare/`) | Old phase sum, median (range) | New, median (range) | Verdict |
| --- | --- | --- | --- |
| `git-heavy` (5 of 1019 old / 1021 new) | 31.791 s (31.377–32.061) | 24.011 s (23.806–24.303) | new faster in every repetition (−24.5%) |
| `no-git` (10) | 1.188 s (1.188–1.312) | 1.209 s (1.188–1.270) | invariance shown |

The saving, 7.8 s, exceeds an estimate at WP3's 3.29 ms per process start
for these tests (555 sequences, 1,665 starts, ≈ 5.5 s;
`residual/gitcount/git-heavy-identity.out`) and the isolated benchmark's
8.35–8.76 ms per clean call (≈ 4.6–4.9 s over 555; `wp5/identity/bench.out`).
The excess is unexplained; repository discovery, the wrapper's cost and load
are candidates no comparison separates.

Regressions (`tests/test_repository.py`):
`test_checkout_identity_decides_only_a_clean_root_from_one_query` compares
14 real selections (main and linked roots, a subdirectory, bare, `.git`,
outside, missing, line breaks, trailing spaces, selections through links)
and a linked root re-created from a bare clone (the differing case) beside
the unchanged main root (invariance) with `_separate_identity`'s outcome,
and lists every Git process started; `test_checkout_identity_decides_only_clean_substituted_answers`
substitutes the real answer (the firing control), answers that each fail one
condition, and a timeout. Through `check.py`: against the unchanged module
both fail (`demo-old-repository.out`, a missing helper); with the merged
query removed both fail on their process lists, showing the four separate
queries (`demo-no-merged-query.out`); dropping the line count, accepting a
nonzero exit, or skipping the root comparison each fails its targeted test
(`demo-no-line-count.out`, `demo-accept-nonzero-exit.out`,
`demo-no-root-comparison.out`). A wider mutation table from the drafting
agent's pytest-free harness (14 of 16 mutations killed; the survivors,
accepting any first line but `true` and dropping `.resolve()` on Git's
paths, are test gaps the current substitutions do not exercise) and an
isolated benchmark (2.85–3.10 ms
against 11.20–11.86 ms per clean call) are in `wp5/identity/`
(`README.txt`), not run through `check.py`.

Open, outside this change (pre-existing; old and new code agree,
`wp5/identity/trailing.out`): `git_text` strips whitespace from both ends of
Git's answers, so a worktree root ending in a space, tab or carriage return
is refused as a subdirectory naming a path that does not exist, and a Git
directory at `<w>/admin ` is recorded as `<w>/admin`. A fix would strip only
Git's terminating newline in both decodings together and refuse such paths
with their own reason. Also by reasoning only: with Git before 2.31 the
separate `--path-format=absolute --git-common-dir` query answers the echoed
option and a relative directory, which `.resolve()` places under Stewart's
working directory.

The plan's WP5 instrumentation (wrapping `Popen` with timings and call sites)
was not built for this change: this one candidate was identified from the
logging wrapper's counts (`residual/gitcount/verbs.out`), and
`checkout_identity` is the only runtime caller of `--is-bare-repository`
(`wp5/callers.out`, `git grep` at `e9353fc`). The instrumentation and other
operations' repeated queries came later; see "WP5 census" below.

### Concurrency probe (`probe/`)

Four disjoint file sets of about 60 s each (`probe/sets.json`, chosen from
the WP3 gate's per-file times by `probe/choose_sets.py`; 14 of 46 files,
239 s of its 849.5 s; `tests/test_runner.py` and `tests/test_foundations.py`
excluded) ran as separate `check.py` invocations, each with its own
provisioning and build: alone, two at a time and all four at once, in a
rotating order over three repetitions at `c762b26` (`probe/drive_probe.py`,
`probe/batches.jsonl`, `probe/analysis.out`). Membership and outcomes were
identical to the alone runs in every condition, so no interference failure
appeared in these files.

| Condition | Per-set slowdown against the same repetition's alone run (medians) | Throughput gain: alone total wall / condition total wall, median (range) |
| --- | --- | --- |
| two at a time | 1.28–1.34 | 1.56 (1.49–1.59) |
| four at a time | 1.82–2.04 | 2.00 (1.99–2.14) |

Each repetition's alone runs were faster when they came first (repetition
1: 45.7–50.6 s per set) than after concurrent batches (up to 57.6 s). Thermal
limits on this fanless machine are one explanation; foreign load is a rival,
since the alone runs of repetitions 2 and 3 carried another session's tests
and repetition 1's did not (`followup-foreign-load.out`); no comparison
separates them. The four-way gains of the more loaded repetitions 2 and 3
(1.99, 2.14) bracket repetition 1's 2.00. The probe answers WP3's caveat:
contention is real, and four concurrent invocations roughly double
throughput, not quadruple it.

### Final gate (`final/gate-314`)

`final/gate-314` at `c762b26` (clean, `project_git` not dirty): no
selector; 1023 collected, 1023 selected, 0 deselected; 1022 passed, 1
skipped; `total_seconds` 728.9, wall 737.9 s; node list equal to
`wp3/gate-314`'s plus exactly the four new regressions
(`final/per-node-vs-wp3-gate.out`); the outer run withheld
`/opt/homebrew/opt/rustup/bin` from provisioning; Git through the `dash`
wrapper; retention removed 2,044 directories and 506 links in 8.8 s and kept
nothing. Foreign load was present: Safari WebKit over 10% in 25 of 75
samples (over 100% in 2), WindowServer, `duetexpertd` 97% (one sample), `mds`
up to 66% (five), among others, and brief samples of another session's
Python tests (`construction-broker-v2/broker_tests.py`, a `pytest`
of `integration/tests/contracts`; `final/load-notes.out`); `fseventsd` stayed
at or below 52% until retention. Against the previous gate the 1019 shared
nodes took 849.5 s and now 721.1 s (−128.3 s, −15.1%; 724 faster, 295
slower; no outcome changed); against `reference/full-314` the 992 shared
nodes took 1358.7 s and now 680.8 s (−49.9%; `final/per-node-vs-reference.out`).
How much of the −128.3 s each change contributed is an attribution, not a
measurement, given the gate's foreground load; the interleaved comparisons
above are the measurements.

### Recommendation on WP4, updated

The probe puts WP4's benefit at about twice the throughput with four
workers on this machine (1.56 times with two), measured as separate
invocations over 28% of the suite's time; a sharded run of the current
suite would take roughly half of `final/gate-314`'s 729 s plus
orchestration and the serial phase (an estimate). Whether that justifies
the plan's membership and merge machinery is the user's decision; if
approved, measure 2, 3 and 4 workers on the full suite, keep the default at
one worker, and expect little beyond four (4 performance cores, thermal
limits). Further WP5 work (other operations' repeated queries) remains
uninvestigated; `checkout_identity` was the largest candidate identified
(44.0% of the runtime's Git calls). The user then declined WP4 (no
sharding); the other operations are covered by "WP5 census" below.

## WP5 census: where the runtime's Git calls go (instrumentation only)

After the follow-ups the user declined WP4 ("We'll pass on WP4: no
sharding") and asked for WP5's instrumentation only: record each Git call's
operation, call site, duration and arguments over a full run, rank what
remains, and separate a question asked twice in one observation from a
re-check at a later boundary. No runtime code changed. Evidence:
`wp5/census/` (probe, runs, tables) and `wp5/review/` (custody review).

### Probe (`wp5/census/_wp5_git_census.py`, sha256 `66bdeccf…`)

A `.pth` line in the check venv's site-packages installs it in every
interpreter of that venv, including the `python -I -m stewart` CLI
children (isolated mode still processes `.pth` files). The hook lived only
in a scratch copy of `scripts/check.py` (`census-hook.diff`); the copy's
tree is `fb532fa`'s (`0abefa4e…`). It wraps `subprocess.Popen` once (`run`
uses it) and writes one record per Git process: argv, cwd, process,
`PYTEST_CURRENT_TEST`, the Python stack, an invocation token, the time from
spawn until the process is waited for, the exit status, and the sha256 and
length of stdout and stderr. This fixes both faults the plan names in
`tools/measure.py` and `tools/measure2.py` (left untouched): all 648 direct
`update-ref --stdin` processes from `create_refs` carry durations (median
15.30 ms; `measure.py` recorded 0.0 s), and the CLI children's own spawns
are recorded.

The first run (`full/`, probe `55eadf62…`) keyed an invocation by the id of
the outermost Stewart frame. Python reuses a freed frame's id, so separate
calls in the pytest process merged: of 950 in-process keys, 561 span more
than one (node, caller frame) and 542 more than one node (`full/NOTE.txt`).
Its per-invocation figures are superseded; its counts, sites and durations
stand. The probe now counts activations with a local `sys.monitoring`
PY_START event on the outermost frame's code. Self-test
(`probe_selftest.out`): five calls in a loop give five activations, where
the id token gave one; recursion splits an activation (repeats undercount,
never merge); without a free tool id each record says
`activation_counted: false`. In `full2/`, 97 records lack a counted
activation, none of them with a Stewart frame.

Departures from the plan's method: it suggested isolated fixtures in the
states each operation needs, with an exhaustive census optional; I ran the
full suite, so the counts describe the states the tests build, not
production use. Environment and Git configuration were not recorded, and
answers only as digests.

### Runs

Both in the default context (`unsandboxed`: no Claude Code sandbox
configured; socket bind allowed), Python 3.14.8, Git 2.54.0 (Apple Git-157)
through the `dash` wrapper, no selector: 1023 collected, 1023 selected,
0 deselected; 1022 passed, 1 skipped, each node's outcome equal to
`final/gate-314`'s.

| Run | Probe | `total_seconds` | Wall | Max 1-min load |
| --- | --- | --- | --- | --- |
| `full` | `55eadf62…` (frame-id token) | 678.2 s | 685.5 s | 2.96 |
| `full2` | `66bdeccf…` (activation token) | 676.8 s | 684.2 s | 3.19 |

Repeatability (`reliability.py`, `full2/reliability.out`): both runs
recorded 68,652 processes, 61,460 of them runtime, with identical counts for
every one of 104 runtime (call site, verb) keys and every one of 736 nodes.
An earlier inline comparison that reported 206 of 207 keys differing keyed
on unnormalized paths, which contain each run's private directories; it is
kept, with the outputs the review read, in `full2/as-reviewed/` (`NOTE.txt`).
`analyze.py` then took a module's name after the first `/stewart/`, which
misplaced 195 records from a runtime deployed under
`<home>/stewart/checkouts/…`. The outputs in `full2/` were regenerated with
the last `/stewart/`; totals and repeat classes are unchanged.

Against the WP3 logging wrapper (`reconcile.py`, `full2/reconcile.out`;
counting run at `7787b96`, before `c762b26`): over 1016 shared nodes the
prediction (wrapper lines, minus 3 per complete `checkout_identity`
sequence, plus 1 per incomplete one) is 66,819 calls and the census
recorded 66,691. 1,007 nodes agree exactly; 9 are lower, each by exactly 4
per incomplete sequence, and all 9 are concurrency tests. The likely cause
is that concurrent processes interleave their sequences in the wrapper's
log, but no comparison distinguishes that from other explanations. No node
is higher. 3 records lack a duration, all fixture calls in
`test_checkout_identity_decides_only_a_clean_root_from_one_query`.

### Where the calls go (`full2/analysis.out`, `full2/candidates.out`)

Durations are spawn-to-wait times from one run on a shared machine:
indicative, not a timing comparison.

- 68,652 Git processes: runtime 61,460 (325.6 s; 5,974 of them in CLI
  children), fixture and test 7,191 (53.4 s), nested `check.py` 1. Median
  runtime call 4.89 ms.
- By operation (calls, invocations, median per invocation, seconds):
  `prepare` 22,583 / 751 / 33 / 125.0 s; `collect` 11,290 / 449 / 30 /
  58.5 s; `close` 7,036 / 281 / 25 / 34.3 s; `status` 5,802 / 426 / 16 /
  29.2 s; every other operation under 1,620 calls.
- By call site: `checkout_identity` (`_repository.py:219`) 10,245 (52.6 s);
  `package_identity` (`session.py:83`, `ls-files`) 4,492 (21.0 s);
  `verify_retention` (`_repository.py:561/565/570`) 9,508 (47.0 s);
  `checkout_state` (`collect.py:139`) 2,931 (15.7 s); `_prepare`
  (`prepare.py:145`, `ls-tree`) 2,124 (10.8 s); `retain_commits`
  (`_repository.py:548`) 1,950 (17.7 s); `maintainer_state`
  (`session.py:307/309`) 3,074 (16.0 s).
- The same argv and cwd asked again within one invocation: 16,235 times
  with the same answer and no write between (81.2 s), 800 after a write
  (4.0 s), 330 with a different answer (1.7 s). Identical argv does not
  establish an equivalent query (plan WP5), so these are candidates, not
  savings.
- Distinct consecutive queries from one caller frame: 38 groups of 20 or
  more cover 15,948 of 25,238 avoidable process starts. This is a candidate
  list; the census cannot tell one call from two consecutive ones at one
  line.

### Custody review (`wp5/review/`, `wp5/review/round2/`)

Two read-only rounds of sub-agents, judged against `AGENTS.md`'s custody
rules and plan WP5. Round 1 had an analyst and a skeptic for each of nine
scopes (c1–c9) built from the largest groups, plus a coverage critic.
Round 2 had five resolvers, each applying one standard to an inconsistency
the critic found across scopes, and five independent refuters of the
largest A and B claims. Classes: **A**, the same question twice in one
observation (pass the first answer along within the call); **B**, distinct
questions one Git process can answer, decided only on clean answers with
replay otherwise (the `checkout_identity` precedent); **C**, a re-check at a
later boundary; **D**, a fresh observation recorded by design; **E**,
unclear. `round2/reconcile.py` merges the rounds: round 2 overrides round 1,
and a round-2 disagreement keeps the stricter class (`round2/final.json`,
`round2/final.out`).

Counts are the reviewers' tallies of `full2` and are not deduplicated
across patterns. Seconds are an estimate at the 4.89 ms median call.

| Class | Patterns | Avoidable under the stated conditions | Estimate |
| --- | --- | --- | --- |
| A | 14 (1 subsumed by a B) | 4,932 calls | 24.1 s |
| B | 11 | 11,213 calls (5,083 in patterns rated low confidence) | 54.8 s |
| E | 14 | 0 now; 4,336 after rulings R1–R3 below | (21.2 s) |
| C | 13 | must stay | |
| D | 7 | must stay | |

A, largest first: re-identification within the status view (1,723;
inside `close`, 182 more are C while that view is close's last role check
before it writes); `load_session`'s two `maintainer()` calls (1,582); the
CLI gate's identity reused by the operation (514, only with a root guard:
use it only when its root equals the operation's resolved `ws.repo`, and
never for request-key bindings or the identities `prepare` and
`register` record); close's nested view (297, through a private parameter
only); `initialize`'s unkeyed gates (193); `record_output` after its load
(122, keeping `maintainer()`'s role checks before `CREATE.json`);
`initialize`'s second `expected_inputs` (120); the declaration helper's
root (112); registrations listed twice in one evaluation (84); staged names
in `check` (78); the frozen HEAD (58, which also fixes deviation 2 below);
`bind` then `status` (27, root guard); `discover`'s first load (22).

B, largest first: `verify_retention`'s commit checks in one `rev-parse`
(1,592) and its value reads joined to them (3,158 more, low confidence;
4,750 together, the by-name alternative to the rejected listing); an empty
patch deciding the name list in `checkout_state` (1,925, low); the three
guidance `ls-tree` calls (1,415); `maintainer_state` from one
`status --porcelain=v2 --branch`, decided only when it lists no entries
(1,355); retained commits in one `rev-parse` (655); the status view's HEAD
and Git directory (489, only after deviation 1 is fixed); collect's
identity pair (369, replaying on any mismatch); the auditor context's HEAD
pair (151); expected inputs in one `ls-tree` (104, replaying when a name
begins with `:` or two names collide after Unicode normalization, and on
`OSError`). Every B also needs a comparison against real Git in the states
where the lookups could differ, and a substituted-answer regression with a
firing control.

Rejected, with what they must preserve:

- One `for-each-ref` listing in place of `verify_retention`'s by-name reads
  (round 1 B, 4,755; now E). Iteration and by-name lookup differ. On this
  case-insensitive volume with the files backend, a loose case variant over
  a packed ref can make them disagree; that is reasoned from the
  documentation, with no Git run. The by-name merges above replace it.
- Branch and HEAD in one `rev-parse` (c5, B 975; c4, E). `git branch
  --show-current` has configuration and version failures of its own, which
  a clean `rev-parse` cannot vouch for. The proposal also accepted attached
  branches through rules that fall back to other refs.
- Skipping the package identity's Git context in `require` (A 1,157) and in
  close's view (A 218, disputed): a hung Git (`TimeoutExpired`) would
  surface later. In `collect`, `run` and `recover_runtime` that is after a
  directory has been created (`collect.py:386` before `:405`,
  `experiment.py:399-408` before `:435`, `runtime.py:321` before `:326`;
  `package_identity` catches only `OSError`, `session.py:92`), leaving
  records that make every concluded close refuse.
- `prepare` re-resolving the prompt (A 723), the target diff equal to the
  parent diff (A 655), and the prompt bytes read again (A 707, now C).
  Replace refs, which `_git.py` does not neutralize, and prunes between the
  reads change refusals and recorded fields for particular interleavings;
  the prompt read also crosses the binding's publication and the checkout's
  validation.
- C and D patterns, kept as they are: `round2/final.out`.

Rulings these depend on:

- **R1.** The standard for A. Most reviewers accept a drop when every
  outcome the change can produce is one the current code produces if the
  change lands just after the later read. That is the tolerance the
  `checkout_identity` merge accepted for a rename during the call. The c3
  refuter required the same outcome for every interleaving. Under that
  reading no A or B survives, the precedent included. R1 alone releases
  723 calls, and with R4 another 655.
- **R2.** Whether a hung package Git may surface later, or whether
  `package_identity` should catch `TimeoutExpired` (a separate change).
  Releases 1,375 calls.
- **R3.** Whether `git branch`'s own failures must still refuse at
  preparation's role stage and in `collect`. Releases 1,583 calls with a
  detached-only shape.
- **R4.** Whether to neutralize replace refs (`GIT_NO_REPLACE_OBJECTS`) in
  `_git.py`. It is a behaviour change in its own right, and it also bears on
  deviations 2 and 4.

### Pre-existing deviations from `AGENTS.md` found by the review

None is caused by WP5. I checked items 1–7 in the code at `fb532fa`. They
are reported, not fixed.

1. **Status runs Git through a planted `.git` link.** `_git_head`
   (`status.py:61-63`, called at `:480` and gated only by `is_dir()`) and
   `_lock_view` (`:913-919`) run `rev-parse` in the auditor worktree
   without the regular-gitfile check that `close` (`close.py:205-207`) and
   `collect` apply. In the census, after
   `test_a_planted_git_link_is_never_used_to_run_git` replaces `.git` with
   a link to the maintainer's, both of its `close` calls ran `status.py:62`
   and `:915` in the worktree with exit 0. The `--absolute-git-dir` answer's
   digest (`788fb9ef…`) equals the earlier `--git-common-dir` answer, the
   maintainer's `.git`; a genuine linked worktree would name
   `<common>/worktrees/<id>`. Git was read-only (`GIT_OPTIONAL_LOCKS=0`),
   so the test's assertion, that the maintainer's index and HEAD are
   unchanged, holds, but its name claims more. As an operation, status can
   report `head`, `head_matches_prompt` (which gates the run and release
   offers) and the lock from the other repository.
2. **The frozen HEAD is a later re-read.** `evaluate` judges the HEAD read
   at `holdings.py:977` but freezes the one read at `:1280`, against "Freeze
   what the evaluation judged … never a later re-read" and its own
   docstring (`:1144-1147`). At use, the not-started path compares HEAD and
   judges again before the attempt record (`:1525-1532`). That limits the
   damage, but a HEAD that moves inside the evaluation is absorbed and the
   worktree is removed instead of the claim being released. The use path
   also compares at `:1526` but judges at `:977` after `git status`, and
   `:1526` runs Git before the gitfile checks (it fails closed).
3. **A failed ref listing reads as absence.** `_session_refs`
   (`close.py:80-81`) runs `for-each-ref` with `check=False` and never
   checks the exit status. `remove_ref` then reports "absent", and the
   inventory and the leftover scan come out empty.
4. **Inherited Git environment.** `_invocation` (`_git.py:24-30`) removes
   only `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` and `GIT_COMMON_DIR`,
   although the module docstring says inherited redirections are dropped;
   `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`,
   `GIT_CONFIG_PARAMETERS` and the replace-ref variables pass through.
   Nothing in `src/` neutralizes replace refs (`grep`). The reviewers add,
   from `git(1)`, that lazy fetch from a promisor remote stays enabled.
5. **Session files written by overwrite.** `collect.py:414` and `:465`
   write `REPORT.md` and the raw captures with `Path.write_bytes` (truncating
   and following links) instead of `write_receipt`. The impact is low: the
   collection directory is created exclusively, with mode 0o700, just
   before (`:386`).
6. **Untested refusals.** No test asserts `worktree_role_identity`
   (`_repository.py:461-473`).
7. **Exceptions without a reason escape `close_plan`.** `_status_view`
   catches only `StewartError` and `OSError` (`close.py:1060`), and
   `close_plan`, documented to report rather than raise its refusal
   (`:1196-1198`), catches only `StewartError` (`:1231`). A Git timeout
   inside the view therefore escapes.

The reviewers also report the following by reasoning alone; none was
checked:

- `collect.py:163`'s plain `rev-parse HEAD` can record a fallback ref's
  commit when HEAD is unborn.
- A branch ref that vanishes between `observe` and `evaluate` freezes a tip
  of None, and its removal can then end with an attempt record but no
  failure record (`holdings.py:1264-1282`, `:1635`).
- An attempt-named entry that `retire_claim` did not write sends
  revalidation down the started path, which judges no HEAD.
- A planted loose-ref symlink can pass `verify_retention`'s by-name reads.

### Review process

Round 2's first attempt was stopped after one agent ran `find /` looking for
Git's source, which raised macOS privacy prompts that the user denied
(`round2/stopped-attempt/audit.out`). The relaunch limited every agent to the
worktree and Xcode's Git manual pages, with no network. A watcher
(`round2/audit.py`) found no tool call outside those places
(`round2/audit-run.out`). The round-1 coverage critic once ran `git status
--short` in the worktree, which can refresh the index's stat cache; no
tracked content changed. No reviewer ran tests, Stewart, or a Git command
that writes.

### What this leaves

The runtime's Git calls take 325.6 s of a 676.8 s run (spawn to wait).
The reviewed A and B candidates come to about 79 s if every one lands with
its conditions (an estimate), with about 21 s more behind R1–R3. Five items
make up about half of that: the status view's re-identification, the two
lookups in `load_session`, `verify_retention`'s commit checks,
`maintainer_state` and the guidance `ls-tree` (7,667 calls, ≈ 37 s). The
rest is small: 13 of the 25 A and B patterns are under 200 calls (≤ 1 s
each). Every change needs its own regression and, for B, a comparison
against real Git. Deviations 1 and 2 are custody defects independent of
speed.
