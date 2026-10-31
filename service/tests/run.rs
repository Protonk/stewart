//! `stewart run` end to end against a fake provider on a loopback listener
//! (INTERFACE 5.7, section 6).
//!
//! The fake provider binds 127.0.0.1 on port 0 in this process and answers
//! each connection from a script. It keeps every request's exact bytes as an
//! independent witness of what the run sent; the archive's captures are
//! compared with them. Each test runs the real binary from an unrelated
//! working directory with its own folder, archive and destination.
//!
//! The tool-calling and seal cases also exercise what the run calls: the
//! auditor's tools (`answer::execute`) and, after a seal, delivery
//! (`delivery::deliver`).

// The crate's log writer refuses with its full account by value.
#![allow(clippy::result_large_err)]

mod common;

use common::{Env, at, bin, s};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use stewart::json::{self, Json};

// ---------------------------------------------------------------------------
// The fake provider.

/// A reply computed from the request's body.
type Responder = Arc<dyn Fn(&[u8]) -> String + Send + Sync>;

/// What the fake provider does with one connection.
#[derive(Clone)]
#[cfg_attr(not(feature = "fault-injection"), allow(dead_code))]
enum Act {
    /// Read the request, answer with this status, extra headers and body.
    Reply(u16, Vec<(String, String)>, String),
    /// Read the request and never answer; hold the connection until the
    /// client closes it.
    Hang,
    /// Read the request and close without answering.
    Drop,
    /// Read the request, send a 200 head promising more body than it sends,
    /// then close.
    CutOff(String),
    /// Read the request and answer 200 with the body this computes from
    /// the request's body.
    Respond(Responder),
    /// Read the request and judge its body by what this provider accepts:
    /// answer 200 with the given body when it passes, else the Messages
    /// API's 400 naming the field (`Surface`).
    Judge(Surface, String),
}

struct Provider {
    port: u16,
    requests: Arc<Mutex<Vec<Vec<u8>>>>,
    stop: Arc<AtomicBool>,
    accept: Option<thread::JoinHandle<()>>,
}

impl Drop for Provider {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
        if let Some(t) = self.accept.take() {
            let _ = t.join();
        }
    }
}

/// Bind 127.0.0.1 on port 0, or `None` (the test then skips, saying so)
/// where binding is not permitted.
fn listener(test: &str) -> Option<TcpListener> {
    match TcpListener::bind("127.0.0.1:0") {
        Ok(l) => Some(l),
        Err(e) if e.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("SKIPPED {test}: binding a loopback listener is not permitted here ({e})");
            None
        }
        Err(e) => panic!("binding a loopback listener failed: {e}"),
    }
}

/// Read one request: the head, then `content-length` body bytes.
fn read_request(s: &mut impl Read) -> Vec<u8> {
    let mut got = Vec::new();
    let mut b = [0u8; 1];
    while !got.ends_with(b"\r\n\r\n") {
        match s.read(&mut b) {
            Ok(1) => got.push(b[0]),
            _ => return got,
        }
    }
    let head = String::from_utf8_lossy(&got).to_string();
    let len: usize = head
        .lines()
        .find_map(|l| l.strip_prefix("content-length: "))
        .map(|v| v.trim().parse().unwrap())
        .unwrap_or(0);
    let mut body = vec![0u8; len];
    if s.read_exact(&mut body).is_ok() {
        got.extend_from_slice(&body);
    }
    got
}

fn reply(s: &mut TcpStream, status: u16, headers: &[(String, String)], body: &str) {
    let mut head = format!(
        "HTTP/1.1 {status} X\r\ncontent-type: application/json\r\ncontent-length: {}\r\n",
        body.len()
    );
    for (k, v) in headers {
        head.push_str(&format!("{k}: {v}\r\n"));
    }
    head.push_str("connection: close\r\n\r\n");
    let _ = s.write_all(head.as_bytes());
    let _ = s.write_all(body.as_bytes());
}

fn serve(mut s: TcpStream, act: Act, requests: Arc<Mutex<Vec<Vec<u8>>>>) {
    let req = read_request(&mut s);
    requests.lock().unwrap().push(req.clone());
    match act {
        Act::Reply(status, headers, body) => reply(&mut s, status, &headers, &body),
        Act::Judge(surface, accepted) => {
            let at = req
                .windows(4)
                .position(|w| w == b"\r\n\r\n")
                .map_or(req.len(), |i| i + 4);
            match surface.judge(&req[at..]) {
                None => reply(&mut s, 200, &[], &accepted),
                Some(why) => reply(
                    &mut s,
                    400,
                    &[("request-id".into(), "req_drift".into())],
                    &rejection(&why),
                ),
            }
        }
        Act::Hang => {
            let mut sink = Vec::new();
            let _ = s.read_to_end(&mut sink);
        }
        Act::Drop => {}
        Act::Respond(f) => {
            let at = req
                .windows(4)
                .position(|w| w == b"\r\n\r\n")
                .map_or(req.len(), |i| i + 4);
            let body = f(&req[at..]);
            let head = format!(
                "HTTP/1.1 200 OK\r\ncontent-type: application/json\r\ncontent-length: {}\r\n\r\n",
                body.len()
            );
            let _ = s.write_all(head.as_bytes());
            let _ = s.write_all(body.as_bytes());
        }
        Act::CutOff(body) => {
            let head = format!(
                "HTTP/1.1 200 OK\r\ncontent-type: application/json\r\ncontent-length: {}\r\n\r\n",
                body.len() + 100
            );
            let _ = s.write_all(head.as_bytes());
            let _ = s.write_all(body.as_bytes());
        }
    }
}

impl Provider {
    /// Start a provider answering connections in script order. When the
    /// script runs out it answers 500 without a retry-after, so a test that
    /// sends more requests than it planned fails visibly.
    fn start(l: TcpListener, script: Vec<Act>) -> Provider {
        let port = l.local_addr().unwrap().port();
        l.set_nonblocking(true).unwrap();
        let requests = Arc::new(Mutex::new(Vec::new()));
        let script = Arc::new(Mutex::new(script));
        let stop = Arc::new(AtomicBool::new(false));
        let (r, sc, st) = (requests.clone(), script.clone(), stop.clone());
        let accept = thread::spawn(move || {
            while !st.load(Ordering::SeqCst) {
                match l.accept() {
                    Ok((s, _)) => {
                        s.set_nonblocking(false).unwrap();
                        let act = {
                            let mut q = sc.lock().unwrap();
                            if q.is_empty() {
                                Act::Reply(500, vec![], "{}".into())
                            } else {
                                q.remove(0)
                            }
                        };
                        let r = r.clone();
                        thread::spawn(move || serve(s, act, r));
                    }
                    Err(_) => thread::sleep(Duration::from_millis(5)),
                }
            }
        });
        Provider {
            port,
            requests,
            stop,
            accept: Some(accept),
        }
    }

    fn url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port)
    }

    fn requests(&self) -> Vec<Vec<u8>> {
        self.requests.lock().unwrap().clone()
    }

    /// The bodies the provider received, in order.
    fn bodies(&self) -> Vec<Vec<u8>> {
        self.requests()
            .iter()
            .map(|r| {
                let at = r.windows(4).position(|w| w == b"\r\n\r\n").unwrap() + 4;
                r[at..].to_vec()
            })
            .collect()
    }

    /// Wait until `n` requests have arrived.
    fn wait_for(&self, n: usize) {
        let t0 = Instant::now();
        while self.requests().len() < n {
            assert!(
                t0.elapsed() < Duration::from_secs(20),
                "no request {n} arrived"
            );
            thread::sleep(Duration::from_millis(10));
        }
    }
}

/// A message body with the given content, stop reason and usage.
fn message(content: &str, stop: &str, input: u64, output: u64) -> String {
    format!(
        r#"{{"id":"msg_1","type":"message","role":"assistant","model":"claude-test","content":{content},"stop_reason":"{stop}","stop_sequence":null,"usage":{{"input_tokens":{input},"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":{output}}}}}"#
    )
}

fn ok(content: &str, stop: &str) -> Act {
    Act::Reply(200, vec![], message(content, stop, 100, 10))
}

