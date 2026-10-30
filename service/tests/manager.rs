//! End-to-end manager commands through the real binary (release behavior;
//! no fault or sabotage controls are set).

mod common;
use common::*;

#[test]
fn the_ordinary_path_from_scaffold_to_close() {
    let e = Env::new();
    let o = e.run(&["new", &e.folder, "--archive", &e.archive, "--json"]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    let j = o.json();
    assert_eq!(s(&j, &["effects", "reference"]), "created");
    assert_eq!(
        at(&j, &["data", "archive_created"]).v,
        stewart::json::V::Bool(true)
    );
    assert_eq!(
        at(&j, &["data", "scaffold_created"]).v,
        stewart::json::V::Bool(true)
    );
    let r = s(&j, &["data", "reference"]).to_string();
    assert!(r.starts_with("stw1:a"));
    // The next call begins with the recorded writer path, never a bare name.
    assert_eq!(s(&j, &["next", "0", "argv", "0"]), bin_canonical());
    let scaffold = std::fs::read_to_string(format!("{}/question.md", e.folder)).unwrap();
    assert!(scaffold.contains("model: REPLACE-WITH-MODEL"));
    assert!(scaffold.contains("leave this folder unchanged until commission returns"));
    assert!(
        std::fs::read_dir(format!("{}/materials", e.folder))
            .unwrap()
            .next()
            .is_none()
    );

    // The scaffold is refused, naming each edit.
    let o = e.run(&["prepare", &r, "--json"]);
    assert_eq!(o.code, Some(3));
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "setting_invalid");
    assert_eq!(s(&j, &["effects", "preparation"]), "none");
    assert_eq!(s(&j, &["data", "defects", "2", "reason"]), "question_empty");

    // A valid folder prepares, and the handle commissions.
    e.fill(
        "Audit our app.\r\n",
        &[
            ("a.py", b"print(1)\r\n"),
            (".hidden/x", b""),
            ("dir/b.txt", "\u{feff}b".as_bytes()),
        ],
    );
    std::fs::create_dir_all(format!("{}/materials/empty", e.folder)).unwrap();
    let o = e.run(&["prepare", &r, "--json"]);
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    let h = s(&j, &["data", "prepared"]).to_string();
    assert!(h.starts_with("mp1."), "{h}");
    let names: Vec<String> = at(&j, &["data", "materials", "files"])
        .as_arr()
        .unwrap()
        .iter()
        .map(|f| s(f, &["name"]).to_string())
        .collect();
    assert_eq!(
        names,
        [
            "materials/.hidden/x",
            "materials/a.py",
            "materials/dir/b.txt"
        ]
    );
    assert_eq!(
        strs(&j, &["data", "materials", "directories"]),
        [
            "materials",
            "materials/.hidden",
            "materials/dir",
            "materials/empty"
        ]
    );
    assert_eq!(s(&j, &["data", "reader", "transformations"]), "none");
    let machine = s(&j, &["data", "arrangement", "machine"]).to_string();
    let readable = s(&j, &["data", "arrangement", "readable"]).to_string();
    let arrangement_sha = s(&j, &["data", "arrangement", "sha256"]).to_string();
    let arrangement = std::fs::read(&machine).unwrap();
    assert_eq!(stewart::util::sha256_hex(&arrangement), arrangement_sha);
    assert!(
        std::fs::read_to_string(&readable)
            .unwrap()
            .contains("Address the question from the supplied materials.")
    );
    assert_eq!(s(&j, &["next", "0", "argv", "4"]), "--i-am-finished");

    let before = e.inventory();
    let o = e.commission(&r, &h);
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    assert_eq!(s(&j, &["effects", "acceptance"]), "accepted");
    assert_eq!(s(&j, &["effects", "attempt"]), "recorded");
    assert_eq!(strs(&j, &["data", "checks"]).len(), 3);
    assert_eq!(s(&j, &["next", "0", "argv", "1"]), "run");
    assert_eq!(s(&j, &["next", "1", "argv", "1"]), "close");
    let receipt_sha = s(&j, &["data", "receipt_sha256"]).to_string();
    only_additions(&before, &e.inventory()).unwrap();
    assert_eq!(
        e.log_kinds(&r),
        ["reference", "prepared", "intake_planned", "accepted"]
    );

    // Source edits after acceptance change nothing; the receipt reads back the captured bytes.
    std::fs::write(format!("{}/materials/a.py", e.folder), b"changed").unwrap();
    std::fs::remove_file(format!("{}/question.md", e.folder)).unwrap();
    let o = e.run(&["commission", &r, &h, "--i-am-finished", "--json"]);
    let j = o.json();
    assert_eq!(
        at(&j, &["data", "already_accepted"]).v,
        stewart::json::V::Bool(true)
    );
    assert_eq!(s(&j, &["data", "receipt_sha256"]), receipt_sha);
    assert_eq!(s(&j, &["effects", "attempt"]), "none");
    let o = e.run(&["receipt", &r, "--read", "materials/a.py"]);
    assert_eq!(o.code, Some(0));
    assert_eq!(o.stdout, b"print(1)\r\n");
    let line = stewart::json::parse(o.stderr.trim_end().as_bytes()).unwrap();
    assert_eq!(at(&line, &["verified"]).v, stewart::json::V::Bool(true));
    let o = e.run(&["receipt", &r, "--read", "question-body"]);
    assert_eq!(o.stdout, b"Audit our app.\r\n");
    let o = e.run(&["receipt", &r, "--read", "arrangement"]);
    assert_eq!(o.stdout, arrangement);
    let o = e.run(&["receipt", &r, "--read", "materials/dir/b.txt"]);
    assert_eq!(o.stdout, "\u{feff}b".as_bytes());
    let o = e.run(&["receipt", &r, "--verify", "--json"]);
    let j = o.json();
    for item in at(&j, &["data", "items"]).as_arr().unwrap() {
        assert_eq!(
            s(item, &["verification"]),
            "verified",
            "{}",
            s(item, &["id"])
        );
    }
    let o = e.run(&["status", &r, "--json"]);
    let j = o.json();
    assert_eq!(s(&j, &["data", "condition"]), "not_started");
    assert_eq!(s(&j, &["data", "headline", "accepted"]), "yes");
    assert_eq!(s(&j, &["data", "headline", "launched"]), "no");
    assert_eq!(s(&j, &["next", "0", "argv", "1"]), "run");

    // Close before launch: no answer, and the reference accepts nothing more.
    let o = e.run(&["close", &r, "--json"]);
    assert_eq!(o.code, Some(0), "{}", o.text());
    let j = o.json();
    assert_eq!(s(&j, &["effects", "closure"]), "complete");
    assert_eq!(s(&j, &["effects", "seal"]), "none");
    assert_eq!(
        at(&j, &["data", "accepted"]).v,
        stewart::json::V::Bool(true)
    );
    let o = e.run(&["close", &r, "--json"]);
    assert_eq!(
        at(&o.json(), &["data", "already_closed"]).v,
        stewart::json::V::Bool(true)
    );
    let o = e.run(&["status", &r, "--json"]);
    assert_eq!(s(&o.json(), &["data", "condition"]), "closed_before_launch");
    // Receipt readback continues after close.
    assert_eq!(
        e.run(&["receipt", &r, "--read", "materials/a.py"]).stdout,
        b"print(1)\r\n"
    );
    // The folder is left alone.
    assert_eq!(
        std::fs::read(format!("{}/materials/a.py", e.folder)).unwrap(),
        b"changed"
    );
}

