//! HTTP/1.1 framing for one provider attempt (INTERFACE 6.1, 4.5).
//!
//! The request is a fixed head (no header beyond the six 6.1 names) and the
//! body. The response is read to its end by `content-length`, chunked transfer
//! coding or the connection closing, and its body is kept exactly as received
//! after removing chunked transfer coding and nothing else, up to 32 MiB.
//! Interim 1xx responses are skipped. Only `content-type`, `request-id` and
//! `retry-after` are recorded; the framing headers are read and not recorded.
//!
//! Reading and writing go through a [`Gate`], which the transport uses to
//! enforce the request deadline and the stop path between system calls.

use std::io::{self, Read, Write};

use crate::provider::StopCause;
use crate::provider::url::Endpoint;
use crate::runs::{self, Headers};

/// Most body bytes captured and decoded (Appendix B): `runs::RESPONSE_LIMIT`.
pub const BODY_LIMIT: usize = runs::RESPONSE_LIMIT as usize;
/// Most bytes of a response head (status line and header lines). A longer
/// head is malformed; nothing in 6.1 needs more.
pub const HEAD_LIMIT: usize = 256 * 1024;
/// Most bytes of one chunk-size line.
const CHUNK_LINE_LIMIT: usize = 4096;

/// The request head: exactly the 6.1 lines, lower-case names, CRLF endings.
/// `api_key` and `anthropic_version` must be visible ASCII; the caller checks.
pub fn request_head(
    endpoint: &Endpoint,
    api_key: &str,
    anthropic_version: &str,
    body_len: usize,
) -> Vec<u8> {
    format!(
        "POST {target} HTTP/1.1\r\nhost: {host}\r\nx-api-key: {api_key}\r\nanthropic-version: {anthropic_version}\r\nanthropic-beta: {beta}\r\ncontent-type: application/json\r\ncontent-length: {body_len}\r\nconnection: close\r\n\r\n",
        beta = crate::forms::ANTHROPIC_BETA,
        target = endpoint.target(),
        host = endpoint.host_header(),
    )
    .into_bytes()
}

/// How the body ended.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BodyEnd {
    /// The framing said the body was complete.
    Complete,
    /// The connection ended, failed or was stopped before the framing completed.
    CutOff,
    /// The body exceeded 32 MiB; the first 32 MiB were kept and reading stopped.
    TooLarge,
    /// The framing could not be followed (a bad chunk, conflicting lengths, an
    /// oversized head); the bytes before the defect were kept.
    Malformed(String),
}

/// A response whose status line was received.
#[derive(Debug, Clone, PartialEq)]
pub struct Reply {
    pub status: u16,
    /// `content-type`, `request-id` and `retry-after` from the final head,
    /// matched without regard to case, each value as `runs::header_value`
    /// records it, in order.
    pub headers: Headers,
    /// Why the body's codings make it undecodable: a `content-encoding` other
    /// than `identity`, or a transfer coding other than `chunked`.
    pub coding: Option<String>,
    /// The body as received after removing chunked transfer coding.
    pub body: Vec<u8>,
    pub end: BodyEnd,
}

impl Reply {
    /// The attempt record's `response.complete`.
    pub fn complete(&self) -> bool {
        self.end == BodyEnd::Complete
    }
}

/// Why reading or writing stopped before its natural end.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum Stop {
    /// The peer ended the stream.
    Eof,
    /// The connection failed, with a description.
    Broken(String),
    /// The request deadline passed.
    Timeout,
    /// The stop path shut the connection down.
    Aborted(StopCause),
}

/// The checks between system calls: the deadline and the stop path.
pub(crate) trait Gate {
    /// Before each read or write: refuse when aborted or past the deadline,
    /// and arm the socket timeout with the time remaining.
    fn before(&self) -> Result<(), Stop>;
    /// After an I/O error: `None` to repeat the call (an interrupted call, or
    /// a socket timeout that fired before the deadline).
    fn after_err(&self, e: &io::Error) -> Option<Stop>;
    /// After the peer ended the stream.
    fn after_eof(&self) -> Stop;
}

/// A gate without deadline or stop path, for in-memory streams.
#[cfg(test)]
pub(crate) struct Ungated;

