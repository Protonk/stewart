# Apparatus reports and response vocabulary

Give a bounded experiment block one coherent account from proposal through
result. The principal should be able to understand the question, the proposed
comparison and its limits, then receive a useful finding with its evidence and
any remaining decision clearly identified. This plan owns the apparatus report
design and implementation, and the product response-vocabulary work.
Product behavior is owned by [CONTRACTS](CONTRACTS.md) and
[INTERFACE](docs/INTERFACE.md); apparatus behavior by
[the apparatus instructions](apparatus/c10/README.md). Historical receipts and
retained evidence keep their original bytes and meanings.

## Why

During the stress one-offs a live launch whose audit legitimately ended at its
turn limit printed `"outcome": "failed"` and `Launch or observation incomplete;
inspect retained records and status before another action.` while the
container record said `observed_review_required` and the evidence was intact.
The principal read it knowing what it meant, but a newcomer would have asked
whether the run had failed. Reporting also controls which work proceeds, so
changing the words alone may leave the underlying mismatch intact.

The retained examples are `.scratch/haiku-stress-live-01` through `-05`, with
their reviews at `review/result.json` and interaction findings under `review/`.
The planned comparisons are in `.scratch/haiku-stress-01/predictions-01.md`.
Use retained records and synthetic cases for the report design and checks.

## What the inventory found

Apparatus (`apparatus/c10`, shared helpers in `apparatus/sanity`):

- [Packet validation](apparatus/c10/common.py) requires live runs to select
  `submitted`. The [reviewer](apparatus/c10/verify.py) distinguishes
  `not_submitted` from `incomplete` evidence, but the
  [batch controller](apparatus/c10/batch.py) counts an unsubmitted live run as
  failed and stops later placements. The [host](apparatus/c10/c10.py) can then
  print a generic launch failure. An experiment that intentionally reaches a
  limit cannot express that expected observation in its live packet.
- Host `session_outcome` copies the container outcome; `binary_status` is
  repeated in several reports. A batch row's `state` can say `reply_lost` while
  its nested `review.outcome` says passed: these describe different observations
  but their names do not make that distinction clear.
- Repeated declarations such as `model_qualified: false`, `approved: false`,
  `loss_surrendered: false` and `unassessed` lists need a consumer and scope
  review. Other apparent constants vary by mode: `witness_scope` distinguishes
  independent fake exchanges from Stewart-owned live captures, and
  `local_iteration_only` distinguishes native iteration from Linux evidence.
- Refusal reasons are flattened in live, rehearse, control and review; withheld
  collection can exit nonzero without a useful sentence. Shared
  [failure reporting](apparatus/sanity/session.py) deliberately suppresses
  arbitrary exception text because it can contain credential-bearing evidence.
  Useful diagnostics need controlled reasons and context, preserving that
  protection.

Stewart's own replies (specification only):

- The sealer is reported in six fields (`headline.sealed.by`, `seal.actor`,
  manifest `seal.actor`, submit `sealer`, re-entry `sealed_by`,
  `effects.seal`). Sixteen status `condition` values restate run endings and
  closure states; `awaiting_confirmation` and `log_damaged` are each a
  condition and an `unfinished_reason`; the confirmation token appears in
  three places.
- Reason names that do not tell a newcomer what went wrong: `input_invalid`
  against `fields_invalid` and `range_invalid`; `stale_entry`, `stale_view`
  and `stale_preparation`; `capture_failed` against `capture_unverified`;
  `affirmation_missing`; `archive_moved_or_copied`; `invocation_id_reused`,
  which no section explains.
- Tokens the manager types back carry prefixes (`cf1.`, `mp1.`, `loss.`) whose
  meaning lives only in INTERFACE 2.3.

## Design requirements

1. Distinguish execution, evidence sufficiency, the experimental finding and
   remaining actions. A supported negative finding can complete a block. A
   mechanism not exercised leaves its question open; missing evidence does not
   establish absence. These findings do not qualify a model or grade an answer.
2. Give each fact an owner and observation boundary. Before-close and
   after-close status are different observations. Derived views identify their
   sources; repeated bindings must serve a consumer or an independently usable
   artifact. Preserve witness scope and uncertainty wherever a claim is read.
3. Human and machine views convey the same facts. The ordinary report explains
   the finding and links directly to supporting evidence; it replaces competing
   summaries instead of adding another layer above them.
4. Name each remaining action, its responsible actor and the authority it needs.
   An operator action is not automatically a request to the principal. A report
   grants no permission to repeat, continue, close or spend.
5. Report controlled reasons that identify what went wrong and where. Retain
   original evidence and protect private diagnostics. Version changed interfaces
   and update their consumers together without compatibility shims or rewritten
   historical receipts.

## Apparatus work