fn bin_canonical() -> String {
    std::fs::canonicalize(bin())
        .unwrap()
        .to_str()
        .unwrap()
        .to_string()
}

#[test]
fn the_human_presentation_carries_the_same_result() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a.txt", b"x")]);
    let o = e.run(&["commission", &r, &h]);
    assert_eq!(o.code, Some(3));
    let t = o.text();
    assert!(t.contains("refused (affirmation_missing)"), "{t}");
    assert!(
        t.contains("Effects: acceptance absent, attempt none"),
        "{t}"
    );
    assert!(t.contains("--i-am-finished"), "{t}");
    let o = e.run(&["status", &r]);
    let t = o.text();
    assert!(t.contains("Accepted: no | Launched: no"), "{t}");
    assert!(t.contains("Condition: preparing."), "{t}");
}

#[test]
fn new_reports_other_references_to_the_same_folder() {
    let e = Env::new();
    let r1 = e.new_ref();
    let o = e.run(&["new", &e.folder, "--archive", &e.archive, "--json"]);
    let j = o.json();
    assert_eq!(
        at(&j, &["data", "scaffold_created"]).v,
        stewart::json::V::Bool(false)
    );
    assert_eq!(
        s(&j, &["data", "notices", "0", "reason"]),
        "folder_already_referenced"
    );
    assert_eq!(
        strs(&j, &["data", "notices", "0", "references"]),
        std::slice::from_ref(&r1)
    );
    assert_ne!(s(&j, &["data", "reference"]), r1);
    // STEWART_ARCHIVE supplies the root for new only.
    let o = e.run_env(
        &["new", &e.path("q2"), "--json"],
        &[("STEWART_ARCHIVE", &e.archive)],
    );
    assert_eq!(o.code, Some(0), "{}", o.text());
    let o = e.run(&["status", "--archive", &e.archive, "--json"]);
    assert_eq!(
        at(&o.json(), &["data", "references"])
            .as_arr()
            .unwrap()
            .len(),
        3
    );
}

