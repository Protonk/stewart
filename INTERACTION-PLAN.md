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

## Authoring direction and next experiment

The principal's November 6 direction separates question-specific structured
requirements from the auditor's main explanation. Some question types may demand
data that Stewart can mechanically check and refuse, or that a manager can use
in a stated relationship. The main response should otherwise be organized by
its author. The applicability, schemas, checks and treatment of unavailable
values remain future design work; the current experiment introduces no new
required fields or substantive acceptance test.

Post-authoring rearrangement may prove unnecessary. Preserve that possibility:
the next reading uses the submitted return with its question, without an
agent-reformulated companion. The principal prefers narrowly scoped linting to
reformulation if intervention proves useful. The existing linter marker remains
deferred; neither general rewriting nor a linter implementation is commissioned
by this study setup. Structured validation and explicit submission remain active.

The next candidate, `account-composition-01`, is prepared in
`.scratch/haiku-authoring-01`. `interface-02.json` owns the exact proposed wording;
`variant-02.patch` changes the open-inquiry family instructions, gives that family
a new version, and updates the two native assertions of its version. The
instructions invite a connected account containing its basis and limits, make
separate observation/limit entries optional, and explain that missing-section
notices do not require more writing. Tools, schemas, the notices themselves,
citation checks, revision, rendering and submission behavior stay fixed. This
tests whether changed guidance is enough; it does not establish that the tools
or their categories are the cause of repetition.

The principal agreed to one new placement each on A and B, using their
frozen submission templates and the baseline model, effort and allowances.
The agreement is retained in `.scratch/haiku-authoring-01/round-agreement-01.json`.
The proposal remains unbound until the study build and Linux rehearsal
are reviewed. Read each original return with the exact question, then record
what it establishes, what remains unresolved, any useful or redundant structure,
and citation navigation. Inspect the saved interaction separately for copying,
repair, category use and reaction to preparation notices. A supported inability
remains a useful B outcome. Preserve all attempts; no automatic replacement run
or continuation follows from an awkward answer.

The principal expects a few more bounded Haiku reading/data-collection rounds,
then a move beyond this model and problem set. Review this pair before choosing
the next discriminating encounter. Any later repeat needs a reason and separate
bounded spending authority; avoid an open-ended campaign to polish these answers.
Evidence from another model and different material is needed before treating a
preference found here as general.

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

The Linux aarch64 rehearsal `.scratch/c10-study-launch-01` at `751aa7c` is
reviewed and pinned in [the qualification record](apparatus/qualified.md).
`review/result.json` binds both templates to the frozen question bodies and
material bytes, verifies their captured inputs and answers, reproduces all
template tampering controls, and verifies later collection through the saved
synthetic connection. It establishes readiness of the apparatus for these
inputs, not an answer from Haiku or authority to spend. The native preparation
logs remain in `.scratch/provider-study-checks-01`.

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
qualification to changed paths or larger workloads. Further apparatus changes
need a matching retained Linux rehearsal, run by the principal, before live use.

## Study mode for interventions

An interface intervention is a new binary: the orientation, family instructions,
tool descriptions and schemas are pinned in it and compared with QUESTION-FORMS
by the service tests and the independent driver's self-test. The ordinary live
launcher selects a binary on the qualification front. The principal has
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
refuses any other failure. Study branches use the committed apparatus
checkout's independent driver without study-specific changes;
ordinary driver maintenance lands in that checkout first.
The recorded self-test failure is not hidden. Variant commits stay
reachable under a ref while their evidence is cited. Adopting a variant goes
through the full cycle on `main` with an independent driver author.

