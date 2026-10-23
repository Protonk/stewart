# CLI reduction: custody-focused status before collection

Status: pending investigation. No runtime, CLI, API or schema change is
implemented by this plan. Work belongs on `cli-reduction`; inspect the actual
branch and working tree before starting and preserve unrelated changes.

## Assignment and review boundary

Investigate how to make pre-collection status inspect recorded custody instead
of repeatedly inspecting the live execution environment. Prepare a concrete
implementation proposal for review. The first dispatch under this plan is an
investigation and preparation task: produce findings, proposed contracts,
examples, dependency analysis and a validation plan. Do not change production
behavior, remove supported interfaces or migrate the parser during that task.
Implementation is a subsequent task after the user reviews the findings.

Pursue this direction even if it does not immediately reduce internal
complexity. Stewart still needs enough information to supply informative errors
and to enforce collection and cleanup requirements. Do not count moving checks
out of a public getter as deleting their underlying responsibility.

The broader goal is a smaller manager-facing command, flag and argument surface,
with less implied work between issuing an assignment and collecting its result.
A smaller surface should also make an eventual Click migration easier. Preserve
the manager's question/answer interface, useful inspection and recoverability.
The present task does not authorize that migration.

## Context and scope

An agent manager can interpret status output as a work queue. Today a normal
prepared audit without a collection can return exit 0 while listing "no complete
collection exists" as outstanding, offering a conditional handoff, printing a
probe and launch recipe, and suggesting collection after the auditor stops.
Stewart observes no auditor activity. These outputs are established behavior;
their effect on agent behavior is a hypothesis, not a measured result.

Explore a public view that says what preparation and custody records establish,
what has been collected, and which recorded problems need attention. Successful
preparation in the past must not be presented as a fresh certification of the
checkout, supplied runtime or harness. The absence of a collection alone is
ordinary during this interval. A quieter view must not imply that an auditor
started, remains active, has stopped or has completed the question.

Focus the proposed product change on pre-collection status inspection, the
interval deliverable 1 defines from records. Give each public field one meaning
and provenance wherever it applies. The custody stage and recorded problems
describe what records establish; they do not combine past preparation with
current observations of the checkout, supplied runtime, handoff or manager
checkout. Identify any live comparison that status keeps as a read-time
observation, including one that compares current bytes with a recorded
baseline. Removing a live check from status removes it at every stage where it
now applies. A check that needs a fact only collection or triage establishes,
such as the checkout being unchanged since collection, applies from that point
without changing its field's provenance.

The intended behavioral change is to pre-collection recommendations and
attention items. Trace each affected field and check through every stage,
including workspace listings, exit codes, offered actions and the operations
that call status. Change post-collection output only where consistent field
provenance or a check moved to operation time requires it, and identify and
justify each such change. Required custody and cleanup checks survive as
validations their operations own, independent of status, including those
`close` now enforces through status-derived attention.

Other pending design plans are outside this investigation and do not constrain
the proposed contract. Record any executable-test coupling to them, such as a
citation check, as an integration item for implementation review.

## Read first and trace the current implementation

Read [AGENTS.md](AGENTS.md), [DEVELOPMENT.md](DEVELOPMENT.md), the
[installed manual](src/stewart/resources/README.md), and
[maintainer guidance](src/stewart/resources/MAINTAINER.md).

These are starting points, not a complete dependency inventory. Reconfirm
symbols and behavior against the checkout you investigate:

| Source | Trace |
| --- | --- |
| [status.py](src/stewart/status.py) | `status`, `_attention`, `_derive_actions`, `_identity_and_holdings`, `status_list`, record/capture readers, stage derivation and live observations. |
| [cli.py](src/stewart/cli.py) | `build_parser`, status dispatch and `_render_status`; prose and JSON, profile overrides and generated commands. |
| [close.py](src/stewart/close.py) | `_status_view`, `_preflight`, `_concluded`, `close_plan`, independent checkout observations and removal revalidation. Close currently uses status and its integrity diagnostics. |
| [collect.py](src/stewart/collect.py) | `_collect`, raw capture before validation, handoff/runtime observations, checkout identity and custody-gap reporting. |
| [audits.py](src/stewart/audits.py) | Discovery, session loading, references and lifetime selection; determine which of them depend on status. |
| [holdings.py](src/stewart/holdings.py) | Resource closeout reached through status; inventory any indirect live filesystem/Git inspection. |
| [session.py](src/stewart/session.py), [captured.py](src/stewart/captured.py) | Session validation, receipt identity, retained evidence and verified capture associations. |
| [runtime.py](src/stewart/runtime.py), [implementation.py](src/stewart/implementation.py) | Runtime observations/recovery and writer identity/handoff; distinguish the auditor's supplied runtime from the manager implementation. |
| [launch_profile.py](src/stewart/launch_profile.py), [coordination.py](src/stewart/coordination.py) | Pinned intent, rendered recipes, overrides, exit observations and attributed manager acknowledgments. |
| [api.py](src/stewart/api.py) | Callable contracts that remain supported even if a CLI route is reduced. |

