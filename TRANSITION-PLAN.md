# Transition plan: from the frozen Python Stewart to the router

Current account, 2026-10-28, written by the coordinator at the end of the design
review. The user decided the design; [CONTRACTS.md](CONTRACTS.md) records it.
This plan organizes the authorized transition into a sequence, carries the open
questions with the work they belong to, and gives the earlier program an
explicit disposition. Preparing a stage here does not commission it; each
stage's execution is commissioned by the user when its turn comes. Update this
account as work changes; delete the plan when the transition is complete or
abandoned, after moving enduring contracts and explanations into documentation
and tests.

Current interface work, 2026-10-28: the user delegated resolution of manager
recall and status/close after reviewing the two past design sessions as history.
CONTRACTS' "Successor manager readback, status and close" now supplies that
design; ROUTER and END-TO-END are synchronized. It adds `receipt REF` and exact
commission readback, distinct status facts, and delivery continuation through
close. This completes the design fixes, not a runtime stage. Preview's scope,
auditor retry/re-entry, and question typing/coupling each require their own
discussion. The stage sequence below remains planning, not current direction to
begin T0 or implementation.

## What is decided, and where

- **The mission**, **successor interfaces decided 2026-10-28**, and **successor
  manager readback, status and close** are in CONTRACTS.
- **The settled design sketch** is
  [coordination/linux-mvp-01/ROUTER.md](coordination/linux-mvp-01/ROUTER.md)
  and **the settled test design** is
  [END-TO-END.md](coordination/linux-mvp-01/END-TO-END.md). Where they and
  CONTRACTS differ, CONTRACTS decides; where CONTRACTS is silent, they are the
  coordinator's proposal.
- **The user's directions**, condensed: the auditor has only Stewart's tools and
  Stewart runs it; Linux only; no Python reference baseline; no Git, with history
  arriving as exported files; the manager owns the question's wording and the
  material's selection; one re-entry call makes compaction harmless; "fast" means
  the app's responsiveness; build, test and experiment in containers, one static
  binary ships; a real-model conformance gate; the auditor's tool is a form and a
  ledger; the inquiry is the manager's unit and receipt, status and close are the
  only operations after the question; the run is a separate command that a
  harness may escalate to a person; a Markdown problem file with advisory checks;
  the return is only what the auditor submitted; a dead run continues as the
  same undertaking. The verbatim prompts are in the conversation record.

## What is still the coordinator's proposal

These are in ROUTER.md and not separately decided. Each is decided when the work
reaches it, and the consequential ones go to the user:

- **Answer forms and stopping rules.** Typed slots exposed as tools versus
  free-form elements rendered by a template; stopping rules stated to the auditor
  only versus checked at submit (recommendation: stated only); the prior shown or
  sealed, per form or per problem; mechanical citation checking versus
  report-only versus none; the reminder after an unsubmitted stop and the
  warning near a limit. The coupling library is provisional; the user requires
  a separate discussion of question typing/coupling itself, not just repairs to
  `claim-check`. `survey` and `claim-check` are proposals, not assumed instruments.
  One test for a slot: the auditor must be able to fill it from where it stands,
  with the evidence attached.
- **Never deleting.** ROUTER says Stewart deletes nothing and close is a record.
  Followed from the auditor having no workspace; not confirmed by the user.
- **Mechanics:** the access log; the home's location and layout; command
  spellings except the now-specified receipt/readback and delivery-redirection
  routes; the response-budget numbers; default model, effort and limits; size
  limits; the default exclude list; WSL `/mnt/` handling; the person adapter's
  presentation and transport.

## The sequence

Dependency order, not a calendar. Each stage names the result required before
dependent work and the decisions that return to the user. Side work that can
start at any time is listed after the stages.

