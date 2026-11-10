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

The current contract places subscription login/routing outside Stewart's main
interface and uses explicit API or supported cloud-provider authentication
([CONTRACTS](CONTRACTS.md#run-and-continuation)). The principal's intended migration
target now includes a subscription connector. Resolve its relationship to that
boundary when selecting the integration; no connector design or authentication
mechanism is selected here. Common audit and custody terms should survive the
change while runtime-specific accounting and enforcement remain explicit.

The adapter preserves the [question-family meanings](CONTRACTS.md#question-families-and-open-inquiry)
and common custody/attribution contract. A family choice must never implicitly
grant execution, including for experimental inquiry.

Define manager-facing runtime observations within the
[evidence and judgment boundary](CONTRACTS.md#principles-and-scope). Additional
telemetry does not expand Stewart's responsibility into assessing the auditor's
understanding or intellectual completeness.

## 1. Feasibility and contract proposal

- [ ] Refresh [the runtime reference](docs/claude-code/RUNTIME-REFERENCE.md)
  against primary documentation for a selected pinned release. Its October 31
  configuration is untested and assumes explicit API/cloud credentials; establish
  the supported subscription route and its relationship to the current product
  boundary before adopting those controls.
- [ ] Compare a CLI bridge with a small SDK helper. State installation, versioning
  and platform implications for the current static Linux binary. The SDK is a
  candidate, not a settled dependency; generic multi-tenant hosting is not scope.
- [ ] Separate Stewart-owned custody and authoring guarantees from runtime
  access, accounting and stopping guarantees. For each runtime promise, identify
  the observation or enforcement available, its failure policy and the evidence
  needed to demonstrate it. Include ambient/managed configuration and tools
  outside Stewart's commissioned surface.
- [ ] Establish what consumption can be reported or defensibly bounded after
  compaction, internal calls or a lost final result. Do not assume Messages-loop
  turn counts or complete auditor telemetry are available. Missing totals are
  not zero consumption; estimated dollars cannot silently replace the current
  token/turn contract. Present unsupported promises and alternatives for decision.
- [ ] Distinguish automatic compaction within a placement from continuation
  after interruption. Initially retain one placement per harness session and
  Stewart's fresh-conversation continuation from its ledger. Harness-native
  resume remains a separate choice; determine how re-entry reaches recorded
  work after compaction without claiming to restore unrecorded understanding.
- [ ] Specify how preparation pins the selected runtime, configuration and
  guarantees. Resolve the meaning of a runtime choice before adding a selector.

**Done when:** this plan contains a concrete integration recommendation, its
limitations and the contract/packaging decisions needed from the principal.
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
[DEVELOPMENT checks](DEVELOPMENT.md#what-to-run-for-what-you-changed), including
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
the contract decision; do not transfer API results into a harness qualification
claim. Model answer quality is not the gate.

Complete this plan when the selected integration has a reviewed qualification
outcome and failures or unexercised work have explicit dispositions. Move enduring
contracts and operating instructions into their owning documentation and keep
results with their evidence, then delete the plan.
