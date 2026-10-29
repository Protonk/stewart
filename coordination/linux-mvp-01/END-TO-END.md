# End-to-end tests for the router

What an end-to-end test of [the router](ROUTER.md) has to show, and how. "End to
end" here means from a problem file a manager wrote to a verified return the
manager reads, through the actual release binary, with nothing replaced except
the model provider, and in one tier not even that.

Revised at turns 19–23 of [the conversation](CONVERSATION.md): ledger truth
replaces settled interruptions in C3 and C4, `collect` and `deliver` leave the
command set in C3, C5 and C8, three claims are added (C11, C12, C13), and C5
delivers only the submission. The version before those turns is in Git at
`05a21d4`. The design review ended at turn 23; this is the settled test design.

Amended 2026-10-28 under the user's delegated resolution of manager recall and
status/close, following CONTRACTS' "Successor manager readback, status and
close": C5/C8/C12 are qualified and C15/C16 added. These are acceptance designs,
not executed checks. Preview, auditor retry and question typing remain separate
discussions; their existing proposed checks are not settled by this amendment.

## What we care about

Each claim below is something the router promises. A test passes only when it
shows the claim holding *and* shows that the same check would have caught it
failing.

| # | Claim |
| --- | --- |
| C1 | The auditor's world is exactly the arrangement. |
| C2 | The manager's question and material reach the auditor unchanged. |
| C3 | Answers are kept, sealed and attributed correctly, including across interruptions. |
| C4 | Compaction is harmless: an auditor that loses track recovers through the protocol. |
| C5 | The delivered return is complete, verified and faithful to what was recorded. |
| C6 | The record is honest: write-once, nothing deleted, the access log matches what happened. |
| C7 | Couplings wrap the question, expose their slots, and check citations. |
| C8 | Close works from every state. |
| C9 | Stewart answers quickly and every reply says what it did. |
| C10 | Real models can actually use the arrangement and finish. |
| C11 | The app teaches: the problem file, the preview and the receipt show the manager exactly what the auditor gets. |
| C12 | The run is a handoff: a receipt's run line works for whoever holds it, from anywhere. |
| C13 | A dead run continues: the audit is its ledger, and `run` again picks it up. |
| C14 | The process promises hold: refusals are recorded with their bytes and reason, every gap has a disposition, no record carries a verdict. |
| C15 | A manager recovers the fixed commission through its reference without the original session or source files. |
| C16 | Status distinguishes the run, answer seal, delivery and closure, with evidence and usable next actions. |

Answer quality is not on the list. Stewart doesn't judge answers, so its tests
don't either.

## Three tiers

| Tier | Runs | Model | Gate? |
| --- | --- | --- | --- |
| **Scripted** | Test image, every platform, every change | A fake provider replaying scripted turns | Yes |
| **Real-model conformance** | Experiment image, each release, each supported model | The real provider | Yes |
| **Experiments** | Experiment image, when someone has a question | The real provider | No |

The scripted tier proves Stewart behaves. The conformance tier proves real
auditors can work in what Stewart builds. Experiments are where research
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
  Stewart's home and outside anything a test removes.
- **Counts are reported, not assumed.** Every run reports how many cases ran,
  passed, failed and were skipped, and which controls fired.

## The scripted tier

The test image holds the release binary, the driver and a fake Messages API. The
fake replays scripts: lists of model turns, each a set of tool calls or a stop. It
can also produce a compaction block, a refusal, a rate limit, a server error, a
dropped stream, and a model that ends its turn without submitting. The binary
points at it through its provider URL setting and doesn't know it's fake.

### C1 — The world is the arrangement

- **Pass:** every recorded request to the provider carries exactly the
  arrangement's tools (the protocol plus the coupling's slots), its frame and its
  limits. `stewart preview` produces the same arrangement digest as the first
  request actually sent.
- **Differing:** a problem with a different coupling changes the tool list exactly
  by that coupling's slots.
- **Invariance:** changing the material changes the materials index but not the
  tool list or frame.
- **Also:** read, search and list given paths outside the material (`../`,
  absolute paths, names that only exist on the host) are refused with a sign, and
  nothing outside the material appears in any reply.
- **Sabotage:** a test build that adds one extra tool, and one where preview
  renders a different frame from the one sent. Both must fail.

### C2 — Question and material arrive unchanged

- **Pass:** the question bytes inside the first request equal the manager's file.
  Every `read` reply's content equals the witness copy of that material, byte for
  byte, over every line range the script asks for.
- **Differing:** a question that differs by one byte appears with exactly that
  difference.
- **Invariance:** the same material supplied under a different directory path
  serves identical content under the same names.
- **Also:** non-UTF-8 bytes, empty files, very long lines, files at the size limit,
  and symbolic links and special files inside a supplied directory (listed in the
  receipt as not copied).
- **Sabotage:** material changed between intake and read in a test build, and a
  normalizing read. Both must fail.

