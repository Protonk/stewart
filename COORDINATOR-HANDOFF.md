# Handoff to Stewart's next coordinator

Read [AGENTS.md](AGENTS.md), [CONTRACTS.md](CONTRACTS.md), the active root
`*-PLAN.md` documents and the working tree. AGENTS.md is the development
guidance for every harness; `CLAUDE.md` carries the same text for Claude. This
handoff carries the working relationship and the context needed to resume; it
is written for you, not for the user, and assumes no particular harness or
model. [DEVELOPMENT-PLAN.md](DEVELOPMENT-PLAN.md) owns current program state,
[VISION-PLAN.md](VISION-PLAN.md) the longer-term approach, and CONTRACTS.md
decided behavior with its implementation status. This account begins aging as
you use it. You own what to carry, revise or omit for an unknown next coordinator;
the user deliberately does not supervise or edit that selection. Preserve useful
continuity without seeking a perfect or permanently synchronized account.
Re-examine what you carry rather than copying or regenerating it wholesale.
Earlier versions remain in Git.

## Where this handover leaves you

The user's latest direction is coordinator-led sub-agent dispatch, with little
routine user management. The laptop preference is about ten simultaneous agents
or fewer across the whole fleet, expressed in prose rather than enforced in
code. Lower harness limits and memory pressure govern actual concurrency.
The current harness permits four total, enough for the three prepared inquiry
workers plus the coordinator. This is a current capacity observation, not a
permanent staffing rule.

AGENTS.md now requires saved briefs, progressive disk checkpoints, file-backed
long-command output where supported, and reconciliation before replacing an
unreachable worker. [Coordinator notes](coordination/COORDINATOR-NOTES.md) locate
assignments, attempt outputs, observed state and the next action. Read those
notes after interruption; they are an index, not proof that a worker is alive
or stopped. Keep potentially live writers out of replacement edit paths.
The active plan owns dependencies; the index owns dispatch state; worker files
own findings. Update these during work, not only when writing a final handoff.

The user has now authorized the briefed first inquiry-preparation wave:
answer requirements, operating routes and coverage/transition, with integration
and independent review. Saved briefs and attempt locations are linked from the
coordinator notes; source inputs are pinned to `250d494` and retained in
`.scratch/successor-inquiry-01/inputs-01.json`. Consult the index for actual
handles and inspected checkpoints; do not infer that a prepared brief ran.
Runtime implementation, fresh audits, live harness/network experiments and
custody disposal are not commissioned. Routine staffing and recovery stay
with the coordinator; product choices and later trial scope remain reserved.

The dispatch-practice review completed with no blockers and one integrated
output-ownership correction. Its validation is retained in
`.scratch/coordinator-dispatch/validation-01.json` and `.log`; no induced fault
test was run. This wave puts the saved-progress practice into ordinary use.

Coordinator intake and forward reconciliation, 2026-10-26. The preceding
session ended with a computer fault, without a deliberate final handoff. This
file had accumulated incidental updates. The user believes the last recorded
change, `a1881c0` incorporating Riker's keyhole reply, may also have been the
last substantive exchange. Intake found a clean tree and verified that all
five documents in that change matched their retained validation identities.
Python source still matched `6582df2`. This is reconstruction from the surviving
record and the user's recollection, not a recovered conversation transcript.

The user's concern is the **whole forward timeline**: many changes were decided
but left for later implementation and testing, and coordinators dispatching
many agents need to avoid logistical snags. The current reconciliation puts
that account at the front of [DEVELOPMENT-PLAN.md](DEVELOPMENT-PLAN.md):

- F1–F7 give dependencies from inquiry preparation through evidence, connected
  design decisions, read-only Rust, write operations, close and acceptance.
- W01–W20 account for outstanding decisions, implementation and verification,
  including earlier accepted fixes, the Git guide, helper consumers and legacy
  retirement. A decided contract is not an implemented or dispatched task.
- The nine unrun stage-3 comparisons now have individual dispositions against
  the current scope. Do not launch all nine mechanically or lose their surviving
  questions when dropping obsolete executor/resource mechanisms.
- Three bounded first-wave briefs cover answer requirements, operating routes,
  and coverage/transition. They are prepared, not dispatched. Later workers
  need shared identity/schema/record interfaces and exclusive edit ownership;
  the coordinator integrates root documents and verifies the combined result.
- Corpus access, real-harness control/delivery trials, Linux execution, actual
  WSL evidence and the finite legacy population are explicit dependencies.
  Prepare them early; do not discover them only when close is otherwise ready.

