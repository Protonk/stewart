"""The shared exit-code contract and the auditor check's parity with collection.

Exit 0 means nothing needs attention; 1 asks for action within the caller's
role; 2 refuses; 3 says something the caller cannot repair does not verify.
Codes never depend on what the audit says. The auditor's check must predict
what a collection of the same unchanged checkout records about the checkout,
so an accepted report never surfaces as a manager-side gap the auditor could
have fixed.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import stat
import sys

import pytest

from stewart import _util as _hash
import stewart
from stewart import _bootstrap
from stewart._bootstrap import (
    EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, EXIT_UNVERIFIED, REFUSED_REASONS, STATE_REASONS, UNVERIFIED_REASONS,
    StewartError, combined_code,
)
from stewart.collect import COLLECTION_ERRORS, collect, custody_gaps
from stewart.report_declaration import check_checkout, report_declaration
from stewart.workspace import workspace
import stewart_support as support
from stewart_support import WS

INSTALLED = Path(stewart.__file__).parent
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*")
pytestmark = pytest.mark.system


def literal_reasons(source: str) -> set[str]:
    """Reason identifiers written as literals: keyword, refusal helper, default and dict forms."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "reason" and isinstance(keyword.value, ast.Constant):
                    found.add(keyword.value.value)
            name = getattr(node.func, "id", getattr(node.func, "attr", None))
            if name == "_refuse" and node.args and isinstance(node.args[0], ast.Constant):
                found.add(node.args[0].value)
            if (name == "getattr" and len(node.args) == 3 and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value == "reason" and isinstance(node.args[2], ast.Constant)):
                found.add(node.args[2].value)
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "reason" and isinstance(value, ast.Constant):
                    found.add(value.value)
    return {reason for reason in found if isinstance(reason, str) and IDENTIFIER.fullmatch(reason)}


@pytest.mark.smoke
def test_every_literal_reason_has_exactly_one_exit_code():
    sources = {path.name: path.read_text(encoding="utf-8") for path in sorted(INSTALLED.glob("*.py"))}
    found = {reason: name for name, source in sources.items() for reason in literal_reasons(source)}
    # Collection error reasons carry their own code and observability.
    classified = REFUSED_REASONS | UNVERIFIED_REASONS | set(COLLECTION_ERRORS)
    assert not REFUSED_REASONS & UNVERIFIED_REASONS, "a reason cannot both refuse and fail verification"
    unused = (REFUSED_REASONS | UNVERIFIED_REASONS) - set(found) - {"refused"}
    assert not unused, f"classified reasons no source raises: {sorted(unused)}"
    assert STATE_REASONS <= classified
    missing = {reason: name for reason, name in found.items() if reason not in classified}
    assert not missing, f"unclassified reasons (add each to REFUSED_REASONS or UNVERIFIED_REASONS): {missing}"
    # Firing control: the scan really sees each literal form, including the
    # plain-dict problem entries that status builds without a raise.
    probe = ('raise StewartError("x", reason="kw_form")\n_refuse("helper_form", "f", 1, 2)\n'
             'getattr(exc, "reason", "default_form")\nproblems.append({"reason": "dict_form"})\n'
             'boundaries.append({"reason": "free text is not an identifier"})\n')
    assert literal_reasons(probe) == {"kw_form", "helper_form", "default_form", "dict_form"}
    assert {"exit_log_malformed", "collection_incomplete", "attempt_unresolved"} <= set(found)


