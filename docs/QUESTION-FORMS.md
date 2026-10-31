# Question forms and rendering

This specifies the three initial families, the exact text the auditor sees, the
tool descriptions and input schemas, the structured answer and the Markdown
renderer. The policy is in [CONTRACTS.md](../CONTRACTS.md). The tools' input
rules, replies and refusals are in [INTERFACE.md](INTERFACE.md) section 7.

Texts in quoted blocks are exact; they are pinned byte for byte in each
arrangement and change only with a new version. In the pinned bytes, the lines
of a quoted paragraph are joined by single spaces, paragraphs are joined by two
LF bytes (`\n\n`), and a text has no trailing LF.

The families are open inquiry (`open-inquiry/1`), inquiry framing
(`inquiry-framing/1`) and comparison (`comparison/1`). The manager names one in
the front matter. The auditor never sees the family name. It sees the
orientation, its family's instructions and its tools.

## System blocks

The request's `system` array has two text blocks: the orientation, then the
family instructions. It is pinned as the compact JSON
`[{"type":"text","text":<orientation>},{"type":"text","text":<family instructions>}]`,
each text a JSON string escaped as in the structured answer (below).

### Orientation (`stewart.orientation/1`)

> You are the auditor in a Stewart audit. The first user message is the
> manager's question, exactly as they wrote it. The materials they selected can
> be read with the list, read and search tools. The question and those materials
> are your whole world: you have no shell, no other files, no network, no way to
> run code and no way to ask the manager anything. Reports, logs and test results
> in the materials are claims by their authors, not executions you witnessed.
>
> Your answer is the entries you record with the record tools, and each entry is
> attributed to you. You may record that the material is inadequate, that you are
> uncertain, that you disagree with the question's premise or that you found no
> supported finding. None of these needs a defect, a winner or a repair. An
> answer with missing sections, or with no entries, can be submitted.
>
> Record your account early, even briefly, and replace it as your work develops.
> Replacing an entry keeps its place. To cite, use the ranges that read and
> search return, or give a quote of exact text. Searching for distinctive text
> gives a ready citation. Citations are checked only for exact location and
> quotation, never for whether they support what you say.
>
> Use handles exactly as tools return them. If a tool says a handle is stale,
> read the current one before replacing it. If your context was summarized, or
> you are unsure what you have recorded, call what_am_i_working_with.
>
> When you are ready, call prepare to see exactly what would be sealed, then call
> submit with that handle and confirm set to true. Submitting seals your answer,
> and it cannot be edited afterwards. Your limits are cumulative across the whole
> audit; what_am_i_working_with shows what remains.

### Family instructions

Open inquiry (`open-inquiry/1`):

> Address the question from the supplied materials. Begin your account with your
> direct response to the question and its reach, including when you cannot
> answer it as asked; do not leave a decisive inability only in a final
> limitation. Record observations that connect what you found to its basis in
> the materials. Record limits on what the materials let you establish. No
> positive finding and no universal assurance is required. When you use a label
> from the materials, such as a requirement number, explain it in ordinary words
> the first time.

Inquiry framing (`inquiry-framing/1`):

> The manager has described a concern. Formulate a working question that the
> supplied materials can bear on, record it, and record how it relates to the
> original concern. Then investigate it in this audit and record what you find.
> The manager's question stays as written; if it is already precise, it can be
> your working question. If useful bounded investigation is not possible with
> these materials, say so and explain why. Begin your account with your direct
> response and its reach. Record observations with their basis and record the
> limits of what you could establish. When you use a label from the materials,
> explain it in ordinary words the first time.

Comparison (`comparison/1`):

> Compare the alternatives the question names, using the supplied evidence.
> Record the criterion, saying what the manager supplied and what is your
> interpretation of it. Use a comparison entry for a finding that relates the
> alternatives to each other, and an observation for a finding about one
> alternative or about the materials. Distinguish what you reasoned from the
> source yourself from what supplied materials report. If the evidence is unequal,
> the criterion is unavailable or a comparison is not possible, say so; no winner
> is required. Begin your account with your direct response and its reach, and
> record the limits of what you could establish. When you use a label from the
> materials, explain it in ordinary words the first time.

## Tools

The `tools` array lists, in this order: `list`, `read`, `search`, the family's
recording tools in table order, `record_artifact`, `replace`, `delete`,
`what_am_i_working_with`, `prepare`, `submit`.

