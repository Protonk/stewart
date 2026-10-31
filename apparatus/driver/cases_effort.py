# -*- coding: utf-8 -*-
"""The effort setting and provider rejections (ACCEPTANCE C1 "Effort", C9 "Provider
rejections"; INTERFACE 3.2, 4.4, 4.5, 6.2, 6.5, 6.6 and Appendix C.2).

- `c1.effort-levels`: prepare accepts each documented level, records it in the prepared
  settings and pins it as the arrangement's request_extra; an unknown or wrongly cased level
  is refused at prepare.
- `c1.effort`: a commission with an effort sends it on every request as the top-level
  `output_config` member and nowhere else; its system blocks, tools and messages are byte for
  byte those of the same commission without the setting, which sends no `output_config`.
- `c9.provider-rejections`: a provider that has moved away from what the release sends is
  reported as it answered, and the same commission runs normally against one that has not.

The provider's side is a declarative model of what it accepts (fake_provider: `Accepts`,
judged in front of the responder by `Gate`), not a scripted refusal. `fp.MESSAGES_API` is the
pinned API version as this release may use it; a drift case derives the moved provider by
changing one fact of it (`renamed`, `without`, `withdrawn`, `answering`), runs the commission
against it, judges the report with `run_support.check_rejection`, and keeps the unchanged model
as its invariance. A future mismatch between Stewart and a moving provider is written the same
way: name the fact that moved, derive the model, reuse the witness.

Written from docs/INTERFACE.md, CONTRACTS.md and ACCEPTANCE.md without reading service/.
"""
from __future__ import annotations

import os

import fake_provider as fp
import run_support as rs
from driver_core import *  # noqa: F401,F403
from procedure import Procedure

EFFORT_BODY = b"Can a reminder be sent twice?\nLook at what happens across a restart.\n"
A_PY = b"def send(r):\n    deliver(r)\n    mark_sent(r)\n"


def effort_entries():
    """Materials whose bytes, and so whose read replies, never contain the word effort."""
    return [F("a.py", A_PY), F("notes/R1.txt", b"R1. A reminder ID is sent at most once.\n")]


def forbidden_for(sub):
    """Strings no auditor reply may carry (7.1): host and archive paths, the reference, the store,
    the destination and the family's identifier."""
    return [sub.archive, sub.folder, sub.ref, sub.store, sub.dest, sub.family + "/1", "=" + sub.family]


def browse(p):
    """List the materials, read one, then end the turn twice with the reminder between: an
    ordinary ending after several requests whose tool replies hold nothing audit-specific (no
    cursor or entry handle), so two audits of the same commission exchange the same bytes."""
    mats, _ = yield from p.list_all()
    p.check("listed", mats is not None and len(mats) == 2, mats)
    text, _ = yield from p.read_all("materials/a.py")
    p.eq("read", text, A_PY)
    turn = yield p.end("I am stopping here.")
    p.check("reminder", turn.reminder and turn.texts == [REMINDER], turn.texts)
    yield p.end("Stopping again.")


def effort_submission(t, effort):
    """A submission of the shared question and materials; effort is its front matter level or None."""
    return t.submission(effort_entries(), body=EFFORT_BODY, effort=effort)


# ---------------------------------------------------------------------------
# C1: prepare and the documented levels.
# ---------------------------------------------------------------------------

@case("c1.effort-levels", ["C1", "C19", "C20"],
      "prepare pins each documented effort level; unknown and wrongly cased levels are refused")
