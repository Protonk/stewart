# Bounded submission prototype

Development-only standalone Rust implementation of the root-owned
[process contract](../../PROTOCOL.md). It does not ship product custody, access
confinement, garbage collection, manager delivery, process stopping or close.

Run `stewart-submission-prototype --store /absolute/existing/ordinary/directory`
with one JSON object on stdin. `--help` describes operations. The directory must
be empty for first init; path components must not be symlinks. All reads and
writes use pinned directory descriptors. Every operation takes a nonblocking
exclusive flock on the directory inode, including reads: contention returns
`busy`. There is no lock-file mutation, so valid dry runs change no store bytes.

The ordered state belongs to a random `instance` plus the caller's audit and
commission hash. Element handles bind instance, random element identity and
version. Preparation handles bind instance and a separately persisted issuance.
Descriptions/names and bytes do not establish identity. Equal-byte replacement
increments revision and element version. Every successful edit, including delete,
increments revision. Prepare and submit do not increment the edit revision.

## Physical layout for independent checking

All members are directly under the store directory; no subdirectories are used.

* `request-<sha256(request_id UTF-8)>.json`: exclusive immutable request binding.
  It contains the exact normalized `intent`, `request_id`, pinned `base` commit
  name/hash (or null for init), planned `candidate` state, `commit_name` when
  applicable, planned `blob` descriptor/name when applicable, and `preparation`
  when applicable. `blob.name` identifies the selected raw payload file; the
  candidate's element descriptor supplies its handle, size and SHA-256.
* `commit-<20 decimal digits>.json`: authoritative contiguous commit chain from
  sequence zero. Each record binds predecessor name/hash, request name/hash,
  and complete state. Only exclusive hardlink publication of a fully staged
  commit makes it authoritative. Readers verify the chain and reconstruct each
  commit from its request binding, then verify current selected payloads.
* `blob-<random hex>.bin`: immutable published exact payload. Every historical
  payload remains. Mapping from element handle to blob is recorded in committed
  request bindings; use the plan's `blob` coordinate for corruption specimens.
* `prepare-<handle>.json`: immutable issuance containing exact manifest and its
  request name/hash. Handles have `p-<instance>-<random hex>` form. Issuance is
  reverified; a caller-supplied digest is not an issued handle.
* `attempt-<sha256(request_id UTF-8)>-<random hex>.json`: exclusive attempt plan naming fresh staging files
  for its bound request before those staging outputs are written. `blob_stage`
  is nullable; `record_stage` names the planned commit stage for init/edits/submit
  or the issuance stage for prepare. Both use the suffix `-record`; use the
  recorded field rather than infer record kind from that suffix. Recovery may
  use only exact verified bytes at names this request's attempts planned.
* `stage-<random hex>-<kind>`: retained staging bytes for requests, attempts,
  blobs, commits, preparations and dispositions. A staged file alone never
  establishes a committed state or issued preparation.
* `state-outcome-<sha256(request_id UTF-8)>.json`: immutable completed outcome
  for init/edits/submit, naming
  the request and exact committed/issued publication digest. Its identity is
  planned in the request before effects. It is published after synchronization
  and before success; a lost reply or interruption before it can be completed
  from the same verified publication. A missing acknowledged publication is
  diagnosed from this separate retained receipt. These state outcomes alone are
  scanned as global chain dependencies, selected by their prefix before decoding.
* `prepare-outcome-<handle>.json`: the preparation's own immutable completion
  receipt, directly locatable from its issued handle. Preparation resolve/resume/
  cancel/submit validates this receipt and its publication; acknowledged missing
  issuance stays `integrity_error`, never becomes a pending issuance to recreate.
  Unused preparation issuance, request or outcome damage does not block ordinary
  inspect/read/new edits. A submitted commit explicitly depends on its chosen
  issuance, so damage to that dependency still refuses current-state claims.
* `cancel-<sha256(request_id UTF-8)>.json`: exclusive caller-attributed
  cancellation of an uncommitted request. All partials remain.

The request binding precedes payload/commit/issuance effects. An attempt plan
precedes its staged outputs. Every record is exclusively created; no record,
payload or historical receipt is overwritten or removed. Binding publication
itself uses a retained fully written stage. Unpublished request-stage residue
is not an issued request and cannot be adopted by recovery.

## Resolution shapes and boundaries

