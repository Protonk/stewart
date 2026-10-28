# Stewart MVP design (draft for discussion)

Drafted 2026-10-28 from source `7f29e83`, after the alignment conversation whose
record is `.scratch/alignment-20261028-01/RESERVATIONS.md` (local). This is a
proposal. Nothing here changes CONTRACTS until you decide it; the last sections
list what would change and what is still open.

## In one paragraph

Stewart becomes a single Linux binary. A manager commissions a question with a set
of files and a destination for the return. Stewart copies and verifies the files,
issues a receipt, and then runs the auditor itself: it drives a model through the
Claude Messages API and gives that model no tools except Stewart's own: read and
search the supplied files, and build an answer. Nothing else exists in the
auditor's world, so there is nothing to contain. When the auditor submits (or the
manager collects), Stewart seals the answer and copies a verified, self-contained
return to the destination. Close records the end of custody; Stewart never deletes
anything. There is no Git, no Python, no macOS-native build, no auditor workspace
and no process to stop except Stewart's own loop.

## What this design rests on

From the alignment conversation (your words in quotes):

- **The auditor has only Stewart's tools (R2).** “R2 I want 100%.”
- **Stewart runs the auditor (R4 declined).** “I prefer the simplicity of R2 over
  R4.” If someone else launches the auditor, they decide whether “only Stewart's
  tools” is true; Stewart running its own model loop makes that true by
  construction.
- **Linux only (R6).** “I don't want this to be a mac tool I want it to run on
  Linux.”
- **No Python baseline or legacy (R8).** “R8 I basically agree with full stop.”
- **No Git (R7).** Questions about history are served by the manager exporting
  what is needed as files: “That's fine.”
- **Stewart never deletes (R3).** It follows from R2: with no auditor workspace,
  there is nothing for Stewart to retire.
- **A small authoring tool instead of a folder snapshot (R5 reshaped).** With no
  shell there is no folder; the tool is the auditor's only way to write, so it
  keeps the decided add/replace/delete and prepare/submit semantics but loses most
  of their difficulty.
