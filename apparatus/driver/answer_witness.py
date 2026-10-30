# -*- coding: utf-8 -*-
"""The driver's own expected bytes for what Stewart derives from a recorded answer.

From docs/QUESTION-FORMS.md ("The structured answer", "The rendering") and
docs/INTERFACE.md (7.2 read pages, 7.3 citations, 8.2 the return manifest):

- `record_citation` applies 7.3 to an auditor citation against the witness
  copies of the question body and materials, giving the recorded form with
  Stewart's additions under `stewart`, or the refusal reason;
- `answer_json`, `render` and `manifest` give the exact bytes of answer.json,
  answer.md and manifest.json for a witnessed selection;
- `page_end` / `read_pages` give the read page boundaries of 7.2.

Nothing here reads Stewart's records: these are what the delivered return and
the prepared views are compared against (ACCEPTANCE "The witness lives outside
Stewart").
"""
from __future__ import annotations

import hashlib
import os
import re

import rawjson
from driver_core import pinned_json_string, selftest

ANSWER_SCHEMA = "stewart.answer/1"
RETURN_SCHEMA = "stewart.return/1"
RENDERER = "stewart.render/1"
RENDER_FIRST_LINE = "Rendered by Stewart. Entry text is attributed to the auditor."
EMPTY_RENDERING = b"No answer entries recorded.\n"
PAGE_TEXT = 65536
PAGE_BINARY = 49152


def sha(data):
    return hashlib.sha256(data).hexdigest()


def is_boundary(data, i):
    return 0 <= i <= len(data) and (i == len(data) or (data[i] & 0xC0) != 0x80)


def line_of(data, offset):
    """1-based line of the byte at offset (LF counting, 3.3)."""
    return data.count(b"\n", 0, offset) + 1


def lines_span(data, start, end):
    return None if start >= end else [line_of(data, start), line_of(data, end - 1)]


def page_end(data, start, window=PAGE_TEXT):
    """7.2: the page ends at the source's end if within the window; otherwise just after the
    last LF in the window, or, with no LF, at the last UTF-8 boundary within it."""
    if len(data) - start <= window:
        return len(data)
    w = data[start:start + window]
    lf = w.rfind(b"\n")
    if lf >= 0:
        return start + lf + 1
    end = start + window
    while end > start and not is_boundary(data, end):
        end -= 1
    return end


def read_pages(data, start=0):
    pages = []
    while True:
        end = page_end(data, start)
        pages.append((start, end))
        if end >= len(data):
            return pages
        start = end


def occurrences(data, needle):
    """Every start of needle in data, overlapping ones included."""
    out, i = [], data.find(needle)
    while needle and i >= 0:
        out.append(i)
        i = data.find(needle, i + 1)
    return out


class CitationDefect(Exception):
    def __init__(self, reason, detail, occurrences=None):
        Exception.__init__(self, "%s: %s" % (reason, detail))
        self.reason, self.detail, self.occurrences = reason, detail, occurrences or []


