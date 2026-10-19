# Orchestration plan

Status: pending. Nothing in this plan is implemented yet. It is the starting
point for building orchestration on top of the interfaces Stewart ships today,
and it depends on nothing outside this repository: read `AGENTS.md`, the
shipped manual (`src/stewart/resources/README.md`, especially "Discovery,
selection and continuation" and "Recorded resources and closeout") and this
file. `tests/test_orchestration_plan.py` checks that every command, flag, API
name and schema cited here exists; keep it passing as this plan changes.

## What orchestration means here

An orchestrator is a caller (an agent or a program) that carries one or more
audits through Stewart's supported operations without a person copying
identities between commands, and that survives its own interruption. It
selects audits, consumes the actions Stewart derives, submits keyed mutations
whose substantive inputs a person supplied, checks completion from recorded
evidence, retries safely, and retires the resources an audit used.

It is not a launcher, scheduler, harness driver or general command recorder.
Stewart still launches nothing and grades nothing. Every judgment the manual
assigns to the manager stays a manager input: the question and prompt, launch
and stop acknowledgments, triage claims, decisions and gap dispositions,
follow-up answers, retention and export selections, disposal decisions,
abandonment, manual-retirement acknowledgments, resuming uncertain work, and
any runtime handoff.

## Supported entry points

Every entry point below exists. Use the JSON envelope `stewart.result/3`
(`ok`, `exit_code`, `result`, `error` with `reason`, `message`, `retained`,
`next_steps` and, for `implementation_mismatch`, `handoff`) or the same
dictionaries from `stewart.api`; never parse prose. Exit codes: 0 nothing needs
attention, 1 action within the caller's role, 2 refused with nothing done,
3 something does not verify.

| Need | CLI | API | Result schema |
| --- | --- | --- | --- |
| Find recorded audits, resources and request keys | `stewart discover` | `api.discover` | `stewart.discovery/1` |
| Select one audit as a kept reference | `stewart select` with `--audit-id` (and global `--workspace`) | `api.select`, then `api.bind` to revalidate; `api.load_reference` reads a saved file | `stewart.selection/1` holding `stewart.audit-ref/1` |
| Inspect stage, blockers, evidence and actions | `stewart status` with `--ref` | `api.status` | `stewart.status/13`, `stewart.status-draft/1`, `stewart.status-closed/2` |
| Record a draft or an existing workspace | `stewart init` with `--replace-prompt`; `stewart register` | `api.initialize`, `api.register` | init result, registration record |
| Prepare | `stewart prepare` | `api.prepare` | result carrying a lifetime-bound `reference` |
| Collect, review, retain, export, resume | `stewart collect`, `stewart triage-draft`, `stewart triage`, `stewart retain`, `stewart export`, `stewart resume` | `api.collect`, `api.triage_draft`, `api.triage`, `api.retain`, `api.export_evidence`, `api.resume` | operation results |
| Check a keyed request | `stewart request` with `--key` | `api.inspect_request` | `stewart.request/1` |
| Describe closeout without writing | `stewart close` with `--plan` | `api.close_plan` | `stewart.closeout/1` |
| Close an audit | `stewart close` with `--actor` | `api.close` | close result with `closeout` and `resources` |
| Record and retire resources | `stewart resource` actions `create-worktree`, `create-branch`, `create-directory`, `enroll`, `associate`, `acknowledge`, `show`; `stewart close` with `--resource` and `--dispose` | `api.create_worktree`, `api.create_branch`, `api.create_directory`, `api.enroll`, `api.associate`, `api.acknowledge`, `api.show_resource`, `api.close_resources` | `stewart.resource-view/1` for show |
| Explain a different writing implementation | `implementation.handoff` in discover, status and refusals | `api.runtime_handoff` | `{state, argv, env}` or `{state, missing, diagnostics}` |

Global options that carry bindings: `--ref` (a saved `stewart.audit-ref/1`),
`--lifetime` (bind a session lifetime), `--request-key` (bind intended work)
and `--resume-request` (explicitly continue a partial close). Every status
action carries `operation` (the API name), `operands` (record names and the
digests read for that view) and `argv` already bound with `--lifetime`.

## Real gaps

These are not implemented and must not be assumed:

1. **Action inputs are literal placeholders.** Status actions carry tokens such
   as `<name>`, `<response.json>`, `<reason>` and `<prompt-commit>` in their
   argv. There is no machine-readable description of which inputs an action
   needs; an orchestrator must map each placeholder to a person-supplied input
   explicitly. A structured `inputs` list on actions is a candidate first
   extension.
2. **No action executor.** Stewart offers argv and API names, not an `apply`
   function. Keep it that way: an orchestrator maps `operation` and `operands`
   to the documented API call (or runs the argv) and owns that mapping.
3. **No change notification.** Progress is observed by polling `stewart status`
   or `stewart discover`; there is no event stream.
4. **Only keyed work is exclusive.** Request keys and resource claims are
   exclusive; two orchestrators issuing unkeyed mutations on one audit can still
   interleave (for example two unkeyed close reruns). Orchestrators must always
   use keys.
5. **In-process writers record no invocation.** Records written through the
   Python API carry no `invocation`, so after the code changes their handoff is
   `unresolved` with `missing: ["invocation"]`. Run Stewart through the isolated
   CLI (or a retained deployment) when a later handoff matters.
6. **Auditor stop is never observed.** `collect` needs the stop kind
   acknowledged by whoever stopped the auditor; Stewart cannot infer it.
7. **Partial requests other than close need a person.** Only `close` (and
   `close --resource`) resume under the same key; any other `partial` request
   requires an explicit decision and a new key.

## Caller journal

The orchestrator keeps its own durable journal; Stewart's records stay the
custody truth and are never copied into it.

- Before submitting a mutation, append an exclusive journal entry with a fresh
  request key, the operation, the reference file's digest (or the explicit
  coordinates) and the semantic inputs or their digests. Persist it, then
  submit with `--request-key`.
