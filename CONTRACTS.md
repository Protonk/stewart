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

**The manager controls what survives by default; undertaken obligations
survive the manager's close.** That control does not extinguish obligations
Stewart has undertaken concerning particular material: a resource Stewart did
not create is never claimed for disposal; another audit's live use keeps a
resource; retention and export copy bytes to their destinations and never
reference the session, so a retained outcome's promise of inspection does not
depend on the session surviving; uncollected auditor work is not destroyed
without an explicit discard naming it; and a preservation the manager began
and Stewart recorded is completed or explicitly surrendered before conclusion.
Releasing a resource claim when the resource changed concerns the scope of the
authorized act, not a promise to the manager's earlier self. Human auditors,
principals, material providers and later readers acquire no retention rights
from their roles; any they hold come from promises, authority limits or
reliance actually recorded. A provider's condition or a manager's delegation
limit is recorded as a hold on a recorded resource, below; it is a record the
manager makes, not a veto to imagine. Stewart's promises to the auditor are
process promises: raw
capture before interpretation, a disposition of every gap, and attribution
that is never turned into a verdict.

**Liberal in handing over, conservative in destroying.** Stewart gives the
manager verified material with its qualifications attached, and withholds
destruction of material the manager has not judged. The manager's judgment,
not Stewart's, decides what the material means.

## Public status contract

Decided 2026-10-23. **Decided, departure.** Status is the first operation the
successor realizes, read-only against Python-written sessions, with Python
status as the control. The preservation-first extraction order described in
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
record that freezes discard identities is a new schema.

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
| `resources` | Replace live closeout dispositions with recorded association/identity information and record diagnostics. Ordinary status does not evaluate disposal eligibility. `close --plan` and actual close retain that job. No summary confers removal authority. |
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
| Resource evaluation (`status.py:799–803`; `holdings.py:1146–1245,1363–1400`) | JSON disposal dispositions; exceptions become session problems | Normal status reports associations, not eligibility. Close-plan evaluates; actual close evaluates again after session removal, claims exclusively and revalidates. Preserve exceptional error coupling during separation. |
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

Decided 2026-10-24. **Decided, departure.** The Python close at `6582df2` is the
control; `CUSTODY-AUDIT-FINDINGS.md` at `356dc58` records its behavior in the
executed comparisons these rules answer. The rules apply to close's own
assessment, however that assessment is obtained; they do not depend on the
public status view.

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

**Experiment HOME is declared disposable with its identity recorded.** The
attempt HOME is created outside the output area before launch and written by
project code; the experiment contract places output elsewhere. The removed
member is the attempt directory that contains HOME, and the declared category
and frozen identity name that member. Close removes it without acknowledgment
when nonempty and freezes its identity in the closing record. A manager who
wants HOME contents takes them before close. This is a declared category, not
a content judgment; it was chosen over charging an acknowledgment because that
acknowledgment would be of a nominal opportunity.

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
Writer authority, captured evidence validation and frozen resource checks are
unchanged. Handoff damage remains evidence and is diagnosed; it is not treated
as merely unavailable interface.

**Retained, not re-decided.** A damaged retained record that conclusion relies
on, such as a mismatched private handoff or a capture that no longer verifies,
still refuses conclusion, because conclusion deletes the originals. The exit
is abandon with explicit discard, naming the damaged record.

**Which live checks conclusion makes.** Conclusion's live checks are
exactly: writer identity; the checkout inventory against the triaged
collection's receipt; runtime coverage; each recovery against its capture; and
the frozen resource evaluation. A public handoff differing from preparation is
accounted for in the same way as the runtime: when the triaged collection
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

## Project commands as experiments

Decided 2026-10-24. **Decided, departure.** The supported route for running a
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

## Holds on recorded resources

Decided 2026-10-24. **Decided, departure.** A manager may record a
repository-level, attributed, blocking-only hold on any recorded resource.
Close honors it exactly as a live use: the resource is never claimed, the hold
is shown in `close --plan`, show, closeout and the closing record, and it is
released only by an explicit attributed release record, never by a close flag,
a container's retirement or a dispose option. The record carries the actor,
the condition's text and a required limit stating what the hold does and does
not do; its wording says "not destroyed by Stewart", never "returned" or
"preserved against the manager", because Stewart can promise the first and
neither of the others. For an enrolled resource this presents a condition
enrollment already honors, and the enrollment note becomes visible wherever
the hold is. For a Stewart-created resource it is a new commitment: a hold
blocks the manager's own disposal until an attributed release. It leaves
"removal is authorized by two records only" intact, since a hold grants
nothing and is one more reason no claim is created. Release never requires the
named provider, and no close flag acknowledges past a hold; the provider is
named in a record and cannot invoke Stewart.

## Attribution of retention

Decided 2026-10-24. **Decided, departure.** `retain` records its actor as
export and every resource-writing operation do, so that publication of the
deliverable is not the least attributed step.

## Writer continuity into the successor

**Deferred to the successor transition.** The conservative default is that
existing Python writers service their open sessions and the successor is
read-only toward those lifetimes, with explicit verified handoff and no
implicit execution of retained code, compatibility shims or rewritten
receipts. If the successor is to continue old sessions, successor authority
is granted explicitly with its evidence, supported record population and
failure treatment. Expected consequence of the refusal principle: read-only
export of a verified report across writers, with the exporting implementation
recorded in the package, is expected to be permitted when this is decided.
Closing every live Python audit under Python before the successor closes
anything makes the default cost nothing in practice.

## Access and experiment capability limits

**Documentation.** Private-path and effect-authorization obligations are
retained. Their costs are stated rather than promised away: the access scope
is a snapshot, so later checkouts or manager entries can require stopping and
repreparing affected auditors; an HTTPS-only assignment can be structurally
valid while the supplied adapter permits no network domains; the Python
minimal-environment experiment route may not serve a project's real system
checks; project rules reach the auditor only through supplied accessible
guidance. Eliminating the coordination duty needs a different access
arrangement and real harness qualification. External retrieval and project
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
  invasive to the manager's flow, and does nothing for recovery or HOME, which
  are never retained.
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
  need.
- **Charging an acknowledgment for a nonempty experiment HOME.** The
  acknowledgment would be of a nominal opportunity; the identity record serves
  the later reader without the step.
- **Work inside populated submodules.** It would make Stewart create, verify,
  configure, inventory and dispose of a second Git administration per gitlink,
  extend coverage, declarations and the closing schema, and decide the fate
  of auditor commits, in an area Git's own documentation calls incomplete for
  linked worktrees; pinned copies plus an ordinary experiment grant serve
  path-based checks and captured edits. Git-aware tooling inside a submodule
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
  executed identity; reopen only on a fielded failure of the shim route that
  is not merely a cost.
- **Condition records on supplemental inputs or workspace declarations.** The
  hold on recorded resources is the one form; these would duplicate it with
  weaker attribution.
- **A right to receive distinct from the commission.** The manager owns the
  workspace and the disk the report is written to; Stewart cannot withhold
  what the manager reads without it, cannot deliver to anyone else, and
  segregating at capture would break raw capture before interpretation. The
  only truthful residue, an auditor-declared claim that the commission does
  not authorize receipt of something, is a declaration-schema question.
