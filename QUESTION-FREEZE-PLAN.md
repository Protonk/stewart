# Narrow question-family freeze proposal

Prepared from the principal's narrow-freeze commission, 2026-10-31. The Riker
consultation led to this reduced scope: settle what accepting a question
promises before the first paid Messages API sanity test. Detailed recipes,
tool vocabulary and intellectual utility remain later work. This proposal
replaces the earlier sequence that put all five implementations before live
work. It authorizes no implementation or model spending.

## Five purposes

| Family | What the manager commissions |
| --- | --- |
| Open inquiry | Investigate the supplied question, without needing to justify choosing a general inquiry. |
| Inquiry framing | Formulate and investigate a working question from the manager's concern, preserving the original question and explaining their relationship. |
| Comparison | Relate alternatives to a criterion, distinguishing the manager's criterion from the auditor's interpretation, without requiring a winner. |
| Claim examination | Examine support, counterevidence, assumptions and qualifications for a stated claim, without requiring a defect, repair or verdict. |
| Experimental inquiry | Discover and develop an informative experiment from the supplied subject material and captured sources, without requiring the manager to supply a finished hypothesis or the auditor to execute the experiment. |

## Shared contractual invariants

- A family specifies the inquiry, not a required result. `answer`,
  `needs-evidence` and `reframe` are legitimate intellectual returns across all
  five, distinct from whether authoring ended, submission occurred, delivery
  verified or close completed. These names do not introduce a mandatory label,
  mutually exclusive schema, or automatic classification of content.
- The original question remains intact. A reframe may explain a poor fit and
  propose a better question; it neither replaces the captured commission nor
  silently grants another investigation. Inquiry framing explicitly includes
  developing and investigating a working question within the same commission.
- Family selection grants no additional permissions, material access or budget.
  The auditor remains read-only over captured materials while able to author
  its answer/artifacts. Even if execution becomes available later, selecting
  experimental inquiry will not itself authorize execution.
- Questions, evidence, artifacts and intellectual returns have the same meaning
  across Messages API and later Claude Code arrangements. Family-specific tools
  and expected sections may guide authoring; they do not establish different
  custody, attribution or submission contracts.
- Mechanical validity and substantive judgment remain separate. Citation
  checks establish locations and exact quotations, not support. Missing-entry
  notices remain nonblocking; incomplete and empty selections remain admissible
  and are not automatically findings of no issue. A proposed check requiring a
  particular conclusion or excluding a legitimate return must be brought back
  as a change to the commission, not added as routine validation.

## Complete experimental contribution without execution

Depending on the materials, an experiment design, concrete specimen, or precise
account of the evidence needed to develop an informative test may be a complete
intellectual contribution. Explain what the auditor accomplished and what remains
for the manager or a later executor. Runnable code, a fixed hypothesis format,
new observations and a successful experimental result are not required.

Keep captured source claims, application-source interpretation, auditor inference,
proposed experiments, predictions and supplied observations distinguishable.
An authored script is not a witnessed execution; a supplied report remains
attributed evidence. These distinctions concern the account's meaning, not six
mandatory fields or a new substantive grading mechanism.

## Minimum material guidance

Ask managers for their question/concern and the relevant captured subject and
evidence. For comparison, identify alternatives and any criterion the manager
has supplied; for claim examination, identify the claim. For experimental
inquiry, include the captured primary-source material that may inform a test,
with available version/context. A link alone does not provide its contents.
Managers need not preselect the finding, solve the comparison, enumerate every
premise, or provide the experiment's finished hypothesis. Missing evidence can
itself be the return; these suggestions are not new intake gates.

## Before the first paid API sanity test

No further family-design decision is needed to prepare a simple sanity run on
this basis. The current service implements open inquiry, inquiry framing and
comparison; dedicated claim-examination and experimental-inquiry forms remain
unimplemented. Use one existing family, preferably open inquiry, and name the
actual operations the probe is intended to exercise. Do not simulate support
for an unimplemented family or require its final vocabulary first.

The remaining launch decisions are the bounded specimen and procedural success
observations; exact model/settings, provider route and spending/retry authority;
and the binary/environment, launch, retention and stop/recovery procedure.
The [release agenda](RELEASE-PLAN.md#before-the-first-live-api-test) owns that
preparation. A successful probe establishes the exercised real-model/tool/
submission/preservation path. A failure must retain its actual outcome; honest
preservation of failure does not establish a successful submission path. This
is not five-family qualification or proof of useful reasoning. Full release
conformance obligations remain separate.

## Later dogfooding and disposition

Use later [Claude Code dogfooding](CLAUDE-CODE-PLAN.md) to investigate material
recipes, prompts, recording vocabulary, expected sections, useful experimental
artifacts, manager repair effort and model utility. Do not optimize those as a
condition of this freeze or expand beyond five families. Any executor design
remains outside this work. Formal deployment of new families will need coherent
specification, service and independent-driver changes and the relevant checks;
that is not part of the first simple API probe.

This is the short proposal for review, not a change to the service's pinned
forms. On adoption, move its contractual meanings into
[CONTRACTS](CONTRACTS.md#question-families-and-open-inquiry), retain later work in
the relevant runtime/release plans, and delete this plan and the now-answered
[Riker request](riker/QUESTION-FREEZE.md). The principal's returned instructions
supply the consultation's disposition; no further reply is needed to prepare
this proposal.

Local check records remain in `.scratch/question-freeze-01`,
`.scratch/question-freeze-02` and `.scratch/question-freeze-03`; the last folder
holds this revision's checks and host commit helper.
