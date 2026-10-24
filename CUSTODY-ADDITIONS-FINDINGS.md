# Custody additions: stage-3 first-wave account

Status: first wave complete. Four source investigations ran under the stage-3
commission of 2026-10-24; independent review of this integrated account is
recorded at the end. Everything here is a recommendation for the user's
decision, not a decision. No production code, test or comparison ran; Python
remains the frozen reference baseline at `6582df2`. `DEVELOPMENT-PLAN.md` owns
the commission and sequence; `CONTRACTS.md` owns decided behavior.

Each investigation wrote a full account with file:line anchors under
`.scratch/custody-additions/` (working material, untracked, about 2,200 lines
in all). This document carries what a decision needs. Anchors marked
*verified* were re-read by the coordinator at the frozen baseline; the rest are
as the investigations reported them, checked by the independent review.

## Recommendations at a glance

Vocabulary: **accept** as stated; **narrow** to a smaller responsibility
stated here; **decline** with the reason a later coordinator should read;
**defer** with the dependency named. Declining is a valid outcome.

| Candidate | Recommendation | Reason in one line |
| --- | --- | --- |
| Submodules (i): readable pinned code | Accept, narrowed | Preparation materializes the pinned tree as its own pinned copies, one level, local objects only, no Git administration created; an effectful step whose costs are stated below |
| Submodules (ii): work inside populated submodules | Decline | A second Git administration per gitlink, inside an area Git documents as unsupported for linked worktrees; an experiment grant over (i) serves path-based checks |
| Return arrangement declared by the manager | Accept, narrowed | Attributed free text under coordination; no time, outcome or current field; never paired with absence as attention |
| Auditor-attributed acceptance of the commission | Decline | No auditor channel reaches Stewart before collection; the `start` skeleton is already the earliest auditor artifact |
| Structured return beyond collect | Narrow | An optional stop note on collect; name the existing two-way structured reply; defer delivery with its dependency stated |
| Human auditor as first-class participant | Narrow | Make the handoff complete without the helpers; no further standing; a capture receipt the auditor could see is deferred to the successor's status rendering |
| External retrieval A1: record named sources beside the constructed grant | Accept, narrowed | A neutral recorded limit, never a refusal, when an assignment names sources the launch style constructs no route to; wording says constructed, not observed |
| External retrieval A2: adapter constructs allowed domains from the assignment | Defer | Needs a real-harness network qualification first |
| External retrieval A3: Stewart fetches and pins bytes | Decline | Supplemental inputs already carry retrieved bytes with attributed provenance |
| System-project experiments B1: the reviewed shim route | Accept, narrowed | State the shim as the supported route with the command literal in the frozen script, so byte review is command review |
| System-project experiments B3: a command experiment kind | Decline | Drops membership review and the firing control; makes HEAD plus an unpinned toolchain the executed identity |
| Provider conditions and delegation limits | Accept, narrowed | An attributed, blocking-only hold on a recorded resource, honored exactly as a live use, released only by an attributed record |
| A right to receive distinct from the commission | Decline | The manager owns the workspace and the disk the report is written to; segregation at capture would break raw capture before interpretation |

## Submodules

**What exists.** Preparation detects gitlinks and requires acknowledgment; it
does not populate them. Committed files below a gitlink are refused as inputs
(`assignment.py:163–165`). Collection's walk lists nested `.git` *files* and
skips nested `.git` *directories* (`collect.py:213–216`, verified), so an
absorbed-form populated submodule would be captured file by file, pointer
included, and could conclude after triage, while an old-form one is a boundary
that blocks conclusion; the capture half is a prediction (Q3 below), the
boundary half is source, and the manual states only the directory case. Nothing parses `.gitmodules`, so
the submodule name needed to locate `modules/<name>` is unknown to Stewart.
The auditor's read grant covers the whole Git common directory except
`common/stewart` and the role markers (`auditor_scope.py:85–88,103`;
`_repository.py:158–175,355–368`), so the constructed scope grants the auditor
read access to a maintainer's absorbed submodule object store and to other
sessions' worktree administration, recorded nowhere; only that scope's
precedence rule is harness-qualified. Close
removes each own worktree administration recursively (`close.py:498`,
`_removal.py:81–99`); if Git places a submodule administration initialized in
the linked worktree under that administration, close would remove it with no
record naming it. That placement is predicted from documentation, not
executed. Git's own documentation declares multiple checkouts of a
superproject with submodules unsupported; Stewart's auditor checkout is one.

