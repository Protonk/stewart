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

## Experimental family guidance

For an ordinary qualified binary, select `guidance: guidance.md` in an open-inquiry
study template and supply that root file. It replaces the family block through
the product's capture and receipt path. Rehearse the exact templates before live
use. Supplied guidance cannot be combined with a study-build override.

The optional study-build path admits an explicitly **unqualified** Linux binary
for an open-inquiry family-guidance experiment. It supports changed family text
and its version; tool schemas, citation checks, rendering, revision and submission
keep the ordinary procedural checks. It makes no product or model qualification
claim and does not update the qualification front.

Keep the variant in a reachable branch commit. Change its specification and
service together, run both native Cargo configurations, and use the independent
driver from the committed apparatus checkout unchanged on the study branch.
Ordinary driver maintenance, including an authorized timing-budget change,
lands in that checkout first; a study build using a different driver is refused.
Identify the expected text/version differences in the
experiment proposal. Run `acceptance.sh` on the
variant commit and retain its failed result as an experiment; **do not extract
that run into the qualification front**. Inspect the actual failures and record
the exact expected case/check and self-test failures before binding them. An
unexpected difference needs investigation; it cannot simply be included to
admit the build.

The interface file has schema `stewart.c10-interface/1`, an `id`, family
`open-inquiry`, an integer `version` greater than 1, and exact `instructions`.
The expectations file has `failed_cases`, mapping case IDs to sorted distinct
failed check names, and `selftest_failures`, a sorted list of full failing names
from the driver's self-test. These are experiment inputs, not product settings.

From the committed apparatus checkout, bind the retained acceptance evidence:

```sh
python3 -I -B apparatus/c10/c10.py study-build \
  /absolute/interface.json /absolute/acceptance-folder /absolute/expected.json \
  /absolute/study-build.json --qualification BASE_QUALIFICATION_ID
```

The command checks both architectures' complete case inventory, exact expected
failure names, controls, binary identities and build evidence. It permits only
the same partial skips already recorded in the qualified base; new skips refuse.
Credential cases must pass. Source and evidence digests are rechecked on every
binding or launch. The descriptor records the qualified base commit, variant
commit, acceptance folder, exact guidance and the unqualified status.

Rehearse with `--study-build /absolute/study-build.json` and the same
`--submission ID FOLDER` arguments proposed for live use. This runs the ordinary
offline controls plus two altered-guidance/version reviewer controls; with two
study templates there are 15 audits and 56 reviewer comparisons. A saved
connection also needs the ordinary synthetic later-collection check.

Use `packet --study-build /absolute/study-build.json` to bind an unpaid proposal.
It produces `stewart.interface-commission/1`; its `study_build` member is part of
the exact packet submitted for authorization. Live launch takes the build from
that approved packet, requires its matching successful rehearsal, and never
accepts a replacement `--study-build` argument. Historical packet schemas and
receipts remain unchanged. Reports identify the binary as `unqualified_study`.

For local iteration only, `smoke.py --interface /absolute/interface.json` accepts
a native prototype. It labels its result as local and unqualified, skips Linux
process checks explicitly, and supplies no evidence that can admit a live build.

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
python3 -I -B apparatus/c10/check_reporting.py \
  "$PWD/.scratch/c10-native-NN/results" "$PWD/.scratch/c10-report-controls-NN"
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
manager attribution and preservation of the original snapshot. Eleven report
comparisons cover the complete inventory, separate submission/closure/reply
observations, unavailable exports, pending and attributed assessments, earlier
assessment basis, identical reassembly and unchanged sources. Live launch
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
model fallback or automatic continuation. Live placement stops after a missing
checked auditor submission, lost caller reply, incomplete review, failed/withheld
export or unknown effects. All later audits remain listed as not started. A
checked limit ending is a policy stop, not an apparatus failure. Rehearsal
expectations apply only to synthetic controls; a live packet's `submitted`
scenario does not certify or require a successful scientific answer.

Before launching the exact final packet digest, the principal or an experimenter
acting under an explicit bounded delegation fills its non-secret `account` labels
and `spending_authority` and reviews a dated provider compatibility/cost assessment.
A nonempty authority field is an input guard,
not proof of permission. Do not put credentials in any packet field. Token
allowances and a watchdog are not a dollar ceiling. These commands do not
authorize a live run:

```sh
shasum -a 256 .scratch/c10-packet.json
python3 -I -B apparatus/c10/c10.py live "$PWD/.scratch/c10-live-NN" \
  --qualification QUALIFICATION_ID --commission "$PWD/.scratch/c10-packet.json" \
  --approved-commission APPROVED_SHA256 --rehearsal "$PWD/.scratch/c10-launch-NN"
```

Run an authorized live launch in a separate interactive terminal, or use the
[delegated host queue](HOST-QUEUE.md) under an explicit campaign commission.
The launcher
first checks bindings, opens a credential-free TCP connection to the provider
and completes every intake/readback. It then obtains the key by hidden entry or
the explicitly selected saved connection and sends it through an inherited
descriptor. Keys never belong in argv, environment
variables or chat. Private command records remain in the container. Automatic
ordinary close occurs only after a checked auditor submission. A failure does
not authorize restarting the batch.

## Saved provider connections

The macOS host can supply the original credential from its login Keychain for
launch and collection. Each connection is a generic password with service
`stewart-provider` and account equal to the packet's `credential_label`.
Labels contain 1–80 letters, digits, dots, underscores or hyphens, starting with
a letter or digit. Provider account/workspace labels remain manager-supplied;
Keychain presence establishes no provider identity or inference access.

Create the item in your own terminal. Keep `-w` last and enter the API key at
the hidden prompt. The default keychain must be your login keychain; inspect it
with `security default-keychain -d user` if uncertain.

```sh
security add-generic-password -s stewart-provider -a stewart-haiku -l stewart-haiku -T "" -w
python3 -I -B apparatus/c10/c10.py connection status stewart-haiku
```

`-T ""` removes the creating tool's default trusted access. Retain confirmation
before access and use the one-time Allow choice for an intended lookup; Always
Allow changes that policy. Lookup holds the key privately and passes it through
the existing container standard-input handoff after verified intake. The host
also uses it for the export scan, then drops its reference. This promises no
memory erasure or secrecy from the host administrator.

Add `--connection stewart-haiku` to `live` or `control ... collect`. The label
must equal the packet's credential label; mismatch refuses before lookup.
Without the option, hidden entry remains available. Neither route reads
`ANTHROPIC_API_KEY`, and failures never fall back to another credential source.
Status requests no password and verifies no access policy or provider access.
Password lookup has a 60-second deadline; metadata status has a 10-second one.

Diagnostics distinguish missing tool, missing item in this execution context,
denied/cancelled access, locked keychain or unavailable interaction, deadline,
invalid credential, and unclassified failure. Records keep the exit status and
fixed classification. Raw stdout and stderr are withheld, since unexpected
diagnostics could contain credentials. An invalid-parameter error followed by
item-not-found stays unclassified; it does not establish absence.

Rehearse with a separate item whose value starts with `c10-NONFUNCTIONAL-`.
Use fresh random characters after the prefix, not text present in the source or
evidence: the host credential scan must not find the value there. Enter it at
the prompt below. Never use the real item in a test.

```sh
security add-generic-password -s stewart-provider -a stewart-synthetic -l stewart-synthetic -T "" -w
python3 -I -B apparatus/c10/c10.py rehearse "$PWD/.scratch/c10-launch-NN" \
  --qualification QUALIFICATION_ID --connection stewart-synthetic
```

Rehearsal refuses a value without that prefix before handoff. After its ordinary
checks it starts a fresh launcher process, looks up the item again and collects
`open-ordinary-r1` into a second immutable snapshot. Both lookups may prompt.
Saved-connection live use requires this successful collection as well as the
full Linux rehearsal. A failed collection leaves the initial records intact
and prevents live use. Collection never starts a model.

Host checks use only the synthetic item. Retain commands, streams, exits,
macOS version, prompt observations and execution context under a new
`.scratch/connection-checks-NN`. Check metadata; observe the allowed lookup and
fresh-process collection; deny a lookup; try a missing label; and exercise a
locked keychain, restoring it afterwards. Existing operator controls test
wrong-key collection. Offline tests use a fake `security` executable and
establish no host Keychain behavior.

Rotate by creating an item with a new label and binding new packets to it.
Keep the old credential until every run using it has been collected. Historical
packets stay unchanged. To disconnect a chosen item locally:

