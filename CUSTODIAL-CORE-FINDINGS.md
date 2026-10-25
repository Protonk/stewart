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
manager's attributed stop as the capture trigger. **A.2 is now decided: the
successor has no dedicated program executor.** Permitted auditor tool use and
custody of captured returns remain; the staged release/run workflow is not
ported or transferred into an external service. Other items remain
recommendations except where a decision is marked below. The user has decided
to defer general manager-workspace creation and disposal, leaning toward
isolating and possibly removing it rather than advancing it. Audit-owned
allocation remains, and narrow attributed holds on identified custody material
with explicit release are decided independently of that service (A.3).

The successor's legacy reading is now bounded by an identified consumer,
supported record population and custody claims. No unconditional read path for
every linked-worktree session, registry row or private Python resource model
follows. Old writers retain authority over their lifetimes; transition-only
inspection need not become a permanent successor surface. Historical evidence
is preserved unchanged, and the Python corpus remains comparison evidence.

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
  authorized by two records only" and the original resource-bound hold contract
  depended on it; the successor dispositions below separate their scope.
  The repository records no use outside its own tests and the manual's
  section on it.

Tests (ii) to (iv), and one custody rule, find these failures in the baseline:

| Test | Failure | Anchor | Disposition |
| --- | --- | --- | --- |
| (ii) | The auditor may read the whole Git common directory: every ref and object, reflogs, other sessions' administration. Nothing in the commission grants it. Today this is a documented limit. | `auditor_scope.py:87-104` | B and F, under the scoped adapter |
| (ii) | The experiment child runs reviewed auditor code with the manager's ambient authority: no sandbox, the manager's PATH, write access to session storage, refs and the manager home as the manager's user. | `experiment.py:196-201,503-506` | Baseline limit; dedicated executor omitted from successor under A.2 |
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
2. **No dedicated successor program executor: decided 2026-10-25.** The user
   selected arrangement 1 from the comparison below. Omit the staged
   construction/review/release/run service, its launcher, invocation controls,
   dedicated output/HOME lifecycle and process-witness guarantees. The manager
   commissions an audit; permitted auditor tool use remains within its actual
   grants. Stewart captures the return and verifies custody, not the truth of
   reported process execution. This supersedes the stage-3 reviewed-shim route
   for successor project commands and the earlier fourth-responsibility
   recommendation. No external executor service replaces it.

   CONTRACTS.md records the dependent dispositions. Ledger/membership
   interpretation over selected captured evidence needs a named consumer and
   bounded schema scope if retained; it does not imply an execution service.
   Legacy Python records and unfinished undertakings stay protected by their
   explicit transition. Interrupted Stewart capture, publication, requests and
   close still need supported resolution without agent-manager private-state
   repair. The possible audit restart facility is separately undecided. This
   is a successor scope decision, not a commission to change frozen Python or
   begin Rust implementation.
3. **General manager-workspace creation and disposal: deferred, decided
   2026-10-25.** The user leans toward isolating and possibly removing this
   service instead of advancing it; it is not a promised later port. The
   reason is the division between audit custody and the manager's independent
   work. Audit-owned allocation and required custody/dependency/access
   protections remain. This revises the earlier binary port-or-defer account
   and its suggestion that holds must follow the general service. Changes
   recorded in `CONTRACTS.md` and development guidance:
   - **Principles and holds:** the resource-bound hold is replaced by a
     narrow attributed hold on identified custody material, with explicit
     release. Holds are decided, not deferred; no Python hold exists to strand.
   - **Condition records:** the decline of separate supplemental-input or
     workspace condition mechanisms stands, with the custody-material hold
     supplying the form and the attribution. Its scope over copies still
     requires design.
   - **Status and close:** legacy records remain unchanged; any successor
     interpretation follows the bounded reader contract below. Successor audit close evaluates its own removal
     inventory, dependencies and holds, and creates no general manager-resource
     removal claims. Manager workspaces have a separate lifetime.
   - **Removal authority:** the resource-claim half of the two-record rule
     remains the frozen Python baseline's rule. Successor audit removal is
     closing-record-authorized; deferral does not weaken frozen identity,
     descriptor removal, shared-use or custody-hold protections.
   - **Legacy resources:** preserve their records and writer-bound recovery.
     Python can service them while available; manual retirement is outside
     Stewart custody. Their inventory and unfinished claims require an
     explicit transition disposition before Python is withdrawn.
   - **Custody and access:** retain records of exports, retentions and failed
     publication independently of the general service, and establish the
     manager- and auditor-side access arrangements the audit needs. For an
     export, the existing resource record is Stewart's repository-held
     handover record (`handoff.py:168-266`).

   Admission tests A.1 remain undecided; A.2 now omits the dedicated executor.
   The chosen workspace
   and history representation, capture trigger and custody location are also
   still open; this decision supplies a boundary for assessing them.

### A.2 comparison and decision: who owns program execution?

