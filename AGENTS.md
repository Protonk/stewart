# Developing Stewart

The successor design review is closed. Start product work from [DESIGN.md](DESIGN.md),
[CONTRACTS.md](CONTRACTS.md) and [ACCEPTANCE.md](ACCEPTANCE.md), not historical
conversations or prototype briefs. Exact schemas and mechanisms are engineering
work within those decisions; bring new authority or substantive restrictions
back to the user. Historical evidence is not a competing design.

The frozen Python tool is independently buildable: its runtime lives in `src/stewart`,
bundled guidance and launcher templates in `src/stewart/resources`, and tests
in `tests`. Runtime dependencies are the Python standard library plus the
declared external Git/shell prerequisites. Use the distribution's `_util` byte
contracts; never import a containing repository's helpers or configuration.

One coordinating agent owns the coherent development result: understanding the
task, organizing work, integrating changes and verifying the result. The user
retains purpose, scope and protected obligations.
[Coordination guidance](coordination/README.md) sets the working constraints,
including for dispatched workers. Notes are optional
support for unfinished work, not a routine deliverable or a session history.

[CONTRACTS.md](CONTRACTS.md) states the behavior Stewart is decided to have,
with each contract's implementation status and the reasons for declined
changes; changes to Stewart's intended responsibilities are recorded there.

The bundled Python manual, role files and issued handoffs describe the frozen
implementation they ship with. Use CONTRACTS.md's decided departures when
designing the successor; do not import the baseline's manager access, resource
service, dedicated program executor or private-location inventory as successor
requirements. Keep those
bundled bytes unchanged while Python remains the frozen legacy implementation.

For user-relayed consultation, [riker/RIKER.md](riker/RIKER.md) defines
“ask Riker for help.”

Preserve unrelated working-tree changes. Active plans are ordinary tracked
working documents with stable paths; discover them by the `*-PLAN.md` naming
convention. Update a plan when decisions or remaining work change; Git preserves
history.
At completion or abandonment, give unfinished work an explicit disposition,
move enduring contracts and explanations into documentation and tests, and
delete the plan. There is no obligation to retain every planning paragraph.
Keep durable guidance stateless: maintained AGENTS and README files must not
route readers to particular plans, and product code and tests must stand without
them. Explain mechanisms and reasons without temporary planning coordinates.
Preserve captured historical documents. Do not add compatibility shims or
rewrite historical receipts to fit a newer schema.

"The user" in development guidance is the development principal. Stewart's
users are the people who supply material and operate it; today they are
the same person, who then acts as their proxy and decides on their behalf. A
document for Stewart's users must serve them, not the proxy.

Development workers do not inherit Stewart's manager/auditor workflow.
Conversely, the product does not
inherit the development fleet's steering and supervision practices. Stewart
serves a bounded commission and structured return; additional intervention
facilities need a specific commission or custody reason, not parity with a
harness-managed swarm. After product handoff, the manager receives a structured
return through the agreed interface; live product access is restricted to
commission readback, operating status and close. The first Rust release's
manager-designated archive remains readable by its owner; no live answer viewer,
steering channel or secrecy from the host owner is promised. Rich
selected context and investigative latitude remain compatible with a narrow
question. The successor auditor has only Stewart's commission-bound tools,
without a private-location inventory. Qualify actual access and stopping, not merely the
settings. Exact wire and process mechanisms instantiate CONTRACTS; they do not
select an extra intervention channel.

Stewart stays agnostic about the intellectual utility of audits, including in
development evaluation. Its major intellectual influence belongs in question
types and the constrained audit space. Examine whether answer restrictions let
participants express, inspect and contest permitted responses; do not use
agreement with a preferred outcome as the success criterion. Restrictions that
privilege or exclude substantive outcomes need explicit design deliberation.
Auditor and manager judgments remain attributed. CONTRACTS.md owns the principle.

The successor direction separates recording a commission from promising its
replay; the manager owns constructing another question. There is no restart-from-start
facility. An interrupted run continues the same ledger and cumulative limits;
existing code or tests do not justify restoring a staged workflow. Stewart must
account for its incomplete custody operations through supported paths:
agent-managers should not need to improvise repairs to private state. Recovery
cannot grant another investigative execution or conceal uncertainty, and a
family of retries is not simplified by renaming it recovery. The successor has
no dedicated program executor or staged program release/run workflow. Permitted
auditor tool use remains bounded by its commission and actual access grants;
supplied execution reports retain their attribution. Continuation grants no fresh
investigation or reset allowance. Frozen-Python rules below concerning releases,
child loading and attempt evidence protect that baseline and admitted legacy
interpretation; they do not require an executor in the successor.

