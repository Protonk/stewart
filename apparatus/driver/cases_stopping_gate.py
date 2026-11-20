"""The publication gate a signal closes, and close winning a start reservation.

INTERFACE 6.8 (a signal before a seal closes the executing mutation's publication gate:
a mutation whose log record has not begun to link is refused `placement_stopped` and links
nothing; one whose link had begun completes it; a durable `close_requested` that won the
log order first refuses it `authoring_ended` instead), 7.1 and Appendix A
(`placement_stopped`), 4.4 (publication settles run start against close with one order),
5.7 (refusals and their next calls) and Appendix C.1 (the fault points used to hold each
process at a named point). Every expected value comes from those texts and from the fake
provider's own witness; none is taken from an observed reply.
"""
import signal

import run_support as rs
from cases_notices import check_interrupted_status
from cases_run import last_call, prepare_and_submit, proc, run_submission
from driver_core import AT_RE, case, mentions, seal_observation

OBSERVATION = "Recorded before the placement was stopped."
# How long a held process is left after a signal before its pause is released. The
# specification gives the signal no external witness on the Messages path; a second
# is far beyond a signal handler's delivery.
SETTLE = 1.0


def _settle():
    rs.wait_for(lambda: False, SETTLE)


def _refused_result(t, sub, tid, name, tool, reason, effects, revision=None):
    """The result record of a refused mutation (4.5, 7.1): it holds the refusal, published
    no log record, and its envelope names the reason with exactly the tool's effect keys."""
    res = rs.result_for(sub, tid)
    if not t.check(name + ".result-record", res is not None and isinstance(res[3], dict), res):
        return None
    body = res[3]
    env = rs.result_envelope(body) or {}
    t.eq(name + ".result", (body.get("outcome"), body.get("reason"), body.get("log_record"), body.get("is_error")),
         ("refused", reason, None, True))
    t.eq(name + ".envelope", (env.get("operation"), env.get("outcome"), env.get("reason")), (tool, "refused", reason))
    t.eq(name + ".envelope.effects", {k: v for k, v in (env.get("effects") or {}).items() if k != "diagnostic"},
         effects)
    t.check(name + ".envelope.message", isinstance(env.get("message"), str) and bool(env["message"].strip()),
            env.get("message"))
    if revision is not None:
        t.eq(name + ".result.revision", body.get("revision"), revision)
    return env


def _submit_body(continue_after):
    """Record one observation, prepare and submit. continue_after: a continuation follows
    the stopped placement; it re-enters, finds the observation and no seal, and submits."""
    def body(p):
        turn = yield p.calls_step(("record_observation", {"text": OBSERVATION, "label": "kept"}))
        r = turn.reply(0)
        p.eq("recorded", (r.outcome, r.data.get("id")) if r else None, ("completed", "e1"))
        turn = yield p.calls_step(("prepare", {}))
        r = turn.reply(0)
        p.eq("prepare", r.outcome if r else None, "completed")
        turn = yield p.calls_step(("submit", {"prepared": r.data.get("prepared") if r else None, "confirm": True}))
        if turn is None or not continue_after:
            return
        p.check("continuation.new-conversation", turn.new_conversation, "the next request did not start a conversation")
        turn = yield p.calls_step(("what_am_i_working_with", {}))
        r = turn.reply(0)
        data = r.data if r else {}
        p.eq("continuation.seal", data.get("seal"), seal_observation())
        p.eq("continuation.entries", [e.get("id") for e in data.get("entries") or []], ["e1"])
        yield from prepare_and_submit(p, "continuation")
    return body


def _entry_body(p):
    """Record one observation; when a continuation follows, re-enter, find no entry and
    record it there before submitting."""
    turn = yield p.calls_step(("record_observation", {"text": OBSERVATION, "label": "kept"}))
    if turn is None:
        return
    p.check("continuation.new-conversation", turn.new_conversation, "the next request did not start a conversation")
    turn = yield p.calls_step(("what_am_i_working_with", {}))
    r = turn.reply(0)
    data = r.data if r else {}
    p.eq("continuation.entries", [e.get("id") for e in data.get("entries") or []], [])
    p.eq("continuation.revision", data.get("revision"), 0)
    turn = yield p.calls_step(("record_observation", {"text": OBSERVATION, "label": "kept"}))
    r = turn.reply(0)
    p.eq("continuation.recorded", (r.outcome, r.data.get("id")) if r else None, ("completed", "e1"))
    yield from prepare_and_submit(p, "continuation")


