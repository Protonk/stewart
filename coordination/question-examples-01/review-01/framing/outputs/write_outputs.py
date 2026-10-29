from pathlib import Path
import json

root = Path('coordination/question-examples-01/review-01/framing')
inputs = root / 'inputs'
out = root / 'outputs'
materials = json.loads((inputs / 'MATERIALS.json').read_text())
material_bytes = {item['material']: (inputs / item['path']).read_bytes() for item in materials}
for item in materials:
    assert len(material_bytes[item['material']]) == item['bytes']
    material_bytes[item['material']].decode('utf-8')

def cite(material, start, end):
    data = material_bytes[material]
    assert 0 <= start <= end <= len(data)
    data[start:end].decode('utf-8')
    return {'material': material, 'start': start, 'end': end}

entries = [
    {
        'tool': 'record_working_question',
        'text': "For implementation A, under the packet's serial-worker and durable-marker assumptions, what happens to recipient-visible message counts when a worker stops between completed calls and later retries the same reminder? What can this establish about duplicate messages and reminders disappearing?",
        'citations': [cite('m1', 50, 576), cite('m2', 0, 175)]
    },
    {
        'tool': 'record_relation',
        'text': "The original request is: \"We want confidence that reminders won't annoy people or disappear. Work out what you can investigate from this packet and do that work.\" I preserve that concern while examining the packet's narrower requirements: at most one recipient-visible message per reminder ID, and eventual delivery after restart when the gateway is available. Duplicate delivery is one possible source of annoyance; these requirements do not define annoyance itself. I investigate the shown delivery order and the specified stop boundaries, without executing the code.",
        'citations': [cite('m1', 50, 223)]
    },
    {
        'tool': 'record_observation',
        'text': "Control case: for a fresh reminder, if all shown calls complete, was_sent reads an absent marker, gateway.send produces one visible message, and mark_sent then records the durable marker. Invariance case: a later serial call for that marked reminder returns before gateway.send, so that retry adds no visible message. These are deductions from the code and stated assumptions. The fixture operator's supplied report describes the corresponding R7 scenarios, but explicitly says it is invented and that no tests ran; it is not execution evidence.",
        'citations': [cite('m1', 255, 531), cite('m2', 0, 175), cite('m3', 0, 345)]
    },
    {
        'tool': 'record_observation',
        'text': "Changed case: let a fresh reminder's gateway.send complete, then stop the worker before mark_sent starts. One visible message has been sent and no sent marker has been written. On a later invocation for the same ID, was_sent still reads an absent marker; if that invocation completes, gateway.send creates a second visible message and mark_sent records the marker. The changed stop boundary explains the increase from one message to two, under the stated assumptions. This is a code-derived counterexample to R1 in the packet's model, not a witnessed run. The fixture operator's illustrative R8 report describes the same sequence and adds no independent test evidence.",
        'citations': [cite('m1', 50, 120), cite('m1', 255, 576), cite('m2', 0, 175), cite('m3', 50, 200), cite('m3', 345, 508)]
    },
    {
        'tool': 'record_account',
        'text': "The modeled serial execution can violate the packet's at-most-one requirement even without concurrent workers or a gateway failure within a call. The guard prevents another send only after mark_sent has completed. By contrast, the shown code does not write a sent marker before a completed send. For a fresh reminder stopped before any completed send, another invocation that runs through the calls would deliver a message; for a stop after mark_sent, a visible message has already occurred. These observations do not prove R2's eventual-delivery promise. The excerpt supplies neither a rule that a restarted worker will invoke deliver again nor a guarantee of eventual progress through the required calls. Gateway availability alone does not supply those missing conditions.",
        'citations': [cite('m1', 50, 223), cite('m1', 255, 662), cite('m2', 0, 175)]
    },
    {
        'tool': 'record_limit',
        'text': "This investigation is limited to the fictional excerpts and their stated assumptions. No code or tests were executed. The supplied report is an attributed invented scenario account. I cannot infer how often stops occur, whether actual users would be annoyed, whether message content or timing causes annoyance, or whether the full service loses reminders. Gateway behavior within a failing call, scheduling after restart, and the rest of the application are outside the supplied material. The original confidence request therefore remains broader than the conclusions established here.",
        'citations': [cite('m1', 0, 50), cite('m1', 576, 662), cite('m3', 0, 200), cite('m3', 508, 591)]
    }
]

