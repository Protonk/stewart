//! Failure traces at the manager foundation's fault points (INTERFACE 9,
//! Appendix C.1). Built only with `--features fault-injection`.
#![cfg(feature = "fault-injection")]

mod common;
use common::*;

const FAULT: &str = "STEWART_TEST_FAULT";

fn killed(o: &Out) -> bool {
    o.code.is_none() && o.stdout.is_empty()
}

#[test]
fn t1_lost_commission_reply_returns_the_recorded_acceptance() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a.py", b"one")]);
    let o = e.run_env(
        &["commission", &r, &h, "--i-am-finished", "--json"],
        &[(FAULT, "commission.after_accepted_link=kill")],
    );
    assert!(killed(&o), "expected a kill before the reply: {}", o.text());
    assert_eq!(
        e.log_kinds(&r),
        ["reference", "prepared", "intake_planned", "accepted"]
    );
    let receipt_sha = s(&e.log_record(&r, 4), &["body", "receipt_sha256"]).to_string();
    // The manager edits the source; the same handle returns the recorded acceptance.
    std::fs::write(e.path("q/materials/a.py"), b"edited").unwrap();
    let o = e.commission(&r, &h);
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    assert_eq!(
        at(&j, &["data", "already_accepted"]).v,
        stewart::json::V::Bool(true)
    );
    assert_eq!(s(&j, &["data", "receipt_sha256"]), receipt_sha);
    assert_eq!(e.log_kinds(&r).len(), 4, "no new intake is planned");
    assert_eq!(
        e.run(&["receipt", &r, "--read", "materials/a.py"]).stdout,
        b"one"
    );
}

#[test]
fn t3_intake_killed_mid_copy_is_reconciled_by_the_next_commission() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a"), ("b", b"b"), ("c", b"c")]);
    let o = e.run_env(
        &["commission", &r, &h, "--i-am-finished", "--json"],
        &[(FAULT, "commission.after_capture:2=kill")],
    );
    assert!(killed(&o));
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "condition"]), "intake_failed");
    assert_eq!(
        s(&j, &["data", "evidence", "0", "fact"]),
        "intake 1 ended without acceptance"
    );
    assert_eq!(
        s(&j, &["data", "evidence", "0", "evidence"]),
        "intake_planned without outcome; lock free"
    );
    let attempt1 = format!("{}/intake/1", e.audit_dir(&r));
    let mut files: Vec<String> = std::fs::read_dir(&attempt1)
        .unwrap()
        .map(|d| d.unwrap().file_name().into_string().unwrap())
        .collect();
    files.sort();
    assert_eq!(files, ["m0001.bin", "q.bin"]);
    let o = e.commission(&r, &h);
    assert_eq!(o.code, Some(0), "{}", o.text());
    assert_eq!(
        e.log_kinds(&r),
        [
            "reference",
            "prepared",
            "intake_planned",
            "intake_ended",
            "intake_planned",
            "accepted"
        ]
    );
    assert_eq!(
        s(&e.log_record(&r, 4), &["body", "outcome"]),
        "process_gone"
    );
    assert_eq!(
        at(&e.log_record(&r, 5), &["body", "attempt"]).as_u64(),
        Some(2)
    );
    assert!(
        std::path::Path::new(&format!("{attempt1}/m0001.bin")).exists(),
        "attempt 1's files remain"
    );
}

#[test]
fn t4_uncertain_acceptance_is_reported_and_reconciled() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let o = e.run_env(
        &["commission", &r, &h, "--i-am-finished", "--json"],
        &[(FAULT, "commission.accepted_dirsync=eio")],
    );
    assert_eq!(o.code, Some(4), "{}", o.text());
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "acceptance_record_uncertain");
    assert_eq!(s(&j, &["effects", "acceptance"]), "unknown");
    assert_eq!(s(&j, &["effects", "attempt"]), "recorded");
    assert_eq!(s(&j, &["effects", "diagnostic"]), "durable");
    assert_eq!(s(&j, &["causes", "0", "operation"]), "fsync log directory");
    assert_eq!(s(&j, &["causes", "0", "error"]), "EIO");
    let retained = strs(&j, &["retained"]);
    assert!(
        retained[0].ends_with("/intake/1") && retained[1].contains("/diag/"),
        "{retained:?}"
    );
    assert_eq!(s(&j, &["next", "1", "argv", "1"]), "commission");
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "headline", "accepted"]), "yes");
    // Repeating returns the recorded acceptance; it never captures twice.
    let j = e.commission(&r, &h).json();
    assert_eq!(
        at(&j, &["data", "already_accepted"]).v,
        stewart::json::V::Bool(true)
    );
    assert!(!std::path::Path::new(&format!("{}/intake/2", e.audit_dir(&r))).exists());
}

