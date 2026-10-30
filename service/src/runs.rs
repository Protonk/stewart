//! Run captures (INTERFACE 4.5): the directory `runs/<n>` of each placement,
//! its raw captures, its linked records (`provider_attempt`, `tool_result`)
//! and the accounting of a placement that has no `run_ended` (6.4).
//!
//! `runs/<n>` is created with `mkdirat` right after its `run_started` is
//! published. Only the holder of the active lock writes there, so names in it
//! are assigned in sequence rather than claimed: a name that already exists,
//! including `runs/<n>` itself, is an archive write failure (6.5), never
//! overwritten or skipped.
//!
//! | Name | Form |
//! | --- | --- |
//! | `request-<k>.json` | Raw capture: one header line ending in the appended messages |
//! | `response-<k>-<a>.bin` | Raw: the body of attempt `a` as received |
//! | `attempt-<k>-<a>.json` | Linked record, kind `provider_attempt` |
//! | `call-<c>.json` | Raw: the exact bytes of one `tool_use` block |
//! | `result-<c>.json` | Linked record, kind `tool_result` |
//! | `stage/` | Stage files of this placement's linked records |
//!
//! Raw captures are decoded tolerantly, never as control records. Linked
//! records are `stewart.record/1` records decoded strictly; unlike log
//! records their bodies carry no `prev`.

use crate::archive::{Audit, RECORD_LIMIT, decode_record};
use crate::fsx::{Dir, ReadError};
use crate::json::{self, J, JsonError, Obj};
use crate::reply::Cause;
use crate::usage::{Charge, Usage};
use crate::util;
use std::collections::BTreeMap;
use std::io;

/// Response bodies are captured and decoded up to this size (6.6).
pub const RESPONSE_LIMIT: u64 = 32 * 1024 * 1024;
/// The recorded error message is cut to at most this many bytes.
pub const ERROR_MESSAGE_BYTES: usize = 1_024;
/// The response headers an attempt record holds, matched without regard to case.
pub const RECORDED_HEADERS: [&str; 3] = ["content-type", "request-id", "retry-after"];

pub const ATTEMPT_OUTCOMES: [&str; 8] = [
    "response",
    "response_undecodable",
    "http_error",
    "timeout",
    "connection_failed",
    "connection_lost",
    "aborted_by_close",
    "aborted_by_signal",
];
pub const REQUEST_WRITTEN: [&str; 3] = ["none", "partial", "complete"];
pub const THEN: [&str; 3] = ["use", "retry", "end"];
pub const CALL_OUTCOMES: [&str; 3] = ["completed", "refused", "failed"];

const NUM_MAX: u64 = 1 << 48;

pub fn dir_name(run: u64) -> String {
    format!("runs/{run}")
}
pub fn request_name(k: u64) -> String {
    format!("request-{k}.json")
}
pub fn response_name(k: u64, a: u64) -> String {
    format!("response-{k}-{a}.bin")
}
pub fn attempt_name(k: u64, a: u64) -> String {
    format!("attempt-{k}-{a}.json")
}
pub fn call_name(c: u64) -> String {
    format!("call-{c}.json")
}
pub fn result_name(c: u64) -> String {
    format!("result-{c}.json")
}

// ---------------------------------------------------------------------------
// Writing.

/// A placement's run directory, held by the process that holds the lock.
pub struct RunDir {
    pub run: u64,
    pub dir: Dir,
    pub stage: Dir,
    /// The directory's absolute path, for causes and retained locations.
    pub path: String,
}

impl RunDir {
    /// Create `runs/<run>` and its `stage/` right after `run_started` is
    /// published. An existing `runs/<run>` is an archive write failure: it is
    /// never adopted.
    pub fn create(audit: &Audit, run: u64) -> Result<RunDir, Cause> {
        let path = audit.abs(&dir_name(run));
        let runs = audit
            .sub("runs")
            .map_err(|e| Cause::io("open runs directory", &e).at(audit.abs("runs")))?;
        runs.mkdir(&run.to_string())
            .map_err(|e| Cause::io("create run directory", &e).at(&path))?;
        let dir = runs
            .open_dir(&run.to_string())
            .map_err(|e| Cause::io("open run directory", &e).at(&path))?;
        dir.mkdir("stage")
            .map_err(|e| Cause::io("create run stage directory", &e).at(format!("{path}/stage")))?;
        let stage = dir
            .open_dir("stage")
            .map_err(|e| Cause::io("open run stage directory", &e).at(format!("{path}/stage")))?;
        runs.sync()
            .map_err(|e| Cause::io("fsync runs directory", &e).at(audit.abs("runs")))?;
        Ok(RunDir {
            run,
            dir,
            stage,
            path,
        })
    }

    /// Write a raw capture as an exclusive file. A taken name is a failure.
    fn write_raw(&self, what: &str, name: &str, bytes: &[u8]) -> Result<(), Cause> {
        self.dir.write_excl(name, bytes).map_err(|e| {
            Cause::io(format!("write {what} ({})", e.step.name()), &e.err)
                .at(format!("{}/{name}", self.path))
        })
    }

    /// `request-<k>.json`, written before the first attempt of request `k`
    /// (fault point `provider.request_capture`).
    pub fn write_request(&self, k: u64, capture: &[u8]) -> Result<(), Cause> {
        let name = request_name(k);
        crate::fault!("provider.request_capture").map_err(|e| {
            Cause::io("write request capture", &e).at(format!("{}/{name}", self.path))
        })?;
        self.write_raw("request capture", &name, capture)
    }

    /// `response-<k>-<a>.bin`: the body of attempt `a` as received, after
    /// removing chunked transfer coding, at most `RESPONSE_LIMIT` bytes
    /// (fault point `provider.response_capture`).
    pub fn write_response(&self, k: u64, a: u64, body: &[u8]) -> Result<(), Cause> {
        let name = response_name(k, a);
        crate::fault!("provider.response_capture").map_err(|e| {
            Cause::io("write response capture", &e).at(format!("{}/{name}", self.path))
        })?;
        self.write_raw("response capture", &name, body)
    }

