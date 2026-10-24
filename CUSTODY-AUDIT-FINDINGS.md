# Existing custody responsibilities: stage-2 audit

Status: investigation complete; independent review resolved. Production baseline
`6582df2c0fd9f27941b933336f6150d83b3a53fa`; no production changes or commits.
`DEVELOPMENT-PLAN.md` owns the commission and sequence. Recommendations here do
not change operative custody obligations. Implementation remains uncommissioned.

The main distinction is between preserving the identity and accountability of
work, and requiring every surrounding facility to remain usable before any
part of that work may proceed. Stewart needs the former. Several instances of
the latter warrant narrower contracts, but narrowing close requires deciding
what evidence its removal covers, not merely deleting an inconvenient check.

## Responsibility map

These are responsibility families, not one product decision per error code.
Source paths below are relative to `src/stewart/`; line numbers refer to the
unchanged production baseline. The source inventory at
`.scratch/custody-audit/source-reasons-01.json` covers 36 top-level modules,
543 `reason=` call sites, 166 distinct literal identifiers and 18 dynamic sites.
It excludes positional helpers, generated diagnostics and bundled guidance;
it is a coverage aid, not proof every refusal was exercised.

| Family | What Stewart protects; who must do what | Cost and recovery | Recommendation |
| --- | --- | --- | --- |
| Commission and target | The manager states the question, scope and stop; preparation binds an exact prompt and target. One control object, required sections, target ancestry and input equality prevent silent substitution. | A one-parent, prompt-only commit, working prompt equality and no intervening non-workspace changes impose history discipline. A changed question/input population needs a fresh commission. | Retain exact binding and explicit scope. Keep current history shape provisionally; it is one binding mechanism, not itself the mission. An amendment mechanism would be an addition. |
| Input and writable populations | Committed regular files and hashed supplemental files have explicit identities; absence cannot reduce the denominator. Inputs cannot overlap writable outputs. Availability of a full checkout does not expand permission. | Managers arrange missing inputs or commission afresh. Pinned inputs inside gitlinks currently encounter contradictory repair instructions; see D3. | Retain population and non-overlap. Fix the contradictory permitted path contract. |
| Participant claims and holds | Auditor declarations, manager stop/pause acknowledgments, observed bytes and process results remain separate. Stewart does not infer completion from prose. | Managers actually stop writers and communicate resumption; Stewart records their acknowledgment. A failed preparation does not silently release a real hold. | Retain attribution. Human handoff, human auditor, and a manager resuming after user approval are distinct arrangements. No launch/watch duty transfers merely because a user intervened. |
| Access boundary | Scope denies manager/private custody and other checkouts while granting task-specific access. The manager supplies applicable project rules through accessible guidance. | Scope is a snapshot: later checkouts or manager entries can require stopping and repreparing affected auditors. Supplied settings do not demonstrate real harness enforcement. | Retain private-custody protection. Keep this continuing coordination duty explicit; do not promise its elimination without a replacement boundary and qualification. |
| Raw return preservation | After safe session/writer/owner identification, collect captures raw report bytes before declaration, handoff, retention and supplied-runtime checks. Missing/invalid claims become gaps. | A different writer or missing owner can block capture before those raw bytes are acquired. Unkeyed retries create new captures. Partial allocations survive failures. | Retain capture before interpretation and safe source identity. Do not describe capture as unconditional. Correct the already accepted stamp-before-effects issue when implementation is commissioned. |
| Receipts and control metadata | Exclusive creation, duplicate-key rejection, schema/identity checks and verified descriptor reads prevent overwrites and ambiguous interpretations. Hashes bind bytes to recorded pins. | Corrupt/unreadable records remain diagnosed; only a missing final record supports incomplete/unresolved classification. Retry means a new record, not repair of history. | Retain. Pins establish consistency, not authenticated participants or trustworthy scientific claims. Raw payloads remain opaque where the control rule does not apply. |
| Disposition | A response binds one collection name and receipt digest plus the report bytes. Managers disposition every gap and explicitly answer valid evidence/reframe requests. | Identical reports in different collections do not share a review automatically. Structural validation cannot judge the adequacy of the explanation. | Retain exact binding. Retain per-gap review provisionally as an explicit managerial obligation; it is more than the act of preserving bytes. |
| Retention and export | Only verified captured selections may be published or packaged. Import conveys custody, not execution authority or acceptance. Selected runtime groups must be complete. | Publication destinations are exclusive. Current report-only consumers also validate omitted runtime observations; original export needs an owned, writer-compatible session, unlike later package import. | Retain selections, source pins and no live fallback. Narrow unrelated availability gates only under D2; ownership/writer relaxation is a separate choice. |
| Experiment authority | A manager releases exact reviewed script/artifact/input identities within a grant; run revalidates them. Construction-only grants confer no execution. Reviewed IDs determine measurement membership. | One attempt consumes one release before validation; uncertainty needs a new conscious release. Python script/minimal environment and inherited manager-harness limits restrict projects it can serve. | Retain effect authorization, membership review and no uncertain replay. One invocation is per release, not a session-wide trial budget. Do not infer scientific validity or universal project-check capability. |
| Request keys and selection | Callers retain explicit references/keys; Stewart revalidates lifetime, records intent before effects and does not choose by recency. Only supported operations resume partial work. | A fixed refused key stays refused after its cause is repaired. A refusal may follow retained side effects; it does not mean nothing happened. Draft references do not acquire later sessions. | Retain identity and no replay of uncertainty. Keep completed request, completed collection, auditor completion and accepted answer distinct. |
| Writer continuity | Mutations require the recorded package identity, including bundled guidance. Verified handoff offers recorded code explicitly without running it. | Compatible schemas alone do not suffice; completed keyed retries also require the old writer. Missing retained launcher/interpreter blocks the offer. | Retain until D5. Rust succeeding Python is an authority decision, not a compatibility shortcut. Read-only inspection remains distinct from mutation. |
| Conclusion and abandonment | Conclusion needs bound triage, verified checkout capture, no unresolved hold/attempt and an unchanged judged checkout. Abandonment records its reason and explicit discard permission where required. | Current conclusion additionally inherits status's live-runtime/handoff and even command-rendering failures. Private session evidence is removed at close; managers retain/export what should outlive it. | Retain accounted-for closure, not perpetual storage. Resolve D1 before weakening sidecar gates. Distinguish optional advice from mandatory preconditions. |
| Resource removal | Only CLOSING and gated exclusive resource claims authorize their recorded inventory. Enrollment, paths and Git registration do not. Uses, ownership and frozen identity/content are revalidated; changed resources remain. | Failed cleanup leaves records and can require restoring the judged state. A kept checkout can permit later cleanup to continue; D1 addresses that distinction. External/enrolled resources remain outside disposal authority. Containers depend on all recorded children; doubt keeps resources. | Retain. Do not flatten this into generic recursive deletion or infer removal permission from a resource being inconvenient. Session sidecar content has a different current boundary, discussed below. |

