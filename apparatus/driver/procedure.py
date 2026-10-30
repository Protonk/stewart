# -*- coding: utf-8 -*-
"""A scripted auditor for exact protocol-shape cases (ACCEPTANCE: "Fixed scripts remain
for exact protocol-shape cases").

A case writes the auditor's side as a generator function `body(p)`. Each `yield`
hands the fake provider the next response (built with `p.calls`, `p.end`,
`p.step`); the value the yield returns is a `Turn` holding Stewart's replies to
the calls of that response, decoded, plus any notice text blocks that followed
them. So the case chooses each call from Stewart's actual replies, and can
follow `next` calls with the helpers `read_all`, `wwaw_all`, `search_all` and
`list_all` (`yield from`).

The generator runs on the fake provider's handler thread. It records named
checks with `p.check` / `p.eq` instead of touching the case's T; after the run
the case calls `run_support.check_procedure(t, p)`, which turns them, and every
reply that broke the envelope rules (INTERFACE 1.3, 7.1), into checks on the main
thread. A request after the generator has finished, or a reply to an unknown
tool_use ID, is an anomaly.

A continuation (a new conversation after the run died) arrives as a Turn with
`new_conversation` set and no replies; the generator decides what to do.
"""
from __future__ import annotations

import base64
import hashlib
import json
import threading

import fake_provider as fp
import rawjson
from driver_core import CONTINUATION, REMINDER, StrictJSONError, short, strict_loads
from reacting_auditor import _btype, _sval, tool_envelope_problems


class Reply:
    """Stewart's reply to one tool call, as the tool_result block carried it."""

    def __init__(self, call, block):
        self.call, self.block = call, block
        self.tid, self.tool = call["id"], call["tool"]
        self.env, self.raw_text, self.page_text, self.problem = None, None, None, None
        self.is_error = None
        content = block.get("content") if block is not None else None
        items = content.items if content is not None and content.kind == "array" else []
        self.content_raw = content.raw if content is not None else None
        ie = block.get("is_error") if block is not None else None
        self.is_error = {b"true": True, b"false": False}.get(ie.raw) if ie is not None else None
        if items and _btype(items[0]) == "text":
            self.raw_text = _sval(items[0].get("text"))
            try:
                self.env = strict_loads(self.raw_text.encode("utf-8"))
            except (StrictJSONError, AttributeError) as exc:
                self.problem = "envelope is not strict JSON: %s" % exc
        else:
            self.problem = "first content block is not text"
        if len(items) > 1 and _btype(items[1]) == "text":
            self.page_text = _sval(items[1].get("text"))
        self.blocks = len(items)

    @property
    def outcome(self):
        return self.env.get("outcome") if isinstance(self.env, dict) else None

    @property
    def reason(self):
        return self.env.get("reason") if isinstance(self.env, dict) else None

    @property
    def data(self):
        d = self.env.get("data") if isinstance(self.env, dict) else None
        return d if isinstance(d, dict) else {}

    @property
    def effects(self):
        e = self.env.get("effects") if isinstance(self.env, dict) else None
        return e if isinstance(e, dict) else {}

    @property
    def next(self):
        n = self.env.get("next") if isinstance(self.env, dict) else None
        return n if isinstance(n, list) else []

    def next_of(self, tool):
        return [n for n in self.next if isinstance(n, dict) and n.get("tool") == tool]

    def page(self):
        """The bytes of a read page: the second block, data.text, or decoded data.base64."""
        d = self.data
        if "base64" in d:
            try:
                return base64.b64decode(d["base64"], validate=True)
            except (ValueError, TypeError):
                return None
        if self.page_text is not None:
            return self.page_text.encode("utf-8")
        t = d.get("text")
        return t.encode("utf-8") if isinstance(t, str) else None

    def summary(self):
        return {"id": self.tid, "tool": self.tool, "outcome": self.outcome, "reason": self.reason,
                "effects": self.effects, "data": short(self.data, 300)}


