# Stewart

*A problem router for cooperative actors who want to make it **just** so.*

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
  material, pick the shape the answer should take, and set the budget. They are
  cooperative, may state preferences (that is their business), and are
  responsible for the answers their choices produce.
- **The auditor owns the answer.** Also cooperative. A model to begin with, a
  person later.
- **Stewart owns the arrangement and the record.** It situates the auditor
  faithfully, records what happened, and delivers the result.

## Principles

- **Responsibility follows authorship.** Whoever wrote something owns it: the
  manager the question and material, the auditor the answer, Stewart the
  arrangement.
- **Opinionated about form, agnostic about conclusions.** Stewart's opinions about
  what an answer should look like live only in its coupling files and the
  auditor's orientation. Those are versioned, readable, recorded in every receipt
  and shown to the manager before a run. Stewart never judges whether an answer is
  right, valuable or welcome.
- **The world is the arrangement.** For a model, that means its tool list and
  nothing more. For a person, it means the packet they receive and their agreement
  to work from it.
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

```json
{
  "schema": "stewart.problem/1",
  "id": "parser-2.4",
  "question": "/work/q/parser-2.4.md",
  "material": ["/work/src/parser/", "/work/exports/parser-history.txt"],
  "coupling": "claim-check",
  "claim": "The 2.4 parser accepts every input the 2.3 parser accepted.",
  "auditor": { "adapter": "model", "model": "claude-opus-5-5", "effort": "high",
               "limits": { "turns": 200, "tokens": 4000000, "minutes": 120 },
               "compaction": "on", "reasoning": "summarized" },
  "destination": "/work/returns"
}
```

- **Question:** the manager's words, delivered verbatim.
- **Material:** files and directories, copied and verified at intake. Anything that
  lives elsewhere (history, test output, logs) comes in as exported files.
- **Coupling:** the shape the answer should take, plus any fields that coupling
  asks for.
- **Auditor:** which adapter, and its settings.
- **Destination:** where returns go.

## Couplings

A coupling is a small versioned file that wraps the manager's question. It never
rewrites the question. It contributes:

- **an answer shape:** named slots, which the protocol exposes as tools;
- **a stopping rule:** stated so that every conclusion finishes at the same point;
- **the universal exits:** *wrong question*, *missing evidence*, *nothing found*;
- **the prior:** whether a claim the manager supplies is shown to the auditor as
  its subject or kept sealed.

```
coupling: claim-check@1
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

The library starts with two couplings:

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

`stewart preview` shows the arrangement exactly as the auditor will meet it,
before anything runs or costs anything. The arrangement's digest goes in the
receipt.

## The protocol

The protocol is the same for every adapter:

| Call | Does |
| --- | --- |
| `what_am_i_working_with` | The question verbatim, the materials index, the current answer, and any unresolved operations or submission errors. |
| `list`, `read`, `search` | Reach the material. |
| *coupling slots* | Fill the answer's shape, e.g. `record_premise`. |
| `add`, `replace`, `delete` | Edit free-form answer elements. |
| `prepare`, `submit` | Prepare a manifest and handle; submit is a dry run unless confirmed, and confirming seals. |

Every reply opens with a header line saying where the auditor is. Every refusal
gives a reason, its effect on the answer, and the next call. Every citation is
checked against the material, byte for byte.

## Adapters

An adapter does three things: it delivers the arrangement, carries protocol
calls, and reports when a run ends.

**Model adapter.** Stewart's own thin loop over the Messages API. The model's tools
are the protocol, so its world is exactly the arrangement. Compaction and reasoning
display are the manager's settings. The full conversation is kept for the
manager to read.

**Person adapter.** The same protocol through a humane command line, and in time
carried to wherever the person works. The person works from the arrangement by
agreement.

Every return names the adapter that produced it and how that adapter holds the
auditor to the arrangement. Any other way of working, such as running code or
another harness, is a new adapter. Stewart itself doesn't change.

## The return

The auditor seals with `submit`, or the manager seals with `collect`. Stewart
delivers to the destination, then reads everything back to verify it:

```
parser-2.4-7QK3RM-copy-1/
  MANIFEST.json      every member and its digest; who sealed it
  QUESTION.md        verbatim
  ARRANGEMENT.json   frame, coupling and version, tools, limits
  RECEIPT.json       the material as copied
  answer/            rendered by the coupling, plus the raw slots and elements
  RECORD.json        adapter and settings, access log, unresolved operations,
                     run summary
```

Every instance of a coupling renders the same way, so returns are comparable
across audits, materials and models.

## Iterating

- `stewart commission --like ID` starts from an earlier problem, with overrides.
- `stewart compare` lays out returns of the same coupling side by side.
- Each audit records what it was varied from, so a sequence of attempts reads as
  one.

## Responsiveness

The manager and the auditor should never wait on Stewart, and never wonder what
it did.

- **Ordinary calls take tens of milliseconds.** Startup, `status`, `preview`,
  `what_am_i_working_with`, answer edits, `prepare` and `submit` answer at once.
- **Size-bound work shows its size first.** Intake copying, search across all the
  material, and delivery state how much they are about to handle, report
  progress, and finish with what they verified.
- **Every reply carries its own certainty.** What changed, what was checked, and
  what to do next, in the same place every time. A reply never says "probably".
- **Speed is tested.** Response budgets are part of the test suite, measured on
  material at the size limits.

## The manager's surface

| Command | Does |
| --- | --- |
| `stewart new` | Scaffolds a problem file for a chosen coupling. |
| `stewart preview` | Shows the arrangement exactly as the auditor will meet it. |
| `stewart commission` | Copies and verifies the material and issues the receipt. |
| `stewart run` | Places the auditor and runs it. |
| `stewart status` | States where every audit stands. |
| `stewart collect` | Seals what is recorded, attributed to the manager. |
| `stewart deliver` | Makes another verified copy of a sealed return. |
| `stewart compare` | Lays returns side by side. |
| `stewart close` | Records the end of the audit once the manager confirms the copy is placed. |
| `stewart help` | A short cheatsheet; detail per command. |

Every command fails early with a reason and a next step. Every command can answer
in JSON, for managers who are agents.

## Lifecycle and storage

```
problem ─▶ commissioned ─▶ running ─▶ sealed ─▶ delivered ─▶ closed
                              └─ ended ─┘ (collect)
```

Each audit lives under Stewart's home as write-once records: the copied material,
the arrangement, every protocol call and its outcome, the conversation, the seal
and each delivery. Stewart deletes nothing. Closing is a record; removing an
audit's directory is the manager's ordinary housekeeping.

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
- `survey` and `claim-check`.
- `new`, `preview`, `commission`, `run`, `status`, `collect`, `deliver`, `compare`,
  `close` and `help`, all within the response budgets.
- Release binaries for Linux x86_64 and aarch64, built and tested in the apparatus.
- A handoff package for a WSL2 run.
