//! States after launch, built with the crate's own writers: log
//! publication of the post-launch record bodies, payload and preparation
//! claims, and the return manifest. They stand in for the run and the
//! answer protocol, so delivery, close after a seal and status can be
//! exercised through the real binary. The writer recorded in each record is
//! the audit's recorded writer, exactly as the binary writes it.
//!
//! The test keeps its own copy of every byte it supplies (entry texts,
//! artifact bytes, the prepared answer and rendering it wrote), so a
//! delivered package is compared against that witness, never against
//! Stewart's records alone. Shared calls of the after-launch tests are here
//! too.

#![allow(dead_code)]
// Publication preconditions return the crate's `Fail` by value, as the
// crate itself does (see the allowance in lib.rs).
#![allow(clippy::result_large_err)]

use stewart::archive::Audit;
use stewart::bodies::{
    Action, Actor, CloseFlags, CloseRequested, EntryRec, Invocation, ProviderUse, RunEnded,
    RunObservations, RunStarted, SealRec, Version,
};
use stewart::json::{J, Json};
use stewart::log;
use stewart::usage::{Split, Usage};

use crate::common::{Env, Out};

const QUESTION: &[u8] = b"Audit our app to make sure there are no bugs.\n";

fn member(name: &str, role: &str, bytes: &[u8]) -> J {
    J::obj()
        .with("name", name)
        .with("role", role)
        .with("size", bytes.len() as u64)
        .with("sha256", stewart::util::sha256_hex(bytes))
}

pub fn open(r: &str) -> Audit {
    match Audit::open(r) {
        Ok(a) => a,
        Err(f) => panic!("{}: {}", f.reason, f.message),
    }
}

/// Publish one log record and return its number.
pub fn put(a: &Audit, kind: &'static str, body: J) -> u64 {
    match log::publish(a, kind, |_| Ok(body.clone())) {
        Ok(p) => p.n,
        Err(e) => panic!("publishing {kind}: {}", e.describe()),
    }
}

/// A reference with an accepted commission: new, prepare and commission
/// through the binary.
pub fn accepted(e: &Env) -> String {
    let (r, h) = e.prepared(&[("a.py", b"print(1)\n")]);
    let o = e.commission(&r, &h);
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    r
}

fn provider() -> ProviderUse {
    ProviderUse {
        base_url: "https://api.anthropic.com".into(),
        overridden: false,
        proxy: None,
        anthropic_version: "2026-10-21".into(),
    }
}

/// Publish `run_started` for placement `run` and create `runs/<run>`, as a
/// run does before its first request.
pub fn start_run(a: &Audit, run: u64) -> u64 {
    let st = log::read(a);
    let arrangement_sha256 = st
        .latest_prepared()
        .map(|p| p.body_obj().str("arrangement_sha256").unwrap().to_string())
        .unwrap();
    let n = put(
        a,
        "run_started",
        RunStarted {
            #[cfg(feature = "claude-code")]
            runtime: None,
            run,
            arrangement_sha256,
            provider: Some(provider()),
            observations: RunObservations::current(),
        }
        .to_j(),
    );
    if let Err(c) = stewart::runs::RunDir::create(a, run) {
        panic!("{}: {}", c.operation, c.error);
    }
    n
}

/// The run directory of placement `run`, for writing its captures.
fn run_dir(a: &Audit, run: u64) -> stewart::runs::RunDir {
    let dir = stewart::runs::open(a, run).unwrap();
    let stage = dir.open_dir("stage").unwrap();
    stewart::runs::RunDir {
        run,
        dir,
        stage,
        path: a.abs(&stewart::runs::dir_name(run)),
    }
}

/// Capture request `k` of placement `run` with a body of `body_bytes`
/// bytes and `max_tokens`, as the run does before its first attempt.
pub fn capture_request(a: &Audit, run: u64, k: u64, max_tokens: u64, body_bytes: usize) {
    let body = vec![b'x'; body_bytes];
    let capture = stewart::runs::request_capture(k, max_tokens, &body, &[b"{}"]);
    if let Err(c) = run_dir(a, run).write_request(k, &capture) {
        panic!("{}: {}", c.operation, c.error);
    }
}

