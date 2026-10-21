# Stewart

Stewart is a command-line tool and Python library for running bounded audits
of Git projects under local custody. It prepares an auditor's checkout, records
each step of the audit, captures what the auditor produces and retires the
audit when it is done.

## Mission

Stewart provides custody for bounded inquiries into material held in Git. It organizes cooperation between distinct roles: a manager who commissions, observes, and disposes of inquiries, and an auditor who investigates and reports.

Stewart maintains the working boundaries of each inquiry, including its subject, permissions, records, and transitions. Its arrangements give the auditor a defined assignment and the manager a means of following the work without continually renegotiating their relationship.

Audits can yield findings, unresolved questions, incomplete work, or accounts of missing evidence. Stewart makes their circumstances and products available for inspection, while the conduct and interpretation of an inquiry remain matters of judgment.

## How an audit works

An audit has two roles. The manager chooses the question, prepares the
assignment, starts the auditor, reviews what comes back and closes the audit.
The auditor, typically an agent working in its own checkout, investigates and
writes a report. The current implementation also calls the manager the
*maintainer*: `MAINTAINER.md` is the manager's role guidance, and the
*maintainer checkout* is the repository worktree the manager runs Stewart from.

Each audit belongs to a *workspace*, a directory in the audited repository such
as `audits/parser-review`. It holds the role guidance (`AUDITOR.md` and
`MAINTAINER.md`), the assignment (`PROMPT.md`) and the audit's `reports/` and
`scratch/` areas. An audit moves through five stages:

1. **Assign.** The manager selects one bounded question and the decision it
   informs. `init` pins the inputs and drafts `PROMPT.md`; the manager writes
   its five sections (question, decision, scope and exclusions, evidence and
   stop condition), then commits the prompt by itself. That commit is the
   assignment.
2. **Prepare.** `prepare` opens a session for the assignment. It creates a
   locked, detached checkout of the prompt commit for the auditor, supplies a
   Stewart runtime beside it for the auditor's helper commands, and writes a
   launch handoff naming the checkout, the role guidance, the prompt and the
   report path. In the default snapshot mode development continues and the
   answer applies to the audited revision; a paused audit instead records a
   hold on the project's writers, which `resume` releases after review.
3. **Investigate.** The manager starts a fresh auditor through an agent
   harness with the handoff and records the handoff with `launch`; a workspace
   launch profile can supply the exact harness command. The auditor works in
   its checkout, writes its report and declared scratch outputs there, and ends
   the report with a declaration of its completion and report kind using the
   helper commands the handoff supplies. Rulings and other messages relayed
   between the two are recorded with `message`.
4. **Collect and review.** When the auditor stops, `collect` captures the
   report, an inventory of the checkout, Git patches and an archive of changed
   files as a new collection. `status` shows the session's stage, its records
   and the commands available next. The manager reviews a collection with
   `triage-draft`, then records with `triage` which claims it accepts, rejects
   or leaves unresolved, a disposition for each custody gap and a decision.
   `retain` copies the reviewed report and support files into the maintainer
   checkout, and `export` packages captured evidence for a later assignment.
5. **Close.** `close` writes a closing record, then removes the session, the
   auditor's checkout and the Git refs and registry entry the session kept.
   `close --abandon` retires an audit that will not be completed.

Assignments, checkouts, records and reports each have their own place. The
assignment is a commit in the audited repository, and the auditor's checkout is
made from that commit. That checkout is a separate Git worktree, kept with its
supplied runtime in a per-session directory under the checkout home
(`~/.local/state/stewart/checkouts` unless `prepare --checkout-home` names
another). Stewart's records live in the repository's Git administration under
`<git-common-dir>/stewart/`, outside every working tree, so no ignore rule is
needed; while an audit is live, each step adds new records rather than
rewriting earlier ones. The report is the auditor's product: it is written in
the checkout, enters the records when a collection captures it, and reaches the
project when the manager retains it.

