//! One provider attempt over a fresh connection (INTERFACE 6.1, 6.6, 6.8).
//!
//! An attempt resolves and connects (to the proxy when one is in use), opens
//! the CONNECT tunnel, completes TLS, writes the request, and reads the
//! response to its end. The request timeout counts from the start of the
//! attempt and covers every step. Between system calls the attempt checks the
//! [`AbortHandle`]; firing the handle also shuts the socket down, so a call
//! blocked in the kernel returns at once and the attempt ends as aborted.
//!
//! Resolution and connecting run on a helper thread so that the stop path and
//! the deadline are honored while they block: the attempt stops waiting at
//! once, and the helper's late connection, if any, is closed when it finishes.
//!
//! The result is raw: how much of the request reached the connection, the
//! reply with its body exactly as received, and why reading stopped.
//! [`crate::provider::response::classify`] turns it into an outcome.

use std::io::{self, Read, Write};
use std::net::{Ipv4Addr, Shutdown, SocketAddr, TcpStream, ToSocketAddrs};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::sync::{Arc, Condvar, Mutex, MutexGuard};
use std::time::{Duration, Instant, SystemTime};

use rustls::pki_types::{DnsName, ServerName};
use rustls::{ClientConfig, ClientConnection, StreamOwned};

use crate::provider::StopCause;
use crate::provider::http::{self, BODY_LIMIT, Gate, HEAD_LIMIT, Reply, Stop};
use crate::provider::tls::Tls;
use crate::provider::url::{Host, Route};
use crate::util;

/// The pinned request timeout (Appendix B).
pub const REQUEST_TIMEOUT: Duration = Duration::from_secs(600);

/// How much of the request reached the connection (4.5 `request_written`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Written {
    None,
    Partial,
    Complete,
}

impl Written {
    pub fn as_str(self) -> &'static str {
        match self {
            Written::None => "none",
            Written::Partial => "partial",
            Written::Complete => "complete",
        }
    }
}

/// Why an attempt stopped before its response was read to the end.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Failure {
    /// Resolution, connecting, the tunnel, TLS, writing or reading failed,
    /// or the connection ended early. The text says which and why.
    Broken(String),
    /// The request timeout passed.
    Timeout,
    /// The stop path shut the connection down.
    Aborted(StopCause),
}

/// The raw result of one attempt.
#[derive(Debug, Clone)]
pub struct Attempt {
    pub started_at: SystemTime,
    pub ended_at: SystemTime,
    pub elapsed: Duration,
    /// The request timeout in force.
    pub timeout: Duration,
    /// The request body's length in bytes.
    pub body_bytes: usize,
    pub written: Written,
    /// Present when a status line was received.
    pub reply: Option<Reply>,
    /// Present when the attempt stopped before the response's end.
    pub failure: Option<Failure>,
}

impl Attempt {
    pub fn status(&self) -> Option<u16> {
        self.reply.as_ref().map(|r| r.status)
    }

    /// The first recorded `request-id` header value.
    pub fn request_id(&self) -> Option<&str> {
        self.reply
            .as_ref()
            .and_then(|r| r.headers.request_id.first())
            .map(String::as_str)
    }

    /// The recorded `retry-after` values, in order.
    pub fn retry_after(&self) -> &[String] {
        self.reply
            .as_ref()
            .map_or(&[][..], |r| r.headers.retry_after.as_slice())
    }

    pub fn elapsed_ms(&self) -> u64 {
        self.elapsed.as_millis().min(u64::MAX as u128) as u64
    }

    /// The attempt record's `timeout_seconds`.
    pub fn timeout_seconds(&self) -> u64 {
        self.timeout.as_secs()
    }

    pub fn started_at_utc(&self) -> String {
        utc(self.started_at)
    }

    pub fn ended_at_utc(&self) -> String {
        utc(self.ended_at)
    }

    /// Prose for the failure, if any, for run messages and diagnostics.
    pub fn failure_text(&self) -> Option<String> {
        self.failure.as_ref().map(|f| match f {
            Failure::Broken(m) => m.clone(),
            Failure::Timeout => format!(
                "no complete response within the request timeout of {} seconds",
                self.timeout_seconds()
            ),
            Failure::Aborted(StopCause::Close) => {
                "the request was aborted because close was requested".into()
            }
            Failure::Aborted(StopCause::Signal) => {
                "the request was aborted because a signal was received".into()
            }
        })
    }
}

fn utc(t: SystemTime) -> String {
    let d = t.duration_since(SystemTime::UNIX_EPOCH).unwrap_or_default();
    util::format_utc(d.as_secs() as i64, d.subsec_millis())
}

/// Shutting a connection down and arming its timeouts, from any thread.
pub(crate) trait SockCtl: Send + Sync {
    fn shutdown(&self);
    fn set_timeout(&self, d: Duration) -> io::Result<()>;
}

impl SockCtl for TcpStream {
    fn shutdown(&self) {
        let _ = TcpStream::shutdown(self, Shutdown::Both);
    }
    fn set_timeout(&self, d: Duration) -> io::Result<()> {
        self.set_read_timeout(Some(d))?;
        self.set_write_timeout(Some(d))
    }
}

#[cfg(unix)]
impl SockCtl for std::os::unix::net::UnixStream {
    fn shutdown(&self) {
        let _ = std::os::unix::net::UnixStream::shutdown(self, Shutdown::Both);
    }
    fn set_timeout(&self, d: Duration) -> io::Result<()> {
        self.set_read_timeout(Some(d))?;
        self.set_write_timeout(Some(d))
    }
}

/// The stop path's hold on in-flight attempts (6.8).
///
/// The watcher (close) or a signal-waiting thread calls [`abort`]: the first
/// cause is kept, the connection of the attempt in flight is shut down, and
/// any [`sleep`] returns. Every later attempt ends at once as aborted, so a
/// placement uses one handle for its whole life. `abort` takes a lock and is
/// not async-signal-safe; call it from a thread, never a signal handler.
///
/// [`abort`]: AbortHandle::abort
/// [`sleep`]: AbortHandle::sleep
#[derive(Clone, Default)]
pub struct AbortHandle {
    inner: Arc<AbortInner>,
}

#[derive(Default)]
struct AbortInner {
    state: Mutex<AbortState>,
    wake: Condvar,
}

