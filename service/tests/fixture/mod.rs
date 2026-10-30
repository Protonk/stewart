//! States after launch, built with the foundation's own writers: log
//! publication of the post-launch record bodies, payload and preparation
//! claims, and the return manifest. They stand in for the run and the
//! answer protocol, so delivery, close after a seal and status can be
//! exercised through the real binary. The writer recorded in each record is
//! the audit's recorded writer, exactly as the binary writes it.
//!
//! The test keeps its own copy of every byte it supplies (entry texts,
//! artifact bytes, the prepared answer and rendering it wrote), so a
//! delivered package is compared against that witness, never against
//! Stewart's records alone.

#![allow(dead_code)]
// Publication preconditions return the crate's `Fail` by value, as the
// crate itself does (see the allowance in lib.rs).
#![allow(clippy::result_large_err)]

use stewart::archive::Audit;
use stewart::bodies::{
    Action, Actor, CloseFlags, CloseRequested, EntryRec, Invocation, ProviderUse, RunEnded,
    RunObservations, RunStarted, SealRec, Version,
};
use stewart::json::{self, J};
use stewart::log;
use stewart::returns::{Manifest, Member, Unproduced};
use stewart::usage::{Split, Usage};

use crate::common::Env;

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

pub fn provider() -> ProviderUse {
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
    start_run_with(a, run, provider())
}

