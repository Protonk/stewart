# Stewart's decided contracts

This is the single current behavioral contract for the Rust audit service.
The design review closed on 2026-10-29. These decisions include the accepted
machine interface; historical conversations and superseded sketches are not
specification inputs. [DESIGN.md](DESIGN.md) explains the system and
[ACCEPTANCE.md](ACCEPTANCE.md) states the evidence required of its implementation.

**Status (2026-10-30): decided and built; the scripted acceptance suite passed
on Linux; WSL2 and real-model qualification are owed.** The Rust audit service
in `service/` implements these contracts. [docs/INTERFACE.md](docs/INTERFACE.md)
and [docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md) specify its exact wire
schemas, record layout, process control and forms within these boundaries.
[apparatus/qualified.md](apparatus/qualified.md) records the latest runs of
the container suites, the source commits they cover and their results. Still
owed: a claim-by-claim check of the suite's coverage against
[ACCEPTANCE.md](ACCEPTANCE.md), native WSL2 qualification and real-model
conformance, which needs named models and a budget. The release's TLS path to
the real provider is unexercised. A design decision is not a passing test.

## Mission

Stewart is a custodian for bounded inquiries between cooperative parties. The
manager supplies a problem in their own words, selected files and an answer
form. Stewart places an auditor in a separate context and returns its answer
with a faithful record. It keeps copies, distinguishes and attributes
observations, acknowledgments and claims, writes records once, verifies
delivery, and states promptly and precisely what it did.

We strive to let the manager attend to the problem rather than the asking.
Orientation, answer forms, stopping rules and exits preserve the auditor’s
latitude. They are readable, versioned, previewed and recorded in returns. The
protocol makes the question, material and recorded answer recoverable.

Stewart must never judge conclusions. Forms must permit no finding, missing
evidence or a wrong question without favoring outcomes. Stewart must show that
auditors can use its arrangements; their authors continually judge their value
as instruments of inquiry, independently of preferred answers.

## Principles and scope

The manager owns the question, material selection, family and limits. The auditor
owns its answer. Stewart owns the arrangement, custody operations and their record.
Keep observed facts, attributed acknowledgments and authored claims separate.
Stewart never turns them into a substantive grade, deadline or verdict. Invocation
outcomes and configured time limits are mechanical facts, not judgments of work.

Stewart's intellectual influence belongs in question families, instructions and
the constrained audit space. An answer must be able to express missing evidence,
uncertainty, disagreement, no supported finding and a challenge to the premise.
Restrictions that privilege substantive outcomes need explicit design deliberation,
even when introduced through schemas or tests. Agreement with a preferred answer
is not a product or development success criterion. Rich selected context is
compatible with a narrow question. Neither more access nor less access establishes
the intellectual utility of an audit.

Refuse only a claim Stewart cannot establish, an act outside its authority, or an
operation inconsistent with an undertaken obligation. Intellectual insufficiency
is not an intake refusal. Give verified material with its qualifications; damage
blocks the claims depending on it, not every independently verifiable selection.
The commission authorizes the manager to receive the return; there is no separate
right-to-receive adjudication. Suggestions and status options are not prerequisites.

Incomplete custody operations remain Stewart's responsibility to account for.
Do not make private-state editing, evidence deletion or guessed repetition the
normal recovery route. Loss despite an undertaking stays loss, never a declined
opportunity. Regenerability is not a substitute for promised retained bytes.
A completed close conceals no unfinished operation. Custody continuation grants
no new investigation. Recording a commission does not promise executable replay.

Records are exclusive, written once and never upgraded in place. Capture raw
attempted calls before interpreting them; preserve invalid bytes and diagnostics.
A complete ledger record establishes an answer effect; a torn tail is evidence
of interruption, not an element. Every gap has an explicit operating disposition
(including unresolved), not a fabricated answer. Preserve source errors when
reporting also fails. Pin the last required check to the value actually published
or used. Use verified, descriptor-relative regular-file reads and exclusive writes;
never follow a caller-planted link or read a FIFO, socket or device.

The product serves a bounded commission and structured return. It does not inherit
the development team's supervision, steering or swarm practices. Managers and
auditors are cooperative but fallible; access constraints make normal operation
reliable rather than claiming protection against a hostile archive owner.

## Platform and auditor access

Ship one statically linked Rust binary for Linux x86_64 and aarch64, without
runtime language dependencies. WSL2 runs that binary. Build, test and experiment
in Linux containers; the development apparatus does not ship. Native macOS is
not a supported target.

Stewart has no version-control relationship. History, diffs, logs and test results
are manager-supplied files, with their authors' attribution. It neither executes
project code nor fetches additional material. The model auditor's world is the
captured question/materials and the tools Stewart supplies: no shell, general
filesystem, project executor, network retrieval or delegated auditing. Stewart
runs the model through its adapter. The only provider network operation is run;
local preparation, acceptance, receipt, status and close need no provider key.
Actual tool/access enforcement requires evidence, not just a constructed setting.

The adapter binds tool calls to the commission. Auditor calls do not select
arbitrary archives, host paths or actors. No manager act-as-auditor route exists.
The auditor sees form instructions and authoring tools, not the family name,
the manager's reason for choosing it or a hidden prior. Host custody paths and
unselected material are absent from its interface. After sealing, closure or
unrepairable damage, stopping is its final route; no further authoring channel
is added. A person adapter is deferred and grants no unqualified access promise.

## Manager preparation and acceptance

**One folder, one acceptance boundary, one close action.** The manager prepares
the question and materials in an ordinary directory, using ordinary tools. Even
when Stewart creates the scaffold, the folder remains the manager's; close leaves
it alone. Preparation does not undertake preservation of its evolving file bytes
or revive the general manager-workspace service. Stewart constructs a separate
captured commission; acceptance fixes that copy, not the source directory.
Later source edits cannot change an accepted commission.

The submission selection is explicit and literal within its defined boundary.
Unsupported entries, collisions and exceeded limits require an explanation and
refusal, not a silently reduced selection. The initial-material contract specifies
layout, text reading, names and limits. Preparation and commissioning are local;
the auditor cannot be launched before acceptance. The ordinary reference follows
preparation through at most one accepted commission and closure; another accepted
commission requires an explicit new reference, even when materials are reused.

**Preparation binds a proposal; commissioning accepts it.** Manager `prepare`
inventories and hashes the question and materials, checks mechanical intake
rules, binds relevant submission settings, and returns a handle identifying the
manifest with a readable account of the selection. Preparation does not accept
the commission or establish custody of source bytes. The instruction to finish
editing and leave the folder unchanged precedes prepare, since hashing takes time.

