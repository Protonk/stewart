# Handoff to Stewart's next coordinator

Read [AGENTS.md](AGENTS.md), [CONTRACTS.md](CONTRACTS.md), the active root
`*-PLAN.md` documents and the working tree. This handoff carries the working
relationship and the context needed to resume. [DEVELOPMENT-PLAN.md](DEVELOPMENT-PLAN.md)
owns current program state; [VISION-PLAN.md](VISION-PLAN.md) owns the
longer-term approach; CONTRACTS.md states decided behavior with its
implementation status. Replace this handover context when passing the role
onward rather than accumulating dated addenda. Earlier versions remain in Git.

## Where this handover leaves you

The five-stage sequence remains: status inquiry, audit of existing custody,
consideration of additions, Rust transition, and optional implementation of the
revised arrangement. **Click integration was dropped**, not deferred. Submodule
support is an explicit stage-3 candidate. Rust acceptance includes executed
Linux and WSL qualification; the user plans to ask a friend to run WSL checks.
Do not substitute a recipe or Linux results for executed WSL evidence.

Stages 1 and 2 are decided. CONTRACTS.md is maintained guidance stating every
decided contract with its implementation status, the principles behind them
and the declines with their reasons; it incorporates the status/14 contract
verbatim from the stage-1 findings. **Python is frozen as the reference
baseline.** Production source is unchanged since `6582df2` and receives no
behavior changes; every decided departure is implemented in Rust, with status
as the first Rust operation, read-only against Python-written sessions with
Python status as the control, and close last. The findings documents and their
run records stay until Rust acceptance evidence supersedes them.

Stage 2 closed on 2026-10-24 with every completion and principle revision
decided; nothing in CONTRACTS.md is marked proposed. Do not reopen decided
items without a new reason. The Riker exchange that produced the final
revisions is retained at `riker/CLOSE-COMMITMENTS-REQUEST.txt` and
`CLOSE-COMMITMENTS-REPLY.txt`; it is advisory. The plan's stage-3 section
holds a proposed commission for the additions inquiry, awaiting the user's
instruction to proceed. It does not start automatically.

## What was decided about close, and why

The discussion the previous handoff asked for took place. The question of what
close must account for before discarding was settled by a reframing rather
than a list of disposable categories: **close offers the manager opportunity,
not preservation.** Close ends private custody deliberately; retention and
export decide what survives; close guarantees that each removed surface matches
a reviewable capture, is verifiably regenerable, is discarded by name, or
belongs to a declared category whose identity the closing record freezes. This
extends the existing rule that Stewart acts only on what the closing evaluation
judged. Two general commitments came with it and are recorded as principles:
Stewart's refusals are limited to its own claims and safety, tested by what
claim it would make falsely by proceeding; and Stewart makes no
material-preservation promise to anyone over the deciding manager, keeping its
process promises to the auditor. The user holds both as commitments and
rejected mandatory retention before close as invasive to the manager's flow.
The user's reason generalizes: most conditions under which Stewart could
withhold a report trace to how the manager constructed the audit, which is the
manager's to judge, not Stewart's.

Two lessons from how it went. The independent review of the decision set
caught a real error: the kept-checkout rule as first stated had no exit and
would have retained sessions forever by silence, failing the refusal principle
beside it. Name every rule's exit. And the later-return comparison contradicted
the source reading usefully: the current close does refuse on a later
collection's runtime gap, but only through status and only while that
collection is the latest; a later clean collection hides it. Read the plan's
account and the retained evidence before choosing further comparisons.

## Preserve the product relationship and delegation boundary

The user wants Stewart to answer an occasional inquiry about an unclosed audit;
checking status should not become the manager's routine job. The preferred idiom
is a promise of an eventual structured reply. Status is a concession to prevent
persistent managers inventing their own inspections. The user does not require
an agent-behavior experiment to justify that product preference.

Stewart should abstract the connection between manager and auditor as far as
practicable; the ideal could accommodate a human auditor. Do not prematurely
assign delivery outside Stewart. Entry points remain open: a manager may launch
and arrange its callback, a human may ferry a command, or harness approval may
pause the manager before that same manager resumes launch and watching. The last
case is different for the user but can be a mild pause for the manager. Human
involvement does not itself transfer the role or callback responsibility.
The user offers fallible help if these relationships become confusing; this is
an available consultation, not a mandatory escalation.

