# -*- coding: utf-8 -*-
"""Provider compaction, independently specified by INTERFACE 4.5/6 and ACCEPTANCE C4.

These cases exercise the adapter's actual summary transition. The reacting auditor's
separate memory-loss/reentry specimens in cases_run remain separate evidence.
"""
from __future__ import annotations

import signal

import fake_provider as fp
import rawjson
import run_support as rs
from driver_core import (COMPACTION, NEAR_LIMIT, POST_COMPACTION, REMINDER, Control, case,
                         mentions, selftest)
from cases_run import answer_of, prepare_and_submit, proc, run_submission


def iteration(kind, inputs, outputs, creation=None, read=None, **extra):
    return dict(type=kind, input_tokens=inputs, output_tokens=outputs,
                cache_creation_input_tokens=creation, cache_read_input_tokens=read, **extra)


def trigger_usage(below=False, iterations=fp.ABSENT):
    # All four top-level counts are needed to reach exactly 150,000.
    return fp.Usage(100000, 1000, 20000, 29000 - int(below), iterations=iterations)


def summary_usage(output=314):
    # Deliberately unlike the top-level counts: adding both or ignoring iterations is visible.
    return fp.Usage(1, 2, iterations=[iteration("message", 11, 7, read=3),
                                    iteration("compaction", 201, output - 7, 5, 13, future="kept")])


def summary(index=1, usage=None):
    # Whitespace, escapes, member order and unknown fields must survive the signed array.
    block = fp.Block(b'{"signature":"c2ln/%d==", "future":{"opaque":true},'
                     b'"content":"Earlier work \\u00e9 %d.","type":"compaction"}' % (index, index), "compaction")
    step = fp.Message([block], stop_reason="compaction", usage=usage or summary_usage())
    step.content_raw = b"[ " + block.raw + b" ]"
    return step


class SummarizingProcedure:
    """Absorb tool results before summarizing, then resume the scripted auditor.

    Prepare its next ordinary response from the summary request's tool results, but
    deliver it only on the following ordinary request. Retries get the same Step.
    """
    def __init__(self, procedure):
        self.procedure = procedure
        self.pending = None
        self.summaries = []
        self.answers = {}

    def __call__(self, ex):
        key = ex.body_sha256()
        if key in self.answers:
            return self.answers[key]
        if rs.is_compaction_request(ex):
            self.pending = self.procedure(ex)
            step = summary(len(self.summaries) + 1)
            self.summaries.append(step)
        elif self.pending is not None:
            step, self.pending = self.pending, None
        else:
            step = self.procedure(ex)
        self.answers[key] = step
        return step

    def witness(self):
        return {"procedure": self.procedure.witness(), "summaries": [s.content_raw.decode() for s in self.summaries]}


def check_common(t, sub, fx, pre, rep, ending, cause=None, run_number=1):
    rs.check_run_reply(t, rep, sub, pre, ending=ending, cause=cause, run_number=run_number,
                       fx=fx, limits=rs.limits_of(sub))
    rs.check_requests(t, fx, sub, pre, exchanges=fx.exchanges_of(pre))
    rs.check_history(t, fx, pre, exchanges=fx.exchanges_of(pre))
    rs.check_captures(t, sub, fx, pre, run_number=run_number)
    rs.check_run_records(t, sub, pre)
    b = rs.run_ended_of(t, sub, run_number) or {}
    t.eq(pre + ".run-ended-usage", b.get("usage"), fx.totals(fx.exchanges_of(pre)))
    rs.check_fake(t, fx, pre)


@case("c4.provider-compaction", ["C4", "C1", "C6", "C18"],
      "two signed provider summaries replace active context, retain reconstructable captures and preserve the sealed answer",
      needs=("loopback",), controls=[
          Control("omit_compaction", [r"^compact\.repeat\.summary-count$"]),
          Control("alter_compaction_summary", [r"^compact\.repeat\.history\..*\.summary-exact$"]),
          Control("retain_precompaction_context", [r"^compact\.repeat\.history\..*\.reset-two$"]),
          Control("ignore_compaction_usage", [r"^compact\.repeat\.(usage|run-ended-usage)$",
                                              r"^compact\.repeat\.capture\..*\.(charged|usage)$"])])
