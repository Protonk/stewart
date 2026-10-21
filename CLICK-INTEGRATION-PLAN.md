# Click integration plan

This pending plan introduces [Click](https://click.palletsprojects.com/) as a
selective command-line boundary. It is not a full CLI conversion. Click owns the
leaf grammar of a few ordinary commands. The existing argparse root keeps the
command registry, the global options and the shared context. Stewart's `main()`
keeps every user-visible result and exit code. A later Rust rewrite is out of
scope; what this work leaves for it is a well-understood grammar and subprocess
tests that pin it from outside the Python process.

Work happens on the `click-integration` branch. When the contracts below reach
DEVELOPMENT.md, AGENTS.md and the tests, remove this plan.

The investigation behind it ran on 2026-10-21 against `main` at `2c4c706`:

- **Environment:** Python 3.14.8 and Git 2.54.0 (Apple). Click 8.5.0 was
  downloaded, hash-verified and studied in a scratch prototype only.
- **Baseline runs:** against a wheel built from a scratch copy of the source
  (sha256 `36974b72…`, byte-identical to the wheel `scripts/check.py` builds),
  installed into a fresh venv with `HOME` and the manager home redirected.

The local, ignored evidence is in
[`.tmp/click-boundary/evidence/`](.tmp/click-boundary/evidence/):

| File | What it is |
| --- | --- |
| `baseline.py`, `show.py` | the black-box harness (92 subprocess cases) and its viewer |
| `baseline.json` | its observations: argv, exit status, stdout/stderr digests and heads |
| `seam.py`, `probe.py` | the scratch prototype of the proposed seam, and Click behaviour probes |
| `targeted-baseline.json`, `.pytest.log` | targeted `check.py` run on current main: 33 selected, 33 passed |

Re-run the baseline with `python3.14 -I -B baseline.py ROOT VENV OUT.json`, where
VENV has the wheel installed. Every write lands under ROOT.

---

## 1. What is actually there

### Invocation chain

Every public form ends in the same verified startup, and only then imports `stewart.cli`:

```
<venv>/bin/stewart (sh)  ─exec→  python -I -B <venv>/bin/_stewart-python  ─runpy→  _bootstrap.py source -- ARGS
python -I -m stewart     ─__main__ execv→                                          _bootstrap.py source -- ARGS
python -I -B src/stewart/_bootstrap.py source -- ARGS            (running from source)
python -I -B <launcher>.py manager --code-root … --runtime-sha256 … -- ARGS   (issued argv: status actions,
                                                                  implementation handoffs, request retries)
_bootstrap.launch(): own argparse (RefusalParser) for the launcher mode → stage/verify the deployment
  → sys.path.insert(0, code_root) → from stewart.cli import main → main(ARGS)
```

The deployed code root holds exactly `SOURCE_FILES` (`_bootstrap.py:415`). Anything
the CLI imports from outside it comes from the interpreter's site-packages, which
`launch()`'s docstring already names as a trust root. The same bootstrap also runs
`helper` (auditor `verify_inputs`/`report_declaration`, each with its own argparse)
and `child` (experiment script with the pinned ledger) modes. Neither imports
`stewart.cli`.

### Packaging and environments

- Hatchling with a version file. `dependencies = []`. The wheel ships the `stewart`
  and `_stewart-python` shared scripts. There are no console_scripts entry points.
- `requirements.lock` already hash-locks the build *and test* tools (pytest 7.4.3,
  iniconfig, pluggy, packaging, build, hatchling, …). `scripts/check.py` installs the
  whole lock into a private venv, installs the wheel with `--no-deps`, and runs the
  staged suite. The README's runtime install is `pip install --no-index --no-deps
  WHEEL`.
- Contract tests encode "stdlib only": `tests/support.py:package_import_violations`
  (AST import guard, `test_foundations.py:53`) and
  `test_distribution.py:43` (`"Requires-Dist:" not in metadata`). So do the docs:
  AGENTS.md line 5 and README "Installation".

### Dispatch, parsing and output (`src/stewart/cli.py`)

- One argparse tree (`build_parser`, `RefusalParser` from `_bootstrap.py:244`, whose
  `error()` raises `StewartError(reason="usage")`). It has 21 commands, 7 `resource`
  actions, and 7 global options that must precede the command: `--repo --workspace
  --json --ref --lifetime --request-key --resume-request`.
- `main()` parses, handles `docs` specially, then runs `_coordinates` (ref, repo and
  workspace resolution and agreement), then `workspace()`. Next comes `dispatch()`: a
  prelude (request-key and resume policy, observer or maintainer role,
  `_revalidate`), then one `if args.command == …` branch per operation. Rendering
  happens last: prose via `render()` or one JSON envelope.
- Outputs:
  - Prose goes to stdout.
  - Refusals go to stderr as `Refused (reason): message`, with `Retained:` and
    `Next:` lines.
  - `--json` gives exactly one `stewart.result/3` document on stdout and nothing else.
  - `select` prints the reference JSON on stdout and advice on stderr; `triage-draft`
    prints the response JSON on stdout and context on stderr.
  - `docs` prints raw text.
- Exit codes are 0, 1, 2 and 3 (`_bootstrap.py:106`). The code a refusal earns comes
  from its reason table (`UNVERIFIED_REASONS`/`REFUSED_REASONS`).
  `test_exit_codes.py:62` requires every literal reason to be in exactly one set.
- When parsing fails there is no namespace, so `main()` decides JSON-vs-prose for any
  refusal by testing `"--json" in raw`. The bootstrap does the same.
- **The grammar is replayed across implementations.** Generated argv (status
  `next_actions`, `_rebind` at `status.py:706` which inserts `--lifetime` at index 4,
  and `request_keys.py:203`'s `["--repo", checkout, "request", "--key", key]` handoff
  retry) is recorded and executed by *other* deployments, including older ones.
  Grammar compatibility is a custody property, not cosmetics.

### Tests that touch the CLI surface

These are the tests a migration interacts with:

- **Subprocess contract tests:** `test_stewart_cli.py` (JSON purity, exit codes,
  human output) and `test_invocation.py`, which covers issued argv, `--help` without
  Git, structured usage refusals and the startup flags.
- **Fresh-venv tests:** `test_distribution.py` builds fresh venvs and runs `docs`.
  `test_invocation.py:179` runs `init` under a venv with **no third-party packages**.
- **Parser introspection:**
  - `test_stewart_cli.py:129` parses the README and manual examples with
    `build_parser()`.
  - `test_stewart_cli.py:225` checks the root help text.
  - `test_orchestration_plan.py:24` walks argparse `_actions` for every flag the
    orchestration plan cites, including `--key`.
- **In-process callers:** `test_stewart.py:522` checks that import and `--help` do no
  work. `test_close.py` and others call `cli.main([...])` in-process.

## 2. Command inventory

Legend: **now** = migrate in the first slice; **later** = plain enough to move once
the seam has proven itself; **outside** = keep its present machinery (reason
given). "Ctx" means the command depends on the global context pipeline
(`_coordinates`/ref agreement, lifetime binding, request-key policy, role checks).

| Route | Own grammar | Consumes → produces | Unusual | Category |
| --- | --- | --- | --- | --- |
| `docs DOCUMENT` | 1 choice positional | none → raw text or envelope; exit 0/2 | handled before `_coordinates`; silently ignores `--repo`, `--request-key` etc. | **now**: no repository, real operation (`docs.document`), the install smoke test; it forces the dependency to be provisioned correctly |
| `request --key KEY` | 1 required option | repo → `stewart.request/1` prose/JSON; exit from result | **handoff retry target replayed by other implementations**; ctx (repo-only, `--ref`, read-only key refusal) | **now**: full global pipeline, no option interacts with ref agreement |
| `discover` | none | repo → listing | ctx | later (no own grammar, so Click adds nothing yet) |
| `select --audit-id` | 1 option | repo, `--workspace`, `--lifetime` → reference on stdout, advice on stderr | `--ref` agreement reads `args.audit_id`; stream split | later: needs Click params merged into ref agreement (slice 2 design) |
| `register` | 2 options | workspace → record | ctx | later |
| `resource ACTION …` (7 actions) | nested subcommands; mutex `--branch`/`--existing-branch` | records, worktrees, branches | nested group; Click has no mutex groups | later (a natural Click group once leaves are routine) |
| `message` | choice + free text | session → record | free-text values that may start with `-` (see §7) | later: **recommended next slice** |
| `launch` | choices, `--from-profile` | session → record | actor required unless profile (checked in operation) | later |
| `triage-draft` | 1 option | → response JSON on stdout, context on stderr | stream split | later |
| `triage`, `release` | JSON file input via `_read_json_file` | records | control-JSON rule stays in the shared reader | later |
| `retain`, `resume`, `recover-runtime` | few options | records, maintainer checkout | ctx | later |
| `export` | **required** mutex `--collection`/`--attempt`, repeatable `--select` | package | required mutex has to be hand-validated in Click | later |
| `init` | `nargs=2` repeatables (`--source URL PURPOSE`), raw-formatted help and epilog | prompt, manifest | most option-heavy | later |
| `prepare` | several options | session, refs, worktree | heavy side effects | later |
| `collect` | 1 choice | collection; exit 0/1/3 | ctx | later |
| `status` | 2 options | big renderer and **issued argv generation** | `--profile` needs `--audit-id` (checked in `dispatch`); listing mode | **outside**: rendering and action generation are the contract |
| `close` | 10 options, modes | removal, closing records; exit-code policy partly computed in `dispatch` | `--plan` exit computation, `--resource` exclusivity, `actor_required`, `--resume-request` | **outside**: refusal policy lives in the CLI layer and must not move into Click callbacks |
| `run` | 3 options | child process group, timeouts; exit 0/1/3 | `KeyboardInterrupt` handled inside the operation; signals | **outside** until signal semantics are specified |
| global options + root dispatcher | 7 options before COMMAND | context for every command | contextual validation after parsing | **outside**: argparse root stays the single registry (see §5) |
| bootstrap launcher modes | `manager/helper/child/source`, fixed `--` | startup | stdlib-only before verification | **permanently outside** |
| auditor helpers (`inputs`, `declaration`) | own argparse | run in the auditor's scope from the supplied runtime | must not need site-packages | **permanently outside** |
| `scripts/check.py` | argparse plus pytest passthrough | developer tool | `parse_known_args` passthrough | out of scope |

No route reads stdin, prompts, or delegates its argv to a subprocess at the CLI
level. `run` executes the *released* child argv, not CLI arguments.

## 3. Baseline: observed behaviour (not necessarily intended)

Full data is in the evidence `baseline.json`. Highlights:

| Case | Observed |
| --- | --- |
| All four entry forms `--help` | identical bytes (sha `a8d04444…`), exit 0 |
| `stewart` / `stewart --json` | usage refusal, exit 2; prose on stderr / envelope on stdout |
| unknown option/command | `Refused (usage): …`, exit 2; no suggestions |
| `stewart docs --json manual` | **JSON envelope** saying `unrecognized arguments: --json`, because the literal token is present |
| `--js` (abbreviation) | accepted: success prints JSON |
| `--js … status` refused | **prose on stderr** (literal `--json` absent) — see B2 |
| abbreviated leaf options | accepted (`--audit` → `--audit-id`); `--inp` is ambiguous → usage |
| `--text --json` / `--text -n` | argparse refuses (`expected one argument`); `--text=-n` works |
| `--request-key k docs auditor` | accepted and ignored (docs bypasses `dispatch`, although `_READ_ONLY` lists `docs`) |
| `FORCE_COLOR=1 stewart --help` | 3.14 argparse emits ANSI colour into a pipe; `NO_COLOR` wins |
| `COLUMNS=50` | argparse rewraps to the given width (175 lines) |
| `docs manual \| head -1` | **`Refused (failed): BrokenPipeError`, exit 0** (3/3 runs) — see B1 |
| closed reader after a completed mutation (`message`) | record written; `Exception ignored while flushing sys.stdout`, **exit 120** |
| stdout closed (`>&-`) | silent, exit 0 (Python sets `sys.stdout = None`) |
| SIGINT mid-operation (slow `git`) | `KeyboardInterrupt` traceback, process dies by SIGINT (-2) |
| SIGTERM | dies by SIGTERM (-15), no output |
| `--` before, inside or after `docs` | exit codes unchanged; the same holds in the prototype seam |
| keyed replay / conflict | replay prints the recorded request, exit 0; conflict refuses `request_key_conflict`, exit 2 |
| complex route | `init` → `prepare` → `status` → `launch` → `message` → `collect` (exit 1, gaps) → `triage-draft` (split streams) → `select`/`--ref` → `close --plan` (exit 2, would refuse) → `close --abandon` → `status` closed: all as documented |

Targeted tests on current main: 33 selected, 33 passed. The selection was
`test_stewart_cli.py` plus 12 invocation, distribution, foundations,
orchestration-plan, import-surface and request-binding nodes.

### Pre-existing defects found (independent of Click)

- **B1. A broken stdout pipe misreports the outcome.** If `print` raises mid-write,
  `main()` catches `BrokenPipeError` as a generic failure. It prints
  `Refused (failed)` and returns the operation's code (`docs manual | head`: exit 0
  with "Refused"). If the failure surfaces at interpreter shutdown, Python exits 120
  and the operation's code is lost. After a completed mutation, the message claims
  nothing was done although the record exists. Reproducer: `stewart … message … |
  { exec 0<&-; sleep 1; }` writes the record and exits 120.
- **B2. JSON mode for refusals ignores the parsed flag.** `"--json" in raw` misses
  accepted abbreviations: `stewart --js --repo /nonexistent --workspace x status`
  prints prose, while the same flag gives JSON on success.
- **B3 (possible). `docs` skips the read-only request-key refusal.** `_READ_ONLY`
  contains `docs`, which suggests the author meant the refusal to apply, but `main()`
  returns before `dispatch()`. Needs a decision: it may be deliberate leniency.

## 4. Click facts that decide the design (8.5.0, read from its source and docs)

- **Latest release:** 8.5.0, uploaded 2026-08-26. The wheel has sha256
  `255bc9599cf7748b4b1a446ccc735421bd08a2ae529a8b88597d3de5664ee360` (verified),
  `Requires-Python >=3.10`, and **no `Requires-Dist`**. The 8.3.x series churned
  flag/default handling (`UNSET` sentinel regressions fixed in 8.3.1–8.3.3), which
  argues for an exact pin.
- **`Command.main()` does more than parse, even with `standalone_mode=False`**
  (`core.py:1484`):
  - it reads `_<PROG>_COMPLETE` from the environment and prints a completion script,
    then exits (verified: `_STEWART_COMPLETE=bash_source` emits a bash script);
  - it turns `KeyboardInterrupt`/`EOFError` into `Abort` (exit 1, no SIGINT death);
  - it handles EPIPE by wrapping the streams and calling `sys.exit(1)`.
  The documentation page ("Exception Handling and Exit Codes", 8.5.x) confirms the
  last two for non-standalone mode.
- **`make_context()` + `invoke()` avoid all of that.** Verified: Ctrl-C still dies by
  SIGINT (exit 130 through the shell), and the completion variable is ignored. Parse
  errors raise `click.UsageError` (with `format_message()`), and `--help` echoes help
  to stdout and raises `click.exceptions.Exit(0)`. Exceptions from callbacks,
  including `StewartError`, propagate unchanged.
- **Grammar differences from argparse:**
  - help options default to `--help` only (`-h` needs `help_option_names`);
  - **no option abbreviations** (it suggests "Did you mean …");
  - an option requiring a value **takes the next word even if it starts with `-`**
    (`--text --json` → text `"--json"`);
  - `--` and interspersed options behave the same;
  - messages differ ("Missing argument 'DOCUMENT'. Choose from:\n\tagents,…",
    "No such option '--ke'. (Did you mean …)");
  - help width is bounded (about 78 columns, roughly 45 minimum) and has no colour.
- **`CliRunner.invoke()` calls `cli.main()`** (`testing.py:687`), the path the seam
  bypasses, and 8.5 deprecates `isolated_filesystem`. CliRunner tests would exercise
  code production never runs, so the plan uses subprocess tests, plus
  `make_context` for narrow unit checks.

## 5. Boundary decision

**Click owns the leaf grammar of selected commands. The argparse root stays the
single command registry and the owner of global options and context. Stewart's
`main()` owns every user-visible result and exit code.**

Mechanism (see the evidence `seam.py` prototype):

1. `build_parser()` registers a Click-backed command as an ordinary subparser with
   `add_help=False`, marked as delegated. The root therefore lists every command, in
   its current order and with its current one-line help, so `stewart --help` is
   unchanged.
2. On Python 3.14 a subparser receives *all* remaining tokens in its public
   `parse_known_args` (`argparse.py`, `_SubParsersAction.__call__`). A delegated
   subparser returns them verbatim (`namespace.leaf_tokens`).
   `nargs=REMAINDER` does **not** work: 3.14 rejects a leading `--help` or `--key`
   with "unrecognized arguments" (tested).
3. `main()` parses the leaf with `command.make_context("stewart <name>", tokens,
   obj=…)` right after the root parse, before `_coordinates`, so `stewart request
   --help` still needs no `--repo`. `click.UsageError` becomes
   `StewartError(reason="usage", next_steps=["consult --help …"])`, and `Exit` (help
   shown) returns its code. **`Command.main()` is never called.**
4. The generic pipeline (`_coordinates`, request-key policy, role checks,
   `_revalidate`) runs unchanged. The command's `dispatch` branch becomes "invoke the
   Click leaf". Its callback calls the existing operation and returns
   `(result, exit_code)`. Rendering and the envelope stay in `main()`.
5. Click is imported lazily, only when a Click-backed command is selected. Every
   other command, the API (`stewart.api`), the auditor helpers and the experiment
   child stay importable and working without Click. That keeps
   `test_invocation.py:179` (legacy `init` under a venv with no third-party packages)
   valid as an invariance case. If Click is missing, the leaf refuses with a stable
   reason instead of a traceback (a bare `ModuleNotFoundError` would escape
   `launch()`, which catches only `StewartError`/`OSError`, and exit 1).

The four questions, answered for every command:

1. **Who recognizes the command?** The root parser in `cli.build_parser()`. It is the
   only registry.
2. **Who parses its arguments?** Its argparse subparser, or, for a delegated command,
   its Click command in the new module.
3. **Where does the work happen?** In the existing operation module, unchanged.
4. **Who decides the visible result and exit code?** `cli.main()`, through
   `render()` and the envelope.

Rejected alternatives:

- **A Click group at the root.** This moves the global options, their abbreviations
  and their error text for *every* command into Click. It forces the legacy
  namespaces to be rebuilt from two parsers and rewraps the tested root help. That is
  a full conversion of the riskiest surface, not a slice.
- **Argparse `REMAINDER`:** broken for leading option tokens on 3.14.
- **Pre-scanning argv:** a second implementation of the global grammar.
- **CliRunner-based tests:** they test `Command.main()`, not production.

Trust model: Click becomes part of the trusted interpreter environment. Its bytes are
not in the deployment manifest, `package_sha256` or runtime handoff verification. So
two managers with different Click versions report the same implementation identity.
Document this; recording the version is proposal P6.

## 6. First slice

**Commands:** `docs` and `request`. Both are read-only, exercise real operations,
together cover the no-repository and the full-context paths, and carry
cross-implementation contracts (install smoke test; handoff retry argv). A mutation
(`message`) is the next slice, once the seam is proven.

Changes, kept as reviewable commits:

1. **Preparatory contract tests (pass on current code).** Subprocess tests for
   `docs` and `request`:
   - root help lists both, unchanged;
   - `--help` and `-h` exit 0 on stdout;
   - usage refusal (prose on stderr, JSON on stdout, reason `usage`, exit 2);
   - success streams and JSON purity;
   - `--request-key` refused for `request`;
   - `request --key` from a `--ref`;
   - the handoff retry argv `--repo R request --key K` parses;
   - `--` placement.
2. **Click integration and the slice:**
   - `pyproject.toml` gets `dependencies = ["click==8.5.0"]`;
   - `requirements.lock` gets `click==8.5.0 --hash=sha256:255bc959…`;
   - a runtime install step (decision D1);
   - a new Click module (name per D4, e.g. `stewart/commands.py`) added to
     `SOURCE_MODULES` (the count test goes from 36 to 37);
   - the `cli.py` seam;
   - test updates: the import guard allows `click` only in that module; metadata
     expects exactly `Requires-Dist: click==8.5.0`; the orchestration-plan walk and
     the documented-examples check also cover Click leaves; the fresh-venv `docs`
     test installs Click from the hash-checked wheelhouse;
   - new tests: the Click-absent venv (a legacy command works, a Click leaf refuses
     with the reason); `_STEWART_COMPLETE` is ignored; root help is unchanged.
3. **Documentation:**
   - AGENTS.md line 5 (runtime dependencies);
   - README "Installation" and its "standard library only" sentence;
   - DEVELOPMENT.md provisioning and a short stateless "CLI structure" rule;
   - a manual note that Click is trusted from the interpreter environment.
4. **Bug fixes, as separate commits and only if approved:** B1, B2, B3.

**Handoff:** this plan is the handoff. Update it with the implemented slice, the
contract evidence (baseline and post-change subprocess checks, test commands and
results, important uncovered cases), and the confirmed change ledger. The durable
boundary rule moves to DEVELOPMENT.md, and this plan is removed once its contracts
live there and in the tests.

## 7. Expected change ledger (predicted; to be confirmed after implementation)

**Framework and presentation differences**, confined to `docs` and `request`:
- Click help layout ("Usage: stewart docs [OPTIONS] DOCUMENT").
- Usage messages worded by Click; the reason stays `usage` and the exit code stays 2.
  The JSON `error.message` text changes, and `Missing argument` contains a newline
  and a tab.
- Click's "Did you mean" suggestions.
- Bounded help width; no `FORCE_COLOR` colour in leaf help.

**Framework differences with a compatibility cost**, to disclose:
- Abbreviated leaf options stop working (`request --ke K`).
- `request --key -x` reaches the operation and refuses `request_key_format`
  (still exit 2), where argparse refused it as `usage`.

**Bug-fix candidates (B1–B3).** Each needs a test with old and new behaviour, and a
decision.

**API proposals: report only, do not implement.**

| # | Friction observed | Proposal | Who benefits | Cost | Recommend at 0.1.0? |
| --- | --- | --- | --- | --- | --- |
| P1 | abbreviations make the grammar implementation-defined; adding an option creates new ambiguities; B2 | `allow_abbrev=False` everywhere | spec writers, the Rust port (clap does not infer by default), scripts | scripts that abbreviate break (none found in docs, tests or generated argv) | **yes** |
| P2 | free-text values beginning with `-` need `--text=-n`; Click and argparse disagree | specify one rule for option values | message, note and reason authors | silently swallowing a mistyped flag as text | decide before migrating `message`; lean towards keeping refusal, closer to clap's default |
| P3 | global options are accepted only before the command | keep as is | — | — | **no change**: `_rebind` and the issued argv depend on it |
| P4 | `docs` accepts and ignores `--repo`, `--ref`, `--request-key` | refuse request and session options on `docs` | consistency | invocations that pass them now refuse | yes, together with B3 |
| P5 | no `--version` | add a root `--version` (version and implementation digest) | operators | a new surface | optional; `discover` and `status` already name the implementation |
| P6 | Click is outside the implementation identity | record Click's version in `tool_identity()` | custody fidelity | a record schema change | later, deliberately |

**Regression risks to watch:**
- `-h` must be configured.
- The root help must stay byte-identical.
- `--help` must not need Git or a repository.
- Issued and handoff argv must parse.
- Ctrl-C and EPIPE behaviour must not change (guaranteed by never calling
  `Command.main()`).

## 8. Open decisions

1. **D1: runtime install of Click.**
   - **(a) Recommended:** a separate hash-locked runtime requirement (e.g.
     `requirements-runtime.lock` holding only `click`), installed before the wheel
     with `--no-deps`, with a test that it agrees with `pyproject.toml` and
     `requirements.lock`.
   - **(b)** Drop `--no-deps` and resolve Click from the wheelhouse by
     `--find-links`: simpler, but Click is then not hash-checked at install.
2. **D2: pin style.** **Exact `click==8.5.0` (recommended)**, because Click is now
   executed CLI code outside the implementation identity. The alternative is a
   compatible range.
3. **D3: reason for a missing Click.** **A new `dependency_missing` (refused, exit 2;
   recommended)**, which is a JSON-contract addition, or reuse `startup_failed`.
4. **D4: name and location of the Click module** (e.g. `stewart/commands.py`).
5. **D5: whether B1, B2 and B3 are fixed in this work**, as separate commits, or
   recorded only.

## 9. Divergences from the brief

- The brief assumed no development dependencies. Here `requirements.lock` already
  hash-locks pytest 7.4.3 and the build tools, and `scripts/check.py` is the runner.
  The smallest sensible setup is therefore to *keep* them and add only Click. No new
  test framework, no dependency group duplicating the lock.
- Making Click a runtime dependency reverses a durable project rule ("runtime
  dependencies are the standard library…"). The guidance and two contract tests
  change in the same commit as the dependency.
- The handoff is this root `*-PLAN.md`, following the repository's plan
  convention, instead of a `docs/` page.

## 10. Next sensible slice (after this one)

Migrate `message` as the first Click-backed **mutation**. Design how Click-parsed
`--audit-id` takes part in `--ref` agreement (`_coordinates` reads `args.audit_id`
today) in one place, then apply the same pattern to `select`, `register` and
`launch`. Leave `status`, `close` and `run` outside Click.
