# Authoring boundary after the prototype

Discussion, 2026-10-27, after prototype commit 00d7c08. This note records a
candidate mechanism and proof; CONTRACTS owns the accepted product decisions.
No new implementation, worker, harness/Claude launch or removal is commissioned.

## Accepted directions

The user accepted persistent per-audit custody associated with the repository,
outside the disposable workspace; the tool integration owning same-operation
accounting after interruption; and immediate membership changes with superseded/
deleted payloads retained until authorized closure. Holds and remaining custody
obligations still constrain removal. Exact placement, grants, moves and backups
remain implementation/qualification work. There is no promised version browser.

The user then asked, “does it want to be a ledger?” and proposed proving that an
interruption will surface to the auditor with what to retry, with no additional
facility beyond another add when there is nothing to replace. That is a design
proposal, not already measured auditor-facing behavior.

## Coordinator recommendation: a custody ledger with retained payloads

An append-only set of exclusive operation, publication and outcome records is a
good fit. Retain exact artifact bytes separately and bind their identity in the
records. The current answer is the ordered selection established by completed
edits. Recording an attempted operation does not make its element part of that
answer or introduce a draft phase. Append-only authoring does not imply perpetual
retention beyond authorized close. A log of names or digests without recoverable
bytes would not fulfill the undertaking.

This is close to the prototype mechanism; a product schema/ledger implementation
has not been chosen. It is distinct from the frozen Python execution ledger.

## Retrying through the ordinary operation

| Observed state after interrupted add | Required ordinary-operation behavior |
| --- | --- |
| No element published, and that absence is established | Retry the identified addition through add; there is no element handle requiring replacement. Account for any earlier planned/partial work internally. |
| Element published, reply lost | The same-operation add returns the existing outcome and element handle without adding another element. |
| Outcome cannot be verified | Preserve the diagnostic and exact operation reference; do not infer absence or launch an unrelated addition as its recovery. |

The integration must retain an operation reference before dispatch and bind any
retry to it. The retry transport remains open: it may be supplied by the adapter
or carried as an opaque reference accepted by add. It cannot depend on guessing
from source paths, names, equal bytes or the most recent operation. A genuinely
new addition of identical bytes must remain possible. These are operation
identities, not draft element handles or another authoring status.

## Proposed next proof boundary

Prove the actual tool response/re-entry route, beyond persistent ledger inspection.
Use independently witnessed operations at cuts before publication, after
publication but before reply, and during delivery of the tool outcome. Observe
the auditor-facing message, its operation identity and concrete next action.
Repeat add for that undertaking and verify exactly one element; include a separate
intentional equal-byte addition as the differing control and unrelated element
readback as invariance. Retain missing/invalid-outcome refusal rather than force
every case into ordinary retry.

An alive caller may receive the wrapper's process-exit report; loss of the wrapper
or entire auditor requires a named supported re-entry route. A ledger cannot wake
an absent auditor. The candidate promise is visibility during a continuing call
or supported return to that audit; stronger eventual notification requires an
actual delivery arrangement. Showing a pending record in a developer's inspection
does not establish that the auditor received it or understood it. No mechanism or
launch permission for that trial has yet been selected. This settles the next
evidence question without importing manager delivery or an audit restart facility.
