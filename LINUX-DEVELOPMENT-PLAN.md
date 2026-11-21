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

Each stage lists its known sites. A review of the tree found them; anything
else that assumes macOS becomes a task where it is found.

### 1. Create the VM

- [ ] Track a Lima template and provisioning script under `apparatus/lima/`.
  The template sets the decisions above: Debian 13, `vz`, Rosetta for x86_64,
  no mounts, SSH agent forwarding and the keyring expiry. Provisioning installs:
  - Podman, with `catatonit` for `--init`. The user gets cgroup v2 delegation
    of memory and CPU, so rootless `--memory` and `--cpus` bounds are enforced.
  - git, Python 3, keyutils, gnupg, curl and the build tools the native checks
    use;
  - rustup with the toolchain the Containerfile's image pins;
  - Claude Code at a pinned version.
- [ ] Create `stewart` from the template, clone over SSH, and run the native
  Cargo matrix, the link check and the driver self-tests. Each failure that
  comes from a macOS assumption becomes a task in stage 3.

Debian 13 mounts `/tmp` as tmpfs by default, which the archive filesystem
allowlist refuses. Archive tests use `STEWART_IT_TMP` on the VM's ext4 disk. The VM must
be reproducible from the tracked template alone.

### 2. Port containers and credentials

- [ ] Replace Apple `container` with Podman. Keep the launchers' properties:
  - one retained container per launch, with its memory bound;
  - UID separation and the independent process observers;
  - no network for rehearsals.

  x86_64 runs as `--platform linux/amd64` through Rosetta. Known sites:
  - **`apparatus/container/suite-host.sh` and `step2.sh`.** The pinned
    `container` version and service checks become Podman equivalents. Their
    `build`, `run` and `image inspect` calls and flag probes change with them.
    The host record from `sw_vers` becomes the VM's `/etc/os-release`.
    `shasum -a 256` becomes `sha256sum`, which has the same output format.
  - **`apparatus/c10/c10.py` and `apparatus/sanity/launch.py`.** The launchers'
    run, exec, inspect, image-inspect, version and service calls, including
    `host_control`, and the error texts that require Apple `container` 1.6.1.
    The pinned Python image reference may need re-pinning for Podman's storage.
  - **`apparatus/c10/test_c10.py`.** Its fake `container` executable and the
    argv it asserts.
  - **`apparatus/container/driver-env.sh`.** Its Rosetta detection looks for
    `VirtualApple` in `/proc/cpuinfo` and the `.cache/rosetta` artifact.
    Observe both again under Lima and Podman, or `qualified.py` will record an
    emulated run as native.
  - **`apparatus/qualified.py`.** It reads Apple `container`'s image-inspect
    JSON (`configuration.descriptor.digest`) for the toolchain and Python image
    identities.
    - Decide which Podman identity pins a locally built toolchain image, and
      change `step2.sh`, `qualified.py`, its self-test and the Containerfile
      comment together.
    - Keep the script lines `qualified.py` parses (`step2.sh`'s start line,
      `inner-build.sh`'s step names and the suites' expect lines), or change
      both sides.
    - Its `.DS_Store` handling becomes dead.
  - **Rootless UID mapping.** Evidence that container UID 1000 writes into bind
    mounts must stay readable to the VM user, for example through
    `--userns=keep-id` or root-owned exports. This covers C10 and sanity
    exports and suite outputs.
- [ ] Replace the Keychain lookup of saved provider connections with the
  keyring lookup, keyed by connection name. Test it with synthetic keys,
  including missing, expired and unreadable keys, and show that no key reaches
  a record. Known sites:
  - `apparatus/c10/connections.py`, which runs the `security` call and
    classifies its macOS status codes.
  - `c10.py`'s credential-source records. Their kind `keychain` becomes a
    keyring kind, and older records are refused, not read.
  - `c10.py`'s `--connection` help and Keychain docstrings, and the host
    queue's pass-through.
  - `test_c10.py`'s fake `security` executable and its diagnostics.
  - `apparatus/testdata/keychain/`, a captured macOS lookup, which gives way to
    a keyring capture.
  - The lookup runs from the launchers' cleared environment and from
    `limactl shell` sessions, so the key lives in the persistent user keyring,
    not in a session keyring.
- [ ] Give the harness apparatus a Linux route. A Linux executable has no Apple
  code signature, so pin it against the signed manifest instead. Keep the route
  short enough for a person outside this checkout to follow. Known sites:
  - **`pin.py`.** Its single `darwin-arm64` platform, its refusal of anything
    but `arm64`, and `codesign`. Select the manifest key by architecture, and
    record the manifest's signature verification as the integrity step.
  - **`profile.py`.** The `codesign` step it runs and later requires at
    assemble, and the `macos-aarch64` launch platform it writes and checks.
    The runtime contract's profile `platform` values lose `macos-aarch64`. The
    code, the contract and the driver change together, and older profiles are
    refused.
  - **Tests and captures.** `test_pin.py`, `test_profile.py` and the `codesign`
    captures under `apparatus/claude-code/testdata/verification/`, replaced by
    captures from the Linux route.
  - **`service_check.py`.** It runs commands in `/private/tmp` and freezes that
    path in its commission, so the commission schema changes. It and
    `bounded.py` choose a macOS clock.
  - **The harness login.** On Linux the harness keeps its login in
    `.credentials.json` under its configuration directory. Check that no
    packet, inventory, retained snapshot or archive walks that directory, and
    restate the guides' claims about not reading the credential store.
- [ ] Run each changed component's check row from DEVELOPMENT.

### 3. Remove macOS

