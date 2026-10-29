# Friction and scope

1. At calls 9 and 11, `prepare()` promises a manifest and member handles, but the card supplies no manifest serialization, prepared-handle shape, form-version token or sealer identifier. I represented those identities and the manifest reply symbolically. The answer entries and rendering are concrete; this attempt cannot verify exact production manifest bytes or a machine-readable prepare/read round trip.
2. At call 10, the rendering instruction specifies an attribution line, kind headings, exact entry text and citation lists, while explicitly leaving final Markdown layout open. I chose the exact attribution sentence, level-two headings, whitespace and compact JSON citation bullets in RETURN.md. Those bytes are a candidate rendering, not an inferred settled format.
3. At calls 12 and 13, `submit(handle, confirm)` specifies dry-run and sealing semantics but no response fields. I used symbolic descriptions of an unsealed dry run and an accepted confirmed submission. I did not fabricate a receipt, digest or complete outcome schema.

No additional tool failure was encountered in this one attempt. The absence of whole-app material and execution evidence limits the answer; it is not treated as a failure of the tools. No unresolved interface issue prevented the paper submission under the brief's allowance for symbolic missing reply schemas.

## Scope account

Actual input files read:

- BRIEF.md
- inputs/TOOLS.md
- inputs/question.md
- inputs/MATERIALS.json
- inputs/materials/requirements.txt
- inputs/materials/a.py
- inputs/materials/supplied-report.txt

Own output files read for verification: ANSWER.json, RETURN.md, TRACE.md, FRICTION.md and CHECKPOINT.md.

No filesystem content outside the allowed brief, inputs and own outputs was read. The assignment arrived with inherited conversation instructions, including the provided root AGENTS text and environment metadata; these were already visible and were not consulted as additional evidence. No ancestor coordinator files, sibling packets, authored walkthroughs, Git history, repository source, reference solutions, web pages or external accounts were opened. Standard-library Python was used only for byte-range inspection and output generation/verification; supplied code was never executed or imported. No sub-agent or external model was used.