/// Request `k` of placement `run`, captured and answered by one used
/// response whose usage the provider reported.
pub fn record_turn(a: &Audit, run: u64, k: u64, input: u64, output: u64) {
    use stewart::runs::{Headers, ProviderAttempt, ReportedUsage};
    use stewart::usage::Charge;
    capture_request(a, run, k, 16_000, 300);
    let attempt = ProviderAttempt {
        request: k,
        attempt: 1,
        started_at: "2026-11-02T14:03:11.402Z".into(),
        ended_at: "2026-11-02T14:03:12.214Z".into(),
        elapsed_ms: 812,
        timeout_seconds: 600,
        request_written: "complete".into(),
        outcome: "response".into(),
        credential_reflection: stewart::credential::Reflection::default(),
        status: Some(200),
        headers: Headers {
            content_type: vec!["application/json".into()],
            request_id: vec![],
            retry_after: vec![],
        },
        response: None,
        error: None,
        stop_reason: Some("tool_use".into()),
        model: None,
        usage: Some(ReportedUsage {
            input_tokens: input,
            cache_creation_input_tokens: 0,
            cache_read_input_tokens: 0,
            output_tokens: output,
        }),
        charged: Charge::reported(input, 0, 0, output),
        problem: None,
        then: "use".into(),
        delay_ms: None,
    };
    let name = stewart::runs::attempt_name(k, 1);
    if let Err(c) = run_dir(a, run).publish(a, "provider_attempt", &name, attempt.to_j()) {
        panic!("{}: {}", c.operation, c.error);
    }
}

/// One recorded entry the witness keeps: its ID, kind, label and bytes.
#[derive(Clone, Debug)]
pub struct Entry {
    pub id: String,
    pub kind: String,
    pub label: String,
    pub bytes: Vec<u8>,
    /// `Some("utf-8" | "binary")` for an artifact.
    pub encoding: Option<String>,
    pub payload: String,
}

fn add(
    a: &Audit,
    run: u64,
    kind: &str,
    label: &str,
    bytes: &[u8],
    encoding: Option<&str>,
) -> Entry {
    let st = log::read(a);
    let id = st.next_entry_id();
    let stored = match stewart::names::write_payload(a, &id, 1, bytes) {
        Ok(s) => s,
        Err(c) => panic!("{}: {}", c.operation, c.error),
    };
    let call = st.revision() + 1;
    let rec = EntryRec {
        action: Action::Add,
        tool: kind.to_string(),
        invocation: Invocation {
            run,
            tool_use_id: format!("toolu_fixture_{call}"),
            call,
        },
        target: None,
        created: Some(Version {
            id: id.clone(),
            version: 1,
            kind: kind.to_string(),
            label: label.to_string(),
            payload: stored.clone().into(),
            encoding: encoding.map(str::to_string),
            citations: encoding.is_none().then(Vec::new),
        }),
        revision: st.revision() + 1,
    };
    put(a, "entry", rec.to_j());
    Entry {
        id,
        kind: kind.to_string(),
        label: label.to_string(),
        bytes: bytes.to_vec(),
        encoding: encoding.map(str::to_string),
        payload: stored.file,
    }
}

/// Record an entry of a recording tool's kind, with no citations.
pub fn add_entry(a: &Audit, run: u64, kind: &str, label: &str, text: &str) -> Entry {
    add(a, run, kind, label, text.as_bytes(), None)
}

/// Record a text artifact.
pub fn add_artifact(a: &Audit, run: u64, label: &str, bytes: &[u8]) -> Entry {
    add(a, run, "record_artifact", label, bytes, Some("utf-8"))
}

/// The usage a fixture placement charged.
pub fn usage() -> Usage {
    Usage {
        #[cfg(feature = "claude-code")]
        harness: None,
        turns: Split {
            reported: 3,
            estimated: 1,
        },
        input_tokens: Split {
            reported: 1200,
            estimated: 300,
        },
        output_tokens: Split {
            reported: 400,
            estimated: 0,
        },
    }
}

