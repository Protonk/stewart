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

## Evidence retention

Evidence folders under `.scratch/` follow the retained-run rules in
[DEVELOPMENT.md](../DEVELOPMENT.md). The report or plan that cites a run keeps
its record.
