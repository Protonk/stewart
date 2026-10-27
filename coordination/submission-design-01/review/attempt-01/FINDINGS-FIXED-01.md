# First fixed-candidate review

Candidate binary `b14f590ad1c67256006382210b97d41c9a58bacace85fbea70334f564cd60b29`; exact source/docs in `REVIEW-INPUTS-02.json`. Reviewer independently verified eight source/document pins and the primary binary (9/9). This candidate partly corrects v1; it is not accepted as the completed result.

## Confirmed corrections

The reviewer's `probe_fixed.py` used 22 of the separately authorized 24 fixed-primary invocations, not part of v1's 14. Launcher PID 84613 exited 0. Evidence is `.scratch/submission-prototype-01/review/probe-fixed-01/`, with launch metadata and complete external stdout/stderr beside it. One `after_stage` process was independently observed stopped, snapshot, then SIGKILLed. No subprocess remains, no original fixture was changed, and no evidence was deleted.

- R1: after moving the acknowledged add's tail commit to an independent witness, resolve, inspect and cancel all refuse `integrity_error` rather than regressing to a pending/cancellable empty state (commands 13–15).
- R2: after the real prepublication interruption, altering only the candidate audit in a copied pending plan makes resolve, cancel and resume all refuse `integrity_error` with the invalid-transition diagnostic (commands 10–12).
- R3: a malformed unrelated init-attempt receipt permits a new exact-source edit, original-element read and current inspection (commands 4–6). The intact comparison also succeeds (command 3). A malformed attempt belonging to the interrupted request still refuses its resume, with the original current answer invariant (commands 7–9).

Source supports these observations: historical-prefix transition validation applies to pending disposition paths; independently recorded outcomes identify required acknowledged publications; and request-key digest prefixes scope attempt discovery before parsing, followed by full request-reference checks. All previous witnesses remain retained. The complete behavior still needs final-source/driver review after R4.

## R4 — Preparation damage becomes an unintended global answer dependency

**Blocker introduced by the first outcome-receipt fix; independently reproduced and accepted by root for correction.**

The fixed `history()` validates every `outcome-*.json` and its publication before returning any current state. This treats a preparation issuance as though it were authoritative current membership. Preparation is expressly not an edit or authoring mode.

Stale-preparation comparison observed by this reviewer:

1. Prepare revision 1 (command 16), then add an element to reach revision 2 (17). The earlier preparation is now stale by contract.
2. A fresh intact clone accepts the next add at revision 3 (18).
3. In another clone, move only the old preparation publication to an external witness. Current commits, selected bytes and all other records remain.
4. Current inspect (19), original selected-element read (20) and the same fresh add (21) all refuse `integrity_error` because that stale issuance is absent. Resolving the affected old preparation (22) also refuses; that last refusal is appropriate.

Evidence: `probe-fixed-01/commands/016`–`022`, `obsolete-preparation.original.json`, `obsolete-preparation-move.json`, the external source witness, and `snapshots/obsolete-preparation-final`.

Current unsubmitted preparation is the same distinction, not an exception: it identifies an inspectable candidate but does not gate continued editing. The independent driver's original `corrupt_preparation_issuance` case in run-005 supplies this other case. Its raw commands 1–3 establish init/add/prepare at revision 1; command 4 appropriately refuses submission using the corrupted issuance; command 5 inappropriately refuses current inspection on that same unrelated-to-membership damage. The original expectation that inspect can still show the unsubmitted answer should be preserved. The failure is not repaired by weakening that assertion.

Recommended resolution, accepted by root: global state-history validation needs state-changing outcome receipts to detect acknowledged missing tails. Select those before parsing unrelated preparation outcomes. Verify each preparation's own outcome/publication when resolving, resuming, cancelling or submitting that preparation. If a submitted commit names an issuance, its validity remains a dependency of that final-state claim and must still be checked. Retain all damaged records and exact diagnostics; this separation grants no repair, purge, silent reissuance or renewed investigation.

## D1 — Independent driver assumed an unpromised commit-stage suffix

The strengthened barrier observer in run-005 searched for `stage-*-commit`, but the frozen implementation plans `record_stage` as `stage-*-record`. The published interface describes the attempt's `record_stage` coordinate and barrier semantics, not a `-commit` suffix. The reviewer identified the mismatch statically and reported it before inspecting the final failed count.

Run-005 preserves 70 selected cases, 42 passed, 28 failed, 1,639 assertions and 382 invocations. Root/driver attribute 27 failures to that observer error; R4 is the other failure. Final review will independently check the failed rows and corrected observer. The correction must inspect the exact request-bound attempt coordinate and staged commit content, preserving the distinction between after-stage and before-publication. It must not remove the comparison or reinterpret the failed run as passing.

## Current disposition

Root accepted R4 and commissioned its narrow correction. No more invocations of this partly corrected candidate are planned; two of its allowance remain unused. Final source/binary and final complete driver freeze are pending. No production custody, runtime handoff, confinement, physical reclamation, all-host or power-loss guarantee follows from these observations.
