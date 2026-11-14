# Release and work plan

This plan owns cross-plan order and first-release obligations. Topic plans own
remaining tasks and decisions. [CONTRACTS](CONTRACTS.md) and
[INTERFACE](docs/INTERFACE.md) own behavior; [ACCEPTANCE](ACCEPTANCE.md) owns the
evidence owed. [README](README.md#status) owns demonstrated product status and
the [qualification index](apparatus/qualified.md) owns retained results.

## Work order

| Order | Remaining work | Owner |
| --- | --- | --- |
| Current | Obtain the principal's disposition of M3, whose commission ran one placement and left interruption and continuation unexercised; then complete or dispose of M4/C5, outcome repairs, fixtures and reassessment. | [Readiness follow-up](READINESS-FOLLOW-UP-PLAN.md) owns the bounded comparisons; the Messages and manager plans own reusable apparatus work in their respective areas. |
| After readiness dispositions | Specify and implement shared commissioning rules, the independent CLI additions, optional preparation MCP and fake-provider integration. | [Manager interface](development/MANAGER-INTERFACE-PLAN.md) |
| Alongside manager work, separately commissioned | Extend procedural question-family and runtime trials. A real-service result is not an entry gate for manager MCP or fake-provider boundary acceptance. | The manager plan's subscription testing track |
| Separately scheduled release work | Complete the Messages model gate, platform qualification and acceptance-policy review. | [Messages API conformance](MESSAGES-API-CONFORMANCE-PLAN.md) and the requirements below |
| Unselected | Broader blinded evaluation and family dogfooding. | [Deferred studies](#deferred-studies) |

Use the existing apparatus and retained exact writers; reconcile uncertain
processes or effects before reusing them. Build only the prerequisites needed
for the selected comparison. Full model conformance is separate from the
bounded readiness observations. Live starts need concrete approval; container
runs and the public release remain the principal's scheduling decisions.

At the manager transition, enter its specification stage and freeze roles,
diagnostics, MCP and effect-description schemas before dependent implementation.
Arrange independent driver authorship where service and driver changes are both
needed. Give residual work one owner in place; do not create a turnover document.

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
case or an explicit disposition. Add independent black-box comparisons for
interim/folded/conflicting-length response heads, the retained-payload reserve
boundary and `not_sent` notices; specification text and service-unit checks do
not establish that coverage. The driver also lacks cases for close's `unknown`
seal, delivery and closure effects after a failed publication, the `--verify`
`problem` member and a symbolic link above an item, `receipt_record_failed`
before the acceptance link, a `checked_at` that is not a timestamp, and a null
JSON-RPC error `id` from the binary. Reassess unreached/partly reached conditions and
unclear behavioral promises against the actual cases. Candidate gaps include
C17's secondary logging
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
