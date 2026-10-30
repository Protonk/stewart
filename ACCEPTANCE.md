# Stewart's acceptance specification

This is the current acceptance design for the [Stewart design](DESIGN.md), under
[CONTRACTS.md](CONTRACTS.md). It specifies the evidence owed, not executed
results. End to end means a manager's submission through the actual release
binary to an independently verified return; only the provider is replaced in
the scripted tier. Real-model conformance uses the real provider.

Every case below is read under the accepted machine interface:
[docs/INTERFACE.md](docs/INTERFACE.md) and
[docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md) give the exact schemas and
fixtures, the deterministic failure-injection points and the supported
filesystem and writer populations. The numerical response budgets are the
apparatus's timing gates ([apparatus/README.md](apparatus/README.md)). Do not
turn an illustrative command spelling, old form or arbitrary test quantity into
a new product obligation. No model-consuming run is commissioned here.

## Acceptance claims

Each claim below is something Stewart promises. A test passes only when it
shows the claim holding *and* shows that the same check would have caught it
failing.

| # | Claim |
| --- | --- |
| C1 | The auditor's world is exactly the arrangement. |
| C2 | The manager's question and material reach the auditor unchanged. |
| C3 | Answers are kept, sealed and attributed correctly, including across interruptions. |
| C4 | After context loss, bounded re-entry recovers recorded work and access without inventing missing memory. |
| C5 | The delivered return is complete, verified and faithful to what was recorded. |
| C6 | The record is honest: write-once, nothing deleted, the access log matches what happened. |
| C7 | Question families preserve the request, express their evidence expectations and leave open inquiry usable. |
| C8 | Close works from every state. |
| C9 | Stewart answers quickly and every reply says what it did. |
| C10 | Real models can actually use the arrangement and finish. |
| C11 | Help, the scaffold, preparation and the receipt explain the submission boundary and identify the selected material. |
| C12 | The run is a handoff: a receipt's run line works for whoever holds it, from anywhere. |
| C13 | A dead run continues: the audit is its ledger, and `run` again picks it up. |
| C14 | The process promises hold: refusals are recorded with their bytes and reason, every gap has a disposition, no record carries a verdict. |
| C15 | A manager recovers the fixed commission through its reference without the original session or source files. |
| C16 | Status distinguishes the run, answer seal, delivery and closure, with evidence and usable next actions. |
| C17 | Preparation/commission failures report their context, effects and uncertainty through Stewart's interface. |
| C18 | Designated custody remains intact through close, with explicit scope and no silent store substitution. |
| C19 | The initial reader and preparation inspection faithfully expose the literal text submission. |
| C20 | Machine replies expose exact bindings, effects and uncertainty through the correct role view. |

Answer quality is not on the list. Stewart doesn't judge answers, so its tests
don't either.

## Three tiers

| Tier | Runs | Model | Gate? |
| --- | --- | --- | --- |
| **Scripted** | Test image, every platform, every change | A fake provider replaying scripted turns | Yes |
| **Real-model conformance** | Experiment image, each release, each supported model | The real provider | Yes |
| **Experiments** | Experiment image, when someone has a question | The real provider | No |

The scripted tier tests Stewart's behavior within its covered cases. The
conformance tier tests whether the named models can use the arrangement. Experiments are where research
happens, such as whether read-only investigation is enough. They inform design
and never block a release.

## Rules every check follows

- **It can fail.** Each claim has a *sabotage control*: a deliberately broken
  input, or a test-only build flag that breaks exactly that property. The suite
  must catch it. A check whose control passes is itself broken.
- **It isolates what it measures.** Next to the passing case there is a *differing
  case* that changes only the property under test, and an *invariance case* that
  changes something the property must ignore.