**Outcome, 2026-10-25: the user selected arrangement 1.** The comparison below
keeps the reasons and rejected alternatives available; it is not a pending
choice or a queue to implement arrangements 2 and 3. These are design alternatives,
not implemented capabilities or newly executed comparisons. The source anchors
are `experiment.py:1-12,242-286,382-418,503-594`,
`request_keys.py:171-244,389-410`, and CONTRACTS.md's preservation-undertaking,
return-arrangement and execution-limit accounts. They establish the baseline;
the selected successor departure remains unimplemented.

"Execution" here means Stewart's optional program runner, not launching the
auditor's harness and not the auditor's intellectual investigation. An auditor
may use tools under its commission and enforced access grants without Stewart
operating a separate executor. Removing that executor does not silently add an
external service to which the manager must hand over the old release workflow.

| Question | 1. No Stewart program executor | 2. Execution within one commission | 3. Retain the staged execution relationship |
| --- | --- | --- | --- |
| Manager relationship | Commission and return. Auditor tool use stays within the granted audit environment. | Commission includes bounded execution authority; Stewart performs/mediates that execution without later manager-operated release stages. | Auditor constructs material; manager receives it and reviews exact bytes before a distinct release and run. |
| Stewart's evidence | Verifies the bytes and provenance it captures. Reported commands, process outcomes and effects remain attributed claims unless separately observed. | Can directly record the process it launches, streams and specified endpoint comparisons, subject to actual isolation and observer limits. | Can retain those process observations plus the manager's explicit approval of the newly constructed script's exact bytes. |
| Responsibility removed or retained | Removes the experiment launcher, release/attempt control, its dedicated HOME and its special cleanup lifecycle. Ordinary audit capture, custody and permissions remain. | Removes manager-operated intermediate stages; retains process authority, invocation accounting, execution environment, output capture and interrupted-process handling. | Retains those duties plus intermediate approval, release identity and return-to-execution transitions. Direct manager workspace access still need not be retained. |
| Main tradeoff | Stewart no longer provides its own process/endpoint witness or enforces invocation limits outside an executor it controls. | Up-front execution authorization must replace the current later exact-byte approval. This is a substantive authority change, not a UI simplification. | A mid-audit manager decision must be worth preserving despite the preferred abstract handoff relationship. |

**The authorization choice in arrangement 2 is unavoidable.** If execution
must remain subject to approval of exact bytes, the executable material can
be selected before handoff. That serves a narrower set of commissions than
running a script the auditor has yet to construct. Allowing that later script
to run without another manager decision requires an up-front grant over what
it may do and real enforcement of its bounds. Do not silently substitute
general permission for the old exact-byte review. A scoped executor interface
also needs a caller, an invocation trigger and a place to record observations;
if the auditor calls it during the audit, that introduces a pre-collection
operational channel absent from the baseline. This is not merely moving the
existing `run` command behind the curtain or a decision to supervise the
auditor's harness. The stop/capture and delivery decisions remain open.

Arrangement 3's strongest case is precisely that later exact-byte approval.
It could operate on an immutable captured construction return rather than
give the manager access to live auditor files. It nevertheless retains two
manager decisions inside the staged undertaking. Selecting it would require
an explicit exception to the trap-door direction, not an inference from the
amount of code already written. Exact-byte approval does not itself constrain
the script's effects: frozen Python's runner is not sandboxed, and its endpoint
comparison promises only the named bytes at two observations, not continuous
preservation or absence of external effects.

**Retry is a separate axis.** None of these three arrangements requires a
restart command. Arrangement 3 can have one authorized invocation and no
re-release facility, although that would change the baseline's allowance of
new releases. Arrangement 2 does not justify hidden retries merely because
the manager no longer sees intermediate stages. Whatever distinct operations
the original commission grants, a failure or uncertain outcome adds no new
execution authority. One consumed wrapper release prevents a second wrapper
launch under that identity; it does not prove exactly-once external effects.
A restart-from-start convenience, if ever selected, must neither discharge
the first undertaking nor reuse its identity or execution rights.

**The same failures discriminate the arrangements.** These are required design
outcomes to make concrete before implementation, not claims that Python or a
successor already supplies them:

| Case | Arrangement 1 | Arrangement 2 | Arrangement 3 |
| --- | --- | --- | --- |
| A program fails with a known outcome | Auditor supplies an attributed account and selected evidence. Stewart captures that return without claiming it observed the process. | Stewart records its process outcome, spent authority and evidence gaps. Failure does not trigger a second invocation. | Same execution accounting, bound to the exact-byte release. No assumed manager cleanup followed by another release. |
| The manager loses a reply | Find the identified existing operation/return within its custody lifetime and existing preservation undertakings; do not submit another audit to recover it. | Same, including the identified execution outcome if available. | Same, including the release and attempt identities. |
| A process outcome is uncertain after interruption | There is no Stewart experiment process to restart. Uncertainty about auditor activity still needs the audit's chosen stop/capture treatment. | Account for the reserved invocation and any possibly continuing process; obtain supported observations where possible, preserve uncertainty otherwise, and expose an authorized disposition. Never infer nonexecution or launch again to find out. | Same, with release/attempt binding. Neither a new release nor a fresh output path resolves the old uncertainty. |
| Capture or publication is interrupted | All three must preserve captured fragments and planned output identities, finish only within verified authority, or explicitly account for the unfulfilled undertaking. A subsequent observation cannot be presented as recovery of bytes never captured. | Same custody responsibility, plus any runner-produced material still owed to capture. | Same custody responsibility, plus intermediate construction returns and execution material. |
| Retirement or close is interrupted | Resolve the existing frozen removal operation and audit obligations; no manager edits to private inventory as normal recovery. | Same, with execution material and possible live uses accounted for. | Same, including outstanding stage/release obligations. |

