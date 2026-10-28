# Stewart

Stewart answers a narrow question about a set of files. A model that can see
nothing but those files does the investigating, and Stewart hands back a
verified, self-contained answer.

Decisions that are still open appear where they arise, marked **Open.** They are
collected at the end.

## What Stewart is for

Someone has a question about material they hold: a codebase, a set of documents,
logs, exported history. They want it answered by an investigator who works only
from that material and isn't steered along the way. They want to hand the job off,
get a receipt, and later get back an answer they can read and check long after
the investigation is over.

That person is the **manager**. The investigator is the **auditor**. Stewart sits
between them as custodian. It takes copies of the question and material, issues a
receipt, runs the auditor in a world containing only those copies and the means
to record an answer, and delivers the answer together with everything needed to
understand it later.

Stewart doesn't judge answers. "I found nothing", "the evidence isn't here" and
"the question rests on a false premise" are as legitimate as a finding. Stewart
shapes an investigation only through what it puts in the auditor's world.

## Design commitments

1. **The auditor's world is its tool list.** The auditor has Stewart's tools and
   nothing else: no shell, no filesystem, no network. Whatever isn't offered
   doesn't exist for it. There is nothing to escape from, so there is no enclosure
   to build.
2. **Copies in, copies out.** Stewart works on copies of what the manager supplies
   and returns copies to a place the manager chose. It never touches originals.
3. **Nothing is destroyed.** Every record is written once. Stewart deletes nothing;
   ending an audit is a record, not a cleanup.
4. **Verify rather than wall off.** Stewart doesn't try to keep the machine's owner
   out of its storage. It hashes what it writes, re-checks what it uses, and names
   any mismatch.
5. **Every refusal points somewhere.** A refusal states its reason, what it did to
   the answer, and the next thing to do.
6. **One audit, one undertaking.** An audit runs once. Stewart records the
   commission well enough to be understood later but never replays it; asking
   again is a new commission.
7. **Neutral about outcomes.** An answer has no required verdict, kind or outcome
   field, and every shape of answer travels the same path.

## Roles

- **Manager.** Commissions audits, runs them, collects, checks status, closes.
  Uses the `stewart` command line. A person or an agent.
- **Auditor.** Normally a model that Stewart drives through the Claude Messages
  API. A person can also act as auditor through the same tools on the command
  line.
- **Stewart.** The custodian. Holds the copies, runs the auditor, records
  everything, delivers the return.

## An audit from start to finish

```
commission ──▶ run ──▶ seal ──▶ deliver ──▶ close
                 │        ▲
                 └ ended ─┘ (collect)
```

| State | Meaning |
| --- | --- |
| `commissioned` | Copies taken and verified; receipt issued. |
| `running` | The auditor loop is live. |
| `ended` | The loop stopped without a submission; waiting for the manager to collect. |
| `sealed` | The answer is fixed, by the auditor's submission or the manager's collection. |
| `delivered` | At least one verified copy of the return exists at a destination. |
| `closed` | The manager has ended Stewart's custody. |

A person acting as auditor skips `running` and works straight from
`commissioned`.

## Commissioning

The manager writes a request and runs `stewart commission --request FILE`.

```json
{
  "schema": "stewart.commission/1",
  "request_id": "parser-review-01",
  "manager": "Release team",
  "question": "/work/questions/parser-review.md",
  "instructions": ["/work/questions/parser-review-scope.md"],
  "materials": ["/work/src/parser/", "/work/exports/parser-history.txt"],
  "destination": "/work/returns",
  "profile": "read",
  "run": { "model": "claude-opus-5-5", "effort": "high",
           "max_turns": 200, "max_tokens": 4000000, "max_minutes": 120 }
}
```

- **Question and instructions** are files, copied verbatim. The auditor can always
  ask to see them again.
- **Materials** are files or directories. A directory is expanded at intake into
  an explicit list of regular files with relative names. Symbolic links, devices
  and other special files are listed in the receipt as not copied, with the reason.
- **Destination** is an existing directory where returns will be delivered. It is
  chosen now so the answer has somewhere to go without anyone being around.
- **Profile** chooses what kind of auditor world to build (see below).
- **Run settings** pick the model and effort and set hard limits on turns, tokens
  and wall time.
- **`request_id`** is the manager's key. Repeating an identical request returns the
  same audit; a different request under the same key is refused.

Stewart copies everything into its own storage, checks each copy against the bytes
it read, and prints the audit ID, the receipt and the receipt's digest. The
receipt lists every copied file with its name, size and SHA-256, everything not
copied and why, the profile and the run settings. It also says plainly that the
material will be sent to the model provider during the run.

