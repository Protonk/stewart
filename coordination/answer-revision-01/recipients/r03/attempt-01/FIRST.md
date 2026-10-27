# r03: first selected return

## Decision and repeatable claim

For the manager's named use in QUESTION.md, I can rely on the selected return's
qualified preservation account. With the stipulated exact report reads, matching
digests, and ENTRIES.json identities, the full dictionary predicted by the supplied
source distinguishes missing, invalid, identity-mismatched, and valid declarations.
It carries the completion/report-kind values as attributed auditor claims, with
an explicit note separating them from process-exit observations and maintainer
judgments. This establishes a static data-flow account, not observed execution,
truth of the claims, or authenticity of a capture.

The decisive evidence is present in the admitted subject packet. The selected
answer does not merely assert preservation: primary.txt names the companion
validation object, artifact-01.txt supplies the route and sites, artifact-02.txt
supplies manually predicted cases, and artifact-03.txt qualifies unavailable-input
branches. I found no consequential disagreement and no repair required for this
bounded use. Reading only completion.value and report_kind.value would not support
the use; that is a narrower consumer than the question names.

## Manager inspection performed

No executed return dictionary was supplied or produced. I applied the selected
answer's inspection rule to the actual source and hypothetical inputs and checked
its predicted distinctions. In either claim object, inspect reason when present;
otherwise inspect validation.status, diagnostics, declaration, and comparisons.
Read the value with attributed_to, source, and note.

| Supplied report | Predicted claim values: completion / report_kind | Distinction available inside either claim's validation |
| --- | --- | --- |
| report-valid.md | complete / answer | status valid; full declaration; six matching comparisons; no diagnostics |
| report-mismatch.md | null / null | status mismatch; declaration still claims complete / answer; target_commit comparison has expected 40 a characters, observed 40 f characters, source pinned session, matches false; identity_mismatch diagnostic names target_commit |
| report-missing.md | null / null | status missing; declaration null; comparisons empty; missing diagnostic, despite the surrounding prose saying work is complete |
| report-invalid.md | null / null | status invalid; declaration null; comparisons empty; duplicate_key diagnostic identifies completion in its message; neither repeated value is selected |
| report-partial-null.md | partial / null | status valid; declaration explicitly contains report_kind null; six comparisons match |
| report-prose-variant.md | complete / answer | same structured claim and validation content as report-valid.md under the same supplied name and identities and each report's own matching digest |

Every row also carries attributed_to="auditor", the collection REPORT.md source,
and the note that these are declarations, not observed exits or maintainer
judgments. These labels support the required distinction in the dictionary;
they do not independently establish who authored real-world bytes.

The valid/mismatch pair is inspectable and discriminating. My standard-library
byte comparison confirmed that replacing only the valid report's target_commit
with 40 f characters produces the mismatch report exactly. Both values satisfy
the supplied commit-ID pattern. Thus the differing prediction is attributable
to identity comparison rather than malformed input. The mismatch is the firing
case; the valid report is its comparison. My byte check also confirmed that the
valid/prose-variant declaration suffixes are identical, supplying the invariance
case for this route. These are input comparisons and source predictions, not
executed controls.

## Producer and consumer sites

All coordinates here are the original coordinates retained in the packet for
revision 5f00082d86768368478ed7cc85b52dd56a60255b.

- declaration-source.txt, report_declaration.py:43-94: _parse locates the
  declaration fence and raises missing when no declaration span exists. It does
  not promote surrounding prose into a completion claim.
- report_declaration.py:95-132 and control-json-source.txt, _json.py:20-34:
  decoding, repeated-name rejection, field/identity checks, and allowed claim
  values distinguish structural validity from a claimed completion. Explicit
  null report_kind is allowed for partial, but a missing member is refused.
- report_declaration.py:143-158: parser refusals become missing or invalid with
  diagnostics; parsed declarations retain field-by-field expected and observed
  identities, source labels, and matches. A mismatch retains the parsed claims.
- report_declaration.py:161-170: five expectations come from the session;
  observed_checkout_commit is compared with collected HEAD only when supplied.
- consumer-source.txt, status.py:78-82 and 92-94: claims adds attribution and
  context, while _auditor_report passes the complete validation result to both
  claim objects. The conditional projection at line 94 sets non-valid claim
  values to null, but does not erase the required distinction from the full
  dictionary. There is no supported first loss or promotion on this named route
  for the six supplied readable reports.

The selected artifacts already identify these sites and cases. I reconstructed
the predicted table from their prose and checked it against source; I did not
discover an omitted consumer or create evidence that the author supplied an
executed dictionary. The actual byte-equality and packet-hash checks described
here are my own checks, separate from the author's process claims.

## Qualifications, support, and remaining uncertainty

Supported by supplied text and my inspection: the conditional projection retains
validation; four declaration classes remain distinguishable; comparison operands
and provenance survive for mismatches; an allowed explicit null remains separable
from a null claim value caused by failed validation; supplied prose changes do
not affect the declaration. The invalid_json refusal branch is also visible in
source, but the supplied invalid report exercises repeated keys rather than
providing an additional syntactically malformed JSON example.

Predicted, not observed: every function return and branch outcome in this memo
and artifact-02.txt. Neither the author nor I supply subject execution evidence.
The selected answer clearly labels its case account this way, so this absence
does not undercut its bounded static conclusion.

The unavailable-input qualifications in the selected return are material:

- record=None predicts session_unavailable and no validation, not a declaration
  classification.
- expected_digest=None predicts validation of synthetic empty bytes, with source
  null. The missing status therefore does not establish that real report bytes
  were read. It is distinguishable from the supplied missing-report case by
  source, which remains present for that actual hypothetical read.
- Unavailable data and a differing digest both predict evidence_tampered. Their
  individual causes are lost at status.py:90-91, and the four declaration classes
  cannot be determined from that branch. This limitation is acknowledged and
  does not contradict the qualified readable-input finding.
- collected_head=None removes the HEAD comparison. The preserved comparison set
  exposes this limit; valid alone cannot certify an independently checked HEAD.

Absent subject evidence: an executed dictionary, actual process observation,
real capture provenance, enforcement of reads, and downstream presentation.
Those are not missing premises for the specified static boundary because the
question stipulates read inputs and excludes those broader claims. Asking to
qualify them would expand the undertaking. No omitted subject implementation
needed for this static decision was identified.

Missing author-created support: none necessary for the static conclusion. The
selected return contains no command transcript proving its claimed hashing or
complete read history; those remain attributed process claims. I independently
checked all 23 PACKET.json entries and all 16 subject/MANIFEST.json entries for
length and SHA-256 agreement, and checked that primary and all three selected
artifacts match their text in RETURN.raw. These checks support the bytes inspected
now, not the author's earlier conduct. No complete access log or enforced
isolation has been established.

Smallest further check: none is required to finish this static account. If an
execution claim is later commissioned, retain actual full dictionaries for the
valid/mismatch, missing/invalid, and valid/prose-variant cases under an explicit
execution grant. If a rendered-status claim is requested, inspect that renderer's
actual handling of validation, source, and reason before carrying this conclusion
across that new boundary. Neither follow-up is performed or authorized here.

## Freeze

FIRST.md and READS-FIRST.json are the first-return checkpoint. I stop after saving
and verifying their presence and JSON readability. No future-phase evidence,
other answer, live source, subject execution, Git, network, or nested agent was
used. Shared ambient instructions influenced the method; they are not evidence
of technical isolation.