Principal source anchors: `prepare.py:93–180,210–310`,
`assignment.py:41–72,153–211`, `auditor_scope.py:32–106`,
`collect.py:423–502,558–576`, `session.py:131–289`, `_json.py:21`,
`report_declaration.py:136–170`, `triage.py:129–213,264–294,444–479`,
`captured.py:20–41,135`, `handoff.py:168–186,286–352`,
`experiment.py:70–163,240–335,406–419,452–506`, `ledger.py:162–267`,
`request_keys.py:171–278,344`, `audits.py:576,690`,
`implementation.py:139–160`, `close.py:905–1000,1101–1154`,
`holdings.py:1146–1245,1363–1400`, `_removal.py:1–125`.

## Recommended decisions, reserved to the user

### D1 — Close should account for what it will discard

Recommend an explicit account-before-discard boundary for every evidence-bearing
surface close removes. It should distinguish already captured and reviewed
runtime damage from new unaccounted changes. Known regenerable material may
have a declared disposal rule; otherwise preserve/capture the changed material
or require explicit bounded discard acknowledgment. This does not mean every
byte must be archived forever: close deliberately ends private custody, and
retention/export determines what survives it.

The current original-runtime gate tests equality with preparation, not coverage
by a later collection. It can block already captured damage. Conversely,
recovered runtimes and experiment HOME enter the session's recursive removal
inventory without equivalent current-content checks. A recovery is regenerable
while it matches the retained copy; newly written inspection work is a different
case. HOME is child-writable outside the captured checkout. Whether its contents
are disposable scratch or part of the audit's evidence cannot be derived from
its pathname alone.

