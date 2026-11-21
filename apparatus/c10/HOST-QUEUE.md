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

Use the same queue for both waves and all authorized models. The private
configuration binds the exact bytes of the commission. Put the signed-off
envelope in a launcher-owned file and compare its SHA-256 with the grant.
Each live session checks the account's credential label, endpoint, models,
wave allocation, authority, total slots and dollar ceiling against that file.
The following offline example uses simulated rates in microdollars per million
tokens. A million microdollars is one dollar.

```json
{
  "schema": "stewart.c10-campaign/3",
  "campaign": "queue-rehearsal",
  "authority": "Synthetic queue comparison only",
  "grant_path": "/home/stewart-launch/commission/envelope.json",
  "grant_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "qualification": "ACCEPTANCE-ID",
  "synthetic_connection": "stewart-synthetic",
  "account": {"account_label": "offline", "workspace_id": "offline", "credential_label": "stewart-synthetic"},
  "cards": "/home/stewart-launch/commission/cards",
  "wave": 1, "wave_one_model": "rehearsal-only", "wave_one_ceiling": 70,
  "placement_ceiling": 70, "budget_usd": 0.70,
  "envelope": {
    "cases": ["open-ordinary","open-inadequate","framing-ordinary","framing-inadequate","comparison-ordinary","comparison-inadequate"],
    "submissions": {}, "efforts": [null],
    "limits": {"turns": 12, "input_tokens": 160000, "output_tokens": 30000},
    "max_placements": 2, "watchdog_seconds": 900, "study_build_sha256": null,
    "pricing": {"rehearsal-only": {"context_tokens":1000000,"bands":[{
      "through_input_tokens":1000000, "input_tokens":10000, "cache_creation_input_tokens":10000,
      "cache_read_input_tokens":10000, "output_tokens":50000
    }]}}
  }
}
```

Freeze per-model rate bands with the commission, including discounts, cache
charges and the maximum input that can overrun the cumulative limit in the
last request. The campaign admits only ordinary client-tool packets whose
cumulative input plus output limits do not exceed the 150,000-token compaction
threshold. This excludes a new server summarization iteration from the cost
bound. Every request and retry checks remaining allowances. Before the child
starts, the runner reserves the unused input allowance plus the greater of the
model context window and the largest terminal estimate, at the highest input
rate. It also reserves the unused output allowance plus one request's maximum
output (at most 16,000 tokens) at the highest output rate. Settlement counts
the full Stewart estimate and rounds up to the next cent per placement.

Each paid packet, including a continuation, specifies `file_size_limit` of
131072 bytes. An unprivileged helper lowers both file-size limits, arms the
default SIGXFSZ action and execs the release writer. Before putting the key
in its pipe, the launcher reads the waiting child's actual kernel limits and
checks the accepted arrangement fits. The writer completely records every
request's newly appended messages before its first network attempt. A retry
uses the same body, and the next new request requires a charged turn. The
maximum pre-send body in bytes is therefore 131072 for fixed arrangement
members, plus 131073 per remaining turn (one capture and its delimiter), plus
1024 for JSON framing. Stewart charges the ceiling of body bytes divided by
three for an estimated input. Rehearsal includes the same oversized question
with and without enforcement and a smaller question with enforcement.

The limit covers every regular file the placement writes, including captures,
prepared answers, generated artifacts, seal files and output streams. Intake,
the manager's close, the fake endpoint, review and the queue run separately.
An over-limit write can terminate the writer with SIGXFSZ, cut off a capture
and leave a started run without its ending. Earlier requests may already have
been billed. A signalled child, a changed file at the threshold or any
incomplete custody record requires reconciliation. The claim retains its full
reservation and blocks subsequent placements. Only a clear, unexercised
limit supports interpretation as an ordinary reference or selection.

Paid publication requires complete, clean receipts from staging, the final
host scan and each audit's export scan. A continuation also requires both
host-directory scans and the snapshot identified by that placement's attempt.
A previous snapshot cannot satisfy the current receipt. A match stops the
queue. A missing, unreadable or incomplete required scan withholds the archive
and settlement. The shared failure summary gives a fixed reason. The launcher
keeps the detailed scan receipts under its private account.

After a complete export, the runner reconstructs the placement from the
digest-verified archive. Its settlement prices the recorded reported input,
cache creation, cache reads and output per attempt at the matching tier.
Known five-minute writes use their listed lifetime rate. Estimates and unspecified cache creation lifetimes use the highest applicable
rates. The new claim carries both the original reservation and that placement's
settlement. Continuations charge just their new placement. An unreviewed or
uncertain placement keeps its reservation and blocks further starts; the
custody operations remain available. Keep the same ledger across restarts and
waves. Once wave two begins, wave one cannot resume. Endpoint billing and the
account-wide provider cap are separate from this campaign meter.

```sh
python3 -I -B apparatus/c10/host_queue.py /var/lib/stewart/queue \
  --config "$HOME/commission/queue.json" --once
```

Add `--live` only to dispatch a granted paid operation. A protected commission
also pins approved input tree hashes, effort, maximum per-audit limits,
watchdog and maximum placements. For study inputs place the reviewed template
under `queue/submissions/ID`, and enter its tree hash under `envelope.submissions`.
The launcher snapshots each exact approved packet before dispatch.
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
base rehearsal reserves 35 simulated slots and 70 cents. Inspect its fake
request witnesses, result, scans and exported snapshots. Submit a second
request with a fresh name and evidence path. Its placement count fits
the 70-slot ceiling while its projected spend exceeds the budget. Its
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
one audit and must match the campaign's permitted model, account, authority and base
qualification. The existing launcher checks its exact packet digest, clean
committed apparatus, declared binary, input hashes and complete rehearsal before
credential access. A packet's authority text records the delegation; it does not
prove permission. Follow-ups get new packets and evidence folders.

`continue` starts one [later placement](README.md#continue-a-retained-audit) of
a retained audit. `evidence` is the original launch's folder, which the packet
must name; `record` is a new folder for this placement's host records; `packet`
is a `stewart.c10-continuation/3` packet with its exact digest. It has the same
guarantees as `live`: it needs a live-enabled session and protected commission, must match the campaign's permitted model, account, authority and base
qualification, charges one slot when claimed, is never dispatched twice, and
waits behind any unreconciled claim. The launcher then repeats those checks and
adds its own against the retained records, the audit's prior state, its writer
and the rehearsal's continuation controls. A first-launch packet is refused
under `continue`, and a continuation packet under `live`. For status,
inspection, close or collection of a continued audit, name the continuation's
record folder as `evidence`. Nothing here selects or starts a continuation by
itself; each one is a request the experimenter publishes after reviewing the
placement before it.

Each paid placement uses a frozen card named `AUDIT-pN.json` in the protected
`cards` directory. The operating agent records the grant digest, campaign,
wave, trial, placement, question, reason, packet digest, model, file-size limit, qualification,
apparatus digest and writer digest before offering its request to the queue.
Use fields `campaign`, `wave`, `trial`, `placement`, `question`, `reason`,
`packet_sha256`, `model`, `qualification`, `apparatus_sha256`, `writer_sha256`
and `grant_sha256`. A claimed trial slot cannot be reused with another request
name or evidence directory. A paid child may have spent money even when its
call timed out. Inspect its exact receipts and keep the slot and original
reservation until reconciliation.

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