This work changes planning, not product contracts or implementation authority.
No runtime work, live answer trial or fleet was commissioned by the reconciliation.
Its checks are retained in `.scratch/forward-program/validation-01.json` and
`.log`. Continue by making the next bounded inquiry concrete under the plan;
bring consequential obligation changes and a concrete trial commission to the
user, without asking them to manage assignments or Git logistics.

## The design direction behind the sequence

The previous session moved from simplifying the manager's closing flow to
reducing the scope of what Stewart undertakes to preserve. The user wants one
`close` command from any state and accepted `close --graceless-exit`. Actual
run binding, stopping authority and evidence that tool activity ended remain
design debt. A person or an agent may execute the supplied command; rendering
it establishes no controller. Human authorship is a separate accommodation and
never an exception to required access enforcement.

The **keyhole candidate** makes a typed submission the whole deliverable and
declares working state disposable in advance, with retirement after durable
valid submission and safe termination. It is the current inquiry direction,
not an adopted repeal of tree-custody, early-close or removal obligations.
The established question types came from real audits; useful answer structures
need their own empirical evidence. Inventory real returns, compare forms, then
trial fresh authoring and integrated submission/disposal. No live answer trial
has run. The obligation inquiry and three independent reviews are in
[KEYHOLE-OBLIGATIONS-FINDINGS.md](KEYHOLE-OBLIGATIONS-FINDINGS.md).

Riker's [reply](riker/KEYHOLE-COMMITMENTS-REPLY.txt) treats admission-only custody
and complete-attempt custody as coherent alternatives. The prior coordinator
favored testing complete attempts first; neither policy is adopted. An attempt
must mean the entire assembled answer, not just final-call arguments. Setter
success, custody failure, schema rejection and durable admission with a lost
reply need distinct meanings. A rejected attempt never fires the proposed
successful-completion retirement trigger. Preserve the advice's provenance.

The older [return design](RETURN-CUSTODY-DESIGN.md) and
[manager flow](MANAGER-CLOSE-FLOW.md) remain useful comparisons, especially
for failure cases, portable-result contents and helper consumers. They are
not a second commission to build general tree capture or a default legacy
package reader. Their proposed ordinary selected-report availability and
portable original-question context still need decisions.

Keep inherited decisions distinct from the new candidate: no dedicated
successor executor or release/run workflow; deferred general manager-workspace
service; audit-owned facilities and restricted manager access; explicit auditor
grants, with delegated evidence-based fallback judgment; finite attributed
holds with explicit release, provisionally outliving environment retirement;
bounded evidence readers and legacy transition. Shared immutable material is
preferred but its mechanism and last-use policy remain open. No audit restart
is scheduled; at most one convenience remains a product question. Recording
a commission need not promise replay. Stewart still owes supported handling of
its incomplete custody operations, without granting another investigation.

CONTRACTS.md controls these obligations. The forward register owns their
remaining design and acceptance work, including A.1/B–F, R1–R3 and the two
proposed workspace completions. The coordinator owns ordering and ordinary
mechanism choices within authority. Stage 4 remains status first, write path
next, close last; scope the reader before implementation and do not port known
superseded facilities just to obtain parity. Keep the independent witness
outside disposal through review: rescue does not establish product retrieval.

## The Git environment document

`GIT-ENVIRONMENT-NEEDS.md` is drafted and reviewed. Its audience is Stewart's
users: the people who hold material in Git and operate Stewart, today the
manager role. It is not for coordinators, and it is not for the development
user, who is only a proxy for Stewart's users and decides on their behalf;
making it serve Stewart's users is the coordinator's responsibility. Its shape
is fixed: a hand-written narrative, a table that `scripts/git_opinions.py`
generates from the source (never hand-written), and a hand-written guide
giving each class of rows a status.

- **Statuses** describe this version only: relied on, decided to change, may
  change, incidental. Unsupported cases belong in the narrative. A first draft
  that called rows "supported" would have promised behavior the round
  proposes to change; the review caught it.
- **Regenerating**: run `scripts/git_opinions.py --write` with the selected
  explicit interpreter and `-I -B`. It rewrites only the marked region;
  `--check` and `--coverage` verify it in separate invocations.
  `tests/test_git_opinions.py` fails when the table is stale, or when the
  guide cites a row ID or reason identifier that does not exist, so keep
  citations valid when editing the guide.
- **After the user decides the statuses**: add the document to the source
  distribution's include list in `pyproject.toml`, as CONTRACTS.md was, with
  the wheel digest unchanged, and link it from the root README. The bundled
  manual is frozen Python source, so it is not edited.
- **Routing and the generator**: the document must not route users to plans,
  findings or development tooling. The static generator serves only the
  Python baseline; the account recommends observing Git calls through the
  test suite's Git wrapper for the successor's table.

