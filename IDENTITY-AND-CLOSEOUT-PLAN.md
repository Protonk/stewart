# Identity, state, and closeout

Implementation has not started. This is a temporary execution plan. Read the
repository and `AGENTS.md`, then implement the contracts below in cohesive
increments. Update execution progress here; put lasting behavior in shipped
documentation and tests. No conversation, audit report, old checkout, or private
session is required. Preserve unrelated work and the separate Linux plan.

## Outcome and scope

A fresh agent can enter an explicitly selected repository, discover its recorded
audits, select one unambiguously, continue it through Stewart's supported operations,
recover from interruption, and retire its temporary resources without manually
reconstructing receipt schemas, runtime commands, or filesystem ownership.
Stewart explains every recorded resource that remains, including enrolled
external resources that require manual retirement under this plan. Sharing
delays a managed resource's retirement but never strands it.

Expand identity resolution, usable state, and resource lifecycle management
together. Scientific review, automated judgments, and the unrelated ledger
operand/case-ID fixes are outside this plan. General orchestration is a follow-on:
do not implement an agent launcher, scheduler, arbitrary command runner, automatic
assignment publication, or general command recorder here. Narrow operations
needed to establish and retire managed resources are in scope.

Completion includes a committed root `ORCHESTRATION-PLAN.md`, written against
the implemented interfaces. Its preparation is specified below; orchestration
implementation is not a prerequisite for completing this work.

## 1. Establish the identity and state contract

Start with the existing `Workspace`, repository lifetime records, session
receipts, `status`/`status_list`, derived actions, triage drafts, pinned manager
invocations, and callable API. Reuse their validation rather than introducing
a second interpretation of custody. Decide the public CLI/API and record shapes
before expanding mutations; command names and internal layout are implementation
choices.

**Selection is a caller-held reference.** Read-only discovery/selection returns
a serializable reference to the repository, workspace, recorded audit identity,
concrete session lifetime when present, and applicable implementation identity.
Selecting writes no receipt or shared "current audit" setting. Callers may save
the reference; every operation revalidates it. After losing it, the caller runs
discovery and explicitly selects again. Stewart recovers operation outcomes from
their records; it does not infer what the caller intended to work on. Operation
receipts still record the identities acted upon. A preparation result can return
a session-bound reference; a draft reference must not silently select a later
session lifetime.

**Discovery covers recorded audits.** Discover across workspaces and manager
worktrees using repository-level draft registrations and supported session,
role, and closing records under the Git common directory. Include failed
preparation, interrupted closeout, and retained closed history. Do not crawl
worktrees or guess workspace directories. A never-recorded unprepared workspace
is absent, not automatically listed as "unregistered".

Mutating initialization must record the draft audit at repository level, with
start/outcome records for its writes. Preserve default `init` preview as read-only.
Provide explicit registration of an existing, named workspace through verified
reads; this records present observations without manufacturing past custody.
Scoped resource creation must likewise have a recorded audit context before its
side effects. Existing supported session records remain discovery sources without
backfilling new draft records or rewriting history. Keep recorded state available
after a disposable manager checkout disappears; report unavailable draft files
as unavailable, without claiming their bytes can be recovered from registration.

Human-readable aliases are locators. Resolve and validate their bindings before
use. Duplicate audit names in different workspaces, reused paths, missing owners,
stale references, and unsupported records must remain explicit. Never silently
select the newest collection, a replacement lifetime, the current working
directory, or a different installed runtime. Keep existing explicit-coordinate
operations coherent with the new selection mechanism; add no historical-schema
compatibility layer.

