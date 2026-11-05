# Stewart auditor-interface study

Use inexpensive Haiku runs to investigate how Stewart presents and supports an
inquiry. The principal's goal is unobtrusive auditor-facing machinery, with a
useful balance between discoverability and verbosity. An equally sufficient
answer with more natural prose or less mechanical effort can be a substantial
success. Minimizing tokens, tool calls or answer length is not the objective.

This plan owns local preparation and remaining work. The
[design advice](riker/INTERACTION-STUDY-ADVICE.md) and
[scope clarification](riker/INTERACTION-STUDY-CONTEXT.md) inform it.
Product obligations remain in [DESIGN](DESIGN.md), [CONTRACTS](CONTRACTS.md),
[INTERFACE](docs/INTERFACE.md) and [QUESTION-FORMS](docs/QUESTION-FORMS.md).
Planning and inspection evidence is retained in `.scratch/interaction-plan-01`,
`.scratch/interaction-plan-02` and `.scratch/interaction-plan-03`.

## Scope and division of work

Keep the manager side deliberately uninteresting. Fix the questions, families,
evidence and other commission settings locally for each comparison. The local
agent may operate as manager within the principal's authorization, but improving
manager workflows or designing a manager interface is outside this study.

The principal supplied the frsrr problems and delegated decisions about what to
freeze and present to the auditor. The local agent owns source selection,
packaging and presentation variants without routine reconfirmation. The principal
retains the study's purpose, spending and protected obligations. Problem A is the
interface baseline; Problem B examines how the same interface accommodates
intellectual limits. The initial choices are fixed below.

The local focus is the auditor's initial context, family instructions, tool
descriptions, evidence presentation, citation handling, recording and revision
tools, and preparation/submission exchanges. Treat these as a coherent interface
whose current shape can be questioned. Start with the existing interface on A,
then B. The first interface intervention remains open until those encounters
have been reviewed; document authoring is not a prerequisite for starting.

Reading the returned answer is part of assessing the effect on auditor behavior.
A separate manager-facing receiving redesign is not current work. Existing
returns remain useful for inspection and explicitly labeled study views; the
receiving-end reading below uses such views. A document-oriented answer is a
candidate, not a selected destination.

## Frozen questions and evidence

The source is frsrr 1.1.0 at commit
`212a3ead6479e126dcc58b09a34da53ef729dbe0`, inspected from
`/Users/raccoon/Desktop/Math/frsrr`. The supplied problem document is
`/Users/raccoon/Desktop/Scratch/frsrr-problems/frsrr-haiku-problems.md`.
Its original bytes, the source snapshot and local inspection results are retained
in `.scratch/frsrr-inspection-01`. These are local development observations,
not Stewart qualification or evidence of Haiku behavior through Stewart.

The frozen auditor inputs are in `.scratch/frsrr-interface-inputs-01`.
`freeze.json` owns per-file SHA-256 identities, exclusions and provenance;
its SHA-256 is
`8081a561df5145db7fd855722ac08455eeac261ff9acaa6a8f5c101ed3908cb9`.
Use these retained bytes, not the live frsrr checkout. This is an input freeze,
not a launch-ready commission: model settings, limits and executable bindings
still belong in the bounded run packet.

| Input | Frozen choice |
| --- | --- |
| Question A | `question-a.txt`: the exact 528 bytes inside Problem A's Prompt fence, including the final LF. Keep its detailed subquestions unchanged for the initial comparison. |
| Question B | `question-b.txt`: the exact 1,194 bytes inside Problem B's Prompt fence, including the final LF. Keep its request to distinguish computation, estimation and confidence. |
| Family | `open-inquiry/1` for both baselines. Both already pose an inquiry; neither needs an additional framing or comparison assignment. |
| Shared evidence | `materials/`: 33 unchanged package files, 132,012 bytes, with repository-relative paths preserved. All tracked source, tests, package metadata and text documentation are included. |
| Selection notice | Manager-authored `materials/SOURCE.txt` identifies the revision and omissions without giving an answer map. With it, the material set is 34 files and 132,741 bytes. |
| Initial presentation | The question body is the initial user message. Keep the existing orientation and family/tools; discover material through `list`, `read` and `search`, without inserting the corpus or a bespoke research guide into initial context. |

