"""Read-only manager MCP, from MANAGER-PREPARATION, INTERFACE 3/5.11 and C21."""
import copy
import os
from pathlib import Path
import subprocess
import threading
import time

from claude_code import transport_loads
from driver_core import (F, FAMILY_ROLES, Proc, case, check_defects, check_family_descriptor,
                         is_compact_json, strict_loads)
from rawjson import compact


VERSION = "2025-11-25"
INITIALIZE = {"jsonrpc": "2.0", "id": "init", "method": "initialize",
              "params": {"protocolVersion": VERSION, "capabilities": {},
                         "clientInfo": {"name": "stewart-independent-driver", "version": "1"}}}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
UNCHANGED = {"state": "none", "created": [], "incomplete": []}
UNCHECKED = ["material_bytes", "filesystem", "source_stability", "acceptance"]


def request(identity, method, params=None):
    value = {"jsonrpc": "2.0", "id": identity, "method": method}
    if params is not None:
        value["params"] = params
    return value


def call(identity, tool, arguments, **params):
    return request(identity, "tools/call", dict(params, name=tool, arguments=arguments))


def wire(frames):
    return b"".join((frame if isinstance(frame, bytes) else compact(frame)) + b"\n" for frame in frames)


def session(t, name, requests, *, before=(), env=None):
    """Wait for initialize before sending initialized. Retain independent stdin, stdout and inventories."""
    prefix = wire([*before, INITIALIZE])
    tail = wire([INITIALIZED, *requests])
    (Path(t.evid) / (name + ".stdin")).write_bytes(prefix + tail)
    argv = [t.bin["path"], "manager-mcp"]
    environment = t.env(env)
    t.sync("before " + name)
    proc = Proc(argv, environment, t.cwd, 20, stdin=subprocess.PIPE)
    errors = []

    def send():
        try:
            with proc.p.stdin as stream:
                stream.write(prefix)
                stream.flush()
                deadline = time.monotonic() + 10
                while proc.out.count(b"\n") < len(before) + 1:
                    if not proc.running() or time.monotonic() >= deadline:
                        errors.append("initialize did not reply before initialized or EOF")
                        return
                    time.sleep(0.005)
                stream.write(tail)
        except OSError as exc:
            errors.append(str(exc))

    sender = threading.Thread(target=send, daemon=True)
    sender.start()
    result = proc.wait()
    sender.join(2)
    t.sync("after " + name, readonly=True)
    t._record(name, "manager-mcp", argv, environment, t.cwd, result, None, False)
    t.require(name + ".exchange", not errors and not sender.is_alive() and not result["timed_out"],
              {"sender": errors, "timed_out": result["timed_out"], "stderr": result["stderr"]})
    t.require(name + ".exit", result["rc"] == 0, result["stderr"])
    output = result["stdout"]
    t.require(name + ".terminated-lines", output.endswith(b"\n"), output[-500:])
    lines = output[:-1].split(b"\n")
    t.check(name + ".compact-frames", all(is_compact_json(line.decode("utf-8")) for line in lines), None)
    replies = [transport_loads(line) for line in lines]
    t.require(name + ".initialized", len(replies) > len(before), replies)
    init = replies.pop(len(before))
    t.eq(name + ".initialize-id", init.get("id"), "init")
    t.eq(name + ".initialize-result", init.get("result"), {
        "protocolVersion": VERSION, "capabilities": {"tools": {}},
        "serverInfo": {"name": "stewart-manager", "version": "1"}})
    t.check(name + ".json-rpc-version", all(reply.get("jsonrpc") == "2.0" for reply in [init] + replies), None)
    return replies


