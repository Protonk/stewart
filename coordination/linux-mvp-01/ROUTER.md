# Stewart

*A problem router for cooperative actors who want to make it **just** so.*

Revised at turns 19–23 of [the conversation](CONVERSATION.md): the auditor's
tool as a form and a ledger (19); the inquiry as the manager's unit, the
operations after the receipt, and the escalated run (20); the problem file,
material acceptance and the pre-run lesson (21); the return as the submission
and nothing else (22); the dead run as a continued placement (23). The version
before those turns is in Git at `05a21d4`. The design review ended at turn 23;
CONTRACTS records the decisions, and this is the settled sketch.

Amended 2026-10-28 after that closed conversation, under the user's delegation
to resolve manager recall and status/close: the receipt readback command,
qualified status and delivery continuation below follow CONTRACTS' "Successor
manager readback, status and close." Preview, auditor retry and question
typing/coupling remain separate discussions; this amendment decides none of them.

## The idea

Someone has a problem: a question about material they hold. They want it answered
by someone else, a model today and a person later, placed in a world arranged
exactly so: this question, this material, these means of answering, and nothing
else. Stewart takes the problem as its owner wrote it, situates an auditor in that
arrangement, and routes the answer back with a faithful record of how it was
produced.

Stewart doesn't investigate and doesn't judge. It arranges, carries and records.

## Who is involved

- **The manager owns the problem.** They choose and word the question, select the
  material, pick the shape the answer should take, and set the limits. They are
  cooperative, may state preferences (that is their business), and are
  responsible for the answers their choices produce. A manager is a person or an
  agent; an agent's harness may hand the run to a person, and Stewart does not
  tell them apart.
- **The auditor owns the answer.** Also cooperative. A model to begin with, a
  person later.
- **Stewart owns the arrangement and the record.** It situates the auditor
  faithfully, records what happened, and delivers the result.

## Principles

- **Responsibility follows authorship.** Whoever wrote something owns it: the
  manager the question and material, the auditor the answer, Stewart the
  arrangement.
- **Opinionated about form, agnostic about conclusions.** Stewart's opinions about
  what an answer should look like live only in its answer forms and the
  auditor's orientation. Those are versioned, readable, named by every return's
  manifest and shown to the manager before a run. Stewart never judges whether an answer is
  right, valuable or welcome.
- **The world is the arrangement.** For a model, that means its tool list and
  nothing more. For a person, it means the packet they receive and their agreement
  to work from it.
- **The auditor's tool is a form and a ledger.** It accepts data, records it, and
  answers plainly and at once. It is deliberately uninteresting, forgiving of
  guesses, and has one visible setting: whether a submit is a dry run. When a call
  fails or its reply is lost, the auditor calls again; the tool never repairs on
  the auditor's behalf and never hands an exceptional state down the line. It is
  the hard side of a boundary object between the auditor's practice and the
  manager's: the standardized form the collector staples to the specimen.
- **Losing track is never fatal.** One call tells an auditor everything it is
  working with.
- **Quick to answer, and sure of what it says.** Every manager command and every
  protocol call responds promptly and says exactly what it did. How long an audit
  runs and how hard its auditor thinks are the manager's business, not Stewart's.
- **Records are written once.**

## The shape

```
            ┌──────────────────────── Stewart ────────────────────────┐
  manager ─▶│ problem ─▶ arrangement ─▶ adapter ─────── protocol ─────┼─▶ auditor
            │                                                         │   (model | person)
  manager ◀─│ return ◀── record ◀────────────────────── protocol ─────┼── auditor
            └─────────────────────────────────────────────────────────┘
```

A **problem** is what the manager writes. An **arrangement** is what Stewart
builds from it. An **adapter** places an auditor into the arrangement, and the
**protocol** is how the auditor works inside it. A **return** is what comes back,
with its **record**.

## The problem

A problem is a Markdown file: a front-matter header and, as the body, the
question in the manager's own words.