#[test]
fn t11_a_failed_diagnostic_keeps_the_original_cause_first() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    std::fs::write(e.path("q/materials/a"), b"changed").unwrap();
    let o = e.run_env(
        &["commission", &r, &h, "--i-am-finished", "--json"],
        &[(FAULT, "diag.write=eio")],
    );
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "selection_changed");
    assert_eq!(s(&j, &["effects", "diagnostic"]), "reported_only");
    let causes = at(&j, &["causes"]).as_arr().unwrap();
    assert_eq!(s(&causes[0], &["error"]), "selection_changed");
    assert_eq!(s(&causes[1], &["operation"]), "write diagnostic");
    assert_eq!(s(&causes[1], &["error"]), "EIO");
}

#[test]
fn each_intake_failure_has_its_own_reason_and_ending() {
    for (fault, reason, outcome, code) in [
        (
            "commission.source_read:materials/b=eio",
            "source_unreadable",
            "source_unreadable",
            3,
        ),
        (
            "commission.source_read:question=eio",
            "source_unreadable",
            "source_unreadable",
            3,
        ),
        (
            "commission.capture_write=enospc",
            "capture_failed",
            "capture_failed",
            4,
        ),
        (
            "commission.capture_corrupt=corrupt",
            "capture_unverified",
            "capture_unverified",
            4,
        ),
        (
            "commission.receipt_write=eio",
            "receipt_record_failed",
            "receipt_record_failed",
            4,
        ),
        (
            "commission.before_accepted_link=eio",
            "receipt_record_failed",
            "receipt_record_failed",
            4,
        ),
        (
            "log.publish:accepted=eio",
            "receipt_record_failed",
            "receipt_record_failed",
            4,
        ),
    ] {
        let e = Env::new();
        let (r, h) = e.prepared(&[("a", b"a"), ("b", b"b")]);
        let o = e.run_env(
            &["commission", &r, &h, "--i-am-finished", "--json"],
            &[(FAULT, fault)],
        );
        assert_eq!(o.code, Some(code), "{fault}: {}", o.text());
        let j = o.json();
        assert_eq!(s(&j, &["reason"]), reason, "{fault}");
        assert_eq!(s(&j, &["effects", "acceptance"]), "absent", "{fault}");
        assert_eq!(s(&j, &["effects", "attempt"]), "partial", "{fault}");
        let kinds = e.log_kinds(&r);
        assert_eq!(
            kinds.last().map(String::as_str),
            Some("intake_ended"),
            "{fault}"
        );
        assert_eq!(
            s(&e.log_record(&r, kinds.len()), &["body", "outcome"]),
            outcome,
            "{fault}"
        );
        // The failure is retryable under the same handle once it is gone.
        let o = e.commission(&r, &h);
        assert_eq!(o.code, Some(0), "{fault}: {}", o.text());
    }
}

#[test]
fn a_reply_that_cannot_be_written_leaves_a_diagnostic() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let o = e.run_env(
        &["commission", &r, &h, "--i-am-finished", "--json"],
        &[(FAULT, "reply.write=epipe")],
    );
    assert_eq!(o.code, Some(4));
    assert!(o.stdout.is_empty());
    assert!(o.stderr.contains("could not be written"), "{}", o.stderr);
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "headline", "accepted"]), "yes");
    let diags = at(&j, &["data", "diagnostics"]).as_arr().unwrap();
    assert!(
        diags
            .iter()
            .any(|d| has(d, "operation") && s(d, &["operation"]) == "commission")
    );
}

#[test]
fn a_preparation_killed_before_its_record_is_an_unpublished_candidate() {
    let e = Env::new();
    let r = e.new_ref();
    e.fill("Q\n", &[("a", b"a")]);
    let o = e.run_env(
        &["prepare", &r, "--json"],
        &[(FAULT, "prepare.before_prepared_link=kill")],
    );
    assert!(killed(&o));
    assert_eq!(e.log_kinds(&r), ["reference"]);
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "condition"]), "preparing");
    let diags = at(&j, &["data", "diagnostics"]).as_arr().unwrap();
    assert!(
        diags.iter().any(|d| s(d, &["record"]) == "prep/1"
            && s(d, &["cause"]).starts_with("unpublished_candidate")),
        "{diags:?}"
    );
    // The next preparation claims the next number.
    let j = e.run(&["prepare", &r, "--json"]).json();
    assert!(s(&j, &["data", "prepared"]).starts_with("mp2."));
}

#[test]
fn a_killed_publication_leaves_an_unlinked_stage_file_not_a_record() {
    let e = Env::new();
    let (r, _) = e.prepared(&[("a", b"a")]);
    let o = e.run_env(
        &["close", &r, "--json"],
        &[(FAULT, "log.publish:close_requested=kill")],
    );
    assert!(killed(&o));
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "condition"]), "preparing");
    let diags = at(&j, &["data", "diagnostics"]).as_arr().unwrap();
    assert!(
        diags
            .iter()
            .any(|d| s(d, &["cause"]).starts_with("interrupted_publication")),
        "{diags:?}"
    );
    let o = e.run_env(
        &["close", &r, "--json"],
        &[(FAULT, "close.before_closed_link=eio")],
    );
    let j = o.json();
    assert_eq!(s(&j, &["outcome"]), "failed");
    assert_eq!(s(&j, &["effects", "closure"]), "unfinished");
    assert_eq!(
        s(
            &e.run(&["status", &r, "--json"]).json(),
            &["data", "condition"]
        ),
        "close_unfinished"
    );
    let j = e.run(&["close", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "closure"]), "complete");
}