def tool_result(t, name, reply, tool, *, problem=None, full=False):
    result = reply.get("result")
    t.require(name + ".tool-result", isinstance(result, dict), reply)
    t.check(name + ".error-flag", result.get("isError") is (problem is not None), result)
    value = result.get("structuredContent")
    t.require(name + ".structured", isinstance(value, dict), result)
    content = result.get("content")
    t.require(name + ".one-text-block", isinstance(content, list) and len(content) == 1
              and content[0].get("type") == "text" and isinstance(content[0].get("text"), str), content)
    text = content[0]["text"]
    t.check(name + ".compact-result", is_compact_json(text), text)
    t.eq(name + ".result-fidelity", strict_loads(text.encode()), value)
    for key, expected in (("schema", "stewart.manager-preparation/1"), ("registry", "stewart.family-registry/1"),
                          ("question_schema", "question/2"), ("tool", tool), ("writes", UNCHANGED),
                          ("outcome", "refused" if problem else "completed")):
        t.eq(name + "." + key, value.get(key), expected)
    t.require(name + ".explanation-array", isinstance(value.get("explanation"), list) and
              all(isinstance(s, str) and s.strip() for s in value["explanation"]), value)
    if not full:
        t.eq(name + ".brief", value["explanation"], [])
    if problem:
        issue = value.get("problem")
        t.require(name + ".problem-object", isinstance(issue, dict), value)
        t.eq(name + ".problem-keys", set(issue), {"reason", "pointer", "message", "remedy"})
        t.eq(name + ".reason", issue.get("reason"), problem)
        for key in ("message", "remedy"):
            t.check(name + "." + key, isinstance(issue.get(key), str) and issue[key].strip(), issue)
        t.eq(name + ".data", value.get("data", "missing"), None)
    else:
        t.eq(name + ".problem", value.get("problem", "missing"), None)
    return value


def field_types(schema):
    """Nullable guidance can use a type array or separate string and null branches."""
    for key in ("anyOf", "oneOf"):
        if key in schema:
            return set().union(*(field_types(branch) for branch in schema[key]))
    types = schema.get("type", [])
    return {types} if isinstance(types, str) else set(types)


def altered_result(t, name, reply, data):
    """Replace both presentations so a semantic defect must be caught independently of their equality."""
    changed = copy.deepcopy(reply)
    value = changed["result"]["structuredContent"]
    value["data"] = data
    changed["result"]["content"][0]["text"] = compact(value).decode("utf-8")
    (Path(t.evid) / (name + ".json")).write_bytes(compact(changed) + b"\n")
    return changed


def check_control(t, name, expected, check, *args, **kwargs):
    observed = copy.copy(t)
    observed.checks = []
    check(observed, "candidate", *args, **kwargs)
    failures = [row["name"] for row in observed.checks if not row["ok"]]
    t.driver_control(name, failures == expected, {"expected_failures": expected, "observed_failures": failures})


@case("c21.manager-mcp-transport", ["C21", "C20"], "stdio handshake, framing, method and argument errors, recovery and notifications")
def c_transport(t):
    pre = request("early", "tools/list")
    notify_call = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "missing", "arguments": {}}}
    exact = compact(request(-5, "ping"))
    exact += b" " * ((4 << 20) - len(exact))
    replies = session(t, "transport", [
        request(1, "ping"), b"{?", [],
        request(3, "resources/list"), call(4, "commission", {}),
        notify_call, exact, exact + b" ", request("after-overlong", "ping"),
        call(6, "discover", {"detail": False}), call(7, "assess", {"workspace": "/"}),
        call(8, "discover", {}, _meta={"driver.example/amount": -0.5}),
        b'{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"discover","arguments":{"detail":"brief","de\\u0074ail":"full"}}}',
        call(10, "discover", {})], before=[pre])
    ids = ["early", 1, None, None, 3, 4, -5, None, "after-overlong", 6, 7, 8, 9, 10]
    t.require("transport.reply-count", len(replies) == len(ids), replies)
    t.eq("transport.reply-identities", [r.get("id", "missing") for r in replies], ids)
    for i, code in ((0, -32600), (2, -32700), (3, -32600), (4, -32601), (5, -32602), (7, -32600)):
        t.eq("transport.error-%d" % i, replies[i].get("error", {}).get("code"), code)
    for i in (1, 6, 8):
        t.eq("transport.ping-%d" % i, replies[i].get("result"), {})
    for i, tool in ((9, "discover"), (10, "assess"), (12, "discover")):
        value = tool_result(t, "transport.invalid-%d" % i, replies[i], tool, problem="input_invalid")
        pointer = value["problem"]["pointer"]
        t.check("transport.pointer-%d" % i, isinstance(pointer, str) and pointer.startswith("/"), pointer)
        if tool == "discover":
            t.eq("transport.detail-pointer-%d" % i, pointer, "/detail")
    first = tool_result(t, "transport.metadata", replies[11], "discover")
    last = tool_result(t, "transport.recovered", replies[13], "discover")
    t.eq("transport.metadata-invariant", first, last)


