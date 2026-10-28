# The conversation

The first of three views of one design encounter on 2026-10-28. This is the
conversation as it happened: each of your prompts verbatim, and each of my replies
as I gave it, with its headings moved one level down to fit this document. The
notes I held back during it, the radical alternatives and your
comment on them are in [CONVERSATION-HELD-BACK.md](CONVERSATION-HELD-BACK.md), a
verbatim copy of the working file. That file's paths point to
`.scratch/alignment-20261028-01/`, where the original stays. The encounter began
right after I took over coordination; that intake exchange is omitted here.

---

## 1. Alignment on the app

> Ok. Let's see if we are aligned first. Describe 1: the mission of stewart 2: how
> our proposed design enforces that mission 3: how we characterize our custody of
> materials and containment of the auditor 4: What our MVP looks like that we will
> send to my friend with WSL at the end of this. Leave
> confusions/concerns/caveats about your assessment for a future turn. Note at no
> point did I ask for a disquisition on the development process (coordinators,
> handoffs, etc.) this is about stewart the app.

Here is my understanding of the app.

### 1. Stewart's mission

Stewart lets someone ask a narrow question about material they hold in Git and get
a trustworthy answer back, without having to steer the investigation.

- **The manager** (a person or an agent) commissions the question and gives
  Stewart copies of the material needed to answer it.
- **The auditor** (usually an agent, sometimes a person) investigates and records
  an answer.
- **Stewart is the custodian between them.** It holds what it was given and what
  the auditor produces, keeps the inquiry within its limits, and gives the manager
  a complete, verified, self-contained return. If it can't, it gives an honest
  account of what's missing.

The relationship is a trap door with receipts. You hand over copies, get detailed
receipts right away, and eventually get a result or an error. Stewart is not a
supervision tool, and it doesn't judge whether an answer is good. "No finding",
"the evidence isn't there" and "the question is wrong" are all legitimate
returns. Stewart's influence on the thinking comes only from the kinds of
questions it supports and the space it gives the auditor. Toward material it is
generous in handing it over and cautious about destroying it.

### 2. How the design enforces that, through one audit

- **Commission.** The manager supplies the question, a finite set of material and
  a destination for the return. Stewart copies and verifies the material and
  issues a detailed receipt immediately. A manager who has lost track can recover
  the original question and material from that receipt, without the original
  conversation.
- **The auditor's space.** Access is defined by what was granted: the selected
  material and the tools needed to work with it. Anything not granted is absent,
  not visible-but-refused.
- **Recording an answer.** The auditor builds the answer only through the
  submission tool. An answer is an optional readable account plus ordered
  artifacts. Each artifact is exact bytes with an identity Stewart assigns and a
  name the auditor chooses.
  - Edits are add, replace and delete. Each one is atomic and is held by Stewart
    the moment it succeeds, even if the tool then exits.
  - There are no outcome or kind fields and no required declarations. An empty,
    blocked or reframing answer goes through exactly like a finding.
  - The size limits are stated up front.
- **Submitting.**
  - "Prepare" produces an inspectable manifest and a handle.
  - "Submit" is a dry run unless explicitly confirmed, and confirming seals the
    answer.
  - An edit after "prepare" makes the handle stale, and "submit" then refuses
    rather than silently taking the newer material.
  - If the reply to a submit is lost, repeating it returns the same submission.
- **Signs on every wall.** Every refusal names its reason, says what happened to
  the answer and gives the next step. It never shows where custody lives.
  - Bare help is a slim cheatsheet, and the question is printed word for word when
    asked.
  - An auditor that is still working can find out what happened to an interrupted
    operation.
  - Submitting with an unresolved operation is allowed, with a clear note in the
    reply and in the return.
- **Manager collect.** The manager can end authoring at any time. The answer is
  fixed and marked as collected by the manager, not submitted by the auditor. If a
  submit and a collect race, exactly one wins.
- **Delivery.** At sealing, the sealed manifest goes to the manager's destination
  first. Then the full return follows: the question and instructions, the receipt,
  the manifest, the selected bytes, and the record of how the answer was
  submitted or collected. Stewart verifies the copy.
  - Empty and partial returns use the same path and name their gaps.
  - Unknown contents are never reported as empty.