- **The witness lives outside Stewart.** The test driver keeps its own copies of
  everything it supplied (question, material) and everything the fake auditor sent
  (each element's bytes, each citation). It compares the delivered return against
  those copies, never against Stewart's own records. The witness sits outside
  Stewart's archive and outside anything a test removes.
- **Counts are reported, not assumed.** Every run reports how many cases ran,
  passed, failed and were skipped, and which controls fired. Schema checks and
  ordinary positive cases alone do not establish enforcement.

## The scripted tier

The test image holds the release binary, the driver and a fake Messages API. The
fake replays scripts: lists of model turns, each a set of tool calls or a stop. It
can also produce a compaction block, a refusal, a rate limit, a server error, a
dropped stream, and a model that ends its turn without submitting. The binary
points at it through its provider URL setting and doesn't know it's fake.

For re-entry and continuation the fake also runs a *reacting auditor*: a small
deterministic policy in the driver with a goal list of entries, whose bytes the
driver keeps as the witness. It chooses each call from Stewart's actual replies.
After a forced compaction or a kill and continuation it discards its memory,
rebuilds its view only from the continuation notice, `what_am_i_working_with`
and its reads, and adds only the goals it cannot see recorded. The return must
contain each goal exactly once, so a re-entry that omits an element produces a
duplicate that the witness comparison catches. Fixed scripts remain for exact
protocol-shape cases. This shows that re-entry carries enough for a mechanical
agent to resume; whether real models use it well is the conformance tier's
question.

### C1 — The world is the arrangement

- **Pass:** every recorded request to the provider carries exactly the
  arrangement's tools (the common tools plus the family's recording tools), its
  system blocks (orientation and family instructions), its pinned model and
  request parameters, and `max_tokens` within its limits. The accepted receipt
  names the arrangement whose pinned bytes the first request actually carried;
  its settings agree with the prepared selection.
- **Differing:** a commission with a different family changes the tool list
  exactly by that family's recording tools, and the system blocks by its
  instructions.
- **Invariance:** changing the material changes the materials index but not the
  tool list or system blocks.
- **Also:** read, search and list given paths outside the material (`../`,
  absolute paths, names that only exist on the host) are refused with a sign, and
  nothing outside the material appears in any reply.
- **Sabotage:** a test build that adds one extra tool, and one where the recorded
  arrangement differs from the one sent. Both must fail.

### C2 — Question and material arrive unchanged

- **Pass:** the question-body bytes inside the first request equal the supplied body.
  Every `read` reply's content equals the witness copy of that material, byte for
  byte, over every byte range the script asks for.
- **Differing:** a question that differs by one byte appears with exactly that
  difference.
- **Invariance:** the same material supplied under a different directory path
  serves identical content under the same names.
- **Also:** empty files, very long lines and files at the size limit, read
  through the `utf8-text/1` reader. Non-UTF-8 content and NUL bytes refuse
  intake under the reader contract rather than being read approximately. Symbolic links, special files and
  other unsupported entries refuse intake rather than silently reducing it.
- **Sabotage:** material changed between intake and read in a test build, and a
  normalizing read. Both must fail.

### C3 — Answers kept, sealed and attributed

Scripts drive add, replace, delete, prepare, dry-run submit, confirmed submit and
manager close, including:

- a stale handle after an edit, which is refused;
- repeated confirmed submits, which return the same submission;
- repeated exact deletion, which reports its recorded removal, and stale
  replacement/deletion targets that cannot mutate a newer version;
- submit racing close, run many times, with exactly one winner each time and
  correct attribution;
- close after auditor launch on an empty answer, giving an honest empty return;
- the limits on elements and sizes, and the edits that are still allowed at them.

**Interruptions.** The ledger is the only truth. The driver kills the binary at
fixed points: while a record is being appended, after it is complete and before
the reply, during seal, and during delivery. Afterward, `what_am_i_working_with`
and `status` report exactly the complete records; a torn tail is reported as a
diagnostic and never as an element. A fresh repeated addition creates another
element; intentional equal-byte additions remain distinct. Re-entry identifies
both with their actual handles/receipts, without claiming sameness of intent.
Redelivery of a known completed invocation instead returns that outcome without
another mutation. Lost identities or unreadable outcomes cannot justify content
deduplication or guessed fresh execution. No settlement console or unfinished
authoring request is handed down as part of the auditor's answer.

- **Sabotage:** report a torn record as an element, merge fresh equal-byte adds,
  execute a known completed invocation twice, overwrite a newer version with an
  old target or attribute a manager seal to the auditor. Each control must fire.

### C4 — Re-entry restores recorded work and access

