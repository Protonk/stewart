# Preparing material in Git for Stewart

**Frozen Python guide.** This generated source inventory is retained for the
legacy implementation and its checks. It is not a successor requirement; the
[current design](DESIGN.md) takes copied files and has no Git relationship.

This document is for the people who keep material in a Git repository and
run Stewart over it. It says what this version of Stewart expects of that
repository, what it places in and beside it, how it runs Git, and what it
does not support or cannot help with. A reference table follows, generated
from Stewart's source, and a guide to the table says which rows you can rely
on and what each asks of you.

## What Stewart expects

Stewart works in one non-bare Git repository with a working tree, and you
run it from the top of that working tree; a bare repository or a
subdirectory is refused (`repository_root`). It runs the `git` it finds on
your `PATH`. Stewart is qualified on macOS with Apple Git 2.54.0 and Python
3.14, in repositories using SHA-1 object IDs; other Git versions, other
hosts and SHA-256 repositories are not qualified.

An audit is commissioned by commits. The workspace guidance and the
assignment are committed before preparation, and the commit that assigns the
audit changes the assignment alone, on top of the commit being audited
(`prompt_commit_shape`, `target_ancestry`). Files outside the workspace must
not differ between the audited commit and the assigning one (`target_drift`,
`input_drift`). The auditor's copy of the subject comes from those commits,
so later edits in your working tree do not reach it. Two things do come from
your working tree: pinned supplemental inputs, which Stewart copies from your
files and checks against their recorded digests, and the working copy of the
assignment, which must match the assigning commit (`prompt_drift`).

## What Stewart places in and beside your repository

- **Private records** under `stewart/` inside your repository's Git
  directory. `git clean` and branch work cannot touch them, and neither
  cloning nor mirroring copies them. They are lost if the Git directory is
  deleted or re-cloned, or if a backup skips `.git`. Do not edit or remove
  them by hand; closing an audit is how they end.
- **Refs** under `refs/stewart/sessions/<id>/` that keep each audit's
  commits from being garbage-collected. An ordinary clone leaves them behind.
  `git clone --mirror`, `git push --mirror`, a remote configured with
  `remote.<name>.mirror`, and `git bundle create --all` copy them, together
  with the commits they name, which include each audit's assigning commit.
  Push with explicit refspecs, or close audits first, if those commits should
  not travel.
- **An auditor checkout** for each audit: a locked, detached linked worktree
  outside your working tree, by default under
  `~/.local/state/stewart/checkouts`. `git worktree list` shows it. Do not
  remove, move, repair or force-prune it; closing the audit removes it.
- **Files in your working tree, when you ask.** `init --replace-prompt`
  rewrites the assignment and writes its input manifest; `retain` publishes
  reviewed deliverables at their paths; `export` writes a package where you
  name it. Stewart never stages or commits them.
- **Branches and worktrees of your own**, only when you ask Stewart to create
  them for an audit.

## How Stewart runs Git

- Every Git command Stewart runs has hooks and the file-system monitor turned
  off and takes no optional locks. Four variables are removed from its
  environment: `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` and
  `GIT_COMMON_DIR`. Every other variable is inherited, including
  `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_CONFIG_*`
  and the replacement-object variables. Run Stewart without Git variables you
  have not chosen deliberately.
- Your user, system and repository configuration all apply. Filters you have
  configured run when the auditor checkout is created, and clean filters are
  expected to run when collection compares the files the auditor changed;
  the auditor can edit the attributes that select them. Git LFS's filter
  runs at checkout and may contact its server.
- Settings that change Git's output reach Stewart's records: `color.ui=always`
  and `diff.noprefix` alter the patches collection keeps.
