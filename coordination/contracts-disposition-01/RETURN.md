# Disposition of CONTRACTS under the 2026-10-28 design

Reviewer: a fresh-eyes worker who was not party to the 2026-10-28 conversation.
Source: `CONTRACTS.md` at `7e49301` (verified byte-identical at HEAD `5bebe98`,
which adds only the brief). Line numbers below are at that revision.

Every recommendation in this document is the reviewer's. The user decides; the
coordinator integrates.

## How to read the source tags

Each reason says what kind of statement it rests on:

- **[D]** a user decision recorded in CONTRACTS (line cited).
- **[P]** a coordinator proposal in `ROUTER.md` (R) or `END-TO-END.md` (E), not
  separately decided (line cited).
- **[R]** an item in `RESERVATIONS.md`.
- **[C]** the user's own quoted words in `CONVERSATION.md` (turn cited). Three of
  the decisions this review relies on, Linux only, no Git, no Python baseline,
  are recorded only there (turn 5: "R8 I basically agree with full stop. R7 has
  been BOTHERING me. R6 is perfectly pleasing ... R2 I want 100%") and in the
  brief; CONTRACTS states them only as the Mission's framing (37–41). See §2.13.

Dispositions, as the brief defines them: **Carry** holds as written; **Restate**
holds in spirit but is phrased for Git, the checkout, Python or removal;
**Retire** depends on something the decisions removed; **Undecided** needs the
user. Where a paragraph's subject no longer exists I mark Retire and name any
sentence that should survive elsewhere; where the subject exists but the words
do not fit, Restate.

Rows marked *(extra)* are beyond the brief's required set (headings, and bold
titles in Principles, the successor sections and Close). I added them for the
`####` sub-headings of the status contract, the bold titles in three other
sections, the untitled preamble, and the fourteen Declined entries, because each
carries a reason that would otherwise be dropped unexamined. §4 reconciles the
counts.

## 1. Table