`commission(handle, I_AM_FINISHED=true)` requests acceptance of that selection.
The acknowledgment means the manager has finished assembling it and will leave
the folder unchanged until commissioning returns. Without an explicit affirmative
argument there is no acceptance. The manager's declaration is recorded separately
from Stewart's observations. Commissioning copies against the prepared manifest,
verifies the captured bytes, and compares a final source scan, including directory
membership, against the preparation. A mismatch prevents acceptance; newer
material cannot silently replace the prepared selection. Changed selection needs
fresh preparation. There is no unprepare action or required inspection pause;
the calls may be composed. Exact CLI spellings are implementation design,
specified in [docs/INTERFACE.md](docs/INTERFACE.md).

These are cooperative interference checks, not proof that the live directory
never changed or that the source had this complete state at one instant. The
receipt identifies what Stewart captured and which checks matched, without
turning the declaration or repeated hashes into an atomic snapshot claim.

**Attempts and acceptance remain distinct.** Copying, verification, recording
acceptance and returning its receipt take time. A complete copy alone establishes
no acceptance. Each attempt keeps its own fixed selection, partial effects and
diagnostics; editing the folder cannot rewrite that intent. A conclusively failed
submission permits correction and another attempt under the same reference.
An accepted handle repeated after a lost reply retrieves the recorded acceptance,
even if the source has since changed. Uncertain acceptance must be reconciled
before a new capture; unavailable or damaged evidence is not evidence of absence.
The storage/publication protocol and supported interruption cases require testing.

**Close before launch ends the reference without making an answer.** Close retires
preparation or an accepted but never-launched commission, accounts for incomplete
intake, and prevents a later launch under that reference. It coordinates with an
in-flight commission so their recorded effects agree. If launch already happened,
the running-audit close rules apply. Failed intake need not be completed
successfully merely to close; actual loss of material Stewart undertook to
preserve remains distinct and cannot disappear under that rule. Retained copies
and records remain governed by their custody obligations. No auditor return,
manager-sealed empty answer or answer-placement confirmation is invented before
launch. Close may itself remain unfinished with a specific continuation through
close, never a requirement to repair Stewart's private records manually.

**Exceptional state has one contextual presentation.** An operational failure
travels with its operation, affected material or record, and underlying cause to
Stewart's presentation boundary. Helpers return diagnostics rather than leaving
independent complaints as the manager's only account. Human and structured replies
identify a stable reason, what Stewart could not do, acceptance as established or
uncertain, known partial effects and retained locations, and a supported next
action. Source access failure, changed selection, failed acceptance recording and
failed receipt delivery are different conditions. An error does not imply absent
effects; a reply failure can follow successful acceptance.

Unexpected errors use the same account with explicit limits on certainty;
implementation defects remain attributed to Stewart. Failure to record a failure
must retain the original diagnostic alongside the recording failure. A diagnostic
delivered to the caller is distinct from one durably retained. Reporting itself
uses fallible operations; process startup failure, forced termination or loss of
every reporting channel may prevent an immediate Stewart response. The calling
interface treats a missing result as interrupted or unknown, and later access
through the same reference reconciles surviving records. No immediate-reporting
guarantee is claimed for those cases. The manager may restore access to its own
folder, but never needs to edit receipts, delete partial captures or improvise
repairs to private state. Qualify this behavior with controlled failures at the
operation boundaries, independent evidence and unaffected comparison cases.

## Initial materials and preparation inspection

**The folder has two entries.** The submission root contains `question.md` and
`materials/`. `question.md` holds the front matter and verbatim question body;
the complete original file is captured as well as the body supplied to the auditor.
`materials/` recursively supplies every contained entry. A material's public name
is its exact path relative to `materials/`, using `/` between components. Host
absolute paths and archive paths are not auditor material names. No extra path
arguments, external-path labels, automatic includes or exclusion rules enlarge
or reduce this set. Unexpected entries at the submission root are refused with
instructions to put intended material under `materials/` or move it outside the
submission. Stewart's own metadata is stored in the archive, not this folder.

**Settings live in the question file's front matter.** It names the family, the
provider model, the run limits, the answer destination and, optionally, an
effort level and the earlier audit this one varies. Prepare decodes it strictly
and binds every setting with the selection. Commission takes only the prepared
handle and the affirmation, and `run` takes only the reference. The auditor
receives the question body, never the front matter. The pinned model serves
every placement of the audit; a release names the models that passed its
conformance gate. An effort level is the manager's choice for that audit alone.
Stewart sends it as a request parameter on every request and never as text the
auditor reads. Without one Stewart sends none and the provider's default for the
model applies; Stewart has no effort default of its own. It knows the documented
level names, not which levels a model accepts, and reports a provider's refusal
as the provider gave it. Run limits are cumulative counts the provider reports:
model turns, input tokens and output tokens. When a response is lost, Stewart
charges a stated conservative estimate and records it as estimated. Stewart sets
no money limit, since prices are not facts it observes. The destination is an
existing directory in which each delivery attempt creates its own new package.

`new` may scaffold an absent folder or use an explicitly supplied existing
folder without replacing its contents. An existing folder's shape is checked at
prepare; neither operation grants removal authority. Another commission requires
another explicit reference, even if it uses the same source folder. There is no
implicit resubmission caused by copying a directory or finding a marker in it.
Only the caller's explicit reference selects work. Moving the source requires
an explicit new reference in this release; old attempts and their diagnostics
stay recorded. The accepted commission remains readable without the source.

Hidden entries under `materials/` are included on the same terms as visible ones.
There are no automatic exclusions for Git administration, build output or editor
backups. Empty files and empty directories are admitted; directory membership is
recorded, including empty directories. An empty material set is mechanically
valid and is not a finding about evidence sufficiency. Symlinks, sockets, devices,
FIFOs and other non-regular/non-directory entries refuse preparation without being
followed or read. Ordinary hard-linked files are admitted as separately named
byte selections; their other links confer no additional access or shared custody.

**The first reader is exact UTF-8 text.** Question and material files must be
valid UTF-8 without NUL bytes. Preserve their bytes, including line endings, BOMs,
empty content and missing final newlines; no transcoding, newline normalization,
OCR, archive expansion, document extraction or execution occurs. Admission is
for raw text reading, independent of filename extension. It does not promise
format interpretation: JSON/CSV/SVG are text, and even a nominal document whose
bytes happen to meet the text rule is exposed as raw syntax, not as an extracted
or rendered document. PDF/image/office/binary readers are outside this release;
the manager supplies a suitable text export when that is what the auditor needs.
Prepare names this reader and its absence of transformations in the arrangement.
Unsupported bytes refuse intake rather than becoming inaccessible attachments.

Names are UTF-8, case-sensitive and retained exactly without Unicode
normalization. Reject control characters in names, absolute names, dot/parent
components and names that collide in the public index. Do not silently rename.
Archive payload filenames are generated identities, not manager-controlled paths;
relative source names cannot traverse archive or delivery locations. Source modes,
ownership and executable bits are not replicated as grants or included in the
content identity. A permission change matters through the actual access and
verification outcomes, not as an automatic changed-content verdict.

Initial bounds are engineering starting values, published by help and recorded
in each preparation/commission. They do not assert that a selected question has
enough context. Changes require a versioned contract and updated boundary tests.

