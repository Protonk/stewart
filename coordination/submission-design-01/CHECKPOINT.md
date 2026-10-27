# Continuing-session checkpoint

2026-10-27, saved in the pre-sleep window. This is not a turnover; the user intends
to resume this session after sleeping the machine. Root remains coordinator.

## Completed and accepted

- Exact recorded artifact bytes survive helper exit. Add, handle-based replace and
  delete should be atomic, with early informative refusal and supported recovery.
- No draft-status lifecycle or separate promotion of artifact bytes into custody.
- Prepare generates an inspectable manifest and issued handle for the exact current
  collection. Editing remains open and later edits make the handle stale.
- Submission requires that handle, defaults to dry run, and needs explicit true
  to atomically fix the result and end edits. The same handle recovers the same
  submission after a lost reply. No call-stack trick is required.
- Manager-side simplification is deferred. Submission is not delivery, process
  termination, environment removal or completed audit close.

CONTRACTS owns the accepted behavior. DESIGN.md supplies the candidate mechanism;
FAILURE-WALKTHROUGH.md is a completed coordinator desk review with unexecuted cases.
NEXT-WORK.md is a prepared, uncommissioned bounded Rust prototype brief.

## Exact resume point

Discuss commissioning that prototype, or select the real storage/access boundary
before a direct product implementation. The prototype would test atomic edits,
issued/stale handles, dry-run invariance, competing mutations/submissions and
lost-reply recovery with retained independent witnesses. It would qualify no
production access boundary, physical reclamation, manager delivery or safe removal.
No agent is assigned; no uncertain effect or background command is pending.

## Recording and retained evidence

Starting HEAD: e06a46bfb8ceb8f206955b4d9a56b1bfa4071a46, initially clean.
Saved edits: CONTRACTS, DEVELOPMENT-PLAN, coordinator current account/turnover,
and this design directory. Source/runtime/tests and frozen bundled guidance are
unchanged. No runtime tests, new behavioral comparisons or custody operations ran.
The final documentation/source-invariance checks and exact input snapshots are
under `.scratch/coordinator-intake-run-012/FINAL-CHECKPOINT.json` and `checkpoint-inputs/`.
The current coordinator account owns that finite evidence directory.

Two Git staging attempts failed creating `.git/index.lock` with `Operation not
permitted`; they are retained in RECORDING.json and RECORDING-02.json there.
No commit was created or permissions repair attempted. Preserve unrelated changes
if Git state differs on resume. Historical evidence and the preceding candidate
remain retained; no pruning occurred.