def record_citation(c, sources):
    """The recorded citation (7.3) for the auditor operands c, with sources mapping
    'question' and 'materials/<name>' to their witness bytes; or CitationDefect."""
    if not isinstance(c, dict) or not isinstance(c.get("source"), str):
        raise CitationDefect("citation_invalid", "no source")
    extra = set(c) - {"source", "start", "end", "quote"}
    if extra:
        raise CitationDefect("citation_invalid", "unknown keys %s" % sorted(extra))
    src = c["source"]
    if src not in sources:
        raise CitationDefect("citation_invalid", "unknown source %r" % src)
    data = sources[src]
    out = {"source": src}
    has_range = "start" in c or "end" in c
    if has_range:
        s, e = c.get("start"), c.get("end")
        if not (isinstance(s, int) and isinstance(e, int)) or isinstance(s, bool) or isinstance(e, bool):
            raise CitationDefect("citation_invalid", "start and end are both required integers")
        if not (0 <= s < e <= len(data)) or not is_boundary(data, s) or not is_boundary(data, e):
            raise CitationDefect("citation_invalid", "range [%r, %r) is not a UTF-8 range in %s" % (s, e, src))
        out["start"], out["end"] = s, e
        if "quote" in c:
            if not isinstance(c["quote"], str) or c["quote"].encode("utf-8") != data[s:e]:
                raise CitationDefect("citation_invalid", "quote differs from bytes [%d, %d)" % (s, e))
            out["quote"] = c["quote"]
        rng = None
        span = (s, e)
    elif "quote" in c:
        q = c["quote"]
        if not isinstance(q, str) or not q:
            raise CitationDefect("citation_invalid", "empty quote")
        occ = occurrences(data, q.encode("utf-8"))
        if not occ:
            raise CitationDefect("quote_not_found", "quote not in %s" % src)
        if len(occ) > 1:
            raise CitationDefect("quote_ambiguous", "%d occurrences" % len(occ), occ[:8])
        out["quote"] = q
        rng = [occ[0], occ[0] + len(q.encode("utf-8"))]
        span = tuple(rng)
    else:
        raise CitationDefect("citation_invalid", "neither a range nor a quote")
    st = {"name": src, "sha256": sha(data)}
    if rng is not None:
        st["range"] = rng
    st["lines"] = lines_span(data, *span)
    out["stewart"] = st
    return out


def citation_bytes(c):
    """A recorded citation with keys in the pinned order (QUESTION-FORMS, INTERFACE 7.3)."""
    parts = [b'"source":' + pinned_json_string(c["source"]).encode("utf-8")]
    for k in ("start", "end"):
        if k in c:
            parts.append(b'"%s":%d' % (k.encode(), c[k]))
    if "quote" in c:
        parts.append(b'"quote":' + pinned_json_string(c["quote"]).encode("utf-8"))
    st = c["stewart"]
    sp = [b'"name":' + pinned_json_string(st["name"]).encode("utf-8"),
          b'"sha256":' + pinned_json_string(st["sha256"]).encode("utf-8")]
    if "range" in st:
        sp.append(b'"range":' + rawjson.compact(st["range"]))
    sp.append(b'"lines":' + (b"null" if st["lines"] is None else rawjson.compact(st["lines"])))
    parts.append(b'"stewart":{' + b",".join(sp) + b"}")
    return b"{" + b",".join(parts) + b"}"


class Entry:
    """One selected entry as the witness knows it. data is the payload bytes (UTF-8 text for
    a recorded entry or a text artifact; any bytes for a binary artifact)."""

    def __init__(self, id, version, kind, label, data, citations=None, encoding=None, unproduced=None,
                 sha256=None, size=None):
        self.id, self.version, self.kind, self.label = id, version, kind, label
        self.data = data
        self.citations = list(citations or [])
        self.encoding = encoding if kind == "record_artifact" else None
        self.unproduced = unproduced
        self._sha, self._size = sha256, size

    @property
    def sha256(self):
        return self._sha or sha(self.data)

    @property
    def size(self):
        return self._size if self._size is not None else len(self.data)

    @property
    def member(self):
        return "artifact-%s.bin" % self.id

    def line(self):
        def s(v):
            return pinned_json_string(v).encode("utf-8")
        head = (b'{"id":' + s(self.id) + b',"version":%d' % self.version + b',"kind":' + s(self.kind)
                + b',"label":' + s(self.label))
        if self.unproduced:
            return head + (b',"unproduced":{"sha256":' + s(self.sha256) + b',"size":%d' % self.size
                           + b',"failure":' + s(self.unproduced) + b"}}")
        if self.kind == "record_artifact":
            return head + (b',"encoding":' + s(self.encoding) + b',"member":' + s(self.member)
                           + b',"size":%d' % self.size + b',"sha256":' + s(self.sha256) + b"}")
        return head + (b',"text":' + s(self.data.decode("utf-8")) + b',"citations":['
                       + b",".join(citation_bytes(c) for c in self.citations) + b"]}")


def answer_json(revision, entries):
    if not entries:
        return b'{"schema":"%s","revision":%d,"entries":[]}\n' % (ANSWER_SCHEMA.encode(), revision)
    return (b'{"schema":"%s","revision":%d,"entries":[\n' % (ANSWER_SCHEMA.encode(), revision)
            + b",\n".join(e.line() for e in entries) + b"]}\n")


