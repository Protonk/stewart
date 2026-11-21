# Linux development

Stewart is Linux software and is to be developed on Linux. The development Mac
becomes only the host for one Lima virtual machine. All development, checks,
container suites, live apparatus and agent sessions will run inside that VM.
The Lima template will be the Mac host's entry point.

Today the work runs in two worlds. Iteration is native on macOS, which no claim
covers; qualification uses Linux containers under Apple `container`. The
real-harness runs are native on macOS too. One Linux environment removes the
macOS code paths and the per-platform notes. It puts live runtime evidence on a
supported platform and makes a development build a Linux build.

**Status:** decided by the maintainer and ready to start.

## Decisions

- **Platform.** Stewart supports Linux x86_64 and aarch64. The
  `aarch64-apple-darwin` build target and every macOS code path are removed.
  For a Mac, the README says one thing: run Stewart inside a Linux VM or
  container with the archive on local ext4, xfs or btrfs.
- **VM.** Lima manages one long-lived VM named `stewart`:
  - Debian 13 for aarch64, the same family as the toolchain image's Debian
    base;
  - Apple's virtualization framework (Lima's `vz` type), with Rosetta
    registered to run x86_64 Linux binaries;
  - 6 CPUs, 8 GiB of memory and an 80 GiB sparse disk. The host has 10 cores,
    16 GiB and about 93 GiB free, and also runs another project's VM.
- **No shared folders.** Keep the Mac home, checkout and temporary directories
  unmounted. The repository, build trees and evidence live on the VM's own
  disk. Stewart's custody checks exercise file modes, exclusive creation and
  fsync on the filesystem that holds the audit. VZ supplies the Rosetta runtime.
- **Containers.** Rootless Podman inside the VM replaces Apple `container`
  everywhere. `container` is dropped entirely. x86_64 containers run through
  Rosetta, as they do today.
- **Sessions.** Claude Code sessions run inside the VM. The maintainer enters
  with `limactl shell stewart` and works with git and ordinary command-line
  tools.
- **Qualification.** The toolchain, release and development-runtime suites
  qualify the behavior exercised by their recorded source, images and writers.
  Both Linux userlands use the VM's aarch64 kernel. Record amd64 execution
  through Rosetta. Native Cargo and driver runs in the VM are for iteration.

### Secrets

The tooling stores no secret of its own, and nobody pastes a key for each run.