@pytest.mark.smoke
def test_codes_combine_with_unverified_first_and_refusals_use_the_table():
    assert combined_code([]) == EXIT_OK
    assert combined_code([EXIT_OK, EXIT_ATTENTION]) == EXIT_ATTENTION
    assert combined_code([EXIT_ATTENTION, EXIT_UNVERIFIED, EXIT_ATTENTION]) == EXIT_UNVERIFIED
    assert StewartError("m", reason="binding_mismatch").exit_code == EXIT_UNVERIFIED
    assert StewartError("m", reason="usage").exit_code == EXIT_REFUSED
    # A raise site that knows the cause can classify it; any other value is ignored.
    assert StewartError("m", reason="usage", code=EXIT_UNVERIFIED).exit_code == EXIT_UNVERIFIED
    assert StewartError("m", reason="binding_mismatch", code=EXIT_ATTENTION).exit_code == EXIT_UNVERIFIED


@pytest.mark.smoke
def test_every_collection_error_and_gap_family_carries_a_code():
    receipt = {
        "errors": [{"reason": reason, "message": reason} for reason in COLLECTION_ERRORS],
        "report_status": "missing", "git_discovery": "failed", "checkout_commit_changed": True,
        "unexpected_paths": ["a.txt", "ignored/supplied.txt"], "unexpected_supplemental": ["ignored/supplied.txt"],
        "missing_supplemental": ["ignored/deleted.txt"],
        "declaration": {"status": "mismatch", "declaration": {"completion": "complete"}, "diagnostics": [
            {"field": "launch_token", "message": "m"}, {"field": "observed_checkout_commit", "message": "m"}]},
        "auditor_stop_kind": "interrupted",
        "inventory": {"movement": True, "omitted": [{"path": "o", "kind": "fifo"}], "unreadable": ["u"],
                      "unsupported": [{"path": "s", "kind": "socket"}], "boundaries": [{"path": "b", "reason": "r"}]},
    }
    gaps = custody_gaps(receipt)
    assert all(gap["code"] in (EXIT_ATTENTION, EXIT_UNVERIFIED) and isinstance(gap["observable"], bool) for gap in gaps)
    families = {gap["id"].split(":", 1)[0] for gap in gaps}
    assert families == {"collection_error", "report_missing", "git_discovery_incomplete", "checkout_commit_changed",
                        "unexpected_path", "supplemental_missing", "declaration_mismatch", "declaration_stale",
                        "completion_stop_discrepancy",
                        "movement_detected", "omitted", "unreadable", "unsupported", "boundary"}
    by_id = {gap["id"]: gap for gap in gaps}
    assert by_id["unexpected_path:ignored/supplied.txt"]["code"] == EXIT_UNVERIFIED
    assert by_id["unexpected_path:a.txt"]["code"] == EXIT_ATTENTION
    assert by_id["supplemental_missing:ignored/deleted.txt"]["code"] == EXIT_UNVERIFIED
    # Manager-side facts are never the auditor's to observe.
    for gap_id in ("git_discovery_incomplete", "completion_stop_discrepancy", "movement_detected"):
        assert by_id[gap_id]["observable"] is False
    source = (INSTALLED / "collect.py").read_text(encoding="utf-8")
    appended = {reason for reason in literal_reasons(source)}
    error_reasons = {"report_capture", "handoff_changed", "runtime_changed", "runtime_observation",
                     "retention_invalid", "declaration_validation"}
    assert error_reasons <= appended and error_reasons <= set(COLLECTION_ERRORS)


SUPPLIED = "ignored/supplied.txt"


def _session(checkout):
    """A prepared session with a supplemental input, a notes area and an accepted skeleton report."""
    supplied = checkout.repo / SUPPLIED
    supplied.parent.mkdir(exist_ok=True)
    supplied.write_text("supplied specimen\n")
    checkout.meta["supplemental_inputs"] = [{"path": SUPPLIED, "sha256": _hash.sha256_bytes(supplied.read_bytes()),
                                             "provenance": "fixture specimen"}]
    checkout.meta["scratch_paths"] = [f"{checkout.ws.scratch}/one-question/notes"]
    prepared = support.prepared_session(checkout, report=None)
    args = _arguments(prepared)
    report_declaration(workspace(prepared.worktree, WS), "start", **args)
    return prepared


