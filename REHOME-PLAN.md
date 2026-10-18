# Rehome Stewart's storage

Execution plan prepared 2026-10-18 and agreed with the user the same day, then
revised the same day for the actor model below.

Status: design and sequence agreed. Step 0 is **not yet approved** and must not
start until the user approves it; it no longer gates steps 1–8. No
implementation has started. This document
is temporary execution state, not shipped guidance. Update it as work proceeds;
remove it once its contracts have reached the manual, CLI help and tests.

## Objective

1. Private custody lives in Git's common administrative directory, under
   `<git-common-dir>/stewart/`.
2. Auditor checkouts, their supplied runtimes and experiment homes live outside
   every working tree of the repository and outside the Git directory, under a
   per-user checkout home.

Afterwards Stewart writes nothing into a maintainer working tree that needs an
ignore rule, and no `git clean` in a maintainer checkout can remove custody
records or an auditor's checkout.

## Execution contract

Read [AGENTS.md](AGENTS.md) before work. The custody rules there are unchanged:
exclusive receipts, `contained` and descriptor-relative reads, refusals with
stable reasons, retained paths and next steps, side-effect-free import, and
paths derived from explicit identities rather than literals.

Stewart is at 0.1.0 with no consumers, so this change carries no backward
compatibility. Bump schemas, and let the existing `session_schema_unsupported`
refusal handle old sessions. Add no migration, shims or rewriting of historical
records.

Preserve unrelated working-tree changes. Untracked `LINUX-CONTAINERS-PLAN.md`
and `user-report.md` belong to other work. Do not spend real harness requests
(step 0) or download wheels (step 8) without the user's approval. The line
numbers below are at `76d331c`; recheck them before editing.

## Actor model

As stated by the user on 2026-10-18, Stewart is not an adversarial containment
tool. The auditor and the manager are both fallible, cooperative actors. When a
machine agent fills either role, "fallible" covers many mistakes a human alone
would rarely make: tidying worktrees it believes are stale, for example, or
deleting a directory whose name says scratch. Isolation serves two purposes:

- **The auditor's focus.** Everything that does not help answer the question
  stays out of the auditor's ambient environment and is available only on a
  need-to-know basis.
- **The manager's focus.** Isolating the manager from the auditor routes their
  exchange through Stewart's question types and its completion/response split.
  The manager's attention then goes to which question would help, not to
  whether the right bytes arrived.

Judge each guard in this plan by whether it prevents ordinary mistakes and keeps
the ambient environment need-to-know, not by its resistance to an attacker.
The user will revise the documentation's framing separately. This work changes
behavior and the facts the documentation states, not that framing.

## Why: evidence gathered on 2026-10-18

`user-report.md` is a first-contact report from the PolicyWitness maintainer.
It found that `.scratch/` reads as disposable in that project and agents follow
that reading. It also found that adopting Stewart means adding an ignore rule
by hand. Its suggestion: keep private storage in `.git/stewart/` and place
auditor checkouts outside the maintainer's working tree.

The deletion risk was reproduced with real Stewart rather than a hand-built
layout. Setup: the wheel from `.scratch/check-result-dist/`, byte-identical to
`src/stewart` at `76d331c`, on Homebrew Python 3.14. Each case used a fresh
throwaway repository with `/.scratch/` in `info/exclude`, then a real
`prepare`, a report written in the worktree, `collect`, and then `git clean`:

| Case | Session records | Supplied runtime | Worktree and report | Registry row, refs | `status` |
|---|---|---|---|---|---|
| no clean (control) | kept | kept | kept | kept | normal, exit 0 |
| `-fd` (invariance) | kept | kept | kept | kept | normal, exit 0 |
| `-fdx` | deleted | deleted | kept ("Skipping repository") | kept | `record_missing`, exit 0 |
| `-ffdx` | deleted | deleted | deleted | kept | `session_missing`, exit 2 |

