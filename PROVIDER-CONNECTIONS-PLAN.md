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
its filtered host environment already drops it. Rehearsal never consults the
Keychain. `--connection LABEL` must equal the approved packet's
`credential_label`; a different label refuses before any lookup, so a changed
ambient default cannot select another paying account. Alternate endpoints remain
a rehearsal-only setting.

**The live check is the Problem A baseline.** The first study launch under
[INTERACTION-PLAN](INTERACTION-PLAN.md) runs with the saved connection and its
later collection uses it again. A successful lookup proves nothing about
inference access; only that authorized run does. No separate model-consuming
check is planned.

**Who runs paid work is unchanged for now.** The principal runs live launches
and collections in a separate terminal and the agent prepares the commands. The
follow-on decision about running and enforcing paid work is staged in
[RELEASE-PLAN](RELEASE-PLAN.md).

## Connection contract

| Concern | Required behavior |
| --- | --- |
| Selection | The packet names provider, endpoint and the non-secret account, workspace and credential labels. The launcher prints them before launch and labels them as manager-supplied; provider-confirmed identity comes only from a successful run and the Console. |
| Configuration | No credential in packets, question files, arrangements, records or ordinary configuration. The only persistent secret is the Keychain item. |
| Private use | The launcher process holds the key between lookup and handoff and for the host scan, then drops it. It never enters argv, environment, container configuration, recorded streams or chat. The `security` tool's standard error is recorded; it carries no secret. |
| Lifecycle | `connection status` reports item presence and metadata without reading the value. Disconnect is the principal deleting the item; the launcher states that this removes local access only and that revocation happens in the Console and is not confirmed by Stewart. |
| Failure | Missing item, locked keychain, denied prompt, missing tool, label mismatch with the packet and wrong key at collection (the existing HMAC refusal) are reported distinctly. No fallback to another source. |

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

### 1. Freeze the launcher interface

- [ ] Add a connection module under `apparatus/c10/` that performs the lookup
  with a bounded deadline, classifies the tool's exit status and standard error
  into the failure cases above, and returns the value only to the caller.
  `launch.py` is unchanged. Record the macOS and `security` behavior observed
  with the synthetic item, including the exit status for a missing item and for
  a denied prompt.
- [ ] Add `--connection LABEL` to `c10.py live` and to `c10.py control … collect`,
  and `c10.py connection status LABEL`. Live and collect refuse a label that
  differs from the packet's `credential_label` and refuse `--connection` in
  rehearsal. Keep hidden entry as the default.
- [ ] Keep the secret out of every record: the lookup runs after verified intake
  exactly where hidden entry runs today, the value is written only to the
  container's standard input, the host scan uses it and drops it, and failure
  reports carry fixed text.
- [ ] Document setup, status, rotation and disconnect in the launcher README,
  including the exact creation command with `-T ""` and hidden entry, and the
  principal-run host checks below.

### 2. Verify the supported path

- [ ] Offline coverage in `test_c10.py` with a fake `security` executable on the
  path: successful lookup, missing item, denied access, missing tool, deadline,
  label mismatch, rehearsal refusal, and absence of the value from every record
  and stream. The agent can run these.
- [ ] Host checks against a synthetic item that the principal creates with a
  nonfunctional value: initial setup, reuse by a fresh launcher process, locked
  keychain, missing item, denied prompt, wrong key at collection, and an observer
  run of the lookup from the agent's sandboxed shell with its prompt recorded.
  The real item is never read by a test. Retain the outputs under
  `.scratch/connection-checks-NN`.
- [ ] Run the [DEVELOPMENT checks](DEVELOPMENT.md#what-to-run-for-what-you-changed)
  for `apparatus/c10/` and preserve outputs. Commit, then the principal runs the
  Linux `c10.py rehearse` for the changed apparatus; its binding is required
  before live use.
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
