# Source-derived predictions; no observations from execution

All A–F use the same exact review.json. In the table, comparisons and mismatches
mean the verifier's counted values, not raw compare-row totals. Each valid
specimen has four raw compare rows: three ordinary and one control.

| Specimen | Parsed valid rows | Parse problems | Ordinary compared / mismatches | Control compared / mismatches |
| --- | ---: | --- | --- | --- |
| A-complete | 10 | empty | 3 / 0 | 1 / 1 |
| B-duplicate | 10 | empty | 1 / 0 | 1 / 1 |
| C-note-invariant | 10 | empty | 3 / 0 | 1 / 1 |
| D-control-extinguished | 10 | empty | 3 / 0 | 1 / 0 |
| E-admission-before-reach | 10 | empty | 0 / 0 | 1 / 1 |
| F-parse-problem | 10 | line 11, invalid JSON row | 3 / 0 | 1 / 1 |

For A, B, C, D and F, each population has declared=1, reached=1,
admitted=1, refused=0. For E, ordinary admitted=0 while ordinary declared=1,
reached=1 and refused=0; control is unchanged. The expected ordinary
mismatching_cases list is empty in every specimen. The control list is
["switch-control"] except D, where it is empty.

A, C and F should have empty arrays in every summary diagnostic field and
prerequisites=[]; F additionally has its separate parse problem. For B the only
nonempty summary diagnostic fields should be:

```json
{
  "missing_measurements": [{"case":"parcel-check","measurement":"label"}],
  "duplicate_measurements": [{"case":"parcel-check","measurement":"seal"}]
}
```

B's prerequisites, in source order, should be exactly:

```json
[
  "missing measurements: parcel-check:label",
  "duplicate measurements: parcel-check:seal"
]
```

D should have inconsistent_comparisons=["switch-control"], with all other
summary diagnostics empty. Its prerequisites should be exactly:

```json
[
  "no control produced a nonzero disagreement; the instrument was not observed to fire",
  "mismatch flags contradict recorded operands for: switch-control"
]
```

E's nonempty summary diagnostic fields should be:

```json
{
  "compared_without_admission": ["parcel-check"],
  "sequence_problems": ["parcel-check: admission requires prior reach and cannot repeat"],
  "unresolved_admission": ["parcel-check"]
}
```

E's prerequisites, in source order, should be exactly:

```json
[
  "no ordinary comparison was recorded",
  "comparisons recorded while cases were not admitted: parcel-check",
  "cases without an admission outcome: parcel-check",
  "parcel-check: admission requires prior reach and cannot repeat"
]
```

In E, missing_measurements and uncompared should remain empty because the
ordinary case never acquired an accepted true admission. That absence must not
be interpreted as coverage. Its admission and sequence diagnostics carry the
gap instead. In F, malformed_rows should remain empty because parse_rows
filters the invalid line out before summarize sees it; parse problems carry
that gap. The exact JSON decoder error wording is not predicted.

These predictions follow the supplied source's set reconciliation, exclusion
of every duplicate occurrence from counts, operand recomputation and event
state transitions. They are hypotheses awaiting a separately commissioned
execution. Structural acceptance by the submission helper would not verify any
table entry or conclusion.