fn text_turn(stop: &str) -> Act {
    ok(r#"[{"type":"text","text":"Thinking about it."}]"#, stop)
}

fn error(status: u16, retry_after: Option<&str>, kind: &str) -> Act {
    let mut h = vec![("request-id".to_string(), format!("req_{status}"))];
    if let Some(r) = retry_after {
        h.push(("retry-after".into(), r.into()));
    }
    Act::Reply(
        status,
        h,
        format!(
            r#"{{"type":"error","error":{{"type":"{kind}","message":"{kind} message"}},"request_id":"req_body"}}"#
        ),
    )
}

// ---------------------------------------------------------------------------
// Running stewart.

/// A commissioned audit with custom limits.
fn commissioned(e: &Env, limits: (u64, u64, u64)) -> String {
    commissioned_with(e, limits, "").0
}

/// A commissioned audit with custom limits and further front-matter lines
/// (each ending with LF), and prepare's reply as printed.
fn commissioned_with(e: &Env, limits: (u64, u64, u64), lines: &str) -> (String, String) {
    let r = e.new_ref();
    let q = format!(
        "---\nstewart: question/1\nfamily: open-inquiry\nmodel: claude-opus-5-5\n{lines}destination: {}\nlimit-turns: {}\nlimit-input-tokens: {}\nlimit-output-tokens: {}\n---\n  Is the restart path safe?  \n",
        e.dest, limits.0, limits.1, limits.2
    );
    std::fs::write(format!("{}/question.md", e.folder), q).unwrap();
    std::fs::create_dir_all(format!("{}/materials", e.folder)).unwrap();
    std::fs::write(
        format!("{}/materials/a.py", e.folder),
        b"print('restart')\n",
    )
    .unwrap();
    let o = e.run(&["prepare", &r, "--json"]);
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    let prepared = o.text();
    let h = s(&o.json(), &["data", "prepared"]).to_string();
    let o = e.commission(&r, &h);
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    (r, prepared)
}

const DEFAULT_LIMITS: (u64, u64, u64) = (200, 20_000_000, 400_000);

fn run_cmd(e: &Env, r: &str, url: &str, extra: &[(&str, &str)]) -> Command {
    let mut c = Command::new(bin());
    c.args(["run", r, "--json"])
        .current_dir(&e.cwd)
        .env_remove("STEWART_ARCHIVE")
        .env_remove("STEWART_TEST_FAULT")
        .env_remove("STEWART_TEST_SABOTAGE")
        .env_remove("STEWART_TEST_TLS_ROOT")
        .env_remove("STEWART_TEST_PROVIDER_TIMEOUT")
        .env_remove("STEWART_TEST_RETRY_DELAYS")
        .env_remove("HTTPS_PROXY")
        .env_remove("https_proxy")
        .env("ANTHROPIC_API_KEY", "sk-test-key")
        .env("STEWART_PROVIDER_URL", url)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    for (k, v) in extra {
        c.env(k, v);
    }
    c
}

struct Ran {
    code: Option<i32>,
    reply: Json,
    stderr: String,
}

fn finish(child: Child) -> Ran {
    let o = child.wait_with_output().unwrap();
    let stderr = String::from_utf8_lossy(&o.stderr).into_owned();
    let reply = json::parse(&o.stdout).unwrap_or_else(|err| {
        panic!(
            "run's reply is not strict JSON ({err}): {}\nstderr: {stderr}",
            String::from_utf8_lossy(&o.stdout)
        )
    });
    Ran {
        code: o.status.code(),
        reply,
        stderr,
    }
}

fn run(e: &Env, r: &str, p: &Provider, extra: &[(&str, &str)]) -> Ran {
    finish(run_cmd(e, r, &p.url(), extra).spawn().unwrap())
}

/// Run where the process is expected to die before replying; returns its
/// exit code (`None` when a signal ended it) and checks it wrote no reply.
#[cfg(feature = "fault-injection")]
fn run_killed(e: &Env, r: &str, p: &Provider, extra: &[(&str, &str)]) -> Option<i32> {
    let o = run_cmd(e, r, &p.url(), extra).output().unwrap();
    assert!(
        o.stdout.is_empty(),
        "{}",
        String::from_utf8_lossy(&o.stdout)
    );
    o.status.code()
}

fn sj<'a>(v: &'a Json, path: &[&str]) -> &'a str {
    s(v, path)
}

fn n(v: &Json, path: &[&str]) -> u64 {
    at(v, path)
        .as_u64()
        .unwrap_or_else(|| panic!("{path:?} is not an integer"))
}

fn is_null(v: &Json, path: &[&str]) -> bool {
    at(v, path).is_null()
}

/// The `body` of log record `n`.
fn body_of(e: &Env, r: &str, n: usize) -> Json {
    at(&e.log_record(r, n), &["body"]).clone()
}

/// The index of the last log record of `kind` (1-based).
fn last_of(e: &Env, r: &str, kind: &str) -> usize {
    e.log_kinds(r).iter().rposition(|k| k == kind).expect(kind) + 1
}

fn run_file(e: &Env, r: &str, run: u64, name: &str) -> Vec<u8> {
    std::fs::read(format!("{}/runs/{run}/{name}", e.audit_dir(r))).unwrap()
}

fn record_body(bytes: &[u8]) -> Json {
    at(&json::parse(bytes).unwrap(), &["body"]).clone()
}

fn attempt(e: &Env, r: &str, run: u64, k: u64, a: u64) -> Json {
    record_body(&run_file(e, r, run, &format!("attempt-{k}-{a}.json")))
}

/// The latest preparation's folder, `prep/<n>`.
fn latest_prep(e: &Env, r: &str) -> String {
    let dir = format!("{}/prep", e.audit_dir(r));
    let mut preps: Vec<u64> = std::fs::read_dir(&dir)
        .unwrap()
        .filter_map(|d| d.ok()?.file_name().to_str()?.parse().ok())
        .collect();
    preps.sort();
    format!("{dir}/{}", preps.last().unwrap())
}

/// The pinned `request_extra`'s members as raw `"key":value` bytes, read
/// independently: none for `{}`, else the bytes inside its braces (this
/// release admits at most the one effort member).
fn pinned_extra(e: &Env, r: &str) -> Vec<Vec<u8>> {
    let bytes = std::fs::read(format!("{}/arrangement.json", latest_prep(e, r))).unwrap();
    let v = json::parse(&bytes).unwrap();
    let x = at(&v, &["body", "request_extra"]);
    let raw = &bytes[x.start..x.end];
    if raw == b"{}" {
        Vec::new()
    } else {
        vec![raw[1..raw.len() - 1].to_vec()]
    }
}

/// The pinned arrangement's spliced members, read independently.
fn arrangement(e: &Env, r: &str) -> (Vec<u8>, Vec<u8>, Vec<u8>, String) {
    let bytes = std::fs::read(format!("{}/arrangement.json", latest_prep(e, r))).unwrap();
    let v = json::parse(&bytes).unwrap();
    let b = at(&v, &["body"]);
    let raw = |k: &str| {
        let x = at(b, &[k]);
        bytes[x.start..x.end].to_vec()
    };
    (
        raw("model"),
        raw("system"),
        raw("tools"),
        sj(b, &["texts", "continuation"]).to_string(),
    )
}

/// Check that every request body the provider received is exactly what the
/// placement's captures rebuild, from the arrangement's pinned bytes.
fn captures_match_what_was_sent(e: &Env, r: &str, run: u64, sent: &[Vec<u8>]) {
    let (model, system, tools, _) = arrangement(e, r);
    let extra = pinned_extra(e, r);
    let extra: Vec<&[u8]> = extra.iter().map(Vec::as_slice).collect();
    let mut caps = Vec::new();
    for (i, body) in sent.iter().enumerate() {
        caps.push(run_file(e, r, run, &format!("request-{}.json", i + 1)));
        let refs: Vec<&[u8]> = caps.iter().map(Vec::as_slice).collect();
        let rebuilt = stewart::runs::rebuild_body(&model, &system, &tools, &extra, &refs).unwrap();
        assert_eq!(&rebuilt, body, "request {} differs from its capture", i + 1);
    }
}

fn kill(child: &Child, sig: i32) {
    // SAFETY: sending a signal to our own child process.
    let rc = unsafe { libc::kill(child.id() as i32, sig) };
    assert_eq!(rc, 0);
}

/// Publish `close_requested` the way a concurrent close does, through the
/// crate's log writer. Only the request is published, so the run's reaction
/// is observed without the seal and delivery a full close goes on to make.
fn request_close(r: &str) {
    let audit = stewart::archive::Audit::open(r).unwrap_or_else(|f| panic!("{}", f.message));
    let body = stewart::bodies::CloseRequested {
        flags: stewart::bodies::CloseFlags {
            confirm: None,
            surrender: vec![],
            destination: None,
        },
    };
    if let Err(e) = stewart::log::publish(&audit, "close_requested", |_| Ok(body.to_j())) {
        panic!("publishing close_requested failed: {}", e.describe());
    }
}

macro_rules! provider {
    ($test:expr, $script:expr) => {
        match listener($test) {
            Some(l) => Provider::start(l, $script),
            None => return,
        }
    };
}

// ---------------------------------------------------------------------------
// Ordinary endings, the reminder and continuation.

#[test]
fn end_turn_sends_the_reminder_once_then_ends_unsubmitted() {
    let p = provider!(
        "end_turn_sends_the_reminder_once_then_ends_unsubmitted",
        vec![text_turn("end_turn"), text_turn("end_turn")]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    let j = &o.reply;
    assert_eq!(sj(j, &["outcome"]), "completed");
    assert_eq!(sj(j, &["data", "ending"]), "ended_unsubmitted");
    assert!(is_null(j, &["data", "cause"]));
    assert_eq!(sj(j, &["effects", "run"]), "ended");
    assert_eq!(sj(j, &["effects", "answer"]), "unchanged");
    assert_eq!(sj(j, &["effects", "seal"]), "none");
    assert_eq!(sj(j, &["effects", "delivery"]), "none");
    assert_eq!(n(j, &["data", "run"]), 1);
    assert!(!at(j, &["data", "continuing"]).v.eq(&json::V::Bool(true)));
    assert_eq!(sj(j, &["data", "notices", "0", "type"]), "reminder");
    assert_eq!(sj(j, &["data", "notices", "0", "sent"]), "sent");
    assert_eq!(n(j, &["data", "usage", "turns", "reported"]), 2);
    assert_eq!(n(j, &["data", "allowances", "turns", "used"]), 2);
    assert_eq!(n(j, &["data", "answer", "revision"]), 0);
    assert!(is_null(j, &["data", "seal"]));
    assert_eq!(sj(j, &["next", "0", "argv", "1"]), "close");

    let kinds = e.log_kinds(&r);
    let tail: Vec<&str> = kinds
        .iter()
        .rev()
        .take(3)
        .rev()
        .map(String::as_str)
        .collect();
    assert_eq!(tail, ["run_started", "notice", "run_ended"]);
    let started = body_of(&e, &r, last_of(&e, &r, "run_started"));
    assert_eq!(sj(&started, &["provider", "base_url"]), p.url());
    assert_eq!(
        at(&started, &["provider", "override"]).v,
        json::V::Bool(true)
    );
    assert!(is_null(&started, &["provider", "proxy"]));
    assert_eq!(
        sj(&started, &["provider", "anthropic_version"]),
        "2026-10-21"
    );
    let notice = body_of(&e, &r, last_of(&e, &r, "notice"));
    assert_eq!(n(&notice, &["request"]), 2);
    assert_eq!(sj(&notice, &["text"]), stewart::forms::REMINDER);
    let ended = body_of(&e, &r, last_of(&e, &r, "run_ended"));
    assert_eq!(sj(&ended, &["recorded_by"]), "run");
    assert_eq!((n(&ended, &["requests"]), n(&ended, &["attempts"])), (2, 2));
    assert_eq!(sj(&ended, &["notices", "0", "sent"]), "sent");

    // The provider saw exactly the 6.1 head and the captured bodies.
    let reqs = p.requests();
    assert_eq!(reqs.len(), 2);
    let head = String::from_utf8_lossy(&reqs[0]);
    assert!(head.starts_with(&format!(
        "POST /v1/messages HTTP/1.1\r\nhost: 127.0.0.1:{}\r\nx-api-key: sk-test-key\r\nanthropic-version: 2026-10-21\r\ncontent-type: application/json\r\ncontent-length: ",
        p.port
    )));
    let bodies = p.bodies();
    captures_match_what_was_sent(&e, &r, 1, &bodies);
    // The first message is the question body exactly, spaces and all; the
    // second request appends the assistant's content and the reminder.
    let first = String::from_utf8(bodies[0].clone()).unwrap();
    assert!(first.ends_with(
        r#""messages":[{"role":"user","content":[{"type":"text","text":"  Is the restart path safe?  \n"}]}]}"#
    ));
    let second = String::from_utf8(bodies[1].clone()).unwrap();
    assert!(second.ends_with(&format!(
        r#"{{"role":"assistant","content":[{{"type":"text","text":"Thinking about it."}}]}},{{"role":"user","content":[{{"type":"text","text":{}}}]}}]}}"#,
        json::quote(stewart::forms::REMINDER)
    )));

    // Authoring ended: another run refuses.
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(3));
    assert_eq!(sj(&o.reply, &["reason"]), "authoring_ended");
    assert_eq!(sj(&o.reply, &["data", "ended_by"]), "ordinary_ending");
    assert_eq!(sj(&o.reply, &["effects", "run"]), "ended");
}