| Scope | First-release bound |
| --- | --- |
| Complete `question.md`, including front matter | 256 KiB |
| Material files, excluding `question.md` | 128 |
| One material file | 16 MiB |
| Total question and material file bytes | 128 MiB |
| Directories under `materials/`, including that root | 256 |
| Material path | 1,024 UTF-8 bytes, at most 32 components, at most 255 bytes per component |
| Text bytes returned by one material read | 64 KiB |
| Material search results per page | 128, also bounded by the reply's text allowance |

Scanning enforces bounds as it goes, not only after allocating an unbounded tree
or file. Overflow, invalid encoding and unsupported entries identify the material
and bound, keep attempted effects accounted for, and establish no acceptance.
Hashing and capture are bounded source reads, with the descriptor and source-change
checks required elsewhere. Permissions and available space are observations,
not promises that later operations will succeed.

`list`, `read` and `search` serve only accepted captured material, never the live
folder or a path mentioned inside a document. List reports the exact index and
sizes. Read returns bounded exact text with its material identity, byte range and
an explicit continuation when more remains; UTF-8 code points are not split.
Line-oriented requests cannot silently drop the tail of a long line. Search is
case-sensitive literal text search over an explicitly named scope, with material
identities and byte positions, bounded pages and explicit continuation/completion.
It is not semantic search or a separate filesystem grant. An incomplete search
cannot be reported as exhaustive absence. Pagination is bound to the accepted
material identities; raw exact-byte readback remains available to the manager.

**Prepare supplies inspection; no separate preview command ships initially.**
The manager reads its question and materials with ordinary tools. Prepare returns
the selection's names, sizes, hashes, counts and limits, and the handle. It also
retains a readable arrangement record alongside its machine representation and
returns their locations. That record contains the exact versioned orientation,
form instructions, stopping instructions, tool definitions and configured limits,
plus bindings to the source question/material selection. It identifies raw text
reading and any truncation/continuation rules. This allows inspection before
commissioning without a mandatory review pause or advisory question grading.

These preparation records are preserved as control records; they are not an
accepted copy of the original input files. Commissioning uses the pinned
arrangement, not whatever the current installation would generate later. A
changed form implementation cannot silently change a prepared commission; it
must either honor that binding through a supported writer or refuse with a next
step. After acceptance the receipt recovers the original question, materials
and arrangement. Built-in help describes available forms and reader limits;
the initial family library and enforcement rules are specified below.

## Custody, retention and manager access

**The manager designates an archive, not a cache.** One explicit storage root
holds Stewart's records for the manager. It is selected when a reference is
created, either directly or through a previously explicit manager configuration;
there is no silently selected fallback store. `new` reports the absolute root,
the new reference and the preparation folder. References bind the store identity
and audit identity; later operations do not select a store from the current
directory, newest record, installation location or newly changed configuration.
Missing or replaced storage is diagnosed, never silently recreated as an empty
audit. Reference identity is not an access credential; actual filesystem access
is still required. Relocation or backup confers no execution permission, and
automatic relocation/rebinding is outside this release's interface.

The designated root is the manager-custodied delivery location for original
commission bytes. Successful acceptance requires those bytes and the acceptance
record to be recoverable there, with verified readback through the reference.
Printing a path or hash alone does not fulfill it. The receipt names the actual
location and custody arrangement; it does not invent another person who has
acknowledged responsibility. The manager is responsible for the storage's ongoing
availability, capacity and independent backup. Stewart is responsible for its
writes, verification, attribution, retention behavior and diagnoses. Local
synchronization is qualified on supported filesystems; this is no replication,
backup, protection against the owner or hardware-loss guarantee. Qualification
kills processes at each publication boundary; durability through power loss
rests on the filesystem's synchronization and is not separately qualified.
Supported archive filesystems are local ext4, xfs and btrfs. The archive needs
exclusive links, advisory locks and directory synchronization, so network, FUSE
and Windows-mounted filesystems such as WSL's `/mnt/` are refused for it. An
answer destination may be on them.

Three locations have separate meanings: the ordinary manager preparation folder;
the designated Stewart archive; and an independently verified answer-delivery
destination. The archive must not be inside the preparation folder, nor the
preparation folder inside the archive. No supported answer destination overlaps
either one. Validate these relationships through the actual opened locations,
not lexical path comparison alone. This prevents intake from absorbing its own
records and delivery from modifying the source or archive. Default creation uses
private permissions for the operating account; permission choices do not change
the recorded custody identity or confer another account's acknowledgment.

**Close ends activity; this release does not delete retained bytes.** Successful
close records the end of that reference, prevents further investigation, and
completes or explicitly accounts for its actual custody obligations. It keeps
accepted originals, arrangement records, attempts and partial captures, failed
stages and diagnostics, ledger records, superseded/deleted answer payloads,
submitted answers, delivery records and closing records. Auditor `delete` changes
current answer membership only. It does not physically erase a payload. Normal
exit, retry, cancellation, close, age and storage pressure authorize no erasure.
There is no prune, purge, automatic cleanup or resource-removal service in the
first Rust release. Storage exhaustion is a contextual failure, never permission
to remove earlier evidence. In-memory buffers and operating-system descriptors
can be released; records and captured on-disk material remain.

Consequently, close does not promise to reclaim disk space or remove the manager's
preparation folder. It also does not depend on keeping an auditor working merely
because bytes remain retained. Readback of retained originals continues after
close; it verifies current bytes and diagnoses damage without rewriting the
historical acceptance. The separately delivered answer remains self-describing
and verifiable without this archive, the original sources or the issuing process.
Its verified placement and any required confirmation are still required; keeping
an internal copy does not silently satisfy delivery to a different destination.

The manager can use ordinary filesystem backup and administration for its own
storage. Stewart does not certify such a copy as verified delivery, authorize
removal on someone else's behalf, monitor external deletion or promise recovery
after external loss. A closed marker is not evidence that all retained material
is disposable under an independently recorded obligation. No live archive is to
be manually repaired, rewritten or partially deleted as an error-recovery step.
Moving/removing it may make its references unavailable; the product diagnoses
that condition rather than starting over under the old identity.

**Holds do not create a new manager workflow in this release.** A hold/release
or generic condition-note facility is declined for this non-removing service:
there is no destructive operation for a new hold to gate. This does not release
existing holds, erase attributed conditions, or turn copying/closure into a
disposition of earlier undertakings. A future deletion service requires a new
explicit contract covering authority, finite selections, dependencies, holds,
verified preservation and failure; none is inherited merely by adding a delete
command. The earlier Python tool's removal protections remain preserved in Git
history for that review.

**The manager's live product interface stays narrow.** `receipt` reads the fixed
commission; `status` states operating and custody facts; `close` ends work. There
is no supported live answer/conversation viewer, question mutation, message to
the auditor, or steering channel. Holding the reference does not expose auditor
authoring tools to the manager. Closed references cannot reopen through a read.