- **Pass:** the fake emits a compaction block midway. The reacting auditor then
  calls `what_am_i_working_with`, which returns bounded state/revision/allowances,
  exact question/material access, element/version handles, recent completed
  receipts and relevant refusals. It follows explicit pages/read handles
  and verifies all bytes against an independent witness, then continues without
  re-adding its prior work. Include an answer and question/index exceeding one
  reply, with essential content on the last page. Re-entry is not a mutation gate.
- **Differing:** a relevant refusal retains its operation/revision; an intervening
  edit invalidates an old page rather than silently mixing two answer revisions.
  Missing or damaged recorded data is distinct from lost model context.
- **Invariance:** the same run without compaction produces the same sealed answer.
- **Sabotage:** omit an element, truncate without continuation, omit the last
  page, mix revisions or reset allowances after compaction. Each must fail.
  These checks preserve recorded work, not thoughts never submitted to the ledger.

### C5 — The return is complete and faithful

- **Pass:** the driver compares each delivered return against its witness: every
  element's bytes and order, the typed structure and artifact identities, the form and version named, the
  audit reference, and who sealed it. The manifest digest printed at seal equals
  the delivered one. An inventory of the delivered package holds the manifest,
  the structured answer, the rendering and artifact members, and nothing else:
  no question, receipt, arrangement, access log, run summary or conversation. The preparation-generated Markdown rendering
  is a sealed member, attributed to Stewart and reproducible from the exact
  structured answer and elements under the pinned rendering rules. The auditor
  can inspect those same bytes before confirming submission.
- **Rendering comparisons:** a changed answer requires fresh preparation and a
  matching rendering; an unrelated installed-form change cannot alter delivery
  or readback of an existing seal. Contradictions and missing evidence in the
  recorded answer stay attributed and are never repaired by the renderer. Cover
  manager sealing of unsubmitted work without claiming auditor review, and a
  rendering failure that remains diagnosed rather than dropping the member.
- **Also:**
  - a delivery interrupted partway keeps its partial directory and names the
    missing members, and `close` produces a complete copy;
  - an unavailable destination is replaced through `close REF --destination DIR`;
    the new exclusive copy has the same seal and member bytes, the original
    location and failure remain recorded, and no provider request occurs;
  - a lost reply after verified delivery is recovered through close without a
    second copy; an existing conflicting package is neither overwritten nor
    adopted as Stewart's own attempt;
  - a payload corrupted in Stewart's storage before delivery is reported as
    damage, never delivered as good, never treated as absent from the answer;
  - an unknown membership is never delivered as an empty answer.
- **Sabotage:** a build that drops the last element, one that publishes completion before
  the selected members verify, and one that delivers the conversation beside the
  answer; also one that regenerates the rendering at delivery under a different
  form or silently adds a substantive conclusion.

### C6 — The record is honest

- **Pass:** an inventory of the archive before and after every command shows
  only additions: no file is rewritten and none removed, through to and after
  close. This is the decided first-release retention policy, not a proposal.
  An in-progress new file may be incomplete; it never replaces an earlier record.
  The access log (the `list`, `read` and `search` calls captured in each run)
  equals the sequence in the script. Each `run_ended` record's turns and usage
  equal what the fake reported.
- **Sabotage:** a build that rewrites a record in place, removes a retained partial
  on retry/close, or skips logging a search. Independent inventories remain outside
  the archive so a passing result cannot conceal deletion of the witness.

### C7 — Question families

These are acceptance obligations for the selected organizing model. Concrete
schemas, tools and rendered fixtures are specification deliverables under the
closed design, not open policy choices.

- **Pass:** each selected family preserves the manager's question verbatim and
  pins its versioned guidance, material expectations and answer instructions in
  the prepared arrangement. A broad request commissions through open inquiry
  with no modules and no extra justification or reduced service.
- **Differing:** selecting inquiry framing explicitly commissions formulation
  and investigation within the same undertaking. The original request and the
  auditor's working question remain distinguishable. Once modules are specified,
  selecting one changes only its declared prompts and answer expectations.
- **Invariance:** changing the family or selecting no module never silently
  rewrites the question or expands material access, tools beyond the declared
  form, budget or investigation. Missing declared material-role mappings do not
  block commissioning or become claims that no attached file contains evidence.
