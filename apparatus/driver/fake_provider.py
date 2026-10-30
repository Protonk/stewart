# -*- coding: utf-8 -*-
"""Fake Anthropic Messages API for Stewart's scripted acceptance tier.

Standard library only, offline. The binary reaches it through
STEWART_PROVIDER_URL (INTERFACE 6.1): plain HTTP/1.1 on a loopback port, or
HTTPS with the test-only CA in testdata/tls (passed to the test build as
STEWART_TEST_TLS_ROOT), directly or through the small CONNECT proxy below
(HTTPS_PROXY), which maps `provider.test` to the local TLS server so no DNS is
involved. Nothing here contacts a real network service.

What it is for (ACCEPTANCE "The scripted tier"):

- It records every request byte for byte, with arrival times, transport and
  TLS server name: the witness of what the auditor was sent. Records are kept
  in memory (`FakeProvider.exchanges`) and, when a record folder is given,
  written to disk as each exchange completes, outside every archive.
- It answers each attempt with the next scripted `Step`: a message (tool calls,
  text, thinking blocks with signatures, a compaction block, unknown blocks,
  any stop reason, any usage, any framing), an HTTP error (429/529/500 with and
  without retry-after, 400/401/413 bodies), a dropped connection, a stalled
  response or raw bytes. A responder can also be a callable, such as the
  reacting auditor, choosing each answer from the request it received.
- It keeps the charge each attempt should add to the allowances under
  INTERFACE 6.4 (`Exchange.charge`), so the driver can compute run_ended usage
  and status allowances without reading Stewart's records.

Each connection carries one exchange; Stewart sends `connection: close`
(6.1) and the fake closes after answering. `handle_connection` serves an
already-connected socket, so self-tests can also drive it over socketpair()
where listening on loopback is not permitted.

Network discipline, enforced here rather than left to habit:

- Every listener binds explicitly to 127.0.0.1 with port 0 (`Listener` takes
  no address); never 0.0.0.0, ::, or a host name.
- The driver connects only to ports its own listeners opened in this process
  and still hold (`OWN_PORTS`). `own_connect` refuses anything else before any
  connection is attempted; the CONNECT proxy's routes must name such ports and
  it connects only through `own_connect`. Nothing scans, probes or connects to
  another local port or service.
- The binary under test is only ever given provider URLs and proxies naming
  these ports, or `provider.test` behind the proxy. A case that lets the binary
  try to resolve `provider.test` itself (no proxy) runs only when the driver
  is told the run is network-isolated (the container suite's --network none).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import select
import socket
import ssl
import threading
import time
import traceback

import rawjson
from rawjson import compact
from driver_core import API_VERSION, selftest

TLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "tls")
LOOPBACK = "127.0.0.1"
# Ports opened by this process's listeners and still held: the only ports the driver connects to.
OWN_PORTS = set()
_OWN_LOCK = threading.Lock()


class NotOwnPort(PermissionError):
    """A connection to something other than this run's own loopback listener was refused."""


def own_connect(addr, timeout=10):
    """Connect to (127.0.0.1, port) only when port is one of this process's listeners."""
    host, port = addr
    with _OWN_LOCK:
        ok = host == LOOPBACK and isinstance(port, int) and port in OWN_PORTS
    if not ok:
        raise NotOwnPort("refusing to connect to %r: only this run's own 127.0.0.1 listeners" % (addr,))
    return socket.create_connection((LOOPBACK, port), timeout=timeout)
# The request header names INTERFACE 6.1 lists, in its order. "No other header is sent."
REQUEST_HEADER_NAMES = ("host", "x-api-key", "anthropic-version", "content-type", "content-length",
                        "connection")
ABSENT = object()
REASONS = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
           408: "Request Timeout", 413: "Payload Too Large", 429: "Too Many Requests",
           500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable",
           504: "Gateway Timeout", 529: "Overloaded"}
ERROR_TYPES = {400: "invalid_request_error", 401: "authentication_error", 403: "permission_error",
               404: "not_found_error", 413: "request_too_large", 429: "rate_limit_error", 500: "api_error",
               529: "overloaded_error"}


def tls_file(name):
    """Path of a test-only TLS fixture, e.g. tls_file('ca.pem')."""
    return os.path.join(TLS_DIR, "testonly-" + name)


class LoopbackUnavailable(RuntimeError):
    """Listening on 127.0.0.1 is not permitted here (cases skip with this reason)."""


def jstr(s):
    return json.dumps(s, ensure_ascii=False).encode("utf-8")


def now():
    return time.perf_counter()


def utc_ms():
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % int((t % 1) * 1000)


# ---------------------------------------------------------------------------
# Content blocks. Each keeps its exact bytes: Stewart must echo them unchanged
# (6.2) and capture each tool_use block exactly (4.5 "Call capture").
# ---------------------------------------------------------------------------

class Block:
    def __init__(self, raw, kind, **meta):
        self.raw, self.kind, self.meta = raw, kind, meta

    def __repr__(self):
        return "Block(%s, %d bytes)" % (self.kind, len(self.raw))


def text(s):
    return Block(b'{"type":"text","text":' + jstr(s) + b"}", "text", text=s)


def tool_use(tid, name, input=None, raw_input=None, raw=None):
    """A tool_use block. raw_input gives the exact input bytes (duplicate keys, spacing);
    raw gives the whole block (a missing or non-string id or name)."""
    if raw is not None:
        return Block(raw, "tool_use", id=tid, name=name, raw_input=raw_input, input=input)
    if raw_input is None:
        raw_input = compact(input if input is not None else {})
    blk = (b'{"type":"tool_use","id":' + jstr(tid) + b',"name":' + jstr(name) + b',"input":'
           + raw_input + b"}")
    return Block(blk, "tool_use", id=tid, name=name, raw_input=raw_input, input=input)


def thinking(thought, signature):
    return Block(b'{"type":"thinking","thinking":' + jstr(thought) + b',"signature":' + jstr(signature) + b"}",
                 "thinking")


def redacted_thinking(data):
    return Block(b'{"type":"redacted_thinking","data":' + jstr(data) + b"}", "redacted_thinking")


def compaction(content):
    """A provider compaction block. Stewart enables no context management (6.2), so for it
    this is a block of a kind it does not interpret, echoed in history like any other."""
    return Block(b'{"type":"compaction","content":' + jstr(content) + b"}", "compaction")


def unknown_block(type_, **fields):
    d = {"type": type_}
    d.update(fields)
    return Block(compact(d), "unknown")


