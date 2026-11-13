# Manager interface implementation and testing

This plan owns the manager CLI, optional preparation MCP server, question-type
guidance and their integration tests, including separately commissioned Claude
Code subscription trials. The objective is an ordinary-file commission followed
by bounded CLI execution and faithful custody, with optional MCP assistance
before commissioning. Neither authority nor lifecycle depends on MCP use.

The principal selected this direction from Riker's proposal and explicitly
retained admission of empty or insufficient materials. This is a work plan, not
an implemented interface or permission to launch a model. Implementation follows
the specification work below; live invocations require a fresh bounded commission.

## Contract inventory and selected changes

The owning specifications are [DESIGN](../DESIGN.md),
[CONTRACTS](../CONTRACTS.md), [INTERFACE](../docs/INTERFACE.md),
[QUESTION-FORMS](../docs/QUESTION-FORMS.md) and [ACCEPTANCE](../ACCEPTANCE.md).
This inventory distinguishes existing behavior from work still owed.

| Area | Existing commitment or evidence | Selected work |
| --- | --- | --- |
| Commission and authority | Ordinary submission files; CLI `prepare` binds a proposal, `commission` explicitly accepts it, and `run` launches only an accepted commission. | Keep these distinct operations. MCP supplies no required token, manifest, registration, certification or privileged handoff. |
| MCP boundary | The earlier design selected documentary guidance; no manager preparation server is implemented. | Add pure prospective assessment and optional explicit candidate creation to discovery and explanation. These replace the previous exclusion of mechanical checks from MCP. |
| Shared rules | CLI intake and three implemented question families already have specified rules. | Extract one production commissioning rule implementation for CLI and MCP; keep the acceptance oracle independently authored from specifications. |
| Material roles | Families have different purposes, instructions and recording tools. Empty materials and intellectual insufficiency remain admissible. | Validate declared role structure and references; give type-specific warnings for missing evidence roles and suggestions for improvements. Do not introduce an evidence-completeness gate. |
| Documentary output | CLI has structured replies, observed effects and specified help. | Add versioned MCP schemas, per-call detail, and prospective CLI effect descriptions available without executing or inspecting an audit. |
| Return context | Returning the exact accepted question body with the answer is decided but unimplemented. | Implement the [returned-question contract](../CONTRACTS.md#returned-question-and-answer), with separate manager/auditor attribution and independent package checks. |
| Lifecycle | Custody, interruption, continuation, delivery and close use one operation core. | Extend comparison coverage across file-only/MCP-assisted construction, direct/wrapped CLI invocation and both implemented runtime arrangements. |
| Runtime evidence | Linux synthetic runtime acceptance and native offline apparatus checks exist; no real-Claude service run exists. | Reuse the apparatus; prepare the missing real-service procedures and bounded question-family trials. Fake-provider evidence establishes the manager-interface boundary; live trials establish only the additional mechanisms actually witnessed. |

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
  Inspection reads compiled descriptions, not audit state or credential stores,
  and neither launches providers nor creates references or prepares a selection.
- [ ] Keep provider identity and authentication mode explicit, with descriptions
  matching the actual build. Fake-provider tests and the gated subscription
  adapter exercise the same custody core; neither introduces an approval bypass.
  Add `run --key-fd` help recipes using an existing secret tool, without secret
  persistence or a credential-store dependency. A hidden prompt remains deferred.
- [ ] Implement the accepted question body in the returned package. Verify exact
  bytes and provenance separately from the auditor's answer; do not add supplied
  materials, guidance or operating history as return context.
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

No live invocation is currently authorized. The two earlier probe commissions
are closed. A prepared packet, successful synthetic rehearsal or previous model
placement supplies no fresh spending authority. Deliberate usage-limit studies
need a separate commission.

### Prepare a concrete, reusable comparison

- [ ] Extend the implemented [controller and profile apparatus](../apparatus/claude-code/README.md)
  into an actual-service procedure. Reuse the independent helper/observer and
  [complete-package witness](../apparatus/driver/CLAUDE-CODE-SERVICE-WITNESS.md);
  first rehearse the procedure offline. Do not rebuild completed apparatus merely
  to restart this work.
- [x] Obtain a reviewed real supplied-surface check under its own bounded
  authority before producing an eligible real profile. The
  [reviewed native comparison](../apparatus/qualified.md#readiness-c1-01)
  supplies the open-inquiry profile. The fixture's exact
  family tool inventory, actual Stewart helpers and independent private sockets
  establish supplied-surface compatibility only, not service custody. No
  placeholder or synthetic observation becomes a real attestation.
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

The existing surface-only draft at `.scratch/claude-code-surface-proposal-01`
(commission SHA-256 `da70d69fde47507f5ebff62d27359760c33fa4959ed8b4c4aa6478acbefa9151`)
remains an unapproved draft: three authentication invocations up to 30 seconds
and three model sessions up to 120 seconds, 450 seconds overall, using the earlier
probe's proposed `claude-haiku-5-5` and open inquiry. Availability is unprobed; no
start, reservation or observation exists. Revalidate its scope and pins before
offering it for approval; a changed surface needs a fresh packet. It commissions
neither the actual service nor the family matrix.

### Remaining offline runtime coverage and evidence review

- [ ] Add the still-missing second-relay-connection refusal within a live
  placement, a hook call after admission stops, and the near-limit notice.
  `run` re-verification of a pinned surface currently has unit coverage only;
  design a suitable independently bound comparison or explicitly retain that
  limitation. Share common behavior cases only where driver independence permits.
- [ ] Register the two native probes in the qualification index without inventing
  the UTC timestamp missing from their records or rewriting receipts. Until that
  disposition is resolved, retain their original paths below.
- [ ] Review the selected evidence and release reproducible/superseded work under
  [evidence and retention](DEVELOPMENT.md#evidence-and-retention). The compact
  locator below preserves the inspection purpose; it is not a new qualification
  record or a reason for indefinite retention.

| Evidence to inspect | Scope, unresolved fact and release condition |
| --- | --- |
| `.scratch/acceptance-environment-observer-01`; [qualification index](../apparatus/qualified.md) | Current recorded Linux synthetic acceptance at `b4ccba4`: each architecture passed 24 runtime cases, 9,892 checks and 73 controls, plus 205 self-tests, with no failures or skips. This binds the recorded source/binaries only; preserve the index-owned evidence under normal retention. |
| `.tmp/service-witness/host.mboAA5`, `host-review.log`; `/private/tmp/stewart-service-witness-01` | Latest native complete-package rehearsal: 2 runtime cases, 865 checks, zero runtime control cases; 32 separate self-test controls. Six host commands passed without timeouts/skips, source unchanged, outer groups absent. Review verified 283 root evidence members and 9 package snapshots/72 members. Retain through first service-comparison review; synthetic continuation is exit-after-record. |
| `.tmp/service-witness/independent-self-test-final.log`, `independent-evidence-review-final.log`, `prior-linux-positive-review-02.log`, `prior-linux-positive-control-02` | Independent witness controls and launch-free comparison to copied Linux evidence; fixed synthetic expectations cannot judge live answers. The first local comparison omitted `actor`; its setup-error log/copy remain at `prior-linux-positive-review.log` and `prior-linux-positive-control`. No original receipt changed. Retain through service-witness review. |
| `.tmp/surface-controller/host.gt15l7`, `host-02-review.log`; `.scratch/claude-code-observer-rehearsal-03`, `.scratch/claude-code-controller-rehearsal-01` | Native synthetic controller/observer review passed all 14 commands; controller 13 and observer 58 checks, no failures/skips. Five listener controls and normal/bad-init/wrong-auth controller cases passed; failures prevented effects and later starts, all launched groups absent. No eligible real check/profile was emitted. Retain through first real surface review. |
| `.scratch/claude-code-service-installation-01`, `.scratch/claude-code-surface-rehearsal-01`; `.tmp/profile-bootstrap/host-review.log` | Installation public signing/executable evidence and actual-helper synthetic comparison, with authentication and real startup unexercised. Revalidate the installation and surface against any proposed live packet. |
| `.tmp/surface-controller/host.ij81RP`, `host-01-review.log`; `.scratch/claude-code-observer-rehearsal-02`; `.tmp/observer-repair/` | Original listener control failed with `ENOTCONN`; 4/5 controls and 12/13 commands passed. Ordered socket comparisons distinguish EPIPE, ENOTCONN and EOF; the original syscall remains unattributed. Repaired correlated-request/attempted-byte controls passed. Keep originals until failure/control review is complete. |
| `.tmp/bounded-observer/host.Qt0uwr`, `host-01-review.log`, `owner-loss-fix-review.log`, `host.CD7Wrh` | Owner-loss observation encountered EPERM; later absence was observed. Corrected controls preserve EPERM as unknown and require absence. The OS cause is unestablished; retain through stopping-observer review. |
| `.scratch/acceptance-runtime-queue-01`, `.scratch/relay-diagnostic-01`, `.scratch/relay-inspection-01`, `.scratch/relay-diagnostic-02`, `.scratch/relay-diagnostic-03` | Original Linux initialization failure, timed-out diagnostic and paired copy-loop evidence. Recovery observed the old diagnostic stopped. The paired comparison distinguished blocking standard-library-copy paths from explicit reply copying, without identifying the underlying kernel/library defect. Keep original failed work/exports through diagnosis; never restart the old probe. |
| `.scratch/acceptance-relay-fix-01`, `.scratch/environment-observer-01`, `.scratch/environment-observer-02`; `/private/tmp/stewart-environment-observer-native-01` | Failed locale witness observed Python startup effects; the repaired observer captures bytes before Python, after shell startup. Paired native/Linux controls and later full Linux acceptance passed. The local wrapper's failed witness is `/private/tmp/stewart-env-cbr34u6i/results`; the passing host comparison is `/private/tmp/stewart-env-dr5n5rw3/results`. Preserve original failed exports (including special entries) and independent earlier/later snapshots through review; do not rewrite them as passes. |
| `.tmp/runtime-queue/`, `.tmp/relay-fix/`, `.tmp/alignment/host.x1DmST`, `.tmp/driver-gaps/host.QdjlTD`, `.tmp/surface-binding/host.24wFiF`, `.tmp/document-harmonization/`, `.tmp/claude-code-adapter*`, `.tmp/claude-code-contract/`, `.tmp/claude-code-probe/` | Earlier implementation/driver controls, sandbox bind failures and socket EOF comparison. Host `runtime-work.txt` files locate external witnesses where present; the remaining locators are below. Retain selected failures through implementation review, then release reproducible working trees. Do not rebind earlier baselines to a new binary. |
| `.scratch/claude-code-controller-sandbox-01`, `.tmp/surface-controller/sandbox-run.log`, `.tmp/surface-controller/profile-refactor-tests*.log`, `.tmp/toolchain-refresh/profile-tests.log`; `/private/tmp/stewart-observer-listeners-native-01`, `/private/tmp/stewart-surface-rehearsal-native-02` | Setup/bind/filename failures and corrected offline checks. Bind refusals occurred before starts. Keep through review of the corresponding successful native rehearsal, then dispose under ordinary retention. |
| `.scratch/claude-code-probe-01`, `.scratch/claude-code-probe-02` | Closed real encounters with frozen original inputs; retain through launch-arrangement review and timestamp-gap disposition. Their observations authorize no further launch. |

External witnesses retained for that earlier implementation review are
`/private/tmp/stewart-relay-runtime.wx0dO3/run`,
`/private/tmp/stewart-relay-forwarding-fix-01`,
`/private/tmp/stewart-queue-runtime.LGe6um/run`,
`/private/tmp/stewart-align-runtime.SbCg7Q/run`,
`/private/tmp/stewart-gaps-runtime.sDdJDu/run`,
`/private/tmp/stewart-surface-runtime.QTlDKw/run`,
`/private/tmp/stewart-doc-runtime.CGwaur/run`,
`/private/tmp/stewart-cc-native.DyFPFv/run`,
`/private/tmp/stewart-claude-driver-checks.AhLaUX`, `/private/tmp/scc5` and
`/private/tmp/scc6`. Review their selected purpose before disposal; this planning
consolidation does not delete or revise any evidence.

## Verification and completion

Use [DEVELOPMENT's check table](DEVELOPMENT.md#what-to-run-for-what-you-changed)
for every implementation change, retaining outputs through review. Markdown-only
plan edits need the link check. Changed specifications/pinned texts, service,
driver and apparatus need their respective named checks; new source is not
qualified by an older suite. Record exact counts, failures, skips and unexercised
mechanisms. Fix unavailable-loopback reporting so an actual skip cannot be
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
tests, give remaining work an explicit disposition, remove consumed evidence
locators and delete this plan.