@case("c13.signal-gate", ["C13", "C3", "C8", "C20"],
      "a signal closes the executing mutation's publication gate before its link; a begun link completes; "
      "a close that won first is named instead",
      mode="test", needs=("loopback",),
      faults=("log.publish:seal=pause", "log.publish:entry=pause", "log.dirsync:seal=pause", "seal.after_link=pause", "close.after_requested=pause"))
def c_signal_gate(t):
    """Each arm holds the run at an Appendix C.1 point inside one auditor mutation, signals
    the run, waits, then releases it (6.8).

    before-link.submit (SIGTERM at log.publish:seal, immediately before the seal's link):
    the submit is refused placement_stopped, its result record holds the refusal with
    seal none, no seal record exists, and the placement ends interrupted with cause signal,
    exit 5. Authoring stays open: status is interrupted with run and close, and the
    continuation re-enters to the unsealed observation and seals it.
    before-link.entry (SIGHUP at log.publish:entry): invariance over the mutation and the
    signal: the record call is refused placement_stopped with answer unchanged, no entry
    record exists and the continuation starts from revision 0.
    link-begun.dirsync (SIGTERM at log.dirsync:seal, after the seal's linkat): differing:
    the link had begun, so it completes; the seal stands with the auditor's attribution, the
    submit completed naming that record, and the placement ends sealed, exit 0, with its
    delivery attempt failed with cause signal. link-begun.after-link (SIGINT at
    seal.after_link) is the same with the seal fully published.
    close-first (close_requested durable and observed, then SIGTERM, then release) and
    signal-first (SIGTERM, then close_requested durable, then release): close won the held
    link's log slot in both, so the submit is refused authoring_ended naming close and its
    close_requested_at, with an absent seal observation, and only close's manager seal
    follows. The first observed condition decides the ending: stopped_by_close, exit 0,
    against interrupted with cause signal, exit 5."""
    for label, point, sig, mutation in (
            ("before-link.submit", "log.publish:seal", signal.SIGTERM, "submit"),
            ("before-link.entry", "log.publish:entry", signal.SIGHUP, "entry"),
            ("link-begun.dirsync", "log.dirsync:seal", signal.SIGTERM, "submit"),
            ("link-begun.after-link", "seal.after_link", signal.SIGINT, "submit")):
        pre = "gate." + label
        begun = label.startswith("link-begun")
        sub = run_submission(t)
        p = proc(sub, _entry_body if mutation == "entry" else _submit_body(continue_after=not begun))
        fx = rs.provider(t, p, label=label)
        name = pre + ".run-1"
        h = rs.start_run(t, sub, fx, name=name, fault=point + "=pause")
        stem = t.wait_paused(point.split(":")[0], h)
        # Before the link no seal record exists; once linkat has run it does (4.3).
        t.eq(pre + ".seal-linked-while-held", "seal" in t.log_kinds(sub), begun)
        t.signal(h, sig)
        _settle()
        t.release(stem)
        rep = rs.finish_run(t, h)
        tid = last_call(p, "record_observation" if mutation == "entry" else "submit")
        seals = [b for b in t.log_bodies(sub, "seal") if isinstance(b, dict)]
        if not begun:
            rs.check_run_reply(t, rep, sub, name, ending="interrupted", cause="signal", run_number=1, fx=fx,
                               limits=rs.limits_of(sub))
            t.eq(name + ".exit", rep.rc, 5)
            t.eq(name + ".effects", {k: v for k, v in rep.effects.items() if k != "diagnostic"},
                 {"run": "ended", "answer": "unchanged" if mutation == "entry" else "changed", "seal": "none",
                  "delivery": "none"})
            rs.check_run_ended(t, sub, 1, name, ending="interrupted", cause="signal")
            t.eq(pre + ".no-seal-record", seals, [])
            if mutation == "entry":
                _refused_result(t, sub, tid, pre + ".refused", "record_observation", "placement_stopped",
                                {"answer": "unchanged", "raw_capture": "recorded"}, revision=0)
                t.eq(pre + ".no-entry-record", rs.entry_bodies(t, sub), [])
            else:
                _refused_result(t, sub, tid, pre + ".refused", "submit", "placement_stopped",
                                {"seal": "none", "raw_capture": "recorded"})
            st = check_interrupted_status(t, sub, fx, pre + ".status", "signal")
            t.eq(pre + ".status.seal", st.data.get("seal"), seal_observation())
            t.eq(pre + ".status.entries", (st.data.get("answer") or {}).get("entries"), 0 if mutation == "entry" else 1)
            if seals:
                # The measured property already failed: a linked seal ends authoring, so a
                # continuation would only repeat that failure.
                t.skip_part(pre + ".run-2", "not run: the held submit linked a seal")
            else:
                rep2 = rs.run(t, sub, fx, name=pre + ".run-2")
                rs.check_run_reply(t, rep2, sub, pre + ".run-2", ending="sealed", run_number=2, fx=fx,
                                   limits=rs.limits_of(sub), seal_actor="auditor", delivery_outcome="verified")
        else:
            rs.check_run_reply(t, rep, sub, name, ending="sealed", run_number=1, fx=fx, limits=rs.limits_of(sub),
                               seal_actor="auditor", delivery_outcome="failed")
            t.eq(name + ".exit", rep.rc, 0)
            t.check(name + ".delivery-cause", mentions((rep.data.get("delivery") or {}).get("cause"), "signal"),
                    rep.data.get("delivery"))
            t.eq(pre + ".seal-stands", [(b.get("actor"), (b.get("invocation") or {}).get("tool_use_id"))
                                        for b in seals], [("auditor", tid)])
            ended = [b for b in t.log_bodies(sub, "delivery_ended") if isinstance(b, dict)]
            t.eq(pre + ".delivery-ended", [(b.get("attempt"), b.get("outcome"), b.get("recorded_by")) for b in ended],
                 [(1, "failed", "run")])
            t.check(pre + ".delivery-ended.cause", bool(ended) and mentions(ended[0].get("cause"), "signal"),
                    ended[:1])
            rs.check_run_ended(t, sub, 1, name, ending="sealed", cause=None)
            res = rs.result_for(sub, tid)
            body = res[3] if res and isinstance(res[3], dict) else {}
            seal_name = [r["name"] for r in t.read_log(sub)
                         if isinstance(r["obj"], dict) and r["obj"].get("kind") == "seal"]
            t.eq(pre + ".submit-completed", (body.get("outcome"), body.get("log_record")),
                 ("completed", "log/" + seal_name[0] if seal_name else "a seal record"))
            st = t.status(sub, name=pre + ".status")
            t.eq(pre + ".status.condition", st.data.get("condition"), "sealed_undelivered")
            t.eq(pre + ".status.seal", (st.data.get("headline") or {}).get("seal"), seal_observation("auditor"))
        rs.check_procedure(t, p, pre, fx)

    # Both a close request and a signal before a seal: the first observed decides the
    # ending, while the held mutation is refused by whichever reached the log slot first.
    # Here close_requested is durable before the held link in both orders, so the submit is
    # refused authoring_ended either way (6.8).
    for order in ("close-first", "signal-first"):
        pre = "gate." + order
        sub = run_submission(t)
        p = proc(sub, _submit_body(continue_after=False))
        fx = rs.provider(t, p, label=order)
        name = pre + ".run"
        h = rs.start_run(t, sub, fx, name=name, fault="log.publish:seal=pause")
        stem = t.wait_paused("log.publish", h)
        if order == "signal-first":
            t.signal(h, signal.SIGTERM)
            _settle()
        hc = t.start(["close", sub.ref], name=pre + ".close", fault="close.after_requested=pause", timeout=120)
        cstem = t.wait_paused("close.after_requested", hc)
        requested = [r["obj"] for r in t.read_log(sub)
                     if isinstance(r["obj"], dict) and r["obj"].get("kind") == "close_requested"]
        t.eq(pre + ".close-requested-durable", len(requested), 1)
        _settle()  # the 250 ms watcher has observed it (6.8)
        if order == "close-first":
            t.signal(h, signal.SIGTERM)
            _settle()
        t.release(stem)
        rep = rs.finish_run(t, h)
        t.release(cstem)
        t.finish(hc, expect="completed")
        tid = last_call(p, "submit")
        env = _refused_result(t, sub, tid, pre + ".refused", "submit", "authoring_ended",
                              {"seal": "none", "raw_capture": "recorded"})
        d = (env or {}).get("data") or {}
        at = requested[0].get("at") if requested else None
        t.eq(pre + ".refused.data", (d.get("ended_by"), d.get("close_requested_at"), d.get("seal")),
             ("close", at, seal_observation()))
        t.check(pre + ".refused.at-form", isinstance(at, str) and bool(AT_RE.match(at)), at)
        t.eq(pre + ".seals", [b.get("actor") for b in t.log_bodies(sub, "seal") if isinstance(b, dict)], ["manager"])
        t.eq(pre + ".run.outcome", rep.outcome, "completed")
        t.eq(pre + ".run.effects.seal", rep.effects.get("seal"), "none")
        data = rep.data if isinstance(rep.data, dict) else {}
        want = ("stopped_by_close", None, 0) if order == "close-first" else ("interrupted", "signal", 5)
        t.eq(pre + ".first-observed-decides", (data.get("ending"), data.get("cause"), rep.rc), want)
        rs.check_run_ended(t, sub, 1, name, ending=want[0], cause=want[1])
        rs.check_procedure(t, p, pre, fx)


