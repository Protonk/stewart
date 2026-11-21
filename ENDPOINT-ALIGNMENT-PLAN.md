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

The design below maps the endpoint assumptions to witnesses, proposes the
Messages run set with its cost, and defines the alignment record.

- [ ] Settle decisions D1–D5 with the maintainer, then fix the run table.
- [ ] Run the shape inventory over the retained captures listed in 1.3 and
  resolve the differences it finds before any spend.
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
| A6 | Summary usage | At least one `compaction` iteration; the charge comes from the iteration sums | Driver replays the m4 body unchanged. C10 fake: nonzero top-level counts with `message` and `compaction` iterations | Summary response capture | Top-level 0/0 and one `compaction` iteration (Opus m4). **The C10 fake differs here** |
| A7 | Compaction protocol | Triggered by ≥150,000 counted tokens. The summary request carries the same model, system, tools and effort plus `{"type":"summarize"}`. The reply is `stop_reason: "compaction"` with exactly one `compaction` block carrying `content` and `signature`. The signed block is reused byte for byte, followed by the post-compaction notice. Recorded work is kept | Driver: captured m4 case. C10 fake: synthetic summaries with an unknown `opaque` member | Summary request and response captures, reset request, log | Opus, effort omitted, one compaction (m4). Not seen: Haiku, effort set, a second compaction |
| A8 | Charges and cost | Charges as INTERFACE 6.4 states, priced at the dated rate card; Haiku's rate band chosen per request; no cache tokens, because no `cache_control` is sent | Fakes report synthetic usage | Attempt records; principal's billing observation (D3) | Zero cache counts (m4); `c10-live-*` calculated cost; Console USD 0.01 for `sanity-live-02` |
| A9 | Errors | `{"type":"error","error":{"type","message"},"request_id"}`. 408/429/5xx/529 retried with `retry-after`; others are `provider_rejected` | Driver: every status and form. Sanity/C10 fake: 401 only | Response captures; `run_ended.provider` | 401 `authentication_error` (`sanity-live-03`, captured). Others are not inducible inside the commission: compared only if they occur, otherwise a stated limitation |
| A10 | Transport | Framing by `content-length`, chunking or close; only `content-type`, `request-id` and `retry-after` retained; 600-second timeout | Driver: every framing (`testdata/wire`) | Attempt timing and three headers; framing itself is not retained | Durations only. Live framing is unwitnessed unless D4 |
| A11 | Model identity | Response `model` equals the requested ID; no `fallbacks` parameter is sent | Fakes echo `rehearsal-only` | Response captures | Haiku and Opus IDs echoed |
| A12 | Effort effect | Acceptance only: a provider that ignores a parameter goes unreported (INTERFACE 6.5) | Not modelled | Usage `thinking_tokens` and output per level, reported but not gated | `high` accepted on Haiku |
| A13 | Credential reflection | None; scanned as INTERFACE 6.1 states | Rehearsal reflection control | Stewart scan; launcher host scan | None seen |

The documentation each assumption rests on (models overview, effort, versioning,
on-demand compaction, authentication, errors and pricing) was last recorded in
`.scratch/c10-haiku-commission-01/compatibility-and-cost.json` (checked
2026-11-03). Recheck it and record it again on the commission date.

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
  with the calculated cost (D3).
- **The rehearsal fake provider.** It is the only independent byte witness. It
  establishes the adapter's handling of the stand-in shapes, not endpoint
  behavior.
