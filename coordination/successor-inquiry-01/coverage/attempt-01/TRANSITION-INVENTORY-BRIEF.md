# Finite legacy transition inventory — proposed next commission

Status: prepared, **not dispatched**. No live population has been identified or inventoried. This brief asks for a bounded read-only account before any operational retirement commission. It is based on `CONTRACTS.md:209–234,1079–1136`, `DEVELOPMENT-PLAN.md:88,775–829`, frozen `AGENTS.md` custody rules and source revision `250d494262374007302ea9765399cb27dce90a34`.

## Purpose and decisions the inventory serves

Identify what an explicitly selected Python population still undertakes, which writer can act on it, which evidence can be interpreted independently, and the disposition needed before two distinct gates:

1. **Before the first successor close (F6):** stop new admissions to the transitioning Python population and close every live Python audit in it under the Python implementation that owns it. A read-only record inventory does not itself establish that an auditor/tool/descendant is stopped.
2. **Before withdrawing those Python writers (F7):** resolve or explicitly dispose of the population's independent resources and claims, runtime recoveries, partial requests/publications and other recorded undertakings. Closing audits is insufficient. Completed independent products may remain historical evidence; they do not have to be destroyed or converted to withdraw the writer.

The inventory must not create removal authority, convert a receipt, replay uncertain execution, restore a successor executor or decide cross-writer mutation/export. Those remain separate decisions/commissions. Invalid evidence and unresolved operations stay explicit, never counted as completed to satisfy a gate.

## Pre-dispatch inputs that are presently missing

The coordinator obtains and records these from authorized context or the principal before dispatch; no worker searches neighboring projects, home directories or private stores to fill them:

- A literal allowlist of repository/Git-common roots and workspace identities in the transitioning population, including whether the whole named common-directory store or only specified workspace/lifetime records are admitted. Shared common storage can contain unrelated audits and resources: repository path alone does not resolve that scope.
- Explicit permission to read the named private custody roots and a finite record-family/depth/volume bound. Begin with one named population manifest; stop and report if a referenced location/family lies outside the allowlist, rather than recursively expanding it.
- Named audit IDs **and lifetimes where available**, draft/closed contexts and any completed package locations whose later reading is the consumer. No selection by newest, current directory or installation. If aliases are ambiguous, keep them ambiguous until explicitly selected.
- Which currently available Python writer/deployment/interpreter identities may be inspected, and whether any later operation by them is authorized. Read-only inventory does not launch a writer. The writer's recorded location is a locator to verify safely, not executable permission.
- Whether the inventory may record external resource/output identities and inspect named completed publications. It may report unapproved locators without following them. Destination verification for a named transition/reader consumer is not a new service policing all published files.
- A cutoff/observation time and the actor who can stop new **init/prepare admissions and new independent resource undertakings** to this bounded population. The admission stop is an operational transition arrangement, not a product feature inferred from this brief. Record allowed remaining completion/preservation work separately.
- Evidence destination outside every contemplated disposal and its retention/review owner. Keep source records unchanged. No live writer is presumed absent because no reply or process is visible.

Current limitation: this assignment has no actual authorized population manifest, store roots, live-process facts or finite list of legacy writers. “The repository records no non-test resource use” in Core A is a documentary observation, not proof of an empty live population.

## Proposed worker boundary and outputs

Read only the allowlisted records and explicitly admitted dependencies using safe regular-file/descriptor traversal; preserve exact record bytes/digests and diagnostic provenance. Treat path hints as locators. Do not import or execute recorded code, invoke a current Stewart CLI on old state, enumerate arbitrary `.git`/home directories, follow symlinks, read special files, change refs/locks/receipts, install a writer, stop an auditor or remove/prune anything.

A read-only adapter must be separately inspected for host effects: custody-record immutability is weaker than whole-host read-only behavior. In particular, invoking a Python API/CLI may materialize a manager deployment even if the requested operation reads custody (C:580). A dedicated bounded parser or copied evidence reader is preferable for the first inventory, with its admitted schema list explicit; unsupported records retain diagnostics. Discovery's path-presence hints cannot establish completed custody.