- **Provider API keys** go into the Linux kernel's per-user persistent keyring.
  - The maintainer enters the key through a non-echoing prompt after boot.
    Feed its bytes to `keyctl padd` on stdin.
  - After verified intake or continuation preflight, the launcher reads the
    named key with `keyctl pipe` into a private pipe. Preserve the existing
    byte validation, rehearsal canary check, container stdin handoff, one-use
    descriptor to Stewart and credential scans. Keep real keys out of
    arguments, the environment, logs and exported records.
  - Each fresh launcher session obtains the user's persistent ring with
    `keyctl get_persistent @s` and searches that ring by type and description.
    Obtaining it refreshes its inactivity timeout. Set the interval to cover
    the planned idle time. Expiry and guest reboot can require re-entry.
    [Persistent keyring](https://man7.org/linux/man-pages/man7/persistent-keyring.7.html)

  Processes running as the development user can read that user's key. A
  dedicated launcher account can restrict access if agents lack general sudo
  and can invoke only launcher code and configuration controlled by that
  account or the maintainer. Lima grants its default guest user passwordless
  sudo. Encrypted systemd credentials are an option if re-entry after reboot
  becomes a burden. [Lima guest privileges](https://lima-vm.io/docs/config/sudo/)
- **GitHub pushes and release signing** use the Mac's SSH agent, forwarded
  into the VM by Lima, so private keys stay on the Mac. The VM's clone uses the
  SSH remote. A guest process with access to the forwarded socket can request
  operations with the loaded identities. For the GitHub CLI fallback, use
  an HTTPS remote with `gh auth setup-git` and provision a working credential
  store before login. On a headless guest `gh` can fall back to a plaintext
  token file. Confirm the storage location with `gh auth status`. This fallback
  covers Git transport only. [GitHub CLI login](https://cli.github.com/manual/gh_auth_login)
- **The Claude Code harness login** belongs to the harness. It is made once in
  the VM through the harness's sign-in URL, opened on the Mac. Stewart never
  reads or copies it.

## Stages

Each stage lists its known sites. Anything
else that assumes macOS becomes a task where it is found.

### 1. Create the VM

- [ ] Inventory the Mac's retained containers, native audits, exact writers and
  qualification pins while their original checkout and launchers still work.
  Keep each needed execution environment available through custody review and
  reserve fresh evidence directory names across both machines.
  Check actual free space on the Mac and in the guest before staging builds
  and retained originals side by side. The sparse disk size is a ceiling.
- [ ] Track a Lima template and provisioning script under `apparatus/lima/`.
  Pin the Debian image by digest and record the tested Lima version. Enable
  Rosetta and its binfmt registration. Omit the default home-directory mount,
  disable Lima's bundled containerd and verify the effective guest mounts.
  Configure SSH forwarding and keyring expiry as above. Install rootless
  Podman and `catatonit` for `--init`, configure subordinate UID/GID ranges
  and delegate the cgroup v2 CPU and memory controllers. Install git, Python
  3, keyutils, gnupg, curl, the native build tools, and rustup with the Rust
  version recorded for the pinned toolchain image.
- [ ] Create `stewart`, clone the repository with its history, and run the link
  check and driver self-tests. Bootstrap the ignored `service/vendor` tree
  from the committed lockfile and compare its file digest listing with the
  recorded toolchain run. Run the four offline Cargo configurations from
  `service/` as the guest user, with `STEWART_IT_TMP` set to a private
  directory on guest ext4 outside the checkout. This also works when `/tmp`
  is tmpfs. Record baseline failures for the port. [Vendoring procedure](development/DEVELOPMENT.md#toolchain-and-dependencies)

### 2. Port containers and credentials

- [ ] Replace Apple `container` with Podman. Keep the launchers' properties:
  - Keep one container per C10 or sanity launch, with its private storage
    and operator commands usable from a fresh guest login.
  - Preserve UID separation and the independent process observers.
  - Run offline rehearsals with loopback only. Preload the pinned images and
    use `--pull=never` for offline runs.
  - Check the effective CPU and memory limits in the container's cgroup and
    exercise enforcement with a disposable load.

  x86_64 runs as `--platform linux/amd64` through Rosetta. Known sites:
  - **`apparatus/container/suite-host.sh` and `step2.sh`.** The pinned
    version check becomes a Podman version check. Exercise local rootless
    Podman directly from the launchers' minimal environment, including its
    guest user runtime directory.
    Build the toolchain from the committed Containerfile and build context
    extracted from the same `git archive` recorded for that run.
    The host record from `sw_vers` becomes the VM's `/etc/os-release`.
    `shasum -a 256` becomes `sha256sum`, which has the same output format.
  - **`apparatus/c10/c10.py` and `apparatus/sanity/launch.py`.** The launchers'
    run, exec, inspect, image-inspect, version and service calls, including
    `host_control`, and the error texts that require Apple `container` 1.6.1.
    Preserve the registry digest for the pinned Python image. Both launchers
    use the qualification record to construct a pullable reference.
    Exercise the fake CLI in `test_c10.py` and the sanity launcher tests.
  - **`apparatus/container/driver-env.sh`.** Its Rosetta detection looks for
    `VirtualApple` in `/proc/cpuinfo` and the `.cache/rosetta` artifact.
    Observe the interpreter and any cache writes in the new environment before
    excluding a path from the write witness. Without the Rosetta marker,
    `qualified.py` labels amd64 on an arm64 host simply `emulated`.
  - **`apparatus/qualified.py`.** It reads Apple `container`'s image-inspect
    JSON (`configuration.descriptor.digest`) for the toolchain and Python image
    identities.
    - Bind each build to the specific local toolchain image it ran. Record the
      registry index and resolved platform manifests for pulled images. Check
      that the aarch64 C10/sanity launch resolves the same Python image as its
      qualification after both architectures have been pulled.
    - Keep the script lines `qualified.py` parses (`step2.sh`'s start line,
      `inner-build.sh`'s step names and the suites' expect lines), or change
      both sides.
    - Exercise image extraction and folder digests against a new Podman run
      and still-pinned originals. The checker re-extracts suite entries and
      excludes regular `.DS_Store` files from recorded tree digests. Preserve
      the digests and original bytes of retained evidence when the producer
      changes.
  - **Archive storage.** Give each run its own guest-ext4 workspace mounted
    at `/work` in the driver, C10 and sanity containers. Inspect the
    filesystem at the actual archive path inside each container. Stewart
    refuses the usual OverlayFS writable layer. Keep the private archive and
    independent witnesses outside the export directory, and retain the
    writable mount with its named container through review.
  - **Filename fixture.** The release suite's `--component-source-work` uses
    a Mac-backed mount to present 255- and 256-byte UTF-8 names to Stewart.
    Guest ext4 rejects the longer name at creation. Supply a guest-local
    source filesystem that can represent both (for example a UTF-8 VFAT test
    volume). Require the existing byte-enumeration witness, exact-bound
    readback and over-bound refusal on both architectures. Keep the audit on
    ext4. [C19 acceptance](ACCEPTANCE.md#c19--literal-text-materials-and-preparation-inspection)
  - **Rootless UID mapping.** Start setup as container UID 0, then drop to
    the recorded UIDs. Exercise the readable and protected process controls
    as UIDs 1000 and 1001. Verify that the guest user can read the published
    evidence and that private witnesses keep their permissions. The default
    rootless mapping maps container root to the VM user, so container-root
    exports can be private and readable by that user. [Podman user namespaces](https://docs.podman.io/en/latest/markdown/podman-run.1.html#userns-mode)
- [ ] Replace the Keychain lookup of saved provider connections with the
  keyring lookup, keyed by connection name. Test it with synthetic keys,
  including missing, expired, unreadable and wrong-label keys. Check that
  failures withhold the handoff, status reads metadata only, and exported
  records and diagnostics pass the credential scan. Keep the independent
  private rehearsal witness. Known sites:
  - `apparatus/c10/connections.py`, which runs the `security` call and
    classifies its macOS status codes.
  - `c10.py`'s credential-source records and checks for launch, continuation
    and collection. Version the changed record forms and refuse superseded
    forms. Keep the original launcher for outstanding custody.
  - The host queue's `--connection` pass-through and both launchers' live
    hidden-entry paths, including standalone sanity. Use the bound credential
    label for saved connections and test the queue with synthetic keys.
  - `test_c10.py`'s fake `security` executable and its diagnostics.
  - `apparatus/testdata/keychain/`, a captured macOS lookup, which gives way to
    a keyring capture.
  - Verify lookup after logout from a fresh `limactl shell` and from the
    queue's minimal environment. Check loss on reboot with a synthetic key.
- [ ] Give the harness apparatus a Linux route. A Linux executable has no Apple
  code signature, so pin it against the signed manifest instead. Keep the route
  short enough for a person outside this checkout to follow. Settle the profile
  form in the runtime contract before assigning service and independent driver
  changes to their respective authors. Known sites:
  - **`pin.py`.** Its single `darwin-arm64` platform, its refusal of anything
    but `arm64`, and `codesign`. Select the manifest key by architecture.
    Verify the detached signature against the pinned signer fingerprint and
    compare the executable's digest to that platform's signed checksum.
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
  - `service/tests/manager.rs`: remove the macOS lock assertion. Keep the
    case-alias test and its filesystem probe. Linux ext4 supports case-folded
    directories. Run that test on a folding workspace and retain its skip
    reason on a case-sensitive one.
- [ ] Apparatus outside the driver: what stage 2 leaves of process
  observation, paths and notes in `apparatus/claude-code/`, C10, sanity and the
  host queue.
- [ ] The driver, its fixtures and their test data: assign these to a separate
  agent that has not read `service/src` or `service/tests`. It works from this
  plan's decisions and the specification alone, under the driver-independence
  rule. Known sites, found without reading the implementation:
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
    wording. Account for differences in case, check and skip counts against
    the prior Linux suite. Each Linux case still owes its controls.
  - Capture the credential observer's actual amd64 interpreter argv and
    descriptor identities in Podman, with native aarch64 as the control.
    Update the matcher and fixture from that observation.
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
      egress. Record what is known about the authorized direct route from
      the guest, including any host VPN on that route;
    - the harness README: the Apple signature, the macOS clock,
      `/private/tmp`, and the "native service comparison procedure" section
      name and its links.

  Write the replacements as if Stewart had always been developed on Linux.
  Attribute platform-sensitive observations to the system that produced them.
  Describe Linux real-harness behavior as demonstrated only when observed there.

### 4. Qualify

- [ ] Run the development checks for the changed components and commit the
  port. Move the bootstrap vendor tree aside before running
  `step2.sh`, which requires `service/vendor` to be absent. It builds both
  toolchain images and compares two offline binary builds per architecture.
  Run the native Cargo matrix with the vendor tree it produces. [Required checks](development/DEVELOPMENT.md#what-to-run-for-what-you-changed)
- [ ] Run `acceptance.sh` and `runtime-acceptance.sh` on both architectures
  against those images. Extract all three runs with `qualified.py` under
  `toolchain`, `acceptance` and `runtime`. Review verdicts, skipped cases
  or parts and firing controls. Require full Linux coverage on both
  architectures, run `qualified.py check` and commit the JSON and rendered
  Markdown together.
- [ ] Pass retained Linux rehearsals of C10 and sanity under Podman.
- [ ] Install and authenticate the pinned Linux executable against the signed
  manifest without launching it. Run the offline harness rehearsals with the
  synthetic peer. The maintainer signs in to the dedicated harness config
  in the VM. Any agent-initiated real harness invocation, including an auth
  or surface check, requires explicit coverage by a bounded authorization.

### 5. Move evidence and retire the Mac setup

- [ ] Reconcile the initial inventory with current audit status, pending
  attempts, deliveries and holds. Resolve open audits with their exact
  writers under the applicable authority. Keep the original environment
  runnable wherever a disposition is outstanding. A copy at a new path can
  support inspection but cannot take over an open reference.
- [ ] Apply each pin's recorded release condition, including pending
  comparisons and fixture reviews that still use Mac profiles. Copy the
  surviving front and pinned evidence into the VM's `.scratch` under the
  recorded names. Verify any separately retained writers, private archives
  and witnesses against the originals. A successful close still leaves
  retained bytes in custody.
- [ ] Run `python3 -I -B apparatus/qualified.py check --require-evidence`
  in the destination checkout. Plain `check` can succeed with an absent
  evidence folder. Confirm the independent backup of irreplaceable originals
  at an authorized destination, or keep the source copy and report the
  outstanding backup. [Evidence and retention](development/DEVELOPMENT.md#evidence-and-retention)
- [ ] Before retiring a Mac container, image or checkout, verify its custody
  disposition and account for worktrees, uncommitted work and local-only
  commits. Remove only the project resources whose obligations are met.
  Uninstalling Apple `container` is the maintainer's choice.

## Done when

- The VM can be provisioned from the tracked template, script and named
  installation inputs. Restoring evidence and signing in are separate steps.
  Development, checks, container suites, live apparatus and agent sessions
  all run inside it.
- The service and guest-side tools build and run on Linux. The Mac-specific
  material is confined to Lima host setup, user guidance and evidence provenance.
- The toolchain, release and runtime suites pass on both architectures under
  Podman, and the C10, sanity and harness rehearsals pass.
- Secrets follow the decisions above.
- The Mac checkout and Apple containers are retired, with every custody
  obligation met.
- The documentation describes the Linux environment, and this plan is deleted.