def c_provider_compaction(t):
    answers = {}
    for label, below in (("repeat", False), ("below", True)):
        pre = "compact." + label
        sub = run_submission(t, body=b"Audit the captured source.\n", effort="high")
        # Trigger uses top-level totals; charges use iterations. The below-trigger fixture
        # has larger iteration sums, distinguishing those two sources of counts.
        its = [iteration("message", 160000 if below else 130, 17, 5, 6), iteration("message", 9, 4)]

        def body(p):
            turn = yield p.calls_step(("record_account", {"text": "The supplied source permits duplicate delivery."}),
                                      ("record_observation", {"text": "Delivery precedes marking the reminder sent."}),
                                      usage=trigger_usage(below, its))
            p.eq("initial-records", [r.outcome for r in turn.replies], ["completed", "completed"])
            _, entries, _ = yield from p.wwaw_all()
            p.eq("recovered-entries", len(entries), 2)
            yield p.calls_step(("read", {"source": "question"}),
                               ("search", {"text": "deliver", "sources": ["materials/a.py"]}),
                               usage=trigger_usage(below, its))
            yield p.calls_step(("record_limit", {"text": "The supplied material does not establish runtime behavior."}))
            yield from prepare_and_submit(p)
        p = proc(sub, body)
        wrapped = SummarizingProcedure(p)
        fx = rs.provider(t, wrapped, label=label, accepts=fp.MESSAGES_API)
        rep = rs.run(t, sub, fx, name=pre)
        check_common(t, sub, fx, pre, rep, "sealed")
        rs.check_procedure(t, p, pre, fx)
        t.eq(pre + ".summary-count", len(wrapped.summaries), 0 if below else 2)
        t.eq(pre + ".first-ordinary", rs.is_compaction_request(fx.exchanges[0]) if fx.exchanges else None, False)
        t.eq(pre + ".one-run", len(t.log_bodies(sub, "run_started")), 1)
        t.eq(pre + ".one-seal", len(t.log_bodies(sub, "seal")), 1)
        t.eq(pre + ".entries", [b.get("action") for b in rs.entry_bodies(t, sub)], ["add"] * 3)
        t.eq(pre + ".no-notice-charge", t.log_bodies(sub, "notice"), [])
        captured = [c[2] for c in rs.calls_and_results(sub)]
        t.eq(pre + ".calls-retained", captured, [c["raw_block"] for c in p.calls.values()])
        answers[label] = answer_of(t, rep, pre)
    t.check("compact.same-answer", answers.get("repeat") is not None and answers.get("repeat") == answers.get("below"),
            "compaction changed the sealed structured answer")


def trigger_step():
    return fp.Message([fp.tool_use("before_summary", "list", {})], stop_reason="tool_use", usage=trigger_usage())


def raw_message(content, usage, stop="compaction", charge="estimated"):
    return fp.Message(body=b'{"content":' + content + b',"stop_reason":' + fp.jstr(stop)
                      + b',"usage":' + usage + b'}', charge=charge)


def malformed_summaries():
    good = summary()
    tool = fp.tool_use("must_not_execute", "record_observation", {"text": "summary tool must not run"})
    for label, blocks in (
        ("missing", []), ("unsigned", [fp.compaction("text")]),
        ("empty-content", [fp.compaction("", "sig")]), ("empty-signature", [fp.compaction("text", "")]),
        ("wrong-signature", [fp.compaction("text", 3)]),
        ("repeated-type", [fp.Block(b'{"type":"compaction","type":"compaction","content":"x","signature":"s"}', "compaction")]),
        ("two-summaries", [fp.compaction("one", "a"), fp.compaction("two", "b")]),
        ("tool", [tool]), ("summary-and-tool", good.content + [tool]),
    ):
        yield label, fp.Message(blocks, stop_reason="compaction", usage=summary_usage()), "protocol_anomaly", "response"
    for stop, cause in (("end_turn", "protocol_anomaly"), ("max_tokens", "max_tokens"),
                        ("refusal", "provider_refusal"), ("model_context_window_exceeded", "context_exhausted")):
        yield stop, fp.Message([tool], stop_reason=stop, usage=summary_usage()), cause, "response"
    content = good.content_raw
    valid = b'{"type":"compaction","input_tokens":1,"output_tokens":2}'
    invalid = [
        ("iterations-absent", b'{"input_tokens":1,"output_tokens":2}'),
        ("iterations-null", b'{"input_tokens":1,"output_tokens":2,"iterations":null}'),
        ("iterations-repeated", b'{"input_tokens":1,"output_tokens":2,"iterations":[' + valid + b'],"iterations":[' + valid + b']}'),
    ]
    for label, value in (
        ("empty", b'[]'), ("object", b'{}'), ("non-object", b'[1]'),
        ("unknown-type", b'[{"type":"future","input_tokens":1,"output_tokens":2}]'),
        ("missing-compaction", b'[{"type":"message","input_tokens":1,"output_tokens":2}]'),
        ("missing-count", b'[{"type":"compaction","input_tokens":1}]'),
        ("negative", b'[{"type":"compaction","input_tokens":-1,"output_tokens":2}]'),
        ("bool", b'[{"type":"compaction","input_tokens":true,"output_tokens":2}]'),
        ("fraction", b'[{"type":"compaction","input_tokens":1.0,"output_tokens":2}]'),
        ("repeated-count", b'[{"type":"compaction","input_tokens":1,"input_tokens":2,"output_tokens":2}]'),
        ("repeated-type", b'[{"type":"compaction","type":"message","input_tokens":1,"output_tokens":2}]'),
        ("over-bound", b'[{"type":"compaction","input_tokens":281474976710657,"output_tokens":2}]'),
        ("sum-over-bound", b'[{"type":"compaction","input_tokens":281474976710656,"output_tokens":2},' + valid + b']'),
    ):
        invalid.append(("iterations-" + label, b'{"input_tokens":1,"output_tokens":2,"iterations":' + value + b'}'))
    for label, usage in invalid:
        yield label, raw_message(content, usage), "protocol_anomaly", "response_undecodable"


