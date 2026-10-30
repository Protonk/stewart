# -*- coding: utf-8 -*-
"""The reacting auditor: a deterministic policy the fake provider runs (ACCEPTANCE,
"The scripted tier").

It has a goal list of entries whose bytes the driver keeps as the witness. It
chooses each call from Stewart's actual replies, following their `next` calls
for pages. After a forced compaction (a `compaction` block it emits) or at the
start of every conversation (a continuation after a kill) it discards its
memory and rebuilds its view only from the continuation notice,
what_am_i_working_with and its reads; it then adds only the goals it cannot see
recorded. A re-entry that omits an element therefore produces a duplicate, which
the witness comparison catches: the return must contain each goal exactly once.

Policy and witness are kept apart on purpose. `self.mem` is the auditor's
memory, the only state its choices use, and is replaced by an empty Memory on
compaction and at each new conversation. `self.goals`, the witness copies of the
question and materials (its task) and the anomaly list are the driver's; the
policy never consults what earlier replies said except through `self.mem`.

Every reply is checked as it arrives (INTERFACE 1.3, 7.1-7.6) against the
driver's own expectations: read pages against the witness bytes and the page
rule, citations against answer_witness.record_citation, allowances against the
fake provider's charges, prepared views against answer_witness. Each failed
expectation is an anomaly ("auditor.<check>"); a case turns anomalies into
failed checks, so sabotage controls can target them.
"""
from __future__ import annotations

import base64
import hashlib
import json

import answer_witness as aw
import fake_provider as fp
import rawjson
from driver_core import (CONTINUATION, EFFECT_VALUES, ENVELOPE_ORDER, FAMILY_TOOLS, NEAR_LIMIT, OUTCOMES,
                         REMINDER, REPLY_SCHEMA, StrictJSONError, is_compact_json, iter_values, selftest,
                         short, strict_loads, tool_effect_keys)

NEAR_LIMIT_PERCENT = 20
EXEMPT_KEYS = ("text", "base64", "preview", "context", "quote", "label")


class Goal:
    """One entry the auditor means to record. kind is the record tool (or record_artifact).
    draft: record this text first, then replace it with `text`. artifact: None, 'text' or
    'base64' (data is then the artifact bytes). bad_first: (input overrides, reason) for a
    call that must be refused before the good one is made."""

    def __init__(self, label, text="", kind="record_observation", citations=(), draft=None, artifact=None,
                 data=None, bad_first=None):
        self.label, self.text, self.kind = label, text, kind
        self.citations = [dict(c) for c in citations]
        self.draft, self.artifact, self.bad_first = draft, artifact, bad_first
        if artifact == "base64":
            self.data = data
        else:
            self.data = (text if artifact else text).encode("utf-8")
        if artifact and kind != "record_artifact":
            raise ValueError("an artifact goal uses record_artifact")

    def input(self, text=None, final=True, entry=None):
        """The tool input for recording (or, with entry, replacing) this goal."""
        d = {}
        if entry is not None:
            d["entry"] = entry
        if self.artifact == "base64":
            d["label"] = self.label
            d["base64"] = base64.b64encode(self.data).decode("ascii")
            return d
        if self.artifact == "text":
            d["label"] = self.label
            d["text"] = self.text if final else (self.draft or self.text)
            return d
        d["text"] = text if text is not None else (self.text if final else (self.draft or self.text))
        d["citations"] = self.citations
        d["label"] = self.label
        return d

    def witness(self):
        return {"label": self.label, "kind": self.kind, "text": self.text, "draft": self.draft,
                "artifact": self.artifact, "data_sha256": hashlib.sha256(self.data).hexdigest(),
                "citations": self.citations, "bad_first": self.bad_first}


class Memory:
    """Everything the policy may use. Discarded on compaction and at each new conversation."""

    def __init__(self):
        self.queue = []
        self.entries = {}        # goal label -> {"id", "version", "handle", "state", "kind"}
        self.reads = {}          # source -> {"buf", "next", "complete"}
        self.listed = None
        self.wwaw = None         # {"entries": [...], "next": input or None, "complete": bool}
        self.reentered = False
        self.pending = []        # calls awaiting results, in block order
        self.bad_done = set()
        self.prepared = None
        self.dry_done = False
        self.submitted = False
        self.ended = False
        self.reminder_seen = False


