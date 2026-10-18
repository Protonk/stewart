# Close finished audits

Execution plan prepared 2026-10-18 and agreed with the user the same day.

Status: design agreed; no implementation has started. This plan depends on
[REHOME-PLAN.md](REHOME-PLAN.md) steps 1–6, which establish `<common>/stewart/`,
the checkout home, UUID-keyed checkout directories and the lifetime lock. This
document is temporary execution state, not shipped guidance. Update it as work
proceeds; remove it once its contracts have reached the manual, CLI help and
tests.

## Objective

Keep the permanent, append-only record for the life of an audit, not forever.

- **While an audit is live,** receipts stay exactly as they are: exclusive,
  never overwritten, with failures preserved.
- **A new `close` command retires a finished or abandoned audit.** It writes
  one small closing record and removes everything else the session created.
- **An abandoned audit ID can be prepared again** only when Stewart can show
  that no chain of evidence could exist under it.

## Execution contract

Read [AGENTS.md](AGENTS.md) and the actor model in REHOME-PLAN.md before work.
The rehome execution contract applies here too:

- no backward compatibility at 0.1.0;
- preserve unrelated working-tree changes;
- the user approved step 0's harness requests and wheelhouse provisioning on
  2026-10-18; other real harness requests still need approval;
- recheck line numbers, which are given at `76d331c`.

This plan deliberately changes two custody rules, listed under "Rule changes".
Update their statements as facts. Leave the documentation's framing to the
user.

## Ordering

The order across this plan, REHOME-PLAN.md and
[EXIT-CODES-PLAN.md](EXIT-CODES-PLAN.md) is set in EXIT-CODES-PLAN.md under
"Recommended order":

1. EXIT-CODES-PLAN.md part A.
2. REHOME-PLAN.md steps 0–6, with exit-codes part B.
3. Steps 1–5 here, with exit-codes part C in steps 2–3.
4. All together: REHOME-PLAN.md steps 7–8, steps 6–8 here, and exit-codes part
   D. The manual and tests then describe one removal path and one set of exit
   codes.

`LINUX-CONTAINERS-PLAN.md` runs after all three plans.

## Why

A concluded audit's durable outcome has already left Stewart:

- **Retention** writes reviewed files into the working tree for the maintainer
  to commit.
- **`export`** produces self-contained evidence packages. A package carries its
  source receipt and selected bytes, and import verifies those bindings without
  consulting the source session (`handoff.py`, `_package_inputs`).

What stays behind costs attention and storage:

- recorded failures that `status` lists forever;
- audit IDs used up by failed preparations, each forcing a new prompt commit;
- `refs/stewart/sessions/*`, which every auditor's `git log --all` can see;
- role registry rows;
- collection archives inside `.git`.

## Decisions (agreed)

1. **`close` has two modes.**
   - **Concluded:** refuses unless the session has finished its work. That
     means a triage bound to a complete collection, no outstanding paused
     hold, and no unresolved experiment attempt.
   - **`--abandon --reason TEXT`:** any state, including failed preparations,
     abandoned audits and sessions whose records are invalid.
2. **Stewart performs the removal itself.**
   - It removes only what the session's own record names:
     - the session directory;
     - the checkout (unlock, then `git worktree remove`);
     - the supplied and recovered runtimes, and the experiment homes;
     - the session's `refs/stewart/sessions/<uuid>/*`;
     - its role registry row.
   - `close` is the only command that deletes.
3. **One closing record per closed session, kept forever.**
   - Location: `<common>/stewart/closed/<slug>/<audit-id>/<uuid>/`.
   - Written in two phases. `CLOSING.json` is written exclusively before
     anything is removed. `CLOSED.json` is written after removal and records
     what each removal did.
   - Stewart never removes closing records.
   - Fields are grouped by kind, as AGENTS.md requires, so that observations,
     acknowledgments and claims never merge into a verdict:
     - **Identity:** schema, session UUID, workspace and slug, audit ID;
       prompt, target and base commits; digest of `session.json`; prepared and
       closed times; the `stewart` tool identity.
     - **Acknowledged:** who closed it, the mode, and for an abandon the
       reason given.
     - **Observed bindings:**
       - the triage receipt's name and digest, and the collection's name and
         receipt digest;
       - retained paths and digests, taken from the retention receipts;
       - for an abandon, the last observed stage and problem reasons;
       - the release basis from decision 4.
     - **Attributed:** the manager's triage decision text, attributed to its
       actor; the auditor's declared completion and report kind, marked as the
       auditor's claim.
     - **Removal inventory:** every path, ref and registry row to be removed.
   - Kept out: report bytes, patches, full inventories and auditor prose.
     Anything worth keeping beyond the record goes through `export` before
     `close`.
