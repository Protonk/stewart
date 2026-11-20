"""Notice claims, their durability and transmission evidence, across continuation.

INTERFACE 4.4 (`notice` and `run_ended` bodies), 6.4 (the one-reminder and
one-notice allowances and `sent`/`not_sent`/`unknown`), 6.5 (archive write failure),
6.7 (continuation) and Appendix C.1 (fault points by record kind). Every expected value
comes from those texts and from the fake provider's own witness of what it received.
"""
import fake_provider as fp
import run_support as rs
from cases_run import proc, run_submission
from driver_core import NEAR_LIMIT, REMINDER, Control, case, mentions

OBSERVATION = "Recorded before the turn ended."
RUN_ENDED_KEYS = ["prev", "run", "ending", "cause", "recorded_by", "provider", "requests", "attempts", "usage",
                  "notices", "seal", "message"]
NOTICE_KEYS = ["prev", "type", "run", "request", "text", "remaining"]


def notice_records(t, sub):
    """[(log name, body)] of every notice record, in log order."""
    return [(r["name"], r["obj"].get("body")) for r in t.read_log(sub)
            if isinstance(r["obj"], dict) and r["obj"].get("kind") == "notice"]


def reminder_body(spent, transmitted):
    """Placement 1 records one entry, then ends its turn without submitting (6.4: the reminder
    is claimed for request 3). transmitted: whether request 3 reaches the fake carrying it.
    The continuation re-enters, then ends its turn. When the reminder was claimed (spent) that
    stop is an ordinary ending; otherwise it receives the reminder first (CONTRACTS, bounded
    prompting; INTERFACE 6.4: the allowance is audit-wide)."""
    def body(p):
        turn = yield p.calls_step(("record_observation", {"text": OBSERVATION, "label": "kept"}))
        r = turn.reply(0)
        p.eq("placement-1.recorded", (r.outcome, r.data.get("id"), r.data.get("revision")) if r else None,
             ("completed", "e1", 1))
        turn = yield p.end("Stopping without submitting.")
        if transmitted:
            p.eq("placement-1.reminder-carried", (turn.new_conversation, turn.texts), (False, [REMINDER]))
            turn = yield p.end("Stopping again.")
            if turn is None:
                return
        p.check("continuation.new-conversation", turn is not None and turn.new_conversation,
                "the next request did not start a new conversation")
        turn = yield p.calls_step(("what_am_i_working_with", {}))
        r = turn.reply(0)
        data = r.data if r else {}
        p.eq("continuation.notices-used", data.get("notices_used"), {"reminder": spent, "near_limit": False})
        p.eq("continuation.entries", [e.get("id") for e in data.get("entries") or []], ["e1"])
        p.eq("continuation.reentry-texts", turn.texts, [])
        turn = yield p.end("Ending in the continuation.")
        if spent:
            p.eq("continuation.no-reminder", turn.texts if turn is not None else [], [])
            if turn is not None and turn.texts:
                yield p.end("Ending after an unexpected reminder.")
        else:
            p.eq("continuation.reminder", turn.texts if turn is not None else None, [REMINDER])
            yield p.end("Ending after the reminder.")
    return body


def check_run_ended_body(t, sub, fx, name, number, *, ending, cause, recorded_by, requests, attempts, notices):
    """The whole run_ended body of 4.4 apart from prev and the prose message."""
    b = rs.run_ended_of(t, sub, number)
    if not t.check(name + ".run_ended.present", isinstance(b, dict), "no run_ended for run %d" % number):
        return None
    t.eq(name + ".run_ended.keys", list(b), RUN_ENDED_KEYS)
    t.eq(name + ".run_ended.body",
         {k: b.get(k) for k in RUN_ENDED_KEYS if k not in ("prev", "message")},
         {"run": number, "ending": ending, "cause": cause, "recorded_by": recorded_by, "provider": None,
          "requests": requests, "attempts": attempts, "usage": fx.totals(fx.exchanges_of(name)),
          "notices": notices, "seal": None})
    t.check(name + ".run_ended.message", isinstance(b.get("message"), str) and bool(b["message"].strip()),
            b.get("message"))
    return b


def check_reminder_record(t, sub, name, run, request):
    """4.4 notice body for a reminder claimed for `request` of placement `run`; returns its log name."""
    recs = notice_records(t, sub)
    t.eq(name + ".notice-records", [(b or {}).get("type") for _, b in recs], ["reminder"])
    if not recs:
        return None
    log_name, b = recs[0]
    t.eq(name + ".notice.keys", list(b or {}), NOTICE_KEYS)
    t.eq(name + ".notice.body", {k: (b or {}).get(k) for k in NOTICE_KEYS[1:]},
         {"type": "reminder", "run": run, "request": request, "text": REMINDER, "remaining": None})
    return "log/" + log_name


