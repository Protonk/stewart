# Local development evidence

This index lists the local records that current work cites. Each is under
`.scratch/`, which Git ignores, so the records exist only in the working copy
where they were made; a clone does not carry them. Retention follows the
[Evidence and retention](../DEVELOPMENT.md#evidence-and-retention) section of
DEVELOPMENT.md.

## Protected local refs

The local refs `refs/development-evidence/successor-inquiry-01/a1`, `a2` and
`a3` keep three historical outcome commits reachable that no branch contains.
Do not delete them. A main-only clone does not carry them.
`coordination/successor-inquiry-01/CORPUS-RETENTION.md` at `267aaf0` explains
what they protect. The same note marks local records that must not be pruned as
run scratch: the 21 original product-audit source copies under
`.scratch/successor-inquiry-01/answers/attempt-01/sources/` (identities in
`CORPUS.json` beside them), and
`.scratch/successor-inquiry-01/history-reachability-01.json` with its
correction, `history-preservation-01.json`.

## Records current work cites

| Records | What they hold |
| --- | --- |
| `apparatus-01/` | The toolchain image builds, two offline builds per architecture and runs in alpine (`apparatus/step2.sh`) |
| `step3-01/`, `step3-02/`, `step3-03/` | Container suite runs of the manager foundation (`apparatus/step3.sh`); `step3-03` passed on both architectures |
| `diag-linux-01/`, `diag-linux-02/`, `diag-linux-03/` | The Linux diagnostics that traced `step3-01`'s failures to the fat-LTO release build |
| `acceptance-01/`, `acceptance-02/` | Acceptance suite runs (`apparatus/acceptance.sh`); `acceptance-02` at `dc85948` is the current qualification |
| `fat-lto-getrandom-01/` | `REPORT.md`: the fat-LTO `getrandom` reproduction and original observations |
| `fat-lto-getrandom-02/` | `ANALYSIS.md`: the source-level account of that failure, with the toolchain sources it cites, the Riker request and reply, and the web-agent brief |
| `fat-lto-getrandom-03/` | `RESULT.md`: the LLVM-only declaration-merge experiment |
| `fat-lto-getrandom-04/` | `RESULT.md`: the Rust comparison confirming the account on both architectures |
| `successor-local/` | Local evidence of the retired commission-bundle slice, moved there from its ignored `successor/evidence/` directory |

[TRANSITION-PLAN.md](../TRANSITION-PLAN.md) records what these runs established.

Older records under `.scratch/` belong to retired studies. Their index and
reports are in Git history (`coordination/EVIDENCE.md` at `267aaf0`). They stay
unless the user decides otherwise.
