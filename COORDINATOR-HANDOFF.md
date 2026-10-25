# Handoff to Stewart's next coordinator

Read [AGENTS.md](AGENTS.md), [CONTRACTS.md](CONTRACTS.md), the active root
`*-PLAN.md` documents and the working tree. This handoff carries the working
relationship and the context needed to resume; it is written for you, not for
the user. [DEVELOPMENT-PLAN.md](DEVELOPMENT-PLAN.md) owns current program
state, [VISION-PLAN.md](VISION-PLAN.md) the longer-term approach, and
CONTRACTS.md decided behavior with its implementation status. Replace this
handover context when passing the role onward; re-examine what you carry
rather than copying or regenerating it. Earlier versions remain in Git.

## Where this handover leaves you

The five-stage sequence remains: status inquiry, audit of existing custody,
consideration of additions, Rust transition, and optional implementation of the
revised arrangement. Stages 1, 2 and 3 are closed and decided; their contracts,
principles, declines and deferrals are in CONTRACTS.md. **Click integration was dropped**,
not deferred. **Python is frozen as the reference baseline**: production source
is unchanged since `6582df2`, every decided departure is implemented in Rust,
status first (read-only against Python-written sessions, with Python status as
the control) and close last. Rust acceptance includes executed Linux and WSL
qualification; the user plans to ask a friend to run WSL checks. Do not
substitute a recipe or Linux results for executed WSL evidence.

Stage 3 is decided. The user agreed to
[CUSTODY-ADDITIONS-FINDINGS.md](CUSTODY-ADDITIONS-FINDINGS.md) as recommended
after independent review; CONTRACTS.md carries its acceptances, declines and
deferrals, and the findings document stays for its anchors. Its second wave of
nine baseline comparisons, needing no harness, network or human, was not run
before the decision; the record marks as predictions the facts they would
establish, and they are available as verification at implementation.

**Stage 4 opened with a decision round** on two external proposals the user
relayed (`planning/inputs/custodial-core.md`, `history-only.md`). The plan's
stage-4 section owns its state. The round's account is
`CUSTODIAL-CORE-FINDINGS.md`: six decisions A to F with recommendations, two
proposed completions and two leads, independently reviewed and corrected.
It awaits the user's decisions, which go to CONTRACTS.md; the Rust write path
waits for them. Rust status does not depend on them but has not been started:
the user has not answered whether it starts alongside. Deferring the
manager-side resource lifecycle would reopen a hold contract decided the day
before. The review caught that the first draft did not say so; when a
recommendation retires something recently decided, enumerate it.

## The Git environment document

`GIT-ENVIRONMENT-NEEDS.md` exists, drafted and reviewed in the same round.
Its audience is Stewart's users: the people who hold material in Git and
operate Stewart, today the manager role. It is not for coordinators, and it is
not for the development user, who is only a proxy for Stewart's users and
decides on their behalf; making it serve Stewart's users is the coordinator's
responsibility. Its shape is fixed: hand-written narrative, a table that
`scripts/git_opinions.py` generates from the source (never hand-written), and a
hand-written guide giving each class of rows a status. The statuses describe
this version only (relied on, decided to change, may change, incidental), with
unsupported cases in the narrative; a first draft that called rows
"supported" would have promised behavior the round proposes to change. The
statuses are the user's decisions. After that decision the document still
needs shipping in the source distribution and a link from where users look.
It must not route users to plans, findings or development tooling. The static
generator serves only the Python baseline; the account recommends observing
Git calls through the test suite's Git wrapper for the successor's table.

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
responsibility. The first wave established from source that nothing the
auditor does reaches Stewart before collection; delivery is deferred with its
dependency named (a receiving endpoint and real-harness evidence), not placed
outside Stewart. The user offers fallible help when these relationships confuse.

The delegation boundary is about commitments, not presentation. Apply the two
tests to any contract, wording or offered action: what might a participant
reasonably rely on it as permission, instruction or assurance to do or omit;
and does that reliance follow from agreed commitments or establish an
undecided one. "No return is recorded," "work is proceeding normally" and "no
manager action is required" make different commitments. Inside a granted
commission, do not seek approval for ordinary choices; when a consequential
crossing is real, state it and finish the independent work.

