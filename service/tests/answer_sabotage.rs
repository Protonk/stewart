//! Each sabotage control of the answer protocol breaks exactly its property
//! (INTERFACE Appendix C.2). A control is read once per process, so each
//! property check is an ignored test that the runner executes twice in its
//! own process: without the control it must pass (the property holds), and
//! with it it must fail (the check fires).
#![cfg(feature = "sabotage")]
// Publication closures return the crate's `Fail` by value, as the crate does.
#![allow(clippy::result_large_err)]

mod answer_support;
mod common;

use answer_support::*;
use common::*;
use stewart::answer::{self, Preparer, Sealer};
use stewart::json::J;
use stewart::usage::Usage;

/// (control, check, extra fault configuration for the run with the control).
const PAIRS: [(&str, &str, &str); 27] = [
    ("read_live_source", "check_reads_serve_the_capture", ""),
    ("normalize_read", "check_reads_keep_crlf", ""),
    ("read_truncate_silently", "check_an_early_page_says_so", ""),
    (
        "search_omit_last_page",
        "check_search_pages_until_complete",
        "",
    ),
    (
        "torn_as_entry",
        "check_unlinked_stage_files_are_not_entries",
        "",
    ),
    ("merge_equal_adds", "check_equal_adds_are_two_entries", ""),
    (
        "stale_target_overwrites",
        "check_a_stale_target_is_refused",
        "",
    ),
    (
        "manager_seal_as_auditor",
        "check_close_seals_as_manager",
        "",
    ),
    ("reentry_omit_entry", "check_reentry_lists_every_entry", ""),
    ("reentry_truncate_page", "check_reentry_pages_hold_64", ""),
    ("reentry_omit_last_page", "check_reentry_pages_hold_64", ""),
    (
        "reentry_mix_revisions",
        "check_a_stale_page_cursor_is_refused",
        "",
    ),
    (
        "reentry_placement_allowances",
        "check_reentry_allowances_are_cumulative",
        "",
    ),
    ("drop_last_entry", "check_preparation_holds_every_entry", ""),
    ("render_conclusion", "check_the_rendering_adds_nothing", ""),
    (
        "remove_superseded_payload",
        "check_superseded_payloads_stay",
        "",
    ),
    (
        "framing_task_elsewhere",
        "check_open_inquiry_pins_its_instructions",
        "",
    ),
    (
        "block_incomplete",
        "check_unfilled_sections_never_block",
        "",
    ),
    ("slow_list", "check_list_is_prompt", ""),
    (
        "fresh_ledger_on_continuation",
        "check_continuation_keeps_the_ledger",
        "",
    ),
    (
        "stale_preparation_retargets",
        "check_a_stale_submit_seals_nothing",
        "",
    ),
    ("prepare_claims_seal", "check_prepare_claims_no_seal", ""),
    ("leak_custody_path", "check_replies_carry_no_host_path", ""),
    (
        "accept_unknown_tool_field",
        "check_unknown_input_keys_are_refused",
        "",
    ),
    (
        "seal_uncertain_as_none",
        "check_an_uncertain_seal_is_unknown",
        "log.dirsync:seal=eio",
    ),
    (
        "submit_claims_delivery",
        "check_submit_claims_no_delivery",
        "",
    ),
    (
        "omit_effects_on_refusal",
        "check_refusals_carry_effects",
        "",
    ),
];

fn run_check(check: &str, control: Option<&str>, fault: &str) -> (bool, String) {
    let mut c = std::process::Command::new(std::env::current_exe().unwrap());
    c.args([check, "--exact", "--ignored", "--test-threads=1"]);
    c.env_remove("STEWART_TEST_SABOTAGE")
        .env_remove("STEWART_TEST_FAULT");
    if let Some(name) = control {
        c.env("STEWART_TEST_SABOTAGE", name);
    }
    if !fault.is_empty() {
        c.env("STEWART_TEST_FAULT", fault);
    }
    let o = c.output().unwrap();
    let out = format!(
        "{}{}",
        String::from_utf8_lossy(&o.stdout),
        String::from_utf8_lossy(&o.stderr)
    );
    (o.status.success() && out.contains("1 passed"), out)
}

