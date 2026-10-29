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

Amended 2026-10-29 following the user's agreements and subsequent delegation,
recorded in CONTRACTS' manager preparation, custody and initial-material sections:
ordinary preparation, explicit prepare/commission, cooperative checks and
contextual errors; a designated non-removing archive; literal text materials and
preparation inspection without a separate preview. The user subsequently accepted
bounded auditor re-entry, exact edit targets and known-invocation result replay;
the corresponding CONTRACTS section governs. The user then selected question
families as the organizing model, with inquiry framing as a specific family and
open inquiry roughly following the optional-evidence-module proposal. CONTRACTS'
"Successor question families and open inquiry" governs. The user subsequently
selected open inquiry, inquiry framing and comparison as the initial library and
accepted a preparation-generated, Stewart-attributed Markdown rendering sealed
with the structured answer. Detailed forms and enforcement remain open.

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
question in the manager's own words. The form and settings below remain
illustrative; the separate typing/coupling discussion selects what ships.
Materials now come from the submission folder, not an extra path list.

```
submission/
  question.md
  materials/
```

These are the only root entries. Intended extra material goes under `materials/`;
unexpected root entries receive a useful refusal. Stewart's metadata lives in
the separately designated archive. `new` can scaffold or use an explicit
existing folder without overwriting it. The caller keeps the returned reference.

