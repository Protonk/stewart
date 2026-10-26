# Stewart's five-stage development plan

Status: the five-stage sequence is agreed; Click integration is dropped.
Stages 1 and 2 are decided. The status contract and the custody decisions are
recorded in [CONTRACTS.md](CONTRACTS.md) with their implementation status; the
findings documents and their run records remain until Rust acceptance evidence
supersedes them, because a run's record leaves with the document that cites
it. Python is frozen as the reference baseline; decided departures are
implemented in Rust. Stages 2 and 3 closed on 2026-10-24. Stage 4, the Rust
transition, opens with a decision round on an external proposal for a narrow
custodial core and files-only workspaces, sharing its inventory with the Git
environment document; the Rust write path waits for those decisions.
This document owns the current sequence, stage outcomes and consequential
decisions. Internal assignments and execution details belong to the coordinating
agent. The [longer-term vision](VISION-PLAN.md) describes the working relationship.

Current checkpoint, 2026-10-25: the user relayed an external proposal, now
`planning/inputs/custodial-core.md`, and agreed to place it inside stage 4 as
an opening decision round before the Rust write path (stage 4 below). The user
authorized that round's inventory and comparisons; whether Rust status starts
alongside it has not been decided. A second proposal for a history-only
profile, `planning/inputs/history-only.md`, joined the same round.
The resumed discussion has since decided deferral of the general
manager-workspace creation/disposal service and a narrow attributed hold on
identified custody material with explicit release. It also agreed the
handoff/closure direction and recorded the effectiveness/seamlessness tension
below. The hold's subject is a finite identified selection with its required
custody dependencies, without recursive expansion. Held-capture closure is provisionally resolved; explicit access grants
are selected with delegated fallback judgment. A bounded legacy transition and
supported evidence interpretation are accepted, without blanket successor
compatibility with Python's operational model. The remaining architectural
choices and implementation commission stay open.
Live-testing retention is being considered to expose missed extraction or
silent loss; the independent test archive is the current recommendation, not
a production cache or post-close recovery promise.
The user has now selected A.2 arrangement 1: no dedicated successor program
executor or staged manager-operated release/run workflow. Permitted auditor
tool use and custody of captured returns remain; execution reports retain
their attribution. Recording a commission without promising replay is an
agreed direction and candidate core commitment. Zero versus at most one audit
restart convenience is still open. Supported resolution of Stewart's own
incomplete operations remains central, especially for agent-managers. The
user requested the next coordinator handoff after this decision; implementation
remains uncommissioned.

Coordinator intake, 2026-10-25: the user strongly prefers a single `close`
command that closes the audit regardless of state, with withdrawal during an
active investigation handled internally if needed. This is the successor
interface design direction. Existing holds and custody obligations still
constrain completion; the manager should not need to select a separate
withdrawal, abandonment or recovery procedure. CONTRACTS.md records the
direction and its unresolved mechanics. No implementation is commissioned.

Current planning priority, 2026-10-25: define return acquisition, availability,
delivery and recovery of identified custody operations before considering an
audit-restart convenience. The user delegated assessment of peripheral advice
and adjustment of this plan to the coordinator. The next design work below
makes stable publication the leading normal-capture candidate, names the
exported-result recipient as the first evidence-reader consumer to specify,
and carries early and interrupted closure through the single `close` entry
point. These are planning choices and recommendations; new custody commitments
still require decision. No audit restart is scheduled for the first successor.

Design progress, 2026-10-25: the user agreed to work through the manager
interaction, inventory portable-result contents, then prepare bounded decisions
and a first reader assignment. They specifically requested a very spare,
human-readable closing flow. [MANAGER-CLOSE-FLOW.md](MANAGER-CLOSE-FLOW.md)
is that proposed task flow; [RETURN-CUSTODY-DESIGN.md](RETURN-CUSTODY-DESIGN.md)
contains ordinary/early-close cases, interrupted-operation continuations,
the frozen package-format inventory and the documented helper-recovery
consumers. Its three proposed completions concern decisions inside `close`,
selected report availability beyond export, and portable original-question
context. None is yet adopted. The bounded Rust package reader assignment is
prepared, not commissioned; its placement and concrete publication, stopping
and delivery routes remain open. The initial account changed neither contracts
nor Python.

Subsequent direction, 2026-10-25: the user accepted adding
`close --graceless-exit` and explicitly recording the control arrangement as
debt to pay. CONTRACTS.md records the branch; RETURN-CUSTODY-DESIGN.md owns
the unresolved control work. The command may be launched by the user or by
an agent, including the manager agent; a printed command does not imply a
human launcher. Bind the actual run and stopping authority across these paths
and qualify what termination ends before promising support. Python remains frozen.
The user's next discussion is a possible radical simplification of the rule
for work outside the stable published answer. Hear that proposal before
advancing the current recommendation; no change to that obligation is yet
decided.