@case("c12.start-races-close", ["C12", "C8", "C16", "C20"],
      "close winning the log order while run holds its start before run_started: refused reference_closed, "
      "nothing launched",
      mode="test", needs=("loopback",),
      faults=("log.publish:run_started=pause", "close.after_requested=pause"))
def c_start_races_close(t):
    """close-wins: run is held at log.publish:run_started (immediately before linking its
    start, C.1); close publishes close_requested and is held after it
    (close.after_requested); run is released. Publication settles the race with one order
    (4.4): run refuses reference_closed (5.7), changes nothing (effects run not_started,
    answer unchanged, seal none, delivery none), offers close and status, exits 3, reaches
    no provider and creates no runs/1. Released, close completes before launch.
    close-before-run: invariance: the same reply when close_requested already exists before
    run begins. run-wins: differing: the same hold released without a close starts the
    placement, which seals."""
    seen = {}
    for label in ("close-wins", "close-before-run", "run-wins"):
        pre = "start-race." + label
        sub = run_submission(t)

        def body(p):
            yield from prepare_and_submit(p)
        p = proc(sub, body)
        fx = rs.provider(t, p, label=label)
        name = pre + ".run"
        if label == "close-before-run":
            hc = t.start(["close", sub.ref], name=pre + ".close", fault="close.after_requested=pause", timeout=120)
            cstem = t.wait_paused("close.after_requested", hc)
            rep = rs.run(t, sub, fx, name=name, expect="refused", reason="reference_closed")
        else:
            h = rs.start_run(t, sub, fx, name=name, fault="log.publish:run_started=pause")
            stem = t.wait_paused("log.publish", h)
            t.check(pre + ".held-before-start", "run_started" not in t.log_kinds(sub), t.log_kinds(sub))
            if label == "close-wins":
                hc = t.start(["close", sub.ref], name=pre + ".close", fault="close.after_requested=pause", timeout=120)
                cstem = t.wait_paused("close.after_requested", hc)
                t.eq(pre + ".close-requested-first", [k for k in t.log_kinds(sub) if k in ("close_requested", "run_started")],
                     ["close_requested"])
            t.release(stem)
            if label == "run-wins":
                rep = rs.finish_run(t, h)
                rs.check_run_reply(t, rep, sub, name, ending="sealed", run_number=1, fx=fx, limits=rs.limits_of(sub),
                                   seal_actor="auditor", delivery_outcome="verified")
                rs.check_procedure(t, p, pre, fx)
                continue
            rep = rs.finish_run(t, h, expect="refused", reason="reference_closed")
        rs.check_refused_before_request(t, rep, sub, fx, name, next_run=False)
        t.eq(name + ".exit", rep.rc, 3)
        t.eq(name + ".next", sorted(tuple(a) for a in rep.next_argvs()),
             sorted([(sub.writer, "close", sub.ref), (sub.writer, "status", sub.ref)]))
        t.check(name + ".no-run-directory", sorted(rs.run_dirs(sub)) == [], sorted(rs.run_dirs(sub)))
        seen[label] = (rep.outcome, rep.reason, {k: v for k, v in rep.effects.items() if k != "diagnostic"},
                       sorted(a[1] for a in rep.next_argvs()))
        t.release(cstem)
        closing = t.finish(hc, expect="completed")
        cd = closing.data if isinstance(closing.data, dict) else {}
        t.eq(pre + ".close", (cd.get("closure"), cd.get("before_launch")), ("complete", True))
        st = t.status(sub, name=pre + ".status")
        t.eq(pre + ".status.condition", st.data.get("condition"), "closed_before_launch")
        t.eq(pre + ".status.runs", (st.data.get("runs") or {}).get("count"), 0)
    if "close-wins" in seen and "close-before-run" in seen:
        t.eq("start-race.invariance", seen["close-wins"], seen["close-before-run"])