| Family | Recording tools | Expected sections for prepare's notices |
| --- | --- | --- |
| Open inquiry | `record_account`, `record_observation`, `record_limit` | all three |
| Inquiry framing | `record_working_question`, `record_relation`, `record_observation`, `record_account`, `record_limit` | all five |
| Comparison | `record_criterion`, `record_comparison`, `record_observation`, `record_account`, `record_limit` | criterion, comparison, account, limit |

Comparison's observation tool is auxiliary. Its entries are counted but they are
not a coverage section, and they never imply that a comparison took place. There
is no required entry count, and multiple entries of a kind are permitted.

Tool descriptions (exact):

| Tool | Description |
| --- | --- |
| `list` | List the captured materials: their names (materials/…), sizes and line counts. Long lists come in pages. |
| `read` | Read exact text from the question (source "question"), a material (materials/…), one of your entries (its handle) or a prepared view. Returns up to 64 KiB per call, and a next call when more remains. For the question and materials, the reply's cite is a ready citation for what was returned. The exact text is the second content block, or the reply's text field when the page is blank; bytes recorded as base64 come in its base64 field. |
| `search` | Find exact, case-sensitive text in the question and all materials, or in the sources you name. Each hit's cite is a ready citation. The reply says whether the whole scope was searched; an incomplete search does not show that text is absent. |
| `record_account` | Record your account: the direct response to the question and its reach, including any inability to answer it as asked. |
| `record_observation` | Record one observation and its basis in the materials. |
| `record_limit` | Record a limit on what the materials let you establish. |
| `record_working_question` | Record the working question you will investigate. |
| `record_relation` | Record how the working question relates to the manager's original concern. |
| `record_criterion` | Record the criterion for the comparison, saying what the manager supplied and what is your interpretation. |
| `record_comparison` | Record a finding that relates the alternatives to each other. |
| `record_artifact` | Record a free-form artifact with a label: text, or base64 for bytes that are not text. It belongs to your answer but fills no section. |
| `replace` | Replace exactly one version of an entry, given its handle. Supply every field: text, citations and label for a recorded entry; label and text or base64 for an artifact. The entry keeps its place. |
| `delete` | Remove exactly one version of an entry from your answer. |
| `what_am_i_working_with` | Show the audit's state: what you have recorded and its handles, recent edits and refusals, the question and materials, and your remaining allowances. Use it when continuing or after your context was summarized. |
| `prepare` | Make the exact candidate that submit would seal, with its Markdown rendering and factual notes on empty sections. It changes nothing, and you can keep editing. |
| `submit` | Seal a prepared candidate as your answer. Without confirm set to true this is a dry run. After a confirmed submit the answer cannot be edited. |

Input schemas (normative). Each tool's `input_schema` is
`{"type":"object","properties":{…},"required":[…],"additionalProperties":false}`
with exactly these properties, `required` listing those marked yes. Each
property schema carries its `type` and the description below, plus `minimum` for
integers and `items` and `maxItems` for arrays. Other bounds, and requirements
that depend on another field or on the entry's kind, are checked by Stewart and
refused as INTERFACE section 7 states. Descriptions are exact.

