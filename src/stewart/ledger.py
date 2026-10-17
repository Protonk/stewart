"""Standard-library-only comparison recorder and verifier for captured JSONL.

The recorder and verifier compare JSON values: object key order is ignored,
array order matters, booleans differ from numbers, and finite JSON numbers
compare numerically. Other Python types and nonfinite numbers are refused.
The wrapper parses captured bytes, recomputes disagreements, and reconciles
case events against the frozen review. None of this establishes the truth of
child-supplied operands, control relevance, or reference independence.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

POPULATIONS = ("ordinary", "control")
KINDS = ("declare", "reach", "admit", "compare")
DECLARATION_FIELDS = ("population", "role", "expected_admission", "prediction", "measurements")


def measurement_problem(measurements: object, expected_admission: bool) -> str | None:
    """Validate the declared measurement set; refusals have no comparisons to make."""
    if (not isinstance(measurements, list)
            or not all(isinstance(item, str) and item.strip() for item in measurements)
            or len(set(measurements)) != len(measurements)):
        return "measurements must be a list of unique nonempty IDs"
    if bool(measurements) != expected_admission:
        return "admitted cases need measurement IDs; planned refusals need an empty measurement list"
    return None


def _comparison_key(value):
    """Type-aware JSON equality, identical before serialization and after parsing."""
    if value is None:
        return ("null",)
    if type(value) is bool:
        return ("boolean", value)
    if type(value) in (int, float):
        if type(value) is float and not math.isfinite(value):
            raise ValueError("comparison numbers must be finite")
        return ("number", value)
    if type(value) is str:
        return ("string", value)
    if type(value) is list:
        return ("array", tuple(_comparison_key(item) for item in value))
    if type(value) is dict and all(type(key) is str for key in value):
        return ("object", tuple((key, _comparison_key(value[key])) for key in sorted(value)))
    raise ValueError("comparison operands must be JSON values with string object keys")


def _row_problem(row: object) -> str | None:
    if not isinstance(row, dict) or row.get("kind") not in KINDS:
        return "not a ledger row"
    if not isinstance(row.get("case"), str) or not row["case"].strip():
        return "case must be a nonempty string"
    kind = row["kind"]
    required = {"kind", "case"}
    optional: set[str] = set()
    if kind == "declare":
        required.update(DECLARATION_FIELDS)
        if row.get("population") not in POPULATIONS or type(row.get("expected_admission")) is not bool:
            return "declaration needs a known population and boolean expected_admission"
        if any(not isinstance(row.get(key), str) or not row[key].strip() for key in ("role", "prediction")):
            return "declaration needs nonempty role and prediction"
        problem = measurement_problem(row.get("measurements"), row["expected_admission"])
        if problem:
            return problem
    elif kind == "admit":
        required.add("admitted")
        optional.add("reason")
        if type(row.get("admitted")) is not bool:
            return "admitted must be boolean"
    elif kind == "compare":
        required.update(("measurement", "expected", "actual", "mismatch"))
        optional.add("note")
        if not isinstance(row.get("measurement"), str) or not row["measurement"].strip():
            return "comparison needs a nonempty measurement ID"
        if type(row.get("mismatch")) is not bool:
            return "mismatch must be boolean"
        try:
            _comparison_key(row.get("expected"))
            _comparison_key(row.get("actual"))
        except ValueError as exc:
            return str(exc)
    if not required <= set(row) or set(row) - required - optional:
        return "missing or unknown row fields"
    if any(not isinstance(row[key], str) for key in optional if key in row):
        return "note/reason must be text"
    return None


class Ledger:
    """Append validated JSONL rows to an exclusively created attempt file.

    The recorder does not grant authority to its own declarations. The wrapper
    checks them against the review and validates event order after capture.
    """

    def __init__(self, rows_path: str | Path) -> None:
        self.path = Path(rows_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("x", encoding="utf-8"):
            pass

    def _append(self, row: dict) -> None:
        problem = _row_problem(row)
        if problem:
            raise ValueError(problem)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")

    def declare(self, case_id: str, *, population: str, role: str, expected_admission: bool,
                prediction: str, measurements: list[str]) -> None:
        """Declare unique measurement IDs for admission, or an empty list for planned refusal."""
        self._append({"kind": "declare", "case": case_id, "population": population, "role": role,
                      "expected_admission": expected_admission, "prediction": prediction,
                      "measurements": measurements})

    def reach(self, case_id: str) -> None:
        self._append({"kind": "reach", "case": case_id})

    def admit(self, case_id: str, admitted: bool, *, reason: str = "") -> None:
        self._append({"kind": "admit", "case": case_id, "admitted": admitted, "reason": reason})

    def compare(self, case_id: str, measurement: str, expected, actual, *, note: str = "") -> bool:
        """Record one named measurement of a case; notes and row order do not define membership."""
        mismatch = _comparison_key(expected) != _comparison_key(actual)
        self._append({"kind": "compare", "case": case_id, "measurement": measurement,
                      "expected": expected, "actual": actual,
                      "mismatch": mismatch, "note": note})
        return mismatch


def parse_rows(data: bytes) -> tuple[list[dict], list[dict]]:
    """Parse captured UTF-8 bytes; no path is opened by this stdlib-only module.

    Invalid lines remain separate problems; callers must keep them alongside
    summarize's result. JSON decoding keeps the last value of a repeated object
    key without reporting a problem. Valid comparisons whose mismatch flags
    contradict their operands are retained for recomputation by summarize.
    """
    rows, problems = [], []
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        return [], [{"line": 0, "problem": f"not UTF-8: {exc}"}]
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            problem = _row_problem(row)
        except (ValueError, RecursionError) as exc:
            problem = f"invalid JSON row: {exc}"
        if problem:
            problems.append({"line": number, "problem": problem})
        else:
            rows.append(row)
    return rows, problems


def summarize(rows: list[dict], *, cases: list[dict] | None = None) -> dict:
    """Recompute counts and anomalies, optionally bound to a validated release review.

    Declarations, reach and admission happen once per case and in that order.
    An admitted case compares each reviewed measurement exactly once. Unadmitted,
    unexpected and duplicate measurements are excluded from counts and reported
    explicitly. The review, not the child, owns the expected measurement set.
    """
    declared, admitted, compared = {}, {}, {}
    reached, undeclared, unadmitted, inconsistent = set(), set(), set(), set()
    sequence, malformed = [], []
    for number, row in enumerate(rows, 1):
        problem = _row_problem(row)
        if problem:
            malformed.append({"row": number, "problem": problem})
            continue
        case, kind = row["case"], row["kind"]
        if kind == "declare":
            if case in declared:
                sequence.append(f"{case}: duplicate declaration")
            else:
                declared[case] = row
            continue
        if case not in declared:
            undeclared.add(case)
        if kind == "reach":
            if case not in declared or case in reached:
                sequence.append(f"{case}: reach requires one prior declaration and cannot repeat")
            else:
                reached.add(case)
        elif kind == "admit":
            if case not in reached or case in admitted:
                sequence.append(f"{case}: admission requires prior reach and cannot repeat")
            else:
                admitted[case] = row["admitted"]
        else:
            mismatch = _comparison_key(row["expected"]) != _comparison_key(row["actual"])
            if mismatch != row["mismatch"]:
                inconsistent.add(case)
            if admitted.get(case) is not True:
                unadmitted.add(case)
            else:
                compared.setdefault(case, {}).setdefault(row["measurement"], []).append(mismatch)
    expected = {row["id"]: row for row in cases} if cases is not None else declared
    conflicts = sorted(case for case in declared if case in expected and any(
        (set(declared[case][field]) != set(expected[case][field]) if field == "measurements"
         else declared[case][field] != expected[case][field]) for field in DECLARATION_FIELDS))
    missing, duplicate, unexpected = [], [], []
    counted = {}
    for case in sorted(set(expected) | set(compared)):
        planned = set(expected[case]["measurements"]) if case in expected else set()
        actual = compared.get(case, {})
        # Refusal is accounted for by admission, not silently reinterpreted as
        # a missing comparison. An unexpected refusal already has its own gap.
        if admitted.get(case) is True:
            missing.extend({"case": case, "measurement": m} for m in sorted(planned - actual.keys()))
        duplicate.extend({"case": case, "measurement": m} for m in sorted(actual) if len(actual[m]) > 1)
        unexpected.extend({"case": case, "measurement": m} for m in sorted(actual.keys() - planned))
        counted[case] = [values[0] for m, values in actual.items() if m in planned and len(values) == 1]
    populations, mismatching = {}, {}
    for population in POPULATIONS:
        selected = [case for case in declared if case in expected and expected[case]["population"] == population]
        comparisons = [value for case in selected for value in counted.get(case, [])]
        populations[population] = {
            "declared": len(selected), "reached": sum(case in reached for case in selected),
            "admitted": sum(admitted.get(case) is True for case in selected),
            "refused": sum(admitted.get(case) is False for case in selected),
            "compared": len(comparisons), "mismatches": sum(comparisons),
        }
        mismatching[population] = sorted(case for case in selected if any(counted.get(case, [])))
    return {
        "populations": populations,
        "mismatching_cases": mismatching,
        "unexpected_admission": sorted(case for case in expected if case in admitted
                                        and admitted[case] != expected[case]["expected_admission"]),
        "compared_without_admission": sorted(unadmitted), "undeclared": sorted(undeclared),
        "inconsistent_comparisons": sorted(inconsistent), "sequence_problems": sequence,
        "malformed_rows": malformed, "declaration_conflicts": conflicts,
        "unreviewed_cases": sorted(set(declared) - set(expected)),
        "missing_declarations": sorted(set(expected) - set(declared)),
        "unreached": sorted(set(expected) - reached),
        "unresolved_admission": sorted(set(expected) - set(admitted)),
        "uncompared": sorted(case for case in expected if admitted.get(case) is True and not compared.get(case)),
        "missing_measurements": missing, "duplicate_measurements": duplicate,
        "unexpected_measurements": unexpected,
    }


def prerequisites(summary: dict) -> list[str]:
    """Mechanical prerequisites; an empty list is necessary, never sufficient.

    At least one counted control comparison must disagree. Individual control
    predictions remain a manager judgment, not a per-case firing requirement.
    """
    unmet = []
    ordinary, control = (summary["populations"][key] for key in POPULATIONS)
    if ordinary["declared"] == 0:
        unmet.append("no ordinary cases were declared")
    elif ordinary["compared"] == 0:
        unmet.append("no ordinary comparison was recorded")
    if control["declared"] == 0:
        unmet.append("no control cases were declared")
    elif control["compared"] == 0:
        unmet.append("no control comparison was reached and recorded")
    elif control["mismatches"] == 0:
        unmet.append("no control produced a nonzero disagreement; the instrument was not observed to fire")
    labels = {
        "unexpected_admission": "admission differed from its declaration for",
        "compared_without_admission": "comparisons recorded while cases were not admitted",
        "undeclared": "rows reference undeclared cases",
        "inconsistent_comparisons": "mismatch flags contradict recorded operands for",
        "declaration_conflicts": "declarations differ from the released review for",
        "unreviewed_cases": "cases absent from the released review",
        "missing_declarations": "reviewed cases missing declarations",
        "unreached": "cases never reached", "unresolved_admission": "cases without an admission outcome",
        "uncompared": "admitted cases without comparisons",
    }
    for key, label in labels.items():
        if summary[key]:
            unmet.append(label + ": " + ", ".join(summary[key]))
    unmet.extend(summary["sequence_problems"])
    for key in ("missing_measurements", "duplicate_measurements", "unexpected_measurements"):
        if summary[key]:
            unmet.append(key.replace("_", " ") + ": " + ", ".join(
                f"{item['case']}:{item['measurement']}" for item in summary[key]))
    if summary["malformed_rows"]:
        unmet.append(f"{len(summary['malformed_rows'])} malformed row(s)")
    return unmet
