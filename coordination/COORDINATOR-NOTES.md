# Current coordinator account

Updated 2026-10-28 UTC at the outgoing coordinator's turnover.
This is a working account of observed work, authority received and remaining
questions. [Standing orders](STANDING-ORDERS.md) own operating instructions;
[the directory entry](README.md) identifies intake documents. The optional
[turnover](TURNOVER.md) is supplementary. Reconcile these observations with
actual files, user instructions and available harness state after interruption.

This account was condensed at this turnover to current state, open work and the
local records it owns. The full earlier narrative, covering every completed
commission since 2026-10-24, is in Git:
`git show 313c4e3:coordination/COORDINATOR-NOTES.md`. Each completed commission's
own RESULT or COMPLETION record owns its findings and evidence.

## Current checkpoint: turnover after the design conversation

**Tenure.** The user directed the transfer in: “Please read
`coordination/TURNOVER.md` and prepare to assume the coordinator role.” Intake ran
on 2026-10-28 at clean HEAD `4037ec3` (records in
`.scratch/coordinator-intake-20261028-01/`). The user then held a long design
conversation and directed this turnover. Commits `7f29e83` through the turnover
commit record the tenure.

**The design conversation.** It is recorded in full in
[linux-mvp-01/](linux-mvp-01/README.md). Read that folder's README and AGENTS file
first. It moved from an alignment check to a proposed redesign of the successor:
Stewart as a *problem router* for cooperative actors who want to make it *just*
so. [ROUTER.md](linux-mvp-01/ROUTER.md) and
[END-TO-END.md](linux-mvp-01/END-TO-END.md) are the latest working statements.

**User direction given in the conversation** (quoted in full in
`linux-mvp-01/CONVERSATION.md`; condensed here):

- The auditor has only Stewart's tools (“R2 I want 100%”). Stewart runs the
  auditor rather than leaving launch to the manager (“I prefer the simplicity of
  R2 over R4”).
- Linux only, not a Mac tool (R6). Drop the Python baseline (“R8 I basically agree
  with full stop”). Git dependence has bothered the user; exporting history as
  files is “fine” (R7).
- Question types: the coordinator recommended a small library of question-answer
  couplings over a no-types panel; the router sketch builds on that.
- Material injection is disallowed by design. The cooperative manager selects and
  words the question and the material, may insert preferences, and is responsible
  for the answers.
- After the MVP, the auditor may become a real human. Think of Stewart as a
  problem router, not an agent harness.
- Testing whether read-only investigation is enough is a research project.
  Neutrality needs restating.
- Provider-side reasoning and compaction are not Stewart's concern. The submission
  tool must make compaction harmless (“what am I working with again”).
- Usefulness can only be learned if Stewart is fast. “Fast” means the app: the
  manager interface and submission tool respond quickly and instill confidence.
  Audit time and effort are the manager's business.
- Develop toward and deploy in containers, with build dependencies the
  coordinator selects; an experimental apparatus that doesn't ship; a small fast
  Rust app that does.
- The manager side needs design.
- A real-model conformance gate is wanted (“EXCELLENT”); END-TO-END.md designs it.

**What has not changed.** CONTRACTS, CLAUDE.md/AGENTS.md, DEVELOPMENT-PLAN,
VISION-PLAN and all product code are unchanged by the conversation. The user has
not yet adopted the router into CONTRACTS; they said they would review the folder.
Much of the router's detail is the coordinator's proposal, not user direction;
`linux-mvp-01/RESERVATIONS.md` separates the two for the first draft.

**State.** No worker, workflow, background command or Claude launch is active or
pending, and none ran this tenure. No container was started this tenure. Nothing
has been pushed: `origin/main` is at `3442f84`.

## Paused: first-leg preparation

