# Readiness review before manager-interface work

This plan owns a read-only review that challenges the release plan's entry
assessment for manager-interface work. It does not critique or revise the
manager-interface plan. It looks for three kinds of trouble that could swamp
that work once it begins and reports them to the principal, who decides what
each one means for entry.

**State: not started.** Nothing below has been dispatched. The orchestrator
updates this line, the task boxes and the [run record](#run-record) in place
and commits those updates.

## The three questions

| | Question | A finding is |
| --- | --- | --- |
| A | Where do we rely on a test for understanding when that test checks its own input, instead of building a principled fixture or meeting the specified failure conditions? | A test, self-test or stand-in whose passing result says less than its name and place suggest, under the [finding rule](#finding-rule). |
| B | Where, in what the `claude` binary or the Messages API treats as normal operation, does Stewart refuse, cap, stop or rewrite what comes back from the auditor, so that a manager would think `claude` had the problem? The necessary restrictions on the auditor's world (no shell, no other files, no network) are not the subject. | An intervention on the auditor's return path that is undecided, differs between the two routes, or reaches the manager without naming Stewart as the actor. |
| C | Where is the documentation about questions needless, confusing, out of line with the mission, summative or redundant? Manager-interface work is expected to turn much of it into code, where an unexplained or duplicated passage costs more. | A passage an implementer would have to guess at, reconcile, or carry into code without a mechanism behind it. |

The manager-facing CLI is meant to behave alike over the Messages API and the
Claude Code runtime. In B, record a difference between the routes even when
each route's behavior is individually decided.

## Authority and decisions

The principal commissioned this review and chose, for this one bounded use:

- **A runs through the harness's Workflow tool.** The principal enables it per
  session (the setting is called ultracode) and intends to leave it on through
  A. Reviewers are Opus 5.5 at high effort, set with the tool's per-agent
  `model` and `effort` options. Refuters and the orchestrator use the session
  model. The script does not exist yet; the orchestrator writes it at dispatch
  from the briefs this plan specifies.
- **At most eight agents at once.** Reviewers and refuters share that pool. A
  goes first; B and C follow and may run together.
- **B and C are dispatched by hand** with the Agent tool. Their briefs differ on
  purpose, and what B's crossing needs depends on what comes back.
- **Results come back in chat** as one list, ranked by how directly an item
  would mislead or stall the specification work. Each item carries the
  orchestrator's proposed disposition: blocks entry, input to the specification
  work, or accept. The principal decides. No findings document is tracked
  unless the principal asks.

Dispatch has not been authorized yet: the principal asked for this plan to be
committed first. A session that did not receive these choices from the
principal directly confirms them, and that the Workflow tool is enabled, before
dispatching anything. The review has no cap on findings; the orchestrator
reports the number of agents used.

## Limits

- Dispatched agents are read-only, except that each writes its own result file
  under `.tmp/readiness/`. No dispatched agent edits a tracked file. The
  orchestrator alone edits this plan's state and removes it at completion.
- Nothing changes under `.scratch/`, under `.tmp/` outside `.tmp/readiness/`,
  or in retained evidence outside the checkout.
- No launch of `claude` in any form, including `--help` and `auth status`; no
  model-consuming Stewart run; no container suite. A question only a live run
  could settle is listed in the delivered results as a candidate for a later
  live commission, which the principal routes.
- Requests to outside services carry no project names, paths or personal
  details.
- Every brief is self-contained and tells its agent not to open or search any
  `*-PLAN.md`. The [leads](#leads-from-reconnaissance) below are the
  orchestrator's comparison and must not reach a reviewer. A lead no reviewer
  reproduces is examined directly before it is dropped or kept.
- Driver independence. Reviewers of `apparatus/driver/` (batches 16 to 27) and
  the refuters of their findings read and search only `apparatus/` and the
  specifications, run no search whose output prints `service/src` or
  `service/tests` lines, and write in specification terms. Only their own
  unedited result files may be handed to a driver author; the orchestrator's
  merged list, which draws on implementation reading, may not. Reviewers of the
  other `apparatus/` batches (28 to 32) may follow imports into the driver but
  raise no finding against a driver file; they pass a note for the driver
  batch. The session that wrote this plan has read `service/src` and edits no
  driver.

## A: tests that test their own input

### Rubric

One record per unit: a `#[test]` function, a driver case, a `def test_`
function, a function registered with `@selftest`, each named check inside a
monolithic `self_test()`, and each stand-in or fake named as a subject. The
orchestrator computes each batch's expected units and passes their names in the
brief: from the commands in the first task below, and from each driver's
`--list` output, which runs no binary. A batch has returned when its file
exists and names every expected unit.

| Property | Values, recorded for the assertions that carry the claim the unit's name makes |
| --- | --- |
| Oracle | `specification`: read from the specification text when the test runs. `witness`: kept or computed by code that shares nothing with the path under test. `cited-literal`: written by hand, and the reviewer can cite the specification passage that gives the value. `literal`: written by hand with no such passage. `self`: produced by the code under test or by the helper that built the input. Record the weakest. |
| Fixture | `real`: bytes with a recorded capture source. `specified`: every member traceable to a cited specification passage. `synthetic`: built by hand otherwise. `none`: no external counterpart. Service-side reviewers add `mirrors-code` when a synthetic fixture repeats literals the code under test hard-codes; driver-side reviewers add `narrower-than-specification` when it exercises less than the cited passage allows. |
| Controls | For the property the unit names, which exist: a sabotage control (ACCEPTANCE's [first rule](ACCEPTANCE.md#rules-every-check-follows): a deliberately broken input or build that the check must catch), a differing case, an invariance case. A control in another file counts and is cited. For driver cases, "exists" means declared with the case; whether it fired belongs to run records. |
| Vacuity | Any of: `any-error` (passes on any failure, not the specified one); `indistinct` (the fixture repeats one value, so members cannot be told apart); `skip-as-pass` (an early return or skip is counted as a pass; name the line); `not-run` (ignored or compiled out unless a named runner executes it). |
| Unreached conditions | Specified failure conditions for the behavior that the batch does not reach, each keyed by its specification clause. These are candidates only. |

Service-side reviewers read whatever their tests call, including sibling fault
and sabotage files for controls, and list the files they opened. Driver-side
reviewers read other driver modules as their cases require and classify only
their own batch's units.

### Finding rule

A unit yields a finding when any of these holds; its class is the name in
parentheses.

- Its oracle is `self` (`self-oracle`).
- It has a vacuity flag (`vacuous`).
- Its fixture is `synthetic` and it stands for an external counterpart
  (provider, harness, operating system, the real service) whose behavior later
  work will take from it (`unanchored-fixture`).
- It has no control of any kind for a property a
  [reliance row](#what-later-work-leans-on) names (`no-control`).
- It is a stand-in or fake whose model of the real counterpart has no stated
  source outside its author (`stand-in-provenance`).

A `literal` or `cited-literal` oracle alone is tallied, not raised. Equality of
two copies of a pinned text is a legitimate check and is recorded as that.
Unreached-condition candidates are merged across batches by the orchestrator;
only a clause no batch reaches becomes a finding (`unreached-condition`).

A finding record has: an identifier (`A<batch>-<n>`), batch, file, unit, line,
the five property values, class, a one-sentence claim, the evidence, its side
(`specification-terms` or `implementation`), the reliance row, and one line on
what a principled fixture would be.

### Refutation

Each finding goes to one fresh agent, given the finding record and the batch's
file list and told to refute it, defaulting to `refuted` when uncertain. Its
verdict is `stands`, `refuted` or, for a driver-side finding that cannot be
settled without the service, `unsettled-driver-side`. Unsettled findings are
kept and reported as questions for a service-side reader, not counted as
refuted. Survivors are reported with the counts of refuted and unsettled.

### Files

Reviewers write `.tmp/readiness/a/batch-NN.review.json`: the full
classification table, findings, unreached-condition candidates and files
opened. Refuters write `.tmp/readiness/a/<finding-id>.refute.json`. The
orchestrator writes `.tmp/readiness/a/merged.json`.

### What later work leans on

| Row | Later work | Batches |
| --- | --- | --- |
| R1 | One set of commissioning rules, extracted for CLI and MCP | 3, 6, 13, 17, 18, 21 |
| R2 | Returned question, lifecycle and custody comparisons | 3, 4, 5, 7, 8, 9, 14, 15, 17, 18, 20, 23 |
| R3 | Runtime comparisons and the subscription track | 6, 12, 24, 25, 26, 27, 29, 30 |
| R4 | Messages API conformance | 1, 2, 10, 11, 14, 19, 21, 22, 23, 28, 31 |

Batch 16 is the driver machinery under every row. Batch 32 falls under none;
its survivors are reported without a row. A unit is trusted when its oracle is
`specification` or `witness`, it has no vacuity flag and no finding against it
stands. A row in which no batch has a trusted unit for the behavior the later
work names is a finding, and is refuted like any other.

### Batches

Thirty-two batches. "Starts from" is where the reviewer begins reading the
specification, not a boundary. Driver cases cite ACCEPTANCE claims, which lead
to their INTERFACE sections.

| # | Files | Starts from |
| --- | --- | --- |
| 1 | `service/tests/run.rs`, from the start through `a_dead_placement_is_reconciled_with_estimated_charges` | INTERFACE 6.2 to 6.8 |
| 2 | `service/tests/run.rs`, from `descriptor_credential_reaches_provider_without_entering_captures` to the end | INTERFACE 5.7, 6.1, 6.3, 8, Appendix C |
| 3 | `service/tests/manager.rs`, `manager_seal.rs` | INTERFACE 3 and 5 |
| 4 | `service/tests/answer.rs`; `common/mod.rs` and `answer_support/mod.rs` as subjects | INTERFACE 7, QUESTION-FORMS |
| 5 | `service/tests/delivery.rs`; `fixture/mod.rs` as subject | INTERFACE 8 and 5.8 |
| 6 | `service/tests/claude_code.rs` | `docs/claude-code/CONTRACT.md` |
| 7 | `service/tests/faults.rs`, `sabotage.rs` | INTERFACE 9, Appendix C |
| 8 | `service/tests/answer_faults.rs`, `answer_sabotage.rs` | INTERFACE 7, Appendix C |
| 9 | `service/tests/close_faults.rs`, `close_sabotage.rs` | INTERFACE 5.8 and 8, Appendix C |
| 10 | In-module tests of `service/src/provider/`: `response.rs`, `tolerant.rs`, `request.rs`, `policy.rs`, `mod.rs` | INTERFACE 1.2, 6.2, 6.5 |
| 11 | In-module tests of `service/src/provider/`: `transport.rs`, `http.rs`, `url.rs`, `tls.rs` | INTERFACE 6.1, 6.6, 6.8 |
| 12 | In-module tests of every file in `service/src/claude_code/` | `docs/claude-code/CONTRACT.md` |
| 13 | In-module tests of `service/src/`: `forms.rs`, `frontmatter.rs`, `help.rs`, `scan.rs`, `names.rs`, `ids.rs` | INTERFACE 2, 3 and 5.9, QUESTION-FORMS |
| 14 | In-module tests of `service/src/`: `json.rs`, `bodies.rs`, `reply.rs`, `log.rs`, `runs.rs`, `usage.rs`, `returns.rs` | INTERFACE 1, 4, 6.4, 8.2 |
| 15 | In-module tests of `service/src/answer/` and `service/src/ops/`, and of `util.rs`, `credential.rs`, `fault.rs` | INTERFACE 5.8, 6.1 and 7, Appendix C |
| 16 | `apparatus/driver/driver_core.py`, `stewart_driver.py`, `rawjson.py`: registry, control machinery, skip handling, self-test | ACCEPTANCE rules and tiers |
| 17 | `apparatus/driver/cases_foundation.py`, from the start through `close.killed-before-closed` | The cited claims |
| 18 | `apparatus/driver/cases_foundation.py`, from `close.during-intake` to the end | The cited claims |
| 19 | `apparatus/driver/cases_run.py`, `run_support.py` | The cited claims |
| 20 | `apparatus/driver/cases_after_launch.py` | The cited claims |
| 21 | `apparatus/driver/cases_compaction.py`, `cases_credentials.py`, `cases_effort.py`, `cases_guidance.py`; `credential_observer.py` as subject | The cited claims |
| 22 | `apparatus/driver/fake_provider.py`, `procedure.py`, as subjects with their self-tests | INTERFACE 6 |
| 23 | `apparatus/driver/reacting_auditor.py`, `mini_stewart.py`, `answer_witness.py`, as subjects with their self-tests | INTERFACE 7 and 8, QUESTION-FORMS |
| 24 | `apparatus/driver/claude_code.py`, runtime cases, before `def self_test()`; `CLAUDE-CODE.md` | `docs/claude-code/CONTRACT.md` |
| 25 | `apparatus/driver/claude_code.py`, from `def self_test()` to the end | `docs/claude-code/CONTRACT.md` |
| 26 | `apparatus/driver/claude_code_observer.py`, `claude_code_peer.py` with their guides | `docs/claude-code/CONTRACT.md` |
| 27 | `apparatus/driver/claude_code_surface.py`, `claude_code_service_witness.py` with their guides | `docs/claude-code/CONTRACT.md` |
| 28 | `apparatus/c10/test_c10.py`; `check_review.py`, `check_reporting.py`, `check_operations.py`, `fake.py` and `verify.py` as subjects | ACCEPTANCE real-model tier, `apparatus/c10/README.md` |
| 29 | `apparatus/claude-code/test_probe.py`, `test_bounded.py`, `test_protocol.py`, `protocol_check.rs` | `apparatus/claude-code/README.md`, `docs/claude-code/CONTRACT.md` |
| 30 | `apparatus/claude-code/test_profile.py`, `test_surface_check.py`, `test_pin.py`; `fake.py` and `fixture.py` as subjects | `apparatus/claude-code/README.md`, `docs/claude-code/CONTRACT.md` |
| 31 | `apparatus/sanity/test_launch.py`; `apparatus/sanity/exercise.py` as subject; `apparatus/test_build_markers.py`; the self-test of `apparatus/check_links.py` | `apparatus/sanity/LAUNCHER.md`, INTERFACE Appendix C |
| 32 | The self-test of `apparatus/qualified.py` | DEVELOPMENT, "Evidence and retention" |

- [ ] Confirm the batch list covers every tracked file with tests, and record
  each batch's expected units:

  ```sh
  git ls-files 'service/*.rs' 'apparatus/*.rs' | xargs grep -c '#\[test\]' | grep -v ':0$'
  git ls-files 'apparatus/*.py' | xargs grep -cE '^[[:space:]]*def test_|^@case|^@selftest|self_test\(' | grep -v ':0$'
  python3 -I -B apparatus/driver/stewart_driver.py --list
  python3 -I -B apparatus/driver/claude_code.py --list
  ```

- [ ] Write the workflow script and run it: review, then refute, eight agents
  at a time. Record its run identifier and script path in the run record as
  soon as it is launched.
- [ ] Merge unreached-condition candidates across batches; refute the clauses
  no batch reaches.
- [ ] Collect survivors per reliance row and apply the trusted-unit test.

## B: interventions on the auditor's return path

Four agents whose briefs must not be merged. None is told what another found.
The reading lists are starting points: each Stewart-side agent follows a
trigger through to the words the manager sees.

| Agent | Starts from | Writes |
| --- | --- | --- |
| Stewart side, Messages route | INTERFACE 1.2, 4.5, 5.6, 5.7, 6, 7 and 9, Appendices A and B; `service/src/provider/`, `answer/`, `ops/run.rs`, `ops/status.rs`, `ops/presentation.rs`, `reply.rs`, `usage.rs` | `.tmp/readiness/b/stewart-messages.md` |
| Stewart side, Claude Code route | `docs/claude-code/CONTRACT.md` and `RUNTIME-REFERENCE.md`; `service/src/claude_code.rs`, `service/src/claude_code/`, and the same `ops/` files | `.tmp/readiness/b/stewart-claude-code.md` |
| Claude side | Public documentation only, through the `claude-code-guide` agent type; its brief forbids reading this repository | `.tmp/readiness/b/claude-side.md` |
| Empirical | Retained real-model runs under `.scratch/` (`c10-live-*`, `haiku-recovery-live-*`, `haiku-stress-live-*`, `opus-live-*`, `sanity-live-*`, `guidance-live-*`, `vocabulary-live-*`, `haiku-authoring-live-01`, `fable-problem-b-live-01`, `claude-code-probe-01`, `claude-code-probe-02`, and any other run `apparatus/qualified.md` records as a live placement), with the results under `apparatus/studies/` | `.tmp/readiness/b/empirical.md` |

A Stewart-side ledger row has: the trigger; the route; the contract clause that
decides it, or "undecided"; what the auditor is told; what the manager sees in
`run`, `status` and the run records, in the exact words; and whether those
words name Stewart as the actor. Rows cover strict decoding of tool input,
bounds on entries and pages, citation matching, the reminder and ending rules,
output and turn caps, retry policy, startup and event validation, and
accounting that turns an ordinary event into "unknown".

The Claude-side agent covers: stop reasons and content block types; thinking
and output caps by effort; the shapes of tool input; several tool calls in one
response; compaction; `stream-json` event types and their optional members;
retries and rate-limit events; how model names are reported; limits on MCP tool
result size and duration; hook timeouts; turn caps; synthetic assistant
messages. It marks each item `documented` (with source and date), `documented
as unspecified` or `not found`. Only `documented` items count as normal. If
that agent type or its network access is unavailable, the Claude side is
reported as not obtained; model memory is not substituted.

The empirical agent lists every refusal, cap or stop a real model met, with the
run that shows it. `.scratch/` is not tracked: in a checkout without those runs
it reports that it had no evidence and substitutes nothing.

The orchestrator crosses the three sources (the two Stewart-side ledgers, the
Claude-side list, the empirical list) into `.tmp/readiness/b/crossed.md`. A row
is a candidate finding when its trigger is `documented` normal or appears in a
real run, and any of these holds: no contract clause decides it; the two routes
treat the same condition differently; the manager-facing words do not attribute
the stop to Stewart. Each candidate goes to a fresh agent, on the session
model, given the row and its cited texts and told to refute it. Decided
restrictions that meet none of the three conditions are listed once, briefly,
as accepted. Report the inverse where it turns up: a real `claude` or provider
failure that Stewart presents as its own.

- [ ] Dispatch the four agents.
- [ ] Cross the sources; refute each candidate.
- [ ] List what only a live run could settle.

## C: question documentation

Specification scope: CONTRACTS from "Mission" through "Shared terms" and from
"Question families and open inquiry" through "The return and its delivery";
all of `docs/QUESTION-FORMS.md`; INTERFACE 3.2 and section 7; in
`docs/claude-code/CONTRACT.md`, "Development input and preparation schema",
"Help, run requirements and presentation" and "Runtime texts"; ACCEPTANCE C7;
and `examples/questions/`.

- [ ] **Render the help.** The forms help is assembled when the binary runs.
  The orchestrator captures `stewart help` and `stewart help forms` from a
  binary built from the current source into `.tmp/readiness/c/help.txt`
  (`cargo build --locked --offline --release` in `service/` if none is
  current). This launches nothing.
- [ ] **Cold implementer, twice.** Two agents, independently, receive
  `DESIGN.md`, `CONTRACTS.md`, `ACCEPTANCE.md`, `docs/INTERFACE.md`,
  `docs/QUESTION-FORMS.md`, `docs/claude-code/CONTRACT.md` and
  `examples/questions/`, and nothing from `service/`, `apparatus/`, the
  rendered help or any plan. Their task is the family-registry and
  role-declaration items of the
  [specification stage](development/MANAGER-INTERFACE-PLAN.md#1-specify-the-shared-commissioning-and-documentary-contracts),
  which the orchestrator copies into both briefs word for word at dispatch,
  for the three implemented families. Every cell of the registry cites the
  passage it came from or is marked as a guess. They write
  `.tmp/readiness/c/registry-1.md` and `registry-2.md`. The guesses, and every
  cell where the two disagree, measure what the documentation leaves
  unspecified.
- [ ] **Editor pass.** One agent reads the specification scope and the rendered
  help, passage by passage, and classifies each problem: contradiction; one
  fact with two owners; a named concept with no mechanism; one thing with
  several names; narration of how a decision was reached where current behavior
  belongs; a summary restating its neighbor; instruction addressed to
  developers in text a manager reads; outside the mission; help and
  specification saying different things. Each gets a proposed edit (delete,
  merge into its owner, keep) and the agent edits nothing. It writes
  `.tmp/readiness/c/editor.md`.
- [ ] **Manager's side.** One agent receives only the rendered help and
  `examples/questions/`, reads as a manager choosing a family would, and
  reports what it could not work out, in `.tmp/readiness/c/manager.md`.
- [ ] Reconcile the four results. Each candidate contradiction goes to a fresh
  agent, on the session model, given the two passages and told to refute it.
  In the delivered list, a proposed edit to the documentation appears under the
  disposition of the problem it answers.

## Leads from reconnaissance

Noticed while planning. "Read" means the planning session read the cited text;
"checked" means an agent checking this plan reported it and the planning
session did not re-read it; "hypothesis" means nothing has tested it.

**A**

- Read: the tests in `service/src/claude_code/events.rs` build the startup
  event by hand, with an invented model name and the pinned version string, and
  change one member at a time. Their usage fixture gives every token count the
  same number.
- Read: harness event names (`compact_boundary`, `rate_limit_event`,
  `api_retry`) occur in tracked files only in the adapter, the runtime
  documents, and the probe and driver apparatus. No captured harness stream is
  a tracked fixture. Checked: the two retained probes hold a startup event and
  `rate_limit_event`s; no real `compact_boundary` or `api_retry` is retained.
- Hypothesis, from test names only: no test in `service/tests/claude_code.rs`
  drives a placement end to end.
- Read: four driver modules refer to `mini_stewart.py`, which
  `apparatus/README.md` describes as a stand-in used only by self-tests. What
  those self-tests establish about the checks is unexamined.
- Read: DEVELOPMENT states that no check reads the worked example submissions.

**B**

- Read: the Claude Code route sets harness retries to 0 and stops a placement
  on an `api_retry` event; the Messages route attempts a request up to four
  times.
- Read: in `events.rs`, a harness line that is not JSON, or an interpreted
  event lacking an expected member (for example a `rate_limit_event` without
  `rate_limit_info`), is an error. How that error reaches the manager is
  untraced.
- Read: an assistant message's model must equal the profile's model string or
  `<synthetic>`.
- Read: a rate-limit event reporting paid extra usage enabled, even when not in
  use, is a stop.
- Read: both routes request at most 16,000 output tokens per response. On the
  Messages route a `max_tokens` response with no tool call ends the placement
  interrupted. Checked: the runtime adapter has no corresponding handling.
  Hypothesis: at high effort, thinking alone can reach the cap.
- Read: `read` returns pages up to 64 KiB, and no tracked file mentions a
  harness limit on tool result size. Hypothesis: the harness has one that such
  a page can exceed.
- Read: after the single reminder, a second ordinary turn ending without
  submission ends authoring for good. This is decided; its presentation to the
  manager is the open point.

**C**

- Read: INTERFACE and QUESTION-FORMS never mention material roles. CONTRACTS
  mentions them twice in passing and ACCEPTANCE C7 once.
- Read: CONTRACTS decides, pending implementation, that the commissioned
  question is returned with the answer, and says its later text describes
  current behavior. "The return and its delivery", "Readable answer rendering"
  and the rendering rules in QUESTION-FORMS state the current behavior without
  pointing to that decision. The open point is whether an implementer can tell
  which is current from each passage alone.
- Read: "family" and "form" are declared synonyms in CONTRACTS; the help topic
  is `forms`, the front matter key is `family`, and manager-interface work
  speaks of "types".
- Read: CONTRACTS gives about sixty lines to the five-purpose library, about
  twenty of them to two unimplemented families, and names `answer`,
  `needs-evidence` and `reframe` and optional evidence modules without a
  mechanism for any of them.
- Read: the reminder text appears in both CONTRACTS and QUESTION-FORMS.
- Read: the front matter grammar already differs by runtime (`limit-*` fields
  against placement fields), which any role declaration must fit.

## Run record

Record here as they come to exist: the workflow run identifier and script path
for A; which batches have a review file and which were re-run; the agents
dispatched for B and C; and anything not written where this plan says. After
an interruption, read this section and list `.tmp/readiness/` before
dispatching anything. A batch or agent has returned when its file exists and
is complete; a missing file does not show that its agent stopped. A workflow
run can be resumed by its identifier only from the session that launched it;
another session re-dispatches only the batches without a file, after
confirming with the principal that the earlier run is no longer active.

Nothing has run.

## Completion

Deliver the ranked list with proposed dispositions and the counts behind it:
units classified, findings raised, refuted and unsettled, and questions left
for a live run. Mark each item that quotes implementation lines. Report a batch
or agent that did not return as not reviewed.

The principal decides what blocks entry and what follows; fixes are separate
work under their own authority. After the principal has given every item its
disposition, and anything the principal wants kept has been recorded where the
principal directs, remove `.tmp/readiness/` and delete this plan with its row
in the release plan's work order.
