# Unresolved operations

This record holds what remains unknown about how Stewart operates with real
endpoints, the Claude Code harness and its own process boundaries, after the
contracts, the implementation and the synthetic suites. It is meant to help an
investigator choose the next useful investigation. It is not a list to execute.

Status lives elsewhere. The runtime contract's
[evidence owed](../docs/claude-code/CONTRACT.md#evidence-owed) states what the
real harness has not yet shown, and the [README](../README.md#status) states
what has been demonstrated. [Live testing](LIVE-TESTING.md) defines the kinds
of evidence used below. No investigation is credited with knowledge its
instruments cannot supply.

## Using this record

Each question records:

- **Known:** what the contract, implementation, synthetic evidence and earlier
  live observations establish.
- **Unknown:** what remains, and its kind:
  - *behavior:* what a real model, harness or provider does;
  - *decision:* a choice Stewart has not made;
  - *witness:* a fact an instrument we lack could observe;
  - *inaccessible:* a fact no observation from Stewart's side can reach.
- **Elicited by:** the operation or failure condition that would produce
  evidence.
- **Next step:** a deterministic test, a synthetic test, a live test,
  instrument development, contract analysis or a decision.
- **Outcomes:** the observation that discriminates between the plausible
  outcomes, and what each warrants.
- **Depends on:** what must be settled first.
- **Closes when:** the evidence that would close or narrow the question.

When choosing, prefer decisions and contract analysis, which cost nothing, and
questions a planned run reaches passively. Prefer too the questions whose
answers would change what is built. State inaccessible facts as limits rather
than buying runs that cannot reach them.

An unknown is not automatically a defect or an obligation to spend. A question
can be answered, narrowed, retired or consciously left open. When one is
answered, move the established fact to its owner, such as the contract,
INTERFACE or a test, then narrow or remove the entry here.

## Launch and startup

The harness is launched with a pinned executable, profile and launch surface
([installation and startup validation](../docs/claude-code/CONTRACT.md#installation-and-startup-validation)).

### Question bytes before startup validation

- **Known:** the contract wants a configuration check before the first message.
  Under the selected launch, `system/init` arrives only after input, as the
  macOS and Linux harness captures showed. Stewart checks the startup inventory
  against the profile and stops on a mismatch.
- **Unknown:** whether the question has already reached the provider when a
  mismatch is found. *Inaccessible:* only a provider or network witness could
  show it, and the credential boundary excludes both.
- **Elicited by:** any harness start. A deliberate mismatch belongs to the
  synthetic controls.
- **Next step:** a decision. Either keep ordering-only evidence as a stated
  limit, or change the launch so that the first input carries no question
  bytes, at the cost of a model turn per start.
- **Outcomes:** a live run can add nothing beyond the observed input and output
  ordering.
- **Depends on:** nothing.
- **Closes when:** the contract records the decision.

### Launching from an already-open descriptor

- **Known:** the executable's digest is checked before launch, and the harness
  reads its own executable from disk while running.
- **Unknown:** *decision:* the file can change between the check and its use,
  and launching from an open descriptor does not close that window while the
  harness rereads its file.
- **Next step:** contract analysis.
- **Outcomes:** either a launch arrangement that closes the window, or an
  accepted limit.
- **Closes when:** the contract states the limit or the remedy.

### The environment the harness receives

- **Known:** Stewart's launch records name the environment it supplies.
- **Unknown:** *witness:* what the process actually received. A wrapper would
  change the pinned executable digest.
- **Next step:** none unless a defect points here; leave open.

## Tool calls: order and recovery

### Several tool calls from one response

- **Known:** on the Messages route, Stewart returns one `tool_result` per
  `tool_use` of a response, in order. The runtime executes calls one at a time
  in arrival order, queueing those that arrive while another is pending. Exact
  version handles make a stale edit refuse rather than overwrite.
  On Linux with Claude Code 2.1.322 and Sonnet 5.5, 11 assistant messages
  contained multiple calls. In every group, tool IDs arrived in assistant
  stream order, with a reply captured before the next call arrived.
  [Linux trial record](../apparatus/qualified.md#cc-trials-02)
- **Unknown:** *behavior:* whether another harness pin dispatches grouped calls
  in a different order or overlaps them.
- **Elicited by:** any harness run in which an assistant message carries two or
  more tool calls.
- **Next step:** compare tool IDs passively when the harness pin changes.
  Both the assistant stream and MCP arrival captures are service-owned.
- **Outcomes:**
  - *Model order preserved:* narrow the question to the pinned harness version.
  - *Order differs, or calls overlap:* make the records expose both orders, and
    make each reply name the version it acted on.

  The remedy belongs in Stewart's in-order execution and records, never in
  asking the model to avoid parallel calls.
- **Depends on:** nothing.
- **Closes when:** several runs with multi-call messages show the dispatch
  pattern for the pinned version. A new pin reopens it.

### Recovery after tool and provider errors in the harness

- **Known:** macOS encounters recovered from quotation refusals, and showed
  one harness-reported output-cap sequence. The synthetic suite covers error
  replies.
- **Unknown:** *behavior:* how the harness proceeds after provider errors such
  as overload or rate limits, and whether result frames with usage still
  arrive.
- **Elicited by:** tool refusals can be induced through materials and inputs.
  Provider errors cannot be induced on the real route without a proxy, which
  the commissioned route excludes.
- **Next step:** opportunistic live observation; no dedicated spend.
- **Closes when:** observed cases narrow it. It may stay open.

## Stopping, interruption and cancellation

Stopping is specified in [INTERFACE 6.8](../docs/INTERFACE.md#68-stopping) and,
for the runtime, in its
[wire and process contract](../docs/claude-code/CONTRACT.md#development-wire-and-process-contract).

### What a signal or interrupt leaves behind

- **Known:** Stewart's publication gate refuses a late effect. A mutation whose
  log link had begun completes; others are refused `placement_stopped`. The
  synthetic suite exercises cancellation. Outside observers on both routes can
  act on a published placement start or auditor preparation and compare the
  stopped ledger with the witnessed records. On the Messages route, a macOS
  control against a fake provider produced all four timings of a witnessed
  signal.
- **Unknown:** *behavior:*
  - when the harness sends `notifications/cancelled`;
  - whether a tool handler in flight receives a usable cancellation signal;
  - what a harness interrupt leaves queued. Its documented receipt can list
    queued messages that still run.
- **Elicited by:** a witnessed signal while a call is in flight, and a harness
  interrupt for cancellation.
- **Next step:** live witnessed interruptions, which observe what arrives after
  the stop passively. A cancellation trigger needs instrument development.
- **Outcomes:**
  - *No call arrives after the stop:* narrow the question.
  - *A call arrives after the stop:* confirm it was refused and recorded.
  - *A cancellation never wins:* record it as unexercised, not as safe.
- **Depends on:** a reviewed profile for the commissioned harness and model.
- **Closes when:** the pinned version's post-stop traffic has been observed at
  each point the triggers reach.

### Relay loss

- **Known:** the synthetic suite exercises it against the actual core. A
  placement admits one MCP relay; a second stops it as a protocol anomaly.
- **Unknown:** *behavior:* how the real harness reacts when its MCP server dies
  mid-session. It might end the session, retry, or continue without tools.
- **Elicited by:** killing the relay during a placement.
- **Next step:** instrument development (outside apparatus that kills the relay,
  with an independent witness), then a live test.
- **Outcomes:**
  - *The harness ends the session:* confirm Stewart's ending and records.
  - *It continues without tools:* confirm that Stewart detects this and stops
    the placement.
- **Depends on:** the instrument.

### Manager close during a running placement

- **Known:** on the Messages route a watcher looks for a close request every
  250 milliseconds. Before a seal, the stop path aborts an in-flight request
  and refuses an executing mutation `authoring_ended`, and the placement ends
  `stopped_by_close`. The runtime's owner orders a close before a signal and a
  signal before the deadline. Close seals the
  selection current at its request. The scripted tier closes from every state.
  In a live Sonnet Messages audit,
  close at preparation stopped a fully written, unanswered request. Stewart
  estimated its usage, attributed the seal to the manager and verified delivery.
  The exact writer then accepted ordinary close confirmation. At the same
  point on Linux Claude Code, the manager's request stopped the placement.
  Both delivered answer files matched the outside witness's prepared bytes.
  Close confirmed, and a subsequent run was refused `reference_closed`.
  [Paired trial record](../apparatus/qualified.md#cc-trials-02)
- **Unknown:** *behavior:* the timing of requests at other close points.
- **Elicited by:** close at a witnessed point during a placement.
- **Next step:** investigate another close point only if its timing matters
  to a custody decision.
- **Outcomes:** a manager seal claiming auditor submission, or a mutation
  linked after the request, would be a defect. Otherwise, narrow to the points
  observed.
- **Depends on:** a close-capable witnessed trigger.

### A process that dies

- **Known:** the scripted tier kills the binary at fixed points, and
  continuation preserves the recorded work (ACCEPTANCE C13). The runtime
  reconciles a dead placement as `process_gone`. The C10 apparatus withholds
  the export of a placement whose process died.
- **Unknown:**
  - *witness:* live Messages evidence lacks an instrument that exports such a
    placement;
  - *inaccessible:* the provider's charge for the request in flight.
- **Next step:** none until a question needs a live kill. The instrument would
  come first.

### Simultaneous stops and final writes

- **Known:** unit tests cover three cases: a close, signal and deadline
  observed at the same instant; a failed final `runtime-stop.json` or usage
  checkpoint write; and the instant a call enters the internal queue.
  Black-box tests exercise each ordering of the simultaneous stops at fault
  pauses. The checked invariant is that an entry exists exactly when its call
  has a completed reply.
- **Unknown:**
  - *inaccessible* to an external witness: the instants themselves;
  - *witness:* no fault point reaches the final-write failure.
- **Next step:** a deterministic fault point, if a defect ever points here.
  Otherwise leave open deliberately.

## Continuation and context loss

[Continuation](../docs/INTERFACE.md#67-continuation) starts a new conversation
over the same ledger and limits. The runtime's rules are in
[limits, usage and continuation](../docs/claude-code/CONTRACT.md#limits-usage-and-continuation).

### Re-entry after total context loss

- **Known:** the scripted tier checks recovery of recorded work (ACCEPTANCE C4
  and C13). After a witnessed interruption, a Haiku 5.5 Messages continuation
  called `what_am_i_working_with` first. It recovered all three entry handles,
  corrected a refused edit to one entry, and submitted with the other two
  intact. The reminder had already been spent. See `INDEPENDENT-REVIEW.json`
  in the [reviewed continuation](../apparatus/qualified.md#readiness-m3-02-continue-reminder-p2-01).
  In two Sonnet Messages continuations the auditor checked its work before
  editing an empty ledger and consulted re-entry before preparing an existing
  three-entry selection without edits. All three Linux Claude Code continuations
  consulted re-entry. One added entries to an empty ledger. The other two
  submitted the existing selections of one and two entries without edits.
  [Paired trial record](../apparatus/qualified.md#cc-trials-02)
- **Unknown:** *behavior:* how a continuing Sonnet auditor on either route
  handles a populated ledger when it chooses to edit.
- **Elicited by:** any continuation; passive.
- **Next step:** passive observation in continuation runs.
- **Outcomes:** if repeats appear, consider the procedural texts, or a
  mechanical report of exact byte repeats. Never judge whether two texts mean
  the same.
- **Closes when:** narrowed for each route and model observed.

### Compaction in the harness

- **Known:**
  - on the Messages route, one Opus encounter preserved and revised an account
    through real provider compaction;
  - the synthetic harness suite exercises compaction against the core;
  - the contract pins a post-compaction notice, but its delivery point with the
    real harness is undemonstrated, so long-run iteration stays unqualified.
- **Unknown:**
  - *decision:* what Stewart promises after a loss of context, defined at its
    own boundary rather than by how the harness or provider summarizes;
  - *behavior:* what the harness exposes at a compaction boundary, where the
    notice lands, and whether the one-reminder policy holds.

  A later conformance of the Messages route needs a comparable boundary.
- **Elicited by:** a placement long enough to compact. No cheap trigger is
  known.
- **Next step:** contract analysis, then instrument development for a cheap
  trigger, then a live test.
- **Depends on:** the definition.

## Usage and accounting

### Usage across placements in the harness

- **Known:** the contract keeps a separate series per session, and leaves a
  missing final result unknown rather than estimating it. The retained macOS encounters
  captured partial usage. On Linux, all three continued audits counted both
  placements and both unknown usage intervals. Across eight placements Stewart
  captured no final result frame. [Linux trial record](../apparatus/qualified.md#cc-trials-02)
- **Unknown:** *behavior:* how often a real continuation supplies a usable
  final result frame.
- **Elicited by:** any continued harness audit; passive.
- **Outcomes:**
  - *Each session reports a final result:* the series rules suffice.
  - *A session reports none:* the interval stays unknown, as designed.

### The final interval of a submitting placement

- **Known:** the placement stops after the auditor's seal. In the four
  auditor-submitted Linux trials, Stewart captured no final result frame
  before stopping. A later arrival lies outside these observations.
- **Unknown:** *behavior:* whether and when that frame arrives. *Decision:*
  whether to wait for it.
- **Elicited by:** any auditor-submitted harness placement; passive.
- **Next step:** passive observation of the gap between the submit reply and
  any result frame, then a decision.
- **Outcomes:**
  - *The frame arrives within a short bound:* a drain grace period captures it.
  - *It never arrives:* the interval stays unknown.

### Turn and output caps

- **Known:** caps are pinned as supporting controls in harness units. One
  harness-reported output-cap sequence has been observed.
- **Unknown:** *behavior:* whether `--max-turns` gates a model call before
  consumption, and whether a crash's zeroed totals leave lost internal-call
  consumption boundable.
- **Elicited by:** deliberately reaching the caps.
- **Next step:** a dedicated cap study, only if a design comes to depend on the
  caps.

### Provider accounting and billing

- **Known:** Messages usage is provider-reported or estimated by Stewart
  ([INTERFACE 6.4](../docs/INTERFACE.md#64-limits-reminder-and-notice)).
  Harness usage is harness-reported and partial. Estimated dollars are
  diagnostics.
- **Unknown:** *inaccessible* from Stewart: actual billing, the charge for an
  aborted request, and the harness's internal calls. A billing witness could
  bound them after the fact, such as Console usage per model and day, or the
  Usage and Cost API with an admin credential.
- **Next step:** a decision on a billing witness. No live test
  supplies one.

### The subscription allowance running out mid-placement

- **Known:** nothing live. Stewart records whatever ending the harness
  produces.
- **Unknown:** *behavior:* what the harness emits when this happens.
- **Elicited by:** never deliberately; a usage-limit study needs its own plan
  and budget.
- **Next step:** record it if it happens.

## Observability boundaries

### An independent witness of live provider traffic

- **Known:** live Messages captures are Stewart-owned, and only rehearsal has
  an independent provider witness
  ([C10 limits](../apparatus/c10/README.md#evidence-and-review-limits)).
  Harness captures are service-owned.
- **Unknown:** *witness:* an independent view of live traffic. An apparatus
  CONNECT proxy would supply one but would change the commissioned route.
- **Next step:** a decision: state the limit, or build the proxy and accept the
  different route.
- **Closes when:** the decision is recorded. Until then, no live result claims
  an independent provider observation.

## Coverage not yet sought

The real harness has run only the open-inquiry family, with Haiku on macOS, and Sonnet is the model selected for its trials. Other families,
the inadequate-evidence variants and other models in the harness have no live
harness evidence. They become questions here only when a design comes to depend
on how they behave.
