# Commissioning an audit with files only

Ana wants to know whether the reminder service has bugs. She has an
implementation, the requirements and a supplied report. This walkthrough
follows her audit from an empty folder to a closed audit. The
[README](README.md) explains the paths, the placeholders and the stand-in
provider behind the outputs.

## 1. Create the reference

```text
$ stewart new /home/ana/reminders --archive /home/ana/stewart-archive
stewart new: completed
Effects: reference created

reference: REF
archive: /home/ana/stewart-archive
archive created: true
folder: /home/ana/reminders
scaffold created: true
writer:
  path: /usr/local/bin/stewart
  sha256: …
notices: none

Next:
  /usr/local/bin/stewart prepare REF
      Edit question.md and materials/, finish, then prepare. Leave the folder unchanged from prepare until commission returns.
```

`new` creates the folder with a scaffold `question.md` and an empty
`materials/`, and prints the reference that every later command takes. The
reference names the audit, its store and its archive, so it works from any
directory. The writer is this binary: only it can change the audit later.

## 2. Write the question and materials

From the repository root, Ana copies the worked example's question and
materials over the scaffold:

```text
$ cp examples/questions/open/submission/question.md /home/ana/reminders/question.md
$ cp -R examples/questions/open/submission/materials/. /home/ana/reminders/materials/
```

and edits one front matter line so that it names her return destination:

```text
destination: /home/ana/returns
```

The front matter names the family (`open-inquiry`), the model used for every
run, the destination and the cumulative limits. `material-roles` declares what
each file is for. The declarations are advisory: a missing role is reported as
a suggestion and never blocks commissioning. The body below the front matter is
her question, word for word: "Audit our app to make sure there are no bugs."
`stewart help forms` describes each family.

## 3. Prepare

```text
$ stewart prepare REF
stewart prepare: refused (destination_invalid)
The destination /home/ana/returns does not exist; it must be an existing directory in which Stewart creates the return package.
Effects: preparation none, diagnostic durable
Retained:
  /home/ana/stewart-archive/audits/…/diag/1.json

destination: /home/ana/returns

Next:
  /usr/local/bin/stewart prepare REF
      Correct the folder, finish editing, then prepare again.
  /usr/local/bin/stewart close REF
      End this reference without commissioning.
```

A refusal states its reason, what it changed and what to do next. Nothing was
prepared; the diagnostic stays in the archive. Ana creates the directory and
prepares again:

```text
$ mkdir /home/ana/returns
$ stewart prepare REF
stewart prepare: completed
Effects: preparation recorded

prepared: HANDLE
question:
  file bytes: …
  file sha256: …
  body bytes: 46
  body sha256: 96bb1920cba63505a4e03c579c4ccceb74f95893df57eef775e0b6b5ec21d36e
guidance: none
settings:
  family: open-inquiry
  model: claude-opus-5-5
  destination: /home/ana/returns
  limits:
    turns: 200
    input tokens: 20000000
    output tokens: 400000
  inquiry: reminder-restarts
materials:
  count: 3
  bytes: 1428
  directories: materials
  files:
    -
      name: materials/a.py
      size: 175
      sha256: 3fed093a5696428b7440ae3a0f93d2bd3bc93084b495fc3ec6297ab78c23afce
      lines: 5
    -
      name: materials/requirements.txt
      size: 662
      sha256: 3c8aa8422012374ddd204acebf0ef45a78fa49cf8fb129c0a3faa104329edb98
      lines: 10
    -
      name: materials/supplied-report.txt
      size: 591
      sha256: 86b5be5c14dad39f2facfb70607658bdc637f2df5a678e78e70972c459b9296d
      lines: 8
…
arrangement:
  sha256: …
  readable: /home/ana/stewart-archive/audits/…/prep/1/arrangement.md
  machine: /home/ana/stewart-archive/audits/…/prep/1/arrangement.json
defects: none

Next:
  /usr/local/bin/stewart commission REF HANDLE --i-am-finished
      Accept exactly this selection. Leave the folder unchanged until commission returns.
```