- **Re-entry.** A manager who has lost track uses help and status. Status takes an
  explicit audit reference and never guesses by recency.
- **Close.** One command closes an audit from any state.
  - In the ordinary case, the manager confirms the copy is safely placed, and
    Stewart ends its custody and removes what it set up.
  - If a known item can't be supplied, the manager can explicitly end that named
    obligation.
  - Close removes only what it evaluated, and never hides an unfinished operation.
- **Refusals are narrow.** Stewart refuses only when proceeding would make a false
  custody claim, require an act it may not perform, or abandon an obligation it
  took on.

### 3. Custody of materials and containment of the auditor

**Custody.** Stewart holds copies, never the originals, from handoff until an
authorized close. Its custody of the answer begins when an add succeeds, not at
submission.
- **What it holds:** the original commission, the recorded answer elements,
  superseded and deleted versions (kept until close), operation records and the
  sealed manifest.
- **Where:** in persistent per-audit storage tied to the repository, outside the
  auditor's disposable workspace. It survives the tool exiting and the workspace
  being torn down.
- **After delivery:** the manager's copy is the manager's responsibility. Close
  ends Stewart's custody, and with it the ability to ask Stewart for another copy.
- **Records:** what was observed, what was acknowledged and what the auditor
  claimed stay in separate, attributed fields, never merged into a verdict.
- **Loss and damage:** a loss is recorded as a loss, and damage blocks only the
  claims that depend on it.

**Containment.** The premise is that managers and auditors are cooperative but
fallible, and that eager, persistent agents make them fallible faster. The
agent's shell can do anything the user can. Containment exists to make normal
operation sturdier and smoother; it is not a security barrier.

The aim is the keyhole you described: the most obvious, easiest and safest thing
to do is the same thing, interacting with Stewart.
- Absence is preferred to refusal, and every wall carries a sign.
- The auditor changes custody only through a tool that holds authority the auditor
  lacks.
- The manager stays out of the auditor's live material and receives the return
  through the supported interface. The manager's own tool fails early and
  informatively.
- An auditor that gets out and draws conclusions from material it wasn't given is
  a design failure, not a breach.
- Containers may be a temporary means. The real goal is to acclimate an agent to
  the auditor role and place it in a space where little besides the material
  needed for the question exists.

### 4. The MVP your friend runs on WSL

The MVP is the Rust Stewart running a whole audit on Linux under WSL, with no
Python Stewart needed:

1. Commission a question with selected material from a Git repository and a
   return destination, and get a receipt.
2. Stewart sets up the auditor's space containing only that material and the
   submission tool, and starts the auditor.
3. The auditor records and submits, or the manager collects.
4. Stewart delivers the verified return to the destination.
5. Help and status show where everything stands. Close works from any state. The
   manager's copy still verifies on its own afterward.

**What your friend gets** is a self-contained package:
- the source pinned to a commit, or a built binary;
- a short guide;
- one command that runs scripted manager and auditor through the cases above:
  normal submit, collect, empty and partial returns, interrupted operations, and
  close.

That command records their environment (Windows and WSL versions, distribution,
CPU architecture, filesystem, Git version) and the results into an archive they
send back.

**Not in the MVP**, as already decided: a program executor for the auditor, an
audit restart, live peeking or steering, and a general manager-workspace service.

---

## 2. The path to the MVP

> Good. Now express to me (Again, holding reservations in mind but out of
> chat--into a scratch file is fine for these and the prior turn concerns, they're
> not secret just not the topic ATM) the overall sequence of things from now until
> that MVP. Imagine you are the coordinator the whole time and can dynamically
> determine your workflow. How do we get from here to there. Talk in terms of
> stages of changes for the project, not human checkpoints.

Here is the path as a series of project changes. My reservations about this and
the previous answer are in `.scratch/alignment-20261028-01/RESERVATIONS.md`.

```
A  access route + delivery, settled by probe ──────────────┐
B  successor foundation ──┬── C  answer custody (auditor tool) ──┐
                          └── D  delivery + manager re-entry ────┼── E  auditor space + lifetime ── F  close, holds, Python exit ── G  integrated acceptance + packaging ── H  WSL
                                                                 │
side work from the start: acceptance driver skeleton, WSL capture script, Python legacy inventory
```

