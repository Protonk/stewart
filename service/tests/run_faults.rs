//! `stewart run` at its fault points (INTERFACE Appendix C.1) against a
//! scripted fake provider on a loopback listener.
//!
//! The independent release driver owns run behavior, including most fault
//! points. A case belongs here only when the driver cannot give it to the
//! development loop: no driver case reaches its fault point or boundary, or
//! it pins bytes or state that only the implementation knows.
#![cfg(feature = "fault-injection")]

mod common;
mod run_support;

use common::{Env, bin, s};
use run_support::*;
use std::time::{Duration, Instant};
use stewart::json::{self, Json};

/// A confirmed submit whose seal is not linked (`log.publish:seal=eio`)
/// fails `record_failed`, which ends the placement `archive_write_failed`;
/// the log holds no seal, so nothing is delivered and no request follows.
#[test]
fn a_seal_that_was_not_linked_is_not_delivered() {
    let p = submitting_provider();
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(
        &e,
        &r,
        &p,
        &[("STEWART_TEST_FAULT", "log.publish:seal=eio")],
    );
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(s(&o.reply, &["data", "ending"]), "interrupted");
    assert_eq!(s(&o.reply, &["data", "cause"]), "archive_write_failed");
    assert_eq!(s(&o.reply, &["effects", "seal"]), "none");
    assert_eq!(s(&o.reply, &["effects", "delivery"]), "none");
    let submit = record_body(&run_file(&e, &r, 1, "result-3.json"));
    assert_eq!(s(&submit, &["reason"]), "record_failed");
    let kinds = e.log_kinds(&r);
    assert!(
        !kinds
            .iter()
            .any(|k| k == "seal" || k.starts_with("delivery"))
    );
    assert_eq!(p.requests().len(), 2);
}