Material that only lives in version control, such as history, diffs or blame, is
supplied as exported files. Stewart reads files, not repositories.

**Open.** Size limits for a commission. Proposed starting values, stated in help:
10,000 files, 16 MiB per file, 1 GiB in total.

**Open.** Whether the manager may (or must) pin expected digests for listed files,
so that a file changed between choosing and commissioning is caught at intake.

**Open.** Whether to record where materials came from (a repository and commit,
say) as an uninterpreted provenance note in the request, so the receipt can carry
it.

## The auditor's world

### Profiles

A **profile** is a named kind of audit: the auditor's tools, its role guidance,
and the manager-side recipe for writing a good question of that kind. Because the
auditor's world is exactly its tool list, choosing the tools is choosing the kind
of audit. Profiles can add capabilities; they never add required answer fields.

The auditor never sees a profile's name. It sees its tools and its guidance.

The first profile is `read`: read and search the materials, build an answer.

**Open.** Which question recipes ship with `read`, and whether there are any at
first.

**Open.** Later profiles. A natural next one adds code execution in a sandbox the
model provider hosts, with materials uploaded to it, so experiments become
possible without giving the auditor anything on the manager's machine.

### Tools in the `read` profile

Reading the commission:

| Tool | Returns |
| --- | --- |
| `question` | The question and instructions, verbatim. |
| `list_materials` | Material names, sizes and line counts; optional name filter. |
| `read_material` | Numbered lines from one material by line range. Capped per call, with a note saying how to continue. |
| `search_materials` | Matches for a literal or regular-expression pattern, optionally limited by name, with context lines. Capped, with a note when results were cut. |

Building the answer:

| Tool | Does |
| --- | --- |
| `answer_add` | Adds an element: a name, its content, and optionally the account marker. |
| `answer_replace` | Replaces an element's content and/or name, by element ID. |
| `answer_delete` | Removes an element from the current answer, by element ID. |
| `answer_inspect` | Shows the current answer, or one element's content. |
| `answer_prepare` | Verifies the current answer; returns its manifest and a handle. |
| `answer_submit` | With the handle: a dry run by default; `confirm: true` seals. |

Every reply starts with the same header line, so an auditor that has lost track
sees where it is before anything else:

```
audit 7QK3RM · open · revision 4 · 3 elements · 41k of 4,000k tokens
```

Every refusal has a stable reason, its effect on the answer, and the next call:

```
refused: stale_handle · answer unchanged · the answer changed after prepare; call answer_prepare again
```

Replies never mention where anything is stored.

**Open.** Non-text materials. `read_material` serves text. Images and PDFs could be
passed to the model in their native form; other binary files can be listed but not
read. Which of these the first release supports.

### Role guidance

The system prompt is a short orientation: this is your whole world; the question
and materials are reached through these tools; only recorded answer elements are
returned; any outcome is legitimate, including no finding, missing evidence, an
unresolved premise or a better question; when you have submitted, you are done. It
never names the profile or a question type.

**Open.** The exact orientation text, and whether there is one orientation for
every profile or one per profile.

## Building the answer

An answer is an optional readable account plus ordered elements. Each element is
exact bytes with an ID and version that Stewart assigns and a name the auditor
chooses. Names are labels; duplicates are allowed and reported. One element may
carry the account marker, which Stewart never interprets. An empty answer is a
valid answer.

Every edit is atomic and recorded the moment it succeeds:

- **Add** stores the content and adds it to the answer.
- **Replace** stores the new version and swaps it in; the old version is kept.
- **Delete** removes the element from the answer; its content is kept.

**Prepare** verifies every element and returns a manifest and a handle tied to the
exact current revision. **Submit** with that handle is a dry run unless confirmed.
Any edit after prepare makes the handle stale, and submit refuses rather than
quietly taking newer content. A confirmed submit seals the answer and ends editing.
Repeating it returns the same submission.

Each edit is an operation whose ID is the ID of the tool call that requested it.
Stewart records an operation's intent before acting and its outcome after. If the
process dies between the two, the next Stewart command that touches the audit
settles it, as either landed or not, and records which. An auditor that submits
while one of its own operations is unresolved is told what that operation would
have changed; the submission goes ahead, and the return's provenance says so.

**Open.** Answer limits. Proposed starting values, stated in help and in the
receipt: 256 elements, 64 MiB per element, 256 MiB for the current answer, 1 GiB
of kept old versions. When old versions reach their cap, only large edits are
refused; small edits, delete, prepare and submit always work.