#[test]
fn new_refusals() {
    let e = Env::new();
    let o = e.run(&["new", &e.folder, "--json"]);
    assert_eq!(o.code, Some(3));
    assert_eq!(s(&o.json(), &["reason"]), "archive_unspecified");
    assert_eq!(s(&o.json(), &["effects", "reference"]), "none");

    std::fs::create_dir_all(e.path("full")).unwrap();
    std::fs::write(e.path("full/x"), b"x").unwrap();
    let o = e.run(&["new", &e.folder, "--archive", &e.path("full"), "--json"]);
    assert_eq!(s(&o.json(), &["reason"]), "archive_not_a_store");

    // The folder may not be inside the archive, nor the archive inside the folder.
    let o = e.run(&[
        "new",
        &format!("{}/inner", e.archive),
        "--archive",
        &e.archive,
        "--json",
    ]);
    assert_eq!(s(&o.json(), &["reason"]), "location_overlap");
    std::fs::create_dir_all(&e.folder).unwrap();
    let o = e.run(&[
        "new",
        &e.folder,
        "--archive",
        &format!("{}/arch", e.folder),
        "--json",
    ]);
    assert_eq!(s(&o.json(), &["reason"]), "location_overlap");

    // A symbolic link in the archive path is refused.
    std::os::unix::fs::symlink(&e.cwd, e.path("link")).unwrap();
    let o = e.run(&[
        "new",
        &e.path("q3"),
        "--archive",
        &e.path("link/arch"),
        "--json",
    ]);
    assert_eq!(s(&o.json(), &["reason"]), "archive_path_symlink");

    // Relative paths are usage errors: no operation began.
    let o = e.run(&["new", "relative", "--archive", &e.archive, "--json"]);
    assert_eq!(o.code, Some(2));
    assert!(o.stdout.is_empty());
}