#[derive(Default)]
struct AbortState {
    cause: Option<StopCause>,
    sock: Option<Arc<dyn SockCtl>>,
}

impl std::fmt::Debug for AbortHandle {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "AbortHandle({:?})", self.cause())
    }
}

impl AbortHandle {
    pub fn new() -> AbortHandle {
        AbortHandle::default()
    }

    fn lock(&self) -> MutexGuard<'_, AbortState> {
        self.inner
            .state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    /// Fire the stop path. The first cause wins.
    pub fn abort(&self, cause: StopCause) {
        let st = {
            let mut st = self.lock();
            if st.cause.is_none() {
                st.cause = Some(cause);
            }
            st.sock.clone()
        };
        if let Some(s) = st {
            s.shutdown();
        }
        self.inner.wake.notify_all();
    }

    /// The cause, once the stop path has fired.
    pub fn cause(&self) -> Option<StopCause> {
        self.lock().cause
    }

    /// Wait `d`, such as a retry delay, unless the stop path fires first;
    /// then return its cause at once.
    pub fn sleep(&self, d: Duration) -> Option<StopCause> {
        let until = Instant::now() + d;
        let mut st = self.lock();
        loop {
            if let Some(c) = st.cause {
                return Some(c);
            }
            let now = Instant::now();
            if now >= until {
                return None;
            }
            st = match self.inner.wake.wait_timeout(st, until - now) {
                Ok((g, _)) => g,
                Err(poisoned) => poisoned.into_inner().0,
            };
        }
    }

    /// Register the attempt's connection; shut it down at once if the stop
    /// path already fired.
    fn arm(&self, s: Arc<dyn SockCtl>) -> Result<Armed<'_>, StopCause> {
        let mut st = self.lock();
        if let Some(c) = st.cause {
            s.shutdown();
            return Err(c);
        }
        st.sock = Some(s);
        Ok(Armed(self))
    }
}

struct Armed<'a>(&'a AbortHandle);

impl Drop for Armed<'_> {
    fn drop(&mut self) {
        self.0.lock().sock = None;
    }
}

/// The deadline and stop-path checks between system calls.
struct Io<'a> {
    ctl: &'a dyn SockCtl,
    deadline: Instant,
    abort: &'a AbortHandle,
}

impl Gate for Io<'_> {
    fn before(&self) -> Result<(), Stop> {
        if let Some(c) = self.abort.cause() {
            return Err(Stop::Aborted(c));
        }
        let now = Instant::now();
        if now >= self.deadline {
            return Err(Stop::Timeout);
        }
        let left = (self.deadline - now).max(Duration::from_millis(1));
        // Some kernels (macOS) refuse socket options once the peer has shut
        // the connection down. The next call then returns at once with the
        // connection's own end or error, which is the fact worth recording;
        // the timeout set before stays in force otherwise.
        let _ = self.ctl.set_timeout(left);
        Ok(())
    }

    fn after_err(&self, e: &io::Error) -> Option<Stop> {
        if let Some(c) = self.abort.cause() {
            return Some(Stop::Aborted(c));
        }
        match e.kind() {
            io::ErrorKind::Interrupted => None,
            io::ErrorKind::WouldBlock | io::ErrorKind::TimedOut => {
                (Instant::now() >= self.deadline).then_some(Stop::Timeout)
            }
            // rustls reports a TCP close without close_notify this way; the
            // framing decides whether the response was complete.
            io::ErrorKind::UnexpectedEof => Some(Stop::Eof),
            _ => Some(Stop::Broken(describe(e))),
        }
    }

    fn after_eof(&self) -> Stop {
        match self.abort.cause() {
            Some(c) => Stop::Aborted(c),
            None => Stop::Eof,
        }
    }
}

fn describe(e: &io::Error) -> String {
    match e.get_ref() {
        // A TLS error carries its own description (an unknown issuer, a bad
        // name); the I/O wrapper adds nothing.
        Some(inner) if e.kind() == io::ErrorKind::InvalidData => format!("TLS: {inner}"),
        _ => util::describe(e),
    }
}

/// What an attempt sends and through what.
struct Plan<'a> {
    /// `host:port` for a CONNECT tunnel through the proxy.
    tunnel: Option<String>,
    tls: Option<(Arc<ClientConfig>, ServerName<'static>)>,
    head: Vec<u8>,
    body: &'a [u8],
}

#[derive(Default)]
struct Progress {
    written: usize,
    flushed: bool,
    reply: Option<Reply>,
    failure: Option<Failure>,
}

/// The provider client: a route, TLS roots, the key and the pinned version.
#[derive(Debug, Clone)]
pub struct Client {
    route: Route,
    tls: Tls,
    api_key: String,
    anthropic_version: String,
    timeout: Duration,
}

impl Client {
    /// `api_key` and `anthropic_version` must be visible ASCII (0x21–0x7E);
    /// `run` refuses a bad key before this (`provider_key_invalid`).
    /// `timeout` is the pinned 600 s, or a test build's override.
    pub fn new(
        route: Route,
        tls: Tls,
        api_key: &str,
        anthropic_version: &str,
        timeout: Duration,
    ) -> Result<Client, String> {
        let visible = |s: &str| !s.is_empty() && s.bytes().all(|c| (0x21..=0x7E).contains(&c));
        if !visible(api_key) {
            return Err("the API key is empty or has a byte outside 0x21-0x7E".into());
        }
        if !visible(anthropic_version) {
            return Err("the API version is empty or has a byte outside 0x21-0x7E".into());
        }
        if timeout.is_zero() {
            return Err("the request timeout must be positive".into());
        }
        Ok(Client {
            route,
            tls,
            api_key: api_key.to_string(),
            anthropic_version: anthropic_version.to_string(),
            timeout,
        })
    }

    pub fn route(&self) -> &Route {
        &self.route
    }

    pub fn timeout(&self) -> Duration {
        self.timeout
    }

