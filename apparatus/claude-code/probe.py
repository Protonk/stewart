"""One approved native probe: bounded setup, then at most three model sessions."""

import argparse
import base64
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture, pin = sibling("fixture"), sibling("pin")
REPO = Path(__file__).resolve().parents[2]
RUN = REPO / ".scratch/claude-code-probe-01"
PIN = REPO / ".scratch/claude-code-pin-01/pin.json"
MODEL = "claude-haiku-5-5"
ORIGINAL_CHECKER = "5abd0f59d856d90014ff7fe1b6566c9512b302e653e76c4df9fb9b001d206a1b"
VISIBLE_FLAGS = ["--restricted", "--tools", "--setting-sources", "--settings", "--strict-mcp-config", "--mcp-config",
                 "--allowedTools", "--permission-mode", "--permission-prompts", "--model",
                 "--no-session-persistence", "--input-format", "--output-format"]
PROMPT = ("You are testing a synthetic tool interface. Use only the supplied tools. Read "
          "the specimen, then record its marker word once. If a tool is denied, report "
          "the denial and stop without retrying. Do not perform any other task.\n")
INPUT = {"type": "user", "session_id": "", "parent_tool_use_id": None,
         "message": {"role": "user", "content": "Carry out the synthetic tool-interface check."}}
CONTROLS = {
    "DISABLE_UPDATES": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
    "CLAUDE_CODE_DISABLE_AGENT_VIEW": "1", "CLAUDE_CODE_DISABLE_FAST_MODE": "1",
    "ENABLE_CLAUDEAI_MCP_SERVERS": "false", "ENABLE_TOOL_SEARCH": "false",
    "CLAUDE_CODE_MAX_RETRIES": "0", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "2048",
}


def write_json(path, value):
    with path.open("x") as out:
        json.dump(value, out, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())


def environment(config):
    result = {key: os.environ[key] for key in ["HOME", "TMPDIR", "LANG"] if key in os.environ}
    result.update(CONTROLS)
    result.update(PATH="/usr/bin:/bin:/usr/sbin:/sbin", CLAUDE_CONFIG_DIR=str(config))
    return result


class State:
    """Reservations are durable before spawning; uncertain uses are never retried."""
    def __init__(self, root):
        self.root = root
        self.path = root / "state.json"
        self.data = fixture.decode(self.path.read_bytes()) if self.path.exists() else {"uses": {}}

    def save(self):
        tmp = self.root / "state.next"
        with tmp.open("w") as out:
            json.dump(self.data, out, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, self.path)
        fd = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def claim(self, name):
        allowed = {"version", "help", "auth-empty", "login", "auth-selected", "case-1", "case-2", "case-3"}
        if name not in allowed or name in self.data["uses"]:
            raise ValueError("invocation already reserved, or outside approved scope: " + name)
        self.data["uses"][name] = {"outcome": "reserved; execution uncertain until completion"}
        self.save()

    def finish(self, name, result):
        self.data["uses"][name] = result
        self.save()


def group_alive(pid, child=None):
    # Keep reaping the owned leader during observation retries. Waiting while
    # leaving an exited leader unreaped can keep the group unobservable.
    # EPERM itself never means absent; persistent denial is a failure.
    for attempt in range(20):
        if child is not None:
            child.poll()
        try:
            os.killpg(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.01)


def stop_group(child, event, grace=5):
    def note(kind, **fields):
        try:
            event(kind, **fields)
        except OSError:
            pass  # A broken recorder must never prevent termination.
    for sig, seconds in [(signal.SIGTERM, grace), (signal.SIGKILL, 1)]:
        if not group_alive(child.pid, child):
            break
        note("signal", signal=int(sig))
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            break
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            child.poll()  # Reap the owned child, including after SIGKILL.
            if not group_alive(child.pid, child):
                break
            time.sleep(0.02)
    child.wait(timeout=2)
    gone = not group_alive(child.pid, child)
    note("group-stopped", observed=gone)
    return gone