pub fn start_run_with(a: &Audit, run: u64, provider: ProviderUse) -> u64 {
    let st = log::read(a);
    let arrangement_sha256 = st
        .latest_prepared()
        .map(|p| p.body_obj().str("arrangement_sha256").unwrap().to_string())
        .unwrap();
    let n = put(
        a,
        "run_started",
        RunStarted {
            run,
            arrangement_sha256,
            provider,
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
    pub manifest_sha256: String,
    pub answer: Vec<u8>,
    /// `None` when the rendering is unproduced.
    pub rendering: Option<Vec<u8>>,
    /// Produced artifacts: member name and bytes.
    pub artifacts: Vec<(String, Vec<u8>)>,
    /// Unproduced entry IDs and their failures.
    pub unproduced: Vec<(String, String)>,
}

fn heading(kind: &str) -> String {
    if kind == "record_artifact" {
        return "Artifact".into();
    }
    let k = kind.trim_start_matches("record_").replace('_', " ");
    let mut c = k.chars();
    match c.next() {
        Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
        None => k,
    }
}

/// Seal the selection at log position `through` (the end of the log when
/// `None`) as `actor`, writing `prepared/<n>` per QUESTION-FORMS and the
/// return manifest, then the `seal` record. A selected payload whose bytes
/// do not verify is written in its unproduced form, and the rendering is
/// then unproduced too (8.1).
pub fn seal(a: &Audit, actor: Actor, through: Option<u64>, run: u64) -> Sealed {
    let st = log::read(a);
    let through = through.unwrap_or(u64::MAX);
    let selection = st.selection_through(through);
    let revision = st.revision_through(through);
    let mut lines = Vec::new();
    let mut members_after = Vec::new();
    let mut artifacts = Vec::new();
    let mut unproduced = Vec::new();
    let mut rendering = b"Rendered by Stewart. Entry text is attributed to the auditor.\n".to_vec();
    for c in &selection {
        let v = c.version;
        let path = format!("{}/{}", a.dir.path, v.payload.file);
        let bytes = std::fs::read(&path);
        let failure = match &bytes {
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Some("missing"),
            Err(_) => Some("unreadable"),
            Ok(b)
                if stewart::util::sha256_hex(b) != v.payload.sha256
                    || b.len() as u64 != v.payload.size =>
            {
                Some("damaged")
            }
            Ok(_) => None,
        };
        let head = format!(
            "{{\"id\":{},\"version\":{},\"kind\":{},\"label\":{}",
            json::quote(&v.id),
            v.version,
            json::quote(&v.kind),
            json::quote(&v.label)
        );
        if let Some(f) = failure {
            lines.push(format!(
                "{head},\"unproduced\":{{\"sha256\":\"{}\",\"size\":{},\"failure\":\"{f}\"}}}}",
                v.payload.sha256, v.payload.size
            ));
            unproduced.push((v.id.clone(), f.to_string()));
            continue;
        }
        let bytes = bytes.unwrap();
        let mut title = format!("\n## {} — {}", heading(&v.kind), v.id);
        if !v.label.is_empty() {
            title.push_str(&format!(" · {}", v.label));
        }
        rendering.extend_from_slice(format!("{title}\n\n").as_bytes());
        if v.is_artifact() {
            let member = stewart::names::artifact_member(&v.id);
            lines.push(format!(
                "{head},\"encoding\":{},\"member\":\"{member}\",\"size\":{},\"sha256\":\"{}\"}}",
                json::quote(v.encoding.as_deref().unwrap_or("utf-8")),
                v.payload.size,
                v.payload.sha256
            ));
            members_after.push(Member {
                name: member.clone(),
                role: "artifact".into(),
                size: v.payload.size,
                sha256: v.payload.sha256.clone(),
            });
            artifacts.push((member, bytes.clone()));
        } else {
            lines.push(format!(
                "{head},\"text\":{},\"citations\":[]}}",
                json::quote(&String::from_utf8_lossy(&bytes))
            ));
        }
        let text = String::from_utf8_lossy(&bytes).into_owned();
        if text.is_empty() {
            rendering.extend_from_slice(b"*No text recorded.*\n");
        } else {
            for l in text.strip_suffix('\n').unwrap_or(&text).split('\n') {
                if l.is_empty() {
                    rendering.extend_from_slice(b">\n");
                } else {
                    rendering.extend_from_slice(format!("> {l}\n").as_bytes());
                }
            }
        }
    }
    let answer = if lines.is_empty() {
        format!("{{\"schema\":\"stewart.answer/1\",\"revision\":{revision},\"entries\":[]}}\n")
    } else {
        format!(
            "{{\"schema\":\"stewart.answer/1\",\"revision\":{revision},\"entries\":[\n{}]}}\n",
            lines.join(",\n")
        )
    }
    .into_bytes();
    if selection.is_empty() {
        rendering = b"No answer entries recorded.\n".to_vec();
    }
    let rendering = unproduced.is_empty().then_some(rendering);
    let (n, dir) = stewart::names::claim_prepared(a).unwrap_or_else(|c| panic!("{}", c.error));
    let answer_sha = stewart::names::write_prepared_file(a, &dir, n, "answer.json", &answer)
        .unwrap_or_else(|c| panic!("{}", c.error));
    let mut members = vec![Member {
        name: "answer.json".into(),
        role: "answer".into(),
        size: answer.len() as u64,
        sha256: answer_sha.clone(),
    }];
    let rendering_sha = rendering.as_ref().map(|r| {
        let sha = stewart::names::write_prepared_file(a, &dir, n, "answer.md", r)
            .unwrap_or_else(|c| panic!("{}", c.error));
        members.push(Member {
            name: "answer.md".into(),
            role: "rendering".into(),
            size: r.len() as u64,
            sha256: sha.clone(),
        });
        sha
    });
    members.extend(members_after);
    let mut unproduced_m: Vec<Unproduced> = unproduced
        .iter()
        .map(|(id, f)| Unproduced {
            name: id.clone(),
            role: "entry".into(),
            failure: f.clone(),
            dependency: None,
        })
        .collect();
    if !unproduced.is_empty() {
        unproduced_m.push(Unproduced {
            name: "answer.md".into(),
            role: "rendering".into(),
            failure: "not_rendered".into(),
            dependency: Some(unproduced.iter().map(|(id, _)| id.clone()).collect()),
        });
    }
    let manifest = Manifest {
        audit: a.id.clone(),
        store: a.archive.store.clone(),
        family: "open-inquiry/1".into(),
        renderer: "stewart.render/1".into(),
        writer: a.refile.writer_sha256.clone(),
        actor,
        sealed_at: stewart::util::now_utc(),
        revision,
        members,
        unproduced: unproduced_m,
    };
    let bytes = manifest.bytes();
    let (_, name) =
        stewart::names::write_manifest(a, &bytes).unwrap_or_else(|c| panic!("{}", c.error));
    let manifest_sha256 = stewart::util::sha256_hex(&bytes);
    let record = put(
        a,
        "seal",
        SealRec {
            actor,
            prepared: n,
            answer_sha256: answer_sha,
            rendering_sha256: rendering_sha,
            revision,
            manifest: name,
            manifest_sha256: manifest_sha256.clone(),
            invocation: (actor == Actor::Auditor).then(|| Invocation {
                run,
                tool_use_id: "toolu_fixture_submit".into(),
                call: 1000,
            }),
        }
        .to_j(),
    );
    Sealed {
        record,
        manifest: bytes,
        manifest_sha256,
        answer,
        rendering,
        artifacts,
        unproduced,
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

/// A placement with three entries (an account, an observation and a text
/// artifact) that the auditor sealed and the run delivered to `dest`.
pub struct Scenario {
    pub r: String,
    pub audit: Audit,
    pub entries: Vec<Entry>,
}

/// Accepted, launched, three entries recorded in run 1.
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
/// answer, the rendering (unless unproduced) and the produced artifacts,
/// byte for byte.
pub fn assert_package(path: &str, s: &Sealed) {
    let mut want = vec!["answer.json".to_string(), "manifest.json".to_string()];
    if s.rendering.is_some() {
        want.push("answer.md".to_string());
    }
    for (m, _) in &s.artifacts {
        want.push(m.clone());
    }
    want.sort();
    assert_eq!(package_members(path), want, "package {path}");
    let read = |n: &str| std::fs::read(format!("{path}/{n}")).unwrap();
    assert_eq!(read("manifest.json"), s.manifest);
    assert_eq!(read("answer.json"), s.answer);
    if let Some(r) = &s.rendering {
        assert_eq!(&read("answer.md"), r);
    }
    for (m, b) in &s.artifacts {
        assert_eq!(&read(m), b, "{m}");
    }
}
