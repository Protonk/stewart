# -*- coding: utf-8 -*-
"""Run support shared by every case after launch.

- `provider(t, responder, mode=...)`: the fake Messages API as a case fixture,
  on loopback (plain HTTP, HTTPS with the test CA, or HTTPS through the CONNECT
  proxy), with the environment that points a binary at it. Where this process
  cannot listen on loopback the case is skipped with that reason.
- `run`, `start_run`, `finish_run`: `stewart run REF` with a controlled
  environment (key, provider URL, proxy, test variables, fault points),
  foreground or background, captured like every other command and with the
  archive inventoried before and after (C6: archives only grow).
- Readers for the archive's run captures (INTERFACE 4.5) and the access log.
- Witness comparisons: request shape and splicing (6.1, 6.2, 4.5), history
  echo, accounting against the fake's charges (6.4), the access log against
  the calls the auditor made, protocol-call timings (C9) and the delivered
  package against answer_witness.

Cases call these with their `T`; nothing here decides a case's verdict except
through `t.check`. The functions and classes without a leading underscore are a
stable API shared by every cases_*.py module; change them only compatibly.

Typical use:

    sub = t.submission(entries, dest_watch="additions"); t.accept(sub)
    p = procedure.Procedure(body, forbidden=[...])   # or reacting_auditor.ReactingAuditor(...)
    fx = run_support.provider(t, p)                   # mode="https-proxy" etc.
    rep = run_support.run(t, sub, fx, name="x.run")
    run_support.check_run_reply(t, rep, sub, "x.run", ending="sealed", run_number=1, fx=fx, ...)
    run_support.check_procedure(t, p, "x", fx)
    run_support.check_requests(t, fx, sub, "x"); run_support.check_history(t, fx, "x")
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil

import answer_witness as aw
import fake_provider as fp
import rawjson
from driver_core import (ANTHROPIC_BETA, API_VERSION, COMPACTION, POST_COMPACTION, LOG_KINDS, MAX_TOKENS_PER_REQUEST, RECORD_SCHEMA, RUN_CAUSES, RUN_ENDINGS,
                         StrictJSONError, Skip, expected_system_bytes, expected_tools, read_bytes, sha256_hex,
                         short, strict_loads)

RUN_DATA_KEYS = ("run", "continuing", "ending", "cause", "provider", "usage", "allowances", "answer", "seal",
                 "delivery", "notices")
NEXT_FOR_ENDING = {  # INTERFACE 5.7
    "interrupted": ("run", "close"),
    "ended_unsubmitted": ("close",), "limit_reached": ("close",), "damaged": ("close",),
    "stopped_by_close": ("status", "close"),
    "sealed": ("close",),
}
PROVIDER_NAME = "provider.test"
# run_ended.provider and the run reply's data.provider (INTERFACE 4.4, 5.7), in order; present
# for the causes provider_unavailable and provider_rejected, else the member is null.
PROVIDER_FACT_KEYS = ("status", "error_type", "error_message", "request_id", "request", "attempt")
PROVIDER_CAUSES = ("provider_unavailable", "provider_rejected")


def effort_bytes(sub):
    """X of INTERFACE 4.5 for a submission: `,"output_config":{"effort":"<level>"}` when its front
    matter sets an effort (6.2 request_extra), and nothing otherwise."""
    e = getattr(sub, "effort", None)
    return b"" if e is None else b',"output_config":{"effort":' + fp.jstr(e) + b"}"


def expected_request_extra(sub):
    """The arrangement's request_extra value (6.2) for a submission, as parsed JSON."""
    e = getattr(sub, "effort", None)
    return {} if e is None else {"output_config": {"effort": e}}


def test_key():
    """A provider key of bytes 0x21-0x7E (6.1, 5.7), unique per call."""
    return "sk-ant-TEST-ONLY-" + os.urandom(12).hex()


# ---------------------------------------------------------------------------
# The provider fixture.
# ---------------------------------------------------------------------------

