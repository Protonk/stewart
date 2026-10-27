#!/usr/bin/env python3
"""Bounded subprocess observations; never imports the helper or Stewart."""

import argparse
import ast
import copy
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys


LIMIT = 1048576
QUESTION = "transport-control-question"
REVISION = "pinned-subject-revision"
PRIMARY = b'Literal \\n and \\u2603; caf\xc3\xa9; \xf0\x9f\x90\x88\r\n\n'
VARIABLE = b'variable: \\t; \xce\xbb\n\n'
CHANGED = b'variable: \\t; \xce\xbb!\n\n'
CONTROL = b'control remains exact\r\n'


def write_receipt(path, data):
    with path.open("xb") as stream:
        stream.write(data)


def encode(value, ascii_only=False):
    return (json.dumps(value, ensure_ascii=ascii_only, allow_nan=False) + "\n").encode("utf-8")


def identity(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def base_payload(form):
    if form == "common":
        return {
            "question_id": QUESTION, "source_revision": REVISION,
            "author": "author-supplied attribution", "response_kind": "needs-evidence",
            "completion_claim": "partial; no inferred completion", "answer": PRIMARY.decode("utf-8"),
            "support": [
                {"id": "../variable", "role": "freely chosen", "encoding": "utf-8", "text": VARIABLE.decode("utf-8")},
                {"id": "control", "role": "", "encoding": "utf-8", "text": CONTROL.decode("utf-8")},
            ],
        }
    return {"text": PRIMARY.decode("utf-8"), "artifacts": [
        {"name": "../variable", "text": VARIABLE.decode("utf-8")},
        {"name": "control", "text": CONTROL.decode("utf-8")},
    ]}


class Checks:
    def __init__(self, root, helper):
        self.root = root
        self.helper = helper
        self.assertions = 0
        self.invocations = []

    def expect(self, condition, message):
        self.assertions += 1
        if not condition:
            raise AssertionError(message)

    def observe(self, form, name, raw, expected_reason=None, expected_payload=None, destination=None):
        case = self.root / (form + "-" + name)
        case.mkdir()
        witness = case / "input.raw"
        write_receipt(witness, raw)
        # Separate expected decoded bytes precede launch and never enter destination.
        expected_items = []
        if expected_payload is not None:
            primary, items, label = ("answer", "support", "id") if form == "common" else ("text", "artifacts", "name")
            write_receipt(case / "expected-primary.utf8", expected_payload[primary].encode("utf-8"))
            for index, item in enumerate(expected_payload[items]):
                data = item["text"].encode("utf-8")
                filename = "expected-artifact-{:02d}.utf8".format(index)
                write_receipt(case / filename, data)
                expected_items.append({"position": index, label: item[label], "witness": filename, **identity(data)})
            write_receipt(case / "EXPECTED.json", encode({"envelope": expected_payload, "artifacts": expected_items}))
        destination = destination or case / "capture"
        argv = [sys.executable, "-I", "-B", "-S", str(self.helper),
                "--form", form, "--question-id", QUESTION, "--source-revision", REVISION,
                "--author-id", "issued-author", "--phase", "phase-control", "--destination", str(destination)]
        command = {"argv": argv, "cwd": str(case), "stdin": str(witness),
                   "input_identity": identity(raw), "witness_saved_before_launch": True,
                   "observer": "check.py parent: saved input and expected bytes before Popen; captured child streams to exclusive files, then inspected destination after exit",
                   "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        write_receipt(case / "COMMAND.json", encode(command))
        with witness.open("rb") as source, (case / "stdout.raw").open("xb") as stdout, (case / "stderr.raw").open("xb") as stderr:
            process = subprocess.Popen(argv, cwd=case, stdin=source, stdout=stdout, stderr=stderr)
            write_receipt(case / "PROCESS.json", encode({"pid": process.pid}))
            code = process.wait()
        result = {"name": form + "-" + name, "pid": process.pid, "exit_code": code,
                  "ended_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        write_receipt(case / "OUTCOME.json", encode(result))
        self.invocations.append(result)
        response = json.loads((case / "stdout.raw").read_bytes())
        self.expect((case / "stderr.raw").read_bytes() == b"", name + " empty stderr")
        self.expect(code == (2 if expected_reason else 0), name + " exit")
        self.expect(response["reason"] == (expected_reason or "structure_accepted"), name + " reason")
        self.expect(response["capture_metadata"] == {
            "form": form, "expected_identity": {"question_id": QUESTION, "source_revision": REVISION},
            "issued_provenance": {"author_id": "issued-author", "phase": "phase-control"},
            "provenance_source": "explicit coordinator CLI arguments; not inferred from submitted text",
        }, name + " independent CLI provenance")
        if expected_reason == "destination_exists":
            self.expect(response["retained_by_this_invocation"] == [], name + " nothing newly retained in reused destination")
            return response, None
        self.expect((destination / "attempt.raw").read_bytes() == witness.read_bytes(), name + " exact raw witness")
        if expected_reason:
            failure = json.loads((destination / "FAILURE.json").read_bytes())
            self.expect(failure == response, name + " failure receipt equals emission")
            self.expect(failure["input_capture_complete"] is True, name + " capture precedes rejection")
            self.expect(failure["raw_transport"] == {"bytes_read": len(raw), "sha256_of_bytes_read": identity(raw)["sha256"]}, name + " rejected raw identity")
            self.expect(not (destination / "SNAPSHOT.json").exists(), name + " no accepted snapshot")
            self.expect(not (destination / "ACCEPTED.json").exists(), name + " no acceptance receipt")
            return response, None
        accepted = json.loads((destination / "ACCEPTED.json").read_bytes())
        snap = json.loads((destination / "SNAPSHOT.json").read_bytes())
        self.expect(accepted == response, name + " acceptance receipt equals emission")
        self.expect(snap["envelope"] == expected_payload, name + " complete payload unchanged")
        self.expect(snap["capture_metadata"] == response["capture_metadata"], name + " snapshot provenance")
        self.expect(snap["intellectual_assessment"] == "not_performed", name + " no judgment")
        observations = snap["byte_observations"]
        self.expect(observations["raw_transport"] == identity(raw), name + " raw identity")
        primary_raw = (case / "expected-primary.utf8").read_bytes()
        self.expect(snap["envelope"][primary].encode("utf-8") == primary_raw, name + " decoded primary bytes")
        self.expect(observations["decoded_primary_text_utf8"] == identity(primary_raw), name + " primary identity")
        expected_observations = [{k: v for k, v in item.items() if k != "witness"} for item in expected_items]
        self.expect(observations["decoded_artifact_text_utf8_in_submission_order"] == expected_observations, name + " ordered artifact identities")
        for index, item in enumerate(expected_items):
            self.expect(snap["envelope"][items][index]["text"].encode("utf-8") == (case / item["witness"]).read_bytes(), name + " decoded artifact " + str(index))
        self.expect(observations["decoded_primary_and_artifact_utf8_bytes"] == len(primary_raw) + sum(item["bytes"] for item in expected_items), name + " decoded total")
        self.expect(not (destination / "FAILURE.json").exists(), name + " no rejection")
        if form == "minimal":
            self.expect(snap["attribution"] == {"payload": "submitted author-selected content"}, name + " no invented author kind/completion/role")
        return response, snap


def run(checks, pinned):
    # Static equality verifies unchanged common validation, including branches
    # outside this bounded subprocess population. It is not runtime coverage.
    old = ast.parse(pinned.read_bytes())
    new = ast.parse(checks.helper.read_bytes())
    original = next(node for node in old.body if isinstance(node, ast.FunctionDef) and node.name == "decode_validate")
    common = next(node for node in new.body if isinstance(node, ast.FunctionDef) and node.name == "validate_common")
    split = next(index for index, node in enumerate(original.body) if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "require_fields")
    checks.expect([ast.dump(n) for n in original.body[split:]] == [ast.dump(n) for n in common.body], "common validator AST unchanged from pinned prototype")
    for form in ("common", "minimal"):
        base = base_payload(form)
        primary, items, label = ("answer", "support", "id") if form == "common" else ("text", "artifacts", "name")
        _, first = checks.observe(form, "baseline", encode(base), expected_payload=base)
        changed = copy.deepcopy(base)
        changed[items][0]["text"] = CHANGED.decode("utf-8")
        _, delta = checks.observe(form, "changed-artifact", encode(changed), expected_payload=changed)
        first_obs = first["byte_observations"]
        delta_obs = delta["byte_observations"]
        checks.expect(first_obs["decoded_artifact_text_utf8_in_submission_order"][0]["sha256"] != delta_obs["decoded_artifact_text_utf8_in_submission_order"][0]["sha256"], form + " changed-artifact firing discriminator")
        checks.expect(first_obs["decoded_artifact_text_utf8_in_submission_order"][1] == delta_obs["decoded_artifact_text_utf8_in_submission_order"][1], form + " unchanged artifact control")
        checks.expect(first_obs["decoded_primary_text_utf8"] == delta_obs["decoded_primary_text_utf8"], form + " primary invariant")
        reordered = copy.deepcopy(base)
        reordered[items].reverse()
        _, order = checks.observe(form, "reordered", encode(reordered), expected_payload=reordered)
        def by_identity(snap):
            return {item[label]: {key: item[key] for key in ("bytes", "sha256")} for item in snap["byte_observations"]["decoded_artifact_text_utf8_in_submission_order"]}
        checks.expect(by_identity(first) == by_identity(order), form + " ordering does not change bytes by identity")
        _, escaped = checks.observe(form, "escaped-json", encode(base, ascii_only=True), expected_payload=base)
        checks.expect(first_obs["raw_transport"] != escaped["byte_observations"]["raw_transport"], form + " alternate transport differs")
        checks.expect(first["envelope"] == escaped["envelope"], form + " alternate transport decoded invariance")
        empty = copy.deepcopy(base)
        empty[primary] = ""
        empty[items] = []
        if form == "common":
            empty.update(author="", completion_claim="", response_kind="answer")
        checks.observe(form, "empty-text-artifacts", encode(empty), expected_payload=empty)
        boundary = copy.deepcopy(empty)
        template = base[items][0]
        boundary[items] = [dict(template, **{label: str(i)}) for i in range(32)]
        checks.observe(form, "32-artifacts", encode(boundary), expected_payload=boundary)
        boundary[items].append(dict(template, **{label: "32"}))
        checks.observe(form, "33-artifacts", encode(boundary), "support_count_exceeded" if form == "common" else "artifact_count_exceeded")
        exact_raw = encode(empty)
        exact_raw += b" " * (LIMIT - len(exact_raw))
        checks.observe(form, "raw-exact-limit", exact_raw, expected_payload=empty)
        checks.observe(form, "raw-over-limit", exact_raw + b" ", "raw_size_exceeded")
        escaped_key = "\\u%04x" % ord(primary[0]) + primary[1:]
        checks.observe(form, "duplicate-escaped-top-key", ('{"%s":"","%s":""}' % (primary, escaped_key)).encode("ascii"), "duplicate_json_key")
        nested = ('{"%s":"","%s":[{"%s":"one","%s":"two","text":""}]}' % (primary, items, label, label)).encode("ascii")
        checks.observe(form, "duplicate-nested-key", nested, "duplicate_json_key")
        checks.observe(form, "invalid-utf8", b'\xff', "invalid_utf8")
        checks.observe(form, "malformed-json", b'{', "malformed_json")
        checks.observe(form, "nonfinite", ('{"%s":1e999}' % primary).encode("ascii"), "nonfinite_json_number")
        checks.observe(form, "extra-field", encode(dict(base, unwanted="extra")), "malformed_field")
        duplicate = copy.deepcopy(base)
        duplicate[items][1][label] = duplicate[items][0][label]
        checks.observe(form, "duplicate-artifact-identity", encode(duplicate), "duplicate_support_id" if form == "common" else "duplicate_artifact_name")
        surrogate = encode(base, ascii_only=True).replace(b'Literal', b'\\ud800')
        checks.observe(form, "unpaired-surrogate", surrogate, "invalid_unicode_text")
        for previous in ("baseline", "invalid-utf8"):
            destination = checks.root / (form + "-" + previous) / "capture"
            before = {path.name: path.read_bytes() for path in destination.iterdir()}
            checks.observe(form, "reuse-" + previous, b'new submitted bytes not captured', "destination_exists", destination=destination)
            checks.expect(before == {path.name: path.read_bytes() for path in destination.iterdir()}, form + " prior destination unchanged " + previous)
        if form == "common":
            for key in ("question_id", "source_revision"):
                mismatch = dict(base, **{key: "different"})
                checks.observe(form, "mismatched-" + key, encode(mismatch), "identity_mismatch")
            reframe = dict(base, response_kind="reframe")
            checks.observe(form, "reframe", encode(reframe), expected_payload=reframe)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, help="Fresh evidence directory; its parent must exist; no cleanup is performed.")
    parser.add_argument("--pinned-prototype", required=True, help="Read-only pinned submit.py used only for common validator AST comparison.")
    args = parser.parse_args()
    root = Path(args.evidence).absolute()
    root.mkdir()
    helper = Path(__file__).absolute().with_name("capture.py")
    pinned = Path(args.pinned_prototype).absolute()
    write_receipt(root / "capture.py", helper.read_bytes())
    write_receipt(root / "check.py", Path(__file__).read_bytes())
    write_receipt(root / "pinned-submit.py", pinned.read_bytes())
    checks = Checks(root, helper)
    status, error = "passed", None
    try:
        run(checks, pinned)
    except Exception as exc:
        status, error = "failed", repr(exc)
    result = {"status": status, "error": error, "assertions": checks.assertions,
              "helper_invocations": len(checks.invocations), "invocations": checks.invocations,
              "interpreter": sys.executable, "version": sys.version,
              "helper_identity": identity(helper.read_bytes()), "check_identity": identity(Path(__file__).read_bytes()),
              "installed_wheel_pytest_nodes": 0, "project_subject_executions": 0,
              "qualification": "Bounded standalone helper checks and static common-validator equality, not project or hostile-filesystem qualification."}
    write_receipt(root / "RESULT.json", encode(result))
    print(json.dumps(result, indent=2))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
