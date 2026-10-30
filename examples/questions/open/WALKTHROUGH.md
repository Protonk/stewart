# Open inquiry: a broad request and a bounded answer

Authored example. The materials are an invented fixture, and the auditor's calls
and entries are written by hand; no model or provider call produced them. The
tools are specified in [INTERFACE](../../../docs/INTERFACE.md) section 7 and
[QUESTION-FORMS](../../../docs/QUESTION-FORMS.md).

## Manager submission

[question.md](submission/question.md) names the family `open-inquiry` in its
front matter. Its body keeps the manager wording below unchanged:

> Audit our app to make sure there are no bugs.

Selected materials, each with the source name the auditor and the manager use:

| Source | File | Bytes | Lines |
| --- | --- | --- | --- |
| `materials/a.py` | [a.py](submission/materials/a.py) | 175 | 5 |
| `materials/requirements.txt` | [requirements.txt](submission/materials/requirements.txt) | 662 | 10 |
| `materials/supplied-report.txt` | [supplied-report.txt](submission/materials/supplied-report.txt) | 591 | 8 |

The [examples README](../README.md) shows how to prepare the folder. The model,
limits and destination are not being tested here.

## Auditor walkthrough

The auditor sees the orientation, the open inquiry instructions and the tools in
QUESTION-FORMS, and the question body as its first user message. It never sees
the front matter or the family name.

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
record_observation({
  "text": "Implementation A can send the same reminder twice if the worker stops after sending but before recording the sent marker. On restart, the missing marker permits another send. This conflicts with R1 under the supplied assumptions. The supplied fictional report describes that outcome for R8; I have not executed a test.",
  "citations": [
    {"source": "materials/requirements.txt", "start": 0, "end": 662},
    {"source": "materials/a.py", "start": 0, "end": 175},
    {"source": "materials/supplied-report.txt", "start": 0, "end": 591}
  ]
})
=> {"entry": "e1.v1.ikpjr5", "id": "e1", "version": 1, "revision": 1,
    "citations": [{"source": "materials/requirements.txt", "start": 0, "end": 662,
                   "stewart": {"name": "materials/requirements.txt", "sha256": "…", "lines": [1, 10]}},
                  …],
    "notices": []}
```

```text
record_account({
  "text": "The supplied excerpts support one restart-related duplicate-delivery concern. They do not establish that the app has no other bugs.",
  "citations": []
})
=> {"entry": "e2.v1.elv7ag", "id": "e2", "version": 1, "revision": 2, "citations": [], "notices": []}
```

```text
record_limit({
  "text": "Only one delivery function, stated assumptions and the limited supplied report were examined. The rest of the app, concurrent workers and gateway failures within a call are outside this packet.",
  "citations": [
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
=> {"entry": "e3.v1.tkxnv2", "id": "e3", "version": 1, "revision": 3, "citations": […], "notices": []}
```

`prepare` makes the candidate that submit would seal. Its `next` offers reading
the rendering and the confirmed submit.

```text
prepare({})
=> {"prepared": "ap1.o35sni", "revision": 3, "entry_count": 3,
    "counts": {"record_account": 1, "record_observation": 1, "record_limit": 1, "record_artifact": 0},
    "notices": [],
    "rendering": {"source": "ap1.o35sni/rendering", "size": 988},
    "selection": {"source": "ap1.o35sni/selection", "size": 1728}}
read({"source": "ap1.o35sni/rendering"})  # optional; exact text shown below
submit({"prepared": "ap1.o35sni", "confirm": true})
=> {"seal": "seal.bsozix", "sealer": "auditor", "sealed_at": "…", "revision": 3, "manifest_sha256": "…"}
```

After a confirmed submit the run delivers the return package and ends, so this
reply is recorded but not sent to the auditor. The return manifest
(`stewart.return/1`) identifies the actual sealer, the family `open-inquiry/1`,
the renderer and the prepared members `answer.json` and `answer.md`. No digest
or delivery record is invented in this document.

## Readable return

The prepared `answer.md`, exactly as `stewart.render/1` renders these entries:

```markdown
Rendered by Stewart. Entry text is attributed to the auditor.

## Observation — e1

> Implementation A can send the same reminder twice if the worker stops after sending but before recording the sent marker. On restart, the missing marker permits another send. This conflicts with R1 under the supplied assumptions. The supplied fictional report describes that outcome for R8; I have not executed a test.

Citations: materials/requirements.txt lines 1–10 [0, 662); materials/a.py lines 1–5 [0, 175); materials/supplied-report.txt lines 1–8 [0, 591).

## Account — e2

> The supplied excerpts support one restart-related duplicate-delivery concern. They do not establish that the app has no other bugs.

## Limit — e3

> Only one delivery function, stated assumptions and the limited supplied report were examined. The rest of the app, concurrent workers and gateway failures within a call are outside this packet.

Citations: materials/requirements.txt lines 1–10 [0, 662).
```

## Inadequate-evidence variant

Give a fresh auditor only supplied-report.txt, with the original question
unchanged. The source and stated requirements are absent. The report remains
explicitly fictional and attributed.

This is a separate audit whose folder has the same question.md and only that
file under materials/. Its one source is `materials/supplied-report.txt`.

One admissible sequence of entries is:

```text
record_account({
  "text": "The supplied report claims two visible messages for R8 after a restart. I cannot inspect the implementation or establish the intended delivery contract from this packet, and cannot assess the app for bugs.",
  "citations": [
    {"source": "materials/supplied-report.txt", "start": 0, "end": 591}
  ]
})
```

```text
record_limit({
  "text": "Source code and the delivery requirements are not included. The reported duplicate outcome is not an execution I witnessed or a demonstrated violation of an attached requirement.",
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

## Account — e1

> The supplied report claims two visible messages for R8 after a restart. I cannot inspect the implementation or establish the intended delivery contract from this packet, and cannot assess the app for bugs.

Citations: materials/supplied-report.txt lines 1–8 [0, 591).

## Limit — e2

> Source code and the delivery requirements are not included. The reported duplicate outcome is not an execution I witnessed or a demonstrated violation of an attached requirement.
```

## Pressure-test focus

Does open inquiry allow the broad wording without forcing a universal assurance,
and can a reader distinguish a reported observation from a verified execution or
a bug judgment?
