# Stewart

Stewart keeps local custody records for bounded audits of Git projects. The
installation, maintainer checkout and auditor checkout are separate locations.
Its runtime uses Python 3.11 or newer, Git and a POSIX shell. Harness profiles
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
STEWART_BASE_PYTHON=/absolute/python3.11
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

Follow the printed handoff and the manual's collection/triage steps. `--repo`
must be the exact maintainer worktree root; subdirectories and registered auditor
worktrees are refused. Sessions stay under that checkout's `.scratch/stewart`;
supplied auditor runtimes and private manager deployments have separate roots.
Keep private storage out of auditor grants. Historical schemas require their
creating installation; new versions never rewrite old records for compatibility.

Run the standalone suite against a fresh wheel with either supported interpreter:

```sh
"$STEWART_BUILD/bin/python" -I -B "$STEWART_SOURCE/scripts/check.py" --wheelhouse "$STEWART_WHEELS" --result /absolute/stewart-results.json
```

For a short development check, add `--fast` to select only `smoke and not
heavy`. Full validation omits that flag. Add `--test-budget-seconds 4` to fail
on any test whose setup, call and teardown exceed four seconds; add
`--total-budget-seconds 120` to bound the complete invocation, including the
private environment and wheel build. Choose budgets appropriate to the host.
The result records all collected and selected nodes, outcomes, plugin origins,
per-phase durations and budget overruns. Test success does not erase a budget
failure. Only the selected pytest's built-in plugins and the staged suite's
own conftest are admitted; containing-project and third-party plugins refuse.

Development and acceptance target Apple Silicon macOS with Python 3.11 and 3.14.
POSIX APIs alone do not establish Linux or other-host support; qualify those
hosts separately. Harness enforcement also needs its own explicit qualification.
The installed interpreter and its environment hooks remain trusted: isolated
mode ignores caller Python variables and the user site, but environment `.pth`
files and `sitecustomize` can still execute. The source bootstrap is available
as `<python> -I -B /absolute/project/src/stewart/_bootstrap.py source -- ...`;
do not use `PYTHONPATH` to select a source installation.
