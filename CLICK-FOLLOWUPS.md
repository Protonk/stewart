# Follow-ups from the Click integration plan

Note written 2026-10-21 when the first slice of `CLICK-INTEGRATION-PLAN.md`
(Click-backed `docs` and `request`) was completed and the plan removed. Its
contracts now live in DEVELOPMENT.md ("Command-line structure"), AGENTS.md,
the README, the manual and the tests. The plan, with its command inventory,
baseline, comparison results and change ledger, remains in Git history (last
at `8b58353`). This note keeps what it left open. Remove it once each item is
handled or dropped.

## Defects found by the baseline, not fixed

Kept out of the integration on purpose. Each behaves exactly as before it.

- **B1. A broken stdout pipe misreports the outcome.** `main()` catches a
  `BrokenPipeError` from printing as a generic failure. If `print` raises
  mid-write, it prints `Refused (failed): BrokenPipeError …` and returns the
  operation's own code: `stewart docs manual | head -n 1` exits 0 with that
  message. If the failure surfaces at interpreter shutdown instead, Python prints
  `Exception ignored while flushing sys.stdout` and exits 120, losing the
  operation's code. After a completed mutation the message claims nothing was
  done although the record exists. Reproducer:

  ```sh
  stewart --repo R --workspace W message --audit-id A --direction to-auditor --text x --actor m | { exec 0<&-; sleep 1; }
  ```

  It writes the record and exits 120. The fix needs a decision on the exit
  code and the stderr note for undelivered output.
- **B2. JSON mode for refusals ignores the parsed flag.** Refusals choose JSON
  by the literal token `"--json" in raw`, so an accepted abbreviation gives JSON
  on success and prose on refusal: `stewart --js --repo /nonexistent
  --workspace x status`. `args.json or "--json" in raw` would fix it without
  changing the misplaced-`--json` case. Proposal P1 would also remove it.
- **B3 (possible). `docs` skips the read-only request-key refusal.**
  `_READ_ONLY` lists `docs`, but `main()` handles `docs` before `dispatch()`, so
  `stewart --request-key k docs auditor` succeeds and ignores the key. It may be
  deliberate leniency; see P4.

## API proposals (reported, not implemented)

| # | Friction | Proposal | Recommendation at 0.1.0 |
| --- | --- | --- | --- |
| P1 | argparse accepts abbreviated options; adding an option creates new ambiguities (`--inp`); it causes B2; Click leaves and clap do not abbreviate | `allow_abbrev=False` on every parser | adopt: no abbreviation was found in docs, tests or generated argv |
| P2 | argparse refuses option values starting with `-` (`--text -n` needs `--text=-n`); Click takes them | specify one rule for option values | decide before delegating `message`; lean towards refusal, closer to clap's default |
| P3 | global options only before the command | keep | no change: `_rebind` and every issued argv rely on it |
| P4 | `docs` accepts and ignores `--repo`, `--ref`, `--request-key` | refuse request and session options on `docs` | adopt, together with B3 |
| P5 | no `--version` | a root `--version` printing the version and implementation digest | optional; `discover` and `status` already name the implementation |
| P6 | Click is outside the implementation identity | record Click's version in `tool_identity()` | later, as a deliberate record-schema change |

## Next slice

Delegate `message`, the first Click-backed mutation. First design, in one
place, how a Click-parsed `--audit-id` takes part in `--ref` agreement
(`_coordinates` reads `args.audit_id` today). Then apply the same pattern to
`select`, `register` and `launch`. Decide P2 before `message`, whose `--text` is
free text.

Inventory for later slices, by expected ease:

- **Plain options:** `discover`, `select`, `register`, `message`, `launch`,
  `triage-draft`, `triage`, `release`, `retain`, `resume`, `recover-runtime`,
  `collect`, `prepare`.
- **Needs explicit validation in Click:**
  - `export` (required mutex `--collection`/`--attempt`);
  - `resource` (nested actions, mutex `--branch`/`--existing-branch`; a natural
    Click group);
  - `init` (`nargs=2` repeatables, raw-formatted help and epilog).
- **Keep outside Click:**
  - `status`: rendering and issued-argv generation are its contract.
  - `close`: refusal and exit-code policy are computed in the CLI layer.
  - `run`: child process groups, timeouts and interrupt handling.
  - The root parser and global options: the only registry.
  - The launcher, the auditor helpers and experiment children: Click-free.

## Known limits

- **Trust assumption.** Click is loaded from the interpreter's environment. The
  exact pin records intent, and the tests verify only the environments they
  provision. Stewart does not check the loaded version at runtime, and the
  implementation identity and runtime handoff verification do not cover Click's
  bytes.
- **Delegated help needs Click.** Without it, `docs --help` and
  `request --help` refuse with `dependency_missing`, where argparse help needed
  nothing.
- **Experiment children can import Click.** Children released with the
  `tool-interpreter` policy see Click in the manager's venv.
- **Two option grammars** (abbreviations, hyphen values) coexist until P1 and
  P2 are decided.
- **Multi-line usage message.** Click's `Missing argument 'DOCUMENT'` lists the
  choices on tab-indented lines inside the one-line `Refused (usage): …` form
  and the JSON `error.message`.
- **`LINUX-CONTAINERS-PLAN.md` is stale on dependencies.** Lines 55 and 158
  still describe a standard-library-only runtime and a single lock; its
  provisioning steps need the runtime lock too.
