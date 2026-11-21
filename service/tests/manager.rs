//! Manager commands through the real binary, for what the independent
//! release driver does not cover: the worked example packets, behavior whose
//! driver case runs only on Linux, host name rules its Linux runs cannot
//! observe, state read in process, and presentation wording the
//! specification leaves to the implementation. Release behavior: no fault or
//! sabotage controls are set.

mod common;
use common::*;

#[test]
fn worked_question_packets_prepare_with_full_or_limited_evidence() {
    let examples = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/questions");
    for (packet, family, third_file, omitted) in [
        (
            "open",
            "open-inquiry",
            "supplied-report.txt",
            &["a.py", "requirements.txt"][..],
        ),
        (
            "framing",
            "inquiry-framing",
            "supplied-report.txt",
            &["a.py", "supplied-report.txt"][..],
        ),
        ("comparison", "comparison", "b.py", &["b.py"][..]),
    ] {
        for omitted in [&[][..], omitted] {
            let e = Env::new();
            let original = examples.join(packet).join("submission");
            assert!(
                std::process::Command::new("cp")
                    .arg("-R")
                    .arg(&original)
                    .arg(&e.folder)
                    .status()
                    .unwrap()
                    .success()
            );
            let folder = std::path::Path::new(&e.folder);
            for name in omitted {
                std::fs::remove_file(folder.join("materials").join(name)).unwrap();
            }
            // The variant keeps the original body and only maps supplied files.
            let original_question = std::fs::read_to_string(original.join("question.md")).unwrap();
            let setting = "\ndestination: /var/tmp\n";
            assert!(original_question.contains(setting), "{packet}");
            let mut question =
                original_question.replacen(setting, &format!("\ndestination: {}\n", e.dest), 1);
            let roles_line = original_question
                .lines()
                .find_map(|l| l.strip_prefix("material-roles: "))
                .unwrap();
            let mappings = stewart::json::parse(roles_line.as_bytes()).unwrap();
            let kept = mappings
                .as_arr()
                .unwrap()
                .iter()
                .filter(|m| {
                    let source = s(m, &["source"]).strip_prefix("materials/").unwrap();
                    !omitted.contains(&source)
                })
                .map(|m| m.to_j())
                .collect();
            question = question.replacen(roles_line, &stewart::json::J::Arr(kept).string(), 1);
            std::fs::write(folder.join("question.md"), &question).unwrap();
            let reference = e.new_ref();
            let result = e.run(&["prepare", &reference, "--json"]);
            assert_eq!(
                result.code,
                Some(0),
                "{packet} {omitted:?}: {}",
                result.text()
            );
            let reply = result.json();
            assert_eq!(s(&reply, &["data", "settings", "family"]), family);
            let defects = at(&reply, &["data", "defects"]).as_arr().unwrap();
            let expected_advice = match (packet, omitted.is_empty()) {
                ("open", false) => Some(("suggestion", "subject")),
                ("comparison", false) => Some(("warning", "alternative")),
                _ => None,
            };
            assert_eq!(
                defects
                    .iter()
                    .map(|d| (s(d, &["severity"]), s(d, &["role"])))
                    .collect::<Vec<_>>(),
                expected_advice.into_iter().collect::<Vec<_>>()
            );
            let files = at(&reply, &["data", "materials", "files"])
                .as_arr()
                .unwrap();
            let mut expected: Vec<_> = ["a.py", "requirements.txt", third_file]
                .into_iter()
                .filter(|name| !omitted.contains(name))
                .map(|name| format!("materials/{name}"))
                .collect();
            expected.sort();
            assert_eq!(files.len(), expected.len(), "{packet} {omitted:?}");
            for (file, source) in files.iter().zip(expected) {
                assert_eq!(s(file, &["name"]), source);
                let bytes = std::fs::read(original.join(source)).unwrap();
                assert_eq!(s(file, &["sha256"]), stewart::util::sha256_hex(&bytes));
            }
            let body = original_question.split_once("\n---\n").unwrap().1;
            assert_eq!(
                s(&reply, &["data", "question", "body_sha256"]),
                stewart::util::sha256_hex(body.as_bytes())
            );
            assert_eq!(e.run(&["close", &reference, "--json"]).code, Some(0));
        }
    }
}

