# Stewart: design and vision

Stewart makes a bounded inquiry easy to commission and keeps its boundaries
honest. The manager supplies a question in their own words, selected material,
an answer family and limits. An auditor works inside that arrangement. Stewart
keeps the records and returns the answer faithfully, without judging it.

The manager should need to care about the question, the materials, whether an
auditor has been launched and whether its answer has returned. One submission
folder, one acceptance boundary and one close action carry the machinery behind
those concerns. This is the current design; the design review is closed.
[CONTRACTS.md](CONTRACTS.md) supplies its binding details. No conversation,
retired proposal or earlier implementation is needed to reconstruct it.

## Responsibilities

| Party | Owns |
| --- | --- |
| Manager | Question wording, material selection, family, limits, destination and judgment of the answer. |
| Auditor | Investigation within the supplied world and the attributed answer, including uncertainty or inability. |
| Stewart | Faithful arrangement, exact custody, mechanical checks, controlled execution, recorded effects and verified delivery. |

Stewart has opinions about how questions meet evidence. Those opinions live in
versioned family guidance and authoring tools, visible before commissioning.
They cannot turn into a requirement to find a defect, choose a winner or agree
with a premise. Open inquiry is an ordinary route for broad requests.

## The manager's path

1. **Prepare ordinary files.** The submission folder contains `question.md`
   and `materials/`. The complete question file has settings and the question
   body. Material is literal recursive UTF-8 text, with published bounds and
   no hidden exclusions. Stewart may scaffold the folder; the manager owns it.
2. **Finish editing, then prepare.** Stewart inventories/hashes the selection
   and pins the instructions, tools and limits. The manager can inspect those
   records. Preparation accepts no commission and promises no preserved source.
3. **Commission the prepared handle with explicit affirmation.** Stewart
   copies, verifies and checks the source again. Acceptance fixes the separate
   captured commission. Failed acceptance leaves the folder editable; uncertain
   acceptance is reconciled before another capture. Matching scans detect
   cooperative interference, not an atomic source snapshot.
4. **Use the receipt's run line.** Commissioning is local. Run alone needs the
   provider and key. It works from the reference without the original session;
   a person or agent can invoke it. A dead placement can continue the same audit,
   with its ledger and cumulative limits intact.
5. **Receive the sealed answer, then close.** A sealed answer is copied to an
   exclusive destination and read back for verification. Status distinguishes
   run, seal, delivery and close. Close is available at every point; before
   launch it creates no auditor answer. After launch it ends authoring and, if
   needed, seals the recorded selection with manager attribution.

If close first makes the delivery, it presents a bound confirmation for a later
close call. A prior request cannot count as confirmation of a copy not yet
received. Failed stopping or custody work keeps close visibly unfinished with
its continuation. Known loss needs explicit surrender of the named undertaking;
unknown membership is never guessed empty. Close leaves the source folder and
all retained archive bytes alone.

## Three storage locations, different promises

| Location | Meaning |
| --- | --- |
| Preparation folder | Manager's editable working files; no evolving-byte preservation promise. |
| Designated archive | Accepted originals, arrangements, ledger, raw calls, conversations, attempts, partials, old payloads and all custody records. Persists through close. |
| Answer destination | Independent verified package: final manifest and its selected members, including the structured answer and stored Markdown rendering. |

References bind the archive and audit, not a current directory or newest record.
The locations cannot overlap through aliases or nesting. The manager maintains
storage availability and backup. Stewart provides no deletion service in this
release and no secrecy from the ordinary archive owner. Its supported live
manager surface remains receipt, status and close. Receipt readback recovers the
fixed commission, never a view of the live answer.

## The auditor's world

The model sees the question, captured-material tools, family instructions and
answer tools. It gets no shell, arbitrary file access, project execution, network
retrieval or delegated auditors. Supplied test reports remain supplied claims.
The family name and manager-only custody metadata do not enter this view.

The initial library is open inquiry, inquiry framing and comparison. Framing
explicitly commissions formation of a working question and useful investigation
within the same limits. Other families can question premises without silently
acquiring that task. [The form specification brief](docs/QUESTION-FORMS.md)
gives the concrete starting points and their limits.

The auditor records elements, replaces/deletes exact versions and prepares its
current answer. Preparation creates an immutable candidate and an inspectable,
deterministic Markdown rendering. Confirmed submit seals that exact selection.
The later seal names the actual actor; preparation cannot claim one in advance.
Missing sections and an empty answer are allowed. Mechanical citation checks
verify locators and explicit quotations, never support for a conclusion.

One bounded re-entry call restores recorded state and routes to all remaining
pages. It cannot restore unrecorded thoughts. Fresh equal-byte additions remain
distinct; a known completed invocation can have its result redelivered. Stale
handles never select newer work silently. One ordinary unsubmitted-stop reminder
and one near-limit notice fit inside the same cumulative budget.

## Implementation shape

One typed Rust operation core owns semantics and records. The manager CLI and
auditor adapter present role-specific views of its results. Small structured
replies name exact handles, observed/durable effects, uncertainty and supported
next calls. Manager JSON replies contain no progress chatter; exact-byte readback
has a separate raw stream contract. Strict versioned input decoding rejects
ambiguous or misspelled control data.

The archive layer provides exclusive records, verified descriptor reads, exact
byte identities and failure retention. The operation layer binds those records
to preparation, acceptance, edits, seals, delivery and close. The adapter alone
talks to the provider and enforces the pinned tool world and cumulative run
limits. Presentation never changes substantive records or manufactures success.

The first adapter is a thin model-provider loop. A person adapter is later work;
the answer format does not depend on model conversation metadata. Ship one static
Linux binary for x86_64 and aarch64. Linux containers hold the build and test
apparatus; WSL2 is qualified with the same shipped binary.

## What remains to build

The review settled behavior, not complete wire schemas or runtime mechanisms.
Specification must now enumerate calls, records, failure variants, exact bindings,
pagination and writer support; then implementation must qualify publication,
stopping and custody across interruption. These are engineering work under the
design, not another general design review. Any genuinely new authority or
substantive restriction still needs the user's decision.

[ACCEPTANCE.md](ACCEPTANCE.md) defines the executable evidence: the release
binary against an independently witnessed fake provider, followed by separately
authorized real-model procedural conformance. Paper examples and older prototypes
are useful inputs, not proof that the new service works. The frozen Python tool
and existing Rust intake slice remain available under their own documented scope
until the successor and the legacy-retirement gates are satisfied.
