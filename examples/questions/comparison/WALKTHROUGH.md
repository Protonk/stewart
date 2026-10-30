# Comparison: two requirements and a tradeoff

Authored example. The materials are an invented fixture, and the auditor's calls
and entries are written by hand; no model or provider call produced them. The
tools are specified in [INTERFACE](../../../docs/INTERFACE.md) section 7 and
[QUESTION-FORMS](../../../docs/QUESTION-FORMS.md).

## Manager submission

[question.md](submission/question.md) names the family `comparison` in its front
matter. Its body keeps the manager wording below unchanged:

> Compare implementations A and B against R1 and R2 under the supplied restart
> assumptions. Explain the tradeoffs supported by this packet.

Selected materials, each with the source name the auditor and the manager use:

| Source | File | Bytes | Lines |
| --- | --- | --- | --- |
| `materials/a.py` | [a.py](submission/materials/a.py) | 175 | 5 |
| `materials/b.py` | [b.py](submission/materials/b.py) | 175 | 5 |
| `materials/requirements.txt` | [requirements.txt](submission/materials/requirements.txt) | 662 | 10 |

The [examples README](../README.md) shows how to prepare the folder. The model,
limits and destination are not being tested here.

## Auditor walkthrough

The auditor sees the orientation, the comparison instructions and the tools in
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
                  {"source": "materials/b.py", "size": 175, "lines": 5},
                  {"source": "materials/requirements.txt", "size": 662, "lines": 10}],
    "directories": ["materials"], "returned": 3, "total": 3, "complete": true}

read({"source": "materials/a.py"})
=> {"source": "materials/a.py", "kind": "material", "size": 175,
    "range": [0, 175], "lines": [1, 5], "complete": true,
    "cite": {"source": "materials/a.py", "start": 0, "end": 175}}

read({"source": "materials/b.py"})
=> {"source": "materials/b.py", "kind": "material", "size": 175,
    "range": [0, 175], "lines": [1, 5], "complete": true,
    "cite": {"source": "materials/b.py", "start": 0, "end": 175}}

read({"source": "materials/requirements.txt"})
=> {"source": "materials/requirements.txt", "kind": "material", "size": 662,
    "range": [0, 662], "lines": [1, 10], "complete": true,
    "cite": {"source": "materials/requirements.txt", "start": 0, "end": 662}}