#[test]
fn prepare_refuses_mechanical_problems_with_useful_reasons() {
    let e = Env::new();
    let r = e.new_ref();
    let reason = |e: &Env| {
        let o = e.run(&["prepare", &r, "--json"]);
        assert_eq!(o.code, Some(3), "{}", o.text());
        s(&o.json(), &["reason"]).to_string()
    };
    e.fill("Q\n", &[("a.txt", b"x")]);
    std::fs::write(e.path("q/notes.txt"), b"n").unwrap();
    assert_eq!(reason(&e), "unexpected_root_entry");
    std::fs::remove_file(e.path("q/notes.txt")).unwrap();

    std::fs::write(
        e.path("q/question.md"),
        e.question("open-inquiry", "Q\n")
            .replace("model:", "modle:"),
    )
    .unwrap();
    assert_eq!(reason(&e), "front_matter_invalid");
    std::fs::write(e.path("q/question.md"), e.question("open-inquiry", " \n")).unwrap();
    assert_eq!(reason(&e), "question_empty");
    std::fs::write(
        e.path("q/question.md"),
        e.question("open-inquiry", "Q\n")
            .replace(&e.dest, &e.path("absent")),
    )
    .unwrap();
    assert_eq!(reason(&e), "destination_invalid");
    std::fs::write(
        e.path("q/question.md"),
        e.question("open-inquiry", "Q\n")
            .replace(&e.dest, &e.path("q/materials")),
    )
    .unwrap();
    assert_eq!(reason(&e), "location_overlap");
    std::fs::write(e.path("q/question.md"), e.question("open-inquiry", "Q\n")).unwrap();

    std::os::unix::fs::symlink("/etc/hosts", e.path("q/materials/link")).unwrap();
    assert_eq!(reason(&e), "unsupported_entry");
    std::fs::remove_file(e.path("q/materials/link")).unwrap();
    std::fs::write(e.path("q/materials/bin"), b"\x89PNG\r\n").unwrap();
    let o = e.run(&["prepare", &r, "--json"]);
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "material_not_text");
    assert_eq!(s(&j, &["data", "entry"]), "materials/bin");
    std::fs::remove_file(e.path("q/materials/bin")).unwrap();
    for i in 0..128 {
        std::fs::write(e.path(&format!("q/materials/f{i:03}")), b"").unwrap();
    }
    let o = e.run(&["prepare", &r, "--json"]);
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "bound_exceeded");
    assert_eq!(s(&j, &["data", "bound"]), "files");
    std::fs::remove_dir_all(e.path("q/materials")).unwrap();
    assert_eq!(reason(&e), "folder_incomplete");
    // Each refusal kept a diagnostic and published nothing.
    assert_eq!(e.log_kinds(&r), ["reference"]);
    assert!(
        std::fs::read_dir(format!("{}/diag", e.audit_dir(&r)))
            .unwrap()
            .count()
            >= 9
    );
}

#[test]
fn a_changed_selection_is_refused_then_a_fresh_preparation_commissions() {
    let e = Env::new();
    let (r, h1) = e.prepared(&[("a.py", b"one\n"), ("b.txt", b"b")]);
    // An added file is seen by the final scan.
    std::fs::write(e.path("q/materials/new.txt"), b"n").unwrap();
    let j = e.commission(&r, &h1).json();
    assert_eq!(s(&j, &["reason"]), "selection_changed");
    assert_eq!(strs(&j, &["data", "added"]), ["materials/new.txt"]);
    std::fs::remove_file(e.path("q/materials/new.txt")).unwrap();
    // A changed file is seen during the copy.
    std::fs::write(e.path("q/materials/a.py"), b"two\n").unwrap();
    let o = e.commission(&r, &h1);
    assert_eq!(o.code, Some(3), "{}", o.text());
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "selection_changed");
    assert_eq!(s(&j, &["effects", "acceptance"]), "absent");
    assert_eq!(s(&j, &["effects", "attempt"]), "partial");
    assert_eq!(strs(&j, &["data", "changed"]), ["materials/a.py"]);
    assert!(
        strs(&j, &["retained"])
            .iter()
            .any(|p| p.ends_with("/intake/2"))
    );
    assert_eq!(
        e.log_kinds(&r),
        [
            "reference",
            "prepared",
            "intake_planned",
            "intake_ended",
            "intake_planned",
            "intake_ended"
        ]
    );
    let rec = e.log_record(&r, 6);
    assert_eq!(s(&rec, &["body", "outcome"]), "selection_changed");
    let o = e.run(&["status", &r, "--json"]);
    assert_eq!(s(&o.json(), &["data", "condition"]), "intake_failed");

    let o = e.run(&["prepare", &r, "--json"]);
    let h2 = s(&o.json(), &["data", "prepared"]).to_string();
    assert!(h2.starts_with("mp2."));
    let o = e.commission(&r, &h2);
    assert_eq!(o.code, Some(0), "{}", o.text());
    assert_eq!(
        e.run(&["receipt", &r, "--read", "materials/a.py"]).stdout,
        b"two\n"
    );
    // A different handle after acceptance is refused; the old attempts stay.
    let o = e.commission(&r, &h1);
    assert_eq!(s(&o.json(), &["reason"]), "reference_already_accepted");
    for n in 1..=3 {
        assert!(
            std::path::Path::new(&format!("{}/intake/{n}/q.bin", e.audit_dir(&r))).exists(),
            "intake {n}"
        );
    }
}

