# Operating routes — first-wave preparation

Prepared 2026-10-26 by `/root/inquiry_routes`. Complete as preparation;
enforcement remains unproved. Source commit:
`250d494262374007302ea9765399cb27dce90a34`. Shared document references mean
the snapshots pinned by `.scratch/successor-inquiry-01/inputs-01.json`.

## Conclusion

No demonstrated route yet satisfies the combined successor obligations.
Compare the scoped local Claude Code route with a whole-auditor container
route, considering native Claude background supervision as a specific control
alternative. Do not select a controller from documentation alone.

Human-run and agent-run launch should invoke the same pre-bound request. They
differ in who conveys the command and receives its immediate reply, not in
where stop authority resides. A human author submitting an answer without
agent helpers is a separate case.

An audit-control adapter would bind one commission to one auditor run, retain
its stop handle, receive the finite return and expose custody recovery. This
is additional responsibility. It need not provide program-attempt APIs,
manager byte review, release, rerun or routine steering. No adapter, service,
runtime implementation or product command is selected by this report.

**User steering:** no Claude session may be launched without first asking the
user. Usage is at 99% today; hitting the limit could confound a comparison.
This wave launches none. Every future Claude probe needs explicit permission
and known usage headroom. Limit-exhaustion work is deferred to a separately
commissioned later test. A tool's approval classifier is not user permission.

## Evidence classes

**Pinned source reading.** `launch_profile.py` implements a renderer:
`render_command` produces a subshell, directory change, scoped argv and optional
`HARNESS-EXIT.txt` trailer. It retains exit/time, not an independently surviving
run handle. Launch-style metadata does not establish who executed it.
`auditor_scope.py:claude_settings` constructs separate file-tool and shell
restrictions with private-root exclusions, runtime/common-Git grants and an
empty shell-network allowlist. `scoped_argv` limits configuration and tools.
This still exposes a broader Git store than selected-history grants require,
and does not restrict manager access. Construction is not enforcement evidence.

**Earlier findings, not rerun.** `CUSTODIAL-CORE-FINDINGS.md`, B/F, reports
selected-history copying, an alternates view exposing unselected objects and
the same-owner limit of ordinary read-only permissions. Its history probe was
Git-only. `GIT-ENVIRONMENT-NEEDS.md` describes baseline filters, substitutions,
shallow/partial and filename hazards. These motivate comparisons, not a newly
qualified route.

**Public documentation.** [SOURCES.md](SOURCES.md) retains exact official
URLs, sections, retrieval date and bounded notes. Rolling docs retrieved
2026-10-26 do not establish the installed CLI/OS version. Current native
supervisor restart/carryover behavior raises a concrete stop question (S1).
`CLAUDE_CODE_DISABLE_BG_EXIT_HANDOFF=1` is a probe variable, not proof against
automatic restart or every descendant. Current documented narrower-path read
precedence (S2) differs from the frozen source's broader-deny account of its
qualification. This is documentary divergence, not established enforcement
drift. Preserve the historical account and pin the actual next tested version.

**Fresh behavioral evidence:** none. Zero pytest nodes, zero behavioral
comparisons, no live audits, network experiments, services or installations.
Public web reads are capability research. No repository content was uploaded.

## Route comparison

Each candidate receives the original commission, selected subject files when
needed, independently copied selected history when granted, pinned submodule
copies, explicit tool/network limits and a return identity. History-only work
omits the subject tree. Granting a selected view must not expose a common Git
directory, alternates or the whole shared backing store.

| Route | Concrete components and inputs | Grant and manager boundary | Control, loss and delivery | Status/setup cost |
| --- | --- | --- | --- | --- |
| A. Scoped foreground CLI and human relay | Human or agent executes the same pinned `claude` argv in the selected tree. Existing renderer is the construction baseline. Add a request reference known before launch and independent return acquisition if developed. | File-tool and shell grants need qualification. Separate manager-harness or OS restrictions are necessary; same-login placement is insufficient. | Today no controller beyond launcher/terminal is bound. Exit trailer does not establish descendant termination. Manual relay can convey a captured return; launcher/reply loss remains unresolved. | Cheapest comparison baseline, **incomplete for successor graceless close**. Later real-Claude trial needs permission, quota headroom and credentials. |
| B. Native background job plus narrow custodian | Trusted adapter submits `claude --bg` under an isolated audit identity/configuration and records the native job/run binding. Same request interface for human and agent. Native supervisor is documented machinery (S1/S3). | Selected grants still needed. Manager sees request/stop/result projections, not raw job storage, attach, transcripts, prompt injection or restart authority. Enforcement owner remains to be selected. | Native stop plus independent activity witness; adapter must survive a lost launch reply. Restart/carryover semantics need comparison. Native job removal must not become Stewart disposal authority. | Medium setup if deployed flags compose as needed; unverified. Default lifecycle is not yet acceptable. Additional identity, adapter and custody required. |
| C. One Linux container per auditor | Custodian creates a pinned image with selected mounts/copies, isolated scratch, explicit provider/network route and `claude -p`. Persist request/planned identity before create; bind engine ID before start. Detached execution with restart disabled (S5/S7). | Whole-process boundary; no engine socket, broad host mount, host credentials or writable cgroup control in guest. Manager separately denied raw engine/live volumes. Custodian owns immutable input views and custody. | Custodian stops the named instance, verifies the bound process subtree and accounts for outstanding custody. Host cgroup evidence is a candidate witness (S8). Captured result remains outside guest storage. | Strongest combined candidate, **unqualified**. Needs Linux host/VM, engine, pinned toolchain image, credentials, adapter and custody store. Higher memory/disk/setup; native macOS investigations may be unavailable. |

