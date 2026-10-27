//! Black-box comparisons; fixtures and command streams remain for inspection.
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::cell::Cell;
use std::fs;
use std::os::unix::fs::symlink;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::time::{SystemTime, UNIX_EPOCH};
struct Case {
    root: PathBuf,
    bundle: PathBuf,
    request: PathBuf,
    question: PathBuf,
    material: PathBuf,
    calls: Cell<u32>,
}
fn hash(b: &[u8]) -> String {
    format!("{:x}", Sha256::digest(b))
}
impl Case {
    fn new(name: &str) -> Self {
        let base = Path::new(env!("CARGO_MANIFEST_DIR")).join("evidence");
        fs::create_dir_all(&base).unwrap();
        let root = base.join(format!(
            "{name}-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&root).unwrap();
        let bundle = root.join("bundle");
        fs::create_dir(&bundle).unwrap();
        let question = root.join("question.md");
        let material = root.join("material.bin");
        fs::write(
            &question,
            b"Does the captured selection support this original question?\n",
        )
        .unwrap();
        fs::write(&material, b"selected\x00material\xff\n").unwrap();
        let request = root.join("request.json");
        let c = Self {
            root,
            bundle,
            request,
            question,
            material,
            calls: Cell::new(0),
        };
        c.write_request();
        c
    }
    fn request_value(&self) -> Value {
        let members = [
            ("question", "question", &self.question, "QUESTION.md"),
            ("specimen", "material", &self.material, "data/specimen.bin"),
        ]
        .iter()
        .map(|(id, role, path, view)| {
            let b = fs::read(path).unwrap();
            json!({"id":id,"role":role,"source":path,"view":view,"size":b.len(),"sha256":hash(&b)})
        })
        .collect::<Vec<_>>();
        json!({"schema":"stewart.commission-request/1","request_id":"selected-01","custodian":"manager","grants":"Inspect these selected bytes.","limits":"No network or live writer access.","members":members})
    }
    fn write_request(&self) {
        fs::write(
            &self.request,
            serde_json::to_vec_pretty(&self.request_value()).unwrap(),
        )
        .unwrap();
    }
    fn run(&self, args: &[&str]) -> Output {
        let n = self.calls.get() + 1;
        self.calls.set(n);
        let o = Command::new(env!("CARGO_BIN_EXE_stewart-commission"))
            .args(args)
            .current_dir(&self.root)
            .output()
            .unwrap();
        fs::write(
            self.root.join(format!("command-{n:03}.json")),
            serde_json::to_vec(&json!({"args":args,"exit":o.status.code()})).unwrap(),
        )
        .unwrap();
        fs::write(self.root.join(format!("command-{n:03}.stdout")), &o.stdout).unwrap();
        fs::write(self.root.join(format!("command-{n:03}.stderr")), &o.stderr).unwrap();
        o
    }
    fn intake(&self, op: &str) -> Output {
        self.run(&[
            op,
            "--request",
            self.request.to_str().unwrap(),
            "--bundle",
            self.bundle.to_str().unwrap(),
        ])
    }
    fn inspect(&self) -> Output {
        self.run(&["inspect", "--bundle", self.bundle.to_str().unwrap()])
    }
    fn read(&self, id: &str) -> Output {
        self.run(&[
            "read",
            "--bundle",
            self.bundle.to_str().unwrap(),
            "--member",
            id,
        ])
    }
}
fn value(o: &Output) -> Value {
    serde_json::from_slice(&o.stdout).unwrap_or_else(|_| {
        panic!(
            "stdout={} stderr={}",
            String::from_utf8_lossy(&o.stdout),
            String::from_utf8_lossy(&o.stderr)
        )
    })
}
fn ok(o: &Output) {
    assert!(o.status.success(), "{}", String::from_utf8_lossy(&o.stderr));
}
fn reason(o: &Output) -> String {
    serde_json::from_slice::<Value>(&o.stderr).unwrap()["error"]["reason"]
        .as_str()
        .unwrap()
        .to_owned()
}
#[test]
fn original_bytes_survive_source_edits_and_move() {
    let c = Case::new("independent");
    let expected = fs::read(&c.material).unwrap();
    let original_request = fs::read(&c.request).unwrap();
    let a = c.intake("accept");
    ok(&a);
    let receipt = value(&a)["receipt_sha256"].as_str().unwrap().to_owned();
    fs::write(&c.material, b"later manager edit").unwrap();
    ok(&c.intake("accept"));
    assert_eq!(c.read("specimen").stdout, expected);
    assert_eq!(c.read("@request").stdout, original_request);
    let moved = c.root.join("elsewhere");
    fs::rename(&c.bundle, &moved).unwrap();
    let o = c.run(&[
        "read",
        "--bundle",
        moved.to_str().unwrap(),
        "--member",
        "specimen",
        "--receipt-sha256",
        &receipt,
    ]);
    ok(&o);
    assert_eq!(o.stdout, expected);
}
#[test]
fn input_change_refuses_then_explicit_completion_preserves_attempt() {
    let c = Case::new("completion");
    let original = fs::read(&c.material).unwrap();
    fs::write(&c.material, b"changed").unwrap();
    let fail = c.intake("accept");
    assert_eq!(reason(&fail), "binding_mismatch");
    assert_eq!(c.inspect().status.code(), Some(3));
    let before = fs::read_dir(&c.bundle)
        .unwrap()
        .map(|e| {
            let p = e.unwrap().path();
            (p.clone(), fs::read(p).unwrap())
        })
        .collect::<Vec<_>>();
    assert_eq!(reason(&c.intake("accept")), "intake_incomplete");
    fs::write(&c.material, &original).unwrap();
    ok(&c.intake("complete"));
    for (p, b) in before {
        assert_eq!(fs::read(p).unwrap(), b);
    }
    assert_eq!(c.read("specimen").stdout, original);
}
#[test]
fn incomplete_disposition_retains_bytes_and_never_accepts() {
    let c = Case::new("disposition");
    fs::write(&c.material, b"changed").unwrap();
    assert!(!c.intake("accept").status.success());
    let before = fs::read_dir(&c.bundle)
        .unwrap()
        .map(|e| {
            let p = e.unwrap().path();
            (p.clone(), fs::read(p).unwrap())
        })
        .collect::<Vec<_>>();
    let a = c.run(&[
        "abandon",
        "--bundle",
        c.bundle.to_str().unwrap(),
        "--actor",
        "manager",
        "--reason",
        "Original source unavailable; preserve incomplete delivery.",
    ]);
    ok(&a);
    assert_eq!(value(&c.inspect())["state"], "incomplete_acknowledged");
    assert!(!c.bundle.join("ACCEPTED.json").exists());
    for (p, b) in before {
        assert_eq!(fs::read(p).unwrap(), b);
    }
    assert_eq!(reason(&c.intake("complete")), "intake_disposed");
}
#[test]
fn nested_escaped_duplicate_refuses_before_material_effect() {
    let c = Case::new("duplicate");
    let raw = fs::read_to_string(&c.request).unwrap().replace(
        "\"id\": \"question\"",
        "\"id\": \"question\", \"\\u0069d\": \"question\"",
    );
    fs::write(&c.request, raw).unwrap();
    assert_eq!(reason(&c.intake("accept")), "duplicate_key");
    assert_eq!(fs::read_dir(&c.bundle).unwrap().count(), 0);
}
#[test]
fn links_and_special_files_do_not_become_inputs() {
    let c = Case::new("unsafe-source");
    let original = c.root.join("original.bin");
    fs::rename(&c.material, &original).unwrap();
    symlink(&original, &c.material).unwrap();
    assert_eq!(reason(&c.intake("accept")), "unsafe_path");
    assert!(!c.bundle.join("ACCEPTED.json").exists());
    let q = Case::new("fifo-source");
    fs::remove_file(&q.material).unwrap();
    let p = std::ffi::CString::new(q.material.to_str().unwrap()).unwrap();
    assert_eq!(unsafe { libc::mkfifo(p.as_ptr(), 0o600) }, 0);
    assert_eq!(reason(&q.intake("accept")), "not_regular");
    let parent = Case::new("unsafe-parent");
    let link = parent.root.join("linked");
    symlink(&parent.root, &link).unwrap();
    let o = parent.run(&[
        "accept",
        "--request",
        parent.request.to_str().unwrap(),
        "--bundle",
        link.join("bundle").to_str().unwrap(),
    ]);
    assert_eq!(reason(&o), "unsafe_path");
    assert_eq!(fs::read_dir(&parent.bundle).unwrap().count(), 0);
}
#[test]
fn selected_recovery_survives_unrelated_damage_but_not_own_damage() {
    let c = Case::new("damage");
    ok(&c.intake("accept"));
    let a: Value =
        serde_json::from_slice(&fs::read(c.bundle.join("ACCEPTED.json")).unwrap()).unwrap();
    let specimen = a["members"][1]["path"].as_str().unwrap();
    fs::write(c.bundle.join(specimen), b"corrupt").unwrap();
    assert_eq!(c.inspect().status.code(), Some(3));
    let q = c.read("question");
    ok(&q);
    assert_eq!(q.stdout, fs::read(&c.question).unwrap());
    assert_eq!(
        serde_json::from_slice::<Value>(&q.stderr).unwrap()["whole_bundle_integrity"],
        "damaged"
    );
    assert_eq!(reason(&c.read("specimen")), "binding_mismatch");
    assert_eq!(reason(&c.intake("accept")), "accepted_material_damaged");
}
#[test]
fn external_receipt_pin_and_unknown_fields_are_enforced() {
    let c = Case::new("pin");
    let a = c.intake("accept");
    ok(&a);
    let pin = value(&a)["receipt_sha256"].as_str().unwrap().to_owned();
    let mut raw = fs::read(c.bundle.join("ACCEPTED.json")).unwrap();
    raw.push(b' ');
    fs::write(c.bundle.join("ACCEPTED.json"), raw).unwrap();
    let o = c.run(&[
        "inspect",
        "--bundle",
        c.bundle.to_str().unwrap(),
        "--receipt-sha256",
        &pin,
    ]);
    assert_eq!(reason(&o), "binding_mismatch");
    let other = Case::new("unknown");
    let mut r = other.request_value();
    r["unexpected"] = json!(true);
    fs::write(&other.request, serde_json::to_vec(&r).unwrap()).unwrap();
    assert_eq!(reason(&other.intake("accept")), "invalid_record");
    assert_eq!(fs::read_dir(&other.bundle).unwrap().count(), 0);
}
#[test]
fn constructed_prepublication_interruption_completes_without_overwrite() {
    let c = Case::new("prepublication");
    ok(&c.intake("accept"));
    let accepted = fs::read(c.bundle.join("ACCEPTED.json")).unwrap();
    fs::rename(
        c.bundle.join("ACCEPTED.json"),
        c.root.join("independent-accepted-witness.json"),
    )
    .unwrap();
    let before = fs::read_dir(&c.bundle)
        .unwrap()
        .map(|e| {
            let p = e.unwrap().path();
            (p.clone(), fs::read(p).unwrap())
        })
        .collect::<Vec<_>>();
    ok(&c.intake("complete"));
    assert_ne!(fs::read(c.bundle.join("ACCEPTED.json")).unwrap(), accepted);
    for (p, b) in before {
        assert_eq!(fs::read(p).unwrap(), b);
    }
    assert_eq!(c.read("specimen").stdout, fs::read(&c.material).unwrap());
}
#[test]
fn concurrent_mutator_is_refused_and_healthy_control_succeeds() {
    use std::os::fd::AsRawFd;
    let c = Case::new("lock");
    let dir = fs::File::open(&c.bundle).unwrap();
    assert_eq!(
        unsafe { libc::flock(dir.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) },
        0
    );
    assert_eq!(reason(&c.intake("accept")), "bundle_busy");
    drop(dir);
    ok(&c.intake("accept"));
}
#[test]
fn incomplete_intent_stage_supports_explicit_completion() {
    let c = Case::new("intent-publication");
    ok(&c.intake("accept"));
    let intent = fs::read(c.bundle.join("INTENT.json")).unwrap();
    let fresh = c.root.join("fresh");
    fs::create_dir(&fresh).unwrap();
    fs::write(fresh.join("INTENT.stage"), &intent).unwrap();
    let o = c.run(&[
        "complete",
        "--request",
        c.request.to_str().unwrap(),
        "--bundle",
        fresh.to_str().unwrap(),
    ]);
    ok(&o);
    assert_eq!(fs::read(fresh.join("INTENT.stage")).unwrap(), intent);
}

#[test]
fn foreign_writer_cannot_complete_or_dispose_but_readback_is_independent() {
    let c = Case::new("writer-binding");
    let original = fs::read(&c.material).unwrap();
    fs::write(&c.material, b"changed").unwrap();
    assert!(!c.intake("accept").status.success());
    fs::write(&c.material, original).unwrap();
    let path = c.bundle.join("INTENT.json");
    let raw = fs::read(&path).unwrap();
    let mut intent: Value = serde_json::from_slice(&raw).unwrap();
    intent["writer_sha256"] = json!("0".repeat(64));
    fs::write(&path, serde_json::to_vec(&intent).unwrap()).unwrap();
    assert_eq!(reason(&c.intake("complete")), "writer_mismatch");
    let o = c.run(&[
        "abandon",
        "--bundle",
        c.bundle.to_str().unwrap(),
        "--actor",
        "manager",
        "--reason",
        "acknowledge incomplete",
    ]);
    assert_eq!(reason(&o), "writer_mismatch");
    assert_eq!(value(&c.inspect())["state"], "incomplete");
    fs::write(path, raw).unwrap();
    ok(&c.intake("complete"));
    ok(&c.read("question"));
}
#[test]
fn damaged_intent_acknowledgment_preserves_unresolved_original() {
    let c = Case::new("damaged-intent");
    fs::write(&c.material, b"changed").unwrap();
    assert!(!c.intake("accept").status.success());
    fs::write(c.bundle.join("INTENT.json"), b"{").unwrap();
    let o = c.run(&[
        "abandon",
        "--bundle",
        c.bundle.to_str().unwrap(),
        "--actor",
        "manager",
        "--reason",
        "Keep unknown original outcome and all evidence",
    ]);
    ok(&o);
    assert_eq!(value(&o)["state"], "unresolved_acknowledged");
    let i = c.inspect();
    assert_eq!(i.status.code(), Some(3));
    assert_eq!(value(&i)["state"], "unresolved_acknowledged");
    assert_eq!(fs::read(c.bundle.join("INTENT.json")).unwrap(), b"{");
}

#[test]
fn published_intent_without_attempt_requires_explicit_completion() {
    let c = Case::new("intent-without-attempt");
    ok(&c.intake("accept"));
    let intent = fs::read(c.bundle.join("INTENT.json")).unwrap();
    let fresh = c.root.join("fresh");
    fs::create_dir(&fresh).unwrap();
    fs::write(fresh.join("INTENT.json"), &intent).unwrap();
    fs::write(fresh.join("INTENT.stage"), &intent).unwrap();
    let args = [
        "accept",
        "--request",
        c.request.to_str().unwrap(),
        "--bundle",
        fresh.to_str().unwrap(),
    ];
    assert_eq!(reason(&c.run(&args)), "intake_incomplete");
    assert_eq!(fs::read_dir(&fresh).unwrap().count(), 2);
    let args = [
        "complete",
        "--request",
        c.request.to_str().unwrap(),
        "--bundle",
        fresh.to_str().unwrap(),
    ];
    ok(&c.run(&args));
    assert_eq!(fs::read(fresh.join("INTENT.json")).unwrap(), intent);
}
#[test]
fn disposition_binding_is_shared_by_inspection_intake_and_replay() {
    let c = Case::new("disposition-binding");
    fs::write(&c.material, b"changed").unwrap();
    assert!(!c.intake("accept").status.success());
    let args = [
        "abandon",
        "--bundle",
        c.bundle.to_str().unwrap(),
        "--actor",
        "manager",
        "--reason",
        "Preserve partial bytes",
    ];
    ok(&c.run(&args));
    ok(&c.run(&args));
    assert_eq!(reason(&c.intake("accept")), "intake_disposed");
    ok(&c.inspect());
    let path = c.bundle.join("ABANDONED.json");
    let raw = fs::read(&path).unwrap();
    let mut wrong: Value = serde_json::from_slice(&raw).unwrap();
    wrong["intent_sha256"] = json!("0".repeat(64));
    fs::write(&path, serde_json::to_vec(&wrong).unwrap()).unwrap();
    for o in [
        c.inspect(),
        c.intake("accept"),
        c.intake("complete"),
        c.run(&args),
    ] {
        assert_eq!(reason(&o), "binding_mismatch");
    }
    fs::write(&path, b"{").unwrap();
    for o in [
        c.inspect(),
        c.intake("accept"),
        c.intake("complete"),
        c.run(&args),
    ] {
        assert_eq!(reason(&o), "invalid_json");
    }
    let mut unsupported: Value = serde_json::from_slice(&raw).unwrap();
    unsupported["schema"] = json!("unavailable/99");
    fs::write(&path, serde_json::to_vec(&unsupported).unwrap()).unwrap();
    for o in [c.inspect(), c.intake("accept"), c.run(&args)] {
        assert_eq!(reason(&o), "unsupported_schema");
    }
    fs::write(&path, raw).unwrap();
    ok(&c.inspect());
    assert_eq!(reason(&c.intake("accept")), "intake_disposed");
}