Suggested saved outputs:

- `POPULATION.json`: approved roots, explicit workspace/audit/lifetime/record selections, known exclusions, observation window and completeness boundary.
- `INVENTORY.json`: one row per identified lifetime or independent undertaking, with exact record paths/digests/schema/writer identity, observed record state, dependencies, reader consumer and proposed disposition class.
- `DIAGNOSTICS.md`: invalid/missing/unreadable/unsupported records and unapproved external locators, preserving exact reasons and inability to establish completion.
- `GATES.md`: F6 and F7 checklists with unresolved rows, intended responsible actor and required next authorized action. No inventory row self-authorizes that action.
- `PROGRESS.md` and `RETURN.md`, plus command/reader identity and bounded evidence manifest. Long output goes to retained files as produced.

Each inventory row should distinguish **observed bytes**, **parsed supported fields**, **attributed claim**, **inference**, and **needed action**. It needs a stable row identity independent of report digest; equal report bytes from distinct collections/lifetimes remain distinct. Include whether a completed record is present, valid, invalid or unreadable; do not normalize all failures into partial.

## Record families and bounded questions

These are source-derived layouts, not evidence that any path or population exists. Resolve actual locations from approved identities and records, not hard-coded workspace coordinates. Root shorthand `<common>/stewart/` follows `workspace.py:9–13`, `_repository` constants, `audits.py:48–51`, `request_keys.py:48,97–100`, `holdings.py:6,38` and the frozen manual's record table at `:1844–1885`.

| Family and source-derived locator | Read-only findings sought | What reading cannot settle / next authority |
| --- | --- | --- |
| Draft/init/registration: `audits/<slug>/<id>/init/<name>/{STARTED,OUTCOME}.json`, `registrations/<name>.json`; workspace prompt/guidance only if admitted | Intended versus completed writes, owning context, source digest and any allocated outputs. Distinguish draft context from later lifetime and registration observation from creation. | Completion/abandonment of an effectful draft may require its writer; absence of a live session does not prove no partial effects. |
| Live/failed/incomplete session: `sessions/<slug>/<id>/session.json`, `PREPARE-ERROR.json`, `LAUNCH.md`, runtime preparation records and recorded refs/checkout locators | Exact session UUID, writer/schema, prompt/target/retention pins, preparation failure and phase omissions, recorded execution/grant/coordination metadata, every readable custody diagnostic. | No record proves actual present process cessation. Obtaining stop/control evidence and operational close remain separate, writer-bound work. Never let a later collection erase failed preparation evidence. |
| Collection and disposition: `collections/<name>/{STARTED.json,collection.json,REPORT.md,...}`, `triage/<name>.json` | Every started/recorded attempt; raw capture/report identity, source receipt/digest, declaration validation and gaps, exact disposition binding, later verification-level gaps. Optional member reads limited to named claims. | Discovery count or final text is not custody/completion. Triage/submission/preservation action requires appropriate writer and explicit manager authority; no prose-inferred completion. |
| Runtime recovery: `runtime-recoveries/<name>/{STARTED.json,RECOVERY.json,runtime-recovery/...}`; materialized directory only if expressly admitted | Source session/assets identity; materialized/capture outcome; current recorded obligations; how its capture can survive directory loss; whether a later named read is needed. | If actual directory comparison/preservation/close needed, commission it separately. Existing drifted/failed recovery cannot be discarded because successor omits facility; no old-command retargeting. |
| Legacy release/attempt: `releases/<name>.json`, `attempts/<name>/{RESERVED.json,ATTEMPT.json,...}` | Reserved versus completed/invalid/unreadable; writer, release/capture/review membership identities and raw payload locators; existing output/HOME/descendant uncertainty. Bound richer interpretation to named consumer. | Reserved attempt is never reusable; reading never grants invocation, release/re-run or completion. Finishing/disposition of old custody is writer-bound; no successor executor. |
| Closing: `closed/<slug>/<id>/<uuid>/{CLOSING.json,CLOSED.json,CLOSE-ATTEMPT-*.json}` | Frozen scope/authority and digest, selected lifetime, unfinished steps/failure reasons, explicit release basis, recorded removals versus leftovers, custody dependencies. Keep later audit lifetime separate. | `CLOSING` authorizes only its frozen inventory, not all locators. Actual resume/revalidation/removal requires old writer; present invalid ending cannot hide unfinished work. Closing record is not proof every independent resource/request finished. |
| Keyed requests: `requests/<sha256>/{REQUEST.json,attempts/*.json,OUTCOME.json}` | Key and intent/writer binding, original invoking checkout/context, each planned effect, completed/refused outcome or partial with no outcome; correlate only own planned output identities. Records outlive close. | `request_keys.py:51` marks only `close`/`resource-close` resumable in baseline. Do not label every other partial request resumable or rerun it. Lost reply uncertain effect must be reconciled before any operation. |
| Independent resources: `resources/<id>/{CREATE.json,CREATED.json,ENROLLED.json,associations/*.json}` | Stewart-created versus enrolled; intended/observed identity and disposition; all in-scope and out-of-scope live-use dependencies, including containers/branches/worktrees; export/retention failure records. | Creation is necessary, not sufficient removal authority; enrollment never grants disposal. Out-of-scope/unlocatable dependent use blocks a safe conclusion and triggers scope request, not crawling or removal. |
| Resource claims and endings: `resources/<id>/claims/<n>.json`, `*.RETIRED.json`, `*.RELEASED.json`, attempt/failure records and `ACKNOWLEDGED.json` | Exclusive claim author/writer, frozen judged inventory/tip/identity, active/released/retired state with diagnostics, interrupted attempt and dependencies. | Only qualifying claim can authorize scoped removal; start/acknowledgment/association/path/Git registration cannot. Old writer must revalidate; changed identity releases claim rather than deleting substituted material. Manual retirement is outside Stewart custody and not inferred from absence. |
| Retention/export/publications: session `retention/<name>.json`, resource handover records, explicit package `manifest.json`/`source.json`/selected members | Completed versus incomplete preservation selection, actor where recorded, source identity, independent product bytes/qualifications and which later-reader consumer needs them. Record missing question context and absent optional groups. | Do not invent baseline retain actor, current hold/close state or full collection soundness. A completed plain retained file is not a self-contained package; no successor cross-writer export authority follows. Publication location outside allowlist is a locator only. |
| Recorded manager deployment/launcher/interpreter and retained source refs | For a separately admitted read: identity availability and safely verified components necessary for explicit handoff; source retention recoverability within selected claims | Inspecting old code never executes it. Missing old code qualifies operations, not independently valid captured evidence. Installing/running it or changing refs needs a separate bounded operational commission. |

