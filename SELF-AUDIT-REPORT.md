# Stewart self-audit: consolidated remediation report

This is the durable handoff for three Stewart audits commissioned and reviewed
on 2026-10-18/19. A later remediation agent needs this report, the committed Git
command log and the current project source/tests. No old audit session,
linked checkout, private receipt, package, virtual environment or scratch
directory is a prerequisite for reproducing or repairing the findings below.
Historical digests identify the evidence reviewed; they are not instructions to
recover discarded artifacts. Appendices contain the reproduction code and inputs.

No product fixes were made. The audited source is commit
`0aaa6eafa06722add123105da912c906b8608633` on `rehome`. The consolidation commit
adds documentation only. Source locations below refer to that audited version;
prefer function/test names when line numbers move during remediation.

## Findings and order of work

| ID | Finding | Observed consequence | Recommended treatment |
| --- | --- | --- | --- |
| F1 | Close traverses a linked top-level checkout ancestor | An outside decoy file is deleted on initial abandon and interrupted retry | First: make removal ancestor-safe; preserve outside state in regression tests |
| F2 | Close retry treats a reused Git administrative pathname as the old lifetime | Another live audit is falsely reported as the old audit's leftover; retry/status exit 1 | Bind registration discovery to the recorded lifetime, not just its pathname |
| F3 | Recorder equality can change through JSON serialization | Surrogate string/key aliases change equality and produce inconsistent mismatch flags | Define/enforce a serialization-stable operand domain or comparison relation |
| F4 | Review accepts whitespace-only case IDs that ledger rows reject | A reviewed case cannot be validly declared; prerequisites cannot pass | Align release-review and row validation without silently changing accepted IDs |

F1 requires manager-side corruption of the checkout parent, beyond the assigned
auditor's write boundary. It is not evidence that an auditor confined to its
worktree can plant that parent link. F2 preserved the other audit and its lifetime
marker; no cross-session deletion was observed. F3/F4 are visible failures,
not demonstrated false acceptance. These distinctions affect priority and must
survive issue creation and repair descriptions.

The package audit established no new package-binding defect. The ledger audit
found no reviewed-membership bypass with `ledger.unmet == []` in the examined
source and bounded comparisons. Neither result is a universal correctness
claim. Additional regression and wording improvements are listed separately.

## Questions commissioned and evidence classes

1. **Information preservation — close/removal.** “Does the identity and scope
   of a session's removable resources survive the route from session/registry
   observations through CLOSING.json to the actual deletion operations, on both
   the first close and an interrupted close's retry?” The decision was whether
   to rely on recent close hardening or require repair/narrower claims.
2. **Receipt sufficiency — one exported package at rest.** “Does the evidence
   package exported from close-removal-boundary-01, collection
   20261019T050641-36a1489d, support a receiving maintainer's claim that it contains
   the exact selected report, notes, and supplied Stewart runtime from that
   audit?” The decision was what a recipient could cite without the source
   session, and whether further capture was necessary.
3. **Instrument discrimination — released-review ledger.** “Does Stewart's
   released-review ledger verifier distinguish a complete set of uniquely
   identified reviewed measurements from omitted, duplicated or substituted
   measurements that have plausible row counts and a firing control, while
   ignoring only the variations its documented contract permits?” The decision
   was how to use summary, anomalies and unmet prerequisites in a zero-disagreement
   claim.

All three assignments were bounded static reviews in snapshot mode. Auditors
could read selected implementation/tests and use issued identity/declaration
helpers; the package auditor additionally had bounded archive inspection.
Auditors were not granted project execution, trial scripts, fixes, external
research or delegation. Their proposed contrasts are predictions. The manager
separately reproduced close behavior, verified package bytes and ran the ledger
contrasts described here. Existing test assertions, retained test outcomes,
manager observations and untested hypotheses are distinguished below.

The user separately reported each auditor stopped and its session terminated.
Collections record the manager's `finished` acknowledgment. All three auditors
declare a complete `answer`; each declaration's six identity comparisons verify,
and each collection has no recorded custody gaps. Harness exit records report
0 at 05:05:44Z, 14:57:53Z and 16:07:51Z on 2026-10-19, respectively. Neither
exit status, declaration nor collection consistency is a grade of the audit.

Operational tooling: installed Stewart 0.1.0, wheel SHA-256
`6da481dd5acacf5b7308d3198a98c9ad127067a5cd34ecce957acd4b2707e313`;
source package inventory SHA-256
`3836f057d1d0b53e2c2c9321ede329af107ce3eb7a5f0656896eb93dc78d21c5`;
complete retained runtime SHA-256
`3e27136d845c87954bec5b38e2726d1cc716c070a0d9ade983c3bc2f63faab2c`.
Manager confirmations used Python 3.14.8 on macOS. Close comparisons used
Git 2.54.0 (Apple Git-157); `shutil.rmtree.avoids_symlink_attacks` was true.
Claude Code 2.1.303 was requested with Opus/max. CLI help, settings construction
and compatibility do not qualify actual filesystem or shell enforcement.

## F1: deletion follows a substituted checkout ancestor

**Route and first unsupported assumption.** In `src/stewart/close.py`,
`_remove.remove_worktree` (:397–420) passes the recorded worktree pathname to
Git or `_remove_tree`. `_remove_tree` (:344–360) tests the leaf for a symlink,
walks/chmods directories and calls `shutil.rmtree(path)`. A symlink in the
worktree's parent is traversed during pathname resolution before those leaf
checks. `_not_real_between` protects recorded runtime members, but this
worktree-removal route does not provide equivalent pinned-ancestor custody.