`prepare` hashes exactly what is in the folder and pins the arrangement: the
instructions, tools and limits the auditor will work under. The readable
arrangement shows them before anything is accepted. Preparing accepts nothing.
From here until `commission` returns, Ana leaves the folder unchanged; after
any edit she prepares again.

## 4. Commission

```text
$ stewart commission REF HANDLE --i-am-finished
stewart commission: completed
Effects: acceptance accepted, attempt recorded

reference: REF
accepted at: …
receipt sha256: …
already accepted: false
checks: capture_digests_match_preparation source_identity_unchanged_during_copy final_scan_matches_preparation
declaration:
  i am finished: true
materials:
  count: 3
  bytes: 1428
run line: /usr/local/bin/stewart run REF
run needs:
  - provider credential through --key-fd or ANTHROPIC_API_KEY
  - network access to the provider
  - runs in the foreground until the placement ends; callers with command timeouts should start it in the background
receipt line: /usr/local/bin/stewart receipt REF

Next:
  /usr/local/bin/stewart run REF
      Start the audit; it needs what run_needs lists.
  /usr/local/bin/stewart close REF
      End the commission without running it.
```

`--i-am-finished` is Ana's declaration that the submission is complete.
Commission copies exactly the prepared selection into the archive, checks that
it still matches and records the acceptance. This is the boundary: after it,
the commission is fixed, and Ana's folder can change without affecting it.
Commission needs no credential or network. The run line works for whoever
holds it, from any directory.

## 5. Recover the commission

```text
$ stewart receipt REF
stewart receipt: completed
Effects: none (read-only)

reference: REF
accepted at: …
prepared: HANDLE
receipt sha256: …
…
```

The receipt shows the accepted commission from the archive's own copies, item
by item; `stewart receipt REF --read ITEM` prints an item's exact bytes. It
does not need the original folder.

## 6. Run

`run` needs the provider credential, here in `ANTHROPIC_API_KEY`. It runs in
the foreground until the placement ends. The auditor works only through its
tools over the accepted materials, records entries, prepares an answer and
submits it. The commission's limits bound every run of the audit together.

```text
$ stewart run REF
Command stewart run: completed
Commission: accepted.
Run 1 was interrupted (provider_unavailable).
The provider was unavailable on attempt 4 of request 1 (status 529); the run may be continued.
Answer: revision 0, 0 recorded entries, unsealed.
Delivery: no attempt is recorded.
Audit: open.
Cumulative usage / limits: turns 0/200 (reported 0; estimated 0), input_tokens 0/20000000 (reported 0; estimated 0), output_tokens 0/400000 (reported 0; estimated 0).
Run 1 was interrupted; the answer is not submitted. Run continues it under the same cumulative limits, or close ends authoring.
Effects: run ended, answer unchanged, seal none, delivery none

Qualifications and exact references:
  provider:
    status: 529
    error type: overloaded_error
    error message: Overloaded
    request id: …
    request: 1
    attempt: 4

Next:
  /usr/local/bin/stewart run REF
      Continue the audit in a new conversation under the same cumulative limits.
  /usr/local/bin/stewart close REF
      Close the audit; it seals the recorded selection with manager attribution.
```

The provider was overloaded, so the run ended interrupted and exited 5.
Nothing was lost. The audit is its own ledger: running it again starts a new
conversation that carries a continuation notice, keeps every entry recorded so
far and counts usage against the same cumulative limits. The same holds when a
run's process dies: `status` then reports the run interrupted from the
evidence it finds, and `run` continues it. The auditor's one procedural
reminder to submit is spent once per audit, so a continued run may end
authoring at its first unsubmitted turn.

