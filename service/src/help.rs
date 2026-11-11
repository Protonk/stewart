//! `stewart help [commands | forms | limits | reader | close]` (INTERFACE 5.9).
//! Help ships with the binary, is printed exactly and involves no archive.

use crate::forms::{self, FAMILIES};
use crate::scan;

pub const TOPICS: [&str; 5] = ["commands", "forms", "limits", "reader", "close"];

#[cfg(feature = "claude-code")]
fn build_notice() -> &'static str {
    crate::claude_code::BUILD_NOTICE
}

#[cfg(not(feature = "claude-code"))]
fn build_notice() -> &'static str {
    ""
}

pub fn overview() -> String {
    let mut text = String::from(build_notice());
    text.push_str(
        "\
Stewart keeps a bounded inquiry honest: you supply a question, selected
materials, a question family and limits; an auditor answers inside that
arrangement; Stewart keeps the records and returns the answer without judging it.

The manager's path:
  1. stewart new FOLDER --archive ROOT
       Creates a reference, the archive if absent, and the folder's scaffold if
       absent. Put your question in FOLDER/question.md and the files the auditor
       may read under FOLDER/materials/, using ordinary tools.
  2. Finish editing, then: stewart prepare REF
       Scans and hashes the folder, checks the intake rules and pins the
       arrangement. It accepts nothing. Leave the folder unchanged from here
       until commission returns.
  3. stewart commission REF HANDLE --i-am-finished
       Copies and verifies exactly the prepared selection. Acceptance fixes that
       copy; later edits to the folder cannot change it.
  4. stewart run REF
       The receipt's run line. Only run uses the network and the provider key.
  5. stewart close REF
       Ends the reference from any state. Before launch it creates no answer.

Read-only at any time:
  stewart receipt REF [--verify]     the fixed commission and its readback items
  stewart receipt REF --read ITEM    the exact captured bytes of one item
  stewart status REF                 where the audit stands, with evidence
  stewart status --archive ROOT      every reference in an archive

Commands take --json for one machine-readable reply on stdout, except help and
receipt --read, which writes the exact item bytes and accepts no --json option.
Status, run and close give a brief account by default; --details adds the full
observations. --details and --json cannot be combined. A completed command does
not imply completed custody or an adequate answer. A run is one execution
placement; an audit keeps its ledger and cumulative limits across placements.
Topics: stewart help commands | forms | limits | reader | close
",
    );
    text
}

pub fn topic(name: &str) -> Option<String> {
    Some(match name {
        "commands" => commands(),
        "forms" => forms_text(),
        "limits" => limits(),
        "reader" => reader(),
        "close" => close(),
        _ => return None,
    })
}