    /// `call-<c>.json`: the bytes of one `tool_use` block, from its `{` to
    /// its `}`, written before the block is executed.
    pub fn write_call(&self, c: u64, block: &[u8]) -> Result<(), Cause> {
        self.write_raw("call capture", &call_name(c), block)
    }

    /// Publish a linked record of `kind` (`provider_attempt` or
    /// `tool_result`) under `name`: stage it in `runs/<n>/stage/` (fault
    /// point `stage.torn:<kind>`), then link it (fault point
    /// `runs.publish:<kind>` just before) and sync the run directory. A taken
    /// name is a failure, never retried under another name. Returns the
    /// record's bytes, whose SHA-256 a later record may bind.
    pub fn publish(
        &self,
        audit: &Audit,
        kind: &'static str,
        name: &str,
        body: J,
    ) -> Result<Vec<u8>, Cause> {
        let bytes = audit.record(kind, body);
        let at = format!("{}/{name}", self.path);
        let stage_name = format!(
            "{}.json",
            crate::ids::random_token().map_err(|e| Cause::io("random stage name", &e))?
        );
        crate::log::write_stage(&self.stage, &stage_name, &bytes, kind).map_err(|e| {
            Cause::io(format!("write stage record ({})", e.step.name()), &e.err)
                .at(format!("{}/stage/{stage_name}", self.path))
        })?;
        crate::fault!("runs.publish", kind)
            .map_err(|e| Cause::io(format!("link {kind} record"), &e).at(&at))?;
        self.stage
            .link_to(&stage_name, &self.dir, name)
            .map_err(|e| Cause::io(format!("link {kind} record"), &e).at(&at))?;
        self.dir
            .sync()
            .map_err(|e| Cause::io("fsync run directory", &e).at(&self.path))?;
        Ok(bytes)
    }
}

// ---------------------------------------------------------------------------
// Request captures and bodies.

/// The body of request `k` (4.5), spliced from pinned bytes and never
/// re-serialized: `{"model":<M>,"max_tokens":<T>,"system":<S>,"tools":<U><X>,
/// "messages":[<A_1>,…,<A_k>]}`. `extra` holds each member of the
/// arrangement's `request_extra` object as its raw `"key":value` bytes (none
/// in this release); `messages` every message so far, each compact JSON.
pub fn request_body(
    model: &[u8],
    max_tokens: u64,
    system: &[u8],
    tools: &[u8],
    extra: &[&[u8]],
    messages: &[&[u8]],
) -> Vec<u8> {
    let mut b = Vec::new();
    b.extend_from_slice(b"{\"model\":");
    b.extend_from_slice(model);
    b.extend_from_slice(format!(",\"max_tokens\":{max_tokens},\"system\":").as_bytes());
    b.extend_from_slice(system);
    b.extend_from_slice(b",\"tools\":");
    b.extend_from_slice(tools);
    for m in extra {
        b.push(b',');
        b.extend_from_slice(m);
    }
    b.extend_from_slice(b",\"messages\":[");
    join_into(&mut b, messages);
    b.extend_from_slice(b"]}");
    b
}

fn join_into(b: &mut Vec<u8>, parts: &[&[u8]]) {
    for (i, p) in parts.iter().enumerate() {
        if i > 0 {
            b.push(b',');
        }
        b.extend_from_slice(p);
    }
}

/// A request capture: one line of compact JSON and an LF,
/// `{"request":<k>,"max_tokens":<T>,"body_bytes":<B>,"body_sha256":"<hex>",
/// "appended":[<A_k>]}`, where `appended` holds the messages request `k`
/// appends exactly as they appear in `body`.
pub fn request_capture(k: u64, max_tokens: u64, body: &[u8], appended: &[&[u8]]) -> Vec<u8> {
    let mut b = format!(
        "{{\"request\":{k},\"max_tokens\":{max_tokens},\"body_bytes\":{},\"body_sha256\":\"{}\",\"appended\":[",
        body.len(),
        util::sha256_hex(body)
    )
    .into_bytes();
    join_into(&mut b, appended);
    b.extend_from_slice(b"]}\n");
    b
}

/// The header of a complete request capture.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RequestHeader {
    pub request: u64,
    pub max_tokens: u64,
    pub body_bytes: u64,
    pub body_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RequestCapture {
    Complete(RequestHeader),
    /// It does not end with `]}` and an LF: cut off, and its request was
    /// never sent.
    CutOff,
    /// It ends as a capture does but its header is not Stewart's layout.
    Unreadable,
}

/// Read a request capture tolerantly: the header is matched by its fixed
/// layout; the appended messages, which carry provider bytes, are not decoded.
pub fn parse_request_capture(bytes: &[u8]) -> RequestCapture {
    if !bytes.ends_with(b"]}\n") {
        return RequestCapture::CutOff;
    }
    fn num<'a>(b: &'a [u8], key: &[u8]) -> Option<(u64, &'a [u8])> {
        let rest = b.strip_prefix(key)?;
        let n = rest.iter().take_while(|c| c.is_ascii_digit()).count();
        let digits = std::str::from_utf8(&rest[..n]).ok()?;
        Some((
            crate::names::parse_num(digits).or_else(|| (digits == "0").then_some(0))?,
            &rest[n..],
        ))
    }
    let parse = || {
        let (request, r) = num(bytes, b"{\"request\":")?;
        let (max_tokens, r) = num(r, b",\"max_tokens\":")?;
        let (body_bytes, r) = num(r, b",\"body_bytes\":")?;
        let r = r.strip_prefix(b",\"body_sha256\":\"")?;
        let sha = std::str::from_utf8(r.get(..64)?).ok()?;
        if !util::is_hex64(sha) {
            return None;
        }
        r[64..].strip_prefix(b"\",\"appended\":[")?;
        Some(RequestHeader {
            request,
            max_tokens,
            body_bytes,
            body_sha256: sha.to_string(),
        })
    };
    match parse() {
        Some(h) => RequestCapture::Complete(h),
        None => RequestCapture::Unreadable,
    }
}

