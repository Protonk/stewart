# Exit codes and auditor check parity

Execution plan prepared 2026-10-18 and agreed with the user the same day.

Status: design agreed; no implementation has started. This plan interleaves with
[REHOME-PLAN.md](REHOME-PLAN.md) and [CLOSE-PLAN.md](CLOSE-PLAN.md); see
"Recommended order". This document is temporary execution state, not shipped
guidance. Update it as work proceeds; remove it once its contracts have reached
the manual, CLI help and tests.

## Objective

1. **Exit 0 means nothing needs anyone's attention**, for every Stewart command
   on both the manager and auditor sides.
2. **Exit codes ignore what the audit says.**
3. **The auditor's `check` predicts what the manager will see.** When the
   auditor stops after an accepting `check`, collecting that unchanged checkout
   produces nothing attributable to the auditor.

This supersedes the earlier "G" discussion about `status` exit codes.

## Execution contract

Read [AGENTS.md](AGENTS.md) and the actor model in REHOME-PLAN.md first. The
rehome execution contract applies here too:

- no backward compatibility at 0.1.0;
- preserve unrelated working-tree changes;
- the user approved step 0's harness requests and wheelhouse provisioning on
  2026-10-18; other real harness requests still need approval;
- recheck line numbers, which are given at `76d331c`.

This plan shapes incentives. It adds no defense against meddling and no limit
on its impact. Its aim is that every path of least resistance for the auditor
is "use the auditing tool until it accepts".

It relies on behavior already seen in earlier Stewart work: auditors interact
with the tool, receive information back, and send different updates in
response. It does not assume they loop on `check` mechanically, and no
rehearsal is planned.

## The three rules (agreed)

1. **No news is good news.**
   - Exit 0 means nothing needs attention.
   - There is no "succeeded with warnings". Anything worth warning about is
     nonzero.
   - Routine next steps, such as "launch" or "triage", are not news.
2. **Codes ignore what the audit says.** None of these ever changes an exit
   code:
   - declared completion (partial, blocked, complete);
   - report kind (answer, needs-evidence, reframe);
   - report prose;
   - triage's accepted, rejected and unresolved items, and its decision;
   - an experiment child's own exit status, which the manual already keeps out
     of the tool's exit code (`README.md:1332`).

   If "blocked" or "needs-evidence" returned nonzero, the tool would reward
   overclaiming. Whether the audit was done well is triage's call.
3. **The auditor's tool predicts the manager's result.** The auditor's final
   `check` code equals the code the manager will get for everything that
   depends only on the checkout.

## The four codes (agreed)

| Code | Meaning everywhere | Auditor reads it as | Manager reads it as |
|---|---|---|---|
| 0 | Nothing needs attention | Accepted; stop | Proceed |
| 1 | Action needed within your role; each message names the change | Change what's listed, run `check` again | Address the listed items: rerun, or record a decision in triage |
| 2 | Refused; nothing was done | Wrong place or command; reread the handoff | Fix the command or its preconditions |
| 3 | Something you didn't produce doesn't verify | Not yours to fix: note it in the report, declare, stop | Inspect, then recover or abandon |

When both apply, 3 takes precedence over 1. A refusal caused by evidence that
doesn't verify is 3, not 2.

## Recommended order

Work on part A of this plan first, then pause it. Fold its later parts into the
other two plans at the steps that already rewrite the same code:

1. **Phase 1, this plan's part A** (steps A1–A6). It covers the code contract,
   the classification tables, `check` parity, the input verifier and `collect`.
   Doing it first is recommended because:
   - it depends on nothing in the other plans, since gap logic is relative to
     the worktree and storage locations don't affect it;
   - the reason table and its completeness test then exist before the other
     two plans add new reasons, so each new reason is classified when it's
     written rather than in a retrofit;
   - it holds the incentive design's centerpiece, the auditor-facing `check`,
     and settles it early;
   - it is the smallest and least risky of the three.
2. **Phase 2:** REHOME-PLAN.md steps 0–6, with part B (`status` codes) folded
   into rehome step 6. That step rewrites `status` and bumps it to
   `stewart.status/12` anyway.
3. **Phase 3:** CLOSE-PLAN.md steps 1–5, with part C (`close` codes and the
   shared invalid-evidence rule) folded into close steps 2–3.
4. **Phase 4, all together:**
   - REHOME-PLAN.md steps 7–8;
   - CLOSE-PLAN.md steps 6–8;
   - this plan's part D, documentation and the final test pass.

   One pass over the manual then describes the final behavior.

`LINUX-CONTAINERS-PLAN.md` runs after all four phases. Leave any coordination
with it to that plan's manager.