Reading an already recorded result spends no execution authority. Completing
publication from verified captured bytes or finishing a recorded removal can
advance custody without repeating the investigation. These distinctions must
be real in the implementation, not exemptions obtained by naming commands
"recovery". Lost replies, uncertain execution and unfinished publication have
different allowed effects even if the eventual interface presents them simply.
An unrecoverable gap remains an explicit acceptance issue until supported
disposition is specified; a diagnostic alone does not justify agent-manager
repairs. No proposal here adds post-close caching or supersedes holds.

**What must receive an explicit disposition.** Under arrangement 1, the
reviewed project-command shim and executor-specific guarantees end as successor
responsibilities; collected results still keep their attribution and byte
identity. Under arrangement 2, decide the changed approval authority and whether
the shim remains useful. Under arrangement 3, justify the separate stage and
its supported handoff. Ledger parsing and membership review over submitted
captured rows can be assessed independently in all three, without treating
those rows as independent proof of execution. Dedicated attempt HOME rules
apply only if that facility survives; removing it does not make other audit
material disposable. Existing Python failures and publication undertakings
retain their bounded transition dispositions under every choice.

**Decision and reason.** The user selected arrangement 1, accepting the lean
that it best fits the commission/return relationship and removes dedicated
execution responsibilities. Arrangements 2 and 3 are not planned optional
features. A future proposal for either would require a fresh scope decision,
not discovery that a previously written runner could be ported. Whether an
audit restart convenience is worthwhile remains separate and open; ordinary
auditor tool use is not removed by this choice.

This comparison and its plan/handoff routing were checked in
`.scratch/resource-decisions/validation-14.json` and its `.log`; zero pytest
nodes selected and zero behavioral comparisons run.

### Resource management: dependencies under review

On 2026-10-25 the user kept resource management unsettled and commissioned a
focused examination of its interactions with the intended simplifications.
Keeping, ignoring, eliminating or strengthening a connection are all open
for evaluation. This is a source-based account, checked against the frozen
implementation and the existing test scenarios; no new comparison or harness
qualification was run. The account informed the subsequent decisions in A.3;
it commissions no implementation. The earlier port-or-defer framing omitted
intermediate arrangements.
The numbered source account records the initial dependencies, not seven
currently undecided alternatives. The disposition table below and CONTRACTS.md
state the decisions reached during the discussion.

1. **Workspace form and the extent of Git responsibility (B, E, F).** Plain
   auditor directories remove one use of linked worktrees. Manager resource
   creation still calls `worktree add`, can create subject branches, and
   disposal still understands Git administration, working-tree changes and
   commit reachability (`holdings.py:681-750,947-995,1258-1281`). Those duties
   would remain even with raw-blob auditor materialization. Deliberate manager
   branch operations are distinct from capture unexpectedly writing subject
   refs; E must say which boundary it promises. Choices include retaining
   this Git-aware manager service, limiting managed kinds, or leaving manager
   workspace construction to callers. A manager worktree is not automatically
   an authorized execution environment for an auditor's Git-dependent test.

2. **Live dependencies, sharing and placement.** Uses include explicit
   associations and paths pinned by sessions and drafts: owner checkout,
   checkout home, runtime, interpreter and launcher. Worktree users also use
   its managed branch (`holdings.py:410-519`). Consequently a directory can
   remain protected because it houses another audit's runtime, with no
   explicit association. New uses inside an active retirement are refused
   (`holdings.py:582-595`; `prepare.py:193-194`). Plain directories do not
   remove these dependencies. Session-owned allocations placed outside
   manager containers could eliminate some; shared runtimes or a shared
   history object store would still need a rule for when deletion is allowed.
   That need does not itself require the general manager-resource API. The
   costs of copying per audit and coordinating shared lifetimes remain to be
   compared if sharing is proposed.

3. **Published evidence, temporary containers and interrupted publication.**
   `retain` writes into the manager checkout; `export` accepts destinations
   inside or outside it. Both use `record_output`, which writes creation and
   outcome records around publication (`triage.py:364-432`;
   `handoff.py:158-266`; `holdings.py:824-858`). Resource records outlive the
   session and are export's repository-held handover record. A recorded output
   inside a retiring container has to be accounted for; another audit's use
   blocks even explicit disposal (`holdings.py:1038-1143,1225-1251`). Options
   include keeping those dependencies, placing enduring outputs outside
   temporary containers, or revising the disposal agreement. Export/retention
   evidence and recorded publication failures still need a home if manager
   cleanup goes. The decided preservation-undertaking rule must be implementable
   against whichever records replace them.

