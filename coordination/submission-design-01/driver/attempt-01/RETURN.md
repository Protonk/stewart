# Independent process qualification return

2026-10-27. The final frozen disposable prototype passed all **72 selected
cases, 2,512 assertions and 522 helper invocations** in `run-007`. The external
raw-record recount agrees: every helper start has an exit record; all 32 intended
barriers have captured markers and kernel-observed SIGSTOPs; 19 SIGKILL and 13
SIGCONT actions are recorded; no timeout occurred. No driver or helper is left
running by this assignment.

This is local procedural evidence for the commissioned prototype on Apple Silicon
macOS with Python 3.14.9. It is not production custody or harness qualification.
The driver uses only the public process protocol, independent exact byte witnesses
and published storage coordinates. It did not inspect or import Rust source.

## Identity and reproducible command

Source base is `cf7216f50f16041c3b31d9136925dec82e07b6bd` plus root-admitted
dispatch/protocol changes. Root froze the final implementation in
`.scratch/submission-prototype-01/REVIEW-INPUTS-03.json`; its SHA-256 is
`93a64f76a0f9a3f1c6e57c855b5dd9539ee5acec5f3663c15c464de823699a66`.
The manifest supplies exact Rust/module/Cargo/source identities without requiring
the driver to inspect implementation code. Its exact bytes, frozen PROTOCOL and
published README are copied into the final driver evidence.

| Tested item | SHA-256 |
| --- | --- |
| Primary executable | `cacc57df666c1b1eeef85c14a3a17a2a7d679d21bd480358548874062838c0de` |
| Distinct valid writer-control executable | `95efb5a07bfd53f0ae49b3f876a59fd06e48cb6c441bcb9b086307a5f74a7671` |
| Executed driver source | `1f4a75b878525877ca80abd4fbb585e4bd74db2fbe4e891033518ceb1bbf1bfc` |

Executed from `/Users/raccoon/Desktop/Experiments/stewart`:

```sh
/opt/homebrew/bin/python3.14 -I -B coordination/submission-design-01/driver/attempt-01/run_driver.py --driver coordination/submission-design-01/driver/attempt-01/driver.py --binary .scratch/submission-prototype-01/review-inputs-03/stewart-submission-prototype --other-binary .scratch/submission-prototype-01/review-inputs-03/stewart-submission-writer-control --evidence .scratch/submission-prototype-01/driver/run-007
```

A repeat requires a new evidence directory. `run-007.launch/COMMAND.json` records
the exact inner interpreter/argv/cwd; START/EXIT identify the driver PID and outcome.
Each helper has its own command, cwd, PID, exact stdin, streamed stdout/stderr and
exit. Both executables and the executed driver source are copied into the run.

## Evidence and actual counts

All run paths below are beneath `.scratch/submission-prototype-01/driver/`.
Each has its own RESULT, case results/assertions, original input witnesses and
snapshots. Its `.launch` sibling holds live driver streams outside its own record.
`independent-counts-final.json` recounts the raw assertion/command/signal files.
Counts are per invocation; repeated selectors are not new distinct experiments.

| Run | Selected | Passed | Failed | Assertions | Helper invocations | Disposition |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| run-001 | 5 | 5 | 0 | 242 | 52 | Initial interface/driver diagnostic controls. |
| run-002 | 59 | 58 | 1 | 1,723 | 425 | Preserved implementation failure: inspect accepted an unknown field. |
| run-003 | 1 | 1 | 0 | 43 | 6 | Stronger observed-lock-contention control on initial binary. |
| run-004 | 8 | 8 | 0 | 411 | 61 | Intermediate fixes, publication loss, writer and recovery probes. |
| run-005 | 70 | 42 | 28 | 1,639 | 382 | 27 driver observer failures; one real preparation-dependency failure. |
| run-006 | 32 | 32 | 0 | 1,204 | 239 | Corrected observer, all barrier cases on the previous frozen candidate. |
| **run-007** | **72** | **72** | **0** | **2,512** | **522** | **Final full population on frozen final executable.** |

The final retained unrelated working/store tree is
`/private/tmp/stewart-submission-driver-t26jqryz`. Earlier trees remain:
`f4uae7wa`, `owv6k9ti`, `s8u1si5r`, `l_wg54n6`, `ugsvkzk2`, and `0f81obuh`, each
with the same `/private/tmp/stewart-submission-driver-` prefix. START and final
inventory records bind these locations; do not remove them during review.

