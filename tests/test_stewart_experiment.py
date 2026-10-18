"""Optional experiment execution: grant, frozen release, one-shot attempt, independent evidence.

Children are harmless synthetic scripts constructed in the worktree the way an
auditor would construct them. Each control pairs the refusal or failure with
the nearest admissible case so the tests read what the wrapper compares: frozen
identities, endpoint state, launch outcome and ledger rows, each recorded
separately from the others.
"""

from __future__ import annotations

import json
from pathlib import Path
import signal
import sys
import threading

import pytest

from stewart import _util as _hash
import stewart
from stewart.assignment import initialize, prompt_metadata
from stewart._bootstrap import StewartError
from stewart.experiment import release, run
from stewart.status import status
import stewart_support as support
from stewart_support import MANIFEST, OUTPUT, PREDICTION, SCRIPT, WS, assignment_text, read_json

INSTALLED_LIB = Path(stewart.__file__).parent.parent
pytestmark = pytest.mark.system


def _release(checkout, review=None, actor="manager"):
    return release(checkout.ws, checkout.meta["audit_id"], review=review or support.REVIEW, actor=actor)


def _run(checkout, released, timeout=60):
    return run(checkout.ws, checkout.meta["audit_id"], release=released["release"], timeout=timeout)


def test_grant_lives_in_the_assignment_block_and_is_validated_for_shape_and_containment(checkout):
    ws, meta = checkout.ws, checkout.meta
    meta["scratch_paths"] = list(support.SCRATCH)
    meta["input_files"] = ["input.txt", MANIFEST]

    def metadata(grant_overrides=None, *, with_prose=True):
        local = dict(meta, experiment=support.grant(**(grant_overrides or {})))
        text = assignment_text(local, extra_sections=support.AUTHORIZATION if with_prose else None)
        return prompt_metadata(text, ws)

    accepted = metadata()
    assert accepted["experiment"]["freeze"] == [PREDICTION] and accepted["experiment"]["invocations"] == 1
    with pytest.raises(StewartError) as refused:
        metadata(with_prose=False)
    assert refused.value.reason == "assignment_sections", "the auditor-facing prose must accompany the object"
    for overrides, reason in (
        ({"script": "elsewhere/experiment.py"}, "grant_containment"),
        ({"output_area": f"{WS}/reports"}, "grant_containment"),
        ({"freeze": ["evidence/protected.json"]}, "grant_containment"),
        ({"script": f"{OUTPUT}/experiment.py"}, "grant_containment"),
        ({"protected_manifest": "other.txt"}, "grant_containment"),
        ({"argv_template": ["{interpreter}", "{script}", "{home}"]}, "grant_schema"),
        ({"argv_template": ["{interpreter}", "--root", "{root}"]}, "grant_schema"),
        ({"invocations": 2}, "grant_schema"),
        ({"interpreter": "/usr/bin/python3"}, "grant_schema"),
        ({"environment": "inherit"}, "grant_schema"),
        ({"cwd": "repo"}, "grant_schema"),
        ({"permission": "execution"}, "grant_schema"),
    ):
        with pytest.raises(StewartError) as refused:
            metadata(overrides)
        assert refused.value.reason == reason, overrides
    draft = initialize(ws, "granted-question", "HEAD", inputs=["input.txt"],
                       scratch=[f"{WS}/scratch/granted-question/artifacts", f"{WS}/scratch/granted-question/run"],
                       experiment=support.grant(script=f"{WS}/scratch/granted-question/artifacts/x.py",
                                                freeze=[], output_area=f"{WS}/scratch/granted-question/run",
                                                protected_manifest="input.txt"))["draft"]
    assert '"experiment":' in draft and "## Experiment authorization" in draft


