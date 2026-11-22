# Build and test apparatus

Development apparatus for the Rust audit service in [`service/`](../service).
It does not ship. Linux containers hold the builds and the scripted acceptance
tier of [ACCEPTANCE.md](../ACCEPTANCE.md): `step2.sh` builds the toolchain
images and vendors the crates, and `acceptance.sh` builds the release and test
binaries and runs the independent driver against them.

[`check_links.py`](check_links.py) checks the relative links and anchors in the
repository's Markdown.

The qualification record, [`qualified.json`](qualified.json), is the tracked
account of what the suites have shown; [`qualified.py`](qualified.py) keeps it
and generates [`qualified.md`](qualified.md) from it.

The [small-commission apparatus](../alignment/messages/procedure/README.md) prepares all three question
families, runs bounded retained batches and reviews immutable exports. Its
offline rehearsal uses synthetic credentials and a local fake provider; live
launch needs a matching rehearsal and an explicitly authorized packet. Its
reports cover small-commission procedure and do not declare a model qualified.

The [standalone runtime driver](driver/CLAUDE-CODE.md) checks the gated Claude
Code adapter against a synthetic executable. It has its own self-test, case
list and native runtime command, and invokes no real harness or provider.
`runtime-acceptance.sh` builds two gated binaries, checks their markers and runs these
runtime cases on both Linux architectures. The separate [profile apparatus](../alignment/claude-code/README.md)
prepares installation evidence and runtime profiles.

## Running the scripts

Run the scripts in the Linux development login with rootless Podman 5 and
cgroup v2. [Guest setup](lima/README.md). Each script requires one argument, its evidence folder, and
refuses one that exists; give a new folder directly under `.scratch/` as an
absolute path. Without the argument a script prints its usage and exits 2
before doing anything else.

## `step2.sh`: toolchain images, vendored crates and a static build

```sh
sh apparatus/step2.sh "$PWD/.scratch/apparatus-NN"  # from the repository root; NN not yet used
```

It creates `service/vendor` and refuses to start while that folder exists. The
script:

1. Checks the Podman version, rootless operation and cgroup version.
2. Archives `service/` and `apparatus/` from `HEAD` with `git archive`. The
   build therefore sees only committed files, and the commit is recorded.
3. With network access:
   - pulls the pinned `rust` and `alpine` images for `linux/arm64` and
     `linux/amd64`;
   - builds `stewart-toolchain:1-arm64` and `stewart-toolchain:1-amd64` from
     [`container/Containerfile`](container/Containerfile), adding the native
     musl target and musl C toolchain;
   - vendors the crates named by `service/Cargo.lock` into `service/vendor`,
     which is not tracked.
4. Without network access, for each architecture:
   - builds the release binary twice, in two fresh containers, and compares
     the binaries;
   - checks the binary has no program interpreter (it is static);
   - runs it in the toolchain image, and runs `stewart help`, which exits 0, in
     the pinned alpine image.

`host/DONE` reports `failures=N`. Every step keeps its stdout, stderr and exit
code under `host/` or the build folder. The toolchain image digests are the
pins for later builds and are recorded in `host/toolchain-inspect-*.stdout`.

The amd64 builds run through Rosetta in the aarch64 guest.

Vendored crates come from crates.io at the versions and checksums in
`Cargo.lock`. To produce `service/vendor` in another checkout, run `step2.sh`
there with network access. Builds are otherwise offline:
`service/.cargo/config.toml` replaces crates.io with `vendor/`.

## The independent driver

[`driver/stewart_driver.py`](driver/stewart_driver.py) is the independent
black-box driver. It was written from [INTERFACE.md](../docs/INTERFACE.md),
[QUESTION-FORMS.md](../docs/QUESTION-FORMS.md),
[CONTRACTS.md](../CONTRACTS.md) and [ACCEPTANCE.md](../ACCEPTANCE.md) without
reading `service/`, and drives two binaries only through their command line:
the release build and the test build (`--features fault-injection,sabotage`,
INTERFACE Appendix C). It uses the Python standard library only.
The walkthrough cases (`cases_manager_walkthroughs.py`) read the
[manager walkthroughs](../examples/manager/README.md) and the
[worked examples](../examples/questions/README.md) at run time, execute them
as written and compare the binary's output with their text; without
`examples/` beside the driver they are skipped.

`stewart_driver.py` is the entrypoint. It puts its own directory on `sys.path`
(isolated mode does not) and imports every `cases_*.py` beside it, so a new
group of cases is a new file. `driver_core.py` holds the case registry, the
per-case context, inventories and evidence; `run_support.py` is the run
harness; the fake Messages API, the two auditors and the byte-exact witnesses
are described below. `mini_stewart.py` is a stand-in used only by self-tests.
Test-only TLS certificates are in [`driver/testdata/`](driver/testdata/README.md).