#[test]
fn every_stop_reason_and_continuation() {
    let p = provider!(
        "every_stop_reason_and_continuation",
        vec![
            text_turn("max_tokens"),
            text_turn("model_context_window_exceeded"),
            text_turn("refusal"),
            text_turn("pause_turn"),
            text_turn("a_new_reason"),
            text_turn("tool_use"),
            ok(
                r#"[{"type":"tool_use","name":"read","input":{}}]"#,
                "tool_use"
            ),
            text_turn("stop_sequence"),
            text_turn("end_turn"),
        ]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    for (i, cause) in [
        "max_tokens",
        "context_exhausted",
        "provider_refusal",
        "protocol_anomaly",
        "protocol_anomaly",
        "protocol_anomaly",
        "protocol_anomaly",
    ]
    .iter()
    .enumerate()
    {
        let run_no = i as u64 + 1;
        let o = run(&e, &r, &p, &[]);
        assert_eq!(o.code, Some(5), "run {run_no}: {}", o.stderr);
        assert_eq!(sj(&o.reply, &["data", "ending"]), "interrupted");
        assert_eq!(sj(&o.reply, &["data", "cause"]), *cause, "run {run_no}");
        assert_eq!(n(&o.reply, &["data", "run"]), run_no);
        assert_eq!(sj(&o.reply, &["next", "0", "argv", "1"]), "run");
        assert_eq!(sj(&o.reply, &["next", "1", "argv", "1"]), "close");
        // Usage is cumulative across placements.
        assert_eq!(
            n(&o.reply, &["data", "allowances", "turns", "used"]),
            run_no
        );
        assert_eq!(n(&o.reply, &["data", "usage", "turns", "reported"]), 1);
    }
    // The unanswerable block was captured and nothing was executed.
    assert_eq!(
        run_file(&e, &r, 7, "call-1.json"),
        br#"{"type":"tool_use","name":"read","input":{}}"#
    );
    assert!(!std::path::Path::new(&format!("{}/runs/7/result-1.json", e.audit_dir(&r))).exists());
    // stop_sequence takes the reminder path; then the ordinary ending.
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "ending"]), "ended_unsubmitted");
    assert_eq!(at(&o.reply, &["data", "continuing"]).v, json::V::Bool(true));
    // A continuing placement starts a fresh conversation: the question, then
    // the continuation notice, and nothing of earlier placements.
    let bodies = p.bodies();
    let (_, _, _, continuation) = arrangement(&e, &r);
    let cont = String::from_utf8(bodies[7].clone()).unwrap();
    assert!(cont.ends_with(&format!(
        r#""messages":[{{"role":"user","content":[{{"type":"text","text":"  Is the restart path safe?  \n"}},{{"type":"text","text":{}}}]}}]}}"#,
        json::quote(&continuation)
    )));
    captures_match_what_was_sent(&e, &r, 8, &bodies[7..9]);
    for k in 1..=8u64 {
        let started = body_of(&e, &r, {
            let kinds = e.log_kinds(&r);
            let mut seen = 0;
            kinds
                .iter()
                .position(|x| {
                    if x == "run_started" {
                        seen += 1;
                    }
                    seen == k
                })
                .unwrap()
                + 1
        });
        assert_eq!(n(&started, &["run"]), k);
        assert_eq!(at(&started, &["continuing"]).v, json::V::Bool(k > 1));
    }
}

// ---------------------------------------------------------------------------
// Provider errors and retries.

#[test]
fn http_errors_retry_with_retry_after_and_record_each_attempt() {
    let p = provider!(
        "http_errors_retry_with_retry_after_and_record_each_attempt",
        vec![
            error(529, Some("0"), "overloaded_error"),
            error(503, Some(" 0 "), "api_error"),
            text_turn("end_turn"),
            text_turn("end_turn"),
        ]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "ending"]), "ended_unsubmitted");
    let a1 = attempt(&e, &r, 1, 1, 1);
    assert_eq!(sj(&a1, &["outcome"]), "http_error");
    assert_eq!(n(&a1, &["status"]), 529);
    assert_eq!(sj(&a1, &["then"]), "retry");
    assert_eq!(n(&a1, &["delay_ms"]), 0);
    assert_eq!(sj(&a1, &["request_written"]), "complete");
    assert_eq!(sj(&a1, &["headers", "request-id", "0"]), "req_529");
    assert_eq!(sj(&a1, &["headers", "retry-after", "0"]), "0");
    assert_eq!(sj(&a1, &["error", "type"]), "overloaded_error");
    assert_eq!(sj(&a1, &["error", "request_id"]), "req_body");
    assert_eq!(sj(&a1, &["charged", "basis"]), "none");
    assert_eq!(at(&a1, &["response", "complete"]).v, json::V::Bool(true));
    assert_eq!(n(&a1, &["timeout_seconds"]), 600);
    // The response capture is the body exactly.
    let cap = run_file(&e, &r, 1, "response-1-1.bin");
    assert_eq!(
        sj(&a1, &["response", "sha256"]),
        stewart::util::sha256_hex(&cap)
    );
    let a2 = attempt(&e, &r, 1, 1, 2);
    assert_eq!(sj(&a2, &["headers", "retry-after", "0"]), "0", "trimmed");
    let a3 = attempt(&e, &r, 1, 1, 3);
    assert_eq!(sj(&a3, &["outcome"]), "response");
    assert_eq!(sj(&a3, &["then"]), "use");
    assert!(is_null(&a3, &["delay_ms"]));
    assert_eq!(sj(&a3, &["stop_reason"]), "end_turn");
    assert_eq!(sj(&a3, &["model"]), "claude-test");
    assert_eq!(sj(&a3, &["charged", "basis"]), "reported");
    // Every attempt of a request sends the same body.
    let b = p.bodies();
    assert_eq!(b[0], b[1]);
    assert_eq!(b[1], b[2]);
    let ended = body_of(&e, &r, last_of(&e, &r, "run_ended"));
    assert_eq!((n(&ended, &["requests"]), n(&ended, &["attempts"])), (2, 4));
}

#[test]
fn a_rejected_request_ends_interrupted_with_the_provider_facts() {
    let p = provider!(
        "a_rejected_request_ends_interrupted_with_the_provider_facts",
        vec![error(400, Some("1"), "invalid_request_error")]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "provider_rejected");
    let ended = body_of(&e, &r, last_of(&e, &r, "run_ended"));
    assert_eq!(n(&ended, &["provider", "status"]), 400);
    assert_eq!(
        sj(&ended, &["provider", "error_type"]),
        "invalid_request_error"
    );
    assert_eq!(
        sj(&ended, &["provider", "request_id"]),
        "req_400",
        "the header wins"
    );
    assert_eq!(
        (
            n(&ended, &["provider", "request"]),
            n(&ended, &["provider", "attempt"])
        ),
        (1, 1)
    );
    assert_eq!(n(&o.reply, &["data", "provider", "status"]), 400);
    // The provider's own words reach the manager, in the reply and the record.
    for v in [&ended, at(&o.reply, &["data"])] {
        assert_eq!(
            sj(v, &["provider", "error_message"]),
            "invalid_request_error message"
        );
    }
    assert_eq!(sj(&attempt(&e, &r, 1, 1, 1), &["then"]), "end");
}

#[test]
fn retryable_errors_end_unavailable_after_four_attempts_or_a_long_retry_after() {
    let p = provider!(
        "retryable_errors_end_unavailable_after_four_attempts_or_a_long_retry_after",
        vec![
            error(529, Some("0"), "overloaded_error"),
            error(429, Some("0"), "rate_limit_error"),
            error(500, Some("0"), "api_error"),
            error(502, Some("0"), "api_error"),
            error(529, Some("61"), "overloaded_error"),
        ]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "provider_unavailable");
    assert_eq!(n(&o.reply, &["data", "provider", "attempt"]), 4);
    assert_eq!(n(&o.reply, &["data", "provider", "status"]), 502);
    assert_eq!(sj(&attempt(&e, &r, 1, 1, 4), &["then"]), "end");
    // Continuing, a retry-after over 60 seconds is not waited for.
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "provider_unavailable");
    assert_eq!(n(&o.reply, &["data", "provider", "attempt"]), 1);
}

#[test]
fn an_undecodable_response_is_charged_and_ends_with_a_protocol_anomaly() {
    let p = provider!(
        "an_undecodable_response_is_charged_and_ends_with_a_protocol_anomaly",
        vec![Act::Reply(
            200,
            vec![],
            r#"{"content":"not an array"}"#.into()
        )]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "protocol_anomaly");
    let a = attempt(&e, &r, 1, 1, 1);
    assert_eq!(sj(&a, &["outcome"]), "response_undecodable");
    assert!(sj(&a, &["problem"]).contains("content is not an array"));
    assert_eq!(sj(&a, &["charged", "basis"]), "estimated");
    let body_bytes = p.bodies()[0].len() as u64;
    assert_eq!(n(&a, &["charged", "input_tokens"]), body_bytes.div_ceil(3));
    assert_eq!(n(&a, &["charged", "output_tokens"]), 16_000);
    assert_eq!(n(&o.reply, &["data", "usage", "turns", "estimated"]), 1);
}

