# Claude Code as a peer auditor runtime

Working plan, 2026-10-31. The sequence is **live Messages API first, then
Claude Code integration and conformance**. The current API implementation stays
in place. This plan authorizes neither implementation nor model-consuming runs;
each live commission needs its scope, models/settings and budget named.

## Direction and starting point

The auditor protocol should eventually serve model runtimes and human auditors:
commissioned material access, recorded work, revisions, explicit submission and
closure. Conversation management, token accounting and process termination have
runtime-specific meanings. Human and Codex/OpenAI adapters remain future work.

The distributed AI interface uses explicit API or supported cloud-provider
authentication. Subscription login/routing stays outside Stewart's main
interface. This product decision is recorded in [CONTRACTS](CONTRACTS.md#run-and-continuation).

The Messages API loop gained provider compaction in `8cbd307`. Native checks
passed; container and live-provider qualification remain outstanding. The
[release plan](RELEASE-PLAN.md#provider-compaction-built-unqualified) owns those
results and pending checks. No Claude Code adapter or live conformance run exists.

## Stages

1. **Run and review the first bounded live API test.** Prepare the current
   adapter's test using the [non-question-type discussion agenda](RELEASE-PLAN.md#before-the-first-live-api-test).
   Keep a first compatibility/procedure probe distinct from the full release
   conformance gate. Record observed behavior, failures and remaining uncertainty.
   Review that result before implementing the Claude Code route.
2. **Resolve the Claude Code adapter contract and build a narrow integration.**
   Establish its accounting, access and stopping guarantees on a pinned runtime.
   Bring any change to Stewart's promises or packaging back to the principal.
   A small SDK helper beside the Rust operation core is a candidate, as is a CLI
   bridge; the SDK is not a settled dependency. Initially retain one placement
   per harness session and Stewart's fresh-conversation continuation from its
   ledger. Harness-native resume is a separate choice.
3. **Qualify Claude Code conformance.** Under a separate bounded commission,
   exercise the actual auditor tool surface, compaction/re-entry, accounting,
   interruption, submission, delivery and close. Check both the common audit
   semantics and the adapter's stated guarantees, with an independent witness,
   firing controls, differing cases and invariance cases. Pin SDK/CLI versions,
   effective configuration, model, authentication route and binaries. Model
   answer quality is not the gate. Do not transfer the API adapter's results
   into a claim about this runtime.

Finishing every release work item is not an added prerequisite to stage 1.
The existing release obligations remain in [ACCEPTANCE](ACCEPTANCE.md#the-real-model-conformance-tier).

## Four takeaways to carry into the design

1. **Authority over recorded work stays in Stewart.** A tool hook can refuse
   entry, but it cannot alone resolve a handler already in flight at close.
   Stewart must reject a late mutation at its durable publication boundary.
   Runtime interruption/termination is another responsibility. The same
   authority boundary can serve a human auditor's late browser request.
2. **Accounting needs an explicit failure policy.** Harness totals include
   internal work and can carry restored history; missing final results can hide
   consumption. Establish what can be reported or defensibly estimated after a
   crash. A zeroed result is not zero consumption, and a client-estimated dollar
   cap is not a substitute for the current token/turn contract.
3. **Qualify the effective configuration.** Verify actual tools, instructions,
   authentication and access before and after compaction, including host and
   server-managed configuration. A collection of isolation flags is a candidate
   configuration, not evidence that the commissioned world was enforced.
4. **The SDK is an engineering candidate.** Its convenient controls assume a
   TypeScript/Python host. Keep audit semantics in the Rust core; assess any
   helper and its installation/versioning explicitly against the current static
   binary product. Generic advice about multi-tenant hosting is not new scope.

## Next decisions and references

- Settle stage 1 through the release plan's focused agenda. Question-type work
  is outside that discussion.
- After the API result, determine whether supported harness observations can
  bound unreported consumption during compaction or another internal call.
  If they cannot support the current promise, present the gap and alternatives
  for a decision rather than silently changing allowance semantics.
- Specify how the selected runtime and its guarantees are pinned in preparation;
  do not add a runtime selector before deciding its effect on the commission.
- Use [the runtime reference](docs/claude-code/RUNTIME-REFERENCE.md) for the
  consultation's option names, documentation links, accounting correction,
  version-sensitive details and unanswered composition questions. It is source
  research, not a validated launcher recipe.

Update this plan as decisions change. At completion or abandonment, give each
open item a disposition, move enduring contracts/mechanisms into maintained
documentation and tests, and delete the plan. Remove its supporting reference
when it no longer helps the next action.
