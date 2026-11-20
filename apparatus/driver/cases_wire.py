"""Local HTTP and CONNECT captures for INTERFACE 6.1 and 6.6."""

import hashlib
from pathlib import Path
import socket
import threading

import fake_provider as fp
import run_support as rs
from cases_run import run_submission
from driver_core import case, selftest


WIRE = Path(__file__).resolve().parent / "testdata" / "wire"
BODY = WIRE.parent / "messages" / "m3-ordinary-ending.json"


def wire(name):
    return (WIRE / (name + ".bin")).read_bytes()


@selftest
def wire_framing_selftest():
    checks = []
    for line in (WIRE / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        digest, name = line.split()
        checks.append(("wire.original." + name, hashlib.sha256((WIRE / name).read_bytes()).hexdigest() == digest))
    body = BODY.read_bytes()
    for name, status, length, coding in (("length", 200, "1555", None), ("chunked", 200, None, "chunked"),
                                          ("close", 200, None, None), ("unavailable", 503, "1555", None)):
        framing = "length" if name == "unavailable" else name
        raw = wire("http-" + name)
        fake_head, fake_payload = fp._framed(status, [], body, framing)
        for source, data in (("captured", raw), ("stand-in", fake_head + fake_payload)):
            code, fields, decoded, complete, _ = fp.parse_response(data)
            headers = {key.lower(): value for key, value in fields}
            facts = (code, headers.get("content-length"), headers.get("transfer-encoding"),
                     complete, decoded == body)
            checks.append(("wire.%s.%s" % (name, source), facts == (status, length, coding, True, True), facts))
    # The final byte is required by these two framings. These copies are synthetic cuts.
    for name in ("length", "chunked"):
        status, _, _, complete, _ = fp.parse_response(wire("http-" + name)[:-1])
        checks.append(("wire.%s.truncated" % name, (status, complete) == (200, False)))
    return checks


@selftest
def wire_connect_selftest():
    checks = []
    for label, req, reply, code in (("accepted", "accepted", "accepted", 200),
                                    ("refused", "accepted", "refused", 407),
                                    ("case", "header-case", "accepted", 200)):
        request = wire("connect-" + req + "-request")
        response = wire("connect-" + reply)
        up = wire("origin-accepted-received")
        down = wire("client-accepted-received")
        opens = []
        origin, relay = socket.socketpair()
        client, server = socket.socketpair()
        with origin, relay, client, server:
            client.settimeout(3)
            origin.settimeout(3)

            def connect(addr):
                opens.append(addr)
                return relay

            target = (fp.LOOPBACK, 1)
            proxy = fp.ConnectProxy({"provider.test:443": target}, reply=response, connector=connect)
            thread = threading.Thread(target=proxy.handle_connection, args=(server,), daemon=True)
            thread.start()
            client.sendall(request)
            with client.makefile("rb") as stream:
                seen = stream.read(len(response))
                checks.append(("wire.connect.%s.reply" % label, seen == response))
                if code == 200:
                    client.sendall(up)
                    with origin.makefile("rb") as upstream:
                        actual_up = upstream.read(len(up))
                    origin.sendall(down)
                    actual_down = stream.read(len(down))
                    checks.append(("wire.connect.%s.relay" % label, (actual_up, actual_down) == (up, down)))
                else:
                    checks.append(("wire.connect.refusal-eof", stream.read(1) == b""))
            if code == 200:
                client.shutdown(socket.SHUT_WR)
                origin.shutdown(socket.SHUT_WR)
            thread.join(3)
            rec = proxy.tunnels[0]
            checks.append(("wire.connect.%s.route" % label, opens == ([target] if code == 200 else []), opens))
            observed = (rec["answer"], rec["request_raw_hex"], rec["up_bytes"], rec["down_bytes"], rec["problem"])
            counts = (len(up), len(down)) if code == 200 else (0, 0)
            checks.append(("wire.connect.%s.witness" % label,
                           not thread.is_alive() and observed == (code, request.hex(), *counts, None), observed))
    return checks


@case("c1.captured-wire", ["C1", "C6", "C12", "C14"],
      "local HTTP and CONNECT replies preserve body bytes and distinguish 503 retry from 407 tunnel refusal",
      mode="test", needs=("loopback",))
def c_captured_wire(t):
    """Replays local HTTP and CONNECT transcripts. A 503 retries. A 200 preserves the same body
    across length, chunked and close-delimited framing. A 407 ends each tunnel attempt before
    any provider request."""
    body = BODY.read_bytes()
    reported = {"basis": "reported", "turns": 1, "input_tokens": 6660, "output_tokens": 248}
    request = wire("connect-accepted-request").hex()
    for label, first, second in (("length", "length", "length"), ("stream", "chunked", "close")):
        name = "wire." + label
        sub = run_submission(t, entries=[], body=b"Describe the supplied material.\n", model="claude-haiku-5-5")
        frames = [wire("http-" + shape) for shape in ("unavailable", first, second)]
        script = fp.Script([fp.Raw(frames[0]), fp.Raw(frames[1], reported), fp.Raw(frames[2], reported)])
        fx = rs.provider(t, script, mode="https-proxy", proxy_reply=wire("connect-accepted"), label=label)
        rep = rs.run(t, sub, fx, name=name)
        rs.check_run_reply(t, rep, sub, name, ending="ended_unsubmitted", run_number=1, fx=fx, limits=rs.limits_of(sub))
        t.eq(name + ".script", (script.used, script.exhausted), (3, []))
        t.eq(name + ".frames-sent", [ex.response_raw for ex in fx.exchanges], frames)
        t.eq(name + ".transport", [ex.transport for ex in fx.exchanges], ["tls-via-proxy"] * 3)
        t.eq(name + ".connect", [(r["request_raw_hex"], r["answer"]) for r in fx.proxy.tunnels], [(request, 200)] * 3)
        rd = rs.run_dirs(sub).get(1)
        t.require(name + ".run-directory", rd is not None)
        keys = [(1, 1), (1, 2), (2, 1)]
        t.eq(name + ".responses", rd.responses, {key: body for key in keys})
        t.eq(name + ".attempts", sorted(rd.attempts), keys)
        attempts = [(rd.attempts.get(key) or {}).get("body", {}) for key in keys]
        observed = [(a.get("status"), a.get("outcome"), a.get("then")) for a in attempts]
        t.eq(name + ".decisions", observed, [(503, "http_error", "retry"), (200, "response", "use"),
                                              (200, "response", "use")])
        rs.check_captures(t, sub, fx, name)

    name = "wire.refused"
    sub = run_submission(t, entries=[], body=b"Describe the supplied material.\n", model="claude-haiku-5-5")
    fx = rs.provider(t, fp.Script([]), mode="https-proxy", proxy_reply=wire("connect-refused"), label="refused")
    rep = rs.run(t, sub, fx, name=name)
    provider = {"status": None, "error_type": None, "error_message": None, "request_id": None, "request": 1, "attempt": 4}
    rs.check_run_reply(t, rep, sub, name, ending="interrupted", cause="provider_unavailable", provider=provider,
                       run_number=1, fx=fx, limits=rs.limits_of(sub))
    t.eq(name + ".connect", [(r["request_raw_hex"], r["answer"], r["up_bytes"], r["down_bytes"])
                             for r in fx.proxy.tunnels], [(request, 407, 0, 0)] * 4)
    t.eq(name + ".provider-exchanges", fx.exchanges, [])
    rd = rs.run_dirs(sub).get(1)
    t.require(name + ".run-directory", rd is not None)
    t.eq(name + ".responses", rd.responses, {})
    keys = [(1, attempt) for attempt in range(1, 5)]
    t.eq(name + ".attempts", sorted(rd.attempts), keys)
    attempts = [(rd.attempts.get(key) or {}).get("body", {}) for key in keys]
    observed = [(a.get("status"), a.get("request_written"), a.get("outcome"), a.get("then")) for a in attempts]
    t.eq(name + ".decisions", observed, [(None, "none", "connection_failed", action)
                                         for action in ("retry", "retry", "retry", "end")])


# ---------------------------------------------------------------------------
# Response heads (INTERFACE 6.1): interim heads, folded fields and content lengths.
# ---------------------------------------------------------------------------

HEAD_USAGE = fp.Usage(310, 9)
HEAD_BOUND = 262144            # 6.1: status and header lines of the interim and final heads together


def _pad_lines(total, prefix):
    """Header lines `<prefix>-NNN: aaa...` CRLF, each at most 8 KiB, whose bytes sum to total."""
    lines, left, i = [], total, 0
    while left > 0:
        name = b"%s-%03d: " % (prefix, i)
        size = min(left, 8192)
        if size < len(name) + 3:
            prev = lines.pop()
            lines.append(prev[:-2] + b"a" * left + b"\r\n")
            break
        lines.append(name + b"a" * (size - len(name) - 2) + b"\r\n")
        left -= size
        i += 1
    return b"".join(lines)


def _bounded_heads(status_line, fields, target, interim):
    """Heads totalling exactly target bytes (status lines, fields, padding and blank lines): with
    interim, a 103 head carries about half the padding before the final head."""
    fixed = status_line + b"".join(f + b"\r\n" for f in fields)
    early = b"HTTP/1.1 103 Early Hints\r\n"
    pad = target - len(fixed) - 2 - ((len(early) + 2) if interim else 0)
    first = pad // 2 if interim else 0
    head = (early + _pad_lines(first, b"x-early") + b"\r\n") if interim else b""
    head += fixed + _pad_lines(pad - first, b"x-final") + b"\r\n"
    assert len(head) == target, (len(head), target)
    return head


def _head(status, reason, fields):
    return b"HTTP/1.1 %d %s\r\n" % (status, reason) + b"".join(f + b"\r\n" for f in fields) + b"\r\n"


def _pause_body(label):
    """A decodable message that ends its placement interrupted (pause_turn, 6.3), so each shape
    is one request of its own placement."""
    return fp.Message([fp.text("Pausing at the %s head." % label)], stop_reason="pause_turn",
                      msg_id="msg_head_" + label, usage=HEAD_USAGE).body(None)


def _head_shapes():
    """(label, [(raw response, charge)], cause, [expected attempt facts]) in 6.1's terms. An
    attempt's facts are status, outcome, then and, where the head is valid, the retained headers
    and the response capture."""
    reported = fp.charge_of("reported", None, HEAD_USAGE)
    json_type = b"content-type: application/json"
    out = []

    def valid(label, fields, *, interim=b"", headers=None):
        body = _pause_body(label)
        raw = interim + _head(200, b"OK", fields(len(body))) + body
        want = {"status": 200, "outcome": "response", "then": "use", "body": body,
                "headers": headers or {"content-type": ["application/json"], "request-id": ["req_" + label],
                                       "retry-after": []}}
        out.append((label, [(raw, reported)], "protocol_anomaly", [want]))

    def malformed(label, lengths):
        body = _pause_body(label)
        raw = _head(200, b"OK", [json_type, b"request-id: req_" + label.encode()]
                    + [b"content-length: " + v for v in lengths(len(body))]) + body
        out.append((label, [(raw, "estimated")], "protocol_anomaly",
                    [{"status": 200, "outcome": "response_undecodable", "then": "end"}]))

    # Interim heads (100 and 103) carry fields of their own; only the final head's are retained.
    valid("interim", lambda n: [json_type, b"request-id: req_interim", b"content-length: %d" % n],
          interim=_head(100, b"Continue", []) + _head(103, b"Early Hints", [
              b"link: </style.css>; rel=preload", b"request-id: req_early", b"retry-after: 9",
              b"content-type: text/html"]))
    # A folded continuation joins the value with one space after its leading spaces and tabs.
    valid("folded", lambda n: [json_type, b"request-id: req_folded", b" \t continued", b"\tand more",
                               b"content-length: %d" % n],
          headers={"content-type": ["application/json"], "request-id": ["req_folded continued and more"],
                   "retry-after": []})
    # Repeated and comma-separated lengths that are the same digit string, and 19 digits, are valid.
    valid("same-lengths", lambda n: [json_type, b"request-id: req_same-lengths",
                                     b"content-length: %d, %d" % (n, n), b"content-length: %d" % n])
    valid("nineteen-digits", lambda n: [json_type, b"request-id: req_nineteen-digits", b"content-length: %019d" % n])
    # Each names the body's own length somewhere, so only the rule, not a short read, can refuse it.
    malformed("twenty-digits", lambda n: [b"%020d" % n])
    malformed("conflicting", lambda n: [b"%d" % n, b"%d" % (n + 1)])
    malformed("comma-conflicting", lambda n: [b"%d, %d" % (n, n - 1)])
    malformed("signed", lambda n: [b"+%d" % n])
    # The head bound (6.1): 64 bytes under it the response is read as usual; 64 bytes over it the
    # framing is malformed, so a 200 is response_undecodable and a 529 stays http_error (retried;
    # the delay is not judged, since whether an over-bound head's retry-after is used is open).
    for layout in ("interim", "final-only"):
        for size, delta in (("under", -64), ("over", 64)):
            label = "bound-200-%s-%s" % (layout, size)
            body = _pause_body(label)
            raw = _bounded_heads(b"HTTP/1.1 200 OK\r\n", [json_type, b"request-id: req_" + label.encode(),
                                                             b"content-length: %d" % len(body)],
                                 HEAD_BOUND + delta, layout == "interim") + body
            if size == "under":
                out.append((label, [(raw, reported)], "protocol_anomaly",
                            [{"status": 200, "outcome": "response", "then": "use", "body": body,
                              "headers": {"content-type": ["application/json"], "request-id": ["req_" + label],
                                          "retry-after": []}}]))
            else:
                out.append((label, [(raw, "estimated")], "protocol_anomaly",
                            [{"status": 200, "outcome": "response_undecodable", "then": "end"}]))
            label = "bound-529-%s-%s" % (layout, size)
            err = b'{"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}'
            raw = _bounded_heads(b"HTTP/1.1 529 Overloaded\r\n", [json_type, b"request-id: req_" + label.encode(),
                                                                     b"retry-after: 0",
                                                                     b"content-length: %d" % len(err)],
                                 HEAD_BOUND + delta, layout == "interim") + err
            body = _pause_body(label + "-after")
            final = _head(200, b"OK", [json_type, b"request-id: req_after", b"content-length: %d" % len(body)]) + body
            first = {"status": 529, "outcome": "http_error", "then": "retry"}
            if size == "under":
                first["delay_ms"] = 0
            out.append((label, [(raw, "none"), (final, reported)], "protocol_anomaly",
                        [first, {"status": 200, "outcome": "response", "then": "use", "body": body}]))
    # Another status keeps its http_error outcome (and its retry) despite malformed framing.
    err = b'{"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}'
    raw = _head(529, b"Overloaded", [json_type, b"request-id: req_err", b"retry-after: 0",
                                     b"content-length: %d" % len(err), b"content-length: %d" % (len(err) + 3)]) + err
    body = _pause_body("after-529")
    final = _head(200, b"OK", [json_type, b"request-id: req_after-529", b"content-length: %d" % len(body)]) + body
    out.append(("error-conflicting", [(raw, "none"), (final, reported)], "protocol_anomaly",
                [{"status": 529, "outcome": "http_error", "then": "retry", "delay_ms": 0},
                 {"status": 200, "outcome": "response", "then": "use", "body": body,
                  "headers": {"content-type": ["application/json"], "request-id": ["req_after-529"],
                              "retry-after": []}}]))
    return out


@case("c13.response-heads", ["C13", "C1", "C6", "C14"],
      "interim heads, folded fields, content lengths and the head bound are read as 6.1 states: only the final "
      "head counts; conflicting or invalid lengths, or heads over the bound, make a 200 undecodable",
      needs=("loopback",))
def c_response_heads(t):
    """One audit, one placement per shape, each continuing the last, on the release binary.
    A 100 and a 103 with their own request-id, retry-after and content-type before the final
    200: the attempt is that 200's, with only its fields retained. A folded request-id joins its
    continuations with single spaces. Equal repeated and comma-separated lengths and a 19-digit
    length decode (the invariance cases). A 20-digit, a conflicting, a comma-conflicting and a
    signed length make the 200 response_undecodable, charged as estimated, ending the placement.
    A 529 with conflicting lengths stays http_error and is retried after its retry-after of 0.
    Heads totalling 64 bytes under the 262,144-byte bound, split across a 103 and the final head
    or all in the final head, are read as usual; 64 bytes over it a 200 is response_undecodable
    and a 529 stays http_error and is retried.
    Each decodable response is captured byte for byte."""
    sub = run_submission(t)
    fx = rs.provider(t, fp.Script([]))
    labels = []
    for i, (label, steps, cause, attempts) in enumerate(_head_shapes(), 1):
        pre = "heads." + label
        labels.append(pre)
        script = fp.Script([fp.Raw(raw, charge) for raw, charge in steps])
        fx.provider.responder = script
        rep = rs.run(t, sub, fx, name=pre)
        t.eq(pre + ".script-used", (script.used, script.exhausted), (len(steps), []))
        rs.check_run_reply(t, rep, sub, pre, ending="interrupted", cause=cause, run_number=i, fx=fx,
                           limits=rs.limits_of(sub))
        rd = rs.run_dirs(sub).get(i)
        if not t.check(pre + ".run-dir", rd is not None, sorted(rs.run_dirs(sub))):
            continue
        keys = sorted(rd.attempts)
        t.eq(pre + ".attempts", keys, [(1, k) for k in range(1, len(attempts) + 1)])
        for key, want in zip(keys, attempts):
            body = (rd.attempts.get(key) or {}).get("body") or {}
            q = "%s.%d" % (pre, key[1])
            t.eq(q + ".decision", [body.get(k) for k in ("status", "outcome", "then")],
                 [want["status"], want["outcome"], want["then"]])
            if want["outcome"] == "response_undecodable":
                t.check(q + ".problem", isinstance(body.get("problem"), str) and body["problem"].strip(), body)
            if "headers" in want:
                t.eq(q + ".headers", body.get("headers"), want["headers"])
            if "body" in want:
                t.eq(q + ".capture", rd.responses.get(key), want["body"])
                t.eq(q + ".response", [(body.get("response") or {}).get(k) for k in ("bytes", "complete")],
                     [len(want["body"]), True])
            if "delay_ms" in want:
                t.eq(q + ".delay", body.get("delay_ms"), want["delay_ms"])
    t.eq("heads.fake-responder", fx.provider.anomalies, [])
    rs.check_requests(t, fx, sub, "heads")
    rs.check_run_ended_usage(t, sub, fx, labels, "heads")
