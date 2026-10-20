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

**Residual cost found on the way (for WP3).** pip runs `rustc --version`
whenever `rustc` is on PATH (its user-agent string; 0.5 s timeout), even with
`--no-index`. Homebrew's rustup proxies are on PATH here, so in a test's empty
private HOME the proxy starts installing the stable toolchain from the network
until pip kills it. Each nested `check.py` makes three such pip calls
(`residual/rustup/proxy-calls.log`); eight reference tests left `.rustup`
trees of up to 34 MB, two with a partial `stable-aarch64-apple-darwin`
toolchain (`residual/rustup/README.txt`). Not changed; see WP3.
