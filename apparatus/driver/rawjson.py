# -*- coding: utf-8 -*-
"""Byte-exact JSON spans, standard library only.

Stewart splices pinned bytes into provider requests and copies response bytes
into history without re-serializing them (INTERFACE 4.5, 6.2). Checking that
needs the exact byte span of each JSON value, which `json` does not expose.
`parse(data)` returns a tree of `Node`s, each with its `start` and `end` byte
offsets in `data`; `node.raw` is `data[start:end]`.

The reader is tolerant in the sense of INTERFACE 6.2: repeated keys are kept
(`node.members` lists every key in order, `node.get` returns the first and
`node.count` says how many there are) and numbers are not interpreted beyond
their span. It refuses what is not JSON at all.
"""
from __future__ import annotations

import json

WS = b" \t\n\r"


class RawJSONError(ValueError):
    pass


class Node:
    __slots__ = ("data", "kind", "start", "end", "members", "items", "_value")

    def __init__(self, data, kind, start):
        self.data, self.kind, self.start, self.end = data, kind, start, start
        self.members = []   # objects: [(key, key_start, key_end, Node)]
        self.items = []     # arrays: [Node]
        self._value = None

    @property
    def raw(self):
        return self.data[self.start:self.end]

    def value(self):
        """The decoded value (tolerant: for repeated keys the last one wins, as json does)."""
        if self._value is None:
            self._value = json.loads(self.raw.decode("utf-8"))
        return self._value

    def keys(self):
        return [k for k, _, _, _ in self.members]

    def get(self, key):
        for k, _, _, n in self.members:
            if k == key:
                return n
        return None

    def count(self, key):
        return sum(1 for k, _, _, _ in self.members if k == key)

    def __repr__(self):
        return "Node(%s, %d:%d)" % (self.kind, self.start, self.end)


def _skip_ws(data, i):
    n = len(data)
    while i < n and data[i] in WS:
        i += 1
    return i


def _string_end(data, i):
    """i is at the opening quote; return the index just after the closing quote."""
    n = len(data)
    j = i + 1
    while j < n:
        c = data[j]
        if c == 0x22:  # "
            return j + 1
        if c == 0x5C:  # backslash
            j += 2
            continue
        if c < 0x20:
            raise RawJSONError("control byte 0x%02x inside a string at %d" % (c, j))
        j += 1
    raise RawJSONError("unterminated string starting at %d" % i)


def _parse(data, i, depth):
    if depth > 512:
        raise RawJSONError("nesting too deep at %d" % i)
    i = _skip_ws(data, i)
    if i >= len(data):
        raise RawJSONError("value expected at %d" % i)
    c = data[i]
    if c == 0x7B:  # {
        node = Node(data, "object", i)
        j = _skip_ws(data, i + 1)
        if j < len(data) and data[j] == 0x7D:
            node.end = j + 1
            return node
        while True:
            j = _skip_ws(data, j)
            if j >= len(data) or data[j] != 0x22:
                raise RawJSONError("object key expected at %d" % j)
            ke = _string_end(data, j)
            key = json.loads(data[j:ke].decode("utf-8"))
            k = _skip_ws(data, ke)
            if k >= len(data) or data[k] != 0x3A:
                raise RawJSONError("':' expected at %d" % k)
            child = _parse(data, k + 1, depth + 1)
            node.members.append((key, j, ke, child))
            j = _skip_ws(data, child.end)
            if j < len(data) and data[j] == 0x2C:
                j += 1
                continue
            if j < len(data) and data[j] == 0x7D:
                node.end = j + 1
                return node
            raise RawJSONError("',' or '}' expected at %d" % j)
    if c == 0x5B:  # [
        node = Node(data, "array", i)
        j = _skip_ws(data, i + 1)
        if j < len(data) and data[j] == 0x5D:
            node.end = j + 1
            return node
        while True:
            child = _parse(data, j, depth + 1)
            node.items.append(child)
            j = _skip_ws(data, child.end)
            if j < len(data) and data[j] == 0x2C:
                j += 1
                continue
            if j < len(data) and data[j] == 0x5D:
                node.end = j + 1
                return node
            raise RawJSONError("',' or ']' expected at %d" % j)
    if c == 0x22:
        node = Node(data, "string", i)
        node.end = _string_end(data, i)
        return node
    for lit, kind in ((b"true", "true"), (b"false", "false"), (b"null", "null")):
        if data.startswith(lit, i):
            node = Node(data, kind, i)
            node.end = i + len(lit)
            return node
    if c == 0x2D or 0x30 <= c <= 0x39:
        j = i + 1
        while j < len(data) and data[j] in b"0123456789+-.eE":
            j += 1
        node = Node(data, "number", i)
        node.end = j
        try:
            json.loads(data[i:j].decode("ascii"))
        except ValueError:
            raise RawJSONError("bad number at %d" % i)
        return node
    raise RawJSONError("unexpected byte 0x%02x at %d" % (c, i))


def parse(data):
    """Parse one JSON document (surrounding JSON whitespace allowed) into Nodes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    data = bytes(data)
    node = _parse(data, 0, 0)
    if _skip_ws(data, node.end) != len(data):
        raise RawJSONError("data after the value at %d" % node.end)
    return node


def try_parse(data):
    try:
        return parse(data)
    except (RawJSONError, ValueError, UnicodeDecodeError):
        return None


def compact(value):
    """Compact JSON bytes with keys in insertion order and raw UTF-8 (ensure_ascii off)."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def self_checks():
    """(name, ok) pairs for the driver's self-test."""
    out = []
    doc = b' {"a":[1,{"b":"x\\"y"}], "a":true ,"c" : null} '
    n = parse(doc)
    out.append(("rawjson.object", n.kind == "object" and n.keys() == ["a", "a", "c"]))
    out.append(("rawjson.repeated", n.count("a") == 2 and n.get("a").kind == "array"))
    out.append(("rawjson.span", n.get("a").raw == b'[1,{"b":"x\\"y"}]'))
    out.append(("rawjson.nested", n.get("a").items[1].get("b").raw == b'"x\\"y"'))
    out.append(("rawjson.whole", n.raw == doc.strip()))
    out.append(("rawjson.trailing", try_parse(b"{} x") is None))
    out.append(("rawjson.unterminated", try_parse(b'{"a":"x}') is None))
    out.append(("rawjson.number", parse(b"[-1.5e3,0]").items[0].raw == b"-1.5e3"))
    out.append(("rawjson.utf8", parse('{"é":"日本"}'.encode()).get("é").value() == "日本"))
    out.append(("rawjson.compact", compact({"b": 1, "a": "é"}) == '{"b":1,"a":"é"}'.encode()))
    return out
