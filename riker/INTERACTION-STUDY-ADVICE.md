# Riker advice on the interaction study

Relayed by the principal on 2026-11-03 in response to the [interaction-study request](INTERACTION-STUDY-REQUEST.md). The principal's accompanying assessment was: “I consider that to be keen advice here.” The relayed advice follows; it is consultation evidence, not an implementation assignment or spending authorization.

## Design position: Make the inquiry prominent, not the machinery

I would define unobtrusiveness as the ability to conduct, receive, and judge an inquiry without having to think about Stewart's recordkeeping, except when a meaningful obligation or boundary is involved.

That is not the same as minimizing tool calls, hiding metadata, or making the interface resemble ordinary chat. Stewart's distinctive value is that an inquiry can be commissioned under known conditions, its work preserved, and its return attributed and delivered without confusing custody with intellectual authority.

The central design distinction is between the work as experienced by participants and the work as preserved by Stewart. These need not have the same shape.

For the auditor, the normal experience should revolve around the question, available evidence, developing an answer, acknowledging uncertainty, and finishing. For the manager, it should revolve around the commission, what the auditor returned, what remains unresolved, and whether the obligations of custody and closure have been fulfilled.

Stewart should be nearly invisible when recording a thought. It should be unmistakable when somebody assumes responsibility for something.

I would therefore preserve three distinctions above all others:

1. Inquiry versus recordkeeping. Writing an answer is not the same activity as maintaining its custody history.
2. Intellectual outcome versus procedural state. An inquiry may finish without a finding; conversely, an unfinished inquiry may contain valuable findings. Neither should be disguised as the other.
3. Authorship versus custody. What the auditor claimed, what Stewart actually recorded or verified, and what the manager subsequently decided must remain distinguishable.

These distinctions belong in the normal experience whenever they affect interpretation or action. Exact version handles, internal identifiers, transport details, and most validation mechanics generally belong on inspection.

Making submission quieter could make Stewart worse. A smooth interaction that automatically seals a prepared draft, conceals that a manager rather than an auditor closed unfinished work, or makes a supplied report sound like an execution Stewart witnessed would erase precisely the accountability Stewart exists to preserve.

## Question families should shape the inquiry before they shape the writing

I would not make answer families primarily into report templates.

An open inquiry asks the auditor to investigate. Framing asks it to make a working question intelligible and then investigate that question. Comparison establishes alternatives and a criterion for relating them. These are differences in intellectual assignment, not necessarily differences in document anatomy.

A framing return should make its working question recoverable. A comparison should make clear what can and cannot be said about each alternative. But neither requires a fixed number of headings, and an inability to reach a conclusion should not create empty ceremonial sections.

There are strong arguments on both sides of the authoring choice.

The strongest case for typed entries is not that they produce better prose. They preserve distinctions the auditor might otherwise blur: source observations, its own judgments, limitations, and accounts of purported work. Individually cited and replaceable entries are also valuable when investigations stop prematurely. They provide stable units of recovery rather than one document whose changing paragraphs may invalidate references.

The strongest case for a document is that writing is itself a way of organizing thought. A good explanation may weave observations and qualifications together instead of depositing them into categories. The auditor can communicate in the order its argument requires. The manager receives an authored account rather than something resembling the database representation of one.

The risk in the proposed comparison is losing track of which advantages come from structure and which from the particular tools implementing it.

I would explore a distinction between the authorial artifact and its structured annotations and history. A document can have saved revisions, checked citations, attribution, and recoverable history without making the author write through categories. Equally, typed records can support a document-like editor. Neither approach requires two competing authoritative versions of the answer.

The critical question is whether typed categories express essential facts that cannot otherwise be preserved, or simply compel the auditor to write according to Stewart's internal vocabulary.

## Three experiments, in priority order

## 1

Start at the receiving end, without model calls.

Take existing returns, including one with the direct answer buried and another with inadequate evidence. Present the same authored material through the current rendering and a reader-oriented view that makes the response or inability immediately apparent, with provenance and detailed records accessible.

Ask the principal to identify what was found, what remains unknown, who authored the return, and what Stewart actually verified.

