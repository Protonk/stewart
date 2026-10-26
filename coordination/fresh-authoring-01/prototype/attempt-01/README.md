# Replaceable submission helper

This is standalone development-study code for the fresh-authoring pilot. It
imports only the Python standard library and does not import or execute Stewart.
It is neither a product schema nor a custody implementation. Its output paths
and read grants are procedural. Structural acceptance is not an assessment of
the author's reasoning, construction, completion claim or findings.

## Usage

Keep the complete submitted JSON as an independent witness first. Choose an
explicit fresh destination whose parent already exists. For example, from the
repository root, with an already saved `selected-envelope.json`:

```sh
/usr/bin/python3 -I -B coordination/fresh-authoring-01/prototype/attempt-01/submit.py \
  --destination /tmp/coordinator-assigned-fresh-submission-01 \
  --question-id question-identity \
  --source-revision 81b557a78db156e7bfc5e8d35ece9d1438608d87 \
  < selected-envelope.json
```

This is an example; its input and destination are not created by this document.
The coordinator must select actual identities and a fresh permitted destination.
The helper never derives output locations from the payload. An existing
destination, even empty or left by failure, is refused before reading stdin.
That refusal does not capture the new input: retain the independent witness and
assign a different destination. Bad CLI syntax likewise precedes capture.

The envelope contains exactly these fields:

```json
{
  "question_id": "question-identity",
  "source_revision": "81b557a78db156e7bfc5e8d35ece9d1438608d87",
  "author": "attributed author string",
  "response_kind": "needs-evidence",
  "completion_claim": "author's qualification or claim",
  "answer": "",
  "support": [
    {"id": "specimen", "role": "freely stated role", "encoding": "utf-8", "text": "exact selected text\r\n"}
  ]
}
```

`response_kind` permits `answer`, `needs-evidence`, or `reframe`. All other
non-support fields are strings, including the possibly empty answer. The helper
does not require particular support roles, findings, successful construction or
agreement with a conclusion. Empty author/completion strings are structurally
permitted and remain attributed. Each support object has exactly `id`, `role`,
`encoding`, `text`; IDs are nonempty unique strings and encoding is `utf-8`.
Path-like IDs are inert logical labels. References in any text trigger no reads,
execution, network access, recursive collection or content reconstruction.

## Observation records

The helper creates the destination once, then writes `attempt.raw` exclusively
before JSON decoding or validation. It rejects repeated keys at every nesting
level, including escape-equivalent names, nonfinite constants and float
overflow, malformed JSON/fields, invalid UTF-8/unpaired Unicode surrogates,
duplicate support IDs and mismatched expected identity. This is a standalone
prototype parser, not a replacement for the product's declaration/control parser.

At most 1,048,576 raw transport bytes and 32 support objects can be accepted.
The raw cap includes JSON syntax, escaping and whitespace. The helper consumes
and preserves the entire stream even when it exceeds that cap: this is an
admission bound, **not a disk, time or stream bound**. An unending input cannot
finish capture. No attempt is silently truncated to pass a limit.

Acceptance creates `SNAPSHOT.json`, then `ACCEPTED.json`, and emits a JSON result
to stdout with exit code 0. The snapshot contains the full envelope in the
submitted support order, the original raw digest/length, and separate UTF-8
digest/length observations for the decoded answer and each support object's
`text`, associated with its ID. It also reports their combined decoded length.
Those lengths exclude support metadata and JSON encoding overhead. Snapshot
serialization may change JSON escaping; decoded text bytes and the raw witness
are separately preserved. Its `author` and `completion_claim` remain claims,
and `intellectual_assessment` is `not_performed`.

Rejection emits exit code 2 and a stable `reason`, `paths`, and `next_step`.
Once the destination exists, rejection attempts to create `FAILURE.json` while
retaining every prior/partial file. A second storage failure may prevent that
record; the emitted diagnostic then names the failure and calls for retaining
it with the independent witness. Output paths in diagnostics are planned names,
not a guarantee that every named record exists. Never retry inside an existing
destination. `write_receipt` uses exclusive binary creation and never replaces
or removes a file.

## Retained check run

The completed command was:

```sh
/usr/bin/python3 -I -B coordination/fresh-authoring-01/prototype/attempt-01/check.py \
  --evidence .scratch/fresh-authoring-01/prototype/attempt-01/check-run-01
```

It passed 204 assertions across 32 helper subprocess invocations. Each case's
independent `input.raw` exists outside its helper destination before launch;
the command, exit status, stdout/stderr, generated files and both source copies
remain retained. The runner's outer stdout/stderr and outcome are retained one
directory above the cases. Re-running requires a new evidence directory.

The cases cover independently expressed exact bytes (non-ASCII, literal
backslash escapes, CRLF and trailing newlines), changed support digest with an
unchanged support control, reordered support invariance by ID, alternate JSON
escaping with decoded invariance, empty answers, all three response kinds,
exact/over raw-size and support-count boundaries, duplicate top/nested/escaped
keys, duplicate IDs, both identity mismatches, UTF-8 and surrogate rejection,
nonfinite numbers, malformed input/fields, encoding/kind rejection, inert
path-like IDs and references, and unchanged accepted/rejected/partial directory
reuse refusals. Rejected bytes and all independent witnesses remain retained.

There were zero installed-wheel/pytest nodes and zero project experiment
executions. The checked pure helper behavior is not a project verification run
or execution of the author's proposed ledger experiment.

## Limits

No durable storage, fsync/crash safety, atomic delivery, replay, custody-start
event, product schema qualification, enforcement against hostile ancestors,
or intellectual adequacy is established. Destination ancestors are not pinned
by descriptors; the coordinator must supply a procedural study destination.
This is not a suitable malicious-writer boundary. No crash, storage exhaustion,
stream failure or fault-injection experiment was run. A preexisting partial
directory's refusal was tested; actual partial capture/write recovery remains
unqualified. Process kill, unavailable stdout or inability to create a failure
record can require the external observer's diagnostic/witness. That witness
cannot establish product retrieval, delivery or custody and grants no audit
execution authority. Do not remove these study artifacts during review.
