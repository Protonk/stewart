# Product response vocabulary

Make Stewart's manager-facing replies easier to understand without obscuring
custody, authority or uncertainty. This plan owns the remaining product vocabulary
decisions and implementation. [CONTRACTS](CONTRACTS.md) owns decided behavior;
[INTERFACE](docs/INTERFACE.md) and [QUESTION-FORMS](docs/QUESTION-FORMS.md) own the
exact interfaces. The principal decides changes to product obligations and what
participants can express. Historical receipts retain their original schemas.

## Decision inputs

The read-only implementation and evidence map,
`.scratch/rapid-iteration-01/VOCABULARY.md`, identifies producers, consumers,
native tests and independent-driver cases for
the candidate fields, reasons and handles. It establishes these distinctions:

- Seal actor appears in manager summaries, detailed records, durable manifests
  and auditor replies. `effects.seal` instead describes the current operation's
  effect or uncertainty. Consolidating names does not eliminate those roles.
- The 17 manager status conditions are already derived from underlying records
  and current observations. A single success word must not hide run, submission,
  delivery or closure facts.
- Invalid-input and stale-reference reasons identify different repair targets.
  `invocation_id_reused` is explained in INTERFACE 6.3 and in the refusal message.
- Human replies already print complete shell-quoted next commands. Handle
  prefixes also participate in binding checks; a rename affects consumers and
  exact-byte evidence, not just presentation.

The turn-limit examples in `.scratch/haiku-stress-live-01` and
`.scratch/haiku-stress-live-02` also show why a reader can mistake an unfinished
answer for a finished return. Whether operating history belongs in the product's
rendering remains a product decision. The apparatus reporting contract is owned
separately by [Experiment reports](apparatus/c10/REPORTING.md).

## Remaining work

- [ ] Principal disposition of `.scratch/rapid-iteration-01/DECISION-BRIEF.md`:
  retain custody and reason distinctions; defer broad field/reason/prefix
  renaming pending a concrete reader benefit; retain the product-rendering
  question for manager-consumption work. These are recommendations, not adopted
  product decisions. If no vocabulary change is selected, dispose of this plan
  explicitly rather than leaving an assumed rename task.
- [ ] For selected changes, name the reader/operator benefit and exact interface
  cost using the inventory. CONTRACTS, INTERFACE, QUESTION-FORMS and CLI help
  change as applicable; service and help follow; the driver is updated from the
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