The archive is ordinary local storage readable by its owner, including during a
run. Stewart does not claim enforced secrecy from that owner. The owner can
inspect records with ordinary tools, but this is not a steering interface and
does not authorize edits to the accepted arrangement or ledger. Qualified
operational isolation keeps archive locations and unrelated files out of the
auditor's tool world. It is distinct from filesystem permissions against other
host accounts and from the manager's ability to read its own archive. No
private-location inventory or protection from a hostile host owner is promised.

## Run and continuation

The manager's unit is an inquiry: a line of questions about a concern. Each audit
has its own explicit reference and can record which earlier problem it varies.
Status never chooses an audit by recency. Constructing another question is the
manager's work; retaining one does not imply a restart-from-start facility.

**The escalated run.** Commission and run are separate commands and the line
between them is the network: commission copies, verifies and records locally;
run is the only step that reaches the provider and needs its key. The receipt is
the handoff and carries the reference, the exact run line and what run needs
from the environment. Run takes the reference and nothing else, works from any
directory, needs no session, runs in the foreground by default, and refuses with
a sign when the audit is running or has ended. Status takes a reference and
answers whoever holds it. Stewart records what it observed about each invocation
as observations and never labels who the manager is. Agent harnesses escalate
network commands to a person at their own discretion; Stewart cannot demand or
enforce that and must plan around it without depending on it, so one session may
hold an audit the agent ran, one a person ran on its behalf, and one handed back
and forth.

**An audit is its ledger; a run is one placement.** A run is one placement of the auditor into the arrangement. A run that
dies, through a tool-call timeout, a closed terminal or a provider outage that
outlasts a bounded retry, ends a placement, not the audit. `run` on the same
reference continues the audit: a new conversation, the same arrangement and
ledger, limits counted across runs, and the auditor told that it is continuing
and that the re-entry call shows what it has recorded. Stewart records every
run, status says how many there were, and the return is unaffected. `run`
refuses while another run holds the audit and once authoring has ended: by
submission, by an ordinary ending without submission, by an exhausted limit or
by close. Continuation serves placements that died; after an ordinary ending,
close seals the recorded selection with manager attribution. This
is continuation of one undertaking, not a restart facility: one ledger, one
answer sealed once, limits that never reset, no second investigation. It
settles the restart-from-start convenience left open under the principles as
none. The same continuation is what a person auditor does on returning to the
work, so one protocol serves both adapters. Replaying the earlier conversation
to a model so it keeps its reading is an adapter optimization to weigh only on
conformance-tier evidence that re-reading after a kill is costly; it would
change nothing in the record.

## Answer construction and atomic artifact edits

Successful additions undertake durable custody of the exact recorded bytes and
identity beyond the originating call/process. There is no separate upload or
promotion from disposable staging. Add, replace and delete change current answer
membership through tools; internal staging is not a public draft lifecycle.
Recorded old payloads and failed stages remain retained through close.

Each element has tool-assigned identity/version, exact bytes and an auditor-chosen
label. Labels are not paths or retry identifiers; duplicates are reported, not
refused, and `/` in a label grants no extraction path. Delivered filenames are
Stewart-generated. There is no general answer-history browser or directory/link
artifact. Raw artifact support remains alongside typed family entries; detailed
encoding and tool schemas belong to specification, not implicit text-only scope.
Typed entry kinds organize the selected form and do not certify substantive
claims.

Initial payload bounds remain 256 elements, 64 MiB per element and 256 MiB in the
current selection. At 1 GiB of retained superseded/deleted payloads, edits larger
than 1 MiB can be refused; smaller edits draw on a fixed 64 MiB reserve. Delete,
prepare, submit and manager seal never refuse on that retained-payload cap. Real
storage failure remains possible and must be diagnosed honestly. The spec must
account for reserve exhaustion and record/metadata bounds without silently
weakening these guarantees. No cap permits deletion of retained bytes.

Preparation verifies the current recorded selection, creates its immutable
inventory and deterministic rendering, and returns an inspection handle. It
leaves editing open and adds no lifecycle stage. Submit requires that handle and
defaults to a dry run; only explicit true requests sealing. Revalidate the exact
selected bytes and bind the last check to publication so edits and sealing cannot
race past one another. Success fixes the selection and ends further edits. A
concurrent manager close and auditor submit have one winner with its real actor.
The machine-interface contract below distinguishes the prepared candidate from
the later seal record. Sealing is not delivery, process termination or close.

## Auditor retry and re-entry

**A new addition is a new item.** Repeating add with equal text and labels can
create another element; equality never establishes intent or authorizes merging.
After an uncertain reply, re-entry makes completed effects available for the
auditor to recognize before deciding whether another addition is wanted. It is
not a mandatory stage or permission gate before each edit. This does not promise
that blind repetition of a fresh add is harmless or reconstruct lost intentions.

**Edits respect exact targets.** Replace targets an element/version; an old
target does not overwrite a later revision. A stale-target reply identifies the
current version and supplies its handle and a read/replace next action without
claiming the earlier replacement failed. Repeating a recorded deletion of the
exact target reports that recorded removal without another mutation. A target
replaced or changed in another way retains that distinction; it never deletes a
newer version. Read operations may be repeated without changing answer state.

Preparation binds the exact current selection. Repeated preparation can inspect
that selection; it submits nothing. Confirmed submit with an already accepted
handle returns the existing seal/outcome, including after close, without resealing
or reopening authoring. A sealed/closed reply states the actual sealer and end,
not a request to prepare forever. A manager seal is never reported as an auditor
submission. State and integrity checks still apply to a handle whose acceptance
cannot be established; missing-readable-result is not evidence of no effect.

**One re-entry call restores orientation and access.** It names the audit,
open/sealed/closed condition, current answer revision, cumulative allowances,
question/material access, current element identities and versions, and recent
completed edit receipts. Each receipt identifies its action, target, resulting
revision and completed effect. The latest relevant refusal remains associated
with the operation/revision it describes. These are observations, not inferences
about what the auditor has read, understood or concluded.

The reply is bounded and includes established counts, identities, sizes and explicit
continuations/read handles for the remainder. The question is verbatim when read;
an excerpt cannot masquerade as the whole question. Answer bytes remain readable
by their handles. Pagination is bound to a revision; an intervening edit requires
a refreshed view, not silently mixed versions. No custody path is exposed. This
does not put the whole question and answer in one reply. It preserves recorded
work across compaction/dead-run continuation,
not unrecorded thoughts, a complete model context or fresh investigative limits.

**Redelivering a known result is different from making a new call.** When the
adapter retains an exact invocation identity bound to its arguments and complete
ledger outcome, it can return that outcome without another mutation. A new call
with matching arguments cannot be inferred to be that invocation. Uncertain
effects require their own evidence to be reconciled, not guessed repetition or
promotion of partial data into an answer element. No hidden identifier promises
logical-action recovery after the caller loses the identity connecting its calls.

