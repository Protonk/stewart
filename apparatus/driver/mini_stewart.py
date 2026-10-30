# -*- coding: utf-8 -*-
"""A deliberately small stand-in for Stewart's run loop and auditor tools.

It exists only to self-test the reacting auditor's policy without a binary:
compaction, kill and continuation, the reminder, paging and the prepared views.
It follows INTERFACE 6.2-7.6 loosely and simply; it is not a reference
implementation, says nothing about Stewart and is never run against a binary.
Its `faults` simulate a few sabotage controls of Appendix C.2 so the self-test
can show that the auditor's checks fire.
"""
from __future__ import annotations

import base64
import hashlib
import json

import answer_witness as aw
import fake_provider as fp
import rawjson
from driver_core import (API_VERSION, CONTINUATION, FAMILY_TOOLS, REMINDER, REPLY_SCHEMA, expected_system_bytes,
                         expected_tools)


def _j(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _text_block(t):
    return b'{"type":"text","text":' + aw.pinned_json_string(t).encode("utf-8") + b"}"


class _Prov:
    def __init__(self):
        self.exchanges, self.charge_overrides, self.extra_charges = [], {}, {}


def http_sender(port, key, host=None):
    """Send a request body to this run's own fake listener as INTERFACE 6.1 prescribes and return
    the response body (the stand-in's transport for harness self-tests)."""
    def send(body, extra_header=None):
        c = fp.own_connect((fp.LOOPBACK, port))
        try:
            req = fp.stewart_request(host or "127.0.0.1:%d" % port, key, body)
            if extra_header:
                req = req.replace(b"\r\nconnection: close", b"\r\n" + extra_header + b"\r\nconnection: close")
            c.sendall(req)
            status, _, rbody, complete, _ = fp.read_response(c)
        finally:
            c.close()
        return rbody if status == 200 and complete else None
    return send


class MiniStewart:
    def __init__(self, auditor, question, materials, family="open-inquiry", limits=None, faults=(), send=None,
                 ledger=None, model="claude-opus-5-5"):
        self.auditor, self.question, self.materials = auditor, question, dict(materials)
        self.family, self.model = family, model
        self.limits = limits or {"turns": 200, "input_tokens": 20000000, "output_tokens": 400000}
        self.faults = set(faults)
        self.send = send
        self.provider = ledger if ledger is not None else _Prov()
        auditor.provider = self.provider
        auditor.limits = self.limits
        tools = expected_tools(family)
        if "extra_tool" in self.faults:
            tools = tools + [{"name": "shell", "description": "Run a command.",
                              "input_schema": {"type": "object", "properties": {}, "required": [],
                                               "additionalProperties": False}}]
        self.prefix = (b'{"model":' + fp.jstr(model) + b',"max_tokens":16000,"system":' + expected_system_bytes(family)
                       + b',"tools":' + rawjson.compact(tools) + b',"messages":[')
        self.entries = []
        self.revision = 0
        self.preps = []
        self.notices_used = {"reminder": False, "near_limit": False}
        self.receipts = []
        self.placement = 0
        self.mutations = 0
        self.sealed = None
        self.placement_first_exchange = 1

    def sources(self):
        s = dict(self.materials)
        s["question"] = self.question
        return s

    def handle(self, e):
        return "%s.v%d.%s" % (e["id"], e["version"], base64.b32encode(hashlib.sha256(
            ("%s.%d" % (e["id"], e["version"])).encode()).digest()).decode().lower()[:6])

    def current(self):
        return [e for e in self.entries if not e["deleted"]]

    # -- the run loop ----------------------------------------------------------
    def run(self, kill_after_mutations=None, kill_after_reminder=False):
        self.placement += 1
        self.placement_first_exchange = len(self.provider.exchanges) + 1
        first = [_text_block(self.question.decode("utf-8"))]
        if self.placement > 1:
            first.append(_text_block(CONTINUATION))
        msgs = [b'{"role":"user","content":[' + b",".join(first) + b"]}"]
        reminder_now = False
        if "reset_reminder" in self.faults and self.placement > 1:
            self.notices_used["reminder"] = False
        dropped = False
        while True:
            body = self.prefix + b",".join(msgs) + b"]}"
            if "body_whitespace" in self.faults:
                body = body.replace(b'"messages":[', b'"messages": [', 1)
            if self.send is None:
                ex = fp.Exchange(0, "sim", None, None, 0.0)
                ex.n = len(self.provider.exchanges) + 1
                ex.body, ex.raw = body, body
                self.provider.exchanges.append(ex)
                step = self.auditor(ex)
                ex.step, ex.charge = step, step.charge(ex)
                rbody = step.body(ex)
            else:
                rbody = self.send(body, b"x-extra: 1" if "extra_header" in self.faults else None)
                if rbody is None:
                    return "interrupted"
                ex = self.provider.exchanges[-1]
            node = rawjson.parse(rbody)
            content = node.get("content")
            stop_reason = node.get("stop_reason").value()
            assistant = b'{"role":"assistant","content":' + content.raw + b"}"
            if "drop_history" in self.faults and not dropped and len(msgs) > 2:
                dropped = True      # forget one earlier exchange: history is no longer append-only
                msgs = msgs[:1] + msgs[3:]
            msgs.append(assistant)
            results = []
            uses = [b for b in content.items if b.get("type") is not None and b.get("type").value() == "tool_use"]
            for blk in uses:
                results.append(self.execute(blk, ex))
                if self.sealed:
                    return "sealed"
                if kill_after_mutations is not None and self.mutations >= kill_after_mutations:
                    return "killed"
            if kill_after_reminder and reminder_now:
                return "killed"
            if stop_reason == "tool_use":
                msgs.append(b'{"role":"user","content":[' + b",".join(results) + b"]}")
                continue
            if not self.notices_used["reminder"]:
                self.notices_used["reminder"] = True
                reminder_now = True
                msgs.append(b'{"role":"user","content":[' + b",".join(results + [_text_block(REMINDER)]) + b"]}")
                continue
            return "ended_unsubmitted"

    # -- tools ------------------------------------------------------------------
    def execute(self, blk, ex):
        tid, name = blk.get("id").value(), blk.get("name").value()
        inp = json.loads(blk.get("input").raw.decode("utf-8"))
        fn = getattr(self, "tool_" + name, None)
        if fn is None and name.startswith("record_"):
            fn = self.tool_record
        env, page = fn(name, inp, ex, tid)
        content = [b'{"type":"text","text":' + aw.pinned_json_string(
            json.dumps(env, ensure_ascii=False, separators=(",", ":"))).encode("utf-8") + b"}"]
        if page is not None:
            content.append(_text_block(page))
        is_err = b"false" if env["outcome"] == "completed" else b"true"
        return (b'{"type":"tool_result","tool_use_id":' + _j(tid) + b',"content":[' + b",".join(content)
                + b'],"is_error":' + is_err + b"}")

    def env(self, tool, outcome="completed", data=None, reason=None, effects=None, next_=()):
        e = {"schema": REPLY_SCHEMA, "operation": tool, "outcome": outcome}
        if outcome != "completed":
            e["reason"], e["message"] = reason, "Refused: %s." % reason
        if effects is None:
            effects = {"raw_capture": "recorded"}
        e["effects"] = effects
        e["next"] = list(next_)
        if data is not None:
            e["data"] = data
        return e

    def tool_list(self, tool, inp, ex, tid):
        mats = [{"source": n, "size": len(b), "lines": _lines(b)}
                for n, b in sorted(self.materials.items(), key=lambda kv: kv[0].encode("utf-8"))]
        return self.env(tool, data={"materials": mats, "directories": ["materials"], "returned": len(mats),
                                    "total": len(mats), "complete": True}), None

    def _page(self, tool, src, data, start, kind, cite=True, extra=None, binary=False):
        if binary:   # 7.2: base64 pages of 49,152 bytes in data.base64
            end = min(len(data), start + aw.PAGE_BINARY)
            d = {"source": src, "kind": kind, "size": len(data), "range": [start, end], "lines": None,
                 "complete": end == len(data), "cite": None,
                 "base64": base64.b64encode(data[start:end]).decode("ascii")}
            if extra:
                d.update(extra)
            nxt = [] if end == len(data) else [{"tool": "read", "input": {"source": src, "start": end}, "why": "More."}]
            return self.env(tool, data=d, next_=nxt), None
        end = aw.page_end(data, start)
        if "truncate_silently" in self.faults and end < len(data):
            complete = True
        else:
            complete = end == len(data)
        page = data[start:end].decode("utf-8")
        d = {"source": src, "kind": kind, "size": len(data), "range": [start, end],
             "lines": aw.lines_span(data, start, end), "complete": complete,
             "cite": {"source": src, "start": start, "end": end} if cite else None}
        if extra:
            d.update(extra)
        blank = not page.strip()
        if blank:
            d["text"] = page
        nxt = [] if complete else [{"tool": "read", "input": {"source": src, "start": end}, "why": "Read the rest."}]
        return self.env(tool, data=d, next_=nxt), (None if blank else page)

    def tool_read(self, tool, inp, ex, tid):
        src, start = inp["source"], inp.get("start", 0)
        srcs = self.sources()
        if src in srcs:
            return self._page(tool, src, srcs[src], start, "question" if src == "question" else "material")
        for p in self.preps:
            for view in ("rendering", "selection"):
                if src == "%s/%s" % (p["handle"], view):
                    return self._page(tool, src, p[view], start, "view", cite=False)
        for e in self.entries:
            if self.handle(e) == src or any(src == h for h in e["old_handles"]):
                if src != self.handle(e):
                    return self.env(tool, "refused", reason="stale_entry", data={"current": self.handle(e)}), None
                return self._page(tool, src, e["data"], start, "entry", cite=False,
                                  extra={"entry": src, "id": e["id"], "version": e["version"],
                                         "entry_kind": e["kind"], "label": e["label"], "citations": e["citations"],
                                         **({"artifact_encoding": e["encoding"]} if e["kind"] == "record_artifact" else {})},
                                  binary=e["encoding"] == "binary")
        return self.env(tool, "refused", reason="source_unknown"), None

    def _mutated(self, tid, tool, action, target, e):
        self.revision += 1
        self.mutations += 1
        self.receipts.insert(0, {"run": self.placement, "tool_use_id": tid, "tool": tool, "action": action,
                                 "target": target, "entry": self.handle(e) if e else None, "revision": self.revision})

    def tool_record(self, tool, inp, ex, tid):
        cits = []
        for c in inp.get("citations", []):
            try:
                cits.append(aw.record_citation(c, self.sources()))
            except aw.CitationDefect as exc:
                return self.env(tool, "refused", reason=exc.reason, effects={"answer": "unchanged",
                                                                              "raw_capture": "recorded"}), None
        if tool == "record_artifact":
            data = base64.b64decode(inp["base64"]) if "base64" in inp else inp["text"].encode("utf-8")
            enc = "binary" if "base64" in inp else "utf-8"
        else:
            data, enc = inp.get("text", "").encode("utf-8"), None
        e = {"id": "e%d" % (len(self.entries) + 1), "version": 1, "kind": tool, "label": inp.get("label", ""),
             "data": data, "citations": cits, "encoding": enc, "deleted": False, "old_handles": []}
        self.entries.append(e)
        self._mutated(tid, tool, "add", None, e)
        return self.env(tool, data={"entry": self.handle(e), "id": e["id"], "version": 1, "revision": self.revision,
                                    "citations": cits, "notices": []},
                        effects={"answer": "changed", "raw_capture": "recorded"}), None

    def tool_replace(self, tool, inp, ex, tid):
        for e in self.entries:
            if self.handle(e) == inp["entry"]:
                old = self.handle(e)
                e["old_handles"].append(old)
                e["version"] += 1
                if e["kind"] == "record_artifact":
                    e["data"] = base64.b64decode(inp["base64"]) if "base64" in inp else inp["text"].encode("utf-8")
                else:
                    e["data"] = inp["text"].encode("utf-8")
                    e["citations"] = [aw.record_citation(c, self.sources()) for c in inp.get("citations", [])]
                e["label"] = inp["label"]
                self._mutated(tid, tool, "replace", old, e)
                return self.env(tool, data={"entry": self.handle(e), "id": e["id"], "version": e["version"],
                                            "revision": self.revision, "citations": e["citations"], "notices": []},
                                effects={"answer": "changed", "raw_capture": "recorded"}), None
        return self.env(tool, "refused", reason="stale_entry", effects={"answer": "unchanged", "raw_capture": "recorded"}), None

    def tool_what_am_i_working_with(self, tool, inp, ex, tid):
        cur = self.current()
        if "omit_last_in_reentry" in self.faults and cur:
            cur = cur[:-1]
        pos = 0
        if "page" in inp:
            pos = int(inp["page"].split(".")[1])
        page = cur[pos:pos + 64]
        ents = [{"id": e["id"], "entry": self.handle(e), "kind": e["kind"], "label": e["label"],
                 "encoding": e["encoding"], "size": len(e["data"]), "preview": None, "preview_complete": False,
                 "problem": None} for e in page]
        complete = pos + len(page) >= len(cur)
        pg = {"bound_revision": self.revision, "returned": len(ents), "total": len(cur), "complete": complete}
        nxt = [{"tool": "list", "input": {}, "why": "List the materials."}]
        if not complete:
            nxt.append({"tool": "what_am_i_working_with", "input": {"page": "pg.%d.aaaaaa" % (pos + 64)},
                        "why": "Next page."})
        if pos:
            return self.env(tool, data={"entries": ents, "page": pg}, next_=nxt), None
        first = 1 if "placement_allowances" in self.faults else None
        tot = fp.totals(self.provider.exchanges, upto=ex.n, overrides=None)
        if first:
            tot = fp.totals([x for x in self.provider.exchanges if x.n >= self.placement_first_exchange], upto=ex.n)
        d = {"audit": "aaaaaaaaaaaaaaaaa", "condition": "open", "sealed_by": None, "revision": self.revision,
             "run": {"number": self.placement, "continuing": self.placement > 1},
             "allowances": fp.allowances(tot, self.limits), "notices_used": dict(self.notices_used),
             "question": {"source": "question", "size": len(self.question), "lines": _lines(self.question)},
             "materials": {"count": len(self.materials), "bytes": sum(len(b) for b in self.materials.values())},
             "entries": ents, "receipts": self.receipts[:16], "latest_refusals": [], "gaps": [], "page": pg}
        return self.env(tool, data=d, next_=nxt), None

    def tool_prepare(self, tool, inp, ex, tid):
        ents = [aw.Entry(e["id"], e["version"], e["kind"], e["label"], e["data"], citations=e["citations"],
                         encoding=e["encoding"]) for e in self.current()]
        aj, md = aw.answer_json(self.revision, ents), aw.render(ents)
        h = "ap%d.aaaaaa" % (len(self.preps) + 1)
        self.preps.append({"handle": h, "rendering": md, "selection": aj, "revision": self.revision})
        tools = FAMILY_TOOLS[self.family] + ["record_artifact"]
        counts = {t: sum(1 for e in self.current() if e["kind"] == t) for t in tools}
        expected = [t for t in FAMILY_TOOLS[self.family] if not (self.family == "comparison" and t == "record_observation")]
        notices = ([{"reason": "section_unfilled", "tool": t, "message": "No %s entries are recorded." % t}
                    for t in expected if counts[t] == 0] if ents else
                   [{"reason": "answer_empty", "message": "No answer entries are recorded."}])
        return self.env(tool, data={"prepared": h, "revision": self.revision, "entry_count": len(ents), "counts": counts,
                                    "notices": notices, "rendering": {"source": h + "/rendering", "size": len(md)},
                                    "selection": {"source": h + "/selection", "size": len(aj)}}), None

    def tool_submit(self, tool, inp, ex, tid):
        p = next(x for x in self.preps if x["handle"] == inp["prepared"])
        if not inp.get("confirm"):
            return self.env(tool, data={"dry_run": True, "revision": p["revision"], "entry_count": 0,
                                        "rendering": {"source": p["handle"] + "/rendering"}},
                            effects={"seal": "none", "raw_capture": "recorded"}), None
        self.sealed = {"prepared": p["handle"], "selection": p["selection"]}
        return self.env(tool, data={"seal": "seal.aaaaaa", "sealer": "auditor"},
                        effects={"seal": "recorded", "raw_capture": "recorded"}), None


def _lines(b):
    n = b.count(b"\n")
    return n + (1 if b and not b.endswith(b"\n") else 0)
