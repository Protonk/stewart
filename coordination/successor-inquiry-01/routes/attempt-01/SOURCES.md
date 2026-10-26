# Public capability source notes

Retrieved 2026-10-26 through the web reader. These are official public
documentation observations, not inspection of the installed CLI and not
executed enforcement. Pages are rolling documentation; no immutable page
revision or complete document version was supplied. Version numbers below
describe individual documented features, not the local installation.

## S1 — Native supervisor and descendants

URL: https://code.claude.com/docs/en/agent-view#the-supervisor-process

Sections: “The supervisor process”, “Manage sessions from the shell”,
“Settings and provider”; reader lines 707–777 and 630–641.

Bounded exact excerpts: “Exited unexpectedly while the supervisor is running:
the supervisor restarts the process.” The documented exit-handoff switch is
described as “stop all of it with the process instead”.

Source notes: background sessions survive terminal closure. The page describes
background shell commands, dynamic workflows and background subagents being
carried to a replacement process; some other activity stops. It names
`CLAUDE_CODE_DISABLE_BG_EXIT_HANDOFF=1` for changing that carryover. Native job
files are expressly unstable. Shell stop, attach, logs and restart interfaces
exist. The cited supervisor paragraph supplies no minimum version for the
switch and no independently measured descendant guarantee.

Inference/probe boundary: this switch is a proposed variable for testing
carryover, **not** evidence it disables automatic process restart or all forms
of descendant survival. Do not infer either property from its name. Determine
which launched mode it affects and observe descendants independently.

## S2 — Documented read precedence differs from the frozen account

URL: https://code.claude.com/docs/en/sandboxing#configure-sandboxing

Sections: “Configure sandboxing” (reader lines 318–339), “What runs outside
the sandbox” (131–140).

Bounded exact excerpt: “the rule with the narrower path applies”.

Source notes: the page's examples reopen a directory inside a denied home
while retaining a narrower denial inside a broad allow. It distinguishes
shell-command sandboxing from built-in tools, MCP and hooks, and points to
whole-process isolation for a common boundary. The precedence paragraph does
not name the release where the behavior changed.

Frozen-source contrast: `250d494:src/stewart/auditor_scope.py`, schema comment
and `validate_scope`, says the qualified harness let the broader deny win.
That is evidence of the baseline's account; this document does not re-run its
qualification or revise it. The successor must pin the CLI/OS/settings and
compare overlapping grants before relying on either rule.

## S3 — CLI construction, output and configuration

URL: https://code.claude.com/docs/en/cli-reference

Section: “CLI flags”, notably `--restricted`, `--safe-mode`, `--tools`,
`--strict-mcp-config`, `--session-id`, `--bg`, `--print`, `--output-format`
and `--json-schema` (reader lines 99–187).

Source notes: restricted mode confines built-in file tools to working
directories, limits loaded settings, and requires explicit reintroduction of
command tools; its documented minimum is v2.1.248. Safe mode disables many
customizations but leaves some managed-policy commands active. Background
launch and print mode cannot be combined. Print mode offers structured output.
A supplied conversation UUID is supported; this does not establish how a
background-job ID binds to it. None of these flags promises Stewart custody.

## S4 — Whole-process isolation options

URL: https://code.claude.com/docs/en/sandbox-environments

Sections: “Compare sandboxing approaches”, “Custom container”, “Virtual
machine” (reader lines 47–60, 165–183).

Source notes: Anthropic documents whole-process sandbox runtime, container and
VM arrangements; custom OCI/Docker images can carry their own mount/network
policies. Model-provider transmission still occurs under isolation. This is
vendor deployment guidance, not a tested Stewart configuration or a selected
host. Container/VM contents, credential route and network policy remain work.

## S5 — Durable container identity and detached execution

URL: https://docs.docker.com/engine/containers/run/

Sections: “Image digests”, “Foreground and background”, “Container
identification”, “Container networking” (reader lines 64–145).

