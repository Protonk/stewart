# Stewart interaction study

Use inexpensive Haiku runs to investigate how Stewart presents an inquiry and
lets an auditor work. The principal's goal is to make Stewart's machinery
unobtrusive. The study concerns commissioning, evidence access, authoring,
submission and reading the return. It does not optimize Haiku's intellectual
performance or introduce a substantive answer-quality gate.

This document owns the study's decisions and remaining work. Writing this plan
and requesting advice are authorized. Prototype implementation and paid trials
remain proposed work; a trial count here is not spending authority. The product
commitments remain in [DESIGN](DESIGN.md), [CONTRACTS](CONTRACTS.md),
[INTERFACE](docs/INTERFACE.md) and [QUESTION-FORMS](docs/QUESTION-FORMS.md).
Planning-check evidence is retained in `.scratch/interaction-plan-01`.

## What unobtrusive means

| Experience | Desired behavior | Who supplies the observation |
| --- | --- | --- |
| Commissioning | The manager can express a request, select its purpose and supply material without learning internal record categories. Scope and spending choices remain intelligible. | The principal working through concrete submission examples. A model simulation cannot establish human usability. |
| Working | The auditor can read, record, revise and finish without unnecessary copying, categorization, navigation or repair. | Raw model/tool traces, recorded effects and scripted comparisons. |
| Receiving | The manager can find and read the answer, its basis and its limits naturally, with attribution and provenance accessible. | The principal comparing concrete returns and locating information in them. |

Normal operation should require little attention to machinery. Failures,
uncertain effects and changes in authority must remain visible. Short prose,
few tools and few calls are possible benefits, not definitions of success.
Removing a useful distinction or making recorded work easier to lose is a cost
even if the resulting interaction looks simpler.

Haiku is an inexpensive participant in the experiment. Its behavior can expose
friction in an interface; it does not establish a universal model preference or
decide the manager's experience. The principal judges whether a design fits
Stewart. Do not optimize a general reasoning score, a planted conclusion or the
presence of every answer section.

## Starting evidence and design question

The six-audit pilot's retained records are in `.scratch/c10-haiku-commission-01`
and `.scratch/c10-live-01` through `.scratch/c10-live-06`. The combined
`review/result.json` owns procedural results. The later
`review/answer-assessment-01.json` in the commission folder records assistant
observations for discussion, rather than the principal's endorsement.

All six audits submitted, delivered and closed. Relevant observations are
repeated conclusions across recorded categories, the account appearing fifth
in both framing returns and fourth in the ordinary comparison, seven citation
refusals and one cursor refusal, and no reads of the prepared rendering. These
suggest interaction questions; the pilot did not compare interface variants
and establishes no cause for those behaviors. Its substantive framing concern
is retained without making repair of that answer the study's objective.

The current arrangement couples family instructions, specialized recording
tools, expected-section notices and rendered headings. Family names themselves
are manager-facing; the auditor receives instructions and tools. The initial
question is whether the authoring interface makes an auditor organize a simple
return around Stewart's categories more than the task requires.

## First comparison: how an answer is written

Compare two coherent authoring interfaces over the same small tasks:

| Alternative | Model-facing behavior |
| --- | --- |
| A: current typed entries | The current family-specific recording tools, entry revision behavior and factual missing-section notices. Preserve the exact baseline prompt/tool definitions in the study packet. |
| B: editable answer document | A single saved answer document, with an explicit revision action and citations. The auditor can organize its own prose without allocating it among Account, Observation and Limit tools. Optional annotations must not become compulsory sections. Exact schemas remain to be designed. |

Hold the manager's request, family purpose, source bytes, material-access tools,
citation validity rules, model/settings, cumulative allowances and finishing
semantics fixed. Alter tool instructions only as needed to describe B honestly;
record those differences. Do not also add better reasoning advice, preload
evidence or simplify citation operands in this comparison.

This is a comparison of authoring packages, not a claim to isolate a single word
or tool name. Expected-section notices are part of A's package. If a difference
matters, a later comparison can separate vocabulary, schema and notice effects.
Do not invisibly translate B's prose back into the typed categories being tested.

- [ ] Specify both interfaces, their returned state and an illustrative call
  sequence before building them. For B, decide citation attachment granularity,
  exact revision targets and how empty saved work differs from no saved work.
  These choices must remain observable in the trace.
