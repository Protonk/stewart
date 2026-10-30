//! The answer protocol at its fault points (INTERFACE Appendix C.1),
//! including trace T6 with the pause point. Fault configuration is read once
//! per process, so each case is an ignored test that the runner below
//! executes in its own process with its own `STEWART_TEST_FAULT`; a case
//! passes only if the fault fired and the protocol answered it as specified.
#![cfg(feature = "fault-injection")]
// Publication closures return the crate's `Fail` by value, as the crate does.
#![allow(clippy::result_large_err)]

mod answer_support;
mod common;

use answer_support::*;
use common::*;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};
use stewart::answer::{self, End, Preparer, Sealer};
use stewart::json::J;

const CASES: [(&str, &str); 9] = [
    ("case_seal_uncertain", "log.dirsync:seal=eio"),
    ("case_entry_uncertain", "log.dirsync:entry=eio"),
    ("case_payload_write", "entry.payload_write=enospc"),
    ("case_payload_corrupt", "entry.payload_corrupt=corrupt"),
    ("case_manifest_write", "seal.manifest_write=eio"),
    ("case_prepared_write", "prepared.write=eio"),
    ("case_entry_after_link", "entry.after_link=pause"),
    ("case_seal_after_link", "seal.after_link=pause"),
    (
        "case_t6_submit_paused_before_its_link",
        "log.publish:seal=pause",
    ),
];

#[test]
fn each_fault_case_in_its_own_process() {
    for (name, fault) in CASES {
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

#[test]
#[ignore]
fn case_seal_uncertain() {
    let mut l = Live::new();
    l.add("record_account", "a", "");
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let r = l.call("submit", &submit(&ap));
    assert_eq!((r.outcome(), r.reason()), ("failed", "seal_uncertain"));
    assert_eq!(r.effect("seal"), "unknown");
    assert_eq!(r.effect("diagnostic"), "durable");
    assert_eq!(r.next_tools(), ["submit"]);
    assert_eq!(r.next_input(0), submit(&ap));
    assert!(!r.ex.sealed && r.ex.end.is_none());
    assert!(l.state().seal().is_some(), "the seal was linked");
    // The same submit returns the recorded seal, which the run then delivers.
    let again = l.call("submit", &submit(&ap));
    again.ok();
    assert_eq!(
        again.data(&["already_sealed"]).v,
        stewart::json::V::Bool(true)
    );
    assert!(again.ex.sealed);
}

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

#[test]
#[ignore]
fn case_payload_write() {
    let mut l = Live::new();
    let r = l.call("record_account", r#"{"text":"lost"}"#);
    assert_eq!((r.outcome(), r.reason()), ("failed", "record_failed"));
    assert_eq!(r.effect("answer"), "unchanged");
    assert_eq!(s(&r.env, &["causes", "0", "error"]), "ENOSPC");
    assert_eq!(r.ex.end, Some(End::ArchiveWriteFailed));
    assert_eq!(l.state().revision(), 0);
}

#[test]
#[ignore]
fn case_payload_corrupt() {
    let mut l = Live::new();
    let e1 = l.add("record_account", "intended", "");
    let r = l.call("read", &J::obj().with("source", e1.as_str()).string());
    assert_eq!(r.reason(), "answer_damaged");
    assert_eq!(r.ex.end, Some(End::AnswerDamaged));
}

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

#[test]
#[ignore]
fn case_prepared_write() {
    let mut l = Live::new();
    let r = l.call("prepare", "{}");
    assert_eq!((r.outcome(), r.reason()), ("failed", "record_failed"));
    assert_eq!(r.ex.end, Some(End::ArchiveWriteFailed));
}

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

#[test]
#[ignore]
fn case_seal_after_link() {
    let mut l = Live::new();
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    let dir = l.audit_dir();
    let seen = on_pause("seal.after_link", move || kinds(&dir).last().cloned());
    let r = l.call("submit", &submit(&ap));
    r.ok();
    assert_eq!(seen.join().unwrap().as_deref(), Some("seal"));
}

#[test]
#[ignore]
fn case_t6_submit_paused_before_its_link() {
    let mut l = Live::new();
    for i in 0..7 {
        l.add("record_observation", &format!("o{i}"), "");
    }
    let ap = l.call("prepare", "{}").str(&["prepared"]).to_string();
    // While the submit is paused just before its seal linkat, close records
    // its request in another writer.
    let r_ref = l.r.clone();
    let dir = l.audit_dir();
    let closer = on_pause("log.publish:seal", move || {
        let mut audit = stewart::archive::Audit::open(&r_ref).unwrap();
        audit.exe = Some(stewart::platform::Exe {
            path: audit.refile.writer_path.clone(),
            sha256: audit.refile.writer_sha256.clone(),
        });
        let body = stewart::bodies::CloseRequested {
            flags: Default::default(),
        };
        stewart::log::publish(&audit, "close_requested", |_| Ok(body.to_j()))
            .ok()
            .unwrap()
            .n
    });
    let r = l.call("submit", &submit(&ap));
    let close = closer.join().unwrap();
    assert_eq!(r.reason(), "authoring_ended");
    assert_eq!(r.str(&["ended_by"]), "close");
    assert!(r.data(&["close_requested_at"]).as_str().is_some());
    assert!(r.data(&["seal"]).is_null() && r.data(&["sealer"]).is_null());
    assert_eq!(
        kinds(&dir).last().map(String::as_str),
        Some("close_requested")
    );
    // Close then seals revision 7 as manager, and that seal names its actor.
    let state = l.state();
    let family = l.world.arrangement.family().unwrap();
    let p = answer::prepare(&l.audit, family, &state, close, Preparer::Manager).unwrap();
    let s = answer::seal(&l.audit, &family.versioned_id(), &p, Sealer::Manager).unwrap();
    assert_eq!((s.actor, s.revision), (stewart::bodies::Actor::Manager, 7));
}