- On any interruption, re-read the journal and resubmit the identical request
  with the same key. A `completed` or `refused` result is recorded history; a
  `reserved` request runs; an `in_progress` one is still running elsewhere; a
  `partial` one is resumed only for close with `--resume-request`, otherwise it
  is surfaced to a person with its planned outputs (from `stewart request`).
- Keep only pointers in the journal: the key, the reference, and the identities
  Stewart returned (collection names and receipt digests, triage names, closing
  paths). Completion is checked by `stewart request` and `stewart status`, not
  by journal state.
- If the journal is lost, `stewart discover` lists every request with its
  exact key, operation, audit and state. A person decides which one carried the
  lost intent; the orchestrator never guesses.
- References are re-derivable: on `reference_stale` or
  `reference_checkout_missing`, run `stewart discover` and `stewart select`
  again and ask for confirmation when the lifetime changed. A reference grants
  no permission.
- On `implementation_mismatch`, surface `error.handoff` to a person. A
  `verified` handoff is an argv the person may choose to run; a recorded
  invocation is never permission to execute it.

## Authorization boundaries

The orchestrator may read anything Stewart reads (`stewart discover`,
`stewart status`, `stewart request`, `stewart close` with `--plan`,
`stewart resource show`) and may submit keyed mutations whose substantive inputs
came from a person: a filled triage response, a retention choice, an export
selection, a disposal decision, a close. It may resume a partial close with
`--resume-request` and retire a left-behind resource with `stewart close`
`--resource` once `stewart close` `--plan` (or `stewart resource show`) reports
it removable. It must not author prompts or triage judgments, acknowledge a
stop or a manual retirement on a person's behalf, abandon an audit, choose
among lost requests, or run a handoff argv without a person's explicit
decision.

## First implementation slice

One audit, one person, one machine: a journaled driver that carries a selected
audit from its first complete collection to its close.

1. Read a saved reference; `api.bind` it.
2. Poll `api.status`; when the person reports the auditor stopped, submit a keyed
   `api.collect` with the person's stop kind.
3. Run the `triage-draft` action for the collection the person names; hand the
   response to the person; submit their filled response with a keyed
   `api.triage`.
4. Submit keyed `api.retain` and `api.export_evidence` as the person selects.
5. Show `api.close_plan` to the person; on approval submit a keyed `api.close`
   (with `dispose` decisions the person made); resume it with
   `--resume-request` after interruption.

Acceptance builds on the existing lifecycle tests (`tests/test_journey.py`,
`tests/test_request_keys.py`, `tests/test_resources.py`,
`tests/test_close_regressions.py`, `tests/test_implementation_handoff.py`):

- kill the driver after each journal append and after each submission; restart
  from the journal only; the same keys return the recorded collection, triage,
  retention, export and close, and nothing is created twice;
- interrupt a close after its closing record; the restarted driver resumes it
  with the same key and finishes from the frozen inventory;
- delete the journal; the driver refuses to continue and lists the recorded
  requests from discovery for a person;
- make the reference stale (close and re-prepare a released audit ID); the driver
  re-selects only after confirmation;
- write the session with another build; the driver stops at
  `implementation_mismatch` and shows the handoff without running it.

## Expansion order

1. Structured action inputs (gap 1), so the driver no longer maps placeholders
   by hand; keep person-supplied inputs explicit.
2. Resource lifecycle: create the managed worktree and directory an audit needs
   with `stewart resource create-worktree` and `create-directory` under keys,
   associate further audits, and retire left-behind resources once
   `stewart close` `--plan` reports them removable.
3. Git recording as a deliberately narrow use case: journal the person-approved
   Git operations the driver performs around an audit (committing a drafted
   prompt alone, merging a managed branch so its retirement is eligible) with the
   refs observed before and after. This records Git activity the driver
   performed; it does not record every activity on the machine.
4. Several audits at once, still one key per intended operation, with the
   driver serializing work per audit and surfacing every shared-resource
   blocker from `stewart close` `--plan`.
5. Only then consider launch handoff integration; Stewart itself still
   launches nothing.
