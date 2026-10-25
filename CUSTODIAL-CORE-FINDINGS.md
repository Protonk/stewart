# A narrow custodial core: findings for decision

This is the account for stage 4's opening decision round. It weighs two
external proposals, preserved at
[`planning/inputs/custodial-core.md`](planning/inputs/custodial-core.md) and
[`planning/inputs/history-only.md`](planning/inputs/history-only.md), against
the frozen Python baseline and the decided contracts. It recommends a
disposition for six decisions, A to F, that belong to the user. Decisions are
recorded in `CONTRACTS.md`; this document retires once they are recorded and
its run records are disposed of under DEVELOPMENT.md's rules.

Evidence is labelled where it matters: an *observation* is anchored in source
or an executed run; a *prediction* is a source reading no run has tested; a
*judgment* is the coordinator's. Working accounts under
`.scratch/custodial-core/` carry the full anchors: `operations.md`,
`workspace.md`, `comparisons.md`, `history-view.md` and `git-opinions.md`.

## The recommendation in brief

Build the successor around one workspace form and one history form, with
custody always present:

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
execution as a fourth responsibility with its authority stated, and leave the
manager-side resource lifecycle out of the successor's core. Each piece is
argued below with what it costs.

## A. The admission rule

**Proposal.** Every privileged operation (i) belongs to exactly one of
workspace access, historical inspection and custody capture, (ii) has authority
traceable to the commission or a later manager authorization, (iii) yields an
intelligible record of its result or failure, and (iv) substitutes no Stewart
judgment for the manager's or auditor's.

**Observed.** Every operation classifies under the three except two
subsystems (`operations.md` §3):

- **Experiment execution**: `run`, the child launcher and the in-child ledger.
  The grant and the release are custody records, but they exist to authorize
  `run`. 880 source lines and 38 dedicated tests. The decided route for project
  commands, close's HOME rule and three custody rules depend on it.
- **The manager-side resource lifecycle**: `resource create-*`, `associate`,
  `acknowledge`, `close --resource` and the claim-and-retire phase inside
  every audit close (`holdings.py`, 1,926 lines, 12% of the source, 53
  dedicated tests). Most of the custody rule "Removal is authorized by two
  records only" and the decided hold contract depend on it. The repository
  records no use outside its own tests and the manual's section on it.

Tests (ii) to (iv) find these failures in the baseline:

| Test | Failure | Anchor | Disposition |
| --- | --- | --- | --- |
| (ii) | The auditor may read the whole Git common directory: every ref and object, reflogs, other sessions' administration. Nothing in the commission grants it. | `auditor_scope.py:87-104` | Addressed by B and F |
| (ii) | The experiment child runs reviewed auditor code with the manager's ambient authority: no sandbox, the manager's PATH, write access to custody storage as the manager's user. | `experiment.py:196-201,503-506` | Stated as a limit below |
| (ii) | `retain` records no actor. | `triage.py:404` | Already decided |
| (iii) | Collection writes the captured `REPORT.md` and three Git outputs with an overwriting write, not the exclusive creation the custody rules require. | `collect.py:468,519` | New correction |
| (iv) | Status infers auditor state and prescribes relaunch. | `status.py:1150-1158` | Already retired by status/14 |
| (iv), arguable | Concluded close refuses over a recorded writer pause that Stewart neither controls nor undertook anything about. | `close.py:1123-1126` | Open lead, below |
| (iv), arguable | Audit close removes Stewart-created resources the command does not name. | `close.py:1188-1198` | Moot if resources leave |

**Recommendation.**

1. Adopt tests (ii) to (iv) as a standing admission test for successor
   operations, recorded with the principles. They restate decided principles;
   their value is being applied to each new operation, as this round did.
2. Do not adopt "exactly three". Recognize **authorized execution** as a
   fourth responsibility: running a manager-released script once, against
   frozen inputs, and capturing what it produced. Moving execution to an
   external executor would turn Stewart's process observations (argv, exit,
   endpoint byte identity of protected files) into executor claims and make
   "one release, one invocation" unenforceable; membership review would
   survive either way, since it is pure over captured bytes. The child's
   present authority is stated as a limit, not promised away: it is the
   manager's, unsandboxed. Bounding it is a separate addition that needs real
   qualification.
3. Leave the **manager-side resource lifecycle** out of the successor's core.
   It constrains no auditor workspace and preserves no commission evidence; it
   is a manager facility for creating and disposing of worktrees, branches and
   directories, which the manager can do with Git directly. Two parts are
   custody and stay: the record of an export, which is Stewart's only record
   of that handover (`handoff.py:168-266`), and the record of a retention.
   Consequences: Stewart no longer destroys manager material at all, which is
   "conservative in destroying" taken further; the hold contract and
   enrollment lose their object for disposal and would be restated or
   retired; and the removal rule shrinks to the closing record. If managers
   rely on the lifecycle, it is a stage-5 candidate rather than a stage-4
   port. The user knows whether they do.