The earlier first-leg preparation is paused, not retired, until the user decides
on the router: [PLAN-FIT](custody-delivery-01/PLAN-FIT.md) (now marked paused),
[NEXT-LEG](submission-design-01/NEXT-LEG.md),
[AUDITOR-CASES](custody-delivery-01/AUDITOR-CASES.md),
[ORIENTATION-TRIAL](custody-delivery-01/ORIENTATION-TRIAL.md) and
[ANSWER-STRUCTURE](custody-delivery-01/ANSWER-STRUCTURE.md). Much of their content
(signs, re-entry, answer structure, the auditor-case table) carries into the
router. Their open questions on access routes and containment are largely
dissolved by it.

## Next

1. **The user's review** of `linux-mvp-01/`, and whether to adopt the router.
2. **If adopted:** restate the principles in CONTRACTS (a draft of the neutrality
   restatement is in the conversation, turn 12), retire the Python baseline and the
   Git-dependent contracts, and rewrite DEVELOPMENT-PLAN. CLAUDE.md/AGENTS.md
   encode the old design's custody rules and belong to the user; change them only
   at the user's direction.
3. **Design the manager side.** The user named it a gap.
4. **Open questions from the conversation:** resuming a dead run; the person adapter
   and transport; how form opinions get added to the library.
5. **The apparatus:** build, test and experiment container images, with build
   dependencies the coordinator selects.
6. **Model use needs permission.** The real-model conformance gate and any
   experiment calls the model provider. Those are model-consuming sessions and
   need the user's explicit, bounded permission and a budget under the standing
   orders.

## Environment notes

- This harness's command sandbox refuses Apple `container` commands and `ps`/`pgrep`.
  Container service and run commands go through the user's terminal (`!`).
- The Python suite runs outside the sandbox (DEVELOPMENT.md).
- Apple `container` 1.6.1 is installed. The alpine, rust and python images pulled
  by digest for the Linux check remain, and the container services the user
  started may still be running.
- The full Python suite was green in the checkout at the previous tenure's end
  (1140, 1 skipped). `test_runner_withholds_rustc_from_provisioning` can flake
  under load.

## Recovery-critical local evidence

The three original audit outcome commits were not ancestors of main and had no
containing refs when inspected. Local development-evidence refs and exact text
copies protect them. [Corpus retention](successor-inquiry-01/CORPUS-RETENTION.md)
names the refs, hashes and source copies; a main-only clone does not carry them.
Retained runs under `.scratch` are local and untracked, and follow DEVELOPMENT.md's
retention rules. Nothing was pruned this tenure.

## Local records this account owns

Each entry is under `.scratch/`. Where a report owns a run's findings, the run
stays with that report under the retention rules.

| Records | Owner of findings |
| --- | --- |
| `alignment-20261028-01/`, `coordinator-intake-20261028-01/` | This tenure. The alignment notes are copied verbatim into `linux-mvp-01/`. |
| `route-research-01/`, `plan-fit-review-01/`, `answer-structure-check-01/`, `auditor-cases-01/` | PLAN-FIT, ANSWER-STRUCTURE and AUDITOR-CASES (paused first-leg work) |
| `linux-first-light-01/`, `linux-check-01/`, `stale-tests-01/`, `fifo-hygiene-01/` | This account. `linux-check-01/RESULTS.md` holds the Linux findings that DEVELOPMENT-PLAN cites. |
| `opus-intake-01/`, `opus-readiness-01/`, `opus-turnover-run-012/`, `astra-turnover-20261027-01/`, `coordinator-intake-run-012/`, `coordinator-transfer-guidance-01/`, `first-leg-riker-brief-01/` | This account (earlier intakes and turnovers) |
| `custody-shakedown-01/`, `custody-concern-routing-01/`, `interaction-simplifications-01/`, `manager-return-direction-01/`, `manager-collect-discussion-01/`, `manager-collect-authority-01/`, `return-completeness-01/`, `authoring-boundary-01/`, `commission-recall-plan-01/`, `forward-program/` | This account (earlier decision records) |
| `coordinator-intake-20261026-01.json`, `coordinator-intake-recording-01.json`, `coordinator-discussion-20261026-01.json` | This account |
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

Other `.scratch` entries belong to earlier plans and findings, not to this account.
