//! Failure traces of delivery and close at their fault points (INTERFACE 9
//! T14, Appendix C.1 "Delivery and close"). Built only with
//! `--features fault-injection`. States after launch come from `fixture`.
#![cfg(feature = "fault-injection")]

mod common;
mod fixture;
use common::*;
use fixture::*;
use stewart::bodies::Actor;
use stewart::json::{Json, V};

const FAULT: &str = "STEWART_TEST_FAULT";

fn killed(o: &Out) -> bool {
    o.code.is_none() && o.stdout.is_empty()
}

fn close_with(e: &Env, r: &str, extra: &[&str], fault: &str) -> Out {
    let mut args = vec!["close", r];
    args.extend_from_slice(extra);
    args.push("--json");
    if fault.is_empty() {
        e.run(&args)
    } else {
        e.run_env(&args, &[(FAULT, fault)])
    }
}

fn status(e: &Env, r: &str) -> Json {
    e.run(&["status", r, "--json"]).json()
}

fn package(e: &Env, r: &str, attempt: u64) -> String {
    format!(
        "{}/stewart-return-{}-{attempt:03}",
        e.dest,
        r.split(':').nth(1).unwrap()
    )
}

/// The `n`-th log record (1-based) and its kind.
fn kind_at(e: &Env, r: &str, n: usize) -> String {
    s(&e.log_record(r, n), &["kind"]).to_string()
}

/// An ordinary ending that a close sealed as manager before it stopped.
fn sealed_by_close(e: &Env) -> (Scenario, Sealed) {
    let sc = launched_with_entries(e);
    end_run(&sc.audit, 1, "ended_unsubmitted", None, None);
    let cr = request_close(&sc.audit);
    let sealed = seal(&sc.audit, Actor::Manager, Some(cr), 1);
    (sc, sealed)
}

/// An auditor seal whose placement ended without a delivery.
fn sealed_by_auditor(e: &Env) -> (Scenario, Sealed) {
    let sc = launched_with_entries(e);
    let sealed = seal(&sc.audit, Actor::Auditor, None, 1);
    end_run(&sc.audit, 1, "sealed", None, Some(sealed.record));
    (sc, sealed)
}

#[test]
fn t14_lost_close_replies_are_recovered_from_the_records() {
    let e = Env::new();
    let (sc, sealed) = sealed_by_close(&e);
    let r = &sc.r;
    let o = close_with(&e, r, &[], "delivery.after_ended=kill");
    assert!(killed(&o), "expected a kill before the reply: {}", o.text());
    let kinds = e.log_kinds(r);
    assert_eq!(
        kinds[kinds.len() - 2..],
        ["delivery_planned", "delivery_ended"]
    );
    assert_eq!(
        s(&e.log_record(r, kinds.len()), &["body", "outcome"]),
        "verified"
    );
    assert_package(&package(&e, r, 1), &sealed);

    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "awaiting_confirmation");
    let token = s(&j, &["data", "deliveries", "0", "confirmation"]).to_string();
    assert!(token.starts_with("cf1."));

    // Close from another directory: the same attempt and token, no new copy.
    let other = e.path("another-cwd");
    std::fs::create_dir(&other).unwrap();
    let o = std::process::Command::new(bin())
        .args(["close", r, "--json"])
        .current_dir(&other)
        .env_remove("STEWART_TEST_FAULT")
        .env_remove("STEWART_TEST_SABOTAGE")
        .output()
        .unwrap();
    let j = stewart::json::parse(&o.stdout).unwrap();
    assert_eq!(s(&j, &["data", "closure"]), "unfinished");
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    assert_eq!(s(&j, &["data", "confirmation"]), token);
    assert_eq!(e.log_kinds(r).len(), kinds.len(), "no new attempt");
    assert!(!std::path::Path::new(&package(&e, r, 2)).exists());

    let o = close_with(
        &e,
        r,
        &["--confirm", &token],
        "close.after_closed_link=kill",
    );
    assert!(killed(&o));
    assert_eq!(e.log_kinds(r).last().unwrap(), "closed");
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "closed");
    let j = close_with(&e, r, &[], "").json();
    assert!(at(&j, &["data", "already_closed"]).v == V::Bool(true));
    assert_eq!(s(&j, &["data", "placement"]), "confirmed");
    assert_eq!(s(&j, &["data", "outcome"]), "closed_delivered");
}

