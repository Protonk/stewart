# Returning an answer and closing an audit

Design proposal, 2026-10-25. The [manager task flow](MANAGER-CLOSE-FLOW.md)
is the short account for discussion. This account supplies its identity,
authority and evidence boundaries. CONTRACTS.md records the decided behavior,
including the subsequently accepted graceless-exit direction below. The other
proposals remain open; no runtime implementation is commissioned.

## Ordinary return and early close

The manager should make preservation and custody decisions, not select a
pipeline of collect, review, withdraw, abandon and recover commands. One
`close` interaction presents only decisions still needed, retaining their
specific attribution and binding. A single command does not make every
request finish immediately.

| Moment | Ordinary return | Close before a return |
| --- | --- | --- |
| Return becomes available | Acquire a fixed publication and expose its verified report with relevant qualifications. Deliver it through the agreed receiving arrangement. Neither event closes the audit. | Record the close request and invoke the commissioned stopping arrangement. Preserve available partial work through a supported acquisition route; no completed report is required. |
| Manager asks to close | Bind the request to the selected audit lifetime and existing return. Establish what can still change before evaluating removal. | Continue the same request after stopping or record the exact missing stop evidence. A stop request alone is not evidence that access ended. |
| Stewart presents outstanding choices | Offer preservation of identified captures; obtain any required gap and follow-up dispositions. Existing decisions apply only to the same collection and material. | Offer the captured partial material, describe omissions and identify any remaining uncaptured material. An authorized explicit surrender names its subject; an unavailable preservation path is recorded as loss, not as an opportunity declined. |
| Stewart finishes | Complete recorded preservation undertakings, honor holds and live dependencies, freeze authorized removal, then revalidate at each removal step. | Apply the same custody rules. Partial investigation is not itself a refusal ground or authority to destroy unaccounted-for work. |
| Result | Closed, or unfinished with a specific supported next step and the available answer still accessible within its custody lifetime. | The same outcomes, with the auditor's claims, stopping observations and capture limits kept separate. |

These are interaction examples, not an instruction to make normal managers
poll status. Ordinary delivery precedes a later close request when the return
arrangement succeeds. Early close must not depend on the auditor producing a
final declaration after access is ended. No new accepted-answer receipt is
proposed. Where the existing contract requires disposition of gaps or a
follow-up request, the close interaction still obtains and binds that judgment;
putting it inside `close` does not silently remove it.

## Graceless exit and the control arrangement still owed

**Direction accepted, mechanism unresolved.** `close --graceless-exit`
requests termination without waiting for the auditor to cooperate or prepare
a final report. Stewart preserves obtainable partial work and continues the
same closing operation. Loss of unwritten work remains possible and capture
limits stay explicit. The flag does not release holds, surrender preservation
undertakings or authorize blanket disposal of uncaptured material.

The present auditor is a Claude Code agent. The user's original arrangement
had a manager agent supply a command, which the user ran while managing the
audit and freeing the manager agent to do other work. An agent can also run
that same command itself. These are both relevant launch paths. The frozen
launcher renders a command; that fact establishes neither a human launcher
nor which participant will retain control. Human-auditor accommodation is a
separate question from who summons this agent auditor.

**Accepted design debt:** before treating the branch as supported, select and
qualify a control arrangement across those launch paths. It must bind the audit
lifetime to the actual run, identify who has stopping authority and a usable
means to exercise it, and account for what termination actually ended,
including tool activity and descendants. Establish how that control survives
the launching participant moving on or losing its reply, and what supported
action remains when control or stop evidence is unavailable. Do not infer
control from the identity of whoever printed the command. No wrapper, service,
process model or new executor has been selected. Paying this debt is part of
realizing the accepted branch, not an optional later enhancement.

## Publication and the material outside it

**Candidate acquisition boundary:** the admitted return arrangement supplies a finite,
identified snapshot of the publication, with a manifest and the corresponding
bytes protected against auditor modification. Stewart pins that version before
acquisition, writes raw bytes into exclusively owned custody storage, and
verifies membership and content before claiming complete acquisition. The
arrangement must demonstrate how it prevents writes through existing handles,
alternate paths and other admitted tools. Renaming a directory, changing a mode
bit, computing a digest or receiving a completion declaration does not by
itself establish that property. A human and an agent face the same boundary.

If a route instead supplies a stream, Stewart can identify and preserve the
bytes received, but must not call that a snapshot of the sender's directory.
That route needs its own finite submission and completion rule before
admission. No concrete harness or transfer route has yet been qualified.

Publication is the return selected for acquisition. It is not the complete
removal inventory. A notebook, unsubmitted draft or other work outside the
publication remains subject to the existing custody promise. Recommend
preserving the existing removal coverage: after ending authorized writes,
account for every audit-owned surface to be removed through a matching
capture, a valid duplicate, a previously declared disposable category or an
explicit named surrender. Publication-only capture must not silently make the
rest disposable. No successor category equivalent to the old experiment HOME
is inferred.

