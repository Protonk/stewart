# Product response vocabulary

The vocabulary revision is implemented at f6a2fd5. Repairs from its first Linux
acceptance run have passed native verification. Linux qualification is still
outstanding.

## Next actions

1. **Run full Linux acceptance from the repaired, committed HEAD.** Use a fresh
   evidence directory, proposed `.scratch/acceptance-vocabulary-02`:

   ```sh
   sh apparatus/acceptance.sh "$PWD/.scratch/acceptance-vocabulary-02"
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

This is native verification, not Linux qualification. The earlier
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
