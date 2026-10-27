# Frozen v1 findings

Reviewed binary SHA-256 `b6463c1bfba01a52712f16b5f4a5c316c6eb04027a52e872a252c02902724f28`; source population is root's `REVIEW-INPUTS-01.json`. Reviewer verified all eight source/document snapshots and the binary (9/9 pins). Root had already relayed the implementer's proposed fixes for R1 and R2; R3 was independently identified in source and reproduced.

The finite independent probe is `probe_v1.py`; launch/streams and full specimen evidence are `.scratch/submission-prototype-01/review/probe-v1-01*`. It completed with 14 subject invocations out of the authorized maximum 24, three comparisons, one actual stopped/killed process, and no deletion. Every corruption uses a fresh reviewer-owned clone of its own baseline. The original changed record is moved to an external witness, not destroyed; original driver fixtures and frozen inputs are unchanged. These are defect-reproducing comparisons, not a passing product qualification suite.

## R1 — A missing acknowledged tail commit becomes pending and cancellable

**Blocker for acknowledging recoverable/final operations; already reported by implementer, independently reproduced.**

Observed sequence: invocations 1–2 acknowledge init and add at revision 1. A fresh clone preserves that state. The reviewer moves only the last authoritative commit to an independent witness; its original exact bytes and the prior successful result remain. Invocation 9 `resolve(answer-a)` returns success with `status: pending`; invocation 10 `inspect` returns revision 0 with an empty selection; invocation 11 `cancel(answer-a)` succeeds. The staged commit witness still exists inside the store as well, but no ordinary read recognizes the acknowledged outcome.

Source: frozen `main.rs` `history()` discovers only currently present `commit-*` names; `committed()` returns false when the planned commit name is absent. No independent completion receipt distinguishes an interrupted prepublication plan from a previously acknowledged publication whose tail went missing. The request and payload alone do not prove which situation happened.

Consequence: supported resolution converts missing custody evidence into permission to cancel an acknowledged operation, and current inspection presents an earlier selection without reporting that gap. A final submission can lose its finality by the same tail mechanism. This conflicts with preserving uncertainty and refusing to treat damaged committed evidence as ordinary absence.

Recommended resolution: publish and synchronize an exclusive completion/outcome receipt before acknowledgment, binding the operation and exact authoritative result. Read paths must validate retained outcome claims against required commit/issuance evidence and diagnose an absent required result. A pending operation without an outcome may complete only its original planned effects. Do not claim this detects wholesale coordinated removal of all relevant evidence or authenticates history against an owner rewriting the store.

Evidence: `probe-v1-01/commands/009` through `011`, `acknowledged-tail.original.json`, `tail-move.json`, `snapshots/base`, and `snapshots/acknowledged-tail-final`.

## R2 — Resolve/cancel accept an invalid pending transition

**Blocker for supported uncertain-operation disposition; already reported by implementer, independently reproduced.**

Observed sequence: invocation 12 starts add `pending-b` against the intact revision-1 baseline. Its stderr marker identifies `after_stage` and planned commit 2; the reviewer observes kernel SIGSTOP (signal 17, wait status 4479) for PID 70592, saves the stopped store, sends SIGKILL and records exit -9. Only the pending request's candidate audit is changed to `foreign-audit`, with the original retained independently. Invocation 13 `resolve` still reports ordinary pending success; invocation 14 `cancel` succeeds and binds the changed request digest.

Source: `plan()` validates request-key consistency and intent fields but does not validate the candidate against its predecessor. `resolve` and `cancel` call `committed()` and cancellation checks without validating that pending plan against its recorded historical base. `complete()` does validate against the current base, but that does not protect the other disposition paths.

Consequence: an unverifiably damaged undertaking receives ordinary pending status and attributed cancellation rather than preserving its invalid transition diagnostic. The protocol explicitly refuses cancellation of unverifiably damaged outcomes. A stale but valid plan must remain distinguishable from a damaged plan; validating only against the current tip would reject both and miss the distinction.

Recommended resolution: recover the verified history prefix selected by the plan's exact predecessor, validate the full planned transition there, and apply that validation to resolve/cancel as well as completion. Preserve damaged raw bytes and their diagnostics. A valid stale plan can still receive bounded cancellation without performing its old edit.

Evidence: `probe-v1-01/commands/012` through `014`, including BARRIER/SIGNAL/EXIT; `corruption-witnesses/pending-plan-audit.*`; `snapshots/012-stopped` and `snapshots/pending-plan-final`.

## R3 — Unrelated malformed attempts impose a permanent editing obstacle

**Blocker for the claimed bounded recovery/continued-authoring behavior unless explicitly narrowed; independently found.**

Firing/difference/invariance comparison:

- Invocation 3 adds a second element successfully at revision 2 in an intact clone.
- In a separate clone, the sole changed property is the historical init attempt receipt: it is replaced with a duplicate-key malformed record, preserving its original outside the store. The committed init/add chain and all selected payloads remain unchanged.
- Invocation 4 tries the same fresh addition under a new key. It fails with `integrity_error`, naming duplicate `schema`, after a new request has been allocated. Invocation 5 still returns exactly the revision-1 state and invocation 6 returns exactly the external raw payload witness.
- Invocation 7 successfully cancels the refused new request. Invocation 8 tries another fresh key and again fails on the unrelated init-attempt damage. The offered generic instruction to preserve the record does not provide a supported way to continue this otherwise verified answer.

Source: `attempts(r)` decodes every `attempt-*.json` receipt before comparing its `request` reference with `r`; `complete()` calls it for every new mutation, before writing its own fresh attempt. The random attempt filename supplies no request-scoped discovery key. Unrelated malformed retained evidence therefore becomes an implicit dependency of every later edit.

Consequence: ordinary fresh editing acquires an obligation to repair private historical attempt state, even though the new operation can read its exact source and no byte from the damaged attempt needs adoption. Cancellation of the new undertaking cannot remove the obstacle. This exceeds the request-specific recovery requirement and is the concrete simplicity concern that a development-only label does not settle. Damage that prevents vouching for a selected commit or same-operation adopted stage should still refuse; this case does neither.

Recommended resolution: scope attempt discovery to the current request by a mechanically verifiable association available before decoding unrelated records (for example, request-bound attempt names), and validate every candidate before adoption. Retain/report unrelated damage without making its repair a prerequisite for a new independent operation. Preserve the firing control and old-state/raw-byte invariance checks in the regression evidence; add a same-request damaged-attempt control so narrower discovery does not silently adopt unverifiable work.

Evidence: `probe-v1-01/commands/003` through `008`, `corruption-witnesses/unrelated-init-attempt.*`, `snapshots/base`, and `snapshots/unrelated-attempt-final`.

## Other static observations at this checkpoint

All operations take the directory lock, state publication uses exclusive hardlinks from complete stages, control records use the shared duplicate-key parser, current payloads are reverified, and matching keys are compared before rereading source. Source-independent committed readback and stale/version semantics appear structurally coherent. The code distinguishes `after_stage` before commit-stage write from `before_publish` after it. These observations remain subject to frozen final-source/evidence review and do not establish host confinement or durability.

No broader v1 run is needed to repeat the driver's main population. Ten of the v1 invocation allowance remain unused. Fixed-source regression and final evidence require the promised later freeze/grant. Root owns each finding's disposition; this file does not amend product scope or authorize repairs.