def kind_title(kind):
    if kind == "record_artifact":
        return "Artifact"
    k = kind[len("record_"):] if kind.startswith("record_") else kind
    k = k.replace("_", " ")
    return k[:1].upper() + k[1:]


def citation_text(c):
    st = c["stewart"]
    lines = st.get("lines")
    if lines is None:
        where = ""
    elif lines[0] == lines[1]:
        where = " line %d" % lines[0]
    else:
        where = " lines %d–%d" % (lines[0], lines[1])
    if "start" in c:
        s, e = c["start"], c["end"]
    else:
        s, e = st["range"]
    out = "%s%s [%d, %d)" % (c["source"], where, s, e)
    if "quote" in c:
        out += " " + pinned_json_string(c["quote"])
    return out


def render(entries):
    """answer.md under stewart.render/1; None when an entry is unproduced (8.1)."""
    if any(e.unproduced for e in entries):
        return None
    if not entries:
        return EMPTY_RENDERING
    out = [RENDER_FIRST_LINE.encode("utf-8") + b"\n"]
    for e in entries:
        head = "## %s — %s" % (kind_title(e.kind), e.id)
        if e.label:
            head += " · " + e.label
        out.append(b"\n" + head.encode("utf-8") + b"\n\n")
        if e.kind == "record_artifact" and e.encoding == "binary":
            out.append(("Binary artifact, %d bytes, SHA-256 %s, delivered as %s.\n"
                        % (e.size, e.sha256, e.member)).encode("utf-8"))
        elif not e.data:
            out.append(b"*No text recorded.*\n")
        else:
            lines = e.data.split(b"\n")
            if e.data.endswith(b"\n"):
                lines = lines[:-1]
            for line in lines:
                out.append((b"> " + line if line else b">") + b"\n")
        if e.citations:
            out.append(b"\nCitations: " + "; ".join(citation_text(c) for c in e.citations).encode("utf-8")
                       + b".\n")
    return b"".join(out)


def members(entries, answer_bytes, rendering_bytes):
    """The manifest's members (8.2): answer.json, answer.md unless unproduced, then each
    produced artifact in selection order."""
    out = [("answer.json", "answer", len(answer_bytes), sha(answer_bytes))]
    if rendering_bytes is not None:
        out.append(("answer.md", "rendering", len(rendering_bytes), sha(rendering_bytes)))
    for e in entries:
        if e.kind == "record_artifact" and not e.unproduced:
            out.append((e.member, "artifact", e.size, e.sha256))
    return out


def unproduced(entries):
    out = []
    bad = [e for e in entries if e.unproduced]
    for e in bad:
        out.append(b'{"name":' + pinned_json_string(e.id).encode() + b',"role":"entry","failure":'
                   + pinned_json_string(e.unproduced).encode() + b',"dependency":null}')
    if bad:
        out.append(b'{"name":"answer.md","role":"rendering","failure":"not_rendered","dependency":'
                   + rawjson.compact([e.id for e in bad]) + b"}")
    return out


def manifest(audit, store, family_id, writer, actor, sealed_at, revision, member_list, unproduced_items=()):
    def s(v):
        return pinned_json_string(v).encode("utf-8")
    mem = b",".join(b'{"name":' + s(n) + b',"role":' + s(r) + b',"size":%d' % size + b',"sha256":' + s(h) + b"}"
                    for n, r, size, h in member_list)
    return (b'{"schema":' + s(RETURN_SCHEMA) + b',"audit":' + s(audit) + b',"store":' + s(store)
            + b',"family":' + s(family_id) + b',"renderer":' + s(RENDERER) + b',"writer":' + s(writer)
            + b',"seal":{"actor":' + s(actor) + b',"sealed_at":' + s(sealed_at) + b'},"revision":%d' % revision
            + b',"members":[' + mem + b'],"unproduced":[' + b",".join(unproduced_items) + b"]}\n")


