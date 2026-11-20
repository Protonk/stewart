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

The dependencies are six crates pinned to exact versions in `Cargo.toml`:
`libc`, `sha2`, `rustls` with its `ring` provider, `webpki-roots`, `secrecy`
and `zeroize`.
`Cargo.lock` pins the whole graph, and builds use the vendored sources in
`vendor/`, which is not tracked.

## Modules by role

One audit can be followed through them: `cli.rs` and `ops/` for the manager's
commands, `ops/run.rs` into `provider/placement.rs` for a Messages API run, `answer/` for
each tool call, then `delivery/` and `ops/close.rs`.

**CLI and help**

- `main.rs`: the binary's entry point; it calls `cli::main`.
- `cli.rs`: exact argument parsing and presentation (5.1).
- `effects.rs`: compiled descriptions shared by `describe` and `help commands` (5.10).
- `manager_mcp/`: the preparation server on stdio (5.11). `assessment.rs`
  applies commissioning rules to caller-supplied question text and inventory.
  `assembly.rs` generates a candidate's question file and inventory from
  explicit inputs and applies the refusal order. `workspace.rs` admits the
  launcher's `--workspace DIR`, reads named sources under `sources/` through
  descriptors and creates one candidate folder exclusively, reporting its
  writes. `rpc.rs` decodes the protocol envelope and leaves metadata opaque.
- `help.rs`: `stewart help` and its topics, printed exactly (5.9). The
  development build adds one topic, `runtime`, whose text is in
  `claude_code.rs`.
- `reply.rs`: the `stewart.reply/3` envelope and its human presentation
  (1.3–1.7).

**Manager operations**

- `ops/presentation.rs`: shared read-only resource and lifecycle accounts.
- `ops/`: one file per command, `new`, `prepare`, `commission`, `receipt`,
  `run`, `status` and `close` (5.2–5.8); `ops/mod.rs` holds what they share.
