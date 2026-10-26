# Prototype return

Completed 2026-10-26. Implemented the bounded replaceable submission helper,
usage/limits documentation and an independent black-box check script. This is
study code only. No product/runtime/test files, historical documents, Git state,
external services or project experiment were changed or executed by this worker.

## Delivered

- `submit.py`: stdin JSON; explicit fresh destination and expected question/source
  identity; complete raw capture before validation; exclusive generated records;
  stable refusal reasons/paths/next steps; self-contained accepted snapshot.
- `check.py`: preserved independent raw witnesses before subprocess launch,
  exact-byte/content/order/boundary/rejection/reuse checks and retained outputs.
- `README.md`: envelope, usage, precise observations and limits.
- `CHECK-RESULT.json`: small result/source identity record.
- `PROGRESS.md`: initial checkpoint and completed disposition.

Example (input must already exist and destination must be fresh):

```sh
/usr/bin/python3 -I -B coordination/fresh-authoring-01/prototype/attempt-01/submit.py \
  --destination /tmp/coordinator-assigned-fresh-submission-01 \
  --question-id question-identity \
  --source-revision 81b557a78db156e7bfc5e8d35ece9d1438608d87 \
  < selected-envelope.json
```

## Checks and preserved failures

One check command, 32 helper subprocess invocations, 204 assertions: **204 passed,
0 failed**. Ten inputs were structurally accepted; 22 expected refusals were
observed and preserved. There was one check run, no corrective rerun and no lost
or deleted witness. Installed-wheel/pytest selector count: **0**. Project
experiment executions: **0**.

Exact check command from the repository root (the saved command record uses
absolute arguments):

```sh
/usr/bin/python3 -I -B coordination/fresh-authoring-01/prototype/attempt-01/check.py \
  --evidence .scratch/fresh-authoring-01/prototype/attempt-01/check-run-01
```

Run exit status was 0; stderr was empty. Retained outer command, stdout, stderr
and outcome are in `.scratch/fresh-authoring-01/prototype/attempt-01/`.
`check-run-01/RESULT.json` records every assertion and command. Each case keeps
input witness, process records, stdout/stderr and helper output. Rejected
oversize input is 1,048,577 bytes and is retained in full. Reusing accepted,
rejected and preexisting partial directories changed none of their bytes.

The firing comparison changed one support object's text/digest while its other
support stayed invariant. The order-only comparison preserved all ID/content
identities while changing presentation order. Independent byte literals checked
non-ASCII, literal backslash escapes, CRLF/trailing newlines and decoded lengths;
separate transport escaping changed raw identity while preserving decoded text.
Further checks covered exact/over raw and support-count caps, all response kinds,
empty answer, duplicate keys (nested/escape-equivalent), duplicate IDs, both
identity mismatches, invalid UTF-8/surrogates, nonfinite constants/overflow,
malformed input/fields, encoding/kind rejection and inert references/labels.

## Identities and scope

Dispatch asserted development HEAD
`f5bebc175aadcbf4ff3da27f4636c00dbc53c10b` and subject revision
`81b557a78db156e7bfc5e8d35ece9d1438608d87`. No Git command was run to independently
re-observe HEAD. All five permitted guidance files read by this worker matched
the pinned byte counts/digests. Their observed identities and timing are retained
in matching scratch `INPUT-IDENTITIES.json`; the dispatch manifest was inspected
for identity only. No other worker work or historical source/results were read.

- `submit.py`: 10418 bytes; SHA-256 `74e3d7c9f66c921ca38689ee84b8181e9fe071796df7b37d46808a0716c7b75c`.
- `check.py`: 11737 bytes; SHA-256 `6bab7ff14e1f579376c342cd0f592295e684364fd2a4c0b902be2b3bce800ed8`.
- `README.md`: 6950 bytes; SHA-256 `0088c67186a348c2c351760ee97a0af5ddbee23cef05a2c6e067d8eff2c63b9c`.

The check-run source copies and recorded digests match the delivered helper and
checker. All output remains within the two assigned attempt directories.

## Limits and disposition

Structural acceptance does not verify authorship, completion, findings or
intellectual adequacy. Decoded byte observations refer to answer/support text;
transport size includes JSON syntax and escaping. The complete over-limit stream
is retained, so the 1 MiB cap is an **admission bound**, not a disk/time/stream
bound. Existing destination or CLI-argument refusal precedes stdin capture and
needs the independent witness. Destinations/ancestors and read grants are
procedural; no descriptor-pinned malicious-writer protection is implemented.

No durability, crash safety, delivery, replay, custody-start event or product
schema qualification is established. No fault injection, process-kill, storage
failure or capture-crash test ran. The preexisting partial-directory refusal
was tested; real partial capture/write failure handling remains unqualified.
No deletion/disposal was performed. Retain all witnesses and attempted outputs
through review. An independent witness does not establish ordinary product
retrieval or authorize investigation.

No unresolved blocker or unfinished implementation remains within this bounded
prototype assignment. Root owns integration and source packet/pilot preparation.
The author/recipient sequence does not run today; stronger custody/access,
durability and later experiment execution require their separately scoped work.