- **Permitted answers:** disagreement with the framing, missing evidence,
  no supported finding and qualified support can each be expressed and submitted
  without inventing a defect or repair. Inquiry framing permits an account that
  useful bounded investigation was impossible. No test grades agreement with an
  expected substantive conclusion as successful compliance.
- **Citation controls:** compare a valid locator/quote, a changed range or quote,
  and a valid but irrelevant citation. Only the mechanical mismatch refuses the
  entry mutation; the raw attempted call remains recorded and no answer element
  is created for the refusal. Prose that resembles a citation is not scraped;
  paraphrases are not checked as verbatim quotations. Read/search references can
  be used directly without guessing offsets.
- **Omissions:** prepare describes missing entries factually, without refusing
  preparation/submission or adding acknowledgment steps. Incomplete, empty and
  ordinary complete selections all have submission paths. An empty answer cannot
  render as "no issues found." Invalid or damaged selected bytes remain custody
  failures, not nonblocking intellectual omissions.
- **Prompts:** capture the exact orientation and notices delivered. One ordinary
  unsubmitted stop can receive the procedural reminder; another ends the
  placement. Continuation cannot reset the audit's one reminder or one near-limit
  notice. Exercise exhausted allowances, provider failures and interrupted calls
  as differing events; no extra allowance or automatic auditor seal appears.
- **Sabotage:** a build that paraphrases the manager's question, requires a module
  for open inquiry, silently gives another family the inquiry-framing task,
  grades evidential support, blocks an incomplete selection, or resets a prompt
  allowance after continuation.
- **Specification:** [docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md) gives the
  concrete field/tool schemas and orientation wording. Optional modules and
  hidden-prior machinery are unselected. C5 owns rendering.

### C8 — Close from every state

Close runs against each state: preparation, failed intake, copying in flight,
accepted but never launched, running (live loop), ended without
submission, submitted, delivered, partially delivered, damaged storage and
already closed. Each reaches the documented effects or an explicit unfinished
outcome with its supported continuation. Before launch it leaves the manager's
folder intact, prevents future launch and creates no answer, empty manager seal
or answer-placement confirmation. Failed intake is accounted for without forcing
successful submission. Race close with intake using controlled synchronization;
their outcomes must agree and no launch may follow closing. After launch a prior
auditor seal keeps its actor; an unsubmitted selection is sealed by the manager.
Sealing alone never counts
as stopped execution. Delivery preceding the first close request permits ordinary
close to confirm placement;
close that first produces a copy presents a seal/delivery-bound confirmation
reference and remains unfinished until it is confirmed through close.

Kill after copying and before its reply, and after confirmation and before its
reply. Status recovers the exact outstanding confirmation or recorded closing
outcome; a repeat without `--confirm TOKEN` only re-presents a copy first made
through close, even though delivery now predates that repeat. It does not reseal,
recopy a verified delivery or close without the required confirmation. A confirmation for a different seal/delivery is
refused. Confirming with a known missing member requires naming the undertaking
being given up separately from placement confirmation. Unknown membership stays
unfinished and never becomes an empty return. Replacing the destination repairs
no missing source bytes. A stop whose completion cannot be established keeps
close unfinished with its evidence.

Under the decided first-release retention rule, none removes anything (C6). There is
no separate collect or deliver command. The differing case is delivery before
versus during close; the invariance case changes the invoking directory and
process after a lost reply. Sabotage controls skip post-copy confirmation,
report sealed authoring as terminated execution or invent an empty return before
launch; each must fail.

### C9 — Quick, and sure of what it says

- **Response budgets**, measured natively in the test image on material at the
  size limits and reported as actual timings. Timings under emulation are
  reported but do not gate:
  - startup, `status` and `help` answer within tens of milliseconds;
  - every protocol call except a full-material search does too;
  - manager preparation and source scanning report scope and progress; intake,
    commission readback, full search and delivery state their known size and
    report progress; raw readback has no progress text in its byte stream.
- **Certainty:** every protocol reply uses the specified structured envelope. Every refusal
  carries a reason, its effect and the next call. Every manager command's JSON
  output carries what changed and what was verified. A schema check runs over
  every reply the suite produces.
