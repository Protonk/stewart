# Transition plan: from the frozen Python Stewart to the router

Current account, updated 2026-10-29 after the manager interface discussion.
The user's decisions are recorded in [CONTRACTS.md](CONTRACTS.md).
This plan organizes the authorized transition into a sequence, carries the open
questions with the work they belong to, and gives the earlier program an
explicit disposition. Preparing a stage here does not commission it; each
stage's execution is commissioned by the user when its turn comes. Update this
account as work changes; delete the plan when the transition is complete or
abandoned, after moving enduring contracts and explanations into documentation
and tests.

Current interface work: the user delegated settlement of custody/retention, live
manager access and the initial material/inspection contract. CONTRACTS now records
the designated non-removing archive, narrow manager product access with ordinary
owner-readable files, literal `question.md`/`materials/` submission, exact UTF-8
text reader and limits, and preparation inspection without a separate preview.
ROUTER and END-TO-END are synchronized, including C17-C19. These are specification
changes, not executed runtime qualification. The user has now accepted the separate
retry/re-entry recommendation; CONTRACTS and C3/C4 record bounded orientation,
exact targets, distinct fresh adds and known-result replay. The user selected a
synthesis of [three question-design paths](coordination/question-types-01/PATHS.md):
C supplies the family library, B becomes a specific inquiry-framing family, and
A roughly describes open inquiry with optional evidence modules. CONTRACTS owns
the architecture and its limits. The user then accepted open inquiry, inquiry
framing and comparison as the initial library, to be specified through concrete
submission/tool/return examples including inadequate evidence, and a deterministic
Markdown rendering prepared for inspection and sealed with the structured answer.
The user accepted [auditor enforcement and prompting](coordination/question-types-01/ENFORCEMENT-BRIEFING.md):
mechanical structured-citation checks, nonblocking omissions and empty-answer
admission, with bounded factual prompts. CONTRACTS owns the decision. Concrete
family specimens remain unfinished; this is specification work under settled
policy. The stage sequence remains planning, not a runtime commission or an old
checklist to replay.

## What is decided, and where

- **The mission**, **successor interfaces decided 2026-10-28**, **successor
  manager readback, status and close**, **successor manager preparation and
  acceptance**, **successor custody, retention and manager access**, and
  **successor initial materials and preparation inspection** are in CONTRACTS.
  **Successor auditor retry and re-entry** records the subsequent agreement.
  **Successor question families and open inquiry** records the selected organizing
  model and initial library. **Successor readable answer rendering** records the
  accepted sealed presentation. **Successor auditor form enforcement and prompting**
  settles validation, incomplete submissions and notices. Concrete forms remain
  to be specified under those decisions.
  The later decisions supersede earlier workflows and proposals.
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
  operations after acceptance; the run is a separate command that a
  harness may escalate to a person; ordinary preparation and a Markdown question,
  a prepared selection and explicit acknowledgment before acceptance;
  the return is only what the auditor submitted; a dead run continues as the
  same undertaking. The verbatim prompts are in the conversation record.

## What is still the coordinator's proposal

These are in ROUTER.md and not separately decided. Each is decided when the work
reaches it, and the consequential ones go to the user:

- **Family definitions.** Specify the three accepted families through actual
  manager submissions, auditor tools and returns, including inadequate evidence.
  A locally checked draft packet and proposed small sub-agent review are in
  [question-examples-01](coordination/question-examples-01/BRIEFING.md). Work resumed
  after the user's network pause; no review agents have been launched. The concrete
  paper tools/schemas remain proposals, not silently adopted implementation inputs.
  Final names, concrete authoring tools/schemas, orientation and any optional
  module interactions remain. Apply the accepted mechanical checks, nonblocking
  omission observations, empty-answer route and bounded notices. No field or test
  may quietly introduce a substantive conclusion or completeness requirement.
  `survey` and `claim-check` are old proposals, not schemas to repair into the
  new library. The specimens should make the consequences of the settled policy
  reviewable; routine details are implementation work unless they expose a new
  substantive restriction.
- **Unselected extensions.** Hidden-prior machinery, a larger family catalogue
  and elaborate module composition are not first-build requirements. The
  coordinator recommends deferring them; any later addition needs its own
  concrete purpose and design. No such feature is authorized by an old sketch.
- **Mechanics:** the access log; archive record layout within the designated root; command
  spellings except the now-specified receipt/readback and delivery-redirection
  routes; response-budget numbers; default model, effort and run limits;
  WSL `/mnt/` handling and filesystem qualification; the person adapter's
  presentation and transport.

## The sequence

Dependency order, not a calendar. Each stage names the result required before
dependent work and the decisions that return to the user. Side work that can
start at any time is listed after the stages.

