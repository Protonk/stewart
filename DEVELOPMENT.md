# Building and testing Stewart

Stewart is the Rust audit service in [`service/`](service): one crate, binary
`stewart`. [`apparatus/`](apparatus) holds what builds and tests it: pinned
Linux toolchain images, container scripts and an independent acceptance driver
with a fake provider. The apparatus does not ship. What to build and what
evidence is owed are in [DESIGN.md](DESIGN.md),
[CONTRACTS.md](CONTRACTS.md), [ACCEPTANCE.md](ACCEPTANCE.md) and
[docs/INTERFACE.md](docs/INTERFACE.md); [AGENTS.md](AGENTS.md) states the
development rules.

The product is one statically linked binary for Linux x86_64 and aarch64
(CONTRACTS, "Platform and auditor access"), built and qualified in Linux
containers. Native macOS is not a target. The crate builds and tests on the
development Mac so that work can iterate quickly there, but nothing run natively
on a development machine counts as evidence.

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

Both cargo configurations, from `service/` ([Building and testing
natively](#building-and-testing-natively)):

```sh
cargo test --locked --offline
CARGO_TARGET_DIR=target-test cargo test --locked --offline --features fault-injection,sabotage
```

| What changed | What to run |
| --- | --- |
| Prose or Markdown anywhere | The link check. |
| `docs/INTERFACE.md` or `docs/QUESTION-FORMS.md` | The link check, both cargo configurations and the driver's self-test. A test in `service/src/forms.rs` compares the service's pinned texts and tool descriptions with QUESTION-FORMS; one in `service/src/fault.rs`, built only in the fault and sabotage configuration, compares its failure points, actions and sabotage controls, and the names in its variable table, with INTERFACE Appendix C. The driver's self-test compares its own copies of the pinned texts and tool descriptions with QUESTION-FORMS, and its answer witness reproduces the structured answer and rendering examples of QUESTION-FORMS and the manifest example of INTERFACE 8.2 byte for byte. A changed pinned text or tool description needs the service's copy changed too (then the `service/` row applies); a changed pinned text or example needs the driver's copy updated, under the driver-independence rule in [AGENTS.md](AGENTS.md). |
| Worked example materials: `question.md` and `materials/` under `examples/questions/*/submission/` | No check reads them. The walkthroughs, `CITATION-CONTROLS.md`, QUESTION-FORMS and INTERFACE cite their sizes, byte ranges and line numbers, and the driver's answer witness pins the examples in those docs, so recheck every citation of a changed file; a changed example in the docs then needs the row above. |
| `CONTRACTS.md`, `DESIGN.md` or `ACCEPTANCE.md` | The link check. Changing what Stewart promises is the user's decision. |
| `service/src/` or `service/tests/` | Both cargo configurations. A behavior change is unqualified until the next container run of `acceptance.sh`, which the user schedules and batches; it can land and be pushed once both configurations pass. |
| `apparatus/driver/` | The driver's self-test and `--list`, which loads every case module. The change is unqualified until the next container run of `acceptance.sh`, which the user schedules and batches; it can land and be pushed once those two pass. Edit the driver only under the driver-independence rule in [AGENTS.md](AGENTS.md). |
| Shell scripts in `apparatus/` or `apparatus/container/` | `sh -n` on each changed script. The change is unqualified until the next container run of the suite that uses it, which the user schedules and batches; it can land and be pushed once `sh -n` passes. `step2.sh` runs `container/inner-build.sh` and `acceptance.sh` the `acceptance-inner-` scripts. |
| `apparatus/check_links.py` | `python3 -I -B apparatus/check_links.py --self-test`, then the link check. |
| `apparatus/qualified.py` | `python3 -I -B apparatus/qualified.py --self-test`, then `python3 -I -B apparatus/qualified.py check`. |
| `service/Cargo.toml`, `service/Cargo.lock`, the vendored crates or `apparatus/container/Containerfile` | The user's run of `step2.sh`, which rebuilds the toolchain images, vendors the crates named by the committed `Cargo.lock` into `service/vendor`, and builds and checks the release binary for both architectures. It refuses while `service/vendor` exists, so the old tree has to be moved out of the way first. Then both cargo configurations, and the next container run of `acceptance.sh`. The change is unqualified until those container runs, which the user schedules and batches; it can land and be pushed once both cargo configurations pass, which after a dependency change needs the tree that `step2.sh` vendors. |

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
[`apparatus/container/Containerfile`](apparatus/container/Containerfile): the
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

The dependencies are four crates pinned to exact versions in
`service/Cargo.toml` (`libc`, `sha2`, `rustls` with its `ring` provider, and
`webpki-roots`), and `service/Cargo.lock` pins the whole graph. Builds never
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
exist only for development; they are not supported behavior.

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

[`apparatus/driver/`](apparatus/driver) is the black-box acceptance driver,
written in Python with the standard library only; `stewart_driver.py` is its
entry point. Its author writes it from INTERFACE, QUESTION-FORMS, CONTRACTS and
ACCEPTANCE and does not read `service/`, and the service is written from the
same specification, not from the driver. Keeping the two apart means a
misreading of the specification has to be made twice, independently, to pass
unnoticed. Disagreements between them have been settled against the
specification: an unclear point was clarified in its text, which both then
follow, and a misreading was corrected on the side that made it.

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
[apparatus/README.md](apparatus/README.md) describes the driver's modules,
cases, controls and evidence in detail.

## Container suites

The suites run under Apple `container` 1.6.1 on the development Mac and need it
on the host. An agent whose shell is sandboxed cannot reach it, so the agent
prepares the command and the user runs it. Each script checks the version and
that the container services are running, and stops otherwise. `acceptance.sh`
also needs the toolchain images and `service/vendor` from
`step2.sh`. The network is used only to pull pinned images, build the toolchain
images and vendor crates; every build and driver run is offline
(`--network none`) in a container removed on exit, and nothing on the host is
deleted.

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
  it builds the release binary, the test build and a glibc control, and checks
  that both musl binaries are static and the glibc control is not, that `cmp`
  tells the release and test binaries apart, and that only the test build
  contains the six test-only variable names. Then, in the pinned python image
  with no network and as an unprivileged user, it runs the driver's self-test
  and every case with `--network-isolated --require-all-controls`, so every
  sabotage control of Appendix C.2 must be assigned to a case and fire.

Each writes `host/DONE` with `failures=N`; `acceptance.sh` also writes
`host/SUMMARY` with the driver's counts per architecture, and
`acceptance.sh` adds the self-test's summary line.
[apparatus/README.md](apparatus/README.md) gives each script's steps and
evidence layout. `apparatus/qualified.py extract` reads a run of `acceptance.sh`
or `step2.sh` into the qualification record ([Evidence and
retention](#evidence-and-retention)).

Evidence comes from a Linux container suite and, under ACCEPTANCE
("Platforms"), from the scripted tier run natively on WSL2 from a handoff
package of the same binary, driver and fake provider; these scripts cover the
Linux containers only. Native runs on a development machine such as the Mac are
not evidence. On the development Mac the x86_64 containers run under Rosetta
emulation: their timings are reported but do not gate (ACCEPTANCE C9), and the
driver records Rosetta's own cache under the home as an emulator artifact rather
than a write by Stewart.

Every suite uses the fake provider. The real-model conformance tier of
ACCEPTANCE needs its own apparatus, and a model-consuming run needs the user's
explicit permission, with its models and budget named.

## Evidence and retention

Runs write their records under `.scratch/<run>/` in the repository: container
suite evidence, driver evidence folders, and the outputs of commands run by hand
for a study. `.scratch/` is ignored by Git, so records stay on the machine that
made them and do not travel with the repository.

The qualification record is the tracked account of what the suites have shown:
[`apparatus/qualified.json`](apparatus/qualified.json), with
[`apparatus/qualified.md`](apparatus/qualified.md) generated from it by
`apparatus/qualified.py`. Never edit the Markdown by hand. The script's
`extract` reads a run of `acceptance.sh` or `step2.sh` from its own evidence
and decides its outcome mechanically. For each suite and platform the record
keeps the latest run and, when that run did not qualify, the latest run that
did (the front). Any other record stays only while it is pinned, with a reason
and a condition for its release; Git history keeps the records that leave.
`check` fails when the Markdown differs from a fresh render, a source commit is
missing from the repository or a record no longer matches the evidence on this
machine, and it reports the changes under `service/` and `apparatus/` since
each front run's source commit.

- **A new attempt gets a new directory.** The suites take their evidence folder
  as a required argument, and the suites and the driver refuse an existing one;
  give each run its own name directly under `.scratch/`.
- **Run records are never rewritten.** A correction or reinterpretation goes in
  the document that cites the run, or into a new run.
- **Retention follows the record and citation.** An entry directly under
  `.scratch/` stays while it is on the front, pinned (`qualified.py pin`, or
  `pin --experiment` for evidence that is not a suite run), or cited as
  `.scratch/NAME`, in any letter case, by a tracked or untracked-but-not-ignored
  file outside `.scratch/` other than the record's own files.
  `qualified.py candidates` lists every entry with its size, marking each as
  kept, with its reasons, or as a removal candidate. It also keeps a folder
  that holds the digests a record entry recorded, so renaming an entry cannot
  expose its folder, and it exits 1 when an entry's folder is absent and no
  folder holds its digests, as on a machine without the evidence. Act only on a
  run that exits 0. Removal is by hand and the user's decision; no script
  removes records.

**Protected local records.** Keep these:

- The refs `refs/development-evidence/successor-inquiry-01/a1`, `a2` and `a3`,
  which keep three historical outcome commits reachable that no branch
  contains. Do not delete them; a main-only clone does not carry them.
- The 21 original product-audit source copies under `A1/` to `A3/` in
  `.scratch/successor-inquiry-01/answers/attempt-01/sources/`, and the records
  `history-reachability-01.json` and its correction
  `history-preservation-01.json` in `.scratch/successor-inquiry-01/`. Do not
  prune them.

The record pins the `.scratch/successor-inquiry-01` folder, which holds the
second item, but not the refs: they are Git state outside `.scratch`, kept by
this rule alone. `coordination/successor-inquiry-01/CORPUS-RETENTION.md` at
commit `267aaf0` explains what they protect.

Two earlier indexes are in Git history. `coordination/EVIDENCE.md` at commit
`267aaf0` indexes the records of the retired studies under `.scratch/`. At
commit `aafcb57` the same file listed the then-current runs, whose account is
`TRANSITION-PLAN.md` at `aafcb57`.

An evidence run keeps what ACCEPTANCE requires until its results have been
reviewed ("What a test run keeps", C18): the witness, and the damaged originals
and bulky material that review needs, under the rules above. The driver writes
its witness, each variant's checks and inventories, and each command's argv,
streams, exit status and timing into the evidence folder, and removes nothing
there. The archives, folders and homes a case works on are in its work
directory (`--work`). With the default `--keep-work failed`, once a variant has
served its purpose (it passed, or its control fired) and its results are
written, the driver removes that variant's work and lists the removal in the
run's `RESULT.json`; a variant that did not serve its purpose keeps its work,
and up to 64 MiB of it is copied into the evidence. `--keep-work all` keeps
every variant's work. The container suites run the driver with the default, in
a work directory on the container's own disk that is discarded with the
container, and copy out the evidence folder. The service's integration tests
remove their temporary trees as each test finishes.

What a run must show:

- A clean result needs a firing control, a case differing in the measured
  property and an invariance case (ACCEPTANCE, "Rules every check follows"). A
  control that does not fire is a broken check, and a run that lost its control
  is not evidence of the property it guards.
- The witness sits outside whatever the run under test may change or remove,
  as the driver keeps its own outside Stewart's archive.
- Preserve command outputs. The scripts keep every step's stdout, stderr and
  exit status; commands run by hand for a study keep theirs beside its record.
- Report actual counts: cases run, passed, failed and skipped, and the controls
  that fired, as the run's own summary gives them (`host/SUMMARY`, the driver's
  `RESULTS.md`), never as what should have run.
- A run qualifies the commit it archived (a suite's `host/commit.stdout`) and
  the binaries whose digests it recorded; by itself it says nothing about a
  later source.
- Qualify actual access and stopping, not merely the settings meant to produce
  them.
- An explanation remains a hypothesis until a comparison distinguishes it from
  its rivals.
