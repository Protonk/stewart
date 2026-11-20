//! Delivery and close at the failure points the independent release driver
//! does not reach (INTERFACE 9, Appendix C.1 "Delivery and close"). Built
//! only with `--features fault-injection`. States after launch come from
//! `fixture`.
#![cfg(feature = "fault-injection")]

mod common;
mod fixture;
use common::*;
use fixture::*;

fn audit_path(e: &Env, r: &str, rel: &str) -> String {
    format!("{}/{rel}", e.audit_dir(r))
}

/// An auditor seal whose placement ended without a delivery.
fn sealed_by_auditor(e: &Env) -> (Scenario, Option<Sealed>) {
    let sc = launched_with_entries(e);
    let sealed = seal(&sc.audit, 1);
    end_run(&sc.audit, 1, "sealed", None, Some(sealed.record));
    (sc, Some(sealed))
}

/// An auditor seal the run delivered before it ended.
fn delivered_by_run(e: &Env) -> (Scenario, Option<Sealed>) {
    let sc = launched_with_entries(e);
    let sealed = seal(&sc.audit, 1);
    deliver_as_run(&sc.audit, &e.dest);
    end_run(&sc.audit, 1, "sealed", None, Some(sealed.record));
    (sc, Some(sealed))
}

/// An ordinary ending: close seals as manager.
fn ended_ordinarily(e: &Env) -> (Scenario, Option<Sealed>) {
    let sc = launched_with_entries(e);
    end_run(&sc.audit, 1, "ended_unsubmitted", None, None);
    (sc, None)
}

/// The run sealed and died without delivering or recording its ending.
fn sealed_then_gone(e: &Env) -> (Scenario, Option<Sealed>) {
    let sc = launched_with_entries(e);
    let sealed = seal(&sc.audit, 1);
    (sc, Some(sealed))
}

#[test]
fn a_member_after_a_failed_write_is_not_attempted() {
    let e = Env::new();
    let (sc, _) = sealed_by_auditor(&e);
    let r = &sc.r;
    let o = close_faulted(&e, r, &[], Some("delivery.member_write:answer.md=eio"));
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    let j = o.json();
    assert_eq!(s(&j, &["effects", "delivery"]), "partial");
    assert_eq!(
        strs(&j, &["data", "delivery", "verified_members"]),
        ["manifest.json", "question.md", "answer.json"]
    );
    let unverified = at(&j, &["data", "delivery", "unverified_members"])
        .as_arr()
        .unwrap();
    assert_eq!(unverified.len(), 1, "a member not attempted is not listed");
    assert_eq!(s(&unverified[0], &["name"]), "answer.md");
    assert_eq!(s(&unverified[0], &["failure"]), "write_failed");
    assert_eq!(
        package_members(&package(&e.dest, r, 1)),
        ["answer.json", "manifest.json", "question.md"]
    );
    let ended = e.log_record(r, e.log_kinds(r).len());
    assert_eq!(
        s(&ended, &["body", "members", "4", "name"]),
        "artifact-e3.bin"
    );
    assert_eq!(
        s(&ended, &["body", "members", "4", "failure"]),
        "not_attempted"
    );
}

#[test]
fn a_delivery_stage_loss_is_retried_once_the_archive_supplies_it() {
    let e = Env::new();
    let (sc, sealed) = sealed_by_auditor(&e);
    let sealed = sealed.unwrap();
    let r = &sc.r;
    let j = close_faulted(&e, r, &[], Some("delivery.source_read:artifact-e3.bin=eio")).json();
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
    let j = close(&e, r, &[]).json();
    let second = s(&j, &["data", "confirmation"]).to_string();
    assert!(second.starts_with("cf2."), "{second}");
    assert_eq!(s(&j, &["effects", "delivery"]), "verified");
    let planned = e.log_record(r, e.log_kinds(r).len() - 1);
    assert_eq!(at(&planned, &["body", "replaces"]).as_u64(), Some(1));
    assert_package(&package(&e.dest, r, 2), &sealed);
    assert!(!package_members(&package(&e.dest, r, 1)).contains(&"artifact-e3.bin".to_string()));
    let o = close(&e, r, &["--confirm", &first]);
    assert_eq!(s(&o.json(), &["reason"]), "confirmation_mismatch");
    let j = close(&e, r, &["--confirm", &second]).json();
    assert_eq!(s(&j, &["data", "closure"]), "complete");
    assert_eq!(at(&j, &["data", "delivery", "attempt"]).as_u64(), Some(2));
}

