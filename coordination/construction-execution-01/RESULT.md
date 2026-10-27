# Returned construction: one captured execution

The unchanged returned observer completed one invocation on 2026-10-27 at
04:01:26 UTC, evaluating all six specimens in A–F order. Every frozen prediction
matched. Root's 107/107 captured-output comparisons passed; exit was 0 and stderr
empty. [Independent captured-result review](review/attempt-01/RESULT-REVIEW.md)
corroborated the complete observations with 215/215 checks and no remaining
substantive blocker. One prose correction narrowed C's invariance claim; no
input, prediction or observation changed.

The main comparison separates raw counts and a firing control from exact reviewed
membership. A and B each contain four valid comparison rows, with the same
operands and control. B changes only one measurement identity. The verifier
counts only its unambiguous ordinary measurement, reports missing label and
duplicate seal, and retains the firing control. C's note-only change leaves the
full summary and prerequisites unchanged, with no parse problems. The other
probes distinguish operand recomputation,
event ordering and parse gaps. These observations support this construction's
specific explanation; they do not establish universal completeness or scientific
validity from mechanical prerequisites.

## Observed comparison

All six returned ten valid parsed rows and four raw valid comparison rows.
Values below are counted ordinary/control comparisons and mismatches, not raw
row totals. Full summaries and ordered prerequisites are retained in the exact
[captured output](OBSERVATIONS.jsonl), whose stdout identity is recorded in
[CAPTURE.json](CAPTURE.json). [EXPECTED.json](EXPECTED.json) is the manually
transcribed expectation frozen before execution, checked against the author's
unchanged PREDICTIONS.md by the independent reviewer.

| Specimen | Ordinary compared / mismatches | Control compared / mismatches | Distinguishing observation |
| --- | ---: | ---: | --- |
| A — complete | 3 / 0 | 1 / 1 | No parse problem, summary diagnostic or unmet prerequisite. |
| B — duplicate membership | 1 / 0 | 1 / 1 | Missing parcel-check:label and duplicate parcel-check:seal; both seal occurrences excluded. |
| C — note change | 3 / 0 | 1 / 1 | Full summary and prerequisites equal A; no parse problems. |
| D — control operand change | 3 / 0 | 1 / 0 | Recorded operands agree despite the claimed mismatch; inconsistent switch-control and no firing control reported. |
| E — admission before reach | 0 / 0 | 1 / 1 | Admission unaccepted; unadmitted comparisons, unresolved admission and sequence error reported. |
| F — malformed line | 3 / 0 | 1 / 1 | One invalid-JSON problem at line 11; full summary and empty prerequisites equal A. |

In E, empty missing-measurement and uncompared lists do not establish coverage:
the ordinary admission never became valid. In F, empty prerequisites do not
erase the separately captured parse problem. These were authored predictions,
not unexpected findings or conditions repaired after execution.

## Selection, execution and preservation

The user's [commission](COMMISSION.md) follows the completed fresh-authoring
pilot and its recipients' recommendation. The prior pilot did not execute this
construction; its historical report remains unchanged. This new run used the
60,027-byte final envelope committed at 9ffad1f, matched to the prior raw transport,
accepted binding, snapshot and retained completion identities. Its SHA-256 is
`d02ada609d13ab069dcdd11382686d3a81da6b3e0cc0845ebc3452dc8f6577c3`.
All three full source files were compared to Git revision 81b557a; the finite
source packet and six full source/guidance identities were also checked.

Preparation materialized exactly 13 regular files: ledger, control decoder and
supplied tests; review, six specimens, predictions, construction and observer.
The observer loads the ledger and decoder; it hashes the tests without running
them. The fixture's review constraints were independently inspected, not passed
through the full wrapper validator. No source, observer or specimen was edited.

The interpreter probe observed CPython 3.14.9 on macOS 26.7.1 arm64. The resolved
binary identity, exact argv/cwd/environment and trusted-host limits are retained
in PREPARATION.json. The observer used `-I -B -S`, closed stdin, a fresh stage as
cwd and the three-variable environment specified in [PROTOCOL.md](PROTOCOL.md).
No installation, shell inside the child, network call or project wrapper was
needed. The driver reserved the invocation exclusively before launch. PID 69922
terminated normally; no timeout, kill or caught parent-failure intervention was
observed. Capture contains eight JSONL records: before, six specimens and after.
Stdout is 9,270 bytes, SHA-256
`5b30fad3c0202277a008f54043107ff45ddf51dccbf8bec52405773c9d39dbcc`.

