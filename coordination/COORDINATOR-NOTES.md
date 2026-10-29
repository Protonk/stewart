# Current coordinator account

Updated 2026-10-28 by the incoming coordinator (Codex) for the manager/auditor
interface review. This is a working account of observed work,
authority received and remaining questions. [Standing orders](STANDING-ORDERS.md)
own operating instructions; [the directory entry](README.md) identifies intake
documents. The optional [turnover](TURNOVER.md) is supplementary. Reconcile these
observations with actual files, user instructions and available harness state
after interruption.

**A note for the next coordinator.** During the design review this account was
appended turn by turn as the conversation went. That habit ends with the review.
The conversation under [linux-mvp-01/](linux-mvp-01/README.md) is closed; its
decisions are in CONTRACTS and its program is in
[TRANSITION-PLAN.md](../TRANSITION-PLAN.md). Do not add turns to the conversation
file or turn-by-turn entries here. Keep this account to current state, dispatched
work and the index of local records, and keep it short. The full earlier
narrative is in Git: `git show 313c4e3:coordination/COORDINATOR-NOTES.md` for
the commissions before 2026-10-28, and `git show 8daac52:coordination/COORDINATOR-NOTES.md`
for the turn-by-turn account of the review.

## Current commission

The user commissioned a review of the manager and auditor tool interfaces and
concerns brought back in conversation. The two design sessions are historical;
their conversation and recording habit stay closed. The turnover's proposed
next work is information, not an instruction to execute T0 or any other stage.
Intake read the named historical accounts at `313c4e3` and `8daac52`, the current
contracts, sketch, test design and plan, and checked the successor's actual
command surface. The successor still implements commission bundles only.

Coordinator concerns for discussion, not decisions or implementation work:

- Manager recall needs an explicit supported route from the reference to the
  original question, arrangement and copied input bytes; the proposed command
  list does not yet describe that route.
- Status and close need plain distinctions between an interrupted placement,
  unsubmitted work, a sealed answer, verified delivery and completed close.
  Delivery failure must have a usable path within close, including a destination
  that is no longer usable, without implying another investigation.
- Material acceptance and preview need to distinguish copied bytes from what
  the auditor's read/search interface can actually present, and account for
  changed inputs between preview and commission.
- Retry guidance must distinguish a new addition from a handle-bound submission
  lookup and make recorded identities/revisions easy to recover after a lost
  reply; blanket "try again" guidance can duplicate an addition.
- Re-entry must restore a usable working position at admitted size limits;
  returning every answer byte in one reply is not a scalable specification.
- The illustrative claim-check slots steer toward finding and repairing missing
  support. A refuted claim, a supported claim and an indeterminate claim need
  equally ordinary expression, and the stopping instruction needs scrutiny.

These are specification concerns, not demonstrated runtime defects. No runtime
tests, model calls or workers were launched. Product contracts, plans and the
closed design record are unchanged.

## Inherited product state