```markdown
---
stewart: problem/1
inquiry: parser-2.4
form: claim-check
claim: The 2.4 parser accepts every input the 2.3 parser accepted.
material:
  - src/parser/
  - exports/parser-history.txt
  - label: design-notes
    path: /home/me/notes/parser-2.4.md
auditor:
  adapter: model
  model: claude-opus-5-5
  effort: high
  limits: { turns: 200, tokens: 4000000, minutes: 120 }
  compaction: on
  reasoning: summarized
destination: /work/returns
---

Does the 2.4 parser accept every input the 2.3 parser accepted? The grammar
was rewritten in `src/parser/grammar.rs`; the exported history lists every
change since 2.3 shipped.
```

- **Inquiry:** the line of questions this problem belongs to. It is the
  manager's unit as far as Stewart is concerned.
- **Question:** the body, delivered verbatim. It may also be given by path.
- **Material:** files and directories, copied and verified at intake. Anything that
  lives elsewhere (history, test output, logs) comes in as exported files. Extra
  material may be added as command-line arguments.
- **Form:** the shape the answer should take, plus any fields that form asks for.
- **Auditor:** which adapter, and its settings and limits.
- **Destination:** where the return goes.

## Material

Flexible at the mouth, exact in the record.

- A path relative to the problem file is the material's name in the auditor's
  index. An absolute path needs a label, which becomes its name. Two materials
  that would share a name are refused with a sign; nothing is renamed silently.
- A directory expands to its regular files. By default Stewart excludes
  version-control administration, build output and files over the per-file
  limit; every exclusion is listed, and the manager can include any of them
  explicitly. Symbolic links and special files are listed as not copied.
- Whatever the manager wrote, the preview and the receipt show one canonical
  problem. Unknown keys and bad values are refused with a sign naming the field
  and the fix, never dropped.

## Answer forms and couplings

An answer form is what the manager picks. The library file that defines it is a
**coupling**: a small versioned file that wraps the manager's question without
rewriting it. It contributes:

- **an answer shape:** named slots, which the protocol exposes as tools;
- **a stopping rule:** stated so that every conclusion finishes at the same point;
- **the universal exits:** *wrong question*, *missing evidence*, *nothing found*;
- **the prior:** whether a claim the manager supplies is shown to the auditor as
  its subject or kept sealed.

The library is provisional. `survey` and `claim-check` were proposed in the
conversation; their concrete shape does not settle their design as instruments of
inquiry, and consequential choices about answer forms and stopping rules are
made in discussion, not by the library. One test for a slot: the auditor must be
able to fill it from where it stands, with the evidence attached. A field that
needs the manager's categories belongs to the manager.

```
coupling: claim-check@1          (illustrative)
asks:     claim
frame:    "You are given a question and a claim someone relies on. Lay out
           the premises the claim needs, and for each say whether the
           material binds it."
slots:    premise {text, binding: bound|unbound|unclear, citations[]}
          first_unbound
          smallest_addition
stop:     every premise the claim relies on is accounted for, or missing
          material prevents that
prior:    shown
```

| Coupling | For | Answer shape |
| --- | --- | --- |
| `survey` | "What here bears on this?" | Findings, gaps, and what the material can't speak to |
| `claim-check` | "Does the material support this claim?" | Premises with binding, the first unbound premise, the smallest addition that would bind it |

New couplings join when returns keep asking for them. Every return records its
coupling and version.

## The arrangement

From the problem, Stewart builds the arrangement:

- the **frame**: the orientation, the coupling's wrapper and the question verbatim;
- the **materials index**;
- the **tool set**: the protocol plus the coupling's slots;
- the **limits**.

The orientation is the form's instructions: how to fill it and when it is
complete. It does not say why the question matters or what the manager will do
with the answer. `stewart preview` shows the arrangement exactly as the auditor
will meet it, before anything runs or costs anything. The arrangement's digest
goes in the receipt.

## Before the run: the app is the lesson

