# Auditor simplifications and the manager discussion

Collected 2026-10-27 at the user's request, after authoring-boundary commit
ea31c37, then updated with the manager decisions below. The user wants manager
interaction simplification to follow auditor interaction simplification. Accepted
directions are distinguished from remaining discussion; no implementation is commissioned.
[CONTRACTS](../../CONTRACTS.md) remains authoritative.

## Auditor-side commitments

“Decided” here means intended successor behavior. The separate prototype supplies
bounded local process evidence for its editing/submission mechanism; no installed
audit service or real auditor notification is qualified by those 72 cases.

| Simplification | Work it removes from the auditor | Standing and evidence |
| --- | --- | --- |
| One recorded answer, edited with add, handle-based replace and delete | No draft-status stages, separate promotion into custody, or second upload at submission. | Decided; atomic membership/identity changes checked in the prototype. |
| Successful add leaves exact held bytes and identity | No need to keep a helper alive or preserve the source path for later readback. | Decided; source-loss and fresh-process controls passed. |
| Tool-generated identity and mechanical metadata | No manually assembled manifest/envelope whose malformed control fields defeat an otherwise usable artifact selection. Invalid operations refuse early. | Decided direction; generated identities/manifests and malformed-control refusals checked. Full answer representation remains open. |
| Independently callable prepare, then submit of its issued handle | The tool verifies and describes the exact selection. The auditor can inspect it without entering a prepared lifecycle state. | Decided; preparation leaves editing open and any edit makes the old preparation stale. |
| Submit defaults to dry run; explicit true ends edits atomically | No separate finalize/release/upload sequence. A repeated confirmed submission identifies the same outcome after a lost reply. | Decided; dry-run invariance, finality, races and lost replies checked. |
| Integration-owned interrupted-operation accounting | No private-state repairs or routine resolve/resume/cancel authoring stages. The original operation's authority and identity survive interruption. | Decided direction. Retrying an addition through add and actual delivery of its interruption notice remain proposed/untested at the auditor interface. |
| Dependency-scoped verification | Damage to an unrelated attempt or unused preparation need not force a reset of an otherwise verifiable answer. Chosen submitted dependencies remain checked. | Implemented and independently checked in the prototype; preserve this distinction in product integration. |
| Protected repository-associated custody; old payloads held until authorized close | No author-managed custody directories, disposal of replaced bytes, retention toggles or promised version-history workflow during editing. | Decided direction; actual access enforcement, placement and close integration remain unqualified. |
| Mechanical admission preserves permitted intellectual responses | Partial findings, missing support, no supported finding or a reframe need no invented “successful answer” claim. Stewart does not grade utility or agreement. | Decided principle; exact question/answer restrictions still require deliberation. |

