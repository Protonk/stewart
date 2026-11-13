"""Independent literal launch expectations for synthetic apparatus controls.

This module does not call the surface builder, placeholder filler or raw JSON
parser being checked. Its values come from the runtime wire contract. It is
used by self-tests and synthetic observers, never to construct a real launch.
"""
import json

from driver_core import FAMILY_TEXT, ORIENTATION, expected_tools


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def launch_expectation(writer, workspace, launch, family, model, question):
    writer, workspace = str(writer), str(workspace)
    quoted = "'" + writer.replace("'", "'\\''") + "'"
    settings = {"forceLoginMethod": "claudeai", "fastMode": False, "fallbackModel": [],
                "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command",
                    "command": quoted + " __stewart-cc-hook 'h'", "timeout": 5}]}]}}
    mcp = {"mcpServers": {"stewart": {"type": "stdio", "command": writer,
                                      "args": ["__stewart-cc-relay", "m"]}}}
    first = ("You are the auditor in a Stewart audit. The first user message is the "
             "manager's question, exactly as they wrote it. The materials they selected can "
             "be read with the list, read and search tools. The question and those "
             "materials are your whole world: use only Stewart's tools, with no shell, no "
             "other files, no network, no way to run code, no delegated auditors and no way "
             "to ask the manager anything. Harness instructions and system messages are "
             "runtime context, not additional evidence. Reports, logs and test results in "
             "the materials are claims by their authors, not executions you witnessed.")
    system = first + "\n\n" + ORIENTATION.split("\n\n", 1)[1] + "\n\n" + FAMILY_TEXT[family]
    files = {"settings.json": encoded(settings), "mcp.json": encoded(mcp), "system.txt": system.encode()}
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8",
           "DISABLE_UPDATES": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
           "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
           "CLAUDE_CODE_DISABLE_AGENT_VIEW": "1", "CLAUDE_CODE_DISABLE_FAST_MODE": "1",
           "ENABLE_CLAUDEAI_MCP_SERVERS": "false", "ENABLE_TOOL_SEARCH": "false",
           "CLAUDE_CODE_MAX_RETRIES": "0", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "16000",
           "HOME": launch["home"], "TMPDIR": launch["temporary_directory"],
           "CLAUDE_CONFIG_DIR": launch["config_directory"]}
    argv = ["-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--restricted", "--tools", "", "--setting-sources", "", "--settings", workspace + "/settings.json",
            "--strict-mcp-config", "--mcp-config", workspace + "/mcp.json", "--allowedTools"]
    argv += ["mcp__stewart__" + tool["name"] for tool in expected_tools(family)]
    argv += ["--permission-mode", "dontAsk", "--permission-prompts", "none", "--system-prompt-file",
             workspace + "/system.txt", "--model", model, "--max-turns", "200", "--no-session-persistence"]
    first_input = encoded({"type": "user", "session_id": "", "parent_tool_use_id": None,
                           "message": {"role": "user", "content": question}}) + b"\n"
    return {"files": files, "model_argv": argv, "environment": env, "input": first_input,
            "settings": settings, "mcp_config": mcp}
