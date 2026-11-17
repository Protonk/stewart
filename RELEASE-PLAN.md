# Release and work plan

**Current status:** The developer lookback is complete. Its decided changes to
placement endings, exhausted starts and signal gating landed with native checks
only; a container run, scheduled by the principal, must qualify the changed
source. Readiness reassessment resumes next; manager-interface implementation,
endpoint alignment and platform qualification remain ahead. No live packet is active and the
public release is not scheduled by this plan.

This plan owns cross-plan order and first-release obligations. Topic plans own
remaining tasks and decisions. [CONTRACTS](CONTRACTS.md) and
[INTERFACE](docs/INTERFACE.md) own behavior; [ACCEPTANCE](ACCEPTANCE.md) owns the
evidence owed. [README](README.md#status) owns demonstrated product status and
the [qualification index](apparatus/qualified.md) owns retained results.

## Work order

| Order | Remaining work | Owner |
| --- | --- | --- |
| Current | Finish remaining fixture dispositions, coverage reassessment and qualification, starting with Linux qualification of the lookback's changes. | [Readiness follow-up](READINESS-FOLLOW-UP-PLAN.md) |
| After readiness dispositions | Specify and implement shared commissioning rules, the independent CLI additions, optional preparation MCP and fake-provider integration. | [Manager interface](development/MANAGER-INTERFACE-PLAN.md) |
| Alongside manager work, separately commissioned | Extend procedural question-family and runtime trials. A real-service result is not an entry gate for manager MCP or fake-provider boundary acceptance. | The manager plan's subscription testing track |
| Separately scheduled release work | Build endpoint alignment and align the endpoints the release names; complete platform qualification and acceptance-policy review. | [Endpoint alignment](ENDPOINT-ALIGNMENT-PLAN.md) and the requirements below |
| Before the release | Prepare the release documentation and source package. | [Release documentation and source package](#release-documentation-and-source-package) |
| After the first release | Investigate shortening test and suite wall-clock time. | [Test wall-clock](development/TEST-WALL-CLOCK-PLAN.md) |
| Unselected | Broader blinded evaluation and family dogfooding. | [Deferred studies](#deferred-studies) |
| Unselected | The lookback's behavior-preserving refactor candidates and public-form candidates. | [Unselected candidates](#unselected-candidates) |

Use the existing apparatus and retained exact writers; reconcile uncertain
processes or effects before reusing them. Build only the prerequisites needed
for the selected comparison. Endpoint alignment is separate from the bounded
readiness observations. Live starts need concrete approval; container
runs and the public release remain the principal's scheduling decisions.

At the manager transition, enter its specification stage and freeze roles,
diagnostics, MCP and effect-description schemas before dependent implementation.
Arrange independent driver authorship where service and driver changes are both
needed. Give residual work one owner in place; do not create a turnover document.

## Deferred studies

Broader blinded evaluation and family dogfooding remain deferred; the
[family contract](CONTRACTS.md#question-families-and-open-inquiry)
owns their product boundaries. An agent-manager study omitting the question from
returns is only an option after the manager interface is established and the
principal selects it, not a pending task. A future study needs a named uncertainty
and bounded commission. Select its inputs and discriminating comparison from the
qualification index's evaluation records and the interaction findings
(`apparatus/studies/interaction/RESULTS.md` at `77375f1`). Real-model
repetition, effort comparisons and killed-and-continued placements, which the
former conformance matrix required, are such studies now, not release gates.

## Unselected candidates

The developer lookback (2026-11-16 and 17) left these candidates. None is
selected. Behavior-preserving candidates keep every public byte and need only
the usual checks:

- Split the pinned arrangement into common and per-runtime parts. Agent
  arrangements still carry Messages placeholder members, and an archive with
  Messages settings beside an agent arrangement, which Stewart cannot
  produce, panics after `run_started` instead of refusing.
- Type usage, limits and remaining allowances by runtime. Agent limits can
  still reach Messages arithmetic (unreachable today), and adding usage
  across runtimes drops the other runtime's values silently.
- Move placement outcome types out of the Messages provider module, so the
  agent runtime stops depending on Messages abort and placement machinery.
- One notice claim for both runtimes. Their preconditions differ: Messages can
  claim a reminder after `close_requested`, the agent runtime cannot.
  Aligning them needs a small decision.
- One family resolution at preparation with a cross-runtime arrangement byte
  test; pinned and compiled family facts are not compared at run.
- Enforce the Messages request timeout from the pinned arrangement rather than
  an equal constant.
- Pin the agent readable view in a Cargo test, and decide whether a bad API
  limit beside a profile should keep reporting two defects for one key.

Public-form candidates change a recorded or reply form and need the
principal's decision:

- Agent records without Messages placeholders (`provider`, `requests`,
  `attempts`), with a top-level runtime and only agent causes.
- Agent accounting naming its session and accepted checkpoint, with stopping
  outside usage.
- Agent notice identity with a durable transmission observation, so recovery
  could report `sent` rather than `unknown`.
- Agent `tool_result` without transport coordinates; named agent stop causes
  instead of one `protocol_anomaly`; a defined
  `claude-code,fault-injection,sabotage` build.
- Smaller wording and form gaps: sealed advice says "An ordinary close confirms
  where the delivered copy is" when `run` did not deliver; an agent seal on a
  damaged log reports delivery `unknown` where Messages gives `none`; `run`'s
  binding refusal `runtime_profile_invalid` carries no `data.surface`, which
  the contract requires only of `prepare`.

Family-descriptor candidates belong to the manager interface's registry stage.

## First-release requirements

| Requirement | Remaining work |
| --- | --- |
| Linux container qualification | Run the scripted acceptance suite on the release source and binaries, on both architectures with the required controls. |
| Native WSL2 qualification | Package the same binary, driver and fake provider; arrange and review the user's native run. |
| Endpoint alignment | A current [alignment record](ENDPOINT-ALIGNMENT-PLAN.md) for each model the release names, each run under an authorized budget. |
| Release documentation and source package | Define and build the source archive and finish the outside-reader documentation pass ([below](#release-documentation-and-source-package)). |
| Public release gate | Set the binary release schedule with the principal. |

The requirements remain those of ACCEPTANCE while its review is open.

### Coverage and acceptance-policy review

Check driver cases against every ACCEPTANCE claim. Uncovered requirements need a
case or an explicit disposition. Add independent black-box comparisons for
interim/folded/conflicting-length response heads, the retained-payload reserve
boundary and `not_sent` notices; specification text and service-unit checks do
not establish that coverage. The driver also lacks cases for close's `unknown`
seal, delivery and closure effects after a failed publication, the `--verify`
`problem` member and a symbolic link above an item, `receipt_record_failed`
before the acceptance link, a `checked_at` that is not a timestamp, and a null
JSON-RPC error `id` from the binary. Reassess unreached/partly reached conditions and
unclear behavioral promises against the actual cases. Candidate gaps include
C17's secondary logging errors, blind repetition after reply failure and omitted
partial effects; C18's pressure pruning, confusion between retained and delivered bytes, and missing
archives reported clean; and C11's scans presented as snapshot proof. Driver
changes require an implementation-independent author.

Resolve these acceptance-policy questions without silently changing the current
requirements:

- Confirm the platform and alignment gates and coverage scope.
- Decide whether to add Linux Cargo tests. Current Linux suites build the crate
  and run the independent driver; an offline Cargo route would need
  `STEWART_IT_TMP` on ext4, xfs or btrfs.
- Decide toolchain-digest enforcement and native/emulated execution recording.
  Built image digests are the actual toolchain pins; acceptance records image
  inspections by tag but does not enforce equality with the toolchain record.
- Review qualification rules for skips, timing gates and failures across
  platforms. The native protocol tripwire is 200 ms; emulated x86_64 has no
  enforced timing gate. Retiring the absolute tripwire or moving performance
  trends into Linux CI remains a later policy option, not implementation
  scheduled now.
- Decide whether to support running the qualification suites from a Linux
  host; the documented host route uses macOS and Apple `container`, and native
  Linux runs are documented as development iteration only.

### WSL2 package

The package must carry the same qualified release/test binaries, driver and fake
provider. Run with the home on the WSL filesystem and a destination under `/mnt/`;
record Windows/WSL versions, distribution, kernel, architecture and filesystems.
The native timing gate applies. Native x86_64 is unexercised, so its timings must
be measured rather than inferred from Rosetta.

Needs: a package builder, instructions and the user's scheduled run.

### Release documentation and source package

The source archive is the release commit's tracked tree plus `service/vendor`,
with the vendored files' digests from the `step2.sh` run that produced them, and
the qualification record of the shipped binaries. Plans are complete and deleted,
and local working material stays out, before it is cut.

The README covers getting and verifying the binary, the archive filesystem rule
(the archive on the WSL filesystem, never under `/mnt/`) and a first run that
needs no provider key. AGENTS, DEVELOPMENT and the crate guide let an outside
agent find the code, build it from the archive without network access and run
the checks natively on Linux, knowing which checks qualify nothing.

Needs: the archive recipe, and a final outside-reader pass after the manager
interface settles the documentation it changes.

Deferred product scope belongs in CONTRACTS; it is not additional release work.
