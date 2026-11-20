//! Delivery, close after launch and status after launch through the real
//! binary, for the boundaries the independent release driver does not reach
//! and for held-lock behavior its cases check only on Linux. States after
//! launch are built with the crate's own writers (`fixture`), and each
//! delivered package is compared with the test's own witness. Release
//! behavior: no fault or sabotage controls are set.

mod common;
mod fixture;
use common::*;
use fixture::*;
use stewart::json::{Json, V};

fn yes(v: &Json, path: &[&str]) -> bool {
    at(v, path).v == V::Bool(true)
}

fn effects(j: &Json) -> Vec<String> {
    ["run", "seal", "delivery", "closure"]
        .iter()
        .map(|k| s(j, &["effects", k]).to_string())
        .collect()
}

#[test]
fn a_stop_signal_during_the_runs_delivery_ends_the_attempt_failed() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let sealed = seal(a, 1);
    // The run's signal receiver set its flag after the seal.
    let flag = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(true));
    let d = deliver_as_run_with(a, &e.dest, Some(flag));
    assert!(d.stopped.is_none(), "the attempt's ending is recorded");
    assert_eq!(d.attempts.len(), 1);
    assert_eq!(d.attempts[0].outcome.as_deref(), Some("failed"));
    let cause = d.attempts[0].cause.as_ref().unwrap();
    assert_eq!(cause.error, "signal");
    assert!(d.attempts[0].verified_members.is_empty());
    end_run(a, 1, "sealed", None, Some(sealed.record));
    let kinds = e.log_kinds(r);
    assert_eq!(
        kinds[kinds.len() - 3..],
        ["delivery_planned", "delivery_ended", "run_ended"]
    );
    // Close continues the owed delivery with a fresh package.
    let j = close(&e, r, &[]).json();
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    assert_package(&package(&e.dest, r, 2), &sealed);
}

#[test]
fn one_invocation_plans_at_most_sixteen_attempts() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let sealed = seal(a, 1);
    end_run(a, 1, "sealed", None, Some(sealed.record));
    for n in 1..=16 {
        std::fs::create_dir(package(&e.dest, r, n)).unwrap();
    }
    let j = close(&e, r, &[]).json();
    assert_eq!(s(&j, &["data", "unfinished_reason"]), "delivery_incomplete");
    assert_eq!(s(&j, &["effects", "delivery"]), "failed");
    let planned = e
        .log_kinds(r)
        .iter()
        .filter(|k| *k == "delivery_planned")
        .count();
    assert_eq!(planned, 16);
    let j = close(&e, r, &[]).json();
    assert!(s(&j, &["data", "confirmation"]).starts_with("cf17."));
    assert_package(&package(&e.dest, r, 17), &sealed);
}

#[test]
fn a_destination_inside_the_archive_is_refused_at_delivery() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let sealed = seal(a, 1);
    std::fs::remove_dir(&e.dest).unwrap();
    deliver_as_run(a, &e.dest);
    end_run(a, 1, "sealed", None, Some(sealed.record));
    let inside = format!("{}/diag", e.audit_dir(r));
    let before = e.inventory();
    let j = close(&e, r, &["--destination", &inside]).json();
    assert_eq!(s(&j, &["data", "unfinished_reason"]), "delivery_incomplete");
    assert_eq!(
        s(&j, &["data", "delivery", "cause", "error"]),
        "location_overlap"
    );
    only_additions(&before, &e.inventory()).unwrap();
    assert!(
        !e.inventory().keys().any(|k| k.contains("stewart-return")),
        "nothing was created inside the archive"
    );
}

