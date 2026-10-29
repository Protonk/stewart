# Auditor retry and re-entry

Prepared 2026-10-29 at the user's request after delegated settlement of manager
custody and initial materials. **Briefing and recommendations, not adopted
auditor changes.** Question types, slots, citation rules, substantive stopping
instructions and answer rendering belong to the next discussion, not this one.
No runtime or real-model tests were run for this briefing.

## The decision in one example

The auditor calls `add("note", "The parser rejects this input.")`. Stewart records
element E17, but the reply never reaches the auditor. The auditor repeats the same
arguments. Under the current ledger design that is a second addition, E18.

Both calls can have succeeded honestly. Equal text and labels cannot distinguish
an intentional second item from repetition after a lost reply. A repeated
`submit(prepared_handle, confirmed=true)` is different: the handle identifies a
particular submission, so a completed outcome can be returned without another seal.

The substantive choice here is whether auditor retry means **make another ordinary
call, using the recorded answer to decide what is needed**, or **repeat the same
logical action without duplicating it**. The latter requires action identity that
survives loss of the reply. Hashes and labels cannot supply that identity.

## What is already decided

The auditor has a form and a ledger, with straightforward replies and no routine
recovery/settlement workflow. There is no resolve/resume/cancel family, manager
interpretation of unfinished authoring requests, or auditor retry-tuning knob.
Completed records determine the answer; torn/incomplete data is not an element.
Equal-byte additions are allowed and never silently merged. Successful edits
preserve selected bytes independently of the originating process.

An answer preparation names an exact recorded revision. Edits make the old
preparation stale; explicit confirmed submit seals once. A completed repeat of
that same submission retrieves its recorded outcome. Manager close and auditor
submit keep their actual seal attribution. A new run continues the same ledger
and cumulative limits; it does not restart the investigation or reset allowances.

These choices do not promise preservation of unrecorded thoughts or a lost model
context. Re-entry must recover the question, permitted world and recorded answer.

## Recommended interaction

Keep the small authoring vocabulary and make `what_am_i_working_with` the reliable
way to regain orientation. When an edit's result is unknown, consult it before
issuing another addition. A new add continues to mean a new item. Do not require
the auditor to invent request keys or classify internal operation states.
Re-entry is an available way to regain orientation, not a mandatory stage or
permission gate before every edit.

The call should provide the audit identity, open/sealed/closed condition, current
answer revision, cumulative allowances, question/material access, current answer
index and recent completed edit receipts. Each receipt identifies the action,
affected element and version, resulting revision, and its completed effect.
Useful details remain attributable observations, not guesses about what the
auditor has read or concluded. The latest relevant refusal is bound to its
operation/revision rather than appearing indefinitely as the current problem.

The default reply is bounded. It includes exact identities, sizes, counts and
explicit ways to retrieve the remaining bytes. The question stays verbatim when
read; any excerpt is marked as such and links to the exact remainder. Answer
elements are readable by their handles. No private custody paths are exposed.
Pagination is bound to a revision; an intervening edit requires a refreshed view,
not a mixture silently called one answer. This refines the earlier promise that
one reply contains the entire recorded answer: one call restores orientation and
access, not a potentially hundreds-of-megabytes model context. It cannot promise
that compaction preserves work the auditor never recorded.

| Situation | Proposed ordinary reply/action |
| --- | --- |
| Read/list/search reply lost | Repeat the read; it changes no answer state. |
| Add reply lost | Re-entry shows completed additions and their handles. The auditor decides whether another item is wanted. Repeating add is a new addition, never implicit deduplication. |
| Replace targeting E17 version 1 succeeded, reply lost | A repeated use of the old version explains the current version and supplies its handle. It must not overwrite a newer edit or falsely say the first replacement never happened. Read the current element and replace only if another change is wanted. |
| Delete succeeded, reply lost | Report that the exact targeted element/version was already removed, with the recorded effect. A stale handle must not delete a newer version. |
| Preparation reply lost | Re-entry identifies the current revision and any relevant prepared/submitted handle; another preparation can inspect the current answer. It does not submit. |
| Confirmed submission succeeded, reply lost | The same handle returns the recorded seal/outcome without another submission. An already sealed answer supplies its actual sealer; it never prompts endless re-preparation. |
| Compaction or dead run | Re-enter the same audit, inspect current handles/bytes, then continue editing under existing limits. Do not re-add everything from memory. |