Route C is specific about required machinery, not an installation plan. This
wave did not inspect whether an engine, suitable VM, delegated cgroup or
custodian identity exists. Docker's stop description concerns the main process
signal (S7); it is not the full acceptance witness. The trial must observe the
bound domain and deny escape routes. A dedicated VM could enlarge isolation,
but no exact hypervisor control endpoint is selected: it is not a ready route.
The Agent SDK could replace adapter subprocess plumbing (S10); interruption
alone does not supply durable control, descendant termination or custody.

## Cross-cutting requirements

**Selected, stable and useful inputs.** Read-only mounting does not prevent a
host writer changing underlying bytes (S6). Use custodian-owned copies or prove
another stability mechanism; do not let later manager edits rewrite the
commission. Keep immutable selected inputs distinct from writable scratch.
Test Git-aware builds expecting `.git` separately from history inspection.
The earlier history-copy finding supports a starting candidate, not automatic
adoption: verify exact object membership, absent unrelated/dangling/replacement
objects, incomplete-history limits, raw-blob/name behavior and useful tools.
A history query service is unnecessary for the first comparison.

**Manager isolation.** An unrestricted same-account shell or engine interface
can reopen live material; auditor containment alone does not restrict the
manager (S9). A manager agent could receive a narrow authenticated API while
its own tools deny custodian storage/control. Test that restriction separately,
including alternate tools and newly created private locations. Whether the
human principal's administrator powers are outside the operational manager
role is a policy choice. No protection from that administrator is promised.

**Bound execution and stop.** Bind the actual boundary, lifetime and trusted
control owner before reporting launch success. A PID alone omits descendants
and can be reused. The Linux candidate binds a host-owned cgroup/container from
before execution, prevents migration outside it and verifies emptiness after
stop. Silence, an answer, a signal request and parent exit are insufficient.
External tool services need a separate effects/termination account: local
process death cannot undo committed remote effects. Such services are excluded
from an initial guarantee unless separately admitted. A mere process-group
wrapper is incomplete until detached children and restart are accounted for.

**Submission and custody.** A finite stream received into exclusive storage or
a narrow complete-attempt submission adapter can be a return route. The latter
adds a real auditor channel and reopens the frozen no-pre-collection-channel
assumption. CLI JSON/schema output is not a Stewart receipt, complete-attempt
custody promise or stop witness. W02 still decides drafts, rejected attempts,
finality and early-close partial work. Until contracts change, preserve
obtainable partial work through a supported path or retain the affected
environment with the exact missing stop/capture action. A schema error cannot
silently make drafts disposable.

**Retirement and holds.** Keep captured return, finite original-question
context, receipt/submission identity and qualified independent reader outside
the working environment. Equal text does not identify a submission. Finite
holds and another audit's live use protect their required backing; copying
does not release a hold. Retiring scratch, completing delivery and closing
custody remain separate. This is W05/W10 work, not general workspace management.

## Delivery and unavailable endpoints

| Arrangement | What it can establish | Required or missing boundary |
| --- | --- | --- |
| Synchronous result | Attached caller receives identified answer/reference. | Persist it before reply; lost reply retrieves the same result without another investigation. |
| Named human relay | Person conveys a selected captured return and reports that act. | Record actual relay/receipt separately. Person owns manual re-entry. Launching Claude does not make the person the answer's author. |
| Automatic manager-agent resumption | Nothing qualified here. | **No actual receiving endpoint identified.** Development collaboration tools are not a product callback contract. Select endpoint, authorization and retry owner before promising delivery. |
| Native terminal notification | S1 describes notification under its UI conditions. | Does not establish manager-agent resumption, acquisition or receipt. |
| Human author handback | Existing contract supports helper-independent report return. | Typed successor channel must offer a manual equivalent or explicitly revise that accommodation. |

Cloud/Remote Control is not ready for this comparison: no selected-upload
boundary, receiving endpoint, restricted manager role or stop qualification
was identified. No service was created or contacted through an authenticated
harness. Reading private job files, editing state or selecting the latest
session is not a supported substitute.

Availability with failed notification remains availability. Delivery recovery
concerns that same captured result; stop recovery concerns that same run.
Neither grants investigation. If the recorded control endpoint cannot be
reached, close remains unfinished and keeps the affected environment. The
supported next action must name its custodian/operator and exact control or
disposition operation, not tell the manager to stop an auditor somehow.

## Bounded discriminating probes — not executed

