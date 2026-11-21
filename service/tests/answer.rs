//! The auditor's tools against a commissioned audit with a live placement,
//! driven in process (INTERFACE 7, 8.1; QUESTION-FORMS).
//!
//! The independent release driver owns the answer protocol. A case belongs
//! here only when the driver cannot give it to the development loop: no
//! driver case reaches its boundary, its driver case runs only on Linux, or
//! it pins bytes or state that only the implementation knows. Cases at fault
//! points are in `answer_faults.rs`.
// Publication closures return the crate's `Fail` by value, as the crate does.
#![allow(clippy::result_large_err)]

mod answer_support;
mod common;

use answer_support::*;
use common::*;
use stewart::answer::{self, End, Preparer, Sealer};
use stewart::json::J;

// ---------------------------------------------------------------------------
// Reading.

/// Intake admits at most 128 materials and a list page holds 128, so a
/// commissioned list is always one complete page.
#[test]
fn a_list_page_holds_every_material_intake_admits() {
    let names: Vec<String> = (0..128).map(|i| format!("m{i:03}.txt")).collect();
    let mats: Vec<(&str, &[u8])> = names.iter().map(|n| (n.as_str(), b"x" as &[u8])).collect();
    let mut l = Live::open("open-inquiry", "Q?\n", &mats);
    let r = l.call("list", "{}");
    assert_eq!(r.num(&["returned"]), 128);
    assert_eq!(r.num(&["total"]), 128);
    assert_eq!(r.data(&["complete"]).v, stewart::json::V::Bool(true));
    assert!(r.next_tools().is_empty());
    assert_eq!(r.str(&["materials", "127", "source"]), "materials/m127.txt");
}