| Stage | Work | Required result | Decisions for the user |
| --- | --- | --- | --- |
| **T0 — Settle the record** | The CONTRACTS disposition review (`coordination/contracts-disposition-01/RETURN.md`) is integrated as the Proposed "Transition status of the earlier contracts" section of CONTRACTS, which lists eight decisions the user has not made; bring them to the user first, five dispositions hang on whether Stewart ever removes bytes. On confirmation, restate what carries, retire what depended on Git, the Python baseline, the checkout or removal at close, and keep retired text's reasoning where it explains a decision. Confirm the earlier program's disposition below item by item, then delete DEVELOPMENT-PLAN.md. Move VISION-PLAN's remaining guidance into coordination guidance and retire it. Draft replacement development guidance for the successor, since the root AGENTS.md custody rules encode the old design. | CONTRACTS reads as one document under the mission; no plan is routed to from durable guidance; workers dispatched for T1 onward inherit rules for the Stewart being built. | Confirm the disposition of each retired contract. AGENTS.md is the user's: adopt or amend the drafted replacement. |
| **T1 — The apparatus** | Build image (pinned Rust toolchain, musl targets for x86_64 and aarch64, a short vendored crate list for JSON, hashing, regular expressions and HTTPS over a pure-Rust TLS stack), test image (driver and fake provider), experiment image. Reproducible offline release builds. On the development Mac: a native aarch64 container and an emulated x86_64 one through Apple's `container`. Restate the evidence retention rules for runs in the apparatus. | A trivial binary built and tested in both images on both architectures, with image and binary digests recorded. | Crate selection is the coordinator's; record it. |
| **T2 — The foundation and the manager's front door** | One `stewart` binary: audit identity and reference; the home; write-once records; strict control JSON; signs with stable reasons; the Markdown problem file; material intake with names, labels, collisions refused, default excludes listed and includable, links and special files listed as not copied, limits; `help`, `new`, `commission`, `receipt REF` with `--read ITEM`, and `status` by reference and inquiry. Receipt readback recovers the fixed commission; status distinguishes run, seal, delivery and closure. Preview follows its separate scope decision. The existing `successor/` code seeds this: descriptor-safe reads, control JSON and verified copy carry over; bundle commands are superseded by commission and the receipt. | C2, C6, C9, the decided parts of C11, C15 and the applicable C16 cases pass in the test image, with timings. | Preview's scope and material presentation before those parts are built; independent receipt/status work may proceed when commissioned. |
| **T3 — The ledger and the protocol** | The auditor's tool: re-entry; `list`, `read`, `search`; `add`, `replace`, `delete`; `prepare` and `submit` with dry run by default; signs; ledger truth. Resolve retry and re-entry usability in their own briefing before fixing that interface. Form tools, citations and stopping instructions follow the separate question-typing/coupling discussion; neither `survey` first nor `claim-check` is assumed. The protocol's command-line face serves the person adapter later. | C3, C4, the subsequently decided C7 cases and the protocol budgets in C9 pass. | Auditor retry/re-entry and the broader question-typing/coupling choices, including the answer-form and stopping-rule choices above. |
| **T4 — The model adapter and the run** | The thin loop over the Messages API; the arrangement as the tool list; compaction and reasoning as settings; limits across runs; `run` from the reference alone, foreground, key from the environment, refusing when running or ended; the dead run continued; bounded provider retry; the record (conversation, access log, run summary) in the home. | C1, C12, C13 and C4 end to end against the fake provider. | None expected; the nudges (reminder, warning) are decided in T3. |
| **T5 — Delivery and close** | Delivery of a sealed answer: manifest and elements, read back and verified. `close` from any state: stop with evidence, preserve an auditor seal or seal as the manager's, continue owed delivery including `--destination DIR`, and record on the applicable placement confirmation. Recover confirmation after lost replies; retain partial copies and failures; name a missing member's undertaking when giving it up; keep unknown membership unfinished. | C5, C8, C6 through close and C16. The first end-to-end audit under the successor. | Whether close is a record only (never deleting); qualify the cross-process stopping mechanism before claiming completed close. |
| **T6 — The scripted tier and the WSL handoff** | The whole scripted tier on both architectures with every sabotage control firing; the handoff package (binary, driver, fake provider, environment capture) run natively on WSL2 by the user's friend; results archived and recorded. | A WSL2 run record with counts, timings, controls and environment. | The handoff's timing is the user's. |
| **T7 — The conformance gate** | The real-model tier of END-TO-END: fixed commissions, procedure checks only, forced compaction and a kill-and-continue run per model. | The release names its supported models and its cost. | Explicit, bounded permission and a budget for model-consuming runs. |
| **T8 — Retire the Python implementation** | Only after T5 and one pass of T7. Inventory the Python audit workspaces under `audits/`, close any live audit under Python, then remove the Python package, tests, checker, manual and DEVELOPMENT.md's Python instructions; rewrite the README for the successor; drop the Python status markers from CONTRACTS. | No period in which the project has no working audit tool. | Confirm retirement. |
| **T9 — Experiments** | Never a gate. Whether read-only investigation is enough; the person adapter and how work reaches a person; the rule for adding form opinions to the library on evidence from returns. | Each its own commission. | Each needs its own commission and, where a model is called, permission. |