#[test]
fn a_partial_delivery_keeps_its_package_and_close_makes_a_fresh_copy() {
    let e = Env::new();
    let (sc, sealed) = sealed_by_auditor(&e);
    let r = &sc.r;
    let o = close_with(&e, r, &[], "delivery.member_write:answer.md=eio");
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    let j = o.json();
    assert_eq!(s(&j, &["effects", "delivery"]), "partial");
    assert_eq!(s(&j, &["data", "unfinished_reason"]), "delivery_incomplete");
    assert_eq!(
        strs(&j, &["data", "delivery", "verified_members"]),
        ["manifest.json", "answer.json"]
    );
    let unverified = at(&j, &["data", "delivery", "unverified_members"])
        .as_arr()
        .unwrap();
    assert_eq!(unverified.len(), 1, "a member not attempted is not listed");
    assert_eq!(s(&unverified[0], &["name"]), "answer.md");
    assert_eq!(s(&unverified[0], &["failure"]), "write_failed");
    assert_eq!(s(&j, &["data", "delivery", "cause", "error"]), "EIO");
    let first = package(&e, r, 1);
    assert_eq!(package_members(&first), ["answer.json", "manifest.json"]);
    let ended = e.log_record(r, e.log_kinds(r).len());
    assert_eq!(
        s(&ended, &["body", "members", "3", "failure"]),
        "not_attempted"
    );

    let j = close_with(&e, r, &[], "").json();
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    assert!(s(&j, &["data", "confirmation"]).starts_with("cf2."));
    assert_package(&package(&e, r, 2), &sealed);
    assert_eq!(package_members(&first), ["answer.json", "manifest.json"]);
    let planned = e.log_record(r, e.log_kinds(r).len() - 1);
    assert_eq!(at(&planned, &["body", "replaces"]).as_u64(), Some(1));
}

#[test]
fn a_kill_during_delivery_is_reconciled_and_copied_afresh() {
    let e = Env::new();
    let (sc, sealed) = sealed_by_auditor(&e);
    let r = &sc.r;
    let o = close_with(&e, r, &[], "delivery.after_member:2=kill");
    assert!(killed(&o));
    assert_eq!(e.log_kinds(r).last().unwrap(), "delivery_planned");
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "close_unfinished");
    assert_eq!(
        s(&j, &["data", "closure", "unfinished_reason"]),
        "delivery_incomplete"
    );
    assert!(at(&j, &["data", "deliveries", "0", "outcome"]).is_null());

    let j = close_with(&e, r, &[], "").json();
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    let kinds = e.log_kinds(r);
    let gone = (1..=kinds.len())
        .map(|n| e.log_record(r, n))
        .find(|j| s(j, &["kind"]) == "delivery_ended")
        .unwrap();
    assert_eq!(s(&gone, &["body", "outcome"]), "failed");
    assert_eq!(s(&gone, &["body", "cause", "error"]), "process_gone");
    assert_eq!(s(&gone, &["body", "recorded_by"]), "close");
    assert!(at(&gone, &["body", "members"]).is_null());
    assert_eq!(
        package_members(&package(&e, r, 1)),
        ["answer.json", "manifest.json"],
        "the interrupted package is kept as it was"
    );
    assert_package(&package(&e, r, 2), &sealed);
}

#[test]
fn a_member_that_does_not_read_back_makes_the_attempt_partial() {
    let e = Env::new();
    let (sc, _) = sealed_by_auditor(&e);
    let r = &sc.r;
    let j = close_with(&e, r, &[], "delivery.member_corrupt:answer.json=corrupt").json();
    assert_eq!(s(&j, &["effects", "delivery"]), "partial");
    let unverified = at(&j, &["data", "delivery", "unverified_members"])
        .as_arr()
        .unwrap();
    assert_eq!(s(&unverified[0], &["name"]), "answer.json");
    assert_eq!(s(&unverified[0], &["failure"]), "not_verified");
    assert_eq!(
        s(&j, &["data", "delivery", "cause", "operation"]),
        "verify answer.json"
    );
    assert_eq!(
        s(&j, &["data", "delivery", "cause", "error"]),
        "not_verified"
    );
}

