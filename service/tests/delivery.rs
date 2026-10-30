//! Delivery, close after launch and status after launch, through the real
//! binary (release behavior; no fault or sabotage controls are set). States
//! after launch are built with the crate's own writers (`fixture`); each
//! delivered package is compared against the test's own witness.

mod common;
mod fixture;
use common::*;
use fixture::*;
use stewart::bodies::Actor;
use stewart::json::{Json, V};

fn close(e: &Env, r: &str, extra: &[&str]) -> Out {
    let mut args = vec!["close", r];
    args.extend_from_slice(extra);
    args.push("--json");
    e.run(&args)
}

fn status(e: &Env, r: &str) -> Json {
    let o = e.run(&["status", r, "--json"]);
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    o.json()
}

fn yes(v: &Json, path: &[&str]) -> bool {
    at(v, path).v == V::Bool(true)
}

fn no(v: &Json, path: &[&str]) -> bool {
    at(v, path).v == V::Bool(false)
}

fn null(v: &Json, path: &[&str]) -> bool {
    at(v, path).is_null()
}

fn effects(j: &Json) -> Vec<String> {
    ["run", "seal", "delivery", "closure"]
        .iter()
        .map(|k| s(j, &["effects", k]).to_string())
        .collect()
}

fn id_of(r: &str) -> String {
    r.split(':').nth(1).unwrap().to_string()
}

fn package(dest: &str, r: &str, attempt: u64) -> String {
    format!("{dest}/stewart-return-{}-{attempt:03}", id_of(r))
}

/// The argv of next call `i`, joined by spaces.
fn next_argv(j: &Json, i: usize) -> String {
    strs(j, &["next", &i.to_string(), "argv"]).join(" ")
}

