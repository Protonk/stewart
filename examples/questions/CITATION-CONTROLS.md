# Citation controls

Paper controls, not executed product tests. Use the open inquiry example's
materials. The exact byte range below selects one requirement sentence of
`materials/requirements.txt` without its newline; a `search` for the sentence
returns this range as its ready `cite`.

Valid structured citation:

```json
{
  "source": "materials/requirements.txt",
  "start": 50,
  "end": 119,
  "quote": "R1. A reminder ID should cause at most one recipient-visible message."
}
```

Stewart records it with its own additions under `stewart` (the source's name,
SHA-256 and lines `[2, 2]`), and the rendering cites it as:

```text
materials/requirements.txt line 2 [50, 119) "R1. A reminder ID should cause at most one recipient-visible message."
```

The same sentence can be cited by quote alone:

```json
{"source": "materials/requirements.txt", "quote": "R1. A reminder ID should cause at most one recipient-visible message."}
```

It occurs once, so Stewart records its range `[50, 119)` under `stewart.range`
and the rendering is the same. A quote that occurs more than once, such as
`reminder`, is refused (`quote_ambiguous`) with its occurrences as ready
citations.

For a mismatching-quote control, replace `at most one` in the quote with
`exactly one` while leaving the range unchanged. The call must be refused
(`citation_invalid`, naming citation 0 and the defect), record no entry and keep
its raw call captured.

For the valid-but-irrelevant control, attach the valid citation above to the
claim `The service encrypts every stored reminder.` The reference is
mechanically valid and the claim remains the auditor's; Stewart must not declare
it supported or reject it on an inferred support judgment. A reader may contest
it.

An empty selection can prepare and submit: prepare's only notice is
`answer_empty` ("No answer entries are recorded."), and the rendering is the
single line `No answer entries recorded.` Two contradictory accounts can both be
recorded and rendered in order without choosing one or inventing a
reconciliation.