### C3 — Answers kept, sealed and attributed

Scripts drive add, replace, delete, prepare, dry-run submit, confirmed submit and
manager close, including:

- a stale handle after an edit, which is refused;
- repeated confirmed submits, which return the same submission;
- submit racing close, run many times, with exactly one winner each time and
  correct attribution;
- close on an empty answer, giving an honest empty return;
- the limits on elements and sizes, and the edits that are still allowed at them.

**Interruptions.** The ledger is the only truth. The driver kills the binary at
fixed points: while a record is being appended, after it is complete and before
the reply, during seal, and during delivery. Afterward, `what_am_i_working_with`
and `status` report exactly the complete records; a torn tail is reported as a
diagnostic and never as an element; the auditor's retry lands exactly once, as a
new record; nothing is settled on the auditor's behalf and no unresolved-operation
state appears in any reply or in the return.

- **Sabotage:** a test build that reports a torn record as an element, and one
  that drops a retry as a duplicate because its bytes match.

### C4 — Compaction is harmless

- **Pass:** the fake emits a compaction block midway. The script then calls
  `what_am_i_working_with`, which returns the question verbatim, the materials
  index and every element recorded so far. The script
  continues and submits, and the submission contains the elements recorded before
  compaction exactly once.
- **Differing:** a submission error pending at compaction shows up in
  `what_am_i_working_with`.
- **Invariance:** the same run without compaction produces the same sealed answer.
- **Sabotage:** a build whose re-entry reply omits the current answer.

### C5 — The return is complete and faithful

- **Pass:** the driver compares each delivered return against its witness: every
  element's bytes and order, the account marker, the form and version named, the
  audit reference, and who sealed it. The manifest digest printed at seal equals
  the delivered one. An inventory of the delivered directory holds the manifest
  and the elements and nothing else: no question, receipt, arrangement, access
  log, run summary or conversation. Whether a prepare-generated rendering is a
  sealed member is undecided; if it is, it is attributed to Stewart and
  reproducible from the elements.
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
- **Sabotage:** a build that drops the last element, one that writes the
  manifest after the members, and one that delivers the conversation beside the
  answer.

### C6 — The record is honest

