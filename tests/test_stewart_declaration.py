"""Declaration contracts built from authored bytes, paired identity and prose controls.

The parser is checked against hand-authored reports as well as helper output.
Custody checks compare named identities; none of these controls dates a mutation
or treats auditor completion as an observed process outcome.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import sys

import pytest

from stewart import _util as _hash
import stewart
from stewart import report_declaration as declaration
from stewart.collect import collect
from stewart._bootstrap import StewartError
from stewart.status import status
from stewart.triage import triage, triage_draft
from stewart.workspace import workspace
import stewart_support as support

INSTALLED_LIB = Path(stewart.__file__).parent.parent
pytestmark = pytest.mark.system


def authored(values, *, before=b"Authored scope.\n\n", after=b"\nCompletion qualification: static only.\n"):
    """Independent bytes: do not call the instrument's serializer or field list."""
    return before + b"```audit-report\n" + json.dumps(values).encode() + b"\n```" + after


def values(prepared, checkout, **changes):
    result = {"schema_version": 2, "audit_id": checkout.meta["audit_id"],
              "target_commit": checkout.meta["target_commit"], "launch_prompt_commit": prepared.revision,
              "prompt_sha256": prepared.prepared["prompt_sha256"], "launch_token": prepared.prepared["launch_token"],
              "observed_checkout_commit": prepared.revision, "completion": "partial", "report_kind": None}
    return {**result, **changes}


def arguments(prepared, checkout):
    return dict(expected_worktree=prepared.worktree, launch_prompt_commit=prepared.revision,
                prompt_sha256=prepared.prepared["prompt_sha256"], launch_token=prepared.prepared["launch_token"])


def argv(prepared, checkout, operation="check", **changes):
    args = arguments(prepared, checkout)
    args.update(changes)
    result = [operation, "--workspace", checkout.ws.rel]
    for name, value in args.items():
        result += ["--" + name.replace("_", "-"), str(value)]
    return result


def fingerprint(location):
    return _hash.sha256_bytes(location.read_bytes()) if location.is_file() else None


def refused(prepared, checkout, monkeypatch, capsys, reason, operation="check", **changes):
    """Every CLI refusal checks exit, reason, actionable text and preserved bytes."""
    before = fingerprint(prepared.report)
    monkeypatch.chdir(prepared.worktree)
    assert declaration.main(argv(prepared, checkout, operation, **changes)) == 2
    output = capsys.readouterr()
    assert not output.out and f"Refused ({reason}):" in output.err
    assert "Next:" in output.err
    assert fingerprint(prepared.report) == before, "refusal must not change report bytes"
    return output.err


