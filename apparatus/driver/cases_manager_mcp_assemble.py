"""Candidate assembly in the manager preparation MCP, from MANAGER-PREPARATION ("Assemble" and
"Filesystem authority and interruption"), INTERFACE 3.2, 5.1, 5.11 and Appendix C, and
ACCEPTANCE C21. Written from the specification without reading service/.

Every case builds its own workspace with a `sources/` directory, keeps an independent witness of
each source and of the candidate it expects (the generated question.md bytes under the
front-matter rule, the sorted inventory, sizes and digests), and inventories the workspace, the
answer destination, HOME, the working directory and TMPDIR around every server session. The
server is driven interactively over stdio, so a case can inspect the filesystem between calls,
pause one creation while another server races it, or lose a reply to a killed process.
"""
import json
import os
import signal
import stat
import subprocess
import time
from pathlib import Path

from claude_code import transport_loads
from driver_core import (D, F, FIFO, HARD, L, Control, Proc, Sub, build_entries, case, is_compact_json,
                         read_bytes, selftest, sha256_hex, strict_loads)
from rawjson import compact
from cases_manager_mcp import INITIALIZE, INITIALIZED, VERSION, call as mcp_call

NONE = {"state": "none", "created": [], "incomplete": []}
# Assess's unchecked list without material_bytes: assembly has checked every supplied byte.
CHECKED_UNCHECKED = ["filesystem", "source_stability", "acceptance"]
RESULT_KEYS = ("schema", "registry", "question_schema", "tool", "outcome", "problem", "data", "writes",
               "explanation")
ROLE_KEY_ORDER = ("role", "source", "label")


# ---------------------------------------------------------------------------
# The independent witness of a candidate.
# ---------------------------------------------------------------------------

