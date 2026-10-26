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

The 2026-10-25 handoff was followed by a session that successfully committed
the inherited tree as `8fd864f`. The user then agreed to work through the
return/close interaction, inventory portable-result contents and prepare
bounded decisions and a first reader assignment. They specifically requested
a very spare, human-readable closing flow. Start discussion from
[MANAGER-CLOSE-FLOW.md](MANAGER-CLOSE-FLOW.md), the proposed manager task flow;
[RETURN-CUSTODY-DESIGN.md](RETURN-CUSTODY-DESIGN.md) carries the supporting
cases, source inventory, authority boundaries and pending reader assignment.

The first decision is how `close` carries outstanding gap, follow-up,
preservation, surrender and hold-release decisions without separate lifecycle
commands or weakened authority. The other proposed completions are ordinary
selected-report availability with surrounding damage and original-question
context in new portable results. None has been adopted. Publication, stopping
and delivery still need an actual admitted route and qualification; the
candidate snapshot mechanism is a design requirement, not enforcement evidence.
No runtime implementation, Rust code, new behavioral comparison, harness
qualification or worker dispatch occurred. CONTRACTS.md remains unchanged by
this design session. The larger open architecture questions below remain.

The most consequential new user direction is **one `close` command that closes
the audit regardless of state**. The user's words were "My STRONG inclination
is to offer a close command and that's it." Any withdrawal path for closing an
active investigation belongs inside that operation. The user authorized
recording this as the successor design direction. The manager should not need
to diagnose a stage and choose a separate withdrawal, abandonment or closure
procedure. Existing holds and preservation undertakings still constrain
completion; exact stopping, capture, dispositions and continuation remain for
design. Bring back concrete conflicts with protected obligations while taking
the one-command target seriously. CONTRACTS.md owns the direction. It is not
permission to report completed close while unfinished obligations remain.

One intake correction matters: I framed human auditors as a potential exception
to enforced access. The user correctly challenged that distinction. A human
can receive restricted repository data just as an agent can. Assess the actual
access/publication arrangement and its tools, not whether the auditor is human.
No admission exception for unenforced access was adopted. Do not reopen that
mistaken framing as an unresolved user question.

The user also delegated judgment over how to internalize outside advice,
including when to consult Riker. They authorized the planning revision, not
blanket adoption of the advice. The revision makes return acquisition,
availability/delivery and identified-operation recovery the next design
priority, with no audit restart scheduled for the first successor. Stable
publication is the leading ordinary-capture candidate; the recipient of a
portable exported result is the first evidence-reader consumer to specify.
These are this coordinator's planning judgments. You may revise them with
reasons and evidence; do not mistake them for new decided contracts.

The inherited **no dedicated successor program executor** decision (A.2,
arrangement 1) is settled. Stewart supplies selected material, captures the
auditor's return and maintains custody; permitted auditor tool use remains
bounded by its commission and enforced grants. Captured execution reports
remain attributed claims, without a Stewart process witness or invocation
guarantee. Do not port or externally recreate the manager-operated
construction/review/release/run workflow, child launcher, dedicated attempt
HOME or output-reset/re-release facilities. The reviewed project-command shim
is superseded. CONTRACTS.md records the dispositions; the other arrangements
in CUSTODIAL-CORE-FINDINGS.md are comparisons, not optional feature plans.

The five-stage program remains: status inquiry, custody audit, additions, Rust
transition, and optional implementation of the revised arrangement. Stages 1–3
closed, with stage-4 departures governing current scope. **Click integration
was dropped. Python remains frozen** against `6582df2`, including bundled
manuals and role files. Begin from the actual working tree and recorded
decisions. This handoff commissions no automatic port or implementation.

The resource discussion also established these directions:

- Defer general manager-workspace creation/disposal, leaning toward isolating
  and removing it rather than promising a later port. Audit-owned allocation
  and required custody, access and shared-use protections remain.
