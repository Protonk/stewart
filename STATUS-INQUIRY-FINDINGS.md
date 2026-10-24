# Status inquiry: decided contract and evidence

Status: inquiry complete. The coordinator has decided the contract below under
the approved commission, and independent review has no unresolved findings.
Production behavior is unchanged.
The implementation proposal is a separate commission, not an implemented UI.

Source baseline: `6582df2c0fd9f27941b933336f6150d83b3a53fa`, plus the engagement's
plan and consultation documents and the investigative test file. The installed
wheel comparisons selected **31 nodes across two runs: 31 passed, 0 failed,
0 skipped, 0 deselected**, on Python 3.14.8 and Apple Silicon macOS. Evidence and its limits
are described below. No real agent-behavior or harness-enforcement study ran.

## Decision

Normal status will inspect recorded custody and verify the retained evidence
it describes. It will answer what commission is held, which handoff bytes are
retained, what participants acknowledged or relayed, and what has been captured
and reviewed. It will not inspect the auditor's present checkout or supplied
runtime to turn that answer into a fresh readiness assessment.

Ordinary absence of a collection is a fact, not an outstanding task. Default
pre-collection output will contain no launch/probe/collect recommendation.
Recorded exceptions remain visible, with attribution, stable reasons, retained
paths and useful conditional next steps. The interface will not imply auditor
activity, satisfactory progress, guaranteed notification, or freedom from every
other obligation. Status checking does not become a recurring managerial duty.

This is a substantive decision about attention, not only a shorter display.
The same semantics govern prose, JSON and workspace status listings. Underlying
collection, closure, capture and removal commitments remain unchanged. Close
must own the observations it currently obtains indirectly from status before
public status stops making them.

The preferred abstraction is a commission followed by a structured return,
with Stewart handling as much of the relationship as practicable. Current
records support an account of that relationship but do not establish a return
route or deliver a callback. The contract exposes this limit without deciding
that delivery must belong outside Stewart.

## What the investigation established

The motivating question was whether Stewart can answer an occasional inquiry
about commission, handoff and return without making the manager reconstruct
the relationship from the auditor's live execution environment.

**For the recorded relationship, substantially yes.** The session holds assignment
metadata and a pinned prompt identity; the readable commission remains in retained
Git, rather than being included in current status's metadata object. A private
handoff copy is retained; launches and
messages are attributed manager records; collections capture reports and
attributed stop kinds; declarations and dispositions remain distinct. These
records can support useful answers without inferring activity from live work.
The comparison varied launch acknowledgment, a live report, a relayed account,
a harness-exit input and collection at two unrelated/nested workspace paths.
The live report changed no status field; collection changed the custody stage
and supplied the captured report locator and stop acknowledgment.

**For present activity or eventual delivery, no general answer is established.**
A launch acknowledgment does not demonstrate activity. A shell exit records a
process result, not whether the question was answered or someone watched. A
relayed message is text attributed to its recorder, not authenticated delivery.
There is no general structured return-route record in the examined interaction
path. This is a limit of the examined implementation, not an argument against
Stewart eventually taking on more of the handling.

Two important distinctions came from the source work and comparisons:

1. Ordinary absence already yields empty `attention` and exit 0. The conflicting
   signal is `outstanding: ["no complete collection exists"]` plus conditional
   handoff, launch-recording and collection actions. Reducing this conflict does
   not require inventing an existing absence attention reason.
2. Preparation retains private `LAUNCH.md` before writing the public handoff.
   An injected `KeyboardInterrupt` between those writes left the private copy
   and runtime custody with no `PREPARE-ERROR.json`, but no public handoff.
   Private custody cannot certify completed publication. A successfully bound
   keyed preparation outcome can provide stronger historical evidence for that
   request; unkeyed preparation has no universal equivalent. Absence of such an
   optional outcome is not a failure.

