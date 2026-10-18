"""The caller contract: what a human or a program can learn from one invocation.

JSON must parse alone on success and on refusal; exit codes and reason codes
must distinguish a failed custody operation from a completed one that recorded
errors; human output must name the result, the limitation and the recovery;
and every documented example must exercise the real parser.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import sys

import pytest

import stewart
from stewart._bootstrap import StewartError
from stewart.cli import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, build_parser
import stewart_support as support
from stewart_support import WS, response_for

INSTALLED_LIB = Path(stewart.__file__).parent.parent
README = INSTALLED_LIB / "stewart/resources/README.md"
pytestmark = pytest.mark.system


def test_command_fixture_preserves_inheritance_and_explicit_environment(run_cmd, monkeypatch):
    monkeypatch.setenv("STEWART_FIXTURE_SENTINEL", "inherited")
    script = "import os; print(os.environ.get('STEWART_FIXTURE_SENTINEL', 'absent'))"
    inherited = run_cmd([sys.executable, "-I", "-B", "-c", script])
    explicit = run_cmd([sys.executable, "-I", "-B", "-c", script], env={})
    assert inherited.stdout.strip() == "inherited"
    assert explicit.stdout.strip() == "absent"


def _run(checkout, run_cmd, *args, json_mode: bool = True):
    argv = [sys.executable, "-m", "stewart", "--repo", str(checkout.repo), "--workspace", WS]
    if json_mode:
        argv.append("--json")
    return run_cmd([*argv, *args], cwd=INSTALLED_LIB, env={"PYTHONPATH": str(INSTALLED_LIB)})


def _break_worktree_git(worktree: Path) -> None:
    """Point the worktree's Git administration nowhere so discovery fails deterministically."""
    (worktree / ".git").write_text("gitdir: /nonexistent/stewart-test\n", encoding="utf-8")


def test_json_parses_alone_on_success_and_on_refusal(checkout, run_cmd):
    checkout.prompt_commit()
    refused = _run(checkout, run_cmd, "prepare", "--mode", "paused")
    assert refused.returncode == EXIT_REFUSED and refused.stderr == ""
    envelope = json.loads(refused.stdout)
    assert envelope["schema"] == "stewart.result/2" and envelope["command"] == "prepare"
    assert envelope["ok"] is False and envelope["exit_code"] == EXIT_REFUSED and envelope["result"] is None
    assert envelope["error"]["reason"] == "pause_unacknowledged" and envelope["error"]["message"]
    assert set(envelope["error"]) == {"reason", "message", "retained", "next_steps"}
    ok = _run(checkout, run_cmd, "prepare")
    assert ok.returncode == EXIT_OK and ok.stderr == ""
    envelope = json.loads(ok.stdout)
    assert envelope["ok"] is True and envelope["exit_code"] == EXIT_OK and envelope["error"] is None
    assert Path(envelope["result"]["session"]).is_dir()


def test_exit_codes_separate_recorded_errors_from_refusals(checkout, run_cmd):
    prepared = support.prepared_session(checkout, report="Report survives a broken checkout\n")
    _break_worktree_git(prepared.worktree)
    collected = _run(checkout, run_cmd, "collect", "--audit-id", checkout.meta["audit_id"], "--auditor-stopped", "finished")
    assert collected.returncode == EXIT_ATTENTION and collected.stderr == ""
    envelope = json.loads(collected.stdout)
    assert envelope["ok"] is False and envelope["exit_code"] == EXIT_ATTENTION, "ok means exit 0"
    receipt = envelope["result"]["receipt"]
    assert receipt["errors"] and receipt["report_status"] == "present" and receipt["git_discovery"] == "failed"
    assert "git_discovery_incomplete" in [gap["id"] for gap in envelope["result"]["gaps"]]
    viewed = _run(checkout, run_cmd, "status", "--audit-id", checkout.meta["audit_id"])
    assert viewed.returncode == EXIT_OK, "inspecting a failed session is itself a success"
    missing = _run(checkout, run_cmd, "collect", "--audit-id", "never-prepared", "--auditor-stopped", "finished")
    assert missing.returncode == EXIT_REFUSED
    assert json.loads(missing.stdout)["error"]["reason"] == "session_missing"
    unacknowledged = _run(checkout, run_cmd, "collect", "--audit-id", checkout.meta["audit_id"])
    assert json.loads(unacknowledged.stdout)["error"]["reason"] == "auditor_not_stopped"


