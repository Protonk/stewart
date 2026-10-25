# A narrow custodial core: findings for decision

This is the account for stage 4's opening decision round. It weighs two
external proposals, preserved at
[`planning/inputs/custodial-core.md`](planning/inputs/custodial-core.md) and
[`planning/inputs/history-only.md`](planning/inputs/history-only.md), against
the frozen Python baseline and the decided contracts. It recommends a
disposition for six decisions, A to F, that belong to the user, and lists the
proposed completions and leads the round turned up. Decisions are recorded in
`CONTRACTS.md`; this document retires once they are recorded and its run
records are disposed of under DEVELOPMENT.md's rules.

Evidence is labelled where it matters: *executed* means an installed-wheel run
or the Git-only probe observed it; *source* means a reading anchored in the
code; *prediction* means a reading no run has tested; *judgment* is the
coordinator's. Working accounts under `.scratch/custodial-core/` carry the
full anchors: `operations.md`, `workspace.md`, `comparisons.md`,
`history-view.md`, `git-opinions.md`, and the independent review in
`review.md`.

## The recommendation in brief

For the sessions the successor writes, build around one workspace form and
one history form, with custody always present:

- **A return area** every audit has: the report and declaration are files, and
  collection captures them.
- **A subject tree**, granted or not: a plain directory Stewart writes from the
  commission's raw blobs, with no `.git`.
- **A history view**, granted or not: a separate read-only repository Stewart
  builds holding only the commission's object closure.

The standard profile grants both, files-only grants the tree, history-only
grants the view. The commission records the grants; there are no modes to
build separately. Keep custody records in the repository's Git common
directory, but stop placing refs in the user's ref namespace. Keep the
manager's attributed stop as the capture trigger. Recognize authorized
execution as a fourth responsibility with its authority stated. Whether to
port the manager-side resource lifecycle is a choice with consequences either
way; the lean is to defer it to stage 5.

The successor still reads what Python wrote. Under the writer-continuity
default it is read-only toward Python sessions, so it keeps a read path for
linked-worktree sessions, registry rows and `refs/stewart/sessions/*` until
every Python audit is closed under Python. "One form" describes what the
successor writes, not what it reads.

## A. The admission rule

**Proposal.** Every privileged operation (i) belongs to exactly one of
workspace access, historical inspection and custody capture, (ii) has authority
traceable to the commission or a later manager authorization, (iii) yields an
intelligible record of its result or failure, and (iv) substitutes no Stewart
judgment for the manager's or auditor's.

**Source.** Every operation classifies under the three except two
subsystems (`operations.md` §3):

- **Experiment execution**: `run`, the child launcher and the in-child ledger.
  The grant and the release are custody records, but they exist to authorize
  `run`. `experiment.py` and `ledger.py` hold 880 lines, the child startup in
  `_bootstrap.py` about 70 more, with 38 dedicated tests. The decided route for
  project commands, close's HOME rule and three custody rules depend on it.
- **The manager-side resource lifecycle**: `resource create-*`, `associate`,
  `acknowledge`, `close --resource` and the claim-and-retire phase inside
  every audit close (`holdings.py`, 1,926 lines, 12% of the source, 53
  dedicated tests). The resource half of the custody rule "Removal is
  authorized by two records only" and the decided hold contract depend on it.
  The repository records no use outside its own tests and the manual's
  section on it.

Tests (ii) to (iv), and one custody rule, find these failures in the baseline:

| Test | Failure | Anchor | Disposition |
| --- | --- | --- | --- |
| (ii) | The auditor may read the whole Git common directory: every ref and object, reflogs, other sessions' administration. Nothing in the commission grants it. Today this is a documented limit. | `auditor_scope.py:87-104` | B and F, under the scoped adapter |
| (ii) | The experiment child runs reviewed auditor code with the manager's ambient authority: no sandbox, the manager's PATH, write access to session storage, refs and the manager home as the manager's user. | `experiment.py:196-201,503-506` | A stated limit, below |
| (ii) | `retain` records no actor. | `triage.py:404` | Already decided |
| Rule "Receipts are exclusive" | Collection writes the captured `REPORT.md` and three Git outputs with an overwriting write. The directory is new and denied to the auditor, so a practical overwrite path is hard to construct. | `collect.py:468,519` | Correction, below |
| (iv) | Status infers auditor state and prescribes relaunch. | `status.py:1150-1158` | Already retired by status/14 |
| (iv), arguable | Concluded close refuses over a recorded writer pause. | `close.py:1123-1126` | Lead, below |
| (iv), arguable | Audit close removes Stewart-created resources the command does not name. | `close.py:1188-1198` | Follows A.3 |

