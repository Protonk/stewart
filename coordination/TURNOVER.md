# For the next coordinator

2026-10-29, from the coordinator who completed the design review and cleanup.
Source checkpoint: `dc3a675`. Updated 2026-10-30, at `aa029bd`, after the
steps 1–6 build: the state below is current; the context bullets are the
earlier coordinator's and still apply.

Stewart has graduated from an extended design conversation into a lighter working
style aimed at implementation. The user explicitly closed the review, asked for
one design and path, and then removed the elaborate coordinator recording duties.
They want your judgment, organization and integrated results. Routine choices
are yours to resolve; involve them when a choice changes what the product promises
or what its participants can express. Notes are incidental support for that work.

The current account is [DESIGN](../DESIGN.md), [CONTRACTS](../CONTRACTS.md),
[ACCEPTANCE](../ACCEPTANCE.md) and [TRANSITION-PLAN](../TRANSITION-PLAN.md),
with the exact interface in [docs/INTERFACE.md](../docs/INTERFACE.md) and
[docs/QUESTION-FORMS.md](../docs/QUESTION-FORMS.md).
The old conversations and alternative designs were deliberately removed after
extraction. Their absence is not a gap to repair by reconstructing history.

No worker or uncertain operation is pending. The Rust audit service in
`service/` (binary `stewart`) is built through step 6 of the plan: the manager
commands, the run adapter, the auditor's tools, seal, delivery and close. Its
scripted acceptance suite (`apparatus/acceptance.sh`, an independent driver
against a fake provider) passed on Linux aarch64 and x86_64. No real model has
been run against it. Python remains frozen. What is not done, and why, is in
TRANSITION-PLAN under "Not done, and why"; steps 7–9 are not commissioned.

Some context I can offer beyond those documents:

- **The simple manager experience is the point of much of the design.** The user
  wants the manager to attend to the question, materials, whether an auditor has
  been summoned and whether its answer returned. Their insistence on one close
  action came from that aim. My reading is that they will accept considerable
  internal care around failures, provided it does not turn into a new manager
  recovery workflow. Cooperative mistakes, such as changing permissions while
  commissioning, were the motivating examples.
- **Question guidance matters to them.** They see the boundary as an opportunity
  to teach better questions and
  evidence habits. They also resisted making a broad request expensive to ask.
  Open inquiry is a normal route, and incomplete or unhelpful answers are an
  accepted consequence of avoiding invented findings and compulsory filler.
- **The paper exercise was deliberately small.** It exposed concrete friction:
  comparison needed room for one-sided observations, and the decisive inability
  needed to be easy to find. It did not justify a larger taxonomy. Its
  preparation and submission replies were symbolic. Empty and missing-section
  submissions are now exercised by the scripted suite (INTERFACE trace T12).
- **The interface separates candidate from event.** Preparation fixes
  inspectable selected bytes; the later seal records who actually sealed them. A
  successful call says only what that operation established. INTERFACE now
  carries this, with literal traces for lost replies, manager-close races and
  uncertain effects.

If the user brings me back for consultation, I can help explain the intent behind
the manager simplification, distinguish what the paper review actually observed,
or check whether an interface choice quietly adds a new obligation. Those are
uses for my conversation context; the maintained design remains the authority.
