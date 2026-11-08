# Rapid question iteration

Let the principal change what an auditor encounters, from the question's
structure and materials to the family and the arrangement, and spend bounded
credits observing the effect without the full product cycle, while keeping
custody, attribution and explicit submission intact. This plan owns the design
of that path, the decision about which shape it takes and the build of the
chosen shape. Product obligations remain in [DESIGN](DESIGN.md),
[CONTRACTS](CONTRACTS.md), [INTERFACE](docs/INTERFACE.md) and
[ACCEPTANCE](ACCEPTANCE.md). Agent outputs and comparisons are retained under
`.scratch/rapid-iteration-NN` and cited here as they are made.

Design for self-contained experiment blocks: the principal agrees a budget and
basic design, and the agent commissions small experiments with useful, largely
unambiguous outcomes within the agreed bounds. Collection, evidence review and
custody disposition belong inside the cycle. The result should identify a
supported finding or an unresolved comparison without routinely requiring the
principal to read long answers or reconstruct several reports. Questions that
need an independent reader or a designer's interpretation remain explicit; this
path does not automate judgments of answer quality. The autonomy agreement
below governs the delegation; each bounded commission fixes its actual scope.

## Premise

The commission surface is one space: the question body, its front matter, the
family, the materials and their packaging, expected sections and notices, and
the auditor's arrangement of orientation, family instructions and tools. Today
the first five are free inputs and the arrangement is pinned in the binary. That
split is not a decision. The manager interface was designed only far enough to
proceed, and the interaction study keeps it deliberately uninteresting. When the
manager side is closed down, parts of the question structure may move into the
app and managers will adapt to that.

Treat the boundary as a design variable with three forces on it: what a manager
must be able to express, what the app must standardize or enforce for custody
and comparability, and what must stay cheap to vary for study. Custody is
already preserved on both sides, since free inputs are captured and hashed and
the arrangement is pinned and recorded. Moving an element into the app buys
consistency and guidance quality at the cost of manager freedom and iteration
speed. Every element that moves into the app becomes pinned text, which is the
part that is slow to vary, so the value of a rapid path grows with each such
move. That is this plan's reason to exist.

Candidate elements that may move into the app, to be placed rather than assumed:
front-matter settings beyond model and limits; family choice and the wording of
its instructions; material packaging, indexing and selection notices; expected
sections and their notices; framing conventions for the question body; evidence
recipes for each family.

## Reference point

The completed `account-composition-01` A/B intervention is "what we have".
Its actual cycle, including failed preparation attempts, is the reference for
the design comparison. The runs and readings are complete; assembling the
measured reference and friction record below remains the first task here.
Do that from retained evidence, without rerunning the completed commissions.

| Reference material | Retained location |
| --- | --- |
| Frozen questions/materials, submission assembly, baseline packets and authority | `.scratch/frsrr-interface-inputs-01`, `.scratch/frsrr-study-submissions-01`, `.scratch/frsrr-study-commission-01` |
| Baseline A/B launches, collections, reviews and principal readings | `.scratch/frsrr-baseline-a-01`, `.scratch/frsrr-baseline-b-01` |
| Intervention wording, patch, proposal, preparation attempts, commands and study-build descriptor | `.scratch/haiku-authoring-01` |
| Both Linux acceptance attempts and their dispositions | `.scratch/haiku-authoring-acceptance-01`, `.scratch/haiku-authoring-acceptance-02` |
| Timing comparisons and the independently authored protocol-budget change | `.scratch/haiku-authoring-timing-01`, `.scratch/haiku-authoring-timing-02`, `.scratch/protocol-budget-120-01` |
| Matching launcher rehearsal | `.scratch/haiku-authoring-rehearsal-01` |
| Intervention launch, collection and reading assessment | `.scratch/haiku-authoring-live-01`, particularly `review/result.json` and `review/pair-reading-01.json` |

