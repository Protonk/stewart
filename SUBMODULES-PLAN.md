# Submodule support plan

Status: not started. Pending work for a later date; nothing here is decided.
Remove this file once its outcome reaches documentation and tests.

## Where things stand

Stewart neither populates nor audits submodules. `init` warns when the
target commit holds gitlinks (mode `160000` tree entries), and `prepare`
refuses such a prompt commit (`submodules_present`) until
`--submodules-acknowledged`. The session records the gitlink paths and the
acknowledgment, the handoff lists the paths, and `status` keeps an
outstanding line. Collection archives every regular file and link that
Stewart's own walk finds but Git neither tracks nor reports, and names
anything below a gitlink path with a `gitlink_contents` gap. Close counts
those files as uncollected. See the README's "Submodules" item under
"Coverage and limits", `prepare.py` (`_prepare`, `_render_handoff`),
`collect.py` (`checkout_state`, `_walk`, `custody_gaps`) and
`tests/test_submodules.py`.

## Work to carry out later

1. **Reading submodule code.** Auditors cannot read a submodule's files: its
   path is an empty directory in their checkout. Make that code available
   to read, at the commit the prompt commit records.
2. **Working in populated submodules.** Audits cannot run in a checkout with
   populated submodules under the same custody guarantees as the top-level
   checkout. Provide that, or establish that it should not be provided.

## Constraints that apply

- The custody rules in `AGENTS.md`, among them: never follow a link the
  auditor could have planted; receipts are exclusive; freeze what was judged
  and revalidate it at use; removal is authorized only by the recorded
  closing record or claim.
- Inspecting a checkout must never execute code from it. Submodule
  configuration is repository configuration (see `TEST-SPEED-FINDINGS.md`,
  "Correctness problems found by this work, not fixed", item 1).
- Retention keeps the commits a session depends on reachable; a submodule's
  commits live in another repository.
- The auditor harness settings deny writes to Git administration and network
  access; real enforcement of those settings has not been qualified.
- Every guarantee needs a regression with a firing control, a case differing
  in the measured property and an invariance case; real harness enforcement
  is qualified separately from settings construction.

## Questions to answer before choosing an approach

- Which audits need submodule code, and whether reading alone is enough.
- Where the submodule objects come from, and what happens when they are
  missing locally.
- What the auditor may write inside a submodule path, and how collection,
  check, close and status should treat it.
- How a recorded submodule commit is retained, verified and released.
- What changes for sessions prepared before the change.
