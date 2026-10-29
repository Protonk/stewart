# Turnover

Written at the user's direction on 2026-10-28 UTC by the outgoing coordinator
(Claude Code, Fable 5.1) at the end of the design review. Source: `main` at
`f2ca3f4`; the following commit holds this brief and the updated
[current account](COORDINATOR-NOTES.md). Nothing has been pushed; `origin/main`
is at `3442f84`. Nothing here commissions work. It supplements the
[standing orders](STANDING-ORDERS.md) and the current account.

## Where things stand

The design review of 2026-10-28 is over. Its decisions are in CONTRACTS
(the Mission, in the user's words; "Successor interfaces decided 2026-10-28").
The settled sketch and test design are ROUTER.md and END-TO-END.md under
[linux-mvp-01/](linux-mvp-01/README.md), whose conversation record is closed.
[TRANSITION-PLAN.md](../TRANSITION-PLAN.md) is the active plan: the stages T0–T9
with their required results and decision points, the disposition of the earlier
program, evidence owed and open questions. DEVELOPMENT-PLAN.md is superseded
and kept until its disposition is confirmed; VISION-PLAN.md carries a dated
note. CONTRACTS also has a **Proposed** "Transition status of the earlier
contracts" section, integrated from a fresh-eyes review
([contracts-disposition-01/RETURN.md](contracts-disposition-01/RETURN.md)),
listing eight decisions the user has not made and the restatements proposed on
confirmation. Retired contracts are untouched until the user confirms.

## What the user asked of you

Familiarize yourself with the plan and its overall sequence, and prepare to
manage the continuing transition. Nothing is commissioned; the user commissions
each stage when its turn comes. The design conversation is closed: do not add
turns to it or resume turn-by-turn entries in the account.

## First work: T0

1. Bring the eight pending decisions to the user. Five dispositions hang on the
   first: whether Stewart ever removes bytes.
2. On confirmation, restate and retire per the review's table, keeping retired
   reasoning where a decision cites it.
3. Confirm the earlier program's disposition item by item against the old
   plan's register, then delete DEVELOPMENT-PLAN.md; retire VISION-PLAN.md into
   the coordination guidance.
4. Draft replacement development guidance for the root AGENTS.md, which the
   user adopts; until then workers inherit custody rules written for the old
   design, so brief them with the decided design.

## Working notes

- When the conversation is about the app, keep development process in the
  files (now in the standing orders).
- T7 and any experiment call the model provider; they need the user's explicit,
  bounded permission and a budget.
- Environment notes are in the account; this harness's sandbox refuses Apple
  `container` commands and `ps`/`pgrep`.

## Workspace

This tenure's local record is `.scratch/coordinator-intake-20261028-02/`. The
turn-by-turn account of the review is at
`git show 8daac52:coordination/COORDINATOR-NOTES.md`; the account before the
review is at `git show 313c4e3:coordination/COORDINATOR-NOTES.md`.
