"""Offline harness peer. It invokes only the synthetic MCP server and hook."""

import json
from pathlib import Path
import subprocess
import sys

case = Path(sys.argv[1])
mode = sys.argv[2]
fixture = str(Path(__file__).with_name("fixture.py"))
tools = ["mcp__probe__read_specimen", "mcp__probe__record_note"]


def emit(value):
    print(json.dumps(value), flush=True)


if mode == "malformed":
    print("{broken", flush=True)
    sys.stdin.buffer.read()
    sys.exit(0)

emit({"type": "system", "subtype": "init", "model": "claude-haiku-5-5",
      "apiKeySource": "none", "claude_code_version": "2.1.322",
      "tools": tools + (["Bash"] if mode == "extra-tool" else []), "permissionMode": "dontAsk",
      "mcp_servers": [{"name": "probe", "status": "connected"}], "plugins": []})
sys.stdin.buffer.read()
server = subprocess.Popen([sys.executable, "-I", "-B", fixture, "mcp", str(case)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)


def rpc(message, reply=True):
    # Deliberate spacing: the recorder must retain these original bytes.
    server.stdin.write((json.dumps(message, indent=None, separators=(", ", ": ")) + "\n").encode())
    server.stdin.flush()
    return json.loads(server.stdout.readline()) if reply else None


try:
    rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "fake", "version": "1"}}})
    rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}, reply=False)
    rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    for number, name, args in [(3, "read_specimen", {}), (4, "record_note", {"text": "orchard"})]:
        hook = [sys.executable, "-I", "-B", fixture, "hook", str(case)]
        if mode == "deny":
            hook.append("--deny")
        outcome = subprocess.run(hook, input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": "mcp__probe__" + name, "tool_input": args}).encode(), capture_output=True, check=True)
        if outcome.stdout and json.loads(outcome.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny":
            break
        response = rpc({"jsonrpc": "2.0", "id": number, "method": "tools/call", "params": {"name": name, "arguments": args}})
        assert "result" in response, response
finally:
    server.stdin.close()
    server.wait(timeout=2)
emit({"type": "result", "is_error": False, "usage": {"input_tokens": 10, "output_tokens": 5}})