Expected refusals give the completed effect or unchanged state and the next
ordinary call. Unrepairable damage preserves diagnostics and leads to stopping,
not repeated additions or auditor repair of private custody. Operational failures
remain in Stewart's operating account; they do not become fabricated conclusions
or mandatory answer fields. No retry changes the material world, resets limits,
revives a closed reference or grants another investigation.

## Question families and open inquiry

**The family carries the pairing.** A family brings together preparation guidance,
expected material roles, auditor instructions and answer expectations. These are
where Stewart expresses opinions about asking and answering that kind of question.
The manager chooses the family; a suggestion does not silently change the choice
or rewrite the question. Its versioned instructions and means of answering belong
in the pinned arrangement already available through preparation. Family selection
is not certification that the question is good, its evidence sufficient or its
eventual answer correct.

**Open inquiry is an ordinary family.** It admits a broad request without requiring
the manager to justify avoiding a more specialized family, accept reduced custody
or investigative means, or perform another commissioning step. Its instructions
can ask what was examined, what the evidence supports and what remains unresolved.
Optional evidence modules can add useful prompts and structure; choosing none is
a complete route. Modules are not a second compulsory taxonomy, and any selected
module must be explicit rather than inferred silently from the question.
Modules and their interactions are not first-build requirements; no module
catalogue or composition system is selected.

**Inquiry framing is an explicit task.** This family commissions the auditor to
formulate a working question from the manager's concern and investigate it within
the same commission. The original question remains intact. The working question,
its relationship to the request, the work performed and its limitations are
attributed to the auditor. A precise original question can remain the working
question. This is not a mandatory preliminary audit whose only product is a
better question; useful bounded investigation belongs in the same undertaking
when the material permits it. Inability to do that remains an expressible result.
The choice grants no additional material, tools, budget, investigation or live
approval channel. Other families still allow challenging a premise, explaining a
poor fit or reporting missing evidence; they do not silently acquire this
family's task of formulating a substitute working question.

**Guidance must leave a usable route.** A broad request such as "audit our app to
make sure there are no bugs" can be commissioned through open inquiry under the
ordinary mechanical intake rules. Material-role prompts can expose missing
declared mappings without treating an unmapped role as proof that evidence is
absent from all attached files. They do not force invented evidence or repeated
justification to proceed. Actual invalid references, unsupported bytes and intake
limits remain mechanical refusals. Every family must permit disagreement with
its framing, missing evidence, no supported finding and qualifications; neither
a defect nor a particular substantive conclusion is mandatory. A bounded
assurance remains the auditor's attributed claim, not Stewart's guarantee.

**Initial library and specification.** Open inquiry, inquiry framing and comparison
are the first families. Comparison relates the supplied alternatives to a criterion
and allows unequal evidence or inability without requiring a winner. Its tools
must accommodate observations about one alternative without implying a comparison.
The [form specification](docs/QUESTION-FORMS.md) fixes the exact fields, tools,
orientation and rendering; the [worked examples](examples/questions/README.md)
are valid submissions whose hand-written walkthroughs illustrate expression, not
expected answers. Both work within the settled policy;
neither is permission for a new completeness gate.
No hidden-prior mechanism, larger catalogue or elaborate module composition is
required for this build. Future family admission is separate optional work.

## Readable answer rendering

Preserve the structured answer and its recorded elements. Auditor
preparation also produces a deterministic Markdown rendering from that exact
selection under the pinned form/renderer version. The rendering is available to
the auditor for inspection, without a compulsory inspection pause. The prepared
handle binds both the source selection and these generated bytes; confirmed
submission seals both in the same manifest. An intervening edit requires fresh
preparation under the existing submission contract.

Attribute the rendering to Stewart and the substantive entries to their author;
the seal retains its actual actor. Rendering arranges and faithfully presents the
recorded answer. It does not generate conclusions, fill missing evidence, resolve
contradictions or insert operating history, source materials or a question that
the auditor did not include. The rendering is a sealed member of the return, with identified
Stewart-generated presentation bytes, not an extra post-submission accompaniment.

Delivery and later readback verify and return the stored rendering; they do not
substitute a new rendering from the installed form. A reproducibility check
compares the stored bytes with the result of the pinned rendering rules, without
rewriting the sealed answer. Exact field layout, generated filenames and bounded
rendering mechanics are specified in
[docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md) and
[docs/INTERFACE.md](docs/INTERFACE.md).

Each recorded citation keeps the auditor's operands beside Stewart's own
attributed additions: the source's public name, digest and line span. The
rendering presents the name and lines, so a reader can locate each citation in
any copy of the material and, using the digest, check whether that copy is the
commissioned one. The return does not carry the material; receipt readback
recovers the commissioned bytes.

Close after launch applies the same rendering rule when it seals unsubmitted
recorded work as the manager's. It does not claim auditor inspection or submission.
Rendering failures retain their evidence and never silently omit an owed member.
When close must seal a selection containing an element it cannot read or verify,
the manager seal binds the recorded identities and digests of the whole
selection. The unreadable element and the rendering that depends on it become
named, unproduced members of the return: delivery supplies what verifies, and
the manager may surrender those members under the named-loss rule. Their bytes
are never invented. Close before launch still creates no auditor return. The
later enforcement decision keeps answer-form omissions nonblocking; rendering
adds no completeness gate.

## Auditor form enforcement and prompting

Stewart checks mechanically
interpretable entries and references, makes incomplete form coverage visible,
and gives bounded procedural prompts. It does not certify intellectual completion.

**Entry validity.** Apply the existing contextual refusals to malformed calls,
stale targets, unsupported bytes and exceeded limits. Structured citations must
identify captured material or the captured question body, and an admissible
range. When an explicitly verbatim quote is supplied, its bytes must match that
range. Refuse a mutation
with an invalid locator or mismatching quote, naming the defect, actual effect
and ordinary correction route. A validation refusal creates no answer element;
preserve the attempted call under the raw-capture contract. Recording or storage
failure retains its exceptional-state diagnosis rather than masquerading as a
validation refusal.

Read/search tools supply usable captured-material references; auditors need not
guess offsets. Do not scrape ordinary prose for citation-like text, move a
locator to matching text, normalize a quotation or validate a paraphrase as an
exact quote. Matching references establish no evidential support or entailment.
Accept mechanically valid attributed claims even when their reasoning is poor;
Stewart assigns no substantive support verdict. Supplied reports remain attributed
material, not Stewart-witnessed executions.

**Form expectations and incomplete answers.** Small entry schemas require
interpretable arguments; the form's instructions ask for evidence and limits.
Every family offers ordinary expression of inadequate material, uncertainty,
disagreement and no supported finding without demanding an invented comparison,
winner, defect or repair. Preparation reports mechanically observable omissions
concisely with access to the prepared answer: "No comparison entries are recorded"
is an observation; "the investigation was inadequate" is not.