class ReactingAuditor:
    def __init__(self, goals, *, question, materials, family="open-inquiry", limits=None, provider=None,
                 compact_after=(), calls_per_turn=1, read_materials=True, read_question=True, finish="submit",
                 after_reminder="submit", thinking_blocks=True, forbidden=(), max_turns=400, model="claude-opus-5-5"):
        self.goals = list(goals)
        labels = [g.label for g in self.goals]
        if len(set(labels)) != len(labels):
            raise ValueError("goal labels must be unique")
        self.question = question                       # body bytes
        self.materials = dict(materials)               # "materials/<name>" -> bytes
        self.sources = dict(self.materials)
        self.sources["question"] = question
        self.family = family
        self.limits = limits                           # {"turns", "input_tokens", "output_tokens"}
        self.provider = provider                       # FakeProvider: charges for allowance checks
        self.compact_after = sorted(set(compact_after))
        self.calls_per_turn = calls_per_turn
        self.read_materials, self.read_question = read_materials, read_question
        self.finish, self.after_reminder = finish, after_reminder
        self.thinking_blocks, self.forbidden = thinking_blocks, [f for f in forbidden if f]
        self.max_turns, self.model = max_turns, model
        self.mem = Memory()
        # Witness (never consulted by the policy).
        self.conversations = 0
        self.turns = 0
        self.call_seq = 0
        self.mutations_done = 0          # completed record/replace/delete replies seen, all conversations
        self.compactions = []
        self.events = []
        self.anomalies = []
        self.issued = {}                 # tool_use id -> call
        self.replies = []                # (tool_use id, tool, outcome, reason)
        self.answers = {}                # request body digest -> step (a retried request gets the same answer)
        self.reminders_seen = 0
        self.notices_seen = []
        self.final_selection = None      # what the auditor last verified in a prepared selection view
        self.sealed = None

    # -- witness helpers ---------------------------------------------------
    def anomaly(self, check, detail):
        self.anomalies.append({"check": check, "detail": short(detail, 1500), "conversation": self.conversations,
                               "turn": self.turns})

    def event(self, what, **kw):
        kw["event"] = what
        kw["conversation"] = self.conversations
        kw["turn"] = self.turns
        self.events.append(kw)

    def witness(self):
        return {"goals": [g.witness() for g in self.goals], "events": self.events, "anomalies": self.anomalies,
                "conversations": self.conversations, "turns": self.turns, "compactions": self.compactions,
                "mutations_done": self.mutations_done, "reminders_seen": self.reminders_seen,
                "notices_seen": self.notices_seen, "final_selection": self.final_selection,
                "sealed": self.sealed}

    # -- the responder -------------------------------------------------------
    def __call__(self, ex):
        key = ex.body_sha256()
        if key in self.answers:
            self.event("retried request answered again", n=ex.n)
            return self.answers[key]
        step = self._respond(ex)
        self.answers[key] = step
        return step

    def _respond(self, ex):
        msgs = ex.messages()
        if msgs is None:
            self.anomaly("request.messages", "request %s has no messages array" % ex.n)
            return self._end_turn("I cannot read this request.")
        if len(msgs) == 1:
            self._new_conversation(msgs[0])
        else:
            if self.mem.submitted:
                self.anomaly("request.after-confirmed-submit",
                             "request %s arrived after a confirmed submit whose result Stewart should not send" % ex.n)
            self._absorb(msgs[-1], ex)
        self.turns += 1
        if self.turns > self.max_turns:
            self.anomaly("policy.turn-cap", "more than %d turns" % self.max_turns)
            return self._end_turn("Stopping: turn cap.")
        blocks = []
        if self.thinking_blocks:
            blocks.append(fp.thinking("Turn %d of conversation %d." % (self.turns, self.conversations),
                                      "c2lnLXR1cm4t%04d" % self.turns))
        if self.compact_after and self.mutations_done >= self.compact_after[0]:
            point = self.compact_after.pop(0)
            self.compactions.append({"after_mutations": point, "turn": self.turns, "n": ex.n})
            blocks.append(fp.compaction("Context summarized. Recorded work is in the ledger; check before repeating."))
            self.event("compaction: memory discarded", after_mutations=point)
            self.mem = Memory()
            self.mem.queue = ["reenter"]
        if self.mem.ended:
            return self._end_turn("Done.", blocks)
        calls = self._next_calls()
        if not calls:
            return self._finish(blocks)
        for c in calls:
            blocks.append(fp.tool_use(c["id"], c["tool"], raw_input=c["raw_input"]))
        self.mem.pending = [c["id"] for c in calls]
        return fp.Message(blocks, stop_reason="tool_use", usage=self._usage(), model=self.model)

    def _usage(self):
        k = self.turns
        cc = (7 * k) if k % 3 == 1 else (fp.ABSENT if k % 3 == 2 else None)
        cr = (k % 5) if k % 2 else fp.ABSENT
        return fp.Usage(1500 + 13 * k, 60 + (k % 17), cache_creation=cc, cache_read=cr)

    def _end_turn(self, words, blocks=None):
        blocks = list(blocks or [])
        blocks.append(fp.text(words))
        return fp.Message(blocks, stop_reason="end_turn", usage=self._usage(), model=self.model)

    def _finish(self, blocks):
        """Nothing left to call: end the turn without submitting. With finish='ordinary' this is
        the ordinary stop that earns the reminder (6.4); after_reminder then decides."""
        if self.finish == "submit":
            self.event("nothing left to call before a submit")
        return self._end_turn("I am stopping without submitting.", blocks)

    # -- conversation start ----------------------------------------------------
    def _new_conversation(self, first):
        self.conversations += 1
        self.mem = Memory()
        content = first.get("content") if first.kind == "object" else None
        items = content.items if content is not None and content.kind == "array" else []
        if first.kind != "object" or first.get("role") is None:
            self.anomaly("first-message.shape", first.raw[:200])
            return
        want_q = b'{"type":"text","text":' + aw.pinned_json_string(self.question.decode("utf-8")).encode("utf-8") + b"}"
        if not items or items[0].raw != want_q:
            self.anomaly("first-message.question", {"got": items[0].raw[:300] if items else None})
        if first.keys() != ["role", "content"] or first.get("role").raw != b'"user"':
            self.anomaly("first-message.shape", first.raw[:200])
        cont = [i for i in items[1:]]
        if self.conversations == 1:
            if cont:
                self.anomaly("first-message.unexpected-block", [c.raw[:200] for c in cont])
        else:
            want_c = b'{"type":"text","text":' + aw.pinned_json_string(CONTINUATION).encode("utf-8") + b"}"
            if len(cont) != 1 or cont[0].raw != want_c:
                self.anomaly("first-message.continuation-notice", [c.raw[:300] for c in cont])
        self.event("conversation started", continuing=self.conversations > 1)
        q = []
        if self.read_question:
            q.append("question")
        if self.read_materials and self.conversations == 1:
            q += ["list", "materials"]
        q.append("reenter")
        self.mem.queue = q

    # -- replies ------------------------------------------------------------------
    def _absorb(self, msg, ex):
        if msg.kind != "object" or msg.keys() != ["role", "content"] or msg.get("role").raw != b'"user"':
            self.anomaly("user-message.shape", msg.raw[:200])
            return
        items = msg.get("content").items if msg.get("content") is not None else []
        results = [b for b in items if _btype(b) == "tool_result"]
        texts = [b for b in items if _btype(b) == "text"]
        order = [_btype(b) for b in items]
        if order != ["tool_result"] * len(results) + ["text"] * len(texts):
            self.anomaly("user-message.order", order)
        got_ids = [_sval(b.get("tool_use_id")) for b in results]
        if got_ids != self.mem.pending:
            self.anomaly("tool-results.order", {"expected": self.mem.pending, "got": got_ids})
        for b in results:
            tid = _sval(b.get("tool_use_id"))
            call = self.issued.get(tid)
            if call is None:
                self.anomaly("tool-results.unknown-id", tid)
                continue
            if b.keys() != ["type", "tool_use_id", "content", "is_error"]:
                self.anomaly("tool-result.keys", b.keys())
            self._on_result(call, b, ex)
        self.mem.pending = []
        for t in texts:
            self._on_notice(_sval(t.get("text")), t, ex)

    def _on_notice(self, text, block, ex):
        if text == REMINDER:
            self.reminders_seen += 1
            self.mem.reminder_seen = True
            self.event("reminder received", n=ex.n)
            if self.reminders_seen > 1:
                self.anomaly("notice.reminder-repeated", "the reminder arrived %d times in this audit" % self.reminders_seen)
            if self.after_reminder == "submit":
                self.mem.queue = ["work", "prepare", "inspect", "dry", "submit"]
            else:
                self.mem.ended = True
            return
        if isinstance(text, str) and text.startswith("Allowance notice:"):
            self.notices_seen.append({"n": ex.n, "text": text})
            if len(self.notices_seen) > 1:
                self.anomaly("notice.near-limit-repeated", self.notices_seen)
            want = self.expected_near_limit(ex)
            if want is not None and text != want[0]:
                self.anomaly("notice.near-limit-text", {"expected": want[0], "got": text})
            return
        self.anomaly("notice.unexpected-text", text)

    def expected_near_limit(self, ex):
        """(text, exchange that triggered it) from the fake's charges (6.4), or None."""
        if not self.limits or self.provider is None:
            return None
        running = {k: 0 for k in ("turns", "input_tokens", "output_tokens")}
        overrides = getattr(self.provider, "charge_overrides", {})
        for e in self.provider.exchanges:
            if e.n >= ex.n:
                break
            c = overrides.get(e.n, e.charge)
            if isinstance(c, str):
                c = fp.charge_of(c, e, getattr(e.step, "usage", None))
            if c and c.get("basis") in ("reported", "estimated"):
                for k in running:
                    running[k] += c[k] or 0
                rem = {k: max(0, self.limits[k] - running[k]) for k in running}
                if any(rem[k] * 100 <= NEAR_LIMIT_PERCENT * self.limits[k] for k in rem):
                    return (NEAR_LIMIT.format(turns=rem["turns"], input_tokens=rem["input_tokens"],
                                              output_tokens=rem["output_tokens"]), e.n)
        return None

    def expected_allowances(self, ex):
        if not self.limits or self.provider is None:
            return None
        tot = fp.totals(self.provider.exchanges, upto=ex.n - 1,
                        overrides=getattr(self.provider, "charge_overrides", None))
        for k, v in getattr(self.provider, "extra_charges", {}).items():
            tot[k[0]][k[1]] += v
        return fp.allowances(tot, self.limits)

    def _on_result(self, call, block, ex):
        tool = call["tool"]
        content = block.get("content")
        cblocks = content.items if content is not None and content.kind == "array" else []
        is_error = block.get("is_error")
        if not cblocks or _btype(cblocks[0]) != "text":
            self.anomaly("reply.first-block", {"tool": tool, "content": block.raw[:300]})
            return
        env_text = _sval(cblocks[0].get("text"))
        try:
            env = strict_loads(env_text.encode("utf-8"))
        except (StrictJSONError, AttributeError) as exc:
            self.anomaly("reply.strict-json", {"tool": tool, "error": str(exc), "text": (env_text or "")[:300]})
            return
        for problem in tool_envelope_problems(env, tool, env_text, self.forbidden):
            self.anomaly("reply.envelope", {"tool": tool, "problem": problem})
        outcome = env.get("outcome")
        if is_error is None or is_error.raw != (b"false" if outcome == "completed" else b"true"):
            self.anomaly("reply.is_error", {"tool": tool, "outcome": outcome, "is_error": is_error.raw if is_error else None})
        page_text = None
        if len(cblocks) > 1:
            if len(cblocks) != 2 or _btype(cblocks[1]) != "text":
                self.anomaly("reply.extra-blocks", {"tool": tool, "blocks": [b.raw[:80] for b in cblocks]})
            page_text = _sval(cblocks[1].get("text"))
        self.replies.append((call["id"], tool, outcome, env.get("reason")))
        handler = getattr(self, "_reply_" + call["purpose"], None)
        if handler is None:
            self.anomaly("policy.no-handler", call["purpose"])
            return
        handler(call, env, page_text, ex)

    # -- calls ------------------------------------------------------------------
    def _call(self, tool, input_, purpose, **meta):
        self.call_seq += 1
        tid = "toolu_c%02d_%05d" % (self.conversations, self.call_seq)
        raw = rawjson.compact(input_)
        c = {"id": tid, "tool": tool, "input": input_, "raw_input": raw, "purpose": purpose}
        c.update(meta)
        self.issued[tid] = c
        self.event("call", id=tid, tool=tool, purpose=purpose, input=_short_input(input_))
        return c

    def _next_calls(self):
        guard = 0
        while self.mem.queue:
            guard += 1
            if guard > 50:
                self.anomaly("policy.no-progress", self.mem.queue)
                return []
            phase = self.mem.queue[0]
            calls = getattr(self, "_phase_" + phase)()
            if calls is None:
                self.mem.queue.pop(0)
                if not self.mem.queue and phase in ("reenter", "materials", "list", "question"):
                    self.mem.queue = self._work_queue()
                continue
            return calls
        return []

    def _work_queue(self):
        if self.finish == "submit":
            return ["work", "prepare", "inspect", "dry", "submit"]
        if self.finish == "ordinary":
            return ["work"]
        return ["work"]

    # Reading a source fully, following the replies' next calls.
    def _read_call(self, source, purpose):
        st = self.mem.reads.get(source)
        if st is None:
            st = self.mem.reads[source] = {"buf": bytearray(), "next": {"source": source}, "complete": False,
                                           "pages": 0}
        if st["complete"]:
            return None
        return [self._call("read", dict(st["next"]), purpose, source=source)]

    def _phase_question(self):
        return self._read_call("question", "read_source")

    def _phase_list(self):
        if self.mem.listed is not None and self.mem.listed.get("complete"):
            return None
        inp = {} if self.mem.listed is None else dict(self.mem.listed["next"])
        return [self._call("list", inp, "list")]

    def _phase_materials(self):
        names = sorted(self.materials, key=lambda n: n.encode("utf-8"))
        for name in names:
            calls = self._read_call(name, "read_source")
            if calls:
                return calls
        return None

    def _phase_reenter(self):
        m = self.mem
        if m.wwaw is None:
            return [self._call("what_am_i_working_with", {}, "wwaw")]
        if not m.wwaw["complete"]:
            return [self._call("what_am_i_working_with", dict(m.wwaw["next"]), "wwaw")]
        # Read each listed entry fully by its handle and identify it against the goals.
        for e in m.wwaw["entries"]:
            h = e.get("entry")
            if not isinstance(h, str):
                continue
            calls = self._read_call(h, "read_entry")
            if calls:
                return calls
        if not m.reentered:
            self._identify()
            m.reentered = True
        return None

    def _identify(self):
        """Match re-entry's entries (bytes verified by reading) to goals by label and content."""
        m = self.mem
        seen = {}
        for e in m.wwaw["entries"]:
            h, label = e.get("entry"), e.get("label")
            st = m.reads.get(h)
            data = bytes(st["buf"]) if st and st["complete"] else None
            goal = next((g for g in self.goals if g.label == label), None)
            if goal is None:
                self.anomaly("reentry.unknown-entry", e)
                continue
            if label in seen:
                self.anomaly("reentry.goal-recorded-twice", {"label": label, "entries": [seen[label], e.get("id")]})
                continue
            seen[label] = e.get("id")
            if data is None:
                self.anomaly("reentry.entry-unread", e)
                state = "unknown"
            elif data == goal.data or (not goal.artifact and data == goal.text.encode("utf-8")):
                state = "final"
            elif goal.draft is not None and data == goal.draft.encode("utf-8"):
                state = "draft"
            else:
                self.anomaly("reentry.entry-bytes", {"label": label, "got": data[:200]})
                state = "unknown"
            m.entries[label] = {"id": e.get("id"), "handle": h, "version": _version_of(h), "state": state,
                                "kind": e.get("kind")}
        self.event("re-entry identified entries", entries={k: v["state"] for k, v in m.entries.items()})

    def _phase_work(self):
        m = self.mem
        calls = []
        for g in self.goals:
            if len(calls) >= self.calls_per_turn:
                break
            if g.label in m.entries:
                continue
            if g.bad_first and g.label not in m.bad_done:
                over, _reason = g.bad_first
                inp = g.input(final=g.draft is None)
                inp.update(over)
                calls.append(self._call(g.kind, inp, "record_bad", goal=g.label))
                m.bad_done.add(g.label)
                break   # the refusal decides the next step
            calls.append(self._call(g.kind, g.input(final=g.draft is None), "record", goal=g.label))
        if calls:
            for c in calls:
                if c["purpose"] == "record":
                    m.entries[c["goal"]] = {"id": None, "handle": None, "version": None, "state": "pending",
                                            "kind": c["tool"]}
            return calls
        for g in self.goals:
            if len(calls) >= self.calls_per_turn:
                break
            e = m.entries.get(g.label)
            if e and e["state"] == "draft" and e["handle"]:
                calls.append(self._call("replace", g.input(final=True, entry=e["handle"]), "replace", goal=g.label))
                e["state"] = "replacing"
        if calls:
            return calls
        if any(e["state"] in ("pending", "replacing") for e in m.entries.values()):
            self.anomaly("policy.waiting-without-calls", m.entries)
        return None

    def _phase_prepare(self):
        if self.mem.prepared is not None:
            return None
        return [self._call("prepare", {}, "prepare")]

    def _phase_inspect(self):
        p = self.mem.prepared
        if not p:
            return None
        for view in ("rendering", "selection"):
            src = p.get(view, {}).get("source") if isinstance(p.get(view), dict) else None
            if not isinstance(src, str):
                self.anomaly("prepare.view-source", p)
                return None
            calls = self._read_call(src, "read_view")
            if calls:
                return calls
        self._check_views()
        return None

    def _phase_dry(self):
        if self.mem.dry_done or not self.mem.prepared:
            return None
        self.mem.dry_done = True
        return [self._call("submit", {"prepared": self.mem.prepared["prepared"], "confirm": False}, "dry")]

    def _phase_submit(self):
        if self.mem.submitted or not self.mem.prepared:
            return None
        self.mem.submitted = True
        self.mem.ended = True
        return [self._call("submit", {"prepared": self.mem.prepared["prepared"], "confirm": True}, "submit")]

    # -- reply handlers ----------------------------------------------------------
    def _reply_read_source(self, call, env, page_text, ex):
        self._take_page(call, env, page_text, verify=self.sources.get(call["source"]))

    def _reply_read_entry(self, call, env, page_text, ex):
        self._take_page(call, env, page_text, verify=None)

    def _reply_read_view(self, call, env, page_text, ex):
        self._take_page(call, env, page_text, verify=None)

    def _take_page(self, call, env, page_text, verify):
        src = call["source"]
        st = self.mem.reads.get(src)
        if st is None:      # memory was discarded since the call was made
            return
        d = env.get("data") if isinstance(env.get("data"), dict) else {}
        if env.get("outcome") != "completed":
            self.anomaly("read.refused", {"source": src, "reason": env.get("reason")})
            st["complete"] = True
            return
        rng = d.get("range")
        if d.get("source") != src or not (isinstance(rng, list) and len(rng) == 2):
            self.anomaly("read.data", {"source": src, "data": _short_input(d)})
            st["complete"] = True
            return
        start, end = rng
        if start != len(st["buf"]):
            self.anomaly("read.range-continuity", {"source": src, "expected_start": len(st["buf"]), "range": rng})
        if "base64" in d:
            try:
                page = base64.b64decode(d["base64"], validate=True)
            except (ValueError, TypeError):
                self.anomaly("read.base64", src)
                page = b""
        elif page_text is not None:
            page = page_text.encode("utf-8")
            if "text" in d:
                self.anomaly("read.text-twice", src)
        else:
            page = (d.get("text") or "").encode("utf-8")
            if page.strip():
                self.anomaly("read.text-in-envelope-not-blank", {"source": src, "text": page[:80]})
        if len(page) != end - start and "base64" not in d:
            self.anomaly("read.page-size", {"source": src, "range": rng, "bytes": len(page)})
        st["buf"] += page
        st["pages"] += 1
        complete = d.get("complete")
        nxt = [n for n in env.get("next") or [] if isinstance(n, dict) and n.get("tool") == "read"]
        if verify is not None:
            size = len(verify)
            want_end = aw.page_end(verify, start)
            if (start, end) != (start, want_end):
                self.anomaly("read.page-boundary", {"source": src, "range": rng, "expected_end": want_end})
            if verify[start:end] != page:
                self.anomaly("read.bytes", {"source": src, "range": rng})
            if d.get("size") != size:
                self.anomaly("read.size", {"source": src, "got": d.get("size"), "expected": size})
            if d.get("cite") != {"source": src, "start": start, "end": end}:
                self.anomaly("read.cite", {"source": src, "cite": d.get("cite"), "range": rng})
            if d.get("lines") != aw.lines_span(verify, start, end):
                self.anomaly("read.lines", {"source": src, "lines": d.get("lines"),
                                            "expected": aw.lines_span(verify, start, end)})
            if complete is not (end == size):
                self.anomaly("read.complete", {"source": src, "complete": complete, "range": rng, "size": size})
        if complete is True:
            if nxt:
                self.anomaly("read.next-when-complete", {"source": src, "next": nxt})
            st["complete"] = True
            if verify is not None and bytes(st["buf"]) != verify:
                self.anomaly("read.reassembled", {"source": src})
            self.event("read complete", source=src, pages=st["pages"], bytes=len(st["buf"]))
        elif complete is False:
            if not nxt:
                self.anomaly("read.incomplete-without-next", {"source": src, "range": rng})
                st["complete"] = True
            else:
                inp = nxt[0].get("input")
                if not isinstance(inp, dict) or inp.get("source") != src:
                    self.anomaly("read.next-input", nxt[0])
                    st["complete"] = True
                else:
                    st["next"] = inp
        else:
            self.anomaly("read.complete-type", {"source": src, "complete": complete})
            st["complete"] = True

    def _reply_list(self, call, env, page_text, ex):
        d = env.get("data") if isinstance(env.get("data"), dict) else {}
        if env.get("outcome") != "completed":
            self.anomaly("list.refused", env.get("reason"))
            self.mem.listed = {"complete": True}
            return
        prev = self.mem.listed or {"materials": []}
        mats = prev["materials"] + list(d.get("materials") or [])
        complete = d.get("complete")
        nxt = [n for n in env.get("next") or [] if isinstance(n, dict) and n.get("tool") == "list"]
        self.mem.listed = {"materials": mats, "complete": complete is True or not nxt,
                           "next": nxt[0].get("input") if nxt else None}
        if complete is True or not nxt:
            want = [{"source": n, "size": len(b), "lines": _lines(b)}
                    for n, b in sorted(self.materials.items(), key=lambda kv: kv[0].encode("utf-8"))]
            if mats != want:
                self.anomaly("list.index", {"got": mats[:20], "expected": want[:20]})
            if d.get("total") != len(want):
                self.anomaly("list.total", {"got": d.get("total"), "expected": len(want)})

    def _reply_wwaw(self, call, env, page_text, ex):
        m = self.mem
        d = env.get("data") if isinstance(env.get("data"), dict) else {}
        if env.get("outcome") != "completed":
            self.anomaly("reentry.refused", {"reason": env.get("reason")})
            if env.get("reason") == "stale_view":
                m.wwaw = None
            else:
                m.wwaw = {"entries": [], "complete": True, "next": None}
            return
        first = m.wwaw is None
        if first:
            self._check_wwaw_first(d, ex)
            m.wwaw = {"entries": [], "complete": False, "next": None, "revision": d.get("revision")}
        page = d.get("page") or {}
        if page.get("bound_revision") != m.wwaw.get("revision"):
            self.anomaly("reentry.page-revision", {"bound": page.get("bound_revision"), "first": m.wwaw.get("revision")})
        ents = d.get("entries") or []
        if page.get("returned") != len(ents):
            self.anomaly("reentry.page-returned", {"returned": page.get("returned"), "entries": len(ents)})
        m.wwaw["entries"] += ents
        nxt = [n for n in env.get("next") or [] if isinstance(n, dict) and n.get("tool") == "what_am_i_working_with"]
        if page.get("complete") is True:
            if nxt:
                self.anomaly("reentry.next-when-complete", nxt)
            m.wwaw["complete"] = True
            if page.get("total") != len(m.wwaw["entries"]):
                self.anomaly("reentry.total", {"total": page.get("total"), "collected": len(m.wwaw["entries"])})
        elif nxt and isinstance(nxt[0].get("input"), dict):
            m.wwaw["next"] = nxt[0]["input"]
        else:
            self.anomaly("reentry.incomplete-without-next", page)
            m.wwaw["complete"] = True
        if not any(isinstance(n, dict) and n.get("tool") == "list" for n in env.get("next") or []) and first:
            self.anomaly("reentry.next-list", env.get("next"))

    def _check_wwaw_first(self, d, ex):
        for k in ("audit", "condition", "sealed_by", "revision", "run", "allowances", "notices_used", "question",
                  "materials", "entries", "receipts", "latest_refusals", "gaps", "page"):
            if k not in d:
                self.anomaly("reentry.member", k)
        if list(d)[:14] != ["audit", "condition", "sealed_by", "revision", "run", "allowances", "notices_used",
                            "question", "materials", "entries", "receipts", "latest_refusals", "gaps", "page"]:
            self.anomaly("reentry.member-order", list(d))
        if d.get("condition") != "open" or d.get("sealed_by") is not None:
            self.anomaly("reentry.condition", {"condition": d.get("condition"), "sealed_by": d.get("sealed_by")})
        run = d.get("run") or {}
        if not isinstance(run.get("number"), int) or run.get("continuing") is not (run.get("number", 0) > 1) \
                or run.get("number", 0) < self.conversations:
            self.anomaly("reentry.run", {"run": run, "conversations": self.conversations})
        if d.get("question") != {"source": "question", "size": len(self.question), "lines": _lines(self.question)}:
            self.anomaly("reentry.question", d.get("question"))
        if d.get("materials") != {"count": len(self.materials), "bytes": sum(len(b) for b in self.materials.values())}:
            self.anomaly("reentry.materials", d.get("materials"))
        want = self.expected_allowances(ex)
        if want is not None and d.get("allowances") != want:
            self.anomaly("reentry.allowances", {"expected": want, "got": d.get("allowances")})
        nu = d.get("notices_used") or {}
        if self.reminders_seen and nu.get("reminder") is not True:
            self.anomaly("reentry.notices-used.reminder", nu)
        if self.notices_seen and nu.get("near_limit") is not True:
            self.anomaly("reentry.notices-used.near-limit", nu)
        for r in d.get("receipts") or []:
            c = self.issued.get(r.get("tool_use_id")) if isinstance(r, dict) else None
            if c is None or c["tool"] != r.get("tool"):
                self.anomaly("reentry.receipt-attribution", r)
        for r in d.get("latest_refusals") or []:
            c = self.issued.get(r.get("tool_use_id")) if isinstance(r, dict) else None
            if c is None or c["tool"] != r.get("tool"):
                self.anomaly("reentry.refusal-attribution", r)
                continue
            seen = [x for x in self.replies if x[0] == r.get("tool_use_id")]
            if seen and (seen[-1][2], seen[-1][3]) != (r.get("outcome"), r.get("reason")):
                self.anomaly("reentry.refusal-reason", {"receipt": r, "witnessed": seen[-1]})
        if not isinstance(d.get("gaps"), list) or d.get("gaps"):
            self.event("re-entry reported gaps", gaps=d.get("gaps"))

    def _reply_record(self, call, env, page_text, ex):
        e = self.mem.entries.get(call["goal"])
        d = env.get("data") if isinstance(env.get("data"), dict) else {}
        if env.get("outcome") != "completed":
            self.anomaly("record.refused", {"goal": call["goal"], "reason": env.get("reason"),
                                            "message": env.get("message")})
            if e is not None and e["state"] == "pending":
                del self.mem.entries[call["goal"]]
            if env.get("reason") == "authoring_ended":
                self.mem.ended = True
            return
        self.mutations_done += 1
        if (env.get("effects") or {}).get("answer") != "changed":
            self.anomaly("record.effects", env.get("effects"))
        g = next(x for x in self.goals if x.label == call["goal"])
        if d.get("version") != 1 or not _handle_ok(d.get("entry"), d.get("id"), 1):
            self.anomaly("record.handle", {"entry": d.get("entry"), "id": d.get("id"), "version": d.get("version")})
        if not g.artifact:
            try:
                want = [aw.record_citation(c, self.sources) for c in g.citations]
            except aw.CitationDefect as exc:
                want = None
                self.anomaly("record.witness-refuses", str(exc))
            if want is not None and d.get("citations") != want:
                self.anomaly("record.citations", {"goal": g.label, "expected": want, "got": d.get("citations")})
        if e is not None:
            e.update({"id": d.get("id"), "handle": d.get("entry"), "version": d.get("version"),
                      "state": "draft" if (g.draft is not None) else "final"})

    def _reply_record_bad(self, call, env, page_text, ex):
        g = next(x for x in self.goals if x.label == call["goal"])
        reason = g.bad_first[1]
        if env.get("outcome") != "refused" or env.get("reason") != reason:
            self.anomaly("record.expected-refusal", {"goal": g.label, "expected": reason,
                                                     "got": [env.get("outcome"), env.get("reason")]})
            if env.get("outcome") == "completed":
                self.mutations_done += 1
        elif (env.get("effects") or {}).get("answer") != "unchanged":
            self.anomaly("record.refusal-effects", env.get("effects"))

    def _reply_replace(self, call, env, page_text, ex):
        e = self.mem.entries.get(call["goal"])
        d = env.get("data") if isinstance(env.get("data"), dict) else {}
        if env.get("outcome") != "completed":
            self.anomaly("replace.refused", {"goal": call["goal"], "reason": env.get("reason")})
            if env.get("reason") == "stale_entry":
                self.mem.queue = ["reenter"] + self._work_queue()
                self.mem.wwaw = None
                self.mem.reentered = False
            return
        self.mutations_done += 1
        if e is not None:
            if d.get("version") != (e.get("version") or 0) + 1 or not _handle_ok(d.get("entry"), e.get("id"), d.get("version")):
                self.anomaly("replace.handle", {"before": e, "data": _short_input(d)})
            e.update({"handle": d.get("entry"), "version": d.get("version"), "state": "final"})

    def _reply_prepare(self, call, env, page_text, ex):
        d = env.get("data") if isinstance(env.get("data"), dict) else {}
        if env.get("outcome") != "completed":
            self.anomaly("prepare.refused", {"reason": env.get("reason")})
            self.mem.ended = True
            return
        if "sealer" in json.dumps(d):
            self.anomaly("prepare.claims-sealer", d)
        self.mem.prepared = d
        tools = FAMILY_TOOLS[self.family] + ["record_artifact"]
        if list((d.get("counts") or {}).keys()) != tools:
            self.anomaly("prepare.counts-keys", d.get("counts"))
        want_counts = {t: 0 for t in tools}
        for label, e in self.mem.entries.items():
            g = next(x for x in self.goals if x.label == label)
            want_counts[g.kind] += 1
        if d.get("counts") != want_counts:
            self.anomaly("prepare.counts", {"expected": want_counts, "got": d.get("counts")})
        if self.mem.entries:
            # INTERFACE 7.6: one section_unfilled per expected section with no entry, in tools order.
            expected_sections = [t for t in FAMILY_TOOLS[self.family]
                                 if not (self.family == "comparison" and t == "record_observation")]
            want_notices = [t for t in expected_sections if want_counts[t] == 0]
            got = [n.get("tool") for n in d.get("notices") or [] if isinstance(n, dict)]
            if got != want_notices or any(n.get("reason") != "section_unfilled" for n in d.get("notices") or []):
                self.anomaly("prepare.notices", {"expected": want_notices, "got": d.get("notices")})
        else:
            if [n.get("reason") for n in d.get("notices") or [] if isinstance(n, dict)] != ["answer_empty"]:
                self.anomaly("prepare.notices-empty", d.get("notices"))
        if d.get("entry_count") != len(self.mem.entries):
            self.anomaly("prepare.entry-count", {"expected": len(self.mem.entries), "got": d.get("entry_count")})

    def expected_selection(self, revision):
        """The witnessed selection as answer_witness entries, in order of first creation."""
        rows = []
        for label, e in self.mem.entries.items():
            g = next(x for x in self.goals if x.label == label)
            n = int(e["id"][1:]) if isinstance(e.get("id"), str) and e["id"][1:].isdigit() else 0
            if g.artifact:
                ent = aw.Entry(e["id"], e["version"], "record_artifact", g.label, g.data,
                               encoding="binary" if g.artifact == "base64" else "utf-8")
            else:
                ent = aw.Entry(e["id"], e["version"], g.kind, g.label, g.text.encode("utf-8"),
                               citations=[aw.record_citation(c, self.sources) for c in g.citations])
            rows.append((n, ent))
        return [ent for _, ent in sorted(rows, key=lambda r: r[0])]

    def _check_views(self):
        p = self.mem.prepared
        rev = p.get("revision")
        ents = self.expected_selection(rev)
        want_json = aw.answer_json(rev, ents)
        want_md = aw.render(ents)
        got_md = bytes(self.mem.reads[p["rendering"]["source"]]["buf"])
        got_json = bytes(self.mem.reads[p["selection"]["source"]]["buf"])
        if got_json != want_json:
            self.anomaly("view.selection", {"expected": want_json[:600], "got": got_json[:600]})
        if want_md is not None and got_md != want_md:
            self.anomaly("view.rendering", {"expected": want_md[:600], "got": got_md[:600]})
        if p["rendering"].get("size") != len(got_md) or p["selection"].get("size") != len(got_json):
            self.anomaly("view.sizes", {"prepare": [p["rendering"], p["selection"]], "read": [len(got_md), len(got_json)]})
        # The return must contain each goal exactly once (ACCEPTANCE "The scripted tier"): count
        # the labels in the selection bytes Stewart produced, not in the auditor's memory.
        try:
            labels = [x.get("label") for x in json.loads(got_json.decode("utf-8")).get("entries", [])]
        except (ValueError, AttributeError, UnicodeDecodeError):
            labels = []
            self.anomaly("view.selection-json", got_json[:300])
        for g in self.goals:
            if labels.count(g.label) != 1:
                self.anomaly("view.goal-count", {"goal": g.label, "count": labels.count(g.label)})
        for extra in sorted(set(labels) - {g.label for g in self.goals}):
            self.anomaly("view.unknown-entry", extra)
        self.final_selection = {"revision": rev, "answer_json_sha256": hashlib.sha256(got_json).hexdigest(),
                                "answer_md_sha256": hashlib.sha256(got_md).hexdigest(), "labels": labels}

    def _reply_dry(self, call, env, page_text, ex):
        d = env.get("data") if isinstance(env.get("data"), dict) else {}
        if env.get("outcome") != "completed" or d.get("dry_run") is not True:
            self.anomaly("submit.dry-run", {"outcome": env.get("outcome"), "data": d})
        if (env.get("effects") or {}).get("seal") != "none":
            self.anomaly("submit.dry-run-effects", env.get("effects"))

    def _reply_submit(self, call, env, page_text, ex):
        # Only reached when Stewart sent the result of a confirmed submit, which it should not
        # (7.6: "After a confirmed submit the run delivers and ends, so its reply is recorded
        # but not sent"), unless the submit was refused.
        if env.get("outcome") == "completed":
            self.anomaly("submit.result-sent", env)
        self.sealed = env.get("data")
        self.mem.ended = True


