//! The answer protocol at its fault points (INTERFACE Appendix C.1), driven
//! in process against a commissioned audit with a live placement.
//!
//! The independent release driver owns the answer protocol, including most
//! fault points. A case belongs here only when the driver cannot give it to
//! the development loop: no driver case reaches its fault point through the
//! auditor's tools, or its driver case runs only on Linux.
//!
//! Fault configuration is read once per process, so each case is an ignored
//! test that the runner below executes in its own process with its own
//! `STEWART_TEST_FAULT`; a case passes only if the fault fired and the
//! protocol answered it as specified.
#![cfg(feature = "fault-injection")]
// Publication closures return the crate's `Fail` by value, as the crate does.
#![allow(clippy::result_large_err)]

mod answer_support;
mod common;

use answer_support::*;
use common::*;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};
use stewart::answer::End;
use stewart::json::J;

const CASES: &[(&str, &str)] = &[
    ("case_entry_uncertain", "log.dirsync:entry=eio"),
    ("case_payload_write", "entry.payload_write=enospc"),
    ("case_manifest_write", "seal.manifest_write=eio"),
    ("case_prepared_write", "prepared.write=eio"),
    (
        "case_prepare_not_published",
        "log.publish:answer_prepared=eio",
    ),
    ("case_prepare_uncertain", "log.dirsync:answer_prepared=eio"),
    ("case_entry_after_link", "entry.after_link=pause"),
];