4. **Access exclusion is currently coupled to enrollment.** Recorded managed
   and enrolled directories and worktrees enter later auditor scopes through
   `private_roots` (`holdings.py:1913-1926`; `_repository.py:355-368`). Git's
   worktree inventory supplies some overlapping coverage; ordinary manager
   directories depend on the resource records. Dropping creation/disposal
   does not alone justify losing this exclusion. It could become a separate
   private-location record, or a new access design could make enumeration
   unnecessary. Either replacement needs actual harness qualification; a plain
   folder or a constructed facility grant does not establish confinement, and
   today's recorded scope is a snapshot, not coverage of later resources.

5. **Audit completion and authority to remove manager material.** An audit
   close removes its own inventory and then claims eligible temporary
   resources. It can complete the session close yet exit with attention for
   a blocked resource (`close.py:1176-1226`). Creation-time temporary intent,
   the closing lifetime and the eligibility evaluation supply this route;
   naming each resource in the close command is not required. Separate named
   resource retirement already exists. We can retain that coupling, separate
   audit closure from manager cleanup, narrow the automatic set, or require
   a different disposal decision. Eligibility is also kind-specific: worktree
   changes and unmerged tips block, while an ordinary temporary directory's
   contents can be frozen and removed without being captured as audit evidence
   (`holdings.py:1146-1293`; `test_resource_safety.py:430-493`). Matching a
   frozen inventory establishes the extent of removal, not preservation.

6. **Holds and commission promises (D).** The earlier decided, unimplemented
   hold contract used recorded resources to express a provider's condition or
   a manager's delegation limit. It blocks Stewart's disposal until attributed
   release; it provides neither delivery nor protection against human removal.
   The discussion considered whether holds should narrow with lifecycle
   support, attach independently, or be deferred. The user chose the independent
   custody-material hold in A.3. Removing holds while declining commission
   retention promises would leave no equivalent recorded form. A hold
   on an original does not by itself specify the treatment of captured copies;
   strengthening that relationship would be a new decision. The affected
   principle and decline are enumerated in A.3 above.

7. **Containment, interruptions and the transition.** A nested or shared
   resource produces an ordering and recovery problem: a container cannot
   remove something still used inside it (or held, under the decided hold
   contract), and an interrupted claim
   resumes only over the state it froze (`holdings.py:1363-1399,1468-1576`).
   A simpler layout could eliminate nesting; separate cleanup would retain
   these checks for whatever it still removes. Creation failures, request keys
   and claims have records whose lives exceed the audit's, so closing Python
   audits is not sufficient to dispose of Python resource history or active
   claims (`request_keys.py:1-27`; `holdings.py:1746-1803`). Any transition needs
   explicit treatment of those records and writer-bound recovery. This does
   not select a new migration policy.

The useful next design comparison is among responsibilities and layouts:
session allocation/custody; records of external dependencies and conditions;
and creation/disposal of manager workspaces. These can share mechanisms
without having identical authority or lifetimes. Evaluate them with concrete
cases: a retained report inside a temporary worktree; two audits using a
runtime under one directory; a held resource inside a disposable container;
and an interrupted retirement followed by a new use. Existing tests describe
several baseline variants (`test_resources.py:346-400,759-805,867-916`;
`test_resource_safety.py:152-200,430-493,717-813`). They were read, not rerun
in this examination. No count of source lines, commands or tests settles
which responsibility is wanted.

**How to resolve the seven connections.** At the user's request, the next
inquiry can be divided by whether new evidence could change the design choice.
This is a recommended method, not a commission to run experiments. Later
implementation acceptance tests remain necessary for whichever behavior is
selected; that alone does not make every item an experimental design question.

| Connection | Primary route | Useful order and discriminating question |
| --- | --- | --- |
| 1. Workspace form and Git responsibility | Conversation; service disposition decided | General manager-workspace creation/disposal is deferred, leaning toward isolation/removal. Audit allocation and necessary custody protections remain. Broader auditor workspace/history representation is still a separate decision. |
| 2. Live dependencies, sharing and placement | Both | Shared immutable material is the user's strong preference. Qualify setup cost, storage and effects on another audit when one ends; live testing must also expose missing extraction and silent loss rather than erasing its evidence. Use those observations to inform the unsettled post-use retention/cache policy. |
| 3. Published evidence and temporary containers | Both; custody arrangement provisionally resolved | Specify the layout/identities for environment retirement while the audit retains held captures, with final close after explicit release and other conditions. Rehearse publication, retirement and later inspection, including interruption. |
| 4. Access exclusion | Both, experiment-led | Explicit audit grants are the selected direction, with a preference to eliminate the private-location inventory. Qualify the actual supported harness, including new private directories after launch and shell and file-tool access. Evidence determines whether elimination is achievable or a narrow fallback is needed; the user delegates that judgment. Settings construction alone cannot settle it. |
| 5. Audit completion and removal authority | Conversation; direction agreed | Audit close does not authorize independent manager-workspace cleanup. Manager live access is restricted; the commission and structured return define the relationship. Specify and qualify the permitted interfaces rather than reopening that authority. |
| 6. Holds and commission promises | Conversation; subject and authority decided | A narrow attributed hold covers a finite selection and custody dependencies, blocks disposal, and ends by explicit release. Design identity/copy/transfer representation without adding recursive scope or investigative authority. |
| 7. Containment, interruption and transition | Both, conversation-led | Design then experiment. Specify separate audit ownership, shared-material lifetimes and complete versus interrupted close; then interrupt creation, publication and removal, introduce a competing use, and check the exact recoverable state. Separately inventory and explicitly dispose of legacy Python obligations before withdrawal; inspection is not an experiment. |

