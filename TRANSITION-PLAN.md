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
changes, not executed runtime qualification. The separate
[retry/re-entry briefing](coordination/auditor-reentry-01/BRIEFING.md) is the next
discussion; question typing and answer presentation come last. The stage sequence
remains planning, not a runtime commission or an old checklist to replay.

## What is decided, and where

- **The mission**, **successor interfaces decided 2026-10-28**, **successor
  manager readback, status and close**, **successor manager preparation and
  acceptance**, **successor custody, retention and manager access**, and
  **successor initial materials and preparation inspection** are in CONTRACTS.
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
- **Auditor retry/re-entry.** The briefing is a proposal, not a contract change:
  exact element/version/receipt visibility, bounded re-entry and known-invocation
  outcome replay must be discussed before changing C3/C4 or the authoring tools.
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
| **T0 — Settle the record** | Apply the decided manager contracts to successor guidance and preserve frozen/historical records. The old eight-question disposition review is historical input: removal, holds, custodian and live manager access are now settled for the first release; stopping is engineering/qualification, forms/rendering are the final discussion, and live Python undertakings are a retirement gate. Complete remaining contract disposition and successor development guidance without making the user review routine row rewrites; preserve the reasons and actual obligations. Dispose of the older plans before deleting them. | Coherent current contracts and guidance, with legacy behavior clearly scoped and no runtime dependency on plans. Manager-policy reconciliation is complete; remaining broader transition work is explicit. | Auditor retry/re-entry, then question typing/answer presentation; any genuine conflict with an existing protected undertaking. |
| **T1 — The apparatus** | Build image (pinned Rust toolchain, musl targets for x86_64 and aarch64, a short vendored crate list for JSON, hashing, regular expressions and HTTPS over a pure-Rust TLS stack), test image (driver and fake provider), experiment image. Reproducible offline release builds. On the development Mac: a native aarch64 container and an emulated x86_64 one through Apple's `container`. Restate the evidence retention rules for runs in the apparatus. | A trivial binary built and tested in both images on both architectures, with image and binary digests recorded. | Crate selection is the coordinator's; record it. |
| **T2 — The foundation and the manager's front door** | One `stewart` binary: stable reference through preparation and one acceptance; designated non-removing archive; write-once records; strict control JSON; contextual errors; `question.md`/`materials/` scaffold; literal bounded UTF-8 text intake and paged reader; `help`, `new`, manager `prepare` with readable pinned arrangement, explicit confirmed `commission`, `receipt REF` with `--read ITEM`, and `status`. Prepared names/bytes/settings bind copying and final source checks; failed attempts remain distinct, and interrupted acceptance is reconciled before fresh capture. The existing `successor/` code seeds safe reads, control JSON and verified copy, not its old bundle workflow. | C2, C6, C9, C11, C15 and applicable C16-C19 cases pass in the test image, with timings and independent witnesses. | Manager foundation policy settled; actual release forms depend on T3, and test fixtures must not silently choose them. |
| **T3 — The ledger and the protocol** | The auditor's tool: re-entry; `list`, `read`, `search`; `add`, `replace`, `delete`; `prepare` and `submit` with dry run by default; signs; ledger truth. Resolve retry and re-entry usability in their own briefing before fixing that interface. Form tools, citations and stopping instructions follow the separate question-typing/coupling discussion; neither `survey` first nor `claim-check` is assumed. The protocol's command-line face serves the person adapter later. | C3, C4, the subsequently decided C7 cases and the protocol budgets in C9 pass. | Auditor retry/re-entry and the broader question-typing/coupling choices, including the answer-form and stopping-rule choices above. |
| **T4 — The model adapter and the run** | The thin loop over the Messages API; the arrangement as the tool list; compaction and reasoning as settings; limits across runs; `run` from the reference alone, foreground, key from the environment, refusing when running or ended; the dead run continued; bounded provider retry; the record (conversation, access log, run summary) in the home. | C1, C12, C13 and C4 end to end against the fake provider. | None expected; the nudges (reminder, warning) are decided in T3. |
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

- Auditor retry and re-entry: the separate briefing at
  `coordination/auditor-reentry-01/BRIEFING.md` distinguishes new calls from known
  outcome replay and proposes bounded, identifiable re-entry. Discuss next; no
  authoring semantics or C3/C4 expectations changed in the manager settlement.
- Question typing/coupling: discuss last, after retry/re-entry, and discuss the arrangement itself rather than treating
  the illustrative claim-check slots as a settled design to repair.
- The person adapter and transport (post-MVP; T9).
- The rule for adding form opinions to the library (T9).
- Whether read-only investigation is enough (T9).
- Manager contract implementation/qualification: C17-C19 own failure, retention
  and material evidence still owed. These are engineering tasks under the decided
  scope, not open policy choices or authority to start a runtime stage.
- Replacement development guidance for the successor (T0; the user's).
- The two points raised on the mission's wording in conversation turn 18 and not
  answered: "separate context" against the only-Stewart's-tools decision, and
  the dropped sentence that material is files and provenance is the manager's
  business. Both are resolved by CONTRACTS' decided section; the mission's
  wording stays the user's.