**Recommendation.**

1. **Adopt tests (ii) to (iv) as a standing admission test** for successor
   operations, recorded with the principles. They restate decided principles;
   their value is being applied to each new operation. An operation passes,
   or its failing effect moves out of Stewart, or it is admitted with a
   *stated limit*, which qualifies only when the limit's cost is recorded in
   `CONTRACTS.md`'s access and capability limits. Adopted this way, (ii) turns
   the documented limit on the auditor's reach into a failure the successor
   fixes, which B and F do.
2. **Do not adopt "exactly three". Recognize authorized execution** as a
   fourth responsibility: running a manager-released script once, against
   frozen inputs, and capturing what it produced. Moving execution to an
   external executor would turn Stewart's process observations (argv, exit,
   endpoint byte identity of protected files) into executor claims and make
   "one release, one invocation" unenforceable; membership review would
   survive either way, since it is pure over captured bytes. The child's
   authority is admitted as a stated limit: the access limits record that a
   released script runs as the manager, unsandboxed, and can write session
   storage, refs and the manager home, so nobody may rely on session records
   being untouched by a released script. Bounding the child is a separate
   addition that needs real qualification.
3. **The manager-side resource lifecycle: port it, or defer it to stage 5.**
   It constrains no auditor workspace and preserves no commission evidence; it
   is a manager facility for creating and disposing of worktrees, branches
   and directories. Porting it keeps every decided contract as it stands, at
   the cost of the subsystem, its 53 tests, the hold implementation (holds
   are decided but not implemented in Python) and three parsing defects a
   port would copy (`review.md` §20: `_ref_tip` accepting a branch's
   descendant, rename records truncated in the doubt check, `worktree list`
   parsed without `-z`). Deferring it reopens decided items, all listed here:
   - **Principles** (`CONTRACTS.md` "The manager controls what survives"): the
     sentence naming a hold on a recorded resource as the form for a
     provider's condition or a manager's delegation limit would say that form
     is deferred with the lifecycle. Meanwhile there is no recorded form. A
     condition on a manager resource needs none to stop Stewart, which would
     destroy no manager resource; a condition on session material has no
     form, though the session holds copies whose originals stay with the
     manager.
   - **Hold contract**: Decided, departure becomes Deferred, depending on the
     lifecycle's return. No Python hold exists to strand.
   - **Decline of condition records** on supplemental inputs or workspace
     declarations: the outcome stands, and its reason changes from "the hold
     is the one form" to "deferred with the hold".
   - **Status and close**: the status/14 `resources` row and its ownership
     row, `close --plan`'s resource evaluation and conclusion's frozen
     resource check. The successor reports Python-recorded resources
     read-only and claims none.
   - **Custody rule** "Removal is authorized by two records only": its
     resource half stays the Python baseline's rule; the successor removes
     only under a closing record.
   - **Python-created resources**: Python keeps servicing them while it is
     installed; their lock reasons name Python's `close --resource`. After
     that, the exit is the manager's own `git worktree unlock` and removal,
     outside custody. Resource records are never removed and stay readable.
   - **What stays**: the records of exports and retentions are custody and
     need a home outside the resource store; for an export it is Stewart's
     only record of the handover (`handoff.py:168-266`).

   Judgment: defer. The subsystem is the largest in the baseline, nothing on
   record uses it, and without it Stewart destroys no manager material, which
   is "conservative in destroying" taken further. The reliance basis is thin,
   since the repository cannot show whether managers use it; the user knows.

**Lead: a recorded pause blocking conclusion.** Paused mode requires a note
naming the writers and how they were paused (`prepare.py:112-117`), and resume
binds its release to a triage (`triage.py:444-460`), so the hold is an
attributed coordination record Stewart keeps. The status/14 ownership table
already decided that paused holds are "shared records, close-owned mandatory
predicates" (`CONTRACTS.md` observation table), and the outstanding-category
table sends them to "coordination and resume/close prerequisites". Changing
the refusal would reopen that decision. No change is recommended; the exits
today are resume with a triage, or abandon.

## B. The workspace representation