#[test]
fn t8_an_ordinary_ending_is_sealed_by_the_manager_delivered_and_confirmed() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    end_run(a, 1, "ended_unsubmitted", None, None);

    // Status after the ordinary ending: no seal, no auditor conclusion.
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "ended_unsubmitted");
    assert_eq!(s(&j, &["data", "headline", "sealed", "by"]), "none");
    assert_eq!(s(&j, &["data", "headline", "launched"]), "yes");
    assert!(no(&j, &["data", "headline", "delivered", "verified"]));
    assert_eq!(at(&j, &["data", "runs", "count"]).as_u64(), Some(1));
    assert_eq!(
        s(&j, &["data", "runs", "last", "ending"]),
        "ended_unsubmitted"
    );
    assert!(no(&j, &["data", "runs", "held"]));
    assert_eq!(
        at(&j, &["data", "allowances", "turns", "used"]).as_u64(),
        Some(4)
    );
    assert_eq!(
        at(&j, &["data", "allowances", "turns", "estimated"]).as_u64(),
        Some(1)
    );
    assert_eq!(at(&j, &["data", "answer", "revision"]).as_u64(), Some(3));
    assert_eq!(at(&j, &["data", "answer", "entries"]).as_u64(), Some(3));
    assert!(null(&j, &["data", "closure"]));
    assert_eq!(s(&j, &["next", "0", "argv", "1"]), "close");

    // A close that sealed and then stopped before delivering (the manager
    // seal is written by the fixture, as close would).
    let cr = request_close(a);
    let sealed = seal(a, Actor::Manager, Some(cr), 1);
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "close_unfinished");
    assert_eq!(
        s(&j, &["data", "closure", "unfinished_reason"]),
        "delivery_incomplete"
    );
    assert_eq!(s(&j, &["data", "headline", "sealed", "by"]), "manager");

    let before = e.inventory();
    let o = close(&e, r, &[]);
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    let j = o.json();
    assert_eq!(effects(&j), ["ended", "existing", "verified", "unfinished"]);
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    let token = s(&j, &["data", "confirmation"]).to_string();
    assert!(token.starts_with("cf1."), "{token}");
    assert_eq!(
        s(&j, &["data", "delivery", "location"]),
        package(&e.dest, r, 1)
    );
    assert_eq!(
        strs(&j, &["data", "delivery", "verified_members"]),
        [
            "manifest.json",
            "answer.json",
            "answer.md",
            "artifact-e3.bin"
        ]
    );
    assert_eq!(s(&j, &["data", "seal", "actor"]), "manager");
    assert_eq!(s(&j, &["data", "runs", "last_ending"]), "ended_unsubmitted");
    assert!(null(&j, &["data", "holder"]));
    assert!(next_argv(&j, 0).ends_with(&format!("close {r} --confirm {token}")));
    assert_eq!(s(&j, &["next", "1", "argv", "1"]), "status");
    assert_package(&package(&e.dest, r, 1), &sealed);
    only_additions(&before, &e.inventory()).unwrap();
    let kinds = e.log_kinds(r);
    assert_eq!(
        kinds[kinds.len() - 4..],
        [
            "close_requested",
            "seal",
            "delivery_planned",
            "delivery_ended"
        ]
    );
    let planned = e.log_record(r, kinds.len() - 1);
    assert_eq!(s(&planned, &["body", "by"]), "close");
    assert_eq!(s(&planned, &["body", "destination_source"]), "commissioned");
    assert!(null(&planned, &["body", "replaces"]));
    let plan = stewart::json::parse(
        &std::fs::read(format!("{}/delivery/1.json", e.audit_dir(r))).unwrap(),
    )
    .unwrap();
    assert_eq!(s(&plan, &["kind"]), "delivery_plan");
    assert_eq!(
        s(&plan, &["body", "members", "3", "source"]),
        sc.entries[2].payload
    );

    // Status recovers the outstanding confirmation.
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "awaiting_confirmation");
    assert_eq!(s(&j, &["data", "deliveries", "0", "confirmation"]), token);
    assert!(yes(&j, &["data", "headline", "delivered", "verified"]));
    assert!(no(&j, &["data", "headline", "delivered", "confirmed"]));
    assert_eq!(s(&j, &["data", "headline", "closed"]), "unfinished");
    assert!(next_argv(&j, 0).ends_with(&format!("--confirm {token}")));

    // A repeat without the token only presents the same result.
    let count = e.log_kinds(r).len();
    let j = close(&e, r, &[]).json();
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    assert_eq!(s(&j, &["data", "confirmation"]), token);
    assert_eq!(e.log_kinds(r).len(), count, "no new attempt or record");

    // A confirmation for something else is refused and publishes nothing.
    let o = close(&e, r, &["--confirm", "cf2.aaaaaa"]);
    assert_eq!(o.code, Some(3));
    assert_eq!(s(&o.json(), &["reason"]), "confirmation_mismatch");
    let o = close(
        &e,
        r,
        &["--confirm", &token, "--surrender", "loss.e9.aaaaaa"],
    );
    assert_eq!(s(&o.json(), &["reason"]), "handle_invalid");
    assert_eq!(e.log_kinds(r).len(), count);

    let o = close(&e, r, &["--confirm", &token]);
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    assert_eq!(effects(&j), ["ended", "existing", "verified", "complete"]);
    assert_eq!(s(&j, &["data", "closure"]), "complete");
    assert!(no(&j, &["data", "already_closed"]));
    assert_eq!(s(&j, &["data", "placement"]), "confirmed");
    assert_eq!(s(&j, &["data", "outcome"]), "closed_delivered");
    assert_eq!(at(&j, &["data", "delivery", "attempt"]).as_u64(), Some(1));
    assert!(at(&j, &["next"]).as_arr().unwrap().is_empty());
    let closed = e.log_record(r, e.log_kinds(r).len());
    assert_eq!(s(&closed, &["body", "confirmation"]), token);

    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "closed");
    assert!(yes(&j, &["data", "headline", "delivered", "confirmed"]));
    assert_eq!(s(&j, &["data", "closure", "placement"]), "confirmed");
    assert!(null(&j, &["data", "deliveries", "0", "confirmation"]));
    assert!(at(&j, &["next"]).as_arr().unwrap().is_empty());
    let j = close(&e, r, &["--confirm", "anything"]).json();
    assert!(yes(&j, &["data", "already_closed"]));
    assert_eq!(s(&j, &["data", "placement"]), "confirmed");
}