Asking is the hard part, and the app teaches it through the four replies a
manager reads anyway.

- **`stewart help`** is one screen: write a problem file, preview it, commission
  it; then run, status, close. It lists the forms with one "ask this when" line
  each, and the limits. There is no manual behind it.
- **`stewart new <form>`** writes the problem file with every field commented:
  what it is for, what the auditor will and will not see because of it, and an
  example. The comments are written against the gap: the auditor knows nothing
  the manager does not put in the question or the material.
- **`stewart preview`** is the mirror. It renders what the auditor will meet and
  runs the checks: names in the question that appear in no material; material
  the question mentions that is not attached; directories that expanded to
  nothing; files skipped and why; the total against the limits. Each check says
  what the auditor would experience. Checks are advisory. Stewart is less
  entitled to be strict about what a manager thinks necessary than it is to make
  an auditor retry, so commission proceeds past a warning and the receipt records
  it.
- **The receipt** confirms: this is the question, this is the material as copied,
  this is the run command. It also gives `stewart receipt REF` for later recall.

The receipt is a supported interface after the commissioning conversation is
gone. `stewart receipt REF` retrieves the recorded commission, its original
question, material index, arrangement identity and intake qualifications. Its
stable item IDs and `stewart receipt REF --read ITEM` recover the original
problem, question, recorded arrangement and individual copied inputs as verified
bytes. It works from any directory, without a provider key, including during a
run. It reads the fixed commission, never the auditor's live answer. Recorded
acceptance and present verification are distinguished; damage is diagnosed
without substituting live sources or current form definitions. A valid selected
item remains readable despite unrelated damage. After close the same route
reads what remains retained, with no new retention promise.

## The protocol

The protocol is the same for every adapter:

| Call | Does |
| --- | --- |
| `what_am_i_working_with` | The question verbatim, the materials index, the current answer as recorded, and the last submission error if any. |
| `list`, `read`, `search` | Reach the material. |
| *coupling slots* | Fill the answer's shape, e.g. `record_premise`. |
| `add`, `replace`, `delete` | Edit free-form answer elements. |
| `prepare`, `submit` | Prepare a manifest and handle; submit is a dry run unless confirmed, and confirming seals. |

Every reply opens with a header line saying where the auditor is. Every refusal
gives a reason, its effect on the answer, and the next call. As proposed, every
citation is checked against the material, byte for byte; that check is one of
the answer-form choices still to be decided.

The ledger is the only truth. A call either appended a complete record or it did
not; a torn record is a diagnostic, never an element. After a failed call or a
lost reply the auditor calls again, and `what_am_i_working_with` shows what
landed. A retry lands as a new record; equal bytes never identify a retry.
Stewart settles nothing on the auditor's behalf, and the return carries no
unresolved-operation state.

## Adapters

An adapter does three things: it delivers the arrangement, carries protocol
calls, and reports when a run ends.

**Model adapter.** Stewart's own thin loop over the Messages API. The model's tools
are the protocol, so its world is exactly the arrangement. Compaction and reasoning
display are the manager's settings. The full conversation is kept in Stewart's
home for whoever runs Stewart to read; it never travels in the return.

**Person adapter.** The same protocol through a humane command line, and in time
carried to wherever the person works. The person works from the arrangement by
agreement.

Every return names the adapter that produced it and how that adapter holds the
auditor to the arrangement. Any other way of working, such as running code or
another harness, is a new adapter. Stewart itself doesn't change.

## The run and the handoff

Commission and run are separate commands, and the line between them is the
network. `commission` copies and verifies the material and writes records, all
locally. `run` is the only step that touches the provider and needs its key.

- The receipt is the handoff. It carries the audit's reference, the exact run
  command, and what run needs from the environment.
- `run` takes the reference and nothing else. It works from any directory,
  needs no session, runs in the foreground by default, and refuses with a sign
  if the audit is already running or has ended.