**Reproduction, in a disposable repository only.** Prepare/collect/triage a
normal audit A using the existing `checkout` fixture and `test_close._triaged`.
Let `worktree = prepared.worktree` and
`audit_dir = Path(prepared.prepared['audit_dir'])` (its UUID-named parent).
Create an unrelated decoy directory containing `worktree/keep.txt` and a
separate sibling sentinel. Rename the real `audit_dir` to a held sibling, then
make its former pathname a symlink to the decoy. Initially both sentinels exist.
Call `close(..., abandon=True, reason=..., discard_uncollected=True)`.
Observed: the decoy's `worktree/keep.txt` is deleted, the unrelated sibling
sentinel survives, and close writes its completed record. These parent-link
comparisons return exit 1 because of kept leftovers; that diagnostic does not
undo the outside deletion. The held original directory is not evidence of safe
removal.

For the retry route, first monkeypatch `closing.git` to raise `StewartError`
on `('worktree', 'remove', ...)`, allowing an ordinary concluded close to write
its closing inventory and fail before removal. Restore Git, perform the same
parent substitution, and retry normal close. The outside sentinel is again
deleted. Appendix A provides the exact fixture code for both routes.

| Link position | Initial abandon | Interrupted retry |
| --- | --- | --- |
| Link inside the worktree | Outside sentinel preserved | Outside sentinel preserved |
| Link at worktree leaf | Outside sentinel preserved | Outside sentinel preserved |
| Link at UUID-named worktree parent | Outside sentinel deleted | Outside sentinel deleted |

The independent sibling sentinel survives in all six arms. This distinguishes
top-level ancestor traversal from ordinary leaf-link handling. It does not test
mount substitution, every filesystem, or a concurrent active attacker.

**Repair contract.** Validate and pin the directory chain used for actual
deletion, not just a previously observed string or leaf type. Refuse or keep a
substituted parent without traversing it; the retained diagnostic must name the
condition. Cover initial concluded/abandoned and resumed removal where relevant.
Preserve the outside sentinel in all link-position arms and preserve unrelated
siblings. Add a healthy real-directory removal control, and retain the existing
inside/leaf invariance cases. A prior `contained` check alone does not prevent a
late ancestor replacement. Do not “fix” the old closing receipts or broaden a
retry's removal inventory.

## F2: administrative-name reuse misattributes another audit

**Route.** `_registered_elsewhere` in `close.py:243–258` recognizes a session by
either a UUID-bearing lock reason or the `gitdir` file found at its recorded
Git administrative pathname. The second route does not establish that the
administrative directory still represents the recorded lifetime. Git can reuse
that basename after the first checkout is removed. `_remove.remove_worktree`
then treats the replacement audit's registered path as the old audit's leftover.

**Reproduction.** In disposable fixtures, prepare/collect/triage A. Temporarily
make `closing.git` raise on `update-ref` so close removes the real worktree but
fails at the later retention-ref step. Preserve `CLOSING.json`; note
`removal.git_admin`. Restore Git. Prepare independent audit D *after* A's
removal, and require the firing condition that D's actual administrative path
equals A's old path. Retry A's close.

Observed: `kept: registered elsewhere`, leftover `checkout registered at <D>`,
retry/status exit 1, although D's checkout and marker survive unchanged. The
marker field is `role_uuid`, which equals D's `session_uuid`. This is false
attribution, not observed deletion or mutation of D.

| Arm | Administrative reuse | Retry worktree outcome | Leftovers / exit |
| --- | --- | --- | --- |
| No other audit | No | absent | none / 0 |
| D prepared before A is removed | No | absent | none / 0 |
| D prepared after removal, same admin path verified | Yes | kept: registered elsewhere | D falsely attributed / 1 |

The before-close arm is the invariance comparison: merely having a second live
audit is insufficient. If Git does not reuse the admin path on another host,
the required sensitivity condition did not fire; that is not a clean result.

**Repair contract.** Make the `gitdir` fallback prove the recorded lifetime,
using the existing marker/UUID/registration contract or an equivalently pinned
identity. A replacement lifetime must not be claimed as A or touched by A.
Retain support for a genuinely moved checkout of the same lifetime. Permanent
tests should make the post-removal reuse case produce no false D leftover,
preserve D's marker and contents, keep the other two arms unchanged, and still
recognize a real move. Re-run all close/recovery checks, not just this probe.

## Package audit: accepted narrow claim and exclusions

The examined package contained seven files: its manifest, exact source
collection receipt, selected report, two notes, and pristine runtime
manifest/archive. The receiving assignment pinned those bytes. The manager
verified the exact seven captured package files, all 39 regular runtime archive
members (membership, size, digest), and report/declaration consistency, without
consulting the originating live session.

Accepted citation, with its trust premise intact:

> Package `close-removal-package-01`, manifest SHA-256
> `f7bc6a19a36a57ca01bd0ce3da677256637a2bb3ef6ec48296c2ea72419b6137`,
> preserves the selected report, two notes and pristine Stewart runtime assets
> byte for byte as recorded by the retained source receipt for collection
> `20261019T050641-36a1489d` of `close-removal-boundary-01`, assuming faithful
> recording and the trusted manifest pin. It does not establish authorship,
> exposed-runtime state, actual execution, or acceptance of report claims.

No new implementation defect was established in `handoff.package_inputs`,
`captured` or the selected bindings. Hashes do not authenticate the historical
collector; a fully self-consistent receipt/manifest replacement before a trusted
pin is outside this protection. Existing retained tests covered payload-tamper
refusal, full rehash acceptance and unchanged captured bytes after source removal.
That combination distinguishes internal custody from historical authenticity.

This package selected `runtime-assets`, not `runtime-observation:collection`.
A receipt's reference to an unselected observation and its empty errors list do
not reconstruct that observation. An explicit export of the existing observation
group would permit endpoint inspection, but still not establish uninterrupted
integrity or executed code. No such addition is required for the narrow claim.
Import acceptance likewise is not certification of every cached declaration or
inventory field. For this specimen, the manager separately reconciled those
fields using the one declaration parser; they agreed.

