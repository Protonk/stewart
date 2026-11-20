"""The manager walkthroughs and the worked packets, run against the binary with the documents as
the oracle. Written from examples/manager/README.md, FILE-ONLY.md and WITH-MCP.md, the worked
examples of examples/questions, INTERFACE 1.7, 5.4, 5.7 and 8.2, MANAGER-PREPARATION and ACCEPTANCE
C21, without reading service/.

The walkthrough documents are read at run time and executed as written: each `$ stewart` command
runs with the release binary, its standard output is compared line by line with the block below it
after the actual binary, home, reference and handle are written as the documents write them
(/usr/local/bin/stewart, /home/ana, REF, HANDLE), and every MCP reply is compared with the members
the document shows. README's reading rules apply: `…` within a line is any value, a line of only
`…` is any run of lines, and an MCP object may leave members out. A mismatch is reported as the
document's line beside the binary's.
"""
import glob
import json
import os
import re
import shutil
import subprocess

import fake_provider as fp
import run_support as rs
from cases_manager_mcp_assemble import Server
from driver_core import Skip, case, read_bytes, selftest, sha256_hex, short, strict_loads
from procedure import Procedure

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EXAMPLES = os.path.join(REPO, "examples")
MANAGER_DOCS = os.path.join(EXAMPLES, "manager")
DOC_BINARY = "/usr/local/bin/stewart"
DOC_HOME = "/home/ana"
ELLIPSIS = "…"
ANY = "\u0000any"          # a bare `…` in a shown JSON value
PACKETS = ("open", "framing", "comparison")
# README "What the outputs show": the stand-in's second run answers four requests, grouped so.
RUN2_GROUPS = (("list", "read", "read", "read"), ("record_observation", "record_account", "record_limit"),
               ("prepare",), ("read", "submit"))
RUN1_ATTEMPTS = 4
RUN2_USAGE = (3000, 400)
# The auditor walkthrough's replies shown whole, with no `…` (the record replies elide citations
# and carry illustrative handles; prepare's handle is replaced by the one Stewart returns).
SHOWN_WHOLE = ("list", "read", "prepare")


def examples_present():
    return all(os.path.isfile(os.path.join(MANAGER_DOCS, n)) for n in ("README.md", "FILE-ONLY.md", "WITH-MCP.md"))


def need_examples():
    if not examples_present():
        raise Skip("examples/ is not beside the driver: the walkthroughs and worked packets are its oracle")


# ---------------------------------------------------------------------------
# Reading the documents.
# ---------------------------------------------------------------------------

class Block:
    """One fenced block: its language, the document line of its first content line, its lines and
    the prose since the previous block."""

    def __init__(self, doc, lang, line, lines, prose):
        self.doc, self.lang, self.line, self.lines, self.prose = doc, lang, line, lines, prose

    @property
    def text(self):
        return "\n".join(self.lines)

    def numbered(self, start=0, stop=None):
        stop = len(self.lines) if stop is None else stop
        return [(self.line + i, self.lines[i]) for i in range(start, stop)]


def blocks_of(text, doc):
    lines = text.split("\n")
    out, prose, i = [], [], 0
    while i < len(lines):
        m = re.match(r"^```(\w*)\s*$", lines[i])
        if not m:
            prose.append(lines[i])
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j].rstrip() != "```":
            j += 1
        out.append(Block(doc, m.group(1), i + 2, lines[i + 1:j], "\n".join(prose)))
        prose, i = [], j + 1
    return out


def read_doc(*parts):
    with open(os.path.join(EXAMPLES, *parts), encoding="utf-8") as f:
        return f.read()


def section(text, heading):
    """The text from a `## heading` line to the next `## ` line outside a fenced block."""
    out, inside, fenced = [], False, False
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            if inside:
                break
            inside = line == "## " + heading
        if inside:
            out.append(line)
    if not out:
        raise ValueError("no section %r" % heading)
    return "\n".join(out)


class Command:
    """A `$ ` line of a text block and the output lines shown below it."""

    def __init__(self, block, index, argv, expected):
        self.block, self.index, self.argv, self.expected = block, index, argv, expected

    @property
    def line(self):
        return self.block.line + self.index

    @property
    def stewart(self):
        return self.argv[0] == "stewart"


def commands_of(block):
    out, cur = [], None
    for i, line in enumerate(block.lines):
        if line.startswith("$ "):
            cur = Command(block, i, line[2:].split(), [])
            out.append(cur)
        elif cur is not None:
            cur.expected.append((block.line + i, line))
    return out


# ---------------------------------------------------------------------------
# README's reading rules.
# ---------------------------------------------------------------------------

def line_regex(text):
    return re.compile("^" + ".*".join(re.escape(p) for p in text.split(ELLIPSIS)) + "$", re.S)


def match_lines(expected, actual):
    """None when the binary's lines match the shown ones, else (doc line number, doc line, binary
    line) at the furthest point the match reached. A shown line of only `…` stands for any run of
    lines, none included; `…` within a line for any value."""
    pats = [None if text.strip() == ELLIPSIS else line_regex(text) for _, text in expected]
    n, m = len(pats), len(actual)
    seen, todo, best = set(), [(0, 0)], (0, 0)
    while todo:
        i, j = todo.pop()
        if (i, j) in seen:
            continue
        seen.add((i, j))
        best = max(best, (i, j))
        if i == n:
            if j == m:
                return None
            continue
        if pats[i] is None:
            todo.append((i + 1, j))
            if j < m:
                todo.append((i, j + 1))
        elif j < m and pats[i].match(actual[j]):
            todo.append((i + 1, j + 1))
    i, j = best
    doc_no, doc_line = expected[i] if i < n else (expected[-1][0] + 1 if expected else None, "<end of the block>")
    return doc_no, doc_line, actual[j] if j < m else "<end of the output>"