- **Sabotage:** a build with an injected delay in one protocol call, and one that
  omits the established/uncertain effect on one refusal.

### C11 — The app teaches

- **Pass:** the scaffold and help explain ordinary editing and the instruction
  to leave the folder unchanged from prepare through commissioning. Prepare's
  manifest identifies the witness's question, material names, hashes and settings;
  its handle alone accepts nothing. Explicitly confirmed commissioning preserves
  those bytes and records the manager declaration separately from observed checks.
- **Differing:** change selected contents or membership after preparation; the
  old handle refuses rather than capturing the newer selection. Fresh preparation
  permits the revised proposal under the same unaccepted reference.
- **Invariance:** compose prepare and commission without an inspection pause;
  the accepted bytes and declarations follow the same contract. Source edits after
  acceptance leave the commission unchanged.
- **Also:** omit the affirmative argument; no acceptance. Exceeded limits,
  unsupported entries, unknown fields and name collisions have useful refusals,
  with no silent exclusion or renaming. Close after prepare requires no unprepare.
- **Sabotage:** silently accept newer bytes, omit an entry, accept without explicit
  affirmation, or present matching scans as proof of a source snapshot. Each
  control must fail. Preparation's readable arrangement is checked under C19;
  no separate preview command or question-grading surface is required.

### C12 — The run is a handoff

- **Pass:** the receipt carries the reference and the exact run line. Copied
  into a shell in an unrelated directory with a different home, that line runs
  the audit to delivery; `status REF` from a third directory reports the seal,
  verified delivery and still-open closure, and names the destination. The run is
  in the foreground and exits with the run's outcome.
- **Differing:** `run` on a reference that is running, has ended or is closed is
  refused with a sign naming the state and the next command.
- **Invariance:** who invokes `run` and from where changes the record's
  observations (user, process, time) and nothing else; invocation observations do not invent a person's identity or acknowledgment;
  actual manager-versus-auditor seal attribution remains required.
- **Also:** `run` without the provider's key refuses before any request, naming
  what it needs; `commission` succeeds without network and without the key.
- **Sabotage:** a build whose run line depends on the commissioning directory,
  and one that commissions over the network.

### C13 — A dead run continues

- **Pass:** the driver kills the binary mid-run at fixed points: during a
  provider request, while a tool reply is being written, and between turns.
  `status` then reports the audit interrupted with its run count, as an
  observation with its evidence (a run record without an end record and no
  observable process), never as an inference from elapsed time; the liveness
  mechanism is the active lock of [docs/INTERFACE.md](docs/INTERFACE.md) 4.6.
  `run REF` continues: the first request of the new conversation carries the
  continuation notice and the same pinned system and tools bytes as the first
  run; the ledger's elements are unchanged; the limits reported to the auditor
  are cumulative across runs; the final submission contains every element
  recorded before the kill exactly once; the record holds every run.
- **Differing:** a run killed after a confirmed submit leaves the audit ended;
  `run` refuses with a sign and `close` delivers. A provider that fails past the
  bounded retry ends the run as interrupted, and `run` again continues.
- **Invariance:** the same script without a kill yields the same sealed answer
  (shared with C4).
- **Sabotage:** a build that resets limits on continuation, and one that starts
  a fresh ledger.

### C14 — The process promises hold

- **Pass:** every refused protocol call (a limit, a stale handle, a refused
  citation, a path outside the material) is in the record with its reason and
  the bytes the auditor sent; every gap (a torn tail, a limit refusal, a dead
  run, an undelivered member) appears in `status` with a recorded disposition;
  no record, reply or return assigns a substantive grade or verdict. Schema
  checks distinguish invocation outcomes/configured limits from judgments of
  the answer; arbitrary authored text remains attributed.
- **Differing:** a refusal of a different kind is recorded with its own reason.
- **Invariance:** the same script with the refused call omitted produces the
  same sealed answer.
- **Sabotage:** a build that drops a refused add without recording it, and one
  that adds a Stewart-assigned substantive verdict to the manifest.

### C15 — Manager recall through the receipt