Source: `runtime.py:1–6,298–351`, `experiment.py:310–325`,
`close.py:322–405,502–545`; manual `resources/README.md:1898–1931` and
`resources/MAINTAINER.md:17–24`. Final/resumed close revalidation covers the
checkout, so the original-runtime gate is not even a complete protection against
changes after CLOSING. The existence of a removal member freezes a location,
not the contents it will later contain.

The status inquiry established a separate incidental coupling: a damaged cached
manager launcher can prevent close by failing generation of a suggested command,
even with matching loaded writer bytes. Recommend that a close-owned assessment
judge closure facts directly. Removing rendering dependence should not remove
writer authorization, captured evidence validation or frozen resource checks.
Handoff damage may also be evidence; do not treat it as merely unavailable UI.

The reliance change to approve: a participant may conclude with a runtime that
no longer verifies against its preparation pin when its relevant contents are
accounted for, while neither a
successful old recovery nor a declared HOME location alone authorizes discarding
new work. The desired sidecar/discard categories need a user decision; designing
those categories is not secretly delegated by the status grant.

Two related source findings need explicit disposition within that decision.
Direct close can select an older triaged collection even when a later untriaged
return records different runtime observations with identical checkout bytes.
Recommend requiring the closing account to address consequential later evidence,
without requiring every optional retention or experiment suggestion to be done.
The precise applicability rule remains open; this inquiry did not execute that
later-return comparison. Separately, a substituted/moved checkout can be reported
as kept while subsequent session removal proceeds (`close.py:464–552`), whereas
failed checkout revalidation stops cleanup. Recommend retaining associated
custody evidence until the kept checkout's disposition is settled. This is a
proposed change to partial-cleanup behavior, not a consequence already enforced
by descriptor safety. No new kept-checkout comparison was executed here.

### D2 — Permit independently verified selected custody with surrounding damage

Recommend allowing export of an intact selected report and its exact source
receipt while explicitly carrying the fact that surrounding runtime custody is
damaged. Preserve the damaged original, refuse invalid selected bytes, and make
no claim that the whole collection is sound. A diagnostic must survive export
when it materially qualifies the source; omitting a failed group is not proof
that it was healthy.

Current `captured.load_collection` validates the entire runtime observation group
before even a REPORT-only selection. Initial recorded capture failure is usable,
but later damage to a formerly complete observation blocks report-only export.
An already-created report-only package does not depend on the omitted group
when imported. This is the existing documented policy
(`tests/test_stewart_runtime.py:71–85`; manual `resources/README.md:1916–1931`),
not simply an accidental exception to erase.

The reliance change to approve: selected custody can remain valid despite
explicitly damaged surrounding evidence. This does not authorize triage to
pretend there were no gaps, nor relax full-capture closure or selected runtime
verification. A first implementation can limit this to export; changes to
triage/retention and original-owner/writer admission require their own rationale.

### D3 — Remove the contradictory supplemental-input path contract

Recommend refusing a supplemental destination below a gitlink before allocation,
with an instruction to pin the supplied copy at an ordinary path. This preserves
the current exclusion of populated submodules without suggesting that moving an
already pinned input during an audit is a valid repair. A later submodule design
may choose a richer distinction between pinned copies and unexpected contents.

Current prepare recommends supplying submodule material as supplemental inputs
and admits such a descendant; exact matching bytes avoid `unexpected_path`,
yet `gitlink_contents` still appears and its repair instruction says to move the
file. Sources: `prepare.py:101–110`, `assignment.py:168–180,453–460`,
`collect.py:351–367,698–702`, `report_declaration.py:325–326`.

This recommendation narrows accepted preparation paths. An alternative is to
allow explicitly pinned descendants and distinguish them during diagnostics.
That alternative is feasible in principle but must not accidentally imply
populated-submodule support. Whichever is chosen, preserve captured contents;
no retroactive rewriting of historical assignments or receipts.