## Preserve the product relationship and delegation boundary

The user wants Stewart to answer an occasional inquiry about an unclosed audit;
checking status is not the manager's routine job. The idiom is a handed-over
audit as a promise of an eventual structured reply. Status is a concession so
persistent managers do not invent their own inspections, and it infers no
activity, completion, publication or delivery. Stewart abstracts the
manager/auditor connection as far as practicable; the ideal accommodates a
human auditor; entry points stay open (a manager launching and arranging its
callback, a human ferrying a command, a harness pausing for approval before the
same manager resumes). Human involvement does not transfer the role or callback
responsibility. A callback arrangement does not authorize recurring live
inspection or steering. In frozen Python, nothing the auditor does reaches
Stewart before collection; delivery is deferred with its dependency named (a receiving endpoint and
real-harness evidence), not placed outside Stewart. That baseline is why the
round recommends a read-only history view over a recorded query interface,
which would be the first pre-collection auditor channel. The user offers
fallible help when these relationships confuse. The product relationship is
a positive choice for narrow questions and answers, not a feature-parity
target for a harness-managed swarm. The development fleet's practices do not
become product requirements. Preserve the effectiveness/seamlessness tension:
rich manager-selected context may aid investigation, while a constrained,
static, nonrecursive slice makes custody promises easier. Neither breadth nor
isolation is automatically the better outcome.

The delegation boundary is about commitments, not presentation. Apply the two
tests to any contract, wording or offered action: what might a participant
reasonably rely on it as permission, instruction or assurance to do or omit;
and does that reliance follow from agreed commitments or establish an
undecided one. "No return is recorded," "work is proceeding normally" and "no
manager action is required" make different commitments. Inside a granted
commission, do not seek approval for ordinary choices; when a consequential
crossing is real, state it and finish the independent work.

Decided principles govern new proposals (CONTRACTS.md): Stewart acts only on
what was judged; refusals rest on a false custody claim, an impermissible act
or an undischarged obligation, never on discomfort with incomplete evidence;
close offers a working opportunity to keep material, not preservation; the
manager controls what survives by default, but requesting close does not
cancel undertaken obligations and completed close cannot hide unfinished work;
liberal in handing over, conservative in destroying. The user rejected
mandatory retention before close as invasive to
the manager's flow, and holds that most conditions under which Stewart could
withhold a report trace to how the manager built the audit, which is the
manager's to judge. "The user" in development guidance is the development
principal; Stewart's users are the people who operate it, and documents for
them must serve them.

## Carry the investigative and coordinating judgment

For commissioned fleet work, the user expects useful delegated assignments
and actual integration, not generic staffing labels. That history does not
commission workers during a semantic discussion or guidance review. Follow the
available harness's delegation rules; no fixed staffing or provider split is
required. Give workers clear edit ownership, compact returns and complete
assignments, and verify the combined result before review. Earlier independent
reviews found consequential errors; stage 4's inquiry review returned 32 findings,
three blocking, since resolved. Run worker tests through `scripts/check.py`
yourself: a stand-in harness once passed tests that the real checker refused
because pytest treated a module-level `setup` helper as a hook.

The user delegates noticing questions an assignment did not ask. Challenge
consequential premises; a passing test does not settle a product judgment.
Choose a source investigation, controlled comparison, regression test or
semantic discussion according to the question, and distinguish settings
construction from real harness enforcement, reported claims from observations,
plans from executed operations, and code consistency from scientific
conclusions. Lessons that held:

- Name every rule's exit; a review once caught a rule that would have retained
  sessions forever by silence.
- Expect a comparison to contradict a source reading usefully.
- When a recommendation retires or defers something recently decided,
  enumerate every decided item it reopens.
- A new refusal or a changed capture comparison is a decision, not a
  correction, even when it applies a principle.

Neither more nor fewer tests is an objective.

Shared documents make purposes, evidence, decisions and remaining choices
intelligible and recoverable from the repository, not memory; the user works
at that level. The coordinator owns assignment design, edit ownership,
ordinary disagreements, integration, verification and all version-control
logistics (AGENTS.md); the user discusses actions effected and retains
purpose, scope and protected obligations. Current behavior is evidence to
examine, not proof it is desirable. Archived plans are not a dormant task
queue. Findings documents distinguish corrections that apply decided rules,
proposed completions awaiting decision, and open leads; preserve that and the
captured historical documents.

## Working tree and evidence

The inherited seven-file tree was committed unchanged on `main` as `8fd864f`,
after the earlier `a8de387`. Normal staging and committing worked in this
session. The earlier coordinators' `Operation not permitted` failures remain
historical records in `.scratch/resource-decisions/commit-attempt-01.json`
and `.scratch/close-direction/commit-attempt-01.json`, with their logs; they
are not a current prohibition. Keep normal coordinator ownership of Git
logistics and inspect the actual state when resuming. No push was made for
the inherited-tree commit.