/// A close that cannot record a step fails with `record_failed`. Its effects
/// say what this invocation established (it published `close_requested`, so
/// closure is `requested`), `retained` lists what it created and kept, and
/// a repeated close resumes from the records.
#[test]
fn a_close_that_cannot_record_states_its_effects_and_resumes() {
    struct Row {
        fault: &'static str,
        setup: fn(&Env) -> (Scenario, Option<Sealed>),
        effects: &'static [(&'static str, &'static str)],
        /// Archive-relative paths, or `{dest}/…` for a package; each
        /// retained path starts with its entry.
        retained: &'static [&'static str],
        /// Members of the resumed close's reply.
        resumed: &'static [(&'static [&'static str], &'static str)],
        /// The attempt whose package the resumed close made, if any.
        copied: Option<u64>,
    }
    let rows = [
        Row {
            fault: "close.before_closed_link=eio",
            setup: delivered_by_run,
            effects: &[
                ("closure", "requested"),
                ("seal", "existing"),
                ("delivery", "verified"),
                ("diagnostic", "durable"),
            ],
            retained: &["diag/"],
            resumed: &[
                (&["data", "closure"], "complete"),
                (&["data", "placement"], "delivered_before_close"),
            ],
            copied: None,
        },
        Row {
            fault: "log.publish:seal=eio",
            setup: ended_ordinarily,
            effects: &[("closure", "requested"), ("seal", "none")],
            retained: &["prepared/1", "seal/manifest-1.json", "diag/"],
            resumed: &[
                (&["effects", "seal"], "recorded"),
                (&["data", "unfinished_reason"], "awaiting_confirmation"),
            ],
            copied: None,
        },
        Row {
            fault: "log.publish:delivery_ended=eio",
            setup: sealed_by_auditor,
            effects: &[
                ("closure", "requested"),
                ("seal", "existing"),
                ("delivery", "unknown"),
            ],
            retained: &["delivery/1.json", "{dest}/1", "diag/"],
            resumed: &[(&["data", "unfinished_reason"], "awaiting_confirmation")],
            copied: Some(2),
        },
        Row {
            fault: "log.publish:run_ended=eio",
            setup: sealed_then_gone,
            effects: &[("closure", "requested")],
            retained: &["diag/"],
            resumed: &[
                (&["effects", "run"], "ended"),
                (&["effects", "closure"], "unfinished"),
            ],
            copied: None,
        },
    ];
    for row in rows {
        let f = row.fault;
        let e = Env::new();
        let (sc, sealed) = (row.setup)(&e);
        let r = &sc.r;
        let o = close_faulted(&e, r, &[], Some(f));
        assert_eq!(o.code, Some(4), "{f}: {}", o.text());
        let j = o.json();
        assert_eq!(s(&j, &["reason"]), "record_failed", "{f}");
        for (k, v) in row.effects {
            assert_eq!(s(&j, &["effects", k]), *v, "{f}: effects.{k}");
        }
        let retained = strs(&j, &["retained"]);
        let expected: Vec<String> = row
            .retained
            .iter()
            .map(|p| match p.strip_prefix("{dest}/") {
                Some(n) => package(&e.dest, r, n.parse().unwrap()),
                None => audit_path(&e, r, p),
            })
            .collect();
        assert_eq!(retained.len(), expected.len(), "{f}: {retained:?}");
        for (got, want) in retained.iter().zip(&expected) {
            assert!(got.starts_with(want.as_str()), "{f}: {retained:?}");
        }

        let j = close(&e, r, &[]).json();
        for (path, v) in row.resumed {
            assert_eq!(s(&j, path), *v, "{f}: {path:?}");
        }
        if let Some(n) = row.copied {
            assert_package(&package(&e.dest, r, n), sealed.as_ref().unwrap());
        }
    }
}