### A. Settle the access route and delivery design by probing them
**What changes:** I'd build a small probe in development tooling. It sets up each
candidate auditor space:
- a macOS container whose custody-writing process runs on the host;
- the host sandbox;
- a Linux namespace equivalent, because WSL has no Apple `container`.

It then tests each with a scripted adversarial shell. The cases are: the auditor
can write custody only through the tool, unselected material is absent, the tool
doesn't read beyond what the auditor itself can, and the auditor can't reach
manager operations. A few real agent sessions follow.

**Result:**
- An agreed route for each platform, recorded in CONTRACTS.
- Delivery designed together with the route, including where the return
  destination is bound and replacing the old "Delivery: Deferred" clause.
- The number of auditors trials use.

**Staffing:** one probe workflow of 3–4 agents, run in parallel with B.

### B. Turn the commission tool into the successor's foundation
**What changes:** `successor/` grows from the `stewart-commission` binary into one
`stewart` binary with a manager command group and an auditor command group. It
gets the shared building blocks every later stage uses:
- audit identity;
- operation and request records with request keys;
- records that are never overwritten;
- file reads that won't follow planted links;
- a strict JSON parser that rejects repeated keys;
- stable refusal reasons that each carry their sign;
- a verified copy primitive;
- a per-audit custody home beside the repository and outside any workspace, at an
  explicit, configurable location.

Commissioning becomes the start of an audit. The request gains the return
destination as a new request version, and the receipt binds the audit identity.
The existing commission tests stay as regression tests.

**Staffing:** one owner, because everything after this depends on these pieces.

### C. Answer custody: the auditor's submission tool
**What changes:** The prototype's mechanics are integrated into the foundation:
- the answer structure: an optional account plus artifacts, within the stated size
  limits;
- atomic add, replace and delete, each with an operation identity;
- prepare and submit, with dry run by default, explicit confirm, and refusal of a
  stale handle;
- manager collect, with exactly one winner when it races a submit;
- accounting for interrupted operations, including the note when submitting over
  one;
- slim help, a word-for-word question, inspect;
- a sign on every refusal.

The rows of the auditor-cases table become tests, and the prototype's controls are
re-run against the integrated code. Before the write protocol is fixed, a sanity
check reviews its failure table. The Q26 proposal (which informational notes are
neutral) settles the wording of the informational notes.

### D. Delivery and manager re-entry
**What changes:**
- At seal time, the sealed manifest goes to the destination first.
- Then the full return is copied there and read back to verify it.
- Further copies can be made of the same sealed return.
- Empty, partial and known-missing returns go through the same path.
- Two independent membership records are kept during authoring.
- Manager help and status work over explicit references.

C and D overlap once B's shared pieces are fixed, with two implementers on
separate files and a reviewer.

**After C+D:** Stewart can hold an answer and deliver it, exercised on sample
audits.

### E. The auditor's space and its lifetime
**What changes:**
- Stewart builds the auditor's world using the route chosen in A. It contains the
  selected material, which I'd populate from the verified commission copies, and
  the tool.
- The workspace and history questions are settled: plain files, history, builds
  and tests, and submodules.
- Stewart can launch an agent or a human auditor and bind the audit to that
  running process.
- It can stop the auditor cooperatively or forcibly, including child processes.
- Access is checked on both the auditor side and the manager side.
- The Git requirements that touch the space get a policy: a declared minimum
  version, and name normalization keyed to the volume rather than the platform.

**After E:** Stewart is a full audit service. Implementation splits by platform
where the routes differ.

### F. Close, holds and the end of Python
**What changes:**
- One close works from any state. It stops the auditor, makes sure delivery
  happened (or arranges it), and asks for explicit authorization over any
  known-missing material.
- Close has a defined behavior when custody itself is damaged.
- Holds block disposal.
- Removal works only from the closing record and through pinned file handles,
  never following paths that could have changed.
- Removal and omission studies are re-run with an independent witness.

