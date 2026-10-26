# A1 saved return

Complete within the bounded static commission. No schema adopted. Findings are
in `FINDINGS.md`; purpose, source obligations, omission and restoration rationale
are in `DESIGN.md` beside this return.

All paths below are relative to `/Users/raccoon/Desktop/Experiments/stewart`.

| Packet | Exact path | Bytes | Preservation/change |
| --- | --- | ---: | --- |
| Original | `.scratch/return-boundary-01/a1/packets/01-original/PACKET.md` | 34,823 | Report and both notes unchanged, separately attributed; raw files also in directory |
| Finite candidate | `.scratch/return-boundary-01/a1/packets/02-finite/PACKET.md` | 42,715 | All 33,698 original source bytes in 23 blocks, plus question-specific editorial navigation |
| Omission | `.scratch/return-boundary-01/a1/packets/03-finite-omission/PACKET.md` | 42,311 | Exactly one 404-byte Finding 1 test-coverage paragraph removed; all other bytes match candidate |
| Order control | `.scratch/return-boundary-01/a1/packets/04-finite-order/PACKET.md` | 42,715 | Complete note groups swapped after unchanged report; same unit multiset and exact inverse restoration |

Shared original question and exact recipe section are in
`.scratch/return-boundary-01/a1/common/`; the coordinator separately elected to
supply historical roles equally across arms. Use neutral packet paths for
recipients. Keep design, source maps and condition labels outside initial supply.

Machine-readable maps, exact source block content, source identities and checks:

- `.scratch/return-boundary-01/a1/PACKET-MAPS-02.json`: all four packet hashes and
  ordered editorial/source segments; original `PACKET-MAPS.json` retained.
- `.scratch/return-boundary-01/a1/BLOCKS.json`: 23 exact source units, offsets,
  source order, hashes and content.
- `.scratch/return-boundary-01/a1/INVENTORY.json`: all 68 report/note paragraphs
  partitioned with retained/omitted disposition.
- `.scratch/return-boundary-01/a1/OMISSION.json` and `REORDER.json`: exact treatment
  identities, permutation and inverse, held outside recipient packets.
- `.scratch/return-boundary-01/a1/READS.json`: external input hashes and scope.
- `.scratch/return-boundary-01/a1/check-01.json`: 109 passing static assertions.
- `.scratch/return-boundary-01/a1/reorder-check-01.json`: five passing reported
  ordering properties over 23 units.
- `.scratch/return-boundary-01/a1/final-check-01.json`: 165 passing static
  assertions, including source/excerpt identity and artifact fidelity controls.
- `.scratch/return-boundary-01/a1/COMMANDS.md`: commands, cwd, outputs and actual
  results. Product test count 0; historical execution count 0.

Exact omission restoration:
`.scratch/return-boundary-01/a1/RESTORE-TEST-COVERAGE.md`.
Separate proposed source restorations:
`.scratch/return-boundary-01/a1/proposed-context/TEST-COVERAGE-SOURCE.md` and
`.scratch/return-boundary-01/a1/proposed-context/RETRY-REGISTRATION-SOURCE.md`.
Their nine selected source excerpts are byte-verified in
`.scratch/return-boundary-01/a1/PROPOSED-CONTEXT.json`; they are new editorial
selections of captured target code, not historical auditor-submitted attachments.

The whole return can support examination of the auditor's stated basis. It does
not independently verify its code claims, establish execution or supply missing
runtime/access/custody evidence. The omission may be redundant enough to produce
no observed difference; residual corroboration is intentionally preserved. The
order manipulation is limited to note order. Recipient testing and judgment are
unfinished work returned to the coordinator; neither is represented as complete.
Original source witnesses and all packet/check artifacts remain retained through
review. This worker is finished and owns no continuing action.