| # | Location (lines at `7e49301`) | Disposition | Reason |
| --- | --- | --- | --- |
| 1 | *(extra)* Preamble: title, status markers, "The Python implementation is the reference baseline" (1–33) | **Restate** | The reference-baseline sentence (27) and the Python-keyed markers are reversed by no-Python-baseline [C t5]; markers need a legend without a Python control; the findings citations at `356dc58` stay as historical citations. |
| 2 | `## Mission` (35) | **Carry** | The user's words [D 43–58]; everything else is read under it. |
| 3 | `## Principles` (60) | **Restate** | Heading and preface hold; several principles below are phrased for removal at close, which the decided text no longer presumes and ROUTER proposes to abolish [P R361]. |
| 4 | Stewart acts only on what was judged (65) | **Undecided** | It authorizes removal of what a closing evaluation judged; whether close removes anything is a proposal never confirmed [P R361; R13]. Never-delete retires it; any removal of an audit directory brings it back as written. |
| 5 | Refusals are limited to Stewart's own claims, acts and obligations (71) | **Restate** | The three grounds and "a refusal whose next step cannot be performed inside Stewart is suspect" carry, realized by "every wall carries a sign" [D 427–429]; the examples (planted link, exclusive destination, destroying material) are checkout/removal-phrased; the right-to-receive clause carries via "status answers whoever holds it" [D 606–607]. |
| 6 | Close offers opportunity, not preservation (89) | **Undecided** | Depends on whether close removes anything [P R361]; "loss despite an undertaking, never a decline" and "regenerability is never a ground" survive regardless, through C5/C8 [P E150–155, E184–192] and 476–487 [D]. |
| 7 | The manager controls what survives by default; requesting close does not cancel undertaken obligations (101) | **Restate** | Retention/export/resource clauses have no referent; what survives: unsubmitted work is sealed and delivered, never discarded [D 594–598]; completed close conceals no unfinished operation; the hold (Undecided, §2.1); the process promises to the auditor, restated at 579–581 [D]. |
| 8 | Liberal in handing over, conservative in destroying (126) | **Restate** | First half carries (verified material with qualifications attached, C5 [P E144–155]); the second half is moot only if nothing is destroyed, which is undecided. |
| 9 | A bounded commission and structured return are the product relationship (131) | **Carry** | Strengthened by "the manager's operations are the receipt, status and close" [D 591–598]; "live inspection is not a product objective" sits against the record being readable by whoever runs Stewart [D 635–636; P R244–245], see §3.2. |
| 10 | Stewart remains agnostic about audits' intellectual utility (143) | **Carry** | Restated in the Mission as never judging conclusions [D 55–58]; its second paragraph's deliberation requirement now bears on the orientation, the two nudges and the citation check, all proposals [P R185–189, R227–228; R1], see §2.15. |
| 11 | Recording a commission does not itself promise replay (160) | **Carry** | Settled in place: no restart convenience; a dead run is continued [D 173–176, 643–659]; `new --like REF` is the manager constructing a new question [P R312]. |
| 12 | Standard commission receipts support manager recall (178) | **Restate** | The receipt is the handoff and the re-entry route [D 600–607, 544–559]; "retained Git", "prompt commit" and the macOS-qualified "Implemented in Rust" status (179, 248) do not fit Linux-only and no-Git [C t5]. |
| 13 | Prefer inexpensive assurance that supports manager judgment (208) | **Carry** | Trap doors with receipts; commission/run split on the network line [D 600–604]. |
| 14 | Incomplete Stewart operations remain Stewart's responsibility to account for (219) | **Carry** | Auditor side becomes "retry; the re-entry call shows what landed" [D 583–589]; manager side continues interrupted delivery and close through close [D 499–505; P E150–152, E184–192]. |
| 15 | Investigative effectiveness and seamless operation are distinct aims (234) | **Carry** | Still a tension; the decided design settles the constrained side by construction (read/search/list only [P R221]); only the non-gating experiment tier evaluates the other [P E47–50; R3]. |
| 16 | `## First successor leg: commission-input acceptance` (246) | **Restate** | The intake promises (acceptance means present and verified; incomplete intake keeps partial bytes and diagnostics; readback never substitutes live sources) carry into `commission` [D 614–629]; "manager-custodied delivery into explicitly designated storage" (258–266) sits against the home layout [P R359–362], see §2.10; the macOS qualification is stale under Linux-only. |
| 17 | `## Successor answer construction and atomic artifact edits` (298) | **Carry** | Add/replace/delete, prepare/submit, no draft stages are the protocol [D 569–589; P R218–224]. |
| 18 | Custody home and edit retention (325) | **Restate** | "Associated with the repository" becomes Stewart's home (no Git [C t5]); "held until authorized closure" depends on the deletion decision; "helper exit and working-environment retirement" has no referent. |
| 19 | The tool integration owns interrupted-operation accounting (339) | **Retire** | Superseded in place by ledger truth [D 583–589]; keep as the reasoning replaced, as the section says. |
| 20 | Normal submission ends editing (364) | **Carry** | Handle, dry-run default, stale handle refused, identical confirmed repeat returns the same submission [P E109–117]; the handle, not equal bytes, identifies the repeat, consistent with 585–586 [D], see §3.8. |
| 21 | Provisional answer structure (390) | **Restate** | Structure and bounds carry [P E117]; "on submit as well as collect" becomes "on submit or manager seal at close" [D 594–596]; "lists it in the return's provenance" (413–414) conflicts with "the return is the submission" [D 631–641], see §3.1. |
| 22 | Auditor-facing signs and re-entry (420) | **Carry** | Signs, absence over denial, no custody paths in auditor replies, stopping as the final door all carry [D 569–589; P R226–228]. The untitled superseded paragraph (435–443) retires except its last sentences: slim help and verbatim question carry [P R220, R339]; "the auditor is not shown the question type" conflicts with the form as the auditor's tool, see §3.3. |
| 23 | `## Successor manager receipt and ordinary closure` (445) | **Carry** | Durable manager-held copy by straightforward copying, delivered at the end of the run and read back [D 594–598; P R293–294]. |
| 24 | Return contents and initial destination (458) | **Restate** | Narrowed in place [D 631–641]; destination chosen at commission carries (`destination` field [P R102, R118]); "further copies may name another destination" is narrowed to close-when-no-verified-copy [D 509–510]. |
| 25 | Empty and partial returns use the same interface (468) | **Carry** | C3 "close on an empty answer" and C5 partial delivery [P E116, E150–155]. |
| 26 | Known-selection incomplete close (476) | **Carry** | C8 "confirming with a missing member requires naming the undertaking being given up" [P E190–191]; "never invent a missing list or infer emptiness" carries via C5 [P E155]. |
| 27 | Close requested before the copy exists (499) | **Carry** | Close delivers when no verified copy exists and continues the same undertaking [D 594–598]. |
| 28 | Manager collect may end authoring (516) | **Restate** | Narrowed in place: the authority is exercised through close [D 517–518]; the no-waiting-period, no-deterrent, no-evaluation-gate clause (530–535) must survive the rewording, since ROUTER does not state it [P R345]. |
| 29 | An interrupted manager re-enters through ordinary help and status (544) | **Carry** | Status takes a reference and answers whoever holds it [D 606–607]; nothing selected by recency; "repository or custody scope" (548–549) reads as inquiry scope [D 591–593]. |
| 30 | `## Successor interfaces decided 2026-10-28` (561) | **Carry** | The decisions [D]. |
| 31 | The auditor's tool is a form and a ledger (569) | **Carry** | [D]; the process promises to the auditor are restated here (579–581). |
| 32 | Ledger truth (583) | **Carry** | [D]; tested by C3 interruptions [P E119–128]. |
| 33 | The manager's unit is the inquiry (591) | **Carry** | [D]; note it says close "records the end", not that anything is removed, so it decides neither way on deletion. |
| 34 | The escalated run (600) | **Carry** | [D]; tested by C12 [P E234–249]. |
| 35 | The problem file and material acceptance (614) | **Carry** | [D]; tested by C11 [P E208–232]. |
| 36 | The return is the submission (631) | **Carry** | [D]; tested by C5 [P E142–158]; see §3.1 (provenance) and §3.4 (rendered answer). |
| 37 | An audit is its ledger; a run is one placement (643) | **Carry** | [D]; tested by C13 [P E251–267]. |
| 38 | `## Handoff and audit-owned facilities` (661) | **Restate** | "Later manager edits must not silently alter what the auditor was commissioned to investigate" carries (material copied at commission [D 600–602]); "manager access to live material very restricted" (664–666) sits against the readable record [D 635–636], see §3.2; the independent-workspace clause (672–675) has no referent, §2.3; "a working opportunity through a supported interface" is close's delivery. |
| 39 | `## Access through explicit grants` (687) | **Restate** | Realized by construction for the model adapter: the auditor's world is the tool list [C t5 R2; P R47–49, E76–90]; inventory fallback and harness/shell qualification (702–707) have no referent; the person adapter's enforcement is "by agreement" [P R247–249; R11] and is not in the first release. |
| 40 | `## General manager-workspace service` (712) | **Retire** | No Git, no worktrees; material is copied; the Python resource-transition paragraph (729–737) moves to the legacy-records question, §2.9. |
| 41 | `## Public status contract` (739) | **Retire** | Built on collections, triage, private handoff and release stages; the durable status principles are collected in §2.11. |
| 42 | `### Public contract` (776) | **Retire** | `stewart.status/14`, its stage vocabulary and field table have no referent; surviving sentences are named in rows 43–46. |
| 43 | *(extra)* `#### Provenance and schemas` (778) | **Restate** | "`ok` means exit zero, not successful inquiry or an auditor verdict" (784–785), "a field has the same provenance at every stage" (787) and "immutable-looking filenames do not confer trust" (791) carry; the field table retires. |
| 44 | *(extra)* `#### Attention and options` (843) | **Restate** | One attention channel with source, reason, message and code; no inference of auditor activity from absence or elapsed time (845–847, 862–863); codes 0/1/2/3; options are not instructions, all carry; collection and launch content retires. C13's "status reports interrupted" needs the liveness decision in §2.11. |
| 45 | *(extra)* `#### Handoff access and explicit recipe preview` (899) | **Retire** | Launch profiles and rendered commands have no referent; "the receipt carries the exact run line" replaces them [D 603–604]. |
| 46 | *(extra)* `#### Workspace listing, discovery, drafts and closes` (927) | **Restate** | "Discovery is an inventory for explicit selection, not validated status" and selection by reference carry into inquiry-scoped status [D 591–593; P R344]; drafts, closes and discovery schemas retire. |
| 47 | *(extra)* `#### Concrete examples` (957) | **Retire** | Baseline output and status/14 projections. |
| 48 | `### Observation, consumer and diagnostic ownership` (1065) | **Retire** | A Python module ownership map; the rule at 1089–1092, "a live check moved out of inspection is detected later at its operation owner, not magically eliminated", should survive as a status principle (§2.11). |
| 49 | *(extra)* Closing records retain their meaning (1094) | **Retire** | `stewart.closing/1` is a Python schema; "a new implementation may inspect supported evidence but may not mutate an old writer's session" (1098–1100) goes to §2.9. |
| 50 | *(extra)* Offers are not operation prerequisites (1103) | **Restate** | Status's suggested next command never becomes a refusal condition; applies to the signs status and `help` now give [P R339–347]. |
| 51 | `## Close` (1109) | **Restate** | The single close from any state is decided [D 594–598]; the legacy collect/triage/abandon procedures retire; what close removes is undecided. |
| 52 | Successor interface direction, 2026-10-25 (1117) | **Carry** | Realized by 594–598 [D]; "an interrupted or blocked closure remains visibly unfinished and needs a supported path through close" carries [P E150–152]. |
| 53 | Graceless exit direction accepted, 2026-10-25 (1137) | **Restate** | No flag: close from any state stops a live run [D 595]; the control obligation (1145–1152: who may stop, by what means, evidence of what termination ended) is unaddressed, §2.4. |
| 54 | Scope updated 2026-10-25 (1160) | **Retire** | Audit facilities, attempt HOME and release/run states have no referent; "a close cannot silently release a hold" (1169–1171) goes to §2.1. |
| 55 | Runtime coverage replaces equality with preparation (1178) | **Retire** | Supplied runtime, collections and triage have no referent. |
| 56 | A recovery is disposable while it matches its own capture (1197) | **Retire** | Runtime recovery directories have no referent. |
| 57 | Access-boundary issue, 2026-10-25 (1216) | **Retire** | The lean to omit materialization is realized by the no-workspace design; nothing to preserve. |
| 58 | Legacy experiment HOME is declared disposable with its identity recorded (1229) | **Retire** | Legacy population only, as the paragraph itself says (1239–1243). |
| 59 | The closing record freezes the identity of what was discarded (1245) | **Undecided** | If close removes nothing there is nothing to freeze; if it removes the audit directory this rule returns as written, including revalidation before each removal step (1250–1253). |
| 60 | Abandon follows the same rule (1255) | **Retire** | No abandon mode; "it names what it gives up" is carried by C8 [P E190–191]. |
| 61 | A kept checkout stops cleanup (1262) | **Retire** | No checkout. |
| 62 | Command rendering is not a closure precondition (1274) | **Retire** | No launcher or rendered command; its spirit, a cosmetic failure never refuses close, is covered by row 50. |
| 63 | Retained, not re-decided (1280) | **Restate** | A damaged record delivery relies on is reported as damage, never delivered as good [P E153–154]; "because conclusion deletes the originals" depends on the deletion decision. |
| 64 | Which live checks conclusion makes (1285) | **Retire** | Writer identity, checkout inventory, runtime coverage and recoveries have no referent. |
| 65 | The closing record is a new schema (1299) | **Undecided** | The grounds list is removal-phrased; one ground survives regardless ("lost despite a recorded preservation undertaking", C8) and "never described as declined or reviewed" (1307–1308) should survive in any closing record. |
| 66 | A recorded preservation undertaking gates conclusion (1316) | **Restate** | Close delivers before it records the end; an interrupted delivery is continued by close; a missing member must be named [D 499–505; P E150–152, E190–191]. |
| 67 | Supplied-file copies at abandon (1326) | **Retire** | Worktree copies and pins have no referent. |
| 68 | Advice stays separate from preconditions (1333) | **Restate** | Same rule as row 50; `retain` and collections retire. |
| 69 | Later returns (1338) | **Retire** | Collections and triage have no referent. |
| 70 | `## Export of selected custody with surrounding damage` (1361) | **Restate** | Damage travels explicitly with the return and blocks only dependent claims [D 431; P E153–154]; there is no export command, §2.5. |
| 71 | `## Supplemental inputs below gitlinks` (1381) | **Retire** | No Git [C t5]. |
| 72 | `## Launch acknowledgments by people` (1393) | **Restate** | Replaced by invocation observations that never label the manager [D 607–608]; "model and effort apply only to an agent arrangement" carries into the adapter settings [P R95–101]. |
| 73 | `## Pinned submodule copies` (1402) | **Retire** | No Git [C t5]. |
| 74 | `## Return arrangements and the human auditor` (1421) | **Restate** | The premise "nothing the auditor does reaches Stewart before collection" is inverted: every call lands in the ledger [D 583–586]; the human-auditor accommodations move to the person adapter, not in the first release [P E342]. |
| 75 | *(extra)* A manager-declared return arrangement (1428) | **Retire** | The problem file's `destination` and Stewart's own delivery replace a free-text expectation [P R102, R293]. |
| 76 | *(extra)* A stop note on collect (1435) | **Retire** | No collect [D 594]. |
| 77 | *(extra)* What the structured return already is (1439) | **Retire** | Documentation of the Python return. |
| 78 | *(extra)* The handoff is complete without the helpers (1445) | **Restate** | For the person adapter: the packet must suffice without the model adapter [P R247–249]; "no channel, no notification, no retention right, no role transfer" carries as written. |
| 79 | *(extra)* Delivery, Deferred (1453) | **Retire** | No longer deferred: delivery at the end of the run or by close is decided [D 594–598]; the marker should change rather than the text be dropped. |
| 80 | *(extra)* A capture receipt for the auditor, Deferred (1457) | **Restate** | Realized by the re-entry call and the submit reply [D 583–586; P R220, E119–125]; should be marked decided, since it serves the first process promise. |
| 81 | `## External sources and the constructed network grant` (1462) | **Retire** | The auditor has no network; external material arrives as exported files [P R113–115; C t5 R7]; the only network is the provider from the model adapter [P R368–369]. |
| 82 | `## Program execution and the legacy experiment route` (1478) | **Carry** | No executor is reaffirmed; "any other way of working is a new adapter" [P R252–253]; the dependent-behavior table describes the legacy population. |
| 83 | *(extra)* Execution failure is not dissatisfaction with an audit answer (1513) | **Carry** | A dead run continues; an unsatisfying answer is a new problem in the inquiry [D 643–659, 591–593]. |
| 84 | *(extra)* Earlier route, superseded for the successor on 2026-10-25 (1521) | **Retire** | Historical; already superseded in place. |
| 85 | `## Holds on identified custody material` (1534) | **Undecided** | A blocking-only restraint on Stewart's disposal has nothing to block if Stewart never deletes [P R361], which the user has not confirmed [R13]; no decided text or ROUTER line mentions holds or provider conditions, §2.1. |
| 86 | `## Attribution of retention` (1585) | **Restate** | Who sealed (manifest) and who invoked each command (observations) are the attributed steps [D 607–608, 638–639]; `retain` and resource writes have no referent. |
| 87 | `## Evidence interpretation across implementations` (1591) | **Restate** | "Across implementations" becomes across binary versions and without the writer process; the return is readable from its files alone [P R303–305], §2.6. |
| 88 | `## Writer continuity into the successor` (1626) | **Undecided** | Depends on whether any Python audits or resources with live undertakings exist, §2.9; the version-skew rule should be restated regardless, §2.7. |
| 89 | `## Access and experiment capability limits` (1650) | **Retire** | Facts of the frozen Python baseline; "costs stated rather than promised away" and "project rules reach the auditor only through supplied guidance" live on in help's limits and ROUTER 201–202 [P]. |
| 90 | `## Previously accepted corrections` (1681) | **Retire** | Git invocation items; "bind the last required observation to the value actually written" is already restated at 374–376 [D]; executable-bit coverage (1692) goes to §2.14. |
| 91 | `## Declined` (1703) | **Restate** | The list survives but each entry needs re-grounding, rows 92–105. |
| 92 | *(extra)* Declined: Mandatory retention before close (1707) | **Carry** | No manager duty before close; delivery is Stewart's act [D 594–598]; holds, if kept, remain voluntary. |
| 93 | *(extra)* Declined: A universal final preparation receipt (1711) | **Retire** | Reversed: commission always issues the receipt as the handoff [D 600–604]; keep the entry as history with that note. |
| 94 | *(extra)* Declined: Splitting issuance from preparation (1717) | **Retire** | The decided design does split commission from run, on the network line [D 600–602]; the old reason no longer describes the design. |
| 95 | *(extra)* Declined: A manager accepted-answer receipt (1721) | **Carry** | Close's confirmation is of the copy's placement [D 597], never acceptance of the answer; verdict-shaped flags stay declined. |
| 96 | *(extra)* Declined: Live checks on retained published files (1725) | **Carry** | Delivery is verified by readback once; a recorded delivery does not certify present safety [D 556–557]. |
| 97 | *(extra)* Declined: Re-capture of recovery contents (1729) | **Retire** | No recoveries. |
| 98 | *(extra)* Declined: Charging an acknowledgment for a nonempty experiment HOME (1736) | **Retire** | No HOME. |
| 99 | *(extra)* Declined: Work inside populated submodules (1739) | **Retire** | No Git [C t5]. |
| 100 | *(extra)* Declined: An auditor-attributed acceptance of the commission (1747) | **Restate** | The reason inverts (every call reaches the ledger); the conclusion holds for a new reason: the first protocol call is an observation, never an acceptance claim. |
| 101 | *(extra)* Declined: Further standing for a human auditor (1751) | **Carry** | Unchanged; the person adapter's packet is the whole accommodation [P R247–249]. |
| 102 | *(extra)* Declined: Stewart fetching and pinning external bytes (1754) | **Carry** | Stewart's only network is the provider; exported files carry attribution as material [P R113–115]. |
| 103 | *(extra)* Declined: A command experiment kind (1757) | **Retire** | Settled by no executor; nothing left to decline. |
| 104 | *(extra)* Declined: Condition records on supplemental inputs or workspace declarations (1763) | **Undecided** | Its reason is that the hold supplies the restriction; it moves with the hold, §2.1. |
| 105 | *(extra)* Declined: A right to receive distinct from the commission (1769) | **Carry** | Status answers whoever holds the reference and Stewart never labels the manager [D 606–608]; "segregating at capture would break raw capture before interpretation" carries. |

