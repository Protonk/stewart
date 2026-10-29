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
- `answer_read(handle)` retrieves an entry's current recorded value or, for a
  prepared-member handle, the exact prepared rendering/manifest bytes.
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

## Selected family tools and instructions

Only the selected row's recording tools join the common reading/editing/submission
tools. The manager selects the family. Review agents receive just the selected
instructions; the family's name is a coordination label here, not an extra
manager-purpose briefing for the auditor.

| Family | Recording tools | Instructions |
| --- | --- | --- |
| Open inquiry | `record_account`, `record_observation`, `record_limit` | Address the question from the supplied materials. Connect observations to their basis and state the reach and limits of the account. No positive finding or universal assurance is required. |
| Inquiry framing | `record_working_question`, `record_relation`, `record_observation`, `record_account`, `record_limit` | Formulate a working question that the supplied material can bear on, explain its relationship to the original concern, and investigate it in this commission. Preserve the original request. Explain inability when useful bounded investigation is not possible. |
| Comparison | `record_criterion`, `record_comparison`, `record_account`, `record_limit` | Identify the criterion and compare the requested alternatives using supplied evidence. Distinguish source reasoning from reported observations. State unequal evidence, an unavailable criterion or inability to compare without inventing a winner. |

There is no required entry count. Every named recording kind is an expected
section for preparation's factual coverage display, not a submission prerequisite.
The text can contest a premise, state inability, contain uncertainty or disagree
with other entries. This deliberately starts with section names and prose rather
than a deeper taxonomy of claims; the pressure test should examine whether it
provides enough useful guidance and preserves relationships between entries.

## Preparation, submission and rendering

`prepare()` makes an inspectable manifest and Markdown rendering for the current
revision. It returns a handle, member read handles, entry counts and observations
such as `No record_comparison entries are recorded.` It does not edit the answer
or seal it. Missing sections and a completely empty answer do not refuse it.

`submit(handle, confirm=false)` is a dry run by default. With `confirm=true`, it
seals the exact prepared selection and rendering. An intervening edit makes that
handle stale; an already accepted handle retrieves its recorded outcome. No
reading/inspection pause or additional omission acknowledgment is required.

For the examples, rendering is mechanical: a Stewart-renderer attribution line,
then entries in recorded order, each with its kind as a heading, the exact text,
and its structured citations listed below. It does not insert the manager's
question, infer a conclusion, combine repeated sections or resolve contradictions.
An empty selection gets only the factual presentation `No answer entries recorded.`
The sealer and form version belong in the manifest; no fake receipt digest is
printed in these walkthroughs. Final Markdown layout is still a proposal.

The settled one unsubmitted-stop reminder and one factual near-limit notice
apply across the audit and within its cumulative budget. They are not extra
authoring stages in these walkthroughs. At a hard stop an unsealed answer remains
unsubmitted, and manager close can seal recorded work with manager attribution.
