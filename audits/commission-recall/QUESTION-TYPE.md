# Audit question types

Maintainers select one primary question and the decision its answer informs.
Use the chooser, then read the relevant recipe; name that section in the
assignment so the auditor need not read the whole guide. Selection is a judgment
expressed in prose, not an assignment-schema field or a verdict from Stewart.
Other workspaces may supply their own question guidance.

Question type and report kind are separate. Any recipe may yield an `answer`,
`needs-evidence`, or `reframe`; see the [reporting obligations](README.md#report-kinds-and-manager-follow-up).
A request for missing evidence or a proposed better question is a useful
hand-back, and grants no authority to expand the assignment.

Recipes and examples grant no permissions. Static analysis can propose cases;
constructing specimens or scripts, executing trials, and external research need
their corresponding assignment grants. Read only the applicable section of
[AUDIT-PROTOCOLS.md](AUDIT-PROTOCOLS.md) when those capabilities are assigned.
For input selection and custody, use the [manager quick start](README.md#manager-quick-start).

## Choose a question

| Need | Primary question | Useful result |
| --- | --- | --- |
| Establish whether a measurement distinguishes the intended property | [Instrument discrimination](#instrument-discrimination) | The actual comparison, independent contrasts, and the limits of its reported result |
| Follow information and its evidentiary meaning across boundaries | [Information preservation](#information-preservation) | A producer-to-consumer trace and the first supported loss, promotion or unresolved premise |
| Design a bounded attempt to break a contract | [Constrained experiment construction](#constrained-experiment-construction) | An inspectable experiment, or granted trial evidence with preservation checks |
| Decide whether a retained artifact supports the claim a consumer makes from it | [Receipt sufficiency](#receipt-sufficiency) | A premise table with binding strength, the first unbound premise the consumer relies on, and the smallest addition that would bind it |

## Instrument discrimination

> Does this instrument distinguish its claimed property from nearby properties
> that should not affect its answer?

**Supply:** the claimed property, instrument, selected population, and a few
entry inputs/results. State the decision that depends on trusting the
measurement. Define the contract without prescribing all the test specimens.

Ask the auditor to inspect selection, normalization, and the actual comparison,
then independently devise a case changing only the measured property and a
case varying something the instrument must ignore. State which distinction each
contrast tests. A planted failure establishes sensitivity to that failure;
it does not establish every claimed distinction. Supplied examples are not an
exhaustive search space.

**Example:** assess whether a configuration comparator detects a changed
setting value while ignoring explanatory text. Changing both at once
does not identify which property the comparison reads. Decide whether the
comparison's result can support a conversion claim or needs narrower wording
or better controls first.

**Return:** the comparison actually made, what the independent contrasts would
establish, and the first unsupported claim or missing evidence. Separate static
predictions from retained observations and new executions. A measured zero
requires an observed nonzero control and a selector count; a qualitative static
conclusion states coverage and assumptions instead.

**Stop:** after tracing selection through comparison and result classification,
assessing the selected cases and contrasts, and identifying the evidence ceiling.
A supported finding, no supported finding within that boundary, or a precise
unresolved premise can each answer the decision.

## Information preservation

> Does this information survive a named producer-to-consumer boundary with its
> meaning and evidentiary status intact?

**Supply:** one bounded route, entry artifacts, consumer, distinctions that
should survive, and intentional projections or normalizations. State which use
of the consumer's output depends on preservation.

Ask for the first point where a required distinction becomes unavailable,
changes meaning, or gains unsupported authority. Inspect companion artifacts,
bindings and actual consumer reads: a missing field need not imply loss, and a
present field need not be used. If the preservation requirement is unsettled,
report that premise rather than inventing a requirement.

**Example:** trace a parsed field through serialization and inspection output.
Assess whether an absent field remains distinguishable from an explicit null.
The decision is whether a migration consumer can use that output for its stated
purpose. Keep the claim bounded to the named route.

**Return:** precise producer/consumer sites, a pair of inputs that ought to
remain distinguishable, the observed preservation or first supported failure,
and the consequence for the named use. Distinguish an intentional projection
from loss of information required by that consumer.

**Stop:** once the named route and its meaningful distinctions are accounted for,
or a missing contract or artifact prevents that account. Report the distinguishing
next check without expanding to unrelated consumers.

## Constrained experiment construction

> Can a small experiment break contract C by varying X while preserving S?

**Supply:** the contract or observable, admissible variation space, protected
state and its preservation criterion, available inputs/tools, and concrete
construction or execution grants. Let the auditor propose hypotheses inside
that space. The target may be a counterexample, a distinction between rival
explanations, or a threshold; define an answering observation without requiring
a particular verdict.

**Example:** vary branch layout in authored parser specimens to look for loss
of a typed value distinction, while keeping the grammar and reference model fixed. The decision is whether a proposed admission boundary
needs repair or narrower qualification. The auditor chooses distinguishing cases
within the granted variation space.

Apply the [experiment protocol](AUDIT-PROTOCOLS.md#experiment-protocol).
**Return:** inspectable artifacts, hypotheses and predicted observations for
construction-only work; for granted execution, retain trial and preservation
evidence as well. Distinguish what was proposed, constructed and run. The
maintainer chooses what merits independent reproduction or a permanent test.

**Stop:** construction-only work ends with unexecuted artifacts and proposed
commands. Execution ends at the assigned trial boundary or a protocol stop such
as failed preservation. An unmeasured preservation criterion cannot support the
requested counterexample; failure to find one does not establish C universally.

## Receipt sufficiency

> Does this retained artifact bind the claim a named consumer makes from it,
> and what is the smallest addition that would?

The object is one artifact at rest, not a route: a receipt, record, manifest
or derived view, read for what it can and cannot establish about a claim.

**Supply:** the artifact, the producer that wrote it, and the claim a named
consumer makes from it, in the consumer's own words. State the decision that
rests on the claim. Supply the companion artifacts the claim's bindings run
through, not a verdict on whether the claim holds.

Ask the auditor to enumerate the claim's premises: who produced the artifact,
from which inputs and population, under what code and environment, and when.
For each premise, classify how the artifact binds it: by digest, by a reference
chain to another retained artifact, by assertion only, or not at all. Identify
the weakest link the consumer actually relies on and the drift, error or
substitution it would admit undetected. Propose the smallest addition that
would bind that premise, and say what the addition still would not establish.

**Example:** a replay receipt is cited as evidence that a structural
comparison ran over the declared inputs. Its rows bind the observed operand to
the input by digest and reach the declared expectation through a chain of
receipts, but they identify the comparator only by an aggregate module digest
and record no expected operand beside a match. The decision is whether the
receipt can be cited for that claim as written, or only for the recorded
operands until the comparator's identity and the expected side are recorded.

**Return:** the premise table with each binding's strength and source, the
first unbound or assertion-only premise the consumer relies on, the undetected
change it admits, and the minimal addition. A recorded value establishes that a
value was written, not that a function consumed it; a reference chain is as
strong as its weakest digest. Distinguish what the artifact fails to bind from
what no artifact could bind without re-execution.

Finish with the exact claim a maintainer may repeat and the assumptions it still
needs. Internally consistent paths, sentinels and line numbers can detect
misassociation without independently establishing historical execution. If
reuse relies on faithful recording, say so; do not turn that assumption into a
verified premise. Keep proposed mechanisms unresolved when a rival remains
indistinguishable. Stronger acquisition records can improve a binding without
becoming absolute attestation. Scientific sufficiency remains the maintainer's
judgment, not a grade computed from the premise table.

**Stop:** when every premise of the stated claim is classified, or when the
claim itself proves unsettled, in which case report the premise the consumer
and producer disagree on. Do not re-run the producer, reconstruct lost
provenance by hand, or widen to artifacts the consumer does not cite.

## Suggestions for prompt authors

Write the prompt backward from the decision it should inform. Name the uncertainty
and what evidence could change that decision. If parts of the assignment could
produce independently useful answers for different decisions, consider separating
them.

Add context where it changes the investigation: the relevant contract, essential
definitions, dependency boundary, and the role of each supplied input. Distinguish
established requirements from suspected explanations. Leave room for the auditor
to discover mechanisms and construct cases within scope. For each background
paragraph, ask what the auditor would misunderstand without it; remove paragraphs
with no concrete answer.

Before launch, imagine receiving a supported finding, no supported finding, or an
unresolved question. Each should be an acceptable outcome with a useful consequence
for the decision. Judge prompt revisions by independently checkable results and
the maintainer work needed to interpret them. Treat expectations about a particular
model as hypotheses to test, and promote additional instructions into general
guidance only when experience across different assignments supports them.
