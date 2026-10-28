# Held-back questions, reservations and confusions, with radical alternatives

**What this is.** During three alignment turns on 2026-10-28 (Stewart's mission
and design; the path to the WSL MVP; the coordinator role) you asked me to keep
my caveats out of the chat. This file collects them. Items 1–36 are copied
verbatim from the working notes I wrote during each turn, with their original
numbering and section headings, so you can see what I was holding back at the
time I held it. Items 37–38 were added while collecting. Nothing here is a
decision or a commission.

**What kind of item each is.** The copied text doesn't label them, so here is a
key:

- *Questions that need your view:* 2, 3, 4, 5, 7, 9, 12, 19, 23, 35, 37, 38.
- *Confusions, where I don't understand the intent:* 1, 3, 12, 37, 38.
- *Reservations, where my description sounded more settled than the record:*
  4, 5, 6, 8, 10, 11, 13, 15, 17, 18, 20, 21.
- *Planning and practice concerns:* 14, 16, 22, 24–34, 36.

**The conclusion** sets out radical alternatives: each gives up something I have
inferred matters to you, and names which items above it would dissolve. They are
there to be read, not adopted.

## About the mission/design/custody/MVP description

1. **README's mission vs the successor framing.** README still describes the
   Python workflow (maintainer checkout, auditor checkout, five stages). The
   description given ("Stewart holds copies, never originals"; the auditor's space
   holds only the selected material) is the successor direction. Whether the
   auditor's space is populated from verified commission copies or from a Git
   checkout is not decided (W04 workspace/history, W06 Git materialization).
2. **History and tooling in the auditor's space.** "Only that material" may starve
   questions that need Git history, builds or tests. CONTRACTS records the
   effectiveness-vs-seamlessness tension; W04 is open. The MVP description glossed it.
3. **Human auditors.** I said "sometimes a person". The provisional answer structure
   explicitly excludes a human auditor's manual equivalent in the first leg, while
   PLAN-FIT's outline says human-auditor accommodation is decided, not optional.
   The MVP needs a stated human-auditor path or an explicit exclusion.