A second source-digest recording already existed in the committed first-audit
manager review. It improved association, not independent authentication; no
close was needed to create that anchor. Future package work should preserve
the same narrow assertions and tests rather than treat these documented limits
as a demand for a new authenticity mechanism.

## Ledger audit: the supported interpretation rule

The wrapper captures raw ledger bytes before parsing. `ledger.parse_rows`
validates accepted JSONL rows; `summarize(rows, cases=release['review']['cases'])`
recomputes operand disagreements and reconciles events/declarations with the
released review. The review owns membership. Only planned IDs recorded exactly
once after admission contribute to counts. Missing/duplicate/unexpected IDs,
sequence problems, admission/declaration conflicts and stale flags leave
prerequisites unmet. Parse problems are preserved separately and added by the
wrapper to `ledger.unmet` and `errors`.

Use `ledger.unmet == []` as the complete mechanical measurement gate. Only then
read zero ordinary mismatches as zero recomputed disagreements over the complete
uniquely identified reviewed ordinary measurements, as decoded from retained
rows. Quote the ordinary comparison count and bind the attempt to its release
record/digest. Inspect process, endpoint, runtime and custody outcomes separately.
`errors == []` or exit 0 does not imply measurement prerequisites passed.
`ledger.anomalies` alone omits parse diagnostics and firing/population thresholds.
Standalone `summarize(rows)` relies on child declarations; it does not verify
released-review membership.

Independent manager baseline: admitted ordinary A/B each require `canonical`
and `strict`; ordinary N is a planned refusal; control K requires both IDs.
All comparisons agree except B:strict and K:strict (`[1,2]` versus `[2,1]`).
There are 18 accepted rows, four ordinary and two control reviewed measurements.
K's difference tests the same array-order property as the ordinary strict mode.

| Change from baseline | Ordinary compared / mismatches | Control compared / mismatches | Result |
| --- | --- | --- | --- |
| none | 4 / 1 | 2 / 1 | unmet empty |
| Only B:strict ID becomes unreviewed | 3 / 0 | 2 / 1 | missing strict + unexpected ID |
| Only B:strict ID becomes canonical | 2 / 0 | 2 / 1 | missing strict + duplicate canonical |
| Omit B:strict | 3 / 0 | 2 / 1 | missing strict |
| B:strict operands genuinely agree, flag consistent | 4 / 0 | 2 / 1 | unmet empty |
| Only B:strict mismatch flag becomes false | 4 / 1 | 2 / 1 | inconsistent flag for B |
| K:strict operands agree, flag consistent | 4 / 1 | 2 / 0 | no firing control |
| Move K's disagreement from strict to canonical | 4 / 1 | 2 / 1 | computed summary/unmet unchanged |
| Valid interleaving / incidental metadata changes | 4 / 1 | 2 / 1 | each summary equals baseline |
| Move A:canonical before admission | 3 / 1 | 2 / 1 | unadmitted compare + missing ID |
| Append malformed line | 4 / 1 | 2 / 1 | parse diagnostic and unmet; summary unchanged |

The ID-substitution arm changes one field, preserves row count and the firing
control, and removes the ordinary disagreement from the numeric summary.
That is correct filtering with a nonempty gate, not false acceptance. The
genuine-zero arm distinguishes those interpretations. Valid case interleaving
and incidental metadata supply invariance comparisons; event precedence remains
significant. The malformed arm has 18 accepted rows plus one rejected line,
so an accepted-row count must not be described as a raw-line count.

Control firing is aggregate. It does not say which measurement mode fired;
inspect retained operands for any per-mode scientific claim. The comparison
also cannot establish operand truth, control relevance, reference independence
or question coverage. Those remain manager judgments.

## F3: Unicode serialization exception and a rejected auditor inference

`ledger._comparison_key` (:32–48) claims the same relation before serialization
and after parsing. Define `pair = "\ud83d\ude00"` (two surrogate code points)
and `scalar = "\U0001f600"` (one astral code point). They differ as Python
strings but serialize to the same JSON escapes. `Ledger.compare` returns true;
captured parsing recomputes equality and flags `inconsistent_comparisons`.
Identical ordinary scalars agree and distinct scalars disagree; a separate
reviewed control comparison continues to fire in all arms.

The object-key version uses expected `{pair: 1, scalar: 2}` and actual
`{scalar: 2}`. Distinct Python keys collapse on decoding, again changing the
comparison and producing the visible flag anomaly. The recorder's append path
(:107–131) accepts these operands; `summarize` (:197–199) detects the mismatch
between the pre-serialization flag and decoded operands. Appendix B reproduces
both forms without a session or child.

**Correction to the auditor.** The report/notes asserted that recorder dicts
cannot emit repeated JSON names, so repeated names prove another writer. That
inference is false: `{pair: 1, scalar: 2}` serializes as two identical escaped
names. The real recorder can emit them. If both operands are the same two-key
dictionary, the parser reports no problem and the flag can remain consistent.
The raw parser intentionally keeps the last value; it makes no uniqueness claim.
`sort_keys=True` preserves insertion-order invariance here. The auditor's bytes
were retained unchanged; the manager explicitly rejected this inference.

**Repair contract.** Decide the intended serialization-stable operand domain or
relation. Either reject unsupported surrogate strings/key collisions before
append with useful errors, or use a documented normalization that keeps recorder
and verifier consistent. Merely removing the anomaly check hides the failure.
Test scalar-string identity/change, value aliases, key aliases, ordinary object
key-order invariance, array-order sensitivity, boolean/number distinction and
finite numeric equality. Preserve raw-evidence parsing separately from control
JSON; do not rewrite historical rows or receipts under a new rule.

## F4: case-ID validation mismatch

