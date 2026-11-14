# Delegated host execution

`host_queue.py` lets an operator enable serial C10 operations from an agent that
cannot use Apple `container` directly. It dispatches the existing launcher and
operator commands, with retained argv, streams and exits. It does not accept
shell commands, replace packet/rehearsal checks, judge scientific work, manage
credits, or confer authority. Use it only under an explicit bounded commission.

## Enable a session

The campaign configuration records its identifier, authority text, exact model,
nonsecret account/workspace/credential labels, base qualification, synthetic
connection, placement ceiling, dollar budget and Console observation. Offline
use permits `console: null` and unfilled account/workspace labels. For live use,
`console` contains `scope`, `month` (`YYYY-MM` in UTC), `limit_usd`,
`starting_spend_usd`, `recorded_by`, `recorded_at` and `credential_binding` (an
attributed statement identifying which key/workspace the setting covers). The
runner checks completeness, current month and positive headroom. It does not
inspect the Console or validate that statement. Console headroom can differ from
the authorized campaign budget; neither extra headroom nor a monthly cap refresh
increases that authorization. Starting spend may be approximate: preserve the
principal's original observation and its precision alongside the configuration.
The experimenter accounts for campaign charges before continuing.

Start from the repository root in a host terminal after committing apparatus:

```sh
python3 -I -B apparatus/c10/host_queue.py /absolute/campaign/queue \
  --config /absolute/campaign/host-offline.json --once
python3 -I -B apparatus/c10/host_queue.py /absolute/campaign/queue \
  --config /absolute/campaign/host-enabled.json --live
```

The first command handles at most one offline request, such as a full Linux
rehearsal with synthetic saved-connection collection and continuation controls.
Inspect that result before
enabling live work. The second runs until `queue/STOP` exists or an operation
fails. It snapshots its configuration and apparatus identity at startup, and
refuses further dispatch if apparatus files change. After a reviewed apparatus
change, restart it; paid launch still needs the new matching rehearsal.

One advisory lock excludes concurrent runners on the same queue. Use one queue
for the entire campaign; starting a new directory would lose its placement count.
All launch paths for the campaign must use that queue. It conservatively charges
one slot when claiming a `live` or `continue` command, including a failed
preflight; actual placement observations remain in the C10 records. Missing claim metadata also
reserves one slot. Slots are never automatically refunded. This small dispatch
bound is not a credit reservation or a measurement of spend.

Keychain access uses the existing [saved connection](README.md#saved-provider-connections)
path. The runner neither caches keys nor changes Keychain access policy. A lookup
may still prompt in macOS, even though no per-trial terminal command is needed.
An unattended terminal loop is not evidence of unattended credential permission.
Choose the item's access policy explicitly outside this runner if that is needed.

## Publish one operation

The agent prepares one nonsecret JSON request in a temporary file, then atomically
renames it into `queue/requests/NAME.json`. Names are lowercase letters, digits
and hyphens, beginning with a letter. Never edit a published request. Read its
result before selecting and publishing the next operation; the queue has no
experiment scheduler. Examples, with absolute paths abbreviated:

```json
{"operation":"rehearse","evidence":"/repo/.scratch/rehearsal-01","submissions":[["case-a","/repo/.scratch/inputs/case-a"]]}
{"operation":"live","evidence":"/repo/.scratch/live-01","packet":"/repo/.scratch/packet.json","sha256":"EXACT_PACKET_SHA256","rehearsal":"/repo/.scratch/rehearsal-01"}
{"operation":"continue","evidence":"/repo/.scratch/live-01","record":"/repo/.scratch/continue-01","packet":"/repo/.scratch/continuation-packet.json","sha256":"EXACT_PACKET_SHA256","rehearsal":"/repo/.scratch/rehearsal-02"}
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
model process, for example on a denied Keychain lookup or a different key. It
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
the delegated experimenter may write a new `claims/NAME/reconciliation.json`:

```json
{"author":"Stewart experimenter","disposition":"Describe the observed effects, remaining obligations and why another placement is now authorized.","evidence":[{"path":"/absolute/checked-observation.json","sha256":"EXACT_OBSERVATION_SHA256"}]}
```

The runner checks that the attributed disposition and referenced bytes exist.
It does not certify the judgment, erase the failure or refund the slot. A claim
with a zero exit also needs ordinary experimenter review: the launcher can
legitimately return zero after an unsubmitted limit stop. No exit code grants
permission to skip that inspection. Reserved decisions still go to the principal.

Creating `STOP` prevents the next operation; it does not cancel an active one.
Interrupting the runner can leave uncertain child/container effects. Inspect
running-work state and retained records before continuing, and remove `STOP`
only when resuming the authorized campaign. Neither stopping nor restarting the
queue disposes of evidence or closes an audit.
