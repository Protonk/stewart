# Question forms: specification brief

The initial library and behavioral policy are settled in
[CONTRACTS.md](../CONTRACTS.md). This brief supplies the concrete starting point
for specification: open inquiry, inquiry framing and comparison; common reading,
exact-version editing and explicit submission; faithful deterministic rendering.
Exact tool names, complete wire schemas and byte encoding are the spec agent's
work. They may improve these examples within the decided semantics without
reopening the design or introducing a new outcome/completeness gate.

Keep section names with prose and structured citations as the initial shape.
Comparison needs an auxiliary observation route for one-sided evidence; it does
not count as a comparison coverage section. The account should lead with the
direct answer or inability and explain its reach. Distinguish supplied criteria
from the auditor's interpretation and explain opaque requirement labels. These
are authoring instructions, not renderer-generated conclusions or admission tests.

The [worked examples](../examples/questions/README.md) include inadequate evidence.
Their paper replies are illustrative, not a completed protocol specification.
The bounded paper review supported these small expression/presentation choices;
it did not exercise a real tool round trip, empty/missing-section submission,
large/multiple-question answers or real runtime interruption. Carry those paths
into executable acceptance. No broader taxonomy is justified by that exercise.

The auditor has the captured question, listed materials and the selected family's
instructions/tools. It cannot execute the supplied code, fetch other material,
ask the manager a live question or change the family. Supplied reports are claims
by their authors. Code reasoning is not a witnessed execution.

## Reading and ordinary authoring

- `list()` returns the explicitly listed material IDs, names and byte counts.
- `read(material, start=0, end=file_size)` returns exact UTF-8 bytes and a usable
  citation object `{material, start, end}`. Ranges are zero-based and end-exclusive.
  These tiny fixtures fit in a page. Production pagination follows CONTRACTS.
- `search(text)` is literal, case-sensitive search over captured materials and
  returns matching ranges, scope and continuation status. It does not search the
  live preparation directory.
- Each family recording tool takes `{text: string, citations: Citation[] = []}`.
  `text` is required as an argument, but may be empty. Citations are optional.
  A citation is `{material: string, start: integer, end: integer, quote?: string}`.
  Its range must exist in that audit's captured material; an explicit quote must
  equal the range bytes. No semantic support check occurs. Ordinary prose is
  not scanned for citations.
- A successful recording call appends one entry and returns its exact handle,
  version and answer revision, e.g. `{entry:"e1", version:1, revision:1}`.
  Repeating a recording call makes another entry. Every entry remains attributed
  to the auditor. Multiple entries of the same kind are permitted; no last-one-wins.
- `add(name, text)` records an additional free-form text artifact with an opaque
  label. It is available in every family. It satisfies no family-section count
  merely because its label or prose resembles a section name.
- `replace(handle, value)` replaces exactly that version, retains its entry kind,
  and returns a new version/revision. `value` is the complete replacement
  `{text, citations}` for a family entry, or `{name, text}` for a free-form artifact.
  All members of the replacement value are explicit; omitted members are an
  invalid call, not a guess to preserve or erase previous content.
- `delete(handle)` removes exactly that version from current membership under
  the settled repeated-delete rules. Retained old bytes are not physically removed.
- `answer_read(handle)` retrieves the explicitly named current entry/version or,
  for a prepared-member handle, the exact prepared rendering/manifest bytes. A
  stale entry handle receives a diagnostic and the current handle; it does not
  silently select a newer version. Historical entry browsing is not added here.
- `what_am_i_working_with()` supplies state, revision, cumulative allowances,
  question/material access, entry handles and recent completed effects. It cannot
  restore thoughts that were never recorded. Reads and mutations obey CONTRACTS'
  bounds, stale-target rules and exceptional-state presentation.

The typed entries and readable rendering both belong to the sealed answer.
They add no judgment or completion grade. Specify their exact serialization and
the raw-byte artifact API together: this text-only example does not remove raw
artifact support or the existing custody guarantees.

## Family tools and instructions to specify