## 2. Would be lost silently

Each item: what the earlier text protected, where it stands in the decided
design and ROUTER, whether the decided design makes it moot, and the reviewer's
recommendation with its reason.

### 2.1 Holds on identified custody material

- **Protected** (1534–1583; 117–121; 1169–1171; AGENTS 209–214): a manager
  could record a narrow, attributed, blocking-only hold on identified material,
  carrying a provider's condition or a delegation limit; Stewart would not
  dispose of it; only an explicit attributed release lifted it; close and
  container retirement could not override it; copying did not discharge it.
- **Where it stands:** mentioned nowhere in the 2026-10-28 decisions, ROUTER or
  END-TO-END. R6 raises the inverse obligation (material that must be destroyed
  after use) and says Stewart cannot honor it.
- **Moot?** Only if Stewart never deletes, which is a proposal [P R361] the user
  has not confirmed [R13]. If close or housekeeping inside Stewart ever removes
  an audit directory, the hold is the only record that stops it. Even under
  never-delete, the hold's record half, an attributed condition attached to
  identified material, has no home: the receipt carries no conditions and the
  manager's housekeeping [P R361–362] gets no sign.
- **Recommendation (reviewer's): Undecided.** Put two questions to the user
  together: does Stewart ever remove bytes, and should the receipt carry an
  attributed condition note on identified material. If never-delete is adopted,
  retire the hold mechanism and record the reason in Declined; if removal
  exists, carry the hold as written. **Reason:** the hold is the one contract
  that connects a third party's condition to Stewart's acts; dropping it
  silently leaves both R6's obligation and its inverse unaddressed.

### 2.2 Stewart's process promises to the auditor

- **Protected** (122–124; 579–581; 1457–1460; AGENTS 118–126): raw capture
  before interpretation (the auditor's bytes are preserved before any
  validation); a disposition of every gap (nothing missing, invalid or
  interrupted is silently omitted); attribution never turned into a verdict
  (observations, acknowledgments and claims in separate fields; no grade,
  deadline or verdict field).
- **Where it stands:** restated as standing in a decided paragraph [D 579–581],
  so not lost from CONTRACTS. ROUTER never names them; END-TO-END has no claim
  for them; the capture receipt for the auditor (1457) is still marked Deferred
  although the re-entry call realizes it.
- **Moot?** No, and the new design has one place where the first promise can
  fail silently: validation now runs before the record is appended. A `limit_exceeded`
  refusal is recorded as an observation [D 413–414], but a citation refused by
  the mechanical check [P R227–228, E174–176] is "never recorded as valid", which
  does not say it is recorded at all. A refused add that leaves no record drops
  auditor bytes before anyone interprets them.
- **Recommendation (reviewer's): Carry, and make them testable.** Add an
  END-TO-END claim (or extend C3 and C6) that every refused protocol call is in
  the record with its reason and its bytes; that every gap (torn tail, limit
  refusal, dead run, undelivered member) appears in `status` with a recorded
  disposition; and that no record, reply or return carries a verdict field.
  Decide where limit and citation refusals reach the manager, which under "the
  return is the submission" must be `status`, not the return (§3.1). Mark 1457
  decided. **Reason:** the promise is decided but unverifiable as the test
  design stands, and refusal-before-record is the one path by which the new
  design could lose auditor bytes.

### 2.3 Managers' independent workspaces

- **Protected** (672–675; 712–737; 1289–1290; AGENTS 201–204): Stewart never
  acquired disposal authority over a manager's own worktree, branch or
  directory; audit close could not reach it; dependencies on it had to be
  ended before its protection was removed.
- **Where it stands:** nowhere; no Git, no worktrees; material is copied at
  commission [D 600–602].
- **Moot?** Mostly: Stewart creates nothing in the manager's tree. The residue
  is the `destination` directory, which is the manager's and which Stewart
  writes into at delivery. Neither ROUTER nor END-TO-END says what delivery does
  when the destination already exists, and C5's "a delivery interrupted partway
  keeps its partial directory ... and close produces a complete copy" [P
  E150–152] does not say where the complete copy goes.
- **Recommendation (reviewer's): Retire the service and restate the residue.**
  Convert the deferral into a Declined entry ("Stewart manages no manager
  workspace; it reads the manager's paths at commission and writes only to its
  home and the named destination") and add one delivery rule: the destination
  is exclusive (an existing directory is evidence and is refused, never
  overwritten or emptied), a partial delivery keeps its name, and the complete
  copy gets a new name. **Reason:** the exclusive-destination refusal (AGENTS
  110–112; 1333–1336) is the one piece of this family the new design still
  needs, and nothing in ROUTER or END-TO-END states it.

### 2.4 The close details

- **Protected** (1109–1359; 476–535), the parts that survive removal's
  departure: (i) the control obligation (1145–1152): who may stop a live run,
  by what means, with evidence of what termination ended; (ii) loss despite an
  undertaking is never recorded as declined (96–97, 1307–1308); (iii) a
  completed close conceals no unfinished operation (110–112); (iv) an
  interrupted close stays visibly unfinished and resumes through close
  (1128–1130, 503–505); (v) the closing record names what was given up (C8);
  (vi) no waiting periods, readiness requirements or deterrents on the manager's
  seal (530–535); (vii) advice is never a precondition (1333–1336); (viii)
  close's confirmation is not acceptance of the answer (1721–1724); (ix)
  revalidate before each removal step (1250–1253), only if removal exists.
- **Where it stands:** ROUTER 345 and C8 [P E184–192] cover (ii), (iv) and (v)
  in outline. (i) is unaddressed: close "stops a live run" while the run may be
  held by another process or another person under the escalated run [D
  600–612]; the run lock is a coordinator proposal [R13]. (vi), (vii) and
  (viii) appear nowhere in ROUTER or END-TO-END.
- **Moot?** (ix) is moot only under never-delete. The rest is not.
- **Recommendation (reviewer's): Restate (ii)–(viii) as the successor close
  contract; put (i) to the user as Undecided.** The question for the user: how
  does close reach a run it did not start (signal by recorded pid, a lock the
  run watches, or refusal with a sign naming the holder), and what the record
  says was stopped (the last complete ledger record is the natural boundary).
  **Reason:** C8 tests outcomes, not authority; without (i) the escalated run
  produces audits a person started that an agent cannot stop, or the reverse,
  and the old text is the only place that obligation is written down.

### 2.5 Export and evidence packages

- **Protected** (1361–1379; 1585–1589; 1645–1648; AGENTS 157–163): a selected
  verified member stays exportable despite damaged siblings, with the damage
  carried explicitly; a package pins its source receipt and selection; importing
  conveys custody, never execution permission or acceptance of claims; the
  exporting implementation is recorded; export is attributed.
- **Where it stands:** C5 carries "damage reported, never delivered as good,
  never treated as absent" [P E153–154]; the manifest names who sealed [D
  638–639]. There is no import; comparison is the manager's work on files it
  owns [D 598].
- **Moot?** The export command and import are moot. Three things are not: the
  return as a self-verifying package (its manifest's digests make it checkable
  without Stewart, which ROUTER implies but does not promise); which Stewart
  version delivered it; and the second copy. The 2026-10-27 text promised "a
  supported request can produce another copy of the same sealed return" (507)
  and the narrowing makes that `close` only when no verified copy exists
  (509–510). A manager who loses a verified delivery gets nothing from Stewart;
  the payloads sit in the home as plain files, reachable by hand [P R303–305].
- **Recommendation (reviewer's): Restate.** State that the return is a
  self-describing package verifiable from its manifest alone, naming the
  delivering version; and state in CONTRACTS that after verified delivery the
  home's copy is the manager's only second source, by hand, with no present-safety
  certification [D 556–557]. **Reason:** dropping export silently leaves the
  second-copy route undocumented; saying it is housekeeping is honest and costs
  nothing.

### 2.6 Evidence interpretation across implementations

- **Protected** (1591–1624): verified captured evidence stays interpretable when
  the writer implementation, executable or environment is gone; the reader names
  what it can establish; damaged selected evidence invalidates only the
  dependent claim; reading never repairs, replays or executes; unsupported
  schemas stay unsupported with distinct diagnostics.
- **Where it stands:** "damage blocks only the claims that depend on it" [D
  431]; "status and the files answer for them" [P R303–305]. Nothing about
  versions or schemas.
- **Moot?** "Across implementations" is moot with one binary. Across binary
  versions it is not: write-once records plus a changing binary is exactly the
  case the rule addressed. R7 also notes that hashes sit beside the payloads
  they protect, with the receipt and manifest digests as the only outside
  anchors.
- **Recommendation (reviewer's): Restate.** Every record names the Stewart
  version and schema that wrote it; later versions read older records or
  diagnose them as unsupported, never rewrite them; a return and a record are
  interpretable from their files alone; damage invalidates only dependent
  claims. **Reason:** no decided text or ROUTER line states the version rule,
  and the first version bump would otherwise be the first time anyone thinks
  about it.

### 2.7 Writer continuity and runtime handoff

- **Protected** (1626–1648; 783; 1098–1100; AGENTS 227–231): a mutation under an
  implementation other than the record's writer is refused; a handoff is offered
  only when verified; recorded code is never executed; existing writers service
  their open sessions.
- **Where it stands:** the multi-implementation case is gone. The version-skew
  case remains and is live in the decided design: an audit commissioned by one
  binary and continued (`run REF` after a dead run) or closed by a newer one.
  C13 checks "the same arrangement digest as the first run" [P E256–257], which
  is the right check, but nothing says what happens when a newer binary's
  orientation or coupling version would produce a different digest.
- **Moot?** The mechanism is; the obligation is not.
- **Recommendation (reviewer's): Restate as a version rule.** The receipt
  records the binary version; `run` and `close` on a record written by a
  different version proceed only with the recorded arrangement verified by
  digest, else refuse with a sign naming both versions; a record is never
  upgraded in place. **Reason:** "one binary" hides a real skew between the
  commissioning and the continuing binary, and the old writer-binding rule was
  the guard.

### 2.8 Request keys

- **Protected** (AGENTS 219–226; 1316–1324; 1711–1716): an agent-manager whose
  reply was lost could re-issue a keyed request and get the same record back
  instead of a second side effect; planned outputs were recorded before the
  first; a partial request resumed only its own planned work; unkeyed requests
  were never deduplicated.
- **Where it stands:** ledger truth replaces it on the auditor side [D
  583–589]. On the manager side: `run` refuses when running or ended [D
  605–606]; close is confirmation-gated and continues the same undertaking [D
  499–505]; `commission` has no key, so a lost commission reply followed by a
  repeat makes a second audit in the inquiry (two copies, no money spent),
  which inquiry-scoped `status` lists [P R344].
- **Moot?** Mostly: the protection moved into the command semantics.
- **Recommendation (reviewer's): Retire the mechanism; restate one
  sentence.** "Commission is not deduplicated: a repeated commission is a new
  audit in the inquiry, which status lists; run and close answer by reference
  and are safe to repeat." **Reason:** the residue is harmless if stated and
  confusing to an agent-manager if not.

### 2.9 Legacy Python records

- **Protected** (729–737; 1601–1607; 1636–1641; 1094–1101; 1503): open Python
  sessions, resources, claims and partial requests receive explicit transition
  dispositions before Python is withdrawn; the successor reads but never
  mutates or executes them; historical receipts are never rewritten; no blanket
  compatibility obligation.
- **Where it stands:** none of the decided text, ROUTER or END-TO-END mentions
  Python records. The user's R8 drops the *baseline* [C t5]; it says nothing
  about records on disk. R18 notes the audit-tool gap between removing Python
  and the binary working.
- **Moot?** Only if no Python audits or resources with live undertakings exist.
- **Recommendation (reviewer's): Undecided; the user names the population.**
  If none is live: record one line in CONTRACTS ("Python records are
  historical; the successor reads none of them; closing them, if wanted, is
  done with the frozen Python before it is removed") and retire the bounded
  reader and writer-continuity sections. If some are live: close them under
  Python before withdrawal, as 734–737 already requires. Either way "never
  rewrite historical receipts" carries into the development guidance
  unchanged. **Reason:** the successor should inherit neither a reader
  obligation by silence nor orphaned live undertakings by silence.

### 2.10 The custodian of the commission copy

- **Protected** (258–266; 325–331, both user-selected 2026-10-27): the
  commission bundle is delivered into explicitly designated storage; a named
  custodian preserves it; acceptance means present and verified at that
  destination; "C neither silently deletes delivered material nor undertakes a
  separate private retention service".
- **Where it stands:** ROUTER puts the copied material under Stewart's home, a
  location Stewart chooses, with removal as the manager's housekeeping [P
  R359–362]; the home layout is listed as a coordinator invention [R13]. The
  decided "commission copies, verifies and records locally" [D 600–602] does
  not say where.
- **Moot?** No; the acceptance promise is unchanged, only its destination moved.
- **Recommendation (reviewer's): Undecided.** The user says whether Stewart's
  home *is* the designated storage (then the receipt names it and the manager
  is custodian of that directory) or whether the commission copy goes to a
  manager-named location. **Reason:** the first leg's custodian selection was
  the user's; the home layout silently relocates it.

### 2.11 Status's refusal to infer activity, and the other durable status rules

- **Protected** (845–856, 862–863, 878–880; 556–558): status never inferred
  that an auditor is running or stopped from absent records or elapsed time;
  absent records establish neither liveness nor completion; no duty to monitor;
  plus the rules in rows 43, 44, 46, 48 and 50: `ok` means exit zero; one
  attention channel with source, reason, message, code; codes 0/1/2/3; options
  are not instructions; offers are not preconditions; a live check moved out of
  inspection is detected at its operation owner, not eliminated.
- **Where it stands:** C13 has `status` report "interrupted with its run count"
  after a kill and C12 has it report "done" [P E238, E255]; the run lock and
  status liveness are coordinator inventions [R13].
- **Moot?** Partly: Stewart now owns the run process, so "running" can be an
  observation of its own process. After a kill the lock is stale and "running"
  would be the inference the old contract forbade.
- **Recommendation (reviewer's): Restate.** Status reports recorded run endings
  as facts; a held run as an observation with its evidence (pid liveness or
  lock age) labelled as such; a run whose process cannot be observed as
  "interrupted, unconfirmed", never "running"; no elapsed-time inference. Carry
  the other status rules as a short list. **Reason:** C13 cannot pass without a
  liveness decision, and a stale lock reported as running is exactly the guess
  the old contract was written to prevent.

### 2.12 The restriction on manager live access

- **Protected** (661–669; 697–700; 134–135): after handoff, manager access to
  the auditor's live material is very restricted; live inspection is not a
  product objective; receiving the return must not reopen live material.
- **Where it stands:** the record "stays in Stewart's home ... readable by
  whoever runs Stewart" [D 635–636]; ROUTER keeps the full conversation for
  whoever runs Stewart to read [P R244–245]; R8 says the manager can read the
  auditor's work live. The user's words: "I might insist here that I don't
  care. A person running stewart is free to inspect reasoning summaries" [C
  t12 #5].
- **Moot?** The steering half is realized by construction: the manager has no
  channel into the run. The inspection half is dropped, by two decided
  paragraphs that disagree (§3.2).
- **Recommendation (reviewer's): Restate 661–669, with the user's
  confirmation.** "Stewart offers no live observation or steering interface;
  the manager cannot change the auditor's world after commission; the record in
  Stewart's home is readable by whoever runs Stewart, including during a run,
  and that is not a product surface." **Reason:** the user's words lean to the
  later paragraph, but the 2026-10-25 text is also marked decided and a reader
  cannot tell which governs.

### 2.13 The platform, no-Git and no-baseline decisions themselves

- **Protected:** nothing old; but every Retire row above rests on "Linux only",
  "no Git, history as exported files" and "no Python baseline", which CONTRACTS
  states only as the Mission's framing (37–41). The source is the user's turn-5
  quote [C t5] and the brief's condensation.
- **Recommendation (reviewer's): Carry, by recording them.** Add three short
  decided contracts (platform and shipping form; material as copied files with
  history as exported files; no Python baseline and what "Implemented" now
  means) citing turn 5, before retiring the Git and Python rows. **Reason:**
  otherwise every retirement cites a decision CONTRACTS does not contain.

### 2.14 File modes at intake

- **Protected** (1692–1693): hidden executable-bit changes counted in capture
  coverage, with kind and content.
- **Where it stands:** C2 checks bytes, not modes [P E94–105]; "a directory
  expands to its regular files" [P R127]; R10 notes text and lines are assumed
  everywhere.
- **Recommendation (reviewer's): Restate as one line** in material acceptance:
  intake records each file's bytes, size and mode; the index shows size; mode
  is recorded, not interpreted. **Reason:** cheap, and a question about scripts
  or permissions otherwise loses evidence silently.

### 2.15 Deliberation of outcome-shaping restrictions

- **Protected** (150–158): restrictions that exclude or privilege substantive
  outcomes need explicit design deliberation, even when introduced through
  formatting or schemas.
- **Where it stands:** the principle carries (row 10). The new influences it
  must govern are all proposals: the orientation text, the reminder after an
  unsubmitted stop, the near-limit warning, the mechanical citation refusal and
  the slot enums [P R185–189, R227–228, E174–176; R1]. The coordinator's own
  pitch lists them as choices for the user (turn 17) and says a mechanical
  check "rewards citing over synthesis and over arguments from absence".
- **Recommendation (reviewer's): Carry, and apply it before the first
  release:** each of those five is recorded in CONTRACTS as a deliberated
  choice with the agnosticism test applied, or as a manager setting.
  **Reason:** the principle survives but nothing forces it onto the new
  influences, which ROUTER currently presents as plumbing.

## 3. Contradictions

### 3.1 Two decided 2026-10-28 paragraphs: the return's provenance

"Provisional answer structure" (413–414) says Stewart "lists [each
`limit_exceeded` refusal] in the return's provenance", and the superseded
paragraph under signs (439–440) spoke of "the return's provenance" too. "The
return is the submission" (631–641) says nothing but the sealed manifest and
its elements travels, and the manifest names only the reference, form, version
and sealer. Both are dated 2026-10-28; the later one (turn 22) is not marked as
narrowing the earlier. **Resolution the reviewer suggests:** mark 413–414
narrowed; refusals and gaps reach the manager through `status` and the record,
never the return. This is also where §2.2's "disposition of every gap" lands.

### 3.2 Two decided paragraphs: manager access to live material

"Handoff and audit-owned facilities" (664–666, decided departure 2026-10-25):
"manager access to the auditor's live material is to be very restricted and the
audit process abstract to the manager"; "Access through explicit grants"
(697–700) repeats it. "The return is the submission" (635–636, decided
2026-10-28): the record "stay[s] in Stewart's home ... readable by whoever runs
Stewart"; ROUTER 244–245 [P] keeps the full conversation readable; R8 names the
consequence. The user's words at turn 12 #5 lean to the later text. Neither
paragraph is marked superseded. See §2.12 for the restatement.

### 3.3 A decided sentence against the decided form

"The auditor is not shown the question type, which is the manager's
implementation concern" (442–443) stands unmarked inside the superseded
paragraph, and the coordinator cited it at turn 6 as a standing decision. Under
"The auditor's tool is a form" (569–579) and ROUTER's arrangement (180–186,
218–224 [P]) the auditor meets the form's instructions as its orientation and
the form's slots as tools; only the form's name and the manager's reason for
choosing it are withheld. The sentence is false as written for the decided
design. **Suggested resolution:** restate as "the auditor is shown the form's
instructions and slots, not its name, the manager's reason for choosing it, or
a sealed prior".

### 3.4 ROUTER against END-TO-END C5 and the decision: the rendered answer

ROUTER's return layout (296–301 [P]) has `answer/` "rendered by the coupling,
plus the raw slots and elements". C5 (147–149 [P]) says the delivered directory
holds "the manifest and the elements and nothing else", and the decision
(631–633 [D]) says the return is "the sealed manifest and the elements it
lists". A rendering is Stewart's product, not the auditor's submission. It can
be consistent only if the rendering is a manifest member generated at `prepare`
("generated mechanical metadata", 304), sealed with the rest, reproducible, and
attributed to Stewart. ROUTER and END-TO-END should say which.

### 3.5 ROUTER and END-TO-END hard-code an undecided premise: never delete

ROUTER 359–362 ("Stewart deletes nothing. Closing is a record") and END-TO-END
C6 and C8 ("none of them removes anything") are proposals [R13: "followed from
R2, never confirmed"]. Decided paragraphs still presume disposal at close:
Principles 65–69 and 89–99; "superseded and deleted payloads remain internally
held until authorized closure" (333–337); the manager "loses the ability to
request another copy from that custody" (494); "Stewart does not promise to
recreate disposed audit payloads" (513–514). Never-delete is a stricter special
case, so this is not a logical contradiction, but the test design would pass
only under a premise no decision records. Rows 4, 6, 59 and 65 and §2.1 hang on
it.

### 3.6 A user selection against the home layout: the commission copy's custodian

"First successor leg" (258–266 [D], user-selected): manager-custodied delivery
into explicitly designated storage, no separate private retention service.
ROUTER 359–362 [P]: the copy lives under Stewart's home. See §2.10.

### 3.7 ROUTER states as design what CONTRACTS keeps as a choice: citation checking

ROUTER 227–228 and C7 (174–176 [P]): "Every citation is checked against the
material, byte for byte"; off-by-one citations are refused. The coordinator's
mission pitch (turn 17) lists citation checking among the consequential choices
to bring to the user and warns it rewards citing over synthesis; the brief lists
it as undecided; Principle 150–158 [D] requires explicit deliberation for
restrictions introduced through schemas. ROUTER's own "the library is
provisional" (147–152) covers the couplings but not this check.

### 3.8 Reconcilable wording: the repeated submit

"An identical confirmed repeat returns its recorded outcome without creating a
second submission" (379–381 [D]) and "a retry lands as a new record, and equal
bytes never identify a retry" (585–586 [D]) read as opposites. They are not:
the *handle* bound to the exact collection revision identifies the repeat, not
the bytes, and returning a recorded outcome is not settling anything. The
submission paragraph should say so in those words.

### 3.9 END-TO-END presumes a liveness mechanism no decision selected

C13 "status then reports the audit interrupted with its run count" and C12
"status REF ... reports it done" [P E238, E255] require status to know whether
a run is held. The run lock is a coordinator invention [R13], and the old
contract forbade inferring activity from records (845–847). See §2.11.

### 3.10 Minor wording

- "Within an explicitly selected repository or custody scope" (548–549 [D])
  reads as inquiry scope under 591–593 [D]; restate, not a contradiction.
- "Delivery. Deferred." (1453) and "A capture receipt for the auditor.
  Deferred." (1457) are both realized by decided text (594–598; 583–586) and
  still carry the Deferred marker.

## 4. Counts

Rows in the table: **105**.

Headings and bold titles found, as the brief defines the required set:

| Kind | Count | Lines |
| --- | --- | --- |
| `##` headings | 25 | 35, 60, 246, 298, 445, 561, 661, 687, 712, 739, 1109, 1361, 1381, 1393, 1402, 1421, 1462, 1478, 1534, 1585, 1591, 1626, 1650, 1681, 1703 |
| `###` headings | 2 | 776, 1065 |
| Bold titles in Principles | 12 | 65, 71, 89, 101, 126, 131, 143, 160, 178, 208, 219, 234 |
| Bold titles in "Successor answer construction" | 5 | 325, 339, 364, 390, 420 |
| Bold titles in "Successor manager receipt" | 6 | 458, 468, 476, 499, 516, 544 |
| Bold titles in "Successor interfaces decided 2026-10-28" | 7 | 569, 583, 591, 600, 614, 631, 643 |
| Bold titles in Close | 18 | 1117, 1137, 1160, 1178, 1197, 1216, 1229, 1245, 1255, 1262, 1274, 1280, 1285, 1299, 1316, 1326, 1333, 1338 |
| **Required rows** | **75** | |
| *(extra)* preamble | 1 | 1–33 |
| *(extra)* `####` sub-headings of the status contract | 5 | 778, 843, 899, 927, 957 |
| *(extra)* bold titles in "Observation, consumer and diagnostic ownership" | 2 | 1094, 1103 |
| *(extra)* bold titles in "Return arrangements and the human auditor" | 6 | 1428, 1435, 1439, 1445, 1453, 1457 |
| *(extra)* bold titles in "Program execution" | 2 | 1513, 1521 |
| *(extra)* Declined entries | 14 | 1707, 1711, 1717, 1721, 1725, 1729, 1736, 1739, 1747, 1751, 1754, 1757, 1763, 1769 |
| **Extra rows** | **30** | |
| **Total** | **105** | equals the table's row count |

"First successor leg" (246) contains no bold paragraph titles. The untitled
superseded paragraph at 435–443 is covered inside row 22 rather than given a
row, so that the required count matches the brief's definition.

Rows per disposition (all 105 rows; the required 75 in parentheses):

| Disposition | All rows | Required rows |
| --- | --- | --- |
| Carry | 32 | 25 |
| Restate | 31 | 23 |
| Retire | 35 | 21 |
| Undecided | 7 | 6 |
| **Total** | **105** | **75** |

(Tallied from the table by `grep` after writing, not from a running count.)

Undecided rows: 4, 6, 59, 65, 85, 88 (required) and 104 (extra). Five of the
seven hang on one question, whether close or anything in Stewart ever removes
bytes; the other two on whether live Python undertakings exist.
