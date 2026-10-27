# Recorded answer elements: candidate for discussion

2026-10-27. Accepted direction: the auditor-facing tool prevents invalid artifact
arrangements and records recoverable exact bytes. The user clarified a small
surface: add, replace using an existing element's handle, and delete. Strongly
seek atomic operations and avoid draft-status lifecycle stages. CONTRACTS owns
these directions; this document proposes their realization, not a runtime schema
or implementation commission.

The user has about 35 minutes from 20:09 UTC before sleeping the machine and is
continuing this session. Reserve roughly 20:39–20:44 UTC for a saved checkpoint.
The active program remains DEVELOPMENT-PLAN F3/W02 and its dependencies. No new
runtime work, audit, Claude launch, disposal or empirical trial is commissioned.

## One recorded answer, edited through the tool

Each successful edit changes an identified collection of recorded elements in
Stewart. The helper need not remain alive, and source paths need not survive.
There is no separately managed draft status or later promotion of those same
bytes into custody. Whether the answer is intellectually unfinished is the
participants' judgment; it does not make its recorded elements provisional storage.

The auditor-facing operation names below are illustrative. Access remains bounded
by the commission. A handle identifies an element; it does not independently grant
access or authority outside that audit.

| Operation | Proposed observable behavior |
| --- | --- |
| add(content, metadata) | Validate the proposed addition and combined collection constraints; record exact bytes and membership together; return an element handle and operation outcome. Equal content is not silently merged. |
| replace(handle, content, metadata) | Replace the named element atomically. Failure leaves the prior recorded element current. Recommend that the handle also identifies the expected revision, so an obsolete handle cannot overwrite an intervening change. Return a handle for the new revision. |
| delete(handle) | Atomically remove the named element from the current answer, subject to its recorded authority and any protected undertaking. Recommend refusing obsolete handles rather than deleting a later replacement. Physical reclamation is specified separately below. |
| inspect/read | Provide supported, verified access to the current recorded selection and its bytes. These reads grant no manager access to live authoring material. |

The primary answer text should use the same storage/mutation guarantees as its
supporting artifacts. Whether it is a distinguished element and how order/roles
are represented remain mechanism choices. Tool-assigned identities and descriptive
labels can be separate, avoiding unnecessary uniqueness constraints on prose.
Structured references must remain unambiguous; ordinary citations do not authorize
extra reads or oblige Stewart to judge the argument.

## Accepted ending direction: prepare a handle, then explicitly submit

The user proposed a preparation function that generates a manifest from the
recorded answer/artifacts, followed by submission with only the resulting handle
and an explicit `submit=true` argument. The default submission call is a dry run.
They also asked whether Rust could require preparation to occur as a submission
argument. Root recommends requiring the result of preparation, while allowing
preparation on its own so the auditor can inspect it. The user accepted this end-editing design. CONTRACTS now owns the behavioral
boundary; storage, handle mechanism and syntax remain unimplemented and unqualified.

Illustrative tool-facing shape, not literal Rust default-argument syntax:

```
p = prepare()
submit(p.handle)                 # dry run
submit(p.handle, submit=true)    # explicit actual submission
```

The tool instance is bound to an explicit audit. Accepted behavioral direction,
with implementation deductions identified where applicable:

- `prepare` verifies the recorded selection and produces an inspectable manifest
  plus an opaque issued handle. Bind the audit/commission, exact collection
  revision, ordered element identities/versions, metadata and content identities.
  A digest alone neither proves issuance nor substitutes for selection identity.
- Preparing does not end editing or move content into another custody class.
  There is no persistent prepared mode. Any successful edit makes earlier
  preparation handles stale, including an edit that restores equal bytes in a
  different recorded revision. The auditor can inspect and prepare again.
- The handle is required. Default/false is a dry run that checks the same
  preconditions without sealing the answer or publishing a submission. Accept
  only explicit true for the effectful form. Do not infer an audit or preparation
  by recency or silently repair a stale handle.
- Actual submission checks that the handle was issued for this audit and current
  exact selection. Revalidate the held content and bind the final check to the
  publication under the mutation serialization rule. A racing edit and submission
  cannot both succeed against incompatible versions.
- Success atomically fixes the selected result and ends further add/replace/delete
  authority for that answer. It does not itself prove stopped processes, manager
  delivery or safe environment removal. Those obligations remain separately owned.
- Use the issued handle to locate the same attempted submission after a lost reply.
  Repeating the identical confirmed call returns its recorded outcome, without a
  second submission. Uncertain effects use supported same-operation resolution;
  a damaged receipt is not treated as absence or permission to submit again.

Inside a Rust library, a public prepared-value type with private fields and a
controlled constructor can require safe callers to obtain it through preparation.
Across separate tool processes, runtime validation of the issued handle carries
that relationship; an in-memory type does not enforce persisted finality or
authenticate serialized input. Do not require call-stack detection or passing
the preparation function itself. The exact persistent issuance/validation mechanism
depends on the chosen storage/access arrangement and remains for qualification.

This direction supplies a deliberate end-editing action without restoring the
withdrawn draft-to-custody content transfer. No callable API is selected merely
by using function notation in the discussion.

## Atomicity target and candidate mechanism

