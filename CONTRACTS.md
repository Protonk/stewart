# Stewart's decided contracts

This document states the behavior Stewart is decided to have, with the status
of each contract. It is maintained guidance: product code and tests must stand
without the plans and inquiry reports that produced these decisions, and this
document does not route readers to them. Where an inquiry report is cited for
evidence, the citation names the commit at which the report was recorded, so
the citation stays valid after the report retires.

Status markers:

- **Implemented.** The Python implementation exhibits the behavior and its
  tests protect it.
- **Implemented in Rust.** The separately scoped successor implementation
  exhibits the stated behavior; its user documentation states qualified limits.
- **Decided, departure.** The behavior is decided and the Python implementation
  does not exhibit it. The successor implementation realizes it; the Python
  behavior is the control in the successor's acceptance evidence.
- **Documentation.** The behavior is retained; only its limits need stating.
- **Declined.** Considered and not adopted, with the reason, so later readers
  recover the intent rather than infer it from omission.
- **Deferred.** Carried to a named later decision without being decided.
- **Proposed.** A completion the coordinator wrote under the decided
  principles after independent review, awaiting the user's confirmation. It
  is not relied on until marked decided.

The Python implementation is the reference baseline. Its production source is
unchanged since commit `6582df2` and receives no further behavior changes;
previously accepted corrections are realized in the successor. Evidence for
the decisions below is recorded in `STATUS-INQUIRY-FINDINGS.md` and
`CUSTODY-AUDIT-FINDINGS.md` at commit `356dc58`, with run records under
`.scratch/status-inquiry/` and `.scratch/custody-audit/` kept outside Git under
DEVELOPMENT.md's retention rules.

## Principles

Decided 2026-10-24. These govern how the contracts below are read and how new
ones are judged.

**Stewart acts only on what was judged.** A closing evaluation authorizes the
removal of what it judged, and its record freezes that judgment. Material the
evaluation did not judge is not removed on the strength of the command that
started it. This has always governed the checkout and claimed resources; the
close rules below apply it to every surface close removes.

**Refusals are limited to Stewart's own claims, the acts it may perform, and
the obligations it has undertaken.** A refusal is justified by one of three
grounds: a specific false custody claim Stewart would make by proceeding; an
act Stewart may not perform, such as following a planted link, overwriting an
exclusive destination, or destroying material it holds no right to dispose of;
or an obligation Stewart has undertaken and not discharged. Discomfort with
incomplete evidence is not a ground; it warrants qualification. The legitimate
refusals are: declining to vouch for bytes it cannot verify, while still saying
where they are; declining to follow a planted link or read a special file;
declining to destroy an exclusive destination, another audit's live use, or
material the closing evaluation did not judge; and conditioning Stewart's own
claims, such as requiring a disposition before publication under its custody
claims. A refusal whose next step cannot be performed inside Stewart is suspect
unless it names the external authority or commitment it honors. Stewart treats
the commission as authorizing the manager to receive the auditor's return;
adjudicating a right to receive is outside its model, and was considered as an
addition and declined.

**Close offers opportunity, not preservation.** Close deliberately ends private
custody; retention and export decide what survives it. Close guarantees that
the manager had a working opportunity to keep what it removes, not a nominal
one: each removed surface matches a capture that retention or export could
have kept, duplicates session-held material that could have been kept the same
way, belongs to a category declared disposable in advance whose identity the
closing record freezes and never describes as reviewed or declined, or is
surrendered by name. Where the only preservation path failed, the loss is
recorded as a loss despite an undertaking, never as a decline. Regenerability
is never a ground: a digest proves what bytes to expect, not the ability to
produce them.

**The manager controls what survives by default; requesting close does not
cancel undertaken obligations.** That control does not extinguish obligations
Stewart has undertaken concerning particular material: a resource Stewart did
not create is never claimed for disposal; another audit's live use keeps a
resource; retention and export copy bytes to their destinations and never
reference the session, so a retained outcome's promise of inspection does not
depend on the session surviving; uncollected auditor work is not destroyed
without an explicit discard naming it; and a preservation the manager began
and Stewart recorded is completed or explicitly surrendered before conclusion.
Clarified 2026-10-25: completed close must not conceal unfinished audit
operations. Completed retained or exported products may survive independently;
an interrupted close remains unfinished, with its failure and recovery visible.
Releasing a resource claim when the resource changed concerns the scope of the
authorized act, not a promise to the manager's earlier self. Human auditors,
principals, material providers and later readers acquire no retention rights
from their roles; any they hold come from promises, authority limits or
reliance actually recorded. Updated 2026-10-25: a provider's condition or a
manager's delegation limit concerning identified custody material can be
recorded as a narrow, attributed hold with explicit release, below. This
replaces the hold's dependency on the general manager-resource service,
which is deferred. It is a record the manager makes, not a veto to imagine.
Stewart's promises to the auditor are process promises: raw capture before
interpretation, a disposition of every gap, and attribution
that is never turned into a verdict.

**Liberal in handing over, conservative in destroying.** Stewart gives the
manager verified material with its qualifications attached, and withholds
destruction of material the manager has not judged. The manager's judgment,
not Stewart's, decides what the material means.

**A bounded commission and structured return are the product relationship.**
Clarified 2026-10-25. Stewart serves people who want to ask narrow questions
and receive answers to those questions, including accounts of missing evidence
or incomplete work. Routine steering, live inspection and general agent
supervision are not product objectives. Their availability in surrounding
harnesses, or their usefulness in developing Stewart, does not justify
reproducing them in the product. Judge proposed intervention facilities by a
specific commission or custody need. This preserves the auditor's investigative
latitude within the assignment; it does not prescribe a narrow method or an
artificially small body of context. The exceptional intervention policy remains
open, and this principle alone removes no existing operation or record.

**Stewart remains agnostic about audits' intellectual utility.** Clarified
2026-10-26. This governs development as well as the product. Stewart's major
intellectual influence belongs in its supported question types and constrained
audit space. It does not judge whether an audit was worth undertaking or whether
its outcome is intellectually valuable. Auditor and manager judgments remain
their own and retain their attribution.

Answer requirements must let participants express, inspect and contest the
responses the commissioned question permits, including no supported finding,
missing evidence, an unresolved premise or a proposed reframe. Restrictions
that exclude or privilege substantive outcomes require explicit deliberation
as design choices, even when introduced through formatting or schemas.
Development may examine lost qualifications, unsupported promotions and the
pressure a format places on authors or recipients. Agreement with a preferred
or historical outcome is not the measure of a successful answer interface.
This principle selects no particular answer schema or custody policy.

**Recording a commission does not itself promise replay.** Agreed design
direction, 2026-10-25; candidate for a core commitment. A commission record
explains the accepted question and its selected material. It does not by itself
undertake to reconstruct an executable audit, reopen it or provide another
invocation. The manager remains responsible for being able to construct a new
question, including an identical one. Existing capture and preservation
undertakings still apply. The user's preference is at most one audit retry
facility, potentially none; explore the zero-facility, single-undertaking
("trap door") design first. A restart-from-start convenience remains open,
not approved, and retaining records does not imply it. The full staged
construction/review/release/run relationship was reconsidered without giving
existing code or tests a presumption of continued product responsibility. The
user subsequently selected no dedicated successor program executor, below;
the possible audit restart convenience remains undecided.

**Standard commission receipts support manager recall.** Decided direction,
2026-10-27; **Implemented in Rust** for the bounded commission-input delivery
leg, with integration into the later audit service still pending. A manager
supplies copies of material for which it is responsible. Stewart promptly returns
detailed receipts for the commission and accepted input selection, independently
of waiting for the auditor's result. Those receipts use a consistent, documented
presentation and access route, with an explicit commission reference. A manager
whose conversation has been compacted can use them to recover the original
question and supplied material, including for constructing a competing answer.

The account binds the original question/instructions, selected material identities
and their supplied view, relevant Stewart-added guidance or transformations,
and recorded grants and limits. It provides a supported way to inspect the
corresponding retained bytes; a filename or digest alone does not supply them.
Distinguish the requested selection, what Stewart recorded accepting or making
available, and any unconfirmed or incomplete step. Manager edits after handoff
do not alter this account, and missing or invalid originals are diagnosed rather
than replaced from a live worktree. It describes the commission, not what the
auditor has read, understood or is currently doing; it grants no live access.

The manager remains responsible for retaining a receipt/reference or knowing the
standard access route. Losing both may require additional reconstruction work;
Stewart does not promise general memory recovery or guess an audit by recency.
The manager need not retain the original conversation to inspect the commission.
The commission-input leg's receipt schema, presentation, explicit location and
acknowledgment boundaries are documented in its user guide. Audit-service
integration and retention after audit closure remain for design and qualification. The interface must
be usable while the audit is live. This input-receipt decision does not settle
custody of the auditor's partial answers or promise executable audit replay.

**Prefer inexpensive assurance that supports manager judgment.** User design
lean, 2026-10-27. Look for bounded handoffs through trap doors with clear receipts:
the manager supplies copies it is responsible for, receives detailed receipts
immediately, and eventually receives a result or error. Favor inexpensive,
inspectable facts on which a competent manager can decide how to proceed,
without making Stewart supervise that judgment. Faster runtime and more routine
use of audits are desired effects, not established findings. This lean chooses
no new automatic disposal, retry or delivery mechanism. Errors still account for
partial effects and unfinished custody obligations; an error does not discharge
them. Concrete eventual-delivery and failure guarantees require a qualified route.