Source notes: images may be pinned by digest; detached containers do not
occupy the invoking terminal. The daemon assigns a container ID, distinct from
an image identity or caller-chosen name. Networking is enabled by default.
These are mechanisms a proposed adapter must bind and constrain; the daemon's
reply alone does not make an uncertain create/start safe to repeat.

## S6 — Mount qualifications

URL: https://docs.docker.com/engine/storage/bind-mounts/

Sections: “Considerations and constraints”, “Recursive mounts”, “Configure
bind propagation” (reader lines 49–62, 231–249).

Source notes: bind mounts are writable by default; read-only is explicit.
They refer to the daemon host; Docker Desktop's daemon runs in a Linux VM.
Submounts are included by default. Recursive read-only support needs Linux
5.12 or later; submount exclusion is another documented option. Desktop does
not support mount propagation. Neither a read-only mount nor a content hash
freezes changes made through a host-side writer.

## S7 — Container stop and restart are separate controls

URLs:

- https://docs.docker.com/reference/cli/docker/container/stop/
  (“Description”, “Stop container with timeout”, reader lines 13–34).
- https://docs.docker.com/engine/containers/start-containers-automatically/
  (“Use a restart policy”, reader lines 26–36).

Source notes: Docker stop sends the main process its configured stop signal
and escalates after the configured grace period. Restart policy `no` disables
automatic container restart. Live restore is a separate behavior. A proposed
route must pin both rather than interpret terminal disconnect as termination.
The stop page alone does not demonstrate every permitted descendant and
external effect has ended.

## S8 — Host process-tree witness

URL: https://docs.kernel.org/admin-guide/cgroup-v2.html

Sections: “[Un]populated Notification” and “Core Interface Files”, entries
`cgroup.kill`, `cgroup.events` (reader lines 134–140, 480–489).

Source notes: the documented kill operation targets the cgroup subtree and
handles concurrent forks/migrations; `populated` reports whether that subtree
has live processes. The kill operation is unavailable in a threaded cgroup.
This suggests a host-owned stop/witness mechanism; it requires checking the
actual kernel, delegation, group lifetime and absence of routes to escape the
group. It does not describe external services or already committed effects.
The page carries an October 2015 origin date, not an immutable current
revision or a promise this laptop has the feature.

## S9 — Engine control is privileged authority

URL: https://docs.docker.com/engine/security/#docker-daemon-attack-surface

Section: “Docker daemon attack surface” (reader lines 49–58).

Source notes: the engine's mount/control authority can expose host resources;
the documentation restricts daemon access to trusted operators. A manager
given the engine socket cannot be treated as isolated from live audit storage
merely because the auditor is in a container. The proposed manager boundary
must be enforced separately from auditor isolation.

## S10 — SDK is an adapter option, not a supplied stop proof

URLs:

- https://code.claude.com/docs/en/agent-sdk (“Compare the Agent SDK to other
  Claude tools”, reader lines 104–111).
- https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode
  (“Streaming Input Mode”, “Limitations”, reader lines 111–125, 280–287).

Source notes: the SDK embeds the Claude Code loop in a process the developer
operates. Streaming input offers interruption; single-message input does not
offer real-time interruption. These pages do not establish descendant
termination, durable control after host loss or an external manager callback.
An SDK wrapper would therefore retain the same containment and custody debts.

## S11 — Settings composition

URL: https://code.claude.com/docs/en/settings

Sections: “Settings files and who they affect”, “Settings precedence”.

Source notes: user, shared-project, local-project and managed settings have
different scope and precedence. Effective configuration needs recording in a
probe. This page was background context; no claimed grant enforcement rests
on its configuration descriptions.

## Retrieval failures and excluded material

The official page https://platform.claude.com/docs/en/agent-sdk/typescript
failed the reader's content-size limit (over 4 MiB). No capability conclusion
is drawn from it. The linked replacement at
https://code.claude.com/docs/en/agent-sdk/typescript failed the same way.
https://code.claude.com/docs/en/settings-reference also exceeded that limit;
its `.md` variant returned an unsupported Markdown content type. The old SDK
`.md` URL redirected to the usable overview cited as S10. Search returned
third-party mirrors and commentary; none are supporting sources. No repository
content was used in public queries.