```sh
security delete-generic-password -s stewart-provider -a LABEL
```

This removes local access only. Provider revocation happens separately in the
Console and is not confirmed by the launcher. It never deletes an item itself.

## Study submissions

Study packets use `stewart.study-commission/1`; the six-case catalog and
`stewart.c10-commission/1` retain their existing meanings. Supply a folder with
`question.md` and `materials/`, plus `guidance.md` when explicitly selected by
`guidance: guidance.md` for open inquiry. It is a hashed template: family, `inquiry`,
optional `varies` and `guidance`, exact question body, selected guidance and
material bytes come from it. Guidance is witnessed and read back separately from
evidence materials; it replaces the effective family block on the same binary.
It cannot be combined with a separate study-build instruction override. The run
packet supplies model, effort and cumulative allowances; the launcher supplies
destination. Those front-matter fields are rendered anew. Template settings
in those positions are not live settings or spending authority.

An inquiry label is required. Omit `varies` for a baseline without an earlier
audit; a supplied reference is preserved as the manager's attributed note.

```sh
python3 -I -B apparatus/c10/c10.py propose --model EXACT_MODEL_ID \
  --submission problem-a /absolute/submission-a \
  --output "$PWD/.scratch/study-proposal.json"
```

Each named template becomes one explicit placement. Study proposals cannot
select catalog cases or implicit repetitions. The defaults are the small
proposal allowances above; size them for the actual corpus before authorization.
`packet`, approval by exact digest and `live` follow the same route as C10.
This mode accepts no experimental or unqualified binary.

The packet binds each absolute folder and its inventory digest, including empty
directories. The host verifies and stages it; the container verifies it again,
retains an independent template copy, renders intake, witnesses every rendered
file and reads it back through the binary's receipt interface before requesting
a credential. Changes, missing members, links and special files refuse. Failed
copies remain in the new evidence folder; original source folders are unchanged.

The Linux rehearsal must include each template hash proposed for live use:

```sh
python3 -I -B apparatus/c10/c10.py rehearse "$PWD/.scratch/c10-launch-NN" \
  --qualification QUALIFICATION_ID --connection stewart-synthetic \
  --submission problem-a /absolute/submission-a \
  --submission problem-b /absolute/submission-b
```

This runs all 13 fixed scenarios plus one audit per template. The rehearsal
auditor follows the ready `next` read when a material exceeds one 65,536-byte
page and requires the reassembled pages to equal the witnessed bytes. The ordinary 14
reviewer comparisons and seven operator comparisons remain required. Each study
audit also gets 18 reviewer comparisons, including four template tampering
controls and two invariance cases. A selected guidance attachment adds four
controls for changed/missing capture, changed template and changed readback. Live launch checks complete coverage and
successful reviews. Native iteration accepts the same `--submission ID FOLDER`
arguments on `smoke.py`; run `check_review.py` on each resulting study audit.
Native checks are not Linux qualification.

The reviewer binds template inventory to the packet, checks deterministic
rendering, then verifies the captured commission and answer. The auditor gets
the question body, existing form/tools and ordinary material access. Reviewer
guidance outside the supplied template is not added to its world.

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

`status` reports authoring state and its first end reason, run state, seal
presence and actor, delivery and closure separately. Operator summaries preserve
unknown usage with known limits and identify when private diagnostics exist.
Current consumers require `stewart.reply/2`; historical reports are retained
without conversion. Unknown
conditions remain unknown, with the raw reply retained privately. `inspect`
verifies package bytes and identifies the answer to read privately; it does not
judge its contents. If close requires confirmation, inspect the return, then
issue `close --confirm TOKEN` explicitly. There is no automatic loss surrender.

`collect` needs the original credential for scanning: hidden terminal entry by
default, or the selected saved connection. A private HMAC check refuses a different key without storing the key
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
from the edit history. Version 2 reviews distinguish completed procedural checks
(`checked`) from `incomplete` evidence. Submission, actor, delivery and closure
are separate facts; an incomplete review leaves those facts unknown. The
automatic-close and rehearsal-admission consumers still require a checked
auditor submission. Empty answers are admissible. Review exit zero means every
planned audit has a checked latest snapshot; it does not assert submission,
answer quality or qualification. Earlier observations remain visible, including
when a later collection is withheld or incomplete.