#[test]
fn handles_bind_their_audit_and_preparation() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let e2 = Env::new();
    let (r2, h2) = e2.prepared(&[("a", b"a")]);
    for bad in [
        h2.as_str(),
        "mp1.aaaaaa",
        "mp9.aaaaaa",
        "ap1.aaaaaa",
        "nonsense",
    ] {
        if bad == h {
            continue;
        }
        let o = e.commission(&r, bad);
        assert_eq!(s(&o.json(), &["reason"]), "handle_invalid", "{bad}");
    }
    let o = e2.commission(&r2, &h);
    assert_eq!(s(&o.json(), &["reason"]), "handle_invalid");
}

#[test]
fn receipt_readback_is_exact_and_diagnoses_damage_per_item() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a.txt", b"alpha\n"), ("b.txt", b"beta")]);
    let o = e.run(&["receipt", &r, "--json"]);
    assert_eq!(o.code, Some(3));
    assert_eq!(s(&o.json(), &["reason"]), "not_accepted");
    let o = e.run(&["receipt", &r, "--read", "materials/a.txt"]);
    assert!(o.stdout.is_empty());
    assert!(o.stderr.contains("not_accepted"));
    assert_eq!(e.commission(&r, &h).code, Some(0));

    // Damage one capture: its readback diagnoses damage, the other still reads.
    let cap = format!("{}/intake/1/m0001.bin", e.audit_dir(&r));
    std::fs::remove_file(&cap).unwrap();
    std::fs::write(&cap, b"alphX\n").unwrap();
    let o = e.run(&["receipt", &r, "--read", "materials/a.txt"]);
    assert_eq!(o.code, Some(3));
    assert!(o.stdout.is_empty(), "unverified bytes must not be written");
    let line = stewart::json::parse(o.stderr.trim_end().as_bytes()).unwrap();
    assert_eq!(s(&line, &["diagnostic"]), "item_damaged");
    assert_eq!(
        e.run(&["receipt", &r, "--read", "materials/b.txt"]).stdout,
        b"beta"
    );
    let j = e.run(&["receipt", &r, "--verify", "--json"]).json();
    let states: Vec<(String, String)> = at(&j, &["data", "items"])
        .as_arr()
        .unwrap()
        .iter()
        .map(|i| {
            (
                s(i, &["id"]).to_string(),
                s(i, &["verification"]).to_string(),
            )
        })
        .collect();
    assert!(states.contains(&("materials/a.txt".into(), "damaged".into())));
    assert!(states.contains(&("materials/b.txt".into(), "verified".into())));
    assert_eq!(
        at(&j, &["data", "verification", "all_items_verified"]).v,
        stewart::json::V::Bool(false)
    );
    std::fs::remove_file(&cap).unwrap();
    let o = e.run(&["receipt", &r, "--read", "materials/a.txt"]);
    assert!(o.stderr.contains("item_missing"));
    let o = e.run(&["receipt", &r, "--read", "materials/c.txt"]);
    assert!(o.stderr.contains("item_unknown"));
    // Without --verify the receipt says the bytes were not re-verified.
    let j = e.run(&["receipt", &r, "--json"]).json();
    assert_eq!(
        at(&j, &["data", "verification", "performed"]).v,
        stewart::json::V::Bool(false)
    );
}