### D4 — Make launch acknowledgments applicable to people

Recommend retaining actor, channel/style and attributed handoff information,
while making model/effort applicable only to an agent arrangement. Current
`style=other` still requires nonempty model and effort
(`coordination.py:98–118`). Invented model values add no useful custody fact.

The reliance change is only representational. It does not establish a delivery
service, require a watcher, transfer responsibility after human approval, or
promise that a recorded launch acknowledgment proves activity. The user has
left entrypoints open and wants the manager/auditor connection abstracted by
Stewart where practicable. Delivery duties remain an independent decision.

### D5 — Choose the writer-continuity policy before Rust mutates old lifetimes

Recommend retaining existing Python writers for their open sessions and making
Rust read-only toward those lifetimes initially. Keep explicit verified handoff;
never execute retained code implicitly, add compatibility shims or rewrite
receipts. This is the conservative default, not a conclusion that successor
custody must always remain impossible.

If the desired product requires Rust to continue old sessions, explicitly grant
successor authority and specify its evidence, supported record population and
failure treatment. A narrow read-only return of a completed keyed outcome is a
separate candidate from permission to append new custody records. Package pins
do not authenticate actors or attest to interpreter bytes or in-memory objects.
Source: `session.py:60–79`, `implementation.py:139–160`,
`request_keys.py:212–243`; current tests `test_request_keys.py:628–657`.

### D6 — Keep access and experiment capability promises qualified

Recommend retaining current private-path and effect-authorization obligations,
while making their operational costs explicit. The access snapshot imposes
ongoing coordination even on a snapshot audit
(`resources/README.md:1950–1980`). Eliminating that duty needs a different access
arrangement and real harness qualification, not only rearranged settings.

An HTTPS-only assignment can be structurally valid while the supplied adapter
has no permitted network domains; the Python/minimal-environment experiment route
may not serve a project's real system checks. Route project rules through the
supplied accessible guidance; do not assume automatic loading. No real external
retrieval, system-project experiment or harness enforcement was qualified here.
These remain concrete stage-3 capability candidates; source restrictions alone
do not prove an exploit or justify bypassing them.

## Implementation defects under retained commitments

Git trust needs a consistent argument across preparation, verification and
cleanup. `_git._invocation` disables hooks and fsmonitor and drops four
redirection variables, but leaves configured filters and other inherited Git
behavior. Preparation invokes `worktree add`. A harmless configured filter
sentinel fired during preparation with a matching attribute; it did not fire
with the attribute unmatched or the filter unset. Assigned input bytes were
unchanged in every case. The command came from repository configuration and
the harmless script was outside the checkout. This demonstrates configured
command execution, not that tracked content alone chooses arbitrary commands,
nor that a real harness can be bypassed.

`assignment.expected_inputs` follows replacement objects, while
`coverage.prompt_identities` explicitly disables them. Holding the selected
commit fixed, the executed replacement-object comparison changed the input pin
to replacement bytes while coverage continued to identify the original bytes;
removing the replacement restored the original pin. Do not describe this as
full end-to-end acceptance of a forged
commission; the probe isolates input-pin construction versus capture coverage.

Retain the intended no-unauthorized-execution and immutable-object identity
commitments. Address these demonstrated boundaries in implementation;
do not weaken the guarantees to excuse current Git behavior. A complete
configuration/environment policy and adversarial qualification remain work for
that implementation, not established by one sentinel.

## Historical decisions reconciled

The captured input `planning/inputs/custody-questions.md` and archive commit
`d4b99f6` are leads and prior decisions, not a dormant task queue. They remain
unchanged. Source inspection confirms continuing relevance of these accepted,
not-yet-implemented items:

- Compute implementation identity before allocating collection/run/recovery
  state; Git metadata timeouts should leave commit/dirty unknown. Collection
  currently allocates before its stamp (`collect.py:440–464`); recovery has the
  same ordering (`runtime.py:321–328`).
- Replace the porcelain branch query after comparing attached, detached, unborn
  and chained HEAD. `collect.py:183` still uses `branch --show-current`. No new
  four-case comparison was executed here; the prior decision remains.