def shown_json(text):
    """A shown JSON value whose bare `…` (outside strings) stands for any value."""
    out, in_str, esc = [], False, False
    for ch in text:
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif ch == ELLIPSIS:
            out.append(json.dumps(ANY))
        else:
            out.append(ch)
    return json.loads("".join(out))


def value_diff(shown, actual, partial, path=""):
    """None when actual has every shown value: objects equal (partial: the shown members only),
    arrays equal in length and element by element, a string with `…` matching any text there,
    and ANY anything. Else (pointer, shown, actual)."""
    if shown == ANY:
        return None
    if isinstance(shown, dict):
        if not isinstance(actual, dict) or (not partial and sorted(shown) != sorted(actual)):
            return path or "/", shown, actual
        for k, v in shown.items():
            if k not in actual:
                return path + "/" + k, v, "<missing>"
            d = value_diff(v, actual[k], partial, path + "/" + k)
            if d:
                return d
        return None
    if isinstance(shown, list):
        if not isinstance(actual, list) or len(actual) != len(shown):
            return path or "/", shown, actual
        for i, (a, b) in enumerate(zip(shown, actual)):
            d = value_diff(a, b, partial, "%s/%d" % (path, i))
            if d:
                return d
        return None
    if isinstance(shown, str) and ELLIPSIS in shown:
        ok = isinstance(actual, str) and line_regex(shown).match(actual)
        return None if ok else (path or "/", shown, actual)
    same = type(shown) is type(actual) and shown == actual
    return None if same else (path or "/", shown, actual)


# ---------------------------------------------------------------------------
# One walkthrough's home.
# ---------------------------------------------------------------------------

class Home:
    """The directory standing for /home/ana in one walkthrough, the binary standing for
    /usr/local/bin/stewart, and the reference and handle once printed."""

    def __init__(self, t, label):
        self.t, self.label = t, label
        self.path = os.path.realpath(t.mkdir(label))
        self.ref = self.handle = None
        self.fx = self.auditor = None
        self.diag_offset = 0
        self.prepare_out = None
        self.machine = None

    def doc_text(self, text):
        for actual, shown in ((self.ref, "REF"), (self.handle, "HANDLE"), (self.t.bin["path"], DOC_BINARY),
                              (self.path, DOC_HOME)):
            if actual:
                text = text.replace(actual, shown)
        return text

    def doc_value(self, v):
        if isinstance(v, str):
            return self.doc_text(v)
        if isinstance(v, list):
            return [self.doc_value(x) for x in v]
        if isinstance(v, dict):
            return {k: self.doc_value(x) for k, x in v.items()}
        return v

    def actual(self, text):
        return text.replace(DOC_HOME, self.path)

    def arg(self, a):
        if a == "REF":
            return self.ref
        if a == "HANDLE":
            return self.handle
        return self.actual(a)

    def run_env(self):
        return rs.run_env(self.t, self.fx)