**Incomplete Stewart operations remain Stewart's responsibility to account
for.** Clarified 2026-10-25. Restricting intervention increases the importance
of a supported account and disposition of interrupted custody work, particularly
for agent-managers likely to improvise repairs when the interface leaves a gap.
Do not make editing private state, deleting evidence or guessing whether an
operation ran the expected recovery path. Complete an existing undertaking
within its recorded authority where possible, or expose its unresolved state,
limits and an authorized disposition. A diagnostic that merely leaves the
manager to improvise private-state repairs is an interface gap, not a supported
resolution. This is not a guarantee that lost bytes can be recovered.
Completing custody work grants no fresh investigative
execution; uncertainty cannot be replayed. Nor may a collection of retry
facilities be accepted merely by calling them recovery. Concrete mechanisms
and their supported failure cases still require design and qualification.

**Investigative effectiveness and seamless operation are distinct aims.**
Recorded 2026-10-25 as a design tension. An effective audit gives the auditor
seemingly transparent access to the materials used to construct its question,
conditioned by manager selection. Seamless operation is easier when Stewart
can isolate a constrained, static slice without nesting or recursive
expansion and make precise promises about it. These aims can trade off in
unexpected ways. A smaller or more isolated slice is not by itself evidence
of a more effective audit; broader access is not by itself evidence of better
operation. Evaluate both for the particular commission and make the selected
material and its limits intelligible. This tension grants no additional
access and decides no workspace or history mechanism.

## First successor leg: commission-input acceptance

Selected 2026-10-27. **Implemented in Rust**, locally qualified on Apple Silicon
macOS. The separate [commission-bundle guide](successor/README.md) states the
interface and limits; this is not the full successor audit service.
The first usable successor leg accepts a bounded
commission-input selection, issues detailed receipts and supports independent
verified readback of the original undertaking. Accepted materials must remain
recoverable without the originating process. Its acceptance promise, responsible
custodian and accounting for incomplete intake must be explicit before the write
interface is implemented.

The user selected manager-custodied delivery: a verified, self-contained bundle
is delivered into explicitly designated storage, and the named manager/custodian
is responsible for preserving it thereafter. Acceptance means the entire
selected original undertaking and its detailed receipt are present and verified
at that destination; printing a path or digest alone is insufficient. It does
not mean an audit has launched or a result is owed through this intake slice.
C neither silently deletes delivered material nor undertakes a separate private
retention service. Independent readback verifies retained bytes, diagnoses loss
or damage and never silently substitutes live sources.

Incomplete intake retains partial bytes and diagnostics. Its known reference
supports completion within the original intent or explicit attributed
acknowledgment/disposition as incomplete, with custody of partial material kept
at the designated destination. Neither path overwrites records, conceals unmet
acceptance nor grants deletion or another investigation. Unrecorded or unverified
disposition remains unresolved. A lost success reply is recovered from the
existing verified record, not by guessing whether an operation ran.
An acknowledged incomplete intake still exposes its valid recorded request and
selection for inspection. Acknowledgment changes the outcome, not the original
undertaking. Damaged intent keeps its diagnostics rather than an invented request;
incomplete inspection does not promise complete raw originals or acceptance.

This intake and readback form one useful feature. A separate reader preview is
not commissioned or required first. This supersedes the earlier status-first
implementation ordering for this leg, not the substantive status obligations of
the later audit service. Commission receipts describe original question, inputs,
guidance and declared grants/limits; they do not claim auditor activity or settle
future result representation, inspection or custody.

Qualification pairs manager recall after a context discontinuity with a bounded
self-audit and later inspection of its actual return without the original writer
or working environment. An explicitly responsible existing custody process
preserves that return. This is not a result-custody capability
of commission intake. Record what the investigator needs, what artifacts support
and what remains inaccessible or unsupported. Those observations inform whether
a result reader preview, new producer-and-reader slice, transition tool or no
additional feature is justified. Successful result inspection is not an acceptance
criterion for the commission-input leg. No future reader or result schema is
selected merely to stage this inquiry.

## Successor answer construction and atomic artifact edits

Agreed design direction, 2026-10-27. **Decided, departure; implementation and
qualification pending.** The auditor-facing submission tool controls construction
of the deliverable so avoidable invalid artifact arrangements cannot become
submitted results through supported operations. It manages artifact identity,
explicit edits, generated mechanical metadata and the exact recorded selection;
the receiving boundary enforces the requirements too. This is mechanical
authority, not authority to assess the answer's intellectual value or silently
rewrite its content. Exact protocol and representation remain for design.

After adding an artifact succeeds and the helper exits, the exact selected bytes
and their identity remain recoverable in Stewart while the audit remains open.
Successful addition therefore undertakes more than validation or process-local
staging. The originating helper need not stay alive to recover the selection.
A source path or digest alone cannot fulfill this promise.

The user clarified that this is an opportunity to avoid draft-status lifecycle
stages. The auditor edits recorded elements through add, replacement using an
existing element's handle, and delete. Seek atomic operations: newly stored bytes
that have not yet been hashed and recorded belong only to a narrow internal
mechanical window, not a manager- or auditor-operated draft phase. Each successful
operation establishes its recorded change; the tool refuses invalid operations
early and provides informative failures from which the auditor can recover.
The interface does not require a separate promotion of the same artifact bytes
from disposable authoring state into custody.

This undertaking is independent of manager delivery and retention after closure.
It grants no manager access to live authoring material and selects no audit
execution or restart facility. Add/replace/delete is the authoring direction;
it grants no authority to rewrite exclusive historical receipts, release a hold,
or erase failure evidence. Existing partial-work, hold and interrupted-operation
obligations remain. Supported interruption cases, handle/version semantics,
storage/access mechanism, physical reclamation of replaced/deleted material,
delivery and treatment at early close remain to be specified and
qualified. No general draft-history service or runtime implementation is
commissioned by this direction.

**Normal submission ends editing.** Accepted 2026-10-27; implementation and
qualification pending. Preparation verifies the current recorded answer and
artifacts, generates an inspectable manifest, and issues a handle bound to that
audit and exact collection revision. Preparation is independently callable and
leaves editing open; it creates no authoring lifecycle status. The auditor need
not manufacture the envelope, manifest or its hash.

Submission requires that issued handle and defaults to a dry run. Only an explicit
true submission argument requests the effectful operation. A subsequent edit
makes the earlier preparation stale; submission refuses informatively rather
than silently selecting newer material. Revalidate the exact selected bytes and
bind the last check to publication so an edit and submission cannot race past
one another. A dry run does not fix the answer or publish a submission.

Successful actual submission atomically fixes the selected result and ends further
add/replace/delete edits of that answer. The same handle identifies the same
submission after a lost reply; an identical confirmed repeat returns its recorded
outcome without creating a second submission. Uncertain or damaged records keep
their diagnostics and require supported resolution, not guessed repetition.
Submission is not a second upload or promotion into custody, and it does not
establish manager delivery, terminated processes, safe environment retirement or
completed audit close. Those responsibilities remain separate. Exact handle
issuance/storage and callable or tool-interface syntax remain mechanism choices;
no call-stack trick or mandatory nesting of preparation inside submission is
required. Manager-side simplification is deferred to later discussion.

## Handoff and audit-owned facilities

Agreed direction 2026-10-25. **Decided, departure.** The manager retains
authority over the commission and disposition; Stewart manages the audit's
material from handoff through authorized closure. After handoff, manager
access to the auditor's live material is to be very restricted and the audit
process abstract to the manager. Missing information can be surfaced through
the auditor's structured return. Later manager edits must not silently alter
what the auditor was commissioned to investigate.

Stewart allocates, protects and retires the facilities it supplies for an
audit. A manager's independent preparation workspace has a separate lifetime;
audit close does not grant disposal authority over it. Dependencies on such
workspaces must actually be ended or otherwise secured before their existing
protection can be removed. A working opportunity to keep material covered by
the custody promise must be available through a supported interface wherever
direct manager access is restricted. Retention remains optional except where
Stewart has undertaken a specific obligation, including a hold. Auditor
completion alone does not authorize closure or disposal.

The exact permitted manager operations and enforced access mechanism remain
to be designed and qualified, including a workable stop/collection route.
The current implementation does not establish this manager-side boundary.
No delivery service, new auditor channel, or guarantee that the host's entire
execution environment is immutable follows from this direction.

## Access through explicit grants

Direction selected 2026-10-25. **Decided, departure.** Pursue auditor access
defined positively by the commission's selected material and required
facilities. The preference is to eliminate Stewart's responsibility for a
private-location inventory, if the access arrangement can actually enforce
the required boundary. Creating a new private manager location should not
require updating an audit's exclusions to keep it inaccessible. Deferring
manager-resource creation and disposal does not weaken access protection.

Shared immutable storage must expose only the material the audit is authorized
to read, not the store's entire contents. The manager-side restriction remains
separate: receiving and inspecting the authorized captured return must not
implicitly reopen the auditor's live material to manager intervention.

Eliminating the inventory requires qualification in the supported harness,
including shell and file-tool routes, useful authorized access, unselected
and neighboring material, and private locations created after launch. Settings
construction alone is not qualification. A narrowly scoped inventory remains
an available fallback if the evidence requires it; its reason and limits must
be stated, without restoring general manager-resource management. The mechanism
and its enforcement are not established by this decision. Permitted auditor
tool use still needs actual access/effect bounds; the later no-executor decision
removes Stewart's separate program runner, not those obligations.

## General manager-workspace service

Decided 2026-10-25. **Deferred.** General creation and disposal of manager
worktrees, branches and temporary directories is deferred from the successor
transition. The preference is toward isolating and possibly removing this
service instead of advancing it; deferral is not a commitment to implement
it later. Reconsideration requires a separate need and commission, in the
optional later implementation stage or a subsequent program.

Audit-owned allocation remains in Stewart. So do required custody records of
retention/export and their failures, and whatever dependency and access
protections the chosen arrangement still needs. This does not require keeping
the general resource API as the mechanism for those duties. The reason for
deferral is the separation between audit custody and management of the
manager's own work, not the subsystem's size or an assumption that nobody uses
it.

