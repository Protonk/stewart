//! Each sabotage control of delivery, close and status breaks exactly its
//! property (INTERFACE Appendix C.2), so the check of that property fires.
//! These tests show the break; `delivery.rs` and `close_faults.rs` show the
//! property holding without it. Built only with `--features sabotage`.
#![cfg(feature = "sabotage")]

mod common;
mod fixture;
use common::*;
use fixture::*;
use stewart::bodies::Actor;
use stewart::json::{Json, V};

const SAB: &str = "STEWART_TEST_SABOTAGE";

fn with(e: &Env, name: &str, args: &[&str]) -> Json {
    let o = e.run_env(args, &[(SAB, name)]);
    assert!(!o.stdout.is_empty(), "{}", o.stderr);
    o.json()
}

fn package(e: &Env, r: &str, attempt: u64) -> String {
    format!(
        "{}/stewart-return-{}-{attempt:03}",
        e.dest,
        r.split(':').nth(1).unwrap()
    )
}

fn sealed_by_auditor(e: &Env) -> (Scenario, Sealed) {
    let sc = launched_with_entries(e);
    let sealed = seal(&sc.audit, Actor::Auditor, None, 1);
    end_run(&sc.audit, 1, "sealed", None, Some(sealed.record));
    (sc, sealed)
}

#[cfg(feature = "fault-injection")]
#[test]
fn skip_delivery_verification() {
    let e = Env::new();
    let (sc, sealed) = sealed_by_auditor(&e);
    let o = e.run_env(
        &["close", &sc.r, "--json"],
        &[
            (SAB, "skip_delivery_verification"),
            (
                "STEWART_TEST_FAULT",
                "delivery.member_corrupt:answer.json=corrupt",
            ),
        ],
    );
    let j = o.json();
    // The delivered bytes differ from the witness, yet the attempt is
    // recorded verified.
    assert_eq!(s(&j, &["effects", "delivery"]), "verified");
    let got = std::fs::read(format!("{}/answer.json", package(&e, &sc.r, 1))).unwrap();
    assert_ne!(got, sealed.answer);
}

#[test]
fn deliver_conversation() {
    let e = Env::new();
    let (sc, _) = sealed_by_auditor(&e);
    std::fs::write(
        format!("{}/runs/1/request-1.json", e.audit_dir(&sc.r)),
        b"{\"request\":1}\n",
    )
    .unwrap();
    let j = with(&e, "deliver_conversation", &["close", &sc.r, "--json"]);
    assert_eq!(s(&j, &["effects", "delivery"]), "verified");
    assert!(package_members(&package(&e, &sc.r, 1)).contains(&"conversation.json".to_string()));
}

#[test]
fn regenerate_rendering() {
    let e = Env::new();
    let (sc, sealed) = sealed_by_auditor(&e);
    let j = with(&e, "regenerate_rendering", &["close", &sc.r, "--json"]);
    assert_eq!(s(&j, &["effects", "delivery"]), "verified");
    let got = std::fs::read(format!("{}/answer.md", package(&e, &sc.r, 1))).unwrap();
    assert_ne!(&got, sealed.rendering.as_ref().unwrap());
}

#[test]
fn remove_partial_package() {
    let e = Env::new();
    let (sc, _) = sealed_by_auditor(&e);
    let r = &sc.r;
    // Attempt 1 cannot supply the artifact (its payload is damaged).
    let payload = format!("{}/{}", e.audit_dir(r), sc.entries[2].payload);
    let original = std::fs::read(&payload).unwrap();
    std::fs::remove_file(&payload).unwrap();
    std::fs::write(&payload, b"damaged").unwrap();
    let j = e.run(&["close", r, "--json"]).json();
    assert_eq!(s(&j, &["effects", "delivery"]), "verified_with_losses");
    assert!(std::path::Path::new(&package(&e, r, 1)).exists());
    // Restored, the next attempt retries it, and the control removes the
    // earlier package.
    std::fs::remove_file(&payload).unwrap();
    std::fs::write(&payload, &original).unwrap();
    let j = with(&e, "remove_partial_package", &["close", r, "--json"]);
    assert_eq!(s(&j, &["effects", "delivery"]), "verified");
    assert!(!std::path::Path::new(&package(&e, r, 1)).exists());
}