def setup_command(t, h, cmd, name):
    """A cp or mkdir line of the walkthrough, run as written from the repository root with the
    home in place of /home/ana; the shell's glob is expanded here."""
    tool = shutil.which(cmd.argv[0], path="/usr/bin:/bin")
    t.require(name + ".tool", cmd.argv[0] in ("cp", "mkdir") and tool, cmd.argv)
    argv = [tool]
    for a in cmd.argv[1:]:
        a = h.actual(a)
        if "*" in a:
            hits = sorted(glob.glob(a if os.path.isabs(a) else os.path.join(REPO, a)))
            t.require(name + ".glob", hits, a)
            argv += hits
        else:
            argv.append(a)
    res = subprocess.run(argv, cwd=REPO, env={"PATH": "/usr/bin:/bin"}, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    t.require(name + ".done", res.returncode == 0 and not cmd.expected,
              {"argv": argv, "rc": res.returncode, "stderr": res.stderr[-400:]})


def doc_exit(expected):
    """The exit status a shown reply implies (INTERFACE 1.7; FILE-ONLY: an interrupted run exits 5)."""
    m = re.match(r"^(?:Command )?stewart (\S+): (completed|refused|failed)", expected[0][1] if expected else "")
    if not m:
        return None
    if m.group(2) != "completed":
        return {"refused": 3, "failed": 4}[m.group(2)]
    interrupted = m.group(1) == "run" and any(" was interrupted" in line for _, line in expected)
    return 5 if interrupted else 0


def stewart_command(t, h, cmd, name):
    """Run one `$ stewart` line and compare its output with the block's."""
    args = [h.arg(a) for a in cmd.argv[1:]]
    t.require(name + ".placeholders-known", all(a is not None for a in args), cmd.argv)
    expected = [(no, re.sub(r"/diag/(\d+)\.json", lambda m: "/diag/%d.json" % (int(m.group(1)) - h.diag_offset), text))
                for no, text in cmd.expected]
    contacts = len(h.fx.exchanges)
    rep = t.cmd(args, json_reply=False, envelope=False, env=h.run_env(), name=name, writer=None, timeout=300)
    out = rep.stdout.decode("utf-8", "replace")
    if args[0] == "new":
        m = re.search(r"^reference: (\S+)$", out, re.M)
        t.require(name + ".reference", m, out[:400])
        h.ref = m.group(1)
    if args[0] == "prepare" and rep.rc == 0:
        m = re.search(r"^prepared: (\S+)$", out, re.M)
        t.require(name + ".handle", m, out[:400])
        h.handle = m.group(1)
        h.prepare_out = h.doc_text(out)
        m = re.search(r"^  machine: (.+)$", out, re.M)
        h.machine = m.group(1) if m else None
    lines = h.doc_text(out).split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    miss = match_lines(expected, lines)
    t.check(name + ".output", miss is None, None if miss is None else
            {"doc": "%s:%s: %s" % (cmd.block.doc, miss[0], miss[1]), "binary": miss[2], "command": " ".join(cmd.argv)})
    # Firing control: the same output against the block with one shown line changed.
    k = next((i for i, (_, text) in enumerate(expected) if text.strip() != ELLIPSIS), None)
    if k is not None:
        changed = list(expected)
        changed[k] = (changed[k][0], changed[k][1] + " [control]")
        t.check(name + ".output.control-fires", match_lines(changed, lines) is not None, changed[k])
    t.eq(name + ".exit", rep.rc, doc_exit(cmd.expected))
    if args[0] != "run":
        t.eq(name + ".no-provider-contact", len(h.fx.exchanges), contacts)
    return rep


# ---------------------------------------------------------------------------
# The stand-in provider (README "What the outputs show").
# ---------------------------------------------------------------------------

def auditor_calls():
    """The open walkthrough's auditor calls, in order: (tool, input) with the input's member order,
    and the shown reply data of the calls whose data is shown whole."""
    text = section(read_doc("questions", "open", "WALKTHROUGH.md"), "Auditor walkthrough")
    calls, dec = [], json.JSONDecoder()
    for b in blocks_of(text, "open/WALKTHROUGH.md"):
        if b.lang != "text":
            continue
        joined = b.text
        for m in re.finditer(r"^(\w+)\(", joined, re.M):
            value, end = dec.raw_decode(joined, m.end())
            shown = None
            r = re.compile(r"\)[^\n]*\n=> ").match(joined, end)
            if r and m.group(1) in SHOWN_WHOLE:
                shown = dec.raw_decode(joined, r.end())[0]
            calls.append((m.group(1), value, shown))
    return calls


def open_body():
    """The open example's question body, the bytes every run's first message and return carry."""
    return read_doc("questions", "open", "submission", "question.md").split("\n---\n", 1)[1].encode("utf-8")


def rendering_block():
    text = section(read_doc("questions", "open", "WALKTHROUGH.md"), "Readable return")
    b = [x for x in blocks_of(text, "open/WALKTHROUGH.md") if x.lang == "markdown"]
    return (b[0].text + "\n").encode("utf-8") if b else None


def stand_in(t, h):
    """Run 1: every request 529 overloaded_error "Overloaded", retry-after 0 (four attempts). Run 2:
    the open walkthrough's calls in README's four responses, each reporting 3,000 input and 400
    output tokens, with the prepared handle Stewart actually returned."""
    calls = auditor_calls()
    names = [c[0] for c in calls]
    t.require(h.label + ".auditor-calls", names == [n for g in RUN2_GROUPS for n in g], names)
    doc_prepared = calls[7][2].get("prepared") if isinstance(calls[7][2], dict) else None

    def swap(v, actual):
        if isinstance(v, str) and doc_prepared and v.startswith(doc_prepared):
            return actual + v[len(doc_prepared):]
        if isinstance(v, dict):
            return {k: swap(x, actual) for k, x in v.items()}
        return v

    def body(p):
        k, prepared = 0, None
        for group in RUN2_GROUPS:
            group_calls = calls[k:k + len(group)]
            k += len(group)
            turn = yield p.calls_step(*[(c[0], swap(c[1], prepared) if prepared else c[1]) for c in group_calls],
                                      usage=fp.Usage(*RUN2_USAGE))
            if group[-1] == "submit":
                return
            for i, (tool, _, shown) in enumerate(group_calls):
                r = turn.reply(i)
                p.check("reply-%s-%d.completed" % (tool, i), r is not None and r.outcome == "completed",
                        r.summary() if r is not None else None)
                if r is None:
                    continue
                if tool == "prepare":
                    prepared = r.data.get("prepared")
                if isinstance(shown, dict):
                    want = swap(shown, prepared) if tool == "prepare" else shown
                    p.eq("reply-%s-%d.data-as-shown" % (tool, i), r.data, want)

    proc = Procedure(body, name="walkthrough-auditor")
    h.auditor = proc
    overloaded = [fp.HttpError(529, "overloaded_error", "Overloaded", retry_after=0) for _ in range(RUN1_ATTEMPTS)]
    h.fx = rs.provider(t, fp.Script(overloaded, then=proc), label=h.label)


# ---------------------------------------------------------------------------
# FILE-ONLY.
# ---------------------------------------------------------------------------

def file_only_steps():
    doc = "FILE-ONLY.md"
    steps = []
    for b in blocks_of(read_doc("manager", doc), doc):
        if b.lang == "text" and any(line.startswith("$ ") for line in b.lines):
            steps += [("command", c) for c in commands_of(b)]
        elif b.lang == "text" and len(b.lines) == 1 and b.lines[0].startswith("destination: "):
            steps.append(("edit", b))
        elif b.lang == "text" and b.lines and b.lines[0].endswith("/"):
            steps.append(("listing", b))
        elif b.lang == "json" and "`stewart status REF --json`" in b.prose and "data.headline" in b.prose:
            steps.append(("headline", b))
        else:
            steps.append(("unknown", b))
    return steps


def edit_destination(t, h, b, name):
    """FILE-ONLY step 2: the one front matter line naming the destination, edited as shown."""
    q = os.path.join(h.path, "reminders", "question.md")
    with open(q, encoding="utf-8") as f:
        lines = f.read().split("\n")
    hits = [i for i, line in enumerate(lines) if line.startswith("destination:")]
    t.require(name + ".one-destination-line", len(hits) == 1, hits)
    lines[hits[0]] = h.actual(b.lines[0])
    with open(q, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def check_listing(t, h, b, name, question_body):
    """FILE-ONLY step 8: one package in the destination with exactly the listed members and the
    sizes shown; answer.md is the auditor walkthrough's rendering, question.md the accepted body,
    and the manifest names the auditor as sealer and binds every member's size and digest."""
    first = h.actual(b.lines[0].rstrip("/"))
    parent, pattern = os.path.dirname(first), line_regex(os.path.basename(first))
    found = sorted(n for n in os.listdir(parent) if pattern.match(n)) if os.path.isdir(parent) else []
    t.require(name + ".package", len(found) == 1, {"doc": "%s:%d: %s" % (b.doc, b.line, b.lines[0]), "found": found})
    pkg = os.path.join(parent, found[0])
    listed = {}
    for no, line in b.numbered(1):
        m = re.match(r"^  (\S+)(?:\s+(\d+) bytes)?$", line)
        t.require(name + ".listing-line", m, "%s:%d: %s" % (b.doc, no, line))
        listed[m.group(1)] = (no, None if m.group(2) is None else int(m.group(2)))
    t.eq(name + ".members", sorted(os.listdir(pkg)), sorted(listed))
    for member, (no, size) in listed.items():
        p = os.path.join(pkg, member)
        if size is not None and os.path.isfile(p):
            t.check(name + ".size." + member, os.path.getsize(p) == size,
                    {"doc": "%s:%d: %s" % (b.doc, no, b.lines[no - b.line]), "binary": os.path.getsize(p)})
    data = {m: read_bytes(os.path.join(pkg, m)) for m in listed if os.path.isfile(os.path.join(pkg, m))}
    rendering = rendering_block()
    t.eq(name + ".answer.md-is-the-walkthrough-rendering", data.get("answer.md"), rendering)
    t.eq(name + ".question.md-is-the-body", data.get("question.md"), question_body)
    try:
        manifest = strict_loads(data.get("manifest.json", b""))
    except Exception as exc:          # noqa: BLE001 - reported as the check
        manifest = {"unreadable": str(exc)}
    t.eq(name + ".manifest.sealer", (manifest.get("seal") or {}).get("actor"), "auditor")
    t.eq(name + ".manifest.members",
         [(x.get("name"), x.get("size"), x.get("sha256")) for x in manifest.get("members") or []],
         [(m, len(data[m]), sha256_hex(data[m])) for m in ("question.md", "answer.json", "answer.md") if m in data])
    return pkg, data


def follow_file_only(t, h, prefix, *, from_prepare=False):
    """Execute FILE-ONLY as written in this home. from_prepare: WITH-MCP's "follows files only from
    step 3" in a home whose destination already exists, so the steps before the first completing
    prepare (the destination refusal and the mkdir) do not apply, and the diagnostic numbers the
    later replies retain are fewer by the refusals skipped."""
    steps = file_only_steps()
    body = open_body()
    pkg = None
    started = not from_prepare
    for k, (kind, item) in enumerate(steps):
        name = "%s.%02d" % (prefix, k + 1)
        if not started:
            if kind == "command" and item.stewart and item.argv[1] == "prepare" and doc_exit(item.expected) == 0:
                started = True
            elif kind == "command" and item.stewart and item.argv[1] == "prepare":
                h.diag_offset += sum(1 for _, line in item.expected if re.search(r"/diag/\d+\.json$", line))
                continue
            else:
                continue
        if kind == "command" and item.stewart:
            stewart_command(t, h, item, "%s-%s" % (name, item.argv[1]))
        elif kind == "command":
            setup_command(t, h, item, "%s-%s" % (name, item.argv[0]))
        elif kind == "edit":
            edit_destination(t, h, item, name + "-edit")
        elif kind == "headline":
            rep = t.cmd(["status", h.ref], name=name + "-status-json", expect="completed", env=h.run_env())
            diff = value_diff(shown_json(item.text), h.doc_value(rep.data.get("headline")), False)
            t.check(name + "-status-json.headline", diff is None,
                    None if diff is None else {"doc": "%s:%d" % (item.doc, item.line), "pointer": diff[0],
                                               "shown": diff[1], "binary": diff[2]})
        elif kind == "listing":
            pkg = check_listing(t, h, item, name + "-return", body)
        else:
            t.check(name + ".doc-shape", False, "%s:%d: an unrecognized block" % (item.doc, item.line))
    t.check(prefix + ".reached-prepare", started, "no completing prepare in FILE-ONLY")
    rs.check_procedure(t, h.auditor, prefix + ".auditor", h.fx)
    return pkg


# ---------------------------------------------------------------------------
# WITH-MCP.
# ---------------------------------------------------------------------------

def tool_reply(t, name, reply):
    """A tools/call result carrying one object as structuredContent and as its JSON text."""
    t.require(name + ".reply", isinstance(reply, dict) and isinstance(reply.get("result"), dict), reply)
    res = reply["result"]
    value = res.get("structuredContent")
    content = res.get("content")
    t.require(name + ".structured", isinstance(value, dict), res)
    t.check(name + ".same-object-twice", isinstance(content, list) and len(content) == 1
            and isinstance(content[0], dict) and isinstance(content[0].get("text"), str)
            and strict_loads(content[0]["text"].encode("utf-8")) == value, content)
    t.eq(name + ".error-flag", res.get("isError"), value.get("outcome") != "completed")
    return value


def changed_leaf(v):
    """v with its first exactly shown scalar changed, or None when it has none."""
    if isinstance(v, dict):
        for k, x in v.items():
            y = changed_leaf(x)
            if y is not None:
                return dict(v, **{k: y})
        return None
    if isinstance(v, list):
        for i, x in enumerate(v):
            y = changed_leaf(x)
            if y is not None:
                return v[:i] + [y] + v[i + 1:]
        return None
    if v == ANY or (isinstance(v, str) and ELLIPSIS in v):
        return None
    if isinstance(v, bool):
        return not v
    if isinstance(v, (int, float)):
        return v + 1
    return "[control]" if v is None else v + " [control]"


def compare_shown(t, h, name, block, value):
    shown = shown_json(block.text)
    actual = h.doc_value(value)
    diff = value_diff(shown, actual, True)
    t.check(name + ".shown", diff is None, None if diff is None else
            {"doc": "%s:%d" % (block.doc, block.line), "pointer": diff[0], "shown": diff[1], "binary": diff[2]})
    # Firing control: the same reply against the shown members with one value changed.
    changed = changed_leaf(shown)
    t.check(name + ".shown.control-fires", changed is not None and value_diff(changed, actual, True) is not None)


def follow_with_mcp(t, h, prefix):
    """WITH-MCP steps 1-6: the setup lines, the server's exact handshake, discover, explain, the
    three assemble proposals, creation, the refused retry and `new` on the candidate."""
    doc = "WITH-MCP.md"
    bl = blocks_of(read_doc("manager", doc), doc)
    shape = [b.lang for b in bl]
    t.require(prefix + ".doc-shape", shape[:12] == ["text", "json", "json", "json", "json", "json", "json", "json",
                                                     "json", "json", "json", "text"], shape)
    setup = commands_of(bl[0])
    t.require(prefix + ".doc-shape.server-line", setup and setup[-1].argv[:2] == ["stewart", "manager-mcp"],
              [c.argv for c in setup])
    for k, cmd in enumerate(setup[:-1]):
        setup_command(t, h, cmd, "%s.setup-%d-%s" % (prefix, k + 1, cmd.argv[0]))
    server_args = [h.arg(a) for a in setup[-1].argv[2:]]
    t.require(prefix + ".server-args", server_args[:1] == ["--workspace"] and len(server_args) == 2, server_args)
    srv = Server(t, prefix + ".server", workspace=server_args[1], initialize=False)
    try:
        frames = [line for line in bl[1].lines if line.strip()]
        t.require(prefix + ".doc-shape.handshake", len(frames) == 2, frames)
        srv.send_raw(frames[0].encode("utf-8") + b"\n")
        init = srv.reply(json.loads(frames[0]).get("id"), 30)
        t.eq(prefix + ".initialize", init, json.loads(bl[2].text))
        srv.send_raw(frames[1].encode("utf-8") + b"\n")
        m = re.search(r'`(\{"jsonrpc":"2\.0","id":(\d+),"method":"tools/call"[^`]*\})`', bl[3].prose)
        t.require(prefix + ".doc-shape.discover-request", m, bl[3].prose[-300:])
        srv.send_raw(m.group(1).encode("utf-8") + b"\n")
        compare_shown(t, h, prefix + ".discover", bl[3], tool_reply(t, prefix + ".discover", srv.reply(int(m.group(2)))))
        m = re.search(r"`explain` with `(\{[^`]*\})`", bl[4].prose)
        t.require(prefix + ".doc-shape.explain-arguments", m, bl[4].prose[-300:])
        value = tool_reply(t, prefix + ".explain", srv.call(3, "explain", json.loads(m.group(1))))
        compare_shown(t, h, prefix + ".explain", bl[4], value)
        args = json.loads(h.actual(bl[5].text))
        value = tool_reply(t, prefix + ".assemble-full", srv.call(4, "assemble", args))
        compare_shown(t, h, prefix + ".assemble-full", bl[6], value)
        roles = json.loads("{" + bl[7].text + "}")
        t.require(prefix + ".doc-shape.drops-detail", "drops `detail`" in bl[8].prose, bl[8].prose[-200:])
        args = dict(args, fields=dict(args["fields"], **roles))
        args.pop("detail", None)
        dry = tool_reply(t, prefix + ".assemble-roles", srv.call(5, "assemble", args))
        compare_shown(t, h, prefix + ".assemble-roles", bl[8], dry)
        t.require(prefix + ".doc-shape.create", '"create": true' in bl[9].prose, bl[9].prose[-200:])
        made = tool_reply(t, prefix + ".assemble-create", srv.call(6, "assemble", dict(args, create=True)))
        compare_shown(t, h, prefix + ".assemble-create", bl[9], made)
        t.eq(prefix + ".assemble-create.data-is-the-dry-run's", made.get("data"), dry.get("data"))
        candidate = os.path.join(server_args[1], args["destination"])
        question = (dry.get("data") or {}).get("question_file")
        qpath = os.path.join(candidate, "question.md")
        t.eq(prefix + ".candidate-question", read_bytes(qpath).decode("utf-8") if os.path.isfile(qpath) else None,
             question)
        again = tool_reply(t, prefix + ".assemble-retry", srv.call(7, "assemble", dict(args, create=True)))
        compare_shown(t, h, prefix + ".assemble-retry", bl[10], again)
    finally:
        srv.close()
    for k, cmd in enumerate(commands_of(bl[11])):
        t.require(prefix + ".doc-shape.cli", cmd.stewart, cmd.argv)
        stewart_command(t, h, cmd, "%s.cli-%d-%s" % (prefix, k + 1, cmd.argv[1]))


# ---------------------------------------------------------------------------
# Comparing the two routes.
# ---------------------------------------------------------------------------

TIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")


def audit_id(ref):
    parts = (ref or "").split(":")
    return parts[1] if len(parts) > 3 else None


def masked(data, ref):
    """Bytes with the audit identifier and every RFC 3339 UTC time replaced, for comparing
    arrangements "apart from its audit identifier and time"."""
    text = data.decode("utf-8", "replace")
    aid = audit_id(ref)
    if aid:
        text = text.replace(aid, "AUDIT")
    return TIME_RE.sub("TIME", text)


def compare_arrangements(t, name, a_dir, a_ref, b_dir, b_ref):
    """arrangement.json and arrangement.md of two preparations, equal apart from the audit
    identifier and times (WITH-MCP step 6)."""
    for member in ("arrangement.json", "arrangement.md"):
        pa, pb = os.path.join(a_dir, member), os.path.join(b_dir, member)
        if not t.check("%s.%s.present" % (name, member), os.path.isfile(pa) and os.path.isfile(pb), [pa, pb]):
            continue
        ma, mb = masked(read_bytes(pa), a_ref), masked(read_bytes(pb), b_ref)
        first = next((i for i, (x, y) in enumerate(zip(ma, mb)) if x != y), min(len(ma), len(mb)))
        t.check("%s.%s.same-apart-from-identifier-and-time" % (name, member), ma == mb,
                {"at": first, "file-only": ma[max(0, first - 120):first + 120],
                 "assembled": mb[max(0, first - 120):first + 120]})


def compare_routes(t, files, mcp, pkg_files, pkg_mcp):
    """WITH-MCP step 6: the same question body, materials and settings, the same arrangement apart
    from its audit identifier and time, the same provider requests, and the same delivered
    question.md, answer.json and answer.md."""
    p = "walkthrough.routes"
    differing = re.compile(r"^  (file bytes|file sha256|sha256): ")
    a = (files.prepare_out or "").replace(audit_id(files.ref) or "\0", "AUDIT").split("\n")
    b = (mcp.prepare_out or "").replace(audit_id(mcp.ref) or "\0", "AUDIT").split("\n")
    t.eq(p + ".prepare.line-count", len(b), len(a))
    pairs = [(x, y) for x, y in zip(a, b) if x != y]
    allowed = [(x, y) for x, y in pairs if differing.match(x) and differing.match(y)
               and x.split(":")[0] == y.split(":")[0]]
    t.check(p + ".prepare.same-body-materials-settings", pairs == allowed,
            [pr for pr in pairs if pr not in allowed][:10])
    t.check(p + ".prepare.question-file-differs", any(x.startswith("  file sha256:") for x, _ in allowed), allowed)
    if files.machine and mcp.machine:
        compare_arrangements(t, p + ".prepare", os.path.dirname(files.machine), files.ref,
                             os.path.dirname(mcp.machine), mcp.ref)
    else:
        t.check(p + ".prepare.arrangement-paths", False, [files.machine, mcp.machine])
    ea, eb = files.fx.exchanges, mcp.fx.exchanges
    t.eq(p + ".requests.count", len(eb), len(ea))
    for label, i in (("run-1-attempt-1", 0), ("run-2-request-1", RUN1_ATTEMPTS)):
        if i < len(ea) and i < len(eb):
            t.check("%s.requests.%s.same-body" % (p, label), ea[i].body == eb[i].body,
                    {"file-only": short(ea[i].body, 300), "assembled": short(eb[i].body, 300)})
    body = open_body()
    if ea:
        rs.check_first_message(t, ea[0], body, False, p + ".run-1")
    if len(ea) > RUN1_ATTEMPTS:
        rs.check_first_message(t, ea[RUN1_ATTEMPTS], body, True, p + ".run-2")
    for member in ("question.md", "answer.json", "answer.md"):
        x = (pkg_files or (None, {}))[1].get(member)
        y = (pkg_mcp or (None, {}))[1].get(member)
        t.check("%s.return.%s.identical" % (p, member), x is not None and x == y,
                {"file-only": None if x is None else (len(x), sha256_hex(x)),
                 "assembled": None if y is None else (len(y), sha256_hex(y))})


@case("c21.walkthroughs", ["C21", "C11", "C16", "C5", "C12", "C9"],
      "the manager walkthroughs run as written: every shown output, exit status, MCP reply and return "
      "member, and both routes deliver the same bytes",
      needs=("loopback",))
def c_walkthroughs(t):
    """FILE-ONLY from an empty home: new, the copies and the destination edit, prepare refused
    destination_invalid (exit 3), mkdir, prepare, commission, receipt, run 1 against a stand-in
    answering 529 overloaded (interrupted, exit 5), run 2 replaying the open auditor walkthrough in
    four responses of 3,000/400 tokens (sealed and delivered), status and its JSON headline, the
    return listing with its sizes (answer.md is the walkthrough's rendering), close, and run after
    close (reference_closed, status alone, exit 3). Only run contacts the stand-in. WITH-MCP from
    another empty home: the sources and destination, the server's exact handshake, discover,
    explain, the full-detail and role-declaring dry runs, creation, the refused retry under the same
    name and new on the candidate; then FILE-ONLY from its first completing prepare. Equivalence:
    the two preparations differ only in the question file's size and digest and the arrangement
    digest, the arrangements only in the audit identifier and times, the provider's first requests
    of each run are byte-identical, and the deliveries' question.md, answer.json and answer.md are
    byte-identical."""
    need_examples()
    files = Home(t, "ana-files")
    stand_in(t, files)
    pkg_files = follow_file_only(t, files, "walkthrough.files")
    mcp = Home(t, "ana-mcp")
    stand_in(t, mcp)
    follow_with_mcp(t, mcp, "walkthrough.mcp")
    pkg_mcp = follow_file_only(t, mcp, "walkthrough.mcp.files", from_prepare=True)
    compare_routes(t, files, mcp, pkg_files, pkg_mcp)


# ---------------------------------------------------------------------------
# Every worked packet through assemble.
# ---------------------------------------------------------------------------

def front_matter(text):
    """(fields, body) of a question/2 file: every `key: value` line but the stewart line and
    comments, material-roles decoded, and the exact body."""
    _, rest = text.split("\n", 1)
    head, body = rest.split("\n---\n", 1)
    fields = {}
    for line in head.split("\n"):
        if not line or line.startswith("#") or line.startswith("stewart:"):
            continue
        key, value = line.split(": ", 1)
        fields[key] = json.loads(value) if key == "material-roles" else value
    return fields, body


def packet_variants(t):
    """[(label, packet, question text, material names)] for each worked packet and its
    inadequate-evidence variant: the variant keeps the sources its walkthrough names and only their
    role declarations, as the walkthrough describes."""
    out = []
    for name in PACKETS:
        q = read_doc("questions", name, "submission", "question.md")
        files = sorted("materials/" + n for n in os.listdir(os.path.join(EXAMPLES, "questions", name, "submission",
                                                                          "materials")))
        out.append((name, name, q, files))
        text = section(read_doc("questions", name, "WALKTHROUGH.md"), "Inadequate-evidence variant")
        m = re.search(r"[Ii]ts (?:one )?sources? (?:is|are) (.+?)\.\n", text, re.S)
        t.require("packets.%s.variant.sources" % name, m, text[:400])
        kept = sorted(re.findall(r"`(materials/[^`]+)`", m.group(1)))
        fields, _ = front_matter(q)
        roles = [r for r in fields["material-roles"] if r["source"] in kept]
        keep = re.search(r"Keep only the (\w+) declaration", text)
        drop = re.search(r"Remove the declaration for (\w+)", text)
        if keep:
            t.eq("packets.%s.variant.roles-as-described" % name, [r["role"] for r in roles], [keep.group(1)])
        elif drop:
            t.check("packets.%s.variant.roles-as-described" % name,
                    all(r.get("label") != drop.group(1) for r in roles) and len(roles) == len(fields["material-roles"]) - 1,
                    roles)
        else:
            t.check("packets.%s.variant.roles-described" % name, False, text[:400])
        line = "material-roles: " + json.dumps(fields["material-roles"], ensure_ascii=False, separators=(",", ":"))
        t.require("packets.%s.roles-line" % name, line in q, line)
        new_line = "material-roles: " + json.dumps(roles, ensure_ascii=False, separators=(",", ":"))
        out.append((name + "-variant", name, q.replace(line, new_line), kept))
    return out


def with_destination(q, dest):
    lines = q.split("\n")
    return "\n".join("destination: " + dest if x.startswith("destination:") else x for x in lines)


def prepared_facts(data):
    """A prepare reply's data without the facts the two routes legitimately differ in: the handle,
    the question file's size and digest, the arrangement's digest and locations, and a defect's
    question.md line."""
    d = json.loads(json.dumps(data))
    d.pop("prepared", None)
    for k in ("file_bytes", "file_sha256"):
        (d.get("question") or {}).pop(k, None)
    d.pop("arrangement", None)
    for x in d.get("defects") or []:
        if isinstance(x, dict):
            x.pop("line", None)
    return d


@case("c21.worked-packets", ["C21", "C7", "C11", "C19"],
      "each worked packet and its inadequate-evidence variant, assembled through MCP, prepares as its "
      "file-only folder does")
def c_worked_packets(t):
    """For open, framing and comparison and each one's inadequate-evidence variant (the sources its
    walkthrough names and only their declarations): a file-only folder from the submission's
    question.md and materials, and the same fields, body and files assembled through `assemble`
    from a workspace's sources. Both are prepared by the CLI: the same question body, materials,
    settings, reader, bounds and diagnostics (apart from a defect's question.md line), the
    arrangement and its readable view equal apart from the audit identifier and times, and the
    assembly's own assessment giving prepare's defects. The comparison variant warns, as its
    walkthrough says."""
    need_examples()
    root = os.path.realpath(t.mkdir("packets"))
    dest = os.path.join(root, "returns")
    os.makedirs(dest)
    archive = os.path.join(root, "archive")
    folders = os.path.join(root, "files")
    os.makedirs(folders)
    workspace = os.path.join(root, "workspace")
    for name in PACKETS:
        src = os.path.join(EXAMPLES, "questions", name, "submission", "materials")
        os.makedirs(os.path.join(workspace, "sources", name))
        for n in os.listdir(src):
            shutil.copyfile(os.path.join(src, n), os.path.join(workspace, "sources", name, n))
    variants = packet_variants(t)
    srv = Server(t, "packets.server", workspace=workspace)
    assembled = {}
    try:
        for k, (label, packet, q, files) in enumerate(variants):
            fields, body = front_matter(with_destination(q, dest))
            args = {"fields": fields, "body": body, "guidance": None, "directories": ["materials"],
                    "files": [{"name": f, "from": packet + "/" + f.split("/", 1)[1]} for f in files],
                    "destination": label, "create": True}
            value = tool_reply(t, "packets.%s.assemble" % label, srv.call(10 + k, "assemble", args))
            t.eq("packets.%s.assemble.outcome" % label, value.get("outcome"), "completed")
            assembled[label] = value
    finally:
        srv.close()
    for label, packet, q, files in variants:
        p = "packets." + label
        folder = os.path.join(folders, label)
        r = t.cmd(["new", folder, "--archive", archive], name=p + ".files.new", expect="completed")
        ref_files = r.data.get("reference")
        os.remove(os.path.join(folder, "question.md"))
        with open(os.path.join(folder, "question.md"), "w", encoding="utf-8") as f:
            f.write(with_destination(q, dest))
        for name in files:
            shutil.copyfile(os.path.join(EXAMPLES, "questions", packet, "submission", name), os.path.join(folder, name))
        prep_files = t.cmd(["prepare", ref_files], name=p + ".files.prepare", expect="completed")
        r = t.cmd(["new", os.path.join(workspace, label), "--archive", archive], name=p + ".mcp.new",
                  expect="completed")
        ref_mcp = r.data.get("reference")
        prep_mcp = t.cmd(["prepare", ref_mcp], name=p + ".mcp.prepare", expect="completed")
        a, b = prepared_facts(prep_files.data), prepared_facts(prep_mcp.data)
        t.eq(p + ".same-preparation", b, a)
        t.check(p + ".question-files-differ",
                (prep_files.data.get("question") or {}).get("file_sha256")
                != (prep_mcp.data.get("question") or {}).get("file_sha256"), prep_mcp.data.get("question"))
        ma = (prep_files.data.get("arrangement") or {}).get("machine")
        mb = (prep_mcp.data.get("arrangement") or {}).get("machine")
        if t.check(p + ".arrangement-paths", isinstance(ma, str) and isinstance(mb, str), [ma, mb]):
            compare_arrangements(t, p, os.path.dirname(ma), ref_files, os.path.dirname(mb), ref_mcp)
        assessment = ((assembled.get(label) or {}).get("data") or {}).get("assessment") or {}
        shown = [{k: v for k, v in x.items() if k not in ("line", "pointer")} for x in assessment.get("defects") or []]
        actual = [{k: v for k, v in x.items() if k in y} for x, y in zip(prep_mcp.data.get("defects") or [], shown)]
        t.eq(p + ".assessment-is-prepare's", (len(assessment.get("defects") or []), actual),
             (len(prep_mcp.data.get("defects") or []), shown))
        if label == "comparison-variant":
            t.check(p + ".warns", any(x.get("severity") == "warning" for x in prep_files.data.get("defects") or []),
                    prep_files.data.get("defects"))


# ---------------------------------------------------------------------------
# Self-tests of the reading rules (no binary).
# ---------------------------------------------------------------------------

@selftest
def walkthrough_reading_selftests():
    out = []
    E = ELLIPSIS
    exp = [(1, "a"), (2, "x: " + E), (3, E), (4, "z")]
    out.append(("walkthrough.match.gap", match_lines(exp, ["a", "x: 1", "p", "q", "z"]) is None))
    out.append(("walkthrough.match.empty-gap", match_lines(exp, ["a", "x: ", "z"]) is None))
    miss = match_lines(exp, ["a", "y: 1", "z"])
    out.append(("walkthrough.match.pair", miss == (2, "x: " + E, "y: 1"), miss))
    out.append(("walkthrough.match.extra-tail", match_lines([(1, "a")], ["a", "b"]) is not None))
    shown = shown_json('{"a": ' + E + ', "b": "p-' + E + '-1", "c": [1, {"d": true}]}')
    out.append(("walkthrough.shown.any", value_diff(shown, {"a": [3], "b": "p-77-1", "c": [1, {"d": True, "e": 0}],
                                                            "f": 1}, True) is None))
    out.append(("walkthrough.shown.bool-is-not-int", value_diff(shown, {"a": 0, "b": "p--1", "c": [1, {"d": 1}]},
                                                               True) is not None))
    out.append(("walkthrough.shown.exact-members", value_diff({"a": 1}, {"a": 1, "b": 2}, False) is not None))
    out.append(("walkthrough.shown.array-length", value_diff([1], [1, 2], True) is not None))
    out.append(("walkthrough.changed-leaf", changed_leaf({"a": ANY, "b": "x" + E, "c": [True, 2]})
                == {"a": ANY, "b": "x" + E, "c": [False, 2]} and changed_leaf({"a": ANY}) is None))
    out.append(("walkthrough.exit", (doc_exit([(1, "stewart run: refused (reference_closed)")]),
                                     doc_exit([(1, "Command stewart run: completed"), (2, "Run 1 was interrupted (x).")]),
                                     doc_exit([(1, "stewart new: completed")])) == (3, 5, 0)))
    if not examples_present():
        out.append(("walkthrough.docs", None, "examples/ not beside the driver; skipped"))
        return out
    steps = file_only_steps()
    out.append(("walkthrough.file-only.shape", not [s for s in steps if s[0] == "unknown"],
                [(s[1].doc, s[1].line) for s in steps if s[0] == "unknown"]))
    calls = auditor_calls()
    out.append(("walkthrough.auditor-calls", [c[0] for c in calls] == [n for g in RUN2_GROUPS for n in g],
                [c[0] for c in calls]))
    out.append(("walkthrough.rendering-size", len(rendering_block() or b"") == 988, len(rendering_block() or b"")))
    return out