def check_interrupted_status(t, sub, fx, name, cause):
    """5.6: an interrupted latest placement whose allowances permit another request."""
    st = t.status(sub, name=name)
    d = st.data
    t.eq(name + ".condition", d.get("condition"), "interrupted")
    last = (d.get("runs") or {}).get("last") or {}
    t.eq(name + ".last", [last.get(k) for k in ("number", "ending", "cause", "recorded_by")],
         [1, "interrupted", cause, "run"])
    t.eq(name + ".authoring", (d.get("headline") or {}).get("authoring"), {"state": "open", "ended_by": None})
    t.eq(name + ".next", sorted({a[1] for a in st.next_argvs()}), ["close", "run"])
    t.eq(name + ".allowances", d.get("allowances"), fp.allowances(fx.totals(), rs.limits_of(sub)))
    return st


def continue_and_check(t, sub, fx, p, pre, spent, carried=False):
    """Placement 2: the continuation ends ordinarily, with or without the reminder. carried:
    placement 1 transmitted a request carrying the reminder (the fake saw it once there)."""
    name = pre + ".run-2"
    rep = rs.run(t, sub, fx, name=name)
    rs.check_run_reply(t, rep, sub, name, ending="ended_unsubmitted", run_number=2, fx=fx, limits=rs.limits_of(sub))
    t.eq(name + ".notices", rep.data.get("notices"), [] if spent else [{"type": "reminder", "sent": "sent"}])
    second = fx.exchanges_of(name)
    if second:
        rs.check_first_message(t, second[0], sub.body, True, name)
    t.eq(pre + ".reminder-texts", p.texts.count(REMINDER), int(carried) + (0 if spent else 1))
    rs.check_procedure(t, p, pre, fx)
    rs.check_requests(t, fx, sub, pre)
    return rep


@case("c7.notice-durability", ["C7", "C6", "C13", "C17"],
      "a reminder claim linked without a confirmed directory sync ends the placement, is listed not_sent and stays spent",
      mode="test", needs=("loopback",),
      faults=("log.dirsync:notice=eio", "log.publish:notice=eio"))
def c_notice_durability(t):
    """log.dirsync:notice=eio links the reminder's notice record, then fails the directory
    sync of its publication (4.3, Appendix C.1). That is an archive write failure (6.5): the
    run records interrupted with cause archive_write_failed, sends no request carrying the
    notice, replies completed and exits 5. The linked record is a notice published during
    the placement, so run_ended lists it, not_sent because no request capture carries it
    (4.4, 6.4). The claim stays spent (6.4, 6.7): the continuation's re-entry shows the
    reminder used and its first ordinary stop ends the audit's authoring without a reminder.
    Differing: log.publish:notice=eio fails before the link, so no notice record exists,
    run_ended lists none, status names the interrupted publication (4.3, 5.6), and the
    continuation receives the reminder once. Invariance: the same fault with the run invoked
    from another directory and HOME gives the same run_ended body and run reply."""
    seen = {}
    for label, fault, linked, elsewhere in (("dirsync-eio", "log.dirsync:notice=eio", True, False),
                                            ("publish-eio", "log.publish:notice=eio", False, False),
                                            ("dirsync-eio-elsewhere", "log.dirsync:notice=eio", True, True)):
        pre = "notice.durability." + label
        sub = run_submission(t, body=b"Does the supplied code mark a reminder sent before delivering it?\n")
        p = proc(sub, reminder_body(spent=linked, transmitted=False))
        fx = rs.provider(t, p, label=label)
        name = pre + ".run-1"
        kw = {"cwd": t.fresh_dir(label + " cwd"), "env": {"HOME": t.fresh_dir(label + " home")}} if elsewhere else {}
        rep = rs.run(t, sub, fx, name=name, fault=fault, **kw)
        rs.check_run_reply(t, rep, sub, name, ending="interrupted", cause="archive_write_failed", run_number=1,
                           fx=fx, limits=rs.limits_of(sub))
        t.eq(name + ".exit", rep.rc, 5)
        t.eq(name + ".effects", {k: v for k, v in rep.effects.items() if k != "diagnostic"},
             {"run": "ended", "answer": "changed", "seal": "none", "delivery": "none"})
        t.eq(name + ".notices", rep.data.get("notices"), [{"type": "reminder", "sent": "not_sent"}] if linked else [])
        t.eq(name + ".requests-received", len(fx.exchanges_of(name)), 2)
        t.check(name + ".no-request-carried-it", not any(REMINDER.encode("utf-8") in (e.body or b"")
                                                         for e in fx.exchanges_of(name)), "a request carried the reminder")
        if linked:
            record = check_reminder_record(t, sub, name, 1, 3)
            notices = [{"type": "reminder", "record": record, "sent": "not_sent"}]
        else:
            t.eq(name + ".no-notice-record", notice_records(t, sub), [])
            notices = []
        body = check_run_ended_body(t, sub, fx, name, 1, ending="interrupted", cause="archive_write_failed",
                                    recorded_by="run", requests=2, attempts=2, notices=notices)
        st = check_interrupted_status(t, sub, fx, pre + ".status", "archive_write_failed")
        if not linked:
            t.check(pre + ".status.interrupted-publication", mentions(st.data.get("diagnostics"), "stage"),
                    st.data.get("diagnostics"))
        continue_and_check(t, sub, fx, p, pre, spent=linked)
        seen[label] = (body, {k: rep.data.get(k) for k in ("run", "continuing", "ending", "cause", "provider", "usage",
                                                           "allowances", "answer", "seal", "delivery", "notices")})
    if "dirsync-eio" in seen and "dirsync-eio-elsewhere" in seen:
        a, b = seen["dirsync-eio"], seen["dirsync-eio-elsewhere"]
        strip = lambda body: {k: v for k, v in (body or {}).items() if k not in ("prev", "message")}
        t.eq("notice.durability.invariance.run_ended", strip(b[0]), strip(a[0]))
        t.eq("notice.durability.invariance.reply", b[1], a[1])


