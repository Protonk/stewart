# Claude Code runtime reference for integration work

Research checked 2026-10-31; no Claude Code/SDK run has been performed for this
work. This supports [the active plan](../../CLAUDE-CODE-PLAN.md). The starting
advice was a user-relayed Claude web consultation asked about a generic
third-party application, deliberately without Stewart context. Its suggested
configuration has not been compiled or tested as a combination. Relayed advice
is not the principal's endorsement or an authorization to run it.

## Where to find the details

| Topic | Primary references | What to resolve or retain |
| --- | --- | --- |
| Runtime/SDK choice | [SDK overview](https://code.claude.com/docs/en/agent-sdk/overview), [configuration](https://code.claude.com/docs/en/agent-sdk/configuration), [CLI reference](https://code.claude.com/docs/en/cli-reference) | SDK convenience versus a CLI bridge; helper installation and version pinning alongside the Rust binary. |
| Explicit credentials | [Authentication](https://code.claude.com/docs/en/authentication), [headless/bare mode](https://code.claude.com/docs/en/headless), [legal and compliance](https://code.claude.com/docs/en/legal-and-compliance) | Use the supported API/cloud route; establish behavior with absent or empty credentials and an existing local login. Keep credentials out of captured diagnostics. |
| Environment and ambient configuration | [SDK feature loading](https://code.claude.com/docs/en/agent-sdk/claude-code-features), [environment variables](https://code.claude.com/docs/en/env-vars), [TypeScript](https://code.claude.com/docs/en/agent-sdk/typescript), [Python](https://code.claude.com/docs/en/agent-sdk/python) | Filesystem settings, global configuration, memory, managed policy and connectors are distinct inputs. The consultation says TS replaces the child environment while Python merges it; check the selected version. |
| Tools and permissions | [Custom tools](https://code.claude.com/docs/en/agent-sdk/custom-tools), [permissions](https://code.claude.com/docs/en/agent-sdk/permissions), [tool search](https://code.claude.com/docs/en/agent-sdk/tool-search) | Tool availability versus approval, MCP loading, deferred schemas and any remaining built-in tools. |
| Compaction | [Agent loop](https://code.claude.com/docs/en/agent-sdk/agent-loop), [model configuration](https://code.claude.com/docs/en/model-config), [hooks](https://code.claude.com/docs/en/agent-sdk/hooks) | Automatic compaction under the selected prompt/configuration, observable boundaries, instruction preservation and re-entry. |
| Usage and budgets | [Cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking), [TypeScript result types](https://code.claude.com/docs/en/agent-sdk/typescript#sdkresultmessage), [Python reference](https://code.claude.com/docs/en/agent-sdk/python) | Which calls are counted, cumulative versus per-turn totals, restored totals, resets, missing results and enforcement timing. |
| Interrupt and termination | [Interrupt receipts](https://code.claude.com/docs/en/agent-sdk/typescript#sdkcontrolinterruptresponse), [SIGTERM behavior](https://code.claude.com/docs/en/headless#stop-a-run-with-sigterm), [hooks](https://code.claude.com/docs/en/agent-sdk/hooks) | Queued work, active handlers, graceful interruption, process death and the final result that may be lost. |

## Candidate controls from the consultation

These names are navigation aids for a later pinned-version check, not a
supported configuration promised by Stewart. Avoid copying the consultation's
whole launcher before checking how its options compose.

- **Authentication:** explicit `ANTHROPIC_API_KEY` or the selected supported
  cloud credentials; `--bare` through SDK `extraArgs`/`extra_args`; private
  configuration through `CLAUDE_CONFIG_DIR`. Inspect reported authentication
  source/provider as supporting observations. Missing credentials must not
  silently select a different billing route.
- **Ambient inputs:** `settingSources: []`, `strictMcpConfig: true`, an explicit
  process environment/working directory, and the documented controls for auto
  memory, connectors and background tasks. Relevant names in the advice were
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY`, `ENABLE_CLAUDEAI_MCP_SERVERS` and
  `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`. Managed/server-managed policy remains
  a separate input; a fresh directory does not remove server-managed policy.
- **Tool surface:** `tools: []`, an explicit `mcpServers` map, a narrowly scoped
  `allowedTools`, `permissionMode: "dontAsk"`, `permissionPrompts: "none"` and
  a `PreToolUse` hook. `allowedTools` is about approval; it is not the sole tool
  inventory control. Inspect actual inventory and behavior, including after
  compaction. The advice flags `EndConversation` as a possible remaining
  built-in, and `ENABLE_TOOL_SEARCH=false` or TS `alwaysLoad` as ways to avoid
  uncertain deferred-tool discovery for a small application tool set.
- **Compaction observations:** `system/compact_boundary`, `PreCompact` and
  `compact_metadata`. The advice names `autoCompactWindow`, `--autocompact`,
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW` and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` for
  configuring triggers. Confirm supported values and actual behavior; these
  are not the Messages adapter's fixed 150,000-token trigger.
- **Limits and shutdown:** `maxTurns`, `maxBudgetUsd`, `interrupt()`, `close()`,
  an abort controller and application-side cancellation. These do not all
  measure or stop the same activity. Establish the event order for a running
  custom tool, queued inputs, a partial response and forced process death.

Open composition question: does the selected SDK's `--bare` pass-through retain
explicitly supplied in-process MCP servers, hooks and normal compaction?
The consultation did not establish this. A custom prompt plus disabled
filesystem instructions also needs an actual compaction/re-entry comparison.

## Accounting: checked distinctions and a correction

The TypeScript reference distinguishes per-turn main-loop `usage` from broader
`modelUsage`; the latter includes internal compaction calls through the query
pipeline. Helpers outside that pipeline can be excluded. `total_cost_usd` is a
client estimate, not authoritative billing. Match the reported units and scope
to the commission before using any field for allowances.

**Correction to the relayed response:** the current result reference and cost
guide explicitly say resumed results can include totals restored from earlier
session calls. Do not assume every `query()` result starts at zero or sum all
results. Streaming totals, session restoration and `/clear` resets require
identified checkpoints/deltas. Keep the Stewart audit identity separate from
harness session IDs. The initial adapter can retain fresh-conversation
continuation, avoiding a need to adopt native resume immediately.

The cost guide states that crash results may have zeroed totals. The documented
assistant-message fallback recovers main-loop input/cache counts but not output
or subagent totals. Whether there is enough supported observation to bound lost
internal-call consumption remains unresolved. The direct adapter's specified
per-request missing-response estimate cannot simply be assumed to apply here.

The documented USD budget uses a client estimate that can exceed its configured
value, and restored spend does not count toward that query's budget. The exact
`maxTurns` model-call boundary was not established by the consultation. Treat
its claim that both controls are detect-after mechanisms as something to check,
not as a measured result. A turn-start gate alone does not observe every internal
model call. Stewart currently promises token/turn allowances, not a dollar cap.

## Stopping and the durable boundary

The documented interrupt receipt can list queued messages that still run;
SDK `interrupt()` does not itself request `cancel_queued`. The direct control
protocol has a separately advertised capability for that request. Stopping new
input alone does not dispose of work already queued. SIGTERM ends the process
but can leave the active turn without a result, affecting accounting.

A hook refusal does not undo a tool handler already in flight. Stewart's own
authorization/publication checks must reject a late effect after authoring ends.
Make helper cancellation cooperate with that boundary; prove actual stopping
separately. The consultation did not establish whether custom handlers receive
a usable cancellation signal or whether interruption waits for them.

## Versions, evidence and follow-up

Pin and record both SDK and Claude Code versions, plus the initialization
capabilities. The consultation supplied version floors for interruption receipts,
queue cancellation, permission prompts, bare mode, reset messages and usage
fields. Recheck those against the selected release; taking their maximum does
not establish that the whole configuration composes correctly.

The focused follow-up is whether supported lifecycle observations include
internal calls early enough to establish a defensible missing-consumption bound.
After that, tests need witnesses for effective authentication/tools, usage across
compaction, and stop/late-mutation behavior. Preserve independent observations
and failed variants through review under [DEVELOPMENT](../../DEVELOPMENT.md#evidence-and-retention).
Only separately commissioned live work can settle provider behavior.

For a relayed consultation use [Riker's procedure](../../riker/RIKER.md); include
the relevant context in the message rather than assuming access to this repo.