SHORT_ESCAPES = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def json_string(text):
    r"""MANAGER-PREPARATION's string rule for generated role arrays: escape only `"`, `\` and
    U+0001-U+001F, as \b, \f, \n, \r or \t where they apply and otherwise \u with four
    lowercase hex digits; every other character is literal UTF-8."""
    out = []
    for ch in text:
        if ch in SHORT_ESCAPES:
            out.append(SHORT_ESCAPES[ch])
        elif "\u0001" <= ch <= "\u001f":
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def json_value(value):
    """Compact JSON for role entries: objects in the given member order, strings by json_string."""
    if isinstance(value, str):
        return json_string(value)
    if isinstance(value, bool) or value is None:
        return {True: "true", False: "false", None: "null"}[value]
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ",".join(json_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(json_string(k) + ":" + json_value(v) for k, v in value.items()) + "}"
    raise TypeError(type(value))


def encode_roles(roles):
    """INTERFACE 3.2 as MANAGER-PREPARATION states it for generation: a compact array in the
    given order, each entry with role, source and label first, then its other members in the
    order supplied."""
    out = []
    for entry in roles:
        ordered = {k: entry[k] for k in ROLE_KEY_ORDER if k in entry}
        ordered.update((k, v) for k, v in entry.items() if k not in ROLE_KEY_ORDER)
        out.append(ordered)
    return json_value(out)


def generate_question(fields, body):
    """UTF-8 front matter with LF: `---`, `stewart: question/2`, the present fields in bytewise
    key order as `key: value`, `---`, then the exact body bytes (no newline added)."""
    lines = ["---\n", "stewart: question/2\n"]
    for key in sorted(fields, key=lambda k: k.encode("utf-8")):
        value = fields[key]
        lines.append("%s: %s\n" % (key, encode_roles(value) if key == "material-roles" else value))
    lines.append("---\n")
    return ("".join(lines) + body).encode("utf-8")


def by_name_bytes(names):
    return sorted(names, key=lambda n: n.encode("utf-8"))


class Candidate:
    """Arguments for one assembly and everything the driver expects of it. files is a list of
    (public name, source name under sources/); sources maps source names to their bytes."""

    def __init__(self, fields, body, guidance, directories, files, sources):
        self.fields, self.body, self.guidance = dict(fields), body, guidance
        self.directories, self.files, self.sources = list(directories), list(files), sources
        self.question = generate_question(self.fields, body)
        self.contents = {name: sources[src] for name, src in files}
        everything = dict(self.contents, **{"question.md": self.question})
        if guidance is not None:
            everything["guidance.md"] = guidance.encode("utf-8")
        self.all_files = everything
        self.rows = [{"name": n, "size": len(everything[n]), "sha256": sha256_hex(everything[n])}
                     for n in by_name_bytes(everything)]
        self.sorted_dirs = by_name_bytes(set(directories))

    def arguments(self, destination, **extra):
        args = {"fields": self.fields, "body": self.body, "guidance": self.guidance,
                "directories": self.directories,
                "files": [{"name": name, "from": src} for name, src in self.files],
                "destination": destination}
        args.update(extra)
        return args

    def assess_arguments(self, unread=False):
        """assess of the generated question, the guidance and the actual sizes, in files order;
        with unread, every size zero, as for an assessment made before any source is read."""
        return {"question_file": self.question.decode("utf-8"), "guidance": self.guidance,
                "directories": self.directories,
                "files": [{"name": name, "size": 0 if unread else len(self.contents[name])}
                          for name, _ in self.files]}

    def data(self, assessment):
        return {"question_file": self.question.decode("utf-8"), "directories": self.sorted_dirs,
                "files": self.rows, "assessment": assessment}

    def created(self, destination):
        """Creation order: the candidate, data.directories, then data.files (question.md last)."""
        return ([destination] + [destination + "/" + d for d in self.sorted_dirs]
                + [destination + "/" + row["name"] for row in self.rows])

    def tree(self):
        """Candidate-relative path -> bytes, or None for a directory, as created."""
        out = {d: None for d in self.sorted_dirs}
        out.update(self.all_files)
        return out

    def sub_entries(self):
        """driver_core entries (relative to materials/) for a Sub witness of the created folder."""
        out = [D(d[len("materials/"):]) for d in self.sorted_dirs if d != "materials"]
        out += [F(n[len("materials/"):], data) for n, data in self.contents.items()]
        return out


SOURCES = {
    "a.py": b"def send(r):\r\n    deliver(r)\r\n    mark_sent(r)",
    "b.py": b"def send(r):\n    mark_sent(r)\n    deliver(r)\n",
    "notes/r.txt": "R1. Au plus une fois — résumé\n".encode("utf-8"),
    "Z-upper.txt": b"upper first\n",
    ".hidden.txt": b"hidden\n",
    "empty.txt": b"",
    "bom.txt": b"\xef\xbb\xbfBOM line\n",
    "bad.bin": b"ok \xff here\n",
    "h1.txt": b"one inode, two names\n",
    "pkg/STORE.json": b"{}\n",
    "pkg/x.txt": b"inside a store marker's directory\n",
    "stewart-return-zz/x.txt": b"inside a package-named directory\n",
    "locked.txt": b"unreadable later\n",
}


def build_workspace(t, label):
    """A fresh workspace W with sources/, every SOURCES file plus a symlink, a FIFO and a second
    name for h1.txt. Returns W (an absolute path)."""
    w = t.mkdir("workspace %s %d" % (label, t.next_k()))
    os.mkdir(os.path.join(w, "sources"))
    entries = [F(name, data) for name, data in SOURCES.items()]
    entries += [L("link.py", b"a.py"), FIFO("pipe"), HARD("h2.txt", "h1.txt")]
    build_entries(os.path.join(w, "sources"), entries)
    return w


def specimen_g(dest):
    """Open inquiry with selected guidance, an effort, an inquiry label, a renamed source, nested,
    hidden, empty, BOM and upper-case names, an empty directory and a CRLF body without a final
    newline."""
    fields = {"family": "open-inquiry", "model": "claude-opus-5-5", "destination": dest,
              "guidance": "guidance.md", "effort": "high", "inquiry": "Reminder duplicates",
              "limit-turns": "200", "limit-input-tokens": "20000000", "limit-output-tokens": "400000"}
    files = [("materials/main.py", "a.py"), ("materials/notes/r.txt", "notes/r.txt"),
             ("materials/.hidden.txt", ".hidden.txt"), ("materials/Z-upper.txt", "Z-upper.txt"),
             ("materials/empty.txt", "empty.txt"), ("materials/bom.txt", "bom.txt")]
    return Candidate(fields, "Can one reminder be sent twice?\r\nCover what happens across a restart.",
                     "Answer only from the supplied files.\r\nCite each claim.",
                     ["materials/notes", "materials", "materials/void"], files, SOURCES)


def specimen_c(dest):
    """Comparison with declared roles supplied in another member order, labels holding a quote,
    a backslash and non-ASCII letters; generation puts role, source and label first, escapes
    the quote and backslash and writes the letters as UTF-8."""
    roles = [{"source": "materials/a.py", "label": "Option \"A\" \\ \u00c4", "role": "alternative"},
             {"label": "Opci\u00f3n B", "role": "alternative", "source": "materials/b.py"},
             {"source": "materials/criteria/rider.txt", "role": "criterion"}]
    fields = {"family": "comparison", "model": "claude-opus-5-5", "destination": dest, "limit-turns": "10",
              "limit-input-tokens": "50000", "limit-output-tokens": "5000", "material-roles": roles}
    files = [("materials/b.py", "b.py"), ("materials/a.py", "a.py"), ("materials/criteria/rider.txt", "notes/r.txt")]
    return Candidate(fields, "Which option sends each reminder at most once?\n", None,
                     ["materials", "materials/criteria"], files, SOURCES)


def specimen_empty(dest):
    """MANAGER-PREPARATION's example: an empty open inquiry."""
    fields = {"family": "open-inquiry", "model": "example-model", "destination": dest, "limit-turns": "4",
              "limit-input-tokens": "32000", "limit-output-tokens": "8000"}
    return Candidate(fields, "What can these materials establish?", None, ["materials"], [], SOURCES)


# ---------------------------------------------------------------------------
# An interactive stdio server and its replies.
# ---------------------------------------------------------------------------

class Server:
    """`stewart manager-mcp [--workspace W]` driven one request at a time. The session's stdin
    is kept in the evidence; the process counts as a live writer for inventories while it runs."""

    def __init__(self, t, name, workspace=None, fault=None, timeout=240, initialize=True):
        """initialize=False leaves the handshake to the caller (send_raw), for exact frames."""
        self.t, self.name, self.fault = t, name, fault
        self.argv = [t.bin["path"], "manager-mcp"] + (["--workspace", workspace] if workspace is not None else [])
        self.env = t.env(None, fault)
        self.sent = bytearray()
        self.consumed = 0
        self.replies = {}
        self.result = None
        t.sync("before " + name)
        self.proc = Proc(self.argv, self.env, t.cwd, timeout, stdin=subprocess.PIPE)
        # Shaped as T.start's handles, so a server left running by an aborted case is ended and
        # recorded as theirs are.
        self.handle = {"proc": self.proc, "env": self.env, "name": name, "op": "manager-mcp", "argv": self.argv,
                       "cwd": t.cwd, "fault": fault}
        t.bg.append(self.handle)
        if not initialize:
            return
        self.send(INITIALIZE)
        init = self.reply("init", 30)
        t.require(name + ".initialize", isinstance(init, dict) and init.get("result") == {
            "protocolVersion": VERSION, "capabilities": {"tools": {}},
            "serverInfo": {"name": "stewart-manager", "version": "1"}}, init)
        self.send(INITIALIZED)

    def send(self, frame):
        self.send_raw(compact(frame) + b"\n")

    def send_raw(self, data):
        """Exact bytes on the server's stdin, kept in the session's evidence."""
        self.sent += data
        try:
            self.proc.p.stdin.write(data)
            self.proc.p.stdin.flush()
        except OSError as exc:
            self.t.check(self.name + ".stdin-open", False, str(exc))

    def _drain(self):
        out = bytes(self.proc.out)
        while True:
            end = out.find(b"\n", self.consumed)
            if end < 0:
                return
            line, self.consumed = out[self.consumed:end], end + 1
            self.t.check(self.name + ".compact-frames", is_compact_json(line.decode("utf-8", "replace")), line[:300])
            try:
                value = transport_loads(line)
            except ValueError as exc:
                self.t.check(self.name + ".frame-json", False, {"error": str(exc), "line": line[:300]})
                continue
            self.replies[value.get("id")] = value

    def reply(self, identity, timeout=90):
        """The reply with this ID, or None if the process ended or the time ran out without it."""
        deadline = time.monotonic() + timeout
        while True:
            self._drain()
            if identity in self.replies:
                return self.replies.pop(identity)
            if not self.proc.running():
                time.sleep(0.05)
                self._drain()
                return self.replies.pop(identity, None)
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.005)

    def call(self, identity, tool, arguments, timeout=90):
        self.send(mcp_call(identity, tool, arguments))
        return self.reply(identity, timeout)

    def close(self, expect_rc=0):
        try:
            self.proc.p.stdin.close()
        except OSError:
            pass
        res = self.proc.wait()
        if self.handle in self.t.bg:
            self.t.bg.remove(self.handle)
        self.t.sync("after " + self.name)
        (Path(self.t.evid) / (self.name + ".stdin")).write_bytes(bytes(self.sent))
        self.t._record(self.name, "manager-mcp", self.argv, self.env, self.t.cwd, res, self.fault, False)
        if expect_rc is not None:
            self.t.eq(self.name + ".exit", res["rc"], expect_rc)
        self.result = res
        return res


def result(t, name, reply, *, outcome="completed", reason=None, pointer="any", writes=NONE, data="any"):
    """One assemble tool result (MANAGER-PREPARATION "Transport" and "Assemble"): isError, a
    structuredContent object equal to its one compact text block, the required keys, and the
    expected outcome, problem, writes and data."""
    t.require(name + ".reply", isinstance(reply, dict) and isinstance(reply.get("result"), dict), reply)
    res = reply["result"]
    t.eq(name + ".error-flag", res.get("isError"), outcome != "completed")
    value = res.get("structuredContent")
    t.require(name + ".structured", isinstance(value, dict), res)
    content = res.get("content")
    t.require(name + ".one-text-block", isinstance(content, list) and len(content) == 1
              and isinstance(content[0], dict) and content[0].get("type") == "text"
              and isinstance(content[0].get("text"), str), content)
    text = content[0]["text"]
    t.check(name + ".compact-result", is_compact_json(text), text[:300])
    t.eq(name + ".result-fidelity", strict_loads(text.encode("utf-8")), value)
    t.check(name + ".required-keys", all(k in value for k in RESULT_KEYS), sorted(value))
    for key, expected in (("schema", "stewart.manager-preparation/1"), ("registry", "stewart.family-registry/1"),
                          ("question_schema", "question/2"), ("tool", "assemble"), ("outcome", outcome)):
        t.eq(name + "." + key, value.get(key), expected)
    t.eq(name + ".brief", value.get("explanation"), [])
    if writes is not None:
        t.eq(name + ".writes", value.get("writes"), writes)
    problem = value.get("problem")
    if reason is None:
        t.eq(name + ".problem", problem, None)
    else:
        # Not a requirement: a case judging a wrong outcome keeps going to the checks that name
        # the property (a control's targets often follow).
        if t.check(name + ".problem-object", isinstance(problem, dict), value):
            t.eq(name + ".problem-keys", sorted(problem), ["message", "pointer", "reason", "remedy"])
            for key in ("message", "remedy"):
                t.check(name + "." + key, isinstance(problem.get(key), str) and problem[key].strip(), problem)
        issue = problem if isinstance(problem, dict) else {}
        t.eq(name + ".reason", issue.get("reason"), reason)
        if pointer != "any":
            t.eq(name + ".pointer", issue.get("pointer", "missing"), pointer)
    if data != "any":
        t.eq(name + ".data", value.get("data", "missing"), data)
    return value