| Stage | Work | Required result | Decisions for the user |
| --- | --- | --- | --- |
| **T0 — Settle the record** | Apply decided manager and auditor contracts to successor guidance and preserve frozen/historical records. The old eight-question disposition review is historical input: removal, holds, custodian and live manager access are settled; stopping is engineering/qualification, enforcement and rendering are settled, with concrete family specimens still to specify, and live Python undertakings are a retirement gate. Complete remaining contract disposition and successor development guidance without requiring routine row approvals; preserve reasons and actual obligations. Dispose of older plans before deleting them. | Coherent current contracts and guidance, with legacy behavior clearly scoped and no runtime dependency on plans. | Any substantive restriction exposed by the concrete forms or genuine conflict with an existing protected undertaking. |
| **T1 — The apparatus** | Build image (pinned Rust toolchain, musl targets for x86_64 and aarch64, a short vendored crate list for JSON, hashing, regular expressions and HTTPS over a pure-Rust TLS stack), test image (driver and fake provider), experiment image. Reproducible offline release builds. On the development Mac: a native aarch64 container and an emulated x86_64 one through Apple's `container`. Restate the evidence retention rules for runs in the apparatus. | A trivial binary built and tested in both images on both architectures, with image and binary digests recorded. | Crate selection is the coordinator's; record it. |
| **T2 — The foundation and the manager's front door** | One `stewart` binary: stable reference through preparation and one acceptance; designated non-removing archive; write-once records; strict control JSON; contextual errors; `question.md`/`materials/` scaffold; literal bounded UTF-8 text intake and paged reader; `help`, `new`, manager `prepare` with readable pinned arrangement, explicit confirmed `commission`, `receipt REF` with `--read ITEM`, and `status`. Prepared names/bytes/settings bind copying and final source checks; failed attempts remain distinct, and interrupted acceptance is reconciled before fresh capture. The existing `successor/` code seeds safe reads, control JSON and verified copy, not its old bundle workflow. | C2, C6, C9, C11, C15 and applicable C16-C19 cases pass in the test image, with timings and independent witnesses. | Manager foundation policy settled; actual release forms depend on T3, and test fixtures must not silently choose them. |
| **T3 — The ledger and the protocol** | Implement bounded re-entry with element/version handles and recent completed receipts; material/answer reads; distinct fresh adds, target-safe replace/delete, preparation and confirmed submission; known-invocation result replay and contextual signs without an auditor recovery console. Qualify C3/C4 including pagination and lost replies. Implement the concrete family tools under the decided citation checks, nonblocking omissions, empty-answer admission and cumulative prompt allowances; neither `survey` nor `claim-check` is assumed. The protocol's command-line face serves the person adapter later. | C3, C4, C7 and protocol budgets in C9 pass. | Concrete family specimens; return only a new substantive restriction that existing policy does not decide. |
| **T4 — The model adapter and the run** | The thin loop over the Messages API; the arrangement as the tool list; compaction and reasoning as settings; limits across runs; `run` from the reference alone, foreground, key from the environment, refusing when running or ended; the dead run continued; bounded provider retry; the record (conversation, access log, run summary) in the home. | C1, C12, C13 and C4 end to end against the fake provider. | None expected; implement the decided reminder/notice policy without resetting allowances on continuation. |
| **T5 — Delivery and close** | Before launch, close ends preparation or the accepted commission, accounts for failed intake without forcing success, leaves the manager folder alone and creates no answer. Coordinate close with intake and launch. After launch, stop with evidence, preserve an auditor seal or seal as the manager's, continue owed delivery including `--destination DIR`, and record on applicable placement confirmation. Recover confirmation after lost replies; retain the archive including partials; name actual custody loss; keep unknown membership unfinished. No deletion service. | C5, C8, C6 through close and C16-C19. The first end-to-end audit under the successor. | No further retention policy choice; return a specific unmet promise if stopping/publication qualification cannot support the decided behavior. |
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

- Concrete question forms: open inquiry, inquiry framing and comparison are the
  initial library, with sealed deterministic Markdown rendering decided. Specify
  their asking/material/answer expectations and tools under the accepted enforcement
  policy. Missing expected coverage and empty selections can submit; structured
  citation mismatches refuse their entry mutation. Do not reopen that decision
  through a fixture or renderer.
  Optional modules must leave open inquiry usable with none. The preserved paths
  and illustrative claim-check slots do not supply an adopted schema.
- The person adapter and transport (post-MVP; T9).
- The rule for adding form opinions to the library (T9).
- Whether read-only investigation is enough (T9).
- Manager contract implementation/qualification: C17-C19 own failure, retention
  and material evidence still owed. These are engineering tasks under the decided
  scope, not open policy choices or authority to start a runtime stage.
- Replacement development guidance for the successor (T0; the user's).
- Build commission: intended endpoint and supported model/provider scope, with
  explicit bounded authorization and budget for real-model qualification. The
  current conversation settles design; it has not started implementation. WSL
  handoff timing and Python retirement retain their later decision points.
- The two points raised on the mission's wording in conversation turn 18 and not
  answered: "separate context" against the only-Stewart's-tools decision, and
  the dropped sentence that material is files and provenance is the manager's
  business. Both are resolved by CONTRACTS' decided section; the mission's
  wording stays the user's.