# ---------------------------------------------------------------------------
# Tool reply envelope rules (INTERFACE 1.3, 1.4, 1.5, 7.1), shared with run_support.
# ---------------------------------------------------------------------------

def tool_envelope_problems(env, tool, raw_text=None, forbidden=()):
    out = []
    if not isinstance(env, dict):
        return ["not an object"]
    keys = list(env)
    allowed = [k for k in ENVELOPE_ORDER if k != "retained"]
    unknown = [k for k in keys if k not in allowed]
    if unknown:
        out.append("unknown keys %s" % unknown)
    known = [k for k in keys if k in allowed]
    if known != sorted(known, key=allowed.index):
        out.append("key order %s" % keys)
    if env.get("schema") != REPLY_SCHEMA:
        out.append("schema %r" % env.get("schema"))
    if env.get("operation") != tool:
        out.append("operation %r for tool %r" % (env.get("operation"), tool))
    oc = env.get("outcome")
    if oc not in OUTCOMES:
        out.append("outcome %r" % oc)
    bad = oc in ("refused", "failed")
    if bad != isinstance(env.get("reason"), str) or (not bad and "reason" in env):
        out.append("reason %r with outcome %r" % (env.get("reason"), oc))
    if bad != (isinstance(env.get("message"), str) and env.get("message", "").strip() != ""):
        out.append("message with outcome %r" % oc)
    eff = env.get("effects")
    if not isinstance(eff, dict):
        out.append("effects missing")
    else:
        want = tool_effect_keys(tool)
        if want is not None and set(eff) - {"diagnostic"} != set(want):
            out.append("effect keys %s, expected %s" % (sorted(eff), list(want)))
        for k, v in eff.items():
            if k not in EFFECT_VALUES or v not in EFFECT_VALUES[k]:
                out.append("effects.%s = %r" % (k, v))
    causes_due = oc == "failed" or (isinstance(eff, dict) and eff.get("diagnostic") == "reported_only")
    if causes_due != isinstance(env.get("causes"), list):
        out.append("causes %r with outcome %r" % (env.get("causes"), oc))
    nxt = env.get("next")
    if not isinstance(nxt, list):
        out.append("next missing")
    else:
        for n in nxt:
            if not (isinstance(n, dict) and set(n) == {"tool", "input", "why"} and isinstance(n.get("tool"), str)
                    and isinstance(n.get("input"), dict) and isinstance(n.get("why"), str) and n["why"].strip()):
                out.append("next item %r" % (n,))
    if oc == "completed" and not isinstance(env.get("data"), dict):
        out.append("data missing on a completed reply")
    if raw_text is not None:
        if not is_compact_json(raw_text):
            out.append("not compact")
    for v in _scan_strings(env):
        for f in forbidden:
            if f in v:
                out.append("discloses %r" % f)
    return out