@case("c4.compaction-failures", ["C4", "C13", "C14"],
      "invalid summaries and iteration usage interrupt visibly, preserve captures and never execute summary tools",
      needs=("loopback",))
def c_compaction_failures(t):
    for label, step, cause, outcome in malformed_summaries():
        pre = "compact.bad." + label
        sub = run_submission(t, body=b"Check the source.\n")
        fx = rs.provider(t, fp.Script([trigger_step(), step]), label=label)
        rep = rs.run(t, sub, fx, name=pre)
        check_common(t, sub, fx, pre, rep, "interrupted", cause)
        t.eq(pre + ".exit", rep.rc, 5)
        t.eq(pre + ".requests", [rs.is_compaction_request(e) for e in fx.exchanges], [False, True])
        t.eq(pre + ".no-summary-tools", [c[2] for c in rs.calls_and_results(sub)], [trigger_step().content[0].raw])
        t.eq(pre + ".no-entries", rs.entry_bodies(t, sub), [])
        t.eq(pre + ".no-seal", t.log_bodies(sub, "seal"), [])
        t.eq(pre + ".no-reminder", [b.get("type") for b in t.log_bodies(sub, "notice")], [])
        rd = rs.run_dirs(sub).get(1)
        rec = ((rd.attempts.get((2, 1)) or {}).get("body") or {}) if rd else {}
        t.eq(pre + ".outcome", rec.get("outcome"), outcome)
        if cause == "protocol_anomaly":
            t.check(pre + ".failure-named", mentions(rep.obj, "compaction"), rep.obj)


@case("c4.compaction-budgets", ["C4", "C13"],
      "turn, input and output limits stop before a summary or after its billed iterations without another request",
      needs=("loopback",))
def c_compaction_budgets(t):
    variants = (
        ("turn-before", {"turns": 1}, 1, summary_usage()),
        ("turn-after", {"turns": 2}, 2, summary_usage()),
        ("input-before", {"input_tokens": 149000}, 1, summary_usage()),
        ("input-after", {"input_tokens": 149200}, 2, summary_usage()),
        ("output-before", {"output_tokens": 2000}, 1, summary_usage()),
        ("output-after", {"output_tokens": 2200}, 2, summary_usage(output=1200)),
    )
    for label, limits, n, usage in variants:
        pre = "compact.budget." + label
        sub = run_submission(t, body=b"Check the source.\n", q=limits)
        fx = rs.provider(t, fp.Script([trigger_step(), summary(usage=usage)]), label=label)
        rep = rs.run(t, sub, fx, name=pre)
        check_common(t, sub, fx, pre, rep, "limit_reached")
        t.eq(pre + ".requests", [rs.is_compaction_request(e) for e in fx.exchanges], [False, True][:n])
        t.eq(pre + ".no-seal", t.log_bodies(sub, "seal"), [])
        if label == "output-after":
            t.eq(pre + ".summary-cap", fx.exchanges[-1].max_tokens() if fx.exchanges else None, 1200)
        rs.run(t, sub, fx, name=pre + ".cannot-resume", expect="refused", reason="authoring_ended")