- Bind the last required observation to the value actually written or used;
  retain it through removal. This remains a cross-cutting implementation rule,
  not proof that every race has been eliminated.
- Count hidden executable-bit changes in capture coverage. Current
  `captured.entry_identity` and `coverage.prompt_identities` reduce regular files
  to kind/content, so the accepted mode-sensitive policy remains unimplemented.

Prior acceptance of withholding offered close without an extra capture alarm,
collection not recording its own coverage, stopping capture rechecks after the
checkout is gone, and requiring restoration for a stopped close remains visible.
The stage-1 public contract changes advice; it does not silently reverse the
closure decisions. Direct close may conclude an older triaged complete
collection if its actual capture/checkout prerequisites hold, whereas status
withholds close when newer triage or retention/release/run options remain.
Recommend keeping optional advice separate rather than inventing a duty to
finish every possible follow-up before conclusion.
That does not settle whether later consequential evidence must be addressed;
D1 reserves that question explicitly.

Other leads are bounded as follows. Supplemental gitlink destinations and
replacement views receive focused comparisons here. Relative worktree
administration, submodule-recursion configuration and general inherited Git
configuration remain unqualified. Descriptor-relative payload reads and removal
now exist; the path-based `_walk` is name discovery and does not itself establish
an arbitrary payload-read exploit (`collect.py:200–244`). Name traversal races,
concurrent unkeyed closes and selective progress after a changed resource merit
implementation review; no new safety proof is claimed. Issuance/preparation
splitting, a final preparation receipt, acceptance receipts and live checks on
retained published files remain optional changes, not inferred duties. Failure
exit codes must not imply that no effects occurred; failed preparation and
recorded keyed refusals can retain evidence. Missing and corrupt records retain
different diagnoses. No historical report was rewritten to fit this account.

## Evidence, review and disposition

New investigative files characterize current behavior; they are not regression
assertions that the behavior should remain. Future implementation must revise
or retire those expectations deliberately. Production source, bundled guidance
and existing tests remain unchanged. Stage-1 evidence is recorded in
`STATUS-INQUIRY-FINDINGS.md` and is not rerun merely to increase test counts.

Three source workers supplied responsibility maps and authored isolated
comparisons; the coordinator owns Git comparisons, integration and judgments.
An independent reviewer checked the premises, controls, integrated account,
outcomes, every retained observation copy, source/receipt/wheel hashes and
inventory counts. All findings are resolved. Review sharpened the distinction
between a changed runtime and non-executable code, frozen removal and executed
deletion, causal restoration and safe recovery, and source-staging versus
executed-test evidence. No paid audit, real auditor or
external harness is part of these probes.

### Executed comparisons

| Question and selector family | Measured result and control | Limit |
| --- | --- | --- |
| Original runtime, four `test_custody_close_original_runtime_capture_boundary` cases | Intact and unrelated-change controls permit close. The same runtime damage before collection is actually captured and triaged; damage after collection is absent from that archive. Both produce `runtime_unavailable` and `close_unverified`, exit 3. Restoring original runtime bytes permits close without changing the receipts. | Restoration is a disposable-fixture causal intervention, not recovery advice: preserve uncollected changes before any real restoration. This is a planning comparison, not execution of close. |
| Recovered runtime and experiment HOME, two close cases | New recovery-directory bytes and synthetic HOME bytes leave close allowed and appear under the actual frozen CLOSING removal members. Adjacent-file invariance and intact recovery capture distinguish location from captured content. | `_finish` is intercepted after CLOSING publication and before removal/claims. No deletion was performed; HOME writes are synthetic, no child ran. Source establishes the later recursive-removal path. |
| Selected report export, three identity cases | Intact control and explicitly recorded initial runtime-capture failure export successfully. Later retained-runtime damage refuses with `evidence_tampered`, despite unchanged report/receipt/live runtime. Previously exported report-only package remains importable in all cases. | This establishes availability asymmetry, not authority to ignore corruption or authenticate a report. Initial storage failure is an injected ENOSPC at production capture. |
| Supplemental path, three scope cases | Preparation and input verification accept the pinned descendant. Its `gitlink_contents` remedy moves it and causes a missing pinned input, exit 3. Identical approved bytes outside an empty gitlink are clean; moving an unassigned descendant clears its gap, exit 0. | The approved path varies while bytes and population size stay fixed. Fixture remedies happen after preserving the initial collection. No populated-submodule support is established. |
| Human acknowledgment, one scope case | Missing model/effort refuses before writing. Explicit not-applicable strings and ordinary agent metadata both record attributed acknowledgments. | No human, agent launch, delivery, activity or responsibility transfer is observed. |
| Git filter, three cases | After correcting the fixture, only the matched configured filter writes its marker; all three preparations succeed and assigned bytes remain identical. | Configured command execution, not a harness escape or a complete Git hardening assessment. |
| Replacement view, one case | Input pin follows replacement bytes; coverage stays with original bytes; removing replacement restores input pin. | Component comparison, not end-to-end forged assignment acceptance. |
| Existing guards, nine selectors | Six verified-capture close variants, two replacement-object coverage variants and one different-writer keyed-retry refusal all pass. | Focused continuity checks, not a full-suite run. |