Missing expected sections do not refuse preparation or submission, trigger a
separate acknowledgment or require a correction cycle. Preserve the existing
empty-answer route. Empty means no recorded answer entries, never "no issues
found" or a claim of completion. The renderer may faithfully expose the recorded
structure but cannot fill gaps or produce a completeness grade. The existing
confirmed submit is the effectful acknowledgment; inspection remains optional.
Invalid, damaged or unverifiable selected bytes still refuse under custody rules.
This deliberately tolerates incomplete and unhelpful returns. Requiring an entry
for every family obligation was considered and declined because it can reward
filler, invented support and loops over how to express inability.

**Bounded prompting.** After an ordinary model turn ends without submission,
give at most one procedural reminder across the audit, if allowance remains:

> This turn ended without a submission. Your recorded answer remains unsealed.
> If you intend to submit it, use prepare and confirm its handle with submit.

The reminder permits the ordinary next response without demanding immediate
submission or another conclusion. Another unsubmitted stop is an ordinary
ending: no further run follows, and close seals the recorded selection.
Continuing a dead placement does not reset the reminder's allowance. Provider
failures, interrupted calls and hard limits are different events, not occasions
to issue this reminder indiscriminately.

Give at most one factual near-limit notice across the audit, tied to a configured
threshold and the allowance Stewart actually accounts for. State the remaining
allowance and that exhaustion leaves an unsealed answer unsubmitted; do not urge
a finding or adequate-coverage claim. Notices and subsequent work use the existing
cumulative budget. Exact threshold and transport are engineering choices. At
exhaustion preserve the work and report its actual state, without an automatic
auditor seal or invented conclusion. Manager close remains available to seal the
recorded work with manager attribution.

## The return and its delivery

The return is the sealed manifest and exactly the members it lists: the recorded
structured answer/artifacts and prepared Markdown rendering. The manifest binds
the audit, family/form and renderer versions, ordered member identities and exact
sizes/digests, writer identity and actual sealer. It is independently verifiable
without the original process, sources or archive. References inside an answer do
not recursively add material to the package.

Stewart does not append the question, receipt, arrangement, access log, run
summary or conversation to the return. Those stay in the archive; operating
refusals/gaps reach the manager through status and records, not fabricated answer
members. Auditor-authored content may of course discuss the question or supplied
material. Stewardship metadata does not certify those claims.

The initial destination is selected with the commission. Delivery publishes its
manifest/selection binding before its members, uses an exclusive new package and
never overwrites or empties an existing destination. An existing path is evidence,
not scratch to clear. Read back and verify every owed member before recording
complete delivery. A partial attempt stays retained with diagnostics; a fresh
attempt uses a new package name. Continuation reconciles the undertaking's own
recorded effects instead of treating a lost reply as permission to copy again.

A verified empty selection produces an honest empty return. For known damaged,
missing or unverified members, provide what can be verified with explicit custody
qualifications and never call the copy complete. Unknown membership is not an
empty selection. Verified delivery, the manager's placement confirmation and
stopped execution are separate facts. The close contract below supplies supported
continuation, destination replacement and narrowly named loss disposition.

## Manager readback, status and close

**The receipt is retrievable.** `stewart receipt REF` retrieves the recorded
commission: the original question, accepted material index, arrangement identity,
grants and limits, recorded intake qualifications and exact run line. It lists
stable item IDs and the readback command for the original question file,
question body, recorded arrangement and each copied input. `stewart receipt REF --read ITEM`
returns the selected item's verified original bytes, not its live source or a
rendering reconstructed with the currently installed form. Raw readback writes
bytes to stdout and qualifications to stderr; ordinary receipt inspection has
human-readable and JSON presentations. The initial receipt and `status REF`
both give this access route. The reference works independently of the invoking
directory or session; inquiry status lists explicit audit references and never
selects one by recency.

Readback is local and read-only, including while a run is active. It exposes the
fixed commission, not the auditor's live answer or conversation. What intake
recorded accepting and what the reader now verifies remain separate facts; a
receipt is not rewritten to reflect subsequent damage. An incomplete commission
is identified as incomplete, never supplied with an invented acceptance receipt.
Missing, damaged, unreadable and unsupported selected records retain distinct
diagnostics. Independently verifiable selected material remains readable when
unrelated material is damaged. Reads name their verification scope and do not
vouch for the whole commission from one valid member. Large readback is
size-bound work with progress outside the byte stream.

This route remains usable after close under the archive retention contract;
it diagnoses unavailable material rather than recreating it. It adds no
removal authority or guarantee against external storage loss. It
does not add commission material to the auditor's return. The manager may keep
the retrieved bytes independently.

**Status answers with distinct facts.** `status REF` gives one short headline
and separately identifies the observed run, recorded answer seal and its actor,
delivery verification and location, and closure. The headline leads with the
facts a manager tracks, in order: commission accepted, auditor launched, answer
sealed and by whom, delivery verified and confirmed, audit closed. Diagnostics
and next actions follow it. The JSON presentation preserves
the same distinctions and diagnostics. A process ending does not establish a
submission; a seal does not establish delivery; delivery does not close the
audit. An empty recorded selection is not the auditor's claim of "nothing found."

| Established condition | Manager-facing answer and supported next action |
| --- | --- |
| Preparation or failed intake, acceptance known absent | No accepted commission; identify the preparation or failed attempt, with preparation/commissioning or close available as applicable. |
| Commissioned, never run | Not started; the receipt supplies `run REF`, or close ends the commission without an auditor return. |
| A run is currently held | Run active, with the observation's evidence; `close REF` can end it. |
| A placement was interrupted, answer unsealed | Interrupted, not submitted; `run REF` continues when the existing limits and run exclusion permit, or `close REF` ends authoring. |
| Run ended normally without submission, or audit limit reached | Run ended, not submitted; `close REF` seals the recorded selection with manager attribution. It does not infer an auditor conclusion. |
| Answer sealed, delivery absent, failed or partial | Answer sealed, delivery incomplete; `close REF` continues copying that same selection. |
| Complete delivery verified and audit open | Return delivery verified at the recorded time and location; `close REF` ends custody on the manager's confirmation. |
| Closing operation incomplete | Close unfinished; show its completed effects, remaining obligation and the exact continuation through `close`. |
| Closed before any auditor launch | Closed without an auditor return; distinguish accepted commission custody from unaccepted preparation. |
| Closed after auditor launch | Closed, with the recorded delivery or explicitly surrendered loss; closure with loss is never complete delivery. |

These are facts to establish, not defaults for damaged records. When a fact
cannot be established, name that uncertainty and its evidence rather than
substituting an empty answer, interrupted run or completed operation. Run counts
and recorded endings remain facts; liveness requires current evidence, never
elapsed time. Status neither probes the delivered copy's current safety nor
launches, repairs, seals, copies or closes anything. Each actionable failure
names a stable reason, retained locations and a supported next action; offers
are not preconditions. No bare "done" hides which undertaking was completed.