def test_release_freezes_exact_artifacts_and_run_consumes_the_release_once(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    released = _release(checkout)
    record = released["record"]
    assert set(record["frozen"]) == {SCRIPT, PREDICTION, MANIFEST}
    assert record["frozen"][SCRIPT] == _hash.sha256_bytes((exp.script).read_bytes())
    assert record["child"]["ledger"]["sha256"] == _hash.sha256_bytes((INSTALLED_LIB / "stewart/ledger.py").read_bytes())
    assert record["approved_argv"][:3] == [sys.executable, "-B", SCRIPT] and record["approved_argv"][4] == str(exp.worktree)
    assert record["argv"][:3] == [sys.executable, "-I", "-B"]
    assert record["child"]["project_paths"] == [str(exp.script.parent), str(exp.worktree)]
    assert record["cwd"] == str(exp.worktree) and "PYTHONPATH" not in record["environment"]
    assert record["review"]["cases"][2]["population"] == "control" and record["grant_sha256"]
    result = _run(checkout, released)
    attempt = result["record"]
    assert result["errors"] == []
    assert attempt["process"]["launched"] and attempt["process"]["exit_code"] == 0 and attempt["process"]["signal"] is None
    assert attempt["endpoint"]["preserved"] is True and attempt["endpoint"]["changed"] == []
    assert attempt["endpoint"]["compared"] == 2 and attempt["endpoint"]["baseline_matched_manifest"] is True
    assert attempt["child_receipt"]["state"] == "parsed"
    summary = attempt["ledger"]["summary"]
    assert summary["control"] == {"declared": 1, "reached": 1, "admitted": 1, "refused": 0, "compared": 1, "mismatches": 1}
    assert summary["ordinary"] == {"declared": 3, "reached": 3, "admitted": 2, "refused": 1, "compared": 2, "mismatches": 0}
    assert attempt["ledger"]["unmet"] == [] and attempt["ledger"]["malformed"] == []
    receipt = json.loads((exp.worktree / OUTPUT / "receipt.json").read_text())
    assert receipt["root"] == str(exp.worktree) and receipt["self_reported_mismatches"] == 0
    assert receipt["modules"] == ["_stewart_ledger_v1"]
    assert receipt["ledger_file"] == record["child"]["ledger"]["path"]
    assert (Path(result["path"]) / "stdout.txt").read_text() == "done\n"
    assert (Path(result["path"]) / "RESERVED.json").exists() and (Path(result["path"]) / "ATTEMPT.json").exists()
    with pytest.raises(StewartError) as refused:
        _run(checkout, released)
    assert refused.value.reason == "release_consumed"
    view = status(checkout.ws, "one-question")
    assert view["releases"][0]["consumed"] is True and view["attempts"][0]["resolved"] is True
    assert "run" not in [action["action"] for action in view["next_actions"]]


@pytest.mark.parametrize("change", ["script", "prediction", "manifest", "protected_input", "unrelated"])
def test_changed_frozen_or_protected_state_invalidates_release_and_unrelated_changes_do_not(tmp_path, run_cmd, change):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    released = _release(checkout)
    if change == "script":
        exp.script.write_text(exp.script.read_text() + "\n# edited after release\n")
    elif change == "prediction":
        (exp.worktree / PREDICTION).write_text("revised prediction\n")
    elif change == "manifest":
        (exp.worktree / MANIFEST).write_text("{\"files\": {}}\n")
    elif change == "protected_input":
        (exp.worktree / "input.txt").write_text("protected bytes changed before launch\n")
    else:
        (exp.worktree / "ignored").mkdir()
        (exp.worktree / "ignored" / "cache.bin").write_bytes(b"\x00")
        (exp.worktree / WS / "scratch/one-question/notes.txt").write_text("unfrozen scratch note\n")
    if change == "unrelated":
        result = _run(checkout, released)
        assert result["errors"] == [] and result["record"]["process"]["launched"]
        return
    with pytest.raises(StewartError) as refused:
        _run(checkout, released)
    assert refused.value.reason == "release_invalidated"
    attempt_dir = Path(refused.value.retained[0])
    attempt = read_json(attempt_dir / "ATTEMPT.json")
    assert attempt["process"]["launched"] is False and attempt["errors"]
    assert not (attempt_dir / "stdout.txt").exists(), "nothing ran"
    if change == "protected_input":
        assert attempt["endpoint"]["baseline_matched_manifest"] is False and attempt["endpoint"]["changed"] == ["input.txt"]
    assert not (exp.worktree / OUTPUT).exists(), "the output area stays fresh for a future release"
    view = status(checkout.ws, "one-question")
    assert view["attempts"][0]["resolved"] is True, "a refused launch still resolves its reservation"


def test_explicit_root_binds_the_child_and_an_outside_root_baseline_is_refused(tmp_path, run_cmd):
    deep = f"{WS}/scratch/one-question/deep/er/still/experiment.py"
    checkout = support.experiment_checkout(tmp_path, run_cmd, script=deep,
                                           scratch=[*support.SCRATCH, f"{WS}/scratch/one-question/deep"])
    exp = support.prepared_experiment(checkout)
    released = _release(checkout)
    result = _run(checkout, released)
    assert result["errors"] == []
    receipt = json.loads((exp.worktree / OUTPUT / "receipt.json").read_text())
    assert receipt["root"] == str(exp.worktree) and receipt["script"].endswith("still/experiment.py")
    # An outside-root baseline cannot be released: the manifest names a path that escapes.
    escaping = support.experiment_checkout(tmp_path / "escape", run_cmd)
    (escaping.repo / MANIFEST).write_text(json.dumps({"files": {"../outside.txt": "0" * 64}}) + "\n")
    escaping.git("add", "--", MANIFEST)
    escaping.git("commit", "-qm", "Escaping manifest")
    escaping.meta["target_commit"] = escaping.git("rev-parse", "HEAD")
    escaping.prompt_text = assignment_text(escaping.meta, extra_sections=support.AUTHORIZATION)
    support.prepared_experiment(escaping)
    with pytest.raises(StewartError) as refused:
        _release(escaping)
    assert refused.value.reason == "path_escape"


@pytest.mark.parametrize("variant", ["early_failure", "malformed_receipt", "nonzero_exit", "timeout"])
def test_child_failures_retain_independent_command_evidence(tmp_path, run_cmd, variant):
    kwargs = {
        "early_failure": {"before": 'raise SystemExit("boom before any import")'},
        "malformed_receipt": {"body": '(output / "receipt.json").write_text("{not json"); raise SystemExit(0)'},
        "nonzero_exit": {"body": "raise SystemExit(3)"},
        "timeout": {"body": "time.sleep(60)"},
    }[variant]
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout, **kwargs)
    released = _release(checkout)
    result = _run(checkout, released, timeout=2 if variant == "timeout" else 60)
    attempt = result["record"]
    attempt_dir = Path(result["path"])
    assert result["errors"], "a failed trial is recorded, not refused"
    assert attempt["process"]["launched"] is True
    assert attempt["endpoint"]["preserved"] is True, "the protected state was still compared"
    assert read_json(attempt_dir / "ATTEMPT.json")["errors"] == result["errors"]
    if variant == "early_failure":
        assert attempt["process"]["exit_code"] == 1
        assert "boom before any import" in (attempt_dir / "stderr.txt").read_text()
        assert attempt["child_receipt"]["state"] == "absent"
        assert attempt["ledger"]["rows"] == 0 and attempt["ledger"]["capture"]["kind"] == "missing"
    elif variant == "malformed_receipt":
        assert attempt["process"]["exit_code"] == 0 and attempt["child_receipt"]["state"] == "malformed"
        assert attempt["ledger"]["summary"]["control"]["mismatches"] == 1, "rows stand on their own"
    elif variant == "nonzero_exit":
        assert attempt["process"]["exit_code"] == 3 and attempt["child_receipt"]["state"] == "absent"
        assert attempt["ledger"]["rows"] > 0 and "child exited 3" in result["errors"]
    else:
        assert attempt["process"]["timed_out"] is True and attempt["process"]["signal"] == signal.SIGTERM
        assert attempt["process"]["exit_code"] is None
        assert (attempt_dir / "stdout.txt").exists()


