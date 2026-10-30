//! Each sabotage control breaks exactly its property (INTERFACE Appendix
//! C.2), so a check of that property fires. These tests show the break; the
//! release-behavior tests show the property holding without it. Built only
//! with `--features sabotage`.
#![cfg(feature = "sabotage")]

mod common;
use common::*;

const SAB: &str = "STEWART_TEST_SABOTAGE";

fn with(e: &Env, name: &str, args: &[&str]) -> Out {
    e.run_env(args, &[(SAB, name)])
}

#[test]
fn accept_without_affirmation() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    assert_eq!(e.run(&["commission", &r, &h, "--json"]).code, Some(3));
    let o = with(
        &e,
        "accept_without_affirmation",
        &["commission", &r, &h, "--json"],
    );
    assert_eq!(s(&o.json(), &["effects", "acceptance"]), "accepted");
}

#[test]
fn accept_changed_source() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"one")]);
    std::fs::write(e.path("q/materials/a"), b"newer").unwrap();
    let o = with(
        &e,
        "accept_changed_source",
        &["commission", &r, &h, "--i-am-finished", "--json"],
    );
    assert_eq!(s(&o.json(), &["effects", "acceptance"]), "accepted");
    assert_eq!(e.run(&["receipt", &r, "--read", "materials/a"]).stdout, b"");
}

#[test]
fn skip_hidden_entries() {
    let e = Env::new();
    let r = e.new_ref();
    e.fill("Q\n", &[(".hidden", b"h"), ("a", b"a")]);
    let j = with(&e, "skip_hidden_entries", &["prepare", &r, "--json"]).json();
    assert_eq!(at(&j, &["data", "materials", "count"]).as_u64(), Some(1));
}

#[test]
fn normalize_newlines() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"x\r\ny\r\n")]);
    assert_eq!(
        with(
            &e,
            "normalize_newlines",
            &["commission", &r, &h, "--i-am-finished"]
        )
        .code,
        Some(0)
    );
    assert_eq!(e.run(&["receipt", &r, "--read", "materials/a"]).stdout, b"");
    let cap = std::fs::read(format!("{}/intake/1/m0001.bin", e.audit_dir(&r))).unwrap();
    assert_eq!(cap, b"x\ny\n");
}

#[test]
fn follow_symlinks() {
    let e = Env::new();
    let r = e.new_ref();
    e.fill("Q\n", &[]);
    std::fs::write(e.path("outside.txt"), b"outside").unwrap();
    std::os::unix::fs::symlink(e.path("outside.txt"), e.path("q/materials/link")).unwrap();
    assert_eq!(
        s(&e.run(&["prepare", &r, "--json"]).json(), &["reason"]),
        "unsupported_entry"
    );
    let o = with(&e, "follow_symlinks", &["prepare", &r, "--json"]);
    assert_eq!(o.code, Some(0), "{}", o.text());
}

#[test]
fn readback_live_source() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"captured")]);
    assert_eq!(e.commission(&r, &h).code, Some(0));
    std::fs::write(e.path("q/materials/a"), b"live").unwrap();
    assert_eq!(
        e.run(&["receipt", &r, "--read", "materials/a"]).stdout,
        b"captured"
    );
    assert_eq!(
        with(
            &e,
            "readback_live_source",
            &["receipt", &r, "--read", "materials/a"]
        )
        .stdout,
        b"live"
    );
}

#[test]
fn regenerate_arrangement() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    assert_eq!(e.commission(&r, &h).code, Some(0));
    let pinned = e.run(&["receipt", &r, "--read", "arrangement"]).stdout;
    assert!(!pinned.is_empty());
    let regenerated = with(
        &e,
        "regenerate_arrangement",
        &["receipt", &r, "--read", "arrangement"],
    )
    .stdout;
    assert_ne!(pinned, regenerated);
}

#[test]
fn rewrite_record_in_place() {
    let e = Env::new();
    let (r, _) = e.prepared(&[("a", b"a")]);
    let before = e.inventory();
    with(&e, "rewrite_record_in_place", &["close", &r, "--json"]);
    assert!(only_additions(&before, &e.inventory()).is_err());
}

#[test]
fn remove_partial_on_retry() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    std::fs::write(e.path("q/materials/a"), b"changed").unwrap();
    assert_eq!(e.commission(&r, &h).code, Some(3));
    let before = e.inventory();
    with(
        &e,
        "remove_partial_on_retry",
        &["commission", &r, &h, "--i-am-finished", "--json"],
    );
    assert!(only_additions(&before, &e.inventory()).is_err());
}

#[test]
fn unknown_as_absent() {
    let e = Env::new();
    let (r, _) = e.prepared(&[("a", b"a")]);
    std::fs::write(format!("{}/log/3.json", e.audit_dir(&r)), b"{").unwrap();
    assert_eq!(
        s(
            &e.run(&["status", &r, "--json"]).json(),
            &["data", "headline", "accepted"]
        ),
        "unknown"
    );
    assert_eq!(
        s(
            &with(&e, "unknown_as_absent", &["status", &r, "--json"]).json(),
            &["data", "headline", "accepted"]
        ),
        "no"
    );
}

#[test]
fn select_newer_store() {
    let e = Env::new();
    let r = e.new_ref();
    std::fs::rename(&e.archive, e.path("away")).unwrap();
    e.run(&["new", &e.path("q2"), "--archive", &e.archive]);
    assert_eq!(
        s(&e.run(&["status", &r, "--json"]).json(), &["reason"]),
        "archive_replaced"
    );
    assert_ne!(
        s(
            &with(&e, "select_newer_store", &["status", &r, "--json"]).json(),
            &["reason"]
        ),
        "archive_replaced"
    );
}

#[test]
fn accept_unknown_field() {
    let e = Env::new();
    let r = e.new_ref();
    std::fs::write(
        e.path("q/question.md"),
        e.question("open-inquiry", "Q\n")
            .replace("family:", "colour: blue\nfamily:"),
    )
    .unwrap();
    assert_eq!(
        s(&e.run(&["prepare", &r, "--json"]).json(), &["reason"]),
        "front_matter_invalid"
    );
    assert_eq!(
        with(&e, "accept_unknown_field", &["prepare", &r, "--json"]).code,
        Some(0)
    );
}

#[test]
fn omit_effects_on_refusal() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    assert!(has(
        &e.run(&["commission", &r, &h, "--json"]).json(),
        "effects"
    ));
    assert!(!has(
        &with(
            &e,
            "omit_effects_on_refusal",
            &["commission", &r, &h, "--json"]
        )
        .json(),
        "effects"
    ));
}

#[test]
fn whole_from_one_member() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a"), ("b", b"b")]);
    assert_eq!(e.commission(&r, &h).code, Some(0));
    let cap = format!("{}/intake/1/m0002.bin", e.audit_dir(&r));
    std::fs::remove_file(&cap).unwrap();
    let all = |o: Out| {
        at(&o.json(), &["data", "verification", "all_items_verified"])
            .v
            .clone()
    };
    assert_eq!(
        all(e.run(&["receipt", &r, "--verify", "--json"])),
        stewart::json::V::Bool(false)
    );
    assert_eq!(
        all(with(
            &e,
            "whole_from_one_member",
            &["receipt", &r, "--verify", "--json"]
        )),
        stewart::json::V::Bool(true)
    );
}