def assessment_of(t, name, server, candidate, identity):
    """assess of the generated question, guidance and actual sizes (the assembly's own oracle,
    MANAGER-PREPARATION "Assemble"), with material_bytes dropped as assembly checks the bytes."""
    reply = server.call(identity, "assess", candidate.assess_arguments())
    value = reply.get("result", {}).get("structuredContent", {}) if isinstance(reply, dict) else {}
    data = value.get("data")
    t.require(name + ".assess", isinstance(data, dict) and value.get("outcome") == "completed", reply)
    t.check(name + ".assess-unchecked", data.get("unchecked", [None])[:1] == ["material_bytes"], data)
    return dict(data, unchecked=[u for u in data.get("unchecked", []) if u != "material_bytes"])


def check_proposal(t, name, data, candidate, assessment):
    t.require(name + ".data-object", isinstance(data, dict), data)
    t.eq(name + ".data-keys", sorted(data), ["assessment", "directories", "files", "question_file"])
    t.eq(name + ".question_file", data.get("question_file"), candidate.question.decode("utf-8"))
    t.eq(name + ".directories", data.get("directories"), candidate.sorted_dirs)
    t.eq(name + ".files", data.get("files"), candidate.rows)
    t.eq(name + ".unchecked", (data.get("assessment") or {}).get("unchecked"), CHECKED_UNCHECKED)
    t.eq(name + ".assessment", data.get("assessment"), assessment)


def tree(path):
    """rel -> (kind, mode, sha256 or None) below path without following links or opening FIFOs."""
    out = {}
    if not os.path.lexists(path):
        return None
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        for name in sorted(dirnames + filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, path)
            st = os.lstat(full)
            mode = stat.S_IMODE(st.st_mode)
            if stat.S_ISDIR(st.st_mode):
                out[rel] = ("dir", mode, None)
            elif stat.S_ISREG(st.st_mode):
                try:
                    digest = sha256_hex(read_bytes(full))
                except OSError:
                    digest = "unreadable"
                out[rel] = ("file", mode, digest, st.st_ino)
            elif stat.S_ISLNK(st.st_mode):
                out[rel] = ("link", mode, os.readlink(full))
            else:
                out[rel] = ("special", mode, None)
    return out


def check_candidate(t, name, root, expected):
    """The created candidate holds exactly the expected entries and bytes, 0700/0600."""
    st = os.lstat(root) if os.path.lexists(root) else None
    t.require(name + ".exists", st is not None and stat.S_ISDIR(st.st_mode), root)
    t.eq(name + ".root-mode", oct(stat.S_IMODE(st.st_mode)), oct(0o700))
    seen = tree(root) or {}
    t.eq(name + ".entries", sorted(seen), sorted(expected))
    for rel, data in sorted(expected.items()):
        got = seen.get(rel)
        if data is None:
            t.eq(name + ".dir." + rel, (got or ("missing",))[:2], ("dir", 0o700))
        else:
            t.eq(name + ".file." + rel, (got or ("missing",))[:3], ("file", 0o600, sha256_hex(data)))


def watch_outsiders(t):
    for p, label in ((t.home, "home"), (t.cwd, "cwd"), (t.tmp, "tmp")):
        t.watch(p, "frozen", label)


def folds_case(directory):
    """Whether this filesystem resolves a name in another case to the same entry."""
    probe = os.path.join(directory, "case-probe-x")
    with open(probe, "wb"):
        pass
    try:
        return os.path.lexists(os.path.join(directory, "CASE-PROBE-X"))
    finally:
        os.unlink(probe)


# ---------------------------------------------------------------------------
# Cases.
# ---------------------------------------------------------------------------

@case("c21.assemble-dry-run", ["C21", "C19", "C20"],
      "dry-run assembly proposes the exact question, inventory and assessment and writes nothing",
      controls=[Control("candidate_dry_run_writes", [r"^assemble\.dry\.[a-z]+\.(workspace-unchanged|no-candidate)$"]),
                Control("candidate_forecast_as_written", [r"^assemble\.dry\.[a-z]+\.writes$"])])
def c_assemble_dry_run(t):
    """With a workspace, a dry run of an open inquiry with guidance (specimen g) and of a
    comparison whose role entries are supplied in another member order (specimen c) returns
    exactly the generated question.md (front matter in bytewise key order, roles re-encoded
    role/source/label first), the directories and files sorted by UTF-8 name bytes with sizes
    and SHA-256 (question and guidance included), and the assessment `assess` gives for the
    generated question, guidance and actual sizes, without material_bytes because the bytes
    were read; writes are none, the candidate does not exist and the workspace inventory is
    unchanged. Invariance: the inventory arrays in another order and a repeated call give the
    same data. Differing: one changed body character changes only question_file and its row.
    Without a workspace, MANAGER-PREPARATION's empty open inquiry works (unchecked has no
    material_bytes: no bytes were supplied); with a file it refuses workspace_required at
    /files, and a creation refuses it at /create. tools/list advertises assemble fourth (c21.manager-mcp-families).
    The controls run specimen g."""
    w = build_workspace(t, "dry")
    t.watch(w, "frozen", "workspace")
    watch_outsiders(t)
    dest = t.dest_path()
    t.watch(dest, "frozen", "answer destination")
    specimens = [("g", specimen_g(dest))] + ([] if t.sabotage else [("c", specimen_c(dest))])
    srv = Server(t, "dry", workspace=w)
    before = tree(w)
    for label, cand in specimens:
        name = "assemble.dry." + label
        assessment = assessment_of(t, name, srv, cand, label + "-assess")
        value = result(t, name, srv.call(label, "assemble", cand.arguments("cand-" + label)))
        check_proposal(t, name, value.get("data"), cand, assessment)
        t.check(name + ".no-candidate", not os.path.lexists(os.path.join(w, "cand-" + label)), sorted(os.listdir(w)))
        t.eq(name + ".workspace-unchanged", tree(w), before)
        if t.sabotage:
            continue
        args = cand.arguments("cand-" + label)
        shuffled = dict(args, directories=list(reversed(args["directories"])), files=list(reversed(args["files"])))
        again = result(t, name + ".reordered", srv.call(label + "-reordered", "assemble", shuffled))
        t.eq(name + ".reordered.same-data", dict(again.get("data") or {}, assessment=None),
             dict(value.get("data") or {}, assessment=None))
        repeat = result(t, name + ".repeat", srv.call(label + "-repeat", "assemble", args))
        t.eq(name + ".repeat.same-data", repeat.get("data"), value.get("data"))
    if not t.sabotage:
        g = specimen_g(dest)
        changed = Candidate(g.fields, g.body.replace("twice", "thrice"), g.guidance, g.directories, g.files, SOURCES)
        reply = srv.call("g-differs", "assemble", changed.arguments("cand-g"))
        value = result(t, "assemble.dry.differing", reply)
        data = value.get("data") or {}
        t.eq("assemble.dry.differing.question", data.get("question_file"), changed.question.decode("utf-8"))
        t.eq("assemble.dry.differing.other-rows",
             [r for r in data.get("files", []) if r.get("name") != "question.md"],
             [r for r in g.rows if r["name"] != "question.md"])
        t.eq("assemble.dry.differing.question-row",
             [r for r in data.get("files", []) if r.get("name") == "question.md"],
             [r for r in changed.rows if r["name"] == "question.md"])
    srv.close()
    if t.sabotage:
        return
    bare = Server(t, "no-workspace")
    empty = specimen_empty("/home/ana/returns")
    reply = bare.call("assess", "assess", empty.assess_arguments())
    assessed = (reply or {}).get("result", {}).get("structuredContent", {}).get("data") or {}
    value = result(t, "assemble.no-workspace.empty", bare.call("empty", "assemble", empty.arguments("first-inquiry")))
    data = value.get("data") or {}
    t.eq("assemble.no-workspace.empty.question_file", data.get("question_file"), empty.question.decode("utf-8"))
    t.eq("assemble.no-workspace.empty.inventory", [data.get("directories"), data.get("files")],
         [["materials"], empty.rows])
    t.eq("assemble.no-workspace.empty.assessment",
         data.get("assessment"), dict(assessed, unchecked=[u for u in assessed.get("unchecked", []) if u != "material_bytes"]))
    g = specimen_g(dest)
    result(t, "assemble.no-workspace.files", bare.call("files", "assemble", g.arguments("cand")),
           outcome="refused", reason="workspace_required", pointer="/files", data=None)
    result(t, "assemble.no-workspace.create", bare.call("create", "assemble", empty.arguments("cand", create=True)),
           outcome="refused", reason="workspace_required", pointer="/create", data=None)
    bare.close()


