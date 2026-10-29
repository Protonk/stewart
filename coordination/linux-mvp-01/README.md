# One design conversation, and what it produced

On 2026-10-28 an alignment conversation about Stewart turned into a redesign. This
folder records that conversation and the documents it produced. The conversation
ended at turn 23 the same day; the user's decisions from it are recorded in
[CONTRACTS.md](../../CONTRACTS.md), which owns them. Nothing is added to the
conversation now. [AGENTS.md](AGENTS.md) says how agents should treat the folder.

## Start here

| Read | What it is |
| --- | --- |
| [ROUTER.md](ROUTER.md) | **The settled design sketch.** Stewart as a problem router for cooperative actors who want to make it *just* so. Where it and CONTRACTS differ, CONTRACTS decides; where CONTRACTS is silent, the sketch is the coordinator's proposal. |
| [END-TO-END.md](END-TO-END.md) | **The settled test design**: what an end-to-end test of the router must show, including a real-model conformance gate. |

## How it got there

The conversation produced three views of one design encounter, then continued:

| Read | What it is |
| --- | --- |
| [CONVERSATION.md](CONVERSATION.md) | The conversation itself: the user's prompts verbatim and the coordinator's replies, from the first alignment question to the end-to-end test request. |
| [CONVERSATION-HELD-BACK.md](CONVERSATION-HELD-BACK.md) | Notes the coordinator held back during the first three turns, the radical alternatives (R1–R12), and the user's comment on them. A verbatim copy of the working file. |
| [DESIGN.md](DESIGN.md) | View 2, the radical design: the first draft, with its reasons and anchors back to the conversation and CONTRACTS. |
| [STEWART.md](STEWART.md) | View 3: the same design presented from a clean sheet, with open decisions posed where they arise. |
| [RESERVATIONS.md](RESERVATIONS.md) | What still bothered the coordinator after the three views, including which details were its own inventions. |

After the three views, the conversation covered two pitches on question types
(a panel of blind auditors, and a small library of question-answer couplings),
settled on the coupling library, worked through the coordinator's deep
reservations and the user's answers, and arrived at ROUTER.md and END-TO-END.md.
Where files disagree on details, the later ones are current and the earlier ones
are records. The conversation continued after the first turnover: turns 17–21
settled the mission, the auditor's tool as a form and a ledger, the inquiry as
the manager's unit, the escalated run and the problem file. ROUTER.md and
END-TO-END.md were revised in place at those turns, and CONTRACTS now records
the decisions.