**Proposal.** Give the auditor a plain directory materialized from the
authorized revision, with no `.git`, as an optional profile.

**Source.** Today the auditor gets a locked, detached linked worktree
(`prepare.py:262-270`). Everything that depends on that has a plain-directory
replacement (`workspace.md` §1): the materialization manifest replaces Git's
view in collection and close; the helpers take their identity from the
handoff and the manifest instead of HEAD; the registry row's three remaining
jobs need a new record; the kept-checkout stop keeps only its substitution
arm (a directory pinned by device and inode), since nothing can be
"registered elsewhere". Decided status/14 barely changes.

**Executed: defects of the baseline's worktree that a materializer removes.**

- **Colliding names collapse silently** (`comparisons-02`). On the default
  macOS volume, a tree holding `Notes.md` and `notes.md` prepares
  successfully, but the checkout holds one file with the second entry's bytes;
  the first entry's bytes never reach the auditor. The only trace is an
  ordinary `unexpected_path` gap, the close plans allow the close, and nothing
  names a collision. NFC and NFD spellings of one name behave the same way.
  The handoff tells the auditor the checkout is the prompt commit, which is
  then false.
- **Decomposed names produce false gaps.** A committed file whose name is
  stored decomposed (NFD), with no collision, is reported as an unexpected
  path because Git lists it precomposed.
- **Configured filters execute** during `worktree add` (stage 2,
  `git-filter-02`).
- **Checkout transformations make an untouched audit unclosable as
  concluded** (`comparisons-04`). With `text eol=crlf` on a file committed
  with LF endings, the checkout holds CRLF and Git reports the file clean, so
  collection never archives it and raises no gap for it; status shows nothing
  and offers retain; the concluded close, planned and executed, refuses
  `capture_uncovered` naming the file and removes nothing. When the attribute
  also matches an assigned input, preparation fails (`prepare_failed`,
  recording `input_mismatch`). Configuration such as `core.autocrlf=true` is
  predicted to do the same to every LF text file.

**Reliance changes to decided contracts.** Without `.git` in the tree:

- **Project commands as experiments**: nobody may rely on project tooling that
  consults Git (version from `git describe`, Git-derived build versions,
  tests that call `git`) working in the subject tree. A route, for instance
  pointing such a run at the read-only view, is a write-path design question.
- **The handoff is complete without the helpers**: its manual remedies are
  Git commands (`git show <prompt>:<path> > <path>`). In files-only they need
  a non-Git route, or the gap is recorded and dispositioned.
- **Large-file pointers**: a materializer that runs no filters hands the
  auditor pointer text. LFS content reaches the auditor as a pinned input or
  not at all, and the session records that limit.

**Recommendation.** One workspace form for successor-written sessions: a plain
directory written from raw blobs, with no filters, attributes or helpers run.
Auditors get no linked worktrees. The subject tree and the history view are
separate grants (D, F), so files-only, standard and history-only come out of
one build.

**Proposed completions for decision** (they change what a manager can
commission or what triage must disposition):

1. **Preparation refuses a tree the destination cannot represent
   distinctly**, naming the colliding spellings, before any access is
   granted. Ground: the handoff would otherwise make a false custody claim.
   Exits: rename in a new commit; history-only, which needs no subject tree;
   or a checkout home on a volume that keeps the names distinct
   (`prepare --checkout-home`; predicted, not run). An alternative
   representation that renames one entry is not offered: the auditor would
   receive names the commission does not hold, and the handoff would have to
   describe the mapping; it could be a later addition. Detection probes the
   actual destination volume, since Python's case folding only approximates
   the filesystem's.
2. **Capture compares names under one normalization**, so a committed name
   stored decomposed no longer yields an `unexpected_path` gap. Effect: one
   false gap removed; no other gap changes.

## C. The capture trigger

**Proposal.** Capture after a supervised session exit plus demonstrated
exclusion of every remaining writer.

**Executed** (`comparisons-02`; close observed through its plan). The stop is
the manager's attributed claim (`collect.py:424-429`). Collection observes
twice and records movement when the observations differ
(`collect.py:520-541`). A write into the checkout during collection, before or
after the archive, is recorded as `movement`, and the concluded close plan then
refuses `capture_not_recorded`. A write after collection leaves the receipt
unchanged, status shows nothing, and the concluded close plan refuses
`checkout_changed`. A write into the test's temporary directory, outside the
checkout, after the archive, changed nothing.