def test_human_output_names_result_limitation_and_recovery(checkout, run_cmd):
    refused = _run(checkout, run_cmd, "prepare", "--mode", "paused", json_mode=False)
    assert refused.stdout == "" and refused.stderr.startswith("Refused (pause_unacknowledged): ")
    prepared = support.prepared_session(checkout, report="Report\n")
    _break_worktree_git(prepared.worktree)
    collected = _run(checkout, run_cmd, "collect", "--audit-id", checkout.meta["audit_id"], "--auditor-stopped", "finished",
                     json_mode=False)
    assert collected.returncode == EXIT_ATTENTION
    assert "Collected: " in collected.stdout and "Report: present" in collected.stdout
    assert "Collection incomplete:" in collected.stdout and "retained" in collected.stdout
    assert "Next: triage --collection" in collected.stdout
    name = re.search(r"Collected: .*/collections/(\S+)", collected.stdout).group(1)
    result = json.loads(_run(checkout, run_cmd, "status", "--audit-id", checkout.meta["audit_id"]).stdout)["result"]
    gaps = next(c for c in result["collections"] if c["name"] == name)["gaps"]
    response = checkout.tmp / "response.json"
    draft = json.loads(_run(checkout, run_cmd, "triage-draft", "--audit-id", checkout.meta["audit_id"],
                            "--collection", name).stdout)["result"]["response"]
    response.write_text(json.dumps({
        **draft,
        "report_sha256": result["collections"][0]["report_sha256"],
        "accepted": [], "rejected": [], "unresolved": [],
        "custody_gaps": {gap: "acknowledged; collection recovered by hand" for gap in gaps},
        "decision": "Retain the report; recover the checkout separately.",
    }))
    triaged = _run(checkout, run_cmd, "triage", "--audit-id", checkout.meta["audit_id"], "--collection", name,
                   "--response", str(response), "--actor", "tester", json_mode=False)
    assert triaged.returncode == EXIT_OK and "Triage recorded: " in triaged.stdout
    triage_name = re.search(r"Next: retain --triage (\S+)", triaged.stdout).group(1)
    retained = _run(checkout, run_cmd, "retain", "--audit-id", checkout.meta["audit_id"], "--triage", triage_name,
                    "--report", json_mode=False)
    assert retained.returncode == EXIT_OK
    assert "Retained:" in retained.stdout and "Nothing was staged or committed" in retained.stdout
    again = _run(checkout, run_cmd, "retain", "--audit-id", checkout.meta["audit_id"], "--triage", triage_name,
                 "--report", json_mode=False)
    assert again.returncode == EXIT_REFUSED and "Refused (destination_exists)" in again.stderr
    status_text = _run(checkout, run_cmd, "status", "--audit-id", checkout.meta["audit_id"], json_mode=False).stdout
    assert "attributed to the auditor, not observed" in status_text
    assert "problem [" not in status_text or "git" in status_text


def test_documented_examples_exercise_the_real_parser():
    """Every command line in the README parses with the shipped parser."""
    text = README.read_text(encoding="utf-8")
    blocks = re.findall(r"```sh\n(.*?)```", text, re.S)
    examples = [line.strip() for block in blocks for line in block.splitlines()
                if '"$STEWART_PYTHON" -I -m stewart --repo' in line and "--help" not in line]
    assert len(examples) >= 8, "the manual must exercise the lifecycle through isolated installed startup"
    parser = build_parser()
    for line in examples:
        tokens = shlex.split(line)
        assert tokens[0] == '$STEWART_PYTHON', line
        assert tokens[1:4] == ['-I', '-m', 'stewart'], line
        namespace = parser.parse_args(tokens[4:])
        assert namespace.command and namespace.repo and namespace.workspace, line


