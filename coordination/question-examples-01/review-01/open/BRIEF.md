# Bounded paper-auditor assignment

Authorized by the user, 2026-10-29. Source revision: `a7c94438584e433303811fb14c170f906b567504`.
Your task is one independent attempt using the supplied question, materials and
proposed tool card. You are a development review worker acting through a paper
interface, not a real Stewart auditor. No Stewart tool is implemented here.

## Read and write scope

Read only this BRIEF.md, files recursively under `coordination/question-examples-01/review-01/open/inputs`,
and your own outputs under `coordination/question-examples-01/review-01/open/outputs`. This brief carries the
applicable dispatched-worker instructions; do not perform coordinator intake.
Do not read ancestor coordinator notes, CONTRACTS, sibling packets, authored
walkthroughs, Git history, repository source, reference solutions or other files.
The input files are your entire material world. Existing developer/system safety
instructions still apply. Do not browse the web or use external accounts.

Write only your output directory. Do not edit inputs or the root repository,
commit changes, launch sub-agents, start external models/Claude, run a container,
or execute/import the material code. You may use isolated `python3 -I -B` and
standard-library file reads to verify cited byte ranges, never to run snippets.
Use `rg` or explicit file reads rather than broad repository scans.

## Attempt and outputs

Save an initial CHECKPOINT.md before substantial work. Complete one attempt,
aiming to finish within ten active minutes; do not iterate toward a preferred
conclusion. If blocked by an unspecified rule, record the point rather than
inventing product behavior. A missing reply schema may be represented symbolically
when its meaning is specified, but say what is symbolic. Stop at twenty proposed
Stewart calls; development reads/writes are not Stewart calls. If unfinished,
retain the draft and say where you stopped. No real submission occurs.

Create these files:

- TRACE.md: numbered proposed Stewart calls, concrete arguments, illustrative
  responses or explicit unresolved questions. Include actual proposed
  prepare/confirmed-submit behavior if you reach it. No fake receipt digest.
- ANSWER.json: an array of the current family entries in recorded order, each
  with `tool`, `text`, and `citations` fields. This is a development witness for
  checking the trace/rendering, not a new Stewart wire format. If using a free-form
  artifact, preserve it separately and name its relationship to the trace.
- RETURN.md: the corresponding Markdown output following the supplied card,
  without reviewer commentary. Do not add question text or source bytes unless
  you recorded them as answer entries. Attribute substantive text to the auditor.
- FRICTION.md: at most five concrete problems with an exact call, field, response
  or instruction, and what you had to guess. Disagreement with the question or
  absent materials is not automatically a tool failure. Include a short scope
  account listing actual files read and whether anything outside scope was seen.
- CHECKPOINT.md: finish by recording the paper outcome (submitted/unsubmitted/
  blocked), total proposed call count, files produced and remaining uncertainties.

Keep conclusions and limitations attributed. There is no expected finding or
answer length; do not infer a desired answer from this assignment. No mandatory
positive finding, winner or complete form coverage is required. The parent owns
integration and any changed product obligations. Send the parent a brief final
status with output paths; do not keep working after returning.