/// Read `request-<k>.json` tolerantly without reading its messages: only
/// its header and its last bytes decide what it is.
pub fn read_request_capture(dir: &Dir, k: u64) -> Result<RequestCapture, ReadError> {
    use std::os::unix::fs::FileExt;
    const HEAD: u64 = 256;
    let (f, st) = dir.open_regular(&request_name(k))?;
    let mut bytes = vec![0u8; st.size.min(2 * HEAD) as usize];
    if st.size <= 2 * HEAD {
        f.read_exact_at(&mut bytes, 0).map_err(ReadError::Io)?;
    } else {
        // The header is in the first bytes and completeness in the last
        // three; joined, they parse exactly as the whole capture would.
        bytes.truncate(HEAD as usize);
        f.read_exact_at(&mut bytes, 0).map_err(ReadError::Io)?;
        let mut tail = [0u8; 3];
        f.read_exact_at(&mut tail, st.size - 3)
            .map_err(ReadError::Io)?;
        bytes.extend_from_slice(&tail);
    }
    Ok(parse_request_capture(&bytes))
}

/// The `tool_result` block sent for a result record (4.5):
/// `{"type":"tool_result","tool_use_id":<ID>,"content":<content>,"is_error":<is_error>}`,
/// with the ID written as in the record and `content` its exact bytes.
pub fn tool_result_block(tool_use_id: &str, content: &[u8], is_error: bool) -> Vec<u8> {
    let mut b = b"{\"type\":\"tool_result\",\"tool_use_id\":".to_vec();
    json::escape_into(tool_use_id, &mut b);
    b.extend_from_slice(b",\"content\":");
    b.extend_from_slice(content);
    b.extend_from_slice(if is_error {
        b",\"is_error\":true}"
    } else {
        b",\"is_error\":false}"
    });
    b
}

