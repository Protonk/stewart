"""The launch profile turns the harness invocation into pinned workspace data.

Pairs: the printed block run against a stand-in harness that records its
argv, environment and working directory, against the same block after the
profile file changes; a profile fault refused before any session exists,
against the same workspace with the fault removed; a workspace with no
profile, which must behave exactly as before.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex

import pytest

from stewart import _util as _hash
from stewart.cli import EXIT_OK, main
from stewart.collect import collect
from stewart.coordination import record_launch
from stewart._bootstrap import StewartError
from stewart.launch_profile import PROFILE_NAME, handoff_prompt, validate_profile
from stewart.prepare import prepare
from stewart.status import status
import stewart_support as support
from stewart_support import WS, read_json

pytestmark = pytest.mark.system

#: A stand-in harness: records how it was invoked, then exits 0. It stands
#: for whatever the real TUI does once started, which this test does not run.
STUB = """#!/bin/sh
printf '%s\\n' "$PWD" > "$STEWART_STUB_OUT/cwd"
printf '%s\\n' "${CLAUDE_CODE_DISABLE_AUTO_MEMORY-unset}" > "$STEWART_STUB_OUT/env"
: > "$STEWART_STUB_OUT/argv"
for arg in "$@"; do printf '%s\\n' "$arg" >> "$STEWART_STUB_OUT/argv"; done
exit "${STEWART_STUB_EXIT:-0}"
"""


def stub_harness(tmp_path: Path) -> tuple[Path, Path]:
    """Install the stand-in harness on a private PATH entry; return (bindir, output dir)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "claude").write_text(STUB)
    (bindir / "claude").chmod(0o755)
    out = tmp_path / "stub-out"
    out.mkdir(exist_ok=True)
    return bindir, out


def run_block(run_cmd, block: str, tmp_path: Path, *, exit_code: int = 0):
    bindir, out = stub_harness(tmp_path)
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STEWART_STUB_OUT": str(out),
           "STEWART_STUB_EXIT": str(exit_code)}
    return run_cmd(["/bin/sh", "-c", block], cwd=tmp_path, env=env, timeout=60), out


def recorded_options(out, scope):
    """Assert fixed boundary options before examining the profile's argv suffix."""
    args = (out / "argv").read_text().splitlines()
    assert args[:12] == ["--restricted", "--safe-mode", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                         "--permission-mode", "dontAsk", "--tools", "Read,Glob,Grep,Edit,Write,Bash",
                         "--add-dir", scope["runtime"], "--settings"]
    settings = json.loads(args[12])
    assert settings["permissions"]["blockReadsOutsideWorkingDirectories"] is True
    assert settings["sandbox"]["filesystem"]["allowRead"] == [
        scope["worktree"], scope["runtime"], scope["git_common"], scope["interpreter_prefix"]]
    assert scope["repository"] in settings["sandbox"]["filesystem"]["denyRead"]
    assert scope["runtime"] in settings["sandbox"]["filesystem"]["denyWrite"]
    return args[13:]


def render_scope(worktree):
    """Disjoint literal paths for shell rendering; no filesystem access is implied."""
    from stewart.auditor_scope import SCOPE_SCHEMA
    sibling = worktree.parent.with_name(worktree.parent.name + "-scope")
    return {"schema": SCOPE_SCHEMA, "repository": str(sibling / "project"), "worktree": str(worktree),
            "runtime": str(sibling / "runtime"), "git_common": str(sibling / "git"),
            "manager_home": str(sibling / "manager"), "interpreter_prefix": str(sibling / "python"),
            "private_roots": sorted([str(sibling / "manager"), str(sibling / "project")])}


