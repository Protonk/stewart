# Handoff to Stewart's next coordinator

Read [AGENTS.md](AGENTS.md), [CONTRACTS.md](CONTRACTS.md), the active root
`*-PLAN.md` documents and the working tree. AGENTS.md is the development
guidance for every harness; `CLAUDE.md` carries the same text for Claude. This
handoff carries the working relationship and the context needed to resume; it
is written for you, not for the user, and assumes no particular harness or
model. [DEVELOPMENT-PLAN.md](DEVELOPMENT-PLAN.md) owns current program state,
[VISION-PLAN.md](VISION-PLAN.md) the longer-term approach, and CONTRACTS.md
decided behavior with its implementation status. Replace this handover context
when passing the role onward; re-examine what you carry rather than copying or
regenerating it. Earlier versions remain in Git.

## Where this handover leaves you

The five-stage sequence remains: status inquiry, audit of existing custody,
consideration of additions, Rust transition, and optional implementation of the
revised arrangement. Stages 1, 2 and 3 are closed and decided; their contracts,
principles, declines and deferrals are in CONTRACTS.md, and their findings
documents stay for their anchors. **Click integration was dropped**, not
deferred. **Python is frozen as the reference baseline**: production source
under `src/stewart/`, including the bundled manual, is unchanged since
`6582df2`, and every decided departure is implemented in Rust, status first
(read-only against Python-written sessions, with Python status as the control)
and close last. Rust acceptance includes executed Linux and WSL qualification;
the user plans to ask a friend to run the WSL checks. Do not substitute a
recipe or Linux results for executed WSL evidence. Stage 3's proposed second
wave of nine baseline comparisons was not run; several presuppose linked
worktrees, so they wait for the workspace decision below.

**Stage 4 opened with a decision round** on two external proposals the user
relayed, preserved verbatim at `planning/inputs/custodial-core.md` and
`planning/inputs/history-only.md`. The plan's stage-4 section owns the round's
state. Its account for decision is
[CUSTODIAL-CORE-FINDINGS.md](CUSTODIAL-CORE-FINDINGS.md), independently
reviewed and corrected. Nothing is in flight. A separate agent is briefing the
user on the round; do not repeat that briefing unless asked. The round awaits
the user on:

- decisions A to F: the admission rule, the workspace representation, the
  capture trigger, commission fields, where custody lives, and the form of the
  history facility;
- the two proposed completions under B: refusing a tree the destination
  cannot represent, and one name normalization in capture;
- two leads: a concluded close over a failed preparation, and the recorded
  pause;
- the statuses in `GIT-ENVIRONMENT-NEEDS.md`'s guide;
- whether Rust status starts alongside. It does not depend on the decisions
  but has not been started. The Rust write path waits for A to F.

When decisions arrive, record each in CONTRACTS.md with its status marker and
reasons, as stages 2 and 3 did, and update the plan's stage-4 section. The
account's A.3 lists every decided item that deferring the manager-side
resource lifecycle would reopen: a principle sentence, the hold contract
decided on 2026-10-24, a decline's reason, status and close rows, and the
custody rule on removal. Change each explicitly if the user takes that
course. Then finish the Git environment document (below), dispose of the
round's artifacts under DEVELOPMENT.md's rules, retire the findings document
when its decisions are recorded and its anchors no longer needed, and prepare
the write path's commission. The history-only and files-only profiles need no
separate build if B and F are decided as recommended; they are grants in one
workspace and history design.

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
- **Regenerating**: `python3.14 -I -B scripts/git_opinions.py --write`
  rewrites only the marked region; `--check` and `--coverage` verify it.
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
responsibility. Nothing the auditor does reaches Stewart before collection;
delivery is deferred with its dependency named (a receiving endpoint and
real-harness evidence), not placed outside Stewart. That premise is why the
round recommends a read-only history view over a recorded query interface,
which would be the first pre-collection auditor channel. The user offers
fallible help when these relationships confuse.

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
manager controls what survives by default while obligations Stewart has
undertaken survive its close; liberal in handing over, conservative in
destroying. The user rejected mandatory retention before close as invasive to
the manager's flow, and holds that most conditions under which Stewart could
withhold a report trace to how the manager built the audit, which is the
manager's to judge. "The user" in development guidance is the development
principal; Stewart's users are the people who operate it, and documents for
them must serve them.

## Carry the investigative and coordinating judgment

The user expects actual use of delegated workers and objected to coordination
that would use none. For this round they asked for limited dispatch with
specific tasks and relationships, not generic implementer, checker and fixer
roles. Use your harness's own delegation and workspace facilities; no fixed
staffing, provider split or orchestration framework is required, and
development workers do not inherit Stewart's manager/auditor workflow. Past
staffing: two and three source researchers with a fresh reviewer each
(stages 1 and 2), one comparison worker and two reviewers (stage-2 decisions),
four source investigators and a reviewer (stage 3), and for stage 4's round
two source investigators, a generator author, a comparison worker, a Git-only
probe and one reviewer. Every review found corrections worth making; this
round's found 32, three blocking. Give each worker exclusive edit ownership,
keep returns compact, have workers write full accounts to working files, and
verify the combined result yourself before review. Run a worker's tests
through `scripts/check.py` yourself: a worker's stand-in harness passed tests
the real checker refused, because pytest called a module-level helper named
`setup` as a hook.

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

Commits are on `main` and pushed to `origin`, which needs network access to
github.com; `git log` from `6582df2` is the engagement's record and each
message states its validation. Run records live under `.scratch/`, untracked
and only on this machine:

- Stages 1 and 2: `status-inquiry/` and `custody-audit/`, as their findings
  describe, including the later-return comparison's three receipts and seventy
  evidence copies (artifacts pruned after review).
- The distribution check after CONTRACTS.md joined the source distribution:
  `contracts-link/distribution-01`.
- Stage 3: four working accounts in `custody-additions/`.
- Stage 4's round, in `custodial-core/`:
  - working accounts: `operations.md`, `workspace.md`, `comparisons.md`,
    `history-view.md`, `git-opinions.md`;
  - the review: `review.md`;
  - receipts: `comparisons-01` to `-04` and `git-opinions-01` to `-05`;
  - the probe's script, outputs and fixture runs under `history-view/`.

  Every comparison node's artifacts are kept and none is pruned yet. Prune them
  with `scripts/prune.py` once the decisions are recorded; the records stay
  with the findings.

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

This engagement had no fieldwork recording assignment. If yours carries its
own recording instructions, follow those; do not assume authority to explore
other runs or restricted neighboring projects. This file is the ordinary
Stewart handoff.