**Prediction.** Write-then-restore between observations is invisible by
construction. On macOS a same-user Stewart cannot demonstrate exclusion for
any supported arrangement (manual terminal launch, a launch a human carries to
another host, a harness sub-agent, a human auditor) without an executor
environment: a separate user, a container or a qualified sandbox that ends
descendants (`workspace.md` §5.6).

**Recommendation.** Decline the supervised exit as a precondition: without a
new executor environment it would make files-only unavailable to every
supported arrangement, and weakened to an attributed claim it is today's stop
acknowledgment. Keep the attributed stop and movement detection, and adopt
the proposal's wording discipline: a capture preserves the contents found
identical at two observations, before and after the archive, at an
acknowledged stop; it does not recover earlier states or rule out a change
undone between the observations. If an executor ever supplies an exit
attestation, it is recorded as an attributed observation in its own field. No
new obligation follows.

## D. Commission fields

**Source.** The committed assignment already holds the pinned subject,
question, decision, scope and stop condition (`assignment.py:23`), and the
return kind is already separate from completion, capture state and
disposition (`report_declaration.py:30-34`). New are permitted facilities, a
capture policy and a retention promise.

**Recommendation.**

- **Permitted facilities: accept.** A structured field in the committed
  prompt's metadata naming the grants (subject tree, history view with its
  scope, experiment), pinned by the prompt digest and readable by the
  auditor. An absent grant means the facility is not constructed. A grant
  never refuses preparation, as an assignment's external sources do not. The
  session records what was constructed, in the "constructed, not observed"
  wording the network grant uses. Nobody may rely on a withheld facility
  being unavailable: under the manual and sub-agent styles, and for a human
  auditor, nothing stops the auditor reading the subject repository directly.
- **Capture policy: decline.** Narrowing what collection captures breaks raw
  capture before interpretation, the process promise to the auditor, and is
  the reason segregation at capture was declined with the right to receive;
  the only form of exclusion is a category declared disposable in advance
  whose identity close freezes, as the experiment HOME is. Widening, the
  proposal's "designated evidence", needs no policy: the return area
  captures whatever the auditor writes there.
- **Retention promise: decline.** The principles allow retention rights that
  come from promises actually recorded, so the reason is not a conflict with
  them. A recorded promise would be an undertaking that gates conclusion until
  it is completed or surrendered, which in effect is mandatory retention
  before close, declined as invasive to the manager's flow. The manager keeps
  material through retain and export.

## E. Where custody lives

**Observed.**

- Records live in six directories under `<common>/stewart/`
  (`workspace.md` §3.1). Executed: neither `clone --mirror`, `push --mirror`
  nor an ordinary clone carries them. By the manual, not run: they survive
  `git clean` and are lost with a re-clone or a backup that skips `.git`.
- Retention refs `refs/stewart/sessions/<uuid>/{prompt,target,base}` live in
  the user's ref namespace. Executed: `clone --mirror` and `push --mirror`
  both carry them with the commits they name; an ordinary clone does not. In
  the fixture those commits were also on a branch, so the run does not itself
  show an unpublished assignment commit leaking; since a clone must hold every
  object its refs name, a mirror also receives it (Git's connectivity rule,
  not run). By Git's documentation the refs are also carried by
  `bundle create --all`, advertised over a transport unless hidden, and
  deletable by `fetch --prune` with a matching refspec.
- Moving the repository with a live session. Executed (`comparisons-04`):
  status, collect and `close --plan` refuse `worktree_role_registry` with
  exit 3; renaming it back restores them; a copy refuses the same way while
  the original keeps working. Source: every manager operation reads the
  registry through `maintainer()` (`_repository.py:371-397`), so every
  operation in the moved repository refuses, abandon included
  (`close.py:1022`). The only exit is restoring the original path, outside
  Stewart, and the refusal's next step does not say so
  (`_repository.py:301`). Three things record the old location: registry rows,
  `load_session`'s owner and common-directory checks (`session.py:227-233`)
  and `repo_key` (`_repository.py:78-82`); only the first belongs to linked
  worktrees.
- A store elsewhere needs a locator that no recency, current directory or
  installation chooses, and under the writer-continuity default the
  successor would read two locations indefinitely, since Python's
  repository-level records are never removed (`workspace.md` §3.3).

