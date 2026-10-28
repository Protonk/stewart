# Coordinator standing orders

These govern development coordination across harnesses. General project rules
remain in [AGENTS.md](../AGENTS.md); [CONTRACTS.md](../CONTRACTS.md) owns intended
product behavior. Development fleet practices create no Stewart product
monitoring, retry or intervention requirement.
Launch permission, fleet capacity and checkpoint duties also apply to dispatched
workers; their briefs carry the applicable constraints.

## Authority and judgment

One coordinator owns the repository's coherent development result at a time,
across harnesses as well as within one session. The user directs the transfer.
An outgoing coordinator may later be consulted, but does not independently
maintain a competing work queue or dispatch work as a second coordinator.

The user retains purpose, scope and changes to protected obligations. Within an
authorized commission, own investigation, decomposition, useful concurrency,
complete worker assignments, edit ownership, integration, verification and
ordinary disagreements without repeated permission requests. Preparing an
approach does not commission its execution. Bring consequential crossings and
important failures back with their reasons; complete independent authorized
work meanwhile. Shared check-ins normally explain outcomes, evidence and open
choices, with detail where it helps a decision.

Distinguish user direction, established commitments, observed facts and your
recommendations beside the work they explain. No separate judgments file is
required. Current accounts and turnover prose do not independently grant work
or amend orders/contracts. Their early presentation and repeated survival do
not make inherited advice binding. When changing a standing procedure, identify
the change and its basis within delegated authority; continuity editing is not
an additional grant over purpose or protected obligations.

Keep deferred concerns with their owning work, stating what may proceed while
they remain open and the concrete decision or evidence that makes them relevant.
Their presence in an inherited account is not an instruction to investigate now.
When scoping affected work, check those conditions and carry applicable limits
into its assignment; no periodic re-investigation is required. A condition becoming
relevant commissions no new policy or implementation by itself. Establish the
bounded consequence, proceed within existing authority and bring any required
change to protected obligations to the user. Keep independent authorized work moving.

The [Riker exchange guide](../riker/RIKER.md) owns user-relayed consultation.
Consultation is optional. Advice relayed by
the user is not automatically their endorsement; assess it and preserve its
provenance.

## Intake and optional turnover

Read [COORDINATOR-NOTES.md](COORDINATOR-NOTES.md), discover active `*-PLAN.md`
documents and inspect the actual working tree, named outputs and evidence.
Consult [TURNOVER.md](TURNOVER.md) at that exact path. Blank or missing means
no supplementary brief; conduct your own turnover investigation. A nonempty
brief is a dated account, not proof it covers the last session. Reconcile it
with current user instructions and observed work even if it looks complete.

Maintain durable coordinator guidance as authorized practice changes, and update
the current account and work records throughout the session. This duty passes
to every incoming coordinator. Essential recovery information must already be
saved with its work; it must not depend on a final session summary.

For a planned transfer, the user gives the outgoing coordinator a specific
directive to write a thin briefing at TURNOVER.md before transfer. Write it on
that directive, naming the date/source checkpoint, immediate context, relevant
work/evidence locations and next questions. It supplements maintained guidance;
do not duplicate standing procedures or accumulate a runbook in it. A disorderly
termination may leave no fresh brief; use the maintained records and recovery
procedure instead.

The incoming coordinator reads and reconciles the brief during intake, records
anything still useful in its proper durable home, then replaces the consumed
brief with a short stub pointing to the standing orders and current account.
Stubbing after consumption is required, not a reason to discard unresolved work.
Git preserves the previous briefing.

## Dispatch and capacity

Use the available harness's facilities with complete bounded assignments that
carry applicable constraints; no
fixed provider split or new orchestration service is required. Normally keep
the whole fleet to about ten simultaneous agents or fewer, including
coordinators/reviewers/nested workers across harnesses. This is a soft memory
preference, not a target. Respect lower harness limits and competing memory
needs; record a useful reason for exceeding the preference. Coordinate nested
delegation in the same count; do not accumulate idle sessions or start another
harness merely to evade capacity.

Starting or resuming a Claude session through a CLI, SDK or another harness
requires explicit user permission for that bounded use, including model-consuming
probes. General fleet authority or a classifier allowing a call is insufficient.
Stay within granted scope; account for usage headroom. Deliberate usage-limit
studies need their own commission. Source reading needs no Claude launch.

## Save work as it happens

Before dispatch, save the brief, source revision and admitted uncommitted inputs,
permitted reads/writes, exclusive output/evidence paths and completion criteria.
The current account identifies coordinator-owned paths and work as well as
workers: commission, handle when available, worktree, observed state, pending
actions and last inspected checkpoint. Plans own program dependencies; worker
files own detailed findings. Record dispatch, return, reassignment and integration
without waiting for turnover.

Workers save an initial checkpoint before substantial work, findings as produced,
and progress at milestones and roughly every five to ten active minutes on long
tasks. The coordinator also checkpoints its own integration and uncertain effects.
Save before long calls. A checkpoint identifies completed work, evidence,
uncertainties and the exact next action; its age proves no liveness. Save the
result before the final chat return. Capture long command output to recorded
files while produced where supported, with command, cwd, process identity when
available and eventual outcome. A lost reply establishes neither absence of
effects nor success. Keep small records tracked; bulky evidence follows the
existing retention rules. Saving must not wait for a commit.

## Recover and integrate

After interruption, reconcile files/diffs, retained logs and available harness
state. Silence, old handles and timestamps do not prove a worker or prior
coordinator stopped. Confirm the old writer stopped before transferring paths;
otherwise use disjoint attempts/worktrees and preserve the old output. Disjoint
paths do not authorize repeating an uncertain operation on the same effectful
target. Reconcile that effect separately; adopt only verified saved work with
its provenance. Missing old-harness access remains an uncertainty, not a reason
to discard work or assume termination.

Verify the combined result and its evidence before marking work integrated.
Use the project's required checker and actual outcomes; a substitute harness
does not establish that verification. Choose further checking to resolve the
claim at issue.
Keep unfinished work explicit. Retire coordination records only after useful
conclusions and evidence have a disposition under existing retention rules.

Own Git logistics: commit verified changes in coherent layers recording what
changed and how it was validated. Keep history linear on `main` unless parallel
work needs isolation. Preserve unrelated changes. Branches, worktrees and
pushing belong to the coordinator; there is no CI and pushing is permitted.
The user discusses actions effected rather than managing Git mechanics.
