# Claude Code runtime reference for integration work

Documentation checked 2026-10-31; the sections on subscription credentials,
binary identity, and tool transport were checked 2026-11-10. No Claude Code/SDK
run has been performed for
this work; the candidate configuration has not been compiled or tested as a
combination. Verify these details against the selected pinned release.

## Where to find the details

| Topic | Primary references | What to resolve or retain |
| --- | --- | --- |
| Runtime/SDK choice | [SDK overview](https://code.claude.com/docs/en/agent-sdk/overview), [configuration](https://code.claude.com/docs/en/agent-sdk/configuration), [CLI reference](https://code.claude.com/docs/en/cli-reference) | SDK convenience versus a CLI bridge; helper installation and version pinning alongside the Rust binary. |
| Explicit credentials | [Authentication](https://code.claude.com/docs/en/authentication), [headless/bare mode](https://code.claude.com/docs/en/headless), [legal and compliance](https://code.claude.com/docs/en/legal-and-compliance) | Use the supported API/cloud route; establish behavior with absent or empty credentials and an existing local login. Keep credentials out of captured diagnostics. |
| Environment and ambient configuration | [SDK feature loading](https://code.claude.com/docs/en/agent-sdk/claude-code-features), [environment variables](https://code.claude.com/docs/en/env-vars), [TypeScript](https://code.claude.com/docs/en/agent-sdk/typescript), [Python](https://code.claude.com/docs/en/agent-sdk/python) | Filesystem settings, global configuration, memory, managed policy and connectors are distinct inputs. Verify child-environment replacement/merging in the selected SDK and version. |
| Tools and permissions | [Custom tools](https://code.claude.com/docs/en/agent-sdk/custom-tools), [permissions](https://code.claude.com/docs/en/agent-sdk/permissions), [tool search](https://code.claude.com/docs/en/agent-sdk/tool-search) | Tool availability versus approval, MCP loading, deferred schemas and any remaining built-in tools. |
| Compaction | [Agent loop](https://code.claude.com/docs/en/agent-sdk/agent-loop), [model configuration](https://code.claude.com/docs/en/model-config), [hooks](https://code.claude.com/docs/en/agent-sdk/hooks) | Automatic compaction under the selected prompt/configuration, observable boundaries, instruction preservation and re-entry. |
| Usage and budgets | [Cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking), [TypeScript result types](https://code.claude.com/docs/en/agent-sdk/typescript#sdkresultmessage), [Python reference](https://code.claude.com/docs/en/agent-sdk/python) | Which calls are counted, cumulative versus per-turn totals, restored totals, resets, missing results and enforcement timing. |
| Installation, updates and binary integrity | [Setup](https://code.claude.com/docs/en/setup) | Version pinning, update control, the signed release manifest and platform requirements. |
| Interrupt and termination | [Interrupt receipts](https://code.claude.com/docs/en/agent-sdk/typescript#sdkcontrolinterruptresponse), [SIGTERM behavior](https://code.claude.com/docs/en/headless#stop-a-run-with-sigterm), [hooks](https://code.claude.com/docs/en/agent-sdk/hooks) | Queued work, active handlers, graceful interruption, process death and the final result that may be lost. |

## Candidate controls

These names are navigation aids for a pinned-version check, not a supported
configuration promised by Stewart. Verify how the options compose before using
them together.

- **Authentication:** explicit `ANTHROPIC_API_KEY` or the selected supported
  cloud credentials; `--bare` through SDK `extraArgs`/`extra_args`; private
  configuration through `CLAUDE_CONFIG_DIR`. Inspect reported authentication
  source/provider as supporting observations. Missing credentials must not
  silently select a different billing route.
- **Ambient inputs:** `settingSources: []`, `strictMcpConfig: true`, an explicit
  process environment/working directory, and the documented controls for auto
  memory, connectors and background tasks. Candidate switches include
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY`, `ENABLE_CLAUDEAI_MCP_SERVERS` and
  `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`. Managed/server-managed policy remains
  a separate input; a fresh directory does not remove server-managed policy.
- **Tool surface:** `tools: []`, an explicit `mcpServers` map, a narrowly scoped
  `allowedTools`, `permissionMode: "dontAsk"`, `permissionPrompts: "none"` and
  a `PreToolUse` hook. `allowedTools` is about approval; it is not the sole tool
  inventory control. Inspect actual inventory and behavior, including after
  compaction. Check whether `EndConversation` remains available. For a small
  application tool set, assess `ENABLE_TOOL_SEARCH=false` or TS `alwaysLoad`
  to avoid uncertain deferred-tool discovery.
- **Compaction observations:** `system/compact_boundary`, `PreCompact` and
  `compact_metadata`. Trigger controls to check include `autoCompactWindow`,
  `--autocompact`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW` and
  `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`. Confirm supported values and actual behavior.
- **Limits and shutdown:** `maxTurns`, `maxBudgetUsd`, `interrupt()`, `close()`,
  an abort controller and application-side cancellation. These do not all
  measure or stop the same activity. Establish the event order for a running
  custom tool, queued inputs, a partial response and forced process death.

Open composition question: does the selected SDK's `--bare` pass-through retain
explicitly supplied in-process MCP servers, hooks and normal compaction?
This is unverified. A custom prompt plus disabled filesystem instructions also
needs an actual compaction/re-entry comparison.

## Subscription credentials

From the authentication, headless and legal pages linked above. These are
documented statements, not observed behavior.

- **Scripted use.** `claude setup-token` prints a one-year OAuth token for
  `CLAUDE_CODE_OAUTH_TOKEN`, documented for CI pipelines and scripts. It can
  only make model requests. A `/login` credential is stored in the macOS
  Keychain, or in `.credentials.json` under `~/.claude` or `CLAUDE_CONFIG_DIR`
  on Linux.
- **Bare mode excludes them.** Bare mode never reads OAuth credentials, the
  keychain or `CLAUDE_CODE_OAUTH_TOKEN`. A subscription run is therefore
  non-bare: hooks, skills, plugins, MCP discovery, auto memory, `CLAUDE.md`,
  system reminders and background tasks each need their own control and their
  own verification. The headless page says bare mode will become the default
  for `-p`; recheck this route at every pin.
- **Precedence.** Cloud-provider selection, `ANTHROPIC_AUTH_TOKEN`,
  `ANTHROPIC_API_KEY`, `apiKeyHelper`, `CLAUDE_CODE_OAUTH_TOKEN`, profile or
  federation credentials, then the `/login` credential. Under `-p` a present
  API key is always used. A non-bare run given no credential uses whatever
  login the machine or configuration directory holds. Either direction can
  select a billing route silently.
- **Terms.** OAuth authentication is for subscribers' ordinary use of Claude
  Code and Anthropic's own applications, and plan limits assume ordinary
  individual use of Claude Code and the Agent SDK. Third-party developers may
  not offer Claude.ai login, route requests through plan credentials for their
  users, or collect, store or intermediate those credentials. An end user
  signing in to the unmodified binary with their own subscription is not
  prevented. Read the legal page itself before relying on this summary;
  questions about a particular use go to Anthropic.

## Binary identity and updates

From the setup page. Documented statements, not observed behavior.

- **One executable.** The native install is a single binary, and the npm
  package installs the same one through a per-platform optional dependency.
  Linux x64 and arm64 are supported, including musl. Alpine needs `libgcc`,
  `libstdc++` and `ripgrep`, with `USE_BUILTIN_RIPGREP=0`.
- **Signed manifest.** Each release from 2.1.89 publishes `manifest.json` with
  a SHA-256 per platform binary and a detached GPG signature. The release key's
  fingerprint is `31DD DE24 DDFA B679 F42D 7BD2 BAA9 29FF 1A7E CACE`. Linux
  binaries carry no code signature of their own; the manifest, or a signed
  apt, dnf or apk repository, is the integrity check.
- **Updates.** A native install updates in the background, and an update takes
  effect at the next start. `~/.local/bin/claude` is a symlink into
  `~/.local/share/claude/versions/`. `DISABLE_AUTOUPDATER` stops only the
  background check; `DISABLE_UPDATES` blocks every update path. The installer
  accepts an exact version. A running session reads parts of its executable
  from disk.
- **An unmodified binary can still be redirected.** `ANTHROPIC_BASE_URL` sends
  requests, and the credential with them, to another endpoint. A settings `env`
  block, an `apiKeyHelper`, hooks, managed settings, a preloaded library or
  another `claude` earlier on `PATH` also change what runs. A digest
  establishes which file ran, not how it was configured.

## Tool transport and Rust building blocks

From the Agent SDK overview, the headless page and crates.io.

- **No official Rust SDK.** The Agent SDK ships for Python and TypeScript. For
  other languages the documentation says to run `claude -p` as a subprocess and
  read its JSON output. About ten community Rust wrappers exist, none official;
  the `claude-agent-sdk` crate names an Anthropic repository but was published
  by an individual and last released in September 2025.
- **Tools arrive through MCP.** The harness starts a stdio MCP server as its
  own child from `--mcp-config`, and under `-p` waits for it before the first
  turn. Its startup event, `system/init`, reports the model, tools, MCP servers
  and plugins.
- **`rmcp`** is the official Rust MCP SDK: client and server, several
  transports and the full protocol surface. A stdio tool server needs its
  `server` and `transport-io` features. It requires `tokio`, `serde`,
  `serde_json`, `futures`, `tracing`, `tokio-util`, `chrono`, `thiserror` and
  `indexmap`, and `sha2` 0.11, a second `sha2` beside the service's pinned
  0.10.9. `mercutio` is a synchronous, IO-less alternative with little
  adoption.
- **Isolation.** `landlock`, from the Landlock project, restricts a child's
  filesystem access; `hakoniwa` and `procage` are higher-level sandboxes. A
  fresh container holding only the pinned binary and an empty configuration
  directory needs none of them.

## Unverified

Stated from memory or inferred, and not checked against a source or a run:

- that the harness names MCP tools `mcp__<server>__<tool>` in what the model
  sees;
- that `system/init` arrives before the first message is sent, which would let
  a session's reported configuration be checked before any audit content;
- that `rmcp` hands a tool handler parsed arguments without the original
  request line;
- that the binary can be launched from an already-open descriptor, given that
  it reads its executable from disk while running;
- `rmcp`'s transitive dependency count, its minimum Rust version against the
  pinned toolchain, and its behavior in the static musl fat-LTO build.

## Accounting

The TypeScript reference distinguishes per-turn main-loop `usage` from broader
`modelUsage`; the latter includes internal compaction calls through the query
pipeline. Helpers outside that pipeline can be excluded. `total_cost_usd` is a
client estimate, not authoritative billing. Match the reported units and scope
to the commission before using any field for allowances.

The result reference and cost guide say resumed results can include totals
restored from earlier session calls. Do not assume every `query()` result starts
at zero or sum all results. Streaming totals, session restoration and `/clear`
resets require identified checkpoints/deltas. Keep the Stewart audit identity separate from
harness session IDs. The initial adapter can retain fresh-conversation
continuation, avoiding a need to adopt native resume immediately.

The cost guide states that crash results may have zeroed totals. The documented
assistant-message fallback recovers main-loop input/cache counts but not output
or subagent totals. Whether there is enough supported observation to bound lost
internal-call consumption remains unresolved. The direct adapter's specified
per-request missing-response estimate cannot simply be assumed to apply here.

The documented USD budget uses a client estimate that can exceed its configured
value, and restored spend does not count toward that query's budget. The exact
`maxTurns` model-call boundary needs verification: establish whether each
control gates a call before consumption or detects an excess afterward. A
turn-start gate alone does not observe every internal model call. Stewart
currently promises token/turn allowances, not a dollar cap.

## Stopping and the durable boundary

The documented interrupt receipt can list queued messages that still run;
SDK `interrupt()` does not itself request `cancel_queued`. The direct control
protocol has a separately advertised capability for that request. Stopping new
input alone does not dispose of work already queued. SIGTERM ends the process
but can leave the active turn without a result, affecting accounting.

A hook refusal does not undo a tool handler already in flight. Stewart's own
authorization/publication checks must reject a late effect after authoring ends.
Make helper cancellation cooperate with that boundary; prove actual stopping
separately. Verify whether custom handlers receive a usable cancellation signal
and whether interruption waits for them.

## Versions and evidence

Pin and record both SDK and Claude Code versions, plus the initialization
capabilities. Check version floors for interruption receipts, queue cancellation,
permission prompts, bare mode, reset messages and usage fields. Availability of
individual features does not establish that the whole configuration composes
correctly.

Tests need witnesses for internal-call accounting, effective authentication/tools,
usage across compaction, and stop/late-mutation behavior. Preserve independent
observations and failed variants through review under
[DEVELOPMENT](../../development/DEVELOPMENT.md#evidence-and-retention). Only separately
commissioned live work can settle provider behavior.
