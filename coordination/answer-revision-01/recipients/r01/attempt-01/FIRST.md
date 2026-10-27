# r01 — first selected return

The selected return supports a useful, conditional claim about the validator. It does not establish that the dictionary returned by `status._auditor_report` supports the manager's named use. That implementation is expressly absent from the packet, so I cannot inspect its actual arguments, projections, companion data or return branches. I agree with the author's bounded `needs-evidence` judgment; I find no consequential disagreement in the supplied account.

The claim I can repeat is: **For these hypothetical report bytes, if the supplied session record and collected HEAD are converted by `session_declaration_expectations` and passed to `validate_report_declaration`, static inspection predicts distinct missing, invalid, mismatch and valid results. The validator retains completion and report-kind values inside a parsed declaration for valid and mismatching inputs, separately from validation status and identity comparisons. This establishes neither actual completion nor a process-exit observation or manager judgment. Preservation through the missing status consumer remains unresolved.**

This inspection used the actual selected primary and four supporting artifacts, also checked against `RETURN.raw`. All 23 files listed by `PACKET.json` match their listed byte counts and SHA-256 values. Those checks establish consistency within this supplied packet, not authenticity or execution history. The detailed byte comparisons are saved in `.scratch/answer-revision-01/recipients/r01/attempt-01/INSPECTION-FIRST.json`.

## Sites and distinctions I could inspect

Coordinates below are the original coordinates carried by the supplied excerpts at revision `5f00082d86768368478ed7cc85b52dd56a60255b`, not live-source inspection.

- `report_declaration.py:161–170` constructs five expectations from the supplied session dictionary and, for this non-null collected HEAD, a sixth comparison. Its source labels distinguish session values from the supplied collection HEAD. The labels are caller-provided provenance descriptions, not independent proof of observation.
- `_parse`, particularly `report_declaration.py:92–132`, distinguishes an absent declaration from rejected JSON or schema values. `_json.py:20–34` rejects duplicate decoded keys instead of selecting either value. The supplied audit-ID and commit-ID excerpts let me check the relevant format constraints.
- `validate_report_declaration`, `report_declaration.py:143–158`, turns parsing refusals into separate `missing` or `invalid` status values, retaining diagnostics. On a parsed declaration it retains expected and observed operands, their source and equality; a mismatch adds a diagnostic and changes status without discarding the declaration.
- `StewartError.to_json`, `_bootstrap.py:231–241`, supplies diagnostic fields. The separately defined exception exit-code property is not read by this serialization path and is not a process-exit observation.
- The named consumer, `status._auditor_report`, has no supplied implementation. Its use of these producer results cannot be established by definitions, comments or the question's stated purpose.

The author's primary pair is directly inspectable: `report-valid.md` and `report-mismatch.md` differ only in the target-commit line, from forty `a` characters to forty `f` characters. My byte comparison confirms that narrow change. Under the stated mappings, the source predicts `valid` versus `mismatch`, with the mismatching operands retained under `comparisons.target_commit`, source `pinned session`, and an `identity_mismatch` diagnostic naming that field. Both declarations still claim `complete` and `answer`; the mismatch does not convert those claims into an accepted fact.

The second pair, `report-missing.md` and `report-invalid.md`, predicts `declaration: null` and empty comparisons in both cases but distinct status and diagnostic reason: `missing` versus `invalid`/`duplicate_key`. The invalid report repeats `completion` with competing values. Inspection of the complete validator dictionary can distinguish absence from rejection even though inspection of `declaration` alone cannot.

The invariance case is `report-valid.md` against `report-prose-variant.md`: my byte comparison confirms an identical declaration suffix, while ordinary unfenced prose changes. The source predicts identical validator results. This is an intentional projection consistent with the named use; it is not proof that every possible surrounding fence or byte change is irrelevant.

## Supported, predicted and unresolved assertions

| Assertion | Grounds and limit |
| --- | --- |
| The consumer implementation is absent. | Directly supported by `AVAILABILITY.md` and the finite packet contents; absence is not a consumer defect. |
| The selected support belongs to the selected answer. | Primary and all four artifact texts exactly match their entries in `RETURN.raw`. |
| Valid, mismatch, missing and invalid categories remain distinct at the validator result. | Source-supported prediction for the supplied inputs and conditional expected/source mappings; not an executed result. |
| The mismatch retains five matching identity comparisons and one failing target comparison. | Source-supported prediction after comparing all six supplied values with `ENTRIES.json`. |
| The partial/null report is valid. | Source-supported prediction: explicit null is allowed for `partial`, while a required member remains present. |
| Removing `report_kind` would be invalid rather than equivalent to explicit null. | The author's clearly labeled manual variant follows the required-fields check. No absent-member fixture or executed result is supplied, and neither is needed to understand this conditional branch. |
| The selected path does not derive a process exit or manager judgment from the declaration. | Supported for the supplied validator/helper path by its inputs and returned values; cannot be extended to the omitted consumer. |
| The full status dictionary supports the manager's use, or needs repair. | Unresolved. Neither preservation nor loss/promotion at that boundary is shown. |
| Status handling of unavailable bytes, digest mismatch, `record=None` or `expected_digest=None`. | Unresolved because the relevant consumer branches are absent. |

No first loss or unsupported promotion required by this use is established in the inspected validator segment. Invalid inputs lose their parsed contents in that result, and prose is not returned, but the manager's stated use does not require choosing an invalid competing claim or preserving every report byte. The return correctly avoids treating these projections alone as a defect.

## Reconstruction, gaps and next material

The selected return already supplies the route, original coordinates, conditional case matrix, distinguishing pairs, limitations and next check. I did not have to invent an omitted argument mapping or consumer result to make it usable. My additional work was independent verification: comparing actual entry operands, tracing the supplied source branches, checking selected-text identity and checking the narrow pair differences. That work is my corroboration, not an executed output or an author-created artifact.

The consequential gap is **absent subject evidence**: the named status consumer. I found no missing author-created support that prevents inspection of the narrower static claim. The author supplies prose predictions rather than captured output dictionaries and labels them accordingly. Requiring program execution, capture-enforcement evidence, collection selection, rendering, disposal or producer behavior would be a different undertaking; those matters are expressly outside this question.

The smallest next material is `status._auditor_report` at the stated revision, with only any directly used helper needed to understand this bounded return. Inspect its actual expectation construction, validator call, all returned dictionary branches and companion fields. Apply the same missing/invalid and valid/mismatch pairs, keeping claim attribution separate from validation and process facts; also account for the additional branch inputs listed in `ENTRIES.json`. That source check would distinguish retention in companion data from an actual required loss or promotion. No broader repository lookup or subject execution is needed for this next static check, and neither was performed here.

This memo and its read record are the frozen first checkpoint. Shared ambient task guidance influenced scope discipline; this is not a claim of independently enforced access isolation.