# ---------------------------------------------------------------------------
# Self-tests: the worked examples of the specification documents themselves.
# ---------------------------------------------------------------------------

def _doc(name):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", name)
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


@selftest
def answer_witness_selftests():
    out = list(rawjson.self_checks())
    # Read pages (7.2).
    data = b"a" * 70000 + b"\n" + b"b" * 10
    out.append(("witness.pages.no-lf-ascii", read_pages(data) == [(0, 65536), (65536, len(data))], read_pages(data)))
    data = (b"x" * 65000 + b"\n") + ("\u00e9" * 400).encode()
    out.append(("witness.pages.after-lf", read_pages(data)[0] == (0, 65001)))
    data = ("\u00e9" * 40000).encode()   # no LF: last boundary within the window
    p = read_pages(data)
    out.append(("witness.pages.boundary", p[0] == (0, 65536) and len(p) == 2 and p[1] == (65536, 80000), p))
    data3 = b"zz" + ("\u20ac" * 30000).encode()  # boundaries at 2 + 3k: 65536 would split a code point
    p3 = read_pages(data3)
    out.append(("witness.pages.no-split", p3[0][1] == 65534 and is_boundary(data3, p3[0][1]), p3))
    out.append(("witness.pages.small", read_pages(b"") == [(0, 0)] and read_pages(b"abc") == [(0, 3)]))
    # Citations (7.3).
    src = {"materials/a.py": b"line one\nR1. A reminder ID is unique\nR1. again\n", "question": b"Q?\n"}
    c = record_citation({"source": "materials/a.py", "quote": "reminder ID"}, src)
    at = src["materials/a.py"].find(b"reminder ID")
    out.append(("witness.cite.quote", c["stewart"]["range"] == [at, at + 11] and c["stewart"]["lines"] == [2, 2], c))
    try:
        record_citation({"source": "materials/a.py", "quote": "R1."}, src)
        out.append(("witness.cite.ambiguous", False))
    except CitationDefect as exc:
        d = src["materials/a.py"]
        out.append(("witness.cite.ambiguous", exc.reason == "quote_ambiguous"
                    and exc.occurrences == [d.find(b"R1."), d.rfind(b"R1.")], exc.occurrences))
    for label, cit, reason in (("not-found", {"source": "question", "quote": "nope"}, "quote_not_found"),
                               ("bad-quote", {"source": "question", "start": 0, "end": 2, "quote": "Qx"}, "citation_invalid"),
                               ("empty-range", {"source": "question", "start": 1, "end": 1}, "citation_invalid"),
                               ("past-end", {"source": "question", "start": 0, "end": 9}, "citation_invalid"),
                               ("start-only", {"source": "question", "start": 0}, "citation_invalid"),
                               ("unknown", {"source": "materials/none", "quote": "x"}, "citation_invalid")):
        try:
            record_citation(cit, src)
            out.append(("witness.cite.%s" % label, False))
        except CitationDefect as exc:
            out.append(("witness.cite.%s" % label, exc.reason == reason, exc.reason))
    mb = "é€".encode()
    try:
        record_citation({"source": "m", "start": 1, "end": 2}, {"m": mb})
        out.append(("witness.cite.mid-codepoint", False))
    except CitationDefect as exc:
        out.append(("witness.cite.mid-codepoint", exc.reason == "citation_invalid"))
    out.append(("witness.cite.bytes", citation_bytes(c) == (
        b'{"source":"materials/a.py","quote":"reminder ID","stewart":{"name":"materials/a.py","sha256":"'
        + sha(src["materials/a.py"]).encode() + b'","range":[%d,%d],"lines":[2,2]}}' % (at, at + 11))))
    # The rendering example of QUESTION-FORMS, byte for byte.
    qf = _doc("QUESTION-FORMS.md")
    if qf is None:
        out.append(("witness.docs", None, "skipped: docs/QUESTION-FORMS.md not beside the driver"))
        return out
    m = re.search(r"## The rendering.*?```\n(.*?)```", qf, re.S)
    example = m.group(1).encode("utf-8") if m else None
    e3 = Entry("e3", 1, "record_observation", "restart duplicate",
               b"Implementation A can send the same reminder twice if the worker stops\n"
               b"after sending but before recording the sent marker.",
               citations=[{"source": "materials/a.py", "start": 50, "end": 119, "quote": "R1. A reminder ID …",
                           "stewart": {"name": "materials/a.py", "sha256": "x", "lines": [4, 6]}},
                          {"source": "question", "start": 0, "end": 46,
                           "stewart": {"name": "question", "sha256": "y", "lines": [1, 1]}}])
    out.append(("witness.render.example", example is not None and render([e3]) == example,
                {"expected": example, "got": render([e3])}))
    # The structured answer example, byte for byte (with its "…" digests).
    m = re.search(r"## The structured answer.*?```json\n(.*?)```", qf, re.S)
    ex_json = m.group(1).encode("utf-8") if m else None
    e1 = Entry("e1", 2, "record_account", "",
               b"The supplied excerpts support one restart-related duplicate-delivery concern.",
               citations=[{"source": "materials/a.py", "start": 0, "end": 175,
                           "stewart": {"name": "materials/a.py", "sha256": "…", "lines": [1, 8]}},
                          {"source": "materials/a.py", "quote": "R1. A reminder ID",
                           "stewart": {"name": "materials/a.py", "sha256": "…", "range": [50, 67],
                                       "lines": [4, 4]}}])
    e4 = Entry("e4", 1, "record_artifact", "trace", b"", encoding="utf-8", sha256="…", size=120)
    out.append(("witness.answer.example", ex_json is not None and answer_json(7, [e1, e4]) == ex_json,
                {"expected": ex_json, "got": answer_json(7, [e1, e4])}))
    out.append(("witness.answer.empty", answer_json(3, []) == b'{"schema":"stewart.answer/1","revision":3,"entries":[]}\n'))
    # Rendering rules beyond the example.
    arts = [Entry("e1", 1, "record_working_question", "", b""),
            Entry("e2", 1, "record_limit", "l", b"a\n\nb\r\n"),
            Entry("e5", 1, "record_artifact", "bin", b"\x00\xff", encoding="binary")]
    want = ("Rendered by Stewart. Entry text is attributed to the auditor.\n\n"
            "## Working question — e1\n\n*No text recorded.*\n\n"
            "## Limit — e2 · l\n\n> a\n>\n> b\r\n\n"
            "## Artifact — e5 · bin\n\nBinary artifact, 2 bytes, SHA-256 %s, delivered as artifact-e5.bin.\n"
            % sha(b"\x00\xff")).encode("utf-8")
    out.append(("witness.render.rules", render(arts) == want, {"got": render(arts), "want": want}))
    out.append(("witness.render.empty", render([]) == b"No answer entries recorded.\n"))
    out.append(("witness.render.unproduced", render([Entry("e1", 1, "record_limit", "", b"", unproduced="damaged")]) is None))
    # The manifest example of INTERFACE 8.2 (its digests and writer are "…").
    itf = _doc("INTERFACE.md")
    m = re.search(r"The manifest \(`stewart.return/1`\).*?```\n(.*?)```", itf or "", re.S)
    ex_man = m.group(1).encode("utf-8") if m else None
    got = manifest("aqm3x7kd2hz5vw4ny", "s7tq2bk6xm3ra4pfe", "open-inquiry/1", "3f1c…", "auditor",
                   "2026-11-02T15:20:04.118Z", 9,
                   [("answer.json", "answer", 3904, "…"), ("answer.md", "rendering", 2210, "…"),
                    ("artifact-e4.bin", "artifact", 120, "…")])
    out.append(("witness.manifest.example", ex_man is not None and got == ex_man, {"expected": ex_man, "got": got}))
    un = unproduced([Entry("e3", 1, "record_observation", "", b"", unproduced="damaged", sha256="h", size=1)])
    out.append(("witness.unproduced", un == [b'{"name":"e3","role":"entry","failure":"damaged","dependency":null}',
                                             b'{"name":"answer.md","role":"rendering","failure":"not_rendered","dependency":["e3"]}']))
    return out
