# Stewart auditor-interface study

Use inexpensive Haiku runs to investigate how Stewart presents and supports an
inquiry. The principal's goal is unobtrusive auditor-facing machinery, with a
useful balance between discoverability and verbosity. An equally sufficient
answer with more natural prose or less mechanical effort can be a substantial
success. Minimizing tokens, tool calls or answer length is not the objective.

This plan owns local preparation and remaining work. The
[design advice](riker/INTERACTION-STUDY-ADVICE.md) and
[scope clarification](riker/INTERACTION-STUDY-CONTEXT.md) inform it.
Product obligations remain in [DESIGN](DESIGN.md), [CONTRACTS](CONTRACTS.md),
[INTERFACE](docs/INTERFACE.md) and [QUESTION-FORMS](docs/QUESTION-FORMS.md).
Planning and inspection evidence is retained in `.scratch/interaction-plan-01`.

## Scope and division of work

Keep the manager side deliberately uninteresting. Fix the questions, families,
evidence and other commission settings locally for each comparison. The local
agent may operate as manager within the principal's authorization, but improving
manager workflows or designing a manager interface is outside this study.

The principal and Riker develop the inquiries and rough standards for answer
sufficiency. Current candidates include a manageable code-and-evidence inquiry
in frsrr, with completeness or consistency variants, and a saturated numerical
question that permits partial answers or inability. These are provisional inputs,
not local question-development tasks. Do not inspect those projects or invent
replacement problems just to advance the apparatus.

The local focus is the auditor's initial context, family instructions, tool
descriptions, evidence presentation, citation handling, recording and revision
tools, and preparation/submission exchanges. Treat these as a coherent interface
whose current shape can be questioned. The first intervention, experimental
sequence, exact interfaces and run counts remain open.

Reading the returned answer is part of assessing the effect on auditor behavior.
A separate manager-facing receiving redesign is not current work. Existing
returns remain useful for inspection and explicitly labeled study views.
A document-oriented answer is a candidate, not a selected destination.

## Design question and boundaries

How much scaffolding should the auditor encounter, in what form, and when?
Separate what must be readily discoverable from what must be explained in full
on every request. Test relocation as well as shortening:

| Exposure | Candidate contents | Failure to watch for |
| --- | --- | --- |
| Initial context and tool definitions | The assignment, material/access boundary, ways to read and save work, legitimate inability, and how to finish deliberately. Brief routes to further detail. | A capability or necessary distinction becomes undiscoverable. |
| At the relevant action | Exact citation references with reads/searches; usable revision handles with writes; actionable validation failures; candidate identity and next actions at preparation. | The reply omits information needed to act or repeats a large operating manual. |
| On inspection | Detailed history, expanded citation metadata, full saved state and less common operating details. | Extra lookup effort or repeated errors outweigh the quieter normal path. |

These are hypotheses, not prescribed partitions. Tool schema requirements and
discoverability may limit what can be moved. An on-demand capability still needs
a clear way to find it; moving a description to a help tool does not make it free.

Preserve custody, attribution, captured evidence integrity, revision history and
explicit submission. Internal handles may be presented more economically without
silently overwriting work or committing different content. Do not confuse an
auditor's submission with a manager's closure of unfinished work. Missing sections,
partial answers, inability and an empty return remain expressible.

Question families convey an assignment, not necessarily a report anatomy. The
authorial artifact, annotations and custody history need not share one shape.
Keep one authoritative recorded answer with identifiable revisions; a presentation
or independently generated summary cannot quietly replace it. Annotations must
distinguish authored claims, mechanical facts and presentation metadata.

Interface choices can influence reasoning. Record when an intervention adds an
interpretation, suggested investigative sequence or substantive guidance, so its
effect is not attributed solely to easier operation. Preserve the inquiry's
purpose without steering the auditor toward reference conclusions or prescribing
its intellectual procedure.

## Current evidence and candidate friction

The six-audit pilot remains in `.scratch/c10-haiku-commission-01` and
`.scratch/c10-live-01` through `.scratch/c10-live-06`. Its observations include
repeated conclusions across categories, seven citation refusals and one cursor
refusal, and no reads of the prepared rendering. These observations suggest
questions; they do not establish which interface choices caused the behavior.

Read-only inspection of three retained arrangements is recorded in
`.scratch/interaction-plan-01/auditor-surface-01.json`. They expose 12 or 14
tools. Compact-JSON tool definitions occupy 8,087–10,015 UTF-8 bytes, compared
with 2,318–2,513 bytes for the system blocks. Citation schemas occur in four or
six tools. These are byte measurements, not token attribution or attention scores.

| Surface | Opportunity to examine | Necessary comparison |
| --- | --- | --- |
| Recording vocabulary and repeated schemas | Fewer overlapping authoring concepts; different tool organization or optional annotations. | Natural composition and preserved partial work versus reduced discoverability or blurred distinctions. |
| Citation operands | Reuse exact references returned by reads/searches with less copying. | Fewer invalid calls without weakening exact-location and explicit-quotation checks. |
| Successful write replies | Show actionable saved state and references; make repeated record metadata inspectable. | Less history clutter without hiding actual effects or making revisions harder. |
| Initial guidance and tool descriptions | Short capability guidance with contextual detail; avoid repeating the same operating advice in several places. | Sufficient discoverability versus clarification calls, refusals and confusion. |
| Expected-section notices | Different wording, timing or exposure of advisory structure. | Less category-driven repetition while retaining useful orientation and the ability to submit incomplete work. |
| Revision and preparation/submission | Clear saved versions, optional preview and deliberate commitment with economical exchanges. | Correct revision submitted, recoverable history and explicit intent under normal and stale-state cases. |
| Evidence discovery | Source organization, indexing, read/search context and presentation of captured material. | Lower discovery effort, with any additional interpretive guidance identified. |