- `status` takes a reference, gives the receipt retrieval command, and answers
  whoever holds it. It distinguishes the observed run, answer seal, delivery and
  closure; a stopped run is not necessarily a submitted or delivered answer.
- Stewart records what it observed about each invocation (user, process, time)
  as observations. It never labels who the manager is; the manager is whoever
  holds the reference.

Agent harnesses escalate network commands to a person at their own discretion.
Stewart cannot demand or enforce that, so the design allows for it without
depending on it: an agent manager may commission, hand the run line to a person,
do nothing while it runs, and come back to `status` afterward; or run it
itself; or both within one session.

**The dead run.** An audit is its ledger, and a run is one placement of the
auditor into the arrangement. A run that dies ends a placement, not the audit.
`run REF` afterward continues it: a new conversation, the same arrangement, the
same ledger, limits counted across runs. The resumed auditor is told it is
continuing and that `what_am_i_working_with` shows what it has recorded. Stewart
records every run and `status` says how many there were. A provider outage
inside a run gets a bounded retry; then the run ends and `run` again continues.
This is what a person auditor does on returning to the work, so one protocol
serves both adapters. Replaying the earlier conversation so a model keeps its
reading is an adapter optimization to weigh on evidence; it changes nothing in
the record.

## The return

The manager receives what the auditor submitted through the tool and `prepare`
accepted, and nothing else. The auditor seals with `submit`, or the manager
seals with `close`. A run with a sealed answer delivers to the destination,
then reads everything back to verify it. A run ending without submission leaves
the recorded selection for manager sealing through close:

```
parser-2.4-7QK3RM/
  MANIFEST.json      the audit reference, the form and version, every member
                     and its digest, and who sealed it
  answer/            the raw slots and elements (whether a form's rendering is
                     also a prepare-generated, Stewart-attributed member is
                     undecided)
```

The destination is exclusive: an existing directory is evidence and is refused,
never overwritten or emptied. The question, the receipt, the arrangement, the
access log, the run summary and the conversation stay in Stewart's home as the
record. `receipt` provides commission readback; `status` reports operating facts;
the remaining record stays in the home. A return looks the same whether a model
or a person produced it. Every instance of a coupling renders the same way, so returns are comparable
across audits, materials and models. Comparing them is the manager's work on
files the manager owns.

## Iterating

- `stewart new --like REF` starts from an earlier problem in the inquiry, with
  overrides.
- Each audit records which problem it was varied from, so an inquiry reads as
  one line of questions rather than a string of failures.

## Responsiveness

The manager and the auditor should never wait on Stewart, and never wonder what
it did.

- **Ordinary calls take tens of milliseconds.** Startup, `status`, `preview`,
  `what_am_i_working_with`, answer edits, `prepare` and `submit` answer at once.
- **Size-bound work shows its size first.** Intake copying, commission readback,
  search across all the material, and delivery state how much they are about to
  handle, report progress, and finish with what they verified. Raw readback keeps
  progress and qualifications outside the byte stream.
- **Every reply carries its own certainty.** What changed, what was checked, and
  what to do next, in the same place every time. A reply never says "probably".
- **Speed is tested.** Response budgets are part of the test suite, measured on
  material at the size limits.

## The manager's surface

After the question, the manager's operations are a receipt, "is it done?" and
close. That is all.

| Command | Does |
| --- | --- |
| `stewart help` | A short cheatsheet; detail per command. |
| `stewart new` | Scaffolds a problem file for a chosen form, or from an earlier problem. |
| `stewart preview` | Shows the arrangement exactly as the auditor will meet it, with the checks. |
| `stewart commission` | Copies and verifies the material and issues the receipt with the run line. |
| `stewart receipt REF` | Retrieves the original commission and readback item IDs; `--read ITEM` returns verified original bytes. |
| `stewart run` | Places the auditor and runs it, delivering a sealed answer at the end. |
| `stewart status` | States the run, answer seal, delivery and closure facts for an audit, or each audit in an inquiry, with explicit references and next actions. |
| `stewart close` | From any state: stops a live run, seals what is recorded as the manager's if unsubmitted, delivers if not delivered, and records the end once the manager confirms the copy is placed. |