answer = json.dumps(entries, ensure_ascii=False, indent=2) + '\n'
(out / 'ANSWER.json').write_text(answer)

rendered = ['Rendered by Stewart. All entry text below is attributed to the auditor.\n']
for entry in entries:
    rendered += ['## ' + entry['tool'] + '\n', entry['text'] + '\n', 'Citations:\n']
    rendered += ['- `' + json.dumps(c, separators=(',', ':')) + '`' for c in entry['citations']]
    rendered.append('')
rendering = '\n'.join(rendered) + '\n'
(out / 'RETURN.md').write_text(rendering)

trace = [
    '# One bounded paper attempt\n',
    'All calls and responses below are proposed and illustrative. No Stewart tool was invoked, no code was executed, and no real submission occurred. Handles are illustrative labels, not issued identifiers. The trace has fourteen proposed calls. Development file reads and writes are not Stewart calls.\n',
    'The current answer has six family entries, in append order. `ANSWER.json` is the exact development witness. `RETURN.md` is the exact chosen Markdown rendering of those entries; its attribution line and citation formatting instantiate the card\'s provisional layout. No free-form artifact was added.\n',
    '## 1. List captured material\n',
    '```json\n{"tool":"list","arguments":{}}\n```\n',
    'Illustrative response (listed material IDs, names and byte counts):\n',
    '```json\n' + json.dumps([{k: item[k] for k in ('material', 'name', 'bytes')} for item in materials], indent=2) + '\n```\n'
]
for n, item in enumerate(materials, 2):
    ident = item['material']
    trace += [f'## {n}. Read {item["name"]}\n',
              '```json\n' + json.dumps({'tool':'read', 'arguments':{'material':ident, 'start':0, 'end':item['bytes']}}) + '\n```\n',
              'Illustrative response: the exact UTF-8 content below, including its final newline, and citation `' + json.dumps(cite(ident, 0, item['bytes'])) + '`.\n',
              '```text\n' + material_bytes[ident].decode() + '```\n']
for n, entry in enumerate(entries, 5):
    handle = 'e' + str(n - 4)
    revision = n - 4
    trace += [f'## {n}. Record {entry["tool"]}\n',
              '```json\n' + json.dumps({'tool':entry['tool'], 'arguments':{k:entry[k] for k in ('text','citations')}}, ensure_ascii=False, indent=2) + '\n```\n',
              'Illustrative response:\n\n```json\n' + json.dumps({'entry':handle, 'version':1, 'revision':revision}) + '\n```\n']
trace += [
    '## 11. Prepare current revision\n',
    '```json\n{"tool":"prepare","arguments":{}}\n```\n',
    'Illustrative response, expressed symbolically because the card does not specify the reply or manifest wire schema:\n\n- Prepared selection handle: `p1`.\n- Selected answer revision: 6.\n- Member read handles: `p1-rendering` and `p1-manifest`.\n- Selection, in order: `e1@1`, `e2@1`, `e3@1`, `e4@1`, `e5@1`, `e6@1`.\n- Entry counts: record_working_question = 1; record_relation = 1; record_observation = 2; record_account = 1; record_limit = 1.\n- Factual coverage observation: all five listed recording kinds have at least one entry. No judgment of correctness or completion is inferred.\n- The selection is prepared and remains unsealed.\n',
    '## 12. Inspect prepared rendering\n',
    '```json\n{"tool":"answer_read","arguments":{"handle":"p1-rendering"}}\n```\n',
    'Illustrative response: exactly the UTF-8 bytes of `RETURN.md`, including its final newline. That file is preserved as the complete prepared-rendering witness. It contains the six entries in order, their exact texts and structured citations, with auditor attribution.\n',
    '## 13. Inspect prepared manifest\n',
    '```json\n{"tool":"answer_read","arguments":{"handle":"p1-manifest"}}\n```\n',
    'Symbolic response only: the manifest identifies revision 6, the ordered six entry/version handles listed at call 11, their exact serialized `text` and `citations` fields witnessed in `ANSWER.json`, and the exact rendering witnessed in `RETURN.md`. It identifies the sealer as this auditor and the form version as the supplied paper tool-card form. The card supplies neither the concrete sealer identifier nor the form-version token or manifest byte schema; these are unresolved and no values or receipt digest are fabricated. This is a semantic inspection of the illustrative preparation, not a claim to have retrieved implemented manifest bytes.\n',
    '## 14. Confirm submission of the prepared selection\n',
    '```json\n{"tool":"submit","arguments":{"handle":"p1","confirm":true}}\n```\n',
    'Illustrative outcome, expressed symbolically: accepted; seal the exact revision-6 selection and rendering prepared under `p1`, with the auditor as sealer. No edits intervened after preparation. There was no separate dry-run call; `confirm` is explicitly true. The acceptance response schema and receipt identity are unspecified, so none is invented. The paper attempt ends submitted in this illustrative trace; there is no real submission or implementation result.\n'
]
(out / 'TRACE.md').write_text('\n'.join(trace))