Coverage records include read/search calls, incomplete pages, offered next-page
calls and later exact tool/input matches with those offers. This narrow check
establishes what was offered and attempted in complete captures. It does not
infer understanding, complete reading, successful pagination or answer quality;
semantically equivalent calls are outside its exact-match count. Missing evidence
produces unknown coverage, not zero. Live captures remain Stewart-owned evidence.

The version 2 session records distinguish placement observation, lost caller
reply, pre-close review, automatic close and export. The host retains its own
operations and a digest reference to the session. A successfully observed live
policy stop can exit zero while reporting unstarted work. A failed operation or
incomplete observation remains nonzero. Export reasons distinguish incomplete
evidence, credential matches, scan uncertainty and archive-write failure. Host
failures name their step and retain controlled exception classifications; private
exception text is not printed. Historical receipts retain their original schemas.

Provider usage is not independently observed billing. Cost assessment, billing
reconciliation, independent observation of live authoring, kill/continuation and
real signed-summary compaction need their own evidence and explicit disposition.
Preserve every failed attempt, original and witness through review under
[the retention rules](../../development/DEVELOPMENT.md#evidence-and-retention). Nothing here
removes containers or evidence.

## Assemble an experiment report

[`REPORTING.md`](REPORTING.md) defines the reading, authority boundaries, source
bindings and later updates. `report` makes a question-first reading from an
attributed proposal, retained batch plans and optional attributed assessment. It
does not launch, close, collect or decide scientific success. The technical return
is available while interpretation is pending.

Create a block manifest using the exact file hashes. Paths are relative to the
manifest or absolute. Select each retained `container/PLAN.json`; for native
iteration use `results/PLAN.json`. The proposal is ordinary UTF-8 Markdown.

```json
{
  "schema": "stewart.experiment-block/1",
  "proposal": {
    "author": "Experimenter name",
    "document": {"path": "proposal.md", "sha256": "EXACT_PROPOSAL_SHA256"}
  },
  "batches": [
    {"path": "../retained-batch/container/PLAN.json", "sha256": "EXACT_PLAN_SHA256"}
  ]
}
```

```sh
python3 -I -B apparatus/c10/c10.py report /absolute/block.json /absolute/return-01
```

The new output directory contains `report.md` and the matching `report.json`.
The proposal states the question, comparison, discriminating observations,
budget, explicit placements, variations and stopping rules. It is not a spending
authorization. The report inventories all planned audits, every collected
snapshot, current gaps, usage and custody work. Reassembly refuses an existing
output directory and never writes to a retained batch. An unsupported historical
session is linked and explicitly unassessed; its available exports can still be
reviewed from their original bytes. No receipt is upgraded in place.

When the experimenter's assessment is ready, write it as ordinary UTF-8 Markdown
and bind it to the `technical_sha256` in the technical return:

```json
{
  "schema": "stewart.experiment-assessment/1",
  "technical_sha256": "EXACT_TECHNICAL_POSITION_SHA256",
  "assessment": {
    "author": "Experimenter name",
    "document": {"path": "assessment.md", "sha256": "EXACT_ASSESSMENT_SHA256"}
  }
}
```

```sh
python3 -I -B apparatus/c10/c10.py report /absolute/block.json /absolute/return-02 \
  --assessment /absolute/assessment.json
```

The assessment should explain the findings and limits, unresolved judgment,
unexercised mechanisms, estimated/calculated costs, independent billing or its
explicit deferral, and remaining actions with actor and authority. These remain
the author's claims. Supplying text neither clears technical gaps nor blocks
custody work. After new collection, an assessment bound to an earlier position
is visibly marked for reconciliation. A report can be useful with unknown or
inconclusive findings; it supplies no universal verdict on the experiment.

Report exit status is nonzero for missing or incomplete current observations,
unassessed session records or execution records needing reconciliation. Later
checked evidence can resolve unknown effects while retaining the original failure
as a dated fact; it does not permanently fail the new report.
Pending interpretation alone does not make it fail. All source identities and
checked details remain inspectable in JSON; earlier dated observations are not
replaced by a new account. Neither output establishes independent billing or
author authenticity.
