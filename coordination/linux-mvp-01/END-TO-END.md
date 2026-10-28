# End-to-end tests for the router

What an end-to-end test of [the router](ROUTER.md) has to show, and how. "End to
end" here means from a problem file a manager wrote to a verified return the
manager reads, through the actual release binary, with nothing replaced except
the model provider, and in one tier not even that.

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
manager collect, including:

- a stale handle after an edit, which is refused;
- repeated confirmed submits, which return the same submission;
- submit racing collect, run many times, with exactly one winner each time and
  correct attribution;
- collect on an empty answer, giving an honest empty return;
- the limits on elements and sizes, and the edits that are still allowed at them.

**Interruptions.** The driver kills the binary at fixed points: before an
operation's intent is recorded, after intent and before effect, after effect and
before the outcome is recorded, after the outcome and before the reply, during
seal, and during delivery. The next command must settle each one exactly once,
landed or not, and list it in provenance.

- **Sabotage:** a test build that skips writing the outcome record, and one that
  applies an edit twice on settlement.

### C4 — Compaction is harmless

- **Pass:** the fake emits a compaction block midway. The script then calls
  `what_am_i_working_with`, which returns the question verbatim, the materials
  index, every element recorded so far and any unresolved operation. The script
  continues and submits, and the submission contains the elements recorded before
  compaction exactly once.
- **Differing:** a submission error pending at compaction shows up in
  `what_am_i_working_with`.
- **Invariance:** the same run without compaction produces the same sealed answer.
- **Sabotage:** a build whose re-entry reply omits the current answer.

### C5 — The return is complete and faithful

- **Pass:** the driver compares each delivered return against its witness: the
  question, the receipt's material digests, every element's bytes and order, the
  account marker, and who sealed it. The manifest digest printed at seal equals
  the delivered one.
- **Also:**
  - a delivery interrupted partway keeps its partial directory and names the
    missing members, and the next `deliver` produces a complete copy;
  - a payload corrupted in Stewart's storage before delivery is reported as
    damage, never delivered as good, never treated as absent from the answer;
  - an unknown membership is never delivered as an empty answer.
- **Sabotage:** a build that drops the last element, and one that writes the
  manifest after the members.

### C6 — The record is honest

- **Pass:** an inventory of Stewart's home before and after every command shows
  only additions: no file is rewritten and none removed, through to and after
  close. The access log equals the sequence of read, list and search calls in the
  script. The run summary's turns and usage equal what the fake reported.
- **Sabotage:** a build that rewrites a record in place, and one that skips logging
  a search.

### C7 — Couplings

- **Pass:** for `survey` and `claim-check`, the frame contains the manager's
  question verbatim and the coupling's wrapper. The slots appear as tools. Filled
  slots render in the return as the coupling specifies.
- **Citations:** a citation to real lines passes. One off by a line, one naming a
  missing material, and one quoting text that isn't there are each refused with a
  sign and never recorded as valid.
- **Exits:** *wrong question*, *missing evidence* and *nothing found* each seal and
  deliver like any other answer.
- **Prior:** `claim-check` shows the manager's claim. A coupling that seals the
  prior keeps it out of every request and delivers it only in the return.
- **Sabotage:** a build that paraphrases the question, and one that accepts an
  off-by-one citation.

### C8 — Close from every state

Close runs against each state: commissioned, running (live loop), ended, sealed,
delivered, partially delivered, damaged storage and already closed. Each one
reaches the documented outcome: stop, collect, deliver, report, wait for
confirmation, record. None of them removes anything (checked by the C6
inventory). Confirming with a missing member requires naming the undertaking
being given up.

### C9 — Quick, and sure of what it says

- **Response budgets**, measured in the test image on material at the size
  limits and reported as actual timings:
  - startup, `status`, `preview` and `help` answer within tens of milliseconds;
  - every protocol call except a full-material search does too;
  - intake, full search and delivery state their size first and report progress.
- **Certainty:** every protocol reply begins with the header line. Every refusal
  carries a reason, its effect and the next call. Every manager command's JSON
  output carries what changed and what was verified. A schema check runs over
  every reply the suite produces.
- **Sabotage:** a build with an injected delay in one protocol call, and one that
  omits the effect line on one refusal.

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
release's default effort, plus one run with compaction forced.

**The gate passes when, for every run:**

- the run ends sealed by the auditor's own submission, not by a limit, a collect,
  or a second unsubmitted stop;
- every citation in the answer resolves;
- after compaction, no element recorded before it is added again, and the
  submission still contains them;
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