Before the Rust version closes anything:
- the remaining Python audits are inventoried and closed under Python;
- Python stops admitting new audits;
- independent legacy obligations are settled.

**Staffing:** a single owner plus an independent witness or reviewer, because this
is the stage that deletes things. The design pass starts during C–E, so that
records already carry what close needs.

### G. Integrated acceptance and packaging
**What changes:**
- One acceptance driver exercises the whole path through the command line, and
  it's the same driver the friend will run.
- Runs on macOS and on Linux in a container (arm64, plus amd64 through Rosetta).
- Real agent audits, including the orientation trial.
- Documentation for Stewart's users: the guide and the Git environment
  requirements.
- Release builds for macOS arm64 and Linux x86_64 and arm64, plus a pinned source
  tarball.

**Staffing:** this is where fan-out pays: platforms and case groups in parallel.

### H. The WSL handoff
**What changes:** a package containing the binary, the pinned source, a short
guide, and one command that runs the driver and captures the environment and
results into an archive. The friend runs it and sends the archive back. Their
results are recorded, and any WSL-specific fixes go back through G and a second
handoff. Every remaining planned item gets an explicit outcome.

**Side work that runs alongside from the start:** the acceptance driver's skeleton
and the WSL environment-capture script, which grow with C–F, and the inventory of
remaining Python audits that F needs.

---

## 3. The coordinator role

> Good. Now talk about the coordinator role. You can see in the instructions from
> the turnover brief and the notes folder that we try to layer guidance in a way
> that you can modify and consume. Talk about the role, especially its expectation
> of regular replacement. As before, keep reservations apart, but your response
> here has less stricture from me.

My reservations about this one are added to the same file,
`.scratch/alignment-20261028-01/RESERVATIONS.md`.

### What the role is

The coordinator is the single agent who owns the coherent state of development at
any given time. You keep purpose, scope and anything that changes Stewart's
promises. The coordinator owns everything that turns an authorized direction into
verified, recorded work:
- investigating and breaking work down;
- deciding what runs in parallel;
- writing complete assignments and deciding who edits which files;
- integrating and verifying the results;
- handling Git.

The aim is that you engage with purpose, meaning and results, and never have to
manage logistics.

A few habits matter more than the rest:
- **Keep kinds of statement apart:** what you directed, what is already committed,
  what was observed, and what the coordinator recommends. Each is labeled where it
  applies.
- **Surviving text isn't authority.** Prose that has been in an account for a long
  time, or that sits near the top, doesn't become binding by staying there. An
  inherited recommendation is something to reassess.
- **Concerns stay with their work.** A deferred concern stays with the work it
  belongs to, along with the condition that would make it matter. It isn't a
  standing instruction to go investigate.

### How the guidance is layered

The layers run from slow-changing to disposable, and each has a different writer
and lifetime:

| Layer | What it holds | Who changes it, and how often |
| --- | --- | --- |
| CLAUDE.md / AGENTS.md | Project rules, custody rules, how to build and test | Rarely; must not point to particular plans |
| CONTRACTS.md | What Stewart is decided to do | Only on your decisions |
| Standing orders | How the coordinator operates | The coordinator, within delegated authority, saying what changed and why |
| Plans (`*-PLAN.md`) | The program: dependencies, open items, evidence owed | Updated as work moves; deleted when done |
| Current account | What is happening now and where things are | Rewritten throughout a tenure |
| Work folders | Briefs, returns, findings for one assignment | Owned by that assignment |
| Turnover brief | A thin, dated note for one handoff | Written on your directive; consumed and stubbed by the next coordinator |

The design lets each coordinator both use and change its own instructions.
Durable layers hold no session state, so they don't go stale when a coordinator
leaves. Session state lives in layers built to be rewritten or thrown away, so it
doesn't harden into rules. Stubbing the turnover brief is the clearest example.
Its useful content moves to a durable home and the brief itself is emptied, so it
can't grow into a runbook.

### Regular replacement

Replacement is the normal case, not an exception. The history shows about one
transfer a day this week, across models and harnesses. I think several reasons
converge:
- **Context degrades.** Context windows fill and compaction loses detail, so a
  long-lived coordinator gradually knows less than it seems to.