Run against a guest development build for iteration.

```sh
python3 -I -B apparatus/driver/stewart_driver.py --list [--describe]
python3 -I -B apparatus/driver/stewart_driver.py --self-test
python3 -I -B apparatus/driver/stewart_driver.py \
    --binary /abs/stewart --test-binary /abs/stewart-test \
    --evidence /abs/new-folder [--case 'c17.*'] [--exclude 'close.*'] [--skip-heavy]
```

Build the test binary into its own target folder, for example with
`CARGO_TARGET_DIR`, so the two builds never share artifacts. Expectations that
cover OFD locks, process observations, the archive filesystem allowlist and
raw filename bytes on both Linux architectures. `--skip-heavy` skips the cases `--list` marks heavy: bound-sized
inputs and close's bounded waits. The evidence folder holds `START.json`,
`RESULT.json`, `RESULTS.md`, each command's argv, streams, exit status and
timing, the inventories, and the witnesses. The exit status is 0 only when no
case failed and every control fired.

### Cases, variants and controls

`--list` prints the case inventory: each case's ID, the ACCEPTANCE claims it
bears on, its title, and where they apply its mode, needs, whether it is heavy,
its sabotage controls (INTERFACE C.2) and the failure points it sets (C.1).
`--list --describe` adds each case's description where it says more than the
title: what passes, what differs and what must stay the same. The description
is the case's docstring and is copied into its `RESULT.json`. A case can set
only the failure points it declares.

A release case runs on the release binary. A release case with sabotage
controls also runs in full on the test binary with no test variable set. That
baseline is the evidence that an unarmed test build behaves as the release
does, which lets the fault cases, run only on the test build, stand for
release behavior; it is also the clean comparison for the controls. Each
control then runs on the test binary and may use only the fixtures that hold
its target checks. A control fires when one of those checks fails, and its
targets name the checks that identify the violated property rather than any
failure in the case. The driver reports an unfired control, or one whose
baseline failed, as a broken check.

Each case keeps its own witness of everything it supplies under the evidence
folder, and inventories every archive (path, type, inode, size, mode, mtime,
SHA-256) before and after every command: an earlier entry may never change or
disappear (C6), except that a file first seen while a Stewart process was
still running may grow, keeping its earlier bytes as a prefix. Folders, homes
and working directories may not change at all, and a destination may only gain
entries once a run can deliver.

### Provider, network and witnesses

- The fake Messages API (`fake_provider.py`) listens only on `127.0.0.1` with
  port 0, and the driver connects only to ports its own listeners hold; both
  rules are enforced in code. Modes: plain HTTP
  (`STEWART_PROVIDER_URL=http://127.0.0.1:PORT`, release and test binaries),
  HTTPS with the test CA (`STEWART_TEST_TLS_ROOT`, test binary), and HTTPS to
  `provider.test` through the CONNECT proxy (`HTTPS_PROXY`). The case where the
  binary itself resolves `provider.test` runs only with `--network-isolated`.
  Where listening is not permitted, cases needing the fake skip with
  "loopback listening unavailable".
- What the fake accepts is declared as data: the request members of the pinned
  API version, the members of `output_config`, the effort levels and on-demand
  `compaction`. A gate judges every request body against it before the case's
  responder answers, and refuses a mismatch as the Messages API does. A case
  that needs a provider which has moved away from what the release sends
  changes one fact of that model.
- Witnesses outside every archive, under the case's evidence folder: each
  request and response byte for byte (`provider-<label>/`), CONNECT requests
  and tunnel counts, the auditor's goals, calls, replies and anomalies
  (`SUMMARY.json`), and the expected answer, rendering and manifest bytes
  computed by `answer_witness.py` from the goals and the material witness.
- Accounting: each attempt's charge under INTERFACE 6.4 is computed by the
  fake from what it did (reported usage, replacing top-level totals with valid
  iteration sums when supplied; an estimate for a lost response; or none);
  `run_ended` usage, run and status allowances and re-entry allowances are
  compared with those sums. A case that kills a run before an attempt record
  exists overrides that attempt's charge to the estimate 6.4 states.
- Protocol timing (C9): for a response holding one tool call, the time from
  its last byte to the next request's connection. This interval includes writing
  captures and starting the next request. On every architecture the timing
  table reports the sample count, median, 95th percentile and maximum per
  operation and binary. These observations carry no qualification threshold.

### The two auditors

A scripted auditor (`procedure.py`) serves exact protocol-shape cases: a case
writes its calls as a generator and reads Stewart's actual replies.

