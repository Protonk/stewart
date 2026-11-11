# Build configuration for the Claude Code development adapter

The released binary carries the Messages API adapter and nothing of Claude Code.
A separate, default-off build carries the Claude Code adapter for local
development and testing. This plan owns that build, its checks and its credential
boundary. The principal has authorized the adapter implementation under its
decided contract; no further Claude invocation is authorized.

## Decided

- **The gate covers the whole adapter.** The default-off cargo feature
  `claude-code` compiles every line of the adapter. The release remains
  the featureless build, so [the distributed boundary](CONTRACTS.md#run-and-continuation)
  holds by construction and the release build commands do not change. One
  function inside the gate builds the credential environment handed to the
  harness, so a later decision to ship any route moves a boundary instead of
  untangling one. Shipping any part of the adapter is a separate decision.
- **Where it is described.** The code stays in the repository. The root README
  and AGENTS say nothing of the feature, the seam or the adapter. Leaf
  documentation carries only what building and checking it need. There is no
  enablement or conversion guide. Code and data that happen to sit at the root
  need no special treatment. The principal owns the underlying policy question
  and may revise this posture.
- **Subscription credentials travel only through the harness.** A subscription
  credential used by this runtime reaches the provider through the unmodified
  `claude` binary. The accepted boundary is structural: this adapter never
  supplies that credential to the Messages API route. It does not classify
  arbitrary opaque bytes supplied independently to the API route.
- **The harness owns its login.** The manager signs in through Anthropic's own
  flow, using a dedicated harness configuration. Claude manages its credential
  storage; Stewart accepts no subscription credential input and does not read
  that storage. The service's descriptor route is not used for that login.
- **Native development, Linux qualification.** Iterate on the development Mac
  with Apple silicon, extending the existing `aarch64-apple-darwin` build and
  [native test workflow](development/DEVELOPMENT.md#building-and-testing-natively).
  Use Linux containers to validate the Linux builds and qualify their behavior.
  Native macOS remains a development environment; this adds no macOS product
  release or qualification claim.

## Selected launch arrangement

[The runtime reference](docs/claude-code/RUNTIME-REFERENCE.md#subscription-credentials)
holds the documented facts and their dates. Its
[native launch recommendation](docs/claude-code/RUNTIME-REFERENCE.md#native-launch-recommendation)
explains the selected credential isolation, explicit environment, refusal
policy and host limits. The [runtime contract](docs/claude-code/CONTRACT.md)
owns the implemented arrangement; the two feasibility commissions are closed.
This plan permits no additional Claude invocation.

The selected arrangement uses one pinned absolute executable, a dedicated
harness-owned login, an explicit child environment and no fallback to the
Messages API. Hash the executable and launch configuration; refuse a changed
binding. macOS observations apply to development, while Linux qualification
exercises Linux's process and filesystem mechanisms separately. The gated
adapter implements the launch controls and has passed native synthetic service
checks. Real-harness service conformance and Linux enforcement remain unqualified.

## Remaining checks and decisions

The feature, module boundary, help notice, third Cargo configuration and
container marker checks are implemented. [The crate guide](service/README.md#development-runtime-build)
owns how to build/check them and explains the distinct writer and qualification
limits. The dependency graph is unchanged. The qualifier reads the added
expected exits and extra binary digest without a schema change; no historical
record has been rewritten.

The integrated adapter passed all three host Cargo configurations, including
loopback cases, and the four optimized markers passed absence/absence/presence
checks in release, fault/sabotage and development builds. The current native
outputs are in `.tmp/document-harmonization/host.VxyhfJ/`. Keep these and the
earlier `.tmp/claude-code-adapter/` and `.tmp/claude-code-setup/` outputs through
review. Earlier failures and skips remain retained; Linux remains unqualified.

- [ ] Run the toolchain and container acceptance checks required by
  [DEVELOPMENT](development/DEVELOPMENT.md#what-to-run-for-what-you-changed),
  on the committed change when the principal schedules them. Retain and extract
  both architectures' results. The development binary is a marker control;
  the independent driver still evaluates the release and fault/sabotage binaries.
  This qualifies the build boundary, not execution of the gated runtime.

The principal accepted the structural credential boundary on 2026-11-10:
the harness owns its secret, the harness route refuses credential arguments and
never falls back to the direct adapter. There is no classification claim for
arbitrary bytes supplied separately to the API route. The
[development runtime contract](docs/claude-code/CONTRACT.md#arrangement-and-observation)
owns this decision; implementation and verification must enforce it.

The [reviewed native comparison](docs/claude-code/RUNTIME-REFERENCE.md#reviewed-native-comparison)
supplies the launch observations for the credential-boundary decision. It does
not qualify Linux enforcement. The accepted structural boundary makes no
direct-route credential-classification claim.

**Done when:** a container run shows the markers absent from the release and
test binaries and present in the gated one; the three cargo configurations
pass natively; the leaf documentation covers building and checking; and the
selected login and launch arrangement has a concrete enforcement and check
design, with any remaining live verification assigned to the runtime work.
The feature comment and crate guide retain the build guidance; delete this plan
when the remaining checks and decisions are complete.
