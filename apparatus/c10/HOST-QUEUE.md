# Delegated host execution

`host_queue.py` serializes a campaign's C10 operations on the host and tracks
its placement allowance across requests. It dispatches the existing launcher
and operator commands, with retained argv, streams and exits. It does not accept
shell commands, replace packet/rehearsal checks, judge scientific work, manage
credits, or confer authority. Use it only under an explicit bounded commission.

## Prepare the accounts and campaign

Start the runner in a fresh `stewart-launch` login with its reviewed standalone clone,
qualified writer, image store, owned evidence and persistent keyring. Keep
the clone, Git metadata, qualification originals, configuration and `.scratch`
under parents that agents cannot write. The clone must have its own Git
directory and object store. `stewart-dev` has no sudo or shell
as the launcher. Both accounts belong to `stewart-queue`. The provisioned
`/var/lib/stewart/queue` is launcher-owned, group `stewart-queue`,
mode 2750. Its launcher-owned subdirectories are:

| Directory | Mode | Who uses it |
| --- | --- | --- |
| `requests/`, `packets/` | 3770 | Agents publish regular JSON files atomically, group-readable by the launcher. |
| `results/` | 2750 | Agents read result JSON and successful, credential-scanned exports. |
| `claims/`, `sessions/`, `submissions/` | 0700 | The launcher retains its allowances, snapshots and reviewed study inputs. |

Use one queue for the whole campaign. The immutable scope includes the
authority, account, model, envelope and ceilings. The example below is a
**synthetic** campaign with simulated rates and dollar amounts.

```json
{
  "schema": "stewart.c10-campaign/2",
  "campaign": "queue-rehearsal",
  "authority": "Synthetic queue comparison only",
  "model": "rehearsal-only",
  "qualification": "ACCEPTANCE-ID",
  "synthetic_connection": "stewart-synthetic",
  "account": {"account_label": "offline", "workspace_id": "offline", "credential_label": "stewart-synthetic"},
  "placement_ceiling": 56,
  "budget_usd": 14.52,
  "console": null,
  "envelope": {
    "cases": ["open-ordinary", "open-inadequate", "framing-ordinary", "framing-inadequate", "comparison-ordinary", "comparison-inadequate"],
    "submissions": {},
    "efforts": [null],
    "limits": {"turns": 12, "input_tokens": 160000, "output_tokens": 30000},
    "max_placements": 2,
    "watchdog_seconds": 900,
    "study_build_sha256": null,
    "pricing": {"input_cents_per_million": 1, "output_cents_per_million": 5, "max_input_per_attempt": 1000000, "max_output_per_attempt": 16000}
  }
}
```

The runner reserves the placement ceiling in whole cents, rounded up, before
dispatch. For each slot it prices four attempts per allowed turn. Each attempt
uses the maximum billable input and output and most expensive applicable rate
bands for the commissioned model and route. Establish those bounds and the
rate card when commissioning, including cache charges, summary iterations
and the final request that can exceed the remaining input allowance. Fixed
cases, submitted content hashes, effort, cumulative tokens and turns, per-audit
placement count, watchdog and writer must fit the envelope. A null study-build
digest permits the qualified writer. A specified digest additionally permits
that reviewed build, identified by SHA-256 of its compact JSON descriptor
in packet member order. For a study, map its ID to the exact tree hash in
`envelope.submissions` and install the reviewed template in
`queue/submissions/ID`. Its packet must name that launcher-owned path.

A paid configuration names the exact commissioned model and bound account,
workspace and credential. The current attributed `console` observation
contains `scope`, `month` (`YYYY-MM` UTC), `limit_usd`,
`starting_spend_usd`, `recorded_by`, `recorded_at` and
`credential_binding`. Each reservation must fit both remaining authorization
and remaining Console headroom after all prior reservations. The runner
does not query billing. Failed and interrupted dispatches retain their full
reservations. Missing charge metadata holds the whole allowance.

```sh
python3 -I -B apparatus/c10/host_queue.py /var/lib/stewart/queue \
  --config "$HOME/commission/queue.json" --once
```

