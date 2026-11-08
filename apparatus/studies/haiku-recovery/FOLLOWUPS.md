# Complete reading and exact calculation

Prepared by the Stewart experimenter on 2026-11-07 under the existing Haiku
recovery commission, after the first eight audits and the two-turn contrasts.
These are two further small cases, with four candidate placements each. They
retain the qualified `acceptance-05` binary, `claude-haiku-5-5`, medium effort,
24 turns, 300,000 cumulative input tokens, 24,000 output tokens and a 900-second
watchdog. Each selected audit is separately bound and inspected before the next.

## Reading beyond the first page

The task asks for the number of DATA rows, the largest integer value and its
record ID. A deterministic 260-row fixture has a unique maximum beyond byte
65,536 in the long version. It begins with a smaller local maximum. Padding is
explicitly inert. The question asks to begin with a read from byte zero; actual
tool captures, rather than a correct answer, establish whether pagination was
offered or followed.

Compare the long baseline, a compact version with exactly the same row/value
pairs fitting one page, the long version with explicit next-page guidance, and
an irrelevant heading added to the long baseline. The compact control tests
the answer task without paging. Check the exact answer against the private
reference; independently report offered next calls, attempted exact continuations,
read ranges and any alternative complete search. A correct answer obtained by
search is not proof of following a read continuation. A partial read alone does
not establish whole-file coverage. An inaccurate final answer can remain a
mechanically valid submission. Missing capture makes tool coverage unknown.

## Exact integer calculation

The task asks for the row count and signed sum of a synthetic CSV's 64 integer
values. There is no currency or real financial data. Private reference checks
use both CSV/integer parsing and a separate Decimal-based line calculation;
the raw fixture remains available for inspection. Compare the baseline, an
eight-row control, explicit eight-row subtotal guidance and changed row labels
with exactly the same 64 values in the same order.

A numerical mismatch is a narrow study finding, not a general competence score.
Keep the submitted answer and mechanically valid citations even if its sum is
wrong. If guidance produces a promising contrast, reverse the condition order
in a fresh pair before claiming repeatable benefit. Correct results in all
conditions or a failure to reproduce a mismatch remain legitimate findings.
Record the first wrong subtotal or combination when the account exposes one;
do not infer hidden reasoning from an unsupported final number.

## Evidence and disposition

`followups.py` generates only ordinary submissions and private reference records.
Its manifest hashes the generator, this protocol, all templates and the private
reference. Reference records and review instructions are outside every submitted
folder. The CSV checks establish fixture properties, not the truth of an auditor's
interpretation. A matching offline Linux rehearsal must cover every template
before paid launch. No binary or tool-feedback change is part of these cases.

Limits, unexpected provider endings or unavailable evidence can prevent a clean
comparison. Preserve and report those conditions; do not replace an uncertain
placement. Manager custody completion remains available after inspection under
the commission. Costs and placements join the same campaign accounting; billing
remains a separate observation. These eight candidates are not a quota. Stop
when the evidence is sufficient to characterize the cases or further comparisons
stop being useful. No permanent product decision follows automatically.
