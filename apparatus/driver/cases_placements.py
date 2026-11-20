"""Placement-level rules: the output floor inside a placement and invocation identity
across placements.

INTERFACE 6.3 (the loop; a tool invocation's identity is the placement number plus the
tool_use ID), 6.4 (max_tokens, exhaustion, pending calls of the last response) and 7.4
(label_duplicate). Expected values come from those texts and the fake's own charges.
"""
import fake_provider as fp
import run_support as rs
from cases_run import last_call, prepare_and_submit, proc, run_submission
from driver_core import Control, case, mentions
import answer_witness as aw


@case("c13.output-floor-live", ["C13", "C7"],
      "inside a placement 1,024 remaining output tokens permit one more request with that cap; 1,023 end it",
      needs=("loopback",))
def c_output_floor_live(t):
    """Output limit 4,096. Base: response 1 is a list call reporting 3,072 output tokens, so
    1,024 remain: request 2 is sent with max_tokens 1,024, the lesser of 16,000 and the
    remaining output (6.4). Response 2, another list call, reports 1: 1,023 remain, fewer
    than 1,024, so the limit is exhausted: no request 3, response 2's call is still executed
    and recorded, and the placement ends limit_reached with no reminder (6.3, 6.4); run then
    refuses authoring_ended (limit) (5.7). Differing: response 1 reports 3,073, so only
    request 1 is sent and its call is executed. Invariance: changing only response 1's cache
    counts changes input charges but not the request series or the ending. No near-limit
    notice is due: 1,024 x 100 exceeds 20 % of 4,096 (6.4)."""
    for label, first_output, cache in (("base", 3072, {}), ("below", 3073, {}),
                                       ("cache-invariance", 3072, {"cache_creation": 500, "cache_read": 700})):
        pre = "floor." + label
        sub = run_submission(t, q={"output_tokens": "4096"})
        sent_two = first_output == 3072

        def body(p, first_output=first_output, cache=cache, sent_two=sent_two):
            turn = yield p.calls_step(("list", {}), usage=fp.Usage(1000, first_output, **cache))
            if sent_two:
                p.eq("request-2-texts", turn.texts, [])
                yield p.calls_step(("list", {}), usage=fp.Usage(1000, 1))
        p = proc(sub, body)
        fx = rs.provider(t, p, label=label)
        name = pre + ".run"
        rep = rs.run(t, sub, fx, name=name)
        rs.check_run_reply(t, rep, sub, name, ending="limit_reached", run_number=1, fx=fx, limits=rs.limits_of(sub))
        exs = fx.exchanges_of(name)
        t.eq(pre + ".request-caps", [e.max_tokens() for e in exs], [4096, 1024] if sent_two else [4096])
        calls = rs.calls_and_results(sub)
        t.eq(pre + ".calls-executed", [(c[0], c[1], c[3] is not None) for c in calls],
             [(1, 1, True), (1, 2, True)] if sent_two else [(1, 1, True)])
        t.eq(pre + ".no-notice", t.log_bodies(sub, "notice"), [])
        rs.check_run_ended(t, sub, 1, name, ending="limit_reached", cause=None, requests=len(exs), attempts=len(exs))
        again = rs.run(t, sub, fx, name=pre + ".again", expect="refused", reason="authoring_ended")
        t.eq(pre + ".again.ended_by", again.data.get("ended_by"), "limit")
        t.eq(pre + ".again.no-request", len(fx.exchanges_of(pre + ".again")), 0)
        rs.check_procedure(t, p, pre, fx)
        rs.check_requests(t, fx, sub, pre)


NOTE = "The same words are recorded again."
NOTE_INPUT = {"text": NOTE, "label": "same"}


@case("c3.identity-across-placements", ["C3", "C13", "C6"],
      "a tool_use ID from an earlier placement names a new invocation; inside a placement it replays",
      needs=("loopback",),
      controls=[Control("replay_reexecutes", [r"^identity\.replay\.(records|same-result)$"])])