    /// Send one attempt of `body` over a new connection. `after_written`
    /// runs once the whole request has been written and flushed, before the
    /// response is read (the `provider.sent` failure point); an error from it
    /// ends the attempt as a failed connection.
    pub fn send(
        &self,
        body: &[u8],
        abort: &AbortHandle,
        after_written: &mut dyn FnMut() -> io::Result<()>,
    ) -> Attempt {
        let started_at = SystemTime::now();
        let t0 = Instant::now();
        let deadline = t0 + self.timeout;
        let mut p = Progress::default();
        match self.connect(deadline, abort) {
            Ok(tcp) => match tcp.try_clone() {
                Ok(ctl) => self.exchange_on(
                    tcp,
                    Arc::new(ctl),
                    deadline,
                    body,
                    abort,
                    after_written,
                    BODY_LIMIT,
                    &mut p,
                ),
                Err(e) => {
                    p.failure = Some(Failure::Broken(format!(
                        "the connection could not be prepared: {}",
                        util::describe(&e)
                    )))
                }
            },
            Err(s) => p.failure = Some(failure(s, "connecting")),
        }
        self.finish(started_at, t0, body.len(), p)
    }

    fn finish(
        &self,
        started_at: SystemTime,
        t0: Instant,
        body_bytes: usize,
        p: Progress,
    ) -> Attempt {
        let total = self.head(body_bytes).len() + body_bytes;
        let written = if p.written == 0 {
            Written::None
        } else if p.written >= total && p.flushed {
            Written::Complete
        } else {
            Written::Partial
        };
        Attempt {
            started_at,
            ended_at: SystemTime::now(),
            elapsed: t0.elapsed(),
            timeout: self.timeout,
            body_bytes,
            written,
            reply: p.reply,
            failure: p.failure,
        }
    }

    fn head(&self, body_bytes: usize) -> Vec<u8> {
        http::request_head(
            &self.route.endpoint,
            &self.api_key,
            &self.anthropic_version,
            body_bytes,
        )
    }

    fn plan<'a>(&self, body: &'a [u8]) -> Result<Plan<'a>, String> {
        let ep = &self.route.endpoint;
        let tls = if ep.tls {
            let name = match &ep.host {
                Host::Name(n) => ServerName::DnsName(
                    DnsName::try_from(n.clone())
                        .map_err(|_| format!("{n} is not a name TLS can verify"))?,
                ),
                Host::V4(a) => ServerName::from(std::net::IpAddr::V4(*a)),
                Host::V6(a) => ServerName::from(std::net::IpAddr::V6(*a)),
            };
            Some((self.tls.config(), name))
        } else {
            None
        };
        Ok(Plan {
            tunnel: self.route.proxy.as_ref().map(|_| ep.authority()),
            tls,
            head: self.head(body.len()),
            body,
        })
    }

    /// Resolve and connect on a helper thread, waiting for it only while the
    /// stop path has not fired and the deadline has not passed.
    fn connect(&self, deadline: Instant, abort: &AbortHandle) -> Result<TcpStream, Stop> {
        if let Some(c) = abort.cause() {
            return Err(Stop::Aborted(c));
        }
        let (host, port) = match &self.route.proxy {
            Some(p) => (p.host.clone(), p.port),
            None => (self.route.endpoint.host.clone(), self.route.endpoint.port),
        };
        wait_for(move || dial(&host, port, deadline), deadline, abort)
    }

    /// The attempt over an open connection: tunnel, TLS, request, response.
    fn exchange_on<S: Read + Write>(
        &self,
        mut sock: S,
        ctl: Arc<dyn SockCtl>,
        deadline: Instant,
        body: &[u8],
        abort: &AbortHandle,
        after_written: &mut dyn FnMut() -> io::Result<()>,
        body_limit: usize,
        p: &mut Progress,
    ) {
        let plan = match self.plan(body) {
            Ok(plan) => plan,
            Err(m) => {
                p.failure = Some(Failure::Broken(m));
                return;
            }
        };
        let _armed = match abort.arm(Arc::clone(&ctl)) {
            Ok(a) => a,
            Err(c) => {
                p.failure = Some(Failure::Aborted(c));
                return;
            }
        };
        let gate = Io {
            ctl: ctl.as_ref(),
            deadline,
            abort,
        };
        if let Some(authority) = &plan.tunnel {
            if let Err(s) = tunnel(&mut sock, &gate, authority) {
                p.failure = Some(failure(s, "the proxy tunnel"));
                return;
            }
        }
        match &plan.tls {
            None => talk(&mut sock, &gate, &plan, after_written, body_limit, p),
            Some((config, name)) => {
                let conn = match ClientConnection::new(Arc::clone(config), name.clone()) {
                    Ok(c) => c,
                    Err(e) => {
                        p.failure = Some(Failure::Broken(format!("TLS could not start: {e}")));
                        return;
                    }
                };
                let mut tls = StreamOwned::new(conn, sock);
                if let Err(s) = handshake(&mut tls, &gate) {
                    p.failure = Some(failure(s, "the TLS handshake"));
                    return;
                }
                talk(&mut tls, &gate, &plan, after_written, body_limit, p);
            }
        }
    }
}

/// Run `dialer` on a helper thread and wait for its result while the stop
/// path has not fired and the deadline has not passed.
fn wait_for(
    dialer: impl FnOnce() -> Result<TcpStream, Stop> + Send + 'static,
    deadline: Instant,
    abort: &AbortHandle,
) -> Result<TcpStream, Stop> {
    let (tx, rx) = mpsc::channel();
    std::thread::Builder::new()
        .name("stewart-connect".into())
        .spawn(move || {
            let _ = tx.send(dialer());
        })
        .map_err(|e| Stop::Broken(format!("the connection thread could not start: {e}")))?;
    loop {
        if let Some(c) = abort.cause() {
            return Err(Stop::Aborted(c));
        }
        let now = Instant::now();
        if now >= deadline {
            return Err(Stop::Timeout);
        }
        match rx.recv_timeout((deadline - now).min(Duration::from_millis(25))) {
            Ok(r) => return r,
            Err(RecvTimeoutError::Timeout) => {}
            Err(RecvTimeoutError::Disconnected) => {
                return Err(Stop::Broken(
                    "the connection thread ended without a result".into(),
                ));
            }
        }
    }
}

fn failure(s: Stop, context: &str) -> Failure {
    match s {
        Stop::Timeout => Failure::Timeout,
        Stop::Aborted(c) => Failure::Aborted(c),
        Stop::Eof => Failure::Broken(format!("{context}: the connection closed")),
        Stop::Broken(m) => Failure::Broken(format!("{context}: {m}")),
    }
}