**Recommendation.** Keep custody records in the common directory: the
repository is the locator, and nothing ordinary copies or deletes them. For
successor-written sessions, retain the commission's objects in Stewart's own
object store there rather than through refs in the user's namespace; the same
store is what the history view (F) is built from. Mirrors and bundles then
carry nothing of what the successor writes, while Python sessions keep their
refs until Python closes them. Cost: the object copy, measured under F.

The move limit needs its own decision with the write path, because B does not
remove it. A refusal whose only next step lies outside Stewart is suspect
under the refusal principle unless it names what it honors. The minimum is a
refusal that names the recorded original path and says restoring it is the
exit; the alternative is records that survive a move. For the baseline, the
limit is stated to users.

## F. The form of the history facility

**Proposals.** A typed query interface (`log`, `show`, `diff`, `blame`,
`ls-tree`, `rev-list`, `cat-file`) whose queries and results Stewart records.

**Source.** No bundled text tells the auditor to read history; Git appears
only in remedies, and a 2026-10-18 self-audit recorded an auditor's `git log`
as exceeding its grant (`workspace.md` §2). Recording queries needs a process
outside the auditor's sandbox, which Stewart, a command-line tool, does not
have, and it would be the first auditor channel to reach Stewart before
collection; the status contract and the declined auditor-attributed
acceptance rest on there being none (`CONTRACTS.md` "Return arrangements").

**Executed** (Git-only probe, `history-view.md`; its environment is given
under Evidence):

- `pack-objects --revs` from the subject, piped into `index-pack` in a fresh
  bare repository, builds exactly the commit's closure, with no replacement
  refs or subject configuration in the view and no filter or hook run.
  `pack-objects` runs in the subject and reads its local configuration, with
  Stewart's overrides applied at command scope. A fetch by object ID is also
  exact, but the subject-side processes receive none of those overrides: an
  `uploadpack.packObjectsHook` from global configuration ran during it
  (`[c0131]`), and its client starts a background `git maintenance` inside
  the view unless disabled. A clone of a temporary ref is not exact and
  writes into the subject. The closure was checked
  against the subject's own `--no-replace-objects` listing, which honors
  grafts and shallow boundaries; that suffices for the ungrafted fixture.
- An alternates-backed view lists and reads every subject object (31 of 31:
  unrelated history, a dangling blob, the replacement commit); the closure
  view refuses them.
- With write permission removed, `log`, `show`, `diff`, `blame`, `ls-tree`,
  `rev-list`, `cat-file`, `grep` and `for-each-ref` all work and write
  nothing. The owner can restore write permission, so read-only holds against
  the auditor's scope, not against the same user.
- Cost: this repository's 895 objects took about 88 ms and 1.26 MB; a
  synthetic history of 30,599 objects about 0.25 s and 5.5 MB. These figures
  do not represent large repositories, and the per-object sizes differ by a
  factor of eight between the two.
- Hazards. `--no-replace-objects` does not disable legacy grafts; a grafted
  subject yields a truncated view that still matches the subject's own
  listing, and `index-pack --strict` and `fsck` catch it (run 05 only). With
  `pack-objects`, a shallow subject yields an incomplete view that `fsck`
  catches; the other methods produce shallow views `fsck` passes. In a
  partial clone, construction and the verifying `rev-list` fetch missing
  objects from the promisor remote, writing into the subject;
  `GIT_NO_LAZY_FETCH=1` stops construction (tried on construction only). The
  promisor was a local `file://` remote, so a fetch over the network is
  predicted, not run.

**Recommendation.** A pinned, read-only view: a repository Stewart builds by
`pack-objects` into `index-pack --strict` under the hardened invocation, holding
exactly the authorized closure (by default the prompt commit's ancestry, which
contains the target), without the subject's replacement refs, grafts or
alternates, with lazy fetching disabled and the result checked by `fsck`. A
grafted, shallow or partial subject is not refused: the view's recorded
identity states what it holds, and when the closure cannot be built without
fetching, the view is recorded as not constructed. Either way preparation's
claim stays true.

- **Scope.** Enforced by which objects exist, where the launch arrangement
  confines the auditor's reads to the view: the scoped adapter, once it no
  longer grants the common directory. Under the manual and sub-agent styles,
  and for a human auditor, nothing confines reads.
- **Records.** Stewart records the view's identity. A query log, if the
  auditor keeps one, is the auditor's claim, captured at collection.
