# Endpoint alignment

**Current status:** The alignment tier is specified; the mechanism is not built.
Its sources are the Messages small-commission apparatus (`apparatus/c10`, with
parts of `apparatus/sanity`) and the harness profile and check tooling
(`apparatus/claude-code`, with the independent `apparatus/driver/claude_code_*`
fixtures). No live run is authorized by this plan.

Stewart talks to two Anthropic endpoints: the Messages API, from the distributed
binary, and the Claude Code harness, from the source-build development runtime.
Each adapter, and each stand-in that replaces it in the scripted suites (the fake
provider, the synthetic harness), encodes assumptions about its endpoint.
Alignment observes the real endpoint in a small approved run, compares what it
saw with those assumptions, turns the observations into stand-in fixtures and
records the result. A release names only endpoint versions with a current
alignment record. The [alignment tier](ACCEPTANCE.md#the-endpoint-alignment-tier)
owns the gate, [INTERFACE 6](docs/INTERFACE.md#6-the-run-adapter) the Messages
adapter, and the [runtime contract](docs/claude-code/CONTRACT.md) the harness
launch, its documented facts and what remains undemonstrated with the real
harness.

Routine design, offline rehearsal and carry-over are authorized. Each live
alignment run needs the principal's approval of its concrete packet and budget;
container runs remain the principal's to schedule. Keep open audits and their
exact writers until closure or explicit disposition.

## 1. Specify the alignment check

- [ ] Fix the Messages run set the tier requires: one audit per implemented
  family to the auditor's own submission, one compaction run past the pinned
  trigger in [INTERFACE 6.2](docs/INTERFACE.md#62-requests-and-responses), and
  one run with each manager-selectable request setting such as effort. Name each
  run's specimen, the mechanisms it must reach and the evidence that shows them;
  reuse the prepared specimens. A run that leaves a mechanism unreached reports
  it unexercised rather than counting it.
- [ ] List the endpoint assumptions to compare: each response, usage, error,
  compaction and stop shape the adapter decodes and the fake provider replays,
  with the dated primary documentation they rest on (model, API and beta
  versions, effort, compaction, authentication, output cap, timeout). Name the
  capture that witnesses each.
- [ ] State each witness's origin and scope. On the direct TLS route Stewart's
  own captures are correlated, not independent observations of what reached the
  provider; bring any obligation that needs more to the principal rather than
  quietly adding a proxy or claiming independence.
- [ ] Define harness alignment: the pinned version's documented facts in the
  runtime contract rechecked against current documentation, a reviewed
  supplied-surface check that produces the profile's `check` attestation, and one
  short audit to the auditor's own submission. Add targeted observations for the
  contract's not-yet-demonstrated list where a bounded run can reach them.
- [ ] Define the alignment record: endpoint, model and versions, binary, date,
  runs, differences and their resolutions, captured fixtures and cost, and the
  pinned inputs whose change ends its currency. Extend `apparatus/qualified.py`
  to keep it and check it against its evidence. Historical `c10-*` and
  `readiness-*` records stay as they are.

**Done when:** each run, assumption, witness and record field has an owner and a
check design, and the principal has approved the run set and its order of cost.

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
- [ ] Add a Linux route for the harness. Today `pin.py` and `profile.py` verify an
  Apple code signature against a native macOS pin; Linux binaries have none, and
  the signed manifest is their integrity check. Pin a Linux executable against
  the manifest, prepare a `linux-x86_64` or `linux-aarch64` profile and run its
  check on Linux, rehearsing offline first. Keep the route short enough for a
  person outside this checkout to follow.
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
  cost estimate, obtain approval, run, review and record. Resolve every
  difference by an adapter fix, a stand-in fixture or a limitation the release
  states before the record counts as current.
- [ ] Align the harness pin the development build uses, through the Linux route,
  producing its profile check.

Real-model repetition, effort comparisons and killed-and-continued placements,
which the former conformance matrix required, are experiment-tier questions, not
alignment tasks.

Complete this plan when the mechanism is built, each model the first release
names and the harness pin have current alignment records, and the enduring
procedure is documented in `alignment/`. Then delete the plan.