**Close continues delivery without another investigation.** After auditor launch,
a run delivers
automatically only after an answer has been sealed. An unsubmitted stop leaves
the recorded selection for manager sealing through close. Close prevents further
authoring, preserves a submission that won the seal race, and otherwise seals
with manager attribution. It reports run termination separately from the seal;
completed close requires the applicable stopping evidence. The mechanism for
reaching a run held by another process has passed the scripted suite on Linux;
its native WSL2 qualification is still owed.

If delivery cannot complete at the commissioned destination, the same interface
accepts `close REF --destination DIR` to continue the copying undertaking at a
manager-selected replacement destination. This changes neither the commission
nor the sealed answer. The new delivery location and its relation to the failed
attempt are recorded before copying. Existing destinations and partial copies
are never overwritten or emptied; a new attempt uses a fresh exclusive package
name and keeps the earlier attempt's bytes and diagnostics. A lost reply is
reconciled against that undertaking's own recorded attempts; an already verified
delivery is reported again, not blindly copied again. This is completion of the
owed delivery, not a general copy service after verified delivery or closure.

Where delivery was already verified when close was first requested, ordinary
close is the manager's affirmative decision about that copy's placement. Where close
first produces the copy, its reply presents the result and a confirmation
reference bound to the audit, seal and delivery record. Confirmation stays
inside `close REF --confirm TOKEN`, is recoverable through status after a lost
reply, and cannot silently acknowledge another destination or selection.
Repeating that close without the confirmation only re-presents the result; the
copy now existing does not turn a repeat into post-receipt confirmation. A
pre-delivery request alone never supplies it. Confirmed repeats return the
recorded closing outcome. No additional report acceptance is required.

Unavailable selected bytes remain a delivery failure even if the destination is
changed. The existing known-selection incomplete-close authority applies only
when the manager explicitly names the undertaking being surrendered, separately
from ordinary placement confirmation. Unknown selection remains diagnosed and
unfinished, never guessed empty or covered by a blanket discard. Neither route
releases a hold or authorizes removal that the applicable custody rules forbid.

Close imposes no auditor-readiness test, waiting period, early-use deterrent or
manager-behavior evaluation. A manager may end authoring without the auditor's
agreement. Placement confirmation is not acceptance of the answer's conclusions.

For a known unsupplied member, name its expected identity, the observed failure,
verified material delivered and exact undertaking being surrendered. Ordinary
confirmation or acknowledgment of a warning does not authorize that surrender.
Unavailable now is not proof of permanent loss. An incomplete close preserves
loss despite the undertaking, cannot release a legacy hold and authorizes no
deletion. Unknown membership stays diagnosed and unfinished; do not invent a
missing list or accept a blanket discard.

## Machine interface

Accepted 2026-10-29. The following semantics are decided;
[docs/INTERFACE.md](docs/INTERFACE.md) specifies exact field spellings and
complete schemas within them.

### One operation core, explicit audience and transport

Use one typed Rust operation layer behind the manager CLI and auditor tools.
Keep role-specific presentation deliberate: shared semantics do not mean identical
payloads. The launched adapter binds an auditor to its commission; an auditor
request does not choose an archive, audit path, actor or arbitrary role. A general
manager `--act-as-auditor` route would contradict the narrow supported interface.
Host-owner archive access remains an existing fact, not a secrecy promise.

For ordinary manager machine commands, use `--json`: one final UTF-8 JSON
reply on stdout, including expected refusals. Put progress and incidental runtime
diagnostics on stderr. Do not require a machine caller to parse prose, ANSI
formatting or interleaved progress to discover the result. Startup/forced-exit/
broken-channel cases may still yield no usable reply; missing output is unknown,
not proof of no effects. Exit status describes the invocation, not audit lifecycle.

Raw exact-byte readback is the explicit exception: stdout contains only the
requested bytes, with qualification kept separate. Auditor bounded text reads
use JSON strings and explicit ranges/continuations. No new daemon, public network
API or event-stream protocol is needed to settle these semantics. Keep complex
structured inputs available through a file or stdin, avoiding shell-quoted JSON
as the only route. Human and JSON views come from the same operation result.

### Small common reply, operation-specific data

Use a versioned envelope with `schema`, `operation`, `outcome` and operation
data. `completed`, `refused` and `failed` are invocation outcomes, never grades
or general "audit done" states. Concrete field spelling remains a spec choice.
Normal edit replies should stay small: exact entry handle, version and resulting
answer revision. Full orientation belongs to re-entry; large manifests and
renderings belong behind read handles and bounded pages.

On refusal/failure add a stable reason, a useful message, established effects and
the next supported call(s). Effects are operation-specific: answer unchanged,
seal recorded, acceptance absent/accepted/unknown, partial copy retained, or
delivery unverified are different facts. A single `changed: false` or global
`ok: false` cannot encode all of them. Raw diagnostic recording may have occurred
even when an answer mutation was refused. Never infer absent effects from an
exception. If recording the diagnostic also failed, preserve both causes and say
which evidence is durable versus merely reported.

Next steps should carry a tool name plus arguments, or a CLI argv array, alongside
the readable explanation. They are suggestions under existing authority, not
auto-execution instructions. Alternatives such as run versus close preserve the
manager's choice. Do not return a blanket `retryable` bit inviting blind repeats.

Auditor errors identify material/entry handles and field locations, not host
paths. Unrepairable custody failures give the auditor a stopping route while
manager status receives the custody diagnostics. The two presentations refer to
the same failure and do not disclose the manager's private operating records.

### Opaque handles bind purpose and exact work

Keep distinct handle kinds for a manager's stable audit reference, exact
entry/version, manager preparation, auditor preparation, prepared member read
and seal reference. They may have readable prefixes, but callers do not
construct, parse, increment or retarget them. Validate audit/store identity,
purpose and version on every use. A handle is neither a filesystem path nor a
new host-owner authentication mechanism. The manager's audit reference carries
the archive's location and identity with the audit identity, so it works from
any directory without configuration. Stewart verifies both on every use and
never treats the reference as a path to records. Material and question sources
are addressed by their exact public names (`question`, `materials/<name>`): a
name reaches only material already in the auditor's world, so it needs no
handle.

The exact entry handle is the edit operand; displayed entry ID/version/revision
help orientation. Display names and equal content never identify edits or retries.
A stale entry handle returns the current handle/read route without silently
reading or overwriting the replacement. Auditor preparation binds the exact
revision, selected entry versions and generated rendering bytes. Manager
preparation binds its different source selection and settings. They cannot be
interchanged just because both operations are called prepare.

Do not invent universal request-key controls. Keep the settled distinctions:
fresh additions are distinct, a known invocation's completed result may be
redelivered by the adapter, and an accepted preparation handle retrieves its
recorded seal/acceptance. Repeated preparation need not produce the same token;
the caller uses the returned handle. Changed bytes require fresh preparation.

### A prepared selection is distinct from an actual seal

Preparation
cannot truthfully record an actual sealer, sealing time or successful submission.
It produces an immutable selection inventory and rendering, with inspectable
read handles. A later seal record binds that selection and records the actual
actor, attribution and operation outcome. It is a new exclusive record, not a
rewrite of the prepared inventory. The prepared bytes do not change at sealing.

