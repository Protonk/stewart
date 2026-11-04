# Auditor-facing study scope

Scope clarification supplied by the principal on 2026-11-04, following the Riker discussion. The principal had also directed the local agent not to focus on developing or examining the proposed Haiku problems. The clarification below is retained as supplied; it leaves the new authoring interface and experimental sequence open.

I'd like to clarify one of our principal goals for the upcoming Haiku experiments, particularly the part that concerns Stewart's auditor-facing interface.

We're going to keep the manager side deliberately uninteresting for now. We'll fix the questions, question families, evidence, and other commission settings locally, so that we can concentrate on the auditor's experience. You may operate as the manager for these runs, but improving manager workflows isn't the present objective.

What we particularly want to investigate is **how much scaffolding Stewart should expose to the auditor, how it should present that scaffolding, and how much should be included in the tokens the auditor always receives.**

The ideal early experiment would involve a question that Haiku can answer adequately, including recognizing uncertainty, a need for evidence, or a need to reframe where appropriate. But its submission might reflect Stewart's recording apparatus too strongly: repeating conclusions under different headings, organizing prose around tool categories, or spending unnecessary effort satisfying a structure that isn't helpful to the inquiry.

We could then change the authoring tools, their descriptions, the required or suggested structure, and the information supplied with tool responses, observing whether the auditor produces an equally sufficient answer with less mechanical effort and less visible influence from Stewart's machinery.

This isn't necessarily a campaign to minimize tokens or tool calls. We want to find a useful balance between **discoverability and verbosity**. Some instructions or distinctions may be essential for the auditor to operate effectively; others might be better communicated when relevant, made available on inspection, or omitted from the ordinary interaction. Removing too much could make the tools harder to discover or lead to more failed calls and confusion.

The scope includes the auditor's initial context, family instructions, tool descriptions, evidence presentation, citation handling, recording and revision tools, and preparation/submission exchanges. We'd like to be able to experiment with these as a coherent interface rather than treating their current forms as fixed.

We should preserve Stewart's actual obligations around custody, attribution, evidence integrity, and explicit submission. We're not trying to improve Haiku's reasoning by prescribing its intellectual procedure or steering it toward reference conclusions.

A useful working habit might be to connect each experimental change to an observed source of friction or a plausible opportunity for simplification, and then look at both the resulting answer and the auditor's interaction with Stewart. We haven't settled how formal that account should be, and I don't want to create an elaborate experimental bureaucracy.

Our initial problems will probably include a manageable code-and-evidence inquiry in `frsrr`, with variations in evidentiary completeness or consistency, and a deliberately saturated numerical question to observe how the interface accommodates partial answers and inability.

The most revealing result may be that Haiku answers correctly both before and after an interface change, but afterward writes more naturally, encounters fewer mechanical obstacles, or needs less scaffolding in its context.

That's the direction we're considering. In particular, I'd welcome your observations about which parts of the current auditor-facing machinery seem to occupy disproportionate attention, and ideas for presenting the necessary distinctions more economically. Nothing here commits us to a particular new authoring interface or experimental sequence.