def _arguments(prepared):
    return dict(expected_worktree=prepared.worktree, launch_prompt_commit=prepared.revision,
                prompt_sha256=prepared.prepared["prompt_sha256"], launch_token=prepared.prepared["launch_token"])


def _check(prepared):
    return check_checkout(workspace(prepared.worktree, WS), **_arguments(prepared))


def _mutate(prepared, checkout, change):
    worktree = prepared.worktree
    if change == "clean":
        return
    if change == "inside_outputs":
        (worktree / checkout.ws.scratch / "one-question/notes/checksums.txt").write_text("notes\n")
    elif change == "outside_outputs":
        (worktree / "stray.txt").write_text("stray\n")
    elif change == "tracked_input":
        (worktree / "input.txt").write_text("edited input\n")
    elif change == "supplemental_input":
        (worktree / SUPPLIED).write_text("edited supplement\n")
    elif change == "prompt_edit":
        (worktree / checkout.ws.prompt).write_text("edited prompt\n")
    elif change == "commit":
        (worktree / "committed.txt").write_text("committed\n")
        checkout.git("add", "committed.txt", cwd=worktree)
        checkout.git("commit", "-qm", "auditor commit", cwd=worktree)
    elif change == "fifo":
        os.mkfifo(worktree / "audits" / "pipe")
    elif change == "unreadable":
        target = worktree / "secret.txt"
        target.write_text("unreadable\n")
        target.chmod(0)
    elif change == "nested_git":
        (worktree / "vendor/.git").mkdir(parents=True)
        (worktree / "vendor/.git/HEAD").write_text("ref: refs/heads/main\n")
    elif change == "report_deleted":
        prepared.report.unlink()
    elif change == "supplemental_deleted":
        (worktree / SUPPLIED).unlink()
    elif change == "handoff_neighbor":
        (worktree / WS / ".stewart-handoffs" / "notes.md").write_text("an editor's note beside the handoff\n")
    elif change == "wrong_token":
        data = prepared.report.read_bytes()
        token = prepared.prepared["launch_token"].encode()
        prepared.report.write_bytes(data.replace(token, b"0" * 16))
    else:
        raise AssertionError(change)


EXPECTED = {
    "clean": set(),
    "inside_outputs": set(),
    "outside_outputs": {("unexpected_path:stray.txt", 1)},
    "tracked_input": {("unexpected_path:input.txt", 1)},
    "supplemental_input": {(f"unexpected_path:{SUPPLIED}", 3)},
    "prompt_edit": {(f"unexpected_path:{WS}/PROMPT.md", 1)},
    "commit": {("checkout_commit_changed", 1), ("declaration_stale", 1), ("unexpected_path:committed.txt", 1)},
    "fifo": {("unsupported:audits/pipe", 1)},
    "report_deleted": {("report_missing", 1), ("declaration_missing", 1)},
    "wrong_token": {("declaration_mismatch:launch_token", 1)},
    # A deleted supplied copy leaves no Git diff; only the pin names it.
    "supplemental_deleted": {(f"supplemental_missing:{SUPPLIED}", 3)},
    # Another file beside the handoff is ordinary; the handoff itself is never listed.
    "handoff_neighbor": {(f"unexpected_path:{WS}/.stewart-handoffs/notes.md", 1)},
}


@pytest.mark.heavy
@pytest.mark.parametrize("change", ["clean", "inside_outputs", "outside_outputs", "tracked_input",
                                    "supplemental_input", "prompt_edit", "commit", "fifo", "unreadable",
                                    "nested_git", "report_deleted", "wrong_token", "supplemental_deleted",
                                    "handoff_neighbor"])