Responsibility and authority are now set sufficiently by 1, 5 and 6, with 3's
custody arrangement provisionally resolved. Qualification for 2 and 4 can inform
the remaining layout and last-use choices. Item 7's failure comparisons can
share the publication cases from 3. The live-testing retention proposal below
must preserve evidence of omissions rather than merely measure storage cost.

**Preferred direction during the discussion of 5.** The user wants a
manager's access to the auditor's material to be very restricted after
handoff, with the audit abstract to the manager and missing information
surfacing through the structured return. The coordinator's earlier example
of an unmerged change referred to the manager's preparation worktree, not the
auditor's separate copy; that distinction had been unclear. The preference
nevertheless reaches beyond the example: the audit should be sufficiently
self-contained that later manager edits do not alter what was commissioned.

Proposal for discussion: distinguish the lifetime of Stewart-owned audit
facilities from any manager preparation workspace. Authorized close can
retire the former under the custody rules, without giving the manager a new
housekeeping task for each directory. Ending dependence on the latter would
require capturing or otherwise securing everything still needed; today's
derived-use protection cannot simply be removed. The manager's authority
over commission and disposition need not entail direct live-workspace access.
The access investigation in 4 would then include enforcement on the manager
side, not only the auditor side, with stopping and collection available
through the agreed interface. Ordinary filesystem layout and hiding paths
do not establish that separation. The user subsequently supported this
direction for 5 and requested a reassessment of 1 and 6. Enforcement,
specific permitted operations and detailed closure rules remain open; no
new return channel has been selected.

**Decided implications for resource discussion items 1 and 6.** For 1, allocating and retiring
Stewart's audit facilities remains necessary even if the manager-workspace
service narrows or disappears. The reason to retain manager worktree and
branch creation would then be its independent value in preparing and
organizing the manager's work. It would have a separate lifetime and authority
from closing an audit. The user agreed to keeping audit allocation in the
core and deferring general manager-workspace management, with a lean toward
isolating and removing that service rather than advancing it. Custody records
and dependency/access protections still needed remain. Copying supplied
material or securing its lifetime must actually remove the dependencies
whose tracking would disappear.

For 6, restricting manager access makes the working preservation opportunity
especially consequential. An exit that requires the manager to copy live
auditor material by hand cannot discharge that promise under a boundary
that denies the access. Stewart needs a supported way to expose and keep
the material covered by the promise, with its qualifications. This does not
make retention mandatory or give declared-disposable scratch a new promise.
One contract to revisit if the access boundary reaches that material is the
drifted-recovery exit: the close contract permits abandon after the manager
has taken what it wants, and declines re-capture of recovery contents. That
decline must be reassessed if its assumed preservation route is removed;
the supported access boundary has not yet determined whether it is affected.

For 6 the user accepted a narrow, attributed hold on identified custody
material with explicit release, independently of manager-workspace creation.
This replaces the previous contract's resource attachment, as now recorded in
`CONTRACTS.md`. The subject rule is now a finite identified selection and the
metadata/captured dependencies needed for its custody claims. Under 3's
provisional resolution, the working environment may retire while identified
captured material remains held in the audit's custody; final close waits for
release and the other conditions. Copying alone does not discharge a hold.
A hold changes disposal permission, not access or investigative authority.
Selection representation, copy/transfer treatment and qualification of continued
capture recoverability remain design work within those decisions.

**The tension to carry through later choices.** The user recorded this on
2026-10-25: an effective Stewart audit gives the auditor seemingly transparent
access to the materials used to construct its question, conditioned by manager
selection. Seamless operation favors an isolated, constrained, static slice
without nesting or recursive expansion, about which Stewart can make precise
promises. Effectiveness and seamlessness can trade off in unexpected ways.
This is a design consideration, not evidence that either end is always better.
It belongs in `CONTRACTS.md`'s principles and in the development vision.
Later comparisons should make both the investigative consequences of selecting
material and the operational consequences of its arrangement visible.

**Sharing preference and the possible back door in 3.** The user strongly
leans toward shared immutable material for connection 2. The user provisionally
resolved 3 on 2026-10-25: the working environment may retire while the audit
retains held custody, with final custody close waiting for explicit release and the other
closing conditions. Neither a final lifecycle schema nor a sharing mechanism
is decided. The user's concern about a back door into a more complicated
abstraction exposes these possible leaks:

- A hold could acquire unintended operational capabilities: browsing live
  work, reconstructing a runnable workspace, widening access, or continuing an
  investigation. Holding identified bytes grants none of these. Inspection of
  an authorized captured return and newly authorized work using it are separate
  acts; a hold supplies only the disposal restriction.
- An audit labelled closed could still have unacknowledged ongoing custody
  responsibilities: locating and verifying the selected bytes and their
  provenance, honoring the hold, exporting them when authorized, and ending
  custody after explicit release and authorized disposal. Retiring a workspace
  establishes none of those endings.
