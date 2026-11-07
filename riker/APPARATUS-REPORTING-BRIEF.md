# Bounded experiment reports: examples and design choices

Prepared for design consultation on 2026-11-07 from Stewart `b378d8e`. These are paper designs, not implemented interfaces or new live commissions. No model was called for this preparation. The historical runs below are complete and their placements consumed. Their records remain unchanged.

## The design problem

We want the principal to agree a budget and basic experiment design, then receive a small, useful result without reconstructing it from launch output, procedural reviews, collection records and a separate conversation. Collection, evidence review and custody disposition belong inside that eventual cycle. Some findings still need a reader or designer; we want those judgments visible and deliberate. The agent's future autonomy, paid-launch arrangement and enforcement are deferred. We are designing reports under current operating rules first.

The apparatus is development tooling around Stewart, not the product's auditor interface. Stewart preserves the auditor's answer and returns it faithfully. The local experimenter may draw conclusions about an encounter; those are attributed study findings, not Stewart's judgments of the answer. Neither a good answer nor a completed submission necessarily exercises the mechanism being studied.

Two constraints from the product matter here. [CONTRACTS](../CONTRACTS.md) assigns the answer to the auditor and custody operations to Stewart, and requires observations, acknowledgments and authored claims to remain distinct. [DESIGN](../DESIGN.md) distinguishes an auditor's submission from a manager's closure of recorded work. The experiment report can explain either without modifying the delivered answer. Experimental evidence does not qualify a model or change product promises.

## A proposed exchange

This is an information design, not a proposed JSON schema. The brief should carry the meaningful choices; exact input and executable bindings must remain inspectable and recoverable with it.

| Before the block | After the block |
| --- | --- |
| The narrow question and comparison; what varies and what stays fixed. | What was observed, which part of the question it answers, and what remains unexercised, ambiguous or unknown. |
| The observations that would distinguish possible outcomes, their sources, and interpretations requiring a reader. A prediction is recorded separately from the observation needed. | Mechanical check results and the experimenter's attributed interpretation, each tied to particular evidence. A surprising result is allowed. |
| Every proposed trial, model/settings, input/build identities, placement and resource bounds, cost basis and financial allowance. Estimate, enforceable limit and authorization remain distinct. | Every trial accounted for, including not-started work; reported and estimated usage, calculated cost and independent billing observation or disposition. |
| Stopping rules and any permitted variations or follow-ups. Under current rules, the principal authorizes exact live packets and runs their launches. | Remaining actions with their actor, reason and evidence. A suggestion neither starts a placement nor changes the agreed scope. |
| Collection, review and custody work needed to finish the block; who performs each under current authority. | Submission, sealing, delivery, closure and collection as observed at named times. A useful finding can coexist with unfinished custody work, which stays explicit. |

Each return identifies the proposal and evidence snapshots it uses. Later collection or a reader's response produces another dated account referring to the earlier one; it does not rewrite the earlier observation. The ordinary view can show the current supported disposition while its history remains inspectable. How to establish that a later observation resolves an earlier action is a design choice, not a rule that the newest file always wins.

## Example A: two planned turn limits

### Proposal example

This is a retrospective reconstruction of the relevant part of the five-run stress commission, simplified for design discussion. It is not the original approval packet and grants no renewed authority.

**Question:** What recorded work and returned package are available when the same inquiry is allowed ten turns or eight? Does the answer text itself make the stop apparent? The first part can be established from records; the second requires a reader. These are two stochastic encounters, not one trajectory truncated twice, and they cannot isolate the effect of the near-limit notice.

**Comparison and bounds:** Use the frozen Problem A question and materials, the same unqualified `open-inquiry/2` study build, `claude-haiku-5-5` at provider default effort, and one placement per condition. Vary the turn cap, 10 versus 8. Each retains 5,000,000 cumulative input tokens, 32,000 output tokens and a 1,800-second watchdog; only the built-in provider request retries are permitted. No repeat, replacement or continuation follows from the result. The original five-run commission owned the spending permission. Its dated estimate apportioned USD 0.0565 expected cost and USD 5.16 at full allowance/high-tier rates to these two trials; those are historical estimates, not current prices or an enforced dollar ceiling.