**Side work from the start:** the successor's development guidance (T0); user
documentation, which is `help` plus a short guide for the WSL handoff; the
acceptance driver's skeleton, which grows with T2 through T5.

## Disposition of the earlier program

DEVELOPMENT-PLAN.md and its register were written for a design that assumed
Git-held material, a Python reference baseline and an auditor checkout. Its
items are disposed as follows; T0 confirms each one and then deletes the plan.

- **First-leg preparation** (PLAN-FIT, NEXT-LEG, AUDITOR-CASES, ORIENTATION-TRIAL
  and ANSWER-STRUCTURE under `coordination/custody-delivery-01/` and
  `coordination/submission-design-01/`): abandoned as programs. Their content on
  signs, re-entry, answer structure and the auditor-case table is input to T3.
- **The commission-input leg C** (`successor/`, `stewart-commission`): completed
  and recorded; its code seeds T2; its bundle interface is superseded by
  `commission` and the receipt.
- **Python-baseline comparisons and the unrun comparisons:** abandoned. There is
  no reference baseline; the Python tool is a frozen legacy tool until T8.
- **Git environment needs** (GIT-ENVIRONMENT-NEEDS.md): moot. Material is files.
- **The Linux check and WSL preparation:** carried into T1 and T6.
- **The inquiry and findings documents** (STATUS-INQUIRY, CUSTODY-AUDIT,
  CUSTODY-ADDITIONS, CUSTODIAL-CORE, KEYHOLE-OBLIGATIONS, RETURN-CUSTODY-DESIGN,
  SUCCESSOR-PREPARATION, MANAGER-CLOSE-FLOW): historical records, preserved,
  not active guidance. Where a CONTRACTS decision cites one, the citation stays.
- **Recovery-critical local evidence** (the corpus retention refs named in the
  coordinator account): preserved under their existing rules; unaffected.
- **The earlier coordination assignments** under `coordination/`: records of
  completed work, preserved; none is an open commission.

VISION-PLAN.md's working-relationship paragraphs stand until moved into the
coordination guidance (T0); its product paragraphs are overtaken as its top note
says.

## Evidence owed

- Each stage keeps its run records under the retention rules the apparatus
  restates in T1, with command, environment, counts, timings and every control
  that fired, kept with the work that cites them.
- The conformance tier states its cost per release.
- A clean result still needs a firing control, a case differing in the measured
  property and an invariance case; END-TO-END applies that rule to every claim.

## Open questions carried

- Manager intake and preview: the user has agreed to one ordinary submission
  folder, one acceptance boundary and one close action. Failed submission leaves
  preparation editable; acceptance fixes the captured commission. Close before
  launch leaves the manager's folder alone, accounts for incomplete intake and
  creates no auditor return. It need not force successful submission, and may
  itself remain unfinished with continuation through close. Actual custody loss
  remains distinct from failed intake. Reconcile CONTRACTS and the T2/T5 sketches
  with this direction once the copying interface is settled. The user favors
  cooperative source stability with before/after hashing as interference
  detection, not an atomic snapshot guarantee. Manager `prepare()` and
  `commission(handle, I_AM_FINISHED=true)` are now proposed, not decided. Define
  the handle, acknowledgment, checks and interrupted-acceptance behavior before
  choosing the remaining preview surface. Historical review distinguishes the
  preparation folder, each immutable attempt and the accepted commission; edits
  cannot rewrite old intent. Identity, retention and storage still need exact
  treatment; this creates no general manager-resource service or runtime commission.
- Auditor retry and re-entry: brief the lost-reply cases and large-answer
  presentation separately. No authoring semantics changed in the manager fixes.
- Question typing/coupling: discuss the arrangement itself rather than treating
  the illustrative claim-check slots as a settled design to repair.
- The person adapter and transport (post-MVP; T9).
- The rule for adding form opinions to the library (T9).
- Whether read-only investigation is enough (T9).
- Replacement development guidance for the successor (T0; the user's).
- The two points raised on the mission's wording in conversation turn 18 and not
  answered: "separate context" against the only-Stewart's-tools decision, and
  the dropped sentence that material is files and provenance is the manager's
  business. Both are resolved by CONTRACTS' decided section; the mission's
  wording stays the user's.