def validate_event(value):
    if not isinstance(value, dict):
        raise ValueError("stream event is not an object")
    if value.get("parent_tool_use_id") is not None:
        raise ValueError("unexpected delegated session")
    if value.get("type") == "system" and value.get("subtype") == "init":
        if value.get("apiKeySource") != "none" or value.get("claude_code_version") != pin.VERSION:
            raise ValueError("unexpected API-key source or harness version")
        if value.get("model") != MODEL or set(value.get("tools", [])) != fixture.TOOLS:
            raise ValueError("unexpected model or tool inventory")
        servers = value.get("mcp_servers", [])
        if len(servers) != 1 or servers[0].get("name") != "probe" or servers[0].get("status") != "connected":
            raise ValueError("MCP server is not the sole connected probe server")
        if value.get("plugins") or value.get("plugin_errors") or value.get("mcp_server_errors"):
            raise ValueError("unexpected plugin or server error")
        if value.get("permissionMode") != "dontAsk":
            raise ValueError("unexpected permission mode")
    if value.get("type") == "system" and value.get("subtype") in {"compact_boundary", "api_retry", "plugin_install"}:
        raise ValueError("unexpected compaction, retry or plugin installation")
    if value.get("type") == "system" and value.get("subtype") in {"task_started", "background_tasks_changed"}:
        raise ValueError("unexpected background work")
    if value.get("type") == "rate_limit_event":
        info = value.get("rate_limit_info", {})
        if info.get("status") == "rejected" or info.get("overageEnabled") is True:
            raise ValueError("quota exhausted or paid overflow enabled")
    if value.get("type") == "assistant":
        model = value.get("message", {}).get("model")
        if model and model not in {MODEL, "<synthetic>"}:
            raise ValueError("assistant message reports a different model")
        for block in value.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") not in fixture.TOOLS:
                raise ValueError("assistant attempted an unexpected tool")
    if value.get("type") == "result" and value.get("is_error"):
        raise ValueError("harness reported an error; batch stopped")


def supervise(argv, cwd, env, out, timeout, payload=None, delay=0, stream=False, private_status=False, overall_deadline=None):
    """Capture before parsing, supervise the process group, send at most one input."""
    out.mkdir(mode=0o700, exist_ok=False)
    def event(kind, **fields):
        fixture.append(out / "process.jsonl", dict(kind=kind, time_ns=time.monotonic_ns(), **fields))
    event("launch-intent", argv=argv)  # No child if its observer cannot record.
    outputs = {}
    start = time.monotonic()
    deadline = min(start + timeout, overall_deadline) if overall_deadline is not None else start + timeout
    try:
        for name in ["stdout", "stderr"]:
            outputs[name] = io.BytesIO() if private_status else (out / (name + ".bin")).open("xb")
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, start_new_session=True)
    except BaseException:
        for stream_out in outputs.values():
            stream_out.close()
        raise
    selector = selectors.DefaultSelector()
    sent = False
    pending = b""
    events = []
    stopped = None
    group_gone = False
    try:
        event("spawn", pid=child.pid, pgid=child.pid, argv=argv)
        for channel in ["stdout", "stderr"]:
            pipe = getattr(child, channel)
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, channel)
        while selector.get_map() or child.poll() is None:
            now = time.monotonic()
            if now >= deadline:
                raise ValueError("session wall-clock limit reached")
            if (out.parent / "unexpected.jsonl").exists():
                raise ValueError("hook observed an unexpected tool")
            if not sent and now - start >= delay:
                if payload is not None:
                    child.stdin.write(payload)
                    child.stdin.flush()
                    event("input-sent", bytes=len(payload))
                child.stdin.close()
                sent = True
            for key, _ in selector.select(0.05):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                outputs[key.data].write(chunk)
                outputs[key.data].flush()
                if not private_status:
                    os.fsync(outputs[key.data].fileno())
                event("capture", channel=key.data, bytes=len(chunk))
                if stream and key.data == "stdout":
                    pending += chunk
                    if len(pending) > 16 * 1024 * 1024:
                        raise ValueError("oversized stream line")
                    while b"\n" in pending:
                        line, pending = pending.split(b"\n", 1)
                        value = fixture.decode(line)
                        validate_event(value)
                        events.append(value)
                        event("stream-event", type=value.get("type"), subtype=value.get("subtype"), before_input=not sent)
        if stream and pending:
            raise ValueError("unterminated stream event")
        group_gone = not group_alive(child.pid, child)
        if not group_gone:
            stopped = "descendant survived the harness"
    except (ValueError, OSError) as exc:
        stopped = str(exc)
    finally:
        try:
            if stopped is not None or child.poll() is None or group_alive(child.pid, child):
                group_gone = stop_group(child, event)
            else:
                child.wait()
                group_gone = True
                event("group-stopped", observed=True)
        except (OSError, subprocess.SubprocessError) as exc:
            # Preserve the failure, but do not leave the owned child running
            # merely because group observation or evidence writing failed.
            stopped = ((stopped + "; ") if stopped else "") + "termination/observation failure: " + str(exc)
            group_gone = False
            try:
                child.kill()
                child.wait(timeout=2)
            except (OSError, subprocess.SubprocessError):
                pass
        # Preserve bytes already in pipes even after a stop; never parse them into a pass.
        for name in outputs:
            pipe = getattr(child, name)
            try:
                tail = pipe.read() or b""
                outputs[name].write(tail)
            except BlockingIOError:
                pass
            pipe.close()
        selector.close()
        if not child.stdin.closed:
            child.stdin.close()
    result = {"exit": child.returncode, "stop": stopped, "group_gone": group_gone,
              "elapsed_seconds": time.monotonic() - start}
    raw = {name: stream_out.getvalue() for name, stream_out in outputs.items()} if private_status else None
    for stream_out in outputs.values():
        stream_out.close()
    write_json(out / "result.json", result)
    return result, events, raw


