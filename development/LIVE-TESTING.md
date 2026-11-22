# Live testing

A live test runs Stewart against a real model to learn what scripted and
synthetic tests cannot show. It reveals how a real model uses the arrangement,
how the provider or the Claude Code harness actually behaves, and whether
Stewart's custody holds when they do. Live tests belong to the
[experiment tier](../ACCEPTANCE.md#three-tiers). They inform design, never gate
a release and qualify nothing. Endpoint alignment, the release's model gate, is
a separate tier with its own coverage
([ACCEPTANCE](../ACCEPTANCE.md#the-endpoint-alignment-tier)).

The default is small and cheap: one Haiku audit on the Messages route, aimed at
one property of one change. Anything larger is an escalation justified by a
particular design question.

## When a change warrants one

Run a live test when a change's correctness depends on behavior only a real
endpoint supplies:

- what the auditor sees and does: the arrangement, tool descriptions and
  replies, notices, re-entry, prepare and submit;
- stopping, interruption and continuation, where the real provider or harness
  sets the timing;
- usage, stop and error shapes that the fake provider or synthetic harness only
  assume.

Do not run one:

- for internal refactors, or custody paths the scripted tier covers;
- to confirm what a scripted test already pins, or to estimate rates by
  repetition;
- to judge an answer. Stewart keeps custody of materials, questions, answers
  and evidence; it does not judge accuracy or usefulness
  ([what the tests don't claim](../ACCEPTANCE.md#what-these-tests-dont-claim)).

The smallest useful test is one audit of the worked example nearest the
change. It runs one placement, or two when continuation is the point. Use the
tightest limits that still let the auditor reach the operation under test, and
check one invariant at one observation point.

## The matrix

Select the rows the change touches. Never run the whole matrix by default.

| Area | Run when the change touches | Smallest test | Observe | Invariant |
| --- | --- | --- | --- | --- |
| Ordinary submission | The arrangement, texts, tools, prepare and submit, delivery | One audit of an ordinary case, one placement | The seal and the delivered package | Sealed by the auditor's own submission; the package verifies; the review is `checked` |
| Tool and custody behavior | A tool's inputs, replies or refusals; citations; edits; re-entry; paging | One audit whose materials lead the auditor to that tool | The tool's call and result records | Every recorded effect has a completed reply and every completed reply its effect; citations meet the mechanical rules; the delivered answer equals the selection the edit history gives |
| Interruption and continuation | Stopping, signals, the continuation notice, cumulative limits, usage across placements | One audit interrupted at a witnessed point, then one continuation | The interrupting record, then the continuation's first input | Recorded work survives unchanged; the notice arrives; the reminder is spent at most once; usage and limits carry over |
| Manager close | Close paths, seal attribution, confirmation | One audit closed after or during a placement | The `close_requested` and seal records | A manager-attributed seal of the selection current at the request, with no claim of auditor submission; the package verifies; a later `run` refuses |

Each catalog case has an inadequate-evidence variant. Use it when the change
concerns what the auditor can say when the evidence is limited. The
[C10 catalog](../alignment/messages/procedure/README.md#cases-and-counts) holds the cases, and
its guide lists the
[witnessed interruption points](../alignment/messages/procedure/README.md#interrupt-a-first-placement-at-a-witnessed-point)
it supports.

## Define the test

Before launch, write a test card of a few lines and keep it with the evidence:

- **Question:** the design question the result will answer, and the commit
  under test.
- **Route and model:** the Messages API or the harness; the exact model ID and
  effort.
- **Conditions:** the case or submission, the limits, any interruption point or
  close, and the placements or starts allowed.
- **Observation point and invariant:** where to look and what must hold, and
  what would leave the test unexercised.
- **Allowance:** placements or starts, and the worst-case cost.
- **Next step:** what follows if the invariant holds, fails or goes
  unexercised.

Fix the invariant before launch. A completed test's invariant and outcome never
change afterwards.

On the Messages route, the worst case is the cumulative input limit, plus one
request whose size is known only afterwards, plus the whole output limit, at
the model's prices ([INTERFACE 6.4](../docs/INTERFACE.md#64-limits-reminder-and-notice)).
An aborted request is charged its whole `max_tokens`, up to 16,000, so size an
interrupted audit's output allowance as the
[C10 guide](../alignment/messages/procedure/README.md#interrupt-a-first-placement-at-a-witnessed-point)
describes. Otherwise the continuation ends `limit_reached` before it sends
anything.

Include Stewart's full estimate for an interrupted request in the cutoff.
The model's context window bounds tokens it can process. Stewart can charge
an estimate based on the serialized request's byte count even when the
provider supplies no usage. If a reservation relies on a maximum request
size, establish that bound before the first billable write. Exercise it with
an oversized capture, an ordinary request under the bound and the same
oversized request without the bound. Record any effect the guard can have on
the writer or its evidence.

## Envelope

Every live test runs under a plan that states its envelope: routes, models,
budget, starts or placements, waves and hard stops. The plan is the authority;
this procedure says how to stay inside it. Routine Haiku tests on the Messages
route run under a standing plan whose envelope covers many small tests, not a
plan per test.

The Messages route's controls are technical:

- a dedicated API key used only for Stewart live tests, in its own workspace,
  with a provider-side spending limit no higher than the plan's budget;
- the key reached only through a
  [saved connection](../alignment/messages/procedure/README.md#saved-provider-connections),
  never in argv, the environment or chat;
- a [host queue](../alignment/messages/procedure/HOST-QUEUE.md) campaign configuration
  carrying the envelope's placement ceiling and budget.

A test whose card fits the envelope runs without further approval. A test
outside it, such as one using another model, the harness or a larger budget,
needs a plan whose envelope covers it ([writing a campaign plan](#writing-a-campaign-plan)).

Scan the private audit evidence and the host's export inputs before publication.
When the commission sets a campaign-wide credential stop, a match ends every
route. Keep the originals and
exact writer under restricted custody, block exports, and report only the
scan counts and verified exposure scope. Leave unsettled reservations in place.

Authority to launch never bypasses a control. Packets stay frozen and approved
by digest, rehearsals and bindings stay current, and nothing continues an audit
automatically.

## Run

1. Commit the change and pass its
   [development checks](DEVELOPMENT.md#what-to-run-for-what-you-changed).
2. Use a writer the route accepts. The Messages apparatus launches only a
   writer in the [qualification record](../apparatus/qualified.md), inside its
   retained Linux container, with a current rehearsal of the committed
   apparatus ([C10](../alignment/messages/procedure/README.md#prepare-a-concrete-live-commission)).
   The harness route runs a Linux gated build with a reviewed profile through
   the [service procedure](../alignment/claude-code/README.md#service-comparison-procedure).
   Today, qualifying the changed source is the main cost of a Messages test.
3. Propose, packet and launch as the apparatus guide describes, through the
   host queue under the plan's envelope.
4. Review with the apparatus reviewer, and record the outcome on the card
   before anyone reads an answer.
5. Close the audit with its own writer, or keep both the audit and the writer
   until closure.

## Outcomes and evidence

Each test ends with one outcome:

- **pass:** the invariant held;
- **fail:** a custody or procedure property failed;
- **incomplete:** evidence is missing, or the run ended before the observation
  point for a recorded cause;
- **unexercised:** the condition never arose, because its point was overtaken
  or never reached.

An unexercised test is evidence about the instrument, not a pass.

Credit a test only with what its instruments supply:

- **Stewart-owned records:** the audit's archive, including its log, call and
  result records, provider captures and usage. They show what Stewart did and
  saw. An omission Stewart shares with them cannot be seen in them.
- **Service-owned captures:** copies the apparatus makes of Stewart's records,
  such as the harness procedure's snapshots. They preserve provenance and are
  not independent.
- **Independent witnesses:** observations made outside Stewart's process and
  archive. These include the apparatus's own copies of what it supplied,
  outside log watchers, process observers, the package witness, and in
  rehearsal the fake provider's or synthetic peer's records.
- **Provider-side facts:** billing, bytes on the network and the harness's
  internal calls. Neither Stewart nor the apparatus observes these on a live
  route. Console usage can bound billing after the fact.

Answers are read only after the outcome is recorded. A reading may suggest the
next question or a change, and that change then carries its own stated reason
through the specification and tests. A reading never changes a completed
outcome and never becomes certification. It never becomes a Stewart mechanism
conditioned on what an answer says.

When a conclusion depends on a count, check the individual cases against the
criterion in the question. A verified delivery establishes the bytes received.
The accuracy of a count in the answer requires a separate comparison.

Retain evidence under [evidence and retention](DEVELOPMENT.md#evidence-and-retention).
A defect a live test finds becomes a scripted regression test; the live run is
not the regression. Select an original for retention only for a present
inspection purpose.

## From observation to the next step

| Observation | Next step |
| --- | --- |
| A Stewart defect | Reproduce it as a failing scripted test, fix it, and run the change's checks |
| A stand-in assumption is wrong | Update the fake provider or synthetic harness from the capture, with its provenance |
| A design question | Decide it within the envelope when there are grounds, and test any change. The question can stay open if the trial leaves the alternatives indistinguishable. Record the boundary for decisions beyond the envelope |
| The model used the procedure in an unexpected way | Record what it did and under which conditions. That observation can stand on its own |
| An apparatus defect, or an unexercised condition | Fix the instrument and rehearse it |
| Nothing new | Record the outcome and move on |

One adaptive retest is optional. It is a new live test of the changed behavior,
with its own card, chosen because the change needs it, not to replicate the
first. Repeat a test unchanged only when its result was unexercised or
incomplete for an instrument reason.

## Keep these apart

- **Messages API and harness.** They differ in adapter, credential, accounting
  and evidence. An API result cannot qualify a harness profile, and a harness
  result cannot satisfy the Messages release gate. A harness test uses the
  subscription login with paid extra usage disabled and a reviewed profile
  pinned to one harness version and model.
- **Haiku and other models.** A Haiku result shows Stewart's procedure working
  with one model that can use it. It says nothing about how Sonnet or Opus
  batch tool calls, re-enter after context loss or reach compaction. It does
  not count for a release that names another model.
- **Experiment, alignment and scripted evidence.** A live test is an
  experiment. Alignment is the release's model gate, and the scripted tier
  qualifies Stewart's behavior.
- Record the platform, executable and runtime profile for each live encounter. The container suites own release and runtime qualification.

## When routes give different results

Trace the difference to the first observation where the routes diverge. Record
the layer, its evidence and its disposition on the card.

| Layer | Disposition |
| --- | --- |
| Ledger, attribution, continuation, reminder or delivery | The same events must yield the same custody facts for a manager. Reproduce the discrepancy and fix the affected route with a scripted regression. |
| Transport or endpoint | Map batching, cancellation and partial usage in the adapter. Document the limits of what the adapter can observe when a complete mapping is impossible. |
| Instructions the auditor sees | Keep the common texts, tools and notices consistent. Test changes on both routes. A harness-motivated change to the shared core needs evidence on Messages. |
| Choices the model makes | Record the sequence, model and conditions. One encounter can supply a question for a later comparison. |
| Observer or reviewer | Compare the original traffic and an independent witness. Fix the instrument and run its positive, negative and invariance controls. A signal before the first request can leave an empty run directory. Checking a directory's existence and checking its files answer different questions. |

## Changing the conditions of a test

Name what the trial measures, what action changes its timing or inputs, and
which claims that change excludes. A signal or manager close after a published
record can exercise ordinary stopping. If submission wins the race, record the
point as overtaken. Keep the first outcome when selecting a follow-up.

- For custody, use the least intrusive means of reaching the state. Scripted
  peers can establish the response to a known event. A live endpoint can show
  whether the event occurs under the commissioned conditions.
- For endpoint behavior, keep the actual endpoint and its replies intact.
  For model behavior, preserve the question, materials and auditor-facing
  text. Record any changes to timing, credentials, routes, limits, binaries
  or instrumentation. An observer that adopts orphan processes must reap them
  while Stewart checks its groups. Otherwise the observer can manufacture a
  stopping failure.
- Prefer an ordinary reference with the same writer, harness pin and model.
  Reach a missed condition with the smallest additional intervention. A fault
  that defines the question, such as loss of a relay, can be introduced on the
  first run. A single behavioral difference between runs leaves causation open.
- Give a product change its own custody or participant-facing reason. Keep a
  test-only hook in a test build and describe what that build demonstrates.

## Escalation

Escalate beyond the default for another model, the harness, compaction,
multi-placement sequences, witnessed interruptions, close during a placement or
deliberate repetition. An escalation states:

- its design question;
- a bounded envelope: routes, models, starts or placements, cost, bindings and
  hard stops;
- how its results feed implementation.

It uses this procedure's cards, outcomes and kinds of evidence.
[Unresolved operations](UNRESOLVED-OPERATIONS.md) records what remains to be
learned and helps choose the question.

## Writing a campaign plan

An escalation, or a standing allowance for routine tests, is written as an
ordinary plan (`*-PLAN.md`), and the plan is the authority for its live work.
It states:

- **Question and objective:** the design question, and what finished means:
  completed changes rather than recommendations.
- **Envelope:** routes, models, budget, starts or placements, bindings,
  permitted work and what lies beyond it, with at most two live waves. The
  first wave is fixed in advance; the second is adaptive.
- **Hard stops:** conditions that halt live work on a route whatever else is
  decided. They include uncertain termination or effects, an unexplained wire
  violation, an evidence-integrity failure, a custody failure and unsafe
  spending. A stop that cannot be resolved ends that route's live work for the
  campaign.
- **First wave:** its tests, with cards and criteria fixed before launch.
- **Ledger:** one row per packet, giving the wave, question and reason for
  selection, digests and identities, conditions and any perturbation, and the
  outcome.
- **Finish:** implementation and verification, documentation, custody closure
  and retention. The exit report gives the completed changes, the reviewed
  evidence and what remains unknown.

Between its start and its exit report, a campaign consults no one. Its
two-wave limit is the stopping condition.