Use the [implemented reporting exchange](apparatus/c10/README.md#assemble-an-experiment-report)
when judging what a block carries back to the principal. Its worked reading of
the limit and pagination trials is
`.scratch/apparatus-report-implementation-01/retained-reading-final/report.md`.
The checked technical position and attributed assessment remain distinct; this
example does not replace the measured intervention cycle below.

The apparatus addition is commit `fa21e8c`; ordinary timing maintenance is
`5d797e4`; the retained candidate is `c76029b` on
`study/account-composition-01`, with worktree `.scratch/haiku-authoring-worktree-01`.
It changes only open-inquiry guidance/version and corresponding native
assertions. The independent driver was not adapted to accept the study text.
The baseline binary was qualified; the candidate remains explicitly unqualified.
Preserve the failed checks and their dispositions when costing the cycle.

- [ ] Record that intervention's actual cycle: which files were edited and by
  whom, which runs the principal made, elapsed time, evidence size, the number
  of agents and authorship splits involved, and what the study mode could not
  vary. Record the two baselines' cycle the same way.
  Separate elapsed calendar time, recorded process durations and principal
  actions; report active effort as unknown where it was not observed. Separate
  reusable apparatus setup and incidental timing maintenance from the marginal
  work of changing the guidance, without dropping either from the record.
- [ ] Record the friction observed in those runs, and in the five stress
  one-offs retained in `.scratch/haiku-stress-live-01` to `-05`, that bears on
  structure: where the question, materials, family text or arrangement fought
  one another, and where a change was wanted but not cheap. The stress runs
  add the refused range read after a search hit, a whole revision refused for
  one inexact quote, the unwarned per-request output cap that counts thinking,
  and tool-reply facts such as line counts that no citation can carry; the last
  changes what participants can express and is the principal's decision.
- [ ] Identify where an independent reader or the principal supplied a judgment
  needed to resolve the comparison. Distinguish mechanically observable outcomes
  from those interpretations, and use that distinction when choosing small
  experiment blocks. Record both handoffs and the material carried between them.

## Clean sheet

- [ ] Commission a fresh agent to design from the obligations alone: the mission
  and principles, the custody and attribution contract, the question families'
  purposes and the acceptance claims. It does not start from INTERFACE 7 or the
  current launcher. It receives the measured reference, the friction record and
  the candidate elements above.
  This is the agent that receives the neutral prompt below; a second fresh agent
  receives the leading version. The design consultations have not been run.
- [ ] Require it to place each element on the manager side, the app side or the
  study-variable side with a reason; to give the simplest architecture that
  meets the obligations and lets the study-variable side change without a
  rebuild; and to name what each candidate gives up, including custody during
  the work, citation checks at the moment of action, re-entry after a kill and
  continuation of one ledger.
- [ ] Assess the whole experiment cycle: preparation, launch, observation,
  collection, review and custody disposition. Identify routine handoffs and
  interpretations that prevent a block from yielding its own useful result.
  Do not assume future delegation or paid-launch authority when evaluating a
  design.
- [ ] Compare the design with the reference on the measured cycle and on the
  obligations, not on preference. Retain both documents.

## The question

This is the gate before building the rapid-iteration path.

- [ ] Write a prompt that cannot simply agree with us. It gives the obligations,
  the measured reference and the goal, and asks for the simplest architecture;
  it states no hypothesis and does not describe the current transport. Only
  after the agent has answered, describe the current transport and put two
  hypotheses to it explicitly: a connector that consumes
  question and answer JSON, validates it and applies it after validation; and
  moving named elements of question structure into the app. It must say what
  each would give up and whether a hybrid preserves the custody events while
  changing the authoring transport.
- [ ] Run a second fresh agent with the leading form of the same question as a
  control on our framing. Retain both answers and record where they differ.
- [ ] Write the comparison for the principal: the shapes found, what each gives
  up, the boundary placements each implies, and the consequences for a Claude
  Code or human auditor runtime, which would use the same transport. The agents
  advise; the principal decides.

## Decision and build

- [ ] The principal chooses among the shapes the comparison produces: the
  arrangement as a commission-time input, a validated document connector, the
  current protocol with a study attachment, or a shape the clean sheet found.
  Record the decision and the boundary placements it settles here; placements
  it leaves open feed the later closing-down of the manager side.
- [ ] Build the chosen shape. A product-side choice changes what Stewart
  promises or what participants can express and goes through the normal cycle:
  a CONTRACTS decision, INTERFACE and forms, help and examples, split driver
  authorship under [AGENTS](AGENTS.md#preserve-independent-evidence) and the
  [DEVELOPMENT checks](DEVELOPMENT.md#what-to-run-for-what-you-changed). An
  apparatus-side choice follows the launcher's checks and rehearsal.
- [ ] Demonstrate the path on one structural change with bounded spending:
  agree the block, define the change, run it, collect and review it, and account
  for custody completion. Return its finding and any unresolved decision;
  record the cycle, actual principal interventions and exchanges beside the
  reference for comparison.

## Authority and limits

On 2026-11-07 the principal agreed broad agent autonomy within a bounded
failure-and-recovery campaign: selecting experiments and variants, repetitions
and follow-ups, paid launch, interpretation, collection and reviewed custody
completion. Budget increases, changes of model or purpose, permanent product
decisions, loss surrender and disposal remain with the principal. The
coordinating plan identifies the active commission and its owner.

This is the delegation pattern for the rapid path; it is not unlimited authority
for other paid work. [AGENTS](AGENTS.md#decisions-and-authority) still requires
an applicable bounded commission. Proposals do not grant permission by themselves.

- [ ] Bind the chosen rapid path's demonstration to an applicable commission,
  including its model, spending and placement bounds and permitted changes.
- [ ] Use an enabled execution route and provider-side spending limit, keeping
  ordinary placement/cost accounting. Add spending-control machinery only for
  a concrete reusable requirement. Keep calculated cost, provider usage and
  independent billing distinct; token/turn limits are not a dollar ceiling.

Out of scope: tuning the auditor's answers, and designing the manager interface
beyond the boundary placements this plan needs.

## Completion

Complete this plan when the decision is recorded, the chosen shape is built and
checked, the autonomy agreement and its enforcement are explicit, and one
structural change has completed a self-contained block with its cycle recorded
beside the reference. Account for every trial, evidence gap and remaining
custody obligation. Move enduring behavior and reasons to the owning
documentation and tests, give open placements and unbuilt candidates an explicit
disposition, preserve evidence under
[DEVELOPMENT](DEVELOPMENT.md#evidence-and-retention), then delete this plan.
