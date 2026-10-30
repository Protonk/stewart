# Inquiry framing: choose a question and investigate it

Authored example. The materials are an invented fixture, and the auditor's calls
and entries are written by hand; no model or provider call produced them. The
tools are specified in [INTERFACE](../../../docs/INTERFACE.md) section 7 and
[QUESTION-FORMS](../../../docs/QUESTION-FORMS.md).

## Manager submission

[question.md](submission/question.md) names the family `inquiry-framing` in its
front matter. Its body keeps the manager wording below unchanged:

> We want confidence that reminders won't annoy people or disappear. Work out
> what you can investigate from this packet and do that work.

Selected materials, each with the source name the auditor and the manager use:

| Source | File | Bytes | Lines |
| --- | --- | --- | --- |
| `materials/a.py` | [a.py](submission/materials/a.py) | 175 | 5 |
| `materials/requirements.txt` | [requirements.txt](submission/materials/requirements.txt) | 662 | 10 |
| `materials/supplied-report.txt` | [supplied-report.txt](submission/materials/supplied-report.txt) | 591 | 8 |

The [examples README](../README.md) shows how to prepare the folder. The model,
limits and destination are not being tested here.

## Auditor walkthrough

The auditor sees the orientation, the inquiry framing instructions and the tools
in QUESTION-FORMS, and the question body as its first user message. It never
sees the front matter or the family name.

Each call is shown as the tool name and its `input`. A line starting `=>` shows
the `data` of the completed `stewart.reply/1` envelope, whose `next` is empty
unless stated. `[…]` stands for the citations as sent, each with Stewart's
additions under `stewart`; elsewhere `…` marks something left out: further
citations, a digest or a time. Handles carry a check bound to their audit, so
the ones here are illustrative.

After `list`, the auditor reads the listed files. Each fits in one page, so each
`read` returns the whole file as its second content block, and the reply's
`cite` is a usable full-file citation:

```text
list({})
=> {"materials": [{"source": "materials/a.py", "size": 175, "lines": 5},
                  {"source": "materials/requirements.txt", "size": 662, "lines": 10},
                  {"source": "materials/supplied-report.txt", "size": 591, "lines": 8}],
    "directories": ["materials"], "returned": 3, "total": 3, "complete": true}

read({"source": "materials/a.py"})
=> {"source": "materials/a.py", "kind": "material", "size": 175,
    "range": [0, 175], "lines": [1, 5], "complete": true,
    "cite": {"source": "materials/a.py", "start": 0, "end": 175}}

read({"source": "materials/requirements.txt"})
=> {"source": "materials/requirements.txt", "kind": "material", "size": 662,
    "range": [0, 662], "lines": [1, 10], "complete": true,
    "cite": {"source": "materials/requirements.txt", "start": 0, "end": 662}}

read({"source": "materials/supplied-report.txt"})
=> {"source": "materials/supplied-report.txt", "kind": "material", "size": 591,
    "range": [0, 591], "lines": [1, 8], "complete": true,
    "cite": {"source": "materials/supplied-report.txt", "start": 0, "end": 591}}
```

Each record call below appends one entry and returns its exact handle and the
answer revision.

```text
record_working_question({
  "text": "Can a worker restart cause implementation A to send a reminder more than once under the supplied serial-worker assumptions?",
  "citations": []
})
=> {"entry": "e1.v1.adje45", "id": "e1", "version": 1, "revision": 1, "citations": [], "notices": []}
```

```text
record_relation({
  "text": "Duplicate delivery is one concrete part of the concern about annoying recipients. I selected it because both the code and the supplied restart report bear on it. This working question does not cover every cause of annoyance or disappearance.",
  "citations": [
    {"source": "materials/a.py", "start": 0, "end": 175},
    {"source": "materials/supplied-report.txt", "start": 0, "end": 591}
  ]
})
=> {"entry": "e2.v1.ihacke", "id": "e2", "version": 1, "revision": 2,
    "citations": [{"source": "materials/a.py", "start": 0, "end": 175,
                   "stewart": {"name": "materials/a.py", "sha256": "…", "lines": [1, 5]}},
                  …],
    "notices": []}
```

```text
record_observation({
  "text": "A sends before recording the sent marker. If the worker stops between those calls, the restart sees no marker and can send again. The supplied fictional report claims that result for R8; this is source reasoning plus an attributed report, not a test I ran.",
  "citations": [
    {"source": "materials/a.py", "start": 0, "end": 175},
    {"source": "materials/supplied-report.txt", "start": 0, "end": 591}
  ]
})
=> {"entry": "e3.v1.5wbt37", "id": "e3", "version": 1, "revision": 3, "citations": […], "notices": []}
```

```text
record_account({
  "text": "Yes, that restart window permits duplicate delivery under the stated assumptions and conflicts with R1. This answer addresses the working question selected above.",
  "citations": [
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
=> {"entry": "e4.v1.nylrf6", "id": "e4", "version": 1, "revision": 4, "citations": […], "notices": []}
```