fn commands() -> String {
    "\
The submission folder
  The folder holds question.md and materials/, plus guidance.md only when
  explicitly selected for open inquiry. Other root entries are refused; move
  evidence under materials/ or move unselected files out of the folder. Everything under materials/ is included, hidden names and
  empty files and directories too. Links, FIFOs, sockets and devices are refused
  unread; nothing is silently skipped or renamed.

  question.md begins with front matter between --- lines:
    stewart: question/1
    family: open-inquiry | inquiry-framing | comparison
    guidance: optional guidance.md, only with open-inquiry; replaces its whole
      family-guidance block with this root file (at most 256 KiB of nonblank
      UTF-8 text without NUL). Omit the key to use built-in guidance.
    model: the provider model for every run of this audit
    effort: optional low | medium | high | xhigh | max, sent to the provider
      with every request; without it the model's provider default applies
    destination: an existing absolute directory for the return package
    limit-turns, limit-input-tokens, limit-output-tokens: cumulative limits
    inquiry: optional label for your own line of questions
    varies: optional stw1: reference of an earlier audit this one varies
  The question body is every byte after the closing --- line, exactly as
  written; the auditor receives it and never sees the front matter.

  Guidance is instruction text, separate from evidence materials. It cannot
  change tools, capabilities, notices, limits or custody. Prepare shows the
  effective text and its origin; receipt recovers the accepted bytes. No includes,
  arbitrary paths, template expansion or semantic certification are performed.

  Finish editing before prepare, and leave the folder unchanged from prepare
  until commission returns: prepare hashes what is there, and commission refuses
  a selection that changed meanwhile. Prepare again after any change.

Commands
  stewart new FOLDER [--archive ROOT] [--json]
      Create a reference. ROOT may also come from STEWART_ARCHIVE (for new only).
      An absent ROOT is created with a store marker; an existing empty directory
      is initialized; an existing Stewart archive is used. An absent FOLDER gets
      the scaffold; an existing one is used unchanged. Paths are absolute.
  stewart prepare REF [--json]
      Inspect and pin the selection; returns a handle (mp1.xxxxxx) and the
      locations of the readable and machine arrangement. Accepts nothing.
  stewart commission REF HANDLE --i-am-finished [--json]
      Accept exactly that prepared selection. --i-am-finished is your declaration
      that you finished assembling it and will leave the folder unchanged until
      this returns. Repeating it after a lost reply returns the recorded
      acceptance without capturing again.
  stewart receipt REF [--verify] [--json]
      The fixed commission: question, selected guidance, materials, arrangement, checks, the run
      line and the readback items. --verify reads and hashes each item.
  stewart receipt REF --read ITEM
      Write one item's captured bytes, exactly, to stdout; one JSON line on
      stderr says whether they verified. Unverified bytes are never written.
      Items: question-file, question-body, guidance-file (when supplied),
      arrangement, arrangement-readable,
      materials/<name>.
  stewart status REF [--details | --json]
  stewart status --archive ROOT [--details | --json]
      Read-only account of the commission, run, answer, delivery and closure,
      including unknown facts, losses, cumulative usage and supported next calls.
      --details includes the underlying observations and evidence; --json gives
      the complete structured reply. Neither option changes the audit.
  stewart run REF [--key-fd FD] [--details | --json]
      Place the auditor, in the foreground until the placement ends. Needs
      a provider credential and the network. Prefer --key-fd FD, an inherited
      descriptor (0 or at least 3) carrying 1–4096 visible ASCII bytes and an
      optional final LF, then EOF within five seconds. Stewart consumes and
      closes it. ANTHROPIC_API_KEY is an alternative; combining sources refuses.
      Linux runs disable core dumps and ordinary process inspection before
      reading the key. Environment input retains the operating system's
      environment exposure; descriptor input avoids putting the key there.
      STEWART_PROVIDER_URL (https://, or
      http:// to a loopback host) and HTTPS_PROXY (http://host:port) are
      optional. An interrupted run exits 5; run again to continue under the
      same cumulative limits. A run can stop without ending authoring, and
      authoring can end while custody remains unfinished. The seal actor names
      who sealed: a manager seal is not auditor submission.
      A reflected credential stops before tools or retries. Raw response bodies
      and retained headers stay exact and private; derived text is explicitly
      redacted. Revoke the exposed key and review evidence before continuing or
      exporting the archive.
  stewart close REF [--confirm TOKEN] [--surrender LOSS]... [--destination DIR] [--details | --json]
      End the reference. See: stewart help close.

Replies: exit 0 completed, 2 usage, 3 refused, 4 failed; run exits 5 when its
placement was interrupted and recorded, and run continues it. A missing reply
means the effects are unknown; status reconciles from the records.
"
    .to_string()
}

fn forms_text() -> String {
    let mut s = String::from(
        "\
Question families

The family is chosen in question.md (family: ...). The auditor sees the
orientation, its effective family guidance, tools and captured base family ID.
Open inquiry accepts an explicitly selected guidance.md replacement; the arrangement
identifies supplied guidance separately from stock family wording. Every family permits answering that the materials are inadequate, that the
premise is wrong or that nothing supported was found; none requires a defect, a
winner or a repair. Missing sections and an empty answer can be submitted.

Orientation (stewart.orientation/1), given in every family:

",
    );
    s.push_str(&indent(forms::ORIENTATION));
    for f in &FAMILIES {
        s.push_str(&format!(
            "\n\n{} (family: {}, {})\n\nInstructions:\n\n",
            f.title,
            f.id,
            f.versioned_id()
        ));
        s.push_str(&indent(f.instructions));
        s.push_str("\n\nRecording tools:\n");
        for t in f.tools {
            s.push_str(&format!("  {t}: {}\n", forms::tool_description(t)));
        }
        s.push_str("  record_artifact: ");
        s.push_str(forms::tool_description("record_artifact"));
        s.push('\n');
        let missing: Vec<&str> = f.sections.to_vec();
        s.push_str(&format!(
            "Prepare notes (without refusing) when no entries of these are recorded: {}.\n",
            missing.join(", ")
        ));
    }
    s.push_str(
        "\nEvery family also has list, read and search over the captured question and
materials, replace, delete, what_am_i_working_with, prepare and submit. The exact
tool definitions are pinned in each preparation's arrangement.md.
",
    );
    s
}

fn indent(text: &str) -> String {
    let mut out = Vec::new();
    for para in text.split("\n\n") {
        let mut line = String::from("   ");
        let mut lines = Vec::new();
        for w in para.split(' ') {
            if line.len() + w.len() + 1 > 80 {
                lines.push(line);
                line = String::from("   ");
            }
            line.push(' ');
            line.push_str(w);
        }
        lines.push(line);
        out.push(lines.join("\n"));
    }
    out.join("\n\n")
}

fn limits() -> String {
    format!(
        "\
Intake bounds (recorded in each preparation and commission; they do not say
whether a question has enough context):
  question.md, including front matter    {} bytes (256 KiB)
  selected guidance.md                    {} bytes (256 KiB)
  material files                          {}
  one material file                       {} bytes (16 MiB)
  question, guidance and materials        {} bytes (128 MiB)
  directories under materials/, with it   {}
  material path                           {} bytes, {} components, {} bytes per component
Bounds are enforced while scanning. Exceeding one refuses with bound_exceeded,
naming the bound, the limit and the entry; nothing is excluded silently.

Run limits (front matter), cumulative across every run of the audit and counted
from the provider's usage reports, with a stated estimate for a lost response:
  limit-turns           1 to 10,000
  limit-input-tokens    1 to 2,000,000,000
  limit-output-tokens   1 to 200,000,000
The scaffold starts at 200 turns, 20,000,000 input and 400,000 output tokens.
A request is not sent when no turn remains, the input allowance is used up or
fewer than 1,024 output tokens remain. One near-limit notice is given per audit
when {}% or less of an allowance remains. Stewart sets no money limit.
Provider compaction automatically summarizes a large active context at 150,000
tokens. Summary calls consume these same turns and token allowances. Original
exchanges and the recorded answer remain retained. A provider refusal is reported
as given; Stewart does not silently disable compaction or change the model.

Auditor reading bounds: 64 KiB of text per read page; 128 search hits and 32 KiB
of context per page; 128 materials per list page; 4 MiB per tool call. Answers:
256 entries, 64 MiB per entry, 256 MiB in the current selection.
",
        scan::QUESTION_BYTES,
        scan::GUIDANCE_BYTES,
        scan::FILES,
        scan::FILE_BYTES,
        scan::TOTAL_BYTES,
        scan::DIRECTORIES,
        scan::PATH_BYTES,
        scan::PATH_COMPONENTS,
        scan::COMPONENT_BYTES,
        forms::NEAR_LIMIT_PERCENT
    )
}

