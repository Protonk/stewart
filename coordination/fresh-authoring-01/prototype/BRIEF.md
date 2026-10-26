# Replaceable submission helper: bounded implementation

Authorized by ../COMMISSION.md. Root owns that commission and all shared files.
Development HEAD f5bebc175aadcbf4ff3da27f4636c00dbc53c10b; the admitted untracked
design is ../../fresh-authoring-01/BRIEF.md, INPUTS.json and PROGRESS.md, pinned
in .scratch/fresh-authoring-preparation-01/completion-02.json. Read the root
AGENTS.md, coordination/STANDING-ORDERS.md, this brief, the study BRIEF.md and
COMMISSION.md. Do not read historical audit results or other worker work.

You exclusively own coordination/fresh-authoring-01/prototype/attempt-01/ and
.scratch/fresh-authoring-01/prototype/attempt-01/. Save PROGRESS.md before work,
then source, usage documentation, check script, outputs and RETURN.md. Keep this
bounded to approximately 10–15 minutes. No nested agents, Claude, Git writes,
network, installations, runtime/test edits, historical source execution or
disposal. Use /usr/bin/python3 -I -B for your independent standard-library code.

Implement a CLI receiving a complete JSON envelope on stdin and an explicit
fresh destination directory, expected question ID and subject revision. It
preserves raw attempted bytes before validation; writes records exclusively;
refuses reuse rather than overwriting; and retains failed/partial output with
a stable reason, paths and next step. A directory left by a failed attempt is
not reusable. The explicit CLI destination is coordinator-assigned, never
selected by payload fields. Document that study output directories/read grants
are procedural and this is not production custody or access enforcement.

Envelope fields: question_id, source_revision, author, response_kind,
completion_claim, answer, support. Identity matches the expected arguments;
author and completion_claim are attributed strings, not verified facts.
response_kind allows answer, needs-evidence and reframe. answer is free text;
empty text is structurally valid and may be substantively inadequate. support
is an ordered array of objects with id, role, encoding and text. IDs are unique
logical labels, not paths; encoding is utf-8 for this pilot. Do not require a
finding, a successful construction, particular support roles or agreement with
an expected conclusion. Keep text/code intact, including escaping/newlines.

Reject duplicate JSON keys at every level (including escape-equivalent keys),
nonfinite JSON constants, invalid UTF-8 encoding, malformed fields or identity
mismatch. A standalone study parser may implement the same unique-name rule;
do not import or execute project code. Record this as prototype behavior only.
The cap is 1 MiB of raw submitted bytes and 32 support objects. Preserve an
over-limit attempt in the study witness; never truncate it to make it pass.
Report raw transport bytes and decoded answer/support bytes separately.

On structural acceptance, emit a self-contained snapshot recording the envelope,
per-object exact UTF-8 byte lengths/digests, and original raw digest. Preserve
object order and stable ID associations; content references never trigger file
reads or recursive collection. Clearly separate structural acceptance from
intellectual assessment. Use a small documented write_receipt helper with
exclusive creation for generated study records. Do not imply durable storage,
crash safety, delivery, replay or product schema qualification.

Verify independently chosen exact-byte fixtures (non-ASCII, literal backslash
escapes, CRLF/trailing newlines), changed support bytes that change the digest,
order-only invariance by ID, exact/over size and object-count boundaries,
duplicate keys/IDs, identity mismatch, a structurally valid empty answer,
preserved rejected bytes and refusal to reuse an existing attempt. Retain all
inputs and outputs; no test may destroy its witness. These are prototype checks,
zero installed-wheel/pytest nodes and zero project experiment executions.

Return exact command/selector counts, passed/failed checks, source identities,
usage example, limitations and any unresolved problem. Save results before chat.