// ---------------------------------------------------------------------------
// Limits and the near-limit notice.

#[test]
fn limits_and_the_near_limit_notice() {
    // After request 1 exactly 1,024 output tokens remain: a request is still
    // sent, with max_tokens 1,024, carrying the reminder and the near-limit
    // notice; after request 2 fewer remain and the run stops.
    let p = provider!(
        "limits_and_the_near_limit_notice",
        vec![
            Act::Reply(
                200,
                vec![],
                message(r#"[{"type":"text","text":"a"}]"#, "end_turn", 50, 398_976)
            ),
            Act::Reply(
                200,
                vec![],
                message(r#"[{"type":"text","text":"b"}]"#, "end_turn", 50, 1)
            ),
        ]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "ending"]), "limit_reached");
    assert_eq!(
        n(&o.reply, &["data", "allowances", "output_tokens", "used"]),
        398_977
    );
    let bodies = p.bodies();
    assert_eq!(bodies.len(), 2);
    let second = String::from_utf8(bodies[1].clone()).unwrap();
    assert!(second.contains(r#""max_tokens":1024,"#));
    let text = "Allowance notice: 199 turns, 19999950 input tokens and 1024 output tokens remain for this audit. When an allowance runs out the run stops, and an unsubmitted answer stays unsubmitted.";
    assert!(second.ends_with(&format!(
        r#"{{"role":"user","content":[{{"type":"text","text":{}}},{{"type":"text","text":{}}}]}}]}}"#,
        json::quote(stewart::forms::REMINDER),
        json::quote(text)
    )));
    let kinds = e.log_kinds(&r);
    let notices: Vec<usize> = kinds
        .iter()
        .enumerate()
        .filter(|(_, k)| *k == "notice")
        .map(|(i, _)| i + 1)
        .collect();
    assert_eq!(notices.len(), 2);
    let near = body_of(&e, &r, notices[0]);
    assert_eq!(sj(&near, &["type"]), "near_limit");
    assert_eq!(sj(&near, &["text"]), text);
    assert_eq!(n(&near, &["request"]), 2);
    assert_eq!(n(&near, &["remaining", "output_tokens"]), 1024);
    let reports = at(&o.reply, &["data", "notices"]).as_arr().unwrap();
    assert_eq!(reports.len(), 2);
    assert!(reports.iter().all(|n| sj(n, &["sent"]) == "sent"));
    // The limit stopped authoring.
    let o = run(&e, &r, &p, &[]);
    assert_eq!(sj(&o.reply, &["reason"]), "authoring_ended");
    assert_eq!(sj(&o.reply, &["data", "ended_by"]), "limit");
}

#[test]
fn a_limit_exhausted_before_the_first_request_sends_nothing() {
    let p = provider!(
        "a_limit_exhausted_before_the_first_request_sends_nothing",
        vec![Act::Reply(
            200,
            vec![],
            message(r#"[{"type":"text","text":"a"}]"#, "max_tokens", 10, 10)
        )]
    );
    let e = Env::new();
    // One turn: the first response uses it; continuing finds no turn left.
    let r = commissioned(&e, (1, 20_000_000, 400_000));
    let o = run(&e, &r, &p, &[]);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "max_tokens");
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "ending"]), "limit_reached");
    assert_eq!(p.requests().len(), 1);
    let ended = body_of(&e, &r, last_of(&e, &r, "run_ended"));
    assert_eq!(n(&ended, &["requests"]), 0);
}

// ---------------------------------------------------------------------------
// Stopping: close, signals and a dead placement.

#[test]
fn close_requested_aborts_the_request_and_stops_the_run() {
    let p = provider!(
        "close_requested_aborts_the_request_and_stops_the_run",
        vec![Act::Hang]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let child = run_cmd(&e, &r, &p.url(), &[]).spawn().unwrap();
    p.wait_for(1);
    let t0 = Instant::now();
    request_close(&r);
    let o = finish(child);
    assert!(t0.elapsed() < Duration::from_secs(10), "{:?}", t0.elapsed());
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "ending"]), "stopped_by_close");
    assert_eq!(sj(&o.reply, &["next", "0", "argv", "1"]), "status");
    let a = attempt(&e, &r, 1, 1, 1);
    assert_eq!(sj(&a, &["outcome"]), "aborted_by_close");
    assert_eq!(sj(&a, &["request_written"]), "complete");
    assert_eq!(sj(&a, &["charged", "basis"]), "estimated");
    assert!(is_null(&a, &["response"]));
    let kinds = e.log_kinds(&r);
    assert_eq!(kinds[kinds.len() - 2..], ["close_requested", "run_ended"]);
    // Close was requested: run refuses now.
    let o = run(&e, &r, &p, &[]);
    assert_eq!(sj(&o.reply, &["reason"]), "reference_closed");
}

#[test]
fn a_signal_interrupts_the_run_and_run_continues() {
    let p = provider!(
        "a_signal_interrupts_the_run_and_run_continues",
        vec![Act::Hang, text_turn("end_turn"), text_turn("end_turn")]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let child = run_cmd(&e, &r, &p.url(), &[]).spawn().unwrap();
    p.wait_for(1);
    kill(&child, libc::SIGTERM);
    let o = finish(child);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "ending"]), "interrupted");
    assert_eq!(sj(&o.reply, &["data", "cause"]), "signal");
    assert_eq!(
        sj(&attempt(&e, &r, 1, 1, 1), &["outcome"]),
        "aborted_by_signal"
    );
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    assert_eq!(n(&o.reply, &["data", "run"]), 2);
    assert_eq!(sj(&o.reply, &["data", "ending"]), "ended_unsubmitted");
    // The aborted attempt's estimate carries over.
    assert_eq!(
        n(&o.reply, &["data", "allowances", "turns", "estimated"]),
        1
    );
    assert_eq!(n(&o.reply, &["data", "allowances", "turns", "reported"]), 2);
}

#[test]
fn a_dead_placement_is_reconciled_with_estimated_charges() {
    let p = provider!(
        "a_dead_placement_is_reconciled_with_estimated_charges",
        vec![Act::Hang, text_turn("end_turn"), text_turn("end_turn")]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let mut child = run_cmd(&e, &r, &p.url(), &[]).spawn().unwrap();
    p.wait_for(1);
    kill(&child, libc::SIGKILL);
    let _ = child.wait();
    let sent = p.bodies()[0].len() as u64;
    // The lock is free and placement 1 has no run_ended.
    assert_eq!(e.log_kinds(&r).last().unwrap(), "run_started");
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    let kinds = e.log_kinds(&r);
    let first_end = kinds.iter().position(|k| k == "run_ended").unwrap() + 1;
    let ended = body_of(&e, &r, first_end);
    assert_eq!(n(&ended, &["run"]), 1);
    assert_eq!(sj(&ended, &["ending"]), "interrupted");
    assert_eq!(sj(&ended, &["cause"]), "process_gone");
    assert_eq!(sj(&ended, &["recorded_by"]), "run");
    assert_eq!((n(&ended, &["requests"]), n(&ended, &["attempts"])), (1, 0));
    assert_eq!(n(&ended, &["usage", "turns", "estimated"]), 1);
    assert_eq!(
        n(&ended, &["usage", "input_tokens", "estimated"]),
        sent.div_ceil(3)
    );
    assert_eq!(n(&ended, &["usage", "output_tokens", "estimated"]), 16_000);
    assert_eq!(
        kinds[first_end], "run_started",
        "reconciliation precedes the new placement"
    );
    assert_eq!(n(&o.reply, &["data", "run"]), 2);
    assert_eq!(
        n(
            &o.reply,
            &["data", "allowances", "output_tokens", "estimated"]
        ),
        16_000
    );
}

// ---------------------------------------------------------------------------
// Refusals before launch.

#[test]
fn refusals_before_launch_change_nothing() {
    let p = provider!("refusals_before_launch_change_nothing", vec![Act::Hang]);
    let e = Env::new();
    // Before acceptance.
    let r0 = e.new_ref();
    let o = run(&e, &r0, &p, &[]);
    assert_eq!(o.code, Some(3));
    assert_eq!(sj(&o.reply, &["reason"]), "not_accepted");
    assert_eq!(sj(&o.reply, &["effects", "run"]), "not_started");

    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let before = e.inventory();
    let refused = |env: &[(&str, &str)], url: &str, reason: &str| {
        let o = finish(run_cmd(&e, &r, url, env).spawn().unwrap());
        assert_eq!(o.code, Some(3), "{reason}: {}", o.stderr);
        assert_eq!(sj(&o.reply, &["reason"]), reason);
        assert_eq!(sj(&o.reply, &["effects", "run"]), "not_started");
        assert_eq!(sj(&o.reply, &["effects", "answer"]), "unchanged");
        assert_eq!(
            sj(&o.reply, &["effects", "delivery"]),
            "none",
            "no attempt is recorded"
        );
        assert_eq!(sj(&o.reply, &["next", "0", "argv", "1"]), "run");
    };
    let url = p.url();
    refused(&[("ANTHROPIC_API_KEY", "")], &url, "provider_key_missing");
    refused(
        &[("ANTHROPIC_API_KEY", "sk test")],
        &url,
        "provider_key_invalid",
    );
    refused(&[], "http://example.com", "provider_url_invalid");
    refused(&[], "https://example.com/", "provider_url_invalid");
    refused(
        &[("HTTPS_PROXY", "http://user:pw@proxy:3128")],
        &url,
        "provider_proxy_invalid",
    );
    refused(
        &[("https_proxy", "socks5://proxy:1080")],
        &url,
        "provider_proxy_invalid",
    );
    assert!(p.requests().is_empty(), "no request before the checks pass");
    // Refusals record diagnostics only.
    let after = e.inventory();
    for (k, v) in &before {
        assert_eq!(after.get(k), Some(v), "{k} changed");
    }
    assert!(
        after
            .keys()
            .filter(|k| !before.contains_key(*k))
            .all(|k| k.contains("/diag/"))
    );

    // A loopback provider never uses the proxy, though the value is checked.
    let p2 = provider!(
        "refusals_before_launch_change_nothing",
        vec![text_turn("max_tokens")]
    );
    let o = finish(
        run_cmd(&e, &r, &p2.url(), &[("HTTPS_PROXY", "http://127.0.0.1:9/")])
            .spawn()
            .unwrap(),
    );
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    let started = body_of(&e, &r, last_of(&e, &r, "run_started"));
    assert!(is_null(&started, &["provider", "proxy"]));

    // A live placement holds the lock.
    let child = run_cmd(&e, &r, &p.url(), &[]).spawn().unwrap();
    p.wait_for(1);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(3));
    assert_eq!(sj(&o.reply, &["reason"]), "run_held");
    assert_eq!(n(&o.reply, &["data", "run"]), 2);
    assert_eq!(n(&o.reply, &["data", "holder", "pid"]), child.id() as u64);
    assert_eq!(sj(&o.reply, &["effects", "run"]), "still_held");
    kill(&child, libc::SIGTERM);
    let o = finish(child);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "signal");
}