4. **Delivery mechanics were presented as settled.** Item 3 is open: push vs pull,
   destination binding (C's request has no destination field), CONTRACTS' older
   "Delivery: Deferred" clause still unreconciled. "Manifest first at seal" is the
   agreed starting point, not the finished design.
5. **Containment mechanism is unselected and unprobed.** "The auditor changes
   custody only through a tool holding authority it lacks" has no qualified route.
   Route research: the host Claude Code sandbox has no per-command filesystem grant
   (only excluded commands with full access, or unsandboxed MCP/hooks); Read/Edit
   are outside the Bash sandbox. A container route needs a host-side process that
   holds custody authority, which is a small running service; tension with "less
   runtime machinery" and with the no-new-service leanings needs the user's view.
6. **Apple `container` does not exist on WSL/Linux.** Whatever enclosure the MVP
   uses must have a Linux (and WSL) realization: namespaces/bubblewrap, podman or
   Docker, or Claude Code's Linux sandbox (unqualified, per linux-check-01). Two
   enclosure implementations (macOS and Linux) may be the real cost.
7. **"Starts the auditor."** Launch/control (W08) has no qualified route. On the
   friend's machine a real agent auditor means their own Claude account and usage;
   scripted participants exercise Stewart's mechanics but qualify neither agent
   behavior nor enforcement on WSL.
8. **Close "removes what it set up."** F6 close is largely undesigned in the
   successor: verified stopping, graceless exit, descendants, holds (W10), damaged
   custody (the narrowed destroyed/tampered policy), the closing record's removal
   authority, descriptor-pinned removal. "Close from any state" is a strong user
   preference the user called hard to effect.
9. **Holds were omitted from the MVP description.** Decided in CONTRACTS; W10 says
   removal depends on them at F6. Probably in the MVP.
10. **Manager-side restriction has the same keyhole problem.** On a single-user
    machine the manager's shell can read the custody home. Mechanism undecided.
11. **Custody home "tied to the repository."** Exact location, move/backup
    behavior and protection are open; on WSL, repositories under `/mnt/c` (drvfs/9p,
    per-directory case sensitivity, NTFS permissions) differ sharply from ext4.
12. **Question types in the successor.** I said Stewart's influence lives in
    question types, but the successor has no question-type design yet; C's request
    and the auditor-facing "no question type shown" decision don't define them.
13. **Interrupted-operation notice** reaching a real auditor needs real-harness
    evidence; records alone don't establish it.
14. **Q26** (which informational notes are neutral) is open; signs are acceptance
    criteria, so it affects the auditor tool's wording.
15. **Arbitrary bounds** (256 elements, 64 MiB, 256 MiB, 1 GiB) are placeholders.
16. **Python legacy.** "No Python needed" is true for the friend, but before Rust
    closes anything the live Python population must be inventoried and closed under
    Python (W17), with independent legacy undertakings settled.

## About the sequence to the MVP

17. **Real agent sessions in the route probe and later trials** need explicit
    bounded launch permission and usage headroom; I described them as if available.
18. **Foundation before route.** The custody home location and the tool's
    two-halves split may depend on the route (custody outside every mount and
    sandbox write root). I judged the foundation route-independent enough to start;
    that is a bet, mitigated by making location explicit configuration.
19. **Populating the auditor space from commission copies** is my inference from
    "manager gives Stewart copies" plus C's verified bundle. It simplifies access
    and absence a lot, but it is a W04 decision with investigative consequences.
20. **Stop/control (W08) may be the largest unknown** after access: process trees,
    graceless exit, human-run launches, the container stop gaps the verifier found
    (stop may leave a VM running; failed relay stop skips the guest-wide kill).
21. **Close is the riskiest stage** (removal) and needs the independent-witness
    discipline; scheduling it last is per plan, but its design pass should start
    while C/D/E are built so records carry what close needs.
22. **WSL return is external and unscheduled;** a failure there loops back through
    fixes and a second handoff.
23. **Cross-compilation/packaging:** building an x86_64 Linux binary from an arm64
    Mac (Rosetta amd64 container or a cross target), or asking the friend to build
    from source with a pinned toolchain offline. Undecided.
24. **Register coverage.** The stage list does not yet map every W01–W20 item to a
    stage or explicit deferral (W01 answer coverage, W03 architecture, W13 helpers,
    W15/W16 trust corrections, W18 docs, W19 crate layout). F7 needs that map.
25. **Failure-table sanity check** (and optional Riker consultation) is meant to
    precede fixing the write protocol; I placed it alongside stage C's start.
26. **Capacity.** ~10 simultaneous agents; much of B and F is single-owner serial
    work, so parallelism concentrates in A, C/D and G.
27. **Frozen Python bytes** stay unchanged while Python is the comparison baseline;
    the successor crate's growth and eventual packaging/naming (`stewart` binary vs
    the Python `stewart` package) need a transition decision.

## About the coordinator role (third alignment turn)

28. **The current account has become a chronicle.** 920 lines, most of it
    narratives of completed commissions with their counts and handles. VISION asks
    to update the account after integration rather than accumulate checkpoints;
    successive tenures prepended a new checkpoint and kept the rest. Intake cost
    grows with every tenure, and replacement is roughly daily (turnover or intake
    commits on 10-24, 10-25, 10-26 twice, 10-27 twice, 10-28 twice). Git already
    holds the history; the account could be current state plus routes.
29. **Guidance ratchets.** Coordinators may change standing procedure within
    delegated authority, with stated basis, but nothing asks them to prune. Each
    tenure tends to add a clause. A periodic consolidation pass would keep the
    layers cheap to consume.
30. **Register.** The coordination documents are written in a dense, abstract
    register ("undertaking", "qualification", "disposition", "bounded"). It is
    precise but expensive for a fresh coordinator and for the user, and it leaks
    into conversation; the user had to say this alignment pass was about the app,
    not the development process.
31. **Ceremony per change.** VALIDATION/COMPLETION JSON for a four-file doc edit
    is heavy relative to what it protects. Proportion the recording to the risk.
32. **Retired work folders linger.** coordination/ holds 19 entries, most of them
    completed commissions whose records the README says to retire once disposed.
33. **"Confirm the old writer stopped"** cannot be checked mechanically across
    sessions in this harness; it rests on the user's word and on file state.
34. **Verbatim user context has no defined home.** The last brief carried the
    user's own words because nowhere else was designated; I moved them to PLAN-FIT.
    Conversation nuance is the thing most easily lost at replacement.
35. **No guidance on when a coordinator should propose its own replacement**
    (heavy context, after compaction, at a stage boundary). The user directs
    transfer; the coordinator could usefully signal good points for it.
36. **My own footing.** Everything I know about items 1 and 3 and the user's
    intentions comes from files and this conversation; derived understanding can
    sound more settled than it is. The alignment turns are the check on that.

## Added while collecting

