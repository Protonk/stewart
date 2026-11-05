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

The first interface intervention run through the launcher's study mode is
"what we have". Its measured cycle is the comparison for everything below, so
the design steps wait for it.

- [ ] Record that intervention's actual cycle: which files were edited and by
  whom, which runs the principal made, elapsed time, evidence size, the number
  of agents and authorship splits involved, and what the study mode could not
  vary. Record the two baselines' cycle the same way.
- [ ] Record the friction observed in those runs that bears on structure: where
  the question, materials, family text or arrangement fought one another, and
  where a change was wanted but not cheap.

## Clean sheet

- [ ] Commission a fresh agent to design from the obligations alone: the mission
  and principles, the custody and attribution contract, the question families'
  purposes and the acceptance claims. It does not start from INTERFACE 7 or the
  current launcher. It receives the measured reference, the friction record and
  the candidate elements above.
- [ ] Require it to place each element on the manager side, the app side or the
  study-variable side with a reason; to give the simplest architecture that
  meets the obligations and lets the study-variable side change without a
  rebuild; and to name what each candidate gives up, including custody during
  the work, citation checks at the moment of action, re-entry after a kill and
  continuation of one ledger.
- [ ] Compare the design with the reference on the measured cycle and on the
  obligations, not on preference. Retain both documents.

## The question

This is the gate before any build.

- [ ] Write a prompt that cannot simply agree with us. It gives the obligations,
  the current transport, the measured reference and the goal, and asks for the
  simplest architecture; it states no hypothesis. Only after the agent has
  answered, put two hypotheses to it explicitly: a connector that consumes
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
  define the change, run it, collect it, and record the cycle beside the
  reference for comparison.

## Authority and limits

Bounded authorization per model-consuming use stays, as [AGENTS](AGENTS.md#decisions-and-authority)
requires. The rapid path cuts ceremony, not authority; a standing allowance
would be a new grant and is not assumed. The decision about who runs paid work
and how that is enforced is an input to the build step.

Out of scope: tuning the auditor's answers, and designing the manager interface
beyond the boundary placements this plan needs.

## Completion

Complete this plan when the decision is recorded, the chosen shape is built and
checked, and one structural change has run through it with its cycle recorded
beside the reference. Move enduring behavior and reasons to the owning
documentation and tests, give open placements and unbuilt candidates an explicit
disposition, preserve evidence under
[DEVELOPMENT](DEVELOPMENT.md#evidence-and-retention), then delete this plan.
