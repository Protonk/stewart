# Building and testing Stewart

Stewart is the Rust audit service in [`service/`](../service): one crate, binary
`stewart`. [`apparatus/`](../apparatus) holds what builds and tests it: pinned
Linux toolchain images, container scripts and an independent acceptance driver
with a fake provider. The apparatus does not ship. What to build and what
evidence is owed are in [DESIGN.md](../DESIGN.md),
[CONTRACTS.md](../CONTRACTS.md), [ACCEPTANCE.md](../ACCEPTANCE.md) and
[docs/INTERFACE.md](../docs/INTERFACE.md); [AGENTS.md](../AGENTS.md) states the
development rules.

The product is one statically linked binary for Linux x86_64 and aarch64
(CONTRACTS, "Platform and auditor access"), built and qualified in Linux
containers. Linux is the supported platform. `aarch64-apple-darwin` is a build
target: the crate builds, tests and runs there, with no release, support or
qualification claim. Work iterates quickly on the development Mac, but native
runs do not qualify Linux behavior.

## What to run for what you changed

Find each kind of change you made in the table and run what its row names, from
the repository root unless it says otherwise. Native runs are for iteration. A
container suite builds from a `git archive` of `HEAD`, so commit before one is
run. The suites need Apple `container` on the host; an agent whose shell is
sandboxed cannot reach it, so the agent prepares the command and the user runs
it ([Container suites](#container-suites)).

The link check, the driver's self-test and its case list:

```sh
python3 -I -B apparatus/check_links.py
python3 -I -B apparatus/driver/stewart_driver.py --self-test
python3 -I -B apparatus/driver/stewart_driver.py --list
```

The release and fault/sabotage Cargo configurations, from `service/` ([Building and testing
natively](#building-and-testing-natively)):

```sh
cargo test --locked --offline
CARGO_TARGET_DIR=target-test cargo test --locked --offline --features fault-injection,sabotage
```

Changes to service code or build configuration also need the development
configuration, from `service/`:

```sh
CARGO_TARGET_DIR=target-local cargo test --locked --offline --features claude-code
```

| What changed | What to run |
| --- | --- |
| Prose or Markdown anywhere | The link check. |
| `docs/INTERFACE.md` or `docs/QUESTION-FORMS.md` | The link check, both cargo configurations and the driver's self-test. A test in `service/src/forms.rs` compares the service's pinned texts and tool descriptions with QUESTION-FORMS; one in `service/src/fault.rs`, built only in the fault and sabotage configuration, compares its failure points, actions and sabotage controls, and the names in its variable table, with INTERFACE Appendix C. The driver's self-test compares its own copies of the pinned texts and tool descriptions with QUESTION-FORMS, and its answer witness reproduces the structured answer and rendering examples of QUESTION-FORMS and the manifest example of INTERFACE 8.2 byte for byte. A changed pinned text or tool description needs the service's copy changed too (then the `service/` row applies); a changed pinned text or example needs the driver's copy updated, under the driver-independence rule in [AGENTS.md](../AGENTS.md). |
| Worked example materials: `question.md` and `materials/` under `examples/questions/*/submission/` | No check reads them. The walkthroughs, `CITATION-CONTROLS.md`, QUESTION-FORMS and INTERFACE cite their sizes, byte ranges and line numbers, and the driver's answer witness pins the examples in those docs, so recheck every citation of a changed file; a changed example in the docs then needs the row above. |
| `CONTRACTS.md`, `DESIGN.md` or `ACCEPTANCE.md` | The link check. Changing what Stewart promises is the user's decision. |
| `service/src/` or `service/tests/` | All three cargo configurations above. A behavior change is unqualified until the next container run of `acceptance.sh`, which the user schedules and batches; it can land and be pushed once all three configurations pass. |
| Release driver and shared helpers in `apparatus/driver/` | `stewart_driver.py --self-test` and `--list`, which loads every release case module. Shared helpers used by the standalone runtime driver also need that driver's checks below. Release-driver qualification needs the next container run of `acceptance.sh`, which the user schedules and batches; the change can land once its native checks pass. Edit only under the driver-independence rule in [AGENTS.md](../AGENTS.md). |
| `apparatus/driver/claude_code.py` or its `CLAUDE-CODE.md` | `python3 -I -B apparatus/driver/claude_code.py --self-test` and `--list`. Runtime behavior changes also need the affected synthetic cases against the gated binary, retaining witnesses as described in the driver guide. Linux qualification needs the next container run of `acceptance.sh`, which also runs this standalone driver on both architectures. |
| `apparatus/driver/claude_code_surface.py` or its `CLAUDE-CODE-SURFACE.md` | `python3 -I -B apparatus/driver/claude_code_surface.py --self-test`, then its synthetic rehearsal with `--binary /absolute/gated-stewart --work /absolute/fresh-evidence` on the native host where Unix sockets and process observation are permitted. Run `apparatus/claude-code/test_profile.py` too when changing the shared check inventory or artifact interface. These exercise the independent fixture and actual transport helpers; they do not establish real-harness conformance or Linux qualification. |
| Runtime schemas or pinned texts in `docs/claude-code/CONTRACT.md` | The link check, the `claude-code` Cargo configuration, and the standalone runtime driver's self-test and list. Update exact service/driver copies when their pinned bytes change, preserving independent authorship. Prose-only status changes need the link check. |
| `apparatus/c10/` | `python3 -I -B apparatus/c10/test_c10.py`, `python3 -I -B apparatus/sanity/test_launch.py`, and the driver's self-test for the specification-derived helpers it imports. Exercise changed run, reviewer and operator behavior with the native fake-provider commands in [the apparatus instructions](../apparatus/c10/README.md#run-the-offline-checks). The change remains unqualified until its retained Linux `c10.py rehearse` run, scheduled by the user after committing. No model calls are needed for these checks. |
| Python in `apparatus/sanity/` | `python3 -I -B apparatus/sanity/test_launch.py`. For shared session or evidence helpers, also run the C10 checks above. The affected launcher needs its retained Linux rehearsal before qualification; source changes invalidate its previous rehearsal binding for live use. |
| `apparatus/claude-code/` | `python3 -I -B apparatus/claude-code/test_pin.py`, `python3 -I -B apparatus/claude-code/test_profile.py`, `python3 -I -B apparatus/claude-code/test_probe.py` and `python3 -I -B apparatus/claude-code/test_protocol.py`, on the native host where process-group observation is permitted. These are offline controls and invoke no Claude process. The protocol check compiles a separate Rust prototype using the existing locked crate and native toolchain; Cargo runs offline. Any real harness invocation needs bounded authority. Native results establish no Linux qualification. |
| Shell scripts in `apparatus/` or `apparatus/container/` | `sh -n` on each changed script. The change is unqualified until the next container run of the suite that uses it, which the user schedules and batches; it can land and be pushed once `sh -n` passes. `step2.sh` runs `container/inner-build.sh` and `acceptance.sh` the `acceptance-inner-` scripts. |
| `apparatus/check-build-markers.sh`, `apparatus/test_build_markers.py` or `apparatus/claude-code-markers.txt` | `sh -n apparatus/check-build-markers.sh` and `python3 -I -B apparatus/test_build_markers.py`; run the marker check against release-profile release/test/development binaries, with expected absence/absence/presence. Linux qualification needs the next container acceptance run. |
| `apparatus/check_links.py` | `python3 -I -B apparatus/check_links.py --self-test`, then the link check. |
| `apparatus/qualified.py` | `python3 -I -B apparatus/qualified.py --self-test`, then `python3 -I -B apparatus/qualified.py check`. |
| `service/Cargo.toml`, `service/Cargo.lock`, the vendored crates or `apparatus/container/Containerfile` | The user's run of `step2.sh`, which rebuilds the toolchain images, vendors the crates named by the committed `Cargo.lock` into `service/vendor`, and builds and checks the release binary for both architectures. It refuses while `service/vendor` exists, so the old tree has to be moved out of the way first. Then all three cargo configurations, and the next container run of `acceptance.sh`. The change is unqualified until those container runs, which the user schedules and batches; it can land and be pushed once all three configurations pass, which after a dependency change needs the tree that `step2.sh` vendors. |

`apparatus/qualified.py` keeps the qualification record ([Evidence and
retention](#evidence-and-retention)). After a container run of `acceptance.sh`
or `step2.sh`, record it with
`python3 -I -B apparatus/qualified.py extract .scratch/<run> --suite acceptance`
(`--suite toolchain` for `step2.sh`) and commit `apparatus/qualified.json` and
`apparatus/qualified.md` together.
Before citing the record, run `python3 -I -B apparatus/qualified.py check`.

## Layout

- `service/src/`: the service. The crate documentation in `service/src/lib.rs`
  maps its modules.
- `service/tests/`: integration tests. Most run the real binary from an
  unrelated working directory; the auditor-tool tests drive the tools in
  process against an audit the real binary commissioned. Each test has its own
  fresh temporary directory.
- `service/Cargo.toml`, `service/Cargo.lock`, `service/.cargo/config.toml`:
  the pinned dependencies and the vendored-source replacement.
- `apparatus/step2.sh`, `apparatus/acceptance.sh`: the host scripts that run
  the container suites.
- `apparatus/container/`: the toolchain `Containerfile` and the scripts that
  run inside the containers.
- `apparatus/driver/`: the independent driver and its fake provider.
- `apparatus/check_links.py`: the link check for the repository's Markdown.
- `apparatus/qualified.json`: the qualification record of what the container
  suites have shown. `apparatus/qualified.py` keeps it and generates
  `apparatus/qualified.md` from it.

## Toolchain and dependencies

The toolchain images `stewart-toolchain:1-arm64` and `stewart-toolchain:1-amd64`
are built by `apparatus/step2.sh` from
[`apparatus/container/Containerfile`](../apparatus/container/Containerfile): the
Rust image pinned by digest, plus the native musl target and the musl C
toolchain (`ring` compiles C and assembly for the target). The target and the
musl packages are fetched when the image is built, so a built image's digest is
the actual pin. `step2.sh` records each image's inspection, and every other
suite records the inspection of the images it used. Inside the image,
`/toolchain-versions.txt` lists the compiler, Cargo, the installed targets and
the musl package versions, and every container build keeps a copy of it.

Release binaries are built for `aarch64-unknown-linux-musl` and
`x86_64-unknown-linux-musl`, each in its own architecture's image. A glibc build
for `<arch>-unknown-linux-gnu` exists only as the firing control for the static
check, which must reject it.

The release profile in `service/Cargo.toml` uses one codegen unit, fat LTO,
`panic = "abort"` and stripped symbols. Fat LTO has one known hazard, described
in the crate documentation in `service/src/lib.rs`: in the static musl release
build, a call through `libc::` to a function that std also declares weak can
link to nothing, and debug, thin-LTO and macOS builds never show it. Such calls
go through `libc::syscall`, as `platform::random_fill` does.

The dependencies are six crates pinned to exact versions in
`service/Cargo.toml` (`libc`, `sha2`, `rustls` with its `ring` provider,
`webpki-roots`, `secrecy` and `zeroize`), and `service/Cargo.lock` pins the whole graph. Builds never
reach crates.io: `service/.cargo/config.toml` replaces it with the vendored
sources in `service/vendor`, and every build here passes `--locked --offline`.

`service/vendor` is not tracked (`service/.gitignore`), so a new clone or
worktree has none. `step2.sh` produces it: with network access, it runs
`cargo vendor --locked --versioned-dirs` in the arm64 toolchain image against a
`git archive` of `HEAD`, records the SHA-256 of every vendored file in its
evidence (`host/vendor.sha256`) and copies the tree into `service/vendor`. It
refuses to start while `service/vendor` exists; after a `Cargo.lock` change the
vendored tree has to be produced again from the new lock. The other suites
record the digests of the vendored files they mount.

Run Cargo from `service/`. Cargo looks for `.cargo/config.toml` from its working
directory upward, so `--manifest-path service/Cargo.toml` from the repository
root misses the source replacement, and an offline build cannot resolve the
crates.

## Building and testing natively

On the development Mac (Apple silicon) the crate builds and tests with a native
Rust toolchain and the vendored crates. The Linux-only calls are gathered in
`service/src/platform.rs`, whose module documentation lists each one beside its
macOS fallback: `flock` for the OFD lock, `st_birthtime` for `statx`,
`getentropy` for `getrandom`, no process start time, and so on. The fallbacks
make the macOS build target work; they are not supported behavior.

```sh
cd service
cargo test --locked --offline
CARGO_TARGET_DIR=target-test cargo test --locked --offline --features fault-injection,sabotage
```

The first run tests release behavior. The second compiles the test-only code of
INTERFACE Appendix C: `fault-injection` adds the failure points and the
test-only TLS root, provider timeout and retry delays, and `sabotage` adds the
controls that each break exactly one property. The test files for them
(`faults.rs`, `sabotage.rs` and their `answer_` and `close_` counterparts) run
only in that configuration. Fault and sabotage settings are read once per
process, so some checks are ignored tests that a runner test executes in a
child process of its own with the setting it needs; an ordinary run lists them
as ignored. The separate target folder keeps the two configurations from
rebuilding over each other.

The tests take their scratch space from the system temporary directory, or
from `STEWART_IT_TMP` when it is set. On Linux the archive must be on ext4, xfs
or btrfs, so point `STEWART_IT_TMP` at such a directory when `/tmp` is tmpfs or
overlayfs. The container suites build the crate but run the driver, not these
tests.

The driver below takes a release binary and a test build:

```sh
cd service
cargo build --locked --offline --release
CARGO_TARGET_DIR=target-test cargo build --locked --offline --release --features fault-injection,sabotage
```

These leave the release binary at `service/target/release/stewart` and the test
build at `service/target-test/release/stewart`. The test build needs its own
target folder; built into the same one, it would replace the release binary.
By Appendix C the release binary contains neither feature's code nor the six
test-only environment variable names; `acceptance.sh` checks the names, with
the test build as the firing control.

## The independent driver

[`apparatus/driver/`](../apparatus/driver) is the black-box acceptance driver,
written in Python with the standard library only; `stewart_driver.py` is its
entry point. Its author writes it from INTERFACE, QUESTION-FORMS, CONTRACTS and
ACCEPTANCE and does not read `service/`, and the service is written from the
same specification, not from the driver. Keeping the two apart means a
misreading of the specification has to be made twice, independently, to pass
unnoticed. Resolve disagreements against the specification: clarify an unclear
contract in its text, or correct the implementation that misreads it.

The driver uses the two binaries only through their command line. It serves a
fake Messages API on loopback, runs a reacting fake auditor, and keeps its own
witness of everything it supplies outside Stewart's archive.

Run it with an explicit interpreter and isolated startup (`-I -B`); the entry
point puts its own directory on `sys.path`:

```sh
python3 -I -B apparatus/driver/stewart_driver.py --list
python3 -I -B apparatus/driver/stewart_driver.py --self-test
python3 -I -B apparatus/driver/stewart_driver.py \
    --binary /abs/stewart --test-binary /abs/stewart-test \
    --evidence /abs/new-folder [--case 'c17.*'] [--exclude 'close.*'] [--skip-heavy]
```

`--list` prints the case inventory. `--self-test` checks the driver's own
helpers without a binary, including its rendering, answer and manifest
witnesses against the examples in `docs/QUESTION-FORMS.md` and
`docs/INTERFACE.md`, byte for byte. A run against binaries needs an evidence
folder that does not exist yet, and a work directory (`--work`, default the
system temporary directory) outside the repository. Its exit status is 0 only
when no case failed and every control fired.

Run natively on the development Mac, the driver is for iteration. Cases with
Linux-only expectations (the OFD lock, `/proc` observations, the archive
filesystem allowlist, byte-string names) are skipped with their reason, as are
cases needing the fake provider where loopback listening is not permitted, and
the timing gate is off unless `--timing-gate on` is given.
[apparatus/README.md](../apparatus/README.md) describes the driver's modules,
cases, controls and evidence in detail.

The [standalone Claude Code driver](../apparatus/driver/CLAUDE-CODE.md) exercises
the gated adapter with a synthetic executable and MCP traffic. Its self-test,
case list and runtime cases are separate from `stewart_driver.py`; they make no
real-Claude or provider calls. Native runs need host Unix sockets and process
observation. The container suite below runs this driver against the gated binary
on both architectures, separately from the release driver. It also supplies a
second gated build with a different digest for the profile/writer comparison.

## Container suites

The suites run under Apple `container` 1.6.1 on the development Mac and need it
on the host. An agent whose shell is sandboxed cannot reach it, so the agent
prepares the command and the user runs it. Each script checks the version and
that the container services are running, and stops otherwise. `acceptance.sh`
also needs the toolchain images and `service/vendor` from
`step2.sh`. The network is used only to pull pinned images, build the toolchain
images and vendor crates; every build and driver run is offline
(`--network none`). Build containers are removed on exit. Acceptance driver
containers remain until evidence review; their names are recorded in
`host/driver-<arch>.container`. Nothing on the host is deleted.

Each script takes one required argument, its evidence folder, and refuses one
that exists; give a new folder directly under `.scratch/` as an absolute path.
Without the argument a script prints its usage and exits 2 before doing
anything else. For example, from the repository root:

```sh
sh apparatus/acceptance.sh "$PWD/.scratch/acceptance-NN"   # NN not yet used
```

Each script builds from a `git archive` of `HEAD` and records the commit, so it
sees only committed files; uncommitted changes under the archived paths are
noted, not used. Commit the work before running a suite. A suite run from
another checkout uses that checkout's own `service/vendor`.

- `step2.sh` builds the two toolchain images and `service/vendor`, then builds
  the release binary twice per architecture in fresh containers, compares the
  two builds byte for byte, checks that the binary is static, runs it in its
  toolchain image, and runs `stewart help` in the pinned alpine image.
- `acceptance.sh` runs the whole scripted tier of ACCEPTANCE. Per architecture
  it builds the release binary, the test build, a development build and a glibc
  control, and checks that all three musl binaries are static and the glibc
  control is not, that `cmp` tells the release and test binaries apart, and that
  only the test build contains the six test-only variable names. The adapter
  marker list must be absent from release/test and present in development.
  Then, in the pinned python image
  with no network and as an unprivileged user, it runs the driver's self-test
  and every case with `--network-isolated --require-all-controls --keep-work all`, so every
  sabotage control of Appendix C.2 must be assigned to a case and fire.
  In the same isolated container it runs the standalone runtime driver's
  self-test and every synthetic case, using the development, release and second
  development binaries. Qualification requires no skipped or unselected runtime
  cases and all controls firing. Runtime witnesses and results are exported
  separately from the release driver's evidence.

Each writes `host/DONE` with `failures=N`; `acceptance.sh` also writes
`host/SUMMARY` with the driver's counts per architecture, and
`acceptance.sh` adds the self-test's summary line.
[apparatus/README.md](../apparatus/README.md) gives each script's steps and
evidence layout. `apparatus/qualified.py extract` reads a run of `acceptance.sh`
or `step2.sh` into the qualification record ([Evidence and
retention](#evidence-and-retention)).

Qualification evidence comes from a Linux container suite and, under ACCEPTANCE
("Platforms"), from the scripted tier run natively on WSL2 from a handoff
package of the same binary, driver and fake provider; these scripts cover the
Linux containers only. Native runs on a development machine such as the Mac are
development checks, not qualification evidence. On the development Mac the x86_64 containers run under Rosetta
emulation: their timings are reported but do not gate (ACCEPTANCE C9), and the
driver records Rosetta's own cache under the home as an emulator artifact rather
than a write by Stewart.

Every suite uses the fake provider. The real-model conformance tier of
ACCEPTANCE needs its own apparatus, and a model-consuming run needs the user's
explicit permission, with its models and budget named.

## Evidence and retention

The working repository serves one agent/human team building, testing and
evaluating the current application. Keep source, specifications, test fixtures
and generators, the lockfile and one vendored dependency tree. Build caches,
staging copies, local checks and synthetic test work are disposable. Use `.tmp/`
for routine check output; overwrite or remove it once consumed. A command log is
not an archival deliverable.

Container suites and live studies initially use `.scratch/<run>/`. New runs use
new folders so a failed attempt cannot overwrite evidence still under review.
Neither `.tmp/` nor `.scratch/` travels with Git. The manager supplies backups
for any selected original evidence that cannot be reproduced.

### Current test evidence

[`qualified.py`](../apparatus/qualified.py) maintains
[`qualified.json`](../apparatus/qualified.json) and its generated Markdown. For
each suite/platform keep the latest result and, if it failed, the last qualified
result. `check` verifies retained results and reports source drift. A result
applies to its recorded binary and source, not automatically to later code.

During review keep the independent witness, actual command outputs, counts,
failures, skips, environment and binary/image identities. Controls must fire;
missing evidence and failed comparisons cannot be reported as passes. For
missing-capture, extraction or deletion investigations keep the witness outside
the operation under test, together with the original affected material, until
review resolves what happened.

The acceptance driver normally uses `--keep-work failed`: successful cases and
firing controls release their synthetic working trees. The suite exports
independent evidence and, on failure, the remaining work. Pass `all` as the
second argument to `apparatus/acceptance.sh` only for an investigation needing
all original work. Export failure retains the container and fails the suite.
After review remove the container and bulky generated files no longer needed;
keep the concise result and any specifically selected failure evidence. A fixed
reproducible defect belongs in a regression test, not an indefinite old run.

### Selected evaluations

Archive originals only when they have a present inspection purpose and would
be costly or impossible to reproduce. A particular model encounter or human
reading cannot be reproduced by another invocation. Retain the question and
inputs, effective arrangement, original response/answer, relevant custody and
usage records, and the attributed assessment needed to inspect the finding.
Keep unresolved limits visible. A paid call alone is not a reason to retain it.
Old synthetic environments are not needed merely to read a completed encounter.

Use explicit pins in the existing qualification index for selected evaluations
and inputs; state their current purpose and release condition. Citations are
navigation and do not preserve entire folders. `qualified.py candidates` lists
unselected folders without deleting them; resolve missing-record warnings before
acting. A pin protects its named original result, not unrelated caches or
preparation logs beside it. Preserve exact original records that remain; revise
the maintained interpretation or retention scope rather than historical bytes.

Routine disposal under these rules is part of maintaining the repository, not a
new approval procedure. Do not discard unfinished product custody, an archive
still needed for an active audit, or its exact writer. Finish or explicitly
dispose of that undertaking first. Retire temporary worktrees when their task
ends; ordinary Git history retains source without additional working copies.