`experiment._validate_review` (:143) tests a nonempty ID with no `strip`, while
`ledger._row_problem` (:54) requires `case.strip()` to be nonempty. A review case
with ID `" \t "` passes the former but no valid declaration can name it.
Manager checks directly evaluated the validator and row parser, not an entire
release/child lifecycle. The same case with ID `A` passes both. The release path
uses that validator; the downstream missing declaration keeps prerequisites
unmet, so this is fail-closed rather than false completion.

**Repair contract.** Reject whitespace-only IDs at review validation with the
stable `review_schema` reason. Preserve meaningful exact IDs; do not silently
trim/relabel them. Add valid/nonblank, whitespace-only and unchanged accepted-ID
tests. Appendix B supplies the complete review fields and row translation.

## Test isolation, wording and unresolved work

The supplied `test_reviewed_measurement_membership_cannot_be_replaced_by_a_firing_control`
substitute arm changes a control's strict ID into a duplicate canonical ID,
leaving no counted firing control. Add an ordinary-only substitution with an
unchanged firing control. Its existing missing-ID assertion still tests a real
anomaly; the gap is isolation of the stronger comparison. In
`test_malformed_fields_never_turn_into_measurements`, the NaN arm lacks a
measurement ID and is rejected before nonfinite checking. Add an otherwise
valid comparison row to isolate finite/nonfinite discrimination. Separate
operand-only changes from flag-only changes and retain event-order boundaries.

“Finite numbers compare numerically” means Python-decoded numbers: integers
exactly, nonintegers through binary64. Observed `0.1` versus
`0.10000000000000001` and `1e-400` versus `0` compare equal; `0.1` versus `0.2`
differs, `1` versus `1.0` is invariant, overflow to infinity is refused. This
supports a wording clarification, not an established membership bug.

Reviews without ordinary or control populations pass the release validator but
cannot meet prerequisites. Earlier rejection and per-mode control firing are
possible policy improvements; the current aggregate policy is documented and
should not be silently upgraded into a violated contract.

Unresolved close hypotheses: partial Git-removal remnants, fallback-ref
behavior, alternate-home and foreign canonical-UUID corruption. They were not
independently qualified and must not be filed as confirmed defects. No result
qualifies concurrent active writers, mount changes, every host, runtime execution
provenance or the real harness's complete enforcement.

The package auditor disclosed `git status --short && git log --oneline -3`;
the history read exceeded its grant. Those are two auditor-reported invocations,
not manager-issued commands; no raw output, exact issue time or exit status was
captured. Its binding conclusions have independent captured-byte support.
The ledger auditor reported no Git commands or scope deviations but disclosed
inherited commit subjects and other audit paths. Such inherited context is not
counted as an issued command, nor does self-report prove scope enforcement.

Manager mistakes were retained rather than turned into product findings:
the first close probe asserted nonexistent marker field `session_uuid` rather
than `role_uuid`; the first Unicode-key probe overlooked recorder key sorting;
the ledger collection wrapper used nonexistent `--auditor-state` (correct:
`--auditor-stopped`); one export lacked its required parent and was retried at
a fresh destination. Failed outputs and original specimens were preserved during
review. Their relevant lessons and corrections are included here, so old failed
run directories are not needed for remediation.

## Verification ledger

| Run / selector | Collected | Selected | Deselected | Actual outcome |
| --- | ---: | ---: | ---: | --- |
| Close preflight: `close or runtime_recovery or exit_codes` | 815 | 127 | 688 | 127 passed |
| Initial close confirmation: `handback_close_probe` | 824 | 9 | 815 | 7 passed, 2 manager-assertion failures |
| Corrected affected lifetime comparison: `handback_close_probe_admin_lifetime` | 824 | 3 | 821 | 3 passed; six link cases already passed, not repeated |
| Package preflight: `stewart_handoff or stewart_runtime_export or package_control_bytes` | 815 | 39 | 776 | 39 passed |
| Ledger preflight: `stewart_ledger or stewart_experiment` | 815 | 65 | 750 | 65 passed |
| Consolidation: exact Appendix A/B specimens in a fresh source fixture | 832 | 17 | 815 | 17 passed, reproducing current behavior |

Do not add these rows as independent full-suite coverage; selectors overlap.
All preflights used hash-locked provisioned wheels and `scripts/check.py`'s
installed-wheel suite with explicit pytest configuration and no parent plugins.
The close confirmation wheel hash was
`5fd13e6cfff45097a0c569470edc365b793c19b1825b774187c7de4a954897d5`.
Every wheel member name/byte matched the operational wheel; executable ZIP-mode
metadata differed for launcher resources/shared copies due to staging. These
Python-invoked comparisons do not qualify console-launcher permission behavior.

Additional manager checks, not pytest selector counts: exact seven package
files and 39 runtime members; 20 ledger arms plus four review-validator arms;
four corrected Unicode-object arms after preserving a failed three-arm prediction.
The ledger baseline selects four ordinary/two control measurements; Unicode
arms select one ordinary/one control, with the control firing. The latest
review export verified 11 files including pristine assets and collection
observations. Historical preflights were not repeated during consolidation.
To check that the handoff is actually independent of old state, both report
appendices were copied verbatim into a fresh fixture containing only the current
project source/tests. The installed-wheel check selected
`handback_close_probe or audit_unicode or audit_review_id or audit_membership`:
832 collected, 17 selected/passed, 815 deselected. The rebuilt wheel exactly
matched the operational wheel hash. Those tests used no original audit checkout,
private session, exported package or old probe module. They reproduce the four
findings and controls; they do not constitute product repairs. Full output and
selector identities were preserved during validation; the essential results
are embedded here so the validation directory may later be discarded.

For remediation, choose an explicit isolated interpreter, provision
`requirements.lock`, and use the installed-wheel check workflow. Example after
copying the appendices into the indicated test files in a repair checkout:

```sh
STEWART_AUDIT_PYTHON=/absolute/path/to/python3
"$STEWART_AUDIT_PYTHON" -I -B -m pip download --only-binary=:all: --require-hashes -r requirements.lock --dest /absolute/path/to/wheelhouse
"$STEWART_AUDIT_PYTHON" -I -B scripts/check.py --wheelhouse /absolute/path/to/wheelhouse --result /absolute/path/to/results/close.json -k handback_close_probe -s
"$STEWART_AUDIT_PYTHON" -I -B scripts/check.py --wheelhouse /absolute/path/to/wheelhouse --result /absolute/path/to/results/ledger.json -k 'audit_unicode or audit_review_id or audit_membership'
```

Create the result parent and wheelhouse first. Offline provisioning may use an
already verified wheel source with `--no-index --find-links`. The appendix tests
assert observed defective behavior for reproduction; after choosing a repair,
replace those assertions with the acceptance contracts above. A passing defect
probe proves reproduction, not repair. Preserve outputs and report actual
selector counts; do not claim old counts for a changed suite.

## Evidence identities, retained for attribution only

| Audit | Collection | Collection receipt SHA-256 | Captured report SHA-256 |
| --- | --- | --- | --- |
| close-removal-boundary-01 | 20261019T050641-36a1489d | a63661886db8f287e5a39d2fd27349370299e041d575c3307536bd335fda7d96 | 5d6076a66ce56e9258772720953f8e372dfa0855c6bb0a8924672b8e996bdcea |
| package-receipt-sufficiency-01 | 20261019T145906-caad2e00 | c04e09fc955a21b3ab3bf6fa55754cdb2147865b4733a9e591d1aaefb0b930d3 | a7120b79862e90f2152c4c7e6958cae6b6d6ed6952f7c1640b73f2cc1e73b516 |
| ledger-instrument-discrimination-01 | 20261019T161041-fdcba1e4 | bdb9c5491c235ad9ac1dc81da50c31b68659f1c0c09875fb81de51bebdffa43a | ce916cbf7cdf385a18d0055ef4a00d6ef2f1347977f19b1d1124bcdfde848a0c |

Close review: triage `20261019T051222-35da49cf`, retention
`20261019T051247-8d0f11c9`, outcome commit
`d2a5779bca324e04e84b60aee5af85ec4f199785`.
Package review: triage `20261019T150353-f8ca70bb`, retention
`20261019T150434-8132d47d`, outcome commit
`4fe0ab7040c679f1985f95a2c6d443e4eb2c8ccb`.
Ledger review: triage `20261019T161458-764e9ddc`, retention
`20261019T161526-7f146172`, outcome commit
`3d3107e8ee8e0ddb72f493d60864240772619c61` (six accepted bounded conclusions,
one rejected inference, three unresolved groups). Those audit-branch commits
are historical anchors, not dependencies of the reproductions in this report.

The detailed manual Git history is committed in
`AUDIT-COMMISSION-GIT-COMMANDS.md`: exact argv, working directories, issue
identifiers, outcomes and command-output references, with auditor-reported
commands separately attributed. It records discovery, commits, branch/worktree
creation, history/identity verification and every manual action, without filtering
by whether Stewart could perform it. Internal Git invoked by Stewart or fixture
operations is not a manager-issued command. Raw output files are optional
diagnostics after this consolidation; no repair below requires recovering them.

## Cleanup assessment — observed 2026-10-19, no cleanup executed

All three current Stewart statuses returned 0, no attention or outstanding
items, and offered normal concluded `close`. All are snapshots: no writer hold
requires `resume`. No session has been abandoned or closed in this workflow.
The following are proposed operations only, not commands already executed.

### What Stewart can retire

Use each status-issued pinned manager `close` action, after rereading status and
checking the real parent chain. Normal close can remove the recorded auditor
worktree and Git registration, its supplied/recovered runtime and recorded
experiment homes, its empty UUID checkout directory, the two recorded retention
refs, the corresponding role-registry row, and private session/captures. Thus
three eligible closes account for three auditor snapshots/runtimes, six refs,
three role rows and three private sessions. The reviewed report's contents are
already preserved here; old captures are no longer a remediation dependency.

The close inventory has the F1/F2 defects described above. Current status does
not qualify deletion safety under later ancestor substitution or admin-name
reuse. Before a future cleanup, verify ancestry/identity, do not interleave new
preparations with a failed close, and stop to inspect any interrupted removal.
An explicit refusal/leftover is not permission to widen the inventory.

Stewart intentionally retains `CLOSING.json`, `CLOSE-ATTEMPT-*.json` and
`CLOSED.json` under `.git/stewart/closed/<workspace-slug>/<audit-id>/...` and
keeps concluded audit IDs reserved. It has no command to purge those historical
closing records. A normal close therefore does not restore a before-the-fact
private-store state. Do not use abandon/discard flags to disguise reviewed
history or release these launched IDs.

### What remains manual

| Residue | Scope and proposed treatment after authorization |
| --- | --- |
| Three manager worktrees and branches | Remove only the three session-created manager checkouts and their audit branches after close and after accounting for their ignored export/input packages; Stewart never removes manager worktrees or branches |
| Root scratch | Remove the four owned commission/report directories listed below, including venv, wheelhouses, staged source, fixture repos, logs, result files and launch helpers; keep the operational interpreter until all Stewart closes/status checks finish |
| Root individual reports | The three superseded SELF-AUDIT-*-RESULTS.md files can be removed after the unified report/log commit is verified; no unrelated root document is included |
| Exported packages and copied specimens | Located in the owned manager trees' ignored `.scratch` areas; normal close leaves them. Their scientifically relevant conclusions and reproductions are in this report |
| Closing receipts and empty private-store/home parents | Explicit manual removal of only these audits' closing subtrees would erase the ID-reservation history. No Stewart purge exists; empty sessions/registry/repo-key parents may remain after close |
| Shared deployment/launcher storage | The selected manager deployment and launcher are also named by preexisting rehome work. No exclusive ownership is established; do not delete the whole shared manager home. Process-cache directory was empty at inspection |
| Harness/terminal history and Git metadata | Harness-owned logs, reflogs, created commit objects, terminal history and other caches are outside Stewart close. Exact pre-session ownership was not inventoried, so no blanket deletion or garbage collection is justified |

