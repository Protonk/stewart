# Preparing material in Git for Stewart

This document is for the people who keep material in a Git repository and
run Stewart over it. It says what Stewart expects of that repository, what
Stewart places in and beside it, how it runs Git, and what it does not
support or cannot help with. The table in the middle is generated from
Stewart's source, so each row is something the code actually does; the guide
after it says which rows you can rely on and what each asks of you.

## What Stewart expects

Stewart works in one non-bare Git repository with a working tree, and you
run it from the top of that working tree; a bare repository or a
subdirectory is refused (`repository_root`). It runs the `git` it finds on
your `PATH`. Stewart is qualified on macOS with Apple Git 2.54.0 and Python
3.14; other Git versions and other hosts are not qualified.

An audit is commissioned by commits. The workspace guidance and the
assignment are committed before preparation, and the commit that assigns the
audit changes the assignment alone, on top of the commit being audited
(`prompt_commit_shape`, `target_ancestry`). Files outside the workspace must
not differ between the audited commit and the assigning one (`target_drift`,
`input_drift`). Anything else the auditor needs is either committed or
supplied as a pinned input. Stewart reads all of this from Git objects, never
from your working files, so local edits after the assignment commit do not
reach the auditor.

## What Stewart places in and beside your repository

- **Private records** under `stewart/` inside your repository's Git
  directory. Nothing in your working tree changes, `git clean` and branch
  work cannot touch them, and neither cloning nor mirroring copies them. They
  are lost if the Git directory is deleted or re-cloned, or if a backup skips
  `.git`. Do not edit or remove them by hand; closing an audit is how they
  end.
- **Refs** under `refs/stewart/sessions/<id>/` that keep each audit's
  commits from being garbage-collected. An ordinary clone and a default push
  leave them behind, but `git clone --mirror` and `git push --mirror` copy
  them, with the commits they name, which include each audit's assignment
  commit.
- **An auditor checkout** for each audit: a locked, detached linked worktree
  outside your working tree, by default under
  `~/.local/state/stewart/checkouts`. `git worktree list` shows it. Do not
  remove, move, repair or force-prune it; closing the audit removes it.
- **Branches and worktrees of your own**, only when you ask Stewart to create
  them for an audit.

## How Stewart runs Git

Every Git command Stewart runs has hooks and the file-system monitor turned
off and takes no optional locks, and the variables that would redirect Git
to another repository, working tree, index or common directory are removed.
Everything else in your environment and configuration still applies. In
particular, filters you have configured run when the auditor checkout is
created.

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
- **Submodule contents.** Stewart does not populate submodules. Preparation
  refuses a commit holding them until you acknowledge it, and their paths are
  empty in the auditor checkout. Supply code the audit needs as committed
  copies or pinned inputs.
- **Replacement objects and grafts.** Stewart follows `git replace` when it
  records the inputs it pins, but ignores replacements when it checks what a
  collection covers, so the two can disagree in a repository that uses them.
  Legacy grafts (`info/grafts`), which Git still honors, are not disabled
  anywhere.
- **Shallow and partial clones.** Stewart is not qualified on them. History
  beyond a shallow boundary is simply absent. In a partial clone, Git fetches
  missing objects from the remote when they are read, so Stewart's reads of
  an audit's commits can reach the network. Commission audits from a complete
  clone.
- **Checkout transformations.** An attribute that changes bytes on checkout,
  such as `text eol=crlf`, makes the auditor's copy of a file differ from the
  committed bytes while Git reports the file unchanged. Stewart then never
  archives that file, and closing the audit as concluded is refused
  (`capture_uncovered`). If the attribute matches an assigned input,
  preparation fails instead (`input_mismatch`). Commission audits only from
  commits whose attributes transform no file.
- **Moving or copying the repository while an audit is open.** After the
  repository is renamed, `status`, `collect` and `close` refuse with
  `worktree_role_registry` for as long as any audit is open; moving it back
  restores them. A copy refuses the same way while the original keeps
  working. Close audits before moving or copying a repository.

## The Git opinions Stewart holds

<!-- git-opinions:begin -->
<!-- Generated by scripts/git_opinions.py from the Python source under src/stewart; edit the script, not this region, and regenerate with --write. -->

Each row below is something Stewart's code does with Git, found by parsing its source; none is written by hand. A row's ID is formed from its content, never from a line number, so it stays the same until the behavior it names changes. **Where** gives `module:function:line` for each place the opinion is written; **Reason** is the refusal identifier Stewart reports, when there is one.

### 1. Configuration common to every Git call (12 rows)

*Inclusion rule.* Read from `_git._invocation`, the one function that builds every Git argument vector and environment, and from the process launches that consume it (calls given `**_invocation(...)`). The returned `args` list supplies the program name and each `-c` setting; `dict(os.environ, NAME=value)` supplies inheritance and each variable set; `env.pop(NAME)` (directly or over a literal tuple) each variable removed; `cwd` the directory. A launch's keywords and its function's `timeout` default supply the process handling. IDs: `cfg.` plus the setting or variable name.

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `cfg.program` | Runs the program `git`, resolved through the inherited `PATH`; no absolute Git path is configured. | configuration | _git:_invocation:24 |  |
| `cfg.c.core-hookspath` | Every Git command gets `-c core.hooksPath=/dev/null`. Hooks never run: Git looks for them in `/dev/null`. | configuration | _git:_invocation:24 |  |
| `cfg.c.core-fsmonitor` | Every Git command gets `-c core.fsmonitor=false`. No file-system monitor runs. | configuration | _git:_invocation:24 |  |
| `cfg.cwd` | Git runs in the directory each caller passes (`cwd=repo`); without `--git-dir` it discovers the repository from there. | configuration | _git:_invocation:24 |  |
| `cfg.env.inherited` | Git inherits Stewart's whole environment, apart from the variables below. | configuration | _git:_invocation:24 |  |
| `cfg.env.set.git-optional-locks` | Sets `GIT_OPTIONAL_LOCKS=0`. Git takes no optional locks, so read-only commands do not rewrite the index. | configuration | _git:_invocation:24 |  |
| `cfg.env.removed.git-dir` | Removes `GIT_DIR` from the environment. An inherited value cannot redirect which repository Git addresses. | configuration | _git:_invocation:28 |  |
| `cfg.env.removed.git-work-tree` | Removes `GIT_WORK_TREE` from the environment. An inherited value cannot redirect which working tree Git addresses. | configuration | _git:_invocation:28 |  |
| `cfg.env.removed.git-index-file` | Removes `GIT_INDEX_FILE` from the environment. An inherited value cannot redirect which index Git reads or writes. | configuration | _git:_invocation:28 |  |
| `cfg.env.removed.git-common-dir` | Removes `GIT_COMMON_DIR` from the environment. An inherited value cannot redirect the common directory. | configuration | _git:_invocation:28 |  |
| `cfg.process.create-refs` | `create_refs` captures Git's output; standard input is `subprocess.PIPE`; stops Git after 120 seconds unless the caller passes `timeout`. | configuration | _git:create_refs:82 |  |
| `cfg.process.git` | `git` captures Git's output; Git's standard input is Stewart's own unless the caller passes `input`; stops Git after 120 seconds unless the caller passes `timeout`. | configuration | _git:git:55 |  |

### 2. Git invocations (57 rows)

*Inclusion rule.* Every call that reaches `_git._invocation`. A *wrapper* is any function that passes one of its own parameters, starred, as an argument after the repository to such a call (found by repeating the search until nothing changes); calls to a wrapper are followed into it with their arguments substituted, so `git_text`, `holdings._git_common` and nested helpers such as `collect.checkout_state.ask` contribute their callers' commands. A function whose Git call takes its parameters only as values (such as `status._git_head` or `_git.resolve_commit`) is not a wrapper: the row is where that call is written, and for helpers in `_git` the row also counts their callers. An *option builder* is a function whose every return is a tuple of options starting with `-` (such as `_repository.checkout_git`); its result is shown as the options it builds. Local variables, list `+=`, conditional expressions and loops over literal tuples are followed within a function. One row per distinct global options, command, flag set and operand shape; `<expr>` is a value computed at run time and `*expr` an unknown run of arguments. Reason `git_failed` means a nonzero exit refuses; otherwise the caller reads the exit status. IDs: `inv.` + command + sorted flags (dashes dropped) + the literal words of operands (first three per operand) + `via-` and the global options, each part present only when nonempty.