@case("c21.assemble-create", ["C21", "C19", "C11", "C15"],
      "creation writes the proposed bytes in order, 0700/0600, and the CLI prepares the folder as proposed")
def c_assemble_create(t):
    """A dry run, then the same arguments with create:true: outcome completed with the dry run's
    data, writes complete with created listing the candidate, its directories and its files
    in creation order (question.md last) and nothing incomplete; the candidate holds exactly
    those entries with the witness bytes, directories 0700 and files 0600; the workspace gains
    only the candidate and sources/ is unchanged; the answer destination is untouched. A second
    creation of the same name refuses destination_exists and writes nothing; the same arguments
    under a fresh name create identical bytes (invariance). Then `stewart new` on the created
    folder and `prepare` see exactly the proposed question, guidance, materials, directories
    and settings."""
    w = build_workspace(t, "create")
    t.watch(w, "additions", "workspace")
    t.watch(os.path.join(w, "sources"), "frozen", "sources")
    watch_outsiders(t)
    dest = t.dest_path()
    t.watch(dest, "frozen", "answer destination")
    cand = specimen_g(dest)
    srv = Server(t, "create", workspace=w)
    assessment = assessment_of(t, "assemble.create", srv, cand, "assess")
    dry = result(t, "assemble.create.dry", srv.call("dry", "assemble", cand.arguments("cand")))
    check_proposal(t, "assemble.create.dry", dry.get("data"), cand, assessment)
    made = result(t, "assemble.create", srv.call("create", "assemble", cand.arguments("cand", create=True)),
                  writes={"state": "complete", "created": cand.created("cand"), "incomplete": []})
    t.eq("assemble.create.same-data", made.get("data"), dry.get("data"))
    check_candidate(t, "assemble.create.tree", os.path.join(w, "cand"), cand.tree())
    t.eq("assemble.create.workspace-entries", sorted(os.listdir(w)), ["cand", "sources"])
    kept = tree(os.path.join(w, "cand"))
    result(t, "assemble.create.repeat", srv.call("repeat", "assemble", cand.arguments("cand", create=True)),
           outcome="refused", reason="destination_exists", pointer="/destination", data=None)
    t.eq("assemble.create.repeat.unchanged", tree(os.path.join(w, "cand")), kept)
    result(t, "assemble.create.fresh", srv.call("fresh", "assemble", cand.arguments("cand-2", create=True)),
           writes={"state": "complete", "created": cand.created("cand-2"), "incomplete": []})
    check_candidate(t, "assemble.create.fresh.tree", os.path.join(w, "cand-2"), cand.tree())
    srv.close()
    folder = os.path.join(w, "cand")
    t.watch(folder, "frozen", "candidate folder")
    sub = Sub(t, folder, dest, t.archive_path(), cand.question, cand.sub_entries(), (), "open-inquiry",
              "claude-opus-5-5", (200, 20000000, 400000), effort="high", guidance=cand.all_files["guidance.md"])
    t.new_ref(sub, name="assemble.cli.new")
    rep = t.prepare(sub, name="assemble.cli.prepare")
    t.check_prepare_witness(rep, sub, "assemble.cli.prepare")


@case("c21.assemble-collision", ["C21", "C6", "C18"],
      "an existing entry of the candidate's name refuses destination_exists in a dry run and at creation, unchanged",
      controls=[Control("candidate_overwrites_existing",
                        [r"^assemble\.collision\.existing\.(create\.reason|create\.writes|unchanged)$"])])
