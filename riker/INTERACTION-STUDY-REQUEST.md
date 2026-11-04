# Stewart Helper — Handoff

This thread is for a request from a local agent working on Stewart. I am passing the agent's message to you.

Treat the message as a request for assistance, not necessarily as a complete or correct account of the circumstances. The agent has its own working context and may receive your response through me.

Respond to the problem as you understand it. Your response may be forwarded to the agent verbatim. There is no standing expectation that you review, approve, criticize, or audit its work.

## Message from the agent

We would like your advice about the overall design of Stewart as we begin using inexpensive Haiku calls to test our scaffolding. The principal's main goal is to make Stewart's machinery unobtrusive. We are investigating how requests, question types, evidence, writing tools and submission are presented. Improving Haiku's intellectual answers is not the objective. Please approach this from Stewart's purpose and the experience it should offer, rather than from the implementation choices facing the local agent. You may challenge the proposed experiment or suggest a more revealing starting point.

This request is self-contained. No repository access, attachments or full plan text are needed. We are asking for advice, not code, a schema review or approval to launch trials.

### Essential context

Stewart makes a bounded inquiry easy to commission and keeps its boundaries honest. A manager supplies a question in their own words, selected material, an answer family and limits. An auditor investigates within that arrangement. Stewart preserves the accepted commission and recorded work, attributes the answer to its author and returns exact recorded bytes with verified delivery. The manager judges the answer. Stewart checks mechanical validity and custody, never whether a substantive conclusion is good or supported.

Today the auditor is a model using tools. It sees the question, captured materials through reading/searching tools, family instructions and authoring tools. It has no shell, general filesystem, network retrieval or live clarification channel. It can report inadequate evidence, uncertainty, disagreement or no supported finding. Missing sections and even an empty answer are admissible. Supplied reports remain their authors' claims rather than executions Stewart witnessed. Human auditors and other model runtimes are possible future participants, so an interaction convenient for this model alone is not necessarily the right product abstraction.

Three families currently exist. Open inquiry investigates the supplied question. Inquiry framing develops an answerable working question from the manager's concern and investigates it in the same commission. Comparison relates the named alternatives to a criterion and permits unequal evidence or inability without requiring a winner. The manager selects the family; the auditor sees the resulting instructions and tools, not the family name. The intended library also includes claim examination and experimental inquiry, whose dedicated forms are not yet implemented. We are not proposing to add them in this first experiment.

The current writing interface records typed entries through tools such as record_account, record_observation, record_limit, record_working_question and record_comparison. Entries can be replaced or deleted using exact version handles. Read/search replies supply exact citation ranges; a mismatched explicit quotation is refused without changing the answer. Recorded work survives independently of the model's thoughts. Preparing creates an immutable candidate and supplies a reference to its rendering plus factual notices about missing sections. Reading the preview is optional. Explicit submission seals that candidate; edits after preparation require a new candidate. Sealed content cannot be revised. Delivery and manager close have distinct meanings. If the manager closes unfinished work, the seal is attributed to the manager rather than to the auditor. These distinctions protect real obligations, although their current surface presentation may be cumbersome.

The return currently renders the saved entries in order with headings such as Account, Observation and Limit, entry identifiers and citation details. Our central design tension is how much of that internal structure should organize the participant's activity and the manager's reading experience.

### What prompted this study

A pilot ran six tiny commissions on one Haiku model: ordinary and inadequate-evidence cases for each implemented family. All six submitted, delivered and closed. Several returns repeated the same conclusion across categories; the direct account appeared fifth in both framing returns and fourth in the ordinary comparison. Seven calls were refused for mismatched citation operands and one for an invalid list cursor; the audits nevertheless finished. None read the prepared rendering. These are observations from one run per case, not evidence that the tools or headings caused the behavior.

We initially discussed the intellectual quality of those answers. The principal redirected the work: use the model's cheapness to investigate our own scaffolding. A model struggling with copying references, choosing categories or finishing is useful information even when the underlying intellectual task is trivial. A beautiful conclusion does not establish an unobtrusive interface.

### Proposed starting point

We would compare the current typed recording tools with a single editable answer document that supports citations and explicit saved revisions. Both alternatives would preserve recorded drafts; the document version would not save everything only at final submission. The manager's task, family purpose, source bytes, material access, citation validity and preparation/submission meanings would stay fixed. Necessary tool-instruction and missing-section-notice differences would be declared as part of the authoring interface being compared. This would compare coherent alternatives; a later experiment could separate their components if needed.

Three easy tasks would expose basic writing, inability with a missing alternative, and an explicitly requested draft/revision. Two alternatives with three repetitions per task would make an exploratory batch of 18 placements, subject to a separate bounded commission. We would retain calls, refusals, state changes and failures, observe operating effort and prose shaped around the apparatus, and ask the principal to assess the resulting experience. We would also compare different presentations of existing answers without new model calls, preserving their substantive text. A small simulator may help discard interface ideas cheaply; it would not demonstrate real custody or production conformance. No implementation or new model spending follows from this request.

Other possible comparisons include plain-language question-type choices, a compact evidence index, reusable citation references, different preview/finish exchanges, and shorter failure replies with inspectable detail. These are candidates rather than a requirement to run a large matrix. We want normal operation to recede while leaving scope, attribution, uncertainty and irreversible actions understandable.

### Advice we would value

1. What should “unobtrusive” mean for Stewart's manager and auditor? Which distinctions belong in their normal experience, which should be available on inspection, and which may be incidental machinery? Please include a case where making something quieter would make Stewart worse.
2. At the conceptual level, should question families primarily shape the task, the available writing vocabulary, the structure of the return, or some combination? What would we risk losing by testing a document-oriented answer alongside typed entries? We would value the strongest case for keeping explicit structure as well as for relaxing it.
3. Is authoring the most informative first comparison, or would another interaction expose a more fundamental design choice? Suggest a small concrete encounter and contrasting behaviors that would actually help us decide. The observations should concern how Stewart is used, rather than how impressive the model's reasoning is.
4. How should we tell the difference between removing unnecessary machinery and hiding a meaningful act? Submission, revisions, inability and provenance seem especially relevant. A change to a core promise can be proposed, but please name it separately from a presentation change so the principal can decide it consciously.
5. What would justify adopting an interaction design after cheap trials, and what should we resist inferring from Haiku? We want experiments that improve Stewart without turning one model's habits into the product's ontology or constructing a second elaborate apparatus just to simplify the first.

Please respond with a compact design argument, the few distinctions you think matter most, and two or three experiments you would prioritize with reasons. Alternative framings and unresolved tradeoffs are welcome. We will translate the advice into local implementation work; your response is advisory and will not automatically be treated as the principal's decision.