- **Fresh eyes reassess.** A newcomer can reassess inherited judgments, which a
  long tenure would quietly entrench.
- **Harnesses and models change.** The role has to survive moving between them.
- **Each handoff tests the records.** If the next coordinator can't pick up from
  the files, the records failed. Better to learn that on a planned transfer than
  after a crash.

Expecting replacement shapes the whole job:
- **Write for a stranger.** The next coordinator knows nothing but the files.
  Every checkpoint names what is done, where the evidence is, what is uncertain
  and the exact next action.
- **Save as you go.** Continuity can't depend on a good final summary, because an
  abrupt end leaves none. The brief is a supplement for planned handoffs only.
- **Authority doesn't travel in prose.** An incoming coordinator gets its
  authority from you and from the standing orders, not from what the last one
  wrote. That is why attribution matters: the successor needs to know which
  statements are yours, which it may revise.
- **One writer at a time.** Before taking over paths someone else was writing,
  confirm that writer has stopped. A silent handle or an old timestamp doesn't
  prove it.
- **The outgoing coordinator steps back.** It can be consulted afterward, but it
  doesn't keep a competing queue of its own.

There's a resemblance to Stewart itself. Stewart treats its participants as
cooperative but fallible. It hands work over through bounded trap doors with
receipts, and an interrupted manager finds its way back through help and status
rather than memory. The coordinator arrangement treats coordinators the same way.
CLAUDE.md keeps the two apart on purpose: neither side's practices become the
other's requirements.

### How I intend to hold it

- **Talk to you about the work, not the machinery.** Process belongs in the files.
  Your correction two turns ago applies to the whole tenure.
- **Keep the current account small.** It should hold the current state plus
  pointers, cheap enough to read at every intake. Git already holds the history.
- **Treat your alignment checks as part of intake.** These turns test whether what
  I built from the files matches what you mean, which the files can't do on their
  own.
- **Leave a clean takeover point at every stage boundary**, and tell you when one
  arrives. You decide when the transfer happens, but I can point out the good
  moments for it.

---

## 4. Collecting the held-back notes, with radical alternatives

> Ok. Collect those questions, reservations, and confusions into one file (ideally
> by copy/paste) and add a header for me to understand what's below and a
> conclusion section where i want you to mark off RADICAL solutions to problems you
> see. Not amleiorative ones. We may not undertake these. I want to read them. By
> radical I don't mean bad or damaging I mean giving up on something you have
> inferred is important to me.

The file is [CONVERSATION-HELD-BACK.md](CONVERSATION-HELD-BACK.md) (copied
verbatim). My reply:

I've collected everything into one file:
`/Users/raccoon/Desktop/Experiments/stewart/.scratch/alignment-20261028-01/RESERVATIONS.md`

- **Header:** explains what the file is and gives a key that sorts the items into
  questions for you, confusions, reservations, and planning or practice concerns.
- **Items 1–36:** the notes I wrote during each of the three turns, copied
  verbatim. I checked the copy byte for byte against the original, and the
  original numbering and headings are kept.
- **Items 37–38:** two confusions I noticed while collecting. One is who your WSL
  friend is in product terms: a Stewart user or a tester. The other is what "how
  many auditors trials use" counts.
- **Conclusion:** twelve radical alternatives. Each one says what it gives up,
  what Stewart would do instead, and which items it would make disappear.

The radical alternatives:
- **R1** detect tampering instead of preventing access.
- **R2** remove the auditor's shell, so it has only Stewart's tools.
- **R3** Stewart never deletes anything.
- **R4** Stewart neither launches nor stops the auditor.
- **R5** drop the authoring tool and snapshot an answer folder at the end.
- **R6** run Stewart only inside Linux.
- **R7** drop Git.
- **R8** drop the Python baseline now.
- **R9** drop question types.
- **R10** make the manager's destination folder the custody.
- **R11** drop coordinator continuity between sessions.
- **R12** drop inquiry before building, and the evidence routines around each
  claim.

The file ends with the thinnest combination: R1, R3, R4, R5 and R7 together turn
Stewart into a notary, which is roughly the existing commission tool plus one more
command.