## Running the auditor

`stewart run --audit ID` runs the auditor in the foreground.

1. **Start.** Send the system prompt, the profile's tools and a first message
   holding the question and an index of materials, with adaptive thinking,
   streaming, and the run's model and effort.
2. **Record before acting.** Every request and response is written to its own
   record before anything else happens. The conversation is append-only.
3. **Tool calls.** Execute each call in order, inside Stewart, and send all the
   results back in one message. Errors go back as error results carrying their
   refusal text.
4. **Ending without submitting.** If the model ends its turn without submitting,
   Stewart sends one reminder that the answer is recorded but not submitted. If it
   ends its turn again, the run ends.
5. **Submitting.** After a confirmed submission there are no more model calls.
6. **The manager steps in.** Before every model call and every answer edit,
   Stewart checks for a collect or close request. Collect wins any race.

The running process holds the audit's run lock, so status can tell a live run from
a dead one without guessing.

**Long runs.** The provider's server-side compaction summarizes old context as
the conversation nears its limit; Stewart keeps the full response content each
turn so compaction carries forward. The orientation lives in the system prompt and
the tool descriptions, outside the conversation history that compaction
summarizes. The header line and the `question` and `answer_inspect` tools are
there for an auditor that has lost its thread.

**Limits.** Stewart enforces the manager's hard limits. A task budget lets the
model pace itself within them. At 90% of a limit Stewart adds a short operator
message saying the run is nearly out and the answer should be recorded and
submitted. At the limit the run ends.

**Refusals by the model.** Requests allow the provider's fallback, so a safety
decline on the chosen model can be answered by another model. Stewart records
which model produced each response.

**Failure.** If the process is killed or the provider keeps failing, the audit
becomes `ended`. Unsettled operations are settled by the next command and listed
in provenance. A run that ends without a submission is collected; it is not
resumed.

**Credentials.** The API key comes from the environment and is never written to
storage.

**Open.** Defaults for model, effort and the three hard limits.

**Open.** Whether a run that died can be continued from its recorded conversation.
The design leans toward never: continuing is a second investigation in all but
name.

**Open.** Whether to support model providers other than the Claude API.

**Open.** How many reminders, if any, before an unsubmitted run ends. Each one is
a small push toward submitting.

## Collecting

`stewart collect --audit ID [--note TEXT]` ends authoring at any time and seals
what is recorded. The answer is marked as collected by the manager, not submitted
by the auditor, and the note is kept with it. A collect and a submit that race
have exactly one winner. Collecting an `ended` audit is the normal way to get its
answer out.

## Sealing and delivery

Sealing fixes the answer and records who sealed it. Delivery to the commissioning
destination follows at once:

1. Create a new directory inside the destination,
   `<destination>/<request_id>-<audit-id>-copy-<n>/`, failing if it already exists.
2. Write the sealed manifest first.
3. Write the rest of the return.
4. Read everything back and check it against the manifest, then record the copy.

```
parser-review-01-7QK3RM-copy-1/
  MANIFEST.json        authoritative: every member, its digest, the seal
  QUESTION.md
  instructions/...
  RECEIPT.json         the commission receipt
  answer/INDEX.txt     element names, IDs, order, account marker
  answer/01-....md     elements under generated names
  PROVENANCE.json      sealed by whom, unresolved operations, limit refusals,
                       run summary (models, effort, turns, usage, stop reason),
                       access log
```

The **access log** lists every material the auditor listed, read or searched, in
order. Everything the auditor saw came through Stewart, so this is an observation,
not an inference. It records what was consulted, not what was understood.

`stewart deliver --audit ID [--to DIR]` makes another copy of the same sealed
return. A delivery that fails partway keeps its partial directory and says which
members are missing. Empty and partial answers go through the same path and name
their gaps. Unknown membership is never reported as empty.

The seal reply and every copy print the manifest's digest, so the manager holds a
reference to the sealed answer outside Stewart's storage.

**Open.** Whether the full conversation belongs in the return. The design leans
no: the access log and run summary go in the return, and the conversation stays
in Stewart's storage, where the manager can read it until deleting the audit.

## Status and recall

`stewart status` lists every audit in the home with its state, destination,
copies and size. `stewart status --audit ID` shows one audit in detail: state,
whether a run is live, copies and their verification, unresolved operations, and
any damage. Status is read-only and states facts; it doesn't judge whether an
answer is complete.

`stewart commission-read --audit ID --member NAME` prints an original commission
member, so a manager who has lost track can recover exactly what was asked and
supplied.

