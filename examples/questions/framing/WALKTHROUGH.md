# Inquiry framing: choose a question and investigate it

Authored paper example, 2026-10-29. All service materials, calls, replies and
answers here are illustrative; no audit, implementation run or provider call
produced them. The proposed interface is defined in [the tool card](../../../docs/QUESTION-FORMS.md).

## Manager submission

[question.md](submission/question.md) keeps the manager wording below unchanged:

> We want confidence that reminders won't annoy people or disappear. Work out what you can investigate from this packet and do that work.

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
record_working_question({
  "text": "Can a worker restart cause implementation A to send a reminder more than once under the supplied serial-worker assumptions?",
  "citations": []
})
=> {"entry": "e1", "version": 1, "revision": 1}
```

```text
record_relation({
  "text": "Duplicate delivery is one concrete part of the concern about annoying recipients. I selected it because both the code and the supplied restart report bear on it. This working question does not cover every cause of annoyance or disappearance.",
  "citations": [
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
=> {"entry": "e2", "version": 1, "revision": 2}
```

```text
record_observation({
  "text": "A sends before recording the sent marker. If the worker stops between those calls, the restart sees no marker and can send again. The supplied fictional report claims that result for R8; this is source reasoning plus an attributed report, not a test I ran.",
  "citations": [
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
=> {"entry": "e3", "version": 1, "revision": 3}
```

```text
record_account({
  "text": "Yes, that restart window permits duplicate delivery under the stated assumptions and conflicts with R1. This answer addresses the working question selected above.",
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
record_limit({
  "text": "This inquiry did not establish the reliability of the rest of the application or investigate all ways a reminder could disappear. Gateway failures within a call and concurrent workers are outside the supplied assumptions.",
  "citations": [
    {
      "material": "m1",
      "start": 0,
      "end": 662
    }
  ]
})
=> {"entry": "e5", "version": 1, "revision": 5}
```

```text
prepare()
=> {"handle": "p1", "revision": 5, "entry_count": 5, "observations": [], "rendering": "p1:markdown", "manifest": "p1:manifest"}
answer_read("p1:markdown")  # optional; exact text shown below
submit("p1", confirm=true)
=> {"sealed": true, "prepared_handle": "p1", "actor": "auditor"}
```

The manifest identifies the actual sealer, form/version and prepared members.
No checksum or completed product receipt is invented in this document.

## Illustrative readable return

```markdown
Rendered by Stewart. Entry text is attributed to the auditor.

## Working question

Can a worker restart cause implementation A to send a reminder more than once under the supplied serial-worker assumptions?

## Relation

Duplicate delivery is one concrete part of the concern about annoying recipients. I selected it because both the code and the supplied restart report bear on it. This working question does not cover every cause of annoyance or disappearance.

Citations: m2 [0, 175); m3 [0, 591).

## Observation

A sends before recording the sent marker. If the worker stops between those calls, the restart sees no marker and can send again. The supplied fictional report claims that result for R8; this is source reasoning plus an attributed report, not a test I ran.

Citations: m2 [0, 175); m3 [0, 591).

## Account

Yes, that restart window permits duplicate delivery under the stated assumptions and conflicts with R1. This answer addresses the working question selected above.

Citations: m1 [0, 662).

## Limit

This inquiry did not establish the reliability of the rest of the application or investigate all ways a reminder could disappear. Gateway failures within a call and concurrent workers are outside the supplied assumptions.

Citations: m1 [0, 662).
```

## Inadequate-evidence variant

Give a fresh auditor only requirements.txt, with the original concern unchanged. No implementation or observed delivery behavior is supplied.

Selected material IDs: `m1`.

One admissible sequence of entries is:

```text
record_working_question({
  "text": "Does the implementation meet R1 and R2 across a worker restart?",
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
record_relation({
  "text": "This would examine duplicate and missing reminders, the concrete requirements corresponding to the stated concern.",
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
  "text": "The packet states the desired behavior and simplifying assumptions, but supplies no implementation or behavior report. I cannot investigate whether the implementation meets these requirements from this material.",
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
record_limit({
  "text": "An implementation excerpt showing send/mark ordering or a scoped restart report would be material for that investigation. No such evidence is in this packet; this return does not claim an investigation was performed.",
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

## Working question

Does the implementation meet R1 and R2 across a worker restart?

Citations: m1 [0, 662).

## Relation

This would examine duplicate and missing reminders, the concrete requirements corresponding to the stated concern.

Citations: m1 [0, 662).

## Account

The packet states the desired behavior and simplifying assumptions, but supplies no implementation or behavior report. I cannot investigate whether the implementation meets these requirements from this material.

Citations: m1 [0, 662).

## Limit

An implementation excerpt showing send/mark ordering or a scoped restart report would be material for that investigation. No such evidence is in this packet; this return does not claim an investigation was performed.
```

## Pressure-test focus

Does the return show an actual investigation when evidence permits one, and a truthful limitation otherwise, without treating a better question alone as successful investigation?