def bindings(state, correcting_checker=False):
    expected = state.data["bindings"]
    for path, digest in expected.items():
        if correcting_checker and path == str(Path(__file__).resolve()):
            continue
        if pin.digest(path) != digest:
            raise ValueError("bound input changed: " + path)
    if state.data["environment"] != environment(state.data["config"]):
        raise ValueError("launch environment changed since setup")


def prepare(state):
    receipt = fixture.decode(PIN.read_bytes())
    if receipt["version"] != pin.VERSION or receipt["signer"] != pin.FINGERPRINT or pin.digest(receipt["binary"]) != receipt["sha256"]:
        raise ValueError("verified binary pin is missing or changed")
    state.data.update(binary=receipt["binary"], model=MODEL,
                      approval="Principal approved the bounded proposal and confirmed extra usage disabled, 2026-11-10",
                      config=str(Path.home() / ".local/share/stewart-claude-code/probe-config"), cases=[])
    config = Path(state.data["config"])
    config.mkdir(mode=0o700, parents=True, exist_ok=False)
    (RUN / "empty-config").mkdir(mode=0o700)
    work = Path(tempfile.mkdtemp(prefix="stewart-claude-probe-", dir="/private/tmp"))
    (work / "setup").mkdir(mode=0o700)
    state.data["setup_cwd"] = str(work / "setup")
    sources = [Path(__file__).resolve(), Path(fixture.__file__).resolve(), Path(pin.__file__).resolve(), PIN, Path(receipt["binary"])]
    inputs = RUN / "inputs"
    inputs.mkdir(mode=0o700)
    for source in sources[:-1]:
        copy = inputs / source.name
        shutil.copyfile(source, copy)
    frozen_fixture = inputs / "fixture.py"
    sources += list(inputs.iterdir())
    for number in [1, 2, 3]:
        case = RUN / ("case-%d" % number)
        case.mkdir(mode=0o700)
        cwd = work / ("case-%d" % number)
        cwd.mkdir(mode=0o700)
        (case / "prompt.txt").write_text(PROMPT)
        hook_cmd = [sys.executable, "-I", "-B", str(frozen_fixture), "hook", str(case)]
        if number == 2:
            hook_cmd.append("--deny")
        write_json(case / "settings.json", {"forceLoginMethod": "claudeai", "fastMode": False, "fallbackModel": [],
                   "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": shlex.join(hook_cmd), "timeout": 5}]}]}})
        write_json(case / "mcp.json", {"mcpServers": {"probe": {"type": "stdio", "command": sys.executable,
                   "args": ["-I", "-B", str(frozen_fixture), "mcp", str(case)]}}})
        state.data["cases"].append({"case": str(case), "cwd": str(cwd)})
        sources += [case / "settings.json", case / "mcp.json", case / "prompt.txt"]
    state.data["bindings"] = {str(p): pin.digest(p) for p in sources}
    state.data["environment"] = environment(config)
    state.save()


def command(state, name, args, auth=False, config=None):
    bindings(state)
    state.claim(name)
    result, _, raw = supervise([state.data["binary"]] + args, state.data["setup_cwd"],
             environment(config or state.data["config"]), RUN / name, 30, private_status=auth)
    state.finish(name, result)
    if result["stop"] or not result["group_gone"]:
        raise ValueError(name + " did not finish under supervision")
    if auth:
        try:
            value = fixture.decode(raw["stdout"])
            safe = {k: value.get(k) for k in ["loggedIn", "authMethod", "configDirectory"]}
            if safe["authMethod"] not in {"none", "claude.ai", "oauth_token", "api_key", "api_key_helper", "third_party"} or not isinstance(safe["configDirectory"], str):
                raise ValueError("unexpected auth status fields")
            if safe["loggedIn"] is not None and not isinstance(safe["loggedIn"], bool):
                raise ValueError("unexpected login status field")
        except (ValueError, AttributeError):
            raise ValueError("auth status was not the documented JSON report; raw auth output was not retained")
        write_json(RUN / name / "auth-status.json", safe)
        expected = "none" if name == "auth-empty" else "claude.ai"
        if safe["authMethod"] != expected or safe["configDirectory"] != str(config or state.data["config"]):
            raise ValueError("unexpected authentication method or configuration directory")
        if result["exit"] != (1 if name == "auth-empty" else 0):
            raise ValueError("unexpected authentication exit status")
        return safe
    if result["exit"]:
        raise ValueError(name + " failed")
    return (RUN / name / "stdout.bin").read_text()


