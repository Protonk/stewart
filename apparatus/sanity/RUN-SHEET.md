# First Messages API sanity commission

This packet tests one small commission through intake, the model loop, recorded
work, submission, delivery and close. The specimen is
[submission/question.md](submission/question.md) and its two captured materials.
Its meaning is open inquiry; no finding, tie-breaking recommendation or answer
section is mandatory. It asks for an explanation of the code, not execution.

## What is ready and what remains

The specimen and offline rehearsal are prepared. A real launch still needs the
API-key handling review, its implementation and canary audit; an exact model;
current provider compatibility/pricing checks; and the principal's bounded
spending and continuation authority. The model/destination placeholders prevent
commissioning this template unchanged. The 8-turn, 80,000-input, 6,000-output
limits are rehearsal settings, not an approved paid budget. Effort is omitted.

No command in the rehearsal can select a real provider. The synthetic model
name is `rehearsal-only`; the fake binds a newly allocated loopback port. The
container has `--network none`. Host credentials and proxy settings are not
forwarded. All model usage in its report is synthetic.

## Rehearse on the host

Commit the packet before running: the wrapper archives `HEAD`, refuses a dirty
packet and checks the binary digest against `acceptance-03` in the qualification
record. It uses the already cached pinned Python image, with no image pull or
build, and the qualified arm64 release binary. Apple `container` 1.6.1 and its
services must be available in the host shell.

```sh
python3 -I -B apparatus/sanity/rehearse.py "$PWD/.scratch/sanity-rehearsal-01"
```

Use a fresh absolute directory directly under `.scratch` for every attempt.
The wrapper retains its named container, source archive, binary/source identity,
host outputs and inspection. Inside it, an unprivileged process keeps the audit
on the Linux filesystem. On completion, the wrapper exports an independent
evidence directory and the entire working tree as `container/work.tar`, with
digest, listing and observation times. Failed runs keep the same evidence and
container; nothing is automatically removed or retried.

The three scenarios use separate references and working directories:

| Scenario | Expected observation before close | Expected preservation |
| --- | --- | --- |
| Scripted submission | Reads both materials, records a cited account and observation, prepares, confirms submission; auditor seal and verified delivery | Ordinary close completes; return agrees with the sealed manifest |
| Ordinary ending without submission | Records work, ends twice with Stewart's reminder between; `ended_unsubmitted`, no auditor seal | After observing that state, manager close preserves the work; verification precedes confirmation and the seal remains attributed to the manager |
| Synthetic HTTP 401 | One rejected request; `interrupted` / `provider_rejected`, no auditor seal | Rejection and raw response retained; no continuation; manager close remains distinct from submission |

The scripted answer deliberately has no `record_limit` entry. A missing-section
notice must not prevent submission. The fake reacts to actual read replies and
preparation handles; its prose is authored fixture text, not a model result.
It validates returned bytes against independent copies, not intellectual quality.

A separate altered copy of the submitted return must fail manifest verification;
the original must still verify afterward. Both copies remain available. The
unsubmitted and rejected scenarios check that successful preservation/close is
not mistaken for successful auditor submission. This rehearsal supplements
procedure preparation; it does not replace the independent acceptance driver,
prove real-provider compatibility, or qualify a model.

## Procedure for the later paid run

1. **Freeze the launch packet.** Copy this specimen into a new retained run.
   Fill the exact approved model, destination and cumulative limits; preserve
   the original inputs independently. Record the qualified binary's digest,
   source identity, container image, filesystem, approved endpoint/proxy choice,
   operator, spending authority and stopping conditions. Keep credentials out
   of these records. The credential-entry mechanism remains to be decided.
2. **Intake without credentials.** Run `new`, `prepare`, then `commission REF
   HANDLE --i-am-finished`. Save JSON stdout, stderr, exit status and timestamps
   for each command. Read the arrangement. Run `receipt --verify` and byte-compare
   `receipt --read` for the question and both materials against the independent
   input copies. Save `status`. These operations consume no model tokens.
3. **Launch once.** Only after the bounded commission is approved and key
   handling is audited, run that same executable's `run REF --json` under the
   approved credential mechanism. Retain the run process identity and provide
   a separate `status REF --json` and `close REF --json` command. Close ends
   authoring and may seal unfinished work as manager. Stewart's existing
   retries (up to four attempts per request) belong in the allowance decision;
   no wrapper repeats a placement or selects another model on failure.
4. **Observe before deciding.** Preserve the run reply, status, actual reported
   and estimated usage, request/response and tool captures, and available billing
   records. Check whether material reading, cited recording, preparation and
   confirmed submission actually occurred. Inspect `ending`, seal actor and
   delivery independently; exit 0 alone does not establish submission. These
   observations are this test's scope, not new service submission rules.
5. **Inspect delivery and close.** Check the return's membership and hashes
   against the sealed manifest, whose digest must match the recorded seal.
   Read the answer. After an auditor submission with verified delivery, ordinary
   close completes. If the run did not submit or delivery failed, preserve that
   state and decide recovery before taking further action. A manager seal is
   preserved work, not a successful auditor submission. Confirm a newly delivered
   manager-sealed copy only after inspecting it. Never surrender a loss silently.
6. **Retain the result.** Export the whole archive, original input copies,
   command records and delivered bytes, with export times and digests. Keep
   the original container through review. Record outcome and limitations before
   considering a new attempt. No automatic cleanup or continuation.

## Review the specimen's intellectual content separately

Reading the code establishes that the maximum timestamp wins for each sensor,
and that the first encountered reading wins among equal maximum timestamps.
Empty input yields an empty dictionary. Returned values are the original reading
objects. The notes do not settle the desired display policy for equal timestamps
or supply execution evidence. These observations are for the manager's inspection;
this run sheet and the fake's authored answer are not commissioned materials.

The first paid result may reveal other relevant qualifications. Its phrasing,
coverage and usefulness can inform later work without changing the procedural
outcome. Haiku framing comparisons, long-context compaction, forced interruption
and additional question families belong to separate commissions.
