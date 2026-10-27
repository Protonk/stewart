# Existing custody route for the first C self-audit

Prepared 2026-10-27 by `/root/commission_auditprep`; source baseline `eea8719`.
This is source-established preparation, not an executed audit or successful
export. `READS.json` identifies inspected source and five retained read-only
command records. No builds, installations, pytest nodes or custody operations
ran in this worker. One initial lookup used guessed test filenames and found
none; the exact existing test paths below were then established from `rg`.

## Responsibility and usable route

Root can operate the frozen Python writer for `prepare`, launch acknowledgment,
`collect`, collection-bound `triage`, `retain` and `export`. Root remains the
manager/custodian of its live session and every incomplete operation. C supplies
the independent original-commission bundle; C does not capture or preserve the
audit return. Keep those claims separate in the final account.

**Corrected assignment assumption:** frozen `prepare` requires its checkout home
outside every repository working tree, Git common directory, manager home and
interpreter prefix, absolute/unlinked and private 0700. An in-repository checkout
home is invalid. Root accepted `/private/tmp/stewart-commission-self-audit-<unique>`
as the planned home and will retain it. Use `/private/tmp`, not the linked `/tmp`
spelling. Sources: `cli.py:228`, `prepare.py:179`, manual's checkout-home rules.

The investigator need not have access to that home, the manager deployment,
repository history or live session. Holding those privately while delivering a
finite package satisfies the intended information boundary without performing
destruction as a demonstration. Instructions and fresh context do not establish
OS enforcement; report the actual boundary used.

## Frozen writer availability and qualification

Observed: repository `.venv/bin/python` is CPython 3.14.9. `build`, `hatchling`
and `pytest` are installed; `stewart` is not. `.scratch/wheelhouse` contains the
locked build/test wheels. Root can build/install offline under fresh named
evidence directories. These are proposed commands, not recorded executions:

```sh
STEWART_AUDIT_REPO=/Users/raccoon/Desktop/Experiments/stewart
STEWART_AUDIT_BUILD="$STEWART_AUDIT_REPO/.venv/bin/python"
STEWART_AUDIT_DIST="$STEWART_AUDIT_REPO/.scratch/commission-self-audit-01/dist"
STEWART_AUDIT_ENV="$STEWART_AUDIT_REPO/.scratch/commission-self-audit-01/runtime"
"$STEWART_AUDIT_BUILD" -I -B -m build --no-isolation --wheel --outdir "$STEWART_AUDIT_DIST" "$STEWART_AUDIT_REPO"
"$STEWART_AUDIT_BUILD" -I -B -m venv "$STEWART_AUDIT_ENV"
"$STEWART_AUDIT_ENV/bin/python" -I -B -m pip install --no-index --no-deps "$STEWART_AUDIT_DIST/stewart-0.1.0-py3-none-any.whl"
```

For a minimal relevant installed-wheel check, use the project's checker and
retain its result/streams. These selected tests cover issued helpers, reviewed
capture retention and exported-source independence; actual collected counts must
come from the runner, including parameterization:

```sh
"$STEWART_AUDIT_BUILD" -I -B "$STEWART_AUDIT_REPO/scripts/check.py" \
  --wheelhouse "$STEWART_AUDIT_REPO/.scratch/wheelhouse" \
  --result "$STEWART_AUDIT_REPO/.scratch/commission-self-audit-01/frozen-route.json" \
  --keep-artifacts all \
  tests/test_prepared_runtime.py::test_preparation_supplies_every_issued_helper_without_project_sources \
  tests/test_stewart_triage.py::test_retention_publishes_the_reviewed_capture_not_the_live_report \
  tests/test_stewart_handoff.py::test_selected_captured_bytes_survive_live_edits_and_source_removal_and_prepare
```

This does not qualify all Python behavior or C. The runtime wheel used to operate
the audit and the checker wheel each need their own identity; do not infer byte
identity merely from a version label. A sandbox refusal at fixture setup is no
executed test body. DEVELOPMENT.md owns retained-run handling.