Every probe needs a later execution commission. **Ask the user before any
Claude session; establish usage headroom first.** No intentional quota
exhaustion in these probes. Use synthetic material, fixed versions, a finite
manifest and externally bounded process/time/resource limits. Keep an
independent witness outside disposal through review. Witness rescue is not
product retrieval. Start without external tool services or general network
grants; real Claude still needs its authorized provider connection. OS-only
fixtures cannot establish actual Claude enforcement.

### P1 — First: useful grants without private-location inventory

Pin current Mac/CLI version, effective managed settings and argv. Use one
selected file, writable scratch, a two-branch Git fixture with only one branch
in the history view, and an unselected sibling. Attempt actual reads/writes
through file tools and shell children. Include an alternate path/symlink,
overlapping broad deny/narrow allow, and a private sibling created after launch.

- **Firing control:** deliberately grant a synthetic sibling and demonstrate
  nonce read and allowed write through both routes.
- **Difference:** omit that grant without listing private siblings; selected
  access remains useful, unselected reads/effects fail, immutable inputs stay
  unchanged. Observe bytes/effects, not auditor prose.
- **Invariance:** create another unselected sibling after launch; both remain
  inaccessible while selected history/file operations still work.
- **Witness:** observer-owned nonce map, identities and captured tool outcomes.
- **Host/permissions/cost:** compatible pinned Claude on Mac, permission and
  quota headroom; no install presumed. Linux repetition is a separate case.
- **Stopping condition:** missing control, leak or unusable selected access
  rejects admission and preserves evidence.

P1 is the cheapest first discriminator before building durable control. It
does not decide manager restriction or complete graceless close.

### P2 — End bound activity after launcher loss

Use a finite foreground writer, signal-ignoring child, child changing process
session/group and bounded background tool. Emit numbered heartbeats to an
observer-owned append endpoint; independently observe process membership.

- **Firing control:** parent-only termination must leave a detectable child in
  the intentionally weak fixture. Otherwise it does not test descendant stop.
- **Difference:** native stop in the exact admitted mode versus C's whole-domain
  stop. Compare exit-handoff switching separately from crash/restart so a
  combined change is not falsely credited to one flag.
  Keep foreground `claude -p` and native `claude --bg` as distinct cases:
  the former tests launcher/parent loss and OS-domain stop; the latter tests
  `claude stop <id>`, supervisor crash/restart and carryover. The background
  switch is not presumed to affect foreground tools or prove whole-tree stop.
- **Invariance:** unrelated workload/witness survives. Human and agent launch
  clients lose their reply or exit; the same run remains controllable without
  another investigation.
- **Witness:** timestamped process/domain identity, heartbeat sequence and
  stop/result records outside disposal; observe through configured restart
  window and controller reconnect. Distinguish surviving and new processes.
- **Host/permissions/cost:** isolated native background service; or Linux
  engine/cgroup-v2 with verified kill support and delegation before spawning.
  Authority covers only test-owned processes. No test setup is assumed present.
- **Stopping condition:** missing domain identity, surviving/renewed activity,
  unobservable descendants or spillover rejects the route. Preserve environment;
  named test operator uses the preassigned containment/cleanup path.

### P3 — Manager restriction and result recovery

Use synthetic custodian/manager identities, a request known before dispatch,
finite original-question context and finite return. First test no-LLM transport;
then ask permission for the smallest real-Claude repeat.

- **Firing control:** custodian can access live fixture; unrestricted control
  client proves live-read/injection targets exist; restricted manager can
  retrieve the completed result.
- **Difference:** manager cannot read/edit live material, raw transcripts or
  engine controls, inject prompts, widen grants or restart; allowed stop and
  result retrieval work. Drop reply after return commit and after create-before-
  start; recovering that request must not launch a second run.
- **Invariance:** return identity/bytes and original question survive manager
  source edits, launcher loss and retirement. Another audit's finite held/shared
  selection remains intact.
- **Witness:** independent request/effect/output membership and delivery records.
  Try ordinary retrieval before consulting witness. Availability, notification
  attempt and receipt are distinct observations.
- **Host/permissions/cost:** approved prototype and identities. No external
  notification is sent. Real resumption comparison is unavailable until a
  concrete endpoint and message authority are commissioned.
- **Stopping condition:** private-state repair, silent second run, unrelated
  output adoption, premature disposal or witness-only recovery rejects route.

After W02 policy selection, add substantial staged fields with an invalid
discriminator; complete-attempt versus final-call-only preservation; corrected
discriminator control; later-setter invariance; failed custody write; admission
with lost acknowledgment; early close before submission. Do not presume drafts
disposable before that decision.

## Decisions and remaining work

User choices still needed: manager-role/threat scope; acceptable custodian
component; supported host/tool classes; actual delivery endpoint or manual
relay limitation; W02 custody/disposability terms. Network grants, installing
services, automatic investigative continuation and a new auditor channel are
not authorized by this report.

Recommend P1, then P2 for at most two viable control candidates, then P3 before
automatic delivery/retirement promises. Defer cloud/full-VM routes unless a
named need or failed comparison warrants them. Coordinator next reviews this
account with the other first-wave results and seeks policy/experimental
authorization. No runtime/bundled bytes changed, contracts revised or material
removed. Saved source/output checks accompany [RETURN.md](RETURN.md).
