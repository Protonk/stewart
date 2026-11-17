# Stewart release work lookback audit guide

This guide prepares a fresh developer to audit the release-work session through
2026-11-16, ending with the OS fixture batch at `5e3a2ad`. It covers what changed,
what the evidence establishes, and two opportunities: make Messages and a
persistent agent easier to develop and test through a shared internal core;
and make question families better owners of materials presentation and evidence
expectations. The architecture candidates below are questions to resolve, not
new public contracts or an instruction to build every proposed abstraction.
The lookback has been performed; its decisions, landed changes and remaining
candidates are under [Findings and dispositions](#findings-and-dispositions).

The central finding is that Stewart already shares authoring and custody across
runtimes. The next useful audit concerns the representations and boundaries
around that core. Similarly, families already select guidance, tools and answer
sections; materials presentation and evidence policy have fewer explicit seams.
Refactoring should make those differences deliberate while preserving exact
custody, expressive latitude and the limits of each observer's evidence.

## Start with the obligations and choose an audit role

Read [AGENTS](../AGENTS.md), [DESIGN](../DESIGN.md),
[CONTRACTS](../CONTRACTS.md), [INTERFACE](../docs/INTERFACE.md),
[QUESTION-FORMS](../docs/QUESTION-FORMS.md) and [ACCEPTANCE](../ACCEPTANCE.md).
[README status](../README.md#status) distinguishes implementation from demonstrated
behavior. Discover current assignments with `git ls-files '*-PLAN.md'`; the
coordinating plan alone owns their order. This guide is a bounded lookback,
not another source of assignments.

Choose the implementation or independent-driver side **before reading code**.
An author who reads `service/src` or `service/tests` cannot edit
`apparatus/driver` in that session. The source links below are for the
implementation reviewer. The driver reviewer works from specifications,
independent originals and observed binary behavior. Shared production logic
must never become the independent acceptance oracle.

Inspect the working tree and retained run state before making changes. No live
Claude, authentication, model or spending authority carries over from a consumed
packet. The session's subscription commissions required extra usage disabled.
A fresh packet needs its own bounded authority. A persistent agent here means a
process/session that persists **within one placement**; continuation deliberately
uses a fresh session with the same audit ledger. Native resume, fork and automatic
restart are not implied by a shared-core refactor.

## What the session established

The session developed a default-off source-build runtime, strengthened the
independent apparatus, performed bounded Messages and native harness encounters,
repaired observed behavior, and grounded synthetic controls in retained captures.
The manager preparation interface remains a design and implementation task.
Its selected direction is ordinary files and an independent CLI, with optional
MCP assistance, shared production commissioning rules and the accepted question
in the return. The current implementation does not yet provide that preparation
MCP, role registry, effect-inspection operation or returned-question member.

The development runtime uses the same Rust authoring/custody core through MCP.
Work included executable/profile binding, bounded starts and stopping, independent
peer/package witnesses, relay behavior, usage observations and admission controls.
Early probe clock problems and Linux relay/observation failures were investigated;
a later workaround or passing run must not be substituted for the original
failure's scope. The [runtime reference](../docs/claude-code/RUNTIME-REFERENCE.md)
records those boundaries and the unresolved observations.

Readiness review then challenged whether tests actually reached their claimed
conditions. Repairs covered service behavior, driver controls, observation scope
and qualification accounting. Useful history anchors are `d33758d`, `0fdac94`,
`8212cf2` and `920e693`; inspect their relevant paths rather than importing old
plans as assignments. The retained Linux `acceptance-readiness-02` run qualifies
source `0fdac94`, with 133/133 ARM and 131/131 x86_64 release cases, 79/79 sabotage
and 21/21 driver controls on each architecture, plus 25/25 synthetic runtime
cases on each. Later source is not covered by that run.

### Bounded encounters and their limits

M labels identify Messages encounters; C labels identify native Claude Code
encounters. They are evidence keys, not interchangeable conformance tiers.
The [qualification index](../apparatus/qualified.md) locates their exact inputs,
approvals, writers and original records.

| Encounter | What happened | What a fresh audit must not infer |
| --- | --- | --- |
| M1 wording and inadequate evidence | Four arms submitted and closed; only the report-only direct wording produced an ordinary prose ending and reminder. Citation refusals were repaired in other arms. | Wording cannot be assumed to force the target behavior; successful submission does not exercise an unused reminder path. |
| M2 effort and response caps | Of four reviewed placements, three submitted and closed; one stopped on thinking-only `max_tokens` and supplied the retained audit for M3. | A cap stop is not a finished entry, and these few encounters do not isolate effort as its cause. |
| M3 interruption and continuation | Recorded entries and spent-reminder state survived a witnessed interruption and fresh conversation. The checklist continued twice, exhausted 64,000 cumulative output tokens, and returned its unchanged partial account through explicit manager seal and close. | The interrupted reminder attempt sent no request bytes; in-flight estimation and a spent-reminder prose ending were not exercised live. Manager sealing did not finish the checklist intellectually. |
| M4 compaction | A real signed summary crossed the configured 150,000-token trigger, was reused unchanged, and preserved an entry through revision, submission and close. Compaction-iteration usage was charged once. | One bounded Opus encounter is not the 21-audit gate for every release model. Service-owned captures are not an independent provider-wire witness; some citations were weak support for the authored claims. |
| C1 surface and C2 service | The supplied-surface comparison observed positive use, denial and invariance. Ordinary and inadequate-evidence service inquiries submitted, delivered exact packages and closed. | Surface results do not qualify a whole service; both C2 final usage intervals remained unknown. |
| C3 large pages | Exact MCP replies were replaced in conversation content by previews/file pointers for two 64 KiB pages, while a 48 KiB control remained whole. Full auxiliary copies could conceal the substitution. | Source-read completeness, valid range citations and successful custody do not establish delivery of the full text to the auditor. |
| C4 deadlines | Short and long placements submitted partial and fuller accounts respectively, both on their first placement. | Live continuation was not reached; no final usage checkpoint arrived. The longer account's eight-versus-sixteen receipt miscount remains authored content. |
| C5 cap and authoring | The harness reported a cap and recovered to submit the checklist. Two other placements exercised long replacement and direct wording. | The requested long-entry token boundary and live reminder interaction remained unexercised. All three final usage intervals remained unknown. |
| Annotated pages and C3 disposition | Annotated tools subsequently delivered all three C3 slices whole in captured conversation results. The two named external C3 copies were separately witnessed, compared and removed under explicit approval. | This does not prove universal clipping prevention, no transient copies, complete provider traffic or automatic cleanup by Stewart. |

[Interaction findings](../apparatus/studies/interaction/RESULTS.md) own the
Messages continuation/compaction readings and earlier guidance studies.
[Large-page and cap findings](../docs/claude-code/RUNTIME-REFERENCE.md#large-material-pages)
own the native observations. Preserve the distinction between attributed
intellectual readings, mechanical citation checks and exact delivery.

### Repairs and grounded comparisons

Continuation advice now respects remaining allowances (`19962b0`). The response
cap remains 16,000 tokens; observations did not establish that increasing it
would finish an account (`8e0fe0a`). MCP tools request a larger inline-result
threshold (`4132953`). The approved reply-fidelity behavior stops on a uniquely
correlated changed conversation result while retaining unknown cases and prior
effects (`3fa45d0`). Publication gating preserves close precedence and an auditor
seal that already won (`d80ab98`). Their exact boundaries belong to
[the runtime contract](../docs/claude-code/CONTRACT.md#observed-reply-fidelity).

The fixture work then replaced many invented examples with exact captured
summary blocks, cap replies, notices, tool calls, refusals, usage series,
verification outputs and complete acceptance records. Synthetic schedules and
identity projections remain explicit. Original captures supply realistic shapes;
independent expectations and firing controls establish what a test detects.
A captured model answer is opaque authored content, not an oracle for its truth.

Failures during that work are part of the audit: the reply-fidelity cases first
failed; the near-limit comparison needed a timing correction; accounting tests
had a wrong file-count assumption; a qualification-reader test used `skip` where
the result says `skipped`. Reviews also found stale preview expectations,
incorrect synthetic aggregate counts and a verifier control retaining success
stdout while returning altered output. Corrected comparisons and the original
failing outputs of the first four are located below; the last three survive
only as notes in their roots' preflight reviews. A passing retry does not erase
the first result.

The final OS batch grounded NUL-delimited environments, owned process-group
presence/absence, a denied signal-0 observation and Linux procfs controls. Its
host run passed **96 Python tests, 9 Rust protocol tests, 525 release self-checks
and 434 runtime self-checks**, with no failures or skips. Before/after bindings
and review covered 367 source files, 132 source-binding snapshot files, four verified binaries and
two retained writers. This is native offline evidence. Linux qualification of
the changed source, native WSL2 and the full real-model gate remain outstanding.

## Shared Messages and persistent agent core

### Map what is already common

The current trunk includes [archive](../service/src/archive.rs),
[filesystem custody](../service/src/fsx.rs), [log](../service/src/log.rs),
[records](../service/src/records.rs), [world](../service/src/world.rs),
[answer operations](../service/src/answer/mod.rs),
[delivery](../service/src/delivery/mod.rs) and [returns](../service/src/returns.rs).
`answer::Placement`, `Call`, `Executed`, preparation and sealing serve both
adapters. [Run operations](../service/src/ops/run.rs) share state refusal,
reconciliation and finish. Start by tracing a call to a published answer version,
then through seal, delivery and close; identify where each runtime enters and
leaves that same path.

The pressure is in the surrounding representation. `frontmatter::Settings`,
`provider::request::Pinned`, `usage::{Usage, Limits, Remaining}`,
`bodies::{RunStarted, RunEnded}` and `runs::Account` combine common concepts,
Messages-shaped fields and optional harness data. The harness path supplies
zero/empty placeholders for some API fields and uses provider placement outcome,
stop and abort machinery. These are audit leads, not demonstrated new defects.

### Evaluate internal seams before merging algorithms

| Candidate seam | Audit question and smallest useful change | Required distinction |
| --- | --- | --- |
| Commission and placement settings | Can common identity, family and custody data be separated from a tagged Messages or agent configuration, eliminating meaningless fields at internal call sites? Start with conversion at the existing boundary. | Messages token/turn allowances versus agent placement/deadline allowances. Never translate one into an invented equivalent. |
| Accounting and observations | Can typed usage evidence retain origin, session/checkpoint, scope and completeness, with mode-specific accumulation rules? | Reported, estimated and unknown usage; repeated cumulative checkpoints versus incremental charges; usage completeness versus stopping or reply fidelity. |
| Placement start and outcome | Can neutral context/outcome types live outside `provider/`, so both adapters feed common reconciliation, notices, remedies and finish? | HTTP retry and compaction attempts versus harness session events. An audit, placement, provider attempt, tool call and answer revision remain different identities. |
| Publication and stopping | Can an explicit common publication capability replace runtime-specific coupling between log publication, answer operations and the harness gate? Audit ordering before moving it. | Close, cancellation, deadline, signal and fidelity mismatch have different causes and precedence. A recorded seal cannot be undone by a later observation. |
| Conformance apparatus | Can independent scenario data and witness descriptions drive both fake transports, leaving each transport's framing and observations local? Reuse exact inputs and expected semantic effects first. | An MCP-to-Messages projection tests common semantics, not MCP framing or live harness behavior. Shared helpers must not hide two implementations' different failures. |

Treat these as internal refactor candidates. Preserve serialized records,
arrangement bytes, pinned texts and ordinary replies in the first slice. If a
public form really must change, specify the new form and refuse the old one
under the version contract; do not add compatibility readers or rewrite receipts.
Keep raw provider/harness captures alongside any normalized observations. A
single universal event or `success` flag would lose distinctions the session
needed to recover.

### Make parity falsifiable

Create a small matrix of common obligations and intentional mode differences,
with a named witness for each cell. Compare observable semantics and exact
question/material/answer bytes; account explicitly for generated identities and
times. Do not demand byte-identical transport envelopes or infer behavior from
settings alone.

1. Run the same specification-derived read, record, refusal, replacement,
   prepare, submit, delivery and close sequences through both fake transports,
   for all three current families. Include an empty answer and insufficient
   material. Expect the same selection, attribution, retained versions and
   citation behavior where the contracts are common.
2. Prove the differences: Messages remaining-output 1,023 versus 1,024 and
   turn/input exhaustion; execution of tools in the last permitted response;
   agent unknown final usage with a remaining slot and known stopping versus
   exhausted slots or unknown stopping. Appropriate continuation advice must
   follow the mode's actual allowance.
3. Follow the one-reminder and near-limit state across interruption, retries,
   compaction and fresh sessions. Keep claimed, captured, transmitted and
   unknown notice evidence distinct. Re-entry restores recorded work, not
   unrecorded thoughts; fresh equal-byte additions are not automatically replays.
4. Exercise publication races: close before the publication link, cancellation,
   signal/deadline, and a seal published before a late stop or fidelity mismatch.
   Observe retained effects and actor, not only the final exit code.
5. Compare exact, changed, missing and duplicate reply echoes live and during
   shutdown drain. Auxiliary arrays cannot substitute for conversation content;
   a crash with no final fidelity record cannot become an exact-delivery verdict.

Existing entry points include [Messages cases](../apparatus/driver/cases_run.py),
[captured citations](../apparatus/driver/cases_citation_captures.py),
[the runtime driver](../apparatus/driver/CLAUDE-CODE.md) and
[the package witness](../apparatus/driver/CLAUDE-CODE-SERVICE-WITNESS.md).
Implementation reviewers can trace [run tests](../service/tests/run.rs),
[runtime tests](../service/tests/claude_code.rs), and focused
[fidelity](../service/src/claude_code/fidelity.rs),
[accounting](../service/src/claude_code/accounting.rs) and
[gate](../service/src/gate.rs) checks. Existing tests are starting
points; each proposed extraction needs controls that would detect its own drift.

## Question families materials and evidence

### Separate the existing responsibilities

[The family contract](../CONTRACTS.md#question-families-and-open-inquiry)
already places preparation guidance, expected material roles, instructions and
answer expectations with the family. Three families are implemented; claim
examination and experimental inquiry remain dedicated-family designs, not
commissionable additions. Open inquiry needs no justification, framing permits
an undeveloped concern, and comparison need not select a winner.

[forms::Family](../service/src/forms.rs) already owns identity/version, guidance,
ordered recording tools and expected sections. Arrangement construction feeds
both runtimes, and [answer preparation](../service/src/answer/prep.rs) uses that
descriptor for counts and notices. Materials instead share a global literal
recursive UTF-8 world: [scan](../service/src/scan.rs), manifest records, `World`
and [reading](../service/src/answer/reading.rs). Citation checks in
[answer editing](../service/src/answer/edit.rs) use the common exact-locator and
quote policy. Family names and tools also appear in front-matter validation and
global dispatch; audit those repeated inventories for drift.

A useful first candidate is a typed family definition with explicit presentation
and evidence-policy descriptors, initially selecting today's behavior for every
family. Establish ownership and composition before adding more behavior. A
plugin loader, a second material reader or a family-specific custody path is not
needed to create that seam.

### Prepare for more opinionated families

| Component | What it should be able to express | Boundary to preserve |
| --- | --- | --- |
| Material roles | Explicit manager-declared roles and references to selected material; family-specific explanations and remedies. | Meaning comes from declarations, not filename guesses or prose classification. All literal selected bytes remain captured. A missing mapping does not prove evidence absent elsewhere. |
| Presentation policy | Role grouping, ordering, navigation and guidance about which sources serve which purpose. Identify derived views separately from originals. | Stable source identity, byte ranges, pagination and search completeness. No silent filtering, truncation, rewritten source or substituted excerpt; a changed access promise requires a decision. |
| Evidence expectations | Recommended evidence classes, provenance/context prompts, and explanations of what a missing source prevents establishing. | Separate structural invalidity from admissible insufficiency. A supplied report remains its author's claim; a proposed experiment is not witnessed execution. |
| Mechanical rules | Well-formed declarations, supported roles and valid references, with stable errors, warnings and suggestions. | Current empty/unequal/insufficient evidence stays admissible. A future mandatory evidence rule needs an explicit predicate and a principal decision about refusal versus advice. |
| Answer vocabulary and rendering | Family-owned authoring kinds, expected-section notices and presentation of the auditor's attributed account. | Missing sections and empty answers remain allowed. Citation validity does not grade support. Do not require a finding, winner, fixed hypothesis or answer endorsement. |
| Runtime mapping | Render the same effective family facts into Messages system/tools or the agent arrangement. | Family choice grants no extra access, execution, budget or lifecycle authority. Keep supplied open-inquiry guidance distinct from product-owned orientation and tools. |

Audit which descriptors must be versioned and pinned at preparation/acceptance,
which declarations belong in the ordinary question-file contract, and which views
can be derived from captured facts. A manager must be able to inspect what will
be commissioned. A later registry change must not silently alter an accepted
arrangement. Preserve one pure production rule layer for CLI and optional manager
MCP; filesystem acquisition and durable acceptance remain outside that layer.

Use the [worked examples](../examples/questions/README.md) to design a small
change-impact exercise: add a hypothetical evidence role and change only its
presentation advice. List every module, pinned document and test that would need
to move. The desirable result is a family descriptor, its explicit versioned
boundary and focused tests, with no new lifecycle or per-runtime authoring branch.
Do the exercise on paper before committing to a generic framework.

Controls should compare valid/invalid references, missing mappings, empty
materials, unequal evidence and renaming invariance. Terse versus detailed advice
must preserve mechanical outcomes. File-only versus MCP-assisted candidates must
capture equivalent enforceable inputs. A later presentation variant must retain
exact source/citation identities and complete access. Controls should detect a
lost material, a falsely required advisory role, a changed accepted guidance
block and a family change leaking into runtime permissions.

Before any new policy, prove extraction preserves each family's exact tool order,
schemas, arrangement and section notices in both modes. Read/search controls
should cross page boundaries, multibyte offsets and files without a final LF.
Refused edits must preserve earlier payloads. Artifacts fill no section, and a
comparison observation does not imply comparison coverage. These are useful
tests of modularity without introducing a new answer standard.

## Evidence for the audit

Tracked fixtures carry provenance in their owning guides:
[driver captures](../apparatus/driver/testdata/README.md),
[OS observations](../apparatus/driver/testdata/os/README.md),
[signature-tool outputs](../apparatus/claude-code/testdata/verification/README.md)
and [acceptance-reader records](../apparatus/testdata/acceptance/README.md).
Use their original bytes and declared transformations. In particular, denied
signal-0 observation does not establish process absence or the cause of denial;
Linux procfs denial tests a different mechanism. Replayed signature output does
not freshly authenticate a synthetic installation.

The following are local working sets, absent from a clone. Follow each root's
`native-review.json` for exact runs and output, except `readiness-fidelity-01/`,
which uses `native-01-reassessment.json` and `native-02-review.json`. Do not pick
the newest-looking folder. Keep original failed and passing outputs through
reassessment. These references do not extend retention after their inspection
purpose ends.

| Review root under `.tmp/` | Change anchor | Inspection purpose |
| --- | --- | --- |
| `readiness-fidelity-01/` | `3fa45d0` | Original driver failures, repaired fidelity cases, Messages regression and Cargo outputs. |
| `readiness-close-submit-01/` | `d80ab98` | Close/publication precedence, variant writers and retained-writer invariance. |
| `readiness-near-limit-01/` | `fb4a747` | Original timing failure and corrected notice-driven comparison; clock scope. |
| `readiness-observations-01/` | `82ee697` | Accounting fields and assistant names (the repeated message IDs are in that commit's driver guide, not the review); file-count repair. |
| `readiness-messages-fixtures-01/` | `25cb7f3` | M4 signed-summary baseline and corruption/invariance controls. |
| `readiness-cap-fixtures-01/` | `4af6cc2` | M2/M3 capped responses, cumulative charges, continuation and refusal. |
| `readiness-reminder-fixtures-01/` | `09f701c` | Reminder state and citation recovery; known transmission and interrupted charging are synthetic. |
| `readiness-c1-fixtures-01/` | `6019fd3` | Surface traffic and listener checks; supplied authentication/process results remain limited. |
| `readiness-authoring-fixtures-01/` | `24743b9` | C4 missing-field recovery, C5 full refusal and exact-version replacement. |
| `readiness-final-captures-01/` | `3dbec14` | M1/C2/C3 citation operands and C4 partial-account timing/retention. |
| `readiness-verifier-fixtures-01/` | `c1839c7` | Complete GPG/codesign outputs and corrected refusal-retention controls. |
| `readiness-qualification-fixtures-01/` | `324bc63` | Full result/self-test/exit records, actual skip refusal and one-property mutations. |
| `readiness-os-fixtures-01/` | `5e3a2ad` | Final native run `native-20261116T191616Z-510b657b`, exact OS originals and source/binary reconciliation. |

The [qualification index](../apparatus/qualified.md) owns selected `.scratch/`
originals and writer identities. For Messages compaction apparatus, use
`.scratch/readiness-m4-rehearsal-02/REVIEW.json` for the full-size synthetic
rehearsal and `.scratch/readiness-m4-live-01/REVIEW.json` for the bounded real
encounter. The C3 external-copy disposition is
`.scratch/readiness-c3-disposition-01/`. Verify bindings before using any source
as current evidence. `python3 -I -B apparatus/qualified.py check` validates the
retained index and reports source drift; a passing index check does not qualify
that drift.

## Finish with decisions the next developer can use

For each finding, record the current contract, responsible component, exact
trigger, original witness, comparison/control and result. Label it as a
reproduced defect, implementation coupling, coverage gap, or proposed product
change. Explain the smallest useful remedy, its tests, affected public forms
and any decision needed. A file count or passing-test total alone is not a
coverage argument.

Prefer a sequence that first clarifies internal runtime variants and family
ownership without changing behavior, then extracts one demonstrably common
operation at a time. Re-run the relevant independent comparisons before
expanding scope. New presentation or evidence requirements follow a separate
explicit contract decision. Maintain common obligations and documented mode
exceptions together, without making one mode's observations qualify the other.

Update the owning plans with current status and remaining work only. Put enduring
behavior in specifications and tests; retain findings here only while this
lookback needs them. Use [DEVELOPMENT's check table](DEVELOPMENT.md#what-to-run-for-what-you-changed)
for actual edits. Native tests aid iteration; changed service/driver behavior
needs the scheduled Linux suites, and WSL2 and real-model gates retain their own
scope. The audit is useful when it leaves bounded implementation candidates,
explicit limitations and decision requests, rather than another broad cleanup
mandate or a claim of release readiness.

## Findings and dispositions

The lookback ran on 2026-11-16 and 2026-11-17 from implementation-side
analyses, reproductions in throwaway copies and a specification-only driver
author. Everything below is native development evidence; none of it is Linux
qualification. Detailed analyses, diffs, mutation tables and logs are local
working files, absent from a clone; the decisions and behavior they support
are in the specifications, tests and commits named here.

### Decided and implemented

The principal decided four questions; the smaller rules below them were
approved with them. INTERFACE and the
[runtime contract](../docs/claude-code/CONTRACT.md) own the resulting behavior.

| Finding | Outcome | Commit |
| --- | --- | --- |
| A Messages signal let an executing mutation link, so a submit held before its seal still sealed; INTERFACE 6.8 said signals take the close path | Messages adopts the publication gate on signal: an unlinked mutation is refused `placement_stopped` and the placement ends `interrupted`; gating became an explicit core capability | `9465a54` |
| The agent runtime let a signal, close, deadline or stop-record failure observed during shutdown replace an already decided ending (a late SIGTERM reopened authoring; a quota rejection became `placement_deadline`) | The first observed condition decides; only a seal from the placement and a drain-time reply mismatch on an ordinary ending apply later | `9465a54` |
| Exhausted placement starts after a non-deadline interruption: status said authoring was open while `run` refused `authoring_ended` without data | The final placement's interruption ends authoring as `limit`; a gone final placement is reconciled, then refused | `9465a54` |
| While stopping was unknown, advice offered `run` and `close`, which refuse `runtime_stop_unknown` | Advice offers only `status`, from the same per-placement check the refusals use | `9465a54` |
| A bad launch directory consumed a start and recorded `interrupted` | Checked before the reservation, refusing `runtime_profile_invalid` | `9465a54` |
| A captured notice whose write failed was `not_sent` | `unknown`; the agent `request` member is the notice's position in its placement | `9465a54` |
| Implemented agent rules were unwritten: near-limit trigger, reminder trigger, error results, reused MCP IDs, notice inputs, default cause | Written into the runtime contract; an error result's usage stays a reported checkpoint with its interval unknown (principal's decision) | `9465a54` |
| Refusals at the start reservation lacked the `data` and `next` of INTERFACE 5.7 | Fixed in both runtimes | `9465a54` |
| A linked notice whose durability was unconfirmed was missing from `run_ended`; `run` and close rebuilt a gone placement's ending differently; the agent's near-limit notice took two clock readings | Fixed | `6f2b862` |
| Agent start-reservation failures were all `refused record_failed` | Messages mapping shared by both runtimes | `a6656f0` |
| Family vocabulary, guidance admission, tool union and dispatch were hand-kept copies of the family definitions | Derived from the definitions with exhaustive dispatch | `172792b` |
| No in-crate test pinned harness record, settings or arrangement bytes | Pinned | `bbf2e36` |
| Settings carried zero Messages limits for agent questions; limits were re-read from raw JSON | Runtime variant in settings | `b44c833` |
| The private launch directory survived under load when the owner's bounded stop wait ended first | Removed when the recorded stop observation finds the groups gone | `9465a54` |
| Driver coverage of the above | Specification-only cases; they fail on the measured property against binaries built before `9465a54` | `6588c4b`, `dfee2e8` |

### Unscheduled behavior-preserving candidates

Each keeps every public byte and needs only the usual checks, but none is
selected.

- Split the pinned arrangement into common and per-runtime parts. Agent
  arrangements still carry Messages placeholder members, and an archive with
  Messages settings beside an agent arrangement, which Stewart cannot
  produce, panics after `run_started` instead of refusing.
- Type usage, limits and remaining allowances by runtime. Agent limits can
  still reach Messages arithmetic (unreachable today), and adding usage
  across runtimes drops the other runtime's values silently.
- Move placement outcome types out of the Messages provider module, so the
  agent runtime stops depending on Messages abort and placement machinery.
- One notice claim for both runtimes. Their preconditions differ: Messages can
  claim a reminder after `close_requested`, the agent runtime cannot.
  Aligning them needs a small decision.
- One family resolution at preparation with a cross-runtime arrangement byte
  test; pinned and compiled family facts are not compared at run.
- Enforce the Messages request timeout from the pinned arrangement rather than
  an equal constant.
- Pin the agent readable view in a Cargo test (only a probe checked it), and
  decide whether a bad API limit beside a profile should keep reporting two
  defects for one key.

### Public-form candidates, not selected

Each changes a recorded or reply form and needs the principal's decision.

- Agent records without Messages placeholders (`provider`, `requests`,
  `attempts`), with a top-level runtime and only agent causes.
- Agent accounting naming its session and accepted checkpoint, with stopping
  outside usage.
- Agent notice identity with a durable transmission observation, so recovery
  could report `sent` rather than `unknown`.
- Agent `tool_result` without transport coordinates; named agent stop causes
  instead of one `protocol_anomaly`; a defined
  `claude-code,fault-injection,sabotage` build.
- Family descriptor work: verify the pinned arrangement against the compiled
  family at run; pin answer expectations; family-owned presentation separate
  from replaceable guidance; role-aware reading presentation; tool identity on
  refusal paths; a presentation-advice channel. Role declarations belong to
  the manager interface's registry stage.
- Smaller wording and form gaps: sealed advice says "An ordinary close confirms
  where the delivered copy is" when `run` did not deliver; an agent seal on a
  damaged log reports delivery `unknown` where Messages gives `none`; `run`'s
  binding refusal `runtime_profile_invalid` carries no `data.surface`, which
  the contract requires only of `prepare`.

### Test reliability and evidence notes

- Two tests failed once each under heavy machine load and passed on every
  rerun: the delivery test of a run still holding the lock (its stand-in found
  the lock held) and the Messages credential-descriptor deadline test.
- Accepted mutation survivors: equivalent mutants in the gate and settings
  slices; three agent races reachable only at the exact deadline instant and a
  failed final checkpoint write, for which no fault point exists.
- A host restart on 2026-11-16 cleared `/private/tmp`, including
  `/private/tmp/stewart-*` work directories some reviews name. The `.tmp`
  roots keep the retained copies.