#[test]
fn a_delivery_verified_before_close_is_placed_by_an_ordinary_close() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let sealed = seal(a, Actor::Auditor, None, 1);
    let d = deliver_as_run(a, &e.dest);
    assert_eq!(d.attempts.len(), 1);
    assert_eq!(d.attempts[0].outcome.as_deref(), Some("verified"));
    end_run(a, 1, "sealed", None, Some(sealed.record));
    assert_package(&package(&e.dest, r, 1), &sealed);

    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "delivered_open");
    assert_eq!(s(&j, &["data", "headline", "sealed", "by"]), "auditor");
    assert!(yes(&j, &["data", "headline", "delivered", "verified"]));
    assert_eq!(
        s(&j, &["data", "headline", "delivered", "location"]),
        package(&e.dest, r, 1)
    );
    assert_eq!(s(&j, &["data", "deliveries", "0", "by"]), "run");
    assert!(null(&j, &["data", "deliveries", "0", "confirmation"]));
    assert!(s(&j, &["data", "seal", "handle"]).starts_with("seal."));
    assert_eq!(at(&j, &["data", "seal", "revision"]).as_u64(), Some(3));
    assert!(
        s(&j, &["next", "0", "why"]).contains("ordinary close confirms"),
        "{}",
        s(&j, &["next", "0", "why"])
    );

    let o = close(&e, r, &[]);
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    assert_eq!(effects(&j), ["ended", "existing", "verified", "complete"]);
    assert_eq!(s(&j, &["data", "placement"]), "delivered_before_close");
    assert_eq!(s(&j, &["data", "seal", "actor"]), "auditor");
    let closed = e.log_record(r, e.log_kinds(r).len());
    assert!(null(&closed, &["body", "confirmation"]));
    assert_eq!(
        e.log_kinds(r)
            .iter()
            .filter(|k| *k == "delivery_planned")
            .count(),
        1
    );
}

#[test]
fn a_stop_signal_during_the_runs_delivery_ends_the_attempt_failed() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let sealed = seal(a, Actor::Auditor, None, 1);
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
fn t9_an_unavailable_destination_is_replaced_through_close() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let sealed = seal(a, Actor::Auditor, None, 1);
    std::fs::remove_dir(&e.dest).unwrap();
    let d = deliver_as_run(a, &e.dest);
    assert_eq!(d.attempts[0].outcome.as_deref(), Some("failed"));
    end_run(a, 1, "sealed", None, Some(sealed.record));

    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "sealed_undelivered");
    assert_eq!(s(&j, &["data", "deliveries", "0", "outcome"]), "failed");
    assert_eq!(
        s(&j, &["data", "deliveries", "0", "cause", "error"]),
        "ENOENT"
    );
    assert!(s(&j, &["next", "0", "why"]).contains("--destination DIR"));

    // Usage: surrender belongs to a confirmation; a replacement destination
    // is not given with one.
    assert_eq!(
        e.run(&["close", r, "--surrender", "loss.e1.aaaaaa"]).code,
        Some(2)
    );
    assert_eq!(
        e.run(&["close", r, "--confirm", "cf1.aaaaaa", "--destination", "/x"])
            .code,
        Some(2)
    );

    let o = close(&e, r, &[]);
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    assert_eq!(effects(&j), ["ended", "existing", "failed", "unfinished"]);
    assert_eq!(s(&j, &["data", "unfinished_reason"]), "delivery_incomplete");
    assert!(null(&j, &["data", "confirmation"]));
    assert_eq!(at(&j, &["data", "delivery", "attempt"]).as_u64(), Some(2));
    assert_eq!(at(&j, &["next"]).as_arr().unwrap().len(), 1);
    assert!(s(&j, &["next", "0", "why"]).contains("--destination DIR"));
    let planned2 = e.log_record(r, e.log_kinds(r).len() - 1);
    assert_eq!(s(&planned2, &["kind"]), "delivery_planned");
    assert_eq!(at(&planned2, &["body", "replaces"]).as_u64(), Some(1));
    assert_eq!(
        s(&planned2, &["body", "destination_source"]),
        "commissioned"
    );

    // A replacement must be an existing absolute directory.
    let o = close(&e, r, &["--destination", "returns2"]);
    assert_eq!(o.code, Some(3));
    assert_eq!(s(&o.json(), &["reason"]), "destination_invalid");
    let o = close(&e, r, &["--destination", &e.path("returns2")]);
    assert_eq!(s(&o.json(), &["reason"]), "destination_invalid");

    let replacement = e.path("returns2");
    std::fs::create_dir(&replacement).unwrap();
    let o = close(&e, r, &["--destination", &replacement]);
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    assert_eq!(effects(&j), ["ended", "existing", "verified", "unfinished"]);
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    let token = s(&j, &["data", "confirmation"]).to_string();
    assert!(token.starts_with("cf3."), "{token}");
    assert_package(&package(&replacement, r, 3), &sealed);
    let planned3 = e.log_record(r, e.log_kinds(r).len() - 1);
    assert_eq!(at(&planned3, &["body", "replaces"]).as_u64(), Some(2));
    assert_eq!(s(&planned3, &["body", "destination_source"]), "replacement");

    // Close is not a copy service once a delivery verified.
    let other = e.path("returns3");
    std::fs::create_dir(&other).unwrap();
    let o = close(&e, r, &["--destination", &other]);
    assert_eq!(s(&o.json(), &["reason"]), "delivery_already_verified");
    assert!(std::fs::read_dir(&other).unwrap().next().is_none());

    let j = close(&e, r, &["--confirm", &token]).json();
    assert_eq!(s(&j, &["data", "closure"]), "complete");
    let j = status(&e, r);
    let outcomes: Vec<String> = at(&j, &["data", "deliveries"])
        .as_arr()
        .unwrap()
        .iter()
        .map(|d| s(d, &["outcome"]).to_string())
        .collect();
    assert_eq!(outcomes, ["failed", "failed", "verified"]);
}

