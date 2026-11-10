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

## Open: the credential route

The principal has deferred who holds a subscription credential, pending
research. [The runtime reference](docs/claude-code/RUNTIME-REFERENCE.md#subscription-credentials)
holds the documented facts and their dates. Bring back options with evidence
for each of these; a live probe needs its own bounded permission.

- **Holder.** The launch environment supplies the credential to the harness
  and Stewart never reads it, or Stewart receives it through the existing
  [descriptor route](docs/INTERFACE.md#61-provider). State what each means under
  the documented credential terms and for the hidden-entry and no-secret-in-
  environment properties the current route provides.
- **Where the gated build runs.** A native development machine with a stored
  login, or a Linux container given a token or credentials file. Compare each
  with the discipline of [the existing live launcher](apparatus/sanity/LAUNCHER.md).
- **No silent route.** The harness prefers an API key over a subscription token
  when both are present, and without bare mode falls through to any login it
  finds. Specify the refusals that make the route in use the route intended.
- **Effecting the harness-only constraint.** Determine what makes it hold in
  the gated build and not merely by intention: what the Messages API path
  refuses, what the gated code may read or pass on, and the check, with its
  firing control, that would catch a subscription credential on the direct
  route.

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
credential route is decided by the principal. Move the description rule to the
comment beside the feature, then delete this plan.