```markdown
---
stewart: problem/1
inquiry: parser-2.4
form: claim-check
claim: The 2.4 parser accepts every input the 2.3 parser accepted.
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
- **Question:** the body, delivered verbatim.
- **Material:** files and directories, copied and verified at intake. Anything that
  lives elsewhere (history, test output, logs) is placed in the submission folder
  as exported files before preparation.
- **Form:** the shape the answer should take, plus any fields that form asks for.
- **Auditor:** which adapter, and its settings and limits.
- **Destination:** where the return goes.

## Material

The submission boundary is literal: every entry under `materials/`, including
hidden entries and empty directories, is accounted for. Names are exact relative
UTF-8 paths, case-sensitive without normalization. Links and special files refuse
intake without being followed; hard-linked regular files remain separately named
selections. No Git/build/editor exclusion list exists. Unknown fields, ambiguous
names, unsupported bytes and exceeded limits name the item and fix. The manager
corrects the ordinary folder and prepares again when its selection changes.

The initial reader serves raw UTF-8 text without NUL bytes, regardless of extension.
It preserves line endings and all other bytes. It performs no document extraction,
OCR, archive expansion, normalization or execution. JSON/CSV/code are read as text;
a nominal document that meets the encoding rule is raw syntax, not a promise of
rendered-document support. The manager supplies text exports when needed.

[CONTRACTS](../../CONTRACTS.md#successor-initial-materials-and-preparation-inspection)
fixes the initial file/count/byte/path bounds. `list` exposes the captured index;
`read` gives exact bounded text with byte ranges and explicit continuation; literal
case-sensitive `search` names its scope, byte positions and whether more remains.
Long lines and paginated results cannot disappear behind unmarked truncation.
These tools never fall back to the live source folder. Source permissions are not
part of content identity or replicated execution grants.

## Answer forms and couplings

The manager chooses from a library of question families. A **coupling** is the
versioned definition pairing a family's preparation guidance, material-role
prompts, auditor instructions and answer expectations. It wraps the manager's
question without rewriting it and is pinned in the arrangement. The library is
the chosen organizing model; its concrete forms are not yet specified.

Three initial families are selected, with final spellings provisional:

| Family | Commissioned work | Boundary |
| --- | --- | --- |
| Open inquiry | Answer the manager's question with an account of the evidence and limits; optional evidence modules can supply useful structure | No compulsory module selection, justification for choosing open, reduced service or extra commissioning step |
| Inquiry framing | Formulate a working question from the concern, then investigate it within the same commission | Preserve the original request and attribute the framing and its limitations to the auditor; no expanded materials, tools, budget or live approval |
| Comparison | Compare supplied alternatives against the stated criterion, explaining evidence and limits | Concrete fields and enforcement remain to be specified; no required winner or invented evidence |

Open inquiry with no modules is a complete route for broad requests. Material-role
prompts may expose unassigned roles without treating them as proof that evidence
is absent or blocking commissioning. Mechanical intake refusals still apply.
Every family permits challenging the framing, missing evidence, no supported
finding and qualifications. Only selecting inquiry framing commissions formulation
as part of the task; the other families do not silently inherit it.

Specify each family through a manager submission, actual auditor tools and a
return, including an inadequate-evidence case. Behavior check and claim examination
remain later candidates. The old `survey` and `claim-check` illustrations do not
select schemas;
`first_unbound` and `smallest_addition` are not inherited obligations. Concrete
slots/tools, module interactions, citation handling, stopping rules/checks, a
manager-supplied prior remain to be settled together. Rendering is decided below.
One test for any slot: the auditor can fill it from where it stands, including an account of
what cannot be established. Selecting a family certifies no substantive outcome.
The rule for adding families remains open. Every return identifies its selected
coupling and version.

## The arrangement

From the problem, Stewart builds the arrangement:

- the **frame**: the orientation, the coupling's wrapper and the question verbatim;
- the **materials index**;
- the **tool set**: the protocol plus the coupling's slots;
- the **limits**.

The orientation is the form's instructions: how to fill it and when it is
complete. It does not say why the question matters or what the manager will do
with the answer. Prepare retains a readable arrangement and its machine
representation: exact versioned instructions, form, tools, limits and bindings to
the question/material selection. It returns their locations for inspection with
ordinary tools. Commission uses that pinned arrangement; the accepted digest goes
in the receipt. No separate preview command ships initially.

## Before the run: the app is the lesson

The manager assembles a question and materials in an ordinary folder. Help and
the scaffold explain the selected form and submission rules without making
Stewart judge whether the question or evidence is intellectually sufficient.

- **`stewart help`** describes ordinary editing, prepare and explicit commission,
  then run, status and close. It explains the limits and instructs the manager to
  finish editing before prepare and leave the folder alone through commissioning.
- **`stewart new`** creates the preparation scaffold and reference. The manager
  owns that folder; close leaves it alone. Form selection remains separate design work.
- **`stewart prepare`** inventories and hashes the selected question and materials,
  checks mechanical intake rules and binds relevant settings. It returns an
  inspectable manifest and handle, without accepting or preserving source bytes.
  Unsupported entries and exceeded limits are refused, not silently excluded.
- **Commissioning** takes that handle and an explicit acknowledgment that
  preparation is finished. It copies and verifies against the manifest and checks
  the final source membership and contents. The declaration and matching checks
  are separately recorded; neither proves an atomic source snapshot. Edits that
  change the selection require fresh preparation, with no unprepare or mandatory
  inspection pause. The readable arrangement supplies pre-acceptance inspection;
  no separate preview or advisory question-grading surface ships initially.
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
item remains readable despite unrelated damage. After close the same route reads
retained originals. The first Rust release removes no archived bytes; external
loss is diagnosed and never repaired from changed live sources.

## The protocol

The protocol is the same for every adapter:

| Call | Does |
| --- | --- |
| `what_am_i_working_with` | Bounded orientation: audit/state/revision/allowances, exact question/material access, current element handles/versions, recent completed receipts and relevant refusals; explicit reads/pages retrieve the remainder. |
| `list`, `read`, `search` | Reach the material. |
| *coupling slots* | Fill the answer's shape, e.g. `record_premise`. |
| `add`, `replace`, `delete` | Edit free-form answer elements. |
| `prepare`, `submit` | Prepare a manifest and handle; submit is a dry run unless confirmed, and confirming seals. |

Every reply opens with a header line saying where the auditor is. Every refusal
gives a reason, its effect on the answer, and the next call. As proposed, every
citation is checked against the material, byte for byte; that check is one of
the answer-form choices still to be decided.

The ledger is the only truth. A call either appended a complete record or it did
not; a torn record is a diagnostic, never an element. A fresh add creates another
element, even with equal bytes. After an uncertain reply, re-entry shows completed
effects so the auditor can decide what remains to do. It is not a required stage
before each edit, and blind repetition of a fresh add is not promised harmless.

Replace respects the exact element/version and explains a stale target with its
current handle; it cannot overwrite a newer edit. Repeated deletion of the exact
already-deleted target reports the recorded removal; other stale targets retain
their diagnosis. Confirmed submission with an accepted handle retrieves the
recorded seal, including after close, with its actual attribution. No reply
invites authoring after sealing or closure.

A known invocation with exact arguments and a completed ledger outcome can have
that result redelivered without another mutation. A fresh call with matching
arguments is not that identity. Uncertain effects are not guessed absent or
settled by silently completing an older authoring request. There is no auditor
request-key knob or recovery console. Operational diagnostics remain Stewart's
account, not fabricated answer elements or conclusions.

Re-entry supplies exact counts and retrieval routes, rather than dumping an
unbounded question/answer into model context. Read question bytes verbatim; mark
excerpts explicitly. Page the answer at a bound revision and refresh after edits
instead of mixing versions. It restores recorded work and access, not unrecorded
thoughts or reset allowances. No private custody paths enter the auditor's view.

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
  answer/            the structured answer and recorded elements, plus the
                     deterministic Markdown rendering generated during prepare
                     and sealed as an identified Stewart-attributed member
```