Source anchors: `coordination.py:45–126,130–174`; `prepare.py:221,256,285–315`;
`request_keys.py:184–187,259–278`; `collect.py:423–502`;
`status.py:621–646,990–1068,1223–1284`; `launch_profile.py:187–255`.

## Participants and entry points

| Situation | What may be described | What does not follow |
| --- | --- | --- |
| Manager launches and arranges its watcher | Its acknowledgment and later supplied observations | That status must poll, or that Stewart observed the launch |
| Harness pauses for user approval, then the manager resumes | The same manager may retain launch and callback responsibility | That human approval transferred the role or created a separate audit flow |
| Human ferries a launch command | A relayed account of that step | That the person executing it necessarily owns return delivery |
| Human auditor in the desired product | Commission, messages and structured return are meaningful independent of a model/process | That current model/effort fields or one shell exit qualify human-auditor support |

These are relationship distinctions, not a universal interruption policy or
executed harness qualification. The user's optional help remains available for
an actual confusing boundary; no consultation step is mandatory.

The manual's description of a nonzero exit without collection as “the signature
of a launch nobody watched” is unsupported by those facts
(`resources/README.md:970–978`; repeated in a test explanation at
`tests/test_stewart_launch_profile.py:294–295`). Implementation should remove
that inference while preserving the recorded process exit and its diagnostic.

## Public contract

### Provenance and schemas

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

### Attention and options

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

### Handoff access and explicit recipe preview

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

### Workspace listing, discovery, drafts and closes

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

### Concrete examples

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

## Observation, consumer and diagnostic ownership

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

## Closure preservation and implementation order

The runtime-only comparison isolates a consequential coupling. A triaged,
unchanged checkout had no close-plan refusal. An unrelated manager commit also
had none. Mutating only the exposed runtime outside the checkout made status
emit `runtime_unavailable` and close-plan refuse `close_unverified` (3). A
**test-local** intervention removed just that status attention item; close-plan
then had no refusal. Restoring the runtime also removed the refusal. No close
was executed in this experiment. This establishes the diagnostic dependency;
it does not establish that the prerequisite is desirable.

Preserve current behavior precisely before altering public inspection:

1. Extract shared internal custody reading/verification from public projection,
   using the existing safe readers, `bound_disposition` and `captured.py`.
   Include records whose integrity affects close even if they are historical
   or not its selected collection. Do not duplicate parsers or trust cached JSON.
2. Give close an internal assessment containing custody diagnostics, collections,
   dispositions, all attempts, coordination, retained-publication accounts,
   attributed declarations and its operational preparation classification.
   It automatically observes the live conditions that currently affect close,
   including resource-evaluation exceptions and consequential maintainer/destination
   errors. Also preserve failures currently escaping status construction and
   caught by `_status_view`, including manager-invocation and recipe/command
   validation failures. Equal loaded writer bytes do not alone guarantee the
   cached command launcher still verifies. Preserve the conditions under which
   these validations run and their failure consequences; an unconditional new
   validation could harden a path that previously rendered no command.
   Equivalent validation belongs at close's boundary without requiring public
   options or a public schema.
3. Preserve existing classification and refusal order, including oddities.
   Missing private handoff currently produces code 1, whereas a present private
   copy with mismatch can produce code 3. Runtime-unavailable is considered only
   after other preparation prerequisites. Missing checkout is 3 before a complete
   collection, 1 after. Do not replace this with a stronger universal readiness
   rule. Keep the concluded order: readable assessment, integrity gate, triaged
   collection, hold, unresolved attempts, requested basis, capture, inventory.
4. Keep independent capture/coverage, uncollected-content handling, frozen
   inventory and removal revalidation, fresh resource claim evaluation and
   claim-release-on-change exactly where operations require them. `close --plan`
   shares actual preflight. Compare outcomes, reasons and observed record fields
   before switching public status.
5. Change public projection, schemas, prose, options and normal live-read boundary.
   Apply the same contract to listing; qualify discovery inventory and selection
   output without changing binding/eligibility. Keep explicit profile preview
   and neutral handoff recovery. Then update help/manual/manager guidance.