| Tool | Property | Type | Required | Bounds | Description |
| --- | --- | --- | --- | --- | --- |
| `list` | `cursor` | string | no | An `ls.` cursor | Cursor from the previous list reply's next call, for the next page. |
| `read` | `source` | string | yes | 1–1,034 bytes: `question`, `materials/<name>`, an entry handle or a prepared view | What to read: question, materials/<name>, one of your entry handles or a prepared view. |
| `read` | `start` | integer, `minimum` 0 | no; default 0 | At most the source's size, on a UTF-8 boundary | Byte offset to start from. Default 0; use the start that a reply's next call gives. |
| `search` | `text` | string | yes | 1–1,024 bytes | Exact text to find. Matching is literal and case-sensitive. |
| `search` | `sources` | array of string, `maxItems` 128 | no; default the question, then every material | Each `question` or `materials/<name>` | Sources to search. Default: the question and every material. |
| `search` | `cursor` | string | no | An `sc.` cursor | Cursor from the previous search reply's next call. Give it with the same text and sources. |
| `record_<kind>` | `text` | string | yes | May be empty | Entry text. It may be empty. |
| `record_<kind>` | `citations` | array of citation, `maxItems` 64 | no; default empty | Citation rules (INTERFACE 7.3) | Citations: {source, start, end, quote?} from read or search, or {source, quote} with exact text. |
| `record_<kind>` | `label` | string | no; default empty | 0–200 characters, no control characters | Optional short label shown in the rendering. |
| `record_artifact` | `label` | string | yes | 1–200 characters, no control characters | Required short label for the artifact, shown in the rendering. |
| `record_artifact` | `text` | string | exactly one of `text`, `base64` | — | Artifact content as text. |
| `record_artifact` | `base64` | string | exactly one of `text`, `base64` | Canonical RFC 4648 with padding, no whitespace | Artifact bytes as base64, for content that is not text. |
| `replace` | `entry` | string | yes | An entry handle | The exact handle of the entry version to replace. |
| `replace` | `label` | string | yes | 0–200 characters for a recorded entry, 1–200 for an artifact; no control characters | Required label for the replacement, shown in the rendering. Give the current label to keep it. |
| `replace` | `text` | string | for a recorded entry; for an artifact, exactly one of `text`, `base64` | May be empty for a recorded entry | Replacement text. |
| `replace` | `citations` | array of citation, `maxItems` 64 | for a recorded entry; not for an artifact | Citation rules (INTERFACE 7.3) | Replacement citations, as for the record tools. Use [] for none. |
| `replace` | `base64` | string | for an artifact, exactly one of `text`, `base64`; not for a recorded entry | Canonical RFC 4648 with padding, no whitespace | Replacement artifact bytes as base64. |
| `delete` | `entry` | string | yes | An entry handle | The exact handle of the entry version to remove. |
| `what_am_i_working_with` | `page` | string | no | A `pg.` cursor | Cursor from the previous reply's next call, for the next page of entries. |
| `prepare` | none | — | — | — | — |
| `submit` | `prepared` | string | yes | An auditor preparation handle | The handle that prepare returned. |
| `submit` | `confirm` | boolean | no; default false | — | Set to true to seal. Otherwise this is a dry run. |

So `required` is `[]` for `list`, `what_am_i_working_with` and `prepare`;
`["source"]` for `read`; `["text"]` for `search` and `record_<kind>`;
`["label"]` for `record_artifact`; `["entry","label"]` for `replace`;
`["entry"]` for `delete`; and `["prepared"]` for `submit`. The schema's
`required` never lists a field that is conditional on another field or on the
entry's kind.

A citation item has this schema:

```json
{"type":"object","properties":{"source":{"type":"string","description":"question or materials/<name>."},"start":{"type":"integer","minimum":0,"description":"Byte offset where the cited span begins."},"end":{"type":"integer","minimum":1,"description":"Byte offset just after the cited span."},"quote":{"type":"string","description":"Exact text of the cited span."}},"required":["source"],"additionalProperties":false}
```

Stewart accepts exactly two forms: `start` and `end`, with an optional `quote`;
or `quote` without `start` and `end`. Any other combination is refused
(`citation_invalid`). The schema states this single object shape rather than a
`oneOf`.

## Notices

The reminder, sent at most once per audit after a turn ends without submission
while no limit is exhausted (text from CONTRACTS):

> This turn ended without a submission. Your recorded answer remains unsealed.
> If you intend to submit it, use prepare and confirm its handle with submit.

The near-limit notice, sent at most once per audit, with each value filled in as
the decimal integer max(0, limit − used):

> Allowance notice: {turns} turns, {input_tokens} input tokens and
> {output_tokens} output tokens remain for this audit. When an allowance runs
> out the run stops, and an unsubmitted answer stays unsubmitted.

The continuation notice, the second block of a continuing placement's first
message:

> This audit is continuing in a new conversation after an earlier run ended.
> Your recorded work is preserved, but this conversation does not contain it.
> Call what_am_i_working_with to see what you have recorded. Your last action
> before the interruption may or may not have been recorded; check before
> repeating it.

The post-compaction notice, after the provider's signed summary in the same
placement (it consumes neither the reminder nor the near-limit allowance):

> The provider has summarized your earlier conversation. Continue this audit.
> Call what_am_i_working_with to check your recorded work before repeating an
> action.

## The structured answer (`stewart.answer/1`)

`answer.json` is the prepared selection. It is the `selection` view the auditor
can read and the `answer.json` return member.

