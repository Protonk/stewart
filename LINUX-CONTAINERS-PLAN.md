# Linux testing and development on this Mac

Execution plan prepared 2026-10-17 for a fresh Astra-class agent.

Status: research complete; implementation, installation, and Linux validation
have not started. The user requested this local plan after reviewing the five
stages below. Installing Apple's container tool is an intended part of execution.
This document is temporary execution state, not shipped guidance. Update it as
work proceeds; remove it only after its contracts have reached implementation,
tests, and durable documentation. Keep evidence under ignored local storage.

## Objective and execution contract

Establish a repeatable Linux test environment hosted on this Apple Silicon Mac,
resolve the observed Linux failures with evidence, add a native Linux regression
gate, and make persistent Linux development practical without losing the ability
to validate from a fresh environment.

Read [AGENTS.md](AGENTS.md) before work. Preserve unrelated changes. Carry the
five stages through their exit criteria, rather than stopping after a container
boots or the smoke suite passes. Use judgment on filenames and implementation
details; the behavioral contracts below matter more than this proposed layout.
When an external dependency prevents a stage from completing, record the exact
remaining action and continue independent local work. Do not describe prepared
configuration as an executed qualification.

Use explicit Python interpreter paths with `-I`, and `-B` for development checks.
Preserve `scripts/check.py` as the installed-wheel validation entrypoint. Do not
introduce editable installs, `PYTHONPATH` selection, parent-project helpers,
compatibility shims, or a second pytest policy. Existing deliberate unisolated
startup controls in tests remain controls; do not mechanically add `-I` to them.
Runtime custody rules and historical receipts remain unchanged by infrastructure
work. Any confirmed runtime fix must preserve those contracts.

Installing the signed container tool, provisioning local images and volumes,
and creating a local development environment are part of this plan. Use the
environment's normal approval mechanism for privileged installation or sandbox
restrictions. Do not mistake this plan for permission to publish images, push
branches, change GitHub branch protection, spend real harness requests, or remove
existing user containers, volumes, or checkouts. Prepare reviewable local work
before raising an external activation dependency.

## Starting observations: recheck, do not assume current

- Checkout at review: commit `76d331c`, clean working tree. Remote:
  `https://github.com/Protonk/stewart.git`. No container definitions or CI workflow
  were present.
- Host reported arm64, macOS 26.7.1. `container` was absent from PATH and from
  `/usr/local/bin/container` and `/opt/homebrew/bin/container`.
- `/opt/homebrew/bin/python3.11` and `/opt/homebrew/bin/python3.14` were available.
  Resolve actual interpreters again and record versions at execution time.
- [README.md](README.md) currently qualifies Apple Silicon macOS with Python
  3.11 and 3.14 only. Runtime dependencies are the standard library, Git, and a
  POSIX shell. Build and test dependencies are in [requirements.lock](requirements.lock).
- The existing `.scratch/check-result.json` was a Python 3.14 smoke result:
  691 collected, 20 selected, 671 deselected, 20 passed. It is historical local
  evidence, not a current full-suite result. Do not overwrite it or bake these
  counts into a new gate.
- The reported Linux failures have not been reproduced here, and no failing
  node list was supplied. Obtain available reports, but do not block fresh
  reproduction on receiving them.

Relevant implementation and tests:

