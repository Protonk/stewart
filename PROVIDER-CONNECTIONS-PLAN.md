# Reusable provider connections

Let the principal connect a provider account once and run an authorized series
of launches and later evidence collection without re-entering the key. The
connection belongs to the launch apparatus on the macOS host. The product keeps
its contract: the manager supplies one credential per placement through the
descriptor or the environment, as [CONTRACTS](CONTRACTS.md#run-and-continuation)
and [INTERFACE 6.1](docs/INTERFACE.md#61-provider) state. This plan changes no
service code, driver code, contract, interface or acceptance claim.

This plan owns the connection design, implementation and verification. Operating
instructions belong in the [launcher instructions](apparatus/c10/README.md) once
implemented. Planning checks are retained in `.scratch/provider-connections-plan-01`
and `.scratch/provider-connections-plan-02`.

The connection module and CLI are implemented; their operating contract is in
[the launcher instructions](apparatus/c10/README.md#saved-provider-connections).
Current local checks are retained in `.scratch/provider-study-checks-01`.
The reviewed Linux aarch64 rehearsal `.scratch/c10-study-launch-01` at `751aa7c`
is pinned in [the qualification record](apparatus/qualified.md). Its
`review/result.json` records all 15 expected audit outcomes, 50 reviewer
comparisons with 44 firing controls, seven operator comparisons and two firing
process-access controls, with no failed or skipped checks. Both study templates
and fresh-process collection through `stewart-synthetic` passed. The two Keychain
lookup records name that account; the principal reported approving two `security`
prompts and tentatively recalls both naming it. The later collection added
`export-0002` without changing the original snapshot's files. This qualifies the
observed apparatus route on Linux aarch64, with no model calls or real-key use.

Retain the native iteration records in `.scratch/c10-study-native-03`,
`.scratch/c10-study-review-fixed-01`, `.scratch/c10-study-review-study-a-01` and
`.scratch/c10-study-review-study-b-01`, and the earlier permission failures in
`.scratch/c10-study-native-01` and `.scratch/c10-study-native-02`. They remain
development observations, with the Linux process-access checks skipped natively.
The apparatus landed on `main` as `72ae26b`. The host checks in
`.scratch/connection-checks-01` used synthetic values on macOS 26.7.1 / kernel
25.6.0; `review-01.json` indexes the original records and their dispositions.
All 11 attempts bind the committed apparatus hash: eight passed, one failed and
two require the observations below. Passing checks cover metadata presence,
missing item (exit 44), allowed retrieval, matching retrieval in a fresh process,
denied access (exit 128), explicit hidden entry, a different value under a new
label, and absence of that label after deletion. The principal confirmed separate
approval prompts for the initial and fresh-process retrievals. Hidden entry
passed on its second attempt; the first failure records no cause and remains
retained without an inferred explanation.

The first locked-state attempt returned a value, but the principal reported that
locking login was unavailable in the GUI and only the normal allow/deny prompt
appeared. It is another allowed lookup, not a locked-keychain demonstration.
The retry after the principal ran `security lock-keychain` returned exit 128 /
`access_denied`. The principal reported cancelling an unlock request and recalls
that its requester was not `sharingd`, but cannot recall the name. Refusal after
the reported cancellation was observed; exact dialog-to-process attribution
remains unconfirmed, and exit 128 alone cannot distinguish it from ordinary
denial. `observer-01.json` through `observer-03.json` preserve these accounts.
The distinct locked/unavailable-interaction classifier has only fake-tool
coverage. A separate `sharingd` prompt is excluded from these checks. Further
host Keychain and harness investigation remains outside this tranche unless
requested.
The principal's 2026-11-05 metadata lookup found the live item in the login
keychain with service `stewart-provider`, account and display label
`stewart-haiku`. The principal reports its provider scope as the Stewart project;
no provider identity or inference access has been checked. No test read its value.
The agent execution context could not find even the earlier known item after
escalation; the principal took that harness investigation elsewhere. The planned
agent-shell observer check is deferred to that separate investigation. Current
launch and collection checks use the principal's terminal.

## Decisions

**The apparatus owns the connection.** The binary runs in a Linux container or
on WSL2 and has no host credential store; the repeated entry happens in the host
launcher, so that is where reuse belongs. A launcher that supplies the key from
a store satisfies the product's one-credential-per-placement rule unchanged. The
static key is the literal value the collection path already needs for its HMAC
check and byte scan, so follow-up collection works without new recognition
material. Product-level saved connections, bearer or federated authentication
and other providers are deferred in [CONTRACTS](CONTRACTS.md#declined-and-deferred-scope).

**The store is the macOS login Keychain.** One generic-password item per
connection, service `stewart-provider`, account equal to the packet's
`credential_label`. The principal creates it in a separate terminal with hidden
entry and `-T ""`, which removes the creating tool's default access so that
every read prompts. The launcher reads it with
`security find-generic-password -s stewart-provider -a LABEL -w` as a subprocess
whose standard output goes only to the existing standard-input handoff into the
container. The sanity launcher keeps hidden entry; the study uses the C10 route.

**The access boundary is the login session plus the per-access prompt.** A
same-user process, including the development agent's shell, receives the value
if the principal approves its prompt. The Keychain is reached through the system
daemon, so the agent sandbox cannot deny it by path. No stronger isolation is
claimed: not a vault, not protection from the host administrator and not memory
erasure. The one prompt per launch and per collection is the accepted manual step.

**Keys.** The study uses a new workspace-scoped key under its own label, so
Console figures attribute cleanly. Rotation is a new item under a new label; the
old item stays until every run launched with it has been collected, then the
principal deletes it. Historical runs were launched by hand entry; collecting
them still needs that key, entered by hand or stored under its own label. No
migration of their records.

**Explicit key supply stays.** Without `--connection`, live launch and collection
prompt for hidden entry as today. The launcher never reads `ANTHROPIC_API_KEY`;
its filtered host environment already drops it. `--connection LABEL` must equal
the approved packet's `credential_label`; a different label refuses before any
lookup, so a changed ambient default cannot select another paying account.
Alternate endpoints remain a rehearsal-only setting.

**Rehearsal may use a synthetic connection.** `rehearse --connection LABEL`
reads a Keychain item whose value must carry the nonfunctional prefix
`c10-NONFUNCTIONAL-` and refuses any other value, so a real key never enters
the rehearsal's plaintext witness. The retained Linux rehearsal then
demonstrates launch and later collection without entry, with the fake
provider's witness confirming which bytes arrived.

**The live check is the Problem A baseline.** The interaction study's first
launch runs with the saved connection and its later collection uses it again. A successful lookup proves nothing about
inference access; only that authorized run does. No separate model-consuming
check is planned.

**Who runs paid work is unchanged for now.** The principal runs live launches
and collections in a separate terminal and the agent prepares the commands. The
follow-on decision about running and enforcing paid work is staged in the
coordinating plan.

## Connection contract

| Concern | Required behavior |
| --- | --- |
| Selection | The packet names provider, endpoint and the non-secret account, workspace and credential labels. The launcher prints them before launch and labels them as manager-supplied; provider-confirmed identity comes only from a successful run and the Console. |
| Configuration | No credential in packets, question files, arrangements, records or ordinary configuration. The only persistent secret is the Keychain item. |
| Private use | The launcher process holds the key between lookup and handoff and for the host scan, then drops it. It never enters argv, environment, container configuration, recorded streams or chat. Lookup records retain the exit status and fixed failure classification; raw stdout and stderr stay unrecorded because unexpected tool output may contain a credential. |
| Lifecycle | `connection status` reports item presence and metadata without reading the value. Disconnect is the principal deleting the item; the launcher states that this removes local access only and that revocation happens in the Console and is not confirmed by Stewart. |
| Failure | Missing item, denied/cancelled access, locked/unavailable interaction, missing tool, label mismatch with the packet and wrong key at collection (the existing HMAC refusal) have distinct diagnostics. A cancelled unlock can return the same access-denied status as ordinary denial; the classification does not independently establish Keychain state. No fallback to another source. |

## Evaluated routes

Checked against primary documentation on 2026-11-04. The Anthropic Console login
(`ant auth login`) issues a workspace-scoped OAuth token, stores it in a plain
credentials file under the configuration directory, and documents a bearer
header for `/v1/messages` through `ant auth print-credentials --access-token`.
It is described as intended for the user's own machine; containers are directed
to Workload Identity Federation. It is not selected: the credential file is
readable by any same-user process without a prompt, the run executes in a
container, and a bearer header with renewal would change the product's wire
rules, reflection scanning and acceptance. Sources:
[CLI authentication](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/authentication),
[CLI scripting](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/scripting#authenticate-curl-requests-with-cli-credentials).
Other providers and subscription routes are deferred scope in CONTRACTS, with
[Anthropic's authentication boundaries](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use)
as the relevant limit for Claude subscriptions.

## Remaining work

The fake-`security` tests cover lookup and fresh-process reuse, metadata-only
status, distinct failures, deadlines, label mismatch before launch, nonfunctional
prefix and credential bounds, collection handoff and exclusion of values from
records and streams. The inherited sanity launcher is unchanged. The local test
outputs, rather than this implementation account, own actual counts and skips.

- [ ] Launch the Problem A baseline with `--connection` under its own
  authorization and collect it later with `--connection`. Record both outcomes
  in that run's evidence and cite them here.

## Completion

Complete this plan when the Problem A baseline has launched and been collected
through the saved connection without key entry, the offline and host checks and
the Linux rehearsal have recorded outcomes, and rotation, disconnect and explicit
hidden entry have been exercised. Move operating instructions to the launcher
README and demonstrations to the run records, give any unfinished item an
explicit disposition, preserve evidence under
[DEVELOPMENT](DEVELOPMENT.md#evidence-and-retention), then remove this plan.
