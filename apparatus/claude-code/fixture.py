"""Synthetic stdio MCP server and command hook; no Claude launch capability."""

import argparse
import base64
import json
import os
from pathlib import Path
import sys
import time

TOOLS = {"mcp__probe__read_specimen", "mcp__probe__record_note"}
CLOCK_NAME = "CLOCK_UPTIME_RAW" if sys.platform == "darwin" else "CLOCK_MONOTONIC"
CLOCK_ID = getattr(time, CLOCK_NAME)


def clock_ns():
    # Python <3.10 gives macOS time.monotonic_ns() a process-local origin.
    # Use the kernel clock directly so separate witnesses share an origin.
    return time.clock_gettime_ns(CLOCK_ID)


def observation(**fields):
    return dict(fields, time_ns=clock_ns(), clock=CLOCK_NAME, observer_pid=os.getpid())


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("non-finite JSON number")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def append(path, value):
    data = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def capture(case, channel, raw):
    append(case / (channel + ".jsonl"), observation(bytes_b64=base64.b64encode(raw).decode()))


def tools():
    return [
        {"name": "read_specimen", "description": "Read the synthetic specimen.",
         "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"name": "record_note", "description": "Record the specimen's marker word once.",
         "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}},
                         "required": ["text"], "additionalProperties": False}},
    ]


def serve(case):
    initialized = False
    for raw in sys.stdin.buffer:
        capture(case, "mcp-in", raw)  # Must succeed before parsing or effects.
        request = decode(raw)
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            raise ValueError("invalid JSON-RPC envelope")
        method = request.get("method")
        if "id" not in request:
            if method == "notifications/initialized":
                initialized = True
            continue
        reply = {"jsonrpc": "2.0", "id": request["id"]}
        params = request.get("params", {})
        if method == "initialize":
            reply["result"] = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                               "serverInfo": {"name": "stewart-probe", "version": "1"}}
        elif method == "ping":
            reply["result"] = {}
        elif not initialized:
            reply["error"] = {"code": -32000, "message": "initialize first"}
        elif method == "tools/list":
            reply["result"] = {"tools": tools()}
        elif method == "tools/call":
            name, args = params.get("name"), params.get("arguments", {})
            if name == "read_specimen" and args == {}:
                append(case / "effects.jsonl", observation(tool=name))
                reply["result"] = {"content": [{"type": "text", "text": "The marker word is orchard.\n"}]}
            elif name == "record_note" and isinstance(args, dict) and set(args) == {"text"} and isinstance(args["text"], str):
                append(case / "effects.jsonl", observation(tool=name, text=args["text"]))
                reply["result"] = {"content": [{"type": "text", "text": "recorded"}]}
            else:
                reply["error"] = {"code": -32602, "message": "unknown tool or invalid arguments"}
        else:
            reply["error"] = {"code": -32601, "message": "method not found"}
        encoded = (json.dumps(reply, separators=(",", ":")) + "\n").encode()
        capture(case, "mcp-out", encoded)
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()


def hook(case, deny):
    raw = sys.stdin.buffer.read()
    capture(case, "hook-in", raw)
    event = decode(raw)
    name = event.get("tool_name")
    if name not in TOOLS:
        append(case / "unexpected.jsonl", observation(reason="unexpected tool at hook"))
    if name not in TOOLS or (deny and name == "mcp__probe__record_note"):
        result = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                          "permissionDecisionReason": "Synthetic probe denial; stop without retrying."}}
        output = (json.dumps(result, separators=(",", ":")) + "\n").encode()
    else:
        output = b""
    capture(case, "hook-out", output)
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["mcp", "hook"])
    parser.add_argument("case", type=Path)
    parser.add_argument("--deny", action="store_true")
    args = parser.parse_args()
    try:
        if args.mode == "mcp":
            serve(args.case)
        else:
            hook(args.case, args.deny)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # Never turn a failed witness write into a successful tool or hook.
        if args.mode == "hook":
            sys.stderr.write("Probe hook could not record or interpret its input; stop.\n")
            return 2
        sys.stderr.write("Probe MCP recorder failed; no successful reply.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
