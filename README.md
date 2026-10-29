# Stewart

Stewart is a custodian for bounded inquiries between cooperative parties. The
manager supplies a question, selected files, an answer family and limits. Stewart
places an auditor in that arrangement and returns its answer faithfully, without
judging its conclusions.

The manager's working model is one submission folder, one acceptance boundary
and one close action. Stewart's opinions live in its question families and
instructions; missing evidence, no finding and disagreement remain ordinary
answers. Records preserve who said what and what Stewart actually did.

## Current design

- [Design and vision](DESIGN.md): responsibilities, workflow and architecture.
- [Decided contracts](CONTRACTS.md): the behavioral specification.
- [Acceptance specification](ACCEPTANCE.md): the evidence the implementation owes.
- [Question forms](docs/QUESTION-FORMS.md) and [worked examples](examples/questions/README.md): concrete inputs to detailed specification.

The design review is closed. These maintained documents are the design; prior
conversations and alternative sketches are not required reading.

## Implementation status

The complete Rust audit service is decided but not yet implemented. It will ship
as one static Linux binary for x86_64 and aarch64, with WSL2 qualification. Its
auditor has only Stewart's tools, and materials are copied files rather than a
Git checkout.

Two narrower implementations currently exist:

- The [frozen Python audit tool](docs/FROZEN-PYTHON.md), with its
  [bundled manual](src/stewart/resources/README.md), remains available until the
  successor and legacy-retirement gates are satisfied. It is not a parity baseline.
- The [Rust commission-bundle slice](successor/README.md) accepts and independently
  reads original-input bundles. It does not run an auditor or hold audit results.

## Development

[Coordination](coordination/README.md) is the entry point for a new coordinator.
[AGENTS.md](AGENTS.md) contains development constraints and
[DEVELOPMENT.md](DEVELOPMENT.md) documents existing build/check commands and
evidence retention. Active implementation work is organized by the tracked
`*-PLAN.md` convention; plans are working accounts, not additional product specs.
