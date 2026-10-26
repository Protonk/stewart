# Dispatch guidance review 01 — return

Completed 2026-10-26. **No blocking findings.** The guidance supports the requested
laptop dispatch and recovery practice. One small conflicting edit boundary
should be reconciled before the substantive inquiry briefs are dispatched.

## Inputs and verification

Reviewed the six snapshots identified by
`.scratch/coordinator-dispatch/review-inputs-01.json`, based on
`777c87b3f0257f5299148677527fd0fb5d036e5a`. All six byte lengths and SHA-256
values matched the manifest, checked with `/usr/bin/python3 -I -B` using the
standard-library `pathlib`, `json` and `hashlib` modules. The live assignment
brief was read first; its saved counterpart was also reviewed. No other
repository documents, external sources or neighboring projects were read.

References below name files **inside the saved review-inputs-01 snapshot**,
not the concurrently changing working copies. Scope: AGENTS.md; the
DEVELOPMENT-PLAN.md dispatch section (lines 135–230); handoff opening (1–80);
VISION-PLAN.md; coordinator notes; review brief.

## Findings, ranked by consequence

1. **Low — first-wave output ownership has two descriptions.**
   DEVELOPMENT-PLAN.md:142–150 permits workers to edit only their assigned
   single `<run>/answers.md`, `routes.md` or `coverage.md` file. Lines 204–211
   require each attempt to write `PROGRESS.md`, developing findings and
   `RETURN.md`, with separate large-output paths. Taken literally, the former
   boundary forbids the latter checkpoint files. The eventual concrete brief
   can resolve this, so it is not a blocker to this guidance preparation or the
   current review. Suggested correction: make the overview/table identify the
   task's assigned attempt outputs; state that the frozen brief enumerates its
   progress, findings, return and evidence paths. Preserve exclusive ownership
   and coordinator-only root-document integration. No additional procedure is
   needed.

## Scenario assessment

| Scenario | Assessment and exact source support |
| --- | --- |
| Approximately ten agents with a lower harness limit | AGENTS.md:86–96 explicitly counts coordinators, reviewers and nested workers across harnesses; the preference is soft, not a target; lower limits and memory demand prevail. It requires a reason for exceeding the preference and coordination of nested dispatch. DEVELOPMENT-PLAN.md:186–193 treats four slots as current, not permanent. |
| Ordinary staffing without user micromanagement | AGENTS.md:58–68 and 94–96 authorize routine decomposition, replacement, integration and review within the commission. VISION-PLAN.md:44–60 preserves user control over consequential decisions without routine relaying. Preparation remains distinct from later execution. |
| Worker disappears after substantial findings | AGENTS.md:107–118 requires early and progressive disk saving and a return saved before chat. Notes:44–51 permits recovery without a final message. Unfinished findings remain reviewable, not automatically accepted. |
| Long command or spawn reply is lost | AGENTS.md:114–117 requires command/output/process evidence and denies outcome inference from a missing reply; lines 125–131 require reconciliation before repeating uncertain effects. Notes:35–40 explicitly handles missing spawn replies using recorded task identity and available inventory. Notes:46–48 requires verifying a process before acting on a locator or PID. |
| Coordinator disappears | Handoff:27–34 locates the index and divides current state among plan, index and worker files. Notes:44–53 and plan:223–230 provide reconstruction from actual files, diffs, outputs and available harness observations. The old-writer rule must apply to any potentially active writer, including a previous coordinator; a changed conversation alone is not proof of termination. |
| Old worker might still write | AGENTS.md:125–131 and notes:49–51 require confirmed stopping before path transfer or isolated replacement paths/worktrees, with old output retained. Plan:209–210 gives replacements new attempts. This avoids relying on silence to transfer ownership. |
| Stale checkpoint or saved draft is mistaken for proof | AGENTS.md:109–113 says cadence is neither a timeout nor liveness evidence; lines 130–136 separate saved drafts from verified integration. Notes:7–8 and 38–40 reinforce observed state and the return/verification distinction. |

The safeguards are proportionate: ordinary files and harness facilities,
meaningful checkpoints, one dispatch index and separate program dependencies.
AGENTS.md:119–137 and notes:55–59 preserve evidence and require disposition
before retirement. VISION-PLAN.md:69–81 rejects staffing as a success measure
and keeps development supervision distinct from product obligations.

## Limits and disposition

This is a documentary/tabletop review, not a sleep, network-loss, process-stop,
spawn-recovery or filesystem fault experiment. It establishes that the written
steps cover these scenarios; it does not establish actual harness persistence,
global fleet visibility, log durability, stop enforcement or successful recovery.
No runtime tests, Git mutations, root-document edits or further dispatch were
performed. The coordinator should disposition finding 1, verify the saved
return, and integrate the guidance; no substantive inquiry was started here.