/// Resolve `host` and connect to the first address that answers. `localhost`
/// is 127.0.0.1 without the resolver.
fn dial(host: &Host, port: u16, deadline: Instant) -> Result<TcpStream, Stop> {
    let addrs: Vec<SocketAddr> = match host {
        Host::V4(a) => vec![SocketAddr::from((*a, port))],
        Host::V6(a) => vec![SocketAddr::from((*a, port))],
        Host::Name(n) if n.eq_ignore_ascii_case("localhost") => {
            vec![SocketAddr::from((Ipv4Addr::LOCALHOST, port))]
        }
        Host::Name(n) => match (n.as_str(), port).to_socket_addrs() {
            Ok(it) => it.collect(),
            Err(e) => return Err(Stop::Broken(format!("resolving {n} failed: {e}"))),
        },
    };
    if addrs.is_empty() {
        return Err(Stop::Broken("resolution returned no address".into()));
    }
    let mut errors = Vec::new();
    for a in addrs {
        let now = Instant::now();
        if now >= deadline {
            return Err(Stop::Timeout);
        }
        match TcpStream::connect_timeout(&a, deadline - now) {
            Ok(s) => return Ok(s),
            Err(e) => errors.push(format!("{a}: {}", util::describe(&e))),
        }
    }
    if Instant::now() >= deadline {
        return Err(Stop::Timeout);
    }
    Err(Stop::Broken(format!(
        "no connection could be made ({})",
        errors.join("; ")
    )))
}

/// Open the CONNECT tunnel. The reply head is read a byte at a time so that
/// no byte of the tunnel is consumed with it.
fn tunnel<S: Read + Write>(s: &mut S, gate: &dyn Gate, authority: &str) -> Result<(), Stop> {
    let req = format!("CONNECT {authority} HTTP/1.1\r\nhost: {authority}\r\n\r\n");
    let mut n = 0;
    http::write_counted(s, gate, req.as_bytes(), &mut n)?;
    http::flush(s, gate)?;
    let mut head = Vec::new();
    while !(head.ends_with(b"\r\n\r\n") || head.ends_with(b"\n\n")) {
        if head.len() >= HEAD_LIMIT {
            return Err(Stop::Broken(
                "the proxy's reply to CONNECT is too long".into(),
            ));
        }
        let mut b = [0u8; 1];
        gate.before()?;
        match s.read(&mut b) {
            Ok(0) => {
                return Err(match gate.after_eof() {
                    Stop::Eof => Stop::Broken(
                        "the proxy closed the connection before answering CONNECT".into(),
                    ),
                    other => other,
                });
            }
            Ok(_) => head.push(b[0]),
            Err(e) => {
                if let Some(st) = gate.after_err(&e) {
                    return Err(st);
                }
            }
        }
    }
    let first = head.split(|c| *c == b'\n').next().unwrap_or(&[]);
    let first = first.strip_suffix(b"\r").unwrap_or(first);
    match http::parse_status(first) {
        Some(status) if (200..300).contains(&status) => Ok(()),
        Some(status) => Err(Stop::Broken(format!(
            "the proxy refused CONNECT {authority} with status {status}"
        ))),
        None => Err(Stop::Broken(
            "the proxy's reply to CONNECT is not an HTTP/1.x status line".into(),
        )),
    }
}

fn handshake<S: Read + Write>(
    tls: &mut StreamOwned<ClientConnection, S>,
    gate: &dyn Gate,
) -> Result<(), Stop> {
    while tls.conn.is_handshaking() {
        gate.before()?;
        if let Err(e) = tls.conn.complete_io(&mut tls.sock) {
            if let Some(s) = gate.after_err(&e) {
                return Err(match s {
                    Stop::Eof => Stop::Broken("the connection closed during the handshake".into()),
                    other => other,
                });
            }
        }
    }
    Ok(())
}

/// Write the request, run the hook, read the response.
fn talk<S: Read + Write>(
    s: &mut S,
    gate: &dyn Gate,
    plan: &Plan,
    after_written: &mut dyn FnMut() -> io::Result<()>,
    body_limit: usize,
    p: &mut Progress,
) {
    let sent = http::write_counted(s, gate, &plan.head, &mut p.written)
        .and_then(|()| http::write_counted(s, gate, plan.body, &mut p.written))
        .and_then(|()| http::flush(s, gate));
    match sent {
        Ok(()) => {
            p.flushed = true;
            if let Err(e) = after_written() {
                p.failure = Some(Failure::Broken(format!(
                    "the attempt failed after the request was written: {}",
                    util::describe(&e)
                )));
                return;
            }
        }
        Err(stop @ (Stop::Timeout | Stop::Aborted(_))) => {
            p.failure = Some(failure(stop, "writing the request"));
            return;
        }
        Err(stop) => {
            // A provider may answer before reading the whole request (a 413,
            // say) and close; its answer is the attempt's result when it can
            // still be read.
            let (reply, rstop) = http::read_response(s, gate, body_limit);
            if reply.is_some() {
                p.reply = reply;
                p.failure = rstop.map(|r| failure(r, "reading the response"));
            } else {
                p.failure = Some(failure(stop, "writing the request"));
            }
            return;
        }
    }
    let (reply, stop) = http::read_response(s, gate, body_limit);
    p.reply = reply;
    p.failure = stop.map(|st| match st {
        Stop::Eof => Failure::Broken(
            "reading the response: the connection closed before the response was complete".into(),
        ),
        other => failure(other, "reading the response"),
    });
}

