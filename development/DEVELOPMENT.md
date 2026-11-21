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
containers. Develop in the dedicated Linux guest. The guest setup covers the
accounts, rootless container storage and Git transport. [Provisioning and access](../apparatus/lima/README.md)

## What to run for what you changed

Find each kind of change you made in the table and run what its row names, from
the repository root unless it says otherwise. A change can land and be pushed
once its development checks pass. Native runs are for iteration. Each
container suite builds from `git archive` of `HEAD`, so commit the source
before running it. See [Container suites](#container-suites) for host access
and commands.

When a specification changes pinned bytes or behavior, update the affected
implementation and independent witnesses and apply their check rows too. A
change whose correctness depends on how a real model, provider or harness
behaves may also warrant a [live test](LIVE-TESTING.md). A live test adds to a
row's checks and replaces none. The
[driver authorship rule](../AGENTS.md#preserve-independent-evidence) applies.

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
CARGO_TARGET_DIR=target-test cargo test --locked --offline --features fault-injection,sabotage --lib --test faults --test answer_faults --test close_faults --test run_faults
```

For adapter code and shared behavior the adapter uses, run the development
configurations from `service/`:

```sh
CARGO_TARGET_DIR=target-local cargo test --locked --offline --features claude-code
CARGO_TARGET_DIR=target-runtime-fault cargo test --locked --offline --features claude-code,fault-injection --test claude_code faults::
```

The first also runs the release tests, because the development build compiles
shared code differently. The second runs the adapter's cases at failure points.
Some runtime tests start a placement whose fake harness connects through a
private Unix socket, so run both where binding a Unix socket is permitted; a
sandbox that denies the bind fails those tests.

| What changed | What to run |
| --- | --- |
| Prose or Markdown anywhere | The link check. |
| `docs/QUESTION-FORMS.md` | The link check and release driver's self-test. From `service/`, run `cargo test --locked --offline --lib forms::tests::` for the family tables, tool descriptions and pinned texts. |
| `docs/INTERFACE.md` | The link check and release driver's self-test, which checks the worked manifest. For changes to Appendix C, also run `CARGO_TARGET_DIR=target-test cargo test --locked --offline --features fault-injection,sabotage --lib fault::tests::` from `service/` to compare the test-build registries with the specification. |
| Worked example materials: `question.md` and `materials/` under `examples/questions/*/submission/` | From `service/`, run `cargo test --locked --offline --test manager worked_question_packets_prepare_with_full_or_limited_evidence`. This prepares each ordinary and inadequate-evidence packet and checks its selected bytes. The walkthroughs, `CITATION-CONTROLS.md`, QUESTION-FORMS and INTERFACE cite their sizes, byte ranges and line numbers, and the driver's answer witness pins the examples in those docs, so recheck every citation of a changed file. Apply the corresponding specification row to changed examples. |
| `CONTRACTS.md`, `DESIGN.md` or `ACCEPTANCE.md` | The link check. |
| Release-only service code or tests | Run default Cargo tests and `fault-injection,sabotage`. Qualify changed release behavior with `acceptance.sh`. |
| Development-adapter-only code or tests | Run the two development Cargo configurations and `runtime-acceptance.sh` for the changed runtime behavior. |
| Code, tests or dependencies shared by the released service and development adapter | Run the release and adapter Cargo commands above. Each affected suite records its own verdict. |
| Release driver and shared helpers in `apparatus/driver/` | `stewart_driver.py --self-test` and `--list`, which loads every release case module. Shared helpers used by the standalone runtime driver also need that driver's checks below. Helpers the C10 and sanity apparatus import (their `SOURCE_PATHS` in `apparatus/c10/common.py`) also need the `apparatus/c10/` checks, and their live use then needs a new rehearsal. Qualify the changed release driver with the `acceptance.sh` container suite. Edit only under the driver-independence rule in [AGENTS.md](../AGENTS.md). |
| `apparatus/driver/claude_code.py` or its `CLAUDE-CODE.md` | `python3 -I -B apparatus/driver/claude_code.py --self-test` and `--list`, and `stewart_driver.py --list`, because a release case imports this module's transport decoder. Runtime behavior changes also need the affected cases against a `claude-code` build, with a featureless release as `--release-binary` and a release-profile `claude-code,fault-injection` build as `--variant-binary`; keep their witnesses as [the driver guide](../apparatus/driver/CLAUDE-CODE.md) describes. The real-harness fixtures and controllers import this module, so also run the next row's offline checks. Linux qualification uses `runtime-acceptance.sh` on both architectures. |
| `apparatus/claude-code/`, or the real-harness fixtures `apparatus/driver/claude_code_{surface,observer,peer,service_witness}.py` and their `CLAUDE-CODE-*.md` guides | Offline checks: each fixture module's `--self-test`, and `python3 -I -B apparatus/claude-code/test_NAME.py` for `pin`, `profile`, `bounded`, `surface_check` and `service_check`. When the change reaches the surface fixture, observer, peer, launcher or supplied-surface controller, also run that controller's `prepare-rehearsal` and frozen `run-rehearsal` for `normal`, `bad-init` and `wrong-auth` with the gated binary, as in [the controller guide](../apparatus/claude-code/README.md#synthetic-controller-rehearsal): `normal` must be observed; `bad-init` must stop at startup and `wrong-auth` at authentication, with no fixture effect and every later slot unstarted. When it reaches the service procedure or the package witness, run that procedure's `prepare-rehearsal` and the positive packet's frozen `rehearse` from [the procedure guide](../apparatus/claude-code/README.md#service-comparison-procedure), and review its six comparisons and package reviews. For witnessed interruption, continuation or manager-close changes also run the five [synthetic trigger comparisons](../apparatus/claude-code/README.md#commissioned-runtime-trials) with the same writer. Run these checks in the Linux guest with synthetic peers and credentials. |
| Runtime schemas or pinned texts in `docs/claude-code/CONTRACT.md` | The link check, the `claude-code` Cargo configuration, and the standalone runtime driver's self-test and list. Update exact service/driver copies when their pinned bytes change, preserving independent authorship. Prose-only status changes need the link check. |
| `alignment/messages/` | Run `python3 -I -B alignment/messages/test_alignment.py`. Compare the original export and attempt digests when the inventory changes. Check proposed reservations using the protected launcher and its qualified-writer rehearsal before commissioning. |
| `apparatus/c10/` | `python3 -I -B apparatus/c10/test_c10.py`, `python3 -I -B apparatus/c10/test_placements.py` and `python3 -I -B apparatus/sanity/test_launch.py`. Exercise changed run, reviewer and operator behavior with the native fake-provider commands in [the apparatus instructions](../apparatus/c10/README.md#run-the-offline-checks). Qualify the committed change with a retained Linux `c10.py rehearse` run; any source change invalidates earlier rehearsal bindings for live use. No model calls are needed for these checks. |
| Python in `apparatus/sanity/` | `python3 -I -B apparatus/sanity/test_launch.py`, and the `apparatus/c10/` checks above for the files C10 imports. The C10 rehearsal qualifies those files. Run the sanity launcher's retained Linux rehearsal only when its own launch path changes or before its next live use; any change under `apparatus/sanity/` invalidates its previous rehearsal binding for live use. |
| Shell scripts in `apparatus/` or `apparatus/container/` | `sh -n` on each changed script. Qualify the change with a passing container run of the suite that uses it. `step2.sh` runs `container/inner-build.sh` and `acceptance.sh` runs the release driver. `runtime-acceptance.sh` runs the runtime driver. Changes to shared suite helpers require both suites. |
| `apparatus/check-build-markers.sh`, `apparatus/test_build_markers.py` or `apparatus/claude-code-markers.txt` | `sh -n apparatus/check-build-markers.sh` and `python3 -I -B apparatus/test_build_markers.py`; run the marker check against release-profile release and development binaries, expecting absence and presence. Qualify with `runtime-acceptance.sh`. |
| `apparatus/check_links.py` | `python3 -I -B apparatus/check_links.py --self-test`, then the link check. |
| `apparatus/qualified.py` | `TMPDIR=/var/lib/stewart/fixtures/fold/work python3 -I -B apparatus/qualified.py --self-test` exercises the case-alias control, then run `python3 -I -B apparatus/qualified.py check`. |
| `service/Cargo.toml`, `service/Cargo.lock`, the vendored crates or `apparatus/container/Containerfile` | Run `step2.sh` to rebuild the toolchain images, vendor the crates named by the committed `Cargo.lock` into `service/vendor`, and build and check the release binary for both architectures. It refuses while `service/vendor` exists, so move the old tree aside first. Run the release and adapter Cargo checks above with the resulting vendor tree. Qualification requires the toolchain, release and runtime container suites to pass. |

`apparatus/qualified.py` keeps the qualification record ([Evidence and
retention](#evidence-and-retention)). After a container run, record it with
`python3 -I -B apparatus/qualified.py extract .scratch/<run> --suite acceptance`
(`--suite toolchain` for `step2.sh`, `--suite runtime` for `runtime-acceptance.sh`) and commit `apparatus/qualified.json` and
`apparatus/qualified.md` together.
Before citing the record, run `python3 -I -B apparatus/qualified.py check`.

## Layout

- `service/src/`: the service. The [crate guide](../service/README.md) and the
  crate documentation in `service/src/lib.rs` map its modules.
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
- `apparatus/driver/`: the independent drivers: the release driver with its
  fake provider, the standalone development-runtime driver with its synthetic
  harness, and the independent fixtures for real-harness checks.
- `apparatus/check_links.py`: the link check for the repository's Markdown.
- `apparatus/qualified.json`: the qualification record of what the container
  suites have shown. `apparatus/qualified.py` keeps it and generates
  `apparatus/qualified.md` from it.
- `apparatus/c10/`, `apparatus/sanity/`, `apparatus/testdata/acceptance/`: the
  live Messages commission apparatus and its captured inputs.
- `apparatus/claude-code/`: installation pinning, runtime profiles and the
  bounded real-harness checks.
- `docs/`: the interface and question forms; `docs/claude-code/` holds the
  development runtime's contract.
- `examples/questions/`: worked submissions and walkthroughs for each family.
- `development/`: this guide, [live testing](LIVE-TESTING.md), the record of
  [unresolved operations](UNRESOLVED-OPERATIONS.md) and long-term plans.

To fix the distributed binary, `service/`, `docs/`, the release driver and these
guides suffice; the development runtime adds its contract under
`docs/claude-code/` and the standalone runtime driver.

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
`x86_64-unknown-linux-musl`, each in its own architecture's image. The release suite compiles a small dynamically linked C
executable on each architecture as the firing control for its static-link check.

The release profile in `service/Cargo.toml` uses one codegen unit, fat LTO,
`panic = "abort"` and stripped symbols. Fat LTO has one known hazard, described
in the crate documentation in `service/src/lib.rs`: in the static musl release
build, a call through `libc::` to a function that std also declares weak can
link to nothing, and debug and thin-LTO builds can mask this defect. Such calls
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

Without the container route, on a networked host with a Rust toolchain, the
command `step2.sh` runs produces the tree from `service/`:
`cargo vendor --locked --versioned-dirs vendor`. Compare its file digests with a
`step2.sh` run's `host/vendor.sha256` before treating it as the same tree.

Run Cargo from `service/`. Cargo looks for `.cargo/config.toml` from its working
directory upward, so `--manifest-path service/Cargo.toml` from the repository
root misses the source replacement, and an offline build cannot resolve the
crates.

## Building and testing natively

Run Cargo in `service/` as the development user with the pinned Rust toolchain
and vendored crates. Use a private directory on guest ext4 for test archives,
for example `export STEWART_IT_TMP=/var/lib/stewart/dev-tmp`. The guest also
provides `/var/lib/stewart/fixtures/fold/work` for the case-alias test.

The [release and fault/sabotage configurations](#what-to-run-for-what-you-changed)
differ in what they compile and run. The first runs every unit and integration
test against release behavior. The second compiles the test-only code of
INTERFACE Appendix C: `fault-injection` adds the failure points and the
test-only TLS root, provider timeout and retry delays, and `sabotage` adds the
controls that each break exactly one property. It runs the unit tests and the
integration targets gated on `fault-injection`; a new target that needs a test
feature joins that list. Rerunning the other targets there would repeat the
first run with the hooks unarmed, which the release driver's test-binary
baseline establishes for the built binary. Native tests exercise the fault
points the driver does not reach; only the driver exercises the sabotage
controls, each paired with a passing test-build baseline. Fault settings are
read once per process, so the runner in `answer_faults.rs` executes each ignored
helper in a child process with its own setting. The separate target folder
keeps the two configurations from rebuilding over each other.

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
python3 -I -B apparatus/driver/stewart_driver.py --list [--describe]
python3 -I -B apparatus/driver/stewart_driver.py --self-test
python3 -I -B apparatus/driver/stewart_driver.py \
    --binary /abs/stewart --test-binary /abs/stewart-test \
    --evidence /abs/new-folder [--case 'c17.*'] [--exclude 'close.*'] [--skip-heavy]
```

`--list` prints the case inventory with each case's claims, controls and
failure points; `--describe` adds each case's description. `--skip-heavy` skips
the slowest cases while iterating. `--self-test` checks the driver's own
helpers without a binary, including its rendering, answer and manifest
witnesses against the examples in `docs/QUESTION-FORMS.md` and
`docs/INTERFACE.md`, byte for byte. A run against binaries needs an evidence
folder that does not exist yet, and a work directory (`--work`, default the
system temporary directory) outside the repository. Its exit status is 0 only
when no case failed and every control fired.

Run the driver in the guest for iteration. Cases that depend on a distinct
filesystem or a loopback listener report missing prerequisites. Full Linux
qualification requires the exercised cases and their firing controls.
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

Run the suites from the Linux development login with rootless Podman 5 and
cgroup v2. Both driver suites
need the toolchain images and `service/vendor` from
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
- `acceptance.sh` builds the release and fault/sabotage writers and a small
  dynamic ELF control for each architecture. It checks static linkage, then
  runs the independent release driver with its loopback fake provider,
  unprivileged, in the pinned Python image. The per-run archive resides on a named ext4-backed volume. The UTF-8
  filename-bound source uses the guest VFAT fixture.
- `runtime-acceptance.sh` builds a featureless release and two distinct
  development writers, checks that the adapter markers are absent from the
  release and present in both writers, and runs the independent synthetic
  runtime driver. Each architecture must complete its full case and control
  inventory. The suite retains its witnesses and working archive.

Both driver suites record the committed source, per-platform outputs, binary
digests, self-tests, counts and final verdict in separate evidence folders.
[The apparatus guide](../apparatus/README.md) describes the outputs. The release and runtime suites
qualify their respective Linux binaries. The aarch64 guest runs arm64 containers
natively and amd64 containers through Rosetta. Both userlands exercise the same
kernel for OFD locks, `/proc` and process protection.

The container suites use the fake provider. Endpoint alignment uses its own
apparatus and requires explicit authorization for the models and budget used.

## Evidence and retention

The working repository serves one agent/human team building, testing and
evaluating the current application. Keep source, specifications, test fixtures
and generators, the lockfile and one vendored dependency tree. Build caches,
staging copies, local checks and synthetic test work are disposable. Use `.tmp/`
for routine check output; overwrite or remove it once consumed. A command log is
not an archival deliverable.

Container suites and live studies initially use `.scratch/<run>/`. New runs use
new folders so a failed attempt cannot overwrite evidence still under review.
Neither `.tmp/` nor `.scratch/` travels with Git. Back up selected irreplaceable
originals to an authorized destination. If none is available, retain the
originals locally and report the missing backup.

### Current test evidence

[`qualified.py`](../apparatus/qualified.py) maintains
[`qualified.json`](../apparatus/qualified.json) and its generated Markdown. For
each suite/platform keep the latest result and, if it failed, the last qualified
result. `check` verifies retained results, checks that the front release and
runtime runs used the toolchain images the latest toolchain run recorded, and
reports source drift. A result
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

A study can finish with an account of what it tested, what happened and what
its evidence could establish. Its implications for work on Stewart may go
unexamined. For a retained encounter, describe the question, conditions and
observation in the existing index entry so someone can find it by what happened.

When a finding bears on a current decision, put it where someone will make
that decision. A repeatable failure belongs in a regression test, a useful way
to read a return in the reader's guide, and a narrowed uncertainty in the
existing question or plan. Include the conditions that matter and point to the
exact capture or attributed review.

When a later question gives an older observation a use, locate it through the
[qualification index](../apparatus/qualified.md) and check the original before
drawing the new conclusion.

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

Clear disposable evidence when its inspection purpose ends. Preserve material
under unresolved custody, including an open audit's archive and exact writer.
Retire temporary worktrees when their task ends. Ordinary Git history retains
the source.
