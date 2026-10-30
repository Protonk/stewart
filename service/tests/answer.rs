//! The auditor's tools against a commissioned audit with a live placement
//! (INTERFACE 7, 8.1; QUESTION-FORMS): every reply shape, the strict input
//! rules, citations, edits and their races with seal and close.
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

#[test]
fn list_and_read_serve_the_captures_exactly() {
    let mut l = Live::new();
    // The live folder changes after acceptance; reads never consult it.
    std::fs::write(l.e.path("q/materials/a.py"), b"changed").unwrap();
    let r = l.call("list", "{}");
    r.ok();
    assert_eq!(r.effect("raw_capture"), "recorded");
    assert_eq!(r.num(&["total"]), 4);
    assert_eq!(r.num(&["returned"]), 4);
    assert_eq!(r.data(&["complete"]).v, stewart::json::V::Bool(true));
    assert_eq!(r.str(&["materials", "0", "source"]), "materials/a.py");
    assert_eq!(r.num(&["materials", "0", "size"]), 36);
    assert_eq!(r.num(&["materials", "0", "lines"]), 3);
    assert_eq!(strs(&r.env, &["data", "directories"]), ["materials"]);
    assert!(r.next_tools().is_empty());

    let r = l.call("read", r#"{"source":"materials/a.py"}"#);
    r.ok();
    assert_eq!(r.blocks.len(), 2);
    assert_eq!(r.blocks[1], "def retry():\r\n    send()\n    send()\n");
    assert_eq!(r.str(&["kind"]), "material");
    assert_eq!(r.data(&["range"]).to_j().string(), "[0,36]");
    assert_eq!(r.data(&["lines"]).to_j().string(), "[1,3]");
    assert_eq!(
        r.data(&["cite"]).to_j().string(),
        r#"{"source":"materials/a.py","start":0,"end":36}"#
    );
    assert!(!has(r.data(&[]), "text"));

    let r = l.call("read", r#"{"source":"question"}"#);
    assert_eq!(r.str(&["kind"]), "question");
    assert_eq!(r.blocks[1], "Is the retry safe?\n");

    // A blank page has no second block; its exact text is in data.text.
    let r = l.call("read", r#"{"source":"materials/blank.txt"}"#);
    assert_eq!(r.blocks.len(), 1);
    assert_eq!(r.str(&["text"]), "  \n");
    // An empty page at the end: no cite, no lines.
    let r = l.call("read", r#"{"source":"materials/u.txt","start":7}"#);
    r.ok();
    assert!(r.data(&["cite"]).is_null() && r.data(&["lines"]).is_null());
    assert_eq!(r.str(&["text"]), "");

    // start inside a character, or past the end.
    let r = l.call("read", r#"{"source":"materials/u.txt","start":2}"#);
    assert_eq!(r.reason(), "range_invalid");
    assert_eq!(r.data(&["nearest"]).to_j().string(), "[1,3]");
    assert_eq!(r.effect("raw_capture"), "recorded");
    let r = l.call("read", r#"{"source":"materials/u.txt","start":8}"#);
    assert_eq!(r.reason(), "range_invalid");

    // Names are exact: a near miss is refused with hints, never normalized.
    let r = l.call("read", r#"{"source":"materials/a.pyy"}"#);
    assert_eq!(r.reason(), "source_unknown");
    assert_eq!(r.str(&["hints", "0"]), "materials/a.py");
    let r = l.call("read", r#"{"source":"e1.v1.aaaaaa"}"#);
    assert_eq!(r.reason(), "handle_invalid");
    let r = l.call("read", r#"{"source":"ap1.aaaaaa/rendering"}"#);
    assert_eq!(r.reason(), "handle_invalid");
    // No host path or manager identifier reaches the auditor.
    for b in &r.blocks {
        assert!(!b.contains(&l.e.archive) && !b.contains(&l.e.folder), "{b}");
    }
}

#[test]
fn long_sources_come_in_pages_that_end_after_a_line() {
    let mut big = Vec::new();
    for i in 0..3000 {
        big.extend_from_slice(format!("line {i:05} of the long material\n").as_bytes());
    }
    let mut l = Live::open("open-inquiry", "Q?\n", &[("big.txt", &big)]);
    let r = l.call("read", r#"{"source":"materials/big.txt"}"#);
    r.ok();
    let end = r.num(&["range", "1"]) as usize;
    assert!(end <= 65_536 && big[end - 1] == b'\n', "{end}");
    assert_eq!(r.data(&["complete"]).v, stewart::json::V::Bool(false));
    assert_eq!(r.next_tools(), ["read"]);
    assert_eq!(
        r.next_input(0),
        format!(r#"{{"source":"materials/big.txt","start":{end}}}"#)
    );
    let mut got = r.blocks[1].clone().into_bytes();
    let mut input = r.next_input(0);
    loop {
        let r = l.call("read", &input);
        got.extend_from_slice(r.blocks[1].as_bytes());
        if r.next_tools().is_empty() {
            break;
        }
        input = r.next_input(0);
    }
    assert_eq!(got, big, "the pages join to the exact source");
}

#[test]
fn a_list_page_holds_every_material_intake_admits() {
    // Intake admits at most 128 files and a page holds 128 materials, so a
    // commissioned list is always one page; a cursor must still match.
    let names: Vec<String> = (0..128).map(|i| format!("m{i:03}.txt")).collect();
    let mats: Vec<(&str, &[u8])> = names.iter().map(|n| (n.as_str(), b"x" as &[u8])).collect();
    let mut l = Live::open("open-inquiry", "Q?\n", &mats);
    let r = l.call("list", "{}");
    assert_eq!(r.num(&["returned"]), 128);
    assert_eq!(r.num(&["total"]), 128);
    assert_eq!(r.data(&["complete"]).v, stewart::json::V::Bool(true));
    assert!(r.next_tools().is_empty());
    assert_eq!(r.str(&["materials", "127", "source"]), "materials/m127.txt");
    assert_eq!(
        l.call("list", r#"{"cursor":"ls.0.aaaaaa"}"#).reason(),
        "handle_invalid"
    );
}

#[test]
fn search_reports_every_occurrence_with_ready_citations() {
    let mut l = Live::new();
    let r = l.call("search", r#"{"text":"send()"}"#);
    r.ok();
    assert_eq!(r.num(&["returned"]), 2);
    assert_eq!(
        strs(&r.env, &["data", "scope"]),
        [
            "question",
            "materials/a.py",
            "materials/blank.txt",
            "materials/notes.txt",
            "materials/u.txt"
        ]
    );
    let h = r.data(&["hits", "0"]).to_j().string();
    assert_eq!(
        h,
        r#"{"source":"materials/a.py","start":18,"end":24,"line":2,"context":{"text":"    send()","truncated_before":false,"truncated_after":false},"cite":{"source":"materials/a.py","start":18,"end":24}}"#
    );
    assert_eq!(r.num(&["hits", "1", "line"]), 3);
    assert_eq!(r.data(&["complete"]).v, stewart::json::V::Bool(true));
    let r = l.call(
        "search",
        r#"{"text":"retry()","sources":["materials/notes.txt"]}"#,
    );
    assert_eq!(r.num(&["returned"]), 1);
    assert_eq!(strs(&r.env, &["data", "scope"]), ["materials/notes.txt"]);
    assert_eq!(
        l.call("search", r#"{"text":"x","sources":["materials/none"]}"#)
            .reason(),
        "source_unknown"
    );
    assert_eq!(l.call("search", r#"{"text":""}"#).reason(), "input_invalid");
}

#[test]
fn search_pages_are_bound_to_text_scope_and_position() {
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
    assert_eq!(r2.num(&["returned"]), 128);
    assert_eq!(r2.num(&["hits", "0", "start"]), 128);
    let r3 = l.call("search", &r2.next_input(0));
    assert_eq!(r3.num(&["returned"]), 299 - 256);
    assert_eq!(r3.data(&["complete"]).v, stewart::json::V::Bool(true));
    // The cursor is bound to the text and the scope.
    let other = next.replace(r#""text":"xx""#, r#""text":"x""#);
    assert_eq!(l.call("search", &other).reason(), "handle_invalid");
    let narrowed = next.replace(
        r#""text":"xx","#,
        r#""text":"xx","sources":["materials/x.txt"],"#,
    );
    assert_eq!(l.call("search", &narrowed).reason(), "handle_invalid");
}

// ---------------------------------------------------------------------------
// Inputs.

#[test]
fn inputs_are_decoded_strictly() {
    let mut l = Live::new();
    let r = l.call("read", r#"{"source":"question","bogus":1}"#);
    assert_eq!(r.reason(), "input_invalid");
    assert_eq!(r.str(&["pointer"]), "/bogus");
    assert_eq!(r.str(&["rule"]), "unknown_key");
    assert_eq!(strs(&r.env, &["data", "expected"]), ["source", "start"]);
    assert!(s(&r.env, &["message"]).contains("captured before decoding"));
    let dup = format!(r#"{{"source":"question","{}":"question"}}"#, "\\u0073ource");
    assert_eq!(
        l.call("read", &dup).data(&["rule"]).as_str(),
        Some("duplicate_key")
    );
    let r = l.call("submit", r#"{"prepared":"ap1.aaaaaa","confirm":"true"}"#);
    assert_eq!(
        (r.reason(), r.str(&["pointer"])),
        ("input_invalid", "/confirm")
    );
    assert_eq!(l.call("read", r#"["question"]"#).reason(), "input_invalid");
    assert_eq!(
        l.call("read", r#"{"source":"question","start":-1}"#)
            .str(&["rule"]),
        "integer_sign"
    );
    let r = l.call("record_observation", r#"{"text":"a\u0000b"}"#);
    assert_eq!(r.str(&["rule"]), "nul");
    assert_eq!(l.call_raw(Some("list"), None).reason(), "input_invalid");
    let big = format!(r#"{{"text":"{}"}}"#, "a".repeat(4 * 1024 * 1024));
    let r = l.call("record_observation", &big);
    assert_eq!(r.reason(), "input_too_large");
    assert_eq!(r.effect("answer"), "unchanged");
    // A name no tool has, or none, is refused naming the tools.
    let r = l.call("record_criterion", "{}");
    assert_eq!(r.reason(), "tool_unknown");
    assert_eq!(s(&r.env, &["operation"]), "record_criterion");
    assert_eq!(r.str(&["tools", "3"]), "record_account");
    assert_eq!(r.effect("raw_capture"), "recorded");
    let r = l.call_raw(None, Some(b"{}"));
    assert_eq!(
        (r.reason(), s(&r.env, &["operation"])),
        ("tool_unknown", "")
    );
    assert!(r.data(&["tool"]).is_null());
    assert_eq!(l.state().revision(), 0, "no refusal recorded anything");
}

// ---------------------------------------------------------------------------
// Recording, citations and edits.

#[test]
fn citations_are_located_exactly_and_kept_apart_from_stewarts_additions() {
    let mut l = Live::new();
    let a_sha = stewart::util::sha256_hex(b"def retry():\r\n    send()\n    send()\n");
    let r = l.call(
        "record_observation",
        r#"{"text":"It sends twice.","label":"twice","citations":[{"source":"materials/a.py","start":0,"end":12},{"source":"materials/notes.txt","quote":"called twice"}]}"#,
    );
    r.ok();
    assert_eq!(r.effect("answer"), "changed");
    assert_eq!(r.str(&["id"]), "e1");
    assert_eq!(r.num(&["version"]), 1);
    assert_eq!(r.num(&["revision"]), 1);
    assert!(r.str(&["entry"]).starts_with("e1.v1."));
    assert_eq!(
        r.data(&["citations", "0"]).to_j().string(),
        format!(
            r#"{{"source":"materials/a.py","start":0,"end":12,"stewart":{{"name":"materials/a.py","sha256":"{a_sha}","lines":[1,1]}}}}"#
        )
    );
    let notes_sha = stewart::util::sha256_hex(b"retry() is called twice.\n");
    assert_eq!(
        r.data(&["citations", "1"]).to_j().string(),
        format!(
            r#"{{"source":"materials/notes.txt","quote":"called twice","stewart":{{"name":"materials/notes.txt","sha256":"{notes_sha}","range":[11,23],"lines":[1,1]}}}}"#
        )
    );
    assert_eq!(r.ex.log_record.as_deref(), Some("log/6.json"));

    let r = l.call(
        "record_limit",
        r#"{"text":"x","citations":[{"source":"materials/a.py","quote":"send()"}]}"#,
    );
    assert_eq!(r.reason(), "quote_ambiguous");
    assert_eq!(r.num(&["index"]), 0);
    assert_eq!(r.num(&["count"]), 2);
    assert_eq!(
        r.data(&["occurrences"]).to_j().string(),
        r#"[{"source":"materials/a.py","start":18,"end":24},{"source":"materials/a.py","start":29,"end":35}]"#
    );
    let r = l.call("record_limit", r#"{"text":"x","citations":[{"source":"question","start":0,"end":2},{"source":"question","quote":"absent text"}]}"#);
    assert_eq!((r.reason(), r.num(&["index"])), ("quote_not_found", 1));
    for (bad, index) in [
        (r#"[{"source":"question","start":3,"end":3}]"#, 0),
        (
            r#"[{"source":"question","start":0,"end":2},{"source":"materials/zz","start":0,"end":1}]"#,
            1,
        ),
        (
            r#"[{"source":"question","start":0,"end":2,"quote":"Iz"}]"#,
            0,
        ),
        (r#"[{"source":"question","start":0}]"#, 0),
        (r#"[{"source":"materials/u.txt","start":0,"end":2}]"#, 0),
        (r#"[{"source":"question","start":0,"end":99}]"#, 0),
    ] {
        let r = l.call(
            "record_limit",
            &format!(r#"{{"text":"x","citations":{bad}}}"#),
        );
        assert_eq!(r.reason(), "citation_invalid", "{bad}");
        assert_eq!(r.num(&["index"]), index, "{bad}");
        assert_eq!(r.effect("answer"), "unchanged");
    }
    assert_eq!(l.state().revision(), 1, "refused calls create no entry");
    // A label equal to another current entry's is noted, not refused.
    let r = l.call("record_account", r#"{"text":"","label":"twice"}"#);
    r.ok();
    assert_eq!(r.str(&["notices", "0", "reason"]), "label_duplicate");
    assert_eq!(r.str(&["id"]), "e2");
    let r = l.call(
        "record_account",
        &format!(r#"{{"text":"","label":"{}"}}"#, "x".repeat(201)),
    );
    assert_eq!(
        (r.reason(), r.str(&["pointer"])),
        ("input_invalid", "/label")
    );
}

#[test]
fn t5_a_stale_target_never_overwrites_a_newer_version() {
    let mut l = Live::new();
    l.add("record_observation", "first", "obs");
    let e2 = l.add("record_observation", "second", "obs2");
    let input = |h: &str| {
        J::obj()
            .with("entry", h)
            .with("text", "second, revised")
            .with("citations", J::Arr(vec![]))
            .with("label", "obs2")
            .string()
    };
    let r = l.call("replace", &input(&e2));
    r.ok();
    let e2v2 = r.str(&["entry"]).to_string();
    assert!(e2v2.starts_with("e2.v2."));
    assert_eq!(r.num(&["revision"]), 3);
    let r = l.call("replace", &input(&e2));
    assert_eq!(r.reason(), "stale_entry");
    assert_eq!(r.str(&["current"]), e2v2);
    assert_eq!(r.next_tools(), ["read", "replace"]);
    assert_eq!(r.effect("answer"), "unchanged");
    let r = l.call("delete", &J::obj().with("entry", e2.as_str()).string());
    assert_eq!(r.reason(), "stale_entry");
    // e2.v2 remains, in e2's place.
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.str(&["entries", "1", "entry"]), e2v2);
    let r = l.call("read", &J::obj().with("source", e2v2.as_str()).string());
    assert_eq!(r.blocks[1], "second, revised");
    assert_eq!(r.str(&["kind"]), "entry");
    assert_eq!(r.str(&["entry_kind"]), "record_observation");
    assert!(!has(r.data(&[]), "artifact_encoding"));
    // Reading the replaced version is stale too.
    let r = l.call("read", &J::obj().with("source", e2.as_str()).string());
    assert_eq!(
        (r.reason(), r.str(&["current"])),
        ("stale_entry", e2v2.as_str())
    );
}

#[test]
fn replace_requires_every_field_of_the_kind_and_delete_repeats_its_removal() {
    let mut l = Live::new();
    let e1 = l.add("record_limit", "a limit", "");
    let r = l.call(
        "replace",
        &J::obj()
            .with("entry", e1.as_str())
            .with("label", "")
            .with("text", "b")
            .string(),
    );
    assert_eq!(r.reason(), "fields_invalid");
    assert_eq!(strs(&r.env, &["data", "missing"]), ["citations"]);
    let r = l.call(
        "replace",
        &J::obj()
            .with("entry", e1.as_str())
            .with("label", "")
            .with("text", "b")
            .with("citations", J::Arr(vec![]))
            .with("base64", "AA==")
            .string(),
    );
    assert_eq!(strs(&r.env, &["data", "not_allowed"]), ["base64"]);
    let r = l.call("delete", &J::obj().with("entry", e1.as_str()).string());
    r.ok();
    assert_eq!(
        r.data(&["removed"]).to_j().string(),
        r#"{"id":"e1","version":1}"#
    );
    assert_eq!(r.num(&["revision"]), 2);
    assert_eq!(
        r.data(&["already_removed"]).v,
        stewart::json::V::Bool(false)
    );
    let again = l.call("delete", &J::obj().with("entry", e1.as_str()).string());
    again.ok();
    assert_eq!(
        again.data(&["already_removed"]).v,
        stewart::json::V::Bool(true)
    );
    assert_eq!(again.num(&["revision"]), 2);
    assert_eq!(again.effect("answer"), "unchanged");
    assert_eq!(l.state().revision(), 2, "the repeat changed nothing");
    let r = l.call("read", &J::obj().with("source", e1.as_str()).string());
    assert_eq!(r.reason(), "entry_deleted");
    let r = l.call(
        "replace",
        &J::obj()
            .with("entry", e1.as_str())
            .with("label", "")
            .string(),
    );
    assert_eq!(r.reason(), "entry_deleted");
    // The order is the order of first creation; the deleted entry is gone.
    l.add("record_account", "acc", "");
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.num(&["page", "total"]), 1);
    assert_eq!(r.str(&["entries", "0", "id"]), "e2");
}

#[test]
fn artifacts_follow_their_input_field() {
    let mut l = Live::new();
    let r = l.call(
        "record_artifact",
        r#"{"label":"bytes","base64":"AAEC/w=="}"#,
    );
    r.ok();
    assert_eq!((r.str(&["encoding"]), r.num(&["size"])), ("binary", 4));
    let bin = r.str(&["entry"]).to_string();
    let r = l.call("read", &J::obj().with("source", bin.as_str()).string());
    r.ok();
    assert_eq!(r.blocks.len(), 1);
    assert_eq!(r.str(&["base64"]), "AAEC/w==");
    assert_eq!(r.str(&["kind"]), "entry");
    assert_eq!(r.str(&["entry_kind"]), "record_artifact");
    assert_eq!(r.str(&["artifact_encoding"]), "binary");
    assert!(r.data(&["citations"]).is_null());
    assert!(!has(r.data(&[]), "encoding"));
    // Text gives utf-8 even when it could be bytes.
    let r = l.call("record_artifact", r#"{"label":"t","text":"plain"}"#);
    assert_eq!(r.str(&["encoding"]), "utf-8");
    let r = l.call("read", &J::obj().with("source", r.str(&["entry"])).string());
    assert_eq!(r.blocks[1], "plain");
    assert_eq!(r.str(&["artifact_encoding"]), "utf-8");
    assert_eq!(
        l.call(
            "record_artifact",
            r#"{"label":"t","text":"a","base64":"AA=="}"#
        )
        .reason(),
        "fields_invalid"
    );
    assert_eq!(
        l.call("record_artifact", r#"{"label":"t"}"#).reason(),
        "fields_invalid"
    );
    assert_eq!(
        l.call("record_artifact", r#"{"label":"t","base64":"AAE"}"#)
            .reason(),
        "input_invalid"
    );
    assert_eq!(
        l.call("record_artifact", r#"{"label":"","text":"a"}"#)
            .reason(),
        "input_invalid"
    );
    assert_eq!(
        l.call("record_artifact", r#"{"text":"a"}"#).str(&["rule"]),
        "missing_key"
    );
    let r = l.call(
        "replace",
        &J::obj()
            .with("entry", bin.as_str())
            .with("label", "bytes")
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
            .with("label", "bytes")
            .with("base64", "/w==")
            .string(),
    );
    r.ok();
    assert_eq!(
        (r.str(&["id"]), r.num(&["version"]), r.str(&["encoding"])),
        ("e1", 2, "binary")
    );
}

#[test]
fn an_archive_write_failure_fails_the_call_and_ends_the_placement() {
    use std::os::unix::fs::PermissionsExt;
    let mut l = Live::new();
    let payload = format!("{}/payload", l.audit_dir());
    std::fs::create_dir_all(&payload).unwrap();
    std::fs::set_permissions(&payload, std::fs::Permissions::from_mode(0o500)).unwrap();
    let r = l.call("record_account", r#"{"text":"lost"}"#);
    std::fs::set_permissions(&payload, std::fs::Permissions::from_mode(0o700)).unwrap();
    assert_eq!((r.outcome(), r.reason()), ("failed", "record_failed"));
    assert_eq!(r.effect("answer"), "unchanged");
    assert_eq!(r.effect("diagnostic"), "durable");
    assert!(has(&r.env, "causes") && !has(&r.env, "retained"));
    assert_eq!(r.ex.end, Some(End::ArchiveWriteFailed));
    assert_eq!(l.state().revision(), 0);
}

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
    assert_eq!(r.reason(), "answer_damaged");
    assert_eq!(r.str(&["entries", "0", "failure"]), "damaged");
    assert_eq!(r.ex.end, Some(End::AnswerDamaged));
    // Re-entry still lists it; digests are checked by read and prepare.
    let r = l.call("what_am_i_working_with", "{}");
    assert!(r.data(&["entries", "0", "problem"]).is_null());
}

// ---------------------------------------------------------------------------
// Re-entry.

#[test]
fn reentry_reports_recorded_facts_and_pages_by_revision() {
    let mut l = Live::new();
    let e1 = l.add("record_account", &"a".repeat(300), "acc");
    l.call(
        "record_observation",
        r#"{"text":"x","citations":[{"source":"question","quote":"zzz"}]}"#,
    );
    l.call("record_artifact", r#"{"label":"bin","base64":"AA=="}"#);
    let r = l.call(
        "replace",
        &J::obj()
            .with("entry", e1.as_str())
            .with("label", "acc")
            .with("text", "short")
            .with("citations", J::Arr(vec![]))
            .string(),
    );
    let e1v2 = r.str(&["entry"]).to_string();
    let r = l.call("what_am_i_working_with", "{}");
    r.ok();
    let d = |p: &[&str]| r.data(p).to_j().string();
    assert_eq!(r.str(&["audit"]), l.audit.id);
    assert_eq!(r.str(&["condition"]), "open");
    assert!(r.data(&["sealed_by"]).is_null());
    assert_eq!(r.num(&["revision"]), 3);
    assert_eq!(d(&["run"]), r#"{"number":1,"continuing":false}"#);
    assert_eq!(
        d(&["allowances", "turns"]),
        r#"{"used":0,"reported":0,"estimated":0,"limit":200}"#
    );
    assert_eq!(
        d(&["notices_used"]),
        r#"{"reminder":false,"near_limit":false}"#
    );
    assert_eq!(
        d(&["question"]),
        r#"{"source":"question","size":19,"lines":1}"#
    );
    assert_eq!(d(&["materials"]), r#"{"count":4,"bytes":71}"#);
    assert_eq!(
        d(&["entries", "0"]),
        format!(
            r#"{{"id":"e1","entry":"{e1v2}","kind":"record_account","label":"acc","encoding":null,"size":5,"preview":"short","preview_complete":true,"problem":null}}"#
        )
    );
    assert!(
        r.data(&["entries", "1", "preview"]).is_null(),
        "no preview of binary bytes"
    );
    assert_eq!(r.str(&["entries", "1", "encoding"]), "binary");
    // Receipts: newest first, with the target's and the result's handles.
    assert_eq!(r.str(&["receipts", "0", "action"]), "replace");
    assert_eq!(r.str(&["receipts", "0", "target"]), e1);
    assert_eq!(r.str(&["receipts", "0", "entry"]), e1v2);
    assert_eq!(r.str(&["receipts", "2", "action"]), "add");
    assert!(r.data(&["receipts", "2", "target"]).is_null());
    // The latest refusal per tool.
    assert_eq!(
        d(&["latest_refusals", "0"]),
        r#"{"run":1,"tool_use_id":"toolu_01_2","tool":"record_observation","outcome":"refused","reason":"quote_not_found","revision":1}"#
    );
    assert_eq!(
        d(&["page"]),
        r#"{"bound_revision":3,"returned":2,"total":2,"complete":true}"#
    );
    assert_eq!(r.next_tools(), ["list"]);
    assert_eq!(d(&["gaps"]), "[]");
    // An unreadable result record is a gap.
    std::fs::write(format!("{}/runs/1/result-90.json", l.audit_dir()), b"{").unwrap();
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.num(&["gaps", "0", "call"]), 90);
}

#[test]
fn reentry_pages_hold_64_entries_and_refuse_a_cursor_after_an_edit() {
    let mut l = Live::new();
    for i in 0..70 {
        l.add("record_observation", &format!("o{i}"), "");
    }
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.num(&["page", "returned"]), 64);
    assert_eq!(r.next_tools(), ["list", "what_am_i_working_with"]);
    let next = r.next_input(1);
    let r2 = l.call("what_am_i_working_with", &next);
    r2.ok();
    assert_eq!(r2.num(&["page", "returned"]), 6);
    assert_eq!(r2.str(&["entries", "0", "id"]), "e65");
    let keys: Vec<String> = match &r2.data(&[]).v {
        stewart::json::V::Obj(m) => m.iter().map(|(k, _)| k.clone()).collect(),
        _ => vec![],
    };
    assert_eq!(
        keys,
        ["entries", "page"],
        "later pages carry entries and page only"
    );
    l.add("record_limit", "edit", "");
    let r3 = l.call("what_am_i_working_with", &next);
    assert_eq!(r3.reason(), "stale_view");
    assert_eq!(r3.next_tools(), ["what_am_i_working_with"]);
    assert_eq!(
        l.call("what_am_i_working_with", r#"{"page":"pg.64.aaaaaa"}"#)
            .reason(),
        "handle_invalid"
    );
}

#[test]
fn a_continuing_placement_sees_the_whole_ledger() {
    let mut l = Live::new();
    l.add("record_account", "before", "");
    l.call(
        "record_limit",
        r#"{"text":"x","citations":[{"source":"question","quote":"nope"}]}"#,
    );
    l.continue_run();
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(
        r.data(&["run"]).to_j().string(),
        r#"{"number":2,"continuing":true}"#
    );
    assert_eq!(r.num(&["page", "total"]), 1);
    assert_eq!(r.num(&["receipts", "0", "run"]), 1);
    assert_eq!(r.num(&["latest_refusals", "0", "run"]), 1);
    // Entry IDs continue across placements.
    let r = l.call("record_account", r#"{"text":"after"}"#);
    assert_eq!(r.str(&["id"]), "e2");
}

// ---------------------------------------------------------------------------
// Prepare, submit and seal.

#[test]
fn t12_an_empty_answer_prepares_and_seals() {
    let mut l = Live::new();
    let r = l.call("prepare", "{}");
    r.ok();
    assert_eq!(
        r.data(&["notices"]).to_j().string(),
        r#"[{"reason":"answer_empty","message":"No answer entries are recorded."}]"#
    );
    assert_eq!(
        r.data(&["counts"]).to_j().string(),
        r#"{"record_account":0,"record_observation":0,"record_limit":0,"record_artifact":0}"#
    );
    let ap = r.str(&["prepared"]).to_string();
    assert!(ap.starts_with("ap1."));
    assert_eq!(r.str(&["rendering", "source"]), format!("{ap}/rendering"));
    let view = l.call(
        "read",
        &J::obj().with("source", format!("{ap}/rendering")).string(),
    );
    assert_eq!(view.blocks[1], "No answer entries recorded.\n");
    assert_eq!(view.str(&["kind"]), "view");
    assert_eq!(
        l.file("prepared/1/answer.json"),
        b"{\"schema\":\"stewart.answer/1\",\"revision\":0,\"entries\":[]}\n"
    );
    let r = l.call(
        "submit",
        &J::obj()
            .with("prepared", ap.as_str())
            .with("confirm", true)
            .string(),
    );
    r.ok();
    assert_eq!(r.effect("seal"), "recorded");
    assert!(r.ex.sealed);
    assert_eq!(r.str(&["sealer"]), "auditor");
    assert!(r.str(&["seal"]).starts_with("seal."));
    assert!(!has(r.data(&[]), "delivered"));
    assert_eq!(
        l.state().seal().unwrap().1.actor,
        stewart::bodies::Actor::Auditor
    );
}

#[test]
fn t12_missing_sections_are_noted_and_never_block() {
    let mut l = Live::open("comparison", "Which is better?\n", &[("a.txt", b"A\n")]);
    l.add("record_account", "Neither is supported.", "");
    let r = l.call("prepare", "{}");
    r.ok();
    let reasons: Vec<String> = r
        .data(&["notices"])
        .as_arr()
        .unwrap()
        .iter()
        .map(|n| format!("{}:{}", s(n, &["reason"]), s(n, &["tool"])))
        .collect();
    assert_eq!(
        reasons,
        [
            "section_unfilled:record_criterion",
            "section_unfilled:record_comparison",
            "section_unfilled:record_limit"
        ]
    );
    assert_eq!(
        r.data(&["counts"]).to_j().string(),
        r#"{"record_criterion":0,"record_comparison":0,"record_observation":0,"record_account":1,"record_limit":0,"record_artifact":0}"#
    );
    let ap = r.str(&["prepared"]).to_string();
    let r = l.call(
        "submit",
        &J::obj()
            .with("prepared", ap.as_str())
            .with("confirm", true)
            .string(),
    );
    r.ok();
}

#[test]
fn submit_answers_every_case_of_its_table() {
    let mut l = Live::new();
    l.add("record_account", "one", "");
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let submit = |confirm: bool| {
        J::obj()
            .with("prepared", ap.as_str())
            .with("confirm", confirm)
            .string()
    };
    // Dry run.
    let r = l.call("submit", &submit(false));
    r.ok();
    assert_eq!(
        r.data(&[]).to_j().string(),
        format!(
            r#"{{"dry_run":true,"revision":1,"entry_count":1,"rendering":{{"source":"{ap}/rendering","size":{}}}}}"#,
            l.file("prepared/1/answer.md").len()
        )
    );
    assert_eq!(r.effect("seal"), "none");
    // Stale after an edit.
    l.add("record_limit", "two", "");
    let r = l.call("submit", &submit(true));
    assert_eq!(r.reason(), "stale_preparation");
    assert_eq!(r.num(&["revision_now"]), 2);
    assert_eq!(r.next_tools(), ["prepare"]);
    // A prepared view stays its fixed selection after the edit.
    let v = l.call(
        "read",
        &J::obj().with("source", format!("{ap}/selection")).string(),
    );
    assert!(v.blocks[1].contains("\"revision\":1"));
    let ap2 = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let r = l.call(
        "submit",
        &J::obj()
            .with("prepared", ap2.as_str())
            .with("confirm", true)
            .string(),
    );
    r.ok();
    let seal = r.str(&["seal"]).to_string();
    assert_eq!(r.num(&["revision"]), 2);
    // The repeat returns the same seal.
    let again = l.call(
        "submit",
        &J::obj()
            .with("prepared", ap2.as_str())
            .with("confirm", true)
            .string(),
    );
    again.ok();
    assert_eq!(again.str(&["seal"]), seal);
    assert_eq!(
        again.data(&["already_sealed"]).v,
        stewart::json::V::Bool(true)
    );
    assert_eq!(again.effect("seal"), "existing");
    // After the seal, mutations refuse and name the sealer; reads still work.
    let r = l.call("record_account", r#"{"text":"late"}"#);
    assert_eq!(r.reason(), "authoring_ended");
    assert_eq!(
        (r.str(&["ended_by"]), r.str(&["sealer"]), r.str(&["seal"])),
        ("seal", "auditor", seal.as_str())
    );
    assert_eq!(r.effect("answer"), "unchanged");
    l.call("read", r#"{"source":"question"}"#).ok();
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(
        (r.str(&["condition"]), r.str(&["sealed_by"])),
        ("sealed", "auditor")
    );
    assert_eq!(
        l.call("submit", r#"{"prepared":"ap9.aaaaaa"}"#).reason(),
        "handle_invalid"
    );
}

#[test]
fn t6_close_first_ends_authoring_and_close_seals_as_manager() {
    let mut l = Live::new();
    for i in 0..7 {
        l.add("record_observation", &format!("o{i}"), "");
    }
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let close = l.request_close();
    let r = l.call(
        "submit",
        &J::obj()
            .with("prepared", ap.as_str())
            .with("confirm", true)
            .string(),
    );
    assert_eq!(r.reason(), "authoring_ended");
    assert_eq!(r.str(&["ended_by"]), "close");
    assert!(r.data(&["close_requested_at"]).as_str().is_some());
    assert!(r.data(&["seal"]).is_null() && r.data(&["sealer"]).is_null());
    assert_eq!(r.effect("seal"), "none");
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.str(&["condition"]), "closed");
    // Close seals revision 7 as manager.
    let state = l.state();
    let family = l.world.arrangement.family().unwrap();
    let p = answer::prepare(&l.audit, family, &state, close, Preparer::Manager).unwrap();
    assert_eq!(p.revision, 7);
    let s = answer::seal(&l.audit, &family.versioned_id(), &p, Sealer::Manager).unwrap();
    assert_eq!(
        (s.actor, s.revision, s.existing),
        (stewart::bodies::Actor::Manager, 7, false)
    );
    let sealed = l.state();
    let (_, rec) = sealed.seal().unwrap();
    assert!(rec.invocation.is_none());
    let r = l.call(
        "submit",
        &J::obj()
            .with("prepared", ap.as_str())
            .with("confirm", true)
            .string(),
    );
    assert_eq!(
        (r.reason(), r.str(&["sealer"])),
        ("authoring_ended", "manager")
    );
    assert_eq!(r.effect("seal"), "existing");
}

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
    match answer::seal(&l.audit, &family.versioned_id(), &p, Sealer::Manager) {
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
    let s = answer::seal(&l.audit, &family.versioned_id(), &p, Sealer::Manager).unwrap();
    let st = l.state();
    let rec = st.seal().unwrap().1;
    assert!(rec.rendering_sha256.is_none());
    let (m, _) =
        stewart::returns::load_manifest(&l.audit, &rec.manifest, &s.manifest_sha256).unwrap();
    assert_eq!(m.member_names(), ["answer.json"]);
    assert_eq!(m.unproduced[0].name, "e2");
    assert_eq!(
        m.unproduced[1].dependency.as_deref(),
        Some(&["e2".to_string()][..])
    );
}

#[test]
fn the_structured_answer_and_rendering_are_byte_exact() {
    let mut l = Live::new();
    l.call(
        "record_account",
        r#"{"text":"The retry sends twice.\nSee below.\n","label":"direct","citations":[{"source":"materials/a.py","start":14,"end":36},{"source":"materials/notes.txt","quote":"called twice"}]}"#,
    )
    .ok();
    l.call("record_observation", r#"{"text":"","citations":[{"source":"question","start":0,"end":19,"quote":"Is the retry safe?\n"}]}"#).ok();
    l.call("record_artifact", r#"{"label":"trace","text":"t1\nt2"}"#)
        .ok();
    l.call("record_artifact", r#"{"label":"raw","base64":"AP8="}"#)
        .ok();
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let fixture = |name: &str| {
        std::fs::read(
            concat!(env!("CARGO_MANIFEST_DIR"), "/tests/fixtures/answer/").to_string() + name,
        )
        .unwrap()
    };
    assert_eq!(
        String::from_utf8(l.file("prepared/1/answer.json")).unwrap(),
        String::from_utf8(fixture("answer.json")).unwrap()
    );
    assert_eq!(
        String::from_utf8(l.file("prepared/1/answer.md")).unwrap(),
        String::from_utf8(fixture("answer.md")).unwrap()
    );
    // The views serve exactly these bytes.
    let v = l.call(
        "read",
        &J::obj().with("source", format!("{ap}/selection")).string(),
    );
    assert_eq!(v.blocks[1].as_bytes(), fixture("answer.json"));
}

#[test]
fn the_run_side_refusals_are_envelopes_too() {
    let call = answer::Call {
        call: 7,
        tool_use_id: "toolu_x",
        name: Some("record_account"),
        input: Some(b"{}"),
    };
    let r = decode(answer::reused(&call, 3, 5));
    assert_eq!(
        (r.outcome(), r.reason()),
        ("refused", "invocation_id_reused")
    );
    assert_eq!(r.num(&["original_call"]), 3);
    assert_eq!(r.effect("answer"), "unchanged");
    assert_eq!(r.effect("raw_capture"), "recorded");
    assert_eq!(r.ex.revision, 5);
    let cause = stewart::reply::Cause::new("write call capture", "ENOSPC");
    let r = decode(answer::capture_failed(&call, &cause, 5));
    assert_eq!((r.outcome(), r.reason()), ("failed", "record_failed"));
    assert_eq!(r.effect("raw_capture"), "failed");
    assert_eq!(s(&r.env, &["causes", "0", "error"]), "ENOSPC");
    assert_eq!(r.ex.end, Some(End::ArchiveWriteFailed));
    let unknown = answer::Call {
        name: Some("shell"),
        ..call
    };
    let r = decode(answer::reused(&unknown, 3, 5));
    assert_eq!(s(&r.env, &["operation"]), "shell");
    assert_eq!(r.effect("raw_capture"), "recorded");
}
