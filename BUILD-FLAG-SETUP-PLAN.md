# Build configuration for the Claude Code development adapter

The released binary carries the Messages API adapter and nothing of Claude Code.
A separate, default-off build carries the Claude Code adapter for local
development and testing. This plan sets up that build, its checks and its
credential route. It authorizes neither adapter implementation nor starting
Claude through any harness.

## Decided

- **The gate covers the whole adapter.** One default-off cargo feature (working
  name `claude-code`) compiles every line of the adapter. The release remains
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

## Remaining: enforce the launch arrangement

[The runtime reference](docs/claude-code/RUNTIME-REFERENCE.md#subscription-credentials)
holds the documented facts and their dates. Specify and check how the selected
login and platform work together. A live probe needs its own bounded permission.

- **Credential isolation.** Establish how the dedicated configuration selects
  Claude's own stored login on macOS, including Keychain behavior, without
  exposing it to Stewart. Specify missing or expired login handling and what
  is kept out of arguments, environment and diagnostics. Check these properties
  against the selected harness version rather than assuming the existing
  [descriptor route](docs/INTERFACE.md#61-provider) supplies them.
- **Platform differences.** Compare native launch and observation controls with
  [the existing Linux launcher](apparatus/sanity/LAUNCHER.md). Identify which
  process, credential and filesystem protections need different mechanisms or
  have narrower development guarantees on macOS. Linux validation must exercise
  its own mechanisms; a native observation cannot establish them.
- **No silent route.** The harness prefers an API key over a subscription token
  when both are present, and without bare mode falls through to any login it
  finds. Specify the refusals that make the route in use the route intended.
- **Effecting the harness-only constraint.** Determine what makes it hold in
  the gated build and not merely by intention: what the Messages API path
  refuses, what the gated code may read or pass on, and the check, with its
  firing control, that would catch a subscription credential on the direct
  route.
- **Harness identity.** Candidate: pin one harness version, take its digest
  from [the signed release manifest](docs/claude-code/RUNTIME-REFERENCE.md#binary-identity-and-updates),
  and have the gated build hash the executable it is about to run, refuse a
  mismatch and record path, digest and version with the placement. The
  manifest signature is checked in the launch apparatus, not in Stewart. A pin
  means launching the versioned file with every update path disabled, through
  an absolute path, an explicit child environment and a controlled
  configuration directory. The claim this supports is that Stewart ran a file
  matching the pinned release under that environment; it is not proof against
  the machine's owner.
- **Check session.** Candidate: a short model-consuming session that exercises
  the real harness, configuration and credential, covering what a digest
  cannot. Bind each result to the binary digest and a digest of the launch
  configuration, and refuse a placement without a passing result for the
  current pair, so the session is owed only on first use and after either
  changes. It needs a firing control, such as a removed hook or a wrong
  credential that must fail it. Its usage is recorded apart from the audit's
  allowances and is not zero. It needs the principal's standing, bounded
  permission. A check session can itself fetch an update that applies at the
  next start, so it depends on the pin above. A cheaper variant inspects the
  harness's startup report in the audit session itself;
  [whether that is possible is unverified](docs/claude-code/RUNTIME-REFERENCE.md#unverified).

## Tasks

- [ ] Add the feature to `service/Cargo.toml` with a comment stating what it
  gates and the description rule above. Create the gated module boundary:
  outside it, only a `cfg`-selected entry point refers to the adapter.
- [ ] Make the gated build identify itself in reachable code, proposed as a
  line in `stewart help`. A gated binary is a [distinct writer](docs/INTERFACE.md#47-the-writer)
  whose audits the release cannot continue or close; it should never be
  mistaken for a release.
- [ ] Add a third cargo configuration with its own target folder,
  `CARGO_TARGET_DIR=target-local cargo test --locked --offline --features claude-code`,
  and describe it in `service/README.md`. Combine it with the fault and
  sabotage features only when gated code gains fault points. Add the changes
  that need it to [the check table](development/DEVELOPMENT.md#what-to-run-for-what-you-changed),
  which is leaf guidance and may name the feature.
- [ ] Extend `apparatus/container/acceptance-inner-build.sh` and
  `apparatus/acceptance.sh` with a gated build and one marker list. The release
  and test binaries must lack every marker; the gated binary is the firing
  control and must contain them. Link-time optimization removes unreferenced
  strings, so a marker must be reachable. Start with the self-identification
  and add each string the adapter cannot work without, such as the harness
  executable name and credential variable names. Check what a further binary
  in the evidence folder means for `apparatus/qualified.py extract`.
- [ ] Show invariance: the release-behavior tests pass unchanged in the gated
  configuration, so the feature alters nothing on the Messages API path.
- [ ] State in the leaf documentation that gated-build runs are iteration. They
  qualify neither the release binary nor a model, and an observation under one
  credential route says nothing about another.

**Done when:** a container run shows the markers absent from the release and
test binaries and present in the gated one; the three cargo configurations
pass natively; the leaf documentation covers building and checking; and the
selected login and launch arrangement has a concrete enforcement and check
design, with any remaining live verification assigned to the runtime work.
Move the description rule to the comment beside the feature, then delete this plan.
