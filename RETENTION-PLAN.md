# A small working repository

Keep what one agent/human team needs to build, test and evaluate Stewart.
Archive material only when it has a present inspection purpose and would be
costly or impossible to reproduce. Reconstructing whether an old test should
have passed is outside that purpose. Generated files are disposable by default.

The principal selected this direction and authorized the initial easy pruning.
The work below is the proposed follow-on, not authorization for model calls or
changes to Stewart's product custody contract. Keep this plan only until the
working setup and retention rules have been simplified.

## Intended working set

- One main checkout, the current source, lockfile and one vendored dependency
  tree; temporary worktrees only for work actually in progress.
- Current product specifications, operating/development instructions, test
  fixtures and generators, and the few unresolved decisions needed for the
  next work. Existing document owners remain authoritative.
- Current build/test outputs as replaceable working files. Keep concise actual
  results, failures, skips, controls and environment/binary identities when
  they are needed to evaluate the current application.
- Selected original model encounters, supplied inputs, returned answers and
  human observations needed to inspect a retained finding. Include the settings,
  usage and attribution needed to interpret them. A paid call alone does not
  justify an archive, and a cheap rerun cannot recreate a particular encounter.

## Remaining work

### 1. Settle the few obligations that affect disposal

- [ ] Check the current state of the two early sanity audits. The retained
  `review/result.json` and exported status replies in `.scratch/sanity-live-01`
  and `.scratch/sanity-live-06` report `closed: no`; no later closure record was
  found locally. These are old observations, not proof of current container
  state. Their `host/operator.json` files supply the exact status commands.
  The principal runs container commands with `!`. If closure is still needed,
  use the original writer, inspect delivery and finish the ordinary close path;
  do not resume a model to dispose of an audit. Until resolved, retain those
  archives and the `acceptance-05` writer.
- [ ] Inventory the remaining containers/images with the principal. Repository
  disk totals exclude them. Retain the working toolchain and only containers
  needed for active work or unresolved inspection; remove superseded synthetic
  runs after selecting any evidence worth keeping.
- [ ] Give the explicitly protected original-audit corpus and three development
  refs in [DEVELOPMENT](DEVELOPMENT.md#evidence-and-retention) a decision against
  the new criterion. Preserve originals needed for a substantive evaluation;
  historical reachability alone is not a continuing research purpose.

### 2. Replace indefinite retention with a small working rule

- [ ] Revise [AGENTS](AGENTS.md),
  [DEVELOPMENT](DEVELOPMENT.md#evidence-and-retention) and
  [ACCEPTANCE](ACCEPTANCE.md#what-a-test-run-keeps) together. Keep detailed
  evidence while reviewing a run or investigating a failure. After review,
  keep only selected artifacts with a current inspection purpose. A document
  citation must not preserve an entire run directory or its build caches.
- [ ] Simplify [the qualification tooling](apparatus/qualified.py) around
  current test evidence and selected evaluations. Release obsolete pins and
  remove routine historical records from the active index. Do not require
  old test environments merely to inspect a completed model encounter. Check
  [packet preparation](apparatus/sanity/packet.py) and
  [study-build bindings](apparatus/c10/study_build.py) before removing records
  they still consume; preserve exact admission checks for new launches.
- [ ] Use a short inventory of the selected archival artifacts and their
  purpose, at the existing result/index location. Avoid a new disposal ledger,
  per-cleanup report hierarchy, general migration service or parallel account
  of the same work. Removing evidence changes what remains inspectable; do not
  rewrite a historical result to suggest that its checks or failures differed.

### 3. Make generated test material disposable in practice

- [ ] Change [the acceptance runner](apparatus/container/acceptance-inner-driver.sh)
  and [host suite](apparatus/acceptance.sh) so ordinary runs stop accumulating
  every successful test's working files and another full `work.tar`. Keep
  witnesses and originals needed during review, for unresolved failures, and
  for explicit missing-capture/deletion investigations. Select exceptional
  retention for a named purpose instead of defaulting to `--keep-work all`.
- [ ] Give launcher rehearsals, local check output, staging source copies and
  build caches the same lifecycle. Working output can be replaced or removed
  once consumed. Preserve the observed failure and relevant evidence while it
  matters; a fixed reproducible defect normally belongs in a regression test.
- [ ] Apply the rule to the remaining acceptance/rehearsal folders. Keep the
  current result needed for evaluation and any specifically selected anomaly;
  release completed historical timing comparisons and redundant generated
  payloads. Retain only the necessary snapshots of real encounters, keeping
  originals and attribution intact. Do not build a deduplication system to
  preserve material that has no remaining purpose.

### 4. Leave one intelligible working input for the team

- [ ] Reduce active plans to remaining decisions, work and concrete inputs.
  Remove completed campaign narratives and repeated evidence inventories.
  Keep substantive findings with their results; put adopted behavior and its
  reasons in the specifications. Move necessary current decision material out
  of disposable scratch folders before pruning them.
- [ ] Review the historical requests/advice in `riker/` and study-specific
  preparation scripts. Keep reusable procedures and advice still needed for a
  live decision; remove superseded administration from the working tree.
- [ ] Retire the two historical worktrees after preserving any selected patch
  or input. Remove duplicate dependency/source copies and unrelated temporary
  tooling. Keep ordinary Git history, not extra checkouts for hypothetical
  reconstruction. Keep temporary instructions and assistant entry points as
  aliases to their existing owner, not separate rule sets.

## Checks and completion

Follow [DEVELOPMENT's change table](DEVELOPMENT.md#what-to-run-for-what-you-changed):
link checks for prose; qualification self-test and record check for its tooling;
shell syntax and scheduled Linux suite/rehearsal for runner changes; the named
launcher checks for shared launch changes. Driver edits require an author who
has not read the implementation. No service behavior change is expected.

Verify that current builds and tests still have their inputs, that new launch
bindings can be prepared without deleted historical records, and that each
selected evaluation can be inspected from its retained originals. Exercise
normal disposal and an exceptional retained-failure case without losing the
independent witness under review. Report remaining storage, outstanding audit
state and any intentionally uninspected material plainly.

Finish when the working checkout and instructions serve the current team,
generated output has a finite working lifetime, and every retained archive has
a concrete inspection purpose. Move enduring rules to their owners and delete
this plan.