#[test]
fn reads_change_nothing_and_mutations_only_add() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let mut before = e.inventory();
    for args in [
        vec!["status", r.as_str(), "--json"],
        vec!["receipt", r.as_str(), "--json"],
        vec!["status", "--archive", e.archive.as_str()],
    ] {
        e.run(&args);
        assert_eq!(before, e.inventory(), "{args:?} changed the archive");
    }
    for args in [
        vec!["commission", r.as_str(), h.as_str(), "--i-am-finished"],
        vec!["receipt", r.as_str(), "--verify"],
        vec!["prepare", r.as_str()],
        vec!["close", r.as_str()],
        vec!["close", r.as_str()],
        vec!["commission", r.as_str(), h.as_str(), "--i-am-finished"],
    ] {
        e.run(&args);
        let after = e.inventory();
        only_additions(&before, &after).unwrap_or_else(|m| panic!("{args:?}: {m}"));
        before = after;
    }
}

#[test]
fn references_never_select_another_store() {
    let e = Env::new();
    let r = e.new_ref();
    assert_eq!(
        s(
            &e.run(&["status", "stw1:nonsense", "--json"]).json(),
            &["reason"]
        ),
        "reference_invalid"
    );
    // A replaced archive at the same path is diagnosed, not used.
    std::fs::rename(&e.archive, e.path("moved-away")).unwrap();
    let o = e.run(&["status", &r, "--json"]);
    assert_eq!(s(&o.json(), &["reason"]), "archive_unavailable");
    e.run(&["new", &e.path("q-other"), "--archive", &e.archive]);
    let o = e.run(&["status", &r, "--json"]);
    assert_eq!(s(&o.json(), &["reason"]), "archive_replaced");
    // A copy of the archive can be read but never mutated.
    let copy = e.path("copy");
    assert!(
        std::process::Command::new("cp")
            .args(["-Rp", &e.path("moved-away"), &copy])
            .status()
            .unwrap()
            .success()
    );
    let id_store: Vec<&str> = r.split(':').collect();
    let r_copy = stewart::ids::encode_reference(id_store[1], id_store[2], &copy);
    let o = e.run(&["status", &r_copy, "--json"]);
    assert_eq!(o.code, Some(0), "{}", o.text());
    assert!(has(at(&o.json(), &["data"]), "archive_notice"));
    let o = e.run(&["prepare", &r_copy, "--json"]);
    assert_eq!(s(&o.json(), &["reason"]), "archive_moved_or_copied");
    // An unknown audit in the right store.
    let o = e.run(&[
        "status",
        &stewart::ids::encode_reference("aaaaaaaaaaaaaaaaa", id_store[2], &e.path("moved-away")),
        "--json",
    ]);
    assert_eq!(s(&o.json(), &["reason"]), "reference_unknown");
}

#[test]
fn close_before_acceptance_ends_the_reference_without_an_answer() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let o = e.run(&["close", &r, "--confirm", "cf1.aaaaaa", "--json"]);
    assert_eq!(s(&o.json(), &["reason"]), "confirmation_mismatch");
    let o = e.run(&["close", &r, "--json"]);
    let j = o.json();
    assert_eq!(s(&j, &["data", "closure"]), "complete");
    assert_eq!(
        at(&j, &["data", "accepted"]).v,
        stewart::json::V::Bool(false)
    );
    assert_eq!(s(&j, &["effects", "run"]), "not_started");
    assert_eq!(
        s(&e.commission(&r, &h).json(), &["reason"]),
        "reference_closed"
    );
    assert_eq!(
        s(&e.run(&["prepare", &r, "--json"]).json(), &["reason"]),
        "reference_closed"
    );
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "condition"]), "closed_before_launch");
    assert_eq!(s(&j, &["data", "headline", "accepted"]), "no");
    assert!(at(&j, &["next"]).as_arr().unwrap().is_empty());
    assert!(std::path::Path::new(&format!("{}/question.md", e.folder)).exists());
    assert_eq!(
        e.log_kinds(&r),
        ["reference", "prepared", "close_requested", "closed"]
    );
}

