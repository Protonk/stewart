//! Offline transport prototype, not a service adapter. Never starts Claude.
//! Reuses the existing scanners without modifying the service or its contracts.
#![allow(dead_code)]

use stewart::json;
#[path = "../../service/src/provider/tolerant.rs"]
mod wire;

use json::J;
use std::collections::HashSet;
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::fd::FromRawFd;
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::sync::{
    Arc,
    atomic::{AtomicU8, Ordering},
};
use wire::{Kind, Span};

const VERSION: &str = "2025-11-25";
const FRAME_LIMIT: usize = 8 * 1024 * 1024;
const ARGUMENT_LIMIT: usize = 4 * 1024 * 1024;

fn object(b: &[u8], s: Span) -> Result<Vec<(Option<String>, Span)>, String> {
    if wire::kind(b, s) != Kind::Object {
        return Err("expected object".into());
    }
    wire::members(b, s)
}

fn field(ms: &[(Option<String>, Span)], key: &str) -> Result<Option<Span>, String> {
    match wire::once(ms, key) {
        wire::Member::Present(s) => Ok(Some(s)),
        wire::Member::Missing => Ok(None),
        _ => Err(format!("repeated {key}")),
    }
}

fn required(ms: &[(Option<String>, Span)], key: &str) -> Result<Span, String> {
    field(ms, key)?.ok_or_else(|| format!("missing {key}"))
}

fn string(b: &[u8], s: Span) -> Result<String, String> {
    if wire::kind(b, s) != Kind::String {
        return Err("expected string".into());
    }
    wire::decode_string(s.of(b)).ok_or_else(|| "invalid Unicode string".into())
}

// Keep the ID's original bytes for the response and a typed identity for reuse
// detection. Numeric IDs use integer notation; -0 and 0 have the same identity.
fn id_key(b: &[u8], s: Span) -> Result<String, String> {
    if wire::kind(b, s) == Kind::String {
        return Ok(format!("s:{}", string(b, s)?));
    }
    let raw = s.of(b);
    let digits = raw.strip_prefix(b"-").unwrap_or(raw);
    if digits.is_empty() || !digits.iter().all(u8::is_ascii_digit) {
        return Err("request ID must be a string or integer".into());
    }
    Ok(format!(
        "n:{}",
        if raw == b"-0" {
            "0"
        } else {
            std::str::from_utf8(raw).unwrap()
        }
    ))
}

fn result(id: &[u8], value: J) -> J {
    J::obj()
        .with("jsonrpc", "2.0")
        .with("id", J::Raw(id.to_vec()))
        .with("result", value)
}

fn error(id: &[u8], code: i32, message: &str) -> J {
    J::obj()
        .with("jsonrpc", "2.0")
        .with("id", J::Raw(id.to_vec()))
        .with(
            "error",
            J::obj()
                .with("code", J::Raw(code.to_string().into_bytes()))
                .with("message", message),
        )
}

fn tool_result(id: &[u8], text: &str, failed: bool) -> J {
    result(
        id,
        J::obj()
            .with(
                "content",
                J::Arr(vec![J::obj().with("type", "text").with("text", text)]),
            )
            .with("isError", failed),
    )
}

#[derive(Debug)]
struct Ticket {
    id: Vec<u8>,
    key: String,
    arguments: Vec<u8>,
}

enum Action {
    Silent,
    Reply(J),
    Tool(Ticket),
}

#[derive(Default)]
struct Session {
    initialized: bool,
    ready: bool,
    ended: bool,
    ids: HashSet<String>,
    pending: HashSet<String>,
    cancelled: HashSet<String>,
}