37. **Who the WSL friend is, in product terms.** If they are a Stewart user, the
    guide and the handoff must serve them (CLAUDE.md: documents for Stewart's users
    serve them, not the proxy). If they are a tester running our driver, the
    package is a test kit. These produce different handoffs.
38. **"How many Stewart auditors trials use."** I don't know whether this means
    how many run at once, how many sessions in total, or how many per trial
    situation. It matters for usage headroom and for what the probe can show.

## Conclusion: radical alternatives

Each of these gives up something I have inferred matters to you. Radical here
means giving that up, not doing harm. I am not recommending any of them. Each
says what is given up, what Stewart would do instead, and which items above it
dissolves. They run roughly from the largest effect on the MVP to the smallest.
Several combine; the last entry shows the thinnest combination.

### R1. Give up enforced containment; detect instead of prevent

**Gives up:** absence enforced by the arrangement, the keyhole as a mechanism,
and qualifying access against unselected and neighboring material.

**Instead:** Stewart builds a clean space holding only the selected material and
keeps custody somewhere ordinary but out of the way. It makes no attempt to stop
an auditor from reaching elsewhere. Custody is protected by verification: every
element is hashed and recorded when added, membership is kept twice, and the
return carries its manifest. Tampering becomes a detected, reported gap rather
than a prevented act. An escape becomes something the return cannot rule out,
which is already true of any audit.

**Dissolves:** 5, 6, 10, 18 and most of 17; most of stage A; one implementation
for every platform.

### R2. Give up the auditor's shell

**Gives up:** the auditor's latitude to run code, builds, tests and arbitrary
tools ("permitted auditor tool use remains").

**Instead:** the auditor is an agent whose only tools are Stewart's: list and read
supplied materials, then add, replace, delete, inspect, prepare and submit. That
means a harness configured with Stewart's tools alone, or a minimal agent loop
Stewart drives itself. Absence is total by construction, because nothing exists
outside the tool surface. Containment needs no container.

**Dissolves:** 5, 6, 10, 13, 17 and 20, and item 2 by declining it. The access
question becomes a question about the tool surface.

### R3. Stewart never deletes anything

**Gives up:** Stewart retiring what it sets up, a close that cleans everything,
and the closing record as removal authority.

**Instead:** close seals the audit and ends custody in the records. The auditor's
space is ephemeral (a container or temporary directory that disappears on its own)
or the manager deletes it like any folder. Custody stays until the manager deletes
the audit's directory. Holds become unnecessary, because nothing Stewart does
destroys anything.

**Dissolves:** 8, 9 and 21, the removal half of stage F, much of 16's legacy
removal claims, and W10/W14 removal work.

### R4. Stewart neither launches nor stops the auditor

**Gives up:** binding the audit to its running execution, "starts the auditor" in
the MVP, and evidence of stopping.

**Instead:** Stewart prepares the space and prints how to start an auditor in it,
and the manager runs it. Collect already freezes the answer whether or not
anything is still running, so ending authoring needs no stop. Close makes no
claim about processes.

**Dissolves:** 7 and 20, and the lifetime half of stage E.

### R5. Give up the authoring tool and snapshot a folder

**Gives up:** custody beginning during authoring, atomic add/replace/delete,
interrupted-operation accounting, prepare/submit handles and most of the signs.
This reverses decisions you made on 2026-10-27 and 2026-10-28. It is listed
because it is the largest single body of work in the plan.

**Instead:** the auditor writes files into an answer folder however it likes.
Submit (or collect) copies and hashes that folder once, and that copy is the
return. Nothing is Stewart's until then.

**Dissolves:** 13, 14 and Q10, most of 15, and nearly all of stage C. Interruption
stops being a topic for the auditor.

### R6. Stewart runs only inside Linux

**Gives up:** native macOS and native WSL operation, and working directly on
material in the host filesystem.

**Instead:** Stewart ships as a Linux image. On macOS it runs under Apple
`container`; on Windows it runs inside WSL2's own ext4. Material is copied in and
the return copied out. There is one filesystem behavior, one pinned Git version
and one enclosure.

**Dissolves:** 6, 11 and 23, the name-normalization part of 2, and most of the
platform matrix in stages G and H.

### R7. Give up Git

**Gives up:** "material held in Git": history, submodules, worktrees, the Git
environment document and the Git trust corrections.

**Instead:** a commission is a question plus a list of files, which is how the
commission tool already works. If a question needs history, the manager exports
what is needed as files.

