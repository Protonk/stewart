# Recovery investigator return

Completed documentary review 2026-10-26 against
`4cfde95d0324486f33ee12371a3b8384dadc535a` and the nine exact original snapshots
listed in `.scratch/handoff-transition-01/inputs-01.json`.

The result is [FINDINGS.md](FINDINGS.md). It supplies original-source line
locators and dispositions, historical/product exclusions, minimum useful
contents, and a recovery walkthrough for missing/stale turnover, unfinished
worker, lost spawn/effect reply, uncertain coordinator, stale account and a
new harness without a usable old handle.

The key implementation advice is to keep the existing notes path as the
continuous account/index, make standing orders reachable independently from
AGENTS (preserving its CLAUDE symlink), and retire the old substantive root
handoff after moving useful context. Maintain coordinator work and uncertain
effects during the task, not only worker dispatches. A blank turnover is
ordinary and must not prevent intake. Freshness and liveness require separate
reconciliation; separate output paths do not make repeating the same uncertain
effectful target safe.

Active fixes are enumerated in FINDINGS, chiefly AGENTS' opening/index/update
routes, notes' standing/recovery routes, VISION-PLAN's continuity paragraph and
DEVELOPMENT-PLAN's continuity/recovery paragraph. The plan also has a live Git
request pointer at original line 835, historical forward pointers at 1237/1469
and a standing fleet locator at 1680. Preserve historical worker/reviewer
references and product handoffs. The integrated findings link needs no change
if COORDINATOR-NOTES retains its path and dispatch responsibility.

Evidence:

- `.scratch/handoff-transition-01/recovery/attempt-01/reference-search.txt`:
  exact-base tracked Markdown search for the old coordinator paths/names.
- `.scratch/handoff-transition-01/recovery/attempt-01/source-check-01.json`:
  nine of nine original snapshot byte counts and SHA-256 hashes matched;
  FINDINGS/PROGRESS trailing-whitespace check passed at that checkpoint.
  The check used `/usr/bin/python3 -I -B` and standard-library reads/hash/JSON.
- CLAUDE alias observed with `git ls-files -s -- AGENTS.md CLAUDE.md` and
  `ls -l AGENTS.md CLAUDE.md`; it is a tracked mode-120000 symlink to AGENTS.

Zero pytest nodes, zero behavioral comparisons, zero live fault tests and zero
harness launches. No root/historical/product edits, Git mutations, private
stores, neighboring projects, Claude sessions or extra agents. Only this
attempt directory and its matching scratch directory were written.

No result here qualifies actual interruption recovery, automatic instruction
presentation by another harness, process control or stopping. The coordinator
must verify its integrated documentation and references; the review does not
resolve current writer liveness or missing external state. No worker work remains.