- **Close.** The view is disposable while it matches its construction
  identity; otherwise it is unjudged, conclusion refuses and abandon names it,
  as for a runtime recovery.
- **The network deferral.** The deferred network qualification worried that a
  permitted domain would make the auditor's readable object store
  transmissible. A view shrinks that store to the authorized closure.

Decline the typed, recorded interface for now: it presupposes a service and an
auditor channel no decision has created.

## Corrections

These apply rules or obligations already decided; they need no new decision.

1. Collection creates its captured files exclusively, under the custody rule
   "Receipts are exclusive" (`collect.py:468,519`).
2. The successor's single Git invocation policy, already an obligation,
   covers what the baseline leaves open:
   - legacy grafts;
   - lazy fetching in partial clones;
   - `color.ui` and `diff.noprefix`, which put escapes and altered headers
     into collection's patches (reviewer's scratch check, `review.md` §19);
   - the assumption that Git precomposes Unicode names on macOS;
   - `worktree.useRelativePaths`, under which close is predicted to leave
     administration behind.

   SHA-256 repositories are unqualified. Grafts, lazy fetching and relative
   paths are predicted for the baseline from Git's behavior; none was run
   through Stewart.
3. Documentation:
   - The manual says close runs `git worktree remove`
     (`src/stewart/resources/README.md:627`), but the code removes the
     checkout by descriptors and never lets Git delete contents.
   - The package and CLI descriptions say Stewart never runs project tests
     (`cli.py:67`, `__init__.py:7`), but `run` executes reviewed scripts that
     may.

## Leads

- **A failed preparation can be collected, triaged and closed as
  concluded** (executed, `comparisons-04`; control only, no invariance case).
  Collect and triage never read the failure record (`session.py:184-266`);
  conclusion refuses only on verification-level attention
  (`close.py:1109-1114`); only status's offer withholds it (`status.py:1381`).
  The decided rule keeps offers as advice rather than preconditions, so this
  is consistent with the contracts. The executed close removed the failure
  record. The closing record keeps the stage `failed` and the reason
  `prepare_failed`, but not the record's content. Question: whether the new
  closing schema freezes the failure record's identity, as it does for
  discards.
- **The recorded pause** (A, above).

## Exits of the rules proposed here

| Rule | Exit |
| --- | --- |
| Refuse an unrepresentable tree (B.1) | Rename in a new commit; history-only; a distinct-name volume (predicted) |
| Name normalization in capture (B.2) | None needed; it removes a gap |
| A view not constructed or with a recorded limit (F) | Make the subject complete and prepare again, or proceed under the limit |
| View at close (F) | Matches its identity: removed; otherwise collect, or abandon naming it |
| Admission failures (A.1) | Move the effect out, or admit with a limit recorded in the access limits |
| Permitted facilities (D) | No refusal; an absent grant constructs nothing |
| Resources deferred (A.3) | Python's `close --resource` while installed; then manual removal |
| Moved repository (E) | Today only restoring the path, outside Stewart; to be decided |
| Exclusive capture files (correction 1) | A retry writes a fresh collection |

## The Git environment document

`GIT-ENVIRONMENT-NEEDS.md` is written for Stewart's users. It leads with what
Stewart expects, places, runs and does not support, then a reference table
generated by `scripts/git_opinions.py` from the source: 180 rows in five
classes (12 configuration, 57 invocations, 6 ref namespaces, 23
administration paths, 82 refusals), with a coverage check that found no Git
launch outside the helpers; the independent sweep agreed. A test fails when
the table is stale or the guide cites a row or reason that does not exist. The review corrected its statuses: they
now distinguish behavior Stewart stands behind, behavior decided to change,
behavior that may change in a later version, incidental details, and cases
Stewart does not support. The statuses are the user's decisions, and those
that A to F would settle are marked as possibly changing. The document is not
yet shipped or linked from where users look; that follows the user's decision
on its statuses.

The generator is a static evaluator of Python source (about 2,400 lines,
with 20 tests). It serves the baseline's document, and its IDs embed function and variable
names, so decisions in `CONTRACTS.md` should cite an opinion's text, not its
ID. Judgment: for the successor, observe Git invocations instead, through the
test suite's existing Git wrapper, which is language-agnostic, and keep static
extraction for what tracing cannot see (reason identifiers, administration
paths, ref names). That is a choice for the user when the successor's
document is due.

## Evidence