Related earlier simplifications also constrain the design. The successor has no
dedicated program executor or manager-operated construction/review/release/run
stages; auditor tool use stays within the commission and actual grants. The
product relationship is a bounded commission and structured return, with
investigative latitude rather than routine live supervision. Positive access
grants are the direction; eliminating a private-location inventory still needs
actual enforcement evidence. These commitments are in
[the principles](../../CONTRACTS.md#principles),
[execution direction](../../CONTRACTS.md#program-execution-and-the-legacy-experiment-route)
and [access direction](../../CONTRACTS.md#access-through-explicit-grants).

## Proposals and unfinished work kept distinct

- A custody ledger backed by retained payloads is a candidate mechanism. It is
  neither an adopted public history API nor proof that a notice reached an auditor.
- Ordinary add can be the retry surface only if its operation identity survives.
  A missing reply can hide a completed addition; identical bytes do not identify
  a retry. Actual delivered notices and supported re-entry remain to be proved.
- Recording a commission does not promise audit replay. Zero audit retry facilities
  is the first design to explore; at most one restart convenience remains open.
- Submission fixes an answer. Delivery, stopping, environment retirement and final
  custody close remain separately evidenced responsibilities.
- Full human handback and material outside the authoring tool remain design work.
  The simplifications do not surrender partial-work custody or authorize automatic
  workspace disposal.

The [prototype result](RESULT.md) and [authoring-boundary note](AUTHORING-BOUNDARY.md)
own the detailed evidence and remaining auditor proof. That proof is not a
prerequisite for beginning this manager discussion.

## What follows for manager interaction

The same division of work should apply: participants express their question,
answer and consequential choices; Stewart owns mechanical recording, preservation
undertakings and supported operation completion. Simplifying the auditor must not
transfer envelope repair, phase diagnosis, manual capture or retry deduplication
to the manager. Internal records can be detailed without becoming mandatory
manager actions. Custody failure still needs an intelligible supported next step.

Several manager simplifications are already decided:

- A standard commission receipt gives the original question and selected bytes an
  explicit reference. The manager need not reconstruct the conversation or enter
  the live workspace to recall the commission. C implements the bounded input leg.
- Routine supervision and live workspace inspection are outside the intended
  commission/return relationship. Return access must not silently reopen them.
- One close entry point works across audit states and carries supported continuation.
  The manager need not choose withdraw versus abandon versus recover by diagnosing
  an internal stage. Graceless exit is an explicit mode, not blanket discard.
- General management/removal of the manager's own workspaces is deferred; audit
  close should not acquire that unrelated service.
- Stewart does not judge whether the answer was worthwhile or prescribe another
  audit because the manager dislikes it. Those judgments remain the manager's.

## Manager decisions following this collection

| Question | Current disposition |
| --- | --- |
| 1. What does normal receipt give? | Decided: a durable manager-held copy of the sealed manifest and selected material. Straightforward independent copying is preferred despite space cost. Actual receiving/delivery, destination and packaging remain unqualified; C's input evidence does not qualify output delivery. |
| 2. What if no submission finished? | Decided for recorded unsubmitted work: manager collect may itself end authoring and produce the fixed manager-collected return. Carry that authority through Rust; early-use policy intervention is deferred beyond the near/medium term. Other incomplete cases, physical stopping and work outside the helper remain for design. |
| 3. What decision remains before ordinary close? | Decided: the manager asks whether its durable copy is somewhere safe and affirmatively closes, knowing audit-held copying will cease. No additional routine acceptance, follow-up, retain/export or backup-proof step. Existing exceptional obligations remain distinct from this completed normal path. |
| 4. How does an interrupted manager return? | Decided interaction: help, status, then normal audit actions, with explicit audit/operation identity and supported continuation. CLI syntax is illustrative. Read-only status offers factual context; it neither guesses a selected audit nor imposes polling or certifies present backup safety. |

The ordinary path is now commission, durable return, affirmative close. Making
another copy of the same sealed return remains supported before close. Stewart
owns verification of its copying; the manager owns placement and later safety.
Close ends audit custody and the ability to request its copy again, while the
manager-held copy remains independent. This changes the normal successor workflow;
it does not rewrite frozen Python or claim implemented delivery.

No-submission return, a failed copying undertaking, an active hold or unavailable
stop evidence must remain explicit. The user's ordinary-path choice is not silent
authority to discard those obligations. Exact authority and presentation for such
cases must fit the simplification rather than restore a routine lifecycle pipeline.

## Manager collection of recorded unsubmitted work

The user first proposed manager-accessible `collect()` for recorded artifacts
after authoring ceased without submit. They then explicitly decided that collect
itself must be allowed to end the authoring opportunity, carrying that authority
through the Rust transition. It does not require prior cessation or auditor
agreement. Implementation and qualification remain pending; this direction does
not itself launch implementation or a trial.

Conceptual input is an explicit audit reference. Stewart selects the currently
recorded elements; it need not obtain a prepare handle from the auditor.
No submitted answer is invented. Intended behavior:

1. Verify the recorded selection and bind one fixed manifest. Required damaged or
   unresolved records retain diagnostics; a pending addition is not silently
   promoted into an acknowledged element or discarded as absent.
2. Atomically seal that collection and end further add/replace/delete/submit for
   that answer. A concurrent submit either commits first, in which case the
   normal submitted return governs, or loses to collection and cannot replace
   it afterward. No competing final returns or changing collected revisions.
3. Attribute the act: the manager requested collection, Stewart fixed/verified
   the recorded selection, and the auditor did not submit it. Artifact content
   keeps its original attribution. This is not an intellectual incompleteness
   judgment or a forged auditor completion declaration.
4. Supply the same durable manager-held copy interface used by normal return.
   The manager can then affirmatively close after deciding the copy is safe.
   Another normal-path collect/triage/retain pipeline is not introduced.
5. A repeat of the same collection undertaking returns or completes that same
   fixed result/copy. An intentionally requested additional copy before close
   still copies that result; it never selects later authoring work.

This function is for recorded unsubmitted material. A normal submitted return
does not need collection. It is not a live-view service, workspace sweep, general
salvage mechanism, close, deletion or audit restart. Those distinctions constrain
its supported claims rather than adding manager-operated phases.

The authority question is settled: collect can end an otherwise live authoring
opportunity. Its irreversible editing cutoff at the fixed-result boundary keeps
it from being a live peek followed by resumed authoring. No inference from silence
or prior proof of ceased authoring is needed. This does not establish that all
processes/tools stopped or authorize environment removal; copying and actual
process-control mechanisms still need qualification.

The user explicitly accepts carrying this decision through Rust without near-
or medium-term intervention against managers collecting early. If later testing
shows frequent early use worth addressing, revisit policy then. Such behavioral
evaluation is not a transition gate and supplies no current justification for
delays, readiness criteria or deterrents. Ordinary correctness testing of races,
fixed-result identity, copying and interrupted operations remains required.

Empty selections, missing/corrupt held bytes, unfinished adds and material outside
the helper are other incomplete cases; this direction does not claim to settle
them. The selected material and remaining obligations must be explicit before
normal close can complete. Frozen Python's collect implementation and its staged
workflow do not determine this successor function's meaning.

## Reading the earlier designs

[The close-flow draft](../../MANAGER-CLOSE-FLOW.md) and
[return-custody proposal](../../RETURN-CUSTODY-DESIGN.md) are supporting proposals,
not additional current contracts. The latter's disposable-authoring-draft and
separate rejected-attempt-stage recommendation predates the now-decided custody
undertaking during authoring. Do not restore that workflow while designing the
manager. Likewise frozen Python's precollection no-channel rules, declarations,
collect/triage stages and executor interfaces are baseline/history, not successor
requirements. Preserve their evidence and outstanding obligations without
requiring their interaction sequence.