| Location | Why it matters |
| --- | --- |
| [scripts/check.py](scripts/check.py) | Offline private venv, wheel build/install, staged suite, plugin isolation, result and artifact retention. |
| [tests/conftest.py](tests/conftest.py) | Actual collected/selected nodes, outcomes, timings, plugin origins, private manager storage. |
| [tests/test_runner.py](tests/test_runner.py) | Runner budgets and nested invocations reuse the provisioned wheelhouse. |
| [tests/test_distribution.py](tests/test_distribution.py) | Exact wheel membership and sdist-to-wheel validation; plans must not enter archives. |
| [tests/test_stewart_launch_profile.py](tests/test_stewart_launch_profile.py) | Direct `/bin/zsh` invocations as well as `/bin/sh`. |
| [tests/test_auditor_runtime.py](tests/test_auditor_runtime.py) | Search-only ancestor permissions, descriptor traversal, non-root behavior. |
| [tests/test_stewart_inventory.py](tests/test_stewart_inventory.py) | FIFO, symlink, and unreadable-file coverage; one assertion is conditional on UID. |
| [src/stewart/_bootstrap.py](src/stewart/_bootstrap.py) | No-follow descriptor reads; `O_SEARCH`/`O_PATH` traversal; exclusive creation. |
| [tests/test_stewart_real_harness.py](tests/test_stewart_real_harness.py) | Opt-in invocation check; it does not prove sandbox enforcement. |
| [tests/acceptance.py](tests/acceptance.py) | Independent installed-wheel lifecycle acceptance with explicit isolation prerequisites. |
| [tests/parity_vectors.py](tests/parity_vectors.py) | Existing byte-contract vectors useful for cross-host comparisons. |

Important runner behavior: `--result` determines the parent of retained fixture
directories, and those directories become pytest's `--basetemp`. Putting the
result on a Mac bind mount also puts test repositories there. The runner's `.log`
captures provisioning/build commands; pytest output inherits the terminal and
needs separate transcript capture. `--total-budget-seconds` checks elapsed time
after execution; it is not a hard process timeout.

## Architecture to implement

Use standard OCI images with a Debian/glibc baseline, native arm64 locally, and
Python 3.11 and 3.14 variants. Keep one shared guest-side check entrypoint usable
under Apple container and a native Linux engine. Avoid a general container-engine
abstraction unless actual differences require it.

The qualification topology is:

```text
identified source snapshot + provisioned toolchain image
                         |
                         v
Linux guest, ordinary user, ext4 workspace
  source / temporary environments / fixture repos / results
                         |
                         v
scripts/check.py -> installed wheel -> staged pytest suite
                         |
                         v
retained Linux artifacts -> verified export to Mac or CI artifact storage
```

Use host bind mounts only as an explicit development convenience or comparison
case. Qualification fixtures, manager storage, temporary environments, and results
belong on Linux storage. Keep source selection and interpreter paths explicit.
Separate disposable test runs from persistent development state.

Suggested deliverables:

- `containers/Containerfile`: pinned toolchain and Python variants.
- A narrow image build context and appropriate ignore rules, verified against
  the selected builder rather than assumed from Docker behavior.
- `scripts/check-linux.sh` or a small equivalent host wrapper, plus a shared
  guest entrypoint if needed. Provide useful `--help` and actionable failures.
- `.github/workflows/linux.yml`: native Linux validation using the same recipe.
- A development-image target or `containers/Containerfile.dev`, plus a small
  creation/entry/backup workflow for the persistent environment.
- Durable instructions in README and a dedicated development document if useful.

Keep container tooling out of the runtime wheel. Decide explicitly whether the
source distribution supports the container workflow; if it does, include the
recipe and supporting files together and verify them through the archive tests.
Do not ship scripts that require omitted files. Exclude this plan, `.scratch`,
host virtualenvs, Git administration, and generated artifacts from distributions.

## Stage 1: install and establish the Linux test command

1. Record current Git status, host architecture/OS, available storage/memory,
   interpreter versions, and existing container resources. Create a unique
   `.scratch/linux-container/<run-id>/` evidence directory. Keep an execution
   ledger here and in this plan; never reuse a previous result destination.
2. Review the official release and versioned documentation below. Research found
   Apple container 1.5.0; use it as the initial candidate, but check current
   release/security information before installing. If selecting another version,
   record the reason, exact installer, digest, and corresponding documentation.
   Reuse an appropriate existing installation instead of silently replacing it.
3. Download Apple's signed installer from its official release assets, verify
   its package signature, retain the verification output and SHA-256, and install
   using the normal macOS installer approval path. Start `container system` and
   capture its version/status. Do not build Apple's Swift project just to get
   the CLI. Prove a simple native arm64 Linux command runs.