Only the selected row's recording tools join the common reading/editing/submission
tools. The manager selects the family. Review agents receive just the selected
instructions; the family's name is a coordination label here, not an extra
manager-purpose briefing for the auditor.

| Family | Recording tools | Instructions |
| --- | --- | --- |
| Open inquiry | `record_account`, `record_observation`, `record_limit` | Address the question from the supplied materials. Connect observations to their basis and state the reach and limits of the account. No positive finding or universal assurance is required. |
| Inquiry framing | `record_working_question`, `record_relation`, `record_observation`, `record_account`, `record_limit` | Formulate a working question that the supplied material can bear on, explain its relationship to the original concern, and investigate it in this commission. Preserve the original request. Explain inability when useful bounded investigation is not possible. |
| Comparison | `record_criterion`, `record_comparison`, `record_observation`, `record_account`, `record_limit` | Identify the criterion, distinguishing what the manager supplied from the auditor's interpretation. Compare the requested alternatives using supplied evidence. Use observations for findings about one alternative; a comparison entry relates alternatives. Distinguish source reasoning from reported observations. State unequal evidence, an unavailable criterion or inability to compare without inventing a winner. |

There is no required entry count. Named recording kinds are expected sections
for preparation's factual coverage display, not submission prerequisites, except
that comparison's auxiliary `record_observation` is not an expected section.
Its coverage list remains criterion, comparison, account and limit. Counts may
include auxiliary observations without implying that a comparison was performed.
The text can contest a premise, state inability, contain uncertainty or disagree
with other entries. This deliberately starts with section names and prose rather
than a deeper taxonomy of claims; the pressure test should examine whether it
provides enough useful guidance and preserves relationships between entries.

In every family, use the account to state the direct response and its reach,
including an inability to answer the requested question. Put that account before
supporting detail when it helps the reader locate the answer; do not leave a
decisive inability only in the final limitation. Explain a requirement label such
as R1 in ordinary words when first using it. These are authoring instructions,
not ordering, citation or substantive-completeness gates. The renderer never
reorders entries or judges whether an observation "really" compares alternatives.

## Preparation, submission and rendering

`prepare()` makes an inspectable selection inventory and Markdown rendering for the current
revision. It returns a handle, member read handles, entry counts and observations
such as `No record_comparison entries are recorded.` It does not edit the answer
or seal it. Missing sections and a completely empty answer do not refuse it.

`submit(handle, confirm=false)` is a dry run by default. With `confirm=true`, it
seals the exact prepared selection and rendering. An intervening edit makes that
handle stale; an already accepted handle retrieves its recorded outcome. No
reading/inspection pause or additional omission acknowledgment is required.

For the examples, the exact renderer convention is the line
`Rendered by Stewart. Entry text is attributed to the auditor.`, followed by a
blank line and each entry in recorded order. The level-two heading is the tool
name with `record_` removed, underscores replaced by spaces and the initial letter
capitalized (for example, `Working question`). After a blank line, emit the exact
entry text. If citations exist, add a blank line and
`Citations: m1 [50, 120); m2 [0, 175).` using the actual IDs and end-exclusive
ranges in recorded order. An explicit quote, if present, follows its range as a
JSON-escaped string. Separate entries with a blank line and end with one newline.
This is a proposed deterministic presentation rule, not a final product wire
schema. It does not insert the manager's
question, infer a conclusion, combine repeated sections or resolve contradictions.
An empty selection gets only the factual presentation `No answer entries recorded.`
The sealer and form version belong in the manifest; no fake receipt digest is
printed in these walkthroughs. Complete preparation/selection/seal response schemas
are specification work under the accepted machine interface; do not claim a machine round trip
from their symbolic representations in this exercise.

The settled one unsubmitted-stop reminder and one factual near-limit notice
apply across the audit and within its cumulative budget. They are not extra
authoring stages in these walkthroughs. At a hard stop an unsealed answer remains
unsubmitted, and manager close can seal recorded work with manager attribution.
