#!/usr/bin/env python3
"""Replaceable study submission helper; not Stewart custody or access enforcement."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys


MAX_RAW_BYTES = 1024 * 1024
MAX_SUPPORT = 32
ENVELOPE_FIELDS = {
    "question_id", "source_revision", "author", "response_kind",
    "completion_claim", "answer", "support",
}
SUPPORT_FIELDS = {"id", "role", "encoding", "text"}


class SubmissionError(Exception):
    """Stable study refusal; no project exception or implementation is imported."""

    def __init__(self, reason, detail):
        super().__init__(detail)
        self.reason = reason


def write_receipt(path, chunks):
    """Create once, without replacement; leave even a partial file on failure.

    A byte string or iterable of byte strings is accepted. This deliberately
    promises neither fsync durability nor crash safety. Paths are supplied by
    this helper, never selected by support IDs or payload references.
    """
    with path.open("xb") as stream:
        if isinstance(chunks, bytes):
            chunks = (chunks,)
        for chunk in chunks:
            stream.write(chunk)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode("ascii")


def unique_names(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise SubmissionError("duplicate_json_key", "Repeated object key: " + repr(key))
        value[key] = item
    return value


def reject_constant(token):
    raise SubmissionError("nonfinite_json_number", "Nonfinite JSON constant: " + token)


def finite_float(token):
    value = float(token)
    if not math.isfinite(value):
        raise SubmissionError("nonfinite_json_number", "JSON number exceeds finite float range")
    return value


def require_text(value, location, nonempty=False):
    if not isinstance(value, str) or (nonempty and not value):
        raise SubmissionError("malformed_field", location + " must be " + ("a nonempty string" if nonempty else "a string"))
    try:
        value.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise SubmissionError("invalid_unicode_text", location + " contains an unpaired surrogate") from exc


def require_fields(value, fields, location):
    if not isinstance(value, dict) or set(value) != fields:
        raise SubmissionError("malformed_field", location + " must contain exactly: " + ", ".join(sorted(fields)))


def decode_validate(raw, expected_question, expected_revision):
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise SubmissionError("invalid_utf8", "Submission is not valid UTF-8") from exc
    try:
        envelope = json.loads(text, object_pairs_hook=unique_names,
                              parse_constant=reject_constant, parse_float=finite_float)
    except SubmissionError:
        raise
    except (ValueError, RecursionError) as exc:
        raise SubmissionError("malformed_json", "Submission is not a supported complete JSON document: " + str(exc)) from exc
    require_fields(envelope, ENVELOPE_FIELDS, "envelope")
    for field in ENVELOPE_FIELDS - {"support"}:
        require_text(envelope[field], field)
    if envelope["question_id"] != expected_question or envelope["source_revision"] != expected_revision:
        raise SubmissionError("identity_mismatch", "Question/source identity differs from explicit expected arguments")
    if envelope["response_kind"] not in {"answer", "needs-evidence", "reframe"}:
        raise SubmissionError("malformed_field", "response_kind must be answer, needs-evidence or reframe")
    support = envelope["support"]
    if not isinstance(support, list):
        raise SubmissionError("malformed_field", "support must be an ordered array")
    if len(support) > MAX_SUPPORT:
        raise SubmissionError("support_count_exceeded", "support exceeds 32 objects; no objects were discarded")
    seen = set()
    for index, item in enumerate(support):
        location = "support[{}]".format(index)
        require_fields(item, SUPPORT_FIELDS, location)
        for field in SUPPORT_FIELDS:
            require_text(item[field], location + "." + field, nonempty=field == "id")
        if item["id"] in seen:
            raise SubmissionError("duplicate_support_id", "Repeated support ID: " + repr(item["id"]))
        seen.add(item["id"])
        if item["encoding"] != "utf-8":
            raise SubmissionError("unsupported_encoding", location + ".encoding must be utf-8")
    return envelope


def byte_identity(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def snapshot(envelope, raw_identity, expected_question, expected_revision):
    answer_identity = byte_identity(envelope["answer"].encode("utf-8"))
    support_identities = [dict(id=item["id"], **byte_identity(item["text"].encode("utf-8")))
                          for item in envelope["support"]]
    return {
        "format": "fresh-authoring-submission-prototype-v1",
        "structural_acceptance": True,
        "intellectual_assessment": "not_performed",
        "attribution": {"author": "submitted claim", "completion_claim": "submitted claim"},
        "expected_identity": {"question_id": expected_question, "source_revision": expected_revision},
        "envelope": envelope,
        "byte_observations": {
            "raw_transport": raw_identity,
            "decoded_answer_utf8": answer_identity,
            "decoded_support_text_utf8_in_submission_order": support_identities,
            "decoded_answer_and_support_utf8_bytes": answer_identity["bytes"] + sum(item["bytes"] for item in support_identities),
        },
        "qualification": "Study observation only; no intellectual verdict, custody, access enforcement, durability, delivery or replay claim.",
    }


def run(args):
    destination = Path(os.path.abspath(args.destination))
    paths = {"destination": str(destination)}
    try:
        destination.mkdir(mode=0o700)
    except FileExistsError:
        return 2, {"status": "refused", "reason": "destination_exists", "paths": paths,
                   "retained_by_this_invocation": [],
                   "detail": "Existing destinations, including failed attempts, cannot be reused; stdin was not captured.",
                   "next_step": "Keep the existing directory and the independent input witness; assign a new destination."}
    except OSError as exc:
        return 2, {"status": "refused", "reason": "destination_create_failed", "paths": paths,
                   "retained_by_this_invocation": [], "detail": str(exc),
                   "next_step": "Preserve the independent input witness; correct the destination parent and assign a fresh destination."}
    paths.update(raw=str(destination / "attempt.raw"), snapshot=str(destination / "SNAPSHOT.json"),
                 accepted=str(destination / "ACCEPTED.json"), failure=str(destination / "FAILURE.json"))
    raw_count, raw_hasher, small_chunks = 0, hashlib.sha256(), []

    def incoming():
        nonlocal raw_count
        while True:
            chunk = sys.stdin.buffer.read(65536)
            if not chunk:
                return
            raw_count += len(chunk)
            raw_hasher.update(chunk)
            if raw_count <= MAX_RAW_BYTES:
                small_chunks.append(chunk)
            yield chunk

    phase = "input_capture"
    try:
        write_receipt(destination / "attempt.raw", incoming())
        raw_identity = {"bytes": raw_count, "sha256": raw_hasher.hexdigest()}
        phase = "validation"
        if raw_count > MAX_RAW_BYTES:
            raise SubmissionError("raw_size_exceeded", "Raw submission exceeds 1048576 bytes; the entire attempt is retained")
        envelope = decode_validate(b"".join(small_chunks), args.question_id, args.source_revision)
        phase = "snapshot_write"
        write_receipt(destination / "SNAPSHOT.json", json_bytes(snapshot(envelope, raw_identity, args.question_id, args.source_revision)))
        phase = "acceptance_write"
        result = {"status": "structurally_accepted", "reason": "structure_accepted", "paths": paths,
                  "raw_transport": raw_identity, "intellectual_assessment": "not_performed",
                  "next_step": "Inspect the snapshot and its exact selected bytes; acceptance is not an intellectual assessment."}
        write_receipt(destination / "ACCEPTED.json", json_bytes(result))
        return 0, result
    except (SubmissionError, OSError, RecursionError) as exc:
        reason = exc.reason if isinstance(exc, SubmissionError) else ("input_capture_failed" if phase == "input_capture" else "record_write_failed")
        failure = {"status": "rejected" if phase == "validation" else "partial",
                   "reason": reason, "phase": phase, "detail": str(exc), "paths": paths,
                   "input_capture_complete": phase != "input_capture",
                   "raw_transport": {"bytes_read": raw_count, "sha256_of_bytes_read": raw_hasher.hexdigest()},
                   "next_step": "Keep this directory and independent witness; inspect the reason and use a fresh destination for another attempt."}
        try:
            write_receipt(destination / "FAILURE.json", json_bytes(failure))
        except OSError as record_exc:
            failure["failure_record_error"] = str(record_exc)
            failure["next_step"] = "Retain this emitted diagnostic with the independent witness; preserve all partial paths and use a fresh destination."
        return 2, failure


def main():
    parser = argparse.ArgumentParser(description="Capture stdin JSON into a fresh coordinator-assigned study destination before structural validation. No project code is imported.")
    parser.add_argument("--destination", required=True, help="Fresh directory whose parent already exists; never selected by payload fields. Existing directories are refused before stdin capture.")
    parser.add_argument("--question-id", required=True, help="Expected question identity, matched exactly.")
    parser.add_argument("--source-revision", required=True, help="Expected subject revision, matched exactly.")
    args = parser.parse_args()
    code, result = run(args)
    sys.stdout.buffer.write(json_bytes(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
