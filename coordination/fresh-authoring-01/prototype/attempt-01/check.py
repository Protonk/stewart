#!/usr/bin/env python3
"""Independent black-box prototype checks; preserves inputs before each process."""

import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def write_receipt(path, data):
    with path.open("xb") as stream:
        stream.write(data)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def identity(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, help="Fresh evidence directory; all witnesses and outputs remain retained.")
    args = parser.parse_args()
    evidence = Path(args.evidence).absolute()
    evidence.mkdir()
    helper = Path(__file__).absolute().with_name("submit.py")
    for source in (helper, Path(__file__).absolute()):
        write_receipt(evidence / source.name, source.read_bytes())
    checks, commands = [], []

    def check(name, condition, detail=None):
        checks.append({"check": name, "passed": bool(condition), "detail": detail})

    def invoke(name, raw, reason="structure_accepted", destination=None):
        case = evidence / name
        case.mkdir()
        # This witness is outside the helper destination and exists before launch.
        write_receipt(case / "input.raw", raw)
        dest = destination if destination is not None else case / "submission"
        command = ["/usr/bin/python3", "-I", "-B", str(helper), "--destination", str(dest), "--question-id", "q1", "--source-revision", "r1"]
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_receipt(case / "COMMAND.json", encoded({"argv": command, "cwd": str(evidence), "witness_saved_before_launch": True, "started_utc": started}))
        process = subprocess.run(command, input=raw, capture_output=True, cwd=evidence)
        write_receipt(case / "stdout.raw", process.stdout)
        write_receipt(case / "stderr.raw", process.stderr)
        command_record = {"case": name, "argv": command, "exit_code": process.returncode, "started_utc": started,
                          "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        write_receipt(case / "PROCESS.json", encoded(command_record))
        commands.append(command_record)
        try:
            result = json.loads(process.stdout)
        except (ValueError, UnicodeDecodeError):
            result = {}
        check(name + ":reason", result.get("reason") == reason, result.get("reason"))
        check(name + ":exit", process.returncode == (0 if reason == "structure_accepted" else 2), process.returncode)
        check(name + ":stderr", process.stderr == b"")
        if destination is None:
            check(name + ":raw_preserved", (dest / "attempt.raw").read_bytes() == raw)
            check(name + ":witness_preserved", (case / "input.raw").read_bytes() == raw)
            record = "ACCEPTED.json" if reason == "structure_accepted" else "FAILURE.json"
            check(name + ":record_matches_stdout", json.loads((dest / record).read_bytes()) == result)
        return dest, result

    base = {"question_id": "q1", "source_revision": "r1", "author": "unverified author",
            "response_kind": "answer", "completion_claim": "author claims complete",
            "answer": "café \\n\r\nlast\n", "support": [
                {"id": "fixture", "role": "arbitrary specimen", "encoding": "utf-8", "text": "snowman ☃\npath\\n\r\n\n"},
                {"id": "code", "role": "unrequired role", "encoding": "utf-8", "text": 'print("hi")\r\n'}]}
    raw = encoded(base) + b"\r\n"
    exact_dest, _ = invoke("01-exact-bytes", raw)
    exact = json.loads((exact_dest / "SNAPSHOT.json").read_bytes())
    obs = exact["byte_observations"]
    expected_answer = b"caf\xc3\xa9 \\n\r\nlast\n"
    expected_support = {"fixture": b"snowman \xe2\x98\x83\npath\\n\r\n\n", "code": b'print("hi")\r\n'}
    check("exact:answer_bytes", exact["envelope"]["answer"].encode("utf-8") == expected_answer)
    check("exact:answer_identity", obs["decoded_answer_utf8"] == identity(expected_answer))
    check("exact:raw_identity", obs["raw_transport"] == identity(raw))
    for item in exact["envelope"]["support"]:
        check("exact:support_bytes:" + item["id"], item["text"].encode("utf-8") == expected_support[item["id"]])
    expected_ids = [dict(id=key, **identity(value)) for key, value in expected_support.items()]
    check("exact:support_identities", obs["decoded_support_text_utf8_in_submission_order"] == expected_ids)
    check("exact:decoded_total", obs["decoded_answer_and_support_utf8_bytes"] == len(expected_answer) + sum(map(len, expected_support.values())))
    check("exact:structural_only", exact["intellectual_assessment"] == "not_performed")

    changed = copy.deepcopy(base)
    changed["support"][0]["text"] += "!"
    changed_dest, _ = invoke("02-changed-support", encoded(changed))
    changed_ids = json.loads((changed_dest / "SNAPSHOT.json").read_bytes())["byte_observations"]["decoded_support_text_utf8_in_submission_order"]
    check("change:firing_digest", changed_ids[0]["sha256"] != expected_ids[0]["sha256"])
    check("change:unmodified_control", changed_ids[1] == expected_ids[1])

    reordered = copy.deepcopy(base)
    reordered["support"].reverse()
    reordered_dest, _ = invoke("03-reordered-support", encoded(reordered))
    reordered_ids = json.loads((reordered_dest / "SNAPSHOT.json").read_bytes())["byte_observations"]["decoded_support_text_utf8_in_submission_order"]
    check("order:preserved_order", [item["id"] for item in reordered_ids] == ["code", "fixture"])
    check("order:invariant_by_id", {item["id"]: item for item in reordered_ids} == {item["id"]: item for item in expected_ids})

    escaped_raw = json.dumps(base, ensure_ascii=True, indent=2).encode("ascii")
    escaped_dest, _ = invoke("04-escaped-transport", escaped_raw)
    escaped = json.loads((escaped_dest / "SNAPSHOT.json").read_bytes())
    check("escaping:decoded_invariant", escaped["envelope"] == exact["envelope"])
    check("escaping:raw_digest_differs", escaped["byte_observations"]["raw_transport"] != obs["raw_transport"])

    simple = copy.deepcopy(base)
    simple["answer"], simple["support"] = "", []
    empty_dest, _ = invoke("05-empty-answer", encoded(simple))
    check("empty:zero_answer_bytes", json.loads((empty_dest / "SNAPSHOT.json").read_bytes())["byte_observations"]["decoded_answer_utf8"] == identity(b""))
    for kind in ("needs-evidence", "reframe"):
        value = dict(simple, response_kind=kind)
        invoke("06-" + kind, encoded(value))

    size_base = encoded(simple)
    exact_cap = size_base + b" " * (1048576 - len(size_base))
    invoke("07-exact-size", exact_cap)
    over_dest, _ = invoke("08-over-size", exact_cap + b" ", "raw_size_exceeded")
    check("size:full_overlimit_witness", (over_dest / "attempt.raw").stat().st_size == 1048577)
    check("size:no_snapshot_after_rejection", not (over_dest / "SNAPSHOT.json").exists())

    count_value = dict(simple, support=[{"id": str(i), "role": "", "encoding": "utf-8", "text": ""} for i in range(32)])
    invoke("09-exact-count", encoded(count_value))
    count_value["support"].append({"id": "32", "role": "", "encoding": "utf-8", "text": ""})
    invoke("10-over-count", encoded(count_value), "support_count_exceeded")

    base_raw = encoded(simple)
    invoke("11-duplicate-top", base_raw.replace(b'"question_id":"q1"', b'"question_id":"q1","question_id":"q1"'), "duplicate_json_key")
    invoke("12-duplicate-escaped", base_raw.replace(b'"question_id":"q1"', b'"question_id":"q1","question_\\u0069d":"q1"'), "duplicate_json_key")
    invoke("13-duplicate-nested", encoded(base).replace(b'"encoding":"utf-8"', b'"encoding":"utf-8","encoding":"utf-8"', 1), "duplicate_json_key")
    duplicate_ids = copy.deepcopy(base)
    duplicate_ids["support"][1]["id"] = "fixture"
    invoke("14-duplicate-ids", encoded(duplicate_ids), "duplicate_support_id")
    invoke("15-question-mismatch", encoded(dict(simple, question_id="different")), "identity_mismatch")
    invoke("16-revision-mismatch", encoded(dict(simple, source_revision="different")), "identity_mismatch")
    invoke("17-invalid-utf8", base_raw + b"\xff", "invalid_utf8")
    for index, token in enumerate((b"NaN", b"Infinity", b"-Infinity", b"1e9999"), 18):
        invoke(str(index) + "-nonfinite", base_raw.replace(b'"answer":""', b'"answer":' + token), "nonfinite_json_number")
    invoke("22-unpaired-surrogate", base_raw.replace(b'"answer":""', b'"answer":"\\ud800"'), "invalid_unicode_text")
    invoke("23-malformed-json", base_raw[:-3], "malformed_json")
    invoke("24-malformed-field", encoded(dict(simple, answer=42)), "malformed_field")
    invoke("25-unsupported-kind", encoded(dict(simple, response_kind="finding-required")), "malformed_field")
    unsupported = copy.deepcopy(base)
    unsupported["support"][0]["encoding"] = "base64"
    invoke("26-unsupported-encoding", encoded(unsupported), "unsupported_encoding")
    invoke("27-extra-payload-destination", encoded(dict(simple, destination="/does/not/exist")), "malformed_field")
    label_value = copy.deepcopy(base)
    label_value["support"][0]["id"] = "../../nonexistent.json"
    label_value["support"][0]["text"] = "See /a/never-read/location and https://example.invalid/"
    label_dest, _ = invoke("28-labels-not-paths", encoded(label_value))
    check("labels:no_dereference_or_extra_files", sorted(path.name for path in label_dest.iterdir()) == ["ACCEPTED.json", "SNAPSHOT.json", "attempt.raw"])

    before = {path.name: path.read_bytes() for path in exact_dest.iterdir()}
    invoke("29-reuse-accepted", encoded(simple), "destination_exists", destination=exact_dest)
    check("reuse:accepted_unchanged", before == {path.name: path.read_bytes() for path in exact_dest.iterdir()})
    before_failed = {path.name: path.read_bytes() for path in over_dest.iterdir()}
    invoke("30-reuse-failed", encoded(simple), "destination_exists", destination=over_dest)
    check("reuse:rejected_unchanged", before_failed == {path.name: path.read_bytes() for path in over_dest.iterdir()})

    # Observe an explicitly preexisting partial directory; do not repair it.
    partial = evidence / "preexisting-partial"
    partial.mkdir()
    write_receipt(partial / "attempt.raw", b"partial independent fixture")
    invoke("31-reuse-partial", encoded(simple), "destination_exists", destination=partial)
    check("reuse:partial_unchanged", (partial / "attempt.raw").read_bytes() == b"partial independent fixture" and len(list(partial.iterdir())) == 1)

    result = {"check_count": len(checks), "passed": sum(item["passed"] for item in checks),
              "failed": sum(not item["passed"] for item in checks), "helper_invocations": len(commands),
              "installed_wheel_pytest_nodes": 0, "project_experiment_executions": 0,
              "observer_scope": "Black-box helper subprocess observations; each raw input witness saved outside submission directory before launch; no deletion or crash/durability experiment.",
              "checks": checks, "commands": commands,
              "source_identities": {path.name: identity(path.read_bytes()) for path in (helper, Path(__file__).absolute())}}
    write_receipt(evidence / "RESULT.json", encoded(result))
    print(json.dumps({key: result[key] for key in ("check_count", "passed", "failed", "helper_invocations", "installed_wheel_pytest_nodes", "project_experiment_executions")}, indent=2))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
