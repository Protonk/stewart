# The service crate

This crate is Stewart: the Rust audit service, built as the binary `stewart`.
It holds the whole audit: the reference and archive, the submission folder,
prepare and commission, receipt readback, the run adapter and the auditor's
tools, seal, delivery, status, and close from every state. It implements
[docs/INTERFACE.md](../docs/INTERFACE.md) and
[docs/QUESTION-FORMS.md](../docs/QUESTION-FORMS.md) under the behavioral
authority of [CONTRACTS.md](../CONTRACTS.md). Module documentation cites
INTERFACE by section number (for example 5.8 for close), so read the two side
by side.

The crate documentation at the top of [`src/lib.rs`](src/lib.rs) lists the
modules and states a rule for calling libc, and each module opens with its own
account of what it does and why. This guide is a map for a first reading; those
comments hold the detail.

The dependencies are four crates pinned to exact versions in `Cargo.toml`:
`libc`, `sha2`, `rustls` with its `ring` provider, and `webpki-roots`.
`Cargo.lock` pins the whole graph, and builds use the vendored sources in
`vendor/`, which is not tracked.

## Modules by role

One audit can be followed through them: `cli.rs` and `ops/` for the manager's
commands, `ops/run.rs` into `provider/placement.rs` for the run, `answer/` for
each tool call, then `delivery/` and `ops/close.rs`.

**CLI and help**

- `main.rs`: the binary's entry point; it calls `cli::main`.
- `cli.rs`: exact argument parsing and presentation (5.1).
- `help.rs`: `stewart help` and its topics, printed exactly (5.9).
- `reply.rs`: the `stewart.reply/1` envelope and its human presentation
  (1.3–1.6).

**Manager operations**

- `ops/`: one file per command, `new`, `prepare`, `commission`, `receipt`,
  `run`, `status` and `close` (5.2–5.8); `ops/mod.rs` holds what they share.
- `frontmatter.rs`, `scan.rs`: the submission folder: the `question/1` front
  matter and the material scan (3).
- `forms.rs`: the question families, their pinned texts and tool definitions,
  and the arrangement prepare pins (QUESTION-FORMS; 6.2).

**Answer protocol**

- `answer/mod.rs`: executing one `tool_use` block of a live placement, and the
  division of work with the run adapter (7).
- `answer/input.rs`: strict decoding of tool inputs.
- `answer/reading.rs`: `list`, `read` and `search` (7.1, 7.2).
- `answer/edit.rs`: `record_<kind>`, `record_artifact`, `replace` and
  `delete`, with their citations (7.3, 7.4).
- `answer/reentry.rs`: `what_am_i_working_with` (7.5).
- `answer/prep.rs`: the structured answer and its renderer, `prepare` and
  `submit`, and the preparation and seal shared with close (7.6, 8.1).
- `answer/common.rs`, `answer/b64.rs`: what every tool shares; base64.
- `world.rs`: a placement's verified captures and pinned arrangement, from
  which reads and searches are served.

**Provider and run adapter**

- `provider/mod.rs`: the request loop in outline (6).
- `provider/placement.rs`: the loop of one placement.
- `provider/request.rs`: the pinned arrangement, decoded once with its exact
  bytes kept, and the messages each request appends (4.5, 6.2).
- `provider/response.rs`, `provider/tolerant.rs`: tolerant decoding and
  classification of responses (6.2, 6.6).
- `provider/policy.rs`: pure retry and next-step decisions.
- `provider/transport.rs`, `provider/http.rs`, `provider/tls.rs`,
  `provider/url.rs`: one attempt over a fresh connection, HTTP/1.1 framing, TLS
  against the built-in web PKI roots, and the base URL and proxy grammar.
- `provider/stop.rs`: the stop path: the close watcher and signals (6.8).
- `runs.rs`: each placement's `runs/<n>` directory, raw captures and linked
  records (4.5); `runs::request_body`, which splices each request body from
  the arrangement's pinned bytes and the appended messages; and the
  accounting of a placement without `run_ended` (6.4).
- `usage.rs`: usage, charges and cumulative allowances (6.4).

**Delivery**

- `delivery/mod.rs`: planning, writing, verifying and recording a delivery
  attempt, and presenting attempts (8.3, 8.4).
- `returns.rs`: the return manifest written at seal (8.2) and each attempt's
  delivery plan (8.3).

**Records and archive**

- `archive.rs`: the store marker, reference resolution, audit directories,
  record headers, the active lock and diagnostics (4).
