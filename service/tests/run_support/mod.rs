//! A scripted fake provider on a loopback listener and the helpers that run
//! `stewart run` against it, shared by `run.rs` and `run_faults.rs`.
//!
//! The fake binds 127.0.0.1 on port 0 in the test process and answers each
//! connection from a script, keeping every request's exact bytes as an
//! independent witness of what the run sent. Each test runs the real binary
//! from an unrelated working directory with its own folder, archive and
//! destination.

#![allow(dead_code)]

use crate::common::{Env, at, bin, s};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use stewart::json::{self, Json};

/// A reply computed from the request's body.
pub type Responder = Arc<dyn Fn(&[u8]) -> String + Send + Sync>;

/// What the fake provider does with one connection.
#[derive(Clone)]
pub enum Act {
    /// Read the request, answer with this status, extra headers and body.
    Reply(u16, Vec<(String, String)>, String),
    /// Read the request and never answer; hold the connection until the
    /// client closes it.
    Hang,
    /// Read the request and answer 200 with the body this computes from
    /// the request's body.
    Respond(Responder),
}

pub struct Provider {
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

/// A loopback listener on an ephemeral port. Binding is required: where it
/// is not permitted the test fails, naming itself, rather than passing
/// without having run.
pub fn listener() -> TcpListener {
    TcpListener::bind("127.0.0.1:0").unwrap_or_else(|e| {
        panic!(
            "{}: binding a required loopback listener failed: {e}; rerun where loopback binding is permitted",
            thread::current().name().unwrap_or("this test")
        )
    })
}

/// Read one request: the head, then `content-length` body bytes.
pub fn read_request(s: &mut impl Read) -> Vec<u8> {
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
        Act::Hang => {
            let mut sink = Vec::new();
            let _ = s.read_to_end(&mut sink);
        }
        Act::Respond(f) => {
            let at = req
                .windows(4)
                .position(|w| w == b"\r\n\r\n")
                .map_or(req.len(), |i| i + 4);
            reply(&mut s, 200, &[], &f(&req[at..]));
        }
    }
}

impl Provider {
    /// Start a provider answering connections in script order. When the
    /// script runs out it answers 500 without a retry-after, so a test that
    /// sends more requests than it planned fails visibly.
    pub fn start(script: Vec<Act>) -> Provider {
        let l = listener();
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

    pub fn url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port)
    }

    pub fn requests(&self) -> Vec<Vec<u8>> {
        self.requests.lock().unwrap().clone()
    }

    /// Wait until `n` requests have arrived.
    pub fn wait_for(&self, n: usize) {
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
pub fn message(content: &str, stop: &str, input: u64, output: u64) -> String {
    format!(
        r#"{{"id":"msg_1","type":"message","role":"assistant","model":"claude-test","content":{content},"stop_reason":"{stop}","stop_sequence":null,"usage":{{"input_tokens":{input},"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":{output}}}}}"#
    )
}

pub fn ok(content: &str, stop: &str) -> Act {
    Act::Reply(200, vec![], message(content, stop, 100, 10))
}

pub fn text_turn(stop: &str) -> Act {
    ok(r#"[{"type":"text","text":"Thinking about it."}]"#, stop)
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
pub fn submitting_provider() -> Provider {
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
    Provider::start(vec![
        ok(
            r#"[{"type":"tool_use","id":"t1","name":"record_account","input":{"text":"The restart path re-sends one reminder."}},{"type":"tool_use","id":"t2","name":"prepare","input":{}}]"#,
            "tool_use",
        ),
        Act::Respond(submit),
        text_turn("end_turn"),
        text_turn("end_turn"),
    ])
}

pub const DEFAULT_LIMITS: (u64, u64, u64) = (200, 20_000_000, 400_000);

/// A commissioned open-inquiry audit over one material, with these limits.
pub fn commissioned(e: &Env, limits: (u64, u64, u64)) -> String {
    let r = e.new_ref();
    let q = format!(
        "---\nstewart: question/2\nfamily: open-inquiry\nmodel: claude-opus-5-5\ndestination: {}\nlimit-turns: {}\nlimit-input-tokens: {}\nlimit-output-tokens: {}\n---\n  Is the restart path safe?  \n",
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
    let h = s(&o.json(), &["data", "prepared"]).to_string();
    let o = e.commission(&r, &h);
    assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
    r
}

/// `stewart run <r> --json` against `url`, with every variable that could
/// redirect it removed and `extra` set.
pub fn run_cmd(e: &Env, r: &str, url: &str, extra: &[(&str, &str)]) -> Command {
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

pub struct Ran {
    pub code: Option<i32>,
    pub reply: Json,
    pub stderr: String,
}

pub fn finish(child: Child) -> Ran {
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

pub fn run(e: &Env, r: &str, p: &Provider, extra: &[(&str, &str)]) -> Ran {
    finish(run_cmd(e, r, &p.url(), extra).spawn().unwrap())
}

/// Run where the process is expected to die before replying; returns its
/// exit code (`None` when a signal ended it) and checks it wrote no reply.
pub fn run_killed(e: &Env, r: &str, p: &Provider, extra: &[(&str, &str)]) -> Option<i32> {
    let o = run_cmd(e, r, &p.url(), extra).output().unwrap();
    assert!(
        o.stdout.is_empty(),
        "{}",
        String::from_utf8_lossy(&o.stdout)
    );
    o.status.code()
}

pub fn n(v: &Json, path: &[&str]) -> u64 {
    at(v, path)
        .as_u64()
        .unwrap_or_else(|| panic!("{path:?} is not an integer"))
}

pub fn is_null(v: &Json, path: &[&str]) -> bool {
    at(v, path).is_null()
}

/// The `body` of log record `n`.
pub fn body_of(e: &Env, r: &str, n: usize) -> Json {
    at(&e.log_record(r, n), &["body"]).clone()
}

/// The index of the last log record of `kind` (1-based).
pub fn last_of(e: &Env, r: &str, kind: &str) -> usize {
    e.log_kinds(r).iter().rposition(|k| k == kind).expect(kind) + 1
}

pub fn run_file(e: &Env, r: &str, run: u64, name: &str) -> Vec<u8> {
    std::fs::read(format!("{}/runs/{run}/{name}", e.audit_dir(r))).unwrap()
}

pub fn record_body(bytes: &[u8]) -> Json {
    at(&json::parse(bytes).unwrap(), &["body"]).clone()
}

pub fn attempt(e: &Env, r: &str, run: u64, k: u64, a: u64) -> Json {
    record_body(&run_file(e, r, run, &format!("attempt-{k}-{a}.json")))
}

pub fn kill(child: &Child, sig: i32) {
    // SAFETY: sending a signal to our own child process.
    let rc = unsafe { libc::kill(child.id() as i32, sig) };
    assert_eq!(rc, 0);
}

/// Publish `close_requested` the way a concurrent close does, through the
/// crate's log writer. Only the request is published, so the run's reaction
/// is observed without the seal and delivery a full close goes on to make.
pub fn request_close(r: &str) {
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
