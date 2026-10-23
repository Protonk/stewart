# Planning reset, 2026-10-23

The user chose a six-stage development program and a shorter long-term vision,
with the coordinator managing internal logistics. The reset leaves
`DEVELOPMENT-PLAN.md` and `VISION-PLAN.md` at the root. It retires the other
execution schedules, establishes the fleet convention in standing guidance,
and removes `tests/test_orchestration_plan.py` and its two plan-lifetime tests.
Runtime behavior is unchanged.

The prior CLI-reduction document and three historical reports were compared
byte-for-byte with their source commits after relocation. Submodules remain a
custody-addition candidate. Linux and friend-tested WSL are Rust acceptance
goals; installing a Python container environment is no longer a pending project.
Prior custody decisions and unresolved leads remain identified separately.

## Validation

Python 3.14.8, installed wheel, provisioned locked wheelhouse, default execution
permissions:

```sh
/Users/raccoon/Desktop/Experiments/stewart/.venv/bin/python -I -B /Users/raccoon/Desktop/Experiments/stewart/scripts/check.py --wheelhouse /Users/raccoon/Desktop/Experiments/stewart/.scratch/wheelhouse --result /Users/raccoon/Desktop/Experiments/stewart/.scratch/planning-reset/packaging-314.json tests/test_distribution.py tests/test_authority.py
```

22 collected, 22 selected, 0 deselected, 22 passed, 0 failed, 0 skipped.
The runner and pytest exited 0. The selection exercises distribution rebuilding,
archive membership and import/custody boundaries, including their existing
firing controls and invariance cases. The full runtime suite was not run for
this documentation and plan-dependency cleanup.

The receipt, wheel, logs and captured stdout/stderr remain under
`.scratch/planning-reset/packaging-314*`. The invocation removed its 64 passing
node paths and kept no entries. `scripts/prune.py`, restricted with
`--root .scratch/planning-reset --run packaging-314 --apply`, removed only its
empty artifacts directory; the pruning receipt is in that root's `pruned/`
directory. Its run record remains with this report. Existing historical
run records and artifacts are untouched. Final checks also verify exactly two
root plan files, valid maintained local links, no runtime changes and no
remaining product/test dependency on the deleted orchestration plan.

## Local branch retirement

`main` is the sole local branch. Unmerged tips are preserved as annotated tags:

| Tag suffix under `archive/2026-10-23/` | Commit |
| --- | --- |
| `cli-reduction` | `220dfa6` |
| `click-integration` | `56686e9` |
| `close-followups` | `d4b99f6` |
| `docs/identity-closeout-audit-kit` | `936526c` |
| `fieldwork-run-003` | `cab483a` |

The merged `readme-rehab` and `test-speed` tips remain reachable from `main`.
Four linked-worktree HEADs were detached at their unchanged commits through
their Git administration before deleting the branch names. Index digests were
unchanged. No linked-worktree contents, locks or Stewart custody records were
removed or rewritten. Remote branch management remains with the user, who took
over that part of the cleanup; these tags are local until explicitly pushed.
The pre-change branch tips and index digests are retained in
`.scratch/planning-reset/branch-retirement.json`.
