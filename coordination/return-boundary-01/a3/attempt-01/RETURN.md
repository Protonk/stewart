# A3 return — finite instrument-discrimination candidates

Construction complete, 2026-10-26 21:05 UTC. No schema adopted. Recipient behavior remains untested. The full packet preserves all 56,766 original bytes from the historical report and two notes, organized as 43 attributed blocks. Source predictions, read test assertions, assumptions, gaps and potentially disputed claims remain unchanged.

## Stable packets

All paths below are relative to `/Users/raccoon/Desktop/Experiments/stewart`.

| Packet | Path | Bytes | What changes |
|---|---|---:|---|
| Original report plus both notes | `.scratch/return-boundary-01/a3/packets/baseline.md` | 57,373 | Editorial container only; original files also byte-exact under `packets/baseline-originals/` |
| Full finite return | `.scratch/return-boundary-01/a3/packets/finite-full.md` | 66,662 | Six question-specific editorial parts; all original source bytes retained once; no substantive compression |
| Matched support omission | `.scratch/return-boundary-01/a3/packets/finite-withheld.md` | 65,962 | Exactly 700 bytes removed: P4's two-direction bijection proof sketch; proposition, sequencing premises, consequence and other qualifications retained |
| Order control | `.scratch/return-boundary-01/a3/packets/finite-order-control.md` | 66,662 | Only swaps complete attributed support units N1-02 and N1-03; all other bytes fixed; inverse gives full packet |

SHA256:

- Baseline: `f9701671f8fe8bf6551628cb73e9b0e2b333e12aed8bde1fe37b20425dff16ad`.
- Full: `d66365f57d045bc31669ef1d063bab3e790a0f6c678a53835775bbb886f423b3`.
- Omission: `4ca5a4d4c38e26899d81e87f1febfefb81484aa63e29136fcbf94fc655a83c84`.
- Order: `32cc2e124bc0e5f7f7136fa4f14e9e74ce78e6a2f94ffef28026832e37341057`.

Common historical question, exact Instrument discrimination recipe and both role artifacts are under `.scratch/return-boundary-01/a3/common/`. Root can use its own identical common copies. Stage neutral recipient filenames; treatment-bearing filenames, maps and design/check records should not be supplied as initial reading material.

## Maps, restoration and evidence

- `.scratch/return-boundary-01/a3/SOURCE-MAP.json`: exact original identities, source byte/line extents, all 43 block hashes, thematic/original orders, full/omission packet locations, collection identity metadata and single omission.
- `.scratch/return-boundary-01/a3/INVENTORY.md`: every source block's retained/omitted disposition. Repetition was retained, not silently merged.
- `.scratch/return-boundary-01/a3/ORDER-MAP.json`: exact support-unit swap, block extents and inverse restoration.
- `.scratch/return-boundary-01/a3/restorations/p4-proof.txt`: exact 700-byte auditor proof restoration, SHA256 `eb0dbf99e269d7ea1e366b2b57ec12d8e30ada336d589530be76dfc40e93502b`.
- `.scratch/return-boundary-01/a3/restorations/source-excerpts.md`: five separately attributed editor-selected code/manual excerpts for a possible later independent source check. These were not in the historical return. Partial dependency coverage is explicit.
- `.scratch/return-boundary-01/a3/SOURCE-EXCERPTS-MAP.json`: exact source/excerpt identities and extents.
- `.scratch/return-boundary-01/a3/READS.jsonl` and `COMMANDS.md`: read identities/scopes and retained command account.
- `.scratch/return-boundary-01/a3/build-01.log`, `check-01.json`, `check-02-order.json`, `check-03-source.json`: retained construction and check output. Corresponding scripts remain beside them.

check-01 passes 151 static checks of source identities, complete coverage, baseline copies, quoted spans, common input bytes and the one-deletion relation. check-02 verifies all 43 block bytes, every non-swapped byte, fixed report blocks and exact inverse restoration. check-03 verifies 3 source files against admitted identities, 5 exact excerpts and 2 role copies. Failed check runs: 0. Product/pytest selectors and runs: 0. No historical Python was imported or executed.

## Findings and limits

`DESIGN.md` explains connection/purpose/replacement, irreducible support pressure, omission rationale, restoration stages and residual corroboration; `FINDINGS.md` gives the construction result. Inspecting the auditor's stated basis is different from checking source or executing a new inquiry. The full packet supports a proposed end to browsing merely to recover that stated basis; it does not establish source agreement, historical observations, durable custody, real stopping, delivery or enforced access restrictions.

The omission does not remove all support for the central claim. R-04/R-05, N1-03, P1/P3 and the surviving P4 proposition/consequence retain enough mechanism for a reader to reconstruct much of the missing proof. The detailed residual-support table in DESIGN.md identifies each block. A non-firing comparison would not show that support is useless or that the answer is independent of support. No cut was widened to force a response.

The mandatory global input manifest exposed path/digest metadata for held-out reviews and other-case material. No held-out review content, earlier pilot response, other worker output, coordinator account or plan outcome was read. The present designer read the whole question guide; only the recipe section is packaged for common recipient input. These limitations are recorded rather than claiming stronger blindness.

All original sources and the omitted span remain retained independently of candidate packets. No Git mutation, network, runtime/test change, deletion, manager-review read or nested delegation occurred. No further worker task remains; fresh recipient comparisons and any adoption decision belong to root's next stage.
