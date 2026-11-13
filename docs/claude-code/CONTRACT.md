# Claude Code development runtime contract

This is the decided contract for the default-off `claude-code` development
runtime. The principal approved its observation, limits and startup boundaries
on 2026-11-10. It does not change the distributed Messages API contract.
The gated adapter is implemented and has passed native offline service checks
and Linux container acceptance using a synthetic harness. The
[qualification record](../../apparatus/qualified.md) identifies the exact
source and binaries covered. Those checks exercise the Rust core, custody,
submission, continuation and process controls; they do
not establish real-Claude service conformance. The
[independent driver's coverage](../../apparatus/driver/CLAUDE-CODE.md) states
which synthetic comparisons it exercises, including relay loss, cancellation,
usage across placements and compaction, and which it does not; unit controls
are separate evidence.

The common [custody and audit contracts](../../CONTRACTS.md),
[interface](../INTERFACE.md) and [question families](../QUESTION-FORMS.md) apply.
This document owns the runtime-specific differences. Stewart retains one writer,
one ledger, exact targets, explicit submission, verified delivery and close.
A session ending is never an auditor submission.

The distributed binary excludes this adapter at build time and carries no
switch for it; a source build includes it with the `claude-code` feature. Keep
this runtime in line with the Messages path wherever the transport allows, so
that what is learned about the manager's interface on one holds on the other.
Linux x86_64 and aarch64 are the platforms Stewart supports. Apple-silicon
macOS is a build target without a support or qualification claim.

Runtime-specific contracts, schemas and technical explanations live in this
directory. Root documents describe excluded adapters and other authentication
options without naming this runtime, linking its contract or explaining how to
enable it. The build, crate and apparatus guides carry what building and
checking require; there is no separate enablement or conversion guide. Code
and data at the repository root have no special placement rule.

## Evidence owed

Offline controls must exercise the actual core through MCP: exact traffic,
positive effects, denial and invariance, publication after closure, startup
mismatch, owner/relay loss, unknown usage, cumulative placement limits and
continuation. An independent author derives driver cases from this contract.
Native macOS checks remain development checks. Linux qualification applies to
the recorded synthetic comparisons; separately commissioned real-harness
compaction, submission and stopping comparisons remain necessary for the claims
they exercise. Messages API results do not qualify the harness profile. The common
[rules every check follows](../../ACCEPTANCE.md#rules-every-check-follows) apply.

## Arrangement and observation

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
supplies separately to the API route. The boundary uses neither
a token-prefix discriminator nor a credential-store read.


## Limits, usage and continuation

This profile requires cumulative `max_placements` and per-placement
`placement_timeout_seconds` settings. An illustrative commission of three
placements and 600 seconds per placement permits at most three starts, each
with a ten-minute supervisor deadline. These numbers are an example, not
defaults or authority to invoke Claude. Reserve a slot durably before spawning;
an uncertain launch consumes it, even if no final result arrives. Slots do not
reset on continuation. No automatic replacement start is made.

Count the deadline from the start reservation, including authentication, startup and waiting,
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
after summarization. The runtime text below pins the post-compaction notice;
its delivery point still needs demonstration with the real harness. Qualification must exercise compaction
and the one-reminder interaction; until then, this path remains unqualified for
long-run iteration rather than being described as tested.


## Installation and startup validation

Preparation and commissioning stay local: neither launches Claude or logs in.
The manager uses the existing dedicated harness-owned login. A separately
commissioned synthetic check produces an inspectable receipt for a launch
profile. Bind it to the executable digest and signature receipt, platform,
model, tool-schema transformation, expected startup inventory and the
[launch surface](#launch-surface): the invocation, settings, hook and relay
arrangement, environment names and values, supporting controls, handshake,
input shape and pinned texts that Stewart supplies to the harness. Retain the
exact synthetic prompt and result with it. Do not hash or copy the credential
store. The two-tool feasibility receipt does not validate the full service tool
set. Profile validation, installation verification and assembly from separately
reviewed evidence are implemented in the [profile apparatus](../../apparatus/claude-code/README.md).
The independent fixture exercises actual helpers offline. A bounded invocation
library and independent observer have passed native controls. Their integrated
controller and explicit review workflow have passed native synthetic integration
rehearsals with the actual helpers, independent traffic witnesses and firing
failure controls. A reviewed real-harness check and subsequent service comparison
are still needed.
Synthetic driver attestations exercise validation and are not real-harness
commissioning evidence.

The check is bound to what the harness is given, not to the `stewart` binary
that gives it. A rebuild that leaves the launch surface unchanged keeps its
check; a build that changes any surface value refuses that profile until the
changed surface has its own check. This binding concerns the profile only. An
audit stays bound to the binary that created it under the common
[one-writer rule](../../CONTRACTS.md#versions-and-legacy-obligations).

`prepare` binds the selected profile, check receipt and launch surface into the
arrangement. Before every start, verify the observable bindings and obtain a
fresh allowlisted authentication status: the selected directory, `claude.ai` and
logged in. Require
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

## Development input and preparation schema

There is one question version, `stewart: question/1`, in the existing front
matter grammar. In the gated build a question selects this runtime by naming
`runtime-profile`; a question without it is a Messages API question, read
exactly as the common interface specifies. Common family, model, destination,
guidance, effort, inquiry and varies fields retain their meanings. A runtime
question replaces all three `limit-*` fields with:

| Field | Required value |
| --- | --- |
| `runtime-profile` | Absolute path to the nonsecret profile JSON below. |
| `max-placements` | Integer 1–10,000, without leading zeros. |
| `placement-timeout-seconds` | Integer 1–86,400, without leading zeros. |

With `runtime-profile`, both placement fields are required: a missing one is a
`setting_missing` defect naming its key, as for any missing required key, and a
value outside the table is `setting_invalid`. Each `limit-*` field is then a
`setting_invalid` defect naming its key, even if its value is valid. Without
`runtime-profile`, `max-placements` and `placement-timeout-seconds` are each a
`setting_invalid` defect naming the key. Any other `stewart` value is refused
as the common interface refuses it, with a diagnostic naming that value and
`question/1`; no second version is read. The featureless build knows none of
the three fields and refuses each as an unknown key. Question body bytes and
material selection do not change.

The scaffold that `new` writes is the common one, byte for byte, in both
builds. The gated build's help says how to turn it into a runtime question.

## Help, run requirements and presentation

Help text, `run_needs`, summaries and other human output are prose, checked for
presence and relevance as the common interface treats such text, not for exact
bytes. This section states the facts each must carry.

The gated build has one more help topic, `stewart help runtime`. Its overview
lists `runtime` after the common topics on the topics line, and the
unknown-topic diagnostic lists it too. The usage synopsis is the common one in
both builds. The overview opens with a build notice that identifies the
development build and points to `stewart help runtime`, not to a path in a
source tree. The featureless build has neither the topic nor the notice, and
`stewart help runtime` is an unknown topic there. The topic covers:

- the scaffold change: keep `stewart: question/1` and replace the three
  `limit-*` lines with `runtime-profile`, `max-placements` and
  `placement-timeout-seconds`, with their meanings and bounds, and that the
  presence of `runtime-profile` selects the runtime;
- what the profile is: a nonsecret JSON file with its schema identifier that
  pins the harness executable, its directories, the installation attestation
  and a check naming the model, tools and launch surface, and that `prepare`
  captures it and launches nothing;
- how to learn the launch surface digest a check must name from a refused
  `prepare`;
- that login stays in the harness, with paid extra usage disabled, and that
  `run` refuses `--key-fd` and credential environment variables and never falls
  back to the Messages API;
- that `run` starts one placement under the placement deadline, uses one of
  the placement starts each time, stays in the foreground, and may leave usage
  partial or unknown.

`run_needs`, in commission and receipt replies for a runtime audit, is an array
of four strings, in this order:

1. explicit authority for this bounded placement, with no automatic restart;
2. the pinned harness installation and its own subscription login, with paid
   extra usage disabled;
3. no credential argument or credential environment variable, and no API
   fallback;
4. that `run` stays in the foreground until the placement ends or reaches its
   deadline, that callers with command timeouts should start it in the
   background, and that usage may remain partial or unknown.

JSON replies are unchanged by the following; they keep the exact captured
profile text and every member the Messages path has, including
`provider_url_override` and `provider_proxy`, which are null for a runtime
audit.

- Human `prepare` and `receipt` output shows the runtime's profile by its path
  and by the SHA-256 of its captured text, the arrangement's `profile_sha256`.
  It does not print the profile text.
- The human summary of `status`, `run` and `close`, which is also
  `data.summary`, states the placement starts used, allowed and remaining
  together with the placement timeout in seconds.
- Its usage and stopping statements agree in number with their counts: one
  placement takes the singular (`1 placement has`, `1 placement`); zero,
  several and unknown counts take the plural (`0 placements have`,
  `2 placements`).

The profile is strict control JSON, at most 64 KiB, read through no-follow
directory/file descriptors. It has exactly `schema`, `launch`, `installation`
and `check`. Its schema is `stewart.claude-code.profile/2`. Any other profile
schema identifier refuses, with a diagnostic naming it and the identifier this
binary reads; there is no reader for another form.

| Object | Exact members |
| --- | --- |
| `launch` | `executable` (absolute regular file path), `sha256` (binary digest), `version` (pinned CLI version), `platform` (`macos-aarch64`, `linux-aarch64` or `linux-x86_64`), `config_directory`, `home`, `temporary_directory` (absolute directory paths). |
| `installation` | `manifest_sha256`, `signer`, `binary_sha256`. The signer is `31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE`; binary digest equals `launch.sha256`. |
| `check` | `surface_sha256`, `launch_sha256`, `tools_sha256`, `model`, `checked_at`, `evidence_sha256`, `outcome` (exactly `observed`). |

SHA-256 values are lowercase 64-digit hexadecimal strings. `launch_sha256`
hashes the original JSON value bytes of `launch`, including their internal
whitespace. `tools_sha256` hashes the compact MCP tool array: pinned family
tool order, each object ordered `name`, `description`, `inputSchema`, with the
original schema value bytes preserved. `surface_sha256` hashes the
[launch surface](#launch-surface) document the check session exercised; it must
equal the digest of the surface the running binary supplies. Model and platform
must match. `checked_at` is a UTF-8 string identifying the check's
date; it is an attributed label, not a parsed timestamp or an expiry check.
`evidence_sha256` identifies its independently reviewed record. The embedded
installation/check entries are attributed attestations; reading and hashing
them does not redo signature verification or reproduce a live check. They confer
no permission to invoke Claude.

`prepare` checks these bindings and hashes the executable without executing it.
It computes the running binary's own launch surface and refuses a profile whose
`check.surface_sha256` differs. A profile that `prepare` cannot accept refuses
with reason `runtime_profile_invalid` and launches nothing. Every such refusal
carries `data.surface`, with exactly `schema` (`stewart.claude-code.surface/1`),
`sha256` (the digest this binary requires a check to name) and `document` (the
surface document as a JSON value, its bytes exactly those the digest covers). A
surface mismatch also states both digests in its message. A manager therefore
learns the required digest and the exact document from a refusal alone.

The source profile's exact UTF-8 text is captured in prepared settings as
`runtime: {kind:"claude-code/1",profile_path,profile}`. Its `limits` object is
exactly `{max_placements,placement_timeout_seconds}`. Subsequent receipt readback
uses captured bytes, never a changed live profile. Before any launch, `run`
verifies the executable and check bindings again, including that the pinned
surface is the one the running binary supplies; a difference refuses with
`runtime_profile_invalid`, naming both digests. The runtime never opens the
named credential directory.

The arrangement schema is `stewart.claude-code.arrangement/2`. Its exact members
are `schema`, `family`, `model`, `guidance`, `orientation`, `system`,
`system_prompt`, `tools`, `mcp_tools`, `runtime`, `profile_sha256`, `surface`,
`surface_sha256`, `effort`, `limits`, `harness_max_turns`,
`harness_max_output_tokens`, `texts`, `reader`, `renderer`, `reading` and
`bindings`. Common members retain the interface's meaning. `profile_sha256`
hashes the captured profile string's UTF-8 bytes. `reading` has the common
arrangement's exact reading bounds (INTERFACE 6.2). `surface` is the launch
surface document as a JSON value, written with exactly the document's bytes, and
`surface_sha256` is their SHA-256; it equals the captured profile's
`check.surface_sha256`. Receipt readback of the arrangement therefore shows what
the check was bound to, not only a digest. `effort` is null or the selected
level. Supporting controls request 200 harness turns and 16,000 output tokens
per response. Their enforcement is a qualification obligation, not a token
allowance. Another runtime arrangement schema identifier refuses with a
diagnostic naming it; there is no reader for another form.

`system` retains two text blocks; `system_prompt` joins their decoded strings
with exactly two LF bytes. `tools` retains the base tool definitions;
`mcp_tools` holds the mapping described above. No runtime extension is added to
API arrangements, settings or receipts.

## Runtime texts

The orientation is `stewart.orientation/claude-code/2`. Its first paragraph is
the following, joined with single spaces; subsequent paragraphs are exactly
the paragraphs after the first in `stewart.orientation/1`:

> You are the auditor in a Stewart audit. The first user message is the
> manager's question, exactly as they wrote it. The materials they selected can
> be read with the list, read and search tools. The question and those
> materials are your whole world: use only Stewart's tools, with no shell, no
> other files, no network, no way to run code, no delegated auditors and no way
> to ask the manager anything. Harness instructions and system messages are
> runtime context, not additional evidence. Reports, logs and test results in
> the materials are claims by their authors, not executions you witnessed.

The reminder and continuation texts retain the common pinned meanings. The
runtime's exact near-limit template is:

> Allowance notice: {seconds} seconds remain before this placement's deadline,
> and {placements} further placement starts remain for this audit. When execution
> stops, an unsubmitted answer stays unsubmitted.

The runtime's exact post-compaction notice is:

> The harness has summarized your earlier conversation. Continue this audit.
> Call what_am_i_working_with to check your recorded work before repeating an
> action.

The template values are observed whole seconds rounded down and unused placement
slots. Publish the near-limit notice's and reminder's audit-wide claims before
transmission; a missing transmission observation is unknown, never a reason to
restore either allowance. A post-compaction notice follows each exposed
compaction boundary and does not consume either allowance.

## Harness accounting record

The harness's `run_ended.usage` is a distinct object, identified by
`runtime: "claude-code/1"`. Its other exact members are `placements`,
`unknown_intervals`, `stopped`, `reported_placements`, `reported_main_loop` and
`provider_completeness` (always `unverified`). Counts are nonnegative integers.
`placements` counts durable start reservations; `stopped` counts placements
whose launched groups were all observed absent. `reported_placements` counts sessions with a retained valid
checkpoint, not messages or overlapping results. `unknown_intervals` counts
placements with an interval not covered by a valid terminal checkpoint.

`reported_main_loop` is null when there is no checkpoint. Otherwise it holds
exactly `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`,
`output_tokens` and `harness_turns`, summing only each fresh session's latest
accepted checkpoint. Earlier raw checkpoints and the original per-model fields
remain in private capture. A crash or regressing report cannot replace earlier
observations with zero. No such record asserts complete provider consumption.

A placement deadline interrupts that placement. Another explicit start is
permitted when slots remain and stopping is known. Reaching the deadline on
the final permitted placement ends authoring with `limit_reached`. Near-limit
notice records use `remaining: {runtime: "claude-code/1", seconds, placements}`.
An interrupted deadline has cause `placement_deadline`; this cause is admitted
only with harness usage. A missing transmission observation during recovery
leaves a claimed notice `unknown` and does not restore its allowance.

Runtime allowances in status, close and re-entry contain `runtime`,
`placements: {used,limit,remaining}`, `placement_timeout_seconds` and `usage`
in the shape above. They never show API token allowances. Unknown stopping or
damaged records keep their explicit diagnostics and block a further start.

## Development wire and process contract

Harness `run_started` keeps the common placement, arrangement and observation
fields, sets `provider` to null, and adds
`runtime: {kind: "claude-code/1", profile_sha256, placement_timeout_seconds}`.
API records retain their exact shape. Before reserving another start, an
unavailable or non-absent prior process
observation refuses `runtime_stop_unknown`; no authentication or model process
is launched. Close also refuses `runtime_stop_unknown` before reconciliation,
sealing or delivery when stopping cannot be established, even with the active
lock free. Following the common [close ordering](../INTERFACE.md#58-close),
`close_requested` may already have been recorded before this refusal.
`--key-fd` or any presence (including an empty value) of
`ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` refuses
`runtime_credential_forbidden` before reading credentials or launching.
At tool publication, including confirmed submission, the runtime gate
refuses `placement_stopped` if cancellation, stopping or the deadline won before
the log link. Payload or stage candidates may remain; they are not answer
entries or a seal. Cancellation of one call leaves the placement available for later calls.
A global signal, close or deadline derives its placement ending from that
actual stopping condition; it is not an archive-write failure. A deadline
interrupts with `placement_deadline` when starts remain, and ends
`limit_reached` only on the last allowed placement.

`orientation` is the string identifier above. `texts` has exactly the four
string members `reminder`, `near_limit`, `continuation` and `compacted`.
`bindings` has exactly the digest members `question_body_sha256` and
`material_index_sha256`, with the common arrangement meanings.

After reserving a placement, run launches one `auth status` check. Its output
is held privately in memory; only `loggedIn`, `authMethod` and
`configDirectory` are retained. They must be `true`, `claude.ai` and the pinned
configuration directory, respectively, with exit status zero. Failed checks
consume the reserved start and launch no model. Raw authentication output is
never copied into the archive or a diagnostic.

The model invocation is `-p --input-format stream-json --output-format
stream-json --verbose --restricted --tools '' --setting-sources '' --settings
PATH --strict-mcp-config --mcp-config PATH --allowedTools NAMES --permission-mode
dontAsk --permission-prompts none --system-prompt-file PATH --model MODEL
--max-turns 200 --no-session-persistence`, plus `--effort LEVEL` when selected.
`NAMES` is every pinned tool prefixed `mcp__stewart__`, one argument per tool in
the pinned family order. Settings select `forceLoginMethod: claudeai`,
`fastMode: false`, `fallbackModel: []`, and a `PreToolUse` command hook matching
`*`, with a five-second timeout. The hook's command is the writer's path in
single quotes (each `'` in the path written `'\''`), `__stewart-cc-hook` and
`'h'`, separated by single spaces. MCP config has exactly one server, `stewart`,
with `type: stdio`, the Stewart writer as `command`, and the arguments
`__stewart-cc-relay` and `m`. The working directory is a fresh, private
directory outside the submission, archive and project ancestry. It holds the
three supplied files `settings.json`, `mcp.json` and `system.txt`, which the
`PATH` arguments name absolutely, and the two private sockets `m` and `h`, which
the relay and hook name relatively.

The hook helper prints one LF-terminated JSON object. It admits a call with `{}`
when the tool is a pinned prefixed name, startup has passed and the placement
still admits calls. Otherwise it prints the denial object given as
`hook_replies.deny` in the [launch surface](#launch-surface).

The child environment is rebuilt, with nothing inherited. It is exactly the
fifteen names and values that the [launch surface](#launch-surface) lists as
its `environment` member: fixed `PATH` and `LANG`, eight disable controls,
`CLAUDE_CODE_MAX_RETRIES` `0`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS` `16000`, and
`HOME`, `TMPDIR` and `CLAUDE_CONFIG_DIR` from the profile's `home`,
`temporary_directory` and `config_directory`. The authentication check uses the same environment and
working directory. No caller environment, credential, endpoint, proxy or agent
injection is forwarded.

Input is LF-delimited JSON. Each supplied message has `type: user`,
`session_id: ""`, `parent_tool_use_id: null`, and
`message: {role: user, content: TEXT}`. The first content is the exact question
body; continuation and notices are separate inputs. MCP uses LF-delimited
JSON-RPC 2.0 and protocol version `2025-11-25`. The initialization result has
exactly `protocolVersion`, `capabilities: {tools: {}}` and
`serverInfo: {name: stewart, version: "1"}`. Initialization, initialized
notification, ping, fixed tools/list, tools/call and cancellation are supported.
Unknown methods return method-not-found. Notifications never execute tools or
receive replies. IDs are strings or integers, unique within a placement;
duplicates are refused, including a repeated ID with different arguments.
Unknown metadata is tolerated; repeated interpreted members are refused.
Interpreted strings require well-formed Unicode without NUL. Core invocation
IDs are `mcp-C` for call number C; the original JSON-RPC ID remains in the
request capture and response, and determines cancellation and duplicate checks.
Tool arguments retain their original bytes for strict core validation.

After startup validation, tool calls execute one at a time in arrival order.
A call arriving behind an unfinished call waits; it is not refused merely
because another call is pending. At most 32 calls may wait, with at most
16 MiB of their original request frames in total, including each LF delimiter;
the executing call is excluded from both bounds. A call exceeding either
waiting bound receives JSON-RPC error `-32000`, naming the queue limit, with
no tool effect. Its request ID remains used. Earlier accepted calls keep their
order and are not discarded.

Cancellation applies to waiting and executing calls. A cancellation observed
before a waiting call starts prevents its execution; its ordinary MCP tool
reply is a `placement_stopped` refusal in its ordered turn. Cancellation during
execution retains the publication rule above. Cancellation of an unknown or
completed ID changes nothing, and cancelling one call does not cancel its
siblings. Control requests and cancellation notifications remain serviceable
while a tool executes. Accepted calls retain their request and result records;
on placement stopping, waiting calls never execute and are recorded as
`placement_stopped` when the archive remains writable. Shutdown does not promise
delivery of their replies after the transport closes.

JSON-RPC envelopes and errors use the transport's number grammar, including
negative error codes. An error whose request ID cannot be determined uses
JSON null for `id`; a well-formed notification still receives no reply. The
unsigned-integer rule for Stewart control arguments
does not apply to them. After confirmed submission, the runtime captures and
attempts to send the MCP tool response, then stops the harness without another
input. The Messages API's recorded-only submit response remains unchanged.
Frames are bounded at 8 MiB; core arguments remain bounded at 4 MiB.
Total observed capture is bounded at 256 MiB per placement. Crossing a transport
frame or capture bound stops execution and reports the incomplete interval; it never discards earlier
captures or turns truncation into a complete conversation.

The startup event must report `type: system`, `subtype: init`, the profile's
`claude_code_version`, commissioned `model`, `apiKeySource: none`,
`permissionMode: dontAsk`, the exact prefixed `tools` inventory and sole
`mcp_servers` entry `{name: stewart, status: connected}` (other metadata may
be present). `plugins` must contain exactly the three reviewed names
`cc-plugin-agents-md`, `cc-plugin-privacy`, `cc-plugin-plugin-authoring`, each
with `path: builtin` and `source: NAME@builtin`. Nonempty `plugin_errors` or
`mcp_server_errors` stop the placement. No material-bearing tool executes
before this event passes. Input may already have reached the harness.

Assistant messages must name the commissioned model or `<synthetic>` and may
name only the prefixed tools. Delegated sessions, background task starts,
plugin installation, API retries and rejected quota or enabled/in-use overage
stop execution. A `system/compact_boundary` event is retained and followed by
the pinned compaction notice. A `result` may carry `usage` with the four token
counts above and `num_turns`. Those fields are a cumulative main-loop
checkpoint. Counts must not regress. Missing, malformed, regressing or error
results retain earlier reports and mark the uncovered interval unknown.

Each launch has a supervisor group. Its ID is durably written to
`runs/N/process-auth.json` or `process-model.json` before the owner permits the
child to start. Each object has exactly `schema: stewart.claude-code.process/1`,
positive integer `group`, and `role: auth` or `model`. The supervisor watches
owner EOF and a monotonic deadline independently. Shutdown sends TERM, waits
two seconds, then KILLs the whole group, including the supervisor. This is
cooperative process-group control, not confinement against a hostile executable
that escapes its group. Recovery observes group absence; it never signals a
potentially reused group ID. Unknown stopping blocks a further start and close
cleanup even when the active lock is free.

`runtime-usage-K.json` files are append-only strict usage checkpoints in the
shape above. `runtime-stop.json` reports `elapsed_ms`, `deadline_ms` and
`groups_gone`; true means every launched group was observed absent. Raw
chunks in `runs/R/` are named `runtime-N-CHANNEL.bin`. `N` is an unpadded
positive decimal integer, starting at 1 and increasing across all channels in
that placement's observer order. Channels are `stdout`, `stderr`, `mcp`,
`mcp-out`, `input`, `hook-in` and `hook-out`. For a streaming channel, concatenate
its chunks in numeric `N` order to recover the observed byte stream; chunk
boundaries need not match frame boundaries. Incoming bytes are retained before
parsing; outgoing bytes are retained before transmission and do not by
themselves prove transmission succeeded. Failed captures leave an explicit gap.
`call-C.json` holds the original MCP request. Common `tool_result` records
retain the actual core reply; `request` and `attempt` are 1 and `block` is C
for this single MCP connection. These are transport coordinates, not HTTP
requests. Harness `run_ended.requests` and `attempts` are zero. No harness
accounting record is interpreted as an API charge.

## Launch surface

The launch surface is everything Stewart supplies to the harness that is the
same in every audit and is not already bound by the profile's `launch_sha256`,
`tools_sha256` or `model`. A profile's `check.surface_sha256` names it. The
surface is a property of a build: two builds that supply the same values have
the same surface wherever they are installed, and a build that changes any
value below has a different one.

The surface document is `stewart.claude-code.surface/1`. It is one JSON object
in the compact form used for `tools_sha256`: no whitespace between tokens,
members in the order given here, integers in decimal, and no trailing LF. In
strings only `"`, `\` and control characters are escaped; the one escape the
current document contains is `\n` for each LF in `system_prompt`. Every byte is
ASCII. `surface_sha256` is the SHA-256 of these bytes.

A value that differs between launches appears as a placeholder: the literal
string below, braces included. Placeholders are never filled in the document.

| Placeholder | Stands for |
| --- | --- |
| `{workspace}` | The placement's private working directory, an absolute path. |
| `{writer}` | The Stewart writer's absolute path. In the hook command a launch writes it with the shell quoting given in the [wire contract](#development-wire-and-process-contract). |
| `{home}`, `{temporary_directory}`, `{config_directory}` | The profile's `launch` members of those names. |
| `{model}` | The commissioned model. |
| `{effort}` | The selected effort level. |
| `{tool}` | One pinned tool name. The single argument `mcp__stewart__{tool}` stands for one argument per pinned tool, in the pinned family order. |
| `{orientation}`, `{guidance}` | The orientation text and the effective family guidance text. |
| `{text}` | The content of one supplied input message. |

The members, in order:

| Member | Value |
| --- | --- |
| `schema` | `stewart.claude-code.surface/1`. |
| `working_directory` | `{workspace}`: the authentication check and the model session both run there. |
| `auth_argv` | The authentication check's arguments: `auth`, `status`. |
| `model_argv` | The model invocation's arguments in order, as strings, without the effort arguments. The two empty arguments are empty strings, each `PATH` is `{workspace}/` followed by its file name, `NAMES` is the single `{tool}` argument, `MODEL` is `{model}` and the turn cap is the string `200`. |
| `effort_argv` | `--effort`, `{effort}`: appended to `model_argv` when the question selects an effort. |
| `settings` | The settings file: `forceLoginMethod`, `fastMode`, `fallbackModel`, then `hooks` with the one `PreToolUse` entry of `matcher` and `hooks`, whose one hook has `type`, `command` and integer `timeout`. The command is `'{writer}' __stewart-cc-hook 'h'`. |
| `mcp_config` | The MCP configuration file: `mcpServers` with the one server `stewart` of `type`, `command` (`{writer}`) and `args`. |
| `environment` | The whole child environment as an object of string values, in this order: `PATH` `/usr/bin:/bin:/usr/sbin:/sbin`; `LANG` `en_US.UTF-8`; `DISABLE_UPDATES`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, `CLAUDE_CODE_DISABLE_AUTO_MEMORY`, `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`, `CLAUDE_CODE_DISABLE_AGENT_VIEW` and `CLAUDE_CODE_DISABLE_FAST_MODE`, each `1`; `ENABLE_CLAUDEAI_MCP_SERVERS` and `ENABLE_TOOL_SEARCH`, each `false`; `CLAUDE_CODE_MAX_RETRIES` `0`; `CLAUDE_CODE_MAX_OUTPUT_TOKENS` `16000`; `HOME` `{home}`; `TMPDIR` `{temporary_directory}`; `CLAUDE_CONFIG_DIR` `{config_directory}`. |
| `controls` | The integers `harness_max_turns` 200 and `harness_max_output_tokens` 16000. |
| `system_prompt` | The system-prompt file's construction: `{orientation}`, two LF bytes, `{guidance}`. |
| `input` | One supplied input message, with `{text}` as its content. |
| `mcp_initialize` | The MCP initialization result. |
| `hook_replies` | `allow`, the empty object, then `deny`: `hookSpecificOutput` with `hookEventName` `PreToolUse`, `permissionDecision` `deny` and `permissionDecisionReason` `Tool is outside the validated active commission.` |
| `texts` | `orientation`, the orientation identifier, then `orientation_sha256`, `reminder_sha256`, `near_limit_sha256`, `continuation_sha256` and `compacted_sha256`. Each digest covers the pinned text's UTF-8 bytes under the [joining convention of QUESTION-FORMS](../QUESTION-FORMS.md), without a trailing LF. The orientation is the [runtime orientation](#runtime-texts) in full. The reminder and continuation are the common texts of QUESTION-FORMS. The near-limit text is this runtime's template with `{seconds}` and `{placements}` unfilled, and the compacted text is this runtime's post-compaction notice. |

The following is the complete current document and owns its literal values.
Join the block's lines without their line endings to obtain the exact bytes; no
line begins or ends with a space, and no break falls inside a string.

```json
{"schema":"stewart.claude-code.surface/1",
"working_directory":"{workspace}",
"auth_argv":["auth","status"],
"model_argv":["-p","--input-format","stream-json","--output-format","stream-json",
"--verbose","--restricted","--tools","","--setting-sources","","--settings",
"{workspace}/settings.json","--strict-mcp-config","--mcp-config","{workspace}/mcp.json",
"--allowedTools","mcp__stewart__{tool}","--permission-mode","dontAsk",
"--permission-prompts","none","--system-prompt-file","{workspace}/system.txt","--model",
"{model}","--max-turns","200","--no-session-persistence"],
"effort_argv":["--effort","{effort}"],
"settings":{"forceLoginMethod":"claudeai","fastMode":false,"fallbackModel":[],
"hooks":{"PreToolUse":[{"matcher":"*","hooks":[{"type":"command",
"command":"'{writer}' __stewart-cc-hook 'h'","timeout":5}]}]}},
"mcp_config":{"mcpServers":{"stewart":{"type":"stdio","command":"{writer}",
"args":["__stewart-cc-relay","m"]}}},
"environment":{"PATH":"/usr/bin:/bin:/usr/sbin:/sbin","LANG":"en_US.UTF-8",
"DISABLE_UPDATES":"1","CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC":"1",
"CLAUDE_CODE_DISABLE_AUTO_MEMORY":"1","CLAUDE_CODE_DISABLE_BACKGROUND_TASKS":"1",
"CLAUDE_CODE_DISABLE_AGENT_VIEW":"1","CLAUDE_CODE_DISABLE_FAST_MODE":"1",
"ENABLE_CLAUDEAI_MCP_SERVERS":"false","ENABLE_TOOL_SEARCH":"false",
"CLAUDE_CODE_MAX_RETRIES":"0","CLAUDE_CODE_MAX_OUTPUT_TOKENS":"16000","HOME":"{home}",
"TMPDIR":"{temporary_directory}","CLAUDE_CONFIG_DIR":"{config_directory}"},
"controls":{"harness_max_turns":200,"harness_max_output_tokens":16000},
"system_prompt":"{orientation}\n\n{guidance}",
"input":{"type":"user","session_id":"","parent_tool_use_id":null,
"message":{"role":"user","content":"{text}"}},
"mcp_initialize":{"protocolVersion":"2025-11-25","capabilities":{"tools":{}},
"serverInfo":{"name":"stewart","version":"1"}},
"hook_replies":{"allow":{},"deny":{"hookSpecificOutput":{"hookEventName":"PreToolUse",
"permissionDecision":"deny",
"permissionDecisionReason":"Tool is outside the validated active commission."}}},
"texts":{"orientation":"stewart.orientation/claude-code/2",
"orientation_sha256":"ce0357e115a83092ebeb4b2e9ae34cd455120df26565d74bb5776c91746ed2bd",
"reminder_sha256":"a863022bc2ca6682a1162aca9b402293efd296d2bc24669574d0308e193dcdda",
"near_limit_sha256":"14dc131ac9bd703c9f8d945db4e78a98a2418b5b27d6535a4870e6ddf5a437d0",
"continuation_sha256":"0cced8b9aae42fb09e5c321e64a44037413d0bd244b0e4d2e855e7d3ce850ac0",
"compacted_sha256":"976166dc9bf95de048376eedbe5b05e78192eebad57c97032b82f173f5059e17"}}
```

Its SHA-256 is
`e8182ecf0009ee1f3889b8e89902bec5eaef34c8bf4c079c2b78c34684780db5`.

Values that vary by audit are pinned by the arrangement and are not part of the
surface: the question body, the effective guidance, the materials, the limits
and the selected effort. The family guidance is such a value even when it is a
built-in text, because the family is the manager's choice. The executable, the
profile's directories, the tool definitions and the model keep their own
bindings. Tool results and JSON-RPC errors are behavior, exercised by cases
rather than named by a digest. Supervision, capture and accounting are Stewart's
own and are not supplied to the harness.