#### `git branch`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.branch.show-current` | Reads the checked-out branch; the branch name, empty when detached.<br>`git branch --show-current` | invocation | _repository:_prospective_role:566 | `git_failed` |
| `inv.branch.show-current.via-git-dir-work-tree` | Reads the checked-out branch; addresses a verified administration directly, never through `.git`; names the checkout explicitly; the branch name, empty when detached.<br>`git --git-dir=<git_admin> --work-tree=<worktree> branch --show-current` | invocation | collect:checkout_state:184 via collect:checkout_state.ask_text:137 | `git_failed` |

#### `git cat-file`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.cat-file.batch.via-no-replace-objects` | Reads objects from the object database; replacement objects ignored; batch reads on standard input; input on standard input.<br>`git --no-replace-objects cat-file --batch` | invocation | coverage:prompt_identities:60 | `git_failed` |
| `inv.cat-file.e` | Reads objects from the object database; existence only.<br>`git cat-file -e <prompt_commit>:<meta['report_path']>`<br>`git cat-file -e <revision>:<item['path']>`<br>`git cat-file -e <target>:<input_manifest>`<br>… 1 more form | invocation | assignment:_initialize:386 via assignment:expected_inputs:169, assignment:input_receipts:206 via assignment:expected_inputs:169, assignment:_initialize:391, prepare:_prepare:167 |  |
| `inv.cat-file.e.via-git-dir-work-tree` | Reads objects from the object database; addresses a verified administration directly, never through `.git`; names the checkout explicitly; existence only.<br>`git --git-dir=<git_admin> --work-tree=<worktree> cat-file -e <issued['launch_prompt_commit']>:<rel>`<br>`git --git-dir=<git_admin> --work-tree=<worktree> cat-file -e <meta['target_commit']>:<item['path']>` | invocation | report_declaration:check_checkout:423, verify_inputs:verify_inputs:47 via assignment:expected_inputs:169 |  |

#### `git diff`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.diff.binary-cached-full-index-no-ext-diff-no-renames-no-textconv.via-git-dir-work-tree` | Compares commits, the index and the working tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; against the index; no external diff driver; no textconv filter; no rename detection; binary patches; full object IDs.<br>`git --git-dir=<git_admin> --work-tree=<worktree> diff --cached --no-ext-diff --no-textconv --no-renames --binary --full-index <prompt_commit>` | invocation | collect:checkout_state:142 via collect:checkout_state.ask:134 | `git_failed` |
| `inv.diff.binary-full-index-no-ext-diff-no-renames-no-textconv.via-git-dir-work-tree` | Compares commits, the index and the working tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; no external diff driver; no textconv filter; no rename detection; binary patches; full object IDs.<br>`git --git-dir=<git_admin> --work-tree=<worktree> diff --no-ext-diff --no-textconv --no-renames --binary --full-index <prompt_commit>` | invocation | collect:checkout_state:141 via collect:checkout_state.ask:134 | `git_failed` |
| `inv.diff.cached-name-only-no-renames-z.via-git-dir-work-tree` | Compares commits, the index and the working tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; against the index; names only; no rename detection; NUL-delimited.<br>`git --git-dir=<git_admin> --work-tree=<worktree> diff --cached --name-only --no-renames -z <issued['launch_prompt_commit']>`<br>`git --git-dir=<git_admin> --work-tree=<worktree> diff --cached --name-only --no-renames -z <prompt_commit>` | invocation | collect:checkout_state:152 via collect:checkout_state.ask:134, report_declaration:check_checkout:425 | `git_failed` |
| `inv.diff.name-only-no-renames-z` | Compares commits, the index and the working tree; names only; no rename detection; NUL-delimited.<br>`git diff --name-only --no-renames -z <parents[1]> <prompt_commit>`<br>`git diff --name-only --no-renames -z <target> <prompt_commit>` | invocation | prepare:_prepare:123, prepare:_prepare:138 | `git_failed` |
| `inv.diff.name-only-no-renames-z.via-git-dir-work-tree` | Compares commits, the index and the working tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; names only; no rename detection; NUL-delimited.<br>`git --git-dir=<git_admin> --work-tree=<worktree> diff --name-only --no-renames -z <prompt_commit>` | invocation | collect:checkout_state:152 via collect:checkout_state.ask:134 | `git_failed` |

#### `git for-each-ref`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.for-each-ref.contains-format-refname` | Lists refs; refs containing a commit; named fields only.<br>`git for-each-ref --contains <commit> --format=%(refname)` | invocation | holdings:_reachable_elsewhere:949 |  |
| `inv.for-each-ref.format-objectname-symref` | Lists refs; named fields only.<br>`git for-each-ref --format=%(objectname)%00%(symref) <ref>` | invocation | holdings:_ref_tip:333 |  |
| `inv.for-each-ref.format-refname` | Lists refs; named fields only.<br>`git for-each-ref --format=%(refname) <ref>` | invocation | close:_still_there:711 |  |
| `inv.for-each-ref.format-refname-objectname-symref.refs-stewart-sessions` | Lists refs; named fields only.<br>`git for-each-ref --format=%(refname)%00%(objectname)%00%(symref) refs/stewart/sessions/<uuid>/` | invocation | close:_session_refs:80 |  |
| `inv.for-each-ref.format-refname.refs-stewart-sessions` | Lists refs; named fields only.<br>`git for-each-ref --format=%(refname) refs/stewart/sessions/<record['session_uuid']>/` | invocation | status:status:456 |  |
| `inv.for-each-ref.format-refname.refs-worktree-refs-bisect` | Lists refs; named fields only.<br>`git for-each-ref --format=%(refname) refs/worktree refs/bisect` | invocation | holdings:_worktree_findings:990 |  |

#### `git ls-files`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.ls-files.error-unmatch` | Lists paths Git knows in the working tree; every path must be tracked.<br>`git ls-files --error-unmatch -- *sorted(payloads)` | invocation | session:package_identity:83 |  |
| `inv.ls-files.others-z.via-git-dir-work-tree` | Lists paths Git knows in the working tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; untracked paths; NUL-delimited.<br>`git --git-dir=<git_admin> --work-tree=<worktree> ls-files --others -z` | invocation | collect:checkout_state:152 via collect:checkout_state.ask:134 | `git_failed` |

#### `git ls-tree`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.ls-tree` | Lists a committed tree.<br>`git ls-tree <prompt_commit> -- <name>`<br>`git ls-tree <revision> -- <rel>`<br>`git ls-tree <target> -- <rel>` | invocation | assignment:_initialize:386 via assignment:expected_inputs:163, assignment:input_receipts:206 via assignment:expected_inputs:163, prepare:_prepare:159 | `git_failed` |
| `inv.ls-tree.d-name-only-r-z.via-git-dir-work-tree` | Lists a committed tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; recursively; directories; names only; NUL-delimited.<br>`git --git-dir=<git_admin> --work-tree=<worktree> ls-tree -r -d --name-only -z <prompt>` | invocation | close:_observe_checkout:215 | `git_failed` |
| `inv.ls-tree.full-tree-r-z` | Lists a committed tree; recursively; NUL-delimited; the whole tree.<br>`git ls-tree -r -z --full-tree <commit>` | invocation | _git:gitlinks:49 via _git:tree_entries:39, used through `gitlinks` by assignment (1), prepare (1) | `git_failed` |
| `inv.ls-tree.full-tree-r-z.via-git-dir-work-tree` | Lists a committed tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly; recursively; NUL-delimited; the whole tree.<br>`git --git-dir=<git_admin> --work-tree=<worktree> ls-tree -r -z --full-tree <prompt_commit>` | invocation | collect:checkout_state:156 via _git:tree_entries:39 | `git_failed` |
| `inv.ls-tree.full-tree-r-z.via-no-replace-objects` | Lists a committed tree; replacement objects ignored; recursively; NUL-delimited; the whole tree.<br>`git --no-replace-objects ls-tree -r -z --full-tree <commit>` | invocation | coverage:prompt_identities:53 via _git:tree_entries:39 | `git_failed` |
| `inv.ls-tree.via-git-dir-work-tree` | Lists a committed tree; addresses a verified administration directly, never through `.git`; names the checkout explicitly.<br>`git --git-dir=<git_admin> --work-tree=<worktree> ls-tree <meta['target_commit']> -- <rel>` | invocation | verify_inputs:verify_inputs:47 via assignment:expected_inputs:163 | `git_failed` |