Checkpoint, 2026-10-24: the user decided D1 as six close rules plus
abandon parity, decided D2, D3 (contingent on stage 3's submodule decision) and
D4, deferred D5 to stage 4, took D6 as documentation, declined seven optional
changes with recorded reasons, and chose to freeze Python and carry every
departure into Rust with status as the first Rust operation. The decisions,
the principles behind them and the declines are in `CONTRACTS.md`. The inquiry
materials were committed at `356dc58`. The independent review of the decision
set returned fourteen findings, none blocking; the corrections are applied and
three completions it required are recorded in `CONTRACTS.md` as proposed,
awaiting confirmation. The later-return comparison then executed
(`.scratch/custody-audit/later-return-03`, 6 of 6 passed) and refined the
source finding; the resulting rule is a fourth proposed completion. Its
evidence was independently reviewed and its artifacts pruned. `CONTRACTS.md`
is linked from AGENTS.md and shipped in the source distribution, validated by
`.scratch/contracts-link/distribution-01` (10 of 10 passed, wheel digest
unchanged). Riker's reply on the two general commitments arrived and is
retained at `riker/CLOSE-COMMITMENTS-REPLY.txt`; it adds a fifth proposed
completion and three proposed revisions to the principles, recorded in stage 2.
The user confirmed the five completions and the principle revisions;
`CONTRACTS.md` records them as decided and stage 2 is closed. Stage 3 was
commissioned, investigated, reviewed and decided the same day: the user agreed
to `CUSTODY-ADDITIONS-FINDINGS.md` as recommended, and `CONTRACTS.md` carries
its acceptances, declines and deferrals. Stage 4 is next.

Checkpoint, 2026-10-23: `STATUS-INQUIRY-FINDINGS.md` records the decided
contract, concrete examples, observation/consumer map, preservation-first
implementation outline and limitations. Two source researchers and independent
review contributed; every review finding is resolved. Installed-wheel runs
`.scratch/status-inquiry/baseline-01.json` and `render-boundary-01.json` selected
30 and 1 nodes respectively, all passed: 31 total, 0 failed, 0 skipped,
0 deselected. Forty-two verified JSON/prose evidence copies, logs, receipts and
wheels are retained with the findings; only working artifacts were pruned via
`scripts/prune.py`. No production behavior changed. Stage 2's account is in
`CUSTODY-AUDIT-FINDINGS.md`: three source investigations, four investigative
test files and coordinator synthesis cover closure/recovery, commission/execution,
evidence/identity and Git trust. Its first installed-wheel run selected 26 nodes:
25 passed and one probe-configuration error failed before the intended operation.
The corrected probe's three controls all passed in a fresh run. Thus 26 distinct
nodes now have passing evidence; neither the failed run nor its cause is hidden.
Independent review verified the outcomes, all retained copies and their hashes;
its findings are resolved. Ninety observation/fixture files and eight staged
inquiry-source copies remain with the receipts/logs/wheels. Only working artifacts
were pruned through `scripts/prune.py`; the report cites both removal records.
Changes to custody obligations and production
implementation remain reserved.

## Purpose and authority

Develop Stewart while shifting routine development coordination to one
high-level agent. The user sets direction, authorizes consequential semantic
changes and assesses the integrated result. The coordinator investigates,
organizes agents and workspaces, reconciles findings, integrates authorized
changes and verifies them. Choose delegation and providers according to the
work; the user should not have to broker worker communication.

Distinguish foundational properties, custody and control arrangements open to
examination, and incidental implementation details. Start from the mission and
the intended distinctions between commission and execution, custody and
correctness, permission and availability, completion and a substantive answer,
and successful work and recoverable failure. Compare design expectations with
repository evidence. Existing behavior is evidence to examine, not proof of
its desirability. Existing contracts remain operative until a change is
authorized.

Keep the current semantic decisions and open questions here during the program.
Accepted contracts eventually belong in maintained documentation and tests.
At a stage boundary, review a concise account of the result, its evidence,
important disagreements and the next commission. Ordinary implementation and
coordination choices remain with the coordinator inside that commission.

## 1. Investigate custody-focused status

**Outcome:** normal status will describe and verify recorded custody, with
neutral absence and no default pre-collection launch/probe/collect options.
Private handoff retention does not certify publication, activity or delivery.
Exceptional records retain their diagnoses. Close will own its existing
operational checks and conditional construction-failure consequences before
the public view stops making them. The findings contain the full decided
contract; its implementation and any reserved obligation changes remain separate.

**Implementation decision, 2026-10-24:** Python implementation is declined.
Status is the first operation the Rust implementation realizes, read-only
against Python-written sessions, with Python status as the control. The
findings' preservation-first extraction order applied to a Python
implementation and is not required. The four reserved questions are disposed:
concluded-close readiness obligations under stage 2's D1 rules; offer versus
direct-close basis as advice kept separate from preconditions, with the
later-return rule pending; proof of preparation completion declined; delivery
and human participation carried to stage 3. The decided contract now lives in
`CONTRACTS.md`; the findings retire when the Rust acceptance evidence
supersedes theirs.

Determine what status should establish between preparation and collection,
and which live validations belong to operations such as collection and close.
Use [the retained CLI-reduction inquiry](planning/inputs/cli-reduction.md) as
source material. Its old branch instructions are historical; this program
sets the sequence and authority.

The first useful result is a decided public contract with concrete prose and
JSON examples, an observation/consumer map, diagnostic ownership, an ordered
implementation proposal and discriminating validation. Keep the investigation
bounded; run focused comparisons where source inspection cannot settle a
question. Distinguish observed behavior from hypotheses about agent behavior.

Treat ordinary absence of a collection separately from failed preparation,
partial collection and invalid or unreadable records. A field keeps its
meaning and provenance across stages. Account for workspace listings, offered
actions, exit codes and operation callers. Necessary custody checks must have
explicit owners; reducing status output must not silently weaken close.
Preserve access to the issued handoff without inferring auditor activity.

### Agreed product direction

The user wants Stewart to answer a status question about an unclosed audit,
while checking status is not part of the manager's ordinary job. The manager
should treat a handed-over audit as a promise of an eventual structured return.
Audit duration can vary for many reasons; ordinary absence of a return does
not create a recurring responsibility to inspect progress or intervene.
An explicit request for status should receive a useful account of what Stewart
can establish, without treating the passage of time as evidence of a problem.

This is a product design preference. The user's motivation includes giving
persistent managers an answer so they need not devise ways to inspect a live
audit. Whether the design actually discourages that behavior remains an
untested hypothesis; no agent-behavior study is requested. The user accepted
assessing the product's output, offered actions and manager guidance against
this preferred relationship, with custody-focused status as a candidate means
of expressing it. The inquiry can recommend retaining justified observations.

Stewart should abstract the connection between manager and auditor as far as
practicable, handling as much of their interaction as possible through the
promise of a structured reply. The ideal should accommodate a human auditor.
No fixed division placing delivery outside Stewart has been selected. The
inquiry should identify how existing handoff and return arrangements support
this direction and expose gaps, without assuming one execution mechanism.

Entry points can differ. A manager's harness may prohibit starting the auditor,
so a human may need to ferry the launch command. It may instead pause for user
approval and then let the same manager resume its launch and watcher flow.
User involvement in approval does not by itself transfer execution or callback
responsibility. The user's experience of that pause may differ substantially
from the manager's continuation. When a manager starts an audit, the user
expects it to arrange a watcher and own how it is called back. Stewart should
remain agnostic about these arrangements; its status design need not determine
the surrounding harness's approval flow. These are relationship examples, not
executed qualifications of any harness. A callback/watcher here concerns
notification of a return or failure, not authority for recurring inspection,
live editing or steering of the inquiry.

Clarified 2026-10-25: the bounded commission and structured return are a
positive product choice for users who want narrow questions and answers.
Surrounding launch and callback arrangements do not make routine steering or
general agent supervision Stewart product objectives. The development fleet's
practices do not determine the product relationship. Rich selected context
and investigative latitude remain compatible with a narrow question.

The policy for pre-return intervention remains open; the coordinator's
suggested list of exceptions has not been adopted as an exhaustive rule.
A substantive answer, incomplete work and a failure can all need an intelligible
return, but precise delivery responsibilities and supported mechanisms remain
open. If a report or scenario makes the manager/auditor/user boundary confusing,
the user offers optional, fallible help. Consult them when useful; this is not
a required review step or a reason to hand back routine coordination.

The inquiry includes whether Stewart exposes enough of the commission, handoff
and return relationship to answer an occasional inquiry without reconstructing
it from the auditor's execution environment. The user identified this question
as potentially amenable to empirical investigation. Use focused comparisons to
resolve concrete uncertainties; do not infer improved agent behavior from them.

### Approved commission and delegated authority

The user approved this commission on 2026-10-23:

> Investigate and decide the public status contract, including truthful
> treatment of uncertainty, ordinary and exceptional attention, and
> already-authorized actions, against our agreed product direction. Explain
> consequential assumptions and investigate dependencies. Preserve existing
> custody and closure commitments. Bring back separately any necessary new
> obligation, transfer of authority, delivery guarantee, execution responsibility,
> removal power, or loss of evidence. Implementation remains separately
> commissioned.

The user relayed Riker's reply to the consultation at
`riker/STATUS-DELEGATION-REQUEST.txt`; the supplied reply is preserved at
`riker/STATUS-DELEGATION-REPLY.txt`. This is advisory reasoning, not repository
evidence or the source of authority; authority comes from the user's approval
above. The coordinator accepts its correction: status wording and attention
semantics can create commitments even without a change to operational code.
Presentation versus implementation is not a sufficient boundary for delegation.

The grant includes substantive decisions about attention and actionability,
with investigated dependencies and reasons; it does not require approval for
every classification or field. The boundary concerns commitments: what might
a manager, auditor or consumer reasonably rely on as permission, instruction,
assurance or a reason not to act, and does that reliance follow from the agreed
product relationship and existing authority? A new independent duty, transfer
of authority, delivery guarantee, execution responsibility, removal power,
evidence loss, or changed
custody or closure requirement remains a user decision. Such a dependency can
be investigated and presented separately while independent contract decisions
proceed within the granted scope. Delivery is not presumed to belong outside
Stewart. Implementation remains separately commissioned.

Concrete implications for the inquiry:

- Ordinary absence alone can be treated as creating no new managerial task;
  it cannot establish that work is active, healthy, guaranteed to return, or
  free of every other obligation. Recorded failures and invalid or unreadable
  records need their own account. A global interruption policy remains open.
- Preserving access to a diagnostic does not by itself preserve a safeguard.
  Trace its consumers, automatic or optional execution, timing, required
  transitions and consequences of omission. Any relocation must preserve the
  relevant commitments or expose the responsibility change for decision.
- Describing a known return arrangement differs from requiring, validating,
  establishing, supervising or guaranteeing one. A truthful answer that falls
  short of the desired abstraction can expose a substantive gap; wording must
  not invent the missing arrangement.

Consultation supplies no approval gate. The commission does not authorize
runtime changes or implementation of monitoring, notification or orchestration
features.

**Exit:** the coordinator has decided and explained the status contract within
the grant, with concrete examples, dependency evidence, important alternatives,
remaining uncertainty and any reserved responsibility decisions presented
separately. A reserved dependency stays explicitly unresolved and does not
invalidate independent decisions. The user assesses the integrated result and
decides any reserved changes and Python implementation or deferral; individual
in-scope contract choices do not await another approval. The contract can be
reconsidered during the wider refusal audit.

### Operating terms

1. **Design latitude.** Use custody-focused status as the preferred direction
   to investigate, with the manager's actual inspection and decision needs as
   the criterion. The coordinator may retain a justified live observation or
   reject a proposed reduction. A smaller field or command count, preparation
   for Click, and reduced code or test volume are not success
   criteria. The findings must explain the alternatives and their costs.
2. **Boundary with the wider custody audit.** Trace status's consumers and
   affected fields through all stages, especially collection and close. Allow
   recommendations about their preconditions when needed to resolve the status
   contract, with each proposed obligation change and consequence explicit.
   Existing obligations remain operative until the user decides otherwise.
   Carry questions independent of that contract into stage 2 with their source,
   significance and unresolved decision, without investigating all refusals now.
   Record check ownership and proposed obligation changes in the findings;
   add deferred questions to stage 2 when they arise.
3. **Evidence and stopping point.** Stop when the contract decision is supported
   and explained sufficiently to assess its consequences and decide on Python
   implementation or deferral, with consequential uncertainty explicit.
   Use source tracing and focused installed-wheel comparisons where competing
   explanations remain; allow focused investigative tests and instrumentation
   within the inquiry,
   while production behavior stays unchanged. Include a firing
   control, a changed case and an invariance case where a comparison is needed.
   Do not infer improved agent behavior from output or unit tests, or include
   an agent-behavior study. Findings distinguish observations, interpretations
   and untested hypotheses.

### Repository record of the inquiry

This stage owns the agreed commission, outcome, user decisions and remaining
questions. `STATUS-INQUIRY-FINDINGS.md` contains the decision, prose and JSON
examples, observation/consumer map, diagnostic ownership, implementation outline,
evidence and limitations. These are the current
destinations; the retained input's old branch, findings filename and plan-update
instructions are historical. Do not edit that captured input to reconcile it.

Investigative tests belong under `tests/`. Executed comparisons use fresh result
names under `.scratch/status-inquiry/` and the installed-wheel workflow in
`DEVELOPMENT.md`, with command output and actual selector/outcome counts retained
and cited in the findings. That document's retention and pruning rules apply.
Accepted behavior belongs in maintained documentation and tests when implemented;
the plan and findings do not become runtime dependencies. Retire the findings
when their review and implementation purpose is served, first moving enduring
decisions into maintained guidance and any still-active decisions into this
plan, and disposing of cited runs under the retention rules.

## 2. Audit refusals and existing custody responsibilities

**Commission:** the user's instruction to proceed commissions this investigation
and recommendations. It does not commission runtime changes or stage-3 additions.
The prior status-contract grant is not blanket authority to revise custody,
closure, removal or execution responsibilities.

**Outcome, decided 2026-10-24:** `CUSTODY-AUDIT-FINDINGS.md` maps existing
responsibility families, costs and recovery; separates prior accepted but
unimplemented fixes from new recommendations; and records controls, outcomes
and limitations. The user decided its recommendations as follows, and
`CONTRACTS.md` states each decided contract with its implementation status:

- D1 is decided as close rules: runtime coverage by the triaged collection
  replaces equality with preparation; a recovery is disposable while it matches
  its own capture and otherwise is unjudged; experiment HOME is declared
  disposable with its identity recorded; the closing record freezes the
  identity of everything discarded; abandon follows the same rule; a kept
  checkout stops cleanup; command rendering is not a closure precondition. The
  reframing that settled it: these extend the existing act-only-on-what-was-judged
  promise, and close offers the manager opportunity, not preservation. The
  later-return rule awaits the executed comparison below.
- D2 is decided: a verified selected report is exportable despite a damaged
  sibling capture, carrying the damage explicitly and preserving the original.
  Export only; closure keeps full-capture.
- D3 is decided in its narrow form, contingent on stage 3's submodule decision.
- D4 is decided.
- D5 is deferred to stage 4 as the conservative default, with cross-writer
  read-only export expected to be permitted under the refusal principle.
- D6 is documentation of retained obligations and their limits.
- Declined with recorded reasons: mandatory retention before close, a universal
  final preparation receipt, splitting issuance from preparation, a manager
  accepted-answer receipt, live checks on retained published files, capture of
  recovery contents, and an acknowledgment charge for a nonempty HOME.

Two general commitments were reached and recorded as principles: Stewart's
refusals are limited to its own claims and safety, tested by what claim it
would make falsely by proceeding; and Stewart's promises to the auditor are
process promises, with no material-preservation promise to the auditor or to
the manager's principal over the deciding manager.

Configured Git-filter execution during preparation and inconsistent replacement
views during input-pin construction versus capture coverage were demonstrated.
They are implementation issues under retained trust commitments, listed in
`CONTRACTS.md` as successor obligations. The broader Git environment policy is
not qualified by those narrow probes. No production change was made and no real
harness enforcement was tested.

Evidence runs are `.scratch/custody-audit/comparisons-01.json` and
`.scratch/custody-audit/git-filter-02.json`; the report owns their exact selectors,
failure/correction account, tested-source hashes and compact evidence manifests.
Retirement/pruning follows DEVELOPMENT.md. Stage 2's investigation can conclude
with explicit reserved choices; stage-3 additions do not start automatically.

The later-return comparison ran as `.scratch/custody-audit/later-return-03.json`
with `tests/test_custody_later_return_inquiry.py`: 6 collected, 6 selected,
6 passed, 0 failed, 0 skipped, 0 deselected; pytest and runner exit 0;
pytest 9.94 s, total 12.5 s; the same wheel digest as the earlier runs. Two
earlier receipts are kept. `later-return-01` recorded five setup failures,
which pytest reports as errors, and no executed test body: the harness shell
sandbox refused creating `.gitconfig` in the private HOMEs under the artifacts
directory. `later-return-02` recorded 1 passed and 4 failed: hypothesis-framed
assertions the observed behavior contradicted. Its staged test source survives
as the receipt's hash and the failing assertion lines in its pytest log, not as
a file. Runs 02 and 03 executed with that sandbox disabled for those commands.
Seventy verified entries are retained in `later-return-03-evidence/`. No close
was executed; `close_plan` and the read-only preflight were observed, with
session-directory snapshots confirming no session writes and source reading
confirming the plan path writes nowhere else. Baseline and
identical-later-collection cases rest on the triaged collection; a
changed-then-restored runtime refuses on the later collection's
`runtime_changed` gap while it is the latest; an unrestored runtime refuses and
restoration alone no longer suffices; a changed checkout refuses
`checkout_changed`; and a changed runtime followed by a clean later collection
concludes on the older triage with the change unaddressed. In every case status
offered `retain` rather than close, since it offers close only when nothing
else is pending; the hypothesis-framed run had expected a close offer, and the
test's docstring now says so. Only the checkout variant of a differing later
return was exercised; that a differing report is caught the same way follows
from the inventory covering the worktree, by source reading.

A second independent reviewer checked this comparison: receipt counts, all
seventy evidence digests and the test-source hash against the receipt, the case
design against the firing/differing/invariance rule, the stated mechanism
against `status.py` and `close.py`, and the sandbox claim against the conftest
and the run-01 log. Nothing blocked the record; the two inference points above
were made explicit at its suggestion. The three artifacts directories were then
pruned through `scripts/prune.py --run custody-audit/<stem> --apply`. The
sandbox also refused unlinking the `.gitconfig` files, so runs 02 and 03 took
two attempts each; the `*-prune.out` streams carry both. Removal records under
`.scratch/pruned/`: `20261024T152616Z-13139` (run 01, together with the already
reduced `contracts-link/distribution-01` directory), `20261024T152617Z-13156`
and `20261024T152929Z-13207` (run 02, refused then completed), and
`20261024T152617Z-13173` and `20261024T152929Z-13224` (run 03, refused then
completed). Each run's `*.pruned.json` names its first record.

Examine what each restriction protects, which obligations it creates, its
costs, and the consequences of retaining, hardening, softening or removing it.
Use [prior custody questions](planning/inputs/custody-questions.md) as leads to
recheck, alongside the status inquiry. Preserve the distinction between prior
user decisions, observed defects and untested proposals.

Independent inquiry is useful where it can challenge a consequential premise.
The coordinator recommends; the user decides changes to Stewart's intended
responsibilities. Neither current implementation nor simplicity alone settles
the answer.

Organize the account by responsibility families rather than treating each reason
identifier as a separate product choice. Use source inspection, historical
decision reconciliation and focused installed-wheel comparisons to distinguish
protected commitments from incidental couplings. Retain fresh runs under
`.scratch/custody-audit/` with their actual outcomes. Arrange independent review
of consequential recommendations and comparison evidence. The current account is
`CUSTODY-AUDIT-FINDINGS.md`; retire it after its decision/implementation purpose is
served, transferring enduring guidance and active decisions and following the
run-retention rules in `DEVELOPMENT.md`.

Dispositions of the leads carried from the status inquiry:

- Concluded close's inherited live-runtime and command-rendering effects are
  decided under D1: runtime coverage replaces the preparation-equality gate and
  rendering is not a precondition. Damaged retained records that conclusion
  relies on still refuse conclusion; that is retained, not re-decided.
- Status's stricter offered close remains advice; newest-collection triage and
  pending retention/release/run are not migrated into mandatory refusals.
  Whether later consequential evidence must be addressed was examined by the
  later-return comparison below. Today conclusion refuses only while the
  latest complete collection is untriaged with a verification-level gap, and
  only because status surfaces that gap; a later clean collection hides it and
  conclusion rests on the older triage. The proposed rule in `CONTRACTS.md`
  requires every later collection with such a gap to be triaged before
  conclusion and keeps review-only gaps as advice.
- Proof of preparation completion is declined in both forms; `CONTRACTS.md`
  records the reasons.

Delivery responsibilities and human-auditor interaction, including an
auditor-attributed acceptance of the commission, are carried to stage 3;
neither an external-only delivery boundary nor a watcher requirement was chosen.

Independent review of the decision set, 2026-10-24: a fresh reviewer applied
the two reliance tests to `CONTRACTS.md` and this section and verified the
factual claims against the frozen source. Fourteen findings, none blocking.
Corrected: the opportunity principle now names the declared-disposable category
HOME uses; the preparation-receipt decline's reason; the export chain claim
(the receipt does pin the runtime group's capture digest, and the report's
verification does not depend on that group's present readability); recovery's
capture wording, since it captures once at materialization; the HOME member,
which is the attempt directory; the reason identifiers `runtime_changed`,
`recovery_changed` and `checkout_kept`; the runtime rule's treatment of
movement and failed capture; freeze-and-revalidate for every comparison; which
mode carries a discard acknowledgment; the open later-return variant; and the
frozen-Python statement in the former-plans disposition. Three completions the
review required are recorded as proposed in `CONTRACTS.md`: the kept-checkout
exit, the enumerated live checks with the public handoff treated like the
runtime, and the closing record as a new schema.

Riker consultation, 2026-10-24: the user relayed
`riker/CLOSE-COMMITMENTS-REQUEST.txt` and returned the reply retained at
`riker/CLOSE-COMMITMENTS-REPLY.txt`. It is advisory, not authority. It retains
the D2 decision and does not defeat opportunity-over-preservation, but it
establishes limits the coordinator accepts as correct: the false-claim test is
one ground for refusal, not the only one; the party hierarchy should give way
to default manager control plus obligations Stewart has actually undertaken;
and "opportunity" must mean a working preservation path, with three outcomes
kept distinct (available and surrendered, declared and unexamined, lost despite
an undertaking). Several of its scenarios are already met by Stewart's
mechanisms, which the revisions below make explicit: enrolled resources are
never claimed for disposal; retention and export copy bytes and never reference
the session; uncollected auditor work is not destroyed without an explicit
discard naming it. Two scenarios lie outside the present model and are carried
to stage 3 rather than decided: a manager not authorized to receive part of the
auditor's return, and limits on a manager's delegated authority to destroy. One
scenario named a real gap: a keyed `retain` records planned outputs before
writing, a failed one leaves a partial request that cannot be resumed, and
close does not consult request state; that is the fifth proposed completion.
The experiment HOME is not the auditor's workspace, so the reply's
restricted-environment auditor case bears on the checkout, which collection
captures and abandon protects, not on the HOME rule.

On 2026-10-24 the user approved the five completions and three revisions to
the principles drawn from that reply: refusals rest on three grounds rather
than the false-claim test alone; default manager control plus undertaken
obligations replaces the party hierarchy; and opportunity means a working
preservation path, with regenerability never a ground. `CONTRACTS.md` carries
the approved text; its history holds the proposal wording.

**Exit:** reached in substance on 2026-10-24: the decisions above are recorded
in `CONTRACTS.md` with reasons and declines, and the independent review of
that decision set is resolved above, as is the Riker consultation. Stage 2
closed on 2026-10-24 with every completion and revision decided. Implementing
decisions in Python is not a condition; Python is frozen.

## 3. Consider additions to custody

Examine responsibilities Stewart might reasonably assume, informed by the
refusal audit. For each candidate, describe the responsibility, required
authority, preserved evidence and commitments, costs and means of discharge.
Declining an addition is a valid outcome.

**Submodule support is an explicit candidate.** Separate making pinned
submodule code readable from supporting work inside populated submodules.
The [candidate note](planning/inputs/submodules.md) keeps the substantive
questions. Consider object availability, scope, commit retention, capture and
cleanup before choosing a mechanism.

Carried from stage 2 for consideration here: delivery and return-route
responsibilities and human-auditor participation, including an
auditor-attributed acceptance of the commission; real external retrieval and
system-project experiment capability (D6's candidates); and, if submodule
support is adopted, revisiting the narrow D3 contract. Stage 2's declines are
recorded in `CONTRACTS.md` and are not reopened here without a new reason.

**Commission, 2026-10-24:** the user's instruction to dispatch the first wave
commissions this investigation on the following terms. Examine each candidate
addition and produce the coherent desired custody arrangement this stage's
exit describes, with every candidate accepted, declined, narrowed or deferred
and with semantics ready for implementation separated from exploratory
ideas. Candidates: submodule support, from the captured note;
delivery and return-route responsibilities with human-auditor participation,
including an auditor-attributed acceptance of the commission; real external
retrieval and system-project experiment capability; a record of a manager's
delegation limits or a material provider's conditions; and a right to receive
distinct from the commission. Declining is a valid outcome for each. The
coordinator would assign one source investigation per candidate to workers
with compact returns, run a controlled comparison only where source cannot
settle a question, arrange a fresh independent reviewer over the integrated
account, and consult Riker at the coordinator's or user's discretion. No
production change; Python stays frozen; accepted additions become contracts in
`CONTRACTS.md` for Rust. The commission does not authorize implementation.

First wave, dispatched 2026-10-24: four source investigations, each returning
a compact summary and writing its full account under
`.scratch/custody-additions/`: submodules (reading pinned code and working in
populated submodules kept separate); delivery and return route with
human-auditor participation, including an auditor-attributed acceptance;
external retrieval and system-project experiments; and authority and
conditions on material, combining the delegation-limits and right-to-receive
candidates. All four returned on 2026-10-24; the integrated account is
`CUSTODY-ADDITIONS-FINDINGS.md`, with fourteen recommendations (six narrowed
acceptances, five declines, two deferrals, one narrowing of a mixed candidate),
eight findings that bear on decided contracts rather than additions, and a
proposed second wave of nine baseline comparisons needing no harness, network
or human. Independent review found every anchor sound and seven corrections,
applied and recorded in the account. If adopted, submodule (i) adds a clause to
the gitlink-input contract and reaches close's abandon exemption, and a hold on
a Stewart-created resource is a new commitment beside the retention-undertaking
rule.

**Decided, 2026-10-24:** the user agreed to the account as recommended.
`CONTRACTS.md` records the accepted additions as contracts (pinned submodule
copies; a manager-declared return arrangement; a stop note on collect; the
handoff complete without the helpers; external sources recorded beside the
constructed grant as a neutral limit; project commands through the reviewed
shim; holds on recorded resources; and the close correction for supplied-file
copies and attribution of retention that came out of the same findings), the
seven declines with their reasons, and the three deferrals with their
dependencies. The second wave's comparisons were not run before the decision;
they remain available as baseline verification at implementation, and the
record marks as predictions the facts they would establish.
This is the stage-3 decision history. The 2026-10-25 resource discussion
replaces the resource-attached hold with a finite custody-material hold,
narrows successor legacy inspection and removes the dedicated executor and
reviewed-shim route from successor scope; CONTRACTS.md carries the current account.

**Exit:** a coherent desired custody arrangement, with additions accepted,
declined, narrowed or deferred. Separate semantics ready for implementation
from exploratory ideas; inclusion as a candidate grants no implementation
authority. Reached 2026-10-24.

## 4. Transition to Rust

Build a new implementation against the contracts selected for continuity and
the deliberate departures authorized in the preceding stages. Choose a
migration sequence and verification strategy that assess the integrated
system. Carry meaningful behavioral comparisons across implementations;
reproducing every Python behavior is not the acceptance criterion.

The Python implementation is frozen as the reference baseline: no further
behavior changes, so that one stable baseline is the control for acceptance.
`CONTRACTS.md` lists every decided departure and the previously accepted
corrections the Rust implementation realizes. Sequence read-only operations
first, beginning with status, then the write path, then close. Use the existing
Python corpus as comparison evidence for the selected custody claims; it does
not require permanent product support for every old operational structure.
Before commissioning status implementation, specify its consumer, supported
record population and placement under the bounded evidence-reader contract.
Write acceptance against the contracts and drive the CLI so it is
language-agnostic. Close every live Python audit under Python before Rust
closes anything; separately dispose of independent legacy undertakings before
withdrawing their writer.

The user has also asked for `GIT-ENVIRONMENT-NEEDS.md`, a document for
Stewart's users, the people who prepare material in Git and operate it, with
the development user acting only as their proxy: how to prepare that material
for Stewart and what Stewart does not support, as a narrative introduction, a
mechanically generated table of the Git opinions Stewart holds, and an
interpretation guide. The coordinator handoff describes the request. The
decisions it produces are recorded in `CONTRACTS.md`, and the Rust
implementation honors or deliberately changes each decided opinion.

Make any intended behavior awaiting the optional final stage explicit. Avoid
requiring all newly accepted responsibilities to be implemented in Python
first. Preserve historical evidence and specify treatment of writer-bound
sessions without compatibility shims or rewritten receipts.

**Platform acceptance:** retain the qualified macOS behavior and establish
Linux and WSL support for Rust. We will execute Linux validation. The user
will ask a friend to execute the WSL checks; prepare a reproducible handoff
and record their actual environment, results and limitations. Linux results
alone do not establish WSL support, and a prepared recipe is not an executed
qualification. If WSL evidence is outstanding, keep that acceptance item open.
Choose tooling when implementing; the former Python container-installation
project is retired.

**Exit:** an integrated Rust system verified against the selected contracts,
with platform evidence and explicit disposition of any unmet acceptance item.

### Next design work: acquiring returns and completing custody

The first connected account is now in RETURN-CUSTODY-DESIGN.md, accompanied
by the manager's task flow. Use it for the next decisions rather than repeat
the source inventory. It identifies a protected-obligation conflict that
publication alone cannot resolve: work outside the selected return still
needs a working preservation opportunity or an authorized named surrender
before removal. A digest or a stable answer also does not establish stopped
activity. The candidate snapshot mechanism has no qualified route yet.

The accepted graceless-exit branch now adds a specific obligation to resolve
the launch/control arrangement. Its task-flow and contract edits are checked
in `.scratch/return-custody-design/validation-02.json` and its `.log`: zero
pytest nodes selected and zero behavioral comparisons run. This is a recorded
design commitment with qualification outstanding, not an implemented flag.

Source review and revalidation of 21 retained export-comparison observations
are recorded in `.scratch/return-custody-design/source-review-01.json` and
its `.log`; documentation validation is in `validation-01.json` and its
`.log` in the same directory. Zero pytest nodes selected and zero new
behavioral comparisons run. The original observations remain in their
existing evidence population. The helper-recovery inventory covers documented
consumers, not an inventory of live Python recoveries or a qualified fresh-
reuse route. Keep those unfinished items with the legacy transition.

Planning revision, 2026-10-25, under the user's delegation. The peripheral
recommendations are preserved in
[`planning/inputs/return-and-custody-advice.txt`](planning/inputs/return-and-custody-advice.txt).
Their relative links were not followed. The choices below are the coordinator's
assessment against current Stewart contracts, source and retained findings;
relaying the advice did not make it the user's guidance. No new runtime or
harness experiment is commissioned by this planning revision.

Develop one account of what Stewart acquires, how the manager receives it, and
how the same custody undertaking finishes after interruption. This is the next
design priority within the open A to F round. Recommend zero audit restarts for
the first successor and schedule no restart convenience. The open product
choice of at most one such facility remains reserved; reconsider it only for
an identified need after the custody interfaces are concrete. Do not replace
recovery of Stewart's own work with a new investigation.

Produce the following connected design account before proposing implementation:

1. **Acquiring an identified return (C, D and R2).** Make a stable, identified
   publication the leading candidate for ordinary acquisition. Define the
   publication act, its finite material boundary, the mechanism that establishes
   stability, the authority to acquire it and the exact observation Stewart can
   claim. Here publication means fixing the auditor's return for acquisition;
   later retention/export to a manager destination is a separate operation.
   A digest or a declaration of completion alone establishes no freeze.
   Qualify the arrangement and its read/write routes equally for human and
   agent auditors; human authorship neither supplies nor defeats confinement.
   Distinguish the auditor's claimed investigative outcome, completeness of
   acquisition, and completion of custody. A complete publication can report
   failed or incomplete investigation. Preserve raw captured bytes before
   interpretation, including invalid declarations and interrupted fragments.
   Specify what happens to material outside the publication: selecting a return
   must not silently narrow an existing capture or preservation obligation.
   Early close must have a supported path when no stable publication exists.
   Keep the baseline's attributed stop and movement observations as comparison
   evidence, not proof of a stronger stability guarantee. Stable return bytes
   alone do not establish stopped activity, revoked grants or safe retirement.
2. **Making the return available and delivering it (R2).** Recommend a normal
   reader that verifies the selected report and the dependencies of its claims,
   carries relevant surrounding damage, and names unfinished custody work
   without withholding an otherwise usable answer merely for cleanup. This
   extends the decided export-only policy and therefore needs a specific
   contract decision. A damaged dependency qualifies the claim it supports;
   intact report bytes do not make all reported evidence verified. Separately
   identify the receiving endpoint, callback/resumption responsibility and
   evidence of delivery on each admitted route. Availability, attempted
   delivery and receipt are different observations; loss of notification must
   not require another audit or routine manager polling. Preserve the decline
   of an accepted-answer receipt. A delivery observation is no verdict on the
   answer and supplies no authority for recurring live inspection.
3. **Completing identified custody operations, including close.** Design the
   manager's retained request reference or unambiguous discovery path as well
   as the exclusive binding before effects. An identifier returned only in a
   lost reply cannot serve that manager. Map each interrupted operation to its
   planned outputs, observed effects, available result and supported completion
   or explicit disposition. A repeat of an identified request remains that
   undertaking; it neither adopts unrelated output nor treats a new observation
   of changed material as the old capture. Do not silently deduplicate unkeyed
   requests. Use one manager-facing `close` entry point across preparation,
   investigation, return, holds and failure, including internal withdrawal and
   partial-work accounting. Continue removal against its frozen inventory and
   revalidated identities; a replacement at the same path grants no authority.
   Keep holds, other live uses and preservation undertakings effective. State
   a usable resolution for each failure; neither a diagnostic alone nor a new
   manager-facing menu of withdrawal/recovery stages meets the design target.
4. **Reading a portable result and bounding legacy needs.** Specify a manager
   or later investigator opening an exported result after its original audit
   environment and writer are gone as the first evidence-reader consumer.
   Name exact admitted schemas, selections and supported claims. Account for
   the question's bytes, subject identity, report, selected support, collection
   and source-receipt identities, attribution and qualifications. A commit ID
   alone does not recover absent question bytes. Inventory what existing
   packages actually carry before promising this view; missing historical
   context stays a limitation, with no rewritten receipts or assumed format
   upgrade. Preserve a finite selection and the dependencies needed for its
   claims, without promising replay or recursively preserving its references.
   Apply the same requirement to held captures after environment retirement.
   A portable snapshot describes its recorded custody; it cannot establish a
   later completion or hold release without the relevant later evidence.
   Keep current-operation status and transition-only Python diagnosis separately
   scoped. This consumer selection organizes reader design; Rust implementation
   remains status first, write path next and close last, pending commission.
   In this account, resolve R1's helper-asset consumers: prefer inspection of
   captured assets and separately authorized fresh reuse over a new mutable
   recovery directory. Carry any unmet consumer and existing Python recovery's
   transition disposition explicitly; removal is not yet a contract decision.

For B and F, retain the leading recommendation of a plain subject directory
and a separately granted pinned history view, including history-only inquiries
with a return area. Use a self-contained copy of the selected history as the
initial design candidate. Shared immutable storage may optimize it only after
selected access and independent custody identities are established. Before
deciding the sole workspace form, give concrete capability examples for
Git-aware inspection and build/test tools: what works, what needs a different
invocation, and what would be unsupported. Useful auditor tool use remains
important after executor removal. Rich selected context is compatible with a
narrow question. Do not add a live history-query service to resolve convenience
issues without assessing its new channel and availability obligations.

The following comparisons define the questions for later qualification; none
has run in this revision. Reuse earlier evidence where it measures the property.
For each new comparison include a firing control, a case differing in that
property and an invariance case, with an independent witness outside any
capture/disposal under study and retained through review.

| Case | What the design and later evidence must distinguish |
| --- | --- |
| A fixed return reports failed investigation | Acquisition can complete while the auditor declares incomplete work; no Stewart process witness is inferred. Compare a successful-investigation report with the same acquisition conditions. |
| A writer attempts to change publication during acquisition | The mechanism protects the identified version or qualifies the failed acquisition and preserves observed bytes. An unchanged publication and changes outside the selection distinguish stability from unrelated activity. |
| Close arrives before publication, or after failed preparation | The same `close` request accounts for available partial material and stopping uncertainty, without requiring a completed publication or another investigation. A completed return supplies the ordinary control. |
| Export or acquisition reply is lost | A caller-held reference or supported discovery finds the original undertaking and its planned result; a changed source is a new observation. Compare no effects, partial effects and a completed operation whose reply alone was lost. |
| Return is available but notification fails | The same identified answer remains retrievable; delivery state stays qualified. Compare confirmed delivery and an unrelated custody change without introducing routine polling or answer acceptance. |
| Selected report survives surrounding damage | Verify the selected view with relevant qualifications; selected-byte or required-dependency damage changes the affected claim. Equal report bytes in distinct collections retain distinct custody identities. |
| Close is interrupted, a path is replaced, or a hold/live use remains | Continue only frozen authorized removal, preserve protected material and keep a verified answer readable. Compare the original target, a substituted target and unrelated filesystem changes. |
| Exported result moves and the original environment disappears | Supported interpretation survives irrelevant paths, writer loss and live-state changes; damaged selected evidence fails its claim. Establish the supported platform result rather than infer portability from a recipe. |

**Exit of this design work:** a concrete manager interaction account for normal
return, early close and each supported failure; a candidate acquisition and
delivery protocol with explicit identity/authority boundaries; a bounded reader
population; and a list of contract decisions with their reliance changes.
In particular bring back the stability undertaking and any capture-scope change,
the extension of selected-report access beyond export, delivery obligations,
and any conflict between single-command close and existing obligations. The
account must distinguish incomplete investigation, acquisition, delivery and
closure without making them new mandatory manager-operated stages. Decide the
remaining workspace, commission and custody-location choices against that
account before commissioning the write path. No fleet is dispatched or runtime
implementation started by preparing this work.

Documentation checks for this planning revision are retained in
`.scratch/return-planning/validation-01.json` and its `.log`, with starting
documents under `before/` to distinguish the pre-existing single-close edits.
Zero pytest nodes are selected and zero behavioral comparisons run. The user
has taken responsibility for the pending commits and Git-permission diagnosis;
this revision makes no further staging or commit attempt.

### Opening decision round: a narrow custodial core

The user placed the external proposal in
[`planning/inputs/custodial-core.md`](planning/inputs/custodial-core.md) here
on 2026-10-25. It reopens no stage-1 to stage-3 decline. Its mechanisms and
traps are implementation material for the successor, and several restate
successor obligations already recorded (configured filters during
`worktree add`, replacement objects, one Git invocation policy, verified
descriptor reads). Its architectural parts raise five decisions that belong
to the user because they change Stewart's intended responsibilities or
decided principles:

- **A. The admission rule.** Whether "exactly three responsibilities"
  (workspace access, historical inspection, custody capture) is exhaustive.
  A.2 is decided: the successor omits the dedicated executor and its staged
  release/run relationship, superseding the stage-3 project-command route.
  That decision does not itself adopt A.1's formal admission test.
  The general manager-side
  resource lifecycle is now deferred under A.3, with its retained custody
  duties separated; do not treat that deferral as still awaiting decision.
  The other three tests (traceable authority, an
  intelligible record, no substituted judgment) restate decided principles.
- **B. The workspace representation.** A materialized plain directory with no
  `.git`, as an optional profile or as the only workspace form, with history
  as a separately granted facility. This must be decided before the write
  path even if the profile itself ships in stage 5, or the successor builds
  two prepare, collect and close paths.
- **C. The capture trigger.** The proposal asks for a supervised session exit
  and demonstrated exclusion of writers; the decided relationship keeps
  Stewart agnostic about launch arrangements and accommodates human auditors.
  The leading candidate is now acquisition of a stable, identified publication,
  with an explicit early-close/partial path, as specified in the next design
  work above. Its stronger guarantee needs a mechanism and a contract decision;
  auditor type does not determine whether access or stability is enforced.
- **D. Commission fields.** Permitted facilities, capture policy and a
  retention promise, against the decided principles that close offers
  opportunity and that promises to the auditor are process promises.
- **E. Where custody lives.** Session storage under the Git common directory
  and `refs/stewart/sessions/<uuid>/*` in the user's repository, or a separate
  custody store.

The user relayed a second proposal the same day,
[`planning/inputs/history-only.md`](planning/inputs/history-only.md): an
audit profile with history inspection and no subject workspace. It reads the
profiles as grants over two facilities, a subject tree and a history view,
with custody always present, which bears on B and D. Its one new decision:

- **F. The form of the history facility.** A typed query interface whose
  queries and results Stewart records needs a process outside the auditor's
  sandbox to record them, which Stewart, a command-line tool, does not have,
  and it would be the first auditor channel to reach Stewart before
  collection; the status contract and the declined auditor-attributed
  acceptance rest on there being none. A pinned, read-only history view that
  Stewart constructs holding only the authorized object closure keeps that
  property and enforces scope by which objects exist, at the cost of copying
  them; any query log is then the auditor's attributed claim. Git's
  documentation says `cat-file --batch-all-objects` reaches alternate object
  stores, so a view borrowing the subject's objects would not confine scope.

Under either proposal every audit still needs a return area that collection
captures, since the report and declaration are files; "no workspace" means no
subject tree.

**Execution decision, 2026-10-25: arrangement 1 selected.** The successor
has no dedicated program executor. Omit the staged manager-operated
construction/review/release/run service, invocation controls, child launcher,
dedicated attempt output/HOME lifecycle and Stewart's own execution-witness
assurances. The decision supersedes stage 3's reviewed project-command shim
as a required successor route. Permitted auditor tool use remains within its
commission and enforced grants; captured reports of execution retain their
attribution. No external service is commissioned to reproduce the old workflow.

The comparison and rejected alternatives remain in CUSTODIAL-CORE-FINDINGS.md,
"A.2 comparison and decision: who owns program execution?" They are reasons
for the choice, not optional feature plans. CONTRACTS.md's execution section
owns the detailed dispositions. The user requested the next coordinator handoff
after this decision; no runtime implementation was commissioned.

Carry these consequences into the remaining plan and eventual implementation:

1. Remove executor stages and their action offers from the successor commission.
   Distinguish permitted auditor tools from a Stewart process witness; do not
   promote captured logs, scripts or ledger rows into proof that Stewart ran
   or observed their reported process. The manager's wish to ask another
   question remains outside Stewart's remit.
2. Specify the reader's consumers and supported records before starting Rust
   status. Historical releases/attempts may remain evidence; their presence
   creates no successor execution facility. A ledger-specific interpretation
   or membership-review surface needs its own bounded consumer and scope.
3. Keep interrupted capture, publication, requests and close central to the
   successor design. A diagnostic alone does not discharge the interface
   requirement: identify supported completion/disposition, or retain an explicit
   acceptance gap. An agent-manager must not be expected to repair private
   records, guess whether work happened or erase evidence to proceed.
4. Inventory the specified legacy population and explicitly dispose of its
   unfinished Python attempts, publications and resources before withdrawing
   their writer. No such population has yet been inventoried. Do not mutate
   legacy receipts, transfer old execution rights or port the executor as a
   substitute for this bounded transition work.

The next design work above now owns the concrete failure cases and planned
qualification. Existing request bindings and closing records are evidence for
design, not a requirement to port every Python mechanism. Live agent testing
should separately establish whether the supported interfaces dissuade private-
state repair after failures; successful record checks alone cannot establish it.

The preference remains zero audit retries, with at most one restart-from-start
convenience still open as a product decision and unscheduled in the first
successor plan. Recording a remit does not itself promise replay; the
manager owns constructing another question. The separately assigned next-
coordinator goal is still to effect the lean against mutable helper-runtime
recovery directories: those helpers are distinct from the removed executor.
A.1, B to F, delivery, exceptional intervention, exact custody recovery and
selected reader formats remain open. The HOME/manual experiment-retry parts
of R1 now have no successor facility to design; their legacy treatment remains.

The comparison was checked in `.scratch/resource-decisions/validation-14.json`
and its `.log`. The decision reconciliation and requested handoff are checked
in `.scratch/resource-decisions/validation-15.json` and its `.log`; zero pytest
nodes selected and zero behavioral comparisons run. Python production source
remains frozen. Git-metadata restrictions blocked earlier commit attempts;
the user subsequently requested committing the accumulated changes. The
ordinary and elevated staging attempts both failed creating `.git/index.lock`
with `Operation not permitted`; no commit was created. The attempt and final
documentation check are retained in `.scratch/resource-decisions/commit-attempt-01.json`
and its log. The coordinator handoff records the resulting version-control state.

The round runs one inventory with two projections: the Git opinions table for
`GIT-ENVIRONMENT-NEEDS.md`, generated by a tracked script, and Stewart's
privileged operations classified against the admission rule. Focused
installed-wheel comparisons under `.scratch/custodial-core/` settle the facts
source cannot: paths colliding by case or Unicode normalization at preparation,
mirror operations carrying Stewart's refs, and writes during and after
collection relative to the stop acknowledgment. A Git-only probe, involving no
Stewart code, settles F's premises: whether a view holding exactly a pinned
commit's closure can be built without the subject's replacement refs,
configuration or alternates, what it costs, and whether an alternates-backed
view exposes unauthorized objects. A fresh reviewer checks the
table's completeness, the prose's truthfulness and the decision account. The
account for decision is `CUSTODIAL-CORE-FINDINGS.md`; decisions go to
`CONTRACTS.md`. Stage 3's proposed second wave is not run in this round:
several of its comparisons presuppose linked worktrees, which decision B may
replace, and they remain available at implementation.

Rust status may start alongside the remaining round at the user's instruction,
after its supported consumer/record scope is made concrete. Interpreting
legacy execution evidence does not require or authorize a successor executor.
The Rust write path waits for the remaining A.1 and B to F decisions.

The round's first wave ran on 2026-10-25: an operations inventory and a
workspace and custody-location investigation (source only), the Git opinions
generator `scripts/git_opinions.py` with its tests (`git-opinions-01`, 4 of 4
passed), installed-wheel comparisons (`comparisons-01` to `-04`, the last
selecting 23 nodes, all passed, wheel `43da134c…`) and the Git-only
history-view probe (`probe-05`). The account for decision is
`CUSTODIAL-CORE-FINDINGS.md`, recommending a disposition for each of A to F;
`GIT-ENVIRONMENT-NEEDS.md` holds the generated table, the narrative and the
proposed status of each class of rows. A fresh independent reviewer returned
32 findings, 3 blocking; all three are resolved and the account records the
disposition of the rest. Generator runs after review: `git-opinions-02` and
`-03` failed on test-helper naming (kept as records), `-04` and `-05` passed
20 of 20.

Remaining semantic decisions: those under A to F (the manager-service
and custody-hold decisions are recorded below); the two proposed completions under B
(refusing an unrepresentable tree, one name normalization in capture); the
leads on a concluded close over a failed preparation and on the recorded
pause; the guide's statuses; and whether Rust status starts alongside. The
coordinator develops the connected return/custody account above to make those
choices concrete. No runtime implementation is in flight.

Discussion resumed, 2026-10-25: the user had little opportunity to confer with
the previous coordinator before the handoff. A to F are being reviewed as
proposals. The user expressly kept manager resource management unsettled and
commissioned a focused account of its interdependencies with the intended
simplifications, allowing connections to be kept, ignored, eliminated or
strengthened as appropriate. The source-based account is in
`CUSTODIAL-CORE-FINDINGS.md`, A, "Resource management: dependencies under
review". It separates manager creation/disposal from live-dependency and access
protection, durable output records, holds, audit closure and recovery. Existing
code and test scenarios were read; no new comparison was run. The initial
account made no contract change; the decisions below followed discussion.
A.2 was subsequently decided as no dedicated successor executor, above. No
production source changes, implementation or Rust-status commission is in force.

The user then requested a classification of those seven connections by
conversation and experimentation. The account recommends conversation for
1 (Git responsibility), 5 (closure authority) and 6 (holds); experiment then
design for 2 (sharing, if its cost motivates the choice) and 4 (access
enforcement); and design then experiment for 3 (publication layout) and
7 (containment, recovery and transition). These are proposed inquiry routes;
no experiment has been commissioned or run in this discussion.

Preferred direction raised while discussing connection 5: after the manager
hands an audit to Stewart, the manager's access to the auditor's material
should be very restricted and the audit process should remain abstract to
them. Missing information can surface in the auditor's structured return.
The coordinator's example of an unmerged change concerned a separate manager
preparation worktree, but did not make that distinction sufficiently clear.
The resulting design question is whether handoff can end dependence on that
mutable preparation environment, with close retiring Stewart-owned audit
facilities and manager workspaces having a separate lifetime. This is a
direction the user subsequently supported for connection 5. The detailed
closure and access contracts remain to be worked out. Enforced manager-side
separation, stopping/collection under that boundary, and the treatment of
shared dependencies need evaluation.

The user requested its implications for 1 and 6. The resulting proposals in
the findings distinguish audit allocation from an optional manager-workspace
service, and consider attaching narrowly scoped holds to identified custody
material independently of that service. Restricted manager access also means
that any promised opportunity to keep material must be available through
Stewart's supported custody interface; a remedy requiring direct access to
the live auditor workspace would need revision.

**Decided, 2026-10-25 (resource discussion items 1 and 6):** defer the general
manager-workspace creation and disposal service, with a lean toward isolating
and possibly removing it rather than advancing it; retain a narrow,
attributed hold on identified custody material with explicit release,
independently of that service. Audit-owned allocation remains in the core.
This is not a blanket deferral of access/dependency protections or custody
records currently implemented in the resource subsystem. The supported
handoff direction for 5, these decisions, and their reasons are recorded in
`CONTRACTS.md`. Its principle, hold contract, condition-record decline,
status/resource ownership rows and close scope have been reconciled; the
resource-claim rule in AGENTS.md and CLAUDE.md distinguishes frozen Python
from the successor. The Git environment guide reflects the manager-service
deferral, while its other statuses remain for decision. No implementation
or experiment has been commissioned.

**Tension to preserve:** effectiveness favors seemingly transparent auditor
access to the materials used to construct the question, conditioned by
manager selection. Seamless operation favors an isolated, constrained,
static slice without nesting or recursive expansion. These can trade off in
unexpected ways. CONTRACTS.md records this as a design principle and
VISION-PLAN.md carries it into the method of inquiry. Selection, material
representation and custody promises must be evaluated together; neither
maximum isolation nor maximum access is the default objective.

Still open within this direction: precise manager access and its enforcement;
the supported identities for holds and copy/transfer treatment; the lifecycle
schema and qualification for the provisional resolution of 3; which
dependencies can actually end at handoff; and legacy resources and claim
recovery during transition. A.1, B to F, the two proposed completions, other
leads and remaining Git-guide statuses are not approved by these resource
decisions. A.2 was subsequently decided separately, above.

On connection 2 the user expressed a **strong lean toward shared immutable
material**. It is the preferred candidate to examine, not executed
qualification or authority to depend on mutable manager files. For connection
3, the user **provisionally resolved keeping held custody with the audit while
its working environment retires** on 2026-10-25, with final custody close
waiting for explicit release and the other closing conditions. This avoids
assuming a separate continuing service after audit close. The lifecycle schema and sharing
mechanism remain undecided. No experiment or implementation is commissioned.

**Direction selected for 4, 2026-10-25:** pursue access defined by explicit
grants to selected audit material and required facilities, preferably
eliminating Stewart's responsibility for a private-location inventory. The
user delegates judgment over a necessary fallback; routine mechanism choices
within the existing access obligations need not return for another decision.
Qualification must establish the boundary, including newly created private
locations, shell and file-tool access, selected material in a shared store,
and the separate manager-side restriction. No successor enforcement result
is established. The later A.2 decision omits the dedicated experiment child;
permitted auditor tool use still needs actual access/effect boundaries.
CONTRACTS.md records the conditional direction and fallback limits.

The remaining discussion of 7 concerns separate audit ownership, the lifetime
of shared material through final close, and bounded recovery from interrupted
custody work. The findings recommend avoiding nested independently owned
lifetimes, making the last shared use and any independent storage lifetime
explicit, and retaining failure records until the work has an explicit
disposition. Legacy Python obligations receive a separate transition inventory
and disposition under the existing writer-continuity default. No new layout,
garbage-collection service or migration mechanism is selected by this briefing.

The user accepted the bounded transition strategy with delegated judgment,
after raising transition itself as a possible source of abstraction leaks.
The findings record a finite procedure over a specified legacy record
population: distinguish completed evidence from unfinished undertakings, stop
admitting new work there at cutover, use authorized old writers to settle what
can be settled, and explicitly dispose of the remainder without automatically
porting old resource management. No actual legacy population has yet been
inventoried in this discussion. This is a strategy, not an executed transition
or a new successor service. CONTRACTS.md corrects the earlier claim that closing
all Python audits makes continuity cost nothing: independent claims and partial
requests can remain. Any admitted reader's scope and cost remain explicit.

The user reconsidered the reader obligation and accepted the narrower direction
on 2026-10-25. CONTRACTS.md now protects supported custody interpretation across
implementations, requires a named consumer and bounded record population for
legacy support, and permits transition-only inspection outside the ordinary
successor surface where that suffices. It replaces the unconditional legacy
resource-reporting promise and distinguishes preservation from interpretation
and from authority to operate. AGENTS.md carries the same boundary. Existing
source separates reading from writer authority but couples status to operational
layout, resource evaluation and command construction; the retained status
inquiry already demonstrated one command-rendering failure blocking the view.
No new comparison ran. Status remains first, with consumer/record scope to be
specified before implementation; Python fixtures are evidence, not a permanent
compatibility promise. Cross-writer export remains separately deferred.

The findings now give a current disposition for all seven resource questions.
The user accepted 6's finite explicit held selection, including metadata and
captured dependencies required for the custody claims Stewart undertakes;
CONTRACTS.md records it. Representation and copy/transfer mechanics remain
design work. For 2/7 the user remains unsure about caching, identifying risks
in live testing: managers missing extraction and working around Stewart to
recover material, and silent destruction/withholding going undetected because
the evidence disappeared. These are concerns to test, not observed failures.

The coordinator revises the initial no-cache recommendation for live testing:
preserve an independent immutable test archive outside the disposal being
exercised, compare pre-deletion audit material with normal captures and the
manager's actual retrieval opportunities, and keep any rescue distinct from
a successful product outcome. Record observer scope/timing rather than assume
complete coverage; do not make a hold prevent the close under test. Archive
retirement follows the development evidence rules. This is a proposal for
development instrumentation, not a production cache or recovery-window
decision. The production last-use policy remains open. Items 1, 3, 4 and 5
have direction sufficient to guide their remaining design
and qualification, without approving the separate A.1 or B–F proposals. A.2's
later no-executor decision is recorded above.

The user's discriminating test is that a hold must not permit the manager to
continue the audit or permit dangling operations after close. Elaborate
facilities during a hold are a warning to examine the commission, capture and
closure boundaries. CONTRACTS.md now distinguishes requesting close from
completing it: obligations are not cancelled by the request, and completion
must not conceal unfinished operations. The findings retain proposed cases
for testing this distinction, including independent completed publications
and another audit's use of shared bytes. A failed close remains unfinished;
recovery authority does not become investigative authority.

The broader product guidance now treats the bounded commission and structured
return as a positive choice for Stewart's intended users, rather than a reason
to reproduce general harness supervision. This distinction is in CONTRACTS.md,
VISION-PLAN.md, the reciprocal development/product boundary in AGENTS.md, and
the root README's mission. It does not decide exceptional intervention or
delivery, or remove current recording interfaces. `launch`/`message` record
acknowledgments; `resume` releases paused writers. Their names alone do not
establish a general agent-supervision service.

Documentation validation is retained at
`.scratch/resource-decisions/validation-01.json` and its `.log`: generated
table freshness and generator coverage both exit 0; `git diff --check` and
the production-source freeze comparison pass; AGENTS.md and its CLAUDE.md
alias agree; no new guide identifier citations were introduced; 18 source/test
anchor groups resolve. No pytest nodes selected and no new comparisons run.
The record stays with this account under DEVELOPMENT.md's retention rules.
The subsequent product/hold guidance check is retained in
`.scratch/resource-decisions/validation-02.json` and its `.log`: whitespace,
production-source freeze and the guidance alias checks pass. The recording
meanings of `launch`/`message` and paused-writer `resume` were checked in source;
no pytest nodes were selected and no behavioral comparisons were run. At that
checkpoint Git metadata was unwritable, so the changes were saved but
uncommitted; later commit disposition is recorded in the handoff.
The provisional resolution of 3 and numbering alignment (3 publication,
4 access exclusion) were checked with `git diff --check`; its output is kept
in `.scratch/resource-decisions/validation-03.log`. The selected direction for
4 and narrowed account of 7 received a documentation-only check retained in
`.scratch/resource-decisions/validation-04.json` and its `.log`; no pytest
nodes selected or behavioral comparisons run. Item 7's recommendations remain
for discussion.
The transition clarification's whitespace and production-freeze checks are
retained in `.scratch/resource-decisions/validation-05.json` and its `.log`;
zero pytest nodes selected and zero behavioral comparisons run.
The reader assessment's documentation check is retained in
`.scratch/resource-decisions/validation-06.json` and its `.log`; zero pytest
nodes selected and zero behavioral comparisons run.
The accepted reader scope and current seven-item account were checked in
`.scratch/resource-decisions/validation-07.json` and its `.log`; zero pytest
nodes selected and zero behavioral comparisons run. The production source
remains frozen. Git metadata was still unwritable at that checkpoint.
The accepted hold subject and live-testing retention discussion are checked in
`.scratch/resource-decisions/validation-08.json` and its `.log`; zero pytest
nodes selected and zero behavioral comparisons run.

### Session-scoped agent-guidance reconciliation, 2026-10-25

The user requested a review only against decisions from this engagement, not
a global stale-document cleanup. The current stock is the seven-item table in
CUSTODIAL-CORE-FINDINGS.md plus the product relationship, bounded transition,
evidence-reader scope and effectiveness/seamlessness principles in CONTRACTS.md.
Strong preferences, provisional resolutions, accepted directions and unexecuted
recommendations remain distinct; production caching and a post-close recovery
promise have not been decided.

Reviewed root AGENTS.md/CLAUDE.md, COORDINATOR-HANDOFF.md, the two active plans,
CONTRACTS.md, README.md and the Git environment guide; bundled role routing,
maintainer/auditor guidance, protocols, question recipes, manual and the issued
handoff text; Riker's current guidance/template; and .tmp's local guidance.
The captured inquiries and external proposals were treated as historical
evidence, not silently updated instructions. No session-related conflict was
found in the Riker routing or .tmp's stated temporary-storage purpose.

Corrections made:

- Reconciled the coordinator handoff with the completed resource/hold/reader
  decisions, restricted manager relationship, unresolved cache policy and
  current working-tree state. Removed the stale separate-briefing-agent route
  and qualified prior fleet expectations by their commissioned work.
- General agent guidance now distinguishes the frozen bundled Python workflow
  from successor obligations, includes explicit grants and the finite hold
  subject, and separates environment retirement from final custody close.
- Preserved the reciprocal development/product boundary and clarified that a
  watcher/callback is not permission for recurring inspection or steering.
- Added scoped evidence-retention guidance for omission/deletion studies,
  without establishing an implemented archive or production recovery service.
- Labelled the root README workflow as current Python; updated the active
  inquiry routing and historical stage-3 hold account so they do not reopen
  settled resource choices. The frozen bundled bytes remain unchanged.

Remainder requiring substantive design or a decision:

| ID | Guidance at issue | Why its disposition is not merely editorial |
| --- | --- | --- |
| R1 | CONTRACTS.md's drifted-recovery route assumes the manager has taken what it wants; experiment HOME advice also assumes direct taking. The manual additionally offers manual output-area cleanup before another attempt. | The user accepts a lean toward omitting successor runtime-recovery materialization; effecting that direction in the larger plan is the next coordinator's goal, below. Its removal is not yet decided. A.2 removes the executor, so its HOME and manual retry cleanup need no successor interface. Legacy evidence and unfinished operations retain their transition disposition. |
| R2 | The baseline manual's post-launch ruling/message example and role instructions to stop/coordinate are not a settled successor intervention protocol. | The narrow commission/return relationship is decided. The user now strongly prefers one `close` command from any audit state, with any withdrawal path internal. Exact stop/capture, disposition and continuation mechanics, other exceptional intervention and return delivery remain open. Keep recording acknowledgments distinct from delivering or authorizing intervention; do not assume live steering survives. |
| R3 | CUSTODIAL-CORE-FINDINGS.md D's proposed retention-promise decline equated a chosen undertaking with mandatory retention before every close. | A narrow voluntarily recorded hold is accepted. Establish what the proposed commission promise adds beyond that hold and completed publication before accepting or declining it. The unsupported equivalence is removed; no new retention promise is approved. |

Hold/copy/transfer representation, exact retirement receipts, selected reader
formats and the shared-store last-use rule remain declared design work, rather
than hidden contradictions repaired by inventing APIs. The independent live-test
archive is still a development recommendation; its concrete scope/retirement
and production cache policy remain open. Guidance for those future interfaces
must be updated with their qualified implementation, not asserted by changing
the frozen Python role files now.

Review inventory and selected remaining excerpts are retained in
`.scratch/resource-decisions/guidance-review-01.json`. Documentation checks are
retained in `.scratch/resource-decisions/validation-09.json` and its `.log`;
zero pytest nodes selected and zero behavioral comparisons run. The review
updates existing coordinator guidance; it does not hand off the coordinating
role or commission runtime implementation.

The user clarified the coordinator's authority over that handoff: it necessarily
ages as soon as it is taken up, was itself written by a coordinator working from
an earlier handoff, and is deliberately not supervised or edited by the user.
Continuity and change both matter. The coordinator selects what belongs for an
unknown next coordinator, accepts imperfection, and need not seek approval of
that selection. AGENTS.md and the handoff introduction now state this directly.

R1's next briefing isolates runtime-recovery materialization from recovery of
audit results. The existing operation creates a fresh directory from captured
Stewart helper assets for inspection or a separately authorized fresh assignment;
it never retargets the live audit's commands, scope or release (`runtime.py:298-304`).
The user accepted the coordinator's lean toward omitting this extra mutable
materialization: retain the evidence and provide bounded inspection/authorized
fresh reuse, rather than automatically add a rescue-and-recapture service for
changes written into the reconstructed directory. Removal itself is not yet an
accepted contract change.
Legacy recoveries still require their bounded transition disposition, and an
unexpected change cannot simply be declared impossible or discarded. A.2's
later no-executor choice removes the successor HOME/manual retry portions of R1.

**Goal assigned to the next coordinator:** effect that lean in the larger
program. Identify the actual consumers of helper-code materialization, establish
whether bounded captured-asset inspection and fresh authorized reuse suffice,
and reconcile the resulting scope across the reader, execution, close and
legacy-transition commissions. Carry forward any necessary unmet use explicitly;
do not invent a rescue service to protect an inherited directory mechanism.
Return any required change to protected obligations for decision. This assigns
planning work, not runtime implementation. A.2's executor removal is now
decided separately; supplied helper-runtime materialization is still distinct.

The handoff-authority clarification and R1 briefing account are checked in
`.scratch/resource-decisions/validation-10.json` and its `.log`; zero pytest
nodes selected and zero behavioral comparisons run.

The R1 execution issue that led to the A.2 decision was another invocation of a released script
after a process or evidence-production failure, not another audit sought because
its answer was intellectually unsatisfying. The user explicitly placed the
latter outside Stewart's remit. The coordinator withdraws the preceding
briefing's proposal to prefer a fresh commission for another investigation as
a resolution of this issue: it conflated the manager's investigative judgment
with the executor's mechanics.

Frozen Python has an optional construction/review/release/run flow. The auditor
constructs a script and stops; the manager reviews and releases exact bytes;
`run` reserves that release once and records the subprocess and its evidence.
Nonzero exit, timeout and malformed output are concrete examples of recorded
problems, not judgments of the audit answer. A further invocation needs a new
release consistent with the assignment (`experiment.py:382-418`). Release also
requires an absent output area (`experiment.py:276-286`) and offers collection,
verification and manual removal/movement before another release, or a fresh
audit. The manual describes this at `src/stewart/resources/README.md:1705-1718`.
This output-area constraint applies after a successful run too. No change of
question, script or auditor is necessary to expose it.

The user's preference for at most one audit retry facility, potentially none,
led to review of the whole execution relationship and selection of no dedicated
successor executor. No local output retry/cleanup or dedicated HOME retrieval
service is planned. A refusal before launch, an observed child failure and an
uncertain outcome remain distinct in legacy evidence; none licenses replay.
The legacy HOME category is unchanged and does not apply to other audit material.

The accepted lean, next-coordinator goal and retry briefing are checked in
`.scratch/resource-decisions/validation-11.json` and its `.log`; zero pytest
nodes selected and zero behavioral comparisons run.

The user's scope clarification and corrected execution account are checked in
`.scratch/resource-decisions/validation-12.json` and its `.log`; zero pytest
nodes selected and zero behavioral comparisons run.

The user authorized recording the retry preference and revising planning after
the discussion-only turn. CONTRACTS.md records the provenance/replay direction
as a candidate core commitment and clarifies responsibility for incomplete
operations. The vision, agent guidance, handoff and A.2 recommendation now
reflect the decision sequence. These documentation changes are checked in
`.scratch/resource-decisions/validation-13.json` and its `.log`; zero pytest
nodes selected and zero behavioral comparisons run. Runtime source is frozen
and no implementation is commissioned by these changes.

### Single close entry point, 2026-10-25

During coordinator intake, the user stated: "My STRONG inclination is to offer
a close command and that's it." The manager should know that close closes the
audit regardless of state; "close demanded while audit in progress" may route
internally to withdrawal. The user authorized recording this direction after
the coordinator distinguished a close request from guaranteed immediate
completion under existing holds and unfinished preservation undertakings.

Design one manager-facing close operation across preparation, investigation,
returned work, held custody and failure states. Stewart owns the internal
stopping, partial-work accounting and custody steps; a manager should not need
to diagnose the stage, repair private records or discover a different lifecycle
command to finish closing. The existing conclusion/abandon distinction supplies
custody rules and legacy evidence, not a requirement for separate successor
modes. Do not weaken the one-command target merely by exposing the old stages
under it. Keep any concrete conflict with an existing obligation explicit for
decision, including the authority needed to release a hold or surrender an
unfinished preservation undertaking. Exact prompts, dispositions, stopping and
continuation mechanisms remain design work; no new interface is implemented.

This narrows R2's interface question without settling capture quiescence,
other exceptional intervention or delivery. Planned qualification should cover
the same close entry point at each lifecycle stage, closure interrupted and
continued within recorded authority, and holds or competing uses that still
protect their material. These are planned cases, not executed results.

The previous documentation changes were committed as `a8de387`; its account
supersedes the earlier checkpoint's uncommitted state. The failed staging
attempt records remain historical evidence. This intake's documentation checks
are retained in `.scratch/close-direction/validation-01.json` and its `.log`,
with the final account checked in `validation-02.json` and its `.log` in the
same directory: zero pytest nodes selected and zero behavioral comparisons run.
The user requested a recording commit as a partial check of repaired Git
permissions. Both ordinary and elevated staging still failed creating
`.git/index.lock` with `Operation not permitted`; nothing was staged and no
commit was created. `.scratch/close-direction/commit-attempt-01.json` and its
`.log` retain both outcomes. The five documentation edits remain uncommitted
until this session can write Git metadata. Do not bypass that restriction.

## 5. Optionally implement the revised custody arrangement in Rust

The user chooses which authorized semantic changes and additions merit
implementation, and may narrow, postpone or decline any of them. The Rust
transition alone does not commission this work. The coordinator organizes
implementation and review within the selected scope.

**Exit:** implemented behavior corresponds to the selected responsibilities,
with evidence that distinguishes it from the old behavior and protects the
intended invariants. Unimplemented decisions receive an explicit disposition.

## Disposition of the former plans

- The fleet convention is now standing development guidance in `AGENTS.md`.
  No separate fleet implementation project remains.
- Product orchestration is dropped as a planned project. Existing supported
  interfaces remain; no code or test depends on its former plan.
- CLI reduction supplies stage 1 inquiry material. Its old findings and
  implementation schedule have not been executed.
- Click integration is dropped. Its earlier role was to discipline parts of
  the Python implementation before Rust; the coordinated transition no longer
  warrants that intermediate migration. The archived `docs`/`request` work and
  `CLICK-FOLLOWUPS.md` remain at `archive/2026-10-23/click-integration`
  (`56686e9`) as possible reference material, not an integration or repair queue.
  There is no replacement preparatory parser-migration stage. Python is now
  frozen as the reference baseline; a bounded Python change would be an
  explicit exception recorded here, reopening that baseline.
- Linux container installation is dropped; Linux and WSL acceptance belongs
  to stage 4.
- The test-speed execution schedule and speculative design companion are
  retired. Existing harness improvements remain. Sharding stays declined;
  no new performance or test-consolidation project is commissioned. Historical
  findings are preserved under `reports/development-history/`, with substantive
  custody leads summarized for stage 2.
- Submodule support is retained as the stage 3 candidate above.
- Unmerged branch work is preserved under `archive/2026-10-23/` tags. Archived
  commits and notes supply context, not active worker assignments. Linked
  worktree contents and Stewart custody records are outside this cleanup.

Keep this plan current as decisions change. When the program completes or is
abandoned, give unfinished work a disposition, move enduring contracts to
their proper homes, and remove this document.