def test_start_set_check_preserve_prose_and_print_identity(checkout, monkeypatch, capsys):
    prepared = support.prepared_session(checkout, report=None)
    monkeypatch.chdir(prepared.worktree)
    assert declaration.main([*argv(prepared, checkout, "start"), "--print"]) == 0
    output = capsys.readouterr().out
    line, printed = output.split("\n", 1)
    assert "partial" in line and prepared.revision in line and str(prepared.report) in line
    assert json.loads(printed) == values(prepared, checkout)
    assert b"Completion qualification:" in prepared.report.read_bytes()
    refused(prepared, checkout, monkeypatch, capsys, "destination_exists", "start")
    # Arbitrary surrounding bytes, including CRLF prose, belong to the auditor.
    prefix, suffix = b"Prose\xff\r\n```python\nx = 1\n```\n", b"\nQualification: pending control.\x00\r\n"
    prepared.report.write_bytes(authored(values(prepared, checkout), before=prefix, after=suffix))
    assert declaration.main([*argv(prepared, checkout, "set"), "--completion", "complete", "--report-kind", "answer", "--print"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output.split("\n", 1)[1])["completion"] == "complete"
    assert prepared.report.read_bytes().startswith(prefix) and prepared.report.read_bytes().endswith(suffix)
    before = fingerprint(prepared.report)
    assert declaration.main(argv(prepared, checkout)) == 0
    assert capsys.readouterr().out.startswith("complete audit=one-question HEAD=")
    assert fingerprint(prepared.report) == before


@pytest.mark.parametrize("field,replacement", [
    ("audit_id", "another-question"), ("target_commit", "1" * 40),
    ("launch_prompt_commit", "2" * 40), ("prompt_sha256", "3" * 64),
    ("launch_token", "4" * 16), ("observed_checkout_commit", "5" * 40),
])
def test_each_identity_compares_its_source_and_ignores_prose(checkout, monkeypatch, capsys, field, replacement):
    prepared = support.prepared_session(checkout, report=None)
    original = values(prepared, checkout)
    prepared.report.write_bytes(authored({**original, field: replacement}))
    refused(prepared, checkout, monkeypatch, capsys, "identity_mismatch", "set", completion="complete", report_kind="answer")
    refused(prepared, checkout, monkeypatch, capsys, "identity_mismatch")
    collected = collect(checkout.ws, "one-question", auditor_stopped="finished")
    comparison = collected["receipt"]["declaration"]["comparisons"][field]
    assert comparison == {"expected": original[field], "observed": replacement,
        "source": "HEAD observed at collection" if field == "observed_checkout_commit" else "pinned session",
        "matches": False}
    gap = "declaration_stale" if field == "observed_checkout_commit" else f"declaration_mismatch:{field}"
    assert {g["id"] for g in collected["gaps"]} == {gap}
    prepared.report.write_bytes(authored(original, before=b"Status: complete (a prose claim is ignored)\n"))
    assert declaration.main(argv(prepared, checkout)) == 0
    capsys.readouterr()
    assert collect(checkout.ws, "one-question", auditor_stopped="finished")["gaps"] == []


@pytest.mark.parametrize("corruption,reason", [
    (lambda b: b"\xef\xbb\xbf" + b, "byte_order_mark"),
    (lambda b: b.replace(b"\n", b"\r\n"), "crlf"),
    (lambda b: b.replace(b"```audit-report\n", b"```audit-report \n"), "fence_trailing_space"),
    (lambda b: b.replace(b"\n```\n", b"\n``` \n"), "fence_trailing_space"),
    (lambda b: b"````markdown\n" + b + b"\n````\n", "nested_block"),
    (lambda b: b + b, "duplicate_blocks"),
    (lambda b: b.replace(b'"schema_version": 2', b'"schema_version": 2, "schema_version": 2'), "duplicate_key"),
    (lambda b: b.replace(b'"schema_version": 2', b'"extra": "scope", "schema_version": 2'), "unknown_field"),
    (lambda b: b'```audit-report\n[]\n```\n', "non_object"),
    (lambda b: b'```audit-report\n{broken}\n```\n', "invalid_json"),
    (lambda b: b'```audit-report\n{}\n```\n', "missing_field"),
    (lambda b: b.replace(b'"schema_version": 2', b'"schema_version": true'), "schema_version"),
    (lambda b: b.replace(b'"completion": "partial"', b'"completion": "complete (static only)"'), "completion"),
    (lambda b: b.replace(b'"audit_id": "one-question"', b'"audit_id": null'), "field_type"),
    (lambda b: b.replace(b'"audit_id": "one-question"', b'"audit_id": "../escape"'), "audit_id_format"),
    (lambda b: re.sub(rb'"target_commit": "[^"]+"', b'"target_commit": "HEAD"', b), "commit_format"),
    (lambda b: re.sub(rb'"launch_token": "[^"]+"', b'"launch_token": "short"', b), "identity_format"),
    (lambda b: b.replace(b"```audit-report", b"~~~audit-report"), "malformed_fence"),
    (lambda b: b'```audit-report\n{}', "unterminated_block"),
    (lambda b: b"Status: complete\n", "missing"),
])
def test_parse_refusals_are_distinct_and_collection_preserves_bytes(checkout, monkeypatch, capsys, corruption, reason):
    prepared = support.prepared_session(checkout, report=None)
    bad = corruption(authored(values(prepared, checkout)))
    prepared.report.write_bytes(bad)
    refused(prepared, checkout, monkeypatch, capsys, reason, "set", completion="complete", report_kind="answer")
    refused(prepared, checkout, monkeypatch, capsys, reason)
    captured = collect(checkout.ws, "one-question", auditor_stopped="interrupted")
    assert (Path(captured["path"]) / "REPORT.md").read_bytes() == bad
    gap = "declaration_missing" if reason == "missing" else f"declaration_invalid:{reason}"
    assert gap in {item["id"] for item in captured["gaps"]}
    assert captured["receipt"]["declaration"]["declaration"] is None


@pytest.mark.parametrize("operation", ["start", "set", "check"])
@pytest.mark.parametrize("change", ["audit_id", "report_path", "digest"])
def test_prompt_agreement_precedes_destination_selection(checkout, monkeypatch, capsys, operation, change):
    prepared = support.prepared_session(checkout, report=None)
    if operation != "start":
        prepared.report.write_bytes(authored(values(prepared, checkout)))
    substitute = prepared.worktree / checkout.ws.reports / "substitute.md"
    prompt = prepared.worktree / checkout.ws.prompt
    extras = {"completion": "complete", "report_kind": "answer"} if operation == "set" else {}
    if change == "digest":
        extras["prompt_sha256"] = "0" * 64
    else:
        text = prompt.read_text()
        text = text.replace('"audit_id": "one-question"', '"audit_id": "substitute"') if change == "audit_id" else text.replace(checkout.meta["report_path"], f"{checkout.ws.reports}/substitute.md")
        prompt.write_text(text)
    error = refused(prepared, checkout, monkeypatch, capsys,
                    "prompt_digest" if change == "digest" else "prompt_drift", operation, **extras)
    assert "expected" in error and "observed" in error
    assert not substitute.exists(), "a changed assignment cannot redirect a write"


@pytest.mark.parametrize("operation", ["start", "set", "check"])
def test_expected_root_separates_identical_detached_worktrees(checkout, monkeypatch, capsys, operation):
    prepared = support.prepared_session(checkout, report=None)
    second = checkout.tmp / "second"
    checkout.git("worktree", "add", "--detach", str(second), prepared.revision)
    for root in (prepared.worktree, second):
        assert (root / ".git").is_file()
        assert checkout.git("rev-parse", "HEAD", cwd=root) == prepared.revision
        assert checkout.git("branch", "--show-current", cwd=root) == "", "both controls must really be detached"
    alternate = second / checkout.meta["report_path"]
    alternate.parent.mkdir(parents=True)
    if operation != "start":
        prepared.report.write_bytes(authored(values(prepared, checkout)))
        alternate.write_bytes(prepared.report.read_bytes())
    expected_before, alternate_before = fingerprint(prepared.report), fingerprint(alternate)
    args = argv(prepared, checkout, operation)
    if operation == "set":
        args += ["--completion", "complete", "--report-kind", "answer"]
    for root, reason in ((checkout.repo, "checkout_root"), (second, "checkout_root")):
        monkeypatch.chdir(root)
        assert declaration.main(args) == 2
        assert f"Refused ({reason})" in capsys.readouterr().err
        assert fingerprint(prepared.report) == expected_before and fingerprint(alternate) == alternate_before
        assert not (checkout.repo / checkout.meta["report_path"]).exists()
    monkeypatch.chdir(prepared.worktree)
    assert declaration.main(args) == 0
    capsys.readouterr()
    # Naming the maintainer root explicitly still cannot turn it into a prepared worktree.
    monkeypatch.chdir(checkout.repo)
    main_args = argv(prepared, checkout, "start", expected_worktree=checkout.repo)
    assert declaration.main(main_args) == 2
    assert "checkout_git_file" in capsys.readouterr().err


@pytest.mark.parametrize("operation", ["start", "set"])
@pytest.mark.parametrize("stage", ["write", "rename", "input_change"])
def test_failed_publication_preserves_original_and_names_staging(checkout, monkeypatch, capsys, operation, stage):
    prepared = support.prepared_session(checkout, report=None)
    if operation == "set":
        prepared.report.write_bytes(authored(values(prepared, checkout)))
    real = declaration.write_exclusive
    def failed_writer(location, data, **kwargs):
        real(location, data[:8] if stage == "write" else data, **kwargs)
        if stage == "write":
            raise OSError("injected staged write failure")
        if stage == "input_change":
            (prepared.worktree / checkout.ws.prompt).write_text("changed while staging")
    monkeypatch.setattr(declaration, "write_exclusive", failed_writer)
    if stage == "rename":
        def fail(*args, **kwargs):
            raise OSError("injected publication failure")
        monkeypatch.setattr(declaration.os, "replace" if operation == "set" else "link", fail)
    extras = {"completion": "complete", "report_kind": "answer"} if operation == "set" else {}
    error = refused(prepared, checkout, monkeypatch, capsys,
                    "prompt_drift" if stage == "input_change" else "report_write", operation, **extras)
    leftovers = list(prepared.report.parent.glob(".*.tmp"))
    assert len(leftovers) == 1 and str(leftovers[0]) in error
    captured = collect(checkout.ws, "one-question", auditor_stopped="interrupted")
    rel = leftovers[0].relative_to(prepared.worktree).as_posix()
    assert f"unexpected_path:{rel}" in {g["id"] for g in captured["gaps"]}


@pytest.mark.parametrize("kind", ["report_symlink", "ancestor_symlink", "fifo", "prompt_symlink", "attached", "missing"])
def test_unsafe_or_unavailable_context_never_changes_other_bytes(checkout, monkeypatch, capsys, kind):
    prepared = support.prepared_session(checkout, report=None)
    sentinel = checkout.tmp / "sentinel"
    sentinel.write_bytes(authored(values(prepared, checkout)))
    if kind == "report_symlink":
        prepared.report.symlink_to(sentinel)
    elif kind == "ancestor_symlink":
        prepared.report.parent.rmdir()
        prepared.report.parent.symlink_to(checkout.tmp, target_is_directory=True)
    elif kind == "prompt_symlink":
        prompt = prepared.worktree / checkout.ws.prompt
        prompt.unlink()
        prompt.symlink_to(checkout.repo / checkout.ws.prompt)
    elif kind == "fifo":
        os.mkfifo(prepared.report)
    elif kind == "attached":
        checkout.git("switch", "-c", "auditor-change", cwd=prepared.worktree)
    expected = {"report_symlink": "path_symlink", "ancestor_symlink": "path_symlink", "fifo": "report_unreadable",
                "prompt_symlink": "path_symlink", "attached": "checkout_detached", "missing": "context_unavailable"}[kind]
    before = fingerprint(sentinel)
    refused(prepared, checkout, monkeypatch, capsys, expected)
    assert fingerprint(sentinel) == before


def test_freshness_compares_declared_head_and_launch_head_independently(checkout, monkeypatch, capsys):
    prepared = support.prepared_session(checkout, report=None)
    local = workspace(prepared.worktree, checkout.ws.rel)
    declaration.report_declaration(local, "start", **arguments(prepared, checkout))
    declaration.report_declaration(local, "set", completion="complete", report_kind="answer", **arguments(prepared, checkout))
    prepared.report.write_bytes(prepared.report.read_bytes() + b"\nAdditional prose.\n")
    assert collect(checkout.ws, "one-question", auditor_stopped="finished")["gaps"] == []
    checkout.git("commit", "--allow-empty", "-qm", "Unexpected auditor commit", cwd=prepared.worktree)
    refused(prepared, checkout, monkeypatch, capsys, "checkout_commit", "set", completion="partial")
    collected = collect(checkout.ws, "one-question", auditor_stopped="finished")
    assert {g["id"] for g in collected["gaps"]} == {"declaration_stale", "checkout_commit_changed"}
    head = checkout.git("rev-parse", "HEAD", cwd=prepared.worktree)
    comparison = collected["receipt"]["declaration"]["comparisons"]["observed_checkout_commit"]
    assert comparison["expected"] == head and comparison["observed"] == prepared.revision
    # Manual declaration at collected HEAD separates stale identity from changed launch identity.
    prepared.report.write_bytes(authored(values(prepared, checkout, observed_checkout_commit=head)))
    assert {g["id"] for g in collect(checkout.ws, "one-question", auditor_stopped="finished")["gaps"]} == {"checkout_commit_changed"}


@pytest.mark.parametrize("stop", ["finished", "interrupted", "blocked"])
def test_completion_claim_does_not_change_observations(checkout, stop):
    prepared = support.prepared_session(checkout, report=None)
    results = []
    views = []
    for completion in ("partial", "complete"):
        prepared.report.write_bytes(authored(values(prepared, checkout, completion=completion, report_kind="answer")))
        results.append(collect(checkout.ws, "one-question", auditor_stopped=stop))
        views.append(status(checkout.ws, "one-question"))
    partial, complete = results
    assert partial["receipt"]["errors"] == complete["receipt"]["errors"] == []
    for key in ("git_discovery", "checkout_commit_changed", "auditor_stopped", "auditor_stop_kind"):
        assert partial["receipt"][key] == complete["receipt"][key]
    assert views[0]["experiment"] == views[1]["experiment"]
    assert partial["gaps"] == []
    assert {g["id"] for g in complete["gaps"]} == ({"completion_stop_discrepancy"} if stop == "interrupted" else set())
    actions = [view["next_actions"][-1] for view in views]
    if stop == "interrupted":
        assert "completion_stop_discrepancy" in " ".join(actions[1]["prerequisites"])
        assert "both claims true" in complete["gaps"][0]["description"]
    else:
        assert actions[0]["prerequisites"] == actions[1]["prerequisites"]


@pytest.mark.parametrize("report", [None, "", "Status: complete\n"])
def test_draft_is_unanswered_bound_and_read_only(checkout, report):
    prepared = support.prepared_session(checkout, report=report)
    captured = collect(checkout.ws, "one-question", auditor_stopped="interrupted")
    before = support.snapshot_tree(prepared.session)
    draft = triage_draft(checkout.ws, "one-question", collection=captured["collection"])
    assert support.snapshot_tree(prepared.session) == before
    response = draft["response"]
    assert response["decision"] is None and response["support_reviewed"] == []
    assert response["custody_gaps"] == {g["id"]: None for g in captured["gaps"]}
    with pytest.raises(StewartError, match="decision"):
        triage(checkout.ws, "one-question", collection=captured["collection"], response=response, actor="manager")
    response["decision"] = "Preserve partial evidence."
    if "report_gap" in response:
        response["report_gap"] = "No nonempty report was captured; keep the available evidence."
    with pytest.raises(StewartError, match=next(iter(response["custody_gaps"]))):
        triage(checkout.ws, "one-question", collection=captured["collection"], response=response, actor="manager")
    response["custody_gaps"] = {g: "Inspected; preserve the gap for follow-up." for g in response["custody_gaps"]}
    reviewed = triage(checkout.ws, "one-question", collection=captured["collection"], response=response, actor="manager")
    assert reviewed["record"]["report_sha256"] == (captured["receipt"].get("report_sha256") if report else None)
    if report is not None:
        (Path(captured["path"]) / "REPORT.md").write_bytes(b"altered captured bytes")
        with pytest.raises(StewartError) as error:
            triage_draft(checkout.ws, "one-question", collection=captured["collection"])
        assert error.value.reason == "evidence_tampered"


def test_launch_commands_execute_in_disposable_prepared_checkout(checkout, run_cmd):
    # The issued commands work when project history contains no Stewart code.
    prepared = support.prepared_session(checkout, report=None)
    text = (prepared.session / "LAUNCH.md").read_text()
    commands = re.findall(r"```sh\n(.*?)\n```", text, re.S)
    assert len(commands) == 4
    for command in commands:
        parts = shlex.split(command)
        assert parts[:3] == ["cd", str(prepared.worktree), "&&"]
        assert parts[4:6] == ["-I", "-B"]
        result = run_cmd(parts[3:], cwd=prepared.worktree, env={"PYTHONPATH": str(prepared.worktree)}, timeout=20)
        assert result.returncode == 0, result.stderr
        assert "audit=one-question" in result.stdout
        if "--helper declaration" in command:
            assert prepared.revision in result.stdout
        else:
            assert "selected=1 matched=1 failed=0" in result.stdout
    assert json.loads(result.stdout.split("\n", 1)[1])["completion"] == "complete"


def test_validator_failure_cannot_prevent_raw_capture(checkout, monkeypatch):
    prepared = support.prepared_session(checkout, report="raw interrupted report\n")
    def fail(*args, **kwargs):
        assert list(prepared.session.glob("collections/*/REPORT.md")), "capture must precede validation"
        raise RuntimeError("injected validator failure")
    monkeypatch.setattr(declaration, "validate_report_declaration", fail)
    result = collect(checkout.ws, "one-question", auditor_stopped="interrupted")
    assert (Path(result["path"]) / "REPORT.md").read_bytes() == prepared.report.read_bytes()
    assert result["receipt"]["errors"] == ["declaration validation: injected validator failure"]
    assert "declaration_invalid:validation_error" in {g["id"] for g in result["gaps"]}


def test_transcribed_token_is_only_verifiable_by_stewart(checkout, monkeypatch, capsys):
    prepared = support.prepared_session(checkout, report=None)
    monkeypatch.chdir(prepared.worktree)
    wrong = "a" * 16 if prepared.prepared["launch_token"] != "a" * 16 else "b" * 16
    for operation in ("start", "check"):
        assert declaration.main(argv(prepared, checkout, operation, launch_token=wrong)) == 0
        capsys.readouterr()
    result = collect(checkout.ws, "one-question", auditor_stopped="finished")
    assert {g["id"] for g in result["gaps"]} == {"declaration_mismatch:launch_token"}


def test_report_change_during_staging_is_not_overwritten(checkout, monkeypatch, capsys):
    prepared = support.prepared_session(checkout, report=None)
    original = authored(values(prepared, checkout))
    prepared.report.write_bytes(original)
    real = declaration.write_exclusive
    changed = original + b"Concurrent writer's evidence.\n"
    def write_and_change(location, data, **kwargs):
        real(location, data, **kwargs)
        prepared.report.write_bytes(changed)
    monkeypatch.setattr(declaration, "write_exclusive", write_and_change)
    monkeypatch.chdir(prepared.worktree)
    before = fingerprint(prepared.report)
    assert declaration.main(argv(prepared, checkout, "set", completion="complete", report_kind="answer")) == 2
    error = capsys.readouterr().err
    assert "report_changed" in error
    assert fingerprint(prepared.report) == _hash.sha256_bytes(changed) != before
    assert prepared.report.read_bytes() == changed, "the helper must preserve the other writer's bytes"
    for temporary in prepared.report.parent.glob(".*.tmp"):
        assert str(temporary) in error


def test_stop_discrepancy_draft_cli_keeps_context_separate(checkout, monkeypatch, capsys):
    from stewart.cli import main

    prepared = support.prepared_session(checkout, report=None)
    prepared.report.write_bytes(authored(values(prepared, checkout, completion="complete", report_kind="answer")))
    captured = collect(checkout.ws, "one-question", auditor_stopped="interrupted")
    base = ["--repo", str(checkout.repo), "--workspace", checkout.ws.rel]
    args = ["triage-draft", "--audit-id", "one-question", "--collection", captured["collection"]]
    assert main(base + args) == 0
    output = capsys.readouterr()
    response = json.loads(output.out)
    assert "Declaration validation: valid" in output.err and "completion_stop_discrepancy:" in output.err
    assert "  launch_token: matches; expected" in output.err, "each identity comparison is its own readable line"
    assert "context" not in response and response["custody_gaps"] == {"completion_stop_discrepancy": None}
    assert main(base + ["--json"] + args) == 0
    output = capsys.readouterr()
    assert not output.err
    result = json.loads(output.out)["result"]
    assert result["response"] == response
    assert result["context"]["declaration"]["declaration"]["completion"] == "complete"
    response["decision"] = "Retain both attributed accounts."
    with pytest.raises(StewartError, match="completion_stop_discrepancy"):
        triage(checkout.ws, "one-question", collection=captured["collection"], response=response, actor="manager")
    response["custody_gaps"]["completion_stop_discrepancy"] = "Completion was followed by interruption; both claims can hold."
    reviewed = triage(checkout.ws, "one-question", collection=captured["collection"], response=response, actor="manager")
    assert reviewed["record"]["report_sha256"] == fingerprint(prepared.report)
    # A second collection has different bytes; the old response cannot bind it.
    prepared.report.write_bytes(prepared.report.read_bytes() + b"More prose.\n")
    second = collect(checkout.ws, "one-question", auditor_stopped="interrupted")
    with pytest.raises(StewartError) as error:
        triage(checkout.ws, "one-question", collection=second["collection"], response=response, actor="manager")
    assert error.value.reason == "collection_binding"


def test_completion_leaves_recorded_child_process_facts_unchanged(tmp_path, run_cmd):
    from stewart.experiment import release, run

    checkout = support.experiment_checkout(tmp_path, run_cmd)
    prepared = support.prepared_experiment(checkout)
    released = release(checkout.ws, "one-question", review=support.REVIEW, actor="manager")
    run(checkout.ws, "one-question", release=released["release"], timeout=20)
    report = prepared.worktree / checkout.meta["report_path"]
    views = []
    results = []
    for completion in ("partial", "complete"):
        report.write_bytes(authored(values(prepared, checkout, completion=completion, report_kind="answer")))
        results.append(collect(checkout.ws, "one-question", auditor_stopped="finished"))
        views.append(status(checkout.ws, "one-question"))
    assert views[0]["attempts"] == views[1]["attempts"] and views[0]["attempts"], "recorded process evidence must actually exist"
    assert results[0]["receipt"]["errors"] == results[1]["receipt"]["errors"]
    assert results[0]["gaps"] == results[1]["gaps"]


def test_missing_latest_report_does_not_inherit_earlier_completion(checkout):
    prepared = support.prepared_session(checkout, report=None)
    prepared.report.write_bytes(authored(values(prepared, checkout, completion="complete", report_kind="answer")))
    collect(checkout.ws, "one-question", auditor_stopped="finished")
    prepared.report.unlink()
    collect(checkout.ws, "one-question", auditor_stopped="blocked")
    view = status(checkout.ws, "one-question")
    assert view["auditor_reported"]["completion"]["value"] is None
    assert view["auditor_reported"]["completion"]["validation"]["status"] == "missing"
    # Unreadable/unsupported sessions must not resurrect an old declaration either.
    record = support.read_json(prepared.session / "session.json")
    record["schema_version"] = 3
    (prepared.session / "session.json").write_text(json.dumps(record))
    assert status(checkout.ws, "one-question")["auditor_reported"]["completion"]["reason"] == "session_unavailable"


@pytest.mark.parametrize("report", [None, "", "Same report bytes\n"])
def test_draft_cannot_review_another_collection_with_identical_report(checkout, report):
    prepared = support.prepared_session(checkout, report=report)
    support_path = prepared.worktree / "stray.txt"
    support_path.write_text("reviewed support bytes\n")
    first = collect(checkout.ws, "one-question", auditor_stopped="finished")
    response = triage_draft(checkout.ws, "one-question", collection=first["collection"])["response"]
    response.update(decision="Keep the reviewed first capture", support_reviewed=["stray.txt"],
                    custody_gaps={gap: "Reviewed first capture" for gap in response["custody_gaps"]})
    if "report_gap" in response:
        response["report_gap"] = "No nonempty report; inspected support instead"
    support_path.write_text("different unreviewed bytes\n")
    second = collect(checkout.ws, "one-question", auditor_stopped="blocked")
    assert first["receipt"].get("report_sha256") == second["receipt"].get("report_sha256")
    assert first["gaps"] == second["gaps"], "gap membership and report bytes do not identify a capture"
    before = support.snapshot_tree(prepared.session / "collections")
    with pytest.raises(StewartError) as refused:
        triage(checkout.ws, "one-question", collection=second["collection"], response=response, actor="manager")
    assert refused.value.reason == "collection_binding"
    assert refused.value.next_steps and not (prepared.session / "triage").exists()
    # Even transcribing the new name must not silently rebind the old digest.
    response_with_new_name = {**response, "collection": second["collection"]}
    with pytest.raises(StewartError) as refused:
        triage(checkout.ws, "one-question", collection=second["collection"], response=response_with_new_name, actor="manager")
    assert refused.value.reason == "collection_binding"
    # The original capture remains usable despite changes to the live worktree.
    reviewed = triage(checkout.ws, "one-question", collection=first["collection"], response=response, actor="manager")
    assert reviewed["record"]["response"]["collection"] == first["collection"]
    assert reviewed["record"]["response"]["collection_sha256"] == _hash.sha256_bytes((Path(first["path"]) / "collection.json").read_bytes())
    assert support.snapshot_tree(prepared.session / "collections") == before


@pytest.mark.parametrize("kind", ["missing", "symlink", "directory"])
def test_project_helper_shape_does_not_select_supplied_runtime(checkout, run_cmd, kind):
    from stewart.prepare import prepare

    helper = checkout.repo / "stewart/report_declaration.py"
    helper.parent.mkdir(parents=True)
    if kind == "symlink":
        helper.symlink_to("assignment.py")
    elif kind == "directory":
        helper.mkdir()
        (helper / "entry.txt").write_text("not a Python module\n")
    if kind != "missing":
        checkout.git("add", "stewart")
        checkout.git("commit", "-qm", "Unrelated project helper path")
    checkout.meta["target_commit"] = checkout.git("rev-parse", "HEAD")
    revision = checkout.prompt_commit()
    prepared = prepare(checkout.ws, revision)
    command = next(c for c in re.findall(r"```sh\n(.*?)\n```", Path(prepared["launch"]).read_text(), re.S)
                   if "--helper declaration -- start" in c)
    result = run_cmd(shlex.split(command)[3:], cwd=prepared["worktree"],
                     env={"PYTHONPATH": prepared["worktree"]}, check=True)
    assert "partial audit=one-question" in result.stdout
    assert Path(prepared["runtime"]["root"]).is_relative_to(checkout.repo / ".scratch/stewart-runtimes")


def test_prepare_ignores_a_working_project_helper(checkout, run_cmd):
    from stewart.prepare import prepare

    revision = checkout.prompt_commit()
    helper = checkout.repo / "stewart/report_declaration.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("raise RuntimeError('unrelated project helper must never run')\n")
    prepared = prepare(checkout.ws, revision)
    launch = Path(prepared["launch"]).read_text()
    command = next(c for c in re.findall(r"```sh\n(.*?)\n```", launch, re.S)
                   if "--helper declaration -- start" in c)
    parts = shlex.split(command)
    result = run_cmd(parts[3:], cwd=prepared["worktree"], env={"PYTHONPATH": prepared["worktree"]}, check=True)
    assert "partial audit=one-question" in result.stdout


@pytest.mark.parametrize("problem", ["mismatch", "invalid", "missing", "tampered", "valid"])
def test_human_status_keeps_declaration_diagnostics_after_triage(checkout, problem):
    from stewart.cli import render

    prepared = support.prepared_session(checkout, report=None)
    report_values = values(prepared, checkout)
    if problem == "mismatch":
        report_values["launch_token"] = "0" * 16 if prepared.prepared["launch_token"] != "0" * 16 else "1" * 16
    data = authored(report_values) if problem in ("mismatch", "valid") else (
        b"```audit-report\n{broken}\n```\n" if problem == "invalid" else b"Prose only\n")
    prepared.report.write_bytes(data)
    captured = collect(checkout.ws, "one-question", auditor_stopped="blocked")
    triage(checkout.ws, "one-question", collection=captured["collection"],
           response=support.response_for(captured), actor="manager")
    if problem == "tampered":
        (Path(captured["path"]) / "REPORT.md").write_bytes(b"Changed capture\n")
    view = status(checkout.ws, "one-question")
    text = render("status", view)
    assert "stop kind: blocked" in text and "maintainer via --auditor-stopped" in text
    if problem == "valid":
        assert "Auditor-reported completion: partial" in text and "declaration validation: valid" in text
        assert "declaration [" not in text
    else:
        assert "Auditor-reported completion: unavailable" in text and "completion: None" not in text
        expected_reason = {"mismatch": "identity_mismatch", "invalid": "invalid_json", "missing": "missing", "tampered": "evidence_tampered"}[problem]
        assert f"declaration [{expected_reason}]" in text
    if problem == "mismatch":
        assert prepared.prepared["launch_token"] in text and report_values["launch_token"] in text
        assert "pinned session" in text
    # Live prose is irrelevant to the captured diagnostics displayed to the manager.
    prepared.report.write_text("Unrelated live report changes\n")
    assert render("status", status(checkout.ws, "one-question")) == text