`reacting_auditor.py` is a deterministic policy with a goal list (label, kind,
text, citations; optionally a draft replaced later, a text or base64 artifact,
or a deliberately refused first attempt). Per conversation it: reads the
question through every page; in the first conversation lists and reads every
material, checking pages, ranges, `cite` and `lines` against the witness and
the 7.2 page rule; calls `what_am_i_working_with` through every page and reads
every listed entry by its handle, matching entries to goals by label and bytes;
then records the goals it cannot see (several calls per response when
configured), replaces drafts, prepares, reads both prepared views and compares
them with the witness bytes, dry-runs and submits with `confirm: true`. It
follows the replies' `next` calls for pages. At configured mutation counts it
emits an opaque `compaction` block in an ordinary response and discards its own
memory. This tests re-entry after fake memory loss; it does not exercise provider
summary requests or establish live model compaction. Every new conversation
(a continuation after a kill) starts with empty memory. It never consults
earlier replies except through its memory. Because it re-adds only what
re-entry does not show, an omitted entry produces a duplicate, and the
duplicate is counted in the selection bytes Stewart produced. Endings:
`submit`, or `ordinary` (end the turn; after the reminder either submit or end
again).

Both auditors check each reply as it arrives (envelope, `is_error`, effects,
no host paths or manager identifiers, the tool results answering exactly the
calls just made); the reacting auditor also checks each conversation's first
message, citations as recorded, allowances against the fake's charges, and the
reminder and near-limit text with their once-per-audit allowance. Each failed
expectation becomes a failed check, and a case judging the same run does not
repeat these comparisons after the fact.

## `acceptance.sh`: the scripted acceptance tier

```sh
sh apparatus/acceptance.sh "$PWD/.scratch/acceptance-NN"  # from the repository root; NN not yet used
```

One container suite runs the whole driver on Linux aarch64 and x86_64 offline.
The arm64 guest executes x86_64 binaries through Rosetta. It needs
the toolchain images and `service/vendor` from `step2.sh`, and pulls the pinned
python image (its only network use). It archives `service`, `apparatus`,
`docs` and `examples` from `HEAD` (the driver compares its pinned texts and
examples with `docs/` and runs the walkthroughs in `examples/`), and for each
architecture, offline:

1. builds the release and fault/sabotage binaries and runs the same static
   linkage check on both and on a tiny dynamically linked C executable, which
   must be rejected;
2. runs the independent release driver's self-test and every case, unprivileged,
   with loopback only. The driver also checks which build carries the test-only
   names. Each assigned sabotage and driver control must fire;
3. exports the evidence. On failure, or when requested with `all`, it retains
   working copies in `driver-<arch>/work.tar`. The named container remains
   available through review.

`host/DONE` reports `failures=N`; `host/SUMMARY` gives the self-test line and
the driver's counts per architecture; `driver-<arch>/evidence/` holds the
driver's full results, and `driver-<arch>/selftest.stdout` its self-test.
When requested, the work archive keeps regular-file bytes and Linux
names/modes/links in a single host file; tar warnings about special specimens
are retained. Failed working trees, and all working trees under `all`, remain
in the named driver containers, including special files. Remove reviewed
containers and generated payloads under the retention rules below. Use
`sh apparatus/acceptance.sh RUN all` when a named investigation needs passing
witnesses and working copies as well as failures.
Build containers are removed on exit.

### Development runtime acceptance

Run `sh apparatus/runtime-acceptance.sh "$PWD/.scratch/runtime-NN"` to exercise
the source-only adapter on Linux ARM64 and x86_64. This independent job builds a
featureless release, a development writer and a distinct fault-enabled
development writer. It checks that the adapter markers are absent from the
release and present in both writers, and runs the standalone driver's self-test
and full synthetic case inventory on each platform.
Each run retains its own `host/DONE`, per-platform results under
`driver-<arch>/runtime-evidence/` and the complete `runtime-work.tar`,
including launch witnesses outside the evidence directory. See the
[runtime driver guide](driver/CLAUDE-CODE.md). Record this suite with
`qualified.py extract .scratch/runtime-NN --suite runtime`.

## Evidence retention

Evidence folders under `.scratch/` follow "Evidence and retention" in
[DEVELOPMENT.md](../development/DEVELOPMENT.md#evidence-and-retention). After a run of
`acceptance.sh` or `step2.sh`, `qualified.py extract` reads it into the
qualification record (`--suite acceptance` or `--suite toolchain`); commit
`qualified.json` and `qualified.md` together. A special entry such as a socket
in an exported runtime evidence tree is recorded as a qualification failure.
The tree digest binds its path and file type with a marker; it never opens the
entry or counts it as a regular evidence file. This permits a failed run to be
recorded without changing its originals. Links and unreadable required fields
still prevent extraction.

`qualified.py candidates` lists
the folders that nothing keeps, under the rules in DEVELOPMENT.md, as removal
candidates; removal is by hand, and only after a run that exits 0.