**(i) Readable pinned code, narrowed.** Preparation materializes the
gitlink's pinned tree as plain files below the gitlink path, as preparation's
own pinned copies: per-file digests, commit, tree and source recorded in the
session record; one level only; objects taken only from the maintainer
checkout's own submodule administration; no network; no Git administration
created; a changed copy is a verification failure like a changed supplemental.
This is an effectful preparation step, not a text change: preparation reads a
second object store, writes files into the checkout, needs Stewart's first
`.gitmodules` parser (nothing in the source reads that file today), and adds a
refusal. It touches one assignment field, the session record, the handoff
text, the expected-output rule at `collect.py:351–367`, the remedy text and
the status limit. It also touches close: at abandon without a collection the
uncollected check exempts only handoff and supplemental pins
(`close.py:839–842`, `coverage.py:79–86`), materialized files lie below a
gitlink where the prompt commit never holds them, so abandon would refuse
`uncollected_changes` unless the copies are accounted for, and extending the
pin-only exemption is what finding 1 below calls unsound; the sound form checks
that the maintainer's submodule administration still holds the objects the
copies duplicate. The decided gitlink-input contract needs one added clause,
that nothing else may be supplied below a gitlink, materialized or not. Every
collection archives the whole materialized tree, a per-collection cost
proportional to the submodule. The investigation calls the second-store read
the one new commitment, small but real. A zero-contract version exists today:
a generator that emits an inputs manifest at an ordinary path. Reliance: an
auditor may rely on the pinned copies being the submodule's pinned revision;
nobody may rely on them being a Git checkout or on recursive submodules being
present.

**(ii) Work inside populated submodules, declined.** It would make Stewart
create, verify, configure, inventory and dispose of a second Git
administration per gitlink, extend coverage, declarations and the closing
schema, and decide the fate of auditor commits, in the area git-worktree's own
documentation calls incomplete for superprojects. (i) plus an ordinary
experiment grant already serves path-based checks and captured edits. The
residual, Git-aware tooling inside a submodule, is a fresh candidate gated on
the comparisons below. Old sessions need no treatment beyond the existing
rules; gap computation must stay keyed to the receipt schema so old
collections keep displaying the gaps they recorded.

**Open questions.** Q1 where a submodule administration initialized in the
auditor worktree lands, and whether close removes it unrecorded. Q2 whether
maintainer `submodule.recurse=true` makes `worktree add` populate gitlinks.
Q3 what collection records for a populated absorbed submodule, clean and
modified. Q4 whether `submodule.<name>.ignore=all` hides a dirty submodule
from Git while the walk still archives it. Q5 which object-transfer route
executes configured commands from the source repository; only the `cat-file`
arm matters for (i). Q6 whether `git status` inside a write-denied submodule
administration answers correctly under the real harness. Q7 whether
`git submodule update --init` over a local path is refused by default.

## Delivery, return route and the human auditor

**What exists.** Before `collect`, nothing the auditor does reaches Stewart.
The issued helpers write only the report path
(`report_declaration.py:451–481,503–535`; `_bootstrap.py:741–747`); the scope
denies session reads and all common-directory writes
(`auditor_scope.py:85–88,101–105`); the session is mode 0700
(`prepare.py:246`); auditor bytes are read once, at collection, after the
manager's stop claim (`collect.py:423–468`). A message recorded as from the
auditor is a manager mutation and authenticates nothing
(`coordination.py:150,162`). The `start` declaration skeleton is already the
earliest auditor-attributed artifact, and it too is seen only at collection.
Triage's kind-bound follow-up is already the manager's structured reply to the
auditor's hand-back, and it never leaves private custody
(`triage.py:45–46`). The human-ferry entry point is host-bound in two places
the manual does not say: the helper argv names the manager process's own
interpreter (`prepare.py:207`; `_invocation.py:66`), and the launch block's
trailer appends into the private session and converts an unwritable log into
exit 1 (`launch_profile.py:205–207`, verified; `prepare.py:341–343`). The
investigation predicts, without executing it, that a ferried command run by
another user or host reports a failed launch that may have succeeded and leaves
no exit line; that is one of the comparisons below. A human can write a valid
declaration by hand, but every gap remedy presumes the helper and the fence
rules make a paste fragile.

**(a) Manager-declared return arrangement, narrowed.** Attributed free text
bound to the session, as a launch-record field or an append-only record if
arrangements get revised, listed under status `coordination`. No time, outcome
or current field; never paired with an absent collection as attention. It
describes how the manager expects the return, not who is entitled to receive
it, and establishes no delivery, watcher or callback duty.

