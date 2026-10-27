# Dual-form procedural study capture

`capture.py` is a standalone standard-library helper. It captures stdin before
parsing, preserves the common envelope's admission semantics, and admits the
minimal text/artifacts form through the same capture path. It neither imports
nor executes Stewart. This is development-study transport, not a product schema,
custody boundary, access-enforcement mechanism or intellectual assessment.

First save the complete input as an independent witness outside the destination.
Use an explicitly assigned fresh directory with an existing parent:

```sh
/usr/bin/python3 -I -B -S coordination/answer-revision-01/transport/attempt-01/capture.py \
  --form minimal \
  --question-id issued-question \
  --source-revision issued-source-revision \
  --author-id a02 \
  --phase phase-01 \
  --destination /absolute/coordinator-assigned/fresh-capture-01 \
  < /absolute/independent-witness/SELECTED-01.json
```

This example does not create its input or parent directory. The coordinator
supplies the actual identities and permitted paths. `--form common` selects the
unchanged common payload schema. Every capture record separates the explicit
CLI question/source and issued author/phase provenance from submitted content.
These CLI labels are caller assertions, not authenticated identities. The common
payload's author string is preserved as an author-supplied claim; it need not
equal the CLI author ID. Minimal identity is supplied only through metadata.

The minimal payload has exactly these fields:

```json
{
  "text": "Selected text, including any qualifications.\n",
  "artifacts": [
    {"name": "chosen logical name", "text": "Exact selected artifact text.\n"}
  ]
}
```

`text` can be empty. `artifacts` is an ordered array, which can be empty. Each
artifact has exactly `name` and `text`, both strings; names must be nonempty and
unique. There is no role, encoding, response kind or completion field added to
minimal submissions. All decoded text must encode strictly as UTF-8. An artifact
name resembling a path is an inert label and never chooses an output path.

The common envelope has exactly `question_id`, `source_revision`, `author`,
`response_kind`, `completion_claim`, `answer` and `support`. All except `support`
are strings; question/source must equal the explicit CLI values. `response_kind`
is one of `answer`, `needs-evidence`, `reframe`. The other strings, including
author, completion and answer, can be empty. `support` is an ordered array of
objects with exactly `id`, `role`, `encoding`, `text`; all are strings, `id` is
nonempty and unique, and `encoding` is exactly `utf-8`. Roles and completion
claims remain freely supplied text, with no intellectual verdict inferred.

Both forms admit at most 1,048,576 raw bytes and 32 artifacts/support objects.
The raw bound includes JSON syntax, escaping and whitespace. The helper captures
the entire input stream even above the bound and then refuses admission: this
is not a stream, disk or time limit. Nothing is silently truncated or discarded.
Repeated JSON keys at every depth (including escape-equivalent keys), invalid
UTF-8, unpaired surrogate strings, nonfinite constants/float overflow, malformed
JSON and fields are rejected. JSON syntax is parsed by Python's standard library;
there is no separate project parser dependency.

Capture creates a fresh destination, then exclusively writes `attempt.raw` before
decoding. Acceptance exclusively writes `SNAPSHOT.json`, then `ACCEPTED.json`,
prints the result as JSON and exits 0. The snapshot stores the complete original
decoded payload under `envelope`, with its order intact. `capture_metadata` stores
the explicit form, expected question/source identity and issued author/phase.
`byte_observations` stores raw byte length/digest, decoded primary-text UTF-8
length/digest, and each ordered artifact's position, name or ID, and text-byte
length/digest. Its decoded total excludes metadata and transport syntax.
Serialization can change JSON escaping, while raw bytes and decoded strings
remain separately preserved.

A rejection or write failure emits exit 2 with a stable `reason`, named paths
and `next_step`. Once a destination has been created, the helper attempts an
exclusive `FAILURE.json`; prior and partial paths remain. If that record cannot
be written, its failure appears in the emitted diagnostic. Listed paths are
planned names, not proof each exists. Before-capture refusals include an existing
destination or failure to create it. Existing accepted, rejected, empty or
partial directories cannot be reused. Bad CLI syntax also precedes raw capture
and uses argparse's stderr diagnostic. Preserve the external input witness and
all partial outputs; correct a mechanical problem in a fresh named attempt.
The helper does not read references, sweep directories, run selected artifacts,
remove files or implement the study's correction allowance.

The retained check command was:

```sh
/usr/bin/python3 -I -B -S coordination/answer-revision-01/transport/attempt-01/check.py \
  --evidence .scratch/answer-revision-01/transport/attempt-01/check-run-01 \
  --pinned-prototype .scratch/answer-revision-01/transport-inputs/coordination/fresh-authoring-01/prototype/attempt-01/submit.py
```

It passed 571 assertions across 41 capture subprocess invocations (22 common,
19 minimal). One additional retained `capture.py --help` invocation exited 0
with empty stderr: 42 total helper invocations. `/usr/bin/python3` resolved to
Xcode's Python 3.9.6; all launches used `-I -B -S`. The check runner never imports
the helper. There were zero installed-wheel/pytest nodes and zero subject or
project executions. [CHECK-RESULT.json](CHECK-RESULT.json) records the identities
and exact counts. This standalone study check is not a project verification run.

The byte-control cases use independent explicit byte literals containing literal
escapes, non-ASCII, CRLF and trailing newlines. For each form, a changed artifact
changes its digest while an untouched artifact and primary text stay invariant;
reordering preserves observations by artifact identity; alternate JSON escaping
changes the raw transport while preserving decoded content. The same population
checks empty text/artifacts, exact/over raw and artifact-count bounds, top-level
escape-equivalent and nested duplicate keys, malformed JSON, invalid UTF-8,
surrogates, float overflow, extra fields, duplicate artifact identity, and
unchanged accepted/rejected destinations after reuse refusal. Common cases also
exercise both identity mismatches and all three response kinds. An AST equality
assertion verifies that the common field-validation body is unchanged from the
pinned prototype; it is separate from runtime coverage.

Every case saves `input.raw`, and successful-case expected decoded-byte witnesses,
outside its helper destination before launch. `COMMAND.json`, `PROCESS.json`,
`stdout.raw`, `stderr.raw` and `OUTCOME.json` retain the command, cwd, PID, streams
and observed exit. The observer inspects destination files only after child exit;
it is not continuous filesystem/process-access monitoring. Source copies and
`RESULT.json` stay with the run; outer command, PID, stdout, stderr and outcome
are retained beside `check-run-01`. All witnesses, including rejected inputs and
unchanged controls, remain for independent review. No removal was performed.

The helper promises no fsync durability, crash safety, atomic delivery, replay,
product retrieval or custody. Destination ancestors are not descriptor-pinned;
the coordinator must supply a procedural study location without concurrent
hostile writers. No kill, storage exhaustion, input-stream failure, concurrent
writer or failure-record-write injection was run. Empty/partial directory reuse
is refused by construction but was not separately executed in this bounded
population. Finite inputs are a caller obligation; an unending stream cannot
finish. Loss of stdout or a process kill can leave uncertain partial output that
requires the independent witness and observer account. Neither a rescue nor
structural admission establishes ordinary product retrieval or grants execution.