#[cfg(test)]
impl Gate for Ungated {
    fn before(&self) -> Result<(), Stop> {
        Ok(())
    }
    fn after_err(&self, e: &io::Error) -> Option<Stop> {
        match e.kind() {
            io::ErrorKind::Interrupted => None,
            io::ErrorKind::UnexpectedEof => Some(Stop::Eof),
            _ => Some(Stop::Broken(e.to_string())),
        }
    }
    fn after_eof(&self) -> Stop {
        Stop::Eof
    }
}

/// Write all of `data`, adding each accepted byte to `written`.
pub(crate) fn write_counted<W: Write + ?Sized>(
    w: &mut W,
    gate: &dyn Gate,
    data: &[u8],
    written: &mut usize,
) -> Result<(), Stop> {
    let mut off = 0;
    while off < data.len() {
        gate.before()?;
        match w.write(&data[off..]) {
            Ok(0) => {
                return Err(Stop::Broken("the connection accepted no more bytes".into()));
            }
            Ok(n) => {
                off += n;
                *written += n;
            }
            Err(e) => {
                if let Some(s) = gate.after_err(&e) {
                    return Err(s);
                }
            }
        }
    }
    Ok(())
}

/// Flush buffered bytes (a TLS layer may hold the last records).
pub(crate) fn flush<W: Write + ?Sized>(w: &mut W, gate: &dyn Gate) -> Result<(), Stop> {
    loop {
        gate.before()?;
        match w.flush() {
            Ok(()) => return Ok(()),
            Err(e) => {
                if let Some(s) = gate.after_err(&e) {
                    return Err(s);
                }
            }
        }
    }
}

/// Buffered reading through a gate.
pub(crate) struct Wire<'a, R: Read + ?Sized> {
    r: &'a mut R,
    gate: &'a dyn Gate,
    buf: Vec<u8>,
    pos: usize,
}

impl<'a, R: Read + ?Sized> Wire<'a, R> {
    pub(crate) fn new(r: &'a mut R, gate: &'a dyn Gate) -> Self {
        Wire {
            r,
            gate,
            buf: Vec::new(),
            pos: 0,
        }
    }

    fn avail(&self) -> &[u8] {
        &self.buf[self.pos..]
    }

    /// Read more bytes into the buffer: at least one, or a stop.
    fn fill(&mut self) -> Result<(), Stop> {
        if self.pos > 0 {
            self.buf.drain(..self.pos);
            self.pos = 0;
        }
        let mut tmp = [0u8; 16 * 1024];
        loop {
            self.gate.before()?;
            match self.r.read(&mut tmp) {
                Ok(0) => return Err(self.gate.after_eof()),
                Ok(n) => {
                    self.buf.extend_from_slice(&tmp[..n]);
                    return Ok(());
                }
                Err(e) => {
                    if let Some(s) = self.gate.after_err(&e) {
                        return Err(s);
                    }
                }
            }
        }
    }

    /// One line without its LF (and a CR before it), charged to `budget`.
    fn line(&mut self, budget: &mut usize, what: &str) -> Result<Vec<u8>, LineErr> {
        loop {
            if let Some(nl) = self.avail().iter().position(|c| *c == b'\n') {
                if nl + 1 > *budget {
                    return Err(LineErr::TooLong(format!("{what} is longer than allowed")));
                }
                *budget -= nl + 1;
                let mut line = self.avail()[..nl].to_vec();
                if line.last() == Some(&b'\r') {
                    line.pop();
                }
                self.pos += nl + 1;
                return Ok(line);
            }
            if self.avail().len() > *budget {
                return Err(LineErr::TooLong(format!("{what} is longer than allowed")));
            }
            self.fill().map_err(LineErr::Stop)?;
        }
    }

    /// Append up to `n` bytes to `out`.
    fn take(&mut self, mut n: usize, out: &mut Vec<u8>) -> Result<(), Stop> {
        while n > 0 {
            if self.avail().is_empty() {
                self.fill()?;
            }
            let k = n.min(self.avail().len());
            out.extend_from_slice(&self.buf[self.pos..self.pos + k]);
            self.pos += k;
            n -= k;
        }
        Ok(())
    }
}

enum LineErr {
    Stop(Stop),
    TooLong(String),
}