def test_check_predicts_every_checkout_attributable_collection_gap(checkout, change):
    prepared = _session(checkout)
    _mutate(prepared, checkout, change)
    checked = _check(prepared)
    try:
        collected = collect(checkout.ws, "one-question", auditor_stopped="finished")
    finally:
        if change == "unreadable":
            (prepared.worktree / "secret.txt").chmod(stat.S_IRUSR | stat.S_IWUSR)
    seen = {(gap["id"], gap["code"]) for gap in checked["gaps"]}
    recorded = {(gap["id"], gap["code"]) for gap in collected["gaps"] if gap["observable"]}
    assert seen == recorded, f"check and collection disagree for {change}"
    assert checked["exit_code"] == combined_code(code for _, code in recorded)
    if change in EXPECTED:
        assert seen == EXPECTED[change]
    else:
        assert seen and all(code == EXIT_ATTENTION for _, code in seen), f"{change} must fire a fixable gap"
    # Exit 0 is no news: nothing listed on either side, nothing manager-side either.
    if checked["exit_code"] == EXIT_OK:
        assert checked["gaps"] == [] and collected["gaps"] == [] and collected["exit_code"] == EXIT_OK
    for gap in checked["gaps"]:
        assert gap["fix"], "every listed gap names what to do"


@pytest.mark.heavy
@pytest.mark.parametrize("completion,kind", [("partial", None), ("blocked", None), ("partial", "needs-evidence"),
                                             ("complete", "answer"), ("complete", "needs-evidence"),
                                             ("complete", "reframe")])
def test_codes_ignore_declared_completion_and_report_kind(checkout, completion, kind):
    prepared = _session(checkout)
    report_declaration(workspace(prepared.worktree, WS), "set", completion=completion, report_kind=kind,
                       **_arguments(prepared))
    checked = _check(prepared)
    assert checked["exit_code"] == EXIT_OK and checked["gaps"] == []
    assert checked["declaration"]["declaration"]["completion"] == completion
    collected = collect(checkout.ws, "one-question", auditor_stopped="finished")
    assert collected["exit_code"] == EXIT_OK and collected["gaps"] == []
    from stewart.status import status
    view = status(checkout.ws, "one-question")
    assert view["exit_code"] == EXIT_OK and view["auditor_reported"]["completion"]["value"] == completion


@pytest.mark.heavy
def test_handoff_identities_bind_the_check_and_the_writers(checkout, monkeypatch, capsys):
    from stewart import report_declaration as declaration

    prepared = _session(checkout)
    wrong = {**_arguments(prepared), "launch_token": "1" * 16}
    checked = check_checkout(workspace(prepared.worktree, WS), **wrong)
    assert {gap["id"] for gap in checked["gaps"]} == {"command_mismatch:launch_token"}
    assert checked["exit_code"] == EXIT_ATTENTION
    with pytest.raises(StewartError) as refused:
        report_declaration(workspace(prepared.worktree, WS), "set", completion="partial", **wrong)
    assert refused.value.reason == "handoff_identity" and refused.value.exit_code == EXIT_REFUSED
    # Control: the issued values are accepted and the CLI exit equals the result's code.
    monkeypatch.chdir(prepared.worktree)
    argv = ["check", "--workspace", WS, "--json"]
    for name, value in _arguments(prepared).items():
        argv += ["--" + name.replace("_", "-"), str(value)]
    assert declaration.main(argv) == EXIT_OK
    document = json.loads(capsys.readouterr().out)
    assert document["ok"] is True and document["exit_code"] == EXIT_OK and document["result"]["gaps"] == []
    handoff = next((prepared.worktree / WS / ".stewart-handoffs").iterdir())
    handoff.unlink()
    assert declaration.main(argv) == EXIT_UNVERIFIED
    document = json.loads(capsys.readouterr().out)
    assert document["ok"] is False and "handoff_unavailable" in {gap["id"] for gap in document["result"]["gaps"]}


