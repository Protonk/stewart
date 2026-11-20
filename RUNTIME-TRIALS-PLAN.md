# Runtime trials

Live trials of the default-off Claude Code development runtime with the real
harness, and matching Messages API runs, to learn how Stewart behaves when an
audit is interrupted and continued. The [runtime contract](docs/claude-code/CONTRACT.md)
owns the runtime's boundaries and lists what the real harness has not yet
shown. This plan grants no starts and no spend: each packet below needs its own
bounded commission.

## What the first series asks

Does an audit behave gracefully when it is interrupted and then continued? Here
"gracefully" is a custody claim, never a judgment of the answer:

- the ledger keeps exactly the work completed before the interruption;
- `status` names the interruption, its cause and its evidence;
- `run` continues the same audit under the same cumulative limits and starts;
- the continuation tells the auditor it is continuing, and
  `what_am_i_working_with` shows the recorded work;
- the procedural reminder is spent at most once in the audit;
- usage accumulates across placements;
- `close` works from the interrupted and the continued states, and the
  delivered package verifies.

Each series also records, without judging, how the real harness behaves where
the contract has no live evidence: whether the auditor calls
`what_am_i_working_with` before editing again, whether it re-adds text equal to
an earlier entry, how the harness sends several tool calls from one response
and in what order they arrive, whether `system/init` precedes the question, and
whether usage for a submitting placement's last interval arrives.

Not asked: answer quality, compaction, turn or output caps, other families, the
inadequate-evidence variants, and models other than Sonnet in the harness.

## Design