#### `git merge-base`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.merge-base.is-ancestor` | Tests commit ancestry; ancestry only.<br>`git merge-base --is-ancestor <target> <prompt_commit>` | invocation | prepare:_prepare:133 |  |

#### `git rev-list`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.rev-list.n-parents.1` | Reads a commit's parents; with parent IDs; a limited count.<br>`git rev-list --parents -n 1 <prompt_commit>` | invocation | prepare:_prepare:120 | `git_failed` |

#### `git rev-parse`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.rev-parse.absolute-git-dir` | Resolves a name or a repository location; the worktree's administration directory.<br>`git rev-parse --absolute-git-dir` | invocation | _repository:_separate_identity:243, holdings:_create_worktree:726, holdings:_enroll:898 | `git_failed` |
| `inv.rev-parse.absolute-git-dir-git-common-dir-is-bare-repository-path-format-absolute-show-toplevel` | Resolves a name or a repository location; whether the repository is bare; the working tree's top level; the worktree's administration directory; absolute path; the common directory.<br>`git rev-parse --is-bare-repository --show-toplevel --absolute-git-dir --path-format=absolute --git-common-dir` | invocation | _repository:checkout_identity:219 |  |
| `inv.rev-parse.git-common-dir-path-format-absolute` | Resolves a name or a repository location; absolute path; the common directory.<br>`git rev-parse --path-format=absolute --git-common-dir` | invocation | _repository:_separate_identity:244, report_declaration:_own_administration:258 | `git_failed` |
| `inv.rev-parse.git-common-dir-path-format-absolute.via-git-dir-work-tree` | Resolves a name or a repository location; addresses a verified administration directly, never through `.git`; names the checkout explicitly; absolute path; the common directory.<br>`git --git-dir=<git_admin> --work-tree=<worktree> rev-parse --path-format=absolute --git-common-dir` | invocation | collect:_collect:510 | `git_failed` |
| `inv.rev-parse.head` | Resolves a name or a repository location.<br>`git rev-parse HEAD` | invocation | _repository:_prospective_role:567, holdings:_create_worktree:731, holdings:_worktree_head:1318, session:package_identity:86, session:maintainer_state:307 | `git_failed` at some sites; others read the exit status |
| `inv.rev-parse.head.via-git-dir` | Resolves a name or a repository location; addresses a verified administration directly, never through `.git`.<br>`git --git-dir=<git_admin> rev-parse HEAD` | invocation | status:_git_head:63 |  |
| `inv.rev-parse.head.via-git-dir-work-tree` | Resolves a name or a repository location; addresses a verified administration directly, never through `.git`; names the checkout explicitly.<br>`git --git-dir=<git_admin> --work-tree=<worktree> rev-parse HEAD` | invocation | collect:checkout_state:183 via collect:checkout_state.ask_text:137, experiment:_release:260, experiment:_run:459, report_declaration:auditor_context:210 | `git_failed` at some sites; others read the exit status |
| `inv.rev-parse.is-bare-repository` | Resolves a name or a repository location; whether the repository is bare.<br>`git rev-parse --is-bare-repository` | invocation | _repository:_separate_identity:235 |  |
| `inv.rev-parse.show-toplevel` | Resolves a name or a repository location; the working tree's top level.<br>`git rev-parse --show-toplevel` | invocation | _repository:_separate_identity:238, report_declaration:auditor_context:192, report_declaration:check_checkout:374, report_declaration:main:627, verify_inputs:main:92 | `git_failed` |
| `inv.rev-parse.show-toplevel.via-git-dir-work-tree` | Resolves a name or a repository location; addresses a verified administration directly, never through `.git`; names the checkout explicitly; the working tree's top level.<br>`git --git-dir=<git_admin> --work-tree=<worktree> rev-parse --show-toplevel` | invocation | collect:_collect:511 | `git_failed` |
| `inv.rev-parse.verify` | Resolves a name or a repository location; the name must resolve.<br>`git rev-parse --verify <entry['ref']>` | invocation | _repository:verify_retention:660 |  |
| `inv.rev-parse.verify.commit` | Resolves a name or a repository location; the name must resolve.<br>`git rev-parse --verify <value>^{commit}` | invocation | _git:resolve_commit:134, used through `resolve_commit` by _repository (2), assignment (4), holdings (2), prepare (4) | `git_failed` |
| `inv.rev-parse.verify.head` | Resolves a name or a repository location; the name must resolve.<br>`git rev-parse --verify HEAD` | invocation | audits:_register:221 |  |

#### `git show`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.show` | Reads committed file bytes.<br>`git show <prompt_commit>:<ws.prompt>`<br>`git show <revision>:<rel>`<br>`git show <target>:<rel>` | invocation | assignment:_initialize:386 via assignment:expected_inputs:166, assignment:input_receipts:206 via assignment:expected_inputs:166, prepare:prepare:54, prepare:_prepare:126 | `git_failed` |
| `inv.show.via-git-dir-work-tree` | Reads committed file bytes; addresses a verified administration directly, never through `.git`; names the checkout explicitly.<br>`git --git-dir=<git_admin> --work-tree=<worktree> show <issued['launch_prompt_commit']>:<ws.prompt>`<br>`git --git-dir=<git_admin> --work-tree=<worktree> show <launch_prompt_commit>:<ws.prompt>`<br>`git --git-dir=<git_admin> --work-tree=<worktree> show <meta['target_commit']>:<rel>` | invocation | report_declaration:auditor_context:214, report_declaration:check_checkout:396, verify_inputs:verify_inputs:36, verify_inputs:verify_inputs:47 via assignment:expected_inputs:166 | `git_failed` at some sites; others read the exit status |

#### `git status`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.status.ignored-porcelain-v1-untracked-files-all-z` | Reports working-tree and index status; porcelain v1 format; NUL-delimited; every untracked file; ignored files included.<br>`git status --porcelain=v1 -z --untracked-files=all --ignored` | invocation | holdings:_worktree_findings:974 |  |
| `inv.status.porcelain-v1-untracked-files-all-z` | Reports working-tree and index status; porcelain v1 format; NUL-delimited; every untracked file.<br>`git status --porcelain=v1 -z --untracked-files=all` | invocation | session:maintainer_state:309 | `git_failed` |
| `inv.status.porcelain-v1-untracked-files-all-z.via-git-dir-work-tree` | Reports working-tree and index status; addresses a verified administration directly, never through `.git`; names the checkout explicitly; porcelain v1 format; NUL-delimited; every untracked file.<br>`git --git-dir=<git_admin> --work-tree=<worktree> status --porcelain=v1 -z --untracked-files=all` | invocation | collect:checkout_state:143 via collect:checkout_state.ask:134 | `git_failed` |
| `inv.status.porcelain-v1-z` | Reports working-tree and index status; porcelain v1 format; NUL-delimited.<br>`git status --porcelain=v1 -z -- <package>` | invocation | session:package_identity:89 |  |

