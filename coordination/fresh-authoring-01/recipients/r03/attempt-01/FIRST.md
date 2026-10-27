# r03 first inspection

I recommend commissioning the six proposed evaluations, conditionally on a complete execution grant and identity-bound staging of the supplied bytes. The construction is inspectable and, by static source tracing, makes the intended distinction. I found no missing author-created dependency that prevents this decision and no reason to require a bypass or a different substantive outcome. Nothing has been executed by this reader, and this recommendation is not an execution grant.

My inspection is limited to the granted r03 packet and required guidance. Its claimed subject revision is `81b557a78db156e7bfc5e8d35ece9d1438608d87`. A standard-library byte/hash check found all 8 source descriptors, the answer, and all 18 support descriptors matched their supplied files: 27 matching identities. This is my point-in-time observation of the recipient packet, not independent verification of Git provenance, historical preservation, the author's work process, or future execution. Root's dispatch says source and packet were independently checked; I did not inspect its witness.

The common hypothetical review is supplied as `review.json` (object-01). It admits ordinary case `parcel-check` with `seal`, `label`, and `route`, and control case `switch-control` with `switch`. The two cases have the exact required fields, unique nonempty IDs, recognized populations, Boolean admissions, nonempty role/prediction text, and unique nonempty measurement lists. The four review fields also meet the supplied validator excerpt. I see no repeated JSON keys. This is an authored review fixture fixed independently of the emitted comparison membership, not an actual released review or independent managerial admission. Its hypothetical status fits the question.

The exact A/B specimen bytes are present, not reconstructed from prose. Both have ten rows: declaration/reach/admission for each case, three ordinary comparisons, and one control comparison. A (object-02) uses the three reviewed ordinary IDs once each. B (object-03) changes only line 5's `measurement` value from `label` to `seal`. Its row count, operands, mismatch flags, notes, declarations, control, and event positions remain fixed. Both ordinary operand pairs agree on every row, including B's two differently shaped seal comparisons. The control compares Boolean false with true. B therefore has two seal occurrences, no label occurrence, and one route occurrence under an unchanged review.

The third ordinary measurement matters: `route` survives counting in B. A generic absence of ordinary comparisons should not explain B's refusal. The raw compare count stays four, including three ordinary comparisons. The verifier's admitted/countable ordinary total changes from three to one as an outcome of excluding duplicate membership. Keeping that output count fixed is not the proposed invariance. This necessary distinction is explicitly explained by the author, rather than concealed as a second input mutation.

The pinned `ledger.py` supplies the consequential route. `parse_rows` validates each row and retains parse problems separately. `summarize(rows, cases=review["cases"])` takes expected IDs from the supplied cases, collects admitted comparisons by case and measurement ID, reports missing/duplicate/unexpected IDs, and counts only reviewed IDs with one occurrence. It recomputes disagreements from operands. `prerequisites` reports summary anomalies and requires a counted firing control, but receives no parse-problem list. The intended observation must therefore retain parse problems, full summary, and prerequisites together.

My static predictions agree with the supplied predictions:

| Specimen | Valid rows; parse problems | Ordinary counted comparisons / mismatches | Control counted comparisons / mismatches | Distinguishing result |
| --- | --- | --- | --- | --- |
| A | 10; none | 3 / 0 | 1 / 1 | No summary gaps; prerequisites empty. |
| B | 10; none | 1 / 0 | 1 / 1 | Missing `parcel-check:label`; duplicate `parcel-check:seal`; those two prerequisite messages. |
| C | 10; none | 3 / 0 | 1 / 1 | Full summary and prerequisites equal A despite the changed note. |
| D | 10; none | 3 / 0 | 1 / 0 | Control fails to fire; `inconsistent_comparisons` names `switch-control`. |
| E | 10; none | 0 / 0 | 1 / 1 | Premature admission, unresolved ordinary admission, and comparisons without admission. |
| F | 10; invalid JSON at line 11 | 3 / 0 | 1 / 1 | A's summary and empty prerequisites coexist with a separate parse problem. |

C (object-04) changes only the label comparison's note; this is the permitted invariance. D (object-05) changes only the control's actual operand to false while retaining its true mismatch flag. The two expected diagnostics in D are a deliberate consequence: recomputation both extinguishes the control and exposes the contradictory claim. D thus tests operand sensitivity rather than trusting the flag. E (object-06) swaps ordinary admission and reach. Its later reach does not retroactively establish admission; its missing-measurements and uncompared lists should remain empty because the case was never successfully admitted. F (object-07) appends `not a JSON row` to A. Its parse problem is not a `summarize` malformed-row diagnostic because the bad line is filtered before summary. Neither E's empty membership-gap lists nor F's empty prerequisites establish coverage.

