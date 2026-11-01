# API-key handling

Complete credential handling and its independent evidence before using a real
provider key. The user has commissioned the design, implementation and local
preparation; no model-consuming call is authorized. Work order belongs to
[RELEASE-PLAN.md](RELEASE-PLAN.md).

## Selected design

The product contract is in [CONTRACTS](CONTRACTS.md#run-and-continuation) and
[INTERFACE 6.1](docs/INTERFACE.md#61-provider):

- Hidden host terminal entry through Python's standard `getpass`, with no echo
  fallback or persistent credential store. A pipe carries the key to the Linux
  process after credential-free intake verification.
- `run --key-fd FD` takes a bounded, one-use descriptor; the existing environment
  input remains an explicit alternative. Ambiguous sources refuse.
- `secrecy` 0.10.3 holds the value; `zeroize` 1.9.1 wipes temporary authentication
  buffers on ordinary drop. Linux suppresses core dumps and ordinary process
  inspection before reading the key. Host administration remains trusted;
  complete memory erasure is not promised.
- Exact response bodies and retained headers remain private. Literal and
  JSON-escaped credential reflection stops the placement before tools or retry;
  derived diagnostics explicitly redact it. The attempt records exposure and
  the normal usage charge. Automatic export withholds contaminated or uncertain
  evidence. Historical captures are never rewritten.

## Remaining work

1. Commit the implementation and apparatus after final review, then run the
   toolchain and Linux acceptance suites on that source. Both native Cargo
   configurations and the independent credential cases have host outputs in
   `.scratch/credential-core-01` and `.scratch/credential-native-driver-01`;
   those development-machine results do not qualify Linux behavior.
2. Exercise the final launcher with the newly qualified executable. Preserve
   the independent credential witness, same-user and different-user observer
   controls, interrupted-run evidence, and withheld/failed exports. Retain the
   original container through review. Local helper/review outputs are in
   `.scratch/launcher-local-02` and `.scratch/launcher-review-01`.
3. Review the Linux outcomes and residual exposures, update the qualification
   record and current product status, and prepare the bound unpaid commission
   packet. Remove this plan when its work is complete. Real-key creation and
   the paid commission remain separate actions.

The evidence requirements are in [ACCEPTANCE](ACCEPTANCE.md#credential-handling),
and build/check requirements in
[DEVELOPMENT](DEVELOPMENT.md#what-to-run-for-what-you-changed). A contaminated
archive remains in its original private container through review. Disposal is
not part of this commission.
