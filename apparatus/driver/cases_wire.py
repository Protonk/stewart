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
