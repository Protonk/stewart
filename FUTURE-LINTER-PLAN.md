# Future linter for read-only commissions

Explore a tiny, deterministic, non-agentic linter inside Stewart, operating
after auditor answer preparation. This is a design marker; no implementation
is commissioned now. The initial scope is redundant caveats saying that an
examination was read-only when the commission already explicitly established
that condition. No model calls or general prose rewriting belong in this path.

The motivating reading and principal's direction are retained in
`.scratch/frsrr-baseline-a-01/review/reading-01/`, particularly
`second-form-response.txt` and `scope-direction-01.txt`. General comment
interpretation and reproducing a better reviewer-written answer are outside
this work.

## Candidate behavior

Consider two companion copies of the prepared answer:

- A **trimmed copy**, omitting only recognized redundant read-only caveats.
- A **hinted copy**, retaining the text and marking candidate omissions with
  a short reason, so the proposed changes can be inspected.

Use an explicit recorded commission condition to establish applicability;
absence of execution tools alone does not establish that the manager asked for
a read-only examination. Decide how to represent that condition before coding.
Keep substantive limits: missing evidence, unperformed work needed to answer the
question, uncertainty and conditions on a conclusion. A sentence mixing these
with a method caveat should remain intact when the rule cannot safely separate
them; it may receive a hint. Initial rules should recognize a narrow set of
phrases and contexts rather than attempt open-ended semantic editing.

Keep the prepared selection and faithful rendering unchanged. Label companion
copies as Stewart-derived, bind them to the source preparation and rule version,
and retain exact locations and removed text. This must fit the current
[rendering contract](CONTRACTS.md#readable-answer-rendering) and
[faithful-return obligation](ACCEPTANCE.md#c5--the-return-is-complete-and-faithful).
Their exposure, delivery and relationship to submission remain design decisions;
adding members to the sealed return would require an explicit contract change.

## Remaining work

- [ ] Specify the applicability signal, eligible passages and the two outputs,
  including behavior when preparation changes. Use retained answers and small
  examples; do not alter historical returns.
- [ ] Compare a firing example of a redundant read-only notice, a differing
  commission or substantive caveat that must survive, and an unchanged answer
  with no eligible passage. Check false removals, readable results and exact
  recovery of the original text before proposing implementation.
- [ ] Decide whether to proceed, narrow or abandon the idea. If selected, align
  the interface and custody specifications and identify the checks required by
  [DEVELOPMENT](DEVELOPMENT.md#what-to-run-for-what-you-changed) before coding.

At completion or abandonment, give remaining work a disposition, retain the
evidence, move adopted behavior into specifications and tests, and remove this
plan.