/// Publish `run_ended` as the run records it.
pub fn end_run(a: &Audit, run: u64, ending: &str, cause: Option<&str>, seal: Option<u64>) -> u64 {
    put(
        a,
        "run_ended",
        RunEnded {
            run,
            ending: ending.to_string(),
            cause: cause.map(str::to_string),
            recorded_by: "run".to_string(),
            provider: None,
            requests: 4,
            attempts: 4,
            usage: usage(),
            notices: vec![],
            seal: seal.map(stewart::names::log_name),
            message: format!("fixture placement {run} ended {ending}"),
        }
        .to_j(),
    )
}

pub fn request_close(a: &Audit) -> u64 {
    put(
        a,
        "close_requested",
        CloseRequested {
            flags: CloseFlags::default(),
        }
        .to_j(),
    )
}

/// What a fixture seal wrote, for the witness.
#[derive(Clone, Debug)]
pub struct Sealed {
    pub record: u64,
    pub manifest: Vec<u8>,
    pub answer: Vec<u8>,
    pub rendering: Vec<u8>,
    /// The artifact members: member name and bytes.
    pub artifacts: Vec<(String, Vec<u8>)>,
}

/// Seal the current selection as the auditor of placement `run`, as a run's
/// `submit` does: claim `prepared/<n>`, write the answer, the rendering and
/// the return manifest, then publish the `seal` record. Delivery copies the
/// prepared answer and rendering by path without reading them, so here they
/// are opaque bytes naming the sealed revision. The manifest and the
/// artifact members are exact, because delivery and close decode the one
/// and verify the other. Every selected payload must still verify.
pub fn seal(a: &Audit, run: u64) -> Sealed {
    let st = log::read(a);
    let selection = st.selection();
    let revision = st.revision();
    let mut artifact_members = Vec::new();
    let mut artifacts = Vec::new();
    for c in &selection {
        let v = c.version;
        if !v.is_artifact() {
            continue;
        }
        let bytes = std::fs::read(format!("{}/{}", a.dir.path, v.payload.file)).unwrap();
        assert_eq!(
            stewart::util::sha256_hex(&bytes),
            v.payload.sha256,
            "the fixture seals intact payloads only"
        );
        let name = stewart::names::artifact_member(&v.id);
        artifact_members.push(member(&name, "artifact", &bytes));
        artifacts.push((name, bytes));
    }
    let answer = format!(
        "fixture answer: revision {revision}, {} entries\n",
        selection.len()
    )
    .into_bytes();
    let rendering = format!("fixture rendering: revision {revision}\n").into_bytes();
    let (n, dir) = stewart::names::claim_prepared(a).unwrap_or_else(|c| panic!("{}", c.error));
    let answer_sha256 = stewart::names::write_prepared_file(a, &dir, n, "answer.json", &answer)
        .unwrap_or_else(|c| panic!("{}", c.error));
    let rendering_sha256 = stewart::names::write_prepared_file(a, &dir, n, "answer.md", &rendering)
        .unwrap_or_else(|c| panic!("{}", c.error));
    let mut members = vec![
        member("question.md", "manager_question", QUESTION),
        member("answer.json", "answer", &answer),
        member("answer.md", "rendering", &rendering),
    ];
    members.extend(artifact_members);
    let mut manifest = J::obj()
        .with("schema", "stewart.return/2")
        .with("audit", a.id.as_str())
        .with("store", a.archive.store.as_str())
        .with("family", "open-inquiry/1")
        .with("renderer", "stewart.render/1")
        .with("writer", a.refile.writer_sha256.as_str())
        .with(
            "seal",
            J::obj()
                .with("actor", Actor::Auditor.name())
                .with("sealed_at", stewart::util::now_utc()),
        )
        .with("revision", revision)
        .with("members", J::Arr(members))
        .with("unproduced", J::Arr(vec![]))
        .bytes();
    manifest.push(b'\n');
    let (_, name) =
        stewart::names::write_manifest(a, &manifest).unwrap_or_else(|c| panic!("{}", c.error));
    let manifest_sha256 = stewart::util::sha256_hex(&manifest);
    let record = put(
        a,
        "seal",
        SealRec {
            actor: Actor::Auditor,
            prepared: n,
            answer_sha256,
            rendering_sha256: Some(rendering_sha256),
            revision,
            manifest: name,
            manifest_sha256,
            invocation: Some(Invocation {
                run,
                tool_use_id: "toolu_fixture_submit".into(),
                call: 1000,
            }),
        }
        .to_j(),
    );
    Sealed {
        record,
        manifest,
        answer,
        rendering,
        artifacts,
    }
}

