# Machine interface: proposed defaults for specification

2026-10-29, following the user's request to hash out the machine interface or
strong opinions a later spec agent can use. **Proposal, not an adopted contract
or implementation commission.** Existing decisions in [CONTRACTS.md](../../CONTRACTS.md)
govern. The [paper review](../question-examples-01/review-01/RESULTS.md) exposed
unspecified prepare/manifest/submit replies and presentation conventions. This
briefing proposes their semantic boundaries before a complete schema is written.

The existing Rust commission slice supplies useful strict JSON, descriptor and
exclusive-record mechanisms and stable `reason/message/paths/next_step` errors.
Its separate accept/complete/abandon workflow and output conventions are an older
interface, not successor requirements. No source or frozen Python bytes change.
No agents, provider calls or runtime tests were started for this discussion.

## 1. One operation core, explicit audience and transport

Use one typed Rust operation layer behind the manager CLI and auditor tools.
Keep role-specific presentation deliberate: shared semantics do not mean identical
payloads. The launched adapter binds an auditor to its commission; an auditor
request does not choose an archive, audit path, actor or arbitrary role. A general
manager `--act-as-auditor` route would contradict the narrow supported interface.
Host-owner archive access remains an existing fact, not a secrecy promise.

For ordinary manager machine commands, propose `--json`: one final UTF-8 JSON
reply on stdout, including expected refusals. Put progress and incidental runtime
diagnostics on stderr. Do not require a machine caller to parse prose, ANSI
formatting or interleaved progress to discover the result. Startup/forced-exit/
broken-channel cases may still yield no usable reply; missing output is unknown,
not proof of no effects. Exit status describes the invocation, not audit lifecycle.

Raw exact-byte readback is the explicit exception: stdout contains only the
requested bytes, with qualification kept separate. Auditor bounded text reads
use JSON strings and explicit ranges/continuations. No new daemon, public network
API or event-stream protocol is needed to settle these semantics. Keep complex
structured inputs available through a file or stdin, avoiding shell-quoted JSON
as the only route. Human and JSON views come from the same operation result.

## 2. Small common reply, operation-specific data

Propose a versioned envelope with `schema`, `operation`, `outcome` and operation
data. `completed`, `refused` and `failed` are invocation outcomes, never grades
or general "audit done" states. Concrete field spelling remains a spec choice.
Normal edit replies should stay small: exact entry handle, version and resulting
answer revision. Full orientation belongs to re-entry; large manifests and
renderings belong behind read handles and bounded pages.

On refusal/failure add a stable reason, a useful message, established effects and
the next supported call(s). Effects are operation-specific: answer unchanged,
seal recorded, acceptance absent/accepted/unknown, partial copy retained, or
delivery unverified are different facts. A single `changed: false` or global
`ok: false` cannot encode all of them. Raw diagnostic recording may have occurred
even when an answer mutation was refused. Never infer absent effects from an
exception. If recording the diagnostic also failed, preserve both causes and say
which evidence is durable versus merely reported.

Next steps should carry a tool name plus arguments, or a CLI argv array, alongside
the readable explanation. They are suggestions under existing authority, not
auto-execution instructions. Alternatives such as run versus close preserve the
manager's choice. Do not return a blanket `retryable` bit inviting blind repeats.

Auditor errors identify material/entry handles and field locations, not host
paths. Unrepairable custody failures give the auditor a stopping route while
manager status receives the custody diagnostics. The two presentations refer to
the same failure and do not disclose the manager's private operating records.

## 3. Opaque handles bind purpose and exact work

Keep distinct handle kinds for a manager's stable audit reference, material
identity, exact entry/version, manager preparation, auditor preparation, prepared
member read and seal reference. They may have readable prefixes, but callers do
not construct, parse, increment or retarget them. Validate audit/store identity,
purpose and version on every use. A handle is neither a filesystem path nor a
new host-owner authentication mechanism.

The exact entry handle is the edit operand; displayed entry ID/version/revision
help orientation. Display names and equal content never identify edits or retries.
A stale entry handle returns the current handle/read route without silently
reading or overwriting the replacement. Auditor preparation binds the exact
revision, selected entry versions and generated rendering bytes. Manager
preparation binds its different source selection and settings. They cannot be
interchanged just because both operations are called prepare.

Do not invent universal request-key controls. Keep the settled distinctions:
fresh additions are distinct, a known invocation's completed result may be
redelivered by the adapter, and an accepted preparation handle retrieves its
recorded seal/acceptance. Repeated preparation need not produce the same token;
the caller uses the returned handle. Changed bytes require fresh preparation.

## 4. A prepared selection is distinct from an actual seal

