# Follow-ups from the rehome, close and exit-code plans

Note written 2026-10-18 when REHOME-PLAN.md, CLOSE-PLAN.md and
EXIT-CODES-PLAN.md were completed and removed. Their contracts now live in the
manual, the CLI help and the tests; the plans remain in Git history (last at
the commit before their removal). This note keeps the questions they left open
and the limits found while finishing them. Remove it once each item is handled
or dropped.

`LINUX-CONTAINERS-PLAN.md` runs next; its articulation is left to the manager
of that plan.

## Open questions carried from the plans

- **Live retained-digest check** (close). Should the closed view compare each
  retained path in the working tree with its recorded digest? That would be an
  observation, not a verdict.
- **Issuance split** (close decision 5). A successfully prepared session that
  is later abandoned keeps its audit ID reserved. Splitting handoff issuance
  out of `prepare` would let those IDs be released. Revisit if
  prepared-but-never-launched abandonment turns out to be common.
- **Acceptance record** (exit codes). Should an accepting `check` write a
  digest of the checkout's contents beside the declaration, so `collect` can
  report "exactly what the auditor's tool accepted" or "changed after
  acceptance"?
- **Handoff integrity in `check`** (exit codes). An edited handoff whose
  identity lines are intact gives `check` 0 and `collect` 3
  (`handoff_changed`). `check` cannot see the pinned digest. Making the handoff
  read-only at preparation would let the auditor's tools notice.

## Decisions taken while finishing, worth a second look

- **`prepare_failed` exits 2** although the failed session is kept. The reason
  table maps every refusal to 2 or 3 (exit codes A1), while code 2 is described
  as "nothing was done". The manual states the exception.
- **`close` is offered only when nothing else is pending** (no retention,
  release or run action) and a fresh inventory equals the triaged
  collection's, so pasting it never removes bytes another offered action
  needs. `close` itself accepts the plan's preconditions without that extra
  condition.
- **Removal stops at the first failure.** The session's own records are removed
  only after everything else is gone; a rerun resumes from `CLOSING.json`.
- **A session whose owning maintainer checkout is gone** is refused with
  `session_owner_missing`. Recreating a linked worktree at the recorded path
  restores it; any maintainer of the repository may abandon it meanwhile.
  Collection still goes through the owner.

## Review items not acted on

From the final adversarial review of `close`; each was judged lower risk than
the defects fixed in the same pass.

- **No lock between unkeyed concurrent closes, or between close and prepare.**
  An unkeyed rerun resumes any incomplete close, including one still running
  elsewhere. Exclusive record creation keeps the records consistent, but two
  removals could interleave. Keyed closes hold their request's lock, resource
  claims are exclusive, and an active claim refuses a prepare that would use the
  claimed resource.
- **A blind discard removes a replacement at the recorded worktree path.**
  Removal now runs through descriptors pinned from the filesystem root and
  keeps a checkout that changed after the close was planned, but an abandon
  that authorized discarding unobservable changes (`discarded: null`) has no
  list to compare, so a real directory substituted at the session's own
  UUID-named path is removed with it.
- **One problem classifier is shared by status and a concluded close only.**
  `triage`, `triage-draft`, `resume`, `export` and retention still take their
  codes from the reason table; a refusal on a missing record they expected is
  2 there, while status reports the same record as 3.
- **Status does not predict release before the close.** A failed preparation
  is offered `close --abandon`; whether the ID will be released is known only
  from close's result and the closed view.
- **`close_attempt_unresolved` has no test**, since it needs an experiment
  attempt reserved but never resolved.
- **`validate_scope`** accepts a scope that denies any one entry of the
  maintainer checkout; it has no filesystem access to check the full set.
- **Closing records written before the frozen-plan revalidation** carry no
  extra fields, but a resumed concluded close compares the checkout with the
  triaged collection's receipt still in the session; an older close whose
  session is already gone has nothing left to compare.
- **Two self-named handoff copies.** A copy whose `Handoff file:` line was
  edited to name the copy makes `check` find two handoffs (3) while
  `collect` sees an unexpected path (1).
- **A prepare that crashes before writing `session.json`** leaves an empty
  checkout directory that the later close of that session directory cannot
  name.
- **An unreadable `session.json`** makes close remove every non-symbolic ref
  under the session's namespace, not only the recorded retention refs.

## Known limits

- **Scope is fixed at preparation.** An auditor already launched is not denied
  checkouts prepared later for other audits, or entries added later to the
  maintainer checkout (the manual says so). Re-rendering denials at launch
  would narrow the window for not-yet-launched sessions only.
- **Shared refs.** Linked worktrees share every ref, so an auditor's
  `git log --all` shows other audits' prompt commits and the maintainer's later
  work. Hiding them needs a different checkout mechanism, such as a dedicated
  clone.
- **The custody manual in the handoff.** The auditor handoff points to the
  bundled manual, which is mostly manager operations, followed by "Read only
  the assigned sections". This matters only when an assignment leaves the
  sections unnamed.
- **`--help` deploys into the manager home.** Every `python -m stewart`
  invocation, including `--help`, deploys the selected source. Skipping it for
  `--help` and `docs` would change the bootstrap's run-only-verified-code
  design.
- **The listing's `manager_storage`** names the default checkout home; each
  session's own view names the home it was prepared with.
- **Lost lifetime lock.** Once a checkout directory is deleted, status reports
  `worktree_missing` but not the state of the surviving Git lock.