class ProviderFixture:
    """modes: 'http' (http://127.0.0.1:PORT), 'http-localhost', 'https' (https://127.0.0.1:PORT,
    test CA), 'https-localhost', 'https-proxy' (https://provider.test through HTTPS_PROXY),
    'https-unreachable' (https://provider.test, no proxy: resolution fails offline)."""

    def __init__(self, t, responder, mode="http", label="provider", path="", cert="provider", proxy_refuse=None,
                 key=None, url_port=None, accepts=None):
        self.t, self.mode, self.label, self.path = t, mode, label, path
        self.key = key or test_key()
        self.record_dir = os.path.join(t.evid, "provider-" + label)
        # accepts (an fp.Accepts): judge every request against what this provider accepts before
        # the responder sees it (fp.Gate); `gate.accepts` may be replaced between runs.
        self.gate = fp.Gate(accepts, responder) if accepts is not None else None
        self.provider = fp.FakeProvider(self.gate or responder, record_dir=self.record_dir, name=label)
        self.provider.charge_overrides = {}
        self.provider.extra_charges = {}
        self.responder = responder
        # A responder that judges allowances and notices (the reacting auditor) needs the fake's
        # charges; give it this provider unless it already has one. Without it those
        # comparisons would be skipped silently.
        if hasattr(responder, "provider") and getattr(responder, "provider") is None:
            responder.provider = self.provider
        self.cert, self.proxy_refuse, self.url_port = cert, proxy_refuse, url_port
        self.listeners = []
        self.proxy = None
        self.marks = []
        self.url = self.proxy_url = None
        self.host_header = None
        self.tls_root = None

    @property
    def exchanges(self):
        return self.provider.exchanges

    def start(self):
        try:
            if self.mode in ("http", "http-localhost"):
                lst = fp.Listener(lambda s, p, ta: self.provider.handle_connection(s, p, ta), "http").start()
                self.listeners.append(lst)
                host = "127.0.0.1" if self.mode == "http" else "localhost"
                self.url = "http://%s:%d%s" % (host, lst.port, self.path)
                self.host_header = "%s:%d" % (host, lst.port)
            elif self.mode in ("https", "https-localhost", "https-proxy"):
                tls = fp.tls_server(self.cert)
                lst = fp.Listener(lambda s, p, ta: self.provider.handle_connection(s, p, ta, tls=tls), "https").start()
                self.listeners.append(lst)
                if self.mode == "https-proxy":
                    port = self.url_port or 443
                    authority = "%s:%d" % (PROVIDER_NAME, port)
                    self.proxy = fp.ConnectProxy({authority: ("127.0.0.1", lst.port)},
                                                 record_dir=os.path.join(self.record_dir, "proxy"),
                                                 refuse=self.proxy_refuse, key=self.key, provider=self.provider)
                    pl = fp.Listener(lambda s, p, ta: self.proxy.handle_connection(s, p, ta), "proxy").start()
                    self.listeners.append(pl)
                    self.proxy_url = "http://127.0.0.1:%d" % pl.port
                    self.url = "https://%s%s%s" % (PROVIDER_NAME, "" if self.url_port is None else ":%d" % port, self.path)
                    self.host_header = PROVIDER_NAME if self.url_port is None else authority
                else:
                    host = "127.0.0.1" if self.mode == "https" else "localhost"
                    self.url = "https://%s:%d%s" % (host, lst.port, self.path)
                    self.host_header = "%s:%d" % (host, lst.port)
            elif self.mode == "https-unreachable":
                # The binary resolves provider.test itself: only on a run without network.
                if not getattr(self.t.drv.args, "network_isolated", False):
                    raise Skip("needs --network-isolated (the binary would resolve provider.test itself)")
                self.url = "https://%s%s" % (PROVIDER_NAME, self.path)
                self.host_header = PROVIDER_NAME
            else:
                raise ValueError(self.mode)
        except fp.LoopbackUnavailable as exc:
            self.stop()
            raise Skip(str(exc))
        if self.mode.startswith("https"):
            d = self.t.mkdir("tls")
            self.tls_root = os.path.join(d, "test-root-%s.pem" % self.label)
            shutil.copyfile(fp.tls_file("ca.pem"), self.tls_root)
        return self

    def env(self, test_binary=True, retry_delays="0,0,0", timeout=None):
        """The environment that points a binary at this fake. The test variables are given
        only to the test binary (the release binary must not know them, Appendix C)."""
        e = {"ANTHROPIC_API_KEY": self.key, "STEWART_PROVIDER_URL": self.url}
        if self.proxy_url:
            e["HTTPS_PROXY"] = self.proxy_url
        if test_binary:
            if self.tls_root:
                e["STEWART_TEST_TLS_ROOT"] = self.tls_root
            if retry_delays is not None:
                e["STEWART_TEST_RETRY_DELAYS"] = retry_delays
            if timeout is not None:
                e["STEWART_TEST_PROVIDER_TIMEOUT"] = str(timeout)
        return e

    def mark(self, label):
        """Attribute the exchanges that follow to this label (one per run invocation)."""
        self.marks.append((label, len(self.provider.exchanges) + 1))

    def exchanges_of(self, label):
        names = [m[0] for m in self.marks]
        if label not in names:
            return []
        i = names.index(label)
        lo = self.marks[i][1]
        hi = self.marks[i + 1][1] if i + 1 < len(self.marks) else None
        return [e for e in self.provider.exchanges if e.n >= lo and (hi is None or e.n < hi)]

    def totals(self, exchanges=None, upto=None):
        return fp.totals(self.provider.exchanges if exchanges is None else exchanges, upto=upto,
                         overrides=self.provider.charge_overrides)

    def stop(self):
        self.provider.stop()
        for lst in self.listeners:
            lst.stop()
        self.listeners = []
        try:
            os.makedirs(self.record_dir, exist_ok=True)
            summary = {"mode": self.mode, "url": self.url, "proxy": self.proxy_url, "marks": self.marks,
                       "accepts": self.gate.accepts.describe() if self.gate else None,
                       "exchanges": [e.summary() for e in self.provider.exchanges],
                       "events": self.provider.events, "anomalies": self.provider.anomalies,
                       "tunnels": self.proxy.tunnels if self.proxy else [],
                       "charge_overrides": {str(k): v for k, v in self.provider.charge_overrides.items()}}
            w = getattr(self.responder, "witness", None)
            if callable(w):
                summary["auditor"] = w()
            with open(os.path.join(self.record_dir, "SUMMARY.json"), "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=1, default=repr)
        except OSError:
            pass


def provider(t, responder, **kw):
    fx = ProviderFixture(t, responder, **kw).start()
    t.cleanup(fx.stop)
    return fx


# ---------------------------------------------------------------------------
# Running.
# ---------------------------------------------------------------------------

def run_env(t, fx, env=None, retry_delays="0,0,0", timeout=None):
    e = {}
    if fx is not None:
        e.update(fx.env(test_binary=t.bin["kind"] == "test", retry_delays=retry_delays, timeout=timeout))
    e.update(env or {})
    return e


def run(t, sub, fx=None, *, name="run", expect="completed", reason=None, env=None, fault=None, timeout=600,
        cwd=None, binary=None, retry_delays="0,0,0", provider_timeout=None, killed=False):
    """`stewart run REF` in the foreground. killed=True is for a run a case kills on purpose
    (a `kill` fault point): no reply exists, so the envelope and outcome are not judged; the
    run must instead have died by SIGKILL with nothing on stdout (checks <name>.killed and
    <name>.no-reply)."""
    if fx is not None:
        fx.mark(name)
    rep = t.cmd(["run", sub.ref], name=name, expect=None if killed else expect, reason=None if killed else reason,
                env=run_env(t, fx, env, retry_delays, provider_timeout), fault=fault, timeout=timeout, cwd=cwd,
                binary=binary, writer=sub.writer, envelope=not killed)
    if killed:
        import signal as _signal
        t.eq(name + ".killed", rep.rc, -_signal.SIGKILL)
        t.eq(name + ".no-reply", rep.stdout, b"")
    if fx is not None:
        collect_protocol_timings(t, fx, name)
    return rep


def start_run(t, sub, fx=None, *, name="run", env=None, fault=None, timeout=600, cwd=None,
              retry_delays="0,0,0", provider_timeout=None):
    if fx is not None:
        fx.mark(name)
    h = t.start(["run", sub.ref], name=name, env=run_env(t, fx, env, retry_delays, provider_timeout), fault=fault,
                timeout=timeout, cwd=cwd)
    h["fx"] = fx
    return h


def finish_run(t, h, *, expect="completed", reason=None, timeout=None, envelope=True):
    rep = t.finish(h, expect=expect, reason=reason, timeout=timeout, envelope=envelope)
    if h.get("fx") is not None:
        collect_protocol_timings(t, h["fx"], h["name"])
    return rep


def check_refused_before_request(t, rep, sub, fx, name, next_run=True):
    """A run refused before launching: nothing reached the provider, nothing was published (5.7).
    next_run: 5.7 offers "the same run once the environment is set" only for the environment
    refusals; pass False for the others (it names no next call for not_accepted)."""
    t.eq(name + ".effects", {k: v for k, v in rep.effects.items() if k != "diagnostic"},
         {"run": "not_started", "answer": "unchanged", "seal": "none", "delivery": "none"})
    if fx is not None:
        t.eq(name + ".no-provider-request", len(fx.exchanges_of(name)), 0)
    t.check(name + ".no-run-started", "run_started" not in t.log_kinds(sub), t.log_kinds(sub))
    if next_run:
        t.check(name + ".next-run", [sub.writer, "run", sub.ref] in rep.next_argvs(), rep.next)


_UNSET = object()


def check_run_reply(t, rep, sub, name, *, ending, cause=None, run_number=None, fx=None, limits=None,
                    seal_actor=None, delivery_outcome=None, provider=_UNSET):
    """The run reply of 5.7 for a recorded ending. data.provider has the members of
    PROVIDER_FACT_KEYS in order when the cause is a provider cause, and is null otherwise;
    provider=, when given, is the exact expected value (see provider_expected)."""
    d = rep.data
    t.eq(name + ".data-keys", list(d), list(RUN_DATA_KEYS))
    t.eq(name + ".ending", d.get("ending"), ending)
    t.eq(name + ".cause", d.get("cause"), cause)
    t.check(name + ".ending-known", ending in RUN_ENDINGS and (cause is None or cause in RUN_CAUSES), (ending, cause))
    t.eq(name + ".effects.run", rep.effects.get("run"), "ended")
    prov = d.get("provider", "missing")
    if cause in PROVIDER_CAUSES:
        t.eq(name + ".provider-keys", list(prov) if isinstance(prov, dict) else prov, list(PROVIDER_FACT_KEYS))
    else:
        t.eq(name + ".provider-null", prov, None)
    if provider is not _UNSET:
        t.eq(name + ".provider", prov, provider)
    if run_number is not None:
        t.eq(name + ".run", d.get("run"), run_number)
        t.eq(name + ".continuing", d.get("continuing"), run_number > 1)
    want_next = NEXT_FOR_ENDING.get(ending, ())
    got_next = sorted({a[1] for a in rep.next_argvs()})
    t.eq(name + ".next", got_next, sorted(want_next))
    if fx is not None:
        t.eq(name + ".usage", d.get("usage"), fx.totals(fx.exchanges_of(name)))
        if limits is not None:
            t.eq(name + ".allowances", d.get("allowances"), fp.allowances(fx.totals(), limits))
    if seal_actor is not None:
        t.eq(name + ".seal.actor", (d.get("seal") or {}).get("actor"), seal_actor)
        t.eq(name + ".effects.seal", rep.effects.get("seal"), "recorded")
    if delivery_outcome is not None:
        t.eq(name + ".delivery.outcome", (d.get("delivery") or {}).get("outcome"), delivery_outcome)
        t.eq(name + ".effects.delivery", rep.effects.get("delivery"), delivery_outcome)


def limits_of(sub):
    return {"turns": sub.limits[0], "input_tokens": sub.limits[1], "output_tokens": sub.limits[2]}


def provider_expected(ex, request, attempt):
    """run_ended.provider / data.provider for a placement whose last attempt the fake answered
    in exchange ex: what the fake sent (fp.provider_facts), then the request and attempt."""
    if ex is None:
        return "no exchange"
    out = dict(fp.provider_facts(ex))
    out["request"], out["attempt"] = request, attempt
    return out


def run_ended_of(t, sub, run_number):
    """The run_ended body of a placement, or None."""
    for b in t.log_bodies(sub, "run_ended"):
        if isinstance(b, dict) and b.get("run") == run_number:
            return b
    return None


def check_run_ended(t, sub, run_number, name, *, ending=None, cause=_UNSET, provider=_UNSET, requests=None,
                    attempts=None):
    """The run_ended record of a placement (4.4): its ending and cause, provider (keys in order
    for a provider cause, else null; exact when given), and its request and attempt counts."""
    b = run_ended_of(t, sub, run_number)
    if not t.check(name + ".run_ended.present", b is not None, "no run_ended for run %d" % run_number):
        return None
    if ending is not None:
        t.eq(name + ".run_ended.ending", b.get("ending"), ending)
    if cause is not _UNSET:
        t.eq(name + ".run_ended.cause", b.get("cause"), cause)
    prov = b.get("provider", "missing")
    if b.get("cause") in PROVIDER_CAUSES:
        t.eq(name + ".run_ended.provider-keys", list(prov) if isinstance(prov, dict) else prov, list(PROVIDER_FACT_KEYS))
    else:
        t.eq(name + ".run_ended.provider-null", prov, None)
    if provider is not _UNSET:
        t.eq(name + ".run_ended.provider", prov, provider)
    if requests is not None:
        t.eq(name + ".run_ended.requests", b.get("requests"), requests)
    if attempts is not None:
        t.eq(name + ".run_ended.attempts", b.get("attempts"), attempts)
    return b


def check_rejection(t, sub, fx, rep, name, *, run_number, request=1):
    """A provider's refusal of a request reported as the provider gave it (INTERFACE 6.5, 6.6;
    ACCEPTANCE C9 "Provider rejections"). The placement made one attempt (the fake saw one
    exchange: `<name>.attempts`); it ended interrupted with cause provider_rejected and exit 5;
    the run reply and run_ended give the status, error type, error message (cut as 4.5 cuts it)
    and request ID exactly as the fake sent them, or null where it sent none (`.provider`,
    `.run_ended.provider`); the attempt record says http_error with that status and error and
    then end, charged nothing (`.then`, `.attempt-record`); and the raw response capture holds
    the body the fake sent (`.response-capture`). Returns the expected provider facts."""
    exs = fx.exchanges_of(name)
    t.eq(name + ".attempts", len(exs), 1)
    ex = exs[-1] if exs else None
    want = provider_expected(ex, request, 1)
    check_run_reply(t, rep, sub, name, ending="interrupted", cause="provider_rejected", run_number=run_number,
                    fx=fx, limits=limits_of(sub), provider=want)
    t.eq(name + ".exit", rep.rc, 5)
    check_run_ended(t, sub, run_number, name, ending="interrupted", cause="provider_rejected", provider=want,
                    requests=request, attempts=1)
    rd = run_dirs(sub).get(run_number)
    if not t.check(name + ".run-dir", rd is not None, sorted(run_dirs(sub))):
        return want
    body = fp.response_body(ex) if ex is not None else None
    t.check(name + ".response-capture", body is not None and rd.responses.get((request, 1)) == body,
            {"captured": short(rd.responses.get((request, 1)), 300), "sent": short(body, 300)})
    rec = ((rd.attempts.get((request, 1)) or {}).get("body") or {})
    t.eq(name + ".then", [((rd.attempts.get(k) or {}).get("body") or {}).get("then") for k in sorted(rd.attempts)],
         ["end"])
    if isinstance(want, dict):
        err = None
        if want["error_type"] is not None or want["error_message"] is not None or fp.error_body_facts(body)[2]:
            _, _, body_rid = fp.error_body_facts(body)
            err = {"type": want["error_type"], "message": want["error_message"], "request_id": body_rid}
        got = {k: rec.get(k) for k in ("outcome", "status", "error", "then", "delay_ms")}
        got["charged"] = (rec.get("charged") or {}).get("basis")
        got["response"] = {k: (rec.get("response") or {}).get(k) for k in ("file", "bytes", "sha256", "complete")}
        t.eq(name + ".attempt-record", got,
             {"outcome": "http_error", "status": want["status"], "error": err, "then": "end", "delay_ms": None,
              "charged": "none", "response": {"file": "response-%d-1.bin" % request, "bytes": len(body or b""),
                                              "sha256": sha256_hex(body or b""), "complete": True}})
    return want


# ---------------------------------------------------------------------------
# The archive's run captures (INTERFACE 4.5), read only for cross-checks.
# ---------------------------------------------------------------------------

class RunDir:
    """runs/<n>: raw captures and linked records, decoded the way 4.5 says."""

    NAME = re.compile(r"^(request-(\d+)\.json|response-(\d+)-(\d+)\.bin|attempt-(\d+)-(\d+)\.json|"
                      r"call-(\d+)\.json|result-(\d+)\.json|stage)$")

    def __init__(self, path):
        self.path = path
        self.requests, self.responses, self.attempts, self.calls, self.results = {}, {}, {}, {}, {}
        self.record_errors, self.unexpected, self.stage = {}, [], []
        try:
            names = sorted(os.listdir(path))
        except OSError:
            names = []
        for n in names:
            m = self.NAME.match(n)
            p = os.path.join(path, n)
            if not m:
                self.unexpected.append(n)
                continue
            if n == "stage":
                self.stage = sorted(os.listdir(p)) if os.path.isdir(p) else []
            elif m.group(2):
                self.requests[int(m.group(2))] = read_bytes(p)
            elif m.group(3):
                self.responses[(int(m.group(3)), int(m.group(4)))] = read_bytes(p)
            elif m.group(5):
                self.attempts[(int(m.group(5)), int(m.group(6)))] = self._record(p, n)
            elif m.group(7):
                self.calls[int(m.group(7))] = read_bytes(p)
            elif m.group(8):
                self.results[int(m.group(8))] = self._record(p, n)

    def _record(self, p, n):
        raw = read_bytes(p)
        try:
            obj = strict_loads(raw)
        except StrictJSONError as exc:
            self.record_errors[n] = str(exc)
            return None
        return obj

    def request_header(self, k):
        """The first line of request-<k>.json decoded, or None when cut off (4.5)."""
        raw = self.requests.get(k)
        if raw is None or not raw.endswith(b"]}\n"):
            return None
        node = rawjson.try_parse(raw[:-1])
        return node


def run_dirs(sub):
    base = os.path.join(sub.audit_dir, "runs")
    out = {}
    try:
        names = os.listdir(base)
    except OSError:
        return out
    for n in names:
        if n.isdigit():
            out[int(n)] = RunDir(os.path.join(base, n))
    return out


def access_log(sub):
    """ACCEPTANCE C6's access log (INTERFACE 4.5): over placements and calls in order, each call
    capture naming list, read or search, with its raw input bytes and its result's outcome."""
    out = []
    for n, rd in sorted(run_dirs(sub).items()):
        for c in sorted(rd.calls):
            node = rawjson.try_parse(rd.calls[c])
            name = node.get("name") if node is not None and node.kind == "object" else None
            try:
                tool = name.value() if name is not None else None
            except ValueError:
                tool = None
            if tool not in ("list", "read", "search"):
                continue
            inp = node.get("input")
            res = rd.results.get(c)
            out.append({"run": n, "call": c, "tool": tool, "input": inp.raw if inp is not None else None,
                        "outcome": res.get("body", {}).get("outcome") if isinstance(res, dict) and isinstance(
                            res.get("body"), dict) else "unknown"})
    return out


def check_run_records(t, sub, name):
    """Every attempt and result record decodes strictly with the record header (4.3, 4.5)."""
    for n, rd in sorted(run_dirs(sub).items()):
        t.check("%s.runs.%d.names" % (name, n), not rd.unexpected, rd.unexpected)
        t.check("%s.runs.%d.records-strict" % (name, n), not rd.record_errors, rd.record_errors)
        for key, rec in list(rd.attempts.items()) + list(rd.results.items()):
            if rec is None:
                continue
            kind = "provider_attempt" if key in rd.attempts and rd.attempts[key] is rec else "tool_result"
            ok = (isinstance(rec, dict) and set(rec) == {"record", "kind", "audit", "writer", "at", "body"}
                  and rec.get("record") == RECORD_SCHEMA and rec.get("audit") == sub.audit and rec.get("kind") == kind)
            t.check("%s.runs.%d.record-header" % (name, n), ok, {"record": key, "header": {k: rec.get(k) for k in
                                                                                         ("record", "kind", "audit")}})


# ---------------------------------------------------------------------------
# Witness comparisons.
# ---------------------------------------------------------------------------

def arrangement_member_raw(sub, member):
    """Raw bytes of a member of the arrangement pinned at prepare (the driver's copy)."""
    arr = sub.arrangement.get(sub.accepted_handle) if sub.accepted_handle else None
    if not arr:
        return None
    node = rawjson.try_parse(arr["machine"])
    if node is None or node.kind != "object":
        return None
    m = node.get(member)
    if m is None and node.get("body") is not None:
        m = node.get("body").get(member)
    return m.raw if m is not None else None


def pinned_request_extra(sub):
    """The request_extra value of the arrangement pinned at prepare, parsed, or None."""
    raw = arrangement_member_raw(sub, "request_extra")
    node = rawjson.try_parse(raw) if raw is not None else None
    if node is None:
        return None
    try:
        v = node.value()
        return json.loads(v) if isinstance(v, str) else v
    except ValueError:
        return None


def check_requests(t, fx, sub, name, *, family=None, exchanges=None):
    """6.1 and 6.2 for every request the fake received: request line, exactly the seven headers in
    the listed order (literal reading of 6.1), and a body spliced as 4.5 states from the pinned
    model, system and tools bytes and the request_extra members (the effort: `output_config`
    after `tools` exactly when the front matter sets one), with nothing else and no whitespace."""
    family = family or sub.family
    want_sys = expected_system_bytes(family)
    want_tools = expected_tools(family)
    pinned_tools = arrangement_member_raw(sub, "tools")
    pinned_sys = arrangement_member_raw(sub, "system")
    want_x = effort_bytes(sub)
    want_extra = expected_request_extra(sub)
    pinned_extra = pinned_request_extra(sub)
    if sub.accepted_handle and sub.arrangement.get(sub.accepted_handle):
        t.eq(name + ".request-extra-pinned", pinned_extra, want_extra)
        for member, expected in (("anthropic_beta", ANTHROPIC_BETA), ("compaction", COMPACTION)):
            raw = arrangement_member_raw(sub, member)
            t.eq(name + "." + member + "-pinned", rawjson.parse(raw).value() if raw else None, expected)
    for ex in exchanges if exchanges is not None else fx.exchanges:
        p = "%s.request-%d" % (name, ex.n)
        t.check(p + ".complete", ex.problem is None, ex.problem)
        t.eq(p + ".line", ex.request_line, "POST %s/v1/messages HTTP/1.1" % fx.path)
        t.eq(p + ".header-names", [h[0] for h in ex.headers], list(fp.REQUEST_HEADER_NAMES))
        hv = dict((h[0].lower(), h[1]) for h in ex.headers)
        t.eq(p + ".host", hv.get("host"), fx.host_header)
        t.check(p + ".key", hv.get("x-api-key") == fx.key, "x-api-key is not the key given")
        t.eq(p + ".version", hv.get("anthropic-version"), API_VERSION)
        t.eq(p + ".beta", hv.get("anthropic-beta"), ANTHROPIC_BETA)
        t.eq(p + ".content-type", hv.get("content-type"), "application/json")
        t.eq(p + ".content-length", hv.get("content-length"), str(len(ex.body or b"")))
        t.eq(p + ".connection", hv.get("connection"), "close")
        node = ex.body_node()
        if not t.check(p + ".body-json", node is not None and node.kind == "object", (ex.body or b"")[:200]):
            continue
        summary = node.get("compaction") is not None
        cx = b',"compaction":{"type":"summarize"}' if summary else b""
        if summary:
            t.eq(p + ".compaction", node.get("compaction").raw, b'{"type":"summarize"}')
        t.eq(p + ".body-keys", node.keys(), ["model", "max_tokens", "system", "tools"]
             + (["output_config"] if want_x else []) + (["compaction"] if summary else []) + ["messages"])
        oc = node.get("output_config")
        t.eq(p + ".effort", None if oc is None else b',"output_config":' + oc.raw, want_x or None)
        if pinned_extra is not None:
            sent = {k: c.value() for k, _, _, c in node.members
                    if k not in ("model", "max_tokens", "system", "tools", "compaction", "messages")}
            t.eq(p + ".request-extra-sent", sent, pinned_extra)
        mt = ex.max_tokens()
        t.check(p + ".max-tokens", isinstance(mt, int) and 1024 <= mt <= MAX_TOKENS_PER_REQUEST, mt)
        t.eq(p + ".model", node.get("model").raw if node.get("model") else None, fp.jstr(sub.model))
        t.check(p + ".system-bytes", node.get("system") is not None and node.get("system").raw == want_sys,
                "system differs from the pinned orientation and family instructions")
        tools = node.get("tools")
        t.check(p + ".tools", tools is not None and tools.value() == want_tools,
                [x.get("name") for x in (tools.value() if tools is not None else [])])
        if pinned_tools is not None:
            t.check(p + ".tools-pinned-bytes", tools is not None and tools.raw == pinned_tools,
                    "tools bytes differ from the arrangement pinned at prepare")
        if pinned_sys is not None and pinned_sys.startswith(b"["):
            t.check(p + ".system-pinned-bytes", node.get("system").raw == pinned_sys, "system differs from arrangement")
        msgs = node.get("messages")
        if msgs is not None and tools is not None:
            splice = (b'{"model":' + fp.jstr(sub.model) + b',"max_tokens":%d' % (mt if isinstance(mt, int) else -1)
                      + b',"system":' + want_sys + b',"tools":' + tools.raw + want_x + cx + b',"messages":' + msgs.raw
                      + b"}")
            t.check(p + ".spliced", ex.body == splice, "body is not exactly the 4.5 splice (whitespace or extra members)")
            t.check(p + ".messages-compact", b"\n" not in msgs.raw, "newline in messages")


def is_compaction_request(ex):
    node = ex.body_node()
    return node is not None and node.get("compaction") is not None


def reconstruct_request(sub, capture, active):
    """Rebuild 4.5 bytes from retained captures and the independently saved arrangement.
    Returns (active messages, body, capture header); raises for malformed captures.
    No provider witness is consulted here: the caller compares against that witness."""
    if not capture.endswith(b"]}\n"):
        raise ValueError("incomplete request capture")
    node = rawjson.parse(capture[:-1])
    keys = ["request", "max_tokens", "body_bytes", "body_sha256", "compaction", "reset", "appended"]
    if node.keys() != keys:
        raise ValueError("request capture keys/order differ: %r" % node.keys())
    header = node.value()
    if type(header["compaction"]) is not bool or type(header["reset"]) is not bool:
        raise ValueError("compaction/reset must be booleans")
    arr = node.get("appended")
    if arr is None or arr.kind != "array":
        raise ValueError("appended is not an array")
    active = ([] if header["reset"] else list(active)) + [m.raw for m in arr.items]
    pinned = {k: arrangement_member_raw(sub, k) for k in ("model", "system", "tools", "request_extra")}
    if any(v is None for v in pinned.values()):
        raise ValueError("missing arrangement bytes")
    extra = rawjson.parse(pinned["request_extra"])
    x = b"".join(b"," + pinned["request_extra"][start:child.end] for _, start, _, child in extra.members)
    if header["compaction"]:
        x += b',"compaction":{"type":"summarize"}'
    body = (b'{"model":' + pinned["model"] + b',"max_tokens":%d' % header["max_tokens"]
            + b',"system":' + pinned["system"] + b',"tools":' + pinned["tools"] + x
            + b',"messages":[' + b",".join(active) + b"]}")
    if header["body_bytes"] != len(body) or header["body_sha256"] != sha256_hex(body):
        raise ValueError("reconstructed size/digest differs from capture")
    return active, body, header


def check_captures(t, sub, fx, name, run_number=1, exchanges=None):
    """Every original request remains reconstructable, and responses/charges match the fake.
    The fake's external witness survives even if the service loses a reset or an old capture."""
    rd = run_dirs(sub).get(run_number)
    if not t.check(name + ".captures.present", rd is not None, "no run directory"):
        return
    exs = list(exchanges if exchanges is not None else fx.exchanges_of(name))
    active, previous, k, a = [], None, 0, 0
    for ex in exs:
        if previous is None or previous.body != ex.body:
            k, a = k + 1, 1
            pre = "%s.capture.%d" % (name, k)
            try:
                active, body, header = reconstruct_request(sub, rd.requests.get(k, b""), active)
                t.eq(pre + ".body", body, ex.body)
                t.eq(pre + ".request", header["request"], k)
                t.eq(pre + ".compaction", header["compaction"], is_compaction_request(ex))
                t.eq(pre + ".reset", header["reset"], previous is not None and is_compaction_request(previous))
            except (ValueError, TypeError, KeyError) as exc:
                t.check(pre + ".reconstruct", False, str(exc))
        else:
            a += 1
        pre = "%s.capture.%d.%d" % (name, k, a)
        body = fp.response_body(ex)
        if body is not None:
            t.eq(pre + ".response", rd.responses.get((k, a)), body)
        rec = (rd.attempts.get((k, a)) or {}).get("body") or {}
        t.eq(pre + ".charged", rec.get("charged"), ex.charge)
        if isinstance(ex.step, fp.Message) and ex.charge and ex.charge.get("basis") == "reported":
            t.eq(pre + ".usage", rec.get("usage"), ex.step.usage.counts())
        previous = ex
    t.eq(name + ".captures.requests", sorted(rd.requests), list(range(1, k + 1)))
    t.eq(name + ".captures.attempts", len(rd.attempts), len(exs))


def conversations(exchanges):
    """Split exchanges into conversations of distinct requests: [[(request exchange, answering
    exchange or None)], ...]. A retry (same body) belongs to its request; the answering exchange is
    the last attempt that served a message."""
    convs, last_body = [], None
    for ex in exchanges:
        if ex.body is None:
            continue
        msgs = ex.messages()
        if ex.body == last_body and convs and convs[-1]:
            req, ans = convs[-1][-1]
            convs[-1][-1] = (req, ex if isinstance(ex.step, fp.Message) else ans)
            continue
        last_body = ex.body
        if msgs is not None and len(msgs) == 1:
            convs.append([])
        if not convs:
            convs.append([])
        convs[-1].append((ex, ex if isinstance(ex.step, fp.Message) else None))
    return convs


def check_history(t, fx, name, exchanges=None):
    """6.2: append exact responses and tool results, or replace context after a signed summary."""
    for ci, conv in enumerate(conversations(exchanges if exchanges is not None else fx.exchanges), 1):
        for i in range(1, len(conv)):
            (prev_req, prev_ans), (req, _) = conv[i - 1], conv[i]
            p = "%s.history.c%d.r%d" % (name, ci, i + 1)
            pm, m = prev_req.messages() or [], req.messages() or []
            if is_compaction_request(prev_req):
                t.eq(p + ".reset-two", len(m), 2)
                if prev_ans is not None and prev_ans.content_raw is not None:
                    t.eq(p + ".summary-exact", m[0].raw if m else None,
                         b'{"role":"assistant","content":' + prev_ans.content_raw + b"}")
                items = m[1].get("content") if len(m) > 1 else None
                first = items.items[0].value() if items is not None and items.kind == "array" and items.items else None
                t.eq(p + ".post-compaction", first, {"type": "text", "text": POST_COMPACTION})
                t.eq(p + ".after-summary-ordinary", is_compaction_request(req), False)
                continue
            t.eq(p + ".appended-two", len(m), len(pm) + 2)
            t.check(p + ".prefix", [x.raw for x in m[:len(pm)]] == [x.raw for x in pm], "earlier messages changed")
            if prev_ans is None or prev_ans.content_raw is None or len(m) < len(pm) + 2:
                continue
            t.eq(p + ".assistant-echo", m[len(pm)].raw,
                 b'{"role":"assistant","content":' + prev_ans.content_raw + b"}")
            user = m[len(pm) + 1]
            items = user.get("content").items if user.kind == "object" and user.get("content") is not None else []
            ids = []
            for b in items:
                tp = b.get("type") if b.kind == "object" else None
                if tp is not None and tp.raw == b'"tool_result"':
                    ids.append(b.get("tool_use_id").value() if b.get("tool_use_id") is not None else None)
            want = [blk.meta.get("id") for blk in prev_ans.tool_uses()]
            t.eq(p + ".tool-result-ids", ids, want)


def check_first_message(t, ex, question_body, continuing, name, notice=None):
    from driver_core import CONTINUATION, pinned_json_string
    blocks = [b'{"type":"text","text":' + pinned_json_string(question_body.decode("utf-8")).encode("utf-8") + b"}"]
    if continuing:
        blocks.append(b'{"type":"text","text":' + pinned_json_string(notice or CONTINUATION).encode("utf-8") + b"}")
    want = b'{"role":"user","content":[' + b",".join(blocks) + b"]}"
    msgs = ex.messages() or []
    t.check(name + ".first-message", len(msgs) == 1 and msgs[0].raw == want,
            {"expected": want[:300], "got": msgs[0].raw[:300] if msgs else None})


def collect_protocol_timings(t, fx, label):
    """C9: for a response with exactly one tool_use and stop_reason tool_use, the time from its
    last byte to the next request's connection. A search without explicit sources (the whole
    default scope) is reported but not gated."""
    exs = fx.exchanges_of(label)
    for a, b in zip(exs, exs[1:]):
        if not isinstance(a.step, fp.Message) or a.step.stop_reason != "tool_use" or b.n != a.n + 1:
            continue
        uses = a.step.tool_uses()
        if len(uses) != 1 or a.t_response_end is None or b.t_accept is None:
            continue
        am, bm = a.messages() or [], b.messages() or []
        if len(bm) != len(am) + 2:
            continue
        tool = uses[0].meta.get("name")
        inp = uses[0].meta.get("input") or {}
        if not inp and uses[0].meta.get("raw_input"):
            try:
                inp = json.loads(uses[0].meta["raw_input"].decode("utf-8"))
            except ValueError:
                inp = {}
        gated = not (tool == "search" and "sources" not in inp)
        t.protocol_timings.append({"tool": tool, "ms": round((b.t_accept - a.t_response_end) * 1000.0, 3),
                                   "gated": gated, "run": label, "request": a.n})


def check_access_log(t, sub, aud, name):
    """C6: the archive's access log equals the list/read/search calls the auditor made, in order,
    with their exact input bytes."""
    got = [(x["tool"], x["input"]) for x in access_log(sub)]
    want = [(c["tool"], c["raw_input"]) for c in sorted(aud.issued.values(), key=lambda c: c["id"])
            if c["tool"] in ("list", "read", "search")]
    t.eq(name + ".access-log", got, want)


def check_auditor(t, aud, name):
    """Turn the reacting auditor's anomalies into failed checks named auditor.<check>."""
    seen = set()
    for a in aud.anomalies:
        nm = "auditor.%s" % a["check"]
        if nm in seen:
            continue
        seen.add(nm)
        t.check(nm, False, a)
    t.check(name + ".auditor-clean", not aud.anomalies, [a["check"] for a in aud.anomalies][:20])


def check_run_ended_usage(t, sub, fx, labels, name):
    """C6: each run_ended's usage equals what the fake reported for that placement (6.4)."""
    bodies = t.log_bodies(sub, "run_ended")
    for i, label in enumerate(labels):
        if i >= len(bodies) or not isinstance(bodies[i], dict):
            t.check("%s.run_ended.%d.present" % (name, i + 1), False, "no run_ended record %d" % (i + 1))
            continue
        t.eq("%s.run_ended.%d.usage" % (name, i + 1), bodies[i].get("usage"), fx.totals(fx.exchanges_of(label)))


def expected_return(aud, revision, *, audit, store, family_id, writer, actor, sealed_at):
    """member name -> expected bytes of the return package (8.2) from the auditor's witness."""
    ents = aud.expected_selection(revision)
    aj = aw.answer_json(revision, ents)
    md = aw.render(ents)
    files = {"answer.json": aj}
    if md is not None:
        files["answer.md"] = md
    for e in ents:
        if e.kind == "record_artifact" and not e.unproduced:
            files[e.member] = e.data
    man = aw.manifest(audit, store, family_id, writer, actor, sealed_at, revision, aw.members(ents, aj, md),
                      aw.unproduced(ents))
    files["manifest.json"] = man
    return files


def check_package(t, path, expected, name):
    """A delivered package holds exactly the expected members, byte for byte, 0700/0600 (8.2)."""
    try:
        names = sorted(os.listdir(path))
    except OSError as exc:
        t.check(name + ".package-readable", False, str(exc))
        return
    t.eq(name + ".package-members", names, sorted(expected))
    st = os.lstat(path)
    t.eq(name + ".package-mode", oct(st.st_mode & 0o7777), oct(0o700))
    for n in names:
        p = os.path.join(path, n)
        st = os.lstat(p)
        t.eq("%s.member-mode.%s" % (name, n), oct(st.st_mode & 0o7777), oct(0o600))
        if n in expected:
            data = read_bytes(p)
            t.check("%s.member-bytes.%s" % (name, n), data == expected[n],
                    {"member": n, "got_sha256": sha256_hex(data), "expected_sha256": sha256_hex(expected[n]),
                     "got": short(data[:300].decode("utf-8", "replace")),
                     "expected": short(expected[n][:300].decode("utf-8", "replace"))})


# ---------------------------------------------------------------------------
# Procedure results, archive lookups and scans (stable API, also for cases_after_launch).
# ---------------------------------------------------------------------------

def check_fake(t, fx, prefix):
    """The fake itself worked: no responder exception or bad step (they are answered 400 and
    would otherwise look like a provider rejection), and no script exhausted."""
    t.check(prefix + ".fake-responder", not fx.provider.anomalies, fx.provider.anomalies[:3])
    ex = getattr(fx.responder, "exhausted", None)
    if ex is not None:
        t.check(prefix + ".fake-script", not ex, {"exhausted_at_exchanges": ex})


def check_procedure(t, p, prefix, fx=None):
    """Turn a procedure.Procedure's recorded checks into checks named <prefix>.<name>, and
    each anomaly (envelope, is_error, ordering, request after the end) into a failed check
    <prefix>.<anomaly>. With fx, also check_fake."""
    for name, ok, detail in p.checks:
        t.check("%s.%s" % (prefix, name), ok, detail)
    seen = set()
    for a in p.anomalies:
        nm = "%s.%s" % (prefix, a["check"])
        if nm not in seen:
            seen.add(nm)
            t.check(nm, False, a)
    if fx is not None:
        check_fake(t, fx, prefix)


def calls_and_results(sub):
    """[(run, call number, call capture bytes, result record or None)] over every placement."""
    out = []
    for n, rd in sorted(run_dirs(sub).items()):
        for c in sorted(set(rd.calls) | set(rd.results)):
            out.append((n, c, rd.calls.get(c), rd.results.get(c)))
    return out


def result_for(sub, tid, which=-1):
    """(run, call, capture bytes, result body) of the which-th call with this tool_use_id, or None."""
    if tid is None:
        return None
    rows = []
    for n, c, raw, rec in calls_and_results(sub):
        body = rec.get("body") if isinstance(rec, dict) else None
        node = rawjson.try_parse(raw) if raw else None
        cid = node.get("id") if node is not None and node.kind == "object" else None
        try:
            cid = cid.value() if cid is not None else (body or {}).get("tool_use_id")
        except ValueError:
            cid = None
        if cid == tid:
            rows.append((n, c, raw, body))
    try:
        return rows[which]
    except IndexError:
        return None


def result_envelope(body):
    """The reply envelope a result record carries in its first content block (4.5, 7.1)."""
    try:
        return strict_loads(body["content"][0]["text"].encode("utf-8"))
    except (KeyError, IndexError, TypeError, StrictJSONError, AttributeError):
        return None


def entry_bodies(t, sub):
    return [b for b in t.log_bodies(sub, "entry") if isinstance(b, dict)]


def package_of(rep):
    """The package path a run or close reply's delivery names (5.7), or None."""
    d = rep.data.get("delivery") if isinstance(rep.data, dict) else None
    loc = d.get("location") if isinstance(d, dict) else None
    return loc if isinstance(loc, str) else None


VERDICT_KEYS = ("verdict", "grade", "graded", "supports", "supported", "score", "quality", "passed", "assurance",
                "complete_answer", "correct")


def verdict_keys(obj, path=""):
    """Keys anywhere in obj that would grade an answer (C14); [] when none."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in VERDICT_KEYS:
                out.append(path + "/" + k)
            out += verdict_keys(v, path + "/" + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += verdict_keys(v, "%s/%d" % (path, i))
    return out


def wait_for(cond, timeout=15.0, interval=0.02):
    """Poll cond() until true or timeout; returns its last value."""
    import time
    deadline = time.time() + timeout
    while True:
        v = cond()
        if v or time.time() >= deadline:
            return v
        time.sleep(interval)


def read_package_member(loc, name):
    try:
        return read_bytes(os.path.join(loc, name))
    except (OSError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Self-tests: the harness's witness comparisons over real loopback traffic from
# mini_stewart (a stand-in, not Stewart), passing on correct traffic and firing on
# four broken variants.
# ---------------------------------------------------------------------------

class _StubT:
    """Just enough of T for the fixture and the comparisons."""

    def __init__(self, root):
        self.root = self.evid = root
        self.checks, self.protocol_timings, self.cleanups = [], [], []
        self.bin = {"kind": "test"}

    def check(self, name, cond, detail=None):
        self.checks.append((name, bool(cond), detail))
        return bool(cond)

    def eq(self, name, actual, expected):
        return self.check(name, actual == expected, {"actual": actual, "expected": expected})

    def mkdir(self, *parts):
        p = os.path.join(self.root, *parts)
        os.makedirs(p, exist_ok=True)
        return p

    def cleanup(self, fn):
        self.cleanups.append(fn)


class _StubSub:
    def __init__(self, effort=None):
        self.model, self.family, self.accepted_handle, self.arrangement = "claude-opus-5-5", "open-inquiry", None, {}
        self.effort = effort


def _harness_round(faults, effort=None, accepts=None):
    import tempfile
    import mini_stewart
    import reacting_auditor as ra
    root = tempfile.mkdtemp(prefix="stewart-driver-harness-")
    try:
        t = _StubT(root)
        q, mats = ra._scenario_material()
        aud = ra.ReactingAuditor(ra._goals(mats), question=q, materials=mats, calls_per_turn=1)
        fx = ProviderFixture(t, aud, mode="http", accepts=accepts).start()
        try:
            fx.mark("sim")
            port = int(fx.url.rsplit(":", 1)[1])
            sim = mini_stewart.MiniStewart(aud, q, mats, faults=faults, ledger=fx.provider,
                                           send=mini_stewart.http_sender(port, fx.key), effort=effort)
            ending = sim.run()
        finally:
            fx.stop()
        sub = _StubSub(effort)
        check_requests(t, fx, sub, "sim")
        check_history(t, fx, "sim")
        if fx.exchanges:
            check_first_message(t, fx.exchanges[0], q, False, "sim")
        collect_protocol_timings(t, fx, "sim")
        return ending, aud, t
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _selftest_harness():
    out = []
    try:
        ending, aud, t = _harness_round(())
    except Skip as exc:
        return [("harness.loopback", None, "skipped: %s" % exc)]
    bad = [c for c in t.checks if not c[1]]
    out.append(("harness.sim-sealed", ending == "sealed" and not aud.anomalies, (ending, aud.anomalies[:3])))
    out.append(("harness.checks-pass", not bad and len(t.checks) > 50, bad[:3]))
    out.append(("harness.protocol-timings", len(t.protocol_timings) > 5 and all(x["ms"] >= 0 for x in t.protocol_timings),
                t.protocol_timings[:3]))
    # The fixture gives a reacting auditor its fake, so allowance and notice checks run.
    import tempfile
    import reacting_auditor as ra
    root = tempfile.mkdtemp(prefix="stewart-driver-wire-")
    try:
        q, mats = ra._scenario_material()
        aud = ra.ReactingAuditor([], question=q, materials=mats,
                                 limits={"turns": 1, "input_tokens": 1, "output_tokens": 1})
        fx = ProviderFixture(_StubT(root), aud, mode="http").start()
        fx.stop()
        out.append(("harness.auditor-gets-provider", aud.provider is fx.provider))
    except Skip as exc:
        out.append(("harness.auditor-gets-provider", None, "skipped: %s" % exc))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    for fault, prefix in (("body_whitespace", ".spliced"), ("extra_header", ".header-names"),
                          ("extra_tool", ".tools"), ("drop_history", ".prefix")):
        _, _, t = _harness_round((fault,))
        fired = [c[0] for c in t.checks if not c[1] and c[0].endswith(prefix)]
        out.append(("harness.control.%s" % fault, bool(fired), [c[0] for c in t.checks if not c[1]][:5]))
    # The effort (6.2 request_extra): accepted by the pinned API version's model and spliced after
    # tools; a commission without one is accepted by a provider that has no output_config at all.
    ending, aud, t = _harness_round((), effort="high", accepts=fp.MESSAGES_API)
    bad = [c for c in t.checks if not c[1]]
    out.append(("harness.effort.sealed", ending == "sealed" and not aud.anomalies, (ending, aud.anomalies[:3])))
    out.append(("harness.effort.checks-pass", not bad and any(c[0].endswith(".effort") for c in t.checks), bad[:3]))
    ending, _, t = _harness_round((), accepts=fp.MESSAGES_API.without("output_config"))
    bad = [c for c in t.checks if not c[1]]
    out.append(("harness.no-effort.accepted-without-output-config", ending == "sealed" and not bad, (ending, bad[:3])))
    for fault, suffixes in (("misspell_effort", (".effort", ".spliced")),
                            ("effort_in_prompt", (".effort", ".body-keys", ".first-message"))):
        ending, _, t = _harness_round((fault,), effort="high", accepts=fp.MESSAGES_API)
        failed = [c[0] for c in t.checks if not c[1]]
        out.append(("harness.control.%s" % fault, all(any(f.endswith(sfx) for f in failed) for sfx in suffixes),
                    (ending, failed[:8])))
    return out


def _selftest_rejection_witness():
    """check_rejection over records written by hand as INTERFACE 4.4 and 4.5 describe them, for a
    refusal the gate actually served: it passes on the specified shape and fires when the
    message is hidden (hide_provider_message's shape) and when the 400 is retried and reported
    as unavailability (rejection_as_unavailable's shape)."""
    import socket
    import tempfile
    import threading
    out = []
    root = tempfile.mkdtemp(prefix="stewart-driver-rejection-")
    try:
        exs = []
        prov = fp.FakeProvider(fp.Gate(fp.MESSAGES_API.without("output_config"), fp.Script([])))
        body = (b'{"model":"m","max_tokens":16000,"system":[],"tools":[],"output_config":{"effort":"high"},'
                b'"messages":[{"role":"user","content":[{"type":"text","text":"q"}]}]}')
        for _ in range(4):
            a, b = socket.socketpair()
            th = threading.Thread(target=prov.handle_connection, args=(a,), daemon=True)
            th.start()
            b.sendall(fp.stewart_request("127.0.0.1:1", "sk-test", body))
            fp.read_response(b)
            th.join(5)
            b.close()
        exs = prov.exchanges

        class Fx:
            def __init__(self, exchanges):
                self.exchanges = exchanges

            def exchanges_of(self, label):
                return self.exchanges

            def totals(self, exchanges=None, upto=None):
                return fp.totals(self.exchanges if exchanges is None else exchanges)

        class Sub:
            accepted_handle, arrangement, limits = None, {}, (200, 20000000, 400000)
            audit, ref, writer = "a" + "a" * 16, "stw1:ref", "/usr/local/bin/stewart"

        class Rep:
            def __init__(self, data, rc):
                self.data, self.rc, self.effects = data, rc, {"run": "ended"}
                self.next = []

            def next_argvs(self):
                return [[Sub.writer, "run", Sub.ref], [Sub.writer, "close", Sub.ref]]

        class StubT(_StubT):
            def log_bodies(self, sub, kind):
                return list(sub.log.get(kind, []))

        def round_(label, n_attempts, cause, hide=False):
            d = os.path.join(root, label)
            sub = Sub()
            sub.audit_dir = d
            os.makedirs(os.path.join(d, "runs", "1"))
            used = exs[:n_attempts]
            facts = fp.provider_facts(used[-1])
            if hide:
                facts["error_message"] = None
            prov_rec = dict(facts, request=1, attempt=n_attempts)
            for i, ex in enumerate(used, 1):
                rb = fp.response_body(ex)
                with open(os.path.join(d, "runs", "1", "response-1-%d.bin" % i), "wb") as f:
                    f.write(rb)
                et, em, rid = fp.error_body_facts(rb)
                rec = {"record": RECORD_SCHEMA, "kind": "provider_attempt", "audit": sub.audit, "writer": "0" * 64,
                       "at": "2026-10-31T00:00:00.000Z",
                       "body": {"request": 1, "attempt": i, "outcome": "http_error", "status": facts["status"],
                                "response": {"file": "response-1-%d.bin" % i, "bytes": len(rb),
                                             "sha256": sha256_hex(rb), "complete": True},
                                "error": {"type": et, "message": em, "request_id": rid},
                                "charged": {"basis": "none", "turns": 0, "input_tokens": 0, "output_tokens": 0},
                                "then": "end" if i == n_attempts else "retry",
                                "delay_ms": None if i == n_attempts else 0}}
                with open(os.path.join(d, "runs", "1", "attempt-1-%d.json" % i), "wb") as f:
                    f.write(json.dumps(rec, separators=(",", ":")).encode() + b"\n")
            zero = fp.totals([])
            sub.log = {"run_ended": [{"prev": None, "run": 1, "ending": "interrupted", "cause": cause,
                                      "recorded_by": "run", "provider": prov_rec, "requests": 1,
                                      "attempts": n_attempts, "usage": zero}]}
            data = {"run": 1, "continuing": False, "ending": "interrupted", "cause": cause, "provider": prov_rec,
                    "usage": zero, "allowances": fp.allowances(zero, limits_of(sub)), "answer": None, "seal": None,
                    "delivery": None, "notices": []}
            t = StubT(d)
            check_rejection(t, sub, Fx(used), Rep(data, 5), "w", run_number=1)
            return [c[0] for c in t.checks if not c[1]], len(t.checks)

        failed, n = round_("specified", 1, "provider_rejected")
        out.append(("rejection-witness.passes", not failed and n >= 15, failed))
        failed, _ = round_("hidden", 1, "provider_rejected", hide=True)
        out.append(("rejection-witness.control.hide_provider_message",
                    "w.provider" in failed and "w.run_ended.provider" in failed, failed))
        failed, _ = round_("retried", 4, "provider_unavailable")
        out.append(("rejection-witness.control.rejection_as_unavailable",
                    {"w.attempts", "w.cause", "w.then", "w.run_ended.attempts"} <= set(failed), failed))
    except Skip as exc:
        out.append(("rejection-witness", None, "skipped: %s" % exc))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return out


try:
    from driver_core import selftest as _selftest
    _selftest(_selftest_harness)
    _selftest(_selftest_rejection_witness)
except ImportError:  # pragma: no cover
    pass
