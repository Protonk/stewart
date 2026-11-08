# Retained sanity sessions

The launcher runs the sensor-reading specimen through a qualified native Linux
binary. It requires Apple `container` 1.6.1 and the cached Python image named by
the selected acceptance record. The binary must have passed the four independent
credential cases; older qualification without those cases is refused.

The host retains one named 512 MiB container per invocation. It stays running
after the session so status and close remain available. Failed launches retain
the same container and records. Nothing automatically repeats a placement,
continues an interrupted audit, removes a container, or deletes evidence.

## Offline rehearsal

Commit the apparatus before running. Choose a new absolute directory directly
under `.scratch` and the qualification ID for the exact binary to exercise:

```sh
python3 -I -B apparatus/sanity/launch.py rehearse \
    "$PWD/.scratch/sanity-launch-NN" --qualification ACCEPTANCE-ID
python3 -I -B apparatus/sanity/review.py "$PWD/.scratch/sanity-launch-NN"
```

The container has no network. The host generates a nonfunctional canary and
sends it through the same stdin/descriptor route used later for live entry.
Scenarios cover auditor submission, ending without submission, provider
rejection, interruption, reflected credentials, contaminated export and failed
export. The last three deliberately retain private originals. An altered copy
of a submitted return must fail verification while the original still verifies.

While a fake request is held, independent process observers under UID 1000 and
UID 1001 inspect the UID 1000 Stewart process. Each observer first proves it can
inspect its own deliberately readable control. The check requires actual access
denials, a live target and disabled core limits, rather than accepting a vanished
process as protected. Its scope is recorded procfs access; it does not establish
protection from the administrator or erasure of process memory.

The original canary and actual received authentication values stay in the
root-owned `/work/credential-witness` directory, outside every audit and export
under test. Reports contain counts, hashes and observation times. Keep this
independent witness and the original containers through review. Live mode never
writes this credential witness.

## Prepare a commission without provider use

The [machine proposal](commission-proposal.json) carries the settings discussed
in [the commission proposal](COMMISSION.md). `packet.py` binds that unapproved
JSON proposal to the qualification ID, exact
binary digest, committed apparatus source and specimen digest. It does not
launch a container or contact a provider:

```sh
python3 -I -B apparatus/sanity/packet.py apparatus/sanity/commission-proposal.json \
    /absolute/private-directory/commission.json --qualification ACCEPTANCE-ID
```

The proposal uses `stewart.sanity-commission/1`. Its fields are the model, optional
effort, cumulative limits, direct endpoint, omitted proxy, one placement, four
built-in request attempts, no automatic continuation, wall-clock stopping rule,
account labels, source/binary bindings and spending authority. An unapproved
proposal leaves the account, bindings and spending-authority values null.
Preparation fills only the bindings. It does not create spending authority.

Before a paid run, the principal supplies the actual non-secret account,
workspace and credential labels and authorizes the bounded commission. Record
that authorization in `spending_authority` and hash the final exact file. A
changed model, bounds, binary, source or specimen requires a new reviewed packet.
The source binding is the `HEAD` commit, so bind the packet after the last
commit before launch; committing anything afterwards, including the
qualification record, means a new packet and a fresh approval digest.
Packet text, including the credential label, must never quote a credential
value, not even a deliberately invalid one for a rejection test: the packet is
copied into the evidence folder, and the host scan then reports the launch as
failed.
See [the run sheet](RUN-SHEET.md) for the decisions and review sequence.

## Live launch, only after spending authorization

Run from a real terminal that supports hidden input:

```sh
python3 -I -B apparatus/sanity/launch.py live \
    "$PWD/.scratch/sanity-live-NN" --qualification ACCEPTANCE-ID \
    --commission /absolute/private-directory/commission.json \
    --approved-commission APPROVED-FILE-SHA256
```

The launcher checks the exact packet and binary before starting. Inside the
container it commissions and verifies the question and material readback before
writing `READY.json`. Only then does the host request the credential with
Python's standard hidden-input component. If terminal echo cannot be disabled,
entry fails. The key travels through container stdin and a one-use inherited
descriptor into Stewart. It is never a command argument, environment value,
container setting, mount or credential-input file. Host and container processes
use minimal environments and no ambient provider/proxy selection.

The host, container administrator, Python runtimes and authenticated provider
are trusted. Ordinary Python objects and pipe/runtime buffers can hold copies;
this procedure makes no claim of complete memory erasure. Core dumps are disabled.
The paid path uses the direct Anthropic endpoint; adding a proxy or a different
route needs an explicitly changed launcher and reviewed commission.

`host/operator.json` gives exact `container exec` commands for status and close.
The operator tool requires `stewart.reply/2`, prints an allowlisted state
summary including authoring, seal observations and unknown usage with known
limits, and retains the full reply
privately. `inspect` verifies a delivered package against its recorded seal and
gives the private answer location and any confirmation token. Read that answer
before explicitly invoking `close --confirm TOKEN`. No confirmation or loss
surrender is automatic. An abnormal run remains open for review; only auditor
submission with verified delivery takes the ordinary automatic-close path.

The watchdog sends SIGTERM at the packet's wall-clock limit, then waits ten
seconds before SIGKILL if the process remains live. A lost host reply is reported
as uncertain; consult the retained container before acting again.

## Evidence and export

Raw command streams, archives, requests, responses and fake-provider witnesses
stay in `/work/private`. Export requires a stopped-process observation, complete
run/request/attempt/response membership, valid clean reflection markers, exact
response hashes and a byte scan for the selected credential and ASCII JSON
escapes. Missing evidence, an unreadable member, a reflection marker, an orphaned
capture, a special file or a matching byte sequence withholds export. Ordinary
diagnostic bytes are preserved. No original record is sanitized or rewritten.

The apparatus serializes its own operator commands and export. It does not
provide an atomic filesystem snapshot or protection against the owner changing
files with other tools. The scanner does not establish secrecy in memory or
recognize every possible encoding. In rehearsal, the deliberate export-failure
control creates a directory at the exclusive output filename; the actual open
fails and the obstruction and originals remain.

Clean scenarios receive `work.tar`, its size/digest and an `EXPORT.json` record.
Withheld scenarios export only safe observation metadata. Host argv, inspection
records and exported files receive a separate credential scan. Contaminated
private records remain withheld for manual review; never export a retained
container wholesale as a shortcut.

`review.py` verifies exported archive digests and reads members directly without
extracting or changing them. `--json` adds a source-linked index of manager
commands, provider attempts and auditor tool results. It reports submission,
delivery, close and usage separately. A live session reports an observed outcome
requiring review; it never calls a model qualified or grades the answer.

Local helper checks, which consume no model tokens:

```sh
python3 -I -B apparatus/sanity/test_launch.py
```

Container qualification and a synthetic credential rehearsal must exercise the
chosen executable and committed launch code before real-key use. The
[qualification record](../qualified.md) identifies retained demonstrations;
local helper checks alone do not qualify the Linux path.