4. **Abandoned audit IDs are released only under a narrow, mechanical rule.**
   - The release needs no statement from the manager. Every check below must
     pass:
     1. **A failure receipt exists.** `PREPARE-ERROR.json` is the positive
        evidence of failure. A missing handoff alone is not enough, because a
        running or crashed `prepare` looks the same.
     2. **Neither handoff file exists.** Check both the private `LAUNCH.md` and
        the public handoff file. Check the files themselves, not only the
        recorded stage.
     3. **No activity records.** The session has no launch records, no harness
        exit record and no collections.
     4. **The checkout holds only `prepare`'s own footprint,** if a checkout was
        created.
        - `close` runs the same no-follow inventory `collect` uses.
        - It compares the result with the footprint derived from the session
          record: supplemental inputs and their digests, the report's parent
          directory, the notes directory.
        - Any extra entry blocks the release.
   - The handoff is the only auditor-facing carrier of the launch token.
     Collection checks the declared token against the session's
     (`session_declaration_expectations`). Without the handoff, no declaration
     can validate, so no chain of evidence can form.
   - **3b:** a released ID may be prepared again from any prompt commit that
     carries it.
   - **Fail closed:** every uncertainty keeps the ID reserved. That includes a
     crashed `prepare` with no failure receipt, an unreadable or unsupported
     record, a misjudged footprint and an unexpected file. The worst case is
     today's behavior: a fresh ID and a new prompt commit.
5. **Issuance stays inside `prepare` for now.** A successfully prepared session
   that is later abandoned keeps its ID reserved. Splitting handoff issuance
   out of `prepare` would extend release to those sessions. That split is
   deferred until prepared-but-never-launched abandonment turns out to be
   common. If adopted, issuance and `close` would compete to create one
   exclusive file in the session, so exactly one wins.

### Details added while writing this plan (veto any)

- **A concluded close refuses if the checkout changed since the triaged
  collection.**
  - It compares a fresh inventory with that collection's.
  - Its next steps are to collect again, or to abandon.
  - This keeps a fallible auditor's late writes from being deleted unseen.
- **An abandon whose checkout holds uncollected changes refuses unless
  `--discard-uncollected` is given.** `CLOSING.json` then lists the discarded
  paths and their digests.
- **Unrecorded entries in the per-audit checkout directory are left in place.**
  `close` removes recorded members, then the directory only if it is empty.
  Anything unrecorded is named in `CLOSED.json` and in `status`.

## Rule changes

| Rule | Now | After this plan |
|---|---|---|
| Recovery preserves failure | A failed preparation keeps its session forever (`AGENTS.md:83`) | Failure is preserved while the audit is live. `close` is the only deletion, explicit and gated. |
| Stewart deletes no worktree | `MAINTAINER.md:20`, `cli.py:61`, `README.md:9` | Only `close` deletes, and only what its session recorded. |
| No automatic ref cleanup | `README.md:149` | `close` removes the session's refs. Nothing else does. |
| Registry rows are not automatically removed | `README.md:132` | `close` removes the session's row. Nothing else does. |

Receipts remain exclusive. Live records are never rewritten.

## Sequence

### 1. Closing record and its single validator

- Define the `CLOSING.json` and `CLOSED.json` schemas, written with
  `write_receipt` and parsed only with `loads_control`.
- Write one function that decides whether an ID is releasable from a session's
  observations. The same function re-validates the recorded basis whenever
  `init` or `prepare` reads a closing record, so close and reuse cannot
  disagree.

### 2. `close`, concluded mode

- Check the preconditions from decision 1 and the unchanged-checkout check.
  Each refusal gets a stable reason, retained paths and next steps.
- Write `CLOSING.json`. Then remove the inventory in this order:
  1. auditor-facing items first, so no auditor can continue: unlock and
     remove the checkout, then the runtimes and experiment homes;
  2. refs, deleted with an expected old value (`git update-ref -d`, through
     `_git.py`);
  3. the registry row;
  4. the session directory last.
- Write `CLOSED.json` with each item's outcome.
- Exit codes follow EXIT-CODES-PLAN.md part C. In particular, a concluded close
  refuses with 3 wherever `status` would return 3.
- A rerun after interruption works only from `CLOSING.json`'s inventory and
  never widens it.

### 3. `close --abandon`