#[test]
fn each_control_breaks_its_check() {
    for (control, check, fault) in PAIRS {
        if !fault.is_empty() && !cfg!(feature = "fault-injection") {
            // The check needs a fault point to fire; this build has none.
            continue;
        }
        let (held, out) = run_check(check, None, fault);
        assert!(held, "{check} fails without {control}:\n{out}");
        let (held, out) = run_check(check, Some(control), fault);
        assert!(!held, "{check} still passes under {control}:\n{out}");
        assert!(
            out.contains("1 failed"),
            "{check} under {control} did not run:\n{out}"
        );
    }
}

fn submit(ap: &str) -> String {
    J::obj().with("prepared", ap).with("confirm", true).string()
}

#[test]
#[ignore]
fn check_reads_serve_the_capture() {
    let mut l = Live::new();
    std::fs::write(
        l.e.path("q/materials/notes.txt"),
        b"rewritten after acceptance\n",
    )
    .unwrap();
    let r = l.call("read", r#"{"source":"materials/notes.txt"}"#);
    assert_eq!(r.blocks[1], "retry() is called twice.\n");
}

#[test]
#[ignore]
fn check_reads_keep_crlf() {
    let mut l = Live::new();
    let r = l.call("read", r#"{"source":"materials/a.py"}"#);
    assert!(r.blocks[1].contains("\r\n"));
}

fn long() -> Vec<u8> {
    let mut big = Vec::new();
    for i in 0..5000 {
        big.extend_from_slice(format!("line {i:05} of the long material\n").as_bytes());
    }
    big
}

#[test]
#[ignore]
fn check_an_early_page_says_so() {
    let mut l = Live::open("open-inquiry", "Q?\n", &[("big.txt", &long())]);
    let r = l.call("read", r#"{"source":"materials/big.txt"}"#);
    assert_eq!(r.data(&["complete"]).v, stewart::json::V::Bool(false));
    assert_eq!(r.next_tools(), ["read"]);
}

#[test]
#[ignore]
fn check_search_pages_until_complete() {
    let xs = vec![b'x'; 300];
    let mut l = Live::open("open-inquiry", "Q?\n", &[("x.txt", &xs)]);
    let r = l.call("search", r#"{"text":"xx"}"#);
    let r = l.call("search", &r.next_input(0));
    assert_eq!(
        r.data(&["complete"]).v,
        stewart::json::V::Bool(false),
        "page 2 of 3"
    );
    assert_eq!(r.next_tools(), ["search"]);
}

#[test]
#[ignore]
fn check_unlinked_stage_files_are_not_entries() {
    let mut l = Live::new();
    l.add("record_account", "linked", "");
    // A staged entry record that no log name holds (a lost publication).
    let entry = l.file("log/6.json");
    std::fs::write(format!("{}/stage/unlinked.json", l.audit_dir()), entry).unwrap();
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.num(&["page", "total"]), 1);
}

#[test]
#[ignore]
fn check_equal_adds_are_two_entries() {
    let mut l = Live::new();
    l.add("record_observation", "same", "x");
    let r = l.call("record_observation", r#"{"text":"same","label":"x"}"#);
    assert_eq!(r.str(&["id"]), "e2");
    assert_eq!(l.state().revision(), 2);
}

#[test]
#[ignore]
fn check_a_stale_target_is_refused() {
    let mut l = Live::new();
    let e1 = l.add("record_limit", "one", "");
    let replace = |h: &str, t: &str| {
        J::obj()
            .with("entry", h)
            .with("text", t)
            .with("citations", J::Arr(vec![]))
            .with("label", "")
            .string()
    };
    l.call("replace", &replace(&e1, "two")).ok();
    let r = l.call("replace", &replace(&e1, "three"));
    assert_eq!(r.reason(), "stale_entry");
    let r = l.call("delete", &J::obj().with("entry", e1.as_str()).string());
    assert_eq!(r.reason(), "stale_entry");
    assert_eq!(l.state().selection().len(), 1);
}

#[test]
#[ignore]
fn check_close_seals_as_manager() {
    let l = Live::new();
    let close = l.request_close();
    let state = l.state();
    let family = l.world.arrangement.family().unwrap();
    let p = answer::prepare(&l.audit, family, &state, close, Preparer::Manager).unwrap();
    answer::seal(&l.audit, &family.versioned_id(), &p, Sealer::Manager).unwrap();
    assert_eq!(
        l.state().seal().unwrap().1.actor,
        stewart::bodies::Actor::Manager
    );
}

#[test]
#[ignore]
fn check_reentry_lists_every_entry() {
    let mut l = Live::new();
    l.add("record_account", "a", "");
    l.add("record_limit", "b", "");
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.num(&["page", "total"]), 2);
    assert_eq!(r.str(&["entries", "1", "id"]), "e2");
}

#[test]
#[ignore]
fn check_reentry_pages_hold_64() {
    let mut l = Live::new();
    for i in 0..70 {
        l.add("record_observation", &format!("o{i}"), "");
    }
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.num(&["page", "returned"]), 64);
    assert_eq!(
        r.data(&["page", "complete"]).v,
        stewart::json::V::Bool(false)
    );
    let r2 = l.call("what_am_i_working_with", &r.next_input(1));
    assert_eq!(r2.num(&["page", "returned"]), 6);
}

#[test]
#[ignore]
fn check_a_stale_page_cursor_is_refused() {
    let mut l = Live::new();
    for i in 0..65 {
        l.add("record_observation", &format!("o{i}"), "");
    }
    let next = l.call("what_am_i_working_with", "{}").next_input(1);
    l.add("record_limit", "edit", "");
    assert_eq!(
        l.call("what_am_i_working_with", &next).reason(),
        "stale_view"
    );
}

#[test]
#[ignore]
fn check_reentry_allowances_are_cumulative() {
    let mut l = Live::new();
    let mut u = Usage::default();
    u.turns.reported = 3;
    u.input_tokens.estimated = 10;
    l.continue_run_with(u);
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(
        r.data(&["allowances", "turns"]).to_j().string(),
        r#"{"used":3,"reported":3,"estimated":0,"limit":200}"#
    );
    assert_eq!(r.num(&["allowances", "input_tokens", "estimated"]), 10);
}

#[test]
#[ignore]
fn check_preparation_holds_every_entry() {
    let mut l = Live::new();
    l.add("record_account", "a", "");
    l.add("record_limit", "last", "");
    let r = l.call("prepare", "{}");
    assert_eq!(r.num(&["entry_count"]), 2);
    assert!(
        String::from_utf8(l.file("prepared/1/answer.md"))
            .unwrap()
            .contains("> last")
    );
}

#[test]
#[ignore]
fn check_the_rendering_adds_nothing() {
    let mut l = Live::new();
    l.add("record_account", "Only this.", "");
    l.call("prepare", "{}").ok();
    assert_eq!(
        String::from_utf8(l.file("prepared/1/answer.md")).unwrap(),
        "Rendered by Stewart. Entry text is attributed to the auditor.\n\n## Account — e1\n\n> Only this.\n"
    );
}

#[test]
#[ignore]
fn check_superseded_payloads_stay() {
    let mut l = Live::new();
    let e1 = l.add("record_limit", "one", "");
    l.call(
        "replace",
        &J::obj()
            .with("entry", e1.as_str())
            .with("text", "two")
            .with("citations", J::Arr(vec![]))
            .with("label", "")
            .string(),
    )
    .ok();
    assert_eq!(l.file("payload/e1.v1.bin"), b"one");
}

#[test]
#[ignore]
fn check_open_inquiry_pins_its_instructions() {
    let sab = std::env::var("STEWART_TEST_SABOTAGE").unwrap_or_default();
    let l = Live::open_env(
        "open-inquiry",
        "Q?\n",
        &[("a.txt", b"a")],
        &[("STEWART_TEST_SABOTAGE", sab.as_str())],
    );
    let system = String::from_utf8(l.world.arrangement.system_raw.clone()).unwrap();
    assert!(system.contains("Address the question from the supplied materials."));
    assert!(!system.contains("Formulate a working question"));
}

#[test]
#[ignore]
fn check_unfilled_sections_never_block() {
    let mut l = Live::new();
    l.add("record_account", "a", "");
    let r = l.call("prepare", "{}");
    r.ok();
    assert_eq!(r.str(&["notices", "0", "reason"]), "section_unfilled");
}

#[test]
#[ignore]
fn check_list_is_prompt() {
    let mut l = Live::new();
    let start = std::time::Instant::now();
    l.call("list", "{}").ok();
    assert!(
        start.elapsed() < std::time::Duration::from_millis(400),
        "{:?}",
        start.elapsed()
    );
}

#[test]
#[ignore]
fn check_continuation_keeps_the_ledger() {
    let mut l = Live::new();
    l.add("record_account", "from the first run", "");
    l.continue_run();
    let r = l.call("what_am_i_working_with", "{}");
    assert_eq!(r.num(&["page", "total"]), 1);
    let r = l.call("prepare", "{}");
    assert_eq!(r.num(&["entry_count"]), 1);
}

#[test]
#[ignore]
fn check_a_stale_submit_seals_nothing() {
    let mut l = Live::new();
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    l.add("record_account", "later", "");
    assert_eq!(l.call("submit", &submit(&ap)).reason(), "stale_preparation");
    assert!(l.state().seal().is_none());
}

#[test]
#[ignore]
fn check_prepare_claims_no_seal() {
    let mut l = Live::new();
    let r = l.call("prepare", "{}");
    assert!(!has(r.data(&[]), "sealer"));
    assert!(!r.text().contains("sealer"));
}

#[test]
#[ignore]
fn check_replies_carry_no_host_path() {
    let mut l = Live::new();
    let r = l.call("read", r#"{"source":"question"}"#);
    for b in &r.blocks {
        assert!(!b.contains(&l.e.archive), "{b}");
    }
}

#[test]
#[ignore]
fn check_unknown_input_keys_are_refused() {
    let mut l = Live::new();
    let r = l.call("record_account", r#"{"text":"a","supports":true}"#);
    assert_eq!(r.reason(), "input_invalid");
    assert_eq!(l.state().revision(), 0);
}

#[test]
#[ignore]
fn check_an_uncertain_seal_is_unknown() {
    let mut l = Live::new();
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let r = l.call("submit", &submit(&ap));
    assert_eq!(r.reason(), "seal_uncertain", "the fault fired");
    assert_eq!(r.effect("seal"), "unknown");
}

#[test]
#[ignore]
fn check_submit_claims_no_delivery() {
    let mut l = Live::new();
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let r = l.call("submit", &submit(&ap));
    r.ok();
    assert!(!has(r.data(&[]), "delivered"));
}

#[test]
#[ignore]
fn check_refusals_carry_effects() {
    let mut l = Live::new();
    let r = l.call("read", r#"{"source":"materials/none"}"#);
    assert_eq!(r.reason(), "source_unknown");
    assert_eq!(r.effect("raw_capture"), "recorded");
    let r = l.call(
        "record_account",
        r#"{"text":"a","citations":[{"source":"question","quote":"nope"}]}"#,
    );
    assert_eq!(r.effect("answer"), "unchanged");
}