class Usage:
    """Reported usage. cache counts may be ABSENT (member left out) or None (null)."""

    def __init__(self, input_tokens, output_tokens, cache_creation=ABSENT, cache_read=ABSENT):
        self.input, self.output = input_tokens, output_tokens
        self.cache_creation, self.cache_read = cache_creation, cache_read

    def raw(self):
        parts = [b'"input_tokens":%d' % self.input]
        for name, v in (("cache_creation_input_tokens", self.cache_creation),
                        ("cache_read_input_tokens", self.cache_read)):
            if v is ABSENT:
                continue
            parts.append(b'"' + name.encode() + b'":' + (b"null" if v is None else str(v).encode()))
        parts.append(b'"output_tokens":%d' % self.output)
        return b"{" + b",".join(parts) + b"}"

    def charged_input(self):
        """input_tokens + cache_creation + cache_read, absent or null counted 0 (6.4)."""
        extra = 0
        for v in (self.cache_creation, self.cache_read):
            if v is not ABSENT and v is not None:
                extra += v
        return self.input + extra

    def describe(self):
        def show(v):
            return "absent" if v is ABSENT else v
        return {"input_tokens": self.input, "output_tokens": self.output,
                "cache_creation_input_tokens": show(self.cache_creation),
                "cache_read_input_tokens": show(self.cache_read)}


# ---------------------------------------------------------------------------
# Steps: the answer to one attempt.
# ---------------------------------------------------------------------------

def charge_of(basis, ex, usage=None):
    """The charge INTERFACE 6.4 assigns to an attempt with this basis."""
    if basis == "reported":
        return {"basis": "reported", "turns": 1, "input_tokens": usage.charged_input(),
                "output_tokens": usage.output}
    if basis == "estimated":
        mt = ex.max_tokens()
        return {"basis": "estimated", "turns": 1,
                "input_tokens": int(math.ceil(len(ex.body) / 3.0)) if ex.body is not None else None,
                "output_tokens": mt}
    return {"basis": "none", "turns": 0, "input_tokens": 0, "output_tokens": 0}