- [ ] Retain and review Linux acceptance and a matching launcher rehearsal for
  the implemented study mode before binding the live packet. Native checks
  passed in `.scratch/haiku-authoring-01/host-checks-02`; `native-review-01.json`
  in the setup folder records the counts, reused passes, expected independent
  self-test mismatch and limits. The original runner and failed attempts remain
  intact, including the inherited-mask failure explained by
  `runner-correction-01.json`. The completed fake-provider rehearsal is in
  `.scratch/c10-interface-host-02`, with reviewer controls in
  `.scratch/c10-interface-review-host-02`. Earlier stopped/diagnostic attempts
  remain in `.scratch/c10-interface-native-01` and
  `.scratch/haiku-authoring-driver-native-01`.
  The apparatus is committed at `fa21e8c`; the four-file variant is `aa8a469` on
  `study/account-composition-01` in `.scratch/haiku-authoring-worktree-01`.
  `.scratch/haiku-authoring-acceptance-01` completed both architectures but is
  not ready to support the packet. `acceptance-review-01/RESULT.json` in the
  setup folder records the actual failures: the old text/version produces
  request and manifest/confirmation mismatches, and native ARM64 additionally
  fails the 100 ms protocol gate at 101.081 ms for the 4 MiB recording call.
  All four credential cases passed on both architectures. The ordinary failure
  names agree across architectures, but their full inventory and 27 controls
  without passing baselines still need review before an expected-difference
  binding. The timing failure is not a permitted text/version difference.
  Four fixed native comparisons (qualified, variant, variant, qualified) are
  retained in `.scratch/haiku-authoring-timing-01`, reviewed in
  `timing-review-01.json` in the setup folder. Both binaries exceeded the
  protocol timing threshold in both attempts; the selected functional checks
  and three sabotage controls passed each time. The principal reports battery
  operation and possible concurrent tests. This does not establish a regression
  caused by the variant or identify the environmental cause. At the principal's
  request, `run-timing-02.py` prepares the same comparison after plugging into
  AC power, allowing other tests to finish and waiting for host activity to
  settle. It retains new evidence in `.scratch/haiku-authoring-timing-02` and
  records power source and host load before/after the measured runs. Its logs
  confirm AC power; both binaries again exceeded the old protocol budget,
  while the selected functional checks and three controls passed each time.
  The principal authorized 120 ms as the protocol tripwire. That budget is
  implemented in the ordinary independent driver and documented in
  [the apparatus](apparatus/README.md#provider-network-and-witnesses); native
  check evidence is in `.scratch/protocol-budget-120-01`. The remaining host
  loopback self-tests precede committing and merging the ordinary driver update
  into the variant. Then run fresh Linux acceptance in
  `.scratch/haiku-authoring-acceptance-02`, review its exact text/version
  differences, and rehearse the launcher. The old runs retain their original
  failed outcomes; no historical result is regraded. Keep the failed run and the variant
  branch/worktree while their evidence is used; do not advance the front.

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

The first baseline is retained in `.scratch/frsrr-baseline-a-01`, pinned with
`review/result.json`. Its Problem A placement and later saved-connection
collection passed procedural review; the auditor sealed the return, delivery
was verified and the audit closed. All 509 files in the original export remain
unchanged in the second snapshot. `review/interaction.json` preserves the tool
exchanges, and `review/answer-assessment-01.json` keeps substantive review separate
from citation and custody checks. There is no model qualification claim.

The commission record is `.scratch/frsrr-study-commission-01`:
`packets/problem-a.for-approval.json` fixes the approved bytes,
`authorization-a.json` records the principal's single-placement permission,
and `compatibility-and-cost.json` and `sizing.json` record the dated compatibility,
pricing and workload estimates. A used `claude-haiku-5-5`, omitted effort
(provider default medium), 48 turns, 5,000,000 cumulative input tokens,
32,000 output tokens and an 1,800-second watchdog. Sixteen requests used
603,844 input and 8,318 output tokens, with no retries or compaction. The
calculated cost is USD 0.0645434, not an independently observed charge.

A's answer review has a disposition. Learn from organization, repeated material
and the placement of known method information without optimizing toward the
principal's or reviewer's better rewrite of this small, explicit question.
Changes to organization, reorganization or structured submission remain possible
study choices. The comment-interpretation issue is outside the project's remit.
The principal's direction is preserved in
`review/reading-01/scope-direction-01.txt` beside A's run; it does not prohibit
retrospective analysis or establish an interface cause for ordinary prose
problems. No implementation intervention is selected.

The separately authorized B placement has completed at `701ce08`, retaining
the same model, effort, allowances and interface. Its packet and authorization
are `packets/problem-b.for-approval.json` and `authorization-b.json` in the
commission folder; `compatibility-and-cost-b.json` owns the dated recheck.
The review in `.scratch/frsrr-baseline-b-01/review/result.json` is pinned in
the qualification record. It passed: auditor seal, verified delivery and ordinary
close, with nine successful requests, no retries or compaction, and four refused
citation writes followed by accepted revisions. Later saved-connection collection
preserved all 442 original files and added four collection records. Its calculated
cost is USD 0.0187986. The original export and interaction remain retained;
`review/answer-assessment-01.json` keeps the assistant's substantive assessment
separate from the principal's now-completed reading. Both authorized placements
are consumed; no further model call is authorized by these packets.

- [ ] Reconcile A's and B's calculated costs with independent Console
  observations or give those observations explicit dispositions.

The workload sizing is complete for this pair. A turn is one provider response
and each request resends the whole context; cumulative input allowances must
cover that transfer. Do not infer model inability from a limit stop or silently
rely on unqualified compaction and continuation paths.

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

The pilot warm-up is complete, original first. In
`.scratch/c10-live-01/review/reading-01/`, `first-form-response.txt` and
`second-form-response.txt` preserve the principal's words; their adjacent JSON
records bind the forms and order. `reading-result.json` separates the assistant's
synthesis from those observations. The principal found less uncertainty about
authorship, sealing and byte checking, but said the added explanation largely
concerned things that should be unobtrusive and not mentioned. They reported
no clear change to the overall answer. This does not establish a preferred
rendering or an effect attributable solely to entry order: the view also added
provenance explanation. Carry the objection to foregrounding those details into
intervention selection; no change to custody obligations follows from it.

A's two responses are recorded in
`.scratch/frsrr-baseline-a-01/review/reading-01/first-form-response.txt` and
`second-form-response.txt`, with form bindings and context in their adjacent
JSON. The study view came first without the question; the principal reported
difficulty identifying the finding and the relevance of its limits. The original
form followed with the exact question in `question-context.txt`;
`second-form-context.json` records that changed condition. With the question,
the principal found the main answer apparently correct but criticized repeated
block-count explanations, an ambiguous comment/code relation and a known method
caveat interrupting linear reading. `reading-result.json` keeps the assistant's
synthesis separate. The subsequent scope direction above gives the answer
discussion its disposition. The two responses do not isolate an effect of
rendering because question context and prior exposure also differ.

B's reading is complete, original first, with the same exact question supplied
with both forms. In `.scratch/frsrr-baseline-b-01/review/reading-01/`,
`first-form-response.txt` and `second-form-response.txt` preserve the principal's
words; adjacent JSON binds the forms and context, and `reading-result.json`
separates the assistant's synthesis. Entry order was unchanged. The original
made the inability and its stated reason clear, but left sealing and verification
unclear. The principal found the study view better overall: attribution and
assembly were clearer, section labels less intrusive than Markdown H2 headings,
and citation details separated from prose immediately beneficial for this short
answer. The three agent-added provenance sentences were noisy or undermined
confidence by explaining routine guarantees and disclaiming substantive judgment.
The principal cautioned that distant citations might become difficult to relate
to claims in a much longer answer. Why this run differed from an earlier ad hoc
trial remains unresolved; no comparison here isolates that cause.

All three planned sittings are complete. Carry quieter attribution and section
presentation, fewer routine operational explanations, and readable citation
placement into the next proposal. The benefit of separated citations on these
short returns does not establish a universal endnote layout; locating the exact
claim and returning to it remain design questions for longer answers. No new
rendering contract or implementation intervention is selected by this account.

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