@pytest.mark.heavy
def test_input_verifier_names_a_restore_for_committed_inputs_only(checkout, monkeypatch, capsys):
    from stewart import verify_inputs

    prepared = _session(checkout)
    monkeypatch.chdir(prepared.worktree)
    argv = ["--workspace", WS, "--json"]
    for name, value in _arguments(prepared).items():
        argv += ["--" + name.replace("_", "-"), str(value)]
    assert verify_inputs.main(argv) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["ok"] is True
    (prepared.worktree / "input.txt").write_text("edited input\n")
    assert verify_inputs.main(argv) == EXIT_ATTENTION
    rows = {row["path"]: row for row in json.loads(capsys.readouterr().out)["result"]["inputs"]}
    # The fix writes only the working tree: the qualified harness denies Git administration writes.
    assert rows["input.txt"]["code"] == EXIT_ATTENTION and f"git show {prepared.revision}:input.txt" in rows["input.txt"]["fix"]
    checkout.git("checkout", prepared.revision, "--", "input.txt", cwd=prepared.worktree)
    (prepared.worktree / SUPPLIED).write_text("edited supplement\n")
    assert verify_inputs.main(argv) == EXIT_UNVERIFIED
    document = json.loads(capsys.readouterr().out)
    rows = {row["path"]: row for row in document["result"]["inputs"]}
    assert document["ok"] is False and rows[SUPPLIED]["code"] == EXIT_UNVERIFIED
    assert "git checkout" not in rows[SUPPLIED]["fix"] and rows["input.txt"]["matches"]


def _cli(checkout, run_cmd, *args):
    """One installed-CLI invocation in JSON mode, from outside the checkout."""
    # The test interpreter is the venv the wheel is installed in; isolated
    # startup selects that installation, never a path variable.
    result = run_cmd([sys.executable, "-I", "-m", "stewart", "--repo", str(checkout.repo), "--workspace", WS, "--json",
                      *args], cwd=INSTALLED.parent, env={})
    return result.returncode, json.loads(result.stdout)


@pytest.mark.heavy
def test_cli_ok_means_exit_zero_and_results_survive_attention(checkout, run_cmd):
    prepared = _session(checkout)
    code, envelope = _cli(checkout, run_cmd, "collect", "--audit-id", "one-question", "--auditor-stopped", "finished")
    assert code == EXIT_OK and envelope["ok"] is True and envelope["result"]["gaps"] == []
    (prepared.worktree / "stray.txt").write_text("stray\n")
    code, envelope = _cli(checkout, run_cmd, "collect", "--audit-id", "one-question", "--auditor-stopped", "finished")
    assert code == EXIT_ATTENTION and envelope["exit_code"] == EXIT_ATTENTION and envelope["ok"] is False
    assert [gap["id"] for gap in envelope["result"]["gaps"]] == ["unexpected_path:stray.txt"]
    (prepared.worktree / SUPPLIED).write_text("edited supplement\n")
    code, envelope = _cli(checkout, run_cmd, "collect", "--audit-id", "one-question", "--auditor-stopped", "finished")
    assert code == EXIT_UNVERIFIED and envelope["ok"] is False, "3 takes precedence over 1"
    code, envelope = _cli(checkout, run_cmd, "collect", "--audit-id", "one-question")
    assert code == EXIT_REFUSED and envelope["ok"] is False and envelope["error"]["reason"] == "auditor_not_stopped"
    # Status follows the same envelope rule: news keeps its result and is not ok.
    code, envelope = _cli(checkout, run_cmd, "status", "--audit-id", "one-question")
    assert code == envelope["exit_code"] == envelope["result"]["exit_code"] == EXIT_UNVERIFIED
    assert envelope["ok"] is False and envelope["result"]["attention"]
    # A refusal caused by evidence that does not verify is 3, not 2.
    collection = Path(envelope_path(checkout, run_cmd))
    receipt = collection / "collection.json"
    receipt.chmod(stat.S_IRUSR | stat.S_IWUSR)
    receipt.write_text(receipt.read_text().replace('"audit_id": "one-question"', '"audit_id": "another-question"'))
    code, envelope = _cli(checkout, run_cmd, "triage-draft", "--audit-id", "one-question",
                          "--collection", collection.name)
    assert code == EXIT_UNVERIFIED and envelope["error"]["reason"] in UNVERIFIED_REASONS