/// Read one response. Returns the reply when a status line was received, and
/// the stop when reading ended before the framing completed (`None` when the
/// response was read to its end, or when reading stopped by choice at the
/// body limit or a framing defect, which the reply's `end` states).
pub(crate) fn read_response<R: Read + ?Sized>(
    r: &mut R,
    gate: &dyn Gate,
    body_limit: usize,
) -> (Option<Reply>, Option<Stop>) {
    let mut w = Wire::new(r, gate);
    let mut budget = HEAD_LIMIT;
    loop {
        let status = match w.line(&mut budget, "the status line") {
            Ok(line) => match parse_status(&line) {
                Some(s) => s,
                None => {
                    return (
                        None,
                        Some(Stop::Broken(
                            "the reply does not begin with an HTTP/1.x status line".into(),
                        )),
                    );
                }
            },
            Err(LineErr::Stop(Stop::Eof)) => {
                return (
                    None,
                    Some(Stop::Broken(
                        "the connection closed before a status line".into(),
                    )),
                );
            }
            Err(LineErr::Stop(s)) => return (None, Some(s)),
            Err(LineErr::TooLong(_)) => {
                return (
                    None,
                    Some(Stop::Broken(
                        "the reply's first line is not an HTTP/1.x status line".into(),
                    )),
                );
            }
        };
        let mut reply = Reply {
            status,
            headers: Headers::default(),
            coding: None,
            body: Vec::new(),
            end: BodyEnd::Complete,
        };
        let mut fields: Vec<(String, Vec<u8>)> = Vec::new();
        loop {
            match w.line(&mut budget, "the response head") {
                Ok(line) if line.is_empty() => break,
                Ok(line) => {
                    if line[0] == b' ' || line[0] == b'\t' {
                        // A folded continuation line joins the previous value.
                        if let Some((_, v)) = fields.last_mut() {
                            let start = line
                                .iter()
                                .position(|c| *c != b' ' && *c != b'\t')
                                .unwrap_or(line.len());
                            v.push(b' ');
                            v.extend_from_slice(&line[start..]);
                        }
                        continue;
                    }
                    if let Some(colon) = line.iter().position(|c| *c == b':') {
                        let name = &line[..colon];
                        if !name.is_empty() && name.iter().all(|c| is_tchar(*c)) {
                            let name = String::from_utf8_lossy(name).to_ascii_lowercase();
                            fields.push((name, line[colon + 1..].to_vec()));
                        }
                    }
                }
                Err(LineErr::Stop(s)) => {
                    reply.headers = recorded(&fields);
                    reply.end = BodyEnd::CutOff;
                    return (Some(reply), Some(s));
                }
                Err(LineErr::TooLong(m)) => {
                    reply.headers = recorded(&fields);
                    reply.end = BodyEnd::Malformed(m);
                    return (Some(reply), None);
                }
            }
        }
        if (100..200).contains(&status) && status != 101 {
            // An interim response: the final one follows.
            continue;
        }
        reply.headers = recorded(&fields);
        let stop = read_body(&mut w, &fields, &mut reply, body_limit);
        return (Some(reply), stop);
    }
}

fn recorded(fields: &[(String, Vec<u8>)]) -> Headers {
    let mut h = Headers::default();
    for (name, v) in fields {
        let slot = match name.as_str() {
            "content-type" => &mut h.content_type,
            "request-id" => &mut h.request_id,
            "retry-after" => &mut h.retry_after,
            _ => continue,
        };
        slot.push(runs::header_value(v));
    }
    h
}

/// `HTTP/1.x SSS[ reason]` → the status.
pub(crate) fn parse_status(line: &[u8]) -> Option<u16> {
    let rest = line.strip_prefix(b"HTTP/1.")?;
    if rest.len() < 5 || !rest[0].is_ascii_digit() || rest[1] != b' ' {
        return None;
    }
    let code = &rest[2..5];
    if !code.iter().all(|c| c.is_ascii_digit()) || code[0] == b'0' {
        return None;
    }
    if rest.len() > 5 && rest[5] != b' ' {
        return None;
    }
    std::str::from_utf8(code).ok()?.parse().ok()
}

fn is_tchar(c: u8) -> bool {
    c.is_ascii_alphanumeric() || b"!#$%&'*+-.^_`|~".contains(&c)
}

