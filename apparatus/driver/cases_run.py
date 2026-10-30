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

import fake_provider as fp
import run_support as rs
from driver_core import *  # noqa: F401,F403
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
    forbidden = [sub.archive, sub.folder, sub.ref, sub.store, sub.family, sub.dest]
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
    rs.check_refused_before_request(t, rep, pre, fx, "env.not-accepted")
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
    r1 = rs.run(t, sub, fx, name="t7.run-1", fault="entry.after_link=kill")
    t.eq("t7.run-1.killed", r1.rc, -signal.SIGKILL)
    t.eq("t7.run-1.no-reply", r1.stdout, b"")
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