/// The human views carry the machine result in the implementation's own
/// wording: a refusal names its reason and effects, the concise status hides
/// the condition that `--details` shows, and once a commission is accepted
/// the concise status prints a receipt command that works as printed from an
/// unrelated directory, before and after close. Reads change nothing.
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
    assert!(t.contains("Commission: not accepted."), "{t}");
    assert!(t.contains("Run: not started."), "{t}");
    assert!(!t.contains("condition: preparing"), "{t}");
    assert!(!t.contains("Receipt:"), "{t}");
    let before = e.inventory();
    let detailed = e.run(&["status", &r, "--details"]).text();
    let machine = e.run(&["status", &r, "--json"]).json();
    assert!(detailed.contains("condition: preparing"), "{detailed}");
    assert!(t.contains(s(&machine, &["data", "summary"])), "{t}");
    assert!(detailed.contains(s(&machine, &["data", "summary"])));
    let listing = e.run(&["status", "--archive", &e.archive]).text();
    let expanded = e
        .run(&["status", "--archive", &e.archive, "--details"])
        .text();
    assert!(listing.contains(&format!("Reference: {r}")), "{listing}");
    assert!(listing.contains("Accepted: no"), "{listing}");
    assert!(!listing.contains("headline:"), "{listing}");
    assert!(expanded.contains("headline:"), "{expanded}");
    assert_eq!(before, e.inventory(), "presentation reads must not mutate");

    assert_eq!(e.commission(&r, &h).code, Some(0));
    for closed in [false, true] {
        if closed {
            assert_eq!(e.run(&["close", &r]).code, Some(0));
        }
        let before = e.inventory();
        let plain = e.run(&["status", &r]).text();
        let detailed = e.run(&["status", &r, "--details"]).text();
        let command = plain
            .lines()
            .find_map(|line| line.strip_prefix("Receipt: "))
            .unwrap_or_else(|| panic!("receipt command missing: {plain}"));
        assert!(detailed.contains(&format!("Receipt: {command}")));
        let receipt = std::process::Command::new("/bin/sh")
            .args(["-c", &format!("{command} --json")])
            .env_clear()
            .current_dir(&e.cwd)
            .output()
            .unwrap();
        assert!(receipt.status.success(), "{receipt:?}");
        let receipt = stewart::json::parse(&receipt.stdout).unwrap();
        assert_eq!(s(&receipt, &["data", "reference"]), r);
        assert_eq!(before, e.inventory(), "status and receipt are read-only");
    }
}

#[test]
fn new_reports_other_references_to_the_same_folder() {
    let e = Env::new();
    let r1 = e.new_ref();
    let o = e.run(&["new", &e.folder, "--archive", &e.archive, "--json"]);
    assert_eq!(o.code, Some(0), "{}", o.text());
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
}

/// Status reports each commissioned limit under its own quantity, from the
/// accepted preparation's settings, and no more usage than the log
/// establishes: zero before any run, every used amount unknown once the log
/// after the acceptance is damaged, and no allowances at all while the
/// acceptance itself is uncertain.
#[test]
fn status_reports_allowances_as_far_as_the_log_establishes_them() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    assert_eq!(e.commission(&r, &h).code, Some(0));
    let allowances = |e: &Env, r: &str| {
        let j = e.run(&["status", r, "--json"]).json();
        at(&j, &["data", "allowances"]).to_j().string()
    };
    assert_eq!(
        allowances(&e, &r),
        r#"{"turns":{"used":0,"reported":0,"estimated":0,"limit":200},"input_tokens":{"used":0,"reported":0,"estimated":0,"limit":20000000},"output_tokens":{"used":0,"reported":0,"estimated":0,"limit":400000}}"#
    );
    std::fs::write(format!("{}/log/6.json", e.audit_dir(&r)), b"{}").unwrap();
    let unknown = |limit: u64| {
        format!(
            r#"{{"used":"unknown","reported":"unknown","estimated":"unknown","limit":{limit}}}"#
        )
    };
    assert_eq!(
        allowances(&e, &r),
        format!(
            r#"{{"turns":{},"input_tokens":{},"output_tokens":{}}}"#,
            unknown(200),
            unknown(20_000_000),
            unknown(400_000)
        )
    );

    // Damage where an acceptance could be recorded: no limit is established.
    let e = Env::new();
    let (r, _) = e.prepared(&[("a", b"a")]);
    std::fs::write(format!("{}/log/3.json", e.audit_dir(&r)), b"{not json").unwrap();
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "condition"]), "acceptance_uncertain");
    assert_eq!(allowances(&e, &r), r#""unknown""#);
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
    // Hold an independent open file description write lock (F_OFD_SETLK).
    let mut fl: libc::flock = unsafe { std::mem::zeroed() };
    fl.l_type = libc::F_WRLCK as libc::c_short;
    assert_eq!(
        unsafe { libc::fcntl(f.as_raw_fd(), 37, &mut fl as *mut libc::flock) },
        0
    );
    let o = e.commission(&r, &h);
    assert_eq!(s(&o.json(), &["reason"]), "intake_in_progress");
    let j = e.run(&["status", &r, "--json"]).json();
    assert_eq!(s(&j, &["data", "condition"]), "intake_in_progress");
    drop(f);
    assert_eq!(e.commission(&r, &h).code, Some(0));
}