- **Pass:** an inventory of Stewart's home before and after every command shows
  only additions: no file is rewritten and none removed, through to and after
  close. ("None removed" presumes the proposal that Stewart never deletes; if
  the user decides otherwise, this becomes "only additions until close" and C8
  gains the earlier close contract's removal checks.) The access log equals the sequence of read, list and search calls in the
  script. The run summary's turns and usage equal what the fake reported.
- **Sabotage:** a build that rewrites a record in place, and one that skips logging
  a search.

### C7 — Couplings

- **Pass:** for `survey` and `claim-check`, the frame contains the manager's
  question verbatim and the coupling's wrapper. The slots appear as tools. Filled
  slots render in the return as the coupling specifies.
- **Citations:** a citation to real lines passes. One off by a line, one naming a
  missing material, and one quoting text that isn't there are each refused with a
  sign and never recorded as valid. (The mechanical check is one of the
  answer-form choices; this item stands only if it is adopted. Under C14 the
  refused call is still recorded with its bytes and reason.)
- **Exits:** *wrong question*, *missing evidence* and *nothing found* each seal and
  deliver like any other answer.
- **Prior:** `claim-check` shows the manager's claim. A coupling that seals the
  prior keeps it out of every request and delivers it only in the return.
- **Sabotage:** a build that paraphrases the question, and one that accepts an
  off-by-one citation.

### C8 — Close from every state

Close runs against each state: commissioned, running (live loop), ended without
submission, submitted, delivered, partially delivered, damaged storage and
already closed. Each reaches the documented effects or an explicit unfinished
outcome with its supported continuation. A prior auditor seal keeps its actor;
an unsubmitted selection is sealed by the manager. Sealing alone never counts
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

Under the still-proposed never-delete rule, none removes anything (C6). There is
no separate collect or deliver command. The differing case is delivery before
versus during close; the invariance case changes the invoking directory and
process after a lost reply. Sabotage controls skip post-copy confirmation or
report sealed authoring as terminated execution; both must fail.

### C9 — Quick, and sure of what it says

- **Response budgets**, measured in the test image on material at the size
  limits and reported as actual timings:
  - startup, `status`, `preview` and `help` answer within tens of milliseconds;
  - every protocol call except a full-material search does too;
  - intake, commission readback, full search and delivery state their size first
    and report progress; raw readback has no progress text in its byte stream.
- **Certainty:** every protocol reply begins with the header line. Every refusal
  carries a reason, its effect and the next call. Every manager command's JSON
  output carries what changed and what was verified. A schema check runs over
  every reply the suite produces.
- **Sabotage:** a build with an injected delay in one protocol call, and one that
  omits the effect line on one refusal.

### C11 — The app teaches

- **Pass:** `stewart new` for each form writes a problem file whose every field
  carries a comment and an example, which parses unchanged. `stewart preview` of
  a witness problem renders the question byte for byte, the materials index with
  the witness's names and sizes, and the same arrangement digest the first
  request later carries (C1). The checks fire on planted cases: a name in the
  question that appears in no material, a material the question mentions that is
  not attached, a directory that expanded to nothing, and files skipped by the
  default excludes, each naming what the auditor would experience.
- **Advisory:** `commission` proceeds past every check and the receipt records
  each one verbatim.
- **Names:** a relative path is the material's name; an absolute path without a
  label is refused with a sign; two materials that would share a name are refused
  with a sign; nothing is renamed.
- **Mouth and record:** the question inline and the same question by path, and
  material listed in the file and the same material as arguments, produce
  identical canonical problems and receipts. An unknown key and a bad value are
  each refused naming the field and the fix.
- **Excludes:** version-control administration, build output and over-limit
  files inside an attached directory are listed as excluded; an explicit include
  copies one of them; a symbolic link and a special file are listed as not copied.
- **Sabotage:** a build whose preview renders a different frame from the one
  sent (shared with C1), one that silently renames a colliding material, and one
  whose receipt omits a fired check.

### C12 — The run is a handoff

- **Pass:** the receipt carries the reference and the exact run line. Copied
  into a shell in an unrelated directory with a different home, that line runs
  the audit to delivery; `status REF` from a third directory reports the seal,
  verified delivery and still-open closure, and names the destination. The run is
  in the foreground and exits with the run's outcome.
- **Differing:** `run` on a reference that is running, has ended or is closed is
  refused with a sign naming the state and the next command.
- **Invariance:** who invokes `run` and from where changes the record's
  observations (user, process, time) and nothing else; no reply or record names a
  manager role.
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
  mechanism is for design. `run REF`
  continues: the first request of the new conversation carries the continuation
  notice and the same arrangement digest as the first run; the ledger's elements
  are unchanged; the limits reported to the auditor are cumulative across runs;
  the final submission contains every element recorded before the kill exactly
  once; the record holds every run.
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
  no record, reply or return carries a grade, deadline or verdict field, and a
  schema check over every record proves it.
- **Differing:** a refusal of a different kind is recorded with its own reason.
- **Invariance:** the same script with the refused call omitted produces the
  same sealed answer.
- **Sabotage:** a build that drops a refused add without recording it, and one
  that adds an outcome field to the manifest.

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
  output use separate streams, including large and non-text inputs.
- **Sabotage:** a build that reads the live source, one that renders the current
  form in place of the recorded arrangement, and one that treats an intact
  member as proof of whole-commission integrity. Each must fail.

### C16 — Status answers the manager's actual question

- **Pass:** at each independently witnessed lifecycle point, status reports the
  run observation, answer seal/actor, delivery verification/location and closure
  as distinct facts, with the receipt command and any specific next action.
  Human and JSON presentations agree. The test covers a never-run commission,
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

### Platforms

The scripted tier runs, unchanged, on:

- Linux aarch64 and x86_64 in the test image. On the development Mac that means
  a native aarch64 container and an emulated x86_64 one.
- WSL2 natively, through the handoff package: the same binary, driver and fake
  provider, with the home on the WSL filesystem and a destination under `/mnt/`.
  The handoff also checks that a home under `/mnt/` is refused.

Each run records the binary's digest, the image digests or WSL environment
(Windows and WSL versions, distribution, kernel, architecture, filesystem types),
the case counts, the timings and every control that fired.

## The real-model conformance tier

This tier answers C10. It checks procedure, never answer quality.

**Fixed commissions.** Two small commissions live in the apparatus, each with a
known structure:

- a `survey` over a handful of files with one planted fact relevant to the
  question;
- a `claim-check` whose claim rests on three premises, exactly one of which the
  material doesn't support.

Each is sized so that forcing compaction is practical, either through a low
compaction trigger or a run long enough to reach it.

**Runs.** For each model a release supports: each commission three times at the
release's default effort, plus one run with compaction forced and one run killed
midway and continued.

**The gate passes when, for every run:**

- the run ends sealed by the auditor's own submission, not by a limit, a close,
  or a second unsubmitted stop;
- every citation in the answer resolves;
- after compaction, and after a kill and continuation, no element recorded
  before it is added again, and the submission still contains them;
- for `claim-check`, the answer uses the coupling's slots rather than only
  free-form elements.

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
- for the conformance tier, the full recorded conversations.

Bulky material such as conversations and homes at the size limits follows the
project's retention rules for evidence runs. The witness is kept until the run's
results have been reviewed.

## What these tests don't claim

- That answers are good. That's the manager's judgment.
- That read-only investigation is enough. That's research for the experiment tier.
- Anything about the person adapter, which isn't in the first release.
- Anything about a provider's behavior beyond what the conformance gate observed.