def c_assemble_collision(t):
    """An earlier complete-looking candidate (question.md, materials/), an incomplete earlier
    candidate (materials/ only) and a plain file each occupy the candidate name: a dry run and
    a creation each refuse destination_exists with null data and writes none, and each entry
    keeps its bytes. Where the host folds case, the existing candidate's name in another case
    is also destination_exists; where it does not, that name is a fresh entry and creation
    completes (the differing case), leaving the existing candidate unchanged. A missing
    required field is checked before the existing name (MANAGER-PREPARATION refusal order):
    candidate_invalid. The control runs the existing candidate's creation."""
    w = build_workspace(t, "collision")
    existing = os.path.join(w, "existing")
    os.makedirs(os.path.join(existing, "materials"))
    with open(os.path.join(existing, "question.md"), "wb") as f:
        f.write(b"---\nstewart: question/2\n---\nAn earlier manager's draft.\n")
    os.makedirs(os.path.join(w, "partial", "materials"))
    with open(os.path.join(w, "plain"), "wb") as f:
        f.write(b"not a directory\n")
    t.watch(w, "additions", "workspace")
    t.watch(existing, "frozen", "existing candidate")
    watch_outsiders(t)
    dest = t.dest_path()
    t.watch(dest, "frozen", "answer destination")
    cand = specimen_g(dest)
    folded = folds_case(t.root)
    before = tree(existing)
    srv = Server(t, "collision", workspace=w)
    name = "assemble.collision.existing"
    reply = srv.call("existing-create", "assemble", cand.arguments("existing", create=True))
    t.eq(name + ".unchanged", tree(existing), before)
    result(t, name + ".create", reply, outcome="refused", reason="destination_exists", pointer="/destination", data=None)
    if not t.sabotage:
        result(t, name + ".dry", srv.call("existing-dry", "assemble", cand.arguments("existing")),
               outcome="refused", reason="destination_exists", pointer="/destination", data=None)
        for label in ("partial", "plain"):
            for mode, extra in (("dry", {}), ("create", {"create": True})):
                prior = tree(os.path.join(w, label))
                result(t, "assemble.collision.%s.%s" % (label, mode),
                       srv.call(label + "-" + mode, "assemble", cand.arguments(label, **extra)),
                       outcome="refused", reason="destination_exists", pointer="/destination", data=None)
                t.eq("assemble.collision.%s.%s.unchanged" % (label, mode), tree(os.path.join(w, label)), prior)
        missing = Candidate({k: v for k, v in cand.fields.items() if k != "model"}, cand.body, cand.guidance,
                            cand.directories, cand.files, SOURCES)
        value = result(t, "assemble.collision.order", srv.call("order", "assemble",
                       missing.arguments("existing", create=True)), outcome="refused", reason="candidate_invalid")
        t.eq("assemble.collision.order.data-keys", sorted(value.get("data") or {}), ["assessment"])
        reply = srv.call("order-assess", "assess", missing.assess_arguments(unread=True))
        t.eq("assemble.collision.order.assessment-before-reading", (value.get("data") or {}).get("assessment"),
             ((reply or {}).get("result", {}).get("structuredContent", {}).get("data")))
        if folded:
            result(t, "assemble.collision.alias", srv.call("alias", "assemble", cand.arguments("EXISTING", create=True)),
                   outcome="refused", reason="destination_exists", pointer="/destination", data=None)
        else:
            result(t, "assemble.collision.alias", srv.call("alias", "assemble", cand.arguments("EXISTING", create=True)),
                   writes={"state": "complete", "created": cand.created("EXISTING"), "incomplete": []})
            check_candidate(t, "assemble.collision.alias.tree", os.path.join(w, "EXISTING"), cand.tree())
        t.eq("assemble.collision.alias.existing-unchanged", tree(existing), before)
    srv.close()


@case("c21.assemble-refusals", ["C21", "C19", "C20"],
      "argument, name, overlap, candidate and source refusals in the specified order, with no writes")