Source-bootstrap alternative, if root chooses it before creating the session:

```sh
"$STEWART_AUDIT_BUILD" -I -B "$STEWART_AUDIT_REPO/src/stewart/_bootstrap.py" \
  source --manager-home /private/tmp/stewart-commission-manager-CHOOSE-UNIQUE-SUFFIX -- \
  --repo "$STEWART_AUDIT_REPO" --workspace audits/commission-recall --json COMMAND
```

Replace CHOOSE-UNIQUE-SUFFIX with a fresh explicit name before issuing this command. The
source route creates a pinned private deployment; even `status` through it may
create deployment state. It is not a read-only probe and was not run here.
`PYTHONPATH` selects neither route. Keep the selected writer, launcher and
interpreter available for all mutations; do not switch installations mid-lifetime.

## Workspace and prompt preparation

There is no `scaffold` CLI command. Root creates a fresh workspace, and exclusively
copies the frozen installed `docs auditor`/`docs maintainer` output into separate
`AUDITOR.md`/`MAINTAINER.md` files; a copied `docs questions` file can supply the
question recipe. Commit support before the prompt commit. Any additional local
audit grants belong in the authored prompt, not alterations to frozen package
resources. Source: `docs.py:6`, `assignment.py:364`, `workspace.py:107`.

Once implementation and acceptance evidence are actually ready, freeze all
unrelated changes and choose the exact target commit. Example shell helper for
the installed route (substitute the actual fresh manager-home suffix):

```sh
STEWART_AUDIT_PY="$STEWART_AUDIT_ENV/bin/python"
STEWART_AUDIT_WS=audits/commission-recall
STEWART_AUDIT_ID=commission-recall-self-audit-01
STEWART_AUDIT_MANAGER_HOME=/private/tmp/stewart-commission-manager-CHOOSE-UNIQUE-SUFFIX
stewart_audit() {
  env STEWART_MANAGER_HOME="$STEWART_AUDIT_MANAGER_HOME" \
    "$STEWART_AUDIT_PY" -I -B -m stewart \
    --repo "$STEWART_AUDIT_REPO" --workspace "$STEWART_AUDIT_WS" --json "$@"
}
```

Persist a fresh request key before each effectful invocation. Global
`--request-key` precedes the command. Retain exact argv/cwd/stdout/stderr/status;
do not use overwriting redirection over earlier output. JSON is an envelope:
ordinary data lives in `result`; `ok` is false for completed attention outcomes.
A keyed replay returns a `stewart.request/1` record with its recorded outcome,
not necessarily the original result shape. Sources: `cli.py:1418`, `request_keys.py`.

Use explicit `--input` arguments for the committed finite source/test/document
population; use `--supplemental PATH PROVENANCE` for uncommitted acceptance
evidence. Avoid a whole-tree grant merely because the detached checkout contains
the whole tree. `--input-manifest` creates a new uncommitted supplemental inventory
and reduces prompt bulk; select it only if useful. A call pattern is:

```sh
stewart_audit --request-key c-self-audit-init-01 init \
  --audit-id "$STEWART_AUDIT_ID" --target-commit "$STEWART_AUDIT_TARGET" \
  --input successor/README.md \
  --input successor/Cargo.toml \
  --supplemental "$STEWART_AUDIT_EVIDENCE_REL" "Manager's retained installed-C acceptance evidence; methods and limits stated in that record" \
  --replace-prompt
```

The two `--input` examples are incomplete placeholders for the real selected
implementation population. Resolve the actual module/test/evidence paths before
issuing the command. The five required prose headings are Question, Decision,
Scope and exclusions, Evidence and Stop condition; remove `UNASSIGNED`, preserve
the generated `audit-assignment` metadata, and do not fabricate an experiment
grant. Commit `PROMPT.md` alone. Its commit must have one parent; target must be
an ancestor; all intervening changes must stay inside this audit workspace, and
assigned input bytes cannot drift. Sources: `assignment.py:23`, `prepare.py:115`.