def envelope_path(checkout, run_cmd):
    """The newest collection directory, located through the public status view."""
    code, envelope = _cli(checkout, run_cmd, "status", "--audit-id", "one-question")
    return envelope["result"]["collections"][-1]["path"]


@pytest.mark.heavy
def test_fixes_write_only_the_working_tree_and_unstage_what_is_staged(checkout):
    prepared = _session(checkout)
    (prepared.worktree / "input.txt").write_text("edited input\n")
    fixes = {gap["id"]: gap["fix"] for gap in _check(prepared)["gaps"]}
    assert fixes == {"unexpected_path:input.txt": f"restore it with `git show {prepared.revision}:input.txt > input.txt`"}
    (prepared.worktree / "input.txt").write_bytes((checkout.repo / "input.txt").read_bytes())
    assert _check(prepared)["exit_code"] == EXIT_OK, "the named fix clears the gap"
    # Measured: a staged path stays reported after removal until it is unstaged.
    (prepared.worktree / "staged.txt").write_text("staged\n")
    checkout.git("add", "staged.txt", cwd=prepared.worktree)
    (prepared.worktree / "staged.txt").unlink()
    fix = {gap["id"]: gap["fix"] for gap in _check(prepared)["gaps"]}["unexpected_path:staged.txt"]
    assert fix.startswith(f"unstage it with `git reset -q {prepared.revision} -- staged.txt`")
    checkout.git("reset", "-q", prepared.revision, "--", "staged.txt", cwd=prepared.worktree)
    assert _check(prepared)["exit_code"] == EXIT_OK


@pytest.mark.heavy
def test_a_changed_input_manifest_never_asks_to_remove_supplied_inputs(checkout):
    from stewart import assignment
    supplied = checkout.repo / "ignored/member.txt"
    supplied.parent.mkdir(exist_ok=True)
    supplied.write_text("member bytes\n")
    manifest = ".scratch/audit-inputs/one-question.json"
    draft = assignment.initialize(checkout.ws, "one-question", checkout.meta["target_commit"], inputs=["input.txt"],
                                  supplemental=[("ignored/member.txt", "fixture origin")],
                                  input_manifest=manifest, replace_prompt=True)
    checkout.meta.clear()
    checkout.meta.update(draft["assignment"])
    prepared = support.prepared_session(checkout, report=None)
    report_declaration(workspace(prepared.worktree, WS), "start", **_arguments(prepared))
    assert _check(prepared)["exit_code"] == EXIT_OK, "control: the unchanged manifest verifies"
    copy = prepared.worktree / manifest
    copy.write_bytes(copy.read_bytes() + b" ")
    checked = _check(prepared)
    collected = collect(checkout.ws, "one-question", auditor_stopped="finished")
    gaps = {gap["id"]: gap for gap in checked["gaps"]}
    assert gaps["input_manifest_changed"]["code"] == EXIT_UNVERIFIED
    for rel in (manifest, "ignored/member.txt"):
        assert gaps[f"unexpected_path:{rel}"]["code"] == EXIT_UNVERIFIED
        assert "remove" not in gaps[f"unexpected_path:{rel}"]["fix"], "never ask to delete what may be supplied"
    assert checked["exit_code"] == collected["exit_code"] == EXIT_UNVERIFIED


