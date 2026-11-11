# Claude Code development runtime contract

This is the decided contract for the default-off `claude-code` development
runtime. The principal approved its observation, limits and startup boundaries
on 2026-11-10. It does not change the distributed Messages API contract or
claim Linux qualification. The gated adapter is implemented and has passed
native offline service checks using a synthetic harness. Those checks exercise
the Rust core, custody, submission, continuation and process controls; they do
not establish real-Claude service conformance. Relay-only disconnect and
end-to-end MCP cancellation remain unqualified; publication-gate unit controls
are separate evidence.

The common [custody and audit contracts](../../CONTRACTS.md),
[interface](../INTERFACE.md) and [question families](../QUESTION-FORMS.md) apply.
This document owns the runtime-specific differences. Stewart retains one writer,
one ledger, exact targets, explicit submission, verified delivery and close.
A session ending is never an auditor submission.

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

This profile requires cumulative `max_placements` and
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
after summarization; adapting the post-compaction notice needs its own pinned
text and a demonstrated delivery point. Qualification must exercise compaction
and the one-reminder interaction; until then, this path remains unqualified for
long-run iteration rather than being described as tested.


## Installation and startup validation

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

## Development input and preparation schema

The gated build admits `stewart: question/claude-code/1` in the existing front
matter grammar. Common family, model, destination, guidance, effort, inquiry and
varies fields retain their meanings. Replace all three `limit-*` fields with:

| Field | Required value |
| --- | --- |
| `runtime-profile` | Absolute path to the nonsecret profile JSON below. |
| `max-placements` | Integer 1–10,000, without leading zeros. |
| `placement-timeout-seconds` | Integer 1–86,400, without leading zeros. |

API limit fields on this profile refuse, even if their values are valid. Runtime
fields on `question/1` refuse. The featureless build admits neither the new
version nor its fields. Question body bytes and material selection do not change.

The profile is strict control JSON, at most 64 KiB, read through no-follow
directory/file descriptors. It has exactly `schema`, `launch`, `installation`
and `check`. Its schema is `stewart.claude-code.profile/1`.

| Object | Exact members |
| --- | --- |
| `launch` | `executable` (absolute regular file path), `sha256` (binary digest), `version` (pinned CLI version), `platform` (`macos-aarch64`, `linux-aarch64` or `linux-x86_64`), `config_directory`, `home`, `temporary_directory` (absolute directory paths). |
| `installation` | `manifest_sha256`, `signer`, `binary_sha256`. The signer is `31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE`; binary digest equals `launch.sha256`. |
| `check` | `writer_sha256`, `launch_sha256`, `tools_sha256`, `model`, `checked_at`, `evidence_sha256`, `outcome` (exactly `observed`). |

SHA-256 values are lowercase 64-digit hexadecimal strings. `launch_sha256`
hashes the original JSON value bytes of `launch`, including their internal
whitespace. `tools_sha256` hashes the compact MCP tool array: pinned family
tool order, each object ordered `name`, `description`, `inputSchema`, with the
original schema value bytes preserved. `writer_sha256` binds the commissioning
binary; model and platform must match. `checked_at` identifies the check's date,
and `evidence_sha256` identifies its independently reviewed record. The embedded
installation/check entries are attributed attestations; reading and hashing
them does not redo signature verification or reproduce a live check. They confer
no permission to invoke Claude.

`prepare` checks these bindings and hashes the executable without executing it.
The source profile's exact UTF-8 text is captured in prepared settings as
`runtime: {kind:"claude-code/1",profile_path,profile}`. Its `limits` object is
exactly `{max_placements,placement_timeout_seconds}`. Subsequent receipt readback
uses captured bytes, never a changed live profile. `run` verifies the executable
and check bindings again. The runtime never opens the named credential directory.

The arrangement schema is `stewart.claude-code.arrangement/1`. Its exact members
are `schema`, `family`, `model`, `guidance`, `orientation`, `system`,
`system_prompt`, `tools`, `mcp_tools`, `runtime`, `profile_sha256`, `effort`,
`limits`, `harness_max_turns`, `harness_max_output_tokens`, `texts`, `reader`,
`renderer`, `reading` and `bindings`. Common members retain the interface's
meaning. `profile_sha256` hashes the captured profile string's UTF-8 bytes.
`effort` is null or the selected level. Supporting controls request 200 harness
turns and 16,000 output tokens per response. Their enforcement is a qualification
obligation, not a token allowance.