#### `git symbolic-ref`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.symbolic-ref.q.head.via-git-dir-work-tree` | Tests whether a ref is symbolic; addresses a verified administration directly, never through `.git`; names the checkout explicitly; quiet.<br>`git --git-dir=<git_admin> --work-tree=<worktree> symbolic-ref -q HEAD` | invocation | report_declaration:auditor_context:206 |  |
| `inv.symbolic-ref.quiet` | Tests whether a ref is symbolic; quiet.<br>`git symbolic-ref --quiet <entry['ref']>`<br>`git symbolic-ref --quiet <ref>` | invocation | _git:create_refs:101, _repository:verify_retention:656, used through `create_refs` by _repository (1), holdings (1) |  |

#### `git update-ref`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.update-ref.d-no-deref` | Writes or deletes refs; never through a symbolic ref; deletes, checking the old value when one is given.<br>`git update-ref --no-deref -d <entry['ref']> <entry['commit']>`<br>`git update-ref --no-deref -d <identity['ref']> <frozen['tip']>` | invocation | close:_remove.remove_ref:521, holdings:retire_claim:1648 | `git_failed` |
| `inv.update-ref.stdin` | Writes or deletes refs; one transaction on standard input.<br>`git update-ref --stdin` | invocation | _git:create_refs:83, used through `create_refs` by _repository (1), holdings (1) |  |

#### `git worktree add`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.worktree-add.b-lock-reason.stewart-managed-worktree` | Creates a linked worktree; locked from creation; with a lock reason; on a new branch.<br>`git worktree add --lock --reason "stewart managed worktree <rid>: retire it with stewart close --resource" -b <branch> <target> <commit>` | invocation | holdings:_create_worktree:725 | `git_failed` |
| `inv.worktree-add.detach-lock-reason.stewart-auditor-registration` | Creates a linked worktree; detached HEAD; locked from creation; with a lock reason.<br>`git worktree add --detach --lock --reason "stewart auditor registration <session_identity>" <worktree> <prompt_commit>` | invocation | prepare:_prepare:262 | `git_failed` |
| `inv.worktree-add.detach-lock-reason.stewart-managed-worktree` | Creates a linked worktree; locked from creation; with a lock reason; detached HEAD.<br>`git worktree add --lock --reason "stewart managed worktree <rid>: retire it with stewart close --resource" --detach <target> <commit>` | invocation | holdings:_create_worktree:725 | `git_failed` |
| `inv.worktree-add.lock-reason.stewart-managed-worktree` | Creates a linked worktree; locked from creation; with a lock reason.<br>`git worktree add --lock --reason "stewart managed worktree <rid>: retire it with stewart close --resource" <target> <existing_branch>` | invocation | holdings:_create_worktree:725 | `git_failed` |

#### `git worktree list`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.worktree-list.porcelain` | Lists the worktrees Git registers; porcelain format.<br>`git worktree list --porcelain` | invocation | close:_registrations:361 | `git_failed` |
| `inv.worktree-list.porcelain-z` | Lists the worktrees Git registers; porcelain format; NUL-delimited.<br>`git worktree list --porcelain -z` | invocation | _repository:worktree_roots:152 | `git_failed` |

#### `git worktree lock`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.worktree-lock.reason.stewart-auditor-checkout` | Locks a linked worktree with a reason; with a lock reason.<br>`git worktree lock --reason "stewart auditor checkout <session_identity>: run stewart status before removing; close removes it with its session" <worktree>` | invocation | prepare:_prepare:270 | `git_failed` |

#### `git worktree unlock`

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `inv.worktree-unlock` | Unlocks a linked worktree.<br>`git worktree unlock <worktree>` | invocation | prepare:_prepare:269 | `git_failed` |

### 3. Refs Stewart names, creates or deletes (6 rows)

*Inclusion rule.* Every string literal or f-string whose text starts with `refs/`, outside docstrings, grouped by its namespace (the literal text up to the last `/` before the first run-time value). Each use is classified where the name is written, following a local variable to its uses: passed to a Git invocation row, passed to a function holding one, tested as a prefix, compared, named in a refusal, returned or recorded. IDs: `ref.` plus the namespace.

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `ref.refs` | `refs/`: prefix test. | ref | _git:create_refs:74 |  |
| `ref.refs-bisect` | `refs/bisect`: passed to Git: `inv.for-each-ref.format-refname.refs-worktree-refs-bisect`. | ref | holdings:_worktree_findings:990 |  |
| `ref.refs-heads` | `refs/heads/<branch>`, `refs/heads/<existing_branch>`: compared; passed to `_ref_tip`: `inv.for-each-ref.format-objectname-symref`; passed to `create_refs`: `inv.symbolic-ref.quiet`, `inv.update-ref.stdin`; recorded; returned by `_create_worktree`; returned by `_enroll`. | ref | holdings:_create_worktree:696, holdings:_create_worktree:701, holdings:_create_worktree:713, holdings:_create_worktree:716, holdings:_create_worktree:717, holdings:_create_worktree:740, holdings:_create_worktree:743, holdings:_create_branch:771, holdings:_enroll:880 |  |
| `ref.refs-stewart` | `refs/stewart/`: prefix test. | ref | holdings:_reachable_elsewhere:951 |  |
| `ref.refs-stewart-sessions` | `refs/stewart/sessions/<ident>/<name>`, `refs/stewart/sessions/<record['session_uuid']>/`, `refs/stewart/sessions/<row['session_uuid']>`, `refs/stewart/sessions/<uuid>/`: named in a refusal; passed to Git: `inv.for-each-ref.format-refname-objectname-symref.refs-stewart-sessions`; passed to Git: `inv.for-each-ref.format-refname.refs-stewart-sessions`; prefix test; returned by `retention_for`. | ref | _repository:registered_session:432, _repository:retention_for:634, close:_session_refs:81, close:_facts:149, close:_read:778, status:status:457 |  |
| `ref.refs-worktree` | `refs/worktree`: passed to Git: `inv.for-each-ref.format-refname.refs-worktree-refs-bisect`. | ref | holdings:_worktree_findings:990 |  |

Invocation rows whose command writes refs (`update-ref` and the other ref-writing commands, or `worktree add` with `-b`): `inv.update-ref.d-no-deref`, `inv.update-ref.stdin`, `inv.worktree-add.b-lock-reason.stewart-managed-worktree`.

### 4. Git administration paths (22 rows)

*Inclusion rule.* Path expressions rooted at the Git common directory (`<common>`: names or record keys `common`, `common_dir`, `git_common`), a worktree's administration (`<git-admin>`: `git_admin`, `admin`) or a checkout's `.git` (`<checkout>/.git`), joined with `/` or `contained(...)`, through local variables and through functions that return one; bare administration directories when they are listed, created, written or removed; the literal `.git` compared with a path component; and `gitdir: ` file content. `{a,b}` is a literal tuple iterated over. Uses are classified by the call or operation receiving the path. IDs: `adm.` plus the root and the literal segments.