- [ ] Service: remove the macOS branches in `service/src/platform.rs` and other
  macOS-only code and comments. The crate builds and tests only on Linux. Known
  sites:
  - the crate documentation in `lib.rs`: its macOS build note and its
    "development fallbacks";
  - comments naming macOS in the runtime's socket naming and in the provider
    transport;
  - the runtime's periodic MCP socket reads, which exist for a macOS socket
    behavior. Test whether Linux needs them, then keep them with a Linux reason
    or remove them;
  - `service/tests/manager.rs`: the macOS lock assertion and the case-folding
    host test that Linux always skips, with the crate guide's lines about
    host-specific skipped tests.
- [ ] Apparatus outside the driver: what stage 2 leaves of process
  observation, paths and notes in `apparatus/claude-code/`, C10, sanity and the
  host queue.
- [ ] The driver, its fixtures and their test data: assign these to a separate
  agent that has not read `service/src` or `service/tests`. It works from this
  plan's decisions and the specification alone, under the driver-independence
  rule. A reviewer who did not read the implementation found these sites:
  - `claude_code.py`:
    - the Darwin row of the platform table;
    - the binding-mutation control that uses `macos-aarch64` as the other
      valid platform;
    - the macOS pipe-packing byte rule and its two checks;
    - the `lsof` branch of pipe-reader observation;
    - the `/Users/` leak check, which should also refuse `/home/`;
    - a `/private/tmp` literal.
  - `claude_code_surface.py`: the macOS clock.
  - `driver_core.py`:
    - `is_linux()` and its guards;
    - the macOS `ru_maxrss` unit;
    - the `mkfifo` fallback for macOS Python;
    - Rosetta wording that names Apple silicon.
  - The Linux-only skip machinery: the `linux` and `lock` needs and
    `linux_reason`. The cases it guards in `cases_foundation.py`,
    `cases_run.py`, `cases_after_launch.py` and `cases_command_effects.py`
    become unconditional. Filesystem-probe skips lose their "Linux-only"
    wording. Case, check and skip counts change.
  - The credential observer's Rosetta interpreter path, `/run/rosetta/rosetta`
    under Apple `container`, which differs under Lima and Podman. Add a fixture
    of the observed Podman form.
  - The guides:
    - `CLAUDE-CODE.md`: its supported platforms, its macOS pipe sentence and
      its "native" results;
    - `CLAUDE-CODE-SURFACE.md`: its clock;
    - links to the service procedure's section, if that section is renamed.
  - Test data captured on macOS, in `testdata/os` and `testdata/wire`, stays as
    provenance. Pointers in `testdata/README.md` to `.scratch` originals that
    do not move into the VM say so.
  - The driver guide states Python 3.9 and `driver_core.py` states 3.8. Settle
    one minimum.
- [ ] Documentation. Known sites:
  - **README:** the platform paragraph, the status paragraph's second macOS
    sentence, and its "native" encounters.
  - **DESIGN and ACCEPTANCE:** their platform lines.
  - **INTERFACE:** its opening sentence on macOS fallbacks, whose DEVELOPMENT
    anchor this stage changes.
  - **CONTRACTS:** its platform section.
  - **The runtime contract:**
    - its platform sentence;
    - "Native macOS checks" in evidence owed;
    - its "native" evidence statements;
    - the harness's Keychain storage fact;
    - the profile platform values.
  - **AGENTS, which CLAUDE.md links to:** the `development Mac` line, the
    development-machine runs paragraph, and "host operation" in the sandbox
    rule.
  - **DEVELOPMENT:**
    - its introduction, and the check-table rows that say "development Mac";
    - native building, and the driver's skip paragraph;
    - container suites;
    - the Rosetta, sandbox and tmpfs notes;
    - the layout and evidence sections;
    - the macOS build note.
  - **The crate guide:** its platform section, the "native Apple-silicon
    workflow" and the Tests paragraph.
  - **Live testing and unresolved operations:** the "qualifies nothing" line
    and the "native" encounters.
  - **The apparatus guides:**
    - `apparatus/README.md`;
    - the C10 README: the Keychain setup with `security`, Allow prompts and
      native iteration;
    - HOST-QUEUE: Keychain prompts and the "host terminal";
    - the sanity LAUNCHER and RUN-SHEET: Apple `container`, and host-VPN
      egress, which becomes the VM's;
    - the harness README: the Apple signature, the macOS clock,
      `/private/tmp`, and the "native service comparison procedure" section
      name and its links.

  Write the replacements as if Stewart had always been developed on Linux.
  Where "native" described evidence gathered on macOS, the documentation
  states what was shown and leaves the platform to the evidence record.

### 4. Qualify

- [ ] Run `step2.sh` in the VM. It builds new toolchain images with Podman for
  both architectures and checks that the build is reproducible.
- [ ] Run `acceptance.sh` and `runtime-acceptance.sh` on both architectures,
  record them with `qualified.py`, and pass `qualified.py check`.
- [ ] Pass retained Linux rehearsals of C10 and sanity under Podman, and the
  harness apparatus's offline rehearsals in the VM with the synthetic peer.
- [ ] Install, pin and sign in to Claude Code in the VM, and pass the harness's
  offline apparatus checks.

### 5. Move evidence and retire the Mac setup

- [ ] Inventory the Mac's Apple containers, images and `.scratch` (27
  containers, 6 images, and 174 entries of 12 GiB on 2026-11-20) against the
  qualification record's pins and any open custody. Close or dispose of any
  open audit with its own writer before its container goes. An archive that
  exists only in a retained container is closed or exported first.
- [ ] Copy into the VM checkout's `.scratch` only the originals whose pins keep
  a present purpose, and verify their digests. Release pins whose purpose ended
  with the move. Examples are a rehearsal bound to live launches from the Mac,
  and the Mac's Claude Code pin and profile evidence, which the new forms
  refuse.
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