/// The comma-separated elements of every value of `name`, trimmed and
/// lower-cased, empty elements dropped.
fn list(fields: &[(String, Vec<u8>)], name: &str) -> Vec<String> {
    fields
        .iter()
        .filter(|(n, _)| n == name)
        .flat_map(|(_, v)| {
            String::from_utf8_lossy(v)
                .split(',')
                .map(|e| e.trim_matches([' ', '\t']).to_ascii_lowercase())
                .filter(|e| !e.is_empty())
                .collect::<Vec<_>>()
        })
        .collect()
}

fn read_body<R: Read + ?Sized>(
    w: &mut Wire<'_, R>,
    fields: &[(String, Vec<u8>)],
    reply: &mut Reply,
    limit: usize,
) -> Option<Stop> {
    let encodings: Vec<String> = list(fields, "content-encoding")
        .into_iter()
        .filter(|e| e != "identity")
        .collect();
    if !encodings.is_empty() {
        reply.coding = Some(format!(
            "the body has content-encoding {}",
            encodings.join(", ")
        ));
    }
    let status = reply.status;
    if status == 204 || status == 304 || (100..200).contains(&status) {
        reply.end = BodyEnd::Complete;
        return None;
    }
    let codings = list(fields, "transfer-encoding");
    if !codings.is_empty() {
        let others: Vec<&String> = codings.iter().filter(|c| *c != "chunked").collect();
        if !others.is_empty() && reply.coding.is_none() {
            reply.coding = Some(format!(
                "the body has transfer coding {}",
                others
                    .iter()
                    .map(|s| s.as_str())
                    .collect::<Vec<_>>()
                    .join(", ")
            ));
        }
        return if codings.last().map(String::as_str) == Some("chunked") {
            read_chunked(w, reply, limit)
        } else {
            read_to_close(w, reply, limit)
        };
    }
    let lengths = list(fields, "content-length");
    if !lengths.is_empty() {
        let n = match content_length(&lengths) {
            Some(n) => n,
            None => {
                reply.end = BodyEnd::Malformed(
                    "the response has an invalid or conflicting content-length".into(),
                );
                return None;
            }
        };
        let want = n.min(limit as u64) as usize;
        match w.take(want, &mut reply.body) {
            Ok(()) => {
                reply.end = if n > limit as u64 {
                    BodyEnd::TooLarge
                } else {
                    BodyEnd::Complete
                };
                None
            }
            Err(s) => {
                reply.end = BodyEnd::CutOff;
                Some(s)
            }
        }
    } else {
        read_to_close(w, reply, limit)
    }
}

fn content_length(values: &[String]) -> Option<u64> {
    let first = &values[0];
    if first.is_empty() || first.len() > 19 || !first.bytes().all(|c| c.is_ascii_digit()) {
        return None;
    }
    if values.iter().any(|v| v != first) {
        return None;
    }
    first.parse().ok()
}

fn read_to_close<R: Read + ?Sized>(
    w: &mut Wire<'_, R>,
    reply: &mut Reply,
    limit: usize,
) -> Option<Stop> {
    loop {
        let room = limit - reply.body.len();
        let k = w.avail().len().min(room);
        reply.body.extend_from_slice(&w.buf[w.pos..w.pos + k]);
        w.pos += k;
        if !w.avail().is_empty() {
            // More than the limit arrived: keep the first 32 MiB and stop.
            reply.end = BodyEnd::TooLarge;
            return None;
        }
        match w.fill() {
            Ok(()) => {}
            Err(Stop::Eof) => {
                reply.end = BodyEnd::Complete;
                return None;
            }
            Err(s) => {
                reply.end = BodyEnd::CutOff;
                return Some(s);
            }
        }
    }
}

