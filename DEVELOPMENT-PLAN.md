# Stewart's five-stage development plan

Status: the five-stage sequence is agreed; Click integration is dropped.
Stages 1 and 2 are decided. The status contract and the custody decisions are
recorded in [CONTRACTS.md](CONTRACTS.md) with their implementation status; the
findings documents and their run records remain until Rust acceptance evidence
supersedes them, because a run's record leaves with the document that cites
it. Python is frozen as the reference baseline; decided departures are
implemented in Rust. Stage 2 closed on 2026-10-24. Stage 3, consideration of
additions, is the next commission; its proposed terms are in its section and
await the user's instruction to proceed.
This document owns the current sequence, stage outcomes and consequential
decisions. Internal assignments and execution details belong to the coordinating
agent. The [longer-term vision](VISION-PLAN.md) describes the working relationship.

Current checkpoint, 2026-10-24: the user decided D1 as six close rules plus
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
commissioned the same day; its first wave is complete and integrated in
`CUSTODY-ADDITIONS-FINDINGS.md`, with independent review in progress and the
recommendations awaiting the user.

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
executed qualifications of any harness.

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

**Exit:** a coherent desired custody arrangement, with additions accepted,
declined, narrowed or deferred. Separate semantics ready for implementation
from exploratory ideas; inclusion as a candidate grants no implementation
authority.

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
first, beginning with status against the existing corpus of Python-written
sessions, then the write path, then close; write the acceptance suite against
the contracts and drive the CLI so it is language-agnostic. Close every live
Python audit under Python before Rust closes anything.

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