@case("c7.notice-transmission", ["C7", "C6", "C13"],
      "a claimed reminder is sent, not_sent or unknown by its request evidence, and is never re-sent after a kill",
      mode="test", needs=("loopback",),
      faults=("log.dirsync:notice=kill", "provider.sent:3=kill"))
def c_notice_transmission(t):
    """6.4: run_ended reports a notice as sent when an attempt record of its planned request
    has request_written other than none, not_sent when no complete request capture exists,
    and unknown otherwise. Unfaulted, the reminder rides on request 3 and the placement ends
    ended_unsubmitted with it sent. log.dirsync:notice=kill links the notice and dies before
    request 3 is captured: the next run reconciles run_ended (process_gone, recorded by run)
    with the notice not_sent and no estimate. provider.sent:3=kill dies after request 3 is
    written: its capture is complete but no attempt record exists, so the notice is unknown
    and reconciliation charges one estimate (6.4). In both killed placements the claim
    stays spent: re-entry shows it used and the continuation's first ordinary stop ends
    authoring without a reminder (6.4, 6.7; CONTRACTS bounded prompting)."""
    for label, fault in (("unfaulted", None), ("kill-after-link", "log.dirsync:notice=kill"),
                         ("kill-after-send", "provider.sent:3=kill")):
        pre = "notice.transmission." + label
        sub = run_submission(t, body=b"Does the supplied code mark a reminder sent before delivering it?\n")
        p = proc(sub, reminder_body(spent=True, transmitted=label != "kill-after-link"))
        fx = rs.provider(t, p, label=label)
        name = pre + ".run-1"
        if fault is None:
            rep = rs.run(t, sub, fx, name=name)
            rs.check_run_reply(t, rep, sub, name, ending="ended_unsubmitted", run_number=1, fx=fx,
                               limits=rs.limits_of(sub))
            t.eq(name + ".notices", rep.data.get("notices"), [{"type": "reminder", "sent": "sent"}])
            record = check_reminder_record(t, sub, name, 1, 3)
            check_run_ended_body(t, sub, fx, name, 1, ending="ended_unsubmitted", cause=None, recorded_by="run",
                                 requests=3, attempts=3,
                                 notices=[{"type": "reminder", "record": record, "sent": "sent"}])
            rs.check_procedure(t, p, pre, fx)
            continue
        rs.run(t, sub, fx, name=name, fault=fault, killed=True)
        first = fx.exchanges_of(name)
        sent = label == "kill-after-send"
        t.eq(name + ".requests-received", len(first), 3 if sent else 2)
        if sent and len(first) == 3:
            # 6.4: a complete request capture whose attempt has no record is charged one
            # estimate once the process is gone.
            fx.provider.charge_overrides[first[2].n] = "estimated"
            t.check(name + ".request-3-carried-reminder", REMINDER.encode("utf-8") in (first[2].body or b""),
                    "request 3 did not carry the reminder")
        record = check_reminder_record(t, sub, name, 1, 3)
        continue_and_check(t, sub, fx, p, pre, spent=True, carried=sent)
        check_run_ended_body(t, sub, fx, name, 1, ending="interrupted", cause="process_gone", recorded_by="run",
                             requests=3 if sent else 2, attempts=2,
                             notices=[{"type": "reminder", "record": record, "sent": "unknown" if sent else "not_sent"}])


