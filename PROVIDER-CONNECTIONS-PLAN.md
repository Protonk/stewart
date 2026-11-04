# Reusable provider connections

Let a user connect a provider once, see which account will pay, and run an
authorized series of inquiries without repeatedly entering a credential.
Authentication and secret storage should use established provider or operating
system facilities. Stewart owns the selected connection, private handoff and
bounded use, not a new identity service or credential vault.

This plan owns the connection design, implementation and verification work.
Current behavior remains in [CONTRACTS](CONTRACTS.md#run-and-continuation),
[INTERFACE 6.1](docs/INTERFACE.md#61-provider) and the
[launcher instructions](apparatus/c10/README.md). Persistent connections and
renewal are not implemented. Planning checks are retained in
`.scratch/provider-connections-plan-01`.

## Scope and authority

Implement one reusable connection path for the current Anthropic Messages API
runtime and the present macOS host-to-Linux-container launch environment.
Preserve direct API-key supply through the existing descriptor and explicit
environment routes. A user supplying a key need not create a saved connection.
The reusable path must remove routine entry from both launches and later evidence
collection, rather than merely cache a key for one process.

Define provider-specific routes without inferring credentials from a model name
or treating every provider's subscription policy as the same. Implementing a
Codex/OpenAI or Claude Code auditor runtime, a hosted service, a general identity
broker and additional operating-system credential stores is outside this scope.
Document the supported platform and packaging requirements; the new host path
does not establish support on every release platform.

Connection access is separate from authority to spend. Login, refresh and status
must not launch an inquiry or silently make a model-consuming health check.
Model calls require the principal's bounded authorization. A saved connection
does not authorize repeat trials, continuations or budget extensions. Routine
credential reuse should not add a manual step to an already authorized series.

## Connection contract to establish

| Concern | Required behavior |
| --- | --- |
| Selection | Explicit provider, authentication route and account/workspace binding. Show the billing route before launch; distinguish a manager-supplied label from provider-confirmed identity. |
| Configuration | Save non-secret connection metadata and a reference to the established credential mechanism. Do not put credentials in question files, arrangements, packets or ordinary configuration. |
| Authentication | Let the provider's supported flow or the chosen credential store own login, persistence and renewal. Prefer a narrow integration over implementing OAuth or encryption from scratch. |
| Private use | Keep credential acquisition and transport outside the auditor's tools and development-agent outputs. The transport process may necessarily hold an access credential; do not describe this as zero credential handling. |
| Lifecycle | Expose connect/select, safe status and disconnect behavior. State whether disconnect removes local access, revokes remote access, or both, and report revocation that could not be confirmed. |
| Failure | Report locked storage, expired/revoked access, missing helper, wrong account and unavailable provider distinctly. Do not silently change account, provider, credential source or billing route. |

Bind a connection to its intended provider endpoint and account. Resolve
conflicting explicit sources deterministically, preserving refusal of ambiguous
sources. A changed ambient default must not select a different paying account.
Keep alternate-endpoint testing explicit and separate from real connections.

The principal will enter secrets only through the selected trusted setup flow,
not through chat or agent tool output. Define and test the actual access boundary
around saved credentials and helper invocation. A credential file readable by an
agent's arbitrary shell is not isolated merely because the model prompt omits
it. Keep the host-administrator trust limit explicit; do not promise complete
memory erasure or protection from the administrator.

## Provider routes and dated evidence

Primary documentation checked on 2026-11-04 supplies candidates, not evidence
that Stewart can use them correctly. Recheck it when selecting pinned versions.

- **Anthropic Console login:** the official `ant` CLI supports browser login,
  workspace-bound profiles and logout. Its documented storage uses credential
  files; this is not an OS-keychain guarantee. Interactive login is described for
  local development and scripting; noninteractive workloads, including servers
  and containers, are directed to workload federation. Resolve applicability to
  our host-launched container and the permissions actually granted before
  selecting this route. Workspace scope alone does not establish inference-only
  authority. [CLI authentication](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/authentication).
- **Direct API use of that login:** Anthropic documents obtaining a refreshed
  access token through the CLI for other HTTP clients, using an Authorization
  bearer header. This is a candidate credential-provider interface; its
  secret-bearing output must go directly to a private consumer, never a recorded
  shell result. [CLI scripting](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/scripting#authenticate-curl-requests-with-cli-credentials).
- **Stored Anthropic API key:** an established OS credential store is the
  alternative if Console login does not fit the supported environment,
  permission boundary or evidence lifecycle. Use platform APIs through a
  maintained integration; do not build an encrypted file format. Preserve
  one-use key supply independently of whether a reusable connection is saved.
- **OpenAI:** official Sign in with ChatGPT documentation describes eligible
  plan usage for locally running open-source tools and personal projects;
  paid or remotely hosted apps require access approval. Record this as a
  possible future route, with API-key access also available to a future adapter.
  This does not authorize borrowing another client's cached login or establish
  Stewart runtime support. [Official OpenAI integration guide](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt).
- **Claude subscriptions:** third-party Claude.ai credential intermediation is
  distinct from a user authenticating in an unmodified Claude Code client.
  Keep the current direct API runtime on a supported API route. Evaluate any
  future client-hosted integration under its own documented conditions.
  [Anthropic authentication boundaries](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use).

## Remaining work

### 1. Select the mechanism and freeze its contract

- [ ] Inspect the supported official helper and OS-store options with synthetic
  credentials. Pin the selected dependency/version, installation and update
  requirements, storage location, permissions, token lifetime and failure modes.
  Establish whether the official Console route fits; otherwise select the
  established-store API-key route and record the reason. One demonstrated
  reusable route is required; both need not be implemented.
- [ ] Specify the smallest connection interface: selection, non-secret status,
  setup and disconnect, plus a private credential-provider boundary. Resolve
  access from the host runner, development-agent shell and Linux worker; avoid
  broad credential-directory mounts or a general token-retrieval tool. Record
  residual trust and packaging requirements before implementation.
- [ ] Define permissions actually needed, account/workspace verification,
  endpoint binding, conflicting-source behavior and connection changes during
  an active run. If a provider grant is broader than Stewart's use, report the
  scope honestly and use the narrowest supported grant; do not claim restrictions
  the provider does not enforce.
- [ ] Define renewal and disconnect semantics. Serialize renewal where the
  provider rotates tokens; cover expiry between requests and between launches.
  Separate credential refresh from request retry, preserving attempt counts,
  cumulative usage and uncertain-response accounting. Loss of access must not
  start browser prompts inside an unattended run or silently replay an inquiry.
- [ ] Align CONTRACTS, INTERFACE, ACCEPTANCE, help and operator documentation
  with the selected behavior. Make persistent storage ownership and any changed
  authentication headers explicit. Current API-key-only wire rules and the
  one-credential-per-placement account cannot silently stand for bearer renewal.
  Bring changes to protected obligations or broader authority to the principal.

### 2. Integrate ordinary use and the retained apparatus

- [ ] Implement the selected connection through a narrow adapter while preserving
  direct key input and credential-free preparation/commissioning. Keep provider
  identity and connection choice separate from the auditor's material and tools.
  Do not add subscription login to an unsupported runtime.
- [ ] Adapt the current [launch path](apparatus/c10/c10.py) and shared
  [session launcher](apparatus/sanity/launch.py) to acquire credentials privately
  after verified intake. Preserve the protected process setup and bounded
  handoff. Restrict helper output, errors and diagnostics so secrets cannot enter
  argv, normal transcripts, captured environments or container configuration.
- [ ] Support repeated authorized launches and follow-up collection after a
  launcher restart without routine terminal input. Make a locked store or
  required reauthentication actionable at the connection level. Credential reuse
  alone must not introduce automatic audit continuation, broader batches or
  weaker close/confirmation rules.

### 3. Preserve evidence across credential changes

The current [collection operation](apparatus/c10/operations.py) requires the
original key for a private HMAC check and byte scan. Fetching a newly refreshed
token cannot satisfy that check or detect an older token reflected in evidence.
Resolve this before claiming that persistent login supports later collection.

- [ ] Specify how every credential actually used is covered by reflection checks
  and later export checks, including responses arriving after rotation. Choose
  protected per-run recognition material using an established storage mechanism,
  or demonstrate an equivalent complete check; a digest alone does not enable
  the current literal/escaped-byte scan. Keep recognition data private and out
  of ordinary archives and exports.
- [ ] Distinguish revoking future provider access from disposing of recognition
  material needed for retained evidence. Define behavior after restart,
  credential replacement, logout and unavailable storage. Withhold export when
  the required checks cannot be completed; do not demand copying an old secret
  into chat or rewrite old captures to make the new mechanism fit.
- [ ] Preserve exact private captures, derived redaction, reflection stopping,
  independent witnesses and immutable export snapshots. Token renewal must not
  weaken the checks merely because one placement used more than one credential.
  Give historical run collection an explicit disposition under its original
  records; do not migrate old receipts or claim new checks ran in the past.

### 4. Verify the supported path

- [ ] Exercise the actual helper/store boundary with synthetic values, including
  initial setup, reuse after restart, locked/unavailable storage, missing or
  changed helper, conflicting sources, wrong account/workspace, expiry,
  revocation, failed renewal and disconnect. If the chosen route renews tokens,
  test concurrent refresh and a run spanning renewal. If it uses a static key,
  test explicit rotation and later collection of evidence made with the old key.
- [ ] Demonstrate at least two separate launches and later collection with no
  routine credential entry after setup. Include an independent witness for
  which synthetic credential reached the fake provider and observers for the
  stated process/file access boundary. Test actual access, not just configured
  flags or an absent secret in stdout.
- [ ] Extend [credential acceptance](ACCEPTANCE.md#credential-handling) with
  firing controls, differing cases and invariance cases. Exercise literal and
  JSON-escaped reflections, malformed responses, secret-bearing helper errors,
  stale credentials and incomplete recognition history. Preserve direct-key
  input behavior, ordinary clean exports and unchanged inquiry/custody behavior.
- [ ] Run all applicable [DEVELOPMENT checks](DEVELOPMENT.md#what-to-run-for-what-you-changed)
  and preserve outputs. Service/interface edits require both Cargo
  configurations; independent driver edits require its self-test and case list.
  C10/shared-launcher edits require the named Python suites and native
  fake-provider/operator checks. Split service and driver authorship under
  [AGENTS](AGENTS.md#preserve-independent-evidence) before reading implementation
  for a task that needs both.
- [ ] After committing implementation, have the principal run the applicable
  Linux acceptance suite and retained launcher rehearsal. Pin the exact binaries,
  helper, store, source and image; record host and Linux observation scopes
  separately. Existing credential qualification does not transfer to the new
  path. Update the qualification record and product status from actual results.
- [ ] Prepare a minimal, separately authorized real-provider check of the chosen
  route and its billing/account binding. Distinguish offline mechanism evidence
  from live compatibility. Any model-consuming verification has an explicit
  allowance; a documentation claim or successful login alone is not proof of
  inference access. The principal performs real login without disclosing secrets
  to the development agent.

## Completion

Complete this plan when the selected Anthropic connection path has demonstrated
repeated launches and later collection without routine credential copy/paste,
the required local and Linux checks pass, and a bounded live check confirms the
actual account can use the route. Renewal or key rotation, revocation, withheld
exports and explicit API-key supply have recorded outcomes. Document any
remaining platform limits and give every unfinished item an explicit disposition.

Keep enduring connection behavior and operating instructions with the product
documentation, and demonstrations with the qualification record. Preserve
evidence under [DEVELOPMENT](DEVELOPMENT.md#evidence-and-retention), then remove
this plan. Additional provider runtimes, OS-store ports and hosted deployment
remain separately scoped work, not implied capabilities of the completed path.