/// A recorded response header value: leading and trailing spaces and tabs
/// removed, and each byte outside 0x20–0x7E written `%XX` in uppercase hex.
pub fn header_value(raw: &[u8]) -> String {
    let start = raw.iter().position(|b| *b != b' ' && *b != b'\t');
    let end = raw.iter().rposition(|b| *b != b' ' && *b != b'\t');
    let trimmed = match (start, end) {
        (Some(s), Some(e)) => &raw[s..=e],
        _ => &[][..],
    };
    let mut out = String::new();
    for &b in trimmed {
        if (0x20..=0x7E).contains(&b) {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

/// Cut `s` to at most `max` bytes on a character boundary.
pub fn cut(s: &str, max: usize) -> &str {
    if s.len() <= max {
        return s;
    }
    let mut end = max;
    while !s.is_char_boundary(end) {
        end -= 1;
    }
    &s[..end]
}

// ---------------------------------------------------------------------------
// `provider_attempt`.

/// The recorded response headers, each the values received in order, `[]`
/// when absent.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct Headers {
    pub content_type: Vec<String>,
    pub request_id: Vec<String>,
    pub retry_after: Vec<String>,
}

/// The response capture an attempt record binds.
#[derive(Debug, Clone, PartialEq)]
pub struct ResponseFile {
    /// `response-<k>-<a>.bin`.
    pub file: String,
    pub bytes: u64,
    pub sha256: String,
    /// False when the body was cut off or exceeded 32 MiB.
    pub complete: bool,
}

/// The error body's facts, each `None` when absent.
#[derive(Debug, Clone, PartialEq)]
pub struct ErrorFacts {
    /// `error.type`.
    pub kind: Option<String>,
    /// `error.message`, cut to at most 1,024 bytes on a character boundary.
    pub message: Option<String>,
    pub request_id: Option<String>,
}

/// A decoded message's usage, absent or null cache counts written 0.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ReportedUsage {
    pub input_tokens: u64,
    pub cache_creation_input_tokens: u64,
    pub cache_read_input_tokens: u64,
    pub output_tokens: u64,
}

impl ReportedUsage {
    pub fn charge(&self) -> Charge {
        Charge::reported(
            self.input_tokens,
            self.cache_creation_input_tokens,
            self.cache_read_input_tokens,
            self.output_tokens,
        )
    }
}

/// The `provider_attempt` record of one attempt (4.5), written when the
/// attempt ends.
#[derive(Debug, Clone, PartialEq)]
pub struct ProviderAttempt {
    pub request: u64,
    pub attempt: u64,
    pub started_at: String,
    pub ended_at: String,
    pub elapsed_ms: u64,
    /// The request timeout in force.
    pub timeout_seconds: u64,
    /// `none`, `partial` or `complete`: how much of the request reached the
    /// connection.
    pub request_written: String,
    /// One of `ATTEMPT_OUTCOMES` (6.6).
    pub outcome: String,
    /// The HTTP status, or `None` without a status line.
    pub status: Option<u64>,
    pub headers: Headers,
    /// `None` when no status line was received.
    pub response: Option<ResponseFile>,
    /// When the body decodes as an error body.
    pub error: Option<ErrorFacts>,
    pub stop_reason: Option<String>,
    pub model: Option<String>,
    pub usage: Option<ReportedUsage>,
    /// What the attempt added to the allowances (6.4).
    pub charged: Charge,
    /// Prose saying why a response was undecodable.
    pub problem: Option<String>,
    /// `use`, `retry` or `end`.
    pub then: String,
    /// The delay before the next attempt; `Some` exactly when `then` is `retry`.
    pub delay_ms: Option<u64>,
}

fn opt_string(o: &Obj, k: &str) -> Result<Option<String>, JsonError> {
    Ok(o.str_or_null(k)?.map(str::to_string))
}

impl ProviderAttempt {
    pub fn to_j(&self) -> J {
        let headers = J::obj()
            .with("content-type", json::strs(&self.headers.content_type))
            .with("request-id", json::strs(&self.headers.request_id))
            .with("retry-after", json::strs(&self.headers.retry_after));
        J::obj()
            .with("request", self.request)
            .with("attempt", self.attempt)
            .with("started_at", self.started_at.as_str())
            .with("ended_at", self.ended_at.as_str())
            .with("elapsed_ms", self.elapsed_ms)
            .with("timeout_seconds", self.timeout_seconds)
            .with("request_written", self.request_written.as_str())
            .with("outcome", self.outcome.as_str())
            .with("status", self.status)
            .with("headers", headers)
            .with(
                "response",
                match &self.response {
                    Some(r) => J::obj()
                        .with("file", r.file.as_str())
                        .with("bytes", r.bytes)
                        .with("sha256", r.sha256.as_str())
                        .with("complete", r.complete),
                    None => J::Null,
                },
            )
            .with(
                "error",
                match &self.error {
                    Some(e) => J::obj()
                        .with("type", e.kind.as_deref())
                        .with("message", e.message.as_deref())
                        .with("request_id", e.request_id.as_deref()),
                    None => J::Null,
                },
            )
            .with("stop_reason", self.stop_reason.as_deref())
            .with("model", self.model.as_deref())
            .with(
                "usage",
                match &self.usage {
                    Some(u) => J::obj()
                        .with("input_tokens", u.input_tokens)
                        .with("cache_creation_input_tokens", u.cache_creation_input_tokens)
                        .with("cache_read_input_tokens", u.cache_read_input_tokens)
                        .with("output_tokens", u.output_tokens),
                    None => J::Null,
                },
            )
            .with("charged", self.charged.to_j())
            .with("problem", self.problem.as_deref())
            .with("then", self.then.as_str())
            .with("delay_ms", self.delay_ms)
    }

    pub fn decode(b: &Obj) -> Result<ProviderAttempt, JsonError> {
        b.exactly(&[
            "request",
            "attempt",
            "started_at",
            "ended_at",
            "elapsed_ms",
            "timeout_seconds",
            "request_written",
            "outcome",
            "status",
            "headers",
            "response",
            "error",
            "stop_reason",
            "model",
            "usage",
            "charged",
            "problem",
            "then",
            "delay_ms",
        ])?;
        let request = b.u64("request", NUM_MAX)?;
        let attempt = b.u64("attempt", NUM_MAX)?;
        for k in ["started_at", "ended_at"] {
            if !util::is_utc_ms(b.str(k)?) {
                return Err(b.invalid(k, "expected a UTC time with milliseconds"));
            }
        }
        let h = b.obj("headers")?;
        h.exactly(&RECORDED_HEADERS)?;
        let strings = |k: &str| -> Result<Vec<String>, JsonError> {
            Ok(h.strs(k)?.into_iter().map(str::to_string).collect())
        };
        let headers = Headers {
            content_type: strings("content-type")?,
            request_id: strings("request-id")?,
            retry_after: strings("retry-after")?,
        };
        let response = match b.obj_or_null("response")? {
            Some(r) => {
                r.exactly(&["file", "bytes", "sha256", "complete"])?;
                let file = r.str("file")?.to_string();
                if file != response_name(request, attempt) {
                    return Err(r.invalid(
                        "file",
                        format!("expected {}", response_name(request, attempt)),
                    ));
                }
                Some(ResponseFile {
                    file,
                    bytes: r.u64("bytes", RESPONSE_LIMIT)?,
                    sha256: r.sha256("sha256")?.to_string(),
                    complete: r.bool("complete")?,
                })
            }
            None => None,
        };
        let error = match b.obj_or_null("error")? {
            Some(e) => {
                e.exactly(&["type", "message", "request_id"])?;
                Some(ErrorFacts {
                    kind: opt_string(&e, "type")?,
                    message: opt_string(&e, "message")?,
                    request_id: opt_string(&e, "request_id")?,
                })
            }
            None => None,
        };
        let usage = match b.obj_or_null("usage")? {
            Some(u) => {
                u.exactly(&[
                    "input_tokens",
                    "cache_creation_input_tokens",
                    "cache_read_input_tokens",
                    "output_tokens",
                ])?;
                Some(ReportedUsage {
                    input_tokens: u.u64("input_tokens", NUM_MAX)?,
                    cache_creation_input_tokens: u.u64("cache_creation_input_tokens", NUM_MAX)?,
                    cache_read_input_tokens: u.u64("cache_read_input_tokens", NUM_MAX)?,
                    output_tokens: u.u64("output_tokens", NUM_MAX)?,
                })
            }
            None => None,
        };
        let then = b.one_of("then", &THEN)?.to_string();
        let delay_ms = b.u64_or_null("delay_ms", NUM_MAX)?;
        if (then == "retry") != delay_ms.is_some() {
            return Err(b.invalid("delay_ms", "a delay is recorded exactly when then is retry"));
        }
        Ok(ProviderAttempt {
            request,
            attempt,
            started_at: b.str("started_at")?.to_string(),
            ended_at: b.str("ended_at")?.to_string(),
            elapsed_ms: b.u64("elapsed_ms", NUM_MAX)?,
            timeout_seconds: b.u64("timeout_seconds", 600)?,
            request_written: b.one_of("request_written", &REQUEST_WRITTEN)?.to_string(),
            outcome: b.one_of("outcome", &ATTEMPT_OUTCOMES)?.to_string(),
            status: b.u64_or_null("status", 999)?,
            headers,
            response,
            error,
            stop_reason: opt_string(b, "stop_reason")?,
            model: opt_string(b, "model")?,
            usage,
            charged: Charge::decode(&b.obj("charged")?)?,
            problem: opt_string(b, "problem")?,
            then,
            delay_ms,
        })
    }
}

// ---------------------------------------------------------------------------
// `tool_result`.

/// The `tool_result` record of one executed (or replayed) `tool_use` block (4.5).
#[derive(Debug, Clone, PartialEq)]
pub struct ToolResult {
    /// The call number `c`; the capture is `call-<c>.json`.
    pub call: u64,
    /// The block is element `block` (from 0) of the `content` of
    /// `response-<request>-<attempt>.bin`.
    pub request: u64,
    pub attempt: u64,
    pub block: u64,
    pub call_bytes: u64,
    pub call_sha256: String,
    pub tool_use_id: String,
    /// The block's `name` when it is a string.
    pub tool: Option<String>,
    /// SHA-256 of the raw bytes of the block's `input` value, if it has one.
    pub input_sha256: Option<String>,
    /// The call whose recorded result this one redelivers (6.3).
    pub replay_of: Option<u64>,
    /// The reply envelope's outcome: `completed`, `refused` or `failed`.
    pub outcome: String,
    /// The envelope's reason; `None` exactly when completed.
    pub reason: Option<String>,
    /// The answer revision after the call.
    pub revision: u64,
    /// The `entry` or `seal` record the call published, `log/<n>.json`.
    pub log_record: Option<String>,
    /// True exactly when the outcome is not `completed`.
    pub is_error: bool,
    /// The exact bytes of the `content` array the `tool_result` block carries.
    pub content: Vec<u8>,
}

impl ToolResult {
    pub fn call_file(&self) -> String {
        call_name(self.call)
    }
    /// The `tool_result` block this record sends.
    pub fn block_bytes(&self) -> Vec<u8> {
        tool_result_block(&self.tool_use_id, &self.content, self.is_error)
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("call", self.call)
            .with("request", self.request)
            .with("attempt", self.attempt)
            .with("block", self.block)
            .with("call_file", self.call_file())
            .with("call_bytes", self.call_bytes)
            .with("call_sha256", self.call_sha256.as_str())
            .with("tool_use_id", self.tool_use_id.as_str())
            .with("tool", self.tool.as_deref())
            .with("input_sha256", self.input_sha256.as_deref())
            .with("replay_of", self.replay_of)
            .with("outcome", self.outcome.as_str())
            .with("reason", self.reason.as_deref())
            .with("revision", self.revision)
            .with("log_record", self.log_record.as_deref())
            .with("is_error", self.is_error)
            .with("content", J::Raw(self.content.clone()))
    }
    /// Decode strictly. `raw` is the whole record's bytes, from which the
    /// exact `content` bytes are taken.
    pub fn decode(b: &Obj, raw: &[u8]) -> Result<ToolResult, JsonError> {
        b.exactly(&[
            "call",
            "request",
            "attempt",
            "block",
            "call_file",
            "call_bytes",
            "call_sha256",
            "tool_use_id",
            "tool",
            "input_sha256",
            "replay_of",
            "outcome",
            "reason",
            "revision",
            "log_record",
            "is_error",
            "content",
        ])?;
        let call = b.u64("call", NUM_MAX)?;
        if b.str("call_file")? != call_name(call) {
            return Err(b.invalid("call_file", format!("expected {}", call_name(call))));
        }
        let outcome = b.one_of("outcome", &CALL_OUTCOMES)?.to_string();
        let reason = opt_string(b, "reason")?;
        if (outcome == "completed") == reason.is_some() {
            return Err(b.invalid(
                "reason",
                "a reason is recorded exactly when the call was not completed",
            ));
        }
        let is_error = b.bool("is_error")?;
        if is_error != (outcome != "completed") {
            return Err(b.invalid(
                "is_error",
                "is_error is true exactly when the outcome is not completed",
            ));
        }
        let log_record = opt_string(b, "log_record")?;
        if log_record
            .as_deref()
            .is_some_and(|s| crate::names::parse_log_name(s).is_none())
        {
            return Err(b.invalid("log_record", "expected a log record name, log/<n>.json"));
        }
        let content = b.req("content")?;
        let blocks = b.arr("content")?;
        if blocks.is_empty() {
            return Err(b.invalid(
                "content",
                "a tool result begins with the reply envelope's text block",
            ));
        }
        for (i, blk) in blocks.iter().enumerate() {
            let o = blk.obj(&format!("{}/{i}", b.ptr("content")))?;
            o.exactly(&["type", "text"])?;
            o.one_of("type", &["text"])?;
            o.str("text")?;
        }
        Ok(ToolResult {
            call,
            request: b.u64("request", NUM_MAX)?,
            attempt: b.u64("attempt", NUM_MAX)?,
            block: b.u64("block", NUM_MAX)?,
            call_bytes: b.u64("call_bytes", NUM_MAX)?,
            call_sha256: b.sha256("call_sha256")?.to_string(),
            tool_use_id: b.str("tool_use_id")?.to_string(),
            tool: opt_string(b, "tool")?,
            input_sha256: b.sha256_or_null("input_sha256")?.map(str::to_string),
            replay_of: b.u64_or_null("replay_of", NUM_MAX)?,
            outcome,
            reason,
            revision: b.u64("revision", NUM_MAX)?,
            log_record,
            is_error,
            content: raw[content.start..content.end].to_vec(),
        })
    }
}

// ---------------------------------------------------------------------------
// Reading.

/// Open `runs/<run>` for reading.
pub fn open(audit: &Audit, run: u64) -> io::Result<Dir> {
    audit.dir.open_dir("runs")?.open_dir(&run.to_string())
}

/// Read and decode one linked run record: its header must name this audit
/// and the expected kind. Returns the body object's owner and the raw bytes.
fn read_record(
    audit: &Audit,
    dir: &Dir,
    name: &str,
    kind: &str,
) -> Result<(json::Json, Vec<u8>), String> {
    let (bytes, _) = dir.read_regular(name, RECORD_LIMIT).map_err(|e| match e {
        ReadError::Missing => "missing".to_string(),
        other => format!("cannot be read: {}", other.describe()),
    })?;
    let r = decode_record(&bytes)?;
    if r.kind != kind {
        return Err(format!("has kind {:?}, not {kind}", r.kind));
    }
    if r.audit.as_deref() != Some(audit.id.as_str()) {
        return Err("names another audit".into());
    }
    Ok((r.json, bytes))
}

pub fn read_attempt(audit: &Audit, dir: &Dir, k: u64, a: u64) -> Result<ProviderAttempt, String> {
    let (v, _) = read_record(audit, dir, &attempt_name(k, a), "provider_attempt")?;
    let b = body(&v)?;
    let p = ProviderAttempt::decode(&b).map_err(|e| e.to_string())?;
    if (p.request, p.attempt) != (k, a) {
        return Err(format!("names request {} attempt {}", p.request, p.attempt));
    }
    Ok(p)
}

pub fn read_result(audit: &Audit, dir: &Dir, c: u64) -> Result<ToolResult, String> {
    let (v, raw) = read_record(audit, dir, &result_name(c), "tool_result")?;
    let b = body(&v)?;
    let t = ToolResult::decode(&b, &raw).map_err(|e| e.to_string())?;
    if t.call != c {
        return Err(format!("names call {}", t.call));
    }
    Ok(t)
}

fn body(v: &json::Json) -> Result<Obj<'_>, String> {
    v.obj("")
        .and_then(|o| o.obj("body"))
        .map_err(|e| e.to_string())
}

