# Handoff to Stewart's next coordinator

Read [AGENTS.md](AGENTS.md) and the active root `*-PLAN.md` documents, then
inspect the working tree. The expectations below apply regardless of provider
or access to earlier conversations. The active plan owns current program state;
this handoff carries the working relationship and reasons a successor should
not lose. It is selective, not a complete account of earlier conversations.
Revise its handover context when replacing it; do not accumulate dated addenda.
Earlier tracked versions remain in Git, including the predecessor at the HEAD
named below.

## Where this handover leaves you

The user has settled the five-stage sequence in
[DEVELOPMENT-PLAN.md](DEVELOPMENT-PLAN.md): status inquiry, audit of existing
custody, consideration of additions, Rust transition, and optional implementation
of the revised custody arrangement. **No Click integration.** Click previously
served as a disciplining migration for the Python repository before Rust. The
user judged that it had much less value with the transition now coordinated by
an agent. This is a decision to drop that stage, not merely to reconsider its
size. Archived Click work remains reference material.

The status inquiry has not begun. Stage 1 records three proposed commission
terms: latitude to retain justified live observations, the boundary with the
wider custody audit, and sufficient evidence and a stopping point. They remain
labelled recommendations; no runtime change is authorized. The user's latest
instruction was to write this handoff and stand by. Resume from the recorded
commission discussion when the user gives the next instruction, rather than
treating the program's existence as a dispatch instruction.

The plan also records where the findings and evidence will go. The user
specifically asked that decisions and outstanding questions be recoverable
from the repository, not conversation or memory. Preserve that property.
The current documentation changes are uncommitted against initial HEAD
`97c44d1aba9197395a4b193b29682752798eb5a4`; inspect the diff rather than relying
on this snapshot. No runtime code or tests changed, no project tests ran,
and no workers were dispatched during this engagement.

## Carry the investigative judgment

The user delegates noticing questions an assignment has not asked, as well as
organizing and executing work. Examine consequential assumptions, recognize
when passing tests leave the central claim unresolved, and arrange independent
scrutiny where it can challenge a premise. The user should not have to
interrupt agent dispatch to supply the question that makes an investigation
or its validation adequate.

A question may call for a regression test, a comparison, a source investigation,
or a semantic decision. Choose evidence that can distinguish plausible
explanations. Explain what was established, what alternatives were challenged,
and what uncertainty remains. Completion of an assignment is not by itself
resolution of its motivating question. For status, clearer output does not by
itself demonstrate better agent behavior.

There is no target test-to-application ratio. The user's observations about
test-heavy projects were reflections on their development practice, not a
request to increase Stewart's test volume. Tests should answer useful questions
and protect meaningful contracts. Neither more tests nor fewer tests is an
independent objective.

## Keep the shared view at the right level

Human-readable documents support discussion of stage purposes, intended
behavior, consequential alternatives, evidence and integrated outcomes. This
is usually the level at which the user wants to work. Go into implementation
or coordination details when they help a decision.

Within an authorized commission, the coordinator owns task decomposition,
worker assignments, workspace and edit ownership, integration and verification.
The user retains authority over direction, scope and consequential semantic
changes. Bring those decisions and important failures or disagreements back
clearly; resolve routine engineering choices without repeated permission
requests. The user should not need to broker worker communication.

Use the harness's available facilities and choose providers according to the
work. Stewart's development coordination does not require a new orchestration
framework or adoption of its product's manager/auditor workflow.

## Distinguish obligations from questions

Existing custody contracts govern current operations. A semantic inquiry may
recommend revising them, with the user's authorization. Existing behavior is
evidence to examine, and simpler behavior is a proposal to justify. Preserve
foundational distinctions while making contested responsibilities explicit.

The status inquiry concerns what inspection should establish and which checks
belong to subsequent operations. Treat recommendations, field provenance and
operation preconditions as contract questions. A quieter display alone does
not settle them. Preliminary source reading found that `close._concluded`
consumes status attention items; it did not establish which resulting refusals
are necessary. Moving a check out of inspection needs an explicit account of
its remaining owner or a proposed change in responsibility. The active plan
carries the inquiry's scope and the decision about any implementation.

Archived plans, notes and commits provide context and possible evidence.
They do not form a dormant assignment queue. Recheck their claims and preserve
the distinction between prior user decisions, proposals and demonstrated
behavior. The current commission determines what work proceeds.

## Keep outside consultation optional

Riker is a separate helper with a different contextual embedding, including an
idealized account of Stewart and no ready access to its code. That perspective
can challenge assumptions; it carries no superior capability or authority.
Repository-specific claims still need evidence.

Either the user or coordinator may identify a useful consultation during their
conversation. Requests and replies are user-relayed under the existing
[exchange guidance](riker/RIKER.md). Consultation has no prescribed question
taxonomy or place in the development sequence. Do not turn it into a required
next step in a committed plan or a worker assignment.