**Open lead.** Whether a recorded pause should block conclusion. Stewart
records the manager's pause claim and controls no writer; the refusal reads
either as conditioning Stewart's own "concluded" record over a hold it
recorded, or as enforcing manager process. Abandon stays available. No change
is recommended without a decision.

## B. The workspace representation

**Proposal.** Give the auditor a plain directory materialized from the
authorized revision, with no `.git`, as an optional profile.

**Observed.** Today the auditor gets a locked, detached linked worktree
(`prepare.py:262-270`). Everything that depends on that has a plain-directory
replacement (`workspace.md` §1): the materialization manifest replaces Git's
view in collection and close; the helpers take their identity from the
handoff and the manifest instead of HEAD; the registry row's three remaining
jobs need a new record. Decided status/14 barely changes. The baseline's
worktree also carries defects a materializer removes:

- **Colliding names collapse silently** (executed, `comparisons-02`). On the
  default macOS volume, a tree holding `Notes.md` and `notes.md` prepares
  successfully, but the checkout holds one file with the second entry's bytes;
  the first entry's bytes never reach the auditor. The only trace is an
  ordinary `unexpected_path` gap, the close plans allow the close, and nothing
  names a collision. NFC and NFD spellings of one name behave the same way.
  The handoff tells the auditor the checkout is the prompt commit, which is
  then false.
- **Decomposed names produce false gaps** (executed). A committed file whose
  name is stored decomposed (NFD), with no collision, is reported as an
  unexpected path because Git lists it precomposed.
- **Configured filters execute** during `worktree add` (stage 2,
  `git-filter-02`).
- **Checkout transformations make an untouched audit unclosable as
  concluded** (executed, `comparisons-04`). With `text eol=crlf` on a file
  committed with LF endings, the checkout holds CRLF and Git reports the file
  clean, so collection never archives it and raises no gap for it; status
  shows nothing and offers retain; the concluded close, planned and executed,
  refuses `capture_uncovered` naming the file and removes nothing. When the
  attribute also matches an assigned input, preparation fails
  `input_mismatch`.

**Lost or needing a facility.** Git commands inside the tree: the auditor's,
project tooling that consults Git (version from `git describe`, build
backends), and the restore remedy `git show <prompt>:<path> > <path>`. The
helpers need a manifest protocol. A human auditor's manual remedies need a
non-Git route, or the gap is recorded and dispositioned.

**Recommendation.** One workspace form for the successor: a plain directory
written from raw blobs, with no filters, attributes or helpers run, refusing
before access any tree the destination cannot represent distinctly (probed
on the actual volume, since Python's case folding only approximates the
filesystem's). Auditors get no linked worktrees. The subject tree and the
history view are separate grants (D, F), so files-only, standard and
history-only come out of one build. How the standard profile serves
Git-calling project tooling, for instance by pointing a run at the read-only
view, is an implementation question for the write path, not a decision here.

## C. The capture trigger

**Proposal.** Capture after a supervised session exit plus demonstrated
exclusion of every remaining writer.

**Observed.** The stop is the manager's attributed claim
(`collect.py:424-429`). Collection observes twice and records movement when
the observations differ (`collect.py:520-541`). Executed (`comparisons-02`):
a write during collection, before or after the archive, is recorded as
`movement`, and a concluded close then refuses `capture_not_recorded`; a
write after collection leaves the receipt unchanged, status shows nothing,
and close refuses `checkout_changed`; a write outside the checkout changes
nothing. Write-then-restore between observations is invisible by
construction (prediction). On macOS a same-user Stewart cannot demonstrate
exclusion for a manual launch, a launch a human carries to another host, a
harness sub-agent or a human auditor (`workspace.md` §5.6); it would need a
separate user, a container or a qualified sandbox that ends descendants.

**Recommendation.** Decline the supervised exit as a precondition: it would
make files-only unavailable to three of the four supported arrangements, and
weakened to an attributed claim it is today's stop acknowledgment. Keep the
attributed stop and movement detection, and adopt the proposal's wording
discipline: a capture preserves the surviving contents at an acknowledged
stop, observed unchanged between two reads; it does not recover earlier
states. If an executor ever supplies an exit attestation, it is recorded as an
attributed observation in its own field. No new obligation follows.

## D. Commission fields

**Observed.** The committed assignment already holds the pinned subject,
question, decision, scope and stop condition (`assignment.py:23`), and the
return kind is already separate from completion, capture state and
disposition (`report_declaration.py:30-34`). New are permitted facilities, a
capture policy and a retention promise.

**Recommendation.**

- **Permitted facilities: accept.** A structured field in the committed
  prompt's metadata naming the grants (subject tree, history view with its
  scope, experiment), pinned by the prompt digest and readable by the
  auditor. The session records what was constructed, in the "constructed,
  not observed" wording the network grant uses; nothing claims a grant was
  enforced.