**Dissolves:** 1, 2 and 19, the minimum-Git question, and the W04, W06, W15 and
W16 parts of 24.

### R8. Drop the Python baseline and legacy settlement now

**Gives up:** Python as the comparison control, closing live Python audits under
Python, and interpreting legacy records.

**Instead:** remove the Python runtime from the active tree (Git keeps it).
Any live Python audits become the manager's to finish or abandon by hand. Stop
comparing against Python.

**Dissolves:** 16 and 27, the legacy part of stage F, and W17.

### R9. Give up question types

**Gives up:** the question types learned through real audits and the bundled
recipes.

**Instead:** there is one kind of commission, question text plus materials.
Stewart's only intellectual influence is the space it gives the auditor.

**Dissolves:** 12.

### R10. Make the destination the custody

**Gives up:** the restriction on the manager seeing live authoring, custody kept
separate from delivery, and delivery as a verified copy.

**Instead:** every successful add writes straight into the manager's destination
folder, append-only and hashed. Submission seals there. Delivery and close have
nothing left to do.

**Dissolves:** 4, 10 and 11, and most of stage D. (This conflicts with R5; with
R5, the snapshot goes straight to the destination instead.)

### R11. Give up coordinator continuity

**Gives up:** one coordinator owning the result across sessions, together with
the current account, standing orders and turnover.

**Instead:** every session starts from CONTRACTS, the plan and the code. The plan
is the only account, and a session ends by updating it. Replacement costs nothing
because there is nothing to hand over.

**Dissolves:** 28–35.

### R12. Give up inquiry-first development and evidence ceremony

**Gives up:** studies and pilots before building, independent review by default,
and retained run records with firing, differing and invariance controls for each
claim.

**Instead:** build straight from CONTRACTS to the MVP. The repository's tests are
the evidence. Review only where something deletes material or crosses a trust
boundary. Accept rework.

**Dissolves:** 24, 26, 31 and 32, most of stage A's probing and much of stage G's
qualification.

### The thinnest combination

R1 + R3 + R4 + R5 + R7, with the snapshot going straight to the destination.
Stewart becomes a notary. It takes a question and files and issues a receipt. It
sets up a folder of copies. Later it snapshots an answer folder into the manager's
destination with a manifest and provenance. Everything else is the manager's.
That is roughly the existing commission tool plus one more command.

## Maintainer comment, 2026-10-28

> OOOOOhhhhh..... Ok. This is excellent. I want to talk about some of these
> alternatives. R8 I basically agree with full stop. R7 has been BOTHERING me. R6
> is perfectly pleasing. I don't want this to be a mac tool I want it to run on
> Linux. R9 is a "kill your darlings situation" so I want to hear about it but
> expect resistance. R3/4/5 seem like they could go together, as you note. R2 I
> want 100%. R1 I want to hear a pitch. That's a sweeping response. Please collect
> that into a maintainer comment as a quote THEN immediately append your
> interpretation of what I want. Then return to me to discuss the confluence of
> what I just said looks dandy.

### Coordinator's interpretation

This is direction for discussion, not yet decisions recorded in CONTRACTS; you
said you want to talk these through.

- **R2, adopt.** The auditor has no shell and no general file tools; its only
  tools are Stewart's. Containing the auditor becomes a question about Stewart's
  tool surface and the harness configuration that leaves only those tools.
- **R8, adopt.** Drop Python as the comparison baseline and as legacy: no
  comparison control, no requirement to close Python audits under Python, no
  legacy interpretation. "Basically" leaves room for details, such as the
  Python-specific rules in CLAUDE.md and what happens to any live Python audit.
- **R6, adopt.** Stewart is a Linux tool. macOS is served by running it inside
  Linux (a container), and WSL by WSL2 itself. Native macOS support is not a goal.
- **R7, strong lean; examine it.** Depending on Git has bothered you. You want the
  case for a commission being a question plus files, with what is lost (history,
  submodules, the Git environment document) laid out.
- **R3/R4/R5, interested as a bundle; not adopted.** You see them going together
  and want to discuss them as one. R5 reverses your own recent authoring
  decisions, and your interest suggests those are open to revision if the bundle
  earns it.
- **R1, pitch it.** Argue for detection over prevention.
- **R9, argue it fairly; you expect to resist.** Question types are a darling; you
  want a real hearing, not a recommendation to rubber-stamp.
- **Overall.** You are willing to make Stewart much smaller and to give up
  commitments made in the last few days if the result is coherent. You want to see
  how these choices fit together before going deeper on any one of them.