4. Build a toolchain image for each selected Python minor. Pin exact base image
   references by digest; record Python patch versions, distro and installed Git/
   shell versions. Include Git at the path required by acceptance, `/bin/sh`,
   `/bin/zsh`, certificates, venv/pip support, and a non-root account. Set a known
   locale, umask, and clean guest user configuration. Do not inherit host Git or
   Python configuration. Start with modest measured resources, e.g. 4 CPUs and
   4 GiB per active test guest if the host can support it; serialize full runs.
5. Provision the hash-locked wheelhouse while building with network access:
   use the selected Python with `-I -B -m pip download --only-binary=:all:
   --require-hashes -r requirements.lock`. Make the wheelhouse available at a
   stable guest path for nested runner tests. Do not reuse a host virtualenv.
   Existing pure-Python wheels can be a verified seed, not an implicit dependency.
6. Create an ext4 workspace with explicit ownership for the test user. Verify
   the actual filesystem, UID, and permissions from inside the guest. Select an
   explicit Linux `TMPDIR` and guest-local result path. Run `scripts/check.py`
   first with `--fast`, then without it, using `-I -B` and the provisioned wheels.
   These runs must not download dependencies. Disabling pip's index is distinct
   from enforcing network denial; label each fact accurately.
7. Expose a simple wrapper interface for Python selection, smoke/full checks,
   output destination, and extra pytest selectors. Preserve the underlying
   runner's argument handling. Do not require the caller's current directory to
   be the repo root. Stage 2's retention behavior is required before relying on
   disposable full runs.

Example guest invocation shape (paths are illustrative container coordinates,
not constants to introduce into Stewart runtime logic):

```sh
STEWART_GUEST_PYTHON=/usr/local/bin/python3.11
"$STEWART_GUEST_PYTHON" -I -B /work/source/scripts/check.py \
  --wheelhouse /opt/stewart/wheelhouse \
  --result /work/runs/unique-run/result.json
```

Exit evidence: installer/version record; image identities and build logs;
non-root/ext4 preflight; a smoke run with actual counts; a full run with retained
results whether green or red. A red suite is valid discovery for the next stage,
not a reason to suppress tests or declare this infrastructure unusable.

## Stage 2: source identity, failure retention, and wrapper validation

Implement alongside Stage 1 so the first meaningful failures survive.

1. Snapshot the source bytes being tested, including tracked modifications,
   deletions, and relevant untracked source/build files. A bare `git archive HEAD`
   is insufficient for everyday development. Use an explicit source/build input
   selection that excludes `.git`, `.scratch`, virtualenvs, caches, secrets, and
   this plan. Record HEAD separately from a manifest/digest of actual staged
   inputs. Verify the copied snapshot inside Linux against that manifest. Do not
   follow source links out of the selected tree; make unsupported inputs explicit.
2. Keep all active test data on ext4. Use a named volume or other verified Linux
   storage with fresh run directories. Image layers can hold the immutable tools;
   the mutable source and artifacts need clear ownership and lifecycle. Do not
   attach a single writable filesystem to concurrent guests without establishing
   that the runtime supports it; separate volumes or serialize ownership.
3. Capture wrapper and guest stdout/stderr as well as the runner's build log.
   Preserve the result JSON, built wheel, fixture tree, source snapshot/manifest,
   selector arguments, timings, image digest, Linux kernel/distro/architecture,
   Python/Git/shell versions, effective UID/GID, filesystem/mount observations,
   resource allocation, and Apple runtime version. Retain a clear failure record
   when setup fails before pytest can produce result JSON.
4. Propagate the actual check exit status through logging/export/cleanup. An
   export failure must also make the wrapper fail and identify the still-retained
   guest data; it must not hide a test failure. Handle interruption without
   discarding completed diagnostics. Keep test outcomes separate from transport
   and setup failures. Avoid a new custody-receipt schema for test orchestration.
