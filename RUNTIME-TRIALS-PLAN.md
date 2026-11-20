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

| Trial | Route | What happens | Starts or placements |
| --- | --- | --- | --- |
| S0 | runtime | Supplied-surface check with Sonnet, reviewed and assembled into a Sonnet profile; no Stewart audit | The check's sessions, as the controller fixes them |
| R1 | runtime | Uninterrupted reference audit | 1 start |
| R2 | runtime | The placement deadline stops the first placement after recorded work; `run` continues | Up to 3 starts |
| R3 | runtime | A witnessed signal stops the first placement after its first recorded entry; `run` continues | 2 starts |
| R4 | runtime | `close` is requested while the first placement is running, after its first recorded entry; close stops it and seals the recorded work as manager | 1 start |
| M1 | Messages | Uninterrupted reference audit | 1 placement |
| M2 | Messages | A witnessed signal stops the first placement after its first recorded entry; `run` continues | 2 placements |
| M3 | Messages | `close` is requested while the first placement is running, after its first recorded entry | 1 placement |

R2's deadline is chosen from R1 before R2's packet is frozen: the elapsed time,
from the start reservation, at which R1 had recorded about half its entries.
R3, R4, M2 and M3 act at the same point, the first `entry` record, so the two
routes and the two kinds of interruption can be compared. For R4 and M3 the
witness runs `stewart close REF` from outside instead of sending a signal. The witness watches the audit log from outside
Stewart's process, signals the placement's process group when the record
appears, and keeps the record, the process identity and the observed
termination outside the archive. If the placement ends first, the interruption
is unexercised; that is an outcome, not permission for another audit.

Order: S0, R1, R2, R3, R4. M1, M2 and M3 can run at any point after their
apparatus is ready. Each step is reviewed before the next is commissioned.

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
recorded entries with manager attribution and no claim of auditor submission,
delivers a package that verifies, awaits or completes confirmation as close
requires, and `run` afterwards refuses `reference_closed`; criteria 2, 5 and 8
below also apply.

R2, R3 and M2 pass when all of these hold:

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
8. `close` completes and the package verifies.

The recorded observations above are kept beside the outcome; none is a
criterion.

## Stopping rules

Stop the series for review on:

- unknown or failed stopping;
- an unexplained wire violation or a failed review;
- a failure of criterion 2 or 4;
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
most seven service starts, each with one authentication check and at most one
model session. The Messages runs use `claude-sonnet-5-5` at $2 per million
input and $10 per million output tokens. With limits of 12 turns, 90,000 input
and 16,000 output tokens per audit, each audit's worst case is about $0.50:
the input limit plus one more request whose size is known only afterwards
(INTERFACE 6.4), and the whole output limit. An interrupted or closed request
can add one estimated charge, so M1, M2 and M3 together stay under $2. The key
can call any model.

## Before any commission

- [ ] Add a witnessed interruption to the service procedure: watch the log
  from outside and, after the k-th `entry` record, either signal the
  placement's process group or run `stewart close REF`; keep the witness
  outside the archive; permit continuation after a reviewed signal
  interruption, and review a close made during a placement. Rehearse both
  offline with the synthetic peer, including an unexercised control.
- [ ] Let C10 live packets select the `entry_record` point, which only
  rehearsals use today, and close as well as a signal; rehearse both.
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
| Cancellation and what an interrupt leaves queued | When the harness sends `notifications/cancelled`; what a witnessed interrupt leaves | Stewart's MCP capture | R3's witnessed interruption, then a cancellation trigger |
| Usage across placements | Each session's results over a continuation | Service check across starts | R2 and R3; provider completeness stays unverified |
| Compaction, re-entry, notice placement, one reminder | A compaction boundary, then the notice, a re-entry call and the reminder still unspent | Stewart's input and output captures | A cheap compaction trigger; R2 and R3 cover re-entry after total context loss |
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
