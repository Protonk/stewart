# Authored comparison, not an execution result

The central comparison is A-complete versus B-duplicate under the exact same
review.json. It tests whether plausible counts, agreeing ordinary operands and
a firing control establish reviewed-measurement coverage. The predicted answer
for this construction is no: the supplied verifier should distinguish the pair
through missing and duplicate reviewed measurement identities.

The fixture was authored for this question. Its parcel-check ordinary case has
three reviewed measurements: seal, label and route. Its switch-control case has
one reviewed measurement, switch. This is hypothetical review input, not an
actual release, managerial admission or evidence of source authenticity. All
six case fields and the four review fields meet the supplied validator's
written constraints by inspection. The review uses no repeated JSON keys.

A has ten valid ledger rows: six declaration/reach/admission rows, three ordinary
comparisons and one control comparison. B changes only the measurement string
on line 5 from label to seal. Every operand, mismatch flag, note, declaration,
control row and event position stays fixed. Thus each still has three raw
ordinary comparison rows with agreeing operands and one raw control comparison
whose operands differ. B presents seal twice, omits label and presents route
once. Neither the declarations nor the authored review grant this substitution.

The third ordinary measurement is intentional. The verifier should count route
in B while excluding both ambiguous seal comparisons. Its ordinary compared
count should therefore be 1, avoiding a generic zero-ordinary-comparisons
explanation. A should count all three. Both should count the same firing control.
The summary's count changes as an outcome of membership checking; it cannot be
held fixed together with this change in duplicate membership. The input row
count, ordinary agreement and control remain fixed.

The complete proposed observation is the tuple of parse problems, full summary
with explicit review cases, and prerequisites. Parse problems must not be
discarded merely because prerequisites is empty. Raw-ledger parse_rows uses
ordinary JSON decoding; the control review must use loads_control, which
rejects repeated keys. These specimen bytes have no repeated keys, so the
central distinction does not depend on that decoder difference.

Secondary probes are separate from the central pair:

- C changes only the ordinary label row's note. Its full summary and
  prerequisites should equal A's, with no parse problems.
- D changes only the control row's actual operand from true to false, keeping
  the claimed mismatch true. Operand recomputation should extinguish the
  control and report the contradictory flag. A versus D makes the firing
  control operand-sensitive rather than merely a child-provided claim.
- E swaps the ordinary reach and admission rows. Membership labels and operands
  remain A's, but the admission has no prior reach. It should expose the event
  sequence requirement separately from the central membership effect.
- F appends one malformed line after A. It should retain A's full summary and
  empty prerequisites while separately reporting a parse problem at line 11.
  This prevents an empty-prerequisites-only observation from concealing a gap.

No project module, proposed observer, experiment, test or submission helper was
executed during construction. The six specimens are six proposed evaluations,
not six trials. Supplied tests were read as examples of source assertions; these
case IDs, three-measurement fixture, operands and exact specimens were authored
independently. No historical study answers were consulted.

Protected state consists of the pinned ledger, control decoder and supplied
tests; the common review; the proposed observer; and the selected specimens and
predictions whose stability the future comparison relies on. The author has
written only assigned output paths and promises no changes to those inputs.
AUTHORED-IDENTITIES.json records point-in-time author observations of their
bytes. These observations are neither coordinator-witnessed identity checks nor
continuous-preservation evidence. Root independently holds source pins and a
witness, but this author has not inspected either. Any future execution needs
its own authorized environment, independent preservation witness and retained
stdout/stderr/status. Before/after hashes cannot prove continuous preservation.

The provided observer is a proposal for the maintainer's next decision. It
loads only explicitly named packet files after checking their pinned hashes,
decodes the review with the supplied control decoder, and emits each specimen's
full observation. It deliberately does not implement a second ledger verifier
or assert the predicted answer. It does not invoke the wrapper review validator;
the review constraints still require the maintainer's inspection. The full
wrapper, custody, release authenticity, program exit semantics, and truth of the
child's operands remain outside the question.

From the repository root, the proposed command is:

```sh
/usr/bin/python3 -I -B coordination/fresh-authoring-01/author/attempt-01/support/observe-proposed.py --packet .scratch/fresh-authoring-01/subject-01 --specimens coordination/fresh-authoring-01/author/attempt-01/support
```

This command has not run and is not authorized by this document. It proposes
Python 3.10 or newer at that exact interpreter path, standard library only,
read access to the specified immutable files, no project installation and no
bytecode writes. Interpreter version/availability has not been checked. The
maintainer must first designate fresh retained stdout/stderr/status destinations
and the independent witness and decide whether this observer and environment
are adequate. An import, decoding, preservation or tool failure ends that
proposed execution; retain partial output rather than modifying an input and
continuing. This is an inspectable command proposal, not a reproducibility
guarantee or permission to run.

If the predictions hold, they distinguish the two explanations for these
specimens. They do not establish universal ledger completeness, the sufficiency
of mechanical prerequisites for scientific validity, or the truth or
independence of review and operands. No bypass or unexpected execution finding
is claimed. A mismatch between prediction and later observation is a result to
inspect, not something to erase by tuning the specimen.