The first deliverable is a small set of concrete block proposals and matching
result examples, with a proposed simplification of the apparatus. Use those
examples to choose the design before fixing new schemas. This work uses current
operating rules and offline checks; it needs no new model placements or grant of
agent autonomy.

### 1. Define the exchange

- [ ] Define the block proposal: narrow question, comparison, observations that
  distinguish possible outcomes, budget and placement limits, permitted
  variations and stopping rules.
- [ ] Define its return: actual observations, what they establish, unexercised
  or ambiguous comparisons, reported/estimated usage and calculated cost,
  remaining actions and direct evidence references. Keep independently observed
  billing distinct. Account for every planned trial, including those not started.
- [ ] Include collection, evidence review and custody disposition in the block's
  account. Show unfinished work explicitly; a scientific finding cannot conceal
  an open custody obligation. Represent who acts under current authority without
  deciding future delegation.

### 2. Choose the reporting structure

- [ ] Map report producers, consumers, observation times and bindings across
  launch, session, audit, review, export and control. Identify facts that must
  travel with a standalone artifact and fields nothing consumes.
- [ ] Compare local vocabulary changes, one authoritative report derived from
  retained observations with human and machine views, and replacement of the
  batch controller with a runner that understands experiment blocks. Use the
  concrete examples to assess each shape's complexity, recovery behavior and
  ability to distinguish expected observations from failures. No shape or set
  of outcome words is selected in advance.
- [ ] Record the chosen design and the producer/consumer changes it needs.
  Separate reporting from decisions about which work may proceed. Implement
  under current operating authority; leave additional delegation for the
  autonomy agreement. Any change to product obligations remains the principal's
  decision.

### 3. Make the outcomes distinguishable

- [ ] Work the proposal and report through an ordinary submission, a planned
  limit stop, an unexercised mechanism, missing evidence and withheld export.
  Include lost replies, later custody observations and an actual apparatus
  failure so the report cannot silently merge them.
- [ ] Specify the observations and checks before running a comparison. Pair
  each claimed check with a firing control, a differing case and an invariance
  case. A correct answer obtained without the mechanism under study must remain
  unexercised for that mechanism, as with the retained pagination trial.
- [ ] Use retained or synthetic observations to demonstrate a narrow finding
  without an independent reader judging a long answer. Name any interpretation
  that still needs a reader or designer; do not turn it into a mechanical grade.

### 4. Implement and verify end to end

- [ ] Implement the chosen reporting path across producers and consumers,
  including `check_rehearsal`, `check_review`, `check_operations`, command
  output and the apparatus README. Preserve actual reasons, explicit unknowns,
  authority boundaries and immutable evidence through later collection.
- [ ] Run and retain the applicable
  [DEVELOPMENT checks](DEVELOPMENT.md#what-to-run-for-what-you-changed): C10
  tests, shared sanity-launch tests, driver self-test, changed run/reviewer/
  operator behavior through the native fake provider, and the link check.
  Apply additional rows if the implementation touches other paths.
- [ ] After committing, have the principal run the matching retained Linux
  rehearsal. Review actual counts, controls, skips and failures, and resolve
  outstanding work. Native checks alone do not qualify the changed apparatus.

## Product vocabulary

- [ ] Read-only: map which driver cases, service tests and apparatus checks
  assert each duplicated field and opaque reason, so the decision list names
  what each rename costs. No edits. An author who reads the service must not
  later edit the driver in that session.
- [ ] Put a short decision list to the principal: collapse the sealer to one
  field plus manifest; make `condition` either the single state word or a
  pure derivation; decide whether a limit stop or interruption should show in
  the rendering, which CONTRACTS now keeps free of operating history, since the
  stress runs showed a manager cannot tell a finished return from a cut-off
  one; rename the reason triads and the opaque reasons; give typed-back tokens
  readable prefixes (for example `confirm1.`) or print the
  whole command instead. Each item names what it costs managers already used
  to the words.
- [ ] After decisions: CONTRACTS, INTERFACE, QUESTION-FORMS and CLI help
  change together; service and help follow; the driver is updated from the
  specification by an author who has not read the implementation
  ([AGENTS](AGENTS.md#preserve-independent-evidence)); the applicable rows
  of [DEVELOPMENT](DEVELOPMENT.md#what-to-run-for-what-you-changed) run,
  then the scheduled Linux suite.

## Completion

The apparatus portion is complete when a block has a coherent proposal and
evidenced result, execution and findings remain distinct, remaining actions are
usable, and the implemented path passes its local checks and retained Linux
rehearsal. Complete the plan when the product vocabulary decisions are also
implemented and checked, with the specification, help, driver and apparatus in
agreement. Move enduring behavior and reasons into their owning documents,
record product renames in the interface version history, give unfinished work
an explicit disposition, and delete this plan.