#[test]
fn destination_replacement_needs_an_incomplete_attempt_of_the_seal() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let other = e.path("returns2");
    std::fs::create_dir(&other).unwrap();
    end_run(a, 1, "interrupted", Some("signal"), None);
    let o = close(&e, r, &["--destination", &other]);
    assert_eq!(o.code, Some(3));
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "destination_not_replaceable");
    assert_eq!(effects(&j), ["ended", "none", "none", "none"]);
    assert!(!e.log_kinds(r).contains(&"close_requested".to_string()));
    let o = close(&e, r, &["--confirm", "cf1.aaaaaa"]);
    assert_eq!(s(&o.json(), &["reason"]), "confirmation_mismatch");
    assert!(!e.log_kinds(r).contains(&"close_requested".to_string()));
}

#[test]
fn t10_a_damaged_element_is_delivered_as_a_named_loss_and_surrendered_by_name() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    end_run(a, 1, "ended_unsubmitted", None, None);
    // The artifact's payload is corrupted in the archive after it was recorded.
    let payload = format!("{}/{}", e.audit_dir(r), sc.entries[2].payload);
    std::fs::remove_file(&payload).unwrap();
    std::fs::write(&payload, b"trace bytes, altered").unwrap();
    let cr = request_close(a);
    let sealed = seal(a, Actor::Manager, Some(cr), 1);
    assert_eq!(
        sealed.unproduced,
        [("e3".to_string(), "damaged".to_string())]
    );

    let o = close(&e, r, &[]);
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    assert_eq!(
        effects(&j),
        ["ended", "existing", "verified_with_losses", "unfinished"]
    );
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    let token = s(&j, &["data", "confirmation"]).to_string();
    let losses = at(&j, &["data", "delivery", "losses"]).as_arr().unwrap();
    let ids: Vec<String> = losses.iter().map(|l| s(l, &["loss"]).to_string()).collect();
    assert_eq!(ids.len(), 2);
    assert!(ids[0].starts_with("loss.e3."), "{ids:?}");
    assert!(ids[1].starts_with("loss.answer-md."), "{ids:?}");
    assert_eq!(s(&losses[0], &["stage"]), "seal");
    assert_eq!(s(&losses[1], &["failure"]), "not_rendered");
    assert_package(&package(&e.dest, r, 1), &sealed);
    let answer =
        std::fs::read_to_string(format!("{}/answer.json", package(&e.dest, r, 1))).unwrap();
    assert!(answer.contains("\"unproduced\":{"), "{answer}");
    // The confirmation offer names every loss and what surrendering it gives up.
    let offer = next_argv(&j, 0);
    assert!(
        offer.contains(&format!("--surrender {}", ids[0])),
        "{offer}"
    );
    assert!(
        offer.contains(&format!("--surrender {}", ids[1])),
        "{offer}"
    );
    assert!(s(&j, &["next", "0", "why"]).contains("gives up entry e3"));

    let st = status(&e, r);
    assert!(no(&st, &["data", "headline", "delivered", "verified"]));
    assert_eq!(strs(&st, &["data", "headline", "delivered", "losses"]), ids);
    assert_eq!(s(&st, &["data", "deliveries", "0", "confirmation"]), token);
    assert_eq!(
        strs(&st, &["data", "seal", "unproduced"]),
        ["e3", "answer.md"]
    );

    let o = close(&e, r, &["--confirm", &token]);
    assert_eq!(o.code, Some(3));
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "surrender_required");
    assert_eq!(at(&j, &["data", "losses"]).as_arr().unwrap().len(), 2);
    assert!(next_argv(&j, 1).contains(&ids[1]));
    let o = close(&e, r, &["--confirm", &token, "--surrender", &ids[0]]);
    assert_eq!(s(&o.json(), &["reason"]), "surrender_required");

    let o = close(
        &e,
        r,
        &[
            "--confirm",
            &token,
            "--surrender",
            &ids[0],
            "--surrender",
            &ids[1],
        ],
    );
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    assert_eq!(
        s(&j, &["data", "outcome"]),
        "closed_with_surrendered_losses"
    );
    let given = at(&j, &["data", "surrendered"]).as_arr().unwrap();
    assert_eq!(s(&given[0], &["loss"]), ids[0]);
    assert_eq!(s(&given[0], &["member"]), "e3");
    let st = status(&e, r);
    assert_eq!(s(&st, &["data", "condition"]), "closed");
    assert!(no(&st, &["data", "headline", "delivered", "verified"]));
    assert!(yes(&st, &["data", "headline", "delivered", "confirmed"]));
    assert!(s(&st, &["data", "summary"]).contains("not a complete delivery"));
    assert_eq!(
        at(&st, &["data", "closure", "surrendered"])
            .as_arr()
            .unwrap()
            .len(),
        2
    );
}

