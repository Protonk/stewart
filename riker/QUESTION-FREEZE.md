# Stewart Helper — Handoff

This thread is for a request from a local agent working on Stewart. I am passing the agent's message to you.

Treat the message as a request for assistance, not necessarily as a complete or correct account of the circumstances. The agent has its own working context and may receive your response through me.

Respond to the problem as you understand it. Your response may be forwarded to the agent verbatim. There is no standing expectation that you review, approve, criticize, or audit its work.

## Message from the agent

We are preparing Stewart for its first live model tests. We want to freeze a small set of question families, then work through their material guidance and what submission tools can meaningfully check. What important questions should we interrogate before testing with a read-only auditor? Please concentrate on whether these commissions can yield useful work under that boundary, and what would help us discover otherwise. This is a design consultation, not a request to execute anything or approve a release. The relevant current context is below; no repository access or attachments are needed.

### The five we have chosen

1. **Open inquiry:** address the supplied question and give an account of what the materials support and leave unresolved. Broad requests have an ordinary route without justifying why they avoided another family.
2. **Inquiry framing:** formulate a working question from the manager's concern, explain its relationship to the original request, and investigate it in the same commission. The original question stays intact.
3. **Comparison:** relate named alternatives to a criterion, distinguishing the manager's criterion from the auditor's interpretation. Unequal evidence or inability to compare is a legitimate result; no winner is required.
4. **Claim examination:** examine support, counterevidence, assumptions and qualifications for a stated claim. Neither a defective premise nor a repair is a required result.
5. **Experimental inquiry:** use the supplied subject material and captured primary sources to develop an informative experiment. The maintainer specifically wants the research material to help the auditor discover what is worth testing, without requiring the manager to supply a finished hypothesis or test specification. Its precise read-only deliverable is still to be settled.

The first three are implemented. The last two are selected directions, with their detailed instructions and tools still to design. Five is the intended maximum for this work. We are not seeking an expanded taxonomy. Recipes within a family can give more specific guidance.

### The actual boundary and the tension

Stewart is currently a Rust audit service using a direct Messages API loop. The manager supplies a question, family, selected UTF-8 text files and cumulative model-turn/token limits. The auditor can list, read and search those captured materials and record, revise, prepare and submit its answer, including free-form text or byte artifacts. “Read-only” means no shell, project execution, general filesystem, network retrieval or delegated investigators; it does not prohibit authoring answer artifacts. There is no mid-run manager conversation or mechanism to fetch additional evidence. Supplied logs and test reports are their authors' claims, not executions the auditor witnessed.

The current contract states: “It neither executes project code nor fetches additional material.” We are retaining that boundary for this work. The maintainer previously removed the Git-management part of custody because it was too easy to rediscover all of Git inside the application and make little progress. An executor or general workspace could repeat that expansion. Read-only operation may also help contain costs, but that remains an expectation to examine. The contrary concern is serious: it could exclude whole useful categories or return first drafts that make the manager repair the investigation afterward. We want to confront that tradeoff rather than declare read-only inquiry sufficient or useless in advance.

The motivating fifth-family example is a selected part of a Python application plus a captured copy of the relevant Python subprocess documentation. The source/application relationship should lead to an experiment, such as one examining the application's treatment of child-process timeouts. Today the auditor could reason from those materials and author a concrete experiment, specimen or script with predicted observations and limitations; it cannot run it. That is a working interpretation, not a settled final form. Captured primary sources make this family possible within today's boundary. A source link alone would not provide its contents. A future auditor with execution may give the family a different form; please distinguish ideas requiring that extension from improvements achievable now.

### Existing answer behavior

The first three families change instructions, recording-tool names and expected-section notices. Most recording tools currently take text, optional citations and an optional label. Missing kinds of entries are reported during preparation; they do not block submission. Empty answers are allowed. Citations are checked for location and exact quotation, never whether they support a conclusion. Stewart preserves the answer and attributes it to the auditor; it does not grade its reasoning. These are current deliberate choices, not claims that every resulting return will be useful. No live test has yet shown how well models use the arrangement. Procedural conformance and intellectual utility are separate questions.

### What would help us now

Please identify and prioritize a small number of consequential questions to settle or observe before moving into live tests. For each, say why it matters and give a concrete example or modest comparison that could change our view. Distinguish what needs a decision before a run from what a bounded live run could help us learn.

In particular, interrogate the useful promise of read-only experimental inquiry: what can count as a complete, useful return in its own right, what work necessarily stays with the manager, and when does the form merely conceal an unfinished investigation? Consider how to keep primary-source claims, reasoning about the supplied application, proposed experiments and supplied observations distinguishable. Also look for consequential gaps or overlaps among the five, and for material guidance that could prevent predictable repair without forcing managers to solve their question before commissioning it.

We will discuss concrete enforcement after freezing the question purposes. Flag any proposed check that actually changes the commission or pressures a substantive conclusion, rather than silently treating it as an engineering detail. Please add important issues our framing misses; you need not work through this message point by point or propose a comprehensive new apparatus.