A successful presentation reduces reconstruction effort without creating greater certainty or authority than the original report warrants.

This comes first because it establishes what authoring should produce. An easier writer interface is of limited value if the manager still receives an awkward artifact.

## 2

Compare typed authoring with a revisioned document.

I support this experiment, but would begin with two discriminating encounters rather than treating all 18 proposed placements as necessary upfront.

First, commission a comparison in which evidence for one alternative is missing. Second, request an answer and then a substantial revision that changes its organization and citations.

Hold the source material, family purpose, citation guarantees, revision persistence, and submission rules constant.

Observe whether the auditor can express inability naturally, whether it repeats conclusions to satisfy categories, how much mechanical repair is necessary, whether references survive revision, and whether the resulting work remains attributable and recoverable.

The most interesting result would be a tradeoff: for instance, a document produces a clearer account but obscures whether a passage is an observation or the auditor's interpretation. That would identify a genuine design problem, rather than merely declare a winner.

## 3

Test the moment of commitment.

Give the auditor a saved answer, have it prepare a candidate, then introduce a needed correction before submission.

Compare the present prepare/preview/submit exchange with an interaction centered on explicitly submitting a named saved revision, with inspection available but not compulsory. Both must preserve an immutable submitted candidate and the same custody history.

Watch for the wrong revision being submitted, attempts to edit sealed content, unnecessary preparation cycles, and misunderstandings about whether finishing requires a substantive finding.

A related manager-facing example should distinguish an auditor's completed submission from a manager's closure of unfinished work.

The question is whether the extra steps protect informed commitment or merely expose internal state transitions.

## Removing machinery versus hiding acts

A useful test is: If this distinction disappeared from the ordinary interface, could a participant reasonably misunderstand what they had authorized, accomplished, received, or become responsible for?

If yes, the distinction is consequential.

For example, replacing an entry handle with an intelligible editing gesture is a presentation change. Retaining the internal history while making citation repair less cumbersome is also a presentation change.

Silently overwriting prior revisions, relaxing explicit quotation verification, treating preparation as submission, or presenting an independently generated summary as the auditor's exact recorded words would change substantive guarantees. Those should be proposed separately, not smuggled into interface simplification.

Similarly, a compact notice that a citation's quoted bytes do not match is useful. A notice saying the evidence was verified would be misleading if Stewart checked only the quotation rather than its truth or relevance.

The system should be quiet about how it records an action, not about what the action means.

## What cheap trials can establish

Haiku can expose friction. It can reveal repeated attempts, copied-reference errors, irrelevant tool use, category-induced repetition, and confusion over finishing. It cannot establish that a structure is inherently natural, that an output is intellectually sound, or that humans and other runtimes will behave similarly.

I would adopt a design when it demonstrates three things:

- It reduces observable effort or misunderstanding across more than one encounter, not merely tool count in a single run.
- It preserves the original custody, authorship, citation, and revision guarantees under adverse as well as normal cases.
- It remains intelligible when considered from the positions of a human auditor and a manager, not just the particular model used in testing.

A handful of inexpensive placements can justify a prototype and identify failure modes. They cannot justify general behavioral claims. A small set of fixed scenarios, saved transcripts, mechanical regression checks, and the principal's direct judgment should suffice initially. I would avoid building a comprehensive simulator that reproduces Stewart's entire state machine just to evaluate alternative interfaces.

## The unresolved design choice

I think the important choice is not ultimately between typed entries and free-form documents.

It is whether Stewart's conceptual categories should be the language in which auditors must compose or the distinctions Stewart can preserve and make inspectable around what auditors compose.

The first offers explicit structure and easier classification. The second offers more natural authorship and greater freedom across future question families, but demands care in preserving provenance and the meaning of partial work.

My inclination is toward the second, provided its custody guarantees are real. I would resist forcing a normal answer into a taxonomy merely because the taxonomy is useful for storage.

That suggests a guiding principle:

Keep intellectual freedom in the inquiry, precision in the record, and explicit consent at the boundaries where responsibility changes.

If Stewart can maintain those three properties while letting the manager read a straightforward answer—or an equally straightforward account of why no answer was possible—it will have become meaningfully unobtrusive.