R5 reverses decisions you made on 10-27 and 10-28, and the entry says so. I
included it because the authoring tool is the largest single body of work in the
plan.

---

## 5. Your reaction, and how the picks fit together

Your comment and my interpretation of it are recorded at the end of
[CONVERSATION-HELD-BACK.md](CONVERSATION-HELD-BACK.md#maintainer-comment-2026-10-28).
The comment, for reading in place:

> OOOOOhhhhh..... Ok. This is excellent. I want to talk about some of these
> alternatives. R8 I basically agree with full stop. R7 has been BOTHERING me. R6
> is perfectly pleasing. I don't want this to be a mac tool I want it to run on
> Linux. R9 is a "kill your darlings situation" so I want to hear about it but
> expect resistance. R3/4/5 seem like they could go together, as you note. R2 I
> want 100%. R1 I want to hear a pitch. That's a sweeping response. Please collect
> that into a maintainer comment as a quote THEN immediately append your
> interpretation of what I want. Then return to me to discuss the confluence of
> what I just said looks dandy.

My reply:

Your comment is quoted verbatim at the end of
`/Users/raccoon/Desktop/Experiments/stewart/.scratch/alignment-20261028-01/RESERVATIONS.md`,
followed by my reading of what you want.

### How the picks fit together

The picks hold together, and R2 is the one the others hang on. Once the auditor
has no shell, most of the hard problems in the earlier plan lose their cause.

**R2 + R6 + R7: one small, Linux-only Stewart.** Without Git, the material is just
files. Without a shell, the auditor reaches those files only through Stewart's
read tools. With Linux as the only platform, there's one filesystem to reason
about: no case-folding, no Unicode-normalization branch keyed to the platform, no
APFS assumptions, no Git version floor. The commission tool already takes plain
file copies, so R7 mostly confirms what the newest code does. R8 removes the last
reason to keep Git-shaped machinery: the frozen Python baseline that compared
against it.

**R2 makes R3 and R4 natural.** An auditor with only Stewart's tools has no
workspace. The harness runs somewhere, but the auditor can't look at it.
- **R3 (never delete):** there's no auditor environment to retire, so close
  shrinks to sealing and recording.
- **R4 (no launching or stopping):** Stewart becomes a tool server that the
  harness starts. Once an answer is submitted or collected, every further call
  gets the closing sign, so a still-running agent can do nothing. Stopping it
  stops mattering.

**R2 changes R5 instead of confirming it.** R5 meant "snapshot a folder", but a
shell-less auditor has no folder. The authoring tool comes back as the auditor's
only way to write, and it gets much smaller:
- Content arrives in the tool call itself, not as a path the auditor wrote to.
- Staging races, planted links and descriptor-safe reads of auditor-written files
  all disappear.
- Stewart is the only writer, so atomic add/replace/delete becomes ordinary.
- Interrupted operations reduce to "your last call did or didn't land", which
  inspect can answer.

The bundle you saw in R3/4/5 really becomes R3 + R4 + a small authoring tool.

**R1 shrinks to what's left over.** On the auditor side, R2 replaces most of what
R1 was about. Absence is total by construction, which is your keyhole: talking to
Stewart is the only thing the auditor can do. What remains for R1 is:
- the harness configuration that keeps only Stewart's tools;
- the manager side;
- protecting the custody folder from everything else on the machine.

The R1 pitch should be aimed there.

### The shape that falls out

A Linux binary with five surfaces:
1. **Commission:** what exists today, plus a return destination.
2. **The auditor's tool surface:** list, read and search the materials; add,
   replace and delete; inspect, prepare and submit. It's exposed both to agent
   harnesses and as a CLI for a human auditor.
3. **Collect.**
4. **Delivery** of the sealed return to the destination.
5. **Status, help and a close** that records and doesn't delete.

On WSL, your friend runs it natively inside WSL2, and the MVP gets much closer.

### Where your picks pull against each other

1. **R2 against investigation.** The auditor can't run tests, builds or scripts.
   Any execution results have to be supplied by the manager as materials.
   Stewart's tool surface has to carry the investigation, so search can't be an
   afterthought. This is your "constrained audit space" made literal, which is
   where CONTRACTS says Stewart's influence legitimately lives, but it needs
   deliberate design under the agnosticism principle.
2. **R4 against enforcing R2.** If Stewart doesn't launch the auditor, then
   whoever launches it decides whether "only Stewart's tools" is actually true.
   Stewart can print the exact command, but a manager can change it. If Stewart
   launches, it can guarantee the configuration but owns a process again. R1's
   detect-don't-prevent stance is one way through that.
3. **R7 against some questions.** Questions about history ("when did this change
   and why") need the manager to export history as files. That's workable, but it
   moves effort to the manager.

Where next: the R1 pitch (now aimed at the harness configuration and the manager
side), the case for R9, or pinning down the R3 + R4 + small-tool bundle?

---

## 6. Three answers, and the radical design

> 1. Ok. R2 and R9 also interact. We might gain a reason for some typing with this
> particular restraint. 2. I prefer the simplicity of R2 over R4. 3. That's fine.
> Consider those answers and NOW draft a design doc for this Stewart MVP.

The design is [DESIGN.md](DESIGN.md), the second view. My reply:

I've drafted the design doc at `coordination/linux-mvp-01/DESIGN.md` and committed
it as `717cdff`. CONTRACTS is unchanged; the doc lists what would have to change
once you decide.

**How I applied your three answers**
- **R2 over R4:** Stewart runs the auditor itself, calling the Claude API in its
  own loop. The model's only tools are the ones Stewart defines, so "only
  Stewart's tools" is true by construction. With Claude Code or another harness,
  we'd have to switch off its built-in tools, hooks, plugins and MCP, then prove
  they stayed off.
- **R2 with R9:** question types come back as **profiles**. A profile is the
  auditor's tool set, its role guidance and the manager's recipe for writing that
  kind of question. The auditor never sees a profile name, which matches the
  decision that it isn't shown a question type. Profiles can add capabilities but
  never required answer fields, so the answer stays neutral about outcomes. The
  MVP ships one profile, `read`. A later profile could add sandboxed code
  execution that runs on the API provider's side, which would bring back
  experiments without giving the auditor a local shell.
- **R7:** a commission is a question plus files. A material can now be a
  directory, which Stewart expands into an explicit list of files when it takes
  the commission. History, diffs and logs are files the manager exports.

**What fell out that I didn't expect**
- **Access log.** Every read and search goes through Stewart, so it can record
  exactly what the auditor consulted. I've proposed putting that in the return.
- **API call IDs as operation IDs.** Each tool call already carries an ID from the
  API, which can serve as the operation reference for interrupted-operation
  accounting. The API also requires an unedited history, which Stewart's
  write-once records already give it.
- **Close becomes easy.** Because it deletes nothing, "close from any state" is
  simple to honor, even over damaged custody.
- **Deterministic tests.** Acceptance runs against a local fake API that replays
  scripted model turns. The WSL suite therefore needs no API key and costs nothing
  to run.

**What the doc covers:** commands, the commission, the auditor's ten tools, the
run loop (budgets, a warning to the model near its limit, compaction for long
runs, fallback when the model declines a request), the storage layout, delivery,
close, integrity, packaging, the WSL handoff and a seven-step path.

**Open questions it asks you:**
1. R1, which is pitched in the doc's "Integrity" section.
2. Whether to keep question types as profile recipes.
3. Whether the full transcript belongs in the return.
4. Whether a human auditor is in the MVP.
5. Whether to support other model providers.
6. Default model, effort and run limits.
7. Size limits for directory materials.

If you'd rather read it as a rendered page, I can publish it.

---

## 7. Three zooms

> Now alongside that write what looks like a clean-sheet design. No findings
> anchors, open decisions posed as they flow from the design. We don't need to
> sweep away what we have, we're drying for 3 "zooms" on one design encounter. The
> conversation, the radical design, and the presentation of that as *the* design.
> When complete review those three and add a new final reservations doc about what
> bothers you even with this new stance. I'll review the whole folder once it is
> committed.

This turn produced the folder's [README](README.md), this file, the clean-sheet
[STEWART.md](STEWART.md) and the final [RESERVATIONS.md](RESERVATIONS.md).