@pytest.mark.heavy
def test_status_reports_a_lost_checkout_and_a_changed_handoff(checkout):
    from stewart.status import status
    prepared = _session(checkout)
    assert status(checkout.ws, "one-question")["exit_code"] == EXIT_OK, "control: a ready session is no news"
    handoff = next((prepared.worktree / WS / ".stewart-handoffs").iterdir())
    original = handoff.read_bytes()
    handoff.write_bytes(original + b"edited\n")
    view = status(checkout.ws, "one-question")
    assert {(item["reason"], item["code"]) for item in view["attention"]} == {("handoff_changed", EXIT_UNVERIFIED)}
    handoff.write_bytes(original)
    assert status(checkout.ws, "one-question")["exit_code"] == EXIT_OK, "invariance: restored bytes verify again"
    # Measured: a checkout removed before any complete collection took its evidence along.
    import shutil
    worktree = prepared.worktree
    shutil.rmtree(worktree)
    view = status(checkout.ws, "one-question")
    assert {(item["reason"], item["code"]) for item in view["attention"]} == {("worktree_missing", EXIT_UNVERIFIED)}


@pytest.mark.heavy
def test_a_lost_checkout_after_a_complete_collection_is_attention(checkout):
    import shutil
    from stewart.status import status
    prepared = _session(checkout)
    collect(checkout.ws, "one-question", auditor_stopped="finished")
    assert status(checkout.ws, "one-question")["exit_code"] == EXIT_OK
    shutil.rmtree(prepared.worktree)
    view = status(checkout.ws, "one-question")
    assert {(item["reason"], item["code"]) for item in view["attention"]} == {("worktree_missing", EXIT_ATTENTION)}


@pytest.mark.heavy
def test_an_interrupted_preparation_is_attention(checkout, monkeypatch):
    import stewart.prepare as prepare_module
    from stewart.status import status
    real = prepare_module.write_exclusive

    def crash(path, data, **kwargs):
        # A crash, not a handled failure: no PREPARE-ERROR.json is written.
        if Path(path).name == "LAUNCH.md":
            raise KeyboardInterrupt("synthetic crash before the handoff")
        return real(path, data, **kwargs)

    revision = checkout.prompt_commit()
    with monkeypatch.context() as patch:
        patch.setattr(prepare_module, "write_exclusive", crash)
        with pytest.raises(KeyboardInterrupt):
            prepare_module.prepare(checkout.ws, revision)
    view = status(checkout.ws, "one-question")
    assert view["preparation"]["state"] == "incomplete"
    assert {(item["reason"], item["code"]) for item in view["attention"]} == {("preparation_incomplete", EXIT_ATTENTION)}


@pytest.mark.heavy
def test_status_news_is_the_latest_word(checkout):
    from stewart.status import status
    prepared = _session(checkout)
    exit_log = prepared.session / "HARNESS-EXIT.txt"
    exit_log.write_text("1 2026-01-01T00:00:00Z\n")
    view = status(checkout.ws, "one-question")
    assert {(item["reason"], item["code"]) for item in view["attention"]} == {("harness_exit_nonzero", EXIT_ATTENTION)}
    collected = collect(checkout.ws, "one-question", auditor_stopped="finished")
    assert status(checkout.ws, "one-question")["exit_code"] == EXIT_OK, "a later collection supersedes the exit"
    started = json.loads((Path(collected["path"]) / "STARTED.json").read_text())

    def partial(name: str, when: str) -> Path:
        directory = prepared.session / "collections" / name
        directory.mkdir(mode=0o700)
        (directory / "STARTED.json").write_text(json.dumps({**started, "collected_at": when}))
        return directory

    # Invariance: a partial attempt that began before the complete one is history.
    partial("20000101T000000-00000000", "2000-01-01T00:00:00+00:00")
    assert status(checkout.ws, "one-question")["exit_code"] == EXIT_OK
    # Measured: one that began after it is the latest word.
    partial("29990101T000000-00000000", "2999-01-01T00:00:00+00:00")
    view = status(checkout.ws, "one-question")
    assert {(item["reason"], item["code"]) for item in view["attention"]} == {("collection_incomplete", EXIT_ATTENTION)}