- **Pass:** the witness retains the commissioned question, problem, arrangement
  and input bytes. After the originating session is gone and the source files
  have been removed or changed, `receipt REF` supplies the recorded commission
  and stable readback item IDs. `receipt REF --read ITEM` matches the witness
  bytes for each item. Receipt and status both supply the readback route. The
  installed form definition cannot replace the recorded arrangement.
- **Differing:** damage one retained input. Its readback diagnoses damage;
  another independently verified input still reads. The original receipt is
  unchanged and recorded acceptance is distinguished from current verification.
- **Invariance:** an unrelated working directory, changed HOME and no provider
  key change no selected bytes; repeat while running and after close with the
  material retained. No read changes the ledger or sends a provider request.
- **Also:** an incomplete commission is not called accepted; unavailable or
  unsupported selected evidence keeps its diagnostic; closed-custody readback
  with missing bytes never substitutes a live original. Raw bytes and diagnostic
  output use separate streams, including large inputs and exact non-text answer artifacts where admitted.
- **Sabotage:** a build that reads the live source, one that renders the current
  form in place of the recorded arrangement, and one that treats an intact
  member as proof of whole-commission integrity. Each must fail.

### C16 — Status answers the manager's actual question

- **Pass:** at each independently witnessed lifecycle point, status reports the
  run observation, answer seal/actor, delivery verification/location and closure
  as distinct facts, with the receipt command and any specific next action.
  Human and JSON presentations agree. The test covers preparation, failed intake,
  uncertain acceptance, closure before launch, a never-run commission,
  held run, interruption, ordinary unsubmitted stop, limit stop, sealed but
  undelivered answer, partial delivery, verified delivery, incomplete close,
  completed close and close with an explicitly surrendered known delivery loss.
- **Differing:** kill before versus after sealing. The former may continue
  through run under existing limits; the latter continues delivery through close
  without a provider call. Neither is called a completed delivery.
- **Invariance:** changing elapsed time establishes no liveness or completion;
  changing a previously delivered copy does not cause status to certify its
  present safety or silently undertake another delivery. Status is read-only.
- **Also:** damaged or unreadable controlling records keep their diagnostics,
  and absent observation facilities do not establish that a process stopped.
  Inquiry status lists references without choosing an audit by recency.
- **Sabotage:** a build that calls every ended run submitted, one that calls a
  seal delivered, and one that converts unknown membership into an empty answer.
  All must fail.

### C17 — Exceptional state has one contextual presentation

- **Pass:** force a required source read to fail after prepare, then a destination
  write, verification, acceptance-record operation and receipt-delivery operation
  in separate cases. The caller receives a stable reason with operation and cause,
  established or uncertain acceptance, known effects, retained locations and a
  supported next action. Independent witnesses establish which effects occurred.
  Check both human and structured presentations; helper output is not the only
  diagnostic. These are controlled boundary failures, not timing-dependent sleeps.
- **Differing:** fail before acceptance versus after acceptance but before reply.
  The latter must reconcile to the original acceptance under the same handle,
  without another capture, even when the source has subsequently changed.
- **Invariance:** a permission change that leaves every required operation and
  verification working does not itself manufacture a changed-selection failure.
  Restoring source access permits a matching prepared selection to be retried.
- **Also:** fail diagnostic persistence as well as the original operation; retain
  both causes and distinguish reported from durably recorded diagnostics. Exercise
  unclassified errors and reporting-channel failures. Forced termination and
  startup failure test the caller's missing-result handling and later reconciliation,
  not an impossible immediate reply from an absent process. Unknown acceptance
  never becomes absent acceptance and never authorizes a fresh capture by default.
- **Sabotage:** replace the original failure with a secondary logging error,
  treat unreadable acceptance as absence, blindly repeat after a reply failure,
  or omit a planned partial effect from the account. Each control must fail.

### C18 — Designated custody and retention

- **Pass:** create explicit, disjoint preparation, archive and delivery locations.
  Witness their identities and the full expected archive population independently.
  Accept, lose the original sources, read back, deliver and close; original input
  readback still verifies and the separately delivered answer verifies after the
  archive is made unavailable in the test. No earlier record, partial, failed stage
  or superseded/deleted payload disappears through retry, close or storage pressure.
  The preparation directory remains untouched by close.
