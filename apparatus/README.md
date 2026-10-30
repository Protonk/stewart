# Build and test apparatus

Development apparatus for the Rust audit service in [`service/`](../service).
It does not ship. Linux containers hold the build and, later, the scripted
acceptance tier; see [ACCEPTANCE.md](../ACCEPTANCE.md).

## Container access

On the development Mac the containers run under Apple `container` 1.6.1. That
service cannot be reached from a sandboxed agent shell, so the apparatus is a
set of host scripts that a person runs directly. Each script writes a new
evidence folder and refuses to reuse an existing one.

## Step 2: toolchain, vendored crates and a static build

```sh
sh apparatus/step2.sh                 # evidence in .scratch/apparatus-01
sh apparatus/step2.sh /abs/new/folder # or a folder you choose
```

The script:

1. Checks the container CLI version and that it supports `build`.
2. Archives `service/` and `apparatus/` from `HEAD` with `git archive`. The
   build therefore sees only committed files, and the commit is recorded.
3. With network access:
   - pulls the pinned `rust` and `alpine` images for `linux/amd64` (the arm64
     ones are already present);
   - builds `stewart-toolchain:1-arm64` and `stewart-toolchain:1-amd64` from
     [`container/Containerfile`](container/Containerfile), adding the native
     musl target and musl C toolchain;
   - vendors the crates named by `service/Cargo.lock` into `service/vendor`,
     which is not tracked.
4. Without network access, for each architecture:
   - builds the release binary twice, in two fresh containers, and compares
     the binaries;
   - checks the binary has no program interpreter (it is static);
   - runs it in the toolchain image and again in the pinned alpine image.

`host/DONE` reports `failures=N`. Every step keeps its stdout, stderr and exit
code under `host/` or the build folder. The toolchain image digests are the
pins for later builds and are recorded in `host/toolchain-inspect-*.stdout`.

The x86_64 builds run under Rosetta emulation. Builds there are slower, and
timings measured there are reported but do not gate (ACCEPTANCE C9).

Vendored crates come from crates.io at the versions and checksums in
`Cargo.lock`. To rebuild `service/vendor` elsewhere, run the vendoring step
again with network access. Builds are otherwise offline:
`service/.cargo/config.toml` replaces crates.io with `vendor/`.

## Step 3: the manager foundation acceptance driver

[`driver/stewart_driver.py`](driver/stewart_driver.py) is the independent
black-box driver for the manager foundation (`new`, `prepare`, `commission`,
`receipt`, `status`, close before launch, `help`). It was written from
[INTERFACE.md](../docs/INTERFACE.md), [CONTRACTS.md](../CONTRACTS.md) and
[ACCEPTANCE.md](../ACCEPTANCE.md) without reading `service/`, and drives two
binaries only through their command line: the release build and the test
build (`--features fault-injection,sabotage`, INTERFACE Appendix C). It uses
the Python standard library only.

Each case keeps its own witness of everything it supplies under the evidence
folder, and inventories every archive (path, inode, size, mode, mtime,
SHA-256) before and after every command: an earlier entry may never change or
disappear (C6), and folders, destinations, homes and working directories may
not change at all. A case with sabotage controls runs on the release binary,
on the test binary without sabotage, and once per control; a control fires
when one of its target checks fails, and one that does not fire is reported as
a broken check. Fault cases run on the test binary.

Natively, for example on the development Mac against a development build
(not qualification evidence):

```sh
python3 -I -B apparatus/driver/stewart_driver.py --list
python3 -I -B apparatus/driver/stewart_driver.py --self-test
python3 -I -B apparatus/driver/stewart_driver.py \
    --binary /abs/stewart --test-binary /abs/stewart-test \
    --evidence /abs/new-folder [--case 'c17.*'] [--exclude 'close.*'] [--skip-heavy]
```

Build the test binary into its own target folder, for example with
`CARGO_TARGET_DIR`, so the two builds never share artifacts. Linux-only
expectations (the ext4/xfs/btrfs allowlist, OFD lock behaviour, byte-string
file names) are skipped with their reason elsewhere. The C9 timing gate (under
100 ms for startup, `status` and `help`) applies only with `--timing-gate on`,
which the container suite sets for the native architecture. The evidence
folder holds `START.json`, `RESULT.json`, `RESULTS.md`, each command's argv,
streams, exit status and timing, the inventories, and the witnesses. The exit
status is 0 only when no case failed and every control fired.

The container suite is the step 3 evidence:

```sh
sh apparatus/step3.sh                 # evidence in .scratch/step3-01
sh apparatus/step3.sh /abs/new/folder # or a folder you choose
```

It needs the step 2 toolchain images and `service/vendor`, and pulls the
pinned python image (its only network use). For each architecture, offline,
it builds from a `git archive` of `HEAD` the release binary, the test binary
and a glibc control build; checks that both musl binaries are static and the
glibc build is not, that `cmp` tells the release and test binaries apart, and
that only the test binary contains `STEWART_TEST_FAULT` and
`STEWART_TEST_SABOTAGE`; then runs the driver in the python image as an
unprivileged user, with the binaries mounted read-only and archives on the
container's own disk. `host/DONE` reports `failures=N`; `host/SUMMARY` gives
the driver's counts per architecture, and `driver-<arch>/evidence/` holds its
full results. Timings under x86_64 emulation are reported but do not gate.

## Evidence retention

Evidence folders under `.scratch/` follow the retained-run rules in
[DEVELOPMENT.md](../DEVELOPMENT.md). The report or plan that cites a run keeps
its record.
