#!/usr/bin/env python3
"""Dual-form study capture; not Stewart custody or access enforcement.

The common payload validator retains the pinned prototype's admission rules.
Assignment provenance is external to either author's submitted payload.
"""

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
MINIMAL_FIELDS = {"text", "artifacts"}
ARTIFACT_FIELDS = {"name", "text"}


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


def decode_json(raw):
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
    return envelope


def validate_common(envelope, expected_question, expected_revision):
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


def validate_minimal(envelope):
    require_fields(envelope, MINIMAL_FIELDS, "minimal return")
    require_text(envelope["text"], "text")
    artifacts = envelope["artifacts"]
    if not isinstance(artifacts, list):
        raise SubmissionError("malformed_field", "artifacts must be an ordered array")
    if len(artifacts) > MAX_SUPPORT:
        raise SubmissionError("artifact_count_exceeded", "artifacts exceeds 32 objects; no objects were discarded")
    seen = set()
    for index, item in enumerate(artifacts):
        location = "artifacts[{}]".format(index)
        require_fields(item, ARTIFACT_FIELDS, location)
        require_text(item["name"], location + ".name", nonempty=True)
        require_text(item["text"], location + ".text")
        if item["name"] in seen:
            raise SubmissionError("duplicate_artifact_name", "Repeated artifact name: " + repr(item["name"]))
        seen.add(item["name"])
    return envelope


def byte_identity(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def capture_metadata(args):
    return {
        "form": args.form,
        "expected_identity": {"question_id": args.question_id, "source_revision": args.source_revision},
        "issued_provenance": {"author_id": args.author_id, "phase": args.phase},
        "provenance_source": "explicit coordinator CLI arguments; not inferred from submitted text",
    }


def snapshot(envelope, raw_identity, metadata):
    common = metadata["form"] == "common"
    text_field, items_field, name_field = ("answer", "support", "id") if common else ("text", "artifacts", "name")
    answer_identity = byte_identity(envelope[text_field].encode("utf-8"))
    item_identities = [dict(position=index, **{name_field: item[name_field]},
                            **byte_identity(item["text"].encode("utf-8")))
                       for index, item in enumerate(envelope[items_field])]
    # The original payload stays intact: minimal has no invented kind,
    # completion claim or artifact roles. Observation names are form-neutral.
    return {
        "format": "answer-revision-capture-v1",
        "structural_acceptance": True,
        "intellectual_assessment": "not_performed",
        "capture_metadata": metadata,
        "attribution": {"payload": "submitted author-selected content", **(
            {"author": "submitted claim", "completion_claim": "submitted claim"} if common else {})},
        "envelope": envelope,
        "byte_observations": {
            "raw_transport": raw_identity,
            "primary_text_field": text_field,
            "decoded_primary_text_utf8": answer_identity,
            "artifact_array_field": items_field,
            "decoded_artifact_text_utf8_in_submission_order": item_identities,
            "decoded_primary_and_artifact_utf8_bytes": answer_identity["bytes"] + sum(item["bytes"] for item in item_identities),
        },
        "qualification": "Study observation only; no intellectual verdict, custody, access enforcement, durability, delivery or replay claim.",
    }


def run(args):
    destination = Path(os.path.abspath(args.destination))
    metadata = capture_metadata(args)
    paths = {"destination": str(destination)}
    try:
        destination.mkdir(mode=0o700)
    except FileExistsError:
        return 2, {"status": "refused", "reason": "destination_exists", "paths": paths, "capture_metadata": metadata,
                   "retained_by_this_invocation": [],
                   "detail": "Existing destinations, including failed attempts, cannot be reused; stdin was not captured.",
                   "next_step": "Keep the existing directory and the independent input witness; assign a new destination."}
    except OSError as exc:
        return 2, {"status": "refused", "reason": "destination_create_failed", "paths": paths, "capture_metadata": metadata,
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
        envelope = decode_json(b"".join(small_chunks))
        envelope = (validate_common(envelope, args.question_id, args.source_revision)
                    if args.form == "common" else validate_minimal(envelope))
        phase = "snapshot_write"
        write_receipt(destination / "SNAPSHOT.json", json_bytes(snapshot(envelope, raw_identity, metadata)))
        phase = "acceptance_write"
        result = {"status": "structurally_accepted", "reason": "structure_accepted", "paths": paths,
                  "capture_metadata": metadata, "raw_transport": raw_identity, "intellectual_assessment": "not_performed",
                  "next_step": "Inspect the snapshot and its exact selected bytes; acceptance is not an intellectual assessment."}
        write_receipt(destination / "ACCEPTED.json", json_bytes(result))
        return 0, result
    except (SubmissionError, OSError, RecursionError) as exc:
        reason = exc.reason if isinstance(exc, SubmissionError) else ("input_capture_failed" if phase == "input_capture" else "record_write_failed")
        failure = {"status": "rejected" if phase == "validation" else "partial",
                   "reason": reason, "phase": phase, "detail": str(exc), "paths": paths, "capture_metadata": metadata,
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
    parser = argparse.ArgumentParser(
        description="Capture common-envelope or minimal text/artifacts stdin JSON before structural validation. Standalone procedural study capture; no project code is imported.",
        epilog="Save an independent input witness first. Acceptance allows at most 1048576 raw bytes and 32 artifacts; the entire stdin stream is retained even over the bound (not a disk/time limit). Failures and partial paths remain. Use a new destination after any attempt. No payload references are opened; no intellectual assessment, custody or durability is established.")
    parser.add_argument("--destination", required=True, help="Fresh directory whose parent already exists; never selected by payload fields. Existing directories are refused before stdin capture.")
    parser.add_argument("--question-id", required=True, help="Issued question identity; matched exactly to common fields and recorded externally for minimal.")
    parser.add_argument("--source-revision", required=True, help="Issued subject revision; matched exactly to common fields and recorded externally for minimal.")
    parser.add_argument("--form", required=True, choices=("common", "minimal"), help="Explicit submitted form; common identity fields must match CLI identity, minimal identity is recorded only in metadata.")
    parser.add_argument("--author-id", required=True, help="Issued author identity, recorded as coordinator provenance for either form; does not replace or constrain a common payload's author claim.")
    parser.add_argument("--phase", required=True, help="Issued phase label, recorded as coordinator provenance for either form.")
    args = parser.parse_args()
    code, result = run(args)
    sys.stdout.buffer.write(json_bytes(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