**Discriminating observations:** Record when an entry is first saved, whether it is revised, whether prepare/submit happens, the run ending, and the actor of any later seal. An empty answer, recorded but unsubmitted work, and auditor submission are all meaningful observations. Retain failed edits. A lost capture would leave the corresponding observation unknown. A reader's judgment about a finished-looking answer is attributed separately from these facts. The prior prediction favored an empty return at ten turns; that prediction must be allowed to be wrong.

**Completion:** An unsubmitted run needs an explicit custody disposition. Under the current route the principal performs close, inspection, confirmation where required, and collection; the local agent reviews the resulting evidence. No further placement is implied by a completed collection or a promising partial answer.

### Result example, using retained observations

**At ten turns there was recorded work to return; at eight there was none. Neither auditor submitted.** At ten, an account was recorded on request 8, a citation revision was refused on request 9, and a corrected revision was accepted on request 10. No prepare or submit call occurred. At eight, the auditor continued reading through the final request and made no recording call. Both runs ended at their turn limits. The paths had already diverged; this does not establish what the ten-turn run would have done under an eight-turn cap.

| Observation | Ten turns, run `-01` | Eight turns, run `-02` |
| --- | --- | --- |
| At launch observation | One selected entry, revision 2; unsubmitted and open | No selected entry; unsubmitted and open |
| After later custody actions | Manager seal, verified delivery, closed, second export collected | Manager seal, verified delivery, closed, second export collected |
| Preservation in the retained collection review | All 419 original files unchanged | All 384 original files unchanged |
| Reported input/output tokens | 341,576 / 11,631 | 160,435 / 3,507 |
| Calculated cost using the retained price record | USD 0.0399731 | USD 0.0177970 |

The calculated pair cost is USD 0.0577701 before taxes; this is not independently observed billing. Billing for the Haiku stress work remains deferred. The principal's ten-turn reading said the answer was largely indistinguishable from one completed in time, while noting that the manager's own need to close was another indicator. That is one reader's observation, not a mechanically established property of the prose or a general reader result.

**Disposition:** The two placements and their custody work are complete. The narrow recorded-work comparison is available; the original rendering question includes an attributed reader response. Whether different guidance would make the auditor record earlier or submit in time remains unresolved. Nothing in this result selects another trial.

The original launch output for each trial says `outcome: failed`; the session reports `observed_review_required` and one failed audit. Later review still says `not_submitted`, correctly, alongside `seal_actor: manager`, `delivery_verified: true`, and `closed: true`. These are different observations. A revised outward report must explain their relationship without changing the old records or treating manager closure as submission.

## Example B: successful submission without paging

### Proposal example

This reconstructs the pagination encounter from the same historical commission. **Question:** When a log is larger than one read, does the auditor use the supplied next-page affordance, and can its returned account distinguish a complete scan from a partial one? Supply a short and a long synthetic log with known counts, failure entries and last entries; ask for those facts through the ordinary material tools. Preserve alternative access routes so the encounter can reveal whether paging is needed at all.

Use the same model, default effort and study build as Example A. One placement; 40 turns, 6,000,000 cumulative input tokens, 32,000 output tokens and a 2,700-second watchdog; no continuation or replacement. The dated estimate was USD 0.093 expected and USD 3.08 at full allowance/high-tier rates. Authority belonged to the original five-run commission. To observe paging use, a reply must offer continuation and a later call must follow it. Correct answers alone cannot establish that. If the model obtains the requested facts through another route, record that route and leave the paging-use question unexercised.

### Two candidate ordinary views of the same result

The following are alternative presentations, not two experiments or tested reader preferences. Both use the same retained evidence and preserve the original question.

**View 1 — operations first**

> One placement ran and submitted. Delivery verified; audit closed and collected. Procedural review reports no failures within its checked scope. Usage: 9 turns, 196,980 input tokens and 5,733 output tokens; calculated cost USD 0.0225645, billing observation deferred.
>
> Paging coverage: unexercised. All seven read/search replies reported complete; none offered a next-page call. The auditor used list metadata, complete searches and a tail read starting at byte 214,000 of the long log. The local review found all six requested answers correct. The auditor stated that it had not read every line of the large file.
>
> No custody action remains. A new paging encounter would need a separately chosen design and authorization.