- [ ] Preserve saved drafts and revision history in both alternatives. A document
  alternative must not obtain a shorter trace by retaining nothing until finish.
  State whether each operation changes recorded work; reject stale revisions
  without silently replacing a newer draft.
- [ ] Keep the same explicit preparation and submission meanings in this round:
  a prepared candidate identifies exact saved content; subsequent edits make it
  stale; deliberate submission seals that candidate. An empty answer and an
  inability response remain expressible. Do not force a comparison or a finding.
- [ ] Write the observation sheet before trials, including what would favor A,
  what would favor B and what would leave the comparison unresolved. B must be
  allowed to lose because structure helps navigation, revision or communication.

## Small tasks and repetitions

Use three fixtures with little intellectual difficulty. Freeze their exact
questions, materials and intended interaction before model calls. Do not reuse
an answer from a prior conversation as the model's starting state.

| Fixture | Interaction to expose | Interpretation limit |
| --- | --- | --- |
| One fact in a short supplied source | Read, save a direct response with its basis, and finish. | A short trace must still account for the source and intended final selection. |
| Comparison with one alternative missing | Express inability to compare and any chosen partial work without fabricating categories or a winner. | No particular substantive answer or entry count is required. |
| A deliberately requested draft and revision | Save work, consult a second supplied note, revise the saved response, then finish the current version. | This is a scripted interaction probe, not evidence of natural investigative behavior. Both notes are captured at the start; no new material is injected into the commission. |

- [ ] Prepare the fixtures and identify a simple observable action for each.
  Preserve task intent across alternatives. If a fixture creates reasoning
  ambiguity that obscures interface use, revise it before freezing the batch.
- [ ] Plan two alternatives x three fixtures x three fresh placements: **18
  proposed placements**. Balance A/B order across fixtures and repetitions;
  record the order before launch. This is exploratory repetition, not a
  statistically established usability rate. Offline controls and human reading
  exercises add no model placements.
- [ ] Set explicit per-placement and batch allowances, request-attempt policy,
  watchdog, stop conditions and an exact model/effort setting. Verify current
  provider compatibility and prices when preparing the paid packet. No automatic
  retries at the batch level, replacements or extensions follow from this plan.
  The completed pilot's authorization and cost calculation do not authorize or
  price these new trials.

## Prototype only what the comparison needs

Use a small study runner with versioned prompts, tool definitions and recorded
state. A simulator is suitable for early interaction prototypes; do not build
a general workflow framework or a second custody engine. Reuse the existing
[launch boundary](apparatus/c10/README.md) where its assumptions fit, after
checking that reuse rather than assuming its qualification transfers.

- [ ] Choose the smallest execution route and document what is simulated.
  Exercise the baseline against the specification so an inaccurate baseline
  cannot make the alternative appear better. A simulator's submission is a
  study event, not a Stewart seal, verified delivery or closed audit.
- [ ] Rehearse both alternatives without a paid model. Include a successful
  save/revise/finish path, empty submission, a stale target, an invalid citation
  and a finish attempted after an intervening edit. Pair the selected boundary
  checks with firing controls and an unchanged valid comparison. Record actual
  outcomes; do not claim production fault coverage from the simulator.
- [ ] Capture requests, raw responses, calls, replies and state effects. Record
  any translation performed by the runner. Never silently repair a handle,
  normalize a citation or supply a missing model step to make a trace succeed.
