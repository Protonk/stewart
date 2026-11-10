# Build configuration for the Claude Code development adapter

The released binary carries the Messages API adapter and nothing of Claude Code.
A separate, default-off build carries the Claude Code adapter for local
development and testing. This plan sets up that build, its checks and its
credential route. It authorizes neither adapter implementation nor starting
Claude through any harness.

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
  credential reaches the provider only through the unmodified `claude` binary.
  Stewart's Messages API adapter never carries one. How this is enforced is
  part of the research below.
- **The harness owns its login.** The manager signs in through Anthropic's own
  flow, using a dedicated harness configuration. Claude manages its credential
  storage; Stewart never receives or reads the subscription credential. The
  service's descriptor route is not used for that login.
- **Native development, Linux qualification.** Iterate on the development Mac
  with Apple silicon, extending the existing `aarch64-apple-darwin` build and
  [native test workflow](development/DEVELOPMENT.md#building-and-testing-natively).
  Use Linux containers to validate the Linux builds and qualify their behavior.
  Native macOS remains a development environment; this adds no macOS product
  release or qualification claim.

## Launch arrangement to verify

[The runtime reference](docs/claude-code/RUNTIME-REFERENCE.md#subscription-credentials)
holds the documented facts and their dates. Its
[native launch recommendation](docs/claude-code/RUNTIME-REFERENCE.md#native-launch-recommendation)
specifies the proposed credential isolation, explicit environment, refusal
policy and host limits. The
[probe proposal](docs/claude-code/FEASIBILITY-PROBE.md) supplies the first
bounded comparison; neither the proposal nor this plan permits starting Claude.

The proposed arrangement uses one pinned absolute executable, a dedicated
harness-owned login, an explicit child environment and no fallback to the
Messages API. Hash the executable and launch configuration; refuse a changed
binding. macOS observations apply to development, while Linux qualification
exercises Linux's process and filesystem mechanisms separately. None of these
launch controls is implemented by the feature boundary.

## Remaining checks and decisions

The feature, module boundary, help notice, third Cargo configuration and
container marker checks are implemented. [The crate guide](service/README.md#development-runtime-build)
owns how to build/check them and explains the distinct writer and qualification
limits. The dependency graph is unchanged. The qualifier reads the added
expected exits and extra binary digest without a schema change; no historical
record has been rewritten.

All three host Cargo configurations pass, including loopback cases, with no
socket skips. Their unchanged tests exercise the Messages API path in the
gated build. Optimized native binaries pass the absence/absence/presence
marker checks; help matches apart from the gated notice. Keep
`.tmp/claude-code-setup/host-native.cqIqZX/` and the other check outputs in
`.tmp/claude-code-setup/` through review. The earlier sandbox socket failure
and skipped cases are superseded by the host runs; Linux remains unqualified.

- [ ] Run the toolchain and container acceptance checks required by
  [DEVELOPMENT](development/DEVELOPMENT.md#what-to-run-for-what-you-changed),
  on the committed change when the principal schedules them. Retain and extract
  both architectures' results. The development binary is a marker control;
  the independent driver still evaluates the release and fault/sabotage binaries.
- [ ] Resolve whether the proposed structural credential boundary satisfies
  the harness-only requirement. The harness owns its secret and cannot fall
  back to the direct adapter; classifying arbitrary bytes supplied to the
  existing API route requires a supported discriminator that is not yet known.
  Do not claim that a token-prefix test enforces this.
- [ ] Freeze the authenticated executable pin and assign the remaining live
  login/launch comparisons to the runtime work. The proposed manifest could
  not be downloaded here; its signature and binary digest remain unverified.

**Done when:** a container run shows the markers absent from the release and
test binaries and present in the gated one; the three cargo configurations
pass natively; the leaf documentation covers building and checking; and the
selected login and launch arrangement has a concrete enforcement and check
design, with any remaining live verification assigned to the runtime work.
The feature comment and crate guide retain the build guidance; delete this plan
when the remaining checks and decisions are complete.
