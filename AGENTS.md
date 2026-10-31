# Developing Stewart

These rules apply to every development task, large or small, whoever takes it.
Stewart is the Rust audit service in [`service/`](service) (binary `stewart`),
specified by [DESIGN.md](DESIGN.md), [CONTRACTS.md](CONTRACTS.md),
[ACCEPTANCE.md](ACCEPTANCE.md), [docs/INTERFACE.md](docs/INTERFACE.md) and
[docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md); [README.md](README.md) states
its status. Start product work from the specification. Exact schemas and
mechanisms are engineering work within its decisions. CONTRACTS.md states the
decided behavior, its implementation status and the reasons for product
boundaries. Historical conversations, reviews and captured plans are evidence,
not assignments or a competing design; removed material is not a gap to repair.

"The user" in development guidance is the development principal. Stewart's
users are the people who supply material and operate it; today they are the same
person, who then acts as their proxy and decides on their behalf. A document for
Stewart's users must serve them, not the proxy.

The user retains purpose, scope, spending and protected obligations. Bring new
authority or substantive restrictions back to the user. Resolve routine choices
yourself; bring back consequential changes, such as a choice that changes what
Stewart promises or what its participants can express, and important failures,
with enough evidence to decide. Planning alone does not authorize execution.
Starting or resuming Claude through a CLI, SDK or another harness, including
model-consuming probes, requires the user's explicit permission for that bounded
use. Stay within authorized scope and budget. Deliberate usage-limit studies
need their own commission.

## Doing a task

Whoever takes a task owns its result: understanding it, doing or organizing the
work, integrating it and verifying it. Start from the user's request and the
actual working tree, and read the specification the task touches. Run the checks
that the "What to run for what you changed" table in
[DEVELOPMENT.md](DEVELOPMENT.md) names. Preserve command outputs and report
actual outcomes: counts as the run gives them, failures with their output, and
skipped steps as skipped. When discussing the app, focus on its behavior and
results rather than development administration. Finish or explicitly dispose of
remaining work.

After an interruption, check files, logs and available running-work state before
repeating a mutation or assigning the same paths to another writer. A lost reply
establishes neither success nor absent effects, and silence does not prove an
agent stopped. Preserve uncertain work while resolving its actual effects, and
preserve unrelated working-tree changes. Other sessions may be working in the
same checkout: check `git status` before committing, and commit only the paths
you changed.

There is one `main` branch, and it moves forward. Organize in-flight work in Git
as suits it, such as branches or worktrees, and land coherent changes on `main`.
Work is verified when the checks the table names for it pass, and you may push
verified work; a binary release schedule, still to be set up, will be the public
gate. A change whose row calls for a container suite is unqualified until the
next such run, which the user schedules; it need not wait for that run to land.
Findings that could be sensitive outside the project, such as a security
weakness in a toolchain, go to the user, who decides how to route them.

Do not add compatibility shims or rewrite historical receipts to fit a newer
schema.

## Larger work

Subagents are optional, and more agents are not a success measure. Give each a
clear task, the constraints that apply, its file ownership and the expected
result; a task message is normally enough. Respect harness limits and keep about
ten or fewer simultaneous agents in total, including nested ones. The agent
that dispatches integrates. Freeze shared schemas or interfaces before parallel
implementations start.

## Documentation and plans

Documentation describes the current product and how to work on it. It is not a
development diary. Prefer a direct statement of the present behavior, reason or
limit to an account of what changed, who requested it or which discussion led
there. Delete obsolete explanation; do not accumulate corrections, completed
work reports, superseded proposals or reminders of removed features. Git keeps
that history. Preserve provenance when it is needed to interpret or retrieve
evidence, and never rewrite historical receipts or run records as editorial
cleanup.

Work that needs a plan, for example because it spans sessions, gets one. Active
plans are ordinary tracked documents with stable `*-PLAN.md` paths. Each plan
owns its remaining work, decisions and necessary inputs. State cross-plan order
once in a coordinating plan; topic plans do not repeat that staging, one
another's status or prerequisite narratives. Link to the concrete contracts,
code or materials the work needs, without mutual plan links or a prose dependency
chain. Give shared status and sequencing a single owner.

Update plans in place as decisions or remaining work change. At completion or
abandonment, give unfinished work an explicit disposition, move enduring
contracts and explanations into documentation and tests, and delete the plan.
Keep durable guidance stateless: maintained AGENTS and README files must not
route readers to particular plans, and product code and tests must stand without
them. Explain mechanisms and reasons without temporary planning coordinates.

Notes are optional support for unfinished work, not a routine deliverable or a
session history. Write only what the next action needs and the code, diff, test
output or plan does not show; keep the same state in one place, and remove a
note when it stops helping. A handoff the user asks for gives the unresolved
facts and the next action.

## Evidence and environment

The acceptance driver in [`apparatus/driver/`](apparatus/driver) is written from
the specification by an author who does not read the implementation. Do not edit
`apparatus/driver/` in a session where you have read `service/src` or
`service/tests`; search results that print their lines count as reading them. A
change that needs both, such as a specification example the driver also pins, is
split between two agents: one changes the specification and the implementation,
and the other changes the driver from the specification alone.

Runs on a development machine are not evidence. Evidence comes from a Linux
container suite and, under ACCEPTANCE, the native WSL2 run; nothing is called
qualified without such a run. Retained runs under `.scratch` follow
DEVELOPMENT.md's [Evidence and retention](DEVELOPMENT.md#evidence-and-retention)
section. A clean result needs a firing control, a case differing in the measured
property and an invariance case. An explanation remains a hypothesis until a
comparison distinguishes it from its rivals. Qualify the enforcement the binary
actually performs, such as access and stopping, not merely the settings that
request it. Write useful CLI help, comments and failure messages along with
implementation and tests.

For studies of missing capture, extraction or deletion, keep an independent
witness and controls through review under the evidence-run retention rules; an
apparently passing run may conceal the omission being investigated. Record
observer scope and timing, and keep the witness outside the disposal under test.
A rescue from development evidence does not establish that the product's
ordinary retrieval worked or grant authority to resume its audit.

A sandboxed agent shell cannot reach Apple `container` (its Rosetta check is
denied), so prepare the command and ask the user to run it with `!`. Run Python,
such as the acceptance driver, with an explicit interpreter and isolated startup
(`-I`, plus `-B` where bytecode must stay unwritten). Isolated mode ignores
`PYTHONPATH`, so documented commands do not set it.

## Riker

For user-relayed consultation, [riker/RIKER.md](riker/RIKER.md) defines “ask
Riker for help.” Consultation is optional, and relayed advice is not
automatically the user's endorsement.
