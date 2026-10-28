# Turnover

Written at the user's direction on 2026-10-28 UTC by the outgoing coordinator.
Source: `main` at `3abfa5c`; this brief and a small tidying pass of the
coordinator documents are the following commit. It supplements the
[standing orders](STANDING-ORDERS.md) and the [current account](COORDINATOR-NOTES.md),
whose current checkpoint holds this tenure's state. Nothing here commissions
work. Nothing has been pushed; `origin/main` lacks this tenure's commits and the
previous tenure's last two.

## Where things stand

The user approved the custody-and-delivery candidate
([NEXT-LEG](submission-design-01/NEXT-LEG.md)) as the first implementation leg
and hopes to continue through the remainder of the transition. The leg is not
dispatched and not dispatch-ready. [PLAN-FIT](custody-delivery-01/PLAN-FIT.md)
is the working document: five of its seven user decisions are settled; items 1
(access route) and 3 (delivery) are open and meant to be designed together.
Capacity, per the user: one or two development sub-agents for this leg, and
the coordinator's own workflows within a rough ceiling of ten simultaneous
agents. Stewart auditors in trials are a separate count, set by item 1.

The Linux check and the suite repairs are complete. The full suite is green in
the checkout. `.scratch/linux-check-01/RESULTS.md` holds successor-design inputs
from that run worth reading before the close and checkout work.

## The conversation in progress

Item 1 is to become a document the user and coordinator agree on, which also
fixes how many Stewart auditors trials use and answers
[AUDITOR-CASES](custody-delivery-01/AUDITOR-CASES.md) Q14 and Q27–Q31. The
threat model and enclosure discussion behind it is unfinished. The user asked
to talk it through rather than have conclusions recorded, so nothing is settled
beyond what CONTRACTS records (notably “Access through explicit grants” and
“Auditor-facing signs and re-entry”). Route research for it is in
`.scratch/route-research-01/RETURN.json`, partly framed around the since-corrected
containment purpose. The user's own words, for continuing that conversation (not
conclusions):

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

Item 3 starts from delivering the sealed manifest to the manager's destination
at seal time; C's request has no destination field yet.

## Next questions

1. Items 1 and 3 with the user, then the agreed access-route document.
2. A proposal for case-table Q26 (which informational notes are neutral).
3. PLAN-FIT's coordinator reconciliation list, including stale ordering text in
   DEVELOPMENT-PLAN and CONTRACTS' older “Delivery: Deferred” clause.
4. The concrete first-leg commission. Real auditor sessions and the
   [orientation trial](custody-delivery-01/ORIENTATION-TRIAL.md) need explicit
   launch permission; the user asked that the trial run outside the session
   that prepared it.

Environment notes are in the current checkpoint (`container` and the full
suite run outside this harness's command sandbox).