Ordinary publication therefore solves the stable-answer problem without
solving stopping or close by itself. Early close still needs a qualified way
to end writes and acquire partial work. If the arrangement cannot establish
that boundary, Stewart can preserve safely readable bytes with qualifications,
but must retain the affected environment and name the stopping authority and
needed action. Unsupported stopping arrangements cannot be disguised as a
generic instruction to stop the auditor somehow.

## A request that survives its reply

Recommend that the invoking integration persist a request reference **before
dispatch**, bound to the audit lifetime and intent. A human interface must
also provide a recoverable reference or explicit discovery from an audit
reference the caller already holds. Printing a new identifier only in the
lost reply does not meet this requirement. Discovery never chooses by recency;
if more than one request is eligible, it presents the explicit alternatives.
Unkeyed calls remain separate requests.

The request records planned output identities before effects. Continuation
verifies and adopts only those outputs. A completed operation whose reply was
lost returns its recorded result. A partly copied publication continues only
against the same fixed version; a changed source produces a separately
identified observation, preserving the earlier fragments and failure. Neither
case grants another investigation.

Additional decisions made during close need exclusive, attributed continuation
records that bind the request, the exact inventory or issue, and the response.
They do not mutate the original request binding or rewrite a refusal. A
decision naming old material is not permission to remove later replacements.
This is a proposed successor protocol, not a claim that the frozen request-key
implementation already supports it.

| Interruption or obstacle | Supported continuation to design | What remains protected |
| --- | --- | --- |
| Acquisition stopped part way | Verify completed planned members, preserve fragments, and finish from the fixed publication if available; otherwise record the gap and obtain its authorized disposition. | Original fragments and their identity; no resampling concealed as the old observation. |
| Export reply lost | Locate the same planned destination and verify its manifest and members. Finish only this operation's remaining writes or report its completed result. | Exclusive destination and earlier failure records; no adoption of an unrelated package. |
| Destination changed or a write is permanently impossible | Preserve partial output. Offer a new explicitly linked preservation destination, or an authorized surrender of the identified undertaking. Account for the earlier operation before close completes. | No overwritten destination or falsely completed preservation. A replacement attempt does not erase the first. |
| Notification failed | Keep the same return available and continue delivery through the named endpoint arrangement. Distinguish attempted notification from receipt. | No fresh audit, fabricated delivery or accepted-answer acknowledgment. |
| Stop cannot be established | Name the recorded stopping arrangement, responsible actor and evidence/action still required; keep the affected environment. Continue through `close` after that condition is resolved. | No inference from silence or a stable report that all relevant activity ended. |
| Removal interrupted or a path replaced | Revalidate the frozen removal inventory and continue only its remaining authorized steps. A replacement requires separate evaluation and explicit authority within the closing interaction. | The replacement, live uses, and the evidence needed to explain what already happened. |
| Hold remains | Preserve the held selection and its required custody dependencies; retire the environment only where its removal is independently safe. Accept an explicit attributed release through the closing interaction when authorized. | Copying alone does not release the original hold. Final custody close remains unfinished. |

The invoking manager/integration owns re-entry after it loses its own reply.
For asynchronous work, Stewart and the receiving adapter need an explicit
resumption contract: retained delivery intent, the endpoint that can resume
the manager, and which party retries after interruption. Merely recording
"notification pending" supplies no such service. Select and qualify an actual
endpoint before promising automatic resumption. For a manually relayed route,
name the relay responsibility and record only what the relay establishes.

## What a portable result can say

First consumer: a manager or later investigator opening a selected exported
result with the original environment and writer unavailable. Its first view
should answer: what question was asked, what material was selected, what was
returned, where the custody evidence comes from, and which claims remain
qualified. It does not reconstruct an executable audit or report current
custody from an old snapshot.

### Inventory of the frozen package format

Source inventory at `6582df2`, unchanged in this checkout. The implementation
is in [handoff.py](src/stewart/handoff.py) (`_export_evidence`, `_package_inputs`),
[collect.py](src/stewart/collect.py) (`_collect`),
[captured.py](src/stewart/captured.py) (`collection_digest`,
`collection_files`) and [triage.py](src/stewart/triage.py) (`_retain`). This inventory describes the
format and selected source paths, not every package ever issued.