The [manual](src/stewart/resources/README.md) covers every command, record and
refusal; its [static audit lifecycle](src/stewart/resources/README.md#static-audit-lifecycle)
follows these stages step by step.

## Installation

Stewart needs Python 3.14 or newer, Git and a POSIX shell. Its runtime uses
the Python standard library and one package, [Click](https://click.palletsprojects.com/),
pinned in [`requirements-runtime.lock`](requirements-runtime.lock). Launch profiles
are optional and require their explicitly named harness executable.

Stewart is installed from a locally built wheel into a dedicated virtual
environment. Its build and test dependencies, and Click, are hash-locked in
[`requirements.lock`](requirements.lock). From a source checkout, provision a
build environment and wheelhouse while network access is available. Use
absolute paths for these variables:

```sh
STEWART_SOURCE=/absolute/stewart-project
STEWART_BASE_PYTHON=/absolute/python3.14
STEWART_BUILD=/absolute/stewart-build-venv
STEWART_WHEELS=/absolute/stewart-wheelhouse
"$STEWART_BASE_PYTHON" -I -m venv "$STEWART_BUILD"
"$STEWART_BUILD/bin/python" -I -m pip download --only-binary=:all: --require-hashes -r "$STEWART_SOURCE/requirements.lock" --dest "$STEWART_WHEELS"
"$STEWART_BUILD/bin/python" -I -m pip install --no-index --find-links "$STEWART_WHEELS" --require-hashes -r "$STEWART_SOURCE/requirements.lock"
```

Build both archives offline, including the wheel from the source archive. In a
fresh runtime venv, install the hash-locked runtime requirement from the
wheelhouse, then the wheel without dependency resolution. The version comes
from `src/stewart/_version.py`; no `.git` directory or VCS plugin is needed.

```sh
"$STEWART_BUILD/bin/python" -I -m build --no-isolation --outdir "$STEWART_SOURCE/dist" "$STEWART_SOURCE"
STEWART_ENV=/absolute/stewart-venv
"$STEWART_BASE_PYTHON" -I -m venv "$STEWART_ENV"
"$STEWART_ENV/bin/python" -I -m pip install --no-index --find-links "$STEWART_WHEELS" --require-hashes -r "$STEWART_SOURCE/requirements-runtime.lock"
"$STEWART_ENV/bin/python" -I -m pip install --no-index --no-deps "$STEWART_SOURCE/dist/stewart-0.1.0-py3-none-any.whl"
STEWART_PYTHON="$STEWART_ENV/bin/python"
"$STEWART_PYTHON" -I -m stewart docs manual
```

The installed `<venv>/bin/stewart` entry point starts the venv's interpreter in
isolated mode; the equivalent module form is `<venv>/bin/python -I -m stewart`,
and it must retain `-I`. Both work outside the source tree. `--help` lists the
commands, and `stewart docs manual` prints the bundled manual outside any
repository. To run Stewart from a source checkout without installing it, see
[Running from source](DEVELOPMENT.md#running-from-source).

## Quick start

In an ordinary Git project, create and customize the role guidance before
preparing an assignment. The project needs neither Stewart's source nor its own
venv:

```sh
cd /absolute/audited-project
mkdir -p audits/parser-review
"$STEWART_PYTHON" -I -m stewart docs auditor > audits/parser-review/AUDITOR.md
"$STEWART_PYTHON" -I -m stewart docs maintainer > audits/parser-review/MAINTAINER.md
git add -- audits/parser-review/AUDITOR.md audits/parser-review/MAINTAINER.md
git commit -m "Define audit roles"
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review init --audit-id parser-fields --input path/to/parser.py --replace-prompt
# Complete PROMPT.md's five sections and remove its UNASSIGNED line, then commit it alone.
git add -- audits/parser-review/PROMPT.md
git commit -m "Assign parser field audit"
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review prepare --mode snapshot
```

Custody commands take explicit `--repo` and `--workspace` arguments. `--repo`
must be the exact maintainer worktree root; subdirectories and registered
auditor worktrees are refused. The manager's harness needs write access to
both custody locations, `<git-common-dir>/stewart` and the checkout home, which
`status` names, and to the private manager deployments `status` creates under
`~/.local/state/stewart/managers`. Keep `<git-common-dir>/stewart` and the
manager deployments out of the auditor's grants.

Give the auditor the handoff `prepare` printed, following the manual's
[terminal launch](src/stewart/resources/README.md#manual-terminal-launch)
recipe, which lists the access an auditor's harness needs, and carry the audit
through to its close. Capitalized placeholders come from earlier output:
`status` names each collection, and `triage` prints the name of its record.

```sh
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review launch --audit-id parser-fields --style terminal --model MODEL --effort EFFORT --actor maintainer
# After the auditor stops:
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review collect --audit-id parser-fields --auditor-stopped finished
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review status --audit-id parser-fields
# Save the printed response as response.json and fill in every null before recording it.
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review triage-draft --audit-id parser-fields --collection COLLECTION
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review triage --audit-id parser-fields --collection COLLECTION --response response.json --actor maintainer
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review retain --audit-id parser-fields --triage TRIAGE --report
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review close --audit-id parser-fields --actor maintainer
```

To continue later, or from another maintainer checkout, `stewart --repo "$PWD"
discover` lists every audit, resource and request key the repository records,
and `select --audit-id ID` prints a reference to keep and pass back with
`--ref`. Mutations accept `--request-key`, so a retry returns the recorded
outcome instead of repeating the operation.

## Current implementation

The mission describes what Stewart is for; this section describes release
0.1.0. It implements the audit lifecycle above through the `stewart` command
and the `stewart.api` Python API, together with:

- discovery, kept selection references and request keys, with which a caller
  can resume an audit later and retry a mutation without repeating it;
- recorded resources: `resource create-worktree`, `create-branch` and
  `create-directory` record the manager worktrees, branches and directories an
  audit uses, so that `close` can retire them once no audit uses them;
- evidence packages, through which `export` carries selected captured bytes
  into a new assignment;
- an optional experiment lifecycle, in which an assignment grants construction
  and execution, `release` freezes the reviewed artifacts and `run` executes
  one released invocation;
- launch profiles that render a Claude Code command through the
  `claude-code-restricted/1` scope adapter.

Its present limits:

- **Platforms.** Development and acceptance target Apple Silicon macOS with
  Python 3.14. Linux and other hosts are not yet qualified; POSIX APIs alone do
  not establish support there.
- **Harnesses.** Stewart launches no agent, sends no messages and stages no
  files. The harness enforces the auditor's filesystem boundary. Another
  harness needs a separately qualified adapter or an explicitly configured
  equivalent boundary, and real harness enforcement is qualified separately
  from the settings an adapter constructs.
- **Orchestration.** No orchestrator exists yet. Discovery, selection, request
  keys and recorded resources are the interfaces it would build on;
  [ORCHESTRATION-PLAN.md](ORCHESTRATION-PLAN.md) describes the pending work.
- **Submodules.** Stewart neither populates nor audits submodules; `prepare`
  refuses a prompt commit holding them until they are acknowledged.
- **Historical records.** Historical schemas require their creating
  installation; new versions never rewrite old records for compatibility.
- **Trusted interpreter.** The installed interpreter and its environment hooks
  remain trusted: isolated mode ignores caller Python variables and the user
  site, but environment `.pth` files and `sitecustomize` can still execute.

## Documentation, development and license

The [manual](src/stewart/resources/README.md),
[question guide](src/stewart/resources/QUESTION-TYPE.md) and
[conditional protocols](src/stewart/resources/AUDIT-PROTOCOLS.md) ship in the
wheel; `stewart docs manual`, `questions` and `protocols` print them.
`stewart docs auditor`, `maintainer`, `agents` and `claude` print generic role
templates for a new workspace such as `audits/parser-review`.

[DEVELOPMENT.md](DEVELOPMENT.md) covers provisioning, the test runner and the
evidence it keeps, and [AGENTS.md](AGENTS.md) states the rules and custody
contracts that changes must keep. With the build environment and wheelhouse
from [Installation](#installation), run the full suite against a fresh wheel:

```sh
"$STEWART_BUILD/bin/python" -I -B "$STEWART_SOURCE/scripts/check.py" --wheelhouse "$STEWART_WHEELS" --result /absolute/stewart-results.json
```

Add `--fast` for a short smoke selection; full validation omits it.

Stewart is released under the [MIT License](LICENSE).
