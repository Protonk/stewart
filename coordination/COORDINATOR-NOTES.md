# Current coordinator notes

Updated 2026-10-26. This is the coordinator-owned dispatch index, not a second
program plan. [DEVELOPMENT-PLAN.md](../DEVELOPMENT-PLAN.md) owns W01–W20 and
their dependencies. [The handoff](../COORDINATOR-HANDOFF.md) explains how to
resume; [AGENTS.md](../AGENTS.md) gives standing capacity/checkpoint rules.
Reconcile files and available harness state after interruption. State below
records an observation; silence and old timestamps establish no liveness.

## Current commission and capacity

The user authorized the briefed first preparation wave on 2026-10-26:
answer requirements, operating routes, and coverage/transition, followed by
coordinator integration and independent review. Runtime implementation, fresh
audits, live harness/network experiments and custody disposal remain outside
this commission. The dispatch-practice review is complete. Routine staffing,
replacement and integration belong to the coordinator. Product decisions and
subsequent empirical execution retain their stated boundaries.

The machine preference is roughly ten simultaneous agents or fewer in total,
including coordinators, reviewers and nested workers. The available harness
currently limits this thread to four total. Use fewer when memory-intensive
builds/tests compete; there is no reason recorded to exceed the preference.
Check actual capacity at the next dispatch rather than assuming this observation
still holds. Further worker delegation must be coordinated in the same count.

## Dispatch index

| Assignment / scope | Observed state and handle | Saved work and next action |
| --- | --- | --- |
| `dispatch_guidance_review`, preparation only | Integrated after coordinator verification; harness handle `/root/dispatch_guidance_review`. No worker work remains. | [Brief](dispatch-review-01-BRIEF.md), [progress](dispatch-review-01-PROGRESS.md), [return](dispatch-review-01-RETURN.md). Source base `777c87b` plus six exact inputs in `.scratch/coordinator-dispatch/review-inputs-01.json`. One low-severity finding resolved below; final checks in `.scratch/coordinator-dispatch/validation-01.json` and `.log`. |
| `answers`, W01/W02 | Authorized; brief saved; not yet dispatched. | [Brief](successor-inquiry-01/answers/BRIEF.md). Source `250d494` and `.scratch/successor-inquiry-01/inputs-01.json`; shared repository, exclusive `successor-inquiry-01/answers/attempt-01/` outputs. Next dispatch and inspect the initial checkpoint. |
| `routes`, W04–W11 | Authorized; brief saved; not yet dispatched. | [Brief](successor-inquiry-01/routes/BRIEF.md). Source `250d494` and `.scratch/successor-inquiry-01/inputs-01.json`; shared repository, exclusive `successor-inquiry-01/routes/attempt-01/` outputs. Next dispatch and inspect the initial checkpoint. |
| `coverage`, W01–W20 and transition | Authorized; brief saved; not yet dispatched. | [Brief](successor-inquiry-01/coverage/BRIEF.md). Source `250d494` and `.scratch/successor-inquiry-01/inputs-01.json`; shared repository, exclusive `successor-inquiry-01/coverage/attempt-01/` outputs. Next dispatch and inspect the initial checkpoint. |

For each dispatch, record the exact source commit/snapshot, task name and
agent handle, start observation, worktree, exclusive output paths and last
checkpoint actually inspected. The brief must already exist before spawn.
If the spawn reply is lost, use available harness inventory and the recorded
task identity before deciding whether another worker is needed. Separate a
worker return from coordinator verification and integration.

## Recovery and next action

1. Read the plan and this index; inspect each named checkpoint, findings file,
   diff and retained command output. Consult the harness when available.
2. Establish what work exists and what effects remain uncertain. A process
   handle or PID is only a locator; verify the actual owned process before
   acting on it. A final chat message is not required to recover saved work.
3. Continue from verified material, including reconciliation of a prior
   coordinator's access to shared notes and plans. Transfer old output paths
   only after the
   old writer is confirmed stopped; otherwise use a new attempt directory or
   isolated worktree. Record adopted work and leave uncertain old output intact.
4. Verify the integrated result, update the relevant W rows and this index,
   and refresh the handoff at a wave boundary or consequential change.

Do not delete these notes or a worker's only saved result just because the
agent is gone. Move enduring conclusions and unresolved work to their owners
before retiring a coordination record. Existing development evidence-retention
rules still govern run artifacts. Small files are versioned with coherent
commits, while workers save intermediate work without waiting for a commit.

The current wave is authorized. Save each worker handle immediately after
spawn, inspect its initial checkpoint and track useful partial results. Next
integrate the three returns into one proposed comparison/decision account,
then arrange independent review and report the result. Do not start empirical
trials merely because this preparation succeeds.

## Review disposition

The coordinator inspected both saved reviewer files. No blocking findings.
Finding 1 is resolved: the first-wave table identifies primary findings files
inside each task's attempt directory; the brief also grants progress and
final-return files. The old single-file-only instruction no longer conflicts
with checkpointing. The recovery guidance also makes the prior coordinator a
potential writer to reconcile before taking over shared notes and plans.
The original review is preserved against its exact snapshot, not rewritten to
describe the correction. Validation checks the final documents and snapshot
identities; no actual sleep/network-fault experiment was performed.

Dispatch observation: 2026-10-26T15:14:26.806772+00:00. One review worker plus the coordinator; main inquiry workers remain unstarted.
