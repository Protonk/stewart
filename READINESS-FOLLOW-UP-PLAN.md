# Readiness follow-up

Repair specification, implementation and test weaknesses; run bounded comparisons;
act on their results; and transfer remaining work to its owning plans.

**State: stage 1 complete; L0, M1, M2 and C1 reviewed; stage 2 continues.**
M2 reproduced a thinking-only response-cap interruption in sw3z default; the
other three placements submitted and closed. The conditional fifth arm was
ineligible. The interrupted audit and exact writer remain retained for separately
commissioned M3. C1 produced a reviewed supplied-surface check and profile.
The next service comparison has prepared inputs and a reviewed native procedure,
including the corrected UTF-8 artifact witness. Its two-start live commission
remains subject to approval.

| Stage | Result |
| --- | --- |
| [1. Fixes now](#1-fixes-now) | Consistent specifications and behavior, clearer question documentation, and corrected tests and apparatus. |
| [2. Live runs](#2-live-runs) | Reviewed outcomes or explicit dispositions for ten bounded comparison packets. |
| [3. Fixes and reassessment after the live runs](#3-fixes-and-reassessment-after-the-live-runs) | Repairs informed by the outcomes, fixtures grounded in captures, and completion checked against stated conditions. |
| [4. Outflow to the plans that follow](#4-outflow-to-the-plans-that-follow) | Each remaining task recorded in the plan that will carry it out. |

Each stage finishes or explicitly disposes of its remaining items before the
next opens. The implementer owns routine documentation, diagnostic, schema,
versioning, test, fixture and retention choices within the settled contracts.
Complete the stated work and checks without another general approval to proceed.

The principal's intervention is needed for:

- Each concrete live commission: model, inputs, authentication launches, maximum
  starts, budget and stopping rules. Include deliberate cap tests explicitly in
  their bounded commissions. Planning supplies no launch or spending authority.
- Scheduling and running the required container suites.
- A newly exposed tradeoff that would expand scope, weaken custody or access
  guarantees, restrict expression, or require more spending. Bring the concrete
  issue and alternatives; routine repairs implementing agreed policy proceed.
- An external backup destination or action when selected irreplaceable evidence
  actually needs one.

Use [DEVELOPMENT's check table](development/DEVELOPMENT.md#what-to-run-for-what-you-changed)
for every change. Preserve driver independence: an author who has read
`service/src` or `service/tests` cannot change `apparatus/driver/` in that
session. Split changes needing both between separate authors, giving the driver
author the settled specification and driver tasks only.

## 1. Fixes now

Settle the affected specifications first, then simplify the documentation.
Correct the apparatus and driver against those texts. Service-test repairs can
proceed alongside that work once their expected behavior is settled. This stage
needs no live model calls.

### Reconcile specification and behavior

- [x] Preserve close's bounded waiting and make close/status report what is
  established when a run has recorded its ending but still holds the lock.
  Do not infer another close solely from that lock. Specify the exact reasons
  and test overlapping closes after launch and the corresponding status.
- [x] Make cancellation, stopping and deadline races at confirmed submission
  report `placement_stopped` rather than an archive-write failure. Derive the
  placement ending from the actual stopping condition, preserving continuation
  rights, and test cancellation before the seal is published.
- [x] Account for status condition sentences for `limit_reached`,
  `ended_unsubmitted` and `damaged`: show them or remove the unused sentences.
- [x] Specify commission outcomes for a changed preparation and for failures
  before the acceptance link or while publishing acceptance. Distinguish known
  absent acceptance from uncertainty and actual recording failure.
- [x] Clarify effects reporting on refusal without the finished-material
  acknowledgment, `not_sent` for notices in cut-off captured requests that were
  never sent, and reserve use at the 1 GiB retained-payload boundary.
- [x] Specify details callers depend on and loosen tests of incidental wording
  or order: retained locations, reconciled delivery members, verification causes,
  close's waiting message and strict-JSON rule identifiers.
- [x] Specify response-head bounds, interim responses, folded headers, invalid
  content lengths and proxy-variable precedence.
- [x] Add a worked handle/check example for independently derived test vectors.
- [x] Resolve receipt-readback refusal for a planted link; close's delivery/seal
  effects under stopping and publication faults; runtime refusals for unknown
  stopping observations and credential options; and JSON-RPC error responses
  whose request ID cannot be determined.
- [x] Apply qualification-record retention and its tests per suite/platform,
  including keeping the last qualified result after a failure.

Specify the corrected behavior before implementation. Report cancellation,
uncertainty and actual write failures distinctly; exact reason names and
transport handling are engineering choices within those promises. Hand remaining
relay-loss and stop-cause presentation work on in stage 4.

### Simplify question documentation

- [x] Remove duplicate explanations and give each rule one owner across
  [CONTRACTS](CONTRACTS.md), [QUESTION-FORMS](docs/QUESTION-FORMS.md),
  [INTERFACE](docs/INTERFACE.md), the [runtime contract](docs/claude-code/CONTRACT.md),
  [ACCEPTANCE](ACCEPTANCE.md), examples and rendered help. Keep pinned product
  text distinct from explanatory prose; update independent copies when needed.
- [x] State five missing interface facts: the result after a second unsubmitted
  stop, refusal of an over-long `read` source, re-entry gap members, the runtime
  arrangement's `reading` member and the form of `checked_at`.
- [x] Point return-membership explanations to "Returned question and answer",
  version explanations to the runtime leaf-contract rule, and citation names to
  INTERFACE 2.4. Document rejection of the scaffold's placeholder model.
- [x] Correct the Mission's return-content wording. The intended return adds the
  exact accepted question body alongside the answer, without operating history
  or guidance. Use a separate package member when implementing that addition in
  manager-interface work; keep its pending status explicit here.
- [x] Preserve all five family purposes and identify the three implemented
  families. Retain material-role and manager-guidance commitments with their
  implementation status explicit; their detailed design belongs to the manager
  interface and creates no new intake gate here.
- [x] Consolidate permissible answers without narrowing them: uncertainty,
  missing evidence, disagreement, no supported finding and challenges to the
  premise remain expressible. Keep `answer`, `needs-evidence` and `reframe` as
  optional descriptions, not mandatory or mutually exclusive labels.
- [x] Align terminology for current family components with QUESTION-FORMS;
  leave the registry's detailed design and version coverage to manager-interface
  work. Preserve the existing scope of supplied-guidance replacement and the
  rule that family selection grants no additional authority, access or budget.
- [x] Consolidate unselected evidence modules and hidden priors into deferred
  scope and remove the inapplicable acceptance control. Preserve deterministic
  rendering and its reproducibility checks without inventing a manager operation.
- [x] Choose canonical names, clarify undefined wording and remove duplication
  while preserving substantive obligations. Avoid cosmetic folder/schema/member
  renames; necessary changed forms take new versions. Apply the same distinction
  between wording and substantive obligations to Mission, Principles, pinned
  text, bounds and acceptance cases.

Retain original working evidence while it has an unfinished inspection purpose
under DEVELOPMENT's retention rules. Routine selection, redaction and retention
need no approval per capture class or general backup checkpoint.

### Repair the tests and instruments

- [x] Correct launcher/checker tests for spending authority, credential entry
  and refusal, child environments, authentication output bounds, withheld
  exports, observer failure and unreadable evidence. Match the intended refusal
  beside a valid case.
- [x] Correct packet/digest and catalog/template checks, batch deadlines,
  installation/profile pins, build markers, and qualification-record mutations,
  counts and skipped controls. Use independent inventories and controls that
  fail when the named check is removed.
- [x] Correct driver counting/exit-status controls, skipped specification
  comparisons and partially skipped cases. Require procedures to finish before
  crediting their checks and claimed TLS-attempt records to exist.
- [x] Give driver payloads, content bytes, schemas, prepared workspace files,
  clocks and observer captures independent expected values. Tighten TLS,
  parsing, read-completeness, permission, capture-write, JSON-RPC and
  package-corruption assertions to their intended failure.
- [x] Separate driver cases with indistinguishable inputs: diagnostic-cause
  order, allowed versus remaining placements, unknown versus present processes,
  and invalid profiles with multiple defects. Test a consistently substituted
  arbitrary helper command.
- [x] Cover `new` without an existing folder reference, commission without a
  leftover diagnostic, published preparation versus unpublished candidates, and
  the close/submission/refusal cases settled above.
- [x] Make service tests report unavailable loopback and marked scratch ancestry
  as skipped or failed. The 36 loopback-dependent tests must not count as passes
  when their listeners cannot bind.
- [x] Tighten service assertions for damaged archive members, malformed usage,
  chunked bodies, TLS failures, profile members, references, citations and taken
  record names. Distinguish valid UTF-8 carried as base64 and unlinked stage
  records with their own entry IDs.
- [x] Derive expected answers, rendering, scaffolds, runtime surface digests,
  limits, tool order, record digests and confirmation tokens from specifications
  or independent inputs. Add firing controls for credential output, citation
  schemas, scaffold effort and the fault/sabotage inventory.
- [x] Run applicable checks and retain exact counts, failures and skips. Identify
  changed launchers needing a fresh Linux rehearsal before live use.

Fixtures needing provider, harness or operating-system captures go to stage 3.
Stage 4 hands the shared post-launch return fixture to manager-interface work
for rewriting when the question is added to the return.

### Verified basis for the next comparisons

The [qualification index](apparatus/qualified.md#acceptance-readiness-02) owns
the exact Linux counts and binary identities for source `0fdac94`. All cases and
controls passed. Independent review verified the release-binary held-run
refusal and stopping, exact 255/256-byte source names on the separate host mount,
the specified overlong-name refusal, and signal stopping before publication.
Archives and ordinary work remained on ext4. The native Cargo checks remain
at `/private/tmp/stewart-readiness-native-87y7ofsj/RESULT.json`.

The retained M2 C10 rehearsal at `.scratch/c10-readiness-m2-01/REVIEW.json` has 18 of 18
expected observations, zero failed, unstarted or skipped audits; reviewer
comparisons 14/14 with 12/12 controls, operator comparisons 7/7, and reporting
comparisons 11/11. The four ordinary M2 templates each pass 18/18 comparisons
and 16/16 firing controls; the guidance template passes 22/22 and 20/20:
94 comparisons and 84 firing controls overall. Independent review checked
all 17 exported snapshot digests and preservation of earlier snapshots. Collection
through the synthetic saved connection succeeds in a fresh process. The three
deliberately unavailable exports retain private originals in their container.
These are fake-provider results, with no live-access or model-conformance claim.

Recheck qualification and launcher bindings before freezing any live packet.
The frozen runtime controller must carry the independent
`fixture_expectations.py` source. Retain the native controller evidence in
`.scratch/readiness-native-jbpx9el6/` for C1 preparation. L0's retained comparison
is `.scratch/readiness-l0-01/RESULT.json`; its original inputs remain at the
paths it records. Apply DEVELOPMENT's retention rules to
completed repair evidence; historical counts and receipts remain unchanged.

**Complete when:** repairs are checked or explicitly disposed of, expected
behavior is specified, and corrected tests distinguish their named defects.
Changed service behavior remains unqualified until its user-scheduled container
run; changed launchers need fresh rehearsals before live use.

## 2. Live runs

Freeze each packet's inputs, binary, model, authentication route, limits,
stopping rules, replacement policy and witnesses before seeking approval.
Include a dated cost estimate and campaign budget: token/time bounds are not
dollar ceilings. These experiments do not qualify release models.

### Current preparation

- **L0 reviewed:** `.scratch/readiness-l0-01/RESULT.json` compares retained
  inside/outside project-ancestry runs and later read-only status in all three
  forms. The startup stop has no auth/model process records. `launched: yes`
  follows the specified `run_started` boundary; it does not establish that a
  model ran. The useful ancestry remedy is in `run_ended.message`, absent from
  default, detailed and JSON status. Carry that presentation issue into stage 3
  and the manager handoff; no reproduction or live call is needed.
- **M1 reviewed:** the [four-arm comparison](apparatus/qualified.md#readiness-m1-01)
  retains exact inputs, authority and per-arm reviews. All four submitted and
  closed: 27 turns, 211,079 input and 12,458 output tokens, with a $0.0273369
  usage-based estimate against the approved $1 budget. Each original and follow-up
  snapshot passed its procedural review; all 12 status-form invocations succeeded.
  Nine citation edits were refused without changing the answer and later corrected.
  Only the report-only direct arm emitted prose/`end_turn`; request 5 carried the
  exact reminder once, then the model prepared and submitted. This is one
  observation per arm, with service-owned provider captures and no independent
  billing or model-conformance claim.
- **M1 follow-ups:** retain the final arm's exact question and sole supplied report
  as firing inputs for M3/C5. That audit is sealed; M3 needs its own commissioned,
  witnessed interruption and continuation. Stage 3 can ground fixtures in the
  captured prose ending/reminder and natural citation-refusal/recovery sequences.
  The invitation-to-ask answer records an assumption and its stated inability to
  ask the manager; treat that as the auditor's account, not a restriction on
  expression. No second unsubmitted stop or reminder persistence across
  continuation was exercised.
- **M2 reviewed:** the [four-arm comparison](apparatus/qualified.md#readiness-m2-01)
  owns inputs, authority, per-arm results and selected capture identities.
  Three arms submitted; sw3z default response 9 contained one thinking block,
  no text or tools, and ended `max_tokens` at 16,000 reported output/thinking
  tokens. The conditional guidance arm was ineligible and did not run.
  Total use: 59 turns, 3,549,845 input and 110,706 output tokens, estimated at
  $0.9398803 against the approved $30 budget. Original and follow-up snapshots
  each passed 313 procedural checks overall; all 12 status forms succeeded.
  No retries, refusals, reminders or compaction occurred. The three final answers
  have eight entries each, items 1–40, and 37, 0 and 38 formal citations. The last
  review's 45 citation checks include seven from a superseded entry version.
  Single observations establish neither an effort effect nor answer accuracy.
- **M2 follow-ups:** keep the open sw3z-default audit, container and exact writer
  identified in its `REVIEW.json`. It has zero recorded answer entries and
  51 turns, 9,617,683 input and 40,970 output tokens remaining. M3 can examine
  continuation from this cap stop, but cannot claim preservation of authored
  work from an empty selection. Its reminder comparison needs M1's retained
  firing inputs and a separately witnessed interruption. No M2 continuation or
  further start is authorized. Retain the firing cap response and 5sgh default's
  near-cap response that completed with tools for stage-three fixtures and cap
  reassessment; the setting remains unchanged pending those comparisons.
- **C1 reviewed:** the [supplied-surface comparison](apparatus/qualified.md#readiness-c1-01)
  passed all three comparisons, 30 case checks and 10 aggregate categories.
  Positive and invariance each produced one exact fixture effect; the closed
  gate denied the attempt before any MCP tool call or effect. All six invocation
  groups stopped and all three model streams reached EOF. Independent review
  verified 131 evidence members and 91 bindings. Three fresh sessions reported
  Claude Code 2.1.322, Haiku 5.5 and the exact 12-tool inventory. Each preliminary
  `server/discover` probe received an initialize-first error, then completed
  initialization and tool listing. The final reports contain six harness turns,
  12 uncached input, 5,976 cache-creation, 22,790 cache-read and 704 output tokens;
  the reported $0.0017763 list-price cost is not a verified subscription charge.
  Rate-limit events reported allowed usage and disabled, unused overage.
- **C1 follow-ups:** the exact reviewed profile is
  `.scratch/readiness-c1-01/profile.json`; its parent retains the authority,
  originals, check and review. C1 establishes native supplied-surface fixture
  compatibility, not real-service custody, billing or turn/output-cap enforcement.
  No C1 allowance remains. Use these captures for startup, hook-denial and final
  report fixtures in stage 3 without rewriting originals.
- **C2 procedure reviewed:** the
  [native synthetic comparison](apparatus/qualified.md#readiness-c2-procedure-host-02)
  passed positive, wrong-model and invariance cases. Both positive cases submitted
  an account and exact UTF-8 artifact, passed 18 package assertions apiece, and
  closed with their packages and prior archive files preserved. Wrong-model
  startup stopped with no answer effects; one unanswered request remains reported.
  The expanded witness passed 880 checks and nine package reviews with 162
  assertions, including continuation without duplicate entries. All 14 recorded
  authentication/model groups were observed absent. Review also verified 116
  apparatus tests, 35 witness checks and 237 runtime-driver checks. The corrected
  witness now accepts the contract's `utf-8` encoding and refuses `text`.
  These are synthetic native results, not live-service or Linux qualification.
- [x] Prepare C2's ordinary and inadequate open-inquiry inputs from the existing
  C10 specimens, using the reviewed profile. Both local preparations accepted
  the exact profile. `.scratch/readiness-c2-01/PREPARATION.json` owns references,
  input witnesses and replies; original work remains at
  `/private/tmp/stewart-readiness-c2-01`. No commission has been accepted and no
  authentication or model process has started. The proposed audits permit one
  placement of 600 seconds each; illustrative answers are excluded.
- [x] Rehearse and review the [bounded service procedure](apparatus/claude-code/README.md#native-service-comparison-procedure).
  The retained review binds original packets and external witnesses. Keep the
  stopped, unsubmitted bad-init audit through C2 review; no continuation is
  authorized. The earlier unentered preparation has an explicit disposition.
- [ ] Obtain approval for C2's concrete two-start commission, then execute and
  review one packet at a time before any close or next start. Correlate
  service-owned MCP captures and entry records with the independent package
  witness; this does not independently capture every model action. Stop later
  starts on unknown stopping, authentication failure, quota or paid-usage routing.

### Comparisons and proposed bounds

| Packet | Comparison | Maximum proposed use |
| --- | --- | --- |
| L0: startup-stop words | Read synthetic run/status replies; optionally reproduce with a fake harness inside/outside project-instruction ancestry, checking that authentication never starts in the refused case. | No model or Claude launch. |
| M1: prose turn end | Open inquiry with ordinary wording, a request for a direct reply, an invitation to ask questions, and direct-reply wording over inadequate material. Observe reminder delivery, next response and ending. | 4 Messages placements; 48 turns, 640,000 input and 48,000 output tokens overall; 900 seconds per placement. |
| M2: thinking-only response | Two copies of the checklist commission at default and low effort; one conditional guidance-matching arm if neither default-effort arm reproduces. Observe thinking, output, recorded work and ending. | 4 Messages placements plus 1 conditional; each 60 turns, 10,000,000 input and 64,000 output tokens. |
| C1: supplied surface | Positive, closed-gate and invariance sessions with full family tools and actual relay/hook helpers. Observe tool/model names, final reports, rate-limit events and authentication outcomes. | 3 authentication checks of 30 seconds and 3 fixture sessions of 120 seconds; 450 seconds overall. |
| M3: continued audit | Continue M2 audits interrupted at max_tokens; also continue after a recorded reminder if M1 supplies firing wording. Compare first responses, reminder delivery and submission. | 4 Messages placements within remaining cumulative allowances; the reminder arm uses a 12-turn audit. |
| C2: first service placements | Ordinary and inadequate-evidence inquiries through the real service. Observe tool names, submit-to-stop traffic, final/partial reports, usage, refused calls and delivered package. | 2 service starts of 600 seconds and 2 authentication checks. |
| C3: large page | Read a source below 50,000 characters and two full 64 KiB pages whose tails matter. Compare supplied pages with harness echoes and next calls; a token-dense page is optional. | 1 service start of 600 seconds. |
| C4: continued placement | Two audits with three placements each and different commissioned deadlines. Compare initial and continued placements, reports per message and premature authoring endings. | 6 service starts; 900 seconds of placement time overall. |
| M4: compaction on another model | Cross the summary trigger with a long-page commission on a non-Haiku model. Observe summary shape, iteration types and signed-block reuse; mutate copies to test the reviewer. | 1 Messages placement; 24 turns, 1,000,000 input and 24,000 output tokens. |
| C5: turn endings | Compare the thinking-heavy checklist, one requested entry longer than 16,000 tokens, and M1's prose-ending wording. Observe cap handling and whether a post-report reminder reaches a new turn. | 3 service starts of 900 seconds. |

The proposed total is at most 14 Messages placements, 3 fixture sessions and
12 service starts. Frozen packets fix all limits not stated above. M1, M2 and C1
propose `claude-haiku-5-5`; M4 proposes `claude-opus-5-5` or the principal's
choice. Service packets use the approved profile's model.

L0, M1 and M2 come first; C1 can proceed independently. M3 follows M2, with its
reminder arm also depending on M1. C2 requires C1's reviewed surface check and a
real profile. C3, C4 and C5 follow C2; C5 also uses M1/M2 outcomes. M4 follows M1.

M3 needs bounded continuation, multi-placement export/review and a witnessed
interruption point. M4 needs summary/reset reviewer support and trigger
observation. C2–C5 need a real profile and an offline-rehearsed service procedure.
Build only the prerequisites needed for the selected bounded comparisons,
recording that work under its existing owning plan. Hand broader conformance
work onward. A concrete scope expansion beyond these prerequisites returns to
the principal; ordinary prerequisite work needs no additional planning approval.

### Execution and review

- [ ] Obtain each frozen packet's approval. Commission M2/C5 explicitly as
  deliberate output-cap studies with their own bounds. Prior approval, unused
  allowance and previous runs authorize no replacement or continuation outside
  that packet.
- [ ] Use qualified service binaries and Linux-rehearsed templates/launchers for
  Messages packets. Refresh the supplied-surface check after changes to the
  runtime launch surface or tool definitions.
- [ ] Give comparisons firing controls, differing cases and invariance cases.
  A target behavior that does not occur is unexercised. Launch Messages arms
  separately and review each return before the next; retain interrupted audits
  for an explicit disposition.
- [ ] Keep input/package/process witnesses outside Stewart's archive and disposal
  scope. Distinguish independent observations from Stewart-owned captures. Retain
  run replies and default, detailed and JSON status after each placement.
- [ ] Stop on unknown stopping, uncertain effects, lost replies or withheld
  exports. Observe transient errors, rejected quota/overage, cancelled calls,
  unexpected model names and harness compaction if they occur; do not provoke
  them under these packets. Resolve outcomes before proposing further starts.
- [ ] Review procedure and original captures, including a reading by someone who
  did not operate the run. Record refused calls, stop reasons and usage basis.
  Preserve capture originals; record source, date, model/version, size and digest
  for selected fixtures. Redact tracked copies and record substitutions; retain
  no raw authentication output. Select fixtures and apply DEVELOPMENT's retention
  rules as part of the work; request an external backup destination or action
  only when selected irreplaceable evidence needs one.

**Complete when:** every packet has a reviewed outcome or a disposition of not
approved, handed on or unexercised, with no process, start or audit left unknown.

## 3. Fixes and reassessment after the live runs

### Act on the outcomes

- [ ] Apply the one-reminder-per-audit rule across continuation. A subsequent
  ordinary unsubmitted ending ends authoring, even when it is the first prose
  ending in the continued placement. Test reminder accounting, delivery and
  recognition of ordinary model endings; fix transport or event-mapping errors
  without reopening that settled policy. An expected ending is not a readiness
  failure and does not imply an auditor seal.
- [ ] Use the comparisons to retain or adjust the 16,000-token response cap as
  an engineering setting within the commissioned budget. It is not a fixed
  product restriction. Compare default/low effort and continuation within the
  remaining allowance; document the resulting setting, behavior and remedy.
  Changing it grants no additional audit allowance or live spending authority.
- [ ] Act on compaction shapes outside the accepted form, unlisted/unprefixed
  tools, missing final usage after submission, truncated/substituted page results,
  reports per continuation message and harness output-cap endings. Repair them
  within the settled promises, specifying expected behavior before implementation
  and preserving independent driver work. Escalate only a concrete tradeoff of
  the kinds listed at the start of this plan.
- [ ] Correct records or usage statements that misreport outcomes. Record reviewed
  observations and their limits in the runtime reference. Pass unresolved stop
  and refused-call presentation to manager-interface work. Give every unprovoked
  exceptional event an action or explicit disposition.
- [ ] Run the checks for each change. Service changes need container acceptance
  before another Messages packet; changed launch surfaces/tools need a newly
  approved and reviewed surface check before another service placement.

### Ground fixtures and reassess

- [ ] Ground provider tool-call/error/compaction fixtures, harness startup/result/
  rate-limit/compaction events, authentication reports, MCP traffic and hook inputs
  in retained or new captures. Derive variants by one named change.
- [ ] Ground wire/proxy, operating-system, environment, process-observation,
  Keychain, signature-tool and driver-record stand-ins in local observations or
  retained records; these need no model launch. Hand on capture groups the
  packets do not supply, including provider errors and rejected/overage events.
- [ ] Reassess only changed, added or newly grounded tests. Expected values must
  come from specifications or independent inputs; record fixture origins,
  firing/differing/invariance controls and wrong-reason or skip-as-pass weaknesses.
  Have an independent author assess driver units and a fresh reviewer challenge
  new findings.
- [ ] Report trusted coverage for commissioning rules, return/lifecycle/custody,
  runtime comparisons and Messages conformance. A trusted unit has independent
  expected values and no standing or unresolved finding. Recheck previously
  unreached conditions a repair claims to cover, beginning with
  `close_in_progress`. Take changed manager-facing words from actual replies.
- [ ] Report outcomes, repairs, limitations and coverage counts against this
  plan's completion conditions. Counts describe coverage; they impose no
  numerical threshold or additional approval to proceed.

Repair or explicitly dispose of remaining weaknesses, including checks that
use their own output as the expected value or pass without exercising their
claim. Do not claim an unexercised behavior is covered. Resolve unknown stopping
or custody before completing the stage; bring a material unresolved problem
and its concrete tradeoffs to the principal.

**Complete when:** every outcome has an action or disposition, every fixture
group is grounded or handed on, applicable checks pass with exact counts and
limitations reported, and no stopping/custody uncertainty remains. Completion
opens stage 4 without a separate readiness approval.

## 4. Outflow to the plans that follow

- [ ] Add remaining manager work to
  [the manager-interface plan](development/MANAGER-INTERFACE-PLAN.md): material
  roles and family definitions/version coverage; family-selection guidance;
  the separate returned-question member; stop/refusal presentation; reminders on
  continuation; runtime differences; and unresolved real-harness/offline coverage.
  Preserve independent expected values when extracting shared commissioning
  rules. Rewrite the post-launch return fixture from literal forms when adding
  the question. Remove its loopback-reporting task once repaired.
- [ ] Add remaining Messages work to
  [the conformance plan](MESSAGES-API-CONFORMANCE-PLAN.md): provider captures,
  compaction strictness, retry/timeout/connection/handshake paths, apparatus
  controls, deferred continuation/compaction packets and remaining response-cap
  coverage or implementation work under the engineering-setting policy above.
- [ ] Add remaining acceptance work to
  [the release plan](RELEASE-PLAN.md): unreached or partly reached conditions,
  behaviors needing specification, driver counting/exit-status controls and the
  interpretation of timing requirements. Include missing standalone comparisons
  for interim/folded/conflicting-length response heads, the retained-payload
  reserve boundary and `not_sent` notices; clarification and service-unit
  coverage here do not supply independent black-box coverage. Give each a case
  or disposition.
- [ ] Move enduring rules into specifications and tests. Apply DEVELOPMENT's
  evidence-retention rules: preserve selected originals for an unfinished
  inspection purpose and carry necessary task details into the destination plan.
  Indefinite deferral alone creates no retention obligation. Ask for an external
  backup destination or action only when selected irreplaceable evidence needs it.
- [ ] Once stage 3 is complete and every remaining task has its owner, delete
  this plan and its row in the release work order.

**Complete when:** no unfinished task depends on this plan remaining in place.
