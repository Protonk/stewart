# Prototype process contract for implementation and independent checks

Root-owned interface, selected under the bounded prototype commission. This is
development-only and does not choose the public product wire schema or payload
bounds. Worker proposals to change it return to root before dependent edits.

Binary: `stewart-submission-prototype --store ABSOLUTE_EXISTING_DIRECTORY`.
One UTF-8 JSON control object on stdin; one JSON outcome on stdout. `--help` is
useful and side-effect free. Reject repeated/unknown fields and invalid JSON.
All paths use explicit safe reads; no symlink traversal/special-file reads.
Store is a caller-created ordinary directory; init requires an empty store.
Compute implementation identity before allocating applicable records. Record the
creating writer and refuse a different writer's mutation; independent supported
reads may remain available. A copied executable with identical bytes is the same
writer. These guards do not qualify a runtime-handoff service.

Common errors: exit 2, object `ok:false`, stable `reason`, `message`, `paths`
array, `next_step`, and `effect` (`unchanged`, `partial`, or `uncertain`). Never
promise no effects merely from an exception. Successful operations exit 0 and
return `ok:true`. Diagnostic names below are prototype interface commitments.

Requests (unknown fields refused):

```
{"op":"init","audit":"audit-a","commission_sha256":"<64 hex>","request_id":"i1"}
{"op":"add","request_id":"a1","name":"answer","source":"/absolute/file","size":12,"sha256":"<64 hex>"}
{"op":"replace","request_id":"r1","handle":"<element>","name":"answer","source":"/absolute/file","size":12,"sha256":"<64 hex>"}
{"op":"delete","request_id":"d1","handle":"<element>"}
{"op":"inspect"}
{"op":"read","handle":"<element>"}
{"op":"prepare","request_id":"p1"}
{"op":"submit","handle":"<preparation>"}
{"op":"submit","handle":"<preparation>","submit":false}
{"op":"submit","handle":"<preparation>","submit":true}
{"op":"resolve","request_id":"a1"}
{"op":"resume","request_id":"a1"}
{"op":"cancel","request_id":"a1","reason":"source no longer available"}
```

These recovery commands are development-only probes of interrupted operation
accounting, not selection of new product authoring stages or audit retry APIs.
`resolve` reports the recorded operation; `resume` explicitly completes only its
planned effects, never different intent. `cancel` records attributed caller
disposition of an uncommitted operation, retains partials, and refuses a committed
or unverifiably damaged outcome. These are interrupted-operation handling, not
manager-operated authoring stages. Confirmed submit uses its issued handle as
request identity; repeating it resolves/completes the same undertaking. If needed,
resolve/resume/cancel may accept that handle as request_id, documented precisely.
No investigated execution is performed or replayed. No unkeyed mutations are
admitted by this prototype; each supplied key binds exact intent before effects.

`state` in inspect and successful init/mutations/submit contains `audit`, `instance`
(distinct store/lifetime identity), numeric `revision`, ordered `elements`, boolean
`submitted`, nullable `submission_handle`. Each element contains `id`, `version`,
`handle`, `name`, `size`, `sha256`. Add/replace also return `element`; read returns
`element` and `bytes_hex`. Equal names are descriptive and allowed; identity is
tool-assigned. Empty files and non-answer/reframed text are legitimate. At most
32 active elements, 1 MiB per element, 8 MiB active bytes; cap control input and
records reasonably. These are test bounds only. Reject sources whose observed
bytes differ from expected identity (`source_mismatch`); store source provenance
without depending on its future existence.

Prepare returns `handle`, `manifest` and `state`. Manifest exposes the same ordered
element descriptors plus audit/instance/revision and commission identity. Exact
held bytes are reverified. Issuance is persisted and the handle binds the exact
manifest, not caller-supplied reconstruction. Preparing is not an edit. Any
successful edit increments revision, including equal-byte replacement.

An unsubmitted preparation, current or stale, is not a dependency of ordinary
current-answer inspect/read/edit operations. Its own resolution, resumption,
cancellation and submission verify its recorded acknowledgment and issuance;
acknowledged damage cannot become ordinary pending/absence. A submitted commit
does depend on its selected issuance. Retaining a record does not make every
unrelated operation depend on it. This makes the no-authoring-stage boundary
explicit following R4's observed failure; it grants no repair or removal.

Dry run returns `dry_run:true`, `would_submit:true` and `state` without changing
store bytes or publishing a submission. Successful confirmed submit returns
`dry_run:false`, `handle` and final `state`. It seals the current selection
atomically; every later edit refuses `already_submitted`. A different preparation
handle after final submission also refuses `already_submitted`; identical confirmed
repeat returns the same outcome. Earlier preparation after an edit refuses
`stale_preparation`; old element versions refuse `stale_handle`; forged/wrong-audit
handles refuse `invalid_handle`; corrupted held material refuses `integrity_error`;
changed key intent refuses `request_conflict`; overlapping invocations may refuse
`busy` if locking is nonblocking. Bounds use `limit_exceeded`.

Storage remains independent of C and frozen Python. Use exclusive receipt creation,
planned output identities before effects, complete atomic commit publication,
descriptor-safe reads, shared duplicate-key parsing and verified chain/selection
bindings. Do not overwrite receipts. Delete removes current membership only;
retain all payloads, partials and operation records as development witnesses.
No physical garbage collection or claims about OS auditor confinement.

Test-only deterministic barriers: `STEWART_PROTO_PAUSE` accepts `after_stage`,
`before_publish`, `after_publish`, `after_sync` for authoritative state-changing
commit publication (not every planning receipt). At the specified point emit and
flush one stderr JSON line with `hook`, `request_id`, and the planned commit
name; then stop via SIGSTOP until the driver sends SIGCONT or SIGKILL. After-stage
follows payload staging/verification (or candidate preparation for a no-payload
operation), before commit-stage construction. Before-
publish follows complete staged commit write, after-publish precedes directory
sync, after-sync precedes normal reply. A barrier affects only that invocation.
Retain this hook as explicitly development-only. Independent driver waits for its
marker, proves the fired window with the captured stores/outcomes, and records
actual PID/signals/exit. No uncontrolled sleeps or unobserved kill claims.

Mechanism/path-layout details belong to the implementer, who must publish them in
README before independent corruption/interruption checks. Root resolves ordinary
interface ambiguities. Driver tests use only published fields and those documented
layout coordinates, with an external raw witness and unrelated working directory.