def test_documented_isolated_commands_set_no_ignored_import_path():
    """Isolated startup ignores PYTHONPATH, so a documented prefix would only mislead.

    Both the shipped manual and the source project's README are read. A command
    line counts when it passes -I; prose naming the variable is not a command.
    """
    documents = {"manual": README.read_text(encoding="utf-8"),
                 "project README": (Path(os.environ["STEWART_TEST_PROJECT"]) / "README.md").read_text(encoding="utf-8")}
    isolated = {name: [line for block in re.findall(r"```sh\n(.*?)```", text, re.S)
                       for line in block.splitlines() if " -I " in line]
                for name, text in documents.items()}
    assert all(len(lines) >= 8 for lines in isolated.values()), "documented isolated command population vanished"

    def prefixed(lines):
        return [line for line in lines if any(token.startswith("PYTHONPATH=") for token in shlex.split(line))]

    assert {name: prefixed(lines) for name, lines in isolated.items()} == {name: [] for name in documents}
    # The selector fires on the removed form and ignores other environment assignments.
    assert prefixed(['PYTHONPATH="$PWD" "$STEWART_PYTHON" -I -m stewart --help'])
    assert not prefixed(['STEWART_PROBE_REAL_HARNESS=/p "$STEWART_PYTHON" -I -B check.py'])


def test_status_human_locators_and_pasted_draft_command_work_with_quoted_paths(tmp_path, run_cmd):
    from stewart.collect import collect

    checkout = support.make_checkout(tmp_path, run_cmd, name="main with 'quotes'")
    prepared = support.prepared_session(checkout, report='Captured, not live\n')
    before = support.snapshot_tree(prepared.session)
    handoff = _run(checkout, run_cmd, 'status', '--audit-id', checkout.meta['audit_id'], json_mode=False)
    assert handoff.returncode == EXIT_OK and handoff.stderr == ''
    assert f'Worktree path: {prepared.worktree}' in handoff.stdout
    assert f'Launch handoff path: {prepared.prepared["launch"]}' in handoff.stdout
    assert f'Live report destination (not captured or read by status): {prepared.report}' in handoff.stdout
    assert 'handoff: manual, if not already handed off' in handoff.stdout
    assert f'first prompt: Read {prepared.prepared["launch"]} and carry out' in handoff.stdout
    assert 'Stewart: this view by package' in handoff.stdout and '(same build)' in handoff.stdout
    assert 'stop the auditor first' in handoff.stdout
    assert support.snapshot_tree(prepared.session) == before

    captured = collect(checkout.ws, checkout.meta['audit_id'], auditor_stopped='finished')
    prepared.report.write_text('Changed after capture\n')
    before = support.snapshot_tree(prepared.session)
    review = _run(checkout, run_cmd, 'status', '--audit-id', checkout.meta['audit_id'], json_mode=False)
    assert f'Captured report location: {Path(captured["path"]) / "REPORT.md"}' in review.stdout
    assert 'handoff: manual' not in review.stdout
    command = next(line.removeprefix('  triage-draft: ') for line in review.stdout.splitlines()
                   if line.startswith('  triage-draft: '))
    # Execute the rendered command from another directory: shell quoting,
    # the selected runtime and named collection must be usable together.
    # That directory carries a decoy copy of the tool that refuses to import.
    # The separate module-mode control below proves that decoy is executable.
    decoy = tmp_path / 'stewart'
    decoy.mkdir(parents=True)
    (decoy / '__init__.py').write_text('raise ImportError("decoy tool package in the caller\'s directory was imported")\n')
    result = run_cmd(['/bin/sh', '-c', command], cwd=tmp_path,
                     env={'PYTHONDONTWRITEBYTECODE': '1'}, timeout=30)
    assert result.returncode == EXIT_OK, result.stderr
    draft = json.loads(result.stdout)
    assert draft['collection'] == captured['collection']
    assert draft['report_sha256'] == captured['receipt']['report_sha256']
    assert draft['decision'] is None and draft['accepted'] == [], 'drafting must not accept audit claims'
    assert support.snapshot_tree(prepared.session) == before, 'status and drafting must leave captures untouched'
    # Removing an isolation flag is itself refused before package imports.
    unsafe = command.replace(' -I ', ' ', 1)
    assert unsafe != command, 'the rendered argv must carry isolated startup'
    result = run_cmd(['/bin/sh', '-c', unsafe], cwd=tmp_path, env={'PYTHONDONTWRITEBYTECODE': '1'}, timeout=30)
    assert result.returncode == EXIT_REFUSED and 'startup_isolation' in result.stderr
    hazard = run_cmd([sys.executable, '-B', '-m', 'stewart'], cwd=tmp_path,
                     env={'PYTHONPATH': str(INSTALLED_LIB)}, timeout=30)
    assert hazard.returncode != EXIT_OK and 'decoy tool package' in hazard.stderr