#[test]
fn unknown_membership_is_never_delivered_as_an_empty_return() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let sealed = seal(a, Actor::Auditor, None, 1);
    // The run died after sealing, before it delivered; the manifest is then
    // damaged in the archive.
    let manifest = format!("{}/seal/manifest-1.json", e.audit_dir(r));
    let mut bytes = std::fs::read(&manifest).unwrap();
    bytes[10] ^= 1;
    std::fs::remove_file(&manifest).unwrap();
    std::fs::write(&manifest, &bytes).unwrap();

    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "sealed_undelivered");
    assert_eq!(s(&j, &["data", "seal", "sealed_at"]), "unknown");
    assert!(
        at(&j, &["data", "diagnostics"])
            .as_arr()
            .unwrap()
            .iter()
            .any(|d| s(d, &["record"]) == "seal/manifest-1.json")
    );

    let o = close(&e, r, &[]);
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    assert_eq!(effects(&j), ["ended", "existing", "failed", "unfinished"]);
    assert_eq!(s(&j, &["data", "unfinished_reason"]), "delivery_incomplete");
    assert_eq!(
        s(&j, &["data", "delivery", "cause", "error"]),
        "manifest_unavailable"
    );
    assert!(
        at(&j, &["data", "delivery", "losses"])
            .as_arr()
            .unwrap()
            .is_empty()
    );
    assert!(
        std::fs::read_dir(&e.dest).unwrap().next().is_none(),
        "no package"
    );
    let kinds = e.log_kinds(r);
    let ended = e.log_record(r, kinds.len());
    assert!(null(&ended, &["body", "members"]));
    assert!(null(&ended, &["body", "losses"]));
    // The dead placement was reconciled by close.
    let run_ended = (1..=kinds.len())
        .map(|n| e.log_record(r, n))
        .find(|j| s(j, &["kind"]) == "run_ended")
        .unwrap();
    assert_eq!(s(&run_ended, &["body", "cause"]), "process_gone");
    assert_eq!(s(&run_ended, &["body", "recorded_by"]), "close");
    assert_eq!(
        s(&run_ended, &["body", "seal"]),
        format!("log/{}.json", sealed.record)
    );
    let plan = stewart::json::parse(
        &std::fs::read(format!("{}/delivery/1.json", e.audit_dir(r))).unwrap(),
    )
    .unwrap();
    assert!(null(&plan, &["body", "members"]));
    // Unknown membership offers no loss IDs and no confirmation.
    let j = status(&e, r);
    assert_eq!(
        s(&j, &["data", "closure", "unfinished_reason"]),
        "delivery_incomplete"
    );
    assert!(null(&j, &["data", "deliveries", "0", "confirmation"]));
}