#[test]
fn a_damaged_capture_refuses_commission_damaged() {
    let p = provider!("a_damaged_capture_refuses_commission_damaged", vec![]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    // Alter one material capture in the archive.
    let intake = format!("{}/intake", e.audit_dir(&r));
    let mut victim = None;
    let mut stack = vec![std::path::PathBuf::from(&intake)];
    while let Some(d) = stack.pop() {
        for ent in std::fs::read_dir(&d).unwrap().flatten() {
            let path = ent.path();
            if path.is_dir() {
                stack.push(path);
            } else if std::fs::read(&path).unwrap() == b"print('restart')\n" {
                victim = Some(path);
            }
        }
    }
    let victim = victim.expect("the material's capture");
    let _ = Command::new("chmod").args(["u+w"]).arg(&victim).status();
    std::fs::write(&victim, b"print('changed')\n").unwrap();
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(3), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["reason"]), "commission_damaged");
    let items = at(&o.reply, &["data", "items"]).as_arr().unwrap();
    assert_eq!(items.len(), 1);
    assert!(sj(&items[0], &["problem"]).contains("SHA-256"));
    assert_eq!(sj(&o.reply, &["next", "0", "argv", "2"]), &r);
    assert!(p.requests().is_empty());
    assert!(!e.log_kinds(&r).iter().any(|k| k == "run_started"));
}

// ---------------------------------------------------------------------------
// The auditor's tools and delivery, as the run calls them.