- `log.rs`: the linked audit log and its one publication rule (4.4).
- `bodies.rs`: the log record bodies after launch.
- `records.rs`: the preparation manifest and the acceptance receipt.
- `names.rs`: the names Stewart generates and the claims that allocate
  numbered ones.
- `json.rs`: strict control JSON and the deterministic writer (1.2).
- `ids.rs`: identifiers, handles and the `stw1:` reference (2).

**Platform**

- `platform.rs`: the Linux-only calls, with development fallbacks.
- `fsx.rs`: descriptor-relative filesystem access and exclusive writes.
- `util.rs`: digests, UTC timestamps, errno names and edit distance.

**Test builds**

- `fault.rs`: the registries of fault points and sabotage controls, the
  readers of their variables, and the `fault!`, `fault_corrupt!`,
  `fault_armed!` and `sabotage!` macros.

## Test builds

INTERFACE Appendix C defines two cargo features for test builds.
`fault-injection` adds named failure points (kill, I/O errors, corruption and
pauses) and three test-only provider settings: an extra TLS root, a provider
timeout and retry delays. `sabotage` adds controls that each break exactly one
property, so that the check for that property can be shown to fire. Both are
set through `STEWART_TEST_*` environment variables. `src/fault.rs` holds the
registries, the readers of those variables, the macros and the kill, error and
pause actions. Corruption, and what each sabotage control breaks, are coded in
the module that does the work, behind a macro or in code compiled only with
the feature. A build with both features is the test build, which the apparatus
names `stewart-test`.

The release binary is built with neither. The `fault!`, `fault_corrupt!`,
`fault_armed!` and `sabotage!` macros then expand to constants and the
feature-gated code is left out, so it contains neither the features' code nor
the variable names, and the acceptance suite checks the names with the test
build as its firing control. Since only a test build can add a root, the
release trusts only its built-in roots.

## Tests

Unit tests sit beside the code in `src/`. The integration tests in `tests/` run
the real binary from an unrelated working directory, each with its own folder,
archive and destination; the auditor-tool tests drive the tools in process
against an audit the real binary commissioned.

| File | Covers | Built with |
| --- | --- | --- |
| `manager.rs` | The manager commands end to end | any |
| `faults.rs` | Manager-foundation failure traces at fault points | `fault-injection` |
| `sabotage.rs` | Manager-foundation sabotage controls, each breaking its property | `sabotage` |
| `answer.rs` | The auditor's tools against a live placement | any |
| `answer_faults.rs` | The answer protocol at its fault points | `fault-injection` |
| `answer_sabotage.rs` | Answer-protocol controls, each checked with and without | `sabotage` |
| `run.rs` | `stewart run` against a scripted fake provider on loopback | any; some cases need a feature |
| `delivery.rs` | Delivery, close and status after launch | any |
| `manager_seal.rs` | Close's manager seal through the answer module | any |
| `close_faults.rs` | Delivery and close failure traces | `fault-injection` |
| `close_sabotage.rs` | Delivery, close and status sabotage controls, and the run-handoff controls `relative_run_line` and `commission_over_network` (ACCEPTANCE C12) | `sabotage` |

Shared support is in `tests/common/` (the harness), `tests/fixture/` (states
after launch built with the crate's own writers), `tests/answer_support/` (a
live placement in process) and `tests/fixtures/` (an expected answer and
rendering, and test-only TLS certificates).

Some tests bind a loopback listener: the `run.rs` cases, the transport unit
tests in `src/provider/transport.rs` and `commission_over_network` in
`close_sabotage.rs`. Where binding is not permitted, the `run.rs` cases and the
transport tests print `SKIPPED` and return, which Cargo reports as passing;
`commission_over_network` fails instead.

## Building and testing

Run Cargo from this directory, so that `.cargo/config.toml` points it at the
vendored sources. The two test configurations, release behavior and the test
build:

```sh
cargo test --locked --offline
CARGO_TARGET_DIR=target-test cargo test --locked --offline --features fault-injection,sabotage
```

[DEVELOPMENT.md](../DEVELOPMENT.md) covers the rest: producing `vendor/`, the
release and test builds, the independent driver, and the Linux container
suites, which alone count as evidence.

## Platform

Linux is the only supported platform. Every Linux-only call is in
`src/platform.rs`, each beside its macOS fallback. The fallbacks let the crate
build and test natively on a development Mac; they are not supported behavior,
and what rests on them (the OFD active lock, `/proc` observations, the archive
filesystem allowlist) behaves as shipped only on Linux.

Before adding a call to a libc function, read "Calling libc" in the crate
documentation in `src/lib.rs`. The fat-LTO static release build constrains how
some of these calls are made, and the rule names them.
