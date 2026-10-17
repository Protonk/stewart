"""Every command status prints is executable as printed, from anywhere, once its stated prerequisites hold.

Status is the manager's instrument panel: each step of a managed audit starts
by reading its next actions and pasting one. Nothing else proves that what it
prints is what the parser accepts, that the quoting survives a shell, or that
its isolated startup keeps a foreign directory from shadowing the tool.
This walk drives one experiment session through its whole lifecycle using
nothing but the commands status renders, run through ``/bin/sh`` from a
directory that carries a decoy copy of the tool. Placeholders are filled from
fixture evidence; every other byte is what a manager would paste.

A failure names the stage, the action, the exact command, the exit code and
the stderr, which is the report an agent needs when a pasted command does not
behave: it separates a rendering or parser drift in the tool from a mistake in
the manager's own substitution.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
import sys

import pytest

import stewart
from stewart.cli import EXIT_OK
import stewart_support as support
from stewart_support import WS

INSTALLED_LIB = Path(stewart.__file__).parent.parent
pytestmark = pytest.mark.system

#: A rendered placeholder is a single shell-quoted token whose text is wrapped
#: in angle brackets, as status prints it. Anything else in a command is literal.
PLACEHOLDER = re.compile(r"'<([^'>]+)>'")
ACTION_LINE = re.compile(r"^  ([a-z-]+): (.+)$")
#: Actions status prints as prose rather than as a command.
MANUAL_ACTIONS = {"handoff"}


def _status_commands(checkout, run_cmd) -> dict[str, str]:
    """The ``action: command`` lines of prose status, in the order printed."""
    result = run_cmd([sys.executable, "-m", "stewart", "--repo", str(checkout.repo), "--workspace", WS,
                      "status", "--audit-id", checkout.meta["audit_id"]], cwd=INSTALLED_LIB, env={"PYTHONPATH": str(INSTALLED_LIB)})
    assert result.returncode == EXIT_OK, result.stderr
    commands: dict[str, str] = {}
    in_actions = False
    for line in result.stdout.splitlines():
        if line == "Next actions:":
            in_actions = True
            continue
        match = ACTION_LINE.match(line) if in_actions else None
        if match and match.group(1) not in MANUAL_ACTIONS:
            commands[match.group(1)] = match.group(2)
    return commands


def _paste(run_cmd, command: str, cwd: Path, fills: dict[str, str], *, stage: str, action: str) -> str:
    """Run one rendered command with its placeholders filled; return stdout or fail with the diagnosis."""
    unknown = [name for name in PLACEHOLDER.findall(command) if name not in fills]
    if unknown:
        pytest.fail(f"stage {stage}, action {action}: status rendered placeholders this walk cannot fill: {unknown}\n"
                    f"command: {command}\neither add a fill here or render a concrete value")
    filled = PLACEHOLDER.sub(lambda m: shlex.quote(fills[m.group(1)]), command)
    result = run_cmd(["/bin/sh", "-c", filled], cwd=cwd, env={"PYTHONDONTWRITEBYTECODE": "1"}, timeout=120)
    used = {name: fills[name] for name in PLACEHOLDER.findall(command)}
    if result.returncode != EXIT_OK or "Traceback" in result.stderr or result.stderr.startswith("usage:"):
        pytest.fail(
            f"stage {stage}, action {action}: a command status printed did not run as printed\n"
            f"exit: {result.returncode}\nrendered: {command}\nfilled: {filled}\nsubstitutions: {used}\n"
            f"stdout: {result.stdout[-1500:]}\nstderr: {result.stderr[-1500:]}\n"
            "a 'usage:' stderr means the renderer and the parser disagree; a 'Refused (' line names the tool's own reason; "
            "a traceback is a defect in the tool"
        )
    return result.stdout


def test_every_rendered_next_action_runs_as_printed_through_the_lifecycle(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    (exp.worktree / checkout.meta["report_path"]).write_text("Status: complete\nConstructed.\n")
    # The foreign directory a manager might paste from, holding a decoy tool
    # package: the isolated startup keeps it from being imported.
    paste = tmp_path / "paste"
    (paste / "stewart").mkdir(parents=True)
    (paste / "stewart" / "__init__.py").write_text('raise ImportError("decoy tool package imported")\n')
    review = tmp_path / "review.json"
    review.write_text(json.dumps(support.REVIEW))
    response = tmp_path / "response.json"
    fills = {
        "terminal|subagent|other": "terminal", "model": "opus", "effort": "max", "name": "walker",
        "finished|interrupted|blocked": "finished", "review.json": str(review), "response.json": str(response),
        "reason": "walk complete",
    }
    walked: list[tuple[str, str]] = []

    def stage(name: str, expected: set[str]) -> None:
        commands = _status_commands(checkout, run_cmd)
        assert set(commands) == expected, (
            f"stage {name}: status offered {sorted(commands)}, the walk expected {sorted(expected)}; "
            "a changed offer needs a changed walk, and an offer the walk cannot satisfy is unpasteable")
        for action, command in commands.items():
            if action == "triage-draft":
                draft = json.loads(_paste(run_cmd, command, paste, fills, stage=name, action=action))
                draft.update(decision="walk: retain the report",
                             custody_gaps={gap: "walk: reviewed" for gap in draft["custody_gaps"]})
                response.write_text(json.dumps(draft))
            else:
                _paste(run_cmd, command, paste, fills, stage=name, action=action)
            walked.append((name, action))

    stage("prepared", {"launch", "collect"})
    stage("collected", {"triage-draft", "triage", "release"})
    stage("released", {"retain", "run"})
    assert _status_commands(checkout, run_cmd) == {}, "after the single run nothing remains to paste"
    final = json.loads(run_cmd([sys.executable, "-m", "stewart", "--repo", str(checkout.repo), "--workspace", WS,
                                "--json", "status", "--audit-id", checkout.meta["audit_id"]],
                               cwd=INSTALLED_LIB, env={"PYTHONPATH": str(INSTALLED_LIB)}).stdout)["result"]
    assert final["experiment"]["state"] == "attempt_recorded" and final["retentions"] and final["launches"]
    assert final["attempts"][0]["errors"] == [] and final["attempts"][0]["ledger"]["unmet"] == []
    assert [a for _, a in walked] == ["launch", "collect", "triage-draft", "triage", "release", "retain", "run"]
    assert (checkout.repo / checkout.meta["report_path"]).read_text() == "Status: complete\nConstructed.\n"
    # Sensitivity: the same walk is only meaningful if the decoy would have been
    # imported by an ordinary module invocation.
    unsafe = _status_commands(checkout, run_cmd)  # empty now; render one command by hand from the last stage
    assert unsafe == {}
    bare = (f"PYTHONPATH={shlex.quote(str(checkout.repo))} {shlex.quote(sys.executable)} -m stewart "
            f"--repo {shlex.quote(str(checkout.repo))} --workspace {WS} status --audit-id {checkout.meta['audit_id']}")
    result = run_cmd(["/bin/sh", "-c", bare], cwd=paste, env={"PYTHONDONTWRITEBYTECODE": "1"}, timeout=60)
    assert result.returncode != EXIT_OK and "decoy tool package" in result.stderr, (
        "an ordinary module invocation loads the decoy; the isolated commands must select their retained runtime")