def c_effort_levels(t):
    """For each level of 3.2 (low, medium, high, xhigh, max) prepare completes; the prepared
    record's settings carry `effort` right after `limits` (4.4), the reply shows no other level,
    and the arrangement pins request_extra {"output_config":{"effort":<level>}} (6.2). With
    inquiry and varies too, settings run family, model, destination, limits, effort, inquiry,
    varies. Differing: without the key the settings have no effort and request_extra is {}.
    Refused setting_invalid with no preparation recorded: High, MAX, xHigh (wrongly cased),
    extreme, none, default, minimal and 3; a second effort line is front_matter_invalid."""
    sub = effort_submission(t, None)
    t.new_ref(sub)
    qpath = os.path.join(sub.folder, "question.md")

    def write(effort, **kw):
        q = question_md(EFFORT_BODY, dest=sub.dest, effort=effort, **kw)
        t.edit(qpath, q, note="question.md with effort %r" % (effort,))
        sub.effort, sub.question, sub.body = effort, q, split_question(q)

    for level in EFFORT_LEVELS:
        name = "levels.%s" % level
        write(level)
        rep = t.prepare(sub, name=name)
        t.check_prepare_witness(rep, sub, name)
        t.check_prepared_settings(sub, name)
        t.eq(name + ".request_extra", t.request_extra_of(sub), {"output_config": {"effort": level}})
    label = "Reminder duplicates, round 2"
    write("low", inquiry=label, varies=sub.ref)
    t.prepare(sub, name="levels.with-notes")
    t.check_prepared_settings(sub, "levels.with-notes", inquiry=True, varies=True)
    write(None)
    rep = t.prepare(sub, name="levels.none")
    t.check_prepare_witness(rep, sub, "levels.none")
    t.check_prepared_settings(sub, "levels.none")
    t.eq("levels.none.request_extra", t.request_extra_of(sub), {})
    for label, value in (("capitalized", "High"), ("upper", "MAX"), ("mixed-case", "xHigh"), ("unknown", "extreme"),
                         ("none", "none"), ("default", "default"), ("minimal", "minimal"), ("number", "3")):
        n = t.log_kinds(sub).count("prepared")
        write(value)
        t.prepare(sub, name="levels.refused.%s" % label, expect="refused", reason="setting_invalid")
        t.eq("levels.refused.%s.no-preparation" % label, t.log_kinds(sub).count("prepared"), n)
    n = t.log_kinds(sub).count("prepared")
    t.edit(qpath, question_md(EFFORT_BODY, dest=sub.dest, effort="high", extra=(b"effort: high",)),
           note="question.md with two effort lines")
    t.prepare(sub, name="levels.refused.duplicate", expect="refused", reason="front_matter_invalid")
    t.eq("levels.refused.duplicate.no-preparation", t.log_kinds(sub).count("prepared"), n)


# ---------------------------------------------------------------------------
# C1: the effort on every request, and nowhere else.
# ---------------------------------------------------------------------------

def _effort_run(t, sub, label, accepts):
    """Run 1 meets one 529 with retry-after 61 (one attempt, interrupted provider_unavailable);
    run 2 continues and the procedure browses to an ordinary ending. Returns (fixture, procedure)."""
    pre = "c1.effort.%s" % label
    p = Procedure(browse, model=sub.model, forbidden=forbidden_for(sub))
    fx = rs.provider(t, fp.Inject(p, {1: fp.HttpError(529, retry_after="61")}), label=label, accepts=accepts)
    r1 = rs.run(t, sub, fx, name=pre + ".run-1")
    first = fx.exchanges_of(pre + ".run-1")
    rs.check_run_reply(t, r1, sub, pre + ".run-1", ending="interrupted", cause="provider_unavailable", run_number=1,
                       fx=fx, limits=rs.limits_of(sub),
                       provider=rs.provider_expected(first[-1] if first else None, 1, 1))
    r2 = rs.run(t, sub, fx, name=pre + ".run-2")
    rs.check_run_reply(t, r2, sub, pre + ".run-2", ending="ended_unsubmitted", run_number=2, fx=fx,
                       limits=rs.limits_of(sub))
    rs.check_procedure(t, p, pre, fx)
    rs.check_requests(t, fx, sub, pre)
    rs.check_history(t, fx, pre)
    second = fx.exchanges_of(pre + ".run-2")
    if first:
        rs.check_first_message(t, first[0], sub.body, False, pre + ".run-1")
    if second:
        rs.check_first_message(t, second[0], sub.body, True, pre + ".run-2")
    t.check(pre + ".accepted-by-provider", fx.exchanges and all(e.verdict and e.verdict["accepted"] for e in fx.exchanges),
            [e.verdict for e in fx.exchanges if not (e.verdict and e.verdict["accepted"])][:3])
    arr_sha = sha256_hex((sub.arrangement.get(sub.accepted_handle) or {}).get("machine", b""))
    started = t.log_bodies(sub, "run_started")
    t.eq(pre + ".run_started.arrangement", [(b or {}).get("arrangement_sha256") for b in started], [arr_sha, arr_sha])
    rc = t.cmd(["receipt", sub.ref], name=pre + ".receipt", expect="completed")
    t.check(pre + ".receipt-arrangement", contains_string(rc.data, arr_sha), "receipt lacks the arrangement digest")
    return fx, p


def _arrangement_members(sub):
    arr = sub.arrangement.get(sub.accepted_handle) or {}
    try:
        obj = strict_loads(arr.get("machine", b""))
    except StrictJSONError:
        return None
    if isinstance(obj, dict) and "request_extra" not in obj and isinstance(obj.get("body"), dict):
        obj = obj["body"]
    return obj if isinstance(obj, dict) else None