- Allowed in any state, including invalid records.
- Compute the release basis (decision 4), apply the `--discard-uncollected`
  guard, and record both in `CLOSING.json`.
- A paused-mode session's close releases no writer hold. Its output says to
  tell the writers, as `resume` does.

### 4. Freshness checks in `init` and `prepare`

- Today these checks are `assignment.py:339-343` and `prepare.py:107-114`.
  They also read every closing record under the audit ID.
- Reuse is allowed only if every record there is complete and released. Each
  of these refuses with a stable reason that names the record:
  - a concluded record;
  - an abandoned record whose release failed;
  - a malformed or unsupported record.
- An incomplete close (`CLOSING.json` without `CLOSED.json`) refuses until
  `close` finishes.
- Exclusive session-directory creation keeps two concurrent prepares from both
  reusing the ID.

### 5. Status

- **A closed audit ID** shows a closed view instead of a refusal: closed when
  and by whom, the mode, the decision or reason, and what was retained.
- **Earlier abandoned attempts** are listed beside a live session for the same
  ID.
- **An incomplete close** is reported, with the rerun offered.
- **Order of lookup:** closed records are consulted before rehome step 6's
  missing-records logic.
- **Next actions:**
  - A concluded session is offered `close`.
  - A failed preparation is offered `close --abandon`, and re-preparation when
    the ID would be released.
- **Failed preparation's next step:** replace "initialize a fresh audit ID…
  cannot be retried in place" (`prepare.py:216-219`) to match.
- **The session listing** (rehome decision 14) includes closed audits.

### 6. Documentation and help

- **AGENTS.md:** the "Recovery preserves failure" rule, restated as fact.
- **`src/stewart/resources/README.md`:**
  - the statements in the rule-changes table;
  - Failure and interruption recovery (the preparation-failure paragraph,
    around line 806);
  - Records;
  - Coverage and limits: what `close` removes, what it keeps, and that
    `export` must precede it for anything else.
- **`MAINTAINER.md:20`** and the top-level CLI description (`cli.py:61`).
- **`close` help.** It states the two modes, the release rule, and that
  closing records are never removed.

### 7. Tests

Each test has a firing control, a case that differs in the measured property,
and an invariance case:

- **Concluded close.**
  - Measured: exactly the recorded paths, refs and row are removed.
  - Control: an unrecorded file in the checkout directory is left in place and
    named.
  - Control: another live session's refs and row are intact.
  - Invariance: repeated `status` on the closed ID gives the same view.
- **Unchanged-checkout check.** Measured: a file written after the triaged
  collection makes the concluded close refuse. Control: an unchanged checkout
  closes.
- **Interrupted close.**
  - Measured: failing after `CLOSING.json` is reported as close incomplete,
    and a rerun finishes from the recorded inventory.
  - Control: an entry added beside the recorded items after interruption is
    not removed.
- **Release rule.**
  - Control: a failure at the worktree stage with a clean checkout releases
    the ID, and preparing it again from a different prompt commit succeeds
    (3b).
  - Measured: each blocker alone keeps the ID reserved, and `prepare` refuses
    with the stable reason. The blockers:
    - `LAUNCH.md` present;
    - the public handoff present;
    - a launch record;
    - a harness exit record;
    - a collection;
    - an extra file in the checkout;
    - no `PREPARE-ERROR.json`.
  - Invariance: a concluded close always reserves the ID.
- **Fail closed.** A malformed or unsupported closing record refuses reuse, and
  so does an incomplete close.
- **Concurrent reuse.** Two prepares racing on a released ID: one wins.
- **Discard guard.**
  - Measured: abandoning with uncollected changes refuses without
    `--discard-uncollected`.
  - Control: with the flag, `CLOSING.json` lists the discarded paths.
- **Paused mode.** The close output names writer coordination and records no
  hold release.

### 8. Checks

Run with REHOME-PLAN.md step 8: unfiltered `scripts/check.py` on Python 3.11
and 3.14, with actual counts reported and outputs preserved.

## Open questions

- **Session listing:** show closed audits by default, or behind a flag.
- **Live retained-digest check:** whether the closed view compares each
  retained path in the working tree with its recorded digest. That would be an
  observation, not a verdict.
- **Issuance split** (decision 5): revisit if prepared-but-never-launched
  abandonment turns out to be common.

## Completion

Done when:

- steps 1–8 meet the contracts above;
- the manual, help and tests carry those contracts;
- full unfiltered checks pass on both interpreters, with the counts reported.

Then remove this file.