/// A test build's request timeout: whole seconds, 1–600 (Appendix C).
#[cfg(feature = "fault-injection")]
pub fn parse_test_timeout(v: &str) -> Result<Duration, String> {
    let ok = !v.is_empty() && v.len() <= 3 && v.bytes().all(|c| c.is_ascii_digit());
    match v.parse::<u64>() {
        Ok(n) if ok && (1..=600).contains(&n) => Ok(Duration::from_secs(n)),
        _ => Err(format!(
            "the test request timeout {v:?} is not a whole number of seconds from 1 to 600"
        )),
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use crate::provider::http::BodyEnd;
    use crate::provider::tls::tests::{server_config, test_tls};
    use crate::provider::url::{Endpoint, Proxy};
    use std::os::unix::net::UnixStream;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::thread;

    pub fn client(base: &str, proxy: Option<&str>, timeout: Duration) -> Client {
        let route = Route::new(
            Endpoint::parse(base).unwrap(),
            proxy.map(|p| Proxy::parse(p).unwrap()),
        );
        Client::new(route, test_tls(), "sk-test-key", "2026-10-21", timeout).unwrap()
    }

    /// Run one attempt over a socket pair; `server` plays the far end.
    pub fn over_pair(
        c: &Client,
        body: &[u8],
        abort: &AbortHandle,
        limit: usize,
        server: impl FnOnce(UnixStream) + Send + 'static,
    ) -> Attempt {
        let (a, b) = UnixStream::pair().unwrap();
        let far = thread::spawn(move || server(b));
        let started_at = SystemTime::now();
        let t0 = Instant::now();
        let mut p = Progress::default();
        let ctl = a.try_clone().unwrap();
        c.exchange_on(
            a,
            Arc::new(ctl),
            t0 + c.timeout,
            body,
            abort,
            &mut || Ok(()),
            limit,
            &mut p,
        );
        let attempt = c.finish(started_at, t0, body.len(), p);
        far.join().unwrap();
        attempt
    }

    /// Stall without answering until the client side closes (after its
    /// attempt ends, `over_pair` drops it).
    pub fn until_closed<R: Read>(s: &mut R) {
        let mut sink = Vec::new();
        let _ = s.read_to_end(&mut sink);
    }

    /// Read one HTTP request (head and content-length body) from `s`.
    pub fn read_request<R: Read>(s: &mut R) -> Vec<u8> {
        let mut got = Vec::new();
        let mut b = [0u8; 1];
        while !got.ends_with(b"\r\n\r\n") {
            if s.read(&mut b).unwrap() == 0 {
                return got;
            }
            got.push(b[0]);
        }
        let head = String::from_utf8_lossy(&got).to_string();
        let len: usize = head
            .lines()
            .find_map(|l| l.strip_prefix("content-length: "))
            .map(|v| v.trim().parse().unwrap())
            .unwrap_or(0);
        let mut body = vec![0u8; len];
        s.read_exact(&mut body).unwrap();
        got.extend_from_slice(&body);
        got
    }

    const OK: &[u8] = b"HTTP/1.1 200 OK\r\ncontent-type: application/json\r\nrequest-id: req_1\r\ncontent-length: 2\r\n\r\n{}";

    fn plain() -> Client {
        client("http://127.0.0.1:8080", None, Duration::from_secs(5))
    }

    #[test]
    fn sends_exactly_the_head_and_body() {
        let (tx, rx) = mpsc::channel();
        let a = over_pair(
            &plain(),
            b"{\"x\":1}",
            &AbortHandle::new(),
            BODY_LIMIT,
            move |mut s| {
                tx.send(read_request(&mut s)).unwrap();
                s.write_all(OK).unwrap();
            },
        );
        let sent = rx.recv().unwrap();
        assert_eq!(
            sent,
            b"POST /v1/messages HTTP/1.1\r\nhost: 127.0.0.1:8080\r\nx-api-key: sk-test-key\r\nanthropic-version: 2026-10-21\r\ncontent-type: application/json\r\ncontent-length: 7\r\nconnection: close\r\n\r\n{\"x\":1}"
        );
        assert_eq!(a.written, Written::Complete);
        assert_eq!(a.failure, None);
        let r = a.reply.as_ref().unwrap();
        assert_eq!(
            (r.status, r.body.as_slice(), &r.end),
            (200, &b"{}"[..], &BodyEnd::Complete)
        );
        assert_eq!(a.request_id(), Some("req_1"));
        assert_eq!(a.body_bytes, 7);
        assert_eq!(a.timeout_seconds(), 5);
        assert!(util::is_utc_ms(&a.started_at_utc()));
        assert!(a.ended_at >= a.started_at);
    }

    #[test]
    fn eof_before_a_status_line_after_writing() {
        let a = over_pair(&plain(), b"{}", &AbortHandle::new(), BODY_LIMIT, |mut s| {
            read_request(&mut s);
        });
        assert_eq!(a.written, Written::Complete);
        assert!(a.reply.is_none());
        assert!(
            matches!(&a.failure, Some(Failure::Broken(m)) if m.contains("before a status line"))
        );
    }

    #[test]
    fn a_peer_gone_before_any_byte_writes_nothing() {
        let (a, b) = UnixStream::pair().unwrap();
        drop(b);
        let c = plain();
        let t0 = Instant::now();
        let mut p = Progress::default();
        let ctl = a.try_clone().unwrap();
        c.exchange_on(
            a,
            Arc::new(ctl),
            t0 + c.timeout,
            b"{}",
            &AbortHandle::new(),
            &mut || Ok(()),
            BODY_LIMIT,
            &mut p,
        );
        let a = c.finish(SystemTime::now(), t0, 2, p);
        assert_eq!(a.written, Written::None);
        assert!(a.reply.is_none());
        assert!(matches!(a.failure, Some(Failure::Broken(_))));
    }

    #[test]
    fn a_partial_write_then_an_early_answer() {
        // The far end reads a little, answers 413 and closes: the writer
        // fails partway and the answer is still read.
        let body = vec![b'x'; 8 * 1024 * 1024];
        let a = over_pair(&plain(), &body, &AbortHandle::new(), BODY_LIMIT, |mut s| {
            let mut first = [0u8; 4096];
            s.read_exact(&mut first).unwrap();
            s.write_all(b"HTTP/1.1 413 Request Entity Too Large\r\ncontent-length: 32\r\n\r\n{\"type\":\"error\",\"error\":{\"x\":1}}")
                .unwrap();
            let _ = s.shutdown(Shutdown::Both);
        });
        assert_eq!(a.written, Written::Partial);
        assert_eq!(a.status(), Some(413));
        assert_eq!(a.reply.as_ref().unwrap().end, BodyEnd::Complete);
    }

    #[test]
    fn a_partial_write_without_an_answer() {
        let body = vec![b'x'; 8 * 1024 * 1024];
        let a = over_pair(&plain(), &body, &AbortHandle::new(), BODY_LIMIT, |mut s| {
            let mut first = [0u8; 4096];
            s.read_exact(&mut first).unwrap();
        });
        assert_eq!(a.written, Written::Partial);
        assert!(a.reply.is_none());
        assert!(
            matches!(&a.failure, Some(Failure::Broken(m)) if m.contains("writing the request"))
        );
    }

    #[test]
    fn timeout_waiting_for_the_response() {
        let c = client("http://127.0.0.1:8080", None, Duration::from_millis(300));
        let a = over_pair(&c, b"{}", &AbortHandle::new(), BODY_LIMIT, |mut s| {
            read_request(&mut s);
            until_closed(&mut s);
        });
        assert_eq!(a.failure, Some(Failure::Timeout));
        assert_eq!(a.written, Written::Complete);
        assert!(a.elapsed >= Duration::from_millis(300));
        assert!(a.elapsed < Duration::from_secs(4), "{:?}", a.elapsed);
        assert!(a.failure_text().unwrap().contains("timeout"));
    }

    #[test]
    fn timeout_in_the_middle_of_a_body_keeps_what_arrived() {
        let c = client("http://127.0.0.1:8080", None, Duration::from_millis(300));
        let a = over_pair(&c, b"{}", &AbortHandle::new(), BODY_LIMIT, |mut s| {
            read_request(&mut s);
            s.write_all(b"HTTP/1.1 200 OK\r\ncontent-length: 100\r\n\r\n{\"partial\"")
                .unwrap();
            until_closed(&mut s);
        });
        assert_eq!(a.failure, Some(Failure::Timeout));
        let r = a.reply.unwrap();
        assert_eq!(
            (r.body.as_slice(), r.end),
            (&b"{\"partial\""[..], BodyEnd::CutOff)
        );
    }

    #[test]
    fn abort_from_another_thread_shuts_the_socket_down() {
        let abort = AbortHandle::new();
        let firing = abort.clone();
        let a = over_pair(&plain(), b"{}", &abort, BODY_LIMIT, move |mut s| {
            read_request(&mut s);
            thread::sleep(Duration::from_millis(100));
            firing.abort(StopCause::Close);
            until_closed(&mut s);
        });
        assert_eq!(a.failure, Some(Failure::Aborted(StopCause::Close)));
        assert_eq!(a.written, Written::Complete);
        assert!(a.elapsed < Duration::from_secs(4), "{:?}", a.elapsed);
        // The first cause stays; later attempts end at once without connecting.
        abort.abort(StopCause::Signal);
        assert_eq!(abort.cause(), Some(StopCause::Close));
        let touched = Arc::new(AtomicBool::new(false));
        let t = Arc::clone(&touched);
        let a = over_pair(&plain(), b"{}", &abort, BODY_LIMIT, move |mut s| {
            let mut b = [0u8; 1];
            if s.read(&mut b).unwrap_or(0) > 0 {
                t.store(true, Ordering::SeqCst);
            }
        });
        assert_eq!(a.failure, Some(Failure::Aborted(StopCause::Close)));
        assert_eq!(a.written, Written::None);
        assert!(!touched.load(Ordering::SeqCst));
    }

    #[test]
    fn abort_while_the_body_arrives() {
        let abort = AbortHandle::new();
        let firing = abort.clone();
        let a = over_pair(&plain(), b"{}", &abort, BODY_LIMIT, move |mut s| {
            read_request(&mut s);
            s.write_all(b"HTTP/1.1 200 OK\r\n\r\n{\"so far\"").unwrap();
            thread::sleep(Duration::from_millis(100));
            firing.abort(StopCause::Signal);
            thread::sleep(Duration::from_millis(100));
        });
        // Even a close-delimited body is not complete when the stop path ended it.
        assert_eq!(a.failure, Some(Failure::Aborted(StopCause::Signal)));
        assert_eq!(a.reply.unwrap().end, BodyEnd::CutOff);
    }

    #[test]
    fn sleep_returns_early_when_aborted() {
        let abort = AbortHandle::new();
        assert_eq!(abort.sleep(Duration::from_millis(20)), None);
        let firing = abort.clone();
        let t = thread::spawn(move || {
            thread::sleep(Duration::from_millis(50));
            firing.abort(StopCause::Signal);
        });
        let t0 = Instant::now();
        assert_eq!(
            abort.sleep(Duration::from_secs(30)),
            Some(StopCause::Signal)
        );
        assert!(t0.elapsed() < Duration::from_secs(5));
        t.join().unwrap();
        assert_eq!(
            abort.sleep(Duration::from_secs(30)),
            Some(StopCause::Signal)
        );
    }

    #[test]
    fn the_hook_runs_after_the_request_and_its_error_fails_the_attempt() {
        let (a, b) = UnixStream::pair().unwrap();
        let far = thread::spawn(move || {
            let mut b = b;
            read_request(&mut b);
            let _ = b.write_all(OK);
        });
        let c = plain();
        let mut p = Progress::default();
        let ctl = a.try_clone().unwrap();
        let mut calls = 0;
        c.exchange_on(
            a,
            Arc::new(ctl),
            Instant::now() + c.timeout,
            b"{}",
            &AbortHandle::new(),
            &mut || {
                calls += 1;
                Err(io::Error::from_raw_os_error(libc::EIO))
            },
            BODY_LIMIT,
            &mut p,
        );
        far.join().unwrap();
        assert_eq!(calls, 1);
        assert!(p.flushed);
        assert!(p.reply.is_none());
        assert!(matches!(&p.failure, Some(Failure::Broken(m)) if m.contains("EIO")));
    }

    /// Serve one TLS exchange on `s` with the test leaf certificate.
    fn tls_server(s: UnixStream, reply: &'static [u8]) -> Option<String> {
        let conn = rustls::ServerConnection::new(server_config()).unwrap();
        let mut tls = StreamOwned::new(conn, s);
        let req = read_request(&mut tls);
        let sni = tls.conn.server_name().map(str::to_string);
        if !req.is_empty() {
            tls.write_all(reply).unwrap();
            tls.conn.send_close_notify();
            let _ = tls.flush();
        }
        sni
    }

    #[test]
    fn tls_end_to_end_with_sni_for_names() {
        let c = client("https://localhost:9443", None, Duration::from_secs(10));
        let (tx, rx) = mpsc::channel();
        let a = over_pair(
            &c,
            b"{\"q\":1}",
            &AbortHandle::new(),
            BODY_LIMIT,
            move |s| {
                tx.send(tls_server(s, OK)).unwrap();
            },
        );
        assert_eq!(a.failure, None, "{:?}", a.failure_text());
        assert_eq!(a.written, Written::Complete);
        assert_eq!(a.status(), Some(200));
        assert_eq!(rx.recv().unwrap().as_deref(), Some("localhost"));
    }

    #[test]
    fn tls_to_an_address_sends_no_sni() {
        let c = client("https://127.0.0.1:9443", None, Duration::from_secs(10));
        let (tx, rx) = mpsc::channel();
        let a = over_pair(&c, b"{}", &AbortHandle::new(), BODY_LIMIT, move |s| {
            tx.send(tls_server(s, OK)).unwrap();
        });
        assert_eq!(a.status(), Some(200), "{:?}", a.failure_text());
        assert_eq!(rx.recv().unwrap(), None);
    }

    #[test]
    fn tls_refuses_an_untrusted_or_misnamed_certificate() {
        // The release roots do not include the test CA.
        let route = Route::new(Endpoint::parse("https://localhost:9443").unwrap(), None);
        let c = Client::new(
            route,
            Tls::web_pki().unwrap(),
            "k",
            "v",
            Duration::from_secs(10),
        )
        .unwrap();
        let a = over_pair(&c, b"{}", &AbortHandle::new(), BODY_LIMIT, |s| {
            let conn = rustls::ServerConnection::new(server_config()).unwrap();
            let mut tls = StreamOwned::new(conn, s);
            let mut b = [0u8; 1];
            let _ = tls.read(&mut b);
        });
        assert_eq!(a.written, Written::None);
        assert!(a.reply.is_none());
        let m = a.failure_text().unwrap();
        assert!(m.contains("handshake") && m.contains("certificate"), "{m}");

        // Trusted CA, but the certificate does not name this host.
        let c = client("https://other.provider.test", None, Duration::from_secs(10));
        let a = over_pair(&c, b"{}", &AbortHandle::new(), BODY_LIMIT, |s| {
            let conn = rustls::ServerConnection::new(server_config()).unwrap();
            let mut tls = StreamOwned::new(conn, s);
            let mut b = [0u8; 1];
            let _ = tls.read(&mut b);
        });
        assert_eq!(a.written, Written::None);
        let m = a.failure_text().unwrap();
        assert!(m.contains("certificate"), "{m}");
    }

    #[test]
    fn tls_peer_that_is_not_tls() {
        let c = client("https://localhost:9443", None, Duration::from_secs(10));
        let a = over_pair(&c, b"{}", &AbortHandle::new(), BODY_LIMIT, |mut s| {
            let mut b = [0u8; 16];
            let _ = s.read(&mut b);
            let _ = s.write_all(b"HTTP/1.1 400 Bad Request\r\n\r\n");
        });
        assert_eq!(a.written, Written::None);
        assert!(a.reply.is_none());
        assert!(a.failure_text().unwrap().contains("handshake"));
    }

    /// Accept a CONNECT, check its exact bytes, answer `status`, and when it
    /// is 200 serve TLS inside the tunnel.
    fn proxy_server(mut s: UnixStream, status: &'static str, seen: mpsc::Sender<Vec<u8>>) {
        let mut head = Vec::new();
        let mut b = [0u8; 1];
        while !head.ends_with(b"\r\n\r\n") {
            if s.read(&mut b).unwrap() == 0 {
                return;
            }
            head.push(b[0]);
        }
        seen.send(head).unwrap();
        s.write_all(format!("HTTP/1.1 {status}\r\nx-proxy: yes\r\n\r\n").as_bytes())
            .unwrap();
        if status.starts_with("200") {
            tls_server(s, OK);
        }
    }

    #[test]
    fn connect_tunnel_carries_tls_end_to_end() {
        let c = client(
            "https://api.provider.test",
            Some("http://127.0.0.1:3128"),
            Duration::from_secs(10),
        );
        assert_eq!(c.route().proxy_value(), Some("http://127.0.0.1:3128"));
        let (tx, rx) = mpsc::channel();
        let a = over_pair(
            &c,
            b"{\"secret\":\"k\"}",
            &AbortHandle::new(),
            BODY_LIMIT,
            move |s| proxy_server(s, "200 Connection established", tx),
        );
        assert_eq!(
            rx.recv().unwrap(),
            b"CONNECT api.provider.test:443 HTTP/1.1\r\nhost: api.provider.test:443\r\n\r\n"
        );
        assert_eq!(a.failure, None, "{:?}", a.failure_text());
        assert_eq!(a.status(), Some(200));
        assert_eq!(a.written, Written::Complete);
    }

    #[test]
    fn connect_refusals_are_connection_failures() {
        let c = client(
            "https://api.provider.test:8443",
            Some("http://proxy.internal:3128/"),
            Duration::from_secs(10),
        );
        let (tx, rx) = mpsc::channel();
        let a = over_pair(&c, b"{}", &AbortHandle::new(), BODY_LIMIT, move |s| {
            proxy_server(s, "407 Proxy Authentication Required", tx)
        });
        assert_eq!(
            rx.recv().unwrap(),
            b"CONNECT api.provider.test:8443 HTTP/1.1\r\nhost: api.provider.test:8443\r\n\r\n"
        );
        assert_eq!(a.written, Written::None);
        assert!(a.reply.is_none());
        let m = a.failure_text().unwrap();
        assert!(m.contains("407"), "{m}");

        let a = over_pair(&c, b"{}", &AbortHandle::new(), BODY_LIMIT, |mut s| {
            let mut b = [0u8; 8];
            let _ = s.read(&mut b);
            let _ = s.write_all(b"SSH-2.0-x\r\n\r\n");
        });
        assert_eq!(a.written, Written::None);
        assert!(a.failure_text().unwrap().contains("status line"));

        let a = over_pair(&c, b"{}", &AbortHandle::new(), BODY_LIMIT, |mut s| {
            let mut b = [0u8; 8];
            let _ = s.read(&mut b);
        });
        assert_eq!(a.written, Written::None);
        assert!(
            a.failure_text()
                .unwrap()
                .contains("before answering CONNECT")
        );
    }

    #[test]
    fn client_checks_its_header_values() {
        let route = Route::new(Endpoint::default_base(), None);
        let t = Tls::web_pki().unwrap();
        assert!(Client::new(route.clone(), t.clone(), "", "v", REQUEST_TIMEOUT).is_err());
        assert!(Client::new(route.clone(), t.clone(), "a b", "v", REQUEST_TIMEOUT).is_err());
        assert!(Client::new(route.clone(), t.clone(), "k\r\nx: y", "v", REQUEST_TIMEOUT).is_err());
        assert!(Client::new(route.clone(), t.clone(), "k", "", REQUEST_TIMEOUT).is_err());
        assert!(Client::new(route.clone(), t.clone(), "k", "v", Duration::ZERO).is_err());
        assert!(Client::new(route, t, "k", "v", REQUEST_TIMEOUT).is_ok());
        assert_eq!(REQUEST_TIMEOUT, Duration::from_secs(600));
    }

    #[cfg(feature = "fault-injection")]
    #[test]
    fn test_timeout_values() {
        assert_eq!(parse_test_timeout("1").unwrap(), Duration::from_secs(1));
        assert_eq!(parse_test_timeout("600").unwrap(), Duration::from_secs(600));
        for bad in ["0", "601", "", "-1", "1.5", " 5", "0005"] {
            assert!(parse_test_timeout(bad).is_err(), "{bad}");
        }
    }

    /// Bind a loopback listener, or `None` when this environment forbids it
    /// (some sandboxes deny `bind` with EPERM). Tests that need a real
    /// listener skip then, saying so.
    pub fn listener(test: &str) -> Option<std::net::TcpListener> {
        match std::net::TcpListener::bind("127.0.0.1:0") {
            Ok(l) => Some(l),
            Err(e) if e.kind() == io::ErrorKind::PermissionDenied => {
                eprintln!(
                    "SKIPPED {test}: binding a loopback listener is not permitted here ({e})"
                );
                None
            }
            Err(e) => panic!("binding a loopback listener failed: {e}"),
        }
    }

    #[test]
    fn real_connection_to_a_loopback_listener() {
        let Some(l) = listener("real_connection_to_a_loopback_listener") else {
            return;
        };
        let port = l.local_addr().unwrap().port();
        let far = thread::spawn(move || {
            for _ in 0..2 {
                let (mut s, _) = l.accept().unwrap();
                read_request(&mut s);
                s.write_all(OK).unwrap();
            }
        });
        // An address, and `localhost` without the resolver.
        for base in [
            format!("http://127.0.0.1:{port}"),
            format!("http://localhost:{port}"),
        ] {
            let a = client(&base, None, Duration::from_secs(10)).send(
                b"{}",
                &AbortHandle::new(),
                &mut || Ok(()),
            );
            assert_eq!(a.status(), Some(200), "{base}: {:?}", a.failure_text());
            assert_eq!(a.written, Written::Complete);
        }
        far.join().unwrap();
    }

    #[test]
    fn real_tls_through_a_real_proxy() {
        let Some(l) = listener("real_tls_through_a_real_proxy") else {
            return;
        };
        let port = l.local_addr().unwrap().port();
        let (tx, rx) = mpsc::channel();
        let far = thread::spawn(move || {
            let (s, _) = l.accept().unwrap();
            let s = unix_bridge(s);
            proxy_server(s, "200 OK", tx);
        });
        let c = client(
            "https://api.provider.test",
            Some(&format!("http://127.0.0.1:{port}")),
            Duration::from_secs(10),
        );
        let a = c.send(b"{}", &AbortHandle::new(), &mut || Ok(()));
        assert_eq!(a.status(), Some(200), "{:?}", a.failure_text());
        assert!(
            rx.recv()
                .unwrap()
                .starts_with(b"CONNECT api.provider.test:443 ")
        );
        far.join().unwrap();
    }

    /// Relay a TCP stream through a socket pair so that the socket-pair
    /// servers above can serve real connections.
    fn unix_bridge(tcp: TcpStream) -> UnixStream {
        let (a, b) = UnixStream::pair().unwrap();
        let (mut t1, mut t2) = (tcp.try_clone().unwrap(), tcp);
        let (mut a1, mut a2) = (a.try_clone().unwrap(), a);
        thread::spawn(move || {
            let _ = io::copy(&mut t1, &mut a1);
            let _ = a1.shutdown(Shutdown::Write);
        });
        thread::spawn(move || {
            let _ = io::copy(&mut a2, &mut t2);
            let _ = t2.shutdown(Shutdown::Write);
        });
        b
    }

    /// A dialer that blocks like a resolver or a connect that never answers.
    fn hanging_dialer() -> Result<TcpStream, Stop> {
        thread::sleep(Duration::from_secs(3));
        Err(Stop::Broken("late".into()))
    }

    #[test]
    fn abort_while_connecting_returns_at_once() {
        let abort = AbortHandle::new();
        let firing = abort.clone();
        let t = thread::spawn(move || {
            thread::sleep(Duration::from_millis(100));
            firing.abort(StopCause::Close);
        });
        let t0 = Instant::now();
        let r = wait_for(hanging_dialer, t0 + Duration::from_secs(30), &abort);
        t.join().unwrap();
        assert_eq!(r.unwrap_err(), Stop::Aborted(StopCause::Close));
        assert!(t0.elapsed() < Duration::from_secs(2), "{:?}", t0.elapsed());
    }

    #[test]
    fn the_deadline_bounds_connecting() {
        let t0 = Instant::now();
        let r = wait_for(
            hanging_dialer,
            t0 + Duration::from_millis(200),
            &AbortHandle::new(),
        );
        assert_eq!(r.unwrap_err(), Stop::Timeout);
        assert!(t0.elapsed() < Duration::from_secs(2), "{:?}", t0.elapsed());
        let r = wait_for(
            || Err(Stop::Broken("refused".into())),
            Instant::now() + Duration::from_secs(5),
            &AbortHandle::new(),
        );
        assert_eq!(r.unwrap_err(), Stop::Broken("refused".into()));
    }

    #[test]
    fn an_aborted_handle_never_connects() {
        let Some(l) = listener("an_aborted_handle_never_connects") else {
            return;
        };
        let port = l.local_addr().unwrap().port();
        let abort = AbortHandle::new();
        abort.abort(StopCause::Signal);
        let c = client(
            &format!("http://127.0.0.1:{port}"),
            None,
            Duration::from_secs(5),
        );
        let a = c.send(b"{}", &abort, &mut || Ok(()));
        assert_eq!(a.failure, Some(Failure::Aborted(StopCause::Signal)));
        assert_eq!(a.written, Written::None);
        // Nothing reached the listener.
        l.set_nonblocking(true).unwrap();
        assert_eq!(l.accept().unwrap_err().kind(), io::ErrorKind::WouldBlock);
    }
}