impl Session {
    fn receive(&mut self, raw: &[u8]) -> Action {
        let top = match wire::validate(raw) {
            Ok(v) => v,
            Err(_) => return Action::Reply(error(b"null", -32700, "invalid JSON")),
        };
        let ms = match object(raw, top) {
            Ok(v) => v,
            Err(_) => return Action::Reply(error(b"null", -32600, "expected one request object")),
        };
        let id = match field(&ms, "id") {
            Ok(v) => v,
            Err(_) => return Action::Reply(error(b"null", -32600, "ambiguous request ID")),
        };
        let method = required(&ms, "method").and_then(|s| string(raw, s));
        let version = required(&ms, "jsonrpc").and_then(|s| string(raw, s));
        if version.as_deref() != Ok("2.0")
            || method.is_err()
            || !matches!(field(&ms, "result"), Ok(None))
            || !matches!(field(&ms, "error"), Ok(None))
        {
            return if id.is_none() {
                Action::Silent
            } else {
                Action::Reply(error(b"null", -32600, "invalid request envelope"))
            };
        }
        let method = method.unwrap();
        let params = field(&ms, "params")
            .and_then(|p| p.map(|s| object(raw, s)).transpose())
            .map(|p| p.unwrap_or_default());
        let Some(id) = id else {
            if let Ok(params) = params {
                match method.as_str() {
                    "notifications/initialized" if self.initialized => self.ready = true,
                    "notifications/cancelled" => {
                        if let Ok(key) = required(&params, "requestId").and_then(|s| id_key(raw, s))
                        {
                            if self.pending.contains(&key) {
                                self.cancelled.insert(key);
                            }
                        }
                    }
                    _ => (), // Notifications never acquire a response or execute tools.
                }
            }
            return Action::Silent;
        };
        let key = match id_key(raw, id) {
            Ok(key) => key,
            Err(e) => return Action::Reply(error(b"null", -32600, &e)),
        };
        if self.ids.len() >= 4096 {
            return Action::Reply(error(id.of(raw), -32000, "prototype request limit"));
        }
        if !self.ids.insert(key.clone()) {
            return Action::Reply(error(
                id.of(raw),
                -32600,
                "request ID already used in this session",
            ));
        }
        let params = match params {
            Ok(v) => v,
            Err(e) => return Action::Reply(error(id.of(raw), -32602, &e)),
        };
        let response = match method.as_str() {
            "ping" => result(id.of(raw), J::obj()),
            "initialize" => {
                let valid = required(&params, "protocolVersion")
                    .and_then(|s| string(raw, s))
                    .is_ok()
                    && required(&params, "capabilities")
                        .and_then(|s| object(raw, s))
                        .is_ok()
                    && required(&params, "clientInfo")
                        .and_then(|s| object(raw, s))
                        .is_ok_and(|info| {
                            ["name", "version"]
                                .iter()
                                .all(|k| required(&info, k).and_then(|s| string(raw, s)).is_ok())
                        });
                if self.initialized || !valid {
                    error(id.of(raw), -32602, "invalid or repeated initialization")
                } else {
                    self.initialized = true;
                    result(
                        id.of(raw),
                        J::obj()
                            .with("protocolVersion", VERSION)
                            .with("capabilities", J::obj().with("tools", J::obj()))
                            .with(
                                "serverInfo",
                                J::obj()
                                    .with("name", "stewart-offline-check")
                                    .with("version", "1"),
                            ),
                    )
                }
            }
            "tools/list" | "tools/call" if !self.ready => error(
                id.of(raw),
                -32000,
                "initialize and notify initialized first",
            ),
            "tools/list" => {
                if !matches!(field(&params, "cursor"), Ok(None)) {
                    error(id.of(raw), -32602, "this fixed list has no next cursor")
                } else {
                    result(
                        id.of(raw),
                        J::obj().with(
                            "tools",
                            J::Arr(vec![
                                J::obj()
                                    .with("name", "record_note")
                                    .with("description", "Record a synthetic note.")
                                    .with(
                                        "inputSchema",
                                        J::obj()
                                            .with("type", "object")
                                            .with(
                                                "properties",
                                                J::obj()
                                                    .with("text", J::obj().with("type", "string")),
                                            )
                                            .with("required", J::Arr(vec![J::from("text")]))
                                            .with("additionalProperties", false),
                                    ),
                            ]),
                        ),
                    )
                }
            }
            "tools/call" => {
                if !matches!(field(&params, "task"), Ok(None)) {
                    return Action::Reply(error(id.of(raw), -32602, "tasks are not supported"));
                }
                if required(&params, "name")
                    .and_then(|s| string(raw, s))
                    .as_deref()
                    != Ok("record_note")
                {
                    return Action::Reply(error(id.of(raw), -32602, "unknown tool"));
                }
                let args = match field(&params, "arguments") {
                    Ok(None) => b"{}".as_slice(),
                    Ok(Some(s)) if wire::kind(raw, s) == Kind::Object => s.of(raw),
                    _ => {
                        return Action::Reply(error(
                            id.of(raw),
                            -32602,
                            "arguments must be one object",
                        ));
                    }
                };
                let valid = args.len() <= ARGUMENT_LIMIT
                    && json::parse(args).is_ok_and(|j| {
                        j.obj("")
                            .is_ok_and(|o| o.exactly(&["text"]).is_ok() && o.str("text").is_ok())
                    });
                if !valid {
                    tool_result(
                        id.of(raw),
                        "input_invalid: expected exactly one text string",
                        true,
                    )
                } else {
                    self.pending.insert(key.clone());
                    return Action::Tool(Ticket {
                        id: id.of(raw).to_vec(),
                        key,
                        arguments: args.to_vec(),
                    });
                }
            }
            _ => error(id.of(raw), -32601, "method not found"),
        };
        Action::Reply(response)
    }