- **Capture policy: decline.** Narrowing what collection captures breaks raw
  capture before interpretation, the process promise to the auditor, and is
  the reason segregation at capture was declined with the right to receive.
  The only form of exclusion is a category declared disposable in advance
  whose identity close freezes, as the experiment HOME is.
- **Retention promise: decline.** A recorded promise is exactly what would
  give the auditor or others retention rights the principles withhold, and it
  would gate conclusion as an undertaking. Mandatory retention before close
  was declined for the same reasons. The manager keeps material through
  retain and export.

## E. Where custody lives

**Observed.**

- Records live in six directories under `<common>/stewart/`
  (`workspace.md` §3.1). Executed: neither `clone --mirror` nor
  `push --mirror` carries them, nor does an ordinary clone. They survive
  `git clean` and are lost with a re-clone or a backup that skips `.git`.
- Retention refs `refs/stewart/sessions/<uuid>/{prompt,target,base}` live in
  the user's ref namespace. Executed: `clone --mirror` and `push --mirror`
  both carry them with the commits they pin, which include the commission's
  prompt commit; an ordinary clone does not. By Git's documentation they are
  also carried by `bundle create --all`, advertised over a transport unless
  hidden, and deletable by `fetch --prune` with a matching refspec.
- Moving the repository with a live session (executed, `comparisons-04`):
  status, collect and `close --plan` refuse `worktree_role_registry` with
  exit 3, because every registry row names the old common directory;
  renaming it back restores them; a copy refuses the same way while the
  original keeps working.
- A store elsewhere needs a locator that no recency, current directory or
  installation chooses, and under the writer-continuity default the
  successor would read two locations indefinitely, since Python's
  repository-level records are never removed (`workspace.md` §3.3).

**Recommendation.** Keep custody records in the common directory: the
repository is the locator, and nothing ordinary copies or deletes them.
Retain the commission's objects in Stewart's own object store there rather
than through refs in the user's namespace; the same store is what the history
view (F) is built from. Mirrors and bundles then carry nothing of Stewart's.
Cost: the object copy, measured under F. A moved repository refusing every
operation is stated as a limit for now; most of the absolute paths that cause
it belong to linked worktrees, which B removes, so whether the successor
survives a move is better decided with the write path.

## F. The form of the history facility

**Proposals.** A typed query interface (`log`, `show`, `diff`, `blame`,
`ls-tree`, `rev-list`, `cat-file`) whose queries and results Stewart records.

**Observed.** No bundled text tells the auditor to read history; Git
appears only in remedies, and a 2026-10-18 self-audit recorded an auditor's
`git log` as exceeding its grant (`workspace.md` §2). Recording queries needs
a process outside the auditor's sandbox, which Stewart, a command-line tool,
does not have, and it would be the first auditor channel to reach Stewart
before collection; the status contract and the declined auditor-attributed
acceptance rest on there being none (`CONTRACTS.md` "Return arrangements").
A Git-only probe (`history-view.md`, run `probe-05`, Git 2.54.0, no Stewart
code) established:

- `pack-objects --revs` piped into `index-pack` in a fresh bare repository
  builds exactly the commit's closure, with no replacement refs, no subject
  configuration and no filter or hook run. A fetch by object ID is also exact,
  but the subject's `upload-pack` runs under the subject's own configuration
  and starts background maintenance unless disabled. A clone of a temporary
  ref is not exact and writes into the subject.
- An alternates-backed view lists and reads every subject object (31 of 31:
  unrelated history, a dangling blob, the replacement commit); the closure
  view refuses them.
- With write permission removed, `log`, `show`, `diff`, `blame`, `ls-tree`,
  `rev-list`, `cat-file`, `grep` and `for-each-ref` all work and write
  nothing, with or without optional locks. The owner can restore write
  permission, so read-only holds against the auditor's scope, not against the
  same user.
- Cost: this repository's 895 objects took about 88 ms and 1.26 MB; a
  synthetic 30,599 objects about 0.25 s and 5.5 MB, roughly linear. These
  sizes do not represent large repositories.
