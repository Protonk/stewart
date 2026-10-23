# Stewart's six-stage development plan

Status: program agreed; the status inquiry is next. This document owns the
current sequence, stage outcomes and consequential decisions. Internal
assignments and execution details belong to the coordinating agent. The
[longer-term vision](VISION-PLAN.md) describes the working relationship.

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

Determine what status should establish between preparation and collection,
and which live validations belong to operations such as collection and close.
Use [the retained CLI-reduction inquiry](planning/inputs/cli-reduction.md) as
source material. Its old branch instructions are historical; this program
sets the sequence and authority.

The first useful result is a proposed public contract with concrete prose and
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

**Exit:** the user has reviewed the recommendation and decided the intended
status contract, remaining uncertainty and whether to implement it in Python
now or defer it. Investigation does not itself authorize the proposed runtime
changes. Its decisions can be reconsidered during the wider refusal audit.

## 2. Move selectively to Click

Review the existing `docs` and `request` implementation, preserved at
`archive/2026-10-23/click-integration` (`56686e9`). Its
`CLICK-FOLLOWUPS.md` describes remaining grammar, dependency and identity
questions. Review and integrate useful work against the selected status
contract, then choose a bounded further slice if warranted.

Separate generic CLI infrastructure from Stewart-specific behavior. Preserve
intended external contracts and disclose deliberate grammar changes. Set a
stopping point based on useful simplification and the coming Rust transition;
the stage does not require migrating every command. This is a further exercise
of delegated implementation and integration after the inquiry.

**Exit:** a reviewed and verified integration, an explicit disposition of
remaining Click proposals, and a decision that further Python parser work
does or does not justify its cost.

## 3. Audit refusals and existing custody responsibilities

Examine what each restriction protects, which obligations it creates, its
costs, and the consequences of retaining, hardening, softening or removing it.
Use [prior custody questions](planning/inputs/custody-questions.md) as leads to
recheck, alongside the status inquiry. Preserve the distinction between prior
user decisions, observed defects and untested proposals.

Independent inquiry is useful where it can challenge a consequential premise.
The coordinator recommends; the user decides changes to Stewart's intended
responsibilities. Neither current implementation nor simplicity alone settles
the answer.

**Exit:** a reasoned account of what to retain, revise or abandon, with explicit
decisions and unresolved questions. Implementing every decision in Python is
not a condition of completing this stage.

## 4. Consider additions to custody

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

## 5. Transition to Rust

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

## 6. Optionally implement the revised custody arrangement in Rust

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
- Linux container installation is dropped; Linux and WSL acceptance belongs
  to stage 5.
- The test-speed execution schedule and speculative design companion are
  retired. Existing harness improvements remain. Sharding stays declined;
  no new performance or test-consolidation project is commissioned. Historical
  findings are preserved under `reports/development-history/`, with substantive
  custody leads summarized for stage 3.
- Submodule support is retained as the stage 4 candidate above.
- Unmerged branch work is preserved under `archive/2026-10-23/` tags. Archived
  commits and notes supply context, not active worker assignments. Linked
  worktree contents and Stewart custody records are outside this cleanup.

Keep this plan current as decisions change. When the program completes or is
abandoned, give unfinished work a disposition, move enduring contracts to
their proper homes, and remove this document.