**Runtime changes require an explicit caller handoff.** Compare verified
implementation byte identities and invocation prerequisites, not installation
paths or version labels alone. A different location alone is not a different
implementation. Refuse a mutation or its resumption under a mismatched
implementation with a stable reason. When the recorded pinned invocation can be
verified through supported metadata and descriptor-safe reads, return its
structured invocation as a next step for the caller to execute explicitly.
Construct only the supported launcher form; never execute or import recorded
code to inspect it, relay arbitrary recorded command text, or auto-dispatch to
another installation. Verification establishes consistency with the recorded
pin, not independent authenticity or permission to execute. If its runtime,
launcher, or interpreter prerequisites cannot be verified, retain the diagnostic
and name the missing prerequisite; never fall back to the current installation.

Discovery includes located unsupported records rather than hiding them. Separate
schema support, record validity, and implementation identity: a different build
with a supported schema can still receive a verified read-only view. For an
unsupported schema, report the location and only metadata readable through a
supported discovery envelope; do not infer lifecycle state from unknown fields.
Offer a pinned invocation only when that metadata and its bytes can actually be
validated. Otherwise explain that the reader/runtime is unresolved. Invalid and
unreadable records keep their diagnostics. This requires no schema migration or
compatibility shim, and discovery launches no other installation.

Expose one read-only view derived from verified records, with understandable
stage, blockers, selected evidence, resource associations, and available actions.
Do not maintain a competing mutable status summary. Missing, partial, invalid,
and unreadable records retain their distinct diagnostics.

Exit criterion: discovery and selection work from the original checkout across
multiple workspaces, including duplicate display names and broken entries,
without reading private schemas or modifying records to inspect them.

## 2. Carry verified bindings through operations

Let callers consume supported structured results and action references directly.
Extend the existing drafts and generated commands so routine continuation does
not require copying UUIDs, collection names, receipt digests, or long runtime
paths between unrelated commands. Keep exact identities inspectable.

Bind actions to their actual operands and revalidate at execution. A new
collection must not retarget an existing review; identical report bytes in two
collections must not erase collection identity. Status and mutations must use
the same validation. Selection conveys no new execution or deletion permission.
Keep observations, actor acknowledgments, auditor declarations, and manager
judgments separate; the manager still supplies substantive decisions.

**Mutations accept an optional caller-chosen request key.** The caller persists
the key before submission. Within the explicitly selected repository, reserve
the key exclusively before side effects and bind it to the operation kind,
selected audit/resource and lifetime identities, implementation identity, and
semantic inputs, including supplied input bytes rather than just their paths.
Reuse with different bindings is a stable refusal. Concurrent identical requests
must admit only one execution. This key identifies intended work; unlike an audit
reference, that intent cannot be reconstructed from matching output bytes.

A matching completed request returns its recorded outcome and original output
identities without executing again or creating another collection. A matching
partial/unresolved request returns that state without replaying uncertain side
effects. A key does not prove whether an unrecorded side effect occurred. Where
an operation supports explicit safe resumption, append fresh attempt records
under the same request and retain its frozen operands/inventory; otherwise a
new execution needs a new key and record names. Same-key inspection is not a new
execution attempt and never overwrites a receipt. Preserve the request binding
and completion/uncertainty evidence beyond session/resource retirement, so retry
cannot recreate closed work. A historical outcome must distinguish subsequently
retired outputs from currently available evidence.

Keys are optional for direct manual use and required for retry-capable
orchestration. Without a key, normal operation-specific safety gates still apply,
but a repeated submission is a new request; do not deduplicate by payload, time,
or "latest". Distinct keys can intentionally produce separate collections of
identical report bytes. If the caller loses its durable key too, discovery can
show recorded requests for explicit inspection/selection, but Stewart cannot
choose which request represented the lost intent or promise automatic deduplication.

Human output and versioned JSON must distinguish completed, partial, refused,
and unverifiable outcomes, with stable reasons and usable next steps. Read-only
inspection never repeats a side effect. Keep public functions in `api.py`.

Exit criterion: an explicit selection can be carried through collection, review
draft/submission, retention/export, and close eligibility using documented
interfaces. Stale or conflicting bindings cannot act on different evidence.

