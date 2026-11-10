# Claude Code as a peer auditor runtime

Add Claude Code as a peer auditor runtime while keeping audit semantics in
Stewart's Rust core. No Claude Code adapter or live conformance run exists.
This plan describes the work; it authorizes neither implementation nor starting
or resuming Claude, including model-consuming feasibility probes.

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

## 1. Feasibility and contract proposal

The current recommendation is a native CLI bridge with a stdio MCP relay back
to the sole Rust writer. The [runtime reference](docs/claude-code/RUNTIME-REFERENCE.md#native-launch-recommendation)
compares the SDK helper and protocol choices, specifies the proposed login and
launch controls, and separates documented mechanisms from unverified behavior.
The [initial probe proposal](docs/claude-code/FEASIBILITY-PROBE.md) is bounded to
synthetic native checks. Its outcome is needed before adopting the combination.

- [ ] Refresh [the runtime reference](docs/claude-code/RUNTIME-REFERENCE.md)
  when freezing the executable pin. Documentation was refreshed for proposed
  version 2.1.322; downloading and authenticating its manifest remains owed.
  Establish how ambient isolation, tools, hooks and compaction compose under
  the selected non-bare subscription route before adopting those controls.
- [ ] Decide first which process executes the auditor's tools. The harness
  starts a stdio MCP server as its own child, while only `run` holds
  [the audit's lock](docs/INTERFACE.md#46-the-active-lock-and-liveness) and
  writes its records. The child must relay each call to `run`, or `run` must
  serve the tools itself over another transport.
- [ ] Confirm the proposed synchronous tool relay with an offline protocol
  check before adoption. Compare its handshake, notifications and errors with
  the specification; demonstrate exact bytes captured before decoding, since
  [raw capture comes first](CONTRACTS.md#principles-and-scope). `rmcp` with a
  transport wrapper remains an alternative if the narrow relay proves costly
  to maintain; its parsed handlers alone do not rule out raw capture.
- [ ] State what the auditor actually sees under the harness. Its tools arrive
  through MCP under harness-assigned names, not as the pinned tool array, and
  a non-bare harness may add model-visible content, which
  [the Messages route forbids](docs/INTERFACE.md#62-requests-and-responses).
  Observations of auditor presentation made through the harness are specific
  to it.
- [ ] Separate Stewart-owned custody and authoring guarantees from runtime
  access, accounting and stopping guarantees. For each runtime promise, identify
  the observation or enforcement available, its failure policy and the evidence
  needed to demonstrate it. Include ambient/managed configuration and tools
  outside Stewart's commissioned surface. Identify host-specific process,
  credential and filesystem mechanisms, with native development checks and
  separate Linux qualification controls; do not transfer guarantees between them.
- [ ] Establish what consumption can be reported or defensibly bounded after
  compaction, internal calls or a lost final result. Do not assume Messages-loop
  turn counts or complete auditor telemetry are available. Missing totals are
  not zero consumption; estimated dollars cannot silently replace the current
  token/turn contract. Present unsupported promises and alternatives for decision.
  The documented crash fallback loses output/internal-call totals; subscription
  billing does not resolve that evidence gap. Propose an explicit unknown-usage
  and continuation policy rather than carrying the API estimates over.
- [ ] Distinguish automatic compaction within a placement from continuation
  after interruption. Initially retain one placement per harness session and
  Stewart's fresh-conversation continuation from its ledger. Harness-native
  resume remains a separate choice; determine how re-entry reaches recorded
  work after compaction without claiming to restore unrecorded understanding.
- [ ] Specify how preparation pins the selected runtime, configuration and
  guarantees. Decide whether a passing check session binds the binary/config
  pair, or whether startup metadata can serve as a demonstrated pre-input gate.
  A standing check-session policy needs bounded permission and its own usage
  record, outside the audit's allowances. Resolve the meaning of a runtime
  choice before adding a selector.

**Done when:** this plan contains a concrete integration recommendation, its
limitations and the contract and installation decisions needed from the principal.
Keep technical controls and dated sources in the runtime reference. Separate
documented capabilities from demonstrated behavior; propose any necessary live
probes with bounded scope and budget before running them.

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