#[test]
fn a_damaged_log_is_diagnosed_never_repaired() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let log = format!("{}/log", e.audit_dir(&r));
    std::fs::write(format!("{log}/3.json"), b"{not json").unwrap();
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "condition"]), "acceptance_uncertain");
    assert_eq!(s(&j, &["data", "headline", "accepted"]), "unknown");
    assert_eq!(s(&j, &["data", "diagnostics", "0", "record"]), "log/3.json");
    let o = e.commission(&r, &h);
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "log_damaged");
    assert_eq!(s(&j, &["effects", "acceptance"]), "unknown");
    let o = e.run(&["close", &r, "--json"]);
    let j = o.json();
    assert_eq!(s(&j, &["outcome"]), "completed");
    assert_eq!(s(&j, &["data", "unfinished_reason"]), "log_damaged");
    assert_eq!(
        std::fs::read(format!("{log}/3.json")).unwrap(),
        b"{not json"
    );
    assert!(!std::path::Path::new(&format!("{log}/4.json")).exists());

    // Damage after a readable acceptance is log_damaged.
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    assert_eq!(e.commission(&r, &h).code, Some(0));
    std::fs::write(format!("{}/log/6.json", e.audit_dir(&r)), b"{}").unwrap();
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "condition"]), "log_damaged");
    assert_eq!(s(&j, &["data", "headline", "accepted"]), "yes");
}

#[test]
fn a_held_lock_is_an_intake_in_progress() {
    use std::os::fd::AsRawFd;
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let f = std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .open(format!("{}/active.lock", e.audit_dir(&r)))
        .unwrap();
    // The development lock is flock; the Linux lock is an OFD lock (same open
    // file description semantics, so each needs its own primitive here).
    #[cfg(target_os = "macos")]
    assert_eq!(
        unsafe { libc::flock(f.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) },
        0
    );
    #[cfg(target_os = "linux")]
    {
        let mut fl: libc::flock = unsafe { std::mem::zeroed() };
        fl.l_type = libc::F_WRLCK as libc::c_short;
        assert_eq!(
            unsafe { libc::fcntl(f.as_raw_fd(), 37, &mut fl as *mut libc::flock) },
            0
        );
    }
    let o = e.commission(&r, &h);
    assert_eq!(s(&o.json(), &["reason"]), "intake_in_progress");
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "condition"]), "intake_in_progress");
    drop(f);
    assert_eq!(e.commission(&r, &h).code, Some(0));
}

#[test]
fn an_unwritable_diagnostic_directory_keeps_both_causes() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a.py", b"one")]);
    std::fs::write(e.path("q/materials/a.py"), b"two").unwrap();
    let diag = format!("{}/diag", e.audit_dir(&r));
    std::process::Command::new("chmod")
        .args(["0500", &diag])
        .status()
        .unwrap();
    let o = e.commission(&r, &h);
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "selection_changed");
    assert_eq!(s(&j, &["effects", "diagnostic"]), "reported_only");
    let causes = at(&j, &["causes"]).as_arr().unwrap();
    assert_eq!(causes.len(), 2);
    assert_eq!(s(&causes[0], &["error"]), "selection_changed");
    assert_eq!(s(&causes[1], &["error"]), "EACCES");
}