## 3. Record resources; repair close before broadening removal

Resource recording may proceed alongside the repairs. Broader deletion must
wait until both regressions below pass their repaired acceptance conditions.

Record ownership when resources are created or explicitly enrolled. Cover
manager worktrees and branches, temporary directories, exports and retained
deliverables, and associations with existing session resources. Record enough
creation provenance, lifetime identity, dependencies, and intended disposition
to distinguish exclusive temporary resources, shared/borrowed dependencies, and
retained evidence. Keep a managed resource's creation record at repository
level: the audit context that created it and every later user are associations,
so its ownership outlives the creating audit's closure. A path or registration
request alone cannot prove ownership or authorize recursive deletion. Existing
resources need explicit enrollment and verified identity; unknown ownership
remains unresolved.

**Removal eligibility requires Stewart-recorded creation in this phase.** Add
narrow creation operations for managed worktrees, branches, and temporary
directories. Explicit enrollment of an externally created resource supports
tracking, association, and closeout explanations only; even an unchanged identity
and contents snapshot plus an enrollment acknowledgment grants no removal
eligibility. Such resources require manual retirement. A managed worktree using
an existing branch does not acquire deletion rights over that branch. Creation
provenance is necessary, not sufficient: explicit close authorization, current
identity, shared-use checks, and retained-work checks still apply. A separate
ownership-transfer/disposal-grant mechanism is deferred beyond this plan.

Support the creation/failure boundary: preserve a start record before managed
side effects and capture their outcome, so an interrupted creation can be
inspected without guessing ownership. Do not turn partial creation into a broad
cleanup grant: a start record alone does not prove that a subsequently found
resource was created by that operation. One manager worktree or runtime may
serve multiple audits.

Reproduce and repair these two existing close failures in disposable fixtures:

- **Checkout ancestor substitution.** Prepare and triage an audit. Rename its
  UUID-named checkout parent aside and replace that pathname with a link to a
  decoy containing `worktree/keep.txt`. Discard-authorized abandon currently can
  delete that outside sentinel. Also interrupt a normal close before worktree
  removal, substitute the parent, and retry. Both routes must preserve the decoy
  and report the substitution. Include healthy real-directory removal, links
  inside the worktree and at its leaf, and an unrelated sibling sentinel. Cover
  initial concluded removal where applicable and controlled replacement between
  validation and use. Protect the actual traversal and Git-removal route;
  checking a pathname earlier or checking only its leaf is insufficient. This
  substitution requires manager-side access beyond the assigned auditor writes.
- **Git administrative-name reuse.** Close audit A with a failure injected at
  retention-ref deletion, after its worktree has actually been removed. Prepare
  B and verify that Git reused A's administrative pathname. Retry A: B must not
  be attributed as A's leftover or modified. Compare with no B and with B
  prepared before A's removal; retain a genuinely moved same-lifetime checkout
  case. A missing reuse condition is an unfired control, not success. The
  lifetime marker's identity field is `role_uuid`; a reused pathname alone is
  insufficient. Existing behavior falsely attributes B but preserves its files.

Use the existing close fixtures and repository lifetime tests as starting points.
Keep failed attempts and closing inventories unchanged. Add useful diagnostics
and assert stable reasons for new refusals.

Exit criterion: resource associations survive failed creation and shared use;
the close regressions discriminate the failures and pass with outside state and
replacement lifetimes preserved. No widened removal ships before this gate.

## 4. Complete resource closeout

Provide an inspectable closeout description that accounts for each recorded
resource: proposed removal, deliberate retention, shared use, or a blocking
condition/decision. Distinguish audit closure from retirement of surrounding
working resources and from retention of historical evidence. Resolve export or
retention dependencies before deleting their source or containing directory.
An export inside a retiring manager tree needs an explicit durable destination
or an explicit disposal decision; its mere existence does not make it safe.