## What the comparisons distinguish

| Concern | Firing, differing and invariance evidence |
| --- | --- |
| Exact material and selection identity | Fresh processes read binary, Unicode and empty raw witnesses after source rename. Equal bytes and equal names produce distinct IDs. Equal-byte replacement changes version/revision; unaffected elements retain their identities and bytes. |
| Bounds and control input | Exact 1 MiB element, 32 elements, 8 MiB active bytes and 64 KiB control input succeed; isolated one-over cases refuse without publishing. Nested and escaped duplicates require duplicate_key diagnostics. Unknown fields across every operation refuse without store changes. |
| Preparation and finality | Ordered manifest matches held selection and commission. Default/false dry runs change no store bytes. Explicit submission seals the selection; identical replay recovers one outcome, different preparation and later edits refuse. Stale/forged/cross-audit handles and damaged selected material remain diagnosed. |
| Real interruption | Each marker binds the caller-known request and planned commit. The parent observes actual SIGSTOP, independently snapshots publication presence, and reads the request-scoped attempt.record_stage to distinguish payload-only from complete commit stage. SIGCONT controls complete; SIGKILL before/after publication exposes complete old/new selections. Raw bytes and unchanged elements remain independent witnesses. |
| Recovery and contention | Same request/handle resolves or completes its recorded work after source loss. Unplanned matching bytes are not adopted. Pending work does not block an independent edit; stale resume refuses and explicit cancellation preserves partials. Completed busy replies occur while the holder is still stopped. Edit/submit both orderings and competing replacements cannot publish incompatible winners. |
| Dependency and corruption scope | Relevant malformed attempts refuse; unrelated malformed attempts leave current reads/new edits available. Missing acknowledged publications stay integrity errors. Current/stale unsubmitted preparation damage leaves ordinary answer reads/edits available, while its own operations diagnose damage. A submitted result validates its chosen issuance. Original corrupted/missing bytes are independently retained and never repaired. |
| Writer identity | A distinct valid binary may perform documented verified reads and resolve. Mutations refuse writer_mismatch without changing store bytes; a byte-identical copied original writer still mutates. |

## Failure dispositions

`run-002/control_unknown_field` demonstrated the implementation's acceptance of
`{"op":"inspect","surprise":true}`. The implementation added authoritative
field validation; final direct and all-operation controls pass.

In `run-005`, the driver incorrectly inferred a `-commit` staging suffix. The
27 affected cases stopped at that observer assertion and killed their retained
children as recorded cleanup of the failed test; those kills are not successful
planned interruption comparisons. The corrected driver follows the published
request-scoped attempt's `record_stage`, validates the complete bound commit bytes,
and retains both failed and passing evidence. `run-006` and final `run-007` pass.

The remaining `run-005/corrupt_preparation_issuance` failure was an implementation
dependency defect, independently confirmed and resolved by root/reviewer as R4.
The driver's original inspect-success expectation remained. A tentative suggestion
that this expectation was obsolete was withdrawn before any test relaxation.
Root clarified the protocol; the implementation separated state and preparation
acknowledgment validation. The original case and narrow stale-unsubmitted versus
chosen-submitted controls all pass in the final run. Reviewer/implementer findings
about missing acknowledgments and unrelated attempts retain their own attribution;
this driver independently checks the final prescribed behavior.

## Limits and handback

These process comparisons do not establish arbitrary partial-write/storage-failure
behavior, power-loss/device durability, host-wide confinement, hostile ancestor
replacement race safety, other platforms, manager delivery/notification, auditor
termination, physical reclamation, retirement, close or full human handback.
Final edit refusal does not prove delivery or stopped descendants. Source-loss
tests rename fixtures and retain their witnesses; no disposal is qualified.
This driver is not the Python installed-wheel checker; frozen Python/C were not
changed or qualified by these runs. No production feature is shipped by this return.

All seven runs, failures, partials, old payloads, witnesses and external trees remain.
No deletion, pruning, Git mutation, product custody operation, network request or
nested delegation was performed. Driver work is complete; root owns integration,
review disposition and the next product decision. No further execution is pending.
