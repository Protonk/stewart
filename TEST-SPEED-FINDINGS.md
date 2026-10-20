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