Use an explicit interpreter with isolated startup (`-I`, plus `-B` where
bytecode must stay unwritten) in development commands. Isolated mode ignores
`PYTHONPATH`, so documented commands do not set it, and nothing selects a
Stewart installation through it. Provision `requirements.lock`
into a wheelhouse, then run `scripts/check.py` with the selected interpreter.
It builds and tests an installed wheel with explicit pytest configuration and
no parent plugins; [DEVELOPMENT.md](DEVELOPMENT.md) gives its commands, test
selection and retained evidence. Preserve command outputs and report actual
selector counts. Retained runs under `.scratch` follow DEVELOPMENT.md's
removal policy: each invocation reduces its own artifacts, `scripts/prune.py`
is the only way an artifacts directory leaves, and a run's record stays with
the plan or report that cites it.
A clean result needs a firing control, a case differing in the measured
property and an invariance case. An explanation remains a hypothesis until a
comparison distinguishes it from its rivals. Qualify real harness enforcement
separately from settings construction. Write useful CLI help, comments and
failure messages along with implementation and tests.
For studies of missing capture, extraction or deletion, keep an independent
witness and controls through review under the evidence-run retention rules;
an apparently passing run may conceal the omission being investigated. Record
observer scope and timing, and keep the witness outside the disposal under
test. A rescue from development evidence does not establish that the product's
ordinary retrieval worked or grant authority to resume its audit.

The custody rules below retain their stated scope. Python module names, Git
resources, request keys, executor and removal mechanics protect the frozen legacy
implementation; they are not extra Rust features. Rust follows CONTRACTS and
qualifies equivalent exclusive-write, exact-byte, attribution and failure duties
within its narrower scope.

The custody rules are:

- **Receipts are exclusive.** Create every record with `write_receipt`; never
  open a session file for overwrite or use an atomic-replace writer here. A
  retry gets a new record name. If a destination exists, that is evidence.
- **Never follow a link the auditor could have planted.** Resolve session and
  checkout paths through `contained`, read regular files through the verified
  descriptor helpers in `_bootstrap.py`, and never read a FIFO, socket or device.
  `contained` validates path shape and observed links; only descriptor-relative
  traversal prevents a late ancestor replacement from redirecting a read.
- **Record what was observed, who acknowledged what, and what the auditor
  claimed, in separate fields.** No field may turn these into a grade,
  deadline or verdict. If you parse anything from a report, attribute it.
- **Declarations have one parser.** Auditor operations and custody consumers
  use `report_declaration.validate_report_declaration` with explicit identities
  and sources. Capture raw bytes first; validation cannot gate preservation.
  Missing or invalid declarations are gaps, never prose-inferred completion.
  Editable reports are not receipts: stage replacement bytes in the report's
  directory, preserve surrounding bytes, and retain failed staging files.
- **Refusals carry a `reason`.** Raise `StewartError` with a stable identifier,
  the retained paths, and a next step; reason identifiers are part of the JSON
  contract and tests assert on them.
- **No workspace coordinates in logic.** Every assignment-facing path derives
  from the `Workspace`. Behavioral tests run the tool at unrelated and nested
  workspace paths; no scanner can recognize every possible workspace literal.
- **Import stays side-effect free.** The package surface loads lazily; keep
  Git, filesystem and subprocess work inside operations, never at import or in
  parser construction.
- **Callable API lives in `api.py`.** Package submodule names remain modules;
  do not export a function under the same name on the package object.
- **Verify the evidence being summarized.** Experiment rows are captured before
  parsing, operands determine disagreements, and the released review determines
  case membership. Input identity comes from preparation, not a rewritten
  manifest. Submitted responses carry their collection name and receipt digest;
  identical report bytes cannot stand in for collection identity. Submission and
  disposition revalidation share that comparison. Status and mutations use the
  same disposition binding validation.
- **Measurement membership is reviewed.** Each admitted case's released IDs
  must occur exactly once. Row counts, a firing control and the child's own
  declaration cannot substitute for that set. Counts exclude ambiguous or
  unreviewed measurement identities; scientific interpretation stays with the manager.
- **Control JSON cannot choose among repeated keys.** Assignment metadata,
  declarations, CLI inputs, input/protected manifests, launch profiles, custody
  records and evidence-package metadata use `_json.loads_control`. Reject nested,
  identical and escape-equivalent repeats before interpreting control fields.
  API callers own decoding before supplying dictionaries. Raw child ledger and
  receipt decoding stay separate; capture and package payloads preserve their
  bytes without imposing the control rule. A matching hash is not permission to
  choose among competing fields, and invalid historical records stay untouched.
- **Handoffs use captured bytes.** Retention, export and status's release capture
  associations share `captured.py` for archive/member verification. Discovery
  digests select candidates; they never establish recoverable captures. Status
  verifies at read time and leaves historical receipts unchanged.
  An evidence package pins its source receipt and
  explicit selections; importing it conveys custody, never execution permission
  or acceptance of its claims. Never fall back to a live worktree file.
