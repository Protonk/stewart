# Product response vocabulary

Make Stewart's replies understandable through the manager interface, Opus studies
and a later subscription connector. This plan owns the proposed vocabulary and
view changes, their implementation and remaining decisions. The proposal below
is ready for review; it is not implemented or a replacement for
[CONTRACTS](CONTRACTS.md), [INTERFACE](docs/INTERFACE.md) or
[QUESTION-FORMS](docs/QUESTION-FORMS.md). Historical receipts retain their schemas.

The implementation/test inventory is `.scratch/rapid-iteration-01/VOCABULARY.md`.
Concrete before/after readings, source bindings and review checks are retained
in `.scratch/vocabulary-revision-01`. Those examples are design illustrations,
not executed results. This work has not launched an auditor.

## Shared meanings

| Term | Meaning to preserve across interfaces and runtimes |
| --- | --- |
| Inquiry | The manager's line of questions about a concern; it can contain separate audits. |
| Audit | One undertaking, identified by its reference, with at most one accepted commission and cumulative ledger/limits. A continued run does not create another audit. |
| Commission | The accepted question, selected material, settings and authorization to undertake that audit. Preparation alone has accepted nothing. |
| Arrangement | The exact instructions, capabilities and runtime settings accepted for the audit. Capture of an arrangement does not itself grant authority. |
| Run | One execution placement in the audit. A process or conversation is evidence about its implementation, not another name for the audit. |
| Answer / revision | The auditor's recorded selection and its particular revision. A poor or empty answer remains possible. |
| Preparation | An exact candidate: manager preparation for acceptance, auditor preparation for sealing. Always qualify which; their handles and effects remain distinct. |
| Submission | The auditor's confirmed act of sealing its prepared selection. |
| Seal / actor | The binding of the selection, attributed to the auditor or manager. A manager seal is never called auditor submission. |
| Return / delivery | The sealed package, and its verified placement at a destination. Verification, placement confirmation and any explicit loss surrender remain separate. |
| Close / closed | The operation ending the undertaking, and its completed custody state. A close request can end authoring while close remains unfinished. |

Keep invocation `outcome`, operation `effects` and observed audit facts separate.
Do not rename a completed command into a completed investigation. Keep precise
refusal reasons and opaque handles; their meanings already distinguish repairs
and exact bindings. The 17 manager conditions remain routing summaries beneath
an ordinary account of the facts, not a vocabulary readers must memorize.

## Proposed reply revision

Use `stewart.reply/2` for the changed public reply shapes. Keep control inputs,
archive records, answer and return formats unchanged unless a separately selected
change requires them. No dual-name aliases or historical receipt rewrites.

### Authoring and closure

Add an `authoring` observation to the manager headline and the first re-entry
page. It is `{state, ended_by}`:

- `state`: `not_started`, `open`, `ended` or `unknown`.
- `ended_by`: `seal`, `ordinary_ending`, `limit`, `damage` or `close` when an
  ending is established; null otherwise. These reuse the existing refusal
  vocabulary for the first recorded event that ends authoring.
- A readable ending remains established despite later damage. Without one,
  damaged evidence means `unknown`; with complete evidence, no launch means
  `not_started`, otherwise `open`. Interruption alone does not end authoring.
- This is an observation, not permission to launch or mutate. Every operation
  still checks authority, binding, current state, access and remaining limits.

Replace re-entry `condition` with this object. Its current `closed` means only
that close was requested before a seal; it must no longer imply completed
custody. Manager `condition` keeps its present scope and values. Do not add
delivery/closure diagnostics to the auditor's ordinary re-entry payload.

### Seal attribution

Use `seal.actor` whenever a reply describes who sealed. A reply's seal observation
begins with `{state, actor}`: `state` is `absent`, `present` or `unknown`; `actor`
is `auditor` or `manager` when present, otherwise null. Known absence requires
complete relevant evidence. A readable seal establishes its actor even if later
damage prevents other claims.