@case("c21.manager-mcp-families", ["C21", "C7"], "discover, explain and validate each worked family's descriptor and declared roles")
def c_families(t):
    methods = [request("list", "tools/list"), call("families", "discover", {})]
    for family in FAMILY_ROLES:
        args = {"family": family + "/1"}
        methods.extend((call(family, "explain", args), call(family + "-full", "explain", dict(args, detail="full"))))
    methods.extend((call("unknown", "explain", {"family": "other/1"}), call("again", "discover", {})))
    replies = session(t, "families", methods)
    t.require("families.reply-ids", [r.get("id") for r in replies] == [r["id"] for r in methods], replies)
    pages = replies[0].get("result", {})
    advertised = pages.get("tools", [])
    t.eq("families.one-page", pages.get("nextCursor"), None)
    t.eq("families.advertised", [tool.get("name") for tool in advertised], ["discover", "explain", "assess"])
    for tool, fields in zip(advertised, ([], ["family"], ["question_file", "guidance", "directories", "files"])):
        name = "families.schema." + tool["name"]
        schema = tool.get("inputSchema", {})
        t.check(name + ".description", isinstance(tool.get("description"), str) and tool["description"].strip(), tool)
        t.eq(name + ".type", schema.get("type"), "object")
        t.check(name + ".closed", schema.get("additionalProperties") is False, schema)
        t.eq(name + ".required", sorted(schema.get("required", [])), sorted(fields))
        properties = schema.get("properties", {})
        t.eq(name + ".properties", sorted(properties), sorted(["detail"] + fields))
        t.eq(name + ".detail-type", field_types(properties.get("detail", {})), {"string"})
        t.eq(name + ".detail-values", sorted(properties.get("detail", {}).get("enum", [])), ["brief", "full"])
        if tool["name"] == "explain":
            t.eq(name + ".family", field_types(properties.get("family", {})), {"string"})
        if tool["name"] == "assess":
            for key, types in (("question_file", {"string"}), ("guidance", {"string", "null"}),
                               ("directories", {"array"}), ("files", {"array"})):
                t.eq(name + "." + key, field_types(properties.get(key, {})), types)
            t.eq(name + ".directory-name", field_types(properties.get("directories", {}).get("items", {})), {"string"})
            file_schema = properties.get("files", {}).get("items", {})
            t.eq(name + ".file-type", field_types(file_schema), {"object"})
            t.check(name + ".file-closed", file_schema.get("additionalProperties") is False, file_schema)
            t.eq(name + ".required-file-members", sorted(file_schema.get("required", [])), ["name", "size"])
            file_fields = file_schema.get("properties", {})
            t.eq(name + ".file-members", sorted(file_fields), ["name", "size"])
            t.eq(name + ".file-name", field_types(file_fields.get("name", {})), {"string"})
            t.eq(name + ".file-size", field_types(file_fields.get("size", {})), {"integer"})
            t.eq(name + ".unsigned-size", file_fields.get("size", {}).get("minimum"), 0)
    families = tool_result(t, "families.discover", replies[1], "discover")["data"]["families"]
    t.eq("families.discovery-order", [f.get("family") for f in families], [f + "/1" for f in FAMILY_ROLES])
    roles = {"open-inquiry": [("subject", "a.py"), ("context", "requirements.txt"), ("report", "supplied-report.txt")],
             "inquiry-framing": [("context", "requirements.txt"), ("subject", "a.py"), ("report", "supplied-report.txt")],
             "comparison": [("alternative", "a.py", "A"), ("alternative", "b.py", "B"), ("criterion", "requirements.txt")]}
    for i, family in enumerate(FAMILY_ROLES):
        name = "families." + family
        brief = tool_result(t, name, replies[2 + 2 * i], "explain")
        full = tool_result(t, name + ".full", replies[3 + 2 * i], "explain", full=True)
        t.eq(name + ".detail-invariance", dict(full, explanation=[]), brief)
        t.check(name + ".full-explains", bool(full["explanation"]), full)
        descriptor = brief["data"]["descriptor"]
        check_family_descriptor(t, name, descriptor, family)
        t.eq(name + ".discovery", families[i], {k: descriptor[k] for k in ("family", "available", "purpose")})
        example = [{"role": role, "source": "materials/" + source, **({"label": label[0]} if label else {})}
                   for role, source, *label in roles[family]]
        t.eq(name + ".worked-packet", brief["data"].get("example"), example)
        if family == "comparison":
            changed = copy.deepcopy(brief["data"])
            changed["descriptor"]["roles"][0]["minimum_recommended"] = 1
            reply = altered_result(t, "lower-alternative-minimum", replies[2 + 2 * i], changed)
            value = tool_result(t, "families.changed-descriptor", reply, "explain")
            check_control(t, "lower-alternative-minimum", ["candidate.alternative.minimum"],
                          check_family_descriptor, value["data"]["descriptor"], family)
    unknown = tool_result(t, "families.unknown", replies[-2], "explain", problem="family_unknown")
    words = unknown["problem"]["message"] + " " + unknown["problem"]["remedy"]
    t.check("families.unknown-names-choices", all(f + "/1" in words for f in FAMILY_ROLES), words)
    again = tool_result(t, "families.again", replies[-1], "discover")
    t.eq("families.no-persistent-detail", again["data"]["families"], families)