def profile(**overrides) -> dict:
    base = {
        "schema": "stewart.launch-profile/2", "scope_adapter": "claude-code-restricted/1", "harness": "stub-tui", "style": "terminal",
        "model": "opus", "effort": "max", "actor": "maintainer",
        "env": {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"},
        "command": ["claude", "--model", "{model}", "--effort", "{effort}", "{prompt}"],
        "note": "stub harness; the first prompt is absolute",
    }
    base.update(overrides)
    return base


def write_profile(checkout, document) -> Path:
    location = checkout.repo / WS / PROFILE_NAME
    location.write_text(json.dumps(document, indent=2) + "\n")
    return location


def test_profile_is_pinned_rendered_and_runs_the_harness_exactly_as_printed(tmp_path, run_cmd, capsys):
    checkout = support.make_checkout(tmp_path, run_cmd, name="main with 'quotes' and spaces")
    ident = checkout.meta["audit_id"]
    location = write_profile(checkout, profile())
    pinned_digest = _hash.sha256_bytes((location).read_bytes())
    prepared = prepare(checkout.ws, checkout.prompt_commit())
    session, worktree = Path(prepared["session"]), Path(prepared["worktree"])
    assert prepared["launch_profile"]["sha256"] == pinned_digest and prepared["launch_profile"]["model"] == "opus"
    command = prepared["launch_command"]
    lines = command.splitlines()
    assert lines[0] == "(" and lines[-1] == ")" and lines[2] == f"  cd {shlex.quote(str(worktree))} &&"
    assert lines[3] == "  CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 \\" and lines[4].startswith("    claude --restricted --safe-mode ")
    assert read_json(session / "session.json")["launch_profile"]["sha256"] == pinned_digest
    assert prepared["probe_command"] is None, "this profile declares no probe"
    assert lines[-6].startswith("  printf '%s %s\\n' \"$stewart_exit\"") and shlex.quote(prepared["exit_log"]) in lines[-6]
    # Run the printed block against the stand-in harness from an unrelated directory.
    result, out = run_block(run_cmd, command, tmp_path)
    assert result.returncode == 0, result.stderr
    assert (out / "cwd").read_text().strip() == str(worktree), "the subshell changed into the worktree"
    assert (out / "env").read_text().strip() == "1", "the profile's environment reached the harness"
    expected_prompt = handoff_prompt(prepared["launch"], worktree)
    assert recorded_options(out, prepared["auditor_scope"]) == ["--model", "opus", "--effort", "max", "--", expected_prompt], (
        "every token, including a prompt with absolute paths that contain quotes and spaces, must arrive intact")
    assert Path.cwd() != worktree, "the caller's directory is untouched"
    view = status(checkout.ws, ident)
    handoff = next(a for a in view["next_actions"] if a["action"] == "handoff")
    assert handoff["command"] == command and handoff["prompt"] == expected_prompt
    launch_action = next(a for a in view["next_actions"] if a["action"] == "launch")
    assert launch_action["argv"][-1] == "--from-profile" and "--style" not in launch_action["argv"]
    assert view["launch_profile"] == {"path": f"{WS}/{PROFILE_NAME}", "sha256": pinned_digest, "harness": "stub-tui",
                                      "style": "terminal", "model": "opus", "effort": "max", "has_probe": False}
    # Pair: editing the file after preparation changes nothing for this session.
    write_profile(checkout, profile(model="haiku", env={}, note="edited later"))
    again = status(checkout.ws, ident)
    assert next(a for a in again["next_actions"] if a["action"] == "handoff")["command"] == command
    launched = record_launch(checkout.ws, ident, from_profile=True)
    record = launched["record"]
    assert (record["style"], record["model"], record["effort"], record["actor"]) == ("terminal", "opus", "max", "maintainer")
    assert record["note"] == profile()["note"] and record["harness"] == "stub-tui"
    assert record["profile"] == {"path": f"{WS}/{PROFILE_NAME}", "sha256": pinned_digest}
    assert record["command"] == command, "the record keeps the exact block the manager was given"
    overridden = record_launch(checkout.ws, ident, from_profile=True, model="sonnet", note="override")["record"]
    assert (overridden["model"], overridden["effort"], overridden["note"]) == ("sonnet", "max", "override")
    assert overridden["profile"]["sha256"] == pinned_digest, "an override still names the profile it departed from"
    assert "--model sonnet --effort max" in overridden["command"], "the printed command must use acknowledged overrides"
    # The next session pins the edited file.
    checkout.meta["audit_id"] = "second-question"
    checkout.meta["report_path"] = checkout.ws.report_path("second-question")
    later = prepare(checkout.ws, checkout.prompt_commit())
    assert later["launch_profile"]["model"] == "haiku" and "CLAUDE_CODE_DISABLE_AUTO_MEMORY" not in later["launch_command"]
    assert "--model haiku --effort max" in later["launch_command"]
    base = ["--repo", str(checkout.repo), "--workspace", WS]
    assert main(base + ["status", "--audit-id", ident]) == EXIT_OK
    assert main(base + ["launch", "--audit-id", ident, "--from-profile"]) == EXIT_OK
    out_text = capsys.readouterr().out
    assert "terminal command (from the pinned launch profile):" in out_text and f"    {lines[1]}" in out_text
    assert f"Launch profile: {WS}/{PROFILE_NAME} ({pinned_digest[:12]}…) pinned at preparation" in out_text
    assert "From profile" in out_text and "the rendered command is in the record" in out_text


@pytest.mark.parametrize("fault", ["unknown_field", "no_prompt", "unknown_placeholder", "stray_brace", "bad_env",
                                   "empty_command", "schema", "style", "not_json", "symlink", "directory",
                                   "scope_adapter", "harness_env", "settings_override"])
def test_profile_faults_refuse_before_any_session_exists(checkout, fault):
    location = checkout.repo / WS / PROFILE_NAME
    documents = {
        "unknown_field": profile(extra=1),
        "no_prompt": profile(command=["claude", "--model", "{model}"]),
        "unknown_placeholder": profile(command=["claude", "{home}", "{prompt}"]),
        "stray_brace": profile(command=["claude", "{prompt}", "{"]),
        "bad_env": profile(env={"1BAD": "x"}),
        "empty_command": profile(command=[]),
        "schema": profile(schema="stewart.launch-profile/0"),
        "style": profile(style="cloud"),
        "scope_adapter": profile(scope_adapter="unqualified-harness/1"),
        "harness_env": profile(env={"CLAUDE_CODE_DISABLE_SANDBOX": "1"}),
        "settings_override": profile(command=["claude", "--settings", "unrestricted.json", "{prompt}"]),
    }
    if fault in documents:
        write_profile(checkout, documents[fault])
    elif fault == "not_json":
        location.write_text("{not json\n")
    elif fault == "symlink":
        elsewhere = checkout.repo / "elsewhere.json"
        elsewhere.write_text(json.dumps(profile()))
        location.symlink_to(elsewhere)
    else:
        location.mkdir()
    revision = checkout.prompt_commit()
    with pytest.raises(StewartError) as refused:
        prepare(checkout.ws, revision)
    assert refused.value.reason == "launch_profile", fault
    assert not (checkout.repo / ".scratch").exists(), "a profile fault must refuse before a session is allocated"
    # Control: the same workspace with the fault removed prepares and prints a command.
    if location.is_dir():
        location.rmdir()
    else:
        location.unlink()
    write_profile(checkout, profile())
    assert prepare(checkout.ws, revision)["launch_command"].startswith("(\n  stewart_exit=0\n  cd ")


def test_validate_profile_defaults_and_keeps_only_declared_fields():
    minimal = validate_profile({"schema": "stewart.launch-profile/2", "scope_adapter": "claude-code-restricted/1", "harness": "h", "model": "m", "effort": "e",
                                "actor": "a", "command": ["x", "{prompt}"]})
    assert minimal["style"] == "terminal" and minimal["env"] == {} and minimal["note"] == "" and minimal["probe"] is None
    assert set(minimal) == {"schema", "scope_adapter", "harness", "style", "model", "effort", "actor", "env", "command", "probe", "note"}


def test_without_a_profile_nothing_changes_and_from_profile_is_refused(checkout):
    ident = checkout.meta["audit_id"]
    prepared = support.prepared_session(checkout, report=None)
    assert prepared.prepared["launch_profile"] is None and prepared.prepared["launch_command"] is None
    assert read_json(prepared.session / "session.json")["launch_profile"] is None
    view = status(checkout.ws, ident)
    assert view["launch_profile"] is None
    handoff = next(a for a in view["next_actions"] if a["action"] == "handoff")
    assert "command" not in handoff and handoff["prompt"] == handoff_prompt(prepared.prepared["launch"], prepared.worktree)
    assert "--style" in next(a for a in view["next_actions"] if a["action"] == "launch")["argv"]
    assert view["harness_exits"] == [] and view["launch_profile_override"] is None
    with pytest.raises(StewartError) as refused:
        record_launch(checkout.ws, ident, from_profile=True)
    assert refused.value.reason == "launch_profile_missing" and refused.value.next_steps
    assert not (prepared.session / "launches").exists()
    explicit = record_launch(checkout.ws, ident, style="terminal", model="opus", effort="max", actor="manager")["record"]
    assert explicit["profile"] is None and explicit["command"] is None and explicit["harness"] is None
    assert explicit["profile_override"] is None
    assert main(["--repo", str(checkout.repo), "--workspace", WS, "launch", "--audit-id", ident, "--style",
                 "terminal", "--model", "opus", "--effort", "max"]) != EXIT_OK, "an actor is still required by hand"


def test_probe_is_rendered_ahead_of_the_launch_and_echoes_the_harness_exit(tmp_path, run_cmd, capsys):
    checkout = support.make_checkout(tmp_path, run_cmd)
    ident = checkout.meta["audit_id"]
    write_profile(checkout, profile(probe=["claude", "--model", "{model}", "--effort", "{effort}", "-p", "say OK"]))
    prepared = prepare(checkout.ws, checkout.prompt_commit())
    probe = prepared["probe_command"]
    assert probe.splitlines()[-3] == '  echo "probe exit $stewart_exit"' and probe.splitlines()[-1] == ")"
    assert "--model opus --effort max -p -- 'say OK'" in probe and "{model}" not in probe
    assert "HARNESS-EXIT" not in probe, "a probe is watched by a person and records nothing"
    result, out = run_block(run_cmd, probe, tmp_path, exit_code=7)
    assert result.returncode == 7 and "probe exit 7" in result.stdout, (
        "the probe's own exit is echoed so a stale flag or model is visible while the manager watches")
    assert recorded_options(out, prepared["auditor_scope"]) == ["--model", "opus", "--effort", "max", "-p", "--", "say OK"]
    assert not (Path(prepared["session"]) / "HARNESS-EXIT.txt").exists()
    view = status(checkout.ws, ident)
    handoff = next(a for a in view["next_actions"] if a["action"] == "handoff")
    assert handoff["probe"] == probe and handoff["profile_source"] == "pinned"
    assert handoff["exit_log"] == prepared["exit_log"] and view["launch_profile"]["has_probe"] is True
    assert main(["--repo", str(checkout.repo), "--workspace", WS, "status", "--audit-id", ident]) == EXIT_OK
    text = capsys.readouterr().out
    assert text.index("probe first (expect 'probe exit 0'):") < text.index("terminal command (from the pinned launch profile):")
    assert "probe present" in text and "the harness's exit code is appended to" in text
    # Pair: the same workspace without a probe prints none and says so.
    write_profile(checkout, profile())
    checkout.meta["audit_id"] = "second-question"
    checkout.meta["report_path"] = checkout.ws.report_path("second-question")
    later = prepare(checkout.ws, checkout.prompt_commit())
    assert later["probe_command"] is None
    view = status(checkout.ws, "second-question")
    assert next(a for a in view["next_actions"] if a["action"] == "handoff")["probe"] is None
    assert view["launch_profile"]["has_probe"] is False
    assert main(["--repo", str(checkout.repo), "--workspace", WS, "status", "--audit-id", "second-question"]) == EXIT_OK
    text = capsys.readouterr().out
    assert "probe first" not in text and "no probe" in text


def test_launch_block_appends_the_harness_exit_and_status_reads_it(tmp_path, run_cmd, capsys):
    checkout = support.make_checkout(tmp_path, run_cmd)
    ident = checkout.meta["audit_id"]
    write_profile(checkout, profile())
    prepared = prepare(checkout.ws, checkout.prompt_commit())
    log = Path(prepared["exit_log"])
    assert log == Path(prepared["session"]) / "HARNESS-EXIT.txt" and not log.exists()
    run_block(run_cmd, prepared["launch_command"], tmp_path, exit_code=0)
    first = log.read_text().splitlines()
    assert len(first) == 1 and first[0].startswith("0 ") and first[0].endswith("Z")
    view = status(checkout.ws, ident)
    assert view["harness_exits"] == [{"exit": 0, "at": first[0].split()[1]}]
    assert not any("harness exited" in item for item in view["outstanding"])
    run_block(run_cmd, prepared["launch_command"], tmp_path, exit_code=2)
    assert len(log.read_text().splitlines()) == 2, "the log is appended, never overwritten"
    view = status(checkout.ws, ident)
    assert [e["exit"] for e in view["harness_exits"]] == [0, 2]
    assert any("harness exited 2" in item and "no collection exists" in item for item in view["outstanding"]), (
        "a failing harness with no collection is the signature of a launch nobody watched")
    assert main(["--repo", str(checkout.repo), "--workspace", WS, "status", "--audit-id", ident]) == EXIT_OK
    assert "Harness exits: 2 recorded by the launch block; last exit 2 at" in capsys.readouterr().out
    # Pair: once a collection exists the exit is a fact, not an outstanding item.
    (Path(prepared["worktree"]) / checkout.meta["report_path"]).write_text("Status: partial\n")
    collect(checkout.ws, ident, auditor_stopped="interrupted")
    view = status(checkout.ws, ident)
    assert [e["exit"] for e in view["harness_exits"]] == [0, 2]
    assert not any("harness exited" in item for item in view["outstanding"])
    # A malformed line is reported, and the well-formed lines still count.
    with log.open("a") as stream:
        stream.write("garbage here\n")
    view = status(checkout.ws, ident)
    assert [e["exit"] for e in view["harness_exits"]] == [0, 2]
    assert any(p["reason"] == "exit_log_malformed" for p in view["session"]["problems"])


def test_override_profile_renders_for_an_existing_session_and_records_both_digests(tmp_path, run_cmd):
    checkout = support.make_checkout(tmp_path, run_cmd)
    ident = checkout.meta["audit_id"]
    pinned_digest = _hash.sha256_bytes((write_profile(checkout, profile())).read_bytes())
    prepare(checkout.ws, checkout.prompt_commit())
    override_rel = "audits/override-profile.json"
    override = checkout.repo / override_rel
    override.write_text(json.dumps(profile(model="haiku", env={}, probe=["claude", "--model", "{model}", "-p", "OK"])))
    override_digest = _hash.sha256_bytes((override).read_bytes())
    view = status(checkout.ws, ident, profile=override_rel)
    assert view["launch_profile"]["model"] == "opus" and view["launch_profile_override"]["model"] == "haiku"
    handoff = next(a for a in view["next_actions"] if a["action"] == "handoff")
    assert "--model haiku" in handoff["command"] and handoff["profile_source"] == "override"
    assert handoff["probe"] and "--model haiku -p -- OK" in handoff["probe"]
    launch_action = next(a for a in view["next_actions"] if a["action"] == "launch")
    assert launch_action["argv"][-3:] == ["--from-profile", "--profile", override_rel]
    record = record_launch(checkout.ws, ident, profile_path=override_rel)["record"]
    assert record["model"] == "haiku" and record["harness"] == "stub-tui"
    assert record["profile"]["sha256"] == pinned_digest and record["profile_override"]["sha256"] == override_digest
    assert "--model haiku" in record["command"] and record["command"].endswith(")")
    # The pinned view is untouched by an override request elsewhere.
    plain = status(checkout.ws, ident)
    assert plain["launch_profile_override"] is None
    assert "--model opus" in next(a for a in plain["next_actions"] if a["action"] == "handoff")["command"]
    for bad in ("audits/nope.json", "../outside.json"):
        with pytest.raises(StewartError) as refused:
            status(checkout.ws, ident, profile=bad)
        assert refused.value.reason in {"launch_profile", "path_escape"}, bad
    # A session prepared without any profile can still take an override.
    (checkout.repo / WS / PROFILE_NAME).unlink()
    checkout.meta["audit_id"] = "bare-question"
    checkout.meta["report_path"] = checkout.ws.report_path("bare-question")
    bare = prepare(checkout.ws, checkout.prompt_commit())
    assert bare["launch_profile"] is None
    view = status(checkout.ws, "bare-question", profile=override_rel)
    assert view["launch_profile"] is None and view["launch_profile_override"]["sha256"] == override_digest
    assert "--model haiku" in next(a for a in view["next_actions"] if a["action"] == "handoff")["command"]
    record = record_launch(checkout.ws, "bare-question", profile_path=override_rel)["record"]
    assert record["profile"] is None and record["profile_override"]["sha256"] == override_digest


@pytest.mark.parametrize("shell", ["/bin/sh", "/bin/zsh"])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_printed_blocks_preserve_status_with_errexit_and_probe_gates_launch(tmp_path, run_cmd, shell, exit_code):
    from stewart.launch_profile import render_command, render_probe

    bindir, out = stub_harness(tmp_path)
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STEWART_STUB_OUT": str(out),
           "STEWART_STUB_EXIT": str(exit_code)}
    # Quoted unrelated paths and environment are ignored by status propagation.
    worktree = tmp_path / "checkout with 'quotes'"
    worktree.mkdir()
    log = tmp_path / "exits"
    launch = render_command(profile(), worktree=worktree, launch_path=tmp_path / "LAUNCH.md", exit_log=log, scope=render_scope(worktree))
    launched = run_cmd([shell, "-c", "set -e\n" + launch], cwd=tmp_path, env=env)
    assert launched.returncode == exit_code, launched.stderr
    assert log.read_text().split()[0] == str(exit_code), "errexit cannot skip recording a failing harness"
    probe = render_probe(profile(probe=["claude", "-p", "OK"]), worktree=worktree, launch_path="LAUNCH.md", scope=render_scope(worktree))
    marker = tmp_path / "launch-was-permitted"
    checked = run_cmd([shell, "-c", "set -e\n" + probe + " && touch " + shlex.quote(str(marker))], cwd=tmp_path, env=env)
    assert checked.returncode == exit_code
    assert marker.exists() == (exit_code == 0), "a failed probe must gate a chained launch"
    assert f"probe exit {exit_code}" in checked.stdout
    assert len(log.read_text().splitlines()) == 1, "probe status must not masquerade as a TUI exit"


