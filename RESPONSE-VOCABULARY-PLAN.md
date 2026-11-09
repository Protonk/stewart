# Product response vocabulary

The vocabulary revision is implemented at f6a2fd5 and repaired at bb786d5.
`acceptance-vocabulary-03`, from c953bed, qualifies it on Linux, and both
launchers are rehearsed and reviewed on that executable.

## Next action

**Disposition any repairs from the commissioned vocabulary study.** The principal
authorized preparation, the bounded Haiku comparison and targeted repairs on
2026-11-09. The [study specification](apparatus/studies/vocabulary/STUDY.md) fixes
the comparison; its exact setup is retained in `.scratch/vocabulary-study-01`.
Stabilize the selected terms and close this plan when its selected work is
complete. A live commission still needs rehearsal coverage matching its own
inputs and credential route.

## Verified state and remaining limits

[The qualification record](apparatus/qualified.md) owns the counts and digests.
`acceptance-vocabulary-03` passed all 125 cases on native aarch64 and all 123
on emulated x86_64, with zero failed checks outside control variants, every
sabotage and driver control fired, and no skips. `c8.close-running` passed and
its control fired on both. The native timing gates passed; the slowest protocol
call measured 98.7 ms against the 200 ms tripwire.

Two earlier runs stay recorded as failed and pinned. `acceptance-vocabulary-01`,
from f6a2fd5, failed on the missing receipt command in concise status, an old
seal-field assertion, and compaction observers expecting absence after scripted
submission. `acceptance-vocabulary-02`, from bb786d5, passed every functional
check and failed only the native protocol timing gate: the 4 MiB
`record_observation` call of `c3.limits` measured 121.26 ms against the then
120 ms tripwire. The focused comparison pinned at `.scratch/vocabulary-timing-01`
found that call at 99 to 132 ms on three builds, including the previously
qualified one, with differences between builds smaller than between repeats;
`review-and-decision-01.json` there records the principal's move to 200 ms.
The service binaries of the second and third runs are byte-identical.

The original native implementation checks and fake-audit/operator/report
comparisons remain in `.scratch/vocabulary-implementation-01`, and the repair
checks in `.scratch/vocabulary-linux-repair-01`, under their own source
bindings.

Both launcher rehearsals ran at apparatus commit 32359be on the
`acceptance-vocabulary-03` native-aarch64 executable, with the fake provider and
no model calls, and are pinned with their reviews. `.scratch/c10-vocabulary-launch-01`
passed the rehearsal gate: 13 of 13 audits observed, 14 reviewer, seven operator
and 11 report comparisons passed, and all 12 reviewer controls fired.
`.scratch/sanity-launch-05` passed its seven scenarios with 26 of 26 exact
authentication matches. In both, the two Linux process-access controls fired and
inspection of the Stewart process was denied. Neither exercised a saved Keychain
connection, supplied study templates or a study-build override.

## Selected scope and completion

Enduring meanings and access decisions belong to
[CONTRACTS](CONTRACTS.md#shared-terms), with exact observations and reply shapes in
[INTERFACE](docs/INTERFACE.md#16-observed-authoring-and-seal) and
[QUESTION-FORMS](docs/QUESTION-FORMS.md). Reply revision 2 changes the ordinary
manager account, authoring/seal observations and captured family metadata. It
keeps control inputs, archive records, prepared answer bytes and return formats.
Historical receipts retain their schemas; no compatibility aliases are introduced.

A supported live manager viewer and a standalone operating-history companion
remain deferred to manager-consumption design. The auditor's host-path,
credential, material-selection and actor/mutation boundaries remain in force.
Auditor success cannot establish human manager usability from replies the model
never sees; keep attributed readings distinct from mechanical lifecycle checks.

Give unresolved work an explicit disposition, retain its evidence and delete this
plan once the selected work is complete. Preserve independent driver authorship
under [AGENTS](AGENTS.md#preserve-independent-evidence).