- If any arbitrary directory could become a held object, the deferred general
  resource service would return through the hold interface. Constraining held
  material to explicit identities produced by supported custody operations is
  a candidate boundary, not a new enrollment feature.
- Shared storage sharpens the distinction between bytes and custody identity.
  Equal bytes do not merge collections, permissions or holds. Releasing one
  hold cannot invalidate another audit's material, and access to one capture
  must not expose the underlying store's other objects. A selection must also
  account for the dependencies needed to recover and verify it.

The provisionally accepted arrangement keeps custody with the audit until
explicit release and the other closing conditions allow final close. It must describe finished
inquiry and surviving held custody without implying an active auditor or a
monitoring duty. Completing audit close while maintaining an independent
held-custody lifetime would be a substantive continuing service, not merely a
storage optimization; it is not the preferred direction. Release is not itself
permission to destroy unjudged material. This revises the coordinator's earlier
preference for calling the audit closed while held custody survives.

**The hold test and the wider product relationship.** The user supplied this
discriminating test: a hold must not become permission for the manager to
continue the audit or permission for Stewart to leave dangling operations
after close. Complex affordances during the hold phase are a warning to
examine abstraction leaks. This fits the user's account of Stewart's intended
users: they want narrow questions and answers and choose this relationship
over readily messaging, steering and influencing a harness-managed swarm.
General agent supervision is therefore not a feature-parity target. Rich
selected context and investigative latitude can still serve a narrow question.

For later design and qualification, compare the same captured return with and
without a hold: the hold must block the relevant disposal without granting
live access, execution or a further investigation. After explicit release,
the other closing conditions still apply; completed close must leave no
unfinished audit operation, while a failed or interrupted close must remain
visibly unfinished. A completed publication may survive independently, and
another audit's use of shared immutable bytes must remain protected in all
cases. These are proposed discriminating cases, not executed evidence.

This principle does not itself remove existing operations. Python's `launch`
and `message` record manager acknowledgments, not launch or message delivery
(`coordination.py:1-9,130-135`); `resume` releases a paused-writer arrangement,
not a custody-material hold or an auditor process (`triage.py:444-479`). Any
review of their future role must distinguish those meanings. Exceptional
intervention, stopping/collection and delivery mechanisms remain open.

**Direction selected for 4, 2026-10-25.** Pursue access defined positively
from the commission's selected material and required facilities, with the
user's preference to eliminate Stewart's responsibility for a private-location
inventory if possible. The user delegates judgment over the fallback within
the existing access obligations. Shared storage must not expose unselected
material, and the manager-side boundary must still allow receiving captured
returns without live-workspace steering. Qualify shell and file-tool routes
separately, including useful allowed access, denied neighboring material and
new private locations created after launch. Only evidence of the remaining
need justifies retaining a narrow inventory; it does not justify restoring
general resource management. This direction is recorded in CONTRACTS.md.
No successor enforcement comparison has run, and the separately released
experiment child's authority is not settled by this decision.

**What remains of 7.** The general manager-container retirement problem is
outside the successor's selected scope. The remaining design is a bounded
audit lifecycle with shared immutable material, holds and honest recovery.
Eliminating the private-location inventory does not eliminate records of what
Stewart itself owns, uses or holds:

- **Ownership and layout.** Prefer separate independently owned audit areas,
  with shared storage outside any one audit's disposable environment. Ordinary
  directory nesting does not require nesting independently owned lifetimes.
  A held capture and its verification dependencies must remain recoverable
  after the working environment retires, under the provisionally resolved
  arrangement for 3.
- **Shared material and final close.** Ending one audit must not remove bytes
  needed by another audit or hold. Define what happens when the last such use
  ends, including any shared-store contents deliberately retained independently
  of an audit. Do not silently substitute an unowned cleanup queue for completed
  close. Shared bytes do not merge collection identity or authority.
- **Interrupted custody work.** Preparation, capture, publication and removal
  need truthful failure records and bounded recovery over recorded identities.
  Recovery must finish or explicitly dispose of authorized custody work, never
  resume investigation or make a failed close look complete. Test interruptions
  at consequential boundaries and a competing use of shared material.

Legacy Python claims and request records need a separate transition inventory
and explicit disposition before Python is withdrawn. Preserve writer-bound
recovery under the existing default; their existence is not a reason to port
general manager-resource management. The layout and remaining shared-store
choices above are coordinator recommendations for discussion, not accepted
mechanisms or executed qualification.

**Transition boundary accepted with delegated judgment, 2026-10-25.** The user raised the risk
that the transition task itself could leak old responsibilities into the
successor and accepted a finite retirement procedure for a
specified repository/store, separate from successor operations. Inventory the
recorded population first; no actual live legacy population has been established
by this discussion. Do not turn it into a search for every private location,
an enrollment service or an open-ended repair framework.

Distinguish surviving completed evidence, resources deliberately left in place,
and genuinely unfinished custody operations. A record's survival, or a manager
directory's existence, does not establish an unfinished obligation. The
cutover stops admitting new Python work in the selected population, settles
existing work through its authorized writer where possible, and gives every
remaining undertaking an explicit disposition. No report can turn an invalid
receipt, missing writer or unresolved operation into completion. A concrete
exception may need a bounded recovery or relinquishment decision; it does not
automatically justify implementing old resource management in the successor.

