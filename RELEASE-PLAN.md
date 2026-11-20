# Release and work plan

The manager interface's scripted stages are complete and qualified. The next
step is the coverage and acceptance-policy review, then the release
documentation and source package.

This plan owns cross-plan order and first-release obligations. Topic plans own
remaining tasks and decisions. [CONTRACTS](CONTRACTS.md) and
[INTERFACE](docs/INTERFACE.md) own behavior; [ACCEPTANCE](ACCEPTANCE.md) owns the
evidence owed. [README](README.md#status) owns demonstrated product status and
the [qualification index](apparatus/qualified.md) owns retained results.

## Work order

| Order | Remaining work | Owner |
| --- | --- | --- |
| Current | Review driver coverage against every acceptance claim, then prepare the release documentation and source package. | [The requirements below](#coverage-and-acceptance-policy-review) |
| Delegated campaign | Runtime trials: two live waves on interruption, continuation and close, with the real harness and the Messages route, under one commission envelope, with implementation between and after them. A real-service result is not an entry gate for the release. | [Runtime trials](RUNTIME-TRIALS-PLAN.md) |
| Separate release work | Specify and build endpoint alignment offline; align the endpoints the release names under a commission. | [Endpoint alignment](ENDPOINT-ALIGNMENT-PLAN.md) and the requirements below |
| Before the release | Prepare the release documentation and source package. | [Release documentation and source package](#release-documentation-and-source-package) |
| After the first release | Investigate shortening test and suite wall-clock time. | [Test wall-clock](development/TEST-WALL-CLOCK-PLAN.md) |
| Unselected | Broader blinded evaluation and family dogfooding. | [Deferred studies](#deferred-studies) |
| Unselected | The lookback's behavior-preserving refactor candidates and public-form candidates. | [Unselected candidates](#unselected-candidates) |

Use the existing apparatus and retained exact writers; reconcile uncertain
processes or effects before reusing them. Build only the prerequisites needed
for the selected comparison. Endpoint alignment is separate from the bounded
readiness observations. Live starts require a bounded commission.

Use the specified manager schemas for dependent implementation.
Arrange independent driver authorship where service and driver changes are both
needed. Give residual work one owner in place; do not create a turnover document.

## Deferred studies

Broader blinded evaluation and family dogfooding remain deferred; the
[family contract](CONTRACTS.md#question-families-and-open-inquiry)
owns their product boundaries. An agent-manager study omitting the question from
returns remains an option after the manager interface is established. A future
study needs a named uncertainty and bounded commission. Select its inputs
and discriminating comparison from the qualification index's evaluation
records and the interaction findings
(`apparatus/studies/interaction/RESULTS.md` at `77375f1`).

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

The following candidates affect recorded forms, replies or build configurations.
If selected, assess them against custody, truthful reporting and what
participants can express. Apply the [version rules](CONTRACTS.md#versions-and-legacy-obligations)
when a form changes.

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
| Linux container qualification | Qualify the binaries to be shipped against the [scripted acceptance claims](ACCEPTANCE.md#the-scripted-tier). |
| Endpoint alignment | A current [alignment record](ENDPOINT-ALIGNMENT-PLAN.md) for each model the release names, each run under an authorized budget. |
| Release documentation and source package | Define and build the source archive and finish the outside-reader documentation pass ([below](#release-documentation-and-source-package)). |
| Public release gate | The maintainer decides when to publish the qualified binaries. |

The requirements remain those of ACCEPTANCE while its review is open.

### Coverage and acceptance-policy review

Every sabotage item in ACCEPTANCE now has a C.2 control or a disposition in
INTERFACE Appendix C, and the driver gaps found in review have cases. The
release and runtime suites run every case on both Linux architectures without
skips; native runs skip only Linux-only expectations.

- [ ] Settle the endpoint evidence the release names through
  [endpoint alignment](ENDPOINT-ALIGNMENT-PLAN.md).

Accepted limitations: the readiness reassessment's surviving mutants were
equivalent; the runtime's unit-only limits are stated in its
[contract](docs/claude-code/CONTRACT.md#evidence-owed). Two tests each failed
once under heavy machine load and passed on rerun (the native held-lock
delivery test and the credential-descriptor deadline, now a driver case);
rerun a timing-sensitive failure alone before acting on it.

### Release documentation and source package

The source archive is the release commit's tracked tree plus `service/vendor`,
with the vendored files' digests from the `step2.sh` run that produced them, and
the qualification record of the shipped binaries. Plans are complete and deleted,
and local working material stays out, before it is cut.

The README covers getting and verifying the binary, the supported archive filesystems and a first run that
needs no provider key. AGENTS, DEVELOPMENT and the crate guide let an outside
agent find the code, build it from the archive without network access and run
the checks natively on Linux, knowing which checks qualify nothing.

Users verify a download against a `SHA256SUMS` file covering both binaries,
signed by the maintainer with `ssh-keygen -Y sign -n file` and checked with
`ssh-keygen -Y verify` against an `allowed_signers` file in the repository. This
needs only OpenSSH. The maintainer signs; the release build is reproducible
(`step2.sh` builds twice and compares), so a reader can also rebuild from the
source archive and compare digests. Qualification stays on the development
Mac's container suites; supporting other development hosts is not a goal.

Needs: the archive recipe, the signing procedure in the README, and a final
outside-reader pass.

Deferred product scope belongs in CONTRACTS; it is not additional release work.
