# Audit assignment

## Question

Primary question type: Information preservation, the named section of the supplied
QUESTION-TYPE.md. Does the proposed custody-and-delivery implementation leg preserve
the decided authoring and manager obligations when translating them into an Opus
commission, or does fulfilling one of its promises require a capability it
explicitly defers?

The producer is the decided contract set in inputs/CONTRACTS.md. The consumer is
the incoming coordinator using inputs/NEXT-LEG.md to organize implementation.
Trace this finite intended route: verified original commission → recorded additions
and edits → auditor submission or manager collection → durable manager copy and
independent readback → supported re-entry after an interrupted operation. Examine
the deferred close/control boundary only where this route actually relies on it.

## Decision

The manager must decide whether to adopt the proposed bounded leg, amend its
scope/acceptance, or settle a named policy question before commissioning it.
Scope deferral can be legitimate; a future feature need not be implemented in
this leg merely because its contract is supplied. A missing mechanism can be an
implementation decision within settled policy. No particular conclusion is sought.
A supported no-gap, needs-evidence or reframe response is as admissible as a gap.

## Scope and exclusions

Read this PROMPT, the issued handoff and AUDITOR.md, and the pinned input_files
below. They are copied documentary snapshots of source 4636a67, mapped by
inputs/SOURCE-MAP.json; their original paths do not grant access to current files.
All paths in the following scope refer to supplied files under this workspace:

- inputs/CONTRACTS.md: use principles, commission-input acceptance, answer
  construction, manager receipt/closure, explicit grants, public status, close,
  holds and writer continuity as relevant to the named route. Other contracts
  are context, not instructions to expand the successor's responsibilities.
- inputs/NEXT-LEG.md is the candidate being assessed. The simplifications,
  authoring-boundary and return-completeness notes distinguish accepted policy,
  proposal, prototype evidence and open mechanism; preserve those distinctions.
- inputs/C-GUIDE.md states the existing C interface/limits; it does not establish
  the later answer-custody service. inputs/PROTOTYPE-RESULT.md is an attributed
  evidence account, not permission to inspect live specimens or rerun experiments.
- inputs/DEVELOPMENT-PLAN.md: read the current forward sequence, discussion and
  work register, stopping before “Test obligations and the unrun comparisons.”
- QUESTION-TYPE.md: the Information preservation section and chooser only.

Static inspection is authorized through file/search tools and explicit isolated
Python standard-library inspection (/opt/homebrew/bin/python3.14 -I -B -S) for
parsing, hashing or comparing the selected bytes. Matched search lines count as
reads. Run only the handoff's exact input-verification and declaration-helper
commands in addition to that inspection. No project execution, builds, tests,
network, Git-history inquiry, private manager/session reads, model/harness launches,
repairs or delegation. File references and links grant no extra reads. An essential
unavailable premise should be named, not filled by expanding the assignment.

Write only the report and declared notes directory. Keep notes/READ-ACCOUNT.md
for actual reads and scope/tool failures and notes/CLAIM-TRACE.md for the source
trace, distinctions and proposed comparisons. Keep original evidence unchanged.
Frozen Python manager/auditor rules govern this actual audit's custody; decided
successor departures govern the design subject. Do not import Python's staged
workflow as a successor requirement merely because this audit uses that writer.

## Evidence

The supplied sources are documentary evidence about promises, proposals and
bounded past tests. They are not a running implementation of the proposed leg.
Source identities establish which bytes were supplied, not whether claims are
true or whether an auditor read them. The manager opened the named producer and
consumer documents before issuing the question. No source code or runtime trial
is admitted for this assignment.

Choose your own distinguishing cases within the route. For a material suspected
gap, give a concrete sequence of permitted actions and any interruption or damage,
the first required distinction/obligation lost, and a nearby case that should
remain valid. Identify whether an implementation choice within scope could
discharge the concern. Assess whether the candidate's acceptance cases could
expose the failure. Findings must distinguish a contradictory promise, a genuinely
unsettled policy and a mechanism/qualification task the coordinator can own.

Use exact supporting passages. Distinguish documentary observations, hypothetical
failure sequences, the prototype's attributed observations and runtime claims
that require later evidence. A passing count is not service qualification, and
absence of a new test is not itself a demonstrated defect.

## Stop condition

Stop when the bounded route and its meaningful distinctions are accounted for,
or identify the exact missing premise that prevents that account. Return any
material scope gap, preserved distinction or unresolved premise with its consequence
for the manager's decision. For each material gap, propose the smallest scope/
acceptance clarification or policy decision that would address it. Do not expand
into a general review, fix the subject or require findings to justify the audit.
Complete the issued declaration helpers and return control for collection.

## Assignment metadata

```audit-assignment
{
  "audit_id": "opus-commission-boundary-01",
  "target_commit": "d38709668bc466769e8c5f71383aed9efa37cff7",
  "report_path": "audits/opus-preparation/reports/opus-commission-boundary-01.md",
  "input_files": [
    "audits/opus-preparation/inputs/CONTRACTS.md",
    "audits/opus-preparation/inputs/NEXT-LEG.md",
    "audits/opus-preparation/inputs/INTERACTION-SIMPLIFICATIONS.md",
    "audits/opus-preparation/inputs/AUTHORING-BOUNDARY.md",
    "audits/opus-preparation/inputs/RETURN-COMPLETENESS.md",
    "audits/opus-preparation/inputs/PROTOTYPE-RESULT.md",
    "audits/opus-preparation/inputs/C-GUIDE.md",
    "audits/opus-preparation/inputs/DEVELOPMENT-PLAN.md",
    "audits/opus-preparation/QUESTION-TYPE.md",
    "audits/opus-preparation/inputs/SOURCE-MAP.json"
  ],
  "scratch_paths": [
    "audits/opus-preparation/scratch/opus-commission-boundary-01/notes"
  ]
}
```
