# Stewart's five-stage development plan

Status: the five-stage sequence is agreed; Click integration is dropped.
The status inquiry is complete under delegated contract authority. Its contract
and evidence are recorded; Python implementation is not commissioned. The user
has commissioned stage 2, the audit of existing custody responsibilities. Its
investigation and independent review are complete; the user's custody decisions
remain open.
This document owns the current sequence, stage outcomes and consequential
decisions. Internal assignments and execution details belong to the coordinating
agent. The [longer-term vision](VISION-PLAN.md) describes the working relationship.

Current checkpoint, 2026-10-23: `STATUS-INQUIRY-FINDINGS.md` records the decided
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

**Current outcome:** `CUSTODY-AUDIT-FINDINGS.md` maps existing responsibility
families, costs and recovery; separates prior accepted but unimplemented fixes
from new recommendations; and records controls, outcomes and limitations. The
coordinator recommends retaining identity, attribution, raw capture, exact review
binding, explicit execution permission, no uncertain replay and bounded removal.
The following proposals remain for the user's assessment, not implementation:

- D1: account for relevant contents before close discards them; distinguish
  captured runtime damage from new drift, define the treatment of recovery/HOME
  contents, and decide later-return and kept-checkout dependencies. Remove
  command-rendering success as a closure precondition while keeping independent
  writer and custody checks.
- D2: allow independently verified report export with explicit surrounding
  capture damage, without claiming the whole collection is sound.
- D3: refuse supplemental destinations below gitlinks before preparation,
  directing supplied copies to ordinary paths; allowing pinned descendants is
  an alternative requiring its own explicit contract.
- D4: allow human launch acknowledgments without invented model/effort values;
  leave delivery and watcher responsibilities open.
- D5: initially service old Python lifetimes through retained writers; decide
  successor authority explicitly before Rust mutates them.
- D6: retain access/effect protections and make their actual capability and
  coordination limits explicit; qualify proposed replacements separately.

Configured Git-filter execution during preparation and inconsistent replacement
views during input-pin construction versus capture coverage were demonstrated.
They are implementation issues under retained trust commitments. The broader
Git environment policy is not qualified by those narrow probes. No production
change was made and no real harness enforcement was tested.

Evidence runs are `.scratch/custody-audit/comparisons-01.json` and
`.scratch/custody-audit/git-filter-02.json`; the report owns their exact selectors,
failure/correction account, tested-source hashes and compact evidence manifests.
Retirement/pruning follows DEVELOPMENT.md. Stage 2's investigation can conclude
with explicit reserved choices; stage-3 additions do not start automatically.

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

Leads carried from the status inquiry, not decisions to change obligations:

- Concluded close currently inherits live-runtime and handoff-integrity effects
  from status, including preparation-state precedence. The runtime-only
  comparison in `STATUS-INQUIRY-FINDINGS.md` demonstrates the coupling. A separate
  comparison also shows cached manager-launcher damage failing command generation
  and therefore close despite matching loaded writer bytes. Examine
  whether these conditions independently protect conclusion after sound capture
  and triage; preserve them until a decision changes them.
- Status's offered close is stricter than direct close's preconditions. Examine
  whether newest-collection triage and pending retention/release/run belong to
  advice or mandatory closure. Source: `status.py:1373–1395` and
  `close.py:1115–1136`; no refusal change has been commissioned.
- Private handoff retention precedes public publication; unkeyed preparation
  has no universal final success receipt. A new completion requirement is an
  open custody question, not a license to reinterpret or rewrite historical
  records. Optional keyed outcomes cannot become an implicit requirement.

The inquiry also leaves delivery responsibilities and human-auditor interaction
open. Consider them with the relevant custody question or stage-3 addition;
neither an external-only delivery boundary nor a watcher requirement was chosen.

**Exit:** a reasoned account of what to retain, revise or abandon, with explicit
decisions and unresolved questions. Implementing every decision in Python is
not a condition of completing this stage.

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
  There is no replacement preparatory parser-migration stage. A bounded Python
  change may still be commissioned for an independently justified benefit.
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