Preserve original evidence without rewriting it as successor-native receipts.
Reuse in a new audit should cross a selected captured-evidence boundary with
its provenance, not transfer an old live session or its execution permissions.
The separately deferred cross-writer export question remains open. The end
condition is no unresolved undertaking needing a retiring writer within the
specified population, or an explicit exception that remains visibly outside
that retirement; it is not the absence of all old files.

The user separately reconsidered and narrowed the reader responsibility below:
preserve supported custody interpretation, without automatically carrying the
Python operational model. Any admitted reader has an explicit scope and cost;
no repair, resource eligibility evaluation, old-writer execution or mutation
follows from reading. No transition inventory, migration or retirement has
been executed in this discussion. This strategy changes neither the
writer-continuity default nor the user's authority over obligations.

**Evidence interpretation: direction accepted 2026-10-25.** The user asked
what core commitment justifies this behavior, whether it violates one, and
what work would make it fit. This is a source and existing-evidence assessment,
not a new implementation or experiment. The coordinator's earlier account
treated the inherited reader commitment as settled without sufficiently
separating its product purpose from the Rust implementation sequence.

The defensible commitment is intelligible, qualified access to custody
evidence under a supported interpretation, separate from authority to act on
its lifetime. CONTRACTS.md's refusal principle permits declining claims that
cannot be verified; it does not make the writer's continued availability a
general condition of reading evidence. Its preservation principle specifically
requires completed retained/exported products to be inspectable independently
of the removed session. That does not promise every future implementation
will interpret every historical private-session schema. Raw preservation,
verified interpretation and operational continuity are different duties.

The current Python source already distinguishes them partly: `load_session`
checks a supported schema and session identity; `mutable_session` adds writer
authority (`session.py:184-289`). An unsupported schema is preserved and
diagnosed, not upgraded. But the current reader is not a general detached
archive reader: it checks owner Git administration, runtime/scope structures
and session layout. Status also calls resource disposal evaluation and builds
operation commands (`status.py:754-803`). These are operational-model
dependencies, not necessary consequences of explaining captured evidence.

There is already executed evidence of excessive coupling. The retained
`status-inquiry/render-boundary-01` comparison, described in
STATUS-INQUIRY-FINDINGS.md at `356dc58`, changed the cached manager launcher
while loaded writer bytes still matched: status raised `launcher_mismatch`
during command construction and close-plan became unverified. An unrelated
launcher-side file and restoration were controls; no close ran. This is not
evidence that every unavailable old writer blocks inspection. It establishes
that the baseline can make an operational facility's availability block a
view. The decided status separation already addresses much of that problem.
API action construction can also deploy manager code; session immutability
must not be inflated into an unqualified whole-host read-only claim.

The accepted direction protects supported evidence interpretation across
writers, not blanket Python operational compatibility. A bounded legacy reader
is justified where a named consumer needs to inspect old custody; the Rust
status acceptance corpus alone does not justify a permanent public promise
to understand every Python session/resource arrangement. Retained reports and
evidence packages already provide a distinct boundary for completed products
(`handoff.py:1-8`). A transition-only need can be met outside the successor's
ordinary operating surface. CONTRACTS.md now records that scope and explicitly
replaces the unconditional legacy-reader commitment, including resource
reporting. The Rust status sequence retains the corpus as comparison evidence,
without making it a permanent public compatibility promise.

Work needed before admitting a narrower reader:

- Name the consumer, supported record population and claims it needs: evidence
  inspection, transition diagnosis or current custody status. Separate these
  from offers to operate the old writer and from any export/import authority.
- Map those claims to verified bytes, identities and attributed records without
  old resource eligibility or live-workspace assumptions. Preserve historical
  bytes and diagnostics; no schema repair, replay or implicit execution follows.
- Specify exact support and refusal boundaries. Unknown schemas stay unknown;
  invalid or missing evidence is not normalized into a successful history.
- Qualify with a known-good supported capture, corrupted selected bytes that
  invalidate the relevant claim, an unavailable old executable or retired live
  environment with the selected captured evidence unchanged, unrelated live
  changes, and distinct collection identities containing equal report bytes. Confirm
  unchanged custody records and no old-code execution. Reuse existing status
  evidence where it actually establishes the property; do not repeat it merely
  to rename the same behavior.

No universal migration format or new operational service is required by this
decision. A narrow reader may fit the custody core directly; carrying the old
operational model requires a separate justification. Exact reader scope and
placement remain design work; status is still first, with its implementation
scope to be made concrete before commissioning it. Cross-writer export is
still separately deferred.

**Where the seven resource questions stand.** The reader and transition
decisions resolve those branches of 7 without settling all storage mechanics.