/// A search cursor continues only the search that issued it: the same text
/// over the same scope. The next call does not restate a default scope, and
/// empty search text is refused.
#[test]
fn search_cursors_are_bound_to_their_text_and_scope() {
    let xs = vec![b'x'; 300];
    let mut l = Live::open("open-inquiry", "Q?\n", &[("x.txt", &xs)]);
    let r = l.call("search", r#"{"text":"xx"}"#);
    assert_eq!(r.num(&["returned"]), 128);
    assert_eq!(r.data(&["complete"]).v, stewart::json::V::Bool(false));
    let next = r.next_input(0);
    assert!(
        !next.contains("sources"),
        "the default scope is not restated: {next}"
    );
    let r2 = l.call("search", &next);
    assert_eq!(r2.num(&["hits", "0", "start"]), 128);
    let other = next.replace(r#""text":"xx""#, r#""text":"x""#);
    assert_eq!(l.call("search", &other).reason(), "handle_invalid");
    let narrowed = next.replace(
        r#""text":"xx","#,
        r#""text":"xx","sources":["materials/x.txt"],"#,
    );
    assert_eq!(l.call("search", &narrowed).reason(), "handle_invalid");
    assert_eq!(l.call("search", r#"{"text":""}"#).reason(), "input_invalid");
}

// ---------------------------------------------------------------------------
// Refusals, recording and edits.

/// Refused calls name what was wrong and record nothing: a recording tool
/// that another family offers is unknown here, naming this family's tools;
/// a block without a name or without an input; a label over its bound; and
/// the index of the citation that failed among several.
#[test]
fn refused_calls_name_what_was_wrong_and_change_nothing() {
    let mut l = Live::new();
    let own = l.world.arrangement.tool_names.clone();
    for kind in ["record_working_question", "record_criterion"] {
        assert!(!own.iter().any(|t| t == kind));
        let r = l.call(kind, r#"{"text":"x"}"#);
        assert_eq!(r.reason(), "tool_unknown", "{kind}");
        assert_eq!(s(&r.env, &["operation"]), kind);
        assert_eq!(
            at(&r.env, &["effects"]).to_j().string(),
            r#"{"raw_capture":"recorded"}"#,
            "{kind}"
        );
        assert_eq!(strs(&r.env, &["data", "tools"]), own, "{kind}");
    }
    let r = l.call_raw(None, Some(b"{}"));
    assert_eq!(
        (r.reason(), s(&r.env, &["operation"])),
        ("tool_unknown", "")
    );
    assert!(r.data(&["tool"]).is_null());
    assert_eq!(l.call_raw(Some("list"), None).reason(), "input_invalid");
    let r = l.call(
        "record_account",
        &format!(r#"{{"text":"","label":"{}"}}"#, "x".repeat(201)),
    );
    assert_eq!(
        (r.reason(), r.str(&["pointer"])),
        ("input_invalid", "/label")
    );
    let r = l.call(
        "record_limit",
        r#"{"text":"x","citations":[{"source":"question","start":0,"end":2},{"source":"question","quote":"absent text"}]}"#,
    );
    assert_eq!((r.reason(), r.num(&["index"])), ("quote_not_found", 1));
    assert_eq!(l.state().revision(), 0, "no refusal recorded anything");
}

/// Edits and reads aimed at a version that is no longer current, or at a
/// field the entry's kind lacks, are refused without changing the answer:
/// a replace naming a field the kind lacks is `fields_invalid`; a
/// superseded version reads `stale_entry` naming the current one; a deleted
/// entry reads and replaces `entry_deleted`, before any field is checked.
#[test]
fn superseded_deleted_and_mismatched_targets_are_refused() {
    let mut l = Live::new();
    let e1 = l.add("record_limit", "a limit", "");
    let replace = |entry: &str| {
        J::obj()
            .with("entry", entry)
            .with("label", "")
            .with("text", "b")
            .with("citations", J::Arr(vec![]))
    };
    let r = l.call("replace", &replace(&e1).with("base64", "AA==").string());
    assert_eq!(r.reason(), "fields_invalid");
    assert_eq!(strs(&r.env, &["data", "not_allowed"]), ["base64"]);
    assert_eq!(r.effect("answer"), "unchanged");
    let r = l.call("replace", &replace(&e1).string());
    r.ok();
    let e1v2 = r.str(&["entry"]).to_string();
    let r = l.call("read", &J::obj().with("source", e1.as_str()).string());
    assert_eq!(
        (r.reason(), r.str(&["current"])),
        ("stale_entry", e1v2.as_str())
    );
    l.call("delete", &J::obj().with("entry", e1v2.as_str()).string())
        .ok();
    let r = l.call("read", &J::obj().with("source", e1v2.as_str()).string());
    assert_eq!(r.reason(), "entry_deleted");
    let r = l.call(
        "replace",
        &J::obj()
            .with("entry", e1v2.as_str())
            .with("label", "")
            .string(),
    );
    assert_eq!(r.reason(), "entry_deleted");
    assert_eq!(l.state().revision(), 3, "the refusals changed nothing");
}

/// An artifact's encoding follows its input field, never its bytes:
/// `base64` records a binary artifact even when the bytes are valid UTF-8
/// text, it reads back as base64, and a replace keeps the encoding. Exactly
/// one of `text` and `base64` is required, the base64 must be canonical,
/// the label is required and nonempty, and an artifact takes no citations.
#[test]
fn an_artifacts_encoding_follows_its_input_field() {
    let mut l = Live::new();
    let r = l.call(
        "record_artifact",
        r#"{"label":"ascii","base64":"aGVsbG8="}"#,
    );
    r.ok();
    assert_eq!((r.str(&["encoding"]), r.num(&["size"])), ("binary", 5));
    let bin = r.str(&["entry"]).to_string();
    let read = l.call("read", &J::obj().with("source", bin.as_str()).string());
    read.ok();
    assert_eq!(read.blocks.len(), 1);
    assert_eq!(read.str(&["artifact_encoding"]), "binary");
    assert_eq!(read.str(&["base64"]), "aGVsbG8=");
    assert!(!has(read.data(&[]), "text"));
    for (input, reason) in [
        (
            r#"{"label":"t","text":"a","base64":"AA=="}"#,
            "fields_invalid",
        ),
        (r#"{"label":"t"}"#, "fields_invalid"),
        (r#"{"label":"t","base64":"AAE"}"#, "input_invalid"),
        (r#"{"label":"","text":"a"}"#, "input_invalid"),
    ] {
        assert_eq!(l.call("record_artifact", input).reason(), reason, "{input}");
    }
    assert_eq!(
        l.call("record_artifact", r#"{"text":"a"}"#).str(&["rule"]),
        "missing_key"
    );
    let r = l.call(
        "replace",
        &J::obj()
            .with("entry", bin.as_str())
            .with("label", "ascii")
            .with("text", "x")
            .with("citations", J::Arr(vec![]))
            .string(),
    );
    assert_eq!(
        (r.reason(), strs(&r.env, &["data", "not_allowed"])),
        ("fields_invalid", vec!["citations".to_string()])
    );
    let r = l.call(
        "replace",
        &J::obj()
            .with("entry", bin.as_str())
            .with("label", "ascii")
            .with("base64", "/w==")
            .string(),
    );
    r.ok();
    assert_eq!(
        (r.str(&["id"]), r.num(&["version"]), r.str(&["encoding"])),
        ("e1", 2, "binary")
    );
}

/// Answer bytes that no longer match their digest stop the auditor: read
/// and prepare refuse `answer_damaged` and end the placement, while
/// re-entry still lists the entry.
#[test]
fn damaged_answer_bytes_stop_the_auditor() {
    let mut l = Live::new();
    let e1 = l.add("record_account", "kept", "");
    let rec = l.state();
    let file = rec.selection()[0].version.payload.file.clone();
    let path = format!("{}/{file}", l.audit_dir());
    std::fs::remove_file(&path).unwrap();
    std::fs::write(&path, b"kepT").unwrap();
    let r = l.call("read", &J::obj().with("source", e1.as_str()).string());
    assert_eq!(r.reason(), "answer_damaged");
    assert!(r.next_tools().is_empty());
    assert_eq!(r.ex.end, Some(End::AnswerDamaged));
    let r = l.call("prepare", "{}");
    assert!(r.ex.log_record.is_none());
    assert!(!l.state().recs.iter().any(|r| r.kind == "answer_prepared"));
    assert_eq!(r.reason(), "answer_damaged");
    assert_eq!(r.str(&["entries", "0", "failure"]), "damaged");
    assert_eq!(r.ex.end, Some(End::AnswerDamaged));
    let r = l.call("what_am_i_working_with", "{}");
    assert!(r.data(&["entries", "0", "problem"]).is_null());
}

// ---------------------------------------------------------------------------
// Prepare, submit and seal.

/// An executing prepare can finish both files and still lose publication
/// to a stop. The next distinct invocation can prepare the same revision.
#[test]
fn a_stopped_preparation_keeps_its_files_and_publishes_no_record() {
    use std::time::{Duration, Instant};
    use stewart::gate::Gate;

    let mut l = Live::new();
    let gate = Gate::new(Instant::now() + Duration::from_secs(60));
    gate.stop();
    let stopped = l.call_by(
        Some("prepare"),
        Some(b"{}"),
        |audit, world, placement, call| answer::execute(audit, world, placement, call, Some(&gate)),
    );
    assert_eq!(stopped.reason(), "placement_stopped");
    assert!(stopped.ex.log_record.is_none());
    assert!(!l.state().recs.iter().any(|r| r.kind == "answer_prepared"));

    let prepared = l.call("prepare", "{}");
    prepared.ok();
    assert!(prepared.str(&["prepared"]).starts_with("ap2."));
    assert_eq!(
        l.file("prepared/1/answer.json"),
        l.file("prepared/2/answer.json")
    );
    assert_eq!(
        l.file("prepared/1/answer.md"),
        l.file("prepared/2/answer.md")
    );
    assert_eq!(
        l.state()
            .recs
            .iter()
            .filter(|r| r.kind == "answer_prepared")
            .count(),
        1
    );
}

/// A preparation's views keep the selection they fixed, even after an edit
/// makes the preparation stale. Once a confirmed submit seals, repeating it
/// returns the same seal, a later edit in the same placement is refused
/// naming the sealer, and reads still serve.
#[test]
fn a_seal_answers_repeats_and_later_edits() {
    let mut l = Live::new();
    l.add("record_account", "one", "");
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    l.add("record_limit", "two", "");
    let v = l.call(
        "read",
        &J::obj().with("source", format!("{ap}/selection")).string(),
    );
    assert!(v.blocks[1].contains("\"revision\":1"), "{}", v.blocks[1]);
    let ap2 = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let submit = J::obj()
        .with("prepared", ap2.as_str())
        .with("confirm", true)
        .string();
    let r = l.call("submit", &submit);
    r.ok();
    let seal = r.str(&["seal", "handle"]).to_string();
    assert_eq!(r.num(&["seal", "revision"]), 2);
    let again = l.call("submit", &submit);
    again.ok();
    assert_eq!(again.str(&["seal", "handle"]), seal);
    assert_eq!(
        again.data(&["already_sealed"]).v,
        stewart::json::V::Bool(true)
    );
    assert_eq!(again.effect("seal"), "existing");
    assert!(again.ex.sealed);
    let r = l.call("record_account", r#"{"text":"late"}"#);
    assert_eq!(r.reason(), "authoring_ended");
    assert_eq!(
        (
            r.str(&["ended_by"]),
            r.str(&["seal", "actor"]),
            r.str(&["seal", "handle"])
        ),
        ("seal", "auditor", seal.as_str())
    );
    assert_eq!(r.effect("answer"), "unchanged");
    l.call("read", r#"{"source":"question"}"#).ok();
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(
        (r.str(&["authoring", "state"]), r.str(&["seal", "actor"])),
        ("ended", "auditor")
    );
}

/// T6, close first, with close recorded before the submit begins (the
/// driver's races hold the submit at its link instead): the submit is
/// refused `authoring_ended` naming close. Close then seals the revision as
/// manager, and a later submit names that seal.
#[test]
fn t6_close_first_ends_authoring_and_close_seals_as_manager() {
    let mut l = Live::new();
    for i in 0..7 {
        l.add("record_observation", &format!("o{i}"), "");
    }
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let close = l.request_close();
    let after_close = l.call("prepare", "{}");
    assert_eq!(after_close.reason(), "authoring_ended");
    assert!(after_close.ex.log_record.is_none());
    assert_eq!(l.state().recs.len() as u64, close);
    let submit = J::obj()
        .with("prepared", ap.as_str())
        .with("confirm", true)
        .string();
    let r = l.call("submit", &submit);
    assert_eq!(r.reason(), "authoring_ended");
    assert_eq!(r.str(&["ended_by"]), "close");
    assert!(r.data(&["close_requested_at"]).as_str().is_some());
    assert!(r.str(&["seal", "state"]) == "absent" && r.data(&["seal", "actor"]).is_null());
    assert_eq!(r.effect("seal"), "none");
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.str(&["authoring", "state"]), "ended");
    assert_eq!(r.str(&["authoring", "ended_by"]), "close");
    let state = l.state();
    let family = l.world.arrangement.family().unwrap();
    let p = answer::prepare(&l.audit, family, &state, close, Preparer::Manager).unwrap();
    assert_eq!(p.revision, 7);
    let s = answer::seal(&l.audit, &family.versioned_id(), &p, Sealer::Manager, None).unwrap();
    assert_eq!(
        (s.actor, s.revision, s.existing),
        (stewart::bodies::Actor::Manager, 7, false)
    );
    let sealed = l.state();
    let (_, rec) = sealed.seal().unwrap();
    assert!(rec.invocation.is_none());
    let r = l.call("submit", &submit);
    assert_eq!(
        (r.reason(), r.str(&["seal", "actor"])),
        ("authoring_ended", "manager")
    );
    assert_eq!(r.effect("seal"), "existing");
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.str(&["authoring", "ended_by"]), "close");
    assert_eq!(r.str(&["seal", "actor"]), "manager");
}

/// T6 in the reverse order: the auditor's seal is linked first, so close's
/// manager seal stands down and the auditor's seal is the audit's. The
/// driver's race of this order runs only on Linux.
#[test]
fn t6_reverse_order_the_auditor_seal_stands_and_close_keeps_it() {
    let mut l = Live::new();
    l.add("record_account", "a", "");
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let r = l.call(
        "submit",
        &J::obj()
            .with("prepared", ap.as_str())
            .with("confirm", true)
            .string(),
    );
    r.ok();
    l.request_close();
    let state = l.state();
    let family = l.world.arrangement.family().unwrap();
    let p = answer::prepare(
        &l.audit,
        family,
        &state,
        state.close_requested().unwrap().n,
        Preparer::Manager,
    )
    .unwrap();
    match answer::seal(&l.audit, &family.versioned_id(), &p, Sealer::Manager, None) {
        Err(answer::SealError::AuthoringEnded { seal: Some(s), .. }) => {
            assert_eq!(
                (s.actor, s.existing),
                (stewart::bodies::Actor::Auditor, true)
            );
        }
        other => panic!("{other:?}"),
    }
    assert_eq!(
        answer::existing_seal(&l.audit, &l.state()).unwrap().actor,
        stewart::bodies::Actor::Auditor
    );
}

/// A manager seal over an entry whose payload is missing names the entry
/// unproduced (`missing`) and does not render around it: the rendering is
/// unproduced too, depending on that entry, and the manifest holds only
/// the question and the structured answer.
#[test]
fn a_manager_seal_names_unreadable_entries_and_never_renders_around_them() {
    let mut l = Live::new();
    l.add("record_account", "kept", "");
    l.add("record_observation", "lost", "");
    let state = l.state();
    let lost = state.selection()[1].version.payload.file.clone();
    std::fs::remove_file(format!("{}/{lost}", l.audit_dir())).unwrap();
    let close = l.request_close();
    let state = l.state();
    let family = l.world.arrangement.family().unwrap();
    let p = answer::prepare(&l.audit, family, &state, close, Preparer::Manager).unwrap();
    assert!(p.rendering.is_none());
    assert_eq!(p.unproduced.len(), 2);
    let json = String::from_utf8(l.file(&format!("prepared/{}/answer.json", p.n))).unwrap();
    assert!(json.contains(r#"{"id":"e2","version":1,"kind":"record_observation","label":"","unproduced":{"sha256":""#), "{json}");
    assert!(json.contains(r#""failure":"missing"}}"#), "{json}");
    assert!(
        !std::path::Path::new(&format!("{}/prepared/{}/answer.md", l.audit_dir(), p.n)).exists()
    );
    let s = answer::seal(&l.audit, &family.versioned_id(), &p, Sealer::Manager, None).unwrap();
    let st = l.state();
    let rec = st.seal().unwrap().1;
    assert!(rec.rendering_sha256.is_none());
    let (m, _) =
        stewart::returns::load_manifest(&l.audit, &rec.manifest, &s.manifest_sha256).unwrap();
    assert_eq!(m.member_names(), ["question.md", "answer.json"]);
    assert_eq!(m.unproduced[0].name, "e2");
    assert_eq!(
        m.unproduced[1].dependency.as_deref(),
        Some(&["e2".to_string()][..])
    );
}