@case("c7.near-limit-continuation", ["C7", "C13"],
      "the near-limit notice sent before an interruption is not sent again in the continuation",
      needs=("loopback",),
      controls=[Control("reset_notice_allowance", [r"^near\.continuation\.(one-near-limit|placement-2\.no-near-limit"
                                                   r"|placement-2\.notices-used|near-limit-records)$"])])
def c_near_limit_continuation(t):
    """Output limit 10,000 and 1,200 output tokens per response: after the seventh response
    1,600 remain, at most 20 % (6.4), so the near-limit notice is published and rides on
    request 8 with the remaining amounts (QUESTION-FORMS). Request 8 is answered 529 four
    times: the placement ends interrupted provider_unavailable with the notice sent. The
    continuation (6.7) still has 1,600 output tokens, at least 1,024, so it may request;
    its re-entry shows the near-limit notice used and no placement-2 request carries
    another one, although its allowance stays below 20 % (6.4: audit-wide, not resent).
    Its first ordinary stop receives the still-unused reminder; the second ends it."""
    sub = run_submission(t, q={"output_tokens": "10000"})
    limits = rs.limits_of(sub)
    state = {}

    def body(p):
        p.usage = lambda: fp.Usage(1000, 1200)
        turn = None
        for _ in range(7):
            turn = yield p.calls_step(("list", {}))
        state["notice"] = list(turn.texts) if turn else None
        turn = yield fp.HttpError(529, retry_after="0")
        p.check("placement-2.new-conversation", turn is not None and turn.new_conversation, "no continuation")
        p.usage = lambda: fp.Usage(1000, 50)
        turn = yield p.calls_step(("what_am_i_working_with", {}))
        r = turn.reply(0)
        p.eq("placement-2.notices-used", (r.data if r else {}).get("notices_used"),
             {"reminder": False, "near_limit": True})
        p.eq("placement-2.no-near-limit", [x for x in turn.texts if x.startswith("Allowance notice:")], [])
        turn = yield p.end("Stopping without submitting.")
        p.eq("placement-2.reminder", turn.texts, [REMINDER])
        yield p.end("Stopping again.")
    p = proc(sub, body)
    fx = rs.provider(t, p)
    r1 = rs.run(t, sub, fx, name="near.continuation.run-1")
    rs.check_run_reply(t, r1, sub, "near.continuation.run-1", ending="interrupted", cause="provider_unavailable",
                       run_number=1, fx=fx, limits=limits)
    first = fx.exchanges_of("near.continuation.run-1")
    used = fx.totals(first[:7]) if len(first) >= 7 else None
    if used is not None:
        rem = {k: max(0, limits[k] - sum(v.values())) for k, v in used.items()}
        t.eq("near.continuation.notice-text", state.get("notice"), [NEAR_LIMIT.format(**rem)])
    t.eq("near.continuation.run-1.notices", r1.data.get("notices"), [{"type": "near_limit", "sent": "sent"}])
    r2 = rs.run(t, sub, fx, name="near.continuation.run-2")
    rs.check_run_reply(t, r2, sub, "near.continuation.run-2", ending="ended_unsubmitted", run_number=2, fx=fx,
                       limits=limits)
    second = fx.exchanges_of("near.continuation.run-2")
    t.check("near.continuation.placement-2-requested", bool(second) and second[0].max_tokens() == 1600,
            [e.max_tokens() for e in second])
    t.eq("near.continuation.run-2.notices", r2.data.get("notices"), [{"type": "reminder", "sent": "sent"}])
    t.eq("near.continuation.one-near-limit", [x for x in p.texts if x.startswith("Allowance notice:")],
         state.get("notice") or ["missing"])
    t.eq("near.continuation.near-limit-records",
         [((b or {}).get("type"), (b or {}).get("run")) for _, b in notice_records(t, sub)],
         [("near_limit", 1), ("reminder", 2)])
    rs.check_procedure(t, p, "near.continuation", fx)
    rs.check_requests(t, fx, sub, "near.continuation")
