# Atomic answer-editing prototype result

The bounded disposable prototype is complete; its final independent process
run passes all 72 cases. Root accepts the fresh review's bounded assessment:
all five implementation findings are corrected, with no remaining blocker for
this commission. The user
commissioned it on 2026-10-27 by “Ok you may go ahead as planned.” The source
checkpoint was clean cf7216f. Final executable SHA-256 is
`cacc57df666c1b1eeef85c14a3a17a2a7d679d21bd480358548874062838c0de`, frozen with
matching sources and valid writer-control executable in
`.scratch/submission-prototype-01/REVIEW-INPUTS-03.json`.

## Implemented boundary

The separate [Rust prototype](prototype/attempt-01/README.md) implements the
[process protocol](PROTOCOL.md): recorded add, handle-based replace and delete;
inspect/read; independently issued prepare; default dry-run submit; and explicit
true submission that fixes the exact prepared revision and ends edits. Equal
bytes do not collapse element identity or make an edited revision current again.
There is no draft promotion or second upload into custody.

The helper pins the store directory, takes a nonblocking lock, verifies control
records and selected bytes, and publishes a complete immutable commit by an
exclusive hardlink. File and directory synchronization precede acknowledgment.
Request bindings name intended effects before they occur. Preparation issuance
and state-changing acknowledgment receipts have distinct roles: current answer
operations must not acquire dependencies on unrelated unsubmitted preparations.
A submitted answer does depend on the issuance it selected.

The same operation identity resolves an interrupted edit or lost submission reply.
Recovery can adopt only its own planned, verified outputs. A changed historical
base, damaged record and unavailable original bytes receive distinct diagnostics;
none grants another investigation. The prototype exposes resolve/resume/cancel
as development probes. These verbs are not an adopted product workflow, and this
study does not establish their usability or justify adding authoring stages.

## Findings and disposition

| Finding | Evidence and disposition |
| --- | --- |
| Unknown fields accepted by unit-form inspect | Independent run-002 failed its refusal control. Explicit operation-field validation was added; the driver checks all twelve operation forms. |
| R1: missing acknowledged tail appeared pending and cancellable | Implementer identified, reviewer independently reproduced. Separate synchronized outcome receipts make a missing required acknowledged publication diagnostic. This does not detect coordinated removal of every witness. |
| R2: inconsistent pending plan could be resolved/cancelled as ordinary | Implementer identified, reviewer reproduced after observed stop/kill. Pending plans are validated against their exact historical predecessor before disposition. Valid stale plans remain distinguishable. |
| R3: malformed unrelated attempt blocked every new edit | Reviewer identified and reproduced. Attempt discovery is scoped by request identity before decoding; relevant malformed attempts still refuse. No repair/purge service was added. |
| R4: preparation damage blocked otherwise valid current answers | Reviewer reproduced the stale case and confirmed the driver's original unsubmitted-preparation expectation. Root kept that expectation. Separate acknowledgment namespaces now preserve ordinary editing while own preparation operations and chosen submitted dependencies diagnose damage. Final driver and 24 targeted reviewer calls confirm the correction. |
| D1: driver assumed an unpromised staging suffix | Twenty-seven run-005 failures were observer errors. The observer now follows the request-bound attempt's exact record_stage and validates staged commit content. Run-006 passed all 32 affected/control cases. The failed run stays retained. |

The independent review's [v1 findings](review/attempt-01/FINDINGS-V1.md) and
[first corrected candidate findings](review/attempt-01/FINDINGS-FIXED-01.md)
preserve the observations and rejected interpretations. The implementation and
driver returns retain exact source/build lineage; later success does not rewrite
earlier failures.

## Recorded verification

The final independent driver run uses the frozen executable and a separately
compiled valid writer variant. Run-007 passes **72/72 cases, 2512/2512 assertions,
522 helper invocations**, with every start accounted for by an exit and no timeout.
It observes 32 actual kernel SIGSTOP barriers, followed by 19 SIGKILL and 13
SIGCONT controls. It verifies distinct pre-stage/pre-publication windows through
recorded coordinates and contents, not merely hook labels. Exact commands, source
and executable copies, raw streams and external witnesses are in `driver/run-007/`
and `driver/run-007.launch/` beneath the report's scratch directory.

