# Dispatch guidance review 01

Prepared 2026-10-26 by the coordinator. This is an independent documentary
review within the user's request to establish future dispatch practice. It
does not start the substantive successor inquiry or authorize runtime changes.

## Inputs and scope

Read AGENTS.md, the new laptop/continuity section of DEVELOPMENT-PLAN.md,
the current opening of COORDINATOR-HANDOFF.md, VISION-PLAN.md's coordination
account and coordination/COORDINATOR-NOTES.md. Base commit: `777c87b`.
The coordinator saves exact admitted guidance bytes and identities under
`.scratch/coordinator-dispatch/review-inputs-01/` before dispatch; its manifest
is `.scratch/coordinator-dispatch/review-inputs-01.json`. Review those bytes;
the index may acquire a worker handle after the snapshot. Identify any
other input explicitly. Do not read restricted neighboring projects.

Check that the user's approximate ten-agent preference remains soft, whole-
fleet and subordinate to actual harness limits, and that ordinary coordination
does not require user micromanagement. Evaluate interruption recovery against:

- A worker disappears after substantial findings but before its final reply.
- A long command or spawn may have taken effect but its reply is lost.
- The coordinator is interrupted and another coordinator resumes from disk.
- An unreachable old worker may still write while a replacement is launched.
- A saved draft or stale checkpoint is mistaken for a verified result or
  liveness evidence.

Distinguish useful safeguards from unnecessary procedure. Check authority,
edit ownership, evidence retention and the separation from Stewart's product
contracts. Flag any materially missing recovery step or conflicting instruction.
This is a source/tabletop review, not a sleep or network-fault experiment.

## Ownership and saving work

Your only writable files are:

- `coordination/dispatch-review-01-PROGRESS.md`
- `coordination/dispatch-review-01-RETURN.md`

First write PROGRESS.md with started state, inputs, intended checks and next
step, before substantive review. Save useful findings as they arise and at
milestones; on a longer task refresh roughly every five to ten active minutes.
Keep both files sufficient for a replacement to continue without this chat.
Do not edit root guidance, plans, contracts, the coordinator's index or other
workers' outputs. Do not spawn agents, run runtime/harness tests, mutate Git
metadata or perform any external action.

## Completion

Write RETURN.md before replying, with findings ranked by consequence, exact
source references, suggested bounded corrections and any remaining uncertainty.
Say explicitly if no blocking findings were found. Include which scenarios
were examined and the documentary limits of the review. Finish PROGRESS.md
with the saved return path and work left. Send a compact chat return pointing
to those files. The coordinator verifies and integrates the result.
