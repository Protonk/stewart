# Small-commission conformance apparatus

[`c10.py`](c10.py) prepares bounded batches, retains every audit and reviews
immutable evidence exports. It uses the real Stewart binary through its CLI.
The procedural obligations come from [ACCEPTANCE C10](../../ACCEPTANCE.md#the-real-model-conformance-tier),
[INTERFACE](../../docs/INTERFACE.md) and [QUESTION-FORMS](../../docs/QUESTION-FORMS.md).
It assigns no answer-quality grade and never declares a model qualified.

This implementation permits one placement per audit. It covers small fixed
commissions, lost caller replies and later custody actions. Interrupted
continuation, real provider compaction, full-size histories and the full C10
repetition matrix remain outside its checked scope. The live provider route is
direct TLS; the reviewer correlates Stewart-owned provider captures there.
Only rehearsal has an independent provider witness. This limitation must remain
visible in any live report.

## Cases and counts

[`catalog.json`](catalog.json) fixes six commissions. Each has an ordinary and
an inadequate-evidence variant with the same question body. Materials are copied
byte for byte from the worked examples; [`specimen-provenance.json`](specimen-provenance.json)
records the mapping. Illustrative returns are references for human inspection,
never model inputs or expected answers. The actual question file is rendered
with the selected family, model, effort, limits and return destination.

| Case IDs | Family | Ordinary materials | Inadequate materials |
| --- | --- | --- | --- |
| `open-ordinary`, `open-inadequate` | Open inquiry | Implementation A, requirements, report | Report alone |
| `framing-ordinary`, `framing-inadequate` | Inquiry framing | Implementation A, requirements, report | Requirements alone |
| `comparison-ordinary`, `comparison-inadequate` | Comparison | Implementations A and B, requirements | Implementation A and requirements |

All submissions use nested material paths. Intake independently witnesses and
reads back every file through `receipt --read`. Catalog hashes bind metadata
and recursive material membership, including empty directories. Submission
hashes bind the rendered question and input bytes separately in each audit.

The full gate needs three default-effort repetitions of each commission, plus
one effort-set audit, one compaction audit and one killed-and-continued audit:
18 + 3 = 21 audits per model. Placements and provider request attempts are
separate counts. The interrupted audit needs more than one placement and cannot
be launched by this implementation. These quantities grant no spending authority.

## Run the offline checks

From the repository root:

```sh
python3 -I -B apparatus/c10/test_c10.py
python3 -I -B apparatus/sanity/test_launch.py
python3 -I -B apparatus/driver/stewart_driver.py --self-test
python3 -I -B apparatus/check_links.py
```

Native iteration uses an existing native binary and a new absolute directory.
It needs permission to listen on loopback; when the agent shell cannot do that,
the operator runs it on the host. It makes no model calls.

```sh
python3 -I -B apparatus/c10/smoke.py \
  --binary "$PWD/service/target/debug/stewart" \
  --evidence "$PWD/.scratch/c10-native-NN" --check-operations
python3 -I -B apparatus/c10/check_review.py \
  "$PWD/.scratch/c10-native-NN/private/open-ordinary-r1" \
  "$PWD/.scratch/c10-review-controls-NN"
```

`--case open-ordinary` selects one ordinary case; `--audit control-unsubmitted`
selects that control alone. `--check-operations` requires the unsubmitted control
and explicitly exercises manager close and confirmation on its synthetic return.
It adds a second export; the first stays unchanged. It is never enabled for a
live audit. Native runs explicitly skip Linux process-access controls and are
not qualification evidence.

Commit the apparatus before a Linux rehearsal: its source comes from a Git
archive of `HEAD`. Supply the qualification ID of the intended retained native
aarch64 executable. The launcher checks the qualification record and refuses
dirty apparatus source, mismatched bindings and reused evidence directories.

```sh
python3 -I -B apparatus/c10/c10.py rehearse \
  "$PWD/.scratch/c10-launch-NN" --qualification QUALIFICATION_ID
python3 -I -B apparatus/c10/c10.py review "$PWD/.scratch/c10-launch-NN"
```

The rehearsal uses Apple `container` 1.6.1, a pinned Python image, Linux aarch64,
512 MiB of memory and no external network. It retains the container and private
originals. The Linux process-access checks use the existing launcher's same-user
and different-user controls. Environment, filesystem observations and process
RSS high-water marks are retained; these do not qualify full-size C10 workloads.

The rehearsal contains 13 audits: the six fixed cases and seven controls.

| Control | Expected observation |
| --- | --- |
| Empty submission | Valid submission; no entry or citation coverage |
| Unsubmitted ending | Retained work, no auditor submission |
| Provider rejection | No submission; provider failure preserved |
| Lost caller reply | Status reconciles the retained audit; no replacement placement |
| Reflected synthetic credential | Incomplete review; export withheld |
| Export contamination | Private original retained; export withheld |
| Export failure | Failed export recorded; private original retained |

The lost-reply control discards the caller's returned value while preserving the
original process streams. It does not claim to test a killed launcher or auditor.
Linux rehearsal also runs 14 reviewer comparisons (12 altered-evidence controls
and two invariances) and seven operator comparisons. The latter exercise wrong-key
refusal, manager close, inspection, explicit confirmation, follow-up export,
manager attribution and preservation of the original snapshot. Live launch
requires these complete results and a matching apparatus, binary, image and catalog.

## Prepare a concrete live commission

`propose` writes an unpaid, unbound proposal. Defaults are one repetition,
12 turns, 160,000 cumulative input tokens, 12,000 cumulative output tokens and
a 900-second watchdog per audit. Select cases explicitly for a minimal trial;
review and adjust the allowances before authorization.

```sh
python3 -I -B apparatus/c10/c10.py list
python3 -I -B apparatus/c10/c10.py propose --model EXACT_MODEL_ID \
  --case open-ordinary --output "$PWD/.scratch/c10-proposal.json"
python3 -I -B apparatus/c10/c10.py packet \
  "$PWD/.scratch/c10-proposal.json" "$PWD/.scratch/c10-packet.json" \
  --qualification QUALIFICATION_ID
```

The `stewart.c10-commission/1` packet fixes every audit ID, case, repetition,
specimen hash, model, effort, cumulative limits, watchdog, endpoint, retry policy
and executable/source/image binding. Unknown fields, duplicate JSON keys and
duplicate identities are refused. `effort: null` omits effort. The route is
`https://api.anthropic.com`, with no proxy. The packet allows one placement and
up to four built-in attempts per provider request. It permits no wrapper retry,
model fallback or automatic continuation. An unexpected outcome stops the batch;
all later planned audits remain accounted for as not started.

Before authorizing the exact final packet digest, the principal fills its
non-secret `account` labels and `spending_authority` and reviews a dated provider
compatibility/cost assessment. A nonempty authority field is an input guard,
not proof of permission. Do not put credentials in any packet field. Token
allowances and a watchdog are not a dollar ceiling. These commands do not
authorize a live run:

```sh
shasum -a 256 .scratch/c10-packet.json
python3 -I -B apparatus/c10/c10.py live "$PWD/.scratch/c10-live-NN" \
  --qualification QUALIFICATION_ID --commission "$PWD/.scratch/c10-packet.json" \
  --approved-commission APPROVED_SHA256 --rehearsal "$PWD/.scratch/c10-launch-NN"
```

Run an authorized live launch in a separate interactive terminal. The launcher
first checks bindings, opens a credential-free TCP connection to the provider
and completes every intake/readback. It then requests the key without echo and
sends it through an inherited descriptor. Keys never belong in argv, environment
variables or chat. Private command records remain in the container. Automatic
ordinary close occurs only after a checked auditor submission. A failure does
not authorize restarting the batch.

## Operate retained audits

`host/operator.json` lists every audit and its retained container. All four
commands below avoid model calls. `close` ends authoring; use it only when that
is the intended disposition of an unsubmitted audit.

```sh
python3 -I -B apparatus/c10/c10.py control "$PWD/.scratch/c10-live-NN" AUDIT_ID status
python3 -I -B apparatus/c10/c10.py control "$PWD/.scratch/c10-live-NN" AUDIT_ID close
python3 -I -B apparatus/c10/c10.py control "$PWD/.scratch/c10-live-NN" AUDIT_ID inspect
python3 -I -B apparatus/c10/c10.py control "$PWD/.scratch/c10-live-NN" AUDIT_ID collect
```

`status` reports run state, seal actor, delivery and closure separately. Unknown
conditions remain unknown, with the raw reply retained privately. `inspect`
verifies package bytes and identifies the answer to read privately; it does not
judge its contents. If close requires confirmation, inspect the return, then
issue `close --confirm TOKEN` explicitly. There is no automatic loss surrender.

`collect` needs an interactive terminal to re-enter the original credential for
scanning. A private HMAC check refuses a different key without storing the key
itself. It observes the writer stopped under the operator lock, repeats the
evidence-membership and credential checks, and creates `export-0002`, then
`export-0003`, and so on. It never changes an earlier snapshot. Uncertain or
credential-bearing evidence stays private; do not bypass withholding by copying
the container wholesale. Status and later custody actions do not resume a model.

## Evidence and review limits

The host retains qualification checks, source archive/digest, command streams,
container identity, packet and launch result. `container/PLAN.json` lists every
planned audit before intake; `RESULT.json` records actual outcomes and skips.
Each audit's exported snapshot contains its input witness, accepted readbacks,
invocation records, provider captures, authoring records and return. Fake request
and response witnesses live outside Stewart's archive. The synthetic credential
witness and credential-check markers stay private, outside exported audit roots.

Each `EXPORT.json` records its observation interval, completeness result,
credential scan and archive digest. The reviewer validates archive membership
and streams its digest without extracting it. Required oversized or unreadable
members yield incomplete evidence; they are never silently omitted. Per-file
reads are bounded at 64 MiB, with a 32 MiB response limit. A greater-than-2-MiB
response invariance exercises the removal of the older indexer's one-MiB cutoff;
it is not a full-history scale test.

The reviewer reconstructs raw ordinary requests, reconciles request attempts and
reported/estimated usage, checks the pinned arrangement and output caps, links
tool effects to accepted edits, validates mechanical citations against witnessed
inputs, and derives prepared/selected answer bytes and exact delivered membership
from the edit history. Reports distinguish `procedural_checks_passed`,
`not_submitted` and `incomplete`, with submission, actor, delivery and closure as
separate facts. Unused tools and form sections are coverage observations. Empty
answers are admissible. Review exit zero means its available snapshots were
read without incomplete evidence; it does not assert auditor submission or
qualification. Read each outcome, including withheld or failed exports.

Provider usage is not independently observed billing. Cost assessment, billing
reconciliation, independent observation of live authoring, kill/continuation and
real signed-summary compaction need their own evidence and explicit disposition.
Preserve every failed attempt, original and witness through review under
[the retention rules](../../DEVELOPMENT.md#evidence-and-retention). Nothing here
removes containers or evidence.