- **Question types may come back as profiles (R9 open).** “R2 and R9 also
  interact. We might gain a reason for some typing with this particular
  restraint.” See [Profiles](#profiles-where-question-types-could-live).
- **Integrity by verification (R1, proposed).** See
  [Integrity](#integrity-verification-instead-of-enclosure).

What carries over from CONTRACTS unchanged: receipts, the provisional answer
structure, the auditor-facing signs and their principles, prepare/submit with dry
run by default, manager collect ending authoring, the return's contents, empty and
partial returns, known-missing close, agnosticism about the answer, the three
refusal grounds, exclusive never-overwritten records, the strict control-JSON
rule, and Stewart's responsibility for its own interrupted operations.

## The lifecycle

```
manager                         Stewart                                   model API
-------                         -------                                   ---------
commission  ──request.json──▶   copy + verify files, issue receipt
run         ─────────────────▶  loop: send question + tools  ─────────────▶
                                       ◀──────────── tool calls
                                execute in-process, record, reply ───────▶
                                ... until submit / end / budget / collect
            (or collect) ────▶  seal answer
                                deliver: manifest first, then the return ──▶ destination/
status/help ─────────────────▶  facts about every audit in the home
close       ─────────────────▶  ensure sealed + delivered, record closure (deletes nothing)
```

States an audit passes through: `commissioned` → `running` → `ended` (the loop
stopped without a submission) or `sealed` (submitted or collected) → `delivered`
→ `closed`. `running` can be skipped by a human auditor working through the CLI.

## Commands

Manager:

| Command | What it does |
| --- | --- |
| `stewart commission --request FILE` | Creates the audit, copies and verifies its files, prints the audit ID and receipt digest. Repeating the same request returns the same audit. |
| `stewart run --audit ID` | Runs the auditor loop in the foreground until it ends. |
| `stewart collect --audit ID [--note TEXT]` | Ends authoring now and seals what is recorded, attributed to the manager. |
| `stewart deliver --audit ID [--to DIR]` | Makes another verified copy of the sealed return (the first copy is automatic at seal). |
| `stewart status [--audit ID]` | Lists audits in the home, or one audit in detail: state, destination, copies, interrupted operations, damage. Read-only. |
| `stewart commission-read --audit ID --member NAME` | Prints an original commission member: the recall route a manager uses after losing track. |
| `stewart close --audit ID [--confirm COPY]` | See [Close](#close). |
| `stewart help [COMMAND]` | Slim cheatsheet; per-command detail on request. |

Human auditor: `stewart auditor TOOL --audit ID ...` exposes the same tool surface
the model gets (below), for a person working through a terminal.

Every command takes `--home DIR` (default `$STEWART_HOME`, then
`$XDG_DATA_HOME/stewart`, then `~/.local/share/stewart`). Nothing is selected by
recency or current directory; every audit operation names its audit.

## The commission

The request extends the existing commission format (`stewart.commission-request/2`):

- **Members** as today: one `question`, any `instruction` and `guidance`
  members, and `material` members. New: a member may name a **directory**, which
  Stewart expands at intake into an explicit, recorded list of regular files.
  Symbolic links and special files inside it are reported in the receipt and not
  copied.
- **Destination:** an absolute path to an existing directory. Each delivered copy
  goes into a new subdirectory Stewart creates exclusively inside it
  (`<destination>/<audit-id>-copy-<n>/`), so audits can share a destination and
  later copies never overwrite earlier ones.
- **Profile:** which auditor profile to use (MVP: `read`, the default).
- **Run settings:** model (default `claude-opus-5-5`), effort (default `high`),
  hard limits on turns, total tokens and wall time.
- Custodian, grants and limits text as today. Grants and limits become partly
  mechanical: the profile defines what the auditor can do.

Bounds need raising for whole-directory materials. Proposed starting values:
10,000 files, 16 MiB per file, 1 GiB total. Like the answer bounds, these are
arbitrary and stated in help.

History, diffs, build logs or test output that a question needs are supplied as
files. The manager produces them however it likes; Stewart does not read Git.

## The auditor's world: Stewart's tools and nothing else

Stewart runs its own agent loop over the Messages API. There is no official Rust
SDK, so this is raw HTTPS. The model sees one system prompt, the conversation and
these tools. It has no shell, no file access, no network and no other tools.

**Reading the commission**

| Tool | Returns |
| --- | --- |
| `question` | The question and instructions, verbatim, with any guidance members. |
| `list_materials` | Material names, sizes and line counts; optional name filter. |
| `read_material` | Numbered lines of one material, by line range; a per-call cap with a sign saying how to continue. |
| `search_materials` | Matches for a literal or regular-expression pattern across materials (optionally filtered by name), with context lines; capped, with a sign when results are cut. |

**Building the answer** (the decided authoring semantics)

| Tool | Does |
| --- | --- |
| `answer_add` | Adds an element: a name, the content, and optionally the account marker. |
| `answer_replace` | Replaces an element's content and/or name by its element ID. |
| `answer_delete` | Removes an element from the current answer by its element ID. |
| `answer_inspect` | The current answer: elements (ID, name, size, digest prefix), revision, interrupted operations; or one element's content. |
| `answer_prepare` | Verifies the current answer, returns the manifest and a handle. |
| `answer_submit` | With the handle: a dry run by default; `confirm: true` seals. |

Content arrives in the tool call. Stewart never reads a path the auditor wrote,
because the auditor cannot write paths. Every reply begins with a fixed header
line (`audit 7QK3… · open · revision 4 · 3 elements · 41k of 400k tokens`), and
every refusal gives a stable reason, its effect on the answer and the next call.
Tool definitions use strict schemas, so malformed calls are refused before they
reach Stewart's logic.

**Role guidance** is the system prompt: a few short paragraphs saying what the
space is, that the materials and question are reached through the tools, that
only recorded answer elements are returned, that any outcome is legitimate
(including no finding, missing evidence, an unresolved premise or a proposed
reframe), and that stopping after submission is the end. This is the “acclimate an
agent to the auditor role” idea, and it lives outside the conversation history
that compaction summarizes. It never names the profile or a question type.

**Why not Claude Code or another harness.** A harness brings its own tools,
hooks, plugins, MCP servers and settings layers. Making “only Stewart's tools” true
there means configuring away each of them and then qualifying that the
configuration held. With Stewart's own loop, the tool list Stewart sends is the
whole world. A harness route can return later as an alternative profile if
someone wants it.

## The run loop

1. Build the request: pinned API version, model, effort, adaptive thinking,
   streaming, the profile's tools, the system prompt, and the first user message
   (the question plus a materials index).
2. Send it. Record the full response before acting on it.
3. On `tool_use`: execute each tool call in order, in-process. Record the
   operation's intent (keyed by the call's `tool_use` ID) before its effect and
   the outcome after. Return all results in one user message. Errors go back as
   `is_error` results carrying their sign.
4. On `end_turn` without a submission: send one reminder (“your answer is recorded
   but not submitted; prepare and submit, or end your turn again to stop”). A
   second `end_turn` ends the run.
5. Stop after a confirmed submission; no further model call.
6. Check for a manager collect or close request before every model call and
   every answer mutation. Collect wins any race through the audit's lock.

**Recording.** The conversation is append-only and every turn is written as its
own exclusively created record. That also satisfies the API's requirement that
history with thinking blocks not be edited between requests.

**Long runs.** Server-side compaction (beta) handles conversations that approach
the context window; Stewart appends the complete response content each turn so
compaction state survives. The fixed header and the `question` and
`answer_inspect` tools are how an auditor that lost track finds its way back.
Prompt caching keeps the stable prefix (tools and system prompt) cheap.

**Budgets.** The manager's hard limits (turns, tokens, wall time) are enforced by
Stewart. A task budget (beta) lets the model pace itself within them. At 90% of
the hard limit Stewart adds a mid-conversation system message, a sign: record and
submit now. At the limit the run ends and the audit waits for collect.

**Refusals and fallback.** Requests use the API's server-side fallback, so a
safety decline on the chosen model can be answered by a fallback model. Stewart
records which model produced each response, since that is part of attribution.

**When the loop dies.** If `stewart run` is killed or the API fails persistently,
the audit is `ended`. Any operation left between intent and outcome is resolved by
the next Stewart command touching the audit (published or not) and listed in the
return's provenance. There is no resume in the MVP: a run that ends without a
submission is collected. This keeps zero restart facilities.

**Credentials.** The API key comes from the environment and is never written to
custody. Materials sent to the model go to the API provider; Stewart says so in
help and in the receipt.

## Custody and storage

```
<home>/audits/<audit-id>/
  LOCK                         advisory lock; serializes every mutation
  commission/                  the verified commission bundle (existing format)
  answer/elements/<id>/<v>     write-once element payloads
  answer/revisions/<n>.json    membership after each change (one record per revision)
  answer/ops/<op>.json         operation intent and outcome records
  run/turns/<n>.json           each request and response, append-only
  run/summary.json             model(s), effort, turns, usage, stop reason
  seal/                        sealed manifest and its attribution (submitted or collected)
  copies/<n>.json              each delivery: destination, files, verification
  CLOSED.json                  the closing record
```

Every record is created exclusively and never rewritten. Payloads and records are
made read-only on disk as a guard against accidental edits. Membership is
derivable two independent ways (revision records and operation records), so loss
of one leaves the other. Superseded and deleted payloads stay until the manager
deletes the audit directory.

The home must be a local Linux filesystem. On WSL, a home under `/mnt/` (the
Windows drive mount) is refused with a sign pointing at the WSL filesystem;
destinations there are allowed.

## Seal and delivery

Sealing (confirmed submit or collect) fixes the selection atomically and ends
authoring. Delivery then runs immediately to the commissioning destination:

1. Create `<destination>/<audit-id>-copy-<n>/` exclusively.
2. Write the sealed manifest first.
3. Copy the rest of the return: the question and instructions, the commission
   receipt, each element under a Stewart-generated name with a plain-text index,
   and provenance (submitted or collected and by whom, interrupted operations,
   limit refusals, the run summary, the access log).
4. Read everything back and verify it against the manifest; record the copy.

The **access log** is new and comes free with R2: every material the auditor
listed, read or searched passes through Stewart, so Stewart can record exactly what
was consulted. It is an observation, attributed as such, not a judgment.

A delivery that fails partway keeps its partial directory and reports which
members are missing; `stewart deliver` makes a fresh copy. Empty and partial
returns use the same path and name their gaps. Unknown membership is never
reported as empty.

## Close

`stewart close --audit ID` works from any state:

- If a run is live, it asks the loop to stop and waits for it.
- If the answer isn't sealed, it collects.
- If no verified copy exists, it delivers.
- Then it reports the copy and stops: close is unfinished until the manager
  confirms the copy is safely placed with `--confirm COPY`.
- If a selected member could not be supplied, confirming requires naming the
  undertaking being ended (`--end-undertaking MEMBER`), as decided.
- If custody itself is damaged, close reports exactly what is unverifiable and can
  still be confirmed; it records the damage alongside the closure.

Close writes `CLOSED.json` and refuses later answer or delivery operations. It
deletes nothing. The manager removes the audit directory with ordinary tools
whenever it likes; status shows closed audits and their size. Because close never
destroys anything, “close whenever the manager wants, regardless of state” becomes
easy to honor, including over damaged custody.

## Integrity: verification instead of enclosure

This is the R1 position, applied to what R2 leaves over. The auditor cannot reach
custody at all, because it has no tools that touch it. What is left is everything
else on the machine, the manager included. Stewart does not try to wall custody
off from the person who owns the machine. Instead:

- payloads and records are write-once, read-only, and hashed when written;
- every read, seal and delivery re-verifies what it uses;
- membership is recorded twice;
- any mismatch is reported as damage, with the claims that depend on it blocked
  and the rest still usable.

So tampering or accidents are detected and named, never silently absorbed. This
matches the working premise: participants are cooperative but fallible, and the
goal is to make ordinary operation sturdy and informative, not to build a barrier.

## Profiles: where question types could live

R2 gives typing a job. If the auditor's world is exactly its tool list, then
choosing the tool list is choosing the kind of audit. A **profile** is a named
bundle: the auditor's tools, its role guidance, and the manager-side recipe for
writing a good question of that kind.

- The MVP ships one profile, `read`: the tools above.
- Profiles are chosen by the manager in the commission. The auditor never sees a
  profile name or a question type, only its tools and guidance, as already
  decided.
- Profiles add capabilities, never required answer fields. The answer structure
  stays the same for every profile, so agnosticism holds.
- Later profiles could add, for example, a tool comparing two materials, or a
  sandboxed code-execution tool that runs on the API provider's side rather than
  on the host. That would bring back granted experiments without giving the
  auditor a local shell.

The existing four question types would become recipes attached to profiles rather
than Stewart features. Whether to keep them at all is the open R9 question.

## Platform and packaging

- Linux on x86_64 and aarch64, as a statically linked binary with no runtime
  dependencies. WSL2 is Linux, and runs the same binary.
- macOS is not a target. Development on this Mac runs Stewart in a Linux container.
- The crate stays locked and builds offline from vendored dependencies. New
  dependencies the MVP needs: an HTTPS client with a pure-Rust TLS stack, and a
  regular-expression engine.
- Tests run the loop against a local fake Messages API that replays scripted model
  turns. Acceptance therefore needs no API key or model cost; a separate small set
  of real-model runs checks the loop against the live API.

## The WSL handoff

Your friend receives one archive:

- the `stewart` binary for x86_64 Linux and its checksum;
- the source at the pinned commit;
- a short guide written for someone using Stewart;
- `acceptance.sh`, which runs the scripted acceptance suite (fake model) and
  records the environment (Windows and WSL versions, distribution, kernel,
  architecture, filesystem types of the home and destination) and the results into
  one archive to send back;
- optionally, with their own API key, one real audit of a small sample commission.

## What this would change in CONTRACTS

- **Superseded:** the frozen Python implementation, its status markers and every
  contract that exists only for it (close and removal rules, resource claims,
  holds as a disposal block, program execution, launch acknowledgments, Git-specific
  sections, the Git environment document, writer continuity into the successor,
  legacy interpretation). The custody rules in CLAUDE.md that protect the Python
  baseline would be rewritten for the successor.
- **Changed:** access through explicit grants (now: the profile's tool list), the
  custody home (Stewart's home, not repository-associated), handoff facilities
  (Stewart supplies none besides custody), delivery (decided, at seal, as above),
  close (records only, never deletes), the commission request (destination,
  directories, profile, run settings), and the human auditor (same tools through
  the CLI).
- **New:** Stewart runs the auditor's model loop; the access log; integrity by
  verification; profiles.

## Open questions

1. **R1:** is integrity by verification, with no enclosure of custody from the
   machine's owner, acceptable?
2. **R9:** keep question types as profile recipes, or drop them and keep only
   profiles (or neither)?
3. **Transcript in the return?** Proposed: the access log goes in provenance; the
   full transcript stays in custody, readable by the manager, but is not part of
   the return.
4. **Human auditor in the MVP?** Proposed yes, since it is the same tool surface
   through the CLI.
5. **Model access:** Anthropic API with an API key only, or other providers too?
6. **Defaults:** model `claude-opus-5-5`, effort `high`, and starting values for
   the hard limits.
7. **Commission bounds** for directory materials (proposed above).

## Path from here

1. Remove Python and Git from the active tree; rewrite README, CLAUDE.md, AGENTS
   and CONTRACTS around this design once it is decided.
2. Grow the crate into the `stewart` binary: home, audit identity, lock, records,
   commission v2 with destination, directories, profile and run settings.
3. The tool surface and answer custody, tested through the human CLI and direct
   calls.
4. The run loop with the fake API server: recording, compaction, budgets, signs,
   fallback.
5. Seal, delivery, status, collect and close.
6. Real-model runs on Linux, the user guide, static release builds.
7. The WSL handoff, then any fixes and a second handoff if needed.