These are proposed signs and semantics, not qualification of the existing code.
The repeated-delete convenience and bounded re-entry require explicit adoption;
they should not silently change the current contract while this briefing is open.

## What the adapter can do without guessing intent

Distinguish redelivering the reply to the **same known invocation** from the
auditor issuing a **new call**. If a persisted invocation identity binds exact
arguments to a complete ledger outcome, the adapter can return that outcome.
It must not execute the action again just because the provider lost the reply.
An invocation with uncertain effects needs its own evidence reconciled; absence
of a readable outcome is not proof that nothing landed.

This is a possible implementation aid, not an adopted exactly-once service or a
reason to infer sameness from bytes. A fresh provider call usually has a different
identity. After compaction it cannot automatically be treated as a retry of an
earlier call with matching arguments. Reconstructing the same logical action then
needs either an explicit retained action reference or a changed authoring interface.
Do not claim hidden identifiers solve intent recovery when the caller has lost
the identity that would connect the two calls.

If the user wants a blind repeated add to be harmless, return to that choice
directly: design stable action identity before the first attempt, or make writes
target an existing element identity. Both are larger changes than better signs.
The recommendation for discussion is to keep new adds distinct and make recorded
effects easy to recognize, while only replaying outcomes whose identity is known.

## Errors and stopping

The manager's new contextual-error contract does not import a recovery console
into the auditor's form. Expected refusals say what was recorded, what did not
change and the next ordinary call. Internal partial files never appear as answer
members. Storage damage is not cured by calling add repeatedly: preserve the
evidence, report only established facts, and stop when the permitted answer can
no longer be supported. Custody diagnostics belong in Stewart's operating account,
not fabricated auditor conclusions or mandatory answer fields.

No retry or re-entry opens a second investigation, revives a closed reference,
changes the material world, resets limits or attributes a manager seal to the
auditor. A stopped auditor has no responsibility to repair the archive.

## Evidence needed after a decision

Use a scripted auditor and independent ledger/byte witnesses. Distinguish a kill
before a complete edit record from a lost reply after it; force actual compaction
and dead-run continuation; exercise repeated add with both intentional duplicates
and lost replies; repeat replace/delete across later edits; repeat confirmed submit
before and after close; damage records separately from genuine absence. Exercise
answers and question/index views larger than one reply, with useful content on
the last page and an edit between pages. All checks concern exact membership,
bytes, identities, attribution and usable next calls, not agreement with an answer.

Firing controls must expose a dropped element, a duplicate hidden by content
deduplication, a stale overwrite, a second seal and unmarked truncation. Invariance
cases include deliberate equal-byte elements, a run without compaction and
re-delivery of a known completed invocation. Successful configuration of these
tests is not evidence that the actual adapter or model can use the interface.

## Source account

The current contract and router at `a90ea31` specify ledger truth, new records for
auditor retries, exact submission handles and an unbounded-looking re-entry reply:
[CONTRACTS](../../CONTRACTS.md), [ROUTER](../linux-mvp-01/ROUTER.md), and C3/C4 of
[END-TO-END](../linux-mvp-01/END-TO-END.md). Their historical basis is turn 19 of
the closed [conversation](../linux-mvp-01/CONVERSATION.md), treated as past evidence.

The earlier [auditor case inventory](../custody-delivery-01/AUDITOR-CASES.md)
identifies repeated additions after compaction, stale targets and generic signs;
many rows predate the ledger decision. The bounded
[prototype report](../submission-design-01/RESULT.md) and its
[protocol description](../submission-design-01/prototype/attempt-01/README.md)
show that interruption and exact-identity recovery mechanisms were studied, but
its request-key and resolve/resume/cancel interface is not the adopted auditor
workflow. Its reported local results are inherited evidence, not rerun here and
not qualification of the proposed interface or Linux/model operation.
