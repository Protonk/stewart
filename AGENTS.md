# Developing Stewart

The design review is closed. Start product work from [DESIGN.md](DESIGN.md),
[CONTRACTS.md](CONTRACTS.md) and [ACCEPTANCE.md](ACCEPTANCE.md), not historical
conversations or prototype briefs. Exact schemas and mechanisms are engineering
work within those decisions; bring new authority or substantive restrictions
back to the user. Historical evidence is not a competing design.

One coordinating agent owns the coherent development result: understanding the
task, organizing work, integrating changes and verifying the result. The user
retains purpose, scope and protected obligations.
[Coordination guidance](coordination/README.md) sets the working constraints,
including for dispatched workers. Notes are optional
support for unfinished work, not a routine deliverable or a session history.

[CONTRACTS.md](CONTRACTS.md) states the behavior Stewart is decided to have,
with each contract's implementation status and the reasons for declined
changes; changes to Stewart's intended responsibilities are recorded there.

For user-relayed consultation, [riker/RIKER.md](riker/RIKER.md) defines
“ask Riker for help.”

Preserve unrelated working-tree changes. Active plans are ordinary tracked
working documents with stable paths; discover them by the `*-PLAN.md` naming
convention. Update a plan when decisions or remaining work change; Git preserves
history.
At completion or abandonment, give unfinished work an explicit disposition,
move enduring contracts and explanations into documentation and tests, and
delete the plan. There is no obligation to retain every planning paragraph.
Keep durable guidance stateless: maintained AGENTS and README files must not
route readers to particular plans, and product code and tests must stand without
them. Explain mechanisms and reasons without temporary planning coordinates.
Git history holds earlier material, including the retired Python tool (last
present at `267aaf0`); do not restore it to the tree. Do not add compatibility
shims or rewrite historical receipts to fit a newer schema.

"The user" in development guidance is the development principal. Stewart's
users are the people who supply material and operate it; today they are
the same person, who then acts as their proxy and decides on their behalf. A
document for Stewart's users must serve them, not the proxy.

Development workers do not inherit Stewart's manager/auditor workflow.
Conversely, the product does not
inherit the development fleet's steering and supervision practices. Stewart
serves a bounded commission and structured return; additional intervention
facilities need a specific commission or custody reason, not parity with a
harness-managed swarm. After product handoff, the manager receives a structured
return through the agreed interface; live product access is restricted to
commission readback, operating status and close. The first Rust release's
manager-designated archive remains readable by its owner; no live answer viewer,
steering channel or secrecy from the host owner is promised. Rich
selected context and investigative latitude remain compatible with a narrow
question. The auditor has only Stewart's commission-bound tools,
without a private-location inventory. Qualify actual access and stopping, not merely the
settings. Exact wire and process mechanisms instantiate CONTRACTS; they do not
select an extra intervention channel.

Stewart stays agnostic about the intellectual utility of audits, including in
development evaluation. Its major intellectual influence belongs in question
types and the constrained audit space. Examine whether answer restrictions let
participants express, inspect and contest permitted responses; do not use
agreement with a preferred outcome as the success criterion. Restrictions that
privilege or exclude substantive outcomes need explicit design deliberation.
Auditor and manager judgments remain attributed. CONTRACTS.md owns the principle.

The design separates recording a commission from promising its
replay; the manager owns constructing another question. There is no restart-from-start
facility. An interrupted run continues the same ledger and cumulative limits;
earlier code or tests do not justify restoring a staged workflow. Stewart must
account for its incomplete custody operations through supported paths:
agent-managers should not need to improvise repairs to private state. Recovery
cannot grant another investigative execution or conceal uncertainty, and a
family of retries is not simplified by renaming it recovery. Stewart has
no dedicated program executor or staged program release/run workflow. Permitted
auditor tool use remains bounded by its commission and actual access grants;
supplied execution reports retain their attribution. Continuation grants no fresh
investigation or reset allowance.

Run Python, such as the acceptance driver, with an explicit interpreter and
isolated startup (`-I`, plus `-B` where bytecode must stay unwritten). Isolated
mode ignores `PYTHONPATH`, so documented commands do not set it.
[DEVELOPMENT.md](DEVELOPMENT.md) gives the development commands, and its
[Evidence and retention](DEVELOPMENT.md#evidence-and-retention) section governs
retained runs under `.scratch`. Preserve command outputs and report actual
counts.
A clean result needs a firing control, a case differing in the measured
property and an invariance case. An explanation remains a hypothesis until a
comparison distinguishes it from its rivals. Qualify real harness enforcement
separately from settings construction. Write useful CLI help, comments and
failure messages along with implementation and tests.
For studies of missing capture, extraction or deletion, keep an independent
witness and controls through review under the evidence-run retention rules;
an apparently passing run may conceal the omission being investigated. Record
observer scope and timing, and keep the witness outside the disposal under
test. A rescue from development evidence does not establish that the product's
ordinary retrieval worked or grant authority to resume its audit.