- **Differing:** remove or replace the named archive in a controlled specimen;
  the reference diagnoses missing/different storage rather than creating or using
  a fresh audit. Damaged records remain damaged, not newly absent. Startup with
  insufficient permissions reports contextual failure without broadening access.
- **Invariance:** change working directory, installation path and default-store
  configuration while using the original reference. It still selects only its
  bound archive. A copied archive grants no execution permission by itself.
- **Also:** root/destination overlaps and aliases are refused from actual opened
  locations. The operating owner can read retained files during a run, while the
  manager product offers only receipt/status/close and the auditor tools expose
  no archive path or unrelated file. This tests those distinct scopes, not secrecy
  from the owner. No hold release, disposal permission or delivery verification
  is inferred from close, copying, a backup path or an externally removed file.
- **Sabotage:** select a newer store, fall back to live source bytes, prune on
  pressure, treat retained internal bytes as delivered elsewhere, or declare a
  missing archive closed and clean. Each control must fire. Witnesses and damaged
  originals remain retained under the evidence-run rules through review.

### C19 — Literal text materials and preparation inspection

- **Pass:** witness `question.md` and every file/directory under `materials/`,
  including hidden names, empty files/directories, BOMs, CRLF, multibyte characters
  and absent final newlines. Preparation and acceptance agree with that exact
  population. Read ranges reassemble the exact originals; long lines span pages
  without lost bytes or split UTF-8 code points. Search reports correct literal
  hit positions, named scope and explicit completion/continuation.
- **Differing:** invalid UTF-8, NUL, links/special files, unexpected root entries,
  ambiguous names and each independently exceeded bound produce useful refusals
  with no acceptance or silent exclusion. A file's name alone must not claim
  document extraction, rendering or execution. The nominal-document case whose
  bytes meet the text rule is described and served only as raw text syntax.
- **Invariance:** extension changes preserve raw text; moving an otherwise equal
  submission to another explicit source location/reference preserves public names
  and bytes. Permissions that leave required access working do not change content
  identity. Distinct hard-link names remain distinct selections.
- **Inspection:** before acceptance, prepare returns the manifest and locations
  of readable/machine arrangement records. Verify pinned instruction/tool/limit
  bytes and source bindings against a witness. Change the installed form after
  preparation: the old handle either uses its verified pinned arrangement through
  a supported writer or refuses, never silently regenerates it. Preparation does
  not claim accepted original-input custody; the manager needs no preview command
  or mandatory review acknowledgment beyond explicit commissioning.
- **Bounds:** exercise exact and just-over limits independently for question,
  file count, file bytes, total bytes, directories, path size/depth/components,
  read pages and search pages. Enumeration/read limits are enforced while working,
  rather than after unbounded allocation. Empty materials remain mechanically
  admissible; no test grades whether the question has sufficient evidence.
- **Sabotage:** skip hidden content, normalize newlines/names, auto-expand an
  archive, follow a link, silently truncate a long line/result set, omit the final
  page or regenerate instructions from the current installation. Each must fail.

### C20 — Machine interface facts and bindings

For each operation, keep literal request/reply fixtures and exercise them through
the actual CLI or tool adapter, including both role-specific presentations.
Ordinary manager JSON commands emit one final structured stdout reply even on
expected refusal; progress and diagnostics cannot contaminate it. Raw readback
contains only the requested bytes. Missing replies imply unknown effects.

- **Pass:** edit replies return exact targets/revisions; prepare returns bounded
  counts and views of its fixed inventory/rendering without an actual sealer;
  confirmed submit returns the actual recorded seal and its binding. Inspect
  prepared bytes again after sealing: they are unchanged. Final return verification
  uses the seal/manifest and exact member bytes without private archive state.
- **Differing:** stale preparation, stale entry target, malformed citation,
  missing expected sections, empty selection, dry run, manager-close seal race,
  known completed invocation replay and a fresh identical addition each retain
  their distinct effects. Repeated accepted submit after close returns its seal.
- **Invariance:** JSON whitespace in a newly decoded request cannot alter semantic
  values, but never reserialize stored bytes to authenticate their digest. An
  unrelated installation/form change cannot alter a pinned candidate or return.