## Classification and finite exit

For each row choose one or more factual classifications, without collapsing them into a verdict:

- historical completed evidence; no continuing operation established;
- live/unfinished audit requiring old-writer stop/close disposition;
- independent unfinished custody/resource/request requiring old-writer completion or explicit authorized disposition;
- supported read-only evidence needed by a named later consumer;
- unsupported/invalid/unreadable/unknown population boundary requiring a decision or more authorized evidence.

The inventory is complete when every item in the **approved finite manifest** has a row or exact diagnostic, all outbound references have been classified in-scope or unapproved/unresolved, and each F6/F7 prerequisite has an owner and next step. It need not prove that no legacy state exists anywhere else on the machine. Gate claims must state the approved population and observation cutoff. If admissions continue or a writer is unreachable, the inventory may still return; the gate remains open.

## Candidate next operational commission after inventory

Prepare exact old-writer actions with a frozen population/cutoff and their own safety/evidence criteria: stopping or confirming stopped audits; preserving selected evidence; closing live lifetimes; resolving partial close/resource claims and preservation requests; explicitly dispositioning unsupported or impossible undertakings. Revalidate recorded identities at execution; no blanket batch close, manual receipt edit or uncertain rerun. The coordinator retains logistics, while purpose/scope or protected-obligation changes return for decision.

The user's later steering additionally forbids Claude session launches without asking first. No CLI/SDK/session is invoked by this inventory. A deliberate usage-limit study is deferred medium-term W08/W11/W20 work and supplies no present launch authority.
