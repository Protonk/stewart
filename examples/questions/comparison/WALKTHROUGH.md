# Comparison: two requirements and a tradeoff

Authored paper example, 2026-10-29. All service materials, calls, replies and
answers here are illustrative; no audit, implementation run or provider call
produced them. The proposed interface is defined in [the tool card](../../../docs/QUESTION-FORMS.md).

## Manager submission

[question.md](submission/question.md) keeps the manager wording below unchanged:

> Compare implementations A and B against R1 and R2 under the supplied restart assumptions. Explain the tradeoffs supported by this packet.

Selected materials:

| Material ID in this walkthrough | Captured file | Bytes |
| --- | --- | --- |
| `m1` | [requirements.txt](submission/materials/requirements.txt) | 662 |
| `m2` | [a.py](submission/materials/a.py) | 175 |
| `m4` | [b.py](submission/materials/b.py) | 175 |

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
  "m4": {
    "material": "m4",
    "start": 0,
    "end": 175
  }
}
```

Each call below appends one entry. Replies expose stable target/version and
revision; these are authored examples, not captured tool results.

```text
record_criterion({
  "text": "Compare A and B against R1 (at most one visible message per reminder ID) and R2 (eventual delivery after restart when the gateway is available), using the supplied serial-worker and completed-call assumptions.",
  "citations": [
    {
      "material": "m1",
      "start": 0,
      "end": 662
    }
  ]
})
=> {"entry": "e1", "version": 1, "revision": 1}
```

```text
record_comparison({
  "text": "A sends before marking. A restart in that gap can duplicate a message, conflicting with R1. B marks before sending. A restart in that gap finds the marker and skips sending, so the reminder can remain undelivered despite gateway availability, conflicting with R2. These are deductions from the supplied code and assumptions; no execution report is included in this packet.",
  "citations": [
    {
      "material": "m2",
      "start": 0,
      "end": 175
    },
    {
      "material": "m4",
      "start": 0,
      "end": 175
    },
    {
      "material": "m1",
      "start": 0,
      "end": 662
    }
  ]
})
=> {"entry": "e2", "version": 1, "revision": 2}
```

```text
record_account({
  "text": "Neither ordering satisfies both requirements across these restart windows. The packet gives no priority between avoiding duplicates and avoiding loss, so I do not select an overall winner.",
  "citations": []
})
=> {"entry": "e3", "version": 1, "revision": 3}
```

```text
record_limit({
  "text": "The comparison covers only the shown functions under the supplied assumptions. It does not establish behavior with overlapping workers or partial gateway failures, or compare any third implementation.",
  "citations": [
    {
      "material": "m1",
      "start": 0,
      "end": 662
    }
  ]
})
=> {"entry": "e4", "version": 1, "revision": 4}
```

```text
prepare()
=> {"handle": "p1", "revision": 4, "entry_count": 4, "observations": [], "rendering": "p1:markdown", "manifest": "p1:manifest"}
answer_read("p1:markdown")  # optional; exact text shown below
submit("p1", confirm=true)
=> {"sealed": true, "prepared_handle": "p1", "actor": "auditor"}
```

The manifest identifies the actual sealer, form/version and prepared members.
No checksum or completed product receipt is invented in this document.

## Illustrative readable return

```markdown
Rendered by Stewart. Entry text is attributed to the auditor.

## Criterion

Compare A and B against R1 (at most one visible message per reminder ID) and R2 (eventual delivery after restart when the gateway is available), using the supplied serial-worker and completed-call assumptions.

Citations: m1 [0, 662).

## Comparison

A sends before marking. A restart in that gap can duplicate a message, conflicting with R1. B marks before sending. A restart in that gap finds the marker and skips sending, so the reminder can remain undelivered despite gateway availability, conflicting with R2. These are deductions from the supplied code and assumptions; no execution report is included in this packet.

Citations: m2 [0, 175); m4 [0, 175); m1 [0, 662).

## Account

Neither ordering satisfies both requirements across these restart windows. The packet gives no priority between avoiding duplicates and avoiding loss, so I do not select an overall winner.

## Limit

The comparison covers only the shown functions under the supplied assumptions. It does not establish behavior with overlapping workers or partial gateway failures, or compare any third implementation.

Citations: m1 [0, 662).
```

## Inadequate-evidence variant

Give a fresh auditor requirements.txt and a.py only. B is absent; the manager question still asks for A versus B. Do not reveal B through another example, a worked answer or inherited context.

Selected material IDs: `m1`, `m2`.

One admissible sequence of entries is:

```text
record_criterion({
  "text": "The requested criteria are R1 and R2 under the supplied restart assumptions.",
  "citations": [
    {
      "material": "m1",
      "start": 0,
      "end": 662
    }
  ]
})
```

```text
record_account({
  "text": "A has a send-before-mark restart window that can produce duplicate delivery. B is not supplied, so I cannot compare A with B or select between them from this packet.",
  "citations": [
    {
      "material": "m2",
      "start": 0,
      "end": 175
    },
    {
      "material": "m1",
      "start": 0,
      "end": 662
    }
  ]
})
```

```text
record_limit({
  "text": "The implementation or equivalent behavioral evidence for B is missing. A limitation is the return; I have not invented a second implementation to complete the comparison.",
  "citations": []
})
```

Preparation reports these mechanical observations:

```json
[
  "No record_comparison entries are recorded."
]
```

It still returns a prepared handle and rendering; confirmed submission is
available without another acknowledgment. The illustrative rendering is:

```markdown
Rendered by Stewart. Entry text is attributed to the auditor.

## Criterion

The requested criteria are R1 and R2 under the supplied restart assumptions.

Citations: m1 [0, 662).

## Account

A has a send-before-mark restart window that can produce duplicate delivery. B is not supplied, so I cannot compare A with B or select between them from this packet.

Citations: m2 [0, 175); m1 [0, 662).

## Limit

The implementation or equivalent behavioral evidence for B is missing. A limitation is the return; I have not invented a second implementation to complete the comparison.
```

## Pressure-test focus

Can an auditor submit a useful one-sided account without filling the comparison section, and does the reader recognize that no A-versus-B comparison was established?