| Current public field | Proposed field |
| --- | --- |
| `headline.sealed.by` | `headline.seal.state` and `headline.seal.actor` |
| Manager `data.seal`, currently object or null | Same path, with the common state/actor prefix; retain detailed metadata when present |
| Re-entry `sealed_by` | `seal.state` and `seal.actor` |
| Submit `seal` handle plus `sealer` | A `seal` object containing state, actor and handle; move that case's returned seal metadata into this object |
| `authoring_ended` refusal's seal handle / sealer | The same seal observation, with handle when established |
| Durable manifest `seal.actor` | Unchanged: it records an actual seal, not an observation of possible absence |
| `effects.seal` | Unchanged: it describes this operation's effect, not its actor |

Role/operation-specific detail stays explicit. Manager detail retains time,
revision, manifest identity and unproduced members. A fresh successful submit
keeps its existing time/revision/manifest information within the seal object;
a repeated submit need only return its established seal identity and actor.
No additional manifest read is required merely to make a repeat look like a
fresh submission. Re-entry needs only the common state/actor observation.
Preparation never manufactures an actual seal. A failed publication never maps
uncertainty to absence. The final wire specification must enumerate each case's
keys and ordering before implementation and independent-driver work split.

### Ordinary manager reading

For `status REF`, `run REF` and `close REF`, show one brief account of commission,
run, answer, delivery and closure, followed by qualifications and supported next
commands. It must include the stop reason, actual seal actor, confirmation still
owed, loss or uncertainty when relevant. A later seal must not hide the earlier
limit/interruption. Do not infer submission from a successful run command.
Include a compact account of known cumulative usage and limits, identifying
estimated portions. Add `data.allowances` to close using the same scope and
qualifications as status/run, null before acceptance; do not invent usage when
its evidence is incomplete. Dollar estimates remain apparatus calculations.

Expose that account in `data.summary` as well as human output, derived from the
same facts. Status already has this field; extend it to run/close. It is a
presentation of observations, not an intellectual assessment or a new state
store. Preserve the current observation/revalidation limits; no atomic live-view
or continuously current-state promise is added.

Default human output for those three commands no longer recursively prints all
of `data` after the account. `--details` includes the expanded data as well;
`--json` returns the full structured reply. The flags are mutually exclusive.
`status --archive` keeps its per-reference listing, with expanded entries under
`--details`. Other commands keep their current presentation in this revision.
Failures, uncertain effects, retained diagnostic locations, named losses and
actionable exact handles must never depend on selecting details. Do not advise
repeating a mutation merely to obtain more verbose output.

Label invocation completion as command completion. Replace the generic
`Next: nothing further is needed.` with `Next: no command is supplied.` when
the next list is empty; closure and outstanding obligations come from the facts.
An absent suggestion establishes neither scientific completion nor permission.

### Refusal wording

Keep reason identifiers, including the invalid/stale distinctions. Retain the
already useful messages naming the current version, JSON pointer or supported
repair. Correct the concrete ambiguity in `nothing was recorded`: refused
quotation/edit attempts can have retained raw calls, payloads or diagnostics.
For a known refused citation use `No answer edit was applied.`; for a known
unpublished entry say the entry was not recorded and identify retained effects.
Where publication is uncertain, state that uncertainty instead. Messages and
`effects` must describe the same scope; no blanket wording replacement is safe.

## View and access decisions