```text
record_limit({
  "text": "This inquiry did not establish the reliability of the rest of the application or investigate all ways a reminder could disappear. Gateway failures within a call and concurrent workers are outside the supplied assumptions.",
  "citations": [
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
=> {"entry": "e5.v1.id6m3g", "id": "e5", "version": 1, "revision": 5, "citations": […], "notices": []}
```

`prepare` makes the candidate that submit would seal. Its `next` offers reading
the rendering and the confirmed submit.

```text
prepare({})
=> {"prepared": "ap1.3eizdd", "revision": 5, "entry_count": 5,
    "counts": {"record_working_question": 1, "record_relation": 1, "record_observation": 1, "record_account": 1, "record_limit": 1, "record_artifact": 0},
    "notices": [],
    "rendering": {"source": "ap1.3eizdd/rendering", "size": 1518},
    "selection": {"source": "ap1.3eizdd/selection", "size": 2645}}
read({"source": "ap1.3eizdd/rendering"})  # optional; exact text shown below
submit({"prepared": "ap1.3eizdd", "confirm": true})
=> {"seal": "seal.votboq", "sealer": "auditor", "sealed_at": "…", "revision": 5, "manifest_sha256": "…"}
```

After a confirmed submit the run delivers the return package and ends, so this
reply is recorded but not sent to the auditor. The return manifest
(`stewart.return/1`) identifies the actual sealer, the family
`inquiry-framing/1`, the renderer and the prepared members `answer.json` and
`answer.md`. No digest or delivery record is invented in this document.

## Readable return

The prepared `answer.md`, exactly as `stewart.render/1` renders these entries:

```markdown
Rendered by Stewart. Entry text is attributed to the auditor.

## Working question — e1

> Can a worker restart cause implementation A to send a reminder more than once under the supplied serial-worker assumptions?

## Relation — e2

> Duplicate delivery is one concrete part of the concern about annoying recipients. I selected it because both the code and the supplied restart report bear on it. This working question does not cover every cause of annoyance or disappearance.

Citations: materials/a.py lines 1–5 [0, 175); materials/supplied-report.txt lines 1–8 [0, 591).

## Observation — e3

> A sends before recording the sent marker. If the worker stops between those calls, the restart sees no marker and can send again. The supplied fictional report claims that result for R8; this is source reasoning plus an attributed report, not a test I ran.

Citations: materials/a.py lines 1–5 [0, 175); materials/supplied-report.txt lines 1–8 [0, 591).

## Account — e4

> Yes, that restart window permits duplicate delivery under the stated assumptions and conflicts with R1. This answer addresses the working question selected above.

Citations: materials/requirements.txt lines 1–10 [0, 662).

## Limit — e5

> This inquiry did not establish the reliability of the rest of the application or investigate all ways a reminder could disappear. Gateway failures within a call and concurrent workers are outside the supplied assumptions.

Citations: materials/requirements.txt lines 1–10 [0, 662).
```

## Inadequate-evidence variant

Give a fresh auditor only requirements.txt, with the original concern unchanged.
No implementation or observed delivery behavior is supplied.

This is a separate audit whose folder has the same question.md and only that
file under materials/. Its one source is `materials/requirements.txt`.

One admissible sequence of entries is:

```text
record_working_question({
  "text": "Does the implementation meet R1 and R2 across a worker restart?",
  "citations": [
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
```

```text
record_relation({
  "text": "This would examine duplicate and missing reminders, the concrete requirements corresponding to the stated concern.",
  "citations": [
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
```

```text
record_account({
  "text": "The packet states the desired behavior and simplifying assumptions, but supplies no implementation or behavior report. I cannot investigate whether the implementation meets these requirements from this material.",
  "citations": [
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
```

```text
record_limit({
  "text": "An implementation excerpt showing send/mark ordering or a scoped restart report would be material for that investigation. No such evidence is in this packet; this return does not claim an investigation was performed.",
  "citations": []
})
```

`prepare` reports this mechanical notice:

```json
[
  {"reason": "section_unfilled", "tool": "record_observation", "message": "No record_observation entries are recorded."}
]
```

It still returns a prepared handle and rendering; confirmed submission is
available without another acknowledgment. The rendering is:

```markdown
Rendered by Stewart. Entry text is attributed to the auditor.

## Working question — e1

> Does the implementation meet R1 and R2 across a worker restart?

Citations: materials/requirements.txt lines 1–10 [0, 662).

## Relation — e2

> This would examine duplicate and missing reminders, the concrete requirements corresponding to the stated concern.

Citations: materials/requirements.txt lines 1–10 [0, 662).

## Account — e3

> The packet states the desired behavior and simplifying assumptions, but supplies no implementation or behavior report. I cannot investigate whether the implementation meets these requirements from this material.

Citations: materials/requirements.txt lines 1–10 [0, 662).

## Limit — e4

> An implementation excerpt showing send/mark ordering or a scoped restart report would be material for that investigation. No such evidence is in this packet; this return does not claim an investigation was performed.
```

## Pressure-test focus

Does the return show an actual investigation when evidence permits one, and a
truthful limitation otherwise, without treating a better question alone as
successful investigation?
