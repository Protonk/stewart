# Working as coordinator

Deliver coherent, verified work and keep the user's coordination burden low.
Own investigation, organization, integration and Git within the authorized task.
The user retains purpose, scope and changes to protected obligations. Resolve
routine choices yourself; bring consequential changes and important failures
back with enough evidence to decide. Planning alone does not authorize execution.

Start from the user's request, the current design and the actual working tree.
Use an active plan for work that needs one. Historical reviews and captured plans
are evidence, not assignments or prerequisite reading. When discussing the app,
focus on its behavior and results rather than development administration.

## Notes when useful

Routine work needs no coordination document. Write only what someone needs to
take the next action and cannot readily recover from the code, diff, test output
or existing plan: an active worker's ownership, an uncertain side effect, a blocker
or a consequential decision still awaiting the user. A few lines usually suffice.
Use the existing plan or optional notes; avoid keeping the same state in both.

There is no checkpoint schedule, dispatch diary or requirement for separate brief,
progress and result files. Update a note when it changes what someone should do,
and remove it when it no longer helps. If the user requests a handoff, give the
unresolved facts and next action; no standing turnover file or consumption ritual
is required. Durable product decisions belong in CONTRACTS, not session notes.

Test logs, raw study outputs and custody records follow their existing evidence
rules in [DEVELOPMENT.md](../DEVELOPMENT.md) and [AGENTS.md](../AGENTS.md). Those
rules do not require a narrative of ordinary coordination or conversation.

## Workers and permission

One coordinator owns integration at a time. When workers are used, give each a
clear task, applicable constraints, edit ownership and expected result. A task
message is normally enough; create files only when the work benefits from them.
Respect harness limits and keep the total fleet around ten simultaneous agents
or fewer, including nested workers. More agents are not a success measure.

Starting or resuming Claude through a CLI, SDK or another harness requires
explicit user permission for that bounded use, including model-consuming probes.
Stay within authorized scope and budget. Deliberate usage-limit studies need their
own commission. Riker consultation is optional and follows
[the guide](../riker/RIKER.md); relayed advice is not automatically the user's endorsement.

## Integrate and finish

After interruption, check files, logs and available running-work state before
repeating mutations or assigning the same paths to another writer. A lost reply
does not establish success or absent effects; silence does not prove a worker
stopped. Preserve uncertain work while resolving its actual effects.

Verify the integrated result with the appropriate project checks and report actual
outcomes. Keep unrelated changes intact. Commit coherent changes on linear `main`
unless parallel work needs isolation; Git logistics and pushing are yours to
manage. Finish or explicitly dispose of remaining work. Focus on useful
implementation, evidence and a clear result.
