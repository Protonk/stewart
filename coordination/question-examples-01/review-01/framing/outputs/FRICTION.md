# Friction

1. At call 11, `prepare()` promises a handle, member read handles, counts and observations, but specifies no reply field schema. I used symbolic labels `p1`, `p1-rendering` and `p1-manifest`, explicit ordered membership and counts. Their meanings follow the card; their concrete representation is my illustrative convention.
2. At call 13, `answer_read("p1-manifest")` is supposed to retrieve exact prepared manifest bytes, while the card explicitly leaves final serialization outside the walkthrough. It also requires a sealer and form version without supplying concrete identifiers. I could inspect the intended membership semantically but could not produce or validate an actual manifest encoding. The trace marks that response symbolic. `ANSWER.json` remains a development witness, not a substituted Stewart wire format.
3. For the rendering at call 12, the card specifies ordering, attribution, headings, exact text and listed structured citations, but leaves final Markdown layout provisional. I chose a concrete attribution line, second-level headings and compact JSON citations. `RETURN.md` preserves that choice exactly; it is not claimed as settled product syntax. Call 14's accepted outcome is likewise symbolic because the submit reply schema is not specified.

These interface omissions did not prevent the bounded reasoning or the illustrative confirmed submission. They prevent treating this paper trace as an implemented protocol run. The limited material and lack of witnessed tests are investigation limits, not tool failures.

## Scope account

Actual input files read:

- `coordination/question-examples-01/review-01/framing/BRIEF.md`
- `coordination/question-examples-01/review-01/framing/inputs/TOOLS.md`
- `coordination/question-examples-01/review-01/framing/inputs/question.md`
- `coordination/question-examples-01/review-01/framing/inputs/MATERIALS.json`
- `coordination/question-examples-01/review-01/framing/inputs/materials/requirements.txt`
- `coordination/question-examples-01/review-01/framing/inputs/materials/a.py`
- `coordination/question-examples-01/review-01/framing/inputs/materials/supplied-report.txt`

The inputs directory was listed with `rg --files`. The output-generation script and final verification read only those allowed inputs and this worker's own output files. No outside filesystem content, sibling packet, parent example, repository source, coordinator notes or Git history was read. Existing system/developer/user instructions and the dispatch message were present in inherited context; no parent-authored walkthrough or solution was consulted. No web access, supplied-code execution/import, external model, container or nested agent was used. Isolated Python performed byte-range checks, output serialization and consistency checks only.
