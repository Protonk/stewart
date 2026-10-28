# Plan fit of the approved custody-and-delivery leg

Coordinator assessment, 2026-10-28 UTC, from source `f987a78`. The user approved
the [NEXT-LEG candidate](../submission-design-01/NEXT-LEG.md) as the first leg,
hopes to continue through the remainder of the transition, set the first leg's
capacity at one or two agents and asked whether the assignment makes sense
against the development and vision plans. Nothing is dispatched by this note;
collaboration setup continues.

Evidence: a read-only in-harness review (`wf_bdadff4a-f82`; two lens reviewers,
then one adversarial verifier; at most two concurrent) returned 28 findings,
of which the verifier confirmed 24 and marked 4 overstated (A12, A14, B14 and one
B2 citation), and added four missing points. Root spot-checked the weightiest
citations. Brief and full structured returns: `.scratch/plan-fit-review-01/`
(local, untracked). Finding IDs below refer to that return.

## Conclusion

The assignment makes sense in direction. DEVELOPMENT-PLAN's F3/F5 paragraph
expressly permits a bounded custody/delivery leg before live launch/control;
every promise the leg makes is already decided in CONTRACTS (B1); the
preparation audit found no forced stop/removal dependency; and a one-or-two
agent shape fits, because most of the leg is single-owner shared foundation
and serial interruption testing (A11). The later 4–10 agent fan-out fits F5's
operation legs once that foundation is integrated (A7).

It is not dispatch-ready. The plan requires decisions the candidate does not
yet carry. The consequential ones belong to the user; the rest are coordinator
reconciliation.

## Decisions for the user

1. **Access route (A1, B2, B8, B13; critic: platform).** The leg must qualify its
   own access boundary although launch is excluded. Allowing tool-mediated edits
   while denying the auditor direct custody mutation needs an enforcement
   arrangement around the auditor process and a tool that holds authority the
   auditor lacks, the same arrangement launch would select. No route probe has run
   (routes FINDINGS P1–P3, not executed); custodian component, threat scope and
   host classes are open user choices; a container route may exclude native macOS
   and so bears on the stage-4 platform exit. Root's recommendation: settle the
   route before fixing the write path, informed by a bounded P1-style probe
   extended with the tool-may-write/auditor-may-not case. That probe needs
   explicit permission for real auditor-harness sessions. Without it, the leg
   must end with access stated as an unqualified limit and return the scope issue.
2. **Provisional answer structure (A2, B6).** The plan's decision point "before
   the durable submission interface" (DEVELOPMENT-PLAN §4 answer protocol) is
   untaken; NEXT-LEG calls schema an implementation choice. Root recommends a
   content-neutral provisional container: ordered, named, opaque elements with
   mechanical metadata only, no outcome discriminator or per-question-type
   required field, with empty, reframed, blocked and no-finding content admitted
   identically; explicit payload bounds and unsupported capabilities.
3. **Delivery trigger and destination binding (B5, A9).** Push to the
   commissioning-time destination versus a manager pull has access and
   manager-step consequences. C's request has no destination field: bind at audit
   creation or version C's request. CONTRACTS' older "Delivery: Deferred" clause
   needs reconciling with the 2026-10-27 manager-receipt direction.
4. **Leg-1 audits as specimens or real use (A6, B7; critic: real-use path).**
   Leg 1 has no input preparation or launch, so a real audit would need frozen
   Python or an outside environment. Its records are writer-pinned and cannot
   close until F6; replacing that writer with unresolved selection would trigger
   the W14 conditional review. Root recommends development/acceptance specimens
   only until the service can launch and close.
5. **Auditor re-entry scope (B3, B4).** Root recommends same-operation accounting
   for a continuing participant only; loss of the whole auditor is handled by
   manager collect; no other execution continues authoring. This keeps zero restart
   facilities; the restart choice remains the user's.
6. **Item 3 interim deferral (A13).** Confirm the approval covers retaining
   material and leaving close unfinished for unverifiable selection scope.
7. **Capacity and launch permission (critic).** Clarify whether "auditors" meant
   development sub-agents or Stewart auditor participants in trials. In-harness
   sub-agents are this harness's dispatch facility; a CLI/SDK Claude session as a
   product participant still needs explicit bounded permission and usage headroom.

## Coordinator reconciliation before a commission

- W-row disposition table: W02/W05/W07/W09/W11/W12 split into leg-1 part and
  remainder; W03/W04/W06/W08/W10/W13/W14/W17 not undertaken, with prerequisites;
  W15/W16 subsets the leg must own (implementation identity before allocation;
  Git policy only if custody location touches Git); W18/W20 surfaces (A3, A8).
- Custody home: location, protection, explicit locator, move/backup behavior
  (refusal naming the recorded path versus move-surviving records) and
  nested/unrelated-path cases (A4, B11). Move behavior is a promise; bring it to
  the user with a recommendation.
- Status consumer (interrupted manager), record population (leg-1 records only)
  and discovery scope; status infers no auditor activity from authoring records;
  outcome replies are not the deferred capture receipt (A5, B9).
- Shared identity/request/record/error/copy contracts as single-owner foundation
  deliverables, packaging choice and hold-compatible copy identity (A7).
- Dispositions for collect stop note, manager-declared return arrangement and
  holds; split access acceptance into auditor-side and manager-side cases and the
  fresh-manager case into re-entry and source independence (B8, B10, B12).
- Carry the conditional review's continuing conditions into acceptance: explicit
  finite selection, no claim that it covers the whole workspace, material held,
  uncertainty visible, close unfinished (critic).
- Reconcile stale or older ordering text: NEXT-LEG status, DEVELOPMENT-PLAN
  candidate wording, W07 timing, "write path waits for A.1 and B–F",
  "before commissioning the write path", status-first ordering (A8, B13, B14).
- Schedule the failure-table sanity check before fixing the write protocol;
  a Riker consultation remains optional.

## Remainder of the transition (outline)

1. Early independent preparation: W17 read-only inventory (needs the user's
   allowlist and inputs), Linux route, WSL handoff, W18 guide statuses. Needs no
   Claude launch; concurrent work would exceed the first leg's capacity unless agreed.
2. F2 route evidence: P1 grants, P2 control after launcher loss, P3 manager
   restriction/recovery; serial harness sessions with explicit permission.
3. F3 connected design for the full service (W03/W04/W05/W06/W07/W08/W10/W13/W15/W16;
   stage-4 versus stage-5 classification; scoped clause-to-acceptance map).
   Human-auditor accommodation is decided, not optional.
4. F5 shared-foundation extension, single owner; then operation legs in the
   plan's order, where 4–10 agents fit on exclusive files.
5. F6 close last, opening with W17's gate: stop admitting Python audits,
   including development's own, and close live ones under Python.
6. F7 platform acceptance (macOS, Linux, actual WSL), documentation, legacy
   settlement, explicit outcome for every register item.
