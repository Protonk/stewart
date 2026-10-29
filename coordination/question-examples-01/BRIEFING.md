# Three examples and a small pressure test

Prepared 2026-10-29 under the user's request for worked examples and a briefing
on how sub-agents could pressure-test them. Base revision: `1ba28ac`. This is
design preparation, not permission to launch the proposed review or start Rust
implementation. No sub-agents, provider calls or product tests ran. The example
files and reports are invented; they are not evidence about a real service.

The question families, enforcement policy and sealed Markdown rendering are
decided in [CONTRACTS.md](../../CONTRACTS.md). The concrete tools, schemas and
rendered layout here are proposals to make those decisions reviewable. Do not
import the examples as default contracts merely because they are written down.

## One small world, three tasks

A reminder service stores a sent marker and asks a gateway to send a message.
Implementation A sends before marking; B marks before sending. The selected
requirements ask for no duplicate messages and eventual delivery after a restart.
The packet states simplifying assumptions and does not describe the whole app.
An explicitly fictional supplied report covers A only. Auditors can inspect
these files; they cannot run the snippets or obtain missing evidence.

| Family | Manager's request | What the example exercises |
| --- | --- | --- |
| [Open inquiry](open/WALKTHROUGH.md) | "Audit our app to make sure there are no bugs." | Commission a broad request unchanged, return a bounded account, distinguish a supplied report from source inference, and make the whole-app limit visible. |
| [Inquiry framing](framing/WALKTHROUGH.md) | Investigate the concern that reminders might annoy people or disappear. | Make the chosen working question and its relationship to the concern explicit, then do actual investigation within the same commission. |
| [Comparison](comparison/WALKTHROUGH.md) | Compare A and B against the two requirements under the supplied assumptions. | Connect each tradeoff to the criterion, distinguish source reasoning from execution, and allow an inability to select an overall winner. |

Each walkthrough contains an ordinary submission folder, usable material
references, proposed calls/replies, a literal illustrative Markdown return and
an inadequate-evidence variant. The [tool card](TOOLS.md) defines the proposed
operations, so a reviewer can point to a missing rule instead of filling it in
from familiarity with Stewart. Model/provider settings, destinations and archive
selection are outside this exercise. The front matter identifies only the family
and inquiry under a candidate format; these folders are not claimed runnable
inputs to the current Rust commission binary or a finished successor CLI.

The authored returns demonstrate expressibility, not preferred conclusions.
Reviewers may produce different conclusions or no finding. What matters is
whether the interface permits them to state the work, basis and limits without
guessing semantics or inventing evidence.

## Questions the examples already expose

- The minimal tools name answer sections but keep reasoning in prose. Is that
  enough to teach a useful evidence discipline? It deliberately avoids a large
  set of finding types, but a reviewer may find a concrete relationship that
  needs a structured representation.
- Multiple framing or criterion entries are preserved in order. Can a reader
  tell whether they are alternatives or a revision, or should the tools make
  that relationship explicit? Do not silently choose the last entry.
- Preparation counts sections, not the quality of their prose. A limitation can
  be an honest completed account while a comparison section is absent. The
  coverage display must not imply a failed or inferior submission.
- Mechanical citations can be valid yet unhelpfully broad or irrelevant. The
  examples cite short complete files; pressure-test whether the tool card makes
  narrower references straightforward and avoids implying semantic validation.
- An open auditor can discuss the scope it actually examined. The distinctive
  inquiry-framing task is selecting and explaining a working question; an
  ordinary scope qualification must not become an unauthorized reframing claim.

## Proposed sub-agent exercise

Use the available in-session sub-agent harness, with three fresh agents and no
inherited conversation (`fork_turns=none`). No separate provider/Claude launch,
runtime integration or experiment infrastructure is needed for this review.
The first wave fits three workers plus the coordinator. Keep the exercise to one
short attempt per worker and one integration pass.

1. **Open auditor:** receive only the open manager question, selected materials,
   common tool card and open instructions. Work the ordinary case.
2. **Framing auditor:** receive only the framing question, selected materials,
   common tool card and framing instructions. Work the ordinary case. Its chosen
   working question need not match the authored example.
3. **Comparison auditor:** receive the comparison question and the inadequate
   packet with B absent, plus the common card and comparison instructions. This
   makes missing evidence a first-class task, not an afterthought in a critique.

Materialize the selected cards/packets before dispatch; do not give workers this
briefing, the worked answers, sibling packets, the full conversation or the
withheld files. A fresh context matters especially for the missing-B case.
The packets are cooperative read scopes for a paper exercise, not an enforced
Stewart auditor sandbox. Inspect the workers' actual reads where the harness
exposes them; any exposure to withheld material qualifies that result.

Each worker returns a compact proposed tool-call trace, its resulting answer,
and up to five concrete friction points. A friction point names the exact call,
field, reply or instruction and what the worker had to guess. Where the card
does not determine a response, mark it unresolved instead of inventing product
behavior. The trace is a paper walk-through, never a claim that real tools ran.

Then use **one fresh reader agent**, sequentially, with only the three original
manager questions, those workers' returns and the relevant manifest attribution.
Ask it to identify what was investigated, what remains unanswered, who supplied
each judgment and whether any wording implies broader assurance than the answer
supports. It does not see the intended interpretation or author solutions. This
tests whether the return can stand on its own in the agreed manager context.

The coordinator checks source/reference validity and fidelity, then tries four
small paper controls against the card: an invalid quotation; a valid but irrelevant
citation; an empty selection; and two contradictory entries. The expected
mechanical effects are prescribed by CONTRACTS, not by agreement with an answer.

Save dispatch briefs and admitted inputs before launch, with exact source revision,
allowed reads, exclusive output directories and a short completion bound. Workers
write only their assigned trace/return/friction files, keep an initial checkpoint,
do not modify examples, and do not launch nested agents or external models. The
coordinator owns integration. No workers have been dispatched for this briefing.

## What would count as useful evidence

Produce a short table: problem observed, exact supporting trace/text, form or
wording change proposed, and whether it needs the user's decision. Routine wording
repairs can be integrated; changed obligations, extra gates or substantive answer
restrictions return to the user. Preserve the original packets and outputs.

Revise once, then rerun only a case whose actual failure needs checking, in a fresh
context. If the bounded exercise exposes a deeper unresolved issue, report it
instead of expanding into repeated agent debate. This initial wave covers three
tasks and one incomplete-material case, not every family/variant combination.

The exercise can show that a reader got lost, an auditor had to guess, a form
pressed toward invented evidence, or a conclusion exceeded its recorded scope.
It cannot establish runtime custody, real tool reliability, supported-model
conformance, intellectual usefulness of audits or statistical robustness. Those
claims require different evidence. The real model gate remains later and bounded
by its own authorization.