5. Export diagnostics only after the run. Fixture trees deliberately contain
   planted links and special files: archive inside Linux without dereferencing
   links or reading FIFOs/devices, and record any entries the archive cannot
   represent. Prefer exporting the regular archive plus a digest over recursively
   materializing hostile fixture trees on the Mac. Verify the export before
   removing run-owned resources. Keep original guest paths and bytes intact;
   an export index can describe their new location without rewriting receipts.
6. Account for Apple's `container cp` requiring a running container. Keep an
   export helper alive, or attach retained storage to a separate helper after
   the test container stops. Do not use `--rm` in a way that destroys the only
   copy of evidence. Cleanup targets must come from the current run's resource
   inventory, never broad container/volume prune commands.
7. Add meaningful behavioral coverage for the wrapper boundaries: a passing
   selection, a deliberately failing selected test whose artifacts and nonzero
   status survive, and an invariance run from an unrelated/quoted host path.
   Demonstrate that a dirty source edit reaches Linux and a missing wheel causes
   an actionable offline failure. Use small disposable probes rather than
   repeatedly executing the full suite for orchestration tests.

Exit evidence: repeatable green and intentionally red wrapper checks, source
identity verified across transfer, artifacts inspectable on the host, and
resource cleanup that leaves evidence and unrelated resources intact.

## Stage 3: reproduce, explain, and fix Linux failures

1. Capture full baseline runs for the same source snapshot on macOS and native
   Linux arm64, each with Python 3.11 and 3.14. Use the provisioned wheelhouse and
   existing runner on both hosts. Compare actual node sets, per-node outcomes,
   skip reasons, and configuration/plugin observations. Different Python patch,
   Git, and shell versions are recorded variables, not automatically OS effects.
2. Build a failure ledger with node ID, exact environment/run, raw diagnostic,
   competing explanations, smallest distinguishing comparison, and conclusion.
   Read failures before choosing experiments. Missing zsh and UID 0 are known
   setup risks, not established causes of the user's report.
3. Investigate setup discrepancies first, then runtime differences. Useful paired
   comparisons include ordinary user versus root, Linux ext4 versus the same
   Linux process using a Mac share, shell choice, and Python/Git versions. Keep
   the other variables fixed where practical. Use a deliberate firing control,
   a case differing in the measured property, and an invariance case. Do not
   accept skips, broad xfails, or a weaker custody invariant as portability fixes.
4. Prioritize descriptor-relative ancestor traversal, `O_SEARCH`/`O_PATH`,
   no-follow behavior, exclusive writes, unreadable bytes, FIFOs/sockets, linked
   and nested workspaces, case-sensitive paths, and Git worktree/ref transactions
   when failures point there. Check stable refusal reasons rather than equating
   host-specific prose or errno text. Preserve invalid historical records.
5. Make the smallest supported implementation or test correction. Missing test
   prerequisites belong in the toolchain/documentation; an actual runtime defect
   needs a regression test. Run targeted checks during diagnosis, then the
   relevant full matrix after fixes. Once required checks pass, repeat only for
   new changes, failures, or unresolved concerns.
6. Compare `--parity-output` byte-contract vectors across hosts where useful;
   retain wheel identities separately. Do not expect OS observations such as
   errno prose or absolute paths to be byte-identical. Preserve offline sdist
   rebuild and wheel-membership checks.
7. Establish timings before enforcing performance budgets. Do not transplant
   macOS's example time limits into a virtualized Linux gate without measurement.
   If a hard timeout is introduced, verify process termination and artifact
   retention separately from the runner's existing budget reporting.
8. Keep `STEWART_PROBE_REAL_HARNESS` unset for the ordinary lane and report its
   observed skip. Actual harness invocation and shell/file-tool enforcement
   require their own explicitly selected executable/profile and paired access
   probes. Passing core tests or rendering settings does not qualify either.

Exit evidence: current full results on both local hosts/Python versions, explained
node-set differences and skips, confirmed defect comparisons, regression tests,
and an explicit statement of what remains unqualified.

## Stage 4: native Linux CI and independent acceptance

