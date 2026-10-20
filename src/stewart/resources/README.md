# Stewart: custody for managed audits

Stewart owns the mechanical side of a managed audit: initializing an
assignment, preparing a disposable detached checkout, collecting evidence from a
stopped auditor, recording collection-bound maintainer dispositions, publishing
reviewed bytes, exporting selected captures for another assignment, releasing a
paused hold, inspecting a session, and closing a finished or abandoned audit.
It also lets a caller discover the audits a repository records, select one by
a reference it keeps, retry mutations under request keys, and record the
manager worktrees, branches and directories an audit depends on so that close
can retire them. It never launches an agent, runs project tests, commits or
imports implementation changes. Only `close` deletes, and only what a closing
record or a resource claim it wrote authorizes.

The managing agent or maintainer owns everything the tool does not: the
question, the decision it informs, source selection, admissibility reasoning,
scientific interpretation, and the decision to act. The tool records identities,
custody and acknowledgments; it does not grade an audit.

For question selection, start with the [question chooser](QUESTION-TYPE.md#choose-a-question):
[instrument discrimination](QUESTION-TYPE.md#instrument-discrimination),
[information preservation](QUESTION-TYPE.md#information-preservation),
[constrained experiment construction](QUESTION-TYPE.md#constrained-experiment-construction), or
[receipt sufficiency](QUESTION-TYPE.md#receipt-sufficiency).
The [conditional protocols](AUDIT-PROTOCOLS.md) apply only when construction,
execution or research is assigned. These documents guide judgment; they do not
grant permissions or add question types to the assignment schema.

## Ownership

- **Workspace**: a repo-relative directory holding the auditor guidance
  (`AUDITOR.md`), the maintainer guidance (`MAINTAINER.md`), the single assignment
  (`PROMPT.md`), retained `reports/` and declared `scratch/` areas. The tool
  takes it as `--workspace` and derives every assignment-facing path from it.
- **Session**: private records under
  `<git-common-dir>/stewart/sessions/<slug>/<audit-id>/`, where `<slug>` is the
  workspace's last path component plus a digest of its full relative path. Two
  workspaces that share an audit ID cannot address each other's evidence.
  Sessions live in Git's administration, outside every working tree: no ignore
  rule is needed and `git clean` cannot remove them. They may hold sensitive or
  large inputs. Sessions are repo-wide, so every linked maintainer worktree sees
  the same audit IDs, but each belongs to the maintainer checkout that prepared
  it; other checkouts are refused with `session_other_maintainer`.
- **Checkout directory**: each session's auditor material lives at
  `<checkout-home>/<repo-key>/<session-uuid>/`: the detached `worktree/`, the
  supplied `runtime/`, any `runtime-recovered-<name>/` and experiment homes at
  `attempts/<name>/home`. `<repo-key>` is the repository's name plus a digest of
  its common directory. The default checkout home is
  `~/.local/state/stewart/checkouts`; `prepare --checkout-home PATH` selects
  another. The name carries neither the audit ID nor the workspace.
- **Receipts** are append-only while an audit is live. Every record is created
  exclusively; a retry writes a new record with a fresh `<UTC stamp>-<8 hex>`
  name. Timestamps say when the maintainer ran a command, never when the
  auditor started or finished.
- **Closing records**: `close` retires an audit and keeps one record under
  `<git-common-dir>/stewart/closed/<slug>/<audit-id>/<session-uuid>/`. Stewart
  never removes closing records.
- **Repository-level records** live beside them and outlive every session:
  draft and registration records under `stewart/audits/<slug>/<audit-id>/`,
  request keys under `stewart/requests/<sha256-of-key>/`, and recorded resources
  under `stewart/resources/<resource-id>/`. See
  [discovery and continuation](#discovery-selection-and-continuation) and
  [recorded resources](#recorded-resources-and-closeout).

## Manager quick start

Start here when asked to organize an audit. Use the [question chooser](QUESTION-TYPE.md#choose-a-question)
or the caller's supplied question guidance to select one bounded question and
the decision it informs. Name the chosen recipe's path and section in the
assignment; the auditor reads that recipe and only the applicable
[protocol](AUDIT-PROTOCOLS.md). Recipes grant no reading or execution permission.
Workspace guidance owns local roles and assignment conventions; shared recipes
are bundled with the installation.

Choose an existing repo-relative workspace or establish one with distinct
regular `AUDITOR.md` and `MAINTAINER.md` files. These and the
prompt must be committed before preparation. `PROMPT.md`, `reports/` and
`scratch/` have fixed names derived from `--workspace`; a recipe document alone
does not establish a workspace. Commit supporting material separately from the
prompt.

Read `MAINTAINER.md` when managing an audit. The generated `LAUNCH.md` explicitly
assigns the auditor role and directs that agent to `AUDITOR.md`, then `PROMPT.md`.
These role policies apply independently of model and harness. Preparation uses
their committed bytes; local edits cannot change an already prepared checkout.

Workspace `AGENTS.md` and `CLAUDE.md`, when provided for harness discovery, should
give the same role-based routing: an assigned auditor follows `AUDITOR.md`, and
an agent tasked with managing the audit follows `MAINTAINER.md`. The task or
handoff selects the role. Keep role policy in its named file, and harness/model
invocation choices in `LAUNCH-PROFILE.json`. Neither harness entry file is a
Stewart prerequisite or a substitute for a missing role file. These instructions
describe the intended routing; Stewart does not attest to what a harness injects
or an agent reads.

Role policy formerly stored in workspace `CLAUDE.md` and `AGENTS.md` moved to
`AUDITOR.md` and `MAINTAINER.md`. Historical prompts, handoffs and prepared
checkouts retain their original references. Use the pinned tool version for an
older assignment; do not rewrite its artifacts to fit the new workspace layout.

All custody commands require explicit `--repo` and `--workspace` arguments.
The repository selects custody storage; it never selects executable code. Add `--json` for one
machine-readable result document.

Control and custody JSON require unique decoded names within every object.
This covers assignment metadata, report declarations, CLI grant/review/response
files, input and protected manifests, launch profiles, session records, and
evidence-package manifests and source receipts. Nested repeats, identical values
and escape-equivalent names are refused. The same name in distinct objects is
allowed. Whitespace and unique-key order do not change this rule; byte pins still
distinguish differently serialized documents.

Refusal reasons retain the reader's context: `duplicate_input_key` for CLI input,
`duplicate_key` for a report declaration, `assignment_schema` for assignment
metadata, `input_manifest` for an input inventory, `launch_profile` for a profile,
`record_corrupt` for custody records (including protected and package manifests),
and `package_schema` for a verified package source receipt. A matching digest
does not make ambiguous metadata acceptable. Invalid historical records remain
untouched; preserve them and use a fresh assignment or the version that wrote
them for recovery, rather than rewriting their evidence.

Raw child ledger rows, child receipts and package payload files are evidence,
not control documents. Their bytes remain captured and portable even when they
contain repeated names; the child readers retain their documented last-key
semantics. A report's declaration is validated separately after raw capture.
Callable API callers own decoding before passing dictionaries: no API can
recover competing fields already discarded by a caller.

Set `STEWART_PYTHON` to the absolute Python executable in the dedicated venv
where the Stewart wheel is installed. For example:

```sh
STEWART_PYTHON=/absolute/stewart-venv/bin/python
"$STEWART_PYTHON" -I -m stewart --help
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review init --audit-id one-bounded-question --input path/to/entry.py --replace-prompt
```

The installed console entrypoint `<venv>/bin/stewart` starts that venv
interpreter in isolated mode before Python startup. The equivalent module form
is `<venv>/bin/python -I -m stewart`; retain `-I`. Both work outside the source
tree. For an explicit source checkout use
`<python> -I -B /absolute/project/src/stewart/_bootstrap.py source -- <arguments>`.
`--repo` must explicitly select the exact non-bare Git worktree root; a
subdirectory is refused. A symlink spelling of that root is canonicalized. Any
branch name, a legitimate linked maintainer worktree, and detached HEAD are
supported. Known auditor worktrees are refused at manager operations, including
after a move. The private role registry lives in Git's common administrative
directory at `stewart/worktree-roles/`. Each exclusive row records the actual
administrative directory, observed path and a lifetime UUID, also stored in
`stewart-auditor.json` inside that worktree's administrative directory. Moving
the checkout preserves its marker; removing it lets Git remove the marker with
its administration. A later checkout can reuse the administrative directory's
name without inheriting the old role. A maintainer root inside a registered
checkout directory is refused even without its marker. This distinguishes
roles; it does not defend against compromised Git administration, including
its role markers. Role rows are exclusive; only `close` removes a session's
row. Preparation creates the worktree with the Git lock
`stewart auditor registration <uuid>`, publishes the marker and role, then
replaces it with the lifetime lock
`stewart auditor checkout <uuid>: run stewart status before removing; close removes it with its session`.
Git then refuses `worktree remove`, `move` and `prune` for the checkout; its
removal goes through `close`. A failed registration keeps the registration
lock, so even a forced move does not make the partial checkout a maintainer.
Preserve it for inspection; do not unlock it merely to bypass role validation.

The checkout home must be an absolute, unlinked directory private to the
current user (mode 0700), outside every working tree of the repository, the Git
common directory, the manager home and the interpreter prefix; each refusal
names `checkout_home`. Preparation creates the session's checkout directory
before the session itself, so a checkout home the manager's harness cannot
write is refused with `manager_grant_missing` before the audit ID is used.

Preparation records a session UUID and atomically creates
`refs/stewart/sessions/<uuid>/{prompt,target,base}` (base only when assigned).
Create-only refs keep those commits reachable after branch movement, reflog
expiry or auditor worktree removal. They remain while the audit is live, failed
preparations included; only `close` removes a session's refs. Recovery verifies their exact names
and objects and refuses symbolic substitutions. Each create rejects even an
existing dangling symbolic ref without changing its target. Stewart checks for
symbolic names after Git prepares and locks every ref, before committing the
transaction; this also covers Git versions that treat a dangling symbolic ref
as absent during `create`. Inspection failure aborts the transaction. Git's
locks exclude concurrent Git writers, not raw writes to manager-owned Git
administration. Missing or altered
refs refuse recovery; collection still preserves
readable raw report bytes and records the retention failure. Status shows the
failure without inventing recovery commands or repairing the refs.

Conflicting or unreadable role registry records refuse manager operations.
Historical evidence is never relabeled to the current session schema.

The source launcher deploys the selected source into a private, complete runtime tree under
`~/.local/state/stewart/managers` (override with `STEWART_MANAGER_HOME` or the source
launcher's `--manager-home`). Overrides must be absolute, unlinked paths, private
to the current user (mode 0700). Keep this manager-owned directory outside auditor
grants; ownership/mode checks cannot establish a harness's effective grants.
`status` can create this deployment while leaving session evidence
unchanged. Source edits create another deployment; commands already printed
continue to name the retained bytes they selected.

Source selection uses the explicit module and resource inventory in
`_bootstrap.py`; adding either requires updating that inventory. Unexpected
entries inside the package are refused. Source-installation `__pycache__`
entries are omitted during selection; the retained runtime permits no added
entries at all. Project tests and development metadata live outside the package.
The bundled manual, question guide, protocols, role templates and launcher
templates are copied and hashed with the code.
Deployments, retained launchers and process caches occupy separate subdirectories.
The selected runtime may be read-only. Removing a deployment leaves its launcher
available to return a structured refusal; removing the interpreter or launcher
itself necessarily produces the operating system/interpreter's failure instead.

Every manager action printed by `status` is a plain argv selecting the explicit
interpreter, `-I -B`, the retained bootstrap, its complete runtime digest, and the
explicit repository/workspace. Its `env` is empty. The launcher refuses changed,
missing or added runtime members before importing the selected implementation;
it never falls back to another checkout. Its fresh private cache prevents reading
planted bytecode. `-I` ignores caller paths, `PYTHON*` variables and user site
packages. The interpreter, retained bootstrap and environment site-packages
hooks remain trusted. Inventory those hooks in the provisioned environment;
this is not protection against a compromised manager installation.
An incomplete command that removes `-I` or `-B` is refused before the bootstrap's
imports, but interpreter startup hooks can already have run without `-I`.

Every custody record carries a `stewart` field identifying its writing package.
`status` distinguishes the session writer from the viewing implementation. A
retained deployment has null commit/dirty coordinates even when its storage is
inside another Git repository; that repository is not the code's source.
Direct source inspection reports Git coordinates only when every selected
module and resource is tracked. Each generated command also names its loaded package, source path at
selection, selected runtime tree, interpreter and bootstrap identities. The
source path is descriptive and is never an import path for the issued command.
Interpreter identity preserves the venv spelling; it does not freeze an upgraded
interpreter or a changed Homebrew symlink.

In-process API callers own their imports. Their first generated command retains
the source bytes on disk at that moment, once per manager-home selection; it
cannot reconstruct Python objects imported earlier. Use isolated startup to bind
executed Stewart code to the verified inventory.

If a deployment is damaged, preserve it before recovery. An issued command keeps
its exact code-root path and digest; restore those bytes there to recover that
command. Removing a damaged deployment and retaining the exact original source
with the same manager home reconstructs that coordinate; preserve the damaged
tree under a fresh name first. Source edits are not recovery of an older pin.
To use current source independently of a damaged cache, choose a fresh absolute
private directory with `--manager-home /absolute/new-manager-home`; the newly
issued commands identify that new selection. No automatic fallback or overwrite
repairs a damaged deployment.

Then follow this route; the [lifecycle](#static-audit-lifecycle) below gives the
commands and refusal/recovery behavior:

1. [Select the question](QUESTION-TYPE.md#choose-a-question) and [prepare readable evidence](#prepare-readable-evidence).
   Use `init` to pin inputs and draft metadata. Author the five prose sections
   and remove `UNASSIGNED`; the manager decides question quality and scope.
   For a multi-file specimen, add `--input-manifest audit-inputs/ID.json`
   (an uncommitted path of your choosing) to keep per-file identities and
   shared provenance out of the readable prompt.
2. Commit `PROMPT.md` alone. Arrange write authorization in the manager's
   harness before calling `prepare`: every custody-writing command (`prepare`,
   `launch`, `message`, `collect`, `triage`, `retain`, `resume`, `close`,
   `recover-runtime` and the experiment commands) writes
   `<git-common-dir>/stewart`, and `prepare`, `recover-runtime` and experiment
   runs also write the checkout home; `close` removes from both. `status`
   names both locations, and a
   permission failure is refused with `manager_grant_missing` naming the one to
   allow. A failed preparation is preserved; `close --abandon` retires it, and
   releases the audit ID only when nothing could have used it
   ([recovery](#failure-and-interruption-recovery)).
3. Prepare a snapshot. With a [launch profile](#launch-profile) in the
   workspace, `prepare` prints the finished terminal command; paste it and
   record the handoff with `launch --from-profile`. Without one, give the
   generated `LAUNCH.md` to a fresh auditor in its worktree using the
   [terminal recipe](#manual-terminal-launch) and record the handoff with
   [`launch`](#launch-and-message-records) by hand. The harness owns launch,
   configuration and interruption either way.
4. After the auditor stops, collect with the acknowledged stop kind. Use
   `status --audit-id ID` to recover locations and the next review commands.
   A ruling you give a stopped auditor before it continues, and a hand-back it
   sends outside the report, go in with `message`.
5. Run the named collection's `triage-draft`, review its captured bytes, fill
   the response and submit `triage`. Retain only reviewed material. Snapshot
   audits need no resume; paused holds require a recorded release and communication.
6. Export anything worth keeping beyond the retained files, then `close` the
   audit. It keeps one closing record and removes the session, its checkout,
   refs and registry row.

## Prepare readable evidence

Identify each input's role: code entry point, admission-defining data, source
expectation, retained observation, or explanation. Pin the minimal data needed
to check admission premises, such as a vocabulary. If a premise is intentionally
assumed, name it as an assumption and state the resulting limit on the decision.
Supplied bytes are not evidence that the auditor inspected them; review the
reported coverage on return.

Name allowed dependency/search paths and exclusions. Supply a bounded search
example with quoted patterns, replacing these example paths with the assignment's
actual boundary:

```sh
rg -n --glob '*.py' -- 'comparison_name' path/to/allowed-code path/to/allowed-tests
```

Matched lines count as reads. An essential lead outside the boundary should be
reported for expansion, not silently consulted. Custody inventories record
files and changes; they cannot enforce or attest to read scope.

Before committing the prompt, open every producer, consumer or instrument site
the question names at the target commit and confirm it does what the sentence
says. An auditor will correct a mistaken route description, but the correction
costs its time and shifts the question; a rehearsal caught exactly that.

For an experiment grant, author the protected manifest from the instrument's
import closure rather than from memory. In a permitted scratch process, record
the source paths of loaded modules under the protected project, then pin those
files at the target commit. Review that population explicitly; a module without
a source file is a gap, not an empty contribution. Import-time discovery does
not cover lazy imports, data files or later subprocesses; name those separately.

Distinguish the selected sample from the population in an original receipt.
IDs and counts are membership metadata. Statuses, refusal reasons and aggregate
match counts are outcomes even when their operands are not inspected. State
which members' outcomes may be read, including through JSON filters.

For a small sample inside a large receipt, a manager-authored selected-row view
can make the permitted reading easier. Keep the original receipt unchanged;
label the view as derived, record the original path and digest, exact selector
and extraction command or field paths, and verify each selected ID occurs
exactly once. Pin the view as a supplemental input with that provenance. It is
a reading aid, not a new execution receipt or replacement for the original
bindings. The scope must explain permitted uses of the original. Do not supply
an earlier audit's verdict as an input fact.

## Static audit lifecycle

### Compact input inventories

Small assignments can list inputs inline. For larger selections, `init
--input-manifest PATH` factors the committed entry paths and supplemental pins
into one inventory with a shared provenance dictionary. `PROMPT.md` carries its
repo-relative path and SHA-256; the generated draft places prose before metadata.
Use a fresh uncommitted path outside the writable audit scratch area, for
example `audit-inputs/one-bounded-question.json` under a directory the project
ignores. Stewart itself writes nothing in the working tree.

With `--replace-prompt`, the inventory is created exclusively after validation,
then the prompt is replaced. Existing inventory destinations are refused; keep
failed writes and choose a fresh path. Without replacement, nothing is written;
`--json` includes both the prompt draft and `result.input_manifest.document` for
preview. Retain the inventory bytes until preparation. They are supplemental
material, not a second commit prerequisite: commit the prompt alone as usual.

The inventory schema is `stewart.inputs/1`, with `input_files` (committed paths),
`provenance` (key-to-description map) and `supplemental_inputs` (path, SHA-256,
provenance key, and optional exported custody). Preparation verifies the pin,
expands through the ordinary assignment validator, and copies the inventory and
its members into the worktree. It rejects recursion, duplicate paths, unsafe
paths, unknown provenance keys, committed collisions and writable-input overlap.
An inventory identifies supplied bytes; it does not expand reading or execution
permission. Keep the human evidence map and scope in the prompt.

### Assignment and custody steps

1. **Initialize.** `init` resolves the target, pins committed inputs and
   selected supplemental bytes, and writes an unassigned draft. Without
   `--replace-prompt` it prints the draft and writes nothing. Validation precedes
   replacement, so a refused draft leaves the existing prompt untouched.
   Unless `--scratch` is supplied, the draft declares `scratch/<audit-id>/notes`
   for prose, checksum lists and verification output. This grants no experiments.

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review init --audit-id one-bounded-question --input path/to/entry.py --supplemental ignored/specimen.bin "Authored specimen" --scratch audits/parser-review/scratch/one-bounded-question/notes
   ```

2. **Commit the prompt alone.** The prompt commit must have one parent and
   change only the workspace's `PROMPT.md`. The target must be an ancestor with
   intervening differences confined to the workspace, and an assigned input must
   not be among those differences even when it lives inside the workspace.

3. **Prepare.** `prepare` validates the committed prompt, creates the
   session's checkout directory under the checkout home, then the session, and
   the locked detached worktree at the prompt commit. It copies supplemental
   bytes and re-verifies every input digest. It supplies a separately scoped
   runtime beside the worktree, retains pristine assets in the session, and
   writes a public handoff under the worktree's workspace at
   `.stewart-handoffs/<session-uuid>.md`. A pinned private copy remains at
   `LAUNCH.md` inside the session. The handoff names the worktree, the
   supplied runtime and its own file name, prints absolute scratch paths and a
   read-only input-check command, and names no private session path, manager
   storage or harness configuration; the conventional declared `notes`
   directory is created for the auditor.

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review prepare --mode snapshot
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review prepare --mode paused --writers-paused --pause-note "Two implementation writers held by chat agreement; the CI bot still commits"
   ```

   Snapshot is the default: development continues and the answer applies to
   the audited revision. Paused records that the maintainer arranged an actual
   writer hold; `--writers-paused` is an acknowledgment, not process control, and
   is refused in snapshot mode. It requires `--pause-note` saying which writers
   were paused, how, and who still writes; the note is recorded verbatim and
   shown by `status`, never verified.

4. **Launch through your harness.** `LAUNCH.md` names the worktree, the
   auditor guidance file to read first, the prompt and target commits, the
   prompt digest, and the report path, and tells a harness that did not start
   in the worktree to use absolute paths rooted there. If the workspace has a
   [launch profile](#launch-profile), `prepare` already printed the terminal
   command to paste; otherwise configure equivalent harness access and paste the
   public handoff into a fresh auditor thread yourself. The public path avoids
   granting the auditor access to the private session parent. Then record the handoff, from the profile or by hand:

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review launch --audit-id one-bounded-question --from-profile
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review launch --audit-id one-bounded-question --style terminal --model opus --effort max --actor "maintainer"
   ```

5. **Collect after the auditor stops.** The tool cannot observe that the
   auditor stopped; `--auditor-stopped finished|interrupted|blocked` records your attributed stop kind.

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review collect --audit-id one-bounded-question --auditor-stopped finished
   ```

   Collection captures the report first, then takes a no-follow filesystem
   inventory, then records Git patches against the prompt commit and archives
   Git-reported changed, untracked and ignored files, then re-observes both to
   detect movement. Every call creates a fresh collection; nothing is deleted.

6. **Inspect.** `status` is read-only and reports what exists, what is broken,
   who acknowledged what, and which commands are available next.
   It exposes the absolute worktree and launch handoff paths, the checkout's
   Git lock, the manager's write locations, and a captured-report location for
   every named collection. It prints no live report destination: only a
   collection captures a report. Locations do not certify availability or
   integrity: consult preparation state, report status and collection problems.
   Human output includes attributed stop kinds and declaration diagnostics with
   identity comparisons, including after triage. Unavailable completion is
   labeled explicitly; triage does not erase the underlying observation.
   Without `--audit-id`, `status` lists every session of the workspace across
   the repository, with its owning maintainer checkout, preparation state,
   checkout, lock, complete collections and exit code, then the workspace's
   closed audits.

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review status --audit-id one-bounded-question
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review status
   ```

   The exit code reports news, never routine next steps. `attention` lists
   each item with its code: a failed preparation, an interrupted one
   (`preparation_incomplete`), a partial collection or unresolved attempt that is
   still the latest word, gaps on the latest complete collection that no valid
   triage has addressed, a nonzero harness exit with no collection, a session
   written by a different build, and an unfinished close or its leftovers are 1.
   Records that do not verify, a changed handoff (`handoff_changed`), a supplied
   runtime that no longer verifies, and a checkout removed before any complete
   collection (`worktree_missing`) are 3; a checkout removed after one is 1.
   Gaps a valid triage addressed are history. A targeted view of a registered
   session whose records are missing is refused (2, `session_records_missing`);
   the listing reports that loss as 3. The listing's code is the highest of its
   live entries; finished closes never count.

   JSON uses `stewart.status/13`: `identities.worktree.path`,
   `preparation.launch_path` and `collections[].report_path` are the locators;
   `manager_storage` names the private and checkout-home write locations;
   `stage` names the observed stage, `reference` a kept reference for the
   lifetime shown, `implementation` the writing and viewing builds (with a
   handoff when they differ), `resources` each recorded resource's closeout
   disposition and `requests` the request keys bound to the audit. The
   listing uses `stewart.status-list/1`. The asset recovery command appears only
   while the supplied runtime fails verification. A ready checkout with no
   collections offers a conditional manual `handoff` action carrying `cwd`,
   `launch` and an absolute `prompt`, without `argv` or an inferred launch
   state, followed by a `launch` action to record the handoff. Command actions
   carry isolated `argv`, an empty `env`, and `runtime` identity. Each untriaged complete
   collection offers `triage-draft` before `triage`; neither action accepts its
   claims. A failed or incomplete preparation offers `close --abandon`. A
   concluded session offers `close` once its latest complete collection is
   triaged, no paused hold or unresolved attempt remains, nothing else is
   pending (a retention, release or run would need the bytes close removes),
   and a fresh inventory equals that collection's. `closes` lists earlier closing records under the
   same audit ID. `tool` is the viewer's build; `session.stewart` is the build that
   wrote the session and `session.same_build_as_viewer` compares them.
   `launches` and `messages` list the manager's coordination records. Each
   release carries `frozen_artifacts`, the frozen paths a collection can capture
   (the script, the frozen declarations, and the manifest when it is a
   supplemental input; committed files cannot be captured unchanged),
   `captured_in`, the collections whose selected bytes are verified recoverable
   and equal all of them during this status read, and `uncaptured_artifacts` for
   those no collection can then supply. Discovery digests select candidates;
   the same reader used by export and retention verifies archive digests, unique
   regular members and payload digests. `capture_problems` names the collection,
   artifact and refusal reason when a candidate fails verification. A completed
   collection receipt does not establish a complete archive, and a historical
   capture does not establish present availability. Status never substitutes
   live worktree bytes or rewrites historical receipts. `release` is offered
   only once a complete collection exists, because release freezes bytes a
   collection should have captured. Status is a read-only view, so these fields
   do not change stored session/receipt schemas.

7. **Triage.** Draft an unanswered response for one named collection, then fill
   the response and submit it. Drafting records nothing.

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review triage-draft --audit-id one-bounded-question --collection 20260101T120000-0a1b2c3d
   ```

   In prose mode stdout is response JSON alone; the report status, one line per
   declaration identity comparison, the declaration diagnostics and the gap
   context go to stderr. JSON mode separates `result.response` from `result.context`.
   Save only the response object for submission. Null decision, gap dispositions
   and any unanswered report gap deliberately fail validation. Preserve its
   `collection` and `collection_sha256` fields: submission verifies both against
   the named capture, even when another capture has identical report bytes.
   The receipt digest comes from the exact bytes read, and the report digest is
   checked against captured bytes; changed captures are refused.

   Then bind the completed response to that same collection:

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review triage --audit-id one-bounded-question --collection 20260101T120000-0a1b2c3d --response response.json --actor "maintainer"
   ```

   The response states `collection` and `collection_sha256` from the draft,
   `report_sha256` of the captured report (or `report_gap`
   when none was captured), `accepted`/`rejected`/`unresolved` claim lists, a
   `custody_gaps` map with a disposition for every gap the collection recorded,
   a `decision`, and optionally `support_reviewed` paths and an `applicability`
   note for snapshot audits. Empty claim lists are valid; a cancellation is a
   triage with a decision and no claims. Validating the shape does not validate
   the reasoning.

8. **Retain.** Publish the reviewed report and/or reviewed support files from
   the immutable capture into the maintainer checkout. Destinations are created
   exclusively; nothing is staged or committed. Report retention does not
   require accepting any claim.

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review retain --audit-id one-bounded-question --triage 20260101T121500-4e5f6a7b --report
   ```

9. **Resume a paused hold.** Only paused sessions have a hold; resume references
   a triage and records the release. Status, retention and resume revalidate the
   same collection receipt and report bindings. A changed capture needs a fresh
   review or cancellation; status explains the broken binding and withholds
   retention/resume suggestions. Tell the writers yourself.

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review resume --audit-id one-bounded-question --triage 20260101T121500-4e5f6a7b --reason "Findings triaged; follow-up selected."
   ```

10. **Close.** Once the audit's durable outcome has left Stewart, through
    retention or `export`, `close` retires it. Export anything else worth
    keeping first: closing keeps no report bytes, patches or inventories.
    `close --plan` describes everything close would remove, preserve or leave
    and writes nothing; after its closing record a close also retires the
    [recorded resources](#recorded-resources-and-closeout) whose last use it ends.

    ```sh
    "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review close --audit-id one-bounded-question --actor "maintainer"
    "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review close --audit-id one-bounded-question --actor "maintainer" --abandon --reason "Preparation failed before any handoff"
    ```

    A concluded close (the default) needs records that verify (otherwise
    `close_unverified`, 3), a triage bound to a complete collection
    (`close_not_concluded`), no outstanding paused hold
    (`close_hold_outstanding`), no unresolved experiment attempt
    (`close_attempt_unresolved`) and a checkout unchanged since that collection
    (`checkout_changed`; collect and triage again, or abandon). `status` offers
    `close` only when these hold for the latest complete collection and no
    other action is pending. An
    abandon (`--abandon --reason TEXT`) is allowed in any state, including
    failed preparations and records that do not verify. It refuses while the
    checkout holds changes no collection captured, or when it cannot observe
    the checkout fully: entries Git cannot list, a commit no complete
    collection recorded, a checkout Git now registers elsewhere, or a `.git`
    that is not the checkout's own gitdir file (`uncollected_changes`). With
    `--discard-uncollected` the closing record lists the discarded paths and
    digests, or `null` when they could not be observed. A session whose directory is gone
    but whose registry row remains can be abandoned through that row; one with
    neither a record nor a row is retired as its session directory alone. An
    audit recorded only by a draft, registration or resource context recorded
    after its last close can be abandoned too: the closing record ends those
    uses, and the audit ID stays reserved. The
    triage decision, if one was recorded, is kept as the manager's attributed
    decision.

    `close` writes `CLOSING.json` exclusively before removing anything:
    identity, the acknowledgment (actor, mode, and an abandon's reason), the
    observations it rests on (triage and collection digests, retained paths and
    digests, or an abandon's observed stage, problems and release basis), the
    auditor's attributed completion and report kind and the manager's
    attributed decision, and the removal inventory. It then removes, in order,
    the checkout (unlocked, then `git worktree remove`; a checkout Git cannot
    validate is removed as its recorded directory), its recorded runtimes and
    experiment homes, the checkout directory if empty, the retention refs the
    session recorded (each with `--no-deref` and its expected commit), the role
    registry row, and the session directory last. Removal never follows a
    link: a link in place of a recorded directory is removed or kept, never
    traversed. Removal stops at the first failure and records the attempt in
    `CLOSE-ATTEMPT-<stamp>.json`, relocking the checkout if it remains; `status`
    reports the close as incomplete and a rerun of `close` finishes from the
    recorded inventory, never a wider one. A close interrupted before writing
    `CLOSING.json` leaves at most an empty directory, which a rerun reuses.
    `CLOSED.json` records each removal's outcome once nothing recorded remains.
    Recorded paths are trusted only inside the session layout,
    `<checkout-home>/<repo-key>/<session-uuid>/`, and only for a canonical
    session UUID; a record that names anything else directs no removal of a
    checkout, and a closing record whose inventory points outside its session
    does not verify (`closing_record_invalid`). Each record is published by
    linking a complete staged copy to its name, so an interruption never
    leaves a partial record. Leftovers are kept and named, in `CLOSED.json`
    and in the closed view, and make `close` exit 1: unrecorded entries in the checkout directory, a link
    or file where a recorded directory belongs, a ref under the session's
    namespace that it did not record or that is symbolic or moved, and a
    checkout Git now registers at another path. Closing a paused session
    releases no hold; tell the writers. The closed view keeps saying so.

    A concluded close keeps the audit ID reserved. An abandon releases it only
    when no chain of evidence can exist under it: `PREPARE-ERROR.json` exists
    and names a stage before the handoff, neither `LAUNCH.md` nor the public
    handoff exists, the session holds nothing beyond `session.json`, the
    failure receipt and the runtime stage's records (no launch, message, exit,
    collection or other record), and the checkout, if created, was observed
    and holds only preparation's footprint: the committed tree, the pinned
    supplemental copies, the report's parent and notes directories and the
    handoff directory, with HEAD at the prompt commit. Any other file or
    directory blocks it. Every doubt keeps the ID reserved. `init` and `prepare` reapply
    that rule to every closing record under the ID: a reserved ID is refused
    with `audit_id_reserved`, an unfinished close with `close_incomplete`, and
    an unreadable or unsupported record with `closing_record_invalid` (3). A
    released ID may be prepared again from any prompt commit that carries it.
    `status` on a closed ID shows the closed view (`stewart.status-closed/2`, which adds
    the reference and what remains of the audit's resources):
    when and by whom it closed, the mode, the decision or reason, what was
    retained, and whether the ID is `reserved`, `released`, `close_incomplete`
    or `unverified`. Earlier closes are listed beside a live session for the
    same ID.

## Discovery, selection and continuation

An audit is a workspace and an audit ID within one repository; a lifetime is
one prepared session, named by its UUID. A released audit ID can be prepared
again, so one audit may have several lifetimes over time; at most one is live.

### Recorded audits and drafts

`init` without `--replace-prompt` still writes nothing. With it, `init` first
writes `stewart/audits/<slug>/<audit-id>/init/<name>/STARTED.json` (the
checkout, the intended writes and their digests, the prompt it replaces, the
closes already recorded) and then `OUTCOME.json` (what was written, or the
failure). An interrupted init leaves a start record without an outcome; status
reports it as `draft_incomplete`.

`register --audit-id ID --actor NAME` records an existing workspace whose
`PROMPT.md` assignment block names the ID: it reads `AUDITOR.md`,
`MAINTAINER.md` and `PROMPT.md` through verified descriptors and records their
present digests in `registrations/<name>.json`. It states what was observed at
registration and implies no earlier custody. Both refuse a reserved ID and an
ID whose session already exists. A workspace no record names is absent from
discovery; Stewart never guesses workspace directories.

`status --audit-id ID` on a recorded audit with no session prints the draft
view (`stewart.status-draft/1`): its draft records, whether each recorded file
is unchanged, changed, missing or unavailable in its checkout now, and the
`prepare` step. When the checkout that held a draft is gone, its files are
unavailable; the record keeps only their digests, never their bytes.

### Discovery

```sh
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" discover
```

`discover` needs only `--repo` and writes nothing. It reads every
repository-level record under the Git common directory (sessions, closing
records, draft and registration records, role rows, resource contexts,
resources and request keys) and lists each audit across workspaces and
maintainer checkouts with its workspace, observed stage (`draft`, `context`,
`prepared`, `preparation_failed`, `preparation_incomplete`, `closing`,
`closed`, `records_missing`, `unsupported` or `unverified`), present lifetime, owner checkout
and whether it still exists, every closing record, draft record, problem and
resource, and the audit IDs it shares with other workspaces. JSON uses
`stewart.discovery/1`.

Records are read only through a supported discovery envelope: the top-level
`schema` or `schema_version`, a `workspace` accepted only when its slug matches
the record's location, and the `stewart` stamp. A session with an unsupported
schema is listed with its location and envelope; no lifecycle state is inferred
from its other fields. A supported session must also load as status and every
mutation load it (from its owner checkout, when that still exists); one that
does not is `unverified` with the loader's reason, and select refuses it.
Invalid and unreadable records, and role rows that do not verify, keep their
diagnostics instead of hiding the rest. The exit code is 3
when a record does not verify, 1 for unfinished work, and 0 otherwise.

### Selection references

```sh
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" select --audit-id ID
"$STEWART_PYTHON" -I -m stewart --ref audit-ref.json status
```

Save the first command's output (the reference alone) as `audit-ref.json`.

`select` resolves an audit ID (with the global `--workspace` when several
workspaces share it) to a reference, `stewart.audit-ref/1`: `repository` (the
Git common directory), `checkout` (the maintainer checkout commands run from),
`owner` (the session's owner or the draft's checkout), `workspace`, `audit_id`,
`lifetime` (the bound session UUID, or null before preparation), `closes` (the
closing records known at selection) and `implementation` (the writing package
digest). Prose output is the reference alone, ready to save; JSON wraps it in
`stewart.selection/1` with the discovery entry. Selecting writes no record of
any kind, prepares no runtime and keeps no "current audit" setting; two
callers' references never affect each other. Ambiguity is refused with `selection_ambiguous` (several
workspaces, or drafts in several checkouts: run select from the one to
continue), a missing audit with `selection_missing`, and records this
implementation cannot read with `selection_unresolved`. Stewart never selects
the newest collection, a replacement lifetime, the current directory or a
different installation.

`--ref FILE` supplies `--repo`, `--workspace`, `--audit-id` and the lifetime to
any command; explicit values that disagree are refused (`reference_mismatch`).
An explicit `--repo` with `--ref` runs from that maintainer checkout instead of
the reference's own, and must be a checkout of the reference's Git common
directory (otherwise `reference_mismatch`). When the reference's checkout is
gone and no `--repo` is given, the session's owner checkout or the repository's
main checkout is used if it still is a checkout of the same common directory;
otherwise the command is refused with `reference_checkout_missing`, naming
`--repo`. Operations that need the session's owner still refuse from any other
checkout. Every use revalidates the reference against the records as they are
now: the same common directory from the checkout in use, the same session
lifetime, and the same recorded implementation. A reference
taken before preparation never selects the session prepared since, and one
taken before a close never selects a later draft or lifetime
(`reference_stale`); select again. `prepare` returns a reference bound to the
new lifetime, and `status` includes the reference for the lifetime it shows.
`--lifetime UUID` binds a lifetime without a file; every command status
generates carries it, so an action never reaches a replacement lifetime.

Status actions name their API `operation` and their `operands` with the
digests read for the view (collection and triage receipt digests). The `close`
action names the collection it was offered for, and a close that would rest on
another one is refused (`action_stale`). Triage responses keep binding the
collection name and receipt digest. Selection conveys no permission to execute
or delete anything.

### Request keys

```sh
"$STEWART_PYTHON" -I -m stewart --ref audit-ref.json --request-key collect-7f3a collect --auditor-stopped finished
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" request --key collect-7f3a
```

Every mutation accepts `--request-key KEY` (API `request_key=`): 1-128
letters, digits, `.`, `_` or `-`, starting with a letter or digit. Persist the
key before submitting. The key's records live in
`stewart/requests/<sha256 of the key>/` with the exact key inside, so keys
differing only in case never share a record. `REQUEST.json` is published
exclusively before any side effect. It binds the operation, the selected audit,
lifetime and resources, the implementation and the semantic inputs: decoded
control documents (responses, reviews, grants) by canonical digest and supplied
files (supplemental inputs, evidence-package manifests, a launch profile) by
byte digest. The invoking checkout is recorded beside the binding, not in it.
The operation records its planned output identities in `attempts/` just before
its first side effect, and `OUTCOME.json` records completion or refusal with
the output identities. Execution holds an exclusive lock on the request;
inspection holds a shared one while it reads, so an inspector is never taken
for a running executor (an executor waits briefly for readers to finish).

A key is resolved before anything else is validated, from any maintainer
checkout of the repository; a retry needs neither the session, the lifetime, the
reference's checkout nor the resources to still exist. Reusing a key with a
different binding is refused (`request_key_conflict`, naming the differing
fields; under another implementation, `implementation_mismatch` with a handoff
to `request --key KEY`), also while another process is executing the key. A
reference is revalidated only when the key's request will execute (a new or
`reserved` key); a retry answered from its records needs nothing else. The
same key and binding never execute again:

- `completed`: the recorded outcome and its output identities, each reported
  as `available`, `changed`, `retired` (its lifetime or resource was retired or
  acknowledged) or `missing` now; a resource output is observed through its
  own records and identity. A keyed collect returns the same collection, never a new one.
- `refused`: the recorded refusal; correct the cause and use a new key.
- `in_progress`: another process holds the request now.
- `reserved`: the binding was recorded but no side effect was planned; the same
  key and inputs run it.
- `partial`: attempts were planned but no outcome was recorded. A side effect
  may or may not have happened; the planned outputs are shown as observed now,
  and nothing is replayed. A close whose removal failed (a session item or a
  claimed resource) also stays `partial` instead of recording an outcome. Only
  `close` (and `close --resource`) resume safely, and only with
  `--resume-request`, which appends a new attempt and continues from the
  close's own frozen inventory and claims; it adopts a close finished elsewhere
  only when that close is the one its own request planned. `--resume-request`
  on a key with no request is refused (`request_missing`), and on a `reserved`
  one (`request_not_resumable`): nothing started, so run it without the flag.
- `unverifiable`: the request's records do not verify.

A replayed request's JSON result is its `stewart.request/1` document with the
recorded exit code (`error` carries a recorded refusal). `request --key KEY`
inspects without executing. Without a key every call is a new request; Stewart
never deduplicates by payload, time or recency, and distinct keys can
intentionally produce separate collections of identical report bytes. If the
caller loses its key, `discover` lists every recorded request with its exact
key, operation, audit, lifetime and state for explicit inspection; Stewart
cannot tell which request carried the lost intent. Request records outlive the
sessions and resources they name, so a retry after closeout reports the
historical outcome and never recreates retired work. A key reserves intent; it
does not make a side effect happen exactly once.

### Implementation identity and runtime handoff

Every record's `stewart` stamp names the writing package by `package_sha256`,
the digest of its complete member inventory, which does not depend on where it
is installed: the same bytes at another location are the same implementation.
Reading is allowed under any build whose schemas are supported. A mutation of a
session, the resumption of a close or a claim, and a request retry under a
different implementation are refused with `implementation_mismatch`. A record
with no verifiable stamp is refused with `implementation_unrecorded` (3), except
that an abandon of an unreadable session stays possible.

When the writer's recorded invocation verifies by descriptor reads alone, the
refusal, `discover` and `status` offer it as a structured handoff
(`implementation.handoff`, and `error.handoff` in `stewart.result/3`): the
deployment at `<manager home>/deployments/<digest>/runtime` must hold exactly
the recorded members under the recorded runtime digest, the launcher at
`<manager home>/launchers/<digest>.py` must have the recorded bytes (the
deployment's bootstrap), and the interpreter must be an executable file. The
handoff is `{state: verified, argv, env: {}}`: the supported isolated-manager
argv with the operation's arguments. Otherwise it is `{state: unresolved,
missing, diagnostics}`, naming `invocation` (an in-process writer records
none), `package_identity`, `runtime`, `launcher` or `interpreter`. Stewart
never runs, imports or relays recorded command text, never falls back to the
current installation, and a verified handoff establishes only consistency with
the recorded pin. The handoff's argv is the recorded launcher invocation
followed by a read-only `status` (or `request --key`, `resource show`) for the
record concerned; status, run under it, offers that build's own actions. Status
renders mutation actions for a session written by another build with the
handoff's argv, or withholds them and names the missing prerequisites. For a
session whose writer is unrecorded, status withholds every mutation action
except an abandon.

## Manual terminal launch

Use the absolute worktree and public handoff paths returned by `prepare` or
`status`. A manual handoff requires explicit harness configuration: write access
to the worktree, read-only access to the exact supplied runtime subtree and to
Git administration, and no access to `<git-common-dir>/stewart` (sessions, role
registry and closing records), the maintainer checkout's other entries, other
sessions' checkout directories or the manager home. Do not add the session
directory or the checkout directory as a harness working directory. The
handoff describes permitted operations; filesystem access is enforced by the
harness, not by the prose or Stewart itself.

The launch profile below renders the qualified adapter's complete command.
Use that printed command when using its harness. Another harness needs a
separately qualified adapter or an explicitly configured equivalent boundary;
changing a profile's model name does not choose or qualify an adapter.

### Launch profile

A workspace selects its model and harness recipe in `LAUNCH-PROFILE.json`
beside its guidance. The scope adapter supplies the access controls:

```json
{
  "schema": "stewart.launch-profile/2",
  "scope_adapter": "claude-code-restricted/1",
  "harness": "claude-code-tui",
  "style": "terminal",
  "model": "opus",
  "effort": "max",
  "actor": "maintainer",
  "env": {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"},
  "command": ["claude", "--model", "{model}", "--effort", "{effort}", "{prompt}"],
  "note": "optional; recorded with each launch made from the profile"
}
```

`command` is an argv list with an executable, optional `--model {model}` and
`--effort {effort}` pairs, and a final `{prompt}` token. The adapter also accepts
`-p`/`--print`, `--verbose`, `--no-session-persistence` and an explicit
`--output-format text|json|stream-json`. A probe uses the same options and a
final literal prompt. Other arguments, repeated flags, directory grants,
settings, MCP, tools and permission overrides are refused. `env` may set
`LANG`, `LC_ALL`, `TZ`, or `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`; harness controls
come from the adapter. The executable and managed harness configuration remain
trusted. Model and harness labels do not establish which implementation ran. `prepare` validates the profile before allocating a
session, pins its bytes and digest into `session.json`, and prints the
rendered block: a subshell that changes into the worktree, sets `env`, and
runs the argv with every token shell-quoted after substitution. `status`
reprints the pinned block while no collection exists, and
`launch --from-profile` records style, model, effort, actor, note, the
profile's digest and the exact command. A later edit to the file changes
nothing for sessions already prepared; it applies to the next `prepare`.
Explicit `launch` flags override single values from the profile.

The profile validates the adapter contract; it cannot establish whether the
harness accepts the requested model name or effort level. Stewart still
launches nothing, and the profile never reaches an auditor; commit it with the
workspace guidance so it is reviewed like them. A symlink, directory or
malformed file at the profile path is refused rather than ignored.

Those names belong to the harness vendor and can go stale without notice, and
the person who finds out is usually the one who pasted the command and looked
away. Three cheap defenses:

- **A probe.** An optional `probe` argv, with the same placeholders, that runs
  the same model, effort and environment through a short non-interactive
  invocation. `prepare` and `status` print it ahead of the launch block with
  `expect 'probe exit 0'`; its own exit code is echoed. Run it first: a renamed
  flag or a retired model name fails in a few seconds while you are watching.
  Its shell block returns the actual probe status, including under `set -e`, so
  `PROBE_BLOCK && LAUNCH_BLOCK` gates launch on success. The blocks remain printed
  shell text; Stewart starts no harness.

  ```json
  "probe": ["claude", "--model", "{model}", "--effort", "{effort}", "-p", "Reply with the single word OK and nothing else."]
  ```

- **The harness exit record.** The launch block appends the harness's exit code
  and UTC time to `HARNESS-EXIT.txt` in the session when the harness ends.
  `status` lists the exits, and names as outstanding a nonzero exit with no
  collection, which is the signature of a launch nobody watched. This is the
  block's observation of the harness process; it says nothing about the auditor.
  The shell block returns that same process status after logging. A failed log
  append is reported and makes an otherwise successful block fail; it cannot
  conceal a nonzero harness status. An auditor can finish while the TUI remains
  open, so an absent exit record is not evidence of an auditor failure.
- **An override for a stale pin.** `status --profile PATH` and
  `launch --from-profile --profile PATH` render from a working-tree profile for
  a session whose pinned recipe went stale, naming both the pinned and the
  override digests, so a repaired profile serves an existing session without a
  fresh audit ID.

After a harness update, run the opt-in check with an explicit profile file.
It prepares a disposable source-free project and drives that profile's probe
through the real harness; it is skipped otherwise because it spends a request:

```sh
STEWART_PROBE_REAL_HARNESS=/absolute/path/to/LAUNCH-PROFILE.json "$STEWART_PYTHON" -I -B /absolute/stewart-project/scripts/check.py -k test_stewart_real_harness
```

A renamed environment variable is the one drift none of this catches: the
harness ignores it silently and the symptom is context leaking into the
auditor. The auditor's disclosure of injected context and the profile digest in
the launch record are what attribute such a run to a profile version.

### Launching as a harness sub-agent

A manager can hand the public prompt to a spawned agent only when its harness
can enforce the same access scopes. A sub-agent that inherits unrestricted
manager permissions does not meet this boundary. Record and disclose other
context differences in the launch note:

- The sub-agent inherits the manager's working directory and cannot be given
  another. Use the absolute prompt; `LAUNCH.md` tells the auditor to root every
  path in the worktree.
- The harness injects the manager's own directory guidance and Git status into
  the sub-agent's context, which can name other audits' files. Two rehearsals
  saw this; the auditors disclosed it and opened none of it.
- Memory, environment and permission mode are the manager's, not a fresh
  session's. Interruption is whatever the harness offers to stop an agent.
- A stopped sub-agent can usually be resumed with a message, which is how a
  manager gives rulings; record them with `message`.

## Launch and message records

Stewart launches nothing and observes no auditor, so these two commands exist
to make the manager's side of the coordination part of the session. Both write
append-only receipts; neither grades anything.

```sh
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review launch --audit-id one-bounded-question --style subagent --model opus --effort max --note "Agent tool, general-purpose; full LAUNCH.md pasted with one sentence on absolute paths" --actor "manager"
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review message --audit-id one-bounded-question --direction to-auditor --text "Ruling: the wrapper creates the output area; accept an existing empty directory." --channel "harness message" --actor "manager"
```

`launch` records the style (`terminal`, `subagent` or `other`), the model and
effort requested of the harness, a note and the actor, bound to the session's
launch token and prompt commit. `message` records one message as the manager
relays it, in either direction. `status` lists both, offers `launch` after the
handoff, and notes once when collections exist without any launch record. A
launch record is the manager's acknowledgment of a request made to a harness; it
does not establish which model actually ran, and a message record does not
establish that the auditor read it.

## Auditor report declarations

The handoff grants the supplied input verifier through its isolated helper
launcher, with the same
checkout, prompt and token arguments as the declaration commands. It shares
their context validator and preparation's input comparison, but reads no report
or manager session and writes nothing. All selected files remain in its count,
including missing, changed, linked or special entries. Expected committed bytes
come from the target revision, not the working file being measured. Manifest
identity is checked before using its population and again after observation.

Default output prints counts and every failed row, each with its code and fix.
`--print` adds all per-file expected/observed digests; `--json` prints one
`stewart.input-check/2` result or refusal document. Exit 0 means every selected
byte identity matches. 1 means a committed input changed; restore it with the
printed `git show <prompt-commit>:<path> > <path>`, which writes only the
working tree, and run the verifier again. 2 means the context was refused or
usage was invalid. 3 means a supplemental input or the input manifest differs:
its original bytes are not the auditor's to restore, so describe it in the
report, declare, and stop. These checks establish byte identity at read time,
not continuous preservation, reading coverage, permissions or scientific value.
Auditors can keep checksum lists and verification output in their declared notes
directory; harness scratchpads are not authorized substitutes.

The public handoff supplies pasteable `start`, `set --completion complete
--report-kind answer`, and `check --print` commands for the declaration helper.
Each command selects the prepared interpreter and external runtime explicitly,
using `-I -B` and the shared bootstrap's fixed helper mode. These narrow
operations and their help are authorized; other execution requires its own
grant. Project history need not contain Stewart. A project-local helper,
package, environment path or planted bytecode cannot choose the issued helper's
implementation. Preparation verifies and retains the complete supplied runtime;
it executes no audited code to test imports.

`start` exclusively creates a partial skeleton at the committed assignment's
report path. An occupied destination requires `set` or `check`, never automatic
replacement. `set` replaces only the reserved block and preserves every other
byte. `start` and `set` refuse with `handoff_identity` when their arguments
differ from the issued handoff. Every successful operation prints completion,
report kind, audit ID, observed HEAD and report path; `--print` additionally
prints the full validated JSON. Exit 0 means the operation validated; exit 2
names a stable refusal reason and correction step.

`check` reads without writing: make it the last action before stopping. It
takes the session's identities from the issued handoff: the one file in the
handoff directory, named by a session UUID, whose `Handoff file:` line states
its own name. Other files beside it, including copies, are ordinary unexpected
paths; a renamed handoff is unavailable (3), as collection finds it changed. It
runs the same report, inventory, Git discovery, archive and declaration
observation a collection runs. Its `stewart.auditor-check/1` result lists every
gap a collection of the unchanged checkout would record that the checkout
alone can show, each with its code and the change that clears it, and its exit
code predicts the manager's: 0 nothing to change, so stop; 1 change what is
listed and run `check` again; 3 something the auditor cannot repair does not
verify (a supplemental input that changed or is missing, a changed input
manifest, an unavailable handoff): describe it in the report, declare, and
stop. File fixes write only the working tree, because the qualified harness
denies writes to Git administration, where the checkout's index lives: restore
a committed file with `git show <prompt-commit>:<path> > <path>`, and move a
stray file under a declared scratch path rather than deleting it. Staging a
path or moving HEAD needed a Git administration write, and so does the fix:
unstage with `git reset -q <prompt-commit> -- <path>`, and restore HEAD with
`git reset --soft <prompt-commit>`. While the input manifest does not verify,
`check` cannot tell which uncommitted files are supplied inputs, so it never
suggests removing one. Arguments that differ from the handoff are reported as
`command_mismatch:<field>` (1). Manager-side facts, such as movement during
collection or a completion and stop discrepancy, are never `check`'s concern.
Declared completion and report kind never change any code.

A report contains exactly one unindented LF-delimited block, with no trailing
fence spaces, BOM, duplicate keys, extra fields, nested block, or duplicate block:

```audit-report
{
  "schema_version": 2,
  "audit_id": "one-bounded-question",
  "target_commit": "<full lowercase target commit ID>",
  "launch_prompt_commit": "<full lowercase prompt commit ID from handoff>",
  "prompt_sha256": "<64 lowercase hex characters from handoff>",
  "launch_token": "<16 lowercase hex characters from handoff>",
  "observed_checkout_commit": "<full lowercase observed HEAD>",
  "completion": "partial",
  "report_kind": null
}
```

Replace the angle-bracket values with actual identities when editing manually.
Completion is exactly `partial`, `complete`, or `blocked`. `report_kind` is
`answer`, `needs-evidence`, or `reframe`; the initial partial skeleton has a null
kind. A partial or blocked report may leave it unset, but a complete report must
select one. `set --completion complete --report-kind needs-evidence` updates both
fields in the reserved block. Omitting `--report-kind` preserves the existing
selection; it never supplies an implicit `answer`. Keep qualifications
on the skeleton's **Completion qualification:** prose line; reasoning, coverage,
conclusions and limitations remain prose outside validation. Manual editing is
allowed, but run `check` afterwards. A missing or malformed declaration receives
an explicit diagnostic; no completion is inferred from prose.

The helper derives audit ID, target and report path only from committed prompt
bytes, verifies the transcribed prompt digest, and requires the working prompt
to be byte-identical on every operation. It requires a detached HEAD at the
transcribed launch commit, a worktree-style `.git` file, and an absolute
`--expected-worktree` from the handoff matching the actual canonical Git root.
An unexpected commit is reported; `check` names `git reset --soft` as its fix,
which keeps the changes, and the report should mention the commit. Two detached
worktrees at the same commit remain different destinations.

The helper takes the launch token from the handoff without private session
access. Only Stewart checks that it equals the issued value. This establishes
agreement with a handoff value, not proof that anyone read or understood it, and
is not a security measure. These checkout checks do not provide isolation.
Session schema 12 pins declaration schema 2 as well as the token. Earlier
sessions and declarations are unsupported by this version and left unchanged.
Use the pinned tool version to finish an ongoing older audit; do not relabel
its declaration, rewrite its receipts, or replace its running checkout. From
the maintainer checkout, use a retained wrapper that starts the explicit
interpreter with `-I -B`, allocates a fresh empty cache prefix, and inserts only
the old checkout before importing its CLI. Select the destination explicitly:

```sh
/absolute/compatible/python -I -B /absolute/retained/recover-old.py --repo /absolute/maintainer --workspace path/to/audit status --audit-id ID
```

Construct and test that wrapper with the matching historical checkout before
changing schemas; `recover-old.py` above is its chosen location, not a supplied
command. Keep it for subsequent collect, triage and retention commands. Old
versions' printed commands may select the wrong code; invoke recovery actions
through the retained wrapper instead.
The target repository locates the session; it need not supply the running tool.

Report publication stages a file in the report directory before atomic
publication, rechecking prompt, checkout and report inputs. Symlinks and special
files are refused. Failed staging files are named and preserved for collection.
These are endpoint checks, not a lock against concurrent hostile writers.

Collection preserves raw bytes before declaration or Git work, even for malformed
or interrupted reports. It validates only the capture and records comparisons
and their sources. Declaration gaps require triage: `declaration_missing`,
`declaration_invalid:<reason>`, `declaration_mismatch:<field>`, and
`declaration_stale` (declared checkout versus collected HEAD). The independent
`checkout_commit_changed` compares launch commit versus collected HEAD. Neither
relationship establishes mutation chronology. A complete declaration with an
interrupted acknowledgment adds `completion_stop_discrepancy`; completion followed
by interruption can make both claims true, so triage explains it without a verdict.

For example, a completed triage response can use these claim objects (actual
report digests, evidence references and gap IDs must come from the named capture):

```json
{
  "collection": "<named collection from triage-draft>",
  "collection_sha256": "<receipt digest from triage-draft>",
  "report_sha256": "<captured digest from triage-draft>",
  "accepted": [{"claim": "Named comparison agrees", "evidence": ["REPORT.md:12"]}],
  "rejected": [{"claim": "Universal coverage", "reason": "Unselected cases were not measured"}],
  "unresolved": [{"claim": "Residual cause", "reason": "No check distinguishes the rivals"}],
  "custody_gaps": {"completion_stop_discrepancy": "Completion was followed by interruption; retain both attributed claims."},
  "decision": "Retain the reviewed bytes and investigate the unresolved cause.",
  "support_reviewed": []
}
```

### Report kinds and manager follow-up

A report kind is the auditor's hand-back, independent of completion and the
manager's stop acknowledgment. A complete `needs-evidence` report can meet the
assignment's stopping condition without settling the original question. Kinds
apply across question recipes and confer no reading or execution permission.

| Kind | Reporting obligation |
| --- | --- |
| `answer` | Answer the assigned question with coverage, evidence and assumptions. Demonstrated insufficiency is an answer when insufficiency settles the assigned decision. |
| `needs-evidence` | State the undecidable premise and what is already known; request the smallest missing artifact or observation with its required identity/provenance; explain which competing answers it would distinguish and whether it needs supply of existing evidence or new measurement. |
| `reframe` | Give the supported answer to the assigned question; cite evidence motivating one bounded replacement question and explain which maintainer decision it would better inform. Propose the new investigation without conducting it. |

A current rerun cannot recover an unrecorded historical observation. An optional
stronger receipt is not automatically a missing prerequisite. Keep incidental
follow-up suggestions in prose and choose one primary kind. Interrupted or
operationally blocked reports preserve what was learned and may leave kind unset.
The helper checks structure and identities; the manager judges necessity,
consequence, and whether the prose fulfills these obligations.

Collection preserves every report before validation. `status` exposes completion
and kind separately under `auditor_reported`, attributed to the auditor and read
from the latest captured declaration. Missing, invalid or mismatched declarations
do not acquire a kind from prose, an older report, or a cached summary.

For a valid captured `needs-evidence` or `reframe` declaration, `triage-draft`
adds this unanswered field to the collection-bound response:

```json
{
  "follow_up": {
    "report_kind": "needs-evidence",
    "disposition": null,
    "reason": null
  }
}
```

Fill `disposition` with `accept`, `decline`, or `defer` and give a nonempty
`reason`. Preserve the report kind; submission checks it against the captured
report bytes and session identities. This is required even for a partial report
that has declared one of these kinds, and remains separate from accepting its
findings. For other kinds, unset kinds or invalid declarations, omit `follow_up`
or set it to null; custody gaps still need their own dispositions. Status,
retention and resume revalidate the same response against the same collection.

Accepting follow-up records a manager decision, not that evidence has been
supplied or an audit commissioned. Changed inputs, scope or questions require a
fresh pinned assignment with its own grants. There is no automatic continuation,
producer run, scope expansion, or release of a paused hold.

## Failure and interruption recovery

- **Preparation failure after session creation** exits 2 with reason
  `prepare_failed`, retained paths and recovery steps. `PREPARE-ERROR.json`
  records the failed stage (`retention`, `worktree`, `role`, `inputs`,
  `runtime` or `handoff`), whether Git worktree creation completed, and whether
  a partial checkout exists. A never-created checkout is not reported as lost,
  and records a later stage would have written (retention refs, runtime
  records) are reported as never written, not as missing. Correct the cause
  (including write authorization for Git administration or the checkout home).
  No in-place retry is supported. Retire the session with
  `close --abandon --reason TEXT`: when the failure came before any handoff and
  the checkout holds only preparation's footprint, the audit ID is released and
  the same assignment may be prepared again. Otherwise use a fresh audit ID and
  prompt-only commit. No failure releases a recorded writer hold.
- **A checkout home the manager cannot write** is refused with
  `manager_grant_missing` before any session exists, naming the location; the
  audit ID is not used.
- **Preparation status** distinguishes `ready`, `failed`, `incomplete` (no
  launch handoff, or a handoff that differs from its pin), and
  `worktree_missing` (handoff exists, checkout is gone). It observes records
  and paths, never an auditor process. An interrupted preparation without a
  failure receipt is `preparation_incomplete` (1); a changed handoff is
  `handoff_changed` (3). Failed or incomplete preparation offers
  `close --abandon` and an `init` draft command with the pinned input
  selection; the manager must choose the new ID, scope, scratch paths and
  grant. Status does not write a replacement prompt or repair the old session.
- **Lost session records.** When a registered session's directory is missing,
  targeted `status`, `init` and `prepare` refuse the ID with
  `session_records_missing`, naming the registry row and refs. Preserve them,
  or retire what the row names with `close --abandon`; the ID stays reserved.
- **The owning maintainer checkout is gone.** A session prepared from a linked
  maintainer worktree that was later removed is refused with
  `session_owner_missing`. Recreate the worktree at the recorded path
  (`git worktree add <path>`), which restores its administration's name, then
  rerun from it, or abandon the session from another maintainer checkout of
  the repository.
- **Interrupted or blocked auditor.** Stop it, then collect. A partial report
  and unexpected changes are evidence; collection records them.
- **Collection with errors** exits 1, or 3 when an error means something does
  not verify (a changed handoff or supplied runtime, invalid retention, an
  archive mismatch, a checkout whose `.git` is not its own gitdir file, which
  Git is never run through), and keeps everything it captured: the
  report, the inventory, any patches and archive, and the worktree. Read the
  receipt's `errors`, resolve the cause (an unsupported entry, a moving file,
  broken Git state), and collect again. Never extract the archive over a checkout.
- **Movement during collection** is recorded with both inventories retained;
  no full-capture claim (`archive_sha256`) is made.
- **A partial attempt** (a collection directory with `STARTED.json` and no
  `collection.json`) is visible in `status` and cannot be triaged.
- **Invalid or unreadable receipts** remain distinct from missing receipts.
  Status keeps the record's reason and recovery location in JSON and human
  output without calling an existing corrupt collection partial or an existing
  corrupt attempt unresolved. Preserve those records; status never repairs them.
- **Cancellation** is a triage whose decision says so. In paused mode it can
  release the hold after a failed collection; the errors stay in the records.
- **Unsupported session schema.** A session written by another version is
  refused with its path retained; it is never rewritten.
- **Lost or changed supplied runtime.** `recover-runtime --audit-id ID --actor NAME`
  verifies the session's private pristine archive and manifest, then materializes
  them at a fresh `runtime-recovered-<name>/` in the session's checkout
  directory and captures that result in the session's `runtime-recoveries/<name>/`. It never overwrites the original runtime or
  retargets session commands, access scopes or releases. This restores assets
  for inspection; execution requires a separately authorized fresh assignment.
  Missing or damaged private assets cause a retained failure, without using the
  exposed copy or the current installation as a substitute. Status verifies
  recovery captures even after their materialized directory is removed.
  To use recovered code for a fresh assignment, explicitly select its bootstrap
  as the manager source, with a fresh private manager cache:
  `<python> -I -B <recovered-root>/stewart/_bootstrap.py source --manager-home <fresh-cache> -- --repo <project> --workspace <workspace> init ...`.
  Use that same source for the fresh assignment's subsequent manager commands.
  Recovery does not activate this selection automatically.
- **Nothing is removed automatically.** `close` is the only deletion. It
  removes only what the session recorded and, under claims it writes and
  revalidates at use, the managed resources whose last live use it ends, and
  only after writing its closing record. A concluded close refuses a checkout changed since the triaged
  collection; an abandon refuses uncollected changes unless told to discard
  them. Do not remove a checkout by hand: its lifetime lock makes Git refuse,
  and a checkout removed before any complete collection takes its evidence
  with it.

## Recorded resources and closeout

Audit work depends on more than its session: manager worktrees and branches,
temporary directories, exported packages and retained deliverables. Stewart
records them under `stewart/resources/<resource-id>/`, at repository level, so
a resource's records outlive every audit that used it.

### Creation, enrollment and uses

```sh
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review resource create-worktree --audit-id ID --path /absolute/manager-tree --branch audit/ID --actor manager
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review resource create-directory --audit-id ID --path /absolute/scratch-dir --actor manager
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review resource enroll --audit-id ID --kind worktree --path /absolute/existing-tree --actor manager
```

Managed creation is the only route to removal eligibility. `create-worktree`
(with `--branch NEW` for a new managed branch, `--existing-branch NAME` to
borrow one, or neither for a detached worktree), `create-branch` and
`create-directory` record `CREATE.json` (the audit context and intended
identity) before any side effect and `CREATED.json` (the observed identity, or
the failure) after. Under a request key, the resource identity is planned with
the request before anything is written for it, so an interrupted keyed creation
is `partial` (inspect it) rather than `reserved`, and a retry never allocates a
second resource for the same key. An interrupted creation leaves a start record without an
outcome, and a failed one records its failure: either is reported with what is
observed at its intended location, and grants nothing over whatever is found
there. Remove what is there by hand if it is not wanted, then acknowledge it. A
managed worktree is created locked (`stewart managed worktree <id>`) and marked
by `stewart-resource.json` in its Git administration; it must lie outside the
Git common directory, checkout homes, the manager home and registered auditor
checkout directories, recorded checkout homes and the running manager home.
A `--path` must be absolute (`resource_location`) and spelled canonically
(`path_noncanonical`).
A borrowed branch never becomes removal-eligible. An audit that is closed (or
whose lifetime is closing) takes no new resource or use (`audit_closed`).
`export` and `retain` record their package and published files as `export` and
`retained` resources: deliberate retention.

`resource enroll` tracks an externally created worktree, branch or directory
from verified observations (`ENROLLED.json`) for association and explanation
only. Even an unchanged identity and contents with an enrollment
acknowledgment grant no removal: enrolled resources are retired by hand and
acknowledged. `resource associate --resource ID` records that another audit
uses a resource. Stewart also derives uses: a live session or draft whose owner
checkout, checkout home or directory, helper interpreter, recorded invocation or
supplied runtime lies inside a worktree or directory resource uses it, and the
users of a managed worktree use the branch created with it. A use ends only
when a closing record verifies for its lifetime (closing or closed); a use
recorded before any session ends with the next closing record of that audit.
A closing record that does not verify, or a session record that cannot be
read, keeps uses live. Creation and recorded resources join the private roots
of later auditor scopes. `resource show --resource ID` prints one resource's
records, uses and disposition; `discover` lists them all.

### Closeout

```sh
"$STEWART_PYTHON" -I -m stewart --ref audit-ref.json close --plan
"$STEWART_PYTHON" -I -m stewart --ref audit-ref.json close --actor manager --dispose EXPORT-ID
```

`close --plan` prints the closeout description (`stewart.closeout/1`) and
writes nothing. It runs the close's own read-only checks for the mode given
(`--abandon`, `--reason`, `--discard-uncollected`, `--collection`, `--lifetime`), so the
refusal it reports is the one that close would raise now: a concluded close of
a draft or closed audit (`session_missing`), an abandon over uncollected changes
(`uncollected_changes`), a concluded close before triage, or `--reason` or
`--discard-uncollected` without `--abandon` (`usage`). Planning requires neither
an actor nor an abandonment rationale. It exits with that
refusal's code, 1 when a resource would stay blocked or missing, and 0
otherwise. It separates audit closure (the session's own inventory and the
refusal, if any), the retirement of working
resources around it, and retained historical evidence (closing records, request
records, retained deliverables). Each resource the audit uses is `remove`
(proposed), `shared` (named live users), `manual` (enrolled), `retained`,
`blocked` (with every reason), `claimed`, `missing`, `acknowledged` or
`retired`.

A close publishes `CLOSING.json` first, which ends the audit lifetime's uses.
After removing the session's own items, and only in its first attempt, it
evaluates the resources it used and claims each one whose every other use has
ended and that passes eligibility (a resumed close retires only the claims its
first attempt made; anything else is left for `close --resource`):

- its creation was recorded by Stewart and its identity still verifies, through
  real directories reached without links (a directory is the same device and
  inode it was created as), with no other filesystem mounted inside;
- a worktree's status is clean, ignored paths included, except paths of
  recorded exports or retained deliverables named with `--dispose`; its HEAD is
  its creation commit or contained in a ref outside `refs/stewart/` and outside
  the branches retiring in the same close; it holds no per-worktree refs and no
  rebase, merge, cherry-pick, revert or bisect;
- a branch's tip is its creation commit or contained in another ref that is not
  retiring in the same close, and no remaining worktree checks it out;
- no checkout that Git or the role registry places inside it remains, other
  than worktrees retiring with it and the closing audit's own checkout;
- every recorded resource inside it retires with it: a worktree or directory
  inside is retired first (deepest first), a recorded export or retained
  deliverable inside needs a durable destination or a `--dispose` decision
  (a retained file committed in a retiring worktree is history and retires with
  it), and the running Stewart package or interpreter is not inside it;
- a disposed or contained export or retained deliverable has no other live use,
  no claim of its own in progress and records that verify: a disposal decision
  never overrides another audit's use. This is checked when the close evaluates
  and again at use, and associating a resource that lies inside one being
  retired is refused (`resource_retiring`).

Containment never drops a resource because its outcome cannot be read. A
readable creation start's intended paths can establish that it might be inside
a container, but grant no authority to dispose of it. Missing, failed or invalid
outcomes keep that container; a reliable intended location outside it does not
block unrelated retirement. When neither verified identity nor readable intended
locations can locate a resource, every worktree or directory container is kept
with a diagnostic naming the uncertain record. The same check runs again before
removal. Invalid retirement endings or acknowledgments do not exclude a resource
from these checks. Preserve the records for inspection; Stewart never rewrites
them to make retirement possible.

The set that retires together is found by elimination: every managed temporary
resource starts in it, and one that is not removable alongside the rest leaves
it, until nothing more leaves. A resource that would be removable only because
another one stays is kept and explained.

A claim is `resources/<id>/claims/<n>.json`, created exclusively, with the
frozen identity, the complete contents inventory (every entry with its kind,
and each file's size and digest), HEAD or tip and any disposal decisions, all
taken from the evaluation that judged it removable. At most one claim is
active, and none is created once a resource is retired; two closes racing for
one resource cannot both claim it. The close then retires its claims, deepest
paths first and branches last. At use it revalidates every use, the identity,
the full inventory, HEAD and tip, re-runs the worktree checks, and refuses a
checkout registered inside since; any change, or a use that appeared since,
ends the claim with `<n>.RELEASED.json` and keeps the resource. A claim whose
removal already started (it has an attempt record) accepts only the entries it
froze, minus what was already removed, and finishes an already-absent path by
dropping its administration, whose resource marker is removed last so an
interrupted removal is found again; a worktree is not retired while Git still
registers it. A container's frozen entries may also disappear below resources
retired first inside it in the same close, and nowhere else. Removal goes through descriptors pinned without
following links, removes only the directory with the frozen device and inode,
never crosses into another filesystem, lets Git delete no contents, removes a
worktree's marker-verified administration by descriptor, and deletes a branch
only if it still points at the frozen tip. Git runs from the common directory,
so a close can retire the manager worktree it was run against. Every removal
attempt first writes `<n>.ATTEMPT-<stamp>.json`, before its first removal step,
so a retirement interrupted anywhere, a killed process included, resumes as its
own partial removal. Success writes `<n>.RETIRED.json`; a caught failure adds
`<n>.ATTEMPT-<stamp>.FAILED.json` and keeps the claim active (a keyed close then
stays `partial`). The audit close
completes once its session items are gone; a resource left blocked or missing
makes its exit 1.

`close --resource ID --actor NAME` retires a recorded resource that no live use
holds, under the same discipline: it records its claim first, freezes the
identity, revalidates at use, and resumes an active claim (including one an
audit close left unfinished) without widening it. Resources named together are
evaluated as retiring together. It refuses enrolled or retained resources with
`resource_not_managed`, retired or acknowledged ones with `resource_retired`,
and shared or blocked ones with `resource_shared` or `resource_blocked`; an
active claim written by another build is refused with `implementation_mismatch`
and a handoff to `resource show`. Closed audits' records are never
reopened. A resource left behind (blocked at the last close, or in use while
other closes were planned) is retired this way once its blocker is cleared.
While a claim is active, `prepare`, `init`, `register`, `resource associate` and
creation inside the resource are refused with `resource_retiring`.

An export placed inside a retiring tree needs a durable destination or a
disposal decision: `export --output /absolute/new-directory` writes the package
outside the maintainer checkout, and `close --dispose ID` records the decision
to remove a contained export or retained deliverable with its container. A
retained report committed to a branch that is merged elsewhere is already
history and blocks nothing.

### Manual retirement acknowledgment

```sh
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" resource acknowledge --resource ID --actor manager --note "removed by hand after review"
```

A recorded resource that is gone is reported `missing`. `resource acknowledge`
revalidates its absence now (a worktree also needs its Git registration gone)
and records `ACKNOWLEDGED.json`. A managed worktree is locked, so retiring one
by hand needs `git worktree remove -f -f <path>` (or `git worktree unlock`
then removal); a worktree directory deleted without Git leaves its registration
until `git worktree prune` after unlocking. The acknowledgment records the observed absence and the manager's
acknowledgment in separate fields, bound to the resource record's digest.
Interrupted and failed creations are acknowledged the same way once their
intended location is empty. It
is refused while the resource is present (`resource_present`) or claimed. The
creation or enrollment record is never edited. An acknowledgment grants nothing
and claims nothing about how the resource was removed; anything found later at
its location is a new observation, not the retired resource.

## Handing captured evidence to another assignment

`export` selects exact captured bytes and keeps their source receipt in a new
package. It neither reads the live auditor checkout nor requires accepting its
claims. The manager chooses every file and the receiving question. For example,
export a construction report and a captured script, then draft a fresh assignment:

```sh
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review export --audit-id one-bounded-question --collection 20260101T120000-0a1b2c3d --select REPORT.md --select files.tar:audits/parser-review/scratch/one-bounded-question/artifacts/experiment.py --output audit-packages/construction-package --actor "manager"
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review init --audit-id independent-review --input path/to/reference.py --evidence-package audit-packages/construction-package/manifest.json
"$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review export --audit-id one-bounded-question --attempt 20260101T130000-9c8d7e6f --select ATTEMPT.json --select ledger.jsonl --select stdout.txt --output audit-packages/measurement-package --actor "manager"
```

Collection selectors are `REPORT.md` and `files.tar:<repo-relative-path>`.
Attempt selectors are `ATTEMPT.json`, `ledger.jsonl`, `child-receipt.json`,
`stdout.txt`, and `stderr.txt`. An unresolved attempt has no completed receipt to
export. Unavailable or changed captures are refused. A verified report can still
be selected from a collection whose archive is incomplete. Archive members must
be unique regular files; nothing is extracted over a checkout.

Both source kinds also accept `runtime-assets`, which selects the complete
pristine manifest/archive pair, and `runtime-observation:<phase>`, which selects
the complete captured receipt, before/after inventories and archive. The phase
is `collection` for a collection or `before`/`after` for an attempt. For example,
add `--select runtime-assets --select runtime-observation:collection` to a
collection export to preserve expected code and independently observed damage.
Each selected group is complete and verified against its source receipt;
imports do not need the source session, exposed runtime or worktree. A partial
group is refused, and importing code grants no permission to execute it.

`--output` names a directory of the manager's choosing in the maintainer
checkout, such as `audit-packages/` above; keep it uncommitted, for example
under a path the project ignores. An absolute `--output` names a durable
destination outside the checkout instead, for a package that must survive the
retirement of a manager worktree. The output directory must be new and its parent must exist.
Each package is recorded as an `export` resource. Publication is
exclusive, with `manifest.json` written last. Partial failure retains its output
and requires a fresh directory. The `stewart.evidence-package/5` manifest records
the selecting actor, source workspace/audit/record and receipt SHA-256, the
exporting tool's `stewart` identity, the supplied runtime identity and pristine
asset pins, and each
selected file's selector, package path, size and digest. `source.json` is the
exact source receipt; `files/` contains only selected payloads. Numeric filenames
preserve suffixes; the manifest provides the mapping to original paths.

`init --evidence-package` verifies source identity and payload bindings, then
pins the manifest, source receipt and every payload as supplemental inputs. Each
input has a structured `custody` reference (`package`, `manifest_sha256`, `member`)
alongside its path, digest and provenance. Preparation rechecks the complete set
and copies it at the same repo-relative paths into the receiving worktree. The
original session is not required for import. The manifest byte digest is pinned,
so even harmless edits after initialization require a fresh draft. Ordinary
`--supplemental PATH PROVENANCE` remains available for independently selected
files without package custody.

This establishes recorded custody and byte identity, not authenticated authorship,
reference independence, permission to execute a captured script, or acceptance
of a report. Author the receiving assignment and any execution grant separately.

## Optional experiment lifecycle

Ordinary static audits need none of this. Construction permission and execution
permission stay distinct, and the tool never certifies more than the named
endpoint property.

1. **Grant in the assignment.** The committed prompt's assignment block carries
   one optional `experiment` object beside the prose authorization section the
   auditor reads. The tool validates the object's shape and containment, never
   the prose, and never reconciles the two.

   ```json
   "experiment": {
     "schema": "stewart.experiment-grant/2",
     "permission": "construction+execution",
     "script": "audits/parser-review/scratch/one-bounded-question/artifacts/experiment.py",
     "freeze": ["audits/parser-review/scratch/one-bounded-question/artifacts/prediction.md"],
     "output_area": "audits/parser-review/scratch/one-bounded-question/run",
     "protected_manifest": "evidence/protected-source.json",
     "interpreter": "repo-venv",
     "environment": "minimal",
     "cwd": "worktree",
     "argv_template": ["{interpreter}", "-B", "{script}", "--root", "{root}", "--manifest", "{manifest}", "--output", "{output}"],
     "invocations": 1
   }
   ```

   `script`, `freeze` entries and `output_area` must sit under declared scratch
   paths, and frozen artifacts must not live inside the child-writable output
   area. `protected_manifest` is a pinned input that maps repo-relative paths
   to SHA-256 digests under `files`. `interpreter` is a policy name:
   `repo-venv` resolves to the maintainer checkout's `.venv/bin/python`,
   `tool-interpreter` to the interpreter running the tool. `environment` is
   `minimal`: PATH and locale, with HOME at `attempts/<name>/home` in the
   session's checkout directory, outside the worktree. The launcher uses
   `-I -B` and a fresh private cache prefix. The only supported command prefixes
   are `[{interpreter}, {script}, ...]` and `[{interpreter}, -B, {script}, ...]`,
   with each element a separate string token. After the script, literal arguments
   and whole-token `{root}`, `{manifest}`, `{output}` substitutions keep their
   order. Interpreter/script placeholders cannot repeat. Shell wrappers, `-c`,
   `-m` and other interpreter flags are refused with `child_argv` before release.
   `invocations` is 1. Pass the versioned object with `init --experiment-grant
   FILE` to inline it into the draft.

2. **Construct.** The auditor writes the script, predictions and declarations
   into the scratch area and stops. Nothing runs.

3. **Release.** The manager reviews the exact bytes and records the review:
   cases with population (`ordinary` or `control`), role, expected admission
   and prediction, plus a `measurements` list of unique nonempty IDs;
   admissibility reasoning; static review statements; limits. Admitted cases
   require at least one measurement ID; planned refusals require an empty list.
   The tool verifies the declaration exists, not that it is right. Release
   freezes the script, the `freeze` list and the protected manifest in the
   worktree. It independently observes the supplied runtime and binds its ledger
   digest and reserved import name, plus a retained manager-owned launcher.
   It records both `approved_argv` (the expanded script command) and `argv`
   (the effective isolated launcher command), the interpreter and ordered project
   import paths. The output area must not exist. Before freezing anything it
   compares every pinned input, including the manifest, to preparation's input
   receipt. Protected files must match that pinned manifest. Rewriting both a
   source and its manifest cannot establish a new baseline; an intentional
   baseline change needs a fresh assignment.

   CLI review files require unique object keys at every nesting level. Repeated
   keys are refused with `duplicate_input_key` before a release is written,
   including identical repeats and names made equal by JSON escape decoding.
   The same rule applies to `init --experiment-grant` and `triage --response`:
   authorizing commands must not silently choose the last of competing fields.
   Whitespace and the order of unique keys do not affect this rule. Repeated
   measurement IDs inside an array are a separate review-schema error.

   A release records the validated decoded review, not the original review-file
   bytes. Preserve those bytes separately when their provenance matters. Callable
   API callers supply already-decoded dictionaries and own the decoding boundary;
   the API cannot recover repeated keys that a caller has already discarded.
   Raw child JSONL remains captured before its documented last-key decoding;
   manager-input refusal does not change that evidence acquisition behavior.

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review release --audit-id one-bounded-question --review review.json --actor "maintainer"
   ```

4. **Run once.** Each release authorizes exactly one invocation. `run`
   re-validates every frozen digest, pinned input and the grant, reserves the attempt
   directory exclusively (so a concurrent call is refused), hashes the
   protected files and compares them to the manifest, creates the output area
   and the attempt `HOME` in the checkout directory, launches the child in its
   own process group with the recorded argv, cwd and environment, captures
   stdout and stderr, hashes the protected files again, and reads the child's
   receipt and ledger rows through verified regular-file descriptors. The exact
   bytes parsed are retained under the attempt with their SHA-256 digests. A
   special output is recorded as unavailable without blocking; other readable
   outputs and process evidence are still retained. The timeout governs the
   child process, not total custody-operation duration.

   ```sh
   "$STEWART_PYTHON" -I -m stewart --repo "$PWD" --workspace audits/parser-review run --audit-id one-bounded-question --release 20260101T130000-9c8d7e6f --timeout 600
   ```

   The child finds its output area already present and empty; a script that
   requires the directory to be absent fails on entry and spends the invocation.
   The attempt record's `output_area` says the wrapper created it. The child's
   `receipt.json` has no schema beyond being one JSON document: the wrapper
   records its keys and digest, retains the bytes, and reports a missing,
   unreadable or malformed receipt as an attempt error. A manager reviewing a
   constructed script before release should check both points; a rehearsal
   found a script that would have crashed on the first.

   A changed frozen artifact, grant, worktree HEAD, protected file or output
   area refuses the launch; the reservation is still resolved so it is not
   mistaken for a crash. A child that fails, times out, tampers with protected
   state or writes a malformed receipt completes the attempt with recorded
   errors (exit 1); a supplied runtime that stopped verifying across the
   attempt exits 3. The child's own exit status never becomes the tool's. Another attempt needs a new release, and a new release
   needs the output area absent: a failed attempt leaves it in the worktree on
   purpose, because its contents are evidence until a collection has captured
   them. Collect, verify the attempt's retained copies, then move or remove the
   directory by hand, or assign a fresh audit ID whose grant names another
   output area. Stewart itself removes it only when `close` removes the whole
   checkout. A changed launched assignment always needs a fresh audit ID and
   prompt-only commit.

5. **Ledger.** The child uses `from _stewart_ledger_v1 import Ledger`. The
   manager-owned launcher reads and loads the pinned standard-library-only
   ledger before admitting project imports; the project need not contain
   Stewart. It then inserts the script directory followed by the worktree root,
   preserving legitimate project `tools`, `stewart` and sibling imports for
   names not already loaded by startup. Standard-library modules used by the
   bootstrap and ledger (for example `json`) remain loaded; a sibling `json.py`
   does not replace them. This is not full import equivalence to plain script
   startup. It
   refuses the reserved `_stewart_ledger_v1` basename or any dotted suffix in
   either directory, including packages, bytecode and native modules; release,
   prelaunch and child startup each check. An unexpectedly preloaded reserved
   module is refused too. This pins initial loading, not a child's later changes
   to its own imports. The reserved module is supplied only in the initial
   process. A subprocess or `multiprocessing` spawn worker cannot import it
   automatically. Keep ledger imports and writes in the initial process; for
   spawn-based workers, put the ledger import under the
   `if __name__ == "__main__":` guard and return worker results to that process.

   The child retains its script-token `sys.argv[0]`, absolute `__file__`,
   script-mode `__main__` and worktree cwd. Child exceptions, exit codes, signals
   and process-group timeouts remain child outcomes, not startup refusals.
   The ledger declares cases, records reach and admission, and
   routes every comparison, ordinary or control, through one `compare` call
   that appends a JSONL row. The wrapper derives per-population counts
   (declared, reached, admitted, refused, compared, mismatches) from the rows
   it retains and lists unmet prerequisites: no ordinary or control cases, a
   control never reached, no disagreement among counted control comparisons, admission
   that differed from its declaration, comparisons made while a case was not
   admitted, undeclared cases. The firing check uses the control population's
   aggregate: one disagreement satisfies it, even when another control agrees.
   Managers use `ledger.mismatching_cases` and the captured operands to assess
   each control's prediction and relevance. A planned refusal is not a mismatch.
   A matched row count or an observed
   nonzero does not establish control relevance, reference independence or
   universal correctness; those are triage decisions.

   The wrapper validates row fields and event order, recomputes disagreements
   from the recorded operands, and checks declarations against the released
   review's case IDs, populations, roles, expected admissions, predictions and
   measurement IDs (measurement order is ignored).
   Each case must be declared, reached and given one admission outcome, in that
   order. Admitted cases require comparisons; planned refusals require none.
   Each reviewed measurement must appear exactly once for its admitted case.
   Omitted, duplicate and unexpected measurement IDs are listed separately in
   `ledger.anomalies`, even if the total row count or case count looks right.
   The cases whose comparisons disagreed are listed per population in
   `ledger.mismatching_cases`, beside the anomalies rather than among them: a
   fired control is the expected outcome.
   Only expected measurements occurring once contribute to comparison and
   disagreement counts. Missing reviewed cases,
   duplicate declarations or admissions, inconsistent mismatch flags and
   malformed rows leave prerequisites unmet. Unadmitted comparisons are excluded
   from numeric counts. Operands still come from the child; internal consistency
   does not establish the truth of those measurements.

   Comparison operands must be JSON values. Object key order and row notes are
   ignored; array order matters; booleans differ from numbers; finite numbers
   compare numerically (`1` equals `1.0`). Nonfinite numbers and other Python
   types are refused. `parse_rows(bytes)` parses captured UTF-8 JSONL without
   opening paths; `summarize(rows, cases=review["cases"])` verifies it against a
   release review. Standalone `summarize(rows)` checks only the child-declared
   population and must not be presented as verification of a released review.

   Direct callers must preserve both values returned by `parse_rows`: accepted
   rows and parsing problems. `summarize` sees only the rows passed to it; the
   wrapper separately records parsing problems in `ledger.malformed` and adds
   them to `ledger.unmet`. It also validates the review before release, refusing
   duplicate case IDs or measurement IDs. A direct `summarize` call assumes that
   review validation has already happened.

   JSONL decoding uses Python's JSON parser: repeated object keys keep their
   last value and do not produce a parsing problem. Key-order invariance applies
   to objects with unique keys; reversing repeated keys can change a decoded
   measurement ID or operand. Retained raw bytes preserve this distinction,
   but an empty parsing-problem list does not establish unique object keys.

   A case in the release review might be:

   ```json
   {"id": "ordinary-a", "population": "ordinary", "role": "comparison modes", "expected_admission": true, "prediction": "agree", "measurements": ["canonical", "strict"]}
   ```

   The child records the corresponding measurement identities explicitly:

   ```python
   ledger.declare("ordinary-a", population="ordinary", role="comparison modes",
                  expected_admission=True, prediction="agree", measurements=["canonical", "strict"])
   ledger.reach("ordinary-a")
   ledger.admit("ordinary-a", True)
   ledger.compare("ordinary-a", "canonical", expected_canonical, actual_canonical)
   ledger.compare("ordinary-a", "strict", expected_strict, actual_strict)
   ```

`status.experiment.state` separates `not_granted`, `construction_only`,
`awaiting_review`, `released`, `attempt_recorded`, `attempt_unresolved` and
`records_invalid`. An execution grant awaiting review remains visible after a
construction report is triaged or retained. `attempt_unresolved` means a reserved
attempt has no completed receipt. For an execution grant, invalid, unreadable,
foreign or unsupported release/attempt records produce `records_invalid`, which
takes precedence over healthy releases and missing attempt receipts. Individual
records keep their diagnostics, and usable sibling releases remain visible. Failed release reads
do not produce capture associations or run suggestions; inspecting them still
returns the status view, with exit 3 for the records that do not verify. A release suggestion appears only
once a complete collection exists, and requires the manager to assess artifact
readiness, reference independence, controls and measurement IDs. Each release
in `status` names the collections whose verified captured bytes equal its frozen
script, declarations and manifest. Artifacts without a verified matching capture
are listed as outstanding; status cannot establish whether another copy survives.
Separate collections may each hold part of a release without any one collection
appearing in `captured_in`. Verification is at read time, not a promise that later
export will succeed after files change. These states describe recorded operations
and authorization; they never certify
readiness or scientific success. A recorded attempt may have process errors or
unmet measurement prerequisites; inspect its separate fields.

The ledger module is part of the frozen instrument identity, so experiments
serve targets at or after the commit that landed it. Endpoint equality
establishes that the named protected files were byte-identical at launch and
after exit, and nothing about the interval, imports, in-process activity or
external effects. The wrapper stops the child's process group on timeout or
interruption and does not claim that every descendant or external effect was
contained.

## Records and what they mean

Session records live in `<git-common-dir>/stewart/sessions/<slug>/<audit-id>/`;
closing records under `<git-common-dir>/stewart/closed/`.

| Record | Meaning |
| --- | --- |
| `session.json` (schema 12) | Assignment, workspace, prompt and target commits, digests, launch token, declaration schema, mode, pause acknowledgment and note, maintainer status at preparation, session UUID and durable retention refs, the checkout home, the session's checkout directory and worktree, the supplied runtime and pristine asset pins, the public handoff digest, the auditor access scope, and the pinned launch profile when the workspace has one. |
| `LAUNCH.md` | Private copy of the pinned handoff; the issued auditor path is the copy at `<workspace>/.stewart-handoffs/<session-uuid>.md` in the worktree. |
| `runtime-pristine/`, `runtime-prepared/`, `RUNTIME-PREPARED.json` | Verified pristine assets and separately captured preparation observations of the exposed runtime. |
| `runtime-recoveries/<name>/STARTED.json`, `RECOVERY.json`, `runtime-recovery/` | An attributed fresh materialization of private pristine assets, its source session digest and independent capture; failures remain recorded. Existing session commands and grants are unchanged. |
| `HARNESS-EXIT.txt` | One `exit timestamp` line per run of the printed launch block, appended by the block itself when the harness ends. Not a Stewart receipt: the shell writes it. |
| `launches/<name>.json` | The manager's acknowledgment of one handoff: style, model, effort, note, actor, bound to the launch token; from a profile, also the harness, the pinned and any override profile digests, and the rendered command. |
| `messages/<name>.json` | One message exchanged with the auditor after launch, as the manager relays it, with direction and channel. |
| `PREPARE-ERROR.json` | Failed preparation stage, original reason, worktree creation outcome and existence; any partial worktree is retained until `close`. |
| `collections/<name>/STARTED.json` | A collection began; without `collection.json` it is a partial attempt. |
| `collections/<name>/REPORT.md` | The captured report bytes, taken before Git work. |
| `collections/<name>/inventory.json` | The no-follow inventory taken before Git discovery; `inventory-after.json` appears only on movement. |
| `collections/<name>/working.patch`, `index.patch`, `status.z`, `files.tar` | Git patches against the prompt commit, porcelain status, and the archive of Git-reported files and links. |
| `collections/<name>/collection.json` (schema 7) | Report status and digest, captured declaration validation and identity comparisons, Git discovery outcome, archive digest, unexpected paths (naming those that are supplemental inputs) and missing supplemental inputs, inventory summary and digest, supplied runtime observation and pristine asset pins, errors as reason/message objects, attributed stop kind. |
| `triage/<name>.json` (schema 3) | A maintainer response carrying and validating the collection name and receipt digest, report digest or gap, and any kind-bound follow-up disposition. Earlier disposition schemas are unsupported and preserved unchanged; use their pinned tool version. |
| `retention/<name>.json` | What was published, from which capture, with digests. |
| `RESUMED.json` | The release of a paused hold, bound to a triage. |
| `releases/<name>.json` (schema 5) | The manager's review, including per-case measurement IDs, plus frozen digests, resolved interpreter, environment, approved/effective argv, ordered import paths, pinned ledger and private launcher, and destinations; consumed once its attempt directory exists. |
| `attempts/<name>/RESERVED.json` | The attempt was reserved; without `ATTEMPT.json` it is unresolved and never reusable. |
| `attempts/<name>/ATTEMPT.json` (schema 8), `stdout.txt`, `stderr.txt` | Prompt and target commits, launch outcome, raw exit or signal, endpoint comparison, supplied runtime observations and pristine asset pins, output-area creation, output capture paths and digests (including streams), measurement verification with mismatching cases beside anomalies, and errors, with process output beside them. Historical attempts require the version that wrote them. |
| `attempts/<name>/ledger.jsonl`, `child-receipt.json` | Exact readable child output bytes used by the wrapper; created exclusively. Unavailable outputs leave an explicit capture observation instead. |
| `closed/<slug>/<audit-id>/<uuid>/CLOSING.json` (`stewart.closing/1`) | Written before `close` removes anything: identity (session UUID, workspace, audit ID, commits, `session.json` digest, prepared and closed times, tool), the acknowledgment (actor, mode, abandon reason), observations (triage and collection digests, retained paths and digests, discarded paths and digests, an abandon's stage, problems and release basis, coordination mode), attributed claims (the manager's decision, the auditor's completion and report kind) and the removal inventory. Never removed. |
| `closed/<slug>/<audit-id>/<uuid>/CLOSED.json` (`stewart.closed/1`), `CLOSE-ATTEMPT-<stamp>.json` | Each removal's outcome and the unrecorded entries left in place, bound to `CLOSING.json`'s digest. `CLOSED.json` is written only once nothing recorded remains; an attempt that stopped partway writes `CLOSE-ATTEMPT-*`. |
| `audits/<slug>/<audit-id>/init/<name>/STARTED.json`, `OUTCOME.json` (`stewart.draft/1`) | A mutating `init`'s intended writes and their digests, recorded before writing, and what was written or why it failed. Without an outcome the init was interrupted. |
| `audits/<slug>/<audit-id>/registrations/<name>.json` (`stewart.registration/1`) | Present observations of an existing workspace's guidance and prompt, attributed to the registering actor; implies no earlier custody. |
| `requests/<sha256>/REQUEST.json`, `attempts/*.json`, `OUTCOME.json` | A request key's exclusive binding (`stewart.request-binding/1`, with the exact key and invoking checkout), the output identities planned before each side effect, and the recorded completion or refusal with output identities. Never removed by close. |
| `resources/<id>/CREATE.json`, `CREATED.json` (`stewart.resource/1`, `stewart.resource-outcome/1`) | A managed resource's audit context, intended identity and intended disposition (`temporary`, or `retained` for exports and retained deliverables), recorded before its side effects, and the observed identity or failure after. A Stewart-recorded creation is necessary for removal eligibility, never sufficient. |
| `resources/<id>/ENROLLED.json` | An externally created resource's observed identity and enrollment acknowledgment, with disposition `manual`; never removal-eligible. |
| `resources/<id>/associations/<name>.json` | An audit context that uses the resource; the use ends with that lifetime's closing record. |
| `resources/<id>/claims/<n>.json`, `<n>.RETIRED.json`, `<n>.RELEASED.json`, `<n>.ATTEMPT-<stamp>.json`, `<n>.ATTEMPT-<stamp>.FAILED.json` | The exclusive claim of one close (frozen identity, complete contents inventory, HEAD or tip, disposal decisions, writer stamp), and how it ended: retired, or released with the observation that kept the resource. Each removal attempt is recorded before its first removal step; a caught failure is recorded beside it and leaves the claim active. |
| `resources/<id>/ACKNOWLEDGED.json` | The manager's acknowledgment of an observed absence as retirement outside Stewart, with the observation in its own field; grants nothing. |

Every record above except the raw captures carries `stewart`, the identity of
the tool build that wrote it: its distribution version, complete member
inventory and digest, and separate resource digests. Commit and dirty state are
optional source-checkout context; installed deployments do not borrow those
coordinates from their storage directory. Installed entrypoint scripts, the
interpreter, site-packages `.pth` files and `sitecustomize` are startup trust
roots outside this identity. It does not attest to in-memory code or host state. An evidence package manifest
(`stewart.evidence-package/5`) carries the same field.

`report_status` distinguishes `present`, `empty`, `missing`, `symlink`,
`unsupported` and `unassessed` (capture itself failed). `unexpected_paths`
lists Git-reported changes outside the report, declared scratch paths and
unchanged copied supplemental inputs and the unchanged supplied public handoff.
A missing, unreadable or changed public handoff is a custody gap even when Git
has no deletion to report. `maintainer_status_changed_since_prepare` compares HEAD
and porcelain status only: it cannot see an edit to an already-dirty file and
cannot certify that a pause was honored.

### Supplied runtime observations

A session's `runtime` is a required supplied identity. It names an absolute root, its complete sorted file
and directory manifest, its digest, and helper/ledger protocol versions.
Collection, release and attempt receipts bind that identity to separately
captured observations. These are manager observations; a helper's own checks
cannot attest to its bytes.

Each observation directory contains `STARTED.json`, `before.json`, `after.json`,
`files.tar`, and the final `capture.json`. The archive preserves all readable
regular files from the first observation, including unexpected packages and
bytecode. Links, missing entries, unreadable files and special entries remain
in the inventory as diagnostics; their targets are never read. The parent
receipt pins `capture.json`, which pins both inventories and the archive.
`matches_expected` compares the complete membership and bytes to preparation;
`movement` compares the two observations. Neither detects a transient change
restored between observations.

Release and execution refuse a runtime mismatch. Collection first preserves the
raw report, then records runtime damage as a custody gap. Triage, retention,
export and status verify the captured inventories, archive membership and bytes,
and their binding to preparation; those custody checks do not consult the current
runtime. Status separately observes the current exposed directory before
suggesting a new handoff or launch. Missing, changed, added, linked or unreadable
runtime entries withhold those suggestions while collection and asset recovery
remain available. This readiness observation does not establish future integrity.
A valid capture of damaged helper files remains evidence. An altered or missing
private capture refuses interpretation. If capture itself fails, its enclosing
receipt records an explicit failed phase and error. Independently preserved
report and child-output bytes remain usable for triage and export; that failed
phase cannot supply a complete runtime-observation export group. A missing
phase without a recorded failure remains malformed. Report-only export records runtime
identity too. The project worktree archive and supplied runtime archive are
separate evidence surfaces.

The shared bootstrap's `helper` mode permits only `inputs` and `declaration`.
It verifies the complete supplied inventory before importing either helper,
uses `-I -B` and a fresh private temporary cache prefix, and inserts no project
import paths. The helper verifies its explicit worktree, prompt commit, prompt
digest and token arguments without opening private session records. Its
self-check supplements the manager's observations; replacing the supplied
bootstrap does not replace the manager's independent verifier.

Pristine assets live separately in `runtime-pristine/manifest.json` and
`runtime-pristine/files.tar`. Their `stewart.runtime-assets/1` binding pins both
files. Readers verify the complete archive membership and every payload against
the manifest. Materialization creates a fresh directory through no-follow
descriptors and refuses an occupied destination. `RUNTIME-PREPARED.json` binds
the preparation observation; it is separate from later observations of the
exposed copy. Losing exposed files does not authorize using a newer installation
as their replacement.

The `claude-code-restricted/1` scope adapter combines restricted file tools with
a required shell sandbox. Its exact runtime subtree is read-only, the worktree
is writable, and `<git-common-dir>/stewart` (private receipts, role registry
and closing records), other sessions' checkout directories and the manager homes
remain read-denied. In the qualified harness a broader read denial wins over a
nested read grant, so a private root that contains a granted path, such as the
maintainer checkout containing its Git administration or an interpreter
environment inside the project, is denied entry by entry beside that path.
A literal denial cannot express an entry name holding `*`, `?`, `[`, `]`, `{`,
`}`, `(`, `)`, `\` or a line break; preparation refuses such an entry with
`scope_uncovered` before any session exists, so rename or move it. Scope
preparation snapshots all Git-registered checkout roots and the checkout
directories and session locations of retained role-registry rows, including
other maintainer checkouts, and excludes both the selected and default manager
home. Keep additional private caches under those excluded roots. The snapshot
cannot cover checkouts created or moved later, including those prepared later
for other audits, or entries added to the maintainer checkout later: finish them
before preparation, or stop the affected auditors and prepare fresh assignments
after the change.
Read-only Git administration and the selected
interpreter environment are separate supporting access paths. Search-only
ancestor descriptors permit reaching an allowed subtree without listing its
private parents. Harness configuration is distinct from the auditor's model,
role guidance and assignment permissions. The adapter's argv excludes settings,
directory, tool, MCP, resume and permission overrides supplied by the profile.
The harness executable, managed configuration and interpreter remain trust
roots. The profile does not sanitize the launching shell's inherited harness
environment, and a trusted executable must not be writable by the auditor.
Read access to common Git administration exposes all objects and refs in the
repository, including other branches and committed prompts. It is not a
confidentiality boundary between committed histories.
Shell sandboxing alone does not restrict file tools; the two controls
must be exercised together. See the [Claude Code sandbox boundary](https://code.claude.com/docs/en/sandboxing#what-runs-outside-the-sandbox).

### Custody gaps

A collection's custody gaps are derived from its receipt: each error,
non-present report, incomplete Git discovery, unexpected commit, unexpected
path, movement, omitted or unreadable or unsupported inventory entry, and
traversal boundary gets an ID, and so does each pinned supplemental input missing
from the checkout (`supplemental_missing:<path>`). Declaration errors, mismatched
or stale identities, and completion/stop discrepancies also get IDs. A triage
must disposition every one. Each gap carries its exit code (1 when the auditor
could fix it, 3 when nothing the auditor does can) and whether the auditor's
`check` observes it from the checkout alone.

## Coverage and limits

- Inventory coverage is every entry below the worktree root except its
  top-level Git administration. Classification and traversal use pinned
  directory descriptors with no-follow opens for every ancestor. Replacing a
  directory with a link cannot redirect traversal; lost directory identities
  are recorded as `replaced`. Regular files are read only through descriptors
  verified with `fstat`; no-follow and nonblocking opens guard late replacements.
  FIFOs, sockets and devices are never read. A nested `.git` is listed as a
  boundary and not traversed. These observations do not certify continuous
  pathname or byte stability between endpoints.
- The archive holds Git-reported regular files and links. Special entries are
  inventoried but not archived; a Git-reported entry that could not be archived
  appears under `omitted`.
- Preservation claims cover recorded file bytes and metadata only. Extended
  attributes, other mounts, shared caches, host services and transient effects
  are outside them. A successful Git command does not establish full coverage;
  the inventory does, within the boundaries it names.
- Acknowledgments are attributed to the maintainer's flags. `auditor stopped:
  acknowledged` is not an observed process exit. The validated reserved declaration records the auditor's completion claim,
  never a verdict. Prose status lines are not interpreted.
- Custody survives `git clean` and branch work in the maintainer checkout, but
  not removing or re-cloning the Git directory, deleting a checkout before
  `collect`, or a backup that skips `.git`. `close` is the only deletion
  Stewart performs; it removes only what its session recorded and the managed
  resources its claims froze, and keeps the closing record. Anything worth keeping beyond retained files must go through
  `export` before `close`.

## Python API

Import callables from `stewart.api`; names on `stewart` identify
submodules. The API resolves lazily and remains callable regardless of whether
the CLI or those submodules were imported first.

```python
from stewart.api import workspace, prepare, record_launch, collect, triage_draft, triage, retain, resume, status, export_evidence, close, StewartError

ws = workspace(repo_root, "audits/parser-review")
prepared = prepare(ws, prompt_commit, mode="snapshot")          # dict with session, worktree, launch
record_launch(ws, audit_id, style="terminal", model="opus", effort="max", actor="me")  # your acknowledgment, not an observation
collected = collect(ws, audit_id, auditor_stopped="finished")        # dict with collection name, path, receipt, gaps
response = triage_draft(ws, audit_id, collection=collected["collection"])["response"]  # review claims and fill every null
disposition = triage(ws, audit_id, collection=collected["collection"], response=response, actor="me")
retain(ws, audit_id, triage=disposition["triage"], report=True)
view = status(ws, audit_id)                                     # the same document as `status --json`
closed = close(ws, audit_id, actor="me")                         # keeps CLOSING.json/CLOSED.json; removes the session
```

Discovery, selection and keyed continuation use the same functions:

```python
from stewart.api import discover, select, bind, collect, close, inspect_request

found = discover(repo_root)                                      # stewart.discovery/1; writes nothing
reference = select(repo_root, audit_id="one-bounded-question")["reference"]   # keep it; it is plain JSON
bound = bind(reference)                                          # revalidates; bound.ws, bound.audit_id, bound.lifetime
collected = collect(bound.ws, bound.audit_id, auditor_stopped="finished", lifetime=bound.lifetime,
                    request_key="collect-7f3a")                  # a retry with the same key returns this collection
view = inspect_request(repo_root, "collect-7f3a")                 # stewart.request/1; never executes
```

Every mutation takes `request_key=` and every session operation `lifetime=`.
`register`, `create_worktree`, `create_branch`, `create_directory`, `enroll`,
`associate`, `acknowledge`, `show_resource`, `close_resources` (the API of
`close --resource`), `close_plan`, `closeout` and `runtime_handoff` cover
registration, resources and handoffs; `load_reference` reads a saved reference
file. A same-key retry returns the request's `stewart.request/1` document
instead of the operation's result.

Operations return structured results and raise `StewartError` with a stable
`reason`, `retained` paths and `next_steps` (and `handoff` for
`implementation_mismatch`); `collect`, `status`, `run` and `close` results and
every refusal carry the exit code the CLI would return. Importing the package
performs no repository, process or network work.

## Exit codes

Every command and helper uses the same four codes:

| Code | Meaning | The auditor reads it as | The manager reads it as |
| --- | --- | --- | --- |
| 0 | Nothing needs attention. | Accepted; stop. | Proceed. |
| 1 | Action is needed within your role; each listed item names the change. | Change what is listed, run `check` again. | Address the listed items: rerun, or record a decision in triage. |
| 2 | Refused; nothing was done. | Wrong place or command; reread the handoff. | Fix the command or its preconditions. |
| 3 | Something you did not produce does not verify. | Not yours to fix: describe it in the report, declare, and stop. | Inspect, then recover or abandon. |

Three rules hold everywhere:

1. **No news is good news.** Exit 0 means nothing needs attention. There is no
   "succeeded with warnings": anything worth warning about is nonzero. Routine
   next steps, such as launch or triage, are not news.
2. **Codes ignore what the audit says.** Declared completion, report kind,
   report prose, triage's claims and decision, and an experiment child's own
   exit status never change a code. Whether the audit was done well is
   triage's call. The one gap that compares the auditor's completion claim
   with the manager's stop acknowledgment, `completion_stop_discrepancy`, is
   manager-side and never `check`'s concern.
3. **The auditor's tool predicts the manager's result.** The auditor's final
   `check` code equals the code the manager's collection gets for everything
   that depends only on the checkout.

When both apply, 3 takes precedence over 1. A refusal caused by records that
do not verify is 3, not 2. Each refusal reason maps to one code; reasons are
part of the JSON contract. Per command: `collect` returns 0, 1 or 3 by its
gaps and errors; `status` as described under [Inspect](#assignment-and-custody-steps);
`triage-draft` returns 0, 2 for a refusal, or 3 when the collection it binds
does not verify;
`run` returns 1 when the child failed or preservation failed and 3 when the
supplied runtime stopped verifying across the attempt; `close` returns 0 for a
clean close, 1 when removal stopped partway, left unrecorded entries, or left a
resource blocked, missing or unremoved, and 3 when a concluded close meets
records that do not verify; `close --plan` returns the code that close would
earn now (a refusal's code, 1 for a resource left blocked or missing, else 0); `prepare` refuses a
failed preparation with 2 (`prepare_failed`) and keeps its session.

A custody operation succeeding is not an audit passing. A child's exit status
is recorded in its attempt and never becomes the tool's exit code. In `--json`
mode the `stewart.result/3` envelope carries `ok`, which is true exactly when
the exit code is 0, `exit_code`, `result` (present for exits 1 and 3 too, and a
`stewart.request/1` document for a replayed request) and `error` (with
`reason`, `message`, `retained`, `next_steps`, and `handoff` for
`implementation_mismatch`), and nothing else is written to stdout.

## Development checks

From a source project with its hash-locked wheelhouse provisioned, run:

```sh
/absolute/build-venv/bin/python -I -B scripts/check.py --wheelhouse /absolute/wheelhouse --result /absolute/results.json
```

The runner builds a wheel, installs it into a private venv, and copies tests to
an unrelated directory. It selects that copy's pytest configuration explicitly,
disables inherited plugins and options, and records collected/selected nodes,
per-node outcomes, the installed member population, wheel digest and interpreter.
It retains command streams and fixture artifacts beside the result. An empty
selection is an error. Repeat with Python 3.11 and a newer supported interpreter.
Socket checks require a host that permits a local Unix socket; unreadable-file
controls require an unprivileged user. No dependency downloads occur in this
runner. Its nested boundary tests reuse the same provisioned wheelhouse.