- Hazards: `--no-replace-objects` does not disable legacy grafts, and a
  grafted subject yields a truncated view that still matches the subject's own
  listing; `index-pack --strict` and `fsck` catch it. A shallow subject yields
  an incomplete view that `fsck` catches. A partial clone fetches missing
  objects from its promisor remote during construction, and even during the
  verifying `rev-list`, writing into the subject, unless `GIT_NO_LAZY_FETCH=1`
  is set.

**Recommendation.** A pinned, read-only view: a repository Stewart builds by
`pack-objects` into `index-pack --strict`, holding exactly the authorized
closure (by default the prompt commit's ancestry, which contains the target),
without the subject's replacement refs, grafts, configuration or alternates,
with lazy fetching disabled and the result checked by `fsck`. A grafted,
shallow or partial subject is refused or its limit recorded, never silently
viewed. The auditor reads the view with ordinary Git, which also serves a
human auditor; scope is enforced by which objects exist, and the auditor's
access scope makes it read-only. Stewart records the view's identity; a query
log, if the auditor keeps one, is the auditor's claim captured at collection.
Decline the typed, recorded interface for now: it presupposes a service and an
auditor channel no decision has created.

## Findings that bear on decided contracts

These are corrections or limits rather than additions; the successor
realizes them whatever A to F decide.

1. Collection creates its captured files exclusively (`collect.py:468,519`).
2. Preparation refuses a tree the destination cannot represent distinctly,
   naming the colliding spellings, rather than granting access to a checkout
   the handoff misdescribes.
3. Capture compares names under one normalization, so a decomposed committed
   name is not reported as an unexpected path.
4. The successor's single Git invocation policy, already an obligation,
   also covers what `--no-replace-objects` leaves open: legacy grafts, and
   lazy fetching in partial clones, which would make Stewart's own reads of
   the commission reach a remote. Both are predicted for the baseline from
   the probe's Git behavior; neither was run through Stewart.
5. The manual says close runs `git worktree remove`; the code removes the
   checkout by descriptors and never lets Git delete contents
   (`README.md:627`). The package and CLI descriptions say Stewart never runs
   project tests, while `run` executes reviewed scripts that may
   (`cli.py:67`, `__init__.py:7`).

One lead, consistent with the decided contracts but worth a decision: a
failed preparation can be collected, triaged and closed as concluded
(executed, `comparisons-04`). Collect and triage never read the failure record
(`session.py:184-266`); conclusion refuses only on verification-level
attention (`close.py:1109-1114`); only status's offer withholds it
(`status.py:1381`), and the decided rule keeps offers as advice rather than
preconditions. The executed close removed the failure record; the closing
record keeps the stage `failed` and the reason `prepare_failed` but not the
record's content. The question is whether the new closing schema freezes the
failure record's identity, as it does for discards.

## The Git environment document

`GIT-ENVIRONMENT-NEEDS.md` is written for Stewart's users. Its table is
generated by `scripts/git_opinions.py` from the source: 176 rows in five
classes (12 configuration, 57 invocations from 77 call sites, 6 ref
namespaces, 22 administration paths, 79 refusals), with a coverage check that
found no Git launch outside the helpers. Its interpretation guide proposes a
status for each class of rows, and those statuses are the user's decisions.
The document describes the baseline, so the statuses A to F would change are
marked undecided there. The generator parses Python source; once the successor
replaces it, the table needs an extractor for the successor's source, so the
script's 2,038 lines serve the baseline's document only.

## Evidence

| Run | Selected | Outcome | Notes |
| --- | --- | --- | --- |
| `comparisons-01` | 14 | 14 passed | Controls asserted only |
| `comparisons-02` | 14 | 14 passed | Observed outcomes asserted |
| `comparisons-03` | 23 | 23 passed | Adds transformations, moves, failed preparation; controls only |
| `comparisons-04` | 23 | 23 passed | Observed outcomes asserted |
| `git-opinions-01` | 4 | 4 passed | Generator's own tests |

All installed-wheel runs tested wheel `43da134c…`, the same digest as the
stage-2 and stage-3 runs, under Python 3.14.9 (earlier runs used 3.14.8) and
Apple Git 2.54.0, with the shell sandbox disabled for the checker only. The
history-view probe used Git 2.54.0 alone, inside the shell sandbox (non-bare
fixtures use separate Git directories because the sandbox refuses writes to
`.git/config` and hooks); `probe-05` is its record and runs 03 and 04
replicate it.

## Limitations

The collision results hold for the default APFS volume and Git's
`core.ignorecase` and `core.precomposeunicode`; other volumes were not run.
No real harness was exercised, so constructed access settings remain
unqualified beyond what earlier stages established. Cost figures for the
history view come from small repositories and do not represent large ones.
