# Orientation trial for agent auditors (prepared, not commissioned)

Prepared 2026-10-28 at the user's direction: “We'll feel this out later with
testing, perhaps much later. We should plan that testing now (put some agents in
the auditor space with short guidance and some without and see what's up), but do
it outside this session.” This is a plan for a later, separately commissioned
trial. Running it needs that commission, a working auditor tool and, for real
auditor sessions, the user's explicit permission for the bounded Claude launches
and usage headroom (coordination standing orders).

## The question

Does a short static orientation in the auditor's space change how agent auditors
use that space and the submission tool? The orientation is a small file at the
workspace root, written once at setup: what the space is, where the question and
supplied materials are, how to record the answer, and “lost track? run inspect”.
Nothing is generated per material and nothing summarizes content.

The user's attention hypothesis (limiting what is present may improve focus on
the question) is something to notice, not a score. Stewart stays agnostic about
the intellectual value of answers: no arm is judged by answer quality or by
agreement with a preferred conclusion.

## Arms

Each arm gets the same commission, materials, tool, enclosure and launch prompt;
only the orientation differs.

- **A, none.** Materials and tool only; the launch prompt names the question file.
- **B, short orientation.** A plus the orientation file (a few lines).
- **C, orientation plus role guidance (optional).** B plus the successor auditor
  guidance that acclimates the agent to the role.

## Situations to include

Use two or three finite commissions from existing study material, so no new
question type is introduced. Within sessions, provoke the situations the case
table cares most about:

- context compaction partway through (forced by the harness, or a restart from a
  summary), to observe re-entry;
- an interrupted add, to observe whether the auditor finds and resolves it;
- a question that refers to material not supplied, to observe whether the gap is
  stated in the account rather than searched for;
- a workspace file edited after it was added, to observe whether the auditor
  replaces it.

## Controls (per AGENTS.md)

- **Firing control:** a case where orientation should plainly matter, such as
  compaction with no other recovery cue; if A and B behave identically there,
  the measure is not sensitive.
- **Differing case:** A versus B on the same commission and provocation.
- **Invariance case:** reword the orientation without changing its content, or
  rename supplied files; behavior should not hinge on wording or names.
- Repeat each cell at least twice, since agent variability could explain a
  single difference.

## Observations

Behavioral, captured from the tool's own records and the session transcript,
with an independent witness of the space's files kept outside it:

- calls to recover after compaction, and whether the first call is help, inspect
  or a filesystem search;
- improvisation: answers left only in the workspace, searches for custody,
  reads outside the supplied materials, direct edits to tool storage;
- whether each sign's next action was followed;
- whether a missing-material gap appears in the account;
- whether the question was reread after compaction.

## Size, stopping and evidence

A first pass of 2 commissions × 2 arms (A, B) × 2 repeats is 8 sessions; add C
only if A and B differ. The number of Stewart auditor sessions is set by the
access-route document (PLAN-FIT item 1) and approved at commissioning. Stop on any
custody damage or unexpected host effect, preserving evidence. Retain transcripts,
tool records and witnesses under the evidence-run rules; an independent reviewer
reads the observations before any conclusion is drawn.

## Dependencies

- A working auditor tool from the first custody/delivery leg, or a faithful stand-in.
- A prepared auditor space, which belongs to the later input-preparation leg; a
  hand-built space can substitute for this trial if it is labelled as such.
- The enclosure used, recorded as part of the setup, since it is contingent.
