"""Decode Stewart control and custody JSON without choosing among repeated names.

This is an authoring/interpretation boundary, not an evidence acquisition gate.
Raw child ledger rows and child receipts retain their separate decoding contract.
Callers add their own schema validation and contextual refusal diagnostics.
"""
from __future__ import annotations

import json
from typing import Any


class DuplicateKey(ValueError):
    """One object repeats a decoded name, even if both values are identical."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"repeated JSON object key {key!r}; each object must have unique keys")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    # json supplies decoded names at every object depth. Escaped aliases collide;
    # the same name in distinct objects does not. Never discard a competing value.
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKey(key)
        result[key] = value
    return result


def loads_control(data: str | bytes) -> Any:
    """Decode control JSON with unique names; this is not a general strict-JSON mode."""
    return json.loads(data, object_pairs_hook=_unique_object)