| Run | Selected | Outcome | Notes |
| --- | --- | --- | --- |
| `comparisons-01` | 14 | 14 passed | Controls asserted only |
| `comparisons-02` | 14 | 14 passed | Observed outcomes asserted |
| `comparisons-03` | 23 | 23 passed | Earlier 14 assert observed outcomes; the 9 new nodes assert controls only |
| `comparisons-04` | 23 | 23 passed | All observed outcomes asserted |
| `git-opinions-01` | 4 | 4 passed | Generator's first tests |
| `git-opinions-02` | 20 | 20 errors at setup | A test helper named `setup` was called by pytest as a module hook |
| `git-opinions-03` | 20 | 19 passed, 1 failed | The coordinator's rename of that helper collided with a local name |
| `git-opinions-04` | 20 | 20 passed | After review |
| `git-opinions-05` | 20 | 20 passed | Final, after the preamble's wording changed |

All installed-wheel runs tested wheel `43da134c…`, the same digest as the
stage-2 and stage-3 runs, under Python 3.14.9 (earlier runs used 3.14.8) and
Apple Git 2.54.0, with the shell sandbox disabled for the checker only (per
the run accounts; the receipts do not record it). Each test had a private
`HOME` whose `.gitconfig` held only a name and email; system configuration
applied. Close was executed in the transformation and failed-preparation
cases and observed through its plan elsewhere. The mirror comparison's
ordinary clone is a differing case; it has no invariance case.

The probe ran Git 2.54.0 alone, inside the shell sandbox. It removed every
`GIT_*` variable and set a private `HOME` and `XDG_CONFIG_HOME`,
`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`,
`GIT_CEILING_DIRECTORIES` and `LC_ALL=C`, and gave every command the hooks
and file-system monitor overrides (`probe.py:14,195-203`). Non-bare fixtures
use separate Git directories because the sandbox refuses writes to
`.git/config` and hooks. `probe-05` is the record; runs 03 and 04 cover most
of its facts but not all (03 lacks `--strict`, the no-maintenance variant and
the large synthetic history; 04 lacks grafts), and no digest of `probe.py`
was recorded.

## Independent review

A fresh reviewer checked this account, the user document, the generator and
every run record at `7b8e986` (`review.md`: 32 findings, 3 blocking). The
executed comparisons held against their observation files; the problems were
in what the documents built on them. All three blocking findings are
resolved:

- The guide's statuses promised behavior this round proposes to change, or
  that `CONTRACTS.md` already decided to change. They now distinguish relied
  on, decided to change, may change and incidental, and describe this version
  only.
- Deferring the resource lifecycle reopened decided items without listing
  them. A.3 is now a choice with every reopening and exit enumerated.
- Two new obligations were presented as corrections. The collision refusal
  and the normalization change are now proposed completions under B, with
  exits.

Of the non-blocking findings, these are applied:

- false user assurances, missing hazards and refusal wrapping in the user
  document;
- plan observations labelled as plans, and claims mislabelled as executed;
- the move limit's scope and its unsupported premise;
- the probe's environment and replication;
- the anchors and counts;
- the reliance changes to decided contracts;
- the read path for Python sessions, the close rule for the view and the
  pause's decided ownership row;
- the exits;
- the generator's dropped refusals, row descriptions, preamble claims, write
  safety, freshness test and the tests for surviving mutants.

Not applied, with reasons:

- **A mirror case with an unpublished assigning commit.** Git's connectivity
  rule settles it, and the claim is labelled accordingly.
- **A status column generated from a map keyed by row ID.** IDs embed code
  names, and the guide's class-level statuses with a citation test serve the
  baseline.
- **A reason index and short IDs in the table.** These follow the decision on
  the generator's future.
- **Rebuilding the static evaluator's weak spots.** The baseline source is
  frozen and none of them is triggered at HEAD. Unknown spreads and mutated
  lists now fail coverage instead of producing rows.
- **Shipping and linking the document.** This follows the user's decision on
  its statuses.

## Limitations

The collision and transformation results hold for the default APFS volume,
Git's `core.ignorecase` and `core.precomposeunicode`, and an empty global
configuration; other volumes and user configuration were not run. No real
harness was exercised, so constructed access settings remain unqualified
beyond what earlier stages established. The probe's environment isolates Git
from user configuration that an auditor reading a view would have. Cost
figures for the history view come from small repositories.
