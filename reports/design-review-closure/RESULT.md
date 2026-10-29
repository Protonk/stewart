# Design-review closure

Authorized by the user on 2026-10-29: adopt the machine-interface recommendations,
close the design review, extract one design/path/vision, commit it and delete
the rest of the review. Extraction source: `db4e02d`. This report documents the
disposition; it is not another design or a prerequisite for a new coordinator.

## Extraction

| Source material | Current home / disposition |
| --- | --- |
| Machine-interface briefing | CONTRACTS: one operation core, role-specific views, compact results with effects/uncertainty, exact handles, immutable preparation versus actual seal, bounded reads and strict schemas. Accepted by the user. |
| Linux review's mission and router | DESIGN and CONTRACTS, using the subsequent manager/family/rendering/enforcement decisions. Old examples, turn narratives and superseded alternatives are deleted. |
| Linux review's end-to-end cases | ACCEPTANCE, reconciled with current semantics and extended with C20. Header-line assumptions, obsolete verdict-field tests, premature filesystem rules and old schema examples do not become requirements. |
| Contract-disposition review | Current contracts state surviving duties directly; obsolete Git/resource/executor/legacy status workflows are excluded. Removal and holds are scoped to the non-removing first release; live legacy undertakings remain a retirement gate. |
| Manager preparation/re-entry/question-type/submission discussion | CONTRACTS and DESIGN; typed entries and raw artifacts, no completeness gate, one close, exact retry identity, no private-state repair. Redundant briefing prose is deleted. |
| Worked examples and paper review | Authored fixtures move to examples/questions with docs/QUESTION-FORMS as their specification brief. Exact actor/reader packets, outputs and witnesses remain unchanged in their evidence directory. Symbolic protocol replies are not conformance. |
| Vision and old five-stage program | Coordination principles move to standing orders. TRANSITION-PLAN is the only active program. Old plans and alternative research queues are deleted; the register disposition below accounts for unfinished work. |
| Older inquiry/findings prose and advice | Applicable custody/access/attribution principles and known limitations are extracted. Superseded design prose is deleted; actual runtime/probe records and witnesses stay retained with the run index. Git preserves historical text. |
| Python user instructions | docs/FROZEN-PYTHON keeps the usable installation/manual route. Bundled bytes stay unchanged. The generated Git guide stays because frozen source/tests consume it; it is explicitly legacy-only. |

## Former register disposition

| Old work | Disposition |
| --- | --- |
| W01 answer studies | Bounded review complete. Initial three families/specification and missing/empty/conflicting cases carried; broader comparison research not scheduled. |
| W02 authoring | Durable exact-version edits, prepared selection/seal, interruption and size limits carried into contracts/acceptance; prototype results remain historical evidence. |
| W03 architecture | Settled by current arrangement, explicit archive, tool-only access and finite return. Alternative admission formulas retired. |
| W04 workspace/history | Retired: copied literal files; no checkout/history facility. Name/encoding/bounds remain material contracts. |
| W05 custody | Explicit archive and reference identity carried; repository association and automatic relocation retired. |
| W06 input materialization | Exact copies and cooperative verification carried; Git/submodule machinery retired. |
| W07 access | Commission-bound Stewart tools and actual enforcement qualification carried; shell/private-inventory/network expansion retired. |
| W08 control | Run ownership, stopping across processes and interrupted continuation carried into build/acceptance. No new intervention channel. |
| W09 return | Finite sealed answer plus rendering, independent verification, known/unknown loss and confirmation carried; question/operating records excluded from the package. |
| W10 holds | No new release/hold service in this non-removing build. Existing obligations remain with their writer. |
| W11 interruption | Supported custody accounting, publication evidence and lost-reply handling carried. No auditor request-key/settlement console. |
| W12 recall/readers | Fixed-commission receipt, factual status and bounded auditor re-entry carried. Generic legacy reader and optional orientation trial abandoned as prerequisites. |
| W13 helper recovery | No successor helper/runtime re-materialization service; existing recoveries remain in the retirement inventory. |
| W14 close | Single entry point, prelaunch behavior, exact seal actor, delivery and confirmation carried. Removal comparisons retired from the non-removing build. |
| W15 trust | Strict JSON, exclusive writes, exact identity and descriptor traversal carried. Git-policy work is frozen legacy scope, not Rust work. |
| W16 corrections | Pin final observations to use/publication and writer identity. Git HEAD/mode capture corrections retire with their absent successor surfaces. |
| W17 transition | Inventory live audits/resources/holds/recoveries/partial requests and settle before writer withdrawal. No cross-writer mutation or rewritten receipts. |
| W18 documentation | Current guide/help/errors ship with their implemented interfaces. Generated Git guide retained only for frozen tests/users. |
| W19 foundation | Reuse useful scoped Rust primitives; one typed core and Linux artifact qualification. No parity port. |
| W20 qualification | Independent witnesses, firing/differing/invariance controls, Linux architectures, WSL and bounded model conformance carried. Native macOS successor gate retired. |