Python's resource service remains frozen as implemented. Historical resource
records are preserved; successor interpretation follows the bounded evidence
reader contract below and creates no general manager-resource removal claims.
Existing resources can still be serviced by
their Python implementation while available; any manual retirement is outside
Stewart custody. Records are preserved. Closing Python audits does not settle
every resource or unfinished claim: their inventory and supported recovery
must receive an explicit transition disposition before Python is withdrawn.
Historical receipts are never rewritten to achieve that transition.

## Public status contract

Decided 2026-10-23, reader scope narrowed 2026-10-25. **Decided, departure.**
The earlier status-first implementation order is superseded for the initial
commission-input acceptance/readback leg selected above. Status remains owed
for the later operational audit service. The
Python corpus and status behavior supply comparison evidence for the selected
contracts; they do not impose permanent support for every Python private-session
or resource format. Before implementation, name the consumer and supported
record population under the evidence interpretation contract below. The
preservation-first extraction order described in
the findings applied to a Python implementation and is not required when the
successor implements status and close against this document directly.

The contract below is incorporated verbatim from `STATUS-INQUIRY-FINDINGS.md`
at commit `356dc58` (its "Public contract" and "Observation, consumer and
diagnostic ownership" sections, and two closure paragraphs), with heading
levels adjusted. Where it says close retains its existing live-runtime and
live-handoff consequences and consequential observation errors pending the
wider audit, and where it keeps `stewart.closing/1`, the close contract later
in this document supersedes it: close's checks are coverage by the triaged
collection, the surviving live checks are enumerated there, and a closing
record that freezes discard identities is a new schema. The 2026-10-25
manager-workspace deferral also revises the resource rows below; the former
resource-based hold is replaced by the custody-material hold contract. The
bounded reader decision also replaces the unconditional legacy-resource
projection with support justified by an identified consumer and record
population. A field's specified meaning is not a promise to decode every
historical format that once supplied it.
The later no-executor decision also supersedes successor release/run stages
and their action offers in this inherited account. Historical release/attempt
records may be interpreted for a specified consumer under the bounded reader
contract; their existence does not commission a successor executor. Captured
evidence, identity checks and precise failure diagnostics remain required for
supported records. Existing Python operations and unfinished attempts remain
writer-bound under the transition contract.

### Public contract

#### Provenance and schemas

Use `stewart.status/14` for the changed live-session view and
`stewart.status-list/2` for its workspace summary. Do not silently change the
meaning of status/13 or provide an old-view compatibility mode. Preserve
references, explicit lifetime selection and writer-bound action construction.
The outer CLI result envelope remains `stewart.result/3`; its `ok` continues to
mean exit zero, not successful inquiry or an auditor verdict.

A field has the same provenance at every stage. A path from a receipt is a
locator. A validated retained byte sequence is available custody evidence at
read time. Neither establishes current auditor checkout readiness. Safe regular
file/descriptor reads, control JSON decoding, identity checks and capture/member
verification remain required. Immutable-looking filenames do not confer trust.

| Field/group | Decided meaning and treatment |
| --- | --- |
| `audit_id`, `workspace`, `reference`, `session`, `assignment`, `tool` | Keep identities, selected lifetime, supported schema and recorded assignment. Session problems remain explicit. Viewer identity is a present observation of the manager implementation. |
| `assignment_source` | Add the recorded repository/retention identity, prompt commit, workspace-derived prompt path, pinned digest and verified authored prompt text from retained Git. Current status metadata does not include this prose. Validate the commit/blob and digest; show a source diagnostic if unavailable, never a live-worktree fallback. Prose may quote labelled authored Question/Decision excerpts using the shared assignment section reader; JSON retains the full text, not an agent summary. |
| `assignment_limits` | Carry recorded submodule gitlinks and their declared support limit as facts from the prepared session. Preserve the full recorded list in JSON and label any prose truncation. These are not a new task to populate or audit submodules. |
| `stage` | Last supported custody milestone, not a readiness or health verdict. Before a collection use `private_handoff_retained`, `preparation_failed`, `preparation_incomplete`, or `unverified` as supported. Later recognized collections/reviews yield `collected`/`triaged`; an unfinished closing record yields `closing`. Preserve earlier preparation failures in their own field and attention even if later custody exists. |
| `preparation` | Historical evidence and diagnostics: session record, recorded failure, retained runtime preparation, private handoff. Replace `ready` and current availability classifications with record-based states. `prepared_at` remains the session's recorded preparation timestamp, not proof of completed publication. |
| `handoff` | Neutral access to the verified retained private copy, its digest, and recorded public/worktree locators. `private_handoff_retained` means the private copy matches the session pin. It does not say the public copy was published, read, or remains present. Missing and present-but-invalid copies remain different diagnoses. |
| `identities` | Keep pinned prompt/target/session identities and recorded paths. Retain explicit read-time commit-retention verification because it concerns recoverability of held evidence. Remove live worktree existence/HEAD/lock, maintainer dirtiness/HEAD comparison and destination-exists fields from normal status. |
| `coordination`, `launches`, `messages`, `harness_exits` | Keep separate attributed acknowledgments, relayed text, paused-hold/resume records and shell-log observations. Do not parse message prose into new role, activity, callback or completion claims. |
| `collections` | Keep every attempt and captured-report locator. Replace ambiguous `complete` with `receipt_state`: `recorded`, `missing`, `invalid`, or `unreadable`; retain precise problems. `recorded` means the supported receipt was read and identified, not that all report/archive capture succeeded. Report state, captured integrity, gaps and stop acknowledgment remain distinct. |
| `auditor_reported` | Keep declaration-derived values, sources, identities and validation diagnostics. No live-report interpretation and no inference from prose. Omit the empty declaration section from ordinary pre-collection prose; JSON may retain explicit unavailable values. |
| `dispositions`, `retentions`, `releases`, `attempts`, `runtime_recoveries`, `experiment` | Keep recorded progression and verified bindings/captures. An execution grant or absence of a release is not a task queue or readiness assertion. Do not demand success-only fields from failed records. |
| `implementation` | Keep writer/viewer distinction and descriptor-verified writer handoff where offered. This verifies manager code, not auditor activity. Never execute/import recorded code to inspect it. |
| `resources` | For an explicitly supported legacy population and identified consumer, expose recorded associations, identities and diagnostics read-only. This is not an unconditional port of Python resource reporting; unsupported material remains diagnosed, not treated as absent. Ordinary status does not evaluate disposal eligibility. The successor creates no general manager-resource removal claims; close planning and close evaluate only their audit-owned removal scope and its dependencies. No summary confers removal authority. |
| `requests`, `closes`, `manager_storage` | Keep recorded request state, closing history/recovery diagnostics and custody locators. Optional keyed completion records are not promoted into a universal preparation-completion requirement. |
| `attention`, `exit_code` | One authoritative public account of diagnosed record/capture issues and exceptional recorded conditions. Every item has source, stable reason, message and code; preserve useful retained locations and conditional next steps. |
| `outstanding` | Retire this parallel obligation-like channel. Move neutral facts into their sections; real diagnostics into attention; operation conditions into the option that actually needs them. |
| `options` | Replace `next_actions`. Conditional record-supported options, not instructions, a schedule, or a promise that an operation will succeed. Preserve lifetime/operand digests, writer binding, isolated argv, empty env and prerequisites. No automatic execution. |

A later missing collection receipt can coexist with an earlier recognized
collection. `stage` alone must not disguise that situation: the later attempt
and its diagnosis appear explicitly and ahead of neutral prose. A present
invalid/unreadable receipt is never labeled merely partial. The existing
supersession rules for *missing* completed receipts remain; corruption is not
silenced by a later successful record. Workspace rows use the same distinctions.

The following precedence fixes the projection, rather than leaving `stage`
to a health inference. Apply it only to the selected lifetime; an old closing
record must not override a separately identified later lifetime.

| First applicable evidence | Public stage and retained qualifications |
| --- | --- |
| Authoritative unfinished closing record for this lifetime | Existing closing-recovery view, `closing`; missing removed session files do not become a preparation failure. |
| Session identity/schema cannot be interpreted | `unverified`; retain every independently readable diagnostic, and infer no later custody milestone. |
| At least one recognized collection receipt | Choose the latest recognized receipt in the established record order: `triaged` if a valid bound disposition addresses it, otherwise `collected`. Keep later partial/invalid/unreadable attempts explicitly visible and do not let the milestone imply they succeeded. Keep any earlier preparation failure in `preparation` and attention. |
| No recognized collection, valid recorded preparation failure | `preparation_failed`, even if a private handoff was retained before the failure. |
| No recognized collection/failure, and preparation custody needed for the claim is present but invalid or unreadable | `unverified`, with the exact diagnostics. A corrupt failure record is not a valid failure acknowledgment or ordinary waiting. |
| No recognized collection/failure, private handoff matches the pin and required historical runtime custody verifies | `private_handoff_retained`; publication and activity remain unestablished. |
| Required completion evidence is missing, with no recorded failure or integrity diagnosis taking precedence | `preparation_incomplete`: the retained records do not establish that preparation reached private handoff custody. Do not assert that nobody launched or that work never began. |

`preparation.state` is projected independently: valid recorded failure wins as
`failed`, while other corrupt/unreadable preparation evidence remains diagnosed;
without a valid failure, invalid/unreadable required preparation evidence means
`unverified`, missing evidence means `incomplete`, and a matching private copy
with usable historical runtime custody means `private_handoff_retained`.
Phase-specific omissions explicitly explained by a valid preparation failure
remain omissions of an unreached phase, not fabricated corruption. Collections
can advance public `stage` without rewriting that historical preparation account.

#### Attention and options

- **Ordinary no-collection state:** retain the factual absence, empty attention,
  exit 0, and no launch/probe/collect options. No elapsed-time threshold, overdue
  category or inference that an auditor is running or has stopped.
- **Exit-0 wording:** “No issues found in the inspected custody records.” This
  is deliberately narrower than a global “no manager action is required.”
- **Recorded exceptions:** preserve preparation failure, missing completed
  receipt, invalid/unreadable record, unresolved attempt, unreviewed custody gap,
  nonzero recorded harness exit and unfinished close, with their actual source.
  A shell exit says nothing about whether somebody watched. Do not prescribe
  blind re-launch from that input. An available recovery option remains subject
  to its existing prerequisites; collection still requires the manager's stop
  acknowledgment.
- **Codes:** keep 0 for no diagnosed issue within the promised view, 1 for
  exceptional recorded conditions or review gaps, 2 for refusal of the requested
  inspection, and 3 for evidence/records that fail verification. Live-only
  runtime/checkout defects no longer set normal status's code because they are
  outside its observation promise; their operation-time consequences survive.
- **Missing launch acknowledgment:** display the empty acknowledgment history
  neutrally. No claim of an unlaunched audit or duty to create the record now.
- **Release without recoverable matching capture:** keep the missing association
  visible as a custody issue (`release_capture_unavailable`, code 1); actual
  damaged capture candidates retain their specific verification reasons/code 3.
  This classification does not add a closure gate: close uses its own preserved
  assessment, not public attention. A release without a review/run is otherwise
  a recorded stage, not a demand to execute.
- **After collection:** offer collection-bound review and other authorized
  operations when the records support considering them. They still validate
  at use. Retention need not be suppressed by a live destination-exists probe;
  retain owns its exclusive destination refusal. A close option is explicitly
  conditional on close's own preflight, rather than certified by a fresh status
  inventory. Preserve current record-based offer restrictions and bindings;
  do not turn those recommendations into mandatory operation preconditions.

This scope permits deciding ordinary versus exceptional attention. It does
not establish a universal duty to monitor for exceptions or determine who
must secure every eventual return.

Every old `outstanding` category has a destination:

| Old content | Replacement |
| --- | --- |
| Uninterpretable session, invalid retention, invalid disposition or receipt, unresolved/invalid attempt | The existing record/capture/attempt diagnostic, preserving source and reason; no second prose queue. |
| No collection, no launch acknowledgment, no release review/captured construction artifacts | Neutral collection/acknowledgment/experiment facts; existing review/release prerequisites when relevant. |
| Nonzero harness exit without collection | Attributed exit observation and `harness_exit_nonzero`, without unwatched-launch or automatic relaunch inference. |
| Preparation failure or insufficient preparation evidence | Historical preparation account plus its diagnostic and conditional recovery options; never automatic fresh-assignment or restart instruction. |
| Live runtime, HEAD, checkout existence or lock condition | Outside normal status; mandatory owners and lost advisory early detection are identified in the ownership table. Retain any already-recorded observations as history. |
| Recorded submodule support limits | `assignment_limits`, including the session's recorded gitlinks. |
| Current retention destination already exists | Retain owns the exclusive-write refusal; the conditional retain option states its destination prerequisite without probing it. |
| Paused hold still recorded | `coordination` and resume/close prerequisites; recorded hold is not a claim about actual present writer activity. |
| Release without verified recoverable capture | Explicit capture association and the issue classification above. |
| A close offer withheld for integrity/coverage | Existing custody diagnoses where observed; otherwise the conditional close option states its own preflight. No promise of successful closure. |
| Mutation withheld for unrecorded/unavailable writer | `implementation` explains the missing identity or verified-handoff components and why the affected option cannot be issued; preserve actual refusal reasons and supported abandon handling. |
| No draft in this checkout | Keep the existing draft/context view's explicit-owner/selection explanation; this is outside the retired live-session queue. |

#### Handoff access and explicit recipe preview

Keep access to the private handoff without retaining a `handoff` instruction
inside `options`. Ordinary prose identifies that retained artifact; JSON also
contains neutral pinned-profile recipe data where available. Call generated
command text “rendered from the pinned profile,” not byte-exact originally
issued shell text: the retained profile is re-rendered by the viewing code.
The private handoff itself is retained bytes; launch acknowledgments may
separately preserve the command their recorder supplied.

Keep CLI `status --profile PATH` and API `status(..., profile=PATH)` as an
explicitly requested alternative recipe preview. Show both profile identities,
with “Preview from requested profile; not executed.” Read/validate the named
profile once and use that same captured object for summary and rendering.
Allow an explicit profile even if no profile was pinned. Retain existing scope,
placeholder, shell-quoting and profile validation. `launch --from-profile
--profile PATH` remains a separate acknowledgment and records its departure.

This intentionally retires current readiness-gated *offers*. It does not
preserve those gates under a new name: a preview establishes neither public
handoff availability nor present runtime integrity nor permission to launch.
No mandatory operation validation is removed. External manual launch already
has no universal Stewart start gate; it must not be given one through this
inquiry. Current launch/readiness advice can detect problems earlier than
collection; that early detection is a lost convenience, explicitly accepted
for normal inspection. Operation errors and `close --plan` retain the checks
relevant to their own purposes. There is no new readiness command.

#### Workspace listing, discovery, drafts and closes

Workspace status lists use the same record reader and classifications as
individual status, without constructing and discarding each session's launch
recipes or resource eligibility. Show owner, lifetime, recorded milestone,
collection-receipt counts, and itemized issue reasons. Preserve the distinction
between a targeted missing registered session refusal (2) and a listing's
reported missing-record integrity issue (3). Finished closes remain historical
and do not raise the workspace aggregate code.

Discovery is an inventory used for explicit selection, not another name for
validated status. It currently counts receipt paths and checks preparation
marker presence (`audits.py:353–384`), then separately validates identities,
owner availability and implementation information (`418–535`). In
`stewart.discovery/2`, qualify these as `inventory_stage`, `preparation_markers`
and `collection_receipt_paths_found`; do not call the count complete collections.
The selection envelope containing this changed payload becomes
`stewart.selection/2`. Keep selection eligibility, explicit aliases, draft/live
lifetime binding and the kept reference schema unchanged. Trace and update
internal consumers rather than making selection depend on a new stage meaning.
Do not make discovery run full status, and retain its existing integrity errors.

Pre-session draft/context inspection and closed-session recovery keep their
existing purposes. Draft-file inspection is inspection of an assignment being
authored, not monitoring an auditor. Observing leftovers for an unfinished
close is recovery of an explicit removal operation. Their existing view schemas
need not change unless implementation actually changes their fields. Preserve
existing completed/invalid closing-record distinctions and read-time recovery
checks; do not expand this inquiry into all resource/discovery behavior.

#### Concrete examples

The before excerpt is actual baseline output with paths omitted:

```text
Status exit 0: nothing needs attention
Preparation: ready
Collections: 0
Outstanding:
  - no complete collection exists
Next actions:
  handoff: manual, if not already handed off
  launch: ...
  collect: ...
```

Decided ordinary prose, with illustrative identities:

```text
Audit one-question — custody: private handoff retained
Assignment: prompt commit <commit>; target <commit>
Handoff: retained private copy <path> (verified against its recorded digest)
Launch acknowledgments: none recorded
Collections: none recorded
No issues found in the inspected custody records.
```

This does not assert publication, activity, notification or completed work.
A launch acknowledgment changes its own line, not the auditor's activity state.
The JSON below is a projection of the decided status/14 contract, not a complete
schema instance or output from the unchanged implementation:

```json
{
  "schema": "stewart.status/14",
  "stage": "private_handoff_retained",
  "preparation": {"state": "private_handoff_retained"},
  "handoff": {
    "source": "retained_private_copy",
    "path": "<session>/LAUNCH.md",
    "sha256": "<verified-digest>",
    "public_path": "<recorded-public-path>",
    "publication": "not_established_by_this_record"
  },
  "launches": [],
  "collections": [],
  "attention": [],
  "exit_code": 0,
  "options": []
}
```

A recorded failure remains specific:

```text
Audit one-question — custody: private handoff retained
Recorded harness exit: 2 at <time> (launch-block observation)
No collection is recorded.
Issue [harness_exit_nonzero]: the recorded command exited nonzero.
This record does not establish auditor completion or a return arrangement.
```

```json
{
  "stage": "private_handoff_retained",
  "harness_exits": [{"exit": 2, "at": "<time>"}],
  "attention": [{"code": 1, "source": "harness exit log",
    "reason": "harness_exit_nonzero",
    "message": "The recorded launch command exited 2; no collection is recorded."}],
  "exit_code": 1,
  "options": []
}
```

The tested transition captured a report containing informal “Status: complete”
prose without a valid declaration. The decided presentation keeps the distinctions:

```text
Audit one-question — custody: collection recorded
Collection <name>: receipt recorded; report captured at <capture>/REPORT.md
Manager acknowledgment: auditor stopped, kind interrupted
Auditor completion declaration: unavailable (declaration_missing)
Issue [custody_gap]: declaration_missing
Review option: triage-draft for collection <name> (no claims accepted)
```

```json
{
  "stage": "collected",
  "collections": [{"name": "<name>", "receipt_state": "recorded",
    "report_status": "present", "report_path": "<capture>/REPORT.md",
    "auditor_stopped": {"acknowledged": true,
      "by": "maintainer via --auditor-stopped", "kind": "interrupted"}}],
  "auditor_reported": {"completion": {"value": null,
    "attributed_to": "auditor", "reason": "declaration_missing"}},
  "attention": [{"code": 1, "source": "collection <name>",
    "reason": "custody_gap", "message": "declaration_missing"}],
  "exit_code": 1,
  "options": [{"action": "triage-draft", "collection": "<name>"}]
}
```

Actual option objects must also carry the preserved runtime, lifetime and
operand bindings; these projections omit those mechanics. A missing final
collection receipt instead shows `receipt_state: missing` and
`collection_incomplete`; invalid or unreadable bytes keep their own reason and
code 3. Neither becomes ordinary waiting or a completed return.

### Observation, consumer and diagnostic ownership

Line references below identify the investigated baseline, not a required future
module layout.

| Observation / source | Present public effect and consumers | Decision and owner |
| --- | --- | --- |
| Session, identity, schema, lifetime (`session.py:184–289`; `status.py:429–479`) | Assignment/stage, diagnostics, mutation identity gates | Shared verified record reader; preserve operation revalidation. Unsupported/unreadable records stay diagnosed. |
| Commit retention (`status.py:442–456`; `_repository.verify_retention`) | Custody availability diagnostics; most mutable operations independently verify | Retain read-time verification of held commits. Collection preserves raw bytes before diagnosing retention. |
| Private handoff and preparation records (`prepare.py:285–315`; `status.py:523–545`) | Mixed preparation/readiness classification | Status verifies retained private custody, not public publication. Keep failure/missing/invalid distinctions and phase-specific absent-record exceptions. |
| Live public handoff, checkout existence/admin/HEAD/lock (`status.py:480–521,523–560`) | Preparation, attention, launch/collect offers; close indirectly | Omit from normal status. Collection owns checkout identity and capture; release/run retain their checks. Close must automatically retain its existing live-observation consequences. Manual launch has no universal Stewart operation gate; loss of status's advisory early check is explicit. |
| Current supplied runtime (`status.py:547–555`) | Runtime-unavailable code 3, recovery/launch offers; close indirectly | Omit normal live scan. Collect, release/run and recovery own their boundaries; close retains existing automatic integrity consequences. Captured runtime bytes remain independently verified. |
| Maintainer checkout state and report destination (`status.py:495–521`) | Coordination signal and suppression of retain; observation errors can gate close | Omit normal probes. Retain's exclusive write validates destination; collection records its observations; close retains currently consequential observation errors pending wider audit. |
| Launch/message receipts (`coordination.py`; `status.py:621–624`) | Attributed history; launch suggestion suppression | Retain safe reads and attribution. Neither acknowledgment nor missing acknowledgment establishes activity. |
| Harness exit log (`launch_profile.py:228–255`; `status.py:599–602,1060–1062`) | Nonzero-without-collection attention and relaunch advice | Retain observation/diagnostic; retire unwatched-launch inference and automatic relaunch advice. No callback inference. |
| Collection attempts/receipts/report (`status.py:116–187,627–631`) | Receipt presence, gaps, captured declaration, review options | Retain all attempts and exact diagnostic quality. Capture remains collect's operation; normal status never substitutes live report bytes. |
| Disposition binding (`triage.py:264–285`; `status.py:636–646`) | Clears addressed gaps; gates retain/resume and close basis | Shared binding validator; retain/resume independently revalidate. Different collection identity cannot be replaced by equal report bytes. |
| Releases/capture associations (`status.py:651–681`; `captured.py`) | Recoverability, gaps and run/release offers | Keep selected captured-byte verification at read time and no live fallback. Preserve failed-release diagnostics without success-only field assumptions. |
| Current inventory / coverage for close offer (`status.py:864–883,1373–1395`) | A fresh check gates the suggestion | Remove live inventory from status; retain `require_capture`, inventory and frozen revalidation in close (`close.py:1137–1150,372–405`). Offer only as conditional on close preflight. |
| Paused holds, unresolved attempts (`close.py:1123–1130`) | Public history/news; actual close refusal | Shared records, close-owned mandatory predicates. Older unresolved attempts may remain close blockers even when newer attention supersedes them. |
| Resource evaluation (`status.py:799–803`; `holdings.py:1146–1245,1363–1400`) | JSON disposal dispositions; exceptions become session problems | Any legacy association/diagnostic view follows the bounded reader contract; no general legacy-resource projection is required. General manager-resource disposal is deferred. Close-plan and close own the frozen inventory, dependency and hold checks for audit-owned material they may remove; they acquire no disposal authority over manager workspaces. |
| Manager implementation (`_invocation.py:37–96`; `implementation.compare`) | Verified command rendering and writer handoff | Keep explicit writer binding and verified descriptors. Inspection executes no recorded code. Session-read immutability is not a promise that API bootstrap never creates manager deployments. |
| Listing/discovery (`status.py:1071–1135`; `audits.py:353–535`) | Listing runs full status; discovery reports path-presence hints | Listing adopts common custody projection. Discovery labels inventory hints and keeps selection identity rules; it does not become full status. |

A live check moved out of inspection is detected later at its operation owner,
not magically eliminated. If a proposed move has no later mandatory owner,
identify whether the retired behavior was advisory or an independent obligation.
Do not claim preserved protection merely because an optional command exists.

**Closing records retain their meaning.** `CLOSING.observed.stage` currently
comes from `preparation.state` (`close.py:963`), not public `stage`. Keep that
operational observation and `stewart.closing/1`; do not feed the new custody
milestone into the old field. Public schema changes do not require session or
closing receipt rewrites. Existing writer-bound sessions remain bound: a new
implementation may inspect supported evidence but may not mutate an old writer's
session or automatically execute its implementation handoff. Historical receipts
and captured documents remain untouched.

**Offers are not operation prerequisites.** Current status offers close more
narrowly than direct close permits. It requires no other pending option and
latest-collection triage; direct close can choose the latest validly triaged
complete collection (`status.py:1373–1395`; `close.py:1115–1136`). Do not migrate
those advisory restrictions into new mandatory refusal conditions.

## Close

**Successor interface direction, 2026-10-25.** The user's strong preference is
one manager-facing `close` command that closes the audit regardless of its
current state. Design toward that single entry point across the lifecycle:
the manager need not diagnose the stage and choose a separate withdrawal,
abandonment or closure procedure. A request made during investigation may
take an internal withdrawal path; Stewart owns the supported stopping,
partial-work accounting and custody steps needed to complete closure.

This is a design direction, not an implemented interface or a guarantee of
immediate completion. Existing holds, preservation undertakings and removal
authority still constrain completion; requesting close does not silently
release or surrender them. An interrupted or blocked closure remains visibly
unfinished and needs a supported path through `close`, without private-state
repair or another lifecycle command. Determine the required dispositions and
return any concrete conflict with an existing obligation for decision. The
earlier conclusion/abandon rules below constrain custody and legacy behavior;
their separate manager-facing modes are not a requirement for the successor.
Exact stop/capture, disposition and continuation mechanics remain open. No
runtime implementation is commissioned by this direction.

**Graceless exit direction accepted, 2026-10-25.** Include
`close --graceless-exit` to request termination of the audit's execution
without waiting for a cooperative handback or final report. Preserve obtainable
partial work and account for capture gaps, including the possible loss of
unwritten work, then continue the same closing operation. The flag supplies
no blanket discard, hold release or surrender of a preservation undertaking;
the existing custody and removal obligations still govern completion.

This direction accepts an unresolved control obligation. The launch command
may be executed by a person or by an agent; issuing it does not determine who
starts, controls or later stops the audit. Design and qualify a binding from
the audit lifetime to its actual execution, the authority and means to stop
it, and evidence of what termination ended, including ongoing tool activity.
The present auditor is Claude Code, but neither the launcher actor nor a
particular control arrangement is fixed by this decision. No termination
mechanism or runtime implementation is established here.

Decided 2026-10-24. **Decided, departure.** The Python close at `6582df2` is the
control; `CUSTODY-AUDIT-FINDINGS.md` at `356dc58` records its behavior in the
executed comparisons these rules answer. The rules apply to close's own
assessment, however that assessment is obtained; they do not depend on the
public status view.

**Scope updated 2026-10-25.** Successor audit closure retires Stewart-owned
audit facilities under the handoff contract above. General manager-workspace
creation and disposal is deferred, so the old claim-and-retire phase over
manager resources is not part of successor audit close. Any legacy resource
reporting follows the bounded reader contract. Holds on identified custody material, live
dependencies and the frozen revalidation of anything close actually removes
remain required. Provisionally resolved 2026-10-25: the working environment
may retire while held material remains in the audit's custody, delaying final
custody close until explicit release and the other closing conditions are met.
The lifecycle schema and its qualification remain open. A close cannot silently
release a hold or destroy its subject, and completed close cannot leave
unfinished audit operations behind under the name of a hold.
The subsequent no-executor decision also removes dedicated attempt HOME,
output areas and active release/run states from successor close. References to
those facilities in the earlier rules and schema examples describe the legacy
population; they do not require recreating it. General capture, hold, frozen
removal and incomplete-operation obligations remain.

**Runtime coverage replaces equality with preparation.** At a concluded close
the supplied runtime is accounted for when its current state matches the
runtime observation recorded by the triaged collection the close rests on. The
preparation pin remains the identity of what was supplied and the readiness
reference for operations that run things (collect, release and run, recovery);
it is not close's reference. The observation compared is the collection's
final recorded runtime state: where the capture recorded movement during
collection, its after-observation. A collection whose runtime phase failed
recorded no state to match, so conclusion on it refuses as unjudged. A
mismatch refuses with reason `runtime_changed`, parallel to the checkout's
`checkout_changed`, and the same next steps: collect again and triage, or
abandon with explicit discard. Damage captured before collection and addressed
by triage concludes; damage after collection refuses. The runtime is still
removed at close. Reliance change: a participant may conclude with a runtime
that no longer matches its preparation pin when the triaged collection
recorded that state. The gap a changed runtime creates at collection is the
collection error whose reason is `runtime_changed`; the disposition must
address that gap, not merely a displayed diagnostic.

**A recovery is disposable while it matches its own capture.** At close in
either mode, each recorded runtime recovery is compared with the capture
recovery made of its materialized directory. A match means the directory is
still what that capture records; it is removed without acknowledgment and the
closing record notes that it matched its materialization capture (this does
not re-verify the pristine assets it was made from). Removing it loses nothing
the session's own runtime capture does not hold, and that capture is what
retention and export can keep; the ground is duplication of held material, not
a claim that the recovery could be regenerated after close. A mismatch is
content the manager never judged: conclusion refuses with reason
`recovery_changed` and
names the recovery, abandon's discard must name it, and the closing record
freezes its identity. A recovery whose materialization or capture failed has
nothing to match and is treated as unjudged. Recovery captures once, at
materialization, and is not re-captured later; the in-Stewart resolution for
a drifted recovery is abandon's acknowledgment after the manager has taken what
it wants. Reliance change: a successful old recovery alone does not authorize
discarding new work written into it.

**Access-boundary issue, 2026-10-25.** The phrase "after the manager has taken
what it wants" assumes a preservation route that restricted manager live access
may remove. It does not authorize direct access contrary to the handoff
contract. On 2026-10-25 the user accepted a lean toward omitting the successor's
mutable runtime-recovery materialization: first establish whether retained
helper assets, bounded inspection and separately authorized fresh reuse serve
its consumers without this extra directory. This is not yet a decided removal.
If materialization remains necessary, specify its supported preservation route
and lifecycle; otherwise explicitly revise the affected opportunity/recapture
contract when removing the capability. Existing Python recoveries still require
their transition disposition. The decline of recovery recapture below is not
silently reversed.

**Legacy experiment HOME is declared disposable with its identity recorded.** The
attempt HOME is created outside the output area before launch and written by
project code; the experiment contract places output elsewhere. The removed
member is the attempt directory that contains HOME, and the declared category
and frozen identity name that member. Close removes it without acknowledgment
when nonempty and freezes its identity in the closing record. A manager who
wants HOME contents takes them before close. This is a declared category, not
a content judgment; it was chosen over charging an acknowledgment because that
acknowledgment would be of a nominal opportunity.

The successor has no dedicated experiment HOME because it has no program
executor. Its retrieval/cleanup interface is therefore not a successor design
task. This rule remains relevant to the legacy population and does not promise
to preserve HOME or authorize access outside its writer's interface. Other
audit material does not acquire this disposable category by analogy.

**The closing record freezes the identity of what was discarded.** Anything
removed under acknowledgment or declaration, rather than by matching a reviewed
capture, is named in the closing record with paths, sizes and digests, never
bytes; a non-regular entry is recorded by kind and is not read. This applies
the existing freeze-what-was-judged rule to discards and makes a later question
about what close removed answerable. Every comparison these rules make is made
at planning, frozen in the closing record, and revalidated before the
corresponding removal step, including on a resumed close, as the checkout
comparison is today; a revalidation failure stops at that step with its reason.

**Abandon follows the same rule.** Only abandon carries a discard
acknowledgment; conclusion acquires none, so a drifted recovery or an
uncaptured runtime change refuses conclusion and is resolved by collecting
again or by abandon. The discard acknowledgment covers what the closing record
names. Abandon never silently discards more than conclusion would; it names
it.

**A kept checkout stops cleanup.** When the checkout is reported kept because
it is registered elsewhere or was substituted, the remaining removal steps do
not proceed, as they already do not after a failed checkout revalidation.
Removing the session would leave the kept checkout without the captures and
receipts that verify or recover its custody context; the closing record names
its identity but cannot substitute for them. The stop is recorded in the
closing record with outcome `checkout_kept` and the
condition observed; the exits are restoring the judged state and resuming the
close, or resuming with an explicit acknowledgment that names the kept checkout
and which the closing record freezes. No session is retained indefinitely by
silence.

**Command rendering is not a closure precondition.** Failure to render a
suggested command from the cached manager launcher does not refuse close.
Writer authority, captured evidence validation and frozen revalidation within
close's authorized removal scope remain required. Handoff damage remains
evidence and is diagnosed; it is not treated as merely unavailable interface.

**Retained, not re-decided.** A damaged retained record that conclusion relies
on, such as a mismatched private handoff or a capture that no longer verifies,
still refuses conclusion, because conclusion deletes the originals. The exit
is abandon with explicit discard, naming the damaged record.

**Which live checks conclusion makes.** Conclusion's live checks are
exactly: writer identity; the checkout inventory against the triaged
collection's receipt; runtime coverage; each recovery against its capture; and
the frozen identities, contents and dependencies of the audit-owned facilities
being removed. General manager-resource eligibility evaluation is deferred
with that service. Recorded custody holds also constrain removal. A public
handoff differing from preparation is accounted for in the same way as the
runtime: when the triaged collection
recorded the difference as a gap and the disposition addressed it, it does not
refuse conclusion. Observations that only populate the closing record, such as
the maintainer checkout's HEAD and dirtiness or a destination's presence, are
recorded as unavailable when they cannot be made and do not refuse. Failure to
render a command is covered above.

**The closing record is a new schema.** A closing record that
freezes discard identities, recovery verifications and kept-checkout
acknowledgments is a new closing schema. Each removed item carries the ground
on which it was removed, and the grounds are not interchangeable: it matched a
reviewed capture; it duplicated session-held material (a matching recovery);
it was removed under a declared category without examination (an attempt
directory with its HOME); it was surrendered by an explicit discard that named
it; or it was lost despite a recorded preservation undertaking that did not
complete. An item removed without examination, or without a working
preservation path, is never described as declined or reviewed. The record's
`observed.stage` is close's own operational preparation classification, not
the public status milestone. Existing `stewart.closing/1` records remain
readable as written and are never rewritten. The close basis under the public
contract's `receipt_state` vocabulary is a collection whose receipt is
recorded, whose capture verifies, and which a valid bound disposition
addresses.

**A recorded preservation undertaking gates conclusion.** A retain or
export the manager began and Stewart recorded as planned, whether as a keyed
request with attempts and no outcome or as a retention record carrying
problems, is an undertaking, not advice. Conclusion refuses while such an
undertaking of this lifetime is neither completed by a later retention covering
its selection nor explicitly surrendered through abandon naming it; the closing
record then carries it as surrendered, never as discarded by default. Today
close does not consult request state and `retain` has no safe resumption, so
the exits are a fresh retention or abandon naming it.

**Supplied-file copies at abandon.** Decided 2026-10-24. A worktree copy of a
supplied file is removed at abandon only if the original it duplicates still
exists and matches its pin; a copy whose original is absent or differs is
treated as uncollected. Today the copy is exempt on its pin alone and is not
named among discards. This is a disposal check on a pinned input whose
duplicate close is about to remove, not a live check on a published output.

**Advice stays separate from preconditions.** Status's offered close is
narrower than direct close's preconditions: it requires newest-collection
triage and no pending retention, release or run. Those remain advice and are
not migrated into mandatory refusal conditions.

**Later returns.** An executed comparison of the frozen Python close
(`.scratch/custody-audit/later-return-03`, six cases, all passed) refined the
source finding. When the latest complete collection is untriaged and records a
verification-level custody gap, such as `runtime_changed`, conclusion refuses
today, because status surfaces that collection's gaps and close refuses on any
code-3 item; triaging it moves the basis to it. That protection is incidental
to status and reaches only the latest collection: once a later clean
collection follows the one that recorded the change, conclusion rests on the
older triaged collection and the recorded runtime change is addressed by no
check. A later return whose checkout bytes differ is caught by the checkout
comparison, as exercised; a differing report lies in the worktree and is covered
by the same inventory, by source reading. The evidence the checkout rule misses
is therefore the custody gaps. Decided rule: conclusion may rest on an older triaged
collection only if every later complete collection either has a valid bound
disposition or records no verification-level custody gap. A later collection
recording such a gap must be triaged before conclusion, whichever position it
holds in the sequence; the exits are triage or abandon. A later collection
whose only gaps are review gaps, such as a missing declaration, remains advice
and does not block. This belongs to close's own assessment, not to the public
attention list. `close --plan` names the collection and disposition the close
would rest on and every later collection with its gap level; today the plan
discards that information and only an executed close records it.

## Export of selected custody with surrounding damage

Decided 2026-10-24. **Decided, departure.** A verified selected report and its
exact source receipt are exportable even when a sibling capture in the same
collection has since been damaged, provided the export carries the damage
explicitly and the damaged original is preserved. The report's trust chain is
per-member hashing anchored by the receipt, and for a triaged collection the
receipt digest is pinned again by the disposition. The receipt also pins the
runtime group's capture digest, so the chain does name that group; what the
selected report's verification does not depend on is the group's present
readability. Invalid selected bytes still refuse. A diagnostic that
materially qualifies the source travels with the package; omitting a failed
group is not proof it was healthy. No claim is made that the whole collection
is sound. Scope: export only. Triage may not pretend there were no gaps,
concluded close keeps full-capture, and the owned writer-compatible session
requirement for original export is a separate choice. This deliberately
revises the policy the manual documents and the test that encodes it.
Reliance change: selected custody remains valid despite explicitly damaged
surrounding evidence.

## Supplemental inputs below gitlinks

Decided 2026-10-24. **Decided, departure.** A supplemental destination below
a gitlink is refused before
allocation, with the instruction to pin the supplied copy at an ordinary path.
This removes the contradictory contract in which preparation admits such a
descendant and the `gitlink_contents` remedy then says to move it. Populated
submodules remain unsupported. The submodule decision is made: pinned
submodule copies, below, are the one thing preparation places below a gitlink,
and nothing else may be supplied there, materialized or not. Captured contents
and historical assignments are never rewritten.

## Launch acknowledgments by people

Decided 2026-10-24. **Decided, departure.** A launch acknowledgment retains its
actor, channel or style, and attributed handoff information; model and effort
apply only to an agent arrangement and are neither required nor invented for a
human one. The change is representational. It establishes no delivery service,
requires no watcher, transfers no responsibility after human approval, and does
not make a recorded acknowledgment proof of activity.

## Pinned submodule copies

Decided 2026-10-24. **Decided, departure.** Preparation materializes a
gitlink's pinned tree as plain files below the gitlink path, as preparation's
own pinned copies: per-file digests, commit, tree and source recorded in the
session record; one level only; objects taken only from the maintainer
checkout's own submodule administration; no network; no Git administration
created; a changed copy is a verification failure like a changed supplemental
input. This is an effectful preparation step: it reads a second object store,
writes files into the checkout, requires parsing `.gitmodules`, and adds a
refusal when the objects are unavailable locally. Collection archives the
materialized tree with the rest of the checkout. At abandon without a
collection the copies are accounted for only if the maintainer's submodule
administration still holds the objects they duplicate; the pin-only exemption
is not extended to them. The auditor may rely on the copies being the
submodule's pinned revision; nobody may rely on them being a Git checkout or on
recursive submodules being present. Work inside populated submodules is
declined; see Declined.

## Return arrangements and the human auditor

Decided 2026-10-24. Nothing the auditor does reaches Stewart before
collection: the issued helpers write only the report path, the scope denies
session reads and common-directory writes, and auditor bytes are read once, at
collection, after the manager's stop claim. The decisions below respect that.

**A manager-declared return arrangement.** **Decided, departure.** The
manager may record, as attributed free text bound to the session, how it
expects the return to arrive. Status lists it under coordination. It carries
no time, outcome or current field, is never paired with an absent collection
as attention, describes how the manager expects the return rather than who is
entitled to receive it, and establishes no delivery, watcher or callback duty.

**A stop note on collect.** **Decided, departure.** `collect` accepts an
optional note stating the basis of the manager's stop acknowledgment,
mirroring the pause note. It is attributed text, not a verdict.

**What the structured return already is.** **Documentation.** The auditor's
structured return is the collection-bound captured report with its
declaration; the manager's disposition with its kind-bound follow-up is a
structured reply that never leaves private custody. Neither reaches the other
party through Stewart today.

**The handoff is complete without the helpers.** **Decided, departure.** The
issued handoff carries a pasteable declaration block, manual remedies for each
gap, and labels on the parts bound to the issuing host: the helper argv names
the manager process's interpreter, and the launch block's exit trailer appends
into the private session. A human auditor can therefore return a valid report
without the helpers. The auditor acquires no further standing: no channel, no
notification, no retention right, no role transfer.

**Delivery.** **Deferred.** Stewart describing, requiring or performing
delivery of the return waits on a receiving endpoint and real-harness
evidence. Delivery is not placed outside Stewart by this deferral.

**A capture receipt for the auditor.** **Deferred.** A read-only projection or
receipt an auditor could see, confirming their return was captured raw, is
decided with the successor's status rendering. It serves Stewart's first
process promise to a human auditor.

## External sources and the constructed network grant

Decided 2026-10-24. **Decided, departure.** An assignment's external sources
are recorded beside the network grant the launch adapter constructs, and the
handoff tells the auditor both. When an assignment names sources that the
selected launch style constructs no route to, Stewart records a neutral limit
in the same way it records gitlinks; it never refuses and raises no attention
item, since an offline construction is the ordinary case and the style is
known at prepare only when a profile is pinned. Wording says constructed, not
observed: a manager may rely on knowing what was constructed, and nobody may
rely on a fetch having been permitted or having happened. **Deferred:**
constructing the allowed domains from the assignment waits on a real-harness
network qualification; a permitted domain would make the auditor's readable
Git object store transmissible, which that qualification must weigh. Stewart
fetching and pinning external bytes itself is declined; see Declined.

## Program execution and the legacy experiment route

Decided 2026-10-25. **Decided, departure: no dedicated program executor in the
successor.** Stewart supplies selected material, captures the audit's return
and maintains its custody. An auditor may use tools under its commission and
enforced access grants; this decision neither bans that activity nor grants
unrestricted execution. It removes Stewart's separate program-execution service
and the manager-operated construction/review/release/run relationship. It does
not transfer that workflow into a new external executor or orchestration service.

The reason is the bounded commission/return relationship and the responsibility
cost of supervising program attempts. Existing implementation investment is
not a reason to retain that responsibility. This revises the stage-3 decision
that reviewed Python scripts are Stewart's route for project commands.
Python remains frozen; the chosen departure is to be realized in the successor
when implementation is commissioned.

| Dependent behavior | Disposition for the successor |
| --- | --- |
| Experiment grants, exact-byte release, `run`, invocation reservations and child launcher | No dedicated execution API or intermediate manager approval stage. No same-audit re-release/output-reset facility. A commission can still state the auditor's permitted tools and operations. |
| Program argv, exit, streams, protected-file endpoints and invocation limits | No Stewart executor witness or execution-count guarantee. Captured reports/logs retain their source attribution; byte verification does not establish the claimed execution or effects. |
| Reviewed project-command shim | Superseded as a required Stewart route. Tool use remains subject to the commission and actual access/effect boundaries; no replacement executor is commissioned. |
| Dedicated attempt output area and HOME | Not created by the successor. Their special retry, retrieval and close handling is not ported. Ordinary audit output remains subject to capture, preservation undertakings, holds and authorized removal. |
| Ledger and measurement evidence | Preserve selected raw bytes, collection/review identities and attribution. Any supported interpretation must verify the applicable recorded membership rather than infer it from counts. A successor ledger-specific reader/reviewer needs a named consumer and scope; this decision neither commissions it nor makes reported rows proof of execution. |
| Status and historical releases/attempts | No new executor stages or successor run/release suggestions. Interpret admitted historical records under the bounded reader contract, retaining their gaps and diagnostics without activating them. |
| Existing Python attempts, captures, publications and related resources | Preserve their records and explicit legacy dispositions. No automatic completion, transfer of execution rights or discard follows from removing the successor executor. |
| Interrupted capture, publication, requests and close | Retain Stewart's responsibility for supported completion or explicit disposition of its own undertaking. A new question is not its remedy, and an honest diagnostic alone is not a usable recovery path. |

Recording the remit does not itself promise replay. The preference remains
zero audit retry facilities, with at most one restart-from-start convenience
still open; selecting no executor does not decide that separate interface.
The lean against materializing mutable helper-runtime recovery directories is
also separate: supplied auditor helpers are not the removed program runner.

**Execution failure is not dissatisfaction with an audit answer.** Clarified
2026-10-25. A manager deciding that an answer is intellectually unsatisfying
and wanting another audit is outside Stewart's remit. Legacy execution records describe
the authorized process and captured evidence; their errors do not grade the
answer or prescribe further investigation. Questions about another invocation
concern execution authority, prior evidence and working-state management, not
a policy for when the manager should ask again.

**Earlier route, superseded for the successor on 2026-10-25.** Decided
2026-10-24: the supported route for running a
project's own build or test commands is a reviewed Python script that invokes
them through a subprocess, with the command literal in the frozen script so
that the manager's byte review is the command review, the child's command
claims in its receipt, and controls designed to discriminate the instrument.
The costs are stated: the attempt environment is the manager's PATH with HOME
redirected, toolchains are unpinned, and residue inside the worktree is
archived as gaps. The access-limits statement that this route may not serve a
project's real system checks remains true where those checks need an
environment the shim cannot provide. A separate command experiment kind is
declined; see Declined.

## Holds on identified custody material

Decided 2026-10-25. **Decided, departure.** A manager may record a narrow,
attributed, blocking-only hold on identified custody material, with explicit
release. This replaces the 2026-10-24 hold's attachment to the general
recorded-resource service; it is not deferred with that service. Neither
form is implemented in frozen Python.

The record identifies the material, actor, condition and the limit of the
undertaking. Stewart does not dispose of that material while the hold is
active. A hold is released only by an explicit attributed release record;
close, a container's retirement and a disposal option cannot override it.
Its effect and identity are visible in custody inspection and removal
planning, and any affected closing record accounts for it. A hold grants no
removal, live-workspace access or investigative authority. It promises
restraint by Stewart, not delivery or protection against the human controlling
the machine. No third-party veto follows from naming a provider, and release
does not require the provider to operate Stewart.

The discriminating design test, recorded 2026-10-25, is that a hold must
neither permit the manager to continue the audit nor excuse dangling operations
after close. If the hold phase seems to need elaborate operational facilities,
first examine whether the commission, capture or closure boundary is leaking.
Recovering an interrupted custody operation must not become permission to
resume investigation. Inspection or preservation of an authorized capture
rests on its existing authorization; a hold adds none.

Subject rule accepted 2026-10-25: hold a finite, explicitly identified selection,
including the metadata and captured dependencies needed for the custody claims
Stewart undertakes. References within that selection do not recursively enlarge
the hold to every mentioned repository, file, tool or environment. Missing
dependencies remain stated limitations or gaps, never material falsely claimed
to be preserved. This promises neither reproducibility of the entire inquiry
nor retention of every audit artifact.

The representation of those identities and treatment of copies or transfers
remain write-path design questions. A hold on an original does not
silently attach to every copy; making a copy does not implicitly release the
hold. If a hold is to allow a working directory to retire while identified
captured bytes remain held, that identity and discharge rule must be explicit
and verified. The user provisionally resolved the arrangement on 2026-10-25:
keep that custody with the audit until explicit release and the other closing
conditions permit final close, without establishing a separate service after
audit closure. The inquiry may be finished and the working
environment retired while custody remains held; this implies neither an active
auditor nor a duty to monitor one. Release removes the hold's restriction,
not the other conditions for disposal. The representation and recoverability
of held material, and evidence for safe working-environment retirement, still
need design and qualification. These details do not reopen the decided
requirement for attribution, a narrow identified subject and explicit release.

## Attribution of retention

Decided 2026-10-24. **Decided, departure.** `retain` records its actor as
export and every resource-writing operation do, so that publication of the
deliverable is not the least attributed step.

## Evidence interpretation across implementations

Decided 2026-10-25. **Decided, departure.** Protect supported, qualified
interpretation of custody evidence independently of authority to continue its
audit. A reader's different implementation, an unavailable old executable or a
retired live environment does not by itself invalidate independently verified
captured evidence. The reader names the material, custody identity, provenance,
attributed claims and limits it can establish. Completed retained/exported
products remain inspectable without the removed session.

This replaces a blanket commitment to successor inspection of Python's private
operational records. Legacy support requires an identified consumer, a bounded
record population and explicit supported claims. Evidence inspection,
transition diagnosis and current custody status are distinct needs. A need
confined to transition can be met outside the successor's ordinary operating
surface; it does not create a permanent compatibility obligation. Using Python
records as acceptance evidence likewise creates no public support promise.

Inspection preserves original bytes and separates interpretation from mutation,
resource eligibility and execution. Unsupported schemas remain unsupported;
invalid, missing and unreadable evidence retain their distinct diagnostics.
No repair, replay, receipt conversion or implicit execution of recorded code
follows from reading. An unavailable operational facility qualifies the affected
operation, rather than suppressing independently interpretable evidence. A
matching report digest cannot replace collection identity. Any optional writer
handoff remains explicitly verified and confers no authority merely by existing.

Each admitted reader scope must be qualified: valid supported evidence remains
usable when irrelevant live state or old-code availability changes; damaged
selected evidence invalidates the relevant claim; custody records remain
unchanged and no old code executes. Whole-host read-only behavior must be
qualified separately from custody-record immutability. No universal migration
format or new operational service is required. Exact reader placement and the
supported population remain design work under this contract.

## Writer continuity into the successor

Bounded retirement direction accepted 2026-10-25; successor mutation of old
lifetimes remains **Deferred to the successor transition**. Existing Python
writers service their open sessions. Any admitted successor inspection is
read-only under the evidence interpretation contract above, with no implicit
execution of retained code, compatibility shims or rewritten receipts. If the
successor is to continue old sessions, its authority requires an explicit
decision with evidence, supported record population and failure treatment.

The transition settles identified undertakings in a specified legacy population
without automatically transferring old operational roles into the successor.
Closing Python audits avoids cross-writer mutation of those audits but does
not settle independent resource claims or partial requests. Remaining
undertakings need explicit dispositions before their writer is withdrawn;
invalid evidence or an unresolved exception cannot be relabelled complete.
Unchanged historical records are not continuing operations merely because they
survive. Reuse of evidence grants neither an old session nor its execution rights.

Cross-writer export remains separately deferred. Under the refusal principle,
export of a verified report with the exporting implementation recorded in the
package is expected to be permitted when that authority is decided; reading
alone does not decide it.

## Access and experiment capability limits

**Documentation, frozen Python.** Private-path and effect-authorization
obligations are retained. Their costs are stated rather than promised away:
the access scope is a snapshot, so later checkouts or manager entries can require stopping and
repreparing affected auditors; an HTTPS-only assignment can be structurally
valid while the supplied adapter permits no network domains; the Python
minimal-environment experiment route may not serve a project's real system
checks; project rules reach the auditor only through supplied accessible
guidance. Eliminating the coordination duty needs a different access
arrangement and real harness qualification; the selected explicit-grant
direction above pursues that elimination. External retrieval and project
commands as experiments are decided above in their narrowed forms.

Further limits established by the additions inquiry, stated as facts of the
frozen baseline: the constructed scope grants the auditor read access to the
whole Git common directory except Stewart's private storage and the role
markers, which includes a maintainer's absorbed submodule object stores and
other sessions' worktree administration; only the scope's precedence rule is
harness-qualified. An assignment's external sources are validated and then
consumed by nothing, and the adapter's empty allowed-domain list is an adapter
constant rather than a scope field; the manual and sub-agent launch styles
construct no network boundary at all. The experiment environment is the
manager's PATH with HOME redirected and no sandbox. Collection's walk lists
nested `.git` files and skips nested `.git` directories, so an absorbed
populated submodule is predicted to be captured file by file while an old-form
one is a boundary; the capture half is unexecuted. The human-ferry entry point
is bound to the issuing host in the helper interpreter path and the launch
trailer's private-session append; that a ferried launch misreports is
predicted, not executed.

## Previously accepted corrections

**Decided, departure.** Accepted before the current program and still
unimplemented in Python; the successor realizes them:

- Compute implementation identity before allocating collection, run or
  recovery state; Git metadata timeouts leave commit and dirty state unknown.
- Replace the porcelain branch query with `git symbolic-ref -q HEAD` after
  comparing attached, detached, unborn and chained HEAD behavior.
- Bind the last required observation to the value actually written or used,
  and retain it through removal.
- Count hidden executable-bit changes in capture coverage, with kind and
  content.

Two demonstrated implementation issues under retained trust commitments:
configured Git filters execute during preparation's `worktree add`, and
`expected_inputs` follows replacement objects while coverage disables them. The
successor's Git invocation needs one consistent configuration and environment
policy across preparation, verification and cleanup. The commitments, no
unauthorized execution and immutable object identity, are not weakened to
excuse current behavior.

## Declined

Each entry records why, so later readers recover intent rather than infer it.

- **Mandatory retention before close.** Converts advice into a duty, is
  invasive to the manager's flow, and did not address the baseline's uncaptured
  recovery changes or disposable HOME. The later executor removal does not
  reverse this decline; accepted narrow holds remain voluntary undertakings.
- **A universal final preparation receipt.** A keyed preparation already binds
  an outcome for a caller who wants that evidence; status describes the
  interrupted state truthfully as a retained private handoff with publication
  not established; a receipt would not prevent the interruption, only relabel
  it. Preparation is one operation evidenced by its records, and a
  bound outcome is opt-in through a request key.
- **Splitting issuance from preparation.** The same gap from the other side. It
  adds a lifecycle stage and a status state with no consumer; the human-ferry
  entry point works through prepare plus a launch acknowledgment. Entry points
  vary at launch, not by splitting preparation.
- **A manager accepted-answer receipt.** Conclusion and triage already record
  the manager's engagement; an accepted flag is verdict-shaped even when
  attributed. Stewart records dispositions and conclusions, never a verdict on
  the answer.
- **Live checks on retained published files.** Publication records the file
  and its digest, so anyone can verify later from the record; policing the
  manager's filesystem is outside custody. Custody ends at the record of
  publication.
- **Re-capture of recovery contents.** Recovery captures its directory once,
  at materialization. A later re-capture of new work written into it is not
  added; abandon's acknowledgment with frozen identity suffices for a drifted
  recovery, and a re-capture operation would be an addition with no identified
  need under that earlier access arrangement. The restricted-manager direction
  now requires checking that premise: the recovery paragraph above records the
  unresolved preservation route. This decline has not been silently reversed.
- **Charging an acknowledgment for a nonempty experiment HOME.** The
  acknowledgment would be of a nominal opportunity; the identity record serves
  the later reader without the step.
- **Work inside populated submodules.** It would make Stewart create, verify,
  configure, inventory and dispose of a second Git administration per gitlink,
  extend coverage, declarations and the closing schema, and decide the fate
  of auditor commits, in an area Git's own documentation calls incomplete for
  linked worktrees; pinned copies and permitted auditor tool use serve
  path-based checks and captured edits. The successor has no separate Stewart
  experiment grant or executor. Git-aware tooling inside a submodule
  is a fresh candidate, not a residue of this one.
- **An auditor-attributed acceptance of the commission.** No auditor channel
  reaches Stewart before collection; the `start` declaration skeleton is
  already the earliest auditor-attributed artifact; a session channel would
  produce exactly the activity signal status refuses to infer.
- **Further standing for a human auditor.** No channel, notification,
  retention right or role transfer follows from human authorship; the
  handoff's completeness is the whole accommodation.
- **Stewart fetching and pinning external bytes.** Supplemental inputs already
  carry retrieved bytes with attributed provenance; making Stewart a network
  client would gain attribution only.
- **A command experiment kind.** It drops membership review and the firing
  control and makes the project at HEAD plus an unpinned toolchain the
  executed identity. That was the reason for declining a second executor
  interface alongside the reviewed shim. On 2026-10-25 the user removed the
  dedicated executor from successor scope altogether; neither kind is ported.
  A fielded failure of the old shim does not by itself reopen that decision.
- **Condition records on supplemental inputs or workspace declarations.** The
  decline stands with its reason updated 2026-10-25: a narrow, attributed hold
  on identified custody material supplies the disposal restriction. Separate
  generic condition mechanisms would duplicate it and would not establish
  which captured copies they constrain. The general manager-resource form is
  deferred with that service.
- **A right to receive distinct from the commission.** The commission remains
  authority for the manager to receive the return; limiting direct access to
  live audit material does not revoke that authority. The earlier rationale
  that the manager could read everything directly describes the Python
  baseline, not the successor's intended access boundary. No separate
  receiving party or delivery service has been selected, and segregating at
  capture would break raw capture before interpretation. The
  only truthful residue, an auditor-declared claim that the commission does
  not authorize receipt of something, is a declaration-schema question.