Keep close as the explicit, gated deletion boundary. Freeze authorized removal
identities before deletion and revalidate them at use. Record outcomes and resume
interrupted removal against that inventory without widening it. Preserve work
added after planning, moved/replaced resources, and unexpected contents. Manager
branch retirement must account for changed tips and unmerged work; a clean
worktree alone is insufficient. Never blanket-clean ignored paths.

**Shared managed resources have a retirement path.** A managed resource with a
live association is in shared use: every close preserves it and names the audits
still using it. An association whose audit state is missing, invalid, or
unreadable counts as live. The close that ends the last live association may
include the resource in its frozen inventory. A resource left behind once no
live association remains (blocked at the last close, or omitted from an
inventory frozen while another association was live) is retired later by an
explicit, gated close of that named resource with the same discipline: record
first, freeze identities, revalidate at use, and resume without widening. Never
reopen or widen a closed audit's inventory to do this. At most one inventory may
claim a resource; make the claim an exclusively created record so concurrent
closes cannot both retire it. Update the custody rules in `AGENTS.md` to name
the records that authorize removal.

**Manual retirement is acknowledged, not inferred.** When a recorded resource is
absent, report that observation. Let the manager acknowledge an observed absence
as retirement outside Stewart in a separate record bound to the resource
identity and that observation; never edit the creation or enrollment record.
Revalidate the absence when recording, and refuse while the resource is present.
The view then distinguishes acknowledged manual retirement from an unexplained
missing resource. An acknowledgment grants no permission and makes no claim
about how the resource was removed; anything later found at that path is a new
observation, not the retired resource.

Run finalization through a runtime and repository context that survive removal
of disposable manager resources. Preserve shared storage, unrelated worktrees,
retained deliverables, closing records, and audit-ID reservation rules. Historical
receipt purging is outside this plan. Preserve failure records while the audit
is live; close records the failure basis before any authorized retirement.

Exit criterion: Stewart can retire eligible recorded manager worktrees, branches,
and temporary outputs as well as session resources, explain all remaining items,
and recover from interruption without a custom cleanup controller. Enrolled
external resources are an explicit manual-retirement remainder, not an unmet
promise of automatic deletion or a reason to broaden a retry. Shared use delays
eligibility but never makes it permanent: once no live association remains,
Stewart can retire the resource. An acknowledged manual retirement is reported
as such, not as missing.

## 5. Validate the complete user journey

Exercise public installed-wheel interfaces in disposable repositories. Create at
least two audits in different, including nested, workspaces and manager checkouts,
using Stewart's managed creation path for resources intended for retirement.
Include shared dependencies, enrolled externally created resources, and unrelated
work. Reuse a display audit ID across workspaces. Include a failed preparation
and two collections with identical report bytes but different receipt identities.

Start a fresh process from the original checkout with only the repository and
shipped guidance. Discover the audits, select one, inspect its actual stage,
continue with an explicitly supplied review, retain/export selected evidence,
and close its eligible resources. Persist a request key before calling, interrupt
an operation, discard the caller's in-memory state/response, and recover using
the saved key and recorded evidence. Confirm that another audit, shared runtime,
unrelated branch/files, retained bytes, and closed history
survive. Repeat observation from another directory; selection must stay bound.
The remaining-resource view must account for deliberate retention and blockers.

Verify that selecting alone writes nothing and two callers' references do not
affect each other. Lose the reference as well as process state, rediscover, and
explicitly reselect. Verify read-only `init` preview, recorded drafts before
preparation, absent unrecorded workspaces, and explicit workspace registration.
Prove healthy managed-resource removal while unchanged enrolled external resources
and an existing branch used by a managed worktree remain intact and explained.

Complete a keyed collection but lose its response: same-key retry returns the
same collection identity. A different key with identical report bytes produces
a distinct collection. Test same-key/different-input refusal, concurrent same-key
submission, and interruption before/after a side effect but before its completion
record. An uncertain result must not be silently replayed. Retry after closeout
must report the historical request without recreating retired resources. Lose
the durable key separately and verify that discovery exposes requests without
guessing intent. Do not claim exactly-once side effects from request reservation.

