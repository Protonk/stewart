# Experiment reports

An experiment report assembles a proposal, checked technical observations and an
optional attributed assessment into one ordinary reading. Assembly is read-only.
It grants no permission, starts no process in a retained audit and decides neither
scientific success nor whether an investigation was satisfactory.

## Reading and authority

Read the question and comparison in the proposal first. The technical return
accounts for each commissioned audit, its available evidence, ending, submission,
custody, usage and observation scope. The experimenter's assessment connects those
observations to the question and states limitations, costs, outstanding judgments
and decisions. Assessment may be pending while technical review and custody work
proceed. A completed block can leave its scientific question open.

The proposal and assessment are attributed authored text. Their file hashes bind
the text selected for assembly; neither their content nor the claimed authorship
is apparatus-certified. The technical return checks evidence under the reviewer's
stated scope. Permission still comes from the principal's commission; a packet's
authority text is not proof of that permission. An answer or a prose claim is
never promoted into a checked finding by appearing beside checked observations.

The proposal should name the question, comparison, discriminating observations,
limits of inference, proposed budget, explicit placements, permitted variations
and stopping rules. The assessment should say what was established, what was not,
what remains unexercised or unknown, and what remains to be done by whom under
which authority. Distinguish estimates, usage-based calculations and independently
observed billing. Deferred billing and unresolved judgments remain visible even
when the experimenter considers the block accounted for. These are authoring
responsibilities, not a schema for satisfactory intellectual work.

## Records and later observations

The selected design is a read-only assembler over the existing packet, session,
export and reviewer. Local vocabulary changes alone cannot assemble a block's
question and evidentiary position. A replacement experiment runner would add
execution policy before there is a commission for further delegation. The
assembler leaves that policy where it is and makes its consequences visible.

The block manifest selects an authored proposal and one or more retained batches.
Each batch is bound by its plan hash. Plans supply the complete placement inventory
and exact commission; neither omitted exports nor absent session results remove
an audit from the report. The assembler reads current session records when their
schema is supported and independently reviews every immutable export. It never
translates historical session receipts into the new schema. Unsupported or absent
session records remain linked and explicitly unassessed; available exports can
still establish observations. Native and Linux evidence keep their distinct scope.

Every export is a dated observation. The most recent collection attempt determines
whether a current observation is available. A later withheld, failed or incomplete
collection must not make an earlier checked snapshot look current. Earlier checked
observations remain visible with their dates. Later manager closure can establish
closed custody without changing an earlier observation or implying auditor
submission. A lost caller reply is separate from the later evidence review.
Later checked evidence can resolve unknown effects or a failed collection while
the earlier operation's failure stays visible. That historical failure is not a
permanent current evidence gap. A later observed placement after a batch-end
`not_started` record needs reconciliation of timing and authority; neither record
is silently overwritten or declared false.

The technical position has a deterministic digest covering the selected proposal
identity, inputs and checked observations, including the reviewer source identity.
Binding the proposal's bytes does not certify its content. An optional assessment names
that digest. An assessment of an earlier position remains attributed to it and is
marked as requiring reconciliation with the current position; it cannot silently
resolve current actions. Reassembly writes a new output directory and leaves every
earlier report and source intact. No generic action-resolution or scientific
verdict engine is needed.

## Producers, fields and consumers