/// Deliver the seal as a run does after an auditor seal, holding the lock.
pub fn deliver_as_run(a: &Audit, destination: &str) -> stewart::delivery::Delivered {
    deliver_as_run_with(a, destination, None)
}

/// `deliver_as_run` with the run's stop input.
pub fn deliver_as_run_with(
    a: &Audit,
    destination: &str,
    stop: Option<std::sync::Arc<std::sync::atomic::AtomicBool>>,
) -> stewart::delivery::Delivered {
    let lock = a.try_lock().unwrap().expect("the lock is free");
    let d = stewart::delivery::deliver(
        a,
        &log::read(a),
        &stewart::delivery::Request {
            by: stewart::delivery::By::Run,
            destination: stewart::delivery::Destination::commissioned(destination),
            retries_losses_of: None,
            stop,
        },
    );
    drop(lock);
    d
}

/// An accepted audit whose placement 1 recorded three entries.
pub struct Scenario {
    pub r: String,
    pub audit: Audit,
    pub entries: Vec<Entry>,
}

/// Accepted, launched, three entries recorded in run 1: an account, an
/// observation and a text artifact (`e3`).
pub fn launched_with_entries(e: &Env) -> Scenario {
    let r = accepted(e);
    let audit = open(&r);
    start_run(&audit, 1);
    let entries = vec![
        add_entry(
            &audit,
            1,
            "record_account",
            "",
            "The excerpts support one finding.\n",
        ),
        add_entry(
            &audit,
            1,
            "record_observation",
            "restart",
            "Line 1 prints \"1\".\nNothing else.\n",
        ),
        add_artifact(&audit, 1, "trace", b"trace bytes\r\nsecond line"),
    ];
    Scenario { r, audit, entries }
}

/// Entries of a package directory, sorted.
pub fn package_members(path: &str) -> Vec<String> {
    let mut names: Vec<String> = std::fs::read_dir(path)
        .unwrap()
        .map(|d| d.unwrap().file_name().into_string().unwrap())
        .collect();
    names.sort();
    names
}

/// Check a delivered package against the witness: exactly the manifest, the
/// question, the answer, the rendering and the artifacts, byte for byte.
pub fn assert_package(path: &str, s: &Sealed) {
    let mut want = vec![
        "question.md".to_string(),
        "answer.json".to_string(),
        "answer.md".to_string(),
        "manifest.json".to_string(),
    ];
    for (m, _) in &s.artifacts {
        want.push(m.clone());
    }
    want.sort();
    assert_eq!(package_members(path), want, "package {path}");
    let read = |n: &str| std::fs::read(format!("{path}/{n}")).unwrap();
    assert_eq!(read("manifest.json"), s.manifest);
    assert_eq!(read("question.md"), QUESTION);
    assert_eq!(read("answer.json"), s.answer);
    assert_eq!(read("answer.md"), s.rendering);
    for (m, b) in &s.artifacts {
        assert_eq!(&read(m), b, "{m}");
    }
}

/// The path of delivery attempt `attempt`'s package of reference `r` in
/// `dest`.
pub fn package(dest: &str, r: &str, attempt: u64) -> String {
    format!(
        "{dest}/{}",
        stewart::names::package_name(r.split(':').nth(1).unwrap(), attempt)
    )
}

/// `close REF [extra…] --json`.
pub fn close(e: &Env, r: &str, extra: &[&str]) -> Out {
    close_faulted(e, r, extra, None)
}

/// `close REF [extra…] --json`, with `STEWART_TEST_FAULT` set to `fault`
/// when given (test builds only).
pub fn close_faulted(e: &Env, r: &str, extra: &[&str], fault: Option<&str>) -> Out {
    let mut args = vec!["close", r];
    args.extend_from_slice(extra);
    args.push("--json");
    match fault {
        Some(f) => e.run_env(&args, &[("STEWART_TEST_FAULT", f)]),
        None => e.run(&args),
    }
}

/// `status REF --json`, which must complete.
pub fn status(e: &Env, r: &str) -> Json {
    let o = e.run(&["status", r, "--json"]);
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    o.json()
}
