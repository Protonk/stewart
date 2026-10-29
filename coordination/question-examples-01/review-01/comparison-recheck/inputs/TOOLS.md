# Paper tool card for the three worked examples

Proposed concrete interface, 2026-10-29. This is a paper prototype, not an
implemented Stewart adapter. Tool names, entry schemas and presentation below
are candidates for review under CONTRACTS, not new settled policy. All replies
and handles in the walkthroughs are illustrative. No auditor or provider ran.

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

These typed entries propose a concrete extension of the older provisional
raw-element answer structure. Their serialized fields and the readable rendering
both belong to the sealed answer. This proposal adds no judgment or completion
grade. Final serialization and the complete raw-byte artifact API are outside
this small text-only walkthrough; the review must not mistake that omission for
a decision to remove either the existing custody guarantees or artifact support.

## Your recording tools and instructions

Identify the criterion, distinguishing what the manager supplied from the auditor's interpretation. Compare the requested alternatives using supplied evidence. Use observations for findings about one alternative; a comparison entry relates alternatives. Distinguish source reasoning from reported observations. State unequal evidence, an unavailable criterion or inability to compare without inventing a winner.

Recording tools: `record_criterion`, `record_comparison`, `record_observation`, `record_account`, `record_limit`.

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

`prepare()` makes an inspectable manifest and Markdown rendering for the current
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
printed in these walkthroughs. Actual prepare/manifest/submit response schemas
remain implementation specification work; do not claim a machine round trip
from their symbolic representations in this exercise.

The settled one unsubmitted-stop reminder and one factual near-limit notice
apply across the audit and within its cumulative budget. They are not extra
authoring stages in these walkthroughs. At a hard stop an unsealed answer remains
unsubmitted, and manager close can seal recorded work with manager attribution.