Exclude exactly four tracked source files: `.Rbuildignore`, `.gitignore`,
`AGENTS.md` and `man/figures/readme-refinement.png`. The first three are build,
checkout or contributor guidance; the PNG is outside the current text reader.
Keep the README and figure-generating R script unchanged, and disclose the
omitted figure in `SOURCE.txt`. An unresolved document link does not supply
content. No source text needs conversion, line numbering or normalization.
Every selected source file fits within one current material read.

The original problem document's reference answers, evidence map, suggested
variations and prior-trial accounts stay reviewer-only. So do our build/test
logs, extra thread comparison and four numerical point checks. Test source
shows what a test checks; it is not evidence that the auditor ran it. No
execution report is supplied in the baselines. R remains a preparation tool
on the host; the auditor reads captured text and records its answer through
Stewart's existing tools, without an execution capability.

Changes to the question, evidence membership, source bytes or added guidance
create a named new input variant with its own manifest. Preserve the baseline
bytes and make the changed condition explicit. During an authoring-interface
comparison, keep each problem's question and material bytes identical. A's
subquestions can themselves organize prose, so do not attribute every heading
or repeated statement to Stewart. Shortening the prompt is a separate possible
intervention, not an unrecorded cleanup.

## Reviewer sufficiency and limits

For A, look for a supported explanation of thread-independent block selection,
per-task storage, fixed combination order and the smallest-magic exact-tie rule,
with accurate test coverage. The scope is the same build, floating-point
environment, sampled inputs and candidates; equal function arguments alone do
not reset sampling. The suite explicitly compares thread counts in the helper
and `frsr()`, not at the `frsr_bin()` level. Its recorded `threads` setting can
differ while the requested columns agree. Judge the substance without requiring
the reference answer's organization or separate entries for these points.

For B, judge what the answer establishes, how it bounds uncertainty and whether
it distinguishes supplied claims, deductions, samples and exhaustive coverage.
A well-supported partial answer or inability is a successful intellectual
outcome; a bare refusal is not automatically useful. Do not require guessed
numbers, confidence percentages or a particular conclusion to satisfy the form.
If the auditor offers an exact result, assess its support rather than rewarding
agreement with the reference table alone.

The local checks reproduce the table's four errors only at the stated input
points. They establish neither maxima nor global optimality. The supplied
account of exhaustive input scans and a candidate window is not a checked
coverage argument over the full magic domain. Retain that distinction when
reviewing B; proving the reference optimum or adding execution tools is outside
this interface study's preparation. Prior Haiku successes are useful motivation,
not a demonstrated Stewart baseline or a requirement to force a similar result.

## Design question and boundaries

How much scaffolding should the auditor encounter, in what form, and when?
Separate what must be readily discoverable from what must be explained in full
on every request. Test relocation as well as shortening:

| Exposure | Candidate contents | Failure to watch for |
| --- | --- | --- |
| Initial context and tool definitions | The assignment, material/access boundary, ways to read and save work, legitimate inability, and how to finish deliberately. Brief routes to further detail. | A capability or necessary distinction becomes undiscoverable. |
| At the relevant action | Exact citation references with reads/searches; usable revision handles with writes; actionable validation failures; candidate identity and next actions at preparation. | The reply omits information needed to act or repeats a large operating manual. |
| On inspection | Detailed history, expanded citation metadata, full saved state and less common operating details. | Extra lookup effort or repeated errors outweigh the quieter normal path. |

These are hypotheses, not prescribed partitions. Tool schema requirements and
discoverability may limit what can be moved. An on-demand capability still needs
a clear way to find it; moving a description to a help tool does not make it free.

Preserve custody, attribution, captured evidence integrity, revision history and
explicit submission. Internal handles may be presented more economically without
silently overwriting work or committing different content. Do not confuse an
auditor's submission with a manager's closure of unfinished work. Missing sections,
partial answers, inability and an empty return remain expressible.

