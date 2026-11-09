# Messages API sanity procedure

This packet tests one small commission through intake, the model loop, recorded
work, submission, delivery and close. The specimen is
[submission/question.md](submission/question.md) and its two captured materials.
Its meaning is open inquiry; no finding, tie-breaking recommendation or answer
section is mandatory. It asks for an explanation of the code, not execution.

## Commission settings

The model/destination placeholders prevent commissioning the template unchanged.
The 8-turn, 80,000-input, 6,000-output limits are rehearsal settings, not an
approved paid budget. Effort is omitted. A live commission must name the model,
credential mechanism, provider route, allowances, spending authority and stopping
conditions; the procedure below records those choices.

The [example proposal](commission-proposal.json) is an unapproved starting point.
Check the selected model's current compatibility and pricing, and obtain bounded
spending authorization before launch. The launcher applies the approved settings
to a retained copy of the specimen.

No command in the rehearsal can select a real provider. The synthetic model
name is `rehearsal-only`; the fake binds a newly allocated loopback port. The
container has `--network none`. Host credentials and proxy settings are not
forwarded. All model usage in its report is synthetic.

## Rehearse on the host

The final credential and launch path is exercised with:

```sh
python3 -I -B apparatus/sanity/launch.py rehearse "$PWD/.scratch/sanity-launch-NN" --qualification ACCEPTANCE_ID
```

Use a fresh evidence folder and the qualification ID for the executable being
tested. Commit the apparatus first. This command uses a synthetic credential and
an offline Linux container. It retains the container and prints the location of
operator status/close commands and results. The launcher checks the credential
path, process-observer controls, interruptions, exact delivery, and withheld or
failed exports. Its review tool reads retained results without launching a model.

The [launcher guide](LAUNCHER.md) describes credential entry, operator commands,
export checks and offline review. Use it for the exact launch and review commands.
Each scenario has its own reference and working directory:

| Scenario | Required observation |
| --- | --- |
| Scripted submission | Both materials read; cited answer explicitly submitted, delivery verified and ordinary close complete. Same-user and different-user process controls fire, protected reads are denied. |
| Ending without submission | `ended_unsubmitted`; recorded work remains open for review. |
| Synthetic HTTP 401 | One rejected request; `interrupted` / `provider_rejected`; no continuation. |
| Interrupted request | Signal stops the placement; reported and estimated usage and partial request evidence remain available. |
| Reflected credential | The exact private capture is marked; further requests and tools stop; export is withheld. |
| Contaminated export | An independent scan detects the deliberate contamination and withholds export. |
| Failed export | A real output-file obstruction prevents the export; originals and obstruction remain retained. |

The scripted answer deliberately has no `record_limit` entry. A missing-section
notice must not prevent submission. The fake reacts to actual read replies and
preparation handles; its prose is authored fixture text, not a model result.
It validates returned bytes against independent copies, not intellectual quality.

An altered copy of the submitted return must fail manifest verification while
the original still verifies. Neither an unsubmitted ending nor a manager close
can establish auditor submission. Rehearsal supplements the independent
acceptance driver; it does not establish real-provider compatibility or qualify
a model.

## Procedure for the later paid run

The credential entry path uses a hidden terminal prompt on the host and a pipe
to a one-use inherited descriptor selected with `run --key-fd` in the Linux
container. It uses no persistent credential store. Intake and receipt
verification finish before the prompt. The launch environment selects the direct
provider endpoint explicitly and excludes ambient
credentials and proxies. The user enters the key locally, never into chat or an
argument. Retain the qualified executable until this audit is closed.

1. **Freeze the launch packet.** Copy this specimen into a new retained run.
   Fill the exact approved model, destination and cumulative limits; preserve
   the original inputs independently. Record the qualified binary's digest,
   source identity, container image, filesystem, approved endpoint/proxy choice,
   operator, spending authority and stopping conditions. Keep credentials out
   of these records. Bind launch approval to the exact completed packet.
2. **Intake without credentials.** Run `new`, `prepare`, then `commission REF
   HANDLE --i-am-finished`. Save JSON stdout, stderr, exit status and timestamps
   for each command. Read the arrangement. Run `receipt --verify` and byte-compare
   `receipt --read` for the question and both materials against the independent
   input copies. Save `status`. These operations consume no model tokens.
3. **Launch once.** Before launching, check that a fresh container with the
   same image and `--network default` can open a TCP connection to the
   provider endpoint; the container's egress follows the host, and an active
   host VPN blocked it in the first attempt, which spent four connection
   timeouts and nothing else. Run that same executable's `run REF --json` under
   the commissioned bounds and credential mechanism. Retain the run process identity
   and provide a separate `status REF --json` and `close REF --json` command. Close ends
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
6. **Retain the result.** The launcher exports the archive, original input
   copies, command records and delivered bytes only after its evidence and
   credential checks pass. It records export times and digests. A withheld or
   failed export leaves the originals private in the retained container. Keep
   that container through review, and record outcome and limitations before
   considering another attempt. Nothing automatically cleans up or continues.

If a response reflects the credential, preserve the exact original privately,
stop and revoke the key. Ordinary diagnostics explicitly redact provider text;
the attempt's `credential_reflection` records the affected body/header surfaces.
The launcher withholds exports when any reflection marker, independent scan match
or uncertainty prevents establishing a clean export. Only safe operational
metadata leaves that container. A withheld export is an incomplete preparation
or test outcome to review, not evidence that the archive vanished or was empty.

## Review the specimen's intellectual content separately

Reading the code establishes that the maximum timestamp wins for each sensor,
and that the first encountered reading wins among equal maximum timestamps.
Empty input yields an empty dictionary. Returned values are the original reading
objects. The notes do not settle the desired display policy for equal timestamps
or supply execution evidence. These observations are for the manager's inspection;
this run sheet and the fake's authored answer are not commissioned materials.

Assess the answer's phrasing, coverage and usefulness separately from whether
submission, delivery and close succeeded.
