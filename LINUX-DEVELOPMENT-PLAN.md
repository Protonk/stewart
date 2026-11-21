# Linux development

Stewart is Linux software and is to be developed on Linux. The development Mac
becomes only the host for one Lima virtual machine. All development, checks,
container suites, live apparatus and agent sessions run inside that VM, and
nothing in the repository targets macOS.

Today the work runs in two worlds. Iteration is native on macOS, which no claim
covers; qualification uses Linux containers under Apple `container`. The
real-harness runs are native on macOS too. One Linux environment removes the
macOS code paths and the per-platform notes. It puts live runtime evidence on a
supported platform, and makes a development build a Linux build. It also gives
autonomous agents a natural boundary.

**Status:** decided by the maintainer on 2026-11-20 and ready to start.

## Decisions

- **Platform.** Stewart supports Linux x86_64 and aarch64, as before. The
  `aarch64-apple-darwin` build target and every macOS code path are removed.
  For a Mac, the README says one thing: run Stewart inside a Linux VM or
  container and keep the archive on the Linux filesystem.
- **VM.** Lima manages one long-lived VM named `stewart`:
  - Debian 13 for aarch64, the same family as the toolchain image's Debian
    base;
  - Apple's virtualization framework (Lima's `vz` type), with Rosetta
    registered to run x86_64 Linux binaries;
  - 6 CPUs, 8 GiB of memory and an 80 GiB sparse disk. The host has 10 cores,
    16 GiB and about 93 GiB free, and also runs another project's VM.
- **No shared folders.** No Mac folder is mounted into the VM. The repository,
  its build trees and its evidence live on the VM's own disk, because
  Stewart's custody tests depend on file modes, exclusive creation and fsync,
  which shared folders bend.
- **Containers.** Rootless Podman inside the VM replaces Apple `container`
  everywhere. `container` is dropped entirely. x86_64 containers run through
  Rosetta, as they do today.
- **Sessions.** Claude Code sessions run inside the VM. The maintainer enters
  with `limactl shell stewart` and works with git and ordinary command-line
  tools as before.
- **Qualification.** Its kind is unchanged. Container suites build from
  `git archive` in pinned toolchain images, now built by Podman, on both
  architectures. A working-tree run qualifies nothing, so the line becomes
  hermetic versus not, rather than Mac versus Linux.

### Secrets

The tooling stores no secret of its own, and nobody pastes a key for each run.

- **Provider API keys** go into the Linux kernel's persistent keyring
  (keyutils):
  - the maintainer enters a key once per VM boot by hidden entry;
  - the apparatus finds it by description and copies it with `keyctl` straight
    into the descriptor the launcher hands to Stewart;
  - it never reaches a file, argv, the environment or chat;
  - provisioning raises the keyring's expiry so that the key lasts for the
    VM's working life.

  Any process of the same user can read the key. Two step-ups are available
  when needed: a dedicated launcher user can hold the key and accept requests
  through a narrow sudo rule, and systemd's encrypted credentials can survive
  reboots if entering the key once per boot becomes a burden.
- **GitHub pushes and release signing** use the Mac's SSH agent, forwarded
  into the VM by Lima, so private keys stay on the Mac. The VM's clone uses the
  SSH remote. If the Mac's agent holds no key that GitHub accepts,
  `gh auth login` inside the VM is the fallback, and its token stays in `gh`'s
  own store.
- **The Claude Code harness login** belongs to the harness. It is made once in
  the VM through the harness's sign-in URL, opened on the Mac. Stewart never
  reads or copies it.

## Stages

### 1. Create the VM

- [ ] Track a Lima template and provisioning script under `apparatus/lima/`.
  The template sets the decisions above: Debian 13, `vz`, Rosetta for x86_64,
  no mounts, SSH agent forwarding and the keyring expiry. Provisioning installs:
  - Podman, git, Python 3, keyutils and the build tools the native checks use;
  - rustup with the toolchain the Containerfile's image pins;
  - Claude Code at a pinned version.