- `frontmatter.rs`, `roles.rs`, `intake.rs`, `scan.rs`: the `question/2` front matter, declared material roles and family descriptors,
  mechanical rules over supplied bytes and names, and descriptor-based
  acquisition of the submission folder (3). In the development build the same version
  takes the three
  [runtime fields](../docs/claude-code/CONTRACT.md#development-input-and-preparation-schema),
  and naming `runtime-profile` selects the runtime.
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
- `credential.rs`: bounded one-use descriptor input, secret values and
  credential-reflection detection (6.1). The process protection primitives are
  in `platform.rs`; raw provider evidence remains exact.
- `provider/placement.rs`: the loop of one placement, including provider
  summary requests and resumption from the signed summary under the same limits.
- `provider/request.rs`: the pinned arrangement, decoded once with its exact
  bytes kept, and the active messages each request appends or replaces after
  successful compaction (4.5, 6.2).
- `provider/response.rs`, `json/tolerant.rs`: tolerant decoding and
  classification of responses, signed summaries and iteration usage (6.2, 6.6).
- `provider/policy.rs`: pure retry and next-step decisions.
- `provider/transport.rs`, `provider/http.rs`, `provider/tls.rs`,
  `provider/url.rs`: one attempt over a fresh connection, HTTP/1.1 framing, TLS
  against the built-in web PKI roots, and the base URL and proxy grammar.
- `provider/stop.rs`: the stop path: the close watcher and signals (6.8).
- `runs.rs`: each placement's `runs/<n>` directory, raw captures and linked
  records (4.5); `runs::request_body`, which splices each request body from
  the arrangement's pinned bytes and captured messages, honoring recorded
  context replacements without discarding earlier captures; and the
  accounting of a placement without `run_ended` (6.4).
- `usage.rs`: usage, charges and cumulative allowances (6.4).
- `claude_code/`: the default-off development runtime, entered from `ops/run.rs`;
  profile and arrangement bindings, the launch surface that a profile's check
  names, MCP transport, the publication gate, harness accounting and process
  supervision. `surface.rs` is the only construction of what a launch supplies
  to the harness, so the surface digest describes the actual launch. Its
  [runtime contract](../docs/claude-code/CONTRACT.md) owns differences from the
  Messages API path.

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

Unit tests sit beside the code in `src/`, and pure rules are tested there. The
integration tests in `tests/` run the real binary from an unrelated working
directory, each with its own folder, archive and destination; the auditor-tool
tests drive the tools in process against an audit the real binary commissioned.

The independent drivers, the [release driver](../apparatus/README.md#the-independent-driver)
and the [runtime driver](../apparatus/driver/CLAUDE-CODE.md), own the behavior
they witness; run them natively with `--case` while iterating. An integration
test here covers what they do not: a fault point or boundary no driver case
reaches, behavior a driver case observes only on Linux, or exact bytes and
archive state that only the implementation names.

| File | Covers | Built with |
| --- | --- | --- |
| `manager.rs` | The manager commands before launch, and a host name rule of candidate assembly | any |
| `faults.rs` | Manager-foundation failure points and the fault harness | `fault-injection` |
| `answer.rs` | The auditor's tools in process | any |
| `answer_faults.rs` | The answer protocol at its failure points | `fault-injection` |
| `run.rs` | `stewart run` against a scripted fake provider on loopback | any |
| `run_faults.rs` | `stewart run` at its failure points | `fault-injection` |
| `delivery.rs` | Delivery, close and status after launch | any |
| `close_faults.rs` | Delivery and close at their failure points | `fault-injection` |
| `claude_code.rs` | The development runtime through the real binary, and its call dispatch in process; its `faults` module holds the failure points | `claude-code`; `faults` also needs `fault-injection` |

Shared support is in `tests/common/` (the harness), `tests/fixture/` (states
after launch built with the crate's own writers), `tests/answer_support/` (a
live placement in process), `tests/run_support/` (the scripted fake provider)
and `tests/fixtures/provider/` (test-only TLS certificates).

A test that binds a loopback listener or Unix socket, or starts a supervised
process group, fails and names the reason where the host forbids it. The
runtime placements likewise fail when the scratch directory lies under a
project or configuration tree, where the runtime refuses to launch. A test of
a host-specific name rule prints `SKIPPED` and passes on a host without that
rule.

## Building and testing

Run Cargo from this directory, so that `.cargo/config.toml` points it at the
vendored sources. `cargo test --locked --offline` tests release behavior;
[DEVELOPMENT](../development/DEVELOPMENT.md#what-to-run-for-what-you-changed)
names the other configurations each kind of change needs.

### Development runtime build

The default-off `claude-code` feature contains the subscription harness adapter
in `src/claude_code.rs` and its child modules. The
[development runtime contract](../docs/claude-code/CONTRACT.md) owns its
question fields, profile schema, observation limits, placement accounting and
[what help and human output must say](../docs/claude-code/CONTRACT.md#help-run-requirements-and-presentation).
A question without `runtime-profile` keeps the Messages API path, and the
scaffold is the same in both builds; `stewart help runtime` in the development
build explains the difference. Build and check it in a separate target folder:

```sh
CARGO_TARGET_DIR=target-local cargo test --locked --offline --features claude-code
CARGO_TARGET_DIR=target-local cargo build --locked --offline --release --features claude-code
```

This extends the native Apple-silicon workflow. Keep the resulting binary for
any audits it creates: its writer digest differs from the release binary, so
the release cannot continue or close those audits. A runtime profile's check is
bound to the [launch surface](../docs/claude-code/CONTRACT.md#launch-surface)
instead, so a rebuild that leaves the surface unchanged accepts an existing
profile for new audits. Unit tests compare the surface and the pinned runtime
texts with the contract byte for byte, so a changed surface value or pinned text
needs the contract's worked example, digest or quoted block changed too.
Gated-build runs are
development iteration and qualify neither the distributed binary nor a model.
An observation under one credential route does not establish another route.

The [independent runtime driver](../apparatus/driver/CLAUDE-CODE.md) uses a
synthetic executable to check preparation, core MCP effects, stopping and
continuation. It invokes no Claude process. Real setup or runtime checks need
their own bounded commission; the earlier two-tool probe is not a service
qualification or a check of this build's launch surface.

The runtime container suite checks
[`claude-code-markers.txt`](../apparatus/claude-code-markers.txt): every listed
string must be absent from the release binary and reachable in both
development writers, which are the check's firing controls. When adapter code
gains an essential identifying string, add it to the list; unused strings
disappear under fat LTO.

[DEVELOPMENT.md](../development/DEVELOPMENT.md) covers the rest: producing `vendor/`, the
release and test builds, the independent driver, and the Linux container
suites. The release and development runtime have separate Linux qualification records.

## Platform

Linux is the supported platform. Apple-silicon macOS is a build target. Every
Linux-only call is in `src/platform.rs`, each beside its macOS fallback. The
fallbacks let the crate build, test and run natively on a Mac; they are not
supported behavior, and what rests on them (the OFD active lock, `/proc` observations, the archive
filesystem allowlist) behaves as shipped only on Linux.

Before adding a call to a libc function, read "Calling libc" in the crate
documentation in `src/lib.rs`. The fat-LTO static release build constrains how
some of these calls are made, and the rule names them.
