# Original corpus retention

The 21 original product-audit text files are captured under
`.scratch/successor-inquiry-01/answers/attempt-01/sources/`; exact identities
are in [CORPUS.json](answers/attempt-01/CORPUS.json). The four supplementary
development texts remain a separate corpus class. Keep these finite source
copies and their independent verification records with the inquiry through
comparison and review. Do not prune them as disposable run scratch.

The coordinator checked history reachability on 2026-10-26. The target commit
`0aaa6eafa06722add123105da912c906b8608633` is an ancestor of main, but the
three outcome commits were not; no containing Git refs were observed for them.
Local source copies already preserved their text. The coordinator additionally
created these development-evidence refs exclusively and verified their values:

| Case | Development ref | Exact historical outcome |
| --- | --- | --- |
| A1 | `refs/development-evidence/successor-inquiry-01/a1` | `d2a5779bca324e04e84b60aee5af85ec4f199785` |
| A2 | `refs/development-evidence/successor-inquiry-01/a2` | `4fe0ab7040c679f1985f95a2c6d443e4eb2c8ccb` |
| A3 | `refs/development-evidence/successor-inquiry-01/a3` | `3d3107e8ee8e0ddb72f493d60864240772619c61` |

These local refs protect the source commits from ordinary unreachable-object
cleanup. They are development retention anchors, not Stewart receipts, restored
audit lifetimes or execution authority. No historical bytes were changed.
They are not presumed present in another clone or remote. Preserve them or move
the exact required source into another verified durable archive before retiring
this inquiry's references. A normal main-only clone is insufficient to recover
these outcome commits without those additional refs or source copies.

Evidence is `.scratch/successor-inquiry-01/history-reachability-01.json` and
`history-preservation-01.json`. The first record's per-commit observations are
correct, but its generic `meaning` sentence incorrectly asserted that all
commits were ancestors. The second record explicitly corrects that sentence
and records the new refs and verification. Preserve both records.
