# Endpoint alignment

The mechanism's sources are the Messages small-commission apparatus (`apparatus/c10`, with
parts of `apparatus/sanity`) and the harness profile and check tooling
(`apparatus/claude-code`, with the independent `apparatus/driver/claude_code_*`
fixtures).

Stewart talks to two Anthropic endpoints: the Messages API, from the distributed
binary, and the Claude Code harness, from the source-build development runtime.
Each adapter, and each stand-in that replaces it in the scripted suites (the fake
provider, the synthetic harness), encodes assumptions about its endpoint.
Alignment observes the real endpoint in a small bounded run, compares what it
saw with those assumptions, turns the observations into stand-in fixtures and
records the result. A release names only endpoint versions with a current
alignment record. The [alignment tier](ACCEPTANCE.md#the-endpoint-alignment-tier)
owns the gate, [INTERFACE 6](docs/INTERFACE.md#6-the-run-adapter) the Messages
adapter, and the [runtime contract](docs/claude-code/CONTRACT.md) the harness
launch, its documented facts and what remains undemonstrated with the real
harness.

Design and rehearse the comparisons offline. Before a live start, verify that
the bounded commission covers the packet, credential route and budget, and that
a rehearsal of the committed apparatus with that writer is current: a change to
the apparatus, a driver helper it imports or the writer needs a new rehearsal
([DEVELOPMENT](development/DEVELOPMENT.md#what-to-run-for-what-you-changed)).
Keep open audits and their exact writers until closure or explicit disposition.

## 1. Specify the alignment check

The initial pair uses the existing protected launcher. The remaining mechanism work below can proceed after those two catalog trials. Complete the per-model record before counting any release gate as passed.

- [x] Fix the initial comparison, release coverage and proposed reservation table.
- [x] Inventory the historical captures and resolve the ordinary and summary usage comparisons. The [comparison procedure](alignment/messages/README.md) identifies the captured and synthetic shapes.
- [ ] Define harness alignment (1.6): which of the
  [unresolved operations](development/UNRESOLVED-OPERATIONS.md) an alignment
  run settles, and which stay with commissioned trials.

### 1.1 Endpoint assumptions to compare

The adapter's rules are [INTERFACE 6.1–6.6](docs/INTERFACE.md#6-the-run-adapter).
The stand-ins are the release driver's fake provider
(`apparatus/driver/fake_provider.py`, with the captured bodies in
`apparatus/driver/testdata/messages/`) and the rehearsal fake shared by C10 and
sanity (`apparatus/sanity/exercise.py`, `apparatus/c10/fake.py`). Every run is
compared on every row it reaches. Rows A1–A13 name the shape, the adapter's
assumption, what the stand-ins replay, the witnessing capture, and what retained
live captures already show.

| # | Shape | Adapter assumes | Stand-ins replay | Witness | Seen live |
| --- | --- | --- | --- | --- | --- |
| A1 | Request acceptance: `anthropic-version: 2026-10-21`, `anthropic-beta: compact-2026-09-04`; `model`, `max_tokens`, `system`, `tools`, `messages`; `output_config.effort` at each level; `compaction` on summary requests | HTTP 200 | Both fakes check the headers and accept | `request-<n>.json`; attempt status and `request-id` | Haiku omitted (`c10-live-*`), Haiku `high` (`sanity-live-05`), Opus omitted (`opus-live-*`, `readiness-m4-live-01`) |
| A2 | Message envelope | `content`, `stop_reason`, `usage` once each; `model` recorded; the rest raw | Driver: configurable members. C10 fake: minimal, no `container`, `diagnostics` or `stop_details` | `response-<r>-<a>.bin` | `id`, `type`, `role`, `stop_sequence`, `stop_details: null`, `container: null`, `diagnostics: null` (m2/m3/m4 fixtures) |
| A3 | Content blocks | `tool_use` (`id`, `name`, `input`), `text`, signed `thinking`, unknown types echoed byte for byte | Driver: all, plus redacted and unknown blocks. C10 fake: tool use, text, one signed thinking cap | Response captures | Signed thinking with empty text; text; tool use |
| A4 | Stop reasons | `tool_use`, `end_turn`, `max_tokens` with and without tool use, `compaction`, `refusal`, `model_context_window_exceeded`; others are `protocol_anomaly` | Driver: any. C10 fake: the scripted ones | Response captures; `run_ended` | `tool_use`, `end_turn`, thinking-only `max_tokens` (Haiku, M2/M3 fixtures), `compaction` (Opus m4). Not seen: `refusal`, window exhaustion, `pause_turn` |
| A5 | Ordinary usage | Integer top-level input and output; cache counts zero, null or absent; when `iterations` is present, its sums replace the top-level totals | Driver `Usage`, iterations optional. C10 fake: no `iterations` and no unknown usage members | Response captures; attempt `usage` | One `message` iteration equal to the top-level counts; unknown `cache_creation{ephemeral_5m,ephemeral_1h}`, `output_tokens_details.thinking_tokens`, `service_tier`, `inference_geo`, `speed` |
| A6 | Summary usage | At least one `compaction` iteration; the charge comes from the iteration sums | Driver replays the m4 body unchanged. C10 fake: nonzero top-level counts with `message` and `compaction` iterations | Summary response capture | Top-level 0/0 and one `compaction` iteration (Opus m4). Mixed iterations are covered separately by the C10 summation control. |
| A7 | Compaction protocol | Triggered by ≥150,000 counted tokens. The summary request carries the same model, system, tools and effort plus `{"type":"summarize"}`. The reply is `stop_reason: "compaction"` with exactly one `compaction` block carrying `content` and `signature`. The signed block is reused byte for byte, followed by the post-compaction notice. Recorded work is kept | Driver: captured m4 case. C10 fake: synthetic summaries with an unknown `opaque` member | Summary request and response captures, reset request, log | Opus, effort omitted, one compaction (m4). Not seen: Haiku, effort set, a second compaction |
| A8 | Charges and cost | Charges as INTERFACE 6.4 states, priced at the dated rate card; Haiku's rate band chosen per request; no cache tokens, because no `cache_control` is sent | Fakes report synthetic usage | Attempt records; principal's billing observation | Zero cache counts (m4); `c10-live-*` calculated cost; Console USD 0.01 for `sanity-live-02` |
| A9 | Errors | `{"type":"error","error":{"type","message"},"request_id"}`. 408/429/5xx/529 retried with `retry-after`; others are `provider_rejected` | Driver: every status and form. Sanity/C10 fake: 401 only | Response captures; `run_ended.provider` | 401 `authentication_error` (`sanity-live-03`, captured). Others are not inducible inside the commission: compared when observed, otherwise a stated limitation |
| A10 | Transport | Framing by `content-length`, chunking or close; only `content-type`, `request-id` and `retry-after` retained; 600-second timeout | Driver: every framing (`testdata/wire`) | Attempt timing and three headers; framing itself is not retained | Durations only. Live framing is unwitnessed on the direct route |
| A11 | Model identity | Response `model` equals the requested ID; no `fallbacks` parameter is sent | Fakes echo `rehearsal-only` | Response captures | Haiku and Opus IDs echoed |
| A12 | Effort effect | Acceptance only: a provider that ignores a parameter goes unreported (INTERFACE 6.5) | Not modelled | Usage `thinking_tokens` and output per level, reported but not gated | `high` accepted on Haiku |
| A13 | Credential reflection | None; scanned as INTERFACE 6.1 states | Rehearsal reflection control | Stewart scan; launcher host scan | None seen |

The [comparison procedure](alignment/messages/README.md) cites the provider documentation and dated model card used for the proposed packets. Reconfirm their currency on the commission date.

### 1.2 Witness origin and scope

- **Stewart's captures.** On the direct TLS route, request bytes, raw response
  bodies, attempt records, three headers and timing are the writer's own
  records. They show what the binary recorded sending and receiving. They do not
  show what reached the provider.
- **The apparatus input witness and the reviewer's reconstruction.** These are
  independent of the service for the inputs and for request bytes recomputed
  from the arrangement and captures. That is internal consistency, not the wire.
- **The provider-issued `request-id`** of each attempt. It is carried inside
  Stewart's capture.
- **Billing.** The principal's Console usage and cost for the workspace and day
  are independent of Stewart but aggregate; reconcile them per model and day
  with the calculated cost.
- **The rehearsal fake provider.** It is the only independent byte witness. It
  establishes the adapter's handling of the stand-in shapes, not endpoint
  behavior.
- **Unmet: an independent per-request witness of the live wire** (bytes,
  framing, attempt count). An apparatus-owned CONNECT proxy
  ([INTERFACE 6.1](docs/INTERFACE.md#61-provider)) could record connections,
  timing and byte volumes without seeing plaintext, but it changes the
  commissioned route. By default it is not used, and the record states the
  unmet requirement.

### 1.3 Messages run set and reservations

Use the qualified release writer for every gate observation. Both model IDs,
all three families, the six evidence variants and each selectable effort
(including explicitly requested medium) are represented below. Omitted effort
is a distinct request shape. H1 and O1 form the first proposed commission,
one placement each, in that order. Review and settle H1 before admitting O1.
The remaining catalog cells are a later commission.

| Haiku | Opus | Catalog specimen | Requested effort | Placement reservation, Haiku / Opus |
| --- | --- | --- | --- | --- |
| H1 | O1 | open-ordinary | omitted | $1.24 / $9.88 |
| H2 | O2 | open-inadequate | low | $1.24 / $9.88 |
| H3 | O3 | framing-ordinary | medium | $1.24 / $9.88 |
| H4 | O4 | framing-inadequate | high | $1.24 / $9.88 |
| H5 | O5 | comparison-ordinary | xhigh | $1.24 / $9.88 |
| H6 | O6 | comparison-inadequate | max | $1.24 / $9.88 |
| H7 | O7 | compaction, ordinary open inquiry | omitted | Pending a separately rehearsed bound |

Catalog placements have 16 turns, 115,000 input tokens and 32,000 output
tokens, a 900-second watchdog and a 131,072-byte per-file limit. Their
147,000-token combined allowance fits the launcher's ordinary-packet guard.
Use distinct audit identifiers for both models. Each packet permits one
placement and the writer's standard transport retries. A second placement
or a replacement audit needs its own commission.

The first pair needs at most **$11.12** in queue reservations. Expected usage
can be much smaller. The queue reserves at the highest applicable input
price, including cache writes, for the allowance and terminal overrun. It
also reserves remaining output plus one request's maximum output, and rounds
up per placement. Use the queue's calculation on the exact packets and dated
model cards. Settle each placement from its reviewed capture. The $11.12 is a
proposed fresh campaign cap. A historical workspace limit grants no spending
authority.

H7 and O7 remain required for release. The current launcher refuses paid
packets that can enter server compaction. Establish and rehearse a separate
bound for summary iterations, retries, large capture files and interrupted
estimates before pricing or commissioning these two rows. Historical
compaction is input for this rehearsal.

Inventory the selected work exports from readiness-m4-live-01, the six
c10-live pilots, sanity-live-02, -03 and -05, readiness-m2-live and
readiness-m3-live, and opus-live-01 through -04. Compare actual response
bytes, their attempt records and the prepared arrangement. Resolve ordinary
and summary usage differences with fixtures or explicit shape limitations
before the first paid comparison.

### 1.4 Alignment record

One record per model per series. It holds:
- the endpoint base URL and route (direct or proxy);
- the API version, compaction beta, compaction trigger and request, and output
  cap;
- the requested model ID and the response `model` values;
- the effort values covered;
- the writer (qualification ID and release SHA-256), apparatus commit, image and
  catalog digest;
- the commission and authorization digests;
- the dates of the runs and of the documentation check.

Per run, it holds:
- specimen, family, evidence variant, effort and limits;
- ending, cause, submitted or not, and placements;
- reported and estimated turns, input and output;
- compaction counts;
- the export path and digest.

It also holds:
- an inventory row for each A1–A13 shape: observed or not, with capture paths
  and digests;
- a comparison result for each row: match, or difference with its resolution,
  given as an adapter-fix commit, a fixture path with provenance, or a stated
  limitation;
- the captured fixtures added;
- the calculated cost at the dated prices, and the billing observation if any;
- the unmet witness requirements;
- the pinned inputs whose change ends currency: model ID, API version, beta,
  effort allowlist, compaction trigger and request, and output cap.

A new `alignment` kind in `apparatus/qualified.py` keeps the record and
re-verifies its evidence digests as `check` does for experiments. Historical
`c10-*` and `readiness-*` records stay as they are.

### 1.5 Existing apparatus and remaining mechanism work

**Reused, in the form the apparatus has when section 2 starts:**
- C10 packet preparation, binding and approval, including the catalog's
  inadequate variants and the `effort` front matter.
- The saved-connection live launch and the host queue's dollar budget.
- Custody-guarded export.
- The procedural reviewer: request reconstruction, iteration sums, compaction
  checks, citations and delivery.
- The experiment report with calculated cost.
- The continuation path.
- The rehearsal fake's compaction and cap controls.
- From sanity: the session engine, credential route, exporter and process
  observers.

The [Messages comparison procedure](alignment/messages/README.md) covers the historical inventory, current packet preparation and the two usage-shape dispositions. The protected launcher admits the first pair using its existing saved-connection rehearsal. [Offline readiness](apparatus/qualified.md#alignment-preparation-01)

Remaining mechanism work includes:
- Assemble reviewed attempt, fixture, and custody observations into each model's final comparison record.
- The existing ordinary-placement reservation check and a separately demonstrated
  compaction bound before either compaction row is admitted.
- A trace-count option for `compaction_specimen.py`.
- The `alignment` record kind.
- Fixture feedback with provenance into `apparatus/driver/testdata/messages/`,
  with expected values and controls by a specification-only author.

### 1.6 Harness alignment

Keep it brief. Recheck the pinned version's documented facts in the runtime
contract against current documentation. Run a reviewed supplied-surface check
that produces the profile's `check` attestation, and one short audit to the
auditor's own submission. Add targeted observations for the contract's
not-yet-demonstrated list where a bounded run reaches them;
[unresolved operations](development/UNRESOLVED-OPERATIONS.md) designs those
observations.

Harness observations use the included subscription. The witnessed Linux surface
check and submitted audit for Claude Code 2.1.322 and Sonnet 5.5 are inputs
to the harness record. Recheck currency against its documented bindings.

### Commission decisions

Keep the direct TLS route and record the limits of the producer-owned captures.
A Console observation can supplement the queue's settlement if the maintainer
supplies it. Otherwise provider billing remains unverified. Record any unmet
witness explicitly. A failed gate or uncertain effect stops further starts
pending review. Packet replacement and additional placements require fresh
authority. Prior encounters inform fixtures and estimates. The release gate
uses the qualified shipping writer.

## 2. Build the mechanism in `alignment/`

- [ ] Create `alignment/messages/` from what the specified check uses of
  `apparatus/c10` and `apparatus/sanity`: packet preparation, the custody-guarded
  launcher and export, the procedural reviewer with its controls, and the host
  queue's saved-connection route. Bring their tests, update DEVELOPMENT's rows,
  rehearse on Linux, then delete the rest of `apparatus/c10`,
  `apparatus/sanity` and `apparatus/testdata/acceptance/`.
- [ ] Create `alignment/claude-code/` from `apparatus/claude-code`: pin, profile,
  bounded launch, and the surface and service checks. The independent observer,
  peer, surface fixture and service witness stay in `apparatus/driver/` under
  the independence rule; changes to them need a specification-only author.
- [ ] Feed captures back as stand-in fixtures with provenance, as
  `apparatus/driver/testdata/messages/` already does, with independently
  expected values and firing controls added by a specification-only author.

Inputs worth reusing: the full-size synthetic compaction rehearsal
(`.scratch/readiness-m4-rehearsal-02/REVIEW.json`), the bounded live compaction
encounter (`.scratch/readiness-m4-live-01/REVIEW.json`), the continuation
records in `.scratch/m3-rehearsal-01`, and the interaction findings
(`apparatus/studies/interaction/RESULTS.md` at `77375f1`). Recheck the recorded source,
writer, image, input and saved-connection identities against the retained receipts before reusing an observation.

**Done when:** the mechanism lives in `alignment/` with its checks in DEVELOPMENT,
its offline controls fire, and the retired apparatus is gone.

## 3. Align and record

- [ ] For each model the first release will name, prepare the packet with a dated
  cost estimate. Execute the commissioned runs, review the observations and
  record the result. Resolve each difference with an adapter fix, a stand-in
  fixture or a stated release limitation before counting the record as current.
- [ ] Align the harness pin the development build uses, through the Linux route,
  producing its profile check.

Complete this plan when the mechanism is built, each model the first release
names and the harness pin have current alignment records, and the enduring
procedure is documented in `alignment/`. Then delete the plan.

Paid Messages trials use the protected launcher account and its metered queue in
the development VM. The development account prepares and reviews proposals.