1. Recheck the GitHub remote and repository CI settings that are accessible.
   Prepare `.github/workflows/linux.yml` with a native amd64 Linux runner and
   Python 3.11/3.14 image variants. Use the same image recipe, guest command,
   non-root account, and output contract as local Apple-container runs. Pin
   action revisions and base images, retain test artifacts on failure, and keep
   workflow permissions narrow. No public image registry is required: CI can
   build locally from the checked-out inputs.
2. Ensure CI's fixture directories are on its Linux filesystem, with explicit
   ownership. Exercise both successful and deliberately failing artifact/status
   paths in small probes before relying on the gate. Use full suite selection
   for the required Linux checks; smoke remains a convenience command.
3. Validate an actual native amd64 run. An Apple `--arch amd64` run uses Rosetta
   translation and can provide additional diagnostic evidence, but cannot stand
   in for the native runner. Record execution architecture and translation mode.
   If remote activation needs a push or permission unavailable in the execution
   session, finish the local workflow and identify the concrete activation step.
   Do not label native CI qualified until a real run has been inspected.
4. Run `tests/acceptance.py` against a freshly installed retained wheel in a
   provisioned guest, without the source checkout available as an import source.
   Satisfy its documented prerequisites: no host-shared directories, networking
   disabled, a fresh destination, and prior paired qualification of the
   `--unavailable` path under the same guest/user/interpreter configuration.
   Do not pass an arbitrary nonexistent path and call that isolation evidence.
5. Build that qualification explicitly: a disposable sentinel must be readable
   in the deliberately exposed control and unavailable in the restricted case;
   a permitted guest-local file remains readable in both. Similarly demonstrate
   networking works in the connected control and is denied under the selected
   restriction, with a guest-local invariant. Use an endpoint under our control
   where possible so a public outage does not masquerade as enforced denial.
   Verify the runtime's actual isolation mechanism; do not assume Docker flags
   are supported by Apple container or infer denial from pip's offline settings.
   Apply the restriction to the guest configuration being accepted, then export
   artifacts through management facilities or retained storage afterward.
6. Record acceptance's actual check/command counts separately from pytest counts.
   If Apple container cannot enforce a prerequisite with the selected version,
   retain that limitation and qualify acceptance in an appropriate native Linux
   environment. Keep local Linux suite evidence distinct from acceptance and
   harness-enforcement claims.
7. Update durable support documentation to name demonstrated combinations of
   OS/distro, architecture, Python, filesystem, and user conditions. Retain the
   macOS validation path. Explain how to refresh pins and reproduce CI locally.

Exit evidence: inspectable native amd64 CI results, artifact retention and exit
propagation, separately qualified installed-wheel acceptance, and a support
statement that matches those observations. A committed workflow alone is partial.

## Stage 5: persistent Linux development

1. Begin with the host checkout as the editing source and the tested snapshot
   wrapper as the Linux feedback loop. Document one command each for smoke,
   full validation, selecting Python, and inspecting the latest run. Never share
   a macOS virtualenv with Linux.
2. Build a persistent development image from the same toolchain recipe. Prefer
   Apple's `container machine`, which needs an init-capable image; a plain Python
   application image is not automatically suitable. Include only development
   services actually needed. Create a named environment with explicit resource
   limits and `--home-mount none` to avoid the default whole-home share. Verify
   that the login user is unprivileged and that the intended checkout resides on
   Linux storage. No nested virtualization is required for this project.
3. Establish one writable authoritative checkout in Linux, including Git history
   and any intended uncommitted work. Do not blindly copy a linked worktree's
   `.git` pointer to another OS. Transfer through a valid standalone clone/bundle
   plus identified working-tree changes, or another verified self-contained
   method. Confirm refs, file contents, modes, and dirty status before using it.
   Keep the existing Mac checkout intact as a transition fallback; identify
   which copy is authoritative to prevent accidental divergent editing.