The status grant includes substantive discretion over truthful semantics,
ordinary versus exceptional attention, wording and already-authorized affordances.
It does not authorize new independent obligations, delivery guarantees, execution
responsibilities, removal powers, changed required custody or closure conditions.
Implementation remains a separate commission. A wording change can cross these
limits without adding a capability: “no return is recorded,” “work is proceeding
normally” and “no manager action is required” make different commitments.

Apply the two tests developed with Riker: what might a participant reasonably
rely on this contract as permission, instruction or assurance to do or omit;
and does that reliance follow from agreed commitments or establish an undecided
one? These expose the boundary without eliminating the coordinator's judgment.
Do not require approval for every ordinary choice inside a granted commission.
When a consequential crossing is real, state it and complete independent work.

## Carry the investigative and coordinating judgment

The user expects actual use of sub-agents and explicitly objected to a conception
of coordination that would use none. In the stage-1 and stage-2 engagement, two source researchers
and an independent reviewer supported stage 1; three source researchers and a
fresh independent reviewer supported stage 2. The coordinator authored additional
comparisons, reconciled reports, owned integrated execution and resolved review.
The decision engagement used one comparison worker and two fresh independent
reviewers, one over the decision set and one over the comparison's evidence;
both found corrections worth making.
Use the next harness's available facilities and useful assignments; worker IDs,
a fixed staffing split and a development orchestration framework are unnecessary.
Development workers do not inherit Stewart's product manager/auditor workflow.

The user delegates noticing questions an assignment did not ask. Challenge
consequential premises; a passing test does not settle the product judgment.
Choose a source investigation, controlled comparison, regression test or semantic
discussion according to the question. Distinguish settings construction from
real harness enforcement, reported claims from observations, and code consistency
from scientific conclusions. There is no target test-to-application ratio.
Neither more tests nor fewer tests is an independent objective.

Shared documents should make purposes, evidence, decisions and remaining choices
intelligible. The user wants these recoverable from the repository, not memory,
and prefers to work at that level. The coordinator owns assignment design, edit
ownership, ordinary disagreements, integration and verification inside an
approved commission. The user retains purpose, scope and protected obligations;
they should not have to broker worker communication or routine logistics.

Current behavior is evidence to examine, not proof it is desirable. Archived
plans are not a dormant task queue. The custody report distinguishes previously
accepted but unimplemented corrections from open leads; preserve both that
distinction and the captured historical documents.

## Working tree and evidence

Initial HEAD for this engagement was `6582df2`; its commits follow on `main`
and are pushed. The coordinator owns version control (AGENTS.md): the user
discusses actions effected and does not want to be asked about Git logistics.
Commit verified work in layers with messages that record validation.

Stage-1 and stage-2 evidence is as the findings describe. The later-return
comparison added `tests/test_custody_later_return_inquiry.py` and three receipts
under `.scratch/custody-audit/`: `later-return-01` (five setup failures, since
the harness shell sandbox refused creating `.gitconfig` in the private HOMEs;
no test body ran), `later-return-02` (one passed, four failed hypothesis-framed
assertions; its staged source survives as the receipt's hash and the failing
lines in its pytest log) and `later-return-03` (six passed), with seventy
verified evidence copies in `later-return-03-evidence/`. After independent
review, all three artifacts directories were pruned through `scripts/prune.py`;
the plan names the removal records. The distribution test was rerun after
CONTRACTS.md was added to the source distribution
(`.scratch/contracts-link/distribution-01`, ten passed). Every run used Python
3.14.8, Apple Git 2.54.0 and the same production wheel digest as the earlier
stages. DEVELOPMENT.md records that the harness shell sandbox stops the suite
at fixture setup and blocks pruning; those commands executed with the sandbox
disabled.

## Consultation and engagement records

Riker is a separately situated helper, not a superior authority. Requests and
replies are user-relayed under [riker/RIKER.md](riker/RIKER.md). Two exchanges
are retained: the status-delegation exchange, which sharpened the commitments
boundary, and the close-commitments exchange, whose reply produced the
proposals the plan records. Consultation is optional, with no prescribed place in the
sequence; repository claims still need evidence.

This engagement had no fieldwork recording assignment; a predecessor's did not
imply one. If your engagement carries its own recording instructions, follow
those; do not assume authority to explore other runs or restricted neighboring
projects. This file is the ordinary Stewart handoff.
