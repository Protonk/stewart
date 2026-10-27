# Implementation return

The bounded standalone Rust prototype implements the root-owned process contract.
Source is `crate/`; mechanism, layout and recovery are in README. Root owns final
integration and independent-check/reviewer disposition. Nothing was changed in C,
frozen Python, product tests or shared documents. No network, Git mutations,
nested delegation, fieldwork access, removal or product custody operation ran.

## Executables and provenance

Primary executable:
`/Users/raccoon/Desktop/Experiments/stewart/.scratch/submission-prototype-01/implementation/target/debug/stewart-submission-prototype`

Final R4 build-06 SHA-256:
`cacc57df666c1b1eeef85c14a3a17a2a7d679d21bd480358548874062838c0de`.
Cargo/rustc 1.99.0 on aarch64 Apple Silicon macOS; dependencies match the original
exact pinned versions. Cargo.lock generated offline, all builds offline/locked,
CARGO_TARGET_DIR exclusively assigned implementation scratch. build-06 exits zero
without warnings. Source/README and binary are ready for root's final freeze.

Writer-control executable is alongside primary as
`stewart-submission-writer-control`, SHA-256
`95efb5a07bfd53f0ae49b3f876a59fd06e48cb6c441bcb9b086307a5f74a7671`.
It is a separately compiled valid executable,
not patched executable bytes. Exact copied source and changes are retained in
`implementation/writer-variant-source-03/` and `WRITER-VARIANT-03.json`: only Cargo
package/binary name and a help-only label differ. `writer-build-03` records its
command, PID and output. Creating-binary digest guards mutation; read/inspect/
resolve/default-false submit remain verified read operations. No production
runtime handoff is implemented.

The source base is cf7216f plus root-pinned dispatch documents. `safe.rs` and
`control.rs` were copied/adapted from successor at that base; their original hashes
are in the root START record. This does not import its earlier qualification.
Safe code adaptations add unsynchronized publication for exact barriers, rename
busy, and remove its unused inventory helper. Control JSON retains the shared
nested duplicate-key parser. Request field whitelist additionally covers unit
operations that serde's enum annotation did not protect.

## Mechanism and supported recovery

All supported operations use a pinned ordinary directory and nonblocking directory
flock. Payload reads traverse no symlink components and reject special files.
One complete immutable commit, exclusively hardlinked after staging, publishes
whole selected state. Every read verifies the chain/request/state binding and
current exact bytes. Separate planned state outcomes diagnose a missing
acknowledged state publication. Preparation outcomes use a separate handle-based
namespace and are checked only when the requested operation depends on that
issuance. Submitted commits retain their chosen-issuance dependency. Files and directories synchronize before success;
this is implementation behavior, not device/power-loss qualification.

Request keys bind exact normalized intent before output effects. Attempts have
request-digest-scoped exclusive filenames and validate their complete stored
request binding. Resume adopts only this request's planned exact payloads/stages;
source paths are provenance, not a dependency of committed replay. A stale pending
predecessor refuses and can be cancelled. Cancellation attributes its supplied
reason, preserves all bytes and refuses committed/damaged outcomes. Preparation
issuance binds exact ordered selection and audit/instance/commission. Edits stale
old preparations; confirmed same-handle submit seals one selection and recovers
that same undertaking. Every later edit refuses.

Test-only SIGSTOP barriers distinguish held payload/no-payload candidate before
commit stage (`after_stage`), complete commit stage (`before_publish`), exclusive
link before directory sync (`after_publish`), and synchronized commit before reply
(`after_sync`). Actual independent driver results belong to the driver, not this
implementation return.

## Retained actual checks and observed defects

All paths below are relative to `.scratch/submission-prototype-01/implementation/`.
The command recorder retains exact argv, cwd, selected build environment, PID,
start/end, exit, separate stdout/stderr. Every check keeps its stores and witnesses.