#[test]
fn help_and_usage() {
    let e = Env::new();
    let o = e.run(&["help"]);
    assert_eq!(o.code, Some(0));
    assert!(o.text().contains("The manager's path"));
    for t in ["commands", "forms", "limits", "reader", "close"] {
        let o = e.run(&["help", t]);
        assert_eq!(o.code, Some(0), "{t}");
        assert!(!o.stdout.is_empty());
    }
    assert!(
        e.run(&["help", "forms"])
            .text()
            .contains("Formulate a working question")
    );
    assert_eq!(e.run(&["help", "nope"]).code, Some(2));
    assert_eq!(e.run(&["run"]).code, Some(2));
    assert_eq!(e.run(&["run", "stw1:x", "--detach"]).code, Some(2));
    let o = e.run(&["run", "stw1:x", "--json"]);
    assert_eq!(o.code, Some(3), "{}", o.text());
    assert_eq!(s(&o.json(), &["reason"]), "reference_invalid");
    assert_eq!(s(&o.json(), &["effects", "answer"]), "unchanged");
    assert_eq!(e.run(&[]).code, Some(2));
    assert_eq!(e.run(&["status", "--jsn"]).code, Some(2));
    assert_eq!(
        e.run(&["receipt", "stw1:x", "--read", "a", "--json"]).code,
        Some(2)
    );
}

#[test]
fn commission_uses_only_the_verified_pinned_arrangement() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let md = format!("{}/prep/1/arrangement.md", e.audit_dir(&r));
    let mut bytes = std::fs::read(&md).unwrap();
    bytes.push(b'!');
    std::fs::remove_file(&md).unwrap();
    std::fs::write(&md, &bytes).unwrap();
    let o = e.commission(&r, &h);
    assert_eq!(o.code, Some(4), "{}", o.text());
    let j = o.json();
    assert_eq!(s(&j, &["reason"]), "record_failed");
    assert_eq!(s(&j, &["effects", "acceptance"]), "absent");
    assert_eq!(s(&j, &["effects", "attempt"]), "none");
    assert_eq!(e.log_kinds(&r), ["reference", "prepared"]);
    // A fresh preparation pins a fresh arrangement and commissions.
    let h2 = s(
        &e.run(&["prepare", &r, "--json"]).json(),
        &["data", "prepared"],
    )
    .to_string();
    assert_eq!(e.commission(&r, &h2).code, Some(0));
}

#[test]
fn a_placements_world_is_the_verified_captures_and_pinned_arrangement() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a.py", b"one\r\ntwo"), ("sub/b.txt", b"")]);
    assert_eq!(e.commission(&r, &h).code, Some(0));
    // The live folder changes after acceptance; the world never consults it.
    std::fs::write(e.path("q/materials/a.py"), b"edited").unwrap();
    let audit = stewart::archive::Audit::open(&r).unwrap();
    let state = stewart::log::read(&audit);
    let w = stewart::world::load(&audit, &state).unwrap_or_else(|p| panic!("{p:?}"));
    assert_eq!(
        w.question.bytes().unwrap(),
        b"Audit our app to make sure there are no bugs.\n"
    );
    assert_eq!(w.question.lines, 1);
    let names: Vec<&str> = w.materials.iter().map(|m| m.name.as_str()).collect();
    assert_eq!(names, ["materials/a.py", "materials/sub/b.txt"]);
    let a = w.source("materials/a.py").unwrap();
    assert_eq!(a.bytes().unwrap(), b"one\r\ntwo");
    assert_eq!((a.size, a.lines), (8, 2));
    assert_eq!(a.read(5, 100).unwrap(), b"two");
    assert_eq!(w.source("materials/sub/b.txt").unwrap().lines, 0);
    assert!(w.source("materials/nope").is_none());
    assert_eq!(w.arrangement.family, "open-inquiry/1");
    assert_eq!(w.arrangement.anthropic_version, "2026-10-21");
    assert_eq!(w.arrangement.tool_names[0], "list");
    assert_eq!(w.directories, ["materials", "materials/sub"]);

    // A damaged capture is named by its receipt item; the others still load.
    let cap = format!("{}/intake/1/m0001.bin", e.audit_dir(&r));
    std::fs::remove_file(&cap).unwrap();
    std::fs::write(&cap, b"one\ntwo").unwrap();
    let problems = match stewart::world::load(&audit, &state) {
        Ok(_) => panic!("a damaged capture loaded"),
        Err(p) => p,
    };
    assert_eq!(
        problems.iter().map(|p| p.item.as_str()).collect::<Vec<_>>(),
        ["materials/a.py"]
    );
}
