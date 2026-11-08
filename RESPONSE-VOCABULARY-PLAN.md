# Product response vocabulary

Make Stewart's replies easier to understand and give the manager interface and
future auditor runtimes a stable shared vocabulary. Preserve custody, authority
and uncertainty while examining whether every differentiated view or access
restriction earns its complexity. Broad renaming is not the objective; keeping
every existing distinction or spelling is not a presumption. This plan owns the
remaining vocabulary and view-boundary decisions and their implementation.
[CONTRACTS](CONTRACTS.md) owns decided behavior;
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

## Design aim

The principal wants the vocabulary to remain useful while the manager interface
is settled, through Opus testing and a later subscription connector. Establish
common meanings before fixing their presentation or machine spellings. Different
runtimes may supply different evidence, resource observations and stopping
mechanisms; they must not silently redefine an audit, recorded answer, submission,
delivery or close. The intended connector is a design input, not a claim that its
integration or enforcement has been implemented.

The inventory establishes what existing distinctions mean and what changing them
would touch. It does not establish that each distinction belongs in the ordinary
reading, needs a different name in each view, or justifies withholding a fact.
Already deriving a condition and printing next commands does not by itself show
that managers can understand the result without learning the implementation.

Use one account of shared facts with views suited to the task. A short presentation
may omit irrelevant detail, but it must not hide uncertainty, an outstanding
obligation or information needed for the next decision. Keep action authority
separate from read access: observing recorded work does not confer authority to
edit it or attribute it to another actor. Common meanings need not require
identical payloads or a universal serialized record.

## Questions to resolve

| Area | Review question |
| --- | --- |
| Audit, commission, arrangement and run | Which terms identify the undertaking, accepted inputs and one execution placement? Can the same account survive a runtime change without making API requests or conversations its primary units? |
| Answer, preparation, submission and seal | Can manager, auditor and return views use consistent terms for the same version and actor, while preserving that manager sealing is not auditor submission and preparation is not sealing? |
| Operating status | Can the ordinary reading explain work, answer, delivery and closure together, with reasons and next actions, without requiring the reader to memorize 17 condition names? Preserve their independent facts and per-invocation effects. |
| Reasons and recovery | Which exact reasons determine a different repair? Which distinctions are diagnostic detail that can sit beneath a clearer explanation? Evaluate the reason together with effects, uncertainty and the suggested action. |
| Runtime evidence and resources | Separate common facts from runtime-specific observations, their units, scope and provenance. Missing usage is not zero; a calculated price is not independent billing. No common label may claim an observation or guarantee a connector cannot provide. |
| Manager access to recorded work | The archive owner can already read it. What purpose is served by having no supported live answer/conversation viewer? Consider a bounded snapshot view separately from steering, editing or reopening work. |
| Auditor visibility | Keep unselected material, credentials and host coordinates outside the commissioned world. Separately justify hiding family labels or other descriptive metadata; a presentation preference is not automatically an authority boundary. |
| The return's ordinary reading | Can a recipient understand why work stopped, who sealed and what custody remains without reconstructing separate records? Keep operational statements attributed to Stewart and authored content attributed to the auditor. Decide any product package/rendering change explicitly. |

For each differentiated view or denied operation, name the information or action,
the actor, the obligation it protects, and the failure that would follow from
relaxing it. Distinguish an authority restriction, commissioned-world boundary,
consistency requirement, usability choice and current implementation limit.
An undocumented rationale is a question to resolve, not proof that the rule can
be removed. Preserve justified boundaries; propose consolidation where only
historical routing or presentation differs.

## Remaining work

- [ ] Produce a compact shared concept/relationship map from the contracts and
  inventory. Identify terms to stabilize, adapter-specific detail to keep local,
  and proposed changes with their reasons. Avoid introducing a second vocabulary
  that callers must translate back to the first.
- [ ] Work through the view/access questions above using concrete information
  and actions. Recommend which boundaries to retain, relax or leave open, naming
  the contract and evidence cost of each. A role-specific payload is not alone
  a reason for a different name or a ban on read access.
- [ ] Draft ordinary readings and their supporting structured facts for a normal
  submission, a manager-sealed limit stop, an interruption eligible for continued
  work, a partial/unknown delivery, and a closed audit with an explicitly limited
  technical review. Include the already-delivered close case that exposed the
  recovery-wrapper error. Show what a manager, auditor and operator each need
  to understand and do. Keep apparatus review assessments attributed outside
  the product's custody facts. These are design examples, not new outcome promises.
- [ ] Check the proposed meanings against the intended manager interface, Opus
  experiments and a different runtime. Identify capabilities and observations
  that still need evidence rather than forcing them into API-specific terms or
  weakening the common contract. No paid run is authorized by this task.
- [ ] Bring a bounded set of vocabulary, view and access decisions to the
  principal, with before/after readings and exact costs. Defer changes without
  a clear benefit; stability should follow this examination, not preclude it.
- [ ] For selected changes, name the reader/operator benefit and exact interface
  cost using the inventory. CONTRACTS, INTERFACE, QUESTION-FORMS and CLI help
  change as applicable; service and help follow; the driver is updated from the
  specification by an author who has not read the implementation
  ([AGENTS](AGENTS.md#preserve-independent-evidence)); the applicable rows
  of [DEVELOPMENT](DEVELOPMENT.md#what-to-run-for-what-you-changed) run,
  then the scheduled Linux suite.


## Completion

Complete this plan when the principal has disposed of the vocabulary and view
decisions, selected changes are implemented and checked, and the specification,
help, service, driver and apparatus agree. If no change is selected, record that
disposition without leaving an assumed rename task.
Move enduring behavior and reasons into their owning documents, record product
renames in the interface version history, give unfinished work an explicit
disposition, and delete this plan.