`stewart help` is a short cheatsheet; `stewart help COMMAND` gives detail.

Nothing is selected by recency or by the current directory. Every audit command
names its audit.

## Closing

`stewart close --audit ID` works from any state:

- a live run is asked to stop, and close waits for it;
- an unsealed answer is collected;
- if no verified copy exists, one is delivered;
- then close reports the copy and stops. It finishes only when the manager
  confirms the copy is safely placed: `stewart close --audit ID --confirm COPY`.

If a member could not be supplied, confirming also requires naming what is being
given up (`--end-undertaking MEMBER`). If Stewart's own records are damaged, close
reports exactly what can't be verified and can still be confirmed; the damage is
recorded with the closure.

Close writes the closing record and refuses later answer and delivery operations.
It deletes nothing. The manager removes an audit's directory with ordinary tools
whenever they like. Because close destroys nothing, it can always be honored,
whatever state the audit is in.

## Storage and integrity

```
<home>/audits/<audit-id>/
  LOCK                       serializes every change to the audit
  RUN.lock                   held by a live run
  commission/                copied question, instructions, materials, receipt
  answer/elements/<id>/<v>   element versions, write-once
  answer/revisions/<n>.json  answer membership after each change
  answer/ops/<op>.json       operation intent and outcome
  run/turns/<n>.json         every request and response
  run/summary.json
  seal/                      sealed manifest and who sealed it
  copies/<n>.json            each delivery and its verification
  CLOSED.json
```

The home is `--home`, then `$STEWART_HOME`, then `$XDG_DATA_HOME/stewart`, then
`~/.local/share/stewart`. It must be on a local Linux filesystem. On WSL, a home
under `/mnt/` (the Windows drives) is refused, with a note pointing at the WSL
filesystem; destinations there are fine.

Every record and payload is created exclusively, never rewritten, and made
read-only. Answer membership can be rebuilt two independent ways, from revision
records and from operation records, so losing one leaves the other. Every read,
seal and delivery re-verifies what it uses.

What this protects against: accidents, crashes, half-finished operations, and
well-meaning edits by people or agents who shouldn't be in there. The auditor
can't reach storage at all. What it doesn't protect against: someone who owns the
machine and deliberately rewrites both a payload and its records. The receipt
digest and the sealed manifest digest, which the manager holds, are the anchors
against that.

**Open.** Whether verification with outside anchors is enough, or whether storage
should also be made harder to change for the machine's own user.

## People as auditors

`stewart auditor TOOL --audit ID ...` gives a person the same tools a model gets,
with the same records, header lines and refusals. Content for `answer_add` comes
from a file or standard input. A person isn't confined the way a model is; they
are trusted to work from the commission, and their answer travels the same path.

**Open.** Whether people as auditors are in the first release.

## Platform and distribution

- Linux on x86_64 and aarch64, as one statically linked binary with no runtime
  dependencies. WSL2 runs the same binary.
- Other systems run Stewart inside Linux: on a Mac, in a Linux container.
- Stewart talks to one network service, the model provider, over HTTPS. Nothing
  else touches the network.
- The source builds offline from vendored dependencies.

## Testing

Stewart's own loop makes the auditor scriptable. The test suite runs every flow
against a local fake of the Messages API that replays scripted model turns: tool
calls, refusals, compaction, lost connections, a model that never submits. That
covers the whole lifecycle with no API key and no model cost. A small separate
set of runs checks the loop against the real API.

A release is accepted when the scripted suite passes on Linux x86_64 and aarch64
and on WSL2, and the real-API set passes on at least one of them.

## What Stewart doesn't do

- Give the auditor a shell, files, network access or tools beyond its profile.
- Read version control.
- Delete anything.
- Replay or restart an audit.
- Let anyone steer the auditor mid-run, beyond the manager collecting or closing.
- Judge an answer's worth or require a particular kind of answer.
- Run on anything but Linux directly.

## Open decisions

| Area | Decision |
| --- | --- |
| Commissioning | Size limits; pinned digests for listed files; a provenance note for where materials came from. |
| Profiles | Which recipes ship with `read`; the first profile after `read`. |
| Materials | Support for images, PDFs and other non-text files. |
| Orientation | The text, and whether it differs by profile. |
| Answers | The starting limits. |
| Runs | Default model, effort and limits; continuing a dead run (leaning never); other providers; reminders before an unsubmitted run ends. |
| Return | Whether the full conversation is included (leaning no). |
| Integrity | Whether verification with outside anchors is enough. |
| People | Whether people as auditors are in the first release. |
