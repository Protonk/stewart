# Product response vocabulary

Make Stewart's manager-facing replies easier to understand without obscuring
custody, authority or uncertainty. This plan owns the remaining product vocabulary
decisions and implementation. [CONTRACTS](CONTRACTS.md) owns decided behavior;
[INTERFACE](docs/INTERFACE.md) and [QUESTION-FORMS](docs/QUESTION-FORMS.md) own the
exact interfaces. The principal decides changes to product obligations and what
participants can express. Historical receipts retain their original schemas.

## Decision inputs

The specification inventory identifies these candidates, not settled renames:

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


The turn-limit examples in `.scratch/haiku-stress-live-01` and
`.scratch/haiku-stress-live-02` also show why a reader can mistake an unfinished
answer for a finished return. Whether operating history belongs in the product's
rendering remains a product decision. The apparatus reporting contract is owned
separately by [Experiment reports](apparatus/c10/REPORTING.md).

## Remaining work

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

Complete this plan when the principal's vocabulary decisions are implemented and
checked, with the specification, help, service, driver and apparatus in agreement.
Move enduring behavior and reasons into their owning documents, record product
renames in the interface version history, give unfinished work an explicit
disposition, and delete this plan.