fn read_chunked<R: Read + ?Sized>(
    w: &mut Wire<'_, R>,
    reply: &mut Reply,
    limit: usize,
) -> Option<Stop> {
    loop {
        let mut budget = CHUNK_LINE_LIMIT;
        let line = match w.line(&mut budget, "a chunk-size line") {
            Ok(l) => l,
            Err(e) => return cut(reply, e),
        };
        let size_text = line.split(|c| *c == b';').next().unwrap_or(&[]);
        let size_text = String::from_utf8_lossy(size_text);
        let size_text = size_text.trim_matches([' ', '\t']);
        let size = if !size_text.is_empty()
            && size_text.len() <= 15
            && size_text.bytes().all(|c| c.is_ascii_hexdigit())
        {
            u64::from_str_radix(size_text, 16).ok()
        } else {
            None
        };
        let Some(size) = size else {
            reply.end = BodyEnd::Malformed(format!(
                "the chunked body has an invalid chunk-size line {:?}",
                String::from_utf8_lossy(&line)
            ));
            return None;
        };
        if size == 0 {
            // Trailer fields up to the empty line; they are not recorded.
            let mut budget = HEAD_LIMIT;
            loop {
                match w.line(&mut budget, "the chunked trailer") {
                    Ok(l) if l.is_empty() => {
                        reply.end = BodyEnd::Complete;
                        return None;
                    }
                    Ok(_) => {}
                    Err(e) => return cut(reply, e),
                }
            }
        }
        let room = (limit - reply.body.len()) as u64;
        if size > room {
            if let Err(s) = w.take(room as usize, &mut reply.body) {
                reply.end = BodyEnd::CutOff;
                return Some(s);
            }
            reply.end = BodyEnd::TooLarge;
            return None;
        }
        if let Err(s) = w.take(size as usize, &mut reply.body) {
            reply.end = BodyEnd::CutOff;
            return Some(s);
        }
        let mut budget = 2;
        match w.line(&mut budget, "the end of a chunk") {
            Ok(l) if l.is_empty() => {}
            Ok(_) | Err(LineErr::TooLong(_)) => {
                reply.end =
                    BodyEnd::Malformed("a chunk is longer than its chunk-size line says".into());
                return None;
            }
            Err(LineErr::Stop(s)) => {
                reply.end = BodyEnd::CutOff;
                return Some(s);
            }
        }
    }
}