Every trial uses the open-inquiry worked example
([`examples/questions/open/submission`](examples/questions/open/submission))
unchanged apart from the front matter each packet sets. The model is
`claude-sonnet-5-5` on both routes. The runtime runs natively on the
development Mac through the [service procedure](apparatus/claude-code/README.md#native-service-comparison-procedure),
with subscription login, included usage only and paid extra usage disabled.
The Messages runs use the [C10 apparatus](apparatus/c10/README.md) and the API
budget on the `stewart-haiku` key.

Interruptions act at one of two points:

- **P1, the first opportunity:** as soon as the placement's `run_started`
  record appears, before any recorded work.
- **P2, between prepare and submit:** as soon as the auditor's `prepare` call
  has a completed result record in the run directory. `prepare` publishes no
  log record, so this is a new trigger.

| Trial | Route | What happens | Starts or placements |
| --- | --- | --- | --- |
| S0 | runtime | Supplied-surface check with Sonnet, reviewed and assembled into a Sonnet profile; no Stewart audit | The check's sessions, as the controller fixes them |
| R1 | runtime | Uninterrupted reference audit | 1 start |
| R2 | runtime | The placement deadline stops the first placement after recorded work; `run` continues | Up to 3 starts |
| R3a | runtime | A witnessed signal at P1; `run` continues | 2 starts |
| R3b | runtime | A witnessed signal at P2; `run` continues | 2 starts |
| R4 | runtime | `close` requested at P2; close stops the placement and seals the selection as manager | 1 start |
| M1 | Messages | Uninterrupted reference audit | 1 placement |
| M2a | Messages | A witnessed signal at P1; `run` continues | 2 placements |
| M2b | Messages | A witnessed signal at P2; `run` continues | 2 placements |
| M3 | Messages | `close` requested at P2 | 1 placement |

R2's deadline is chosen from R1 before R2's packet is frozen: the elapsed time,
from the start reservation, at which R1 had recorded about half its entries.
The witness watches the audit from outside Stewart's process and, when its
trigger appears, signals the placement's process group or, for R4 and M3, runs
`stewart close REF`. It keeps the triggering record, the process identity and
the observed termination outside the archive. If the placement ends or moves
past the point first, which P2's narrow window allows, the interruption is
unexercised; that is an outcome to record, not a failure and not permission for
another audit.

Order: S0, R1, R2, R3a, R3b, R4. M1, M2a, M2b and M3 can run at any point after
their apparatus is ready. Each step is reviewed before the next is
commissioned.

### What Stewart does at each point

From the specification and code. The trials check that the real harness and
the provider leave these behaviors intact.

| Point | A reasonable app should | Stewart does |
| --- | --- | --- |
| P1 | Stop cleanly and record the interruption. Invent no answer or seal. Account honestly for anything that may have been spent. Leave the audit able to continue, or to close with an honest empty return. On continuation, the auditor starts fresh. | Ends `interrupted` with cause `signal`, exit 5; nothing recorded; the reminder stays unused. Messages aborts the in-flight first request and, if any byte of it was sent, charges an estimate of one turn, its whole `max_tokens` (up to 16,000) and its size ÷ 3 in input. On the runtime the signal can come before the model sees the question; the start is still used and that session's usage is unknown. `run` continues with the continuation notice and an empty ledger. `close` seals the empty selection as manager and delivers an honest empty return. |
| P2 | Never submit a preparation automatically or discard it; keep the entries. On continuation, let the auditor learn that a still-current preparation exists, or ask it to prepare again and review before submitting. A `close` seals the same selection as the manager's, never as the auditor's submission. | Ends `interrupted` with cause `signal`; entries and the preparation are kept; nothing is sealed. On Messages the request carrying the `prepare` result is probably in flight, so the same estimate is charged. On continuation, `what_am_i_working_with` does not mention the preparation. Its handle still works while the revision is unchanged, but an auditor without memory cannot know it, so it prepares again (identical bytes) before submitting. `close` prepares the selection current at its request and seals that as manager; the answer bytes match the auditor's preparation when nothing was edited. A signal during `submit` lets a seal whose link had begun stand; otherwise the submit is refused `placement_stopped`. |

Reminders for whoever prepares the packets:

- **Messages output allowance:** an aborted request is charged its whole
  `max_tokens`, up to 16,000. An interrupted audit's output allowance must cover
  the work before the point, that estimate and at least 1,024 more, or the
  continuation ends `limit_reached` before sending anything.
- **Runtime starts:** a P1 signal can come before the model sees the question,
  and it still uses a start. Every interrupted runtime trial needs at least two
  starts.

Decide before R3b and M2b are frozen whether the continuation notice should
tell a continuing auditor to prepare again before submitting, or whether
re-entry should report a still-current preparation. Today it does neither.

## Criteria fixed before any run

Every placement passes these, or the series stops:

- stopping is observed: no process group remains, and the stop record agrees;
- the procedure's review passes, including MCP call correlation with the
  ledger and the package witness;
- every earlier archive snapshot is preserved byte for byte;
- no wire rule violation goes unexplained.

R1 and M1 pass when the auditor seals and the package is delivered and
verified. Any other ending is incomplete, with its cause named.

R4 and M3 pass when close stops the placement (`stopped_by_close`), seals the
selection current at its request with manager attribution and no claim of
auditor submission, delivers a package that verifies, awaits or completes
confirmation as close requires, and `run` afterwards refuses
`reference_closed`. When no edit came between the auditor's `prepare` and the
close request, the sealed answer bytes equal that preparation's. Criteria 2, 5
and 8 below also apply.

R2, R3a, R3b, M2a and M2b pass when all of these hold:

1. the first placement ends `interrupted` with the expected cause (deadline or
   signal), and `status` reports it with the starts or placements used;
2. the ledger at the interruption equals what the outside witness saw;
3. the next placement's first input carries the continuation notice;
4. every entry recorded before the interruption is still current at the end,
   or was removed by an explicit auditor `delete`;
5. the audit's log holds at most one procedural reminder;
6. cumulative usage and starts carry across placements;
7. the audit ends sealed by the auditor, or with an honest unsubmitted or
   limit ending that `close` then seals as manager;
8. `close` completes and the package verifies;
9. at P2, no seal exists after the interruption, and the interrupted
   preparation's files are retained unchanged. A submit whose link began before
   the signal was observed means the point was overtaken: the trial is
   unexercised, not failed.

The recorded observations above are kept beside the outcome; none is a
criterion.

## Stopping rules

Stop the series for review on:

- unknown or failed stopping;
- an unexplained wire violation or a failed review;
- a failure of criterion 2, 4 or 9;
- any sign the harness is near the weekly allowance.

An allowance that runs out mid-placement is treated as an interruption to
record. Do not provoke one; deliberate usage-limit studies need their own
commission. Reconvene before any use of extra usage.

On the Messages route, stop before any run whose worst-case cost exceeds the
authorization left.

## Running and reviewing

- Check fresh bindings and the explicit approval before each launch. Starts
  are reserved durably; an uncertain outcome is kept, and no later start
  follows uncertain termination or effects. Reaching an allowance or an
  ordinary ending authorizes no continuation or replacement.
- Review raw inputs and traffic, outside package inventories, process
  observations and service captures with their distinct provenance.
  Service-owned captures are not independent witnesses or complete provider
  transcripts. Report pass, failure, incomplete and unexercised outcomes
  separately from any reading of answers.
- Record results against the actual model, harness version, configuration,
  authentication route, writer and binaries. An API result cannot qualify the
  harness profile, and a subscription result cannot satisfy the Messages
  release gate. Apply the evidence retention rules after review.

## Reading the answers

Outcomes are recorded before anyone reads an answer. Afterwards the maintainer
may read each delivered answer and record one coarse, attributed note per audit
(legible and addressing the question as asked, or not, or unclear). The note is
kept apart from the trial record. Nothing from it feeds back into prompts,
tools or criteria; a change it motivates goes through the specification with its
own reason. A return of limits alone is a valid answer.

## Budget

The runtime trials use included subscription usage: S0's check sessions plus at
most nine service starts, each with one authentication check and at most one
model session. The Messages runs use `claude-sonnet-5-5` at $2 per million
input and $10 per million output tokens. A worst case is the input limit plus
one more request whose size is known only afterwards (INTERFACE 6.4), and the
whole output limit. M1 with 12 turns, 90,000 input and 16,000 output tokens is
about $0.50. M2a, M2b and M3, with 24 turns, 180,000 input and 48,000 output
tokens to cover the reminder above, are about $1 each, so the Messages runs
stay under $4. The key can call any model.

## Before any commission

- [ ] Add a witnessed interruption to the service procedure with two
  triggers: the placement's `run_started` record (P1) and the auditor's
  completed `prepare` result record in the run directory (P2, new). On the
  trigger, signal the placement's process group or run `stewart close REF`;
  keep the witness outside the archive; permit continuation after a reviewed
  signal interruption, and review a close made during a placement. Rehearse
  each trigger and action offline with the synthetic peer, including an
  unexercised control.
- [ ] Give C10 live packets the same two triggers (its live packets accept only
  the reminder notice today) and close as well as a signal; rehearse each.
- [ ] Settle the continuation-notice decision above before freezing R3b and
  M2b.
- [ ] Encode the criteria above in the procedure's and C10's reviews where they
  are mechanical, so an outcome is computed rather than judged.
- [ ] Build a native gated writer from a qualified commit for the runtime
  trials, and pin the release writer for the Messages runs. Keep both until
  their audits close.
- [ ] Prepare and freeze each packet: inputs, binaries, profile, model, limits,
  deadline, interruption point, starts or placements and stopping rules. List
  the starts and the worst-case cost in each commission request.

## Unresolved observations

The synthetic runtime suite exercises each of these against the actual core; it
says nothing about how the real harness behaves. "Service check" means review of
Stewart's own captures, stop records and archives through the service procedure;
they are service-owned, not independent witnesses.

| Observation | A live trial would have to observe | Witness | Missing |
| --- | --- | --- | --- |
| Startup validation before the question reaches the provider | Whether question bytes leave the host before `system/init` | stdin/stdout ordering only | A provider or network witness, which the credential boundary excludes; record ordering only |
| Failure recovery and complete provider accounting | The harness after tool errors and API errors, with final results | Service check; package witness | A provider usage witness and a design that elicits errors |
| Relay loss | The harness's reaction to its MCP server dying mid-session | Service check stop and process records | External apparatus that kills the relay, with an outside witness |
| Cancellation and what an interrupt leaves queued | When the harness sends `notifications/cancelled`; what a witnessed interrupt leaves | Stewart's MCP capture | R3a and R3b's witnessed interruptions, then a cancellation trigger |
| Usage across placements | Each session's results over a continuation | Service check across starts | R2, R3a and R3b; provider completeness stays unverified |
| Compaction, re-entry, notice placement, one reminder | A compaction boundary, then the notice, a re-entry call and the reminder still unspent | Stewart's input and output captures | A cheap compaction trigger; R2 and R3b cover re-entry after total context loss |
| Several calls from one response | A response with two or more tool calls, and whether they arrive together or in turn | Service check correlating calls with assistant frames | Observed passively in this series |
| Usage in a submitting placement's final interval | Whether a result frame arrives before the stop that follows submission | Service check stream review | A provider usage witness, or a decision on a drain grace period |
| Turn cap and per-response output enforcement | Reaching the turn or output cap; gating before or after consumption | Stream results | A separately commissioned cap study |

Launching from an already-open descriptor is a design gap between the digest
check and execution, kept as a stated limitation. The environment the harness
receives is known only from Stewart's launch records; a wrapper witness would
change the pinned executable digest.

## Deferred

- **Several tool calls in one response:** a targeted trial waits on what this
  series observes. The auditor issues the calls and Claude Code chooses when to
  send them. Stewart executes them one at a time in arrival order and records
  each. The manager sees them only in the archive and the answer's revision
  history. The question is whether arrival order matches the model's order.
  Correct behavior belongs in Stewart's in-order execution and records, not in
  asking the model to avoid parallel calls.
- **Compaction:** later, defined at Stewart's boundary: what the auditor gets
  after losing context, not how the harness or the provider summarizes.
- **Other interruptions:** killing the harness or Stewart, relay loss and
  cancellation.
- **Wider coverage:** other families, the inadequate-evidence variants,
  turn and output caps, and Haiku or Opus in the harness.