#[test]
fn skip_confirmation() {
    let e = Env::new();
    let (sc, _) = sealed_by_auditor(&e);
    let j = with(&e, "skip_confirmation", &["close", &sc.r, "--json"]);
    assert_eq!(s(&j, &["data", "closure"]), "complete");
}

#[test]
fn seal_as_stopped() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    seal(&sc.audit, Actor::Auditor, None, 1);
    // A run that sealed holds the audit and does not stop.
    let r = sc.r.clone();
    let (tx, rx) = std::sync::mpsc::channel::<()>();
    let (ready_tx, ready_rx) = std::sync::mpsc::channel::<()>();
    let h = std::thread::spawn(move || {
        let a = open(&r);
        let lock = a.try_lock().unwrap().expect("free");
        ready_tx.send(()).unwrap();
        rx.recv().unwrap();
        drop(lock);
    });
    ready_rx.recv().unwrap();
    let start = std::time::Instant::now();
    let j = with(&e, "seal_as_stopped", &["close", &sc.r, "--json"]);
    tx.send(()).unwrap();
    h.join().unwrap();
    assert!(start.elapsed() < std::time::Duration::from_secs(20));
    assert_eq!(s(&j, &["effects", "run"]), "ended");
}

#[test]
fn empty_return_before_launch() {
    let e = Env::new();
    let r = accepted(&e);
    let j = with(&e, "empty_return_before_launch", &["close", &r, "--json"]);
    assert_eq!(s(&j, &["data", "closure"]), "complete");
    assert!(e.log_kinds(&r).contains(&"seal".to_string()));
    assert!(std::fs::read_dir(&e.dest).unwrap().next().is_some());
}

#[test]
fn ended_as_submitted() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    end_run(&sc.audit, 1, "ended_unsubmitted", None, None);
    let j = with(&e, "ended_as_submitted", &["status", &sc.r, "--json"]);
    assert_eq!(s(&j, &["data", "headline", "sealed", "by"]), "auditor");
}

#[test]
fn seal_as_delivered() {
    let e = Env::new();
    let (sc, _) = sealed_by_auditor(&e);
    let j = with(&e, "seal_as_delivered", &["status", &sc.r, "--json"]);
    assert_eq!(
        at(&j, &["data", "headline", "delivered", "verified"]).v,
        V::Bool(true)
    );
}

#[test]
fn unknown_membership_empty() {
    let e = Env::new();
    let (sc, _) = sealed_by_auditor(&e);
    let manifest = format!("{}/seal/manifest-1.json", e.audit_dir(&sc.r));
    std::fs::remove_file(&manifest).unwrap();
    std::fs::write(&manifest, b"{}\n").unwrap();
    let j = with(&e, "unknown_membership_empty", &["close", &sc.r, "--json"]);
    assert_eq!(s(&j, &["effects", "delivery"]), "verified");
}

#[test]
fn relative_run_line() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let j = with(
        &e,
        "relative_run_line",
        &["commission", &r, &h, "--i-am-finished", "--json"],
    );
    assert!(!s(&j, &["data", "run_line", "0"]).starts_with('/'));
    let j = with(&e, "relative_run_line", &["receipt", &r, "--json"]);
    assert!(!s(&j, &["data", "run_line", "0"]).starts_with('/'));
}

#[test]
fn commission_over_network() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let args = [
        "commission",
        r.as_str(),
        h.as_str(),
        "--i-am-finished",
        "--json",
    ];
    let o = e.run_env(&args, &[(SAB, "commission_over_network")]);
    assert_eq!(s(&o.json(), &["reason"]), "provider_key_missing");
    // With a key, it reaches the provider (a listener this test opened on
    // the loopback interface) before accepting.
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let url = format!("http://127.0.0.1:{}", listener.local_addr().unwrap().port());
    listener.set_nonblocking(true).unwrap();
    let o = e.run_env(
        &args,
        &[
            (SAB, "commission_over_network"),
            ("ANTHROPIC_API_KEY", "test-key"),
            ("STEWART_PROVIDER_URL", &url),
        ],
    );
    assert_eq!(s(&o.json(), &["effects", "acceptance"]), "accepted");
    assert!(
        listener.accept().is_ok(),
        "the commission connected to the provider"
    );
}