This is an internal separation, not a public status mode switch, compatibility
shim or new orchestration framework. Source identifiers can be chosen during
implementation; no new architectural layer is required beyond the shared reader
and the operation-owned assessment actually needed by both callers.

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

## Validation and test disposition

The baseline tests are not future expectations for the decided UI. They are
retained sources for observations and should be deliberately updated or retired
when their old behavior is replaced.

| Test family | Disposition when implementing |
| --- | --- |
| Ordinary no-collection `outstanding` and handoff/launch/collect action assertions | Update for neutral absence and empty ordinary options. Keep live-report non-inference, acknowledgment attribution, lifetime/path and no-session-write controls. |
| Live runtime/HEAD gates on status launch suggestions | Retire the default-offer assertions because that behavior ends. Retain/add equivalent mandatory operation tests for close, collect, release/run and recovery; do not replace them with preview tests. |
| Profile pin/override/quoted command/scope tests | Keep validation and executable block controls; update default output versus explicit preview, verify one captured override supplies summary and recipe, including no pinned profile. |
| Failed/incomplete/invalid records, report declarations, captured runtime, disposition and release bindings | Retain the contracts, updating only new public field names and intended attention classification. Invalid and unreadable must not become incomplete. |
| Status/discovery/listing/closed views | Update versioned fields and examples; retain explicit selection and draft/lifetime tests, missing-record diagnostics, closed recovery and finished-close aggregation. |
| Close/resource/coverage tests | Preserve operation outcomes, reasons, failure ordering, closing observations, claim/removal and live-use revalidation. Add differential cases for the extracted assessment, especially preparation-state precedence and exceptional resource errors. |
| `tests/test_status_inquiry.py` | Relationship snapshots become new-contract evidence; runtime dependency intervention documents why extraction is required, then updates to prove public diagnostic removal cannot bypass close. Private/public handoff interruption remains a meaningful provenance control. |

Implementation acceptance must include:

- A firing corruption/invalid-record control that remains visible; ordinary
  absence and a recorded harness failure differ for the right reason.
- Instrumented normal inspection and listing that do not traverse the auditor
  checkout, scan its supplied runtime, or evaluate resource disposal; custody
  capture verification must still fire on damaged retained bytes.
- The same removed live condition detected with its preserved consequence by
  the operation that owns it. Exercise refusal precedence as well as acceptance.
- Repeat reads, irrelevant manager advancement, unrelated/nested workspaces,
  live report changes, explicit lifetime references and no session evidence writes.
- Failed preparation, interrupted private/public handoff publication, partial
  collection, invalid/unreadable completed records, failed release, captured
  declaration versus manager acknowledgment, post-collection and closed recovery.
- Bound manager invocation versus in-process API deployment: qualify any global
  read-only claim separately from session immutability. Current API action
  construction can retain a manager deployment (`_invocation.current`). Preserve
  currently consequential command-render failures at close, not only diagnostics
  that reach the public attention list.

No full-suite run was needed to decide this contract. Implementation would need
appropriate broader regression coverage once extraction and new behavior exist.
No claimed CLI parser/flag reduction, code-volume reduction or test-count saving
justifies this decision; zero immediate internal simplification is acceptable.

## Executed evidence

Run record: [baseline-01.json](.scratch/status-inquiry/baseline-01.json).
Provisioning/build: [baseline-01.log](.scratch/status-inquiry/baseline-01.log).
Actual selection/stdout/stderr:
[baseline-01.pytest.log](.scratch/status-inquiry/baseline-01.pytest.log).
The tested wheel is in `.scratch/status-inquiry/baseline-01-dist/`, SHA-256
`43da134c32731f783f74aff6bfe997a8b8078a899e71f1a264c0fb02a846a94f`.
The runner records Python 3.14.8, selected Apple Git 2.54.0, isolated suite
configuration, staged source identities and actual collected/selected nodes.