(out / 'FRICTION.md').write_text('''# Friction

1. At call 11, `prepare()` promises a handle, member read handles, counts and observations, but specifies no reply field schema. I used symbolic labels `p1`, `p1-rendering` and `p1-manifest`, explicit ordered membership and counts. Their meanings follow the card; their concrete representation is my illustrative convention.
2. At call 13, `answer_read("p1-manifest")` is supposed to retrieve exact prepared manifest bytes, while the card explicitly leaves final serialization outside the walkthrough. It also requires a sealer and form version without supplying concrete identifiers. I could inspect the intended membership semantically but could not produce or validate an actual manifest encoding. The trace marks that response symbolic. `ANSWER.json` remains a development witness, not a substituted Stewart wire format.
3. For the rendering at call 12, the card specifies ordering, attribution, headings, exact text and listed structured citations, but leaves final Markdown layout provisional. I chose a concrete attribution line, second-level headings and compact JSON citations. `RETURN.md` preserves that choice exactly; it is not claimed as settled product syntax. Call 14's accepted outcome is likewise symbolic because the submit reply schema is not specified.

These interface omissions did not prevent the bounded reasoning or the illustrative confirmed submission. They prevent treating this paper trace as an implemented protocol run. The limited material and lack of witnessed tests are investigation limits, not tool failures.

## Scope account

Actual input files read:

- `coordination/question-examples-01/review-01/framing/BRIEF.md`
- `coordination/question-examples-01/review-01/framing/inputs/TOOLS.md`
- `coordination/question-examples-01/review-01/framing/inputs/question.md`
- `coordination/question-examples-01/review-01/framing/inputs/MATERIALS.json`
- `coordination/question-examples-01/review-01/framing/inputs/materials/requirements.txt`
- `coordination/question-examples-01/review-01/framing/inputs/materials/a.py`
- `coordination/question-examples-01/review-01/framing/inputs/materials/supplied-report.txt`

The inputs directory was listed with `rg --files`. The output-generation script and final verification read only those allowed inputs and this worker's own output files. No outside filesystem content, sibling packet, parent example, repository source, coordinator notes or Git history was read. Existing system/developer/user instructions and the dispatch message were present in inherited context; no parent-authored walkthrough or solution was consulted. No web access, supplied-code execution/import, external model, container or nested agent was used. Isolated Python performed byte-range checks, output serialization and consistency checks only.
''')

(out / 'CHECKPOINT.md').write_text('''# Checkpoint

Initial checkpoint was saved before substantial work, with zero proposed Stewart calls.

Final paper outcome: **submitted in the illustrative paper trace**. No real submission occurred. One attempt completed with **14 proposed Stewart calls**, including preparation, prepared-member inspection and explicit `submit(handle="p1", confirm=true)`.

Produced files:

- `TRACE.md`: the complete numbered call attempt and illustrative/symbolic responses.
- `ANSWER.json`: six current family entries in recorded order, with exact text and citations.
- `RETURN.md`: their exact chosen Markdown rendering, attributed to the auditor.
- `FRICTION.md`: three concrete interface gaps and the actual read-scope account.
- `CHECKPOINT.md`: this initial/final state record.
- `write_outputs.py`: the development-only standard-library serializer used to preserve these witnesses; it executes no supplied material.

The analysis identifies a modeled duplicate-send window between completed send and durable marker, with normal completion and marked retry as comparison cases. It does not establish real execution, human annoyance or eventual-delivery behavior of the full application. Remaining interface uncertainties are the actual preparation/manifest/submission schemas, concrete sealer and form-version identifiers, and final Markdown layout. They were represented symbolically where required and no receipt digest was invented. No further attempt, revision toward an expected result or real action is pending.
''')