#[test]
fn a_delivery_stage_loss_is_retried_once_the_archive_supplies_it() {
    let e = Env::new();
    let (sc, sealed) = sealed_by_auditor(&e);
    let r = &sc.r;
    let j = close_with(&e, r, &[], "delivery.source_read:artifact-e3.bin=eio").json();
    assert_eq!(s(&j, &["effects", "delivery"]), "verified_with_losses");
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    let first = s(&j, &["data", "confirmation"]).to_string();
    let loss = at(&j, &["data", "delivery", "losses", "0"]);
    assert!(s(loss, &["loss"]).starts_with("loss.artifact-e3-bin."));
    assert_eq!(s(loss, &["stage"]), "delivery");
    assert_eq!(s(loss, &["failure"]), "unreadable");
    assert_eq!(
        s(
            &j,
            &["data", "delivery", "unverified_members", "0", "failure"]
        ),
        "source_unreadable"
    );

    // The archive now reads it: close makes a new attempt that replaces it.
    let j = close_with(&e, r, &[], "").json();
    let second = s(&j, &["data", "confirmation"]).to_string();
    assert!(second.starts_with("cf2."), "{second}");
    assert_eq!(s(&j, &["effects", "delivery"]), "verified");
    let planned = e.log_record(r, e.log_kinds(r).len() - 1);
    assert_eq!(at(&planned, &["body", "replaces"]).as_u64(), Some(1));
    assert_package(&package(&e, r, 2), &sealed);
    assert!(!package_members(&package(&e, r, 1)).contains(&"artifact-e3.bin".to_string()));
    let o = close_with(&e, r, &["--confirm", &first], "");
    assert_eq!(s(&o.json(), &["reason"]), "confirmation_mismatch");
    let j = close_with(&e, r, &["--confirm", &second], "").json();
    assert_eq!(s(&j, &["data", "closure"]), "complete");
    assert_eq!(at(&j, &["data", "delivery", "attempt"]).as_u64(), Some(2));
}

#[test]
fn a_close_killed_after_its_request_continues_from_the_records() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let r = &sc.r;
    let sealed = seal(&sc.audit, Actor::Auditor, None, 1);
    std::fs::remove_dir(&e.dest).unwrap();
    deliver_as_run(&sc.audit, &e.dest);
    end_run(&sc.audit, 1, "sealed", None, Some(sealed.record));
    std::fs::create_dir(&e.dest).unwrap();
    let o = close_with(&e, r, &[], "close.after_requested=kill");
    assert!(killed(&o));
    let n = e.log_kinds(r).len();
    assert_eq!(kind_at(&e, r, n), "close_requested");
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "close_unfinished");
    assert_eq!(
        s(&j, &["data", "closure", "unfinished_reason"]),
        "delivery_incomplete"
    );
    let j = close_with(&e, r, &[], "").json();
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    assert_package(&package(&e, r, 2), &sealed);
}

#[test]
fn a_closing_record_that_cannot_be_published_leaves_close_resumable() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let r = &sc.r;
    let sealed = seal(&sc.audit, Actor::Auditor, None, 1);
    deliver_as_run(&sc.audit, &e.dest);
    end_run(&sc.audit, 1, "sealed", None, Some(sealed.record));
    let o = close_with(&e, r, &[], "close.before_closed_link=eio");
    assert_eq!(o.code, Some(4), "{}", o.text());
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "record_failed");
    // The request, the stop and the lock were established before the
    // failure, so the close stands unfinished.
    assert_eq!(s(&j, &["effects", "closure"]), "unfinished");
    assert_eq!(s(&j, &["effects", "diagnostic"]), "durable");
    let j = close_with(&e, r, &[], "").json();
    assert_eq!(s(&j, &["data", "closure"]), "complete");
    assert_eq!(s(&j, &["data", "placement"]), "delivered_before_close");
}

#[test]
fn a_close_that_fails_right_after_its_request_says_only_that() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let r = &sc.r;
    // The run sealed and died without delivering or recording its ending;
    // reconciling it fails.
    seal(&sc.audit, Actor::Auditor, None, 1);
    let o = close_with(&e, r, &[], "log.publish:run_ended=eio");
    assert_eq!(o.code, Some(4), "{}", o.text());
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "record_failed");
    assert_eq!(s(&j, &["effects", "closure"]), "requested");
    assert_eq!(e.log_kinds(r).last().unwrap(), "close_requested");
    // Repeating close reconciles the placement and continues.
    let j = close_with(&e, r, &[], "").json();
    assert_eq!(s(&j, &["effects", "closure"]), "unfinished");
    assert!(e.log_kinds(r).contains(&"run_ended".to_string()));
}