@case("c1.effort", ["C1", "C2"],
      "an effort is sent on every request as the top-level output_config and nowhere else",
      needs=("loopback",),
      controls=[Control("misspell_effort", [r"^c1\.effort\.with\..*\.(effort|spliced|request-extra-sent)$",
                                            r"^c1\.effort\.differing\..*\.only-output-config$"]),
                Control("effort_in_prompt", [r"^c1\.effort\.with\..*\.(effort|body-keys|first-message|no-effort-text)$",
                                             r"^c1\.effort\.differing\..*\.(messages|only-output-config)$"])])
def c_effort(t):
    """Two commissions of the same question and materials, one with `effort: high` and one
    without, each run the same way: run 1 meets a 529 with retry-after 61 and ends interrupted
    after one attempt; run 2 continues, lists the materials, reads one and ends ordinarily.
    With the effort: the prepared settings and the pinned request_extra carry it; every request
    (the interrupted run's and the continuation's alike) has members model, max_tokens, system,
    tools, output_config, messages with `,"output_config":{"effort":"high"}` spliced after tools
    (4.5), the fake's model of the pinned API version accepts each, and no system block, tool or
    message contains the word effort; the first messages carry the question body exactly (C2).
    run_started and the receipt name the arrangement whose bytes were sent.
    Differing: without the setting the arrangement differs only in request_extra ({}), no
    request has output_config, a provider that has no output_config at all accepts every request,
    and request by request the system, tools and messages bytes are equal, each body being the
    other with exactly the output_config member removed."""
    with_, without = effort_submission(t, "high"), effort_submission(t, None)
    for label, sub in (("with", with_), ("without", without)):
        t.accept(sub, prefix="c1.effort.%s." % label, check_witness=True)
        t.check_prepared_settings(sub, "c1.effort.%s.prepare" % label)
    t.eq("c1.effort.with.request_extra", t.request_extra_of(with_, with_.accepted_handle),
         {"output_config": {"effort": "high"}})
    t.eq("c1.effort.without.request_extra", t.request_extra_of(without, without.accepted_handle), {})
    ma, mb = _arrangement_members(with_), _arrangement_members(without)
    if t.check("c1.effort.arrangements", ma is not None and mb is not None, "arrangement records unavailable"):
        t.eq("c1.effort.differing.arrangement-rest",
             sorted(k for k in set(ma) | set(mb) if k != "request_extra" and ma.get(k) != mb.get(k)), [])
        for member in ("system", "tools"):
            t.check("c1.effort.differing.arrangement-%s-bytes" % member,
                    rs.arrangement_member_raw(with_, member) == rs.arrangement_member_raw(without, member),
                    "pinned %s bytes differ between the two arrangements" % member)
    fx_a, _ = _effort_run(t, with_, "with", fp.MESSAGES_API)
    fx_b, _ = _effort_run(t, without, "without", fp.MESSAGES_API.without("output_config"))
    for k, ex in enumerate(fx_a.exchanges, 1):
        node = ex.body_node()
        for member in ("system", "tools", "messages"):
            m = node.get(member) if node is not None and node.kind == "object" else None
            t.check("c1.effort.with.request-%d.no-effort-text" % k, m is not None and b"effort" not in m.raw.lower(),
                    {"member": member, "found": m is not None})
    t.eq("c1.effort.differing.requests", len(fx_a.exchanges), len(fx_b.exchanges))
    x = rs.effort_bytes(with_)
    for k, (a, b) in enumerate(zip(fx_a.exchanges, fx_b.exchanges), 1):
        p = "c1.effort.differing.r%d" % k
        na, nb = a.body_node(), b.body_node()
        if not t.check(p + ".bodies", na is not None and nb is not None and na.kind == nb.kind == "object",
                       "a request body is not a JSON object"):
            continue
        for member in ("system", "tools", "messages"):
            ma_, mb_ = na.get(member), nb.get(member)
            t.check(p + "." + member, ma_ is not None and mb_ is not None and ma_.raw == mb_.raw,
                    "%s bytes differ between the commissions with and without the effort" % member)
        tools = na.get("tools")
        cut = None
        if tools is not None and a.body[tools.end:tools.end + len(x)] == x:
            cut = a.body[:tools.end] + a.body[tools.end + len(x):]
        t.check(p + ".only-output-config", cut is not None and cut == b.body,
                {"with": short(a.body[:200]), "without": short(b.body[:200])})
        t.check(p + ".without-has-no-output-config", nb.get("output_config") is None, nb.keys())


# ---------------------------------------------------------------------------
# C9: provider rejections, reported as the provider gave them.
# ---------------------------------------------------------------------------

