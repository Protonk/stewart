# Release and work plan

This plan owns work order and the remaining first-release work. Individual plans
own their task's decisions and execution details. Product behavior is specified
in [CONTRACTS.md](CONTRACTS.md) and [docs/INTERFACE.md](docs/INTERFACE.md);
[ACCEPTANCE.md](ACCEPTANCE.md) defines the evidence owed.

## Work order

| Stage | Work | Working document |
| --- | --- | --- |
| Current build work | Qualify the default-off build and release absence boundary in the separately scheduled container run; native checks pass | [BUILD-FLAG-SETUP-PLAN.md](BUILD-FLAG-SETUP-PLAN.md) |
| Current runtime work | Complete the remaining failure controls and prepare a bounded commission for real service conformance; the implemented adapter passes native synthetic checks | [CLAUDE-CODE-PLAN.md](CLAUDE-CODE-PLAN.md) |
| Later, after the two above | Align the manager interface, using the development runtime for iteration and including the decided return of the accepted question body with the answer | [MANAGER-ALIGNMENT-PLAN.md](MANAGER-ALIGNMENT-PLAN.md) |
| Separately scheduled release work | Complete Messages API conformance, platform qualification and acceptance review | [MESSAGES-API-CONFORMANCE-PLAN.md](MESSAGES-API-CONFORMANCE-PLAN.md) and the release requirements below |
| Unselected | Further auditor studies and question-family dogfooding | [Deferred studies](#deferred-studies) |

Further API studies and completion of the API conformance gate are not
prerequisites for the build setup or Claude Code feasibility work. Claude Code
feasibility and the adapter contract are decided. Implementation and offline
verification are authorized; further live checks require their own bounded
commission. Planning and previous model placements confer no spending authority.

The return-context decision needs no further presentation tuning or reader
comparison before implementation. No additional reading interface or return
context is selected here.

## Current evidence

[README](README.md#status) owns product maturity and coverage limits;
[the qualification index](apparatus/qualified.md) owns current suite results
and selected evaluations. Retain originals for inspection under
[DEVELOPMENT](development/DEVELOPMENT.md#evidence-and-retention), not to reconstruct old
builds.

## Deferred studies

No further auditor study is selected. Blinded evaluation and question-family
dogfooding are deferred; the [family contract](CONTRACTS.md#question-families-and-open-inquiry)
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

### Remaining test discrepancies

- Add a check that prepares the worked examples. Make unavailable loopback tests
  report actual skips rather than printing SKIPPED and returning as passed.

Deferred product scope belongs in CONTRACTS; it is not additional release work.