/// The names in a run directory, by kind.
#[derive(Debug, Default)]
pub struct Listing {
    /// Request numbers with a `request-<k>.json`.
    pub requests: Vec<u64>,
    /// `(k, a)` with a `response-<k>-<a>.bin`.
    pub responses: Vec<(u64, u64)>,
    /// `(k, a)` with an `attempt-<k>-<a>.json`.
    pub attempts: Vec<(u64, u64)>,
    /// Call numbers with a `call-<c>.json`.
    pub calls: Vec<u64>,
    /// Call numbers with a `result-<c>.json`.
    pub results: Vec<u64>,
    /// Any other name besides `stage`.
    pub other: Vec<String>,
}

fn two(s: &str) -> Option<(u64, u64)> {
    let (a, b) = s.split_once('-')?;
    Some((crate::names::parse_num(a)?, crate::names::parse_num(b)?))
}

pub fn list(dir: &Dir) -> io::Result<Listing> {
    let mut l = Listing::default();
    for n in dir.names()? {
        let num = |prefix: &str, suffix: &str| {
            n.strip_prefix(prefix)
                .and_then(|r| r.strip_suffix(suffix))
                .and_then(crate::names::parse_num)
        };
        let pair = |prefix: &str, suffix: &str| {
            n.strip_prefix(prefix)
                .and_then(|r| r.strip_suffix(suffix))
                .and_then(two)
        };
        if let Some(k) = num("request-", ".json") {
            l.requests.push(k);
        } else if let Some(x) = pair("response-", ".bin") {
            l.responses.push(x);
        } else if let Some(x) = pair("attempt-", ".json") {
            l.attempts.push(x);
        } else if let Some(c) = num("call-", ".json") {
            l.calls.push(c);
        } else if let Some(c) = num("result-", ".json") {
            l.results.push(c);
        } else if n != "stage" {
            l.other.push(n);
        }
    }
    l.requests.sort_unstable();
    l.responses.sort_unstable();
    l.attempts.sort_unstable();
    l.calls.sort_unstable();
    l.results.sort_unstable();
    Ok(l)
}