@case("c4.compaction-notices", ["C4", "C7", "C13"],
      "summary reset carries the pending near-limit notice and leaves the ordinary reminder available",
      needs=("loopback",))
def c_compaction_notices(t):
    pre = "compact.notices"
    sub = run_submission(t, body=b"Check the source.\n", q={"turns": 5})
    # At four charged responses one turn remains. The fourth is a summary, so the pending
    # notice belongs beside the post-compaction notice on request five.
    fx = rs.provider(t, fp.Script([
        fp.Message([fp.tool_use("early", "list", {})], stop_reason="tool_use"),
        fp.Message([fp.text("First stop.")], stop_reason="end_turn"),
        trigger_step(), summary(), fp.Message([fp.text("Second stop.")], stop_reason="end_turn"),
    ]))
    rep = rs.run(t, sub, fx, name=pre)
    check_common(t, sub, fx, pre, rep, "limit_reached")
    t.eq(pre + ".sequence", [rs.is_compaction_request(e) for e in fx.exchanges], [False, False, False, True, False])
    notices = [b.get("type") for b in t.log_bodies(sub, "notice")]
    t.eq(pre + ".notices-once", notices, ["reminder", "near_limit"])
    if len(fx.exchanges) == 5:
        used = fx.totals(upto=4)
        remaining = {k: max(0, rs.limits_of(sub)[k] - sum(v.values())) for k, v in used.items()}
        user = fx.exchanges[4].messages()[1].value()
        t.eq(pre + ".post-summary-texts", user.get("content"),
             [{"type": "text", "text": POST_COMPACTION}, {"type": "text", "text": NEAR_LIMIT.format(**remaining)}])
    sub2 = run_submission(t, body=b"Check the source.\n")
    fx2 = rs.provider(t, fp.Script([trigger_step(), summary(), fp.Message(), fp.Message()]), label="reminder")
    rep2 = rs.run(t, sub2, fx2, name=pre + ".reminder")
    check_common(t, sub2, fx2, pre + ".reminder", rep2, "ended_unsubmitted")
    t.eq(pre + ".reminder-request-count", len(fx2.exchanges), 4)
    if len(fx2.exchanges) == 4:
        t.eq(pre + ".reminder-after-summary", fx2.exchanges[-1].messages()[-1].value().get("content"),
             [{"type": "text", "text": REMINDER}])


@case("c4.compaction-rejection", ["C4", "C9", "C13"],
      "provider refusal of compaction parameters or beta stays visible without fallback",
      needs=("loopback",))
def c_compaction_rejection(t):
    for label in ("parameter", "beta"):
        pre = "compact.reject." + label
        sub = run_submission(t, body=b"Check the source.\n", effort="high")
        if label == "parameter":
            fx = rs.provider(t, fp.Script([trigger_step()]), label=label,
                             accepts=fp.MESSAGES_API.without("compaction"))
            n = 2
        else:
            def refuses_beta(ex):
                beta = dict(ex.headers).get("anthropic-beta")
                return fp.HttpError(400, message="Unsupported anthropic-beta: %s" % beta)
            fx = rs.provider(t, refuses_beta, label=label)
            n = 1
        rep = rs.run(t, sub, fx, name=pre)
        check_common(t, sub, fx, pre, rep, "interrupted", "provider_rejected")
        t.eq(pre + ".requests", len(fx.exchanges), n)
        want = rs.provider_expected(fx.exchanges[-1] if fx.exchanges else None, n, 1)
        t.eq(pre + ".provider", rep.data.get("provider"), want)
        t.eq(pre + ".run-ended-provider", (rs.run_ended_of(t, sub, 1) or {}).get("provider"), want)
        t.eq(pre + ".no-reminder", t.log_bodies(sub, "notice"), [])
        st = t.status(sub, name=pre + ".status")
        t.check(pre + ".status-interrupted", mentions(st.data, "interrupted"), st.data)


@case("c4.compaction-usage-fallback", ["C4", "C13"],
      "ordinary absent/null iterations use top-level counts while malformed iteration usage interrupts",
      needs=("loopback",))