def _framed(status, headers, body, framing="length", chunk=None):
    """Status line, headers and body with the given framing: 'length' (content-length),
    'chunked' (transfer-encoding: chunked) or 'close' (delimited by closing)."""
    lines = [b"HTTP/1.1 %d %s" % (status, REASONS.get(status, "Status").encode())]
    lines += [n.encode("latin-1") + b": " + v.encode("latin-1") for n, v in headers]
    if framing == "length":
        lines.append(b"content-length: %d" % len(body))
        payload = body
    elif framing == "chunked":
        lines.append(b"transfer-encoding: chunked")
        size = chunk or max(1, (len(body) + 2) // 3)
        payload = b""
        for i in range(0, len(body), size):
            piece = body[i:i + size]
            payload += b"%x\r\n" % len(piece) + piece + b"\r\n"
        payload += b"0\r\n\r\n"
    elif framing == "close":
        payload = body
    else:
        raise ValueError(framing)
    lines.append(b"connection: close")
    return b"\r\n".join(lines) + b"\r\n\r\n", payload


class Step:
    kind = "step"

    def describe(self):
        return {"kind": self.kind}

    def charge(self, ex):
        return charge_of("none", ex)

    def serve(self, sock, ex, provider):
        raise NotImplementedError


class Message(Step):
    """An HTTP 200 message. body= replaces the whole body (an undecodable or unusual
    message); charge= then states what Stewart should charge ('reported', 'estimated',
    'none' or a dict), defaulting to 'estimated' (6.4: response_undecodable)."""
    kind = "message"

    def __init__(self, content=(), stop_reason="end_turn", usage=None, model="claude-opus-5-5",
                 msg_id=None, framing="length", chunk=None, headers=(), body=None, charge=None,
                 delay=0.0, stop_sequence=None, extra=b"", content_encoding=None, label=None):
        self.content = list(content)
        self.stop_reason, self.model, self.msg_id = stop_reason, model, msg_id
        self.usage = usage if usage is not None else Usage(1000, 50)
        self.framing, self.chunk, self.headers = framing, chunk, list(headers)
        self.body_override, self.charge_override = body, charge
        self.delay, self.stop_sequence, self.extra = delay, stop_sequence, extra
        self.content_encoding, self.label = content_encoding, label
        self.content_raw = b"[" + b",".join(b.raw for b in self.content) + b"]"

    def tool_uses(self):
        return [b for b in self.content if b.kind == "tool_use"]

    def body(self, ex):
        if self.body_override is not None:
            return self.body_override
        mid = self.msg_id or "msg_fake_%04d" % ex.n
        return (b'{"id":' + jstr(mid) + b',"type":"message","role":"assistant","model":' + jstr(self.model)
                + b',"content":' + self.content_raw
                + b',"stop_reason":' + (jstr(self.stop_reason) if self.stop_reason is not None else b"null")
                + b',"stop_sequence":' + (jstr(self.stop_sequence) if self.stop_sequence is not None else b"null")
                + b',"stop_details":null,"usage":' + self.usage.raw() + self.extra + b"}")

    def describe(self):
        return {"kind": self.kind, "stop_reason": self.stop_reason, "framing": self.framing,
                "blocks": [b.kind for b in self.content], "label": self.label,
                "tool_uses": [{"id": b.meta.get("id"), "name": b.meta.get("name")} for b in self.tool_uses()],
                "usage": self.usage.describe() if self.body_override is None else None,
                "body_override": self.body_override is not None}

    def charge(self, ex):
        c = self.charge_override
        if isinstance(c, dict):
            return c
        if c is None:
            c = "estimated" if (self.body_override is not None or self.content_encoding) else "reported"
        return charge_of(c, ex, self.usage)

    def headers_for(self, ex):
        hs = [("content-type", "application/json"), ("request-id", "req_fake_%04d" % ex.n)]
        if self.content_encoding:
            hs.append(("content-encoding", self.content_encoding))
        return hs + self.headers

    def framed(self, ex, framing=None):
        return _framed(200, self.headers_for(ex), self.body(ex), framing or self.framing, self.chunk)

    def serve(self, sock, ex, provider):
        if self.delay:
            provider.wait(self.delay)
        ex.content_raw = self.content_raw if self.body_override is None else None
        head, payload = self.framed(ex)
        provider.send(sock, ex, head + payload)


class HttpError(Step):
    """A non-200 answer with an error body {"type":"error","error":{...},"request_id":...}."""
    kind = "http_error"

    def __init__(self, status, error_type=None, message=None, retry_after=None, headers=(), body=None,
                 framing="length", request_id_header=True, delay=0.0):
        self.status = status
        self.error_type = error_type or ERROR_TYPES.get(status, "api_error")
        self.message = message or REASONS.get(status, "Error")
        if isinstance(retry_after, (list, tuple)):
            self.retry_after = list(retry_after)
        else:
            self.retry_after = [] if retry_after is None else [str(retry_after)]
        self.headers, self.body_override, self.framing = list(headers), body, framing
        self.request_id_header, self.delay = request_id_header, delay

    def body(self, ex):
        if self.body_override is not None:
            return self.body_override
        return (b'{"type":"error","error":{"type":' + jstr(self.error_type) + b',"message":' + jstr(self.message)
                + b'},"request_id":' + jstr("req_fake_%04d" % ex.n) + b"}")

    def describe(self):
        return {"kind": self.kind, "status": self.status, "error_type": self.error_type,
                "retry_after": self.retry_after, "framing": self.framing}

    def framed(self, ex, framing=None):
        hs = [("content-type", "application/json")]
        if self.request_id_header:
            hs.append(("request-id", "req_fake_%04d" % ex.n))
        hs += [("retry-after", v) for v in self.retry_after] + self.headers
        return _framed(self.status, hs, self.body(ex), framing or self.framing)

    def serve(self, sock, ex, provider):
        if self.delay:
            provider.wait(self.delay)
        head, payload = self.framed(ex)
        provider.send(sock, ex, head + payload)


class Drop(Step):
    """Close the connection after the request: 'before_response' (no status line),
    'after_status' (status line only) or 'mid_body' (headers announcing the whole body of
    `message`, then half of it). Request bytes were written. Under 6.6 as amended, a cut-off
    200 is connection_lost (retried, charged an estimate, 6.4); a cut-off answer with another
    status is http_error (charged nothing), so `message` may also be an HttpError."""
    kind = "drop"

    def __init__(self, when="before_response", message=None, reset=False):
        assert when in ("before_response", "after_status", "mid_body")
        self.when, self.message, self.reset = when, message or Message([text("cut")]), reset

    def describe(self):
        return {"kind": self.kind, "when": self.when, "reset": self.reset,
                "status": getattr(self.message, "status", 200)}

    def charge(self, ex):
        if self.when == "mid_body" and isinstance(self.message, HttpError):
            return charge_of("none", ex)
        return charge_of("estimated", ex)

    def serve(self, sock, ex, provider):
        if self.when == "after_status":
            provider.send(sock, ex, b"HTTP/1.1 200 OK\r\n")
        elif self.when == "mid_body":
            head, payload = self.message.framed(ex, "length")
            provider.send(sock, ex, head + payload[:max(1, len(payload) // 2)])
        if self.reset:
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\x00\x00\x00\x00\x00\x00\x00")
            except OSError:
                pass
        ex.outcome = "dropped_" + self.when


class Stall(Step):
    """Hold the connection after the request (after sending `prefix`, if any) until the
    client closes, `seconds` pass or the provider stops; then close without answering.
    With STEWART_TEST_PROVIDER_TIMEOUT the client times out first (6.6 'timeout')."""
    kind = "stall"

    def __init__(self, seconds=30.0, prefix=b""):
        self.seconds, self.prefix = seconds, prefix

    def describe(self):
        return {"kind": self.kind, "seconds": self.seconds, "prefix_bytes": len(self.prefix)}

    def charge(self, ex):
        return charge_of("estimated", ex)

    def serve(self, sock, ex, provider):
        if self.prefix:
            provider.send(sock, ex, self.prefix)
        deadline = now() + self.seconds
        ex.outcome = "stalled"
        while now() < deadline and not provider.stopping.is_set():
            try:
                r, _, _ = select.select([sock], [], [], 0.05)
            except (OSError, ValueError):
                break
            if r:
                try:
                    data = sock.recv(65536)
                except (OSError, ssl.SSLError):
                    data = b""
                if not data:
                    ex.t_client_closed = now()
                    ex.outcome = "stalled_client_closed"
                    return


class Raw(Step):
    """Exact bytes, then close. charge states the expected 6.4 charge."""
    kind = "raw"

    def __init__(self, data, charge="none"):
        self.data, self.charge_basis = data, charge

    def describe(self):
        return {"kind": self.kind, "bytes": len(self.data)}

    def charge(self, ex):
        return self.charge_basis if isinstance(self.charge_basis, dict) else charge_of(self.charge_basis, ex)

    def serve(self, sock, ex, provider):
        provider.send(sock, ex, self.data)


# ---------------------------------------------------------------------------
# Responders: who chooses the step for an attempt.
# ---------------------------------------------------------------------------

class Script:
    """Steps in order, one per attempt. An item may be a Step or a callable(exchange) ->
    Step. When the list runs out, `then` answers (a callable), else the fake answers 400
    and records the exhaustion, which a case reports as a failure."""

    def __init__(self, steps=(), then=None):
        self.steps, self.then, self.used, self.exhausted = list(steps), then, 0, []

    def __call__(self, ex):
        if self.used < len(self.steps):
            s = self.steps[self.used]
            self.used += 1
            return s if isinstance(s, Step) else s(ex)
        if self.then is not None:
            return self.then(ex)
        self.exhausted.append(ex.n)
        return HttpError(400, "invalid_request_error", "fake provider: script exhausted")


class Inject:
    """Answer attempt numbers in `at` ({exchange number: Step}) with those steps and every
    other attempt with base(exchange). Lets a case put a 529 or a drop in front of the
    reacting auditor without the auditor seeing that attempt."""

    def __init__(self, base, at):
        self.base, self.at = base, dict(at)

    def __call__(self, ex):
        s = self.at.get(ex.n)
        if s is not None:
            return s if isinstance(s, Step) else s(ex)
        return self.base(ex)


# ---------------------------------------------------------------------------
# Exchanges and the server.
# ---------------------------------------------------------------------------

class Exchange:
    """One attempt as the fake saw it."""

    def __init__(self, conn, transport, sni, peer, t_accept):
        self.n = None
        self.conn, self.transport, self.sni, self.peer = conn, transport, sni, peer
        self.t_accept, self.t_first_byte = t_accept, None
        self.t_request_end = self.t_response_start = self.t_response_end = self.t_client_closed = None
        self.at = utc_ms()
        self.raw = b""
        self.request_line = None
        self.method = self.target = self.version = None
        self.headers = []          # [(name as received, value)] decoded latin-1
        self.body = None
        self.problem = None
        self.step = None
        self.step_desc = None
        self.charge = None
        self.response_raw = b""
        self.content_raw = None    # exact bytes of the response's content array, when a message
        self.outcome = None
        self.send_error = None
        self._node = None

    # -- request views --
    def header(self, name):
        return [v for n, v in self.headers if n.lower() == name]

    def body_node(self):
        if self._node is None and self.body is not None:
            self._node = rawjson.try_parse(self.body)
        return self._node

    def body_sha256(self):
        return hashlib.sha256(self.body).hexdigest() if self.body is not None else None

    def max_tokens(self):
        n = self.body_node()
        mt = n.get("max_tokens") if n is not None and n.kind == "object" else None
        try:
            return mt.value() if mt is not None else None
        except ValueError:
            return None

    def messages(self):
        n = self.body_node()
        m = n.get("messages") if n is not None and n.kind == "object" else None
        return m.items if m is not None and m.kind == "array" else None

    def tool_uses(self):
        return self.step.tool_uses() if isinstance(self.step, Message) and self.step.body_override is None else []

    def summary(self):
        return {"n": self.n, "conn": self.conn, "transport": self.transport, "sni": self.sni, "at": self.at,
                "request_line": self.request_line, "headers": self.headers,
                "request_bytes": len(self.raw), "request_sha256": hashlib.sha256(self.raw).hexdigest(),
                "body_bytes": None if self.body is None else len(self.body), "body_sha256": self.body_sha256(),
                "max_tokens": self.max_tokens(), "problem": self.problem, "step": self.step_desc,
                "charge": self.charge, "outcome": self.outcome, "send_error": self.send_error,
                "response_bytes": len(self.response_raw),
                "response_sha256": hashlib.sha256(self.response_raw).hexdigest(),
                "times": {k: getattr(self, k) for k in ("t_accept", "t_first_byte", "t_request_end",
                                                       "t_response_start", "t_response_end",
                                                       "t_client_closed")}}


def _read_request(sock, ex, limit=64 << 20, timeout=30.0):
    """Read one request (headers to CRLFCRLF, then content-length bytes) into ex."""
    sock.settimeout(timeout)
    buf = bytearray()
    end = -1
    try:
        while end < 0:
            chunk = sock.recv(65536)
            if not chunk:
                break
            if ex.t_first_byte is None:
                ex.t_first_byte = now()
            buf += chunk
            end = buf.find(b"\r\n\r\n")
            if end < 0 and len(buf) > (1 << 20):
                break
        if end < 0:
            ex.raw = bytes(buf)
            ex.problem = "connection closed before the end of the headers" if len(buf) <= (1 << 20) else "headers too long"
            return False
        head = bytes(buf[:end]).decode("latin-1")
        lines = head.split("\r\n")
        ex.request_line = lines[0]
        parts = lines[0].split(" ")
        if len(parts) == 3:
            ex.method, ex.target, ex.version = parts
        for line in lines[1:]:
            name, sep, value = line.partition(":")
            ex.headers.append([name, value.strip(" \t") if sep else None])
        cl = ex.header("content-length")
        try:
            want = int(cl[0]) if len(cl) == 1 else None
        except ValueError:
            want = None
        if want is None:
            ex.problem = "no single numeric content-length: %r" % (cl,)
            want = 0
        total = end + 4 + want
        if total > limit:
            ex.problem = "request over %d bytes" % limit
            ex.raw = bytes(buf)
            return False
        while len(buf) < total:
            chunk = sock.recv(min(1 << 20, total - len(buf)))
            if not chunk:
                break
            buf += chunk
        ex.raw = bytes(buf)
        ex.body = bytes(buf[end + 4:total])
        if len(buf) < total:
            ex.problem = "connection closed after %d of %d body bytes" % (len(buf) - end - 4, want)
            return False
        if len(buf) > total:
            ex.problem = "%d bytes after the body" % (len(buf) - total)
        return True
    except socket.timeout:
        ex.raw = bytes(buf)
        ex.problem = "timed out reading the request"
        return False
    except (OSError, ssl.SSLError) as exc:
        ex.raw = bytes(buf)
        ex.problem = "error reading the request: %s" % exc
        return False
    finally:
        ex.t_request_end = now()


class FakeProvider:
    """The fake Messages API. responder(exchange) -> Step chooses each answer."""

    def __init__(self, responder=None, record_dir=None, name="provider"):
        self.responder = responder if responder is not None else Script([])
        self.record_dir, self.name = record_dir, name
        self.exchanges = []
        self.events = []        # connection-level events: TLS failures, unreadable requests
        self.anomalies = []     # failures of the fake itself (a responder that raised, ...)
        self.lock = threading.Lock()
        self.decide = threading.Lock()
        self.stopping = threading.Event()
        self.conn_seq = 0
        self.attribution = {}   # upstream local port -> proxy tunnel id
        if record_dir:
            os.makedirs(record_dir, exist_ok=True)

    def wait(self, seconds):
        self.stopping.wait(seconds)

    def send(self, sock, ex, data):
        if ex.t_response_start is None:
            ex.t_response_start = now()
        try:
            sock.sendall(data)
            ex.response_raw += data
            ex.outcome = ex.outcome or "sent"
        except (OSError, ssl.SSLError) as exc:
            ex.send_error = str(exc)
            ex.outcome = "send_failed"

    def _event(self, ev):
        with self.lock:
            self.events.append(ev)
            self._append_jsonl("events.jsonl", ev)

    def _append_jsonl(self, name, obj):
        if self.record_dir:
            with open(os.path.join(self.record_dir, name), "a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False, default=repr) + "\n")

    def _write(self, name, data):
        if self.record_dir:
            with open(os.path.join(self.record_dir, name), "wb") as f:
                f.write(data)

    def handle_connection(self, sock, peer=None, t_accept=None, tls=None, transport="http"):
        """Serve one exchange on a connected socket. tls is a context factory (tls_server)."""
        t_accept = t_accept if t_accept is not None else now()
        with self.lock:
            self.conn_seq += 1
            conn = self.conn_seq
        sni = []
        try:
            if tls is not None:
                transport = "tls"
                try:
                    sock.settimeout(30)
                    sock = tls(sni).wrap_socket(sock, server_side=True)
                except (ssl.SSLError, OSError) as exc:
                    self._event({"conn": conn, "event": "tls_handshake_failed", "error": str(exc),
                                 "transport": transport, "sni": sni[0] if sni else None, "at": utc_ms()})
                    return None
            # The proxy registers its upstream port before relaying the client's first bytes,
            # so after the handshake a proxied connection is attributable.
            if peer is not None and isinstance(peer, tuple) and len(peer) >= 2 and peer[1] in self.attribution:
                transport = "tls-via-proxy"
            ex = Exchange(conn, transport, sni[0] if sni else None, peer, t_accept)
            complete = _read_request(sock, ex)
            if not complete and not ex.raw:
                self._event({"conn": conn, "event": "no_request", "problem": ex.problem, "transport": transport,
                             "at": utc_ms()})
                return None
            with self.decide:
                with self.lock:
                    ex.n = len(self.exchanges) + 1
                    self.exchanges.append(ex)
                self._write("%04d-request.bin" % ex.n, ex.raw)
                try:
                    step = self.responder(ex) if complete else Drop("before_response")
                except Exception:
                    self.anomalies.append({"n": ex.n, "anomaly": "responder raised",
                                           "traceback": traceback.format_exc()[-2000:]})
                    step = HttpError(400, "invalid_request_error", "fake provider: responder raised")
                if not isinstance(step, Step):
                    self.anomalies.append({"n": ex.n, "anomaly": "responder returned %r" % (step,)})
                    step = HttpError(400, "invalid_request_error", "fake provider: no step")
                ex.step = step
                ex.step_desc = step.describe()
                try:
                    ex.charge = step.charge(ex)
                except Exception:
                    ex.charge = None
            step.serve(sock, ex, self)
            ex.t_response_end = now()
            self._write("%04d-response.bin" % ex.n, ex.response_raw)
            self._append_jsonl("exchanges.jsonl", ex.summary())
            return ex
        finally:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except (OSError, ValueError):
                pass
            try:
                sock.close()
            except OSError:
                pass

    def stop(self):
        self.stopping.set()


def tls_server(cert="provider"):
    """A TLS context factory for handle_connection: serves testonly-<cert>.pem and records
    the client's server name (SNI) into the list it is given."""
    certfile, keyfile = tls_file(cert + ".pem"), tls_file(cert + ".key")

    def make(sni_out):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile, keyfile)

        def on_sni(sslobj, server_name, context):
            sni_out.append(server_name)
        ctx.sni_callback = on_sni
        return ctx
    return make


class Listener:
    """Accepts connections on 127.0.0.1 (ephemeral port) and hands each to handler(sock,
    peer, t_accept) on its own thread."""

    def __init__(self, handler, name="listener"):
        self.handler, self.name = handler, name
        self.sock = None
        self.port = None
        self.stop_flag = threading.Event()
        self.thread = None
        self.threads = []

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((LOOPBACK, 0))      # never a wildcard address or a name; the kernel picks the port
            s.listen(64)
        except OSError as exc:
            s.close()
            raise LoopbackUnavailable("loopback listening unavailable: %s" % exc)
        if s.getsockname()[0] != LOOPBACK:
            s.close()
            raise LoopbackUnavailable("listener is not on 127.0.0.1: %r" % (s.getsockname(),))
        s.settimeout(0.2)
        self.sock, self.port = s, s.getsockname()[1]
        with _OWN_LOCK:
            OWN_PORTS.add(self.port)
        self.thread = threading.Thread(target=self._loop, name=self.name, daemon=True)
        self.thread.start()
        return self

    def _loop(self):
        while not self.stop_flag.is_set():
            try:
                conn, peer = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t_accept = now()
            conn.settimeout(None)
            th = threading.Thread(target=self.handler, args=(conn, peer, t_accept), daemon=True)
            self.threads.append(th)
            th.start()

    def stop(self, join=5.0):
        self.stop_flag.set()
        with _OWN_LOCK:
            OWN_PORTS.discard(self.port)
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        if self.thread is not None:
            self.thread.join(join)
        deadline = now() + join
        for th in self.threads:
            th.join(max(0.0, deadline - now()))


class ConnectProxy:
    """A small HTTP CONNECT proxy for HTTPS_PROXY (INTERFACE 6.1). routes maps
    'host:port' to (ip, port); anything else is answered 502. refuse= answers every
    CONNECT with that status. It records each CONNECT request byte for byte and the
    tunnel's byte counts, and whether the API key ever crossed the tunnel in clear
    (it must not: TLS runs end to end inside the tunnel)."""

    def __init__(self, routes, record_dir=None, refuse=None, key=None, provider=None, connector=None):
        self.routes, self.record_dir, self.refuse = dict(routes), record_dir, refuse
        self.key = key.encode() if isinstance(key, str) else key
        self.provider = provider           # attribution of upstream connections
        for target in self.routes.values():
            if not (isinstance(target, tuple) and len(target) == 2 and target[0] == LOOPBACK):
                raise ValueError("proxy routes must name 127.0.0.1 listener ports: %r" % (target,))
        self.connector = connector or own_connect
        self.tunnels = []
        self.lock = threading.Lock()
        if record_dir:
            os.makedirs(record_dir, exist_ok=True)

    def handle_connection(self, sock, peer=None, t_accept=None):
        with self.lock:
            tid = len(self.tunnels) + 1
            rec = {"tunnel": tid, "at": utc_ms(), "request": None, "authority": None, "headers": [],
                   "answer": None, "up_bytes": 0, "down_bytes": 0, "key_seen_in_clear": False, "problem": None}
            self.tunnels.append(rec)
        up = None
        try:
            sock.settimeout(30)
            buf = bytearray()
            while b"\r\n\r\n" not in buf and len(buf) < 65536:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
            end = buf.find(b"\r\n\r\n")
            raw = bytes(buf[:end + 4]) if end >= 0 else bytes(buf)
            rec["request_raw_hex"] = raw.hex()
            if self.record_dir:
                with open(os.path.join(self.record_dir, "%04d-connect.bin" % tid), "wb") as f:
                    f.write(raw)
            if end < 0:
                rec["problem"] = "no complete CONNECT request"
                return
            lines = raw[:end].decode("latin-1").split("\r\n")
            rec["request"] = lines[0]
            rec["headers"] = [l.split(":", 1) for l in lines[1:]]
            parts = lines[0].split(" ")
            if len(parts) != 3 or parts[0] != "CONNECT":
                rec["problem"] = "not a CONNECT request"
                sock.sendall(b"HTTP/1.1 405 Method Not Allowed\r\ncontent-length: 0\r\n\r\n")
                rec["answer"] = 405
                return
            rec["authority"] = parts[1]
            if self.key and self.key in raw:
                rec["key_seen_in_clear"] = True
            if self.refuse:
                sock.sendall(b"HTTP/1.1 %d %s\r\ncontent-length: 0\r\n\r\n" % (
                    self.refuse, REASONS.get(self.refuse, "Refused").encode()))
                rec["answer"] = self.refuse
                return
            target = self.routes.get(parts[1])
            if target is None:
                sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\ncontent-length: 0\r\n\r\n")
                rec["answer"] = 502
                return
            up = self.connector(target)
            try:
                lport = up.getsockname()[1]
                if self.provider is not None and isinstance(lport, int):
                    self.provider.attribution[lport] = tid
            except (OSError, IndexError, TypeError):
                pass
            sock.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            rec["answer"] = 200
            rest = bytes(buf[end + 4:])
            if rest:
                up.sendall(rest)
                rec["up_bytes"] += len(rest)
            self._relay(sock, up, rec)
        except (OSError, ssl.SSLError) as exc:
            rec["problem"] = "%s" % exc
        finally:
            for s in (up, sock):
                if s is not None:
                    try:
                        s.close()
                    except OSError:
                        pass
            if self.record_dir:
                with open(os.path.join(self.record_dir, "tunnels.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _relay(self, a, b, rec):
        a.settimeout(None)
        b.settimeout(None)
        tail = b""
        open_ab = open_ba = True
        while open_ab or open_ba:
            rs = [s for s, o in ((a, open_ab), (b, open_ba)) if o]
            try:
                r, _, _ = select.select(rs, [], [], 60)
            except (OSError, ValueError):
                return
            if not r:
                return
            for s in r:
                try:
                    data = s.recv(65536)
                except OSError:
                    data = b""
                if s is a:
                    if not data:
                        open_ab = False
                        try:
                            b.shutdown(socket.SHUT_WR)
                        except OSError:
                            pass
                        continue
                    rec["up_bytes"] += len(data)
                    if self.key:
                        window = tail + data
                        if self.key in window:
                            rec["key_seen_in_clear"] = True
                        tail = window[-len(self.key):]
                    b.sendall(data)
                else:
                    if not data:
                        open_ba = False
                        try:
                            a.shutdown(socket.SHUT_WR)
                        except OSError:
                            pass
                        continue
                    rec["down_bytes"] += len(data)
                    a.sendall(data)


# ---------------------------------------------------------------------------
# Accounting witness (INTERFACE 6.4).
# ---------------------------------------------------------------------------

def totals(exchanges, upto=None, overrides=None):
    """Sum the charges of exchanges (n <= upto), split reported and estimated, in the shape
    of run_ended usage. overrides maps exchange number -> basis or charge dict, for attempts
    whose record a kill prevented (reconciliation charges an estimate, 6.4)."""
    out = {k: {"reported": 0, "estimated": 0} for k in ("turns", "input_tokens", "output_tokens")}
    for ex in exchanges:
        if upto is not None and ex.n > upto:
            continue
        c = ex.charge
        if overrides and ex.n in overrides:
            o = overrides[ex.n]
            c = o if isinstance(o, dict) else charge_of(o, ex, getattr(ex.step, "usage", None))
        if not c or c.get("basis") not in ("reported", "estimated"):
            continue
        for k in out:
            out[k][c["basis"]] += c[k] or 0
    return out


def allowances(usage_totals, limits):
    """Status/re-entry allowances (5.6, 7.5) from totals and {turns, input_tokens, output_tokens}."""
    out = {}
    for k in ("turns", "input_tokens", "output_tokens"):
        r, e = usage_totals[k]["reported"], usage_totals[k]["estimated"]
        out[k] = {"used": r + e, "reported": r, "estimated": e, "limit": limits[k]}
    return out


# ---------------------------------------------------------------------------
# A reference HTTP client for self-tests (the shape INTERFACE 6.1 prescribes).
# ---------------------------------------------------------------------------

def stewart_request(host, key, body, path=""):
    head = ("POST %s/v1/messages HTTP/1.1\r\nhost: %s\r\nx-api-key: %s\r\nanthropic-version: %s\r\n"
            "content-type: application/json\r\ncontent-length: %d\r\nconnection: close\r\n\r\n"
            % (path, host, key, API_VERSION, len(body))).encode("latin-1")
    return head + body


def read_response(sock, timeout=10.0):
    """(status, headers, body, complete, raw) for one HTTP/1.1 response; status None when
    no status line arrived."""
    sock.settimeout(timeout)
    raw = bytearray()
    try:
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            raw += chunk
    except (socket.timeout, OSError, ssl.SSLError):
        pass
    raw = bytes(raw)
    end = raw.find(b"\r\n\r\n")
    if not raw.startswith(b"HTTP/1.1 ") or end < 0:
        return None, [], b"", False, raw
    lines = raw[:end].decode("latin-1").split("\r\n")
    status = int(lines[0].split(" ")[1])
    headers = [tuple(x.strip() for x in l.split(":", 1)) for l in lines[1:]]
    hmap = {}
    for n, v in headers:
        hmap.setdefault(n.lower(), []).append(v)
    rest = raw[end + 4:]
    if "chunked" in [v.lower() for v in hmap.get("transfer-encoding", [])]:
        body, i, complete = b"", 0, False
        while True:
            j = rest.find(b"\r\n", i)
            if j < 0:
                break
            size = int(rest[i:j].split(b";")[0], 16)
            if size == 0:
                complete = rest[j + 2:j + 4] == b"\r\n"
                break
            body += rest[j + 2:j + 2 + size]
            i = j + 2 + size + 2
        return status, headers, body, complete, raw
    if "content-length" in hmap:
        n = int(hmap["content-length"][0])
        return status, headers, rest[:n], len(rest) >= n, raw
    return status, headers, rest, True, raw


# ---------------------------------------------------------------------------
# Self-tests (no Stewart binary, no listening socket).
# ---------------------------------------------------------------------------

def _serve_pair(provider, tls=None):
    """A connected (client, thread) pair whose server end the provider serves."""
    a, b = socket.socketpair()
    th = threading.Thread(target=provider.handle_connection, args=(a,), kwargs={"tls": tls}, daemon=True)
    th.start()
    return b, th


def _client_tls(sock, ca="ca", server_hostname="provider.test"):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(tls_file(ca + ".pem"))
    sock.settimeout(10)
    return ctx.wrap_socket(sock, server_hostname=server_hostname)


@selftest
def fake_provider_selftests():
    out = []
    key = "sk-test-0123456789abcdef"
    body = (b'{"model":"claude-opus-5-5","max_tokens":16000,"system":[],"tools":[],"messages":'
            b'[{"role":"user","content":[{"type":"text","text":"Hello \\u00e9"}]}]}')
    req = stewart_request("127.0.0.1:4321", key, body)
    tu = tool_use("toolu_x1", "read", raw_input=b'{"source":"question"}')
    msg = Message([thinking("t", "sig=="), tu, compaction("summary")], stop_reason="tool_use",
                  usage=Usage(1200, 34, cache_creation=None, cache_read=5))

    # Plain HTTP, content-length framing; exact request bytes are recorded.
    for framing in ("length", "chunked", "close"):
        prov = FakeProvider(Script([Message(msg.content, stop_reason="tool_use", usage=msg.usage, framing=framing)]))
        c, th = _serve_pair(prov)
        c.sendall(req)
        status, headers, rbody, complete, raw = read_response(c)
        th.join(5)
        ex = prov.exchanges[0] if prov.exchanges else None
        node = rawjson.try_parse(rbody)
        out.append(("fake.%s.status" % framing, status == 200 and complete, (status, complete, raw[:200])))
        out.append(("fake.%s.request-recorded" % framing, ex is not None and ex.raw == req and ex.body == body))
        out.append(("fake.%s.content-bytes" % framing, node is not None and node.get("content").raw == msg.content_raw
                    and ex.content_raw == msg.content_raw))
        out.append(("fake.%s.tool-use-bytes" % framing,
                    node is not None and node.get("content").items[1].raw == tu.raw
                    and node.get("content").items[1].get("input").raw == b'{"source":"question"}'))
    out.append(("fake.headers-parsed", [h[0] for h in prov.exchanges[0].headers] == list(REQUEST_HEADER_NAMES)))
    out.append(("fake.usage-raw", msg.usage.raw() == b'{"input_tokens":1200,"cache_creation_input_tokens":null,'
                b'"cache_read_input_tokens":5,"output_tokens":34}'))
    ex = prov.exchanges[0]
    out.append(("fake.charge.reported", ex.charge == {"basis": "reported", "turns": 1, "input_tokens": 1205,
                                                      "output_tokens": 34}, ex.charge))
    out.append(("fake.max-tokens", ex.max_tokens() == 16000))

    # Errors with retry-after, and their charge (none).
    prov = FakeProvider(Script([HttpError(529, retry_after="0"), HttpError(413), HttpError(429, retry_after=["61", "x"])]))
    res = []
    for _ in range(3):
        c, th = _serve_pair(prov)
        c.sendall(req)
        res.append(read_response(c))
        th.join(5)
    st, hs, eb, _, _ = res[0]
    hm = {}
    for n, v in hs:
        hm.setdefault(n.lower(), []).append(v)
    err = rawjson.try_parse(eb)
    out.append(("fake.529", st == 529 and hm.get("retry-after") == ["0"] and hm.get("request-id") == ["req_fake_0001"]))
    out.append(("fake.529-body", err is not None and err.get("error").get("type").value() == "overloaded_error"
                and err.get("request_id").value() == "req_fake_0001"))
    out.append(("fake.413-type", rawjson.parse(res[1][2]).get("error").get("type").value() == "request_too_large"))
    hm3 = [v for n, v in res[2][1] if n.lower() == "retry-after"]
    out.append(("fake.retry-after-repeated", hm3 == ["61", "x"], hm3))
    out.append(("fake.charge.none", all(e.charge["basis"] == "none" for e in prov.exchanges)))

    # A dropped connection before the response and in mid-body; an estimated charge.
    prov = FakeProvider(Script([Drop("before_response"), Drop("mid_body", message=msg)]))
    c, th = _serve_pair(prov)
    c.sendall(req)
    st, _, _, _, raw = read_response(c)
    th.join(5)
    out.append(("fake.drop.no-status", st is None and raw == b""))
    c, th = _serve_pair(prov)
    c.sendall(req)
    st, _, rb, complete, _ = read_response(c)
    th.join(5)
    out.append(("fake.drop.mid-body", st == 200 and not complete and 0 < len(rb)))
    e0 = prov.exchanges[0]
    prov2 = FakeProvider(Script([Drop("mid_body", message=HttpError(529))]))
    c, th = _serve_pair(prov2)
    c.sendall(req)
    st, _, _, complete, _ = read_response(c)
    th.join(5)
    out.append(("fake.drop.error-mid-body", st == 529 and not complete and prov2.exchanges[0].charge["basis"] == "none"))
    out.append(("fake.charge.estimated", e0.charge == {"basis": "estimated", "turns": 1,
                                                       "input_tokens": math.ceil(len(body) / 3.0),
                                                       "output_tokens": 16000}, e0.charge))

    # A stall the client abandons (its own timeout): the fake sees the close.
    prov = FakeProvider(Script([Stall(5.0)]))
    c, th = _serve_pair(prov)
    c.sendall(req)
    c.settimeout(0.3)
    try:
        got = c.recv(10)
    except socket.timeout:
        got = None
    c.close()
    th.join(5)
    out.append(("fake.stall.client-timeout", got is None and prov.exchanges[0].outcome == "stalled_client_closed",
                (got, prov.exchanges[0].outcome)))

    # Script exhaustion is answered 400 and recorded.
    sc = Script([])
    prov = FakeProvider(sc)
    c, th = _serve_pair(prov)
    c.sendall(req)
    st = read_response(c)[0]
    th.join(5)
    out.append(("fake.script-exhausted", st == 400 and sc.exhausted == [1]))

    # TLS with the test CA; the server name is recorded; four controls must refuse.
    if not getattr(ssl, "HAS_SNI", False):
        out.append(("fake.tls", None, "skipped: this Python's ssl has no SNI"))
        return out
    prov = FakeProvider(Script([Message([text("over TLS")])]))
    c, th = _serve_pair(prov, tls=tls_server("provider"))
    try:
        cc = _client_tls(c)
        cc.sendall(stewart_request("provider.test", key, body))
        st, _, rb, complete, _ = read_response(cc)
        ok = st == 200 and complete and prov.exchanges and prov.exchanges[0].sni == "provider.test"
        out.append(("fake.tls.exchange", ok, (st, complete, [e.sni for e in prov.exchanges])))
    except (ssl.SSLError, OSError) as exc:
        out.append(("fake.tls.exchange", False, str(exc)))
    th.join(5)
    prov = FakeProvider(Script([Message([text("ip")])]))
    c, th = _serve_pair(prov, tls=tls_server("provider"))
    try:
        cc = _client_tls(c, server_hostname="127.0.0.1")
        cc.sendall(stewart_request("127.0.0.1:443", key, body))
        st = read_response(cc)[0]
        out.append(("fake.tls.ip-name", st == 200 and prov.exchanges[0].sni is None,
                    (st, [e.sni for e in prov.exchanges])))
    except (ssl.SSLError, OSError) as exc:
        out.append(("fake.tls.ip-name", False, str(exc)))
    th.join(5)
    for label, cert, ca, name in (("untrusted-issuer", "untrusted", "ca", "provider.test"),
                                  ("wrong-name", "wrongname", "ca", "provider.test"),
                                  ("expired", "expired", "ca", "provider.test"),
                                  ("other-root", "provider", "other-ca", "provider.test")):
        prov = FakeProvider(Script([Message([text("x")])]))
        c, th = _serve_pair(prov, tls=tls_server(cert))
        try:
            _client_tls(c, ca=ca, server_hostname=name)
            refused = False
        except ssl.SSLError:
            refused = True
        except OSError:
            refused = True
        c.close()
        th.join(5)
        out.append(("fake.tls.control.%s" % label, refused and not prov.exchanges))

    # The CONNECT proxy: a tunnel to the TLS server, key never in clear; and a refusal.
    prov = FakeProvider(Script([Message([text("via proxy")])]))

    def connector(addr):
        a, b = socket.socketpair()
        threading.Thread(target=prov.handle_connection, args=(a,), kwargs={"tls": tls_server("provider")},
                         daemon=True).start()
        return b
    proxy = ConnectProxy({"provider.test:443": ("127.0.0.1", 1)}, key=key, provider=prov, connector=connector)
    p1, p2 = socket.socketpair()
    pt = threading.Thread(target=proxy.handle_connection, args=(p1,), daemon=True)
    pt.start()
    p2.sendall(b"CONNECT provider.test:443 HTTP/1.1\r\nhost: provider.test:443\r\n\r\n")
    p2.settimeout(5)
    hello = b""
    while b"\r\n\r\n" not in hello:
        d = p2.recv(1)
        if not d:
            break
        hello += d
    ok = hello.startswith(b"HTTP/1.1 200")
    try:
        cc = _client_tls(p2)
        cc.sendall(stewart_request("provider.test", key, body))
        st, _, rb, complete, _ = read_response(cc)
        cc.close()
    except (ssl.SSLError, OSError) as exc:
        st, complete = None, str(exc)
    pt.join(5)
    t = proxy.tunnels[0] if proxy.tunnels else {}
    out.append(("fake.proxy.tunnel", ok and st == 200 and complete is True, (hello, st, complete)))
    out.append(("fake.proxy.recorded", t.get("request") == "CONNECT provider.test:443 HTTP/1.1"
                and t.get("authority") == "provider.test:443" and t.get("up_bytes", 0) > len(body)))
    out.append(("fake.proxy.key-not-in-clear", t.get("key_seen_in_clear") is False))
    proxy2 = ConnectProxy({}, refuse=403)
    p1, p2 = socket.socketpair()
    pt = threading.Thread(target=proxy2.handle_connection, args=(p1,), daemon=True)
    pt.start()
    p2.sendall(b"CONNECT provider.test:443 HTTP/1.1\r\nhost: provider.test:443\r\n\r\n")
    st = read_response(p2, timeout=5)[0]
    pt.join(5)
    out.append(("fake.proxy.refusal", st == 403))
    # A key sent in clear through the tunnel is detected (the firing control for that check).
    proxy3 = ConnectProxy({"provider.test:443": ("127.0.0.1", 1)}, key=key,
                          connector=lambda addr: _sink())
    p1, p2 = socket.socketpair()
    pt = threading.Thread(target=proxy3.handle_connection, args=(p1,), daemon=True)
    pt.start()
    p2.sendall(b"CONNECT provider.test:443 HTTP/1.1\r\nhost: provider.test:443\r\n\r\n")
    time.sleep(0.1)
    p2.sendall(stewart_request("provider.test", key, body))
    p2.shutdown(socket.SHUT_WR)
    read_response(p2, timeout=2)
    pt.join(5)
    out.append(("fake.proxy.control.key-in-clear", proxy3.tunnels and proxy3.tunnels[0]["key_seen_in_clear"] is True))

    # Accounting.
    class E:
        pass
    exs = []
    for n, (basis, i, o) in enumerate((("reported", 10, 2), ("estimated", 7, 16000), ("none", 0, 0)), 1):
        e = E()
        e.n = n
        e.charge = {"basis": basis, "turns": 1 if basis != "none" else 0, "input_tokens": i, "output_tokens": o}
        exs.append(e)
    tt = totals(exs)
    out.append(("fake.totals", tt == {"turns": {"reported": 1, "estimated": 1},
                                      "input_tokens": {"reported": 10, "estimated": 7},
                                      "output_tokens": {"reported": 2, "estimated": 16000}}, tt))
    al = allowances(tt, {"turns": 5, "input_tokens": 100, "output_tokens": 20000})
    out.append(("fake.allowances", al["turns"] == {"used": 2, "reported": 1, "estimated": 1, "limit": 5}))

    out += _loopback_selftests(key, body)
    return out


def _loopback_selftests(key, body):
    """The same exchanges over real 127.0.0.1 sockets: plain HTTP, HTTPS with the test CA, and
    HTTPS through the CONNECT proxy. Skipped (never passed) only when binding is refused."""
    out = []
    # The connection guard refuses before connecting: a port this process does not listen on,
    # and any address other than 127.0.0.1 (firing controls for own_connect).
    for label, addr in (("foreign-port", (LOOPBACK, 1)), ("wildcard", ("0.0.0.0", 1)),
                        ("name", ("localhost", 1)), ("ipv6", ("::1", 1))):
        try:
            own_connect(addr)
            out.append(("fake.guard.%s" % label, False, "connected"))
        except NotOwnPort:
            out.append(("fake.guard.%s" % label, True))
        except OSError as exc:
            out.append(("fake.guard.%s" % label, False, "attempted a connection: %s" % exc))
    try:
        ConnectProxy({"x:1": ("10.0.0.1", 443)})
        out.append(("fake.guard.proxy-route", False))
    except ValueError:
        out.append(("fake.guard.proxy-route", True))
    listeners = []

    def listen(handler, name):
        lst = Listener(handler, name).start()
        listeners.append(lst)
        return lst
    try:
        prov = FakeProvider(Script([Message([text("loopback http")], framing="chunked"),
                                    Message([text("loopback https")]), Message([text("via proxy")])]))
        hl = listen(lambda s, p, ta: prov.handle_connection(s, p, ta), "http")
        tl = listen(lambda s, p, ta: prov.handle_connection(s, p, ta, tls=tls_server("provider")), "https")
        proxy = ConnectProxy({"provider.test:443": (LOOPBACK, tl.port)}, key=key, provider=prov)
        pl = listen(lambda s, p, ta: proxy.handle_connection(s, p, ta), "proxy")
        out.append(("fake.loopback.bound", all(l.sock.getsockname()[0] == LOOPBACK for l in listeners)
                    and {l.port for l in listeners} <= OWN_PORTS))
        c = own_connect((LOOPBACK, hl.port))
        c.sendall(stewart_request("127.0.0.1:%d" % hl.port, key, body))
        st, _, rb, complete, _ = read_response(c)
        c.close()
        out.append(("fake.loopback.http", st == 200 and complete and b"loopback http" in rb
                    and prov.exchanges[0].transport == "http" and prov.exchanges[0].t_accept is not None))
        c = _client_tls(own_connect((LOOPBACK, tl.port)), server_hostname="127.0.0.1")
        c.sendall(stewart_request("127.0.0.1:%d" % tl.port, key, body))
        st, _, rb, complete, _ = read_response(c)
        c.close()
        out.append(("fake.loopback.https", st == 200 and complete and prov.exchanges[1].transport == "tls"))
        c = own_connect((LOOPBACK, pl.port))
        c.sendall(b"CONNECT provider.test:443 HTTP/1.1\r\nhost: provider.test:443\r\n\r\n")
        c.settimeout(5)
        hello = b""
        while b"\r\n\r\n" not in hello:
            d = c.recv(1)
            if not d:
                break
            hello += d
        cc = _client_tls(c)
        cc.sendall(stewart_request("provider.test", key, body))
        st, _, rb, complete, _ = read_response(cc)
        cc.close()
        deadline = now() + 5
        while len(prov.exchanges) < 3 and now() < deadline:
            time.sleep(0.01)
        ex3 = prov.exchanges[2] if len(prov.exchanges) > 2 else None
        out.append(("fake.loopback.proxy", hello.startswith(b"HTTP/1.1 200") and st == 200 and complete
                    and ex3 is not None and ex3.transport == "tls-via-proxy" and ex3.sni == "provider.test",
                    (hello, st, ex3.transport if ex3 else None)))
        time.sleep(0.05)
        out.append(("fake.loopback.proxy-key-not-in-clear", proxy.tunnels and proxy.tunnels[0]["key_seen_in_clear"] is False
                    and proxy.tunnels[0]["up_bytes"] > len(body)))
        # A route to a port that is not one of this run's listeners is refused by the guard.
        stray = ConnectProxy({"provider.test:443": (LOOPBACK, 1)}, key=key)
        sl = listen(lambda s, p, ta: stray.handle_connection(s, p, ta), "stray-proxy")
        c = own_connect((LOOPBACK, sl.port))
        c.sendall(b"CONNECT provider.test:443 HTTP/1.1\r\nhost: provider.test:443\r\n\r\n")
        st = read_response(c, timeout=5)[0]
        c.close()
        out.append(("fake.loopback.proxy-guard", st is None and stray.tunnels and "refusing" in (stray.tunnels[0]["problem"] or ""),
                    stray.tunnels))
    except LoopbackUnavailable as exc:
        out.append(("fake.loopback", None, "skipped: %s" % exc))
    finally:
        for l in listeners:
            l.stop()
        out.append(("fake.loopback.ports-released", not ({l.port for l in listeners} & OWN_PORTS)))
    return out


def _sink():
    a, b = socket.socketpair()

    def drain():
        try:
            while a.recv(65536):
                pass
        except OSError:
            pass
        a.close()
    threading.Thread(target=drain, daemon=True).start()
    return b