- **Recovery preserves failure.** While an audit is live, a failed preparation
  keeps its session and every failure record. In the frozen Python baseline,
  `close` is the only deletion: it
  is explicit and gated, writes its closing record first, and removes only what
  the session recorded or its resource claims froze. An abandoned audit ID is released only under the
  mechanical rule that `init` and `prepare` reapply; otherwise a fresh
  assignment is needed. Status names the observed stage and prerequisites,
  without inferring auditor completion or experiment readiness. Only a missing
  completed receipt supports a partial/unresolved label; an invalid or unreadable
  record keeps its diagnostics. Failed release reads must not require success-only
  fields or produce capture associations and run suggestions.
  For the successor, working-environment retirement may precede final custody
  close while identified captured material stays held. Removal still needs
  explicit recorded authority; a hold grants no continued investigation, and
  completed close cannot conceal unfinished custody operations. The retirement
  interface and receipt representation must realize that distinction.
- **Removal is authorized by two records only.** In the frozen Python
  baseline, a session's `CLOSING.json`
  authorizes its recorded inventory. A resource's exclusive
  `resources/<id>/claims/<n>.json`, created by a gated close (audit close after
  its `CLOSING.json`, or `close --resource`), authorizes that resource and the
  dependencies it names as disposed. A claim requires a Stewart-recorded
  creation (`CREATE.json` with `CREATED.json`), no live use and every
  eligibility check; it never names an enrolled resource. Start records,
  enrollments, registrations, associations, acknowledgments, paths and Git
  registrations grant nothing. Freeze what the evaluation judged (identity,
  full inventory, HEAD or tip), never a later re-read. Revalidate frozen
  identities, contents and uses at use; release the claim
  (`<n>.RELEASED.json`) rather than remove anything that changed. Record each
  removal attempt before its first removal step. A container retires only with
  everything recorded inside it, and a disposal decision never overrides
  another audit's live use. Intended locations of unverified resources can only
  block removal; an unlocatable resource keeps every path container. Invalid
  retirement endings or acknowledgments never hide a dependency. Remove through pinned
  descriptors, only the recorded device and inode, never across filesystems,
  and never let Git delete contents; drop a worktree's administration only
  after its marker names the lifetime. Doubt about a use keeps the resource.
  The first Rust successor has no removal service: close ends activity and keeps
  captured bytes, partials and records in the manager-designated archive; the
  ordinary preparation folder stays with its manager. No prune, purge or hold/
  release workflow ships in that non-removing scope. This releases no earlier
  hold or obligation. Any later destructive service needs a new explicit contract
  and must revisit these authority, custody and dependency protections. The general
  manager-workspace service remains deferred. Legacy interpretation serves an
  identified consumer over
  explicitly supported records; it creates no new resource-removal claims or
  blanket compatibility obligation. Preserve original evidence and diagnostics;
  interpreting it grants no authority to continue its old lifetime.
  Frozen revalidation, descriptor removal, custody, access and live-dependency
  protections remain within that removal scope. A narrow, attributed hold
  covers a finite identified selection and the metadata/captured dependencies
  required for its custody claims; references do not recursively enlarge it.
  It blocks disposal until explicit attributed release; close and container
  removal never release it.
  Copying or relocating held material does not by itself discharge the hold.
- **Selection is a reference the caller keeps.** Discovery and selection write
  nothing and choose nothing by recency, current directory or installation.
  Every operation revalidates a reference; a draft reference never selects a
  later lifetime. Aliases stay explicit when ambiguous.
- **Request keys bind intent; they never replay uncertainty.** Publish the
  exclusive binding before side effects, record planned outputs before the
  first one and the outcome after (plan a new record's identity before writing
  it); a matching key returns its record. A result
  its operation does not call complete records no outcome. Resume only a
  partial request of a resumable operation, adopting only work its own attempts
  planned. Keep request records beyond retirement. Do not deduplicate unkeyed
  requests.
- **Runtime handoff is explicit.** A mutation under an implementation other
  than the record's writer is refused; offer only a handoff verified by
  descriptor reads of the recorded deployment, launcher and interpreter. Never
  import, execute or relay recorded code, and never fall back to the current
  installation.
- **Child ledger loading is independent of project imports.** `ledger.py`
  depends on the standard library only. The private launcher preloads its pinned
  bytes as `_stewart_ledger_v1` before admitting the script directory and project
  root. Project `tools` and `stewart` remain legitimate names. Check the reserved
  ledger namespace at release, prelaunch and startup; never catch project
  exceptions as bootstrap refusals.
