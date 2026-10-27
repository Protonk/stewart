# Implementation checkpoint

2026-10-27, initial checkpoint. Read root AGENTS, coordination README/standing
orders, bounded COMMISSION/BRIEF/PROTOCOL, NEXT-WORK, DESIGN, FAILURE-WALKTHROUGH,
relevant CONTRACTS sections, DEVELOPMENT, and pinned START/toolchain record.
No implementation or build has run. Source base is cf7216f plus admitted root
commission/protocol/briefs. Writes are restricted to this attempt and assigned
implementation scratch; no nested delegation, network, Git, product changes or
removal is permitted.

Selected mechanism: descriptor-pinned flat store and nonblocking whole-directory
flock for every operation; exclusive immutable request bindings; planned blob and
commit identities; fully written staged commits published by exclusive hardlink;
verified predecessor chain and exact request-to-commit binding. All payloads,
partials, attempts and receipts retained. Preparation issuance is persisted with
exact ordered manifest; instance-bound opaque handles prevent cross-store use.
No access confinement or power-loss qualification is claimed.

Next: publish precise layout/recovery response shapes in README, implement the
standalone crate using copied/adapted C safe/control modules with provenance, then
run offline build through a command recorder preserving argv/cwd/PID/streams/exit.
Open detail: interrupted uncommitted request may be stale after another edit;
resume will refuse and supported cancel records caller disposition while retaining
all bytes. Damaged committed state must remain diagnostic, never treated absent.

Milestone: standalone Cargo manifest, copied/adapted safe/control modules and core
implementation written. README layout/recovery shapes published to root and driver.
No build/check result exists yet. Root requested creating-binary identity guard
and distinct interruption windows; implementing those before first build.
`after_stage` will be after complete held payload staging/verification but before
commit stage creation; `before_publish` after complete synchronized commit stage.
Next: offline lock generation/build with recorded subprocess metadata, fix compile
failures, then report driver readiness. Build target remains assigned scratch.

Milestone after first independent checking: first build b6463c1 passed local
smoke11; driver reported 58/59 selectors with unit-variant inspect accepting an
unknown field. Explicit request field whitelist fixed that. Added semantic
validation of pending requests against their historical predecessor and planned
immutable outcome receipts, detecting a missing acknowledged publication. Local
fix-comparison-01 preserved three failing-v1/passing-fixed comparisons (16 calls).
Formatted build-04 primary SHA-256 602825b5 was given to driver; exact full hash,
source/digest variants and command records are in retained implementation scratch.

Root accepted reviewer R3: decoding unrelated attempts before filtering can block
new edits after historical attempt damage. Fix now scopes attempt filenames to
request ID digest before decoding, then checks exact request binding. No bytes are
removed; relevant damage still refuses. Next: fresh before/after/control evidence,
final formatted offline build and writer-control variant, then final readiness.
Root/driver preserve all earlier binaries/results; no old store is resumed under
a different binary. Source changes remain confined to this attempt.

Final candidate milestone: build-05 primary b14f590ad1c67256006382210b97d41c9a58bacace85fbea70334f564cd60b29
passed offline/locked without warnings. README/source frozen for root; only this
checkpoint/RETURN changed afterward. Root and driver have exact readiness/path.
R3 local before/after controls on exact final candidate: six cases, 18 commands,
all expected differences/invariances passed; old binaries and raw witnesses kept.
Writer-control final source/provenance and build retained under variant-02 paths.
RETURN records implementation scope, exact build/comparison distinctions, retained
failures, supported recovery and limits. Next: respond to final independent
findings if any, otherwise root integrates; no further source edit is in flight.

R4 follow-up accepted by root after final-candidate review. Reviewer probe-fixed-01
confirmed that missing stale preparation issuance incorrectly blocks ordinary
inspect/read/new edit through global outcome scanning. Read that saved probe and
reviewed the dependency path. Prior primary b14f590 and valid variant139509 remain
retained; all old driver/reviewer evidence remains untouched.

Selected correction: separate planned state-outcome and prepare-outcome filenames;
only state-changing outcomes participate in global chain acknowledgement checks.
Prepare outcome is directly locatable by issued handle, so its own resolve/resume/
cancel/submit can still diagnose acknowledged missing/damaged issuance, while an
unrelated preparation adds no current read/edit dependency. Submitted commits
retain their explicit chosen-issuance dependency. Next: implement, document exact
attempt fields and dependency scope, run before/after with healthy/relevant
controls, build new distinct valid writer variant, and request a new root freeze.

R4 completion milestone: build-06 primary cacc57df666c1b1eeef85c14a3a17a2a7d679d21bd480358548874062838c0de
compiled offline/locked without warnings. Separate state/prepare outcome prefixes
and direct handle lookup now scope dependencies before decoding. README also names
attempt.record_stage and nullable blob_stage exactly. No source change followed
this build. Local preparation-comparison-02 passed 14 cases/124 commands on exact
prior/fixed binaries. Failed comparison01 kept 44 commands and identifies its
baseline diagnostic-assumption error, not an implementation change.
Final valid writer variant03 built with exact copied-source provenance. Root and
driver informed of new readiness and root is preparing new freeze. RETURN updated
with R4 lineage, dependency mechanism, counts, preserved failures and limits.
Next: root-owned independent final 72 selectors/review disposition; respond only to
new accepted bounded findings, otherwise stop with this return.

Root confirmed candidate03 freeze in REVIEW-INPUTS-03.json: primary cacc57… and
valid writer control 95efb5…, source/README/protocol pinned. No implementation or
README edit followed that freeze. Final return saved; implementation assignment
is complete subject to root-owned independent qualification and disposition.