Owned root scratch directories:

- `.scratch/self-audit-commission-20261018`
- `.scratch/receipt-sufficiency-commission-20261019`
- `.scratch/instrument-discrimination-commission-20261019`
- `.scratch/unified-audit-report-20261019`

Superseded owned root reports:

- `SELF-AUDIT-CLOSE-REMOVAL-RESULTS.md`
- `SELF-AUDIT-RECEIPT-SUFFICIENCY-RESULTS.md`
- `SELF-AUDIT-INSTRUMENT-DISCRIMINATION-RESULTS.md`

Preserve preexisting `LINUX-CONTAINERS-PLAN.md`, `SELF-AUDIT-SNAGS.md`,
`user-report.md`, `.venv`, `.scratch/wheelhouse`, rehome directories,
other check-result/commission-close/copy-smoke artifacts and
`stewart-rehome-scope-manager` / `audit/rehome-scope-01`. Their presence does not
make them part of this session's cleanup. Avoid broad clean/reset/prune commands.

Keeping this report/log commit deliberately changes repository history from
the pre-audit state. Restoring the operational layout while retaining the
handoff is feasible; exact byte-for-byte pre-session Git/global-harness state is
not established by available evidence and cannot be promised by `stewart close`.

### Current concrete cleanup targets and command recipe

| Audit ID | Manager checkout basename (under /Users/raccoon/Desktop/Experiments) | Workspace | UUID | Owned manager branch |
| --- | --- | --- | --- | --- |
| close-removal-boundary-01 | stewart-close-removal-manager | audits/close-removal-review | e6f345bd-52a5-4702-81e5-0a45c007b08c | audit/close-removal-boundary-20261018 |
| package-receipt-sufficiency-01 | stewart-receipt-sufficiency-manager | audits/package-receipt-review | a7561b30-eee3-40b4-83c2-e46022566fd1 | audit/package-receipt-sufficiency-20261019 |
| ledger-instrument-discrimination-01 | stewart-ledger-instrument-manager | audits/ledger-instrument-review | 926fc96a-6a57-469a-8dfb-ebe6cf471720 | audit/ledger-instrument-discrimination-20261019 |

Auditor checkout parent for each UUID is
`/Users/raccoon/.local/state/stewart/checkouts/stewart-a964a1bb21fd/<UUID>/`.
Private live session locations and proposed close commands:

- `/Users/raccoon/Desktop/Experiments/stewart/.git/stewart/sessions/close-removal-review-e197ab918629/close-removal-boundary-01`
- `/Users/raccoon/Desktop/Experiments/stewart/.git/stewart/sessions/package-receipt-review-a5d4a352ef9c/package-receipt-sufficiency-01`
- `/Users/raccoon/Desktop/Experiments/stewart/.git/stewart/sessions/ledger-instrument-review-67a47bcd1447/ledger-instrument-discrimination-01`

The recipe below only defines a function and lists commands for later use.
None of these close commands was run while preparing this report. Keep the
interpreter, manager deployment and manager checkouts until it finishes.

```sh
stewart_audit_cleanup() {
  /Users/raccoon/Desktop/Experiments/stewart/.scratch/self-audit-commission-20261018/runtime-venv/bin/python -I -B /Users/raccoon/.local/state/stewart/managers/launchers/21497ee383617dbbd28b3fa7bd7b860c0671313db17929c9a83f463bd63aba6e.py manager --code-root /Users/raccoon/.local/state/stewart/managers/deployments/3e27136d845c87954bec5b38e2726d1cc716c070a0d9ade983c3bc2f63faab2c/runtime --runtime-sha256 3e27136d845c87954bec5b38e2726d1cc716c070a0d9ade983c3bc2f63faab2c --source-package /Users/raccoon/Desktop/Experiments/stewart/.scratch/self-audit-commission-20261018/runtime-venv/lib/python3.14/site-packages/stewart -- "$@"
}
stewart_audit_cleanup --repo /Users/raccoon/Desktop/Experiments/stewart-close-removal-manager --workspace audits/close-removal-review close --audit-id close-removal-boundary-01 --actor 'maintainer performing authorized audit cleanup'
stewart_audit_cleanup --repo /Users/raccoon/Desktop/Experiments/stewart-receipt-sufficiency-manager --workspace audits/package-receipt-review close --audit-id package-receipt-sufficiency-01 --actor 'maintainer performing authorized audit cleanup'
stewart_audit_cleanup --repo /Users/raccoon/Desktop/Experiments/stewart-ledger-instrument-manager --workspace audits/ledger-instrument-review close --audit-id ledger-instrument-discrimination-01 --actor 'maintainer performing authorized audit cleanup'
```

After each close, inspect its actual removal outcomes and status before moving
on. These printed commands are not permission to erase unrelated or shared
state. Manual cleanup remains a separate future action.

## Appendix A: exact close confirmation fixtures

Copy this block into `tests/test_self_audit_close_regressions.py` in a repair
checkout. It relies only on the current repository's normal pytest fixtures,
`test_close` helpers and installed Stewart. It creates disposable repositories;
it must never be pointed at the live audit snapshots. These assertions reproduce
the observed defects; change the failing-contract assertions when implementing
the repairs described above. No old audit metadata or path is an input.

