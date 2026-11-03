# C10: real-model conformance apparatus

Build a reusable Messages API apparatus that can establish whether a named model
uses Stewart's arrangement and finishes. The gate and required observations are
owned by [ACCEPTANCE C10](ACCEPTANCE.md#the-real-model-conformance-tier);
[INTERFACE](docs/INTERFACE.md#6-the-run-adapter) owns the adapter behavior and
[QUESTION-FORMS](docs/QUESTION-FORMS.md) owns the three implemented forms.
Answer usefulness remains the manager's judgment.

This plan authorizes no model calls. The first deliverable is a checked apparatus
for small fixed commissions. Full conformance also needs controlled interruption,
actual provider compaction and a reviewed result for every required run. A model
is supported only after its whole gate passes.

## Starting points and boundaries

Reuse the [retained-session launcher](apparatus/sanity/LAUNCHER.md), its qualified
binary selection, credential-free intake, hidden credential entry, operator
commands and conservative export checks. The [qualification record](apparatus/qualified.md)
owns demonstrated results; run `python3 -I -B apparatus/qualified.py check` before
relying on it. Existing sanity and mechanism results remain supporting evidence,
with their original scope and records.

The concrete generalization points are:

- [Session setup](apparatus/sanity/session.py) fixes open inquiry and enumerates
  only immediate material files. [Specimen identity and packet validation](apparatus/sanity/session_support.py)
  bind one fixed specimen and permit exactly one placement.
- The same session's export checker requires one run and one run directory.
  [Operator commands](apparatus/sanity/control.py) can add evidence after that
  session's export; a later review needs those effects too.
- [Offline review](apparatus/sanity/review.py) verifies the export digest and
  indexes selected records. It does not implement the C10 gate, and its one-MiB
  indexing cutoff needs an explicit disposition for larger evidence.

Keep the current product contracts, direct provider route and credential boundary.
Choose the new apparatus layout and shared helpers during implementation; preserve
the ability to interpret retained sanity evidence without rewriting it or adding
record-format compatibility shims. No prompt, tool or rendering variant silently
becomes the release arrangement.

## 1. Fix the evidence matrix and specimens

- [ ] Give every case a stable identity and map it to the exact C10 obligation,
  specimen, family, model/settings, expected mechanism, evidence and verifier.
  Separate an audit, its placements and its provider request attempts in counts.
- [ ] Prepare small executable submissions for open inquiry, inquiry framing
  and comparison, including inadequate-evidence cases and illustrative returns.
  Use the [worked examples](examples/questions/README.md) and
  [citation controls](examples/questions/CITATION-CONTROLS.md) as source material;
  preserve cited material bytes when copying them. Example prose is never an
  expected model answer. Keep illustrative returns, private inspection notes and
  controls outside the material supplied to the model.
- [ ] Enumerate every fixed commission before setting the run total. For `N`
  commissions, the current requirement is `3*N + 3` completed audits per model:
  three repetitions each with effort omitted, then one effort-set audit, one
  compaction audit and one killed-and-continued audit. If ordinary and inadequate
  evidence are separate commissions for each family, `N=6` means 21 audits, not
  12. The interrupted audit needs at least two placements. Select the specimens
  and effort level for the additional audits explicitly in the matrix.
- [ ] Record operation coverage without making every tool or section mandatory.
  Missing sections and empty submissions remain admissible. A run that never
  cites, edits or records an entry supplies no evidence for those unused paths.
  A recovery run with no pre-event entries cannot establish preservation of
  recorded work; report the coverage gap without inventing a content grade.
- [ ] Define failure dispositions before launch: missing evidence, a mechanism
  not reached, provider rejection, limit stop, unsubmitted ending and manager
  seal cannot count as a successful C10 audit. Retain every attempt. A replacement
  run needs an authorized disposition and remains linked to the failed attempt;
  repeated trials until success cannot erase failures from the gate report.

**Done when:** the case inventory is complete enough to derive exact audit,
placement and repetition counts, each specimen prepares through the real binary,
and every claimed check has an evidence source and a control design. A decision
to change ACCEPTANCE's coverage or gate belongs to the principal.

## 2. Generalize preparation and bounded launch

- [ ] Accept a selected specimen and preserve its family and literal recursive
  material population. Bind the template and the actual rendered submission;
  record model, limits, effort and destination substitutions explicitly. Verify
  accepted question/material readback against an independent input witness.
- [ ] Define a versioned run manifest and commission packet covering case IDs,
  repetitions, model/settings, qualified executable, apparatus source, container
  image, endpoint, input identities and permitted placements. Refuse crossed or
  changed bindings before credential entry. Keep account labels non-secret.
- [ ] Track each planned audit and actual attempt in an inventory. A lost host
  reply leaves unknown effects to reconcile against its retained reference and
  process records; it never starts a replacement audit automatically. Stop the
  batch on an unexpected outcome pending its recorded disposition.
- [ ] Preserve hidden terminal entry and the inherited-descriptor route. Keep
  per-audit cumulative limits, built-in request retries, watchdog termination
  and batch spending authority distinct. No wrapper retries, model fallback or
  continuation beyond the packet's authority. Include a credential-free network
  preflight so a connectivity failure is diagnosed before a paid placement.
- [ ] Give the operator exact commands and safe summaries for every audit, with
  separate run, seal/actor, delivery and closure facts. Cover every specified
  condition; an unknown condition stays unknown with its private reply retained.

**Done when:** offline cases exercise all three families, nested materials,
multiple fresh audit identities, changed-binding refusals and loss of a launcher
reply. The launcher accounts for all planned work and exposes usable status/close
commands without repeating a mutation or disclosing credentials.

## 3. Preserve evidence through interruption and later actions

- [ ] Design a witnessed interruption point after actual recorded work and
  before submission. Record the selected point, process identity, signal and
  observed termination. Rehearse graceful interruption and abrupt process death;
  choose the C10 kill case explicitly. A sleep alone does not establish the point.
- [ ] Add bounded continuation on the same reference and exact writer. Preserve
  the pre-kill witness outside the audit, verify the fresh conversation's pinned
  arrangement and continuation notice, and reconcile every placement's reported
  and estimated usage into the cumulative limits. An already sealed audit goes
  to custody completion, not another model placement.
- [ ] Extend evidence membership checks across all placements, request attempts,
  partial captures, reconciliation records and later operator actions. Distinguish
  established absence from an unobserved or unreadable member. A killed process
  with no final reply must remain reviewable without fabricating a run result.
- [ ] Add immutable follow-up exports and review records for later actions;
  preserve earlier exports as observations of their own intervals. Establish the
  stopped-writer observation, full membership and credential checks again for
  each export. Specify how credential scanning works after a terminal session
  ends, without persisting the live key or weakening withholding on uncertainty.
- [ ] Keep private originals and independent witnesses when export is withheld
  or fails. Rehearse missing captures, reflection, contamination and export
  failure across continuation and follow-up collection. Never copy a retained
  container wholesale to bypass those checks.

**Done when:** a no-kill case and a controlled killed-and-continued case yield
fully accounted histories; controls for missing/repeated effects, reset limits,
omitted placements and uncertain exports fire. Later close/confirmation evidence
can be reviewed with its original run evidence. Confirmation and loss surrender
remain explicit manager acts under the existing interface.

## 4. Implement the procedural verifier and its controls

- [ ] Specify each witness's origin, storage, observation time and scope. Input
  copies sit outside Stewart's archive. The fake provider independently retains
  its sent/received bytes. Resolve how live authoring and pre-interruption effects
  are witnessed on the direct TLS route: a copy of Stewart's archive after the
  run is not an independent observation of what reached it. Identify checks that
  only correlate Stewart-owned captures and bring any unmet acceptance obligation
  to the principal; do not quietly add a TLS proxy or claim independence.
- [ ] Verify pinned system/tool/model/effort bytes and request output caps,
  mechanical citations against witnessed sources, accepted authoring effects,
  preparation/submission bindings, auditor attribution and exact delivered
  membership/bytes. Reconstruct the selected answer from the observed edit history
  under the specification, not from an assumed expected conclusion.
- [ ] Check continuity across compaction and interruption using invocation,
  entry and revision identities. Detect lost work and repeated additions caused
  by re-entry. Legitimate edits and fresh equal-byte entries remain distinct;
  content equality alone cannot establish an accidental replay. Define what
  needs human inspection and report unresolved comparisons explicitly.
- [ ] Reconcile ordinary and compaction usage, reported versus estimated charges,
  retries, notices and every placement. Report actual tool operations, re-entry
  calls and their timing, submission, delivery and close separately. Keep provider
  usage, calculated cost and independently observed billing distinguishable.
- [ ] Make all required missing, malformed, duplicated, uninspected or conflicting
  evidence visible. Use bounded inspection and streaming hashes where needed;
  large captures cannot silently disappear behind an indexing cutoff. Exercise
  representative large histories and export sizes within measured container
  memory/storage limits before selecting live resource settings.
- [ ] Pair checks with firing controls, differing cases and invariance cases.
  Cover altered/missing returns, invalid citations, changed arrangement bytes,
  false auditor attribution, omitted history, duplicated effects, changed signed
  summaries, missing summary usage and reset cumulative limits. Work on copies
  and retain originals. Report case/variant counts and skips as actually run.

**Done when:** the verifier derives each gate result from named evidence, detects
the broken controls and preserves the unchanged comparisons. Reports distinguish
pass, failure, incomplete evidence and unexercised coverage. Human observations
about answer quality remain outside the mechanical gate.

## 5. Establish real compaction and provider coverage

- [ ] Design a separate specimen that reaches the pinned trigger in
  [INTERFACE 6.2](docs/INTERFACE.md#62-requests-and-responses), currently 150,000
  tokens, with recorded work before compaction and ordinary work afterwards.
  Specify how reaching the trigger will be observed and how failure to reach it
  will be reported. Do not lower the release trigger to obtain a passing result.
- [ ] Require a real summary request/response, the signed content block reused
  unchanged on the next ordinary request, the correct replacement of context,
  accounted iteration usage and the subsequent preservation of recorded work.
  A fake summary tests the apparatus and cannot qualify provider compaction.
- [ ] Estimate cumulative input consumption across the growing conversation,
  summary and subsequent requests, plus permitted retries and interrupted-response
  estimates. Context size is not the cumulative input budget. Rehearse evidence
  volume and verifier controls offline before proposing this live packet.
- [ ] Verify current provider compatibility against primary documentation when
  freezing a live packet: exact model, API/beta versions, effort, compaction,
  authentication, output cap and timeout. Record dated sources and unresolved
  points. Real observations must use the selected release binary and its TLS roots.
- [ ] Keep real-provider timeout and `max_tokens` behavior explicit in the
  coverage matrix. An output-allowance stop is not a provider `max_tokens` stop;
  a response arriving within the timeout does not demonstrate timeout handling.
  Propose any additional mechanism probe with its evidence objective and budget,
  or obtain an explicit disposition through acceptance review. Do not add a
  deliberate usage-limit study as an incidental test.

**Done when:** the compaction and provider-coverage packets have exact conditions,
observable success/failure criteria and bounded spending proposals. Actual live
coverage remains outstanding until those authorized runs supply the evidence.

## 6. Rehearse, commission and report

Two apparatus milestones keep completion concrete:

| Milestone | Required result |
| --- | --- |
| Small-commission readiness | Fixed small specimens and case inventory; generalized launch with exact bindings and bounded authority; independent input readback; automated procedural review; loss-of-reply handling and later close/evidence collection; synthetic credential and export controls demonstrated in retained Linux runs. Specialized recovery/compaction coverage remains visibly outstanding. |
| Full C10 apparatus readiness | The first milestone plus witnessed kill/continuation, multi-placement accounting and export, compaction specimen, summary verification, scale checks and their firing controls. All required cases and budgets can be derived from the manifest. |

- [ ] Freeze schemas and observation rules before dependent implementations.
  Follow the [driver-independence rule](AGENTS.md#preserve-independent-evidence):
  a session that reads `service/src` or `service/tests` cannot edit the driver.
  If both need changes, use separate implementation and specification-only driver
  authors. Keep apparatus checks derived from the specification.
- [ ] Add useful help, refusal/failure messages, an operator run sheet and exact
  offline test commands with the implementation. Extend the existing
  `python3 -I -B apparatus/sanity/test_launch.py` checks or supply a documented
  successor; add its applicable check row to DEVELOPMENT when code lands.
- [ ] Run the applicable [DEVELOPMENT checks](DEVELOPMENT.md#what-to-run-for-what-you-changed):
  link check for prose; shell syntax checks for changed scripts; driver self-test
  and case list for driver changes; both Cargo configurations for service changes.
  Driver and service changes also need the scheduled Linux acceptance suite;
  changed scripts need the container suite that uses them. Qualification-tooling
  changes need its self-test and record check. Commit apparatus code before its
  container rehearsal, which runs archived source. Local checks alone establish
  no Linux qualification.
- [ ] Retain Linux rehearsal output with exact source, binary/image identities,
  environment/filesystem, command streams, counts, skips, timings, controls,
  witnesses and export outcomes. Recheck qualification bindings before real-key
  use. Record limitations of the observed platform rather than transferring its
  result to another architecture or WSL2.
- [ ] Prepare separate bounded live packets for small commissions and the
  additional conformance mechanisms. Name exact models/settings, all audit and
  placement counts, retry/continuation policy, cumulative allowances, wall-clock
  stops and batch stop conditions. Include dated cost estimates and the limits
  of those estimates; Stewart supplies no dollar ceiling. Obtain the principal's
  authorization for the concrete packets before any model-consuming work.
- [ ] Review all actual outcomes and publish a per-model C10 report with source
  links, exercised/unexercised procedures, full conversations, provider usage and
  available billing evidence. Preserve failures and resolve any missing billing
  observation explicitly. Extend qualification-record tooling as needed so the
  conformance result can be checked against its retained evidence; never hand-edit
  generated qualification Markdown or rewrite historical receipts.

For this work, the principal executes commands that change the Git index or
commit state, and commands that operate containers. Supply those commands with
`!`. Supply paid launch commands without `!`; the principal runs them and enters
the API key in a separate terminal. A paid launch command follows the bounded
authorization above. Prepare and verify all files before handing over Git
commands, and stage/commit only the intended paths.

The plan is complete when the apparatus is demonstrated and each commissioned
model has a reviewed gate outcome with failures and unexercised work explicitly
disposed. Keep enduring procedures in apparatus documentation and tests, the
results in the qualification record, and then delete this plan. Evidence and
container disposal remain governed by
[DEVELOPMENT](DEVELOPMENT.md#evidence-and-retention).