#[test]
fn tool_calls_are_captured_executed_replayed_and_answered() {
    let content = r#"[{"type":"thinking","thinking":"plan","signature":"c2ln"},{"type":"tool_use","id":"toolu_1","name":"list","input":{}},{"type":"tool_use","id":"toolu_1","name":"list","input":{}},{"type":"tool_use","id":"toolu_1","name":"list","input":{"page":2}}]"#;
    let p = provider!(
        "tool_calls_are_captured_executed_replayed_and_answered",
        vec![
            ok(content, "tool_use"),
            text_turn("end_turn"),
            text_turn("end_turn")
        ]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    // Each block is captured exactly before it runs.
    assert_eq!(
        run_file(&e, &r, 1, "call-1.json"),
        br#"{"type":"tool_use","id":"toolu_1","name":"list","input":{}}"#
    );
    let r1 = record_body(&run_file(&e, &r, 1, "result-1.json"));
    assert_eq!(sj(&r1, &["outcome"]), "completed");
    assert_eq!(n(&r1, &["block"]), 1);
    let r2 = record_body(&run_file(&e, &r, 1, "result-2.json"));
    assert_eq!(n(&r2, &["replay_of"]), 1);
    let r3 = record_body(&run_file(&e, &r, 1, "result-3.json"));
    assert_eq!(sj(&r3, &["reason"]), "invocation_id_reused");
    // The next request copies the assistant content exactly and answers each
    // block in order.
    let second = String::from_utf8(p.bodies()[1].clone()).unwrap();
    assert!(second.contains(&format!(r#"{{"role":"assistant","content":{content}}}"#)));
    assert_eq!(
        second
            .matches(r#""type":"tool_result","tool_use_id":"toolu_1""#)
            .count(),
        3
    );
}

/// The auditor preparation handle in a request body: the `prepared` member
/// of the prepare reply, as it appears JSON-escaped inside a text block.
fn prepared_handle(body: &[u8]) -> String {
    let s = String::from_utf8_lossy(body);
    let key = r#"\"prepared\":\""#;
    let at = s.rfind(key).expect("a prepare reply in the request") + key.len();
    s[at..].split('\\').next().unwrap().to_string()
}

/// A provider that records an account, prepares, then confirms a submit of
/// the handle that prepare returned, and would otherwise end its turn.
fn submitting_provider(test: &str) -> Option<Provider> {
    let submit: Responder = Arc::new(|body: &[u8]| {
        let h = prepared_handle(body);
        message(
            &format!(
                r#"[{{"type":"tool_use","id":"t3","name":"submit","input":{{"prepared":"{h}","confirm":true}}}}]"#
            ),
            "tool_use",
            100,
            10,
        )
    });
    let script = vec![
        ok(
            r#"[{"type":"tool_use","id":"t1","name":"record_account","input":{"text":"The restart path re-sends one reminder."}},{"type":"tool_use","id":"t2","name":"prepare","input":{}}]"#,
            "tool_use",
        ),
        Act::Respond(submit),
        text_turn("end_turn"),
        text_turn("end_turn"),
    ];
    listener(test).map(|l| Provider::start(l, script))
}

#[test]
fn a_confirmed_submit_seals_and_the_run_delivers_before_ending() {
    let Some(p) =
        submitting_provider("a_confirmed_submit_seals_and_the_run_delivers_before_ending")
    else {
        return;
    };
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    let j = &o.reply;
    assert_eq!(sj(j, &["data", "ending"]), "sealed");
    assert_eq!(sj(j, &["effects", "answer"]), "changed");
    assert_eq!(sj(j, &["effects", "seal"]), "recorded");
    assert_eq!(sj(j, &["effects", "delivery"]), "verified");
    assert_eq!(sj(j, &["data", "seal", "actor"]), "auditor");
    assert!(sj(j, &["data", "seal", "handle"]).starts_with("seal."));
    assert_eq!(sj(j, &["data", "delivery", "outcome"]), "verified");
    assert_eq!(sj(j, &["next", "0", "argv", "1"]), "close");
    // The submit's result was recorded but no further request was sent.
    assert_eq!(p.requests().len(), 2);
    let kinds = e.log_kinds(&r);
    let seal = kinds.iter().position(|k| k == "seal").unwrap();
    let ended = kinds.iter().position(|k| k == "run_ended").unwrap();
    assert!(kinds[seal..ended].iter().any(|k| k == "delivery_ended"));
    let ended = body_of(&e, &r, ended + 1);
    assert_eq!(sj(&ended, &["seal"]), format!("log/{}.json", seal + 1));
    // Authoring ended with the seal. The refusal makes no delivery and
    // reports the newest recorded attempt's outcome (1.4).
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(3));
    assert_eq!(sj(&o.reply, &["data", "ended_by"]), "seal");
    assert_eq!(sj(&o.reply, &["effects", "seal"]), "existing");
    assert_eq!(sj(&o.reply, &["effects", "delivery"]), "verified");
}

/// A seal whose publication is uncertain to the submit but was in fact
/// linked: the run reads the log, delivers and ends `sealed`, and sends no
/// further request and no reminder.
#[cfg(feature = "fault-injection")]
#[test]
fn an_uncertain_seal_that_was_linked_is_delivered_and_ends_sealed() {
    let Some(p) =
        submitting_provider("an_uncertain_seal_that_was_linked_is_delivered_and_ends_sealed")
    else {
        return;
    };
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(
        &e,
        &r,
        &p,
        &[("STEWART_TEST_FAULT", "log.dirsync:seal=eio")],
    );
    assert_eq!(o.code, Some(0), "{}", o.stderr);
    let j = &o.reply;
    assert_eq!(sj(j, &["data", "ending"]), "sealed");
    assert_eq!(sj(j, &["effects", "seal"]), "recorded");
    assert_eq!(sj(j, &["effects", "delivery"]), "verified");
    assert_eq!(sj(j, &["data", "seal", "actor"]), "auditor");
    // The submit itself replied seal_uncertain (7.6).
    let submit = record_body(&run_file(&e, &r, 1, "result-3.json"));
    assert_eq!(sj(&submit, &["tool"]), "submit");
    assert_eq!(sj(&submit, &["outcome"]), "failed");
    assert_eq!(sj(&submit, &["reason"]), "seal_uncertain");
    // Nothing followed the seal but its delivery and the ending.
    assert_eq!(p.requests().len(), 2, "no request after the seal");
    let kinds = e.log_kinds(&r);
    let seal = kinds
        .iter()
        .position(|k| k == "seal")
        .expect("the seal was linked");
    assert!(
        !kinds.iter().any(|k| k == "notice"),
        "no reminder: {kinds:?}"
    );
    assert_eq!(
        kinds[seal + 1..],
        ["delivery_planned", "delivery_ended", "run_ended"],
        "{kinds:?}"
    );
    let ended = body_of(&e, &r, kinds.len());
    assert_eq!(sj(&ended, &["ending"]), "sealed");
    assert_eq!(sj(&ended, &["seal"]), format!("log/{}.json", seal + 1));
    // Control: the same provider without the fault seals as ordinarily
    // (a_confirmed_submit_seals_and_the_run_delivers_before_ending); with the
    // seal unlinked, nothing is sealed and the turn continues.
}

/// The differing case: a submit whose seal is not linked at all fails
/// `record_failed`, which ends the placement `archive_write_failed`; the log
/// holds no seal, so nothing is delivered.
#[cfg(feature = "fault-injection")]
#[test]
fn a_seal_that_was_not_linked_is_not_delivered() {
    let Some(p) = submitting_provider("a_seal_that_was_not_linked_is_not_delivered") else {
        return;
    };
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(
        &e,
        &r,
        &p,
        &[("STEWART_TEST_FAULT", "log.publish:seal=eio")],
    );
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "ending"]), "interrupted");
    assert_eq!(sj(&o.reply, &["data", "cause"]), "archive_write_failed");
    assert_eq!(sj(&o.reply, &["effects", "seal"]), "none");
    assert_eq!(sj(&o.reply, &["effects", "delivery"]), "none");
    let submit = record_body(&run_file(&e, &r, 1, "result-3.json"));
    assert_eq!(sj(&submit, &["reason"]), "record_failed");
    let kinds = e.log_kinds(&r);
    assert!(
        !kinds
            .iter()
            .any(|k| k == "seal" || k.starts_with("delivery"))
    );
    assert_eq!(p.requests().len(), 2);
}

#[test]
fn an_unanswerable_block_is_captured_and_ends_the_run() {
    let p = provider!(
        "an_unanswerable_block_is_captured_and_ends_the_run",
        vec![ok(
            r#"[{"type":"text","text":"x"},{"type":"tool_use","id":7,"name":"list","input":{}},{"type":"tool_use","id":"t2","name":"list","input":{}}]"#,
            "tool_use"
        )]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "protocol_anomaly");
    assert_eq!(
        run_file(&e, &r, 1, "call-1.json"),
        br#"{"type":"tool_use","id":7,"name":"list","input":{}}"#
    );
    let dir = format!("{}/runs/1", e.audit_dir(&r));
    assert!(!std::path::Path::new(&format!("{dir}/call-2.json")).exists());
    assert!(!std::path::Path::new(&format!("{dir}/result-1.json")).exists());
}

// ---------------------------------------------------------------------------
// Test builds: transport variables, TLS and sabotage.

#[cfg(feature = "fault-injection")]
#[test]
fn timeouts_and_lost_connections_are_retried() {
    let p = provider!(
        "timeouts_and_lost_connections_are_retried",
        vec![
            Act::Hang,
            Act::Drop,
            Act::CutOff(r#"{"content":["#.into()),
            text_turn("max_tokens"),
        ]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(
        &e,
        &r,
        &p,
        &[
            ("STEWART_TEST_PROVIDER_TIMEOUT", "1"),
            ("STEWART_TEST_RETRY_DELAYS", "0,0,0"),
        ],
    );
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "max_tokens");
    let outcomes: Vec<String> = (1..=4)
        .map(|a| sj(&attempt(&e, &r, 1, 1, a), &["outcome"]).to_string())
        .collect();
    assert_eq!(
        outcomes,
        ["timeout", "connection_lost", "connection_lost", "response"]
    );
    let t = attempt(&e, &r, 1, 1, 1);
    assert_eq!(n(&t, &["timeout_seconds"]), 1);
    assert_eq!(sj(&t, &["charged", "basis"]), "estimated");
    let cut = attempt(&e, &r, 1, 1, 3);
    assert_eq!(n(&cut, &["status"]), 200);
    assert_eq!(at(&cut, &["response", "complete"]).v, json::V::Bool(false));
    assert_eq!(n(&cut, &["delay_ms"]), 0);
}

#[cfg(feature = "fault-injection")]
#[test]
fn invalid_test_variables_refuse_before_any_request() {
    let p = provider!("invalid_test_variables_refuse_before_any_request", vec![]);
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let no_cert = e.path("no-cert.pem");
    std::fs::write(&no_cert, b"not a certificate\n").unwrap();
    for (k, v, reason) in [
        (
            "STEWART_TEST_PROVIDER_TIMEOUT",
            "0",
            "test_variable_invalid",
        ),
        (
            "STEWART_TEST_PROVIDER_TIMEOUT",
            "601",
            "test_variable_invalid",
        ),
        ("STEWART_TEST_RETRY_DELAYS", "1,2", "test_variable_invalid"),
        (
            "STEWART_TEST_RETRY_DELAYS",
            "1,2,30001",
            "test_variable_invalid",
        ),
        (
            "STEWART_TEST_TLS_ROOT",
            "relative.pem",
            "test_tls_root_invalid",
        ),
        (
            "STEWART_TEST_TLS_ROOT",
            "/nonexistent/roots.pem",
            "test_tls_root_invalid",
        ),
        (
            "STEWART_TEST_TLS_ROOT",
            no_cert.as_str(),
            "test_tls_root_invalid",
        ),
    ] {
        let o = run(&e, &r, &p, &[(k, v)]);
        assert_eq!(o.code, Some(3), "{k}={v}");
        assert_eq!(sj(&o.reply, &["reason"]), reason, "{k}={v}");
    }
    assert!(p.requests().is_empty());
}

#[cfg(feature = "fault-injection")]
#[test]
fn tls_to_a_test_provider_with_a_test_root() {
    use rustls::pki_types::pem::PemObject;
    use rustls::pki_types::{CertificateDer, PrivateKeyDer};
    let Some(l) = listener("tls_to_a_test_provider_with_a_test_root") else {
        return;
    };
    let port = l.local_addr().unwrap().port();
    let fixtures = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/fixtures/provider");
    let chain: Vec<CertificateDer<'static>> =
        CertificateDer::pem_file_iter(format!("{fixtures}/server.pem"))
            .unwrap()
            .map(|c| c.unwrap())
            .collect();
    let key = PrivateKeyDer::from_pem_file(format!("{fixtures}/server.key.pem")).unwrap();
    let provider = Arc::new(rustls::crypto::ring::default_provider());
    let config = Arc::new(
        rustls::ServerConfig::builder_with_provider(provider)
            .with_safe_default_protocol_versions()
            .unwrap()
            .with_no_client_auth()
            .with_single_cert(chain, key)
            .unwrap(),
    );
    let server = thread::spawn(move || {
        let reply = message(r#"[{"type":"text","text":"a"}]"#, "max_tokens", 1, 1);
        let (s, _) = l.accept().unwrap();
        let conn = rustls::ServerConnection::new(config.clone()).unwrap();
        let mut tls = rustls::StreamOwned::new(conn, s);
        read_request(&mut tls);
        let head = format!(
            "HTTP/1.1 200 OK\r\ncontent-type: application/json\r\ncontent-length: {}\r\n\r\n",
            reply.len()
        );
        tls.write_all(head.as_bytes()).unwrap();
        tls.write_all(reply.as_bytes()).unwrap();
        tls.conn.send_close_notify();
        let _ = tls.flush();
    });
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let url = format!("https://localhost:{port}");
    let o = finish(
        run_cmd(
            &e,
            &r,
            &url,
            &[("STEWART_TEST_TLS_ROOT", &format!("{fixtures}/ca.pem"))],
        )
        .spawn()
        .unwrap(),
    );
    server.join().unwrap();
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "max_tokens");
    assert_eq!(sj(&attempt(&e, &r, 1, 1, 1), &["outcome"]), "response");
}

#[cfg(feature = "fault-injection")]
#[test]
fn run_fault_points_are_recorded_or_reconciled() {
    let p = provider!(
        "run_fault_points_are_recorded_or_reconciled",
        vec![
            text_turn("max_tokens"),
            text_turn("max_tokens"),
            text_turn("end_turn"),
            text_turn("max_tokens"),
        ]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    // Killed right after run_started: no request; reconciled with no usage.
    assert_eq!(
        run_killed(
            &e,
            &r,
            &p,
            &[("STEWART_TEST_FAULT", "run.after_started=kill")]
        ),
        None
    );
    assert!(std::path::Path::new(&format!("{}/runs/1", e.audit_dir(&r))).is_dir());
    // A request capture that cannot be written ends archive_write_failed;
    // the dead placement 1 is recorded first.
    let o = run(
        &e,
        &r,
        &p,
        &[("STEWART_TEST_FAULT", "provider.request_capture=eio")],
    );
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "archive_write_failed");
    let kinds = e.log_kinds(&r);
    let first_end = kinds.iter().position(|k| k == "run_ended").unwrap() + 1;
    let ended = body_of(&e, &r, first_end);
    assert_eq!(sj(&ended, &["cause"]), "process_gone");
    assert_eq!(
        (
            n(&ended, &["requests"]),
            n(&ended, &["usage", "turns", "estimated"])
        ),
        (0, 0)
    );
    assert!(p.requests().is_empty());
    // Killed after request 1 was written to the connection: reconciled with
    // one estimated attempt for the complete capture without a record.
    assert_eq!(
        run_killed(
            &e,
            &r,
            &p,
            &[("STEWART_TEST_FAULT", "provider.sent:1=kill")]
        ),
        None
    );
    p.wait_for(1);
    // An attempt record that cannot be linked ends archive_write_failed and
    // is charged as an unrecorded attempt.
    let o = run(
        &e,
        &r,
        &p,
        &[("STEWART_TEST_FAULT", "runs.publish:provider_attempt=eio")],
    );
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    assert_eq!(sj(&o.reply, &["data", "cause"]), "archive_write_failed");
    assert_eq!(n(&o.reply, &["data", "usage", "turns", "estimated"]), 1);
    assert_eq!(n(&o.reply, &["data", "usage", "turns", "reported"]), 0);
    let ends: Vec<usize> = e
        .log_kinds(&r)
        .iter()
        .enumerate()
        .filter(|(_, k)| *k == "run_ended")
        .map(|(i, _)| i + 1)
        .collect();
    let killed = body_of(&e, &r, ends[2]);
    assert_eq!(n(&killed, &["run"]), 3);
    assert_eq!(
        (n(&killed, &["requests"]), n(&killed, &["attempts"])),
        (1, 0)
    );
    assert_eq!(n(&killed, &["usage", "output_tokens", "estimated"]), 16_000);
    // Between turns: killed after the reminder is published for request 2
    // and before request 2 is captured, so the reminder was never sent.
    assert_eq!(
        run_killed(
            &e,
            &r,
            &p,
            &[("STEWART_TEST_FAULT", "run.between_turns:1=kill")]
        ),
        None
    );
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    let ends: Vec<usize> = e
        .log_kinds(&r)
        .iter()
        .enumerate()
        .filter(|(_, k)| *k == "run_ended")
        .map(|(i, _)| i + 1)
        .collect();
    let between = body_of(&e, &r, ends[4]);
    assert_eq!(n(&between, &["run"]), 5);
    assert_eq!(sj(&between, &["notices", "0", "type"]), "reminder");
    assert_eq!(sj(&between, &["notices", "0", "sent"]), "not_sent");
    assert_eq!(
        (n(&between, &["requests"]), n(&between, &["attempts"])),
        (1, 1)
    );
}

/// A placement whose ending cannot be recorded: the run fails
/// `record_failed` with its cause, lists the locations it created and kept,
/// and the next run records the ending as a dead placement's.
#[cfg(feature = "fault-injection")]
#[test]
fn an_ending_that_cannot_be_recorded_fails_with_its_cause_and_locations() {
    let p = provider!(
        "an_ending_that_cannot_be_recorded_fails_with_its_cause_and_locations",
        vec![text_turn("max_tokens"), text_turn("max_tokens")]
    );
    let e = Env::new();
    let r = commissioned(&e, DEFAULT_LIMITS);
    let o = run(
        &e,
        &r,
        &p,
        &[("STEWART_TEST_FAULT", "log.publish:run_ended=eio")],
    );
    assert_eq!(o.code, Some(4), "{}", o.stderr);
    let j = &o.reply;
    assert_eq!(sj(j, &["outcome"]), "failed");
    assert_eq!(sj(j, &["reason"]), "record_failed");
    assert_eq!(sj(j, &["effects", "run"]), "started");
    assert_eq!(
        sj(j, &["causes", "0", "operation"]),
        "link run_ended record"
    );
    let retained = common::strs(j, &["retained"]);
    let dir = e.audit_dir(&r);
    assert!(retained.contains(&format!("{dir}/runs/1")), "{retained:?}");
    // The unpublished record's stage file is reported by status, not listed.
    assert!(
        !retained
            .iter()
            .any(|x| x.starts_with(&format!("{dir}/stage"))),
        "{retained:?}"
    );
    assert!(
        retained
            .iter()
            .any(|x| x.starts_with(&format!("{dir}/diag/"))),
        "{retained:?}"
    );
    assert_eq!(e.log_kinds(&r).last().unwrap(), "run_started");
    let o = run(&e, &r, &p, &[]);
    assert_eq!(o.code, Some(5), "{}", o.stderr);
    let kinds = e.log_kinds(&r);
    let first_end = kinds.iter().position(|k| k == "run_ended").unwrap() + 1;
    assert_eq!(sj(&body_of(&e, &r, first_end), &["cause"]), "process_gone");
}

/// Whether request 1 carried exactly the pinned system, tools and question.
#[cfg(feature = "sabotage")]
fn sent_as_pinned(e: &Env, r: &str, body: &[u8]) -> (bool, bool, bool) {
    let (_, system, tools, _) = arrangement(e, r);
    let s = String::from_utf8(body.to_vec()).unwrap();
    (
        s.contains(&format!(
            r#""system":{},"#,
            String::from_utf8(system).unwrap()
        )),
        s.contains(&format!(
            r#""tools":{},"#,
            String::from_utf8(tools).unwrap()
        )),
        s.contains(r#""text":"  Is the restart path safe?  \n""#),
    )
}

#[cfg(feature = "sabotage")]
#[test]
fn request_sabotage_is_caught_by_the_pinned_bytes_check() {
    let mut seen = Vec::new();
    for control in [
        "",
        "extra_tool",
        "arrangement_mismatch",
        "paraphrase_question",
    ] {
        let p = provider!(
            "request_sabotage_is_caught_by_the_pinned_bytes_check",
            vec![text_turn("max_tokens")]
        );
        let e = Env::new();
        let r = commissioned(&e, DEFAULT_LIMITS);
        let o = run(&e, &r, &p, &[("STEWART_TEST_SABOTAGE", control)]);
        assert_eq!(o.code, Some(5), "{control}: {}", o.stderr);
        seen.push(sent_as_pinned(&e, &r, &p.bodies()[0]));
    }
    // The control passes; each sabotage breaks exactly its own property.
    assert_eq!(
        seen,
        [
            (true, true, true),
            (true, false, true),
            (false, true, true),
            (true, true, false)
        ]
    );
}

#[cfg(feature = "sabotage")]
#[test]
fn continuation_sabotage_resets_limits_and_notices() {
    // Placement 1 uses 395,000 of 400,000 output tokens and fires the
    // near-limit notice. Continuing, request 1 may ask for at most the 5,000
    // that remain, and the notice, used once per audit, does not fire again.
    let mut results = Vec::new();
    for control in ["", "reset_limits_on_continuation", "reset_notice_allowance"] {
        let p = provider!(
            "continuation_sabotage_resets_limits_and_notices",
            vec![
                Act::Reply(
                    200,
                    vec![],
                    message(r#"[{"type":"text","text":"a"}]"#, "max_tokens", 10, 395_000)
                ),
                Act::Reply(
                    200,
                    vec![],
                    message(r#"[{"type":"text","text":"b"}]"#, "max_tokens", 10, 10)
                ),
            ]
        );
        let e = Env::new();
        let r = commissioned(&e, DEFAULT_LIMITS);
        let sab = [("STEWART_TEST_SABOTAGE", control)];
        let o = run(&e, &r, &p, &sab);
        assert_eq!(o.code, Some(5), "{}", o.stderr);
        let o = run(&e, &r, &p, &sab);
        assert_eq!(o.code, Some(5), "{}", o.stderr);
        let second = String::from_utf8(p.bodies()[1].clone()).unwrap();
        let notices = e.log_kinds(&r).iter().filter(|k| *k == "notice").count();
        results.push((second.contains(r#""max_tokens":5000,"#), notices));
    }
    assert_eq!(results, [(true, 1), (false, 1), (true, 2)]);
}

// ---------------------------------------------------------------------------
// Effort, and a provider that has moved.
//
// The manager's effort travels only as the top-level `output_config` request
// parameter, never as text the auditor reads (INTERFACE 3.2, 6.2). What the
// release sends can stop matching what the provider accepts: the provider may
// rename the parameter, withdraw it or one of its levels, or refuse without an
// error object. Stewart cannot prevent that, so it must report the refusal as
// the provider gave it, without retrying, hiding or reclassifying it (6.5).
// `Surface` models what a provider accepts, so each kind of drift is one
// changed fact, and a parameter added later joins the model the same way.

/// What the fake provider accepts, as far as these tests model it: the
/// top-level request members, the members of `output_config` and the effort
/// levels. `current()` is the provider this release was written against.
#[derive(Clone)]
struct Surface {
    top: Vec<&'static str>,
    output_config: Vec<&'static str>,
    levels: Vec<&'static str>,
}

impl Surface {
    fn current() -> Surface {
        Surface {
            top: vec![
                "model",
                "max_tokens",
                "system",
                "tools",
                "output_config",
                "messages",
            ],
            output_config: vec!["effort"],
            levels: vec!["low", "medium", "high", "xhigh", "max"],
        }
    }

    /// The provider's complaint about a request body, worded as the Messages
    /// API words one, or `None` when it accepts the body.
    fn judge(&self, body: &[u8]) -> Option<String> {
        let Ok(v) = json::parse(body) else {
            return Some("There was an error parsing the body of your request.".into());
        };
        let top = v.obj("").expect("a request body is an object");
        if let Some((k, _)) = top
            .members
            .iter()
            .find(|(k, _)| !self.top.contains(&k.as_str()))
        {
            return Some(format!("{k}: Extra inputs are not permitted"));
        }
        // Without output_config there is nothing more to judge.
        let oc = top.get("output_config")?;
        let oc = oc
            .obj("/output_config")
            .expect("output_config is an object");
        if let Some((k, _)) = oc
            .members
            .iter()
            .find(|(k, _)| !self.output_config.contains(&k.as_str()))
        {
            return Some(format!("output_config.{k}: Extra inputs are not permitted"));
        }
        let level = oc.get("effort")?.as_str().expect("effort is a string");
        if self.levels.contains(&level) {
            return None;
        }
        let names: Vec<String> = self.levels.iter().map(|l| format!("'{l}'")).collect();
        Some(format!(
            "output_config.effort: Input should be {}",
            names.join(", ")
        ))
    }

    /// Answer one request: `accepted` when it passes, else the API's 400.
    fn act(&self, accepted: &str) -> Act {
        Act::Judge(self.clone(), accepted.to_string())
    }
}

/// The Messages API's error body for an invalid request.
fn rejection(why: &str) -> String {
    format!(
        r#"{{"type":"error","error":{{"type":"invalid_request_error","message":{}}},"request_id":"req_drift_body"}}"#,
        json::quote(why)
    )
}

/// An ordinary turn that ends without a tool call.
fn ended_turn() -> String {
    message(
        r#"[{"type":"text","text":"Thinking about it."}]"#,
        "end_turn",
        100,
        10,
    )
}

/// `body` with `member` spliced in after `tools`, where 4.5 puts `X`.
fn with_extra(body: &[u8], member: &[u8]) -> Vec<u8> {
    let tools_end = b"],\"messages\":[";
    let i = body
        .windows(tools_end.len())
        .position(|w| w == tools_end)
        .expect("tools then messages")
        + 1;
    [&body[..i], b",", member, &body[i..]].concat()
}

/// The top-level member names of a request body, in order, and the raw bytes
/// of the members the model reads: `system`, `tools` and `messages`.
fn request_shape(body: &[u8]) -> (Vec<String>, Vec<Vec<u8>>) {
    let v = json::parse(body).unwrap();
    let top = v.obj("").unwrap();
    let names = top.members.iter().map(|(k, _)| k.clone()).collect();
    let read = ["system", "tools", "messages"]
        .iter()
        .map(|k| {
            let x = top.get(k).unwrap();
            body[x.start..x.end].to_vec()
        })
        .collect();
    (names, read)
}

#[test]
fn effort_travels_only_as_a_top_level_parameter() {
    let mut sent = Vec::new();
    for lines in ["", "effort: high\n"] {
        let turn = Surface::current().act(&ended_turn());
        let p = provider!(
            "effort_travels_only_as_a_top_level_parameter",
            vec![turn.clone(), turn]
        );
        let e = Env::new();
        let (r, prepared) = commissioned_with(&e, DEFAULT_LIMITS, lines);
        // The current provider accepts both; the run ends ordinarily.
        let o = run(&e, &r, &p, &[]);
        assert_eq!(o.code, Some(0), "{}", o.stderr);
        assert_eq!(sj(&o.reply, &["data", "ending"]), "ended_unsubmitted");
        let bodies = p.bodies();
        assert_eq!(bodies.len(), 2);
        captures_match_what_was_sent(&e, &r, 1, &bodies);
        let readable =
            std::fs::read_to_string(format!("{}/arrangement.md", latest_prep(&e, &r))).unwrap();
        sent.push((bodies, prepared, pinned_extra(&e, &r), readable));
    }
    let (plain, with) = (&sent[0], &sent[1]);
    let member = br#""output_config":{"effort":"high"}"#;
    // Pinned once at prepare, shown before commissioning, and only when set.
    assert_eq!(plain.2, Vec::<Vec<u8>>::new());
    assert_eq!(with.2, [member.to_vec()]);
    assert!(!plain.1.contains("\"effort\""), "{}", plain.1);
    assert!(with.1.contains(r#""effort":"high""#), "{}", with.1);
    assert!(plain.3.contains("- Effort: not set."), "{}", plain.3);
    assert!(
        with.3.contains("- Effort: high, sent with every request as the provider parameter output_config.effort."),
        "{}",
        with.3
    );
    for k in 0..2 {
        // Every request differs only by the one top-level member, after tools.
        assert_eq!(
            String::from_utf8(with.0[k].clone()).unwrap(),
            String::from_utf8(with_extra(&plain.0[k], member)).unwrap(),
            "request {}",
            k + 1
        );
        let (names, read) = request_shape(&with.0[k]);
        assert_eq!(
            names,
            [
                "model",
                "max_tokens",
                "system",
                "tools",
                "output_config",
                "messages"
            ]
        );
        // Nothing the model reads mentions it.
        assert_eq!(read, request_shape(&plain.0[k]).1);
        for part in read {
            let text = String::from_utf8(part).unwrap();
            assert!(!text.to_lowercase().contains("effort"), "{text}");
        }
    }
}

/// One way a provider can have moved, the answer it gives, and what the
/// manager must then see: the status, error type, message and request id,
/// or `None` where the provider gave none.
struct Drift {
    name: &'static str,
    effort: &'static str,
    act: Act,
    body: String,
    error_type: Option<&'static str>,
    error_message: Option<String>,
    request_id: Option<&'static str>,
}

fn drift(name: &'static str, effort: &'static str, surface: Surface) -> Drift {
    let probe = format!(r#"{{"output_config":{{"effort":"{effort}"}}}}"#);
    let why = surface
        .judge(probe.as_bytes())
        .expect("the drift refuses the effort");
    Drift {
        name,
        effort,
        act: surface.act(&ended_turn()),
        body: rejection(&why),
        error_type: Some("invalid_request_error"),
        error_message: Some(why),
        request_id: Some("req_drift"),
    }
}

#[test]
fn a_provider_that_has_moved_is_reported_as_it_answered() {
    let mut renamed = Surface::current();
    renamed.output_config = vec!["reasoning_effort"];
    let mut removed = Surface::current();
    removed.top.retain(|k| *k != "output_config");
    let mut withdrawn = Surface::current();
    withdrawn.levels.retain(|l| *l != "max");
    let graceless = "<html><body><h1>400 Bad Request</h1></body></html>";
    let drifts = [
        drift("renamed", "high", renamed),
        drift("removed", "high", removed),
        drift("level withdrawn", "max", withdrawn),
        Drift {
            name: "graceless",
            effort: "high",
            act: Act::Reply(400, vec![], graceless.into()),
            body: graceless.into(),
            error_type: None,
            error_message: None,
            request_id: None,
        },
    ];
    assert_eq!(
        drifts[0].error_message.as_deref(),
        Some("output_config.effort: Extra inputs are not permitted")
    );
    assert_eq!(
        drifts[1].error_message.as_deref(),
        Some("output_config: Extra inputs are not permitted")
    );
    for d in drifts {
        let p = provider!(
            "a_provider_that_has_moved_is_reported_as_it_answered",
            vec![d.act.clone(), d.act.clone()]
        );
        let e = Env::new();
        let (r, _) = commissioned_with(&e, DEFAULT_LIMITS, &format!("effort: {}\n", d.effort));
        for run_no in [1u64, 2] {
            let o = run(&e, &r, &p, &[]);
            let ctx = format!("{} run {run_no}: {}", d.name, o.stderr);
            assert_eq!(o.code, Some(5), "{ctx}");
            assert_eq!(n(&o.reply, &["data", "run"]), run_no, "{ctx}");
            assert_eq!(
                sj(&o.reply, &["data", "cause"]),
                "provider_rejected",
                "{ctx}"
            );
            // One attempt per placement: a refusal is not retried.
            assert_eq!(p.requests().len() as u64, run_no, "{ctx}");
            let body = String::from_utf8(p.bodies()[run_no as usize - 1].clone()).unwrap();
            assert!(
                body.contains(&format!(r#","output_config":{{"effort":"{}"}},"#, d.effort)),
                "{ctx}"
            );
            let ended = body_of(&e, &r, last_of(&e, &r, "run_ended"));
            for v in [&ended, at(&o.reply, &["data"])] {
                assert_eq!(n(v, &["provider", "status"]), 400, "{ctx}");
                let fact = |k: &str| at(v, &["provider", k]).as_str().map(str::to_string);
                assert_eq!(fact("error_type").as_deref(), d.error_type, "{ctx}");
                assert_eq!(fact("error_message"), d.error_message, "{ctx}");
                assert_eq!(fact("request_id").as_deref(), d.request_id, "{ctx}");
                assert_eq!(
                    (
                        n(v, &["provider", "request"]),
                        n(v, &["provider", "attempt"])
                    ),
                    (1, 1),
                    "{ctx}"
                );
            }
            // The raw answer is kept, byte for byte.
            assert_eq!(
                run_file(&e, &r, run_no, "response-1-1.bin"),
                d.body.as_bytes(),
                "{ctx}"
            );
            assert_eq!(
                sj(&attempt(&e, &r, run_no, 1, 1), &["then"]),
                "end",
                "{ctx}"
            );
        }
    }
}

#[cfg(all(feature = "fault-injection", feature = "sabotage"))]
#[test]
fn effort_and_rejection_sabotage_break_only_their_own_property() {
    let sab = |c| {
        [
            ("STEWART_TEST_SABOTAGE", c),
            ("STEWART_TEST_RETRY_DELAYS", "0,0,0"),
        ]
    };
    let turn = || Surface::current().act(&ended_turn());
    let question = r#""text":"  Is the restart path safe?  \n""#;
    let member = r#","output_config":{"effort":"high"},"#;

    // misspell_effort: the request names a parameter the provider does not
    // know; the arrangement still pins the right one, and the provider's
    // refusal reaches the manager as it gave it.
    for (control, code, misspelled) in [("", 0, false), ("misspell_effort", 5, true)] {
        let p = provider!(
            "effort_and_rejection_sabotage_break_only_their_own_property",
            vec![turn(), turn()]
        );
        let e = Env::new();
        let (r, _) = commissioned_with(&e, DEFAULT_LIMITS, "effort: high\n");
        let o = run(&e, &r, &p, &sab(control));
        assert_eq!(o.code, Some(code), "{control}: {}", o.stderr);
        let body = String::from_utf8(p.bodies()[0].clone()).unwrap();
        assert_eq!(body.contains(r#""eefort":"high""#), misspelled, "{control}");
        assert_eq!(
            pinned_extra(&e, &r),
            [br#""output_config":{"effort":"high"}"#.to_vec()]
        );
        if misspelled {
            assert_eq!(
                sj(&o.reply, &["data", "provider", "error_message"]),
                "output_config.eefort: Extra inputs are not permitted"
            );
        }
    }

    // effort_in_prompt: the effort leaves the parameters for the question.
    for (control, as_parameter, in_question) in
        [("", true, false), ("effort_in_prompt", false, true)]
    {
        let p = provider!(
            "effort_and_rejection_sabotage_break_only_their_own_property",
            vec![turn(), turn()]
        );
        let e = Env::new();
        let (r, _) = commissioned_with(&e, DEFAULT_LIMITS, "effort: high\n");
        let o = run(&e, &r, &p, &sab(control));
        assert_eq!(o.code, Some(0), "{control}: {}", o.stderr);
        let body = String::from_utf8(p.bodies()[0].clone()).unwrap();
        assert_eq!(body.contains(member), as_parameter, "{control}");
        assert_eq!(body.contains(question), !in_question, "{control}");
        assert_eq!(
            body.contains(r#""text":"  Is the restart path safe?  \nEffort: high.\n""#),
            in_question,
            "{control}"
        );
    }

    // hide_provider_message: the manager loses the provider's words, which
    // the attempt record still holds.
    for (control, shown) in [("", true), ("hide_provider_message", false)] {
        let p = provider!(
            "effort_and_rejection_sabotage_break_only_their_own_property",
            vec![error(400, None, "invalid_request_error")]
        );
        let e = Env::new();
        let r = commissioned(&e, DEFAULT_LIMITS);
        let o = run(&e, &r, &p, &sab(control));
        assert_eq!(o.code, Some(5), "{control}: {}", o.stderr);
        let words = "invalid_request_error message";
        assert_eq!(
            !is_null(&o.reply, &["data", "provider", "error_message"]),
            shown,
            "{control}"
        );
        assert_eq!(sj(&attempt(&e, &r, 1, 1, 1), &["error", "message"]), words);
    }

    // rejection_as_unavailable: a refusal is retried and reported as an
    // unavailable provider.
    for (control, requests, cause) in [
        ("", 1, "provider_rejected"),
        ("rejection_as_unavailable", 4, "provider_unavailable"),
    ] {
        let p = provider!(
            "effort_and_rejection_sabotage_break_only_their_own_property",
            vec![error(400, None, "invalid_request_error"); 4]
        );
        let e = Env::new();
        let r = commissioned(&e, DEFAULT_LIMITS);
        let o = run(&e, &r, &p, &sab(control));
        assert_eq!(o.code, Some(5), "{control}: {}", o.stderr);
        assert_eq!(sj(&o.reply, &["data", "cause"]), cause, "{control}");
        assert_eq!(p.requests().len(), requests, "{control}");
    }
}