```json
{"schema":"stewart.answer/1","revision":7,"entries":[
{"id":"e1","version":2,"kind":"record_account","label":"","text":"The supplied excerpts support one restart-related duplicate-delivery concern.","citations":[{"source":"materials/a.py","start":0,"end":175,"stewart":{"name":"materials/a.py","sha256":"…","lines":[1,5]}},{"source":"materials/requirements.txt","quote":"R1. A reminder ID","stewart":{"name":"materials/requirements.txt","sha256":"…","range":[50,67],"lines":[2,2]}}]},
{"id":"e4","version":1,"kind":"record_artifact","label":"trace","encoding":"utf-8","member":"artifact-e4.bin","size":120,"sha256":"…"}]}
```

Serialization is pinned so the bytes are reproducible:

- Keys appear in the order shown. There is no whitespace between tokens, and
  each entry begins on a new line as shown. The file ends with `]}` and one LF.
  An empty selection is the single line
  `{"schema":"stewart.answer/1","revision":<n>,"entries":[]}` and one LF.
- Strings escape `"` and `\` with a backslash. Of the control characters,
  exactly U+0000–U+001F are escaped: `\b \f \n \r \t` for those five and
  `\u00xx` in lowercase hex for the rest. All other characters, including
  U+007F and non-ASCII, are written as raw UTF-8.
- A citation holds the auditor's operands at its top level and Stewart's
  additions under `stewart` (INTERFACE 7.3). Its keys appear in the order
  `source`, `start`, `end`, `quote`, `stewart`, and inside `stewart` in the
  order `name`, `sha256`, `range`, `lines`. Absent keys are omitted; `range` is
  present only when Stewart located the citation from a quote.
- Artifact entries carry `encoding`, `member`, `size` and `sha256`. `encoding`
  follows the input field: `utf-8` for `text`, `binary` for `base64`, even when
  the base64 bytes happen to be UTF-8. The artifact bytes are a separate member,
  never inlined.
- An entry whose bytes close could not read or verify when it sealed
  (INTERFACE 8.1) is written
  `{"id","version","kind","label","unproduced":{"sha256","size","failure"}}` in
  that key order. `sha256` and `size` are the recorded digest and size of its
  payload, and `failure` is `missing`, `unreadable` or `damaged`. Every other
  entry keeps its ordinary form, so the file still binds the whole selection's
  identities and digests.

## The rendering (`stewart.render/1`)

`answer.md` is generated from the selection by these rules alone. It never
reorders, combines or judges entries, never inserts the question or operating
history, and never fills a gap.

```
Rendered by Stewart. Entry text is attributed to the auditor.

## Observation — e3 · restart duplicate

> Implementation A can send the same reminder twice if the worker stops
> after sending but before recording the sent marker.

Citations: materials/requirements.txt line 2 [50, 119) "R1. A reminder ID should cause at most one recipient-visible message."; question line 1 [0, 46).
```

1. First line: `Rendered by Stewart. Entry text is attributed to the auditor.`
2. For each entry in selection order, a blank line, then the heading `## <Kind>
   — <id>`, followed by ` · <label>` when the label is non-empty. Kind is the
   tool name without `record_`, with underscores as spaces and the first letter
   capitalized (`Working question`). Artifacts use `Artifact`.
3. A blank line, then the text as a blockquote. The text is split at each LF,
   and a final LF does not add a line. Each line is written as `> ` plus the
   line, or as `>` alone if the line is empty. Other bytes, including CR, are kept.
   Empty text is written `*No text recorded.*`. A binary artifact is written
   `Binary artifact, <size> bytes, SHA-256 <hex>, delivered as <member>.`
4. If the entry has citations, a blank line, then `Citations: ` followed by
   each citation joined with `; ` and ended with `.`. A citation is the source
   name; then `line N` or `lines N–M` (an en dash) from `stewart.lines`; then
   the byte range `[start, end)`, from the citation's `start` and `end` when
   present and otherwise from `stewart.range`; then, if a quote was given, a
   space and the quote as a JSON string with the escapes above.
5. The file ends with one LF.

An empty selection renders as the single line `No answer entries recorded.` and
an LF. The renderer is not run when any entry is unproduced: `answer.md` is then
itself an unproduced member of the return (INTERFACE 8.1), and its bytes are
never invented.

## Worked examples

The [worked examples](../examples/questions/README.md) give one submission
folder per family over a small invented reminder service, each a valid
`question/1` question with its materials. Their walkthroughs show an auditor's
calls, written by hand, with the replies and the rendering this specification
and INTERFACE section 7 give for them, and a variant with inadequate evidence.
They illustrate expression; they are not wire fixtures, and no conclusion in
them is an expected answer.