```python
"""Bounded manager confirmation of the static audit; never operate on the live audit."""
import json
from pathlib import Path
import shutil
import sys
import pytest
import test_close as baseline
import stewart.close as closing
from stewart._bootstrap import StewartError, read_regular
from stewart._repository import ROLE_MARKER, checkout_identity
from stewart.session import capture_receipt
from stewart.status import status
import stewart_support as support

pytestmark = pytest.mark.system


def observe(tmp_path, name, value):
    (tmp_path / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value, sort_keys=True))


@pytest.mark.parametrize('interleave', ['none', 'before_close', 'after_removal'])
def test_handback_close_probe_admin_lifetime(checkout, monkeypatch, tmp_path, interleave):
    prepared, _ = baseline._triaged(checkout)
    other = baseline._second_audit(checkout) if interleave == 'before_close' else None
    real_git = closing.git
    def fail_later(repo, *args, **kwargs):
        if args[:1] == ('update-ref',):
            raise StewartError('manager probe: fail after real checkout removal', reason='git_failed')
        return real_git(repo, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(closing, 'git', fail_later)
        first = closing.close(checkout.ws, baseline.IDENT, actor='manager confirmation')
    assert first['closed'] is None
    assert first['results'][0]['outcome'] == 'removed' and not prepared.worktree.exists()
    assert first['failed'][0]['kind'] == 'retention ref', 'failure must occur after real removal'
    frozen, _ = capture_receipt(Path(first['closing']), what='probe closing record')
    old_admin = frozen['removal']['git_admin']
    if interleave == 'after_removal':
        other = baseline._second_audit(checkout)
    marker_before = None
    new_admin = None
    if other:
        new_admin = checkout_identity(Path(other['worktree']))['git_admin']
        if interleave == 'after_removal':
            assert new_admin == old_admin, 'administrative-name reuse control must fire'
        else:
            assert new_admin != old_admin, 'live lifetime must have a separate admin name'
        marker_before, _ = capture_receipt(Path(new_admin) / ROLE_MARKER, what='probe role marker')
    second = closing.close(checkout.ws, baseline.IDENT, actor='manager confirmation retry')
    assert second['resumed'] and second['closed'] and second['failed'] == []
    expected = [f"checkout registered at {other['worktree']}"] if interleave == 'after_removal' else []
    assert second['leftovers'] == expected
    expected_outcome = 'kept: registered elsewhere' if expected else 'absent'
    assert second['results'][0]['outcome'] == expected_outcome
    if other:
        assert Path(other['worktree']).is_dir()
        marker_after, _ = capture_receipt(Path(new_admin) / ROLE_MARKER, what='probe role marker')
        assert marker_before == marker_after and marker_after['role_uuid'] == other['session_uuid']
    view = status(checkout.ws, baseline.IDENT)
    assert view['exit_code'] == (1 if expected else 0)
    observe(tmp_path, 'ADMIN-LIFETIME', {'comparison':'admin-lifetime', 'case':interleave,
        'old_admin':old_admin, 'other_admin':new_admin, 'reuse_observed':new_admin == old_admin,
        'retry_worktree_outcome':second['results'][0]['outcome'], 'leftovers':second['leftovers'],
        'exit_code':second['exit_code'], 'other_session_preserved':other is None or Path(other['worktree']).is_dir()})


@pytest.mark.parametrize('route', ['first_abandon', 'retry'])
@pytest.mark.parametrize('position', ['inside_link', 'leaf_link', 'parent_link'])
def test_handback_close_probe_link_position(checkout, monkeypatch, tmp_path, route, position):
    prepared, _ = baseline._triaged(checkout)
    if route == 'retry':
        real_git = closing.git
        def fail_before_removal(repo, *args, **kwargs):
            if args[:2] == ('worktree', 'remove'):
                raise StewartError('manager probe: interrupt before checkout removal', reason='git_failed')
            return real_git(repo, *args, **kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(closing, 'git', fail_before_removal)
            first = closing.close(checkout.ws, baseline.IDENT, actor='manager confirmation')
        assert first['closed'] is None and first['failed'][0]['kind'] == 'worktree'
        assert prepared.worktree.is_dir()
    audit_dir = Path(prepared.prepared['audit_dir'])
    decoy = tmp_path / 'decoy'
    decoy.mkdir()
    unrelated = tmp_path / 'unrelated.txt'
    unrelated.write_text('invariant sibling\n')
    if position == 'parent_link':
        (decoy / 'worktree').mkdir()
        sentinel = decoy / 'worktree/keep.txt'
        sentinel.write_text('outside recorded checkout\n')
        audit_dir.rename(audit_dir.with_name(audit_dir.name + '-held'))
        audit_dir.symlink_to(decoy, target_is_directory=True)
    else:
        sentinel = decoy / 'keep.txt'
        sentinel.write_text('outside recorded checkout\n')
        if position == 'leaf_link':
            prepared.worktree.rename(prepared.worktree.with_name('worktree-held'))
            prepared.worktree.symlink_to(decoy, target_is_directory=True)
        else:
            (prepared.worktree / 'linked-decoy').symlink_to(decoy, target_is_directory=True)
    assert sentinel.is_file() and unrelated.is_file(), 'both preservation sentinels start present'
    if route == 'first_abandon':
        result = closing.close(checkout.ws, baseline.IDENT, actor='manager confirmation', abandon=True,
            reason='disposable link-position comparison', discard_uncollected=True)
    else:
        result = closing.close(checkout.ws, baseline.IDENT, actor='manager confirmation retry')
    assert result['closed'] is not None and result['failed'] == []
    assert sentinel.exists() is (position != 'parent_link')
    assert unrelated.read_text() == 'invariant sibling\n'
    observe(tmp_path, 'LINK-POSITION', {'comparison':'link-position', 'route':route, 'case':position,
        'decoy_sentinel_survived':sentinel.exists(), 'unrelated_sentinel_survived':True,
        'worktree_outcome':result['results'][0]['outcome'], 'exit_code':result['exit_code'],
        'python':sys.version, 'rmtree_avoids_symlink_attacks':shutil.rmtree.avoids_symlink_attacks})
```

