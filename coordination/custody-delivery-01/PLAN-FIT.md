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

As assessed before the user's answers; the responses below record what changed.

1. **Access route (A1, B2, B8, B13; critic: platform).** The leg must qualify its
   own access boundary although launch is excluded. Allowing tool-mediated edits
   while denying the auditor direct custody mutation needs an enforcement
   arrangement around the auditor process and a tool that holds authority the
   auditor lacks, the same arrangement launch would select. No route probe has run
   ([routes FINDINGS](../successor-inquiry-01/routes/attempt-01/FINDINGS.md) P1–P3, not executed); custodian component, threat scope and
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

## User responses, 2026-10-28 UTC

Recorded from the user's reply; wording condensed, meaning preserved.

- **Linux route:** set up a Linux container together with Apple's `container`
  tool; it may need installing plus further installs. Observed: this host is
  macOS 26.7.1 on arm64. A container on this Mac gives a real Linux kernel; it
  does not by itself cover x86_64 or WSL. The user later installed `container`
  1.6.1 and corrected the purpose: the Linux work checks that Stewart works on
  Linux, not auditor containment. The first Linux run is recorded in the
  coordinator account.
- **1 Access route:** settle together, write it down and agree on it. That agreed
  document also settles how many Stewart auditors (product participants) trials use.
- **2 Answer structure:** the user needed it elaborated; root's
  [proposal](ANSWER-STRUCTURE.md) was then approved in full, with arbitrary
  bounds to be checked by a much later real-project audit. Recorded in CONTRACTS.
- **3 Delivery trigger:** discuss and design it, aiming to make things easier.
- **4 Specimens only:** accepted. Leg-1 audits are development/acceptance
  specimens until the service can launch and close.
- **5 Re-entry:** accepted. A continuing auditor can find out what happened to an
  interrupted operation or return to the submission tool after compaction;
  otherwise the manager collects.
- **6 Unknown-selection deferral:** the user first needed to know whether the
  condition could be avoided entirely; root's account below was then accepted.
- **7 Capacity:** “1 or 2 auditors” meant development sub-agents; the previous
  review shape was fine. Root may establish its own workflows dynamically within
  a rough ceiling of ten simultaneous agents. Claude CLI/SDK sessions as product
  participants are not granted by this; their number belongs in the item-1 document.

Root opened discussion with item 6. Root's position, accepted by the user as
recorded after it: the condition cannot be avoided entirely, because it means every
trustworthy copy of the small selection record (element identities, names,
digests, order) is gone, and no design recovers a record with no surviving copy.
It can be removed from every ordinary path and confined to destruction or
tampering of Stewart's own records:

- atomic edits/seal and same-operation accounting already keep interruptions,
  lost replies and submit/collect races from producing it (prototype mechanism
  evidence only);
- after seal, deliver the sealed manifest to the manager's independent
  destination before any bytes, and return it or its digest in the seal reply;
  later custody damage then yields known missing members, which already has an
  accepted close direction;
- during authoring, keep two independent self-verifying derivations of current
  membership inside custody (immutable membership revisions plus operation
  records naming element identity and digest);
- enforced auditor access (item 1) removes the likeliest cause of destroyed
  records, an auditor shell touching custody. This point depends on item 1,
  which remains open.

The open policy would then narrow to what close does after Stewart's own custody
records are destroyed or tampered with. It does not block leg 1, whose audits
are specimens and remove nothing.

**User response:** comfortable with this; it is plausible, and more disciplined
manager/auditor access cannot avoid the residue. `close` could then be the
manager's recourse for a damaged audit; the user would like `close` to be the
answer whenever the manager wants the audit closed, regardless of state,
recognizing that this is hard to effect. Agreed for leg 1: the three avoidance
mechanisms become acceptance cases; the narrowed destroyed-custody policy goes
to the close leg, framed as close's behavior on a damaged audit (consistent with
VISION's single close from any state). Item 3 starts from delivering the sealed
manifest to the manager's destination at seal time.

## Items 1 and 3: conversation in progress

The threat-model and enclosure discussion behind item 1 is unfinished. The user
asked to talk it through rather than have conclusions recorded, so nothing is
settled beyond CONTRACTS (notably “Access through explicit grants” and
“Auditor-facing signs and re-entry”). The agreed item-1 document also fixes how
many Stewart auditors trials use and answers [AUDITOR-CASES](AUDITOR-CASES.md)
Q14 and Q27–Q31. Item 3 starts from delivering the sealed manifest to the
manager's destination at seal time; C's request has no destination field yet.
Route facts for both are in `.scratch/route-research-01/RETURN.json` (local),
partly framed around the since-corrected containment purpose.

The user's own words from that conversation, carried from the 2026-10-28 turnover
brief as inputs for continuing it, not conclusions:

- “We consider the manager and auditor to be cooperative but fallible and
  potentially accelerated by eager and persistent agents. The agent's shell can
  do anything the user can and we should expect bored or confused auditors or
  managers to attempt things that seem silly or improbable in retrospect.”
- “… the goal of this adversarial containment is to harden and lubricate normal
  operations. If I'm operating stewart and an auditor escapes and draws
  conclusions from material not supplied I'll be mad and consider that a failure
  of our design but I don't want us to act as though a safety barrier has been
  breached. I think there's some hard to reach keyhole we can thread where we
  make the most obvious, the easiest, and the safest thing to do be the same
  thing: interact with stewart.”
- “One thing we should consider is that containerization might be a temporary,
  contingent move. I'd really love to be able to load up an agent, acclimate it
  to the auditor role, place it in a space where much aside from the materials
  needed to answer the question is absent, and be ok with it.”
- A hypothesis the user has not verified but started Stewart around: “limiting
  attention might improve focus on the question at hand.”
- “‘The manager side is the harder mirror’ YES. But also there's less that they
  can damage that we are responsible for. … However their TOOL they interact with
  is more complex than the auditor's and we still want it to fail early and in an
  informative way.”

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
   allowlist and inputs), WSL handoff, W18 guide statuses. The Linux route is
   located and a first run recorded. Needs no
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
