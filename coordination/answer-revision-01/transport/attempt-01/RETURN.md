# Transport implementation return

Ready for independent review; no authors were dispatched and no subject code
was imported or executed. The implemented utility is
[capture.py](capture.py), with usage, schemas, evidence and limitations in
[README.md](README.md). Only the assigned transport attempt and matching scratch
were written. Prior prototype, bundled/runtime files, project tests, shared
documents and Git were not changed.

The common payload's field-validation body remains AST-identical to the pinned
prototype. Minimal payloads require exact `text`/`artifacts` fields and exact
artifact `name`/`text` fields. Raw capture precedes either validation path, and
all receipts use exclusive creation. Both forms record CLI expected identity,
form and issued author/phase separately from submitted content. Minimal captures
invent no kind, completion or artifact role. Decoded strings, order and artifact
associations remain inspectable with lengths and SHA-256 digests.

All eight dispatched source snapshots matched their recorded byte identities.
The retained first check run passed 571 assertions across 41 capture invocations:
22 common and 19 minimal. A separate help invocation passed, making 42 total
helper invocations. All used Python 3.9.6 with `-I -B -S`; there were zero pytest
nodes, installed-wheel checks, project or subject executions. The paired controls
distinguish changed-artifact bytes from unchanged controls and ordering/JSON
escaping invariants. Rejected input witnesses, failures and reused destinations
remain independently reviewable.

Evidence is retained at
`.scratch/answer-revision-01/transport/attempt-01/check-run-01`, with the run's
outer command/streams/outcome beside it. [CHECK-RESULT.json](CHECK-RESULT.json)
records counts and source/result identities. The independent input and decoded
byte witnesses precede launch and are outside each helper destination. Retain
the whole finite evidence population, including controls and failures, through
review under DEVELOPMENT.md; this worker performed no cleanup or pruning.

Limits are procedural capture, unauthenticated CLI provenance, non-pinned
destination ancestors, unbounded whole-stream preservation beyond the admission
limit, and no durability/crash/fault-injection qualification. The code is not a
hostile-filesystem boundary. No independent reviewer has yet accepted it; root
owns that review, study integration and whether to release it to authors.
No further implementation work is pending from this worker absent review findings.