## Investigation deliverables

### 1. Define the interval and its exceptions

Specify a mechanical boundary using records. Compare "no collection attempt"
with "no complete collection" rather than treating them as equivalent. Account
for failed/interrupted preparation, partial collection, invalid or unreadable
receipts, recorded harness failure, missing session records, abandoned or
partially closed audits, and any supported unusual operation ordering. Do not
classify all of these as ordinary waiting.

State whether a manager launch acknowledgment affects the view and why. It must
not become evidence of process activity. Explain how a collection attempt or
completed capture changes the view without a live report scan. Include workspace
listings and discovery in the scope analysis so another common getter does not
silently reintroduce the same monitoring behavior.

### 2. Inventory observations, consumers and diagnostics

Produce a matrix with one row per relevant observation or derived fact:

- source bytes or operation, and whether it reads recorded evidence or live state;
- direct and indirect callers, including subprocess/Git/filesystem work;
- public fields, stage, exit-code and action recommendations it affects;
- which collection, release, recovery or cleanup precondition relies on it;
- proposed timing and owner of the check, plus the diagnostic if it fails;
- tests that protect the public promise versus the underlying custody rule.

Explicitly include checkout existence, Git administration/HEAD/lock, maintainer
state, public and private handoffs, runtime history and current bytes, commit
retention, resource closeout, implementation identity, and collection/receipt
verification. An immutable-looking receipt still needs safe reads and validation.
"Recorded custody" is not permission to trust unchecked JSON or cached claims.

For each live check removed from normal inspection, name the operation that
takes it over, when a problem will next be detected and what information the
manager receives then. Distinguish deferred detection from loss of detection: a
removed check with no later detection point is a requirement change to present
for review. Preserve useful stable reasons,
retained paths and next steps; a generic failure is not an adequate substitute.

### 3. Propose the smallest public contract

Give concrete before/after prose and JSON examples for ordinary pre-collection
status, a recorded failure and the transition to collection. Specify the meaning
and provenance of every retained or changed field, exit code and action.
Separate recorded preparation success from unobserved current readiness.

Specify which pre-collection action recommendations are justified by recorded
custody and how the others should be treated in both prose and JSON. Preserve a
way to recover the issued handoff/reference without turning inspection into a
renewed invitation to launch.

Where status stops checking a live condition that gates an offer, at any stage,
state what the offer then means: an operation worth attempting, subject to its
own validation, not a sign that status established it will succeed.

Keep the proposed surface small. If an additional public entry point proves
necessary, justify its net surface cost and why existing operation errors cannot
supply the information.

The proposed first implementation may remove a CLI flag or API parameter when
the removal follows directly from the custody-focused status contract; recommend
none that the contract does not require. Explain each removal's lost capability,
affected callers and test consequences.

Identify the impact on schemas, API callers, CLI help, generated actions,
workspace listings, closing records and documentation. A record-derived custody
stage changes the meaning of the stage `close` records as observed; propose how
new closing records make that explicit. State the treatment of existing records
and writer-bound sessions. Do not rewrite historical receipts, introduce
compatibility shims or automatically execute an implementation handoff.

### 4. Prepare the internal change and test accounting

Recommend a concrete separation, if needed, between public custody summaries
and operation-time observation/validation. Trace how close will retain all of
its required checks after that separation, and do the same for retain, release
and other affected operations. A concluded close now refuses on every exit-3
attention item in status, including live runtime and handoff observations;
determine which of those conditions closure requires. Keep each required one as
a validation close owns, and do not turn an incidental refusal into a new close
requirement. Prefer shared validators with clear callers over duplicated rules
or a public status function with hidden mode switches. Do not prescribe a new
architecture merely to make the getter look small.