The old F1–F7 and custody-first programs are abandoned; completed work remains
evidence, and all surviving implementation work is in the one transition plan.
Unrun Python comparisons, old route trials and broader form studies are not an
implicit pending commission. Later optional studies have explicit scope in the
current plan. No earlier audit, hold or unfinished custody operation is closed
or released by this documentation action.

## Deletion and preservation boundary

[REMOVED-PATHS.txt](REMOVED-PATHS.txt) lists the 67 tracked review/plan files
removed after extraction commit `d7caecb`. The user's specific instruction supersedes
the old review folder's instruction to preserve conversation prose. It does not
authorize disposal of runtime custody or independent evidence. No runtime source, bundled
manual, test, issued audit record, raw actor output, independent witness, local
corpus ref or `.scratch` artifacts directory is removed. Existing evidence packets
retain their original paths/text even when a historical link points to retired
prose; their source revision supplies that context.

[RETAINED-RUNS.md](RETAINED-RUNS.md) and coordination/EVIDENCE.md own local
records previously cited by deleted planning prose. Future coordinators need the
current design, contracts, acceptance and active plan, not these historical accounts.

## Verification

Before deletion, checked 25 maintained/example/report Markdown documents: 116
local links/anchors, balanced fences and 8 JSON examples. No link enters a slated
removal. Compared 1,279 retained runtime/evidence files with the independent
pre-edit SHA-256 inventory; all match. The four intentionally revised coordinator
entry documents are separately accounted for. Verified the mission verbatim,
the generated Git-guide body unchanged, all 12 relocated submission files exact,
the CLAUDE guidance symlink intact and all three protected corpus refs unchanged.

The extraction commit `d7caecb` precedes removal of all 67 listed paths. Final
post-deletion checks are recorded in [VERIFICATION.json](VERIFICATION.json).
No maintained entry point depends on a removed file. The only active plan is
TRANSITION-PLAN.md; a captured historical plan inside an issued audit remains
unchanged evidence.

The source-distribution manifest was updated to include the relocated guide and
current design/example docs. The ordinary installed-wheel checker ran
`tests/test_distribution.py::test_sdist_builds_same_wheel_without_git_or_network`
with Python 3.14.9: **1 collected/selected, 1 passed, 0 skipped**, exit 0.
It rebuilt the wheel from the source distribution offline and compared exact
members/bytes against the wheel built from this checkout. Hatchling's actual
source-member enumeration separately includes all 21 required new/relocated
documentation members and excludes plans, review directories and scratch.

The run record, build/pytest output, wheel and packaging enumeration are retained
under `.scratch/design-review-closure-20261029/`, owned by this report. The checker
reduced its own passing-case artifacts under the normal policy; its artifacts
directory remains and no prune command ran. Full-suite or successor-runtime
qualification was not needed or claimed. No model/provider run occurred.
