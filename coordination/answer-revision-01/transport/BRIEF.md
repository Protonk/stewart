# Dual-form study capture, bounded implementation

Read the study COMMISSION.md and PROTOCOL.md, AGENTS.md, coordination standing
orders and DEVELOPMENT.md. Source HEAD 5f00082d86768368478ed7cc85b52dd56a60255b.
Root's uncommitted commission/protocol and the prior prototype submit.py/README
are pinned in `.scratch/answer-revision-01/TRANSPORT-INPUTS.json` before dispatch.

Build a standalone standard-library capture helper for the two forms described
in the protocol. Preserve the existing common envelope semantics and limits;
minimal exact fields are `text` and `artifacts`, with artifact exact fields
`name` and `text` (unique nonempty names). Explicit CLI expected identity,
author/phase provenance and form belong in capture metadata for both. Do not
invent author kind/completion/role for minimal returns. Raw stdin bytes must be
captured before parsing; snapshots preserve exact decoded strings and ordered
artifact associations with lengths/digests. Fresh destination only, no payload-
selected paths, repeated control keys/nonfinite/invalid UTF-8 rejected, exclusive
receipts, retain failures and prior paths. Help/errors must explain remedies and
limits. This is procedural development capture, not a product custody boundary.

Own only `coordination/answer-revision-01/transport/attempt-01/` and
`.scratch/answer-revision-01/transport/attempt-01/`. Do not edit prior prototype,
runtime/tests/bundled guidance, shared docs, other worker paths or Git. No nested
workers, Claude, network, installation, subject import/execution, removal or
pruning. Use explicit interpreter -I -B, preferably -S. You may read the finite
source inputs and root instructions named above; do not inspect old study
author/recipient answers or neighboring projects.

Save initial checkpoint before substantial work. Implement capture.py plus
README, retained check code/commands/stdout/stderr/outcomes and RETURN.md. Run
meaningful paired byte-preservation controls for both forms, including literal
escapes/non-ASCII/trailing newlines, changed artifact with unchanged control,
order invariance by identity, malformed/repeated keys, refusal of reused
destinations, and boundaries. Keep checks bounded; prior prototype tests are
reference evidence, not a requirement to recreate a broad suite. Record actual
helper invocation and assertion counts; zero pytest/project executions.
Each check retains its independent input witness outside its destination before
launch. Save progress roughly every 5–10 active minutes and at milestones.
Stop after a reviewed-ready utility and report exact limitations; root/reviewer
will independently inspect it before authors. Do not dispatch authors yourself.