- **Unmet: an independent per-request witness of the live wire** (bytes,
  framing, attempt count). An apparatus-owned CONNECT proxy
  ([INTERFACE 6.1](docs/INTERFACE.md#61-provider)) could record connections,
  timing and byte volumes without seeing plaintext, but it changes the
  commissioned route (D4). By default it is not used, and the record states the
  unmet requirement.

### 1.3 Messages run set and cost

The first release names `claude-haiku-5-5` and `claude-opus-5-5`; omitted effort
selects `medium` on both. For each model, the runs cover every family, with
ordinary and inadequate evidence among them, every effort value and one
compaction. There is one run per cell: repetition, effort comparison and
killed-and-continued placements stay in the experiment tier
([ACCEPTANCE](ACCEPTANCE.md#the-endpoint-alignment-tier)).

Each run is one audit and one placement. A run that stops without submission
may get one separately approved continuation; because the limits are
cumulative, the continuation does not change the run's ceiling.

**Specimens.**
- The catalog cases are `apparatus/c10/catalog.json`, with materials of at most
  1.4 KB.
- The compaction specimen is `compaction_specimen.py` with four traces instead
  of eight. In m4, eight 64 KiB traces produced one 341,007-token request,
  about 42,000 tokens per trace. Four put one full read near 176,000 tokens:
  over the 150,000 trigger, without m4's second 170,000.

| Run | Model | Specimen | Effort | Limits: turns / input / output | Expected USD | Ceiling USD |
| --- | --- | --- | --- | --- | ---: | ---: |
| H1 | Haiku 5.5 | open-ordinary | omitted | 16 / 200,000 / 32,000 | 0.01 | 0.05 |
| H2 | Haiku 5.5 | open-inadequate | `low` | same | 0.01 | 0.05 |
| H3 | Haiku 5.5 | framing-ordinary | `medium` | same | 0.01 | 0.05 |
| H4 | Haiku 5.5 | framing-inadequate | `high` | same | 0.01 | 0.05 |
| H5 | Haiku 5.5 | comparison-ordinary | `xhigh` | same | 0.01 | 0.05 |
| H6 | Haiku 5.5 | comparison-inadequate | `max` | same | 0.01 | 0.05 |
| H7 | Haiku 5.5 | four-trace compaction | omitted | 24 / 700,000 / 32,000 | 0.19 | 0.60 |
| O1 | Opus 5.5 | open-ordinary | omitted | 12 / 90,000 / 16,000 | 0.32 | 0.94 |
| O2 | Opus 5.5 | framing-inadequate | `low` | same | 0.30 | 0.94 |
| O3 | Opus 5.5 | comparison-ordinary | `xhigh` | same | 0.40 | 0.94 |
| O4 | Opus 5.5 | comparison-inadequate | `max` | same | 0.48 | 0.94 |
| O5 | Opus 5.5 | four-trace compaction | `high` | 24 / 500,000 / 12,000 | 1.74 | 3.60 |
| **Total** | | | | | **≈3.5** | **8.25** |

Haiku: about 0.24 expected, 0.87 ceiling. Opus: about 3.24 expected, 7.38
ceiling. Opus covers `omitted`, `low`, `high`, `xhigh` and `max`; explicit
`medium`, which is its default, is covered only on Haiku (D2).

**Prices** (Anthropic first-party, USD per million tokens, as supplied
2026-11-20):
- Opus 5.5: 4 input, 20 output.
- Haiku 5.5: 0.10 input and 0.50 output for prompts up to 100,000 tokens, and
  0.50 input and 2.50 output beyond.

Formula check: `readiness-m4-live-01`'s 737,969 input and 4,266 output tokens
give USD 3.0372, its recorded calculated cost.

**Ceiling arithmetic.** The ceiling is `p_in × (L_in + R_max) + p_out × L_out`.
Reported output never exceeds `L_out`. Input can exceed `L_in` by the one
request the input check lets through before the response reports its size
(INTERFACE 6.4); `R_max` bounds that request.

- **Catalog runs.** `R_max = B + L_out + (T − 1) × τ`, where:
  - `B` is the first request: 5,000 tokens for Haiku (observed 3,941–4,749 in
    `c10-live-01/02/05`) and 6,000 for Opus (an assumed 1.35× tokenizer factor).
  - `τ = 4,000` is the tool-result growth per turn; observed growth was at most
    about 4,400 tokens per turn including output.
  - This gives Haiku 97,000, so every catalog request stays in the low band, and
    Opus 66,000.
- **Compaction runs.** `R_max = 150,000 + 16,000 + M + B = 341,000`: the request
  after the last response under the trigger, carrying one full read of the
  materials, `M ≈ 4 × 42,000 + 1,000`. For the ceiling, Haiku compaction runs
  are priced entirely at the higher band.

Worked examples:

| Run | Input | Output | Total |
| --- | --- | --- | ---: |
| H1 | 0.10 × 297,000 / 10⁶ = 0.030 | 0.50 × 32,000 / 10⁶ = 0.016 | 0.046 |
| H7 | 0.50 × 1,040,000 / 10⁶ = 0.520 | 2.50 × 32,000 / 10⁶ = 0.080 | 0.60 |
| O1 | 4 × 156,000 / 10⁶ = 0.624 | 20 × 16,000 / 10⁶ = 0.320 | 0.944 |
| O5 | 4 × 841,000 / 10⁶ = 3.364 | 20 × 12,000 / 10⁶ = 0.240 | 3.604 |

**Expected costs** come from:
- **Haiku catalog runs:** the six `c10-live-*` pilots, 28,365–71,095 input and
  1,516–4,314 output tokens, a mean of USD 0.006, with output doubled at
  `high` and above.
- **Opus catalog runs:** about 60,000 input tokens, with output of 3,000–12,000
  rising with effort.
- **Compaction runs:** m4's pre- and post-trigger requests (53,000 tokens over
  eight requests), plus a trigger request of about 177,000 and a summary of
  about 179,000.

**Assumptions and limits of these figures:**
- **Cache tokens.** No `cache_control` is ever sent, and m4 and every fixture
  show zero cache counts. Cache-write prices were not in the supplied rate card;
  if any appear, assume Anthropic's standard 1.25× (5-minute) or 2× (1-hour)
  input price. Any nonzero cache count is an A8 difference that pauses the
  series.
- **Lost attempts.** An attempt lost after its request was written is charged by
  estimate: body bytes ÷ 3 input and `max_tokens` output. For hex trace pages
  that understates tokens: m4's summary was 562,869 bytes, estimated at 187,623
  tokens, reported at 344,449. So each lost compaction-sized Opus attempt could
  bill up to about USD 0.64 beyond the ceiling.
- **Order.** Run H1–H7 first, then O1–O4, then O5. Launch each run only when
  the remaining authorization covers its ceiling, and stop at an unresolved
  difference.
- **Thinking-only caps.** `xhigh` and `max` can produce a thinking-only
  `max_tokens` cap, as Haiku did in M2 and M3. With 16,000 output, a cap on
  O3's or O4's first request exhausts the allowance. It is then an A4
  observation and the run fails the gate (D5).

**Mechanisms reached:**
- **Every run:** A1–A5, A8, A11, A12 and A13.
- **Inadequate-evidence runs:** often a prose `end_turn` followed by the single
  reminder, as in `readiness-m1-live-direct-inadequate-01`, but only if the
  model does so.
- **H7 and O5:** add A6 and A7.
- **A9 and A10:** only if they occur.

Report the reach actually observed, not this list.

**Retained captures to inventory first** (offline, no spend):
- `readiness-m4-live-01`: Opus compaction.
- `c10-live-01` through `c10-live-06`: the six Haiku cases, effort omitted.
- `sanity-live-02` and `sanity-live-05`: Haiku, effort omitted and `high`.
- `sanity-live-03`: the 401.
- `readiness-m2-live-*` and `readiness-m3-live-*`: Haiku caps and the reminder.
- `opus-live-01` through `opus-live-04`: Opus, including input-limit stops.

Two differences are already visible: the C10 fake's ordinary usage (A5) and its
summary usage (A6). Resolve both, by an updated stand-in or a documented second
shape, before the live set.

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

### 1.5 What is reused now and what section 2 adds

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

**Section 2 must add:**
- A shape inventory over response captures and attempt records.
- A comparator against the adapter rules and against both stand-ins, reading
  the driver's fixtures without editing them.
- A per-run ceiling check that uses the formula above, so the queue refuses a
  launch the remaining authorization cannot cover.
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

Harness runs use included subscription usage. The externally fixed USD 49 API
budget is shared with other Messages commissions; the Messages set above is
held to a ceiling of about USD 8.

### Decisions needed

- **D1, prior evidence.** Is the compaction comparison retained from
  `readiness-m4-live-01` acceptable as the Opus compaction observation, and the
  six `c10-live-*` pilots as Haiku family coverage? They share the model, API
  version and beta but used earlier writers. If yes, O5 is dropped, saving about
  USD 1.74 expected and 3.60 of ceiling, and room opens for an explicit `medium`
  Opus run. The strict reading, "through the release binary", says no.
- **D2, effort coverage.** Does "each manager-selectable request setting" mean
  every effort value, as planned here (Opus lacking only an explicit `medium`),
  or just effort set versus omitted?
- **D3, billing witness.** Will the principal record Console usage per model and
  day after the series? Optionally, the Usage and Cost API with an admin
  credential could supply it.
- **D4, independent transport witness.** Use an apparatus CONNECT proxy, which
  changes the commissioned route, or accept and record the unmet requirement.
- **D5, reruns.** Can a run that fails the gate be repeated inside the same
  authority? At a ceiling of 8.25 there is no slack unless D1 frees some.

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
(`apparatus/studies/interaction/RESULTS.md` at `77375f1`). Recheck source,
writer, image, input and saved-connection bindings before using any of them.

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

The Messages launcher in step 2 can use a saved connection directly. Run from
the development VM, alignment needs neither a delegated queue nor a manual
handoff to reach the container runtime.
