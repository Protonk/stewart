# Manager interface implementation and testing

**Current status:** The file-only commissioning and custody path exists. The
manager contracts are specified. Both runtimes bind the manager's `question/2` role declarations
and family descriptor in the arrangement. CLI preparation reports reference
errors and family-specific advice. The read-only preparation MCP supports
discovery, explanation and prospective assessment. The standalone CLI exposes
command effects and delivers the accepted question with the answer. MCP candidate
assembly remains open.
Live trials require a separate bounded commission.

This plan owns the manager CLI, optional preparation MCP server, question-type
guidance and their integration tests, including separately commissioned Claude
Code subscription trials. The objective is an ordinary-file commission followed
by bounded CLI execution and faithful custody, with optional MCP assistance
before commissioning. Neither authority nor lifecycle depends on MCP use.

## Contract inventory and selected changes

The owning specifications are [DESIGN](../DESIGN.md),
[CONTRACTS](../CONTRACTS.md), [INTERFACE](../docs/INTERFACE.md),
[QUESTION-FORMS](../docs/QUESTION-FORMS.md) and [ACCEPTANCE](../ACCEPTANCE.md).
This inventory distinguishes existing behavior from work still owed.

| Area | Existing commitment or evidence | Selected work |
| --- | --- | --- |
| Commission and authority | Ordinary submission files; CLI `prepare` binds a proposal, `commission` explicitly accepts it, and `run` launches only an accepted commission. | Keep these distinct operations. MCP supplies no required token, manifest, registration, certification or privileged handoff. |
| MCP boundary | The stdio server discovers families, explains them and assesses a supplied question and inventory. | Add dry-run and explicit creation of candidate files. |
| Shared rules | The CLI and MCP use the same parser, material bounds, role assessment and family descriptors. | Use these rules for candidate assembly and retain independent acceptance checks. |
| Material roles | Families have different purposes, instructions and recording tools. Empty materials and intellectual insufficiency remain admissible. | Validate declared role structure and references; give type-specific warnings for missing evidence roles and suggestions for improvements. Do not introduce an evidence-completeness gate. |
| Documentary output | Help and `describe` expose the same compiled command effects. The preparation MCP has versioned schemas and per-call detail. | Describe candidate assembly when the MCP gains workspace access. |
| Return context | The [returned-question contract](../CONTRACTS.md#returned-question-and-answer) binds the accepted question body separately from the auditor’s answer. | Apply the same package checks to MCP-assisted commissions. |
| Lifecycle | Custody, interruption, continuation, delivery and close use one operation core. | Extend comparison coverage across file-only/MCP-assisted construction, direct/wrapped CLI invocation and both implemented runtime arrangements. |
| Runtime evidence | [Current demonstrations](../README.md#status) and [retained evidence](../apparatus/qualified.md) identify the reviewed native service use and synthetic acceptance coverage. | Reuse the apparatus for bounded question-family trials. Fake-provider evidence establishes the manager-interface boundary; live trials establish only the additional mechanisms actually witnessed. |

The MCP boundary is a separate entry point in the shipped `stewart` binary,
consistent with the existing single-binary design. Its dispatcher cannot invoke
the operational CLI or auditor. The manager preparation server is distinct from
the auditor-facing MCP transport used by the development runtime; they share no
session, audit handle or lifecycle tool surface. Use existing dependencies.

The first registry covers the three implemented families: open inquiry, inquiry
framing and comparison. Preserve the five purposes in the
[family contract](../CONTRACTS.md#question-families-and-open-inquiry); claim
examination and experimental inquiry remain unimplemented dedicated families.
Do not advertise them as commissionable or invent another taxonomy. Their exact
prompts, tools and specimens remain deferred, rather than becoming prerequisites
for this interface.

Role declarations must be well formed and refer to selected material. Absent
evidence and unmapped expected roles remain admissible. Do not demand invented
evidence, a waiver, an explanation for choosing open inquiry, or a finished
working question for inquiry framing. No new exception mechanism is selected. If a
future contract permits an exception to a structural rule, its rationale must
be explicit and captured; MCP cannot silently waive CLI rules.

`answer`, `needs-evidence` and `reframe` remain legitimate intellectual returns,
not required labels, lifecycle states or automatic content classifications.
Question-family choice grants no execution, additional access or budget. Close
accounts for custody; it does not certify an auditor's conclusions.

## Implementation sequence

Each stage includes its specification, help, failure semantics and tests. The
documentation stage below completes the joint walkthrough; documentation is not
postponed until code is finished. Freeze shared schemas before splitting service
and independent-driver work between authors.

### 1. Shared contracts specified

The [family registry](../docs/QUESTION-FORMS.md#manager-family-registry),
[declarations and capture](../docs/INTERFACE.md#declared-material-roles),
[diagnostics](../docs/INTERFACE.md#commissioning-diagnostics),
[command effects](../docs/INTERFACE.md#510-prospective-command-effects),
[preparation protocol](../docs/MANAGER-PREPARATION.md) and
[returned-question member](../docs/INTERFACE.md#returned-question-in-revision-2)
are the implementation inputs. [C21](../ACCEPTANCE.md#c21--manager-preparation-and-command-inspection)
owns the new scripted comparisons, alongside C5 and C7.

The worked-packet change exercise used the framing example. A hypothetical
new role for incident reports would change the family descriptor and registry
version, its explanation fixture and family acceptance cases. Editing only
the presentation advice for an existing role changes the descriptor text and
new readable/machine arrangements, not existing captures. Neither edit changes
the material scanner, reader, runtime dispatch, recording tools, answer form
or close. Preserve that boundary in the shared extraction.

The lookback's proposals for comparing the compiled family at run, pinning
answer expectations, role-aware reading and separate presentation advice,
and identifying tools on refusal remain unselected. The registry work
introduces none of those changes to the auditor's interface.

### 2. Implement one set of production rules

The file-only path, packet producers and independent drivers use `question/2`.
Both runtime arrangement tests compare the previous fields against their original
digests for all three families and supplied open-inquiry guidance. The worked
packets exercise complete and limited evidence. Captured runtime originals keep
their historical bytes.

The MCP uses the same parser, material checks and role assessment as CLI
preparation. It takes a prospective inventory directly. Discovery and
explanation expose the family descriptors. The independent driver compares
the two callers on a one-sided comparison, a misspelled source and its
correction, including the facts and effects at both detail levels.

### 3. Independent CLI path

`stewart describe COMMAND` and `help commands` show this build's possible
effects. Direct and wrapped file-only commissions use the existing lifecycle
commands. Status retains the last recorded cause and message, prior refusal
effects, and the supported recovery calls.

The `stewart.return/2` manifest binds the exact accepted question body
separately from the answer. Delivery verifies the entire accepted capture
before copying the body. Independent comparisons cover a changed header, a
missing receipt, partial intake, lost replies, and substituted package members.

The [qualification record](../apparatus/qualified.md) identifies
`split-matrix-release-01` at `9b0afe6` as the Linux release run for this
stage. Both architectures passed all 158 cases and fired every control.

- [ ] When work resumes, run and review the
  [offline C10 rehearsal](../apparatus/c10/README.md#run-the-offline-checks)
  with qualification ID `split-matrix-release-01`. C10 has only native
  development results for this change.

### 4. Implement the bounded manager MCP surface

| Capability | Function | Required limits |
| --- | --- | --- |
| Discover | List supported types, purposes and availability. | Built-in documentary data only; no audit discovery. |
| Explain | Show a selected type's role structure, enforced constraints, conventions and examples. | Distinguish requirements from advice; `detail` expands rationale per call. |
| Assess | Apply the shared rules to an explicitly supplied prospective question and material inventory. | Bounded reads within the declared candidate workspace; report errors/warnings/suggestions and unestablished CLI conditions. |
| Assemble | Propose a candidate layout and question, or explicitly create them. | Ordinary files only; explicit destination, default dry-run and no overwrite. No acceptance or privileged CLI handoff. |

- [ ] Extend the read-only dispatcher with assembly using the same prospective
  rules. Keep each call independent of earlier proposals.
- [ ] Define and enforce candidate access before opening content. Reject audit
  references, archive/delivery paths and path escapes; cover symlinks, hard-link
  aliases and case aliases as applicable to the declared workspace policy. Do not
  scan archives to discover execution progress or use audit contents to construct
  advice. State the actual access boundary and its limits, without claiming OS
  confinement merely because a tool checks paths.
- [ ] Keep all documented functionality available with lifecycle dispatch,
  auditor launches, provider access and credential access unavailable. No remote
  material gathering, model calls, prose sufficiency judgments, audit monitors,
  resume/close tools or automatic family selection.
- [ ] Make dry-run produce the proposed files/effects and predictable validation
  results with no writes, including no directories, locks or temporary files.
  Distinguish those forecasts from permissions, races, source stability and
  acceptance that a later CLI operation alone can establish.
- [ ] Initially create only a fresh, explicit candidate destination. Refuse an
  existing destination instead of overwriting, merging or silently renaming it;
  never mutate an established audit. Specify partial creation/interruption
  reports, bounded supplied source reads and what a safe retry does. Generation
  stays deterministic from explicit inputs and documented templates.

**Complete when:** all four capabilities satisfy their schemas and access rules,
candidate creation has predictable effects, and no call exposes lifecycle
information. Human and agent managers can use the same ordinary file handoff.

### 5. Finish the documentary interface

- [ ] Publish one file-only walkthrough and an equivalent optional-MCP walkthrough,
  with required fields, advisory roles, diagnostics, creation effects, failure
  remedies and the CLI acceptance boundary. Update scaffold/help/examples and
  status descriptions to agree with the implemented behavior. Print each
  `run_needs` entry legibly in commission and receipt. A run refused after
  completed close must give a next action appropriate to the closed state.
- [ ] Test terse and detailed response examples, effect descriptions and generated
  candidates against the declared schemas and actual rules. Extend the CLI
  checks of the ordinary and inadequate-evidence worked packets to their
  MCP-created equivalents.
- [ ] Explain bounded autonomy, dead-placement continuation and the distinction
  between intellectual outcome, authoring end, seal, verified delivery and close.
  Say where continuation is explained that the reminder is spent once per audit:
  a continued placement can end authoring at its first unsubmitted turn.
  Keep required acknowledgment, placement confirmation and loss surrender; do not
  turn them into intellectual endorsement or remove them as unnecessary approvals.

**Complete when:** examples execute as documented, a manager can identify each
command's effects without executing it, and guidance never represents a candidate
assessment as acceptance, sufficient evidence or an assured answer.

### 6. Demonstrate integration without a real model

Extend the independent acceptance driver from the specifications. An author who
has read `service/src` or `service/tests` cannot edit that driver in the same
session. Shared production rules must not become a shared test oracle.

| Comparison | Positive and differing cases | Invariance and firing control |
| --- | --- | --- |
| Optionality | Construct equivalent ordinary-file and MCP-assisted commissions; execute both through CLI with the fake provider. | Same normalized selection, rules, attribution and durable effects, apart from explicit content and generated identities/times. Change or omit a real required field and show both routes refuse for the same reason. No MCP-use marker is required. |
| Independence | Run every manager MCP capability with operational CLI dispatch, providers, auditor and credentials inaccessible; run every CLI lifecycle operation without MCP. | Observe actual filesystem/process/network access, not just requested settings. A deliberately attempted forbidden access must be detected; changing unrelated audit state cannot affect MCP output. |
| Type consequences | Test all three families' role structures, guidance arrangements and distinct remedies. Comparison distinguishes alternatives/criterion; framing permits an undeveloped concern; open inquiry permits a broad question and explicitly selected guidance. | Invalid declared roles/references fail where specified; empty/unequal/insufficient evidence remains accepted. Renaming valid files or changing irrelevant prose cannot change a role's meaning. Missing roles produce useful type-specific advice. |
| Documentary contract | Validate every reply, version, error and detail variant; compare stated requirements with CLI enforcement. | Mutated required fields, wrong versions and misleading required/advisory labels are detected. Detail changes explanation, not authority or acceptance. |
| Candidate effects | Inspect dry-run and explicit creation, including refusal, partial failure, repeat calls and path races/aliases. | Independently compare directory membership and bytes before/after. Dry-run leaves them unchanged; existing candidates and audits stay unchanged; a deliberate write makes the non-mutation control fail. |
| CLI effects and interruption | Direct/wrapped invocation, fresh working directory/environment, lost replies, repeated calls, failed authorization/authentication/provider interactions and interruption at durable boundaries. | Match observed effects and recovery to descriptions; detect omitted partial effects, duplicated acceptance, reset limits or a false clean state. Unknown results are reconciled before retry. |
| Custody and autonomy | Fake audits with complete, needs-evidence/reframe, empty, unsubmitted, limited, interrupted and damaged/missing outcomes; close before/after launch and after delivery. | No continuation after ordinary ending, submission or exhausted allowance; dead-placement recovery preserves work and cumulative limits. Controls fire for missing return members, changed question/answer bytes, wrong actor, duplicate entries and unconfirmed delivery. Close does not delete retained archive bytes. |

Use independent original inputs and provider/transport witnesses outside the
archive, with observation scope and timing recorded. Carry package inventories
through delivery, close and repeated close. Unexercised behavior, an absent
witness, failed export or incomplete inspection cannot count as a pass.

**Complete when:** native checks pass and the Linux container
suites qualify the exact release binary on both architectures for the manager
boundary and lifecycle claims. Test the gated runtime separately with its
synthetic harness. Real-model release obligations retain their own acceptance scope.

## Additional Claude Code subscription testing

This work exercises question families and the manager workflow with the existing
default-off development adapter. The [runtime contract](../docs/claude-code/CONTRACT.md)
owns its permissions, authentication, placement limits, observation promises
and the limitations not yet demonstrated with the real harness. The distributed binary continues to exclude this adapter. Its
auditor-facing MCP tools do not expose or depend on the manager preparation MCP.

A prepared packet, successful synthetic rehearsal or previous model placement
supplies no fresh spending authority. Each live comparison requires its own
bounded commission; deliberate usage-limit studies need a separate commission.

### Prepare a concrete, reusable comparison

Use the [service procedure](../apparatus/claude-code/README.md#native-service-comparison-procedure),
[independent package witness](../apparatus/driver/CLAUDE-CODE-SERVICE-WITNESS.md)
and reviewed annotated open-inquiry profile at
`.scratch/readiness-pages-surface-01/profile.json`.
Revalidate bindings for each commission; another family or changed surface
needs its own matching reviewed check. Procedures and profiles grant no starts.

- [ ] Build ordinary and inadequate-evidence specimens for all three implemented
  families, reusing the shared commissioning fixtures and existing
  [question examples](../examples/questions/README.md). Include file-only and
  MCP-assisted preparation with equivalent enforceable inputs. Keep illustrative
  answers outside model inputs and observe procedure separately from intellectual
  usefulness. Record the model's actual use/non-use of tools and expressive forms;
  do not require a winner, defect, finding, finished hypothesis or successful answer.
- [ ] Specify the smallest comparison set that answers named uncertainties,
  sharing runs only where their witnesses genuinely cover both. Count audits,
  authentication invocations, model starts, placements and request attempts
  separately. Additional family trials do not silently become a broad blinded
  evaluation or a model-support gate.
- [ ] Add a witnessed external interruption after actual recorded work and
  before submission, paired with uninterrupted and invariance cases. The existing
  fake harness exits after recording; that is not an externally timed kill.
  Keep the pre-interruption witness outside the archive and compare revisions,
  effects, continuation, delivery and close without treating equal text as replay.
- [ ] Define real compaction and re-entry comparisons, effective tool/instruction
  and authentication/access checks before and after compaction, multi-tool-call
  ordering, accounting and submission. Include host/server-managed configuration
  and distinguish supplied configuration from observed enforcement. Fixed
  synthetic answer text cannot be the oracle for a real model's answer.
- [ ] Name the unresolved observations explicitly: usage in a submitting
  placement's final interval; several calls from one response; placement of the
  post-compaction notice; startup validation before the first question reaches
  the provider; actual turn-cap and per-response output enforcement. An unknown
  interval remains unknown, rather than inferred from settings or an intended cap.
- [ ] Freeze each proposed commission's exact inputs, binaries, surface/profile
  pins, model, authentication route, paid-extra-usage-disabled setting, maximum
  starts/placements and duration/resource bound, stopping rules, replacement
  policy and retained witnesses. Include availability probes and authentication
  launches in the requested allowance.

### Run only the approved packet and review what occurred

- [ ] Check fresh bindings and explicit approval before any launch. Reserve
  starts durably, preserve unknown outcomes and stop before a later start if
  termination or a command's effects are uncertain. Reaching an allowance or
  ordinary ending authorizes no continuation or replacement.
- [ ] Review raw inputs/traffic, external package inventories, process observations
  and service captures with their distinct provenance. Service-owned raw captures
  are not independent peer witnesses or complete provider transcripts. Report
  real-harness pass/failure/incomplete/unexercised observations and answer-quality
  judgments separately, without turning native results into Linux qualification.
- [ ] Record results against the actual model, CLI, configuration, authentication
  route, writer and binaries. Apply retention rules after review. An API result
  cannot qualify this harness profile, and a subscription result cannot satisfy
  the Messages API release gate.

### Remaining offline runtime coverage and evidence review

- [ ] Add second-relay-connection refusal within an active placement and a hook
  call after admission stops. Add an independent comparison for `run`'s own
  pinned-surface re-verification or explicitly retain its unit-only limitation.
- [ ] Resolve the qualification-index disposition for
  `.scratch/claude-code-probe-01` and `.scratch/claude-code-probe-02`, whose
  original records lack UTC timestamps. Preserve those originals; do not invent
  dates or rewrite receipts to register them.
- [ ] Finish unresolved observer/failure reviews before releasing their selected
  witnesses: socket errors in `.tmp/observer-repair/`, stopping-observer EPERM in
  `.tmp/bounded-observer/`, relay-copy behavior in `.scratch/relay-diagnostic-03`,
  and observer scope in `.scratch/environment-observer-02`. Recover specific
  original paths from their records and Git when needed. Distinguish an observed
  workaround from an established OS/library cause; missing witnesses remain a
  review limitation. Do not restart old diagnostics or probes.
- [ ] Apply [evidence retention](DEVELOPMENT.md#evidence-and-retention) after each
  review. Release reproducible or superseded working trees when their purpose
  ends; preserve originals needed for unresolved findings and open custody.
  The [qualification index](../apparatus/qualified.md) owns retained suite results
  and selected encounters, not this plan.

## Verification and completion

Use [DEVELOPMENT's check table](DEVELOPMENT.md#what-to-run-for-what-you-changed)
for every implementation change, retaining outputs through review. Markdown-only
plan edits need the link check. Changed specifications/pinned texts, service,
driver and apparatus need their respective named checks; new source is not
qualified by an older suite. Record exact counts, failures, skips and unexercised
mechanisms. Unavailable loopback or another skipped prerequisite cannot be
reported as a passing test.

The manager interface is ready when a manager can construct a conforming
commission through ordinary files; optionally obtain type-specific guidance,
assessment and candidate files; inspect command effects without execution; and
complete bounded CLI operations and custody with faithful accounting of incomplete
work. The integration comparisons must pass for the actual release binary.

Additional real-harness trials have their own reviewed outcome and explicit
disposition for failures or unexercised work. A deferred live commission is not a
hidden blocker on the manager-interface boundary, nor permission to call that
runtime conformant. At completion, put enduring rules in specifications and
tests, give remaining work an explicit disposition, and delete this plan.