def test_help_marks_mutations_and_read_only_commands():
    parser = build_parser()
    help_text = parser.format_help()
    assert "[read-only]" in help_text and "[writes into the maintainer checkout]" in help_text
    flat = " ".join(help_text.split())
    assert "Exit codes: 0 nothing needs attention; 1 completed, action needed" in flat
    assert "2 refused or invalid usage, nothing done; 3 records or bytes do not verify" in flat
    with pytest.raises(StewartError) as finished:
        parser.parse_args(["--workspace", WS, "retain"])
    assert finished.value.reason == "usage"


def test_review_input_fifo_is_a_json_refusal_without_blocking(checkout, tmp_path, run_cmd):
    import os

    pipe = tmp_path / "review.json"
    os.mkfifo(pipe)
    result = run_cmd(
        [sys.executable, "-B", "-m", "stewart", "--repo", str(checkout.repo), "--workspace", WS, "--json",
         "release", "--audit-id", "one-question", "--review", str(pipe), "--actor", "manager"],
        cwd=INSTALLED_LIB, env={"PYTHONPATH": str(INSTALLED_LIB)}, timeout=10,
    )
    assert result.returncode == EXIT_REFUSED, result.stderr
    error = json.loads(result.stdout)["error"]
    assert error["reason"] == "input_file" and error["next_steps"]
    assert "regular file" in error["message"]


@pytest.mark.parametrize("document", [
    '{"decision":"keep","decision":"discard"}',
    '{"decision":"discard","decision":"keep"}',
    '{"decision":"keep","decision":"keep"}',
    '{"cases":[{"measurements":["a"],"measurements":["b"]}]}',
    r'{"cases":[{"id":"a","\u0069d":"b"}]}',
])
def test_manager_input_refuses_repeated_names_before_values_can_be_selected(tmp_path, document):
    from stewart.cli import _read_json_file
    from stewart._bootstrap import StewartError

    source = tmp_path / "manager.json"
    original = document.encode()
    source.write_bytes(original)
    with pytest.raises(StewartError) as refused:
        _read_json_file(source, "review")
    assert refused.value.reason == "duplicate_input_key", (
        "conflicting, identical, nested and escape-equivalent object names are all ambiguous authoring")
    assert refused.value.retained == [str(source)] and refused.value.next_steps
    assert source.read_bytes() == original, "refusal must preserve the authored evidence"


@pytest.mark.parametrize("document", [
    '{"cases":[{"id":"a"},{"id":"b"}],"note":"id id"}',
    '{ "note": "id id", "cases": [ { "id": "a" }, { "id": "b" } ] }',
    r'{"cases":[{"\u0069d":"a"},{"id":"b"}],"note":"id id"}',
])
def test_manager_input_ignores_formatting_and_names_in_separate_objects(tmp_path, document):
    from stewart.cli import _read_json_file

    source = tmp_path / "manager.json"
    source.write_text(document)
    assert _read_json_file(source, "review") == {
        "cases": [{"id": "a"}, {"id": "b"}], "note": "id id",
    }, "name uniqueness belongs to each decoded object, not the whole document or its text"


