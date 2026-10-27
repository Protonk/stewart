# Auditor simplifications and the manager discussion

Collected 2026-10-27 at the user's request, after authoring-boundary commit
ea31c37. The user wants manager interaction simplification to follow auditor
interaction simplification. This is a synthesis and discussion agenda; manager
recommendations below are not new product decisions or an implementation commission.
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

## Decisions to discuss, in order

1. **What does receiving the return give the manager?** Distinguish access to
   audit-held material from a verified copy in a named manager-held destination
   that survives close. Candidate simplification: choose the normal destination
   once and make successful delivery fulfill that preservation undertaking, so
   the same bytes need no later retain/export decision. This needs explicit
   agreement and a qualified delivery route; reading alone currently establishes
   no preservation. C's input-copy pattern informs this candidate, but its evidence
   does not qualify output delivery.
2. **What is the ordinary return object, including when no submission finished?**
   Candidate: one inspectable result bound to the original commission, selected
   answer/artifacts, their submission status and specific qualifications. Preserve
   auditor claims separately from Stewart's custody observations. Decide which
   unsubmitted/partial material it presents and what stays accessible; keep the
   treatment of work outside the helper explicit. Do not make the full internal
   ledger or obsolete versions the compulsory reading surface.
3. **Which decisions genuinely remain when closing?** Keep the existing single
   close direction. Obtain only outstanding, material-specific choices about
   preservation, gaps/follow-up, holds or surrender. Already recorded choices
   apply to the same identified material. Their presentation can be simplified;
   removing an existing obligation would require a separate explicit decision.
   Submission, receipt or an ordinary close request does not itself release a hold
   or authorize unaccounted removal. Automatic retirement remains undecided.
4. **How does the manager continue after a lost reply or unfinished delivery/close?**
   Candidate: the same ordinary operation and retained reference recover its
   outcome or remaining authorized work. Define the actual receiving/re-entry
   endpoint and the specific outside action needed if Stewart cannot proceed.
   Preserve receipt uncertainty and failed undertakings; introduce no new audit
   execution or family of repair commands. Actual stopping authority remains a
   control-design obligation, not a manager assertion that makes it true.

The candidate normal interaction is: commission the audit, receive and inspect its
return, then close with only remaining choices. These are user tasks, not a chosen
command count or schema. Receiving the normal return need not require requesting
destruction first. The first useful decision is whether normal return delivery
already establishes a durable manager-held copy.

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