def c_identity_across_placements(t):
    """Placement 1 executes tool_use toolu_identity_same (record_observation, label same) as
    e1, then the provider is unavailable (6.5). In the continuation the same ID with the
    same raw input is a new invocation, because identity is the placement number plus the
    tool_use ID (6.3): it records e2, with label_duplicate (7.4) and no replay_of. Repeating
    that ID with the same input inside placement 2 is a replay: the recorded content and
    is_error, replay_of naming placement 2's call, and no entry (6.3). A fresh ID with the
    same bytes records e3 (6.3: a new call with matching arguments is a new invocation).
    The sealed selection holds e1, e2 and e3."""
    sub = run_submission(t)
    raw = b'{"text":"The same words are recorded again.","label":"same"}'
    tid = "toolu_identity_same"

    def body(p):
        turn = yield p.step([p.call("record_observation", input=NOTE_INPUT, raw_input=raw, tid=tid)])
        r = turn.reply(0)
        p.eq("placement-1", (r.outcome, r.data.get("id"), r.data.get("revision")) if r else None, ("completed", "e1", 1))
        turn = yield fp.HttpError(529, retry_after="0")
        p.check("continuation", turn is not None and turn.new_conversation, "no continuation")
        turn = yield p.step([p.call("record_observation", input=NOTE_INPUT, raw_input=raw, tid=tid)])
        again = turn.reply(0)
        p.eq("new-invocation", (again.outcome, again.data.get("id"), again.data.get("revision")) if again else None,
             ("completed", "e2", 2))
        p.check("new-invocation.label-duplicate", again is not None and mentions(again.data.get("notices"),
                                                                                  "label_duplicate"),
                again.data if again else None)
        turn = yield p.step([p.call("record_observation", input=NOTE_INPUT, raw_input=raw, tid=tid)])
        replay = turn.reply(0)
        p.eq("replay.same-result", (replay.content_raw, replay.is_error) if replay else None,
             (again.content_raw, again.is_error) if again else "missing")
        turn = yield p.step([p.call("record_observation", input=NOTE_INPUT, raw_input=raw, tid="toolu_identity_fresh")])
        fresh = turn.reply(0)
        p.eq("fresh-id", (fresh.outcome, fresh.data.get("id"), fresh.data.get("revision")) if fresh else None,
             ("completed", "e3", 3))
        yield from prepare_and_submit(p)
    p = proc(sub, body)
    fx = rs.provider(t, p)
    r1 = rs.run(t, sub, fx, name="identity.run-1")
    rs.check_run_reply(t, r1, sub, "identity.run-1", ending="interrupted", cause="provider_unavailable",
                       run_number=1, fx=fx, limits=rs.limits_of(sub))
    r2 = rs.run(t, sub, fx, name="identity.run-2")
    rs.check_run_reply(t, r2, sub, "identity.run-2", ending="sealed", run_number=2, fx=fx, limits=rs.limits_of(sub),
                       seal_actor="auditor", delivery_outcome="verified")
    rs.check_procedure(t, p, "identity", fx)
    rows = [(n, c, (rec or {}).get("body") or {}) for n, c, _, rec in rs.calls_and_results(sub)
            if ((rec or {}).get("body") or {}).get("tool_use_id") == tid]
    t.eq("identity.replay.records", [(n, b.get("replay_of"), b.get("outcome")) for n, c, b in rows],
         [(1, None, "completed"), (2, None, "completed"), (2, rows[1][1] if len(rows) > 1 else "missing", "completed")])
    t.eq("identity.entry-records", [(b.get("action"), b.get("id"), (b.get("invocation") or {}).get("run"))
                                    for b in rs.entry_bodies(t, sub)],
         [("add", "e1", 1), ("add", "e2", 2), ("add", "e3", 2)])
    loc = rs.package_of(r2)
    want = aw.answer_json(3, [aw.Entry(e, 1, "record_observation", "same", NOTE.encode()) for e in ("e1", "e2", "e3")])
    t.eq("identity.selection", rs.read_package_member(loc, "answer.json") if loc else None, want)
    t.check("identity.submitted", last_call(p, "submit") is not None, "no submit")
