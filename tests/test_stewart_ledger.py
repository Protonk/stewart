"""The comparison ledger: one shared recorder, populations kept apart, summaries from rows alone.

The pairs here distinguish the measured property from nearby properties:
a case that changes only the measured property fires, a case that changes only
ignored metadata does not, and a planned refusal is neither.
"""

from __future__ import annotations

from pathlib import Path

import json

import pytest

from stewart.ledger import Ledger, parse_rows, prerequisites, summarize


def _ledger(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path / "run" / "ledger.jsonl")


def _declare_default(ledger: Ledger) -> None:
    ledger.declare("o1", population="ordinary", role="measured property varies", expected_admission=True, prediction="agree", measurements=["value"])
    ledger.declare("o2", population="ordinary", role="ignored metadata varies", expected_admission=True, prediction="agree", measurements=["value"])
    ledger.declare("c1", population="control", role="planted disagreement", expected_admission=True, prediction="mismatch", measurements=["value"])
    ledger.declare("r1", population="ordinary", role="planned refusal", expected_admission=False, prediction="refused", measurements=[])


def test_one_recorder_counts_ordinary_and_control_rows_separately(tmp_path):
    ledger = _ledger(tmp_path)
    _declare_default(ledger)
    for case in ("o1", "o2", "c1", "r1"):
        ledger.reach(case)
    ledger.admit("o1", True)
    ledger.admit("o2", True)
    ledger.admit("c1", True)
    ledger.admit("r1", False, reason="declared inadmissible")
    assert ledger.compare("o1", "value", {"leaf": "a"}, {"leaf": "a"}) is False
    # Pair: only ignored metadata differs (the note), the compared values are identical.
    assert ledger.compare("o2", "value", {"leaf": "a"}, {"leaf": "a"}, note="different specimen encoding") is False
    # Pair: only the measured property differs, through the same operation the ordinary rows use.
    assert ledger.compare("c1", "value", {"leaf": "a"}, {"leaf": "b"}, note="planted") is True
    rows, problems = parse_rows(ledger.path.read_bytes())
    assert problems == [] and len(rows) == 4 + 4 + 4 + 3
    summary = summarize(rows)
    assert summary["populations"]["ordinary"] == {"declared": 3, "reached": 3, "admitted": 2, "refused": 1,
                                                  "compared": 2, "mismatches": 0}
    assert summary["populations"]["control"] == {"declared": 1, "reached": 1, "admitted": 1, "refused": 0,
                                                 "compared": 1, "mismatches": 1}
    assert summary["mismatching_cases"] == {"ordinary": [], "control": ["c1"]}
    assert summary["unexpected_admission"] == [] and summary["compared_without_admission"] == []
    assert prerequisites(summary) == []


def test_a_planned_refusal_is_not_a_mismatch_and_an_unexpected_admission_is_flagged(tmp_path):
    ledger = _ledger(tmp_path)
    _declare_default(ledger)
    ledger.reach("r1")
    ledger.admit("r1", False, reason="refused as declared")
    summary = summarize(parse_rows(ledger.path.read_bytes())[0])
    assert summary["populations"]["ordinary"]["refused"] == 1
    assert summary["populations"]["ordinary"]["mismatches"] == 0
    assert "r1" not in summary["unexpected_admission"]
    surprise = Ledger(tmp_path / "surprise.jsonl")
    _declare_default(surprise)
    surprise.reach("r1")
    surprise.admit("r1", True)
    surprise.reach("o1")
    surprise.admit("o1", False, reason="unexpectedly refused")
    summary = summarize(parse_rows(surprise.path.read_bytes())[0])
    assert summary["unexpected_admission"] == ["o1", "r1"]
    assert any("admission differed from its declaration for: o1, r1" in item for item in prerequisites(summary))


@pytest.mark.parametrize("shape", ["empty", "no_control", "control_unreached", "control_agrees", "undeclared", "unadmitted"])
def test_prerequisites_stay_unmet_until_the_rows_support_them(tmp_path, shape):
    ledger = _ledger(tmp_path)
    if shape != "empty":
        ledger.declare("o1", population="ordinary", role="x", expected_admission=True, prediction="agree", measurements=["value"])
        ledger.reach("o1")
        ledger.admit("o1", True)
        ledger.compare("o1", "value", 1, 1)
    if shape in ("control_unreached", "control_agrees", "undeclared", "unadmitted"):
        ledger.declare("c1", population="control", role="planted", expected_admission=True, prediction="mismatch", measurements=["value"])
    if shape == "control_agrees":
        ledger.reach("c1")
        ledger.admit("c1", True)
        ledger.compare("c1", "value", 1, 1)
    if shape == "undeclared":
        ledger.reach("c1")
        ledger.admit("c1", True)
        ledger.compare("c1", "value", 1, 2)
        ledger.compare("ghost", "value", 1, 2)
    if shape == "unadmitted":
        ledger.reach("c1")
        ledger.compare("c1", "value", 1, 2)
    unmet = prerequisites(summarize(parse_rows(ledger.path.read_bytes())[0]))
    expectation = {
        "empty": ("no ordinary cases were declared", "no control cases were declared"),
        "no_control": ("no control cases were declared",),
        "control_unreached": ("no control comparison was reached and recorded",),
        "control_agrees": ("no control produced a nonzero disagreement",),
        "undeclared": ("rows reference undeclared cases: ghost",),
        "unadmitted": ("comparisons recorded while cases were not admitted: c1",),
    }[shape]
    for fragment in expectation:
        assert any(fragment in item for item in unmet), (shape, unmet)
    if shape == "undeclared":
        assert not any("no control produced" in item for item in unmet), "the declared control did fire"