fn wait_for(path: &str) {
    let start = std::time::Instant::now();
    while !std::path::Path::new(path).exists() {
        assert!(
            start.elapsed().as_secs() < 30,
            "timed out waiting for {path}"
        );
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
}

#[test]
fn close_racing_an_intake_agrees_with_it() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a"), ("b", b"b")]);
    let fdir = e.path("faults");
    std::fs::create_dir_all(&fdir).unwrap();
    let commission = {
        let mut c = std::process::Command::new(bin());
        c.args(["commission", &r, &h, "--i-am-finished", "--json"])
            .env(FAULT, "commission.after_capture:1=pause")
            .env("STEWART_TEST_FAULT_DIR", &fdir)
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null());
        c.spawn().unwrap()
    };
    wait_for(&format!("{fdir}/commission.after_capture:1.paused"));
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "condition"]), "intake_in_progress");
    // Close publishes its request, then waits for the intake holding the lock.
    let close = std::process::Command::new(bin())
        .args(["close", &r, "--json"])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .spawn()
        .unwrap();
    let start = std::time::Instant::now();
    while !e.log_kinds(&r).contains(&"close_requested".to_string()) {
        assert!(start.elapsed().as_secs() < 30);
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    std::fs::write(format!("{fdir}/commission.after_capture:1.go"), b"").unwrap();
    let c = commission.wait_with_output().unwrap();
    let cj = stewart::json::parse(&c.stdout).unwrap();
    assert_eq!(s(&cj, &["reason"]), "reference_closed");
    assert_eq!(s(&cj, &["effects", "acceptance"]), "absent");
    let k = close.wait_with_output().unwrap();
    let kj = stewart::json::parse(&k.stdout).unwrap();
    assert_eq!(s(&kj, &["data", "closure"]), "complete");
    assert_eq!(
        at(&kj, &["data", "accepted"]).v,
        stewart::json::V::Bool(false)
    );
    assert_eq!(
        e.log_kinds(&r),
        [
            "reference",
            "prepared",
            "intake_planned",
            "close_requested",
            "intake_ended",
            "closed"
        ]
    );
    assert_eq!(s(&e.log_record(&r, 5), &["body", "outcome"]), "closed");
}

#[test]
fn a_torn_stage_file_is_an_interrupted_publication_and_never_a_record() {
    let e = Env::new();
    let (r, _) = e.prepared(&[("a", b"a")]);
    let stage = format!("{}/stage", e.audit_dir(&r));
    let staged = || std::fs::read_dir(&stage).unwrap().count();
    let before = staged();
    // Armed for another kind, the point does not fire.
    let o = e.run_env(
        &["prepare", &r, "--json"],
        &[(FAULT, "stage.torn:close_requested=kill")],
    );
    assert_eq!(o.code, Some(0), "{}", o.text());
    assert_eq!(staged(), before + 1);
    // Armed for this kind, half the record is written and synced, then the
    // process dies.
    let o = e.run_env(
        &["prepare", &r, "--json"],
        &[(FAULT, "stage.torn:prepared=kill")],
    );
    assert!(killed(&o));
    assert_eq!(staged(), before + 2);
    let torn: Vec<Vec<u8>> = std::fs::read_dir(&stage)
        .unwrap()
        .map(|d| std::fs::read(d.unwrap().path()).unwrap())
        .filter(|b| stewart::json::parse(b).is_err())
        .collect();
    assert_eq!(torn.len(), 1, "exactly one stage file is torn");
    let torn = &torn[0];
    let whole = std::fs::read(format!("{}/log/3.json", e.audit_dir(&r))).unwrap();
    assert!(torn.len() * 2 <= whole.len() + 64, "about half a record");
    assert_eq!(e.log_kinds(&r), ["reference", "prepared", "prepared"]);
    let j = e.run(&["status", &r, "--json"]).json();
    let diags = at(&j, &["data", "diagnostics"]).as_arr().unwrap();
    assert_eq!(
        diags
            .iter()
            .filter(|d| s(d, &["cause"]).starts_with("interrupted_publication"))
            .count(),
        1,
        "{diags:?}"
    );
}

#[test]
fn an_unconfirmed_log_sync_is_reported_for_any_kind() {
    let e = Env::new();
    let (r, _) = e.prepared(&[("a", b"a")]);
    let o = e.run_env(
        &["close", &r, "--json"],
        &[(FAULT, "log.dirsync:close_requested=eio")],
    );
    assert_eq!(o.code, Some(4), "{}", o.text());
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "record_failed");
    assert_eq!(s(&j, &["effects", "closure"]), "unknown");
    assert_eq!(s(&j, &["causes", "0", "operation"]), "fsync log directory");
    assert_eq!(s(&j, &["causes", "0", "error"]), "EIO");
    // The record was linked; status reads it.
    assert_eq!(
        e.log_kinds(&r),
        ["reference", "prepared", "close_requested"]
    );
}
