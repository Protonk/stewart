# Developing Stewart

This project is independently buildable: runtime code lives in `src/stewart`,
bundled guidance and launcher templates in `src/stewart/resources`, and tests
in `tests`. Runtime dependencies are the Python standard library plus the
declared external Git/shell prerequisites. Use the distribution's `_util` byte
contracts; never import a containing repository's helpers or configuration.

[The coordinator handoff](COORDINATOR-HANDOFF.md) records the user's working
expectations for agents taking the coordinating role across harnesses.

“Ask Riker for help” means prepare a request for the user to relay to a separate
Project conversation. `riker/RIKER.md` describes the exchange and links the
opening-message template.

Preserve unrelated working-tree changes. Active plans are ordinary tracked
working documents with stable paths; discover them by the `*-PLAN.md` naming
convention. Update their current account as work changes; Git preserves history.
At completion or abandonment, give unfinished work an explicit disposition,
move enduring contracts and explanations into documentation and tests, and
delete the plan. There is no obligation to retain every planning paragraph.
Keep durable guidance stateless: maintained AGENTS and README files must not
route readers to particular plans, and product code and tests must stand without
them. Explain mechanisms and reasons without temporary planning coordinates.
Preserve captured historical documents. Do not add compatibility shims or
rewrite historical receipts to fit a newer schema.

For a fleet approach, one coordinating agent owns the coherent result. It
investigates the intended outcome, protected obligations, changeable behavior
and consequential decisions for the user; chooses useful concurrency, complete
worker assignments, edit ownership, integration order and verification; and
makes a bounded first wave ready to dispatch. Later assignments can remain
provisional. Preparing an approach does not itself start implementation.
Within authorized execution, the coordinator may revise assignments, resolve
ordinary disagreements, integrate changes and arrange independent review without
repeated permission requests. The user retains authority over purpose, scope
and changes to protected obligations. Use the harness's delegation and workspace
facilities, with Codex or Claude as appropriate; no fixed staffing, provider split
or development orchestration framework is required. Development workers do not
inherit Stewart's manager/auditor workflow. Keep worker returns compact and
verify the combined result. Shared check-ins normally cover stage outcomes,
semantic decisions, evidence and unresolved questions in human-readable docs;
the coordinator manages internal logistics.

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
  keeps its session and every failure record. `close` is the only deletion: it
  is explicit and gated, writes its closing record first, and removes only what
  the session recorded or its resource claims froze. An abandoned audit ID is released only under the
  mechanical rule that `init` and `prepare` reapply; otherwise a fresh
  assignment is needed. Status names the observed stage and prerequisites,
  without inferring auditor completion or experiment readiness. Only a missing
  completed receipt supports a partial/unresolved label; an invalid or unreadable
  record keeps its diagnostics. Failed release reads must not require success-only
  fields or produce capture associations and run suggestions.
- **Removal is authorized by two records only.** A session's `CLOSING.json`
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