class Turn:
    def __init__(self, ex, conversation, new_conversation, replies=(), texts=(), first_message=None):
        self.ex, self.conversation, self.new_conversation = ex, conversation, new_conversation
        self.replies, self.texts, self.first_message = list(replies), list(texts), first_message

    def reply(self, i=0):
        return self.replies[i] if i < len(self.replies) else None

    @property
    def reminder(self):
        return REMINDER in self.texts


class Procedure:
    def __init__(self, body, *, model="claude-opus-5-5", forbidden=(), thinking=False, name="procedure"):
        self.body, self.model, self.name = body, model, name
        self.forbidden = [f for f in forbidden if f]
        self.thinking = thinking
        self.gen = None
        self.finished = False
        self.conversations = 0
        self.seq = 0
        self.k = 0
        self.pending = []
        self.calls = {}
        self.replies = []
        self.checks = []
        self.anomalies = []
        self.texts = []
        self.first_messages = []
        self.answers = {}
        self.lock = threading.Lock()
        self.turn = None

    # -- building responses -----------------------------------------------------
    def call(self, tool, input=None, raw_input=None, tid=None, raw_block=None):
        """A tool_use block. raw_input sends exact input bytes; raw_block the whole block."""
        self.seq += 1
        tid = tid if tid is not None else "toolu_p%02d_%05d" % (max(self.conversations, 1), self.seq)
        if raw_input is None and raw_block is None:
            raw_input = rawjson.compact(input if input is not None else {})
        blk = fp.tool_use(tid, tool, raw_input=raw_input, raw=raw_block)
        self.calls.setdefault(tid, {"id": tid, "tool": tool, "input": input, "raw_input": raw_input,
                                    "raw_block": blk.raw, "conversation": self.conversations})
        return blk

    def usage(self):
        self.k += 1
        return fp.Usage(1200 + 7 * self.k, 40 + self.k % 9)

    def step(self, blocks, stop_reason="tool_use", usage=None, **kw):
        pre = []
        if self.thinking:
            pre.append(fp.thinking("Procedure turn %d." % (self.k + 1), "c2lnLXByb2M=%04d" % (self.k + 1)))
        msg = fp.Message(pre + list(blocks), stop_reason=stop_reason, usage=usage or self.usage(),
                         model=self.model, **kw)
        self.pending = [b.meta.get("id") for b in msg.tool_uses()]
        return msg

    def calls_step(self, *specs, **kw):
        """A tool_use response from (tool, input) pairs or ready Blocks."""
        blocks = [s if isinstance(s, fp.Block) else self.call(s[0], s[1] if len(s) > 1 else None) for s in specs]
        return self.step(blocks, **kw)

    def end(self, text="I am stopping here.", stop_reason="end_turn", **kw):
        return self.step([fp.text(text)], stop_reason=stop_reason, **kw)

    # -- checks -----------------------------------------------------------------
    def check(self, name, cond, detail=None):
        with self.lock:
            self.checks.append((name, bool(cond), None if cond else short(detail, 1500)))
        return bool(cond)

    def eq(self, name, actual, expected):
        return self.check(name, actual == expected, {"actual": actual, "expected": expected})

    def anomaly(self, check, detail):
        with self.lock:
            self.anomalies.append({"check": check, "detail": short(detail, 1500)})

    # -- following next calls ---------------------------------------------------
    def read_all(self, source, start=0, name=None):
        """Read source to its end following the replies' next calls. Returns (bytes, pages),
        pages being the Replies; None bytes when a page is refused."""
        buf, pages, inp = bytearray(), [], {"source": source} if not start else {"source": source, "start": start}
        while True:
            turn = yield self.calls_step(("read", inp))
            r = turn.reply(0)
            pages.append(r)
            if r is None or r.outcome != "completed":
                return None, pages
            page = r.page()
            if page is None:
                self.anomaly("read.page-missing", {"source": source, "data": short(r.data, 300)})
                return None, pages
            buf += page
            nxt = r.next_of("read")
            if r.data.get("complete") is True:
                if nxt:
                    self.anomaly("read.next-when-complete", {"source": source})
                return bytes(buf), pages
            if not nxt or not isinstance(nxt[0].get("input"), dict):
                self.anomaly("read.incomplete-without-next", {"source": source, "data": short(r.data, 300)})
                return bytes(buf), pages
            inp = nxt[0]["input"]

    def wwaw_all(self):
        """what_am_i_working_with through every page. Returns (first page data, entries, Replies)."""
        first, entries, pages, inp = None, [], [], {}
        while True:
            turn = yield self.calls_step(("what_am_i_working_with", inp))
            r = turn.reply(0)
            pages.append(r)
            if r is None or r.outcome != "completed":
                return first, entries, pages
            if first is None:
                first = r.data
            entries += list(r.data.get("entries") or [])
            page = r.data.get("page") or {}
            nxt = r.next_of("what_am_i_working_with")
            if page.get("complete") is True or not nxt:
                return first, entries, pages
            inp = nxt[0].get("input") or {}

    def search_all(self, text, sources=None):
        """search through every page following its sc. cursor. Returns (hits, Replies)."""
        inp = {"text": text}
        if sources is not None:
            inp["sources"] = sources
        hits, pages = [], []
        while True:
            turn = yield self.calls_step(("search", inp))
            r = turn.reply(0)
            pages.append(r)
            if r is None or r.outcome != "completed":
                return None, pages
            hits += find_hits(r.data)
            nxt = r.next_of("search")
            if r.data.get("complete") is True or not nxt:
                return hits, pages
            inp = nxt[0].get("input") or {}

    def list_all(self):
        mats, pages, inp = [], [], {}
        while True:
            turn = yield self.calls_step(("list", inp))
            r = turn.reply(0)
            pages.append(r)
            if r is None or r.outcome != "completed":
                return None, pages
            mats += list(r.data.get("materials") or [])
            nxt = r.next_of("list")
            if r.data.get("complete") is True or not nxt:
                return mats, pages
            inp = nxt[0].get("input") or {}

    # -- the responder --------------------------------------------------------------
    def __call__(self, ex):
        key = ex.body_sha256()
        if key in self.answers:
            return self.answers[key]
        step = self._respond(ex)
        self.answers[key] = step
        return step

    def _respond(self, ex):
        msgs = ex.messages()
        if not msgs:
            self.anomaly("request.messages", "request %s has no messages" % ex.n)
            return fp.Message([fp.text("unreadable request")], stop_reason="end_turn")
        if len(msgs) == 1:
            self.conversations += 1
            self.first_messages.append(msgs[0].raw)
            turn = Turn(ex, self.conversations, True, first_message=msgs[0])
            self.pending = []
        else:
            turn = self._absorb(msgs[-1], ex)
        self.turn = turn
        if self.finished:
            self.anomaly("request.after-end", "request %s arrived after the procedure ended" % ex.n)
            return self.end("The procedure has ended.")
        try:
            if self.gen is None:
                self.gen = self.body(self)
                step = next(self.gen)
            else:
                step = self.gen.send(turn)
        except StopIteration:
            self.finished = True
            return self.end("The procedure has ended.")
        if not isinstance(step, fp.Step):
            self.anomaly("procedure.step", repr(step))
            return self.end("bad step")
        return step

    def _absorb(self, msg, ex):
        items = []
        if msg.kind == "object" and msg.get("content") is not None and msg.get("content").kind == "array":
            items = msg.get("content").items
        results = [b for b in items if _btype(b) == "tool_result"]
        texts = [_sval(b.get("text")) for b in items if _btype(b) == "text"]
        order = [_btype(b) for b in items]
        if order != ["tool_result"] * len(results) + ["text"] * len(texts):
            self.anomaly("user-message.order", order)
        ids = [_sval(b.get("tool_use_id")) for b in results]
        if ids != self.pending:
            self.anomaly("tool-results.order", {"expected": self.pending, "got": ids})
        replies = []
        for b in results:
            tid = _sval(b.get("tool_use_id"))
            call = self.calls.get(tid)
            if call is None:
                self.anomaly("tool-results.unknown-id", tid)
                continue
            r = Reply(call, b)
            r.ex = ex          # the request that carried this reply
            replies.append(r)
            self.replies.append(r)
            if r.problem:
                self.anomaly("reply.%s" % call["tool"], r.problem)
                continue
            for problem in tool_envelope_problems(r.env, call["tool"], r.raw_text, self.forbidden):
                self.anomaly("reply.envelope.%s" % call["tool"], problem)
            if r.is_error is not (r.outcome != "completed"):
                self.anomaly("reply.is_error.%s" % call["tool"], {"outcome": r.outcome, "is_error": r.is_error})
        self.texts += texts
        self.pending = []
        return Turn(ex, self.conversations, False, replies, texts)

    def witness(self):
        return {"conversations": self.conversations, "calls": list(self.calls.values()),
                "replies": [r.summary() for r in self.replies], "checks": self.checks,
                "anomalies": self.anomalies, "texts": self.texts}