Provide an ordered implementation outline naming affected functions/modules,
the smallest coherent first change, migration of internal callers and the
documentation work. Classify proposed test changes as:

- deleted because the supported behavior itself is retired;
- updated because the public contract changes;
- moved or retained because the underlying validation still exists;
- added to prove the new boundary and prevent loss of diagnostics.

Separate CLI parser/dispatch savings from semantic test savings and code merely
moved elsewhere. Count argument definitions separately from distinct flag names.
Leaving an API callable supported retains its behavioral obligation. Existing
record readers and cleanup constraints retain their tests too. Zero immediate
internal simplification is an acceptable finding; do not manufacture a savings
claim or delete a safety test to achieve one.

## Evidence and validation requirements

Start with a bounded source investigation. Run focused comparisons only where
needed to resolve uncertainty; do not run the full suite simply to write a plan.

The investigation may add and commit focused tests under `tests/`, including
instrumentation and firing controls needed to resolve its questions. Production
behavior stays unchanged. Run these tests through the installed-wheel workflow
below and keep the source of every test whose run the findings cite.
Distinguish baseline observations from enduring invariants and explain which
tests the proposed implementation would update, retain or remove. Do not commit
failing expectations for unimplemented behavior or weaken existing tests to
accommodate the proposal.

Any executed project tests use the installed-wheel workflow in
[DEVELOPMENT.md](DEVELOPMENT.md), an explicit Python 3.14 interpreter with `-I -B`,
and the locked wheelhouse. Use fresh result names under `.scratch/cli-reduction/`,
preserve command output and report actual collected, selected, deselected,
passed, failed and skipped counts. Follow that document's retention policy;
only `scripts/prune.py` removes a retained run's artifacts directory.

The proposed implementation validation must include a firing control, a changed
case and an invariance case. Cover at least these obligations, with exact
selectors to be chosen after tracing the dependencies:

- A real corruption or failed/partial receipt remains visible with an informative
  diagnostic; no damaged state is relabeled as a healthy wait.
- A live-only change outside the promised custody view does not cause normal
  pre-collection inspection to probe or advertise activity. Instrument relevant
  reads/subprocesses where necessary: equal output alone does not prove that a
  scan stopped occurring. At the operation that still requires that check, the
  same condition is detected with its required consequence and useful error.
- An unchanged audit, unrelated repository advancement, and repeated reads
  preserve the intended invariants and write no session evidence.
- Failed preparation, partial collection and invalid records remain distinct;
  collection still preserves raw evidence, and cleanup still refuses or retains
  resources under the existing custody rules.
- Reference/lifetime binding, post-collection evidence interpretation, and
  affected listing/closed views retain their promised behavior.

Relevant existing suites include
[test_stewart_status.py](tests/test_stewart_status.py),
[test_exit_codes.py](tests/test_exit_codes.py),
[test_close.py](tests/test_close.py),
[test_close_regressions.py](tests/test_close_regressions.py),
[test_discovery.py](tests/test_discovery.py),
[test_stewart_launch_profile.py](tests/test_stewart_launch_profile.py),
[test_stewart_coordination.py](tests/test_stewart_coordination.py), and
[test_resources.py](tests/test_resources.py). This is a reading map, not a mandate
to run all of them during investigation. Identify additional runtime, capture
and collection tests through the actual call graph. Do not infer real harness
enforcement or improved manager behavior from unit tests.

## Handoff for review

Write `CLI-REDUCTION-FINDINGS.md` with the source-backed dependency matrix,
recommended public contract and examples, implementation outline, diagnostic
preservation analysis, test accounting, evidence references and unresolved
decisions. Make it self-contained for a reviewer.
Record investigation progress and evidence pointers in this plan; clearly
separate observed facts, proposals and hypotheses. If there are competing
designs, explain their concrete costs and recommend the smallest viable one.

Return the findings for user review before implementation. The approved
implementation continues under this plan, and the findings serve only that
review and implementation. Its end state needs neither file: shipped
documentation, code and tests carry the contracts and stand without the plan,
the findings or their runs. Once they do, prune the cited `.scratch/cli-reduction/`
runs under [DEVELOPMENT.md](DEVELOPMENT.md)'s retention policy, then remove this
plan, `CLI-REDUCTION-FINDINGS.md` and those run records together.
