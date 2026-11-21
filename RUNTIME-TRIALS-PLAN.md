# Runtime trials

This is an agent-managed campaign to make Stewart behave gracefully when an
audit is interrupted, continued or closed mid-placement. It covers the
default-off Claude Code development runtime with the real harness, and the
Messages route. Two live waves run under one commission envelope, with
implementation work between and after them. The operating agent manages the
trials, reviews the evidence, makes in-scope design and implementation changes
and tests the result. It exits with completed work, not recommendations.

Three documents divide the subject:

- This plan says what the agent is authorized to accomplish and how it
  iterates.
- [Live testing](development/LIVE-TESTING.md) says how live tests become an
  ordinary development operation. This campaign is an escalation under it:
  Sonnet, the real harness, witnessed interruptions and close during a
  placement. Its cards, outcomes and kinds of evidence apply here.
- [Unresolved operations](development/UNRESOLVED-OPERATIONS.md) records what is
  still to be learned and which investigations could teach it. Questions this
  campaign answers, narrows or leaves open are recorded there.

The [runtime contract](docs/claude-code/CONTRACT.md) owns the runtime's
boundaries. The [service procedure](apparatus/claude-code/README.md#native-service-comparison-procedure)
and [C10](apparatus/c10/README.md) own the apparatus.

**Status:** proposed. The envelope is not yet granted, and nothing has been
launched.

## Objective

"Gracefully" is a custody claim, never a judgment of the answer:

- the ledger keeps exactly the work completed before the interruption;
- `status` names the interruption, its cause and its evidence;
- `run` continues the same audit under the same cumulative limits and starts;
- the continuation tells the auditor it is continuing, and
  `what_am_i_working_with` shows the recorded work;
- the procedural reminder is spent at most once in the audit;
- usage accumulates across placements;
- `close` works from the interrupted, continued and running states, and the
  delivered package verifies.

The campaign is finished when:

- each in-scope defect it found is fixed with a scripted regression test, and
  each in-scope design question it raised is decided, implemented and tested;
- the changed source has passed its development checks and the container
  suites its rows require;
- each live trial has an outcome (pass, fail, incomplete or unexercised) tied
  to its packet, writer and conditions;
- every audit is closed by its own writer or has an explicit custody
  disposition;
- the runtime contract's undemonstrated list, the README's status where
  demonstrated status changed, and the unresolved record are current;
- the route-disagreement and perturbation rules, as honed by the campaign,
  are in the live-testing procedure;
- retention is settled, the exit report is written and this plan is deleted.

The exit report gives the completed changes, the reviewed evidence and what
remains unknown. It reports unresolved questions without manufacturing them to
create another approval stage.

## Commission envelope

The maintainer grants this envelope once, and it covers both waves. Within it,
the operating agent freezes and approves each packet by digest, launches,
reviews and decides, without further requests. It grants no right to launch
outside these bounds and no exemption from any apparatus control.

| Bound | Envelope |
| --- | --- |
| Routes | **Harness:** in the Linux development VM through the service procedure, with subscription login, included usage only and paid extra usage disabled. **Messages:** direct TLS to `api.anthropic.com` through C10 and its [host queue](apparatus/c10/HOST-QUEUE.md), on the `stewart-haiku` key. |
| Models | **Harness:** `claude-sonnet-5-5` under the profile S0 produces, for the harness version S0 pins. **Messages:** `claude-sonnet-5-5`, and `claude-haiku-5-5` for wave 2 diagnostics. |
| Starts and placements | **Harness:** S0's check sessions and at most 16 service starts, at most 9 of them in wave 1. **Messages:** at most 12 placements, at most 6 of them in wave 1. |
| Cost | **Messages:** worst-case reservations of at most USD 10 across both waves. Each placement's worst case is reserved before launch, and actual reported usage is recorded after review. The key's external cap is shared with other commissions, so the Console headroom must cover the next reservation. **Harness:** included subscription usage only. |
| Time | The service procedure's bounds of 600 seconds per placement and 900 seconds per packet, and C10's watchdog per audit. |
| Bindings | Each packet binds its writer, apparatus commit, inputs, model, limits, interruption point or close, and its starts or placements. A harness packet also binds the profile, harness executable and interpreter. Writers come from commits whose required container suite passed. Each launch path has a current rehearsal of the committed apparatus with that writer. |
| Waves | Wave 1 below, then at most one wave 2 within the remaining bounds. |

**Permitted work:**

- the apparatus: the service procedure, C10, the host queue, and their
  triggers and reviews;
- Stewart's stopping, interruption, continuation, close and re-entry behavior
  on both routes, and the runtime's usage recording;
- the texts, schemas and specification of that behavior, in INTERFACE,
  QUESTION-FORMS and the runtime contract;
- tests, documentation, qualification runs and retention of this campaign's
  evidence;
- reading delivered answers under the rules below;
- driver changes that a specification change needs. These are made by a
  separate agent that has not read the implementation, under the
  driver-independence rule in [AGENTS](AGENTS.md).

**Beyond the envelope.** Stop the affected work, state the boundary precisely
and continue the rest:

- another harness version or profile than S0's, another model, another
  credential, or paid extra usage;
- any launch beyond the bounds, including a third wave;
- a change to custody, attribution, the substance of what participants can
  express, or the release gates in [ACCEPTANCE](ACCEPTANCE.md);
- compaction, turn-cap or output-cap studies, or deliberately exhausting the
  subscription allowance;
- deleting evidence under unresolved custody, public release or disclosure.

## Hard stops

These constrain the agent, and no delegated decision overrides them. Each
stops launches on the affected route until it is resolved; offline work
continues.

| Condition | Stops | Resolution |
| --- | --- | --- |
| Uncertain termination or effects: a process group present or unknown, an uncertain start or an unreconciled claim | That audit and route | Establish the actual effects from retained records and process observations, then record a disposition. If they cannot be established, the route stays stopped and the agent reports. |
| An unexplained wire violation | That route | Explain it from the captures. A Stewart defect becomes a scripted test and a fix, and the route resumes only with a fixed, qualified writer. |
| An evidence-integrity failure: a failed or incomplete review, a changed earlier archive snapshot or a missing witness record | That route | Explain it. If an apparatus or Stewart defect caused it, fix that defect and rehearse it again before resuming. |
| Credential material found in evidence | All live work | Report to the maintainer. |
| A custody failure: criterion 2, 4 or 9 below, or a manager seal claiming auditor submission | Launches with that writer | Reproduce it as a failing scripted test, fix and qualify; continue only with the fixed writer. |
| Unsafe spending on the harness: any sign the subscription allowance is near its end, paid extra usage appearing enabled, or a harness version differing from the pin | Harness work for the campaign | Reconvene with the maintainer. |
| Unsafe spending on Messages: Console headroom below the next reservation, or a placement whose worst case exceeds the remaining reservation | Messages work for the campaign | Reconvene with the maintainer. |

An allowance that runs out mid-placement is recorded as an interruption and is
never provoked.

## Process

### 1. Prepare

- [ ] The maintainer grants the envelope and records the key's current Console
  limit and spend for the host queue configuration, stating which key and
  workspace they cover.
- [ ] Record the grant in the campaign's configurations: a host queue
  configuration for Messages, and a campaign ledger for harness starts. The
  agent checks and updates the ledger before each start, because the service
  procedure has no queue.
- [ ] Let the service procedure accept approval under a recorded delegation, as
  C10 does, and count starts against the ledger.
- [ ] Add a witnessed interruption to the service procedure with two triggers:
  - P1, the placement's `run_started` record;
  - P2, the auditor's completed `prepare` result record in the run directory.

  On the trigger it signals the placement's process group or runs
  `stewart close REF`, and keeps its witness outside the archive. Permit
  continuation after a reviewed signal interruption, and review a close made
  during a placement. Rehearse each trigger and action offline with the
  synthetic peer, including an unexercised control.
- [ ] Give C10 live packets the same two triggers, and close as well as a
  signal. Its live packets accept only the reminder notice today. Rehearse each.
- [ ] Encode the mechanical criteria below in the procedure's and C10's
  reviews, so that an outcome is computed rather than judged.
- [ ] Build a gated writer in the development VM from a commit whose runtime
  suite passed, and pin the release writer for the Messages runs. Keep each
  writer until its audits close.

### 2. Wave 1

Run the fleet below, reviewing each placement before the next placement of
the same audit and before any packet that depends on it. Review is the agent's
own work, not a request for approval.

### 3. Diagnose and change

Classify each outcome as [live testing](development/LIVE-TESTING.md#from-observation-to-the-next-step)
describes. Reproduce defects as failing scripted tests and fix them. Decide the
in-scope design questions and implement them, using the synthetic peer and fake
provider to test. Qualify the changed source.

The P2 continuation question falls here: whether the notice or re-entry should
tell a continuing auditor about a still-current preparation. R3b and M2b
observe the current behavior first. Close the wave-1 audits with their own
writers.

### 4. Wave 2, at most once

Wave 2's composition is adaptive within the remaining bounds. It may:

- repeat an informative or unexercised trial unchanged;
- test a change made in phase 3;
- revise a question or interruption condition;
- investigate a newly found bug;
- give a slot to another question within scope, such as several tool calls
  from one response, or relay loss or cancellation once their instruments are
  built and rehearsed offline under the
  [perturbation rule](#perturbing-to-reach-a-situation).

It does not replicate wave 1 for its own sake. Before each wave-2 packet is
frozen, write its card with the question, the reason it was selected, its
conditions and its criteria. The packet is then fixed like any other.
Adaptation happens between packets, never within one.

### 5. Finish

Complete the in-scope implementation, offline verification and qualification.
Update the contract, the README's status where demonstrated status changed,
and the unresolved record. Move the honed
[route-disagreement rule](#route-disagreements) and
[perturbation rule](#perturbing-to-reach-a-situation) into
[live testing](development/LIVE-TESTING.md), with the cases that shaped them
recorded as examples rather than history. Settle custody and retention, write
the exit report and delete this plan.

## Wave 1

Every trial uses the open-inquiry worked example
([`examples/questions/open/submission`](examples/questions/open/submission))
unchanged, apart from the front matter each packet sets. Interruptions act at
one of two points:

- **P1, the first opportunity:** as soon as the placement's `run_started`
  record appears, before any recorded work.
- **P2, between prepare and submit:** as soon as the auditor's `prepare` call
  has a completed result record in the run directory. `prepare` publishes no
  log record, so this is a new trigger. The window is at least one model turn
  wide: `submit` needs the handle `prepare` returns, so the model must read
  that reply and respond before any seal. The realistic miss is an auditor that
  never prepares.

| Trial | Route | What happens | Starts or placements |
| --- | --- | --- | --- |
| S0 | harness | A supplied-surface check with Sonnet, reviewed and assembled into a Sonnet profile ([preparing a profile](apparatus/claude-code/README.md#preparing-a-profile)); no Stewart audit | The check's sessions, as the controller fixes them |
| R1 | harness | An uninterrupted reference audit | 1 start |
| R2 | harness | The placement deadline stops the first placement after recorded work; `run` continues | Up to 3 starts |
| R3a | harness | A witnessed signal at P1; `run` continues | 2 starts |
| R3b | harness | A witnessed signal at P2; `run` continues | 2 starts |
| R4 | harness | `close` requested at P2; close stops the placement and seals the selection as manager | 1 start |
| M1 | Messages | An uninterrupted reference audit | 1 placement |
| M2a | Messages | A witnessed signal at P1; `run` continues | 2 placements |
| M2b | Messages | A witnessed signal at P2; `run` continues | 2 placements |
| M3 | Messages | `close` requested at P2 | 1 placement |

R2's deadline is chosen from R1 before R2's packet is frozen. It is the elapsed
time from the start reservation at which R1 had recorded about half its
entries. The deadlines of R2's starts must together fit the 900 seconds the
service procedure allows per packet.

The witness watches the audit from outside Stewart's process. When its trigger
appears, it signals the placement's process group or, for R4 and M3, runs
`stewart close REF`. It keeps the triggering record, the process identity and
the observed termination outside the archive. If the placement ends before
reaching the point, or moves past it first, the interruption is unexercised.
That is an outcome to record, not a failure and not permission for another
audit. Both P1 and P2 are realistic triggers: they watch from outside and alter
nothing.

S0 precedes the harness trials, and R1 precedes R2. The other trials run in any
order once their apparatus is ready.

### What Stewart does at each point

This comes from the specification and code. The trials check that the real
harness and the provider leave these behaviors intact.

| Point | A reasonable app should | Stewart does |
| --- | --- | --- |
| P1 | Stop cleanly and record the interruption. Invent no answer or seal. Account honestly for anything that may have been spent. Leave the audit able to continue, or to close with an honest empty return. On continuation, the auditor starts fresh. | Ends `interrupted` with cause `signal`, exit 5; nothing recorded; the reminder stays unused. Messages aborts the in-flight first request and, if any byte of it was sent, charges an estimate of one turn, its whole `max_tokens` (up to 16,000) and its size ÷ 3 in input. On the harness the signal can come before the model sees the question; the start is still used and that session's usage is unknown. `run` continues with the continuation notice and an empty ledger. `close` seals the empty selection as manager and delivers an honest empty return. |
| P2 | Never submit a preparation automatically or discard it; keep the entries. On continuation, let the auditor learn that a still-current preparation exists, or ask it to prepare again and review before submitting. A `close` seals the same selection as the manager's, never as the auditor's submission. | Ends `interrupted` with cause `signal`; entries and the preparation are kept; nothing is sealed. On Messages the request carrying the `prepare` result is probably in flight, so the same estimate is charged. On continuation, `what_am_i_working_with` does not mention the preparation. Its handle still works while the revision is unchanged, but an auditor without memory cannot know it, so it prepares again (identical bytes) before submitting. `close` prepares the selection current at its request and seals that as manager; the answer bytes match the auditor's preparation when nothing was edited. A signal during `submit` lets a seal whose link had begun stand; otherwise the submit is refused `placement_stopped`. |

Reminders for whoever prepares the packets:

- **Messages output allowance:** an aborted request is charged its whole
  `max_tokens`, up to 16,000. An interrupted audit's output allowance must
  cover the work before the point, that estimate and at least 1,024 more.
  Otherwise the continuation ends `limit_reached` before it sends anything.
- **Harness starts:** a P1 signal can come before the model sees the question,
  and it still uses a start. Every interrupted harness trial needs at least two
  starts.

### Wave 1 cost

The Messages runs use `claude-sonnet-5-5` at USD 2 per million input tokens
and USD 10 per million output tokens. A worst case is the input limit, plus one
more request whose size is known only afterwards (INTERFACE 6.4), plus the
whole output limit. With 12 turns, 90,000 input and 16,000 output tokens, M1
comes to about USD 0.50. M2a, M2b and M3 are about USD 1 each, with 24 turns,
180,000 input and 48,000 output tokens to cover the reminder above. Wave 1's
Messages worst case therefore stays under USD 4. The harness trials use S0's
check sessions and at most nine service starts, each with one authentication
check and at most one model session.

## Criteria

Wave 1's criteria are below. Each wave-2 card states its own, starting from
these. Criteria are fixed before a trial launches, and a completed trial's
criteria and outcome never change.

Every placement must satisfy these:

- stopping is observed: no process group remains, and the stop record agrees;
- the procedure's review passes, including MCP call correlation with the
  ledger and the package witness;
- every earlier archive snapshot is preserved byte for byte;
- no wire rule violation goes unexplained.

R1 and M1 pass when the auditor seals and the package is delivered and
verified. Any other ending is incomplete, with its cause named.

R4 and M3 pass when close stops the placement (`stopped_by_close`) and seals
the selection current at its request. The seal carries manager attribution and
no claim of auditor submission. The delivered package verifies, confirmation
is awaited or completed as close requires, and a later `run` refuses
`reference_closed`. When no edit came between the auditor's `prepare` and the
close request, the sealed answer bytes equal that preparation's. Criteria 2, 5
and 8 below also apply.

R2, R3a, R3b, M2a and M2b pass when all of these hold:

1. the first placement ends `interrupted` with the expected cause (deadline or
   signal), and `status` reports it with the starts or placements used;
2. the ledger at the interruption equals what the outside witness saw;
3. the next placement's first input carries the continuation notice;
4. every entry recorded before the interruption is still current at the end,
   or was removed by an explicit auditor `delete`;
5. the audit's log holds at most one procedural reminder;
6. cumulative usage and starts carry across placements;
7. the audit ends sealed by the auditor, or with an honest unsubmitted or
   limit ending that `close` then seals as manager;
8. `close` completes and the package verifies;
9. at P2, no seal exists after the interruption, and the interrupted
   preparation's files are retained unchanged. If a submit's link began before
   the signal was observed, the point was overtaken: the trial is unexercised,
   not failed.

Each trial also records these observations, without judging them:

- whether the auditor calls `what_am_i_working_with` before editing again;
- whether it re-adds text equal to an earlier entry;
- how the harness sends several tool calls from one response, and in what
  order they arrive;
- whether `system/init` precedes the question;
- whether usage arrives for a submitting placement's last interval.

None of these is a criterion.

## Records and review

- **Ledger:** keep a campaign ledger with the evidence, outside every archive.
  It has one row per packet, giving:
  - the wave, trial and question, and for wave 2 the reason for selection;
  - the packet digest, writer, apparatus commit, profile, harness version and
    model;
  - the conditions, and for a perturbed trial what was perturbed and which
    claims that excludes;
  - the outcome and the review digest;
  - any route disagreement met, with its layer and disposition.
- **Before each launch:** check fresh bindings and the envelope's remaining
  bounds. Starts are reserved durably. An uncertain outcome is kept, and no
  later start follows uncertain termination or effects. Reaching an allowance
  or an ordinary ending authorizes no continuation or replacement.
- **Review:** review raw inputs and traffic, outside package inventories,
  process observations and service captures, each with its own provenance.
  Report pass, fail, incomplete and unexercised outcomes apart from any reading
  of answers. An unexercised interruption is recorded with what its witness
  saw. It is never relabeled, and it may justify a wave-2 slot.
- **What a result applies to:** record each result against the actual model,
  harness version, configuration, authentication route, writer and binaries.
  An API result cannot qualify the harness profile, and a subscription result
  cannot satisfy the Messages release gate. Apply the
  [retention rules](development/DEVELOPMENT.md#evidence-and-retention) after
  review.

## Answers and adaptation

Outcomes are recorded before anyone reads an answer. The agent or the
maintainer may then read the delivered answers. A reading may shape the next
question, a wave-2 condition or an implementation change, and that change
carries its own stated reason through the specification and tests.

A reading never changes a completed trial's criteria or outcome, and never
becomes certification. It never becomes a Stewart mechanism conditioned on what
an answer says. Stewart keeps custody of materials, questions, answers and
evidence; it does not judge accuracy or usefulness. Keep reading notes
attributed and apart from the trial records. A return of limits alone is a
valid answer.

## Route disagreements

This is a working rule. The campaign hones it, and at the finish it moves to
the live-testing procedure, where a live-test manager with design authority
needs it. When the two routes disagree, first find the layer the disagreement
is in:

| Layer | Examples | Response |
| --- | --- | --- |
| Custody facts | Ledger, seal attribution, continuation, reminder count, close | **Fix** the route that is wrong, with a scripted regression test. Custody is common to both routes, and a difference here is never accepted. |
| Endpoint behavior | Call batching, cancellation, partial usage reports | **Accommodate** in that route's adapter, mapping the behavior onto the common semantics. If the mapping cannot preserve them, **isolate** the difference as a stated limit in the runtime contract. An accepted difference concerns what Stewart can know or account for, never what it does with custody. |
| What the auditor experiences | Texts, tools, notices, re-entry | **Keep identical.** A change prompted by one route goes to both, as the runtime contract asks, so that what is learned on one holds on the other. |
| Model behavior | Re-entry habits, tool-call patterns | **Record** it as an observation. The harness adds its own context, and the core does not adapt to it. |

Two checks apply to any proposed fix:

- **Would a manager see the same custody facts for the same events on both
  routes?** If not, fix.
- **Does the fix make the shared core branch on the route?** That is a warning
  sign. The Messages route is the shipped product, so a harness-motivated
  change to the shared core must keep or improve Messages behavior and carry
  Messages evidence of its own.

Within this commission the agent fixes custody disagreements on either route,
accommodates in the adapters, changes auditor-facing texts on both routes
together, and states accepted limits in the runtime contract. Record each
disagreement in the ledger with its layer and disposition: fix, accommodate,
isolate, keep identical or record. When a case fits no layer, or a response
proves wrong, revise this rule and note the case that prompted the revision.

## Perturbing to reach a situation

This is a working rule. The campaign hones it, and at the finish it moves to
the live-testing procedure. Its core: **perturb the occasion, never the
response.** A test may control when and whether a situation arises. It may not
change how the part under study responds to it.

**Name the object of study first.** Each kind tolerates perturbation
differently:

| Studying | May perturb | Must leave alone |
| --- | --- | --- |
| Stewart: custody, stopping, continuation | Almost anything outside Stewart, since custody must hold whatever the endpoint and model do. If the endpoint and model can be faked freely, though, a live run adds little beyond finding states the synthetic tests did not imagine | Stewart itself |
| The endpoint: provider or harness behavior | Inputs, the timing of manager actions, and faults that happen in ordinary use | The traffic. A proxy that rewrites or injects responses replaces the real endpoint, which is what a live test buys |
| The model: what the auditor does | As little as possible of what it sees | Prompts, texts and materials. Each becomes part of what is measured |

The same lever can serve one question and spoil another. Asking the model to
make several calls at once is fine for learning how the harness delivers them,
and fatal for learning whether models batch calls unprompted.

**Levers, best first:**

1. **The commission:** the question, materials, limits, deadlines, placements
   and effort. Any value a real manager could choose is realistic. Small
   materials bring the auditor to `prepare` sooner, and large ones toward
   compaction.
2. **Manager actions and their timing:** signal, close, status and
   continuation. A trigger on a record is just a very attentive manager.
3. **Faults that happen in ordinary use and that Stewart claims to handle,**
   induced from outside: process death, a dead relay, a lost caller reply, an
   unwritable destination.
4. **A sharper trigger on a record Stewart already writes,** before building
   anything new. For example, trigger on the record of a call arriving, if
   Stewart writes it before executing the call.

**Do not perturb:**

- what the studied party perceives, beyond what ordinary use supplies;
- Stewart's pinned texts or arrangement for the test only, unless that change
  is the candidate design;
- the endpoint's traffic;
- the binary, with hooks such as fault points or pauses. Evidence from a test
  build is about that build, and covers only behavior that does not involve
  the hook;
- the conditions of observation, as a wrapper changing the executable digest,
  logging that shifts timing or a witness inside the archive would;
- the credential or route.

**A good perturbation turns bad when:**

- **it touches what the question is about.** Tight limits suit a test of limit
  endings and spoil a test of unprompted submission.
- **its size leaves the range of ordinary use.** A two-second deadline tests
  startup aborts. "Invisible" has a threshold too: a held tool reply becomes
  visible when the harness times it out and tells the model.
- **several realistic perturbations add up** to a situation no one would meet.
- **it selects its own outcome,** by rerunning until the event occurs or by
  tuning the question after reading answers. That serves design progress, but
  the result cannot be reported as typical.
- **it becomes product for the test's sake.** See the next paragraph.

**Changing the product to observe it.** With design authority, a hard-to-see
event can sometimes be made observable by improving the product, and the test
environment then moves closer to production. Ask whether we would want the
change if no test needed it. If it serves custody, the manager or the auditor,
it is design. If it serves only the test, it is a hook: keep it out of the
shipped binary and treat its evidence as a test build's. Never design away a
state that participants need, such as review before submission, to make
testing easier.

**The environment.** Keep it as close to production as the question requires,
and declare every difference. The live environment is more watched and more
bounded than ordinary use, but never more helped:

- no extra guidance to the model;
- no friendlier texts;
- no softened endpoint.

**Reading the result:**

- A failure under a realistic perturbation is a finding, because production
  can reach that state. A pass is a sample of the condition tested.
- The card and ledger name what was perturbed and which claims that excludes.
- A perturbed result is never relabeled as an ordinary encounter.

**Ordering across waves: clean first, follow-ups next, play last.**

1. For each surface, the first wave runs the least perturbed test that can meet
   its objective.
2. The second wave serves first what the first wave demands. That means
   reaching an unexercised situation by the smallest added perturbation, and
   checking a fix whose correctness depends on the real endpoint.
3. Slots that remain may perturb surfaces whose clean result is recorded. Such
   runs can add claims and never remove the clean ones.
4. Perturb in the first wave instead when the perturbation is the only way to
   reach the situation, or when a surprise it provokes could only be settled
   live. A Stewart-side defect is settled offline by a scripted test.
5. A clean run is a reference only for the same writer, harness pin and model.
   Custody invariants need no reference. A behavioral difference between one
   clean and one perturbed run is a hypothesis, not a finding.

**In this campaign:**

- P1 and P2 are realistic triggers.
- R1 and M1 are the clean references.
- Cancellation and relay loss have no clean version, since the fault is the
  occasion itself, so rule 4 applies to them. Their instruments are not built,
  which leaves them wave-2 candidates.
- If phase 3 changes the continuation text or re-entry, rule 5 governs any
  wave-2 continuation comparison.

## Decisions

Within the envelope, the agent decides, implements and tests rather than
recommending. Examples:

- the P2 continuation text or re-entry report;
- a drain grace period for a submitting placement's final usage interval;
- trigger and review designs;
- fixes to stopping and continuation;
- the disposition of a route disagreement, under the
  [rule above](#route-disagreements).

When a decision exceeds the envelope, the agent states the precise boundary,
stops only the affected work and continues the rest.