| Boundary | Recommendation and reason | Cost / disposition |
| --- | --- | --- |
| Host paths, credentials, unselected material and manager control metadata hidden from the auditor | Retain. They are outside the commissioned world or could expose operating resources. Shared terms do not imply sharing private records. | Existing C1/C20 isolation and disclosure checks remain. |
| Auditor cannot select another audit, claim another actor or edit after authoring ends | Retain. Reading and naming a fact does not grant its mutation authority. | Preserve binding, ordering and stopping controls. |
| Family ID/version hidden from the auditor | Relax. It describes instructions already supplied; the inventory found no distinct custody or authority reason to hide the label itself. Keep the manager's selection rationale, inquiry label and varies note private unless commissioned as material. | Principal decision. Expose `family` in first-page re-entry and the auditor prepare reply, using the captured value. Update C20 visibility expectations; instructions/tools are otherwise unchanged. No claim that the label improves reasoning. |
| Manager lacks a supported live answer/conversation viewer | Treat as current product scope, not an inherent prohibition on reading. Owner-readable records do not by themselves establish a safe supported viewer. | Defer implementation to manager-interface design. A future read-only, revision-bound view must specify snapshot/partial-data behavior and must not grant steering, authoring or reopening. |
| Standalone return omits operating history | Keep its format in this revision; improve the live manager reading now and retain the assembled study account. The authored answer must remain distinguishable from Stewart's observations. | A product companion account remains a manager-consumption decision. Adding it changes package membership, verification and timing; it cannot retroactively claim later delivery or closure in an earlier seal. |

The family-label relaxation is the proposed change to participants' visibility.
It needs the principal's choice before the corresponding contract and tests
change. The two deferred manager surfaces are explicitly open product questions,
not claims that custody requires their permanent exclusion.

## Runtime stability and validation

Keep the meanings above common across the current API runtime, Opus studies and
the intended subscription connector. Do not create a generic authentication or
resource schema speculatively. Current cumulative allowances retain their units
and reported/estimated distinction. A future runtime must state what it can
observe, charge and enforce; absent observations cannot become zero usage.
Calculated cost, quota consumption and independently observed billing remain
different claims. A different runtime may require new explicit details without
changing the meanings of submission, seal, delivery and close.

The worked readings cover normal submission; a manager-sealed limit stop;
interruption with an eligible continuation; partial delivery; unknown membership;
an already-delivered ordinary close; a close-created delivery awaiting confirmation;
and closed custody with incomplete apparatus review. They identify manager,
auditor and operator needs without importing apparatus review judgments into
product state. They are the proposed behavior to check, not a usability finding.

## Remaining work

- [ ] Principal disposition of this concrete revision, including the family-ID
  visibility change and explicit manager-surface deferrals.
- [ ] Freeze the exact `/2` schemas and observation rules in CONTRACTS/INTERFACE,
  revise forms/help where needed, and implement the selected change. Root has
  read service code; an independent author must change the driver from the
  specification alone under [AGENTS](AGENTS.md#preserve-independent-evidence).
- [ ] Update service producers, native assertions, driver expectations and the
  C10/sanity consumers together. Preserve old reports and their source bindings;
  do not adapt historical receipts to the new interface or accept both shapes
  through a compatibility shim.
- [ ] Check actual observer consistency and refusal/recovery behavior, including
  close requested before sealing versus completed close, uncertain publication,
  loss surrender and already-delivered closure. Use the existing firing controls,
  differing cases and invariances; extend where the revision creates a new risk.
- [ ] Run the applicable [DEVELOPMENT checks](DEVELOPMENT.md#what-to-run-for-what-you-changed):
  link check, both cargo configurations, driver self-test/list and affected
  apparatus checks. Retain outputs. Supply the commit and host Linux commands;
  the changed product/apparatus remain unqualified until the required suites.
- [ ] After the bounded Haiku vocabulary check, disposition any concrete repairs,
  stabilize the selected terms and close this plan. Haiku cannot establish human
  manager usability from replies it never sees; retain attributed readings and
  offline lifecycle checks as distinct evidence.

## Completion

Move selected enduring meanings and behavior into documentation and tests, record
the interface version change, and give deferred access/package work an explicit
owner when manager-consumption work is selected. Retain evidence, account for any
unresolved checks and delete this plan once its selected work is complete.