def c_assemble_refusals(t):
    """Each call below is a creation unless named a dry run, against a frozen workspace; each
    refusal has null data (candidate_invalid: {assessment}) and writes none.
    input_invalid: CR in /fields/model, LF in /fields/destination, an integer
    /fields/limit-turns, a role array given as a string, an unknown /fields/colour, a
    /fields/stewart key, a string /create and an integer /files/0/from.
    candidate_path_invalid for the candidate name: empty, absolute, `.`, `..`, two components,
    `sources`, `STORE.json`, `stewart-return-cand`, `stw1:cand`. At /fields/destination: the
    candidate itself (also spelled with doubled slashes and `.` components), a path inside it
    and the workspace containing it; differing, `<W>/x/../cand` is not resolved and a sibling
    name sharing the prefix does not overlap, so both dry runs complete.
    candidate_invalid with {assessment}: a missing model, a relative front matter destination,
    a role entry with an extra member and a missing materials directory, each established
    before any source is read, so the assessment equals assess with every size zero and keeps
    material_bytes unchecked; and a non-UTF-8 source, whose diagnostic names its public name
    with null pointer, line and key.
    For sources: absolute, `..`, `.`, empty-component and `stw1:` names, a symlink, a FIFO, a
    file with two hard links, a file under a directory holding STORE.json and one under a
    stewart-return- directory refuse candidate_path_invalid; a missing source, the existing
    source spelled in another case (absent on every host) and an unreadable one (unprivileged
    only) refuse candidate_source_failed. Pointers: /destination for the candidate name,
    /files/<i>/from for a source. Order: a reserved name before a
    missing workspace; an overlap before a missing field; sources in files order (a symlink
    first, or a missing file first, decides the reason). Each call checks the workspace again:
    a store marker planted in it after launch refuses candidate_path_invalid with a null
    pointer, after a missing field's candidate_invalid and before an existing name's
    destination_exists, and the same call completes once the marker is removed; a workspace
    path that now names another directory refuses the same way."""
    w = build_workspace(t, "refusals")
    os.mkdir(os.path.join(w, "taken"))
    locked = os.path.join(w, "sources", "locked.txt")
    if os.geteuid() != 0:
        os.chmod(locked, 0)
        t.mode_exempt.add(locked)
        t.cleanup(lambda: os.chmod(locked, 0o600))
    t.watch(w, "frozen", "workspace")
    watch_outsiders(t)
    dest = t.dest_path()
    t.watch(dest, "frozen", "answer destination")
    g = specimen_g(dest)
    srv = Server(t, "refusals", workspace=w)

    def refuse(label, args, reason, pointer="any"):
        name = "assemble.refuse." + label
        value = result(t, name, srv.call(label, "assemble", args), outcome="refused", reason=reason, pointer=pointer,
                       data="any" if reason == "candidate_invalid" else None)
        return value

    base = g.arguments("cand", create=True)
    for label, change, pointer in (
            ("cr-model", ("fields", "model", "claude\ropus"), "/fields/model"),
            ("lf-destination", ("fields", "destination", dest + "\nx"), "/fields/destination"),
            ("integer-limit", ("fields", "limit-turns", 200), "/fields/limit-turns"),
            ("roles-string", ("fields", "material-roles", "[]"), "/fields/material-roles"),
            ("unknown-field", ("fields", "colour", "blue"), "/fields/colour"),
            ("stewart-field", ("fields", "stewart", "question/2"), "/fields/stewart"),
            ("string-create", ("create", None, "true"), "/create"),
            ("integer-from", ("files", None, [{"name": "materials/main.py", "from": 7}]), "/files/0/from")):
        args = json.loads(json.dumps(base))
        where, key, value = change
        if key is None:
            args[where] = value
        else:
            args[where][key] = value
        refuse("input." + label, args, "input_invalid", pointer)
    for label, destination in (("empty", ""), ("absolute", os.path.join(w, "cand")), ("dot", "."), ("dotdot", ".."),
                               ("two-components", "a/b"), ("sources", "sources"), ("store-marker", "STORE.json"),
                               ("package", "stewart-return-cand"), ("reference", "stw1:cand")):
        refuse("name." + label, g.arguments(destination, create=True), "candidate_path_invalid", "/destination")
    for label, answer in (("names-candidate", os.path.join(w, "cand")),
                          ("names-candidate-spelled", w + "//cand/."),
                          ("inside", os.path.join(w, "cand", "returns")), ("contains", w)):
        changed = Candidate(dict(g.fields, destination=answer), g.body, g.guidance, g.directories, g.files, SOURCES)
        refuse("overlap." + label, changed.arguments("cand", create=True), "candidate_path_invalid", "/fields/destination")
    for label, answer in (("unresolved", os.path.join(w, "x", "..", "cand")), ("sibling", os.path.join(w, "cand-sibling"))):
        changed = Candidate(dict(g.fields, destination=answer), g.body, g.guidance, g.directories, g.files, SOURCES)
        result(t, "assemble.refuse.no-overlap." + label, srv.call("no-overlap-" + label, "assemble",
                                                                    changed.arguments("cand")))
    invalid = [
        ("missing-model", Candidate({k: v for k, v in g.fields.items() if k != "model"}, g.body, g.guidance,
                                    g.directories, g.files, SOURCES), None),
        ("relative-destination", Candidate(dict(g.fields, destination="returns"), g.body, g.guidance,
                                           g.directories, g.files, SOURCES), None),
        ("role-extra-member", Candidate(dict(g.fields, **{"material-roles": [
            {"role": "subject", "source": "materials/main.py", "note": "extra"}]}), g.body, g.guidance,
            g.directories, g.files, SOURCES), None),
        ("missing-materials", Candidate(g.fields, g.body, g.guidance, ["materials/notes", "materials/void"],
                                        g.files, SOURCES), None),
        ("not-text", Candidate(g.fields, g.body, g.guidance, g.directories,
                               g.files + [("materials/bad.txt", "bad.bin")], SOURCES), "materials/bad.txt"),
    ]
    for label, cand, source in invalid:
        name = "assemble.refuse.invalid." + label
        value = refuse("invalid." + label, cand.arguments("cand", create=True), "candidate_invalid")
        data = value.get("data") or {}
        t.eq(name + ".data-keys", sorted(data), ["assessment"])
        assessed = data.get("assessment") or {}
        t.check(name + ".not-valid", assessed.get("valid") is False, assessed)
        if source is None:
            # Established before any source is read: every size counts as zero and
            # material_bytes stays unchecked (MANAGER-PREPARATION refusal order).
            reply = srv.call(label + "-assess", "assess", cand.assess_arguments(unread=True))
            expected = ((reply or {}).get("result", {}).get("structuredContent", {}).get("data") or {})
            t.check(name + ".assess-reply", bool(expected), reply)
            t.eq(name + ".assessment-before-reading", assessed, expected)
        else:
            rows = [d for d in assessed.get("defects", []) if d.get("source") == source]
            t.require(name + ".source-diagnostic", len(rows) == 1, assessed)
            t.eq(name + ".source-diagnostic.facts",
                 {k: rows[0].get(k) for k in ("reason", "severity", "pointer", "line", "key")},
                 {"reason": "material_not_text", "severity": "error", "pointer": None, "line": None, "key": None})
    for label, src, reason in (
            ("absolute", os.path.join(w, "sources", "a.py"), "candidate_path_invalid"),
            ("dotdot", "../sources/a.py", "candidate_path_invalid"),
            ("dot", "./a.py", "candidate_path_invalid"),
            ("empty-component", "notes//r.txt", "candidate_path_invalid"),
            ("reference", "stw1:a.py", "candidate_path_invalid"),
            ("symlink", "link.py", "candidate_path_invalid"),
            ("fifo", "pipe", "candidate_path_invalid"),
            ("hard-link", "h1.txt", "candidate_path_invalid"),
            ("store-ancestry", "pkg/x.txt", "candidate_path_invalid"),
            ("package-ancestry", "stewart-return-zz/x.txt", "candidate_path_invalid"),
            ("missing", "absent.txt", "candidate_source_failed"),
            ("case-alias", "A.PY", "candidate_source_failed")):
        files = [(n, src if n == "materials/main.py" else s) for n, s in g.files]
        cand = Candidate(g.fields, g.body, g.guidance, g.directories, files, dict(SOURCES, **{src: b""}))
        refuse("source." + label, cand.arguments("cand", create=True), reason, "/files/0/from")
    if os.geteuid() != 0:
        files = [(n, "locked.txt" if n == "materials/main.py" else s) for n, s in g.files]
        cand = Candidate(g.fields, g.body, g.guidance, g.directories, files, SOURCES)
        refuse("source.unreadable", cand.arguments("cand", create=True), "candidate_source_failed", "/files/0/from")
    else:
        t.skip_part("unreadable source", "running as root: permissions do not stop reads")
    # Refusal order (MANAGER-PREPARATION "Assemble").
    overlap_missing = Candidate({k: v for k, v in dict(g.fields, destination=os.path.join(w, "cand")).items()
                                 if k != "model"}, g.body, g.guidance, g.directories, g.files, SOURCES)
    refuse("order.overlap-before-candidate", overlap_missing.arguments("cand", create=True), "candidate_path_invalid",
           "/fields/destination")
    for label, first, second, reason in (("symlink-first", "link.py", "absent.txt", "candidate_path_invalid"),
                                         ("missing-first", "absent.txt", "link.py", "candidate_source_failed")):
        files = [("materials/one.txt", first), ("materials/two.txt", second)]
        cand = Candidate(g.fields, g.body, g.guidance, ["materials"], files, dict(SOURCES, **{first: b"", second: b""}))
        refuse("order." + label, cand.arguments("cand", create=True), reason, "/files/0/from")
    # Each assemble call checks the workspace again: with a store marker planted in it after
    # launch, a dry run refuses candidate_path_invalid with a null pointer. In the refusal order
    # that check follows candidate_invalid and precedes destination_exists. Once the marker is
    # gone, the same call completes (differing).
    marker = os.path.join(w, "STORE.json")
    t.driver_change("plant a store marker in the workspace after launch",
                    lambda: open(marker, "wb").close())
    refuse("workspace-recheck", g.arguments("cand"), "candidate_path_invalid", None)
    refuse("workspace-recheck.before-existing", g.arguments("taken", create=True), "candidate_path_invalid", None)
    missing = Candidate({k: v for k, v in g.fields.items() if k != "model"}, g.body, g.guidance, g.directories,
                        g.files, SOURCES)
    refuse("workspace-recheck.after-candidate", missing.arguments("cand"), "candidate_invalid")
    t.driver_change("remove the planted store marker", lambda: os.unlink(marker))
    result(t, "assemble.refuse.workspace-recheck.restored", srv.call("recheck-restored", "assemble", g.arguments("cand")))
    refuse("existing", g.arguments("taken", create=True), "destination_exists", "/destination")
    # A DIR that now names another directory: the launched workspace moved away and a new
    # directory created at its path.
    moved = w + "-moved"
    t.driver_change("replace the workspace directory", lambda: (os.rename(w, moved), os.mkdir(w)))
    t.cleanup(lambda: (os.rmdir(w), os.rename(moved, w)) if os.path.isdir(moved) else None)
    refuse("workspace-replaced", g.arguments("cand"), "candidate_path_invalid", None)
    srv.close()
    bare = Server(t, "refusals-no-workspace")
    result(t, "assemble.refuse.order.name-before-workspace",
           bare.call("name-first", "assemble", g.arguments("sources", create=True)),
           outcome="refused", reason="candidate_path_invalid", pointer="/destination", data=None)
    bare.close()


def launch(t, name, workspace_arg, *, cwd=None):
    """Start the server with --workspace and a regular file as stdin holding initialize and
    initialized; return (result, stdin offset after exit, stdin length). The offset is the
    shared file position, so it shows whether the process read stdin."""
    data = compact(INITIALIZE) + b"\n" + compact(INITIALIZED) + b"\n"
    path = os.path.join(t.root, "%s.stdin" % name)
    with open(path, "wb") as f:
        f.write(data)
    argv = [t.bin["path"], "manager-mcp", "--workspace", workspace_arg]
    env = t.env()
    t.sync("before " + name)
    with open(path, "rb") as stream:
        proc = Proc(argv, env, cwd or t.cwd, 30, stdin=stream)
        res = proc.wait()
        offset = os.lseek(stream.fileno(), 0, os.SEEK_CUR)
    t.sync("after " + name, readonly=True)
    t._record(name, "manager-mcp", argv, env, cwd or t.cwd, res, None, False)
    return res, offset, len(data)


@case("c21.assemble-launcher", ["C21", "C18", "C20"],
      "--workspace refuses relative, missing, non-directory, store and package locations before reading stdin")
