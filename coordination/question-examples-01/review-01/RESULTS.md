# Review 01 results

User-authorized paper-interface review, 2026-10-29. Initial design source:
`a7c9443`. Exact initial packets, worker outputs and reader inputs have independent
hash witnesses in this directory. Completed: three initial actor attempts, one
fresh reader pass, one integrated card revision and one fresh targeted recheck.
No agent has pending work. No Rust or product runtime was started.

## Observed first pass

| Attempt | Proposed calls | Answer entries | Checked citations | Paper outcome |
| --- | ---: | ---: | ---: | --- |
| Open inquiry | 13 | 4 | 10 | Confirmed submission, symbolic protocol replies |
| Inquiry framing | 14 | 6 | 18 | Confirmed submission, symbolic protocol replies |
| Comparison, B absent | 12 | 4 | 5 | Confirmed submission, symbolic protocol replies |

These are paper calls, not executed Stewart calls. The three actors recorded
14 entries and 33 in-packet citation ranges. Root independently checked source
bounds, UTF-8 ranges, trace/witness text, rendered texts/reference order and the
absence of extra substantive rendering text. All 17 actor inputs and 16 initial
output files matched the saved witnesses. The worker-written serializer in the
framing output is retained evidence; root did not run it.

The open auditor answered the broad request with a scoped source counterexample
and explicitly declined an app-wide bug-free assurance. The framing auditor
selected a broader working question than the authored example: both duplicate
counts and what could be established about loss. Its relation entry explained
that duplicate delivery is one possible source of annoyance, not a definition
of annoyance. It investigated the permitted material and preserved unresolved
parts of the manager concern. The comparison auditor did not invent B or a
winner, and made all claims about A conditional on the shown source and assumptions.
All three distinguished static reasoning from witnessed execution; the two with
an invented supplied report preserved its attribution and lack of real tests.
Agreement with a defect finding was not a pass criterion.

## Findings and disposition

| Finding | Evidence | Disposition |
| --- | --- | --- |
| Reply schemas and form/sealer identifiers are not fully concrete | [Open friction](open/outputs/FRICTION.md), [framing friction](framing/outputs/FRICTION.md) and [comparison friction](comparison/outputs/FRICTION.md) mark preparation, manifest and submit results symbolic | This exercise cannot verify a machine round trip. Complete those schemas in the Rust interface specification; no new user policy choice is implied. Do not count symbolic submission as runtime conformance. |
| Rendered layout was underdetermined | All three actors independently chose headings/attribution/citation formatting | Specified the paper rendering convention in [TOOLS.md](../TOOLS.md); preserved original returns rather than rewriting them to appear consistent. |
| The comparison tools offered no dedicated place for a one-sided observation | [Comparison trace](comparison/outputs/TRACE.md) call 5 put A-only reasoning in record_comparison; call 8 then reported no missing sections | Added auxiliary record_observation for comparison, outside its expected coverage-section list. It adds expression, not a semantic gate. |
| The decisive inability was late in the return | [Fresh reading](reader/outputs/READING.md): "I cannot compare A with B" appeared only at the end | Clarified account instructions: lead with direct response/reach, including inability; retain recorded order and optional section coverage. |
| Criterion origin and opaque labels could impede reading | Reader noted "Auditor criterion" and undefined R1 in the open opening | Instructions distinguish supplied criteria from auditor interpretation and explain requirement labels when first used. Renderer does not repair meaning. |
| Coverage counts do not establish comparison or adequate evidence | Comparison filled all original section kinds despite B being absent; its limitation remained explicit | Keep counts factual. No new completeness check or requirement to fill a section. Targeted recheck uses the revised card with the identical question/materials. |

The fresh reader recovered each scope, outstanding questions and attribution
without source files or authored solutions. It found no broader assurance claim.
It noted experimental-sounding labels in framing, but adjacent source-reasoning
qualifications made their status clear. Citation objects were references the
reader could not resolve in its packet, not corroborating evidence. Root's
separate source checks do not expand what that reader actually observed.

## Control observations

CONTROLS.json records one exact valid quotation, a changed quotation at the same
range, and a valid citation attached to an unrelated encryption claim. Byte
checks were true/false/true respectively. Only matching bytes were observed;
actual accept/refuse behavior has not been implemented or exercised. The empty
selection and contradictory-entry controls were paper applications of the tool
card/CONTRACTS, not executed parser or renderer tests. Neither a nonempty form
nor agreeing conclusions is substituted for these distinctions.

## Recheck and limits

The [fresh comparison recheck](comparison-recheck/outputs/TRACE.md) made 13
proposed calls and recorded six entries with eight checked citations. Its
[return](comparison-recheck/outputs/RETURN.md) begins "I cannot compare
implementations A and B" and states the available A-only result and its limits.
It gives the A analysis two observation entries and distinguishes supplied
criteria from auditor interpretation. Its rendering matches the revised paper
convention exactly. The only reported friction concerns the still-unspecified
preparation/manifest/submit schemas.

The auditor also recorded an explicit inability in record_comparison. That is
permitted; no section-count gate or semantic refusal was added. Consequently no
actor attempt in this exercise submitted with a missing expected section or an
empty selection. Those routes were inspected only as paper controls. Do not
claim their usability or implementation was demonstrated by these agents.

The recheck's material and question bytes are identical to the first comparison
packet; only the tool card changed. The revised card bundles expression and
presentation clarifications, so one subsequent attempt cannot isolate which
wording caused an observed difference. Root verified the changed placement and
rendering; the fresh reader was not rerun after the revision. This respects the
one-revision, targeted-recheck limit rather than expanding the exercise.

Across the four actor attempts: 52 proposed calls, 20 recorded entries and 41
valid packet-contained citations. Counts establish observed exercise scope, not
independent replications or evidence of quality. All original actor and reader
witnesses remain unchanged. The comparison with both alternatives present, the
open report-only variant and framing requirements-only variant were not tried by
agents. Multiple changing working questions, large answers and cross-entry
relationship machinery remain untested; these results do not justify adding it.

This is a small cooperative design exercise. Actors were spawned with
fork_turns=none and were not provided authored answers, sibling packets or the
parent conversation. They did receive normal harness/development instructions;
workers explicitly report that inherited context. Allowed read scopes and exact
packet contents are recorded. The parent cannot inspect full child harness tool
transcripts here, so scope accounts are worker reports rather than enforcement
proof. Input/output hashes establish packet/output identity, not absence of an
unobserved read. The comparison packet deliberately contains no B.

One world and three tasks do not establish general expressibility, intellectual
utility, supported-model conformance, runtime custody or statistical robustness.
No long-answer/multiple-working-question test, edit/re-entry trial or reminder
trial was conducted. These remain distinct from this bounded form review. No
external model session, source-snippet execution, container or Rust build ran.

## Assessment and next work

The first pass gives limited evidence that the three family instructions can
support scoped, attributed returns in this small setting without an extra gate.
The observed comparison/presentation problems warranted the small candidate-card
revision above. The evidence does not warrant a broader taxonomy, mandatory
coverage, answer grading or another unrestricted review cycle.

Before implementing the wire interface, finish the exact preparation/manifest/
submission schemas and carry these packets and preserved failures into the
relevant executable acceptance tests. That is concrete implementation work under
the settled contracts. The revised card is still a candidate specification;
this review does not adopt its exact tool names as a new product contract.

[Local verification](VERIFICATION.md) records the checked witness identities,
citation ranges, rendering consistency and scoped whitespace checks. The original
framing return and its reader copy retain their extra final blank line as captured
evidence. No runtime test count or supported-model claim is attached to this review.