**(b) Auditor-attributed acceptance, declined.** The checkout form adds one
word to what `start`, `blocked`, `needs-evidence` and `reframe` already say. A
session channel would change the auditor scope and the no-live-read decision
to produce exactly the activity signal the status contract refuses to infer.

**(c) Structured return beyond collect, narrowed.** Accept an optional stop
note on `collect`, the basis of the stop acknowledgment, mirroring the pause
note. Name in the contracts what already exists: the auditor's structured return is
the collection-bound captured report with its declaration, and the manager's
disposition with its kind-bound follow-up is a structured reply that never
leaves private custody. Neither statement implies the reply reaches the
auditor. Defer
delivery with its dependency stated, a receiving endpoint and real-harness
evidence, rather than placing it outside Stewart.

**(d) Human auditor, narrowed.** Make the handoff complete without the
helpers: a pasteable declaration block, manual remedies, and labels on the
host-bound parts. Decline any further standing: no channel, notification,
retention right or role transfer. One sub-item is deferred rather than
declined: a read-only projection or capture receipt an auditor could see,
confirming that their return was captured raw. It serves Stewart's first
process promise to a human auditor and is decidable with the successor's
status rendering.

**Open questions.** Does the rendered launch block misreport a ferried launch
(stub harness exiting 0, writable versus unwritable session log)? Does a
hand-written declaration collect cleanly (pasted block, CRLF variant, wrong
HEAD value)? Is `start` a sufficient captured acceptance (collections after
`start` only, report without block, no report)? Can status prose carry an
arrangement line without reading as a task? Whether any harness emits a return
signal recordable without a watcher needs a real harness and is why delivery
is deferred rather than designed.

**A gap in the decided record.** The status contract's "Participants and
entry points" table was not among the sections incorporated into
`CONTRACTS.md`. If (a) or (d) is adopted, the table comes in with them; it is
the fullest tracked statement of those four relationship distinctions, which
otherwise survive only partially in the contracts once the stage-1 findings
retire.

## External retrieval and system-project experiments

**What exists.** An assignment's external sources are validated as public
HTTPS URLs with a purpose and can alone satisfy the has-inputs rule
(`assignment.py:108–122,141–142`, verified), and then nothing consumes them:
the rendered handoff never mentions them, the declaration has no sources
field, and the only other reader re-authors init arguments. The adapter
hardcodes an empty allowed-domain list and excludes web tools
(`auditor_scope.py:106`, verified; `:143–145`); the network setting is an
adapter constant, not a scope field. The manual and sub-agent launch styles
construct nothing, so for a sub-agent the gap does not exist and neither does
any boundary. The experiment's "minimal" environment is the manager's PATH
verbatim, with its policy and worktree parameters unused
(`experiment.py:196–201`, verified); the child runs in the manager's process
context with no sandbox and no network construction. The auditor is
constructed offline; what it builds and the manager runs is online and
unobserved. Project commands already run today through a released Python
script that calls a subprocess; nothing refuses it, the protocol anticipates
it, and the ledger records only declare, reach, admit and compare. Build
residue inside the worktree becomes unexpected paths and gaps, all archived;
writes outside the worktree are unobserved except HOME. A permitted domain
would have a confidentiality consequence: the auditor's read grant includes
the whole Git object store, so readable becomes transmissible.

**A1, accepted narrowly.** Record the hostnames the assignment names beside
the network grant the adapter constructs; tell the auditor both in the
handoff; never refuse. The investigation proposed an attention item when an
assignment names sources the launch style constructs no route to; under the
status contract attention is a coded exceptional condition with exit 1, and an
offline construction is the ordinary, documented case, so the coordinator
narrows this to a neutral recorded limit, treated as recorded gitlinks are,
and notes that the style is known at prepare only when a profile is pinned.
Wording says constructed, not observed. Reliance: a manager may rely on knowing what was constructed;
nobody may rely on a fetch having been permitted or having happened.

**A2, deferred.** Constructing allowed domains from the assignment waits for a
real-harness network qualification, as the filesystem precedence rule did.

**A3, declined.** Stewart as a network client gains attribution only, at the
cost of a new capability; the supplemental-input route already carries
retrieved bytes with attributed provenance.

