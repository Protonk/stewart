# Turnover

Written at the user's direction on 2026-10-28 UTC by the outgoing coordinator
(Claude Code, Opus 5.5). Source: `main` at `313c4e3`. The following commit holds
this brief, the condensed [current account](COORDINATOR-NOTES.md), a pause note on
PLAN-FIT and one transition paragraph in DEVELOPMENT-PLAN. Nothing has been pushed;
`origin/main` is at `3442f84`. Nothing here commissions work. It supplements the
[standing orders](STANDING-ORDERS.md) and the current account, whose checkpoint
holds this tenure's state.

## Where things stand

This tenure was one long design conversation with the user. All of it is in
[linux-mvp-01/](linux-mvp-01/README.md), which the user said you will see exactly
as it was left. Read its README and AGENTS file first.
[ROUTER.md](linux-mvp-01/ROUTER.md) and
[END-TO-END.md](linux-mvp-01/END-TO-END.md) are the latest statements. The user
said they would review the whole folder, so their verdict may be the first thing
you hear.

The conversation proposes a different successor: a small, fast, Linux-only Rust
binary that routes a manager's problem to an auditor placed in an arrangement made
*just* so. It has these parts:
- the auditor has only Stewart's tools;
- a small library of question-answer couplings;
- a model adapter now, a person adapter later;
- verified returns;
- no Python baseline and no Git;
- build, test and experiment containers that never ship.

None of it is adopted. CONTRACTS, AGENTS.md/CLAUDE.md, DEVELOPMENT-PLAN and the
code are unchanged. The earlier first-leg preparation (PLAN-FIT and its companions)
is paused, not retired.

## Reading the folder

`CONVERSATION.md` quotes every prompt verbatim; those are the user's directions.
Most of the design's detail is the coordinator's proposal, and
`RESERVATIONS.md` separates the two for the first draft. The current account's
checkpoint lists the user's directions in condensed form. The earlier files in the
folder are records; leave the conversation files as they are.

## Next questions

1. The user's verdict on the folder, and whether to adopt the router.
2. If adopted: restate the principles in CONTRACTS (a neutrality restatement is
   drafted in conversation turn 12), retire the Python baseline and the
   Git-dependent contracts, and rewrite DEVELOPMENT-PLAN. AGENTS.md (CLAUDE.md links
   to it) encodes the old design's custody rules and is the user's to change.
3. The manager side, which the user named as needing design.
4. Still open from the conversation: resuming a dead run, the person adapter and
   how work reaches a person, and a rule for adding form opinions to the coupling
   library.
5. The apparatus: container images with build dependencies the coordinator
   selects.
6. The real-model conformance gate and any experiment call the model provider.
   That needs the user's explicit, bounded permission and a budget.

One working note from this tenure: when the conversation is about the app, the
user doesn't want discussion of the development process. Keep process in the files.

## Workspace

The current account was condensed at this turnover to current state, open work and
an index of the local records it owns. The full earlier narrative is at
`git show 313c4e3:coordination/COORDINATOR-NOTES.md`. This tenure's local records
are `.scratch/coordinator-intake-20261028-01/` and `.scratch/alignment-20261028-01/`.
The alignment notes are copied verbatim into the folder. Environment notes are in
the account.