| Evidence | Actual scope/outcome |
| --- | --- |
| `lock-01`, `build-01` | Offline lock generation and first build passed. Build had one unused-function warning, retained. |
| `smoke-01/RESULT.json` and command log | 11 commands on first binary b6463c1: init/add/read/source-loss exact replay/prepare/dry run/submit/repeat/final edit refusal/resolve/inspect passed. This is smoke only. |
| `fix-comparison-01/RESULT.json` | Three before/after comparisons, 16 commands. v1 accepted inspect's unknown field, treated a moved acknowledged final commit as absent, and cancelled a semantically corrupted pending plan. Fixed build-03 refused each with the expected diagnostic. Witness originals and SIGKILL marker/PID retained. |
| `format-01`, `build-04` | Build-03 was formatted and its unused copied inventory helper removed; build-04 602825 compiled without warnings. These were nonsemantic changes but changed the executable digest. |
| `attempt-comparison-01/RESULT.json` | Six cases/18 commands on exact build-04 602825 versus exact prior build-05 b14f590. Corrupted unrelated init attempt blocks a new add only before the fix; healthy addition succeeds on both; corruption of the pending request's own attempt refuses resume on both. Inspect of prior state is invariant. |
| `format-02`, `build-05`, `writer-build-02` | Prior candidate formatting/build and valid differing-writer build passed without warnings. |
| `preparation-comparison-01/FAILURE.json` | R4 comparison stopped at 44 commands because the old submitted-missing-issuance path reported invalid_handle before its global outcome pass. The local comparison had expected integrity_error. Failure is attributed to that baseline expectation; no source change followed. |
| `preparation-comparison-02/RESULT.json` | 14 cases/124 commands on exact prior b14f590 and exact final cacc57. Healthy prepare/read/submit is invariant. Missing current/stale unused issuance and corrupt unused outcome no longer block inspect/read/new edit; own preparation resolve/resume/cancel/submit still refuse. Damage to chosen submitted issuance/outcome and missing acknowledged state publication remain refusals. |
| `format-03`, `build-06`, `writer-build-03` | Final R4 formatting/build and valid differing-writer build passed without warnings. |

Exact distinction: fix-comparison-01's fixed executable is build-03
`87d5a5e370e547bb997b3c6513a25cf96f50fac43fd4fe3af0ed0d63c43f5ccf`, **not** build-04 `602825…` or R4 final `cacc57…`.
The root's final report must use the independent driver's runs on the final digest
for combined qualification. Earlier executables `prototype-v1`, `prototype-v2`,
and `prototype-writer-v2` remain, as do every comparison's source/witness files.
No passing result rewrites the failing baseline.

Driver-reported observations, not independently recounted here: run-002 on first
binary had 58/59 passing selectors, with inspect unknown-field acceptance failing;
run-004 on 602825 passed eight focused selectors including writer difference.
Root/reviewer requested the unrelated-attempt recovery fix (R3), then the unrelated
preparation-dependency fix (R4); final driver and
reviewer disposition remain their responsibility. No Rust unit tests or Python
installed-wheel tests were added/run: product Python was untouched, and the main
qualification is the commissioned independent process driver.

## Limits and unfinished scope

No known required protocol operation is a stub. Final independent qualification
and reviewer disposition are pending when this return is written. This prototype
retains every payload, obsolete version, partial and receipt. It provides no
physical disposal, access confinement, manager delivery, auditor stopping,
retirement/close, complete human handback, Linux/WSL, storage-replication or
power-loss guarantee. Local filenames/digests are integrity bindings, not a
security boundary against a principal with arbitrary authority to rewrite the
whole store. Advisory locking coordinates supported invocations.

No published request binding means no issued request to recover; an unpublished
request-stage residue is never adopted. An interrupted initial binding can leave
an uninitialized nonempty directory; init still requires an empty directory and
preserves that residue, so a fresh explicit store is required. This boundary does
not claim recoverability of bytes never captured. A pending request whose exact
source and all its planned exact captured bytes are gone can be cancelled but
cannot recreate lost bytes. Test payload/record/directory bounds are finite and
not product capability choices. Writer changes refuse old mutations rather than
migrate them; final evidence must use fresh stores under its own binary.

Root froze the prior b14f590 candidate in
`.scratch/submission-prototype-01/REVIEW-INPUTS-02.json`. Subsequent independent
review found R4, and root explicitly commissioned its bounded follow-up. The new
cacc57 source/README and primary/control executables are frozen in
`.scratch/submission-prototype-01/REVIEW-INPUTS-03.json` with the admitted protocol
dependency clarification. No implementation edit followed that freeze. Old source snapshots/binaries,
controls, failures and raw witnesses remain; no historical receipt was rewritten.