| Item | Current disposition | Work still needed |
| --- | --- | --- |
| 1. Manager-workspace service | Deferred, with a lean toward isolation/removal | Separate its old obligations at transition; audit allocation remains. Broader workspace/history choices remain outside this resource decision. |
| 2. Sharing and placement | Strong preference for shared immutable material | Choose shared-use lifetime and the last-use rule; qualify access, cost and cross-audit retirement. |
| 3. Held capture and environment retirement | Provisionally resolved | Specify and qualify the capture identity/dependencies that survive environment retirement; final close waits for release and the other conditions. |
| 4. Access exclusion | Pursue explicit grants; prefer no private-location inventory; fallback judgment delegated | Qualify real access boundaries and retain only an evidence-justified fallback. |
| 5. Handoff and cleanup authority | Agreed separation of audit custody from independent manager work; restricted manager live access | Define permitted interfaces and qualify handoff, stop/capture and retirement under that boundary. |
| 6. Holds | Narrow attributed hold with explicit release over a finite identified selection and dependencies needed for its custody claims | Specify identity representation and copy/transfer treatment; references do not recursively expand the hold and no investigative authority follows. |
| 7. Containment, recovery and transition | Bounded transition accepted; reader scope narrowed; no dangling operations after close | Choose ownership/shared-store lifetime, then qualify interrupted operations and competing uses. |

The user accepted the subject rule for 6 on 2026-10-25: a finite explicit
selection plus the metadata and captured dependencies required for the claims
Stewart undertakes. A report alone may remain readable while losing the receipt
needed to verify its custody; following every reference would instead create
recursive preservation. Missing material remains a stated limit, and copying
cannot silently substitute or discharge the held subject. CONTRACTS.md records
the accepted rule; representation and copy/transfer mechanics remain open.

**2/7: retention for live testing, not just reuse.** The user did not settle
post-use caching. They identified two prospective failures: a manager who
thinks an audit is done but has missed extracting material and tries to work
around Stewart to retrieve it; and Stewart silently destroying or withholding
information whose absence goes unnoticed because the test retained no witness.
These are design concerns, not observed successor failures. They challenge
the coordinator's earlier no-independent-cache lean on grounds other than
storage efficiency. The production last-use and cache policy remains open.

The coordinator now recommends preserving an independent, immutable test
archive around bounded live runs before judging that policy. Each archive
would identify the run, audit/collection and observed bytes, with explicit
retirement after its diagnostic purpose is served. It would not serve as the
latest truth, refresh itself from mutable work, automatically resume an audit,
or enter ordinary manager grants. Immutable identities remove freshness
ambiguity; storage cost and safe archive retirement still need an explicit
bounded arrangement. Existing development evidence-retention rules govern
test artifacts; this proposal does not add a production eviction service.
An apparently passing run can conceal an omission, so keep its witness and
controls through review using the evidence-run retention provisions rather
than letting default passing-case reduction erase them.

Backing up only Stewart's normal capture would miss omissions in that capture.
The comparison needs independently observed audit-owned material before deletion
as well as Stewart's captures, manager-visible offers/results and published
outputs. The witness scope, timing and any movement must be recorded; it is
not an omniscient record of everything ever produced. Keep it outside the
disposal being tested so real close can still remove its judged inventory.
Do not use an audit hold to prevent the closure under examination. Recovery
from the test archive preserves diagnostic evidence but does not turn a failed
product extraction into a successful test or authorize continued investigation.

This is a proposed development arrangement, not an approved production cache,
post-close recovery promise or implemented test harness. If later evidence
supports a manager-facing recovery window, its retained material, access and
final disposal must be decided explicitly against close's current end-of-custody
meaning and the hold test. Another audit's legitimate shared use remains
protected throughout; completed close must not conceal unfinished operations.

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
  scope), pinned by the prompt digest and readable by the
  auditor. An absent grant means the facility is not constructed. A grant
  never refuses preparation, as an assignment's external sources do not. The
  session records what was constructed, in the "constructed, not observed"
  wording the network grant uses. Nobody may rely on a withheld facility
  being unavailable: under the manual and sub-agent styles, and for a human
  auditor, nothing stops the auditor reading the subject repository directly.
  The dedicated experiment grant is removed from this proposal by the A.2
  decision. Describing permitted auditor tool use remains possible without a
  Stewart executor; D's field design and actual enforcement are still open.
- **Capture policy: decline.** Narrowing what collection captures breaks raw
  capture before interpretation, the process promise to the auditor, and is
  the reason segregation at capture was declined with the right to receive;
  the only form of exclusion is a category declared disposable in advance
  whose identity close freezes, as the legacy experiment HOME was. The
  successor no longer creates that HOME; no disposable category transfers to
  other audit material. Widening, the
  proposal's "designated evidence", needs no policy: the return area
  captures whatever the auditor writes there.
- **Retention promise: proposed decline needs a revised justification.** The
  earlier argument equated a voluntarily recorded preservation undertaking
  with mandatory retention before every close. The accepted narrow hold shows
  why that equivalence is insufficient: a chosen obligation can constrain
  disposal without imposing universal retention. D remains undecided. Establish
  what the proposed commission promise adds beyond the hold and completed
  retention/export, then judge that specific responsibility. This does not
  approve a new promise or reopen the decline of universal mandatory retention.

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
     may. This remains a frozen-baseline discrepancy; after A.2 there is no
     successor program runner to port or accommodate in its description.

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
