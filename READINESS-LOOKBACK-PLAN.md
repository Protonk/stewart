# Readiness session lookback

Audit the work done after receipt of the repair plan, repair supported defects,
and leave the repository ready to continue at M3. This is an execution plan for
a fresh agent, not a session report or a replacement for the live topic plans.

## Scope and recovery points

The input repair plan is `READINESS-FOLLOW-UP-PLAN.md` at `ba92086`. Examine the
session's changes in `ba92086..f3ddfef`, including planning decisions,
specifications, service behavior, tests, apparatus, live commissions, evidence
interpretation and this planning cleanup. Use these two snapshots when recovering
details removed from maintained plans:

- `2f22846`: plans updated to the status after C4, before history was removed.
- `f3ddfef`: plans reduced to remaining work and concrete inputs.

Read the original plan and intervening diffs directly from Git. Follow earlier
sources when necessary to assess a session change or claim; do not restart the
antecedent readiness review or treat historical proposals as new assignments.
Removed text is not itself evidence of a missing obligation. Investigate whether
the current code, contracts, evidence or plans actually leave something undone.

Use [AGENTS](AGENTS.md), [DESIGN](DESIGN.md), [CONTRACTS](CONTRACTS.md),
[INTERFACE](docs/INTERFACE.md), [QUESTION-FORMS](docs/QUESTION-FORMS.md),
[ACCEPTANCE](ACCEPTANCE.md) and the [runtime contract](docs/claude-code/CONTRACT.md)
as the current authorities. [DEVELOPMENT](development/DEVELOPMENT.md) owns checks
and retention; the [qualification index](apparatus/qualified.md) locates retained
suite results and encounters. Inspect original evidence, not only summaries.

## Audit and repair

- [ ] Inspect the working tree, available running-work state and Git range.
  Establish the work actually performed and the decisions it implements before
  choosing checks. Cover the whole range, including early repair work, rather
  than stopping at the recent harness comparisons.
- [ ] Preserve driver independence before reading implementation. Give any
  needed `apparatus/driver/` edits to an author who has not read `service/src`
  or `service/tests`, with specification-derived expectations. The integrating
  agent owns understanding, integration and verification of all repairs.
- [ ] Check specification and implementation changes against the accepted
  decisions: stopping and close races, submission/refusal effects, custody and
  readback, literal text and citations, transport parsing, limits, notices and
  continuation. Trace claims of completion to the relevant behavior and evidence.
  Detect accidental changes to promises, admission or expression, and new
  compatibility paths or rewritten historical forms.
- [ ] Review changed tests and instruments for independent expected values,
  firing controls, differing and invariance cases, actual reached conditions,
  wrong-reason failures, skipped prerequisites counted as passes and self-derived
  oracles. Inspect the original failures and later checks, including repairs to
  apparatus that had previously reported a clean result. Run focused comparisons
  where a specific uncertainty remains; broad reruns alone do not settle it.
- [ ] Audit the launchers, observers, profiles and reviewers against their
  documented boundaries: immutable input/source bindings, credential handling,
  environment and tool access, launch reservations, bounded stopping, interrupted
  or lost replies, export membership, package reconstruction and closure.
  Separate controls that request enforcement from observations that establish it.
- [ ] Reconcile the session's frozen commissions and approvals with actual
  authentication/model starts, continuations, unused slots, limits and spending
  statements. Check each completed comparison's scope and disposition against
  its originals. Previous approval or unused allowance cannot become authority
  for a replacement, probe or resumed audit.
- [ ] Review evidence interpretations: service captures versus independent
  witnesses; MCP payload versus auditor-facing conversation; partial assistant
  snapshots versus final checkpoints; reported tokens versus billing; observed
  coverage versus answer correctness. Check page-substitution findings,
  unexercised continuation and cap/reminder observations without upgrading them
  into broader model or platform claims.
- [ ] Verify custody and stopping from retained records and necessary fresh
  read-only observations. In particular, locate the open audit and exact writer
  through `.scratch/readiness-m2-live-sw3z-default-01/REVIEW.json` and establish
  their availability for M3. Verify claims of preserved packages and prior
  archives through close. Missing evidence is a limitation to resolve, not proof
  of absence. Preserve witnesses outside any operation being examined.
- [ ] Check qualification, evidence pins and maintained documentation against
  actual source/binary identities, counts, failures, skips and observation scope.
  Native results cannot qualify Linux behavior. Keep original failed records
  unchanged; correct interpretations separately. Preserve selected originals
  and exact writers still needed for open custody or an unresolved finding.
- [ ] Compare the two planning snapshots with current plans. Restore only
  substantive unfinished obligations or necessary inputs that were lost; put
  each in its existing owner. Remove duplicate, completed or obsolete tasks.
  Do not rebuild a historical checklist, ledger, running log or turnover file.
- [ ] Repair supported defects within the settled contracts, with useful help,
  diagnostics and the required independent checks. Update the owning live plans
  in place for work that remains. Completing unrelated future work is not a
  lookback gate. Bring new spending, changed promises or protected obligations,
  substantive tradeoffs and important failures to the principal with evidence.

## Verification and completion

For each change run the checks named by
[DEVELOPMENT](development/DEVELOPMENT.md#what-to-run-for-what-you-changed), retaining
outputs through review and reporting actual failures and skips. Schedule needed
container qualification with the principal; supply host commands when the
sandbox cannot perform an observation or run. Do not substitute native checks
for required Linux evidence or repeat mutations after an uncertain response.

This lookback authorizes investigation and routine repairs, not fresh live-model
or authentication use. Do not resume or close the retained M2 audit, alter its
writer or archive, or resurrect sealed comparisons while auditing them. Prepare
any newly necessary bounded commission before seeking its specific approval.

Complete when the session's work has been examined, supported defects are
repaired and checked or have explicit dispositions with owners, material limits
are reported, and no unresolved authority, stopping or custody uncertainty is
silently carried into M3. Put durable corrections in their owning documents and
tests; keep only unfinished work in plans. Commit coherent repairs, then delete
this plan and its coordinating work-order row.

Proceed directly to M3 preparation after completion; no new general permission
is needed. Its concrete live commission still requires approval. Return for a
necessary host command or a material decision, not merely to ask whether to begin
already authorized preparation.