- **The design is decided and recorded.** CONTRACTS.md has the Mission (the
  user's words), "Successor interfaces decided 2026-10-28" (including the
  platform, no-Git, no-baseline and auditor's-world decisions), and a
  **Proposed** "Transition status of the earlier contracts" section listing
  eight decisions the user has not made and the restatements proposed on
  confirmation. ROUTER.md and
  END-TO-END.md under `linux-mvp-01/` are the settled sketch and test design, with
  the revising turns noted at their tops. The README is framed as the frozen
  Python tool's manual under the new mission.
- **The program is TRANSITION-PLAN.md**: stages T0–T9, the disposition of the
  earlier program, evidence owed and open questions. DEVELOPMENT-PLAN.md is
  marked superseded and kept until its disposition is confirmed item by item;
  VISION-PLAN.md carries a dated note on what is overtaken.
- **No implementation stage is commissioned.** The plan prepares; the user
  commissions each stage. No code changed in this review. `successor/` still holds
  the `stewart-commission` binary, which seeds T2.
- **Git at intake.** Clean `main` at `218d5ba`; the turnover reported nothing
  pushed and `origin/main` at `3442f84`. The Python suite was not run in this
  review; the inherited result is 1140 passed, 1 skipped.

## Dispatched work

| Assignment | State | Records |
| --- | --- | --- |
| `contracts-disposition-01` — a fresh-eyes, read-only disposition of every CONTRACTS section under the 2026-10-28 decisions, with what would be lost silently (RESERVATIONS.md item 16's check). Pinned to `7e49301`. One general-purpose agent through the harness; no Claude launch, no network, no Git state changes. | Returned and integrated 2026-10-28 at `f2ca3f4`. 105 rows (75 required): Carry 25, Restate 23, Retire 21, Undecided 6 of the required set; fifteen "lost silently" items; nine contradictions. Integrated as CONTRACTS' Proposed transition-status section, three wording fixes and two realized deferrals, plus markers in ROUTER.md and END-TO-END.md and claim C14. Retired sections are untouched pending the user. | [BRIEF](contracts-disposition-01/BRIEF.md), `PROGRESS.md`, `RETURN.md` |

No other worker, workflow, background command, container or Claude launch is
active or pending.

## Next

Discuss the interface concerns with the user. No transition stage follows
automatically from this review. TRANSITION-PLAN.md retains the prior coordinator's
sequence and CONTRACTS' Proposed transition section retains the pending
dispositions; neither is the present commission. Model-consuming work still
requires explicit, bounded permission and a budget under the standing orders.

## Environment notes

Inherited observations from the previous tenure; not re-tested at this intake.

- This harness's command sandbox refuses Apple `container` commands and `ps`/`pgrep`.
  Container service and run commands go through the user's terminal (`!`).
- The Python suite runs outside the sandbox (DEVELOPMENT.md).
- Apple `container` 1.6.1 is installed. The alpine, rust and python images pulled
  by digest for the Linux check remain, and the container services the user
  started may still be running.
- `test_runner_withholds_rustc_from_provisioning` can flake under load.

## Recovery-critical local evidence

The three original audit outcome commits were not ancestors of main and had no
containing refs when inspected. Local development-evidence refs and exact text
copies protect them. [Corpus retention](successor-inquiry-01/CORPUS-RETENTION.md)
names the refs, hashes and source copies; a main-only clone does not carry them.
Retained runs under `.scratch` are local and untracked, and follow DEVELOPMENT.md's
retention rules. Nothing was pruned this tenure.

## Local records this account owns

Each entry is under `.scratch/`. Where a report owns a run's findings, the run
stays with that report under the retention rules.

| Records | Owner of findings |
| --- | --- |
| `coordinator-intake-20261028-02/` | The outgoing coordinator's intake record. The closed design review's records are tracked under `coordination/linux-mvp-01/` and `coordination/contracts-disposition-01/`. |
| `alignment-20261028-01/`, `coordinator-intake-20261028-01/` | The design-conversation tenure. The alignment notes are copied verbatim into `linux-mvp-01/`. |
| `route-research-01/`, `plan-fit-review-01/`, `answer-structure-check-01/`, `auditor-cases-01/` | PLAN-FIT, ANSWER-STRUCTURE and AUDITOR-CASES (paused first-leg work) |
| `linux-first-light-01/`, `linux-check-01/`, `stale-tests-01/`, `fifo-hygiene-01/` | This account. `linux-check-01/RESULTS.md` holds the Linux findings that DEVELOPMENT-PLAN cites. |
| `opus-intake-01/`, `opus-readiness-01/`, `opus-turnover-run-012/`, `astra-turnover-20261027-01/`, `coordinator-intake-run-012/`, `coordinator-transfer-guidance-01/`, `first-leg-riker-brief-01/` | This account (earlier intakes and turnovers) |
| `custody-shakedown-01/`, `custody-concern-routing-01/`, `interaction-simplifications-01/`, `manager-return-direction-01/`, `manager-collect-discussion-01/`, `manager-collect-authority-01/`, `return-completeness-01/`, `authoring-boundary-01/`, `commission-recall-plan-01/`, `forward-program/` | This account (earlier decision records) |
| `coordinator-intake-20261026-01.json`, `coordinator-intake-recording-01.json`, `coordinator-discussion-20261026-01.json` | This account |
| `submission-prototype-01/` | [submission-design-01/RESULT.md](submission-design-01/RESULT.md) |
| `opus-preparation-audit-01/` | [reports/opus-preparation-audit-2026-10-27/RESULT.md](../reports/opus-preparation-audit-2026-10-27/RESULT.md) |
| `commission-intake-01/` | [reports/commission-self-audit-2026-10-27/RESULT.md](../reports/commission-self-audit-2026-10-27/RESULT.md) |
| `receipt-challenge-01/` | [receipt-challenge-01/RESULT.md](receipt-challenge-01/RESULT.md) |
| `answer-revision-01/` | [answer-revision-01/RESULT.md](answer-revision-01/RESULT.md) |
| `construction-execution-01/` | [construction-execution-01/RESULT.md](construction-execution-01/RESULT.md) |
| `fresh-authoring-01/`, `fresh-authoring-preparation-01/` | [fresh-authoring-01/RESULT.md](fresh-authoring-01/RESULT.md) |
| `return-boundary-01/` | [return-boundary-01/RESULT.md](return-boundary-01/RESULT.md) |
| `answer-representation-01/` | [answer-representation-01/RESULT.md](answer-representation-01/RESULT.md) |
| `handoff-transition-01/` | [handoff-transition-01/RESULT.md](handoff-transition-01/RESULT.md) |
| `successor-inquiry-01/` | [successor-inquiry-01/COORDINATOR-PROGRESS.md](successor-inquiry-01/COORDINATOR-PROGRESS.md) |

Other `.scratch` entries belong to earlier plans and findings, not to this account.
