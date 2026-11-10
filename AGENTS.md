# Developing Stewart

Stewart is an experimental Rust audit service in [`service/`](service), built
as the binary `stewart`. These rules apply to all development work.
[README.md](README.md) owns the account of its maturity and demonstrated status.
Experimental status leaves room to change the design; it does not cancel custody
obligations, excuse unreported failures or turn intended behavior into evidence.

## Start a task

1. **Read the request and inspect the working tree.** Check `git status` and
   preserve unrelated changes. Other sessions may be working in this checkout.
2. **Read the specification the task touches.** [DESIGN.md](DESIGN.md) explains
   purpose and architecture; [CONTRACTS.md](CONTRACTS.md) owns decided behavior,
   implementation status and the reasons for boundaries. [docs/INTERFACE.md](docs/INTERFACE.md)
   and [docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md) define the exact interface
   and forms. [ACCEPTANCE.md](ACCEPTANCE.md) states the evidence owed. Resolve
   schemas and mechanisms within those decisions.
3. **Find remaining work in tracked `*-PLAN.md` files.** Use
   `git ls-files '*-PLAN.md'`. The coordinating plan owns cross-plan order;
   each topic plan owns its decisions and tasks. Historical conversations,
   reviews and captured plans are evidence, not assignments or competing design.
   Removed material is not a gap to repair. Planning alone does not authorize
   execution.
4. **Identify the required checks before editing.** Use
   [What to run for what you changed](development/DEVELOPMENT.md#what-to-run-for-what-you-changed).
   Notice the driver-independence rule below before reading implementation code
   for a task that may need acceptance-driver changes.

## Decisions and authority

"The user" in development guidance is the development principal. Stewart's users
are the people who supply material and operate it. Today they are the same person;
the principal acts as their proxy and decides on their behalf. Documentation for
Stewart's users must help them operate it, not narrate development administration.

The user retains purpose, scope, spending and protected obligations. Resolve
routine choices yourself. Bring new authority, substantive restrictions, changes
to what Stewart promises or what participants can express, and important failures
back to the user with enough evidence to decide.

Starting or resuming Claude through a CLI, SDK or another harness, including
model-consuming probes, requires the user's explicit permission for that bounded
use. Stay within authorized scope and budget. Deliberate usage-limit studies need
their own commission. A plan, fixture or previous run is not fresh spending authority.

Findings that could be sensitive outside the project, such as a toolchain security
weakness, go to the user, who decides how to route them.

## Complete the work

Whoever takes a task owns understanding it, doing or organizing it, integrating it
and verifying the result. Write useful CLI help, comments and failure messages
along with implementation and tests. Run the checks named by DEVELOPMENT,
keep their outputs through review and report actual outcomes: counts as the run gives them,
failures with their output, and skipped steps as skipped. Finish remaining work
or give it an explicit disposition. Explain the app through its behavior and
results.

After an interruption, inspect files, logs and available running-work state
before repeating a mutation or assigning the same paths to another writer. A lost
reply establishes neither success nor absent effects; silence does not establish
that an agent stopped. Preserve uncertain work while resolving its actual effects.

There is one `main` branch, and it moves forward. Use branches or worktrees as
helpful, and land coherent changes on `main`. Check `git status` before committing
and commit only the paths you changed. Work is verified when the applicable
checks in DEVELOPMENT pass; verified work may be pushed. A change whose row calls
for a container suite remains unqualified until that run, which the user schedules
and batches; it need not wait for the run to land. The public binary release gate
is separate, and its schedule remains the user's decision.

Do not add compatibility shims or rewrite historical receipts to fit a newer
schema.

## Organize larger work

Subagents are optional. Give each a clear task, applicable constraints, file
ownership and expected result; a task message is normally enough. Respect harness
limits and keep about ten or fewer simultaneous agents in total, including nested
ones. The dispatching agent integrates. Freeze shared schemas or interfaces before
parallel implementations start.

Work that needs a plan, for example because it spans sessions, gets an ordinary
tracked document at a stable `*-PLAN.md` path. Each plan owns its remaining work,
decisions and necessary inputs. State cross-plan order once in a coordinating
plan; topic plans do not repeat that staging, one another's status or prerequisite
narratives. Link to the concrete contracts, code or materials the task needs,
without mutual plan links or a prose dependency chain.

Update plans in place as decisions and remaining work change. At completion or
abandonment, give unfinished work an explicit disposition, move enduring contracts
and explanations into documentation and tests, and delete the plan.

## Maintain the documentation

Documentation describes the current product and how to work on it. Prefer direct
statements of behavior, reasons and limits. Distinguish a design commitment, an
implemented path and a demonstrated result. Keep each fact with its owner and
link to it rather than duplicating detail. Delete obsolete explanations; Git
keeps history. Preserve provenance needed to interpret or retrieve evidence, and
never rewrite historical receipts or run records as editorial cleanup.

Keep durable guidance stateless: maintained AGENTS and README files must not
route readers to particular plans, and product code and tests must stand without
them. Explain mechanisms and reasons without temporary planning coordinates.
Do not accumulate completed work reports, superseded proposals or reminders of
removed features.

Keep one current working set for the agent/human team. Generated output is
disposable after use and review; archive only originals with a present inspection
purpose that would be costly or impossible to reproduce. Citations and completed
tasks do not create indefinite retention obligations.

Notes are optional support for unfinished work, not routine deliverables or a
session history. Write only what the next action needs and the code, diff, test
output or plan does not show. Keep the same state in one place; remove a note
when it stops helping. A requested handoff gives unresolved facts and the next
action.

## Preserve independent evidence

The acceptance driver in [`apparatus/driver/`](apparatus/driver) is written from
the specification by an author who does not read the implementation. Do not edit
it in a session where you have read `service/src` or `service/tests`; search
results that print their lines count as reading them. A change needing both,
such as a specification example pinned by the driver, is split between two agents:
one changes specification and implementation, the other changes the driver from
the specification alone.

Development-machine runs help iteration but are not qualification evidence.
Evidence comes from a Linux container suite and, under ACCEPTANCE, the native
WSL2 run. Call nothing qualified without such a run. Retained `.scratch` runs
follow [Evidence and retention](development/DEVELOPMENT.md#evidence-and-retention).

A clean result needs a firing control, a case differing in the measured property
and an invariance case. An explanation remains a hypothesis until a comparison
distinguishes it from its rivals. Qualify the enforcement the binary actually
performs, such as access and stopping, not merely the settings that request it.

For studies of missing capture, extraction or deletion, keep an independent
witness and controls through review under the evidence-run retention rules. An
apparently passing run may conceal the omission being investigated. Record
observer scope and timing; keep the witness outside the disposal under test.
A rescue from development evidence does not establish that ordinary product
retrieval worked or grant authority to resume an audit.

## Use the environment correctly

A sandboxed agent shell cannot reach Apple `container` because its Rosetta check
is denied. Prepare the command and ask the user to run it with `!`.

Run Python with an explicit interpreter and isolated startup (`-I`, plus `-B`
where bytecode must stay unwritten). Isolated mode ignores `PYTHONPATH`, so
documented commands do not set it.

For user-relayed consultation, [riker/RIKER.md](riker/RIKER.md) defines “ask Riker
for help.” Consultation is optional; relayed advice is not automatically the
user's endorsement.