@pytest.mark.parametrize("failure", ["cd", "missing_command", "log_after_success", "log_after_failure"])
def test_launch_reports_setup_or_recording_failures_without_masking_harness_status(tmp_path, run_cmd, failure):
    from stewart.launch_profile import render_command

    bindir, out = stub_harness(tmp_path)
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STEWART_STUB_OUT": str(out),
           "STEWART_STUB_EXIT": "9" if failure == "log_after_failure" else "0"}
    worktree = tmp_path / "absent" if failure == "cd" else tmp_path
    log = tmp_path / "exits"
    if failure.startswith("log_"):
        log.mkdir()  # An unwriteable destination even when tests run as owner/root.
    chosen = profile(command=[str(tmp_path / "absent-command"), "{prompt}"]) if failure == "missing_command" else profile()
    block = render_command(chosen, worktree=worktree, launch_path="LAUNCH.md", exit_log=log, scope=render_scope(worktree))
    result = run_cmd(["/bin/zsh", "-c", "set -e\n" + block], cwd=tmp_path, env=env)
    assert result.returncode != 0
    if failure.startswith("log_"):
        assert "Could not record harness exit" in result.stderr
        assert result.returncode == (9 if failure == "log_after_failure" else 1)
    else:
        assert not (out / "argv").exists(), "setup failure must never invoke a harness from the wrong location"
        assert int(log.read_text().split()[0]) == result.returncode
