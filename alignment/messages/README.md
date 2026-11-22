# Messages endpoint comparisons

Use the distributed release writer and record its qualification ID and binary digest. A catalog proposal specifies one model, one audit and one placement. Choose specimens for family and evidence coverage. A selected family audit can also exercise a manager-supplied effort. Live alignment checks its transmission and the endpoint response.

## Prepare unpaid proposals

From the repository root, choose a new directory and a dated price card. For example:

```sh
python3 -I -B alignment/messages/prepare.py .scratch/open-pair \
  --case open-ordinary --prices alignment/messages/pricing-2026-11-21.json
```

Use `--model claude-haiku-5-5` or `--model claude-opus-5-5` to prepare a single proposal. The proposal files leave the account, spending authority and build bindings empty. `PROPOSALS.json` contains the hashes and the reservation calculated by the launcher's billing code for each placement. An omitted effort remains absent from the request. Use `--effort medium` to exercise the explicit setting. The short catalog limits leave room for an ordinary audit below the launcher's 150,000-token combined guard. Paid compaction uses a dedicated single-placement grant and an exact-template rehearsal with the 640 KiB file limit.

The November 21, 2026 price card uses microdollars per million tokens, a one-million-token context window, the direct API's standard rates and the one-hour cache-write rate as the maximum write price. The launcher prices an observed five-minute write separately and reserves using the most expensive applicable band. Recheck the model IDs, settings, API version, compaction beta, rates and route when commissioning. [Models](https://platform.claude.com/docs/en/models/overview), [pricing](https://platform.claude.com/docs/en/about-claude/pricing), [effort](https://platform.claude.com/docs/en/build-with-claude/effort), [API versions](https://platform.claude.com/docs/en/api/versioning) and [on-demand compaction](https://platform.claude.com/docs/en/build-with-claude/compaction-on-demand).

Bind the unpaid proposals in the protected launcher checkout and verify its saved-connection rehearsal. The approved budget, grant and trial cards belong to the separately commissioned queue. Review each placement, its scan, its settlement and the delivered package before admitting the next. The release gate requires auditor submission. An incomplete observation stays in the record. [Packet preparation](procedure/README.md#prepare-a-concrete-live-commission), [launcher budgeting](procedure/HOST-QUEUE.md) and [acceptance policy](../../ACCEPTANCE.md#the-endpoint-alignment-tier).

## Compare observed response shapes

Give the inventory original work tar files and their adjacent `EXPORT.json` receipts. It verifies each tar's byte count and digest, relates each attempt to its request, pinned model and raw response, and compares the charged usage with the response's iteration totals. It identifies absent responses and rejects disagreements across overlapping exports. The private result records source paths and digests without reproducing tool arguments, response text or answers.

```sh
python3 -I -B alignment/messages/inventory.py --output /absolute/new-inventory.json \
  /absolute/export-0001/work.tar /absolute/export-0002/work.tar
python3 -I -B alignment/messages/test_alignment.py
```

An ordinary provider response can carry one message iteration with counts matching its top-level usage. A compaction response can carry zero top-level counts and one compaction iteration carrying the whole charge. The release driver replays both original shapes. The C10 rehearsal also exercises ordinary usage without iterations and a synthetic mixed-iteration summary that distinguishes summation from trusting top-level counts. Use the original fixtures for claims about provider shape and retain the synthetic cases for their accounting controls. [Fixture provenance](../../apparatus/driver/testdata/README.md).

Use the C10 procedural reviewer alongside the inventory. It checks request reconstruction, the signed summary and reset, ledger continuity, citations, attribution and delivery. The inventory alone cannot establish a release pass. Stewart and the direct-route reviewer see recorded attempts. Independent wire framing and aggregate provider billing require different witnesses. Record the scope and any unobserved shape with the outcome. Substantive assessment of an answer is optional. [Procedural reviewer](procedure/README.md), [live-testing guidance](../../development/LIVE-TESTING.md).

## Register a model series

Keep one JSON comparison under `records/<id>.json` and the identical `ALIGNMENT.json` in `.scratch/<id>/` beside its private inputs. The tracked document contains shapes, member locators, digests and procedural outcomes. Keep raw requests, responses, accounts and authorization receipts in the private evidence folder. The qualification index links the comparison for readers without that evidence.

For each model, bind the three family exports and the compaction export to their receipts, packets, authorizations, qualified writer and procedural reviews. Run the shape inventory against each original. Match each attempt to its request, response, reported model, iteration charges and signed reset where applicable. Record run dates, evidence variants, settings, allowances, actual operations, refusals, reminders, usage, and the dated cost calculation. Compare the procedural reviews with sealed auditor submission, citations, delivered bytes and closure. Record the pre-reset entry identity, its revision and delivered version.

For each of the 13 protocol assumptions, identify the observed scope, witnesses, and disposition. Give exact capture locators and digests through the shape inventory. A changed protocol shape needs a reviewed adapter fix, a provenance-bound replay with independent expected values and controls, or an explicit release limitation. Record existing fixture coverage and unobserved behavior. Cost reconciliation with the provider requires independent billing evidence. Content assessment may remain unexamined.

Register the reviewed series with `python3 -I -B apparatus/qualified.py alignment .scratch/<id> --reason TEXT --until TEXT`, then run `python3 -I -B apparatus/qualified.py check`. Registration requires the matching qualified release writer, four completed audits, a disposition for every protocol row, the fixture bytes at their recorded Git revision and every listed private evidence digest. A checkout without the originals can verify the tracked decision and fixture provenance. On the evidence machine, confirm the checker reports both the comparison and the private digests verified.

Before naming a model in a release, compare its model ID, route, API version, compaction beta, trigger and request, maximum output and allowed effort values with the recorded settings. A change requires alignment for the new pins. The record qualifies the procedure and shapes actually observed.

The [commission procedure](procedure/README.md) covers custody-guarded launch, the procedural reviewer and Linux rehearsal. [The saved-connection launcher](procedure/HOST-QUEUE.md) enforces each authorized placement and reservation. The [standalone launcher check](launcher/LAUNCHER.md) exercises the shared session and export controls.
