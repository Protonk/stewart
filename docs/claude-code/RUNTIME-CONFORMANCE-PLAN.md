# Claude Code runtime conformance

The gated adapter is implemented and aligned with the Messages path at the
manager's surface, including ordered tool-call queuing. Native offline checks
against a synthetic harness pass. No real-Claude service run exists. No Claude
launch or resume is authorized: both earlier probe commissions are closed,
and the real-service run below needs its own commission.

## Decided scope

The [development runtime contract](CONTRACT.md) owns the selected
observation, placement-limit, startup and credential boundaries. The
[runtime reference](RUNTIME-REFERENCE.md) owns technical evidence
and remaining limits. Packaged releases exclude the adapter; the published
source keeps it behind the default-off feature. Its purpose is to be the main
means of exercising the manager's interface, so keep it in line with the
Messages path wherever the transport allows. Linux is in scope: a source
builder there is an intended user.

Preserve the [question-family meanings](../../CONTRACTS.md#question-families-and-open-inquiry),
common custody/attribution contract and
[evidence and judgment boundary](../../CONTRACTS.md#principles-and-scope). Family choice
never grants execution. Runtime telemetry does not establish the auditor's
understanding or intellectual completeness. Human and other runtime adapters
remain future work.

## Next steps, in order

Take these in order. Each step that changes the contract or the service is
written by one author, and its driver cases by another who has not read the
implementation.

1. **Qualify the Linux runtime path.** The container suite now includes the
   standalone runtime driver against both architectures' gated binaries, a
   different-digest writer control, exported independent witnesses and runtime
   results in the qualification record. Native verification is complete. Have
   the principal run the container suite on the committed source, then review
   and extract both architectures' results. Linux runtime execution remains
   unqualified until that run.
2. **Build the real-service check and propose its commission.** Two pieces of
   apparatus are missing: a producer for a profile's installation and check
   attestation, and a full-service check that drives the actual auditor tool
   set through the real harness with independent witnesses. Current fixtures
   supply synthetic attestations only, and the two-tool probe is not a
   full-service check. Then write a concrete bounded commission: exact
   synthetic materials, model, session allowance, stopping conditions,
   executable and surface pins, the subscription route with paid extra usage
   disabled, and the witnesses retained. Rehearse it offline against the
   synthetic harness. Bring it to the principal; preparing it authorizes
   nothing.
3. **Run the real-service check under that commission.** Exercise the actual
   tool surface, compaction and re-entry, accounting, interruption,
   submission, delivery and close. Verify effective tools, instructions,
   authentication and access before and after compaction, including host and
   server-managed configuration; settings alone do not establish enforcement.
   The commission names these as explicit observations, each currently unknown
   for the real harness:
   - what usage a submitting placement reports. The runtime stops the harness
     after a confirmed submission; in synthetic runs that leaves the final
     interval unknown on every sealed audit, while a turn that ends with a
     result is reported;
   - how the harness issues several tool calls of one model response;
   - where a post-compaction notice is delivered, and whether startup can be
     validated before the first question reaches the provider;
   - whether the turn cap and per-response output request are enforced.

Use firing controls, differing cases and invariance cases under
[ACCEPTANCE](../../ACCEPTANCE.md#the-real-model-conformance-tier). Bind results to the
actual CLI, effective configuration, model, authentication route and binaries.
Model answer quality is not the gate. API results do not qualify the harness
profile, and native results do not qualify Linux.

## Desirable work

None of this blocks the steps above. Do it when it fits.

- Share driver cases for behavior common to both runtimes where independence
  allows. The two drivers now cover custody, submission, delivery and close
  separately, so a common behavior is specified once and checked twice by
  different code.
- Write the offline cases still missing: refusal of a second relay connection
  in a live placement (the stop after relay loss now ends the attempt first), a
  hook call after the placement has stopped admitting calls, and the
  near-limit notice. `run`'s re-verification of a pinned surface has unit
  coverage only, because one binary cannot hold an arrangement that pins
  another surface.

## Housekeeping

- Register the two native probes in the qualification index. Their result and
  state files carry no UTC run timestamp the indexer accepts. Resolve how to
  register that known gap; do not manufacture a timestamp or rewrite their
  receipts to fit. Until then their paths and retention purpose stay listed
  below.
- Once the principal has reviewed the evidence listed below, apply the
  [retention rules](../../development/DEVELOPMENT.md#evidence-and-retention):
  keep the current results and selected originals, and release the reproducible
  working trees and superseded runs.

## Evidence through review

The queued-call and Linux suite changes passed host verification in
`.tmp/runtime-queue/host.yTveQl/`, with runtime witnesses at
`/private/tmp/stewart-queue-runtime.LGe6um/run`: all three Cargo configurations,
apparatus checks and optimized marker checks passed. The runtime suite passed
23 cases, 9,702 checks and 68 controls, with no skips or unselected cases.
Its self-test passed 158 checks; the qualification self-test passed 97 controls.
The source snapshot stayed unchanged and all three copied binary digests match
the runtime's environment record. No real harness was invoked.

The cancellation comparison witnessed a refused sibling without an effect,
and cancellation won all six further races. Its traffic does not independently
identify the instant a call entered the internal queue; deterministic unit
controls cover waiting-state cancellation and queue bounds. The host run
resolves the earlier sandbox loopback failures and skips retained beside it in
`.tmp/runtime-queue/`. Keep the host outputs, binaries and independent witnesses
through review of the Linux run.

The latest completed native validation of the earlier service baseline is `.tmp/alignment/host.x1DmST`,
with runtime witnesses at `/private/tmp/stewart-align-runtime.SbCg7Q/run`: all
applicable [DEVELOPMENT checks](../../development/DEVELOPMENT.md#what-to-run-for-what-you-changed)
passed with no skips and the source snapshot stayed unchanged. The corresponding run
of the independent driver against those same binaries is
`.tmp/driver-gaps/host.QdjlTD`, with witnesses at
`/private/tmp/stewart-gaps-runtime.sDdJDu/run`: 23 cases, 9,690 checks and 68
controls passed, with no skips. It adds the hook helper, a selected effort,
cancellation, relay loss, usage across two placements and compaction; its notes
record that cancellation won all six races, each answered `placement_stopped`.
Earlier validations are `.tmp/surface-binding/host.24wFiF` (first surface-bound
form, witnesses at `/private/tmp/stewart-surface-runtime.QTlDKw/run`) and
`.tmp/document-harmonization/host.VxyhfJ` (writer-bound form, witnesses at
`/private/tmp/stewart-doc-runtime.CGwaur/run`).

Keep `.tmp/document-harmonization/` through review of the later socket EOF
failure and its fix. `host.PMinwd` retains the failed native run. The paired
socket comparisons distinguish a blocked read after peer write-half shutdown
from an empty channel or missing EOF; they do not qualify Linux behavior.
The MCP reader's bounded idle-read retries passed the strengthened regression
and the native validation above.

Keep `.tmp/claude-code-adapter*`, the earlier host runs and their external
witnesses through this implementation review; each host directory's
`runtime-work.txt` locates its witness. The original socket-mode and driver
parser failures remain intact. The baseline in `4e7478a` has its own
`host.PZGw1h` results and `/private/tmp/stewart-cc-native.DyFPFv/run` witnesses;
those records are not rebound to the current binary. Also keep
`/private/tmp/stewart-claude-driver-checks.AhLaUX`, `/private/tmp/scc5`,
`/private/tmp/scc6`, `.tmp/claude-code-contract/` and `.tmp/claude-code-probe/`
through review of their offline controls and observer comparisons.

The original `.scratch/claude-code-probe-01` and
`.scratch/claude-code-probe-02` captures remain unchanged for review of the
selected launch arrangement. Each run's frozen inputs own what executed;
previous runs confer no new launch authority. Apply the normal
[evidence retention rules](../../development/DEVELOPMENT.md#evidence-and-retention)
after review rather than retaining reproducible working trees indefinitely.

Complete this plan when the selected integration has a reviewed qualification
outcome and failures or unexercised work have explicit dispositions. Keep
enduring behavior in the owning documentation and tests, then delete the plan.
