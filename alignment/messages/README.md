# Messages endpoint comparisons

Use the distributed release writer and record its qualification ID and binary digest. A catalog proposal specifies one model, one audit and one placement. Choose specimens for family and evidence coverage. A selected family audit can also exercise a manager-supplied effort. Live alignment checks its transmission and the endpoint response.

## Prepare unpaid proposals

From the repository root, choose a new directory and a dated price card. For example:

```sh
python3 -I -B alignment/messages/prepare.py .scratch/open-pair \
  --case open-ordinary --prices alignment/messages/pricing-2026-11-21.json
```

Use `--model claude-haiku-5-5` or `--model claude-opus-5-5` to prepare a single proposal. The proposal files leave the account, spending authority and build bindings empty. `PROPOSALS.json` contains the hashes and the reservation calculated by the launcher's billing code for each placement. An omitted effort remains absent from the request. Use `--effort medium` to exercise the explicit setting. The short catalog limits leave room for an ordinary audit below the launcher's 150,000-token combined guard. Paid compaction needs a separate admission mechanism and rehearsal.

The November 21, 2026 price card uses microdollars per million tokens, a one-million-token context window, the direct API's standard rates and the one-hour cache-write rate as the maximum write price. The launcher prices an observed five-minute write separately and reserves using the most expensive applicable band. Recheck the model IDs, settings, API version, compaction beta, rates and route when commissioning. [Models](https://platform.claude.com/docs/en/models/overview), [pricing](https://platform.claude.com/docs/en/about-claude/pricing), [effort](https://platform.claude.com/docs/en/build-with-claude/effort), [API versions](https://platform.claude.com/docs/en/api/versioning) and [on-demand compaction](https://platform.claude.com/docs/en/build-with-claude/compaction-on-demand).

Bind the unpaid proposals in the protected launcher checkout and verify its saved-connection rehearsal. The approved budget, grant and trial cards belong to the separately commissioned queue. Review each placement, its scan, its settlement and the delivered package before admitting the next. The release gate requires auditor submission. An incomplete observation stays in the record. [Packet preparation](../../apparatus/c10/README.md#prepare-a-concrete-live-commission), [launcher budgeting](../../apparatus/c10/HOST-QUEUE.md) and [acceptance policy](../../ACCEPTANCE.md#the-endpoint-alignment-tier).

## Compare observed response shapes

Give the inventory original work tar files and their adjacent `EXPORT.json` receipts. It verifies each tar's byte count and digest, relates each attempt to its request, pinned model and raw response, and compares the charged usage with the response's iteration totals. It identifies absent responses and rejects disagreements across overlapping exports. The private result records source paths and digests without reproducing tool arguments, response text or answers.

```sh
python3 -I -B alignment/messages/inventory.py --output /absolute/new-inventory.json \
  /absolute/export-0001/work.tar /absolute/export-0002/work.tar
python3 -I -B alignment/messages/test_alignment.py
```

An ordinary provider response can carry one message iteration with counts matching its top-level usage. A compaction response can carry zero top-level counts and one compaction iteration carrying the whole charge. The release driver replays both original shapes. The C10 rehearsal also exercises ordinary usage without iterations and a synthetic mixed-iteration summary that distinguishes summation from trusting top-level counts. Use the original fixtures for claims about provider shape and retain the synthetic cases for their accounting controls. [Fixture provenance](../../apparatus/driver/testdata/README.md).

Use the C10 procedural reviewer alongside the inventory. It checks request reconstruction, the signed summary and reset, ledger continuity, citations, attribution and delivery. The inventory alone cannot establish a release pass. Stewart and the direct-route reviewer see recorded attempts. Independent wire framing and aggregate provider billing require different witnesses. Record the scope and any unobserved shape with the outcome. Substantive assessment of an answer is optional. [Procedural reviewer](../../apparatus/c10/README.md), [live-testing guidance](../../development/LIVE-TESTING.md).