That commit's validation is `.scratch/commit-working-tree/validation-01.json`
and its log: all seven files matched their retained checks, and fresh
whitespace, frozen-source, unchanged-implementation and generated Git-table
checks passed. The subsequent design account adds MANAGER-CLOSE-FLOW.md and
RETURN-CUSTODY-DESIGN.md and updates this handoff and DEVELOPMENT-PLAN.md.
Its source review and documentation validation live in
`.scratch/return-custody-design/`, cited by the plan and design account.

The preceding documentation validation culminates in
`resource-decisions/validation-15.json` and its log. The single-close direction's
checks are in `close-direction/validation-01.json` and `validation-02.json`
with their logs, the latter covering the close-direction account before the
planning revision. These checks selected
zero pytest nodes and ran zero behavioral comparisons; they include the frozen
source and generated Git table.

The inherited handoff is checked in `.scratch/coordinator-turnover/validation-01.json`
and its log: zero pytest nodes selected and zero behavioral comparisons run.
The check verifies the frozen source and that the other documents still match
the completed planning revision; it establishes no repaired Git write access.
Run records live under `.scratch/`, untracked and only on this machine:

- Stages 1 and 2: `status-inquiry/` and `custody-audit/`, as their findings
  describe, including the later-return comparison's three receipts and seventy
  evidence copies (artifacts pruned after review).
- The distribution check after CONTRACTS.md joined the source distribution:
  `contracts-link/distribution-01`.
- Stage 3: four working accounts in `custody-additions/`.
- The resumed resource discussion's documentation checks: `resource-decisions/`,
  cited by the development plan. No new behavioral comparisons are claimed.
- The single-close direction's documentation checks: `close-direction/`, cited
  by the development plan. No runtime or harness qualification is claimed.
- The advice-based planning revision: `return-planning/validation-01.json` and
  its log, with starting documents under `before/`. No pytest nodes selected
  and no behavioral comparisons run; no new contract adoption is claimed.
- Stage 4's round, in `custodial-core/`:
  - working accounts: `operations.md`, `workspace.md`, `comparisons.md`,
    `history-view.md`, `git-opinions.md`;
  - the review: `review.md`;
  - receipts: `comparisons-01` to `-04` and `git-opinions-01` to `-05`;
  - the probe's script, outputs and fixture runs under `history-view/`.

  The inherited handoff reports every comparison node's artifacts kept. This
  coordinator did not rerun or prune them. Check their recorded state and prune
  only with `scripts/prune.py` once their purpose is served; records stay with
  the findings.

Findings documents and their run records stay until Rust acceptance evidence
supersedes them. `tests/test_custodial_core_inquiry.py` and
`tests/test_git_opinions.py` are tracked.

The checker runs directly under the base interpreter, with the provisioned
wheelhouse, for example
`/opt/homebrew/opt/python@3.14/bin/python3.14 -I -B scripts/check.py --wheelhouse <project>/.scratch/wheelhouse --result <absolute>.json <selectors>`.
Use a fresh result name per run and `--keep-node` for evidence.
Installed-wheel runs used Apple Git 2.54.0 and one production wheel digest,
`43da134c…`; Python was 3.14.8 through stage 3 and 3.14.9 from stage 4, after
a Homebrew update. DEVELOPMENT.md records that a shell sandbox refusing
`.gitconfig` writes stops the suite at fixture setup and blocks pruning. Run
both outside such a sandbox, or permit those operations.

## Consultation and engagement records

Riker is a separately situated helper, not a superior authority. Requests and
replies are user-relayed under [riker/RIKER.md](riker/RIKER.md). Three exchanges
are retained: status delegation, which sharpened the commitments boundary;
close commitments, which informed the principle revisions and the
retention-undertaking rule; and keyhole commitments, which distinguished
admission-only custody from preserving complete attempted answers. Consultation is
optional, at the coordinator's or user's discretion, with no prescribed place
in the sequence; repository claims still need evidence.

The user explicitly delegates judgment over how to internalize outside advice,
including when to ask Riker. Advice forwarded by the user is not thereby the
user's guidance. Revise plans using your assessment and preserve provenance;
bring consequential changes to protected obligations back for decision. Do not
make consultation a routine approval gate or ask the user to adjudicate every
suggestion before doing the planning work.

Follow any engagement-specific recording instructions separately from ordinary
project materials; do not assume authority to explore other runs or restricted
neighboring projects. This file remains ordinary Stewart coordination guidance.
