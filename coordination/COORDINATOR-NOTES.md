# Current coordinator account

Updated 2026-10-28 UTC at the incoming coordinator's intake, the second transfer
that day. This is a working account of observed work, authority received and
remaining questions. [Standing orders](STANDING-ORDERS.md) own operating
instructions; [the directory entry](README.md) identifies intake documents. The
optional [turnover](TURNOVER.md) is supplementary. Reconcile these observations
with actual files, user instructions and available harness state after
interruption.

The account was condensed at the first 2026-10-28 turnover to current state, open
work and the local records it owns. The full earlier narrative, covering every
completed commission since 2026-10-24, is in Git:
`git show 313c4e3:coordination/COORDINATOR-NOTES.md`. Each completed commission's
own RESULT or COMPLETION record owns its findings and evidence.

## Current checkpoint: intake and the mission pitch

**Tenure.** The user directed the transfer in this session's first message:
"You are assuming the coordinator role for now. You should find a turnover brief
in the repo." Intake ran on 2026-10-28 at clean HEAD `05a21d4` (Claude Code,
Fable 5.1; record in `.scratch/coordinator-intake-20261028-02/`). The brief was
consumed and stubbed; Git holds it at `05a21d4`.

**User direction at intake** (quoted in full as turn 17 of
[linux-mvp-01/CONVERSATION.md](linux-mvp-01/CONVERSATION.md); condensed here):

- The coupling library stays provisional. `survey` and `claim-check` were
  proposals developed in the conversation; their concrete presentation does not
  settle their design as instruments of inquiry.
- Stewart remains agnostic about auditors' conclusions; we remain responsible
  for judging the arrangements it offers them.
- Protocol conformance (whether a real auditor can work in the arrangement) is a
  distinct question from that design question.
- Consequential choices about answer forms and stopping rules come to the user.
- The first deliverable is a new mission statement for the successor code,
  pitched in chat with the README left unchanged. Stewart is still a custodian;
  manager and auditor are still cooperative; the point is still to let the
  manager focus on their problem rather than on how to ask a question when asker
  and answerer have different contexts; Git no longer matters.

**Delivered.** The mission pitch, the changes from the README's mission, what is
held provisional and the choices to bring to the user are recorded as the
coordinator's reply in turn 17. It is a proposal; CONTRACTS is unchanged.

**Coordinator's reading of the design** (from ROUTER.md and END-TO-END.md under
the user's direction; the folder's AGENTS file governs attribution):

- A problem is what the manager writes: the question verbatim, selected files,
  an answer form, auditor settings and a destination. Stewart builds an
  arrangement from it, places an auditor in it through an adapter, and returns
  the answer with its record.
- The arrangement is the auditor's whole world: for a model, the protocol tools
  plus the form's slots; for a person, a packet and an agreement.
- One protocol call restores everything an auditor is working with, so provider
  compaction is harmless by construction.
- Records are write-once; Stewart deletes nothing; close is a record.
- Responsiveness is a product requirement for manager commands and protocol
  calls, never for audits.
- One static Linux binary ships; build, test and experiment containers never do.
- Decided by the user in the conversation: the auditor has only Stewart's tools;
  Stewart runs the auditor; Linux only; no Python baseline; no Git; material
  injection is disallowed by design and the manager owns wording and selection;
  the submission tool makes compaction harmless; fast means the app; containers
  for development; a real-model conformance gate.
- Proposed by coordinators, not decided: the coupling mechanism and its two
  starter couplings, slots as tools, mechanical citation checks, the reminder and
  near-limit warning, the access log in the return, never deleting, the home
  layout, the command set and the response budgets' numbers.

**State.** No worker, workflow, background command, container or Claude launch is
active or pending, and none ran this tenure. Nothing has been pushed:
`origin/main` is at `3442f84`.

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

1. **The user's verdict on the mission pitch** and on adopting the router.
2. **If adopted:** restate the principles in CONTRACTS (the neutrality
   restatement drafted in conversation turn 12 and the mission pitched in
   turn 17), retire the Python baseline and the Git-dependent contracts, and
   rewrite DEVELOPMENT-PLAN. CLAUDE.md/AGENTS.md encode the old design's custody
   rules and belong to the user; change them only at the user's direction.
3. **Answer forms and stopping rules.** Bring each consequential choice to the
   user before building: typed slots versus free-form elements, stated versus
   checked stopping rules, shown versus sealed prior, citation checking, and the
   two submission nudges. Turn 17 lists them.
4. **Design the manager side.** The user named it a gap.
5. **Open questions from the conversation:** resuming a dead run; the person
   adapter and transport; how form opinions get added to the library.
6. **The apparatus:** build, test and experiment container images, with build
   dependencies the coordinator selects.
7. **Model use needs permission.** The real-model conformance gate and any
   experiment calls the model provider. Those are model-consuming sessions and
   need the user's explicit, bounded permission and a budget under the standing
   orders.

## Environment notes

Inherited observations from the previous tenure; not re-tested at this intake.

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
| `coordinator-intake-20261028-02/` | This tenure's intake. |
| `alignment-20261028-01/`, `coordinator-intake-20261028-01/` | The design-conversation tenure. The alignment notes are copied verbatim into `linux-mvp-01/`. |
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