- [ ] Create `stewart` from the template, clone over SSH, and run the native
  Cargo matrix, the link check and the driver self-tests. Each failure that
  comes from a macOS assumption becomes a task in stage 3.

The VM must be reproducible from the tracked template alone.

### 2. Port containers and credentials

- [ ] Replace Apple `container` with Podman in `step2.sh`, the suite host and
  inner scripts, `c10.py`, `smoke.py` and the sanity launcher. Keep their
  properties:
  - one retained container per launch, with its memory bound;
  - UID separation and the independent process observers;
  - no network for rehearsals.

  x86_64 runs as `--platform linux/amd64` through Rosetta.
- [ ] Replace the Keychain lookup of saved provider connections
  (`apparatus/c10/connections.py` and the host queue) with the keyring lookup,
  keyed by connection name. Test it with synthetic keys, including missing,
  expired and unreadable keys, and show that no key reaches a record.
- [ ] Give the harness apparatus a Linux route. `pin.py` and `profile.py`
  today verify an Apple code signature against a native macOS pin. A Linux
  executable has none, so pin it against the signed manifest instead. Keep the
  route short enough for a person outside this checkout to follow.
- [ ] Run each changed component's check row from DEVELOPMENT.

### 3. Remove macOS

- [ ] Service: remove the macOS branches in `service/src/platform.rs` and other
  macOS-only code and comments. The crate builds and tests only on Linux.
- [ ] Apparatus outside the driver: process observation, paths and notes in
  `apparatus/claude-code/`, C10, sanity and the host queue.
- [ ] The driver, its fixtures and their test data: assign these to a separate
  agent that has not read `service/src` or `service/tests`. It works from this
  plan's decisions and the specification alone, under the driver-independence
  rule.
- [ ] Documentation:
  - the README's platform paragraph and its sentence for Mac users;
  - DEVELOPMENT: its introduction, native building, container suites, the
    Rosetta and sandbox notes, the layout and evidence sections;
  - CONTRACTS' platform section, the runtime contract's platform sentence and
    the crate guide;
  - the apparatus guides, live testing and the `development Mac` lines in
    AGENTS and CLAUDE.

### 4. Qualify

- [ ] Run `step2.sh` in the VM. It builds new toolchain images with Podman for
  both architectures and checks that the build is reproducible.
- [ ] Run `acceptance.sh` and `runtime-acceptance.sh` on both architectures,
  record them with `qualified.py`, and pass `qualified.py check`.
- [ ] Pass retained Linux rehearsals of C10 and sanity under Podman, and the
  harness apparatus's offline rehearsals in the VM with the synthetic peer.
- [ ] Install, pin and sign in to Claude Code in the VM, and pass the harness's
  offline apparatus checks. The runtime trials make its Sonnet profile.

### 5. Move evidence and retire the Mac setup

- [ ] Inventory the Mac's 27 Apple containers, its 6 images and `.scratch`
  (12 GiB, 174 entries) against the qualification record's pins and any open
  custody. Close or dispose of any open audit with its own writer before its
  container goes. An archive that exists only in a retained container is
  closed or exported first.
- [ ] Copy into the VM checkout's `.scratch` only the originals whose pins keep
  a present purpose, and verify their digests. Release pins whose purpose ended
  with the move, such as a rehearsal bound to live launches from the Mac.
- [ ] Once `qualified.py check` passes in the VM and nothing on the Mac is
  unpushed, remove the Apple containers and images and retire the Mac
  checkout. Uninstalling the `container` tool itself is the maintainer's
  choice.

## Done when

- The VM can be rebuilt from the tracked template. Development, checks,
  container suites, live apparatus and agent sessions all run inside it.
- No tracked file depends on macOS or Apple `container`, apart from history in
  the qualification record.
- The toolchain, release and runtime suites pass on both architectures under
  Podman, and the C10, sanity and harness rehearsals pass.
- Secrets follow the decisions above.
- The Mac checkout and Apple containers are retired, with every custody
  obligation met.
- The documentation describes the Linux environment, and this plan is deleted.