**B1, accepted narrowly.** State the reviewed Python shim that runs project
commands through a subprocess as the supported route, with the command literal
in the frozen script so that the manager's byte review is the command review,
the child's command claims in its receipt, controls designed as instrument
discrimination, and the costs stated: the environment is the manager's PATH,
toolchains are unpinned, and residue is archived as gaps. The access-limits
documentation's statement that this route may not serve a project's real
system checks remains true where those checks need an environment the shim
cannot provide; the second wave's build-cost comparison decides whether the
route is proportionate for ordinary projects.

**B3, declined.** A command experiment kind drops membership review and the
firing control and makes the project at HEAD plus an unpinned toolchain the
executed identity. Reopen only on a fielded failure of the shim route that is
not merely a cost.

**Open questions.** Does the qualified harness honor the constructed network
settings (three launches: as constructed, one allowed domain, unsandboxed
control; filesystem settings as invariance)? Does the sub-agent style inherit
the manager's network? Does `start_new_session` with `killpg` contain build
daemons? What does a representative build cost at collection? Which
toolchains break under the attempt environment? Is attribution of retrieval a
real need, which decides whether A3 stays declined?

## Authority and conditions on material

**What exists.** Enrollment already implements the core of a provider
condition: an enrolled resource is never claimed and is `manual` before the
live-use test (`holdings.py:1198–1200`), which the tests establish with
control, differing and invariance cases; by source reading it also blocks a
managed container it sits inside (`:1249–1251`), untested and an open question
below; and its roots are denied to auditors (`:1913–1926`). But the
enrollment note is write-only: recorded (`holdings.py:907`, verified) and read
by nothing in show, summaries, status or close, so a provider's condition typed
today is preserved and invisible at close planning. Supplied files are never
in Stewart's custody; the only copy close removes is the worktree duplicate,
exempted from the uncollected check at abandon on the strength of its pin
alone (`close.py:839–842`, `coverage.py:84–85`, verified) with no check that
the manager's original still exists, and not named among discards. The
right-to-receive question has no purchase: the manager owns the workspace,
chose the target and inputs, the report is written to a path the manager
assigned on the manager's own disk, collect captures it under the manager
repository's common directory, and only the auditor is forbidden to read
session storage. Stewart's who-may-act gates are location and tool identity;
the close actor is a non-empty string. Retain publishes whole report bytes
verified against the receipt, so partial withholding would break byte
identity, and segregation at collect would violate raw capture before
interpretation. Stewart's supplied runtime is its own distribution, so a
third party supplying a runtime maps onto supplemental inputs or enrollment.

**Provider conditions and delegation limits, accepted narrowly.** A
repository-level, attributed, blocking-only hold on any recorded resource,
honored exactly as a live use: never claimed, shown in `close --plan`, show,
closeout and the closing record, released only by an explicit attributed
release record, never by a close flag, a container's retirement or a dispose
option. The record carries the actor, the condition's text and a required
`limit` stating what the hold does and does not do; its wording says "not
destroyed by Stewart", never "returned" or "preserved against the manager",
because Stewart can promise the first and neither of the others. For enrolled
resources this is presentation of a condition enrollment already honors;
nothing else about enrollment changes. For a Stewart-created resource it is a
new commitment, a hold that blocks the manager's own disposal until an
attributed release, and that is exactly the decision this stage asks the user
to make. The supplemental-input and workspace-declaration forms are declined.
It leaves "removal is authorized by two records only" intact, since a hold
grants nothing and is one more reason no claim is created. Veto creep enters
only if release ever required the named provider or a close flag could
acknowledge past a hold; the contract forbids both. The provider is named in a
record and cannot invoke Stewart.

**Right to receive, declined.** Stewart cannot withhold what the manager
reads on its own disk, cannot deliver to anyone else, and would have to
interpret the return at capture to try. The right to receive is settled
outside Stewart by who owns the repository and the checkout home. The only
truthful residue is an auditor-declared claim that the commission does not
authorize receipt of something, which is a declaration-schema question under
the return-route candidate, not a custody responsibility.

**Open questions.** Does abandon destroy the last copy of a supplied file
(delete the original, abandon without a collection; differing case with the
original intact; invariance with a concluded close whose archive holds the
copy)? Is the enrollment note visible anywhere? Does an enrolled resource
nested in a managed directory block retirement? A hold recorded between
evaluation and retirement must release the claim like a new live use and be
refused while a claim is active; that is a design point, not a baseline fact.

## Findings that bear on decided contracts rather than on additions

These came out of the investigations and belong to the close or status
contracts, or to the manual, whatever the user decides about the additions.