/// An unknown help topic is a usage error that names the topics there are;
/// the release build has no runtime topic.
#[test]
fn an_unknown_help_topic_is_a_usage_error_naming_the_topics() {
    #[cfg(not(feature = "claude-code"))]
    let (topics, unknown) = (
        "topics: commands, forms, limits, reader, close\n",
        ["nope", "runtime"].as_slice(),
    );
    #[cfg(feature = "claude-code")]
    let (topics, unknown) = (
        "topics: commands, forms, limits, reader, close, runtime\n",
        ["nope"].as_slice(),
    );
    let e = Env::new();
    for topic in unknown {
        let o = e.run(&["help", topic]);
        assert_eq!(o.code, Some(2), "{topic}");
        assert!(o.stdout.is_empty(), "{topic}");
        assert!(o.stderr.contains(topics), "{topic}: {}", o.stderr);
    }
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

#[test]
fn preparation_reports_a_missing_role_source_alongside_a_bad_destination_setting() {
    let e = Env::new();
    let reference = e.new_ref();
    let question = e.question("open-inquiry", "What does the report show?").replace(
        &format!("destination: {}", e.dest),
        "material-roles: [{\"role\":\"report\",\"source\":\"materials/missing\"}]\ndestination: relative",
    );
    std::fs::write(format!("{}/question.md", e.folder), question).unwrap();
    let reply = e.run(&["prepare", &reference, "--json"]).json();
    let defects = at(&reply, &["data", "defects"]).as_arr().unwrap();
    assert_eq!(
        defects
            .iter()
            .map(|d| s(d, &["reason"]))
            .collect::<Vec<_>>(),
        ["role_source_unknown", "setting_invalid"]
    );
    assert_eq!(s(&reply, &["reason"]), "role_source_unknown");
    assert_eq!(s(&reply, &["effects", "preparation"]), "none");
}

/// One `manager-mcp` session: initialize, then each `tools/call` of `calls`
/// as `(tool, arguments)`; returns each call's structured result in order.
fn manager_mcp(e: &Env, launch: &[&str], calls: &[(&str, String)]) -> Vec<stewart::json::Json> {
    use std::io::Write;
    let mut input = String::from(
        "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-11-25\",\"capabilities\":{\"tools\":{}},\"clientInfo\":{\"name\":\"test\",\"version\":\"1\"}}}\n{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}\n",
    );
    for (i, (tool, arguments)) in calls.iter().enumerate() {
        input.push_str(&format!(
            "{{\"jsonrpc\":\"2.0\",\"id\":{},\"method\":\"tools/call\",\"params\":{{\"name\":\"{tool}\",\"arguments\":{arguments}}}}}\n",
            i + 10
        ));
    }
    let mut child = std::process::Command::new(bin())
        .arg("manager-mcp")
        .args(launch)
        .current_dir(&e.cwd)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(input.as_bytes())
        .unwrap();
    let out = child.wait_with_output().unwrap();
    assert!(out.status.success(), "{out:?}");
    let replies: Vec<_> = String::from_utf8(out.stdout)
        .unwrap()
        .lines()
        .skip(1)
        .map(|l| stewart::json::parse(l.as_bytes()).unwrap())
        .collect();
    assert_eq!(replies.len(), calls.len());
    replies
        .iter()
        .map(|r| at(r, &["result", "structuredContent"]).clone())
        .collect()
}

/// In a directory that folds case, a source named in
/// another case is absent, and a candidate named in another case collides
/// with the existing one in a dry run and at creation instead of opening it.
/// The release driver qualifies on case-sensitive Linux filesystems, where
/// this host rule cannot be observed.
#[test]
fn a_case_alias_is_absent_and_cannot_claim_an_existing_candidate() {
    let e = Env::new();
    let ws = e.path("workspace");
    std::fs::create_dir_all(format!("{ws}/sources")).unwrap();
    std::fs::write(format!("{ws}/sources/a.txt"), b"alpha\n").unwrap();
    if !std::path::Path::new(&format!("{ws}/sources/A.TXT")).exists() {
        println!("SKIPPED: the scratch filesystem distinguishes case");
        return;
    }
    std::fs::create_dir(format!("{ws}/first")).unwrap();
    let call = |from: &str, destination: &str, create: bool| {
        (
            "assemble",
            format!(
                "{{\"fields\":{{\"family\":\"open-inquiry\",\"model\":\"m\",\"destination\":\"{}\",\"limit-turns\":\"4\",\"limit-input-tokens\":\"32000\",\"limit-output-tokens\":\"8000\"}},\"body\":\"Q?\",\"guidance\":null,\"directories\":[\"materials\"],\"files\":[{{\"name\":\"materials/a.txt\",\"from\":\"{from}\"}}],\"destination\":\"{destination}\",\"create\":{create}}}",
                e.dest
            ),
        )
    };
    let results = manager_mcp(
        &e,
        &["--workspace", &ws],
        &[
            call("A.TXT", "fresh", false),
            call("a.txt", "FIRST", false),
            call("a.txt", "FIRST", true),
        ],
    );
    assert_eq!(
        s(&results[0], &["problem", "reason"]),
        "candidate_source_failed"
    );
    assert_eq!(s(&results[0], &["problem", "pointer"]), "/files/0/from");
    for r in &results[1..] {
        assert_eq!(s(r, &["problem", "reason"]), "destination_exists");
        assert_eq!(s(r, &["problem", "pointer"]), "/destination");
        assert_eq!(s(r, &["writes", "state"]), "none");
    }
    assert!(
        std::fs::read_dir(format!("{ws}/first"))
            .unwrap()
            .next()
            .is_none(),
        "the existing candidate was not opened or written"
    );
    assert!(!std::path::Path::new(&format!("{ws}/fresh")).exists());
}
