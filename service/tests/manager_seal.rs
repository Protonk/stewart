//! Close's manager seal through the answer module's `prepare` and `seal`
//! (INTERFACE 5.8 "Seal", 8.1; traces T8 and T10 in full). The close paths in
//! `delivery.rs` start instead from seals the fixture writes.

mod common;
mod fixture;
use common::*;
use fixture::*;
use stewart::json::V;

fn close(e: &Env, r: &str, extra: &[&str]) -> Out {
    let mut args = vec!["close", r];
    args.extend_from_slice(extra);
    args.push("--json");
    e.run(&args)
}

fn package(e: &Env, r: &str, attempt: u64) -> String {
    format!(
        "{}/stewart-return-{}-{attempt:03}",
        e.dest,
        r.split(':').nth(1).unwrap()
    )
}

#[test]
fn manager_seal_through_the_answer_interface() {
    // T8: an ordinary ending; close seals the recorded selection as manager,
    // delivers it and waits for confirmation.
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let r = &sc.r;
    end_run(&sc.audit, 1, "ended_unsubmitted", None, None);
    let o = close(&e, r, &[]);
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    let j = o.json();
    for (k, v) in [
        ("run", "ended"),
        ("seal", "recorded"),
        ("delivery", "verified"),
        ("closure", "unfinished"),
    ] {
        assert_eq!(s(&j, &["effects", k]), v, "{k}");
    }
    assert_eq!(
        s(&j, &["data", "unfinished_reason"]),
        "awaiting_confirmation"
    );
    assert_eq!(s(&j, &["data", "seal", "actor"]), "manager");
    let token = s(&j, &["data", "confirmation"]).to_string();
    assert!(token.starts_with("cf1."));
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
    let seal_rec = e.log_record(r, kinds.len() - 2);
    assert_eq!(s(&seal_rec, &["body", "actor"]), "manager");
    assert!(at(&seal_rec, &["body", "invocation"]).is_null());

    // The delivered return against the witness.
    let pkg = package(&e, r, 1);
    assert_eq!(
        package_members(&pkg),
        [
            "answer.json",
            "answer.md",
            "artifact-e3.bin",
            "manifest.json"
        ]
    );
    let manifest = std::fs::read(format!("{pkg}/manifest.json")).unwrap();
    let m = stewart::returns::Manifest::decode(&manifest).unwrap();
    assert_eq!(m.actor, stewart::bodies::Actor::Manager);
    assert_eq!(m.revision, 3);
    assert_eq!(m.family, "open-inquiry/1");
    assert!(m.unproduced.is_empty());
    for member in &m.members {
        let b = std::fs::read(format!("{pkg}/{}", member.name)).unwrap();
        assert_eq!(
            stewart::util::sha256_hex(&b),
            member.sha256,
            "{}",
            member.name
        );
    }
    assert_eq!(
        std::fs::read(format!("{pkg}/artifact-e3.bin")).unwrap(),
        sc.entries[2].bytes
    );
    let answer = std::fs::read_to_string(format!("{pkg}/answer.json")).unwrap();
    let mut at_ = 0;
    for entry in &sc.entries[..2] {
        let quoted = stewart::json::quote(std::str::from_utf8(&entry.bytes).unwrap());
        let i = answer[at_..]
            .find(&quoted)
            .unwrap_or_else(|| panic!("{quoted} in {answer}"));
        at_ += i;
    }
    let rendering = std::fs::read_to_string(format!("{pkg}/answer.md")).unwrap();
    assert!(
        rendering.starts_with("Rendered by Stewart. Entry text is attributed to the auditor.\n")
    );

    let j = close(&e, r, &["--confirm", &token]).json();
    assert_eq!(s(&j, &["data", "closure"]), "complete");
    assert_eq!(s(&j, &["data", "placement"]), "confirmed");
    assert_eq!(s(&j, &["effects", "seal"]), "existing");

    // T10: a payload damaged in the archive becomes a named, unproduced
    // member, and so does the rendering; delivery carries the losses.
    let e = Env::new();
    let sc = launched_with_entries(&e);
    let r = &sc.r;
    end_run(&sc.audit, 1, "ended_unsubmitted", None, None);
    let payload = format!("{}/{}", e.audit_dir(r), sc.entries[2].payload);
    std::fs::remove_file(&payload).unwrap();
    std::fs::write(&payload, b"altered").unwrap();
    let j = close(&e, r, &[]).json();
    assert_eq!(s(&j, &["effects", "seal"]), "recorded");
    assert_eq!(s(&j, &["effects", "delivery"]), "verified_with_losses");
    assert_eq!(
        strs(&j, &["data", "seal", "unproduced"]),
        ["e3", "answer.md"]
    );
    let pkg = package(&e, r, 1);
    assert_eq!(package_members(&pkg), ["answer.json", "manifest.json"]);
    let answer = std::fs::read_to_string(format!("{pkg}/answer.json")).unwrap();
    assert!(answer.contains("\"unproduced\":{"), "{answer}");
    let token = s(&j, &["data", "confirmation"]).to_string();
    let ids: Vec<String> = at(&j, &["data", "delivery", "losses"])
        .as_arr()
        .unwrap()
        .iter()
        .map(|l| s(l, &["loss"]).to_string())
        .collect();
    assert_eq!(ids.len(), 2);
    let j = close(
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
    )
    .json();
    assert_eq!(
        s(&j, &["data", "outcome"]),
        "closed_with_surrendered_losses"
    );

    // An empty selection is sealed as an honest empty return.
    let e = Env::new();
    let r = accepted(&e);
    let a = open(&r);
    start_run(&a, 1);
    end_run(&a, 1, "ended_unsubmitted", None, None);
    let j = close(&e, &r, &[]).json();
    assert_eq!(s(&j, &["effects", "delivery"]), "verified");
    let pkg = package(&e, &r, 1);
    assert_eq!(
        std::fs::read(format!("{pkg}/answer.json")).unwrap(),
        b"{\"schema\":\"stewart.answer/1\",\"revision\":0,\"entries\":[]}\n"
    );
    assert_eq!(
        std::fs::read(format!("{pkg}/answer.md")).unwrap(),
        b"No answer entries recorded.\n"
    );
    assert!(matches!(at(&j, &["data", "seal", "revision"]).v, V::Int(0)));
}
