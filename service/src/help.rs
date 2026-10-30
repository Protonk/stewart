//! `stewart help [commands | forms | limits | reader | close]` (INTERFACE 5.9).
//! Help ships with the binary, is printed exactly and involves no archive.

use crate::forms::{self, FAMILIES};
use crate::scan;

pub const TOPICS: [&str; 5] = ["commands", "forms", "limits", "reader", "close"];

pub fn overview() -> String {
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

Every command except help takes --json for one machine-readable reply on stdout.
Topics: stewart help commands | forms | limits | reader | close
"
    .to_string()
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
  The folder holds exactly two entries: question.md and materials/. Anything else
  at its root is refused; move it under materials/ (the auditor may read it) or
  out of the folder. Everything under materials/ is included, hidden names and
  empty files and directories too. Links, FIFOs, sockets and devices are refused
  unread; nothing is silently skipped or renamed.

  question.md begins with front matter between --- lines:
    stewart: question/1
    family: open-inquiry | inquiry-framing | comparison
    model: the provider model for every run of this audit
    destination: an existing absolute directory for the return package
    limit-turns, limit-input-tokens, limit-output-tokens: cumulative limits
    inquiry: optional label for your own line of questions
    varies: optional stw1: reference of an earlier audit this one varies
  The question body is every byte after the closing --- line, exactly as
  written; the auditor receives it and never sees the front matter.

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
      The fixed commission: question, materials, arrangement, checks, the run
      line and the readback items. --verify reads and hashes each item.
  stewart receipt REF --read ITEM
      Write one item's captured bytes, exactly, to stdout; one JSON line on
      stderr says whether they verified. Unverified bytes are never written.
      Items: question-file, question-body, arrangement, arrangement-readable,
      materials/<name>.
  stewart status REF [--json]
  stewart status --archive ROOT [--json]
      Read-only facts: accepted, launched, sealed, delivered, closed, with the
      evidence behind them and the supported next calls.
  stewart run REF [--json]
      Place the auditor (needs ANTHROPIC_API_KEY and the network).
  stewart close REF [--confirm TOKEN] [--surrender LOSS]... [--destination DIR] [--json]
      End the reference. See: stewart help close.

Replies: exit 0 completed, 2 usage, 3 refused, 4 failed. A missing reply means
the effects are unknown; status reconciles from the records.
"
    .to_string()
}

fn forms_text() -> String {
    let mut s = String::from(
        "\
Question families

The family is chosen in question.md (family: ...). The auditor sees the
orientation, its family's instructions and its tools; it never sees the family
name. Every family permits answering that the materials are inadequate, that the
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
  material files                          {}
  one material file                       {} bytes (16 MiB)
  question and materials together         {} bytes (128 MiB)
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

Auditor reading bounds: 64 KiB of text per read page; 128 search hits and 32 KiB
of context per page; 128 materials per list page; 4 MiB per tool call. Answers:
256 entries, 64 MiB per entry, 256 MiB in the current selection.
",
        scan::QUESTION_BYTES,
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
Close is available in every state. It is one algorithm: repeating it resumes from
the recorded state. It never removes anything and leaves your folder alone.

Before launch (no run has started):
  Close records the request, waits up to 10 s for a commission that is capturing,
  records the end of any intake whose process is gone, and records the reference
  as closed, saying whether a commission had been accepted. No answer, seal or
  confirmation is created, and no run can start afterwards.
  If the intake is still running after 10 s: unfinished, intake_still_running.
  Run close again.

After launch:
  Stop    Close records its request; a run notices and stops. If a run still
          holds the audit after 30 s: unfinished, run_still_held. Run close again.
  Seal    An auditor's seal is kept. Otherwise close seals the recorded answer
          with manager attribution; an unreadable entry becomes a named,
          unproduced member.
  Deliver Close delivers the sealed return to the commissioned destination, or
          presents a delivery that already verified. A partial or failed
          delivery leaves close unfinished (delivery_incomplete); continue with
          close, or close --destination DIR for a replacement destination.
  Confirm A delivery close produced must be confirmed:
          close REF --confirm TOKEN (status shows the token). A delivery that
          verified before you first asked to close needs no confirmation.
  Surrender  If members could not be produced, confirmation also needs
          --surrender LOSS for each named loss.

Other unfinished reasons: close_in_progress (another close holds the audit) and
log_damaged (close publishes nothing to a damaged log; restore your storage).
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