    // Models the publication check. The real service must perform its own
    // durable log-slot check; this state machine is not that evidence.
    fn finish(
        &mut self,
        ticket: Ticket,
        publish: impl FnOnce(&[u8]) -> io::Result<()>,
    ) -> io::Result<Option<J>> {
        self.pending.remove(&ticket.key);
        if self.cancelled.remove(&ticket.key) {
            return Ok(None);
        }
        if self.ended {
            return Ok(Some(tool_result(&ticket.id, "authoring_ended", true)));
        }
        publish(&ticket.arguments)?;
        Ok(Some(tool_result(&ticket.id, "recorded", false)))
    }
}

fn exclusive(path: &Path) -> io::Result<File> {
    OpenOptions::new().write(true).create_new(true).open(path)
}

fn retain(file: &mut File, bytes: &[u8]) -> io::Result<()> {
    file.write_all(bytes)?;
    file.sync_all()
}

// Capture each received chunk before looking for a frame or decoding it. A
// truncated/oversized frame stays in incoming.bin, including its exact suffix.
fn serve(root: &Path) -> io::Result<()> {
    let mut incoming = exclusive(&root.join("incoming.bin"))?;
    let mut outgoing = exclusive(&root.join("outgoing.bin"))?;
    let mut effects = exclusive(&root.join("effects.jsonl"))?;
    let mut session = Session::default();
    let mut buffered = Vec::new();
    let mut chunk = [0; 4096];
    let mut input = io::stdin().lock();
    let mut output = io::stdout().lock();
    loop {
        let n = input.read(&mut chunk)?;
        if n == 0 {
            return if buffered.is_empty() {
                Ok(())
            } else {
                Err(io::Error::other("truncated MCP frame retained"))
            };
        }
        retain(&mut incoming, &chunk[..n])?;
        for &byte in &chunk[..n] {
            buffered.push(byte);
            if buffered.len() > FRAME_LIMIT {
                return Err(io::Error::other(
                    "MCP frame exceeds prototype bound; received bytes retained",
                ));
            }
            if byte != b'\n' {
                continue;
            }
            let reply = match session.receive(&buffered) {
                Action::Silent => None,
                Action::Reply(j) => Some(j),
                Action::Tool(t) => session.finish(t, |args| {
                    let mut line = args.to_vec();
                    line.push(b'\n');
                    retain(&mut effects, &line)
                })?,
            };
            if let Some(j) = reply {
                let mut bytes = j.bytes();
                bytes.push(b'\n');
                retain(&mut outgoing, &bytes)?;
                output.write_all(&bytes)?;
                output.flush()?;
            }
            buffered.clear();
        }
    }
}

