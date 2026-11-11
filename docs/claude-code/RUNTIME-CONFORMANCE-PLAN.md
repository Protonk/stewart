# Claude Code runtime conformance

The gated adapter is implemented and has passed native offline service checks.
The principal approved A–C and implementation with offline controls on
2026-11-10. No real-Claude service conformance run exists, and no additional
Claude launch or resume is authorized. Both earlier probe commissions are closed.

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

## Remaining work

- List every difference this contract makes from the Messages path at the
  manager's surface: front matter, preparation, receipt, status, close and the
  return. Separate those the transport forces from the incidental, and bring
  the incidental ones to the principal with evidence. Share driver cases for
  common behavior between the two runtimes where independence allows.
- Extend the independent offline driver to isolate relay-only disconnect while
  the model remains alive, MCP cancellation through the actual service, valid
  terminal usage checkpoints across placements, and compaction/notice/reminder
  interactions. Current cases exercise relay stopping with owner/model loss and
  usage with missing terminal reports. Publication-gate and event-parser unit
  controls, and the protocol prototype, are separate evidence.
- Provide a Linux execution path for the standalone synthetic runtime suite,
  with the exact gated binary and independent witnesses. `acceptance.sh` checks
  the gated build and markers but does not run this suite; its result cannot
  qualify runtime execution.
- Prepare a concrete bounded commission for real service conformance, with exact
  synthetic materials, model, session allowance, stopping conditions, executable
  and writer pins, selected subscription route and retained witnesses. The
  earlier two-tool probe is not a full-service profile check. Obtain the
  principal's explicit approval before any additional Claude invocation.
  The real full-service check and profile-attestation producer still need
  apparatus; current offline fixtures supply synthetic attestations only.
- Under that commission, exercise the actual auditor tool surface,
  compaction/re-entry, accounting, interruption, submission, delivery and close.
  Verify effective tools, instructions, authentication and access before and
  after compaction, including host and server-managed configuration. Settings
  alone do not establish enforcement.

Use firing controls, differing cases and invariance cases under
[ACCEPTANCE](../../ACCEPTANCE.md#the-real-model-conformance-tier). Bind results to the
actual CLI, effective configuration, model, authentication route and binaries.
Model answer quality is not the gate. API results do not qualify the harness
profile, and native results do not qualify Linux.

## Evidence through review

The current native validation is `.tmp/document-harmonization/host.VxyhfJ`,
with runtime witnesses at `/private/tmp/stewart-doc-runtime.CGwaur/run`:
14 cases, 4,711 checks and 45 controls passed, with no skips. All applicable
[DEVELOPMENT checks](../../development/DEVELOPMENT.md#what-to-run-for-what-you-changed)
passed. The source snapshot stayed unchanged throughout the run.

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

The two probes are not yet registered in the qualification index. Their
results/state files have no UTC run timestamp accepted by the current indexer.
Resolve how to register that known date gap before relying on the index to cover
these selected evaluations; do not manufacture a run timestamp or rewrite their
receipts to fit the index. Keep their original paths and retention purpose above
explicit until that is resolved.

Complete this plan when the selected integration has a reviewed qualification
outcome and failures or unexercised work have explicit dispositions. Keep
enduring behavior in the owning documentation and tests, then delete the plan.