def check_version(version):
    if not version.startswith(pin.VERSION + " ") and version.strip() != pin.VERSION:
        raise ValueError("unexpected CLI version")


def check_help(help_text):
    # In the authenticated 2.1.322 bundle, --system-prompt-file and --max-turns
    # are explicitly registered with hideHelp(). The official CLI reference
    # documents both and says help is not an exhaustive flag inventory.
    for option in VISIBLE_FLAGS:
        if option not in help_text:
            raise ValueError("required visible option not identified in captured help: " + option)


def login_steps(state):
    command(state, "auth-empty", ["auth", "status"], auth=True, config=RUN / "empty-config")
    bindings(state)
    state.claim("login")
    print("Sign in through Claude's own flow using your subscription. This interaction is not recorded.", flush=True)
    rc = subprocess.call([state.data["binary"], "auth", "login"], cwd=state.data["setup_cwd"], env=environment(state.data["config"]))
    state.finish("login", {"exit": rc})
    if rc:
        raise ValueError("login failed; the one approved login attempt has been used")
    command(state, "auth-selected", ["auth", "status"], auth=True)
    state.data["setup_complete"] = True
    state.save()
    print("Setup verified. No model session was started.")


def setup(state):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("run setup in your own Terminal; the login interaction must not be captured by an agent")
    if state.path.exists():
        raise ValueError("setup already began; inspect its records before any further invocation")
    prepare(state)
    check_version(command(state, "version", ["--version"]))
    check_help(command(state, "help", ["--help"]))
    login_steps(state)


def check_setup_checkpoint(data):
    if data.get("setup_complete") or data.get("live_started") or set(data["uses"]) != {"version", "help"}:
        raise ValueError("continuation requires exactly the completed version/help checkpoint")
    for result in data["uses"].values():
        if result.get("exit") != 0 or result.get("stop") is not None or result.get("group_gone") is not True:
            raise ValueError("a completed setup check failed or has uncertain execution")


