# Fresh integrated review — findings

Review source: exact 18 integrated snapshots in
`.scratch/handoff-transition-01/review-inputs-01.json`, compared with the nine
original snapshots in `inputs-01.json` at `4cfde95d0324486f33ee12371a3b8384dadc535a`.
The optional TURNOVER snapshot is intentionally zero bytes. This is an
independent documentary review, not a product or harness qualification.

## Finding R1 — low severity: contradictory current progress instructions

Source: integrated `coordination/handoff-transition-01/PROGRESS.md:3–5` says both
investigators returned and the old handoff is retired, but lines 15–16 still say
“Next: dispatch inventory and recovery workers,” and lines 20–23 still describe
the old handoff as remaining. These older checkpoint passages have no milestone
headings or date/status labels distinguishing them from the current instructions.

Consequence: the current account sends a recovering coordinator to this progress
record, where the apparent next action disagrees with the current-state heading.
The current account and actual saved returns resolve the ambiguity, so this is
not a blocker or evidence of actual duplicate dispatch. It adds avoidable
reconstruction work at precisely the interruption boundary being improved.

Smallest fix: give retained older checkpoints explicit historical milestone
labels, or replace the stale next-action paragraph with the actual current next
action. Keep one unambiguous current checkpoint. Do not rewrite the pinned review
snapshot or completed investigator reports.

## R1 follow-up

The coordinator reported a correction while review continued. I read the current
root PROGRESS and REVIEW-DISPOSITION: the stale paragraphs are replaced with one
current checkpoint, clearly completed milestones and an actual next action. R1
is resolved in that current file. Its original finding above remains against the
pinned 18-input review source; the pin has not been rewritten.

## Conclusion and supporting observations

No material authority or continuity blockers found in the integrated source.

- Root AGENTS now contains role and routing rather than the removed coordinator
  standing procedure. Its diff leaves the general development, product boundary,
  frozen-baseline and custody rules intact. CONTRACTS is byte-identical to the
  original. Standing orders preserve scope/protected-obligation authority, Git
  ownership, optional consultation and independent assessment of relayed advice.
  No compulsory personal test rerun or new approval gate is introduced.
- Worker reach is explicit in root AGENTS's coordinator-folder route and
  STANDING-ORDERS:7–8. The standing launch/capacity/checkpoint provisions are
  applicable to dispatched workers, and saved briefs carry bounded scope and
  the commission's no-Claude/checkpoint limits. The ten-agent preference stays
  soft, lower limits apply, and dated four-slot/99-percent observations stay in
  the working account. Repository discoverability does not prove automatic
  instruction presentation by every harness.
- README and STANDING-ORDERS:34–47 support intake with blank or absent TURNOVER;
  a populated brief is explicitly fallible. The named current account locates
  the commission, base/input pin, owned paths, returned worker outputs, inspected
  checkpoints and next action. The intentionally empty brief is not needed to
  find any of these. Active plans remain discoverable by naming convention.
- The eight documentary recovery cases in the investigator map are supported by
  the integrated orders/account: saved work without final chat; missing/stale
  turnover; lost spawn/effect replies; uncertain prior coordinator; stale account;
  and a new harness without old API access. The orders require reconciliation
  before adoption and keep potential writers distinct. Disjoint paths do not
  authorize repetition against the same uncertain effectful target. No absence
  of logs, old handle or timestamp is promoted to evidence of termination.
- The Git-guide three-part requirement and exact baseline maintenance commands
  survive in the plan's publication section. I independently sampled a792774
  and 85b957b and the existing CUSTODIAL-CORE-FINDINGS account. The checker/setup
  failure remains in its evidence table, with the coordinator's own failed rename
  distinct; the new orders require real checker evidence without converting a
  prior coordinator lesson into mandatory duplicated runs.
- The plan explicitly preserves named baseline findings/records while their
  Rust-acceptance versus purpose-served wording awaits scoped disposition. The
  sampled be5e6ba/85b957b history supports that tension. No deletion or new
  universal retention rule follows from moving the guidance. Corpus retention
  retains exact source/ref locators and the main-only-clone limitation; the
  current account labels local scratch and dated evidence as such. The A3 pilot,
  helper reuse, actual finite legacy population and route qualification remain
  open or uncommissioned. Later a8de387/8fd864f commit identities support treating
  older Git permission failures as history, not standing prohibitions.
- The active old-handoff routes in AGENTS, notes and plans are removed or
  redirected. Remaining scoped matches describe historical input, the
  transformation or its preserved source. CLAUDE is still mode 120000 and points
  to AGENTS. Tracked historical worker/reviewer sources, runtime, tests, contracts
  and other sampled protected owners show no diff from the admitted base.

## Checks and limits

SOURCE-CHECK.json records 9/9 original and 18/18 integrated snapshot byte/hash
matches and 9/9 original matches to the base commit. ROUTE-CHECK.json records 85
local Markdown path targets with no missing target, plus scoped read-only Git
outputs. LOCATOR-CHECK.json records ten named work/evidence paths present and
three finite local development-evidence refs matching CORPUS-RETENTION. This
checks presence/ref identity, not payload validity or portability to another
machine. Markdown anchor coverage is not claimed.

Read changed guidance passages, the original handoff, both investigator maps and
returns, and sampled owners/history rather than rereading every unchanged line
of the large plan/contracts. No bulk evidence artifacts, private/home/neighbor
state, old process liveness, external harness configuration or remotes were
inspected. Zero pytest nodes, zero behavioral comparisons, zero induced faults,
zero installations or harness/Claude launches. No Git mutations or external
services/messages. Only the assigned review attempt directory was written.
No failed validation check; diff exit 1 denoted expected content differences.
The review supports the documented arrangement, not actual fault recovery,
automatic loading, enforcement, or complete recoverability of unsaved work.