The final return manifest can serve as, or reference, that seal record, but must
remain self-contained for verifying its listed members. It includes ordered
members with their exact byte sizes/digests, the exact rendering, audit identity,
form/version binding and actual sealer. Its membership comes from the prepared
selection; there is no second selection step. Identity hashes refer to exact
stored bytes, not a caller's reserialization of an equivalent JSON object.

Preparation/read views shown to the auditor must omit host coordinates and the
manager-only family name. An opaque arrangement binding is sufficient there.
The final manager return manifest can carry the required family/version metadata.
Separate the view from the private record deliberately; do not serialize an
internal struct wholesale because it happens to contain the desired members.

Illustrative field spellings, not a complete wire schema (tokens are symbolic):

```json
{
  "schema": "stewart.reply/1",
  "operation": "prepare",
  "outcome": "completed",
  "data": {
    "prepared_handle": "ap_7",
    "answer_revision": 7,
    "entry_count": 3,
    "selection_view": "view_selection_7",
    "rendering_view": "view_rendering_7",
    "notices": [
      {"reason": "section_unfilled", "section": "comparison", "message": "No comparison entries are recorded."}
    ]
  }
}
```

There is no sealer or "complete answer" grade in that preparation reply. Existing
notices remain nonblocking and require no acknowledgment. An auxiliary observation
count cannot imply a comparison took place.

```text
submit(prepared_handle="ap_7", confirm=false)
  -> dry-run result; no seal
submit(prepared_handle="ap_7", confirm=true)
  -> recorded seal reference, actual actor and bound answer revision
repeat the accepted confirmed call
  -> that same recorded seal, no new mutation
```

Explicit true is required for effect. Use the manager's separately decided
finished-material acknowledgment for commission; do not give a vague universal
`force` flag several meanings. Neither response promises delivery, stopped
processes or close. If manager close won the race, return the actual manager seal
and the applicable ended-state response, not an invented auditor submission.
If an earlier seal cannot be established, expose the uncertainty and supported
continuation rather than guessing that submit failed and preparing again.

### Snapshot reads and exact bindings

Enumerations distinguish the number returned, any established total for the
bound selection, and explicit page continuation/completion. An interrupted or
damaged enumeration does not invent a total for unobserved members. Material
pages bind immutable captured inputs; answer pages bind the observed revision.
An intervening edit produces a stale-view response and an ordinary refresh route
rather than a mixture of versions. Search absence is scoped to what was actually
searched. Read replies return exact text and byte bounds with usable citation
values. Truncation must not masquerade as an entire answer or exhaustive absence.

Response bodies do not imply that the returned state is still current after the
operation completes. Revalidation happens at use. A held prepared rendering can
still be inspected as its fixed selection even if it is no longer submittable;
its handle is not a way to silently read a newer rendering or regain authoring.
Final delivery and readback return the stored sealed bytes, never a fresh render.

### Explicit schemas and conservative interpretation

Use ordinary UTF-8 JSON with one strict control decoder: reject duplicate keys
at every nesting level, unknown request fields, wrong types, nonliteral booleans
and integers outside published bounds. Do not coerce `"true"`, accept misspelled
arguments or silently discard an unrecognized field. Raw attempts are captured
before validation under the existing contract. An integer counter is a bounded
number; an identity token is a string, not a number a caller increments.

Distinguish protocol/schema versions, form/renderer versions, and the writing
implementation identity. Changes to one do not silently redefine the others.
Pin the arrangement and exact stored bytes. Do not promise universal historical
compatibility, negotiate down to a different form, rewrite old records or execute
recorded code. Unsupported data retains its diagnostics. Exact wire schemas and
encoding rules are part of the interface specification, not incidental output
of a Rust serializer.


## Versions and legacy obligations

Every record identifies its writer and schema. Schema, family/renderer and writer
identities are distinct; a matching digest does not imply a supported writer or
authorize execution of recorded code. Verify the pinned arrangement before use.
Unsupported writers/records retain their diagnostics; no silent upgrade, fallback
to current definitions, invocation of recorded code or cross-writer takeover.

**One writer per audit.** The exact binary that created a reference, identified
by its SHA-256, is the only writer for that audit. Another binary, including a
later release, may read supported receipt and status records but refuses every
mutation, including run and close, naming the recorded binary. The receipt's run
line names that binary's recorded path. Managers keep it until its audits close;
an upgrade neither continues nor closes older audits. This was chosen over a
format-compatibility class for simplicity, accepting that an upgrade can leave
open audits waiting for their original binary.

**Earlier implementations are history, not baselines.** A Python audit tool
and a separately scoped Rust commission-bundle binary (`stewart-commission`)
preceded this service. Both were retired on 2026-10-30, when no Python audit
remained open; the Python tool's recorded independent resources were left where
they were, undisposed. Both remain in Git history (the last commit containing
them is `267aaf0`). Neither is a reference baseline, and neither one's test results
are evidence for this service. No old live audit, independent resource, hold,
recovery or partial request is imported into Rust merely because its record can
be read. No historical receipt is rewritten, hold silently released or
unresolved exception called done. The Rust service need not implement a general
Python-record reader or removal service. Any future legacy reader needs a named
consumer, finite supported records and verified claims; interpretation grants no
execution or mutation authority.

## Declined and deferred scope

- No dedicated program executor, Git/worktree/history service or general manager
  workspace service. The manager supplies exported files; a source folder is not
  a resource-disposal grant. Earlier implementation effort does not justify
  preserving those operating stages.
- No restart-from-start, general recovery console or request-key controls for
  the auditor. Continue one interrupted undertaking with one ledger and cumulative
  limits; the manager constructs another commission when that is wanted.
- No collect/deliver/compare stages, routine polling duty, live answer viewer or
  steering channel. Receipt, status and close provide the supported manager
  interaction; comparison is the manager's work on its files.
- No extra report-acceptance receipt, intellectual completeness gate, compulsory
  evidence module or omission acknowledgment. These add pressure or friction
  without establishing custody; placement confirmation has a different purpose.
- No separate preview command or mandatory inspection pause. Ordinary material
  inspection and the pinned preparation records supply the relevant assurance.
- No first-release deletion, prune/purge or new hold/release service. Keeping
  custody scope explicit avoids importing legacy removal machinery. Existing
  holds and independent obligations remain effective.
- No generic legacy reader (see "Versions and legacy obligations").
- No automatic source repair, silent exclusion, regenerated original or current-
  form replacement for sealed bytes. These would change the undertaking while
  claiming to fulfill it.
- No generic additional-copy service after verified delivery/close or monitoring
  of a delivered copy's present safety. Delivery records describe verified events.
- Person transport, hidden priors, a larger family catalogue and elaborate module
  composition are unselected extensions, each requiring its own concrete need.
- Whether read-only inquiry is intellectually useful, and how to admit new family
  opinions on evidence, remain optional studies, not gates on this design.