Command (the named wheelhouse was already provisioned; the runner installs the
locked requirements offline):

```sh
/opt/homebrew/bin/python3.14 -I -B scripts/check.py \
  --wheelhouse /Users/raccoon/Desktop/Experiments/stewart/.scratch/wheelhouse \
  --result /Users/raccoon/Desktop/Experiments/stewart/.scratch/status-inquiry/baseline-01.json \
  --keep-artifacts all \
  tests/test_status_inquiry.py \
  tests/test_stewart_status.py::test_missing_corrupt_and_partial_records_stay_visible_without_repair \
  tests/test_stewart_status.py::test_status_distinguishes_absent_receipts_from_present_invalid_receipts \
  tests/test_stewart_launch_profile.py::test_launch_block_appends_the_harness_exit_and_status_reads_it \
  tests/test_close.py::test_concluded_close_refuses_until_the_audit_is_finished \
  tests/test_verified_capture.py::test_a_concluded_close_needs_a_verified_capture_whatever_the_triage_says \
  tests/test_stewart_runtime.py::test_changed_runtime_cannot_suppress_raw_report_or_claim_clean_collection
```

The selection expands to 30 nodes, including four new investigative nodes,
parameterized invalid-receipt cases and six verified-capture cases. Counts:
30 collected, 30 selected, 0 deselected, 30 passed, 0 failed, 0 skipped;
pytest and runner exit 0; test time 30.71 seconds, total 33.056 seconds.

Thirty-eight actual JSON/prose outputs from the four investigative nodes are
copied, byte-for-byte with source/node/digest mapping, into
[baseline-01-evidence/manifest.json](.scratch/status-inquiry/baseline-01-evidence/manifest.json).
They are observations, not executable instructions or a recoverable evidence
package for the fixture audits. Absolute paths in them describe the run; their
continued existence is not implied. Key groups:

- `test_status_inquiry_relationsh0/` and `test_status_inquiry_relationsh1/`:
  ordinary, acknowledged,
  live-report, relayed-account, harness-exit, listing and collection views, plus
  instrumented Git/runtime read observations.
- `test_status_inquiry_close_runt0/`: baseline, unrelated manager advancement,
  runtime-only change, test-local diagnostic omission, restoration.
- `test_status_inquiry_private_ha0/`: interrupted publication and retained record
  inventory proving private custody does not establish public publication.

After independent review, `scripts/prune.py --run status-inquiry/baseline-01
--apply` removed the working artifacts. The removal is recorded by
[baseline-01.pruned.json](.scratch/status-inquiry/baseline-01.pruned.json), with
[command output](.scratch/status-inquiry/baseline-01-prune.out). The run receipt,
logs, wheel and verified evidence copies stay with this findings document.
No historical run or receipt was rewritten.

The recorded harness failure in the new test is a planted observation input.
The selected existing profile test executes a stand-in shell harness. Neither
qualifies a real provider's permissions, callback or notification flow. The
relayed approval/watcher text is synthetic and deliberately remains attributed
text; it does not demonstrate a real approval continuation. The live-report
comparison establishes field invariance, not absence of every read; separate
instrumentation establishes the baseline's Git/runtime observations.

A review-prompted comparison ran separately as
[render-boundary-01.json](.scratch/status-inquiry/render-boundary-01.json), with
[build log](.scratch/status-inquiry/render-boundary-01.log) and
[pytest streams](.scratch/status-inquiry/render-boundary-01.pytest.log):

```sh
/opt/homebrew/bin/python3.14 -I -B scripts/check.py \
  --wheelhouse /Users/raccoon/Desktop/Experiments/stewart/.scratch/wheelhouse \
  --result /Users/raccoon/Desktop/Experiments/stewart/.scratch/status-inquiry/render-boundary-01.json \
  --keep-artifacts all \
  tests/test_status_inquiry.py::test_status_inquiry_close_depends_on_manager_command_rendering
```