Every command fails early with a reason and a next step. Every command can answer
in JSON, for managers who are agents; raw receipt readback instead puts bytes on
stdout and qualifications on stderr.

Status says, for example, "Interrupted; not submitted", "Answer sealed; delivery
incomplete", or "Delivery verified at [time/location]; audit open". It does not
infer an auditor conclusion from an empty selection, liveness from elapsed time,
or present copy safety from a delivery record. Damaged records keep their
diagnostics instead of defaulting to one of these states. It gives the specific
continuation through `run` or `close`, without making inspection a prerequisite.

If copying cannot finish at its destination, `close REF --destination DIR`
continues the same owed delivery elsewhere. It records the replacement location,
uses a fresh exclusive package name and preserves partial copies. It never
changes the sealed answer or reopens investigation. A repeated close reconciles
its own recorded effects and reports an already verified delivery again. This
does not add a general copy service after successful delivery or closure.

If delivery predates the first close request, ordinary close is the manager's
placement confirmation. If close first makes the copy, it returns a confirmation
reference bound to that seal and delivery, recoverable through status; the manager
uses `close REF --confirm TOKEN` after receipt. Repeating close without that
confirmation only re-presents the result. Lost replies do not authorize final closure. Known
missing members require explicit surrender of their named undertakings, distinct
from ordinary confirmation. Unknown selection stays diagnosed and unfinished.
Run termination is evidenced separately from sealing; close cannot claim that
stopping succeeded just because the answer was sealed.

## Lifecycle and storage

Commission fixes the question and material. Runs may be interrupted and continued
on that commission until the answer is sealed or the audit ends. An auditor
submission or manager close seals the answer once. Delivery and its verification
follow that seal; close records the end after the required confirmation and
stopping evidence. A run ending at a limit without submission has no automatic
auditor seal. A closed audit with an explicitly surrendered delivery loss stays
labelled that way, never as a completely delivered return.

Each audit lives under Stewart's home as write-once records: the copied material,
the arrangement, every protocol call and its outcome, the conversation, the seal
and the delivery. As proposed, Stewart deletes nothing, closing is a record, and
removing an audit's directory is the manager's ordinary housekeeping; whether
Stewart ever removes bytes is the first decision the transition plan carries to
the user.

## What ships, and what doesn't

**Stewart ships as one small binary.** It is statically linked Rust for Linux on
x86_64 and aarch64, with no runtime dependencies; WSL2 runs it as is. The coupling
library and orientation are built in. The only network it touches is the model
provider, over HTTPS, from the model adapter.

**The apparatus never ships.** Everything used to build, test and experiment with
Stewart lives in Linux containers defined in the repository:

- **a build image** with a pinned Rust toolchain, the musl targets, and a short list
  of vendored crates (JSON, hashing, regular expressions, HTTPS over a pure-Rust TLS
  stack), producing the release binaries reproducibly and offline;
- **a test image** that runs the suite against the binary as built: a fake model
  provider replaying scripted auditor turns, material at the size limits, the
  response budgets, and every lifecycle and failure path;
- **an experiment image** for trials with real models and real questions, kept
  apart from the suite and never a release gate.

No host language runtimes, version matrices or host toolchains are involved. A
developer's machine only needs to run containers; on a Mac that is a Linux VM.
What gets tested is exactly the binary that ships, in the kind of system it ships
to.

## First release

- The model adapter.
- `survey` and `claim-check`, as the provisional library.
- `help`, `new`, `preview`, `commission`, `receipt`, `run`, `status` and `close`,
  all within the response budgets.
- Release binaries for Linux x86_64 and aarch64, built and tested in the apparatus.
- A handoff package for a WSL2 run: the release binary plus the test suite's
  driver and fake provider, run natively in WSL2, since WSL's own environment is
  what's being tested.
