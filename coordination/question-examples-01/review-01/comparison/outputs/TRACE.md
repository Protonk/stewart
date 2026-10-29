# One bounded paper attempt

All calls and responses below are proposed or illustrative. No Stewart adapter, supplied code, or real submission was run. Handles e1–e4 and P1, PM1, PR1 are illustrative tokens, not receipts or digests. P1 is a prepared-selection handle; PM1 and PR1 are its manifest and rendering member read handles. Response fields not specified by the card are described semantically rather than asserted as a wire schema. The list/read observations are checked against the input files.

The question asks to compare A and B against R1 and R2 under the supplied restart assumptions. The question is context for this trace; it is not an answer entry and is not inserted into RETURN.md.

## 1. list()

Illustrative response:

```json
[
  {
    "material": "m1",
    "name": "requirements.txt",
    "bytes": 662
  },
  {
    "material": "m2",
    "name": "a.py",
    "bytes": 175
  }
]
```

## 2. read

```json
{
  "material": "m1",
  "start": 0,
  "end": 662
}
```

Illustrative response: exact UTF-8 bytes below, including the final newline, with citation `{"material":"m1","start":0,"end":662}`.

```text
Reminder service requirements (fictional fixture)
R1. A reminder ID should cause at most one recipient-visible message.
R2. A reminder should eventually produce a message after a worker restart if the gateway is available.
Assumptions for these excerpts:
- A new reminder has no sent marker; was_sent reads that durable marker.
- Workers process a reminder serially; no concurrent workers share that reminder ID.
- mark_sent records durable state before it returns.
- gateway.send sends one visible message each time it completes.
- A worker may stop between completed calls.
These excerpts do not describe the rest of the app or gateway failures within a call.
```

## 3. read

```json
{
  "material": "m2",
  "start": 0,
  "end": 175
}
```

Illustrative response: exact UTF-8 bytes below, including the final newline, with citation `{"material":"m2","start":0,"end":175}`.

```text
def deliver(reminder, store, gateway):
    if store.was_sent(reminder.id):
        return
    gateway.send(reminder.recipient, reminder.text)
    store.mark_sent(reminder.id)
```

## 4. record_criterion

```json
{
  "text": "Auditor criterion: R1 requires at most one recipient-visible message for a reminder ID. R2 requires eventual production of a message after a worker restart when the gateway is available. I assess the excerpt under the stated durable-marker, serial-worker and between-completed-call stop assumptions. These are separate safety and progress requirements; evidence for one does not establish the other.",
  "citations": [
    {
      "material": "m1",
      "start": 50,
      "end": 576
    }
  ]
}
```

Illustrative response:

```json
{"entry":"e1","version":1,"revision":1}
```

## 5. record_comparison

```json
{
  "text": "Auditor source reasoning: A admits a duplicate if restart processing invokes deliver again for the same reminder. Start with no sent marker: was_sent returns false, gateway.send completes with one visible message, and the worker stops before mark_sent. On re-entry the marker is still absent, so another completed send produces a second visible message. This is a serial, between-call counterexample to R1 for that restart processing; it needs neither concurrency nor an in-call failure. The packet does not show the surrounding restart dispatcher, so this is an admitted source-level trace, not an observed application run.",
  "citations": [
    {
      "material": "m2",
      "start": 0,
      "end": 175
    },
    {
      "material": "m1",
      "start": 255,
      "end": 662
    }
  ]
}
```

Illustrative response:

```json
{"entry":"e2","version":1,"revision":2}
```

## 6. record_account

```json
{
  "text": "Auditor source reasoning: A writes the durable marker only after a completed visible send. Once mark_sent completes, later invocations seeing that marker return without sending. If a restarted worker invokes deliver for an unmarked reminder and proceeds through its calls, the send occurs before marking. Thus A has no mark-before-send loss window between these completed calls, but has the duplicate window described above. This ordering does not establish R2's eventual guarantee: the packet supplies no restart dispatch or progress rule, and excludes gateway failures within a call from its description. Gateway availability alone does not establish that deliver is invoked or reaches its send. No execution or reported test observations are supplied.",
  "citations": [
    {
      "material": "m2",
      "start": 0,
      "end": 175
    },
    {
      "material": "m1",
      "start": 120,
      "end": 662
    }
  ]
}
```

Illustrative response:

```json
{"entry":"e3","version":1,"revision":3}
```

## 7. record_limit

```json
{
  "text": "Auditor limitation: The listed packet contains only requirements.txt (m1) and a.py (m2). No implementation B or B-specific observations are supplied. I cannot compare A with B, determine B's compliance, or rank their tradeoffs. My claims about A are conditional source reasoning over the supplied excerpt, not whole-application verification.",
  "citations": []
}
```

Illustrative response:

```json
{"entry":"e4","version":1,"revision":4}
```

## 8. prepare()

Illustrative response, symbolic field layout: prepared handle P1 binds revision 4; PM1 reads its manifest and PR1 reads its Markdown rendering. Counts are record_criterion=1, record_comparison=1, record_account=1 and record_limit=1. No section is missing. These counts say nothing about the substantive availability of B or satisfaction of R1/R2. No answer edit or sealing occurs.

## 9. answer_read(PM1)

Illustrative manifest inspection, symbolic serialization: P1 selects e1/version 1, e2/version 1, e3/version 1 and e4/version 1 in that order at answer revision 4. Their exact kinds, text and citations are the four entries in ANSWER.json. It also binds the exact UTF-8 rendering stored in RETURN.md. There are no free-form artifacts. The final sealer is the auditor and the form is this supplied paper comparison card. The card provides no manifest serialization or canonical form-version identifier; those details remain symbolic, not invented byte-level manifest evidence. ANSWER.json is the development witness, not the manifest or a Stewart wire format.

## 10. answer_read(PR1)

Illustrative response is exactly the contents of RETURN.md, including its final newline. That file is the retained exact rendering witness. Inspection found all four entry texts and structured citation objects in recorded order, with no question text or source bytes inserted. Renderer attribution is distinguished from substantive auditor text. No edit intervenes.

## 11. submit(P1, confirm=false)

Illustrative response, symbolic schema: dry run accepts the current prepared selection P1 as submittable and does not seal it. This assesses selection freshness and submission permissibility only; it does not judge the comparison or fill in missing B evidence.

## 12. submit(P1, confirm=true)

Illustrative response, symbolic schema: the exact prepared selection P1 and its rendering are accepted and sealed with auditor attribution. No edit occurred after preparation. No receipt digest is fabricated. This is the end of the paper attempt; no real submission occurs.

Total proposed Stewart calls: 12. No replacement, deletion, supplementary artifact, additional attempt or supplied-code execution was used.