It collected and selected 1 node: 1 passed, 0 deselected, failed or skipped;
pytest and runner exit 0. Test time was 1.31 seconds, total 3.681 seconds. The
tested wheel digest is identical to baseline-01. Four diagnostic/plan outputs
are retained with their source/node/digests in
[render-boundary-01-evidence/manifest.json](.scratch/status-inquiry/render-boundary-01-evidence/manifest.json).

An unrelated note beside the manager launcher did not affect close-plan.
Changing the cached launcher while keeping loaded writer code unchanged let
the explicit writer check pass, but status raised `launcher_mismatch` during
command generation; close-plan converted that into `close_unverified` because
`_status_view` could not obtain a view. Restoration removed the refusal. This
confirms a wider dependency than attention items alone. No command from the
damaged launcher was executed, no close occurred, and the session was unchanged.
After review, `scripts/prune.py --run status-inquiry/render-boundary-01 --apply`
removed its working artifacts, retaining evidence copies and run records:
[pruning record](.scratch/status-inquiry/render-boundary-01.pruned.json),
[command output](.scratch/status-inquiry/render-boundary-01-prune.out).

## Independent review and resolution

Two source researchers supplied complementary public-surface and dependency
maps. A third agent independently reviewed the integrated contract, inspected
the consequential source paths, checked baseline's 30/30 result and all 38
initial evidence-copy hashes. It identified two medium concerns and one small
completeness gap: deterministic stage precedence, the full close error boundary
including command-generation failures, and destinations for every retired
`outstanding` fact. There were no critical/high findings.

The coordinator supplied the stage/diagnostic precedence and migration tables,
preserved the conditional render-error consequences in the implementation
boundary, and ran the additional one-node comparison above. Self-review also
made readable commission retrieval explicit rather than implying current
assignment metadata contains prose. The reviewer checked the revisions, the
new run receipt and test-source identity, and all four additional copies against
both their hashes and original files. It reported all findings resolved and
the contract decision-ready. The coordinator accepted that disposition after
integrating the corrections. Review did not implement the contract or qualify
actual harness behavior.

## Reserved questions and implementation recommendation

These do not prevent the decided public contract and are not silently resolved:

1. **Concluded-close readiness obligations.** Should current supplied runtime
   and public/private handoff readiness block conclusion after sound capture and
   triage? Should failures of public command construction also determine
   conclusion when writer identity otherwise matches? The existing coupling,
   conditional execution and refusal precedence remain operative. Stage 2
   should examine their independent purpose and consequences.
2. **Offer versus direct-close basis.** Should direct close require the newest
   complete collection to be triaged and prohibit pending retention/release/run,
   or should those remain advice? Preserve current behavior; stage 2 owns any
   responsibility change.
3. **Proof of preparation completion.** A universal final publication receipt
   could support a stronger historical statement than retained private handoff.
   Making it a new required custody record is not authorized here. Optional keyed
   outcomes must not become a de facto requirement or rewrite historical sessions.
4. **Delivery and human participation.** Which return arrangements Stewart
   should describe, require, establish or deliver, and how human auditors fit
   the present acknowledgment fields, remain product decisions. No external-only
   boundary or new watcher requirement follows from this inquiry.

I recommend deferring production implementation until the stage-2 review has
considered the first two couplings. Exact preservation is feasible, but it
requires separating substantial operational observation from public status;
implementing and then immediately revising those responsibilities has a real
cost. This is an implementation sequencing recommendation, not a retreat from
the decided contract or an assertion that current behavior should survive Rust.
If earlier Python benefit is prioritized, the ordered preservation-first plan
above is the coherent bounded implementation; a prose-only cleanup would leave
the JSON instruction surface and operation coupling unresolved.

The inquiry establishes the current information and dependency boundaries and
a justified public contract. It does not establish fewer manager interruptions,
reliable eventual delivery, real harness enforcement, universal human-auditor
support, Linux/WSL qualification, or implementation of the new contract.
