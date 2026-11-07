# Response vocabulary

Make what Stewart and its apparatus report readable without the appendix: a
reader should tell at a glance whether something failed, whether the result is
an expected shape, and whether an action is theirs to take. Trim fields that
nothing consumes, report each fact once, and leave the scheme easy to extend or
simplify. Product vocabulary is owned by [CONTRACTS](CONTRACTS.md) and
[INTERFACE](docs/INTERFACE.md); apparatus vocabulary by
[the apparatus instructions](apparatus/c10/README.md). Historical receipts and
retained evidence keep the words they were written with.

## Why

During the stress one-offs a live launch whose audit legitimately ended at its
turn limit printed `"outcome": "failed"` and `Launch or observation incomplete;
inspect retained records and status before another action.` while the
container record said `observed_review_required` and the evidence was intact.
The principal read it knowing what it meant, but a newcomer would have asked
whether the run had failed. The same pattern recurs across both surfaces.

## What the inventory found

Apparatus (`apparatus/c10`, shared helpers in `apparatus/sanity`):

- `observed_review_required` is the unconditional live session outcome; an
  expected `not_submitted` audit still counts as `failed`, fails the batch
  guard and prints the catch-all error. A correct `withheld` collection exits
  nonzero with no sentence. Every `ValueError` in live, rehearse, control and
  review is flattened to one sentence, so the actual reason never reaches
  the operator.
- The same fact appears twice: host `session_outcome` copies the container
  `outcome`; a batch row's `state` can say `reply_lost` while its nested
  `review.outcome` says passed; `binary_status` is repeated in four records.
- Fields that are always constant: `loss_surrendered: false`,
  `model_qualified: false`, `model_calls`, `local_iteration_only`,
  `approved: false`, `spending_authorized: false`, the four `connection
  status` booleans, `witness_scope` and `unassessed` strings.

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

## Principles for the change

1. One fact, one field. Derived views such as `headline` may remain, but they
   name the field they derive from.
2. An expected shape is not a failure. Outcome words separate "finished as
   planned", "finished, your action is next" and "something broke", and the
   accompanying sentence says which action.
3. Anything printed for a human says what to do next or is removed. Anything
   consumed by code is listed as such, and changes to it are versioned.
4. Reasons are named by what went wrong and where, in words a reader can act
   on without the appendix.

## Decision

The principal agreed to split the work. The apparatus vocabulary changes now,
under its own checks and one retained Linux rehearsal. The product vocabulary
waits for the rapid-iteration architecture choice, since that choice may
reshape the manager CLI and the auditor envelope, and renaming twice is the
one way to pay twice. One product task is pulled forward because it is
read-only and cheap: an inventory of which driver cases, service tests and
apparatus checks pin each duplicated or opaque field. The agent that performs
that survey must not later edit the driver if it read the service.

## Tasks

Apparatus first; it changes under its own checks and the retained Linux
rehearsal, with no product decision.

- [ ] Replace the live outcome words. Host and container outcomes become
  `completed`, `operator_action_needed` (expected unsubmitted or withheld
  states, naming the audit and the action) and `failed`; `error` carries the
  actual reason instead of the catch-all. Stop flattening refusal reasons.
- [ ] Remove duplicated and constant fields listed above, or move them into a
  single `bindings`-style block that a reader can skip. Give each report a
  new schema version; do not rewrite retained records.
- [ ] Control replies carry one sentence stating the next operator step
  (for example "closed; collect when ready", "awaiting your confirmation:
  close --confirm cf1.…").
- [ ] Change code-consumed values together with their consumers: update
  `check_rehearsal`, `check_review`, `check_operations`, the tests and the
  README tables, then the retained Linux rehearsal, which the principal runs.

Product vocabulary follows the split above: the inventory now, the decision
list and the normal cycle after the architecture choice.

- [ ] Pulled forward, read-only: map which driver cases, service tests and
  apparatus checks assert each duplicated field and each opaque reason, so
  the decision list names what each rename costs. No edits.
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

Complete when both surfaces report each fact once, an expected shape never
prints as a failure, every human-facing word states the next action or is
gone, and the specification, help, driver and apparatus agree. Move the
principles into the owning documents, record the renames in the interface
version history, and delete this plan.
