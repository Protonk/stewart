# Claim trace

## Initial milestone

Question: whether C preserves original requested undertaking, completed verified delivery, incomplete intake, and present verifiability across acceptance-to-readback. No conclusion selected. Planned static route: request parsing/intake; copy and acceptance bindings; inspect and member retrieval; incomplete/abandoned disposition; selected tests and observed supplied records. No comparisons will be executed against project code. Proposed discriminating comparisons will remain predictions.

## Route milestone

Healthy acceptance: main.rs 486–565 retains exact request and refuses changed request bytes; 416–465 publishes attempt first, copies original request and selected sources, verifies retained bytes, then publishes ACCEPTED. Acceptance consumer 314–364 checks external pin and intent/attempt/selection bindings. 366–386 separates recorded accepted state from current integrity; 766–803 verifies selected bytes and emits damage qualification separately. 567–609 exposes incomplete/unresolved states without promoting them.

Incomplete disposition: 631–675 shares binding validation; 677–764 records actor/reason and preserves uncertainty; no deletion. Potential presentation boundary under consideration: after valid incomplete abandonment, inspect at 570–586 returns disposition/inventory but omits the valid loaded original undertaking exposed at 607 beforehand, and read at 769 requires ACCEPTED. INTENT still physically retains the raw request. This is a supported CLI recall gap candidate, not proven byte destruction or false acceptance. Scope relevance must be assessed against CONTRACTS.md 150–178, 218–246.

Supplied evidence agrees with healthy pin/selection and damaged-vs-unaffected member separation. command-023 records attributed incomplete disposition; command-024 refuses later completion. There is no supplied post-abandon inspect/read output. Source prediction must remain distinct from those observations. BYTE-COMPARISONS.md retains direct supplied-byte checks.

## Final assessment milestone

Accepted-route preservation is supported within supplied evidence limits. The acknowledged-incomplete consumer projection is the concrete recall limitation: valid retained INTENT request remains available as raw bundle data, but inspect omits its meaning after abandonment and read requires ACCEPTED. Do not describe this as deletion, information-theoretic indistinguishability (hashes differ), or false acceptance. README 37–43 needs state qualification if the implementation stays unchanged. README 86–87 additionally promises mode provenance that no request/receipt/read path records; narrowing this prose avoids an invented executable-environment obligation.

### Independently proposed discriminating comparisons (not run)

1. Reader gap: independent request witness; legitimate incomplete intake with valid intent; capture inspect before/after ordinary abandonment and read @request after. Keep original intent bytes fixed. Predicted distinction: undertaking shown before, omitted after, read missing acceptance. Firing control: healthy accepted bundle returns exact request. Invariance control: unacknowledged incomplete bundle still shows original undertaking even when source paths are unavailable. This separates deliberate state projection from damaged-intent or unavailable-source explanations.
2. Mode wording: same exact request and input bytes at the same source coordinates, with only source executable permission changed between two fresh destinations. Predicted identical receipt and no mode field; healthy read should still recover identical bytes. Change payload bytes and expected identity as a firing contrast. This would demonstrate the documentation boundary, not establish a duty to preserve executable metadata.

No additional investigation is needed under this commission. Source-to-binary execution provenance, direct post-abandon CLI observation, hostile-host enforcement and hardware failure remain outside the acquired evidence. Final report states these limits and does not derive universal correctness from 14/14 or 46/46.
