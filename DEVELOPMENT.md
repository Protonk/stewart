# Developing Stewart

This document covers building Stewart from source and running its test suite.
[AGENTS.md](AGENTS.md) states the development rules and custody contracts that
changes must keep, and the [manual](src/stewart/resources/README.md) documents
the installed tool. Development commands name an explicit interpreter and use
isolated startup (`-I`, plus `-B` where bytecode must stay unwritten).

## Build and provisioning

Build and test dependencies are hash-locked in
[`requirements.lock`](requirements.lock). Builds use Hatchling's
[wheel builder](https://hatch.pypa.io/1.13/plugins/builder/wheel/) and
[version-file selection](https://hatch.pypa.io/1.13/version/), without Git
metadata: the version comes from `src/stewart/_version.py`, and no `.git`
directory or VCS plugin is needed.

Provision the build environment and wheelhouse, and build and install a wheel,
as the README's [Installation](README.md#installation) section shows. The
commands below reuse its absolute-path variables `STEWART_SOURCE`,
`STEWART_BUILD` and `STEWART_WHEELS`. Provision while network access is
available: `scripts/check.py` performs no network downloads, and its nested
boundary tests reuse the same provisioned wheelhouse.

## Running the suite

Run the standalone suite against a fresh wheel with Python 3.14:

```sh
"$STEWART_BUILD/bin/python" -I -B "$STEWART_SOURCE/scripts/check.py" --wheelhouse "$STEWART_WHEELS" --result /absolute/stewart-results.json
```

The runner builds a wheel, installs it into a private venv, and copies the
tests to an unrelated directory, where it tests the installed wheel. It selects
that copy's pytest configuration explicitly and disables inherited plugins and
options. Only the selected pytest's built-in plugins and the staged suite's own
conftest are admitted; containing-project and third-party plugins refuse.
Without `--wheelhouse` the runner uses `$STEWART_WHEELHOUSE`, else
`<project>/.scratch/wheelhouse`; without `--result` it writes
`<project>/.scratch/check-result.json`. `scripts/check.py --help` describes
every option.

For a short development check, add `--fast` to select only `smoke and not
heavy`. Full validation omits that flag. `--fast` owns the marker selection,
so it cannot be combined with `-m`.

### Selecting tests

Other arguments go to pytest unchanged: `-k` expressions, or test files and
node IDs named relative to the staged suite root, which mirrors the project
root:

```sh
"$STEWART_BUILD/bin/python" -I -B "$STEWART_SOURCE/scripts/check.py" --wheelhouse "$STEWART_WHEELS" --result /absolute/stewart-runner.json tests/test_runner.py::test_budget_charges_all_phases_and_ignores_node_names
```

A selection that collects a node more than once, such as a file together with
one of its node IDs, is refused, as is an empty selection, and so is a test
outside the staged `tests` directory named beside a staged path. pytest loads
the staged conftest only for staged paths: a selection naming only outside
paths runs those tests without the suite's boundary checks or private HOME, and
the invocation then fails because it wrote no receipt. Options that end pytest
before a session (`--version`, `--markers`) fail the same way.

### Time budgets

Add `--test-budget-seconds 4` to fail on any test whose setup, call and
teardown exceed four seconds; add `--total-budget-seconds 120` to bound the
complete invocation, including the private environment and wheel build. The
total budget is compared with the elapsed time once pytest ends; it does not
stop a run early. Choose budgets appropriate to the host. Test success does not
erase a budget failure.

```sh
"$STEWART_BUILD/bin/python" -I -B "$STEWART_SOURCE/scripts/check.py" --wheelhouse "$STEWART_WHEELS" --result /absolute/stewart-budget.json --test-budget-seconds 4 --total-budget-seconds 120
```

## Git selection

The tests reach Git through PATH. On macOS `/usr/bin/git` is Apple's shim,
which locates the developer tools' Git on every call. `--git-executable`
chooses which Git the tests reach:

- **`auto`** (the default). When git on PATH is that shim, the check resolves
  `xcrun --find git` once and requires a regular executable that reports the
  shim's `--version` and an existing `--exec-path`, both inside the
  `xcode-select -p` developer directory. It writes a private `git` script that
  `exec`s that binary by absolute path (`/bin/dash`, or `/bin/sh` without it),
  and inserts the script's directory immediately before the PATH entry that
  supplied the shim, so earlier entries keep precedence and only `git` changes.
  Apple's Git derives its exec path and templates from the path it was invoked
  by, so a link or copy would break them, and the binary's own directory
  (`<developer>/usr/bin`) holds other tools, `python3.9` among them. On other
  platforms, when git resolves elsewhere, or without a verified binary, PATH is
  unchanged and the reason is recorded.
- **`path`** leaves PATH alone.
- **`/absolute/dir/git`**, such as a wrapper that logs each call, inserts that
  executable's whole directory at the same place, or appends it when no Git
  resolves. Use a directory holding only `git`, and make a wrapper `exec` the
  real Git by absolute path: under the tests' PATH a wrapper that runs `git` by
  name finds itself. A different path to the same file, such as a link, does
  not count as already selected; a request the insertion cannot reach is
  refused.

The check prints the selection, writes it to the `.log` and records it as
`git_selection` in the result, with the version and exec path that Git reports
under the tests' PATH and every name whose resolution changed. Stewart itself
still runs `git` by name, so inside the tests it reaches the selected Git, and
the experiment launcher passes that PATH to auditor children. Tests that build
PATH without the inherited value (for example from `os.defpath`) do not see the
selection; those that extend the inherited PATH do.

## PATH for provisioning commands

The provisioning commands (`ensurepip`, both pip installs, the wheel build and
any `--parity-output` run) get the inherited PATH minus every entry in which
`rustc` resolves: pip runs `rustc --version` for its user-agent string even
with `--no-index`, and under a test's empty HOME a rustup proxy would start
installing a toolchain from the network. The check records those entries in
the `.log` and as `provisioning_path_removed` in the result. The tests keep the
inherited PATH; a test that starts pip itself gives it `path_without_rustc`
from `tests/support.py`.

## Results and retained evidence

Beside `<name>.json` (the `--result` path) a run keeps:

- `<name>.log`: the Git selection, the PATH entries withheld from
  provisioning, then provisioning and build;
- `<name>.pytest.log`: pytest's argv and cwd, then its stdout and stderr with
  each line labelled by stream, kept even when pytest stops before writing a
  result;
- `<name>-dist/`: the tested wheel;
- `<name>-artifacts-*/`: pytest's base temporary directory.

Each invocation replaces the two logs and adds an artifacts directory; a run
that writes no result leaves an earlier `<name>.json` in place, so use a fresh
result name per run.

The result records all collected and selected nodes, outcomes, plugin origins,
per-phase durations and budget overruns. It also records every phase outcome,
the markers and the owned test directory and private HOME of each node, the
installed member population, the wheel and its digest, the interpreter, digests
of the staged suite and of `check.py`, and the project's commit and
`git status` when the project is the top of its own Git work tree.

Once pytest has written this invocation's result, `check.py` removes the
directories of each node whose setup, call and teardown all passed within any
`--test-budget-seconds`, recording its plan in the result before the first
removal and each path's outcome after it. Failed, skipped, interrupted and
over-budget nodes and entries no node owns stay, and a run that leaves no
result of its own keeps everything. Add `--keep-node NODEID`, repeatable, to
keep passing evidence such as a comparison's controls. A named node with no
executed call on record (no call phase, or a skipped one, which is how pytest
reports skips and expected failures, or no usable result) fails the invocation
and nothing is removed, because an evidence run that lost its control is not
evidence. `--keep-artifacts all` removes nothing. Removal failures are printed
and recorded but change neither the exit status nor any test outcome.

## Retained runs and their removal

A run is what `check.py` leaves beside `<name>.json`. Its **record** is the
receipt, `<name>.log`, `<name>.pytest.log`, the tested wheel under
`<name>-dist/` and whatever the caller put beside them, such as an `.out`
stream. Its **artifacts directory**, `<name>-artifacts-*/`, is working state:
the test directories and private HOMEs the receipt describes. Left whole, a
full run's artifacts hold about 3.6 GB in 200,000 entries, nearly half of it
runtime capture archives and a third copies of the package, so two rules bound
them and nothing else is deleted:

1. **Each invocation reduces its own run.** The default `--keep-artifacts
   failed` removes the directories of every node that passed within budget
   once the receipt is written, as the previous section describes. A run made
   with `--keep-artifacts all` or `--keep-node` is an evidence run; the plan
   or report that needs it names it.
2. **An artifacts directory leaves when the run's purpose is served; the
   record stays.** `scripts/prune.py` is the only mechanism, and it never
   removes a record. Records stay beside the plan or report that cites them
   and are removed by hand with that plan, as [AGENTS.md](AGENTS.md) says of
   completed plans; they are never rewritten. Prune once a plan's findings are
   recorded, and before removing the plan.

```sh
"$STEWART_BUILD/bin/python" -I -B "$STEWART_SOURCE/scripts/prune.py"
"$STEWART_BUILD/bin/python" -I -B "$STEWART_SOURCE/scripts/prune.py" --apply
"$STEWART_BUILD/bin/python" -I -B "$STEWART_SOURCE/scripts/prune.py" --run identity/repair-314 --orphans --apply
```

Without `--apply` the script prints the plan and writes nothing. It walks
`--root` (default `<project>/.scratch`) without entering any run's
directories. Only a receipt binds an artifacts directory: the directory it
names must be a real directory beside it named `<name>-artifacts-*`. The
default plan takes every bound run whose outcomes all passed or were skipped,
with pytest and the runner exiting 0 and no budget exceeded, that selected no
evidence, and whose stem no tracked file of the project names (`git grep`,
which requires the project to be the top of its own Git work tree; the default
stem `check-result` is always named by this document). Everything else is kept
and its reason printed: a failed, over-budget or cited run, an evidence run, a
receipt naming a directory elsewhere or a link, a directory a running process
names, and an orphan no receipt binds. `--run NAME` plans the named run
whatever its outcomes and citations, where NAME is the receipt's path relative
to the root without `.json` or its bare stem when unique; a name matching no
receipt, an unbound run or one a running process names refuses the whole
invocation, and nothing is removed. `--orphans` plans unbound directories no
running process names.

With `--apply` the plan goes to `<root>/pruned/<timestamp>-<pid>.json` before
the first removal and each directory's result after it, and
`<name>.pruned.json` beside each pruned receipt names that record. Removal
checks each directory's device and inode against the plan, follows no links,
and restores owner permissions a test took away, as the retention pass does; a
refused removal is recorded, printed and fails the invocation.

## Qualification

Development and acceptance target Apple Silicon macOS with Python 3.14.
POSIX APIs alone do not establish Linux or other-host support; qualify those
hosts separately. Harness enforcement also needs its own explicit
qualification, separate from the settings a launch profile constructs. The
manual's [launch profile](src/stewart/resources/README.md#launch-profile)
section describes an opt-in check to run after a harness update, which drives
a profile's probe through the real harness and is skipped otherwise because it
spends a request. Socket checks require a host that permits a local Unix
socket, and unreadable-file controls require an unprivileged user.

## Running from source

The source bootstrap runs Stewart from a source checkout without installing
it:

```sh
<python> -I -B /absolute/project/src/stewart/_bootstrap.py source -- ...
```

Do not use `PYTHONPATH` to select a source installation; isolated mode ignores
it. The installed interpreter and its environment hooks remain trusted:
isolated mode ignores caller Python variables and the user site, but
environment `.pth` files and `sitecustomize` can still execute. The manual's
[manager quick start](src/stewart/resources/README.md#manager-quick-start)
describes the private deployment the source launcher makes under
`~/.local/state/stewart/managers`.
