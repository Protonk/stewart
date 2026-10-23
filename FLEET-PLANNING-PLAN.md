# Establish fleet planning for Stewart development

Status: pending local work. Establish the practice described here; preserve
unrelated changes and leave product behavior unchanged.

The user wants to be able to say “write me a fleet approach for this change”
without specifying how to organize the agents. Add concise standing guidance
that makes this a useful commission. Its audience is a coordinating agent and
the workers it commissions, with discretion to inspect the repository and
make implementation decisions. The user should review the direction, delegated
authority and first useful result; the coordinator owns organizing the work.

Use the harness's delegation and workspace facilities. This is a development
practice, not an extension of Stewart's audit machinery. Do not build a fleet
framework or require development workers to follow Stewart's custody workflow.

The convention should ask an agent to:

- Investigate enough to propose a concrete outcome, distinguish protected
  obligations from changeable behavior and implementation, and identify the
  consequential product decisions that remain for the user.
- Choose useful concurrency, assignments, dependencies, workspace and edit
  ownership, integration order and verification. Explain why parallel work
  helps; available worker slots are a ceiling, not a staffing requirement.
- Assign one coordinator responsibility for the coherent result. Give workers
  complete changes, including affected tests and documentation, and leave
  routine implementation choices with them. Make shared boundaries explicit.
- Make the first wave ready to dispatch. Keep later assignments provisional
  where they depend on discoveries. Propose a bounded effort and identify when
  to stop, combine or replace assignments.
- Once execution is authorized, let the coordinator revise assignments,
  resolve ordinary disagreements, integrate changes and arrange targeted
  review within scope. Return to the user for decisions beyond that scope or
  changes to protected obligations. Respect authorization already supplied.
- Keep worker returns compact: changes, verification, consequential decisions
  and integration issues. Verify the combined result; use independent review
  where it can challenge consequential assumptions.

Preparing an approach does not itself launch implementation. Make that boundary
clear without adding approval gates inside already authorized work.

Establish these planning lifecycle rules alongside the convention:

1. Plans are ordinary tracked working documents with stable paths while active.
   Update their current account as work changes; Git preserves the history.
   At completion or abandonment, give unfinished work an explicit disposition,
   move enduring explanations into their proper homes, and delete the plan.
   There is no obligation to preserve every planning paragraph in current docs.
2. Lasting code and documentation explain mechanisms, constraints and reasons
   without planning coordinates such as “Phase 3c.” Maintained AGENTS and README
   files must not link or route readers to particular plans, even existing ones.
   General discovery conventions are fine. Product code and tests must not
   require a particular temporary plan to survive. Preserve historical evidence
   rather than rewriting captured documents to satisfy current guidance.

Choose the smallest useful home for this guidance after reading the local
documentation. Remove conflicting instructions and existing plan dependencies,
including the coupling in `tests/test_orchestration_plan.py`. Use focused
mechanical checks where they enforce the lifecycle rules honestly; review
planning-coordinate comments for meaning rather than banning legitimate domain
vocabulary. Avoid elaborate templates or speculative enforcement machinery.

Finish with a concise account of the adopted convention and appropriate
validation. The standing guidance must work without this document. Dissolve
this plan when that work is complete.