The main alternative is to do rehome first and this plan last. That retrofits
the classification tables onto every reason the other plans add, and delays
the auditor-side change. I recommend against it.

## Classification: what `check` sees, and who can fix it

Every condition gets two independent properties:

- **Observability.** Could the auditor's `check` compute it from the worktree
  and the issued handoff alone? If so, `check` must evaluate it. Partitioning by
  observability rather than by blame means `check` can never miss something
  `collect` would later attribute to the checkout.
- **Fixability.** Can the auditor fix it within its grants?
  - Fixable is code 1, with the fix named.
  - Not fixable is code 3. No meddling can clear a 3, and the message says it
    doesn't count against the report.

The current gap IDs from `custody_gaps` (`collect.py:423`), classified:

- **Observable from the checkout**, so `check` evaluates them:
  - `report_*`: write the report (1).
  - `checkout_commit_changed` and `declaration_stale`: restore HEAD to the
    prompt commit (1).
  - `unexpected_path:*`: move the file under a declared output or remove it
    (1). Classify edits to supplemental inputs separately as 3; see A4.
  - `declaration_missing`, `declaration_invalid:*` and
    `declaration_mismatch:*`, including the launch token once A3 makes it
    checkable: rerun the issued command (1).
  - `unreadable:*`, `unsupported:*`, `omitted:*` and `boundary:*`: classify
    each case during A2, by whether the auditor created and can undo it.
- **Manager-side only**, reported by `collect` and never `check`'s concern:
  - `collection_error:*`;
  - `git_discovery_incomplete`;
  - `movement_detected`, which means the checkout was collected while still
    being written;
  - `completion_stop_discrepancy`, which needs the manager's stop
    acknowledgment.

## Part A (phase 1)

### A1. Code contract and reason table

- **One module owns the codes 0–3.** Each operation computes its code and puts
  it in the result dictionary, so API callers (`api.py`) get the same signal.
  The CLI (`cli.py:37-39`) and the auditor helpers map that code to the
  process exit.
- **`ok` in JSON means `exit_code == 0` everywhere.** Today the CLI envelope
  sets `ok: true` for any returned code (`cli.py:772`), while `verify_inputs`
  uses `code == 0`. Keep `result` present for exits 1 and 3.
- **A reason table maps every refusal reason to 2 or 3.** It covers the CLI,
  the helpers and the bootstrap launcher's own refusals. A changed deployed
  runtime (`runtime_mismatch`), for example, is 3.
  - A completeness test scans the source with `ast` for literal `reason=`
    arguments and fails on any reason missing from the table.
  - The test must also cover problem entries written as plain dicts, such as
    `{"reason": "collection_incomplete"}` and `"exit_log_malformed"` in
    `status.py` (lines 116-129, 256-288, 381, 497). The `reason=` scan misses
    those, and they are exactly what part B classifies. Either scan dict
    literals with a `"reason"` key as well, or create those entries through
    one constructor that the table checks.
  - Reasons added later by REHOME-PLAN.md and CLOSE-PLAN.md must be classified
    when they are written.

### A2. Gap classification and `collect` codes

- Encode the classification above as a table beside `custody_gaps`, with a
  completeness test that triggers every gap family.
- `collect` returns:
  - 0 with no gaps or capture errors;
  - 1 if any recorded gap or error is class 1;
  - 3 if any is class 3, or if it refuses because the session's records don't
    verify;
  - 2 for other refusals.

### A3. `check` parity in the declaration helper

- **What changes:** today the helper returns only 0 or 2 and checks only the
  declaration (`report_declaration.py:385-391`). `check` would also:
  - run a read-only, no-follow inventory and Git discovery of the worktree;
  - build the would-be receipt and run the same `custody_gaps` on it;
  - keep the observable gap IDs and apply fixability;
  - exit 0, 1 or 3, or 2 for refusals.
- **Where the allowed outputs come from:** the prompt metadata already in the
  checkout, so `check` reads nothing private.
- **What each message carries:** the gap ID the manager would see, the fix,
  and the command to rerun.
- **Speed and side effects:** `check` must stay fast and write nothing, apart
  from the optional acceptance record (A6), so checking again after each
  change is the cheapest thing the auditor can do.
- **The launch token:** compare it with the issued handoff file in the
  worktree, since the helper can't verify it today
  (`report_declaration.py:217`). A mismatch is a 1: use the issued command.
- **`start` and `set`:** they keep 0 on success and 2 for refusals. `check`
  is the single place that evaluates the whole checkout.

### A4. Input verifier codes

A failed row exits 1 today (`verify_inputs.py:80`). `prepare` verifies inputs
before handoff, so a later mismatch arose inside the checkout:

- A changed tracked input exits 1, with `git checkout <prompt-commit> --
  <path>` named as the fix.
- A changed supplemental input exits 3. The original bytes are private, so the
  auditor can't restore them.

### A5. Handoff and helper wording

- Add one line to the auditor handoff explaining 0, 1, 2 and 3. Messages from
  the helpers carry the rest.
- REHOME-PLAN.md step 2 later rewrites the handoff's paths and removes its
  manager-facing text (rehome decision 11); keep this line in that rewrite.

### A6. Tests for part A

Each has a firing control, a case that differs in the measured property, and
an invariance case:

- **Parity property test.**
  - Measured: generate checkout states by mutating a clean checkout, then
    compare `check`'s code and gap IDs with what `collect` produces from the
    unchanged checkout for its observable gaps. The mutations:
    - a write inside, and a write outside, the declared outputs;
    - an edited tracked input, and an edited supplemental input;
    - a commit;
    - a FIFO;
    - an unreadable file;
    - a deleted report;
    - a wrong token.
  - Control: a clean checkout gives 0 from both.
- **Codes ignore content.**
  - Measured: every completion value and every report kind, across otherwise
    identical well-formed states.
  - Invariance: `check`, `collect` and `status` codes are identical across all
    of them.
- **Precedence.** 3 wins over 1, and a refusal caused by evidence that doesn't
  verify is 3.
- **`ok` semantics.** `ok` is true exactly when the exit code is 0, for every
  command and helper.
- **No news at 0.** Every exit-0 result has empty problem and gap lists.
- **Completeness tests** for both tables.

## Part B (phase 2, with REHOME-PLAN.md step 6)

`status` returns:

- **0:** records verify and nothing is anomalous.
- **1:** anomalies, each listed:
  - an interrupted or failed operation that is still the latest word: a
    failed preparation, a partial collection with no later complete one, an
    unresolved attempt, an incomplete close;
  - gaps on the latest complete collection that no valid triage has yet
    addressed, each at its class code;
  - a nonzero harness exit with no collection;
  - a different build having written the session;
  - leftovers named by `close`.

  Gaps that a valid triage has addressed are history, not news.
- **3:** records that don't verify. That includes a supplied runtime that no
  longer verifies, an unsupported session schema, and a lost session in the
  listing.
- **2:** refusals, unchanged. That includes targeted status on a registered
  session whose records are missing.

In the session listing (rehome decision 14), the exit code is the highest code
of any live entry. Closed entries never count. `triage-draft` returns 0, 2, or
3 when the collection it binds to doesn't verify.

One function decides "records don't verify". It is shared by `status` and by
every command that refuses on that basis: `triage`, `triage-draft`, `resume`,
`export`, retention and a concluded `close`. AGENTS.md already requires
`status` and mutations to share validation.

## Part C (phase 3, with CLOSE-PLAN.md steps 2–3)

- A concluded `close` refuses with 3 wherever `status` would return 3, using
  the shared function from part B. Abandoning stays available.
- `close` returns 1 if it finished but left named leftovers, or if its removal
  stopped partway. It returns 0 on a clean close.

## Part D (phase 4)

- **Manual exit codes:** rewrite the table at `README.md:1324` around the four
  codes and the three rules.
- **Manual command sections:** update the `status`, `collect` and auditor
  declaration sections.
- **Role templates:** say in `MAINTAINER.md` and the bundled auditor-facing
  guidance what each code asks of that role.
- **CLI help:** name the codes in the CLI epilog and in each helper's `--help`.
- **Final checks:** run with the other plans' final checks, unfiltered on
  Python 3.11 and 3.14, with actual counts reported.

## Open questions

- **Acceptance record.** Should an accepting `check` write a digest of the
  checkout's contents beside the declaration? `collect` could then report
  "exactly what the auditor's tool accepted" or "changed after acceptance",
  giving the manager one clear bit and giving the auditor a reason to make
  `check` the last action. If adopted, the digest must exclude the files
  Stewart itself writes into the checkout, the handoff and the record itself.
  That overlaps the earlier deferred item about classifying the handoff file
  in collections.
- **Handoff integrity.** `status` treats an edited public handoff as
  incomplete preparation. Should `check` also observe whether the handoff is
  unchanged, so the auditor learns of it before the manager does?
- **Classification of `omitted:*` and `boundary:*`.** Settle case by case
  during A2.

## Completion

Done when:

- parts A–D meet the contracts above;
- the manual, help and tests carry those contracts;
- full unfiltered checks pass on both interpreters, with the counts reported.

Then remove this file.