/// A stand-in for run A of T13: it holds the active lock (an OFD lock on
/// Linux, flock in development) from its own open file description, as a
/// run does for its whole life, and does what `on_close` says once it sees
/// `close_requested`.
fn hold_lock_until<F>(
    r: &str,
    on_close: F,
) -> (std::sync::mpsc::Receiver<()>, std::thread::JoinHandle<()>)
where
    F: FnOnce(&stewart::archive::Audit) + Send + 'static,
{
    let r = r.to_string();
    let (tx, rx) = std::sync::mpsc::channel();
    let h = std::thread::spawn(move || {
        let a = open(&r);
        let lock = a.try_lock().unwrap().expect("free");
        tx.send(()).unwrap();
        let start = std::time::Instant::now();
        while stewart::log::read(&a).close_requested().is_none() {
            assert!(start.elapsed() < std::time::Duration::from_secs(20));
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
        on_close(&a);
        drop(lock);
    });
    (rx, h)
}

#[test]
fn t13_a_held_run_stops_within_the_wait_and_close_proceeds() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let r = sc.r.clone();
    let sealed = seal(&sc.audit, 1);
    let dest = e.dest.clone();
    let record = sealed.record;
    // Run A sealed and is about to deliver when close is requested: a seal
    // alone never counts as stopped, so close waits for it.
    let (ready, h) = hold_lock_until(&r, move |a| {
        let d = stewart::delivery::deliver(
            a,
            &stewart::log::read(a),
            &stewart::delivery::Request {
                by: stewart::delivery::By::Run,
                destination: stewart::delivery::Destination::commissioned(dest),
                retries_losses_of: None,
                stop: None,
            },
        );
        assert_eq!(d.attempts[0].outcome.as_deref(), Some("verified"));
        end_run(a, 1, "sealed", None, Some(record));
    });
    ready.recv().unwrap();
    let j = status(&e, &r);
    assert_eq!(s(&j, &["data", "condition"]), "run_active");
    assert!(yes(&j, &["data", "runs", "held"]));
    assert_eq!(
        at(&j, &["data", "runs", "holder", "pid"]).as_u64(),
        Some(std::process::id() as u64)
    );

    let o = close(&e, &r, &[]);
    h.join().unwrap();
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    let j = o.json();
    assert_eq!(effects(&j), ["ended", "existing", "verified", "unfinished"]);
    // The run's delivery ended after the close request, so it awaits
    // confirmation (the differing case: delivery during versus before close).
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    let kinds = e.log_kinds(&r);
    let cr = kinds.iter().position(|k| k == "close_requested").unwrap();
    let planned = kinds.iter().position(|k| k == "delivery_planned").unwrap();
    assert!(cr < planned, "{kinds:?}");
    assert_package(&package(&e.dest, &r, 1), &sealed);
    let token = s(&j, &["data", "confirmation"]).to_string();
    let j = close(&e, &r, &["--confirm", &token]).json();
    assert_eq!(s(&j, &["data", "closure"]), "complete");
}

#[test]
fn t13_a_run_still_held_keeps_close_unfinished_until_it_is_released() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let r = sc.r.clone();
    let sealed = seal(&sc.audit, 1);
    let d = deliver_as_run(&sc.audit, &e.dest);
    assert_eq!(d.attempts[0].outcome.as_deref(), Some("verified"));
    // Run A delivered and then stopped responding (as under SIGSTOP): it
    // holds the lock and never records its ending.
    let (release_tx, release_rx) = std::sync::mpsc::channel::<()>();
    let (ready, h) = hold_lock_until(&r, move |_| {
        release_rx.recv().unwrap();
    });
    ready.recv().unwrap();
    let start = std::time::Instant::now();
    let o = close(&e, &r, &[]);
    assert!(start.elapsed() >= std::time::Duration::from_secs(29));
    release_tx.send(()).unwrap();
    h.join().unwrap();
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    let j = o.json();
    assert_eq!(
        effects(&j),
        ["still_held", "existing", "verified", "unfinished"]
    );
    assert_eq!(s(&j, &["data", "unfinished_reason"]), "run_still_held");
    assert!(yes(&j, &["data", "runs", "held"]));
    assert_eq!(
        at(&j, &["data", "holder", "pid"]).as_u64(),
        Some(std::process::id() as u64)
    );
    assert_eq!(s(&j, &["next", "0", "argv", "1"]), "close");

    // The holder is gone (the lock was released without run_ended): close
    // records its end and, since the delivery verified before close was
    // first requested, the ordinary close places it.
    let j = close(&e, &r, &[]).json();
    assert_eq!(
        s(&j, &["data", "closure"]),
        "complete",
        "{}",
        j.to_j().string()
    );
    assert_eq!(s(&j, &["data", "placement"]), "delivered_before_close");
    let kinds = e.log_kinds(&r);
    let n = kinds.iter().position(|k| k == "run_ended").unwrap() + 1;
    let ended = e.log_record(&r, n);
    assert_eq!(s(&ended, &["body", "cause"]), "process_gone");
    assert_eq!(s(&ended, &["body", "recorded_by"]), "close");
    assert_eq!(
        s(&ended, &["body", "seal"]),
        format!("log/{}.json", sealed.record)
    );
}

/// A placement that recorded a damaged ending is its own condition.
#[test]
fn a_placement_that_ended_damaged_is_its_own_condition() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    end_run(&sc.audit, 1, "damaged", None, None);
    assert_eq!(s(&status(&e, &sc.r), &["data", "condition"]), "damaged");
}