| Material | What `stewart.evidence-package/5` carries | Limit for this consumer |
| --- | --- | --- |
| Package and collection identity | Export actor/time and writer identity; source kind, workspace, audit ID, record name and receipt digest; exact source receipt in `source.json`. | Attribution and internal binding are not authenticated authorship. Preserve the receipt identity even for identical report bytes. |
| Selected return | Explicit selected entries with selector, stored member, size and digest. Collection selectors include `REPORT.md` and individual `files.tar:<path>` members. | No automatic report or supporting-file closure: the caller selects them. A reference in a report does not include its target. |
| Original question and selected subject | A collection receipt records the prompt commit and observed checkout/retention information. Captured input bytes may be present when explicitly selected and actually archived. | The exporter does not automatically include the authored question, original assignment metadata or selected subject bytes. A commit identifier does not recover those bytes after the repository disappears. Auditor-edited copies are not automatically the original commission. |
| Capture qualifications | The exact receipt includes its recorded errors, declaration validation and inventory observations. | Later damage, disposition, holds, releases and closing outcomes are not automatically added. The snapshot cannot claim their current state. |
| Helper assets and runtime observations | Optional complete pristine-assets and observation groups, each verified against the receipt; the manifest always carries runtime identity and asset pins. | Pins alone do not include the groups. Report-only package import still validates the structure of its runtime references. |
| Legacy process material | Attempt packages can select the attempt receipt, ledger, child receipt and streams, plus runtime groups. | They do not automatically carry the release and review bytes needed for richer interpretation. Keep this population outside the first reader assignment. |
| Plain retained files | `retain` copies selected report/support bytes to independent destinations; its retention/disposition records remain in the session. | Those files alone are not a self-contained custody package. Do not market them as one. |

Existing retained comparison evidence confirms the availability asymmetry:
later runtime-capture damage blocked original report-only export while a
previously exported package remained importable. The report and receipt stayed
unchanged. The intact case and initially recorded capture-failure case are the
controls; this is the earlier experiment, not a new run. Its 21 compact
observation copies are rechecked against their retained manifest in
`.scratch/return-custody-design/source-review-01.json`. The original working
fixtures were pruned after review; these copies are observations, not recovered
product packages. The broader package contents above are source findings.

**Proposed successor result:** include captured original commission bytes and
their preparation binding, selected subject identities, the selected report
and support, exact capture/source receipts, relevant qualifications and any
dispositions the view claims to carry. Identify omitted support explicitly;
including a reference does not recursively expand the bundle. A hold uses the
same finite dependency principle. Later hold releases or operation completion
need their later evidence and cannot be inferred from the bundle's age.
This adds a portable-context promise; it needs a contract decision and a new
schema, not rewritten Python packages.

### Helper recovery consumers

The frozen [runtime recovery](src/stewart/runtime.py) and
[manual](src/stewart/resources/README.md#failure-and-interruption-recovery)
describe two consumers:
inspection of retained pristine helper bytes, and explicit selection of those
bytes as the source of a separately authorized fresh assignment. Recovery
never retargets the old audit's commands, grants or releases. Its current
materialized directory has its own captured observation and can later drift.

For inspection, a bounded reader of selected captured assets serves the named
need without adding a mutable audit-owned recovery directory. For fresh reuse,
explicit export of pristine assets supplies the bytes; selecting an executable
source remains a separate authorization. The reader must neither import nor
execute them. This accounts for the documented consumers by source, but no
new export-to-fresh-assignment route was exercised here, and no population of
existing Python recoveries was inventoried. Recommend omitting successor
recovery materialization, conditional on that route's qualification and an
explicit legacy disposition. Do not call its removal decided yet.

## Decisions and the next implementation boundary

The task-flow draft relies on these proposed completions:

1. **One closing interaction carries the outstanding decisions.** Preserve
   exact gap, follow-up, surrender, preservation and hold-release authority;
   obtain it through `close` instead of requiring the manager to choose another
   lifecycle operation. Prior decisions count only for their bound material.
   Ordinary close does not imply a blanket surrender or a mandatory new
   confirmation when all needed authority already exists.
2. **Selected report availability extends beyond export.** Allow the ordinary
   reader to expose verified selected bytes with relevant surrounding damage
   and unfinished-custody qualifications. Required dependency damage limits
   the affected claim. This extends CONTRACTS.md's export-only decision;
   destruction still assesses its whole authorized scope.
3. **A portable result includes the original question and its binding.** Add
   the finite context described above for new exports. Older packages remain
   readable only for what their actual contents establish.

Publication stability, stopping and delivery need a concrete admitted route
and qualification before their stronger promises are adopted. Keep workspace
form, commission fields and custody location open where this account has not
settled them. Do not replace those decisions with an implementation accident.

**Prepared first reader assignment, pending commission:** implement a read-only
Rust custody inspection for `stewart.evidence-package/5` collection packages
with `REPORT.md`, optional captured-file members and complete selected runtime
groups. Take an explicit package location; consult no originating session,
writer executable or live checkout. Report verified selection and exact source
identity, attributed declaration, recorded gaps and absent question context.
Keep unsupported schemas and attempt packages diagnosed without conversion.
No old code execution, export mutation, recovery materialization or inferred
current hold/close status. This is the portable evidence-status slice, not a
claim to implement the larger current-audit status contract. Its placement
(standalone reader or ordinary status subview) needs selection before dispatch.

Qualify that slice with valid evidence at relocated/nested paths after writer
and source loss; damaged selected bytes; damaged required versus unselected
dependencies; identical reports in different collections; missing original
question bytes; repeated control keys; unsupported schema; planted links and
special files. Observe custody-byte immutability separately from whole-host
effects. Use an independent witness outside disposal, with a firing control
and invariance case, and retain it through review. macOS, Linux and actual WSL
acceptance remain separate. No implementation or new behavioral comparison
was run for this design account.