def finish_setup(state):
    """Continue this stopped setup after correcting its help-inventory check.

    No completed or reserved invocation is repeated. Preserve the original
    controller and all earlier records; append the correction's provenance.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("finish setup in your own Terminal so login remains uncaptured")
    check_setup_checkpoint(state.data)
    controller = Path(__file__).resolve()
    if state.data["bindings"].get(str(controller)) != ORIGINAL_CHECKER:
        raise ValueError("this continuation applies only to the reviewed help-check failure")
    bindings(state, correcting_checker=True)
    check_version((RUN / "version/stdout.bin").read_text())
    check_help((RUN / "help/stdout.bin").read_text())
    snapshot = RUN / "inputs/probe-corrected-help-check.py"
    with snapshot.open("xb") as out:
        out.write(controller.read_bytes())
        out.flush()
        os.fsync(out.fileno())
    new_digest = pin.digest(snapshot)
    correction = RUN / "setup-checker-correction.json"
    write_json(correction, {"reason": "Two documented CLI options are explicitly hidden from help; the approved argv and limits are unchanged.",
               "old_controller_sha256": ORIGINAL_CHECKER, "new_controller_sha256": new_digest,
               "version_output_sha256": pin.digest(RUN / "version/stdout.bin"),
               "help_output_sha256": pin.digest(RUN / "help/stdout.bin"),
               "hidden_options": ["--system-prompt-file", "--max-turns"], "repeated_invocations": []})
    state.data["bindings"].update({str(controller): new_digest, str(snapshot): new_digest, str(correction): pin.digest(correction)})
    state.data["setup_checker_correction"] = str(correction)
    state.save()
    print("Reusing successful version/help records; continuing only the unused authentication steps.", flush=True)
    login_steps(state)


def records(path):
    return [fixture.decode(line) for line in path.read_bytes().splitlines()] if path.exists() else []


def assessment(case, events, denial):
    effects = records(case / "effects.jsonl")
    hook_inputs = [fixture.decode(base64.b64decode(v["bytes_b64"])) for v in records(case / "hook-in.jsonl")]
    hook_outputs = [base64.b64decode(v["bytes_b64"]) for v in records(case / "hook-out.jsonl")]
    calls = [fixture.decode(base64.b64decode(v["bytes_b64"])) for v in records(case / "mcp-in.jsonl")]
    inits = [v for v in events if v.get("type") == "system" and v.get("subtype") == "init"]
    finals = [v for v in events if v.get("type") == "result"]
    notes = [v for v in effects if v["tool"] == "record_note"]
    read = any(v["tool"] == "read_specimen" for v in effects)
    attempted = any(v.get("tool_name") == "mcp__probe__record_note" for v in hook_inputs)
    if len(inits) != 1 or len(finals) != 1:
        return {"outcome": "failed", "reason": "missing or repeated initialization/final result"}
    if not read or not attempted:
        return {"outcome": "unexercised", "reason": "required read or hook-observed record attempt absent"}
    if denial:
        denied = any(raw and fixture.decode(raw).get("hookSpecificOutput", {}).get("permissionDecision") == "deny" for raw in hook_outputs)
        handler_called = any(v.get("method") == "tools/call" and v.get("params", {}).get("name") == "record_note" for v in calls)
        passed = denied and not notes and not handler_called
    else:
        passed = len(notes) == 1 and notes[0].get("text") == "orchard"
    return {"outcome": "observed" if passed else "failed", "effect_count": len(notes),
            "usage_reported": finals[0].get("usage"), "model_usage_reported": finals[0].get("modelUsage"),
            "usage_scope": "harness report only; missing/internal consumption is not inferred as zero"}


def live(state):
    if not state.data.get("setup_complete") or state.data.get("live_started"):
        raise ValueError("setup must finish first; the model batch can start only once")
    bindings(state)
    state.data["live_started"] = True
    state.save()
    deadline = time.monotonic() + 360
    results = []
    for number, row in enumerate(state.data["cases"], 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        bindings(state)
        name = "case-%d" % number
        state.claim(name)
        case = Path(row["case"])
        argv = [state.data["binary"], "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                "--restricted", "--tools", "", "--setting-sources", "", "--settings", str(case / "settings.json"),
                "--strict-mcp-config", "--mcp-config", str(case / "mcp.json"), "--allowedTools",
                "mcp__probe__read_specimen", "mcp__probe__record_note", "--permission-mode", "dontAsk",
                "--permission-prompts", "none", "--system-prompt-file", str(case / "prompt.txt"),
                "--model", MODEL, "--max-turns", "4", "--no-session-persistence"]
        write_json(case / "launch.json", {"argv": argv, "cwd": row["cwd"], "environment": environment(state.data["config"])})
        result, events, _ = supervise(argv, row["cwd"], environment(state.data["config"]), case / "process",
                   min(120, remaining), payload=(json.dumps(INPUT) + "\n").encode(), delay=5 if number == 1 else 0,
                   stream=True, overall_deadline=deadline)
        state.finish(name, result)
        if result["stop"] or result["exit"] or not result["group_gone"]:
            observed = {"outcome": "failed", "reason": "process or launch checks failed", "process": result}
        else:
            observed = assessment(case, events, number == 2)
        write_json(case / "assessment.json", observed)
        results.append(dict(case=number, **observed))
        print("%s: %s" % (name, observed["outcome"]), flush=True)
        if result["stop"] or result["exit"] or not result["group_gone"]:
            break
    for number in range(len(results) + 1, 4):
        results.append({"case": number, "outcome": "unexercised", "reason": "batch stopped before launch"})
    write_json(RUN / "RESULT.json", {"native_development_only": True, "cases": results})
    state.data["live_complete"] = True
    state.save()
    print("Results: " + str(RUN / "RESULT.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "finish-setup", "live"])
    parser.add_argument("--extra-usage-disabled", action="store_true", help="confirm the approved included-usage-only condition remains true")
    args = parser.parse_args()
    os.umask(0o077)
    RUN.mkdir(mode=0o700, exist_ok=True)
    try:
        with (RUN / "active.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            state = State(RUN)
            if args.action == "setup":
                setup(state)
            elif args.action == "finish-setup":
                finish_setup(state)
            else:
                if not args.extra_usage_disabled:
                    raise ValueError("live phase requires the included-usage-only condition")
                live(state)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(1, "probe stopped: %s\nNo automatic replacement or retry is allowed.\n" % exc)


if __name__ == "__main__":
    main()