/// Stage files of a run directory that no run record shares: interrupted
/// publications, reported by status and never read as records.
pub fn unlinked_stage(dir: &Dir) -> Vec<String> {
    let Ok(stage) = dir.open_dir("stage") else {
        return Vec::new();
    };
    let Ok(names) = stage.names() else {
        return Vec::new();
    };
    let linked: Vec<(u64, u64)> = dir
        .names()
        .unwrap_or_default()
        .iter()
        .filter(|n| n.ends_with(".json") && (n.starts_with("attempt-") || n.starts_with("result-")))
        .filter_map(|n| dir.stat_at(n).ok().map(|s| s.id()))
        .collect();
    names
        .into_iter()
        .filter(|n| match stage.stat_at(n) {
            Ok(st) => !linked.contains(&st.id()),
            Err(_) => true,
        })
        .map(|n| format!("stage/{n}"))
        .collect()
}

/// What one request's records establish, for notice reports (6.4).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct RequestSeen {
    /// Its capture is complete.
    pub complete: bool,
    /// An attempt record of it has `request_written` other than `none`.
    pub written: bool,
    /// One of its attempt records could not be read.
    pub unreadable_attempt: bool,
}

/// A placement's run directory as the accounting of 6.4 reads it, for a
/// placement without `run_ended`: what reconciliation records in its
/// `run_ended` and what status adds to the recorded totals.
#[derive(Debug, Default)]
pub struct Account {
    /// Complete request captures.
    pub requests: u64,
    /// Attempt records.
    pub attempts: u64,
    /// The charges of the attempt records, plus one estimated attempt for
    /// each complete request capture whose latest attempt has no record.
    pub usage: Usage,
    /// The last readable attempt record in (request, attempt) order.
    pub last: Option<ProviderAttempt>,
    /// Requests that have a capture, by number.
    pub seen: BTreeMap<u64, RequestSeen>,
    /// Captures and records that could not be read, each with its problem.
    /// An unreadable attempt record is charged as an estimated attempt of
    /// its request, since its own charge cannot be known.
    pub problems: Vec<String>,
}

impl Account {
    /// A notice's `sent` value for its planned request (6.4): `sent` when an
    /// attempt record of it has `request_written` other than `none`;
    /// `not_sent` when the request was never captured, including a cut-off
    /// capture, whose request was never sent; else `unknown`.
    pub fn notice_sent(&self, request: u64) -> &'static str {
        match self.seen.get(&request) {
            Some(s) if s.written => "sent",
            Some(s) if s.complete => "unknown",
            _ => "not_sent",
        }
    }
}

/// The audit's cumulative usage (5.6, 6.4): every `run_ended` usage plus
/// the accounting of each placement that has none. The second value lists
/// what could not be read, so a caller can report the figure as uncertain.
pub fn cumulative_usage(audit: &Audit, state: &crate::log::LogState) -> (Usage, Vec<String>) {
    let mut used = state.recorded_usage();
    let mut problems = Vec::new();
    for p in state.placements().iter().filter(|p| p.ended.is_none()) {
        match account(audit, p.run) {
            Ok(a) => {
                used.add(&a.usage);
                problems.extend(a.problems);
            }
            Err(e) => problems.push(e),
        }
    }
    (used, problems)
}