For a supported reader, a mutation takes effect all at once: the previous complete
collection or the new complete collection is visible, never a partially replaced
artifact or membership entry with missing required bytes. Success additionally
requires the new bytes and their binding to be recorded independently of the
helper's lifetime. Exact filesystem/durability assumptions need qualification.

Candidate implementation within existing receipt rules:

1. Check authority, current handle and known bounds before copying content. Bind a
   caller-known request identity and planned effects before effectful work where
   required by the request contract. Do not infer intent by recency or payload hash.
2. Assemble the candidate under internal exclusive names, compute identities and
   validate the exact held bytes, metadata and combined collection constraints.
   This temporary mechanical state is not an authoring stage or readable result.
3. Recheck the expected current state under the serialization mechanism, then
   publish one complete exclusive commit record selecting the new state. Keep
   historical receipts unchanged. The precise lock/publication/read protocol is
   an implementation decision, not established by this sketch.
4. Complete required synchronization before acknowledging success. A crash or lost
   reply is resolved from the same operation identity and verified records. Never
   turn an uncertain outcome into a definite no-change refusal.

Replacing an element does not mean overwriting its old receipt. Immutable records
can describe a changing current answer without exposing a history-management
workflow. The existing C implementation provides a local example of exclusive
publication after staged bytes, not qualification of multi-element edits or of a
new storage protocol. No runtime behavior has been tested in this discussion.

## Failures the auditor can recover from

| Observed outcome | Proposed response and supported continuation |
| --- | --- |
| Definite precondition refusal | Stable reason, offending handle/field/limit, and explicit no-change statement. The auditor can correct that input and perform a new operation. |
| Recorded success | Exact operation/element identity and observed recorded result. A lost reply does not create a new addition or require reconstructing source content. |
| Interrupted or uncertain operation | Retained request reference, observed effects/diagnostics and a supported same-operation resolution. Completion may adopt only its planned effects; no private-state editing or blind repetition. |

These are operation outcomes, not persistent draft-status stages. Early refusal
reduces avoidable effects, but storage failure after effects still needs its
accurate account. Rejected edits leave the previous current answer intact. The
raw-capture/failure-evidence rules apply within the chosen operation boundary;
this design does not silently erase failed staging evidence.

## Open choices that matter for a bounded implementation

- Handle semantics: recommend an opaque audit/element/revision binding, with
  explicit stale-handle refusal and supported inspection of current identity.
- Replacement/delete lifetime: decide when obsolete payloads can be reclaimed.
  The user wants replacement/deletion of recorded elements; that does not require
  an undo service or indefinite history. It also cannot rewrite receipts, release
  holds or erase unfinished-operation evidence. Identify exact retained subjects
  and deletion authority before physical reclamation. Prefer no new user workflow.
- Audit ending and delivery: realize the accepted prepare-issued handle and explicit-submit
  boundary above, then specify the receiving endpoint and delivery responsibility.
  Ending, delivery and safe environment retirement remain distinct duties.
- Early close: use the current recorded answer as identified obtainable material,
  while accounting for an operation in its narrow mechanical window and existing
  obligations over material outside the recorded selection. No general scratch
  preservation duty has been removed.
- Access/storage/manual handback: name the concrete receiving and reader routes
  before implementation. Apply the same constraints to every supported entry;
  do not assume a privileged live service or qualification from client validation.

## Proposed qualification for the selected scope

No new tests or experiments have run. A later bounded implementation brief should
include firing, measured-difference and invariance cases for:

- Successful addition recoverable by a fresh helper after source change/loss;
  changed selected bytes change identity, while unrelated source changes do not.
- Rejected conflict/bounds operation leaving the previous collection unchanged.
- Successful replacement and deletion versus obsolete-handle refusal; unaffected
  elements keep their identities and bytes.
- Interruption before publication, around publication and after commit with lost
  reply: each reader sees a complete collection, and supported resolution finds
  the same operation's effects without duplicate additions.
- An invalid direct input through another supported entry point; authoritative
  enforcement cannot depend only on a preflight helper's assertion.
- Dry-run invariance, explicit true submission, issued versus fabricated/cross-audit
  handles, stale preparations, concurrent edit/submission and a successful submission
  whose reply is lost. Preparation may not silently pin an obsolete answer for
  submission after an intervening edit.
- Failure or a hold blocking physical reclamation without concealing its effects,
  and inspection of the authorized current collection under that condition.

Use an independent witness outside any disposal through review. Prototype
construction evidence does not establish actual custody/access/removal/platform
qualification. The normal artifact interface and its failures must remain useful
to the auditor without a manager-operated authoring workflow.

## Immediate next step and continuity

The prepare-issued handle, default dry run and explicit-submit direction is
accepted. The pre-sleep failure walkthrough and next-work brief are in
FAILURE-WALKTHROUGH.md and NEXT-WORK.md. Manager-side design is deferred. Prepare a bounded
implementation or disposable prototype assignment only after naming the remaining
promises and dependencies. Root owns this candidate and shared integration; no
worker is active. Save decisions and the exact resume point before sleep.

The preceding draft-oriented candidate was withdrawn after the user's
clarification and is preserved in
`.scratch/coordinator-intake-run-012/design-before-atomic-elements.md`.