// Pure duplex byte forwarding. Never parse, open an archive, synthesize a reply
// or reconnect. An inherited socket isolates this check from rendezvous policy.
fn relay(fd: i32) -> io::Result<()> {
    // The checker passes an owned, inherited socket descriptor, never a secret.
    let mut peer = unsafe { UnixStream::from_raw_fd(fd) };
    let mut writer = peer.try_clone()?;
    let input_state = Arc::new(AtomicU8::new(0));
    let state = Arc::clone(&input_state);
    std::thread::spawn(move || {
        if io::copy(&mut io::stdin().lock(), &mut writer).is_err() {
            state.store(2, Ordering::SeqCst);
            let _ = writer.shutdown(std::net::Shutdown::Both);
        } else {
            state.store(1, Ordering::SeqCst);
            let _ = writer.shutdown(std::net::Shutdown::Write);
        }
    });
    let result = io::copy(&mut peer, &mut io::stdout().lock()).map(|_| ());
    let _ = peer.shutdown(std::net::Shutdown::Both);
    // Main exits even if stdin remains open after the owner has gone.
    result?;
    if input_state.load(Ordering::SeqCst) == 1 {
        Ok(())
    } else {
        Err(io::Error::other(
            "owner closed before relay input completed; no reconnect",
        ))
    }
}

fn main() -> io::Result<()> {
    let args: Vec<_> = std::env::args_os().collect();
    match args.get(1).and_then(|s| s.to_str()) {
        Some("serve") if args.len() == 3 => serve(Path::new(&args[2])),
        Some("relay") if args.len() == 3 => relay(
            args[2]
                .to_str()
                .and_then(|s| s.parse::<i32>().ok())
                .filter(|fd| *fd > 2)
                .ok_or_else(|| {
                    io::Error::other("relay needs an inherited socket descriptor greater than 2")
                })?,
        ),
        _ => Err(io::Error::other(
            "offline check only: serve CAPTURE_DIRECTORY | relay INHERITED_SOCKET_FD",
        )),
    }
}

#[cfg(test)]
mod controls {
    use super::*;

    fn ready() -> Session {
        let mut s = Session::default();
        assert!(matches!(s.receive(br#"{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}"#), Action::Reply(_)));
        assert!(matches!(
            s.receive(br#"{"jsonrpc":"2.0","method":"notifications/initialized"}"#),
            Action::Silent
        ));
        s
    }

    fn ticket(s: &mut Session) -> Ticket {
        match s.receive(br#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"record_note","arguments":{ "text" : "orch\u0061rd" },"_meta":{"progressToken":-1,"unknown":1.5}}}"#) {
            Action::Tool(t) => t,
            _ => panic!("expected pending tool"),
        }
    }

    #[test]
    fn publication_positive_close_and_invariance() {
        for (index, close) in [false, true, false].into_iter().enumerate() {
            let mut s = ready();
            if index == 2 {
                // An unrelated notification must not change publication.
                assert!(matches!(s.receive(br#"{"jsonrpc":"2.0","method":"notifications/unrelated","params":{"value":1.5}}"#), Action::Silent));
            }
            let t = ticket(&mut s);
            s.ended = close;
            let mut effects = Vec::new();
            let reply = s
                .finish(t, |a| {
                    effects.push(a.to_vec());
                    Ok(())
                })
                .unwrap()
                .unwrap();
            assert_eq!(effects.len(), usize::from(!close));
            assert_eq!(reply.string().contains("authoring_ended"), close);
            if !close {
                assert_eq!(effects[0], br#"{ "text" : "orch\u0061rd" }"#);
            }
        }
    }

    #[test]
    fn cancellation_of_pending_call_is_silent_and_blocks_publication() {
        let mut s = ready();
        let t = ticket(&mut s);
        assert!(matches!(
            s.receive(
                br#"{"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":1}}"#
            ),
            Action::Silent
        ));
        assert!(
            s.finish(t, |_| panic!("cancelled call must not publish"))
                .unwrap()
                .is_none()
        );
        // Late and unknown cancellation are harmless, never rollback.
        assert!(matches!(s.receive(br#"{"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":999}}"#), Action::Silent));
    }

    #[test]
    fn failed_publication_keeps_failure() {
        let mut s = ready();
        let t = ticket(&mut s);
        let failure = s
            .finish(t, |_| Err(io::Error::other("synthetic storage failure")))
            .unwrap_err();
        assert_eq!(failure.to_string(), "synthetic storage failure");
    }
}
