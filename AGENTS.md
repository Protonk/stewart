# Developing Stewart

Stewart is an experimental Rust audit service in [`service/`](service), built
as the binary `stewart`. These rules apply to all development work.
[README.md](README.md) owns the account of its maturity and demonstrated status.
Experimental status leaves room to change the design; it does not cancel custody
obligations, excuse unreported failures or turn intended behavior into evidence.

## Find your way

- **Code.** The [crate guide](service/README.md) maps the modules by role, the
  integration tests and the build features. Each module opens with an account
  of what it does and cites [docs/INTERFACE.md](docs/INTERFACE.md) by section
  number; read the cited section rather than the whole interface.
- **Behavior.** [DESIGN.md](DESIGN.md) explains purpose and architecture;
  [CONTRACTS.md](CONTRACTS.md) owns decided behavior, implementation status and
  the reasons for boundaries. INTERFACE and
  [docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md) define the exact interface
  and forms. [ACCEPTANCE.md](ACCEPTANCE.md) states the evidence owed.
- **Source archives.** Start in `service/` with the included dependencies. The [offline build instructions](development/DEVELOPMENT.md#build-from-a-release-source-archive) include native tests and explain how to compare a shipping binary.
- **Builds and checks.** [DEVELOPMENT](development/DEVELOPMENT.md) covers
  building from the vendored crates, the Cargo configurations, the independent
  drivers and the container suites. Use the unprivileged development account in the Linux guest for iteration.
- **Audits belong to their writer.** Only the exact binary that created an audit
  can change it. A rebuilt binary can read its receipt and status but refuses
  every mutation, including `run` and `close`. Keep that binary until its
  audits close
  ([version obligations](CONTRACTS.md#versions-and-legacy-obligations)).

## Start a task

1. **Read the request and inspect the working tree.** Check `git status` and
   preserve unrelated changes. Other sessions may be working in this checkout.
2. **Read the specification the task touches.** Resolve schemas and mechanisms
   within its decisions. For a defect, first reproduce it as a failing test
   beside the code or under `service/tests/`.
3. **Find remaining work in tracked `*-PLAN.md` files.** Use
   `git ls-files '*-PLAN.md'`. The coordinating plan owns cross-plan order;
   each topic plan owns its decisions and tasks. Historical conversations,
   reviews and captured plans are evidence, not assignments or competing design.
   Removed material is not a gap to repair. Work within the current task and
   leave deferred ideas for later.
4. **Identify the required checks before editing.** Use
   [What to run for what you changed](development/DEVELOPMENT.md#what-to-run-for-what-you-changed).
   Notice the driver-independence rule below before reading implementation code
   for a task that may need acceptance-driver changes.

## Decisions and authority

Exercise your judgment and proceed within the task's scope. You own technical
design and priorities, including refactoring, internal interfaces, documentation
and error handling. Choose fixtures, construct tests, assess their coverage and
decide how to run and improve them. Interpret unexpected failures, fix
demonstrated defects, and explain any limitation you accept. Use the retention
rules to clear disposable evidence. Speculative work can stay unselected.

The maintainer (the development principal) sets the project's purpose, scope
and protected obligations, and controls spending, credential use and external
effects such as public release and disclosure of sensitive findings. You can
change public forms and schemas while preserving those obligations, including
custody, attribution and the substance of what participants can express.
Decide what merits discussion. If an operation lacks authority, leave it
unperformed, account for it and continue with the work you can do.

Starting or resuming Claude through a CLI, SDK or other harness, including a
model-consuming probe, requires explicit permission for that bounded use.
Deliberate usage-limit studies need their own commission. Stay within the
authorized scope and budget.

When only the maintainer has the machine access or credentials for an
authorized operation, give them the command and its purpose. You still own the
engineering decision and interpretation of the result.

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
for a container suite can land after its development checks pass. It remains
unqualified until the suite passes for the changed source.

Do not add compatibility shims, old-form readers, converters or parallel code
paths, and do not rewrite historical receipts to fit a newer schema. A changed
form replaces the old one, which is then refused;
[CONTRACTS](CONTRACTS.md#versions-and-legacy-obligations) owns the rule.

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

Documentation describes the current product and how to work on it. Write operator
guidance for the people who supply material and use Stewart. Prefer direct
statements of behavior, reasons and limits. Distinguish a design commitment, an
implemented path and a demonstrated result. Keep each fact with its owner and
link to it rather than duplicating detail. Delete obsolete explanations; Git
keeps history. Write documentation and comments as if the present design had
always been so; provenance belongs in evidence records. Preserve provenance
needed to interpret or retrieve evidence, and never rewrite historical receipts
or run records as editorial cleanup.

Each directory's agent guidance is its `AGENTS.md`; a `CLAUDE.md` beside it is
a symbolic link to that file, so every agent reads the same guidance.

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

Run development checks in the Linux guest.
Evidence comes from the Linux container suite for the corresponding release or
development runtime. Each suite qualifies the behavior it exercises. Retained `.scratch` runs
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

If the sandbox blocks a required guest or Lima operation, use the harness's normal
escalation route for that command.

Run Python with an explicit interpreter and isolated startup (`-I`, plus `-B`
where bytecode must stay unwritten). Isolated mode ignores `PYTHONPATH`, so
documented commands do not set it.
