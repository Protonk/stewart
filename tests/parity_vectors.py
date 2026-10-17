"""Emit fixed utility vectors from an installed distribution for a consumer bridge.

This producer imports no containing project's code. The caller compares these
results with its own byte contracts; the wheel digest identifies the installation.
"""
import json
from pathlib import Path
import sys

from stewart import _util


def vectors():
    values = ({}, {"z": "é\n", "a": {"β": [1, True, None]}}, {"a": 1, "b": 2}, {"b": 2, "a": 1})
    return {
        "json": [{"input": value, "canonical": _util.canonical_json(value),
                  "digest": _util.sha256_canonical_json(value),
                  "receipt_hex": _util.receipt_json_bytes(value).hex()} for value in values],
        "bytes": [{"input_hex": value.hex(), "bytes_digest": _util.sha256_bytes(value),
                   "text_digest": _util.sha256_text(value.decode())}
                  for value in (b"", b"abc", "é\n".encode(), b"abc\n")],
        "paths": [{"input": value, "root": "/tmp/stewart-parity", "result": _util.rel(value, Path("/tmp/stewart-parity"))}
                  for value in ("relative/member", "/tmp/stewart-parity/inside", "/tmp/external")],
        "relative": [{"input": value, "result": _util.require_rel(value)} for value in ("a", "a/b", ".")],
    }


if __name__ == "__main__":
    value = {"wheel_sha256": sys.argv[2], "vectors": vectors()}
    Path(sys.argv[1]).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
