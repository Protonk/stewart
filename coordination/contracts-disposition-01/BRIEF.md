# Brief: disposition of CONTRACTS under the 2026-10-28 design

Dispatched 2026-10-28 by the coordinator. Source revision: `7e49301` on `main`,
clean tree. Read-only assignment except for the files named under Output.

## Purpose

The design review of 2026-10-28 decided a new mission and new successor
interfaces, recorded in CONTRACTS.md under "Mission" and "Successor interfaces
decided 2026-10-28". Many earlier contracts assume material held in Git, a
Python reference baseline, an auditor checkout with a shell, manager-operated
stages, separate collect/deliver/export commands, or removal of material at
close. Before those contracts are restated or retired, a reader who was not
part of the conversation must say, section by section, what each becomes under
the decided design, and what would be lost silently if the earlier text were
simply dropped. This is the check RESERVATIONS.md item 16 asked for.

## Read

- `CONTRACTS.md` in full. The decisions are its Mission section, its Principles,
  and "Successor interfaces decided 2026-10-28". Paragraphs marked *Superseded*
  or *Narrowed* in place are already disposed; include them in the table anyway.
- `coordination/linux-mvp-01/ROUTER.md` and `END-TO-END.md`: the settled design
  sketch and test design. They are coordinator proposals except where CONTRACTS
  records a decision; say which kind of statement you rely on.
- `coordination/linux-mvp-01/RESERVATIONS.md`, items 13 and 16.
- `AGENTS.md` at the root: the custody rules written for the old design.
- `coordination/linux-mvp-01/CONVERSATION.md` only if a decision's reason is
  unclear from CONTRACTS; the user's words are the quoted prompts.

## The decided design, condensed

User decisions (CONTRACTS records them): the auditor has only Stewart's tools and
Stewart runs the auditor; Linux only; no Python reference baseline; no Git, with
history arriving as exported files; the manager owns the question's wording and
the material's selection and may state preferences; one re-entry call makes
compaction harmless; "fast" means the app's responsiveness, not audits;
containers for build, test and experiment, one static binary ships; a
real-model conformance gate; the auditor's tool is a form and a ledger (ledger
truth, auditor retry, no settlement by Stewart, no unresolved-operation state);
the manager's unit is the inquiry and the operations after the question are
receipt, status and close; the run is a separate command the harness may
escalate to a person; a Markdown problem file with advisory checks; the return
is only what the auditor submitted and prepare accepted; a dead run is
continued as the same undertaking, with no restart convenience.

Coordinator proposals not separately decided: Stewart never deletes anything
and close is a record; the access log; the home layout; command spellings;
response-budget numbers; the coupling library's two starter forms and slots as
tools; mechanical citation checks; the reminder and near-limit nudges.

## Output

Write to `coordination/contracts-disposition-01/`:

- `PROGRESS.md` first: start time, revision, your plan; update at milestones.
- `RETURN.md` with four sections:
  1. **Table.** One row per CONTRACTS heading (`##` and `###`) and per bold
     paragraph title inside Principles, the three successor sections and Close.
     Columns: location (heading or title, with line numbers at `7e49301`),
     disposition, one-line reason. Dispositions: **Carry** (holds as written
     under the decided design); **Restate** (holds in spirit, phrased for Git,
     the checkout, Python or removal, needs rewording); **Retire** (depends on
     something the decisions removed); **Undecided** (needs the user, say why).
  2. **Would be lost silently.** Obligations or protections in the earlier
     contracts that the decided design and ROUTER do not mention. Cover at
     least: holds; Stewart's process promises to the auditor (raw capture before
     interpretation, a disposition of every gap, attribution never turned into a
     verdict); managers' independent workspaces; the close details; export and
     evidence packages; evidence interpretation across implementations; writer
     continuity and runtime handoff; request keys; legacy Python records. For
     each: what it protected, whether the decided design makes it moot, and your
     recommendation with its reason.
  3. **Contradictions.** Places where ROUTER.md or END-TO-END.md contradict a
     decided contract, or where two decided paragraphs contradict each other.
  4. **Counts.** Rows per disposition, and the total against the number of
     headings and bold titles you found.

Label every recommendation as the reviewer's. The user decides; the coordinator
integrates.

## Constraints

- Read-only outside the output directory. No Git command that changes state.
  No network. No Claude launches. Do not edit CONTRACTS.md or the design folder.
- Checkpoint PROGRESS.md before substantial work and roughly every ten minutes.
- Finish RETURN.md before replying; the reply is a summary, not the deliverable.

## Completion

RETURN.md exists with sections 1–4; the table's row count equals the count of
headings and bold titles reported in section 4; every "lost silently" item has
a recommendation and reason.