## Appendix B: standalone ledger/review reproduction fixtures

Copy this block into `tests/test_self_audit_ledger_regressions.py` for the stated
selector. It uses installed Stewart and fresh temporary files. It is a compact
reproduction of the important observed distinctions, not the full historical
20-arm evaluation. It asserts today's behavior and does not prescribe whether
the Unicode repair should reject or normalize the unsupported operand domain.

```python
import copy
import json
import pytest
from stewart.ledger import Ledger, parse_rows, summarize, prerequisites
from stewart.experiment import _validate_review


def _audit_case(ident, population, admitted=True, measurements=None):
    return dict(id=ident, population=population, role="audit contrast",
                expected_admission=admitted, prediction="compare operands",
                measurements=["value"] if measurements is None else measurements)


def _audit_recorder(tmp_path, expected, actual):
    cases = [_audit_case("U", "ordinary"), _audit_case("C", "control")]
    path = tmp_path / "rows.jsonl"
    recorder = Ledger(path)
    recorded = None
    for case in cases:
        ident = case["id"]
        recorder.declare(ident, **{k: v for k, v in case.items() if k != "id"})
        recorder.reach(ident)
        recorder.admit(ident, True)
        flag = recorder.compare(ident, "value", expected if ident == "U" else 1,
                                actual if ident == "U" else 2)
        if ident == "U":
            recorded = flag
    rows, problems = parse_rows(path.read_bytes())
    return recorded, problems, summarize(rows, cases=cases), path.read_bytes()


@pytest.mark.parametrize("expected,actual,before,after", [
    ("\U0001f600", "\U0001f600", False, False),
    ("\U0001f600", "\U0001f601", True, True),
    ("\ud83d\ude00", "\U0001f600", True, False),
    ({"\ud83d\ude00": 1, "\U0001f600": 2}, {"\U0001f600": 2}, True, False),
])
def test_audit_unicode_relation(tmp_path, expected, actual, before, after):
    recorded, problems, measured, raw = _audit_recorder(tmp_path, expected, actual)
    assert recorded is before and problems == []
    assert measured["populations"]["ordinary"]["mismatches"] == int(after)
    assert measured["populations"]["control"]["mismatches"] == 1
    assert measured["inconsistent_comparisons"] == (["U"] if before != after else [])


def test_audit_unicode_recorder_repeated_names(tmp_path):
    operand = {"\ud83d\ude00": 1, "\U0001f600": 2}
    recorded, problems, measured, raw = _audit_recorder(tmp_path, operand, operand)
    repeated = []
    def pairs(items):
        seen = set()
        for key, _ in items:
            if key in seen:
                repeated.append(key)
            seen.add(key)
        return dict(items)
    for line in raw.splitlines():
        json.loads(line, object_pairs_hook=pairs)
    assert repeated == ["\U0001f600", "\U0001f600"]
    assert recorded is False and problems == [] and prerequisites(measured) == []


@pytest.mark.parametrize("ident,accepted", [("A", True), (" \t ", False)])
def test_audit_review_id(ident, accepted):
    case = _audit_case(ident, "ordinary")
    review = dict(cases=[case], admissibility_reasoning="contrast",
                  static_review=["contrast"], limits=[])
    assert _validate_review(review) == review
    declaration = dict(kind="declare", case=ident, **{k: v for k, v in case.items() if k != "id"})
    rows, problems = parse_rows(json.dumps(declaration).encode())
    assert bool(rows) is accepted
    assert bool(problems) is not accepted


def test_audit_membership_gate():
    cases = [_audit_case("A", "ordinary", measurements=["canonical", "strict"]),
             _audit_case("B", "ordinary", measurements=["canonical", "strict"]),
             _audit_case("N", "ordinary", False, []),
             _audit_case("K", "control", measurements=["canonical", "strict"])]
    baseline = []
    for case in cases:
        ident = case["id"]
        baseline.extend([dict(kind="declare", case=ident, **{k: v for k, v in case.items() if k != "id"}),
                         dict(kind="reach", case=ident),
                         dict(kind="admit", case=ident, admitted=case["expected_admission"])])
        for measurement in case["measurements"]:
            different = ident in ("B", "K") and measurement == "strict"
            baseline.append(dict(kind="compare", case=ident, measurement=measurement,
                                 expected=[1, 2], actual=[2, 1] if different else [1, 2],
                                 mismatch=different, note=""))
    measured = summarize(baseline, cases=cases)
    changed = copy.deepcopy(baseline)
    next(r for r in changed if r["case"] == "B" and r.get("measurement") == "strict")["measurement"] = "unreviewed"
    substitution = summarize(changed, cases=cases)
    invariant = copy.deepcopy(baseline)
    for row in invariant:
        if row["kind"] == "compare":
            row["note"] = "ignored text"
    assert summarize(invariant, cases=cases) == measured
    assert prerequisites(measured) == []
    assert measured["populations"]["ordinary"]["mismatches"] == 1
    assert len(changed) == len(baseline) == 18
    assert substitution["populations"]["ordinary"]["mismatches"] == 0
    assert substitution["populations"]["ordinary"]["compared"] == 3
    assert substitution["populations"]["control"]["mismatches"] == 1
    assert substitution["missing_measurements"] == [{"case": "B", "measurement": "strict"}]
    assert substitution["unexpected_measurements"] == [{"case": "B", "measurement": "unreviewed"}]
    assert prerequisites(substitution)
```