- [ ] Freeze versioned prompts, schemas, fixture bytes, runner identity and the
  run manifest. Give every placement a fresh evidence location. Follow
  [evidence retention](DEVELOPMENT.md#evidence-and-retention); preserve failed
  attempts and originals as well as successful traces. Keep study artifacts
  distinct from the pilot's sealed returns.

## Observe friction and decide

Record counts alongside the exact interaction that explains them. Avoid one
aggregate score that rewards a short but confusing or incomplete interaction.

| Observation | How to interpret it |
| --- | --- |
| Tool calls, first-call validity, refusals and repair attempts | Separate model operand errors, unfamiliar affordances and runner failures. A refused call can show a necessary boundary working. |
| Material reads, repeated navigation and citation copying | Identify what each step accomplished before calling it overhead. Evidence inspection is useful work. |
| First saved work, revisions and surviving draft state | Show whether simplicity came at the expense of preserving work or making changes understandable. |
| Successful preparation to submission, and stale/empty cases | Measure observable steps. Readiness inside the model is not observable; mark any inferred readiness as such. |
| Repetition and references to Stewart's machinery in authored prose | Inspect actual passages and their function. A necessary qualification or useful explanation is not automatically noise. |
| Return order, answer location and source lookup | Ask the principal to locate the response, its basis and its limits. Record concrete difficulty and preference separately from model behavior. |
| Turns, reported/estimated tokens, elapsed time and cost | Record operating consequences, not an intellectual-quality score. Distinguish calculated cost from attributed billing. |

- [ ] Review all authorized outcomes, including limits, unsubmitted endings and
  failures. An unreached operation is unexercised coverage. Retain awkward runs
  instead of replacing them until a preferred design looks successful.
- [ ] Give each observation a source and distinguish observed behavior, a causal
  hypothesis and a principal preference. Name plausible competing explanations;
  use a subsequent controlled comparison when choosing between them matters.
- [ ] Decide whether to keep, revise, abandon or further distinguish the
  alternatives. A result of no useful difference is sufficient. Do not tune a
  fixture-specific prompt until Haiku produces a pleasing answer.

## Human presentation exercise

- [ ] Make separately labeled study views of selected existing returns, using
  the same attributed prose and source references. Compare the current rendering
  with a document view that reduces record labels and makes citations easier to
  consult. Preserve all substantive text; a shorter edited answer is a different
  comparison. Keep original sealed files unchanged.
- [ ] Show paired views without preference-signaling names and alternate their
  order. Ask the principal to find the response and its basis, and identify any
  information that became harder to notice. Record preferences without treating
  this single person's judgment as population evidence.
- [ ] Separate authored repetition from renderer clutter. Record whether future
  model trials read their prepared rendering; the pilot's models did not, so
  its traces cannot establish an effect of inspecting that preview.

## Candidate later comparisons

Select a next comparison from an observed friction point; this is a menu, not a
commitment to run every combination.

| Surface | Candidate difference | Meaning to preserve or make explicit |
| --- | --- | --- |
| Question types | Plain-language manager choices; concise task brief versus current family instructions. | Manager-selected purpose, original question and legitimate inability. Do not silently select a different family. |
| Evidence | File listing versus a manager-supplied source index; small captured material shown initially versus read on demand. | Source identity, full available scope and attribution. A source description is not a certification of its claims. |
| Citations | Current locator operands versus reusable references returned by reading/searching. | Exact resolution to captured bytes. No fuzzy correction or support verdict. |
| Finishing | Different names, previews and ready-to-use next calls; later, a single finish operation if explicitly selected. | Explain what exact draft is sealed, whether inspection is optional, how revision races resolve and who acts. Combining steps can change the product contract and needs that decision stated. |
| Failure replies | Short action-oriented replies with detail available versus the current envelopes. | Actual effects, uncertainty and the valid recovery route remain inspectable. |

## Design advice and adoption

- [ ] Relay [the self-contained Riker request](riker/INTERACTION-STUDY-REQUEST.md)
  under [the consultation procedure](riker/RIKER.md). Seek advice about Stewart's
  conceptual design: necessary distinctions, avoidable machinery and experiments
  that would inform those choices. Riker need not read this plan or design the
  runner. Incorporate useful advice explicitly; it is not the principal's assent.
- [ ] Resolve substantive changes to participant authority, expressive freedom,
  preservation or submission meaning with the principal. Versioned interaction
  prototypes are proposals, not amendments to existing records or promises.
- [ ] Before adopting a candidate, implement it in Stewart with aligned
  contracts, interface, forms, help and examples as applicable. Verify the actual
  behavior under [DEVELOPMENT](DEVELOPMENT.md#what-to-run-for-what-you-changed),
  including the independent-driver authoring rule. Simulator success establishes
  no production qualification; results on Haiku do not automatically establish
  suitability for another runtime or a human auditor.

The first decision package consists of two specified authoring prototypes,
three frozen fixtures, the observation sheet, a bounded run proposal and paired
human-readable views. After authorized trials, it includes every outcome and
an explicit design disposition. This plan is complete when the selected rounds
have those dispositions, adopted behavior is documented and verified, and
unselected ideas are explicitly deferred or abandoned. Move enduring guidance
to its owners and delete the plan; retain evidence under the ordinary rules.