Changes to reply shape, tools or submission gestures may require specification
and implementation changes. Their current forms are not immutable study
requirements, but a candidate must state how it preserves the underlying
obligations. The matrix is a menu, not a mandatory sequence of experiments.

## Local preparation

- [ ] Prepare the smallest study route for an explicitly supplied submission
  folder and bounded run packet. The current C10 launcher validates exactly six
  specimens in [common.py](apparatus/c10/common.py) and instantiates them in
  [batch.py](apparatus/c10/batch.py). Keep that conformance catalog intact.
  Identify reuse of launch, intake witnessing, capture, review and custody
  collection rather than building another general experimental framework.
- [ ] Preserve question/material identities and source mapping. Establish any
  conversion to Stewart's current UTF-8 material format when the actual sources
  are supplied. Keep reviewer sufficiency notes distinguishable from model
  inputs; any deliberate inclusion in the commission must be explicit.
- [ ] Identify concrete places to vary the auditor-facing arrangement and
  replies. Packaging can vary through submissions; instructions, tool definitions
  and rendering are pinned and may need a new build. Record the actual exposed
  variant rather than mutating an accepted arrangement in place.
- [ ] Inspect initial context, repeated replies and relevant-action detail
  separately. Use retained traces and small offline examples to prepare
  candidates; question selection need not block this preparation.
- [ ] Exercise changed operations with appropriate small cases and controls.
  Include stale revisions, invalid citations, incomplete/empty returns and
  intervening edits where relevant. A simulator may answer an isolated question
  but is not evidence of production custody or a substitute for using Stewart.

Before implementation edits, identify the applicable
[DEVELOPMENT checks](DEVELOPMENT.md#what-to-run-for-what-you-changed) and follow
the independent-driver authoring rule. Reusing a launcher does not transfer its
qualification to changed paths or larger workloads.

## Lightweight iteration

For each intervention, retain a short note: what prompted it, what changed,
what observable difference was expected, and what happened. Link the note to
the relevant submission/build and saved traces. Plain text is sufficient.
The product's `inquiry` label and `varies` reference can associate audits if
the study route preserves them; the latter is a manager's attributed note,
not a verified comparison. No scoring service or elaborate report is needed.

Keep answer sufficiency and interface friction as separate observations. An
adequate answer can conceal substantial mechanical effort; an insufficient
answer can still show a useful interface improvement. Resource exhaustion,
provider problems and apparatus failures need their own account. Returned
source text does not prove understanding, and one unsuccessful answer does not
identify reasoning or the interface as its cause.

Inspect discoverability, navigation, copying and repair, revision effort,
category-driven prose, recovery and commitment. Record calls, turns, reported
or estimated usage and timing when useful. Do not optimize a count in isolation.
For both proposed inquiries, inability or a partial result must be an available
intellectual outcome, not a reason to demand filler or automatic continuation.

- [ ] Once a chosen inquiry is supplied, prepare an authorized baseline or
  initial comparison. Fix exact model/settings, source versions, allowances,
  request-attempt policy, watchdog and stop conditions. Verify compatibility and
  costs when freezing the packet; the prior pilot grants no new spending.
- [ ] Size allowances for the actual workload. Input use is cumulative across
  requests; repeated evidence can be expensive in context. Do not infer model
  inability from a limit stop or silently rely on unqualified compaction and
  continuation paths.
- [ ] Select changes from observed friction or plausible simplification.
  Hold commission settings fixed except where an explicit evidence-presentation
  variant is the intervention. Changes to completeness or consistency are
  distinct conditions, not invisible differences in an interface comparison.
- [ ] Review the resulting answer and interaction together. Preserve failures and
  original records; no silent repairs, replacement trials or automatic extensions.
  A coherent interface package can vary together, provided its components are
  identified and any causal claim stays within what the comparison supports.
- [ ] Keep, revise, abandon or further distinguish a candidate according to the
  principal's judgment and the evidence. Propose extra comparisons only when
  they would resolve a material uncertainty.

## Adoption and completion

A useful reduction in mechanical effort counts even without an improved
intellectual answer. Consider discoverability and the risk of confusion as well
as verbosity. One model on a few inquiries does not establish a universal
interface preference; broader claims need corresponding evidence.

Bring changes to authority, expressive freedom or protected obligations to the
principal explicitly. Before adopting a design, align the affected contracts,
interface, forms, help and examples, and verify actual behavior under the required
normal and adverse checks. Keep custody verification distinct from judging
claims or evidence support.

Update this plan with selected work and unresolved decisions. At completion,
give remaining candidates a disposition, move enduring behavior and guidance to
their owners, and delete the plan. Preserve original evidence under
[DEVELOPMENT](DEVELOPMENT.md#evidence-and-retention).
