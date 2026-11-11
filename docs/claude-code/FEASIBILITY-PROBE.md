# Native subscription feasibility probe

Approved by the principal on 2026-11-10 for the limits below; the principal
also confirmed paid extra usage disabled. This is one commission, not standing
permission for replacement runs. The
[recorder and supervisor](../../apparatus/claude-code/README.md) are implemented;
the 3 pin checks and 18 offline native probe checks pass. Version and help have
completed; dedicated login and the two authentication checks remain prerequisites
to model use.
This is the first bounded experiment for the
[native launch recommendation](RUNTIME-REFERENCE.md#native-launch-recommendation),
using synthetic material on the development Mac. It does not qualify an adapter,
a model or Linux enforcement.

## Approved commission

| Boundary | Proposed limit |
| --- | --- |
| Executable | Unmodified Claude Code **2.1.322**, `darwin-arm64`; signed manifest, SHA-256 and Apple code signature verified on the host. Pin: `~/.local/share/stewart-claude-code/2.1.322/claude`, SHA-256 `a9d237949db816a0b7afd88a9a8e1df36b3a597a30f5a41d1c0539eb180a3450`. |
| Authentication | Manager's own subscription login in a dedicated `CLAUDE_CONFIG_DIR`; harness-owned Keychain/file storage. No subscription secret enters Stewart. |
| Spending | Included subscription usage only. Manager confirms paid overflow/usage credits are disabled. Quota exhaustion ends the batch. No API route or purchased additional usage. |
| Model | Exact proposed ID `claude-haiku-5-5`, as listed in the [model reference](https://platform.claude.com/docs/en/models/overview). Availability under this subscription is unverified; unavailable means stop, with no substitute model. |
| Setup | At most four non-model CLI invocations: version, help, auth status against an empty configuration, auth status against the selected configuration. If needed, one manager-operated login flow before that final status check, without capturing its codes or credentials. |
| Model sessions | At most **three**, sequential, fresh sessions; exactly one user input per session, no queued follow-ups, resume, automatic replacement or retry of a failed case. |
| Limits | `--max-turns 4`, requested output limit 2,048 tokens, provider retries disabled. A supervisor stops each session after 120 seconds and the entire model phase after six minutes. |
| Stop | Close input, terminate the owned process group, allow five seconds, then kill survivors and record the observed outcome. Stop the batch on an unexpected route, model, tool, configuration, credential exposure or supervision failure. |

These are execution limits, not a proof of a total token cap. The harness's
turn/output controls do not account for every internal call. Missing totals are
reported as unknown, never zero. This batch excludes compaction, usage-limit
studies and attempts to exhaust the subscription.

## Fixed launch inputs

Use `.scratch/claude-code-probe-01` for the private run records and independent
witnesses, with separate empty working directories outside the repository under
`/private/tmp`. Keep the dedicated harness
login outside the evidence. Hash the executable, supplied settings, MCP config,
prompt, hook, relay and supervisor before starting; retain those nonsecret
inputs with the run. Do not copy or inspect the credential store.

Use an explicit environment containing the real home identity, required host
temporary-directory/locale values, a controlled system PATH and
`CLAUDE_CONFIG_DIR`. Add these proposed controls, checked against the
[environment reference](https://code.claude.com/docs/en/env-vars):

```text
DISABLE_UPDATES=1
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
CLAUDE_CODE_DISABLE_AGENT_VIEW=1
CLAUDE_CODE_DISABLE_FAST_MODE=1
ENABLE_CLAUDEAI_MCP_SERVERS=false
ENABLE_TOOL_SEARCH=false
CLAUDE_CODE_MAX_RETRIES=0
CLAUDE_CODE_MAX_OUTPUT_TOKENS=2048
```

Do not inherit provider credentials, alternate endpoints, proxies, credential
helpers, library injection or watchdog variables. Do not enable debug logging
or capture the manager's login interaction. Require `auth status` to report the
selected configuration directory and `authMethod: "claude.ai"`; the empty
configuration must report no login. A conflicting result ends setup.
[Authentication reference](https://code.claude.com/docs/en/authentication)

The proposed argv after the absolute executable is:

```text
-p --input-format stream-json --output-format stream-json --verbose
--restricted --tools "" --setting-sources ""
--settings <absolute-settings-file>
--strict-mcp-config --mcp-config <absolute-mcp-file>
--allowedTools mcp__probe__read_specimen mcp__probe__record_note
--permission-mode dontAsk --permission-prompts none
--system-prompt-file <absolute-prompt-file>
--model claude-haiku-5-5 --max-turns 4 --no-session-persistence
```

This is an argument specification, not a shell command. Explicit settings use
`forceLoginMethod: "claudeai"`, `fastMode: false`, `fallbackModel: []` and
the case's command hook. The MCP file contains only the local stdio server
`probe`, with an absolute executable path. No other tools are granted.
Managed policy remains an input: inspect the effective observations and stop
on a mismatch. These flags' composition is what the experiment tests.
If a necessary source or setting cannot be observed, leave that property
unverified; do not infer its absence from the startup tool inventory.
[CLI reference](https://code.claude.com/docs/en/cli-reference),
[settings reference](https://code.claude.com/docs/en/settings-reference)

Use this system prompt:

> You are testing a synthetic tool interface. Use only the supplied tools. Read
> the specimen, then record its marker word once. If a tool is denied, report
> the denial and stop without retrying. Do not perform any other task.

The sole user input is: `Carry out the synthetic tool-interface check.`
Send it as one stream-json user message, then close stdin. In the first case,
hold stdin open without input for five seconds first and record whether
`system/init` arrives. If it does not, send the synthetic input within the same
session budget and record the actual ordering. Absence before input means it
cannot yet serve as a pre-input gate; an event timestamp alone cannot establish
the timing of all provider requests.

## Cases and witnesses

The MCP server exposes exactly two tools. `read_specimen` takes an empty object
and returns `The marker word is orchard.\n`. `record_note` takes an object with
one string field, `text`, and appends the original operand to the independent
witness before returning the fixed text `recorded`. Neither tool reads the
repository or a real audit. Reject unknown
fields and tool names. Observe each raw JSON-RPC line before parsing it, as
required by the [stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).

| Case | Only intended difference | Observation required |
| --- | --- | --- |
| 1. Firing control | Command hook observes calls and returns no decision; explicit permissions allow both tools. | Actual read and record calls, exact operand `orchard`, and a corresponding witness append. Startup reports the pinned model and only the two expected tools/server. |
| 2. Denial | Same setup and prompt; hook denies `mcp__probe__record_note`. | An attempted record observed by the hook, its denial response, and no record call reaching the handler or witness append. An absent attempt is unexercised, not a passing denial. |
| 3. Invariance | Case 1 in a different empty working directory, with a fresh witness and session. | Same inventory and successful read/record effect despite the changed location. |

Use a command `PreToolUse` hook, with no prompt/agent hook that could consume
another model call. It logs its raw input and output independently. In case 2
it returns `hookSpecificOutput` with `hookEventName: "PreToolUse"`,
`permissionDecision: "deny"` and a fixed synthetic reason. It leaves other
tool decisions to the explicit allow list.
[Hook protocol](https://code.claude.com/docs/en/hooks#pretooluse-decision-control)

Retain stdout/stderr bytes, raw MCP traffic, hook traffic, effect witness,
monotonic event times, process/group identity, signals and exit statuses.
Retain only credential-free auth status fields. Capture the initialization and
final result as emitted, including usage, model usage, errors and session ID;
do not turn reported cost into a bill or infer missing output/internal usage.
No TLS interception or provider credential capture is part of this probe.

Unexpected extra tools or plugins fail the launch candidate. Restricted mode
is not an OS sandbox, and this comparison proves only the observed hook/tool
path. It says nothing about an already-running handler after authoring ends,
filesystem confinement of the harness, compaction or completeness of internal
accounting. Those require separate controls before adapter claims are adopted.

## Before execution

The authenticated pin receipt and original verification outputs are in
`.scratch/claude-code-pin-01/`. The version and help calls completed successfully
in `.scratch/claude-code-probe-01/`; the original checker then stopped because
it incorrectly required hidden options to appear in help. The
[runtime reference](RUNTIME-REFERENCE.md#help-inventory-check) records the
reviewed cause. `finish-setup` retains these two completed calls and their original
inputs, records the checker correction, and continues with the two unused
authentication checks and one login. No model session has started. The runner
reserves each invocation durably before launch; its run state owns the remaining
allowance.

1. Complete the dedicated harness-owned login in the manager's own Terminal,
   as part of the bounded setup checks.
2. Perform the bounded setup checks before the model phase. Any discrepancy
   between the pinned binary's supported options and this proposal stops the
   batch for review; do not expand the commission to work around one.

The result should recommend adopting, changing or abandoning the launch
candidate, with each case marked observed, failed or unexercised. Keep originals
through review under [evidence and retention](../../development/DEVELOPMENT.md#evidence-and-retention).
The unresolved adapter contract still needs decisions about ambient inputs,
unknown consumption, stopping and durable authoring; this probe does not settle
those by itself.