Decided principles now govern new proposals (CONTRACTS.md): Stewart acts only
on what was judged; refusals rest on a false custody claim, an impermissible
act or an undischarged obligation, never on discomfort with incomplete
evidence; close offers a working opportunity to keep material, not
preservation; the manager controls what survives by default while obligations
Stewart has undertaken survive its close; liberal in handing over, conservative
in destroying. The user rejected mandatory retention before close as invasive
to the manager's flow, and holds that most conditions under which Stewart could
withhold a report trace to how the manager built the audit, which is the
manager's to judge.

## Carry the investigative and coordinating judgment

The user expects actual use of sub-agents and objected to coordination that
would use none. The stage-1 and stage-2 engagement used two and three source
researchers with a fresh independent reviewer each; the decision engagement
used one comparison worker and two reviewers; stage 3's first wave used four
source investigators and a reviewer over the integration; stage 4's decision
round used two source investigators, a generator author, a comparison worker,
a Git-only probe and one reviewer. Every review found corrections worth
making. The user asked for limited dispatch with specific tasks and
relationships, not generic implementer, checker and fixer roles. Use the harness's facilities; no fixed staffing,
provider split or orchestration framework is required, and development workers
do not inherit Stewart's manager/auditor workflow. Keep worker returns compact,
have them write full accounts to working files, and verify the combined result
yourself before review. Run a worker's tests through `scripts/check.py`
yourself: a worker's stand-in harness passed tests the real checker refused,
because pytest called a module-level helper named `setup` as a hook.

The user delegates noticing questions an assignment did not ask. Challenge
consequential premises; a passing test does not settle a product judgment.
Choose a source investigation, controlled comparison, regression test or
semantic discussion according to the question, and distinguish settings
construction from real harness enforcement, reported claims from observations,
and code consistency from scientific conclusions. Two lessons from this
engagement: name every rule's exit, because the independent review caught a
rule that would have retained sessions forever by silence; and expect a
comparison to contradict a source reading in a useful way, as the later-return
comparison did. Neither more nor fewer tests is an objective.

Shared documents make purposes, evidence, decisions and remaining choices
intelligible and recoverable from the repository, not memory; the user works
at that level. The coordinator owns assignment design, edit ownership,
ordinary disagreements, integration, verification and all version-control
logistics (AGENTS.md); the user discusses actions effected and retains
purpose, scope and protected obligations. Current behavior is evidence to
examine, not proof it is desirable. Archived plans are not a dormant task
queue. Findings documents distinguish accepted-but-unimplemented corrections
from open leads; preserve that and the captured historical documents.

## Working tree and evidence

Commits are on `main` and pushed; `git log` from `6582df2` is the engagement's
record and each message states its validation. Stage-1 and stage-2 evidence is
as their findings describe, with run records under `.scratch/status-inquiry/`
and `.scratch/custody-audit/`; the later-return comparison's three receipts and
seventy evidence copies are there too, artifacts pruned after review, with
`tests/test_custody_later_return_inquiry.py` tracked. The distribution test was
rerun after CONTRACTS.md joined the source distribution
(`.scratch/contracts-link/distribution-01`, ten passed, wheel digest
unchanged). Stage 3's four working accounts are untracked under
`.scratch/custody-additions/` (about 2,200 lines with anchors); the findings
document carries what a decision needs, and the accounts exist only on this
machine. Stage 4's decision round keeps its untracked working accounts,
review and run records under `.scratch/custodial-core/`
(`comparisons-01` to `-04`, `git-opinions-01` to `-05`, the probe's
`history-view/` runs), with every comparison node's artifacts kept and none
pruned yet. Findings documents and their run records stay until Rust
acceptance evidence supersedes them. Every installed-wheel run used Apple Git
2.54.0 and one production wheel digest, `43da134c…`; Python was 3.14.8 through
stage 3 and 3.14.9 from stage 4, after a Homebrew update. DEVELOPMENT.md records that the harness shell
sandbox stops the suite at fixture setup and blocks pruning; run both outside
it or permit the `.gitconfig` operations.

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