def c_assemble_launcher(t):
    """A relative DIR (an existing directory named relative to the working directory), a
    missing one, a regular file, a directory inside a Stewart store (an audit directory of a
    real archive) and a directory below a stewart-return- package directory are each a usage
    error: the reason on stderr, exit 2, nothing on stdout and stdin unread (its shared file
    offset still 0). Differing: an existing absolute workspace, and a symlink naming one
    (symlinks are followed), read stdin to its end, answer initialize and exit 0 at EOF. The
    store check walks the actual parent chain, so a symlink naming a directory inside the
    store is still a usage error; the package check reads DIR's components as given, so a
    symlink naming a directory below a stewart-return- directory is accepted. The offset
    witness is a driver control: it must observe each accepted launch's reading."""
    watch_outsiders(t)
    rel_target = "relative-ws"
    t.driver_change("make a directory relative to the working directory",
                    lambda: os.mkdir(os.path.join(t.cwd, rel_target)))
    plain = os.path.join(t.mkdir("launcher files"), "plain")
    with open(plain, "wb") as f:
        f.write(b"x\n")
    sub = t.submission([F("a.txt", b"a\n")])
    t.new_ref(sub, name="launcher.new")
    package = t.mkdir("returns", "stewart-return-aaaaaaaaaaaaaaaaa-001", "ws")
    good = t.mkdir("good workspace")
    t.watch(good, "frozen", "good workspace")
    links = t.mkdir("links")
    good_link, store_link = os.path.join(links, "to-good"), os.path.join(links, "to-store")
    package_link = os.path.join(links, "to-package")
    os.symlink(good, good_link)
    os.symlink(sub.audit_dir, store_link)
    os.symlink(package, package_link)
    for label, arg in (("relative", rel_target), ("missing", os.path.join(t.root, "absent workspace")),
                       ("file", plain), ("inside-store", sub.audit_dir), ("inside-package", package),
                       ("symlink-into-store", store_link)):
        name = "launcher." + label
        res, offset, _ = launch(t, name, arg)
        t.eq(name + ".exit", res["rc"], 2)
        t.eq(name + ".stdout", res["stdout"], b"")
        t.check(name + ".stderr-reason", res["stderr"].strip() != b"", res["stderr"])
        t.eq(name + ".stdin-unread", offset, 0)
    for label, arg in (("absolute", good), ("symlink", good_link), ("symlink-into-package", package_link)):
        name = "launcher.accepted-" + label
        res, offset, size = launch(t, name, arg)
        t.eq(name + ".exit", res["rc"], 0)
        lines = res["stdout"].split(b"\n")
        t.check(name + ".initialized", bool(lines) and b'"protocolVersion"' in lines[0], res["stdout"][:300])
        t.driver_control("stdin-offset-observes-reading-" + label, offset == size, {"offset": offset, "size": size})


@case("c21.assemble-concurrent", ["C21", "C6"],
      "two servers racing for one candidate name have exactly one winner",
      mode="test", faults=("candidate.after_entry:1=pause",))
def c_assemble_concurrent(t):
    """Server A creates `race` and pauses at candidate.after_entry:1, after claiming only the
    candidate directory. Server B then refuses `race` with destination_exists in a dry run and
    at creation (writes none), while its creation of `race-other` completes (differing: a
    different name has its own winner). Released, A completes with every entry; the candidate
    holds A's exact bytes and nothing from B."""
    w = build_workspace(t, "race")
    t.watch(w, "additions", "workspace")
    t.watch(os.path.join(w, "sources"), "frozen", "sources")
    watch_outsiders(t)
    dest = t.dest_path()
    cand = specimen_g(dest)
    a = Server(t, "race-a", workspace=w, fault="candidate.after_entry:1=pause")
    a.send(mcp_call("create", "assemble", cand.arguments("race", create=True)))
    stem = t.wait_paused("candidate.after_entry", a.handle, timeout=60)
    t.require("assemble.race.paused", stem is not None, "server A did not pause after claiming the candidate")
    try:
        t.eq("assemble.race.claimed-only", tree(os.path.join(w, "race")), {})
        b = Server(t, "race-b", workspace=w)
        result(t, "assemble.race.b-dry", b.call("dry", "assemble", cand.arguments("race")),
               outcome="refused", reason="destination_exists", pointer="/destination", data=None)
        lost = result(t, "assemble.race.b-create", b.call("create", "assemble", cand.arguments("race", create=True)),
                      outcome="refused", reason="destination_exists", pointer="/destination", data=None)
        result(t, "assemble.race.b-other", b.call("other", "assemble", cand.arguments("race-other", create=True)),
               writes={"state": "complete", "created": cand.created("race-other"), "incomplete": []})
        b.close()
    finally:
        t.release(stem)
    won = result(t, "assemble.race.a", a.reply("create", 90),
                 writes={"state": "complete", "created": cand.created("race"), "incomplete": []})
    a.close()
    t.eq("assemble.race.one-winner", [won.get("outcome"), lost.get("outcome")], ["completed", "refused"])
    check_candidate(t, "assemble.race.tree", os.path.join(w, "race"), cand.tree())
    check_candidate(t, "assemble.race.other-tree", os.path.join(w, "race-other"), cand.tree())


@case("c21.assemble-interrupted", ["C21", "C17", "C6"],
      "a creation killed after an entry leaves its partial, loses its reply, and a retry needs a fresh name",
      mode="test", faults=("candidate.after_entry:5=kill",))
def c_assemble_interrupted(t):
    """candidate.after_entry:5=kill ends the server after the candidate, its three directories
    and guidance.md (entry 5, written and verified): no reply arrives and the process dies by
    SIGKILL. Ordinary file reads then show exactly those entries, guidance.md with its witness
    bytes and nothing else. A new server refuses the same name with destination_exists in a
    dry run and at creation and leaves the partial unchanged; a fresh name creates the complete
    candidate."""
    w = build_workspace(t, "cut")
    t.watch(w, "additions", "workspace")
    t.watch(os.path.join(w, "sources"), "frozen", "sources")
    watch_outsiders(t)
    dest = t.dest_path()
    cand = specimen_g(dest)
    srv = Server(t, "cut", workspace=w, fault="candidate.after_entry:5=kill")
    reply = srv.call("create", "assemble", cand.arguments("cut", create=True), timeout=60)
    res = srv.close(expect_rc=None)
    t.eq("assemble.cut.lost-reply", reply, None)
    t.eq("assemble.cut.killed", res["rc"], -signal.SIGKILL)
    expected = {"materials": None, "materials/notes": None, "materials/void": None,
                "guidance.md": cand.all_files["guidance.md"]}
    check_candidate(t, "assemble.cut.partial", os.path.join(w, "cut"), expected)
    partial = tree(os.path.join(w, "cut"))
    again = Server(t, "cut-retry", workspace=w)
    result(t, "assemble.cut.retry-dry", again.call("dry", "assemble", cand.arguments("cut")),
           outcome="refused", reason="destination_exists", pointer="/destination", data=None)
    result(t, "assemble.cut.retry-create", again.call("create", "assemble", cand.arguments("cut", create=True)),
           outcome="refused", reason="destination_exists", pointer="/destination", data=None)
    t.eq("assemble.cut.partial-preserved", tree(os.path.join(w, "cut")), partial)
    result(t, "assemble.cut.fresh", again.call("fresh", "assemble", cand.arguments("cut-2", create=True)),
           writes={"state": "complete", "created": cand.created("cut-2"), "incomplete": []})
    again.close()
    check_candidate(t, "assemble.cut.fresh-tree", os.path.join(w, "cut-2"), cand.tree())


