# Prior custody decisions and questions to recheck

These are inputs to semantic inquiry, not a new correctness execution queue.
The performance work left substantive custody issues despite its stale
schedule. Historical findings remain in
[`reports/development-history/`](../../reports/development-history/README.md).
Reproduce or inspect each relevant claim before relying on it as current fact.

## Previously agreed, recorded as unimplemented

`archive/2026-10-23/close-followups` (`d4b99f6`), in
`CORRECTNESS-FOLLOWUPS-PLAN.md`, records these user decisions:

- Compute the implementation stamp before creating collection, run or runtime
  recovery state; package Git timeouts leave commit and dirty state unknown.
- Replace the porcelain branch query with `git symbolic-ref -q HEAD`, after
  comparing attached, detached, unborn and chained HEAD behavior; cover the
  worktree role identity contract.
- Preserve the last required observation before a write, record or removal,
  and record or bind the value the decision actually used. Resolve the prompt
  commit once in preparation where that rule permits it.
- Count hidden executable-bit changes in capture coverage, as well as kind
  and content.

The same note accepts status withholding close without a separate capture
attention item, provisionally accepts collection recording no coverage of its
own, and accepts stopping capture rechecks after the checkout has been removed.
A stopped close requiring restoration of its judged state was also accepted.
These are prior decisions to make visible when examining alternatives; the
reset neither implements nor silently reverses them.

## Open or tabled leads

- Execution through submodule Git configuration; relative-path worktree
  administration; replace refs and inherited Git environment variables.
- Filesystem traversal and late replacement, including the path-based walk,
  frozen observations, and cleanup paths that keep a resource while proceeding
  with other removal.
- Supplemental inputs below gitlinks being classified as custody gaps.
- Refusal semantics and recoverability: failed preparation's exit code,
  missing versus invalid evidence, unresolved attempts and interrupted writes.
- Issuance versus preparation, launch acknowledgment, live retained-digest
  checks, and what status offers versus what an operation must validate.
- Scope changes after preparation, project rules reaching the auditor, and
  whether the experiment route meets projects' real execution needs.

Sources: the historical test-speed findings and close/report follow-up notes,
plus `d4b99f6`. Some reported defects were subsequently fixed; none of this
list establishes present reproducibility. The shipped checkout-administration
gate and verified capture before close remain in place. Submodule support has
its own [candidate note](submodules.md).