| Record / fields | Consumer and disposition |
| --- | --- |
| Commission: runs, limits, placement/retry bounds, account, authority, executable/source/image bindings | Intake, launch gates, standalone audit binding and block inventory. Keep exact commission. Interpretation does not amend it. |
| Audit binding: commission, run, binary, input inventory, destination | Standalone export reviewer. Keep even though the plan contains the commission: exports must be independently checkable and must match their selected batch. |
| Host: container identity, bindings, credential source, timing, scan, exit, outcome | Operator recovery and rehearsal admission. Keep host observations; remove the copied `session_outcome` and duplicated binary classification. The bound packet owns build identity. |
| Session: placement state, caller reply loss, pre-close review, export, stop reason | Batch controller, smoke, host and rehearsal admission. Separate observation from policy; count check/operation failures separately from a live stop without submission. Label review timing. |
| Rehearsal expectation match | Rehearsal gate only. A synthetic control intentionally failing review/export can pass its comparison. Live observations have no fake-scenario verdict. |
| Review: checks, failures, scope, ending, cause, usage, coverage, submission, sealer, delivery, closure | Automatic ordinary close, rehearsal controls, independent review and report. Checks complete independently of submission. All custody values are unknown until the full review completes. |
| Export: interval, completeness, scan, archive hash/size, outcome | Safe collection, review, report. Preserve withholding and failure reasons, and never infer evidence absence from a withheld archive. |
| Operator: action, exit, safe state, private reply, confirmation, collection | Explicit operator work and controls. Preserve the source and action; inspection verifies bytes, not answer quality. No loss surrender occurs implicitly. |
| `local_iteration_only`, `witness_scope` | Qualification gates and reader's interpretation of evidence. These vary with actual observer and environment; keep them. |
| `model_qualified: false`, `unassessed`, `approved: false`, `loss_surrendered: false` | Standalone scope/authority notices. Keep where the artifact is independently used; do not repeat them at every assembled row. None is a new outcome axis. |
| Report: input identities, technical position, authored texts and assessment basis | One human reading and its matching JSON view. The report doesn't introduce another execution status or duplicate the complete source documents. |

## Distinguishing cases

These expectations are fixed before implementation checks. A complete review
means the named procedural checks completed, not that an answer is good.

| Case | Required ordinary reading / control |
| --- | --- |
| Ordinary submission | Checked evidence; auditor submitted; delivery and closure separately observed. Empty-but-valid submission is an invariance for procedural review, not answer quality. |
| Planned turn-limit stop | Checked ending at the limit; no submission; no apparatus failure merely from this ending. Current live policy still halts later placements, which remain listed as not started. An unexpected exception differs: effects unknown, controlled failure retained. |
| Unexercised mechanism | A narrow check may count offered/used affordances in complete captures. Correct answer text does not imply exercise. Missing capture must produce unknown, not a zero count. Changing answer prose alone is an invariance. |
| Missing evidence | Incomplete review with controlled reason; current custody/coverage unknown. An independently retained source and altered copy provide a firing control. |
| Withheld or failed export | Explain incomplete membership, scan match/uncertainty, or archive-write failure. Originals remain private; absence of an exported observation says nothing about the answer. |
| Lost caller reply | Reply loss visible independently of a later checked submission. No replacement placement. |
| Later manager closure | Earlier no-submission/open-custody observation remains dated; later manager seal/delivery/closure is shown. Auditor submission stays false. |
| Assessment pending | Technical reading available; no claim of scientific conclusion. Supplying an assessment changes attributed text, not checked observations or custody permissions. |
| Later evidence / old assessment | Mark the assessment's earlier basis. Identical reassembly keeps the technical digest; added collection changes it. Preserve both reports. |
| Unresolved judgment / deferred billing | Explicit attributed disposition in the assessment; no forced negative scientific verdict and no billing certification. |

## Execution boundaries

Live placement policy remains conservative: stop after an observation without a
checked auditor submission, reply loss, incomplete review, failed/withheld export
or unknown effects. A live turn-limit stop is a policy stop, not a rehearsal
expectation failure. Completion of one placement does not authorize the next.
Ordinary automatic close still requires a checked auditor submission and a
received caller reply. Inspection, collection and explicitly authorized manager
closure remain available before intellectual assessment.

Shell success describes the command's technical work. A successfully observed
live policy stop may exit zero while listing unstarted work. Evidence review and
reporting return nonzero for missing/incomplete current observations or unresolved
execution records; interpretation pending does not make the technical command fail.
Rehearsal admission still requires the complete matching control inventory, no
skips and the Linux observations. Native runs are iteration only.