This is the main semantic clarification the paper exercise needs. Preparation
cannot truthfully record an actual sealer, sealing time or successful submission.
It produces an immutable selection inventory and rendering, with inspectable
read handles. A later seal record binds that selection and records the actual
actor, attribution and operation outcome. It is a new exclusive record, not a
rewrite of the prepared inventory. The prepared bytes do not change at sealing.

The final return manifest can serve as, or reference, that seal record, but must
remain self-contained for verifying its listed members. It includes ordered
members with their exact byte sizes/digests, the exact rendering, audit identity,
form/version binding and actual sealer. Its membership comes from the prepared
selection; there is no second selection step. Identity hashes refer to exact
stored bytes, not a caller's reserialization of an equivalent JSON object.

Preparation/read views shown to the auditor must omit host coordinates and the
manager-only family name. An opaque arrangement binding is sufficient there.
The final manager return manifest can carry the required family/version metadata.
Separate the view from the private record deliberately; do not serialize an
internal struct wholesale because it happens to contain the desired members.

Illustrative data, not a complete wire schema (tokens are symbolic):

```json
{
  "schema": "stewart.reply/1",
  "operation": "prepare",
  "outcome": "completed",
  "data": {
    "prepared_handle": "ap_7",
    "answer_revision": 7,
    "entry_count": 3,
    "selection_view": "view_selection_7",
    "rendering_view": "view_rendering_7",
    "notices": [
      {"reason": "section_unfilled", "section": "comparison", "message": "No comparison entries are recorded."}
    ]
  }
}
```

There is no sealer or "complete answer" grade in that preparation reply. Existing
notices remain nonblocking and require no acknowledgment. An auxiliary observation
count cannot imply a comparison took place.

```text
submit(prepared_handle="ap_7", confirm=false)
  -> dry-run result; no seal
submit(prepared_handle="ap_7", confirm=true)
  -> recorded seal reference, actual actor and bound answer revision
repeat the accepted confirmed call
  -> that same recorded seal, no new mutation
```

Explicit true is required for effect. Use the manager's separately decided
finished-material acknowledgment for commission; do not give a vague universal
`force` flag several meanings. Neither response promises delivery, stopped
processes or close. If manager close won the race, return the actual manager seal
and the applicable ended-state response, not an invented auditor submission.
If an earlier seal cannot be established, expose the uncertainty and supported
continuation rather than guessing that submit failed and preparing again.

## 5. Snapshot reads and exact bindings

Enumerations distinguish the number returned, any established total for the
bound selection, and explicit page continuation/completion. An interrupted or
damaged enumeration does not invent a total for unobserved members. Material
pages bind immutable captured inputs; answer pages bind the observed revision.
An intervening edit produces a stale-view response and an ordinary refresh route
rather than a mixture of versions. Search absence is scoped to what was actually
searched. Read replies return exact text and byte bounds with usable citation
values. Truncation must not masquerade as an entire answer or exhaustive absence.

Response bodies do not imply that the returned state is still current after the
operation completes. Revalidation happens at use. A held prepared rendering can
still be inspected as its fixed selection even if it is no longer submittable;
its handle is not a way to silently read a newer rendering or regain authoring.
Final delivery and readback return the stored sealed bytes, never a fresh render.

## 6. Explicit schemas and conservative interpretation

Use ordinary UTF-8 JSON with one strict control decoder: reject duplicate keys
at every nesting level, unknown request fields, wrong types, nonliteral booleans
and integers outside published bounds. Do not coerce `"true"`, accept misspelled
arguments or silently discard an unrecognized field. Raw attempts are captured
before validation under the existing contract. An integer counter is a bounded
number; an identity token is a string, not a number a caller increments.

Distinguish protocol/schema versions, form/renderer versions, and the writing
implementation identity. Changes to one do not silently redefine the others.
Pin the arrangement and exact stored bytes. Do not promise universal historical
compatibility, negotiate down to a different form, rewrite old records or execute
recorded code. Unsupported data retains its diagnostics. Exact wire schemas and
encoding rules are part of the spec agent's deliverable, not incidental output
of a Rust serializer.

## What the spec agent should produce

For each operation, specify arguments and exact response variants; which facts
are observed versus durable; permitted state effects; handle bindings; view and
record schemas; role-visible fields; size/page bounds; raw-byte versus JSON
behavior; and interruption/next-action semantics. Include literal request/reply
fixtures for success, stale target/preparation, invalid citation, a dry run,
lost-reply repeat, manager seal, partial custody failure and uncertain prior
outcome. Include empty and missing-section submissions, which the agents did not
exercise. A successful operation must not imply unrelated lifecycle completion.

The user need not choose every field name or enum spelling. The important
decisions are these semantic boundaries. A spec agent can resolve routine naming,
encoding and layout choices within them, while returning any newly introduced
authority, material access, outcome restriction or completeness gate for discussion.