- On macOS Stewart assumes Git precomposes Unicode names
  (`core.precomposeUnicode`, Git's default there).
- `worktree.useRelativePaths` is not qualified; with it, closing an audit is
  expected to leave Git's administration for the auditor checkout behind.
- The auditor runs Git too, in its own environment. Under the launch adapter
  Stewart constructs, it can read your whole Git directory apart from
  Stewart's records, including every ref and object, and cannot write any of
  it. Under a manual or sub-agent launch,
  Stewart constructs no boundary at all.
- A script you release for the auditor runs with your `PATH`, a private
  `HOME` and no sandbox. Any Git it runs finds the auditor checkout through
  its `.git` file, with hooks enabled and your configuration applied, and can
  write your Git directory as you.

## What Stewart does not support

- **Names that differ only by case or by Unicode normalization.** On the
  default macOS filesystem, a commit holding both `Notes.md` and `notes.md`
  yields an auditor checkout with one file and one entry's bytes. Stewart
  does not detect this. The auditor sees an unexplained change, and the
  other entry's bytes never reach it. Rename such files before commissioning
  an audit.
- **Names stored decomposed.** On macOS a committed name stored in Unicode
  decomposed form (NFD) is reported as an unexpected path although nothing
  changed. Expect that gap, or store such names precomposed.
- **Checkout transformations.** Anything that changes bytes on checkout makes
  the auditor's copy of a file differ from the committed bytes while Git
  reports the file unchanged: an attribute such as `text eol=crlf`,
  configuration such as `core.autocrlf=true` or `core.eol=crlf`, `ident`,
  `working-tree-encoding`, or a large-file filter. Stewart then never
  archives that file, closing the audit as concluded is refused
  (`capture_uncovered`), and collecting again cannot help; abandoning it
  needs an explicit discard. If the transformation touches an assigned
  input, preparation fails instead (`prepare_failed`, recording
  `input_mismatch`). To check a commit before commissioning it, run
  `git ls-files --eol` in a checkout of it with your configuration: a line
  showing `i/lf w/crlf` is a file Stewart would handle this way.
- **Submodule contents.** Stewart does not populate submodules. Preparation
  refuses a commit holding them until you acknowledge it, and their paths are
  empty in the auditor checkout, unless your configuration sets
  `submodule.recurse`, which may make Git populate them (not qualified).
  Supply code the audit needs as committed copies or pinned inputs.
- **Replacement objects and grafts.** The auditor's checkout, preparation's
  ancestry checks and the inputs Stewart pins all follow `git replace`;
  checking what a collection covers ignores it. In a repository that uses
  replacements, the auditor can be handed replaced content while coverage
  compares unreplaced bytes. Legacy grafts (`info/grafts`), which Git still
  honors, change the same ancestry checks and are disabled nowhere.
- **Shallow and partial clones.** Stewart is not qualified on them. History
  beyond a shallow boundary is absent. In a partial clone, Git fetches
  missing objects from the remote when they are read, so Stewart's reads of
  an audit's commits are expected to reach the network. Commission audits
  from a complete clone.
- **Moving or copying the repository while an audit is open.** After the
  repository is moved, every Stewart command in it refuses with
  `worktree_role_registry`, including closing or abandoning the open audit,
  until the repository is back at its original path. A copy refuses the same
  way while the original keeps working. The refusal does not say that
  restoring the path is the way out. Close audits before moving or copying a
  repository.

## Other places Stewart is particular about your repository

The table lists what Stewart's own Git calls and checks do. These conditions
are outside its classes and matter just as much:

- **Where auditor checkouts live** (`checkout_home`): an absolute path with no
  link anywhere along it, a directory you own with mode 0700, outside every
  working tree of the repository, not overlapping your Git directory,
  Stewart's manager home or the Python installation it runs from, and not
  containing your working tree.
- **Names beside `.git`** (`scope_uncovered`): preparation refuses when an
  entry at the top of your working tree, beside `.git`, has a name holding
  any of `* ? [ ] { } ( ) \` or a line break, because the auditor's access
  settings cannot deny it by name. Rename it and prepare again.
- **Links in Stewart's storage** (`path_symlink`): Stewart's `stewart/`
  directory in your Git directory, and the directories within it, must not be
  links.
- **Which checkout owns an audit** (`session_owner_missing`,
  `session_other_maintainer`): an audit belongs to the working tree that
  prepared it; other linked worktrees of the same repository are refused.
- **Lock reasons**: Stewart identifies its checkouts partly by the reason
  text on their Git locks. Do not change those locks.
- **Commit IDs**: where Stewart asks for a commit it takes a full commit ID,
  of either length, or `HEAD` where it is selecting a revision (`commit_id`).
- **Commands Stewart prints for you**: some refusals suggest a Git command,
  such as `git worktree remove -f -f <path>` for a worktree Git still
  registers. Stewart never runs these itself.

## Reference: the Git opinions Stewart holds

<!-- git-opinions:begin -->
<!-- Generated by scripts/git_opinions.py from the Python source under src/stewart; edit the script, not this region, and regenerate with --write. -->

Rows are selected by parsing Stewart's source: each is something its code does with Git. Each row's description is composed from fixed glosses of Git's commands and options, and of what the code does with a path. A row's ID is formed from that content and from the names of the code that holds it, never from a line number; it stays the same while the code holding the opinion is unchanged. **Where** names the `module:function` of Stewart's source that holds the opinion; **Reason** is the refusal identifier that code raises, when there is one. A refusal raised while preparing an audit is reported as `prepare_failed`, with this reason in the preparation's failure record.

### 1. Configuration common to every Git call (12 rows)

The settings, environment and working directory Stewart gives every Git command it runs. Your own Git configuration and the rest of your environment still apply and are not listed.

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `cfg.program` | Runs the program `git`, resolved through the inherited `PATH`; no absolute Git path is configured. | configuration | _git:_invocation |  |
| `cfg.c.core-hookspath` | Every Git command gets `-c core.hooksPath=/dev/null`. Hooks never run: Git looks for them in `/dev/null`. | configuration | _git:_invocation |  |
| `cfg.c.core-fsmonitor` | Every Git command gets `-c core.fsmonitor=false`. No file-system monitor runs. | configuration | _git:_invocation |  |
| `cfg.cwd` | Git runs in the directory each caller passes (`cwd=repo`): a checkout or repository root, except the Git common directory in `holdings:_create_branch`, `holdings:_git_common`, `holdings:_reachable_elsewhere`, `holdings:_ref_tip`, `holdings:retire_claim`; and the process's current directory in `report_declaration:main`, `verify_inputs:main`. Without `--git-dir`, Git discovers the repository from there. | configuration | _git:_invocation |  |
| `cfg.env.inherited` | Git inherits Stewart's whole environment, apart from the variables below. | configuration | _git:_invocation |  |
| `cfg.env.set.git-optional-locks` | Sets `GIT_OPTIONAL_LOCKS=0`. Git takes no optional locks, so read-only commands do not rewrite the index. | configuration | _git:_invocation |  |
| `cfg.env.removed.git-dir` | Removes `GIT_DIR` from the environment. An inherited value cannot redirect which repository Git addresses. | configuration | _git:_invocation |  |
| `cfg.env.removed.git-work-tree` | Removes `GIT_WORK_TREE` from the environment. An inherited value cannot redirect which working tree Git addresses. | configuration | _git:_invocation |  |
| `cfg.env.removed.git-index-file` | Removes `GIT_INDEX_FILE` from the environment. An inherited value cannot redirect which index Git reads or writes. | configuration | _git:_invocation |  |
| `cfg.env.removed.git-common-dir` | Removes `GIT_COMMON_DIR` from the environment. An inherited value cannot redirect the common directory. | configuration | _git:_invocation |  |
| `cfg.process.create-refs` | `create_refs` captures Git's output; standard input is `subprocess.PIPE`; stops Git after 120 seconds unless the caller passes `timeout`. | configuration | _git:create_refs |  |
| `cfg.process.git` | `git` captures Git's output; Git's standard input is Stewart's own unless the caller passes `input`; stops Git after 120 seconds unless the caller passes `timeout`. | configuration | _git:git |  |

### 2. Git invocations (57 rows)

Each distinct Git command Stewart's own code runs, where it runs it, and whether a failure stops the operation. Git run by the auditor or by an experiment, and Git commands Stewart only prints as advice, are not listed.

#### `git branch`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.branch.show-current` | Lists, reads or changes branches; reads the checked-out branch's name, empty when detached.<br>`git branch --show-current` | invocation | _repository:_prospective_role | `git_failed` |
| `inv.branch.show-current.via-git-dir-work-tree` | Lists, reads or changes branches; addresses a verified administration directly, never through `.git`; names the checkout explicitly; reads the checked-out branch's name, empty when detached.<br>`git --git-dir=<git_admin> --work-tree=<worktree> branch --show-current` | invocation | collect:checkout_state via collect:checkout_state.ask_text | `git_failed` |

#### `git cat-file`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.cat-file.batch.via-no-replace-objects` | Reads objects from the object database; replacement objects ignored; batch reads on standard input; input on standard input.<br>`git --no-replace-objects cat-file --batch` | invocation | coverage:prompt_identities | `git_failed` |
| `inv.cat-file.e` | Reads objects from the object database; tests that an object exists.<br>`git cat-file -e <prompt_commit>:<meta['report_path']>`<br>`git cat-file -e <revision>:<item['path']>`<br>`git cat-file -e <target>:<input_manifest>`<br>… 1 more form | invocation | assignment:_initialize, assignment:_initialize via assignment:expected_inputs, assignment:input_receipts via assignment:expected_inputs, prepare:_prepare |  |
| `inv.cat-file.e.via-git-dir-work-tree` | Reads objects from the object database; addresses a verified administration directly, never through `.git`; names the checkout explicitly; tests that an object exists.<br>`git --git-dir=<git_admin> --work-tree=<worktree> cat-file -e <issued['launch_prompt_commit']>:<rel>`<br>`git --git-dir=<git_admin> --work-tree=<worktree> cat-file -e <meta['target_commit']>:<item['path']>` | invocation | report_declaration:check_checkout, verify_inputs:verify_inputs via assignment:expected_inputs |  |

#### `git diff`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.diff.binary-cached-full-index-no-ext-diff-no-renames-no-textconv.via-git-dir-work-tree` | Compares commits, the index and the working tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; against the index; no external diff driver; no textconv filter; no rename detection; binary patches; full object IDs.<br>`git --git-dir=<git_admin> --work-tree=<worktree> diff --cached --no-ext-diff --no-textconv --no-renames --binary --full-index <prompt_commit>` | invocation | collect:checkout_state via collect:checkout_state.ask | `git_failed` |
| `inv.diff.binary-full-index-no-ext-diff-no-renames-no-textconv.via-git-dir-work-tree` | Compares commits, the index and the working tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; no external diff driver; no textconv filter; no rename detection; binary patches; full object IDs.<br>`git --git-dir=<git_admin> --work-tree=<worktree> diff --no-ext-diff --no-textconv --no-renames --binary --full-index <prompt_commit>` | invocation | collect:checkout_state via collect:checkout_state.ask | `git_failed` |
| `inv.diff.cached-name-only-no-renames-z.via-git-dir-work-tree` | Compares commits, the index and the working tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; against the index; names only; no rename detection; NUL-delimited.<br>`git --git-dir=<git_admin> --work-tree=<worktree> diff --cached --name-only --no-renames -z <issued['launch_prompt_commit']>`<br>`git --git-dir=<git_admin> --work-tree=<worktree> diff --cached --name-only --no-renames -z <prompt_commit>` | invocation | collect:checkout_state via collect:checkout_state.ask, report_declaration:check_checkout | `git_failed` |
| `inv.diff.name-only-no-renames-z` | Compares commits, the index and the working tree; names only; no rename detection; NUL-delimited.<br>`git diff --name-only --no-renames -z <parents[1]> <prompt_commit>`<br>`git diff --name-only --no-renames -z <target> <prompt_commit>` | invocation | prepare:_prepare | `git_failed` |
| `inv.diff.name-only-no-renames-z.via-git-dir-work-tree` | Compares commits, the index and the working tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; names only; no rename detection; NUL-delimited.<br>`git --git-dir=<git_admin> --work-tree=<worktree> diff --name-only --no-renames -z <prompt_commit>` | invocation | collect:checkout_state via collect:checkout_state.ask | `git_failed` |

#### `git for-each-ref`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.for-each-ref.contains-format-refname` | Lists refs; only refs containing a commit; named fields only.<br>`git for-each-ref --contains <commit> --format=%(refname)` | invocation | holdings:_reachable_elsewhere |  |
| `inv.for-each-ref.format-objectname-symref` | Lists refs; named fields only.<br>`git for-each-ref --format=%(objectname)%00%(symref) <ref>` | invocation | holdings:_ref_tip |  |
| `inv.for-each-ref.format-refname` | Lists refs; named fields only.<br>`git for-each-ref --format=%(refname) <ref>` | invocation | close:_still_there |  |
| `inv.for-each-ref.format-refname-objectname-symref.refs-stewart-sessions` | Lists refs; named fields only.<br>`git for-each-ref --format=%(refname)%00%(objectname)%00%(symref) refs/stewart/sessions/<uuid>/` | invocation | close:_session_refs |  |
| `inv.for-each-ref.format-refname.refs-stewart-sessions` | Lists refs; named fields only.<br>`git for-each-ref --format=%(refname) refs/stewart/sessions/<record['session_uuid']>/` | invocation | status:status |  |
| `inv.for-each-ref.format-refname.refs-worktree-refs-bisect` | Lists refs; named fields only.<br>`git for-each-ref --format=%(refname) refs/worktree refs/bisect` | invocation | holdings:_worktree_findings |  |

#### `git ls-files`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.ls-files.error-unmatch` | Lists paths in the index or working tree; every path must be tracked.<br>`git ls-files --error-unmatch -- *sorted(payloads)` | invocation | session:package_identity |  |
| `inv.ls-files.others-z.via-git-dir-work-tree` | Lists paths in the index or working tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; untracked paths; NUL-delimited.<br>`git --git-dir=<git_admin> --work-tree=<worktree> ls-files --others -z` | invocation | collect:checkout_state via collect:checkout_state.ask | `git_failed` |

#### `git ls-tree`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.ls-tree` | Lists a committed tree.<br>`git ls-tree <prompt_commit> -- <name>`<br>`git ls-tree <revision> -- <rel>`<br>`git ls-tree <target> -- <rel>` | invocation | assignment:_initialize via assignment:expected_inputs, assignment:input_receipts via assignment:expected_inputs, prepare:_prepare | `git_failed` |
| `inv.ls-tree.d-name-only-r-z.via-git-dir-work-tree` | Lists a committed tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; recursively; directories only; names only; NUL-delimited.<br>`git --git-dir=<git_admin> --work-tree=<worktree> ls-tree -r -d --name-only -z <prompt>` | invocation | close:_observe_checkout | `git_failed` |
| `inv.ls-tree.full-tree-r-z` | Lists a committed tree; recursively; NUL-delimited; the whole tree.<br>`git ls-tree -r -z --full-tree <commit>` | invocation | _git:gitlinks via _git:tree_entries, used through `gitlinks` by assignment (1), prepare (1) | `git_failed` |
| `inv.ls-tree.full-tree-r-z.via-git-dir-work-tree` | Lists a committed tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; recursively; NUL-delimited; the whole tree.<br>`git --git-dir=<git_admin> --work-tree=<worktree> ls-tree -r -z --full-tree <prompt_commit>` | invocation | collect:checkout_state via _git:tree_entries | `git_failed` |
| `inv.ls-tree.full-tree-r-z.via-no-replace-objects` | Lists a committed tree; replacement objects ignored; recursively; NUL-delimited; the whole tree.<br>`git --no-replace-objects ls-tree -r -z --full-tree <commit>` | invocation | coverage:prompt_identities via _git:tree_entries | `git_failed` |
| `inv.ls-tree.via-git-dir-work-tree` | Lists a committed tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly.<br>`git --git-dir=<git_admin> --work-tree=<worktree> ls-tree <meta['target_commit']> -- <rel>` | invocation | verify_inputs:verify_inputs via assignment:expected_inputs | `git_failed` |

#### `git merge-base`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.merge-base.is-ancestor` | Computes or tests merge bases; tests whether one commit is an ancestor of another.<br>`git merge-base --is-ancestor <target> <prompt_commit>` | invocation | prepare:_prepare |  |

#### `git rev-list`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.rev-list.n-parents.1` | Lists commits; with parent IDs; a limited count.<br>`git rev-list --parents -n 1 <prompt_commit>` | invocation | prepare:_prepare | `git_failed` |

#### `git rev-parse`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.rev-parse.absolute-git-dir` | Resolves a name or a repository location; the worktree's administration directory.<br>`git rev-parse --absolute-git-dir` | invocation | _repository:_separate_identity, holdings:_create_worktree, holdings:_enroll | `git_failed` |
| `inv.rev-parse.absolute-git-dir-git-common-dir-is-bare-repository-path-format-absolute-show-toplevel` | Resolves a name or a repository location; whether the repository is bare; the working tree's top level; the worktree's administration directory; absolute paths; the common directory.<br>`git rev-parse --is-bare-repository --show-toplevel --absolute-git-dir --path-format=absolute --git-common-dir` | invocation | _repository:checkout_identity |  |
| `inv.rev-parse.git-common-dir-path-format-absolute` | Resolves a name or a repository location; absolute paths; the common directory.<br>`git rev-parse --path-format=absolute --git-common-dir` | invocation | _repository:_separate_identity, report_declaration:_own_administration | `git_failed` |
| `inv.rev-parse.git-common-dir-path-format-absolute.via-git-dir-work-tree` | Resolves a name or a repository location; addresses a verified administration directly, never through `.git`; names the checkout explicitly; absolute paths; the common directory.<br>`git --git-dir=<git_admin> --work-tree=<worktree> rev-parse --path-format=absolute --git-common-dir` | invocation | collect:_collect | `git_failed` |
| `inv.rev-parse.head` | Resolves a name or a repository location.<br>`git rev-parse HEAD` | invocation | _repository:_prospective_role, holdings:_create_worktree, holdings:_worktree_head, session:maintainer_state, session:package_identity | `git_failed` at some sites; others read the exit status |
| `inv.rev-parse.head.via-git-dir` | Resolves a name or a repository location; addresses a verified administration directly, never through `.git`.<br>`git --git-dir=<git_admin> rev-parse HEAD` | invocation | status:_git_head |  |
| `inv.rev-parse.head.via-git-dir-work-tree` | Resolves a name or a repository location; addresses a verified administration directly, never through `.git`; names the checkout explicitly.<br>`git --git-dir=<git_admin> --work-tree=<worktree> rev-parse HEAD` | invocation | collect:checkout_state via collect:checkout_state.ask_text, experiment:_release, experiment:_run, report_declaration:auditor_context | `git_failed` at some sites; others read the exit status |
| `inv.rev-parse.is-bare-repository` | Resolves a name or a repository location; whether the repository is bare.<br>`git rev-parse --is-bare-repository` | invocation | _repository:_separate_identity |  |
| `inv.rev-parse.show-toplevel` | Resolves a name or a repository location; the working tree's top level.<br>`git rev-parse --show-toplevel` | invocation | _repository:_separate_identity, report_declaration:auditor_context, report_declaration:check_checkout, report_declaration:main, verify_inputs:main | `git_failed` |
| `inv.rev-parse.show-toplevel.via-git-dir-work-tree` | Resolves a name or a repository location; addresses a verified administration directly, never through `.git`; names the checkout explicitly; the working tree's top level.<br>`git --git-dir=<git_admin> --work-tree=<worktree> rev-parse --show-toplevel` | invocation | collect:_collect | `git_failed` |
| `inv.rev-parse.verify` | Resolves a name or a repository location; the name must resolve.<br>`git rev-parse --verify <entry['ref']>` | invocation | _repository:verify_retention |  |
| `inv.rev-parse.verify.commit` | Resolves a name or a repository location; the name must resolve.<br>`git rev-parse --verify <value>^{commit}` | invocation | _git:resolve_commit, used through `resolve_commit` by _repository (2), assignment (4), holdings (2), prepare (4) | `git_failed` |
| `inv.rev-parse.verify.head` | Resolves a name or a repository location; the name must resolve.<br>`git rev-parse --verify HEAD` | invocation | audits:_register |  |

#### `git show`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.show` | Shows objects.<br>`git show <prompt_commit>:<ws.prompt>`<br>`git show <revision>:<rel>`<br>`git show <target>:<rel>` | invocation | assignment:_initialize via assignment:expected_inputs, assignment:input_receipts via assignment:expected_inputs, prepare:_prepare, prepare:prepare | `git_failed` |
| `inv.show.via-git-dir-work-tree` | Shows objects; addresses a verified administration directly, never through `.git`; names the checkout explicitly.<br>`git --git-dir=<git_admin> --work-tree=<worktree> show <issued['launch_prompt_commit']>:<ws.prompt>`<br>`git --git-dir=<git_admin> --work-tree=<worktree> show <launch_prompt_commit>:<ws.prompt>`<br>`git --git-dir=<git_admin> --work-tree=<worktree> show <meta['target_commit']>:<rel>` | invocation | report_declaration:auditor_context, report_declaration:check_checkout, verify_inputs:verify_inputs, verify_inputs:verify_inputs via assignment:expected_inputs | `git_failed` at some sites; others read the exit status |

#### `git status`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.status.ignored-porcelain-v1-untracked-files-all-z` | Reports working-tree and index status; porcelain v1 format; NUL-delimited; every untracked file; ignored files included.<br>`git status --porcelain=v1 -z --untracked-files=all --ignored` | invocation | holdings:_worktree_findings |  |
| `inv.status.porcelain-v1-untracked-files-all-z` | Reports working-tree and index status; porcelain v1 format; NUL-delimited; every untracked file.<br>`git status --porcelain=v1 -z --untracked-files=all` | invocation | session:maintainer_state | `git_failed` |
| `inv.status.porcelain-v1-untracked-files-all-z.via-git-dir-work-tree` | Reports working-tree and index status; addresses a verified administration directly, never through `.git`; names the checkout explicitly; porcelain v1 format; NUL-delimited; every untracked file.<br>`git --git-dir=<git_admin> --work-tree=<worktree> status --porcelain=v1 -z --untracked-files=all` | invocation | collect:checkout_state via collect:checkout_state.ask | `git_failed` |
| `inv.status.porcelain-v1-z` | Reports working-tree and index status; porcelain v1 format; NUL-delimited.<br>`git status --porcelain=v1 -z -- <package>` | invocation | session:package_identity |  |

#### `git symbolic-ref`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.symbolic-ref.q.head.via-git-dir-work-tree` | Reads, writes or deletes a symbolic ref; addresses a verified administration directly, never through `.git`; names the checkout explicitly; tests whether the ref is symbolic, quietly.<br>`git --git-dir=<git_admin> --work-tree=<worktree> symbolic-ref -q HEAD` | invocation | report_declaration:auditor_context |  |
| `inv.symbolic-ref.quiet` | Reads, writes or deletes a symbolic ref; tests whether the ref is symbolic, quietly.<br>`git symbolic-ref --quiet <entry['ref']>`<br>`git symbolic-ref --quiet <ref>` | invocation | _git:create_refs, _repository:verify_retention, used through `create_refs` by _repository (1), holdings (1) |  |

#### `git update-ref`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.update-ref.d-no-deref` | Writes or deletes refs; never through a symbolic ref; deletes, checking the old value when one is given.<br>`git update-ref --no-deref -d <entry['ref']> <entry['commit']>`<br>`git update-ref --no-deref -d <identity['ref']> <frozen['tip']>` | invocation | close:_remove.remove_ref, holdings:retire_claim | `git_failed` |
| `inv.update-ref.stdin` | Writes or deletes refs; one transaction on standard input.<br>`git update-ref --stdin` | invocation | _git:create_refs, used through `create_refs` by _repository (1), holdings (1) |  |

#### `git worktree add`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.worktree-add.b-lock-reason.stewart-managed-worktree` | Creates a linked worktree; locked from creation; with a lock reason; on a new branch.<br>`git worktree add --lock --reason "stewart managed worktree <rid>: retire it with stewart close --resource" -b <branch> <target> <commit>` | invocation | holdings:_create_worktree | `git_failed` |
| `inv.worktree-add.detach-lock-reason.stewart-auditor-registration` | Creates a linked worktree; detached HEAD; locked from creation; with a lock reason.<br>`git worktree add --detach --lock --reason "stewart auditor registration <session_identity>" <worktree> <prompt_commit>` | invocation | prepare:_prepare | `git_failed` |
| `inv.worktree-add.detach-lock-reason.stewart-managed-worktree` | Creates a linked worktree; locked from creation; with a lock reason; detached HEAD.<br>`git worktree add --lock --reason "stewart managed worktree <rid>: retire it with stewart close --resource" --detach <target> <commit>` | invocation | holdings:_create_worktree | `git_failed` |
| `inv.worktree-add.lock-reason.stewart-managed-worktree` | Creates a linked worktree; locked from creation; with a lock reason.<br>`git worktree add --lock --reason "stewart managed worktree <rid>: retire it with stewart close --resource" <target> <existing_branch>` | invocation | holdings:_create_worktree | `git_failed` |

#### `git worktree list`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.worktree-list.porcelain` | Lists the worktrees Git registers; porcelain format.<br>`git worktree list --porcelain` | invocation | close:_registrations | `git_failed` |
| `inv.worktree-list.porcelain-z` | Lists the worktrees Git registers; porcelain format; NUL-delimited.<br>`git worktree list --porcelain -z` | invocation | _repository:worktree_roots | `git_failed` |

#### `git worktree lock`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.worktree-lock.reason.stewart-auditor-checkout` | Locks a linked worktree with a reason; with a lock reason.<br>`git worktree lock --reason "stewart auditor checkout <session_identity>: run stewart status before removing; close removes it with its session" <worktree>` | invocation | prepare:_prepare | `git_failed` |

#### `git worktree unlock`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.worktree-unlock` | Unlocks a linked worktree.<br>`git worktree unlock <worktree>` | invocation | prepare:_prepare | `git_failed` |

### 3. Refs Stewart names, creates or deletes (6 rows)

The ref names Stewart's code writes, and what it does with refs in each namespace. Refs it only learns from Git's output are not listed by name.

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `ref.refs` | `refs/`: prefix test. | ref | _git:create_refs |  |
| `ref.refs-bisect` | `refs/bisect`: passed to Git: `inv.for-each-ref.format-refname.refs-worktree-refs-bisect`. | ref | holdings:_worktree_findings |  |
| `ref.refs-heads` | `refs/heads/<branch>`, `refs/heads/<existing_branch>`: compared (in `holdings:_enroll`); passed to `_ref_tip`: `inv.for-each-ref.format-objectname-symref`; passed to `create_refs`: `inv.symbolic-ref.quiet`, `inv.update-ref.stdin` (in `holdings:_create_branch`); recorded; recorded refs deleted by `inv.update-ref.d-no-deref` (in `holdings:retire_claim`); recorded refs read by `inv.for-each-ref.contains-format-refname` (in `holdings:evaluate`); recorded refs read by `inv.for-each-ref.format-objectname-symref`; returned by `_create_worktree` (in `holdings:_create_worktree`); returned by `_enroll` (in `holdings:_enroll`). | ref | holdings:_create_branch, holdings:_create_worktree, holdings:_enroll, holdings:_revalidate, holdings:evaluate, holdings:observe, holdings:retire_claim |  |
| `ref.refs-stewart` | `refs/stewart/`: prefix test. | ref | holdings:_reachable_elsewhere |  |
| `ref.refs-stewart-sessions` | `refs/stewart/sessions/<ident>/<name>`, `refs/stewart/sessions/<record['session_uuid']>/`, `refs/stewart/sessions/<row['session_uuid']>`, `refs/stewart/sessions/<uuid>/`: named in a refusal (in `_repository:registered_session`); passed to Git: `inv.for-each-ref.format-refname-objectname-symref.refs-stewart-sessions` (in `close:_session_refs`); passed to Git: `inv.for-each-ref.format-refname.refs-stewart-sessions` (in `status:status`); prefix test (in `close:_facts`, `close:_read`); recorded refs created by `inv.update-ref.stdin` (in `_repository:retain_commits`); recorded refs deleted by `inv.update-ref.d-no-deref` (in `close:_remove.remove_ref`); recorded refs read by `inv.rev-parse.verify` (in `_repository:verify_retention`); recorded refs read by `inv.symbolic-ref.quiet` (in `_repository:retain_commits`, `_repository:verify_retention`); returned by `retention_for` (in `_repository:retention_for`). | ref | _repository:registered_session, _repository:retain_commits, _repository:retention_for, _repository:verify_retention, close:_facts, close:_read, close:_remove.remove_ref, close:_session_refs, status:status |  |
| `ref.refs-worktree` | `refs/worktree`: passed to Git: `inv.for-each-ref.format-refname.refs-worktree-refs-bisect`. | ref | holdings:_worktree_findings |  |

Invocation rows whose command writes refs: `inv.update-ref.d-no-deref`, `inv.update-ref.stdin`, `inv.worktree-add.b-lock-reason.stewart-managed-worktree`.

### 4. Git administration paths (23 rows)

The files and directories in Git's administration that Stewart reads, writes or checks, and where its own records live inside your repository's Git directory. Your working files and Stewart's checkout home are not listed.

#### Git's administration

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `adm.checkout.dot-git` | `<checkout>/.git`: checked (in `holdings:_revalidate`); compared (in `_repository:checkout_git_admin`, `holdings:_worktree_findings`); named in a refusal (in `_repository:checkout_git_admin`); read (in `_repository:checkout_git_admin`, `holdings:_worktree_findings`). | administration | _repository:checkout_git_admin, holdings:_revalidate, holdings:_worktree_findings |  |
| `adm.common` | `<common>`: listed under `allowRead`; listed under `denyWrite`. | administration | auditor_scope:claude_settings |  |
| `adm.common.worktrees` | `<common>/worktrees`: compared; listed (in `holdings:_admin_for`); opened without following links (in `close:_own_administrations`). | administration | _repository:checkout_git_admin, close:_facts, close:_own_administrations, close:_read, holdings:_admin_for, holdings:_create_worktree |  |
| `adm.common.worktrees.any.stewart-auditor-json` | `<common>/worktrees/*/stewart-auditor.json`: listed under `denyRead`. | administration | auditor_scope:claude_settings |  |
| `adm.common.worktrees.entry` | `<common>/worktrees/<name>`: compared; named in a message (in `holdings:_worktree_findings`); passed to `_admin_worktree` (in `close:_own_administrations`, `holdings:observe`); passed to `_remove_administration` (in `holdings:_remove_worktree`); passed to `admin_lifetime` (in `close:_own_administrations`); recorded (in `holdings:observe`); returned (in `close:_own_administrations`, `holdings:_admin_for`). | administration | close:_own_administrations, holdings:_admin_for, holdings:_remove_worktree, holdings:_worktree_findings, holdings:observe |  |
| `adm.common.worktrees.entry.stewart-resource-json` | `<common>/worktrees/<name>/stewart-resource.json`: read. | administration | holdings:_admin_for |  |
| `adm.content.gitdir` | a `.git` file holding one `gitdir: <path>` line: compared (in `holdings:_worktree_findings`); passed to `_git_pointer` (in `_repository:checkout_git_admin`). | administration | _repository:checkout_git_admin, holdings:_worktree_findings |  |
| `adm.git-admin` | `<git-admin>`: opened without following links (in `holdings:_remove_administration`); removed. | administration | close:_remove.remove_worktree, holdings:_remove_administration, holdings:_remove_worktree |  |
| `adm.git-admin.entry` | `<git-admin>/<named_back>`: compared. | administration | _repository:checkout_git_admin |  |
| `adm.git-admin.gitdir` | `<git-admin>/gitdir`: named in a refusal (in `_repository:checkout_git_admin`); read. | administration | _repository:checkout_git_admin, close:_admin_worktree, holdings:_worktree_findings |  |
| `adm.git-admin.in-progress` | `<git-admin>/{rebase-merge,rebase-apply,MERGE_HEAD,CHERRY_PICK_HEAD,REVERT_HEAD,BISECT_LOG}`: checked. | administration | holdings:_worktree_findings |  |
| `adm.git-admin.locked` | `<git-admin>/locked`: read. | administration | _repository:admin_lifetime, _repository:worktree_lock |  |
| `adm.git-admin.stewart-auditor-json` | `<git-admin>/stewart-auditor.json`: named in a refusal (in `_repository:_marker`); read (in `_repository:_marker`, `_repository:admin_lifetime`); written as an exclusive record (in `_repository:_publish_role`). | administration | _repository:_marker, _repository:_publish_role, _repository:admin_lifetime |  |
| `adm.git-admin.stewart-resource-json` | `<git-admin>/stewart-resource.json`: written as an exclusive record. | administration | holdings:_create_worktree |  |
| `adm.name.dot-git` | a path component named `.git`: compared; compared case-insensitively (in `workspace:relative`). | administration | _repository:repo_key, collect:_walk, collect:inventory.visit, workspace:relative |  |

#### Stewart's storage in the common directory

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `adm.common.stewart` | `<common>/stewart`: checked (in `_repository:private_storage`, `close:_close`); created; created (mode 0700) (in `_repository:private_storage`, `close:_close`); listed under `denyRead` (in `auditor_scope:claude_settings`); named; named in a refusal (in `_repository:private_storage`). | administration | _repository:custody_roots, _repository:private_storage, auditor_scope:claude_settings, audits:_audit_directory, cli:_manager_grant, close:_close, holdings:_materialize, prepare:_prepare, request_keys:keyed, status:_manager_storage |  |
| `adm.common.stewart.audits` | `<common>/stewart/audits/…` (10 paths): created (in `audits:_audit_directory`); listed (in `audits:draft_records`); named; read (in `audits:draft_records`). | administration | audits:_audit_directory, audits:_audit_keys, audits:draft_records, audits:records_location, holdings:Index.__init__ |  |
| `adm.common.stewart.closed` | `<common>/stewart/closed/…` (6 paths): checked; created (mode 0700) (in `close:_close`); listed; listed under `retained` (in `close:closing_entries`); named; named in a refusal (in `close:_close`); read (in `close:_close`); written as an exclusive record (in `close:_close`). | administration | audits:_audit_keys, close:_close, close:closed_location, close:closing_entries, status:status_list |  |
| `adm.common.stewart.entry` | `<common>/stewart/<>/…`: checked; created (mode 0700); named in a refusal. | administration | close:_close |  |
| `adm.common.stewart.requests` | `<common>/stewart/requests/…` (7 paths): checked; created (in `request_keys:keyed`); created (mode 0700) (in `request_keys:keyed`); listed (in `request_keys:request_summaries`); named; named in a refusal (in `request_keys:keyed`); read (in `request_keys:request_summaries`); written as an exclusive record (in `request_keys:keyed`). | administration | cli:_revalidate, request_keys:inspect, request_keys:keyed, request_keys:location, request_keys:request_summaries |  |
| `adm.common.stewart.resources` | `<common>/stewart/resources/…` (8 paths): checked (in `holdings:load`); listed (in `holdings:load`, `holdings:rids`); named; read (in `holdings:load`). | administration | holdings:_allocate, holdings:context_keys, holdings:load, holdings:location, holdings:rids |  |
| `adm.common.stewart.sessions` | `<common>/stewart/sessions/…` (18 paths): checked; compared; created (in `prepare:_prepare`); created (mode 0700) (in `prepare:_prepare`); listed; named; named in a refusal; read; written as an exclusive record (in `prepare:_prepare`). | administration | _repository:session_location, _repository:workspace_sessions, assignment:_initialize, audits:_audit_keys, audits:_register, audits:_session_view, audits:require_lifetime, close:_close, close:_read, close:close_plan, handoff:_export_checked, holdings:Index.__init__, holdings:_audit_context, holdings:_recorded_checkout_homes, holdings:record_output, prepare:_prepare, session:load_session, session:session_dir, status:status, status:status_list |  |
| `adm.common.stewart.worktree-roles` | `<common>/stewart/worktree-roles/…` (6 paths): compared (in `close:_read`); created (mode 0700) (in `_repository:_publish_role`); listed (in `_repository:_role_records`, `_repository:role_rows`); named; named in a refusal; written as an exclusive record (in `_repository:_publish_role`). | administration | _repository:_prospective_role, _repository:_publish_role, _repository:_registry, _repository:_role_records, _repository:registered_session, _repository:role_rows, close:_read, close:_removal_inventory |  |

### 5. Refusals that depend on what Git reports (82 rows)

The refusals Stewart raises because of something Git reported or something in Git's administration, with their reason identifiers. Refusals that depend only on your arguments, on Stewart's own records or on values passed between Stewart's functions, and problems that `status` reports without refusing, are not listed.

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `refuse.auditor_worktree._repository.maintainer` | “the selected root is inside auditor checkout storage”<br>“the selected worktree carries an auditor role marker”<br>“the selected worktree has an unfinished auditor registration”<br>“the selected worktree is a locked Stewart auditor checkout” | refusal | _repository:maintainer | `auditor_worktree` |
| `refuse.auditor_worktree._repository.observer` | “the selected root is inside auditor checkout storage”<br>“the selected worktree carries an auditor role marker”<br>“the selected worktree is a Stewart auditor checkout” | refusal | _repository:observer | `auditor_worktree` |
| `refuse.capture_uncovered.coverage.require_capture` | “{lead}: {'; '.join(described[:10])}{f'; and {len(described) - 1…}” | refusal | coverage:require_capture | `capture_uncovered` |
| `refuse.capture_unverified.coverage.require_capture` | “{lead}: the prompt commit cannot be compared: {exc}” | refusal | coverage:require_capture | `capture_unverified` |
| `refuse.checkout_changed.close._revalidate_plan` | “changes written after the close was planned: {', '.join(added[:10])}” | refusal | close:_revalidate_plan | `checkout_changed` |
| `refuse.checkout_commit.report_declaration.auditor_context` | “HEAD expected {launch_prompt_commit}, observed {head}.” | refusal | report_declaration:auditor_context | `checkout_commit` |
| `refuse.checkout_detached.report_declaration.auditor_context` | “HEAD expected 'detached', observed {symbolic.stdout.decode(…)}.” | refusal | report_declaration:auditor_context | `checkout_detached` |
| `refuse.checkout_git_file.report_declaration._own_administration` | “.git expected "this checkout's own gitdir file", observed {str(exc)}.” | refusal | report_declaration:_own_administration | `checkout_git_file` |
| `refuse.checkout_git_missing._repository.checkout_git_admin` | “the checkout's .git names {admin}, which does not exist; Git cannot discover the checkout through it” | refusal | _repository:checkout_git_admin | `checkout_git_missing` |
| `refuse.checkout_identity._repository.checkout_git_admin` | “the Git administration {admin} belongs to another session's lifetime; Git is not run through it”<br>“the Git administration {admin} does not name this checkout; Git is not run through it”<br>“the checkout's .git is not its gitdir file ({found}); Git is not run through it”<br>“the checkout's .git names {admin}, not one of its repository's worktree administrations; Git is not run throu…” | refusal | _repository:checkout_git_admin | `checkout_identity` |
| `refuse.checkout_identity.collect._collect` | “audit checkout identity changed; refuse to collect another repository” | refusal | collect:_collect | `checkout_identity` |
| `refuse.checkout_identity.experiment._release` | “the worktree HEAD is not the prompt commit; collect the unexpected commit first”<br>“the checkout cannot be verified: {exc}” | refusal | experiment:_release, experiment:_release (raised in experiment:_own_checkout_git) | `checkout_identity` |
| `refuse.checkout_root.report_declaration.auditor_context` | “repository root expected {str(expected_root)}, observed {str(actual)}.” | refusal | report_declaration:auditor_context | `checkout_root` |
| `refuse.checkout_root.report_declaration.check_checkout` | “repository root expected {str(…)}, observed {str(actual)}.” | refusal | report_declaration:check_checkout | `checkout_root` |
| `refuse.close_unidentified.close._preflight` | “no session record or registry row identifies this session” | refusal | close:_preflight | `close_unidentified` |
| `refuse.closing_record_invalid.close._read` | “closing record has a removal inventory outside its session's layout: {location}” | refusal | close:_read | `closing_record_invalid` |
| `refuse.commit_id._git.resolve_commit` | “not an exact commit ID: {value}” | refusal | _git:resolve_commit | `commit_id` |
| `refuse.context_changed.report_declaration._operate.verify` | “checkout context expected {expected}, observed 'changed inputs'.” | refusal | report_declaration:_operate.verify | `context_changed` |
| `refuse.context_changed.verify_inputs.verify_inputs` | “checkout/prompt changed during input verification” | refusal | verify_inputs:verify_inputs | `context_changed` |
| `refuse.context_unavailable.report_declaration.report_declaration` | “checkout/report expected 'readable prepared context', observed {str(exc)}.” | refusal | report_declaration:report_declaration | `context_unavailable` |
| `refuse.destination_exists.assignment._initialize` | “session or report destination already exists; choose a fresh audit ID” | refusal | assignment:_initialize | `destination_exists` |
| `refuse.destination_exists.holdings._create_branch` | “branch {branch} already exists; enroll it instead” | refusal | holdings:_create_branch | `destination_exists` |
| `refuse.destination_exists.holdings._create_worktree` | “branch {branch} already exists; borrow it with --existing-branch” | refusal | holdings:_create_worktree | `destination_exists` |
| `refuse.destination_exists.prepare._prepare` | “report destination already exists; choose a fresh audit ID” | refusal | prepare:_prepare | `destination_exists` |
| `refuse.destination_exists.report_declaration._operate` | “{str(report)} expected 'unoccupied destination', observed 'occupied'.” | refusal | report_declaration:_operate | `destination_exists` |
| `refuse.evidence_tampered.collect._collect` | “captured report changed before declaration validation” | refusal | collect:_collect | `evidence_tampered` |
| `refuse.git_failed._git.git` | “git {args[0]} failed: {os.fsdecode(result.stderr).…}” | refusal | _git:git | `git_failed` |
| `refuse.git_failed.coverage.prompt_identities` | “the prompt commit's blob {oid} cannot be read” | refusal | coverage:prompt_identities | `git_failed` |
| `refuse.git_ref_transaction._git.create_refs` | “cannot create direct refs: {exc}; {detail}” | refusal | _git:create_refs | `git_ref_transaction` |
| `refuse.handoff_identity.report_declaration.auditor_context` | “--{field.replace('_', '-')} expected {handoff[1][field]}, observed {value}.” | refusal | report_declaration:auditor_context | `handoff_identity` |
| `refuse.initialization_failed.assignment._initialize` | “could not replace prompt at {destination}: {exc}” | refusal | assignment:_initialize | `initialization_failed` |
| `refuse.input_collision.assignment._initialize` | “input manifest must be uncommitted supplemental material” | refusal | assignment:_initialize | `input_collision` |
| `refuse.input_collision.assignment.expected_inputs` | “supplemental input collides with a committed path: {item['path']}” | refusal | assignment:expected_inputs | `input_collision` |
| `refuse.input_drift.prepare._prepare` | “assigned inputs changed between target and prompt commits: {', '.join(drifted)}; choose a target that contain…” | refusal | prepare:_prepare | `input_drift` |
| `refuse.input_manifest.verify_inputs.verify_inputs` | “input manifest changed during verification” | refusal | verify_inputs:verify_inputs | `input_manifest` |
| `refuse.input_mismatch.assignment.input_receipts` | “missing or mismatched supplemental input: {row['path']} ({row['observed_kind']})” | refusal | assignment:input_receipts | `input_mismatch` |
| `refuse.input_mismatch.prepare._prepare` | “checked-out input differs from its receipt: {item['path']}” | refusal | prepare:_prepare | `input_mismatch` |
| `refuse.input_missing.assignment.expected_inputs` | “input_files must name committed regular files: {rel}” | refusal | assignment:expected_inputs | `input_missing` |
| `refuse.input_overlap.assignment._initialize` | “manifest destination collides with an input”<br>“manifest destination overlaps writable output” | refusal | assignment:_initialize | `input_overlap` |
| `refuse.input_overlap.assignment.expected_inputs` | “input paths and writable output paths must not overlap” | refusal | assignment:expected_inputs | `input_overlap` |
| `refuse.manager_grant_missing.cli.main` | “permission denied at {target or 'an unnamed path'}: {exc.strerror}” | refusal | cli:main | `manager_grant_missing` |
| `refuse.movement.collect._collect` | “checkout changed during collection; partial archive retained, collect again after stopping writers”<br>“report changed before archive capture; both versions retained, collect again” | refusal | collect:_collect | `movement` |
| `refuse.path_noncanonical.workspace.relative` | “noncanonical or administrative path: {value}” | refusal | workspace:relative | `path_noncanonical` |
| `refuse.prepare_failed.prepare._prepare` | “preparation failed during {stage}: {exc}” | refusal | prepare:_prepare | `prepare_failed` |
| `refuse.prompt_commit_shape.prepare._prepare` | “prompt commit must be a normal one-parent commit”<br>“prompt commit must change {ws.prompt} alone” | refusal | prepare:_prepare | `prompt_commit_shape` |
| `refuse.prompt_digest.report_declaration.auditor_context` | “committed prompt SHA-256 expected {prompt_sha256}, observed {digest}.” | refusal | report_declaration:auditor_context | `prompt_digest` |
| `refuse.prompt_digest.report_declaration.check_checkout` | “committed prompt SHA-256 expected {issued['prompt_sha256']}, observed {'unavailable' if prompt.ret…}.” | refusal | report_declaration:check_checkout | `prompt_digest` |
| `refuse.prompt_drift.prepare._prepare` | “working PROMPT.md differs from the chosen prompt commit” | refusal | prepare:_prepare | `prompt_drift` |
| `refuse.prompt_drift.report_declaration.auditor_context` | “{str(prompt_path)} expected {digest}, observed {info.get(…)}.” | refusal | report_declaration:auditor_context | `prompt_drift` |
| `refuse.reference_mismatch.prepare.prepare` | “the prompt commit assigns audit {ident}, not the selected audit {audit_id}” | refusal | prepare:prepare | `reference_mismatch` |
| `refuse.reference_stale.status.status` | “audit {ident} has no lifetime {lifetime}” | refusal | status:status | `reference_stale` |
| `refuse.release_invalidated.experiment._run` | “the worktree HEAD is not the prompt commit”<br>“the checkout cannot be verified: {exc}” | refusal | experiment:_run, experiment:_run (raised in experiment:_own_checkout_git) | `release_invalidated` |
| `refuse.report_unreadable.report_declaration._operate` | “{str(report)} expected 'readable regular file', observed {info}.” | refusal | report_declaration:_operate | `report_unreadable` |
| `refuse.repository_root._repository._separate_identity` | “cannot inspect the selected Git worktree: {exc}”<br>“repository must be a non-bare Git working tree”<br>“select the worktree root explicitly: {actual}; subdirectories are refused” | refusal | _repository:_separate_identity | `repository_root` |
| `refuse.request_missing.request_keys._inspect` | “no request is recorded under key {key}” | refusal | request_keys:_inspect | `request_missing` |
| `refuse.resource_blocked.holdings._close_resources` | “{message}” | refusal | holdings:_close_resources | `resource_blocked` |
| `refuse.resource_creation.holdings._create_branch` | “managed branch creation failed: {error['message']}” | refusal | holdings:_create_branch | `resource_creation` |
| `refuse.resource_creation.holdings._create_worktree` | “managed worktree creation failed: {error['message']}” | refusal | holdings:_create_worktree | `resource_creation` |
| `refuse.resource_identity.holdings._create_worktree` | “the new worktree's administration is not under the common directory” | refusal | holdings:_create_worktree | `resource_identity` |
| `refuse.resource_identity.holdings._remove_worktree` | “Git still registers {path} after its removal; the claim stays active” | refusal | holdings:_remove_worktree | `resource_identity` |
| `refuse.resource_missing.holdings._create_worktree` | “branch {existing_branch} does not exist” | refusal | holdings:_create_worktree | `resource_missing` |
| `refuse.resource_missing.holdings._enroll` | “Git registers no worktree at {target}”<br>“branch {branch} is absent or symbolic” | refusal | holdings:_enroll | `resource_missing` |
| `refuse.resource_not_managed.holdings._close_resources` | “{message}” | refusal | holdings:_close_resources | `resource_not_managed` |
| `refuse.resource_present.holdings._acknowledge` | “resource {rid} is not absent ({observation['state']}); an acknowledgment needs an observed absence” | refusal | holdings:_acknowledge | `resource_present` |
| `refuse.resource_retired.holdings._close_resources` | “{message}” | refusal | holdings:_close_resources | `resource_retired` |
| `refuse.resource_shared.holdings._close_resources` | “{message}” | refusal | holdings:_close_resources | `resource_shared` |
| `refuse.session_identity.session.load_session` | “session maintainer Git administration changed” | refusal | session:load_session | `session_identity` |
| `refuse.session_retention._repository.retain_commits` | “cannot create session retention refs: {exc}” | refusal | _repository:retain_commits | `session_retention` |
| `refuse.session_retention._repository.verify_retention` | “retained session commit is unavailable: {entry['commit']}”<br>“session retention must remain a direct ref: {entry['ref']}”<br>“session retention ref is absent or changed: {entry['ref']}” | refusal | _repository:verify_retention | `session_retention` |
| `refuse.session_unavailable.status.status` | “cannot validate disposition without its supported session” | refusal | status:status | `session_unavailable` |
| `refuse.submodules_present.prepare._prepare` | “the prompt commit holds submodules, which Stewart does not populate or audit: {', '.join(…)}” | refusal | prepare:_prepare | `submodules_present` |
| `refuse.target_ancestry.prepare._prepare` | “target_commit must be an ancestor of the prompt commit” | refusal | prepare:_prepare | `target_ancestry` |
| `refuse.target_drift.prepare._prepare` | “target bytes changed outside the workspace between target and prompt commits” | refusal | prepare:_prepare | `target_drift` |
| `refuse.uncollected_changes.close._preflight` | “the checkout could not be observed fully ({why}); changes no collection captured cannot be ruled out”<br>“the checkout holds changes no collection captured: {', '.join(…)}” | refusal | close:_preflight | `uncollected_changes` |
| `refuse.uncollected_changes.close._revalidate_plan` | “the checkout can no longer be observed fully; changes made after planning cannot be ruled out” | refusal | close:_revalidate_plan | `uncollected_changes` |
| `refuse.workspace_guidance.prepare._prepare` | “committed {name} must be a regular guidance/assignment file” | refusal | prepare:_prepare | `workspace_guidance` |
| `refuse.worktree_role_conflict._repository._prospective_role` | “auditor marker differs from its session UUID”<br>“existing auditor role differs; preserve it” | refusal | _repository:_prospective_role | `worktree_role_conflict` |
| `refuse.worktree_role_conflict._repository._publish_role` | “auditor marker changed before publication”<br>“role registration raced another writer; inspect the retained record” | refusal | _repository:_publish_role | `worktree_role_conflict` |
| `refuse.worktree_role_identity._repository._prospective_role` | “auditor must be a separate linked worktree of this repository”<br>“auditor registration requires its detached prompt checkout”<br>“session and observed worktree disagree” | refusal | _repository:_prospective_role | `worktree_role_identity` |
| `refuse.worktree_role_registry._repository._marker` | “worktree role marker cannot establish a role: {exc}” | refusal | _repository:_marker | `worktree_role_registry` |
| `refuse.worktree_role_registry._repository.maintainer` | “auditor marker and registry administration disagree” | refusal | _repository:maintainer | `worktree_role_registry` |
| `refuse.worktree_role_registry._repository.worktree_lock` | “worktree lock is unreadable” | refusal | _repository:worktree_lock | `worktree_role_registry` |
<!-- git-opinions:end -->

## Reading the table

Each class below has one of these statuses. They describe this version of
Stewart; a later version documents its own.

- **Relied on**: Stewart relies on it, and you may too.
- **Decided to change**: a later version is decided to behave differently.
  Do not build on this behavior.
- **May change**: this version behaves this way and a later one may not. Do
  not build on it.
- **Incidental**: how this version happens to work, not a promise.

Cases Stewart does not handle are listed above under "What Stewart does not
support".

### Configuration

- `cfg.c.core-hookspath`, `cfg.c.core-fsmonitor`,
  `cfg.env.set.git-optional-locks` and the `cfg.env.removed.*` rows:
  **relied on**. Your hooks never run under Stewart's own Git commands, no
  file-system monitor starts, and the four removed variables cannot point
  Stewart at another repository.
- `cfg.program`: **relied on**, for the qualified Git. Make sure the `git` on
  your `PATH` is the one you intend.
- `cfg.cwd`: **incidental**. Most commands run in the working tree they
  concern; some run in the Git directory or the current directory.
- `cfg.env.inherited`: **decided to change**. A later version is decided to
  use one consistent Git configuration and environment for preparing,
  checking and closing; today filters and replacement objects reach some of
  those steps and not others. Until then everything except the four removed
  variables reaches Stewart's Git.
- `cfg.process.*`: **incidental**. A Git command that runs longer than its
  limit, 120 seconds unless an operation sets another, fails with a generic
  error.

### Invocations

- **Reading the commission**: `inv.show`, `inv.ls-tree`, `inv.cat-file.e`,
  `inv.merge-base.is-ancestor`, `inv.rev-list.n-parents.1`,
  `inv.diff.name-only-no-renames-z`, `inv.rev-parse.verify.commit`. That
  Stewart reads the commission from commits is **relied on**; the particular
  commands are **incidental**; their following of replacement objects is
  **decided to change**.
- **Creating the auditor checkout**:
  `inv.worktree-add.detach-lock-reason.stewart-auditor-registration`,
  `inv.worktree-lock.reason.stewart-auditor-checkout`, `inv.worktree-unlock`:
  **may change**. Today the auditor works in a linked worktree of your
  repository; a later version may give it a plain directory instead.
- **Observing the auditor checkout**: the `via-git-dir-work-tree` rows from
  `collect` and `close`, and `inv.rev-parse.head.via-git-dir` from `status`:
  **may change**, with the linked worktree. In this version two properties are
  **relied on**: Stewart names the checkout's administration itself and never
  follows a `.git` file the auditor could have changed, and collection
  includes ignored files, so `.gitignore` hides nothing from it.
- **Branch queries**: `inv.branch.show-current` and
  `inv.branch.show-current.via-git-dir-work-tree`: **decided to change**. A
  later version asks Git for the symbolic `HEAD` instead. Both run in auditor
  checkouts, not in yours.
- **The auditor's helpers**: the `report_declaration` and `verify_inputs`
  rows: **may change**. In this version they need Git in the auditor's
  checkout.
- **Experiment execution**: the `experiment` release/run call sites:
  **decided to change**. The successor omits Stewart's dedicated program
  executor and those stages. Permitted auditor tool use and custody of its
  captured return remain; those reports do not become Stewart's own execution
  observations.
- **Checking coverage**: `inv.ls-tree.full-tree-r-z.via-no-replace-objects`
  and `inv.cat-file.batch.via-no-replace-objects`: **relied on**. Coverage
  reads committed bytes without replacements or filters and hashes them
  itself.
- **Refs**: `inv.update-ref.stdin`, `inv.update-ref.d-no-deref`,
  `inv.symbolic-ref.quiet`, and the `for-each-ref` rows naming
  `refs-stewart-sessions`: **may change**, with the refs themselves.
- **Your own checkout**: `inv.status.porcelain-v1-untracked-files-all-z`
  and `inv.rev-parse.head` from `session`: **incidental**. Stewart records your
  checkout's status and `HEAD` beside what it does.
- **Stewart's own installation**: `inv.ls-files.error-unmatch` and
  `inv.status.porcelain-v1-z` read Stewart's source checkout when you run it
  from source: **incidental**. They concern Stewart, not your material.
- **Worktrees, branches and directories you ask Stewart to create**: the
  `holdings` creation and disposal rows: **decided to change**. The successor's
  general manager-workspace creation and disposal service is deferred; it may
  be isolated and removed rather than advanced. In this version worktree and
  branch disposal refuses uncommitted, ignored or unmerged work as applicable.
  Plain temporary directories have a different rule: their contents are
  inventoried and frozen for removal, with live uses and recorded dependencies
  checked. Records of published evidence and required dependency protections
  remain responsibilities of the successor independently of this service.

### Refs

- `ref.refs-stewart-sessions`: **may change**. A later version may keep
  audit commits in its own storage instead. In this version a fetch that
  prunes into `refs/*` from a remote lacking these refs is documented by Git
  to delete them; Stewart then reports `session_retention` for that audit,
  and restoring the refs to the commits they named is the way back.
- `ref.refs-heads`, `ref.refs-worktree`, `ref.refs-bisect` and
  `ref.refs-stewart`: their use for manager-resource creation and disposal is
  **decided to change** with the deferred service. This does not decide every
  other use of these namespaces. In this version closing a managed branch
  deletes its recorded ref.
- `ref.refs`: **incidental**, a check that a name is a full ref name.

### Administration paths

- **Git's administration** (`adm.checkout.dot-git`,
  `adm.common.worktrees.*`, `adm.git-admin.*`, `adm.content.gitdir`):
  **may change**, with the linked worktree and the worktrees you ask Stewart
  to create. In this version Stewart writes its own marker files,
  `stewart-auditor.json` and `stewart-resource.json`, beside Git's; do not
  edit them. The manager-resource creation and disposal uses specifically are
  **decided to change**, with the deferred service; the auditor-workspace
  representation remains undecided.
- `adm.name.dot-git`: **relied on**. A path component named `.git`, in any
  letter case, is never accepted as an audit path.
- **Stewart's storage** (`adm.common.stewart.*`): what it asks of you is
  **relied on**: never edit these records, and back them up with `.git`. Six
  directories hold sessions, closing records, drafts and registrations,
  request keys, recorded resources and checkout registrations. Where Stewart
  keeps them **may change**.

### Refusals

A reason identifier is part of Stewart's JSON output and names one condition:
**relied on** for this version. A reason raised while preparing is reported
as `prepare_failed`, with the inner reason in the preparation's failure
record. A Git command that fails reports `git_failed` with Git's own message
and no further advice. Grouped by what they ask of you:

- **Repository shape**: `repository_root`, `path_noncanonical`. Run from the
  top of a non-bare working tree, with canonical paths.
- **Commission shape**: `prompt_commit_shape`, `target_ancestry`,
  `target_drift`, `input_drift`, `input_missing`, `input_collision`,
  `input_overlap`, `input_mismatch`, `prompt_drift`, `workspace_guidance`,
  `submodules_present`, `destination_exists`, `reference_mismatch`. Fix the
  commits or the assignment, or choose a fresh audit ID.
- **Checkout identity**: `checkout_*`, `auditor_worktree`,
  `worktree_role_*`, `handoff_identity`, `context_*`, `session_identity`:
  **may change**, with the linked worktree. Something about a checkout no
  longer matches what Stewart recorded, and Stewart will not run Git through
  a checkout it cannot identify. Undo the change if you know what it was.
- **Custody**: `capture_uncovered`, `capture_unverified`, `checkout_changed`,
  `uncollected_changes`, `movement`, `evidence_tampered`. Stewart will not
  claim custody it cannot verify. After writers stop, collect again; when
  collecting cannot help, as with a checkout transformation, abandon with an
  explicit discard. `session_retention` **may change** with the refs; restore
  the refs.
- **Resources you asked for**: `resource_*`: the general manager-resource
  creation and disposal operations are **decided to change**, with the service
  deferred in the successor. This version refuses disposal while doubt remains;
  existing records retain their meanings.
- **Git itself**: `git_failed`, `git_ref_transaction`, `commit_id`. The Git
  command failed, refs could not be created together, or a commit ID was not
  given in full.

A few refusal rows concern Stewart's own records rather than your repository,
such as `manager_grant_missing`, `request_missing`, `reference_stale` and
`closing_record_invalid`.
