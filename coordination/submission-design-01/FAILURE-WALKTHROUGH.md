# Failure walkthrough of the accepted submission direction

2026-10-27. Coordinator desk review of DESIGN.md and CONTRACTS, not independent
review, executed tests or harness qualification. The accepted direction is a
recorded collection edited atomically, an inspectable preparation handle, dry-run
submission by default, and explicit confirmed submission ending edits. Exact
mechanisms below are requirements for a later implementation to demonstrate.

## Model used for this review

Let the current answer be audit A, recorded revision r, and an ordered set of
element identities with exact bytes/metadata. A successful edit produces a new
revision. An issued preparation handle identifies A, r and its generated manifest.
A successful actual submission records one fixed result and rejects later edits.
Preparation records, operation receipts and internal partial files do not create
authoring lifecycle stages. Handles do not grant access outside the commission.

| Case | Required outcome and why |
| --- | --- |
| Ordinary addition and helper exit | Fresh invocation recovers the exact element and membership through a supported reference. A source-path change is irrelevant to held bytes. |
| Conflicting or oversized edit | Refuse before publication, identify the conflict/limit, leave the previous current collection unchanged. Any temporary effects still need their accurate failure account. |
| Replacement uses an obsolete element handle | Recommended mechanism: refuse the old revision, name the supported inspection route. Do not replace the later element merely because a logical ID matches. Exact handle semantics remain a mechanism choice. |
| Prepare races with an edit | It must inspect one coherent revision. If an edit commits afterward, the returned handle can become stale; it must never describe a mixed collection as one revision. |
| Edit after prepare, then restore equal bytes | Earlier preparation stays stale because the recorded revision/selection changed. Digest equality does not identify the same selection or operation. |
| Default or explicit-false submit | Revalidate the issued selection and report what would happen without sealing, reserving a final submission or changing answer state. It does not prove a later call will succeed. |
| Caller-made manifest or hash | It is not itself an issued handle. Validate issuance and audit/revision binding; do not silently accept a caller's assertion that preflight ran. Exact issuance mechanism is still owed. |
| Handle from another audit | Refuse before mutation even if all payload bytes match. Both audit binding and selected-record identity matter. |
| Held bytes damaged after prepare | Refuse the affected claim with integrity diagnostics. The unchanged revision number cannot substitute for read-time byte verification, and a live source must not repair the observation silently. |
| Edit races with confirmed submission | One serialization boundary binds the final check to the publication. Either the edit commits first and submission is stale, or submission commits first and the edit is refused. No valid ordering permits both effects against incompatible selections. |
| Two distinct preparation handles submit the same revision | At most one submission is recorded. A later different request receives an already-submitted diagnosis with the fixed-result reference; it is not recorded as a second successful submission. This is a coordinator deduction from the single ending boundary. |
| Same confirmed submission repeated after a lost reply | Recover its existing outcome through the same handle; no second selection, payload copy or audit execution. The handle can supply the request reference without a third auditor-facing argument. Bind its intent before effects. |
| Interruption before commit publication | The prior current collection remains authoritative; planned partial work and diagnostics remain attributable to this operation. Supported resolution must not adopt unrelated files. |
| Interruption around publication/synchronization | The caller may be uncertain whether the operation committed. Never report definite no change solely from a lost reply or nonzero exit. Resolve the same request by verified records; invalid/unreadable records are not treated as absence. |
| Submit succeeded, but manager notification failed | Editing remains ended and the same result remains identified. This is not authority to reopen or resubmit. The actual delivery/recovery route is deferred, so this review establishes no eventual-delivery guarantee. |
| Submit succeeded, but auditor process/tool descendant remains alive | Artifact edits are refused by the authoritative tool boundary. Submission alone is not proof of termination or removal authority; stopping and retirement remain separate work. |

## Consequences for implementation

An in-memory Rust prepared type helps keep library callers honest but cannot
establish persisted issuance, current bytes, cross-process exclusion or finality.
Every supported entry must reach the same authoritative validators and mutation
gate. There must be no fallback that trusts the caller's manifest or silently
re-prepares on a stale handle.

The prototype must expose enough operation identity to recover a lost edit reply
as well as a lost submit reply. The two-argument constraint is for submission;
mutation request identity can be carried by the chosen tool protocol. It cannot
be supplied only in the reply that might be lost. Matching keys return the same
intent; unkeyed edits remain distinct rather than deduplicated by content.

Preparation must not silently become a hold on obsolete artifacts. An edit can
invalidate its handle; whether obsolete payloads are reclaimed depends on their
actual protected uses. Likewise, deleting an active element need not imply an undo
service. Receipt/failure-evidence retention and physical reclamation need concrete
authority and qualification, without a new user-operated lifecycle.

No substantive-outcome discriminator is required by this design. Mechanical
validity does not establish scientific sufficiency. Do not parse ordinary prose
citations into implicit dependencies or silently rewrite them during replacement.

## Remaining boundaries

The failure reasoning supports preparing a bounded local prototype commission.
It does not by itself make a product deployment ready. Concrete storage/access,
handle issuance and mutation recovery must be selected and tested. Physical
reclamation, manual handback, manager delivery, stopped execution and single-close
integration retain their current obligations and qualification gates.

No fatal logical conflict was found in this desk walkthrough. That is a limited
coordinator assessment; independent review and runtime interruption/race controls
remain necessary before claiming an implemented guarantee.