def find_hits(data):
    """Search hits located structurally (7.2 names a hit's members but not the list's key)."""
    best = []
    for v in data.values() if isinstance(data, dict) else []:
        if isinstance(v, list) and v and all(isinstance(x, dict) and {"source", "start", "end", "cite"} <= set(x)
                                             for x in v):
            best = v if len(v) > len(best) else best
    return best


def first_message_bytes(question_body, continuing):
    from driver_core import pinned_json_string
    blocks = [b'{"type":"text","text":' + pinned_json_string(question_body.decode("utf-8")).encode("utf-8") + b"}"]
    if continuing:
        blocks.append(b'{"type":"text","text":' + pinned_json_string(CONTINUATION).encode("utf-8") + b"}")
    return b'{"role":"user","content":[' + b",".join(blocks) + b"]}"


# ---------------------------------------------------------------------------
# Self-test against the stand-in (no binary).
# ---------------------------------------------------------------------------

def _selftest_procedure():
    import mini_stewart
    from reacting_auditor import _scenario_material
    q, mats = _scenario_material()
    out = []

    def body(p):
        text, pages = yield from p.read_all("question")
        p.eq("q.bytes", text, q)
        p.check("q.pages", len(pages) >= 2, len(pages))
        turn = yield p.calls_step(("record_observation", {"text": "A", "label": "x"}),
                                  ("record_observation", {"text": "A", "label": "x"}))
        h1, h2 = turn.reply(0).data.get("entry"), turn.reply(1).data.get("entry")
        p.check("distinct", h1 != h2 and h1 and h2, (h1, h2))
        turn = yield p.calls_step(("replace", {"entry": h2, "text": "B", "citations": [], "label": "x"}))
        turn = yield p.calls_step(("replace", {"entry": h2, "text": "C", "citations": [], "label": "x"}))
        p.eq("stale", turn.reply(0).reason, "stale_entry")
        first, entries, pages = yield from p.wwaw_all()
        p.eq("entries", [e.get("id") for e in entries], ["e1", "e2"])
        turn = yield p.calls_step(("prepare", {}))
        ap = turn.reply(0).data.get("prepared")
        sel, _ = yield from p.read_all(ap + "/selection")
        p.check("selection", sel is not None and b'"text":"B"' in sel, sel)
        yield p.calls_step(("submit", {"prepared": ap, "confirm": True}))

    p = Procedure(body, forbidden=("/archive/root",))
    sim = mini_stewart.MiniStewart(p, q, mats)
    ending = sim.run()
    out.append(("procedure.sealed", ending == "sealed", ending))
    out.append(("procedure.checks", all(c[1] for c in p.checks) and len(p.checks) == 6, p.checks))
    out.append(("procedure.no-anomalies", not p.anomalies, p.anomalies[:3]))
    return out


try:
    from driver_core import selftest as _selftest
    _selftest(_selftest_procedure)
except ImportError:  # pragma: no cover
    pass