/// With a close request readable before the damage, a damaged log leaves
/// close unfinished (`log_damaged`) with every other effect unknown, and it
/// publishes nothing. (Without a readable request, closure is unknown too.)
#[test]
fn a_damaged_log_after_a_close_request_leaves_closure_unfinished() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    end_run(a, 1, "limit_reached", None, None);
    request_close(a);
    std::fs::write(format!("{}/log/99.json", e.audit_dir(r)), b"{}").unwrap();
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "log_damaged");
    assert_eq!(s(&j, &["data", "headline", "authoring", "state"]), "ended");
    assert_eq!(
        s(&j, &["data", "headline", "authoring", "ended_by"]),
        "limit"
    );
    assert_eq!(
        s(&j, &["data", "headline", "delivered", "verified"]),
        "unknown"
    );
    assert_eq!(
        s(&j, &["data", "closure", "unfinished_reason"]),
        "log_damaged"
    );
    let before = e.inventory();
    let j = close(&e, r, &[]).json();
    assert_eq!(s(&j, &["data", "unfinished_reason"]), "log_damaged");
    assert_eq!(effects(&j), ["unknown", "unknown", "unknown", "unfinished"]);
    assert_eq!(before, e.inventory(), "close published nothing");
}

#[test]
fn incomplete_usage_evidence_never_presents_partial_totals_as_complete() {
    let e = Env::new();
    let r = accepted(&e);
    let a = open(&r);
    start_run(&a, 1);
    record_turn(&a, 1, 1, 1_000, 50);
    record_turn(&a, 1, 2, 2_000, 60);
    let complete = status(&e, &r);
    assert_eq!(allowance(&complete, "turns"), (2, 2, 0));
    let record = format!("{}/runs/1/attempt-2-1.json", e.audit_dir(&r));
    let witness = std::fs::read(&record).unwrap();
    std::fs::write(&record, b"{}").unwrap();
    let before = e.inventory();
    let damaged = status(&e, &r);
    for dimension in ["turns", "input_tokens", "output_tokens"] {
        assert_eq!(
            s(&damaged, &["data", "allowances", dimension, "used"]),
            "unknown"
        );
        assert!(
            at(&damaged, &["data", "allowances", dimension, "limit"])
                .as_u64()
                .is_some()
        );
    }
    let human = e.run(&["status", &r]).text();
    assert!(human.contains("turns unknown/"), "{human}");
    assert!(human.contains("attempt-2-1.json"), "{human}");
    assert_eq!(
        before,
        e.inventory(),
        "observation does not repair the evidence"
    );
    std::fs::write(&record, &witness).unwrap();
    assert_eq!(
        allowance(&status(&e, &r), "turns"),
        allowance(&complete, "turns")
    );
}

/// The allowances of one quantity in a status reply: used, reported,
/// estimated.
fn allowance(j: &Json, k: &str) -> (u64, u64, u64) {
    let f = |part: &str| {
        at(j, &["data", "allowances", k, part])
            .as_u64()
            .unwrap_or_else(|| panic!("{k}.{part}"))
    };
    (f("used"), f("reported"), f("estimated"))
}