After `-ffdx`, `status` suggests "if the ID is right and the assignment was
never prepared, prepare the committed prompt" (`status.py:320`). `prepare` then
refuses with reason `auditor_scope` ("auditor read scope would reopen a private
root"), with empty `retained` and `next_steps`. The refusal happens both before
and after `git worktree prune`. A fresh audit ID prepares in the same
repository, and after the prune the only remaining state that names the old
worktree path is the role registry row.

A linked maintainer worktree outside the main checkout was verified as an
interim workaround. Its sessions survive `git clean -fdx` in the main checkout,
and its prompt commits land on its own branch. This plan makes that workaround
unnecessary.

The actor model adds reasons for external checkouts:

- An external checkout has no directories of the maintainer repository above
  it. A harness that loads guidance from parent directories (Claude Code loads
  `CLAUDE.md` that way outside safe mode) does not pick up the maintainer's
  guidance during a non-qualified launch.
- The manager's working tree no longer contains live auditor checkouts.

Two observations shaped the later decisions:

- **Ambient audit names (decision 7).** In the same throwaway repositories,
  `git worktree list` named every audit's checkout path, for example
  `…/ws-799a6d0e6cd4/q1/worktree`. The manual's sub-agent section records
  rehearsals in which other audits' names reached auditors through ambient
  context.
- **Git's lock behavior (decision 8).** Verified with Git 2.54.0 on a locked
  worktree:
  - `git worktree remove` and `remove -f` refuse and print the lock reason;
    only `-f -f` overrides.
  - After the directory is deleted, `git worktree prune` keeps the locked
    registration.
  - `git worktree list --porcelain` shows the reason.

## Decisions (agreed)

1. **Repo-wide session namespace, bound to its maintainer.**
   - Sessions live at `<common>/stewart/sessions/<slug>/<audit-id>/` and are
     shared by all linked worktrees.
   - The existing `repo` and `maintainer_git_admin` checks bind each session to
     the maintainer checkout that prepared it.
   - An operation from another maintainer worktree refuses with a stable reason
     that names the owning checkout and the `--repo` to use.
   - An audit ID becomes unique per workspace per repository, matching the
     refs and the role registry.
2. **A checkout home with a default.**
   - The default is `~/.local/state/stewart/checkouts`. `prepare
     --checkout-home ABS` overrides it, and no environment variable selects it.
   - Only `prepare` reads the setting; the session records it. Later commands
     use the recorded paths, never the current setting.
   - Validation: absolute, with no symlinked component or ancestor, owned by
     the current user, mode 0700. It must not lie inside any registered
     worktree of the repository, the common directory, the manager home, the
     interpreter prefix or any other private root.
3. **No ignore-rule prerequisite.** Remove `require_private_exclusions`, the
   `private_storage_not_ignored` and `private_storage_tracked` reasons, and
   their guidance.
4. **Experiment HOME moves out of the session**, into the per-audit checkout
   directory. That HOME is written by project code. Attempt receipts, stdout
   and stderr stay in the private session.
5. **Evidence packages and input manifests stay at user-chosen paths** in the
   working tree. They are pinned by SHA-256 and can be regenerated from a
   collection. Change only the manual's examples so they no longer suggest
   `.scratch/`.
6. **The manager home default moves** from `~/.cache/stewart/managers` to
   `~/.local/state/stewart/managers`. `STEWART_MANAGER_HOME` and
   `--manager-home` remain. All of Stewart's per-user state then shares a
   parent whose name does not suggest it is disposable.

Decisions 7–9 were added after the actor-model review:

7. **Checkout directories are keyed by session UUID.**
   - The layout is `<checkout-home>/<repo-key>/<session-uuid>/`.
   - Neighboring directories, and `git worktree list` run from any checkout,
     then name no audit ID or workspace.
   - Sessions keep readable `<slug>/<audit-id>` paths, because only the manager
     sees them. The manager finds checkouts through `status`.
8. **Auditor checkouts stay locked for their lifetime.**
   - After registration, Stewart replaces the registration lock with a lifetime
     lock. Its reason names the checkout as a Stewart auditor checkout and says
     to run `stewart status` before removing it.
   - `git worktree remove` without `-f -f` and `git worktree move` then refuse,
     and `git worktree prune` keeps the registration and its role marker.
   - Stewart never unlocks or removes a checkout. `status` prints the
     unlock-and-remove commands for the manager to run.
9. **The manager's write locations are surfaced.**
   - Every custody-writing command writes `<common>/stewart`. `prepare`,
     `recover-runtime` and experiment runs also write the checkout home, which
     is outside the manager's working directory.
   - `status` reports these locations for the repository.
   - A permission failure under them refuses with a stable reason that names
     the location the manager's harness must grant.

Decisions 10–14 are trims to user-visible output, agreed the same day. Each is
carried by a step that already rewrites that output:

10. **Help labels say what they leave untouched.**
    - Every invocation, including `--help` and `docs`, installs the selected
      source into the manager home before the CLI runs. That install stays.
    - Reword the `[read-only]` labels on `status` and `triage-draft`
      (`cli.py:169,222`) and the `docs` label (`cli.py:80`). The new labels
      name what the command does not write: the repository and session
      records.
11. **The auditor handoff carries only what the auditor needs.**
    - Remove the harness-configuration paragraph (`prepare.py:319-322`) and
      the mention of the private session directory (`prepare.py:312`).
    - The manager already receives the harness requirement from `prepare` and
      `status`.
    - The handoff names the worktree, the runtime, the helpers and the
      auditor's guidance, and nothing private.
12. **`status` shows the runtime recovery command only when it is needed.**
    - Today the command appears whenever the backup copy of the runtime
      (`runtime-pristine`) verifies (`status.py:469`, `cli.py:606-608`), which
      is nearly always.
    - Show it only when the runtime the auditor uses fails verification
      (`current_runtime.matches_expected` is false; state
      `runtime_unavailable`).
    - In JSON, `runtime_recovery` is null otherwise.
13. **`status` drops the live report path.**
    - Remove `identities.live_report_path` (`status.py:420`), the "Live report
      destination" line (`cli.py:621`), and the live-report mention in the
      `status` help description (`cli.py:170-171`).
    - The auditor learns its report path from the handoff, and the manager
      reads collected bytes.
14. **`status` without `--audit-id` lists the workspace's sessions.**
    - One line per session: audit ID, owning maintainer checkout, preparation
      state, checkout path, lock state, and whether a collection exists.
    - Decisions 7 and 8 rely on this. Checkouts are named by UUID and sessions
      live inside Git's directory, so the manager needs a listing to find them.

Decisions 12–14 change the status JSON, so bump `stewart.status/11` to
`stewart.status/12`.

## Target layout

```
<git-common-dir>/stewart/                  private; manager only, auditor denied
  worktree-roles/<uuid>.json               unchanged
  sessions/<slug>/<audit-id>/              session.json, LAUNCH.md, runtime-pristine/,
                                           RUNTIME-PREPARED.json, runtime-prepared/,
                                           collections/, launches/, messages/, triage/,
                                           retention/, runtime-recoveries/,
                                           attempts/<name>/ (receipts, stdout, stderr),
                                           HARNESS-EXIT.txt, PREPARE-ERROR.json

<checkout-home>/<repo-key>/<session-uuid>/         auditor- and process-facing
  worktree/                                auditor read-write
  runtime/                                 auditor read-only
  runtime-recovered-<stamp>/
  attempts/<name>/home/                    experiment process HOME
```

`<repo-key>` is a readable name plus `sha256_text(common_dir)[:12]`, the same
pattern as the workspace slug. The name is the common directory's parent name
when the common directory is a `.git` directory, and its own name for a bare
common directory. One checkout home can serve several repositories. Below the
repository key, names are session UUIDs only (decision 7). The session record
maps each UUID to its workspace and audit ID. Below, `<audit-dir>` means this
per-audit checkout directory.

## Sequence

### 0. Qualify the sandbox boundary (needs user approval; not a gate)

After the move, keeping sessions out of the auditor's reach depends on
`denyRead <common>/stewart` nesting inside `allowRead <common>`
(`auditor_scope.py:58-80`). Today only the role registry depends on that
nesting. Under the actor model, the question is whether a fallible auditor
could come across private material, not whether an attacker could reach it.
Without the deny, `<common>/stewart` is still reachable only by an absolute
path into Git internals that nothing in the auditor's context names. So steps
1–8 proceed with today's settings shape, and this step runs whenever the user
approves it. Qualify with the current code, since the registry already sits at
that location.

- Prepare a session in a throwaway repository with a `claude-code-restricted/1`
  launch profile. Also place a maintainer-written sentinel under
  `<common>/stewart/` to model the future session location.
- Have the auditor attempt each access through both the Read tool and Bash
  (`cat`):
  - **Firing control:** a sentinel in the worktree is readable.
  - **Measured case:** the registry row and the sentinel under
    `<common>/stewart/` are refused.
  - **Invariance case:** `git log -1`, `git cat-file -p HEAD` and `git status`
    still work in the worktree.
  - **Also record:** whether a file in the maintainer checkout outside the
    worktree and `.git` is refused. That is today's nested deny.
- Keep the evidence outside the repository. Record here the harness version,
  the digest of the settings JSON, the exact prompts and the outcomes.
- **Outcome A, the deny holds:** keep the `<common>` read grant plus the
  `<common>/stewart` deny.
- **Outcome B, the deny does not hold:** report it to the user as a
  need-to-know gap.
  - Try replacing the `<common>` read grant with an explicit list of the Git
    paths the auditor needs (objects, refs, packed-refs, config, info, and its
    own `worktrees/<name>`).
  - Adopt that list only if a set of everyday commands all still work under
    it: `log`, `show`, `diff`, `blame`, `grep` and `status`. A cooperative
    auditor's ordinary Git use matters more than a perfect seal.
  - Otherwise, keep the grant and document the gap.

Only step 4's `<common>` read grant depends on this outcome.

### 1. Derive every storage root in one place

- Replace `PRIVATE_ROOTS` (`_repository.py:23`), `SESSIONS_ROOT`
  (`workspace.py:25`), `Workspace.sessions` and `Workspace.session`
  (`workspace.py:100-104`) with one storage derivation. It takes `maintainer()`'s
  identity (`common_dir`) plus the checkout home and yields the session
  directory and the per-audit checkout directory. `Workspace` keeps only
  assignment-facing paths; drop `sessions` from `Workspace.to_json` and remove
  the `.scratch` workspace refusal (`workspace.py:124`).
- Resolve paths with `contained(common, "stewart/sessions/<slug>/<id>")` and
  `contained(checkout_home, "<repo-key>/<session-uuid>")`. `relative()` needs no
  change, because these relative paths contain no `.git` component.
- Create `<common>/stewart` with mode 0700 explicitly, because
  `mkdir(parents=True)` does not apply the mode to parents.
- Decision 6: change the default in `manager_home` (`_bootstrap.py:445`) and the
  hard-coded private root in `scope_for` (`auditor_scope.py:51`).
- Decision 10: reword the help labels while the manager home's location is
  changing.
- If a new module is added, update the source inventory (`SOURCE_MODULES` and
  `SOURCE_FILES` in `_bootstrap.py`) and the distribution tests.
- Keep all Git and filesystem work inside operations, never at import or in
  parser construction.

### 2. Prepare

- Drop `require_private_exclusions` (`prepare.py:46`).
- Validate the checkout home (decision 2) before allocating anything.
- Create the session directory, then the checkout directory, each
  exclusively. Any failure writes `PREPARE-ERROR.json` in the session and
  retains both directories.
- Run `git worktree add --detach --lock …` into `<audit-dir>/worktree`
  (`prepare.py:124,177`). Place the runtime at `<audit-dir>/runtime`
  (`prepare.py:127`).
- Decision 8: once the marker and role are published, replace the registration
  lock with the lifetime lock (`prepare.py:182` unlocks today). Git cannot
  change a lock's reason in place, so unlock and lock again immediately. The
  published marker classifies the checkout during the brief unlocked window.
- Bump `SESSION_SCHEMA` from 11 to 12, recording `checkout_home` and
  `audit_dir`.
- Update the paths and wording in the rendered `LAUNCH.md`, the public handoff
  and the printed launch and probe blocks.
- Decision 11: in the same rewrite, remove the manager-facing text from the
  handoff (`_render_handoff`, `prepare.py:312,319-322`). The runtime's parent
  is now the per-audit checkout directory, so replace "never its parent" with
  a plain instruction to read only that subtree.

### 3. Roles

- In `_prospective_role` (`_repository.py:170`), require the worktree to equal
  both `record["worktree"]` and `<audit-dir>/worktree`, instead of
  `session/"worktree"`.
- Replace the path-shape backstop `_reserved_auditor_root` (`_repository.py:45`,
  used at `:137`). The new rule refuses a maintainer root inside the default
  checkout home or inside any registered auditor's checkout directory. The
  marker, registry and lock remain the primary mechanism.
- `maintainer()` treats a lock reason that begins with `LOCK_PREFIX` as an
  unfinished registration (`_repository.py:152-155`). Give the lifetime lock a
  reason that cannot be mistaken for it, and keep the marker check first.
- Bump `ROLE_SCHEMA` only if the registry row's fields change.

### 4. Auditor scope

- Bump `SCOPE_SCHEMA` to `stewart.auditor-scope/3`.
- Make `<common>/stewart` an explicit private root; today `claude_settings`
  appends it (`auditor_scope.py:62`). Add the other registered audits' checkout
  directories as private roots.
- Replace the `runtime.is_relative_to(worktree.parent)` rule
  (`auditor_scope.py:36`). The new rule: the worktree and runtime are distinct
  children of the checkout directory, and neither lies under the maintainer
  repository, any registered worktree, the common directory, the manager home
  or the interpreter prefix.
- Keep today's `<common>` read grant until step 0 reports, then change it only
  as its outcome directs.
- Test settings construction separately from real enforcement.

### 5. Recorded paths and experiments

- Derive these from the session's recorded `audit_dir`, never the current
  setting:
  - `session.py:211`: the expected runtime root and the scope comparison.
  - `runtime.py:304` and `captured.py:335`: the recovery destination and its
    expected value.
  - `session_dir` (`session.py:151`), `assignment.py:339` and `handoff.py:136`.
- Decision 4: set the experiment `HOME` (`experiment.py:199`) to
  `<audit-dir>/attempts/<name>/home`. Attempt receipts stay at
  `session/attempts/<name>` (`experiment.py:264,366`). Update the
  `output_area_policy` wording.

### 6. Status and refusals the manager sees

- **Missing session records.** When no session directory exists, have `status`
  consult the role registry and `refs/stewart/sessions/*` for this workspace
  and audit ID. A registered session whose records are missing gets a new
  stable reason, naming the UUID, the registry row and the refs. Its next step
  is to preserve them and use a fresh audit ID. Remove the "never prepared,
  prepare it" hint from that case.
- **Same-ID re-prepare.** Have `prepare` detect a registry row for the same
  session path before constructing the scope. With UUID-keyed checkouts
  (decision 7), the session path is where a same-ID re-prepare now collides. It
  refuses with a stable reason, retained paths and next steps, instead of the
  bare `auditor_scope` refusal. Give `validate_scope` refusals next steps too.
- **Cross-maintainer refusal** from decision 1.
- **Checkout removal (decision 8).** `status` prints the unlock-and-remove
  commands as manager-run commands. Note that removing a checkout ends any
  further auditor work in it, such as the resume of a paused hold.
- **Manager write locations (decision 9).** `status` reports
  `<common>/stewart` and the checkout home for this repository. Map a
  permission failure under either to a stable reason that names the location
  and the harness grant to add, instead of an unexplained `OSError`.
- **Recovery command (decision 12).** Condition `runtime_recovery` on the
  current-runtime check.
- **Live report path (decision 13).** Remove it from the JSON, the text and the
  help.
- **Session listing (decision 14).** Make `--audit-id` optional for `status`
  (`cli.py:180`). Without it, list every session for the workspace across the
  repository, each with its owning maintainer. Include unreadable or invalid
  session records as listed problems, never skip them. A workspace with no
  sessions lists none and exits 0.
- Bump the status JSON schema to `stewart.status/12`.
- Reason identifiers are part of the JSON contract; assert them in tests.

### 7. Documentation and help

Write help text and failure messages along with each code change. Update the
facts the documentation states. Do not rewrite its framing toward the actor
model, which the user will revise separately. Then update:

- **`src/stewart/resources/README.md`:**
  - Ownership.
  - Manager quick start, step 2: every custody-writing command (`prepare`,
    `launch`, `message`, `collect`, `triage`, `resume`, `recover-runtime`,
    experiment commands) now writes Git administration, so the manager's
    harness needs write authorization for the common directory and the
    checkout home. Point to `status` for the exact locations (decision 9).
  - The worktree-role and reserved-root paragraph, including the lifetime
    lock. Moving or removing a checkout now requires unlocking it first.
  - The ignore-rule paragraph: delete it.
  - The manager home paragraph.
  - Manual terminal launch and sub-agent launch grants.
  - Failure and interruption recovery.
  - The evidence handoff examples: replace the `.scratch/` paths.
  - Static audit lifecycle, step 6, "Inspect" (around line 389): live report
    destinations (decision 13), the listing mode (decision 14), and the
    `stewart.status/12` locators.
  - Optional experiment lifecycle: HOME.
  - Records.
  - Coverage and limits. State what can still destroy custody: removing or
    re-cloning the Git directory, deleting a checkout before `collect`, and
    backups that skip `.git`.
- **`README.md:70`.**
- **`src/stewart/resources/MAINTAINER.md`.**
- **The `prepare` help** (`cli.py:117`) and the new `--checkout-home` option.
- **The `status` help** for the optional `--audit-id` and the listing, and the
  relabeled commands (decision 10).
- **Module docstrings** in `workspace.py` and `_repository.py`.

### 8. Tests and checks

Update the existing assertions on old paths. At `76d331c` these are in
`stewart_support.py`, `acceptance.py`, `test_auditor_scope.py`,
`test_authority.py`, `test_repository.py`, `test_stewart_declaration.py` and
`test_stewart.py`. Remove the `.scratch/` rule from `make_checkout`'s
`.gitignore`, so the suite itself shows that no ignore rule is needed.

Test helpers pass an explicit checkout home under `tmp_path`, so the suite
never writes the real home. Test the default only in a subprocess whose `HOME`
points into `tmp_path`.

New behavioral tests. Each has a firing control, a case that differs in the
measured property, and an invariance case:

- **`git clean -ffdx` in the maintainer.**
  - Control: an ignored file in the working tree is removed.
  - Measured: the session, checkout and runtime survive.
  - Invariance: `status --json` is identical before and after.
- **No working-tree footprint.**
  - Measured: `git status --porcelain --ignored` of the maintainer checkout is
    identical before and after `prepare` and `collect`, with no ignore rules
    present.
  - Control: an ordinary new file does appear.
- **The full flow** at unrelated and nested workspace paths, and from a linked
  maintainer worktree.
- **Two maintainer worktrees** preparing the same workspace and audit ID: the
  second refuses with the cross-maintainer or `destination_exists` reason and
  names the first.
- **Each checkout-home refusal:** inside the repository, inside a linked
  worktree, inside the common directory, inside the manager home, under the
  interpreter prefix, a symlinked ancestor, and a group- or world-accessible
  mode. Control: a valid home succeeds.
- **A maintainer root inside a registered auditor checkout** is refused, both
  with the marker present and with it removed (the backstop).
- **A deleted session and checkout.**
  - `status` reports the new missing-records reason.
  - A same-ID `prepare` refuses with retained paths and next steps.
  - Control: a fresh ID succeeds.
- **UUID-keyed checkouts.**
  - Measured: neither the checkout path nor `git worktree list` run inside the
    checkout contains the audit ID or the workspace name. Use distinctive
    names that cannot occur in a UUID or digest.
  - Control: the session path does contain both.
- **The lifetime lock.**
  - Measured: `git worktree remove` and `remove -f` refuse on an auditor
    checkout. After its directory is deleted, `git worktree prune` keeps the
    registration and role marker.
  - Control: the same commands remove an unlocked plain worktree.
  - Invariance: the auditor's ordinary Git commands in the checkout behave the
    same.
  - The lifetime lock is not reported as an unfinished registration.
- **Manager write locations.**
  - Measured: making the checkout home or `<common>/stewart` unwritable gives
    the new stable reason, naming that location.
  - Control: the writable case succeeds.
  - `status` reports both locations.
- **The auditor handoff (decision 11).**
  - Measured: the handoff names no session path, `<common>/stewart`, role
    registry or manager home, and contains no harness-configuration paragraph.
  - Control: it names the worktree and runtime paths.
- **The recovery command (decision 12).**
  - Measured: it is absent from text and JSON while the runtime verifies, and
    present after a byte in the runtime changes.
  - Invariance: the rest of the status view is unchanged.
- **No live report path (decision 13).** Measured: neither text nor JSON
  contains the live report destination. Control: collected report locations are
  still listed.
- **Session listing (decision 14).**
  - Measured: with sessions from two maintainer worktrees and one unreadable
    session record, the listing shows all three. Each has its owner, and the
    unreadable one is shown as a problem.
  - Control: `status --audit-id` for one of them gives the same detailed view
    as before.
  - Invariance: an empty workspace lists none.
- **The experiment HOME** is under the checkout directory, and attempt receipts
  are in the session.
- **Scope settings construction** for the new layout, including the step 0
  outcome.

Provision `requirements.lock` into a wheelhouse; `.scratch/wheelhouse` was
absent on 2026-10-18, so this needs network access and the user's approval.
Then run `scripts/check.py`, unfiltered, on Python 3.11 and 3.14. Report the
actual collected, selected and passed counts, and preserve the outputs. Do not
overwrite `.scratch/check-result.json` from earlier runs; choose fresh
`--result` paths.

## Observed, outside this plan

Every `python -m stewart` invocation, including `--help`, deploys the selected
source into the manager home. This was verified on 2026-10-18 with a fresh
`STEWART_MANAGER_HOME`; importing the package alone writes nothing. Decision 10
fixes the help labels. Making `--help` and `docs` skip the deployment would
change the bootstrap's run-only-verified-code design and is not part of this
plan.

The actor-model review also raised two points for the user's documentation
and later design work. None is a storage-location change:

- **Shared refs.** Linked worktrees share every ref. An auditor's `git log
  --all` or `git branch -a` shows other audits' prompt commits (through
  `refs/stewart/sessions/*`) and the maintainer's later work. Hiding these
  needs a different checkout mechanism, such as a dedicated clone.
- **The custody manual in the handoff.** The auditor handoff points to the
  bundled custody manual (`prepare.py:317`), which is mostly manager
  operations. It does follow that pointer with "Read only the assigned
  sections" (`prepare.py:318`), so this matters only if assignments leave the
  sections unnamed.

## Completion

Done when:

- step 0's outcome is recorded here; if the user has not approved it by then,
  record that it remains open and what its outcome would change;
- steps 1–8 meet the contracts above;
- the manual, help and tests carry those contracts;
- full unfiltered checks pass on both interpreters, with the counts reported.

Then remove this file.
