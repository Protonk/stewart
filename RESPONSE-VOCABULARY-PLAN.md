# Product response vocabulary

The vocabulary revision is implemented at f6a2fd5 and repaired at bb786d5. The
second Linux acceptance run passed every functional check on both architectures
and failed only the native protocol timing gate. The principal has raised that
tripwire to 200 ms. Linux qualification is still outstanding.

## Next actions

1. **Run full Linux acceptance from the committed HEAD that carries the 200 ms
   tripwire.** Use a fresh evidence directory, proposed
   `.scratch/acceptance-vocabulary-03`:

   ```sh
   sh apparatus/acceptance.sh "$PWD/.scratch/acceptance-vocabulary-03"
   ```

   Review both architectures, all controls and native timing gates. In particular,
   exercise `c8.close-running` and its lock control, which macOS cannot check.
   Record the actual outcome with `apparatus/qualified.py extract`, validate it
   with `check`, and commit the generated qualification pair. A failure needs
   diagnosis and disposition before the affected capability is called qualified.
2. **Rehearse and review both affected launchers.** Use the resulting qualified
   native-aarch64 executable and its exact qualification ID for `c10.py rehearse`
   and `sanity/launch.py rehearse`, each with a fresh retained directory. Follow
   their [C10](apparatus/c10/README.md) and [sanity](apparatus/sanity/LAUNCHER.md)
   review commands, including Linux process-access controls. Record and commit
   the reviewed bindings. These are fake-provider checks, with no model calls.
3. **Disposition any repairs from the bounded vocabulary study.** Stabilize the
   selected terms and close this plan when its selected work is complete. The
   coordinating plan owns when the study and broader auditor work occur; this
   plan does not authorize paid placements.

## Verified state and remaining limits

The latest evidence is `.scratch/vocabulary-linux-repair-01/native-01`:

- Both full Rust configurations passed; the source inventory stayed unchanged.
- Driver self-test: **352 checks passed, zero failures or skips**. Inventory:
  123 cases.
- Targeted acceptance: **14 selected, 13 ran and passed, zero failed, one skipped**.
  All 15 runnable sabotage controls fired; the Linux-only case and its control
  were skipped. There were zero failed checks outside control variants and no
  broken checks. Expected failures inside sabotage variants are firing evidence.

This is native verification, not Linux qualification.

`.scratch/acceptance-vocabulary-02`, from bb786d5, is recorded as failed. On
native aarch64 124 of 125 cases passed, with zero failed checks outside control
variants and all 74 sabotage controls fired, including `c8.close-running` and
its control; emulated x86_64 passed all 123 cases. The one failure was
`c9.protocol-timing-gate`: the 4 MiB `record_observation` call of `c3.limits`
measured 121.26 ms against the 120 ms tripwire. The focused comparison in
`.scratch/vocabulary-timing-01` ran that call 12 times on each of the
`acceptance-05`, `acceptance-vocabulary-01` and `acceptance-vocabulary-02`
builds: medians of 113 to 116 ms, a range of 99 to 132 ms, and differences
between builds smaller than between repeats of one build. The qualified baseline
crossed 120 ms twice. It is a diagnostic in one sitting, not qualification. The
principal then set the tripwire to 200 ms; the driver's self-test and case list
passed natively in `.scratch/protocol-budget-200-01`. A run under the new
tripwire is still owed.

The earlier
failed `.scratch/acceptance-vocabulary-01` remains recorded as failed. Its three
causes were the missing receipt command in concise status, an old seal-field
assertion, and compaction observers expecting absence after scripted submission.
The original native implementation checks and fake-audit/operator/report
comparisons remain in `.scratch/vocabulary-implementation-01`, under their own
source bindings. Linux process-access controls remain owed by the rehearsals.

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
