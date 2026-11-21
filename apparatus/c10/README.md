# Small-commission conformance apparatus

[`c10.py`](c10.py) prepares bounded batches, retains every audit and reviews
immutable evidence exports. It uses the real Stewart binary through its CLI.
The procedural obligations come from [ACCEPTANCE C10](../../ACCEPTANCE.md#the-endpoint-alignment-tier),
[INTERFACE](../../docs/INTERFACE.md) and [QUESTION-FORMS](../../docs/QUESTION-FORMS.md).
It assigns no answer-quality grade and never declares a model qualified.

Every launch performs one placement of each audit it names. It covers small
fixed commissions, lost caller replies, later custody actions, a first placement
interrupted at a witnessed point, and [separately approved later placements](#continue-a-retained-audit)
of an audit whose last placement was recorded interrupted. Nothing continues an
audit automatically. The reviewer reconstructs provider compaction from captured
exchanges; its offline controls use synthetic summaries. Real provider compaction,
a placement whose process died, full-size histories and the full C10 repetition
matrix still need their own evidence. The live provider route is direct TLS; the reviewer correlates
Stewart-owned provider captures there. Only rehearsal has an independent
provider witness. This limitation must remain visible in any live report.

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

The offline reader tests use [complete captured acceptance records](../testdata/acceptance/README.md).
Their declared study difference is a named synthetic projection; original
records, including historical skips, remain unchanged.

Keep the variant in a reachable branch commit. Change its specification and
service together, run both native Cargo configurations, and use the independent
driver from the committed apparatus checkout unchanged on the study branch.
Ordinary driver maintenance lands in that checkout first. A study build using
a different driver is refused.
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
study templates the first placements cover 24 audits and 56 ordinary/template
reviewer comparisons, plus the 26 compaction comparisons. A saved connection also needs the ordinary synthetic
later-collection and continuation checks.

Use `packet --study-build /absolute/study-build.json` to bind an unpaid proposal.
It produces `stewart.interface-commission/2`; its `study_build` member is part of
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

The endpoint alignment tier needs one run of each case per named model, spread
across the effort values, plus one compaction run. Repetitions, effort
comparisons and killed-and-continued audits are experiment-tier questions
([ACCEPTANCE](../../ACCEPTANCE.md#the-endpoint-alignment-tier)). Placements and
provider request attempts are separate counts. An interrupted audit needs more
than one placement: its first is launched with a witnessed interruption and each
later one is a separately approved [continuation](#continue-a-retained-audit). Killing the process is a
different case that this apparatus does not exercise. These quantities grant no
spending authority.

## Run the offline checks

From the repository root:

```sh
python3 -I -B apparatus/c10/test_c10.py
python3 -I -B apparatus/c10/test_placements.py
python3 -I -B apparatus/sanity/test_launch.py
python3 -I -B apparatus/check_links.py
```

The apparatus imports specification-derived helpers from the release driver
(`driver_core.py`, `rawjson.py`, `answer_witness.py`, `credential_observer.py`).
When one of those changes, run these checks as well as the driver's own
self-test; they are in the apparatus source binding, so a change to them also
needs a new rehearsal.

Native iteration uses an existing native binary and a new absolute directory.
Run it where the fake provider can listen on loopback. It makes no model calls.

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

The rehearsal uses rootless Podman 5.x, the preloaded qualified arm64 Python manifest,
two CPUs, 512 MiB of memory and loopback only. A fresh named volume on guest ext4
holds the archive and independent witnesses at `/work`. Keep the volume and its
named container through review. Run operator commands from the same guest
account. The Linux process-access checks use the launcher's same-user and
different-user controls. Environment, filesystem observations and process
RSS high-water marks are retained; these do not qualify full-size C10 workloads.

The rehearsal contains 27 audits and 35 placements: the six fixed cases, thirteen
single-placement controls and eight continued controls of two placements each.
Its output allowance is 30,000 tokens, not the proposal default, so that an
interrupted control can absorb one estimated request and still start again
([the reason](#continue-a-retained-audit)).

| Control | Expected observation |
| --- | --- |
| Empty submission | Valid submission; no entry or citation coverage |
| Unsubmitted ending | Retained work, no auditor submission |
| Provider rejection | No submission; provider failure preserved |
| Lost caller reply | Status reconciles the retained audit; no replacement placement |
| Reflected synthetic credential | Incomplete review; export withheld |
| Export contamination | Private original retained; export withheld |
| Export failure | Failed export recorded; private original retained |
| Compaction | Two summaries, unchanged signed arrays, replaced context and preserved recorded work; auditor submission |
| Below compaction trigger | Same selected answer at 149,999 top-level tokens, with no summary or reset |
| Invalid compaction | Summary tool block executes nothing and consumes no reminder; interrupted with `protocol_anomaly`, recorded work retained |

The compaction scripts differ in their top-level trigger count: 150,000 or
149,999, including output. Iteration charges are smaller; the fake tests which
count governs the trigger without producing a real 150,000-token conversation.
Two entries precede the first summary, re-entry checks them before revision,
and re-entry after the second checks the revised selection. Summary usage has
both `message` and `compaction` iterations and differs from top-level usage.
These are apparatus controls, not provider or full-history scale evidence.

The lost-reply control discards the caller's returned value while preserving the
original process streams. It does not claim to test a killed launcher or auditor.

| Continued control | First placement | Second placement |
| --- | --- | --- |
| `continue-cap` | Thinking-only response at the output cap: interrupted, `max_tokens`; nothing recorded | Ordinary work; sealed by the auditor |
| `continue-entries` | The same ending after two recorded entries | Finds them through re-entry, revises one and removes the other; sealed |
| `reminder-spent` | Prose draws the reminder; signalled after its recorded notice while the provider holds the request carrying it: interrupted, `signal` | The next ordinary ending ends authoring unsubmitted; no second reminder |
| `reminder-spent-unheld` | The same, but nothing is held: signalled as soon as the notice is seen, as a live placement is | The same unsubmitted ending, whichever timing the signal met |
| `reminder-spent-submits` | As `reminder-spent` | Submits unprompted; sealed |
| `reminder-unused` | Signalled after its recorded entries, before any reminder, with the request held | Prose draws the audit's one reminder; sealed |

The signalled controls show the [interruption witness](#interrupt-a-first-placement-at-a-witnessed-point)
and, between them, that a reminder is spent once for the whole audit. The three
held ones make the aborted-in-flight estimate certain. The unheld one leaves the
timing to chance, as a live interruption does; its endings are the same either
way and the witness records which timing occurred.

The first launch runs every audit's first placement and exports it. The host
then starts the second placement of each continued control through the same
`continue` path a live continuation uses, against the rehearsal's own retained
container: a generated `rehearsal-only` packet bound to the prior state read
from that control's first export, the committed source delivered into a new code
directory, the packet delivered, the preflight record awaited, then the same
synthetic key. Each keeps its host records in its own new folder beside the
rehearsal, named `REHEARSAL-CONTROL-p2`; the rehearsal folder's name must
therefore be short, unused and made of lowercase letters, digits and hyphens.
`host/continuations.json` lists all six. The first one that fails leaves the
rest not started, and the rehearsal fails.

Linux rehearsal also runs 14 reviewer comparisons (12 altered-evidence controls
and two invariances) and seven operator comparisons on the first placements.
Another 26 comparisons cover compaction: 19 altered-evidence controls, six
unchanged/large-response invariances and equality of the selected answer above
and below the trigger. They exercise omitted summary requests/responses,
changed/omitted signed blocks, retained old context, missing iterations, omitted
charges, repeated interpreted iteration fields, summary tool execution, changed post-summary notices and wrong failure
endings. The final answer comparison retains revisions, entry versions, text
and resolved citation metadata while excluding audit-local handles.
The latter exercise wrong-key
refusal, manager close, inspection, explicit confirmation, follow-up export,
manager attribution and preservation of the original snapshot. Eleven report
comparisons cover the complete inventory, separate submission/closure/reply
observations, unavailable exports, pending and attributed assessments, earlier
assessment basis, identical reassembly and unchanged sources.

Each continuation in the rehearsal carries two further kinds of control. Right
after the placement, the container offers the same packet to its preflight
again; it must be refused at the placement count, which shows that the
service's own record, not the attempt folders, is what prevents a second start.
Then, on the finished two-placement audit, it runs reviewer comparisons for
continued audits (13 altered-evidence controls and one invariance: omitted
placement captures or records, a changed continuation notice, a reminder
recorded or resent twice, usage or the request cap reset between placements, an
effect claimed twice, a changed earlier record or ending, an earlier placement
recorded for a dead process, a changed interruption timing or witness), 14
report comparisons, and for the two controls left unsubmitted eight operator
comparisons. A reviewer control with no subject in a control's evidence is
listed as not applicable; which ones are is fixed per control before they run,
and none is skipped.

| Continued control | Reviewer comparisons run / controls fired | Not applicable | Report | Operator |
| --- | --- | --- | --- | --- |
| `continue-cap` | 11 / 10 | 3 | 14 | none |
| `continue-entries` | 12 / 11 | 2 | 14 | none |
| `reminder-spent` | 14 / 13 | 0 | 14 | 8 |
| `reminder-spent-unheld` | 13 / 12 or 14 / 13 | 1 or 0 | 14 | 8 |
| `reminder-spent-submits` | 14 / 13 | 0 | 14 | none |
| `reminder-unused` | 14 / 13 | 0 | 14 | none |

Nothing was recorded before `continue-cap`'s interruption and neither capped
control is signalled, so their effect and witness controls have no subject. The
request-cap control has a subject in the unheld control only when its signal
found a written request, which charges the estimate; hence its two shapes.

Live launch and live continuation require all of this from one retained
rehearsal made by the same committed apparatus, binary, image and catalog:
27 planned and observed first placements with none failed, skipped or not
started; the 14, seven and eleven first-placement comparisons with every
control fired and originals unchanged; all 26 compaction comparisons passed,
all 19 controls fired and the selected answers equal; eight continuations planned and completed
through the host path at their first attempt, each with its own host record
bound to the rehearsal's container and bindings and to the digest of the
container's result; the second start refused at the placement count each time;
exactly the counts in the table above, all passed, none failed or skipped,
every reviewer control fired and originals unchanged; and for each continued
control a checked final export whose log holds exactly its two endings. The
host applies the second-start and count requirements when each continuation
ends as well, so a rehearsal that misses one fails then.

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

The `stewart.c10-commission/2` packet fixes every audit ID, case, repetition,
specimen hash, model, effort, cumulative limits, watchdog, endpoint, retry policy
and executable/source/image binding. Unknown fields, duplicate JSON keys and
duplicate identities are refused. `effort: null` omits effort. The route is
`https://api.anthropic.com`, with no proxy. The packet allows one placement and
up to four built-in attempts per provider request. It permits no wrapper retry,
model fallback or automatic continuation; a later placement needs its own
[continuation packet](#continue-a-retained-audit). Live placement stops after a missing
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
sha256sum .scratch/c10-packet.json
python3 -I -B apparatus/c10/c10.py live "$PWD/.scratch/c10-live-NN" \
  --qualification QUALIFICATION_ID --commission "$PWD/.scratch/c10-packet.json" \
  --approved-commission APPROVED_SHA256 --rehearsal "$PWD/.scratch/c10-launch-NN"
```

For a direct authorized launch, use the dedicated launcher account. For a
delegated campaign dispatch through the [host queue](HOST-QUEUE.md).
After checking bindings and a credential-free TCP preflight, the launcher
verifies intake and reads the key from its packet-bound keyring label.
Keys travel through container stdin and a one-use Stewart descriptor.
Automatic ordinary close follows a checked auditor submission.

## Saved provider connections

In a `stewart-launch` login, provision the key through the non-echoing prompt
after boot. The command sends validated bytes to `keyctl padd` on stdin, under
the type `user` and description `stewart-provider:LABEL`. Its permission
mask grants access to the launcher UID. A label starts with an ASCII letter
or digit and contains up to 80 letters, digits, dots, underscores or hyphens.

```sh
python3 -I -B apparatus/c10/c10.py connection store stewart-haiku
python3 -I -B apparatus/c10/c10.py connection status stewart-haiku
```

For each placement the launcher scans its staged Git archive, commission and
supplied inputs with the bound credential after intake and before handing the
credential to the child. A literal or decoded ASCII JSON match, or an
incomplete staging scan, closes the child's input without sending the key.
A staging match identifies bytes already present before the provider request.

Private scan receipts group matching files by a fixed artifact class, the
step that produced it, and the match form. A literal match takes precedence
when one file contains both forms. The receipt preserves counts without copying
matched bytes, excerpts or filenames. The final host scan covers the entire
launch directory, including staged inputs, launcher command output and
container exports. The independent audit scan covers the private working tree
before packaging.

Every process obtains the launcher user's persistent keyring with
`keyctl get_persistent @s`. This refreshes the ring inactivity timeout.
Status searches only for the type and description. Launch, continuation and
collection search for the bound label and use `keyctl pipe` over a private
pipe. Each keyctl command has a ten-second deadline. Records give the stage
and classified outcome. The Debian [metadata capture](../testdata/keyring/metadata-missing.json)
records the missing-key diagnostic used by the offline test. A missing or inaccessible key, invalid bytes or
timeout withholds the handoff. Account and workspace labels come from the
manager.

Live launch and collection use the packet's `account.credential_label`.
An explicit `--connection LABEL` must match. Supply a separate rehearsal
connection whose payload begins with `c10-NONFUNCTIONAL-` followed by fresh
random characters. The synthetic witness stays outside the archive and exports.
A complete saved-connection rehearsal uses a new process for follow-up
collection and for each of the eight continuation controls.

```sh
python3 -I -B apparatus/c10/c10.py connection store stewart-synthetic
python3 -I -B apparatus/c10/c10.py rehearse "$PWD/.scratch/c10-launch-NN" \
  --qualification QUALIFICATION_ID --connection stewart-synthetic
```

Check the guest's `/proc/sys/kernel/keys/persistent_keyring_expiry` against the
intended idle interval. Expiry and reboot can require fresh provisioning.
Rotate through a new label. Keep the original key available for collection
and retain superseded writers, launchers and private containers with audits
that still need them. Local removal and provider revocation are separate
operations.

## Study submissions

Study packets use `stewart.study-commission/2`; the six-case catalog and
`stewart.c10-commission/2` retain their existing meanings. Supply a folder with
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

This runs all 27 fixed audits plus one audit per template. The rehearsal
auditor follows the ready `next` read when a material exceeds one 65,536-byte
page and requires the reassembled pages to equal the witnessed bytes. The ordinary 14
reviewer comparisons and seven operator comparisons remain required. Each study
audit also gets 18 reviewer comparisons, including four template tampering
controls and two invariance cases. A selected guidance attachment adds four
controls for changed/missing capture, changed template and changed readback. Live launch checks complete coverage and
successful reviews. Native iteration accepts the same `--submission ID FOLDER`
arguments on `smoke.py`; run `check_review.py` on each resulting study audit.
Native checks are not Linux qualification.

To exercise compaction on supplied bytes, add `--study-scenario ID compaction`
to `rehearse` or `smoke.py`. The other choices are `compaction-below` and
`compaction-invalid`. Name each comparison as a separate `--submission`; the
same folder can supply all three. These scenarios use built-in guidance, keep
the full fixed rehearsal inventory, and are refused for live packets. The
successful script records entries, summarizes twice, recovers and revises the
same entry, then submits. Its comparison changes only the reported trigger
count; the invalid summary leaves recorded work unsubmitted. They still use
synthetic token counts, regardless of file size.

`compaction_specimen.py /absolute/new-submission` generates eight deterministic
65,536-byte trace files and a short receipt rule. Its question asks for an early
recorded account and later revision after reading the traces. The generator
makes no provider calls; its byte count does not establish a token count or
promise that a live model reaches the compaction trigger. Keep the generated
inventory and rehearse its exact hash before binding a live packet.

Each supplied compaction audit adds four template-tampering controls to its
compaction comparisons: 16 checks for `compaction`, eight for
`compaction-below`, and 13 for `compaction-invalid`. Each includes two
invariances. `check_review.exercise_compactions` can compare three named audits
over the same template, including equality of the selected answers above and
below the trigger: 38 checks in total, with 31 negative controls. Review actual
request/export sizes and Linux memory observations separately from the synthetic
usage ledger; a small charged count cannot establish a small evidence footprint.
The loopback fake accepts request bodies through 64 MiB, matching the reviewer's
evidence-member bound; larger or incomplete bodies are refused. This is an
apparatus resource bound, not a provider or Stewart input limit. Native rehearsal
starts no later continuation after a failed first-placement batch or control,
keeping the failed batch for review.

The reviewer binds template inventory to the packet, checks deterministic
rendering, then verifies the captured commission and answer. The auditor gets
the question body, existing form/tools and ordinary material access. Reviewer
guidance outside the supplied template is not added to its world.

## Continue a retained audit

A continuation is one later placement of one audit, started in the container
that already holds it, on the same reference, exact writer, model and cumulative
limits. It applies only when the audit's last placement is recorded
`interrupted` with cause `signal`, `max_tokens`, `provider_unavailable`,
`provider_rejected`, `context_exhausted`, `provider_refusal` or
`protocol_anomaly`, and only up to four placements per audit. A sealed or ended
audit goes to custody completion instead. Each continuation has its own packet,
`stewart.c10-continuation/3`, approved by exact digest; completing one
authorizes nothing further.

### Interrupt a first placement at a witnessed point

A study audit's first placement can be commissioned to stop at a witnessed
point. Add both options to a one-submission study proposal:

```sh
python3 -I -B apparatus/c10/c10.py propose --model EXACT_MODEL_ID \
  --submission problem-a /absolute/submission-a \
  --interrupt-after reminder_notice --max-placements 2 \
  --output "$PWD/.scratch/interrupted-proposal.json"
```

This writes `stewart.interruption-commission/3`: one audit, `interruption`
`{"after": "reminder_notice", "action": "signal"}` and the placement ceiling
commissioned for that audit (2–4 for a signal, 1–4 for close). `packet`, approval and `live` are unchanged,
and its rehearsal is the ordinary one that includes the same template. Live packets can select the reminder notice, the first linked `run_started`
(P1), or the auditor's linked `answer_prepared` (P2). `--action close` issues
ordinary close at P1 or P2 and permits a single-placement ceiling. Rehearsal
also exercises a first entry. The witness begins before the new placement,
compares process identities, and copies the linked ledger through the trigger
outside the archive. At P2 it copies both prepared files. A finished placement
or an overtaken point is recorded as unexercised. The witness records its
action, the observed termination, and whether the process group is gone.

Both P1/P2 signal controls continue through the retained launcher. The
reviewer replays the cumulative ledger and usage, checks the continuation
input, and compares the witnessed files with the archived originals and the
manager's sealed return. The close controls check the actual refused later
run on the closed reference. A fake that never prepares exercises the missed
trigger, with no manager action. Report the computed trial outcome alongside
its placement outcomes. A pending continuation or outstanding confirmation
can require a later verified collection.

A live placement is signalled as soon as the record is seen, whatever the
request that carries the reminder has reached. After the process has stopped,
the witness reads the placement's own captures and attempt records and states
which of four timings the signal met, with the request, each attempt's outcome,
its `request_written` state and its charge basis:

| Timing | The request carrying the reminder | Output estimate charged |
| --- | --- | --- |
| `not_captured` | was never captured | none |
| `captured_not_written` | was captured; no byte was written | none |
| `written_unanswered` | was written and had no response | its whole `max_tokens` |
| `answered` | received a response | none; the response's reported usage counts |

The reviewer derives the timing again from the exported records and requires it
to equal the witness's and to agree with the `sent` state the placement's
ending gives that notice: `not_sent`, `unknown`, `sent` and `sent` in the
table's order. A recorded reminder is spent whichever timing occurs: the next
placement gets no second one.

Three rehearsal controls have the fake provider hold the request until the
signal has been sent, which makes `written_unanswered` certain. The fourth,
`reminder-spent-unheld`, is signalled on sight like a live placement. In twelve
native runs of that control all four timings occurred. Native timing says
nothing about Linux or a real provider.

Size the allowances for the charged case. [INTERFACE 6.4](../../docs/INTERFACE.md#64-limits-reminder-and-notice)
charges a request aborted after any byte was written one estimated turn,
ceil(body bytes / 3) input tokens and its whole `max_tokens`, which is the
lesser of 16,000 and the remaining output allowance. The audit's output
allowance must therefore cover what is used before the point, that estimate of
up to 16,000 and at least 1,024 more, or the continuation ends `limit_reached`
before any request. `propose` and `propose-continuation` print these figures
for the most favourable case, and the container records them in its
credential-free preflight. They are stated, never enforced: the commission
decides.

### Prepare and approve

```sh
python3 -I -B apparatus/c10/c10.py propose-continuation \
  "$PWD/.scratch/c10-live-NN" --max-placements 2 \
  --output "$PWD/.scratch/continuation-proposal.json"
python3 -I -B apparatus/c10/c10.py packet \
  "$PWD/.scratch/continuation-proposal.json" "$PWD/.scratch/continuation-packet.json" \
  --qualification QUALIFICATION_ID
sha256sum .scratch/continuation-packet.json
```

`propose-continuation` takes the evidence folder of the audit's original launch
and runs nothing in the container. It reads the retained launch records and the
audit's latest export, which must be a checked observation; collect and review
first if a later collection was withheld. From that export's own log it takes
the audit reference, the number of recorded placements, the last ending and
cause, the newest log record's digest and the cumulative usage the limits count.
The proposal names the next placement, keeps the retained commission's model,
limits and watchdog, and leaves spending authority, account and bindings null.
`--audit` selects one of several retained audits. `--max-placements` states the
ceiling of the new commission when the original packet allowed one placement; an
interrupted study keeps its own ceiling. `--interrupt-after reminder_notice`
interrupts this placement too. `--stop-after-seconds` sets its watchdog.

`packet` binds the proposal to the committed apparatus and requires the selected
qualification's writer and image to be the ones the retained launch recorded.
The apparatus may be newer than the one that launched the audit; the writer may
not differ. Fill `account` and `spending_authority` as for any live packet,
with the `credential_label` of the original placement's key.

### Rehearse and run

A live continuation needs a retained Linux [rehearsal](#run-the-offline-checks)
made by the same committed apparatus, with all eight continuation controls
passed. When the audit came from a study template or a study build, the
rehearsal must include that template and build, as its first launch did. With
`--connection`, the rehearsal must have used a saved synthetic connection too.

```sh
python3 -I -B apparatus/c10/c10.py continue live \
  "$PWD/.scratch/c10-live-NN" "$PWD/.scratch/c10-continue-NN" \
  --packet "$PWD/.scratch/continuation-packet.json" --approved-packet APPROVED_SHA256 \
  --rehearsal "$PWD/.scratch/c10-launch-NN" --qualification QUALIFICATION_ID \
  --connection stewart-haiku
```

The first folder is the original launch's evidence; the host writes nothing
there. The second is a new folder directly under `.scratch`, named with
lowercase letters, digits and hyphens, for this placement's host records.
Before the container or any credential is touched the launcher refuses, with
its reason, when: the packet is invalid or differs from the approved digest; it
names another evidence folder, container, audit or reference; the retained
launch record is incomplete or belongs to the other mode; the model, limits or
an interrupted study's ceiling differ from the retained commission; an earlier
attempt of the placement started or may have started; the prior state differs
from the latest export; the apparatus is uncommitted or the packet's bindings differ; the
writer or image differs from the retained launch; or the rehearsal is missing,
incomplete or made by another apparatus. A packet may leave the prior log
digest and usage null; the launcher then records what the export shows.

It then records each command's argv, streams and exit while it:

1. confirms the container holds the audit;
2. delivers a Git archive of the committed apparatus over the command's input
   into `/work/code-` plus the first 12 hex digits of the archive's digest. The
   launch-time `/work/code` is never changed. An existing directory is accepted
   only when its members and bytes equal the archive, and refused otherwise;
3. delivers the exact packet the same way to a directory of its own;
4. opens the same credential-free TCP connection as a first launch;
5. starts the placement and waits up to 300 seconds for its preflight record.
   Inside the container the preflight rechecks the writer, source, reference,
   commission and a fresh status against the packet before anything is created
   in the audit. If the process ends or the deadline passes first, or the
   record names another audit, placement or attempt, no credential is read or
   sent;
6. reads the bound key from the launcher keyring, checks the staged inputs
   and sends it on the placement's input only after a clean scan. The container compares it with the original
   placement's private marker before any start; a different key starts nothing;
7. inspects the container and scans both the new record folder and the original
   evidence folder for the key, since the placement's records and the next
   `export-NNNN` reach the original folder through the container's existing
   mount.

`host/RESULT.json` (`stewart.c10-continuation-launch/2`) records the prior state
found, the attempt number, the delivered code directory and the container's own
result by path and digest. Exit zero means the placement was observed and
nothing failed; like a first launch, it does not mean the auditor submitted.
Nothing is retried.

The container keeps each attempt of a placement in its own directory,
`continuations/AUDIT-pN/attempt-K/` under the original evidence folder's
`container/`, numbered from 1 and created exclusively before anything else. Its
preflight record names the attempt, and its `RESULT.json` states whether a model
process was started. A placement that started, or whose start is uncertain, is
never attempted again. An attempt's result says `not_started` only on proof that
the run command never became a process: the attempt stopped at its preflight, on
a missing or invalid credential or on a key that differs from the original
placement's, or the one command record it wrote says the spawn itself failed.
From the moment a start is possible the result says `unknown` until the
placement has been observed. Only `not_started` attempts may be followed by
another. The launcher and the container both apply this to every earlier
attempt: a missing or unreadable result, a failure record alone, `unknown` or
any other state refuses for good, and the audit is then reconciled from its
retained records and status. Independently of these folders, the container's
preflight compares the service's own count of placements with the packet's
prior state, so a placement the service has recorded cannot be started twice.

A host launch therefore ends in one of three ways besides success. A refusal
before the container is touched creates no record folder. `not_started` names
the stage at which the container stopped, for example a denied keyring lookup
or a mistyped key; it exits nonzero, and a further attempt is a new launch with
a new record folder and the same approved packet. `failed` is incomplete at a
named host step: the container reported a start, an uncertain start or nothing
readable, or the host's own observation did not complete. Whether another
attempt is then possible is decided only by the container's records, at the
next launch.

Afterwards use `control` with the new record folder. It names the delivered
code directory, so status, inspection, close and collection use source that
understands every placement; collection scans both folders. `review` and
`report` read the original evidence folder, where every snapshot lives.

### Limits that remain

- Abrupt process death is unsupported. A placement whose process died has no
  recorded ending; its audit's export is withheld, and once Stewart has
  reconciled it as `process_gone` the review stays incomplete with that
  placement unassessed. This apparatus proposes no continuation for it.
- A placement that sends no request, for example one that starts with an
  exhausted allowance and ends `limit_reached` at once, withholds its export.
- An export needs every placement's records complete. A response body that was
  cut off is accepted when its attempt record binds its exact size and digest
  and the attempt did not use it as a response; every other incompleteness,
  and any size or digest difference, still withholds.
- Live provider captures are Stewart-owned. Only rehearsal has an independent
  provider witness, including for the request a signal interrupts.
- A continuation needs the original named container running with its private
  volume mounted at `/work`. Keep the writer, volume, and frozen apparatus
  through custody review.
- Compaction review uses the same capture reconstruction in every placement.
  Real-provider coverage requires a real summary and later ordinary work;
  the synthetic rehearsal alone supplies neither observation.
- The rehearsal interrupts synthetic scripts at the same witnessed points. A
  study template runs there once, as an ordinary submitted audit, and gets the
  template-tampering reviewer controls on that one placement. A continued audit
  gets the continued-audit controls instead, so no rehearsal applies the
  template controls to a study audit that has several placements.
- `smoke.py --interruption POINT` with exactly one `--submission` rehearses a
  lone interrupted study and its continuation natively, and puts a wrong key,
  a repeated attempt and a second start around each continuation. It is local
  iteration: lacking the fixed inventory and Linux, it admits no live launch.
  The Linux rehearsal continues each control once and does not replay the
  wrong-key sequence.

## Operate retained audits

`host/operator.json` lists every audit, its retained container and the code
directory its operator commands run. A continuation's record folder has its own,
naming the source delivered for it; use the latest such folder for an audit
that has been continued. All four commands below avoid model calls. `close` ends authoring; use it only when that
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
Current consumers require `stewart.reply/3`; historical reports are retained
without conversion. Unknown
conditions remain unknown, with the raw reply retained privately. `inspect`
verifies package bytes and identifies the answer to read privately; it does not
judge its contents. If close requires confirmation, inspect the return, then
issue `close --confirm TOKEN` explicitly. There is no automatic loss surrender.

`collect` reads the original credential from the packet’s bound keyring label. A private HMAC check refuses a different key without storing the key
itself. It observes the writer stopped under the operator lock, repeats the
evidence-membership and credential checks, and creates `export-0002`, then
`export-0003`, and so on. It never changes an earlier snapshot. Uncertain or
credential-bearing evidence stays private; do not bypass withholding by copying
the container wholesale. Status and later custody actions do not resume a model.
Collection through a continuation's record folder writes its scan of that
folder and of the original evidence folder, where the new snapshot lands.

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
response invariance checks that the indexer imposes no one-MiB cutoff; it is not
a full-history scale test.

The reviewer reconstructs raw ordinary and summary requests, checks the top-level
trigger separately from iteration charges, retains the signed content array
byte for byte and replaces active context after a successful summary. It rejects
summary tool execution and checks decoded unsuccessful summary endings. A cut-off
or undecodable provider response remains outside its decoded-response checks.
It reconciles request attempts and
reported/estimated usage, checks the pinned arrangement and output caps, links
tool effects to accepted edits, validates mechanical citations against witnessed
inputs, and derives prepared/selected answer bytes and exact delivered membership
from the edit history. Version 3 reviews cover every recorded placement in
order and distinguish completed procedural checks (`checked`) from `incomplete`
evidence. Submission, actor, delivery and closure
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
Compaction coverage counts summary requests, successful and failed decoded
summaries, subsequent context resets and completed re-entry inspections after
a reset. A successful summary at the last allowed request can have no reset or
later re-entry; the counts expose that unexercised path. A run with no summary
explicitly leaves compaction unassessed. Synthetic exchanges remain labeled as
insufficient to establish real-provider compaction.

The version 2 session records distinguish placement observation, lost caller
reply, pre-close review, automatic close and export. The host retains its own
operations and a digest reference to the session. A successfully observed live
policy stop can exit zero while reporting unstarted work. A failed operation or
incomplete observation remains nonzero. Export reasons distinguish incomplete
evidence, credential matches, scan uncertainty and archive-write failure. Host
failures name their step and retain controlled exception classifications; private
exception text is not printed. Historical receipts retain their original schemas.

Provider usage is not independently observed billing. Cost assessment, billing
reconciliation, independent observation of live authoring, a killed process and
its reconciliation, and real signed-summary compaction need their own evidence
and explicit disposition.
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