| Independent driver run | Passing/selected cases | Assertions | Helper invocations | Disposition |
| --- | --- | --- | --- | --- |
| 001 | 5/5 | 242 | 52 | Initial diagnostic selection. |
| 002 | 58/59 | 1723 | 425 | Unknown-field implementation failure retained. |
| 003 | 1/1 | 43 | 6 | Deterministic contention observation. |
| 004 | 8/8 | 411 | 61 | Intermediate recovery/refusal/writer controls. |
| 005 | 42/70 | 1639 | 382 | 27 observer failures and R4; retained as failing. |
| 006 | 32/32 | 1204 | 239 | Corrected observer with affected and invariance cases. |
| 007 | 72/72 | 2512 | 522 | Final complete population on cacc57df. |

Counts above are different measurements, not interchangeable or additive unique
coverage. Controls cover exact retained bytes after source loss/change, identity
despite equal bytes/names, duplicate and malformed controls, finite bounds,
stale/cross-audit handles, dry-run invariance, edit/submission races, actual
interruption at four windows, lost replies, scoped adoption and relevant versus
unrelated damage. The [driver return](driver/attempt-01/RETURN.md) owns the exact
selector population and evidence paths.

The fresh reviewer used 14 v1, 22 intermediate and 24 final helper invocations in
separate bounded probes. Those are additional targeted comparisons, not the
driver's 72 cases. Its final [review](review/attempt-01/REVIEW.md) and
[return](review/attempt-01/RETURN.md) own source findings and independent raw-evidence
verification. Implementation smoke and local before/after comparisons are reported
separately in its [return](prototype/attempt-01/RETURN.md), including a retained
44-command comparator failure caused by an incorrect baseline reason expectation.
The reviewer separately verified 19878 raw trace/inventory checks and 134 final
association/stage checks. Those validate evidence consistency, not additional
subject cases; the verifier's earlier text-help parsing error remains retained.

Root's first integration check ran before the driver return had been saved:
24/25 checks passed and the missing return was correctly reported. That record
remains in INTEGRATION-CHECKS.json; final readiness is checked in a fresh record.
INTEGRATION-CHECKS-02.json records 25/25 source/binary matching, exact selected-case
and count reconciliation, saved-handback and product-scope checks. The staged-file
check then found extra EOF blank lines in two reviewer probes; root removed only
those, preserving exact executed originals in INTEGRATION-CLEANUP.json. The final
INTEGRATION-CHECKS-03.json adds staged-file validation. COMPLETION.json
records final saved-file identities, Git outcome and no remaining worker activity.

## Scope and next decision

This is local process-interruption evidence on Apple Silicon macOS, using offline
Rust builds and an independent stdlib Python process driver. No installed product
code, frozen Python/bundled bytes or qualified C implementation changes here.
No pytest nodes or installed-wheel checks were run for this separate prototype.

All old payloads, failed stages, interrupted stores, external byte witnesses and
corrupted originals remain retained. Delete removes current membership only.
This does not establish physical reclamation, holds, production access enforcement,
manager delivery, auditor termination, retirement/close, human handback,
power-loss/storage-failure durability, or Linux/WSL support. State which records
are required for a claim before treating every retained record as its dependency.

Interruption before the initial request binding is published is outside the
verified commit barriers: retained unpublished residue can leave an uninitialized
nonempty directory requiring a fresh explicit store. No issued request or never
captured bytes are inferred from that residue. This is a prototype limit to carry
into the product recovery decision, not qualification of every possible cut point.

Root's next recommendation is to settle the actual custody/access boundary and
the supported recovery interaction before product integration. Preserve the small
auditor authoring surface; determine how the tool accounts for an interrupted
operation without exposing internal stages as routine user work. Manager-side
delivery remains the later discussion already deferred by the user. No further
implementation is commissioned by this recommendation.

This report owns `.scratch/submission-prototype-01/`, the fresh driver/reviewer
specimens named in its records, and their retained witnesses. No pruning/removal
was performed. Fieldwork reflections remain separately in the granted run-012
notes directory; no turnover was requested or written.
