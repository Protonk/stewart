# Product response vocabulary

The vocabulary revision is implemented at f6a2fd5 and repaired at bb786d5.
`acceptance-vocabulary-03`, from c953bed, qualifies it on Linux. The launcher
rehearsals on that executable are outstanding.

## Next actions

1. **Rehearse and review both affected launchers.** Use the qualified
   native-aarch64 executable of `acceptance-vocabulary-03`, each launcher with a
   fresh retained directory:

   ```sh
   python3 -I -B apparatus/c10/c10.py rehearse \
     "$PWD/.scratch/c10-vocabulary-launch-01" --qualification acceptance-vocabulary-03
   python3 -I -B apparatus/c10/c10.py review "$PWD/.scratch/c10-vocabulary-launch-01"
   python3 -I -B apparatus/sanity/launch.py rehearse \
     "$PWD/.scratch/sanity-launch-05" --qualification acceptance-vocabulary-03
   python3 -I -B apparatus/sanity/review.py "$PWD/.scratch/sanity-launch-05"
   ```

   Follow the [C10](apparatus/c10/README.md) and
   [sanity](apparatus/sanity/LAUNCHER.md) instructions, including Linux
   process-access controls. Record and commit the reviewed bindings. These are
   fake-provider checks, with no model calls. A live commission still needs
   rehearsal coverage matching its own inputs and credential route.
2. **Disposition any repairs from the bounded vocabulary study.** Stabilize the
   selected terms and close this plan when its selected work is complete. The
   coordinating plan owns when the study and broader auditor work occur; this
   plan does not authorize paid placements.

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
bindings. Linux process-access controls remain owed by the rehearsals.

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
