# Conditional audit protocols

These protocols support the [question recipes](QUESTION-TYPE.md). They do not
select a question or grant any capability. The maintainer supplies the concrete
scope and grants in the assignment; the auditor reads only the applicable
section when that capability is assigned.

- [Experiment protocol](#experiment-protocol): construction, or construction
  plus execution, within an explicit preservation boundary.
- [Research protocol](#research-protocol): assigned external sources that can
  change a premise, control, interpretation or scope.

For the tool-facing experiment object and release/attempt receipts, see
[Stewart experiments](README.md#optional-experiment-lifecycle). Reading a recipe or declaring a
scratch path alone authorizes neither construction nor execution.

## Experiment protocol

This section is the canonical construction/execution protocol. The maintainer
completes the following authorization in `PROMPT.md`; the auditor reads this
section when either capability is assigned. Replace the placeholders:

```markdown
## Experiment authorization
Permission: <construction only OR construction plus execution>.
Target and variation: <contract/observable, admissible inputs and mutations,
hypothesis space, exclusions>.
Protected state: <state, equality/behavioral criterion, when it must hold>.
Construction area: <declared scratch paths, mutable copies, output locations>.
Execution allowance: <none OR named commands/bounded templates, interpreter,
environment, working directory, inputs, dependencies, permitted side effects>.
Action bounds and stops: <permitted trial scope/count where side effects require
it; stop on failed preservation checks, unexpected effects, or tool failure>.
Preservation evidence: <baseline and independent checks, who runs them,
receipt paths>.
```

When execution is granted, the assignment block also carries a matching
`stewart.experiment-grant/2` experiment object naming the script, frozen
declarations, output area, protected manifest, interpreter and environment
policies, and one Python-script command template. The tool validates that
object and never this prose. The template begins with `{interpreter}`, optional
`-B`, then `{script}`; shell wrappers and other interpreter modes are unsupported.
A child imports `Ledger` from `_stewart_ledger_v1`, supplied by the pinned
runtime. Do not copy Stewart into the project or use that reserved name for a
project module. Legitimate imports from the script directory and worktree root
remain available in that order for names not preloaded by bootstrap/ledger
startup; standard-library names such as `json` stay bound to their loaded
modules. The reserved ledger module is supplied only in the initial process,
not subprocesses or multiprocessing spawn workers. Keep its import and ledger
writes in that process, under `if __name__ == "__main__":` when using spawn.

Two facts about the wrapper bind the construction. It creates the output area,
empty, and the attempt's `HOME` outside it before it launches the child, so the
script must accept an existing empty output directory; a script that requires
the directory to be absent fails on entry and spends the single invocation. The
child's `receipt.json` is one JSON document with no further schema: the wrapper
records its keys and digest and retains the bytes, nothing more.

Construction permission alone permits no trial execution. Execution covers only
the supplied commands and bounds, including preservation checks. The workspace
policy and assignment determine which tests, project commands and side effects
may be granted. No recipe supplies permission to install dependencies, mutate
Git, change production code or regenerate evidence.
Arrange dependencies in advance and account for caches, temporary files, and
subprocess effects. If effects cannot be bounded, assign construction only and
have the maintainer run proposed trials.

Action bounds constrain permitted effects. Add an operational command timeout only
when a particular command needs one. Missing constraints leave the corresponding
action unauthorized; report the gap without broadening the grant. No further
confirmation is needed inside a complete grant. The helper neither approves
nor enforces authorization prose.

Before each trial, record the hypothesis and predicted distinguishing
observation. Retain input identities, specimens/code, exact commands/environment,
stdout/stderr, exit status, and preservation receipts. Hypotheses may change
within the granted space; record why.

A counterexample requires both an admissible failure of C and evidence that S
met its criterion. Include the checker/reference data in S where their stability
matters. An experiment's success flag or unchanged Git status over dirty files
does not establish preservation. Restoring state after mutation does not prove
it stayed undisturbed.

Stop and preserve evidence on unexpected effects, failed preservation checks,
or tool failure, including assertions and crashes. Distinguish a predicted target
failure from a broken harness. An unmeasured/violated preservation criterion
limits the observation; it is not the requested counterexample. Failure to find
a counterexample does not establish the contract universally.

## Research protocol

Research enhances any question when it can change a premise, control,
interpretation, or scope. A source summary alone does not answer the question.

The maintainer supplies specific sources, each source's purpose, applicable
versions, required authority, and allowed reference-following scope. Prefer
primary sources for claims about their own systems and verify ownership;
a URL in a prompt does not establish authority. Avoid requiring research when
local evidence answers the question.

The auditor reads assigned sources even when familiar, cites retrieved pages
and relevant sections, and records access date and applicable version.
Separate source statements from their application to the audited project and from hypotheses.
Inaccessibility, undocumented behavior, or a version mismatch is a visible gap;
memory cannot substitute for retrieval, and documentation alone does not
establish observed host behavior. Research grants no construction or execution
permission and stays within the assigned question.