#[test]
fn each_fault_case_in_its_own_process() {
    for &(name, fault) in CASES {
        let dir = std::env::temp_dir().join(format!(
            "stewart-fault-{}",
            stewart::ids::random_token().unwrap()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let o = std::process::Command::new(std::env::current_exe().unwrap())
            .args([name, "--exact", "--ignored", "--test-threads=1"])
            .env("STEWART_TEST_FAULT", fault)
            .env("STEWART_TEST_FAULT_DIR", &dir)
            .env_remove("STEWART_TEST_SABOTAGE")
            .output()
            .unwrap();
        let out = String::from_utf8_lossy(&o.stdout);
        assert!(
            o.status.success() && out.contains("1 passed"),
            "{name} under {fault}:\n{out}\n{}",
            String::from_utf8_lossy(&o.stderr)
        );
        let _ = std::fs::remove_dir_all(&dir);
    }
}

fn fault_dir() -> PathBuf {
    PathBuf::from(std::env::var("STEWART_TEST_FAULT_DIR").expect("run by the runner"))
}

/// Wait for the process to pause at `spec`, run `observe`, then release it.
fn on_pause<T: Send + 'static>(
    spec: &str,
    observe: impl FnOnce() -> T + Send + 'static,
) -> std::thread::JoinHandle<T> {
    let dir = fault_dir();
    let spec = spec.to_string();
    std::thread::spawn(move || {
        let paused = dir.join(format!("{spec}.paused"));
        let start = Instant::now();
        while !paused.exists() {
            assert!(
                start.elapsed() < Duration::from_secs(30),
                "never paused at {spec}"
            );
            std::thread::sleep(Duration::from_millis(5));
        }
        let seen = observe();
        std::fs::write(dir.join(format!("{spec}.go")), b"").unwrap();
        seen
    })
}

fn kinds(audit_dir: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut n = 1;
    while let Ok(b) = std::fs::read(format!("{audit_dir}/log/{n}.json")) {
        let j = stewart::json::parse(&b).unwrap();
        out.push(s(&j, &["kind"]).to_string());
        n += 1;
    }
    out
}

fn submit(ap: &str) -> String {
    J::obj().with("prepared", ap).with("confirm", true).string()
}

/// An entry linked without a confirmed directory sync: the call fails
/// `record_failed` with the answer `unknown`, the linked entry counts in the
/// revision, and the placement ends.
#[test]
#[ignore]
fn case_entry_uncertain() {
    let mut l = Live::new();
    let r = l.call("record_account", r#"{"text":"maybe"}"#);
    assert_eq!((r.outcome(), r.reason()), ("failed", "record_failed"));
    assert_eq!(r.effect("answer"), "unknown");
    assert_eq!(r.ex.end, Some(End::ArchiveWriteFailed));
    assert_eq!(r.ex.revision, 1, "the linked entry counts");
    assert_eq!(s(&r.env, &["causes", "0", "error"]), "EIO");
}

/// A payload that cannot be written: the call fails `record_failed` with a
/// durable diagnostic, the answer is unchanged and the placement ends.
#[test]
#[ignore]
fn case_payload_write() {
    let mut l = Live::new();
    let r = l.call("record_account", r#"{"text":"lost"}"#);
    assert_eq!((r.outcome(), r.reason()), ("failed", "record_failed"));
    assert_eq!(r.effect("answer"), "unchanged");
    assert_eq!(r.effect("diagnostic"), "durable");
    assert_eq!(s(&r.env, &["causes", "0", "error"]), "ENOSPC");
    assert!(!has(&r.env, "retained"));
    assert_eq!(r.ex.end, Some(End::ArchiveWriteFailed));
    assert_eq!(l.state().revision(), 0);
}

/// A seal manifest that cannot be written: the auditor's submit fails
/// `record_failed`, no seal is recorded and the placement ends.
#[test]
#[ignore]
fn case_manifest_write() {
    let mut l = Live::new();
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let r = l.call("submit", &submit(&ap));
    assert_eq!((r.outcome(), r.reason()), ("failed", "record_failed"));
    assert_eq!(r.effect("seal"), "none");
    assert_eq!(r.ex.end, Some(End::ArchiveWriteFailed));
    assert!(l.state().seal().is_none());
}

/// A preparation that cannot be written: the auditor's prepare fails
/// `record_failed` and the placement ends.
#[test]
#[ignore]
fn case_prepared_write() {
    let mut l = Live::new();
    let r = l.call("prepare", "{}");
    assert_eq!((r.outcome(), r.reason()), ("failed", "record_failed"));
    assert_eq!(r.ex.end, Some(End::ArchiveWriteFailed));
}

/// Both prepared files survive a publication failure. A failed link leaves
/// no log record; after a failed directory sync the link can already be seen.
fn failed_preparation_publication(linked: bool) {
    let mut l = Live::new();
    let r = l.call("prepare", "{}");
    assert_eq!((r.outcome(), r.reason()), ("failed", "record_failed"));
    assert_eq!(s(&r.env, &["causes", "0", "error"]), "EIO");
    assert_eq!(r.ex.end, Some(End::ArchiveWriteFailed));
    assert!(r.ex.log_record.is_none());
    let kinds = kinds(&l.audit_dir());
    assert_eq!(
        kinds.iter().filter(|k| *k == "answer_prepared").count(),
        usize::from(linked)
    );
    assert!(!l.file("prepared/1/answer.json").is_empty());
    assert!(!l.file("prepared/1/answer.md").is_empty());
    assert_eq!(l.state().revision(), 0);
    assert!(l.state().seal().is_none());
}

#[test]
#[ignore]
fn case_prepare_not_published() {
    failed_preparation_publication(false);
}

#[test]
#[ignore]
fn case_prepare_uncertain() {
    failed_preparation_publication(true);
}

/// The `entry.after_link` point lies after the entry's link and before the
/// call's result record.
#[test]
#[ignore]
fn case_entry_after_link() {
    let mut l = Live::new();
    let dir = l.audit_dir();
    let seen = on_pause("entry.after_link", move || {
        (
            kinds(&dir).last().cloned(),
            Path::new(&format!("{dir}/runs/1/call-1.json")).exists(),
            Path::new(&format!("{dir}/runs/1/result-1.json")).exists(),
        )
    });
    l.call("record_account", r#"{"text":"linked"}"#).ok();
    let (last, call, result) = seen.join().unwrap();
    assert_eq!(
        last.as_deref(),
        Some("entry"),
        "paused after the entry was linked"
    );
    assert!(call && !result, "and before the call's result record");
}