def c_compaction_usage_fallback(t):
    for label, its in (("absent", fp.ABSENT), ("null", None),
                       ("summed", [iteration("message", 12, 7), iteration("compaction", 31, 8, 3, 4)])):
        pre = "compact.usage." + label
        sub = run_submission(t, body=b"Check the source.\n")
        fx = rs.provider(t, fp.Script([fp.Message(usage=fp.Usage(21, 5, 2, 3, iterations=its)),
                                      fp.Message(usage=fp.Usage(6, 7, None, None, iterations=its))]), label=label)
        rep = rs.run(t, sub, fx, name=pre)
        check_common(t, sub, fx, pre, rep, "ended_unsubmitted")
        t.eq(pre + ".ordinary-only", [rs.is_compaction_request(e) for e in fx.exchanges], [False, False])
    # Ordinary messages must not hide malformed iteration data behind small top-level totals.
    for label, step, _, outcome in malformed_summaries():
        if outcome != "response_undecodable" or label in (
                "iterations-absent", "iterations-null", "iterations-missing-compaction"):
            continue
        pre = "compact.ordinary-bad." + label
        sub = run_submission(t, body=b"Check the source.\n")
        fx = rs.provider(t, fp.Script([step]), label="ordinary-" + label)
        rep = rs.run(t, sub, fx, name=pre)
        check_common(t, sub, fx, pre, rep, "interrupted", "protocol_anomaly")
        t.eq(pre + ".no-fallback", len(fx.exchanges), 1)
        rd = rs.run_dirs(sub).get(1)
        rec = ((rd.attempts.get((1, 1)) or {}).get("body") or {}) if rd else {}
        t.eq(pre + ".outcome", rec.get("outcome"), "response_undecodable")


@case("c4.compaction-retries", ["C4", "C13"],
      "summary retries resend identical bytes and charge each response once before the ordinary reset",
      mode="test", needs=("loopback",))
def c_compaction_retries(t):
    pre = "compact.retry"
    sub = run_submission(t, body=b"Check the source.\n")
    fx = rs.provider(t, fp.Script([trigger_step(), fp.HttpError(529, retry_after="0"),
                                  summary(), fp.Message(), fp.Message()]))
    rep = rs.run(t, sub, fx, name=pre)
    check_common(t, sub, fx, pre, rep, "ended_unsubmitted")
    t.eq(pre + ".sequence", [rs.is_compaction_request(e) for e in fx.exchanges], [False, True, True, False, False])
    t.check(pre + ".same-summary-request", len(fx.exchanges) == 5 and fx.exchanges[1].body == fx.exchanges[2].body,
            "summary retry changed its request")
    t.eq(pre + ".response-turns", rep.data.get("usage", {}).get("turns"), {"reported": 4, "estimated": 0})


@case("c4.compaction-stopping", ["C4", "C13", "C8"],
      "signals and close abort a summary request under the same stopping path and charge an estimate",
      mode="test", needs=("loopback", "lock"),
      linux_reason="close reaches a held summary through the Linux OFD lock")
def c_compaction_stopping(t):
    for label, sig in (("sigterm", signal.SIGTERM), ("sigint", signal.SIGINT),
                       ("sighup", signal.SIGHUP), ("close", None)):
        pre = "compact.stop." + label
        sub = run_submission(t, body=b"Check the source.\n")
        fx = rs.provider(t, fp.Script([trigger_step(), fp.Stall(60)]), label=label)
        h = rs.start_run(t, sub, fx, name=pre)
        arrived = rs.wait_for(lambda: len(fx.exchanges) >= 2 and fx.exchanges[1].step is not None, 30)
        t.check(pre + ".summary-in-flight", arrived and rs.is_compaction_request(fx.exchanges[1]), "summary not received")
        if sig is not None:
            t.signal(h, sig)
            rep = rs.finish_run(t, h)
            ending, cause, outcome = "interrupted", "signal", "aborted_by_signal"
        else:
            close = t.start(["close", sub.ref], name=pre + ".close", timeout=120)
            rep = rs.finish_run(t, h)
            t.finish(close, expect="completed")
            ending, cause, outcome = "stopped_by_close", None, "aborted_by_close"
        check_common(t, sub, fx, pre, rep, ending, cause)
        t.eq(pre + ".requests", len(fx.exchanges), 2)
        rd = rs.run_dirs(sub).get(1)
        rec = ((rd.attempts.get((2, 1)) or {}).get("body") or {}) if rd else {}
        t.eq(pre + ".aborted", (rec.get("outcome"), (rec.get("charged") or {}).get("basis")), (outcome, "estimated"))
        t.eq(pre + ".no-reminder", t.log_bodies(sub, "notice"), [])