fn cut(reply: &mut Reply, e: LineErr) -> Option<Stop> {
    match e {
        LineErr::Stop(s) => {
            reply.end = BodyEnd::CutOff;
            Some(s)
        }
        LineErr::TooLong(m) => {
            reply.end = BodyEnd::Malformed(m);
            None
        }
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use std::io::Cursor;

    /// A reader that returns at most `step` bytes per call and then ends,
    /// or fails with `fail` at the end when given.
    pub struct Trickle {
        data: Vec<u8>,
        at: usize,
        step: usize,
        fail: Option<io::ErrorKind>,
    }

    impl Trickle {
        pub fn new(data: &[u8], step: usize) -> Self {
            Trickle {
                data: data.to_vec(),
                at: 0,
                step,
                fail: None,
            }
        }
        pub fn failing(mut self, kind: io::ErrorKind) -> Self {
            self.fail = Some(kind);
            self
        }
    }

    impl Read for Trickle {
        fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
            if self.at == self.data.len() {
                return match self.fail {
                    Some(k) => Err(io::Error::new(k, "test failure")),
                    None => Ok(0),
                };
            }
            let n = self.step.min(buf.len()).min(self.data.len() - self.at);
            buf[..n].copy_from_slice(&self.data[self.at..self.at + n]);
            self.at += n;
            Ok(n)
        }
    }

    fn read_all(data: &[u8]) -> (Option<Reply>, Option<Stop>) {
        // Every case is read in one piece and byte by byte: framing must not
        // depend on how the bytes arrive.
        let whole = read_response(&mut Cursor::new(data.to_vec()), &Ungated, BODY_LIMIT);
        let bytewise = read_response(&mut Trickle::new(data, 1), &Ungated, BODY_LIMIT);
        assert_eq!(whole, bytewise, "framing depends on read sizes");
        whole
    }

    #[test]
    fn request_head_is_exact() {
        let e = Endpoint::parse("http://127.0.0.1:8080/base").unwrap();
        let head = request_head(&e, "sk-test", "2026-10-21", 42);
        assert_eq!(
            head,
            b"POST /base/v1/messages HTTP/1.1\r\nhost: 127.0.0.1:8080\r\nx-api-key: sk-test\r\nanthropic-version: 2026-10-21\r\nanthropic-beta: compact-2026-09-04\r\ncontent-type: application/json\r\ncontent-length: 42\r\nconnection: close\r\n\r\n"
        );
        let head = request_head(&Endpoint::default_base(), "k", "v", 0);
        assert!(head.starts_with(b"POST /v1/messages HTTP/1.1\r\nhost: api.anthropic.com\r\n"));
        assert!(
            String::from_utf8(head)
                .unwrap()
                .contains("anthropic-beta: compact-2026-09-04")
        );
    }

    #[test]
    fn content_length_framing() {
        let (r, stop) = read_all(
            b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nContent-Type: application/json\r\n\r\nhelloEXTRA",
        );
        let r = r.unwrap();
        assert_eq!(stop, None);
        assert_eq!(
            (r.status, r.body.as_slice(), r.end),
            (200, &b"hello"[..], BodyEnd::Complete)
        );
        assert_eq!(r.headers.content_type, ["application/json"]);
        assert_eq!(r.coding, None);
    }

    #[test]
    fn short_content_length_body_is_cut_off() {
        let (r, stop) = read_all(b"HTTP/1.1 200 OK\r\ncontent-length: 10\r\n\r\nhello");
        let r = r.unwrap();
        assert_eq!(r.body, b"hello");
        assert_eq!(r.end, BodyEnd::CutOff);
        assert_eq!(stop, Some(Stop::Eof));
        let (r, stop) = read_response(
            &mut Trickle::new(b"HTTP/1.1 529 x\r\ncontent-length: 10\r\n\r\nab", 3)
                .failing(io::ErrorKind::ConnectionReset),
            &Ungated,
            BODY_LIMIT,
        );
        assert_eq!(r.unwrap().body, b"ab");
        assert!(matches!(stop, Some(Stop::Broken(_))));
    }

    #[test]
    fn chunked_framing_removes_only_the_chunking() {
        let raw = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n4;ext=1\r\n{\"a\"\r\nA\r\n:\"0123456\"\r\n1\r\n}\r\n0\r\nx-trailer: y\r\n\r\n";
        let (r, stop) = read_all(raw);
        let r = r.unwrap();
        assert_eq!(stop, None);
        assert_eq!(r.body, b"{\"a\":\"0123456\"}");
        assert_eq!(r.end, BodyEnd::Complete);
        // Upper-case hex digits and bare LF line ends are accepted.
        let (r, _) =
            read_all(b"HTTP/1.1 200 OK\ntransfer-encoding: chunked\n\nB\nhello world\n0\n\n");
        assert_eq!(r.unwrap().body, b"hello world");
    }

    #[test]
    fn unterminated_or_malformed_chunks() {
        let (r, stop) =
            read_all(b"HTTP/1.1 200 OK\r\ntransfer-encoding: chunked\r\n\r\n5\r\nhello\r\n");
        let r = r.unwrap();
        assert_eq!(
            (r.body.as_slice(), &r.end),
            (&b"hello"[..], &BodyEnd::CutOff)
        );
        assert_eq!(stop, Some(Stop::Eof));
        let (r, _) = read_all(b"HTTP/1.1 200 OK\r\ntransfer-encoding: chunked\r\n\r\n5\r\nhel");
        assert_eq!(r.unwrap().end, BodyEnd::CutOff);
        let (r, stop) = read_all(
            b"HTTP/1.1 200 OK\r\ntransfer-encoding: chunked\r\n\r\nzz\r\nhello\r\n0\r\n\r\n",
        );
        assert!(matches!(r.unwrap().end, BodyEnd::Malformed(_)));
        assert_eq!(stop, None);
        let (r, _) = read_all(
            b"HTTP/1.1 200 OK\r\ntransfer-encoding: chunked\r\n\r\n2\r\nhello\r\n0\r\n\r\n",
        );
        let r = r.unwrap();
        assert_eq!(r.body, b"he");
        assert!(matches!(r.end, BodyEnd::Malformed(_)));
        // The trailer section must end too.
        let (r, _) = read_all(b"HTTP/1.1 200 OK\r\ntransfer-encoding: chunked\r\n\r\n0\r\n");
        assert_eq!(r.unwrap().end, BodyEnd::CutOff);
    }

    #[test]
    fn close_delimited_framing() {
        let (r, stop) = read_all(b"HTTP/1.1 200 OK\r\n\r\n{\"all\":\"until close\"}");
        let r = r.unwrap();
        assert_eq!(stop, None);
        assert_eq!(
            (r.body.as_slice(), r.end),
            (&b"{\"all\":\"until close\"}"[..], BodyEnd::Complete)
        );
        // A transfer coding that does not end in chunked is read to the close
        // and makes the body undecodable.
        let (r, _) = read_all(b"HTTP/1.1 200 OK\r\ntransfer-encoding: gzip\r\n\r\nzz");
        let r = r.unwrap();
        assert_eq!(r.body, b"zz");
        assert!(r.coding.unwrap().contains("gzip"));
    }

    #[test]
    fn codings_other_than_identity_are_flagged() {
        let (r, _) = read_all(
            b"HTTP/1.1 200 OK\r\ncontent-encoding: identity\r\ncontent-length: 2\r\n\r\n{}",
        );
        assert_eq!(r.unwrap().coding, None);
        let (r, _) =
            read_all(b"HTTP/1.1 200 OK\r\nContent-Encoding: GZIP\r\ncontent-length: 2\r\n\r\nxx");
        assert!(r.unwrap().coding.unwrap().contains("gzip"));
        let (r, _) = read_all(
            b"HTTP/1.1 200 OK\r\ntransfer-encoding: gzip, chunked\r\n\r\n2\r\nxx\r\n0\r\n\r\n",
        );
        let r = r.unwrap();
        assert_eq!(r.body, b"xx");
        assert!(r.coding.unwrap().contains("gzip"));
    }

    #[test]
    fn content_length_must_be_one_valid_number() {
        for raw in [
            &b"HTTP/1.1 200 OK\r\ncontent-length: 2\r\ncontent-length: 3\r\n\r\n{}"[..],
            b"HTTP/1.1 200 OK\r\ncontent-length: -2\r\n\r\n{}",
            b"HTTP/1.1 200 OK\r\ncontent-length: 2x\r\n\r\n{}",
        ] {
            let (r, stop) = read_all(raw);
            assert!(matches!(r.unwrap().end, BodyEnd::Malformed(_)));
            assert_eq!(stop, None);
        }
        let (r, _) = read_all(b"HTTP/1.1 200 OK\r\ncontent-length: 2, 2\r\n\r\n{}");
        assert_eq!(r.unwrap().end, BodyEnd::Complete);
    }

    #[test]
    fn interim_responses_are_skipped() {
        let (r, stop) = read_all(
            b"HTTP/1.1 100 Continue\r\nrequest-id: interim\r\n\r\nHTTP/1.1 200 OK\r\nrequest-id: final\r\ncontent-length: 2\r\n\r\n{}",
        );
        let r = r.unwrap();
        assert_eq!(stop, None);
        assert_eq!(r.status, 200);
        assert_eq!(r.headers.request_id, ["final"]);
        let (r, _) = read_all(b"HTTP/1.1 204 No Content\r\n\r\n");
        let r = r.unwrap();
        assert_eq!((r.status, r.end), (204, BodyEnd::Complete));
    }

    #[test]
    fn recorded_headers_match_case_insensitively_in_order() {
        let (r, _) = read_all(
            b"HTTP/1.1 529 Overloaded\r\nRequest-ID:  req_1 \t\r\nretry-after: 5\r\nRETRY-AFTER:\t7\r\nx-other: no\r\ncontent-type: application/json\r\n folded part\r\ncontent-length: 0\r\n\r\n",
        );
        let h = r.unwrap().headers;
        assert_eq!(h.request_id, ["req_1"]);
        assert_eq!(h.retry_after, ["5", "7"]);
        assert_eq!(h.content_type, ["application/json folded part"]);
    }

    #[test]
    fn status_lines() {
        assert_eq!(parse_status(b"HTTP/1.1 200 OK"), Some(200));
        assert_eq!(parse_status(b"HTTP/1.0 529"), Some(529));
        assert_eq!(parse_status(b"HTTP/1.1 404 Not Found here"), Some(404));
        for bad in [
            &b"HTTP/2 200 OK"[..],
            b"HTTP/1.1 20 OK",
            b"HTTP/1.1 2000 OK",
            b"HTTP/1.1 099 x",
            b"http/1.1 200 OK",
            b"HTTP/1.1  200 OK",
            b"SSH-2.0-OpenSSH",
            b"",
        ] {
            assert_eq!(
                parse_status(bad),
                None,
                "{:?}",
                String::from_utf8_lossy(bad)
            );
        }
    }

    #[test]
    fn replies_without_a_status_line() {
        let (r, stop) = read_all(b"");
        assert_eq!(r, None);
        assert!(matches!(stop, Some(Stop::Broken(m)) if m.contains("before a status line")));
        let (r, stop) = read_all(b"garbage\r\n\r\n");
        assert_eq!(r, None);
        assert!(matches!(stop, Some(Stop::Broken(m)) if m.contains("status line")));
        // A status line cut off in the head keeps the status and the
        // complete header lines seen.
        let (r, stop) = read_all(b"HTTP/1.1 503 x\r\nrequest-id: a\r\nretry-af");
        let r = r.unwrap();
        assert_eq!((r.status, r.end.clone()), (503, BodyEnd::CutOff));
        assert_eq!(r.headers.request_id, ["a"]);
        assert_eq!(stop, Some(Stop::Eof));
    }

    #[test]
    fn oversized_heads_are_malformed() {
        let mut raw = b"HTTP/1.1 200 OK\r\n".to_vec();
        for _ in 0..(HEAD_LIMIT / 64 + 1) {
            raw.extend_from_slice(b"x-filler: ");
            raw.extend_from_slice(&[b'a'; 52]);
            raw.extend_from_slice(b"\r\n");
        }
        raw.extend_from_slice(b"\r\n");
        let (r, stop) = read_response(&mut Cursor::new(raw), &Ungated, BODY_LIMIT);
        assert!(matches!(r.unwrap().end, BodyEnd::Malformed(_)));
        assert_eq!(stop, None);
    }

    #[test]
    fn body_limit_keeps_the_first_bytes_and_stops() {
        let limit = 8;
        for raw in [
            &b"HTTP/1.1 200 OK\r\ncontent-length: 12\r\n\r\n0123456789ab"[..],
            b"HTTP/1.1 200 OK\r\n\r\n0123456789ab",
            b"HTTP/1.1 200 OK\r\ntransfer-encoding: chunked\r\n\r\n6\r\n012345\r\n6\r\n6789ab\r\n0\r\n\r\n",
        ] {
            for step in [1, 1024] {
                let (r, stop) = read_response(&mut Trickle::new(raw, step), &Ungated, limit);
                let r = r.unwrap();
                assert_eq!(r.body, b"01234567");
                assert_eq!(r.end, BodyEnd::TooLarge);
                assert_eq!(stop, None);
            }
        }
        // Exactly at the limit is complete.
        for raw in [
            &b"HTTP/1.1 200 OK\r\ncontent-length: 8\r\n\r\n01234567"[..],
            b"HTTP/1.1 200 OK\r\n\r\n01234567",
            b"HTTP/1.1 200 OK\r\ntransfer-encoding: chunked\r\n\r\n8\r\n01234567\r\n0\r\n\r\n",
        ] {
            let (r, _) = read_response(&mut Trickle::new(raw, 3), &Ungated, limit);
            assert_eq!(r.unwrap().end, BodyEnd::Complete);
        }
    }

    #[test]
    fn the_real_limit_is_32_mib() {
        assert_eq!(BODY_LIMIT, 33_554_432);
        let mut raw = b"HTTP/1.1 200 OK\r\n\r\n".to_vec();
        raw.resize(raw.len() + BODY_LIMIT + 1, b'x');
        let (r, _) = read_response(&mut Cursor::new(raw), &Ungated, BODY_LIMIT);
        let r = r.unwrap();
        assert_eq!(r.body.len(), BODY_LIMIT);
        assert_eq!(r.end, BodyEnd::TooLarge);
    }

    #[test]
    fn write_counted_counts_accepted_bytes() {
        struct Limited(usize, Vec<u8>);
        impl Write for Limited {
            fn write(&mut self, b: &[u8]) -> io::Result<usize> {
                if self.0 == 0 {
                    return Err(io::Error::new(io::ErrorKind::BrokenPipe, "closed"));
                }
                let n = b.len().min(self.0).min(3);
                self.0 -= n;
                self.1.extend_from_slice(&b[..n]);
                Ok(n)
            }
            fn flush(&mut self) -> io::Result<()> {
                Ok(())
            }
        }
        let mut w = Limited(100, Vec::new());
        let mut n = 0;
        write_counted(&mut w, &Ungated, b"0123456789", &mut n).unwrap();
        assert_eq!((n, w.1.as_slice()), (10, &b"0123456789"[..]));
        let mut w = Limited(4, Vec::new());
        let mut n = 0;
        let e = write_counted(&mut w, &Ungated, b"0123456789", &mut n).unwrap_err();
        assert!(matches!(e, Stop::Broken(_)));
        assert_eq!(n, 4);
    }
}
