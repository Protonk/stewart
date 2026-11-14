# Manager interface implementation and testing

This plan owns the manager CLI, optional preparation MCP server, question-type
guidance and their integration tests, including separately commissioned Claude
Code subscription trials. The objective is an ordinary-file commission followed
by bounded CLI execution and faithful custody, with optional MCP assistance
before commissioning. Neither authority nor lifecycle depends on MCP use.

Empty or insufficient materials remain admissible. The manager preparation MCP,
shared family/role registry, prospective effect inspection and returned-question
member remain to be implemented. Live trials require a concrete bounded
commission; this plan grants no model or authentication launch authority.

## Contract inventory and selected changes

The owning specifications are [DESIGN](../DESIGN.md),
[CONTRACTS](../CONTRACTS.md), [INTERFACE](../docs/INTERFACE.md),
[QUESTION-FORMS](../docs/QUESTION-FORMS.md) and [ACCEPTANCE](../ACCEPTANCE.md).
This inventory distinguishes existing behavior from work still owed.

| Area | Existing commitment or evidence | Selected work |
| --- | --- | --- |
| Commission and authority | Ordinary submission files; CLI `prepare` binds a proposal, `commission` explicitly accepts it, and `run` launches only an accepted commission. | Keep these distinct operations. MCP supplies no required token, manifest, registration, certification or privileged handoff. |
| MCP boundary | No manager preparation server is implemented. | Add pure prospective assessment and optional explicit candidate creation to discovery and explanation. |
| Shared rules | CLI intake and three implemented question families already have specified rules. | Extract one production commissioning rule implementation for CLI and MCP; keep the acceptance oracle independently authored from specifications. |
| Material roles | Families have different purposes, instructions and recording tools. Empty materials and intellectual insufficiency remain admissible. | Validate declared role structure and references; give type-specific warnings for missing evidence roles and suggestions for improvements. Do not introduce an evidence-completeness gate. |
| Documentary output | CLI has structured replies, observed effects and specified help. | Add versioned MCP schemas, per-call detail, and prospective CLI effect descriptions available without executing or inspecting an audit. |
| Return context | Returning the exact accepted question body with the answer is decided but unimplemented. | Implement the [returned-question contract](../CONTRACTS.md#returned-question-and-answer), with separate manager/auditor attribution and independent package checks. |
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

The principal's admission decision applies throughout: role declarations must be
well formed and refer to selected material, but absent evidence or an unmapped
expected role does not prevent commissioning. Do not demand invented evidence,
a waiver, an explanation for choosing open inquiry, or a finished working
question for inquiry framing. No new exception mechanism is selected. If a
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

### 1. Specify the shared commissioning and documentary contracts

- [ ] Walk `new`, `prepare`, `commission`, `run`, `receipt`, `status`, `close`
  and the return against the owning contracts and the
  [interaction findings](../apparatus/studies/interaction/RESULTS.md). Record
  actionable mismatches here as they are found, without reopening the decided
  return-context change for another reader study.
- [ ] Specify the family registry: identity/version, availability, purpose,
  accepted roles, optional evidence classes, declaration shape, structural
  constraints, recommended roles and explanation/remedy text. Derive meanings
  from the existing families, not filenames or an inferred reading of prose.
- [ ] Specify how the manager declares roles in the ordinary question-file
  contract, how paths bind to literal selected materials, and what acceptance
  captures. Preserve the current submission boundary and explicit open-inquiry
  guidance selection. No MCP-only metadata or silently excluded material.
- [ ] Separate diagnostics into stable errors, warnings and suggestions, each
  with its applicable rule, affected field/path/role and concise remedy. Errors
  cover mechanical invalidity; warnings describe accepted arrangements that may
  weaken the inquiry; suggestions offer alternatives without silently changing
  the chosen family, question or selection.
- [ ] Specify the manager MCP transport and four capability schemas, version
  identification, per-call `detail`, bounds, refusal semantics and candidate
  filesystem authority. Define exact command/tool names in INTERFACE. Responses
  identify the documentary/commissioning contract versions, not an invented
  approval record or an audit acceptance certificate.
- [ ] Specify the CLI effect-inspection operation and its machine-readable
  schema, plus the returned-question package change. Add acceptance claims and
  examples to their owning documents. Changed forms replace the old form under
  [version rules](../CONTRACTS.md#versions-and-legacy-obligations); no converters,
  parallel readers or rewritten historical receipts.

**Complete when:** each promised rule has one owner; examples distinguish invalid
structure from admissible insufficiency; exact schemas and test obligations are
reviewable before implementation.

### 2. Implement one set of production rules

- [ ] Extract pure parsing and validation over explicit candidate bytes and
  inventory data. The rule layer cannot open an archive, spawn a process, read a
  credential, query a provider or accept a commission. Filesystem acquisition
  and durable lifecycle operations stay outside it.
- [ ] Make CLI intake and MCP assessment call this implementation. CLI
  preparation and commissioning still perform their own scans, binding,
  source-change checks and acceptance; a previous assessment is not reused as
  authority or proof of an unchanged directory.
- [ ] Put manager-facing explanations in one human-readable, build-consumable
  source. Test examples and requirements against the rules; retain exact pinned
  text comparisons where the form contract requires them. Terse and detailed
  output use the same facts. The source at the build commit supplies the text.
- [ ] Add family-specific fixtures with declared roles, missing mappings,
  invalid references, unsupported role declarations, empty materials and unequal
  evidence. Preserve generic intake refusals and custom-guidance boundaries.

**Complete when:** equivalent candidate snapshots get the same mechanical result
from both production callers, and specification-derived controls detect rule or
documentary drift without importing that validator as the acceptance oracle.

### 3. Complete the independent CLI path

- [ ] Make the complete file-only workflow usable without starting MCP. Keep
  `prepare` and explicit `commission` distinct; no command is replaced by a
  preparation-server interaction.
- [ ] Add effect descriptions to ordinary help and a side-effect-free structured
  inspection operation. Cover every public entry point, including commands whose
  effects are conditional: reads, writes and durable state; provider/network
  contact; authentication route and credential use; transmitted material;
  resource limits/stops; retries; interruption and repeat behavior; inspection,
  execution and custody. Distinguish possible effects from observed outcomes.
  Describe where the two runtime arrangements differ for a manager: request
  retries, an unlisted tool name, usage after a submitted audit, full `read`
  pages against the harness's result limit, and local network failures.
  Inspection reads compiled descriptions, not audit state or credential stores,
  and neither launches providers nor creates references or prepares a selection.
- [ ] Keep provider identity and authentication mode explicit, with descriptions
  matching the actual build. Fake-provider tests and the gated subscription
  adapter exercise the same custody core; neither introduces an approval bypass.
  Add `run --key-fd` help recipes using an existing secret tool, without secret
  persistence or a credential-store dependency. A hidden prompt remains deferred.
- [ ] Implement the accepted question body in the returned package. Verify exact
  bytes and provenance separately from the auditor's answer; do not add supplied
  materials, guidance or operating history as return context. Rewrite the shared
  post-launch return fixture from literal forms with independent expected bytes.
- [ ] Present recorded stop causes, refused-call effects and supported remedies
  consistently across status forms. Use `.scratch/readiness-l0-01/RESULT.json`
  for the startup-ancestry case: the remedy in `run_ended.message` must reach
  status without implying that `run_started` proves an authentication/model
  process ran. Cover relay loss and runtime-specific stopping/usage uncertainty.
- [ ] Exercise direct commands and shell wrappers from different working
  directories and fresh environments. Reconcile repeated/interrupted operations
  against durable records, including reply loss after effects, failed acceptance,
  authentication failure and provider failure. Preserve exact writer and handle
  bindings, uncertainty and supported recovery without manual archive repair.

**Complete when:** file-only commissioning, execution, readback and custody work
with MCP unavailable, and effect inspection accurately describes those operations
while making none of their durable or network effects. No classifier-specific
approval choreography or prediction is part of the interface or test claim.

### 4. Implement the bounded manager MCP surface

| Capability | Function | Required limits |
| --- | --- | --- |
| Discover | List supported types, purposes and availability. | Built-in documentary data only; no audit discovery. |
| Explain | Show a selected type's role structure, enforced constraints, conventions and examples. | Distinguish requirements from advice; `detail` expands rationale per call. |
| Assess | Apply the shared rules to an explicitly supplied prospective question and material inventory. | Bounded reads within the declared candidate workspace; report errors/warnings/suggestions and unestablished CLI conditions. |
| Assemble | Propose a candidate layout and question, or explicitly create them. | Ordinary files only; explicit destination, default dry-run and no overwrite. No acceptance or privileged CLI handoff. |

- [ ] Implement the separate dispatcher using shared pure rules and build-owned
  text, without lifecycle or provider dependencies. Calls have no implicit
  conversation memory; `detail` is not a session or launch setting.
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
  status descriptions to agree with the implemented behavior.
- [ ] Test terse and detailed response examples, effect descriptions and generated
  candidates against the declared schemas and actual rules. Add a check that
  prepares every worked example, including MCP-created candidates.
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

**Complete when:** native checks pass and the user-scheduled Linux container
suites qualify the exact release binary on both architectures for the manager
boundary and lifecycle claims. Test the gated runtime separately with its
synthetic harness. Native WSL2 and real-model release obligations retain their
own acceptance scope; this fake-provider result does not claim them.

## Additional Claude Code subscription testing

This work exercises question families and the manager workflow with the existing
default-off development adapter. The [runtime contract](../docs/claude-code/CONTRACT.md)
owns its permissions, authentication, placement limits and observation promises;
the [runtime reference](../docs/claude-code/RUNTIME-REFERENCE.md) owns technical
limitations. The distributed binary continues to exclude this adapter. Its
auditor-facing MCP tools do not expose or depend on the manager preparation MCP.

A prepared packet, successful synthetic rehearsal or previous model placement
supplies no fresh spending authority. Each live comparison requires its own
bounded commission; deliberate usage-limit studies need a separate commission.

### Prepare a concrete, reusable comparison

Use the [service procedure](../apparatus/claude-code/README.md#native-service-comparison-procedure),
[independent package witness](../apparatus/driver/CLAUDE-CODE-SERVICE-WITNESS.md)
and reviewed open-inquiry profile at `.scratch/readiness-c1-01/profile.json`.
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
  policy and retained witnesses. Present that concrete packet to the principal.
  Availability probes and authentication launches need bounded authority too.

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