def test_summaries_come_from_rows_and_malformed_lines_are_reported(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.declare("c1", population="control", role="planted", expected_admission=True, prediction="mismatch", measurements=["value", "second"])
    ledger.reach("c1")
    ledger.admit("c1", True)
    ledger.compare("c1", "value", "x", "y")
    with ledger.path.open("a", encoding="utf-8") as stream:
        stream.write('{"kind": "compare", "case": "c1", "measurement": "second", "expected": 1, "actual": 1, "mismatch": false}\n')
        stream.write("not json at all\n")
        stream.write('{"kind": "summary", "mismatches": 0}\n')
        stream.write('{"kind": "compare"}\n')
    rows, problems = parse_rows(ledger.path.read_bytes())
    assert [problem["line"] for problem in problems] == [6, 7, 8]
    summary = summarize(rows)
    assert summary["populations"]["control"]["compared"] == 2 and summary["populations"]["control"]["mismatches"] == 1
    assert parse_rows(b"\xff")[1][0]["line"] == 0, "invalid UTF-8 remains a parsing gap"


def test_rows_file_is_created_exclusively_and_populations_are_closed(tmp_path):
    ledger = _ledger(tmp_path)
    with pytest.raises(FileExistsError):
        Ledger(ledger.path)
    with pytest.raises(ValueError, match="population"):
        ledger.declare("t1", population="treatment", role="x", expected_admission=True, prediction="y", measurements=["value"])


def _witness_rows():
    """Authored rows independent of Ledger.compare, paired with reviewed declarations."""
    cases = [
        {"id": "ordinary", "population": "ordinary", "role": "value", "expected_admission": True, "prediction": "agree", "measurements": ["value"]},
        {"id": "ignored", "population": "ordinary", "role": "metadata", "expected_admission": True, "prediction": "agree", "measurements": ["value"]},
        {"id": "control", "population": "control", "role": "value", "expected_admission": True, "prediction": "disagree", "measurements": ["value"]},
    ]
    rows = []
    for case in cases:
        ident = case["id"]
        rows.extend([
            {"kind": "declare", "case": ident, **{key: value for key, value in case.items() if key != "id"}},
            {"kind": "reach", "case": ident}, {"kind": "admit", "case": ident, "admitted": True},
            {"kind": "compare", "case": ident, "measurement": "value", "expected": 1, "actual": 2 if ident == "control" else 1,
             "mismatch": ident == "control", "note": "ignored metadata"},
        ])
    return rows, cases


def test_verifier_reads_operands_and_ignores_notes_instead_of_trusting_flags():
    rows, cases = _witness_rows()
    baseline = summarize(rows, cases=cases)
    assert prerequisites(baseline) == []
    for row in rows:
        if row["kind"] == "compare":
            row["note"] = "changed metadata only"
    assert summarize(rows, cases=cases) == baseline, "notes must not change measured comparisons"
    for row in rows:
        if row["kind"] == "compare":
            row["actual"] = row["expected"] if row["case"] == "control" else 2
    actual = summarize(rows, cases=cases)
    assert actual["populations"]["ordinary"]["mismatches"] == 2
    assert actual["populations"]["control"]["mismatches"] == 0
    assert actual["inconsistent_comparisons"] == ["control", "ignored", "ordinary"]
    assert any("no control produced" in item for item in prerequisites(actual))


@pytest.mark.parametrize("mutation", ["omit", "relabel", "duplicate", "unreached", "unadmitted", "uncompared", "unreviewed"])
def test_reviewed_cases_cannot_disappear_or_redeclare_their_own_authority(mutation):
    rows, cases = _witness_rows()
    assert prerequisites(summarize(rows, cases=cases)) == []
    if mutation == "omit":
        rows = [row for row in rows if row["case"] != "ignored"]
    elif mutation == "relabel":
        rows[4]["population"] = "control"
    elif mutation == "duplicate":
        rows.insert(1, dict(rows[0], population="control"))
    elif mutation == "unreviewed":
        cases = cases[:1] + cases[2:]
    else:
        kind = {"unreached": "reach", "unadmitted": "admit", "uncompared": "compare"}[mutation]
        rows = [row for row in rows if (row["case"], row["kind"]) != ("ignored", kind)]
    measured = summarize(rows, cases=cases)
    assert prerequisites(measured), f"{mutation} must not be hidden by another ordinary case and a firing control"
    field = {"omit": "missing_declarations", "relabel": "declaration_conflicts", "duplicate": "sequence_problems",
             "unreached": "unreached", "unadmitted": "unresolved_admission", "uncompared": "uncompared",
             "unreviewed": "unreviewed_cases"}[mutation]
    assert measured[field], f"the specific defect must be visible under {field}"


@pytest.mark.parametrize("edit", [
    {"admitted": "false"}, {"case": []}, {"kind": "compare", "expected": 1, "mismatch": False},
    {"kind": "compare", "expected": float("nan"), "actual": 1, "mismatch": True},
])
def test_malformed_fields_never_turn_into_measurements(edit):
    row = {"kind": "admit", "case": "ordinary", "admitted": True, **edit}
    rows, problems = parse_rows((json.dumps(row) + "\n").encode())
    assert rows == [] and problems[0]["line"] == 1
    assert summarize([row])["malformed_rows"], "direct callers get the same validation as parsed rows"


def test_json_comparison_semantics_survive_serialization(tmp_path):
    ledger = _ledger(tmp_path)
    assert ledger.compare("bool", "value", True, 1) is True, "booleans and numbers have different JSON types"
    assert ledger.compare("number", "value", 1, 1.0) is False, "JSON numbers compare numerically"
    assert ledger.compare("object", "value", {"a": 1, "b": 2}, {"b": 2, "a": 1}) is False
    assert ledger.compare("array", "value", [1, 2], [2, 1]) is True
    rows, problems = parse_rows(ledger.path.read_bytes())
    assert problems == [] and summarize(rows)["inconsistent_comparisons"] == []
    with pytest.raises(ValueError, match="JSON values"):
        ledger.compare("tuple", "value", (1, 2), [1, 2])


def _two_mode_rows():
    """Independent row fixture: both modes are mandatory even when one control fires."""
    rows, cases = _witness_rows()
    for case in cases:
        case['measurements'] = ['canonical', 'strict']
    expanded = []
    for row in rows:
        if row['kind'] == 'declare':
            row = dict(row, measurements=['canonical', 'strict'])
        if row['kind'] == 'compare':
            expanded.extend(dict(row, measurement=mode) for mode in ('canonical', 'strict'))
        else:
            expanded.append(row)
    return expanded, cases


@pytest.mark.parametrize('mutation', ['omit_mode', 'duplicate', 'substitute', 'extra', 'self_authorize'])
def test_reviewed_measurement_membership_cannot_be_replaced_by_a_firing_control(mutation):
    rows, cases = _two_mode_rows()
    assert prerequisites(summarize(rows, cases=cases)) == []
    if mutation == 'omit_mode':
        rows = [r for r in rows if r.get('measurement') != 'strict']
    elif mutation == 'self_authorize':
        rows = [r for r in rows if r.get('measurement') != 'strict']
        rows = [dict(r, measurements=['canonical']) if r['kind'] == 'declare' else r for r in rows]
    elif mutation == 'duplicate':
        rows.append(dict(rows[-1]))
    elif mutation == 'substitute':
        # Same row count and operands; only a measurement identity changes.
        rows[-1] = dict(rows[-1], measurement='canonical')
    else:
        rows.append(dict(rows[-1], measurement='unreviewed'))
    actual = summarize(rows, cases=cases)
    assert prerequisites(actual), 'Every case and a firing control are insufficient when measurements disappear'
    field = {'omit_mode': 'missing_measurements', 'duplicate': 'duplicate_measurements',
             'substitute': 'missing_measurements', 'extra': 'unexpected_measurements',
             'self_authorize': 'declaration_conflicts'}[mutation]
    assert actual[field], f'{mutation} must name the actual measurement defect'
    if mutation == 'omit_mode':
        assert actual['populations']['control']['mismatches'] == 1, 'a control still fires in the surviving mode'
        assert actual['missing_measurements'] == [
            {'case': c, 'measurement': 'strict'} for c in ('control', 'ignored', 'ordinary')]


def test_measurement_identity_ignores_notes_and_declaration_order():
    rows, cases = _two_mode_rows()
    before = summarize(rows, cases=cases)
    for row in rows:
        if row['kind'] == 'declare':
            row['measurements'] = list(reversed(row['measurements']))
        if row['kind'] == 'compare':
            row['note'] = 'different incidental prose'
    assert summarize(rows, cases=cases) == before, 'membership is a set; prose does not define measurements'


@pytest.mark.parametrize('measurements', [None, [], ['x', 'x'], [''], [1]])
def test_admitted_declaration_requires_unique_measurement_ids(tmp_path, measurements):
    ledger = _ledger(tmp_path)
    with pytest.raises(ValueError, match='measurement'):
        ledger.declare('o', population='ordinary', role='value', expected_admission=True,
                       prediction='agree', measurements=measurements)
