# Claude Code runtime reference for integration work

Launch, authentication, CLI, tool and accounting documentation checked
2026-11-10. The selected harness pin is **2.1.322**, present in the
[official changelog](https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md).
The pinned CLI has completed version, help and authentication checks, with one
manager-operated subscription login. The development-build boundary is
implemented. The revised native launch candidate passed its three-case
synthetic comparison: successful tool use, a witnessed hook denial and a
successful repeat in another working directory. The service adapter is now
implemented under its [development runtime contract](CONTRACT.md) and has passed
native offline checks through the actual Rust core and Linux container
acceptance. Those service checks use a synthetic harness; the
[qualification record](../../apparatus/qualified.md) identifies their exact
source, binaries and coverage. Real-Claude service conformance remains
unqualified.

The [manifest for this version](https://downloads.claude.ai/claude-code-releases/2.1.322/manifest.json)
was authenticated against the pinned release signing key on 2026-11-10. The
installed `darwin-arm64` binary and a dedicated copy match its SHA-256, and the
copy passed Apple's code-signature check on the host. Agent-shell DNS and
code-signature failures did not establish these results; host checks did.
The CLI reports the expected version. The successful comparison demonstrates
the selected model and synthetic tool path under this subscription; complete
consumption accounting remains unverified.

## Reviewed native comparison

The principal approved probe 02 on 2026-11-10. It used exactly one fresh
authentication-status check and three fresh model sessions. Review of
`.scratch/claude-code-probe-02` confirmed all three outcomes against raw harness
stdout and the independent MCP, hook and effect witnesses. All 32 input bindings
matched, and all 42 files in the stopped first run remained unchanged. The
executed controller is from commit `1efed2a`; frozen source and the approved
scope are retained in the run's `inputs/` directory.

| Case | Independent observations | Process outcome |
| --- | --- | --- |
| 1. Positive control | One read, one hook-observed record attempt, one handler call recording exactly `orchard`. | Exit 0; process group gone after 7.834 seconds. |
| 2. Denial | One read and one hook-observed record attempt. The hook returned deny; no record call reached the MCP handler and no record effect was written. The harness reported the matching tool-use ID as denied and did not retry. | Exit 0; process group gone after 3.559 seconds. |
| 3. Invariance | A fresh session in another empty directory again read and recorded exactly `orchard` once. | Exit 0; process group gone after 3.150 seconds. |

Each startup reported exactly the two expected tools, the sole connected
`probe` MCP server, the three accepted built-ins, `dontAsk`, CLI 2.1.322 and
`claude-haiku-5-5`. Session IDs were distinct; each supervisor sent one user
input. Every result reported success, three turns, no queued turns and no
spawned subagents. No supervision signal was needed in this batch.

The fresh authentication check reported `loggedIn: true`, `authMethod:
"claude.ai"` and the dedicated configuration directory, with exit 0. All three
startups reported `apiKeySource: "none"`. Each session's rate-limit event
reported `overageEnabled: false` and `isUsingOverage: false`, consistent with
the principal's disabled-extra-usage condition. These are harness observations,
not an independent inspection of billing or the credential store.

The first session sent its synthetic input at 5.019 seconds and observed
`system/init` at 5.039 seconds. The other two also observed initialization after
input. The stream therefore supplies no demonstrated pre-input configuration
gate. The revised shared clock kept all MCP, hook and effect observations
inside their session's supervisor interval; observers are identified by PID.

Final usage reports were present for all three fresh sessions:

| Case | Input | Cache creation input | Cache read input | Output |
| --- | ---: | ---: | ---: | ---: |
| 1 | 6 | 1,286 | 2,322 | 136 |
| 2 | 6 | 545 | 3,104 | 213 |
| 3 | 6 | 504 | 3,104 | 127 |
| Sum of reports | 18 | 2,335 | 8,530 | 476 |

These are the harness's reported token fields, not independently complete
provider accounting. Its cost fields do not establish a bill. The first stopped
run still has unknown consumption. Turn/output limits were not reached, so
their enforcement remains unexercised; compaction, a lost final result, native
resume, filesystem confinement and late authoring after closure were outside
this comparison. Reported skills and agent definitions remain part of the
harness metadata; two available tools do not establish an otherwise empty
instruction surface.

This comparison supplied the feasibility evidence for the selected native CLI
and stdio MCP path. It does not establish full-service or release qualification.
The commission is consumed; there is no remaining launch or replacement authority.

## Native authentication observations

On 2026-11-10, the empty configuration reported `loggedIn: false`,
`authMethod: "none"` and exit 1. After the manager completed one uncaptured
login, the dedicated configuration reported `loggedIn: true`,
`authMethod: "claude.ai"` and exit 0. Both reports named the intended
configuration directories. The first session's startup also reported
`apiKeySource: "none"`. These are observations of the selected route, not an
independent observation of provider billing. No credential store was inspected
or copied.

The private run is `.scratch/claude-code-probe-01`. Its `auth-empty` and
`auth-selected` records retain only the allowlisted status fields, process
observations and exit results. The run state records all four setup calls and
the single login as consumed.

## Help inventory check

The first setup checker incorrectly required every approved option to appear
in `--help`. It stopped after the two successful metadata calls, before any
authentication check or login. The
[CLI reference](https://code.claude.com/docs/en/cli-reference#cli-flags) explicitly
says help omits supported flags. Read-only inspection of the authenticated
2.1.322 executable found `--system-prompt-file` and `--max-turns` registered
with `hideHelp()`. Their absence from the captured help is expected and does
not require changing the approved arguments.

The corrected checker retained the visible-option checks. The continuation
preserved the original source and outputs and recorded the correction before
the unused authentication steps. Option registration alone did not establish
that the launch settings worked together; the later native comparison supplied
that bounded observation.

## First native launch outcome

The 2026-11-10 run in `.scratch/claude-code-probe-01` launched case 1 once and
stopped the batch. `RESULT.json`, the case's raw stdout and process journal,
and its independent MCP journals retain the observations. Cases 2 and 3 never
launched. All bound source, executable and configuration hashes still matched
at the initial review. The subsequent offline recorder fixes changed the working
source, while the run's frozen inputs, receipts and captures remain unchanged.

Startup reported the expected `claude-haiku-5-5`, CLI version, `dontAsk`
permission mode, exactly the two probe tools, and the sole connected `probe`
server. It also reported these plugins with `path: "builtin"` and the
corresponding `@builtin` source:

- `cc-plugin-agents-md`
- `cc-plugin-privacy`
- `cc-plugin-plugin-authoring`

That nonempty inventory triggered the recorder's `unexpected plugin or server
error` refusal. No plugin/server error field was present; the plugin inventory
itself was the cause. The supervisor sent SIGTERM, observed the process group
gone, and recorded exit 143 after 5.113 seconds. This demonstrates this native
stop path, not Linux enforcement or cancellation of a provider request.

The supervisor held input for five seconds. Its own journal records the sole
synthetic input at 5.009 seconds and first stdout capture, containing
`system/init`, at 5.038 seconds. No startup event was captured before input.
This configuration therefore has no demonstrated startup check before sending
input. Provider-request timing is not visible in these records.

The MCP witness contains an unsupported `server/discover` request followed by
successful `initialize`, `notifications/initialized` and `tools/list` traffic.
It contains no tool call. There is no hook/effect witness, assistant response,
final result or usage total. The positive tool control, hook denial and
invariance comparison are unexercised. Consumption is unknown, not zero;
reported startup model selection does not establish a successful provider call.

### Built-in inventory decision

The selected launch arrangement accounts explicitly for the pinned harness's
built-in components. The second probe retained its exact two-tool restriction.
Restricted mode is documented to limit tools and settings sources, not to remove
every built-in component.
[CLI reference](https://code.claude.com/docs/en/cli-reference#cli-flags)

Read-only inspection of the authenticated binary identifies the instruction
loader, a privacy guard, and plugin-authoring support behind the three names.
The privacy guard's declared role is to refuse shell calls combining the
signed-in account's email address with a User-Agent. These are static findings,
not exercised guarantees. Disabling all three merely to obtain an empty list
would remove a protection and would not establish an instruction-free harness.
The documented `enabledPlugins` settings and built-in instruction options are
configuration controls; their composition under this restricted launch has not
been tested. [Settings reference](https://code.claude.com/docs/en/settings-reference#enabledplugins),
[instruction loading](https://code.claude.com/docs/en/memory#choose-which-instruction-files-load)

The principal accepted the next candidate's inventory on 2026-11-10: exactly
these three built-in name/source/path entries for this binary, with the privacy
guard preserved. The checker rejects missing, extra, duplicated or changed
entries, while permitting a different list order. Extra tools and plugin/server
errors still refuse. This configuration decision does not certify their
model-visible contributions or authorize a new Claude invocation. The stopped
batch is not resumable, and its two unused sessions
are not replacement authority. The separately approved second commission tested
the accepted candidate as described above; its allowance is now consumed too.

### Observer clock scope

The probe used Python 3.9.6 on macOS. Its monotonic clocks have different origins
in different processes; MCP timestamps cannot be subtracted from supervisor
timestamps to establish cross-process order. The input/startup/stop timings
above come from the single supervisor's journal. Python made the macOS
monotonic clock common to all processes in 3.10.
[Python clock reference](https://docs.python.org/3/library/time.html#time.monotonic)

A native offline comparison reproduced this mismatch in three parent/child
brackets; `CLOCK_UPTIME_RAW` readings fell inside all three brackets. The current
recorder now uses that shared clock directly on macOS and `CLOCK_MONOTONIC` on
Linux, with a clock name and observer PID on each new observation. Native tests
check the cross-process bracket immediately and after a delay. Existing
timestamps remain as recorded and gain no cross-process meaning from the fix.

## Where to find the details

| Topic | Primary references | What to resolve or retain |
| --- | --- | --- |
| Runtime/SDK choice | [SDK overview](https://code.claude.com/docs/en/agent-sdk/overview), [configuration](https://code.claude.com/docs/en/agent-sdk/configuration), [CLI reference](https://code.claude.com/docs/en/cli-reference) | SDK convenience versus a CLI bridge; helper installation and version pinning alongside the Rust binary. |
| Credentials | [Authentication](https://code.claude.com/docs/en/authentication), [headless/bare mode](https://code.claude.com/docs/en/headless), [legal and compliance](https://code.claude.com/docs/en/legal-and-compliance) | For the native development route, use the manager's own login in the unmodified harness; establish missing-login refusal and absence of API fallback. Keep credentials out of captured diagnostics. |
| Environment and ambient configuration | [SDK feature loading](https://code.claude.com/docs/en/agent-sdk/claude-code-features), [environment variables](https://code.claude.com/docs/en/env-vars), [TypeScript](https://code.claude.com/docs/en/agent-sdk/typescript), [Python](https://code.claude.com/docs/en/agent-sdk/python) | Filesystem settings, global configuration, memory, managed policy and connectors are distinct inputs. Verify child-environment replacement/merging in the selected SDK and version. |
| Tools and permissions | [Custom tools](https://code.claude.com/docs/en/agent-sdk/custom-tools), [permissions](https://code.claude.com/docs/en/agent-sdk/permissions), [tool search](https://code.claude.com/docs/en/agent-sdk/tool-search) | Tool availability versus approval, MCP loading, deferred schemas and any remaining built-in tools. |
| Compaction | [Agent loop](https://code.claude.com/docs/en/agent-sdk/agent-loop), [model configuration](https://code.claude.com/docs/en/model-config), [hooks](https://code.claude.com/docs/en/agent-sdk/hooks) | Automatic compaction under the selected prompt/configuration, observable boundaries, instruction preservation and re-entry. |
| Usage and budgets | [Cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking), [TypeScript result types](https://code.claude.com/docs/en/agent-sdk/typescript#sdkresultmessage), [Python reference](https://code.claude.com/docs/en/agent-sdk/python) | Which calls are counted, cumulative versus per-turn totals, restored totals, resets, missing results and enforcement timing. |
| Installation, updates and binary integrity | [Setup](https://code.claude.com/docs/en/setup) | Version pinning, update control, the signed release manifest and platform requirements. |
| Interrupt and termination | [Interrupt receipts](https://code.claude.com/docs/en/agent-sdk/typescript#sdkcontrolinterruptresponse), [SIGTERM behavior](https://code.claude.com/docs/en/headless#stop-a-run-with-sigterm), [hooks](https://code.claude.com/docs/en/agent-sdk/hooks) | Queued work, active handlers, graceful interruption, process death and the final result that may be lost. |

## Documented control surface

These names summarize the documentation reviewed on the date above, including
options not selected for Stewart. The [runtime contract](CONTRACT.md) owns the
implemented configuration. The native two-tool comparison demonstrates only
its recorded combination; verify a changed combination before relying on it.

- **Authentication:** the manager's harness-owned login, selected by a dedicated
  `CLAUDE_CONFIG_DIR`; no credential supplied by Stewart. Use non-bare mode.
  `claude auth status` reports `authMethod` and `configDirectory` without
  returning the credential. Require the selected directory and `claude.ai`
  method before model use; missing or conflicting observations refuse.
- **Ambient inputs:** `settingSources: []`, `strictMcpConfig: true`, an explicit
  process environment/working directory, and the documented controls for auto
  memory, connectors and background tasks. Documented switches include
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY`, `ENABLE_CLAUDEAI_MCP_SERVERS` and
  `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`. Managed/server-managed policy remains
  a separate input; a fresh directory does not remove server-managed policy.
- **Tool surface:** `tools: []`, an explicit `mcpServers` map, a narrowly scoped
  `allowedTools`, `permissionMode: "dontAsk"`, `permissionPrompts: "none"` and
  a `PreToolUse` hook. `allowedTools` is about approval; it is not the sole tool
  inventory control. Inspect actual inventory and behavior, including after
  compaction. For a small
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

For the native CLI candidate, `--restricted`, `--tools ""`,
`--setting-sources ""` and `--strict-mcp-config` are complementary controls.
The [CLI reference](https://code.claude.com/docs/en/cli-reference) documents
restricted mode from 2.1.248; it still loads managed policy. It is not an OS
sandbox. The subscription login, explicit MCP server and command hook composed
successfully in the native comparison with the three accepted built-ins. Bare
mode also disables explicitly configured hooks, so it is unsuitable for this
subscription route.

The [tool reference](https://code.claude.com/docs/en/tools-reference#endconversation-tool-behavior)
says `EndConversation` cannot be removed while other tools remain **on surfaces
where it exists**, but explicitly excludes noninteractive `-p` and SDK sessions.
Check the actual inventory; do not infer an extra tool from the CLI flag's
general caveat. A custom prompt plus controlled filesystem instructions still
needs a separate compaction/re-entry comparison.

## Subscription credentials

From the authentication, headless and legal pages linked above. These are
documented statements, not observed behavior.

- **Scripted use.** `claude setup-token` prints a one-year OAuth token for
  `CLAUDE_CODE_OAUTH_TOKEN`, documented for CI pipelines and scripts. It can
  only make model requests. A `/login` credential is stored in the macOS
  Keychain, or in `.credentials.json` under `~/.claude` or `CLAUDE_CONFIG_DIR`
  on Linux. The current authentication page also documents a macOS file fallback
  when a Keychain write fails; the configuration directory selects the Keychain
  entry as well. Do not inspect either credential store from Stewart.
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

Subscription authentication alone does not establish zero additional spending.
[Usage credits](https://support.claude.com/en/articles/12429409-manage-usage-credits-for-paid-claude-plans)
can keep requests running at consumption-based prices after included usage is
exhausted. The consumed native commissions required included usage only, and
the runtime contract retains that condition: the manager confirms paid overflow
is disabled; a quota stop ends the run. This confers no new invocation authority.

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

From the Agent SDK overview, the headless page and the
[official Rust MCP SDK](https://github.com/modelcontextprotocol/rust-sdk).

- **No official Rust SDK.** The Agent SDK ships for Python and TypeScript. For
  other languages the documentation says to run `claude -p` as a subprocess and
  read its JSON output.
- **Tools arrive through MCP.** The harness starts a stdio MCP server as its
  own child from `--mcp-config`. Under `-p` it normally waits for pending
  servers before the first turn, subject to startup timeout and cached-tool
  behavior. Its startup event, `system/init`, reports the model, tools, MCP
  servers and plugins.
- **`rmcp`** is the official Rust MCP SDK: client and server, several
  transports and the full protocol surface. A stdio tool server needs its
  `server` and `transport-io` features. Its async runtime and serialization
  dependencies would expand Stewart's graph. Resolve and inspect the graph
  for a selected version before choosing it; no dependency has been added.

## Native launch recommendation

The development adapter implements this mechanism on the strength of the native
comparison. The [runtime contract](CONTRACT.md) pins its exact launch and archive
formats, supplied inputs, enforcement and observation limits.
Use the pinned executable by absolute path, outside the repository,
with an empty working directory and a dedicated harness configuration. The
manager completes Anthropic's login flow there. Keep the actual home identity
for Keychain access; do not copy an existing login or read its secret.

Construct one explicit child environment inside the gated module. Retain only
required host values such as home, temporary directory, locale and a controlled
system PATH, plus the selected configuration and documented controls. Refuse
explicit provider/key inputs for the harness route; never inherit provider,
proxy, credential-helper or library-injection variables. Disable every update
path with `DISABLE_UPDATES=1`. Pin the model and configuration as well as the
binary, and refuse a changed binding. An invalid harness setup must not fall
back to the Messages API.

Apply `forceLoginMethod: "claudeai"` as a supporting control, not the sole
route check. Inspect the harness's credential-free authentication report and
effective startup metadata. Managed policy can outrank supplied settings;
unexpected sources, tools, plugins, routing or model selection stop the run.
An input the harness cannot expose remains unverified; a matching tool list
does not prove the absence of other instructions or policy.
`system/init` is evidence about what the harness reports. In both probes' first
cases it was captured only after input, following five seconds with stdin held open.
Do not use it as an assumed pre-request gate. A first synthetic check session
is preferable to exposing an audit while discovering the configuration; standing
check-session authority still needs its own bounded decision.

The [SDK's API-key-source field](https://code.claude.com/docs/en/agent-sdk/typescript#apikeysource)
distinguishes environment keys, helpers and Console login keys from `none`.
Require `none` at initialization alongside the earlier `claude.ai` auth status
and explicit environment. `none` alone does not prove subscription login; it
also covers other non-key authentication. A reported enabled paid-overflow
setting or quota rejection stops the probe. Absence of such an event does not
replace the manager's account-setting confirmation.

The existing API path accepts an opaque credential. A token prefix is not
proof of its class, and the adapter cannot certify arbitrary manager-supplied
bytes as an API key without a supported provider mechanism. The defensible
initial constraint is structural: the native harness owns the subscription
secret, the harness route has no credential argument, and it never calls the
direct adapter. Any stronger direct-route rejection claim needs a separately
specified discriminator and a synthetic firing control; it is not implemented
by the build feature.

The integration uses a standard-library CLI bridge with a stdio MCP relay. The
harness owns the relay child; `run` owns a private Unix-domain socket, the audit lock and
every durable mutation. The relay forwards original request bytes; `run`
captures them before interpretation and returns the response bytes. The relay
copies each available reply chunk to stdout and flushes it before reading
again, so partial frames can reach the peer while the socket remains open. Closing
authoring must be checked again at durable publication, even if a call entered
earlier. A missing relay or owner ends the session without another writer.

This keeps the shipped Rust dependency graph unchanged. A Python/TypeScript
SDK helper offers higher-level hooks and interruption but adds a language
runtime, package pin and another deployment component. It still wraps the same
harness and cannot supply missing provider evidence by itself. `rmcp` is a
maintained option; raw capture can sit below parsing, so it is not ruled out
by parsed handler arguments. For the narrow handshake/list/call surface, the
implementation uses the existing tolerant JSON scanner around strict core
arguments.
Use the [MCP stdio specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
and [tool protocol](https://modelcontextprotocol.io/specification/2025-11-25/server/tools),
including errors and notifications. The offline check below exercises the
protocol prototype. The [independent service driver](../../apparatus/driver/CLAUDE-CODE.md)
separately exercises the actual core integration, including preparation,
startup gating, recording, submission, delivery, continuation, recorder failure
and process-group stopping.

Native checks establish development behavior only. macOS has no Linux
`/proc`/non-dumpable boundary, and its existing lock and process-identity
fallbacks do not establish the Linux guarantees. Native synthetic tests exercise
owned-process supervision and witnessed termination; Linux qualification
exercises Linux's own mechanisms. Restricting the auditor's
tool surface does not make the entire harness a filesystem sandbox.

### Private helper transport for independent fixtures

An independent fixture can own the private sockets while invoking the gated
binary's actual helpers. `__stewart-cc-relay m` connects to the Unix socket
`m` relative to its working directory. It forwards stdin bytes unchanged and
shuts down the socket's write half at stdin EOF. Replies are forwarded unchanged
to stdout, with each available chunk flushed before another read; socket EOF
ends the reply stream. The helper does not parse MCP or own an audit.

`__stewart-cc-hook h` connects to socket `h`, reads stdin through EOF with an
8 MiB input bound, forwards those bytes unchanged, then shuts down the socket's
write half. The owner replies and closes its connection. The helper copies a
nonempty reply of at most 64 KiB unchanged to stdout. Each socket read has a
four-second timeout; this is not an overall invocation deadline. An empty or
oversized reply, connection/read failure or oversized input produces a diagnostic
and exit 2. Successful transport exits zero. The owner supplies the
LF-terminated hook JSON in the [runtime contract](CONTRACT.md#development-wire-and-process-contract);
the helper itself does not interpret it.

The fixture must retain independent request, reply and effect witnesses, own
its overall timeout and observe stopping. Using actual helpers exercises their
transport; fixture-owned sockets and simulated tool effects establish no core
publication, custody or service-conformance result.

## Offline Rust protocol check

`apparatus/claude-code/test_protocol.py` builds and exercises
`protocol_check.rs` without invoking Claude. The prototype links the existing
Rust crate for strict argument decoding and compiles the existing tolerant
provider scanner for outer MCP frames. It adds no dependency and changes no
service source. The scanner choice matters: MCP metadata can contain numbers
and strings that are not valid Stewart control arguments. Preserve those bytes;
apply strict control validation to the original argument span before dispatch.

The protocol was checked against the dated MCP
[base messages](https://modelcontextprotocol.io/specification/2025-11-25/basic),
[lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle),
[stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports),
[tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools),
[ping](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping)
and [cancellation](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation)
specifications on 2026-11-10. It supports initialization and version negotiation,
the initialized notification, ping, a fixed tool list and tool calls. It advertises
only tools, without tasks, sampling, resources, prompts or list changes. Unknown
methods receive method-not-found; the observed `server/discover` request therefore
allows the client's ordinary initialize fallback without adopting that extension.
Notifications receive no reply. Request IDs retain their type and original wire
representation, with repeated IDs refused within the session.

Malformed envelopes and unknown tools receive protocol errors. Invalid arguments
to the known synthetic tool receive a tool result with `isError: true`, preserving
the distinction from an unrecognized request. MCP's cancellation notification
does not undo a completed effect. A pending synthetic mutation can be cancelled
before publication, and authoring ending between admission and publication
prevents its effect. Those checks model ordering; they do not test the service's
durable log boundary.

The native run passed **9 Rust tests** (six existing scanner tests and three
publication/cancellation controls) and **14 Python process checks**, with no skips.
An independent peer retains its sent and received bytes outside the owner's
capture directory. The owner preserves chunks before framing or decoding,
including malformed, truncated and oversized inputs, and response bytes before
transmission. Controls exercise unavailable capture, argument refusal and failed
publication. An unrelated notification leaves the positive publication unchanged.
The real relay and owner processes preserve pipelined traffic byte for
byte. A simultaneous large write in each direction demonstrates progress under
backpressure; owner loss exits the relay with a failure even while stdin is open.

The service uses a duplex byte relay with serialized core execution. A reader
remains available for cancellation and ping while a handler is pending. The
prototype uses inherited Unix socketpairs; the service uses a private named
socket. The prototype does not establish peer binding,
archive failure recovery, close races in the actual core, orphan stopping,
Linux behavior or real-harness compatibility with the full auditor tool set.
Its frame/request-count bounds and one synthetic tool are apparatus limits,
not additional restrictions on Stewart's auditor contract. A transport wrapper
around `rmcp` remains possible if maintaining this narrow surface becomes costly.

## Unverified

Not demonstrated under the selected native launch arrangement:

- a supported configuration check before the first message is sent; the
  observed `system/init` ordering does not provide one;
- actual-adapter capture and failure recovery with the real harness; native
  synthetic service checks exercise the writer, without establishing Claude's
  behavior or complete provider accounting;
- real-harness behavior for relay loss, MCP cancellation, usage checkpoints
  across placements, and compaction with re-entry, its notice and the
  one-reminder policy; the independent synthetic service suite exercises each
  of these against the actual core, which says nothing about how the real
  harness issues calls, reports usage or delivers a notice;
- how the real harness issues several tool calls of one model response; the
  runtime answers a call that arrives while another is pending with an error;
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
harness session IDs. The adapter uses fresh-conversation continuation; it does
not use native resume.

The cost guide states that crash results may have zeroed totals. The documented
assistant-message fallback recovers main-loop input/cache counts but not output
or subagent totals. Whether there is enough supported observation to bound lost
internal-call consumption remains unresolved. The direct adapter's specified
per-request missing-response estimate cannot simply be assumed to apply here.

The documented USD budget uses a client estimate that can exceed its configured
value, and restored spend does not count toward that query's budget. The exact
`maxTurns` model-call boundary needs verification: establish whether each
control gates a call before consumption or detects an excess afterward. A
turn-start gate alone does not observe every internal model call. The Messages
adapter retains token/turn allowances. The development runtime instead uses
the [placement and deadline limits](CONTRACT.md#limits-usage-and-continuation);
neither is a dollar cap.

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

Pin and record the Claude Code version and initialization capabilities; an
SDK-based alternative would also need its SDK pin. Check version floors for interruption receipts, queue cancellation,
permission prompts, bare mode, reset messages and usage fields. Availability of
individual features does not establish that the whole configuration composes
correctly.

Tests need witnesses for internal-call accounting, effective authentication/tools,
usage across compaction, and stop/late-mutation behavior. Preserve independent
observations and failed variants through review under
[DEVELOPMENT](../../development/DEVELOPMENT.md#evidence-and-retention). Only separately
commissioned live work can settle provider behavior.
