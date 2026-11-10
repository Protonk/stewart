# Release and work plan

This plan owns work order and the remaining first-release work. Individual plans
own their task's decisions and execution details. Product behavior is specified
in [CONTRACTS.md](CONTRACTS.md) and [docs/INTERFACE.md](docs/INTERFACE.md);
[ACCEPTANCE.md](ACCEPTANCE.md) defines the evidence owed.

## Work order

| Stage | Work | Working document |
| --- | --- | --- |
| Next | Set up the default-off development build that carries the Claude Code adapter, its release absence check and its credential route | [BUILD-FLAG-SETUP-PLAN.md](BUILD-FLAG-SETUP-PLAN.md) |
| After the build setup | Resolve Claude Code feasibility and propose the adapter contract; implementation follows the resulting decisions, inside that build | [CLAUDE-CODE-PLAN.md](CLAUDE-CODE-PLAN.md) |
| Independent of the two above | Align the manager interface, including the decided return of the accepted question body with the answer | [MANAGER-ALIGNMENT-PLAN.md](MANAGER-ALIGNMENT-PLAN.md) |
| Separately scheduled release work | Complete Messages API conformance, platform qualification and acceptance review | [MESSAGES-API-CONFORMANCE-PLAN.md](MESSAGES-API-CONFORMANCE-PLAN.md) and the release requirements below |
| Deferred until the build setup, Claude Code and manager alignment plans finish | Rework the root README | [README-RESCUE-PLAN.md](development/README-RESCUE-PLAN.md) |
| Unselected | Further auditor studies and question-family dogfooding | [Deferred studies](#deferred-studies) |

Further API studies and completion of the API conformance gate are not
prerequisites for the build setup or Claude Code feasibility work. Claude Code
feasibility research may begin during the build setup; adapter code waits for
it. Planning and previous model placements confer no execution or spending
authority.

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

- Reconcile ACCEPTANCE's per-change tier/image language with batched container
  qualification and the current pinned Python runner.
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

### Documentation and test discrepancies

- Align CONTRACTS' illustrative prepare/submit field names with INTERFACE 7.6
  (`prepared_handle`, `answer_revision` and the notice key `section` differ).
  Clarify the synonymous family/form terminology where needed.
- Correct INTERFACE 9's claim that named fault traces run against the release
  binary; fault points are test-build features. Correct CLI help's assertion
  that every non-help command accepts `--json`: raw receipt readback does not.
- Have an implementation-independent author correct the TLS fixture README's
  expired-certificate validity and its description of wrong-name/expired
  self-test fixtures as driver controls.
- Add a check that prepares the worked examples. Make unavailable loopback tests
  report actual skips rather than printing SKIPPED and returning as passed.

Deferred product scope belongs in CONTRACTS; it is not additional release work.