- Restrict manager access after handoff; preserve the bounded commission and
  structured return. Manager workspaces have independent lifetimes.
- Strongly prefer shared immutable material. Its last-use/cache policy remains
  open; sharing must not expose unselected material or merge collection identities.
- Provisionally allow the working environment to retire while the same audit
  holds identified captures. Final custody close waits for explicit release
  and its other conditions. A hold permits neither continued investigation nor
  dangling operations after completed close.
- Hold a finite identified selection, with attribution and metadata/captured
  dependencies needed for its custody claims. References do not enlarge it
  recursively; copying does not silently release the original hold. Exact
  identity and transfer representation remains design work.
- Pursue explicit access grants, preferably eliminating the private-location
  inventory. The user delegates judgment over an evidence-justified fallback.
  Actual harness qualification must cover manager and auditor boundaries.
- Use bounded legacy retirement over a specified population; none has yet been
  inventoried. Protect supported evidence interpretation across writers, with
  named consumers, records and claims. A historical release, runtime or resource
  record does not require the successor to continue its old operational role.

The manager owns constructing another question, including an identical one.
Recording the remit need not promise replay; this is an agreed direction and
candidate core commitment. The preference is zero audit retry facilities, with
at most one restart-from-start convenience still open. Intellectual dissatisfaction
with an audit answer and the decision to ask again are outside Stewart's remit.
Do not describe them as a Stewart failure or recovery task.

**Incomplete Stewart operations remain its responsibility.** This matters
especially for agent-managers, whom an inadequate interface can lead to repair
private state, erase evidence or guess whether work happened. A diagnostic alone
is not a supported resolution. Capture, publication, lost replies and interrupted
close need usable completion/disposition paths within recorded authority, with
honest gaps where evidence is lost. Recovery cannot grant another investigation
or replay uncertainty; renaming several retry facilities does not simplify them.
The plan's failure cases remain design/qualification work, not executed results.

Live testing must be able to detect missed extraction and silent destruction
or withholding. The current recommendation is an independent immutable test
archive outside the disposal under test, retained through review even for passing
runs. Its observer scope and timing must be explicit; copying only Stewart's
capture cannot reveal what capture omitted. Archive rescue is not successful
product retrieval, and a hold must not prevent the close being tested. This
is not an implemented archive, a production cache or a post-close recovery promise.

## Take up the remaining work

Continue the design conversation before commissioning implementation. The
stage-4 round came from `planning/inputs/custodial-core.md` and
`planning/inputs/history-only.md`, preserved verbatim. The initial inquiry was
independently reviewed; the subsequent conversation changed several recommendations.
DEVELOPMENT-PLAN.md and CUSTODIAL-CORE-FINDINGS.md own the current account.

The user subsequently supplied peripheral advice on return acquisition,
recovery, availability, workspace form and a portable-result reader, then
delegated its assessment and incorporation into the plans to the coordinator.
It is preserved in `planning/inputs/return-and-custody-advice.txt`; its relative
links were not followed and must not be treated as local sources to resolve.
The resulting planning revision makes the connected return/custody design
account the next priority. Develop stable, identified publication as the
leading ordinary-acquisition candidate, with explicit early-close and partial
paths; distinguish availability from delivery, and give interrupted operations
usable completion/disposition through their existing identity. Schedule no
audit restart for the first successor. These are coordinator recommendations
and ordering choices, not newly accepted contracts or an implementation
commission. The development plan contains the concrete work products and
discriminating cases. Re-examine the recommendations as you use them rather than
mechanically repeating the advice or treating it as another task queue.

The first walkthrough now covers ordinary publication and delivery, close
before publication, interrupted acquisition, a lost reply and interrupted
removal. The new design account makes those interactions reviewable; it does
not settle a concrete harness protocol. Discuss its bounded decisions, then
select an actual publication/stopping/delivery arrangement to qualify. You
own the order and method. The details most likely to be lost in a short recap
are:

- "Publication" here fixes the auditor's return for acquisition; later
  retention/export to a manager destination is a different operation. A digest
  or completion declaration does not freeze a working directory. A complete
  publication may report incomplete investigation; incomplete acquisition and
  unfinished closure are separate facts. Stable return bytes alone do not
  establish stopped activity or removal authority.
- An operation identity only returned in the lost reply does not solve that
  failure. The manager needs a reference already held or supported unambiguous
  discovery. Continuing the undertaking must not adopt unrelated outputs or
  relabel a new observation of changed material as the old capture.
- A readable answer is not delivered merely by existing. Specify the receiving
  endpoint and callback/resumption responsibility without making routine
  polling or an accepted-answer acknowledgment the manager's job. Extending
  selected-report access with surrounding damage from export to the ordinary
  reader remains a proposed contract change.
- The portable reader needs finite supporting bytes and identities, not just
  a commit ID naming an absent question. Existing packages need an actual
  inventory before their supported view is promised. A portable snapshot does
  not establish later hold release or operation completion. Keep current
  custody status and transition diagnosis separately scoped, and retain the
  status-first Rust implementation sequence.

The remaining decisions and unfinished assignments are:

- **A.1 and B–F remain open:** formal admission rule, workspace representation,
  capture trigger, commission fields, custody location and history facility.
  No executor does not itself adopt the exact-three-responsibilities formula.
  Two proposed completions under B concern unrepresentable trees and name
  normalization; two leads concern concluded close over failed preparation and
  recorded writer pause. The Git guide's remaining statuses also need decision.
- **The remaining guidance questions are substantive.** R2's closing entry
  point now has the single-command direction above; exact stop/capture and
  closure dispositions, other exceptional intervention and delivery remain
  open. Old harness-message examples are not a successor protocol.
  R3 concerns D's proposed commission retention promise:
  the accepted voluntary hold defeats the old equation with mandatory retention.
  Identify what the promise adds beyond a hold and completed publication.
- **The inherited helper-runtime assignment is partly advanced:** the source
  and manual name inspection and separately authorized fresh reuse as its two
  consumers; RETURN-CUSTODY-DESIGN.md maps them to captured-asset reading and
  explicit export. Qualification of the fresh-reuse route and an inventory
  of existing Python recoveries remain undone. Removal is not yet decided.
  Helper assets are
  distinct from the program executor just removed. Existing Python recovery
  material needs an explicit
  transition disposition. R1's dedicated experiment HOME/retry portions no longer
  need a successor interface; do not revive them to settle the helper question.
- The first evidence-reader consumer to specify is now the recipient of an
  exported result whose original environment and writer are gone. Bound its
  schemas, material and supported claims before proposing Rust status work;
  current-operation status and transition diagnosis still have separate needs.
  Historical attempt/ledger interpretation needs a justified scope and does not
  preserve executor APIs. The Python corpus supplies comparison evidence, not
  a blanket compatibility promise. Rust remains status first, close last; the
  write path waits for the remaining architecture decisions.

Keep the seven resource directions settled while designing their mechanisms.
Hold identities/transfer, shared-store lifetime, actual access enforcement and
supported custody recovery still need qualification. Rust acceptance requires
executed Linux and WSL evidence as well as the macOS baseline; the user plans
to ask a friend to run WSL. A recipe or Linux result cannot substitute for that
run. Reassess stage 3's unrun nine comparisons against selected scope before
commissioning any; neither linked worktrees nor executor parity is assumed.

Record decisions in CONTRACTS.md and update current plans. Finish the Git
publication work below after its remaining statuses are settled. Keep findings
and run records until their evidence is superseded; prune artifacts only under
DEVELOPMENT.md. No implementation commission is hidden in this handoff.

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
replies are user-relayed under [riker/RIKER.md](riker/RIKER.md). Two exchanges
are retained: the status-delegation exchange, which sharpened the commitments
boundary, and the close-commitments exchange, whose reply produced the final
principle revisions and the retention-undertaking rule. Consultation is
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