`system` retains two text blocks; `system_prompt` joins their decoded strings
with exactly two LF bytes. `tools` retains the base tool definitions;
`mcp_tools` holds the mapping described above. No runtime extension is added to
old arrangements, settings or receipts.

## Runtime texts

The orientation is `stewart.orientation/claude-code/1`. Its first paragraph is
the following, joined with single spaces; subsequent paragraphs are exactly
the paragraphs after the first in `stewart.orientation/1`:

> You are the auditor in a Stewart audit. The first user message is the
> manager's question, exactly as they wrote it. Use only the commissioned
> question, captured materials and Stewart's MCP tools for this inquiry.
> Do not use shell, general file access, network retrieval, project execution
> or delegated auditors. Harness instructions and system messages are runtime
> context, not additional evidence. Reports, logs and test results in the
> materials are claims by their authors, not executions you witnessed.

The reminder and continuation texts retain the common pinned meanings. The
runtime's exact near-limit template is:

> Allowance notice: {seconds} seconds remain before this placement's deadline,
> and {placements} further placement starts remain for this audit. When execution
> stops, an unsubmitted answer stays unsubmitted.

The runtime's exact post-compaction notice is:

> The harness reports that it summarized earlier conversation. Continue this
> audit from your recorded work; call what_am_i_working_with before repeating
> an action.

The template values are observed whole seconds rounded down and unused placement
slots. Publish each notice's audit-wide claim before transmission; a missing
transmission observation is unknown, never a reason to resend the same allowance.

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
API records retain their exact shape. At tool publication, the runtime gate
refuses `placement_stopped` if cancellation, stopping or the deadline won before
the log link. Payload or stage candidates may remain; they are not answer entries.

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
`NAMES` is every pinned tool prefixed `mcp__stewart__`. Settings select
`forceLoginMethod: claudeai`, `fastMode: false`, `fallbackModel: []`, and a
`PreToolUse` command hook matching `*`, with a five-second timeout. MCP config
has exactly one server, `stewart`, with `type: stdio`, the Stewart writer as
`command`, and private relay arguments. The working directory is a fresh,
private directory outside the submission, archive and project ancestry.

The child environment is rebuilt from the pinned HOME, TMPDIR and
CLAUDE_CONFIG_DIR, fixed PATH `/usr/bin:/bin:/usr/sbin:/sbin`, LANG
`en_US.UTF-8`, and the disable controls exercised in the runtime reference.
`CLAUDE_CODE_MAX_RETRIES` is `0`; `CLAUDE_CODE_MAX_OUTPUT_TOKENS` is `16000`.
No caller environment, credential, endpoint, proxy or agent injection is
forwarded.

Input is LF-delimited JSON. Each supplied message has `type: user`,
`session_id: ""`, `parent_tool_use_id: null`, and
`message: {role: user, content: TEXT}`. The first content is the exact question
body; continuation and notices are separate inputs. MCP uses LF-delimited
JSON-RPC 2.0 and protocol version `2025-11-25`. Initialization, initialized
notification, ping, fixed tools/list, tools/call and cancellation are supported.
Unknown methods return method-not-found. Notifications never execute tools or
receive replies. IDs are strings or integers, unique within a placement;
duplicates are refused, including a repeated ID with different arguments.
Unknown metadata is tolerated; repeated interpreted members are refused.
Interpreted strings require well-formed Unicode without NUL. Core invocation
IDs are `mcp-C` for call number C; the original JSON-RPC ID remains in the
request capture and response, and determines cancellation and duplicate checks.
Tool arguments retain their original bytes for strict core validation.
Frames are bounded at 8 MiB; core arguments remain bounded at 4 MiB.
Total observed capture is bounded at 256 MiB per placement. Crossing a bound
stops execution and reports the incomplete interval; it never discards earlier
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