Question families convey an assignment, not necessarily a report anatomy. The
authorial artifact, annotations and custody history need not share one shape.
Keep one authoritative recorded answer with identifiable revisions; a presentation
or independently generated summary cannot quietly replace it. Annotations must
distinguish authored claims, mechanical facts and presentation metadata.

Interface choices can influence reasoning. Record when an intervention adds an
interpretation, suggested investigative sequence or substantive guidance, so its
effect is not attributed solely to easier operation. Preserve the inquiry's
purpose without steering the auditor toward reference conclusions or prescribing
its intellectual procedure.

## Current evidence and candidate friction

The six-audit pilot remains in `.scratch/c10-haiku-commission-01` and
`.scratch/c10-live-01` through `.scratch/c10-live-06`. Its observations include
repeated conclusions across categories, seven citation refusals and one cursor
refusal, and no reads of the prepared rendering. These observations suggest
questions; they do not establish which interface choices caused the behavior.

Read-only inspection of three retained arrangements is recorded in
`.scratch/interaction-plan-01/auditor-surface-01.json`. They expose 12 or 14
tools. Compact-JSON tool definitions occupy 8,087–10,015 UTF-8 bytes, compared
with 2,318–2,513 bytes for the system blocks. Citation schemas occur in four or
six tools. These are byte measurements, not token attribution or attention scores.

| Surface | Opportunity to examine | Necessary comparison |
| --- | --- | --- |
| Recording vocabulary and repeated schemas | Fewer overlapping authoring concepts; different tool organization or optional annotations. | Natural composition and preserved partial work versus reduced discoverability or blurred distinctions. |
| Citation operands | Reuse exact references returned by reads/searches with less copying. | Fewer invalid calls without weakening exact-location and explicit-quotation checks. |
| Successful write replies | Show actionable saved state and references; make repeated record metadata inspectable. | Less history clutter without hiding actual effects or making revisions harder. |
| Initial guidance and tool descriptions | Short capability guidance with contextual detail; avoid repeating the same operating advice in several places. | Sufficient discoverability versus clarification calls, refusals and confusion. |
| Expected-section notices | Different wording, timing or exposure of advisory structure. | Less category-driven repetition while retaining useful orientation and the ability to submit incomplete work. |
| Revision and preparation/submission | Clear saved versions, optional preview and deliberate commitment with economical exchanges. | Correct revision submitted, recoverable history and explicit intent under normal and stale-state cases. |
| Evidence discovery | Source organization, indexing, read/search context and presentation of captured material. | Lower discovery effort, with any additional interpretive guidance identified. |

Changes to reply shape, tools or submission gestures may require specification
and implementation changes. Their current forms are not immutable study
requirements, but a candidate must state how it preserves the underlying
obligations. The matrix is a menu, not a mandatory sequence of experiments.

## Local preparation

