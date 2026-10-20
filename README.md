# Stewart

Stewart keeps local custody records for bounded audits of Git projects. The
installation, maintainer checkout and auditor checkout are separate locations.
Its runtime uses Python 3.14 or newer, Git and a POSIX shell. Harness profiles
are optional and require their explicitly named harness executable.

Install a locally built wheel into a dedicated virtual environment, then use
`<venv>/bin/stewart --help` or `<venv>/bin/python -I -m stewart --help`.
Custody commands require explicit `--repo` and `--workspace` arguments.
`<venv>/bin/stewart docs manual` prints the bundled manual outside any repository.

The [manual](src/stewart/resources/README.md),
[question guide](src/stewart/resources/QUESTION-TYPE.md) and
[conditional protocols](src/stewart/resources/AUDIT-PROTOCOLS.md) ship in the
wheel. `stewart docs auditor`, `maintainer`, `agents` and `claude` print generic
role templates for a new workspace such as `audits/parser-review`.

Build and test dependencies are hash-locked in `requirements.lock`. Provision
their wheelhouse before running `scripts/check.py`; the runner performs no
network downloads and tests an installed wheel in a private environment.
Builds use Hatchling's [wheel builder](https://hatch.pypa.io/1.13/plugins/builder/wheel/)
and [version-file selection](https://hatch.pypa.io/1.13/version/), without Git metadata.

For a source checkout, provision the build environment and wheelhouse while
network access is available. Use absolute paths for these variables:

```sh
STEWART_SOURCE=/absolute/stewart-project
STEWART_BASE_PYTHON=/absolute/python3.14
STEWART_BUILD=/absolute/stewart-build-venv
STEWART_WHEELS=/absolute/stewart-wheelhouse
"$STEWART_BASE_PYTHON" -I -m venv "$STEWART_BUILD"
"$STEWART_BUILD/bin/python" -I -m pip download --only-binary=:all: --require-hashes -r "$STEWART_SOURCE/requirements.lock" --dest "$STEWART_WHEELS"
"$STEWART_BUILD/bin/python" -I -m pip install --no-index --find-links "$STEWART_WHEELS" --require-hashes -r "$STEWART_SOURCE/requirements.lock"
```

Build both archives offline, including the wheel from the source archive, then
install that wheel in a fresh runtime venv. The version comes from
`src/stewart/_version.py`; no `.git` directory or VCS plugin is needed.

```sh
"$STEWART_BUILD/bin/python" -I -m build --no-isolation --outdir "$STEWART_SOURCE/dist" "$STEWART_SOURCE"
STEWART_ENV=/absolute/stewart-venv
"$STEWART_BASE_PYTHON" -I -m venv "$STEWART_ENV"
"$STEWART_ENV/bin/python" -I -m pip install --no-index --no-deps "$STEWART_SOURCE/dist/stewart-0.1.0-py3-none-any.whl"
STEWART_PYTHON="$STEWART_ENV/bin/python"
"$STEWART_PYTHON" -I -m stewart docs manual
```

In an ordinary Git project, create and customize role guidance before preparing
an assignment. The project needs neither Stewart source nor its own venv:

```sh
cd /absolute/audited-project
mkdir -p audits/parser-review
"$STEWART_PYTHON" -I -m stewart docs auditor > audits/parser-review/AUDITOR.md
"$STEWART_PYTHON" -I -m stewart docs maintainer > audits/parser-review/MAINTAINER.md
git add -- audits/parser-review/AUDITOR.md audits/parser-review/MAINTAINER.md
git commit -m "Define audit roles"
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review init --audit-id parser-fields --input path/to/parser.py --replace-prompt
# Complete PROMPT.md's question, evidence, scope and stop condition, then commit it alone.
git add -- audits/parser-review/PROMPT.md
git commit -m "Assign parser field audit"
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review prepare --mode snapshot
```

Follow the printed handoff and the manual's collection, triage and close steps.
To continue later, or from another maintainer checkout, `stewart --repo "$PWD"
discover` lists every audit, resource and request key the repository records,
and `select --audit-id ID` prints a reference to keep and pass back with
`--ref`; mutations accept `--request-key` so a retry returns the recorded
outcome instead of repeating it. `resource create-worktree` and
`create-directory` record the manager worktrees, branches and directories an
audit uses so that `close` can retire them once no audit uses them.
Orchestration on top of these interfaces is planned in
[ORCHESTRATION-PLAN.md](ORCHESTRATION-PLAN.md) and not implemented yet.
`--repo` must be the exact maintainer worktree root; subdirectories and
registered auditor worktrees are refused. Sessions live under the repository's
Git common directory at `stewart/sessions/`, outside every working tree, so no
ignore rule is needed. Each auditor checkout and its supplied runtime live in
a per-session directory under the checkout home
(`~/.local/state/stewart/checkouts` unless `prepare --checkout-home` names
another); private manager deployments live under
`~/.local/state/stewart/managers`. The manager's harness needs write access to
both custody locations, which `status` names. Keep private storage out of
auditor grants. `close` retires a finished or abandoned audit, keeping one
closing record. Historical schemas require their creating installation; new
versions never rewrite old records for compatibility.

Run the standalone suite against a fresh wheel with Python 3.14:

```sh
"$STEWART_BUILD/bin/python" -I -B "$STEWART_SOURCE/scripts/check.py" --wheelhouse "$STEWART_WHEELS" --result /absolute/stewart-results.json
```

For a short development check, add `--fast` to select only `smoke and not
heavy`. Full validation omits that flag. Other arguments go to pytest
unchanged: `-k` expressions, or test files and node IDs named relative to the
staged suite root, which mirrors the project root
(`tests/test_runner.py::test_budget_charges_all_phases_and_ignores_node_names`).
A selection that collects a node more than once, such as a file together with
one of its node IDs, or a test outside the staged `tests` directory, is
refused, and a run that exits without writing its receipt fails. Add
`--test-budget-seconds 4` to fail on any test whose setup, call and teardown
exceed four seconds; add `--total-budget-seconds 120` to bound the complete
invocation, including the private environment and wheel build. Choose budgets
appropriate to the host. The result records all collected and selected nodes,
outcomes, plugin origins, per-phase durations and budget overruns. Test
success does not erase a budget failure. Only the selected pytest's built-in
plugins and the staged suite's own conftest are admitted; containing-project
and third-party plugins refuse.

The tests reach Git through PATH. On macOS `/usr/bin/git` is Apple's shim,
which locates the developer tools' Git on every call. By default
(`--git-executable auto`) the check resolves `xcrun --find git` once, requires
a regular executable that reports the shim's `--version` and an existing
`--exec-path`, both inside the `xcode-select -p` developer directory, and
writes a private `git` script that `exec`s that binary by absolute path
(`/bin/dash`, or `/bin/sh` without it). It inserts the script's directory
immediately before the PATH entry that supplied the shim, so earlier entries
keep precedence and only `git` changes: Apple's Git derives its exec path and
templates from the path it was invoked by, so a link or copy would break
them, and the developer directory itself holds other tools, `python3.9` among
them. On other platforms, or without a verified binary, PATH is unchanged and
the reason is recorded. `--git-executable path` leaves PATH alone.
`--git-executable /absolute/dir/git`, such as a wrapper that logs each call,
inserts that executable's directory the same way, or appends it when no Git
resolves. A different path to the same file, such as a link, does not count
as already selected; a request the insertion cannot reach is refused. The
check prints the selection, writes it to the `.log` and records it as
`git_selection` in the result, with the version and exec path that Git
reports under the tests' PATH and every name whose resolution changed.
Stewart itself still runs `git` by name, so inside the tests it reaches the
selected Git, and the experiment launcher passes that PATH to auditor
children. Tests that build PATH without the inherited value (for example from
`os.defpath`) do not see the selection; those that extend the inherited PATH
do.

Development and acceptance target Apple Silicon macOS with Python 3.14.
POSIX APIs alone do not establish Linux or other-host support; qualify those
hosts separately. Harness enforcement also needs its own explicit qualification.
The installed interpreter and its environment hooks remain trusted: isolated
mode ignores caller Python variables and the user site, but environment `.pth`
files and `sitecustomize` can still execute. The source bootstrap is available
as `<python> -I -B /absolute/project/src/stewart/_bootstrap.py source -- ...`;
do not use `PYTHONPATH` to select a source installation.
