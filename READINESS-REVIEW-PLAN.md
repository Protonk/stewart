# Readiness review before manager-interface work

This plan owns a read-only review that challenges the release plan's entry
assessment for manager-interface work. It does not critique or revise the
manager-interface plan. It looks for three kinds of trouble that could swamp
that work once it begins and reports them to the principal, who decides what
each one means for entry.

**State: every dispatched agent has returned and the ranked list has been
delivered to the principal in chat. What remains is the principal's
disposition of each item, then [completion](#completion).** The orchestrator
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
- **At most eight agents at once, as a hard limit; four to six in practice.**
  Reviewers and refuters share that pool. A goes first; B and C follow and may
  run together.
- **B and C are dispatched by hand** with the Agent tool. Their briefs differ on
  purpose, and what B's crossing needs depends on what comes back.
- **Results come back in chat** as one list, ranked by how directly an item
  would mislead or stall the specification work. Each item carries the
  orchestrator's proposed disposition: blocks entry, input to the specification
  work, or accept. The principal decides. No findings document is tracked
  unless the principal asks.

The principal authorized dispatch after this plan was committed. A session that
did not receive these choices from the principal directly confirms them, and
that the Workflow tool is enabled, before dispatching anything further. The review has no cap on findings; the orchestrator
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
  raise no finding against a driver file. Such a note goes only to the
  orchestrator's merged list, never to a driver-batch reviewer or refuter. The
  session that wrote this plan has read `service/src` and edits no driver.

## A: tests that test their own input

### Rubric

One record per unit. A unit is a `#[test]` function; a driver case; a `def
test_` function that a test runner collects; a function registered with
`selftest`, by decorator or by call; a whole monolithic `self_test()`, whose
named checks the reviewer lists as sub-rows (one sub-row for a loop that
generates names); or a stand-in or fake named as a subject. The orchestrator
lists each batch's expected units by name in the brief, from the commands in
the first task below. A batch has returned when its file exists and names every
expected unit.

Properties are recorded for the assertions that carry the claim the unit's name
makes. The values of each property are exclusive.

| Property | Values |
| --- | --- |
| Oracle | Where the expected value comes from. `specification`: read from the specification text when the test runs. `witness`: bytes the test itself supplied, or a value computed from them by code separate from the path under test. `cited-literal`: a hand copy of a value the specification gives, or a value a cited passage's rule determines; cite the passage. `literal`: written by hand, with no such passage. `self`: derived from the output being checked or regenerated by the same code path, including a stored expected file whose origin is not recorded (recorded means a commit message or note says how the file was produced). Record the weakest, and how many of the assertions carry it. A comparison between two outputs of the code under test (a repeat against the first, two runs, sent against pinned) is a control, not an oracle. |
| Fixture | What plays the other party; with several parties, record the value latest in this order: `none`, `real`, `specified`, `stand-in`, `synthetic`. `real`: bytes with a recorded capture source. `specified`: input that Stewart's own specification defines (a manager's files, a tool input), with its shape and every value the behavior depends on given by a cited passage. `synthetic`: built by hand otherwise, which includes the output of an external party (provider, harness, operating system) written from the specification's description of it and not from a capture. `stand-in`: supplied by a stand-in or fake that is another batch's subject; name its file. `none`: no other party. Service-side reviewers add `mirrors-code` when a synthetic fixture repeats literals the code under test hard-codes; driver-side reviewers add `narrower-than-specification` when it exercises less than the cited passage allows. |
| Controls | For the property the unit names, which exist: a sabotage control (ACCEPTANCE's [first rule](ACCEPTANCE.md#rules-every-check-follows): a broken implementation, or an input to the check itself, on which the check must fail), a differing case (which includes a malformed input the code is expected to refuse), an invariance case (which includes a repeat of the same input). A control in another unit or file counts when it breaks the property this unit names, wholly or in part; cite it and say which part. For a driver case, a control exists when it is in the case's source, in its declaration or its body; whether it fired belongs to run records. |
| Vacuity | Any of: `any-error` (the assertion accepts any error although the code or specification distinguishes the failure claimed, so a failure for the wrong reason would pass); `indistinct` (the claim depends on telling fields or cases apart and the fixture gives them one value); `skip-as-pass` (an early return or skip, disclosed or not, leaves the unit tallied as passed; name the line); `not-run` (ignored or compiled out, and no command in DEVELOPMENT's check table runs it; a feature-gated unit that such a command runs is not flagged, and the command is recorded). |
| Unreached conditions | Specified failure conditions for the behavior that the batch does not reach, each keyed by its specification clause. These are candidates only. |

Service-side reviewers (batches 1 to 15 and 28 to 32) read whatever their tests
call, including sibling fault and sabotage files for controls, and list the
files they opened. Driver-side reviewers read other driver modules as their
cases require and classify only their own batch's units.

### Finding rule

A finding is raised when any of these holds; its class is the name in
parentheses.

- A unit's oracle is `self` (`self-oracle`).
- A unit has a vacuity flag (`vacuous`).
- A unit in a batch that a [reliance row](#what-later-work-leans-on) lists has
  a `synthetic` fixture in which its own hand-built bytes play an external
  party (`unanchored-fixture`). Raise this once per fixture or helper, listing
  the units that depend on it. A unit whose fixture is `stand-in` raises
  nothing here; the stand-in's own record carries the question.
- A unit in a batch that a reliance row lists has no control of any kind for
  the property it names (`no-control`).
- A stand-in or fake has no stated source, outside its author, for its model
  of the real counterpart (`stand-in-provenance`).

A `literal` or `cited-literal` oracle alone is tallied, not raised.

Unreached-condition candidates are merged by clause across batches. Each
distinct clause goes to one refuter that may read every test tree and is told
to find a unit reaching it; a clause for which it finds none is a finding
(`unreached-condition`). That refuter reads the service, so its result is
implementation-side whatever batch proposed the clause.

A finding record has: an identifier (`A<batch>-<n>`), batch, file, unit or
units, line, the property values, class, a one-sentence claim, the evidence,
its side (`specification-terms` or `implementation`), every reliance row that
lists its batch, and one line on what a principled fixture would be.

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
`specification`, `witness` or `cited-literal`, it has no vacuity flag, and no
finding against it stands or is unsettled. A row whose batches hold no trusted
unit is a finding. Its refuter is given the row and those batches'
classification tables and told to name a trusted unit.

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
| 19 | `apparatus/driver/cases_run.py`; `run_support.py` with its two self-tests (its `test_key` is a helper, not a unit) | The cited claims |
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

- [x] Confirm the batch list covers every tracked file with tests, and list
  each batch's expected units by name. The first two commands print the Rust
  tests and the Python tests, cases and self-test registrations; the two
  `--list` commands print the drivers' cases and run no binary.

  ```sh
  git ls-files 'service/*.rs' 'apparatus/*.rs' | xargs grep -n -A2 '#\[test\]' | grep 'fn '
  git ls-files 'apparatus/*.py' | xargs grep -nE '^[[:space:]]*def test_|^@case|^@selftest|^[[:space:]]*_?selftest\(|^def (run_)?self_test'
  python3 -I -B apparatus/driver/stewart_driver.py --list
  python3 -I -B apparatus/driver/claude_code.py --list
  ```

- [x] Write the workflow script and run it: review, then refute, eight agents
  at a time. Record its run identifier and script path in the run record as
  soon as it is launched.
- [x] Merge unreached-condition candidates by clause and send each to its
  refuter.
- [x] Collect survivors per reliance row and apply the trusted-unit test.

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

- [x] Dispatch the four agents.
- [x] Cross the sources; refute each candidate.
- [x] List what only a live run could settle.

## C: question documentation

Specification scope: CONTRACTS from "Mission" through "Shared terms" and from
"Question families and open inquiry" through "The return and its delivery";
all of `docs/QUESTION-FORMS.md`; INTERFACE 3.2 and section 7; in
`docs/claude-code/CONTRACT.md`, "Development input and preparation schema",
"Help, run requirements and presentation" and "Runtime texts"; ACCEPTANCE C7;
and `examples/questions/`.

- [x] **Render the help.** The forms help is assembled when the binary runs.
  From `service/`, the orchestrator builds both configurations from the
  current source and captures two files. `.tmp/readiness/c/help.txt` holds
  `stewart help` and `stewart help forms` from the release binary
  (`cargo build --locked --offline --release`). `help-runtime.txt` holds
  `stewart help` and `stewart help runtime` from the development binary
  (`CARGO_TARGET_DIR=target-local cargo build --locked --offline --features claude-code`).
  This launches nothing. The editor receives both files; the manager's-side
  agent receives `help.txt` only.
- [x] **Cold implementer, twice.** Two agents, independently, receive
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
- [x] **Editor pass.** One agent reads the specification scope and the rendered
  help, passage by passage, and classifies each problem: contradiction; one
  fact with two owners; a named concept with no mechanism; one thing with
  several names; narration of how a decision was reached where current behavior
  belongs; a summary restating its neighbor; instruction addressed to
  developers in text a manager reads; outside the mission; help and
  specification saying different things. Each gets a proposed edit (delete,
  merge into its owner, keep) and the agent edits nothing. It writes
  `.tmp/readiness/c/editor.md`.
- [x] **Manager's side.** One agent receives only `help.txt` and
  `examples/questions/`, reads as a manager choosing a family would, and
  reports what it could not work out, in `.tmp/readiness/c/manager.md`.
- [x] Reconcile the four results. Each candidate contradiction goes to a fresh
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

**A, expected units.** `.tmp/readiness/a/expected.json` and one
`batch-NN.expected.json` per batch: 786 units, of which 389 Rust tests and 150
driver cases (126 release, 24 runtime), matching the commands above.

**A, review and refutation.** Launched as workflow run `wf_d19e9fa6-d66`, six
agents at a time: one Opus 5.5 reviewer per batch at high effort, then one
refuter per finding on the session model. Its script is
`readiness-a-test-review-wf_d19e9fa6-d66.js` under the launching session's
`workflows/scripts/` directory in the harness's project folder for this
checkout; the script holds the reviewer and refuter briefs. Reviewers return
at most twelve unreached-condition candidates each. All 32 batches returned and
no batch was re-run: each `batch-NN.review.json` names every expected unit
(786 of 786). The run raised 189 findings, each with a `<finding-id>.refute.json`:
137 stand, 49 were refuted and 3 are unsettled on the driver side.
`.tmp/readiness/a/merged.json` holds the tables, findings and verdicts;
`.tmp/readiness/tools/merge_a.py` rebuilds it from the batch files.

**A, unreached conditions.** The reviewers proposed 379 candidates citing 375
different passages, so merging by quoted clause merged almost nothing. They
are instead grouped by specification section into 58 sets of at most eight
(`.tmp/readiness/a/unreached-GNN.candidates.json`, identifiers `U001` to
`U379`, built by `.tmp/readiness/tools/group_unreached.py`), one refuter per
set on the session model. Launched as workflow run `wf_e15d37fd-f69`, four
agents at a time; script `readiness-a-unreached-conditions-wf_e15d37fd-f69.js`
in the same directory as the first. Each refuter writes
`unreached-GNN.result.json` with a verdict per candidate: `reached` (unit,
file, line and tree named), `partly`, `unreached` or `not-specified`. All 58
sets returned with every candidate accounted for: 154 reached, 91 partly
reached, 114 unreached and 20 not specified.
`.tmp/readiness/a/unreached-merged.json` holds them, rebuilt by
`.tmp/readiness/tools/merge_unreached.py`. Every reliance row has trusted
units (`.tmp/readiness/tools/trusted.py`), so no row-level finding was raised.

**B.** Both Stewart-side ledgers have returned: `stewart-messages.md` (74
rows, `M-01` to `M-74`) and `stewart-claude-code.md` (83 rows, `CC-01` to
`CC-83`). Both briefs gave the same twelve category keys (`K1` to `K12`) so
the ledgers can be crossed. `claude-side.md` (public documentation fetched 2026-11-12; several pages were
only partly obtained and are listed at its end) and `empirical.md` (75 events
from 53 retained run directories) have also returned. The Claude-side agent
wrote its own result file and read nothing else locally. `crossed.md` holds
twelve candidates, `X1` to `X12`, and the list accepted without refutation.
Each candidate went to one refuter under `REFUTER-BRIEF.md`, which wrote
`Xn.refute.md`: `X8` stands as written, the other eleven stand in part, and
none was refuted outright. The refuters' corrected statements, not the
wording in `crossed.md`, are what was delivered.

**C.** `help.txt` and `help-runtime.txt` are captured from the two builds.
`registry-1.md`, `registry-2.md`, `editor.md` (156 items) and `manager.md`
have returned. The manager's-side agent had `stewart help` and `help forms`
only, as specified above; some of what it could not work out is answered by
`help commands`, `help limits` and `help reader`, which the orchestrator read
afterwards. `contradictions.md` lists ten candidates, `K1` to `K10`: the
editor's six and four the cold implementers raised. Each went to one refuter
under `.tmp/readiness/c/REFUTER-BRIEF.md`, which wrote `Kn.refute.md`: `K1`
stands, `K4`, `K7` and `K8` are reconcilable only from a passage the others do
not point to, and the other six were refuted.

## Completion

Deliver the ranked list with proposed dispositions and the counts behind it:
units classified, findings raised, refuted and unsettled, and questions left
for a live run. Mark each item that quotes implementation lines. Report a batch
or agent that did not return as not reviewed. Name the driver-side result files
(batches 16 to 27 and their refutations) that hold standing or unsettled
findings, and ask the principal whether to keep them for a driver author: they
are the only form of those findings that may be handed on.

The principal decides what blocks entry and what follows; fixes are separate
work under their own authority. After the principal has given every item its
disposition, and anything the principal wants kept has been recorded where the
principal directs, remove `.tmp/readiness/` and delete this plan with its row
in the release plan's work order.