#[test]
fn an_existing_package_name_is_never_adopted() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let sealed = seal(a, Actor::Auditor, None, 1);
    end_run(a, 1, "sealed", None, Some(sealed.record));
    let taken = package(&e.dest, r, 1);
    std::fs::create_dir(&taken).unwrap();
    std::fs::write(format!("{taken}/mine.txt"), b"the manager's").unwrap();

    let j = close(&e, r, &[]).json();
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    assert!(s(&j, &["data", "confirmation"]).starts_with("cf2."));
    assert_eq!(package_members(&taken), ["mine.txt"]);
    assert_eq!(
        std::fs::read(format!("{taken}/mine.txt")).unwrap(),
        b"the manager's"
    );
    assert_package(&package(&e.dest, r, 2), &sealed);
    let st = status(&e, r);
    assert_eq!(
        s(&st, &["data", "deliveries", "0", "outcome"]),
        "name_taken"
    );
    assert_eq!(
        s(&st, &["data", "deliveries", "0", "package"]),
        format!("stewart-return-{}-001", id_of(r))
    );
    assert_eq!(
        at(&st, &["data", "deliveries", "1", "replaces"]).as_u64(),
        Some(1)
    );
}

#[test]
fn one_invocation_plans_at_most_sixteen_attempts() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let sealed = seal(a, Actor::Auditor, None, 1);
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
    let sealed = seal(a, Actor::Auditor, None, 1);
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
    let sealed = seal(&sc.audit, Actor::Auditor, None, 1);
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
    let sealed = seal(&sc.audit, Actor::Auditor, None, 1);
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