For a paid campaign the maintainer adds `--live`. Omitting `--once` runs
until `queue/STOP` or a failed child. An exclusive lock covers admission,
allowance checks and execution. A session checks committed apparatus, snapshots
the configuration and persists claims before spawning the launcher.
[Saved provider connections](README.md#saved-provider-connections)

## Exercise the two accounts

Using the synthetic configuration above, provision a fresh nonfunctional
key and re-enter the launcher login. Run `connection status stewart-synthetic`.
Check that a direct read of the key serial as `stewart-dev` fails, that the
developer cannot write launcher source, configuration or claims, and cannot
connect to its Podman socket. Compare against an accessible launcher-owned
socket to distinguish permission denial from an absent socket. Compare key
presence from a launcher login before and after a guest reboot.

As `stewart-dev` publish one `rehearse` request with no supplied cases. The
base rehearsal reserves 28 simulated slots and 1,452 cents. Inspect its fake
request witnesses, result, scans and exported snapshots. Submit a second
request with a fresh name and evidence path. Its placement count fits
the 56-slot ceiling while its projected spend exceeds the budget. Its
refusal leaves no new claim, container or provider calls. Preserve both
operations, the independent fake witness and negative access checks through
review. A paid campaign's offline preparation rehearsal uses the synthetic
connection and carries zero paid slots and cents.

## Publish one operation

The agent prepares one nonsecret JSON request in a temporary file, then atomically
renames it into `queue/requests/NAME.json`. Names are lowercase letters, digits
and hyphens, beginning with a letter. Never edit a published request. Read its
group-readable `results/NAME.json` before selecting the next operation.
A refusal requires a fresh request name. The launcher reads each submitted packet
once into its private session and validates that snapshot. Results reference the
credential-scanned, digest-verified exports by filename. Examples, with absolute paths abbreviated:

```json
{"operation":"rehearse","evidence":"/repo/.scratch/rehearsal-01","submissions":[["case-a","/var/lib/stewart/queue/submissions/case-a"]]}
{"operation":"live","evidence":"/repo/.scratch/live-01","packet":"/var/lib/stewart/queue/packets/packet.json","sha256":"EXACT_PACKET_SHA256","rehearsal":"/repo/.scratch/rehearsal-01"}
{"operation":"continue","evidence":"/repo/.scratch/live-01","record":"/repo/.scratch/continue-01","packet":"/var/lib/stewart/queue/packets/continuation.json","sha256":"EXACT_PACKET_SHA256","rehearsal":"/repo/.scratch/rehearsal-02"}
{"operation":"inspect","evidence":"/repo/.scratch/live-01","audit":"case-a","confirm":null}
{"operation":"close","evidence":"/repo/.scratch/live-01","audit":"case-a","confirm":null}
{"operation":"close","evidence":"/repo/.scratch/live-01","audit":"case-a","confirm":"EXACT_RETURNED_CONFIRMATION"}
{"operation":"collect","evidence":"/repo/.scratch/live-01","audit":"case-a","confirm":null}
```

`status` has the same shape as `inspect`. Only ordinary close is supported; there
is no surrender or disposal command. A live request names exactly
one audit and must match the campaign's model, account, authority and base
qualification. The existing launcher checks its exact packet digest, clean
committed apparatus, declared binary, input hashes and complete rehearsal before
credential access. A packet's authority text records the delegation; it does not
prove permission. Follow-ups get new packets and evidence folders.

`continue` starts one [later placement](README.md#continue-a-retained-audit) of
a retained audit. `evidence` is the original launch's folder, which the packet
must name; `record` is a new folder for this placement's host records; `packet`
is a `stewart.c10-continuation/1` packet with its exact digest. It has the same
guarantees as `live`: it needs a live-enabled session and current Console
record, must match the campaign's model, account, authority and base
qualification, charges one slot when claimed, is never dispatched twice, and
waits behind any unreconciled claim. The launcher then repeats those checks and
adds its own against the retained records, the audit's prior state, its writer
and the rehearsal's continuation controls. A first-launch packet is refused
under `continue`, and a continuation packet under `live`. For status,
inspection, close or collection of a continued audit, name the continuation's
record folder as `evidence`. Nothing here selects or starts a continuation by
itself; each one is a request the experimenter publishes after reviewing the
placement before it.

A `continue` launch whose host record says `not_started` stopped before any
model process, for example on a denied keyring lookup or a different key. It
still exits nonzero, keeps its charged slot and blocks paid dispatch until its
claim is reconciled. A further attempt of the same placement is a new request
with a new `record` folder and its own slot. The launcher permits it only while
every earlier attempt is recorded as not started; a placement that started or
may have started is never dispatched again.

`claims/NAME/` is created exclusively before subprocess execution. It retains the
request, command, streams and result. A claimed name is never dispatched twice,
including after a crash. The queue process's exit is not the audit's outcome.
Use C10's host/session/export records to establish actual effects and custody.

## Failed or interrupted operations

A nonzero child exit stops dispatch. An incomplete or failed claim blocks further
paid dispatch even after restart. Status, inspection and collection remain
available offline. Move any unclaimed paid request out of `requests/` while
publishing recovery operations; preserve it rather than rewriting it. Do not
restart the placement merely because its caller disappeared.

After inspecting the original evidence and completing necessary custody work,
the launcher operator may write a new `claims/NAME/reconciliation.json`:

```json
{"author":"Stewart experimenter","disposition":"Describe the observed effects, remaining obligations and why another placement is now authorized.","evidence":[{"path":"/absolute/checked-observation.json","sha256":"EXACT_OBSERVATION_SHA256"}]}
```

The runner checks that the attributed disposition and referenced bytes exist.
It does not certify the judgment, erase the failure or refund the slot. A claim
with a zero exit also needs experimenter review because the launcher can
return zero after an unsubmitted limit stop. Any further paid placement must
fit the campaign's commission and remaining allowance.

Creating `STOP` prevents the next operation; it does not cancel an active one.
Interrupting the runner can leave uncertain child/container effects. Inspect
running-work state and retained records before continuing, and remove `STOP`
only when resuming the authorized campaign. Neither stopping nor restarting the
queue disposes of evidence or closes an audit.