Accept the final actual question and identical selected original materials into
C for manager recall before auditor launch. The C bundle need not be an input to
its own audit prompt; that would risk a circular binding. The auditor can examine
C implementation and prior acceptance evidence, while the manager independently
uses C to preserve/recover this actual audit commission. Preserve an independent
pre-intake witness and exact relation between C's selection and Python's inputs.

## Prepare and hand off to the actual auditor

```sh
stewart_audit --request-key c-self-audit-prepare-01 prepare \
  --prompt-commit "$STEWART_AUDIT_PROMPT_COMMIT" --mode snapshot \
  --checkout-home "$STEWART_AUDIT_CHECKOUT_HOME"
```

The result supplies `reference`, `session_uuid`, `worktree`, public `launch`,
`prompt_sha256`, `launch_token`, `runtime` and private custody coordinates. Save
the reference exactly and bind later commands with `--lifetime SESSION_UUID`
or `--ref FILE`. Do not send the private session paths to the auditor. No launch
profile is needed for the actual fresh Codex worker.

Root gives that worker only the public handoff and finite task/grants. Its first
actions read AUDITOR/PROMPT, invoke the exact issued input verifier and declaration
`start` helper, then preserve the reserved declaration block while authoring.
It writes only report/declared notes, uses the issued `set --completion ...
--report-kind ...` helper, and invokes `check --print` last before stopping.
No complete declaration is inferred from prose. `answer`, `needs-evidence` and
`reframe` are all available; completion and report kind remain separate.
The handoff prints exact isolated helper commands bound to runtime, worktree,
workspace, prompt commit/hash and launch token. Do not reconstruct them manually.
Source: `prepare.py:350`, `report_declaration.py:545`.

Record the real handoff after dispatch. A fresh `fork_turns=none` worker is best
described with `--style other` plus its actual harness note, rather than implying
the help text's context-inheriting subagent style:

```sh
stewart_audit --lifetime "$STEWART_AUDIT_LIFETIME" \
  --request-key c-self-audit-launch-01 launch --audit-id "$STEWART_AUDIT_ID" \
  --style other --model "inherited default; no model override" \
  --effort "inherited default; no effort override" --actor "root coordinator" \
  --note "Fresh Codex collaboration worker with fork_turns=none; actual handle recorded in coordinator evidence. Finite procedural grants; no claim of OS-enforced isolation."
```

Use the actual requested model/effort if explicitly known. Those fields are
attributed requested settings, not measured runtime facts. The command launches
nothing and observes no agent. Source: `coordination.py:45`.

## Capture, deliberate review and preservation

Wait for actual worker completion/stop evidence and save it. Only then:

```sh
stewart_audit --lifetime "$STEWART_AUDIT_LIFETIME" --request-key c-self-audit-collect-01 \
  collect --audit-id "$STEWART_AUDIT_ID" --auditor-stopped finished
stewart_audit --lifetime "$STEWART_AUDIT_LIFETIME" \
  triage-draft --audit-id "$STEWART_AUDIT_ID" --collection "$STEWART_AUDIT_COLLECTION"
```

Choose interrupted/blocked instead when that is the actual stop. Collect captures
raw report before interpreting it and preserves gaps/failure evidence. With
`--json`, submit only the edited `result.response` from the triage draft; retain
`result.context` separately. Preserve `collection`, `collection_sha256` and
`report_sha256` exactly. Fill a decision, disposition every actual custody-gap ID,
and review each support member before adding its repo-relative path to
`support_reviewed`. Accepted claims need evidence references; rejected/unresolved
claims need reasons. Empty claim lists are valid. A valid needs-evidence/reframe
requires `follow_up` with matching kind, accept/decline/defer and a reason.
Source: `triage.py:60`, `triage.py:145`. Shape validation is not review quality.