def _scan_strings(obj, key=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in EXEMPT_KEYS:
                continue
            for s in _scan_strings(v, k):
                yield s
        for k in obj:
            yield k
    elif isinstance(obj, list):
        for v in obj:
            for s in _scan_strings(v, key):
                yield s
    elif isinstance(obj, str):
        yield obj


def _btype(node):
    if node is None or node.kind != "object":
        return None
    t = node.get("type")
    try:
        return t.value() if t is not None else None
    except ValueError:
        return None


def _sval(node):
    try:
        v = node.value() if node is not None else None
    except ValueError:
        return None
    return v if isinstance(v, str) else None


def _lines(data):
    n = data.count(b"\n")
    return n + (1 if data and not data.endswith(b"\n") else 0)


def _version_of(handle):
    try:
        return int(handle.split(".")[1][1:])
    except (AttributeError, IndexError, ValueError):
        return None


def _handle_ok(handle, eid, version):
    if not isinstance(handle, str) or not isinstance(eid, str):
        return False
    parts = handle.split(".")
    return (len(parts) == 3 and parts[0] == eid and parts[1] == "v%s" % version and len(parts[2]) == 6
            and all(c in "abcdefghijklmnopqrstuvwxyz234567" for c in parts[2]))


def _short_input(d):
    if not isinstance(d, dict):
        return d
    return {k: (short(v, 80) if isinstance(v, str) else v) for k, v in d.items()}


# ---------------------------------------------------------------------------
# Self-tests against mini_stewart, a small stand-in for the run loop (no binary).
# ---------------------------------------------------------------------------

def _scenario_material():
    long_q = ("Audit the reminder service.\n" + "background line\n" * 4500
              + "Essential: the answer must cover restarts.\n").encode("utf-8")
    mats = {"materials/a.py": b"def send(r):\n    deliver(r)\n    mark_sent(r)\n",
            "materials/notes/R1.txt": "R1. A reminder ID is sent at most once.\nrésumé\n".encode("utf-8")}
    return long_q, mats


def _goals(mats):
    a = mats["materials/a.py"]
    s = a.find(b"deliver(r)")
    return [
        Goal("account", "Restarts can duplicate a send.", kind="record_account", draft="Draft account.",
             citations=[{"source": "materials/notes/R1.txt", "quote": "at most once"}]),
        Goal("obs-1", "deliver precedes mark_sent.", citations=[{"source": "materials/a.py", "start": s, "end": s + 10}],
             bad_first=({"citations": [{"source": "materials/a.py", "start": s, "end": s + 10, "quote": "nope"}]},
                        "citation_invalid")),
        Goal("limit-1", "Only two files were supplied.\n", kind="record_limit"),
        Goal("trace", "send -> deliver -> mark\n", kind="record_artifact", artifact="text"),
        Goal("blob", kind="record_artifact", artifact="base64", data=b"\x00\x01\xfe\xff"),
    ]


def _run_scenario(faults=(), compact_after=(), kill_after=None, finish="submit", after_reminder="submit",
                  calls_per_turn=2, kill_after_reminder=False):
    import mini_stewart
    q, mats = _scenario_material()
    aud = ReactingAuditor(_goals(mats), question=q, materials=mats, compact_after=compact_after,
                          calls_per_turn=calls_per_turn, finish=finish, after_reminder=after_reminder,
                          forbidden=("/archive/root", "open-inquiry"))
    sim = mini_stewart.MiniStewart(aud, q, mats, faults=faults)
    endings = [sim.run(kill_after_mutations=kill_after, kill_after_reminder=kill_after_reminder)]
    if endings[-1] == "killed":
        endings.append(sim.run())
    return aud, sim, endings


@selftest
def reacting_auditor_selftests():
    out = []

    def clean(label, aud, sim, endings, want_ending="sealed"):
        out.append(("auditor.%s.ending" % label, endings[-1] == want_ending, endings))
        out.append(("auditor.%s.no-anomalies" % label, not aud.anomalies, aud.anomalies[:5]))
        if want_ending == "sealed":
            labels = [e["label"] for e in sim.current()]
            out.append(("auditor.%s.each-goal-once" % label,
                        sorted(labels) == sorted(g.label for g in aud.goals), labels))
            out.append(("auditor.%s.views-verified" % label, aud.final_selection is not None
                        and aud.final_selection["answer_json_sha256"] == hashlib.sha256(sim.sealed["selection"]).hexdigest()))

    aud, sim, endings = _run_scenario()
    clean("plain", aud, sim, endings)
    out.append(("auditor.plain.read-long-question", any(e["event"] == "read complete" and e["source"] == "question"
                                                        and e["pages"] >= 2 for e in aud.events)))
    out.append(("auditor.plain.refusal-then-record", ("citation_invalid" in [r[3] for r in aud.replies])))
    aud, sim, endings = _run_scenario(compact_after=(2, 5), calls_per_turn=1)
    clean("compaction", aud, sim, endings)
    out.append(("auditor.compaction.happened", len(aud.compactions) == 2, aud.compactions))
    aud, sim, endings = _run_scenario(kill_after=3)
    clean("continuation", aud, sim, endings)
    out.append(("auditor.continuation.two-conversations", aud.conversations == 2 and endings[0] == "killed"))
    aud, sim, endings = _run_scenario(finish="ordinary", after_reminder="end")
    clean("ordinary", aud, sim, endings, want_ending="ended_unsubmitted")
    out.append(("auditor.ordinary.one-reminder", aud.reminders_seen == 1))
    aud, sim, endings = _run_scenario(finish="ordinary", after_reminder="submit")
    clean("reminder-then-submit", aud, sim, endings)

    # Firing controls: each simulated sabotage must produce the named anomaly.
    def fires(label, check_prefix, **kw):
        aud, sim, endings = _run_scenario(**kw)
        hit = [a for a in aud.anomalies if a["check"].startswith(check_prefix)]
        out.append(("auditor.control.%s" % label, bool(hit), {"anomalies": [a["check"] for a in aud.anomalies][:10]}))

    # reentry_omit_entry: the omitted entry is added again, and the duplicate is caught.
    fires("reentry-omission-duplicates", "view.goal-count", faults=("omit_last_in_reentry",), compact_after=(4,),
          calls_per_turn=1)
    # reentry_placement_allowances: allowances that restart with the placement.
    fires("placement-allowances", "reentry.allowances", faults=("placement_allowances",), kill_after=3)
    # read_truncate_silently: a page that claims completeness early.
    fires("truncated-read", "read.", faults=("truncate_silently",))
    # reset_notice_allowance: the reminder offered again in a continuing placement.
    fires("reminder-reset", "notice.reminder-repeated", faults=("reset_reminder",), finish="ordinary",
          after_reminder="submit", kill_after_reminder=True)
    # Its baseline: the same continuation without the fault ends ordinarily, reminder used once.
    aud, sim, endings = _run_scenario(finish="ordinary", after_reminder="submit", kill_after_reminder=True)
    clean("reminder-continuation", aud, sim, endings, want_ending="ended_unsubmitted")
    out.append(("auditor.reminder-continuation.once", aud.reminders_seen == 1 and endings[0] == "killed", endings))
    return out
