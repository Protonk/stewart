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
coordinator integration and independent review. That preparation wave is now
complete. Runtime implementation, fresh audits, live harness/network experiments and custody disposal remain outside
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

User steering, 2026-10-26: Claude usage is reported at 99%, with no auto-buy
credits. Do not start or resume a Claude session without explicit permission;
the deliberate limit study is deferred, not for today. All three workers were
notified. The completed wave used this harness; no Claude session was launched.
Recheck future usage rather than carrying today's percentage forward as fact.

| Assignment / scope | Observed state and handle | Saved work and next action |
| --- | --- | --- |
| `dispatch_guidance_review`, preparation only | Integrated after coordinator verification; harness handle `/root/dispatch_guidance_review`. No worker work remains. | [Brief](dispatch-review-01-BRIEF.md), [progress](dispatch-review-01-PROGRESS.md), [return](dispatch-review-01-RETURN.md). Source base `777c87b` plus six exact inputs in `.scratch/coordinator-dispatch/review-inputs-01.json`. One low-severity finding resolved below; final checks in `.scratch/coordinator-dispatch/validation-01.json` and `.log`. |
| `answers`, W01/W02 | Integrated after coordinator checks and independent review; handle `/root/inquiry_answers`. No worker work remains. | [Brief](successor-inquiry-01/answers/BRIEF.md), [progress](successor-inquiry-01/answers/attempt-01/PROGRESS.md), [return](successor-inquiry-01/answers/attempt-01/RETURN.md). Source `250d494` and `.scratch/successor-inquiry-01/inputs-01.json`; exclusive attempt outputs are now saved. Integrated result: [first-wave findings](../SUCCESSOR-PREPARATION-FINDINGS.md). |
| `routes`, W04–W11 | Integrated after coordinator checks and independent review; handle `/root/inquiry_routes`. No worker work remains. | [Brief](successor-inquiry-01/routes/BRIEF.md), [progress](successor-inquiry-01/routes/attempt-01/PROGRESS.md), [return](successor-inquiry-01/routes/attempt-01/RETURN.md). Source `250d494` and `.scratch/successor-inquiry-01/inputs-01.json`; exclusive attempt outputs are now saved. Integrated result: [first-wave findings](../SUCCESSOR-PREPARATION-FINDINGS.md). |
| `coverage`, W01–W20 and transition | Integrated after coordinator checks and independent review; handle `/root/inquiry_coverage`. No worker work remains. | [Brief](successor-inquiry-01/coverage/BRIEF.md), [progress](successor-inquiry-01/coverage/attempt-01/PROGRESS.md), [return](successor-inquiry-01/coverage/attempt-01/RETURN.md). Source `250d494` and `.scratch/successor-inquiry-01/inputs-01.json`; final source-only check in `.scratch/successor-inquiry-01/coverage/attempt-01/validation-01.json`. |
| `review`, independent integration review | Integrated; handle `/root/inquiry_review`. No blockers; one low locator correction resolved. No reviewer work remains. | [Brief](successor-inquiry-01/review/BRIEF.md), [progress](successor-inquiry-01/review/attempt-01/PROGRESS.md), [return](successor-inquiry-01/review/attempt-01/RETURN.md), [disposition](successor-inquiry-01/REVIEW-DISPOSITION.md). Base `8b6420a` plus 23 exact inputs in `.scratch/successor-inquiry-01/review-inputs-01.json`. Initial checkpoint identity: `.scratch/successor-inquiry-01/review-checkpoint-01.json`. |

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

All three inquiry returns and the independent review are integrated. The
[first-wave account](../SUCCESSOR-PREPARATION-FINDINGS.md) is the current result;
[corpus retention](successor-inquiry-01/CORPUS-RETENTION.md) records protected
original sources. Final document validation is
`.scratch/successor-inquiry-01/validation-02.json` and `.log`. Next obtain the
bounded A3 pilot commission, then prepare/review finite packets before fresh
recipient dispatch. Actual route probes, legacy inventory and helper comparisons
remain separately gated. No current worker or empirical trial remains active.

## Earlier dispatch-practice review disposition

The coordinator inspected both saved reviewer files. No blocking findings.
Finding 1 is resolved: the first-wave table identifies primary findings files
inside each task's attempt directory; the brief also grants progress and
final-return files. The old single-file-only instruction no longer conflicts
with checkpointing. The recovery guidance also makes the prior coordinator a
potential writer to reconcile before taking over shared notes and plans.
The original review is preserved against its exact snapshot, not rewritten to
describe the correction. Validation checks the final documents and snapshot
identities; no actual sleep/network-fault experiment was performed.

Earlier dispatch-practice review began 2026-10-26T15:14:26.806772+00:00 with one reviewer plus the coordinator. Its result above is complete; use the index for the subsequent inquiry wave.