BUS_BODY = ("For a Saturday trip from Elm Square to Central Market, which bus, Option A or Option B, "
            "best meets the rider's arrival criterion? Give the earliest qualifying arrival supported for each option, "
            "and say what else you need if you cannot choose between them.\n")
BUS_MATERIALS = {
    "saturday-a.txt": (b"Option A, Saturday service\nElm Square departure -> Central Market arrival (local time)\n"
                       b"07:50 -> 08:17\n08:13 -> 08:39\n08:40 -> 09:00\n"),
    "rider-note.txt": (b"I need to get to Central Market on Saturday before 9 a.m. Of the trips arriving before then, "
                       b"I prefer the one that arrives earliest.\n"),
}


def bus_question(destination, alternate="saturday-a.txt"):
    roles = [{"role": "alternative", "source": "materials/" + alternate, "label": "Option A"},
             {"role": "criterion", "source": "materials/rider-note.txt"}]
    return ("---\nstewart: question/2\nfamily: comparison\nmaterial-roles: " + compact(roles).decode()
            + "\nmodel: claude-opus-5-5\ndestination: " + destination
            + "\nlimit-turns: 10\nlimit-input-tokens: 50000\nlimit-output-tokens: 5000\n---\n" + BUS_BODY)


def inventory(question):
    return {"question_file": question, "guidance": None, "directories": ["materials"],
            "files": [{"name": "materials/" + name, "size": len(data)} for name, data in BUS_MATERIALS.items()]}


