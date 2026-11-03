# Proposed first paid commission

This is an unpaid proposal for one run of the [sensor specimen](submission/question.md)
under the [run procedure](RUN-SHEET.md). It grants no spending authority.
The principal must authorize the completed launch packet before `run`.

## Proposed settings

| Setting | Selection |
| --- | --- |
| Model | `claude-haiku-5-5` |
| Effort | Omit `effort`; use the provider default |
| Cumulative allowances | 12 turns, 160,000 input tokens, 12,000 output tokens |
| Provider | Direct `https://api.anthropic.com`; no proxy or alternate provider |
| Account | A dedicated personal API key scoped to the selected workspace |
| Placements | One; no automatic continuation or new attempt |
| Request retries | Stewart's bounded policy: at most four attempts per request, within the cumulative allowances |
| Wall-clock stop | 900 seconds for the placement; request termination, then force termination if still alive after 10 seconds |

Use the original question and both materials unchanged. Set the proposed model
and allowances in a new retained submission copy, and record its actual answer
destination. The launch packet must also identify the account/workspace without
the secret, approved credential-entry mechanism, executable digest, source,
container image and Linux filesystem. Its source identity and checks must cover
the executable actually launched.

Approval must explicitly cover these settings and the built-in request retries.
Review any ending before deciding further action. No failure authorizes a changed
model, changed limits, continuation or another placement. Status and close remain
available during the run; close ends authoring. Inspect any newly delivered
manager-sealed copy before confirming close, following the run sheet.

The watchdog is an operator stopping condition. It can interrupt an in-flight
request whose provider consumption is not yet known; preserve the resulting
reported and estimated usage and reconcile actual billing during review.

## Compatibility checked against public documentation

Checked **2026-11-01**; recheck if the proposal or provider documentation changes.
These checks establish documented compatibility, not a real-provider result.

- The API documents `anthropic-version: 2026-10-21`.
  [Versions](https://platform.claude.com/docs/en/api/versioning)
- Haiku 5.5 supports tool use and adaptive thinking. Omitted effort uses medium;
  thinking is on by default and counts toward output limits. Its dateless model
  ID names a fixed snapshot, while serving infrastructure may change.
  [Model](https://platform.claude.com/docs/en/models/haiku-5-5/overview),
  [Effort](https://platform.claude.com/docs/en/build-with-claude/effort),
  [Model IDs](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)
- The documented on-demand compaction protocol uses `compact-2026-09-04`,
  `{"type":"summarize"}`, a signed block reused unchanged, and iteration usage.
  Haiku 5.5 is among its supported models. This small commission does not aim to
  reach Stewart's 150,000-token context trigger or establish compaction conformance.
  [On-demand compaction](https://platform.claude.com/docs/en/build-with-claude/compaction-on-demand)
- Stewart's 16,000-token request cap is below the SDK's documented 21,333-token
  nonstreaming threshold; the proposed output allowance makes the initial
  effective cap 12,000. Neither cap guarantees completion within the 600-second
  timeout or prevents an idle connection from failing.
  [Thinking](https://platform.claude.com/docs/en/build-with-claude/thinking),
  [Long requests](https://platform.claude.com/docs/en/api/errors)
- `x-api-key` remains supported. A workspace-scoped key can omit the workspace
  header; an unscoped key requires it, and Stewart does not send it.
  [Authentication](https://platform.claude.com/docs/en/manage-claude/authentication)

## Cost and remaining observations

At the documented short-prompt rates of $0.10 per million input tokens and $0.50
per million output tokens, consuming the proposed allowances costs **$0.022**
before taxes. Each request whose prompt exceeds 100,000 tokens uses higher rates;
applying those rates to the same allowances gives **$0.11**. Prompt length is
measured per request, separately from cumulative input consumption.
[Pricing](https://platform.claude.com/docs/en/about-claude/pricing)

Both figures are estimates, **not spending ceilings**. Input usage is known only
after a response and can exceed the allowance. Retries, lost responses and
timeouts can leave billed consumption that Stewart estimates rather than observes.
The provider can charge for a request that would have succeeded despite a client
disconnect or timeout. Stewart enforces no dollar ceiling; approval must account
for these limits. Preserve reported usage, estimates and available billing records
separately.
[Billing](https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage)

Account access, provider TLS, model tool use and submission were observed once
under these settings in the retained run `sanity-live-02`, recorded in
[the qualification record](../qualified.md); billing reconciliation remains the
user's observation. Purchasing credits does not authorize a run. The amount
available to buy is determined in the Console; this proposal specifies no
minimum credit purchase.