@pytest.mark.parametrize("operation", ["release", "triage", "init"])
def test_cli_manager_input_refusal_precedes_mutation_and_unique_equivalent_succeeds(tmp_path, run_cmd, operation):
    """Exercise each authorizing front door with an ambiguous and unique pair."""
    checkout = (support.make_checkout(tmp_path, run_cmd) if operation == "triage"
                else support.experiment_checkout(tmp_path, run_cmd))
    source = tmp_path / "manager-input.json"
    if operation == "release":
        support.prepared_experiment(checkout)
        document = support.REVIEW
        field, value, earlier = "measurements", ["value"], ["different-required-measurement"]
        argv = ["release", "--audit-id", "one-question", "--review", str(source), "--actor", "tester"]
    elif operation == "triage":
        from stewart.collect import collect

        support.prepared_session(checkout, report="Preserved partial report.\n")
        captured = collect(checkout.ws, "one-question", auditor_stopped="finished")
        document = response_for(captured)
        field, value, earlier = "decision", document["decision"], "A competing disposition."
        argv = ["triage", "--audit-id", "one-question", "--collection", captured["collection"],
                "--response", str(source), "--actor", "tester"]
    else:
        document = checkout.grant
        field, value, earlier = "invocations", 1, 0
        argv = ["init", "--audit-id", "one-question", "--input", "input.txt",
                "--input", support.MANIFEST, "--experiment-grant", str(source), "--replace-prompt"]
        for area in support.SCRATCH:
            argv.extend(["--scratch", area])

    unique = json.dumps(document)
    occurrence = json.dumps(field) + ": " + json.dumps(value)
    assert occurrence in unique, "the pair must actually vary the intended input field"
    ambiguous = unique.replace(occurrence, json.dumps(field) + ": " + json.dumps(earlier) + ", " + occurrence, 1)
    source.write_text(ambiguous)
    before = support.snapshot_tree(checkout.repo)
    refused = _run(checkout, run_cmd, *argv)
    assert refused.returncode == EXIT_REFUSED, refused.stdout
    error = json.loads(refused.stdout)["error"]
    assert error["reason"] == "duplicate_input_key" and str(source) in error["retained"]
    assert source.read_text() == ambiguous
    assert support.snapshot_tree(checkout.repo) == before, (
        f"{operation} must not write a release, disposition or assignment before rejecting ambiguous input")

    # The last-value equivalent is admissible; the refusal must be aimed at
    # repeated names rather than the command, field value, or nested object.
    source.write_text(unique)
    accepted = _run(checkout, run_cmd, *argv)
    assert accepted.returncode == EXIT_OK, accepted.stdout + accepted.stderr
    result = json.loads(accepted.stdout)["result"]
    if operation == "release":
        assert result["record"]["review"]["cases"][0]["measurements"] == ["value"]
    elif operation == "triage":
        assert result["record"]["decision"] == document["decision"]
    else:
        assert result["assignment"]["experiment"] == document, "the unique grant must reach the draft intact"
        assert (checkout.repo / checkout.ws.prompt).read_text() == result["draft"], (
            "init publishes an unassigned draft; it does not complete the manager's assignment prose")
        assert support.snapshot_tree(checkout.repo) != before, "the unique grant must reach assignment publication"


def test_export_and_import_cli_explain_selection_and_pin_the_package(checkout, run_cmd):
    from stewart.collect import collect

    support.prepared_session(checkout, report='Captured CLI report\n')
    collected = collect(checkout.ws, checkout.meta['audit_id'], auditor_stopped="finished")
    result = _run(checkout, run_cmd, 'export', '--audit-id', checkout.meta['audit_id'],
                  '--collection', collected['collection'], '--select', 'REPORT.md',
                  '--output', '.scratch/cli-package', '--actor', 'manager', json_mode=False)
    assert result.returncode == EXIT_OK and result.stderr == ''
    assert 'Evidence package: .scratch/cli-package/manifest.json' in result.stdout
    assert 'REPORT.md -> files/0000.md' in result.stdout and 'custody' in result.stdout
    initialized = _run(checkout, run_cmd, 'init', '--audit-id', 'receiving',
                       '--evidence-package', '.scratch/cli-package/manifest.json')
    assert initialized.returncode == EXIT_OK
    items = json.loads(initialized.stdout)['result']['assignment']['supplemental_inputs']
    assert len(items) == 3 and all(item['custody']['manifest_sha256'] for item in items)
    refused = _run(checkout, run_cmd, 'export', '--audit-id', checkout.meta['audit_id'],
                   '--collection', collected['collection'], '--select', 'live/path.py',
                   '--output', '.scratch/bad-selection', '--actor', 'manager')
    error = json.loads(refused.stdout)['error']
    assert refused.returncode == EXIT_REFUSED and refused.stderr == ''
    assert error['reason'] == 'capture_selector' and error['retained'] and error['next_steps']