def assessment(t, name, reply, defects, *, full=False, same_as=None):
    data = tool_result(t, name, reply, "assess", full=full)["data"]
    t.eq(name + ".data-keys", set(data), {"valid", "defects", "unchecked"})
    t.check(name + ".valid", data.get("valid") is all(d["severity"] != "error" for d in defects), data)
    t.eq(name + ".unchecked", data.get("unchecked"), UNCHECKED)
    check_defects(t, name, data, defects)
    if same_as is not None:
        t.eq(name + ".same-facts", data, same_as)
    return data


@case("c21.manager-mcp-bus", ["C21", "C11", "C15"],
      "the same literal bus timetable, typo and correction assessed through MCP and prepared through files")
def c_bus(t):
    destination = t.dest_path()
    good = bus_question(destination)
    bad = bus_question(destination, "satruday-a.txt")
    args = inventory(good)
    warning = [{"reason": "role_unmapped", "severity": "warning", "key": "material-roles",
                "pointer": None, "line": None, "source": None, "role": "alternative"}]
    error = [{"reason": "role_source_unknown", "severity": "error", "key": "material-roles", "pointer": "/0/source",
              "line": 4, "source": "materials/satruday-a.txt", "role": "alternative"}]
    sub = t.submission([F(name, data) for name, data in BUS_MATERIALS.items()], question=good.encode(),
                       family="comparison", dest=destination, q={"turns": "10", "input_tokens": "50000", "output_tokens": "5000"})
    # A nonexistent archive path is referred to by the environment; MCP has nothing to prepare there.
    t.watch(sub.archive, "archive")
    t.watch(t.home, "frozen")
    t.watch(t.cwd, "frozen")
    t.watch(t.tmp, "frozen")
    frames = [call("available", "assess", args), call("typo", "assess", inventory(bad)),
              call("corrected", "assess", dict(args, detail="full")),
              call("reordered", "assess", dict(args, files=list(reversed(args["files"])))),
              call("unchecked-path", "assess", inventory(bus_question(os.path.join(destination, "absent"))))]
    replies = session(t, "bus-before", frames, env={"STEWART_ARCHIVE": sub.archive})
    t.require("bus.reply-ids", [r.get("id") for r in replies] == [f["id"] for f in frames], replies)
    available = assessment(t, "bus.available", replies[0], warning)
    typo = assessment(t, "bus.typo", replies[1], error)
    for i, label in ((2, "corrected"), (3, "reordered"), (4, "unchecked-path")):
        assessment(t, "bus." + label, replies[i], warning, full=i == 2, same_as=available)
    # Each changed reply keeps text and structured content mutually consistent.
    # Reuse the actual checks above and require the particular failing observations.
    warned = available["defects"][0]
    mistaken = typo["defects"][0]
    for label, i, changes, expected, failures in (
            ("missing-advice", 0, {"defects": []}, warning, ["candidate.defect-count"]),
            ("advice-made-mandatory", 0, {"valid": False, "defects": [dict(warned, severity="error")]},
             warning, ["candidate.valid", "candidate.defect-0.severity"]),
            ("wrong-reference", 1, {"defects": [dict(mistaken, source="materials/saturday-a.txt")]},
             error, ["candidate.defect-0.source"]),
            ("full-detail-changed-remedy", 2, {"defects": [dict(warned, remedy="Supply a second option before commissioning.")]},
             warning, ["candidate.same-facts"])):
        data = dict(replies[i]["result"]["structuredContent"]["data"], **changes)
        changed = altered_result(t, label, replies[i], data)
        check_control(t, label, failures, assessment, changed, expected, full=i == 2,
                      same_as=available if i == 2 else None)
    t.check("bus.no-archive-created", not os.path.lexists(sub.archive), sub.archive)
    t.new_ref(sub)
    prep = t.prepare(sub, name="bus.cli-available")
    t.check_prepare_witness(prep, sub, "bus.cli-available")
    t.eq("bus.same-warning", prep.data["defects"], available["defects"])
    t.edit(os.path.join(sub.folder, "question.md"), bad.encode())
    refused = t.prepare(sub, name="bus.cli-typo", expect="refused", reason="role_source_unknown")
    t.eq("bus.same-error", refused.data["defects"], typo["defects"])
    t.edit(os.path.join(sub.folder, "question.md"), good.encode())
    prep = t.prepare(sub, name="bus.cli-corrected")
    t.eq("bus.restored-warning", prep.data["defects"], available["defects"])
    t.check_prepare_witness(prep, sub, "bus.cli-corrected")
    # This session sees an existing archive with two preparations and a diagnostic.
    again = session(t, "bus-after", [call("again", "assess", args)], env={"STEWART_ARCHIVE": sub.archive})
    t.require("bus.reconnect-id", [r.get("id") for r in again] == ["again"], again)
    t.eq("bus.archive-state-invariance", assessment(t, "bus.after", again[0], warning), available)