def test_concurrent_consumption_cannot_launch_twice(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    support.prepared_experiment(checkout, body="time.sleep(3)")
    released = _release(checkout)
    outcomes: list = []
    barrier = threading.Barrier(2)

    def attempt():
        barrier.wait()
        try:
            outcomes.append(_run(checkout, released, timeout=10))
        except StewartError as exc:
            outcomes.append(exc)

    workers = [threading.Thread(target=attempt) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(60)
    launched = [o for o in outcomes if isinstance(o, dict)]
    refused = [o for o in outcomes if isinstance(o, StewartError)]
    assert len(launched) == 1 and len(refused) == 1
    assert refused[0].reason == "release_consumed"
    assert launched[0]["record"]["process"]["launched"] and launched[0]["errors"] == []


def test_a_tampering_child_fails_preservation_without_failing_custody(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout, body='(root / "input.txt").write_text("tampered\\n")')
    released = _release(checkout)
    result = _run(checkout, released)
    attempt = result["record"]
    assert attempt["process"]["exit_code"] == 0, "the child reports success"
    assert attempt["endpoint"]["preserved"] is False and attempt["endpoint"]["changed"] == ["input.txt"]
    assert any("protected state changed" in error for error in result["errors"])
    assert attempt["ledger"]["unmet"] == [], "preservation failure is recorded beside, not inside, the measurement"
    assert (exp.worktree / "input.txt").read_text() == "tampered\n", "the wrapper restores nothing"


@pytest.mark.parametrize("variant", ["no_control", "unexpected_admission", "control_never_reached", "liar"])
def test_measurement_prerequisites_derive_from_rows_not_child_claims(tmp_path, run_cmd, variant):
    cases = {
        "no_control": support.DEFAULT_CASES.replace(
            'ledger.declare("c1", population="control", role="planted disagreement", expected_admission=True, prediction="mismatch", measurements=["value"])\n', ""
        ).replace('control = ledger.compare("c1", "value", 1, 2, note="planted")\n', "").replace('ledger.admit("c1", True)\n', "")
        .replace('for case in ("o1", "o2", "c1", "r1"):', 'for case in ("o1", "o2", "r1"):'),
        "unexpected_admission": support.DEFAULT_CASES.replace('ledger.admit("r1", False, reason="declared inadmissible")',
                                                               'ledger.admit("r1", True)'),
        "control_never_reached": support.DEFAULT_CASES.replace('control = ledger.compare("c1", "value", 1, 2, note="planted")\n', "")
        .replace('ledger.admit("c1", True)\n', "").replace('for case in ("o1", "o2", "c1", "r1"):', 'for case in ("o1", "o2", "r1"):'),
        "liar": support.DEFAULT_CASES,
    }[variant]
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    support.prepared_experiment(checkout, cases=cases)
    released = _release(checkout)
    attempt = _run(checkout, released)["record"]
    assert attempt["process"]["exit_code"] == 0
    unmet = attempt["ledger"]["unmet"]
    if variant == "no_control":
        assert any("no control cases were declared" in item for item in unmet)
    elif variant == "unexpected_admission":
        assert any("admission differed from its declaration for: r1" in item for item in unmet)
        assert attempt["ledger"]["anomalies"]["unexpected_admission"] == ["r1"]
    elif variant == "control_never_reached":
        assert any("no control comparison was reached" in item for item in unmet)
        assert attempt["ledger"]["summary"]["control"] == {"declared": 1, "reached": 0, "admitted": 0, "refused": 0,
                                                            "compared": 0, "mismatches": 0}
    else:
        # The child's receipt claims zero mismatches; the rows show the planted control fired.
        assert attempt["child_receipt"]["state"] == "parsed"
        assert attempt["ledger"]["summary"]["control"]["mismatches"] == 1 and unmet == []


def test_construction_only_damaged_supplied_ledger_and_bad_review_refuse_release(tmp_path, run_cmd):
    construction = support.experiment_checkout(tmp_path / "construction", run_cmd, permission="construction")
    support.prepared_experiment(construction)
    with pytest.raises(StewartError) as refused:
        _release(construction)
    assert refused.value.reason == "execution_not_granted"
    old_target = support.experiment_checkout(tmp_path / "noledger", run_cmd)
    prepared = support.prepared_experiment(old_target)
    (Path(prepared.prepared["runtime"]["root"]) / "stewart/ledger.py").unlink()
    with pytest.raises(StewartError) as refused:
        _release(old_target)
    assert refused.value.reason == "runtime_mismatch"
    granted = support.experiment_checkout(tmp_path / "granted", run_cmd)
    support.prepared_experiment(granted)
    for broken in (
        {**support.REVIEW, "cases": []},
        {**support.REVIEW, "admissibility_reasoning": ""},
        {**support.REVIEW, "cases": [dict(support.REVIEW["cases"][0], population="treatment")]},
        {key: value for key, value in support.REVIEW.items() if key != "limits"},
    ):
        with pytest.raises(StewartError) as refused:
            _release(granted, review=broken)
        assert refused.value.reason == "review_schema"
    with pytest.raises(StewartError) as refused:
        _release(granted, actor="")
    assert refused.value.reason == "actor_required"
    with pytest.raises(StewartError) as refused:
        run(granted.ws, "one-question", release="20260101T000000-00000000")
    assert refused.value.reason == "record_missing"
    static = support.make_checkout(tmp_path / "static", run_cmd)
    support.prepared_session(static)
    with pytest.raises(StewartError) as refused:
        _release(static)
    assert refused.value.reason == "no_grant"


def test_cli_release_and_run_distinguish_a_failed_trial_from_failed_custody(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    support.prepared_experiment(checkout, body="raise SystemExit(5)")
    review = tmp_path / "review.json"
    review.write_text(json.dumps(support.REVIEW))
    base = [sys.executable, "-m", "stewart", "--repo", str(checkout.repo), "--workspace", WS, "--json"]
    env = {"PYTHONPATH": str(INSTALLED_LIB)}
    released = run_cmd([*base, "release", "--audit-id", "one-question", "--review", str(review), "--actor", "cli"],
                       cwd=INSTALLED_LIB, env=env)
    assert released.returncode == 0 and released.stderr == ""
    name = json.loads(released.stdout)["result"]["release"]
    ran = run_cmd([*base, "run", "--audit-id", "one-question", "--release", name, "--timeout", "60"], cwd=INSTALLED_LIB, env=env)
    envelope = json.loads(ran.stdout)
    assert ran.returncode == 1 and envelope["ok"] is False and envelope["exit_code"] == 1
    assert envelope["result"]["record"]["process"]["exit_code"] == 5
    assert "child exited 5" in envelope["result"]["errors"]
    again = run_cmd([*base, "run", "--audit-id", "one-question", "--release", name], cwd=INSTALLED_LIB, env=env)
    assert again.returncode == 2 and json.loads(again.stdout)["error"]["reason"] == "release_consumed"
    human = run_cmd([*base[:-1], "status", "--audit-id", "one-question"], cwd=INSTALLED_LIB, env=env, check=True)
    assert "releases: 1; attempts: 1" in human.stdout


@pytest.mark.parametrize("change", ["input", "manifest", "both", "supplemental", "unrelated"])
def test_release_checks_preparation_pins_before_accepting_a_baseline(tmp_path, run_cmd, change):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    if change == "supplemental":
        sample = checkout.repo / "ignored/sample.txt"
        sample.parent.mkdir()
        sample.write_text("pinned supplemental")
        checkout.meta["supplemental_inputs"] = [
            {"path": "ignored/sample.txt", "sha256": _hash.sha256_bytes((sample).read_bytes()), "provenance": "selected specimen"}]
        checkout.prompt_text = assignment_text(checkout.meta, extra_sections=support.AUTHORIZATION)
    exp = support.prepared_experiment(checkout)
    if change in ("input", "both"):
        (exp.worktree / "input.txt").write_text("replacement baseline")
    if change in ("manifest", "both"):
        manifest = read_json(exp.worktree / MANIFEST)
        manifest["files"]["input.txt"] = _hash.sha256_bytes((exp.worktree / "input.txt").read_bytes())
        (exp.worktree / MANIFEST).write_text(json.dumps(manifest))
    if change == "supplemental":
        (exp.worktree / "ignored/sample.txt").write_text("changed supplemental")
    if change == "unrelated":
        (exp.worktree / PREDICTION).write_text("a prediction constructed before release")
        assert _run(checkout, _release(checkout))["errors"] == []
    else:
        with pytest.raises(StewartError) as refused:
            _release(checkout)
        assert refused.value.reason == "pinned_input_changed"
        assert not list((exp.session / "releases").glob("*.json")), "no release may bless a replacement pinned baseline"
        assert list((exp.session / "releases").glob("runtime-*/capture.json")), "preserve the preceding runtime observation"


@pytest.mark.parametrize("output", ["ledger", "receipt"])
def test_special_child_output_finishes_custody_without_blocking(tmp_path, run_cmd, output):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    victim = 'ledger.path' if output == "ledger" else '(output / "receipt.json")'
    # Exit ourselves so the fixture's normal receipt writer cannot block on its FIFO.
    body = f'import os\nif {victim}.exists():\n    {victim}.unlink()\nos.mkfifo({victim})\nprint("child finished", flush=True)\nraise SystemExit(0)'
    exp = support.prepared_experiment(checkout, body=body)
    released = _release(checkout)
    base = [sys.executable, "-B", "-m", "stewart", "--repo", str(checkout.repo), "--workspace", WS, "--json"]
    result = run_cmd([*base, "run", "--audit-id", "one-question", "--release", released["release"], "--timeout", "0.5"],
                     cwd=INSTALLED_LIB, env={"PYTHONPATH": str(INSTALLED_LIB)}, timeout=10)
    assert result.returncode == 1, result.stderr
    record = json.loads(result.stdout)["result"]["record"]
    attempt = exp.session / "attempts" / released["release"]
    assert (attempt / "ATTEMPT.json").exists(), "a special output must not leave an unresolved reservation"
    assert record["process"]["exit_code"] == 0 and not record["process"]["timed_out"]
    assert (attempt / "stdout.txt").read_text() == "child finished\n"
    if output == "ledger":
        assert record["ledger"]["capture"]["retained"] is None and record["ledger"]["unmet"]
    else:
        assert record["child_receipt"]["state"] == "unsupported"
        assert record["ledger"]["summary"]["control"]["mismatches"] == 1


def test_attempt_retains_the_exact_rows_and_receipt_it_parsed(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    result = _run(checkout, _release(checkout))
    record = result["record"]
    for key, name in (("ledger", "ledger.jsonl"), ("child_receipt", "receipt.json")):
        original = (exp.worktree / OUTPUT / name).read_bytes()
        captured = record[key]["capture"]
        assert Path(captured["retained"]).read_bytes() == original
        assert captured["sha256"] == _hash.sha256_bytes(original)
        (exp.worktree / OUTPUT / name).write_text("changed after attempt")
        assert Path(captured["retained"]).read_bytes() == original, "later output changes cannot replace attempt evidence"
    assert record["ledger"]["unmet"] == []


def test_attempt_reconciles_rows_against_the_release_review(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    body = '''rows = [json.loads(line) for line in ledger.path.read_text().splitlines()]
rows = [row for row in rows if row["case"] != "o2"]
for row in rows:
    if row["kind"] == "compare":
        row["actual"] = row["expected"] if row["case"] == "c1" else 2
ledger.path.write_text("".join(json.dumps(row) + "\\n" for row in rows))'''
    support.prepared_experiment(checkout, body=body)
    result = _run(checkout, _release(checkout))
    ledger = result["record"]["ledger"]
    assert ledger["summary"]["ordinary"]["mismatches"] == 1
    assert ledger["summary"]["control"]["mismatches"] == 0
    assert ledger["anomalies"]["missing_declarations"] == ["o2"]
    assert ledger["anomalies"]["inconsistent_comparisons"] == ["c1", "o1"]
    assert ledger["unmet"], "a successful child exit cannot satisfy missing or contradictory measurement evidence"


def test_release_measurement_membership_survives_self_authored_ledger_omission(tmp_path, run_cmd):
    """The release requires a second mode even if the child drops it from its declaration."""
    from copy import deepcopy

    checkout = support.experiment_checkout(tmp_path, run_cmd)
    support.prepared_experiment(checkout)
    review = deepcopy(support.REVIEW)
    review['cases'][0]['measurements'] = ['value', 'strict']
    released = _release(checkout, review=review)
    result = _run(checkout, released)
    assert result['errors'] == [], 'a successful custody operation need not meet measurement prerequisites'
    record = result['record']['ledger']
    assert record['anomalies']['missing_measurements'] == [{'case': 'o1', 'measurement': 'strict'}]
    assert record['unmet'] and record['summary']['control']['mismatches'] == 1


def test_release_refuses_missing_or_ambiguous_measurement_ids(tmp_path, run_cmd):
    from copy import deepcopy

    checkout = support.experiment_checkout(tmp_path, run_cmd)
    support.prepared_experiment(checkout)
    for bad in (None, [], ['value', 'value'], [''], [1]):
        review = deepcopy(support.REVIEW)
        review['cases'][0]['measurements'] = bad
        with pytest.raises(StewartError) as refused:
            _release(checkout, review=review)
        assert refused.value.reason == 'review_schema'
    review = deepcopy(support.REVIEW)
    del review['cases'][0]['measurements']
    with pytest.raises(StewartError) as refused:
        _release(checkout, review=review)
    assert refused.value.reason == 'review_schema'