fn reader() -> String {
    "\
The reader: utf8-text/1

Question and material files must be valid UTF-8 without NUL bytes. Their bytes
are kept exactly: line endings, byte-order marks, empty files and missing final
newlines included. There is no transcoding, newline normalization, OCR, archive
expansion, document extraction or execution, whatever the file name says. JSON,
CSV and SVG are text; a document format whose bytes happen to be text is served
as raw syntax, not as a rendered document. PDFs, images, office files and other
binary formats are refused at prepare (material_not_text, naming the file and
the offset of the first invalid byte); supply a text export instead.

Names are UTF-8 without control characters and are kept exactly, with no
Unicode normalization. A material's public name is materials/ followed by its
path, with / between components.

The auditor reads pages of at most 64 KiB, ending at the source's end, just after
the last LF in the window, or at the last character boundary; a ready next call
continues the page, so long lines are never cut silently. Search is literal and
case-sensitive, and an incomplete search never reports absence.
"
    .to_string()
}

fn close() -> String {
    "\
stewart close REF [--confirm TOKEN] [--surrender LOSS]... [--destination DIR]

Close is available in every state. It is one algorithm: repeating it resumes from
the recorded state, so after a lost reply you simply run it again, from any
directory. It never removes anything: not at a destination, not in the archive
and not in your folder. --surrender is accepted only with --confirm, and
--destination only without it.

Before launch (no run has started):
  Close records the request, waits up to 10 s for a commission that is capturing,
  records the end of any intake whose process is gone, and records the reference
  as closed, saying whether a commission had been accepted. No answer, seal or
  confirmation is created, and no run can start afterwards. --confirm,
  --surrender and --destination are refused: nothing is owed for delivery.

After launch, in order:
  Stop     Close records its request, which ends authoring; a run notices it
           and stops. A seal alone never counts as a stopped run.
  Seal     An existing seal is kept, whoever made it. Otherwise close seals the
           answer recorded when you asked to close, attributed to you, the
           manager, never to the auditor. An entry whose bytes cannot be read
           or verified becomes a named, unproduced member, and so does the
           rendering that depends on it.
  Deliver  Close delivers the sealed return into a fresh package at the
           destination, or presents a delivery that already verified. Each
           attempt uses a new package; earlier attempts stay where they are.
  Confirm  A delivery that verified before you first asked to close is placed
           by the ordinary close itself. A delivery close produced, or one with
           losses, waits for close REF --confirm TOKEN; status shows the token.
           Confirming places the copy; it does not accept the answer.
  Surrender  When the delivery has losses (members that could not be produced
           or supplied), --confirm also needs --surrender LOSS naming each one,
           so you give each up explicitly. Status lists the loss IDs. A closure
           with surrendered losses is never a complete delivery.

Unfinished closes and how to continue (the reply's unfinished_reason):
  intake_still_running   A commission still holds the reference after 10 s.
                         Run close again.
  run_still_held         A run still holds the audit after 30 s; the reply names
                         its holder. Run close again once it has stopped.
  close_in_progress      Another close holds the audit. Run close again.
  delivery_incomplete    No delivery attempt verified. Run close again to retry
                         at the last destination, or, after an attempt that
                         was partial or failed, close REF --destination DIR to
                         deliver to another existing directory. A destination
                         is never replaced after a delivery verified.
  awaiting_confirmation  A delivery verified and needs your confirmation:
                         close REF --confirm TOKEN, with --surrender LOSS for
                         each loss. Repeating close without the token only
                         presents the same delivery again.
  log_damaged            The audit log is damaged; close publishes nothing to
                         it. Status names the bad records; restore your own
                         storage, or start a new reference.

When the seal's manifest cannot be read, membership is unknown: delivery fails,
no loss IDs exist and close stays unfinished. Unknown membership is never
treated as an empty answer.

Closed (closure complete): repeating close returns the recorded outcome with
already_closed true. The receipt stays readable through status.
"
    .to_string()
}

#[cfg(test)]
mod tests {
    #[test]
    fn every_topic_has_text_and_mentions_no_test_controls() {
        let mut all = super::overview();
        for t in super::TOPICS {
            let text = super::topic(t).expect("topic");
            assert!(!text.is_empty());
            all.push_str(&text);
        }
        assert!(all.contains("leave the folder unchanged"));
        assert!(!all.contains("STEWART_TEST"));
        assert!(super::topic("nope").is_none());
    }
}