/// Account a placement from its run directory (6.4).
pub fn account(audit: &Audit, run: u64) -> Result<Account, String> {
    let dir = open(audit, run)
        .map_err(|e| format!("{} cannot be opened: {}", dir_name(run), util::describe(&e)))?;
    let l = list(&dir)
        .map_err(|e| format!("{} cannot be listed: {}", dir_name(run), util::describe(&e)))?;
    let mut acc = Account {
        attempts: l.attempts.len() as u64,
        ..Account::default()
    };
    for &k in &l.requests {
        let name = request_name(k);
        let header = match read_request_capture(&dir, k) {
            Ok(c) => c,
            Err(e) => {
                acc.problems.push(format!(
                    "{}/{name} cannot be read: {}",
                    dir_name(run),
                    e.describe()
                ));
                RequestCapture::Unreadable
            }
        };
        let header = match header {
            RequestCapture::Complete(h) if h.request == k => Some(h),
            RequestCapture::CutOff => {
                acc.seen.insert(k, RequestSeen::default());
                continue;
            }
            _ => {
                acc.problems.push(format!(
                    "{}/{name} is not a request capture in Stewart's layout",
                    dir_name(run)
                ));
                None
            }
        };
        let mut seen = RequestSeen {
            complete: header.is_some(),
            ..RequestSeen::default()
        };
        let mut latest_recorded_then: Option<String> = None;
        for &(_, a) in l.attempts.iter().filter(|(kk, _)| *kk == k) {
            match read_attempt(audit, &dir, k, a) {
                Ok(p) => {
                    acc.usage.charge(&p.charged);
                    seen.written |= p.request_written != "none";
                    latest_recorded_then = Some(p.then.clone());
                    acc.last = Some(p);
                }
                Err(e) => {
                    acc.problems
                        .push(format!("{}/{}: {e}", dir_name(run), attempt_name(k, a)));
                    seen.unreadable_attempt = true;
                    latest_recorded_then = None;
                    if let Some(h) = &header {
                        acc.usage
                            .charge(&Charge::estimated(h.max_tokens, h.body_bytes));
                    }
                }
            }
        }
        if let Some(h) = &header {
            acc.requests += 1;
            // The latest attempt has no record when no attempt was recorded,
            // or the latest record planned another attempt.
            let unrecorded = match latest_recorded_then.as_deref() {
                None => !seen.unreadable_attempt,
                Some(t) => t == "retry",
            };
            if unrecorded {
                acc.usage
                    .charge(&Charge::estimated(h.max_tokens, h.body_bytes));
            }
        }
        acc.seen.insert(k, seen);
    }
    Ok(acc)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::usage::Basis;

    fn attempt(k: u64, a: u64, outcome: &str, then: &str) -> ProviderAttempt {
        ProviderAttempt {
            request: k,
            attempt: a,
            started_at: "2026-11-02T14:03:11.402Z".into(),
            ended_at: "2026-11-02T14:03:12.214Z".into(),
            elapsed_ms: 812,
            timeout_seconds: 600,
            request_written: "complete".into(),
            outcome: outcome.into(),
            status: Some(529),
            headers: Headers {
                content_type: vec!["application/json".into()],
                request_id: vec!["req_011".into()],
                retry_after: vec!["0".into()],
            },
            response: Some(ResponseFile {
                file: response_name(k, a),
                bytes: 105,
                sha256: "a".repeat(64),
                complete: true,
            }),
            error: Some(ErrorFacts {
                kind: Some("overloaded_error".into()),
                message: Some("Overloaded".into()),
                request_id: Some("req_011".into()),
            }),
            stop_reason: None,
            model: None,
            usage: None,
            charged: Charge::NONE,
            problem: None,
            then: then.into(),
            delay_ms: (then == "retry").then_some(0),
        }
    }

    #[test]
    fn request_bodies_and_captures_splice_pinned_bytes() {
        let m1 = br#"{"role":"user","content":[{"type":"text","text":"Q"}]}"#;
        let m2 = br#"{"role":"assistant","content":[{"type":"text","text":"A"}]}"#;
        let body = request_body(
            br#""claude-opus-5-5""#,
            16000,
            br#"[{"type":"text","text":"S"}]"#,
            b"[]",
            &[],
            &[m1, m2],
        );
        assert_eq!(
            body,
            br#"{"model":"claude-opus-5-5","max_tokens":16000,"system":[{"type":"text","text":"S"}],"tools":[],"messages":[{"role":"user","content":[{"type":"text","text":"Q"}]},{"role":"assistant","content":[{"type":"text","text":"A"}]}]}"#
        );
        let with_extra = request_body(b"\"m\"", 1, b"[]", b"[]", &[br#""x":1"#], &[]);
        assert_eq!(
            with_extra,
            br#"{"model":"m","max_tokens":1,"system":[],"tools":[],"x":1,"messages":[]}"#
        );
        let cap = request_capture(2, 16000, &body, &[m2]);
        let want = format!(
            r#"{{"request":2,"max_tokens":16000,"body_bytes":{},"body_sha256":"{}","appended":[{}]}}"#,
            body.len(),
            util::sha256_hex(&body),
            String::from_utf8_lossy(m2)
        ) + "\n";
        assert_eq!(cap, want.as_bytes());
        assert_eq!(
            parse_request_capture(&cap),
            RequestCapture::Complete(RequestHeader {
                request: 2,
                max_tokens: 16000,
                body_bytes: body.len() as u64,
                body_sha256: util::sha256_hex(&body),
            })
        );
        assert_eq!(
            parse_request_capture(&cap[..cap.len() - 1]),
            RequestCapture::CutOff
        );
        assert_eq!(parse_request_capture(&cap[..40]), RequestCapture::CutOff);
        assert_eq!(
            parse_request_capture(b"{\"request\":x]}\n"),
            RequestCapture::Unreadable
        );
        let (p, audit) = crate::log::tests::scratch_audit();
        let rd = RunDir::create(&audit, 1).unwrap();
        let long = vec![b'z'; 5000];
        let big = request_capture(1, 16000, &long, &[&long]);
        rd.write_request(1, &big).unwrap();
        rd.write_request(2, &big[..big.len() - 2]).unwrap();
        let dir = open(&audit, 1).unwrap();
        assert_eq!(
            read_request_capture(&dir, 1).unwrap(),
            parse_request_capture(&big)
        );
        assert_eq!(
            read_request_capture(&dir, 2).unwrap(),
            RequestCapture::CutOff
        );
        std::fs::remove_dir_all(p).unwrap();
        assert_eq!(
            tool_result_block("toolu_\"1", br#"[{"type":"text","text":"{}"}]"#, true),
            br#"{"type":"tool_result","tool_use_id":"toolu_\"1","content":[{"type":"text","text":"{}"}],"is_error":true}"#
        );
    }

    #[test]
    fn header_values_and_messages_are_recorded_as_specified() {
        assert_eq!(header_value(b" \tapplication/json\t "), "application/json");
        assert_eq!(header_value(b"a\xffb\x7f%"), "a%FFb%7F%");
        assert_eq!(header_value(b"   "), "");
        assert_eq!(cut("aé", 2), "a");
        assert_eq!(cut("aé", 3), "aé");
    }

    #[test]
    fn records_publish_in_sequence_and_decode_strictly() {
        let (p, audit) = crate::log::tests::scratch_audit();
        let rd = RunDir::create(&audit, 1).unwrap();
        assert!(
            RunDir::create(&audit, 1).is_err(),
            "runs/<n> is never adopted"
        );
        let req = request_capture(1, 16000, b"{}", &[b"{}"]);
        rd.write_request(1, &req).unwrap();
        assert!(
            rd.write_request(1, &req).is_err(),
            "a taken name is a failure"
        );
        let a1 = attempt(1, 1, "http_error", "retry");
        rd.publish(&audit, "provider_attempt", &attempt_name(1, 1), a1.to_j())
            .unwrap();
        assert!(
            rd.publish(&audit, "provider_attempt", &attempt_name(1, 1), a1.to_j())
                .is_err()
        );
        let dir = open(&audit, 1).unwrap();
        assert_eq!(read_attempt(&audit, &dir, 1, 1).unwrap(), a1);
        // The second (failed) publication's stage file is an interrupted publication.
        assert_eq!(unlinked_stage(&dir).len(), 1);

        let content = br#"[{"type":"text","text":"{\"schema\":\"stewart.reply/1\"}"}]"#.to_vec();
        let t = ToolResult {
            call: 1,
            request: 1,
            attempt: 2,
            block: 0,
            call_bytes: 10,
            call_sha256: "b".repeat(64),
            tool_use_id: "toolu_01A".into(),
            tool: Some("list".into()),
            input_sha256: Some("c".repeat(64)),
            replay_of: None,
            outcome: "completed".into(),
            reason: None,
            revision: 0,
            log_record: None,
            is_error: false,
            content: content.clone(),
        };
        rd.write_call(1, b"{\"type\":\"tool_use\"}").unwrap();
        rd.publish(&audit, "tool_result", &result_name(1), t.to_j())
            .unwrap();
        let back = read_result(&audit, &dir, 1).unwrap();
        assert_eq!(back, t);
        assert_eq!(back.content, content, "content keeps its exact bytes");
        let l = list(&dir).unwrap();
        assert_eq!(
            (l.requests, l.attempts, l.calls, l.results),
            (vec![1], vec![(1, 1)], vec![1], vec![1])
        );
        std::fs::remove_dir_all(p).unwrap();
    }

    #[test]
    fn an_open_placement_is_accounted_from_its_records_and_captures() {
        let (p, audit) = crate::log::tests::scratch_audit();
        let rd = RunDir::create(&audit, 1).unwrap();
        // Request 1: one used response, reported.
        let body1 = vec![b'x'; 30];
        rd.write_request(1, &request_capture(1, 16000, &body1, &[b"{}"]))
            .unwrap();
        let mut used = attempt(1, 1, "response", "use");
        used.charged = Charge::reported(100, 0, 20, 7);
        rd.publish(&audit, "provider_attempt", &attempt_name(1, 1), used.to_j())
            .unwrap();
        // Request 2: a retry was planned and its next attempt never recorded.
        let body2 = vec![b'y'; 31];
        rd.write_request(2, &request_capture(2, 5000, &body2, &[b"{}"]))
            .unwrap();
        rd.publish(
            &audit,
            "provider_attempt",
            &attempt_name(2, 1),
            attempt(2, 1, "http_error", "retry").to_j(),
        )
        .unwrap();
        // Request 3: cut off, so never sent and never charged.
        rd.write_request(3, b"{\"request\":3,\"max_tok").unwrap();
        let acc = account(&audit, 1).unwrap();
        assert_eq!(acc.requests, 2);
        assert_eq!(acc.attempts, 2);
        assert_eq!(acc.usage.turns.reported, 1);
        assert_eq!(acc.usage.turns.estimated, 1);
        assert_eq!(acc.usage.input_tokens.reported, 120);
        assert_eq!(acc.usage.input_tokens.estimated, 11, "ceil(31 / 3)");
        assert_eq!(acc.usage.output_tokens.estimated, 5000);
        assert_eq!(
            acc.last.as_ref().map(|a| (a.request, a.attempt)),
            Some((2, 1))
        );
        assert_eq!(acc.notice_sent(1), "sent");
        assert_eq!(acc.notice_sent(3), "not_sent");
        assert_eq!(acc.notice_sent(4), "not_sent");
        assert!(acc.problems.is_empty(), "{:?}", acc.problems);
        let _ = Basis::None;
        std::fs::remove_dir_all(p).unwrap();
    }
}