- **Failures:** known absent, accepted and uncertain acceptance get different
  next actions; recorded seal with incomplete delivery is not failed submission.
  Exercise lost reply and diagnostic-write failure. Machine next calls carry
  usable operands and preserve alternatives; none silently retries a mutation.
- **Views:** auditor replies omit host coordinates, family name and manager-only
  records. Handles bind purpose, audit/store and version; crossed or constructed
  handles cannot select another object. Pages expose coverage and stale revisions
  without silently switching selections. No caller computes its own manifest.
- **Parsing:** duplicate keys at any depth, escape-equivalent repeats, unknown
  fields, mistyped booleans and out-of-bound integers refuse usefully while raw
  attempts are preserved. Unsupported schemas/writers are not silently upgraded.
- **Sabotage:** retarget a stale handle, label preparation auditor-sealed, leak a
  custody path, accept a typo, replace an uncertain effect with absence, omit a
  page, or imply delivery/close from submission. Every corresponding check fires.

### Platforms

The scripted tier runs, unchanged, on:

- Linux aarch64 and x86_64 in the test image. On the development Mac that means
  a native aarch64 container and an emulated x86_64 one.
- WSL2 natively, through the handoff package: the same binary, driver and fake
  provider, with the home on the WSL filesystem and a destination under `/mnt/`.
  Archive placement is qualified on its actual filesystem semantics:
  [docs/INTERFACE.md](docs/INTERFACE.md) 4.1 names the supported filesystems
  and refuses others by the type `statfs` observes, not by a path prefix.

Each run records the binary's digest, the image digests or WSL environment
(Windows and WSL versions, distribution, kernel, architecture, filesystem types),
the case counts, the timings and every control that fired.

## The real-model conformance tier

This tier answers C10. It checks procedure, never answer quality.

**Fixed commissions.** The apparatus will contain small commissions covering the
three selected families: open inquiry, inquiry framing and comparison. Each
specimen includes a manager submission, actual auditor tools and an example
return, with an inadequate-evidence case. Executable fixtures follow the form
specification; planted evidence may help inspection but finding it is not a
required substantive outcome.

Each is sized so that forcing compaction is practical, either through a low
compaction trigger or a run long enough to reach it.

**Runs.** For each model a release supports: each commission three times at the
release's default effort, plus one run with compaction forced and one run killed
midway and continued. These are planning quantities, not authorization to spend;
the bounded conformance commission fixes model coverage and budget before launch.

**The gate passes when, for every run:**

- the run ends sealed by the auditor's own submission, not by a limit, a close,
  or a second unsubmitted stop;
- structured material citations satisfy the mechanical locator/quote rules;
  evidential support is never graded by Stewart;
- after compaction, and after a kill and continuation, no element recorded
  before it is added again, and the submission still contains them;
- the answer follows the specified authoring/submission procedure; missing form
  coverage and empty answers remain admissible and no substantive finding is
  required.

Report the operations actually exercised. An allowed empty submission can show
submission conformance but supplies no evidence about unused entry/edit/citation
paths. Qualify that coverage explicitly; do not replace missing procedural evidence
with a content-completeness grade.

**Reported but not gating:** whether the planted fact or the unsupported premise
was found, turns and tokens used, how often `what_am_i_working_with` was called and
when, reminders sent, and cost. These go into the release notes as observations.

Every release names the models it passed this gate on. A model the gate hasn't
seen isn't listed as supported.

Running this tier spends real money on the provider. Each release states its
cost.

## What a test run keeps

Each run keeps a record next to the work that cites it:

- the binary and image digests;
- the environment;
- per-case outcomes and counts;
- timings;
- which sabotage controls fired;
- the witness comparisons;
- for the conformance tier, the full recorded conversations and actual provider usage/cost.

Bulky material such as conversations and homes at the size limits follows the
project's retention rules for evidence runs. The witness is kept until the run's
results have been reviewed.

## What these tests don't claim

- That answers are good. That's the manager's judgment.
- That read-only investigation is enough. That's research for the experiment tier.
- Anything about the person adapter, which isn't in the first release.
- Anything about a provider's behavior beyond what the conformance gate observed.
