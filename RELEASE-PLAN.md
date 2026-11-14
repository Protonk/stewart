# Release and work plan

This plan owns work order and the remaining first-release work. Individual plans
own their task's decisions and execution details. Product behavior is specified
in [CONTRACTS.md](CONTRACTS.md) and [docs/INTERFACE.md](docs/INTERFACE.md);
[ACCEPTANCE.md](ACCEPTANCE.md) defines the evidence owed.

**Current state:** readiness stage 1 and L0, M1, M2, C1–C4 are reviewed; M3
preparation is next, followed by the remaining comparisons, repairs and
reassessment. M3, M4 and C5 have no live-start authority. Manager-interface
implementation, full Messages model conformance, native WSL2 qualification and
the public release remain outstanding.

## Work order

| Stage | Work | Working document |
| --- | --- | --- |
| Readiness follow-up, before the stages below | Correct what the readiness review found that can be corrected now, run the live checks it designs as the principal approves each, reassess, and pass what remains to the plans below as notes | [READINESS-FOLLOW-UP-PLAN.md](READINESS-FOLLOW-UP-PLAN.md) |
| Current manager work | Specify shared commissioning rules, complete the independent CLI, implement optional preparation MCP, and demonstrate the interface with fake-provider integration | [Integrated manager-interface plan](development/MANAGER-INTERFACE-PLAN.md) |
| Alongside manager work, separately bounded | Prepare source-only runtime comparisons and question-family trials; live starts require the principal's approval and their own verified apparatus/profile prerequisites | The integrated plan owns this testing track; a real-service outcome is not a prerequisite for manager MCP or fake-provider boundary acceptance |
| Separately scheduled release work | Complete Messages API conformance, platform qualification and acceptance review | [MESSAGES-API-CONFORMANCE-PLAN.md](MESSAGES-API-CONFORMANCE-PLAN.md) and the release requirements below |
| Unselected | Broader auditor studies, blinded evaluation and question-family dogfooding beyond the integrated procedural trials | [Deferred studies](#deferred-studies) |

The integrated plan subsumes the former manager-alignment and runtime-conformance
plans, including their remaining tasks and evidence-review obligations. It owns
the local implementation sequence and the shared manager/type test matrix.
The separate Messages API plan retains the full release-model gate; neither
subscription trials nor fake-provider acceptance substitute for that gate.
Planning and previous model placements confer no execution or spending authority.

The return-context decision needs no further presentation tuning or reader
comparison before implementation. No additional reading interface or return
context is selected here.

## Entry to manager-interface work

**Assessment: the specification stage can start once the
[readiness follow-up](READINESS-FOLLOW-UP-PLAN.md) has passed on what it does
not fix.** The readiness plan owns verification of its repairs. Qualification
applies to the source and binaries recorded with each result. The remaining
runtime and release obligations follow the routing above.

1. **Carry the baseline forward.** Use the integrated plan's
   [evidence-review section](development/MANAGER-INTERFACE-PLAN.md#remaining-offline-runtime-coverage-and-evidence-review)
   to locate the current results, selected failures and witnesses. Preserve
   them through their specified reviews. Reconcile any newly discovered uncertain
   process or durable effect before reusing that work; a fresh broad suite or
   historical cleanup is not an entry requirement.
2. **Keep the live-testing handoff explicit.** The
   [subscription testing track](development/MANAGER-INTERFACE-PLAN.md#additional-claude-code-subscription-testing)
   uses the implemented service procedure and reviewed open-inquiry profile.
   The earlier surface draft is superseded; no C1–C4 start remains authorized.
   Revalidate current profile and procedure bindings for each new commission.
   The reviewed native encounters leave final usage, page fidelity and live
   continuation unresolved; broader trials remain separately bounded. Those
   results do not qualify the manager interface or the Messages release gate.
3. **Enter the existing plan at stage 1:**
   [specify the shared contracts](development/MANAGER-INTERFACE-PLAN.md#1-specify-the-shared-commissioning-and-documentary-contracts).
   Start with the CLI walk-through and rule/diagnostic inventory, then freeze the
   question-role, MCP and effect-description schemas with their acceptance
   examples. Arrange implementation-independent driver authorship before changes
   needing both service and driver work. Implementation follows that plan's
   sequence and DEVELOPMENT checks.

This transition is complete when stage 1 is underway with the baseline and
remaining obligations accounted for. Remove this entry section then; the work
order and topic plans continue to own execution. No model launch or container run
is required merely to make this transition.

## Current evidence

[README](README.md#status) owns product maturity and coverage limits;
[the qualification index](apparatus/qualified.md) owns current suite results
and selected evaluations. Retain originals for inspection under
[DEVELOPMENT](development/DEVELOPMENT.md#evidence-and-retention), not to reconstruct old
builds.

## Deferred studies

The integrated plan includes preparation of bounded procedural question-family
trials, without authorizing live calls. Broader blinded evaluation and family
dogfooding remain deferred; the [family contract](CONTRACTS.md#question-families-and-open-inquiry)
owns their product boundaries. An agent-manager study omitting the question from
returns is only an option after the manager interface is established and the
principal selects it, not a pending task. A future study needs a named uncertainty
and bounded commission. [Completed interaction findings](apparatus/studies/interaction/RESULTS.md)
and the evidence index retain the observations and original input locations.

## First-release requirements

| Requirement | Remaining work |
| --- | --- |
| Linux container qualification | Run the scripted acceptance suite on the release source and binaries, on both architectures with the required controls. |
| Native WSL2 qualification | Package the same binary, driver and fake provider; arrange and review the user's native run. |
| Real-model conformance | Complete [Messages API conformance](MESSAGES-API-CONFORMANCE-PLAN.md) and qualify each model the release names under an authorized budget. |
| Public release gate | Set the binary release schedule with the principal. |

The requirements remain those of ACCEPTANCE while its review is open.

### Coverage and acceptance-policy review

Check driver cases against every ACCEPTANCE claim. Uncovered requirements need a
case or an explicit disposition. Candidate gaps include C17's secondary logging
errors, blind repetition after reply failure and omitted partial effects; C18's
pressure pruning, confusion between retained and delivered bytes, and missing
archives reported clean; and C11's scans presented as snapshot proof. Driver
changes require an implementation-independent author.

Resolve these acceptance-policy questions without silently changing the current
requirements:

- Confirm the platform and real-model release gates and coverage scope.
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
- Decide whether to support running the apparatus from a Linux host; the
  documented host route uses macOS and Apple `container`.

### WSL2 package

The package must carry the same qualified release/test binaries, driver and fake
provider. Run with the home on the WSL filesystem and a destination under `/mnt/`;
record Windows/WSL versions, distribution, kernel, architecture and filesystems.
The native timing gate applies. Native x86_64 is unexercised, so its timings must
be measured rather than inferred from Rosetta.

Needs: a package builder, instructions and the user's scheduled run.

Deferred product scope belongs in CONTRACTS; it is not additional release work.