#### Git's administration

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `adm.checkout.dot-git` | `<checkout>/.git`: checked; compared; named in a refusal; read. | administration | _repository:checkout_git_admin:472, _repository:checkout_git_admin:479, _repository:checkout_git_admin:483, _repository:checkout_git_admin:487, _repository:checkout_git_admin:492, holdings:_worktree_findings:968, holdings:_worktree_findings:970, holdings:_revalidate:1528 |  |
| `adm.common.worktrees` | `<common>/worktrees`: compared; listed; opened without following links. | administration | _repository:checkout_git_admin:484, close:_facts:143, close:_own_administrations:254, close:_read:775, holdings:_admin_for:319, holdings:_create_worktree:727 |  |
| `adm.common.worktrees.any.stewart-auditor-json` | `<common>/worktrees/*/stewart-auditor.json`: recorded. | administration | auditor_scope:claude_settings:86 |  |
| `adm.common.worktrees.entry` | `<common>/worktrees/<name>`: compared; named in a message; passed to `_admin_worktree`; passed to `_remove_administration`; passed to `admin_lifetime`; recorded; returned. | administration | close:_own_administrations:262, close:_own_administrations:263, holdings:_admin_for:327, holdings:observe:380, holdings:_worktree_findings:964, holdings:_remove_worktree:1605 |  |
| `adm.common.worktrees.entry.stewart-resource-json` | `<common>/worktrees/<name>/stewart-resource.json`: read. | administration | holdings:_admin_for:321 |  |
| `adm.content.gitdir` | a `.git` file holding one `gitdir: <path>` line: compared; passed to `_git_pointer`. | administration | _repository:checkout_git_admin:474, holdings:_worktree_findings:971 |  |
| `adm.git-admin` | `<git-admin>`: opened without following links; removed. | administration | close:_remove.remove_worktree:499, holdings:_remove_administration:1586, holdings:_remove_administration:1593, holdings:_remove_worktree:1610 |  |
| `adm.git-admin.entry` | `<git-admin>/<named_back>`: compared. | administration | _repository:checkout_git_admin:490 |  |
| `adm.git-admin.gitdir` | `<git-admin>/gitdir`: named in a refusal; read. | administration | _repository:checkout_git_admin:488, _repository:checkout_git_admin:492, close:_admin_worktree:245, holdings:_worktree_findings:967 |  |
| `adm.git-admin.in-progress` | `<git-admin>/{rebase-merge,rebase-apply,MERGE_HEAD,CHERRY_PICK_HEAD,REVERT_HEAD,BISECT_LOG}`: checked. | administration | holdings:_worktree_findings:993 |  |
| `adm.git-admin.locked` | `<git-admin>/locked`: read. | administration | _repository:worktree_lock:444, _repository:admin_lifetime:520 |  |
| `adm.git-admin.stewart-auditor-json` | `<git-admin>/stewart-auditor.json`: named in a refusal; read; written as an exclusive record. | administration | _repository:_marker:337, _repository:_marker:352, _repository:admin_lifetime:513, _repository:_publish_role:598 |  |
| `adm.git-admin.stewart-resource-json` | `<git-admin>/stewart-resource.json`: written as an exclusive record. | administration | holdings:_create_worktree:730 |  |
| `adm.name.dot-git` | a path component named `.git`: compared. | administration | _repository:repo_key:81, collect:inventory.visit:65, collect:inventory.visit:75, collect:_walk:214, collect:_walk:216, workspace:relative:40 |  |

#### Stewart's storage in the common directory

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `adm.common.stewart` | `<common>/stewart`: checked; created; created (mode 0700); named; named in a refusal. | administration | _repository:private_storage:45, _repository:private_storage:47, _repository:custody_roots:363, auditor_scope:claude_settings:85, audits:_audit_directory:124, cli:_manager_grant:806, close:_close:1060, holdings:_materialize:534, prepare:_prepare:240, request_keys:keyed:200, status:_manager_storage:985 |  |
| `adm.common.stewart.audits` | `<common>/stewart/audits/…` (10 paths): created; listed; named; read. | administration | audits:records_location:50, audits:_audit_directory:124, audits:draft_records:259, audits:draft_records:261, audits:draft_records:262, audits:draft_records:266, audits:draft_records:278, audits:draft_records:288, audits:draft_records:289, audits:_audit_keys:393, holdings:Index.__init__:459, holdings:Index.__init__:460 |  |
| `adm.common.stewart.closed` | `<common>/stewart/closed/…` (6 paths): checked; created (mode 0700); listed; named; named in a refusal; read; written as an exclusive record. | administration | audits:_audit_keys:392, close:closed_location:58, close:closing_entries:607, close:closing_entries:611, close:closing_entries:613, close:_close:1059, close:_close:1072, close:_close:1079, close:_close:1083, close:_close:1084, close:_close:1086, status:status_list:1104 |  |
| `adm.common.stewart.entry` | `<common>/stewart/<>/…`: checked; created (mode 0700); named in a refusal. | administration | close:_close:1062, close:_close:1065, close:_close:1068 |  |
| `adm.common.stewart.requests` | `<common>/stewart/requests/…` (7 paths): checked; created; created (mode 0700); listed; named; named in a refusal; read; written as an exclusive record. | administration | cli:_revalidate:605, request_keys:location:100, request_keys:keyed:199, request_keys:keyed:202, request_keys:keyed:225, request_keys:keyed:230, request_keys:keyed:232, request_keys:keyed:247, request_keys:keyed:252, request_keys:keyed:261, request_keys:keyed:270, request_keys:keyed:274, request_keys:keyed:278, request_keys:inspect:331, request_keys:inspect:332, request_keys:request_summaries:414, request_keys:request_summaries:417, request_keys:request_summaries:425, request_keys:request_summaries:428, request_keys:request_summaries:431, request_keys:request_summaries:434, request_keys:request_summaries:437 |  |
| `adm.common.stewart.resources` | `<common>/stewart/resources/…` (8 paths): checked; listed; named; read. | administration | holdings:location:64, holdings:load:131, holdings:load:132, holdings:load:138, holdings:load:140, holdings:load:153, holdings:load:168, holdings:load:172, holdings:load:181, holdings:load:183, holdings:rids:201, holdings:context_keys:223, holdings:_allocate:529 |  |
| `adm.common.stewart.sessions` | `<common>/stewart/sessions/…` (18 paths): checked; compared; created; created (mode 0700); listed; named; named in a refusal; read; written as an exclusive record. | administration | _repository:session_location:67, _repository:workspace_sessions:72, assignment:_initialize:374, audits:_register:216, audits:_register:219, audits:_session_view:357, audits:_session_view:360, audits:_session_view:362, audits:_session_view:379, audits:_session_view:381, audits:_session_view:382, audits:_session_view:383, audits:_audit_keys:392, audits:_audit_keys:407, audits:require_lifetime:726, audits:require_lifetime:731, audits:require_lifetime:742, close:_read:763, close:_close:1029, close:_close:1030, close:close_plan:1253, close:close_plan:1254, close:close_plan:1256, handoff:_export_checked:151, holdings:Index.__init__:432, holdings:Index.__init__:443, holdings:Index.__init__:444, holdings:Index.__init__:446, holdings:Index.__init__:453, holdings:_audit_context:547, holdings:_audit_context:550, holdings:_recorded_checkout_homes:570, holdings:_recorded_checkout_homes:572, holdings:_recorded_checkout_homes:574, holdings:record_output:838, holdings:record_output:840, prepare:_prepare:182, prepare:_prepare:187, prepare:_prepare:195, prepare:_prepare:254, prepare:_prepare:256, prepare:_prepare:287, prepare:_prepare:292, prepare:_prepare:302, prepare:_prepare:321, prepare:_prepare:326, prepare:_prepare:343, prepare:_prepare:346, session:session_dir:163, session:load_session:192, session:load_session:200, session:load_session:209, session:load_session:214, session:load_session:218, session:load_session:221, session:load_session:226, status:status:340, status:status:392, status:status:404, status:status:431, status:status:434, status:status:467, status:status:523, status:status:530, status:status:537, status:status:539, status:status:562, status:status:565, status:status:578, status:status:604, status:status:606, status:status:653, status:status:658, status:status_list:1084, status:status_list:1085, status:status_list:1087, status:status_list:1108, status:status_list:1117 |  |
| `adm.common.stewart.worktree-roles` | `<common>/stewart/worktree-roles/…` (6 paths): compared; created (mode 0700); listed; named; named in a refusal; written as an exclusive record. | administration | _repository:_registry:257, _repository:_role_records:289, _repository:_role_records:300, _repository:role_rows:311, _repository:role_rows:320, _repository:role_rows:325, _repository:registered_session:436, _repository:_prospective_role:583, _repository:_publish_role:591, _repository:_publish_role:593, _repository:_publish_role:606, _repository:_publish_role:609, close:_removal_inventory:355, close:_read:773 |  |