The parent verified stage and independent witness inventories immediately before
launch and after observed termination. File hashes, lengths, modes, device/inode
identities and recorded timestamps matched preparation. Child endpoint hashes
matched the same 13 protected files; per-specimen read-byte hashes matched their
independent witnesses. Stage remained cache-free with files 0444/directories
0555. These are observed permissions and endpoint checks in a cooperative,
single-owner run. They do not prove continuous preservation, that an owner could
not change permissions, or adversarial exact-source loading. The interpreter,
stdlib and host libraries remain trusted; the binary alone does not pin all of
them. Both child records explicitly leave continuous preservation unestablished.

## Verification and its limits

Preparation passed 60/60 checks. Root's six static revision checks passed.
Independent preflight reviewed 63 frozen inputs, seven Git reads, fixture
constraints, all specimen transformations and complete expected summaries.
Its 410/411, 24/25 and 9/9 comparisons preserve two nonblocking discrepancies:
an original comparator compared to its announced revision, and a reviewer
line-diff predicate corrected by AST inspection. Neither was an observed
construction failure, and neither original check was rewritten. The
[review disposition](REVIEW-DISPOSITION.md) explains both.

Preflight also found a caught-parent-error gap in the first driver. Before any
observer launch, root revised shutdown/reaping and the posttermination claim,
then obtained review of the exact replacement identity. Original preparation,
driver and comparator pins remain retained. The replacement's exceptional
paths were inspected, not exercised by fault injection. This normal run did
not qualify abrupt parent/host failure or loss of every recording channel.

The comparator was frozen before launch and ran only against captured output.
Its 107/107 checks cover full summary equality, ordered prerequisites, parse
expectations, record membership/order, capture bindings, preserved input identities
and the paired controls. Counts are overlapping checks, not independent trials
or an efficacy score. Actual selectors: **one observer process, six specimen
evaluations, zero pytest nodes, zero installed-wheel runs**. No target rerun or
input tuning occurred. Product/runtime/tests/bundled-guidance bytes remain
unchanged. This is development evidence, not product custody, release, delivery,
stop/access enforcement, retirement or platform acceptance.

Independent result review verified all 48 frozen result inputs, the original
expectations, full captured records and parent/child identities. Its 215/215
checks corroborate root's 107/107. The initial draft's “full result invariant”
wording for C was too broad: its emitted name, length and digest differ. Root
applied the precise summary/prerequisites claim and the reviewer verified it;
both drafts remain retained. The reviewer returned and is stopped. No unresolved
effect, prediction discrepancy or further study phase remains.

## Evidence and disposition

Retain `.scratch/construction-execution-01/` with this report: independent original
and staged witnesses, preparation/probe, both driver/comparator revisions, frozen
review inputs, preflight checks including failures/correction, reservation/plan,
PID/exit, raw stdout/stderr, parent inventories and COMPARISON-01.json. The eight
adjacent command outputs `construction-execution-01-{prepare,driver,comparison,final}.{stdout,stderr}`
under `.scratch/` retain outer command output. Nothing is pruned or disposed.
The earlier fresh-authoring witnesses retain their original report ownership.
Tracked OBSERVATIONS.jsonl and EXPECTED.json carry the compact observed/predicted
record; a Git clone does not carry the entire local evidence population.

Preparation was committed as 4bc6bd9. Final retained-evidence/document checks
passed 278/278, recorded in FINAL-CHECKS-01.json and its captured output. Final recording
and the committed-byte/evidence inventory are located by COMPLETION.json under
this study's scratch root; inspect that record and Git after interruption.
Absence of COMPLETION.json means final mechanical recording is unfinished.

For W01/F2, the returned construction now supports an executed, precisely bounded
local comparison as well as recipient inspection. It adds no alternative-interface
comparison, actual late finding, partial/reframed/non-answer authoring or cap
pressure evidence. Broader question/outcome coverage remains open. No durable
schema, custody policy, successor executor, retry facility or protected obligation
has been selected. Further substantive work needs another bounded commission;
the completed substantive task ends with evidence verification and recording at
a clean pause point. No additional dispatch is pending.