The support is sufficient to inspect these claims:

| Supplied support ID / packet source | Consequential use |
| --- | --- |
| `review.json`, objects 01–07 | Exact fixed review and all six exact specimens; the essential comparison evidence. |
| `CONSTRUCTION.md`, object-08 | Input/output invariants, scope, protected material, proposed command, and acknowledged environment gap. |
| `PREDICTIONS.md`, object-09 | Full expected diagnostics and counts, expressly unobserved. |
| `observe-proposed.py`, object-10 | Exact unexecuted observer; I can inspect its load, parse, summarize, prerequisite and emission steps. |
| `source/ledger.py` | Actual subject definitions for validation, membership exclusion, event order and operand equality. |
| `source/experiment-EXCERPTS.txt` plus `measurement_problem` in the ledger | Review and case constraints; enough for the requested static fixture inspection. |
| `source/_json.py` | Control-decoder duplicate-key rule; distinct from raw-ledger decoding. |
| `source/test_stewart_ledger.py` | Existing written assertions corroborating intended distinctions; no observed tests and no substitute for source tracing. |
| `AUTHORED-IDENTITIES.json`, object-11 | Attributed author identity observations, expressly not continuous preservation. |
| `DRAFT-NOTE.md`, `final/REVISION.md`, `final/RETURN.md`, objects 13–15 | Attributed construction, self-check, and stopping accounts; substantially redundant for specimen semantics. |
| `draft-helper-stdout.json`, `draft-coordinator-result.json`, objects 17–18 | Attributed structural acceptance and byte/snapshot checks only; neither assesses intellectual correctness. |

The two author read ledgers (objects 12 and 16) were byte-hashed but not substantively read. Their procedural detail is unnecessary to inspect the finite construction; I do not independently establish the author's zero-execution account. The completion claim and final self-check remain claims even where their specimen descriptions agree with what I read. No absent specimen, unavailable support object, or contradiction between the selected construction and its explanation was found. Repeated explanatory/structural accounts add provenance context, not independent confirmation of the predictions.

The observer is also inspectable. It hashes the pinned ledger, decoder and tests, loads the ledger and decoder by explicit file paths, decodes the common review with `loads_control`, and emits each specimen's parse problems, full summary and prerequisites. It does not execute tests, invoke the wrapper, run a replacement verifier, or assert that the predictions succeeded. It fingerprints the authored files and itself before/after; it hardcodes pins only for three subject files. Consequently an arbitrary directory with the expected filenames is not sufficient to bind execution to this returned construction. Its repeated path reads also do not establish continuous preservation. These are commissioning conditions, acknowledged in the construction, rather than hidden scientific results.

Before execution I require the following named operational material. These are execution/environment dependencies outside the completed construction undertaking, not requests for the author to conduct a new investigation:

1. An `EXECUTION-GRANT` naming the six A–F evaluations, actual working directory, exact command, explicit interpreter, read/write bounds, and stop rules. The authored command proposes `/usr/bin/python3 -I -B` with the original author support and subject paths. Those paths are outside this reader's grant and were not inspected. The manager must bind the actual command to the selected bytes, whether at those established locations or at newly staged locations.
2. A `STAGED-INPUTS` record mapping the observer, review, A–F, predictions, construction explanation, ledger, decoder and tests to execution paths and the selected identities. This is manager preparation using already supplied author support and subject source. It requires no additional subject source or author reconstruction.
3. An interpreter/environment record establishing the actual executable/version and the proposed standard-library-only environment. The author proposes Python 3.10 or newer but has not established interpreter suitability. A future environment check is not an observation already made in this inspection.
4. A preservation/capture arrangement naming its independent observer, finite protected selection, timing/scope and retained stdout, stderr, exit-status and partial-output destinations. Preserve unexpected results and stop on tool/preservation failure. Any limitation to endpoint checks must remain a limitation; neither matching endpoints nor restored bytes prove uninterrupted preservation.

No full wrapper, release-authenticity evidence, real parcel facts, or further historical material is needed to decide whether this bounded pure-verification experiment merits running. Those would answer different questions. Six proposed evaluations should be commissioned once the operational conditions are concrete; their execution may confirm or falsify these predictions. Even confirmation would establish this finite distinction, not universal completeness, truth of the operands, or scientific sufficiency of empty prerequisites.

I stop with this first memo and its read ledger. No later material has been read, no code or experiment has been run, and this memo is preserved for any later comparison.