**View 2 — the experimental question first**

> **This encounter did not test use of the next-page affordance.** No read/search reply offered it. The auditor obtained the requested facts through metadata, complete searches and a tail read, then submitted. The local review found all six answers correct; the auditor's account disclosed its unread middle pages. Successful answering and successful submission therefore leave the paging-use question open.
>
> The recorded interaction supports the route and lack of a paging opportunity. The answer/key comparison and reading assessment are the local reviewer's work. The principal found the account legible and explicitly did not check correctness. These are separate contributions to the result.
>
> One placement; 9 turns; 196,980 input and 5,733 output tokens; calculated USD 0.0225645. Delivery, close and collection are complete; billing observation is deferred. No action is requested to finish this encounter. A further design could test responding to a deliberately supplied continuation, but that would answer a narrower question than spontaneous discovery in the existing tool world.

For either view, the inspectable evidence identifies the exact input/build, live capture scope, tool calls, returned answer, review and later collection. This was one encounter on an unqualified build. The live provider exchanges are Stewart-owned captures, not an independent TLS witness. The result supplies no general model capability or qualification claim.

The distinction between *no opportunity*, *opportunity offered but not used*, *used successfully*, and *unknown because evidence is missing* is necessary to make this study useful. It need not become four large categories imposed on every study. One open design question is how much study-specific meaning the apparatus should represent and check.

## Where the existing reports come from

This is a first-pass map of the reporting path at `b378d8e`, not an exhaustive field-by-field inventory. Code locations are supplied for local follow-up; the descriptions here are sufficient for this consultation.

| Producer / observation | Record or view | Consumers and consequence |
| --- | --- | --- |
| Host binding and launch, [c10.py](../apparatus/c10/c10.py), `bindings` / `launch_batch` | Bound packet, host launch result, process exit, credential handoff and host scan | Live admission checks exact bindings and a matching rehearsal. Host output copies the session outcome; a nonzero container exit or failed/not-started count becomes a generic launch failure. |
| Container intake, [batch.py](../apparatus/c10/batch.py), `prepare_batch` / `Audit.intake` | Plan, per-audit binding, independent input copies and receipt readbacks | Reviewer checks accepted input against the witnessed copies. Each audit's export needs enough identity to stand on its own; a binding is not redundant merely because the host has another copy. |
| Per-audit execution and review, `Audit.execute` / [verify.py](../apparatus/c10/verify.py) | Review before close; procedural outcome, ending, usage, selected work, seal/delivery/close facts | Checked auditor submission permits ordinary automatic close. The review returned to the batch was taken before that close; its `closed: false` is not proof that the later export is open. |
| Batch controller, `execute_batch` | Session rows, counts and expected-observation checks | Live packets currently admit only `scenario: submitted`. An unsubmitted live run fails the expected-observation comparison and stops later placements. Rehearsal separately accepts its deliberately unsubmitted controls. |
| Export, `locked_export` / `export_snapshot` | Immutable export metadata and archive, or withholding/failure | Collection requires observed stopping, evidence membership and credential checks. `review_batch` reads exported snapshots; withheld material stays private. A missing export cannot be replaced with an assertion that there is no work. |
| Later operations, [operations.py](../apparatus/c10/operations.py), `operate`; host `host_control` | Separate status/close/inspect/collect observations and new export | Explicit manager acts advance custody; they do not alter the old launch report. Known raw failures need controlled explanations because arbitrary exception text may contain private evidence. |
| Recomputed snapshot review, `review_batch`; [check_review.py](../apparatus/c10/check_review.py), [check_operations.py](../apparatus/c10/check_operations.py) | Batch/snapshot reviews and comparison results | Rehearsal admission, operator comparisons and reviewer controls consume particular outcome words and facts. Changing those words requires changing the decisions that consume them. |
| Local study reading and synthesis | Retained `review/result.json`, interaction findings, principal responses, assessments and billing dispositions | The principal and local agent interpret the study. These records are not all generated by the reusable launcher and have no common resolution rule. In these examples, an earlier `pending` list still names readings that later files show occurred. |