`resolve` takes the caller-known request ID, or a preparation handle for confirmed
submit. It returns `ok:true`, `request_id`, `status` (`pending`, `committed`, or
`cancelled`), `operation` (recorded intent), and `outcome` (the original success
object if committed, otherwise null). A cancelled result also includes the
attributed `cancellation`. Missing requests refuse `unknown_request`; damaged
records refuse `integrity_error` rather than becoming absence.

`resume` takes the same ID and returns the original operation's success object
(with `request_id`), completing only that binding's plan. Repeating an ordinary
mutation with identical ID/intent also completes or returns that exact operation.
A changed intent refuses `request_conflict` before touching source bytes. Confirmed
submit normalizes omitted irrelevant defaults and uses its preparation handle as
its request ID. Default/false submit does not bind any request.

`cancel` returns `ok:true`, `request_id`, `status:"cancelled"` and
`cancellation:{"attribution":"caller","reason":...}`. Committed operations
refuse `already_committed`; unverifiably damaged requests refuse `integrity_error`.
Cancelled requests cannot resume (`request_cancelled`). A pending edit whose
predecessor is no longer current refuses `stale_request`; cancellation remains
supported. These are development probes of interrupted tool operations, not a
proposed family of product authoring stages or investigative retries.

A committed replay returns the original outcome/state, which can precede the
current state. Current `inspect` remains the route to the latest selection.
Replay never rereads the original source. Pending recovery adopts a planned
published payload or complete planned stage after verifying exact identity;
otherwise it requires the original source still to match. Missing source is
reported; caller cancellation accounts for an undertaking whose bytes are lost.
An incomplete stage is retained and a new planned attempt can stage exact bytes;
no unplanned file or matching unrelated file is adopted.

## Commit, interruption and limits

A process holds the directory lock through validation, publication, synchronization
and reply construction. Readers therefore see a verified old or new complete
state, or `busy`; they cannot observe half an in-process publication. Process
exit releases the lock. Publication linearizes at the exclusive commit hardlink;
file and directory synchronization precede success. Local process evidence does
not prove device durability or behavior after power loss.

`STEWART_PROTO_PAUSE` is a test-only barrier on state-changing commits:
`after_stage`, `before_publish`, `after_publish`, `after_sync`. It emits/flushed a
JSON stderr marker with `hook`, `request_id`, `commit`, then SIGSTOPs. `after_stage` is after the held payload is complete/verified (or the no-payload
candidate is prepared), before commit stage creation; `before_publish` is after
complete synchronized commit stage write and immediately before link publication;
`after_publish` is before directory sync; `after_sync` is before reply. Resume
uses the same commit identity. No barrier runs for preparation or dry run.

Test bounds are 32 active elements, 1 MiB per element, 8 MiB active bytes, 64 KiB
control input, bounded strings and 2 MiB records. These are not product payload
policy. All input and record JSON uses the same nested duplicate-key rejecting
parser; request and record schemas reject unknown fields. Arbitrary bytes,
empty files, qualified findings and reframed/no-answer prose remain permissible.

The safe descriptor module and duplicate-key parser are copied/adapted from
`successor/src/safe.rs` and `successor/src/control.rs` at cf7216f, whose pinned
hashes are in `.scratch/submission-prototype-01/START.json`. Existing qualification
does not transfer. The prototype uses only the same exact dependency versions,
offline; build products belong to assigned implementation scratch. Apple Silicon
macOS Rust/cargo 1.99.0 is the local target; no Linux/WSL claim is made.

Every request records the exact executable SHA-256. Mutations require the initial
writer identity (and pending resume its own writer); a different binary refuses
`writer_mismatch`. Inspect/read/resolve and help remain available. This finite
prototype guard does not implement production runtime handoff. Copied executables
with identical bytes retain the same writer identity.

Resolution and cancellation validate pending plan semantics against the exact
verified historical predecessor, even after another operation has advanced the
current state. Schema-valid but inconsistent pending plans cannot be disposed as
if they were verified undertakings. Missing, unreadable and malformed record
causes remain distinguished in the `integrity_error` message.

Attempt lookup is scoped by the request-key digest in its filename before decoding.
Within that selection, the complete stored request name and digest must match.
A malformed unrelated historical attempt remains retained without blocking a
new undertaking; malformed or mismatched relevant attempts refuse recovery.

Preparation is issuance only: its own operations depend on its recorded request,
manifest, publication and any recorded completion receipt. Ordinary read/edit
operations do not acquire that dependency merely because a preparation was once
issued. A state-changing submission explicitly acquires its chosen preparation
dependency. Separate outcome filename namespaces implement that finite distinction
before decoding; no record is repaired, rewritten, disposed or globally cleared.