/// A request capture that cannot be written ends the placement
/// `archive_write_failed` before anything is sent. An attempt record that
/// cannot be linked does too, and its attempt is charged as an unrecorded
/// attempt is: an estimate.
#[test]
fn unwritable_captures_and_attempt_records_end_the_placement() {
    let p = Provider::start(vec![text_turn("max_tokens")]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(
        &e,
        &r,
        &p,
        &[("STEWART_TEST_FAULT", "provider.request_capture=eio")],
    );
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(s(&o.reply, &["data", "cause"]), "archive_write_failed");
    assert!(p.requests().is_empty());
    let o = run(
        &e,
        &r,
        &p,
        &[("STEWART_TEST_FAULT", "runs.publish:provider_attempt=eio")],
    );
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(s(&o.reply, &["data", "cause"]), "archive_write_failed");
    assert_eq!(n(&o.reply, &["data", "usage", "turns", "estimated"]), 1);
    assert_eq!(n(&o.reply, &["data", "usage", "turns", "reported"]), 0);
    assert_eq!(p.requests().len(), 1);
}

/// A placement whose ending cannot be recorded: the run fails
/// `record_failed` with its cause, lists the locations it created and kept,
/// and the next run records the ending as a dead placement's.
#[test]
fn an_ending_that_cannot_be_recorded_fails_with_its_cause_and_locations() {
    let p = Provider::start(vec![text_turn("max_tokens"), text_turn("max_tokens")]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(
        &e,
        &r,
        &p,
        &[("STEWART_TEST_FAULT", "log.publish:run_ended=eio")],
    );
    assert_eq!(o.code, Some(4), "{}", o.stderr);
    let j = &o.reply;
    assert_eq!(s(j, &["outcome"]), "failed");
    assert_eq!(s(j, &["reason"]), "record_failed");
    assert_eq!(s(j, &["effects", "run"]), "started");
    assert_eq!(s(j, &["causes", "0", "operation"]), "link run_ended record");
    let retained = common::strs(j, &["retained"]);
    let dir = e.audit_dir(&r);
    assert!(retained.contains(&format!("{dir}/runs/1")), "{retained:?}");
    // The unpublished record's stage file is reported by status, not listed.
    assert!(
        !retained
            .iter()
            .any(|x| x.starts_with(&format!("{dir}/stage"))),
        "{retained:?}"
    );
    assert!(
        retained
            .iter()
            .any(|x| x.starts_with(&format!("{dir}/diag/"))),
        "{retained:?}"
    );
    assert_eq!(e.log_kinds(&r).last().unwrap(), "run_started");
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    let kinds = e.log_kinds(&r);
    let first_end = kinds.iter().position(|k| k == "run_ended").unwrap() + 1;
    assert_eq!(s(&body_of(&e, &r, first_end), &["cause"]), "process_gone");
}

/// How a dead placement's run directory is left before its ending is
/// reconciled.
#[derive(Clone, Copy, Debug)]
enum RunDirectory {
    Intact,
    /// Removed, as when the process died before creating it.
    Missing,
    /// Replaced by a regular file: it exists but cannot be opened.
    Unreadable,
}

/// Placement 1 killed after its reminder was published for request 2 and
/// before that request was captured, its run directory left as `left`, then
/// reconciled by `by` (`run` or `close`). Returns that placement's
/// `run_ended` body and the raw bytes of every member both recorders
/// share, which excludes `recorded_by` and `message`.
fn reconciled_after_the_reminder(left: RunDirectory, by: &str) -> (Json, Vec<String>) {
    let p = Provider::start(vec![text_turn("end_turn"), text_turn("end_turn")]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    assert_eq!(
        run_killed(
            &e,
            &r,
            &p,
            &[("STEWART_TEST_FAULT", "run.between_turns:1=kill")]
        ),
        None
    );
    let dir = format!("{}/runs/1", e.audit_dir(&r));
    match left {
        RunDirectory::Intact => {}
        RunDirectory::Missing => std::fs::remove_dir_all(&dir).unwrap(),
        RunDirectory::Unreadable => {
            std::fs::rename(&dir, format!("{dir}.aside")).unwrap();
            std::fs::write(&dir, b"not a directory\n").unwrap();
        }
    }
    match by {
        "run" => {
            let o = run(&e, &r, &p, &[]);
            assert_eq!(o.code, Some(0), "{}", o.stderr);
        }
        _ => {
            let o = e.run(&["close", &r, "--json"]);
            assert!(o.code.is_some(), "{}", o.stderr);
        }
    }
    let kinds = e.log_kinds(&r);
    let first_end = kinds.iter().position(|k| k == "run_ended").unwrap() + 1;
    let raw = std::fs::read(format!("{}/log/{first_end}.json", e.audit_dir(&r))).unwrap();
    let record = json::parse(&raw).unwrap();
    let body = common::at(&record, &["body"]).clone();
    assert_eq!(n(&body, &["run"]), 1);
    assert_eq!(s(&body, &["cause"]), "process_gone");
    assert_eq!(s(&body, &["recorded_by"]), by);
    let shared = [
        "run", "ending", "cause", "provider", "requests", "attempts", "usage", "notices", "seal",
    ]
    .iter()
    .map(|k| {
        let v = common::at(&body, &[k]);
        String::from_utf8(raw[v.start..v.end].to_vec()).unwrap()
    })
    .collect();
    (body, shared)
}

/// A dead placement's notice is reported from what its run directory shows
/// (6.4), and run and close record the same ending apart from their names
/// and messages. A directory that exists but cannot be read shows nothing
/// about the notice: `unknown`. Differing: a directory that was never
/// created shows no request carried it, and an intact one shows its request
/// was never captured: `not_sent` either way.
#[test]
fn a_dead_placements_notice_follows_what_its_run_directory_shows() {
    for (left, sent, counts) in [
        (RunDirectory::Unreadable, "unknown", (0, 0)),
        (RunDirectory::Missing, "not_sent", (0, 0)),
        (RunDirectory::Intact, "not_sent", (1, 1)),
    ] {
        let (by_run, run_shared) = reconciled_after_the_reminder(left, "run");
        let (by_close, close_shared) = reconciled_after_the_reminder(left, "close");
        for ended in [&by_run, &by_close] {
            assert_eq!(s(ended, &["notices", "0", "type"]), "reminder", "{left:?}");
            assert_eq!(s(ended, &["notices", "0", "sent"]), sent, "{left:?}");
            assert_eq!(
                (n(ended, &["requests"]), n(ended, &["attempts"])),
                counts,
                "{left:?}"
            );
            if let RunDirectory::Unreadable = left {
                assert_eq!(s(ended, &["notices", "0", "record"]), "log/6.json");
                assert_eq!(n(ended, &["usage", "turns", "estimated"]), 0);
                assert!(
                    s(ended, &["message"]).contains("runs/1 cannot be opened"),
                    "{}",
                    s(ended, &["message"])
                );
            }
        }
        assert_eq!(run_shared, close_shared, "{left:?}");
    }
}

/// A reply's bytes with this test's own locations and reference replaced
/// by fixed names, so that the rest compares byte for byte.
fn normalized(e: &Env, r: &str, stdout: &[u8]) -> String {
    String::from_utf8(stdout.to_vec())
        .unwrap()
        .replace(r, "<ref>")
        .replace(bin(), "<bin>")
        .replace(&e.audit_dir(r), "<audit>")
        .replace(e.base.to_str().unwrap(), "<base>")
}

/// Wait up to 30 seconds for `path` to exist.
fn appears(path: &str) -> bool {
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(30) {
        if std::path::Path::new(path).exists() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    false
}

/// Run's start reservation (5.7) reports what it linked. A `run_started`
/// that was not linked started nothing: `failed`, `effects.run`
/// `not_started`. One linked without confirmed durability may stand:
/// `failed`, `effects.run` `unknown`, and the next run reconciles that
/// placement as gone before starting another. A close that wins the
/// reservation's log slot leaves nothing started: `refused`
/// `reference_closed`, with the data and next calls the state check gives
/// that reason. The replies are pinned byte for byte, apart from this
/// test's locations and reference.
#[test]
fn a_start_reservation_reports_what_it_linked() {
    let p = Provider::start(vec![text_turn("max_tokens")]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let faulted = |fault: &str| {
        let o = run_cmd(&e, &r, &p.url(), &[("STEWART_TEST_FAULT", fault)])
            .output()
            .unwrap();
        (o.status.code(), normalized(&e, &r, &o.stdout))
    };
    let (code, reply) = faulted("log.publish:run_started=eio");
    assert_eq!((code, reply.as_str()), (Some(4), NOT_LINKED), "{reply}");
    assert!(!e.log_kinds(&r).iter().any(|k| k == "run_started"));
    let (code, reply) = faulted("log.dirsync:run_started=eio");
    assert_eq!((code, reply.as_str()), (Some(4), UNCONFIRMED), "{reply}");
    assert_eq!(e.log_kinds(&r)[4..], ["run_started"]);
    assert!(!std::path::Path::new(&format!("{}/runs/1", e.audit_dir(&r))).exists());
    assert!(p.requests().is_empty());
    // The linked placement is reconciled as gone; the next one is placement 2.
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(n(&o.reply, &["data", "run"]), 2);
    assert_eq!(
        e.log_kinds(&r)[4..],
        ["run_started", "run_ended", "run_started", "run_ended"]
    );
    let gone = body_of(&e, &r, 6);
    assert_eq!(
        (
            n(&gone, &["run"]),
            s(&gone, &["cause"]),
            s(&gone, &["recorded_by"])
        ),
        (1, "process_gone", "run")
    );

    // A close that is linked while the reservation waits to link.
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let faults = e.path("faults");
    std::fs::create_dir(&faults).unwrap();
    let child = run_cmd(
        &e,
        &r,
        &p.url(),
        &[
            ("STEWART_TEST_FAULT", "log.publish:run_started=pause"),
            ("STEWART_TEST_FAULT_DIR", &faults),
        ],
    )
    .spawn()
    .unwrap();
    assert!(appears(&format!("{faults}/log.publish:run_started.paused")));
    request_close(&r);
    std::fs::write(format!("{faults}/log.publish:run_started.go"), b"").unwrap();
    let o = child.wait_with_output().unwrap();
    let reply = normalized(&e, &r, &o.stdout);
    assert_eq!(
        (o.status.code(), reply.as_str()),
        (Some(3), CLOSE_WON),
        "{reply}"
    );
    assert_eq!(e.log_kinds(&r)[4..], ["close_requested"]);
    assert_eq!(
        p.requests().len(),
        1,
        "only the continuation above reached the provider"
    );
}

const NOT_LINKED: &str = concat!(
    r#"{"schema":"stewart.reply/3","operation":"run","outcome":"failed","reason":"record_failed","message":"run_started could not be recorded, so no placement started.","effects":{"run":"not_started","answer":"unchanged","seal":"none","delivery":"none","diagnostic":"durable"},"retained":["<audit>/diag/1.json"],"causes":[{"operation":"link run_started record","error":"EIO"}],"next":[]}"#,
    "\n"
);
const UNCONFIRMED: &str = concat!(
    r#"{"schema":"stewart.reply/3","operation":"run","outcome":"failed","reason":"record_failed","message":"run_started was linked as log/5.json but its durability could not be confirmed; the run did not continue.","effects":{"run":"unknown","answer":"unchanged","seal":"none","delivery":"none","diagnostic":"durable"},"retained":["<audit>/diag/2.json"],"causes":[{"operation":"fsync log directory","error":"EIO"}],"next":[{"argv":["<bin>","status","<ref>"],"why":"See where the audit stands."}]}"#,
    "\n"
);
const CLOSE_WON: &str = concat!(
    r#"{"schema":"stewart.reply/3","operation":"run","outcome":"refused","reason":"reference_closed","message":"Close was requested (log/5.json), so no run can start.","effects":{"run":"not_started","answer":"unchanged","seal":"none","delivery":"none","diagnostic":"durable"},"retained":["<audit>/diag/1.json"],"next":[{"argv":["<bin>","close","<ref>"],"why":"Continue the close."},{"argv":["<bin>","status","<ref>"],"why":"See where the audit stands."}],"data":{"record":"log/5.json"}}"#,
    "\n"
);