The implemented [study packet path](apparatus/c10/README.md#study-submissions)
keeps the six conformance cases intact and adds explicit folder/hash bindings.
The two offline templates are in `.scratch/frsrr-study-submissions-01`, with
`assembly.json` recording verification against the frozen manifest, exact question
bodies and all 34 material files. Their front matter carries the inquiry label;
`varies` is omitted because these baselines have no earlier audit reference.
Model/effort, allowances and destination in these templates are offline settings,
not a proposed live commission. The packet supplies the eventual run settings.

The native run `.scratch/c10-study-native-03` passed all 15 planned audits,
including both study templates, and all seven operator comparisons. The reviewer
checks passed in `.scratch/c10-study-review-fixed-01` (14/14),
`.scratch/c10-study-review-study-a-01` and `.scratch/c10-study-review-study-b-01`
(18/18 each, including all template controls). The logs and matching source hash
are in `.scratch/provider-study-checks-01`. This is native iteration, with Linux
process-access checks skipped. Preserve the earlier permission failures in
`.scratch/c10-study-native-01` and `.scratch/c10-study-native-02` as well.

- [ ] Run and retain the committed apparatus's
  Linux rehearsal with both study templates before binding a paid packet.
  Study template tampering, actual capture/review and later collection must
  pass; successful intake alone establishes neither an answer nor qualification.
- [ ] Identify concrete places to vary the auditor-facing arrangement and
  replies. Packaging can vary through submissions; instructions, tool definitions
  and rendering are pinned and may need a new build. Record the actual exposed
  variant rather than mutating an accepted arrangement in place.
- [ ] Inspect initial context, repeated replies and relevant-action detail
  separately. Capture the complete baseline exposure, including tool schemas
  and returned content, so a quieter variant can be compared with what the
  auditor actually received. Use small offline examples for proposed changes.
- [ ] Exercise changed operations with appropriate small cases and controls.
  Include stale revisions, invalid citations, incomplete/empty returns and
  intervening edits where relevant. A simulator may answer an isolated question
  but is not evidence of production custody or a substitute for using Stewart.

Before implementation edits, identify the applicable
[DEVELOPMENT checks](DEVELOPMENT.md#what-to-run-for-what-you-changed) and follow
the independent-driver authoring rule. Reusing a launcher does not transfer its
qualification to changed paths or larger workloads. The changed apparatus needs
its retained Linux rehearsal, run by the principal, before the first live
baseline.

## Study mode for interventions

An interface intervention is a new binary: the orientation, family instructions,
tool descriptions and schemas are pinned in it and compared with QUESTION-FORMS
by the service tests and the independent driver's self-test, and the live
launcher accepts only a binary on the qualification front. The principal has
decided on a study mode in the C10 launcher for identified unqualified study
builds. Qualifying each variant would put experimental commits on the product's
front; making the arrangement a commission input is a product change left to
the rapid-iteration work.

Each variant is a branch commit. The agent edits QUESTION-FORMS and the service
and runs both Cargo configurations natively. The principal runs `acceptance.sh`
on that commit: it builds and digests the Linux binaries and runs every case,
and its self-test and text-comparison cases fail as expected. That run is pinned
as an experiment and never extracted into the front. The principal then runs
`c10.py rehearse` with the study binary, and the packet binds the study digest,
the variant commit, the qualified base commit and the acceptance folder, all
labelled unqualified in every record.

Guards: the launcher applies its existing credential-case check to the
variant's acceptance result, so no real key reaches a build whose credential
handling failed. The packet names the expected failed cases and the launcher
refuses any other failure. The driver copies stay untouched on study branches
and the recorded self-test failure is not hidden. Variant commits stay
reachable under a ref while their evidence is cited. Adopting a variant goes
through the full cycle on `main` with an independent driver author.

- [ ] Implement the study mode and its guards after the baselines. The first
  intervention binary forces a new rehearsal in any case, so landing it later
  costs no extra rehearsal.

## Lightweight iteration

For each intervention, retain a short note: what prompted it, what changed,
what observable difference was expected, and what happened. Link the note to
the relevant submission/build and saved traces. Plain text is sufficient.
The `inquiry` label and `varies` reference in the rendered front matter
associate audits; the latter is a manager's attributed note, not a verified
comparison. No scoring service or elaborate report is needed.

Keep answer sufficiency and interface friction as separate observations. An
adequate answer can conceal substantial mechanical effort; an insufficient
answer can still show a useful interface improvement. Resource exhaustion,
provider problems and apparatus failures need their own account. Returned
source text does not prove understanding, and one unsuccessful answer does not
identify reasoning or the interface as its cause.

Inspect discoverability, navigation, copying and repair, revision effort,
category-driven prose, recovery and commitment. Record calls, turns, reported
or estimated usage and timing when useful. Do not optimize a count in isolation.
For both inquiries, inability or a partial result must be an available
intellectual outcome, not a reason to demand filler or automatic continuation.

- [ ] Prepare a proposed first commission of two placements: one current-interface
  A baseline, then one B baseline on the same interface, reviewing A before B.
  Fix exact model/effort, allowances, request-attempt policy, watchdog, stop
  conditions and source/binary/apparatus bindings. Verify compatibility and costs
  and obtain bounded spending authorization before launch. The delegated input
  choices and prior pilot grant no new model calls. A and B are separate
  launches with their own packets, approvals and evidence folders. A launches
  and is later collected through the saved provider connection and is that
  route's live check; a connection failure is a launch failure, not a study
  observation.
- [ ] Size allowances for the actual workload. A turn is one provider response
  and each request resends the whole context, so the pilot's allowances do not
  transfer: reading most of the 132 KB corpus over a few dozen turns consumes
  far more cumulative input than the pilot packet allowed, and a limit stop
  confounds the baseline. Do not infer model inability from a limit stop or
  silently rely on unqualified compaction and continuation paths.
- [ ] Select changes from observed friction or plausible simplification.
  Hold commission settings fixed except where an explicit evidence-presentation
  variant is the intervention. Changes to completeness or consistency are
  distinct conditions, not invisible differences in an interface comparison.
  After baseline review, choose one intervention and the smallest useful
  comparison; there is no precommitted variant matrix or numerical-search
  campaign. Preserve model/effort and per-problem allowances across interface
  comparisons unless their change is itself an identified condition.
- [ ] Review the resulting answer and interaction together, with the
  receiving-end reading of its return. Preserve failures and original records;
  no silent repairs, replacement trials or automatic extensions.
  A coherent interface package can vary together, provided its components are
  identified and any causal claim stays within what the comparison supports.
- [ ] Keep, revise, abandon or further distinguish a candidate according to the
  principal's judgment and the evidence. Propose extra comparisons only when
  they would resolve a material uncertainty.

## Receiving-end reading

The advice's first experiment is adopted in a folded form, without model calls.
For a return, the agent writes a study view: a derived, labelled document that
puts the answer or the inability first and keeps provenance and the detailed
record reachable. It is kept beside the run under `.scratch`, is never a member
of the return and changes no rendering. The principal reads the current
rendering and the study view and records what each let them recover. The
principal is the instrument; the agent, who wrote the view, is not a reader.

The view keeps auditor text and Stewart presentation distinguishable, does not
merge entries or paraphrase in a way that changes a claim, calls nothing
verified where Stewart checked only a quotation, and states the seal's actor as
recorded.

Rubric, one sitting of about ten minutes per return, with the second form
hidden until the first is done:

1. What did the auditor find?
2. What remains unknown or unsupported?
3. Who authored the return, and did the auditor or the manager seal it?
4. What did Stewart verify, and what did the auditor merely claim?

Answer the four for the first form, then read the second and note what
changed, what was wrong and what the second form made easier or harder to see.
Record effort as it happened: how many sections were read to find the answer,
and where an observation and an inference could not be told apart. A view that
reads smoothly but leaves the reader more certain than the record justifies is
a failure. The reader does not grade whether the auditor was right; that
judgment stays under the reviewer sufficiency section. Alternate which form is
read first across returns. The reader's notes are the record: the agent files
them verbatim with the order read and the run they belong to, beside the run,
cited from here.

- [ ] Warm-up now: write the study view of the pilot's first return,
  `.scratch/c10-live-01/review/answer.md`, whose observations restate its
  account, and hold the reading. Its result informs the choice of the first
  intervention: authoring categories or rendering order.
- [ ] For each baseline, write the study view of the return during review and
  hold the reading before the next launch. Three sittings in all.

## Adoption and completion

A useful reduction in mechanical effort counts even without an improved
intellectual answer. Consider discoverability and the risk of confusion as well
as verbosity. One model on a few inquiries does not establish a universal
interface preference; broader claims need corresponding evidence.

Bring changes to authority, expressive freedom or protected obligations to the
principal explicitly. Before adopting a design, align the affected contracts,
interface, forms, help and examples, and verify actual behavior under the required
normal and adverse checks. Keep custody verification distinct from judging
claims or evidence support.

Update this plan with selected work and unresolved decisions. At completion,
give remaining candidates a disposition, move enduring behavior and guidance to
their owners, and delete the plan. Preserve original evidence under
[DEVELOPMENT](DEVELOPMENT.md#evidence-and-retention).
