# API-key handling

Harden credential entry, runtime use and evidence handling with established
components. The implementation choices below remain proposals; a synthetic-key
security audit is still needed. Product responsibility changes require the
principal's decision under [AGENTS.md](AGENTS.md).

## What the current path does

These are code-review findings, not results of a canary security audit.

| Surface | Observed behavior and implication |
| --- | --- |
| Credential input | [ops/run.rs](service/src/ops/run.rs) reads `ANTHROPIC_API_KEY`, refuses an empty value or bytes outside visible ASCII, then holds it in a `String`. No file-descriptor or secret-store input exists. The error does not print the rejected key. |
| Transport | [transport.rs](service/src/provider/transport.rs) copies the key into `Client`; [http.rs](service/src/provider/http.rs) places it in the HTTP header. `Client` derives `Debug` and `Clone`: debug formatting would expose the field. No normal-path logging of that debug representation was found in this review; it is a latent exposure, not an observed leak. Header buffers and ordinary strings also hold copies. |
| Destination | [url.rs](service/src/provider/url.rs) accepts an explicit HTTPS provider override and HTTP on loopback; `run` also reads upper/lowercase proxy variables. A valid override can intentionally receive the key. The live launcher must select the destination explicitly and exclude ambient overrides/proxies unless commissioned. |
| TLS | The release verifies TLS with built-in public roots. The proxy route uses CONNECT followed by end-to-end TLS. This protects transport; it does not protect local process state or logs. |
| Normal request evidence | [INTERFACE 4.5](docs/INTERFACE.md#45-run-captures) captures request bodies, not outbound authentication headers. The key is not deliberately added to the arrangement, question or tools. This is narrower than a guarantee that no evidence can contain it. |
| Provider responses | [placement.rs](service/src/provider/placement.rs) calls `write_response` before decoding; [runs.rs](service/src/runs.rs) writes those bytes unchanged. Provider error text is also retained in attempt and run records and exposed through manager results. A response echoing the key would therefore persist it. That conclusion follows from the code; the echo case has not yet been executed. |
| Launcher/container | Shell arguments and container environment settings expose a key to additional inspection and recording surfaces. The live credential-entry mechanism must be selected and audited. |

The Linux `/proc` interface exposes process arguments and environment subject
to access controls. We should measure which actors can read them in the actual
container, rather than treat an environment variable as private storage.
[Kernel documentation](https://docs.kernel.org/filesystems/proc.html)

## Proposed hardening commission

Use established components and keep the Stewart adapter small. Candidate
references checked on 2026-10-31:

| Need | Existing component and proposed use |
| --- | --- |
| Secret values inside Stewart | [`secrecy`](https://docs.rs/secrecy/latest/secrecy/) provides `SecretString`, explicit access through `ExposeSecret`, redacted debug output and zeroization on drop. Use it for the API key instead of an ordinary `String` or a homemade secret wrapper. |
| Temporary buffers containing the header/key | [`zeroize`](https://docs.rs/zeroize/latest/zeroize/) provides memory wiping and `Zeroizing` wrappers. Stewart already has it transitively through `rustls`. Avoid unnecessary copies; wiping one buffer does not erase previous reallocations/copies, and a release abort does not run destructors. |
| Interactive entry | [`rpassword`](https://docs.rs/rpassword/latest/rpassword/) supplies hidden TTY input. Evaluate it for an explicit interactive entry path rather than writing terminal-control code. Immediately transfer the resulting value into the secret type. |
| Persistent storage, if wanted | The [`keyring` ecosystem](https://github.com/open-source-cooperative/keyring-rs) accesses existing OS credential stores. Its current guidance recommends `keyring-core` plus the selected store for applications needing explicit backend control. A host-side store can serve the launcher; do not assume a desktop credential service exists inside the headless Linux container or build our own encrypted vault. |
| Dependency review | [`cargo audit`](https://github.com/RustSec/rustsec/tree/main/cargo-audit) checks the lockfile against RustSec advisories. It complements the canary audit; it does not check our credential data flow. |

The first implementation candidate is `secrecy` for values, `zeroize` for
temporary buffers and an established entry mechanism. The small adapter into
the Linux process, explicit provider selection and evidence policy remain
Stewart's work. These are candidates, not dependencies already installed or
verified in the static Linux build.

1. **Name the protection boundary.** Protect against accidental disclosure to
   chat, Git, command history, process arguments, container configuration,
   routine diagnostics, model context and exported run records. Test access by
   other unprivileged processes. The user-controlled host/VM administrator and
   the authenticated provider remain trusted; this is not a promise against a
   compromised kernel or an authorized debugger reading runtime memory.
2. **Choose credential entry before implementing it.** Evaluate the existing
   hidden-TTY and host credential-store routes above first; the assistant never
   needs the value. If the host must pass a key into the Linux process, use a
   small adapter over a standard pipe/inherited descriptor with a bounded read
   and immediate close. Do not design a credential store or a new cryptographic
   transport protocol. Specify ambiguous-source behavior and failure handling.
   Any new Stewart input interface needs the principal's decision. A smaller
   launcher-only approach can supply the current environment input inside an
   isolated container, but leaves the process-environment exposure to qualify
   and disclose.
3. **Harden the implementation and launcher.** Remove secret-bearing debug
   formatting; minimize copies and lifetime; disable core dumps and test actual
   process-inspection behavior. Do not claim reliable erasure merely because a
   Rust value was dropped or an environment entry removed. The launcher should
   use a minimal environment, one approved endpoint and proxy decision, and no
   secret in arguments, container configuration, submission, logs or exported
   setup files. Missing credentials fail closed. Each run receives only its
   expressly selected credential, with no subscription or alternate-key fallback.
4. **Decide reflected-secret handling.** A credential can come back in a
   response body or one of the retained response headers. Sanitizing only the
   terminal leaves archive copies. Sanitizing the raw capture changes Stewart's
   exact-evidence promise (INTERFACE 4.5), so it cannot be an incidental fix.
   Recommended initial direction: keep exact raw evidence private, make any
   redaction in displayed/derived diagnostics explicit, detect echoes and stop
   for review, and revoke an exposed test key. Restrict export of contaminated
   evidence. This still permits a key in private raw evidence; the principal
   must choose that tradeoff or commission a changed capture contract. Do not
   rewrite historical receipts/captures or silently remove evidence.
5. **Use a dedicated, narrowly scoped test credential.** The user creates it
   and controls expiry, revocation and account spending settings. Keep its
   non-secret identifier and permitted workspace in the run record. A disposable
   key limits consequences; it does not substitute for handling checks.

Provider compatibility matters here too. Current Anthropic documentation says
`x-api-key` remains supported, but an unscoped key requires an
`anthropic-workspace-id` header, which Stewart does not send. Prefer a personal
key scoped to the selected workspace with an expiry for an individual test; a
shared deployment needs its own service identity. Confirm the account's actual
options before creating it.
[Authentication](https://platform.claude.com/docs/en/manage-claude/authentication)

Anthropic recommends separate-purpose keys, secret storage, usage monitoring,
rotation and prompt revocation after suspected exposure. Apply those to this
bounded test without putting the key in a repository `.env` file or in this chat.
[API-key guidance](https://support.claude.com/en/articles/9767949-api-key-best-practices-keep-your-keys-safe-and-secure)

## Audit with synthetic canaries before using a real key

Use generated, nonfunctional key values and local fakes on Linux. Keep an
independent canary witness outside the archive and outside any redaction under
test. Scan exact bytes and their relevant JSON/escaping encodings. Do not print
values in the report; report surfaces, access, timing and match counts.

| Test | Required distinction |
| --- | --- |
| Credential delivery | Fake receives the exact canary, while argv, container inspection, preparation/receipt, model-visible bodies, ordinary outputs and exports have only the exposure permitted by the chosen contract. Observe both before and during `run`. |
| Process access | An intentionally readable environment/argument fixture is a positive control; test same-user and different-user observers against the hardened process. Inspect core-dump behavior and surviving files after exit rather than trusting settings alone. |
| Provider routing | Approved route receives the key. Ambient override/proxy injection is excluded by the launcher. Wrong TLS identity, invalid/missing credential and unavailable endpoint fail without alternate credential or provider fallback. |
| Error and response reflection | Exercise echoes in a body, JSON escapes and retained header, on 401 and malformed/truncated responses as well as a successful body. Verify the exact selected raw-evidence/display policy, including stopping and accounting. |
| Failure and lifecycle | Inspect timeout, cancellation, crash, failed export and repeated invocation. Stopped containers and partial records must not accidentally retain a credential-input file or expose it through diagnostics. No automatic resume. |
| Detection controls and invariance | A deliberately leaking fixture must be detected. A clean baseline must remain clean on the surfaces claimed, and an unrelated non-secret diagnostic must retain its original evidence. Keep all witnesses and controls through review. |

Report the tested boundary and residual exposures. A clean recursive text search
alone cannot establish secrecy in process memory or container metadata. The
normal rehearsal provider intentionally does not store authentication headers;
it cannot serve as the independent witness for this credential audit unchanged.

## Decisions and completion

Before implementation, select the existing entry/store components and the small
Stewart adapter they need, and settle exact private captures versus a changed
reflected-secret capture contract. Pin and vendor any chosen dependencies under
[DEVELOPMENT's dependency-change checks](DEVELOPMENT.md#what-to-run-for-what-you-changed).
Implement the chosen changes, run both Cargo configurations and the required
Linux checks, and audit the final credential path with canaries. Independent-driver
additions require an author who has not read the service implementation.

Completion means the selected credential path is implemented, the tested boundary
and residual exposures are documented, and the chosen evidence policy is stated
in CONTRACTS/INTERFACE and exercised in tests.