@case("c21.manager-mcp-inventory", ["C21", "C19", "C20"],
      "prospective inventory and guidance failures stay distinct from invalid tool arguments")
def c_inventory(t):
    question = bus_question("/intentionally-absent/return")
    args = inventory(question)
    entries = args["files"]
    nested = {"name": "materials/notes/note.txt", "size": 7}
    cases = [
        ("nested", dict(args, files=entries + [nested], directories=["materials/notes", "materials"]), None),
        ("missing-parent", dict(args, files=entries + [nested]), "folder_incomplete"),
        ("missing-root", dict(args, directories=[]), "folder_incomplete"),
        ("duplicate", dict(args, files=entries + [entries[0]]), "name_invalid"),
        ("collision", dict(args, directories=["materials", entries[0]["name"]]), "name_invalid"),
        ("size", dict(args, files=[dict(entries[0], size=16777217), entries[1]]), "bound_exceeded"),
        ("unselected-guidance", dict(args, guidance="Some guidance."), "unexpected_root_entry"),
        ("missing-guidance", dict(args, question_file=question.replace("family: comparison",
                "family: open-inquiry\nguidance: guidance.md").replace(
                next(s for s in question.splitlines(True) if s.startswith("material-roles:")), "")), "folder_incomplete"),
    ]
    frames = [call(label, "assess", candidate) for label, candidate, _ in cases]
    frames += [call("string-size", "assess", dict(args, files=[dict(entries[0], size="7")])),
               call("missing-files", "assess", {k: v for k, v in args.items() if k != "files"}),
               call("bad-detail", "discover", {"detail": "verbose"})]
    replies = session(t, "inventory", frames)
    t.require("inventory.reply-ids", [r.get("id") for r in replies] == [f["id"] for f in frames], replies)
    for i, (label, _, reason) in enumerate(cases):
        name = "inventory." + label
        data = tool_result(t, name, replies[i], "assess")["data"]
        t.check(name + ".valid", data.get("valid") is (reason is None), data)
        t.eq(name + ".unchecked", data.get("unchecked"), UNCHECKED)
        if reason is None:
            check_defects(t, name, data, [{"reason": "role_unmapped", "severity": "warning", "role": "alternative"}])
        else:
            defects = data.get("defects", [])
            t.require(name + ".defects", bool(defects), data)
            t.eq(name + ".first-reason", defects[0].get("reason"), reason)
            t.check(name + ".errors-only", all(d.get("severity") == "error" for d in defects), defects)
            if label == "duplicate":
                t.eq(name + ".source", defects[0].get("source"), entries[0]["name"])
                t.eq(name + ".pointer", defects[0].get("pointer"), "/files/2/name")
    for i, (tool, pointer) in enumerate((("assess", "/files/0/size"), ("assess", "/files"), ("discover", "/detail"))):
        name = "inventory.argument-" + str(i)
        value = tool_result(t, name, replies[len(cases) + i], tool, problem="input_invalid")
        t.eq(name + ".pointer", value["problem"].get("pointer"), pointer)