Use two implementations with supported schemas but different byte identities:
discovery can inspect, mutations refuse, and any verified next-step invocation
remains unexecuted. A matching implementation at another location is invariant
subject to invocation prerequisites. Include unsupported schemas, missing/tampered
runtime or launcher bytes, and untrusted invocation fields. Listing must preserve
diagnostics, avoid guessing a command, and never import or execute the other code.

Close every audit sharing a managed worktree, its branch, and a managed
temporary directory. Each earlier close preserves them as shared use; Stewart
retires them after the last association closes. Controls: an associated audit
that is still live, or changed contents or branch tip, preserves them with an
explanation; a single-audit resource is removed as before. Leave a shared
resource blocked at the last close, clear the blocker, and retire it through the
explicit resource close without changing any closed audit's records. Under a
controlled interleaving of two final closes, only one inventory claims the
resource. Manually remove an enrolled external resource and a blocked managed
resource: before acknowledgment the view reports them missing; afterwards it
reports acknowledged manual retirement with observation and acknowledgment in
separate fields. Acknowledging a present resource is refused, and an
unacknowledged absence keeps its missing diagnostic.

Test stale actions, foreign/reused identities, changed branch tips and directory
contents, links, malformed/duplicate-key control records, missing owners, and
interrupted resource creation/removal. Each measured guarantee needs a firing
control, a changed-property case, and an invariance case. Keep discovery
read-only, imports side-effect free, and filesystem access descriptor-safe.

Provision `requirements.lock` into a wheelhouse and use an explicit interpreter
with `-I -B` to run `scripts/check.py`. Run focused installed-wheel checks during
implementation and the full suite for final acceptance. Preserve outputs and
actual collected/selected/deselected counts; do not inherit historical counts.
This journey needs no real model request or scientific experiment. Synthetic
handoffs qualify lifecycle behavior only, not real harness enforcement.

## 6. Deliver the orchestration outflow and finish

Before declaring this plan complete, write and commit root
`ORCHESTRATION-PLAN.md`. Ground it in the finished CLI/API, schemas, failure
behavior, and acceptance fixtures. It must independently enable a fresh agent
to begin orchestration work after reading the repository. Include:

- The remaining mechanical work suitable for orchestration, with a bounded
  first implementation slice and an ordered sequence to expand it.
- Concrete supported entry points for selecting an audit, consuming actions,
  registering outputs, checking completion, retrying, and retiring resources;
  identify any real gaps instead of inventing interface names.
- How operation outputs and failures will be recorded without parsing human
  prose, duplicating custody truth, or replaying a completed side effect.
- A caller journal that durably records each request key and intended inputs
  before submission, reuses that key on retry, and obtains explicit decisions
  for uncertain outcomes or lost intent. Selection references remain re-derivable.
  Runtime handoff is explicit; a recorded invocation is not execution permission.
- Authorization boundaries, explicit human decisions, and failure/restart
  acceptance cases built on the completed lifecycle tests. Git recording may
  be a deliberately narrow first use case; collecting every kind of activity
  is not an automatic requirement.

Use no dependency on this conversation, this plan, deleted audit notes, or old
private state. The outflow must be actionable, not a placeholder or an assertion
that orchestration is already implemented.

Finish the main acceptance journey with the outflow present in the repository:
the fresh agent can discover and continue the audits and then find the separate
plan for starting orchestration. Document the selection, registration, removal
eligibility, shared-resource retirement, manual-retirement acknowledgment,
request-key, runtime-handoff, and failure/recovery contracts in shipped guidance
and CLI help. Commit the implementation, tests, documentation, and outflow;
remove this completed plan
once its contracts are represented there. Leave `ORCHESTRATION-PLAN.md` pending.
