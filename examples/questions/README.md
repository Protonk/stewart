# Worked question examples

One example for each of the three question families. The invented reminder
service supplies a small common world. Each example has:

- `submission/`: a submission folder, `question.md` with `question/1` front
  matter and `materials/`, that `stewart prepare` accepts as written;
- `WALKTHROUGH.md`: an auditor's calls written by hand, with Stewart's replies
  and the rendered answer, then a variant with inadequate evidence.

The walkthroughs show what each family lets an auditor express, including
inadequate evidence; alternate returns are permitted. No model produced their
entries, so they establish nothing about how a model uses the arrangement.
Expected substantive conclusions are never acceptance criteria.

| Example | Family | Work and inadequate-evidence variant |
| --- | --- | --- |
| [Open inquiry](open/WALKTHROUGH.md) | `open-inquiry` | A broad bug-free request, a bounded source account, and a report-only variant. |
| [Inquiry framing](framing/WALKTHROUGH.md) | `inquiry-framing` | A concern about reminders, an attributed working question and investigation; a requirements-only variant. |
| [Comparison](comparison/WALKTHROUGH.md) | `comparison` | A/B tradeoffs against supplied criteria; an absent-B variant that permits inability and one-sided observations. |

[Citation controls](CITATION-CONTROLS.md) distinguish exact quote checking from
semantic support and include empty and conflicting answer cases.

## Preparing an example

The materials are exact bytes: the walkthroughs, the citation controls and
[QUESTION-FORMS](../../docs/QUESTION-FORMS.md) cite their byte ranges and line
numbers, so copy them unchanged. With the `stewart` binary built
([DEVELOPMENT](../../DEVELOPMENT.md)), from the repository root, and with
absolute paths, as every path argument must be:

```sh
stewart new /home/ana/reminders --archive /home/ana/stewart-archive
cp examples/questions/open/submission/question.md /home/ana/reminders/question.md
cp -R examples/questions/open/submission/materials/. /home/ana/reminders/materials/
stewart prepare REF
```

`new` creates an absent folder inside an existing directory, with the scaffold
`question.md` and an empty `materials/`, which the copies replace. It prints the
reference (`stw1:…`) to give `prepare` as REF. `prepare` checks the folder and
pins the arrangement; it accepts nothing. The archive root must be on local
ext4, xfs or btrfs. A variant is another audit: a new folder with the same
`question.md` and only the materials its walkthrough names.

Two front matter settings depend on where the example is used:

- `destination: /var/tmp` names a directory present on standard Linux systems,
  so the examples prepare as written. Set it to the absolute path of the
  existing directory where the return package should go. The folder, the
  archive and the destination must not contain one another
  (`location_overlap`).
- `model: claude-opus-5-5` is the provider model for every run of the audit.
  Set it to a model your provider key can use.

Change them before the `prepare` whose handle you commission. Commission, run
and close are described by `stewart help`; only `run` contacts the provider.
It sends no request once a limit in the front matter is exhausted, but counted
usage can pass a limit: a request's input size is known only from its
response, and estimates for lost responses can take counted output past its
limit ([INTERFACE](../../docs/INTERFACE.md) 6.4).

An optional `effort:` line (`low`, `medium`, `high`, `xhigh` or `max`) asks
the provider for that effort on every request of the audit. The examples set
none, so the model's provider default applies.