1. **Supplied-file copies at abandon.** A pin-matching worktree copy of a
   supplied file is removed on its pin alone, with no check that the original
   it duplicates still exists, and is not named among discards. Under the
   decided principle that a removed surface must duplicate held material or
   be surrendered by name, a copy whose original is absent or differs should
   be treated as uncollected. This needs no condition record. It is a disposal
   check on a pinned input whose duplicate close is about to remove, not the
   declined policing of a published output after publication.
2. **Retain records no actor** (`triage.py` retain, verified) while export and
   every resource-writing operation require one. Publication of the
   deliverable is the least attributed step.
3. **The enrollment note is write-only.** Presentation belongs with the hold
   contract above or on its own.
4. **Nested `.git` files versus directories** decide whether a populated
   submodule is captured or a boundary; the manual states one case.
5. **The auditor's read grant reaches absorbed submodule object stores and
   other sessions' worktree administration.** Recorded nowhere; it is a fact
   about the present access boundary that the access-limits documentation
   should state.
6. **External sources are unconsumed** and the offline construction is not a
   scope field; the handoff is silent about sources the protocol tells the
   auditor to retrieve.
7. **The experiment environment is the manager's PATH** with dead parameters;
   the capability documentation should say so.
8. **The ferry is host-bound** in the helper interpreter path and the launch
   trailer's private-session append; a ferried launch can misreport failure.

## Coherence across candidates

The declines fit together: the auditor's only channel is the return, so there
is no acceptance to record and no right to receive to adjudicate, while the
manager's expectations are attributed text and nothing more. Most narrowed
acceptances add records or text and no new operation with effects: a
return-arrangement line, a stop note, handoff completeness, recorded hostnames
beside a constructed grant, and a stated shim route. Two do more and are
stated as such: pinned submodule copies are an effectful preparation step that
reaches close's abandon exemption, and a hold on a Stewart-created resource is
a new commitment. None lets status infer
activity, delivery or publication, none transfers launch or callback
responsibility, and none creates a party who can invoke Stewart. Submodule
(i) and the hold each require one clause in an already decided contract; the
plan names which.

## Proposed second wave

Before decisions on the narrowed acceptances, these comparisons of baseline
behavior need no harness, network or human and would settle facts the
recommendations rest on: whether abandon destroys the last copy of a supplied
file; what collection records for a populated absorbed submodule, clean,
modified and with `submodule.<name>.ignore=all` (Q3 and Q4, one fixture);
whether maintainer `submodule.recurse=true` makes `worktree add` populate
gitlinks (Q2, a premise of "no Git administration created" and the stage-2
unqualified item); whether a submodule administration initialized in the
auditor worktree is removed by close unrecorded today (the baseline half of
Q1); whether the rendered launch block misreports a ferried launch; whether a
hand-written declaration collects cleanly; whether the enrollment note is
visible anywhere; whether an enrolled resource nested in a managed directory
blocks retirement; and what a representative build costs at collection, which
decides whether the shim route is proportionate. Design points wait for
implementation: where a new administration should land, which object-transfer
route executes configured commands (Q5), daemon containment and toolchain
breakage under the attempt environment. Everything that needs a real harness,
a real fetch or a real human stays out of scope and is the stated dependency
of the deferrals.

## Evidence, review and disposition

Source investigation only; no installed-wheel run and no production change.
The four working accounts under `.scratch/custody-additions/` carry the full
anchors and alternatives.

Independent review of this account, 2026-10-24: a fresh reviewer checked
fidelity to the four investigations, every anchor marked verified and sixteen
more, the reliance tests on each narrowed acceptance and the deferral,
consistency with the contracts, and the second wave. All anchors held and
every recommendation matched its investigation. Seven corrections were made:
submodule (i) is now stated as an effectful preparation step that reaches
close's abandon exemption and carries a per-collection archive cost, rather
than "one clause, close untouched"; the hold carries its `limit` field and
no-return wording, and the managed-resource hold is named as the new
commitment it is; a deferred capture-receipt sub-item is recorded under the
human auditor; the structured-reply sentence no longer implies the disposition
reaches the auditor; four claims stated as fact are marked as predictions or
constructed scope; the second wave carries the comparisons it had dropped; and
A1 is narrowed from an attention item to a neutral recorded limit. Nothing
blocks presenting the account for decision.

The
recommendations await the user's decision; stage 3's exit is a coherent
desired custody arrangement, and this account is its first wave. Accepted
additions become contracts in `CONTRACTS.md` for the Rust implementation;
declines are recorded there with their reasons. After this document has served
its decision purpose, transfer enduring contracts and declines there and retire
it under the plan's rules.
