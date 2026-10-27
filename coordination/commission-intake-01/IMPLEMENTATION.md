# Bounded C implementation assignment

Source `eea8719` plus current user-authorized plan/contract edits. User explicitly
selected manager-custodied delivery bundles in response to the custody question.
Root remains sole coordinator. Worker owns only `successor/`; root owns shared
docs, integration, acceptance evidence and later audit. No other runtime edits,
Claude, external services, disposal, pruning or nested agents. Preserve frozen
Python and unrelated changes. Save PROGRESS.md under your assigned directory
before substantial work, at milestones and at most ten active minutes apart.

Implement an independently useful, deliberately small Rust CLI crate under
`successor/`, binary `stewart-commission`. Use cached dependencies/offline Cargo
and pinned lockfile; no toolchain/network installation. Current local toolchain
1.99.0. Shared scope comes from COMMISSION-INTAKE-PLAN.md and CONTRACTS. C is
original commission intake and readback only, not launch/results/status/close.

Settled semantics: manager designates and preserves storage after delivery;
Stewart never deletes it. Accepted means all finite selected original files,
original request and declared grants/limits are copied, verified, completion
receipt published last and independent readback possible. No audit result promise.
Incomplete attempt retains copies/diagnostics and supports completion within its
same intent or attributed acknowledgment/disposition as incomplete, never accepted.
No overwrite, replacement, deletion or manual private-state repair. A completed
disposition ends intake, keeps all partial material, and grants no investigation.

Choose the smallest clear shared command/request/receipt interface and document
it in successor/README.md before coding further; notify root of the interface.
Suggested commands: accept, inspect, read, complete, abandon. A caller-designated
existing empty directory can be required so an exclusive INTENT.json is the first
effect; do not create a private store or global index. Known directory/request key
locates interrupted effects and lost replies. An existing identical completed
intent returns its receipt; changed intent refuses; unkeyed calls are distinct.
Only explicit complete resumes incomplete copying, with new planned output names.
Abandon is attributed incomplete disposition, no deletion or false acceptance.

Finite explicit regular-file selections, exactly one original question, roles
for instructions/material/guidance, supplied-view names and explicit declared
grants/limits. Require expected size/digest in input to bind caller intent before
copying. Retain raw request bytes; never normalize away original instructions.
Reasonable documented size/count limits are allowed. No Git materialization,
fetch, archives, links, special files, recursive selection or executable replay.

Use descriptor-relative no-follow traversal for every path component, including
sources, bundle reads/writes and ancestors. Pin directories; regular files only;
do not rely on resolve/lstat then path reopen. Prevent FIFO blocking. Exclusively
create records via one write_receipt helper. No atomic replace or overwriting
partial outputs. Plan exact output names before copying; a new continuation plan
binds its own output names before effects. Preserve failed attempts. Sync files
and directories before acceptance, qualify actual platform limits. Source
observations changing during read refuse acceptance. Bind all member bytes and
original request to intent/acceptance identities. Duplicate JSON keys at every
depth (including escape aliases) must refuse before interpretation; one parser.
Unknown schemas and malformed structures have stable reason identifiers, paths
and next steps. No panics for external input; startup/help do no filesystem work.

Independent inspect/read must run against a moved bundle with only installed
binary, without source files/originating process/old writer execution. Expose
explicit receipt digest/reference, attribution and limitations. A supplied digest
pin verifies against substitution; self-consistency alone does not authenticate
history. Never guess a bundle by recency. Diagnose invalid/missing/unreadable/
unsupported separately. A selected verified member should remain recoverable
with qualifications if unrelated member payload is missing; don't claim whole
acceptance integrity when partial. No future result envelope/registry/reader.

Write meaningful unit/integration tests for content identity, UTF-8/control
parsing, lost reply, interrupted copies/new-name completion or disposition,
path safety, relocation/source independence and damage. Root will independently
exercise installed binary with witnesses, firing/differing/invariance controls.
Do not inflate counts with tautological doc assertions. Save exact commands and
results under assigned successor evidence without deleting failed results. All
Python commands explicit interpreter -I -B (prefer -S for stdlib only).

Return implemented scope, command interface, paths, verification actually run,
unresolved defects/limits and next action. Do not commit; root owns Git.
