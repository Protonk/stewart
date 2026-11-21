//! `stewart run` end to end against a scripted fake provider on a loopback
//! listener (INTERFACE 5.7, section 6), on the release feature set.
//!
//! The independent release driver owns run behavior. A case belongs here
//! only when the driver cannot give it to the development loop: its driver
//! case runs only on Linux, no driver case reaches its boundary, or it pins
//! bytes or state that only the implementation knows. Cases at fault points
//! are in `run_faults.rs`, built with `fault-injection`.

mod common;
mod run_support;

use common::{Env, s};
use run_support::*;
use std::time::{Duration, Instant};

/// A second execution prepares the same empty selection again. A Messages
/// replay returns the first result without preparing or changing the answer.
#[test]
fn executed_preparations_publish_once_and_a_replay_uses_the_original() {
    let prepare = |id: &str| {
        ok(
            &format!(r#"[{{"type":"tool_use","id":"{id}","name":"prepare","input":{{}}}}]"#),
            "tool_use",
        )
    };
    let p = Provider::start(vec![
        prepare("p1"),
        prepare("p1"),
        prepare("p2"),
        text_turn("end_turn"),
        text_turn("end_turn"),
    ]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    assert_eq!(s(&o.reply, &["effects", "answer"]), "unchanged");
    assert_eq!(s(&o.reply, &["effects", "seal"]), "none");
    let kinds = e.log_kinds(&r);
    assert_eq!(kinds.iter().filter(|k| *k == "answer_prepared").count(), 2);
    let first = e.assert_empty_preparation(&r, 1, 1, "p1");
    let second = e.assert_empty_preparation(&r, 2, 3, "p2");
    assert_ne!(first, second);
    let original = record_body(&run_file(&e, &r, 1, "result-1.json"));
    let replay = record_body(&run_file(&e, &r, 1, "result-2.json"));
    assert_eq!(n(&replay, &["replay_of"]), 1);
    assert!(is_null(&replay, &["log_record"]));
    assert_eq!(
        s(&original, &["content", "0", "text"]),
        s(&replay, &["content", "0", "text"])
    );
}

/// A close requested while a request is in flight aborts it: the attempt
/// is charged an estimate, the placement ends `stopped_by_close` and run
/// refuses afterwards.
#[test]
fn close_requested_aborts_the_request_and_stops_the_run() {
    let p = Provider::start(vec![Act::Hang]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let child = run_cmd(&e, &r, &p.url(), &[]).spawn().unwrap();
    p.wait_for(1);
    let t0 = Instant::now();
    request_close(&r);
    let o = finish(child);
    assert!(t0.elapsed() < Duration::from_secs(10), "{:?}", t0.elapsed());
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    assert_eq!(s(&o.reply, &["data", "ending"]), "stopped_by_close");
    assert_eq!(s(&o.reply, &["next", "0", "argv", "1"]), "status");
    let a = attempt(&e, &r, 1, 1, 1);
    assert_eq!(s(&a, &["outcome"]), "aborted_by_close");
    assert_eq!(s(&a, &["request_written"]), "complete");
    assert_eq!(s(&a, &["charged", "basis"]), "estimated");
    assert!(is_null(&a, &["response"]));
    let kinds = e.log_kinds(&r);
    assert_eq!(kinds[kinds.len() - 2..], ["close_requested", "run_ended"]);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(s(&o.reply, &["reason"]), "reference_closed");
}

/// A signal while a request is in flight aborts it and ends the placement
/// `interrupted` with cause `signal`; run continues, carrying the aborted
/// attempt's estimate into the cumulative allowances.
#[test]
fn a_signal_interrupts_the_run_and_run_continues() {
    let p = Provider::start(vec![
        Act::Hang,
        text_turn("end_turn"),
        text_turn("end_turn"),
    ]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let child = run_cmd(&e, &r, &p.url(), &[]).spawn().unwrap();
    p.wait_for(1);
    kill(&child, libc::SIGTERM);
    let o = finish(child);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(s(&o.reply, &["data", "ending"]), "interrupted");
    assert_eq!(s(&o.reply, &["data", "cause"]), "signal");
    assert_eq!(
        s(&attempt(&e, &r, 1, 1, 1), &["outcome"]),
        "aborted_by_signal"
    );
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    assert_eq!(n(&o.reply, &["data", "run"]), 2);
    assert_eq!(s(&o.reply, &["data", "ending"]), "ended_unsubmitted");
    assert_eq!(
        n(&o.reply, &["data", "allowances", "turns", "estimated"]),
        1
    );
    assert_eq!(n(&o.reply, &["data", "allowances", "turns", "reported"]), 2);
}

/// While a placement's request is in flight its run holds the audit: a
/// second run refuses `run_held`, naming the holder, and starts nothing.
#[test]
fn a_live_placement_holds_the_run_against_another() {
    let p = Provider::start(vec![Act::Hang]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let child = run_cmd(&e, &r, &p.url(), &[]).spawn().unwrap();
    p.wait_for(1);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(3), "{}", o.stderr);
    assert_eq!(s(&o.reply, &["reason"]), "run_held");
    assert_eq!(n(&o.reply, &["data", "run"]), 1);
    assert_eq!(n(&o.reply, &["data", "holder", "pid"]), child.id() as u64);
    assert_eq!(s(&o.reply, &["effects", "run"]), "still_held");
    assert_eq!(p.requests().len(), 1, "the refused run sent nothing");
    kill(&child, libc::SIGTERM);
    let o = finish(child);
    assert_eq!(s(&o.reply, &["data", "cause"]), "signal");
}

/// A `tool_use` block without a string ID cannot be answered: it is
/// captured, nothing is executed, no later block of the response is
/// captured, and the placement ends `protocol_anomaly`.
#[test]
fn an_unanswerable_block_is_captured_and_ends_the_run() {
    let p = Provider::start(vec![ok(
        r#"[{"type":"text","text":"x"},{"type":"tool_use","id":7,"name":"list","input":{}},{"type":"tool_use","id":"t2","name":"list","input":{}}]"#,
        "tool_use",
    )]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(s(&o.reply, &["data", "cause"]), "protocol_anomaly");
    assert_eq!(
        run_file(&e, &r, 1, "call-1.json"),
        br#"{"type":"tool_use","id":7,"name":"list","input":{}}"#
    );
    let dir = format!("{}/runs/1", e.audit_dir(&r));
    assert!(!std::path::Path::new(&format!("{dir}/call-2.json")).exists());
    assert!(!std::path::Path::new(&format!("{dir}/result-1.json")).exists());
}
