# Follow-ups from the PolicyWitness first-contact report

Note written 2026-10-18 after reviewing `user-report.md` (untracked), a
first-contact report written by reading Stewart's documentation and source,
without running it. The user decided not to tackle these items now; this note
keeps them from being lost. Remove it once each item is handled or dropped.

## 1. Audits that need the project's own checks (report observation 1)

**What the report expected.** It expected the qualified adapter
`claude-code-restricted/1` to block checks that need XPC lookups, unified-log
access and signing-keychain access. The adapter requires a shell sandbox with
no network and no unsandboxed commands. That expectation matches the settings
Stewart builds (`auditor_scope.py`, `claude_settings`). Real enforcement was not
tested.

**A route the report didn't read about: the experiment lifecycle.** A granted
Python script runs from the manager's process, outside the auditor's harness
sandbox (`experiment.py`: `subprocess.Popen` with `cwd` at the worktree).

**Its limits, from the code.** None of these were tested against
PolicyWitness:

- **Environment.** `minimal` is the only environment policy: `PATH`, locale,
  and `HOME` redirected into the attempt. After the rehome plan, `HOME` points
  into the per-audit checkout directory.
- **Interpreter.** Either `repo-venv` (the maintainer checkout's
  `.venv/bin/python`) or the interpreter running Stewart.
- **Script.** A Python script that writes ledger rows. Each release allows one
  invocation.
- **Manager sandbox.** If the manager runs Stewart inside a sandboxed harness,
  the child inherits that sandbox.
- **Unknown.** Whether a redirected `HOME` breaks keychain access or tool
  configuration for PolicyWitness.

**Possible follow-up:** qualify this route with one of PolicyWitness's checks,
or document its limits for projects like it.

## 2. Project rules for the auditor (report observation 2)

**What happens now.** The adapter passes `--safe-mode`, which the report notes
disables `CLAUDE.md` loading. An auditor therefore sees the project's working
rules only through the workspace's `AUDITOR.md`, the prompt, or files those
point to. The bundled `AUDITOR.md` template has no place for naming which
project rules apply.

**Possible follow-up:** add a slot for project rules to the template, or have
the manual tell managers to route project rules through the workspace's
`AUDITOR.md`.

## 3. Observations the rehome, close and exit-code work answered

- **Storage under `.scratch/` and the hand-added ignore rule:** sessions now
  live under `<git-common-dir>/stewart/`; no ignore rule is needed.
- **The full checkout nested in the maintainer tree (observation 4):**
  checkouts now live under the per-user checkout home.
- **History footprint (observation 5):**
  - One prompt-only commit per audit remains.
  - `close` removes a session's refs.
  - Released audit IDs spare a new prompt commit after a failed preparation.
- **Ignored evidence must be pinned with `--supplemental` (observation 3):**
  already documented; no change planned.

## 4. No reply to the reporters has been written
