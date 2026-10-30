# -*- coding: utf-8 -*-
"""Run cases: the run adapter and the answer protocol after launch (ACCEPTANCE C1-C4,
C6, C7, C9 protocol timing, C12-C14, C20 tool replies, traces T5-T8, T12, T13, T15, T16).

Each case drives `stewart run` against the fake Messages API on loopback
(run_support.provider) and judges it against the driver's witnesses: what the
fake received, what the reacting auditor recorded, and answer_witness's
expected bytes. Written from docs/INTERFACE.md, docs/QUESTION-FORMS.md,
CONTRACTS.md and ACCEPTANCE.md without reading service/.

Delivery, close and status after launch (C5, C8, C16, C18 after launch, T8-T10,
T14) belong in their own module; they reuse run_support the same way.
"""
from __future__ import annotations

import os
import signal

import json

import answer_witness as aw
import fake_provider as fp
import run_support as rs
from driver_core import *  # noqa: F401,F403
from procedure import Procedure, find_hits, first_message_bytes
from reacting_auditor import Goal, ReactingAuditor


# ---------------------------------------------------------------------------
# Shared scenario material.
# ---------------------------------------------------------------------------

def long_question():
    """A question over one read page (7.2) whose essential sentence is on the last page (C4)."""
    head = "Audit the reminder service: can a reminder be sent twice?\n"
    filler = "".join("Background note %05d: the service was described by its authors.\n" % i for i in range(1100))
    return (head + filler + "Essential: cover what happens across a restart.\n").encode("utf-8")


def scenario_entries():
    return [F("a.py", b"def send(r):\n    deliver(r)\n    mark_sent(r)\n"),
            F("notes/R1.txt", "R1. A reminder ID is sent at most once.\r\nrésumé line\r\n".encode("utf-8")),
            F("empty.txt", b"")]


def scenario_goals(sub):
    a = sub.files[b"a.py"]["data"]
    s = a.find(b"deliver(r)")
    return [
        Goal("account", "Restarts can duplicate a send; the materials do not show recovery.", kind="record_account",
             draft="Draft account.", citations=[{"source": "materials/notes/R1.txt", "quote": "at most once"}]),
        Goal("delivery before marking", "deliver(r) runs before mark_sent(r).",
             citations=[{"source": "materials/a.py", "start": s, "end": s + 10}],
             bad_first=({"citations": [{"source": "materials/a.py", "start": s, "end": s + 10, "quote": "deliver(x)"}]},
                        "citation_invalid")),
        Goal("restart window", "A stop between the two calls leaves the reminder unmarked.\n",
             citations=[{"source": "question", "quote": "Essential: cover what happens across a restart."}]),
        Goal("scope", "Only two non-empty files were supplied.", kind="record_limit"),
        Goal("trace", "send -> deliver -> mark_sent\n", kind="record_artifact", artifact="text"),
    ]


def auditor_for(t, sub, goals, **kw):
    sources = {sub.public(rel): w["data"] for rel, w in sub.files.items() if "data" in w}
    forbidden = forbidden_for(sub)
    return ReactingAuditor(goals, question=sub.body, materials=sources, family=sub.family,
                           limits=rs.limits_of(sub), forbidden=forbidden, model=sub.model, **kw)


def run_submission(t, entries=None, body=None, **kw):
    sub = t.submission(entries if entries is not None else scenario_entries(), body=body or long_question(),
                       dest_watch="additions", **kw)
    t.accept(sub)
    return sub


# ---------------------------------------------------------------------------
# C12: the run's environment boundary.
# ---------------------------------------------------------------------------

@case("c12.run-environment", ["C12", "C20", "C14"],
      "run refuses a missing or invalid key, provider URL or proxy before any request",
      needs=("loopback",))
def c_run_environment(t):
    """Before acceptance run refuses not_accepted. After it, each bad environment refuses
    before any request with effects {not_started, unchanged, none, none}, no run_started and
    the same run line offered: no key, an empty key, keys with bytes outside 0x21-0x7E; provider
    URLs with another scheme, user information, a query, a fragment or a trailing slash; proxies
    that are not http://host:port. The fake records no exchange. A non-loopback http:// URL is
    tried only on a network-isolated run. Status stays not_started."""
    pre = t.submission(scenario_entries(), dest_watch="additions")
    t.new_ref(pre, name="env.pre.new")
    t.prepare(pre, name="env.pre.prepare")
    fx = rs.provider(t, fp.Script([]))
    rep = rs.run(t, pre, fx, name="env.not-accepted", expect="refused", reason="not_accepted")
    rs.check_refused_before_request(t, rep, pre, fx, "env.not-accepted", next_run=False)
    sub = run_submission(t)
    port = fx.url.rsplit(":", 1)[1]
    specimens = [
        ("key-missing", {"ANTHROPIC_API_KEY": None}, "provider_key_missing"),
        ("key-empty", {"ANTHROPIC_API_KEY": ""}, "provider_key_missing"),
        ("key-space", {"ANTHROPIC_API_KEY": "sk-ant x"}, "provider_key_invalid"),
        ("key-non-ascii", {"ANTHROPIC_API_KEY": "sk-ant-é"}, "provider_key_invalid"),
        ("url-scheme", {"STEWART_PROVIDER_URL": "ftp://127.0.0.1:%s" % port}, "provider_url_invalid"),
        ("url-userinfo", {"STEWART_PROVIDER_URL": "http://user@127.0.0.1:%s" % port}, "provider_url_invalid"),
        ("url-query", {"STEWART_PROVIDER_URL": "http://127.0.0.1:%s?x=1" % port}, "provider_url_invalid"),
        ("url-fragment", {"STEWART_PROVIDER_URL": "http://127.0.0.1:%s#f" % port}, "provider_url_invalid"),
        ("url-trailing-slash", {"STEWART_PROVIDER_URL": "http://127.0.0.1:%s/" % port}, "provider_url_invalid"),
        # 6.1 read literally: a set proxy must be valid even when the loopback URL would not use it.
        ("proxy-https", {"HTTPS_PROXY": "https://127.0.0.1:%s" % port}, "provider_proxy_invalid"),
        ("proxy-credentials", {"HTTPS_PROXY": "http://u:p@127.0.0.1:%s" % port}, "provider_proxy_invalid"),
        ("proxy-no-port", {"HTTPS_PROXY": "http://127.0.0.1"}, "provider_proxy_invalid"),
        ("proxy-lowercase", {"https_proxy": "http://127.0.0.1:%s/x" % port}, "provider_proxy_invalid"),
    ]
    if t.drv.args.network_isolated:
        specimens.append(("url-http-not-loopback", {"STEWART_PROVIDER_URL": "http://provider.test:%s" % port},
                          "provider_url_invalid"))
    else:
        t.skip_part("url-http-not-loopback", "a faulty binary could reach out; tried only with --network-isolated")
    for label, env, reason in specimens:
        name = "env." + label
        rep = rs.run(t, sub, fx, name=name, env=env, expect="refused", reason=reason)
        rs.check_refused_before_request(t, rep, sub, fx, name)
    t.eq("env.no-exchanges", len(fx.exchanges), 0)
    t.eq("env.no-connections", [e for e in fx.provider.events if e.get("event") != "no_request"], [])
    st = t.status(sub, name="env.status")
    t.eq("env.status.condition", st.data.get("condition"), "not_started")


# ---------------------------------------------------------------------------
# The integrated end-to-end audit (C1, C2, C4, C5, C6, C9, C12).
# ---------------------------------------------------------------------------

@case("e2e.reacting-audit", ["C12", "C1", "C2", "C4", "C5", "C6", "C9", "C20"],
      "an audit end to end: the receipt's run line, a reacting auditor with a compaction, delivery, close",
      needs=("loopback",))
def c_e2e(t):
    """The commission's run line runs from an unrelated directory with another HOME against the
    fake. The reacting auditor reads the question (over one page, essential text on the last
    page) and every material, records five goals (one refused citation first, one draft then
    replaced, a text artifact), forgets everything at a compaction and re-enters, prepares,
    inspects both views, dry-runs and submits. The run ends sealed and delivers. Every request
    has the 6.1 shape and the 4.5 splice, history is echoed byte for byte, the access log equals
    the auditor's reads, run_ended usage equals the fake's charges, and the package equals the
    witness. Status from a third directory reports the auditor seal and the verified delivery;
    an ordinary close then closes it as delivered before close."""
    sub = run_submission(t)
    rep = t.cmd(["receipt", sub.ref], name="e2e.receipt", expect="completed")
    run_line = rep.data.get("run_line")
    t.require("e2e.run-line", run_line == [sub.writer, "run", sub.ref], run_line)
    aud = auditor_for(t, sub, scenario_goals(sub), compact_after=(3,), calls_per_turn=2)
    fx = rs.provider(t, aud)
    home, cwd = t.fresh_dir("run home"), t.fresh_dir("run cwd")
    rep = rs.run(t, sub, fx, name="e2e.run", env={"HOME": home}, cwd=cwd, timeout=900)
    rs.check_run_reply(t, rep, sub, "e2e.run", ending="sealed", run_number=1, fx=fx, limits=rs.limits_of(sub),
                       seal_actor="auditor", delivery_outcome="verified")
    rs.check_auditor(t, aud, "e2e")
    t.check("e2e.compacted", len(aud.compactions) == 1, aud.compactions)
    rs.check_requests(t, fx, sub, "e2e")
    rs.check_history(t, fx, "e2e")
    if fx.exchanges:
        rs.check_first_message(t, fx.exchanges[0], sub.body, False, "e2e")
    rs.check_access_log(t, sub, aud, "e2e")
    rs.check_run_records(t, sub, "e2e")
    rs.check_run_ended_usage(t, sub, fx, ["e2e.run"], "e2e")
    d = rep.data
    seal = d.get("seal") or {}
    loc = (d.get("delivery") or {}).get("location")
    if t.check("e2e.delivery-location", isinstance(loc, str) and loc.startswith(sub.dest + os.sep)
               and os.path.basename(loc) == "stewart-return-%s-001" % sub.audit, loc):
        want = rs.expected_return(aud, seal.get("revision"), audit=sub.audit, store=sub.store,
                                  family_id=sub.family + "/1", writer=t.bin["sha256"], actor="auditor",
                                  sealed_at=seal.get("sealed_at"))
        rs.check_package(t, loc, want, "e2e.package")
    st = t.status(sub, name="e2e.status", cwd=t.fresh_dir("status cwd"))
    hl = st.data.get("headline") or {}
    t.eq("e2e.status.condition", st.data.get("condition"), "delivered_open")
    t.eq("e2e.status.sealed", hl.get("sealed"), {"by": "auditor"})
    t.eq("e2e.status.delivered", hl.get("delivered"), {"verified": True, "confirmed": False, "location": loc})
    t.eq("e2e.status.closed", hl.get("closed"), "no")
    t.eq("e2e.status.allowances", st.data.get("allowances"), fp.allowances(fx.totals(), rs.limits_of(sub)))
    t.eq("e2e.status.provider", [st.data.get("provider_url_override"), st.data.get("provider_proxy")], [fx.url, None])
    rep = t.cmd(["close", sub.ref], name="e2e.close", expect="completed")
    t.eq("e2e.close.closure", rep.data.get("closure"), "complete")
    t.eq("e2e.close.placement", rep.data.get("placement"), "delivered_before_close")
    t.eq("e2e.close.outcome", rep.data.get("outcome"), "closed_delivered")
    t.eq("e2e.close.provider-untouched", len(fx.exchanges), len(fx.exchanges_of("e2e.run")))


# ---------------------------------------------------------------------------
# C13 / T7: a kill after an entry, then continuation.
# ---------------------------------------------------------------------------

@case("c13.t7-kill-after-entry", ["C13", "C4", "C3", "C6", "C16"],
      "T7: killed after an entry is linked; status says interrupted; run continues without re-adding it",
      mode="test", needs=("loopback", "lock"),
      linux_reason="interruption is observed through the free OFD lock, a Linux-only expectation")
def c_t7(t):
    """entry.after_link=kill stops run 1 after its first entry and before the call's result.
    Status reports interrupted from a run_started without run_ended and a free lock. run REF
    records run_ended process_gone for run 1, starts run 2 whose first message carries the
    question and the continuation notice, and the reacting auditor, its memory gone, finds the
    entry through what_am_i_working_with and does not add it again. The run seals with every
    goal exactly once; run_ended usage of both runs equals the fake's charges."""
    sub = run_submission(t)
    aud = auditor_for(t, sub, scenario_goals(sub), calls_per_turn=1)
    fx = rs.provider(t, aud)
    rs.run(t, sub, fx, name="t7.run-1", fault="entry.after_link=kill", killed=True)
    st = t.status(sub, name="t7.status")
    t.eq("t7.status.condition", st.data.get("condition"), "interrupted")
    runs = st.data.get("runs") or {}
    t.eq("t7.status.runs", [runs.get("count"), runs.get("held"), runs.get("holder")], [1, False, None])
    t.check("t7.status.evidence", any("run_ended" in (e.get("evidence") or "") or "lock" in (e.get("evidence") or "")
                                      for e in st.data.get("evidence") or []), st.data.get("evidence"))
    r2 = rs.run(t, sub, fx, name="t7.run-2")
    rs.check_run_reply(t, r2, sub, "t7.run-2", ending="sealed", run_number=2, fx=fx, limits=rs.limits_of(sub),
                       seal_actor="auditor", delivery_outcome="verified")
    ended = t.log_bodies(sub, "run_ended")
    t.check("t7.run-1.reconciled", ended and ended[0].get("cause") == "process_gone"
            and ended[0].get("recorded_by") == "run" and ended[0].get("ending") == "interrupted", ended[:1])
    second = fx.exchanges_of("t7.run-2")
    if second:
        rs.check_first_message(t, second[0], sub.body, True, "t7.run-2")
    rs.check_auditor(t, aud, "t7")
    t.eq("t7.two-conversations", aud.conversations, 2)
    rs.check_requests(t, fx, sub, "t7")
    rs.check_history(t, fx, "t7")
    rs.check_run_ended_usage(t, sub, fx, ["t7.run-1", "t7.run-2"], "t7")


# ---------------------------------------------------------------------------
# T16: provider unavailable, rejected.
# ---------------------------------------------------------------------------

@case("t16.provider-unavailable", ["C13", "C6", "C14"],
      "T16: 529 four times ends interrupted provider_unavailable; retry-after 61 and 413 end after one attempt",
      needs=("loopback",))
