# Retained development evidence

This is a retention index, not a design or work queue. Completed study directories
retain raw packets, actor outputs, checks and their provenance unchanged. Their
briefs describe their historical commissions, not new instructions. Relative
references to retired design files are historical coordinates at their recorded
source revision; do not recreate those files as current guidance.

The [closure report](../reports/design-review-closure/RESULT.md) records the
extraction/deletion boundary. Runtime reports, audit receipts, corpus sources,
independent witnesses, local refs and `.scratch` run records are retained under
DEVELOPMENT.md. The [retired-document run index](../reports/design-review-closure/RETAINED-RUNS.md)
owns their otherwise orphaned local run references. No artifact directory or
evidence ref was removed in this consolidation.

The question-family paper review remains under question-examples-01/review-01/;
it contains exact original packets and outputs. Its finding was a small comparison
and presentation improvement, with 52 paper calls, 20 entries and 41 checked
citation ranges across four actor attempts. That is not runtime qualification.
The fresh reader was run once; neither missing expected sections nor empty
submission was exercised by an actor. The interface spec and acceptance cases
carry those gaps forward without another open-ended design-review cycle.

## Recovery-critical local evidence

The three original audit outcome commits were not ancestors of main and had no
containing refs when inspected. Local development-evidence refs and exact text
copies protect them. [Corpus retention](successor-inquiry-01/CORPUS-RETENTION.md)
names the refs, hashes and source copies; a main-only clone does not carry them.
Retained runs under `.scratch` are local and untracked, and follow DEVELOPMENT.md's
retention rules. No evidence is pruned by design closure.

## Local records this index owns

Each entry is under `.scratch/`. Where a report owns a run's findings, the run
stays with that report under the retention rules.

| Records | Owner of findings |
| --- | --- |
| `coordinator-intake-20261028-02/` | The outgoing coordinator's intake record. The review prose is retired; its decisions and acceptance obligations are in the maintained product docs. |
| `alignment-20261028-01/`, `coordinator-intake-20261028-01/` | The design-conversation tenure. Conversation prose is retired; the source checkpoint is recorded in the closure report. |
| `route-research-01/`, `plan-fit-review-01/`, `answer-structure-check-01/`, `auditor-cases-01/` | This index; the first-leg program is abandoned and applicable cases are in ACCEPTANCE.md |
| `linux-first-light-01/`, `linux-check-01/`, `stale-tests-01/`, `fifo-hygiene-01/` | This index. `linux-check-01/RESULTS.md` holds the Linux findings from the retired development plan. |
| `opus-intake-01/`, `opus-readiness-01/`, `opus-turnover-run-012/`, `astra-turnover-20261027-01/`, `coordinator-intake-run-012/`, `coordinator-transfer-guidance-01/`, `first-leg-riker-brief-01/` | This index (earlier intakes and turnovers) |
| `custody-shakedown-01/`, `custody-concern-routing-01/`, `interaction-simplifications-01/`, `manager-return-direction-01/`, `manager-collect-discussion-01/`, `manager-collect-authority-01/`, `return-completeness-01/`, `authoring-boundary-01/`, `commission-recall-plan-01/`, `forward-program/` | This index (earlier decision records) |
| `coordinator-intake-20261026-01.json`, `coordinator-intake-recording-01.json`, `coordinator-discussion-20261026-01.json` | This index |
| `submission-prototype-01/` | [submission-design-01/RESULT.md](submission-design-01/RESULT.md) |
| `opus-preparation-audit-01/` | [reports/opus-preparation-audit-2026-10-27/RESULT.md](../reports/opus-preparation-audit-2026-10-27/RESULT.md) |
| `commission-intake-01/` | [reports/commission-self-audit-2026-10-27/RESULT.md](../reports/commission-self-audit-2026-10-27/RESULT.md) |
| `receipt-challenge-01/` | [receipt-challenge-01/RESULT.md](receipt-challenge-01/RESULT.md) |
| `answer-revision-01/` | [answer-revision-01/RESULT.md](answer-revision-01/RESULT.md) |
| `construction-execution-01/` | [construction-execution-01/RESULT.md](construction-execution-01/RESULT.md) |
| `fresh-authoring-01/`, `fresh-authoring-preparation-01/` | [fresh-authoring-01/RESULT.md](fresh-authoring-01/RESULT.md) |
| `return-boundary-01/` | [return-boundary-01/RESULT.md](return-boundary-01/RESULT.md) |
| `answer-representation-01/` | [answer-representation-01/RESULT.md](answer-representation-01/RESULT.md) |
| `handoff-transition-01/` | [handoff-transition-01/RESULT.md](handoff-transition-01/RESULT.md) |
| `successor-inquiry-01/` | [successor-inquiry-01/COORDINATOR-PROGRESS.md](successor-inquiry-01/COORDINATOR-PROGRESS.md) |

Additional runs cited by retired plans/findings are assigned to the closure
report's RETAINED-RUNS index. No source or witness is disposed by deletion of a plan.
