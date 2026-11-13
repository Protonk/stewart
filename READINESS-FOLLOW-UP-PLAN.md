# Readiness follow-up

A read-only review challenged the release plan's entry assessment for
manager-interface work. The principal accepted its results. This plan owns what
follows from them, in four stages that run in this order.

| Stage | Work | The principal decides |
| --- | --- | --- |
| [1. Fixes now](#1-fixes-now) | Reconcile specification and behavior where they differ, cut the question documentation, correct the launchers, checkers and driver the later stages lean on, and correct service tests in place | Row 1 of 1.1 and any row verification turns into a promise change; K1 and the table in 1.2; whether to back up the review's files |
| [2. Live runs](#2-live-runs) | Ten bounded packets that settle what only a real model or the real harness can show | Approval of each frozen packet, with its budget, before it starts; for a packet whose prerequisite another plan owns, whether to build it now or hand the packet on |
| [3. Fixes and reassessment after the live runs](#3-fixes-and-reassessment-after-the-live-runs) | Act on each outcome, anchor test fixtures in real captures, re-rate what changed | Each specification change an outcome raises, the 16,000-token response cap among them; whether the decision to proceed stands |
| [4. Outflow to the plans that follow](#4-outflow-to-the-plans-that-follow) | Pass what is not fixed here, as notes, to the plans that follow this one | Nothing further |

**State: nothing has started.** Update this line and the task boxes in place.

A stage opens when the one before it is complete or each of its remaining items
has an explicit disposition. Nothing here authorizes a launch: every start of a
model or of `claude` needs the principal's explicit approval of that bounded
use. Implementation is left open where a task says so; the order of the stages
is not.

The acceptance driver is corrected only by an author who has not read
`service/src` or `service/tests`. That author is given
[Appendix A](#appendix-a-driver-findings) and the files part 1.3 names, not the
rest of this plan, which describes implemented behavior.

## 1. Fixes now

Everything here is wrong or ambiguous today whatever the manager-interface work
decides, needs no model launch and no bytes captured from a provider or harness,
and either changes no promise or corrects a divergence the principal can decide
from two texts. Detail is under `.tmp/readiness/`: finding `A<nn>-<k>` and batch
notes in `a/merged.json` and `a/A<nn>-<k>.refute.json`; `U<nnn>` in
`a/unreached-merged.json`; `X<n>` in `b/X<n>.refute.md`; `K<n>` in
`c/K<n>.refute.md`; `ED-<nnn>` in `c/editor.md`. Checks are rows of
[What to run for what you changed](development/DEVELOPMENT.md#what-to-run-for-what-you-changed),
named by their first column.

The parts run in this order:

- **1.1 first.** It settles which text is right: every later test, driver case
  and edit takes its expected value from the reconciled passage, and the
  principal's decisions take elapsed time.
- **1.2 next.** It changes the documents the driver author and the test
  correctors read.
- **1.3 before the live runs.** A corrected launcher needs its Linux rehearsal
  again before it is bound to a live packet, and the driver hand-off needs the
  texts of 1.1 and 1.2.
- **1.4 beside 1.3.** It waits only on 1.1, and nothing in stage 2 waits on it.

A change needing specification, service and driver work is split between two
agents; the driver's part is done from the specification alone (1.3b).

### 1.1 Reconciliations of specification against behavior

R: stating in INTERFACE or the runtime contract what the binary already does is
routine. P: changing a reason, outcome or ending a manager or auditor receives
goes to the principal with both texts. "Refuter": a refuter checked the
behavior.
"Once": one reviewer reported it; verify before editing.

| # | Specification | Behavior | Source | Standing | Decides |
| --- | --- | --- | --- | --- | --- |
| 1 | [INTERFACE 5.8](docs/INTERFACE.md#58-close) step 6 and the 5.6 derivation: a held lock with every `run_started` ended means another close; reply unfinished, `close_in_progress`. INTERFACE 6.8 has a run publish `run_ended` before it releases the lock, so the inference fails in that interval. | A close that found a placement open when it began keeps waiting, up to the 30 seconds, while the lock stays held after that placement records its ending, and proceeds when the lock is released; it replies `close_in_progress` at once only when it waited for no run. Status cannot wait and reports `close_in_progress` in the interval. No test in any tree reaches `close_in_progress`. | Batch 9 note 1; U216, U223, U224, U230 | Once, confirmed by reading while drafting; the unreached verdicts are refuter-checked | P: when close and status say `close_in_progress` |
| 2 | Runtime contract: "At tool publication, the runtime gate refuses `placement_stopped` if cancellation, stopping or the deadline won before the log link." INTERFACE reserves `record_failed` and cause `archive_write_failed` for an archive write that failed. | A confirmed submit cancelled after admission and before its seal is linked fails `record_failed`, leaves a diagnostic with that reason and ends the placement `interrupted (archive_write_failed)`; no archive write failed. The recording tools return the contract's refusal at the same point and the placement continues. The same diagnostic is written when Stewart's own stop or the deadline wins that race. No test cancels a confirmed submit. | X9 | Refuter | R for the refusal reason. P if the corrected placement ending differs from the recording tools' case: the contract names none |
| 3 | INTERFACE 5.1 and 5.6 require `summary` and fix no sentence per condition. | Status appends a condition sentence for nine conditions; sentences exist for `limit_reached`, `ended_unsubmitted` and `damaged` and no view shows them. | X1, element 1b; `b/stewart-messages.md`, preamble | Refuter | R: show or remove. Their wording is outflow (section 4) |
| 4 | INTERFACE 5.4 names no outcome for a preparation whose members no longer verify at commission; Appendix A gives `record_failed` as "An archive write failed". | Commission of a preparation altered after `prepare` fails `record_failed`, exit status 4, `acceptance: absent`, `attempt: none`. | Batch 3 note 3 | Once | R to name it in 5.4; P to change the reason |
| 5 | Appendix A: `receipt_record_failed` is "Writing the acceptance receipt failed"; 5.4 gives `acceptance_record_uncertain` when publishing `accepted` fails. No passage assigns a reason to a failure before the acceptance link. | A failure before the link, and a failed publication of `accepted`, are both reported `receipt_record_failed` with acceptance absent. | Batch 7 note 1 | Once | R if 5.4 can say which publication failures leave acceptance known absent; else P |
| 6 | 5.4: commission without `--i-am-finished` is refused "with no effects"; 1.4: every reply carries `effects`. | That refusal carries `effects`, and a sabotage control requires them. | Batch 7 note 2 | Once | R: wording |
| 7 | [INTERFACE 6.4](docs/INTERFACE.md#64-limits-reminder-and-notice): a notice is `not_sent` "when that request was never captured", `unknown` otherwise; 4.5: a cut-off request capture "was never sent". | A captured, cut-off planned request is reported `not_sent`. | Batch 14 note | Once | R: wording of 6.4 |
| 8 | INTERFACE 7.4: "Once retained superseded and deleted payloads reach 1 GiB" small edits draw on the reserve; the edit that reaches the cap is not placed. | The edit that reaches 1 GiB draws nothing from the reserve. | Batch 15 note | Once | R |
| 9 | No passage gives: the order of `retained` (1.3); `members` on a delivery record reconciled as `process_gone`; the operation text of a delivery verification cause; close's waiting line on stderr; the rule identifiers of strict-JSON refusals (1.2). | Tests pin each of these. | Batch 9 note 6; batch 14 note | Once | R: specify what a manager or checker depends on, loosen the rest |
| 10 | INTERFACE 6.1 and 6.6 give no limit on a response head, no rule for interim 1xx responses, folded headers or invalid content lengths, and no precedence between `HTTPS_PROXY` and `https_proxy`. | Each is decided in the binary and tested. | Batch 11 note | Once | R |
| 11 | [INTERFACE 2.3](docs/INTERFACE.md#23-handles) gives the check's rule and no complete worked example. | No test or driver check has an independent vector; A14-2 and the driver's handle check both lean on it. | Batch 16 note 1 | Once | R: add one worked example |
| 12 | INTERFACE 5.5 assigns a planted link to neither `item_unsupported` nor `item_unreadable`. | The driver accepts either. | Batch 17 note 5 | Once | R |
| 13 | 5.8's effects table gives `delivery` under `run_still_held` as "newest attempt's outcome, or `none`". | The driver also accepts `unknown` there, and `seal` `none` or `unknown` under two faults. | Batch 20 note 2 | Once | R if the driver is loose; P if the binary replies `unknown` |
| 14 | The runtime contract names no reason for refusing an unknown stopping observation or a credential option, and no cause for relay loss. | The driver accepts any refusal in those cases. | Batch 24 note | Once | R for the refusal reasons; the cause joins the stop causes in section 4 |
| 15 | The runtime contract pins MCP `2025-11-25`; JSON-RPC 2.0 gives an error response `id: null` when the request's id cannot be determined. | The driver's peer accepts an error response with no id and refuses a null id in every response. | Batch 25 note 2 | Once | R, driver author |
| 16 | DEVELOPMENT, "Current test evidence": keep the last qualified result "for each suite/platform ... if it failed". | The qualification record decides "failed" from the entry's outcome, not the platform's; no test covers the difference. | Batch 32 note | Once | R |

- [ ] Verify each "once" row against the passage and the binary. Rows 12 to 15
  are driver-side: the driver author verifies them from the specification.
- [ ] Put row 1, and every row verification turns into a P, to the principal.
- [ ] Amend the owning passage or the behavior, one owner per fact.
- [ ] Add a test reaching each corrected condition: for row 1 two overlapping
  closes after launch, asserted in close and status; for row 2 a cancelled
  confirmed submit. Driver cases for rows 1, 2 and 12 to 15 go to 1.3b.

- **Checks:** "`docs/INTERFACE.md` or `docs/QUESTION-FORMS.md`"; "Runtime
  schemas or pinned texts in `docs/claude-code/CONTRACT.md`"; "`service/src/`
  or `service/tests/`"; "`apparatus/qualified.py`" (row 16); the driver rows of
  1.3b.
- **Complete when:** every row is verified or withdrawn, each standing
  divergence has one text and matching behavior, rows 1 and 2 have a reaching
  test, and each P row is decided.

### 1.2 Documentation of questions

The editor's 156 items: 45 applied now, 3 answered by the K edits, 30 applied
after a check, 66 awaiting a decision, 7 help items in outflow, 5 kept.

| Applied now: restatements and second owners removed, no rule changed (45) | Items |
| --- | --- |
| CONTRACTS: Principles and scope; Question families and open inquiry; Readable answer rendering; Auditor form enforcement and prompting; The return and its delivery | ED-015; ED-027, 028, 035, 040, 049; ED-057, 058, 061, 062, 063; ED-064, 070, 074; ED-077 |
| QUESTION-FORMS | ED-078, 079, 087, 088, 089, 091, 092, 097, 098 |
| INTERFACE 3.2; INTERFACE 7 | ED-101, 104; ED-107, 108, 110, 113, 114, 116, 120 |
| Runtime contract; ACCEPTANCE C7 | ED-121, 122, 124, 128; ED-132 |
| `examples/questions/`; rendered help | ED-138, 140, 141, 143, 144, 147; ED-150 |

Three carry a condition. ED-078 leaves the scaffold's comment line alone: it is
product bytes. ED-122 moves a requirement into INTERFACE 3.2 only once the
distributed build's diagnostic is confirmed to name the value and `question/1`.
ED-150 changes help the binary prints, so the service row applies.

| K | Edit | Decides |
| --- | --- | --- |
| K1, stands (ED-002) | CONTRACTS "Mission" says orientation and stopping rules are "recorded in returns"; the return names only the family and renderer versions ("The return and its delivery", INTERFACE 8.2). One of the two changes. | Principal |
| K4 (ED-054) | CONTRACTS "The return and its delivery" and INTERFACE 8.2 point to "Returned question and answer" as the one place that says when the question becomes a member. | Routine |
| K7 | CONTRACTS "Versions and legacy obligations" and the `question/1` row of INTERFACE 1.1 point to the leaf-contract rule of "Run and continuation". | Routine |
| K8 | CONTRACTS on recorded citations and INTERFACE 5.3 point to INTERFACE 2.4: the public name is the path under `materials/`; the source name is `materials/<public name>`. | Routine |
| K6 (ED-099) | The `model` row of INTERFACE 3.2 says the scaffold's placeholder is refused (`setting_invalid`). | Routine |

- [ ] Apply the 45 and the K edits.
- [ ] Apply 25 rewrites that restate what an owner already fixes, each checked
  against that owner first: ED-026, 038, 048, 066, 067, 068, 069, 073, 086,
  093, 095, 096, 100, 102, 103, 105, 109, 118, 119, 125, 130, 137, 139, 142,
  146. One that states a new fact moves to the table below. ED-095 changes an
  example the driver pins; its driver copy goes to the driver author.
- [ ] Look up and state five missing facts: what `run` receives after the
  second unsubmitted stop (ED-072), the refusal for an over-long `read` source
  (ED-090), the members of a re-entry gap (ED-112), the runtime arrangement's
  `reading` member (ED-127), the form of `checked_at` (ED-129).
- [ ] Put the table below to the principal. Nothing in it is edited before its
  row is decided. Rows 1, 5, 6 and 7 settle only what the documents say
  meanwhile; the designs are manager-interface work (section 4).

| # | Decision | Items | Options the documents leave open |
| --- | --- | --- | --- |
| 1 | Material roles | ED-024, 036, 037, 134 | Delete the role sentences from CONTRACTS and C7 until roles are specified; or keep them marked decided and unimplemented, as "Returned question and answer" is |
| 2 | Evidence modules and hidden priors | ED-029, 052, 053, 135 | Delete, with the C7 sabotage control that INTERFACE Appendix C records as unable to exist; or one line in "Declined and deferred scope" |
| 3 | The two unimplemented families and a library of five | ED-039, 041, 042, 043, 047, 050 | Three families, the other two named once as unselected; or the five purposes as now, which the manager-interface plan says to preserve |
| 4 | The one list of answers every family leaves expressible | ED-008, 044, 045 | Which members the list has (its nine copies give three to five); whether `answer`, `needs-evidence` and `reframe` remain as names |
| 5 | Guidance to the manager by family | ED-023, 025, 051 | Delete the clauses no text backs; or leave them until such text exists |
| 6 | What a family consists of and what a version covers | ED-020, 021, 022, 034, 081 | Correct "Shared terms" now to what QUESTION-FORMS specifies per family; or leave all five statements for the registry work |
| 7 | The returned question's carrier | ED-055 | A package member, a manifest key, a block in `answer.md` or reply text: undecided here; only the K4 pointers are added |
| 8 | The rendering's reproducibility check | ED-060 | Name the operation that re-renders and compares; or delete the sentence |
| 9 | Sentences stating a limit or principle with no mechanism or defined term | ED-003, 007, 010, 012, 032, 033, 059, 076 | Delete each; or define its term |
| 10 | Copies that differ | ED-009, 030, 046 | Which copy's members stand: who admits a check that privileges an outcome; what guidance replacement leaves alone; what choosing a family grants |
| 11 | Names | ED-001, 004, 013, 016, 018, 031, 056, 065, 071, 080, 082, 083, 084, 085, 123, 154; ED-017, 111 | One name for each thing. ED-017 renames the manager's folder and ED-111 a reply member: each takes a new version under the versions rule, or stays |
| 12 | Rewrites that change product bytes, a bound, an acceptance case or a Mission or Principles sentence | ED-005, 011, 014, 094, 106, 115, 117, 133, 136, 145 | Each: adopt, or leave |

- **Checks:** "Prose or Markdown anywhere"; "`CONTRACTS.md`, `DESIGN.md` or
  `ACCEPTANCE.md`"; "`docs/INTERFACE.md` or `docs/QUESTION-FORMS.md`" (if the
  driver's self-test then fails on a moved table or pinned block, its copy is
  the driver author's); "Worked example materials" (ED-147); "Runtime schemas
  or pinned texts in `docs/claude-code/CONTRACT.md`"; "`service/src/` or
  `service/tests/`" (ED-150).
- **Complete when:** the 45 are applied and the checks pass; K1 is decided and
  the pointers are in; each checked rewrite and looked-up fact is applied or
  moved to the table; every table row is decided or deferred to the
  manager-interface plan.

### 1.3 Instruments the later stages depend on

**(a) Tests of the launchers and checkers a live run would use (21 findings).**
Each passes with its named check removed, accepts a refusal for any reason,
lacks the contrasting case, or imitates system behavior it could use directly.

| Findings | Subject | Needs |
| --- | --- | --- |
| A31-1, A31-2 | Sanity launcher, spending authority | A packet with account labels set and authority absent, the refusal asserted to name spending authority; and a pair differing only in recorded authority, one refused at this gate and one passing it |
| A31-9, A31-5 | Sanity launcher, hidden credential entry | A passing case in which entry without a warning returns the credential's bytes; the real entry path with no terminal in place of an imitation |
| A28-8 | C10 operations, wrong credential | Match the credential refusal, with the writer-state and binding preconditions shown to hold |
| A29-3, A29-1 | Probe child environment; bounded launcher's authentication output bound | An allowed inherited variable shown reaching the child, and a control that forwards the whole environment; padding that is valid JSON, so only the bound can stop it |
| A28-7, A31-3 | Export withholding, C10 and sanity (3 units) | Assert the withheld reason `evidence_incomplete` and the evidence state beside a complete root that exports; assert the exact refusal state for each altered field |
| A31-10, A31-6 | Sanity, observer failure and unreadable evidence | A succeeding observer beside the failing one; a real unreadable directory in place of a replaced directory walk |
| A28-5, A28-13, A28-2 | C10 approved packet, catalog (2 units), template identity | A filled packet in which only the digest differs; a catalog missing a family or variant and a specimen with a changed or unlisted file, both refused; an expected inventory written by hand |
| A29-4 | Bounded launcher, batch deadline | A paired run with a deadline that does not bind, shown to exceed the threshold |
| A30-1, A30-2 | Profile's failed installation record; pin (2 units) | Isolate the exit-status check from the inventory comparison and assert its message; assert each refusal's own message, and no output in the attestation case |
| A31-4 | Build markers, missing marker list | Remove only the list, with the binary present; assert stderr names the list |
| A32-1, A32-2, A32-3 | Qualification record: 13 runtime mutations, failed case, skipped control | For each mutation the expected kind and a message naming the mutated cause; break only the case counts with every exit record left at 0; a skipped firing control fails the self-test |

- [ ] Correct the 21 tests, and in the same files the weaknesses the notes of
  batches 28 to 31 record outside the finding classes.
- [ ] Tell the stage 2 owner which launchers changed: a changed launcher loses
  its rehearsal binding, and its Linux rehearsal is a user-scheduled container
  run that precedes any live packet.

- **Checks:** "`apparatus/c10/`"; "Python in `apparatus/sanity/`";
  "`apparatus/claude-code/`"; "`apparatus/check-build-markers.sh`,
  `apparatus/test_build_markers.py` or `apparatus/claude-code-markers.txt`";
  "`apparatus/qualified.py`".
- **Complete when:** each corrected test fails with its named check removed and
  passes with it restored, and stage 2 has the list of launchers to rehearse.

**(b) Driver corrections (41 findings).** They are made by an author who has not
read `service/src` or `service/tests` in that session.

- **Handed over:** `.tmp/readiness/a/batch-16.review.json` to
  `batch-27.review.json` and the `A16-*` to `A27-*` refutation files, unedited
  and copied to `.tmp/readiness/driver-handoff/`; the specifications as amended
  by 1.1 and 1.2; and a copy of [Appendix A](#appendix-a-driver-findings) with
  this part's bullets. The rest of this plan describes implemented behavior and
  is not handed over, nor is `merged.json` or any other result file.
- **Also the author's:** the weaknesses those batch files' notes record outside
  the finding classes (a control that compares two constants, a control that
  restates its pass condition, checks looser than INTERFACE 7.2 and 3.2), and
  the driver cases of 1.1.
- **Three questions from service-side findings:** does a case show that `new`
  on a folder no reference names reports no `folder_already_referenced` notice
  (A03-3), that a commission whose reply was written leaves no commission
  diagnostic in status (A07-3), and that a published preparation is not
  reported as an unpublished candidate (A07-4)?
- **Order of Appendix A:** most consequential first. Its first 28 rows are
  corrected now; the 13 from A24-1 down need bytes from a real provider,
  harness or operating system and wait on stage 3.

- [ ] Prepare the hand-off directory and brief the driver author.
- [ ] The author corrects A19-3 to A27-8 and answers the three questions.

- **Checks:** "Release driver and shared helpers in `apparatus/driver/`" and
  the rows for `claude_code.py`, `claude_code_surface.py`,
  `claude_code_observer.py`, `claude_code_peer.py` and
  `claude_code_service_witness.py`.
- **Complete when:** the 28 are corrected with a firing control each, the
  self-tests and case lists pass, the questions are answered, and the author's
  session opened nothing outside the hand-off.

### 1.4 Service tests corrected in place

34 findings in batches 1 to 15 need a tighter assertion, an independent expected
value or one added case, and no new fixture.

| Kind | Findings and what each needs |
| --- | --- |
| A skip tallied as a pass (4) | A01-1 (14 tests), A02-1 (19) and A11-1 (3) return and count as passed when a loopback listener cannot be bound: 36 tests. A06-2 does so when the scratch directory lies under a marked ancestor. Each fails, or the runner records it as skipped. |
| A refusal accepted for any reason (10) | Assert the specified reason, pointer or rule: A07-1 (which archive file was removed or rewritten), A07-2 (the positive consequence, not an inequality), A08-1 (a sabotage control counted as firing on any failure), A10-4 (malformed `usage.iterations`), A11-2 (chunked-body defects), A11-3 (TLS: unknown issuer, wrong name, not TLS), A12-5 (a profile with an unexpected member beside a valid one), A13-4 (non-canonical references), A14-4 (citation and record refusals), A14-5 (a taken run, request or attempt name). |
| Cases that do not differ in the property (2) | A04-4: a base64 input whose bytes are valid UTF-8 (INTERFACE 7.4). A08-2: an unlinked stage record with its own entry ID. |
| Expected values taken from the specification (11) | A03-1, A15-1 (`answer.json` text and citation key order by hand from QUESTION-FORMS); A04-1 (stored expected `answer.json` and `answer.md` derived from QUESTION-FORMS, origin recorded); A04-2 (family and audit ID from the question written and the reference); A06-1 (the scaffold against INTERFACE 3.2); A12-2 (launch surface and digest from the runtime contract's block); A12-3 (a control that cannot fail: change a real input or drop the claim); A12-4 (32 calls and 16 MiB from the runtime contract); A13-1 (per-family tool order from the QUESTION-FORMS table); A14-1 (the previous record's digest computed independently); A14-2 (the confirmation token from INTERFACE 2.3 and 8.4; uses row 11 of 1.1). |
| Controls added (7) | A11-5 (a case in which the key prints); A13-5 (a citation schema changed by one byte must fail); A13-6 (a scaffold with an effort line must fail); A15-3 (the Appendix C comparison over an altered copy); the service halves of A03-3, A07-3 and A07-4 (1.3b). |

- [ ] Correct the 34, and in the same files the weak assertions the notes of
  batches 3, 5, 6, 9, 13, 14 and 15 record outside the finding classes.

- **Not here:** A05-1 needs a rewritten fixture (section 4). The 23 fixture
  findings wait on stage 3: A01-2, A02-2, A02-3, A04-5, A04-8, A06-3, A10-5 to
  A10-10, A11-6 to A11-8, A12-7 to A12-12, A14-6, A15-2.
- **Checks:** "`service/src/` or `service/tests/`", all three configurations.
- **Complete when:** each corrected assertion is shown to fail on the defect
  its finding names, and a run with loopback denied reports 36 tests skipped or
  failed and none of them passed.

## 2. Live runs

This stage designs bounded packets and authorizes none. Each packet is frozen
first (inputs, binary, model, limits, stopping rules, replacement policy,
witnesses), shown to the principal with its bound, and started only on the
principal's explicit approval of that exact packet. Approval covers that packet
alone: no replacement, continuation or unused allowance carries over. These are
experiment-tier runs ([ACCEPTANCE](ACCEPTANCE.md#three-tiers)): they qualify no
model and add no C10 coverage; a native harness run is development evidence.

No rival track is created. Messages packets run through the
[small-commission apparatus](apparatus/c10/README.md) and its
[host queue](apparatus/c10/HOST-QUEUE.md); the apparatus work they lack belongs
to [the conformance plan](MESSAGES-API-CONFORMANCE-PLAN.md), sections 2 to 4.
Claude Code packets are the named uncertainties and smallest comparison set of
[the subscription track](development/MANAGER-INTERFACE-PLAN.md#additional-claude-code-subscription-testing),
which owns the surface packet, the real profile and the service procedure.

### Order and bounds

L0, M1 and M2 need nothing from the Claude Code track and nothing that does not
exist, so they come first. C1 is independent of them and may run beside them.
M3, M4 and C2 to C5 need apparatus that another plan owns (last column). For
each of those the principal chooses when the packet is frozen: build the
prerequisite now, under the owning plan's section, and run the packet here; or
hand the packet on with its design (section 4). Nothing in this plan builds
that apparatus on its own authority.

| Order | Packet | Route, model | Settles | Bound | Comparable earlier use | After | Does not exist yet (owner) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | L0 startup-stop words | none: retained synthetic evidence | X1, X12 | no launch | none | none | nothing |
| 2 | M1 prose turn end | Messages, `claude-haiku-5-5` | X2 | 4 placements; 48 turns, 640,000 input, 48,000 output | the six pilots: 5 to 8 turns, 28,365 to 71,095 input, 1,516 to 4,314 output each | stage 1 | nothing; templates and their Linux rehearsal are the existing procedure |
| 3 | M2 thinking-only response | Messages, `claude-haiku-5-5` | X3 | 4 placements and 1 conditional; each 60 turns, 64,000 output | 10 and 14 turns, 424,235 and 544,146 input, 26,211 and 30,922 output; USD 0.056 and 0.070 calculated | stage 1 | nothing, as M1 |
| 4 | C1 supplied surface | harness against the independent fixture, `claude-haiku-5-5` | X7, X12, captures | 3 authentication checks of 30 s, 3 sessions of 120 s, 450 s in all | probe 02: three sessions of three turns, 476 output tokens in sum | stage 1 | the principal's approval of the revalidated surface packet, then its independent review (subscription track) |
| 5 | M3 continued audit | Messages, `claude-haiku-5-5` | X2, X3 | 4 placements inside existing audits' remaining allowances (about 46 to 50 turns and 33,000 to 38,000 output each for arm a; a 12-turn audit for arm b) | none: no real audit has been continued | M2; arm b also M1 | bounded continuation, multi-placement export and review; for arm b a witnessed interruption point (conformance plan, section 2) |
| 6 | C2 first service placements | Claude Code, profile's model | X7, X8, X10 | 2 starts of 600 s, 2 authentication checks | the same commissions on Messages: 8 and 5 turns, 71,095 and 28,365 input | C1 | real profile; actual-service procedure and its offline rehearsal; specimens (subscription track) |
| 7 | C3 large page | Claude Code | X6 | 1 start of 600 s | long-page Messages audits: 5 and 13 turns | C2 | as C2 |
| 8 | C4 continued placement | Claude Code | X2, row CC-25 | 6 starts, 900 s of placement time in all | none on this route | C2 | as C2 |
| 9 | M4 compaction off Haiku | Messages, `claude-opus-5-5` or the model the principal names | X11 | 1 placement; 24 turns, 1,000,000 input, 24,000 output | trial 14 (Haiku): 13 turns, 531,740 input, 7,104 output | M1 | reviewer support for summary and reset requests; trigger observation (conformance plan, sections 3 and 4) |
| 10 | C5 turn endings | Claude Code | X3, X2, row CC-26 | 3 starts of 900 s | none; the probes' cap of 2,048 was not approached | C2, M1, M2 | as C2 |

In all, at most 14 Messages placements, 3 fixture sessions and 12 service
starts. Allowances and deadlines are not a dollar ceiling: each frozen packet
carries a dated cost estimate and the host queue's campaign budget.

### Rules for every packet

- **Binary.** The launcher refuses an unqualified binary, so a stage 1 service
  change needs its container acceptance run, and each template its Linux
  rehearsal, before a Messages packet. A stage 1 change to the launch surface
  or the tool definitions needs a freshly prepared C1 packet.
- **One audit per launch.** The launcher stops a batch after an audit without a
  checked auditor submission, which several arms intend. Launch each arm alone
  and read its return before the next.
- **Controls and view.** An arm in which the behavior does not appear is
  unexercised, never absence. After each placement keep the `run` reply with
  its summary and `status` in its default, `--details` and `--json` forms.
- **The cap.** M2 and C5 aim at the per-response output cap on purpose.
  Whether that falls under the rule that a deliberate usage-limit study needs
  its own commission is the principal's reading, stated in the approval.
- **Stopping.** Unknown stopping, an uncertain effect, a lost reply or a
  withheld export stops the packet; nothing restarts without fresh approval.
- **Counted in passing.** Refused calls and their reasons (X10), stop reasons
  and usage basis, extending the tallies of `.tmp/readiness/b/empirical.md`.

### L0: the words for a stop on a startup observation (X1, X12)

No launch is needed. The qualified synthetic acceptance run already holds the
replies:
`.scratch/acceptance-environment-observer-01/driver-<arch>/runtime-evidence/commands/`,
case `runtime-init-control`, `run` and `status`. Their summaries match, line for
line, the words the X1 and X12 refutations assembled from source.

- [ ] Record those replies as the observed words for X1 and X12.
- [ ] Optional, native, no Claude process: with the synthetic harness, arrange
  a profile whose `temporary_directory` lies inside project instruction ancestry
  ([CONTRACT](docs/claude-code/CONTRACT.md#arrangement-and-observation)) and
  confirm the same words and that no authentication check started. Differing
  case: the same profile outside that ancestry. By hand or by helper is open.

### Messages packets

All are open inquiry. Outside Stewart: the launcher's input witness, the host's
command streams and the delivered package. Requests and responses are Stewart's
own captures on the direct TLS route; that limit belongs to the conformance
plan, section 3. Interrupted audits are left open, not closed, until M3 is
decided.

| Packet | Commissioned, and why the behavior is likely | Observed | Firing, differing, invariance | To stage 3 |
| --- | --- | --- | --- | --- |
| M1 | Catalog `open-ordinary` materials, effort unset, proposal defaults (12 turns, 160,000 input, 12,000 output, 900 s). Arm A: the catalog question. Arm B: the same request worded as a chat message asking for a short direct reply. Arm C: the same request preceded by an invitation to ask about anything unclear. Arm D: wording B over `open-inadequate`. B and C set a manager's ordinary phrasing against the orientation's "no way to ask the manager anything" and "your answer is the entries you record". Exact wording is left to the packet. | Each stop reason; a reminder notice record and its `sent` value; the reminder as the next request's user message; the auditor's next response; the ending. | An arm where `end_turn` occurs; arm A, where none is expected (0 of 356) and no notice record may appear; D against B, same notice text and record. | D1. A wording that fires is reused by M3 arm b and C5. |
| M2 | The checklist question over both copies frozen in `.scratch/haiku-stress-01/templates/`, original limits (60 turns, 10,000,000 input, 64,000 output) on every arm. R1, R2: effort unset, the arrangement that stopped at the cap twice. E1, E2: `effort: low`, the one documented remedy a manager controls. G, only if neither R arm reproduces: effort unset with the study build's family guidance supplied as `guidance`, since the original ran on an unqualified study build. | Per response: output tokens, thinking tokens, stop reason; whether anything is recorded; the ending. | R1 and R2; E1 and E2, where only effort changes; the second copy at each effort. | D3. The approval must say that reaching the per-response cap is the purpose. |
| M3 | Arm a: `run` again, same reference and writer, on each M2 audit left `interrupted (max_tokens)`. Arm b, only if M1 found a wording that fires: one audit with it, interrupted after its reminder notice record is observed and before submission, then `run`. Arm b is the only honest way to a continued placement whose audit has spent its reminder. | The continuation notice in the first request; the first response (a re-entry call, another call or prose); any notice record; the ending; whether submission is reached in the remaining allowance. Arm b: whether authoring ends with no reminder delivered in that conversation (row M-31), and the words shown. | Arm b; arm a, reminder unused; the two arm a audits. | D2, D3. An arm whose prerequisite or firing wording does not arrive goes to the conformance plan as a note. |
| M4 | The `page-long` template frozen in `.scratch/haiku-recovery-followups-01`, limits and effort as trial 14: the arrangement in which Haiku passed 150,000 context tokens by its fourth request. | The summary request; the response's stop reason, blocks and `usage.iterations` element types; the signed block reused unchanged; the ending. | Altered copies of the captured summary (changed signed block, missing compaction iteration, added block) must fail the reviewer; requests below the trigger ask for no summary; the retained Haiku capture (E-58) shows the same shape. | D4. Not reaching the trigger is unexercised. A sample of two cannot show that no summary ever departs from the shape. |

### Claude Code packets

All use open inquiry and the profile's model. C1's bytes are held by the
independent observer and fixture sockets. In C2 to C5, input copies,
process-group absence, the command streams and the complete-package witness are
outside Stewart; the harness stream and MCP traffic are Stewart's own captures.
Whether the service procedure can add an independent stream witness is open.

| Packet | Commissioned, and why the behavior is likely | Observed | Firing, differing, invariance | To stage 3 |
| --- | --- | --- | --- | --- |
| C1 | The draft at `.scratch/claude-code-surface-proposal-01`, revalidated or prepared afresh: positive, closed-gate and invariance sessions with the full family tool inventory and Stewart's actual relay and hook helpers. | Beyond its required comparisons: tool and model names on assistant events; the final report of a session that ends by itself; rate-limit event members; duration and exit of each authentication check. A logged-out check exits 1 in 0.13 s (retained, `.scratch/claude-code-probe-01/auth-empty/`), so that X12 question needs no run. | Its own positive, denial and invariance cases. | D6; the first independently witnessed captures. Its reviewed outcome gates the real profile. |
| C2 | Two audits through the real service path, `max-placements: 1`, `placement-timeout-seconds: 600`: catalog `open-ordinary`, then `open-inadequate`. | Tool names on assistant events; whether a harness report or a partial frame follows the submit reply before the harness is gone; the usage line and usage object; refused calls; the delivered package. | For "a final report can be captured": C1's sessions, which end with one; the placement Stewart stops after submission; the second audit. | D6, D7, D12. |
| C3 | One audit. A text source under 50,000 characters and an ASCII source long enough for two full 64 KiB pages; the question needs text from each page's tail. A token-dense page for the documented 25,000-token limit is optional. Question design is open; a `search` shortcut must be visible in the call record. | The harness's echo of each tool result (whole, truncated, an error or a file reference) beside the page Stewart supplied; the model's next call. | The full page; the source under the limit; the second full page. Other route: the retained full-page deliveries of `haiku-recovery-live-12` and `-14`. | D8; a call naming a tool outside the commission also feeds D6. |
| C4 | Two audits, `max-placements: 3`, a commission needing more time than its deadline (120 s, then 180 s), so the first placement ends at a commissioned deadline and `run` continues it. This is the contract's own interruption, not the externally timed kill the subscription track still owes. | In each continuing placement: how many harness reports follow the question and continuation notice Stewart sends together; whether a reminder is issued or authoring ends before the model has acted; the first tool call. | The continuing placements; C2's placements, which receive one message; the second audit's different interruption point. | D9, D2. If the first continuation ends authoring at once, the packet stops there. |
| C5 | Three audits of one start. Arm T: the M2 checklist arrangement that reproduced. Arm W: a question asking for one account longer than 16,000 tokens in a single entry. Arm P: M1's firing wording. | What the harness emits when a response reaches the cap (it recovers, a non-error report, an error report) and whether thinking counts; for arm P, whether a reminder written after a report reaches the model as a new turn. | Arm W; C2; arm T, where the excess is thinking. | D10, D1. An arm that does not reach the cap is unexercised. |

### Recorded if they occur, never provoked

If one occurs, the packet stops, the captures are kept and it enters D11.

- A transient provider error while harness retries are 0 (X4, X1), and on the
  Messages route any 429, 5xx, 529 or `retry-after` value.
- A rate-limit event with a rejected status, or paid extra usage reported
  enabled or in use (X5). The contract forbids commissioning such an account,
  and deliberately reaching a usage limit needs its own commission.
- A harness cancellation of an executing call (X9), an assistant model name
  other than the commissioned one (X7), a harness compaction boundary.

### Retention, captures and review

- [ ] Each launch writes a new `.scratch/<run>/` folder; containers stay until
  review, and witnesses stay outside the audit and anything a run removes.
  Register each reviewed run as a selected evaluation with its purpose and
  release condition
  ([retention](development/DEVELOPMENT.md#evidence-and-retention)).
- [ ] For every capture chosen as a fixture anchor record: run, member path,
  size, SHA-256, date, model, API or harness version, and whether an
  independent observer or Stewart captured it. Originals are never edited.
- [ ] A tracked fixture is a redacted copy with a list of what was replaced.
  Remove credential bytes (rescan the copy); provider request and message
  identifiers; account, organization and workspace identifiers; thinking and
  compaction signatures; tool-use identifiers, replaced consistently; harness
  session, event and request identifiers; rate-limit utilization and reset
  values; host paths and the user name; audit reference tokens. Raw
  authentication output is never retained. Tracking any capture class is the
  principal's decision.
- [ ] Review before reliance: the apparatus's procedural review, then a reading
  of the original captures by a reviewer who did not operate the run, then the
  principal for anything that changes what Stewart promises.

**Complete when** every packet has a reviewed outcome or an explicit
disposition (not approved, handed to its owning plan with its prerequisite, or
unexercised), and no process, start or audit is left in an unknown state.

## 3. Fixes and reassessment after the live runs

### Decisions

Actions: a specification change the principal decides (S), a service change
(V), a driver change by an independent author (R), a note to a later plan (N),
or closing as accepted (C).

| | Question | Outcome | Action |
| --- | --- | --- | --- |
| D1 | Prose turn end and reminder (M1, C5) | No arm fires | C for the run; N to the conformance plan: the rule is still unmet by a real model |
| | | Fires; the auditor then works or submits | C; the exchange anchors fixtures |
| | | Fires and a second prose turn ends authoring, or arm A fires | S: the one-reminder rule ([CONTRACTS, bounded prompting](CONTRACTS.md)), with the transcript |
| D2 | First response of a continued audit (M3, C4) | A tool call | C; N to the conformance plan, section 2 |
| | | Prose, reminder unused and then delivered | C |
| | | Prose, reminder already spent: authoring ends with none delivered | S, then V and R |
| D3 | The 16,000-token cap (M2, M3) | Reproduces; low effort avoids it | S: keep the cap and tell the manager the remedy where the stop is shown, or change the cap |
| | | Reproduces at both efforts | S: the cap itself |
| | | Does not reproduce, arm G included | C as specific to the study build; N to the conformance plan, section 4 |
| D4 | Summary shape off Haiku (M4) | Accepted | C as a sample of two; N to the conformance plan, section 4 |
| | | Departs from the accepted shape | S: [INTERFACE 6.2](docs/INTERFACE.md#62-requests-and-responses), then V and R |
| D5 | Startup-stop words (L0) | As assembled | C; already an input to the specification work |
| D6 | Tool names (C1, C2, C3) | Prefixed only | C; record in the runtime reference |
| | | An unlisted or unprefixed name appears | S: what such a call costs on this route, then V and R |
| D7 | Final report after submission (C2) | None before the harness is gone | S: wait a bounded time for it, or say that Stewart's stop left usage unknown |
| | | A report arrives, or a partial frame is left | V if the record or usage line misstates it; otherwise C |
| D8 | Page above 50,000 characters (C3) | Delivered whole | C; record in the runtime reference |
| | | Truncated, an error or a file reference | S: the runtime page bound or a declared tool result limit, then V and R |
| D9 | Reports per message sent (C4) | One per message | S: which harness event is an ordinary turn ending ([CONTRACT](docs/claude-code/CONTRACT.md#limits-usage-and-continuation)), then V and R |
| | | One for both messages | C; the recognition rule still goes to the specification work |
| D10 | Output cap on the harness (C5) | Harness recovers | C; record |
| | | A report that reads as an ordinary stop, or an error | S: the route difference in row CC-26, then V |
| D11 | An unprovoked event occurred | Any | Review the capture; S or V as it shows; otherwise N to the subscription track's unresolved observations |
| D12 | Refused calls (every packet) | Counts and habits | N to the specification work on showing refusals |

- [ ] Record each row's outcome with its evidence path, then act. A
  specification change lands before the service and driver changes it causes;
  those go to separate agents, and the driver author receives the
  specification and the unedited driver-side result files only.
- [ ] Run the rows of
  [the check table](development/DEVELOPMENT.md#what-to-run-for-what-you-changed)
  for what changed: `service/src/` or `service/tests/`; INTERFACE or
  QUESTION-FORMS; runtime schemas or pinned texts in CONTRACT; the release
  driver; `claude_code.py`; `apparatus/c10/`; `apparatus/claude-code/`.
- [ ] A change to the launch surface or tool definitions voids the profile's
  check: no further service placement until a new supplied-surface check is
  approved and reviewed. A service change needs its container acceptance run
  before another Messages packet.
- [ ] Move what was observed out of "Unverified" in
  [the runtime reference](docs/claude-code/RUNTIME-REFERENCE.md#unverified)
  into its reviewed observations, with their limits.

### Anchoring fixtures

Standing `unanchored-fixture` and `stand-in-provenance` findings, by the capture
that would anchor them; detail is in `.tmp/readiness/a/merged.json`. A finding
appears under each capture it needs. Driver-side findings (A19 to A27) are
changed only by the independent driver author.

| Capture | Findings | New capture from | Retained now |
| --- | --- | --- | --- |
| Messages response with tool calls | A01-2, A02-2, A04-5, A04-8, A10-5, A10-6, A10-10, A19-6, A28-11, A28-15, A31-12 | M1, M2 on the current binary; M1 adds the first `end_turn` body | 356 bodies in the runs `empirical.md` lists |
| Provider error body and recorded headers | A02-3, A10-7, A10-9, A14-6, A15-2, A21-2 | no packet: errors are not provoked | one 401 body; no 400, 429 or 529, no `retry-after` |
| Compaction response | A21-1, and the compaction parts of A01-2, A10-6, A28-11 | M4 | one, Haiku (`haiku-recovery-live-14`) |
| Harness startup event | A12-7, A24-1, A26-4, A29-7, A30-8 | C1, independently; C2 | the two probes, two-tool fixture |
| Harness result, rate-limit and compaction-boundary events | A12-8, A12-9, A12-10, A24-1, A26-4, A26-6, A29-7 | C1, C2 for results and allowed rate-limit events; no packet for a rejected or overage event or a compaction boundary | three results, three allowed events |
| Authentication report | A06-3, A29-6, A29-9 | C1: the three allowlisted members, exit and duration | probe 01, logged in and logged out |
| MCP client traffic | A12-11, A26-7, A27-1, A29-10, A29-11, A29-12 | C1 at the fixture's sockets; C2 for Stewart's own tools | probe journals |
| Hook input | A24-1, A26-4, A26-6, A26-7, A27-1, A29-10 | C1, C2 | probe 02 hook journal |
| None of these: wire framing, proxy, operating system, Keychain, signature tool, driver run records | A10-8, A11-6, A11-7, A11-8, A12-12, A21-3, A25-5, A25-6, A26-5, A27-2, A28-9, A28-10, A28-12, A29-8, A29-13, A30-3, A30-4, A30-5, A31-7, A31-8 | not a live-run matter: retained local records or a launch-free reproduction | varies |

- [ ] Anchor from retained captures first where the last column allows it.
  Derive each hand-built variant from an anchored capture by one named change,
  and state the capture in the fixture.
- [ ] Pass the groups no packet supplies to the conformance plan (error bodies)
  and the subscription track (rejected and overage events, compaction
  boundary) as notes.

### Reassessment

- [ ] Re-rate only the units that stage 1 or this stage changed, added or
  re-anchored, against the review's rubric and finding rule. List them from
  the changed paths and `.tmp/readiness/a/batch-NN.expected.json`. Driver units
  are re-rated by a reviewer who has not read the service; one refuter per new
  finding. The rubric and finding rule are in
  [Appendix B](#appendix-b-the-rubric-for-re-rating).
- [ ] Recount trusted units per reliance row with
  `.tmp/readiness/tools/trusted.py`.
  Before: runtime comparisons 32 of 165 (23 without a synthetic or stand-in
  fixture); Messages conformance 123 of 330 (73).
- [ ] Recheck only the unreached conditions a fix claims to reach,
  `close_in_progress` first.
- [ ] For each ledger row whose manager-facing words changed, replace the words
  assembled from source with words taken from a run.

The decision to proceed changes if any of these holds: a live outcome shows
authoring or a placement ended on ordinary model behavior and no decision was
taken on it (D1, D2, D9); the runtime row's trusted count has not risen once
its captures exist; a reliance row holds no trusted unit; a unit added by a fix
draws a standing `self-oracle` or `vacuous` finding; a packet left stopping or
custody unknown. The principal sets any threshold from the reported counts.

**Complete when** every decision row has a recorded outcome and action, each
capture group is anchored or passed on with its owner, the recount is reported,
and the principal has confirmed or changed the decision to proceed.

## 4. Outflow to the plans that follow

Each row is added to the plan named, in the section quoted, as the note given. A
row marked † is reworded after stage 3, because a live run bears on it. The
16,000-token response cap (X3) is put to the principal at the stage 3
reassessment; if deferred it travels as the last Messages row.

### [development/MANAGER-INTERFACE-PLAN.md](development/MANAGER-INTERFACE-PLAN.md)

| Item | Review identifiers | Section of that plan | Note to add |
| --- | --- | --- | --- |
| What a role is, and the registry's content | Ranked 1; `c/registry-1.md`, `c/registry-2.md`; ED-024, 134; K7 | "1. Specify the shared commissioning and documentary contracts", items "Specify the family registry" and "Specify how the manager declares roles" | The principal first decides what a role is. From the specifications alone two implementers fully cited 3 of 27 registry cells: no family names a role; "evidence class", "availability" and "explanation/remedy text" occur in no specification; the front matter admits one scalar per key. Their unanswered questions are section 5 of each file under `.tmp/readiness/c/`. |
| What a family consists of and what its version covers | ED-020, 021, 022, 034, 046, 081 | Same items | Five passages define a family and no two agree. QUESTION-FORMS specifies an ID and version, one instruction text, ordered recording tools, expected sections and, for open inquiry, replaceable instructions. The common tools and the four notices have no version identifier: decide what a family version covers. |
| What a manager is shown when a placement stops † | X1, X5, X7, X11, X12, X9 (deadline half); 1.1 rows 3 and 14 | Stage 1, items "Walk `new`, `prepare`, ..." and "Separate diagnostics into stable errors, warnings and suggestions" | The sentence recorded with a placement's ending is printed by neither `run` nor `status`. On the Claude Code runtime every stop on a startup or stream observation, a local launch failure or a harness failure reads `Run <n> was interrupted (protocol_anomaly)`, a cause the runtime contract never assigns; a workspace under a marked ancestor consumes a start, and no list of checks made before a start names that rule. Decide whether the sentence is shown and which causes the runtime contract names. |
| What a manager is shown when calls are refused † | X10 | Same items | CONTRACTS says refusals reach the manager "through status and records"; `run` and `status` report nothing about a refused call. In retained real runs 46 of 678 calls were refused, for recurring causes. Decide what is shown. |
| The reminder rule's presentation † | X2; ED-072 | "5. Finish the documentary interface", item "Explain bounded autonomy, dead-placement continuation ..." | The reminder is one per audit and is spent when recorded: a continued placement can end authoring at its first turn without a submission, with no reminder in that conversation. Say so where continuation is explained. |
| When to choose each family | Ranked 13; ED-023, 025, 051, 126, 148, 149, 151, 152, 153, 155; `c/manager.md` section 2 | Stage 1, "Specify the family registry" (purpose; explanation/remedy text); stage 5, item "Publish one file-only walkthrough ..." | Nothing a manager reads says when to choose a family: `help forms` prints the auditor's instructions, and what each family commissions and what to supply is in CONTRACTS alone. A first-time manager's reading and seven help items are under `.tmp/readiness/c/`. |
| Differences between the two runtime arrangements † | X4, X6, X7, X8, X3 (runtime half) | "3. Complete the independent CLI path", item "Add effect descriptions ..."; stage 6 table, row "CLI effects and interruption" | A manager can see the arrangements differ: four request attempts against none; a wrong tool name refused against the placement ended; usage reported against an uncovered interval after a successful audit; a full `read` page against the harness's documented result limit; a local network failure shown as `provider_unavailable`. Describe each in the effect descriptions or remove it. |
| Tests under the commissioning rules | A03-1, A03-3, A06-1, A06-2, A13-1, A13-4, A13-5, A13-6; driver A17-2, A18-1, A18-2, A21-5 | "2. Implement one set of production rules", item "Extract pure parsing and validation ..." | Of 157 test units behind these rules 98 are trusted. The listed tests were corrected to take expected values from the specification; an extracted rule's tests keep that, and none takes its expected value from the rule's own output. |
| Tests under the returned-question, lifecycle and custody comparisons | Corrected: A04-1, A04-2, A04-4, A07-1 to A07-4, A08-1, A08-2, A14-1, A14-2, A14-4, A14-5, A15-1, A20-3, A23-2. Open: A05-1, A04-5, A04-8 | "3. Complete the independent CLI path", item "Implement the accepted question body in the returned package"; stage 6 table, row "Custody and autonomy" | Of 290 units behind these comparisons 208 are trusted. The shared post-launch fixture writes the return manifest and every record with the service's own writers (A05-1), so an encoding that departs from INTERFACE 8.2 or 4.4 consistently passes every delivery test: write it from the literal forms when the package gains the question. |
| Runtime conditions no test reaches | U075 to U136 (runtime contract: 23 unreached, 23 partly); U377 to U379; U035 to U054 (`apparatus/claude-code`: 14, 3) | "Remaining offline runtime coverage and evidence review", first item | No test feeds the runtime the events that stop a placement. 46 conditions of the runtime contract, 3 of the runtime reference and 17 of the apparatus instructions are unreached or reached in part: filter `.tmp/readiness/a/unreached-merged.json` by `doc`. |
| No real-session evidence † | Ranked 6; A06-3, A12-7 to A12-12, A24-1, A25-5, A25-6, A26-4 to A26-7, A27-1, A27-2, A29-6 to A29-13, A30-3 to A30-5, A30-8 | "Prepare a concrete, reusable comparison", item "Name the unresolved observations explicitly" | No Stewart placement has run through the real harness. Of 165 units behind the runtime comparisons 32 are trusted, and every harness frame in every test is hand-built (28 findings). Add the observations this plan's live runs leave open. |
| Loopback skip | A01-1, A02-1, A11-1 | "Verification and completion" | Delete "Fix unavailable-loopback reporting so an actual skip cannot be reported as a passing test." once 1.4 lands. |

### [MESSAGES-API-CONFORMANCE-PLAN.md](MESSAGES-API-CONFORMANCE-PLAN.md)

| Item | Review identifiers | Section of that plan | Note to add |
| --- | --- | --- | --- |
| Provider bodies modeled by hand † | Ranked 8; A01-2, A02-2, A02-3, A10-5 to A10-10, A11-6 to A11-8, A14-6, A15-2, A19-6, A21-1, A21-2, A28-11, A28-15, A31-12; batch 22 note 2 | "4. Establish real compaction and provider coverage", item "Verify current provider compatibility against primary documentation ..." | Every test of the adapter, the driver's fake provider and the apparatus fakes play the provider with bodies written by hand; real captures are retained under `.scratch/` and none is a tracked fixture. Of 330 units behind this plan 123 are trusted. Choose captures to track, with source, date, model and API version recorded, and derive the hand-built variants from them. |
| Retry, timeout and connection paths no test reaches | U285, U287, U289, U290, U291, U293, U294, U296; U241, U244, U282 | Section 4, item "Keep real-provider timeout and `max_tokens` behavior explicit in the coverage matrix" | No test reaches a stop during a retry delay, the limit recheck after it, a failed name resolution, a refused connection, connecting time charged to the request deadline, or an abort during the tunnel or TLS handshake; 408, 504 and a `retry-after` of 61 seconds are reached in part. Give each a fake-provider case or a disposition before a live packet relies on it. |
| Compaction strictness † | X11; U254, U258, U261, U265 to U268, U276 | Section 4, items "Design a separate specimen ..." and "Require a real summary request/response ..." | A placement ends unless the summary response has exactly the expected stop reason, block and `usage.iterations` content, and a response with an unrecognized iteration type is discarded. One live compaction is the whole sample. Record the shape of every real summary response; a departure is a finding about the rule as well as the run. |
| Apparatus conditions no test reaches | U024 to U034 (`apparatus/c10`: 9 unreached, 1 partly); U062 to U068 (`apparatus/sanity`: 5); A28-9, A28-10, A28-12, A31-7, A31-8 | "3. Extend the procedural verifier and its controls", item "Pair checks with firing controls, differing cases and invariance cases" | 15 conditions the apparatus instructions state are unreached or reached in part, and five fixtures stand in for host tools, driver results and the credential observer without a capture. Add each to the control inventory or dispose of it. |
| The response cap, if the principal defers it † | X3 | Section 4, the `max_tokens` item; "1. Complete the evidence matrix", first item | Each response is capped at 16,000 output tokens and thinking counts against it: two real Haiku placements spent a whole response on thinking and ended `interrupted (max_tokens)` with nothing recorded. The cap is a restriction the principal has yet to decide; decide it before the matrix fixes effort levels. |

### [RELEASE-PLAN.md](RELEASE-PLAN.md), "Coverage and acceptance-policy review"

Note to add after the candidate gaps that section already names: "A read-only
review found 114 specified conditions that no test in any tree reaches and 91
reached in part. `.tmp/readiness/a/unreached-merged.json` gives each one's
clause, the searches made, the unreached part and what is at stake. Twenty more
were expected by a reviewer and are stated by no passage (verdict
`not-specified`): each is a behavior to specify or a test of something
unspecified. The driver's own counting and exit-status rules have no firing
control (A16-3, U001, U002), and the apparatus reads C9's 'tens of
milliseconds' as 100 ms." The table goes with it.

| Specification | Unreached | Partly | Identifiers |
| --- | ---: | ---: | --- |
| ACCEPTANCE, rules and C2 to C20 | 10 | 4 | U001 to U022 |
| INTERFACE 1, 3 and 4: conventions, submission folder, archive | 8 | 12 | U147 to U196 |
| INTERFACE 5, the manager CLI | 10 | 10 | U197 to U232; four are `close_in_progress`, closed by 1.1 |
| INTERFACE 6, the run adapter | 17 | 11 | U233 to U296; nineteen are also in the Messages table |
| INTERFACE 7, the auditor's tools | 8 | 10 | U297 to U330 |
| INTERFACE 8, 9 and appendices A and C | 5 | 8 | U332 to U370 |
| QUESTION-FORMS, DEVELOPMENT and `apparatus/README.md` | 4 | 7 | U372, U373; U141 to U146; U056 to U061 |
| With the other two plans: runtime contract and reference, `apparatus/claude-code`, `apparatus/c10`, `apparatus/sanity` | 52 | 29 | In the two tables above |

## The review's files

`.tmp/readiness/` is 7 MB, untracked and not backed up. Model agents produced
it, and another run would not reproduce it identically.

- [ ] At the start of stage 1 ask the principal whether to back it up: the
  manager supplies backups of evidence that cannot be reproduced.
- [ ] While this plan runs, change nothing under it except to add
  `driver-handoff/`. Only plans link into it.
- [ ] At completion keep it until each destination plan has closed the rows
  that cite it, which each note records; then remove it. If a destination plan
  is deferred indefinitely, the principal chooses between keeping the backup
  and copying that plan's rows out in full.

## Completion

Complete when stage 3's reassessment is confirmed by the principal and every
row of section 4 is in its destination plan. Then move anything enduring into
the documentation and tests it belongs to, dispose of the review's files as
the section above says, and delete this plan with its row in the release
plan's work order.

## Appendix A: driver findings

The 41 standing findings against `apparatus/driver/`, each in its reviewer's
own words, most consequential first. Part 1.3 says which are corrected now and
what else is handed over.

| Finding | Reviewer's claim |
| --- | --- |
| A19-3 | These cases hold all their claim checks in a Procedure body, accept any run reply with outcome completed (which INTERFACE 5.7 gives for every recorded ending), and never require the Procedure to have finished, so a run that ends after its first few calls passes with the remaining checks never recorded. |
| A16-3 | No self-test or other unit exercises the driver's case selection, skip tallying, control-status tallying or exit status, so ACCEPTANCE's counting rule and README's exit-status rule have no firing control in the driver. |
| A16-1 | When docs/QUESTION-FORMS.md or docs/INTERFACE.md is not beside the driver, self_test records the skipped specification comparisons as a passing check (ok True) instead of a skip (ok None), so the self-test reports success without having compared any pinned text. |
| A18-2 | Parts dropped with t.skip_part leave the case tallied as passed, and in c19.bounds.paths the component_bytes over-bound part is dropped on every ext4/xfs/btrfs run. |
| A19-4 | Parts of these cases are dropped by run configuration while the case is still tallied pass: the non-loopback http:// URL without --network-isolated, run_held on the release variant and any non-Linux host, and the over-32 MiB shape under --skip-heavy (this one not even recorded as a skipped part). |
| A21-5 | When loopback listening is unavailable, c15.guidance-capture records skip_part and skips both fake placements, source-removal continuation and the two commission_damaged run refusals, yet the case variant can still be tallied pass. |
| A17-2 | When the driver runs as root, c15.damage skips the unreadable-capture part named in its title with skip_part, and the case can still tally pass. |
| A19-5 | The untrusted-certificate leg checks the connection_failed attempt outcomes only when Stewart's run directory exists, so a binary that writes no run directory passes the claim that every attempt failed TLS as connection_failed. |
| A19-1 | c6.payload-kept checks each payload file against the sha256 and size in Stewart's own entry record rather than against the texts 'v1' and 'v2' the procedure sent, so a payload file that holds the wrong bytes but matches its own record passes. |
| A18-1 | c18.permissions accepts any refused or failed status reply for a mode-000 archive root, although INTERFACE Appendix A gives archive_unavailable for a root that cannot be opened, so a refusal for an unrelated reason passes. |
| A20-3 | In the manifest-write iteration both injected faults are EIO, and causes.original-first checks only that causes[0].error is "EIO", so a reply that put the diagnostic-write cause first would pass. |
| A22-1 | The fake.<framing>.content-bytes sub-rows compare the served content array and ex.content_raw with msg.content_raw, which the same Message object computed and inserted into the served body, so no independent expected value checks the content bytes. |
| A22-2 | The four fake.tls.control.* sub-rows pass on any ssl.SSLError or OSError, including a missing certificate or CA file, so a control whose certificate fails for a reason other than its designed one (untrusted issuer, wrong name, expiry, other root) still passes. |
| A22-3 | accepts.current.not-json passes on any refusal of b"{", although Accepts.judge distinguishes an unparseable body ("", "There was an error parsing the body of your request") from schema refusals. |
| A23-2 | The auditor.control.truncated-read firing control passes on any anomaly whose check name starts with "read.", so it would pass if truncate_silently provoked a different read check than the completeness/reassembly checks it is meant to fire. |
| A24-6 | The explicit capture/write diagnostic check accepts any text containing a capture or write word and a failure word, and the case never requires the placement to end interrupted with cause archive_write_failed. |
| A24-4 | The runtime-profile-with-limits control accepts any refusal although its question also omits both required placement fields, so a setting_missing refusal satisfies it even if limit-* fields were admitted. |
| A24-3 | summary_facts at used=0 with a three-placement limit cannot tell 'allowed' from 'remaining', because one occurrence of '3' satisfies both regexes. |
| A25-1 | The <family>.schema.<tool> sub-rows take the expected inputSchema bytes from parse(base).get('input_schema').raw, the same rawjson slice that mcp_tools concatenates into its output, so a raw-slice defect shared by both sides would pass. |
| A25-4 | The mcp.refuses.* and environment.decoder-refuses-* sub-rows count any ValueError as the named refusal, though the decoders raise distinct ValueErrors per rule, so a refusal for the wrong reason passes (any-error). |
| A26-1 | In the observer self-test's positive, closed-gate and invariance rows, the launcher capture digests and the launch record that the observer compares against are copied from the observer's own state, so an observer that mis-counted or mis-hashed captured bytes, or held a wrong expected launch, would still report witness-integrity and supplied-surface as observed. |
| A26-2 | The observer self-test's startup-variant, event-refusal, process-result, partial-socket, malformed-hook and witness-failure rows pass on any ObserverStop or any recorded error, although the observer records a distinct reason for each condition, and no valid assistant or rate_limit_event frame is ever fed, so an observer that refused every assistant or rate-limit event would pass six of these rows. |
| A26-3 | The peer self-test's refuses() helper passes any ValueError, OSError or SystemExit, and the arbitrary-command row is refused because the settings hook command no longer matches the derived writer, not because the writer is arbitrary: changing mcp.json and settings.json consistently to /bin/sh, with the synthetic marker bytes, would be accepted by validate_surface. |
| A27-3 | prepare.workspace-files-match compares two outputs of prepare written from the same in-memory dict, so it cannot detect a wrong settings.json, mcp.json or system.txt. |
| A27-4 | journal.shared-clock-and-observer checks the recorded clock name against the same CLOCK_NAME constant the journal writes, so a wrong clock choice passes. |
| A27-6 | <family>.unknown-tool and <family>.duplicate-id pass on any JSON-RPC error although the fixture distinguishes unknown tool (-32602), closed gate (-32000) and duplicate ID (-32600). |
| A27-7 | The mutation rows, package-symlink, symlink-ancestor and manager-binding-{audit,actor} pass on any failed review outcome or any diagnostic, without asserting which named check or refusal fired. |
| A27-8 | unresolved-stop-blocks-next-start-unknown and -present give the code under test one identical input, so the 'unknown' row does not exercise an unknown observation. |
| A24-1 | Every harness observation the runtime cases feed Stewart (auth status, system/init, result checkpoints, compact_boundary, the PreToolUse hook payload) is written by synthetic_harness from the contract's description, with no recorded capture source. |
| A26-4 | Every harness frame the observer is tested on (system/init, result, assistant, rate_limit_event, system subtypes and PreToolUse hook input) is hand-built from the contract's description, not taken from a recorded capture of the pinned harness. |
| A26-6 | The observer's model of the harness's stop-condition events and hook input states no source outside its author: the specification names the categories (delegation, background task start, plugin installation, retry, rejected quota) but not the subtype strings, the rate_limit_info.status value or the hook-input member names the observer matches. |
| A26-7 | The synthetic CLI peer's assistant tool_use event and its PreToolUse hook input have no stated source outside its author: its documentation cites the runtime contract and the private helper section, and neither gives those forms. |
| A27-1 | The harness side of the surface fixture (PreToolUse hook input and MCP client requests) is hand-built with no recorded capture or specification passage defining its shape. |
| A21-1 | Every provider-compaction case plays the provider with compaction responses and usage bodies hand-written in cases_compaction.py from INTERFACE 6.2's description, with no recorded capture of a real provider's on-demand compaction response. |
| A21-2 | reflected_steps() hand-builds the provider's credential-echoing responses (literal and \u-escaped bodies, reflecting content-type/request-id/retry-after headers, 401/529 error bodies, a malformed body and a raw truncated HTTP response) with no capture of how a real provider echoes a key. |
| A19-6 | _shape_placements plays the Messages API with response bodies and tool_use blocks written by hand in the case (not-json, no-usage, repeated-member, over-32mib, no-id, nul-id), with no recorded capture from which the near-valid ones were derived. |
| A21-3 | The credentials.argv-direct and credentials.argv-rosetta self-test rows build the procfs cmdline bytes with the same NUL-join-and-terminate formula as credential_observer.cmdline_forms and the same '/run/rosetta/rosetta' prefix, so they pass by construction whatever real procfs or Rosetta presents; the denied/missing observations hand-model the errnos Linux returns. |
| A25-5 | The environment.nul-decoder-values and empty-decoder sub-rows decode hand-built bytes that stand for /usr/bin/env -0 output; no capture records how the real utility frames a value containing LF and '=', or an empty value. |
| A25-6 | The group-observer.denial-is-unknown sub-row stands in for the operating system's EPERM with a hand-written probe that raises PermissionError, and never observes a real denied group probe. |
| A26-5 | The peer self-test's environment snapshot, which plays `/usr/bin/env -0` output after shell startup, and its shell-added names and values are hand-built, not captured from the frozen wrapper on a supported platform. |
| A27-2 | The stop-blocking rows of the service-witness self-test take process-group observations from hand-written mock return values rather than from an operating-system probe or recorded observation. |

## Appendix B: the rubric for re-rating

The review rated every test unit with this rubric. Stage 3 applies it again to
the units that changed.

One record per unit. A unit is a `#[test]` function; a driver case; a `def
test_` function that a test runner collects; a function registered with
`selftest`, by decorator or by call; a whole monolithic `self_test()`, whose
named checks the reviewer lists as sub-rows (one sub-row for a loop that
generates names); or a stand-in or fake named as a subject. Each batch's units
are listed by name in
`.tmp/readiness/a/batch-NN.expected.json`.

Properties are recorded for the assertions that carry the claim the unit's name
makes. The values of each property are exclusive.

| Property | Values |
| --- | --- |
| Oracle | Where the expected value comes from. `specification`: read from the specification text when the test runs. `witness`: bytes the test itself supplied, or a value computed from them by code separate from the path under test. `cited-literal`: a hand copy of a value the specification gives, or a value a cited passage's rule determines; cite the passage. `literal`: written by hand, with no such passage. `self`: derived from the output being checked or regenerated by the same code path, including a stored expected file whose origin is not recorded (recorded means a commit message or note says how the file was produced). Record the weakest, and how many of the assertions carry it. A comparison between two outputs of the code under test (a repeat against the first, two runs, sent against pinned) is a control, not an oracle. |
| Fixture | What plays the other party; with several parties, record the value latest in this order: `none`, `real`, `specified`, `stand-in`, `synthetic`. `real`: bytes with a recorded capture source. `specified`: input that Stewart's own specification defines (a manager's files, a tool input), with its shape and every value the behavior depends on given by a cited passage. `synthetic`: built by hand otherwise, which includes the output of an external party (provider, harness, operating system) written from the specification's description of it and not from a capture. `stand-in`: supplied by a stand-in or fake that is another batch's subject; name its file. `none`: no other party. Service-side reviewers add `mirrors-code` when a synthetic fixture repeats literals the code under test hard-codes; driver-side reviewers add `narrower-than-specification` when it exercises less than the cited passage allows. |
| Controls | For the property the unit names, which exist: a sabotage control (ACCEPTANCE's [first rule](ACCEPTANCE.md#rules-every-check-follows): a broken implementation, or an input to the check itself, on which the check must fail), a differing case (which includes a malformed input the code is expected to refuse), an invariance case (which includes a repeat of the same input). A control in another unit or file counts when it breaks the property this unit names, wholly or in part; cite it and say which part. For a driver case, a control exists when it is in the case's source, in its declaration or its body; whether it fired belongs to run records. |
| Vacuity | Any of: `any-error` (the assertion accepts any error although the code or specification distinguishes the failure claimed, so a failure for the wrong reason would pass); `indistinct` (the claim depends on telling fields or cases apart and the fixture gives them one value); `skip-as-pass` (an early return or skip, disclosed or not, leaves the unit tallied as passed; name the line); `not-run` (ignored or compiled out, and no command in DEVELOPMENT's check table runs it; a feature-gated unit that such a command runs is not flagged, and the command is recorded). |
| Unreached conditions | Specified failure conditions for the behavior that the batch does not reach, each keyed by its specification clause. These are candidates only. |

Service-side reviewers (batches 1 to 15 and 28 to 32) read whatever their tests
call, including sibling fault and sabotage files for controls, and list the
files they opened. Driver-side reviewers read other driver modules as their
cases require and classify only their own batch's units.

### Finding rule

A finding is raised when any of these holds; its class is the name in
parentheses.

- A unit's oracle is `self` (`self-oracle`).
- A unit has a vacuity flag (`vacuous`).
- A unit in a batch that a reliance row (below) lists has
  a `synthetic` fixture in which its own hand-built bytes play an external
  party (`unanchored-fixture`). Raise this once per fixture or helper, listing
  the units that depend on it. A unit whose fixture is `stand-in` raises
  nothing here; the stand-in's own record carries the question.
- A unit in a batch that a reliance row lists has no control of any kind for
  the property it names (`no-control`).
- A stand-in or fake has no stated source, outside its author, for its model
  of the real counterpart (`stand-in-provenance`).

A `literal` or `cited-literal` oracle alone is tallied, not raised.

Unreached-condition candidates are merged by clause across batches. Each
distinct clause goes to one refuter that may read every test tree and is told
to find a unit reaching it; a clause for which it finds none is a finding
(`unreached-condition`). That refuter reads the service, so its result is
implementation-side whatever batch proposed the clause.

A finding record has: an identifier (`A<batch>-<n>`), batch, file, unit or
units, line, the property values, class, a one-sentence claim, the evidence,
its side (`specification-terms` or `implementation`), every reliance row that
lists its batch, and one line on what a principled fixture would be.

A refuter is a fresh agent given one finding and the batch's files and told to
refute it, defaulting to `refuted` when uncertain. Its verdict is `stands`,
`refuted` or, for a driver-side finding that cannot be settled without the
service, `unsettled-driver-side`.

### Reliance rows

| Row | Later work | Batches |
| --- | --- | --- |
| R1 | One set of commissioning rules, extracted for CLI and MCP | 3, 6, 13, 17, 18, 21 |
| R2 | Returned question, lifecycle and custody comparisons | 3, 4, 5, 7, 8, 9, 14, 15, 17, 18, 20, 23 |
| R3 | Runtime comparisons and the subscription track | 6, 12, 24, 25, 26, 27, 29, 30 |
| R4 | Messages API conformance | 1, 2, 10, 11, 14, 19, 21, 22, 23, 28, 31 |

Batch 16 is the driver machinery under every row. Batch 32 falls under none;
its survivors are reported without a row. A unit is trusted when its oracle is
`specification`, `witness` or `cited-literal`, it has no vacuity flag, and no
finding against it stands or is unsettled. A row whose batches hold no trusted
unit is a finding. Its refuter is given the row and those batches'
classification tables and told to name a trusted unit.
