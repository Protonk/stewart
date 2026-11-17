# Test wall-clock time

**Current status:** Deferred until the first release is complete; not started.

Shorten how long the checks and container suites take without weakening what
they establish. [DEVELOPMENT](DEVELOPMENT.md#what-to-run-for-what-you-changed)
owns which checks a change needs and [ACCEPTANCE](../ACCEPTANCE.md) the evidence
they owe; this plan changes how fast they run, not what they cover.

## Where the time goes today

Measured from the `acceptance-lookback-02` suite (2026-11-17, about 60 minutes)
and native runs on the development Mac the same day:

| Stage | Wall-clock |
| --- | --- |
| arm64 build (native container) | about 1.5 min |
| arm64 release driver | about 6 min |
| arm64 synthetic runtime driver | about 17 min |
| amd64 build (emulated) | about 3.5 min |
| amd64 release driver (emulated) | about 8 min |
| amd64 synthetic runtime driver (emulated) | about 23 min |
| Native complete runtime driver | about 20 min |
| Native Cargo test execution, excluding compilation | about 1.5, 4, 2 and 3 min for the release, fault/sabotage, `claude-code` and `claude-code,fault-injection` configurations |

The synthetic runtime driver is about two-thirds of the suite. The stages run
one after another, and amd64 runs under emulation. Neither driver records
per-case durations, so the slowest cases are not yet known.

## Tasks

- [ ] Measure first. Record per-case, per-variant and per-control wall-clock in
  both drivers' results and the suite's stage times in the qualification record,
  and attribute the time to fixed waits, placement deadlines, process startup,
  emulation and compilation. Driver changes need a specification-only author.
- [ ] In the runtime driver, replace fixed waits with observed events where the
  measured property allows, shorten deadlines whose length is not the property
  under test, and consider running independent cases concurrently in separate
  work roots while timing-sensitive cases stay serial.
- [ ] In the suite, consider running the two architectures concurrently if the
  host has capacity and the arm64 timing gate is not disturbed, and whether a
  native x86_64 host should replace emulation (this meets the acceptance-policy
  question on Linux hosts and the native WSL2 timings).
- [ ] For Cargo, separate compile from run time across the four configurations,
  find the long test binaries (the fault/sabotage configuration's longest is
  about 95 seconds) and avoid redundant rebuilds.

Every firing control, differing case and invariance case keeps running. Timing
gates keep their meaning: concurrency must not inflate a gated measurement, or
that measurement runs alone. Results stay comparable with earlier qualification
records. Any reduction in coverage is the principal's decision, not a speed
optimization.

Complete this plan when before-and-after times are measured on the same host
with unchanged outcomes and controls, and DEVELOPMENT describes the faster
procedures. Then delete the plan.
