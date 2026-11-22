# Captured acceptance-reader inputs

These fixtures contain exact local Linux acceptance records. Both
`readiness-02` result files include the full case, variant and control inventory,
including each of the four credential cases. `readiness-01` preserves an earlier
ARM run with two skipped cases. The JSON files are stored in gzip containers;
decompression reproduces the original bytes. [ORIGINS.json](ORIGINS.json) records
every source path, original size/digest and stored size/digest.

| Record | Original bytes | Original SHA-256 |
| --- | ---: | --- |
| `readiness-02/driver-arm64/evidence/RESULT.json` | 757607 | `d3be1252e1869ad48a70969906697889f708d08053138a35bd548f6025bc40e0` |
| `readiness-02/driver-amd64/evidence/RESULT.json` | 757297 | `b9da0b487e48de690998d7a0995e35d1a3d348f08e14fe3fbe361fb54ecc756f` |
| `readiness-01/driver-arm64/evidence/RESULT.json` | 757555 | `095467ffeec573c10eeeb1e10fa67030d736217d83d9997a85b94e37456600aa` |
| `readiness-02/driver-{arm64,amd64}/selftest.stdout` | 12950 each | `d8ec77aa5934e3d933e9ef2621fd946432c9b0b54d20d436a0a6b9b304955e22` |

The fixture sources were captured under `.scratch/acceptance-readiness-02/` and
`.scratch/acceptance-readiness-01/`. The later run completed on 2026-11-13,
with 133 ARM cases and 131 emulated x86 cases, no skipped cases, 79 firing
sabotage controls, 21 firing driver controls and 403 passing selfchecks on each
architecture. Its source was `0fdac9450aa0d1a72d1465b17b7e3e5038796c71`.
The earlier result reports exit 0 while marking `c12.run-refusals` and
`c19.bounds.paths` as `skipped`; all four credential cases still pass.
The [qualification index](../../../../apparatus/qualified.md) owns the qualification history.

The selected build records are the complete two-byte exit records for
`build-release`, `build-test`, `static-stewart`, `static-stewart-test`,
`build-glibc`, `static-stewart-glibc`, `cmp-release-test` and `run-release`, for
both architectures. The negative build controls (`static-stewart-glibc`
and `cmp-release-test`) record exit 1; the others record exit 0. The fixtures
also include the complete selftest and evidence-copy exit records. These are
the fields consumed by the tested reader; they do not reproduce compilation or
ELF inspection.

## Comparisons and limits

[The test helper](../acceptance_fixtures.py) verifies stored and original digests
before returning a fresh object. The sanity test uses the complete original
results as positive inputs. Each negative changes one required case or release
variant property: missing/duplicate membership, outcome, skipped parts, skip
reason, binary or sabotage identity. Reversing case order preserves the result.
The historical skipped run remains a positive for this narrow credential-case
predicate; that predicate alone cannot qualify a whole run.

The C10 study test derives an explicitly synthetic result by changing only
`c19.arrangement`'s `open.system-bytes` check to a failure, plus the corresponding
case/variant outcomes, failure inventory, exit and aggregate counts. Its
selftest projection changes the matching family check and summary to 402 passed
and one failed. No retained run demonstrates this study difference. Original
timestamps, paths and binary descriptions in these derived objects remain
fixture context, not identities of a new execution.

The same projection is applied to the earlier skipped result so the skip
comparison reaches the skip-specific refusal rather than failing at its exit-0
gate. Other controls name the exact refusal for new failures, credential
failure, missing inventory, new partial skips, interruption, wrong platform,
unfired/unassigned controls and unrelated broken checks. JSON member ordering
does not change acceptance of the projected result; both architectures' full
records are checked against their own inventories.

A separate supplied control appends a synthetic `baseline_failed` control for
the changed family text, with corresponding total and baseline-failure counts.
Changing its status to `not_fired` must reach the control-specific refusal.

The study binding test still supplies synthetic Git replies, source archive,
binary canaries and retention-substep flags. The original successful release
run did not request a work archive, so no observed release retention-substep
records exist in that run. The binding test exercises digest checking and
failure propagation; it does not qualify or authorize those synthetic inputs.
No fixture reader opens a stored operational path or starts a binary, container,
credential lookup or model.
