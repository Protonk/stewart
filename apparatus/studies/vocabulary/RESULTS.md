# Vocabulary comparison findings

The 2026-11-09 comparison completed all **six placements and six audit closures**.
The ordinary and seeded-recovery pairs submitted sufficient answers. Both
three-turn cases stopped before submission: the control preserved one limit
entry and the candidate preserved no answer entries. Manager custody faithfully
returned and closed both selections without surrendering losses.

The comparison found a concrete reply defect: a `citation_invalid` refusal still
said "Nothing was recorded." even though raw capture was retained. The existing
[refusal contract](../../../docs/INTERFACE.md#13-reply-envelope) requires
"No answer edit was applied." The correction is implemented with service and
independently authored driver checks and has passed Linux acceptance.
The live encounters used the original frozen binaries, not the repaired build.

These are the Stewart experimenter's attributed readings, separate from the
procedural checks. They establish neither model qualification nor a general
performance preference. No further model placement is selected.

## Comparison and observed results

[STUDY.md](STUDY.md) fixes the protocol. The historical control uses
`acceptance-05`, executable SHA-256
`9553371d20683125874569e471ba38d752d2ed9bff20c0ce8a41e73af86ddb09`,
with unchanged apparatus at `a36acbb`. The candidate uses
`acceptance-vocabulary-03`, executable SHA-256
`72dc02154d718d40af2108235ab3e7f046dd92cc2687d392437c53159201f95e`,
with apparatus at `79d304c`. Each used its own matching reviewer; historical
receipts were not converted to the newer schema.

All encounters used `claude-haiku-5-5`, medium effort, `open-inquiry/1`,
160,000 cumulative input tokens and 12,000 output tokens. Ordinary and recovery
cases allowed 16 turns; constrained cases allowed three. Captured arrangement
bodies and question bytes matched within each pair. Each constrained case used
its arm's ordinary question and arrangement, changing only the turn allowance.

| Trial | Case | Requests / tool calls | Final procedural checks | Recorded ending and answer | Calculated USD |
| --- | --- | --- | --- | --- | --- |
| 01 | Control ordinary | 7 / 9 | 78 | Auditor submission; one sufficient account | 0.0044792 |
| 02 | Candidate ordinary | 7 / 9 | 80 | Auditor submission; one sufficient account | 0.0045257 |
| 03 | Candidate recovery | 8 / 9 | 83 | Auditor submission; corrected observation and account | 0.0056504 |
| 04 | Control recovery | 8 / 11 | 79 | Auditor submission; corrected observation and account | 0.0059808 |
| 05 | Control constrained | 3 / 4 | 75 | Turn limit; manager-sealed limit entry, incomplete answer | 0.0016397 |
| 06 | Candidate constrained | 3 / 4 | 73 | Turn limit; manager-sealed empty answer | 0.0015797 |

Every final review has zero failed checks, verified delivery and completed
closure. Check counts differ with the operations and custody paths exercised;
they are not answer grades. The initial constrained reviews had 66 and 64 checks,
before manager sealing and delivery added the remaining custody evidence.

### Ordinary work and the wording defect

Both ordinary auditors first paired a full-file range with a quotation that
omitted the heading, then tried a quotation missing the final newline. Both
edits were refused. Search supplied exact ranges, after which each recorded,
prepared and submitted a correct account of the 14-day recovery window and the
absence of a support-response-time promise. Missing-section notices did not
cause filler entries. The candidate initially batched a refused record with
prepare, but later prepared and submitted the corrected revision.

This pair preserves the ordinary procedure without showing a request-count
improvement. Candidate calls 2 and 4 expose the stale `citation_invalid` wording;
candidate constrained call 2 repeats it. Mechanical refusal and raw retention
worked. The defect concerns the scope of the message, not lost answer content.
Nothing in these encounters isolates that wording as the cause of an auditor's
mistake or ending.

### Recovery preserved the existing entry

Both recovery auditors recorded a valid observation, inspected re-entry,
attempted the seeded inexact-quotation replacement, and inspected re-entry again.
The `quote_not_found` refusal left the original handle, preview and revision
unchanged and was visible in the later state. Both repaired that same entry,
added an account and submitted revision 3, with one current observation.

The candidate exposed the captured family and version and used the required
"No answer edit was applied." wording for this refusal. The historical control
used its older state and message vocabulary. The treatment combines reply
revision and family exposure; their effects are not separately identified.

Both auditors batched some steps despite the question's waiting instruction.
The candidate composed its account in the same request as the successful repair;
the control observed that repair before composing its account. Actual execution
preserved the required state. These remain encounter observations, not new
product defects or grounds for additional placements. Re-entry occurred within
one placement and does not demonstrate actual context loss or interruption.

### Constrained endings and later custody

Each three-turn case read the policy, received the same quote/range refusal and
searched for the correct range on its last request. The control separately
recorded a supported limit entry. The candidate instead prepared its empty
selection. Neither repaired the account or submitted before stopping. These are
fresh encounters, not identical ordinary trajectories truncated at turn three.

Neither auditor received a near-limit warning. In both ledgers, the 20-percent
threshold triggered only after the third response, when zero turns remained.
The notice was planned for request four and explicitly marked `not_sent`.
This exercises the stop and retained unsent notice, not an auditor response to
a warning. That live coverage limit is explicit; no additional paid encounter
was selected to fill it.

Manager close sealed the actual selections, delivered them for inspection and
then required explicit confirmation. The control's return retains its one limit
entry; the candidate's rendering says "No answer entries recorded." Refused
prose remains raw evidence and was not promoted into either answer. Confirmation
establishes custody, not substantive success.

All 100 original control files and all 99 original candidate files remain
byte-identical through the final snapshots. The respective second snapshots'
125 and 124 files also remain unchanged; final collection added nine files to
each. No model continuation, replacement trial, loss surrender or evidence
disposal occurred.

## Resources and limits

The six placements used **36 requests and 36 attempts, 46 tool calls, 205,625
input tokens and 6,586 output tokens**, with no estimated usage or retry.
Calculated cost is **USD 0.0238555**, using the dated pricing observations in
`.scratch/vocabulary-study-01/compatibility-and-cost-01.json`. Independent billing
is unobserved. The principal stated that the Haiku budget was externally preset;
the study did not independently inspect its amount or enforcement.

Direct-TLS provider captures are Stewart-owned, without an independent live
provider witness. Inputs were independently copied before intake, and reviewers
checked captures, ledger records and delivered bytes. One observation per arm
is a mechanism comparison, not a causal estimate of model-wide behavior.
Manager replies were inspected during custody, but these readings do not
establish usability for independent human managers. Compaction, interruption,
continuation, the full C10 gate and native WSL2 qualification remain outside this
block.

The selected repair changes the common `citation_invalid` message to agree with
its retained effects. Other known citation-refusal messages were checked; the
not-found and ambiguous-quote paths already use the required sentence. No new
restriction, answer-quality gate or Haiku-specific prompt adjustment is selected.
A post-repair model encounter is not needed to check this deterministic wording
contract. No further model use is selected by this block.

Native checks passed 247 default Cargo tests and 311 fault/sabotage tests, with
35 ignored in the latter configuration. The driver self-test passed all 352
checks without skips, and its case list loaded 123 cases. A focused comparison
against retained pre-repair binaries found 24 message-scope failures across
recording and replacement; the repaired binaries passed 1,849 checks with zero
failures outside control variants. Both sabotage controls and all eight
message controls fired. Earlier sandbox-denied loopback attempts remain retained
as failed or skipped, not rewritten as successes.

The subsequent Linux suite `.scratch/acceptance-vocabulary-citation-01`, built
from `027def8`, qualifies the correction on native aarch64 and emulated x86_64.
Both platforms passed every case with no skips or failures outside deliberate
control variants, and every sabotage and driver control fired. The new refusal
case passed in both binary variants on both architectures. Native command and
protocol timing gates passed; emulated timings did not gate qualification.
[The qualification record](../../qualified.md) owns the exact counts, digests and
source identity. This completes the selected vocabulary work. Full real-model
qualification, native x86_64 and WSL2 evidence remain separate requirements;
future model use needs rehearsal bindings matching its own build and inputs.

## Evidence and retention

Exact inputs, six packets, authority, source bindings, costs, launch records and
pair comparisons remain in `.scratch/vocabulary-study-01`. Its
`comparison-final/result.json` binds the final per-placement reviews and totals.
Each original run is pinned in [the qualification record](../../qualified.md):

- `.scratch/vocabulary-live-01-control-ordinary`
- `.scratch/vocabulary-live-02-candidate-ordinary`
- `.scratch/vocabulary-live-03-candidate-recovery`
- `.scratch/vocabulary-live-04-control-recovery`
- `.scratch/vocabulary-live-05-control-constrained`
- `.scratch/vocabulary-live-06-candidate-constrained`

The first four attributed readings are in `review/`; the constrained cases keep
`review/`, `review-02/` and final `review-03/` beside three immutable exports.
Technical results, exact answer bytes and attributed assessments remain separate.
Pinning retains evidence; it does not qualify a model.

Repair verification and pre-repair native binaries remain at
`.scratch/vocabulary-citation-repair-01`; its `review/result.json` binds the
native outcomes. Independent driver checks, before/after host runs and their
controls remain at `.scratch/vocabulary-citation-driver-01`, with the aggregate
in `host-result.json`.
The Linux suite's `review/result.json` records its inspected controls and verified
work-archive digests. Earlier vocabulary implementation and Linux-repair checks
remain in `.scratch/vocabulary-implementation-01` and
`.scratch/vocabulary-linux-repair-01` under their original source bindings.

Both matching Linux rehearsals are retained and pinned at
`.scratch/vocabulary-control-rehearsal-01` and
`.scratch/vocabulary-candidate-rehearsal-01`. Each observed 15 audits, passed 50
reviewer comparisons, fired 44 reviewer controls, passed seven operator and 11
report comparisons, and fired both Linux process-access controls. Both included
the exact templates and synthetic saved-connection collection, with no model
calls or skips. The unchanged historical apparatus remains in
`.scratch/vocabulary-control-worktree-01`; earlier rejected setup attempts remain
in the study evidence. Keep the run containers and original records until the
principal authorizes disposal.