```text
$ stewart run REF
Command stewart run: completed
Commission: accepted.
Run 2 ended after auditor submission.
The auditor submitted its answer and the seal was recorded; the run's delivery ended verified.
Answer: revision 3 sealed by the auditor.
Delivery: attempt 1 is verified at /home/ana/returns/stewart-return-…-001.
Audit: open.
Ordinary close can settle placement of the already-delivered copy; no confirmation token is required for that path.
Cumulative usage / limits: turns 4/200 (reported 4; estimated 0), input_tokens 12000/20000000 (reported 12000; estimated 0), output_tokens 1600/400000 (reported 1600; estimated 0).
Effects: run ended, answer changed, seal recorded, delivery verified


Next:
  /usr/local/bin/stewart close REF
      Close the audit. An ordinary close confirms where the delivered copy is.
```

## 7. Status

```text
$ stewart status REF
Command stewart status: completed
Commission: accepted.
Run 2 ended after auditor submission.
The auditor submitted its answer and the seal was recorded; the run's delivery ended verified.
Answer: revision 3 sealed by the auditor.
Delivery: attempt 1 is verified at /home/ana/returns/stewart-return-…-001.
Audit: open.
…
Next:
  /usr/local/bin/stewart close REF
      Close the audit. An ordinary close confirms where the delivered copy is.
```

Status keeps separate facts apart. They are not stages of one progress bar:

| Fact | Here | What it means |
| --- | --- | --- |
| The answer's content | Entries the auditor recorded | What the auditor says, including that the evidence is inadequate. Stewart grades none of it. |
| Authoring ended | By the auditor's submission | No further entries can be recorded. A limit, an unsubmitted ending or close can also end it. |
| Seal | Present, by the auditor | The exact answer is fixed, with who sealed it. A close before submission seals with manager attribution instead. |
| Delivery verified | Attempt 1 | The package was written and read back member by member. |
| Closed | Not yet | Custody is settled. Only close does that. |

An agent manager reads the same facts from `stewart status REF --json`. Its
`data.headline` here is:

```json
{"accepted": "yes", "launched": "yes",
 "authoring": {"state": "ended", "ended_by": "seal"},
 "seal": {"state": "present", "actor": "auditor"},
 "delivered": {"verified": true, "confirmed": false,
               "location": "/home/ana/returns/stewart-return-…-001"},
 "closed": "no"}
```

## 8. The return

The return package holds the return manifest, Ana's accepted question body
as `question.md`, the structured answer `answer.json` and its rendering
`answer.md`:

```text
/home/ana/returns/stewart-return-…-001/
  answer.json     1728 bytes
  answer.md        988 bytes
  manifest.json
  question.md       46 bytes
```

`answer.md` is the rendering shown in the
[auditor walkthrough](../questions/open/WALKTHROUGH.md#readable-return). The
manifest names who sealed the answer and binds every member's digest.

## 9. Close

```text
$ stewart close REF
Command stewart close: completed
Commission: accepted.
Run 2 ended after auditor submission.
The auditor submitted its answer and the seal was recorded; the run's delivery ended verified.
Answer: revision 3 sealed by the auditor.
Delivery: attempt 1 is verified at /home/ana/returns/stewart-return-…-001.
Audit: closed. Ordinary close confirmed placement of the copy delivered before close was requested.
Cumulative usage / limits: turns 4/200 (reported 4; estimated 0), input_tokens 12000/20000000 (reported 12000; estimated 0), output_tokens 1600/400000 (reported 1600; estimated 0).
Effects: run ended, seal existing, delivery verified, closure complete


Next: no command is supplied.
```

The run had already delivered, so an ordinary close confirms where the copy
is. Close works from every state. When it makes the copy itself, it presents a
confirmation token for `close REF --confirm TOKEN`; when members are known to
be lost, closing also requires naming each one with `--surrender`. These
confirm custody. None of them endorses the answer.

A closed audit cannot run again:

```text
$ stewart run REF
stewart run: refused (reference_closed)
The audit is closed (log/…), so no run can start.
Effects: run ended, answer unchanged, seal existing, delivery verified, diagnostic durable
Retained:
  /home/ana/stewart-archive/audits/…/diag/2.json

record: log/…

Next:
  /usr/local/bin/stewart status REF
      See how the audit closed.
```