LEVEL = "xhigh"


def drifts():
    """(label, what moved, the moved provider): each changes one fact of the pinned API
    version's model; graceless and long-message also change how it words the refusal."""
    removed = fp.MESSAGES_API.without("output_config")
    long_base = "output_config: Extra inputs are not permitted"
    return [
        ("renamed", "the effort is known under another name",
         fp.MESSAGES_API.renamed("output_config.effort", "reasoning_effort")),
        ("removed", "output_config is no longer accepted at all", removed),
        ("level-withdrawn", "the level %s is no longer accepted" % LEVEL,
         fp.MESSAGES_API.withdrawn("output_config.effort", LEVEL)),
        ("graceless", "the parameter is gone and the refusal is an HTML page, not an error object",
         removed.answering(fp.Page())),
        ("long-message", "the parameter is gone and the message runs past the 1,024 bytes a record keeps",
         removed.answering(fp.ErrorObject(detail=fp.long_detail(long_base)))),
    ]


@case("c9.provider-rejections", ["C9", "C6"],
      "a provider that moved away from what the release sends is reported as it answered; one that did not runs",
      needs=("loopback",),
      controls=[Control("hide_provider_message", [r"^c9\.rejections\..*\.(provider|run_ended\.provider)$"]),
                Control("rejection_as_unavailable", [r"^c9\.rejections\..*\.(attempts|cause|then|run_ended\.attempts|"
                                                     r"run_ended\.cause)$"])])
def c_provider_rejections(t):
    """One commission with `effort: xhigh` per drift of the fake provider's model: the effort
    renamed, output_config removed, the level withdrawn, output_config removed and refused with
    an HTML 400 page (no error object, no request ID), and output_config removed with a message
    over 1,024 bytes whose cut falls inside a character. Runs 1 and 2 each make one attempt that
    the model refuses, end interrupted with cause provider_rejected and exit 5; the run reply and
    run_ended give status, error_type, error_message (cut as the attempt record cuts it) and
    request_id exactly as the fake sent them, or null where it sent none, with request 1 and
    attempt 1; the attempt record says http_error, then end, charged none; the raw response
    capture holds the body sent; run 2 reports the same status, type and message; status says
    interrupted with the last run provider_rejected. Every request carries the effort exactly
    (4.5). Invariance: with the fake moved back to the pinned API version's model, run 3 of the
    same commission is accepted and ends ordinarily."""
    for label, why, model in drifts():
        pre = "c9.rejections.%s" % label
        sub = effort_submission(t, LEVEL)
        t.accept(sub, prefix=pre + ".")
        p = Procedure(browse, model=sub.model, forbidden=forbidden_for(sub))
        fx = rs.provider(t, p, label=label, accepts=model)
        facts = []
        for i in (1, 2):
            name = "%s.run-%d" % (pre, i)
            rep = rs.run(t, sub, fx, name=name)
            facts.append(rs.check_rejection(t, sub, fx, rep, name, run_number=i))
            exs = fx.exchanges_of(name)
            t.check(name + ".refused-by-model", bool(exs) and all(e.verdict and not e.verdict["accepted"] for e in exs),
                    {"moved": why, "verdicts": [e.verdict for e in exs][:2]})
        same = lambda f: [f.get(k) for k in ("status", "error_type", "error_message")] if isinstance(f, dict) else f
        t.eq(pre + ".same-refusal", same(facts[1]), same(facts[0]))
        st = t.status(sub, name=pre + ".status")
        t.eq(pre + ".status.condition", st.data.get("condition"), "interrupted")
        last = (st.data.get("runs") or {}).get("last") or {}
        t.eq(pre + ".status.last", {k: last.get(k) for k in ("number", "ending", "cause", "recorded_by")},
             {"number": 2, "ending": "interrupted", "cause": "provider_rejected", "recorded_by": "run"})
        fx.gate.accepts = fp.MESSAGES_API
        name = pre + ".run-3"
        rep = rs.run(t, sub, fx, name=name)
        rs.check_run_reply(t, rep, sub, name, ending="ended_unsubmitted", run_number=3, fx=fx,
                           limits=rs.limits_of(sub))
        third = fx.exchanges_of(name)
        t.check(name + ".accepted-by-model", bool(third) and all(e.verdict and e.verdict["accepted"] for e in third),
                [e.verdict for e in third][:2])
        rs.check_procedure(t, p, pre, fx)
        rs.check_requests(t, fx, sub, pre)
        rs.check_history(t, fx, pre)
        rs.check_run_ended_usage(t, sub, fx, [pre + ".run-1", pre + ".run-2", name], pre)