def c_t16(t):
    """Run 1: four 529 overloaded_error answers with retry-after 0. Four attempts, three with
    then retry and one with then end, none charged; run_ended interrupted provider_unavailable
    with provider status 529 and error_type overloaded_error; exit 5. Every attempt carries the
    same request bytes. Run 2 (a continuation): retry-after 61 ends after one attempt, also
    provider_unavailable. Run 3: 413 request_too_large ends after one attempt, provider_rejected."""
    sub = run_submission(t)
    steps = [fp.HttpError(529, retry_after="0") for _ in range(4)]
    steps += [fp.HttpError(529, retry_after="61"), fp.HttpError(413)]
    fx = rs.provider(t, fp.Script(steps))
    for i, (label, n_attempts, cause, status) in enumerate((("t16.run-1", 4, "provider_unavailable", 529),
                                                            ("t16.run-2", 1, "provider_unavailable", 529),
                                                            ("t16.run-3", 1, "provider_rejected", 413)), 1):
        rep = rs.run(t, sub, fx, name=label, retry_delays=None)
        rs.check_run_reply(t, rep, sub, label, ending="interrupted", cause=cause, run_number=i, fx=fx,
                           limits=rs.limits_of(sub))
        t.eq(label + ".exit", rep.rc, 5)
        exs = fx.exchanges_of(label)
        t.eq(label + ".attempts", len(exs), n_attempts)
        t.check(label + ".same-bytes", len({e.body for e in exs}) == 1, [e.body_sha256() for e in exs])
        prov = rep.data.get("provider") or {}
        t.eq(label + ".provider", [prov.get("status"), prov.get("error_type")],
             [status, "overloaded_error" if status == 529 else "request_too_large"])
        rd = rs.run_dirs(sub).get(i)
        if t.check(label + ".run-dir", rd is not None, sorted(rs.run_dirs(sub))):
            thens = [(rd.attempts.get((1, a)) or {}).get("body", {}).get("then") for a in range(1, n_attempts + 1)]
            t.eq(label + ".then", thens, ["retry"] * (n_attempts - 1) + ["end"])
            charged = [(rd.attempts.get((1, a)) or {}).get("body", {}).get("charged") for a in range(1, n_attempts + 1)]
            t.check(label + ".charged-none", all(c == {"basis": "none", "turns": 0, "input_tokens": 0,
                                                       "output_tokens": 0} for c in charged), charged)
        if i > 1 and exs:
            rs.check_first_message(t, exs[0], sub.body, True, label)
    st = t.status(sub, name="t16.status")
    t.eq("t16.status.condition", st.data.get("condition"), "interrupted")


# ---------------------------------------------------------------------------
# C1 / 6.1: TLS through the CONNECT proxy, and an untrusted certificate.
# ---------------------------------------------------------------------------

@case("c1.tls-proxy", ["C1", "C12", "C20"],
      "HTTPS through HTTPS_PROXY: CONNECT provider.test:443, TLS end to end, recorded proxy; untrusted TLS fails",
      mode="test", needs=("loopback",))
def c_tls_proxy(t):
    """With STEWART_PROVIDER_URL https://provider.test, HTTPS_PROXY on loopback and the test
    root, every attempt goes through CONNECT provider.test:443 (host header provider.test:443),
    TLS with SNI provider.test, and the key never crosses the tunnel in clear. A turn ending
    twice gives the reminder and then ended_unsubmitted. run_started records the base URL, the
    override, the proxy and the API version; status shows the override and the proxy. A second
    audit whose server presents a certificate from another CA fails TLS on every attempt
    (connection_failed) and ends interrupted provider_unavailable without any request reaching
    the fake."""
    sub = run_submission(t)
    steps = [fp.Message([fp.text("Ending without submitting.")], stop_reason="end_turn"),
             fp.Message([fp.text("Ending again.")], stop_reason="end_turn")]
    fx = rs.provider(t, fp.Script(steps), mode="https-proxy")
    rep = rs.run(t, sub, fx, name="tls.run")
    rs.check_run_reply(t, rep, sub, "tls.run", ending="ended_unsubmitted", run_number=1, fx=fx,
                       limits=rs.limits_of(sub))
    t.eq("tls.transports", [e.transport for e in fx.exchanges], ["tls-via-proxy"] * 2)
    t.eq("tls.sni", [e.sni for e in fx.exchanges], [rs.PROVIDER_NAME] * 2)
    tunnels = fx.proxy.tunnels if fx.proxy else []
    t.eq("tls.connect-lines", [x.get("request") for x in tunnels], ["CONNECT provider.test:443 HTTP/1.1"] * 2)
    t.check("tls.connect-host", all([h[0].strip().lower() for h in x.get("headers") or []] == ["host"]
                                    and x["headers"][0][1].strip() == "provider.test:443" for x in tunnels),
            [x.get("headers") for x in tunnels])
    t.check("tls.key-not-in-clear", tunnels and all(x.get("key_seen_in_clear") is False for x in tunnels), tunnels)
    rs.check_requests(t, fx, sub, "tls")
    started = t.log_bodies(sub, "run_started")
    t.eq("tls.run_started.provider", (started[0] or {}).get("provider") if started else None,
         {"base_url": "https://provider.test", "override": True, "proxy": fx.proxy_url, "anthropic_version": API_VERSION})
    st = t.status(sub, name="tls.status")
    t.eq("tls.status.provider", [st.data.get("provider_url_override"), st.data.get("provider_proxy")],
         ["https://provider.test", fx.proxy_url])
    sub2 = run_submission(t)
    fx2 = rs.provider(t, fp.Script([]), mode="https-proxy", cert="untrusted", label="untrusted")
    rep = rs.run(t, sub2, fx2, name="tls.untrusted")
    rs.check_run_reply(t, rep, sub2, "tls.untrusted", ending="interrupted", cause="provider_unavailable",
                       run_number=1, fx=fx2, limits=rs.limits_of(sub2))
    t.eq("tls.untrusted.no-exchange", len(fx2.exchanges), 0)
    t.check("tls.untrusted.handshakes-failed", len([e for e in fx2.provider.events
                                                    if e.get("event") == "tls_handshake_failed"]) == 4,
            fx2.provider.events)
    rd = rs.run_dirs(sub2).get(1)
    if rd is not None:
        outs = [(rd.attempts.get((1, a)) or {}).get("body", {}).get("outcome") for a in range(1, 5)]
        t.eq("tls.untrusted.outcomes", outs, ["connection_failed"] * 4)


@case("c12.test-variables", ["C12", "C20", "C17"],
      "invalid test variables refuse run on the test build before any request; the release build ignores them",
      mode="both", needs=("loopback",))
