# Open inquiry: a broad request and a bounded answer

Authored paper example, 2026-10-29. All service materials, calls, replies and
answers here are illustrative; no audit, implementation run or provider call
produced them. The proposed interface is defined in [the tool card](../TOOLS.md).

## Manager submission

[question.md](submission/question.md) keeps the manager wording below unchanged:

> Audit our app to make sure there are no bugs.

Selected materials:

| Material ID in this walkthrough | Captured file | Bytes |
| --- | --- | --- |
| `m1` | [requirements.txt](submission/materials/requirements.txt) | 662 |
| `m2` | [a.py](submission/materials/a.py) | 175 |
| `m3` | [supplied-report.txt](submission/materials/supplied-report.txt) | 591 |

IDs are audit-scoped symbols for these exact fixture files, not real custody
receipts. The manager still uses the settled prepare/confirmed-commission
boundary. Family settings and launch configuration are not being tested here.

## Auditor walkthrough

The proposed family instructions/tools are in the selected row of the tool card.
After `list()`, the auditor reads the listed files. `read()` supplies exact
text from the linked files and these usable full-file citation values:

```json
{
  "m1": {
    "material": "m1",
    "start": 0,
    "end": 662
  },
  "m2": {
    "material": "m2",
    "start": 0,
    "end": 175
  },
  "m3": {
    "material": "m3",
    "start": 0,
    "end": 591
  }
}
```

Each call below appends one entry. Replies expose stable target/version and
revision; these are authored examples, not captured tool results.

```text
record_observation({
  "text": "Implementation A can send the same reminder twice if the worker stops after sending but before recording the sent marker. On restart, the missing marker permits another send. This conflicts with R1 under the supplied assumptions. The supplied fictional report describes that outcome for R8; I have not executed a test.",
  "citations": [
    {
      "material": "m1",
      "start": 0,
      "end": 662
    },
    {
      "material": "m2",
      "start": 0,
      "end": 175
    },
    {
      "material": "m3",
      "start": 0,
      "end": 591
    }
  ]
})
=> {"entry": "e1", "version": 1, "revision": 1}
```

```text
record_account({
  "text": "The supplied excerpts support one restart-related duplicate-delivery concern. They do not establish that the app has no other bugs.",
  "citations": []
})
=> {"entry": "e2", "version": 1, "revision": 2}
```

```text
record_limit({
  "text": "Only one delivery function, stated assumptions and the limited supplied report were examined. The rest of the app, concurrent workers and gateway failures within a call are outside this packet.",
  "citations": [
    {
      "material": "m1",
      "start": 0,
      "end": 662
    }
  ]
})
=> {"entry": "e3", "version": 1, "revision": 3}
```

```text
prepare()
=> {"handle": "p1", "revision": 3, "entry_count": 3, "observations": [], "rendering": "p1:markdown", "manifest": "p1:manifest"}
answer_read("p1:markdown")  # optional; exact text shown below
submit("p1", confirm=true)
=> {"sealed": true, "prepared_handle": "p1", "actor": "auditor"}
```

The manifest identifies the actual sealer, form/version and prepared members.
No checksum or completed product receipt is invented in this document.

## Illustrative readable return

```markdown
Rendered by Stewart. Entry text is attributed to the auditor.

## Observation

Implementation A can send the same reminder twice if the worker stops after sending but before recording the sent marker. On restart, the missing marker permits another send. This conflicts with R1 under the supplied assumptions. The supplied fictional report describes that outcome for R8; I have not executed a test.

Citations: m1 [0, 662); m2 [0, 175); m3 [0, 591).

## Account

The supplied excerpts support one restart-related duplicate-delivery concern. They do not establish that the app has no other bugs.

## Limit

Only one delivery function, stated assumptions and the limited supplied report were examined. The rest of the app, concurrent workers and gateway failures within a call are outside this packet.

Citations: m1 [0, 662).
```

## Inadequate-evidence variant

Give a fresh auditor only supplied-report.txt, with the original question unchanged. The source and stated requirements are absent. The report remains explicitly fictional and attributed.

Selected material IDs: `m3`.

One admissible sequence of entries is:

```text
record_account({
  "text": "The supplied report claims two visible messages for R8 after a restart. I cannot inspect the implementation or establish the intended delivery contract from this packet, and cannot assess the app for bugs.",
  "citations": [
    {
      "material": "m3",
      "start": 0,
      "end": 591
    }
  ]
})
```

```text
record_limit({
  "text": "Source code and the delivery requirements are not included. The reported duplicate outcome is not an execution I witnessed or a demonstrated violation of an attached requirement.",
  "citations": []
})
```

Preparation reports these mechanical observations:

```json
[
  "No record_observation entries are recorded."
]
```

It still returns a prepared handle and rendering; confirmed submission is
available without another acknowledgment. The illustrative rendering is:

```markdown
Rendered by Stewart. Entry text is attributed to the auditor.

## Account

The supplied report claims two visible messages for R8 after a restart. I cannot inspect the implementation or establish the intended delivery contract from this packet, and cannot assess the app for bugs.

Citations: m3 [0, 591).

## Limit

Source code and the delivery requirements are not included. The reported duplicate outcome is not an execution I witnessed or a demonstrated violation of an attached requirement.
```

## Pressure-test focus

Does open inquiry allow the broad wording without forcing a universal assurance, and can a reader distinguish a reported observation from a verified execution or a bug judgment?