Preparation makes the rendering inspectable without a mandatory pause; the handle
binds its exact bytes with the source selection. Rendering preserves the author's
statements without adding interpretations or operating history. Delivery and
readback use those sealed bytes, never a rendering regenerated with a later form.
When close seals unsubmitted work after launch, it applies the same rendering rule
with manager seal attribution and no claim of auditor review. Rendering failure
uses the existing custody continuation; no owed member silently disappears.

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

- **Ordinary calls take tens of milliseconds.** Startup, `status`,
  `what_am_i_working_with`, answer edits, auditor `prepare` and `submit` answer at once.
- **Size-bound work shows its scope and progress.** Manager preparation and source
  scanning, intake copying, commission readback,
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
| `stewart new` | Creates the ordinary preparation scaffold and reference. |
| `stewart prepare` | Records the selected names, hashes and settings and returns a handle; accepts no commission. |
| `stewart commission` | Takes the prepared handle and explicit acknowledgment; copies, verifies, checks the source and records acceptance before issuing the receipt and run line. |
| `stewart receipt REF` | Retrieves the original commission and readback item IDs; `--read ITEM` returns verified original bytes. |
| `stewart run` | Places the auditor and runs it, delivering a sealed answer at the end. |
| `stewart status` | States the run, answer seal, delivery and closure facts for an audit, or each audit in an inquiry, with explicit references and next actions. |
| `stewart close` | Before launch, ends preparation or the accepted commission without creating an answer. After launch, stops as needed, seals unsubmitted work with manager attribution, and completes owed delivery and closure. |

Every exceptional response names the failed operation and cause, established or
uncertain acceptance, known partial effects, retained locations and a supported
next action. A failed reply may follow acceptance; unavailable evidence is not
absence. Errors in recording or delivering diagnostics preserve the original
failure and their own uncertainty. Human and JSON presentations carry the same
facts; raw receipt readback instead puts bytes on stdout and qualifications on
stderr. A process unable to start or report cannot promise an immediate response;
the calling interface and later access through the reference account for the
missing result. Exact implementation and qualification remain pending.

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

Preparation leaves the manager's folder ordinary and editable. A reference can
accept one commission; another requires an explicit new reference. Failed attempts
keep their own intent and partial effects. An accepted handle repeated after a
lost reply retrieves its acceptance, even if the folder was subsequently edited;
uncertainty must be reconciled before another capture. Close before launch ends
work under that reference without manufacturing an answer or answer-placement confirmation.
It accounts for failed intake without requiring successful submission. Real
custody loss remains distinct. Close coordinates with in-flight intake, prevents
future launch, and continues through close if its own operations are unfinished.

Acceptance fixes the captured question and material. Runs may be interrupted and continued
on that commission until the answer is sealed or the audit ends. An auditor
submission or manager close seals the answer once. Delivery and its verification
follow that seal; close records the end after the required confirmation and
stopping evidence. A run ending at a limit without submission has no automatic
auditor seal. A closed audit with an explicitly surrendered delivery loss stays
labelled that way, never as a completely delivered return.

Stewart's home is the manager's explicitly designated archive, independent of the
preparation folder and answer destination. References bind that store and audit;
changing directories, installations or configuration cannot select another store.
Acceptance fulfills original-input custody there, with independent verified
readback. The receipt names the location and actual custody arrangement.

The first release keeps copied materials, arrangements, ledger/conversation,
attempts, partials, failed stages, superseded/deleted answer payloads, seals,
delivery and closing records. No close, retry, storage pressure or age permits
physical deletion, and no purge/prune/hold-release service ships. Close still
establishes stopping and accounts for delivery; retaining internal bytes does not
satisfy a separate promised destination. Earlier recorded holds remain unchanged.

The manager owns ongoing storage availability and backup. Ordinary host access
can read the archive even while a run is active; the product does not promise
secrecy from that owner. The manager's supported live commands remain receipt,
status and close, without an answer/conversation viewer or steering channel.
Archive paths stay outside the auditor's tool world. External deletion or movement
can break references and is not a supported repair; a closed marker grants no
blanket disposal authority over independent obligations.

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
- A question-family library of open inquiry, inquiry framing and comparison;
  concrete forms and modules remain to be specified. The earlier
  `survey` and `claim-check` illustrations do not select the release library.
- `help`, `new`, manager `prepare`, `commission`, `receipt`, `run`, `status` and `close`,
  all within the response budgets.
- Release binaries for Linux x86_64 and aarch64, built and tested in the apparatus.
- A handoff package for a WSL2 run: the release binary plus the test suite's
  driver and fake provider, run natively in WSL2, since WSL's own environment is
  what's being tested.