Run with `/opt/homebrew/bin/python3.14 -I -B scripts/check.py`, the provisioned
`.scratch/wheelhouse`, explicit selectors and `--keep-artifacts all`. The runner
builds/installs a wheel and stages the suite in an unrelated directory with
isolated pytest configuration. Actual argv/cwd and output are retained in each
run's `.pytest.log`, `.log` and `.out`.

| Receipt under `.scratch/custody-audit/` | Collected / selected | Outcome | Time |
| --- | --- | --- | --- |
| `comparisons-01.json` | 26 / 26 | 25 passed, 1 failed; 0 skipped/deselected | pytest 22.83 s; total 25.311 s |
| `git-filter-02.json` | 3 / 3 | 3 passed; 0 failed/skipped/deselected | pytest 1.01 s; total 3.268 s |

The first failure was a probe error: a required smudge filter had no clean half,
so Git refused in `maintainer_state` before the intended checkout observation.
Adding the inert `clean=cat` configuration fixed the fixture; all three filter
controls were rerun. No production change was made. There are 26 distinct
selected nodes with passing evidence after correction; the historical execution
totals remain 29 executions, 28 passed and 1 failed. The scope test's docstring
was clarified after run 1 without a behavioral change or a redundant rerun.

Both runs used Python 3.14.8, Apple Git 2.54.0 (Apple Git-157), and the identical
production wheel SHA-256
`43da134c32731f783f74aff6bfe997a8b8078a899e71f1a264c0fb02a846a94f`.
`comparisons-01-evidence/manifest.json` binds 83 immediate observation/fixture
files and four staged inquiry sources; `git-filter-02-evidence/manifest.json`
binds seven observation/fixture files and four staged inquiry sources (only the
Git file's filter cases executed in that second run). Each copy was byte-checked;
test-source hashes match the runner's staged-suite hashes, including the
reconstructed pre-correction source. Manifests also pin their run receipt and
wheel. These are comparison evidence, not transferable audit packages or usable
commands for the fixture coordinates printed within them.

After independent review, both working artifact directories were removed through
`scripts/prune.py --run custody-audit/<stem> --apply`. Their `*-prune.out` and
`*.pruned.json` files name the removal records:
`.scratch/pruned/20261024T043214Z-84672.json` (123,994,112 allocated bytes,
7,108 entries) and `20261024T043219Z-84689.json` (15,253,504 bytes, 913 entries).
The tool reported that process-list access was unavailable; both runner sessions
had already exited and no worker ran tests. Receipts, logs, wheels, staged
inquiry sources and compact evidence remain. Printed fixture paths now refer
to removed working state, not recoverable audit sessions.

The audit can finish with recommendations and explicit unresolved choices.
D1–D6 remain proposals for the user's assessment. Stage-3 additions and production
implementation require their own commission. This report and its new tests are
ordinary development materials; extra engagement accounts remain in the
fieldwork run's notes. After this report has served its decision/implementation
purpose, transfer enduring contracts to maintained documentation/tests and
active decisions to the plan, then retire the report under the run-retention
rules. It is not a runtime dependency.