### 5. Refusals about repository shape (79 rows)

*Inclusion rule.* `raise StewartError(..., reason=...)`, directly or through a function that returns a `StewartError`, when the raise is guarded by a condition or loop over a Git-derived value, or handles an exception from work holding one. Values are Git-derived when they come from a Git helper call, from a Git-administration expression in the same function (class 4, not Stewart's storage), or from a function whose return value derives from those, up to 2 levels deep; the common directory's path, paths into Stewart's storage and Stewart's own installation (`__file__`) are locations and carry nothing. A reason passed in as a parameter is taken from each caller that passes a literal. Messages are shortened, with run-time values in braces. IDs: `refuse.` + reason + module + function.

| ID | Opinion | Class | Where | Reason |
|---|---|---|---|---|
| `refuse.auditor_worktree._repository.maintainer` | “the selected root is inside auditor checkout storage”<br>“the selected worktree carries an auditor role marker”<br>“the selected worktree has an unfinished auditor registration”<br>“the selected worktree is a locked Stewart auditor checkout” | refusal | _repository:maintainer:377, _repository:maintainer:384, _repository:maintainer:392, _repository:maintainer:395 | `auditor_worktree` |
| `refuse.auditor_worktree._repository.observer` | “the selected root is inside auditor checkout storage”<br>“the selected worktree carries an auditor role marker”<br>“the selected worktree is a Stewart auditor checkout” | refusal | _repository:observer:410, _repository:observer:414, _repository:observer:418 | `auditor_worktree` |
| `refuse.capture_uncovered.coverage.require_capture` | “{lead}: {'; '.join(described[:10])}{f'; and {len(described) - 1…}” | refusal | coverage:require_capture:157 | `capture_uncovered` |
| `refuse.capture_unverified.coverage.require_capture` | “{lead}: the prompt commit cannot be compared: {exc}” | refusal | coverage:require_capture:152 | `capture_unverified` |
| `refuse.checkout_changed.close._revalidate_plan` | “changes written after the close was planned: {', '.join(added[:10])}” | refusal | close:_revalidate_plan:430 | `checkout_changed` |
| `refuse.checkout_commit.report_declaration.auditor_context` | “HEAD expected {launch_prompt_commit}, observed {head}.” | refusal | report_declaration:auditor_context:212 | `checkout_commit` |
| `refuse.checkout_detached.report_declaration.auditor_context` | “HEAD expected 'detached', observed {symbolic.stdout.decode(…)}.” | refusal | report_declaration:auditor_context:208 | `checkout_detached` |
| `refuse.checkout_git_file.report_declaration._own_administration` | “.git expected "this checkout's own gitdir file", observed {str(exc)}.” | refusal | report_declaration:_own_administration:263 | `checkout_git_file` |
| `refuse.checkout_git_missing._repository.checkout_git_admin` | “the checkout's .git names {admin}, which does not exist; Git cannot discover the checkout through it” | refusal | _repository:checkout_git_admin:482 | `checkout_git_missing` |
| `refuse.checkout_identity._repository.checkout_git_admin` | “the checkout's .git is not its gitdir file ({found}); Git is not run through it”<br>“the checkout's .git names {admin}, not one of its repository's worktree administrations; Git is not run throu…”<br>“the Git administration {admin} does not name this checkout; Git is not run through it”<br>“the Git administration {admin} belongs to another session's lifetime; Git is not run through it” | refusal | _repository:checkout_git_admin:478, _repository:checkout_git_admin:485, _repository:checkout_git_admin:491, _repository:checkout_git_admin:494 | `checkout_identity` |
| `refuse.checkout_identity.collect._collect` | “audit checkout identity changed; refuse to collect another repository” | refusal | collect:_collect:512 | `checkout_identity` |
| `refuse.checkout_identity.experiment._release` | “the checkout cannot be verified: {exc}”<br>“the worktree HEAD is not the prompt commit; collect the unexpected commit first” | refusal | experiment:_release:260 (raised in experiment:_own_checkout_git:225), experiment:_release:263 | `checkout_identity` |
| `refuse.checkout_root.report_declaration.auditor_context` | “repository root expected {str(expected_root)}, observed {str(actual)}.” | refusal | report_declaration:auditor_context:195 | `checkout_root` |
| `refuse.checkout_root.report_declaration.check_checkout` | “repository root expected {str(…)}, observed {str(actual)}.” | refusal | report_declaration:check_checkout:376 | `checkout_root` |
| `refuse.closing_record_invalid.close._read` | “closing record has a removal inventory outside its session's layout: {location}” | refusal | close:_read:781 | `closing_record_invalid` |
| `refuse.commit_id._git.resolve_commit` | “not an exact commit ID: {value}” | refusal | _git:resolve_commit:136 | `commit_id` |
| `refuse.context_changed.report_declaration._operate.verify` | “checkout context expected {expected}, observed 'changed inputs'.” | refusal | report_declaration:_operate.verify:540 | `context_changed` |
| `refuse.context_changed.verify_inputs.verify_inputs` | “checkout/prompt changed during input verification” | refusal | verify_inputs:verify_inputs:49 | `context_changed` |
| `refuse.context_unavailable.report_declaration.report_declaration` | “checkout/report expected 'readable prepared context', observed {str(exc)}.” | refusal | report_declaration:report_declaration:564 | `context_unavailable` |
| `refuse.destination_exists.assignment._initialize` | “session or report destination already exists; choose a fresh audit ID” | refusal | assignment:_initialize:379 | `destination_exists` |
| `refuse.destination_exists.holdings._create_branch` | “branch {branch} already exists; enroll it instead” | refusal | holdings:_create_branch:773 | `destination_exists` |
| `refuse.destination_exists.holdings._create_worktree` | “branch {branch} already exists; borrow it with --existing-branch” | refusal | holdings:_create_worktree:698 | `destination_exists` |
| `refuse.destination_exists.prepare._prepare` | “report destination already exists; choose a fresh audit ID” | refusal | prepare:_prepare:169 | `destination_exists` |
| `refuse.destination_exists.report_declaration._operate` | “{str(report)} expected 'unoccupied destination', observed 'occupied'.” | refusal | report_declaration:_operate:505 | `destination_exists` |
| `refuse.evidence_tampered.collect._collect` | “captured report changed before declaration validation” | refusal | collect:_collect:567 | `evidence_tampered` |
| `refuse.git_failed._git.git` | “git {args[0]} failed: {os.fsdecode(result.stderr).…}” | refusal | _git:git:59 | `git_failed` |
| `refuse.git_failed.coverage.prompt_identities` | “the prompt commit's blob {oid} cannot be read” | refusal | coverage:prompt_identities:67 | `git_failed` |
| `refuse.git_ref_transaction._git.create_refs` | “cannot create direct refs: {exc}; {detail}” | refusal | _git:create_refs:111 | `git_ref_transaction` |
| `refuse.handoff_identity.report_declaration.auditor_context` | “--{field.replace('_', '-')} expected {handoff[1][field]}, observed {value}.” | refusal | report_declaration:auditor_context:204 | `handoff_identity` |
| `refuse.initialization_failed.assignment._initialize` | “could not replace prompt at {destination}: {exc}” | refusal | assignment:_initialize:438 | `initialization_failed` |
| `refuse.input_collision.assignment._initialize` | “input manifest must be uncommitted supplemental material” | refusal | assignment:_initialize:392 | `input_collision` |
| `refuse.input_collision.assignment.expected_inputs` | “supplemental input collides with a committed path: {item['path']}” | refusal | assignment:expected_inputs:170 | `input_collision` |
| `refuse.input_drift.prepare._prepare` | “assigned inputs changed between target and prompt commits: {', '.join(drifted)}; choose a target that contain…” | refusal | prepare:_prepare:153 | `input_drift` |
| `refuse.input_manifest.verify_inputs.verify_inputs` | “input manifest changed during verification” | refusal | verify_inputs:verify_inputs:53 | `input_manifest` |
| `refuse.input_mismatch.assignment.input_receipts` | “missing or mismatched supplemental input: {row['path']} ({row['observed_kind']})” | refusal | assignment:input_receipts:209 | `input_mismatch` |
| `refuse.input_mismatch.prepare._prepare` | “checked-out input differs from its receipt: {item['path']}” | refusal | prepare:_prepare:276 | `input_mismatch` |
| `refuse.input_missing.assignment.expected_inputs` | “input_files must name committed regular files: {rel}” | refusal | assignment:expected_inputs:165 | `input_missing` |
| `refuse.input_overlap.assignment._initialize` | “manifest destination collides with an input”<br>“manifest destination overlaps writable output” | refusal | assignment:_initialize:387, assignment:_initialize:390 | `input_overlap` |
| `refuse.manager_grant_missing.cli.main` | “permission denied at {target or 'an unnamed path'}: {exc.strerror}” | refusal | cli:main:1435 | `manager_grant_missing` |
| `refuse.movement.collect._collect` | “checkout changed during collection; partial archive retained, collect again after stopping writers”<br>“report changed before archive capture; both versions retained, collect again” | refusal | collect:_collect:529, collect:_collect:539 | `movement` |
| `refuse.path_noncanonical.workspace.relative` | “noncanonical or administrative path: {value}” | refusal | workspace:relative:41 | `path_noncanonical` |
| `refuse.prepare_failed.prepare._prepare` | “preparation failed during {stage}: {exc}” | refusal | prepare:_prepare:300 | `prepare_failed` |
| `refuse.prompt_commit_shape.prepare._prepare` | “prompt commit must be a normal one-parent commit”<br>“prompt commit must change {ws.prompt} alone” | refusal | prepare:_prepare:122, prepare:_prepare:125 | `prompt_commit_shape` |
| `refuse.prompt_digest.report_declaration.auditor_context` | “committed prompt SHA-256 expected {prompt_sha256}, observed {digest}.” | refusal | report_declaration:auditor_context:217 | `prompt_digest` |
| `refuse.prompt_digest.report_declaration.check_checkout` | “committed prompt SHA-256 expected {issued['prompt_sha256']}, observed {'unavailable' if prompt.ret…}.” | refusal | report_declaration:check_checkout:398 | `prompt_digest` |
| `refuse.prompt_drift.prepare._prepare` | “working PROMPT.md differs from the chosen prompt commit” | refusal | prepare:_prepare:128 | `prompt_drift` |
| `refuse.prompt_drift.report_declaration.auditor_context` | “{str(prompt_path)} expected {digest}, observed {info.get(…)}.” | refusal | report_declaration:auditor_context:222 | `prompt_drift` |
| `refuse.reference_mismatch.prepare.prepare` | “the prompt commit assigns audit {ident}, not the selected audit {audit_id}” | refusal | prepare:prepare:62 | `reference_mismatch` |
| `refuse.reference_stale.status.status` | “audit {ident} has no lifetime {lifetime}” | refusal | status:status:343 | `reference_stale` |
| `refuse.release_invalidated.experiment._run` | “the checkout cannot be verified: {exc}”<br>“the worktree HEAD is not the prompt commit” | refusal | experiment:_run:459 (raised in experiment:_own_checkout_git:225), experiment:_run:462 | `release_invalidated` |
| `refuse.report_unreadable.report_declaration._operate` | “{str(report)} expected 'readable regular file', observed {info}.” | refusal | report_declaration:_operate:523 | `report_unreadable` |
| `refuse.repository_root._repository._separate_identity` | “repository must be a non-bare Git working tree”<br>“select the worktree root explicitly: {actual}; subdirectories are refused”<br>“cannot inspect the selected Git worktree: {exc}” | refusal | _repository:_separate_identity:237, _repository:_separate_identity:240, _repository:_separate_identity:247 | `repository_root` |
| `refuse.request_missing.request_keys._inspect` | “no request is recorded under key {key}” | refusal | request_keys:_inspect:354 | `request_missing` |
| `refuse.resource_blocked.holdings._close_resources` | “{message}” | refusal | holdings:_close_resources:1782 | `resource_blocked` |
| `refuse.resource_creation.holdings._create_branch` | “managed branch creation failed: {error['message']}” | refusal | holdings:_create_branch:786 | `resource_creation` |
| `refuse.resource_creation.holdings._create_worktree` | “managed worktree creation failed: {error['message']}” | refusal | holdings:_create_worktree:746 | `resource_creation` |
| `refuse.resource_identity.holdings._create_worktree` | “the new worktree's administration is not under the common directory” | refusal | holdings:_create_worktree:728 | `resource_identity` |
| `refuse.resource_missing.holdings._create_worktree` | “branch {existing_branch} does not exist” | refusal | holdings:_create_worktree:703 | `resource_missing` |
| `refuse.resource_missing.holdings._enroll` | “branch {branch} is absent or symbolic” | refusal | holdings:_enroll:883 | `resource_missing` |
| `refuse.resource_not_managed.holdings._close_resources` | “{message}” | refusal | holdings:_close_resources:1777 | `resource_not_managed` |
| `refuse.resource_present.holdings._acknowledge` | “resource {rid} is not absent ({observation['state']}); an acknowledgment needs an observed absence” | refusal | holdings:_acknowledge:1830 | `resource_present` |
| `refuse.resource_retired.holdings._close_resources` | “{message}” | refusal | holdings:_close_resources:1779 | `resource_retired` |
| `refuse.resource_shared.holdings._close_resources` | “{message}” | refusal | holdings:_close_resources:1781 | `resource_shared` |
| `refuse.session_identity.session.load_session` | “session maintainer Git administration changed” | refusal | session:load_session:233 | `session_identity` |
| `refuse.session_retention._repository.retain_commits` | “cannot create session retention refs: {exc}” | refusal | _repository:retain_commits:645 | `session_retention` |
| `refuse.session_retention._repository.verify_retention` | “session retention must remain a direct ref: {entry['ref']}”<br>“session retention ref is absent or changed: {entry['ref']}”<br>“retained session commit is unavailable: {entry['commit']}” | refusal | _repository:verify_retention:658, _repository:verify_retention:662, _repository:verify_retention:667 | `session_retention` |
| `refuse.session_unavailable.status.status` | “cannot validate disposition without its supported session” | refusal | status:status:641 | `session_unavailable` |
| `refuse.submodules_present.prepare._prepare` | “the prompt commit holds submodules, which Stewart does not populate or audit: {', '.join(…)}” | refusal | prepare:_prepare:105 | `submodules_present` |
| `refuse.target_ancestry.prepare._prepare` | “target_commit must be an ancestor of the prompt commit” | refusal | prepare:_prepare:134 | `target_ancestry` |
| `refuse.target_drift.prepare._prepare` | “target bytes changed outside the workspace between target and prompt commits” | refusal | prepare:_prepare:143 | `target_drift` |
| `refuse.uncollected_changes.close._preflight` | “the checkout could not be observed fully ({why}); changes no collection captured cannot be ruled out”<br>“the checkout holds changes no collection captured: {', '.join(…)}” | refusal | close:_preflight:977, close:_preflight:982 | `uncollected_changes` |
| `refuse.uncollected_changes.close._revalidate_plan` | “the checkout can no longer be observed fully; changes made after planning cannot be ruled out” | refusal | close:_revalidate_plan:424 | `uncollected_changes` |
| `refuse.workspace_guidance.prepare._prepare` | “committed {name} must be a regular guidance/assignment file” | refusal | prepare:_prepare:161 | `workspace_guidance` |
| `refuse.worktree_role_conflict._repository._prospective_role` | “auditor marker differs from its session UUID”<br>“existing auditor role differs; preserve it” | refusal | _repository:_prospective_role:573, _repository:_prospective_role:582 | `worktree_role_conflict` |
| `refuse.worktree_role_conflict._repository._publish_role` | “auditor marker changed before publication”<br>“role registration raced another writer; inspect the retained record” | refusal | _repository:_publish_role:600, _repository:_publish_role:608 | `worktree_role_conflict` |
| `refuse.worktree_role_identity._repository._prospective_role` | “auditor must be a separate linked worktree of this repository”<br>“session and observed worktree disagree”<br>“auditor registration requires its detached prompt checkout” | refusal | _repository:_prospective_role:556, _repository:_prospective_role:565, _repository:_prospective_role:568 | `worktree_role_identity` |
| `refuse.worktree_role_registry._repository._marker` | “worktree role marker cannot establish a role: {exc}” | refusal | _repository:_marker:351 | `worktree_role_registry` |
| `refuse.worktree_role_registry._repository.maintainer` | “auditor marker and registry administration disagree” | refusal | _repository:maintainer:383 | `worktree_role_registry` |
| `refuse.worktree_role_registry._repository.worktree_lock` | “worktree lock is unreadable” | refusal | _repository:worktree_lock:448 | `worktree_role_registry` |
<!-- git-opinions:end -->

## Reading the table

Each class below is marked **supported** (Stewart relies on it and you can
rely on it), **unsupported** (Stewart does not handle the case; avoid it) or
**undecided** (it is how Stewart behaves now, but whether Stewart will keep
this opinion has not been decided; do not build on it). Each entry also says
what the opinion asks of you.

### Configuration

- `cfg.c.core-hookspath`, `cfg.c.core-fsmonitor`,
  `cfg.env.set.git-optional-locks` and the four `cfg.env.removed.*` rows:
  **supported**. Your hooks never run under Stewart, no file-system monitor
  starts, and an inherited `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` or
  `GIT_COMMON_DIR` cannot point Stewart at another repository.
- `cfg.program` and `cfg.cwd`: **supported**, qualified for Apple Git 2.54.0
  on macOS. Make sure the `git` on your `PATH` is the one you intend.
- `cfg.env.inherited`: **undecided**. Every other variable and all of your
  Git configuration reach Stewart's Git, including other `GIT_*` variables,
  configured filters and attributes. Run Stewart without Git variables you
  have not chosen deliberately, and do not rely on filters or attributes
  behaving any particular way.
- `cfg.process.*`: **supported**. Each command is stopped after 120 seconds
  unless the operation sets another limit; a very large repository can hit
  that limit.

### Invocations

- **Reading the commission**: `inv.show`, `inv.ls-tree`, `inv.cat-file.e`,
  `inv.merge-base.is-ancestor`, `inv.rev-list.n-parents.1`,
  `inv.diff.name-only-no-renames-z` and `inv.rev-parse.*` without
  `via-git-dir`: **supported**. These read commits and objects, never your
  working files.
- **Creating the auditor checkout**: `inv.worktree-add.detach-lock-reason.stewart-auditor-registration`,
  `inv.worktree-lock.reason.stewart-auditor-checkout`, `inv.worktree-unlock`:
  **undecided**. Today the auditor works in a linked worktree of your
  repository; whether it stays one is not decided. Stewart reads the lock
  reasons back to identify its own checkouts, so do not change them.
- **Observing the auditor checkout**: rows ending `via-git-dir-work-tree` in
  `collect`, `close` and `status`: **supported**. Stewart names the checkout's
  administration explicitly and never follows a `.git` file the auditor
  could have changed. Collection includes ignored files, so `.gitignore`
  cannot hide anything from it.
- **The auditor's helpers**: `report_declaration` and `verify_inputs` rows:
  **supported** while the auditor works in a Git checkout. They need Git in
  that checkout.
- **Checking coverage**: rows ending `via-no-replace-objects`: **supported**.
  Coverage reads committed bytes without replacements or filters and hashes
  them itself.
- **Refs**: `inv.update-ref.*`, `inv.symbolic-ref.*`,
  `inv.for-each-ref.*.refs-stewart-sessions`: **supported** for as long as
  Stewart keeps refs in your repository (see Refs below).
- **Your own checkout**: `inv.status.porcelain-v1-untracked-files-all-z`,
  `inv.branch.show-current`, `inv.rev-parse.head` from `session`: **supported**.
  Stewart records your checkout's state beside what it does; it never changes
  it.
- **Stewart's own installation**: `inv.ls-files.error-unmatch` and
  `inv.status.porcelain-v1-z` read Stewart's source checkout when you run it
  from source. They concern Stewart, not your material.
- **Worktrees, branches and directories you ask Stewart to create**: rows in
  `holdings`: **undecided**. They work now; whether Stewart keeps creating and
  disposing of these for you is not decided. If you create them, expect
  Stewart to refuse their disposal while they hold uncommitted, ignored or
  unmerged work.

### Refs

- `ref.refs-stewart-sessions`: **undecided**. These refs keep audit commits
  alive in your repository. If you mirror the repository or bundle all its
  refs, the copy receives them and the commits they name; push with explicit
  refspecs instead of `--mirror`, or close audits first. A fetch that prunes
  into `refs/*` from a remote without them deletes them, after which Stewart
  refuses that audit with `session_retention`.
- `ref.refs-heads`: **supported**, only for branches you ask Stewart to create.
- `ref.refs-worktree`, `ref.refs-bisect`, `ref.refs` and `ref.refs-stewart`:
  **supported**. These are read only, to check a worktree's state before
  disposal and to recognize Stewart's own refs.

### Administration paths

- **Git's administration** (`adm.checkout.*`, `adm.common.worktrees.*`,
  `adm.git-admin.*`, `adm.content.gitdir`, `adm.name.dot-git`):
  **supported**. Stewart reads worktree administration to identify checkouts
  and writes its own marker files, `stewart-auditor.json` and
  `stewart-resource.json`, beside Git's. Do not edit them. A path component
  named `.git`, in any case, is never accepted as an audit path.
- **Stewart's storage** (`adm.common.stewart.*`): **supported**. Six
  directories under `stewart/` in your Git directory hold sessions, closing
  records, registrations, request keys, recorded resources and checkout
  registrations. Back them up with `.git`; never edit them.

### Refusals

Every refusal row is **supported**: its reason identifier is stable and its
message says what to do next. Grouped by what they ask of you:

- **Repository shape**: `repository_root`, `path_noncanonical`. Run from the
  top of a non-bare working tree.
- **Commission shape**: `prompt_commit_shape`, `target_ancestry`,
  `target_drift`, `input_drift`, `input_missing`, `input_collision`,
  `input_overlap`, `input_mismatch`, `prompt_drift`, `workspace_guidance`,
  `submodules_present`, `destination_exists`, `reference_mismatch`. Fix the
  commits or the assignment, or choose a fresh audit ID.
- **Checkout identity**: `checkout_*`, `auditor_worktree`,
  `worktree_role_*`, `handoff_identity`, `context_*`, `session_identity`.
  Something about a checkout no longer matches what Stewart recorded; do not
  repair it with Git.
- **Custody**: `session_retention`, `capture_uncovered`, `capture_unverified`,
  `checkout_changed`, `uncollected_changes`, `movement`,
  `evidence_tampered`. Stewart will not claim custody it cannot verify;
  collect again after the writers stop, or abandon with an explicit discard.
- **Resources you asked for**: `resource_*`. Disposal is refused while doubt
  remains.
- **Git itself**: `git_failed`, `git_ref_transaction`, `commit_id`. The Git
  command failed, a ref could not be created atomically, or an identity was
  not a full commit ID.

The selection rule for this class follows values derived from Git up to two
calls deep, so a few rows (for example `manager_grant_missing`,
`request_missing`, `reference_stale`) concern Stewart's own records rather
than your repository, and a few refusals that concern your repository, such
as where the auditor checkouts may be placed, are not listed.