4. Prove an interactive terminal can edit, invoke Git, run a small selected check,
   and inspect artifacts entirely inside Linux. Then verify the user's existing
   editor can work against that same checkout through its supported remote
   mechanism. A terminal editor is a complete initial editing path; treat GUI
   integration as unverified until exercised. If the preferred editor cannot be
   inferred, ask that narrow preference while continuing terminal/backup work.
   Do not assume Apple container supplies Docker's API or automatic Dev Containers
   integration. Avoid mounting the entire Mac home to solve editor access.
5. Keep the disposable qualification path available from the persistent workflow.
   The Mac may orchestrate fresh test guests from a snapshot of the Linux checkout;
   do not add Docker-in-Docker merely to launch tests from the development shell.
   Verify the snapshot identity in this direction too. Tests passing only after
   manual package installation in the development machine are not reproducible.
6. Design storage and backups before making Linux the daily primary environment.
   Verify checkout survival across stop/start. Machine persistence does not imply
   survival of machine deletion: use a supported separate volume if available,
   or explicit backups with a tested restore procedure. Preserve both Git history
   and uncommitted/untracked work. Never rely on Git push alone as a dirty-tree
   backup. Exercise recovery into a second fresh environment without deleting
   the original. Retain source manifests and compare the restored contents.
7. Demonstrate a complete small edit/test/review loop in Linux, then recreate the
   environment from recipes and restore the checkout. Run clean validation on
   that restored source. Move the ordinary development commands into this
   environment once these checks pass; retain the Mac checkout and documented
   fallback until the user chooses to retire it.

Exit evidence: working Linux terminal/editor path, persistent authoritative
checkout, verified stop/start and backup/restore, a recreated toolchain producing
the same expected test behavior, and continued disposable validation. If GUI or
account integration is pending, describe the working terminal path and remaining
dependency precisely rather than claiming the whole transition is complete.

## Completion and handoff

Keep this ledger updated with concise evidence pointers, not copied transcripts:

| Stage | State | Evidence / remaining action |
| --- | --- | --- |
| 1. Tool installation and Linux command | Pending | No installation or Linux run yet. |
| 2. Source identity and retention | Pending | Wrapper not implemented. |
| 3. Failure diagnosis and fixes | Pending | Reported failures not reproduced. |
| 4. Native CI and acceptance | Pending | Remote known; workflow and qualification absent. |
| 5. Persistent development | Pending | No environment created. |

After each substantial action record: command/log paths, selected versions,
resources created and their owner/purpose, actual selector/outcome counts,
confirmed findings, remaining hypotheses, and the next executable step. Preserve
this information across context changes. Keep absolute local evidence paths in
this temporary plan or ignored records, not durable guidance or runtime logic.

Before declaring completion, verify all five exit criteria; inspect the final
diff; confirm archive membership; and report actual matrix results, expected
skips, acceptance results, known limitations, and the commands a developer now
uses. Durable documentation must stand on its own without this plan. Remove
this file only after those contracts are represented in documentation/tests and
no required execution remains. If completion is blocked externally, retain the
plan with precise pending actions and finish all independent local work.

## Primary references

These were consulted for planning. Use documentation matching the version
actually installed and refresh unstable details before implementation.

- [Apple container 1.5.0 release](https://github.com/apple/container/releases/tag/1.5.0).
- [Requirements and signed installation](https://github.com/apple/container/blob/1.5.0/README.md).
- [VM-per-container architecture](https://github.com/apple/container/blob/1.5.0/docs/technical-overview.md).
- [Bind mounts, ext4 volumes, and lifecycle](https://github.com/apple/container/blob/1.5.0/docs/volumes.md).
- [CLI reference: build, run, copy, machines](https://github.com/apple/container/blob/1.5.0/docs/command-reference.md).
- [Persistent machines and home sharing](https://github.com/apple/container/blob/1.5.0/docs/container-machine.md).
- [Multiplatform images and Rosetta](https://github.com/apple/container/blob/1.5.0/docs/multiplatform-images.md).
- [Networking](https://github.com/apple/container/blob/1.5.0/docs/networking.md).