```

Each record call below appends one entry and returns its exact handle and the
answer revision.

```text
record_criterion({
  "text": "Compare A and B against R1 (at most one visible message per reminder ID) and R2 (eventual delivery after restart when the gateway is available), using the supplied serial-worker and completed-call assumptions.",
  "citations": [
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
=> {"entry": "e1.v1.s7bekq", "id": "e1", "version": 1, "revision": 1,
    "citations": [{"source": "materials/requirements.txt", "start": 0, "end": 662,
                   "stewart": {"name": "materials/requirements.txt", "sha256": "…", "lines": [1, 10]}}],
    "notices": []}
```

```text
record_comparison({
  "text": "A sends before marking. A restart in that gap can duplicate a message, conflicting with R1. B marks before sending. A restart in that gap finds the marker and skips sending, so the reminder can remain undelivered despite gateway availability, conflicting with R2. These are deductions from the supplied code and assumptions; no execution report is included in this packet.",
  "citations": [
    {"source": "materials/a.py", "start": 0, "end": 175},
    {"source": "materials/b.py", "start": 0, "end": 175},
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
=> {"entry": "e2.v1.xktk5z", "id": "e2", "version": 1, "revision": 2, "citations": […], "notices": []}
```

```text
record_account({
  "text": "Neither ordering satisfies both requirements across these restart windows. The packet gives no priority between avoiding duplicates and avoiding loss, so I do not select an overall winner.",
  "citations": []
})
=> {"entry": "e3.v1.yb6z5l", "id": "e3", "version": 1, "revision": 3, "citations": [], "notices": []}
```

```text
record_limit({
  "text": "The comparison covers only the shown functions under the supplied assumptions. It does not establish behavior with overlapping workers or partial gateway failures, or compare any third implementation.",
  "citations": [
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
=> {"entry": "e4.v1.h6jnmk", "id": "e4", "version": 1, "revision": 4, "citations": […], "notices": []}
```

`prepare` makes the candidate that submit would seal. Its `next` offers reading
the rendering and the confirmed submit.

```text
prepare({})
=> {"prepared": "ap1.xy6ms6", "revision": 4, "entry_count": 4,
    "counts": {"record_criterion": 1, "record_comparison": 1, "record_observation": 0, "record_account": 1, "record_limit": 1, "record_artifact": 0},
    "notices": [],
    "rendering": {"source": "ap1.xy6ms6/rendering", "size": 1386},
    "selection": {"source": "ap1.xy6ms6/selection", "size": 2309}}
read({"source": "ap1.xy6ms6/rendering"})  # optional; exact text shown below
submit({"prepared": "ap1.xy6ms6", "confirm": true})
=> {"seal": "seal.tueurl", "sealer": "auditor", "sealed_at": "…", "revision": 4, "manifest_sha256": "…"}
```

After a confirmed submit the run delivers the return package and ends, so this
reply is recorded but not sent to the auditor. The return manifest
(`stewart.return/1`) identifies the actual sealer, the family `comparison/1`,
the renderer and the prepared members `answer.json` and `answer.md`. No digest
or delivery record is invented in this document.

## Readable return

The prepared `answer.md`, exactly as `stewart.render/1` renders these entries:

```markdown
Rendered by Stewart. Entry text is attributed to the auditor.

## Criterion — e1

> Compare A and B against R1 (at most one visible message per reminder ID) and R2 (eventual delivery after restart when the gateway is available), using the supplied serial-worker and completed-call assumptions.

Citations: materials/requirements.txt lines 1–10 [0, 662).

## Comparison — e2

> A sends before marking. A restart in that gap can duplicate a message, conflicting with R1. B marks before sending. A restart in that gap finds the marker and skips sending, so the reminder can remain undelivered despite gateway availability, conflicting with R2. These are deductions from the supplied code and assumptions; no execution report is included in this packet.

Citations: materials/a.py lines 1–5 [0, 175); materials/b.py lines 1–5 [0, 175); materials/requirements.txt lines 1–10 [0, 662).

## Account — e3

> Neither ordering satisfies both requirements across these restart windows. The packet gives no priority between avoiding duplicates and avoiding loss, so I do not select an overall winner.

## Limit — e4

> The comparison covers only the shown functions under the supplied assumptions. It does not establish behavior with overlapping workers or partial gateway failures, or compare any third implementation.

Citations: materials/requirements.txt lines 1–10 [0, 662).
```

## Inadequate-evidence variant

Give a fresh auditor requirements.txt and a.py only. B is absent; the manager
question still asks for A versus B. Do not reveal B through another example, a
worked answer or inherited context.

This is a separate audit whose folder has the same question.md and only those
files under materials/. Its sources are `materials/a.py` and
`materials/requirements.txt`.

One admissible sequence of entries is:

```text
record_criterion({
  "text": "The requested criteria are R1 and R2 under the supplied restart assumptions.",
  "citations": [
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
```

```text
record_account({
  "text": "A has a send-before-mark restart window that can produce duplicate delivery. B is not supplied, so I cannot compare A with B or select between them from this packet.",
  "citations": [
    {"source": "materials/a.py", "start": 0, "end": 175},
    {"source": "materials/requirements.txt", "start": 0, "end": 662}
  ]
})
```

```text
record_limit({
  "text": "The implementation or equivalent behavioral evidence for B is missing. A limitation is the return; I have not invented a second implementation to complete the comparison.",
  "citations": []
})
```

`prepare` reports this mechanical notice:

```json
[
  {"reason": "section_unfilled", "tool": "record_comparison", "message": "No record_comparison entries are recorded."}
]
```

It still returns a prepared handle and rendering; confirmed submission is
available without another acknowledgment. The rendering is:

```markdown
Rendered by Stewart. Entry text is attributed to the auditor.

## Criterion — e1

> The requested criteria are R1 and R2 under the supplied restart assumptions.

Citations: materials/requirements.txt lines 1–10 [0, 662).

## Account — e2

> A has a send-before-mark restart window that can produce duplicate delivery. B is not supplied, so I cannot compare A with B or select between them from this packet.

Citations: materials/a.py lines 1–5 [0, 175); materials/requirements.txt lines 1–10 [0, 662).

## Limit — e3

> The implementation or equivalent behavioral evidence for B is missing. A limitation is the return; I have not invented a second implementation to complete the comparison.
```

## Pressure-test focus

Can an auditor submit a useful one-sided account without filling the comparison
section, and does the reader recognize that no A-versus-B comparison was
established?