The shared sanity launcher and helpers also report outcomes; any chosen implementation must account for their consumers. Keychain diagnostics already use controlled classifications, while some other failures are deliberately flattened. The rewrite must preserve privacy without discarding actionable causes. Repeated declarations such as `model_qualified: false` can be reconsidered; live versus fake witness scope and native versus Linux observations must remain attached to the claims they qualify.

## Three implementation choices

| Shape | What changes | Benefit | Cost or unresolved question |
| --- | --- | --- | --- |
| Local report repair | Improve names, explanations, observation times and next actions in each existing producer; make expected experimental endings expressible where needed. | Smallest operational change; existing evidence and operator route remain familiar. Can support View 1 or View 2. | The experimenter still joins procedural records and study interpretations. Merely renaming `failed` cannot change the submission-only batch policy. |
| One assembled experiment report | Retain observations at their current boundaries; assemble a versioned account of named snapshots, trials, spending and outstanding actions. Carry study findings as attributed contributions, with the readable and machine views drawn from the same account. | Gives the conversation one object and can replace duplicated outward summaries. Later reports can resolve actions while preserving their earlier state. | Must define who supplies each claim, how observations resolve or conflict, and what makes the report usable without its original directory. It can become another layer if old summaries remain competing public answers. It does not itself change launch authority or choose the next experiment. |
| Experiment runner | Make the block an executable plan of trials, observation rules and allowed next operations, generating its report as it proceeds. | Aligns expected outcomes with execution and could later reduce routine handoffs. | Larger change; pressure to encode scientific interpretation as pass/fail. Choices about adaptive work, paid execution and delegated custody require the deferred agreement. Its reporting part can be considered now; future authority cannot be assumed. |

My provisional preference is the assembled report, with the experimental question first. I would give it authority over its declared evidence selection and mechanical derivations, while identifying interpretations by author and basis. That is a candidate, not a settled architecture. A simpler arrangement of a compact technical result and a clearly linked experimenter's account might preserve the distinctions with less new machinery.

There is also a design risk in promising “largely unambiguous outcomes”: we could choose only questions convenient for the apparatus to classify. Example B supplies a useful observation about an alternate route while leaving the intended mechanism untested. The report should help decide what that means for the next design, without manufacturing either success or failure or requiring every answer to be reread by the principal.

## What remains open for consultation

1. What is the smallest coherent exchange that lets the principal agree a bounded study and interpret what comes back? Which distinctions need ordinary visibility, and which can remain inspectable?
2. Should the checked observations and the experimenter's interpretation live in one account with explicit attribution, or in separate linked artifacts? Where would either arrangement distort responsibility or make the reader reconstruct too much?
3. How much should the apparatus know about the study question and its possible outcomes? Which parts of the pagination example justify reusable structure, and which should stay in the experimenter's short account?

The next local work will select a reporting structure, exercise normal and adverse cases, then implement and rehearse it. Product vocabulary changes and the autonomy agreement retain their separate decisions. We are seeking design guidance while the exchange is still cheap to change.

## Source basis and limits of this preparation

The examples use `.scratch/haiku-stress-01/predictions-01.md`, its pre-turns-8 amendment, the consumed packets, `round-agreement-01.json` and the dated `cost-01.json`. The actual observations come from `.scratch/haiku-stress-live-01`, `.scratch/haiku-stress-live-02` and `.scratch/haiku-stress-live-03`: each run's `host/RESULT.json`, `container/RESULT.json`, second export, `review/result.json`, and case-specific interaction, cost, reading-binding and later reading records. These paths identify local evidence; no external reader is expected to open them. Relevant facts are included above. The original predictions concerned what a manager could tell from the return, so the original reader observations remain part of those studies.

For this briefing, a read-only extraction checked the three export digests and packet identities, nine delivered-member copies against their exports and reading bindings, three interaction operation counts, and three usage agreements across saved reviews: 21 checks passed, none failed. This is consistency checking of retained records, not a new qualification run or independent observation of the provider. The extraction, selected observations, 64 source-file identities and command outputs are retained in `.scratch/apparatus-report-design-01/`. No historical report, accepted input or delivered answer was changed. The proposed views are authored here and are not outputs of an implemented report generator.