```sh
stewart_audit --lifetime "$STEWART_AUDIT_LIFETIME" --request-key c-self-audit-triage-01 \
  triage --audit-id "$STEWART_AUDIT_ID" --collection "$STEWART_AUDIT_COLLECTION" \
  --response "$STEWART_AUDIT_RESPONSE" --actor "root coordinator"
stewart_audit --lifetime "$STEWART_AUDIT_LIFETIME" --request-key c-self-audit-retain-01 \
  retain --audit-id "$STEWART_AUDIT_ID" --triage "$STEWART_AUDIT_TRIAGE" --report \
  --support "$STEWART_AUDIT_NOTE_REL"
stewart_audit --lifetime "$STEWART_AUDIT_LIFETIME" --request-key c-self-audit-export-01 \
  export --audit-id "$STEWART_AUDIT_ID" --collection "$STEWART_AUDIT_COLLECTION" \
  --select REPORT.md --select "files.tar:$STEWART_AUDIT_NOTE_REL" \
  --output "$STEWART_AUDIT_EXPORT" --actor "root coordinator"
```

Use the actual selected support list, including none; repeat the relevant flag
for each file. Never manufacture a note for the example. Retain writes captured
bytes at their assigned paths exclusively; export reads selected captures only,
not live files, and publishes a new package with `manifest.json` last. Parent
destination must already exist; failed output remains and needs a fresh output
path. Export also records a retained resource. Sources: `triage.py:344`,
`handoff.py:120`. No `resume` is needed for snapshot coordination. No `close`
is needed for the investigator experiment; root keeps all outstanding custody.

## What the investigator receives and what it cannot assume

`stewart.evidence-package/5` contains the exact source receipt as `source.json`,
explicitly selected report/support bytes, and a manifest binding selection,
source collection identity/digest, actor and writer/runtime metadata. The same
report bytes in another collection are a different custody source. Optional
`runtime-assets` and `runtime-observation:collection` are complete-group selectors;
they are unnecessary to include by default and do not prove what code executed.

The package does **not** automatically carry authored PROMPT bytes, original
question materials, target Git objects or manager triage. A commit name does not
recover those bytes after repository loss. Unchanged committed inputs are not
ordinary `files.tar` selections. Supply finite original context separately when
root judges it necessary: the C commission bundle, exact manager review/triage
record, or independently preserved source witnesses, with source/digest/copy
attribution. Do not rewrite `manifest.json` to smuggle them into the old schema
or claim C preserved the result. Prefer stating a missing artifact over secretly
falling back to the live checkout.

Before delivery, root independently checks package manifest/source/member
bindings and selected byte equality against preserved captures, then records the
finite delivered inventory and receipt pins. This is evidence preservation,
not a new result-reader contract. Give the fresh investigator that population
alone and a concrete decision, not an expected remedy. It should record needs,
successful checks, unavailable operands and unsupported claims. If it requires
originating code execution or live state, record the need; do not supply those
silently or count a witness rescue as ordinary retrieval.

Suggested audit question, to refine against actual C code: “Does this accepted
commission receipt support the manager's claim that the named original question,
selected material and declared grants/limits remain recoverable after the
originating intake process and original source paths are unavailable? Trace the
first supported loss, unsupported promotion or unresolved premise.” Select the
existing Receipt sufficiency recipe. The decision is whether to ship the claim,
repair a specific gap or narrow its wording. Finite source should follow the
actual accept/read/verification path and relevant retained acceptance cases;
do not preselect a favorable result or a future answer schema. Static review can
propose discriminating cases; execution requires explicit bounded grants.

## Remaining facts for root

Actual C source revision, module/input population, original question, evidence,
input-manifest choice, package selection and worker identities are not yet known.
The writer route is source-established but not executed here. Root must record
real build/installation/checker outcomes and actual capture/export failures if
any. Reading `package_inputs` explains independent verification; it does not
commission a successor legacy reader or require the investigator to use the old
writer. No A-style preview follows automatically from this route.
