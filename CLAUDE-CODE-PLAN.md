# Claude Code as a peer auditor runtime

Add Claude Code as a peer auditor runtime while keeping audit semantics in
Stewart's Rust core. No Claude Code adapter or live conformance run exists.
The principal authorized the contract proposal and offline protocol work after
the native comparison. The proposal below is ready for decision; changes to
runtime promises precede adapter implementation. No additional Claude launch
or resume, including a model-consuming check, is authorized.

## Scope

The auditor protocol should eventually serve model runtimes and human auditors:
commissioned material access, recorded work, revisions, explicit submission and
closure. Conversation management, token accounting and process termination have
runtime-specific meanings. Human and Codex/OpenAI adapters remain future work.

The distributed integrations keep explicit API or supported cloud-provider
authentication ([CONTRACTS](CONTRACTS.md#run-and-continuation)). The adapter is
developed behind a default-off build feature and is absent from the release
binary; shipping any of it is a later decision for the principal. This plan
takes that build configuration and its credential route as given and covers
the runtime. Common audit and custody terms should survive the change while
runtime-specific accounting and enforcement remain explicit.

The adapter preserves the [question-family meanings](CONTRACTS.md#question-families-and-open-inquiry)
and common custody/attribution contract. A family choice must never implicitly
grant execution, including for experimental inquiry.

Define manager-facing runtime observations within the
[evidence and judgment boundary](CONTRACTS.md#principles-and-scope). Additional
telemetry does not expand Stewart's responsibility into assessing the auditor's
understanding or intellectual completeness.

## 1. Contract proposal for decision

The current recommendation is a native CLI bridge with a stdio MCP relay back
to the sole Rust writer. The [runtime reference](docs/claude-code/RUNTIME-REFERENCE.md#native-launch-recommendation)
compares the SDK helper and protocol choices, specifies the proposed login and
launch controls, and separates documented mechanisms from unverified behavior.
The [reviewed native comparison](docs/claude-code/RUNTIME-REFERENCE.md#reviewed-native-comparison)
demonstrates the bounded synthetic path with the accepted built-in inventory.
Both probe commissions are closed; no additional live use is authorized.

Recommend the following development-only profile. It preserves the existing
question families and custody operations, while explicitly replacing three
Messages-specific promises. These are proposed decisions, not amendments to
CONTRACTS or evidence that the service already implements them.

### A. A harness arrangement, with an explicit observation boundary

The profile pins the native executable, model, local launch configuration,
Stewart-supplied prompt and MCP definitions. It retains the accepted three
built-in plugins. The auditor receives the same question body, family guidance,
material access and answer operations. Family choice still grants no shell,
general file access, retrieval, execution or delegation.

The transport changes the presentation: concatenate the orientation and effective
family text with a pinned paragraph separator for the CLI system-prompt file;
map each tool's `input_schema` to MCP `inputSchema`, preserving the schema value
and descriptions; record the harness-assigned names such as
`mcp__stewart__record_account`. MCP text results carry the auditor reply and text
pages, including refusals, through the same role-specific core. Pin these
transformed bytes as well as the originals. They are not the Messages wire array.

The harness may add reminders, built-in instructions or managed policy that
Stewart cannot fully inspect. Accordingly, this profile promises exact capture
of what Stewart supplies and of the harness/MCP traffic it receives, **not** an
exhaustive capture of provider HTTP exchanges or every model-visible instruction.
Raw capture precedes decoding, including invalid and incomplete frames. Missing
harness output is an explicit gap, not an empty conversation. Raw private
captures have no automatic export: Stewart cannot search them for a subscription
secret it deliberately never holds.

Use an empty launch directory outside project instruction ancestry, an explicit
environment, an explicit MCP tool arrangement, no background tasks and
no fallback to a different model or adapter. Reject a changed effective tool,
plugin or routing inventory. These restrict the auditor's tool interface; the
trusted harness still has host access. This is not OS filesystem confinement or
proof that hidden managed instructions are absent. Native and Linux enforcement
must be demonstrated independently.

The credential boundary is structural: the unmodified harness owns the login
and secret; the adapter accepts no credential argument and cannot fall through
to Messages. It cannot identify the class of arbitrary opaque bytes someone
supplies separately to the API route. Recommend accepting this boundary, without
a token-prefix discriminator or a credential-store read.

**Decision A:** accept this explicitly observed harness profile for local
development. The alternative is to defer integration until exhaustive prompt,
provider-traffic and access evidence is available. The existing API and release
promises remain in force for their own route.

### B. Placement limits and honest usage, rather than API token allowances

Give this profile required cumulative `max_placements` and
`placement_timeout_seconds` settings. An illustrative commission of three
placements and 600 seconds per placement permits at most three starts, each
with a ten-minute supervisor deadline. These numbers are an example, not
defaults or authority to invoke Claude. Reserve a slot durably before spawning;
an uncertain launch consumes it, even if no final result arrives. Slots do not
reset on continuation. No automatic replacement start is made.

Count the deadline from spawning the harness, including startup and waiting,
using the host's elapsed-time clock. At expiry stop admitting authoring calls
and terminate the process group, with bounded escalation. Report observed
stopping and any overrun separately; a failed supervisor or host suspension
does not establish that provider activity ended at the deadline. A missing
stop observation blocks another placement, even when slots remain. Receipt,
status, re-entry and close distinguish starts used/reserved, deadlines and stop
observations. These are execution controls, not a provider token or money cap.

Keep a pinned harness turn cap and per-response output request as supporting
controls. Report their units as harness units and qualify their actual behavior
before relying on them. They do not recreate cumulative Messages input/output
allowances. Refuse API token-limit fields for this profile rather than ignoring
or translating them. A near-limit notice states the remaining placement time
and starts, never invented remaining tokens; it retains the audit-wide one-notice
allowance. The ordinary one-reminder policy also stays audit-wide.

Usage records retain each original reported field and its scope: session ID,
result/checkpoint identity, main-loop `usage`, per-model `modelUsage` and
reported harness turns. Do not add overlapping fields or successive cumulative
results. A fresh session has a separate series; within it, display the latest
valid checkpoint and any later unaccounted interval. Missing/malformed final
results and crash-zeroed totals leave that interval **unknown**. Earlier reports
remain reported, not promoted to complete totals. Assistant-message input counts
may be described as partial observations; they cannot recover missing output
or all internal calls. Estimated dollars are optional diagnostics, never bills
or a substitute allowance.

One placement uses one fresh harness session. After an interruption, continuation
uses the same audit ledger, a fresh session, the pinned continuation notice and
the existing re-entry tools. Unknown token usage alone does not prohibit it under
these placement limits; an uncertain effect is reconciled and the prior process
must be stopped first. Ordinary unsubmitted ending after the single reminder,
submission, close, damage or exhausted placement allowance still ends authoring.
Harness-native resume/fork/clear and automatic restart are excluded initially.

Harness-managed compaction within a placement does not grant a new slot, reset
the deadline or replace ledger state. Record exposed boundaries and summaries
without claiming to capture every internal exchange. Re-entry supplies recorded
state, not lost understanding. Keep the orientation's direction to use re-entry
after summarization; adapting the post-compaction notice needs its own pinned
text and a demonstrated delivery point. Qualification must exercise compaction
and the one-reminder interaction; until then, this path remains unqualified for
long-run iteration rather than being described as tested.

**Decision B:** use placement limits, reported/partial/unknown usage, and
continuation under those limits for this development profile. If cumulative
provider token ceilings must remain a requirement, the harness cannot presently
satisfy it; defer this adapter instead of inventing estimates.

### C. Checked installation, without claiming a pre-input startup gate

Preparation and commissioning stay local: neither launches Claude or logs in.
The manager uses the existing dedicated harness-owned login. A separately
commissioned synthetic check produces an inspectable receipt for a launch
profile. Bind it to the executable digest and signature receipt, platform,
model, environment allowlist/values, settings, hook and relay/writer identities,
tool-schema transformation and expected startup inventory. Retain the exact
synthetic prompt and result with it. Do not hash or copy the credential store.
The two-tool feasibility receipt does not validate the future service tool set.

`prepare` binds the selected profile and check receipt into the arrangement.
Before every start, verify the observable bindings and obtain a fresh allowlisted
authentication status: the selected directory, `claude.ai` and logged in. Require
`apiKeySource: "none"` separately at initialization. A failed or changed binding
refuses. Live commissioning must include
the non-model status invocation as well as any model session; installation and
check records do not confer spending authority. No periodic or automatic model
check is proposed. Recheck after an observable input changes or a startup mismatch;
show the check's date and scope without assigning an unsupported expiry period.

A prior check cannot freeze server-managed policy or prove the next session's
configuration. The native comparison saw `system/init` only after input. Validate
each actual startup and keep the MCP data/authoring gate closed until it matches,
but acknowledge that its system prompt and first question may already have
reached the harness/provider before a mismatch is reported. Do not describe this
as a guarantee that no audit content was exposed. A separate synthetic session
reduces uncertainty; it cannot certify a later session's hidden inputs.

Continue to require included usage only, with paid extra usage disabled. Stop
on quota rejection or observed overage enablement/use; do not switch models,
wait for a reset and restart, or fall back to API billing. Account settings are
the principal's declaration plus exposed harness observations, not independently
verified billing state.

**Decision C:** accept checked local bindings plus startup refusal with this
exposure limit. A hard guarantee of configuration validation before any audit
content would require another demonstrated mechanism; do not claim one from
the successful synthetic probe. There is no new live commission in this proposal.

### Implementation recommendation and verification obligations

Keep the core as sole writer and sole executor of auditor tools. `run` holds
the audit lock and a private Unix-domain socket; the harness starts a relay child
of the same gated Stewart binary. The child forwards bytes in both directions,
without opening the archive, parsing tool arguments, granting authority or
reconnecting. Use a private per-placement rendezvous, bind its handshake to that
placement and refuse another attachment. Possession of a path or matching UID
alone is not a claim of isolation from the ordinary owner.

The [offline Rust protocol check](docs/claude-code/RUNTIME-REFERENCE.md#offline-rust-protocol-check)
supports this narrow transport choice with the existing dependency graph. It
uses a tolerant outer JSON scanner and the unchanged strict argument decoder.
One blocking request/reply loop is insufficient: notification and cancellation
intake must remain responsive while execution is pending. Use bounded input
queues and one serialized core executor; prompt ping/cancellation handling does
not require a second audit writer. A fresh transport request ID is never assumed
to be a retry of an earlier logical action.

At publication, check the core's durable authoring boundary again. A hook is an
early refusal, not the authority that commits a mutation. On close, submission,
timeout or other authoring end, close the mutation gate before stopping the
harness. A completed effect followed by a lost reply stays completed; a later
cancellation cannot undo it. Retain exact attempts, refusal/result and effect
identity before relaying replies. Handler failure stops further execution; it
cannot turn into a successful empty result.

| Promise | Mechanism and failure policy | Evidence still needed in the adapter |
| --- | --- | --- |
| Captured material and answer semantics | Existing role-specific core and one durable writer; invalid/stale calls use existing refusals. | Actual MCP schemas, reads, edits, prepare/submit and empty-answer paths against independent witnesses. |
| Exact observed traffic | Capture input chunks before framing/decoding and response bytes before transmission; stop on capture failure. | Actual archive records, failed/partial writes, process death and owner/relay loss. The offline check is a transport prototype. |
| No late authoring | Check the authoritative log publication slot, including already-running handlers. | Barrier-controlled close versus pending mutation, plus firing and invariance cases. Prototype state flags do not establish the service boundary. |
| Session access and presentation | Pin observable configuration and expected tools; refuse mismatches; acknowledge opaque harness contributions. | Real adapter initialization and hooks, tool inventory and material non-disclosure before its gate opens, before/after compaction. |
| Usage and continuation | Preserve checkpoints and unknown intervals; reserve placement slots; never reset cumulative starts. | Fake crashes before/after results, counter reset/regression, lost reply with retained effect, fresh-session re-entry. |
| Stop and ownership | Hold the writer lock, watch close, terminate/observe the harness and descendants; uncertain stopping blocks restart. | Native child/group checks and separate Linux identity/lock controls, including owner killed while relay/handler is active. |
| Subscription route | Dedicated login, explicit environment, no credential argument or fallback. | Missing/conflicting authentication controls and actual launch routing, separately for each host. No classification claim for arbitrary API credential bytes. |

Update CONTRACTS, INTERFACE, QUESTION-FORMS and ACCEPTANCE after A–C are decided,
before exposing a runtime selector. Use a versioned development arrangement and
runtime-specific limit/usage records; do not reinterpret old API commissions or
rewrite receipts. The API's turn/token limits, exact system/tool arrays, raw HTTP
captures and signed provider compaction remain its own contract. Profile-specific
orientation, reminder delivery and near-limit text must be pinned and checked
against the specifications, including an independent driver author when needed.

**Ready for the principal:** decisions A–C above. Then implement the gated core
boundary and fake-runtime controls before commissioning any real adapter run.
No dependency addition or SDK helper is recommended. Linux qualification remains
the separately scheduled container work.

Keep `.tmp/claude-code-probe/first-live-review.log`,
`.tmp/claude-code-probe/shared-clock-*.log` and
`.tmp/claude-code-probe/probe-02-*.log` through review of the static plugin
findings, observer clock comparison and offline recorder changes. The frozen
inputs in `.scratch/claude-code-probe-01` own what executed in the stopped run;
the successful second commission is retained in `.scratch/claude-code-probe-02`.
Its `inputs/proposal.md` and frozen code own the executed scope. Both run states
and all original captures stay unchanged through review.
Keep `.tmp/claude-code-contract/` check outputs through review of this proposal
and its offline prototype, including the corrected initial build failure.

## 2. Narrow implementation after the decisions

- [ ] Align CONTRACTS, INTERFACE and the applicable acceptance requirements with
  the selected adapter promises before implementing them. Preserve the common
  audit semantics and the evidence/judgment boundary above.
- [ ] Connect one auditor session to the accepted commission, material access,
  recording/revision tools, explicit submission, delivery and close. Keep audit
  semantics in Rust and isolate the chosen runtime mechanism behind that core.
- [ ] Enforce authority over recorded work at durable publication: reject a late
  mutation after authoring closes, including from an already-running handler.
  A tool-entry hook alone is insufficient. Implement runtime interruption and
  termination as distinct responsibilities under the selected contract.
- [ ] Implement the chosen re-entry, continuation and accounting failure policies;
  preserve uncertain endings without fabricating consumption or completion.
  Supply useful setup, help and failure messages for the chosen installation.

**Done when:** the narrow path and failure policies pass the applicable
[DEVELOPMENT checks](development/DEVELOPMENT.md#what-to-run-for-what-you-changed), including
offline controls. Real harness guarantees remain unqualified until demonstrated.

## 3. Qualify the selected guarantees

Under a bounded commission, exercise the actual auditor tool surface,
compaction/re-entry, accounting, interruption, submission, delivery and close.
Verify effective tools, instructions, authentication and access before and after
compaction, including host and server-managed configuration. Settings alone do
not establish enforcement.

Use an independent witness, firing controls, differing cases and invariance
cases under [ACCEPTANCE](ACCEPTANCE.md#the-real-model-conformance-tier). Pin
SDK/CLI versions, effective configuration, model, authentication route and
binaries. Resolve any mismatch between that gate and the proposed runtime during
the contract decision. Do not transfer API results into a harness qualification
claim, or results under one credential route into a claim about another. Model
answer quality is not the gate.

Complete this plan when the selected integration has a reviewed qualification
outcome and failures or unexercised work have explicit dispositions. Move enduring
contracts and operating instructions into their owning documentation and keep
results with their evidence, then delete the plan.
