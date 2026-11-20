//! Manager-foundation failure points the independent release driver does not
//! reach, the commission and close race on the active lock (whose driver case
//! runs only on Linux), and the fault harness's own pause and argument rules
//! (INTERFACE 9, Appendix C.1). Built only with `--features fault-injection`.
#![cfg(feature = "fault-injection")]

mod common;
use common::*;

const FAULT: &str = "STEWART_TEST_FAULT";

#[test]
fn each_intake_failure_has_its_own_reason_and_ending() {
    for (fault, reason, code) in [
        (
            "commission.source_read:question=eio",
            "source_unreadable",
            3,
        ),
        (
            "commission.before_accepted_link=eio",
            "receipt_record_failed",
            4,
        ),
        ("log.publish:accepted=eio", "receipt_record_failed", 4),
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
            reason,
            "{fault}"
        );
        // The failure is retryable under the same handle once it is gone.
        let o = e.commission(&r, &h);
        assert_eq!(o.code, Some(0), "{fault}: {}", o.text());
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
    wait_for_file(&format!("{fdir}/commission.after_capture:1.paused"));
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

/// The close request is linked but its directory sync fails: close cannot
/// say whether the request is durable, so closure is unknown, and status
/// reads the linked record.
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
    let j = e.run(&["close", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "closure"]), "complete");
}

#[test]
fn an_unconfirmed_close_request_leaves_closure_unknown() {
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
    assert_eq!(
        e.log_kinds(&r),
        ["reference", "prepared", "close_requested"]
    );
}

/// Start `close REF --json` with a pause armed in `faults`.
fn close_paused(e: &Env, r: &str, fault: &str, faults: &str) -> std::process::Child {
    std::process::Command::new(bin())
        .args(["close", r, "--json"])
        .current_dir(&e.cwd)
        .env(FAULT, fault)
        .env("STEWART_TEST_FAULT_DIR", faults)
        .env_remove("STEWART_TEST_SABOTAGE")
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap()
}

#[test]
fn a_stale_pause_file_aborts_instead_of_continuing_unpaused() {
    let e = Env::new();
    let (r, _) = e.prepared(&[("a", b"a")]);
    let faults = e.path("faults");
    std::fs::create_dir(&faults).unwrap();
    let point = "log.publish:close_requested";
    // A file left by an earlier process: the pause cannot be observed.
    let stale = format!("{faults}/{point}.paused");
    std::fs::write(&stale, b"").unwrap();
    let out = close_paused(&e, &r, &format!("{point}=pause"), &faults)
        .wait_with_output()
        .unwrap();
    assert!(out.status.code().is_none(), "the process aborts");
    assert!(out.stdout.is_empty());
    let err = String::from_utf8_lossy(&out.stderr);
    assert!(err.contains(&stale), "{err}");
    assert_eq!(
        e.log_kinds(&r),
        ["reference", "prepared"],
        "it did not continue"
    );

    // With a directory free of the point's files, the same call pauses.
    let fresh = e.path("faults-fresh");
    std::fs::create_dir(&fresh).unwrap();
    let child = close_paused(&e, &r, &format!("{point}=pause"), &fresh);
    wait_for_file(&format!("{fresh}/{point}.paused"));
    assert_eq!(
        e.log_kinds(&r),
        ["reference", "prepared"],
        "paused before the link"
    );
    std::fs::write(format!("{fresh}/{point}.go"), b"").unwrap();
    let out = child.wait_with_output().unwrap();
    assert_eq!(out.status.code(), Some(0));
    let j = stewart::json::parse(&out.stdout).unwrap();
    assert_eq!(s(&j, &["data", "closure"]), "complete");
}

#[test]
fn a_point_pauses_once_per_process() {
    // `log.publish` without an argument matches both records close publishes
    // before launch; only the first hit pauses, and the second continues
    // although its `.paused` file exists, because this process created it.
    let e = Env::new();
    let (r, _) = e.prepared(&[("a", b"a")]);
    let faults = e.path("faults");
    std::fs::create_dir(&faults).unwrap();
    let child = close_paused(&e, &r, "log.publish=pause", &faults);
    wait_for_file(&format!("{faults}/log.publish.paused"));
    std::fs::write(format!("{faults}/log.publish.go"), b"").unwrap();
    let out = child.wait_with_output().unwrap();
    assert_eq!(
        out.status.code(),
        Some(0),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert_eq!(
        e.log_kinds(&r),
        ["reference", "prepared", "close_requested", "closed"]
    );
}
