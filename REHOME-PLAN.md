# Rehome Stewart's storage

Execution plan prepared 2026-10-18 and agreed with the user the same day.

Status: design and sequence agreed. Step 0 is **not yet approved** and must not
start until the user approves it. No implementation has started. This document
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

<checkout-home>/<repo-key>/<slug>/<audit-id>/      auditor- and process-facing
  worktree/                                auditor read-write
  runtime/                                 auditor read-only
  runtime-recovered-<stamp>/
  attempts/<name>/home/                    experiment process HOME
```

`<repo-key>` is a readable name plus `sha256_text(common_dir)[:12]`, the same
pattern as the workspace slug. The name is the common directory's parent name
when the common directory is a `.git` directory, and its own name for a bare
common directory. One checkout home can serve several repositories.

## Sequence

### 0. Qualify the sandbox boundary first (gated: needs user approval)

Session confidentiality would newly depend on `denyRead <common>/stewart`
nesting inside `allowRead <common>` (`auditor_scope.py:58-80`). Today only the
role registry depends on that nesting. Qualify it with the current code, since
the registry already sits at that location.

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
- **Outcome B, the deny does not hold:** the registry is exposed today, so
  report that to the user at once. In step 4, replace the `<common>` read grant
  with an explicit list of the Git paths the auditor needs (objects, refs,
  packed-refs, config, info, and its own `worktrees/<name>`), then requalify.

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
  `contained(checkout_home, "<repo-key>/<slug>/<id>")`. `relative()` needs no
  change, because these relative paths contain no `.git` component.
- Create `<common>/stewart` with mode 0700 explicitly, because
  `mkdir(parents=True)` does not apply the mode to parents.
- Decision 6: change the default in `manager_home` (`_bootstrap.py:445`) and the
  hard-coded private root in `scope_for` (`auditor_scope.py:51`).
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
- Bump `SESSION_SCHEMA` from 11 to 12, recording `checkout_home` and
  `audit_dir`.
- Update the paths and wording in the rendered `LAUNCH.md`, the public handoff
  and the printed launch and probe blocks.

### 3. Roles

- In `_prospective_role` (`_repository.py:170`), require the worktree to equal
  both `record["worktree"]` and `<audit-dir>/worktree`, instead of
  `session/"worktree"`.
- Replace the path-shape backstop `_reserved_auditor_root` (`_repository.py:45`,
  used at `:137`). The new rule refuses a maintainer root inside the default
  checkout home or inside any registered auditor's checkout directory. The
  marker, registry and lock remain the primary mechanism.
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
- Set the `<common>` read grant according to step 0's outcome.
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

### 6. Missing and foreign sessions

- When no session directory exists, have `status` consult the role registry and
  `refs/stewart/sessions/*` for this workspace and audit ID. A registered
  session whose records are missing gets a new stable reason, naming the UUID,
  the registry row and the refs. Its next step is to preserve them and use a
  fresh audit ID. Remove the "never prepared, prepare it" hint from that case.
- Have `prepare` detect a registry row for the same session or checkout path
  before constructing the scope. It then refuses with a stable reason, retained
  paths and next steps, instead of the bare `auditor_scope` refusal. Give
  `validate_scope` refusals next steps too.
- Add the cross-maintainer refusal from decision 1.
- Reason identifiers are part of the JSON contract; assert them in tests.

### 7. Documentation and help

Write help text and failure messages along with each code change. Then update:

- **`src/stewart/resources/README.md`:**
  - Ownership.
  - Manager quick start, step 2: every custody-writing command (`prepare`,
    `launch`, `message`, `collect`, `triage`, `resume`, `recover-runtime`,
    experiment commands) now writes Git administration, so the manager's
    harness needs write authorization for the common directory.
  - The worktree-role and reserved-root paragraph.
  - The ignore-rule paragraph: delete it.
  - The manager home paragraph.
  - Manual terminal launch and sub-agent launch grants.
  - Failure and interruption recovery.
  - The evidence handoff examples: replace the `.scratch/` paths.
  - Optional experiment lifecycle: HOME.
  - Records.
  - Coverage and limits. State what can still destroy custody: removing or
    re-cloning the Git directory, deleting a checkout before `collect`, and
    backups that skip `.git`.
- **`README.md:70`.**
- **`src/stewart/resources/MAINTAINER.md`.**
- **The `prepare` help** (`cli.py:117`) and the new `--checkout-home` option.
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
source into the manager home. The `[read-only]` labels in the CLI help describe
effects on the repository only. This was verified on 2026-10-18 with a fresh
`STEWART_MANAGER_HOME`; importing the package alone writes nothing. Decide
separately whether the help should say so.

## Completion

Done when:

- step 0's outcome is recorded here;
- steps 1–8 meet the contracts above;
- the manual, help and tests carry those contracts;
- full unfiltered checks pass on both interpreters, with the counts reported.

Then remove this file.