@selftest
def compaction_witness_selftests():
    """Run the new witnesses without sockets or a service; corrupt each measured property."""
    from types import SimpleNamespace
    from driver_core import sha256_hex
    out = []
    counts = summary_usage().counts()
    out.append(("compaction.usage.iteration-sums", counts == {
        "input_tokens": 212, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 16, "output_tokens": 314}))
    for label, its in (("absent", fp.ABSENT), ("null", None)):
        out.append(("compaction.usage." + label, fp.Usage(3, 7, 11, 13, iterations=its).counts() == {
            "input_tokens": 3, "cache_creation_input_tokens": 11, "cache_read_input_tokens": 13, "output_tokens": 7}))
    su = summary()
    out.append(("compaction.signed-block", rawjson.parse(su.content_raw).items[0].get("signature").value() == "c2ln/1=="))
    out.append(("compaction.parameter.accepted", fp.MESSAGES_API.judge(
        b'{"model":"m","max_tokens":16000,"compaction":{"type":"summarize"},"messages":[]}') is None))
    out.append(("compaction.parameter.rejected", fp.MESSAGES_API.without("compaction").judge(
        b'{"model":"m","max_tokens":16000,"compaction":{"type":"summarize"},"messages":[]}') is not None))
    arr = b'{"model":"m","system":[],"tools":[],"request_extra":{"output_config":{"effort":"high"}}}'
    sub = SimpleNamespace(accepted_handle="mp1.x", arrangement={"mp1.x": {"machine": arr}})
    first = b'{"role":"user","content":[{"type":"text","text":"question"}]}'
    assistant = b'{"role":"assistant","content":' + su.content_raw + b'}'
    notice = rawjson.compact({"role": "user", "content": [{"type": "text", "text": POST_COMPACTION}]})
    prefix = b'{"model":"m","max_tokens":16000,"system":[],"tools":[],"output_config":{"effort":"high"}'
    steps = [fp.Message([fp.text("ordinary")]), su, fp.Message([fp.text("after summary")]), fp.Message()]
    message_sets = [[first],
                    [first, b'{"role":"assistant","content":' + steps[0].content_raw + b'}',
                     b'{"role":"user","content":[]}'],
                    [assistant, notice],
                    [assistant, notice, b'{"role":"assistant","content":' + steps[2].content_raw + b'}',
                     b'{"role":"user","content":[]}']]
    exs, captures, active = [], [], []
    for i, (messages, step) in enumerate(zip(message_sets, steps)):
        compacting, reset = i == 1, i == 2
        body = prefix + (b',"compaction":{"type":"summarize"}' if compacting else b'') + b',"messages":[' + b','.join(messages) + b']}'
        ex = fp.Exchange(i + 1, "sim", None, None, 0)
        ex.n, ex.body, ex.step, ex.content_raw = i + 1, body, step, step.content_raw
        exs.append(ex)
        appended = messages if i in (0, 2) else messages[-2:]
        capture = (rawjson.compact({"request": i + 1, "max_tokens": 16000, "body_bytes": len(body),
                                   "body_sha256": sha256_hex(body), "compaction": compacting, "reset": reset})[:-1]
                   + b',"appended":[' + b','.join(appended) + b']}\n')
        captures.append(capture)
        active, rebuilt, _ = rs.reconstruct_request(sub, capture, active)
        out.append(("compaction.capture.reconstruct-%d" % (i + 1), rebuilt == body))
    t = rs._StubT("")
    rs.check_history(t, SimpleNamespace(exchanges=exs), "witness")
    out.append(("compaction.history.pass", all(c[1] for c in t.checks), [c for c in t.checks if not c[1]]))
    for label, suffix, changed in (
        ("alter-summary", ".summary-exact", [assistant.replace(b"Earlier", b"Changed"), notice]),
        ("retain-context", ".reset-two", message_sets[1] + message_sets[2]),
    ):
        old = exs[2].body
        exs[2].body = prefix + b',"messages":[' + b','.join(changed) + b']}'
        exs[2]._node = None
        t = rs._StubT("")
        rs.check_history(t, SimpleNamespace(exchanges=exs), "witness")
        out.append(("compaction.control." + label, any(not ok and n.endswith(suffix) for n, ok, _ in t.checks)))
        exs[2].body, exs[2]._node = old, None
    try:
        rs.reconstruct_request(sub, captures[2].replace(b'"reset":true', b'"reset":false'), message_sets[1])
        caught = False
    except ValueError:
        caught = True
    out.append(("compaction.control.lost-reset-capture", caught))
    return out