#[test]
fn status_after_launch_reports_each_fact_separately() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    // An open placement with the lock free: its process is gone.
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "interrupted");
    assert_eq!(
        s(&j, &["data", "evidence", "0", "evidence"]),
        "run_started without run_ended; lock free"
    );
    assert!(null(&j, &["data", "runs", "last", "ending"]));
    assert!(null(&j, &["data", "runs", "holder"]));
    assert!(null(&j, &["data", "provider_url_override"]));
    assert!(null(&j, &["data", "provider_proxy"]));
    assert_eq!(s(&j, &["next", "0", "argv", "1"]), "run");
    assert_eq!(s(&j, &["next", "1", "argv", "1"]), "close");
    let keys: Vec<String> = match &at(&j, &["data"]).v {
        V::Obj(m) => m.iter().map(|(k, _)| k.clone()).collect(),
        _ => panic!(),
    };
    assert_eq!(
        keys,
        [
            "headline",
            "condition",
            "summary",
            "evidence",
            "runs",
            "allowances",
            "answer",
            "seal",
            "deliveries",
            "closure",
            "diagnostics",
            "provider_url_override",
            "provider_proxy",
            "receipt_line"
        ]
    );
    // Elapsed time establishes nothing; the same records give the same answer.
    std::thread::sleep(std::time::Duration::from_millis(1100));
    assert_eq!(s(&status(&e, r), &["data", "condition"]), "interrupted");

    end_run(a, 1, "interrupted", Some("signal"), None);
    start_run_with(
        a,
        2,
        stewart::bodies::ProviderUse {
            base_url: "http://127.0.0.1:9".into(),
            overridden: true,
            proxy: Some("http://proxy.example:3128".into()),
            anthropic_version: "2026-10-21".into(),
        },
    );
    end_run(a, 2, "limit_reached", None, None);
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "limit_reached");
    assert_eq!(
        s(&j, &["data", "provider_url_override"]),
        "http://127.0.0.1:9"
    );
    assert_eq!(
        s(&j, &["data", "provider_proxy"]),
        "http://proxy.example:3128"
    );
    assert_eq!(at(&j, &["data", "runs", "count"]).as_u64(), Some(2));
    assert_eq!(
        at(&j, &["data", "allowances", "turns", "reported"]).as_u64(),
        Some(6)
    );
    assert_eq!(s(&j, &["data", "headline", "sealed", "by"]), "none");
    assert!(s(&j, &["next", "0", "why"]).contains("manager attribution"));

    // Human and JSON presentations carry the same facts.
    let human = e.run(&["status", r]).text();
    assert!(human.contains("Condition: limit_reached"), "{human}");
    assert!(human.contains("Sealed by: none"), "{human}");
    assert!(
        human.contains("provider url override: http://127.0.0.1:9"),
        "{human}"
    );

    // A placement ending damaged is its own condition.
    let e2 = Env::new();
    let sc2 = launched_with_entries(&e2);
    end_run(&sc2.audit, 1, "damaged", None, None);
    assert_eq!(s(&status(&e2, &sc2.r), &["data", "condition"]), "damaged");

    // Close requested and every fact of closure has its key.
    let cr = request_close(a);
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "close_unfinished");
    let closure: Vec<String> = match &at(&j, &["data", "closure"]).v {
        V::Obj(m) => m.iter().map(|(k, _)| k.clone()).collect(),
        _ => panic!(),
    };
    assert_eq!(
        closure,
        [
            "requested_at",
            "before_launch",
            "accepted",
            "unfinished_reason",
            "closed_at",
            "outcome",
            "placement",
            "surrendered"
        ]
    );
    assert!(no(&j, &["data", "closure", "before_launch"]));
    assert!(null(&j, &["data", "closure", "unfinished_reason"]));
    assert!(null(&j, &["data", "closure", "closed_at"]));
    let _ = cr;

    // A damaged log after launch leaves dependent facts unknown.
    std::fs::write(format!("{}/log/99.json", e.audit_dir(r)), b"{}").unwrap();
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "log_damaged");
    assert_eq!(
        s(&j, &["data", "headline", "delivered", "verified"]),
        "unknown"
    );
    assert_eq!(
        s(&j, &["data", "closure", "unfinished_reason"]),
        "log_damaged"
    );
    let j = close(&e, r, &[]).json();
    assert_eq!(s(&j, &["data", "unfinished_reason"]), "log_damaged");
    assert_eq!(effects(&j), ["unknown", "unknown", "unknown", "unfinished"]);
}

#[test]
fn close_and_status_change_only_by_addition() {
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let (r, a) = (&sc.r, &sc.audit);
    let sealed = seal(a, Actor::Auditor, None, 1);
    end_run(a, 1, "sealed", None, Some(sealed.record));
    let folder_before = std::fs::read(format!("{}/materials/a.py", e.folder)).unwrap();
    let before = e.inventory();
    let j = status(&e, r);
    assert_eq!(s(&j, &["data", "condition"]), "sealed_undelivered");
    assert_eq!(before, e.inventory(), "status writes nothing");
    let token = s(&close(&e, r, &[]).json(), &["data", "confirmation"]).to_string();
    let mid = e.inventory();
    only_additions(&before, &mid).unwrap();
    close(&e, r, &["--confirm", &token]);
    only_additions(&mid, &e.inventory()).unwrap();
    assert_eq!(
        std::fs::read(format!("{}/materials/a.py", e.folder)).unwrap(),
        folder_before
    );
    // The delivered answer verifies without the archive.
    let pkg = package(&e.dest, r, 1);
    std::fs::rename(&e.archive, e.path("archive-away")).unwrap();
    let manifest = std::fs::read(format!("{pkg}/manifest.json")).unwrap();
    let m = stewart::returns::Manifest::decode(&manifest).unwrap();
    for member in &m.members {
        let b = std::fs::read(format!("{pkg}/{}", member.name)).unwrap();
        assert_eq!(
            stewart::util::sha256_hex(&b),
            member.sha256,
            "{}",
            member.name
        );
    }
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