#[test]
fn status_counts_a_live_placement_by_its_records_and_a_gone_one_with_its_estimate() {
    let e = Env::new();
    let r = accepted(&e);
    let a = open(&r);
    start_run(&a, 1);
    // One completed turn, then request 2 captured and in flight.
    record_turn(&a, 1, 1, 1_000, 50);
    capture_request(&a, 1, 2, 16_000, 3_000);

    // Run A is live: it holds the lock from its own open file description.
    let (ready_tx, ready_rx) = std::sync::mpsc::channel::<()>();
    let (release_tx, release_rx) = std::sync::mpsc::channel::<()>();
    let r2 = r.clone();
    let h = std::thread::spawn(move || {
        let a = open(&r2);
        let lock = a.try_lock().unwrap().expect("free");
        ready_tx.send(()).unwrap();
        release_rx.recv().unwrap();
        drop(lock);
    });
    ready_rx.recv().unwrap();
    let j = status(&e, &r);
    assert_eq!(s(&j, &["data", "condition"]), "run_active");
    // The request in flight is charged when its attempt ends.
    assert_eq!(allowance(&j, "turns"), (1, 1, 0));
    assert_eq!(allowance(&j, "input_tokens"), (1_000, 1_000, 0));
    assert_eq!(allowance(&j, "output_tokens"), (50, 50, 0));

    // Its process is gone (the lock is free and run_ended is missing): the
    // in-flight request is estimated, as reconciliation will record it.
    release_tx.send(()).unwrap();
    h.join().unwrap();
    let gone = status(&e, &r);
    assert_eq!(s(&gone, &["data", "condition"]), "interrupted");
    assert_eq!(allowance(&gone, "turns"), (2, 1, 1));
    assert_eq!(allowance(&gone, "input_tokens"), (2_000, 1_000, 1_000));
    assert_eq!(allowance(&gone, "output_tokens"), (16_050, 50, 16_000));

    // Reconciliation records exactly those figures, and status then reads
    // the same totals from run_ended.
    close(&e, &r, &[]);
    let kinds = e.log_kinds(&r);
    let n = kinds.iter().position(|k| k == "run_ended").unwrap() + 1;
    let ended = e.log_record(&r, n);
    assert_eq!(s(&ended, &["body", "cause"]), "process_gone");
    let u = |k: &str, part: &str| at(&ended, &["body", "usage", k, part]).as_u64().unwrap();
    assert_eq!((u("turns", "reported"), u("turns", "estimated")), (1, 1));
    assert_eq!(
        (
            u("input_tokens", "reported"),
            u("input_tokens", "estimated")
        ),
        (1_000, 1_000)
    );
    assert_eq!(
        (
            u("output_tokens", "reported"),
            u("output_tokens", "estimated")
        ),
        (50, 16_000)
    );
    let after = status(&e, &r);
    for k in ["turns", "input_tokens", "output_tokens"] {
        assert_eq!(allowance(&after, k), allowance(&gone, k), "{k}");
    }
}

#[test]
fn status_preserves_the_recorded_stopping_message_in_every_view() {
    let e = Env::new();
    let reference = accepted(&e);
    let audit = open(&reference);
    start_run(&audit, 1);
    // Replay the recorded startup boundary: the placement exists, with zero
    // requests and no authentication or model observation.
    let message = "private launch directory has project/configuration ancestry at /project; choose a temporary_directory outside it";
    put(
        &audit,
        "run_ended",
        stewart::bodies::RunEnded {
            run: 1,
            ending: "interrupted".into(),
            cause: Some("protocol_anomaly".into()),
            recorded_by: "run".into(),
            provider: None,
            requests: 0,
            attempts: 0,
            usage: Default::default(),
            notices: vec![],
            seal: None,
            message: message.into(),
        }
        .to_j(),
    );
    for target in [vec![reference.as_str()], vec!["--archive", &e.archive]] {
        for detail in [None, Some("--details"), Some("--json")] {
            let mut args = vec!["status"];
            args.extend_from_slice(&target);
            args.extend(detail);
            let output = e.run(&args);
            assert_eq!(output.code, Some(0));
            assert!(output.text().contains(message), "{args:?}");
            assert!(output.text().contains("protocol_anomaly"), "{args:?}");
        }
    }
}

/// The accepted receipt binds the question a seal delivers. Without it, close
/// cannot make a new seal; an existing seal is still delivered, with the
/// question as a named delivery loss.
#[test]
fn losing_the_accepted_receipt_blocks_a_new_seal_but_preserves_an_existing_one() {
    for previously_sealed in [false, true] {
        let e = Env::new();
        let sc = launched_with_entries(&e);
        let r = &sc.r;
        if previously_sealed {
            let sealed = seal(&sc.audit, 1);
            end_run(&sc.audit, 1, "sealed", None, Some(sealed.record));
        } else {
            end_run(&sc.audit, 1, "ended_unsubmitted", None, None);
        }
        std::fs::remove_file(format!("{}/intake/1/receipt.json", e.audit_dir(r))).unwrap();
        let result = close(&e, r, &[]);
        let reply = result.json();
        if previously_sealed {
            assert_eq!(s(&reply, &["effects", "seal"]), "existing");
            assert_eq!(s(&reply, &["effects", "delivery"]), "verified_with_losses");
            let loss = &at(&reply, &["data", "delivery", "losses"])
                .as_arr()
                .unwrap()[0];
            assert_eq!(s(loss, &["member"]), "question.md");
            assert_eq!(s(loss, &["stage"]), "delivery");
            assert_eq!(s(loss, &["role"]), "manager_question");
            assert_eq!(s(loss, &["failure"]), "missing");
        } else {
            assert_eq!(s(&reply, &["effects", "seal"]), "none");
            assert_eq!(s(&reply, &["reason"]), "item_missing");
            assert!(s(&reply, &["message"]).contains("intake/1/receipt.json"));
            assert!(!e.log_kinds(r).iter().any(|k| k == "seal"));
        }
    }
}