@case("c21.assemble-write-failures", ["C21", "C17", "C6"],
      "failed writes and verifications report failed with the exact created and incomplete entries and stop",
      mode="test",
      controls=[Control("candidate_unreported_partial",
                        [r"^assemble\.fail\.[a-z-]+\.writes\.(state|created|incomplete)$"])],
      faults=("candidate.entry_write:materials/main.py=eio", "candidate.entry_corrupt:question.md=corrupt",
              "candidate.after_entry:2=eio"))
def c_assemble_write_failures(t):
    """Each failure is outcome failed, reason candidate_write_failed, with the dry run's data
    and writes partial; nothing proposed after the failure point exists afterwards and the
    candidate is unchanged when the server closes.
    candidate.entry_write:materials/main.py=eio: created lists the candidate, its directories
    and the files before materials/main.py; incomplete lists materials/main.py only, which
    remains as an empty file.
    candidate.entry_corrupt:question.md=corrupt: created lists every entry but question.md;
    incomplete lists question.md, which remains for inspection.
    candidate.after_entry:2=eio: created lists the candidate and materials, nothing is
    incomplete. The control runs the first failure."""
    w = build_workspace(t, "fail")
    t.watch(w, "additions", "workspace")
    t.watch(os.path.join(w, "sources"), "frozen", "sources")
    watch_outsiders(t)
    dest = t.dest_path()
    cand = specimen_g(dest)
    order = cand.created("x")
    specimens = [("write", "candidate.entry_write:materials/main.py=eio", "materials/main.py"),
                 ("corrupt", "candidate.entry_corrupt:question.md=corrupt", "question.md"),
                 ("after-entry", "candidate.after_entry:2=eio", None)]
    for label, fault, failing in specimens[:1] if t.sabotage else specimens:
        name = "assemble.fail." + label
        destination = "fail-" + label
        srv = Server(t, "fail-" + label, workspace=w, fault=fault)
        dry = result(t, name + ".dry", srv.call("dry", "assemble", cand.arguments(destination)))
        value = result(t, name, srv.call("create", "assemble", cand.arguments(destination, create=True)),
                       outcome="failed", reason="candidate_write_failed", pointer=None, writes=None)
        t.eq(name + ".data", value.get("data"), dry.get("data"))
        writes = value.get("writes") or {}
        everything = [destination + p[1:] for p in order]
        if failing is None:
            created, incomplete = everything[:2], []
        else:
            stop = everything.index(destination + "/" + failing)
            created, incomplete = everything[:stop], [destination + "/" + failing]
        t.eq(name + ".writes.state", writes.get("state"), "partial")
        t.eq(name + ".writes.created", writes.get("created"), created)
        t.eq(name + ".writes.incomplete", writes.get("incomplete"), incomplete)
        root = os.path.join(w, destination)
        later = everything[len(created) + len(incomplete):]
        t.eq(name + ".nothing-later", [p for p in later if os.path.lexists(os.path.join(w, p))], [])
        for p in incomplete:
            left = os.path.join(w, p)
            if t.check(name + ".incomplete-left", os.path.isfile(left), sorted((tree(root) or {}))) and label == "write":
                # Appendix C.1: the fault fires after the exclusive create and before any byte.
                t.eq(name + ".empty-file-left", read_bytes(left), b"")
        expected_created = {p[len(destination) + 1:]: cand.tree()[p[len(destination) + 1:]]
                            for p in created if p != destination}
        for rel, data in sorted(expected_created.items()):
            got = (tree(root) or {}).get(rel)
            t.eq(name + ".created-entry." + rel, (got or ("missing",))[:3],
                 ("dir", 0o700, None) if data is None else ("file", 0o600, sha256_hex(data)))
        at_reply = tree(root)
        srv.close()
        t.eq(name + ".no-further-writes", tree(root), at_reply)


# ---------------------------------------------------------------------------
# Self-tests: the witness against MANAGER-PREPARATION's own example and rules.
# ---------------------------------------------------------------------------

@selftest
def assemble_witness_selftests():
    out = []
    empty = specimen_empty("/home/ana/returns")
    want = (b"---\nstewart: question/2\ndestination: /home/ana/returns\nfamily: open-inquiry\n"
            b"limit-input-tokens: 32000\nlimit-output-tokens: 8000\nlimit-turns: 4\nmodel: example-model\n"
            b"---\nWhat can these materials establish?")
    out.append(("assemble.witness.example-question", empty.question == want, empty.question))
    out.append(("assemble.witness.example-arguments", empty.arguments("first-inquiry") == json.loads(
        '{"fields":{"family":"open-inquiry","model":"example-model","destination":"/home/ana/returns",'
        '"limit-turns":"4","limit-input-tokens":"32000","limit-output-tokens":"8000"},'
        '"body":"What can these materials establish?","guidance":null,"directories":["materials"],'
        '"files":[],"destination":"first-inquiry"}')))
    c = specimen_c("/r")
    roles_line = [line for line in c.question.split(b"\n") if line.startswith(b"material-roles: ")]
    out.append(("assemble.witness.role-order", roles_line == [
        'material-roles: [{"role":"alternative","source":"materials/a.py","label":"Option \\"A\\" \\\\ \u00c4"},'
        '{"role":"alternative","source":"materials/b.py","label":"Opci\u00f3n B"},'
        '{"role":"criterion","source":"materials/criteria/rider.txt"}]'.encode("utf-8")], roles_line))
    escapes = json_string('q"b\\\b\f\n\r\t\u0001\u001f\u007f\u00e9/')
    out.append(("assemble.witness.string-escapes",
                escapes == '"q\\"b\\\\\\b\\f\\n\\r\\t\\u0001\\u001f\u007f\u00e9/"', escapes))
    extra = encode_roles([{"note": "n", "source": "s", "role": "r"}])
    out.append(("assemble.witness.role-extra-member-last", extra == '[{"role":"r","source":"s","note":"n"}]', extra))
    keys = [line.split(b":")[0] for line in c.question.split(b"\n")[2:9]]
    out.append(("assemble.witness.bytewise-key-order", keys == [b"destination", b"family", b"limit-input-tokens",
                                                              b"limit-output-tokens", b"limit-turns",
                                                              b"material-roles", b"model"], keys))
    g = specimen_g("/r")
    names = [row["name"] for row in g.rows]
    out.append(("assemble.witness.name-byte-order", names == [
        "guidance.md", "materials/.hidden.txt", "materials/Z-upper.txt", "materials/bom.txt", "materials/empty.txt",
        "materials/main.py", "materials/notes/r.txt", "question.md"], names))
    created = g.created("cand")
    out.append(("assemble.witness.creation-order", created[:4] == ["cand", "cand/materials", "cand/materials/notes",
                                                                    "cand/materials/void"]
                and created[-1] == "cand/question.md" and len(created) == 12, created))
    out.append(("assemble.witness.body-exact", g.question.endswith(b"---\nCan one reminder be sent twice?\r\n"
                                                                    b"Cover what happens across a restart."), g.question))
    out.append(("assemble.witness.no-body-newline-added", not empty.question.endswith(b"\n")))
    differing = Candidate(dict(g.fields, model="other-model"), g.body, g.guidance, g.directories, g.files, SOURCES)
    out.append(("assemble.witness.differing-field", differing.question != g.question
                and differing.rows[:-1] == g.rows[:-1], differing.question))
    return out