def c_test_variables(t):
    """Appendix C (as amended): on the test build an out-of-range or malformed
    STEWART_TEST_PROVIDER_TIMEOUT or STEWART_TEST_RETRY_DELAYS refuses test_variable_invalid,
    and a missing, relative, empty, certificate-free or over-1-MiB STEWART_TEST_TLS_ROOT
    refuses test_tls_root_invalid, each before any request and publishing nothing. The TLS
    root is checked even for an http:// loopback provider (literal reading: "refuses run").
    The release build contains none of these names, so the same environment changes nothing:
    its run proceeds to an ordinary ending."""
    sub = run_submission(t)
    steps = [fp.Message([fp.text("Stopping.")], stop_reason="end_turn"),
             fp.Message([fp.text("Stopping again.")], stop_reason="end_turn")]
    fx = rs.provider(t, fp.Script(steps))
    d = t.mkdir("tls specimens")
    empty, keyonly, big = (os.path.join(d, n) for n in ("empty.pem", "key-only.pem", "big.pem"))
    open(empty, "wb").close()
    with open(fp.tls_file("ca.key"), "rb") as src, open(keyonly, "wb") as dst:
        dst.write(src.read())
    with open(fp.tls_file("ca.pem"), "rb") as src:
        pem = src.read()
    with open(big, "wb") as dst:
        dst.write(pem * ((1 << 20) // len(pem) + 2))
    bad = [("timeout-zero", {"STEWART_TEST_PROVIDER_TIMEOUT": "0"}, "test_variable_invalid"),
           ("timeout-601", {"STEWART_TEST_PROVIDER_TIMEOUT": "601"}, "test_variable_invalid"),
           ("timeout-word", {"STEWART_TEST_PROVIDER_TIMEOUT": "soon"}, "test_variable_invalid"),
           ("timeout-fraction", {"STEWART_TEST_PROVIDER_TIMEOUT": "1.5"}, "test_variable_invalid"),
           ("delays-two", {"STEWART_TEST_RETRY_DELAYS": "0,0"}, "test_variable_invalid"),
           ("delays-four", {"STEWART_TEST_RETRY_DELAYS": "0,0,0,0"}, "test_variable_invalid"),
           ("delays-over", {"STEWART_TEST_RETRY_DELAYS": "30001,0,0"}, "test_variable_invalid"),
           ("delays-negative", {"STEWART_TEST_RETRY_DELAYS": "-1,0,0"}, "test_variable_invalid"),
           ("delays-spaces", {"STEWART_TEST_RETRY_DELAYS": "0, 0, 0"}, "test_variable_invalid"),
           ("root-missing", {"STEWART_TEST_TLS_ROOT": os.path.join(d, "absent.pem")}, "test_tls_root_invalid"),
           ("root-relative", {"STEWART_TEST_TLS_ROOT": "ca.pem"}, "test_tls_root_invalid"),
           ("root-empty", {"STEWART_TEST_TLS_ROOT": empty}, "test_tls_root_invalid"),
           ("root-no-certificate", {"STEWART_TEST_TLS_ROOT": keyonly}, "test_tls_root_invalid"),
           ("root-over-1mib", {"STEWART_TEST_TLS_ROOT": big}, "test_tls_root_invalid")]
    if t.bin["kind"] == "test":
        for label, env, reason in bad:
            name = "testvars." + label
            rep = rs.run(t, sub, fx, name=name, env=env, expect="refused", reason=reason, retry_delays=None)
            rs.check_refused_before_request(t, rep, sub, fx, name)
        t.eq("testvars.no-exchanges", len(fx.exchanges), 0)
        st = t.status(sub, name="testvars.status")
        t.eq("testvars.status.condition", st.data.get("condition"), "not_started")
    else:
        env = {}
        for _, e, _ in bad:
            env.update(e)
        rep = rs.run(t, sub, fx, name="testvars.release-ignores", env=env)
        rs.check_run_reply(t, rep, sub, "testvars.release-ignores", ending="ended_unsubmitted", run_number=1, fx=fx,
                           limits=rs.limits_of(sub))
        t.eq("testvars.release-ignores.exchanges", len(fx.exchanges), 2)


# ---------------------------------------------------------------------------
# Helpers for scripted procedures.
# ---------------------------------------------------------------------------

def forbidden_for(sub):
    """Strings no auditor reply may carry (7.1, C20 views): host and archive paths, the
    reference, the store ID, the destination, and the family: its versioned identifier
    anywhere, its bare name as a whole value (the bare word is also part of tool names)."""
    return [sub.archive, sub.folder, sub.ref, sub.store, sub.dest, sub.family + "/1", "=" + sub.family]


def proc(sub, body, **kw):
    return Procedure(body, model=sub.model, forbidden=forbidden_for(sub), **kw)


def finish_ordinary(p, label="end"):
    """End the turn; after the reminder (6.4) end it again: an ordinary ending."""
    turn = yield p.end("I am stopping here.")
    p.check(label + ".reminder", turn.reminder and turn.texts == [REMINDER], turn.texts)
    yield p.end("Stopping again.")


def prepare_and_submit(p, label="seal"):
    turn = yield p.calls_step(("prepare", {}))
    r = turn.reply(0)
    p.eq(label + ".prepare", r.outcome if r else None, "completed")
    ap = r.data.get("prepared") if r else None
    yield p.calls_step(("submit", {"prepared": ap, "confirm": True}))
    return ap


def mat(sub, rel):
    return os.path.join(sub.folder, "materials", rel)


def has_int(obj, n):
    return any(isinstance(v, int) and not isinstance(v, bool) and v == n for v in iter_values(obj))


def last_call(p, tool):
    """The tool_use ID of the procedure's last call to tool, or None if it never made one."""
    ids = [c["id"] for c in p.calls.values() if c["tool"] == tool]
    return ids[-1] if ids else None


def material_bytes(sub, name):
    return sub.files[name.encode("utf-8")]["data"]


def sources_of(sub):
    out = {sub.public(rel): w["data"] for rel, w in sub.files.items() if "data" in w}
    out["question"] = sub.body
    return out


def default_scope(sub):
    return ["question"] + sorted((sub.public(rel) for rel in sub.files), key=lambda n: n.encode("utf-8"))


def answer_of(t, rep, name):
    """The delivered answer.json bytes of a run reply's package, or None."""
    loc = rs.package_of(rep)
    data = rs.read_package_member(loc, "answer.json") if loc else None
    t.check(name + ".delivered-answer", data is not None, loc)
    return data


# ---------------------------------------------------------------------------
# C1: the auditor's world is the arrangement.
# ---------------------------------------------------------------------------

@case("c1.requests", ["C1", "C7", "C20"],
      "every request carries exactly the family's pinned tools, system blocks, model and max_tokens",
      needs=("loopback",),
      controls=[Control("extra_tool", [r"^c1\..*\.(tools|tools-pinned-bytes|spliced)$"]),
                Control("arrangement_mismatch", [r"^c1\..*\.(system-bytes|system-pinned-bytes)$"])])
def c_c1_requests(t):
    """For each family an audit lists the materials and ends ordinarily. Every request has the
    6.1 shape and the 4.5 splice of the arrangement's pinned model, system and tools bytes (the
    driver's own copies from QUESTION-FORMS, and the arrangement.json pinned at prepare);
    the first max_tokens is 16,000. The receipt and run_started name the arrangement whose bytes
    were carried. Differing: the families' tool lists differ exactly by their recording tools,
    and their system blocks only in the second (instructions) block. Invariance: other
    materials leave the open-inquiry tools and system bytes unchanged."""
    raw = {}
    for label, family, entries in (("open-inquiry", "open-inquiry", None), ("inquiry-framing", "inquiry-framing", None),
                                   ("comparison", "comparison", None),
                                   ("other-materials", "open-inquiry", [F("other.txt", b"entirely different\n")])):
        sub = run_submission(t, entries=entries, family=family)

        def body(p):
            mats, _ = yield from p.list_all()
            p.check("listed", mats is not None, mats)
            yield from finish_ordinary(p)
        p = proc(sub, body)
        fx = rs.provider(t, p, label=label)
        pre = "c1.%s" % label
        rep = rs.run(t, sub, fx, name=pre + ".run")
        rs.check_run_reply(t, rep, sub, pre + ".run", ending="ended_unsubmitted", run_number=1, fx=fx,
                           limits=rs.limits_of(sub))
        rs.check_procedure(t, p, pre, fx)
        rs.check_requests(t, fx, sub, pre)
        rs.check_history(t, fx, pre)
        if not fx.exchanges:
            continue
        t.eq(pre + ".first-max-tokens", fx.exchanges[0].max_tokens(), MAX_TOKENS_PER_REQUEST)
        arr = sub.arrangement.get(sub.accepted_handle) or {}
        arr_sha = sha256_hex(arr.get("machine", b""))
        rc = t.cmd(["receipt", sub.ref], name=pre + ".receipt", expect="completed")
        t.check(pre + ".receipt-arrangement", contains_string(rc.data, arr_sha), "receipt lacks the arrangement digest")
        started = t.log_bodies(sub, "run_started")
        t.eq(pre + ".run_started.arrangement", (started[0] or {}).get("arrangement_sha256") if started else None, arr_sha)
        node = fx.exchanges[0].body_node()
        raw[label] = {"system": node.get("system").raw, "tools": node.get("tools").raw,
                      "system_value": node.get("system").value(),
                      "tool_names": [x.get("name") for x in node.get("tools").value()]}
    if {"open-inquiry", "comparison", "inquiry-framing"} <= set(raw):
        o, c, f = raw["open-inquiry"], raw["comparison"], raw["inquiry-framing"]
        common = lambda names: [n for n in names if not n.startswith("record_") or n == "record_artifact"]
        for lab, g in (("comparison", c), ("inquiry-framing", f)):
            t.eq("c1.differing.%s.common-tools" % lab, common(g["tool_names"]), common(o["tool_names"]))
            fam = "comparison" if lab == "comparison" else "inquiry-framing"
            t.eq("c1.differing.%s.recording-tools" % lab, [n for n in g["tool_names"] if n not in common(g["tool_names"])],
                 FAMILY_TOOLS[fam])
            t.eq("c1.differing.%s.orientation-shared" % lab, g["system_value"][0], o["system_value"][0])
            t.check("c1.differing.%s.instructions-differ" % lab, g["system_value"][1] != o["system_value"][1],
                    "instruction blocks equal")
    if "other-materials" in raw and "open-inquiry" in raw:
        t.eq("c1.invariance.system", raw["other-materials"]["system"], raw["open-inquiry"]["system"])
        t.eq("c1.invariance.tools", raw["other-materials"]["tools"], raw["open-inquiry"]["tools"])


@case("c1.outside-paths", ["C1", "C20"],
      "read, search and list refuse names outside the material without revealing anything",
      needs=("loopback",))
def c_outside_paths(t):
    """Names that leave the material (../, absolute host paths, archive names, near misses,
    directories) are each refused source_unknown by read and by search, with no host or archive
    path, reference, store or family name anywhere in any reply; a near miss names the closest
    real name as a hint. A constructed list cursor is refused handle_invalid. Differing: the
    real name reads. Invariance: a second audit in another location refuses the same relative
    names with the same reasons."""
    reasons = {}
    for label in ("a", "b"):
        sub = run_submission(t)
        names = ["../question.md", "materials/../question.md", "/etc/passwd", os.path.join(sub.folder, "question.md"),
                 os.path.join(sub.archive, "STORE.json"), "question.md", "materials", "materials/",
                 "materials/a.py/", "materials/./a.py", "materials//a.py", "materials/A.py",
                 "materials/notes", "materials/nonexistent.txt", "REFERENCE.json", "log/1.json", "STORE.json",
                 "~/.ssh/id_rsa", "file:///etc/passwd", "materials/a.py\\n"]

        def body(p, names=names):
            turn = yield p.calls_step(*[("read", {"source": n}) for n in names])
            got = {}
            for n, r in zip(names, turn.replies):
                got[n] = (r.outcome, r.reason)
                p.check("read-refused.%s" % n, r.outcome == "refused" and r.reason == "source_unknown",
                        {"name": n, "outcome": r.outcome, "reason": r.reason})
                p.eq("read-refused-effects.%s" % n, r.effects, {"raw_capture": "recorded"})
                if n == "materials/A.py":
                    p.check("near-miss-hint", mentions(r.env, "materials/a.py"), r.env)
            p.got = got
            turn = yield p.calls_step(*[("search", {"text": "def", "sources": [n]}) for n in names[:6]])
            for n, r in zip(names[:6], turn.replies):
                p.check("search-refused.%s" % n, r.outcome == "refused" and r.reason == "source_unknown",
                        {"name": n, "outcome": r.outcome, "reason": r.reason})
            turn = yield p.calls_step(("list", {"cursor": "ls.0.aaaaaa"}))
            p.eq("constructed-cursor", (turn.reply(0).outcome, turn.reply(0).reason), ("refused", "handle_invalid"))
            text, _ = yield from p.read_all("materials/a.py")
            p.eq("real-name-reads", text, material_bytes(sub, "a.py"))
            yield from finish_ordinary(p)
        p = proc(sub, body)
        fx = rs.provider(t, p, label="paths-" + label)
        rs.run(t, sub, fx, name="paths.%s.run" % label)
        rs.check_procedure(t, p, "paths.%s" % label, fx)
        rel = [n for n in names if not n.startswith("/")]
        reasons[label] = {n: v for n, v in (getattr(p, "got", {}) or {}).items() if n in rel}
    if len(reasons) == 2:
        t.eq("paths.invariance.reasons", reasons["b"], reasons["a"])


# ---------------------------------------------------------------------------
# C2 and C19: the question and material arrive unchanged; pages and search.
# ---------------------------------------------------------------------------

def c2_entries():
    return [F("crlf.txt", b"one\r\ntwo\r\nthree\r\n"), F("bom.txt", b"\xef\xbb\xbfBOM first\n"),
            F("multibyte.txt", "é 日本語 \U0001F600\nΩ≈\n".encode("utf-8")),
            F("blank.txt", b"   \n\n\t\n"), F("empty.txt", b""), F("only-newline.txt", b"\n"),
            F("long-line.txt", b"x" * 70000 + b"\n"), F("long-multibyte.txt", ("é" * 40000).encode("utf-8")),
            F("lf-window.txt", (b"y" * 999 + b"\n") * 70), F(".hidden/n.txt", b"hidden\n"),
            F("no-final-newline.txt", b"end without newline"), F("lone-cr.txt", b"a\rb\r")]


@case("c2.question-and-reads", ["C2", "C19", "C4"],
      "the question body and every material page reach the auditor byte for byte",
      needs=("loopback",),
      controls=[Control("read_live_source", [r"^auditor\.read\.", r"^c2\..*\.auditor-clean$"]),
                Control("normalize_read", [r"^auditor\.read\.", r"^c2\..*\.auditor-clean$"]),
                Control("paraphrase_question", [r"^auditor\.first-message\.", r"^c2\..*\.first-message$"])])
def c_c2(t):
    """The first message carries the question body exactly (CRLF, a page longer than one
    read, essential text last). The reacting auditor reads the question and every material
    page by page, checking each page's range against the 7.2 page rule, its bytes, cite and
    lines against the witness; blank and empty pages come in data.text, others in a second
    block. A material is rewritten in the folder after commission: reads still serve the
    capture. Differing: a question differing in one byte arrives differing in exactly that
    byte. Invariance: the same materials from another folder read identically."""
    firsts = {}
    for label, change in (("a", None), ("b", 7)):
        body = long_question().replace(b"\n", b"\r\n", 3)
        if change is not None:
            body = body[:change] + bytes([body[change] ^ 0x20]) + body[change + 1:]
        sub = run_submission(t, entries=c2_entries(), body=body)
        t.edit(mat(sub, "crlf.txt"), b"rewritten in the folder after commission\n")
        aud = auditor_for(t, sub, [], finish="ordinary", after_reminder="end")
        fx = rs.provider(t, aud, label="c2-" + label)
        rep = rs.run(t, sub, fx, name="c2.%s.run" % label)
        rs.check_run_reply(t, rep, sub, "c2.%s.run" % label, ending="ended_unsubmitted", run_number=1, fx=fx,
                           limits=rs.limits_of(sub))
        rs.check_auditor(t, aud, "c2.%s" % label)
        rs.check_fake(t, fx, "c2.%s" % label)
        if fx.exchanges:
            rs.check_first_message(t, fx.exchanges[0], sub.body, False, "c2.%s" % label)
            firsts[label] = (fx.exchanges[0].messages() or [None])[0]
        reads = [e for e in aud.events if e["event"] == "read complete"]
        t.eq("c2.%s.sources-read" % label, sorted(e["source"] for e in reads),
             sorted(["question"] + [sub.public(r) for r in sub.files]))
        rs.check_access_log(t, sub, aud, "c2.%s" % label)
    if len(firsts) == 2 and firsts["a"] is not None and firsts["b"] is not None:
        a, b = firsts["a"].raw, firsts["b"].raw
        diff = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
        t.check("c2.differing.one-byte", len(a) == len(b) and len(diff) == 1, {"positions": diff[:5]})


@case("c19.paging", ["C19", "C2", "C20"],
      "read pages never split a code point or drop bytes; search reports every literal hit with explicit completion",
      needs=("loopback",),
      controls=[Control("read_truncate_silently", [r"^c19\.read\."]),
                Control("search_omit_last_page", [r"^c19\.search\."])])
def c_paging(t):
    """A long line of three-byte characters pages at 65,534, not 65,536. A start inside a code
    point or past the end is range_invalid naming the nearest boundaries; a start at the end
    gives an empty complete page. Search for "aa" over a file of "aaa" lines reports both
    overlapping hits on each line, in position order, over pages of at most 128 hits with
    cursors, the last page complete; each hit's cite and line agree with the witness. The
    default scope is the question then every material in index order, and naming that scope
    explicitly gives the same hits (invariance); "aaa" gives one hit per line (differing).
    Absent text is reported absent only with complete: true. A 1,025-byte search is refused."""
    multi = b"zz" + ("€" * 30000).encode("utf-8")
    hits_file = b"aaa\n" * 200 + b"abc\n"
    entries = [F("multi.txt", multi), F("hits.txt", hits_file), F("few.txt", b"one aa here\n")]
    sub = run_submission(t, entries=entries, body=b"Where does aa appear?\n")
    srcs = sources_of(sub)

    def witness_hits(text, scope):
        out = []
        for s in scope:
            for o in aw.occurrences(srcs[s], text.encode("utf-8")):
                out.append({"source": s, "start": o, "end": o + len(text.encode("utf-8")),
                            "line": aw.line_of(srcs[s], o)})
        return out

    def core(hits):
        return [{k: h.get(k) for k in ("source", "start", "end", "line")} for h in hits or []]

    def body(p):
        text, pages = yield from p.read_all("materials/multi.txt")
        p.eq("read.multi.bytes", text, multi)
        p.eq("read.multi.ranges", [r.data.get("range") for r in pages], [list(x) for x in aw.read_pages(multi)])
        p.check("read.multi.next-calls", all(r.next_of("read") for r in pages[:-1]), [r.next for r in pages])
        turn = yield p.calls_step(("read", {"source": "materials/multi.txt", "start": 3}),
                                  ("read", {"source": "materials/multi.txt", "start": len(multi) + 1}),
                                  ("read", {"source": "materials/multi.txt", "start": len(multi)}))
        mid, past, at_end = turn.replies
        p.eq("range.mid-codepoint", (mid.outcome, mid.reason), ("refused", "range_invalid"))
        p.check("range.mid-codepoint.boundaries", has_int(mid.data, 2) and has_int(mid.data, 5), mid.env)
        p.eq("range.past-end", (past.outcome, past.reason), ("refused", "range_invalid"))
        p.eq("range.at-end", (at_end.outcome, at_end.data.get("range"), at_end.data.get("complete"),
                              at_end.data.get("lines"), at_end.data.get("cite"), at_end.data.get("text"), at_end.blocks),
             ("completed", [len(multi), len(multi)], True, None, None, "", 1))
        hits, spages = yield from p.search_all("aa", ["materials/hits.txt"])
        want = witness_hits("aa", ["materials/hits.txt"])
        p.eq("search.hits", core(hits), want)
        p.check("search.page-bound", all(len(find_hits(r.data)) <= 128 for r in spages), [len(find_hits(r.data)) for r in spages])
        p.eq("search.completion", [r.data.get("complete") for r in spages], [False] * (len(spages) - 1) + [True])
        p.check("search.cursors", all(r.next_of("search") and str(r.next_of("search")[0]["input"].get("cursor", "")).startswith("sc.")
                                      for r in spages[:-1]), [r.next for r in spages])
        p.check("search.cites", all(h.get("cite") == {"source": h.get("source"), "start": h.get("start"), "end": h.get("end")}
                                    for h in hits or []), (hits or [])[:3])
        # 7.2: "context is the hit's line, clipped to 240 bytes around the hit ..., with truncated
        # flags". The shape is not fixed: accept the clipped text directly or as an object's text,
        # and require truncation flags somewhere in the hit.
        def ctx_text(h):
            c = h.get("context")
            return c if isinstance(c, str) else (c.get("text") if isinstance(c, dict) else None)
        p.check("search.context", all(isinstance(ctx_text(h), str) and "aa" in ctx_text(h)
                                      and any("truncated" in k for v in (h, h.get("context")) if isinstance(v, dict)
                                              for k in v) for h in hits or []), (hits or [])[:2])
        dhits, dpages = yield from p.search_all("aa")
        scope = default_scope(sub)
        p.eq("search.default-scope-hits", core(dhits), witness_hits("aa", scope))
        p.check("search.scope-stated", any(v == scope for v in iter_values(dpages[0].data)) if dpages else False,
                dpages[0].data if dpages else None)
        ehits, _ = yield from p.search_all("aa", scope)
        p.eq("search.invariance.explicit-scope", core(ehits), core(dhits))
        thits, _ = yield from p.search_all("aaa", ["materials/hits.txt"])
        p.eq("search.differing.aaa", core(thits), witness_hits("aaa", ["materials/hits.txt"]))
        nhits, npages = yield from p.search_all("not present anywhere")
        p.check("search.absent", nhits == [] and npages and npages[-1].data.get("complete") is True,
                [r.data for r in npages])
        turn = yield p.calls_step(("search", {"text": "q" * 1025}), ("search", {"text": "q" * 1024}))
        p.eq("search.text-1025", turn.reply(0).outcome, "refused")
        p.eq("search.text-1024", turn.reply(1).outcome, "completed")
        yield from finish_ordinary(p)
    p = proc(sub, body)
    fx = rs.provider(t, p)
    rs.run(t, sub, fx, name="c19.run")
    rs.check_procedure(t, p, "c19", fx)
    rs.check_requests(t, fx, sub, "c19")


# ---------------------------------------------------------------------------
# C3: answers kept, sealed and attributed.
# ---------------------------------------------------------------------------

@case("c3.edits", ["C3", "C20", "C6"],
      "T5: stale targets never touch a newer version; equal adds stay distinct; a known invocation replays",
      needs=("loopback",),
      controls=[Control("merge_equal_adds", [r"^c3\.edits\.(equal-adds|selection|revision|entry-records)"]),
                Control("replay_reexecutes", [r"^c3\.edits\.replay"]),
                Control("stale_target_overwrites", [r"^c3\.edits\.stale"])])
def c_edits(t):
    """Two equal-byte adds give e1 and e2 (the second with label_duplicate). replace(e2.v1)
    gives e2.v2; a second replace and a delete of e2.v1 refuse stale_entry with the current
    handle and read/replace next calls, and e2.v2 still reads B. Deleting e1 reports the
    removal; repeating it reports already_removed and changes nothing. A tool_use ID repeated
    with identical raw input is a replay (same content, replay_of, no new entry); with other
    input invocation_id_reused; a fresh call with the same arguments is a new entry. The
    prepared selection equals the witness, at revision 6."""
    sub = run_submission(t)
    state = {}

    def body(p):
        turn = yield p.calls_step(("record_observation", {"text": "A", "label": "same"}),
                                  ("record_observation", {"text": "A", "label": "same"}))
        r1, r2 = turn.replies
        h1, h2 = r1.data.get("entry"), r2.data.get("entry")
        p.check("equal-adds-distinct", r1.outcome == r2.outcome == "completed" and h1 != h2
                and [r1.data.get("id"), r2.data.get("id")] == ["e1", "e2"], [r1.summary(), r2.summary()])
        p.check("equal-adds-label-duplicate", mentions(r2.data.get("notices"), "label_duplicate")
                and not mentions(r1.data.get("notices"), "label_duplicate"), [r1.data.get("notices"), r2.data.get("notices")])
        p.eq("equal-adds-revisions", [r1.data.get("revision"), r2.data.get("revision")], [1, 2])
        turn = yield p.calls_step(("replace", {"entry": h2, "text": "B", "citations": [], "label": "same"}))
        r = turn.reply(0)
        h2b = r.data.get("entry")
        p.check("replace", r.outcome == "completed" and isinstance(h2b, str) and h2b.startswith("e2.v2."), r.summary())
        turn = yield p.calls_step(("replace", {"entry": h2, "text": "STALE", "citations": [], "label": "same"}))
        r = turn.reply(0)
        p.eq("stale-replace-refused", (r.outcome, r.reason, r.effects.get("answer")), ("refused", "stale_entry", "unchanged"))
        p.eq("stale-replace-current", r.data.get("current"), h2b)
        targets = {n.get("tool"): (n.get("input") or {}) for n in r.next}
        p.check("stale-replace-next", targets.get("read", {}).get("source") == h2b
                and targets.get("replace", {}).get("entry") == h2b, r.next)
        turn = yield p.calls_step(("delete", {"entry": h2}))
        r = turn.reply(0)
        p.eq("stale-delete-refused", (r.outcome, r.reason, r.data.get("current")), ("refused", "stale_entry", h2b))
        text, _ = yield from p.read_all(h2b)
        p.eq("stale-kept-current", text, b"B")
        turn = yield p.calls_step(("delete", {"entry": h1}))
        r = turn.reply(0)
        p.eq("delete", (r.outcome, r.data.get("removed"), r.data.get("already_removed"), r.data.get("revision")),
             ("completed", {"id": "e1", "version": 1}, False, 4))
        turn = yield p.calls_step(("delete", {"entry": h1}))
        r = turn.reply(0)
        p.eq("delete-repeated", (r.outcome, r.data.get("removed"), r.data.get("already_removed"), r.data.get("revision"),
                                 r.effects.get("answer")), ("completed", {"id": "e1", "version": 1}, True, 4, "unchanged"))
        raw = b'{"text":"C","label":"replayed"}'
        turn = yield p.step([p.call("record_limit", raw_input=raw, tid="toolu_replay_1")])
        orig = turn.reply(0)
        p.check("replay-original", orig.outcome == "completed" and orig.data.get("id") == "e3", orig.summary())
        turn = yield p.step([p.call("record_limit", raw_input=raw, tid="toolu_replay_1")])
        again = turn.reply(0)
        p.eq("replay-same-result", (again.content_raw, again.is_error), (orig.content_raw, orig.is_error))
        turn = yield p.step([p.call("record_limit", raw_input=b'{"text":"D","label":"replayed"}', tid="toolu_replay_1")])
        r = turn.reply(0)
        p.eq("replay-different-input", (r.outcome, r.reason), ("refused", "invocation_id_reused"))
        turn = yield p.calls_step(("record_limit", {"text": "C", "label": "replayed"}))
        fresh = turn.reply(0)
        p.check("replay-fresh-call-is-new", fresh.outcome == "completed" and fresh.data.get("id") == "e4", fresh.summary())
        first, entries, _ = yield from p.wwaw_all()
        p.eq("replay-no-new-entry", [(e.get("id"), e.get("label")) for e in entries],
             [("e2", "same"), ("e3", "replayed"), ("e4", "replayed")])
        p.eq("revision", (first or {}).get("revision"), 6)
        turn = yield p.calls_step(("read", {"source": "question"}), ("read", {"source": "question"}))
        first2, _, _ = yield from p.wwaw_all()
        p.eq("reads-change-nothing", (first2 or {}).get("revision"), 6)
        turn = yield p.calls_step(("prepare", {}))
        ap = turn.reply(0).data.get("prepared")
        sel, _ = yield from p.read_all(ap + "/selection")
        state["selection"] = sel
        yield from finish_ordinary(p)
    p = proc(sub, body)
    fx = rs.provider(t, p)
    rep = rs.run(t, sub, fx, name="c3.edits.run")
    rs.check_run_reply(t, rep, sub, "c3.edits.run", ending="ended_unsubmitted", run_number=1, fx=fx,
                       limits=rs.limits_of(sub))
    rs.check_procedure(t, p, "c3.edits", fx)
    want = aw.answer_json(6, [aw.Entry("e2", 2, "record_observation", "same", b"B"),
                              aw.Entry("e3", 1, "record_limit", "replayed", b"C"),
                              aw.Entry("e4", 1, "record_limit", "replayed", b"C")])
    t.eq("c3.edits.selection", state.get("selection"), want)
    t.eq("c3.edits.entry-records", [b.get("action") for b in rs.entry_bodies(t, sub)],
         ["add", "add", "replace", "delete", "add", "add"])
    orig, again, other = (rs.result_for(sub, "toolu_replay_1", i) for i in (0, 1, 2))
    t.check("c3.edits.replay-of", orig and again and (again[3] or {}).get("replay_of") == orig[1]
            and (orig[3] or {}).get("replay_of") is None, [orig and orig[3], again and again[3]])
    t.check("c3.edits.replay-content", orig and again and (again[3] or {}).get("content") == (orig[3] or {}).get("content"),
            "replayed result content differs")
    t.eq("c3.edits.reused-recorded", (rs.result_envelope(other[3]) or {}).get("reason") if other else None,
         "invocation_id_reused")


@case("c3.interruptions", ["C3", "C13", "C16", "C6"],
      "kills while appending, before the seal link and after it: only complete records count",
      mode="test", needs=("loopback", "lock"),
      linux_reason="interruption is observed through the free OFD lock, a Linux-only expectation",
      controls=[Control("torn_as_entry", [r"^int\.torn\.status-entries$", r"^auditor\."])])
def c_interruptions(t):
    """stage.torn:entry=kill leaves a torn stage file and no entry: status (interrupted) counts
    no entry and reports the interrupted publication; run continues and the reacting auditor
    adds each goal once. log.publish:seal=kill dies before the seal: status shows no seal; run
    continues and the auditor seals. seal.after_link=kill dies after it: status shows the
    auditor seal undelivered, and run refuses authoring_ended (ended_by seal) with effects
    run ended, seal existing."""
    for label, fault in (("torn", "stage.torn:entry=kill"), ("pre-seal", "log.publish:seal=kill"),
                         ("post-seal", "seal.after_link=kill")):
        pre = "int." + label
        sub = run_submission(t)
        aud = auditor_for(t, sub, scenario_goals(sub))
        fx = rs.provider(t, aud, label=label)
        rs.run(t, sub, fx, name=pre + ".run-1", fault=fault, killed=True)
        st = t.status(sub, name=pre + ".status")
        hl = st.data.get("headline") or {}
        if label == "torn":
            t.eq(pre + ".no-entry-record", len(rs.entry_bodies(t, sub)), 0)
            t.eq(pre + ".condition", st.data.get("condition"), "interrupted")
            t.eq(pre + ".status-entries", (st.data.get("answer") or {}).get("entries"), 0)
            t.check(pre + ".interrupted-publication", mentions(st.data.get("diagnostics"), "stage"),
                    st.data.get("diagnostics"))
        elif label == "pre-seal":
            t.eq(pre + ".condition", st.data.get("condition"), "interrupted")
            t.eq(pre + ".no-seal", [st.data.get("seal"), hl.get("sealed")], [None, {"by": "none"}])
        else:
            t.eq(pre + ".condition", st.data.get("condition"), "sealed_undelivered")
            t.eq(pre + ".sealed-by", hl.get("sealed"), {"by": "auditor"})
            r2 = rs.run(t, sub, fx, name=pre + ".run-2", expect="refused", reason="authoring_ended")
            t.eq(pre + ".ended_by", r2.data.get("ended_by"), "seal")
            t.check(pre + ".record", isinstance(r2.data.get("record"), str) and r2.data["record"].startswith("log/"),
                    r2.data.get("record"))
            t.eq(pre + ".effects", {k: v for k, v in r2.effects.items() if k != "diagnostic"},
                 {"run": "ended", "answer": "unchanged", "seal": "existing", "delivery": "none"})
            t.eq(pre + ".no-request", len(fx.exchanges_of(pre + ".run-2")), 0)
            continue
        r2 = rs.run(t, sub, fx, name=pre + ".run-2")
        rs.check_run_reply(t, r2, sub, pre + ".run-2", ending="sealed", run_number=2, fx=fx, limits=rs.limits_of(sub),
                           seal_actor="auditor", delivery_outcome="verified")
        rs.check_auditor(t, aud, pre)
        rs.check_run_ended_usage(t, sub, fx, [pre + ".run-1", pre + ".run-2"], pre)


@case("c3.submit-races-close", ["C3", "C8", "C5"],
      "T6: submit racing close has exactly one winner, which names its actual actor",
      mode="test", needs=("loopback", "lock"),
      linux_reason="close waits on the OFD lock the run holds, a Linux-only expectation",
      controls=[Control("manager_seal_as_auditor", [r"^t6\.close-wins\.\d+\.seal-actor$"])])
def c_t6(t):
    """Close wins: the run pauses just before its seal link (log.publish:seal), close publishes
    close_requested, the run is released: the submit is refused authoring_ended with ended_by
    close, close_requested_at and no seal or sealer; the run ends stopped_by_close; close seals
    revision 1 as manager. Submit wins: the run pauses after its seal (seal.after_link), close
    is requested, the run is released: it delivers and ends sealed; the only seal is the
    auditor's. Each order twice."""
    for order, point in (("close-wins", "log.publish:seal"), ("submit-wins", "seal.after_link")):
        for i in (1, 2):
            pre = "t6.%s.%d" % (order, i)
            sub = run_submission(t)

            def body(p):
                turn = yield p.calls_step(("record_observation", {"text": "Recorded before the race.", "label": "race"}))
                p.eq("recorded", turn.reply(0).outcome, "completed")
                yield from prepare_and_submit(p)
            p = proc(sub, body)
            fx = rs.provider(t, p, label="%s-%d" % (order, i))
            h = rs.start_run(t, sub, fx, name=pre + ".run", fault=point + "=pause")
            stem = t.wait_paused(point.split(":")[0], h)
            cl = t.start(["close", sub.ref], name=pre + ".close", timeout=120)
            t.check(pre + ".close-requested", rs.wait_for(lambda: "close_requested" in t.log_kinds(sub), 15),
                    t.log_kinds(sub))
            t.release(stem)
            rr = rs.finish_run(t, h)
            t.finish(cl, expect="completed")
            rs.check_procedure(t, p, pre, fx)
            seals = [b for b in t.log_bodies(sub, "seal") if isinstance(b, dict)]
            st = t.status(sub, name=pre + ".status")
            if order == "close-wins":
                t.eq(pre + ".run-ending", rr.data.get("ending"), "stopped_by_close")
                tid = last_call(p, "submit")
                res = rs.result_for(sub, tid)
                env = rs.result_envelope(res[3]) if res else None
                d = (env or {}).get("data") or {}
                t.eq(pre + ".submit-refused", ((env or {}).get("outcome"), (env or {}).get("reason")),
                     ("refused", "authoring_ended"))
                t.check(pre + ".submit-data", d.get("ended_by") == "close" and isinstance(d.get("close_requested_at"), str)
                        and AT_RE.match(d["close_requested_at"]) and d.get("seal") is None and d.get("sealer") is None, d)
                t.eq(pre + ".seal-actor", [b.get("actor") for b in seals], ["manager"])
                t.eq(pre + ".seal-revision", [b.get("revision") for b in seals], [1])
                t.eq(pre + ".status-actor", (st.data.get("seal") or {}).get("actor"), "manager")
            else:
                t.eq(pre + ".run-ending", rr.data.get("ending"), "sealed")
                t.eq(pre + ".seal-actor", [b.get("actor") for b in seals], ["auditor"])
                t.eq(pre + ".status-actor", (st.data.get("seal") or {}).get("actor"), "auditor")


@case("c3.limits", ["C3", "C20"], "256 entries and 4 MiB inputs: the limits refuse, and edits at the limits still work",
      heavy=True, needs=("loopback",))
def c_limits(t):
    """256 entries are recorded (four responses of 64 calls); the 257th refuses entry_limit
    with the answer unchanged. At the limit a replace and a delete still work, then one add
    fits and the next refuses. A record call whose input is 4 MiB + 1 byte refuses
    input_too_large; one of exactly 4 MiB is recorded."""
    sub = run_submission(t)

    def body(p):
        for batch in range(4):
            turn = yield p.calls_step(*[("record_observation", {"text": "n%d" % (batch * 64 + i)}) for i in range(64)])
            p.check("fill-%d" % batch, all(r.outcome == "completed" for r in turn.replies),
                    [r.reason for r in turn.replies if r.outcome != "completed"][:3])
        turn = yield p.calls_step(("record_observation", {"text": "one too many"}))
        r = turn.reply(0)
        p.eq("entry-limit", (r.outcome, r.reason, r.effects.get("answer")), ("refused", "entry_limit", "unchanged"))
        first, entries, _ = yield from p.wwaw_all()
        p.eq("at-limit", len(entries), 256)
        h1, h2, h3 = (entries[i].get("entry") for i in range(3)) if len(entries) >= 3 else (None, None, None)
        turn = yield p.calls_step(("replace", {"entry": h1, "text": "replaced at the limit", "citations": [], "label": ""}),
                                  ("delete", {"entry": h2}))
        p.eq("edits-at-limit", [r.outcome for r in turn.replies], ["completed", "completed"])
        turn = yield p.calls_step(("record_observation", {"text": "fits again"}),
                                  ("record_observation", {"text": "over again"}))
        p.eq("refill", [(r.outcome, r.reason) for r in turn.replies], [("completed", None), ("refused", "entry_limit")])
        turn = yield p.calls_step(("delete", {"entry": h3}))
        n = 4 * 1024 * 1024 - len(b'{"text":""}')
        turn = yield p.step([p.call("record_observation", raw_input=b'{"text":"' + b"x" * (n + 1) + b'"}')])
        p.eq("input-over-4mib", (turn.reply(0).outcome, turn.reply(0).reason), ("refused", "input_too_large"))
        turn = yield p.step([p.call("record_observation", raw_input=b'{"text":"' + b"x" * n + b'"}')])
        p.eq("input-4mib", turn.reply(0).outcome, "completed")
        yield from finish_ordinary(p)
    p = proc(sub, body)
    fx = rs.provider(t, p)
    rs.run(t, sub, fx, name="limits.run", timeout=1800)
    rs.check_procedure(t, p, "limits", fx)


# ---------------------------------------------------------------------------
# C4: re-entry restores recorded work and access.
# ---------------------------------------------------------------------------

@case("c4.reentry", ["C4", "C13", "C20", "C14"],
      "re-entry pages every entry, refuses a stale page, keeps refusals and gaps, and counts allowances across runs",
      needs=("loopback",),
      controls=[Control("reentry_omit_entry", [r"^c4\.(pages|continuation)\.entries$", r"^auditor\."]),
                Control("reentry_truncate_page", [r"^c4\.(pages|continuation)\.(entries|shape)$"]),
                Control("reentry_omit_last_page", [r"^c4\.(pages|continuation)\.(entries|shape)$"]),
                Control("reentry_mix_revisions", [r"^c4\.stale-view$"]),
                Control("reentry_placement_allowances", [r"^c4\.continuation\.allowances$",
                                                         r"^auditor\.reentry\.allowances$"])])
def c_reentry(t):
    """Seventy entries come back over two re-entry pages (64 then 6, later pages holding only
    entries and page), ids and handles in order. A page cursor taken before an edit is refused
    stale_view with a call to start again. A refused citation is listed in latest_refusals with
    its operation and revision. The first run ends on an unavailable provider; a result record
    is then damaged. In the continuation, re-entry reports run 2, all 71 entries, the damaged
    record as a gap (recorded data it could not read, distinct from lost context) and the
    allowances of both runs. Invariance: the reacting auditor seals the same answer.json bytes
    with and without a compaction, including an entry longer than one read page."""
    sub = run_submission(t, body=b"Short question for re-entry pages.\n")
    box = {}

    def body(p):
        for half in range(2):
            turn = yield p.calls_step(*[("record_observation", {"text": "entry %02d" % (half * 35 + i),
                                                                "label": "g%02d" % (half * 35 + i)}) for i in range(35)])
            p.check("recorded-%d" % half, all(r.outcome == "completed" for r in turn.replies),
                    [r.reason for r in turn.replies if r.outcome != "completed"][:3])
        first, entries, pages = yield from p.wwaw_all()
        p.eq("pages.entries", [(e.get("id"), e.get("label")) for e in entries],
             [("e%d" % (i + 1), "g%02d" % i) for i in range(70)])
        p.eq("pages.shape", [[(r.data.get("page") or {}).get(k) for k in ("returned", "total", "complete", "bound_revision")]
                             for r in pages], [[64, 70, False, 70], [6, 70, True, 70]])
        p.check("pages.handles", all(isinstance(e.get("entry"), str) and e["entry"].startswith("%s.v1." % e.get("id"))
                                     for e in entries), entries[:2])
        p.eq("pages.later-page-keys", sorted(pages[1].data) if len(pages) > 1 else None, ["entries", "page"])
        turn = yield p.calls_step(("what_am_i_working_with", {}))
        nxt = turn.reply(0).next_of("what_am_i_working_with")
        cursor = nxt[0].get("input") if nxt else {"page": "pg.0.aaaaaa"}
        turn = yield p.calls_step(("record_observation", {"text": "intervening edit", "label": "g70"}))
        turn = yield p.calls_step(("what_am_i_working_with", cursor))
        r = turn.reply(0)
        p.eq("stale-view", (r.outcome, r.reason), ("refused", "stale_view"))
        p.check("stale-view.next", any(n.get("tool") == "what_am_i_working_with" and not (n.get("input") or {}).get("page")
                                       for n in r.next), r.next)
        turn = yield p.calls_step(("record_observation", {"text": "bad", "citations": [{"source": "question",
                                                                                      "quote": "not in the question"}]}))
        refusal = turn.reply(0)
        p.eq("refusal", (refusal.outcome, refusal.reason), ("refused", "quote_not_found"))
        turn = yield fp.HttpError(529, retry_after="0")
        p.check("continuation.new-conversation", turn.new_conversation, "no new conversation")
        p.eq("continuation.first-message", turn.first_message.raw if turn.first_message else None,
             first_message_bytes(sub.body, True))
        first, entries, pages = yield from p.wwaw_all()
        f = first or {}
        p.eq("continuation.entries", len(entries), 71)
        p.eq("continuation.run", f.get("run"), {"number": 2, "continuing": True})
        fx = box["fx"]
        p.eq("continuation.allowances", f.get("allowances"),
             fp.allowances(fx.totals(upto=pages[0].ex.n - 1), rs.limits_of(sub)))
        p.check("continuation.gaps", any(isinstance(g, dict) and g.get("run") == 1 and g.get("call") == 1
                                         for g in f.get("gaps") or []), f.get("gaps"))
        lr = [x for x in f.get("latest_refusals") or [] if isinstance(x, dict) and x.get("tool") == "record_observation"]
        p.eq("continuation.latest-refusal", lr[:1], [{"run": 1, "tool_use_id": refusal.tid, "tool": "record_observation",
                                                      "outcome": "refused", "reason": "quote_not_found", "revision": 71}])
        yield from finish_ordinary(p)
    p = proc(sub, body)
    fx = rs.provider(t, p)
    box["fx"] = fx
    r1 = rs.run(t, sub, fx, name="c4.run-1")
    rs.check_run_reply(t, r1, sub, "c4.run-1", ending="interrupted", cause="provider_unavailable", run_number=1, fx=fx,
                       limits=rs.limits_of(sub))
    res1 = os.path.join(sub.audit_dir, "runs", "1", "result-1.json")
    if t.check("c4.result-record-present", os.path.isfile(res1), res1):
        t.flip_bit(res1, 0)
    r2 = rs.run(t, sub, fx, name="c4.run-2")
    rs.check_run_reply(t, r2, sub, "c4.run-2", ending="ended_unsubmitted", run_number=2, fx=fx, limits=rs.limits_of(sub))
    rs.check_procedure(t, p, "c4", fx)
    answers = {}
    for label, compact_after in (("compacted", (3,)), ("uncompacted", ())):
        s2 = run_submission(t)
        goals = scenario_goals(s2) + [Goal("long entry", "".join("long line %05d of the long entry.\n" % i
                                                                 for i in range(2500)))]
        aud = auditor_for(t, s2, goals, compact_after=compact_after, calls_per_turn=2)
        fx2 = rs.provider(t, aud, label=label)
        rep = rs.run(t, s2, fx2, name="c4.%s.run" % label)
        rs.check_run_reply(t, rep, s2, "c4.%s.run" % label, ending="sealed", run_number=1, fx=fx2,
                           limits=rs.limits_of(s2), seal_actor="auditor", delivery_outcome="verified")
        rs.check_auditor(t, aud, "c4.%s" % label)
        answers[label] = answer_of(t, rep, "c4.%s" % label)
    t.check("c4.invariance.same-answer", answers.get("compacted") is not None
            and answers.get("compacted") == answers.get("uncompacted"), "answer.json differs with compaction")


# ---------------------------------------------------------------------------
# C6: the record is honest.
# ---------------------------------------------------------------------------

@case("c6.records", ["C6", "C14", "C18"],
      "the access log equals the auditor's calls, refused and replayed ones included; payloads are never removed",
      needs=("loopback",),
      controls=[Control("rewrite_record_in_place", [r"^inventory\.", r"^log\.", r"^c6\."]),
                Control("remove_superseded_payload", [r"^inventory\.", r"^c6\.payload"]),
                Control("skip_search_capture", [r"^c6\.(access-log|search-captured)"])])
def c_records(t):
    """list, read, search, a refused read and a replay of the search are each in the access log
    in order, with their exact input bytes and the outcome of their result records. A replace
    keeps the superseded payload file: both versions' payload files hold their bytes. Every run
    record decodes strictly; run_ended usage equals the fake's charges; archives only grow."""
    sub = run_submission(t)
    raw_search = b'{"text":"deliver","sources":["materials/a.py"]}'

    def body(p):
        yield p.calls_step(("list", {}))
        yield p.calls_step(("read", {"source": "question"}))
        yield p.step([p.call("search", raw_input=raw_search, tid="toolu_search_1")])
        turn = yield p.calls_step(("read", {"source": "materials/nope.txt"}))
        p.eq("refused-read", turn.reply(0).reason, "source_unknown")
        yield p.step([p.call("search", raw_input=raw_search, tid="toolu_search_1")])
        turn = yield p.calls_step(("record_observation", {"text": "v1", "label": "x"}))
        h = turn.reply(0).data.get("entry")
        turn = yield p.calls_step(("replace", {"entry": h, "text": "v2", "citations": [], "label": "x"}))
        p.eq("replaced", turn.reply(0).outcome, "completed")
        yield from finish_ordinary(p)
    p = proc(sub, body)
    fx = rs.provider(t, p)
    rep = rs.run(t, sub, fx, name="c6.run")
    rs.check_procedure(t, p, "c6", fx)
    log = [(x["tool"], x["input"], x["outcome"]) for x in rs.access_log(sub)]
    t.eq("c6.access-log", log, [("list", b"{}", "completed"), ("read", b'{"source":"question"}', "completed"),
                                ("search", raw_search, "completed"),
                                ("read", b'{"source":"materials/nope.txt"}', "refused"),
                                ("search", raw_search, "completed")])
    t.check("c6.search-captured", rs.result_for(sub, "toolu_search_1", 0) is not None, "no capture of the search")
    for b in rs.entry_bodies(t, sub):
        pl = b.get("payload") or {}
        path = os.path.join(sub.audit_dir, pl.get("file", "missing"))
        data = read_bytes(path) if os.path.isfile(path) else None
        t.check("c6.payload-kept.%s" % pl.get("file"), data is not None and sha256_hex(data) == pl.get("sha256")
                and len(data) == pl.get("size"), {"payload": pl, "present": data is not None})
    t.eq("c6.payload-files", sorted(os.listdir(os.path.join(sub.audit_dir, "payload")))
         if os.path.isdir(os.path.join(sub.audit_dir, "payload")) else None, ["e1.v1.bin", "e1.v2.bin"])
    rs.check_run_records(t, sub, "c6")
    rs.check_run_ended_usage(t, sub, fx, ["c6.run"], "c6")


# ---------------------------------------------------------------------------
# C7: question families, permitted answers, citation controls and prompts.
# ---------------------------------------------------------------------------

def find_cites(data):
    for v in iter_values(data):
        if isinstance(v, list) and v and all(isinstance(x, dict) and {"source", "start", "end"} <= set(x) for x in v):
            return v
    return []


@case("c7.families", ["C7", "C5", "C14", "C1"],
      "each family's sections and notices; open inquiry and inability are ordinary routes; citation controls",
      needs=("loopback",),
      controls=[Control("framing_task_elsewhere", [r"^c7\..*\.system-bytes$"]),
                Control("grade_support", [r"^c7\.cite\.recorded"]),
                Control("block_incomplete", [r"^c7\..*\.prepare-"])])
def c_families(t):
    """For each family: prepare with no entries gives the single answer_empty notice, an empty
    selection and "No answer entries recorded."; after an account stating that the question
    cannot be answered as asked, prepare lists one section_unfilled per other expected section
    in tools order, and submit seals without acknowledgment. Comparison counts an observation
    without treating it as a comparison. Open inquiry exercises citations: a range, a quote, a
    range with its quote and an irrelevant but valid citation are recorded with Stewart's
    additions only; a changed range, a missing quote and an ambiguous quote refuse without an
    entry (the ambiguous one listing each occurrence as a ready citation); prose resembling a
    citation is not scraped. T12: an empty answer seals and renders as
    "No answer entries recorded.". Each family's requests carry its own instructions."""
    for family in ("open-inquiry", "inquiry-framing", "comparison"):
        pre = "c7." + family
        sub = run_submission(t, family=family)
        tools = FAMILY_TOOLS[family] + ["record_artifact"]
        expected = [x for x in FAMILY_TOOLS[family] if not (family == "comparison" and x == "record_observation")]

        def body(p, sub=sub, family=family, tools=tools, expected=expected):
            turn = yield p.calls_step(("prepare", {}))
            r = turn.reply(0)
            p.eq("prepare-empty", ([n.get("reason") for n in r.data.get("notices") or []], r.data.get("counts"),
                                   r.data.get("entry_count")), (["answer_empty"], {k: 0 for k in tools}, 0))
            ap = r.data.get("prepared")
            md, _ = yield from p.read_all(ap + "/rendering")
            js, _ = yield from p.read_all(ap + "/selection")
            p.eq("empty-views", (md, js), (aw.EMPTY_RENDERING, aw.answer_json(0, [])))
            turn = yield p.calls_step(("record_account", {"text": "I cannot answer this as asked: the materials do "
                                                                  "not show what happens across a restart."}))
            p.eq("inability-recorded", turn.reply(0).outcome, "completed")
            if family == "comparison":
                turn = yield p.calls_step(("record_observation", {"text": "Only one alternative is described."}))
            if family == "inquiry-framing":
                turn = yield p.calls_step(("record_working_question", {"text": "The question is precise; it is my working question."}))
            turn = yield p.calls_step(("prepare", {}))
            r = turn.reply(0)
            counts = {k: 0 for k in tools}
            counts["record_account"] = 1
            if family == "comparison":
                counts["record_observation"] = 1
            if family == "inquiry-framing":
                counts["record_working_question"] = 1
            p.eq("prepare-partial.counts", r.data.get("counts"), counts)
            p.eq("prepare-partial.notices", [(n.get("reason"), n.get("tool")) for n in r.data.get("notices") or []],
                 [("section_unfilled", x) for x in expected if counts[x] == 0])
            p.check("prepare-partial.no-sealer", "sealer" not in json.dumps(r.data), r.data)
            if family == "open-inquiry":
                yield from citation_controls(p, sub)
            yield from prepare_and_submit(p)
        p = proc(sub, body)
        fx = rs.provider(t, p, label=family)
        rep = rs.run(t, sub, fx, name=pre + ".run")
        rs.check_run_reply(t, rep, sub, pre + ".run", ending="sealed", run_number=1, fx=fx, limits=rs.limits_of(sub),
                           seal_actor="auditor", delivery_outcome="verified")
        rs.check_procedure(t, p, pre if family != "open-inquiry" else "c7.cite", fx)
        rs.check_requests(t, fx, sub, pre)
    sub = run_submission(t)

    def empty(p):
        yield from prepare_and_submit(p)
    p = proc(sub, empty)
    fx = rs.provider(t, p, label="empty")
    rep = rs.run(t, sub, fx, name="c7.t12.run")
    rs.check_run_reply(t, rep, sub, "c7.t12.run", ending="sealed", run_number=1, fx=fx, limits=rs.limits_of(sub),
                       seal_actor="auditor", delivery_outcome="verified")
    rs.check_procedure(t, p, "c7.t12", fx)
    loc = rs.package_of(rep)
    t.eq("c7.t12.rendering", rs.read_package_member(loc, "answer.md") if loc else None, aw.EMPTY_RENDERING)
    t.eq("c7.t12.answer", rs.read_package_member(loc, "answer.json") if loc else None, aw.answer_json(0, []))


def citation_controls(p, sub):
    a = material_bytes(sub, "a.py")
    srcs = sources_of(sub)
    _, pages = yield from p.read_all("materials/a.py")
    page_cite = pages[0].data.get("cite") if pages else None
    s = a.find(b"deliver(r)")
    cites = [
        ("range", [{"source": "materials/a.py", "start": s, "end": s + 10}], None),
        ("quote", [{"source": "materials/a.py", "quote": "mark_sent(r)"}], None),
        ("range-and-quote", [{"source": "materials/a.py", "start": s, "end": s + 10, "quote": "deliver(r)"}], None),
        ("changed-range", [{"source": "materials/a.py", "start": s, "end": s + 11, "quote": "deliver(r)"}], "citation_invalid"),
        ("missing-quote", [{"source": "materials/a.py", "quote": "not there"}], "quote_not_found"),
        ("ambiguous-quote", [{"source": "materials/a.py", "quote": "(r)"}], "quote_ambiguous"),
        ("irrelevant", [{"source": "materials/notes/R1.txt", "quote": "R1."}], None),
        ("prose", [], None),
        ("read-cite", [page_cite], None),
    ]
    texts = {"prose": "See materials/a.py lines 1–2 [0, 13) \"def send(r):\" for the start."}
    turn = yield p.calls_step(*[("record_observation", {"text": texts.get(lab, "Citation case %s." % lab), "citations": c})
                                for lab, c, _ in cites])
    revisions = []
    for (lab, c, reason), r in zip(cites, turn.replies):
        if reason is None:
            want = [aw.record_citation(x, srcs) for x in c]
            p.eq("recorded.%s" % lab, (r.outcome, r.data.get("citations")), ("completed", want))
            revisions.append(r.data.get("revision"))
        else:
            p.eq("refused.%s" % lab, (r.outcome, r.reason, r.effects.get("answer")), ("refused", reason, "unchanged"))
            if lab == "ambiguous-quote":
                occ = aw.occurrences(a, b"(r)")
                p.eq("refused.ambiguous.occurrences", [(x.get("source"), x.get("start"), x.get("end"))
                                                       for x in find_cites(r.data)],
                     [("materials/a.py", o, o + 3) for o in occ[:8]])
    p.check("refusals-create-no-entry", revisions and revisions == list(range(revisions[0], revisions[0] + len(revisions))),
            revisions)


@case("c7.prompts", ["C7", "C13", "C6"],
      "the reminder and the near-limit notice are sent once per audit; limits stop the run without a seal",
      needs=("loopback",),
      controls=[Control("reset_notice_allowance", [r"^c7\.prompts\.reminder-once$", r"^c7\.prompts\.notices$"])])
def c_prompts(t):
    """An ordinary stop receives the exact reminder; the run is then interrupted by an
    unavailable provider and continued; a stop in the continuation ends the run without a second
    reminder (one reminder per audit, its notice sent). With a 10,000-token output limit and
    1,200 output tokens per response, each request's max_tokens is the lesser of 16,000 and the
    remaining output; the near-limit notice (exact text and remaining amounts) rides on the
    request after the attempt that crossed 20%; the run ends limit_reached after executing the
    last response's call, with no reminder and no seal, and run then refuses authoring_ended
    (limit)."""
    sub = run_submission(t)

    def body(p):
        turn = yield p.end("Stopping without submitting.")
        p.eq("reminder.text", turn.texts, [REMINDER])
        turn = yield fp.HttpError(529, retry_after="0")
        p.check("continued", turn.new_conversation, "no continuation")
        while True:
            turn = yield p.end("Stopping again.")
    p = proc(sub, body)
    fx = rs.provider(t, p, label="reminder")
    r1 = rs.run(t, sub, fx, name="c7.prompts.run-1")
    rs.check_run_reply(t, r1, sub, "c7.prompts.run-1", ending="interrupted", cause="provider_unavailable", run_number=1,
                       fx=fx, limits=rs.limits_of(sub))
    r2 = rs.run(t, sub, fx, name="c7.prompts.run-2")
    rs.check_run_reply(t, r2, sub, "c7.prompts.run-2", ending="ended_unsubmitted", run_number=2, fx=fx,
                       limits=rs.limits_of(sub))
    rs.check_procedure(t, p, "c7.prompts", fx)
    t.eq("c7.prompts.reminder-once", p.texts.count(REMINDER), 1)
    notices = [b for b in t.log_bodies(sub, "notice") if isinstance(b, dict)]
    t.eq("c7.prompts.notices", [(b.get("type"), b.get("run"), b.get("text")) for b in notices], [("reminder", 1, REMINDER)])
    ended = t.log_bodies(sub, "run_ended")
    t.eq("c7.prompts.run-1.notices", [(n.get("type"), n.get("sent")) for n in (ended[0] or {}).get("notices") or []]
         if ended else None, [("reminder", "sent")])
    t.eq("c7.prompts.run-2.reply-notices", r2.data.get("notices"), [])
    sub2 = run_submission(t, q={"output_tokens": "10000"})

    def limited(p):
        p.usage = lambda: fp.Usage(1000, 1200)
        while True:
            yield p.calls_step(("list", {}))
    p2 = proc(sub2, limited)
    fx2 = rs.provider(t, p2, label="limits")
    rep = rs.run(t, sub2, fx2, name="c7.limits.run")
    rs.check_run_reply(t, rep, sub2, "c7.limits.run", ending="limit_reached", run_number=1, fx=fx2,
                       limits=rs.limits_of(sub2))
    rs.check_procedure(t, p2, "c7.limits", fx2)
    t.eq("c7.limits.requests", len(fx2.exchanges), 8)
    t.eq("c7.limits.max-tokens", [e.max_tokens() for e in fx2.exchanges],
         [min(MAX_TOKENS_PER_REQUEST, 10000 - 1200 * k) for k in range(len(fx2.exchanges))])
    want = NEAR_LIMIT.format(turns=200 - 7, input_tokens=20000000 - 7000, output_tokens=10000 - 7 * 1200)
    t.eq("c7.limits.near-limit-text", p2.texts, [want])
    last = fx2.exchanges[-1].messages() if fx2.exchanges else None
    t.check("c7.limits.notice-on-request-8", last is not None and want.encode("utf-8") in last[-1].raw, "notice not on the last request")
    t.eq("c7.limits.reply-notices", rep.data.get("notices"), [{"type": "near_limit", "sent": "sent"}])
    calls = rs.calls_and_results(sub2)
    t.check("c7.limits.last-call-executed", len(calls) == 8 and all(c[3] is not None for c in calls), len(calls))
    t.eq("c7.limits.no-seal", t.log_bodies(sub2, "seal"), [])
    r3 = rs.run(t, sub2, fx2, name="c7.limits.again", expect="refused", reason="authoring_ended")
    t.eq("c7.limits.ended_by", r3.data.get("ended_by"), "limit")


# ---------------------------------------------------------------------------
# C9: protocol calls answer quickly, and every reply says what it did.
# ---------------------------------------------------------------------------

@case("c9.protocol-timing", ["C9", "C20"],
      "each protocol call is answered within tens of milliseconds; every reply carries its envelope",
      needs=("loopback",),
      controls=[Control("slow_list", [r"^c9\.list-relative$"]),
                Control("omit_effects_on_refusal", [r"^c9\.reply\.envelope\."])])
def c_protocol_timing(t):
    """One call per response: list, read, search of one material, what_am_i_working_with, a
    record, prepare, a refused read and list again. The fake measures each call's interval
    (C9's gate applies on the native architecture); list may not stand out from the median of
    the others by 250 ms (a relative check that also holds under emulation). Every reply, the
    refusal included, passes the envelope rules."""
    sub = run_submission(t, body=b"Is deliver called before mark_sent?\n")

    def body(p):
        for spec in (("list", {}), ("read", {"source": "question"}), ("read", {"source": "materials/a.py"}),
                     ("search", {"text": "deliver", "sources": ["materials/a.py"]}), ("what_am_i_working_with", {}),
                     ("record_observation", {"text": "deliver precedes mark_sent."}), ("prepare", {}),
                     ("read", {"source": "materials/nope.txt"}), ("list", {}), ("list", {})):
            yield p.calls_step(spec)
        yield from finish_ordinary(p)
    p = proc(sub, body)
    fx = rs.provider(t, p)
    rs.run(t, sub, fx, name="c9.run")
    rs.check_procedure(t, p, "c9", fx)
    samples = [x for x in t.protocol_timings if x["run"] == "c9.run"]
    lists = [x["ms"] for x in samples if x["tool"] == "list"]
    others = sorted(x["ms"] for x in samples if x["tool"] != "list")
    if t.check("c9.samples", len(lists) >= 2 and len(others) >= 5, samples):
        med = others[len(others) // 2]
        t.check("c9.list-relative", max(lists) - med < 250.0, {"list_ms": lists, "median_other_ms": med})


# ---------------------------------------------------------------------------
# C12: run refusals and the run as a handoff.
# ---------------------------------------------------------------------------

def ordinary_body(p):
    yield from finish_ordinary(p)


@case("c12.run-refusals", ["C12", "C16", "C20"],
      "run refuses an ended, limited, sealed, closed or held audit with a sign; commission needs no key or network",
      needs=("loopback",),
      controls=[Control("relative_run_line", [r"^c12\.refusals\.(run-line|commission\.data\.run_line)"]),
                Control("commission_over_network", [r"^c12\.refusals\.commission"])])
def c_run_refusals(t):
    """Commission succeeds without ANTHROPIC_API_KEY while STEWART_PROVIDER_URL points at the
    fake, which sees no connection; its run line names the absolute writer. After an ordinary
    ending, a limit stop and a seal, run refuses authoring_ended with ended_by ordinary_ending,
    limit or seal and the record that ended authoring, effects stating the recorded facts and
    next calls close and status. On a closed reference it refuses reference_closed. While
    another run holds the lock (test build on Linux) it refuses run_held naming the holder's
    observations. Invariance: the same audit run from another directory and HOME differs only
    in run_started observations, which name a process and user ID, never a person."""
    watch = rs.provider(t, fp.Script([]), label="commission-watch")
    sub = t.submission(scenario_entries(), body=b"Is the reminder sent twice?\n", dest_watch="additions")
    t.new_ref(sub)
    t.prepare(sub)
    rep = t.commission(sub, sub.handles[-1], name="c12.refusals.commission",
                       env={"STEWART_PROVIDER_URL": watch.url, "ANTHROPIC_API_KEY": None})
    t.check("c12.refusals.commission-offline", rep.outcome == "completed" and not watch.exchanges
            and not watch.provider.events, {"outcome": rep.outcome, "exchanges": len(watch.exchanges)})
    t.eq("c12.refusals.run-line", rep.data.get("run_line"), [sub.writer, "run", sub.ref])
    replies = {}
    for label, subx, cwd, home in (("a", sub, t.fresh_dir("cwd a"), t.fresh_dir("home a")),
                                   ("a2", run_submission(t, body=b"Is the reminder sent twice?\n"),
                                    t.fresh_dir("cwd a2"), t.fresh_dir("home a2"))):
        pre = "c12.refusals.%s" % label
        p = proc(subx, ordinary_body)
        fx = rs.provider(t, p, label="ordinary-" + label)
        r = rs.run(t, subx, fx, name=pre + ".run", env={"HOME": home}, cwd=cwd)
        replies[label] = r
        rs.check_run_reply(t, r, subx, pre + ".run", ending="ended_unsubmitted", run_number=1, fx=fx,
                           limits=rs.limits_of(subx))
        started = t.log_bodies(subx, "run_started")
        obs = (started[0] or {}).get("observations") if started else None
        t.check(pre + ".observations", isinstance(obs, dict) and list(obs) == ["pid", "start_ticks", "uid", "host", "boot_id"]
                and isinstance(obs.get("pid"), int) and obs.get("uid") == os.getuid(), obs)
        r2 = rs.run(t, subx, fx, name=pre + ".again", expect="refused", reason="authoring_ended")
        kinds = t.log_kinds(subx)
        t.eq(pre + ".ended_by", (r2.data.get("ended_by"), r2.data.get("record")),
             ("ordinary_ending", "log/%d.json" % (kinds.index("run_ended") + 1) if "run_ended" in kinds else None))
        t.eq(pre + ".effects", {k: v for k, v in r2.effects.items() if k != "diagnostic"},
             {"run": "ended", "answer": "unchanged", "seal": "none", "delivery": "none"})
        t.eq(pre + ".next", sorted({a[1] for a in r2.next_argvs()}), ["close", "status"])
    if len(replies) == 2:
        pick = lambda r: (r.data.get("ending"), r.data.get("usage"), r.data.get("notices"))
        t.eq("c12.refusals.invariance", pick(replies["a2"]), pick(replies["a"]))
    sub_b = run_submission(t, q={"turns": "1"})

    def one_call(p):
        while True:
            yield p.calls_step(("list", {}))
    pb = proc(sub_b, one_call)
    fxb = rs.provider(t, pb, label="limit")
    r = rs.run(t, sub_b, fxb, name="c12.refusals.b.run")
    rs.check_run_reply(t, r, sub_b, "c12.refusals.b.run", ending="limit_reached", run_number=1, fx=fxb,
                       limits=rs.limits_of(sub_b))
    r2 = rs.run(t, sub_b, fxb, name="c12.refusals.b.again", expect="refused", reason="authoring_ended")
    t.eq("c12.refusals.b.ended_by", r2.data.get("ended_by"), "limit")
    sub_c = run_submission(t)

    def seal_body(p):
        yield from prepare_and_submit(p)
    pc = proc(sub_c, seal_body)
    fxc = rs.provider(t, pc, label="seal")
    rs.run(t, sub_c, fxc, name="c12.refusals.c.run")
    r2 = rs.run(t, sub_c, fxc, name="c12.refusals.c.again", expect="refused", reason="authoring_ended")
    t.eq("c12.refusals.c.ended_by", r2.data.get("ended_by"), "seal")
    t.eq("c12.refusals.c.effects", {k: v for k, v in r2.effects.items() if k != "diagnostic"},
         {"run": "ended", "answer": "unchanged", "seal": "existing", "delivery": "verified"})
    sub_d = run_submission(t)
    t.cmd(["close", sub_d.ref], name="c12.refusals.d.close", expect="completed")
    fxd = rs.provider(t, fp.Script([]), label="closed")
    r2 = rs.run(t, sub_d, fxd, name="c12.refusals.d.run", expect="refused", reason="reference_closed")
    t.eq("c12.refusals.d.next", sorted({a[1] for a in r2.next_argvs()}), ["close", "status"])
    t.eq("c12.refusals.d.no-request", len(fxd.exchanges), 0)
    if t.bin["kind"] == "test" and is_linux():
        sub_e = run_submission(t)
        pe = proc(sub_e, ordinary_body)
        fxe = rs.provider(t, pe, label="held")
        h = rs.start_run(t, sub_e, fxe, name="c12.refusals.e.holder", fault="run.after_started=pause")
        stem = t.wait_paused("run.after_started", h)
        r2 = rs.run(t, sub_e, fxe, name="c12.refusals.e.second", expect="refused", reason="run_held")
        started = t.log_bodies(sub_e, "run_started")
        t.eq("c12.refusals.e.holder", (r2.data.get("run"), r2.data.get("holder")),
             (1, (started[0] or {}).get("observations") if started else None))
        t.eq("c12.refusals.e.effects", {k: v for k, v in r2.effects.items() if k != "diagnostic"},
             {"run": "still_held", "answer": "unchanged", "seal": "none", "delivery": "none"})
        t.eq("c12.refusals.e.next", sorted({a[1] for a in r2.next_argvs()}), ["close", "status"])
        t.release(stem)
        rs.finish_run(t, h)
    else:
        t.skip_part("run held", "needs the test build's pause point and Linux OFD locks")


# ---------------------------------------------------------------------------
# C13: a dead run continues; provider shapes; stopping.
# ---------------------------------------------------------------------------

@case("c13.continuation", ["C13", "C4", "C3", "C6"],
      "kills during a request, while a result is written and between turns: the continuation finishes once",
      mode="test", needs=("loopback", "lock"),
      linux_reason="interruption is observed through the free OFD lock, a Linux-only expectation",
      controls=[Control("reset_limits_on_continuation", [r"^c13\.cont\..*\.allowances$", r"^auditor\.reentry\.allowances$"]),
                Control("fresh_ledger_on_continuation", [r"^auditor\.", r"^c13\.cont\..*\.(same-answer|auditor-clean)$"])])
def c_continuation(t):
    """A reference audit seals the reacting auditor's goals. Three more are killed at
    provider.sent:12 (the request was sent, its answer never read: reconciliation charges one
    estimate), stage.torn:tool_result and run.between_turns:11. Each: status interrupted with
    one run; run continues with the same pinned system and tools bytes and the continuation
    notice, cumulative allowances, every earlier element once, and seals the same answer.json
    bytes as the reference; both run_ended records equal the fake's charges."""
    ref = run_submission(t)
    aud = auditor_for(t, ref, scenario_goals(ref), calls_per_turn=1)
    fx = rs.provider(t, aud, label="reference")
    rep = rs.run(t, ref, fx, name="c13.cont.reference.run")
    rs.check_auditor(t, aud, "c13.cont.reference")
    want = answer_of(t, rep, "c13.cont.reference")
    for label, fault, sent_k in (("during-request", "provider.sent:12=kill", 12),
                                 ("result-write", "stage.torn:tool_result=kill", None),
                                 ("between-turns", "run.between_turns:11=kill", None)):
        pre = "c13.cont." + label
        sub = run_submission(t)
        aud = auditor_for(t, sub, scenario_goals(sub), calls_per_turn=1)
        fx = rs.provider(t, aud, label=label)
        rs.run(t, sub, fx, name=pre + ".run-1", fault=fault, killed=True)
        first = fx.exchanges_of(pre + ".run-1")
        if sent_k is not None and t.check(pre + ".request-sent", len(first) >= sent_k, len(first)):
            fx.provider.charge_overrides[first[sent_k - 1].n] = "estimated"
        st = t.status(sub, name=pre + ".status")
        t.eq(pre + ".condition", st.data.get("condition"), "interrupted")
        t.eq(pre + ".runs", (st.data.get("runs") or {}).get("count"), 1)
        r2 = rs.run(t, sub, fx, name=pre + ".run-2")
        rs.check_run_reply(t, r2, sub, pre + ".run-2", ending="sealed", run_number=2, fx=fx, limits=rs.limits_of(sub),
                           seal_actor="auditor", delivery_outcome="verified")
        rs.check_auditor(t, aud, pre)
        second = fx.exchanges_of(pre + ".run-2")
        if first and second:
            a, b = first[0].body_node(), second[0].body_node()
            t.check(pre + ".same-pinned-bytes", a is not None and b is not None
                    and (a.get("system").raw, a.get("tools").raw) == (b.get("system").raw, b.get("tools").raw), "differs")
            rs.check_first_message(t, second[0], sub.body, True, pre + ".run-2")
        rs.check_run_ended_usage(t, sub, fx, [pre + ".run-1", pre + ".run-2"], pre)
        t.check(pre + ".same-answer", want is not None and answer_of(t, r2, pre) == want, "answer differs from the reference")


def _shape_placements(heavy):
    tu = lambda i, name="list", inp=b"{}": fp.tool_use("toolu_shape_%02d" % i, name, raw_input=inp)
    out = [
        ("echo", [fp.Message([fp.thinking("Considering.", "c2lnbmF0dXJl"), fp.redacted_thinking("ZW5jcnlwdGVk"),
                              fp.compaction("Earlier work summarized."), fp.unknown_block("server_note", note="kept"),
                              fp.text("Looking."), tu(1)], stop_reason="tool_use", framing="chunked"),
                  fp.Message([tu(2)], stop_reason="max_tokens", framing="close"),
                  fp.Message([fp.text("Cut short.")], stop_reason="max_tokens")],
         "max_tokens", ["response"] * 3, {}),
        ("refusal", [fp.Message([fp.text("I will not.")], stop_reason="refusal")], "provider_refusal", ["response"], {}),
        ("pause", [fp.Message([fp.text("Pausing.")], stop_reason="pause_turn")], "protocol_anomaly", ["response"], {}),
        ("unknown-stop", [fp.Message([fp.text("?")], stop_reason="brand_new_reason")], "protocol_anomaly", ["response"], {}),
        ("t15", [fp.Message([tu(3, "record_observation", b'{"text":"Recorded as the window closed."}')],
                            stop_reason="model_context_window_exceeded")], "context_exhausted", ["response"], {}),
        ("not-json", [fp.Message(body=b"this is not json")], "protocol_anomaly", ["response_undecodable"], {}),
        ("no-usage", [fp.Message(body=b'{"id":"msg_x","type":"message","role":"assistant","model":"m","content":[],'
                                      b'"stop_reason":"end_turn"}')], "protocol_anomaly", ["response_undecodable"], {}),
        ("repeated-member", [fp.Message(body=b'{"type":"message","content":[],"stop_reason":"end_turn",'
                                             b'"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1}}')],
         "protocol_anomaly", ["response_undecodable"], {}),
        ("gzip", [fp.Message([fp.text("x")], content_encoding="gzip")], "protocol_anomaly", ["response_undecodable"], {}),
        ("cut-off", [fp.Drop("mid_body", message=fp.Message([fp.text("never whole")])),
                     fp.Drop("mid_body", message=fp.HttpError(500)),
                     fp.Message([tu(4)], stop_reason="tool_use"), fp.Message([fp.text("p")], stop_reason="pause_turn")],
         "protocol_anomaly", ["connection_lost", "http_error", "response", "response"], {}),
        ("timeout", [fp.Stall(5.0) for _ in range(4)], "provider_unavailable", ["timeout"] * 4,
         {"STEWART_TEST_PROVIDER_TIMEOUT": "1"}),
        ("no-id", [fp.Message([fp.tool_use(None, "list", raw=b'{"type":"tool_use","name":"list","input":{}}')],
                              stop_reason="tool_use")], "protocol_anomaly", ["response"], {}),
        ("nul-id", [fp.Message([fp.tool_use(None, "list", raw=b'{"type":"tool_use","id":"toolu_\\u0000x","name":"list",'
                                                               b'"input":{}}')], stop_reason="tool_use")],
         "protocol_anomaly", ["response"], {}),
        ("no-tool-use", [fp.Message([fp.text("I will call a tool.")], stop_reason="tool_use")], "protocol_anomaly",
         ["response"], {}),
        ("nul-strings", [fp.Message([tu(5, "li\u0000st")], stop_reason="tool_use"),
                         fp.Message([fp.text("x")], stop_reason="end\u0000turn", model="claude\u0000x")],
         "protocol_anomaly", ["response", "response"], {}),
        ("nul-error", [fp.HttpError(400, error_type="invalid\u0000request", message="bad\u0000message")],
         "provider_rejected", ["http_error"], {}),
        ("retry-after-date", [fp.HttpError(503, retry_after="Wed, 21 Oct 2015 07:28:00 GMT"),
                              fp.Message([fp.text("p")], stop_reason="pause_turn")],
         "protocol_anomaly", ["http_error", "response"], {}),
    ]
    if heavy:
        out.append(("over-32mib", [fp.Message(body=b'{"x":"' + b"a" * ((32 << 20) + 16) + b'"}')], "protocol_anomaly",
                    ["response_undecodable"], {}))
    return out


@case("c13.provider-shapes", ["C13", "C1", "C6", "C14"],
      "T15 and every provider shape: blocks echoed, stop reasons, undecodable, cut-off, timeout and unanswerable answers",
      mode="test", needs=("loopback",))
def c_provider_shapes(t):
    """One audit, one placement per shape, each continuing the last: thinking, redacted,
    compaction and unknown blocks echoed byte for byte through chunked and close-delimited
    bodies; max_tokens with a call continues and without one interrupts; refusal, pause_turn,
    an unknown stop reason; T15 (model_context_window_exceeded with one call: executed,
    recorded, no further request); complete but undecodable 200s; a cut-off 200
    (connection_lost, retried) and a cut-off 500 (http_error); timeouts with a 1-second test
    timeout; a tool_use without an ID or with U+0000 in it (captured, not executed); a stop
    tool_use without a block; U+0000 in a tool name (tool_unknown), model and stop_reason, and in
    an error body (recorded null); a retry-after date ignored for the test delay. Each ending,
    cause and attempt outcome is as 6.3 to 6.6 state; charges follow 6.4."""
    sub = run_submission(t)
    shapes = _shape_placements(not t.drv.args.skip_heavy)
    fx = rs.provider(t, fp.Script([]))
    labels = []
    for i, (label, steps, cause, outcomes, env) in enumerate(shapes, 1):
        pre = "shape." + label
        labels.append(pre)
        script = fp.Script(steps)       # each placement has its own script, so one shape cannot shift the next
        fx.provider.responder = script
        rep = rs.run(t, sub, fx, name=pre, env=env, timeout=300)
        t.eq(pre + ".script-used", (script.used, script.exhausted), (len(steps), []))
        rs.check_run_reply(t, rep, sub, pre, ending="interrupted", cause=cause, run_number=i, fx=fx,
                           limits=rs.limits_of(sub))
        rd = rs.run_dirs(sub).get(i)
        if not t.check(pre + ".run-dir", rd is not None, sorted(rs.run_dirs(sub))):
            continue
        atts = [rd.attempts[k] for k in sorted(rd.attempts)]
        bodies = [(a or {}).get("body") or {} for a in atts]
        t.eq(pre + ".attempt-outcomes", [b.get("outcome") for b in bodies], outcomes)
        # 4.5 (amended): then is the decision about the attempt; a decoded response that is acted
        # on is use even when the placement then ends; end means no response is used.
        t.eq(pre + ".last-then", bodies[-1].get("then") if bodies else None,
             "use" if outcomes[-1] == "response" else "end")
        for b, o in zip(bodies, outcomes):
            basis = {"response": "reported", "http_error": "none"}.get(o, "estimated")
            t.eq("%s.charged.%s.%s" % (pre, b.get("request"), b.get("attempt")), (b.get("charged") or {}).get("basis"), basis)
        if label == "t15":
            t.eq(pre + ".one-request", len(fx.exchanges_of(pre)), 1)
            t.check(pre + ".call-recorded", any(rec is not None for _, _, _, rec in
                                                [c for c in rs.calls_and_results(sub) if c[0] == i]), "no result record")
        if label in ("no-id", "nul-id"):
            t.eq(pre + ".captured-not-executed", (len(rd.calls), len(rd.results)), (1, 0))
        if label == "cut-off":
            t.eq(pre + ".first-capture-incomplete", ((bodies[0].get("response") or {}).get("complete"), bodies[0].get("then")),
                 (False, "retry"))
        if label == "timeout":
            t.check(pre + ".timeout-seconds", all(b.get("timeout_seconds") == 1 for b in bodies), [b.get("timeout_seconds") for b in bodies])
        if label == "nul-strings":
            t.eq(pre + ".tool-unknown", (rs.result_envelope((rd.results.get(1) or {}).get("body") or {}) or {}).get("reason"),
                 "tool_unknown")
            t.eq(pre + ".model-null", bodies[-1].get("model") if bodies else "missing", None)
        if label == "nul-error":
            t.eq(pre + ".error-null", (bodies[0].get("error") or {}).get("type") if bodies else "missing", None)
            t.eq(pre + ".provider", (rep.data.get("provider") or {}).get("error_type", "missing"), None)
        if label == "retry-after-date":
            t.eq(pre + ".retry", (bodies[0].get("then"), bodies[0].get("delay_ms")) if bodies else None, ("retry", 0))
    t.eq("shape.fake-responder", fx.provider.anomalies, [])
    rs.check_requests(t, fx, sub, "shape")
    rs.check_history(t, fx, "shape")
    rs.check_run_ended_usage(t, sub, fx, labels, "shape")


@case("c13.stopping", ["C13", "C8", "C6"],
      "signals and close abort an in-flight request; a signal after the seal fails only the delivery",
      mode="test", needs=("loopback", "lock"),
      linux_reason="close reaches a held run through the OFD lock, a Linux-only expectation")
def c_stopping(t):
    """With a request stalled at the fake, SIGTERM, SIGINT and SIGHUP each abort it
    (aborted_by_signal, charged an estimate) and end the placement interrupted with cause
    signal, exit 5; run continues each time. Close during a stalled request aborts it
    (aborted_by_close) and the run ends stopped_by_close with exit 0 and next status and close.
    After a seal, SIGTERM while delivery is paused fails that delivery with cause signal and
    the placement still ends sealed."""
    sub = run_submission(t)
    fx = rs.provider(t, fp.Script([fp.Stall(60.0) for _ in range(4)]))
    stops = (("sigterm", signal.SIGTERM), ("sigint", signal.SIGINT), ("sighup", signal.SIGHUP), ("close", None))
    for i, (label, sig) in enumerate(stops, 1):
        pre = "stop." + label
        h = rs.start_run(t, sub, fx, name=pre)
        t.check(pre + ".request-in-flight", rs.wait_for(lambda: len(fx.exchanges_of(pre)) >= 1, 30), "no request")
        rs.wait_for(lambda: False, 0.3)
        if sig is not None:
            t.signal(h, sig)
            rep = rs.finish_run(t, h)
            rs.check_run_reply(t, rep, sub, pre, ending="interrupted", cause="signal", run_number=i, fx=fx,
                               limits=rs.limits_of(sub))
            want = "aborted_by_signal"
        else:
            cl = t.start(["close", sub.ref], name=pre + ".close", timeout=120)
            rep = rs.finish_run(t, h)
            rs.check_run_reply(t, rep, sub, pre, ending="stopped_by_close", run_number=i, fx=fx,
                               limits=rs.limits_of(sub))
            t.finish(cl, expect="completed")
            want = "aborted_by_close"
        rd = rs.run_dirs(sub).get(i)
        att = ((rd.attempts.get((1, 1)) or {}).get("body") or {}) if rd else {}
        t.eq(pre + ".attempt", (att.get("outcome"), att.get("request_written"), (att.get("charged") or {}).get("basis")),
             (want, "complete", "estimated"))
    sub2 = run_submission(t)

    def seal_body(p):
        yield from prepare_and_submit(p)
    p = proc(sub2, seal_body)
    fx2 = rs.provider(t, p, label="sealed")
    h = rs.start_run(t, sub2, fx2, name="stop.after-seal", fault="delivery.after_member:1=pause")
    stem = t.wait_paused("delivery.after_member", h)
    t.signal(h, signal.SIGTERM)
    t.release(stem)
    rep = rs.finish_run(t, h)
    rs.check_run_reply(t, rep, sub2, "stop.after-seal", ending="sealed", run_number=1, fx=fx2,
                       limits=rs.limits_of(sub2), seal_actor="auditor", delivery_outcome="failed")
    t.check("stop.after-seal.cause", mentions((rep.data.get("delivery") or {}).get("cause"), "signal"),
            rep.data.get("delivery"))
    rs.check_procedure(t, p, "stop.after-seal", fx2)


# ---------------------------------------------------------------------------
# C14: refusals are recorded; no verdicts.
# ---------------------------------------------------------------------------

@case("c14.refusals-recorded", ["C14", "C6", "C5"],
      "every refused call is recorded with its bytes and reason; nothing grades the answer",
      needs=("loopback",),
      controls=[Control("drop_refused_capture", [r"^c14\.a\.refused-captured\."]),
                Control("manifest_verdict", [r"^c14\.a\.(manifest-keys|no-verdict)"])])
def c_refusals_recorded(t):
    """A refused citation, a path outside the material, a stale replace and a duplicate-key
    input are each kept as a call capture with the exact block bytes and a result record with
    the reason, is_error and the content sent; none creates an entry. The audit seals and
    delivers. No manifest, log record, result envelope, run reply or status holds a key that
    grades the answer; the manifest holds exactly its 8.2 keys. Differing: each kind has its
    own reason. Invariance: without the refused calls, the same answer.json bytes."""
    answers = {}
    for label in ("a", "b"):
        pre = "c14." + label
        sub = run_submission(t)
        refused = []

        def body(p, label=label, refused=refused):
            if label == "a":
                turn = yield p.calls_step(("record_observation", {"text": "bad", "citations": [
                    {"source": "materials/a.py", "start": 0, "end": 100000}]}), ("read", {"source": "../question.md"}))
                refused += [(r.tid, r.reason, r.content_raw) for r in turn.replies]
            turn = yield p.calls_step(("record_observation", {"text": "ok", "label": "kept"}))
            h = turn.reply(0).data.get("entry")
            turn = yield p.calls_step(("replace", {"entry": h, "text": "ok, revised", "citations": [], "label": "kept"}))
            if label == "a":
                turn = yield p.calls_step(("replace", {"entry": h, "text": "stale", "citations": [], "label": "kept"}))
                refused += [(r.tid, r.reason, r.content_raw) for r in turn.replies]
                turn = yield p.step([p.call("record_observation", raw_input=b'{"text":"a","text":"b"}')])
                refused += [(r.tid, r.reason, r.content_raw) for r in turn.replies]
            yield from prepare_and_submit(p)
        p = proc(sub, body)
        fx = rs.provider(t, p, label=label)
        rep = rs.run(t, sub, fx, name=pre + ".run")
        rs.check_run_reply(t, rep, sub, pre + ".run", ending="sealed", run_number=1, fx=fx, limits=rs.limits_of(sub),
                           seal_actor="auditor", delivery_outcome="verified")
        rs.check_procedure(t, p, pre, fx)
        answers[label] = answer_of(t, rep, pre)
        t.eq(pre + ".entries", [b.get("action") for b in rs.entry_bodies(t, sub)], ["add", "replace"])
        if label == "a":
            t.eq(pre + ".reasons", [x[1] for x in refused], ["citation_invalid", "source_unknown", "stale_entry", "input_invalid"])
            for tid, reason, content in refused:
                res = rs.result_for(sub, tid)
                ok = (res is not None and res[2] == p.calls[tid]["raw_block"] and res[3] is not None
                      and res[3].get("is_error") is True and rs.result_envelope(res[3]) is not None
                      and rs.result_envelope(res[3]).get("reason") == reason
                      and res[3].get("content") == json.loads(content.decode("utf-8")))
                t.check(pre + ".refused-captured.%s" % reason, ok, res and {"capture": res[2], "record": res[3]})
            loc = rs.package_of(rep)
            man = rs.read_package_member(loc, "manifest.json") if loc else None
            mobj = json.loads(man.decode("utf-8")) if man else {}
            t.eq(pre + ".manifest-keys", list(mobj), ["schema", "audit", "store", "family", "renderer", "writer", "seal",
                                                     "revision", "members", "unproduced"])
            st = t.status(sub, name=pre + ".status")
            scanned = [mobj, rep.obj, st.obj] + [r["obj"] for r in t.read_log(sub)]
            scanned += [rs.result_envelope(c[3].get("body") or {}) for c in rs.calls_and_results(sub) if c[3]]
            t.eq(pre + ".no-verdict", [k for o in scanned for k in rs.verdict_keys(o)], [])
    t.check("c14.invariance.same-answer", answers.get("a") is not None and answers.get("a") == answers.get("b"),
            "refused calls changed the sealed answer")


# ---------------------------------------------------------------------------
# C20: tool inputs, views and seal facts.
# ---------------------------------------------------------------------------

BAD_INPUTS = [
    ("duplicate-key", "record_observation", b'{"text":"a","text":"b"}', "/text"),
    ("escaped-duplicate", "record_observation", b'{"text":"a","\\u0074ext":"b"}', "/text"),
    ("unknown-field", "record_observation", b'{"text":"a","colour":1}', "/colour"),
    ("nul", "record_observation", b'{"text":"a\\u0000b"}', "/text"),
    ("not-object", "record_observation", b'[1]', None),
    ("mistyped-citations", "record_observation", b'{"text":"a","citations":"none"}', "/citations"),
    ("depth-17", "record_observation", b'{"text":"a","label":' + b"[" * 17 + b"]" * 17 + b"}", None),
    ("negative-start", "read", b'{"source":"question","start":-1}', "/start"),
    ("huge-start", "read", b'{"source":"question","start":99999999999999999999999}', "/start"),
    ("string-start", "read", b'{"source":"question","start":"0"}', "/start"),
    ("fraction-start", "read", b'{"source":"question","start":1.0}', "/start"),
    ("missing-source", "read", b'{}', "/source"),
]


@case("c20.tool-inputs", ["C20", "C14", "C9"],
      "strict tool inputs refuse usefully with raw bytes kept; views hide custody; seal facts are exact",
      needs=("loopback",),
      controls=[Control("accept_unknown_tool_field", [r"^c20\.inputs\.input\.unknown-field$"]),
                Control("leak_custody_path", [r"^c20\.inputs\.reply\.envelope\.read$"]),
                Control("prepare_claims_seal", [r"^c20\.inputs\.prepare-no-sealer$"]),
                Control("stale_preparation_retargets", [r"^c20\.inputs\.stale-preparation"]),
                Control("seal_uncertain_as_none", [r"^c20\.uncertain\.effects$"]),
                Control("submit_claims_delivery", [r"^c20\.inputs\.submit-data$"])])
def c_tool_inputs(t):
    """Duplicate and escape-equivalent keys, an unknown field, NUL, a non-object input, the
    wrong type, nesting deeper than 16, out-of-bound and non-integer starts and a missing
    required field each refuse input_invalid naming the JSON pointer (an unknown field also
    naming the expected keys); each call capture keeps the exact block bytes. An unknown tool
    refuses tool_unknown naming the tools. Constructed entry and view handles refuse
    handle_invalid. Replies carry no host path. Prepare names no sealer. Submit with a stale
    preparation refuses stale_preparation with revision_now and a prepare next call; "true"
    for confirm is input_invalid; a dry run seals nothing; the confirmed submit's recorded data
    is exactly seal, sealer, sealed_at, revision and manifest_sha256, claiming no delivery. On
    the test build an uncertain seal publication (log.dirsync:seal=eio) fails seal_uncertain
    with effects.seal unknown and the same submit as next call."""
    sub = run_submission(t)
    box = {}

    def body(p):
        turn = yield p.step([p.call(tool, raw_input=raw) for _, tool, raw, _ in BAD_INPUTS])
        box["bad"] = [(lab, r.tid) for (lab, _, _, _), r in zip(BAD_INPUTS, turn.replies)]
        for (lab, tool, raw, ptr), r in zip(BAD_INPUTS, turn.replies):
            p.check("input.%s" % lab, r.outcome == "refused" and r.reason == "input_invalid"
                    and (ptr is None or mentions(r.env, ptr)), {"outcome": r.outcome, "reason": r.reason,
                                                               "message": (r.env or {}).get("message")})
            if lab == "unknown-field":
                p.check("input.unknown-field.expected-keys", mentions(r.env, "citations") and mentions(r.env, "label"), r.env)
        turn = yield p.calls_step(("shell", {"command": "ls"}))
        r = turn.reply(0)
        p.check("tool-unknown", r.outcome == "refused" and r.reason == "tool_unknown" and mentions(r.env, "record_observation"),
                r.env)
        yield from p.read_all("materials/a.py")
        turn = yield p.calls_step(("record_observation", {"text": "first"}))
        h1 = turn.reply(0).data.get("entry")
        turn = yield p.calls_step(("prepare", {}))
        r = turn.reply(0)
        p.check("prepare-no-sealer", r.outcome == "completed" and "sealer" not in r.data and "seal" not in r.data, r.data)
        ap1 = r.data.get("prepared")
        forged = (h1 or "e1.v1.zzzzzz").rsplit(".", 1)[0] + "." + ("aaaaaa" if not (h1 or "").endswith("aaaaaa") else "bbbbbb")
        turn = yield p.calls_step(("replace", {"entry": forged, "text": "x", "citations": [], "label": ""}),
                                  ("read", {"source": "ap1.aaaaaa/rendering" if ap1 != "ap1.aaaaaa" else "ap1.bbbbbb/rendering"}))
        p.eq("constructed-handles", [(r.outcome, r.reason) for r in turn.replies],
             [("refused", "handle_invalid"), ("refused", "handle_invalid")])
        turn = yield p.calls_step(("record_observation", {"text": "second"}))
        step = p.calls_step(("submit", {"prepared": ap1, "confirm": True}))
        box["stale_submit"] = p.pending[0] if p.pending else None
        turn = yield step
        r = turn.reply(0)
        p.eq("stale-preparation", (r.outcome, r.reason, r.data.get("revision_now")), ("refused", "stale_preparation", 2))
        p.check("stale-preparation.next", any(n.get("tool") == "prepare" for n in r.next), r.next)
        turn = yield p.calls_step(("prepare", {}))
        ap2 = turn.reply(0).data.get("prepared")
        turn = yield p.step([p.call("submit", raw_input=rawjson_compact({"prepared": ap2, "confirm": "true"}))])
        r = turn.reply(0)
        p.check("confirm-string", r.outcome == "refused" and r.reason == "input_invalid" and mentions(r.env, "/confirm"), r.env)
        turn = yield p.calls_step(("submit", {"prepared": ap2}))
        r = turn.reply(0)
        p.eq("dry-run", (r.outcome, r.data.get("dry_run"), r.effects.get("seal")), ("completed", True, "none"))
        turn = yield p.calls_step(("submit", {"prepared": ap2, "confirm": True}))
        box["submit"] = turn.reply(0) if turn else None
    p = proc(sub, body)
    fx = rs.provider(t, p)
    rep = rs.run(t, sub, fx, name="c20.inputs.run")
    rs.check_run_reply(t, rep, sub, "c20.inputs.run", ending="sealed", run_number=1, fx=fx, limits=rs.limits_of(sub),
                       seal_actor="auditor", delivery_outcome="verified")
    rs.check_procedure(t, p, "c20.inputs", fx)
    for lab, tid in box.get("bad", []):
        res = rs.result_for(sub, tid)
        t.check("c20.inputs.raw-kept.%s" % lab, res is not None and res[2] == p.calls[tid]["raw_block"],
                res and res[2][:200])
    # The stale submit, judged from the archive too: had it sealed, the run would have ended
    # there and the procedure's own check would never have been recorded.
    res = rs.result_for(sub, box.get("stale_submit"))
    env = rs.result_envelope(res[3]) if res and res[3] else None
    t.eq("c20.inputs.stale-preparation.recorded", ((env or {}).get("outcome"), (env or {}).get("reason")),
         ("refused", "stale_preparation"))
    t.check("c20.inputs.reached-final-submit", sum(1 for c in p.calls.values() if c["tool"] == "submit") >= 4,
            [c["input"] for c in p.calls.values() if c["tool"] == "submit"])
    seals = [b for b in t.log_bodies(sub, "seal") if isinstance(b, dict)]
    t.eq("c20.inputs.stale-preparation.seal-revision", [b.get("revision") for b in seals], [2])
    tid = last_call(p, "submit")
    res = rs.result_for(sub, tid)
    env = rs.result_envelope(res[3]) if res and res[3] else None
    d = (env or {}).get("data") or {}
    t.eq("c20.inputs.submit-data", sorted(d), sorted(["seal", "sealer", "sealed_at", "revision", "manifest_sha256"]))
    t.eq("c20.inputs.submit-sealer", d.get("sealer"), "auditor")
    if t.bin["kind"] != "test":
        return
    sub2 = run_submission(t)

    def unc(p):
        yield p.calls_step(("record_observation", {"text": "before an uncertain seal"}))
        yield from prepare_and_submit(p)
    p2 = proc(sub2, unc)
    fx2 = rs.provider(t, p2, label="uncertain")
    rep = rs.run(t, sub2, fx2, name="c20.uncertain.run", fault="log.dirsync:seal=eio")
    # 6.3 (amended): whether a seal was recorded is read from the log after the blocks run; the
    # seal was linked, so the run delivers and ends sealed, and no request or reminder follows.
    t.eq("c20.uncertain.ending", rep.data.get("ending"), "sealed")
    t.eq("c20.uncertain.seal-actor", [b.get("actor") for b in t.log_bodies(sub2, "seal") if isinstance(b, dict)],
         ["auditor"])
    t.eq("c20.uncertain.no-reminder", [b.get("type") for b in t.log_bodies(sub2, "notice") if isinstance(b, dict)], [])
    rs.check_procedure(t, p2, "c20.uncertain", fx2)
    tid = last_call(p2, "submit")
    res = rs.result_for(sub2, tid)
    env = rs.result_envelope(res[3]) if res and res[3] else {}
    t.eq("c20.uncertain.outcome", ((env or {}).get("outcome"), (env or {}).get("reason")), ("failed", "seal_uncertain"))
    t.eq("c20.uncertain.effects", ((env or {}).get("effects") or {}).get("seal"), "unknown")
    t.check("c20.uncertain.next", any(n.get("tool") == "submit" for n in (env or {}).get("next") or []), env)


def rawjson_compact(v):
    import rawjson
    return rawjson.compact(v)
